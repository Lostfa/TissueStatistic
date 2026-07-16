import os
import glob
import pandas as pd
from tqdm import tqdm


LABEL_TISSUE = {1:'MUSCLE', 2:'BONE', 3:'SAT', 4:'VAT', 5:'IMAT', 6:'PAT', 7:'EAT'}
LABEL_INDICATOR = {0:'volume', 3:'mean', 4:'std'}

# work_path = "d:/hjf/before_treatment"
work_path = "d:/hjf/after_treatment"

image_path = glob.glob(f"{work_path}/boa_label/*")
patient_id = [os.path.basename(path) for path in image_path]
csv_path = glob.glob(f"{work_path}/tissue_statistic/*/*.csv")

# target_csv = "T1-T12"
target_csv = "T2-T10"

result = pd.DataFrame()

for i in tqdm(range(len(image_path))):
    result.loc[i, "id"] = patient_id[i]
    id_target = f"{patient_id[i]}_{target_csv}"
    for j in range(len(csv_path)):
        if id_target in csv_path[j]:
            # print(f"找到id_target ‘{id_target}’ 对应的csv文件 ‘{csv_path[j]}’")
            csv_info = csv_path[j].split("/")[-1].split("_")
            result.loc[i, "vertebra"] = csv_info[-2]
            result.loc[i, "range"] = csv_info[-1][:-6]

            tissue_statistic = pd.read_csv(csv_path[j])
            for t_label, tissue in LABEL_TISSUE.items():
                for i_label, indicator in LABEL_INDICATOR.items():
                    result.loc[i, f"{tissue}_{indicator}"] = tissue_statistic[tissue][i_label]

result.to_csv(f"{work_path}/result_{target_csv}.csv", index=False)