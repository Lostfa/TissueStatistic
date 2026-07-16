/**
 * API通信模块
 * 封装所有与后端FastAPI服务的HTTP请求。
 * 支持SSE（Server-Sent Events）实时进度流和标准REST调用。
 */

const API_BASE = '';

// ===== 通用请求函数 =====

async function apiGet(path, params = {}) {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v);
  });
  const resp = await fetch(url);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }
  return resp.json();
}

async function apiPost(path, data = {}) {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }
  return resp.json();
}

async function apiDelete(path) {
  const resp = await fetch(`${API_BASE}${path}`, { method: 'DELETE' });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }
  return resp.json();
}

// ===== SSE 流式请求 =====

function apiStreamTask(taskId, callbacks) {
  const url = `${API_BASE}/api/tasks/${taskId}/stream`;
  const eventSource = new EventSource(url);

  eventSource.addEventListener('progress', (e) => {
    try {
      const data = JSON.parse(e.data);
      if (callbacks.onProgress) callbacks.onProgress(data.progress, data.message);
    } catch { /* ignore parse error */ }
  });

  eventSource.addEventListener('log', (e) => {
    if (callbacks.onLog) callbacks.onLog(e.data);
  });

  eventSource.addEventListener('status', (e) => {
    const status = e.data;
    if (status === 'completed' && callbacks.onComplete) callbacks.onComplete();
    if (status === 'failed' && callbacks.onError) callbacks.onError('任务执行失败');
    if (status === 'cancelled' && callbacks.onCancelled) callbacks.onCancelled();
    eventSource.close();
  });

  eventSource.addEventListener('result', (e) => {
    try {
      const data = JSON.parse(e.data);
      if (callbacks.onResult) callbacks.onResult(data);
    } catch { /* ignore parse error */ }
  });

  eventSource.addEventListener('error', (e) => {
    if (callbacks.onError) callbacks.onError(e.data || '连接错误');
    eventSource.close();
  });

  eventSource.onerror = () => {
    // SSE连接出错，可能任务已完成但未收到最终事件
    // 回退到轮询获取最终状态
    setTimeout(async () => {
      try {
        const task = await apiGetTask(taskId);
        if (task.status === 'completed' && callbacks.onComplete) callbacks.onComplete();
        if (task.status === 'failed' && callbacks.onError) callbacks.onError(task.error);
      } catch { /* ignore */ }
    }, 2000);
  };

  return eventSource;
}

// ===== 轮询备选 =====

async function apiPollTask(taskId, callbacks, intervalMs = 1000) {
  let completed = false;
  while (!completed) {
    await sleep(intervalMs);
    try {
      const task = await apiGetTask(taskId);
      if (callbacks.onProgress) callbacks.onProgress(task.progress, task.message);
      if (task.log && callbacks.onLog) {
        // 仅发送新增的日志
        task.log.slice(-5).forEach(l => callbacks.onLog(l));
      }
      if (task.status === 'completed') {
        if (callbacks.onComplete) callbacks.onComplete();
        if (task.result && callbacks.onResult) callbacks.onResult(task.result);
        completed = true;
      }
      if (task.status === 'failed') {
        if (callbacks.onError) callbacks.onError(task.error || '未知错误');
        completed = true;
      }
      if (task.status === 'cancelled') {
        if (callbacks.onCancelled) callbacks.onCancelled();
        completed = true;
      }
    } catch (e) {
      if (callbacks.onError) callbacks.onError(e.message);
      completed = true;
    }
  }
}

// ===== 任务API =====

function apiGetTask(taskId) { return apiGet(`/api/tasks/${taskId}`); }
function apiListTasks(params = {}) { return apiGet('/api/tasks', params); }
function apiCancelTask(taskId) { return apiDelete(`/api/tasks/${taskId}`); }

// ===== 配置API =====

function apiGetConfig() { return apiGet('/api/config'); }

// ===== 预处理API =====

function apiScanInputs(inputPath, inputType) {
  return apiPost('/api/preprocess/scan-inputs', { input_path: inputPath, input_type: inputType });
}
function apiStartPreprocess(inputPath, inputType, outputBasePath, patientIds, huMin, huMax, gaussianSigma, outputNaming, sliceThickness, interpolation) {
  return apiPost('/api/preprocess/start', {
    input_path: inputPath,
    input_type: inputType,
    output_base_path: outputBasePath,
    patient_ids: patientIds,
    hu_min: huMin,
    hu_max: huMax,
    gaussian_sigma: gaussianSigma,
    output_naming: outputNaming,
    slice_thickness: sliceThickness || 1.0,
    interpolation: interpolation || 'sitkBSpline',
  });
}
function apiGetPreprocessPatients(basePath) {
  return apiGet('/api/preprocess/patients', { base_path: basePath });
}

// ===== BOA API =====

function apiCheckBOAEnv() { return apiGet('/api/boa/check-environment'); }
function apiStartBOA(basePath, patientIds, models) {
  return apiPost('/api/boa/start', {
    base_path: basePath,
    patient_ids: patientIds,
    models: models || 'all',
  });
}
function apiGetBOAPatients(basePath) {
  return apiGet('/api/boa/patients', { base_path: basePath });
}

// ===== 分析API =====

function apiGetAnalysisDefaults() { return apiGet('/api/analysis/config/defaults'); }
function apiScanAnalysisDirs(workDir) {
  return apiPost('/api/analysis/scan-dirs', { work_dir: workDir });
}
function apiStartModeB(basePath, workers, vertebrae, ranges, includeAll,
                       thresholdEnabled = false, fatMin = -190, fatMax = -30,
                       muscleMin = -29, muscleMax = 150) {
  return apiPost('/api/analysis/mode-b/start', {
    base_path: basePath,
    workers: workers,
    vertebrae: vertebrae,
    ranges: ranges,
    include_all: includeAll,
    threshold_enabled: thresholdEnabled,
    fat_min: fatMin,
    fat_max: fatMax,
    muscle_min: muscleMin,
    muscle_max: muscleMax,
  });
}
function apiGetCSVFiles(basePath) {
  return apiGet('/api/analysis/csv-files', { base_path: basePath });
}

// ===== 合并导出API =====

function apiScanCSVs(basePath) {
  return apiPost('/api/merge/scan-csvs', { base_path: basePath });
}
function apiGenerateMerge(basePath, includeAll, singleVert, ranges, vertPairs, tissues, metrics, patientIds) {
  return apiPost('/api/merge/generate', {
    base_path: basePath,
    include_all: includeAll,
    single_vertebrae: singleVert,
    ranges: ranges,
    vertebra_pairs: [],
    tissues: tissues,
    metrics: metrics,
    patient_ids: patientIds,
  });
}
function apiDownloadMerge(taskId) {
  return `${API_BASE}/api/merge/download/${taskId}`;
}
function apiPreviewMerge(taskId) {
  return apiGet(`/api/merge/preview/${taskId}`);
}

// ===== 工具函数 =====

// ===== 系统工具API =====

function apiOpenFolder(path) {
  return apiPost('/api/system/open-folder', { path: path });
}

// ===== 工具函数 =====

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
