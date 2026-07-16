"""
预处理API
提供DICOM/NIfTI扫描和标准化处理的HTTP端点。
"""
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tasks.manager import task_manager
from wrappers.preprocess import (
    scan_dicom_input, scan_nifti_input,
    preprocess_dicom, preprocess_nifti
)

router = APIRouter(prefix="/api/preprocess", tags=["预处理"])


# ---- 请求/响应模型 ----
class ScanInputsRequest(BaseModel):
    input_path: str
    input_type: str  # "dicom" | "nifti"


class StartPreprocessRequest(BaseModel):
    input_path: str
    input_type: str  # "dicom" | "nifti"
    output_base_path: str
    patient_ids: Optional[List[str]] = None  # 可选，指定要处理的子集
    hu_min: int = -3000        # HU值下限
    hu_max: int = 3000         # HU值上限
    gaussian_sigma: float = 0.0  # 高斯平滑sigma（0=禁用）
    output_naming: str = "original"  # "original" | "series_id"
    slice_thickness: float = 1.0     # 层厚mm（0.5-2.5）
    interpolation: str = "sitkBSpline"  # 插值方法


class PatientInfo(BaseModel):
    patient_id: str
    status: str = "pending"


# ---- API端点 ----
@router.post("/scan-inputs")
async def scan_inputs(request: ScanInputsRequest):
    """
    扫描输入目录，识别DICOM序列或NIfTI文件。
    返回检测到的患者列表及其基本信息。
    """
    if not os.path.isdir(request.input_path):
        raise HTTPException(status_code=400, detail=f"目录不存在: {request.input_path}")

    if request.input_type == "dicom":
        patients = scan_dicom_input(request.input_path)
    elif request.input_type == "nifti":
        patients = scan_nifti_input(request.input_path)
    else:
        raise HTTPException(status_code=400, detail=f"不支持的输入类型: {request.input_type}")

    return {
        "patients": patients,
        "total": len(patients),
        "input_path": request.input_path,
        "input_type": request.input_type,
    }


@router.post("/start")
async def start_preprocessing(request: StartPreprocessRequest):
    """
    启动预处理后台任务。
    根据输入类型（DICOM/NIfTI）调用相应的处理逻辑。
    """
    if request.input_type == "dicom":
        all_patients = scan_dicom_input(request.input_path)
    elif request.input_type == "nifti":
        all_patients = scan_nifti_input(request.input_path)
    else:
        raise HTTPException(status_code=400, detail=f"不支持的输入类型: {request.input_type}")

    if not all_patients:
        raise HTTPException(status_code=400, detail="未在输入目录中检测到任何患者数据")

    # 过滤选定的患者
    if request.patient_ids:
        selected = [p for p in all_patients if p["patient_id"] in request.patient_ids]
    else:
        selected = all_patients

    if not selected:
        raise HTTPException(status_code=400, detail="没有匹配的患者数据")

    # 创建输出目录：避免重复拼接ct_image
    base = request.output_base_path.rstrip("/\\")
    if os.path.basename(base) == "ct_image":
        output_dir = base  # 用户已指定ct_image目录
    else:
        output_dir = os.path.join(base, "ct_image")  # 自动创建ct_image子目录

    # 创建后台任务
    task = task_manager.create("preprocess", total_work=len(selected))
    result_container = {"patients": [], "success_count": 0, "fail_count": 0}

    def _run(task_obj):
        for i, patient in enumerate(selected):
            if task_obj.is_cancelled:
                task_obj.update(task_obj.progress, "Task cancelled")
                return

            # 根据命名模式决定输出文件名（去除DICOM元数据可能带入的前后空格）
            if request.output_naming == "original":
                pid = patient.get("original_name", patient["patient_id"]).strip()
            else:
                pid = patient["patient_id"].strip()

            task_obj.update(
                int(i / len(selected) * 100),
                f"({i + 1}/{len(selected)}) Processing: {pid}",
            )

            if request.input_type == "dicom":
                result = preprocess_dicom(
                    patient["input_path"], output_dir, pid,
                    hu_min=request.hu_min, hu_max=request.hu_max,
                    gaussian_sigma=request.gaussian_sigma,
                    slice_thickness=request.slice_thickness,
                    interpolation=request.interpolation,
                )
            else:
                result = preprocess_nifti(
                    patient["input_path"], output_dir, pid,
                    hu_min=request.hu_min, hu_max=request.hu_max,
                    gaussian_sigma=request.gaussian_sigma,
                    slice_thickness=request.slice_thickness,
                    interpolation=request.interpolation,
                )

            result_container["patients"].append(result)
            if result.get("success"):
                result_container["success_count"] += 1

                # ---- Log detailed image info (English, for console) ----
                orig = result.get("original", {})
                res = result.get("result", {})
                task_obj.log.append(f"{'='*50}")
                task_obj.log.append(f"[DONE] Series ID: {pid}")
                task_obj.log.append(f"  Input: {patient.get('input_path', '')}")
                task_obj.log.append(f"{'─'*40}")
                task_obj.log.append(f"  [Original Image]")
                task_obj.log.append(f"    Size: {orig.get('size', '')}")
                task_obj.log.append(f"    Spacing: {orig.get('spacing', '')}")
                task_obj.log.append(f"    Physical (mm): {orig.get('physical_size', '')}")
                task_obj.log.append(f"    Dtype: {orig.get('dtype', '')}")
                task_obj.log.append(f"    HU range: [{orig.get('hu_min', '')}, {orig.get('hu_max', '')}]")
                task_obj.log.append(f"    HU mean ± std: {orig.get('hu_mean', '')} ± {orig.get('hu_std', '')}")
                task_obj.log.append(f"{'─'*40}")
                task_obj.log.append(f"  [Standardized]")
                task_obj.log.append(f"    Size: {res.get('size', '')}")
                task_obj.log.append(f"    Spacing: {res.get('spacing', '')}")
                task_obj.log.append(f"    Physical (mm): {res.get('physical_size', '')}")
                task_obj.log.append(f"    Dtype: {res.get('dtype', '')}")
                task_obj.log.append(f"    HU range: [{res.get('hu_min', '')}, {res.get('hu_max', '')}]")
                task_obj.log.append(f"    HU mean ± std: {res.get('hu_mean', '')} ± {res.get('hu_std', '')}")
                task_obj.log.append(f"  Saved: {result.get('output_path', '')}")
                task_obj.log.append(f"{'='*50}")

                task_obj.advance(1, f"[OK] {pid} — Size {orig.get('size','')} -> {res.get('size','')}, HU[{orig.get('hu_min','')}~{orig.get('hu_max','')}]")
            else:
                result_container["fail_count"] += 1
                task_obj.log.append(f"[FAIL] {pid}: {result.get('error', 'unknown error')}")
                task_obj.advance(1, f"[FAIL] {pid}: {result.get('error', 'unknown error')}")

        task_obj.result = result_container

    task.start(_run)
    return {"task_id": task.id, "total_patients": len(selected)}


@router.get("/patients")
async def list_preprocessed_patients(base_path: str):
    """列出已经完成预处理的患者"""
    ct_dir = os.path.join(base_path, "ct_image")
    if not os.path.isdir(ct_dir):
        return {"patients": [], "total": 0}

    import glob
    files = sorted(glob.glob(os.path.join(ct_dir, "*.nii.gz")))
    patients = []
    for f in files:
        fname = os.path.basename(f)
        pid = fname.replace(".nii.gz", "")
        stat = os.stat(f)
        patients.append({
            "patient_id": pid,
            "filename": fname,
            "path": f,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "modified": stat.st_mtime,
        })

    return {"patients": patients, "total": len(patients)}
