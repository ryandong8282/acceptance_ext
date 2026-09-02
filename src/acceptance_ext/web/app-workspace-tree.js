function nodeMatches(node, filter) {
  if (!filter) return true;
  const text = [node.name, node.source_clause, node.source_quote, node.item_category, node.source_title].filter(Boolean).join(' ').toLowerCase();
  if (text.includes(filter)) return true;
  return node.children?.some((child) => nodeMatches(child, filter)) || false;
}

function renderTree(result) {
  if (!result?.tree?.length) return '<div class="tree-empty"><strong>没有识别出结构节点</strong><p>可以打开运行详情查看各阶段输出和审计提示。</p></div>';
  const filter = state.treeFilter.trim().toLowerCase();
  const rows = result.tree.filter((node) => nodeMatches(node, filter)).map((division) => renderTreeNode(division, 'division', filter)).join('');
  return rows || '<div class="tree-empty"><strong>没有匹配项</strong><p>换一个关键词试试。</p></div>';
}

function renderTreeNode(node, type, filter) {
  const children = (node.children || []).filter((child) => nodeMatches(child, filter));
  const hasChildren = children.length > 0;
  const expanded = filter || state.expanded.has(node.id);
  const selected = node.id === state.selectedNodeId;
  const categoryClass = node.item_category === '主控项目' ? 'control' : node.item_category === '一般项目' ? 'general' : '';
  const kind = type === 'division' ? '分项' : type === 'lot' ? '批' : node.source_clause || '项';
  const meta = type === 'division'
    ? `${children.length} 批${node.mapping_score ? ` · ${Math.round(node.mapping_score * 100)}%` : ''}`
    : type === 'lot'
      ? `${children.length} 项`
      : node.item_category || '';
  const row = `
    <div class="tree-node">
      <button type="button" class="tree-row ${type} ${selected ? 'selected' : ''}" data-node-id="${attr(node.id)}">
        <span class="tree-toggle" data-toggle-id="${attr(node.id)}">${hasChildren ? (expanded ? '▼' : '▶') : '·'}</span>
        ${type === 'item' ? `<span class="tree-category ${categoryClass}"></span>` : ''}
        <span class="tree-kind">${escapeHtml(kind)}</span>
        <span class="tree-name">${escapeHtml(node.name)}</span>
        <span class="tree-meta">${escapeHtml(meta)}</span>
      </button>
      ${hasChildren && expanded ? `<div class="tree-children">${children.map((child) => renderTreeNode(child, type === 'division' ? 'lot' : 'item', filter)).join('')}</div>` : ''}
    </div>`;
  return row;
}

function bindTreeEvents() {
  document.querySelectorAll('[data-node-id]').forEach((row) => {
    row.addEventListener('click', (event) => {
      const toggle = event.target.closest('[data-toggle-id]');
      if (toggle && row.querySelector('.tree-toggle')?.textContent !== '·') {
        const id = toggle.dataset.toggleId;
        if (state.expanded.has(id)) state.expanded.delete(id);
        else state.expanded.add(id);
      } else {
        state.selectedNodeId = row.dataset.nodeId;
        state.detailTab = 'detail';
      }
      rerenderTreeAndDetail();
    });
  });
}

function rerenderTreeAndDetail() {
  const tree = document.querySelector('#result-tree');
  if (tree) tree.innerHTML = renderTree(state.result);
  const detail = document.querySelector('.workspace-detail');
  if (detail) detail.innerHTML = workspaceDetail();
  bindTreeEvents();
  document.querySelectorAll('[data-detail-tab]').forEach((button) => {
    button.addEventListener('click', () => {
      state.detailTab = button.dataset.detailTab;
      renderWorkspace();
      if (state.detailTab === 'source') void ensureSourceText();
    });
  });
  bindDetailForm();
}

function findNode(id) {
  if (!id || !state.result) return null;
  for (const division of state.result.tree || []) {
    if (division.id === id) return { node: division, type: '分项' };
    for (const lot of division.children || []) {
      if (lot.id === id) return { node: lot, type: '检验批', parent: division };
      for (const item of lot.children || []) {
        if (item.id === id) return { node: item, type: '验收项目', parent: lot, division };
      }
    }
  }
  return null;
}
