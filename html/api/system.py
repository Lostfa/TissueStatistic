"""
系统工具API
提供原生文件夹选择对话框、文件管理器打开等系统级功能。
"""
import os
import subprocess
import platform
import tkinter as tk
from tkinter import filedialog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/system", tags=["系统工具"])


class OpenFolderRequest(BaseModel):
    path: str


@router.get("/pick-folder")
async def pick_folder():
    """
    打开系统原生文件夹选择对话框，返回用户选择的完整路径。
    使用 tkinter（Python标准库自带），无需额外安装依赖。

    前端调用此接口后，浏览器会暂时"卡住"等待用户完成选择，
    返回的路径可直接用于后续API调用。
    """
    # 创建隐藏的根窗口
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    root.attributes('-topmost', True)  # 置顶显示对话框
    root.lift()
    root.focus_force()

    try:
        folder_path = filedialog.askdirectory(
            title="请选择文件夹",
            mustexist=True,
        )
        if folder_path:
            # 标准化路径格式
            folder_path = folder_path.replace("/", "\\")
            return {"path": folder_path, "success": True}
        else:
            return {"path": "", "success": False, "message": "用户取消了选择"}
    finally:
        root.destroy()


@router.post("/open-folder")
async def open_folder(request: OpenFolderRequest):
    """
    在操作系统默认文件管理器中打开指定目录。

    支持 Windows（Explorer）、macOS（Finder）和 Linux（xdg-open）。
    """
    target = request.path.strip()
    if not target or not os.path.isdir(target):
        raise HTTPException(status_code=400, detail=f"目录不存在: {target}")

    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(target)
        elif system == "Darwin":
            subprocess.Popen(["open", target])
        else:
            subprocess.Popen(["xdg-open", target])
        return {"success": True, "message": f"已在文件管理器中打开: {target}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"打开失败: {e}")
