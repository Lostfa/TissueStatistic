"""
BOA（Body and Organ Analysis）分割包装器
在 conda 环境中通过 subprocess 运行 BOA 命令行工具进行CT图像分割。

BOA 工具输出（每位患者在 {output_dir}/ 下生成）：
- bca.nii.gz       — Body Composition Analysis 标签
- total.nii.gz     — TotalSegmentator 椎体标签
- tissues.nii.gz   — 组织成分标签
- body-regions.nii.gz — 身体区域标签
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional, List

# 确保 pipline/ 在搜索路径中
PIPLINE_DIR = Path(__file__).parent.parent.parent / "pipline"
if str(PIPLINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPLINE_DIR))

# ---- BOA 命令配置 ----
# BOA 可执行路径，根据实际安装情况修改。
# 默认: python c:/python/Boa（boa_bat.py 中使用的路径）
# 也可通过环境变量 TS_BOA_COMMAND 覆盖，如:
#   set TS_BOA_COMMAND=python d:/Boa
#   set TS_BOA_COMMAND=boa
BOA_COMMAND = os.environ.get(
    "TS_BOA_COMMAND",
    "python c:/python/Boa"
)

# 命令行参数模板：{input_image} → 输入CT图像路径, {output_dir} → 输出目录, {models} → 模型选择
# 根据 cli.py 定义的参数: --input-image, --output-dir, --models, --verbose
BOA_ARGS_TEMPLATE = os.environ.get(
    "TS_BOA_ARGS",
    "--input-image {input_image} --output-dir {output_dir} --models {models} --verbose"
)


def check_boa_environment() -> dict:
    """
    检测 BOA 运行环境是否就绪。

    检查项：
    - boa 命令是否可用
    - Python 环境是否包含 body_organ_analysis 包
    - 当前是否在 conda boa 环境中

    返回:
        环境状态字典
    """
    result = {
        "boa_available": False,
        "boa_command": BOA_COMMAND,
        "boa_version": "",
        "conda_env": "",
        "gpu_available": False,
        "gpu_info": "",
        "message": "",
    }

    # 检查当前 conda 环境
    conda_env = os.environ.get("CONDA_DEFAULT_ENV", "")
    result["conda_env"] = conda_env

    # 检查 boa 命令路径是否存在
    boa_cmd_parts = BOA_COMMAND.split()

    if boa_cmd_parts[0] == "python" and len(boa_cmd_parts) >= 2:
        # 格式: python <script_path> — 检查脚本文件是否存在
        script_path = boa_cmd_parts[1]
        if os.path.exists(script_path) and os.path.isdir(script_path):
            # 是目录（如 c:/python/Boa），检查 __main__.py 是否存在
            main_py = os.path.join(script_path, "__main__.py")
            if os.path.isfile(main_py):
                result["boa_available"] = True
                result["boa_command"] = f"python {script_path}"
                result["boa_version"] = f"脚本目录: {script_path}"
            else:
                result["message"] = f"BOA directory exists but missing __main__.py: {script_path}"
                return result
        else:
            result["message"] = f"BOA path not found: {script_path}"
            return result
    else:
        # 直接命令 — 检查是否在 PATH 中
        if not shutil.which(boa_cmd_parts[0]):
            result["message"] = f"BOA command '{boa_cmd_parts[0]}' not found in PATH"
            return result
        else:
            result["boa_available"] = True
            result["boa_command"] = BOA_COMMAND

    # 检查GPU可用性（通过 nvidia-smi）
    try:
        nvidia_proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10
        )
        if nvidia_proc.returncode == 0 and nvidia_proc.stdout.strip():
            result["gpu_available"] = True
            result["gpu_info"] = nvidia_proc.stdout.strip()
    except Exception:
        pass

    # 汇总状态
    if result["boa_available"]:
        env_info = f"conda env: {conda_env}" if conda_env else "conda env not detected"
        result["message"] = f"BOA ready ({result['boa_command']}) | {env_info}"
        if not result["gpu_available"]:
            result["message"] += " | Warning: GPU not detected"

    return result


def build_boa_command(
    input_file: str,
    output_dir: str,
    models: str = "all",
) -> List[str]:
    """
    构建 BOA 命令行参数。

    参数:
        input_file: 输入的 .nii.gz CT 图像绝对路径
        output_dir: 输出目录（结果保存为 boa_label/{patient_id}/ 结构）
        models: 分割模型 (all|total|bca|total+bca)

    返回:
        命令行参数列表，可直接传给 subprocess
    """
    # 标准化路径为绝对路径
    input_file = os.path.abspath(input_file)
    output_dir = os.path.abspath(output_dir)

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 格式化参数
    args_str = BOA_ARGS_TEMPLATE.format(
        input_image=input_file,
        output_dir=output_dir,
        models=models,
    )

    # 构建完整命令
    boa_parts = BOA_COMMAND.split()
    if boa_parts[0] == "python":
        # 使用当前Python解释器
        cmd = [sys.executable] + boa_parts[1:] + args_str.split()
    else:
        cmd = boa_parts + args_str.split()

    return cmd


def run_boa_segmentation(
    input_file: str,
    output_dir: str,
    models: str = "all",
) -> subprocess.Popen:
    """
    启动 BOA 分割进程并返回 Popen 句柄，供调用方实时读取输出。

    参数:
        input_file: 输入CT图像路径 (.nii.gz)
        output_dir: 输出目录
        models: 分割模型选择

    返回:
        运行中的 subprocess.Popen 对象
    """
    cmd = build_boa_command(input_file, output_dir, models)

    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )


def get_segmentation_status(base_path: str) -> List[dict]:
    """
    扫描 BOA 分割结果目录，获取每位患者的分割完成状态及预处理图像信息。

    检查三个关键输出文件：
    - bca.nii.gz       (身体成分分析)
    - total.nii.gz     (椎体分割)
    - tissues.nii.gz   (组织成分)

    同时读取 ct_image/ 中预处理后NIfTI文件的图像尺寸和体素间距。

    参数:
        base_path: 工作根目录（包含 boa_label/ 子目录）

    返回:
        每位患者的分割状态列表（含image_size, image_spacing）
    """
    import glob as _glob
    from wrappers.preprocess import _get_nifti_image_info

    label_dir = os.path.join(base_path, "boa_label")
    ct_dir = os.path.join(base_path, "ct_image")

    if not os.path.isdir(ct_dir):
        return []

    patients = []
    ct_files = sorted(_glob.glob(os.path.join(ct_dir, "*.nii.gz")))

    required_files = ["bca.nii.gz", "total.nii.gz", "tissues.nii.gz"]

    for ct_path in ct_files:
        filename = os.path.basename(ct_path)
        patient_id = filename.replace(".nii.gz", "")
        patient_label_dir = os.path.join(label_dir, patient_id)

        # 读取预处理后NIfTI的图像尺寸和体素间距
        image_info = _get_nifti_image_info(ct_path)

        existing_files = []
        missing_files = []
        for rf in required_files:
            fp = os.path.join(patient_label_dir, rf)
            if os.path.isfile(fp):
                existing_files.append(rf)
            else:
                missing_files.append(rf)

        if len(existing_files) == len(required_files):
            status = "done"
        elif len(existing_files) > 0:
            status = "partial"
        else:
            status = "pending"

        patients.append({
            "patient_id": patient_id,
            "status": status,
            "existing_files": existing_files,
            "missing_files": missing_files,
            "image_size": image_info["image_size"],
            "image_spacing": image_info["image_spacing"],
        })

    return patients
