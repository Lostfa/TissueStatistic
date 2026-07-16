import os
import shutil
import glob
import pandas as pd
import SimpleITK as sitk
from tqdm import tqdm
from utils.image_io import ImageIO, ImageInfo
from utils.image_process import ImageProcess


patient_id_list = []
image_size_list = []
image_spacing_list = []
new_size_list = []
new_spacing_list = []

id_list = glob.glob('d:/hjf2/total_image/*')

for i in tqdm(range(len(id_list))):
    nii_path = glob.glob((id_list[i]) + '/*/*nii*')

    for j in range(len(nii_path)):
        itk_image = ImageIO.nii2itk(nii_path[j])
        image_size = itk_image.GetSize()
        image_spacing = itk_image.GetSpacing()
        image_size_list.append(image_size)
        image_spacing_list.append(image_spacing)

        new_spacing = (image_spacing[0], image_spacing[1], 1)
        new_origin = (0, 0, 0)
        new_direction = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
        resized_itk_image = ImageProcess.itk_resize(itk_image, new_spacing=new_spacing, interpolation=sitk.sitkBSpline)
        new_size_list.append(resized_itk_image.GetSize())
        new_spacing_list.append(resized_itk_image.GetSpacing())
        smoothed_itk_image = sitk.DiscreteGaussian(resized_itk_image, [1.5, 1.5, 1.5])
        smoothed_itk_image = sitk.Cast(smoothed_itk_image, sitk.sitkInt16)

        patient_id = nii_path[j][20:].replace('\\', '_').split('.')[0][:-6]
        patient_id_list.append(patient_id)

        save_name = f'{patient_id}.nii.gz'
        save_path = os.path.join('d:/hjf2/ct_image', save_name)
        print(save_path)

        ImageIO.itk2nii(smoothed_itk_image, save_path, spacing=new_spacing, origin=new_origin, direction=new_direction)

        df = pd.DataFrame({'patient_id' : patient_id_list,
                           'image_size' : image_size_list,
                           'image_spacing' : image_spacing_list,
                           'new_size' : new_size_list,
                           'new_spacing' : new_spacing_list
                           })

        df.to_csv('d:/hjf2/image_info.csv', index=False, encoding='gbk', errors='ignore')

















