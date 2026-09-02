const screen = document.querySelector('#screen');
const activeCount = document.querySelector('#active-count');
const healthDot = document.querySelector('#health-dot');
const healthCopy = document.querySelector('#health-copy');
const toastStack = document.querySelector('#toast-stack');

const STATUS_LABELS = {
  queued: '排队中',
  running: '执行中',
  succeeded: '已完成',
  failed: '失败',
  cancelled: '已取消',
  cancelling: '取消中',
  pending: '待执行',
  done: '完成',
  skipped: '跳过',
};

const TERMINAL = new Set(['succeeded', 'failed', 'cancelled']);

const state = {
  jobs: [],
  capabilities: null,
  selectedFile: null,
  workspaceJobId: null,
  workspaceJob: null,
  result: null,
  selectedNodeId: null,
  expanded: new Set(),
  treeFilter: '',
  detailTab: 'detail',
  sourceText: null,
  sourceTextJobId: null,
  consoleStatus: 'all',
  consoleSearch: '',
  runJob: null,
  runEvents: [],
  eventSource: null,
  runRefreshTimer: null,
  runAutoFollow: true,
  globalRefreshTimer: null,
};

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function attr(value) {
  return escapeHtml(value).replaceAll('`', '&#096;');
}

function clamp(value, min = 0, max = 1) {
  return Math.max(min, Math.min(max, Number(value) || 0));
}

function statusBadge(status, compact = false) {
  const label = STATUS_LABELS[status] || status || '未知';
  return `<span class="badge ${attr(status)}"><span class="status-pulse"></span>${compact ? '' : escapeHtml(label)}</span>`;
}

function formatBytes(bytes) {
  const value = Number(bytes) || 0;
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 ** 2).toFixed(1)} MB`;
}

function formatTime(value, withDate = false) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const options = withDate
    ? { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }
    : { hour: '2-digit', minute: '2-digit', second: '2-digit' };
  return new Intl.DateTimeFormat('zh-CN', options).format(date);
}

function formatDuration(start, end) {
  if (!start) return '—';
  const started = new Date(start).getTime();
  const finished = end ? new Date(end).getTime() : Date.now();
  if (!Number.isFinite(started) || !Number.isFinite(finished)) return '—';
  const seconds = Math.max(0, Math.round((finished - started) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${seconds % 60}s`;
}

function formatMetric(key, value) {
  if (value === null || value === undefined) return '—';
  if (key.endsWith('_rate') || key.endsWith('_coverage')) return `${Math.round(Number(value) * 100)}%`;
  if (key === 'elapsed_seconds') return `${Number(value).toFixed(2)}s`;
  return String(value);
}

function metricLabel(key) {
  return ({
    division_count: '分项',
    inspection_lot_count: '检验批',
    acceptance_item_count: '验收项目',
    grounding_rate: '证据覆盖',
    sampling_coverage: '抽样覆盖',
    ontology_attachment_rate: '50300 挂载',
    elapsed_seconds: '执行耗时',
  })[key] || key;
}

function currentRoute() {
  const path = window.location.pathname;
  const runMatch = path.match(/^\/jobs\/([^/]+)$/);
  if (runMatch) return { name: 'run', jobId: decodeURIComponent(runMatch[1]) };
  if (path === '/jobs') return { name: 'console' };
  return { name: 'workspace' };
}

function setActiveNav(routeName) {
  document.querySelectorAll('.nav-button').forEach((button) => {
    const route = button.dataset.route;
    const active = routeName === 'workspace' ? route === '/editor' : route === '/jobs';
    button.classList.toggle('active', active);
  });
}

function closeEventSource() {
  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }
  if (state.runRefreshTimer) {
    clearTimeout(state.runRefreshTimer);
    state.runRefreshTimer = null;
  }
}

function navigate(path, { replace = false } = {}) {
  closeEventSource();
  if (replace) window.history.replaceState({}, '', path);
  else window.history.pushState({}, '', path);
  void renderRoute();
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const contentType = response.headers.get('content-type') || '';
  let payload;
  if (contentType.includes('application/json')) payload = await response.json();
  else payload = await response.text();
  if (!response.ok) {
    const detail = typeof payload === 'object' ? payload.detail : payload;
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }
  return payload;
}

function toast(message, kind = 'info', timeout = 3200) {
  const item = document.createElement('div');
  item.className = `toast ${kind}`;
  item.textContent = message;
  toastStack.append(item);
  window.setTimeout(() => item.remove(), timeout);
}

function confirmAction(title, message, confirmLabel = '确认') {
  return new Promise((resolve) => {
    const backdrop = document.createElement('div');
    backdrop.className = 'confirm-backdrop';
    backdrop.innerHTML = `
      <div class="confirm-dialog" role="dialog" aria-modal="true">
        <h2>${escapeHtml(title)}</h2>
        <p>${escapeHtml(message)}</p>
        <div class="confirm-actions">
          <button type="button" class="button" data-confirm="cancel">取消</button>
          <button type="button" class="button danger" data-confirm="ok">${escapeHtml(confirmLabel)}</button>
        </div>
      </div>`;
    document.body.append(backdrop);
    backdrop.addEventListener('click', (event) => {
      const action = event.target.closest('[data-confirm]')?.dataset.confirm;
      if (!action && event.target !== backdrop) return;
      backdrop.remove();
      resolve(action === 'ok');
    });
  });
}

async function checkHealth() {
  try {
    const health = await api('/health');
    healthDot.className = 'health-dot ok';
    healthCopy.textContent = '服务正常';
    healthCopy.title = health.workspace || '';
  } catch (error) {
    healthDot.className = 'health-dot error';
    healthCopy.textContent = '服务断开';
    healthCopy.title = error.message;
  }
}

async function refreshJobs({ render = true } = {}) {
  try {
    const payload = await api('/api/jobs');
    state.jobs = payload.jobs || [];
    const active = state.jobs.filter((job) => ['queued', 'running'].includes(job.status)).length;
    activeCount.textContent = String(active);
    activeCount.hidden = active === 0;
    const route = currentRoute();
    if (render && route.name === 'console') renderConsole();
    if (route.name === 'workspace') renderRecentJobs();
  } catch (error) {
    console.error(error);
  }
}

function renderRecentJobs() {
  const holder = document.querySelector('#recent-jobs');
  if (!holder) return;
  const jobs = state.jobs.slice(0, 14);
  holder.innerHTML = jobs.length
    ? jobs.map((job) => {
        const isActive = job.job_id === state.workspaceJobId;
        return `
          <button type="button" class="job-mini ${isActive ? 'active' : ''}" data-workspace-job="${attr(job.job_id)}">
            <div class="job-mini-top">
              ${statusBadge(job.status, true)}
              <span class="job-mini-name">${escapeHtml(job.input?.file_name || job.job_id)}</span>
            </div>
            <div class="job-mini-meta">
              <span>${escapeHtml(job.input?.parser || '—')} · ${formatTime(job.created_at)}</span>
              <span>${Math.round(clamp(job.progress) * 100)}%</span>
            </div>
            <div class="mini-progress"><span style="width:${Math.round(clamp(job.progress) * 100)}%"></span></div>
          </button>`;
      }).join('')
    : '<div class="tree-empty"><strong>还没有任务</strong><p>上传一个规范，或直接运行内置示例。</p></div>';
  holder.querySelectorAll('[data-workspace-job]').forEach((button) => {
    button.addEventListener('click', () => void selectWorkspaceJob(button.dataset.workspaceJob));
  });
}

async function init() {
  document.querySelector('#brand-home').addEventListener('click', () => navigate('/editor'));
  document.querySelectorAll('[data-route]').forEach((button) => {
    button.addEventListener('click', () => navigate(button.dataset.route));
  });
  window.addEventListener('popstate', () => {
    closeEventSource();
    void renderRoute();
  });
  await Promise.all([
    checkHealth(),
    api('/api/capabilities').then((value) => { state.capabilities = value; }).catch(() => null),
    refreshJobs({ render: false }),
  ]);
  await renderRoute();
  state.globalRefreshTimer = window.setInterval(() => {
    void refreshJobs();
    void checkHealth();
  }, 2200);
}

async function renderRoute() {
  const route = currentRoute();
  setActiveNav(route.name);
  if (route.name === 'run') {
    await loadRun(route.jobId);
    return;
  }
  closeEventSource();
  state.runJob = null;
  state.runEvents = [];
  if (route.name === 'console') {
    renderConsole();
    return;
  }
  await ensureWorkspaceJob();
  renderWorkspace();
}

async function ensureWorkspaceJob() {
  if (state.workspaceJobId && state.jobs.some((job) => job.job_id === state.workspaceJobId)) return;
  const candidate = state.jobs.find((job) => job.status === 'succeeded') || state.jobs[0];
  if (!candidate) return;
  await selectWorkspaceJob(candidate.job_id, { render: false });
}

async function selectWorkspaceJob(jobId, { render = true } = {}) {
  state.workspaceJobId = jobId;
  state.workspaceJob = null;
  state.result = null;
  state.selectedNodeId = null;
  state.sourceText = null;
  state.sourceTextJobId = null;
  try {
    const job = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
    state.workspaceJob = job;
    if (job.status === 'succeeded') {
      state.result = await api(`/api/jobs/${encodeURIComponent(jobId)}/result`);
      initializeTreeSelection();
    }
  } catch (error) {
    toast(error.message, 'error');
  }
  if (render) renderWorkspace();
}

function initializeTreeSelection() {
  state.expanded.clear();
  const result = state.result;
  if (!result) return;
  result.tree?.forEach((division) => {
    state.expanded.add(division.id);
    division.children?.forEach((lot) => state.expanded.add(lot.id));
  });
  const firstItem = result.tree?.[0]?.children?.[0]?.children?.[0];
  const firstLot = result.tree?.[0]?.children?.[0];
  const firstDivision = result.tree?.[0];
  state.selectedNodeId = firstItem?.id || firstLot?.id || firstDivision?.id || null;
}
