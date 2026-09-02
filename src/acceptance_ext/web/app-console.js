function currentStageLabel(job) {
  return job?.stages?.find((stage) => stage.key === job.current_stage)?.label || job?.current_stage || '等待执行';
}

function renderConsole() {
  const query = state.consoleSearch.trim().toLowerCase();
  const jobs = state.jobs.filter((job) => {
    if (state.consoleStatus !== 'all' && job.status !== state.consoleStatus) return false;
    if (!query) return true;
    return [job.job_id, job.input?.file_name, job.input?.parser, job.input?.extractor, job.error]
      .filter(Boolean).join(' ').toLowerCase().includes(query);
  });
  const grouped = groupJobsByDate(jobs);
  screen.innerHTML = `
    <div class="console-layout">
      <header class="console-header">
        <div class="console-heading">
          <h1>运行控制台</h1>
          <p>真实后台 Job、阶段进度、失败原因和重跑入口都在这里。</p>
        </div>
        <div class="console-tools">
          <input class="input" id="console-search" value="${attr(state.consoleSearch)}" placeholder="任务、文件、解析器…" />
          <div class="segmented" id="status-filter">
            ${['all', 'running', 'queued', 'succeeded', 'failed', 'cancelled'].map((status) => `<button type="button" data-status="${status}" class="${state.consoleStatus === status ? 'active' : ''}">${status === 'all' ? '全部' : STATUS_LABELS[status]}</button>`).join('')}
          </div>
          <button type="button" class="button" id="console-demo">执行示例</button>
          <button type="button" class="button primary" id="console-new">新建抽取</button>
        </div>
      </header>
      <div class="console-body">
        ${jobs.length ? [...grouped.entries()].map(([label, rows]) => renderJobGroup(label, rows)).join('') : `
          <div class="console-empty"><h2>没有符合条件的任务</h2><p>新建一次抽取，或者运行内置示例，马上可以看到完整的阶段时间线。</p><button type="button" class="button primary" id="console-empty-demo">执行内置示例</button></div>`}
      </div>
    </div>`;
  bindConsole();
}

function groupJobsByDate(jobs) {
  const groups = new Map();
  const today = new Date();
  const yesterday = new Date(Date.now() - 86400000);
  for (const job of jobs) {
    const date = new Date(job.created_at);
    let label = date.toLocaleDateString('zh-CN');
    if (date.toDateString() === today.toDateString()) label = '今天';
    else if (date.toDateString() === yesterday.toDateString()) label = '昨天';
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(job);
  }
  return groups;
}

function renderJobGroup(label, jobs) {
  return `
    <section class="job-group">
      <h2 class="job-group-title">${escapeHtml(label)} · ${jobs.length}</h2>
      <table class="job-table">
        <colgroup><col style="width:34%"><col style="width:11%"><col style="width:19%"><col style="width:13%"><col style="width:10%"><col style="width:13%"></colgroup>
        <thead><tr><th>文档 / Job</th><th>状态</th><th>进度</th><th>执行配置</th><th>耗时</th><th></th></tr></thead>
        <tbody>${jobs.map(renderJobRow).join('')}</tbody>
      </table>
    </section>`;
}

function renderJobRow(job) {
  const progress = Math.round(clamp(job.progress) * 100);
  const ext = (job.input?.file_name?.split('.').pop() || 'DOC').slice(0, 4).toUpperCase();
  return `
    <tr data-open-job="${attr(job.job_id)}">
      <td><div class="job-name-cell"><span class="file-glyph">${escapeHtml(ext)}</span><span class="job-name-copy"><strong>${escapeHtml(job.input?.file_name || job.job_id)}</strong><small>${escapeHtml(job.job_id)} · ${formatTime(job.created_at, true)}</small></span></div></td>
      <td>${statusBadge(job.status)}</td>
      <td><div class="row-progress"><div class="progress-track ${job.status}"><span style="width:${progress}%"></span></div><span class="mono faint">${progress}%</span></div></td>
      <td><span class="mono">${escapeHtml(job.input?.parser || '—')}</span><br><span class="faint">${escapeHtml(job.input?.extractor || '—')}</span></td>
      <td class="mono">${formatDuration(job.started_at, job.finished_at)}</td>
      <td><div class="row-actions">
        ${job.status === 'succeeded' ? `<button class="button small" type="button" data-job-action="result" data-job-id="${attr(job.job_id)}">结果</button>` : ''}
        ${['queued', 'running'].includes(job.status) ? `<button class="button small danger" type="button" data-job-action="cancel" data-job-id="${attr(job.job_id)}">取消</button>` : `<button class="button small" type="button" data-job-action="restart" data-job-id="${attr(job.job_id)}">重跑</button>`}
        ${TERMINAL.has(job.status) ? `<button class="button small quiet" type="button" data-job-action="delete" data-job-id="${attr(job.job_id)}">删除</button>` : ''}
      </div></td>
    </tr>`;
}

function bindConsole() {
  document.querySelector('#console-search')?.addEventListener('input', (event) => {
    state.consoleSearch = event.target.value;
    renderConsole();
    document.querySelector('#console-search')?.focus();
  });
  document.querySelectorAll('[data-status]').forEach((button) => {
    button.addEventListener('click', () => {
      state.consoleStatus = button.dataset.status;
      renderConsole();
    });
  });
  document.querySelector('#console-new')?.addEventListener('click', () => navigate('/editor'));
  document.querySelector('#console-demo')?.addEventListener('click', () => void submitDemo());
  document.querySelector('#console-empty-demo')?.addEventListener('click', () => void submitDemo());
  document.querySelectorAll('[data-open-job]').forEach((row) => {
    row.addEventListener('click', (event) => {
      if (event.target.closest('[data-job-action]')) return;
      navigate(`/jobs/${encodeURIComponent(row.dataset.openJob)}`);
    });
  });
  document.querySelectorAll('[data-job-action]').forEach((button) => {
    button.addEventListener('click', (event) => {
      event.stopPropagation();
      void handleJobAction(button.dataset.jobAction, button.dataset.jobId);
    });
  });
}

async function handleJobAction(action, jobId) {
  try {
    if (action === 'result') {
      await selectWorkspaceJob(jobId, { render: false });
      navigate('/editor');
      return;
    }
    if (action === 'cancel') {
      await api(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' });
      toast('取消请求已发送');
    } else if (action === 'restart') {
      const job = await api(`/api/jobs/${encodeURIComponent(jobId)}/restart`, { method: 'POST' });
      await refreshJobs({ render: false });
      navigate(`/jobs/${encodeURIComponent(job.job_id)}`);
      return;
    } else if (action === 'delete') {
      const ok = await confirmAction('删除任务', '源文件、事件日志和结果都会从本地工作区删除。', '删除');
      if (!ok) return;
      await api(`/api/jobs/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
      if (state.workspaceJobId === jobId) {
        state.workspaceJobId = null;
        state.workspaceJob = null;
        state.result = null;
      }
      toast('任务已删除', 'success');
    }
    await refreshJobs();
  } catch (error) {
    toast(error.message, 'error');
  }
}
