import os
import numpy as np
import pandas as pd
import SimpleITK as sitk
from typing import Optional, Tuple
import warnings

# 组织标签映射字典
TISSUE_LABEL = {'MUSCLE': 1, 'BONE': 2, 'SAT': 3, 'VAT': 4, 'IMAT': 5, 'PAT': 6, 'EAT': 7}
LABEL_TISSUE = {v: k for k, v in TISSUE_LABEL.items()}  # 反向映射

# 椎体标签映射字典
VERTEBRA_LABEL = {
    'L5': 18, 'L4': 19, 'L3': 20, 'L2': 21, 'L1': 22,
    'T12': 23, 'T11': 24, 'T10': 25, 'T9': 26, 'T8': 27,
    'T7': 28, 'T6': 29, 'T5': 30, 'T4': 31, 'T3': 32,
    'T2': 33, 'T1': 34, 'C7': 35, 'C6': 36, 'C5': 37,
    'C4': 38, 'C3': 39, 'C2': 40
}
LABEL_VERTEBRA = {v: k for k, v in VERTEBRA_LABEL.items()}  # 反向映射

# 统计指标名称
STAT_NAMES = ['volume', 'max-hu', 'min-hu', 'mean-hu',
              'std-hu', 'median-hu', 'q1-hu', 'q3-hu']


def remove_extra_vertebra_parts(bca_array: np.ndarray, total_array: np.ndarray) -> np.ndarray:
    """
    使用BCA标签去除椎体多余部分
    参数:
        bca_array: BCA标签的三维数组
        total_array: 椎体标签的三维数组
    返回:
        清理后的椎体标签数组
    """
    # 创建副本以避免修改原始数据
    cleaned_array = total_array.copy()
    depth, height, width = bca_array.shape

    # 使用向量化操作替换循环以提高性能
    for i in range(depth):
        for j in range(width):
            column = bca_array[i, :, j]
            positions = np.where(column == 11)[0]
            if positions.size > 0:
                min_pos = positions.min()
                # 将最小位置以下的所有元素置零
                cleaned_array[i, min_pos:, j] = 0

    return cleaned_array


def get_vertebra_center_coordinates(bca_array: np.ndarray, total_array: np.ndarray,
                                    vertebra_name: str) -> Optional[Tuple[int, int, int]]:
    """
    获取指定椎体的三维空间中心点坐标
    参数:
        bca_array: BCA标签的三维数组
        total_array: 椎体标签的三维数组
        vertebra_name: 椎体名称（如'T10'）
    返回:
        包含三个整数的元组 (z, y, x)，分别表示椎体在三个方向上的中心坐标
        如果椎体不存在则返回None
    """
    # 清理椎体数据
    cleaned_total_array = remove_extra_vertebra_parts(bca_array, total_array)

    # 检查椎体是否存在
    if vertebra_name not in VERTEBRA_LABEL:
        warnings.warn(f"未知的椎体名称: {vertebra_name}")
        return None

    label_value = VERTEBRA_LABEL[vertebra_name]

    # 创建椎体的01掩码
    vertebra_mask = np.array(cleaned_total_array == label_value, dtype=bool)

    if vertebra_mask.sum() == 0:
        warnings.warn(f"椎体 {vertebra_name} 在图像中未找到")
        return None

    # 获取所有非零元素的坐标
    z_coords, y_coords, x_coords = np.where(vertebra_mask)

    # 方法1：使用边界框中心
    # center_z = (z_coords.min() + z_coords.max()) // 2
    # center_y = (y_coords.min() + y_coords.max()) // 2
    # center_x = (x_coords.min() + x_coords.max()) // 2

    # 方法2：使用质心（体积中心） - 如果需要更精确的中心
    center_z = int(np.mean(z_coords))
    center_y = int(np.mean(y_coords))
    center_x = int(np.mean(x_coords))

    return (center_z, center_y, center_x)


def extract_all_region(tissues_array: np.ndarray):
    """
    提取所有层面的组织区域

    参数:
        tissues_array: 组织标签的三维数组

    返回:
        提取的组织区域
    """

    return tissues_array


def extract_vertebra_region(center_slice: np.ndarray, tissues_array: np.ndarray, specified_range: int):
    """
    提取以椎体中心层面为中心指定范围的组织区域

    参数:
        center_slice: 椎体中心层面掩码
        tissues_array: 组织标签的三维数组
        specified_range: 指定的分析范围

    返回:
        提取的组织区域，如果范围超出图像边界则返回None
    """

    depth, height, width = tissues_array.shape

    # 找到中心层位置
    center_z = np.where(center_slice == 1)[0]
    if center_z.size == 0:
        return None, None

    center_z = center_z[0]
    half_range = specified_range // 2

    # 计算提取范围的起始和结束位置
    if specified_range % 2 == 0:
        # 偶数范围：中心层两边各取一半
        start_z = center_z - half_range
        end_z = center_z + half_range
    else:
        # 奇数范围：包括中心层，两边各取一半
        start_z = center_z - half_range
        end_z = center_z + half_range + 1
    print(f"--分析层面为 {start_z}-{end_z}，分析范围为{specified_range}mm")

    # 边界检查
    if start_z < 0 or end_z > depth:
        warnings.warn(f"提取范围超出图像边界: start_z={start_z}, end_z={end_z}, depth={depth}")
        return None, None

    # 创建范围掩码
    region_mask = np.zeros_like(tissues_array, dtype=np.uint8)
    region_mask[start_z:end_z, :, :] = 1

    # 提取组织区域
    extracted_region = tissues_array * region_mask

    return extracted_region, specified_range


def extract_vertebra_range(center_slice_start: np.ndarray, center_slice_end: np.ndarray, tissues_array: np.ndarray):
    """
    提取以两个指定椎体中心层面为中心的范围的组织区域，如T1~T12

    参数:
        center_slice_start: 起始椎体中心层面掩码
        center_slice_end: 结束椎体中心层面掩码
        tissues_array: 组织标签的三维数组

    返回:
        提取的组织区域，如果选取的椎体不存在则返回None
    """
    if center_slice_start is None or center_slice_end is None:
        return None, None

    depth, height, width = tissues_array.shape

    # 找到中心层位置
    center_z_start = np.where(center_slice_start == 1)[0]
    center_z_end = np.where(center_slice_end == 1)[0]

    center_z_start = int(center_z_start[0])
    center_z_end = int(center_z_end[0])

    # 计算提取范围的起始和结束位置
    start_z = min(center_z_start, center_z_end)
    end_z = max(center_z_start, center_z_end) + 1
    vertebra_range = end_z - start_z
    print(f"--分析层面为 {start_z}-{end_z}，分析范围为{vertebra_range}mm")

    # 边界检查
    if start_z < 0 or end_z > depth:
        warnings.warn(f"提取范围超出图像边界: start_z={start_z}, end_z={end_z}, depth={depth}")
        return None, None

    # 创建范围掩码
    region_mask = np.zeros_like(tissues_array, dtype=np.uint8)
    region_mask[start_z:end_z, :, :] = 1

    # 提取组织区域
    extracted_region = tissues_array * region_mask

    return extracted_region, vertebra_range


def calculate_tissue_statistics(ct_array: np.ndarray, tissue_region: np.ndarray, voxel_volume: float) -> pd.DataFrame:
    """
    计算指定区域内各种组织的统计信息
    参数:
        ct_array: CT图像的三维数组（HU值）
        tissue_region: 组织标签的三维数组
        voxel_volume: 单个体素的体积（立方毫米）
    返回:
        包含各种组织统计信息的DataFrame
    """
    if tissue_region is None:
        return pd.DataFrame()

    # 初始化结果DataFrame
    results = pd.DataFrame(index=STAT_NAMES)

    for tissue_name, label_value in TISSUE_LABEL.items():
        # 创建当前组织的01掩码
        tissue_mask = np.array(tissue_region == label_value, dtype=bool)

        # 计算组织体积
        voxel_count = tissue_mask.sum()
        volume = int(voxel_count * voxel_volume)

        # 如果没有该组织，填充NaN
        if voxel_count == 0:
            results[tissue_name] = [volume] + [np.nan] * (len(STAT_NAMES) - 1)
            continue

        # 提取组织的CT值
        tissue_hu_values = ct_array[tissue_mask]

        # 计算统计量
        stats = [
            volume,
            int(np.max(tissue_hu_values)),
            int(np.min(tissue_hu_values)),
            int(np.mean(tissue_hu_values)),
            int(np.std(tissue_hu_values)),
            int(np.median(tissue_hu_values)),
            int(np.percentile(tissue_hu_values, 25)),
            int(np.percentile(tissue_hu_values, 75))
        ]

        results[tissue_name] = stats

    return results


def load_image_files(base_path: str, patient_id: str):
    """
    加载所有需要的图像文件
    参数:
        base_path: 数据根目录
        patient_id: 患者ID
    返回:
        (ct_array, bca_array, total_array, tissues_array, voxel_volume)
    """
    # 构建文件路径
    ct_path = f"{base_path}/ct_image/{patient_id}.nii.gz"
    bca_path = f"{base_path}/boa_label/{patient_id}/bca.nii.gz"
    total_path = f"{base_path}/boa_label/{patient_id}/total.nii.gz"
    tissues_path = f"{base_path}/boa_label/{patient_id}/tissues.nii.gz"

    # 加载CT图像
    ct_image = sitk.ReadImage(ct_path)
    spacing = ct_image.GetSpacing()
    voxel_volume = spacing[0] * spacing[1] * spacing[2]
    z_ratio = spacing[2] / spacing[1]
    ct_array = sitk.GetArrayFromImage(ct_image)

    # 加载标签图像
    bca_array = sitk.GetArrayFromImage(sitk.ReadImage(bca_path))
    total_array = sitk.GetArrayFromImage(sitk.ReadImage(total_path))
    tissues_array = sitk.GetArrayFromImage(sitk.ReadImage(tissues_path))

    return ct_array, bca_array, total_array, tissues_array, voxel_volume, z_ratio


def process_vertebra_analysis(base_path: str, patient_id: str, vertebra_name_start=None, vertebra_name_end=None, analysis_range=None):
    """
    处理单个椎体的完整分析流程
    参数:
        patient_id: 患者ID
        vertebra_name_start: 起始椎体名称
        vertebra_name_end: 结束椎体名称
    返回:
        包含组织统计信息的DataFrame
    """

    # 加载数据
    ct_array, bca_array, total_array, tissues_array, voxel_volume, z_ratio = load_image_files(base_path, patient_id)

    if vertebra_name_start is None: # 未指定起始椎体，则分析整个图像
        # 提取组织区域
        tissue_region = extract_all_region(tissues_array)
        # 获取整个图像的范围，即数组的第一个维度大小
        analysis_range = tissue_region.shape[0]
        # 计算统计信息
        stats_df = calculate_tissue_statistics(ct_array, tissue_region, voxel_volume)

        return stats_df, analysis_range

    elif vertebra_name_end is None: # 未指定结束椎体，则以单个椎体为中心分析
        # 获取椎体中心点坐标
        center_coordinates = get_vertebra_center_coordinates(bca_array, total_array, vertebra_name_start)

        if center_coordinates is None:
            return pd.DataFrame(), None
        # 获取椎体在z轴方向上的中心层面切片（mask）
        center_slice = np.zeros_like(total_array)
        center_slice[center_coordinates[0], :, :] = 1

        if center_slice is None:
            print(f"--无法找到椎体 {vertebra_name_start} 的中心层面")
            return pd.DataFrame(), None

        # 提取组织区域
        tissue_region, analysis_range = extract_vertebra_region(center_slice, tissues_array, analysis_range)

        if tissue_region is None:
            print(f"--无法提取椎体 {vertebra_name_start} 的组织区域")
            return pd.DataFrame(), None

        # 计算统计信息
        stats_df = calculate_tissue_statistics(ct_array, tissue_region, voxel_volume)

        return stats_df, analysis_range

    else: # 分析指定的两个椎体之间的范围
        # 获取椎体中心点坐标
        center_coordinates_start = get_vertebra_center_coordinates(bca_array, total_array, vertebra_name_start)
        center_coordinates_end = get_vertebra_center_coordinates(bca_array, total_array, vertebra_name_end)
        if center_coordinates_start is None or center_coordinates_end is None:
            return pd.DataFrame(), None

        # 获取椎体在z轴方向上的中心层面切片（mask）
        center_slice_start, center_slice_end = np.zeros_like(total_array), np.zeros_like(total_array)
        center_slice_start[center_coordinates_start[0], :, :] = 1
        center_slice_end[center_coordinates_end[0], :, :] = 1

        if center_slice_start is None or center_slice_end is None:
            print(f"--无法找到椎体 “{vertebra_name_start}” 或椎体 “{vertebra_name_end}” 的中心层面")
            return pd.DataFrame(), None

        # 提取组织区域
        tissue_range, analysis_range = extract_vertebra_range(center_slice_start, center_slice_end, tissues_array)

        if tissue_range is None:
            print(f"--无法提取椎体 “{vertebra_name_start}” 到椎体 “{vertebra_name_end}” 的组织区域")
            return pd.DataFrame(), None

        # 计算统计信息
        stats_df = calculate_tissue_statistics(ct_array, tissue_range, voxel_volume)

        return stats_df, analysis_range


def save_results_to_csv(results_df: pd.DataFrame, base_path: str, patient_id: str, vertebra_name: str, analysis_range: int) -> None:
    """
    保存结果到CSV文件
    参数:
        results_df: 结果DataFrame
        patient_id: 患者ID
        vertebra_name: 椎体名称
        analysis_range: 分析范围
    """
    if results_df.empty:
        print("没有数据可保存")
        return

    output_dir = f"{base_path}/tissue_statistic/{patient_id}"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_path = f"{output_dir}/{patient_id}_{vertebra_name}_{analysis_range}mm.csv"
    results_df.to_csv(output_path, index=True)
    print(f"--结果已保存到: {output_path}")


if __name__ == "__main__":
    # 配置参数
    BASE_PATH = "d:/lyx/before_treatment"
    PATIENT_ID = "179792-0002"
    VERTEBRA_NAME_START = "T1"
    VERTEBRA_NAME_END = "T12"
    RANGE_MM = 10

    # 执行单个椎体分析
    print(f"开始分析ID号为 {PATIENT_ID} 患者的 {VERTEBRA_NAME_START} 椎体层面组织信息...")
    df_results, range_mm = process_vertebra_analysis(
        base_path = BASE_PATH, patient_id=PATIENT_ID, vertebra_name_start=VERTEBRA_NAME_START, vertebra_name_end=None, analysis_range=RANGE_MM)

    # 保存结果
    if not df_results.empty:
        save_results_to_csv(df_results, base_path=BASE_PATH, patient_id=PATIENT_ID, vertebra_name=VERTEBRA_NAME_START, analysis_range=range_mm)
    else:
        print("--分析失败，未生成结果")


    # 执行椎体间范围分析
    print(f"开始分析ID号为 {PATIENT_ID} 患者的 {VERTEBRA_NAME_START} 椎体到 {VERTEBRA_NAME_END} 椎体层面组织信息...")
    df_results, range_mm = process_vertebra_analysis(
        base_path = BASE_PATH, patient_id=PATIENT_ID, vertebra_name_start=VERTEBRA_NAME_START, vertebra_name_end=VERTEBRA_NAME_END, analysis_range=None)

    # 保存结果
    if not df_results.empty:
        save_results_to_csv(df_results, base_path=BASE_PATH, patient_id=PATIENT_ID, vertebra_name=f"{VERTEBRA_NAME_START}-{VERTEBRA_NAME_END}", analysis_range=range_mm)
    else:
        print("--分析失败，未生成结果")