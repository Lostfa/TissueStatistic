"""
结果合并包装器
提供CSV数据扫描和合并功能。
包含：
- scan_csv_files: 扫描 tissue_statistic/ 目录中的CSV文件
- generate_merged_csv: 根据选择生成合并后的CSV表格

所有函数参数化，不修改原有代码。
"""
import os
import sys
import glob
from pathlib import Path
from typing import Optional, List

# 确保 pipline/ 在搜索路径中
PIPLINE_DIR = Path(__file__).parent.parent.parent / "pipline"
if str(PIPLINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPLINE_DIR))

import pandas as pd


def scan_csv_files(base_path: str) -> dict:
    """
    扫描 tissue_statistic/ 目录，识别所有可用的CSV结果文件，
    并分析文件中包含的椎体、范围和全图分析类型。

    CSV文件命名规则：{患者ID}_{椎体标识}_{范围}mm.csv
    - 全图分析: {患者ID}_ALL_{范围}mm.csv
    - 单椎体分析: {患者ID}_{椎体}_{范围}mm.csv

    参数:
        base_path: 数据根目录

    返回:
        {
            patients: [{id, csv_files}],
            total: 患者数量,
            total_csv_files: CSV文件总数,
            has_all: 是否包含全图分析,
            available_vertebrae: 可用的椎体列表,
            available_ranges: 可用的范围列表（mm）,
        }
    """
    stat_dir = os.path.join(base_path, "tissue_statistic")
    if not os.path.isdir(stat_dir):
        return {
            "patients": [], "total": 0, "total_csv_files": 0,
            "has_all": False, "available_vertebrae": [], "available_ranges": [],
        }

    patients = {}
    all_vertebrae = set()
    all_ranges = set()
    has_all = False
    total_csv = 0

    for patient_dir in sorted(glob.glob(os.path.join(stat_dir, "*"))):
        if not os.path.isdir(patient_dir):
            continue
        pid = os.path.basename(patient_dir)
        csv_files = sorted(glob.glob(os.path.join(patient_dir, "*.csv")))
        total_csv += len(csv_files)
        file_list = []
        for cf in csv_files:
            fname = os.path.basename(cf)
            file_list.append(fname)
            # 解析文件名: {pid}_{标识}_{范围}mm.csv
            name_no_ext = fname.replace(".csv", "")
            # 去掉患者ID前缀
            rest = name_no_ext[len(pid) + 1:]  # +1 跳过下划线
            # 提取范围和标识
            if rest.endswith("mm"):
                rest = rest[:-2]  # 去掉 "mm"
            parts = rest.rsplit("_", 1)  # 从右侧分割一次: ["标识", "范围"]
            if len(parts) == 2:
                identifier, range_str = parts
                try:
                    range_val = int(range_str)
                except ValueError:
                    continue
                if identifier == "ALL":
                    has_all = True
                    # ALL 的范围是全图深度，不加入单椎体范围列表
                else:
                    all_vertebrae.add(identifier)
                    # 仅收集单椎体分析的范围（≤30mm）
                    if range_val <= 30:
                        all_ranges.add(range_val)

        patients[pid] = file_list

    # 按解剖顺序排列椎体（C2→C7, T1→T12, L1→L5）
    def vertebra_sort_key(v):
        letter = v[0]
        num = int(v[1:])
        order = {'C': 0, 'T': 1, 'L': 2}
        return (order.get(letter, 9), num)

    return {
        "patients": [
            {"id": pid, "csv_files": files}
            for pid, files in sorted(patients.items())
        ],
        "total": len(patients),
        "total_csv_files": total_csv,
        "has_all": has_all,
        "available_vertebrae": sorted(all_vertebrae, key=vertebra_sort_key),
        "available_ranges": sorted(all_ranges),
    }


def generate_merged_csv(
    task_obj,
    base_path: str,
    include_all: bool,
    single_vertebrae: List[str],
    ranges: List[int],
    vertebra_pairs: List[str],
    tissues: List[str],
    metrics: List[str],
    patient_ids: Optional[List[str]] = None,
) -> str:
    """
    生成合并后的CSV数据（服务端实现，对应 tissue_statistic.html 的功能）。

    参数:
        task_obj: 任务对象
        base_path: 数据根目录
        include_all: 是否包含全图分析
        single_vertebrae: 选中的目标椎体列表
        ranges: 选中的分析范围
        vertebra_pairs: 已废弃（保留兼容性，不再使用）
        tissues: 选中的组织类型
        metrics: 选中的统计指标
        patient_ids: 指定患者（默认全部）

    返回:
        CSV格式的字符串内容
    """
    stat_dir = os.path.join(base_path, "tissue_statistic")
    if not os.path.isdir(stat_dir):
        return ""

    # 获取患者目录
    all_dirs = sorted(glob.glob(os.path.join(stat_dir, "*")))
    patient_dirs = []
    for d in all_dirs:
        if os.path.isdir(d):
            pid = os.path.basename(d)
            if patient_ids is None or pid in patient_ids:
                patient_dirs.append((pid, d))

    # 构建列名
    columns = []
    scan_types_config = []

    if include_all:
        scan_types_config.append({"type": "ALL"})

    for vert in single_vertebrae:
        for r in ranges:
            scan_types_config.append({"type": "single", "vertebra": vert, "range": r})

    for pair in vertebra_pairs:
        parts = pair.split("-")
        if len(parts) == 2:
            scan_types_config.append({"type": "pair", "start": parts[0], "end": parts[1]})

    for st in scan_types_config:
        for tissue in tissues:
            for metric in metrics:
                if st["type"] == "ALL":
                    col_name = f"ALL_{tissue}_{metric}"
                elif st["type"] == "single":
                    col_name = f"{st['vertebra']}_{st['range']}mm_{tissue}_{metric}"
                else:
                    col_name = f"{st['start']}-{st['end']}_{tissue}_{metric}"
                columns.append(col_name)

    # 处理每位患者
    result_rows = []
    task_obj.total_work = len(patient_dirs)

    for idx, (pid, pdir) in enumerate(patient_dirs):
        if task_obj.is_cancelled:
            break

        row = {"PatientID": pid}
        csv_files = {os.path.basename(f): f for f in glob.glob(os.path.join(pdir, "*.csv"))}

        for st in scan_types_config:
            # 查找匹配的CSV文件
            matching_file = None
            if st["type"] == "ALL":
                pattern = f"{pid}_ALL_"
            elif st["type"] == "single":
                pattern = f"{pid}_{st['vertebra']}_{st['range']}mm"
            else:
                pattern = f"{pid}_{st['start']}-{st['end']}_"

            for fname, fpath in csv_files.items():
                if pattern in fname:
                    matching_file = fpath
                    break

            if matching_file:
                try:
                    df = pd.read_csv(matching_file, index_col=0)
                    for tissue in tissues:
                        for metric in metrics:
                            if st["type"] == "ALL":
                                col_name = f"ALL_{tissue}_{metric}"
                            elif st["type"] == "single":
                                col_name = f"{st['vertebra']}_{st['range']}mm_{tissue}_{metric}"
                            else:
                                col_name = f"{st['start']}-{st['end']}_{tissue}_{metric}"

                            if tissue in df.columns and metric in df.index:
                                val = df.loc[metric, tissue]
                                row[col_name] = "" if pd.isna(val) else str(val)
                            else:
                                row[col_name] = ""
                except Exception:
                    # 文件读取失败，填充空值
                    pass

        # 填充缺失的列
        for col in columns:
            if col not in row:
                row[col] = ""

        result_rows.append(row)
        task_obj.advance(1, f"({idx + 1}/{len(patient_dirs)}) 处理: {pid}")

    # 生成CSV
    if not result_rows:
        return ""

    result_df = pd.DataFrame(result_rows)
    # 确保列顺序
    ordered_cols = ["PatientID"] + [c for c in columns if c != "PatientID"]
    result_df = result_df[ordered_cols]

    csv_content = result_df.to_csv(index=False, encoding="utf-8-sig")
    task_obj.result = {
        "total_patients": len(result_rows),
        "total_columns": len(columns),
        "csv_content": csv_content,
    }

    return csv_content
