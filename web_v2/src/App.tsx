import { useEffect, useState } from "react";

import { apiClient } from "./api/client";
import { SessionEventStream } from "./api/sse";
import { CandlestickChart } from "./components/CandlestickChart";
import { ChatPanel } from "./components/ChatPanel";
import { EventTimeline } from "./components/EventTimeline";
import { SessionSidebar } from "./components/SessionSidebar";
import { createMockCandles } from "./mockData";
import type { AgentEvent, ChartSignal, ChatMessage, StrategyPromptVersion, TradingSession } from "./types";

const timeframes = ["1m", "5m", "15m", "30m", "1h", "1D"];

function App() {
  const [sessions, setSessions] = useState<TradingSession[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [timeframe, setTimeframe] = useState("5m");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [versions, setVersions] = useState<StrategyPromptVersion[]>([]);
  const [signals, setSignals] = useState<ChartSignal[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [createPrompt, setCreatePrompt] = useState("");
  const [creating, setCreating] = useState(false);
  const [chartLayer, setChartLayer] = useState<"signals" | "positions">("signals");
  const [candles, setCandles] = useState(createMockCandles);
  const [usingDemoData, setUsingDemoData] = useState(true);
  const selected = sessions.find((session) => session.id === selectedId);
  const lastCandle = candles[candles.length - 1];
  const previous = candles[candles.length - 2];
  const change = previous ? ((lastCandle.close - previous.close) / previous.close) * 100 : 0;

  const loadSessions = async () => {
    const remoteSessions = await apiClient.getSessions();
    setSessions(remoteSessions);
    setSelectedId((current) => remoteSessions.some((item) => item.id === current)
      ? current
      : (remoteSessions[0]?.id ?? ""));
  };

  useEffect(() => {
    loadSessions()
      .catch(() => setError("无法连接 V2 API，请确认后端已启动。"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setMessages([]);
      setVersions([]);
      setSignals([]);
      setEvents([]);
      return;
    }
    let cancelled = false;
    apiClient.getSession(selectedId).then((snapshot) => {
      if (cancelled) return;
      setMessages(snapshot.messages);
      setVersions(snapshot.promptVersions);
      setSignals(snapshot.signals);
      setEvents(snapshot.events);
      setTimeframe(snapshot.session.timeframe);
    }).catch(() => {
      if (!cancelled) setError("会话详情加载失败，请刷新后重试。");
    });
    return () => { cancelled = true; };
  }, [selectedId]);

  useEffect(() => {
    if (!selected || !selected.venue || !selected.symbol) {
      setCandles(createMockCandles());
      setUsingDemoData(true);
      return;
    }
    let cancelled = false;
    const refreshBars = () => apiClient.getMarketBars(
        `${selected.assetClass}:${selected.venue}:${selected.symbol}`,
        timeframe,
        120,
      ).then((bars) => {
        if (!cancelled && bars.length >= 2) {
          setCandles(bars);
          setUsingDemoData(false);
        }
      }).catch(() => {
        if (!cancelled) {
          setCandles(createMockCandles());
          setUsingDemoData(true);
        }
      });
    refreshBars();
    const refreshTimer = window.setInterval(refreshBars, 15_000);
    return () => {
      cancelled = true;
      window.clearInterval(refreshTimer);
    };
  }, [selected, timeframe]);

  useEffect(() => {
    if (!selectedId || import.meta.env.VITE_ENABLE_SSE === "false") return undefined;
    const stream = new SessionEventStream();
    stream.connect(selectedId);
    const unsubscribe = stream.subscribe(() => {
      loadSessions().catch(() => undefined);
      apiClient.getSession(selectedId).then((snapshot) => {
        setMessages(snapshot.messages);
        setVersions(snapshot.promptVersions);
        setSignals(snapshot.signals);
        setEvents(snapshot.events);
      }).catch(() => undefined);
    });
    return () => {
      unsubscribe();
      stream.close();
    };
  }, [selectedId]);

  const createSession = async () => {
    const prompt = createPrompt.trim();
    if (!prompt || creating) return;
    setCreating(true);
    setError("");
    try {
      const session = await apiClient.createSession(prompt);
      setSessions((items) => [session, ...items]);
      setSelectedId(session.id);
      setCreatePrompt("");
      setShowCreate(false);
    } catch {
      setError("创建策略失败，请检查 API 与模型配置。");
    } finally {
      setCreating(false);
    }
  };

  const togglePause = async () => {
    if (!selected) return;
    try {
      const updated = await apiClient.setPaused(selected.id, selected.status === "running");
      setSessions((items) => items.map((item) => item.id === updated.id ? updated : item));
    } catch {
      setError("策略状态更新失败。");
    }
  };

  const sendMessage = async (content: string) => {
    if (!selected) return;
    const optimistic: ChatMessage = {
      id: `local-user-${Date.now()}`,
      role: "user",
      content,
      timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false }),
      status: "complete",
    };
    setMessages((items) => [...items, optimistic]);
    setSending(true);
    setError("");
    try {
      await apiClient.sendMessage(selected.id, content);
      const snapshot = await apiClient.getSession(selected.id);
      setMessages(snapshot.messages);
      setVersions(snapshot.promptVersions);
      setSignals(snapshot.signals);
      setEvents(snapshot.events);
      setSessions((items) => items.map((item) => item.id === selected.id ? snapshot.session : item));
    } catch {
      setMessages((items) => [...items, {
        id: `local-error-${Date.now()}`,
        role: "system",
        content: "消息保存失败，请检查后端服务后重试。",
        timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false }),
        status: "failed",
      }]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark"><span /></div>
          <div><strong>VIBE</strong><em>TRADING</em></div>
        </div>
        <div className="session-title">
          <div className="breadcrumb"><span>策略会话</span>{selected && <><i>/</i><span>{selected.name}</span></>}</div>
          <h1>{selected?.name ?? "创建你的第一个交易策略"}</h1>
          {selected && <div className="session-tags">
            <span className="tag mode">{selected.mode === "paper" ? "模拟交易" : "观察模式"}</span>
            <span className={`tag ${selected.status}`}><i />{selected.status === "paused" ? "已暂停" : selected.status === "draft" ? "草稿" : "运行中"}</span>
          </div>}
        </div>
        <div className="top-actions">
          <div className="portfolio-summary">
            <span>交易权限<strong>仅观察</strong></span>
            <span>Broker<strong>未接入</strong></span>
          </div>
          {selected && <button className={`pause-button ${selected.status !== "running" ? "resume" : ""}`} onClick={togglePause}>
            {selected.status === "draft" ? "▶ 启动策略" : selected.status === "paused" ? "▶ 继续运行" : "Ⅱ 暂停策略"}
          </button>}
        </div>
      </header>

      <main className="workspace">
        <SessionSidebar
          sessions={sessions}
          selectedId={selectedId}
          marketConnected={!usingDemoData}
          onCreate={() => setShowCreate(true)}
          onSelect={setSelectedId}
        />

        {!selected ? (
          <section className="empty-workspace">
            <div className="empty-orbit"><span>V</span></div>
            <p className="eyebrow">CONVERSATION-FIRST TRADING</p>
            <h2>{loading ? "正在加载策略会话…" : "用一句话描述你的交易想法"}</h2>
            <p>Agent 会把自然语言编译成受约束的策略结构，并保存每次修改的完整版本。</p>
            <button onClick={() => setShowCreate(true)}>＋ 创建策略会话</button>
            {error && <small>{error}</small>}
          </section>
        ) : <>
          <div className="market-workspace">
            <section className="market-panel panel-edge">
              <div className="market-toolbar">
                <div className="instrument">
                  <div className="instrument-symbol"><strong>{selected.symbol}</strong><span>{selected.venue}</span></div>
                  <div><h2>{selected.name}</h2><small>{usingDemoData ? "演示行情 · cpptdx 未连接" : "cpptdx 行情 · 分钟级"}</small></div>
                </div>
                <div className="quote">
                  <strong>{lastCandle.close.toFixed(2)}</strong>
                  <span className={change >= 0 ? "positive" : "negative"}>{change >= 0 ? "+" : ""}{change.toFixed(2)}%</span>
                </div>
                <div className="ohlc">
                  <span>开 <b>{lastCandle.open.toFixed(2)}</b></span>
                  <span>高 <b className="positive">{lastCandle.high.toFixed(2)}</b></span>
                  <span>低 <b className="negative">{lastCandle.low.toFixed(2)}</b></span>
                  <span>量 <b>{lastCandle.volume.toFixed(0)}</b></span>
                </div>
                <div className="timeframe-switch">
                  {timeframes.map((item) => (
                    <button className={timeframe === item ? "active" : ""} key={item} onClick={() => setTimeframe(item)}>{item}</button>
                  ))}
                </div>
              </div>

              <div className="chart-legend">
                <span><i className="legend-line ma5" />MA5</span>
                <span><i className="legend-line ma20" />MA20</span>
                <div className="chart-layer-switch">
                  <button className={chartLayer === "signals" ? "active" : ""} onClick={() => setChartLayer("signals")}><i className="signal-dot" />交易信号</button>
                  <button className={chartLayer === "positions" ? "active" : ""} onClick={() => setChartLayer("positions")}>持仓成本</button>
                </div>
              </div>
              <div className="chart-stage">
                {usingDemoData && <span className="demo-watermark">DEMO DATA</span>}
                <CandlestickChart candles={candles} signals={chartLayer === "signals" ? signals : []} />
              </div>

              <div className="chart-stats">
                <span><small>当前仓位</small><strong>未接入</strong></span>
                <span><small>持仓成本</small><strong>—</strong></span>
                <span><small>浮动盈亏</small><strong>—</strong></span>
                <span><small>策略版本</small><strong>v{selected.promptVersion}</strong></span>
                <span><small>执行权限</small><strong>仅观察</strong></span>
              </div>
            </section>
            <EventTimeline events={events} />
          </div>

          <ChatPanel messages={messages} versions={versions} busy={sending} onSend={sendMessage} />
        </>}
      </main>

      {showCreate && <div className="create-backdrop" onMouseDown={() => !creating && setShowCreate(false)}>
        <section className="create-dialog" onMouseDown={(event) => event.stopPropagation()}>
          <p className="eyebrow">NEW TRADING SESSION</p>
          <h2>一句话创建策略</h2>
          <p>包含交易品种、周期、触发条件和风险约束会得到更准确的结果。</p>
          <textarea
            autoFocus
            value={createPrompt}
            onChange={(event) => setCreatePrompt(event.target.value)}
            placeholder="例如：为 600519 创建 5 分钟放量突破策略，单次最大仓位 5%，止损 3%"
            rows={5}
          />
          <div className="create-actions">
            <button className="cancel" onClick={() => setShowCreate(false)} disabled={creating}>取消</button>
            <button onClick={createSession} disabled={!createPrompt.trim() || creating}>{creating ? "正在编译…" : "创建草稿"}</button>
          </div>
        </section>
      </div>}
    </div>
  );
}

export default App;
