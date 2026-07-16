"""
后台任务管理器
负责创建、跟踪、取消长时间运行的后台任务（预处理、BOA分割、统计分析等）。
支持通过SSE（Server-Sent Events）向客户端推送实时进度更新。
"""
import threading
import time
import uuid
import json
from enum import Enum
from datetime import datetime
from typing import Dict, Optional, Callable, Any, List


class TaskStatus(str, Enum):
    """任务状态枚举"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task:
    """
    单个后台任务对象。
    工作线程通过 update() 和 advance() 方法更新进度和日志。
    外部通过 status, progress, log 等属性读取状态。
    """

    def __init__(self, task_type: str, total_work: int = 100):
        self.id = str(uuid.uuid4())[:8]
        self.type = task_type
        self.status = TaskStatus.QUEUED
        self.progress = 0  # 0-100
        self.total_work = total_work
        self.completed_work = 0
        self.message = ""
        self.log: List[str] = []
        self.result: Any = None
        self.error: Optional[str] = None
        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.updated_at = self.created_at
        self._cancel_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self, target: Callable, args: tuple = ()):
        """在后台线程中启动任务"""
        self.status = TaskStatus.RUNNING
        self.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._thread = threading.Thread(
            target=self._run_wrapper, args=(target, args), daemon=True
        )
        self._thread.start()

    def _run_wrapper(self, target: Callable, args: tuple):
        """包装执行函数，管理任务生命周期"""
        try:
            target(self, *args)
            if not self._cancel_event.is_set():
                self.status = TaskStatus.COMPLETED
                self.progress = 100
                self.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            self.status = TaskStatus.FAILED
            self.error = str(e)
            self.log.append(f"[ERROR] {e}")
            self.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def cancel(self):
        """取消正在运行的任务"""
        self._cancel_event.set()
        self.status = TaskStatus.CANCELLED
        self.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def update(self, progress: int, message: str = None):
        """更新进度百分比和消息"""
        self.progress = min(max(progress, 0), 100)
        timestamp = datetime.now().strftime("%H:%M:%S")
        if message:
            self.message = message
            self.log.append(f"[{timestamp}] {message}")
        self.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def advance(self, amount: int = 1, message: str = None):
        """增加已完成工作量并自动计算进度百分比"""
        self.completed_work += amount
        progress = int((self.completed_work / max(self.total_work, 1)) * 100)
        self.update(progress, message)

    def to_dict(self) -> dict:
        """序列化为可JSON传输的字典"""
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "log": self.log[-50:],  # 只返回最后50条日志
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class TaskManager:
    """
    全局任务管理器（单例模式）。
    线程安全地管理所有活跃任务。
    后台线程定期清理已完成超过1小时的旧任务。
    """

    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()
        self._cleanup_thread: Optional[threading.Thread] = None

    def create(self, task_type: str, total_work: int = 100) -> Task:
        """创建新任务并注册到管理器中"""
        task = Task(task_type, total_work)
        with self._lock:
            self._tasks[task.id] = task
        return task

    def get(self, task_id: str) -> Optional[Task]:
        """根据ID获取任务"""
        with self._lock:
            return self._tasks.get(task_id)

    def list(self, status: Optional[str] = None,
             task_type: Optional[str] = None) -> List[dict]:
        """列出所有任务，支持按状态和类型过滤"""
        with self._lock:
            tasks = list(self._tasks.values())

        if status:
            tasks = [t for t in tasks if t.status.value == status]
        if task_type:
            tasks = [t for t in tasks if t.type == task_type]

        # 按创建时间降序排列
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return [t.to_dict() for t in tasks]

    def cancel(self, task_id: str) -> bool:
        """取消指定任务"""
        task = self.get(task_id)
        if task and task.status in (TaskStatus.QUEUED, TaskStatus.RUNNING):
            task.cancel()
            return True
        return False

    def _cleanup_old_tasks(self):
        """清理已完成/失败/取消超过1小时的旧任务"""
        while True:
            time.sleep(600)  # 每10分钟检查一次
            with self._lock:
                now = datetime.now()
                to_remove = []
                for tid, task in self._tasks.items():
                    if task.status in (
                        TaskStatus.COMPLETED,
                        TaskStatus.FAILED,
                        TaskStatus.CANCELLED,
                    ):
                        try:
                            updated = datetime.strptime(
                                task.updated_at, "%Y-%m-%d %H:%M:%S"
                            )
                            if (now - updated).total_seconds() > 3600:
                                to_remove.append(tid)
                        except ValueError:
                            pass
                for tid in to_remove:
                    del self._tasks[tid]

    def start_cleanup(self):
        """启动后台清理线程"""
        if self._cleanup_thread is None:
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_old_tasks, daemon=True
            )
            self._cleanup_thread.start()


# 全局任务管理器单例
task_manager = TaskManager()
