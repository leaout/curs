import type { Candle, ChartSignal } from "./types";

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
