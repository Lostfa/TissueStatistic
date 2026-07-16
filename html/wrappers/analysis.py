"""
统计分析包装器
包装 pipline/statistic/ 中的现有统计计算逻辑。
支持模式B（单次检查）：并行处理所有患者的多项分析任务。

所有函数通过 sys.path 导入 tissue_statistic.py 中的现有函数，
保持参数化调用，不修改原有代码。
"""
import os
import sys
import glob
from pathlib import Path
from typing import Optional, List, Tuple

# 确保 pipline/ 在搜索路径中
PIPLINE_DIR = Path(__file__).parent.parent.parent / "pipline"
if str(PIPLINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPLINE_DIR))

import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed

from utils.image_io import ImageIO
from utils.image_process import ImageProcess

from statistic.tissue_statistic import (
    load_image_files,
    extract_all_region,
    extract_vertebra_region,
    calculate_tissue_statistics,
    get_vertebra_center_coordinates,
    save_results_to_csv,
    VERTEBRA_LABEL, TISSUE_LABEL, STAT_NAMES,
)

# 默认椎体列表和范围配置
DEFAULT_VERTEBRA_LIST = list(VERTEBRA_LABEL.keys())
DEFAULT_RANGE_LIST = [1, 5, 10, 20]


def _process_single_patient_modeb(args_tuple: tuple) -> Tuple[str, List[str]]:
    """
    处理单个患者的所有分析任务（模块级函数，供多进程使用）。

    与 main_statistic_parallel.py 中的 _process_single_patient 逻辑一致，
    但接收参数化的椎体列表、范围列表和椎体组合配置。

    参数:
        args_tuple: (base_path, patient_path, vertebrae, ranges, include_all)

    返回:
        (patient_id, messages) 元组
    """
    base_path, patient_path, vertebrae, ranges, include_all = args_tuple
    filename = os.path.basename(patient_path)
    patient_id = filename[:-7]  # 去掉 .nii.gz
    messages = []

    # 加载数据（仅一次）
    try:
        ct_array, bca_array, total_array, tissues_array, voxel_volume, z_ratio = \
            load_image_files(base_path, patient_id)
    except Exception as e:
        return patient_id, [f"[异常] {patient_id}: 数据加载失败 —— {e}"]

    def _save_csv(label, stats_df, range_val):
        if not stats_df.empty:
            save_results_to_csv(stats_df, base_path=base_path, patient_id=patient_id,
                                vertebra_name=label, analysis_range=range_val)
            return f"[成功] {patient_id}: {label}"
        else:
            return f"[失败] {patient_id}: {label} —— 未生成结果"

    # 1) 全图分析
    if include_all:
        try:
            tissue_region = extract_all_region(tissues_array)
            analysis_range_val = tissue_region.shape[0]
            stats_df = calculate_tissue_statistics(ct_array, tissue_region, voxel_volume)
            messages.append(_save_csv('ALL', stats_df, analysis_range_val))
        except Exception as e:
            messages.append(f"[异常] {patient_id}: ALL —— {e}")

    # 2) 单个椎体 × 范围
    for vertebra in vertebrae:
        for r in ranges:
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


def _process_single_tissue_label(args: tuple):
    """
    处理单个CT图像，使用自定义HU阈值生成组织标签（模块级函数，供多进程使用）。

    功能与 pipline/tissue_label_parallel.py:process_single_image 一致，
    但使用传入的自定义 CT 值范围代替 HURange 枚举中的默认值。

    参数:
        args: (image_path, label_path, fat_min, fat_max, muscle_min, muscle_max)

    返回:
        (patient_id, message) 元组
    """
    image_path, label_path, fat_min, fat_max, muscle_min, muscle_max = args
    patient_id = os.path.basename(label_path)

    body_path = os.path.join(label_path, 'body.nii')
    bca_path = os.path.join(label_path, 'bca.nii.gz')
    total_path = os.path.join(label_path, 'total.nii.gz')

    # ---- 读取阶段 ----
    itk_image = ImageIO.nii2itk(image_path)
    spacing = itk_image.GetSpacing()
    origin = itk_image.GetOrigin()
    direction = itk_image.GetDirection()

    np_image = ImageIO.itk2array(itk_image, dtype=np.int16)
    np_bca = ImageIO.nii2array(bca_path, dtype=np.uint8)
    np_total = ImageIO.nii2array(total_path, dtype=np.uint8)
    np_body = ImageIO.nii2array(body_path, dtype=np.uint8)

    # ---- 使用自定义 HU 范围蒙版 ----
    adipose_mask = ((np_image >= fat_min) & (np_image <= fat_max)).astype(np.uint8)
    muscle_mask = ((np_image >= muscle_min) & (np_image <= muscle_max)).astype(np.uint8)

    # ---- 身体与器官蒙版 ----
    np_body = ImageProcess.remove_small_islands(np_body, 100000)
    total_mask = (np_total == 0).astype(np.uint8)

    # ---- 各组织区域提取 ----
    # 骨骼: BCA通道5 → 值2
    np_bone = np.where(np_bca == 5, 2, 0).astype(np.uint8)

    # 皮下脂肪 SAT: BCA通道1 → 值3 × 脂肪HU蒙版
    np_sat = np.where(np_bca == 1, 3, 0).astype(np.uint8)
    np.multiply(np_sat, adipose_mask, out=np_sat)

    # 肌肉: BCA通道2 → 值1 × 肌肉HU蒙版
    np_mix = np.where(np_bca == 2, 1, 0).astype(np.uint8)
    np_muscle = (np_mix * muscle_mask).astype(np.uint8)

    # 肌间脂肪 IMAT: BCA通道2中非肌肉部分 → 值5
    np_imat = np_mix - np_muscle
    np_imat *= 5

    # 纵隔脂肪 PAT: BCA通道9 → 值6 × 脂肪HU蒙版
    np_pat = np.where(np_bca == 9, 6, 0).astype(np.uint8)
    np.multiply(np_pat, adipose_mask, out=np_pat)

    # 心包脂肪 EAT: BCA通道7 → 值7 × 脂肪HU蒙版
    np_eat = np.where(np_bca == 7, 7, 0).astype(np.uint8)
    np.multiply(np_eat, adipose_mask, out=np_eat)

    # 腹腔脂肪 VAT: BCA通道3 → 值4 × 脂肪HU蒙版
    np_vat = np.where(np_bca == 3, 4, 0).astype(np.uint8)
    np.multiply(np_vat, adipose_mask, out=np_vat)

    # ---- 合并组织标签 ----
    np_tissue = np_bone + np_sat
    np_tissue += np_muscle
    np_tissue += np_imat

    np_visceral = np_pat + np_eat
    np_visceral += np_vat
    np.multiply(np_visceral, total_mask, out=np_visceral)

    np_tissue += np_visceral
    np.multiply(np_tissue, np_body, out=np_tissue)

    # ---- 保存 ----
    save_path = os.path.join(label_path, 'tissues.nii.gz')
    ImageIO.array2nii(np_tissue, save_path, spacing, origin, direction)

    return patient_id, f"[成功] {patient_id}: 组织标签已生成"


def run_mode_b_analysis(
    task_obj,
    base_path: str,
    workers: int = 4,
    vertebrae: Optional[List[str]] = None,
    ranges: Optional[List[int]] = None,
    include_all: bool = True,
    custom_thresholds: Optional[dict] = None,
):
    """
    执行模式B（单次检查）的并行统计分析。

    支持可选的两阶段流程：
      Phase 1: 如果 custom_thresholds 启用，先用自定义HU阈值并行生成组织标签
      Phase 2: 执行标准的组织统计分析

    结果保存到 base_path/tissue_statistic/{patient_id}/*.csv

    参数:
        task_obj: 任务对象，用于进度报告
        base_path: 数据根目录
        workers: 并行进程数
        vertebrae: 要分析的椎体列表（默认全部）
        ranges: 分析范围列表（毫米）
        include_all: 是否包含全图分析
        custom_thresholds: 自定义阈值dict，包含 enabled, fat_min, fat_max, muscle_min, muscle_max
    """
    vertebrates = vertebrae or DEFAULT_VERTEBRA_LIST
    rngs = ranges or DEFAULT_RANGE_LIST

    patient_paths = sorted(glob.glob(f"{base_path}/ct_image/*.nii.gz"))
    if not patient_paths:
        task_obj.update(100, "未找到CT图像文件")
        task_obj.result = {"total_patients": 0}
        return

    total_patients = len(patient_paths)
    has_phase1 = custom_thresholds is not None and custom_thresholds.get("enabled", False)

    # 总工作量：Phase 1（若启用） + Phase 2
    task_obj.total_work = total_patients * (2 if has_phase1 else 1)
    task_obj.completed_work = 0

    import multiprocessing
    ctx = multiprocessing.get_context('spawn')

    # ===== Phase 1: 组织标签生成 =====
    if has_phase1:
        fat_min = custom_thresholds.get("fat_min", -190)
        fat_max = custom_thresholds.get("fat_max", -30)
        muscle_min = custom_thresholds.get("muscle_min", -29)
        muscle_max = custom_thresholds.get("muscle_max", 150)

        task_obj.update(0, f"Phase 1/2: 正在生成组织标签 (共 {total_patients} 个序列, {workers} 进程)...")

        phase1_args = []
        for p in patient_paths:
            filename = os.path.basename(p)
            patient_id = filename[:-7]  # 去掉 .nii.gz
            label_path = os.path.join(base_path, 'boa_label', patient_id)
            phase1_args.append((p, label_path, fat_min, fat_max, muscle_min, muscle_max))

        phase1_completed = 0
        phase1_fail = 0

        try:
            with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as executor:
                future_to_patient = {
                    executor.submit(_process_single_tissue_label, args): args[0]
                    for args in phase1_args
                }

                for future in as_completed(future_to_patient):
                    if task_obj.is_cancelled:
                        executor.shutdown(wait=False, cancel_futures=True)
                        return
                    phase1_completed += 1
                    try:
                        pid, msg = future.result()
                        task_obj.log.append(msg)
                    except Exception as e:
                        phase1_fail += 1
                        patient_path = future_to_patient[future]
                        pid = os.path.basename(patient_path)[:-7]
                        task_obj.log.append(f"[失败] {pid}: 组织标签生成失败 —— {e}")
                    task_obj.advance(1,
                        f"Phase 1/2: 组织标签生成 [{phase1_completed}/{total_patients}]"
                        + (f" ({phase1_fail} 失败)" if phase1_fail else "")
                    )
        except Exception as e:
            task_obj.update(task_obj.progress, f"Phase 1 并行处理出错: {e}")
            raise

        if task_obj.is_cancelled:
            return

        task_obj.update(task_obj.progress, "Phase 1/2 完成，开始 Phase 2 统计分析...")

    # ===== Phase 2: 统计分析 =====
    task_obj.update(task_obj.progress,
        f"发现 {total_patients} 个序列，使用 {workers} 个进程并行分析...")

    completed = 0
    success_count = 0
    fail_count = 0

    task_args = [
        (base_path, p, vertebrates, rngs, include_all)
        for p in patient_paths
    ]

    try:
        with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as executor:
            future_to_patient = {
                executor.submit(_process_single_patient_modeb, ta): ta[1]
                for ta in task_args
            }

            for future in as_completed(future_to_patient):
                if task_obj.is_cancelled:
                    executor.shutdown(wait=False, cancel_futures=True)
                    return
                completed += 1
                try:
                    pid, messages = future.result()
                    for msg in messages:
                        task_obj.log.append(msg)
                        if "[成功]" in msg:
                            success_count += 1
                        elif "[失败]" in msg or "[异常]" in msg:
                            fail_count += 1
                    phase_tag = "Phase 2/2: " if has_phase1 else ""
                    task_obj.advance(1,
                        f"{phase_tag}[{completed}/{total_patients}] 序列 {pid} 分析完成"
                        f"（成功{success_count}项）"
                    )
                except Exception as e:
                    task_obj.advance(1,
                        f"[{completed}/{total_patients}] 处理异常: {e}"
                    )
    except Exception as e:
        task_obj.update(task_obj.progress, f"并行处理出错: {e}")
        raise

    task_obj.result = {
        "total_patients": total_patients,
        "success_tasks": success_count,
        "fail_tasks": fail_count,
        "output_dir": f"{base_path}/tissue_statistic",
    }


def scan_analysis_dirs(ct_dir: str, label_dir: str) -> dict:
    """
    扫描图像目录和标签目录，统计序列数量。

    参数:
        ct_dir: ct_image 目录路径（存放 .nii.gz 文件）
        label_dir: boa_label 目录路径（存放患者子文件夹）

    返回:
        {
            ct_count: NIfTI文件数量,
            label_count: 标签子文件夹数量,
            ct_dir: 图像目录路径,
            label_dir: 标签目录路径,
        }
    """
    ct_count = 0
    if os.path.isdir(ct_dir):
        ct_count = len(glob.glob(os.path.join(ct_dir, "*.nii.gz")))

    label_count = 0
    if os.path.isdir(label_dir):
        label_count = len([d for d in glob.glob(os.path.join(label_dir, "*"))
                          if os.path.isdir(d)])

    return {
        "ct_count": ct_count,
        "label_count": label_count,
        "ct_dir": ct_dir,
        "label_dir": label_dir,
    }
