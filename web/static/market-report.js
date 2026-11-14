(() => {
  const day = document.getElementById('market-report-day');
  const status = document.getElementById('market-report-status');
  const content = document.getElementById('market-report-content');
  const text = document.getElementById('market-report-text');
  const sources = document.getElementById('market-report-sources');
  const params = new URLSearchParams(location.search);
  day.value = params.get('date') || new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Shanghai'
  }).format(new Date());
  let requestId = 0;

  async function load(showLoading = false) {
    const id = ++requestId;
    if (showLoading) {
      content.hidden = true;
      status.textContent = '正在读取市场报告…';
    }
    if (!day.value) {
      status.textContent = '请选择报告日期。';
      return;
    }
    try {
      const query = new URLSearchParams({date: day.value});
      const response = await fetch('/api/market-report?' + query, {cache: 'no-store'});
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const {report} = await response.json();
      if (id !== requestId) return;
      status.textContent = report ? '' : '所选日期暂无市场报告。定时分析每日北京时间 21:30 开始。';
      content.hidden = !report;
      if (!report) return;
      text.textContent = report.assessment;
      sources.replaceChildren(...report.sources.map(source => {
        const item = document.createElement('li');
        item.textContent = source.title;
        if (source.url.startsWith('https://')) {
          const link = document.createElement('a');
          link.href = source.url;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          link.textContent = source.title;
          item.replaceChildren(link);
        }
        return item;
      }));
    } catch (error) {
      if (id !== requestId) return;
      status.textContent = '市场报告读取失败。' + error.message;
    }
  }

  day.addEventListener('change', () => {
    const url = new URL(location.href);
    url.searchParams.set('date', day.value);
    history.replaceState(null, '', url);
    load(true);
  });
  load();
  setInterval(load, 30000);
})();
