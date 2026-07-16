import glob
from tissue_statistic import process_vertebra_analysis, save_results_to_csv


BASE_PATH = "d:/hjf/after_treatment"
VERTEBRA_NAME_START = "T1"
VERTEBRA_NAME_END = "T12"
RANGE_MM = None

patient_path = glob.glob(f"{BASE_PATH}/ct_image/*")

for i in range(len(patient_path)):
    patient_id = patient_path[i].split("\\")[-1][:-7]

    # 执行椎体间范围分析
    print(f"({i+1}/{len(patient_path)})开始分析ID号为 {patient_id} 患者的 {VERTEBRA_NAME_START} 椎体到 {VERTEBRA_NAME_END} 椎体层面组织信息...")
    df_results, range_mm = process_vertebra_analysis(
        base_path = BASE_PATH, patient_id=patient_id, vertebra_name_start=VERTEBRA_NAME_START, vertebra_name_end=VERTEBRA_NAME_END, analysis_range=None)

    # 保存结果
    if not df_results.empty:
        save_results_to_csv(
            df_results, base_path=BASE_PATH, patient_id=patient_id, vertebra_name=f"{VERTEBRA_NAME_START}-{VERTEBRA_NAME_END}", analysis_range=range_mm)
    else:
        print("--分析失败，未生成结果")