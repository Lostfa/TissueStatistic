import os
import glob
import pandas as pd
import SimpleITK as sitk
from tqdm import tqdm
from utils.image_io import ImageIO, ImageInfo
from utils.image_process import ImageProcess


dicom_path = glob.glob('/home/wuzhifa/data/hjf/after_treatment/ct_dicom/*/*')

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
    file_name = dicom_path[i].split('/')[-2].split('_')[0]
    # file_date = dicom_path[i].split('/')[-2].split('_')[1]
    file_name_list.append(file_name)
    # file_date_list.append(file_date)

    dicom_info = ImageInfo.get_dicom_metadata(dicom_path[i])
    series_date = dicom_info['series_date']

    patient_name = dicom_info['patient_name']
    try:
        print(patient_name)
    except UnicodeEncodeError as e:
        print(f'\nUnicodeEncodeError: {e}')
        patient_name = ' '
    if patient_name[-1] == ' ':
        patient_name = patient_name[:-1]

    patient_id = dicom_info['patient_id']
    if patient_id[-1] == ' ':
        patient_id = patient_id[:-1]

    save_name = f'{patient_id}.nii.gz'

    series_date_list.append(series_date)
    patient_name_list.append(patient_name)
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

    save_path = os.path.join('/home/wuzhifa/data/hjf/after_treatment/ct_image', save_name)
    print(save_path)
    ImageIO.itk2nii(resized_itk_image, save_path, spacing=new_spacing, origin=new_origin, direction=new_direction)

    df = pd.DataFrame({'file_name': file_name_list,
                       # 'file_date': file_date_list,
                       'series_date': series_date_list,
                       'patient_name': patient_name_list,
                       'patient_id': patient_id_list,
                       'image_size': image_size_list,
                       'image_spacing': image_spacing_list,
                       'new_size': new_size_list,
                       'new_spacing': new_spacing_list,
                       })
    df.to_csv('/home/wuzhifa/data/hjf/after_treatment/image_info.csv', index=False, encoding='gbk', errors='ignore')