"""
统计分析API
提供模式B（单次检查）的统计分析HTTP端点。
"""
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tasks.manager import task_manager
from wrappers.analysis import (
    run_mode_b_analysis,
    scan_analysis_dirs,
    DEFAULT_VERTEBRA_LIST,
    DEFAULT_RANGE_LIST,
)

router = APIRouter(prefix="/api/analysis", tags=["统计分析"])


# ---- 请求/响应模型 ----
class ModeBRequest(BaseModel):
    base_path: str
    workers: int = 4
    vertebrae: Optional[List[str]] = None
    ranges: Optional[List[int]] = None
    include_all: bool = True
    # 组织阈值设定参数
    threshold_enabled: bool = False
    fat_min: int = -200
    fat_max: int = 0
    muscle_min: int = 1
    muscle_max: int = 150


# ---- API端点 ----
@router.get("/config/defaults")
async def get_default_config():
    """获取默认的椎体列表和范围列表配置"""
    return {
        "vertebrae": DEFAULT_VERTEBRA_LIST,
        "ranges": DEFAULT_RANGE_LIST,
        "tissues": {
            "MUSCLE": "肌肉", "BONE": "骨骼", "SAT": "皮下脂肪",
            "VAT": "腹腔脂肪", "IMAT": "肌间脂肪", "PAT": "纵隔脂肪", "EAT": "心包脂肪",
        },
        "metrics": {
            "volume": "容积", "max-hu": "最大值", "min-hu": "最小值",
            "mean-hu": "均值", "std-hu": "标准差", "median-hu": "中位数",
            "q1-hu": "四分位数间距1", "q3-hu": "四分位数间距2",
        },
    }


@router.post("/mode-b/start")
async def start_mode_b_analysis(request: ModeBRequest):
    """
    启动模式B（单次检查）并行统计分析。

    对 base_path/ct_image/ 中的所有患者，并行执行多项组织成分分析：
    - 全图分析 (ALL)
    - 单椎体+范围（如 L5_1mm, L5_5mm, ...）

    结果保存到 base_path/tissue_statistic/{patient_id}/*.csv
    """
    if not os.path.isdir(os.path.join(request.base_path, "ct_image")):
        raise HTTPException(status_code=400, detail=f"ct_image目录不存在: {request.base_path}/ct_image")

    if not os.path.isdir(os.path.join(request.base_path, "boa_label")):
        raise HTTPException(status_code=400, detail=f"boa_label目录不存在，请先完成BOA分割")

    vertebrae = request.vertebrae or DEFAULT_VERTEBRA_LIST
    ranges = request.ranges or DEFAULT_RANGE_LIST
    workers = max(1, min(8, request.workers))

    tasks_per_patient = (
        (1 if request.include_all else 0) +
        len(vertebrae) * len(ranges)
    )

    import glob as _glob
    patient_count = len(_glob.glob(f"{request.base_path}/ct_image/*.nii.gz"))

    task = task_manager.create("analysis", total_work=patient_count)

    def _run(task_obj):
        run_mode_b_analysis(
            task_obj,
            base_path=request.base_path,
            workers=workers,
            vertebrae=vertebrae,
            ranges=ranges,
            include_all=request.include_all,
            custom_thresholds={
                "enabled": request.threshold_enabled,
                "fat_min": request.fat_min,
                "fat_max": request.fat_max,
                "muscle_min": request.muscle_min,
                "muscle_max": request.muscle_max,
            } if request.threshold_enabled else None,
        )

    task.start(_run)
    return {
        "task_id": task.id,
        "total_patients": patient_count,
        "tasks_per_patient": tasks_per_patient,
        "estimated_total_tasks": patient_count * tasks_per_patient,
    }


class ScanDirsRequest(BaseModel):
    work_dir: str


@router.post("/scan-dirs")
async def api_scan_dirs(request: ScanDirsRequest):
    """
    扫描工作目录下的 ct_image/ 和 boa_label/ 文件夹，
    返回 NIfTI 文件数量和标签子文件夹数量。
    """
    ct_dir = os.path.join(request.work_dir, "ct_image")
    label_dir = os.path.join(request.work_dir, "boa_label")
    return scan_analysis_dirs(ct_dir, label_dir)


@router.get("/csv-files")
async def list_csv_files(base_path: str):
    """列出所有已生成的组织统计CSV文件"""
    from wrappers.merge import scan_csv_files
    return scan_csv_files(base_path)


@router.get("/csv-content")
async def get_csv_content(path: str):
    """读取单个CSV文件内容用于预览"""
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {path}")

    try:
        import pandas as pd
        df = pd.read_csv(path)
        return {
            "headers": list(df.columns),
            "rows": df.head(50).values.tolist(),
            "total_rows": len(df),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取CSV失败: {e}")
