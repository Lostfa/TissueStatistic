"""
BOA 分割 API
提供 BOA 环境检测、分割启动和状态查询的 HTTP 端点。

BOA 在 conda 环境中以命令行方式运行，每张 CT 图像依次处理。
输出为标准 NIfTI 标签文件：bca.nii.gz, total.nii.gz, tissues.nii.gz
"""
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tasks.manager import task_manager
from wrappers.boa import (
    check_boa_environment,
    run_boa_segmentation,
    get_segmentation_status,
)

router = APIRouter(prefix="/api/boa", tags=["BOA分割"])


# ---- 请求/响应模型 ----
class StartBOARequest(BaseModel):
    base_path: str
    patient_ids: List[str]
    models: str = "all"  # all|total|bca|total+bca


# ---- API 端点 ----
@router.get("/check-environment")
async def api_check_environment():
    """检测 BOA 运行环境（conda环境、命令可用性、GPU状态）"""
    return check_boa_environment()


@router.post("/start")
async def start_boa_segmentation(request: StartBOARequest):
    """
    启动 BOA 分割任务。

    对选定的每位患者依次运行 BOA 命令行工具。
    每位患者的处理时间取决于 CT 体积和 GPU 性能，可能从几分钟到数十分钟。

    参数:
        base_path: 工作根目录（包含 ct_image/ 子目录）
        patient_ids: 要处理的患者ID列表
        models: 分割模型选择
    """
    ct_dir = os.path.join(request.base_path, "ct_image")
    if not os.path.isdir(ct_dir):
        raise HTTPException(
            status_code=400,
            detail=f"ct_image 目录不存在: {ct_dir}。请先完成步骤1的数据预处理。"
        )

    # 收集有效的患者
    valid_patients = []
    skipped_patients = []
    for pid in request.patient_ids:
        input_file = os.path.join(ct_dir, f"{pid}.nii.gz")
        if os.path.isfile(input_file):
            output_dir = os.path.join(request.base_path, "boa_label", pid)
            valid_patients.append({
                "patient_id": pid,
                "input_file": input_file,
                "output_dir": output_dir,
            })
        else:
            skipped_patients.append(pid)

    if not valid_patients:
        raise HTTPException(
            status_code=400,
            detail="没有找到有效的CT图像文件（.nii.gz）。请确认 ct_image/ 目录中包含预处理完成的图像。"
        )

    # 创建后台任务
    task = task_manager.create("boa_segmentation", total_work=len(valid_patients))
    result_container = {
        "patients": [],
        "success_count": 0,
        "fail_count": 0,
        "skipped": skipped_patients,
    }

    def _run(task_obj):
        for i, p in enumerate(valid_patients):
            if task_obj.is_cancelled:
                task_obj.update(task_obj.progress, "Task cancelled")
                return

            pid = p["patient_id"]
            progress_pct = int(i / len(valid_patients) * 100)
            task_obj.update(
                progress_pct,
                f"({i + 1}/{len(valid_patients)}) BOA segmenting: {pid}"
            )

            try:
                # 启动 BOA 进程
                proc = run_boa_segmentation(
                    p["input_file"],
                    p["output_dir"],
                    models=request.models,
                )

                # 实时读取并转发 BOA 输出到任务日志
                output_lines = []
                for line in proc.stdout:
                    line = line.strip()
                    if line:
                        output_lines.append(line)
                        # 每隔5行记录一次，避免日志过多
                        if len(output_lines) % 5 == 0:
                            task_obj.log.append(f"[BOA:{pid}] {line[:200]}")

                proc.wait()

                if proc.returncode == 0:
                    result_container["success_count"] += 1
                    task_obj.advance(
                        1,
                        f"[OK] BOA segmentation done: {pid}"
                    )
                    result_container["patients"].append({
                        "patient_id": pid,
                        "success": True,
                        "output_dir": p["output_dir"],
                    })
                else:
                    # 返回码非零，显示最后的错误信息
                    last_lines = "\n".join(output_lines[-5:]) if output_lines else "无输出"
                    result_container["fail_count"] += 1
                    task_obj.advance(
                        1,
                        f"[FAIL] BOA exited abnormally: {pid} (code={proc.returncode})"
                    )
                    task_obj.log.append(f"[ERROR:{pid}] {last_lines[:500]}")
                    result_container["patients"].append({
                        "patient_id": pid,
                        "success": False,
                        "error": f"返回码 {proc.returncode}",
                    })

            except Exception as e:
                result_container["fail_count"] += 1
                task_obj.advance(1, f"[EXCEPTION] {pid}: {str(e)}")
                task_obj.log.append(f"[EXCEPTION:{pid}] {str(e)}")
                result_container["patients"].append({
                    "patient_id": pid,
                    "success": False,
                    "error": str(e),
                })

        task_obj.result = result_container
        task_obj.update(100, f"BOA segmentation all done: {result_container['success_count']} OK, {result_container['fail_count']} failed")

    task.start(_run)

    message = f"BOA task submitted for {len(valid_patients)} series"
    if skipped_patients:
        message += f", {len(skipped_patients)} skipped (file not found)"

    return {
        "task_id": task.id,
        "total_patients": len(valid_patients),
        "skipped_patients": skipped_patients,
        "message": message,
    }


@router.get("/patients")
async def list_boa_patients(base_path: str):
    """列出所有患者的分割完成状态"""
    patients = get_segmentation_status(base_path)
    done = sum(1 for p in patients if p["status"] == "done")
    return {
        "patients": patients,
        "total": len(patients),
        "done_count": done,
    }
