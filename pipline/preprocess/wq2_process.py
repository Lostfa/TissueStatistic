import os
import glob
import pandas as pd
import SimpleITK as sitk
from tqdm import tqdm
from utils.image_io import ImageIO, ImageInfo
from utils.image_process import ImageProcess


dicom_path = glob.glob('d:/wq2/*/*/*')

file_name_list = []
file_date_list = []

series_date_list = []
patient_name_list = []
patient_id_list = []

image_size_list = []
image_spacing_list = []
new_size_list = []
new_spacing_list = []


for i in tqdm(range(len(dicom_path))):
    file_name = dicom_path[i][7:]
    file_name_list.append(file_name)

    dicom_info = ImageInfo.get_dicom_metadata(dicom_path[i])
    series_date = dicom_info['series_date']

    patient_id = dicom_info['patient_id']

    series_date_list.append(series_date)
    patient_id_list.append(patient_id)

    itk_image = ImageIO.dcm2itk(dicom_path[i])
    itk_info = ImageInfo.get_image_info(itk_image)
    image_size = itk_info['size']
    image_spacing = itk_info['spacing']
    image_origin = itk_info['origin']
    image_direction = itk_info['direction']

    new_spacing = (image_spacing[0], image_spacing[1], 1)
    new_origin = (0, 0, 0)
    new_direction = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)

    image_size_list.append(image_size)
    image_spacing_list.append(image_spacing)

    resized_itk_image = ImageProcess.itk_resize(itk_image, new_spacing=new_spacing, interpolation=sitk.sitkBSpline)
    new_size_list.append(resized_itk_image.GetSize())
    new_spacing_list.append(resized_itk_image.GetSpacing())

    save_path = dicom_path[i][:30].replace('wq2', 'ct_image') + '.nii.gz'
    print(save_path)
    ImageIO.itk2nii(resized_itk_image, save_path, spacing=new_spacing, origin=new_origin, direction=new_direction)

    df = pd.DataFrame({'file_name': file_name_list,
                       'series_date': series_date_list,
                       'patient_id': patient_id_list,
                       'image_size': image_size_list,
                       'image_spacing': image_spacing_list,
                       'new_size': new_size_list,
                       'new_spacing': new_spacing_list,
                       })
    df.to_csv('d:/image_info.csv', index=False, encoding='gbk', errors='ignore')
