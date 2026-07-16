import pandas as pd
from tqdm import tqdm


LABEL_TISSUE = {1:'MUSCLE', 2:'BONE', 3:'SAT', 4:'VAT', 5:'IMAT', 6:'PAT', 7:'EAT'}
LABEL_INDICATOR = {0:'volume', 3:'mean', 4:'std'}

work_time = ["before", "after"]
work_path = "d:/lyx"
target_csv = "T2-T10"
# target_csv = "T10_20mm"


clinic_info = pd.read_csv(f"{work_path}/clinic_info.csv", index_col="NAME", dtype={'NAME': str})
result = clinic_info.copy()


for wt in work_time:
    image_info = pd.read_csv(f"{work_path}/{wt}_treatment/image_info_vertebra.csv", encoding='gbk')
    tissue_info = pd.read_csv(f"{work_path}/{wt}_treatment/result_{target_csv}.csv", index_col="id")

    result[f"{wt}_vertebra"] = pd.Series(dtype=object)
    for i in tqdm(range(len(image_info)), desc=f"Calculate {wt}_treatment"):
        image_name = image_info.loc[i, "file_name"]
        patient_id = image_info.loc[i, "patient_id"]
        inspection_date = pd.to_datetime(image_info.loc[i, "inspection_date"], format="%Y%m%d")

        if patient_id in tissue_info.index:
            analysis_vertebra = tissue_info.loc[patient_id, "vertebra"]

            if "range" in tissue_info.columns:
                analysis_range = tissue_info.loc[patient_id, "range"]
                result.loc[image_name, f"{wt}_range"] = analysis_range

            result.loc[image_name, f"{wt}_date"] = inspection_date
            result.loc[image_name, f"{wt}_id"] = patient_id
            result.loc[image_name, f"{wt}_vertebra"] = analysis_vertebra

            for t_label, tissue in LABEL_TISSUE.items():
                for i_label, indicator in LABEL_INDICATOR.items():
                    result.loc[image_name, f"{wt}_{tissue}_{indicator}"] = tissue_info.loc[patient_id, f"{tissue}_{indicator}"]


for name in tqdm(result.index, desc=f"Calculate delta"):
    try:
        for t_label, tissue in LABEL_TISSUE.items():
            for i_label, indicator in LABEL_INDICATOR.items():
                before_date = result.loc[name, "before_date"]
                after_date = result.loc[name, "after_date"]
                if before_date is not None and after_date is not None:
                    delta_days = (after_date - before_date).days
                    result.loc[name, f"delta_days"] = delta_days

                before_data = result.loc[name, f"before_{tissue}_{indicator}"]
                after_data = result.loc[name, f"after_{tissue}_{indicator}"]
                if before_data is not None and after_data is not None:
                    delta_data = after_data - before_data
                    result.loc[name, f"delta_{tissue}_{indicator}"] = delta_data
    except:
        print(name)

result.to_csv(f"{work_path}/delta_result_{target_csv}.csv", encoding="gbk")