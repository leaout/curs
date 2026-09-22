import type {
  AgentEvent,
  Candle,
  ChatMessage,
  ChartSignal,
  SessionSnapshot,
  StrategyPromptVersion,
  TradingSession,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v2";

interface ApiBar {
  open_time: string;
  open: string | number;
  high: string | number;
  low: string | number;
  close: string | number;
  volume: string | number;
}

interface ApiSession {
  id: string;
  name: string;
  symbol: string;
  venue: string;
  asset_class: string;
  timeframe: string;
  status: TradingSession["status"];
  mode: TradingSession["mode"];
  pnl_percent: number;
  prompt_version: number;
  created_at: string;
  updated_at: string;
}

interface ApiMessage {
  id: string;
  session_id: string;
  role: ChatMessage["role"];
  content: string;
  created_at: string;
  version?: number;
  status?: "complete" | "failed";
}

interface ApiPromptVersion {
  version: number;
  summary: string;
  strategy?: Record<string, unknown>;
  active: boolean;
  warning?: string;
  created_at: string;
}

interface ApiSessionSnapshot {
  session: ApiSession;
  messages: ApiMessage[];
  prompt_versions: ApiPromptVersion[];
  signals: ApiSignal[];
  events: ApiEvent[];
}

interface ApiSignal {
  id: string;
  timestamp: string;
  price: number;
  side: ChartSignal["side"];
  state: ChartSignal["state"];
  label: string;
  confidence?: number;
}

interface ApiEvent {
  id: string;
  timestamp: string;
  type: AgentEvent["type"];
  title: string;
  detail: string;
  state: AgentEvent["state"];
  duration_ms?: number;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly payload?: unknown,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = await response.text();
    }
    throw new ApiError(`请求失败：${response.status}`, response.status, payload);
  }

  return response.json() as Promise<T>;
}

const formatActivity = (value: string) => new Date(value).toLocaleString("zh-CN", {
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const mapSession = (session: ApiSession): TradingSession => ({
  id: session.id,
  name: session.name,
  symbol: session.symbol,
  venue: session.venue,
  assetClass: session.asset_class,
  timeframe: session.timeframe,
  status: session.status,
  mode: session.mode,
  pnlPercent: session.pnl_percent,
  lastActivity: formatActivity(session.updated_at),
  promptVersion: session.prompt_version,
});

const mapMessage = (message: ApiMessage): ChatMessage => ({
  id: message.id,
  role: message.role,
  content: message.content,
  timestamp: new Date(message.created_at).toLocaleTimeString("zh-CN", {
    hour: "2-digit", minute: "2-digit", hour12: false,
  }),
  version: message.version,
  status: message.status,
});

const mapVersion = (version: ApiPromptVersion): StrategyPromptVersion => ({
  version: version.version,
  summary: version.summary,
  strategy: version.strategy,
  warning: version.warning,
  createdAt: formatActivity(version.created_at),
  active: version.active,
});

const mapSignal = (signal: ApiSignal): ChartSignal => ({
  id: signal.id,
  timestamp: Date.parse(signal.timestamp),
  price: Number(signal.price),
  side: signal.side,
  state: signal.state,
  label: signal.label,
  confidence: signal.confidence,
});

const mapEvent = (event: ApiEvent): AgentEvent => ({
  id: event.id,
  timestamp: new Date(event.timestamp).toLocaleTimeString("zh-CN", {
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  }),
  type: event.type,
  title: event.title,
  detail: event.detail,
  state: event.state,
  durationMs: event.duration_ms,
});

const mapSnapshot = (snapshot: ApiSessionSnapshot): SessionSnapshot => ({
  session: mapSession(snapshot.session),
  messages: snapshot.messages.map(mapMessage),
  promptVersions: snapshot.prompt_versions.map(mapVersion),
  candles: [],
  signals: snapshot.signals.map(mapSignal),
  events: snapshot.events.map(mapEvent),
});

export const apiClient = {
  getSessions: async () => (await request<ApiSession[]>("/sessions")).map(mapSession),
  createSession: async (message: string) =>
    mapSession(await request<ApiSession>("/sessions", {
      method: "POST",
      body: JSON.stringify({ message }),
    })),
  getSession: async (sessionId: string) =>
    mapSnapshot(await request<ApiSessionSnapshot>(`/sessions/${encodeURIComponent(sessionId)}`)),
  getCandles: (sessionId: string, timeframe: string) =>
    request<Candle[]>(
      `/sessions/${encodeURIComponent(sessionId)}/candles?timeframe=${encodeURIComponent(timeframe)}`,
    ),
  getMarketBars: async (instrument: string, timeframe: string, limit = 200) => {
    const query = new URLSearchParams({
      instrument,
      timeframe: timeframe === "1D" ? "1d" : timeframe,
      limit: String(limit),
    });
    const bars = await request<ApiBar[]>(`/market/bars?${query.toString()}`);
    return bars.map((bar) => ({
      timestamp: Date.parse(bar.open_time),
      open: Number(bar.open),
      high: Number(bar.high),
      low: Number(bar.low),
      close: Number(bar.close),
      volume: Number(bar.volume),
    } satisfies Candle));
  },
  sendMessage: async (sessionId: string, content: string) =>
    mapMessage(await request<ApiMessage>(`/sessions/${encodeURIComponent(sessionId)}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    })),
  setPaused: async (sessionId: string, paused: boolean) =>
    mapSession(await request<ApiSession>(`/sessions/${encodeURIComponent(sessionId)}/${paused ? "pause" : "resume"}`, {
      method: "POST",
    })),
};
