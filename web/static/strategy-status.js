(() => {
  const select = document.getElementById('strategy-choice');
  const engine = document.getElementById('strategy-engine');
  const status = document.getElementById('strategy-signal-status');
  const table = document.getElementById('strategy-signals');
  const link = document.getElementById('strategy-signals-link');
  let requestId = 0;

  async function loadSignals() {
    const id = ++requestId;
    table.replaceChildren();
    link.hidden = true;
    if (!select.value) return;
    status.textContent = '正在读取最近信号…';
    const query = new URLSearchParams({strategy: select.value, limit: '20'});
    try {
      const response = await fetch('/api/signals?' + query, {cache: 'no-store'});
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const data = await response.json();
      if (id !== requestId) return;
      const directions = {BUY: '买入', SELL: '卖出'};
      for (const signal of data.signals) {
        const row = table.insertRow();
        for (const value of [signal.timestamp, (signal.stock_name || '名称暂缺') + ' ' + signal.stock_code,
          directions[signal.signal_type] || signal.signal_type, signal.price ?? '—']) {
          row.insertCell().textContent = value;
        }
      }
      status.textContent = data.signals.length ? `最近 ${data.signals.length} 条原始触发` : '该策略暂无信号。';
      link.href = '/signals?' + new URLSearchParams({strategy: select.value, date: ''});
      link.hidden = false;
    } catch (error) {
      if (id === requestId) status.textContent = '信号读取失败。' + error.message;
    }
  }

  async function loadStrategies() {
    try {
      const response = await fetch('/api/health', {cache: 'no-store'});
      const data = await response.json();
      if (!response.ok && response.status !== 503) throw new Error('HTTP ' + response.status);
      const strategies = data.strategies || [];
      engine.textContent = `${data.running ? '信号引擎运行中' : '信号引擎未运行'} · 已加载 ${strategies.length} 个策略`;
      const requested = new URLSearchParams(location.search).get('strategy');
      for (const strategy of strategies) select.add(new Option(strategy.id, strategy.id));
      select.disabled = !strategies.length;
      if (strategies.some(strategy => strategy.id === requested)) select.value = requested;
      if (strategies.length) loadSignals();
      else status.textContent = '没有可查看的已加载策略。';
    } catch (error) {
      engine.textContent = '读取引擎状态失败。' + error.message;
    }
  }

  select.addEventListener('change', () => {
    const url = new URL(location.href);
    url.searchParams.set('strategy', select.value);
    history.replaceState(null, '', url);
    loadSignals();
  });
  loadStrategies();
})();
