function uploadPanel() {
  const file = state.selectedFile;
  return `
    <section class="upload-block">
      <div class="section-kicker">新建抽取</div>
      <label class="dropzone" id="dropzone">
        <input id="file-input" type="file" accept=".pdf,.md,.markdown,.txt,application/pdf,text/markdown,text/plain" />
        <div>
          <span class="dropzone-icon">⇧</span>
          <strong>拖入 PDF / Markdown</strong>
          <small>单份规范，最大 160 MB</small>
        </div>
      </label>
      <div class="file-picked" id="file-picked" ${file ? '' : 'hidden'}>${file ? `${escapeHtml(file.name)} · ${formatBytes(file.size)}` : ''}</div>
      <div class="upload-options">
        <div class="field">
          <label for="parser-select">Parser</label>
          <select class="select" id="parser-select">
            <option value="auto">自动选择</option>
            <option value="markdown">Markdown</option>
            <option value="pymupdf">PyMuPDF</option>
            <option value="docling">Docling</option>
            <option value="mineru">MinerU 命令</option>
            <option value="paddleocr">PaddleOCR 命令</option>
          </select>
        </div>
        <div class="field">
          <label for="extractor-select">Extractor</label>
          <select class="select" id="extractor-select">
            <option value="heuristic">确定性基线</option>
            <option value="openai-compatible">LLM 复核</option>
          </select>
        </div>
      </div>
      <div class="upload-actions">
        <button type="button" class="button primary" id="start-extract" ${file ? '' : 'disabled'}>开始抽取</button>
        <button type="button" class="button" id="run-demo" title="不用准备文件，直接观看完整 Job 流程">执行示例</button>
      </div>
    </section>`;
}

function workspaceCenter() {
  const job = state.workspaceJob;
  if (!job) {
    return `
      <div class="panel-header"><div class="panel-title"><strong>结构结果</strong><small>等待选择任务</small></div></div>
      <div class="tree-empty"><strong>从一份规范开始</strong><p>左侧上传 PDF 或 Markdown。任务进入后台后，会自动跳到运行时间线；完成后返回这里核对结构。</p><button class="button primary" type="button" id="empty-demo">执行内置示例</button></div>`;
  }
  if (job.status !== 'succeeded') {
    const message = job.status === 'failed'
      ? `<div class="error-box">${escapeHtml(job.error || '任务失败')}</div>`
      : `<p>当前阶段：${escapeHtml(currentStageLabel(job))} · ${Math.round(clamp(job.progress) * 100)}%</p>`;
    return `
      <div class="panel-header">
        <div class="panel-title"><strong>${escapeHtml(job.input?.file_name)}</strong><small>${escapeHtml(job.job_id)}</small></div>
        ${statusBadge(job.status)}
      </div>
      <div class="tree-empty">
        <strong>${job.status === 'failed' ? '这次没有生成结果' : '任务仍在后台执行'}</strong>
        ${message}
        <button class="button primary" type="button" id="open-current-run">打开执行详情</button>
      </div>`;
  }
  const result = state.result;
  const metrics = result?.metrics || job.metrics || {};
  return `
    <div>
      <div class="panel-header">
        <div class="panel-title">
          <strong>${escapeHtml(result?.standard_no || result?.standard_name || job.input?.file_name)}</strong>
          <small>${escapeHtml(result?.standard_name || job.input?.file_name)} · ${escapeHtml(result?.parser)} / ${escapeHtml(result?.extractor)}</small>
        </div>
        <div style="display:flex;gap:6px;align-items:center">
          <span class="badge">rev ${Number(job.result_revision || 0)}</span>
          ${statusBadge(job.status)}
        </div>
      </div>
      <div class="metrics-strip">
        ${['division_count', 'inspection_lot_count', 'acceptance_item_count', 'grounding_rate'].map((key) => `
          <div class="metric-cell"><strong>${escapeHtml(formatMetric(key, metrics[key]))}</strong><small>${escapeHtml(metricLabel(key))}</small></div>`).join('')}
      </div>
      <div class="result-toolbar">
        <input class="input" id="tree-filter" value="${attr(state.treeFilter)}" placeholder="筛选分项、检验批、验收项目…" />
        <button type="button" class="button small" id="expand-tree">全部展开</button>
        <button type="button" class="button small" id="collapse-tree">折叠</button>
      </div>
    </div>
    <div class="tree-scroll" id="result-tree">${renderTree(result)}</div>`;
}

function workspaceDetail() {
  const job = state.workspaceJob;
  const result = state.result;
  const found = findNode(state.selectedNodeId);
  const title = found?.node?.name || '节点详情';
  return `
    <div>
      <div class="panel-header">
        <div class="panel-title"><strong>${escapeHtml(title)}</strong><small>${found ? escapeHtml(found.type) : '选择结构树中的节点'}</small></div>
        ${job?.status === 'succeeded' ? `<a class="button small" href="${attr(job.output?.download_url)}">导出 JSON</a>` : ''}
      </div>
      <div class="detail-tabs">
        <button type="button" class="detail-tab ${state.detailTab === 'detail' ? 'active' : ''}" data-detail-tab="detail">字段与证据</button>
        <button type="button" class="detail-tab ${state.detailTab === 'source' ? 'active' : ''}" data-detail-tab="source">原文</button>
        <button type="button" class="detail-tab ${state.detailTab === 'json' ? 'active' : ''}" data-detail-tab="json">结果 JSON</button>
      </div>
    </div>
    <div class="detail-body" id="detail-body">
      ${state.detailTab === 'detail' ? renderDetailForm(found) : state.detailTab === 'source' ? renderSource(found) : `<pre class="json-view">${escapeHtml(JSON.stringify(result || {}, null, 2))}</pre>`}
    </div>`;
}

function renderWorkspace() {
  screen.innerHTML = `
    <div class="workspace-layout">
      <aside class="workspace-sidebar">
        <div class="panel-header"><div class="panel-title"><strong>输入与运行</strong><small>同一个入口创建 Job</small></div></div>
        ${uploadPanel()}
        <div id="recent-jobs" class="job-mini-list"></div>
      </aside>
      <section class="workspace-tree">${workspaceCenter()}</section>
      <aside class="workspace-detail">${workspaceDetail()}</aside>
    </div>`;
  renderRecentJobs();
  bindWorkspace();
}

function bindWorkspace() {
  const input = document.querySelector('#file-input');
  const dropzone = document.querySelector('#dropzone');
  if (input) {
    input.addEventListener('change', () => setSelectedFile(input.files?.[0] || null));
  }
  if (dropzone) {
    ['dragenter', 'dragover'].forEach((name) => dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.add('dragover');
    }));
    ['dragleave', 'drop'].forEach((name) => dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.remove('dragover');
    }));
    dropzone.addEventListener('drop', (event) => setSelectedFile(event.dataTransfer?.files?.[0] || null));
  }
  document.querySelector('#start-extract')?.addEventListener('click', () => void submitUpload());
  document.querySelector('#run-demo')?.addEventListener('click', () => void submitDemo());
  document.querySelector('#empty-demo')?.addEventListener('click', () => void submitDemo());
  document.querySelector('#open-current-run')?.addEventListener('click', () => navigate(`/jobs/${encodeURIComponent(state.workspaceJobId)}`));
  document.querySelector('#tree-filter')?.addEventListener('input', (event) => {
    state.treeFilter = event.target.value;
    const tree = document.querySelector('#result-tree');
    if (tree) tree.innerHTML = renderTree(state.result);
    bindTreeEvents();
  });
  document.querySelector('#expand-tree')?.addEventListener('click', () => {
    state.result?.tree?.forEach((division) => {
      state.expanded.add(division.id);
      division.children?.forEach((lot) => state.expanded.add(lot.id));
    });
    rerenderTreeAndDetail();
  });
  document.querySelector('#collapse-tree')?.addEventListener('click', () => {
    state.expanded.clear();
    rerenderTreeAndDetail();
  });
  document.querySelectorAll('[data-detail-tab]').forEach((button) => {
    button.addEventListener('click', () => {
      state.detailTab = button.dataset.detailTab;
      renderWorkspace();
      if (state.detailTab === 'source') void ensureSourceText();
    });
  });
  bindTreeEvents();
  bindDetailForm();
  if (state.detailTab === 'source') void ensureSourceText();
}

function setSelectedFile(file) {
  state.selectedFile = file;
  const holder = document.querySelector('#file-picked');
  const button = document.querySelector('#start-extract');
  if (holder) {
    holder.hidden = !file;
    holder.textContent = file ? `${file.name} · ${formatBytes(file.size)}` : '';
  }
  if (button) button.disabled = !file;
}

async function submitUpload() {
  if (!state.selectedFile) return;
  const button = document.querySelector('#start-extract');
  const parser = document.querySelector('#parser-select')?.value || 'auto';
  const extractor = document.querySelector('#extractor-select')?.value || 'heuristic';
  const data = new FormData();
  data.append('file', state.selectedFile);
  data.append('parser', parser);
  data.append('extractor', extractor);
  if (button) {
    button.disabled = true;
    button.textContent = '正在创建…';
  }
  try {
    const job = await api('/api/jobs', { method: 'POST', body: data });
    state.selectedFile = null;
    await refreshJobs({ render: false });
    navigate(`/jobs/${encodeURIComponent(job.job_id)}`);
  } catch (error) {
    toast(error.message, 'error', 5000);
    if (button) {
      button.disabled = false;
      button.textContent = '开始抽取';
    }
  }
}

async function submitDemo() {
  try {
    const job = await api('/api/jobs/demo', { method: 'POST' });
    await refreshJobs({ render: false });
    navigate(`/jobs/${encodeURIComponent(job.job_id)}`);
  } catch (error) {
    toast(error.message, 'error');
  }
}
