"""
任务管理API
提供任务列表查询、状态获取、SSE实时流推送和取消功能。
"""
import json
import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from tasks.manager import task_manager, TaskStatus

router = APIRouter(prefix="/api/tasks", tags=["任务管理"])


@router.get("")
async def list_tasks(
    status: Optional[str] = Query(None, description="按状态过滤: queued|running|completed|failed|cancelled"),
    type: Optional[str] = Query(None, description="按类型过滤: preprocess|boa_segment|analysis|merge"),
    limit: int = Query(50, description="返回结果数量上限"),
):
    """
    列出所有任务，支持按状态和类型过滤。
    默认返回最近50条任务记录。
    """
    tasks = task_manager.list(status=status, task_type=type)
    return {"tasks": tasks[:limit], "total": len(tasks)}


@router.get("/{task_id}")
async def get_task(task_id: str):
    """获取单个任务的详细状态"""
    task = task_manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    return task.to_dict()


@router.delete("/{task_id}")
async def cancel_task(task_id: str):
    """取消正在运行或排队中的任务"""
    success = task_manager.cancel(task_id)
    if not success:
        raise HTTPException(status_code=400, detail=f"无法取消任务 {task_id}（可能已完成或不存在）")
    return {"success": True, "message": f"任务 {task_id} 已取消"}


@router.get("/{task_id}/stream")
async def stream_task(task_id: str):
    """
    通过Server-Sent Events (SSE) 实时推送任务进度。
    浏览器可使用 EventSource 接收事件：
      - event: progress  → 进度百分比
      - event: log       → 日志消息
      - event: status    → 最终状态 (completed/failed/cancelled)
      - event: result    → JSON格式的结果数据
      - event: error     → 错误信息
    """
    task = task_manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    async def event_generator():
        """生成符合SSE规范的文本事件流"""
        last_log_index = 0
        last_progress = -1

        def _sse_event(event: str, data: str) -> str:
            """构建单条SSE事件消息"""
            return f"event: {event}\ndata: {data}\n\n"

        # 持续轮询直到任务结束
        while task.status in (TaskStatus.QUEUED, TaskStatus.RUNNING):
            # 检查是否有新日志
            current_log_len = len(task.log)
            if current_log_len > last_log_index:
                for line in task.log[last_log_index:]:
                    # 转义换行符，确保data在一行内
                    safe_line = line.replace("\n", "\\n").replace("\r", "")
                    yield _sse_event("log", safe_line)
                last_log_index = current_log_len

            # 检查进度是否有变化
            if task.progress != last_progress:
                progress_data = json.dumps({
                    "progress": task.progress,
                    "message": task.message or "",
                }, ensure_ascii=False)
                yield _sse_event("progress", progress_data)
                last_progress = task.progress

            await asyncio.sleep(0.8)

        # ---- 循环结束后，补发最后的日志和进度（修复最后一条数据不显示的问题） ----
        current_log_len = len(task.log)
        if current_log_len > last_log_index:
            for line in task.log[last_log_index:]:
                safe_line = line.replace("\n", "\\n").replace("\r", "")
                yield _sse_event("log", safe_line)

        if task.progress != last_progress:
            progress_data = json.dumps({
                "progress": task.progress,
                "message": task.message or "",
            }, ensure_ascii=False)
            yield _sse_event("progress", progress_data)

        # 发送最终状态
        yield _sse_event("status", task.status.value)

        if task.result is not None:
            result_data = json.dumps(task.result, ensure_ascii=False, default=str)
            yield _sse_event("result", result_data)

        if task.error:
            yield _sse_event("error", task.error)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
