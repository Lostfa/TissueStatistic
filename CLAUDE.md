# TissueStatistic — CT组织成分统计分析平台

从CT图像中分割软组织成分并生成统计结果的综合项目。

## 项目结构

```
├── boa/                        # BOA分割工具文档（代码已移除，仅保留README）
│   ├── README.md
│   └── documentation/
│       ├── command_line.md
│       └── environment_variables.md
├── pipline/                    # 管线脚本
│   ├── environment.yml         # Conda环境配置
│   ├── boa_bat.py              # BOA批处理生成器
│   ├── main_statistic_parallel.py  # 并行统计分析入口
│   ├── preprocess/             # 预处理脚本
│   │   ├── dicom_process.py
│   │   ├── hjf2_process.py
│   │   └── wq2_process.py
│   ├── statistic/
│   │   └── tissue_statistic.py # 核心分析函数库
│   └── utils/
│       ├── image_io.py
│       └── image_process.py
└── html/                       # Web应用（FastAPI + 原生JS）
    ├── app.py                  # 应用入口
    ├── config.py               # 配置
    ├── api/                    # REST API端点
    │   ├── analysis.py         # 统计分析API
    │   ├── boa.py              # BOA分割API
    │   ├── merge.py            # CSV合并导出API
    │   ├── preprocessing.py    # 预处理API
    │   ├── system.py           # 系统工具API
    │   └── tasks.py            # 任务管理API
    ├── wrappers/               # Python包装器（封装pipline调用）
    │   ├── analysis.py         # 统计分析包装器
    │   ├── boa.py              # BOA分割包装器
    │   ├── merge.py            # 结果合并包装器
    │   └── preprocess.py       # 预处理包装器
    ├── tasks/                  # 任务管理器
    │   └── manager.py
    ├── templates/
    │   └── index.html          # 前端主页面
    └── static/
        ├── css/style.css
        └── js/
            ├── api.js          # API通信层
            ├── app.js          # 业务逻辑控制器
            ├── wizard.js       # 步骤导航与状态管理
            └── lang.js         # 国际化（中/英）
```

## 项目流程

### 步骤1：环境搭建
- 使用 `pipline/environment.yml` 创建 conda 虚拟环境 `boa`
- 环境包含 BOA 分割工具所需的全部依赖

### 步骤2：CT图像预处理
- 使用 `pipline/preprocess/` 中的脚本对原始CT图像进行标准化
- 支持 **DICOM** 和 **NIfTI** 两种输入格式
- 处理内容包括：HU值裁剪、重采样、可选高斯模糊
- 结果输出到 `ct_image/` 文件夹（NIfTI格式）

### 步骤3：BOA组织分割
- 使用 `pipline/boa_bat.py` 生成批处理文件并执行
- 基于 TotalSegmentator 和 Body and Organ Analysis 模型
- 输出椎体标签（total）、BCA标签（bca）、组织标签（tissues）
- 结果保存在 `boa_label/{患者ID}/` 文件夹

### 步骤4：统计分析
- 使用 `pipline/main_statistic_parallel.py` 并行处理所有患者
- 支持两种分析类型：
  - **全图分析 (ALL)**：分析全部层面的组织成分
  - **目标椎体 + 范围**：以指定椎体（C2-L5共23个）为中心，分析指定毫米范围内的组织成分
- 分析的组织类型：MUSCLE、BONE、SAT、VAT、IMAT、PAT、EAT（共7种）
- 统计指标：volume、max/min/mean/std/median/q1/q3 HU值（共8项）
- 结果保存在 `tissue_statistic/{患者ID}/` 文件夹

### 步骤5：数据导出
- 通过 Web 应用（`html/`）在线选择和合并数据
- 命令行也可直接使用 `main_statistic_parallel.py`

## Web应用（html/）

启动方式：
python -m uvicorn app:app --host 127.0.0.1 --port 8000

访问 `http://localhost:8000` 使用完整的4步向导界面：
1. **数据预处理** — 上传DICOM/NIfTI，配置HU范围和高斯模糊
2. **BOA分割** — 环境检测、模型选择、批量分割
3. **统计分析** — 选择目标椎体（C/T/L分组）和分析范围（含自定义1-30mm滑块）
4. **数据导出** — 选择组织成分和统计指标，生成合并CSV并下载

右侧控制台实时显示任务进度和日志。

## 技术要点

- `pipline/statistic/tissue_statistic.py` 是核心函数库，提供椎体定位、区域提取、统计计算等功能
- Web后端通过 `wrappers/` 封装 `pipline/` 的导入调用，不修改原始管线代码
- 统计分析使用 `ProcessPoolExecutor` 多进程并行，每个患者数据只加载一次
- Windows 上多进程需 `spawn` 上下文和 `__main__` 保护
- 数据分析结果按 `{患者ID}_{椎体标识}_{范围}mm.csv` 命名规则存储

## 注意事项

- `boa/` 中的代码文件已被删除，仅保留文档（README.md 和 documentation/）
- 需要阅读 `boa/` 中的 md 文件了解 BOA 工具的使用方法
- 项目不支持椎体间范围分析（已移除），仅支持全图分析和单椎体+范围分析
