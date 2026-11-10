(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const time = value => value ? new Date(value).toLocaleString('zh-CN', {hour12:false, timeZone:'Asia/Shanghai'}) : '时间未知';
  const reportDay = $('report-day');
  const initialFilters = new URLSearchParams(location.search);
  reportDay.value = initialFilters.get('date') || new Intl.DateTimeFormat('sv-SE', {timeZone:'Asia/Shanghai'}).format(new Date());
  let loadId = 0;
  let board = null;
  let selectedStock = initialFilters.get('stock') || '';
  if (/^\d{6}\.(SH|SZ|BJ)$/.test(selectedStock)) $('bridge-stock').value = selectedStock;
  else selectedStock = '';
  let bridgeStatus = {};
  let connectionCheck = null;
  const markupCache = new Map();

  function setMarkup(id, markup) {
    if (markupCache.get(id) === markup) return;
    $(id).innerHTML = markup;
    markupCache.set(id, markup);
  }

  function renderPool() {
    if (!board) return;
    const stocks = new Map(board.pool.map((stock, index) => [stock.stock_code, {...stock, rank:index + 1}]));
    const reportCodes = new Set();
    for (const report of board.agent_reports) {
      reportCodes.add(report.stock_code);
      if (!stocks.has(report.stock_code)) stocks.set(report.stock_code, report);
    }
    const query = $('pool-search').value.trim().toUpperCase();
    const matches = [...stocks.values()].filter(stock =>
      stock.stock_code.toUpperCase().includes(query) || (stock.stock_name || '').toUpperCase().includes(query));
    setMarkup('pool', matches.map(stock => {
      const hasReport = reportCodes.has(stock.stock_code);
      return `<button class="pool-row" type="button" data-stock="${esc(stock.stock_code)}" aria-pressed="false">
        <span class="stock-rank">${stock.rank ?? '—'}</span>
        <span class="stock-name"><strong>${esc(stock.stock_name || '名称待补')}</strong><code class="stock-code">${esc(stock.stock_code)}</code></span>
        <span class="report-mark${hasReport ? ' available' : ''}" role="img" aria-label="${hasReport ? '当日有报告' : '当日暂无报告'}" title="${hasReport ? '当日有报告' : '当日暂无报告'}"></span>
      </button>`;
    }).join('') || '<p class="empty-state">没有匹配的股票。</p>');
  }

  async function load() {
    const id = ++loadId;
    try {
      const query = new URLSearchParams({date:reportDay.value});
      const response = await fetch('/api/finance-board?' + query, {cache:'no-store'});
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const data = await response.json();
      if (id !== loadId) return;
      $('board-status').textContent = '';
      $('daily-count').textContent = data.daily?.total ? `${data.daily.complete} / ${data.daily.total}` : '—';
      $('daily-coverage').textContent = data.daily?.total ? '已完成 / 批次总数' : '所选日期暂无批次';
      $('pool-count').textContent = data.pool.length;
      $('report-count').textContent = data.agent_reports.length;
      board = data;
      renderPool();
      renderSelection();
      renderConnection();
    } catch (error) { if (id === loadId) $('board-status').textContent = '读取失败：' + error.message; }
  }

  function renderSelection() {
    const chart = $('view-stock-chart');
    if (chart) {
      chart.hidden = !selectedStock;
      if (selectedStock) chart.href = '/signals?' + new URLSearchParams({stock: selectedStock, date: '', chart: '1'});
    }
    document.querySelectorAll('.pool-panel [data-stock]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.stock === selectedStock));
    });
    if (!board) {
      $('view-stock').textContent = selectedStock || '全部股票';
      return;
    }
    const selected = board.pool.find(stock => stock.stock_code === selectedStock)
      || board.agent_reports.find(report => report.stock_code === selectedStock);
    $('view-stock').textContent = selectedStock
      ? [selected?.stock_name, selectedStock].filter(Boolean).join(' · ')
      : '全部股票';
    const reports = selectedStock
      ? board.agent_reports.filter(report => report.stock_code === selectedStock) : board.agent_reports;
    const sourceIds = selectedStock ? new Set(reports.flatMap(report => report.source_ids)) : null;
    const items = sourceIds
      ? board.items.filter(item => item.stock_code === selectedStock && sourceIds.has(item.id))
      : board.items;
    const itemsById = new Map(items.map(item => [item.id, item]));
    if ($('item-count')) $('item-count').textContent = `${items.length} 条`;
    if ($('items')) setMarkup('items', items.map(sourceMarkup).join('') ||
      '<p class="empty-state">当前筛选范围暂无引用来源。</p>');
    setMarkup('reports', reports.map(report => `<article class="intel-report">
      <header><strong>${esc(report.stock_name || '名称待补')} <code>${esc(report.stock_code)}</code></strong><span>${esc(report.agent)} · ${esc(time(report.created_at))}</span></header>
      <p>${esc(report.assessment)}</p>
      <details><summary>证据、反证与来源（${report.source_ids.length}）</summary>
        <p><b>支持证据：</b>${formatEvidence(report.evidence)}</p>
        <p><b>反向证据：</b>${formatEvidence(report.counter_evidence)}</p>
        <p><b>催化：</b>${formatEvidence(report.catalysts)}</p>
        <p><b>失效条件：</b>${formatEvidence(report.invalidation)}</p>
        <div>${report.source_ids.map(id => itemsById.get(id)).filter(Boolean).map(sourceMarkup).join('') ||
          '<p>暂无可显示的引用来源。</p>'}</div>
      </details></article>`).join('') || `<p class="empty-state">${selectedStock
        ? esc(missingReportMessage())
        : '所选日期暂无报告。可以切换日期查看历史记录。'}</p>`);
  }

  function sourceMarkup(item) {
    const title = esc(item.title);
    const heading = /^https:\/\//i.test(item.url)
      ? `<a href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">${title}</a>`
      : `<strong>${title}</strong>`;
    return `<article class="intel-item">${heading}<p>${esc(item.excerpt)}</p>
      <footer>收录于 ${esc(time(item.collected_at))}</footer></article>`;
  }

  function missingReportMessage() {
    if (bridgeStatus.state === 'running' && bridgeStatus.report_day !== reportDay.value) {
      return '该股票在所选日期暂无报告。WorkBuddy 正在执行其他分析，完成后可手动发起。';
    }
    if (bridgeStatus.report_day === reportDay.value) {
      const failure = (bridgeStatus.errors || []).find(message => message.startsWith(selectedStock + '：'));
      if (failure) return '该股票本轮分析未生成报告。' + failure;
      if (bridgeStatus.state === 'running') {
        return '该股票在所选日期暂无报告。定时批次正在运行，新报告保存后会自动显示。';
      }
    }
    return '该股票在所选日期暂无报告。可以切换日期或发起个股分析。';
  }

  function formatEvidence(value) {
    return (Array.isArray(value) ? value.map(esc).join('；') : esc(value)) || '暂无';
  }

  $('pool-search').addEventListener('input', () => {
    renderPool();
    renderSelection();
  });
  document.querySelector('.pool-panel').addEventListener('click', event => {
    const button = event.target.closest('button[data-stock]');
    if (!button) return;
    selectedStock = button.dataset.stock;
    saveSelection();
    if (selectedStock) $('bridge-stock').value = selectedStock;
    if ($('items')) $('items').scrollTop = 0;
    renderSelection();
  });
  function saveSelection() {
    const url = new URL(location.href);
    if (selectedStock) url.searchParams.set('stock', selectedStock);
    else url.searchParams.delete('stock');
    if (reportDay.value) url.searchParams.set('date', reportDay.value);
    else url.searchParams.delete('date');
    history.replaceState(null, '', url);
  }
  const bridge = '/api/finance-board/desktop-bridge';
  const connectionOutput = $('bridge-connection') || document.createElement('p');
  if (!connectionOutput.isConnected) {
    connectionOutput.id = 'bridge-connection';
    connectionOutput.hidden = true;
    connectionOutput.setAttribute('role', 'status');
    $('bridge-form').after(connectionOutput);
  }
  let bridgeTimer;
  let bridgeRequest = 0;

  function renderConnection() {
    if (!connectionCheck) return;
    const verified = bridgeStatus.succeeded > 0 || bridgeStatus.market_saved
      || (board?.daily?.complete > 0 && bridgeStatus.report_day === reportDay.value);
    const message = connectionCheck.connection_available && verified
      ? '本地管道可用，本批次已成功生成报告。'
      : connectionCheck.connection;
    if (connectionOutput.textContent !== message) connectionOutput.textContent = message;
    connectionOutput.hidden = false;
  }

  async function updateBridge(options, check = false) {
    clearTimeout(bridgeTimer);
    const id = ++bridgeRequest;
    try {
      const response = await fetch(bridge + (check ? '?check=1' : ''), {cache:'no-store', ...options});
      const data = await response.json();
      if (id !== bridgeRequest) return;
      if (!response.ok) throw new Error(data.error || 'HTTP ' + response.status);
      bridgeStatus = data;
      if (check) connectionCheck = data;
      renderConnection();
      const progress = [data.report_day && `定时批次 ${data.report_day}`, data.message].filter(Boolean).join(' · ') || '等待分析';
      if ($('bridge-status').textContent !== progress) $('bridge-status').textContent = progress;
      $('bridge-status').dataset.state = data.state;
      $('bridge-submit').disabled = data.state === 'running';
      $('bridge-all').disabled = data.state === 'running';
      $('bridge-check').disabled = false;
      $('bridge-errors').replaceChildren(...(data.errors || []).map(message => {
        const item = document.createElement('li');
        item.textContent = message;
        return item;
      }));
      renderSelection();
      if (data.state === 'running') bridgeTimer = setTimeout(updateBridge, 2500);
      if (data.state === 'complete') load();
    } catch (error) {
      if (id !== bridgeRequest) return;
      $('bridge-submit').disabled = false;
      $('bridge-all').disabled = false;
      $('bridge-check').disabled = false;
      if (check || options) {
        connectionOutput.hidden = false;
        connectionOutput.textContent = error.message;
        bridgeTimer = setTimeout(updateBridge, 2500);
      } else {
        $('bridge-status').textContent = error.message;
        $('bridge-status').dataset.state = 'failed';
      }
    }
  }
  function submitBridge(body) {
    $('bridge-submit').disabled = true;
    $('bridge-all').disabled = true;
    $('bridge-check').disabled = true;
    updateBridge({method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body)});
  }
  $('bridge-form').addEventListener('submit', event => {
    event.preventDefault();
    submitBridge({stock_code:$('bridge-stock').value});
  });
  $('bridge-all').addEventListener('click', () => submitBridge({all_stocks:true}));
  $('bridge-check').addEventListener('click', () => updateBridge(undefined, true));
  reportDay.addEventListener('change', () => {
    saveSelection();
    board = null;
    $('daily-coverage').textContent = '';
    $('daily-count').textContent = '—';
    $('report-count').textContent = '—';
    if ($('item-count')) $('item-count').textContent = '…';
    if ($('items')) setMarkup('items', '<p class="empty-state">正在读取来源…</p>');
    setMarkup('reports', '<p class="empty-state">正在读取报告…</p>');
    load();
  });
  load();
  updateBridge();
  setInterval(load, 30000);
})();
