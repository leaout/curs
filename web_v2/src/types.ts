export type AgentMode = "observe" | "paper" | "approval" | "live";
export type SessionStatus = "running" | "paused" | "draft" | "attention";
export type SignalSide = "BUY" | "SELL" | "HOLD";

export interface TradingSession {
  id: string;
  name: string;
  symbol: string;
  venue: string;
  assetClass: string;
  timeframe: string;
  status: SessionStatus;
  mode: AgentMode;
  pnlPercent: number;
  lastActivity: string;
  promptVersion: number;
}

export interface Candle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ChartSignal {
  id: string;
  timestamp: number;
  price: number;
  side: SignalSide;
  state: "candidate" | "approved" | "rejected" | "filled";
  label: string;
  confidence?: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  version?: number;
  status?: "streaming" | "complete" | "failed";
}

export interface StrategyPromptVersion {
  version: number;
  summary: string;
  createdAt: string;
  active: boolean;
  strategy?: Record<string, unknown>;
  warning?: string;
}

export interface AgentEvent {
  id: string;
  timestamp: string;
  type: "signal" | "context" | "model" | "risk" | "order" | "system";
  title: string;
  detail: string;
  state: "success" | "warning" | "neutral" | "error";
  durationMs?: number;
}

export interface SessionSnapshot {
  session: TradingSession;
  candles: Candle[];
  signals: ChartSignal[];
  messages: ChatMessage[];
  promptVersions: StrategyPromptVersion[];
  events: AgentEvent[];
}
