async function loadRun(jobId) {
  closeEventSource();
  screen.innerHTML = '<div class="loading-screen"><div><div class="loading-mark"></div><p>载入运行记录…</p></div></div>';
  try {
    const [job, events] = await Promise.all([
      api(`/api/jobs/${encodeURIComponent(jobId)}`),
      loadAllEvents(jobId),
    ]);
    state.runJob = job;
    state.runEvents = events;
    renderRun();
    if (!TERMINAL.has(job.status)) connectJobStream(jobId);
  } catch (error) {
    screen.innerHTML = `<div class="empty-screen"><div class="console-empty"><h2>无法打开任务</h2><p>${escapeHtml(error.message)}</p><button type="button" class="button" id="run-load-back">返回控制台</button></div></div>`;
    document.querySelector('#run-load-back')?.addEventListener('click', () => navigate('/jobs'));
  }
}

async function loadAllEvents(jobId) {
  let cursor = 0;
  const events = [];
  while (true) {
    const page = await api(`/api/jobs/${encodeURIComponent(jobId)}/event-log?cursor=${cursor}&limit=500`);
    events.push(...(page.events || []));
    if (page.next_cursor === null || page.next_cursor === undefined) break;
    cursor = page.next_cursor;
  }
  return events;
}

function renderRun() {
  const job = state.runJob;
  if (!job) return;
  const oldScroll = document.querySelector('#timeline-scroll');
  const previousTop = oldScroll?.scrollTop || 0;
  const nearBottom = !oldScroll || oldScroll.scrollHeight - oldScroll.scrollTop - oldScroll.clientHeight < 90;
  const progress = Math.round(clamp(job.progress) * 100);
  screen.innerHTML = `
    <div class="run-layout">
      <header class="run-header">
        <button type="button" class="button icon run-back" id="run-back" title="返回运行控制台">←</button>
        <div class="run-title"><strong>${escapeHtml(job.input?.file_name || job.job_id)}</strong><small>${escapeHtml(job.job_id)} · ${escapeHtml(job.input?.parser)} / ${escapeHtml(job.input?.extractor)}</small></div>
        ${statusBadge(job.status)}
        <span class="run-progress-number">${progress}%</span>
        <div class="run-header-actions">
          ${job.status === 'succeeded' ? '<button type="button" class="button primary" id="run-result">查看抽取结果</button>' : ''}
          ${['queued', 'running'].includes(job.status) ? '<button type="button" class="button danger" id="run-cancel">取消任务</button>' : '<button type="button" class="button" id="run-restart">重新执行</button>'}
        </div>
      </header>
      <div class="run-body">
        <aside class="stage-panel">
          <div class="panel-header"><div class="panel-title"><strong>执行阶段</strong><small>${job.stages?.length || 0} 个阶段</small></div></div>
          <div class="stage-list">${(job.stages || []).map(renderStage).join('')}</div>
        </aside>
        <section class="timeline-panel">
          <div class="timeline-header"><div class="panel-title"><strong>运行时间线</strong><small>${state.runEvents.length} 条事件 · 实时写入 events.jsonl</small></div><button type="button" class="button small quiet" id="toggle-follow">${state.runAutoFollow ? '自动跟随：开' : '自动跟随：关'}</button></div>
          <div class="timeline-scroll" id="timeline-scroll">${state.runEvents.map(renderTimelineEvent).join('') || '<div class="tree-empty"><strong>等待第一条事件</strong><p>任务创建后，解析器开始工作时会在这里出现阶段记录。</p></div>'}</div>
          <div class="running-dock">
            <div class="running-copy">当前：<strong>${escapeHtml(currentStageLabel(job))}</strong></div>
            <div class="progress-track ${job.status}"><span style="width:${progress}%"></span></div>
            <span class="mono faint">${progress}%</span>
          </div>
        </section>
        <aside class="run-meta-panel">${renderRunMeta(job)}</aside>
      </div>
    </div>`;
  bindRun();
  const scroll = document.querySelector('#timeline-scroll');
  if (scroll) {
    if (state.runAutoFollow && nearBottom) scroll.scrollTop = scroll.scrollHeight;
    else scroll.scrollTop = previousTop;
    scroll.addEventListener('scroll', () => {
      const remaining = scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight;
      if (remaining > 140) state.runAutoFollow = false;
    });
  }
}
