/* Display-only formatting: preserve numeric values and avoid HTML interpolation. */
(() => {
  const statuses = {candidate:'候选观察',confirming:'持续确认',confirmed:'已记录信号',abandoned:'已放弃',paused:'暂停确认',excluded:'已排除',observe_only:'仅观察',data_unavailable:'行情不足',unknown:'未记录',BUY:'买入',SELL:'卖出'};
  const dates = value => String(value).replace(/(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}(?::\d{2})?)(?:\.\d+)?(?:\+08:00)?/g,'$1 $2');
  window.observationText = value => dates(statuses[value] || value);
  window.observationInfo = (id,value) => {
    const node = document.getElementById(id);
    node.className = 'info-grid';
    node.replaceChildren(...String(value).split(' | ').map(part => {
      const span = document.createElement('span');span.className='info-item';span.textContent=dates(part);return span;
    }));
  };
  window.observationEvidence = raw => {
    try {
      const e = typeof raw === 'string' ? JSON.parse(raw) : raw;
      return [e.scope, e.strong_peers == null ? null : `同步走强 ${e.strong_peers} 只`,
        e.elapsed_seconds == null ? null : `已确认 ${Math.round(e.elapsed_seconds)} 秒`,
        e.confirm_seconds == null ? null : `目标 ${e.confirm_seconds} 秒`,
        e.samples == null ? null : `${e.samples} 个样本`,
        e.amount_increase == null ? null : `成交额增加 ${(e.amount_increase/10000).toFixed(1)} 万元`].filter(v=>v!=null).join(' · ') || '暂无确认依据';
    } catch {return '暂无可读依据';}
  };
})();
