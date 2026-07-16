/**
 * 步骤导航与状态管理模块
 * 管理4步向导流程、步骤间数据传递和UI状态更新。
 */

// ===== 文件夹选择器 =====

/**
 * 通过后端原生对话框选择文件夹。
 * 调用 Python tkinter 的文件夹选择器，获取完整的本地路径。
 *
 * 由于浏览器安全限制，网页无法获取本地文件的完整路径，
 * 因此通过后端API打开操作系统原生文件夹选择对话框。
 *
 * @param {string} _pickerId - 未使用（保留参数兼容旧HTML onclick调用）
 * @param {string} targetInputId - 要填入路径的文本输入框ID
 */
async function pickFolder(_pickerId, targetInputId) {
  const target = document.getElementById(targetInputId);
  if (!target) return;

  try {
    const resp = await fetch('/api/system/pick-folder');
    const data = await resp.json();
    if (data.success && data.path) {
      target.value = data.path;
      // 同步全局工作目录
      if (target.classList.contains('wd-input') || targetId === 'baseWorkingDir') {
        syncWorkingDirs(data.path);
      }
    }
    // 用户取消选择时不做任何操作
  } catch (e) {
    console.error('文件夹选择失败:', e);
  }
}

/**
 * 在 Windows 资源管理器（或系统默认文件管理器）中打开当前工作目录。
 * 调用后端 API 执行系统级文件夹打开操作。
 */
async function openWorkDirInExplorer() {
  const dirPath = document.getElementById('baseWorkingDir').value;
  if (!dirPath) {
    alert('请先设置工作目录路径');
    return;
  }
  try {
    await apiOpenFolder(dirPath);
  } catch (e) {
    alert('无法打开目录: ' + (e.message || e));
  }
}

// ===== 全局应用状态 =====
const AppState = {
  activeStep: 1,
  baseWorkingDir: 'D:/TissueStatistic',
  // 步骤1 - 预处理
  preprocess: {
    inputType: 'dicom',
    inputPath: '',
    patients: [],
    selectedIds: [],
    taskId: null,
    running: false,
  },
  // 步骤2 - BOA
  boa: {
    patients: [],
    selectedIds: [],
    models: 'all',
    weightsPath: '',
    taskId: null,
    running: false,
    dockerChecked: false,
    dockerAvailable: false,
    gpuAvailable: false,
  },
  // 步骤3 - 分析
  analysis: {
    mode: 'B',
    basePath: '',
    workers: 4,
    taskId: null,
    running: false,
    vertebrae: [],
    ranges: [],
    includeAll: true,
  },
  // 步骤4 - 导出
  export: {
    basePath: '',
    patients: [],
    scanTypes: [],
    includeAll: true,
    singleVertebrae: [],
    ranges: [],
    tissues: ['MUSCLE', 'BONE', 'SAT', 'VAT', 'IMAT', 'PAT', 'EAT'],
    metrics: ['volume', 'max-hu', 'min-hu', 'mean-hu', 'std-hu', 'median-hu', 'q1-hu', 'q3-hu'],
    taskId: null,
    running: false,
  },
};

// ===== 步骤导航 =====

function goToStep(step) {
  // 允许自由导航到任意步骤（1-4）
  step = Math.max(1, Math.min(4, step));
  AppState.activeStep = step;
  updateStepIndicators();
  updateStepPanel();
}

function goToPrevStep() { goToStep(AppState.activeStep - 1); }
function goToNextStep() { goToStep(AppState.activeStep + 1); }

function completeStep(step) {
  // 保留兼容性，仅更新状态指示器
  updateStepIndicators();
  updateStepPanel();
}

function updateStepIndicators() {
  document.querySelectorAll('.step-indicator').forEach((el, i) => {
    const stepNum = i + 1;
    el.classList.remove('active', 'completed');
    if (stepNum === AppState.activeStep) el.classList.add('active');
    else if (stepNum < AppState.activeStep) el.classList.add('completed');
  });

  // 更新步骤描述
  document.getElementById('step1Status').textContent = AppState.preprocess.patients.length > 0
    ? `(${AppState.preprocess.patients.length} ${currentLang === 'zh' ? '个序列' : 'series'})` : '';
  document.getElementById('step2Status').textContent = AppState.boa.patients.length > 0
    ? `(${AppState.boa.patients.length} ${currentLang === 'zh' ? '个序列' : 'series'})` : '';

  // 更新导航按钮和标签
  const btnPrev = document.getElementById('btnPrevStep');
  const btnNext = document.getElementById('btnNextStep');
  const navLabel = document.getElementById('consoleNavLabel');
  if (btnPrev) {
    btnPrev.disabled = AppState.activeStep <= 1;
    btnPrev.textContent = t('nav.prev');
  }
  if (btnNext) {
    btnNext.disabled = AppState.activeStep >= 4;
    btnNext.textContent = t('nav.next');
  }
  if (navLabel) navLabel.textContent = `${t('nav.step')} ${AppState.activeStep} / 4`;
}

function updateStepPanel() {
  document.querySelectorAll('.step-panel').forEach(p => p.classList.remove('active'));
  const panel = document.getElementById(`step${AppState.activeStep}Panel`);
  if (panel) panel.classList.add('active');

  // 进入步骤时的刷新操作
  if (AppState.activeStep === 2) refreshBOAPatients();
  if (AppState.activeStep === 4) {
    // 不自动扫描，用户需手动点击"扫描CSV数据"
    document.getElementById('step4ScanOptions').style.display = 'none';
    document.getElementById('step4Status').style.display = 'none';
  }
}

// ===== 任务进度UI =====

let activeTaskStream = null;

/** 显示/隐藏右侧控制台进度条 */
function showProgress(containerId, show) {
  const wrap = document.getElementById('consoleProgress');
  if (wrap) wrap.style.display = show ? 'block' : 'none';
}

/** 更新右侧控制台进度条百分比和文字 */
function updateProgress(containerId, percent, text) {
  const fill = document.getElementById('consoleProgressFill');
  const textEl = document.getElementById('consoleProgressText');
  if (fill) fill.style.width = percent + '%';
  if (textEl) textEl.textContent = text || '';
  // 同时更新控制台状态栏
  const statusEl = document.getElementById('consoleStatus');
  if (statusEl && text) statusEl.textContent = text;
}

/** 显示日志面板（已废弃，控制台始终可见） */
function showLogPanel(containerId, show) {
  // 控制台始终可见，此函数保留兼容性
}

/** 向右侧控制台追加日志行 */
function appendLog(containerId, message, level) {
  const panel = document.getElementById('consoleLog');
  if (!panel) return;

  // 移除空状态提示
  const empty = panel.querySelector('.console-empty');
  if (empty) empty.remove();

  const line = document.createElement('div');
  line.className = 'log-line';
  if (level === 'success') line.classList.add('log-success');
  else if (level === 'error') line.classList.add('log-error');
  else if (level === 'warn') line.classList.add('log-warn');
  else if (level === 'info') line.classList.add('log-info');
  line.textContent = message;
  panel.appendChild(line);
  panel.scrollTop = panel.scrollHeight;
}

/** 清空右侧控制台日志 */
function clearLog(containerId) {
  const panel = document.getElementById('consoleLog');
  if (panel) {
    panel.innerHTML = '<div class="console-empty">等待任务开始...</div>';
  }
}

/** 清空整个控制台 */
function clearConsole() {
  clearLog();
  showProgress('', false);
  document.getElementById('consoleStatus').textContent = t('console.cleared');
}

/** 显示状态提示框（保留兼容，同时更新控制台状态） */
function showStatusBox(boxId, type, message) {
  // 更新原有的状态框
  const box = document.getElementById(boxId);
  if (box) {
    box.className = `status-box ${type}`;
    box.innerHTML = message;
    box.style.display = 'block';
  }
  // 同步到控制台状态栏
  const statusEl = document.getElementById('consoleStatus');
  if (statusEl) {
    let label = '';
    if (type === 'success') label = '✅ ';
    else if (type === 'error') label = '❌ ';
    else if (type === 'warning') label = '⚠️ ';
    statusEl.textContent = label + message.replace(/<[^>]*>/g, '');
  }
}

function hideStatusBox(boxId) {
  const box = document.getElementById(boxId);
  if (box) box.style.display = 'none';
}

// ===== 任务执行辅助 =====

function runTaskWithUI(taskId, progressContainerId, logContainerId,
                       onComplete, onResult, onError) {
  showProgress(progressContainerId, true);
  showLogPanel(logContainerId, true);
  clearLog(logContainerId);
  updateProgress(progressContainerId, 0, '任务已提交，等待开始...');

  // 尝试SSE流
  try {
    activeTaskStream = apiStreamTask(taskId, {
      onProgress: (percent, msg) => {
        updateProgress(progressContainerId, percent, msg || '');
      },
      onLog: (msg) => {
        let level = '';
        if (msg.includes('[OK]') || msg.includes('[DONE]') || msg.includes('[成功]') || msg.includes('完成')) level = 'success';
        else if (msg.includes('[FAIL]') || msg.includes('[ERROR]') || msg.includes('[EXCEPTION]') || msg.includes('[失败]') || msg.includes('[异常]') || msg.includes('[错误]')) level = 'error';
        else if (msg.includes('[WARN]') || msg.includes('[警告]')) level = 'warn';
        appendLog(logContainerId, msg, level);
      },
      onComplete: () => {
        updateProgress(progressContainerId, 100, '任务完成');
        showLogPanel(logContainerId, false);
        if (onComplete) onComplete();
      },
      onResult: (result) => {
        if (onResult) onResult(result);
      },
      onError: (err) => {
        updateProgress(progressContainerId, 0, `错误: ${err}`);
        appendLog(logContainerId, `[ERROR] ${err}`, 'error');
        if (onError) onError(err);
      },
      onCancelled: () => {
        updateProgress(progressContainerId, 0, '任务已取消');
      },
    });
  } catch (e) {
    // SSE不支持，回退到轮询
    apiPollTask(taskId, {
      onProgress: (percent, msg) => {
        updateProgress(progressContainerId, percent, msg || '');
      },
      onLog: (msg) => {
        appendLog(logContainerId, msg, '');
      },
      onComplete: () => {
        updateProgress(progressContainerId, 100, '任务完成');
        if (onComplete) onComplete();
      },
      onResult: (result) => {
        if (onResult) onResult(result);
      },
      onError: (err) => {
        updateProgress(progressContainerId, 0, `错误: ${err}`);
        if (onError) onError(err);
      },
    });
  }
}

function cancelActiveTask() {
  if (activeTaskStream) {
    activeTaskStream.close();
    activeTaskStream = null;
  }
}

// ===== 通用UI辅助 =====

function renderPatientTable(containerId, patients, checkboxes = false, selectedIds = [], inputType = null) {
  const container = document.getElementById(containerId);
  if (!container) return;
  if (!patients || patients.length === 0) {
    container.innerHTML = '<div class="empty-state"><div class="empty-icon">📭</div><div class="empty-text">暂无序列数据</div></div>';
    return;
  }

  let html = '<table><thead><tr>';
  if (checkboxes) html += '<th><input type="checkbox" class="select-all-cb"></th>';

  if (inputType) {
    // 步骤1 扫描结果：显示详细列
    html += '<th>序列ID</th>';
    if (inputType === 'dicom') html += '<th>扫描时间</th>';
    html += '<th>图像尺寸</th>';
    html += '<th>体素间距</th>';
  } else {
    // 其他步骤：原始列
    html += '<th>序列ID</th><th>状态</th><th>详情</th>';
  }
  html += '</tr></thead><tbody>';

  patients.forEach((p, i) => {
    const pid = p.patient_id || p.id || '';

    html += '<tr>';
    if (checkboxes) {
      const checked = selectedIds.includes(pid) ? 'checked' : '';
      html += `<td><input type="checkbox" class="patient-cb" value="${pid}" ${checked}></td>`;
    }

    if (inputType) {
      // 详细列模式
      html += `<td>${pid}</td>`;
      if (inputType === 'dicom') {
        const date = p.series_date || '';
        html += `<td class="${date ? '' : 'text-muted'}">${date || '-'}</td>`;
      }
      html += `<td>${p.image_size || 'N/A'}</td>`;
      html += `<td>${p.image_spacing || 'N/A'}</td>`;
    } else {
      // 原始列模式
      const status = p.status || '';
      const detail = p.file_count ? `${p.file_count}个文件` : (p.existing_files || []).join(', ') || (p.csv_files || []).length + '个CSV';

      let statusClass = '';
      if (status === 'done' || status === 'completed') statusClass = 'text-success';
      else if (status === 'pending') statusClass = 'text-muted';
      else if (status === 'partial') statusClass = 'text-muted';

      html += `<td>${pid}</td>`;
      html += `<td class="${statusClass}">${status}</td>`;
      html += `<td>${detail}</td>`;
    }
    html += '</tr>';
  });
  html += '</tbody></table>';

  container.innerHTML = html;

  // 绑定全选事件
  if (checkboxes) {
    const selectAll = container.querySelector('.select-all-cb');
    if (selectAll) {
      selectAll.addEventListener('change', (e) => {
        container.querySelectorAll('.patient-cb').forEach(cb => {
          cb.checked = e.target.checked;
        });
      });
    }
  }
}

function getSelectedPatientIds(tableContainerId) {
  const container = document.getElementById(tableContainerId);
  if (!container) return [];
  const cbs = container.querySelectorAll('.patient-cb:checked');
  return Array.from(cbs).map(cb => cb.value);
}

function toggleGroup(containerId, select) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.querySelectorAll('input[type=checkbox]').forEach(cb => {
    cb.checked = select;
  });
}

function getCheckedValues(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return [];
  return Array.from(container.querySelectorAll('input:checked')).map(cb => cb.value);
}

// ===== 同步工作目录 =====

/**
 * 将所有步骤中的工作目录输入框与全局值同步。
 * 当用户在任一位置修改工作目录时调用。
 */
function syncWorkingDirs(sourceValue) {
  AppState.baseWorkingDir = sourceValue;
  // 更新顶部栏
  const headerDir = document.getElementById('baseWorkingDir');
  if (headerDir) headerDir.value = sourceValue;
  // 更新各步骤中class为wd-input的输入框
  document.querySelectorAll('.wd-input').forEach(inp => {
    inp.value = sourceValue;
  });
  // 也更新步骤1的工作目录
  const step1Dir = document.getElementById('step1WorkDir');
  if (step1Dir) step1Dir.value = sourceValue;
  // 步骤3 — 图像/标签目录
  const step3Ct = document.getElementById('step3CtDir');
  if (step3Ct) step3Ct.value = sourceValue + '/ct_image';
  const step3Label = document.getElementById('step3LabelDir');
  if (step3Label) step3Label.value = sourceValue + '/boa_label';
  // 步骤4
  const step4Dir = document.getElementById('step4BasePath');
  if (step4Dir) step4Dir.value = sourceValue;
}

// ===== 初始化 =====

function initWizard() {
  // 步骤点击事件
  document.querySelectorAll('.step-indicator').forEach(el => {
    el.addEventListener('click', () => {
      const step = parseInt(el.dataset.step);
      goToStep(step);
    });
  });

  // 初始设置默认值
  document.getElementById('baseWorkingDir').value = AppState.baseWorkingDir;

  // 顶部栏工作目录变化时同步
  document.getElementById('baseWorkingDir').addEventListener('change', (e) => {
    syncWorkingDirs(e.target.value);
  });

  // 初始同步
  syncWorkingDirs(AppState.baseWorkingDir);

  updateStepIndicators();
  updateStepPanel();
}
