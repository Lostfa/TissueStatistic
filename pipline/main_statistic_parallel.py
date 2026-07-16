"""
main_statistic.py 的并行版本。
使用 ProcessPoolExecutor 多进程同时处理多个患者，大幅提升运行速度。
每个患者的数据只加载一次，在内存中完成全部78项分析，避免重复I/O和内存浪费。
"""

import glob
import os
import argparse
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed

from statistic.tissue_statistic import (
    load_image_files,
    extract_all_region,
    extract_vertebra_region,
    calculate_tissue_statistics,
    get_vertebra_center_coordinates,
    save_results_to_csv,
)

# 椎体标签映射字典
VERTEBRA_LABEL = {
    'L5': 18, 'L4': 19, 'L3': 20, 'L2': 21, 'L1': 22,
    'T12': 23, 'T11': 24, 'T10': 25, 'T9': 26, 'T8': 27,
    'T7': 28, 'T6': 29, 'T5': 30, 'T4': 31, 'T3': 32,
    'T2': 33, 'T1': 34, 'C7': 35, 'C6': 36, 'C5': 37,
    'C4': 38, 'C3': 39, 'C2': 40
}

VERTEBRA_LIST = [k for k in VERTEBRA_LABEL.keys()]
RANGE_LIST = [1, 5, 10, 20]


def _process_single_patient(args):
    """处理单个患者的所有分析任务（模块级函数，供多进程 pickle 序列化使用）

    关键优化：数据文件只加载一次，所有分析共用内存中的数组，
    避免原来每项分析都重复加载4个NIfTI文件（78次→1次）。
    """
    base_path, patient_path = args
    filename = os.path.basename(patient_path)
    patient_id = filename[:-7]  # 去掉末尾的 ".nii.gz"（7个字符）得到患者ID
    messages = []

    # ---- 第一步：加载数据（仅一次）----
    try:
        ct_array, bca_array, total_array, tissues_array, voxel_volume, z_ratio = \
            load_image_files(base_path, patient_id)
    except Exception as e:
        return patient_id, [f"[异常] {patient_id}: 数据加载失败 —— {e}"]

    # ---- 第二步：逐项分析（共用已加载数据）----

    # 辅助函数：保存结果并记录消息
    def _save_csv(label, stats_df, range_val):
        if not stats_df.empty:
            save_results_to_csv(stats_df, base_path=base_path, patient_id=patient_id,
                                vertebra_name=label, analysis_range=range_val)
            return f"[成功] {patient_id}: {label}"
        else:
            return f"[失败] {patient_id}: {label} —— 未生成结果"

    try:
        # 1）分析所有层面
        tissue_region = extract_all_region(tissues_array)
        analysis_range = tissue_region.shape[0]
        stats_df = calculate_tissue_statistics(ct_array, tissue_region, voxel_volume)
        messages.append(_save_csv('ALL', stats_df, analysis_range))
    except Exception as e:
        messages.append(f"[异常] {patient_id}: ALL —— {e}")

    # 2）分析单个椎体 × 指定范围
    for vertebra in VERTEBRA_LIST:
        for r in RANGE_LIST:
            label = f"{vertebra}"
            try:
                center = get_vertebra_center_coordinates(bca_array, total_array, vertebra)
                if center is None:
                    messages.append(f"[失败] {patient_id}: {label} —— 未找到椎体中心")
                    continue
                center_slice = np.zeros_like(total_array)
                center_slice[center[0], :, :] = 1
                tissue_region, range_val = extract_vertebra_region(center_slice, tissues_array, r)
                if tissue_region is None:
                    messages.append(f"[失败] {patient_id}: {label} —— 无法提取组织区域")
                    continue
                stats_df = calculate_tissue_statistics(ct_array, tissue_region, voxel_volume)
                messages.append(_save_csv(label, stats_df, range_val))
            except Exception as e:
                messages.append(f"[异常] {patient_id}: {label} —— {e}")

    return patient_id, messages


def main():
    parser = argparse.ArgumentParser(description='组织统计并行分析（多进程）')
    parser.add_argument('--workers', '-w', type=int, default=20,
                        help='并行工作进程数（默认：CPU核心数）')
    parser.add_argument('--base-path', '-b', type=str, default='d:/acrin_nsclc',
                        help='数据根目录（默认：d:/acrin_nsclc）')

    args = parser.parse_args()

    base_path = args.base_path
    patient_path_list = glob.glob(f"{base_path}/ct_image/*")

    num_patients = len(patient_path_list)
    tasks_per_patient = 1 + len(VERTEBRA_LIST) * len(RANGE_LIST)
    total_tasks = num_patients * tasks_per_patient

    print(f"患者数量：{num_patients}")
    print(f"每例患者分析任务数：{tasks_per_patient}")
    print(f"总任务数：{total_tasks}")
    print(f"并行进程数：{args.workers}")
    print("=" * 60)

    task_args = [(base_path, p) for p in patient_path_list]
    completed_patients = 0
    completed_tasks = 0

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(_process_single_patient, ta): ta for ta in task_args}
        for future in as_completed(futures):
            completed_patients += 1
            patient_id, messages = future.result()
            for msg in messages:
                completed_tasks += 1
                print(f"[{completed_tasks}/{total_tasks}] {msg}")
            print(f"--- 患者进度：{completed_patients}/{num_patients} ---")

    print("=" * 60)
    print("全部分析完成！")


if __name__ == '__main__':
    main()
