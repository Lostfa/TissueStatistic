"""
CSV合并与导出API
提供服务端的CSV数据合并功能（替代原 tissue_statistic.html 的客户端合并逻辑），
支持扫描CSV文件、生成合并表格和下载结果。
"""
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io

from tasks.manager import task_manager
from wrappers.merge import scan_csv_files, generate_merged_csv

router = APIRouter(prefix="/api/merge", tags=["CSV合并导出"])


# ---- 请求/响应模型 ----
class ScanCSVsRequest(BaseModel):
    base_path: str


class GenerateMergeRequest(BaseModel):
    base_path: str
    include_all: bool = True
    single_vertebrae: List[str] = []
    ranges: List[int] = []
    tissues: List[str] = []
    metrics: List[str] = []
    patient_ids: Optional[List[str]] = None


# ---- API端点 ----
@router.post("/scan-csvs")
async def api_scan_csvs(request: ScanCSVsRequest):
    """
    扫描指定工作目录的 tissue_statistic/ 子目录，
    发现所有患者的CSV分析结果文件。
    """
    if not os.path.isdir(request.base_path):
        raise HTTPException(status_code=400, detail=f"工作目录不存在: {request.base_path}")

    return scan_csv_files(request.base_path)


@router.post("/generate")
async def api_generate_merge(request: GenerateMergeRequest):
    """
    根据用户选择的扫描类型、组织成分和统计指标，
    生成合并后的CSV表格。

    选择逻辑与原 tissue_statistic.html 保持一致：
    - 全图分析 (ALL) × 组织 × 指标
    - 单椎体 (如 L5) × 范围 (如 10mm) × 组织 × 指标
    - 椎体组合 (如 T1-T12) × 组织 × 指标
    """
    # 验证输入
    if not request.include_all and not request.single_vertebrae:
        raise HTTPException(status_code=400, detail="请至少选择一种扫描类型")

    if not request.tissues:
        raise HTTPException(status_code=400, detail="请至少选择一种组织成分")

    if not request.metrics:
        raise HTTPException(status_code=400, detail="请至少选择一种统计指标")

    # 对于单椎体选择，必须同时选择范围
    if request.single_vertebrae and not request.ranges:
        raise HTTPException(status_code=400, detail="选择单椎体分析时必须同时选择分析范围")

    task = task_manager.create("merge_csv")

    def _run(task_obj):
        generate_merged_csv(
            task_obj,
            base_path=request.base_path,
            include_all=request.include_all,
            single_vertebrae=request.single_vertebrae,
            ranges=request.ranges,
            vertebra_pairs=[],
            tissues=request.tissues,
            metrics=request.metrics,
            patient_ids=request.patient_ids,
        )

    task.start(_run)
    return {"task_id": task.id}


@router.get("/download/{task_id}")
async def download_merged_csv(task_id: str):
    """
    下载指定合并任务的CSV结果文件。

    等待任务完成后，以文件下载方式返回合并后的CSV数据。
    文件名包含时间戳以便区分。
    """
    task = task_manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    # 等待任务完成（最多等待60秒）
    import time
    waited = 0
    while task.status.value in ("queued", "running") and waited < 60:
        time.sleep(0.5)
        waited += 0.5

    if task.status.value == "failed":
        raise HTTPException(status_code=500, detail=f"CSV生成失败: {task.error}")

    if task.status.value == "cancelled":
        raise HTTPException(status_code=400, detail="CSV生成已取消")

    if not task.result or "csv_content" not in task.result:
        raise HTTPException(status_code=404, detail="未找到CSV数据")

    csv_content = task.result["csv_content"]

    # 生成文件名
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"tissue_statistics_{timestamp}.csv"

    return StreamingResponse(
        io.BytesIO(csv_content.encode("utf-8-sig")),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/preview/{task_id}")
async def preview_merged_csv(task_id: str):
    """
    预览合并CSV的前100行数据。
    """
    task = task_manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    if task.status.value == "completed" and task.result and "csv_content" in task.result:
        csv_content = task.result["csv_content"]
        lines = csv_content.split("\n")
        headers = lines[0].split(",") if lines else []
        rows = [line.split(",") for line in lines[1:101]]  # 前100行数据
        return {
            "headers": headers,
            "rows": rows,
            "total_rows": task.result.get("total_patients", 0),
            "total_columns": task.result.get("total_columns", 0),
        }

    # 任务还在运行中
    return {
        "headers": [],
        "rows": [],
        "total_rows": 0,
        "total_columns": 0,
        "status": task.status.value,
        "message": "任务尚未完成",
    }
