import type {
  AgentEvent,
  Candle,
  ChartSignal,
  ChatMessage,
  StrategyPromptVersion,
  TradingSession,
} from "./types";

export const mockSessions: TradingSession[] = [
  {
    id: "session-breakout-600519",
    name: "茅台放量突破",
    symbol: "600519",
    venue: "SH",
    timeframe: "5m",
    status: "running",
    mode: "paper",
    pnlPercent: 2.84,
    lastActivity: "刚刚",
    promptVersion: 7,
  },
  {
    id: "session-rebound-300750",
    name: "宁德时代超跌反弹",
    symbol: "300750",
    venue: "SZ",
    timeframe: "15m",
    status: "running",
    mode: "observe",
    pnlPercent: 0.62,
    lastActivity: "2 分钟前",
    promptVersion: 4,
  },
  {
    id: "session-grid-002594",
    name: "比亚迪趋势跟随",
    symbol: "002594",
    venue: "SZ",
    timeframe: "5m",
    status: "paused",
    mode: "paper",
    pnlPercent: -0.38,
    lastActivity: "38 分钟前",
    promptVersion: 12,
  },
  {
    id: "session-draft",
    name: "银行板块轮动",
    symbol: "自选池",
    venue: "CN",
    timeframe: "30m",
    status: "draft",
    mode: "observe",
    pnlPercent: 0,
    lastActivity: "昨天",
    promptVersion: 1,
  },
];

export function createMockCandles(count = 82): Candle[] {
  const output: Candle[] = [];
  const start = Date.UTC(2026, 8, 21, 1, 30);
  let close = 1522.8;

  for (let index = 0; index < count; index += 1) {
    const wave = Math.sin(index / 4.7) * 2.4 + Math.sin(index / 11) * 3.2;
    const trend = index > 46 ? (index - 46) * 0.34 : index * 0.04;
    const jitter = Math.sin(index * 2.13) * 1.4;
    const open = close + Math.sin(index * 1.61) * 1.05;
    close = 1519 + wave + trend + jitter;
    const high = Math.max(open, close) + 0.9 + (index % 5) * 0.24;
    const low = Math.min(open, close) - 0.8 - (index % 4) * 0.28;
    output.push({
      timestamp: start + index * 5 * 60 * 1000,
      open,
      high,
      low,
      close,
      volume: 1300 + Math.abs(Math.sin(index / 3.1)) * 2600 + (index > 54 ? 1200 : 0),
    });
  }

  return output;
}

export const mockSignals: ChartSignal[] = [
  {
    id: "signal-1",
    timestamp: Date.UTC(2026, 8, 21, 4, 45),
    price: 1516.9,
    side: "BUY",
    state: "rejected",
    label: "风控拒绝",
    confidence: 0.68,
  },
  {
    id: "signal-2",
    timestamp: Date.UTC(2026, 8, 21, 6, 15),
    price: 1520.6,
    side: "BUY",
    state: "filled",
    label: "买入成交",
    confidence: 0.87,
  },
  {
    id: "signal-3",
    timestamp: Date.UTC(2026, 8, 21, 7, 20),
    price: 1528.4,
    side: "SELL",
    state: "candidate",
    label: "候选信号",
    confidence: 0.76,
  },
];

export const mockMessages: ChatMessage[] = [
  {
    id: "msg-1",
    role: "user",
    content: "盯住贵州茅台的 5 分钟放量突破，趋势确认后买入，但不要追高。",
    timestamp: "09:25",
    version: 5,
    status: "complete",
  },
  {
    id: "msg-2",
    role: "assistant",
    content:
      "策略已运行。我会在收盘价突破近 20 根 K 线高点、成交量达到均量 1.8 倍时生成候选信号；若价格偏离 VWAP 超过 2.5%，将放弃追单。",
    timestamp: "09:25",
    version: 5,
    status: "complete",
  },
  {
    id: "msg-3",
    role: "user",
    content: "把成交量条件改成 2 倍，单次仓位最多 8%，止损收紧到 2%。",
    timestamp: "13:04",
    version: 6,
    status: "complete",
  },
  {
    id: "msg-4",
    role: "assistant",
    content:
      "已生成 v7：量比阈值调整为 2.0，单次最大仓位 8%，硬止损 2%。新版本从下一根闭合 K 线开始生效，已有订单不受影响。",
    timestamp: "13:04",
    version: 7,
    status: "complete",
  },
];

export const mockPromptVersions: StrategyPromptVersion[] = [
  { version: 7, summary: "量比 2.0 · 仓位 8% · 止损 2%", createdAt: "13:04", active: true },
  { version: 6, summary: "增加 VWAP 追高过滤", createdAt: "11:28", active: false },
  { version: 5, summary: "5 分钟放量突破初版", createdAt: "09:25", active: false },
];

export const mockEvents: AgentEvent[] = [
  {
    id: "event-1",
    timestamp: "14:37:00",
    type: "signal",
    title: "候选信号",
    detail: "价格突破 20 周期高点，量比 2.18",
    state: "success",
    durationMs: 8,
  },
  {
    id: "event-2",
    timestamp: "14:37:01",
    type: "context",
    title: "上下文就绪",
    detail: "行情、账户与近 3 次决策已装载",
    state: "success",
    durationMs: 31,
  },
  {
    id: "event-3",
    timestamp: "14:37:03",
    type: "model",
    title: "AI 决策 · BUY",
    detail: "置信度 0.87，建议限价买入 100 股",
    state: "success",
    durationMs: 1842,
  },
  {
    id: "event-4",
    timestamp: "14:37:03",
    type: "risk",
    title: "风控通过",
    detail: "预计仓位 7.6%，价格与资金检查通过",
    state: "success",
    durationMs: 5,
  },
  {
    id: "event-5",
    timestamp: "14:37:04",
    type: "order",
    title: "模拟成交",
    detail: "BUY 100 @ ¥1,520.60",
    state: "success",
    durationMs: 246,
  },
];
