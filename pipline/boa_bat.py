import glob
import os
from pathlib import Path

work_path = Path('d:/hjf2')
bat_path = work_path / 'boa.bat'
input_dir = work_path / 'ct_image'
output_dir = work_path / 'boa_label'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
task = 'all'

bat_content = '''@echo off
call activate boa

'''

input_files = glob.glob(os.path.join(input_dir, '*.nii.gz'))
input_files.sort()

for i in range(640, 842):
    filename = os.path.basename(input_files[i])
    file_stem = filename[:-7]

    file_path = os.path.join(input_dir, filename).replace('\\', '/')
    output_path = os.path.join(output_dir, file_stem).replace('\\', '/')

    command = f'python c:/python/Boa --input-image {file_path} --output-dir {output_path} --models {task} --verbose'
    print(command)

    bat_content += f'echo ----------------Executing task in: {filename}----------------\n'
    bat_content += f'{command}\n\n'

bat_content += '''echo All tasks completed!
pause
'''

with open(bat_path, 'w') as f:
    f.write(bat_content)

print(f'segment bat saved to: {bat_path}')