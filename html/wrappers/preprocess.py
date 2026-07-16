"""
预处理包装器
包装 pipline/preprocess/ 中的现有DICOM/NIfTI预处理逻辑。
通过 sys.path 导入 utils 模块，所有路径参数化，不修改原有代码。

支持的输入类型：
- DICOM目录：包含DICOM序列文件的文件夹
- NIfTI文件：.nii.gz 或 .nii 格式的单个文件

输出：标准化后的CT图像（z轴间距=1mm），保存为 {patient_id}.nii.gz
"""
import os
import sys
from pathlib import Path

# 确保 pipline/ 在搜索路径中
PIPLINE_DIR = Path(__file__).parent.parent.parent / "pipline"
if str(PIPLINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPLINE_DIR))

import glob
import gzip
import struct
import numpy as np
import SimpleITK as sitk
import traceback
from utils.image_io import ImageIO, ImageInfo
from utils.image_process import ImageProcess


def _parse_interpolation(interp: str):
    """将字符串插值方法名转换为 SimpleITK 插值常量"""
    mapping = {
        "sitkBSpline": sitk.sitkBSpline,
        "sitkLinear": sitk.sitkLinear,
        "sitkNearestNeighbor": sitk.sitkNearestNeighbor,
    }
    return mapping.get(interp, sitk.sitkBSpline)


def preprocess_dicom(dicom_dir: str, output_dir: str, patient_id: str,
                     hu_min: int = -3000, hu_max: int = 3000,
                     gaussian_sigma: float = 0.0,
                     slice_thickness: float = 1.0,
                     interpolation: str = "sitkBSpline") -> dict:
    """
    将单个DICOM序列目录转换为标准化NIfTI文件。

    处理流程：
    1. 读取DICOM序列 → SimpleITK图像
    2. 重采样：xy间距保持原图，z轴间距=slice_thickness
    3. HU值裁剪到 [hu_min, hu_max] 范围
    4. 可选：高斯平滑（gaussian_sigma > 0 时启用）
    5. 保存为 {patient_id}.nii.gz

    参数:
        dicom_dir: DICOM序列所在的目录路径
        output_dir: 输出目录（ct_image/）
        patient_id: 患者标识符，用作输出文件名
        hu_min: HU值下限（默认-3000）
        hu_max: HU值上限（默认3000）
        gaussian_sigma: 高斯平滑sigma（默认0.0表示不启用）
        slice_thickness: 层厚mm（默认1.0）
        interpolation: 插值方法（sitkBSpline/sitkLinear/sitkNearestNeighbor）
    """
    os.makedirs(output_dir, exist_ok=True)

    try:
        # 读取DICOM序列
        itk_image = ImageIO.dcm2itk(dicom_dir)
        original_size = itk_image.GetSize()
        original_spacing = itk_image.GetSpacing()
        original_origin = itk_image.GetOrigin()
        original_direction = itk_image.GetDirection()
        original_dtype = itk_image.GetPixelIDTypeAsString()

        # 获取原始图像的HU值统计
        original_array = sitk.GetArrayFromImage(itk_image)
        original_min = int(np.min(original_array))
        original_max = int(np.max(original_array))
        original_mean = int(np.mean(original_array))
        original_std = int(np.std(original_array))

        # 计算原始物理尺寸
        original_physical = tuple(
            round(s * n, 1) for s, n in zip(original_spacing, original_size)
        )

        # 重采样：xy间距保持原图，z轴间距=用户指定层厚
        new_spacing = (original_spacing[0], original_spacing[1], slice_thickness)
        interp_method = _parse_interpolation(interpolation)
        resized = ImageProcess.itk_resize(
            itk_image, new_spacing=new_spacing, interpolation=interp_method
        )

        # HU值裁剪：限制CT值在 [hu_min, hu_max] 范围内
        resized_array = sitk.GetArrayFromImage(resized)
        resized_array = np.clip(resized_array, hu_min, hu_max)
        resized = sitk.GetImageFromArray(resized_array)
        resized.SetSpacing(new_spacing)
        resized.SetOrigin((0, 0, 0))
        resized.SetDirection((1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0))

        # 可选的高斯平滑
        if gaussian_sigma and gaussian_sigma > 0:
            resized = sitk.DiscreteGaussian(resized, [gaussian_sigma] * 3)
            resized = sitk.Cast(resized, sitk.sitkInt16)

        new_size = resized.GetSize()
        new_dtype = resized.GetPixelIDTypeAsString()

        # 获取重采样后图像的HU值统计
        resized_array = sitk.GetArrayFromImage(resized)
        new_min = int(np.min(resized_array))
        new_max = int(np.max(resized_array))
        new_mean = int(np.mean(resized_array))
        new_std = int(np.std(resized_array))

        # 计算新的物理尺寸
        new_physical = tuple(
            round(s * n, 1) for s, n in zip(new_spacing, new_size)
        )

        # 保存为NIfTI
        save_path = os.path.join(output_dir, f"{patient_id}.nii.gz")
        ImageIO.itk2nii(
            resized, save_path,
            spacing=new_spacing,
            origin=(0, 0, 0),
            direction=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
        )

        return {
            "patient_id": patient_id,
            "output_path": save_path,
            "original": {
                "size": tuple(original_size),
                "spacing": tuple(round(s, 3) for s in original_spacing),
                "origin": tuple(round(o, 1) for o in original_origin),
                "direction": tuple(round(d, 4) for d in original_direction[:3]),
                "dtype": original_dtype,
                "physical_size": original_physical,
                "hu_min": original_min,
                "hu_max": original_max,
                "hu_mean": original_mean,
                "hu_std": original_std,
            },
            "result": {
                "size": tuple(new_size),
                "spacing": tuple(round(s, 3) for s in new_spacing),
                "dtype": new_dtype,
                "physical_size": new_physical,
                "hu_min": new_min,
                "hu_max": new_max,
                "hu_mean": new_mean,
                "hu_std": new_std,
            },
            "success": True,
        }

    except Exception as e:
        return {"patient_id": patient_id, "success": False, "error": str(e)}


def preprocess_nifti(nifti_path: str, output_dir: str, patient_id: str,
                     hu_min: int = -3000, hu_max: int = 3000,
                     gaussian_sigma: float = 0.0,
                     slice_thickness: float = 1.0,
                     interpolation: str = "sitkBSpline") -> dict:
    """
    将单个NIfTI文件转换为标准化格式。

    处理流程：
    1. 读取NIfTI文件 → SimpleITK图像
    2. 重采样：xy间距保持原图，z轴间距=slice_thickness
    3. HU值裁剪到 [hu_min, hu_max] 范围
    4. 可选：高斯平滑（gaussian_sigma > 0 时启用）
    5. 保存为 {patient_id}.nii.gz

    参数:
        nifti_path: 输入的.nii.gz文件路径
        output_dir: 输出目录（ct_image/）
        patient_id: 患者标识符
        hu_min: HU值下限（默认-3000）
        hu_max: HU值上限（默认3000）
        gaussian_sigma: 高斯平滑sigma（默认0.0表示不启用）
        slice_thickness: 层厚mm（默认1.0）
        interpolation: 插值方法（sitkBSpline/sitkLinear/sitkNearestNeighbor）

    返回:
        包含处理结果的字典
    """
    os.makedirs(output_dir, exist_ok=True)

    try:
        # 读取NIfTI文件
        itk_image = ImageIO.nii2itk(nifti_path)
        original_size = itk_image.GetSize()
        original_spacing = itk_image.GetSpacing()
        original_origin = itk_image.GetOrigin()
        original_direction = itk_image.GetDirection()
        original_dtype = itk_image.GetPixelIDTypeAsString()

        # 获取原始图像的HU值统计
        original_array = sitk.GetArrayFromImage(itk_image)
        original_min = int(np.min(original_array))
        original_max = int(np.max(original_array))
        original_mean = int(np.mean(original_array))
        original_std = int(np.std(original_array))

        # 计算原始物理尺寸
        original_physical = tuple(
            round(s * n, 1) for s, n in zip(original_spacing, original_size)
        )

        # 重采样：xy间距保持原图，z轴间距=用户指定层厚
        new_spacing = (original_spacing[0], original_spacing[1], slice_thickness)
        interp_method = _parse_interpolation(interpolation)
        resized = ImageProcess.itk_resize(
            itk_image, new_spacing=new_spacing, interpolation=interp_method
        )

        # HU值裁剪：限制CT值在 [hu_min, hu_max] 范围内
        resized_array = sitk.GetArrayFromImage(resized)
        resized_array = np.clip(resized_array, hu_min, hu_max)
        resized = sitk.GetImageFromArray(resized_array)
        resized.SetSpacing(new_spacing)
        resized.SetOrigin((0, 0, 0))
        resized.SetDirection((1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0))

        # 可选的高斯平滑
        if gaussian_sigma and gaussian_sigma > 0:
            resized = sitk.DiscreteGaussian(resized, [gaussian_sigma] * 3)
            resized = sitk.Cast(resized, sitk.sitkInt16)

        new_size = resized.GetSize()
        new_dtype = resized.GetPixelIDTypeAsString()

        # 获取处理后图像的HU值统计
        resized_array = sitk.GetArrayFromImage(resized)
        new_min = int(np.min(resized_array))
        new_max = int(np.max(resized_array))
        new_mean = int(np.mean(resized_array))
        new_std = int(np.std(resized_array))

        # 计算新的物理尺寸
        new_physical = tuple(
            round(s * n, 1) for s, n in zip(new_spacing, new_size)
        )

        # 保存
        save_path = os.path.join(output_dir, f"{patient_id}.nii.gz")
        ImageIO.itk2nii(
            resized, save_path,
            spacing=new_spacing,
            origin=(0, 0, 0),
            direction=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
        )

        return {
            "patient_id": patient_id,
            "output_path": save_path,
            "original": {
                "size": tuple(original_size),
                "spacing": tuple(round(s, 3) for s in original_spacing),
                "origin": tuple(round(o, 1) for o in original_origin),
                "direction": tuple(round(d, 4) for d in original_direction[:3]),
                "dtype": original_dtype,
                "physical_size": original_physical,
                "hu_min": original_min,
                "hu_max": original_max,
                "hu_mean": original_mean,
                "hu_std": original_std,
            },
            "result": {
                "size": tuple(new_size),
                "spacing": tuple(round(s, 3) for s in new_spacing),
                "dtype": new_dtype,
                "physical_size": new_physical,
                "hu_min": new_min,
                "hu_max": new_max,
                "hu_mean": new_mean,
                "hu_std": new_std,
            },
            "success": True,
        }

    except Exception as e:
        return {"patient_id": patient_id, "success": False, "error": str(e)}


def _count_dicom_files(dir_path: str) -> int:
    """
    检查目录是否包含DICOM文件，返回文件数量。
    支持多种DICOM文件格式：.dcm, .IMA, 无扩展名文件, 以及DICOM魔数检测。

    返回0表示该目录不是DICOM序列目录。
    """
    if not os.path.isdir(dir_path):
        return 0
    count = 0
    try:
        for f in os.listdir(dir_path):
            fpath = os.path.join(dir_path, f)
            if not os.path.isfile(fpath):
                continue
            # 常见DICOM扩展名
            if f.endswith(('.dcm', '.DCM', '.ima', '.IMA', '.dicom', '.DICOM')):
                count += 1
            # 无扩展名的文件（常见DICOM格式）
            elif '.' not in f:
                count += 1
            # 检查DICOM魔数 "DICM"（位于文件偏移128字节处）
            else:
                try:
                    with open(fpath, 'rb') as fh:
                        fh.seek(128)
                        if fh.read(4) == b'DICM':
                            count += 1
                except (IOError, OSError):
                    pass
        return count
    except PermissionError:
        return 0


def _get_dicom_image_info(series_dir: str) -> dict:
    """
    读取DICOM序列的图像尺寸和体素间距信息。

    通过读取第一个DICOM文件的元数据获取：
    - Columns (0028|0011) → x维度
    - Rows (0028|0010) → y维度
    - 系列文件总数 → z维度
    - PixelSpacing (0028|0030) → x, y间距
    - SliceThickness (0018|0050) → z间距

    参数:
        series_dir: DICOM序列目录路径

    返回:
        {"image_size": "(x, y, z)", "image_spacing": "(sx, sy, sz)"}
    """
    try:
        reader = sitk.ImageSeriesReader()
        dcm_files = reader.GetGDCMSeriesFileNames(str(series_dir))
        if not dcm_files:
            print(f"[WARN] _get_dicom_image_info 未找到DICOM文件: {series_dir}")
            return {"image_size": "N/A", "image_spacing": "N/A"}

        z_size = len(dcm_files)

        file_reader = sitk.ImageFileReader()
        file_reader.SetFileName(dcm_files[0])
        file_reader.LoadPrivateTagsOn()
        file_reader.ReadImageInformation()

        cols = file_reader.GetMetaData('0028|0011')  # Columns = x
        rows = file_reader.GetMetaData('0028|0010')  # Rows = y
        px_spacing = file_reader.GetMetaData('0028|0030').split('\\')  # "x_spacing\y_spacing"

        try:
            slice_thickness = file_reader.GetMetaData('0018|0050')
        except RuntimeError:
            slice_thickness = "?"

        if len(px_spacing) >= 2:
            spacing_str = f"({px_spacing[0]}, {px_spacing[1]}, {slice_thickness})"
        else:
            spacing_str = f"({px_spacing[0]}, ?, {slice_thickness})"

        size_str = f"({cols}, {rows}, {z_size})"
        print(f"[DEBUG] DICOM读取成功: {series_dir} → size={size_str}, spacing={spacing_str}")

        return {"image_size": size_str, "image_spacing": spacing_str}
    except Exception as e:
        print(f"[WARN] _get_dicom_image_info 读取失败: {series_dir}")
        print(f"  错误类型: {type(e).__name__}: {e}")
        traceback.print_exc()
        return {"image_size": "N/A", "image_spacing": "N/A"}


def _format_dicom_date(date_str: str) -> str:
    """将DICOM日期格式(YYYYMMDD)转换为YYYY-MM-DD显示格式"""
    if not date_str or date_str == "Unknown":
        return ""
    date_str = date_str.strip()
    if len(date_str) == 8 and date_str.isdigit():
        return f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
    return date_str


def _get_nifti_image_info(nifti_path: str) -> dict:
    """
    读取NIfTI文件的图像尺寸和体素间距信息。

    直接解析NIfTI文件头（348字节），避免SimpleITK在Windows上对
    含中文/Unicode路径的文件读取失败的问题。

    支持 .nii 和 .nii.gz 两种格式。

    NIfTI-1 文件头结构（关键字段）：
    - 偏移   0: sizeof_hdr (int32)
    - 偏移  40: dim[8] (int16 × 8) → dim[1]=x, dim[2]=y, dim[3]=z
    - 偏移  76: pixdim[8] (float32 × 8) → pixdim[1]=sx, pixdim[2]=sy, pixdim[3]=sz

    参数:
        nifti_path: NIfTI文件路径

    返回:
        {"image_size": "(x, y, z)", "image_spacing": "(sx, sy, sz)"}
    """
    try:
        # 打开文件（支持 gzip 压缩）
        if nifti_path.endswith('.gz'):
            with gzip.open(nifti_path, 'rb') as f:
                header_bytes = f.read(348)
        else:
            with open(nifti_path, 'rb') as f:
                header_bytes = f.read(348)

        if len(header_bytes) < 348:
            return {"image_size": "N/A", "image_spacing": "N/A"}

        # 检测字节序：sizeof_hdr 应为 348
        sizeof_hdr = struct.unpack_from('<i', header_bytes, 0)[0]
        endian = '<'
        if sizeof_hdr != 348:
            sizeof_hdr = struct.unpack_from('>i', header_bytes, 0)[0]
            if sizeof_hdr == 348:
                endian = '>'
            else:
                return {"image_size": "N/A", "image_spacing": "N/A"}

        # 解析维度 dim[8]（偏移40，int16 × 8）
        dims = struct.unpack_from(f'{endian}8h', header_bytes, 40)
        ndim = dims[0]
        if ndim >= 3:
            sx, sy, sz = dims[1], dims[2], dims[3]
        elif ndim == 2:
            sx, sy, sz = dims[1], dims[2], 1
        elif ndim == 1:
            sx, sy, sz = dims[1], 1, 1
        else:
            return {"image_size": "N/A", "image_spacing": "N/A"}

        # 解析体素间距 pixdim[8]（偏移76，float32 × 8）
        pixdims = struct.unpack_from(f'{endian}8f', header_bytes, 76)
        if ndim >= 3:
            spx, spy, spz = pixdims[1], pixdims[2], pixdims[3]
        elif ndim == 2:
            spx, spy, spz = pixdims[1], pixdims[2], 1.0
        else:
            spx, spy, spz = pixdims[1], 1.0, 1.0

        size_str = f"({sx}, {sy}, {sz})"
        spacing_str = f"({spx:.4f}, {spy:.4f}, {spz:.4f})"
        print(f"[DEBUG] NIfTI读取成功: {os.path.basename(str(nifti_path))} → size={size_str}, spacing={spacing_str}")
        return {"image_size": size_str, "image_spacing": spacing_str}

    except Exception as e:
        print(f"[WARN] _get_nifti_image_info 解析失败: {nifti_path}")
        print(f"  错误类型: {type(e).__name__}: {e}")
        traceback.print_exc()
        return {"image_size": "N/A", "image_spacing": "N/A"}


def _find_dicom_series(root_dir: str, max_depth: int = 4) -> list:
    """
    递归查找目录树下所有DICOM序列目录。

    搜索策略：
    - 从root_dir开始深度优先搜索
    - 一旦某个目录被确认为DICOM序列目录（包含≥1个DICOM文件），
      则停止向该目录的更深层搜索
    - 最大递归深度为max_depth（默认4层）

    参数:
        root_dir: 搜索根目录
        max_depth: 最大递归深度

    返回:
        [(目录路径, DICOM文件数量), ...] 列表
    """
    if not os.path.isdir(root_dir):
        return []

    series_dirs = []

    def _scan(current_dir: str, depth: int):
        if depth > max_depth:
            return
        # 先检查当前目录本身是否为DICOM序列
        file_count = _count_dicom_files(current_dir)
        if file_count >= 1:
            series_dirs.append((current_dir, file_count))
            return  # 找到序列后不再深入
        # 否则递归检查子目录
        try:
            for item in sorted(os.listdir(current_dir)):
                item_path = os.path.join(current_dir, item)
                if os.path.isdir(item_path):
                    _scan(item_path, depth + 1)
        except PermissionError:
            pass

    _scan(root_dir, 0)
    return series_dirs


def scan_dicom_input(input_dir: str) -> list:
    """
    扫描目录，递归识别其中的DICOM序列。
    每个DICOM序列对应一个患者。

    支持以下目录结构：
    - 直接选择DICOM序列目录（包含.dcm等文件）
    - 选择包含多个序列子文件夹的父目录
    - 嵌套结构（如 patient/series/ 或 study/patient/series/）

    参数:
        input_dir: DICOM数据目录（可以是单个序列或包含多个序列的父目录）

    返回:
        患者信息列表
    """
    patients = []
    if not os.path.isdir(input_dir):
        return patients

    series_list = _find_dicom_series(input_dir)

    for series_dir, file_count in series_list:
        # 生成唯一患者ID：使用相对于input_dir的路径
        if series_dir == input_dir:
            item = os.path.basename(input_dir) or "DICOM"
        else:
            rel_path = os.path.relpath(series_dir, input_dir)
            item = rel_path.replace(os.sep, '_').replace(' ', '_')

        # 原始名称：DICOM序列文件夹名
        original_name = os.path.basename(series_dir)

        # 读取DICOM图像尺寸和间距信息
        image_info = _get_dicom_image_info(series_dir)

        # 尝试读取DICOM元数据
        try:
            metadata = ImageInfo.get_dicom_metadata(series_dir)
            raw_date = metadata.get("series_date", "Unknown")
            patients.append({
                "patient_id": metadata.get("patient_id", item).strip(),
                "patient_name": metadata.get("patient_name", "Unknown").strip(),
                "series_date": _format_dicom_date(raw_date),
                "input_path": series_dir,
                "file_count": file_count,
                "image_size": image_info["image_size"],
                "image_spacing": image_info["image_spacing"],
                "original_name": original_name.strip(),
            })
        except Exception:
            patients.append({
                "patient_id": item.strip(),
                "patient_name": "Unknown",
                "series_date": "",
                "input_path": series_dir,
                "file_count": file_count,
                "image_size": image_info["image_size"],
                "image_spacing": image_info["image_spacing"],
                "original_name": original_name.strip(),
            })

    return patients


def scan_nifti_input(input_dir: str) -> list:
    """
    扫描目录，递归识别其中的NIfTI文件。
    每个.nii.gz或.nii文件对应一个患者。

    参数:
        input_dir: 包含NIfTI文件的目录

    返回:
        患者信息列表
    """
    patients = []
    if not os.path.isdir(input_dir):
        return patients

    # 递归搜索所有.nii.gz和.nii文件
    nii_files = sorted(glob.glob(os.path.join(input_dir, "**", "*.nii.gz"), recursive=True))
    nii_files += sorted(glob.glob(os.path.join(input_dir, "**", "*.nii"), recursive=True))

    # 去重（同名的.nii.gz和.nii只保留一个，优先.nii.gz）
    seen_ids = set()
    for nii_path in nii_files:
        filename = os.path.basename(nii_path)
        # 提取患者ID（去掉扩展名）
        for ext in ['.nii.gz', '.nii']:
            if filename.endswith(ext):
                patient_id = filename[:-len(ext)]
                break
        else:
            patient_id = filename

        patient_id = patient_id.strip()
        if patient_id in seen_ids:
            continue
        seen_ids.add(patient_id)

        # 读取NIfTI图像尺寸和间距信息（仅读文件头）
        image_info = _get_nifti_image_info(nii_path)

        patients.append({
            "patient_id": patient_id,
            "input_path": nii_path,
            "file_size": os.path.getsize(nii_path),
            "image_size": image_info["image_size"],
            "image_spacing": image_info["image_spacing"],
            "original_name": patient_id,  # NIfTI的原始名即文件名（不含后缀）
        })

    return patients
