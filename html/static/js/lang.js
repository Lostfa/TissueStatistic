/**
 * 国际化 (i18n) 模块
 * 支持中文(zh)和英文(en)，默认英文。
 * 控制台输出始终使用英文。
 */

// 当前语言，默认英文
let currentLang = localStorage.getItem('ts_lang') || 'en';

// 翻译字典：涵盖页面中所有中文字符串
const I18N = {
  // ===== 页面标题和头部 =====
  'app.title':         { zh: 'CT 组织成分统计分析平台', en: 'CT Tissue Composition Analysis Platform' },
  'app.title.alt':     { zh: 'TissueStatistic - CT组织成分统计分析平台', en: 'TissueStatistic - CT Tissue Composition Analysis Platform' },
  'app.subtitle':      { zh: 'TissueStatistic — 从CT图像到统计结果的一站式分析工具', en: 'TissueStatistic — One-stop analysis from CT images to statistical results' },
  'app.workingDir':    { zh: '工作根目录（如 D:/research/study1）', en: 'Working directory (e.g. D:/research/study1)' },
  'header.workingDir': { zh: '当前工作目录：', en: 'Current Working Directory:' },
  'header.openExplorer': { zh: '📂 在文件管理器中打开', en: '📂 Open in File Explorer' },

  // ===== 语言切换 =====
  'lang.zh': { zh: '中文', en: '中文' },

  // ===== 步骤条 =====
  'step1.name': { zh: '数据预处理', en: 'Preprocessing' },
  'step1.desc': { zh: 'DICOM/NIfTI标准化', en: 'DICOM/NIfTI Standardization' },
  'step2.name': { zh: 'BOA 分割', en: 'BOA Segmentation' },
  'step2.desc': { zh: 'CT图像组织分割', en: 'CT Tissue Segmentation' },
  'step3.name': { zh: '统计分析', en: 'Statistical Analysis' },
  'step3.desc': { zh: '组织成分计算', en: 'Tissue Composition' },
  'step4.name': { zh: '数据导出', en: 'Data Export' },
  'step4.desc': { zh: 'CSV表格合并与下载', en: 'CSV Merge & Download' },

  // ===== 步骤1 =====
  'step1.card1.title':     { zh: '文件路径配置', en: 'File Path Config' },
  'step1.card2.title':     { zh: '图像预处理', en: 'Image Preprocessing' },
  'step1.card2.subtitle':  { zh: '配置CT图像的标准化处理参数', en: 'Configure CT image normalization parameters' },
  'step1.inputType':       { zh: '输入类型', en: 'Input Type' },
  'step1.dicomDir':        { zh: 'DICOM目录', en: 'DICOM Directory' },
  'step1.niftiFile':       { zh: 'NIfTI文件', en: 'NIfTI Files' },
  'step1.inputPath':       { zh: '输入目录路径', en: 'Input Directory Path' },
  'step1.inputPathPH':     { zh: '包含DICOM序列或NIfTI文件的目录', en: 'Directory with DICOM series or NIfTI files' },
  'step1.workDir':         { zh: '工作根目录', en: 'Working Root Directory' },
  'step1.workDirPH':       { zh: '将在此目录下创建ct_image/等子目录', en: 'Subdirs ct_image/ etc. created here' },
  'step1.workDirExtra':    { zh: '这是项目根目录，ct_image/、boa_label/等将创建在此目录下', en: 'Root directory; ct_image/, boa_label/ etc. created under it' },
  'step1.browseHint':      { zh: '点击"浏览"选择文件夹，路径将自动填入', en: 'Click Browse to select a folder' },
  'step1.scan':            { zh: '🔍 扫描输入数据', en: '🔍 Scan Input Data' },
  'step1.patientList':     { zh: '检测到的序列列表：', en: 'Detected Series:' },
  'step1.emptyScan':       { zh: '请先输入目录路径并点击"扫描输入数据"', en: 'Enter directory path and click Scan Input Data' },
  'step1.start':           { zh: '▶ 开始预处理', en: '▶ Start Preprocessing' },
  'step1.resampleConfig':  { zh: '重采样参数配置', en: 'Resampling Config' },
  'step1.sliceThickness':  { zh: '层厚设置', en: 'Slice Thickness' },
  'step1.sliceHint':       { zh: '（范围 0.5 ~ 2.5，默认 1.0）', en: '(Range 0.5 ~ 2.5, default 1.0)' },
  'step1.sliceWarning':    { zh: '※ 如需进行组织成分分析，图像层厚需要设置为1mm', en: '* For tissue composition analysis, slice thickness must be 1mm' },
  'step1.interpolation':   { zh: '图像插值方法', en: 'Interpolation Method' },
  'step1.interpHint':      { zh: '重采样时使用的插值算法，默认 B 样条插值效果最好', en: 'Interpolation algorithm for resampling; B-spline gives best results' },
  'step1.huRange':         { zh: 'HU值范围', en: 'HU Value Range' },
  'step1.huMin':           { zh: '最小值', en: 'Min' },
  'step1.huMax':           { zh: '最大值', en: 'Max' },
  'step1.huHint':          { zh: 'CT值超出此范围的体素将被裁剪，默认范围 [-1000, 3000] HU', en: 'Voxels outside this HU range will be clipped; default [-1000, 3000] HU' },
  'step1.gaussianEnable':  { zh: '启用高斯模糊', en: 'Enable Gaussian Blur' },
  'step1.sigmaParam':      { zh: 'Sigma 参数', en: 'Sigma Parameter' },
  'step1.sigmaHint':       { zh: '（范围 0.5 ~ 2.5，默认 1.5）', en: '(Range 0.5 ~ 2.5, default 1.5)' },
  'step1.gaussianHint':    { zh: '参考 hjf2_process.py 中的 sitk.DiscreteGaussian 方法，对重采样后的图像进行三维高斯平滑', en: 'Applies 3D Gaussian smoothing on resampled image via sitk.DiscreteGaussian' },
  'step1.outputNaming':    { zh: '输出文件命名方式', en: 'Output File Naming' },
  'step1.naming.original': { zh: '原始文件/文件夹名称', en: 'Original File/Folder Name' },
  'step1.naming.seriesId': { zh: '序列ID', en: 'Series ID' },
  'step1.namingHint':      { zh: '"原始名称"使用DICOM文件夹名或NIfTI文件名；"序列ID"使用DICOM元数据中的PatientID或扫描生成的唯一标识', en: '"Original Name" uses DICOM folder or NIfTI filename; "Series ID" uses PatientID from DICOM metadata' },

  // ===== 步骤2 =====
  'step2.card1.title':     { zh: 'BOA 环境检测', en: 'BOA Environment Check' },
  'step2.card1.subtitle':  { zh: '检测 conda 环境和 BOA 命令行工具是否就绪', en: 'Check conda environment and BOA CLI' },
  'step2.workDir':         { zh: '工作根目录', en: 'Working Root Directory' },
  'step2.workDirPH':       { zh: '包含ct_image/的根目录', en: 'Root dir containing ct_image/' },
  'step2.checkEnv':        { zh: '🔧 检测运行环境', en: '🔧 Check Environment' },
  'step2.card2.title':     { zh: 'BOA 分割配置', en: 'BOA Segmentation Config' },
  'step2.card2.subtitle':  { zh: '在 conda 环境中运行 BOA 命令行工具进行CT图像组织分割', en: 'Run BOA CLI in conda for CT tissue segmentation' },
  'step2.models':          { zh: '分割模型', en: 'Segmentation Models' },
  'step2.models.hint':    { zh: 'TotalSegmentator 和 Body and Organ Analysis 为实际可用的分割模型；Lung anatomy 和 Pulmonary lesions 为规划中的功能',
                            en: 'TotalSegmentator and Body and Organ Analysis are available models; Lung anatomy and Pulmonary lesions are planned features' },
  'step2.selectPatient':   { zh: '选择要分割的序列：', en: 'Select series to segment:' },
  'step2.empty':           { zh: '请确认 ct_image/ 目录中有预处理完成的图像，然后点击刷新', en: 'Verify preprocessed images in ct_image/, then refresh' },
  'step2.refresh':         { zh: '🔄 刷新序列列表', en: '🔄 Refresh Series List' },
  'step2.start':           { zh: '▶ 启动 BOA 分割', en: '▶ Start BOA Segmentation' },
  'step2.timeNote':        { zh: '⏱ 单个图像序列处理时间约数分钟至数十分钟，取决于图像层数和GPU', en: '⏱ Minutes to tens of minutes per series, depending on slices and GPU' },

  // ===== 步骤3 =====
  'step3.card1.title':     { zh: '文件路径配置', en: 'File Path Config' },
  'step3.card2.title':     { zh: '统计分析配置', en: 'Analysis Config' },
  'step3.card3.title':     { zh: '组织阈值设定', en: 'Tissue Threshold Config' },
  'step3.card3.subtitle':  { zh: '自定义脂肪和肌肉的CT值范围，重新生成组织标签（tissues.nii.gz）', en: 'Customize fat/muscle CT value ranges to regenerate tissue labels (tissues.nii.gz)' },
  'step3.card3.defaults':  { zh: '默认阈值：脂肪 -190 ~ -30 HU，肌肉 -29 ~ 150 HU', en: 'Default: Fat -190 ~ -30 HU, Muscle -29 ~ 150 HU' },
  'step3.thresholdEnable': { zh: '更改组织阈值设定', en: 'Modify custom thresholds' },
  'step3.fatRange':        { zh: '脂肪 CT 值范围 (HU)', en: 'Fat CT Range (HU)' },
  'step3.muscleRange':     { zh: '肌肉 CT 值范围 (HU)', en: 'Muscle CT Range (HU)' },
  'step3.thresholdHint':   { zh: '勾选后，系统将先使用自定义阈值重新生成组织标签，再执行统计分析', en: 'When checked, system regenerates tissue labels with custom thresholds, then runs analysis' },
  'step3.modeB':           { zh: '模式B — 单次检查分析', en: 'Mode B — Single Exam' },
  'step3.workers':         { zh: '并行处理的序列数', en: 'Parallel Workers' },
  'step3.includeAll':      { zh: '全图分析 (ALL)', en: 'Whole Image (ALL)' },
  'step3.singleVert':      { zh: '目标椎体', en: 'Target Vertebra' },
  'step3.range':           { zh: '分析范围（mm）', en: 'Range (mm)' },
  'step3.cervical':        { zh: '颈椎 C', en: 'Cervical (C)' },
  'step3.thoracic':        { zh: '胸椎 T', en: 'Thoracic (T)' },
  'step3.lumbar':          { zh: '腰椎 L', en: 'Lumbar (L)' },
  'step3.customRange':     { zh: '自定义范围：', en: 'Custom Range:' },
  'step3.startB':          { zh: '▶ 启动并行分析', en: '▶ Start Parallel Analysis' },
  'step3.imageDir':        { zh: '图像目录', en: 'Image Directory' },
  'step3.labelDir':        { zh: '标签目录', en: 'Label Directory' },
  'step3.scanNifti':       { zh: '🔍 扫描NIFTI文件', en: '🔍 Scan NIfTI Files' },

  // ===== 步骤4 =====
  'step4.card1.title':     { zh: 'CSV数据合并导出', en: 'CSV Merge & Export' },
  'step4.card1.subtitle':  { zh: '选择需要合并的分析结果类型、组织成分和统计指标，生成综合数据表', en: 'Select analysis types, tissues and metrics to generate a table' },
  'step4.basePath':        { zh: '数据根目录', en: 'Data Root Directory' },
  'step4.basePathPH':      { zh: '包含tissue_statistic/的根目录', en: 'Root with tissue_statistic/' },
  'step4.scan':            { zh: '🔍 扫描CSV数据', en: '🔍 Scan CSV Data' },
  'step4.card2.title':     { zh: '扫描范围选择', en: 'Scan Range Selection' },
  'step4.card3.title':     { zh: '组织成分选择', en: 'Tissue Selection' },
  'step4.card4.title':     { zh: '统计学指标选择', en: 'Statistical Metrics' },
  'step4.required':        { zh: '（至少选一项）', en: '(Select at least one)' },
  'step4.generate':        { zh: '▶ 生成合并表格', en: '▶ Generate Table' },
  'step4.download':        { zh: '💾 下载 CSV文件', en: '💾 Download CSV' },
  'step4.preview':         { zh: '数据预览', en: 'Data Preview' },
  'step4.cervical':        { zh: '颈椎 C', en: 'Cervical (C)' },
  'step4.thoracic':        { zh: '胸椎 T', en: 'Thoracic (T)' },
  'step4.lumbar':          { zh: '腰椎 L', en: 'Lumbar (L)' },

  // ===== 导航 =====
  'nav.prev':    { zh: '◀ 上一步', en: '◀ Previous' },
  'nav.next':    { zh: '下一步 ▶', en: 'Next ▶' },
  'nav.step':    { zh: '步骤', en: 'Step' },
  'nav.stepOf':  { zh: '步骤 1 / 4', en: 'Step 1 / 4' },

  // ===== 控制台 =====
  'console.title':   { zh: '📟 控制台', en: '📟 Console' },
  'console.clear':   { zh: '清空', en: 'Clear' },
  'console.ready':   { zh: '等待任务开始...', en: 'Waiting for task...' },
  'console.status':  { zh: '就绪', en: 'Ready' },
  'console.progress':{ zh: '准备就绪', en: 'Ready' },
  'console.cleared': { zh: '已清空', en: 'Cleared' },

  // ===== 通用按钮/标签 =====
  'btn.cancel':   { zh: '取消', en: 'Cancel' },
  'btn.browse':   { zh: '📂 浏览...', en: '📂 Browse...' },
  'btn.selectAll':{ zh: '全选', en: 'Select All' },
  'btn.deselect': { zh: '取消全选', en: 'Clear All' },

  // ===== 页脚 =====
  'footer': { zh: 'TissueStatistic — CT组织成分统计分析平台 v1.0  |  基于 BOA (Body and Organ Analysis) + TotalSegmentator  |  用于医学研究目的',
              en: 'TissueStatistic — CT Tissue Analysis Platform v1.0  |  BOA + TotalSegmentator  |  For Medical Research' },

  // ===== JS动态文本 =====
  'js.scanFound':     { zh: '检测到 {n} 个序列', en: 'Found {n} series' },
  'js.scanEmpty':     { zh: '未检测到序列', en: 'No series detected' },
  'js.scanFail':      { zh: '扫描失败', en: 'Scan failed' },
  'js.scanFailMsg':   { zh: '扫描失败: {msg}', en: 'Scan failed: {msg}' },
  'js.dirNotFound':   { zh: '目录不存在', en: 'Directory not found' },
  'js.selectSeries':  { zh: '请至少选择一个序列', en: 'Please select at least one series' },
  'js.startFail':     { zh: '启动失败', en: 'Start failed' },
  'js.startFailMsg':  { zh: '启动失败: {msg}', en: 'Start failed: {msg}' },
  'js.processing':    { zh: '正在处理: {pid}', en: 'Processing: {pid}' },
  'js.done':          { zh: '处理完成: {pid}', en: 'Done: {pid}' },
  'js.fail':          { zh: '处理失败: {pid}', en: 'Failed: {pid}' },
  'js.preprocessDone':{ zh: '预处理完成：成功 {s}，失败 {f}', en: 'Preprocessing done: {s} OK, {f} failed' },
  'js.segDone':       { zh: '分割完成：成功 {s}，失败 {f}', en: 'Segmentation done: {s} OK, {f} failed' },
  'js.analysisDone':  { zh: '分析完成：{n}个序列，成功{s}项', en: 'Analysis: {n} series, {s} OK' },
  'js.mergeDone':     { zh: '合并完成：处理了{t}个目标', en: 'Merge done: {t} targets' },
  'js.totalSeries':   { zh: '共 {n} 个序列', en: 'Total: {n} series' },
  'js.allDone':       { zh: '全部分割完成！可手动进入下一步', en: 'All done! Use buttons to proceed.' },
  'js.statsDone':     { zh: '统计分析完成！可手动进入下一步导出结果', en: 'Analysis done! Proceed to export.' },
  'js.mergeDone2':    { zh: '合并完成！可手动进入下一步导出结果', en: 'Merge done! Proceed to export.' },
  'js.preprocessDone2':{ zh: '预处理完成！可手动进入下一步', en: 'Preprocessing done! Proceed to next step.' },
  'js.noWorkingDir':  { zh: '请先设置数据根目录', en: 'Please set data root directory first' },
  'js.noWorkingDirStep3': { zh: '请先在顶部栏设置工作目录', en: 'Please set working directory in the top bar first' },
  'js.noInputPath':   { zh: '请输入输入目录路径', en: 'Please enter input directory path' },
  'js.noInputOrWorkDir': { zh: '请输入输入路径和工作目录', en: 'Please enter input and working directory' },
  'js.selectScanType':{ zh: '请至少选择一种扫描类型', en: 'Please select at least one scan type' },
  'js.selectTissue':  { zh: '请至少选择一种组织成分', en: 'Please select at least one tissue type' },
  'js.selectMetric':  { zh: '请至少选择一种统计指标', en: 'Please select at least one statistical metric' },
  'js.selectVertRange': { zh: '选择目标椎体分析时必须同时选择分析范围', en: 'When selecting vertebra analysis, you must also select a range' },
  'js.tableGenerated':{ zh: '表格生成完成！', en: 'Table generated!' },
  'js.generateFail':  { zh: '生成失败: {msg}', en: 'Generation failed: {msg}' },
  'js.scanCSVHint':   { zh: '请先点击"扫描CSV数据"以加载可用选项', en: 'Click "Scan CSV Data" to load available options' },
  'js.noVertData':    { zh: '未检测到椎体分析数据', en: 'No vertebra analysis data detected' },
  'js.noRangeData':   { zh: '未检测到范围数据', en: 'No range data detected' },
  'js.scanNoData':    { zh: '⚠️ 未检测到数据，请先完成预处理和BOA分割', en: '⚠️ No data detected. Complete preprocessing and BOA segmentation first' },
  'js.scanResult':    { zh: '✅ 图像目录：{ct} 个NIfTI文件 &nbsp;|&nbsp; 标签目录：{lb} 个序列', en: '✅ Image dir: {ct} NIfTI files &nbsp;|&nbsp; Label dir: {lb} series' },
  'js.scanCSVFound':  { zh: '✅ 发现 {n} 个序列，共 {c} 个 CSV 文件', en: '✅ Found {n} series, {c} CSV files total' },
  'js.scanCSVEmpty':  { zh: '⚠️ 未在 tissue_statistic/ 目录下发现任何 CSV 数据，请先完成统计分析', en: '⚠️ No CSV data found in tissue_statistic/. Complete statistical analysis first' },
};

/**
 * 获取翻译文本
 * @param {string} key - 翻译键
 * @param {object} params - 插值参数，替换 {key} 占位符
 * @returns {string} 翻译后的文本
 */
function t(key, params) {
  const entry = I18N[key];
  let text = entry ? (entry[currentLang] || entry['en']) : key;
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(`{${k}}`, v);
    });
  }
  return text;
}

/**
 * 应用语言到整个页面。
 * 策略：
 * 1. 遍历所有带 data-i18n 的元素（精确键翻译）
 * 2. 遍历所有文本节点，通过中→英反向字典匹配翻译
 * 3. 更新 input/textarea 的 placeholder 属性
 */
function applyLanguage() {
  // ---- 第一步：构建双向反向查找字典 ----
  const normKey = (s) => s.replace(/ /g, ' ').replace(/\s+/g, ' ').trim();
  const reverseMap = {};  // normalized text → i18n key
  Object.entries(I18N).forEach(([key, entry]) => {
    if (entry.zh && entry.zh.trim()) reverseMap[normKey(entry.zh)] = key;
    if (entry.en && entry.en.trim()) reverseMap[normKey(entry.en)] = key;
  });

  // ---- 第二步：精确键翻译（data-i18n 属性） ----
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const text = t(key);
    if (text) {
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        el.placeholder = text;
      } else {
        el.textContent = text;
      }
    }
  });

  // ---- 第三步：遍历所有文本节点，反向匹配翻译 ----
  const walker = document.createTreeWalker(
    document.body,
    NodeFilter.SHOW_TEXT,
    {
      acceptNode: function(node) {
        // 跳过脚本、样式、空白文本、控制台日志（始终英文）
        const parent = node.parentElement;
        if (!parent) return NodeFilter.FILTER_REJECT;
        if (parent.tagName === 'SCRIPT' || parent.tagName === 'STYLE') return NodeFilter.FILTER_REJECT;
        if (parent.closest('#consoleLog')) return NodeFilter.FILTER_REJECT;
        if (parent.closest('#consoleStatus')) return NodeFilter.FILTER_REJECT;
        if (parent.closest('#consoleProgressText')) return NodeFilter.FILTER_REJECT;
        // 跳过步骤4的组织/指标选择区（动态渲染，保持原有中英文格式）
        if (parent.closest('#exportTissueGrid')) return NodeFilter.FILTER_REJECT;
        if (parent.closest('#exportMetricGrid')) return NodeFilter.FILTER_REJECT;
        // 跳过已有 data-i18n 的元素（已在上一步处理）
        if (parent.closest('[data-i18n]') && parent.closest('[data-i18n]') === parent) return NodeFilter.FILTER_REJECT;
        const text = node.textContent.trim();
        if (!text || text.length < 2) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    }
  );

  const translatedNodes = new Set();
  const norm = (s) => s.replace(/ /g, ' ').replace(/\s+/g, ' ').trim();

  while (walker.nextNode()) {
    const node = walker.currentNode;
    const rawText = node.textContent;
    const trimmed = norm(rawText);
    if (!trimmed || translatedNodes.has(node)) continue;

    // 精确匹配（使用标准化后的文本）
    const normText = norm(rawText);
    if (reverseMap[normText]) {
      const key = reverseMap[normText];
      const entry = I18N[key];
      if (entry && entry[currentLang] && normKey(entry[currentLang]) !== normText) {
        node.textContent = entry[currentLang];
        translatedNodes.add(node);
        continue;
      }
    }

    // 部分匹配：对文本中的片段逐一替换
    let changed = false;
    let result = rawText;
    for (const [textKey, key] of Object.entries(reverseMap)) {
      if (result.includes(textKey)) {
        const entry = I18N[key];
        if (entry && entry[currentLang] && entry[currentLang] !== textKey) {
          result = result.split(textKey).join(entry[currentLang]);
          changed = true;
        }
      }
    }
    if (changed && result !== rawText) {
      node.textContent = result;
      translatedNodes.add(node);
    }
  }

  // ---- 第四步：更新 placeholder 属性 ----
  document.querySelectorAll('input[placeholder], textarea[placeholder]').forEach(el => {
    const ph = normKey(el.getAttribute('placeholder'));
    if (ph && reverseMap[ph]) {
      const key = reverseMap[ph];
      const entry = I18N[key];
      if (entry && entry[currentLang] && normKey(entry[currentLang]) !== ph) {
        el.placeholder = entry[currentLang];
      }
    }
  });

  // ---- 第五步：更新语言按钮状态 ----
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.lang === currentLang);
  });

  // ---- 第六步：更新动态元素 ----
  updateStepIndicators();

  localStorage.setItem('ts_lang', currentLang);
}

/**
 * 切换语言
 * @param {string} lang - 'zh' 或 'en'
 */
function switchLanguage(lang) {
  if (lang === currentLang) return;
  currentLang = lang;
  // 更新按钮激活状态
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.lang === currentLang);
  });
  localStorage.setItem('ts_lang', currentLang);
  // 仅更新静态翻译文本，动态内容保持原有逻辑
  applyLanguage();
}

// 页面加载时应用语言
document.addEventListener('DOMContentLoaded', () => {
  // applyLanguage 会在 initWizard 之前由主控制器调用
  setTimeout(applyLanguage, 50);
});
