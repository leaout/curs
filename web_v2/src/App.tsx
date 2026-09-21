import { useEffect, useState } from "react";

import { apiClient } from "./api/client";
import { SessionEventStream } from "./api/sse";
import { CandlestickChart } from "./components/CandlestickChart";
import { ChatPanel } from "./components/ChatPanel";
import { EventTimeline } from "./components/EventTimeline";
import { SessionSidebar } from "./components/SessionSidebar";
import {
  createMockCandles,
  mockEvents,
  mockMessages,
  mockPromptVersions,
  mockSessions,
  mockSignals,
} from "./mockData";
import type { ChatMessage, StrategyPromptVersion, TradingSession } from "./types";

const timeframes = ["1m", "5m", "15m", "30m", "1h", "1D"];

function App() {
  const [sessions, setSessions] = useState<TradingSession[]>(mockSessions);
  const [selectedId, setSelectedId] = useState(mockSessions[0].id);
  const [timeframe, setTimeframe] = useState("5m");
  const [messages, setMessages] = useState<ChatMessage[]>(mockMessages);
  const [versions, setVersions] = useState<StrategyPromptVersion[]>(mockPromptVersions);
  const [sending, setSending] = useState(false);
  const [chartLayer, setChartLayer] = useState<"signals" | "positions">("signals");
  const [candles, setCandles] = useState(createMockCandles);
  const [usingDemoData, setUsingDemoData] = useState(true);
  const selected = sessions.find((session) => session.id === selectedId) ?? sessions[0];
  const lastCandle = candles[candles.length - 1];
  const previous = candles[candles.length - 2];
  const change = ((lastCandle.close - previous.close) / previous.close) * 100;

  useEffect(() => {
    apiClient.getSessions().then((remoteSessions) => {
      if (remoteSessions.length) {
        setSessions(remoteSessions);
        setSelectedId((current) => remoteSessions.some((item) => item.id === current) ? current : remoteSessions[0].id);
      }
    }).catch(() => {
      // The standalone UI intentionally remains usable with demo data before the API is started.
    });
  }, []);

  useEffect(() => {
    const session = sessions.find((item) => item.id === selectedId);
    const venue = session?.venue === "SH" ? "XSHG" : session?.venue === "SZ" ? "XSHE" : undefined;
    if (!session || !venue || !/^\d{6}$/.test(session.symbol)) {
      setCandles(createMockCandles());
      setUsingDemoData(true);
      return;
    }
    let cancelled = false;
    apiClient.getMarketBars(`cn_equity:${venue}:${session.symbol}`, timeframe, 120)
      .then((bars) => {
        if (!cancelled && bars.length >= 2) {
          setCandles(bars);
          setUsingDemoData(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setCandles(createMockCandles());
          setUsingDemoData(true);
        }
      });
    return () => { cancelled = true; };
  }, [selectedId, sessions, timeframe]);

  useEffect(() => {
    if (import.meta.env.VITE_ENABLE_SSE !== "true") return undefined;
    const stream = new SessionEventStream();
    stream.connect(selectedId);
    const unsubscribe = stream.subscribe((event) => {
      if (event.event === "session") {
        apiClient.getSessions().then(setSessions).catch(() => undefined);
      }
    });
    return () => {
      unsubscribe();
      stream.close();
    };
  }, [selectedId]);

  const togglePause = () => {
    const paused = selected.status !== "paused";
    setSessions((items) => items.map((item) => item.id === selected.id
      ? { ...item, status: paused ? "paused" : "running", lastActivity: "刚刚" }
      : item));
    apiClient.setPaused(selected.id, paused).catch(() => undefined);
  };

  const sendMessage = async (content: string) => {
    const now = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
    const nextVersion = (versions.find((version) => version.active)?.version ?? 0) + 1;
    const userMessage: ChatMessage = {
      id: `local-user-${Date.now()}`,
      role: "user",
      content,
      timestamp: now,
      version: nextVersion - 1,
      status: "complete",
    };
    setMessages((items) => [...items, userMessage]);
    setSending(true);

    let response: ChatMessage | undefined;
    try {
      response = await apiClient.sendMessage(selected.id, content);
    } catch {
      await new Promise((resolve) => window.setTimeout(resolve, 850));
      response = {
        id: `local-agent-${Date.now()}`,
        role: "assistant",
        content: `已理解你的调整：“${content}”。我已生成策略 v${nextVersion}，完成约束检查后，将从下一根闭合 K 线开始生效。`,
        timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false }),
        version: nextVersion,
        status: "complete",
      };
    }

    setMessages((items) => [...items, response!]);
    setVersions((items) => [
      { version: nextVersion, summary: content.length > 22 ? `${content.slice(0, 22)}…` : content, createdAt: now, active: true },
      ...items.map((item) => ({ ...item, active: false })),
    ]);
    setSessions((items) => items.map((item) => item.id === selected.id
      ? { ...item, promptVersion: nextVersion, lastActivity: "刚刚" }
      : item));
    setSending(false);
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark"><span /></div>
          <div><strong>VIBE</strong><em>TRADING</em></div>
        </div>
        <div className="session-title">
          <div className="breadcrumb"><span>策略会话</span><i>/</i><span>{selected.name}</span></div>
          <h1>{selected.name}</h1>
          <div className="session-tags">
            <span className="tag mode">{selected.mode === "paper" ? "模拟交易" : "观察模式"}</span>
            <span className={`tag ${selected.status}`}><i />{selected.status === "paused" ? "已暂停" : "运行中"}</span>
          </div>
        </div>
        <div className="top-actions">
          <div className="portfolio-summary">
            <span>今日收益<strong className="positive">+¥ 1,284.60</strong></span>
            <span>可用资金<strong>¥ 86,420</strong></span>
          </div>
          <button className={`pause-button ${selected.status === "paused" ? "resume" : ""}`} onClick={togglePause}>
            {selected.status === "paused" ? "▶ 继续运行" : "Ⅱ 暂停策略"}
          </button>
          <button className="more-button" aria-label="更多操作">•••</button>
        </div>
      </header>

      <main className="workspace">
        <SessionSidebar sessions={sessions} selectedId={selectedId} marketConnected={!usingDemoData} onSelect={(id) => {
          setSelectedId(id);
          const session = sessions.find((item) => item.id === id);
          if (session) setTimeframe(session.timeframe);
        }} />

        <div className="market-workspace">
          <section className="market-panel panel-edge">
            <div className="market-toolbar">
              <div className="instrument">
                <div className="instrument-symbol"><strong>{selected.symbol}</strong><span>{selected.venue}</span></div>
                <div><h2>{selected.name.replace(/放量突破|超跌反弹|趋势跟随/, "") || selected.name}</h2><small>{usingDemoData ? "界面演示 · 行情待接入" : "cpptdx 行情 · 分钟级"}</small></div>
              </div>
              <div className="quote">
                <strong>{lastCandle.close.toFixed(2)}</strong>
                <span className={change >= 0 ? "positive" : "negative"}>{change >= 0 ? "+" : ""}{change.toFixed(2)}%</span>
              </div>
              <div className="ohlc">
                <span>开 <b>{lastCandle.open.toFixed(2)}</b></span>
                <span>高 <b className="positive">{lastCandle.high.toFixed(2)}</b></span>
                <span>低 <b className="negative">{lastCandle.low.toFixed(2)}</b></span>
                <span>量 <b>4.26万</b></span>
              </div>
              <div className="timeframe-switch">
                {timeframes.map((item) => (
                  <button className={timeframe === item ? "active" : ""} key={item} onClick={() => setTimeframe(item)}>{item}</button>
                ))}
              </div>
            </div>

            <div className="chart-legend">
              <span><i className="legend-line ma5" />MA5 1527.34</span>
              <span><i className="legend-line ma20" />MA20 1522.86</span>
              <div className="chart-layer-switch">
                <button className={chartLayer === "signals" ? "active" : ""} onClick={() => setChartLayer("signals")}><i className="signal-dot" />交易信号</button>
                <button className={chartLayer === "positions" ? "active" : ""} onClick={() => setChartLayer("positions")}>持仓成本</button>
              </div>
            </div>
            <div className="chart-stage">
              {usingDemoData && <span className="demo-watermark">DEMO DATA</span>}
              <CandlestickChart candles={candles} signals={chartLayer === "signals" && usingDemoData ? mockSignals : []} />
            </div>

            <div className="chart-stats">
              <span><small>当前仓位</small><strong>100 股 · 7.6%</strong></span>
              <span><small>持仓成本</small><strong>¥1,520.60</strong></span>
              <span><small>浮动盈亏</small><strong className="positive">+¥782.00</strong></span>
              <span><small>策略胜率</small><strong>64.2%</strong></span>
              <span><small>下次评估</small><strong><i className="live-pulse" /> 02:18</strong></span>
            </div>
          </section>

          <EventTimeline events={mockEvents} />
        </div>

        <ChatPanel messages={messages} versions={versions} busy={sending} onSend={sendMessage} />
      </main>
    </div>
  );
}

export default App;
