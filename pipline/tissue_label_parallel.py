import os
import sys
import glob
import enum
import numpy as np
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
from utils.image_io import ImageIO
from utils.image_process import ImageProcess


class HURange(enum.Enum):
    ALL = (-1000, 3000)
    ADIPOSE_TISSUE = (-200, 0)   # 脂肪CT值范围
    MUSCLE_TISSUE = (1, 150)    # 肌肉CT值范围

class Tissue(enum.IntEnum):
    MUSCLE = 1  # 肌肉
    BONE = 2    # 骨骼
    SAT = 3     # 皮下脂肪
    VAT = 4     # 腹腔脂肪
    IMAT = 5    # 肌间脂肪
    PAT = 6     # 纵隔脂肪
    EAT = 7     # 心包脂肪


def filter_by_hu_range(array: np.ndarray, hu_range: HURange) -> np.ndarray:
    """HU值范围过滤，返回 uint8 二值蒙版"""
    low, high = hu_range.value
    return ((array >= low) & (array <= high)).astype(np.uint8)


def process_single_image(args: tuple) -> str:
    """
    处理单张 CT 图像，生成组织标签并保存。

    设计为顶层函数以支持 ProcessPoolExecutor 的 pickle 序列化。
    各组织标签值定义见 Tissue 枚举类。

    Parameters
    ----------
    args : tuple
        (image_path, label_path) 元组

    Returns
    -------
    str
        保存路径
    """
    image_path, label_path = args

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

    # ---- 预计算 HU 范围蒙版 ----
    adipose_mask = filter_by_hu_range(np_image, HURange.ADIPOSE_TISSUE)
    muscle_mask = filter_by_hu_range(np_image, HURange.MUSCLE_TISSUE)
    # 注: 原始代码中的 bone_mask 计算后未被使用，此处省略

    # ---- 身体与器官蒙版 ----
    np_body = ImageProcess.remove_small_islands(np_body, 100000)
    total_mask = (np_total == 0).astype(np.uint8)  # 器官区域反选

    # ---- 各组织区域提取 ----
    # 骨骼: BCA通道5 → 值2
    np_bone = np.where(np_bca == 5, 2, 0).astype(np.uint8)

    # 皮下脂肪 SAT: BCA通道1 → 值3 × 脂肪HU蒙版
    np_sat = np.where(np_bca == 1, 3, 0).astype(np.uint8)
    np.multiply(np_sat, adipose_mask, out=np_sat)

    # 肌肉: BCA通道2 → 值1 × 肌肉HU蒙版
    np_mix = np.where(np_bca == 2, 1, 0).astype(np.uint8)
    np_muscle = (np_mix * muscle_mask).astype(np.uint8)  # 肌肉HU范围内的部分

    # 肌间脂肪 IMAT: BCA通道2中非肌肉部分 → 值5
    # 安全: np_muscle 是 np_mix 的子集，减法不会下溢
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
    # 优化: 使用 in-place 加法替代原始代码中的链式 + 运算符
    # 原: (np_bone+np_sat+np_muscle+np_imat) + ((np_pat+np_eat+np_vat)*...)*...
    # 原链式 + 产生约 8 个临时数组，优化后仅 ~2 个

    # 基础组织: 骨骼 + 皮下脂肪 + 肌肉 + 肌间脂肪 (不受器官蒙版约束)
    np_tissue = np_bone + np_sat   # 产生1个临时数组
    np_tissue += np_muscle         # in-place
    np_tissue += np_imat           # in-place

    # 内脏相关脂肪: 纵隔 + 心包 + 腹腔 (受 total_mask 约束)
    np_visceral = np_pat + np_eat  # 产生1个临时数组
    np_visceral += np_vat          # in-place
    np.multiply(np_visceral, total_mask, out=np_visceral)

    # 最终结果：骨骼 + 皮下脂肪 + 肌肉 + 肌间脂肪 + 内脏脂肪（受 body_mask 约束）
    np_tissue += np_visceral       # in-place
    np.multiply(np_tissue, np_body, out=np_tissue)

    # ---- 保存 ----
    save_path = os.path.join(label_path, 'tissues.nii.gz')
    ImageIO.array2nii(np_tissue, save_path, spacing, origin, direction)

    return save_path


def main(max_workers: int = None) -> None:
    """
    主函数: 并行处理所有 CT 图像生成组织标签。

    Parameters
    ----------
    max_workers : int, optional
        并行进程数
    """
    image_list = sorted(glob.glob('d:/wq/ct_image/*.nii.gz'))
    label_list = sorted(glob.glob('d:/wq/boa_label/*'))

    if len(image_list) != len(label_list):
        print(f"警告: 图像数量({len(image_list)})与标签目录数量({len(label_list)})不匹配，"
              f"将取较小值进行匹配")

    n_samples = min(len(image_list), len(label_list))
    if n_samples == 0:
        print("错误: 未找到任何图像或标签文件，请检查路径")
        return

    args_list = list(zip(image_list[:n_samples], label_list[:n_samples]))

    # 确定并行进程数（默认8，避免过多进程占满内存）
    max_workers = 8

    print(f"待处理样本数: {n_samples}")
    print(f"并行进程数:   {max_workers}")
    print("-" * 40)

    # 并行处理
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_single_image, args): args
            for args in args_list
        }

        with tqdm(total=len(futures), desc='Generating tissue labels') as pbar:
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    _, label_path = futures[future]
                    pbar.write(f"错误 [{os.path.basename(label_path)}]: {e}")
                pbar.update(1)

    print("处理完成!")


if __name__ == '__main__':
    # 支持命令行指定进程数: python tissue_label_parallel.py 4
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(max_workers=workers)
