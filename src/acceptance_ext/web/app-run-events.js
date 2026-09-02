function renderStage(stage) {
  const status = stage.status || 'pending';
  const symbol = status === 'done' ? '✓' : status === 'failed' ? '!' : status === 'cancelled' ? '×' : status === 'skipped' ? '–' : status === 'running' ? '•' : '';
  return `
    <div class="stage-item ${attr(status)}">
      <span class="stage-symbol">${symbol}</span>
      <div class="stage-copy">
        <strong>${escapeHtml(stage.label || stage.key)}</strong>
        <p>${escapeHtml(stage.detail || STATUS_LABELS[status] || status)}</p>
        <small>${stage.started_at ? formatTime(stage.started_at) : '—'}${stage.finished_at ? ` → ${formatTime(stage.finished_at)}` : ''}</small>
      </div>
    </div>`;
}

function renderTimelineEvent(event) {
  const payload = event.payload && Object.keys(event.payload).length ? event.payload : null;
  const showPayload = payload && (event.kind === 'error' || event.kind === 'summary');
  return `
    <article class="timeline-event ${attr(event.state || '')} ${attr(event.kind || '')}">
      <time class="event-time">${formatTime(event.ts)}</time>
      <span class="event-pin"></span>
      <div class="event-card">
        <div class="event-card-head"><strong>${escapeHtml(event.title)}</strong><span class="badge ${attr(event.state)}">${escapeHtml(STATUS_LABELS[event.state] || event.state)}</span><span class="event-stage">${escapeHtml(event.stage)}</span></div>
        ${event.detail ? `<div class="event-detail">${escapeHtml(event.detail)}</div>` : ''}
        ${showPayload ? `<pre class="event-payload">${escapeHtml(JSON.stringify(payload, null, 2))}</pre>` : ''}
      </div>
    </article>`;
}

function renderRunMeta(job) {
  const metrics = job.metrics || {};
  const hasMetrics = Object.keys(metrics).length > 0;
  return `
    <div class="panel-header"><div class="panel-title"><strong>运行信息</strong><small>可审计的任务元数据</small></div></div>
    <section class="meta-section">
      <h3>任务</h3>
      <dl class="meta-grid">
        <dt>状态</dt><dd>${escapeHtml(STATUS_LABELS[job.status] || job.status)}</dd>
        <dt>创建</dt><dd>${formatTime(job.created_at, true)}</dd>
        <dt>开始</dt><dd>${formatTime(job.started_at, true)}</dd>
        <dt>结束</dt><dd>${formatTime(job.finished_at, true)}</dd>
        <dt>耗时</dt><dd>${formatDuration(job.started_at, job.finished_at)}</dd>
        <dt>源文件</dt><dd>${escapeHtml(job.input?.file_name)}</dd>
        <dt>大小</dt><dd>${formatBytes(job.input?.size)}</dd>
        <dt>Parser</dt><dd class="mono">${escapeHtml(job.input?.parser)}</dd>
        <dt>Extractor</dt><dd class="mono">${escapeHtml(job.input?.extractor)}</dd>
        <dt>修订版本</dt><dd>${Number(job.result_revision || 0)}</dd>
      </dl>
      <div style="display:flex;gap:6px;margin-top:10px">
        <a class="button small" href="${attr(job.output?.source_url)}" target="_blank" rel="noreferrer">打开源文档</a>
        ${job.status === 'succeeded' ? `<a class="button small" href="${attr(job.output?.download_url)}">下载结果</a>` : ''}
      </div>
      ${job.error ? `<div class="error-box">${escapeHtml(job.error)}</div>` : ''}
    </section>
    <section class="meta-section">
      <h3>结果指标</h3>
      ${hasMetrics ? `<div class="metric-list">${Object.entries(metrics).map(([key, value]) => `<div class="metric-tile"><strong>${escapeHtml(formatMetric(key, value))}</strong><small>${escapeHtml(metricLabel(key))}</small></div>`).join('')}</div>` : '<p class="muted" style="font-size:10px">任务完成后显示结构数量、证据覆盖和耗时。</p>'}
    </section>
    <section class="meta-section">
      <h3>本地落盘</h3>
      <p class="muted" style="font-size:10px;line-height:1.6;margin:0">每个 Job 独立保存 source、job.json、events.jsonl 和 result.json。服务重启后历史任务仍会出现在控制台。</p>
    </section>`;
}

function bindRun() {
  const job = state.runJob;
  document.querySelector('#run-back')?.addEventListener('click', () => navigate('/jobs'));
  document.querySelector('#run-result')?.addEventListener('click', async () => {
    await selectWorkspaceJob(job.job_id, { render: false });
    navigate('/editor');
  });
  document.querySelector('#run-cancel')?.addEventListener('click', () => void handleRunCancel(job.job_id));
  document.querySelector('#run-restart')?.addEventListener('click', () => void handleRunRestart(job.job_id));
  document.querySelector('#toggle-follow')?.addEventListener('click', () => {
    state.runAutoFollow = !state.runAutoFollow;
    renderRun();
  });
}

async function handleRunCancel(jobId) {
  try {
    state.runJob = await api(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' });
    toast('取消请求已发送');
    renderRun();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function handleRunRestart(jobId) {
  try {
    const job = await api(`/api/jobs/${encodeURIComponent(jobId)}/restart`, { method: 'POST' });
    await refreshJobs({ render: false });
    navigate(`/jobs/${encodeURIComponent(job.job_id)}`);
  } catch (error) {
    toast(error.message, 'error');
  }
}

function connectJobStream(jobId) {
  closeEventSource();
  const lastSeq = state.runEvents.at(-1)?.seq || 0;
  const source = new EventSource(`/api/jobs/${encodeURIComponent(jobId)}/events?cursor=${lastSeq}`);
  state.eventSource = source;
  source.onmessage = (message) => {
    try {
      const event = JSON.parse(message.data);
      if (!state.runEvents.some((entry) => entry.seq === event.seq)) state.runEvents.push(event);
      scheduleRunRefresh(jobId);
    } catch (error) {
      console.error(error);
    }
  };
  source.addEventListener('terminal', () => {
    source.close();
    if (state.eventSource === source) state.eventSource = null;
    scheduleRunRefresh(jobId, true);
    void refreshJobs({ render: false });
  });
  source.onerror = () => {
    source.close();
    if (state.eventSource === source) state.eventSource = null;
    scheduleRunRefresh(jobId, true);
  };
}

function scheduleRunRefresh(jobId, reconnect = false) {
  if (state.runRefreshTimer) return;
  state.runRefreshTimer = window.setTimeout(async () => {
    state.runRefreshTimer = null;
    if (currentRoute().name !== 'run' || currentRoute().jobId !== jobId) return;
    try {
      state.runJob = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
      renderRun();
      if (reconnect && !TERMINAL.has(state.runJob.status) && !state.eventSource) {
        window.setTimeout(() => connectJobStream(jobId), 900);
      }
    } catch (error) {
      console.error(error);
    }
  }, 120);
}

void init();
