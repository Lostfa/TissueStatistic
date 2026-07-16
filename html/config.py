"""
全局配置模块
管理Web应用的所有可配置参数，支持环境变量覆盖。
"""
import os
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Settings:
    """应用全局设置"""

    # 默认工作目录
    base_working_dir: str = field(
        default_factory=lambda: os.environ.get("TS_BASE_DIR", str(Path.home() / "TissueStatistic"))
    )

    # BOA Docker配置
    docker_image: str = "shipai/boa-cli"
    docker_weights_path: str = field(
        default_factory=lambda: os.environ.get("TS_WEIGHTS_PATH", "")
    )
    docker_gpu_ids: str = "all"
    docker_shm_size: str = "8g"

    # 并行处理配置
    default_workers: int = field(
        default_factory=lambda: min(int(os.environ.get("TS_WORKERS", "4")), os.cpu_count() or 4)
    )

    # 默认分割模型
    default_boa_models: str = "all"

    # 服务器配置
    host: str = "127.0.0.1"
    port: int = 8000

    # 项目根目录
    @property
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    @property
    def pipline_dir(self) -> Path:
        return self.project_root / "pipline"


# 全局单例
settings = Settings()
