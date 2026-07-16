"""
TissueStatistic Web 应用主入口
FastAPI应用，管理CORS、路由注册、静态文件服务和生命周期事件。
将 pipline/ 目录加入 sys.path 以导入现有代码，不修改任何原有文件。
"""
import sys
from pathlib import Path

# ---- 将 pipline/ 加入Python搜索路径，以便导入现有代码 ----
PIPLINE_DIR = Path(__file__).parent.parent / "pipline"
if str(PIPLINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPLINE_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response

from config import settings
from tasks.manager import task_manager

# ---- 创建FastAPI应用 ----
app = FastAPI(
    title="TissueStatistic - CT组织成分统计分析平台",
    description="从CT图像中分割软组织成分并生成统计结果的综合Web平台",
    version="1.0.0",
)

# ---- CORS中间件（允许前端开发时的跨域请求） ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- 生命周期事件 ----
@app.on_event("startup")
async def startup():
    """应用启动时的初始化操作"""
    print(f"[TissueStatistic] 项目根目录: {settings.project_root}")
    print(f"[TissueStatistic] 管线代码目录: {settings.pipline_dir}")
    print(f"[TissueStatistic] 默认工作目录: {settings.base_working_dir}")
    task_manager.start_cleanup()
    print("[TissueStatistic] 任务管理器已启动")


@app.on_event("shutdown")
async def shutdown():
    """应用关闭时的清理操作"""
    print("[TissueStatistic] 应用已关闭")


# ---- 注册API路由 ----
from api.tasks import router as tasks_router
from api.preprocessing import router as preprocessing_router
from api.boa import router as boa_router
from api.analysis import router as analysis_router
from api.merge import router as merge_router
from api.system import router as system_router

app.include_router(tasks_router)
app.include_router(preprocessing_router)
app.include_router(boa_router)
app.include_router(analysis_router)
app.include_router(merge_router)
app.include_router(system_router)


# ---- Favicon ----
@app.get("/favicon.ico")
async def favicon():
    """返回网站图标，避免浏览器请求时返回404"""
    svg_icon = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        '<rect width="32" height="32" rx="6" fill="#1a365d"/>'
        '<text x="16" y="23" text-anchor="middle" font-size="22" fill="white">TS</text>'
        '</svg>'
    )
    return Response(content=svg_icon, media_type="image/svg+xml")


# ---- 健康检查和配置API（直接定义在app.py中） ----
@app.get("/api/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/config")
async def get_config():
    """获取当前应用配置"""
    return {
        "base_working_dir": settings.base_working_dir,
        "docker_image": settings.docker_image,
        "default_workers": settings.default_workers,
        "default_boa_models": settings.default_boa_models,
        "host": settings.host,
        "port": settings.port,
    }


# ---- 静态文件服务 ----
static_dir = Path(__file__).parent / "static"
templates_dir = Path(__file__).parent / "templates"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def serve_index():
    """提供前端主页面"""
    index_path = templates_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "TissueStatistic API Server is running. Frontend not yet built."}
