import gradio as gr
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import json
from typing import List, Tuple, Optional, Dict
import io
from pathlib import Path

from tissue_statistic import (
    VERTEBRA_LABEL, TISSUE_LABEL, STAT_NAMES,
    remove_extra_vertebra_parts, get_vertebra_center_coordinates,
    extract_vertebra_region, calculate_tissue_statistics,
    load_image_files, LABEL_TISSUE, LABEL_VERTEBRA
)

# 过滤出T1-T12的椎体标签
T_VERTEBRA_LABEL = {k: v for k, v in VERTEBRA_LABEL.items() if k.startswith('T')}

class TissueAnalyzerGUI:
    def __init__(self):
        self.base_path = "./data"
        self.available_subjects = []
        self.current_results = {}
        self.refresh_subject_list()

    def refresh_subject_list(self):
        """获取所有可用的CT图像ID"""
        image_dir = Path(self.base_path) / "ct_image"
        if image_dir.exists():
            self.available_subjects = sorted([f.stem[:-4] for f in image_dir.glob("*.nii.gz")])
        else:
            self.available_subjects = []

    def get_vertebra_display_image(self, subject_id: str, vertebra_name: str) -> Optional[np.ndarray]:
        """获取椎体的显示图像"""
        try:
            # 确保subject_id不包含扩展名
            if subject_id.endswith('.nii.gz'):
                subject_id = subject_id[:-7]  # 移除.nii.gz
            elif subject_id.endswith('.nii'):
                subject_id = subject_id[:-4]  # 移除.nii

            print(f"生成显示图像: 受试者ID={subject_id}, 椎体={vertebra_name}")

            # 加载数据
            ct_array, bca_array, total_array, tissues_array, voxel_volume, z_ratio = \
                load_image_files(self.base_path, subject_id)

            # 获取椎体中心点坐标
            center_coordinates = get_vertebra_center_coordinates(bca_array, total_array, vertebra_name)

            if center_coordinates is None:
                print(f"无法获取椎体{vertebra_name}的中心坐标用于显示")
                return None

            print(f"椎体{vertebra_name}中心坐标: {center_coordinates}")

            # 创建显示图像 (X和Y轴方向的切片)
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']

            # X轴切片
            x_array = np.flipud(ct_array[:, center_coordinates[1], :])
            mask_x = np.zeros_like(x_array)
            mask_x[center_coordinates[0], :] = 1
            label_x_array = np.zeros((x_array.shape[0], x_array.shape[1], 4))
            label_x_array[np.flipud(mask_x) == 1] = [1, 0, 0, 0.5]

            # Y轴切片
            y_array = np.flipud(ct_array[:, :, center_coordinates[2]])
            mask_y = np.zeros_like(y_array)
            mask_y[center_coordinates[0], :] = 1
            label_y_array = np.zeros((x_array.shape[0], x_array.shape[1], 4))
            label_y_array[np.flipud(mask_y) == 1] = [1, 0, 0, 0.5]

            # 显示X轴切片
            ax1.imshow(x_array, cmap="gray", vmin=-160, vmax=240)
            ax1.imshow(label_x_array, cmap="Oranges", aspect=z_ratio)
            ax1.set_title(f"{vertebra_name}-冠状位中心层面")
            ax1.axis('off')

            # 显示Y轴切片
            ax2.imshow(y_array, cmap="gray", vmin=-160, vmax=240)
            ax2.imshow(label_y_array, cmap="Oranges", aspect=z_ratio)
            ax2.set_title(f"{vertebra_name}-矢状位中心层面")
            ax2.axis('off')

            plt.tight_layout()

            # 转换为numpy数组
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            image_array = plt.imread(buf)
            plt.close()

            print(f"成功生成椎体{vertebra_name}的显示图像")
            return image_array

        except Exception as e:
            print(f"生成显示图像时出错: {e}")
            import traceback
            traceback.print_exc()
            return None

    def analyze_vertebra(self, subject_id: str, vertebra_name: str, range_mm: int) -> pd.DataFrame:
        """分析单个椎体的组织信息"""
        try:
            # 确保subject_id不包含扩展名
            if subject_id.endswith('.nii.gz'):
                subject_id = subject_id[:-7]  # 移除.nii.gz
            elif subject_id.endswith('.nii'):
                subject_id = subject_id[:-4]  # 移除.nii

            print(f"开始分析: 受试者ID={subject_id}, 椎体={vertebra_name}, 范围={range_mm}mm")

            # 加载数据
            ct_array, bca_array, total_array, tissues_array, voxel_volume, z_ratio = \
                load_image_files(self.base_path, subject_id)

            # 获取椎体中心点坐标
            center_coordinates = get_vertebra_center_coordinates(bca_array, total_array, vertebra_name)

            if center_coordinates is None:
                print(f"无法获取椎体{vertebra_name}的中心坐标")
                return pd.DataFrame()

            # 获取椎体在z轴方向上的中心层面切片（mask）
            center_slice = np.zeros_like(total_array)
            center_slice[center_coordinates[0], :, :] = 1

            # 提取组织区域
            tissue_region = extract_vertebra_region(center_slice, tissues_array, range_mm)

            if tissue_region is None:
                print(f"无法提取椎体{vertebra_name}的组织区域")
                return pd.DataFrame()

            # 计算统计信息
            stats_df = calculate_tissue_statistics(ct_array, tissue_region, voxel_volume)

            print(f"分析完成: 椎体{vertebra_name} - 组织类型数量={len(stats_df.columns)}")
            return stats_df

        except Exception as e:
            print(f"分析椎体 {vertebra_name} 时出错: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    def batch_analyze_vertebra(self, subject_ids: List[str], vertebra_names: List[str], range_mm: int, progress=gr.Progress()):
        """批量分析多个椎体的组织信息"""
        results = {}
        total_tasks = len(subject_ids) * len(vertebra_names)
        completed_tasks = 0

        for subject_id in subject_ids:
            results[subject_id] = {}
            for vertebra_name in vertebra_names:
                progress(completed_tasks / total_tasks, f"分析 {subject_id} 的 {vertebra_name}...")

                stats_df = self.analyze_vertebra(subject_id, vertebra_name, range_mm)
                results[subject_id][vertebra_name] = stats_df
                completed_tasks += 1

        # 保存结果
        return self.save_batch_results(results, vertebra_names, range_mm)


    def save_batch_results(self, results: Dict, vertebra_names: List[str], range_mm: int):
        """保存批量分析结果"""
        all_results = []
        save_success_count = 0

        for subject_id, subject_results in results.items():
            output_dir = Path(self.base_path) / "tissues_statistic" / subject_id
            output_dir.mkdir(parents=True, exist_ok=True)

            for vertebra_name, stats_df in subject_results.items():
                if not stats_df.empty:
                    output_path = output_dir / f"{subject_id}_{vertebra_name}_{range_mm}mm.csv"
                    stats_df.to_csv(output_path, index=True)
                    save_success_count += 1

                    # 为显示准备数据
                    for tissue in stats_df.columns:
                        for stat_name in stats_df.index:
                            all_results.append({
                                'Subject_ID': subject_id,
                                'Vertebra': vertebra_name,
                                'Tissue': tissue,
                                'Statistic': stat_name,
                                'Value': stats_df.loc[stat_name, tissue],
                                'Range_mm': range_mm
                            })

        result_df = pd.DataFrame(all_results)

        if result_df.empty:
            return "没有成功分析的数据。", pd.DataFrame()

        summary = f"分析完成！\n"
        summary += f"成功的分析：{save_success_count}/{len(results) * len(vertebra_names)} \n"
        summary += f"已保存到相应的CSV文件中。\n"

        return summary, result_df

def create_interface():
    """创建Gradio界面"""
    analyzer = TissueAnalyzerGUI()

    with gr.Blocks(title="身体成分分析") as interface:
        gr.Markdown("""
        # CT图像身体组织分析 v1.0
        """)

        with gr.Tab("图像分析"):
            with gr.Row():
                with gr.Column(scale=1):
                    # CT图像选择
                    subject_selector = gr.Dropdown(
                        choices=analyzer.available_subjects,
                        value=analyzer.available_subjects[0] if analyzer.available_subjects else None,
                        label="按ID选择CT图像",
                        info=" "
                    )

                    refresh_btn = gr.Button("刷新图像列表")

                    # 椎体选择 (T1-T12)
                    vertebra_selector = gr.CheckboxGroup(
                        choices=[f"T{i}" for i in range(1, 13)],
                        label="选择椎体 (T1-T12)",
                        info="可以选择多个椎体进行分析"
                    )

                    # 分析范围选择
                    range_slider = gr.Slider(
                        minimum=1,
                        maximum=50,
                        value=10,
                        step=1,
                        label="分析范围 (mm)",
                        info="以椎体中心层面为中心的提取范围"
                    )

                    # 分析按钮
                    analyze_btn = gr.Button("开始分析", variant="primary")


                with gr.Column(scale=2):
                    # 显示图像
                    display_image = gr.Image(
                        label="椎体中心层面示意图",
                        type="numpy"
                    )

                    # 统计结果显示
                    stats_display = gr.Dataframe(
                        label="组织统计信息",
                        headers=["锥体", "统计指标", "肌肉-MUSCLE", "骨骼-BONE", "皮下脂肪-SAT", "腹腔脂肪-VAT", "肌间脂肪-IMAT", "纵隔脂肪-PAT", "心包脂肪-EAT"],
                        datatype=["str"] + ["number"] * 8,
                        interactive=False
                    )

        with gr.Tab("批量分析"):
            with gr.Row():
                with gr.Column():
                    # CT图像选择区域
                    with gr.Group():
                        gr.Markdown("""### &nbsp;&nbsp;按ID选择CT图像""")
                        batch_subjects = gr.Dropdown(
                            choices=analyzer.available_subjects,
                            value=analyzer.available_subjects if len(analyzer.available_subjects) <= 5 else analyzer.available_subjects[:5],
                            multiselect=True,
                            label=" ",
                            info=" "
                        )

                        # 全选按钮组
                        with gr.Row():
                            select_all_btn = gr.Button("全选", size="sm")
                            clear_all_btn = gr.Button("清空", size="sm")
                            invert_btn = gr.Button("反选", size="sm")

                    batch_vertebrae = gr.CheckboxGroup(
                        choices=[f"T{i}" for i in range(1, 13)],
                        label="选择椎体 (T1-T12)",
                        info="可以选择多个椎体"
                    )

                    batch_range = gr.Slider(
                        minimum=1,
                        maximum=50,
                        value=10,
                        step=1,
                        label="分析范围 (mm)"
                    )

                    batch_analyze_btn = gr.Button("批量分析", variant="primary")

                    # 进度和结果
                    batch_summary = gr.Textbox(
                        label="分析结果摘要",
                        lines=5,
                        interactive=False
                    )

                with gr.Column():
                    # 批量结果显示
                    batch_results = gr.Dataframe(
                        label="详细统计结果",
                        interactive=False,
                        wrap=True
                    )

        with gr.Tab("数据管理"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### 已保存的分析结果")
                    saved_results_btn = gr.Button("查看已保存的结果")
                    saved_results_list = gr.Textbox(
                        label="已保存的CSV文件",
                        lines=10,
                        interactive=False
                    )

                with gr.Column():
                    gr.Markdown("### 系统信息")
                    system_info = gr.Textbox(
                        label="系统状态",
                        value=f"可用CT图像数量: {len(analyzer.available_subjects)}\n"
                              f"支持的椎体类型: T1-T12\n"
                              f"组织类型: {', '.join(TISSUE_LABEL.keys())}",
                        lines=5,
                        interactive=False
                    )

                    refresh_data_btn = gr.Button("重新加载数据")

        # 事件处理函数
        def on_refresh_subject_list():
            analyzer.refresh_subject_list()
            # 返回具体的数据值，而不是Gradio组件对象
            return (
                analyzer.available_subjects,  # subject_selector的choices
                analyzer.available_subjects,  # batch_subjects的choices
                f"可用CT图像数量: {len(analyzer.available_subjects)}\n支持椎体类型: T1-T12\n组织类型: {', '.join(TISSUE_LABEL.keys())}"  # system_info的value
            )

        def on_subject_change(subject_id):
            if subject_id and subject_id in analyzer.available_subjects:
                # 当CT图像选择改变时，清除当前显示并更新椎体选择
                return None, []  # display_image=None, vertebra_selector=[]
            return None, []  # 默认情况下都返回空值

        def on_analyze_single(subject_id, vertebra_names, range_mm):
            if not subject_id or not vertebra_names:
                return None, pd.DataFrame()

            results = []
            for vertebra_name in vertebra_names:
                stats_df = analyzer.analyze_vertebra(subject_id, vertebra_name, range_mm)
                if not stats_df.empty:
                    # 转换格式用于显示
                    stats_df.columns.name = "组织类型"
                    stats_df.index.name = "统计指标"
                    results.append(stats_df)

            if results:
                combined_stats = pd.concat(results, keys=vertebra_names, names=['椎体'])
                combined_stats = combined_stats.reset_index()

                # 获取显示图像 (显示第一个椎体)
                display_img = analyzer.get_vertebra_display_image(subject_id, vertebra_names[0])

                return display_img, combined_stats
            else:
                return None, pd.DataFrame()

        def on_batch_analyze(subject_ids, vertebra_names, range_mm):
            if not subject_ids or not vertebra_names:
                return "请选择CT图像和椎体", pd.DataFrame()

            summary, results_df = analyzer.batch_analyze_vertebra(subject_ids, vertebra_names, range_mm)
            return summary, results_df

        def on_refresh_saved_results():
            saved_files = []
            tissue_statistic_dir = Path(analyzer.base_path) / "tissues_statistic"

            if tissue_statistic_dir.exists():
                for subject_dir in tissue_statistic_dir.iterdir():
                    if subject_dir.is_dir():
                        for csv_file in subject_dir.glob("*.csv"):
                            saved_files.append(str(csv_file.relative_to(analyzer.base_path)))

            return "\n".join(saved_files) if saved_files else "暂无保存的分析结果"

        def on_select_all_subjects():
            """全选CT图像"""
            return analyzer.available_subjects

        def on_clear_all_subjects():
            """清空所有选择的CT图像"""
            return []

        def on_invert_selection(current_selection):
            """反选CT图像"""
            if not current_selection:
                return analyzer.available_subjects  # 如果没有选择，就选全部

            # 反选逻辑：已选变未选，未选变已选
            current_set = set(current_selection)
            all_subjects = set(analyzer.available_subjects)
            inverted = list(all_subjects - current_set)

            return inverted if inverted else []

        # 绑定事件
        refresh_btn.click(on_refresh_subject_list,
                         outputs=[subject_selector, batch_subjects, system_info])

        # 全选功能事件绑定
        select_all_btn.click(on_select_all_subjects,
                           outputs=[batch_subjects])

        clear_all_btn.click(on_clear_all_subjects,
                          outputs=[batch_subjects])

        invert_btn.click(on_invert_selection,
                       inputs=[batch_subjects],
                       outputs=[batch_subjects])

        subject_selector.change(on_subject_change,
                               inputs=[subject_selector],
                               outputs=[display_image, vertebra_selector])

        analyze_btn.click(on_analyze_single,
                         inputs=[subject_selector, vertebra_selector, range_slider],
                         outputs=[display_image, stats_display])

        batch_analyze_btn.click(on_batch_analyze,
                               inputs=[batch_subjects, batch_vertebrae, batch_range],
                               outputs=[batch_summary, batch_results])

        saved_results_btn.click(on_refresh_saved_results,
                               outputs=[saved_results_list])

        refresh_data_btn.click(on_refresh_subject_list,
                              outputs=[subject_selector, batch_subjects, system_info])

    return interface

if __name__ == "__main__":
    # 创建并启动界面
    interface = create_interface()
    interface.launch(
        server_name="localhost",
        server_port=7880,  # 改为不同的端口避免冲突
        share=True,
        inbrowser=True
    )