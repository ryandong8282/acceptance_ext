function fieldInput(label, field, value, options = {}) {
  const full = options.full ? ' full' : '';
  const required = options.required ? 'required' : '';
  const readonly = options.readonly ? 'readonly' : '';
  if (options.type === 'textarea') {
    return `<div class="field${full}"><label>${escapeHtml(label)}</label><textarea class="textarea" data-node-field="${attr(field)}" ${required} ${readonly}>${escapeHtml(value ?? '')}</textarea></div>`;
  }
  if (options.type === 'select') {
    return `<div class="field${full}"><label>${escapeHtml(label)}</label><select class="select" data-node-field="${attr(field)}">${options.values.map((entry) => `<option value="${attr(entry)}" ${entry === value ? 'selected' : ''}>${escapeHtml(entry)}</option>`).join('')}</select></div>`;
  }
  return `<div class="field${full}"><label>${escapeHtml(label)}</label><input class="input ${options.mono ? 'mono' : ''}" data-node-field="${attr(field)}" value="${attr(value ?? '')}" ${required} ${readonly} /></div>`;
}

function renderDetailForm(found) {
  if (!found) return '<div class="tree-empty"><strong>选择一个节点</strong><p>这里会显示可编辑字段、原文证据、页码与坐标。</p></div>';
  const node = found.node;
  let fields = '';
  if (found.type === '分项') {
    fields = [
      fieldInput('名称', 'name', node.name, { full: true, required: true }),
      fieldInput('章节号', 'chapter_no', node.chapter_no, { mono: true }),
      fieldInput('50300 路径（用 / 分隔）', 'mapped_50300_path', (node.mapped_50300_path || []).join(' / '), { full: true }),
      fieldInput('映射分数', 'mapping_score', node.mapping_score, { mono: true }),
    ].join('');
  } else if (found.type === '检验批') {
    fields = [
      fieldInput('名称', 'name', node.name, { full: true, required: true }),
      fieldInput('来源标题', 'source_title', node.source_title, { full: true }),
      fieldInput('章节号', 'chapter_no', node.chapter_no, { mono: true }),
      fieldInput('PDF 页', 'pdf_page', node.pdf_page, { mono: true }),
    ].join('');
  } else {
    fields = [
      fieldInput('验收项目名称', 'name', node.name, { full: true, required: true }),
      fieldInput('条款号', 'source_clause', node.source_clause, { mono: true }),
      fieldInput('项目类别', 'item_category', node.item_category, { type: 'select', values: ['主控项目', '一般项目', '未分类'] }),
      fieldInput('检查数量', 'check_quantity', node.check_quantity, { full: true }),
      fieldInput('最小抽样', 'min_sampling', node.min_sampling, { full: true }),
      fieldInput('抽样依据', 'min_sampling_reason', node.min_sampling_reason, { full: true, type: 'textarea' }),
      fieldInput('检验方法', 'check_method', node.check_method, { full: true, type: 'textarea' }),
      fieldInput('原文条款', 'source_quote', node.source_quote, { full: true, type: 'textarea', required: true }),
      fieldInput('置信度', 'confidence', node.confidence, { mono: true }),
    ].join('');
  }
  const evidence = found.type === '验收项目' ? renderEvidence(node.evidence || []) : '';
  return `
    <form class="detail-form" id="node-form">
      <div class="detail-form-grid">${fields}</div>
      ${evidence}
      <div class="detail-actions">
        <button type="button" class="button" id="open-source-tab">查看原文</button>
        <button type="submit" class="button primary">保存修改</button>
      </div>
    </form>`;
}

function renderEvidence(evidence) {
  if (!evidence.length) return '<div class="error-box">当前节点没有原文证据。</div>';
  return evidence.map((item, index) => `
    <div class="evidence-card">
      <div class="section-kicker">Evidence ${index + 1}</div>
      <blockquote>${escapeHtml(item.quote)}</blockquote>
      <div class="evidence-meta">
        <span class="badge">${escapeHtml(item.method || 'exact')}</span>
        <span class="badge">${escapeHtml(item.parser || 'parser')}</span>
        ${item.page ? `<span class="badge">PDF p.${item.page}</span>` : ''}
        ${item.line_start ? `<span class="badge">L${item.line_start}${item.line_end && item.line_end !== item.line_start ? `–${item.line_end}` : ''}</span>` : ''}
        ${item.bbox ? `<span class="badge mono">bbox ${escapeHtml(item.bbox.join(', '))}</span>` : ''}
      </div>
    </div>`).join('');
}

function bindDetailForm() {
  document.querySelector('#node-form')?.addEventListener('submit', (event) => {
    event.preventDefault();
    void saveSelectedNode();
  });
  document.querySelector('#open-source-tab')?.addEventListener('click', () => {
    state.detailTab = 'source';
    renderWorkspace();
    void ensureSourceText();
  });
}

async function saveSelectedNode() {
  const found = findNode(state.selectedNodeId);
  if (!found || !state.workspaceJobId || !state.result) return;
  const node = found.node;
  document.querySelectorAll('[data-node-field]').forEach((element) => {
    const field = element.dataset.nodeField;
    const raw = element.value.trim();
    if (field === 'mapped_50300_path') {
      node[field] = raw ? raw.split(/\s*[/>]\s*/).filter(Boolean) : [];
    } else if (['mapping_score', 'confidence'].includes(field)) {
      node[field] = raw === '' ? null : Number(raw);
    } else if (['pdf_page'].includes(field)) {
      node[field] = raw === '' ? null : Number.parseInt(raw, 10);
    } else {
      node[field] = raw === '' && !['name', 'source_quote'].includes(field) ? null : raw;
    }
  });
  try {
    state.result = await api(`/api/jobs/${encodeURIComponent(state.workspaceJobId)}/result`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(state.result),
    });
    state.workspaceJob = await api(`/api/jobs/${encodeURIComponent(state.workspaceJobId)}`);
    toast('修订已保存，并记录到 Job 事件流', 'success');
    renderWorkspace();
  } catch (error) {
    toast(error.message, 'error', 5000);
  }
}

function selectedEvidencePage(found) {
  const node = found?.node;
  return node?.evidence?.find((item) => item.page)?.page || node?.pdf_page || node?.source_page || 1;
}

function renderSource(found) {
  const job = state.workspaceJob;
  if (!job) return '<div class="tree-empty"><strong>没有原文</strong></div>';
  const isPdf = String(job.input?.file_name || '').toLowerCase().endsWith('.pdf');
  if (isPdf) {
    const page = selectedEvidencePage(found);
    return `<iframe class="source-frame" title="PDF 原文" src="${attr(job.output.source_url)}#page=${page}&view=FitH"></iframe>`;
  }
  if (state.sourceTextJobId !== job.job_id || state.sourceText === null) {
    return '<div class="loading-screen"><div><div class="loading-mark"></div><p>读取原文…</p></div></div>';
  }
  const quote = found?.node?.source_quote || found?.node?.evidence?.[0]?.quote;
  let text = escapeHtml(state.sourceText);
  if (quote) {
    const escapedQuote = escapeHtml(quote);
    text = text.replace(escapedQuote, `<mark>${escapedQuote}</mark>`);
  }
  return `<pre class="source-text">${text}</pre>`;
}

async function ensureSourceText() {
  const job = state.workspaceJob;
  if (!job || String(job.input?.file_name || '').toLowerCase().endsWith('.pdf')) return;
  if (state.sourceTextJobId === job.job_id && state.sourceText !== null) return;
  try {
    const response = await fetch(job.output.source_url);
    if (!response.ok) throw new Error(await response.text());
    state.sourceText = await response.text();
    state.sourceTextJobId = job.job_id;
    if (currentRoute().name === 'workspace' && state.detailTab === 'source') {
      const body = document.querySelector('#detail-body');
      if (body) body.innerHTML = renderSource(findNode(state.selectedNodeId));
    }
  } catch (error) {
    toast(`读取原文失败：${error.message}`, 'error');
  }
}
