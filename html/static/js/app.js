/**
 * 主应用控制器
 * 连接UI事件与API调用，管理4步工作流的业务逻辑。
 */

document.addEventListener('DOMContentLoaded', () => {
  initWizard();
  loadAnalysisDefaults();
  initStep1();
  initStep2();
  initStep3();
  initStep4();
});

// ===== 加载默认配置 =====

async function loadAnalysisDefaults() {
  try {
    const defaults = await apiGetAnalysisDefaults();
    applyDefaults(defaults);
  } catch (e) {
    console.log('加载默认配置失败，使用内置默认值:', e);
    // 内置兜底默认值
    applyDefaults({
      vertebrae: ['C2','C3','C4','C5','C6','C7','T1','T2','T3','T4','T5','T6','T7','T8','T9','T10','T11','T12','L1','L2','L3','L4','L5'],
      ranges: [1, 5, 10, 20],
      tissues: {'MUSCLE':'肌肉','BONE':'骨骼','SAT':'皮下脂肪','VAT':'腹腔脂肪','IMAT':'肌间脂肪','PAT':'纵隔脂肪','EAT':'心包脂肪'},
      metrics: {'volume':'容积','max-hu':'最大值','min-hu':'最小值','mean-hu':'均值','std-hu':'标准差','median-hu':'中位数','q1-hu':'四分位数间距1','q3-hu':'四分位数间距2'},
    });
  }
}

function applyDefaults(defaults) {
    AppState.analysis.vertebrae = defaults.vertebrae || [];
    AppState.analysis.ranges = defaults.ranges || [];
    AppState.export.singleVertebrae = [];
    AppState.export.ranges = [];
    renderModeBOptions(defaults);
    renderTissueMetrics(defaults);
    renderVertebraOptions(defaults);
}

function renderModeBOptions(defaults) {
  // 目标椎体 — 按 C(颈椎)/T(胸椎)/L(腰椎) 分三行，组内升序
  if (defaults.vertebrae) {
    // 按首字母分组，组内按编号升序（C2→C7, T1→T12, L1→L5）
    const numSort = (a, b) => parseInt(a.slice(1)) - parseInt(b.slice(1));
    const cervical = defaults.vertebrae.filter(v => v.startsWith('C')).sort(numSort);
    const thoracic = defaults.vertebrae.filter(v => v.startsWith('T')).sort(numSort);
    const lumbar   = defaults.vertebrae.filter(v => v.startsWith('L')).sort(numSort);

    const vertContainer = document.getElementById('step3VertGrid');
    if (vertContainer) {
      vertContainer.innerHTML = '';

      const renderGroup = (label, verts) => {
        const groupDiv = document.createElement('div');
        groupDiv.className = 'vertebra-group';
        groupDiv.innerHTML = `<span class="vertebra-group-label">${label}</span>`;
        verts.forEach(v => {
          const item = document.createElement('div');
          item.className = 'tag-item';
          item.innerHTML = `
            <input type="checkbox" id="sv_${v}" value="${v}" checked>
            <label for="sv_${v}">${v}</label>`;
          groupDiv.appendChild(item);
        });
        vertContainer.appendChild(groupDiv);
      };

      if (cervical.length) renderGroup(t('step3.cervical'), cervical);
      if (thoracic.length) renderGroup(t('step3.thoracic'), thoracic);
      if (lumbar.length)   renderGroup(t('step3.lumbar'), lumbar);
    }
  }

  // 分析范围
  const rangeContainer = document.getElementById('step3RangeGrid');
  if (rangeContainer && defaults.ranges) {
    rangeContainer.innerHTML = defaults.ranges.map(r =>
      `<div class="tag-item">
        <input type="checkbox" id="rg_${r}" value="${r}" checked>
        <label for="rg_${r}">${r}mm</label>
      </div>`
    ).join('');
  }

  // 自定义分析范围滑块
  const customContainer = document.getElementById('step3CustomRange');
  if (customContainer) {
    customContainer.innerHTML = `
      <div class="custom-range-row">
        <label class="custom-range-check">
          <input type="checkbox" id="rg_custom_enable">
          ${t('step3.customRange')}
        </label>
        <input type="range" id="rg_custom_slider" min="1" max="30" value="15" step="1"
               disabled oninput="document.getElementById('rg_custom_val').textContent=this.value">
        <span class="custom-range-val" id="rg_custom_val">15</span>
        <span>mm</span>
      </div>`;
    // 勾选启用滑块
    document.getElementById('rg_custom_enable').addEventListener('change', function() {
      document.getElementById('rg_custom_slider').disabled = !this.checked;
    });
  }
}

function renderVertebraOptions(defaults) {
  // 步骤4初始状态：仅显示占位提示，等待扫描
  const vertGrid = document.getElementById('exportVertGrid');
  if (vertGrid) {
    vertGrid.innerHTML = `<span style="font-size:12px;color:#999;">${t('js.scanCSVHint')}</span>`;
  }
  const rangeGrid = document.getElementById('exportRangeGrid');
  if (rangeGrid) rangeGrid.innerHTML = '';
}

function renderTissueMetrics(defaults) {
  const tissueGrid = document.getElementById('exportTissueGrid');
  if (tissueGrid && defaults.tissues) {
    tissueGrid.innerHTML = Object.entries(defaults.tissues).map(([key, name]) =>
      `<div class="tag-item">
        <input type="checkbox" id="ex_ts_${key}" value="${key}" checked>
        <label for="ex_ts_${key}">${name}<br><small>${key}</small></label>
      </div>`
    ).join('');
  }
  const metricGrid = document.getElementById('exportMetricGrid');
  if (metricGrid && defaults.metrics) {
    metricGrid.innerHTML = Object.entries(defaults.metrics).map(([key, name]) =>
      `<div class="tag-item">
        <input type="checkbox" id="ex_mt_${key}" value="${key}" checked>
        <label for="ex_mt_${key}">${name}<br><small>${key}</small></label>
      </div>`
    ).join('');
  }
}

// ===== 步骤1: 预处理 =====

function initStep1() {
  // 输入类型切换
  document.querySelectorAll('input[name="step1InputType"]').forEach(r => {
    r.addEventListener('change', (e) => {
      AppState.preprocess.inputType = e.target.value;
    });
  });

  // 扫描输入
  document.getElementById('btnScanInputs').addEventListener('click', async () => {
    const inputPath = document.getElementById('step1InputPath').value;
    const inputType = AppState.preprocess.inputType;
    if (!inputPath) {
      showStatusBox('step1Status', 'error', t('js.noInputPath'));
      return;
    }
    try {
      const result = await apiScanInputs(inputPath, inputType);
      AppState.preprocess.patients = result.patients || [];
      AppState.preprocess.inputPath = inputPath;

      renderPatientTable('step1PatientTable', AppState.preprocess.patients, true, [], AppState.preprocess.inputType);
      showStatusBox('step1Status', 'info',
        `检测到 <b>${result.total}</b> 个序列（${inputType === 'dicom' ? 'DICOM序列' : 'NIfTI文件'}）`);
    } catch (e) {
      showStatusBox('step1Status', 'error', t('js.scanFailMsg', {msg: e.message}));
    }
  });

  // 高斯模糊复选框：切换sigma输入框状态
  document.getElementById('step1GaussianEnable').addEventListener('change', (e) => {
    document.getElementById('step1GaussianSigma').disabled = !e.target.checked;
  });

  // 启动预处理
  document.getElementById('btnStartPreprocess').addEventListener('click', async () => {
    const inputPath = document.getElementById('step1InputPath').value;
    const outputPath = document.getElementById('step1WorkDir').value;
    const selectedIds = getSelectedPatientIds('step1PatientTable');

    if (!inputPath || !outputPath) {
      showStatusBox('step1Status', 'error', t('js.noInputOrWorkDir'));
      return;
    }

    // 读取图像预处理参数
    const sliceThickness = parseFloat(document.getElementById('step1SliceThickness').value) || 1.0;
    const interpolation = document.getElementById('step1Interpolation').value || 'sitkBSpline';
    const huMin = parseInt(document.getElementById('step1HuMin').value) || -3000;
    const huMax = parseInt(document.getElementById('step1HuMax').value) || 3000;
    const gaussianEnable = document.getElementById('step1GaussianEnable').checked;
    const gaussianSigma = gaussianEnable ? (parseFloat(document.getElementById('step1GaussianSigma').value) || 1.5) : 0.0;
    const outputNaming = document.querySelector('input[name="step1OutputNaming"]:checked')?.value || 'original';

    AppState.baseWorkingDir = outputPath;
    document.getElementById('baseWorkingDir').value = outputPath;

    try {
      const result = await apiStartPreprocess(
        inputPath, AppState.preprocess.inputType,
        outputPath, selectedIds.length > 0 ? selectedIds : null,
        huMin, huMax, gaussianSigma, outputNaming,
        sliceThickness, interpolation,
      );
      AppState.preprocess.taskId = result.task_id;

      document.getElementById('btnStartPreprocess').disabled = true;
      document.getElementById('btnCancelStep1').style.display = 'inline-flex';

      runTaskWithUI(result.task_id, 'step1Progress', 'step1Log',
        () => {
          document.getElementById('btnStartPreprocess').disabled = false;
          document.getElementById('btnCancelStep1').style.display = 'none';
          showStatusBox('step1Status', 'success', t('js.preprocessDone2'));
        },
        (res) => {
          const succ = res.success_count || 0;
          const fail = res.fail_count || 0;
          showStatusBox('step1Status', 'success', t('js.preprocessDone', {s: succ, f: fail}));
        },
        (err) => {
          document.getElementById('btnStartPreprocess').disabled = false;
          document.getElementById('btnCancelStep1').style.display = 'none';
        }
      );
    } catch (e) {
      showStatusBox('step1Status', 'error', t('js.startFailMsg', {msg: e.message}));
    }
  });

  // 取消
  document.getElementById('btnCancelStep1').addEventListener('click', () => {
    if (AppState.preprocess.taskId) apiCancelTask(AppState.preprocess.taskId);
    cancelActiveTask();
    document.getElementById('btnStartPreprocess').disabled = false;
    document.getElementById('btnCancelStep1').style.display = 'none';
  });
}

// ===== 步骤2: BOA分割 =====

async function refreshBOAPatients() {
  const basePath = document.getElementById('step2WorkDir').value || AppState.baseWorkingDir;
  try {
    const result = await apiGetBOAPatients(basePath);
    AppState.boa.patients = result.patients || [];
    renderPatientTable('step2PatientTable', AppState.boa.patients, true,
      AppState.boa.patients.filter(p => p.status === 'pending').map(p => p.patient_id),
      'nifti');
  } catch (e) {
    // 静默处理
  }
}

function initStep2() {
  document.getElementById('btnCheckEnv').addEventListener('click', async () => {
    try {
      const result = await apiCheckBOAEnv();
      AppState.boa.envChecked = true;
      AppState.boa.boaAvailable = result.boa_available;
      AppState.boa.gpuAvailable = result.gpu_available;

      let cls = 'info';
      let icon = '🔍';
      if (result.boa_available) {
        icon = '✅';
        cls = 'success';
      } else {
        icon = '❌';
        cls = 'error';
      }

      let info = `${result.message}`;
      if (result.gpu_available) info += `<br>🖥 GPU: ${result.gpu_info}`;
      if (result.conda_env) info += `<br>🐍 ${result.conda_env}`;

      showStatusBox('step2EnvStatus', cls, `<span class="status-icon">${icon}</span> ${info}`);
    } catch (e) {
      showStatusBox('step2EnvStatus', 'error', t('js.scanFailMsg', {msg: e.message}));
    }
  });

  document.getElementById('btnRefreshBOA').addEventListener('click', refreshBOAPatients);

  document.getElementById('btnStartBOA').addEventListener('click', async () => {
    const basePath = document.getElementById('step2WorkDir').value;
    const selectedIds = getSelectedPatientIds('step2PatientTable');
    // 收集选中的模型（total, bca），拼接为命令行参数格式
    const checkedModels = [];
    document.querySelectorAll('#md_total, #md_bca').forEach(cb => {
      if (cb.checked) checkedModels.push(cb.value);
    });
    const models = checkedModels.length > 0 ? checkedModels.join('+') : 'total+bca';

    if (!basePath || selectedIds.length === 0) {
      showStatusBox('step2EnvStatus', 'error', t('js.selectSeries'));
      return;
    }

    AppState.baseWorkingDir = basePath;
    document.getElementById('baseWorkingDir').value = basePath;

    try {
      const result = await apiStartBOA(basePath, selectedIds, models);
      AppState.boa.taskId = result.task_id;
      document.getElementById('btnStartBOA').disabled = true;
      document.getElementById('btnCancelStep2').style.display = 'inline-flex';

      showStatusBox('step2EnvStatus', 'info', result.message);

      runTaskWithUI(result.task_id, 'step2Progress', 'step2Log',
        () => {
          document.getElementById('btnStartBOA').disabled = false;
          document.getElementById('btnCancelStep2').style.display = 'none';
          showStatusBox('step2EnvStatus', 'success', t('js.allDone'));
          refreshBOAPatients();
        },
        (res) => {
          const succ = res.success_count || 0;
          const fail = res.fail_count || 0;
          showStatusBox('step2EnvStatus', 'success', t('js.segDone', {s: succ, f: fail}));
        },
        () => {
          document.getElementById('btnStartBOA').disabled = false;
          document.getElementById('btnCancelStep2').style.display = 'none';
        }
      );
    } catch (e) {
      showStatusBox('step2EnvStatus', 'error', t('js.startFailMsg', {msg: e.message}));
    }
  });

  document.getElementById('btnCancelStep2').addEventListener('click', () => {
    if (AppState.boa.taskId) apiCancelTask(AppState.boa.taskId);
    cancelActiveTask();
    document.getElementById('btnStartBOA').disabled = false;
    document.getElementById('btnCancelStep2').style.display = 'none';
  });
}

// ===== 步骤3: 统计分析 =====

function initStep3() {
  AppState.analysis.mode = 'B';

  // ---- 组织阈值设定 — 勾选后允许修改阈值 ----
  const thresholdInputs = ['step3FatMin', 'step3FatMax', 'step3MuscleMin', 'step3MuscleMax'];
  document.getElementById('step3ThresholdEnable').addEventListener('change', function() {
    thresholdInputs.forEach(id => {
      document.getElementById(id).disabled = !this.checked;
    });
  });

  // ---- 扫描NIFTI文件 ----
  document.getElementById('btnScanDirs').addEventListener('click', async () => {
    const workDir = AppState.baseWorkingDir;
    if (!workDir) {
      showStatusBox('step3ScanStatus', 'error', t('js.noWorkingDirStep3'));
      return;
    }
    // 更新路径显示
    document.getElementById('step3CtDir').value = workDir + '/ct_image';
    document.getElementById('step3LabelDir').value = workDir + '/boa_label';

    try {
      const result = await apiScanAnalysisDirs(workDir);
      const box = document.getElementById('step3ScanStatus');
      box.style.display = 'block';
      if (result.ct_count === 0 && result.label_count === 0) {
        box.className = 'status-box error';
        document.getElementById('step3ScanResult').innerHTML =
          t('js.scanNoData');
      } else {
        box.className = 'status-box info';
        document.getElementById('step3ScanResult').innerHTML =
          t('js.scanResult', {ct: `<b>${result.ct_count}</b>`, lb: `<b>${result.label_count}</b>`});
      }
    } catch (e) {
      showStatusBox('step3ScanStatus', 'error', t('js.scanFailMsg', {msg: e.message}));
    }
  });

  // ---- 启动并行分析 ----
  document.getElementById('btnStartModeB').addEventListener('click', async () => {
    const basePath = AppState.baseWorkingDir;
    const workers = parseInt(document.getElementById('step3Workers').value) || 4;
    const includeAll = document.getElementById('step3IncludeAll').checked;
    const vertebrae = getCheckedValues('step3VertGrid');
    const ranges = getCheckedValues('step3RangeGrid').map(Number);

    // 自定义范围
    const customEnable = document.getElementById('rg_custom_enable');
    if (customEnable && customEnable.checked) {
      const customVal = parseInt(document.getElementById('rg_custom_slider').value);
      if (!ranges.includes(customVal)) ranges.push(customVal);
    }

    // ---- 组织阈值设定参数 ----
    const thresholdEnabled = document.getElementById('step3ThresholdEnable').checked;
    const fatMin = parseInt(document.getElementById('step3FatMin').value) || -190;
    const fatMax = parseInt(document.getElementById('step3FatMax').value) || -30;
    const muscleMin = parseInt(document.getElementById('step3MuscleMin').value) || -29;
    const muscleMax = parseInt(document.getElementById('step3MuscleMax').value) || 150;

    try {
      const result = await apiStartModeB(basePath, workers, vertebrae, ranges, includeAll,
        thresholdEnabled, fatMin, fatMax, muscleMin, muscleMax);
      AppState.analysis.taskId = result.task_id;
      document.getElementById('btnStartModeB').disabled = true;
      document.getElementById('btnCancelStep3').style.display = 'inline-flex';

      runTaskWithUI(result.task_id, 'step3Progress', 'step3Log',
        () => {
          document.getElementById('btnStartModeB').disabled = false;
          document.getElementById('btnCancelStep3').style.display = 'none';
          showStatusBox('step3Status', 'success', t('js.statsDone'));
        },
        (res) => {
          showStatusBox('step3Status', 'success',
            t('js.analysisDone', {n: res.total_patients, s: res.success_tasks}));
        },
        () => {
          document.getElementById('btnStartModeB').disabled = false;
          document.getElementById('btnCancelStep3').style.display = 'none';
        }
      );
    } catch (e) {
      showStatusBox('step3Status', 'error', t('js.startFailMsg', {msg: e.message}));
    }
  });

  // 取消
  document.getElementById('btnCancelStep3').addEventListener('click', () => {
    if (AppState.analysis.taskId) apiCancelTask(AppState.analysis.taskId);
    cancelActiveTask();
    document.getElementById('btnStartModeB').disabled = false;
    document.getElementById('btnCancelStep3').style.display = 'none';
  });
}

// ===== 步骤4: 数据导出 =====

async function refreshExportData() {
  const basePath = document.getElementById('step4BasePath').value || AppState.baseWorkingDir;
  if (!basePath) {
    showStatusBox('step4Status', 'error', t('js.noWorkingDir'));
    return;
  }
  try {
    const result = await apiScanCSVs(basePath);
    AppState.export.patients = result.patients || [];
    AppState.export.scanResult = result;

    // 显示扫描统计
    const statusBox = document.getElementById('step4Status');
    statusBox.style.display = 'block';
    statusBox.className = result.total > 0 ? 'status-box info' : 'status-box error';
    if (result.total > 0) {
      document.getElementById('step4ScanResult').innerHTML =
        t('js.scanCSVFound', {n: `<b>${result.total}</b>`, c: `<b>${result.total_csv_files || 0}</b>`});
    } else {
      document.getElementById('step4ScanResult').innerHTML =
        t('js.scanCSVEmpty');
    }

    // 动态渲染扫描范围选项
    renderExportScanOptions(result);
  } catch (e) {
    showStatusBox('step4Status', 'error', t('js.scanFailMsg', {msg: e.message}));
  }
}

/** 根据扫描结果动态渲染步骤4的扫描范围选项 */
function renderExportScanOptions(result) {
  const optionsCard = document.getElementById('step4ScanOptions');
  if (!result || result.total === 0) {
    if (optionsCard) optionsCard.style.display = 'none';
    return;
  }
  if (optionsCard) optionsCard.style.display = '';

  const hasAll = result.has_all;
  const vertebrae = result.available_vertebrae || [];
  const ranges = result.available_ranges || [];

  // ---- 全图分析 (ALL) ----
  const allCheckbox = document.getElementById('exportALL');
  const allHint = document.getElementById('exportALLHint');
  if (allCheckbox) {
    allCheckbox.checked = hasAll;
    allCheckbox.disabled = !hasAll;
  }
  if (allHint) {
    allHint.textContent = hasAll ? '（已检测到全图分析数据）' : '（未检测到全图分析数据，不可选）';
  }

  // ---- 目标椎体（C/T/L 分组） ----
  const vertGrid = document.getElementById('exportVertGrid');
  if (vertGrid && vertebrae.length > 0) {
    const numSort = (a, b) => parseInt(a.slice(1)) - parseInt(b.slice(1));
    const cervical = vertebrae.filter(v => v.startsWith('C')).sort(numSort);
    const thoracic = vertebrae.filter(v => v.startsWith('T')).sort(numSort);
    const lumbar   = vertebrae.filter(v => v.startsWith('L')).sort(numSort);

    vertGrid.innerHTML = '';
    const renderGroup = (label, verts) => {
      const groupDiv = document.createElement('div');
      groupDiv.className = 'vertebra-group';
      groupDiv.innerHTML = `<span class="vertebra-group-label">${label}</span>`;
      verts.forEach(v => {
        const item = document.createElement('div');
        item.className = 'tag-item';
        item.innerHTML = `
          <input type="checkbox" id="ex_sv_${v}" value="${v}">
          <label for="ex_sv_${v}">${v}</label>`;
        groupDiv.appendChild(item);
      });
      vertGrid.appendChild(groupDiv);
    };
    if (cervical.length) renderGroup(t('step4.cervical'), cervical);
    if (thoracic.length) renderGroup(t('step4.thoracic'), thoracic);
    if (lumbar.length)   renderGroup(t('step4.lumbar'), lumbar);
  } else if (vertGrid) {
    vertGrid.innerHTML = `<span style="font-size:12px;color:#999;">${t('js.noVertData')}</span>`;
  }

  // ---- 分析范围 ----
  const rangeGrid = document.getElementById('exportRangeGrid');
  if (rangeGrid && ranges.length > 0) {
    rangeGrid.innerHTML = ranges.map(r =>
      `<div class="tag-item">
        <input type="checkbox" id="ex_rg_${r}" value="${r}">
        <label for="ex_rg_${r}">${r}mm</label>
      </div>`
    ).join('');
  } else if (rangeGrid) {
    rangeGrid.innerHTML = `<span style="font-size:12px;color:#999;">${t('js.noRangeData')}</span>`;
  }
}

function initStep4() {
  document.getElementById('btnScanCSVs').addEventListener('click', refreshExportData);

  document.getElementById('btnStep4Generate').addEventListener('click', async () => {
    const basePath = document.getElementById('step4BasePath').value;
    const includeAll = document.getElementById('exportALL').checked;
    const singleVert = getCheckedValues('exportVertGrid');
    const ranges = getCheckedValues('exportRangeGrid').map(Number);
    const tissues = getCheckedValues('exportTissueGrid');
    const metrics = getCheckedValues('exportMetricGrid');

    if (!includeAll && singleVert.length === 0) {
      alert(t('js.selectScanType'));
      return;
    }
    if (tissues.length === 0) { alert(t('js.selectTissue')); return; }
    if (metrics.length === 0) { alert(t('js.selectMetric')); return; }
    if (singleVert.length > 0 && ranges.length === 0) {
      alert(t('js.selectVertRange'));
      return;
    }

    try {
      const result = await apiGenerateMerge(basePath, includeAll, singleVert, ranges, [], tissues, metrics, null);
      AppState.export.taskId = result.task_id;
      document.getElementById('btnStep4Generate').disabled = true;

      runTaskWithUI(result.task_id, 'step4Progress', 'step4Log',
        async () => {
          document.getElementById('btnStep4Generate').disabled = false;
          document.getElementById('btnStep4Download').style.display = 'inline-flex';
          showStatusBox('step4Status', 'success', t('js.tableGenerated'));
          // 显示预览
          try {
            const preview = await apiPreviewMerge(result.task_id);
            renderPreviewTable(preview);
          } catch (e) { /* ignore */ }
        },
        null,
        () => { document.getElementById('btnStep4Generate').disabled = false; }
      );
    } catch (e) {
      alert(t('js.generateFail', {msg: e.message}));
    }
  });

  document.getElementById('btnStep4Download').addEventListener('click', () => {
    if (AppState.export.taskId) {
      window.open(apiDownloadMerge(AppState.export.taskId), '_blank');
    }
  });
}

function renderPreviewTable(preview) {
  const container = document.getElementById('step4PreviewTable');
  if (!container || !preview.headers || preview.headers.length === 0) return;

  let html = '<thead><tr>';
  preview.headers.forEach(h => { html += `<th>${h}</th>`; });
  html += '</tr></thead><tbody>';

  (preview.rows || []).forEach(row => {
    html += '<tr>';
    row.forEach((cell, i) => {
      const val = cell !== undefined && cell !== null && cell !== '' ? String(cell) : '-';
      const css = val === '-' ? ' class="empty"' : '';
      html += `<td${css}>${val}</td>`;
    });
    html += '</tr>';
  });
  html += '</tbody>';

  container.innerHTML = html;
  document.getElementById('step4PreviewWrap').style.display = 'block';
  document.getElementById('step4PreviewStats').textContent =
    `共 ${preview.total_rows || 0} 行 × ${preview.total_columns || preview.headers.length} 列`;
  document.getElementById('step4PreviewWrap').scrollIntoView({ behavior: 'smooth' });
}
