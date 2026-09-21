import type { Candle, ChatMessage, SessionSnapshot, TradingSession } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v2";

interface ApiBar {
  open_time: string;
  open: string | number;
  high: string | number;
  low: string | number;
  close: string | number;
  volume: string | number;
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

export const apiClient = {
  getSessions: () => request<TradingSession[]>("/sessions"),
  createSession: (message: string) =>
    request<TradingSession>("/sessions", {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  getSession: (sessionId: string) =>
    request<SessionSnapshot>(`/sessions/${encodeURIComponent(sessionId)}`),
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
  sendMessage: (sessionId: string, content: string) =>
    request<ChatMessage>(`/sessions/${encodeURIComponent(sessionId)}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
  setPaused: (sessionId: string, paused: boolean) =>
    request<TradingSession>(`/sessions/${encodeURIComponent(sessionId)}/${paused ? "pause" : "resume"}`, {
      method: "POST",
    }),
};
