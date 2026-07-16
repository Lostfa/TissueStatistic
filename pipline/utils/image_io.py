import glob
import numpy as np
import SimpleITK as sitk
from pathlib import Path
from typing import Union, Dict, Any, Tuple, Optional


class ImageIO:
    @staticmethod
    def dcm2itk(dicom_dir: Union[str, Path]) -> sitk.Image:
        """读取DICOM序列为SimpleITK图像"""
        series_reader = sitk.ImageSeriesReader()
        names = series_reader.GetGDCMSeriesFileNames(str(dicom_dir))
        series_reader.SetFileNames(names)
        image = series_reader.Execute()
        print(f'\033[36m[ImageIO] 读取DICOM序列 "{dicom_dir}" 为SimpleITK图像\n'
              f' size: {image.GetSize()}\n'
              f' spacing: {image.GetSpacing()}\n'
              f' origin: {image.GetOrigin()}\n'
              f' direction: {image.GetDirection()}\n'
              f' dtype: {image.GetPixelIDTypeAsString()}\n'
              f'------------------------------------------------\033[0m')
        return image

    @staticmethod
    def nii2itk(nifti_path: Union[str, Path]) -> sitk.Image:
        """读取NIfTI文件为SimpleITK图像"""
        image = sitk.ReadImage(nifti_path)
        print(f'\033[36m[ImageIO] 读取NIfTI文件 "{nifti_path}" 为SimpleITK图像\n'
              f' size: {image.GetSize()}\n'
              f' spacing: {image.GetSpacing()}\n'
              f' origin: {image.GetOrigin()}\n'
              f' direction: {image.GetDirection()}\n'
              f' dtype: {image.GetPixelIDTypeAsString()}\n'
              f'------------------------------------------------\033[0m')
        return image

    @staticmethod
    def array2itk(array: np.ndarray, reference_image: Optional[sitk.Image] = None) -> sitk.Image:
        """NumPy数组转SimpleITK图像"""
        image = sitk.GetImageFromArray(array)
        if reference_image is not None:
            image.SetSpacing(reference_image.GetSpacing())
            image.SetOrigin(reference_image.GetOrigin())
            image.SetDirection(reference_image.GetDirection())
        return image
    
    @staticmethod
    def itk2array(image: sitk.Image, dtype: str) -> np.ndarray:
        """SimpleITK图像转NumPy数组"""
        return sitk.GetArrayFromImage(image).astype(dtype)

    @staticmethod
    def nii2array(nifti_path: Union[str, Path], dtype: str) -> np.ndarray:
        """SimpleITK图像转NumPy数组"""
        image = sitk.ReadImage(nifti_path)
        return sitk.GetArrayFromImage(image).astype(dtype)
    
    @staticmethod
    def itk2nii(image: sitk.Image, nifti_path: Union[str, Path],
                   spacing: Tuple[float, float, float] = (1.0, 1.0, 1.0),
                   origin: Tuple[float, float, float] = (0.0, 0.0, 0.0),
                   direction: Tuple[float, float, float, float, float, float, float, float, float]\
                           =(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)) -> None:
        """SimpleITK图像保存为NIfTI格式"""
        image.SetSpacing(spacing)
        image.SetOrigin(origin)
        image.SetDirection(direction)
        sitk.WriteImage(image, str(nifti_path))
        print(f'\033[36m[ImageIO] 从SimpleITK保存NIfTI图像到 "{nifti_path}"\n'
              f' size: {image.GetSize()}\n'
              f' spacing: {image.GetSpacing()}\n'
              f' origin: {image.GetOrigin()}\n'
              f' direction: {image.GetDirection()}\n'
              f' dtype: {image.GetPixelIDTypeAsString()}\n'
              f'------------------------------------------------\033[0m')

    @staticmethod
    def array2nii(array: np.ndarray, nifti_path: Union[str, Path],
                    spacing: Tuple[float, float, float] = (1.0, 1.0, 1.0),
                    origin: Tuple[float, float, float] = (0.0, 0.0, 0.0),
                    direction: Tuple[float, float, float, float, float, float, float, float, float]\
                            = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)) -> None:
        """NumPy数组保存为NIfTI格式"""
        image = sitk.GetImageFromArray(array)
        image.SetSpacing(spacing)
        image.SetOrigin(origin)
        image.SetDirection(direction)
        sitk.WriteImage(image, str(nifti_path))
        print(f'\033[36m[ImageIO] 从NumPy数组保存NIfTI图像到 "{nifti_path}"\n'
              f' size: {image.GetSize()}\n'
              f' spacing: {image.GetSpacing()}\n'
              f' origin: {image.GetOrigin()}\n'
              f' direction: {image.GetDirection()}\n'
              f' dtype: {image.GetPixelIDTypeAsString()}\n'
              f'------------------------------------------------\033[0m')
    

class ImageInfo:
    @staticmethod
    def get_dicom_metadata(dicom_dir: Union[str, Path]) -> Dict[str, Any]:
        """获取DICOM元数据"""
        dicom_files = glob.glob(str(dicom_dir) + '/*.dcm')
        if not dicom_files:
            raise FileNotFoundError(f'DICOM files not found in {dicom_dir}')
        
        reader = sitk.ImageFileReader()
        reader.SetFileName(dicom_files[0])
        reader.LoadPrivateTagsOn()
        reader.ReadImageInformation()
        
        def safe_get_metadata(key, default="Unknown"):
            try:
                return reader.GetMetaData(key)
            except RuntimeError:
                return default
        
        return {
            'institution': safe_get_metadata('0008|0080'),
            'manufacturer': safe_get_metadata('0008|0070'),
            'studyUID': safe_get_metadata('0020|000d'),
            'protocol': safe_get_metadata('0018|1030'),
            'series_date': safe_get_metadata('0008|0021'),
            'series_time': safe_get_metadata('0008|0031'),
            'series_description': safe_get_metadata('0008|103e'),
            'series_number': safe_get_metadata('0020|0011'),
            'patient_id': safe_get_metadata('0010|0020'),
            'patient_name': safe_get_metadata('0010|0010'),
            'patient_age': safe_get_metadata('0010|1010'),
            'patient_sex': safe_get_metadata('0010|0040')
        }
    
    @staticmethod
    def get_image_info(image: Union[sitk.Image, np.ndarray]) -> Dict[str, Any]:
        info = {}
        if isinstance(image, sitk.Image):
            info['type'] = 'SimpleITK'
            info['size'] = image.GetSize()
            info['spacing'] = image.GetSpacing()
            info['origin'] = image.GetOrigin()
            info['direction'] = image.GetDirection()
            info['dtype'] = image.GetPixelIDTypeAsString()
            info['physical_size'] = tuple(s * n for s, n in zip(info['spacing'], info['size']))
            array = sitk.GetArrayFromImage(image)
            info['min_hu'] = np.min(array)
            info['max_hu'] = np.max(array)
            info['mean_hu'] = np.mean(array)
            info['std_hu'] = np.std(array)

            
        elif isinstance(image, np.ndarray):
            info['type'] = 'NumPy'
            info['shape'] = image.shape
            info['dtype'] = str(image.dtype)
            info['voxel_count'] = image.size
            info['sum_value'] = np.sum(image)
            info['min_value'] = np.min(image)
            info['max_value'] = np.max(image)
            info['mean_value'] = np.mean(image)
            info['std_value'] = np.std(image)
        
        return info

    @staticmethod
    def show_info(image: Union[sitk.Image, np.ndarray, str, Path]) -> None:
        image_info = dict()
        if isinstance(image, sitk.Image):
            image_info = ImageInfo.get_image_info(image)
            print(f'\033[36m[ImageInfo] SimpleITK图像的信息：\033[0m')
        elif isinstance(image, np.ndarray):
            image_info = ImageInfo.get_image_info(image)
            print(f'\033[36m[ImageInfo] NumPy数组的信息：\033[0m')
        elif isinstance(image, (str, Path)):
            path_obj = Path(image) if isinstance(image, str) else image
            if path_obj.is_dir():
                print(f'\033[36m[ImageInfo] DICOM序列 "{image}" 的元数据：\033[0m')
                image_info = ImageInfo.get_dicom_metadata(path_obj)
            elif path_obj.is_file():
                if path_obj.suffix in ['.nii', '.nii.gz', '.gz', '.nrrd']:
                    image_info = ImageInfo.get_image_info(sitk.ReadImage(path_obj))
                    print(f'\033[36m[ImageInfo] NIfTI文件 "{image}" 的信息：\033[0m')
                elif path_obj.suffix in ['.npy', '.npz']:
                    image_info = ImageInfo.get_image_info(np.load(path_obj))
                    print(f'\033[36m[ImageInfo] NumPy文件 "{image}" 的信息：\033[0m')
                else:
                    raise ValueError(f"Unsupported file format: {path_obj.suffix}")

        for key, value in image_info.items():
            print(f'\033[36m {key}: {value}\033[0m')
        print(f'\033[36m------------------------------------------------\033[0m')