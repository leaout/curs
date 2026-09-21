import type { TradingSession } from "../types";

interface SessionSidebarProps {
  sessions: TradingSession[];
  selectedId: string;
  onSelect: (id: string) => void;
  marketConnected: boolean;
}

const statusLabel: Record<TradingSession["status"], string> = {
  running: "运行中",
  paused: "已暂停",
  draft: "草稿",
  attention: "需处理",
};

export function SessionSidebar({ sessions, selectedId, onSelect, marketConnected }: SessionSidebarProps) {
  return (
    <aside className="session-sidebar panel-edge">
      <div className="sidebar-heading">
        <div>
          <p className="eyebrow">TRADING SESSIONS</p>
          <h2>策略会话</h2>
        </div>
        <button className="icon-button" title="搜索策略" aria-label="搜索策略">⌕</button>
      </div>

      <button className="new-session-button"><span>＋</span> 用一句话创建策略</button>

      <div className="session-list">
        {sessions.map((session) => (
          <button
            key={session.id}
            className={`session-card ${session.id === selectedId ? "selected" : ""}`}
            onClick={() => onSelect(session.id)}
          >
            <div className="session-row">
              <span className={`status-dot ${session.status}`} />
              <span className="session-name">{session.name}</span>
              <span className={`pnl ${session.pnlPercent >= 0 ? "positive" : "negative"}`}>
                {session.pnlPercent >= 0 ? "+" : ""}{session.pnlPercent.toFixed(2)}%
              </span>
            </div>
            <div className="session-meta">
              <span>{session.symbol}.{session.venue}</span>
              <span>·</span>
              <span>{session.timeframe}</span>
              <span>·</span>
              <span>{statusLabel[session.status]}</span>
            </div>
            <div className="session-foot">
              <span>{session.lastActivity}</span>
              <span className="version-chip">v{session.promptVersion}</span>
            </div>
          </button>
        ))}
      </div>

      <div className="sidebar-system">
        <div className="system-row"><span><i className={`health-dot ${marketConnected ? "" : "offline"}`} />行情服务</span><strong>{marketConnected ? "cpptdx" : "演示数据"}</strong></div>
        <div className="system-row"><span><i className="health-dot offline" />Broker</span><strong>未接入</strong></div>
        <div className="system-row"><span><i className="health-dot model offline" />决策模型</span><strong>未配置</strong></div>
      </div>
    </aside>
  );
}
