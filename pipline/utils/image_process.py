import numpy as np
import scipy.ndimage as ndi
from typing import Union, Optional, Tuple
import SimpleITK as sitk


class ImageProcess:
    @staticmethod
    def array_resize(input_array: np.ndarray, new_shape, order=0) -> np.ndarray:
        """
        使用scipy.ndimage.zoom将3D数组重采样到指定大小

        参数:
        input_array: 输入的3D numpy数组
        new_shape: 目标形状 (depth, height, width)
        order: 插值顺序 (0=最邻近, 1=双线性, 3=三次样条)

        返回:
        重采样后的3D数组
        """
        # 计算每个维度的缩放因子
        original_shape = input_array.shape
        zoom_factors = (
            new_shape[0] / original_shape[0],
            new_shape[1] / original_shape[1],
            new_shape[2] / original_shape[2]
        )
        # 使用最邻近插值进行重采样
        output = ndi.zoom(input_array, zoom_factors, order=order)

        return output

    @staticmethod
    def itk_resize(input_image: sitk.Image,
                   new_size: Optional[Tuple[int, int, int]] = None,
                   new_spacing: Optional[Tuple[float, float, float]] = None,
                   interpolation = "Linear",
                   default_value: float = 0.0) -> sitk.Image:
        """
        使用SimpleITK对3D医学图像进行重采样

        参数:
            input_image: 输入的SimpleITK图像
            new_size: 目标图像大小 (深度, 高度, 宽度)
            new_spacing: 目标体素间距 (z_spacing, y_spacing, x_spacing)
            interpolation: 插值方法 (sitk.sitkNearestNeighbor, sitk.sitkLinear, sitk.sitkBSpline等)
            default_value: 重采样时超出区域的默认值

        返回:
            重采样后的SimpleITK图像

        说明:
            必须提供new_size或new_spacing中的一个参数，不能同时提供两个
        """
        # 获取原始图像信息
        original_spacing = input_image.GetSpacing()
        original_size = input_image.GetSize()
        original_origin = input_image.GetOrigin()
        original_direction = input_image.GetDirection()

        # 创建重采样滤波器
        resampler = sitk.ResampleImageFilter()

        if interpolation == "Linear":
            resampler.SetInterpolator(sitk.sitkLinear)
        elif interpolation == "NearestNeighbor":
            resampler.SetInterpolator(sitk.sitkNearestNeighbor)
        elif interpolation == "BSpline":
            resampler.SetInterpolator(sitk.sitkBSpline)

        resampler.SetOutputDirection(original_direction)
        resampler.SetOutputOrigin(original_origin)
        resampler.SetDefaultPixelValue(default_value)

        # 根据输入参数计算新的间距和大小
        if new_size is not None:
            # 根据新大小计算对应的新间距
            new_spacing = [
                round(original_spacing[0] * (original_size[0] / new_size[0]), 2),
                round(original_spacing[1] * (original_size[1] / new_size[1]), 2),
                round(original_spacing[2] * (original_size[2] / new_size[2]), 2),
            ]
            resampler.SetSize(new_size)
            resampler.SetOutputSpacing(new_spacing)
        elif new_spacing is not None:
            # 根据新间距计算对应的新大小
            new_size = [
                int(round(original_size[0] * (original_spacing[0] / new_spacing[0]))),
                int(round(original_size[1] * (original_spacing[1] / new_spacing[1]))),
                int(round(original_size[2] * (original_spacing[2] / new_spacing[2]))),
            ]
            resampler.SetOutputSpacing(new_spacing)
            resampler.SetSize(new_size)
        else:
            raise ValueError("必须提供'new_size'或'new_spacing'参数！")

        return resampler.Execute(input_image)

    @staticmethod
    def normalize(array: np.ndarray,
                        method: str = 'minmax',
                        min_val: float = 0.0,
                        max_val: float = 1.0) -> np.ndarray:
        """
        对3D医学图像进行归一化处理

        参数:
            array: 输入的3D numpy数组
            method: 归一化方法 ('minmax', 'zscore', 'clip')
                   - minmax: 最小-最大归一化，将数据缩放到[min_val, max_val]范围
                   - zscore: Z-score标准化，使数据均值为0，标准差为1
                   - clip: 数据裁剪，将超出范围的值裁剪到指定区间
            min_val: 最小值（用于minmax和clip方法）
            max_val: 最大值（用于minmax和clip方法）
            
        返回:
            归一化后的3D数组
            
        异常:
            ValueError: 当指定了不支持的归一化方法时抛出
        """
        if method == 'minmax':
            # 最小-最大归一化
            arr_min, arr_max = np.min(array), np.max(array)
            if arr_max > arr_min:
                return (array - arr_min) / (arr_max - arr_min) * (max_val - min_val) + min_val
            return np.zeros_like(array)
        elif method == 'zscore':
            # Z-score标准化
            mean, std = np.mean(array), np.std(array)
            if std > 0:
                return (array - mean) / std
            return np.zeros_like(array)
        elif method == 'clip':
            # 范围裁剪
            return np.clip(array, min_val, max_val)
        else:
            raise ValueError(f"不支持的归一化方式: {method}")

    @staticmethod
    def bounding_box(array: np.ndarray, condition=None) -> Union[Tuple[slice, slice, slice], np.ndarray]:
        """
        计算3D数组中目标区域的最小边界框
        
        参数:
            array: 输入的3D numpy数组
            condition: 条件函数，用于确定目标区域（默认为非零元素）
                     例如: lambda x: x > 0.5 可用于阈值分割
        
        返回:
            包含目标区域的最小边界框切片对象，格式为 (slice_z, slice_y, slice_x)
            如果未找到目标区域，返回空数组
            
        示例:
            # 获取非零区域的边界框
            bbox = ImageProcess.bounding_box(image_array)
            cropped = image_array[bbox]
            
            # 获取阈值分割后的边界框
            bbox = ImageProcess.bounding_box(image_array, lambda x: x > 100)
        """
        # 设置默认条件为非零元素
        if condition is None:
            mask = array != 0
        else:
            mask = condition(array)

        # 获取所有满足条件的坐标
        coordinates = np.argwhere(mask)
        if coordinates.size == 0:
            # 未找到目标区域，返回空数组
            return np.array([])

        # 计算每个维度的最小和最大索引
        min_coordinates = coordinates.min(axis=0)
        max_coordinates = coordinates.max(axis=0)

        # 创建切片对象（边界框）
        slices = tuple(slice(min_dim, max_dim+1) for min_dim, max_dim in zip(min_coordinates, max_coordinates))
        return slices

    @staticmethod
    def median_filter(image: np.ndarray, kernel_size: Tuple[int, int, int]) -> np.ndarray:
        """
        对3D医学图像应用中值滤波去除噪声
        
        参数:
            image: 输入的3D numpy数组
            kernel_size: 中值滤波的核大小 (z, y, x)
                       建议使用奇数，如(3,3,3)或(5,5,5)
                       
        返回:
            中值滤波后的3D数组
            
        说明:
            中值滤波对于去除医学图像中的椒盐噪声特别有效
            同时能较好地保留边缘信息
        """
        return ndi.median_filter(image, size=kernel_size, mode='nearest')

    @staticmethod
    def gaussian_filter(image: np.ndarray,
                              sigma: Union[float, Tuple[float, float, float]] = 1.0) -> np.ndarray:
        """
        对3D医学图像应用高斯滤波

        参数:
            image: 输入的3D numpy数组
            sigma: 高斯核的标准差
                  - 单个值：在所有维度使用相同的sigma
                  - 元组：(sigma_z, sigma_y, sigma_x) 每个维度使用不同的sigma

        返回:
            高斯滤波后的3D数组

        说明:
            高斯滤波用于平滑图像，去除高频噪声
            sigma值越大，平滑效果越强
        """
        return ndi.gaussian_filter(image, sigma=sigma, mode='nearest')

    @staticmethod
    def remove_small_islands(image: np.ndarray, min_size: int) -> np.ndarray:
        """
        移除3D二值图像中的小连通区域
        
        参数:
            image: 输入的3D二值numpy数组 (0和1组成)
            min_size: 保留的最小连通区域大小（体素数量）
                   小于该值的连通区域将被移除
                   
        返回:
            移除小连通区域后的3D二值数组 (uint8类型)
            
        说明:
            使用连通域分析标记每个独立的区域
            然后根据区域大小进行筛选
            常用于医学图像分割后的后处理
        """
        # 标记连通区域
        labeled_array, num_features = ndi.label(image)
        
        # 计算每个连通区域的大小
        sizes = np.bincount(labeled_array.ravel())
        
        # 创建大小筛选掩膜
        mask_sizes = sizes >= min_size
        mask_sizes[0] = False  # 背景区域（标签0）不参与筛选
        
        # 应用筛选掩膜
        cleaned = mask_sizes[labeled_array]
        
        return cleaned.astype(np.uint8)

    @staticmethod
    def margin_grow(image: np.ndarray, kernel_size: Tuple[int, int, int]) -> np.ndarray:
        """
        对3D二值掩膜进行边缘膨胀操作
        
        参数:
            image: 输入的3D二值numpy数组 (0和1组成)
            kernel_size: 膨胀核大小 (z, y, x)
                       建议使用奇数，如(3,3,3)或(5,5,5)
                       
        返回:
            边缘膨胀后的3D二值数组 (uint8类型)
            
        说明:
            使用形态学膨胀操作，将掩膜边缘向外扩展
            常用于扩大感兴趣区域或填补掩膜中的小空洞
        """
        return ndi.binary_dilation(image, structure=np.ones(kernel_size)).astype(np.uint8)

    @staticmethod
    def margin_shrink(image: np.ndarray, kernel_size: Tuple[int, int, int]) -> np.ndarray:
        """
        对3D二值掩膜进行边缘腐蚀操作
        
        参数:
            image: 输入的3D二值numpy数组 (0和1组成)
            kernel_size: 腐蚀核大小 (z, y, x)
                       建议使用奇数，如(3,3,3)或(5,5,5)
                       
        返回:
            边缘腐蚀后的3D二值数组 (uint8类型)
            
        说明:
            使用形态学腐蚀操作，将掩膜边缘向内收缩
            常用于去除掩膜边缘的毛刺或小突起
        """
        return ndi.binary_erosion(image, structure=np.ones(kernel_size)).astype(np.uint8)

    @staticmethod
    def resample_intensity(image: np.ndarray, 
                          percentiles: Tuple[float, float] = (1.0, 99.0)) -> np.ndarray:
        """
        对3D医学图像进行强度重采样（去除异常值）
        
        参数:
            image: 输入的3D numpy数组
            percentiles: 百分位范围 (min_percentile, max_percentile)
                        默认去除1%的最低值和99%的最高值
                        
        返回:
            强度重采样后的3D数组，值域为[0, 1]
            
        说明:
            有效去除CT或MRI图像中的异常高强度值
            常用于深度学习模型的预处理
        """
        # 计算百分位值
        min_val = np.percentile(image, percentiles[0])
        max_val = np.percentile(image, percentiles[1])
        
        # 裁剪到指定范围
        clipped = np.clip(image, min_val, max_val)
        
        # 归一化到[0, 1]
        if max_val > min_val:
            return (clipped - min_val) / (max_val - min_val)
        else:
            return np.zeros_like(image)


