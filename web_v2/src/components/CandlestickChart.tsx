import { useMemo } from "react";

import type { Candle, ChartSignal } from "../types";

interface CandlestickChartProps {
  candles: Candle[];
  signals: ChartSignal[];
}

const width = 1040;
const height = 520;
const plotLeft = 18;
const plotRight = 82;
const plotTop = 26;
const volumeHeight = 82;
const plotBottom = 42 + volumeHeight;

function movingAverage(candles: Candle[], period: number): Array<number | null> {
  return candles.map((_, index) => {
    if (index < period - 1) return null;
    const values = candles.slice(index - period + 1, index + 1);
    return values.reduce((total, candle) => total + candle.close, 0) / period;
  });
}

function money(value: number): string {
  return value.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function CandlestickChart({ candles, signals }: CandlestickChartProps) {
  const geometry = useMemo(() => {
    if (!candles.length) return null;
    const chartBottom = height - plotBottom;
    const innerWidth = width - plotLeft - plotRight;
    const values = candles.flatMap((candle) => [candle.high, candle.low]);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = Math.max((max - min) * 0.1, 1);
    const priceMin = min - padding;
    const priceMax = max + padding;
    const priceToY = (price: number) =>
      plotTop + ((priceMax - price) / (priceMax - priceMin)) * (chartBottom - plotTop);
    const step = innerWidth / candles.length;
    const xAt = (index: number) => plotLeft + step * index + step / 2;
    const maxVolume = Math.max(...candles.map((candle) => candle.volume));
    const ma5 = movingAverage(candles, 5);
    const ma20 = movingAverage(candles, 20);
    const maPath = (valuesToPlot: Array<number | null>) =>
      valuesToPlot
        .map((value, index) => (value === null ? "" : `${index === 0 || valuesToPlot[index - 1] === null ? "M" : "L"}${xAt(index)},${priceToY(value)}`))
        .filter(Boolean)
        .join(" ");

    return {
      chartBottom,
      priceMin,
      priceMax,
      priceToY,
      xAt,
      step,
      maxVolume,
      ma5Path: maPath(ma5),
      ma20Path: maPath(ma20),
    };
  }, [candles]);

  if (!geometry) {
    return <div className="chart-empty">暂无行情数据</div>;
  }

  const last = candles[candles.length - 1];
  const latestY = geometry.priceToY(last.close);
  const timeAt = (ratio: number) => candles[Math.min(candles.length - 1, Math.floor(candles.length * ratio))];
  const horizontalGrid = Array.from({ length: 6 }, (_, index) => {
    const ratio = index / 5;
    return {
      y: plotTop + (geometry.chartBottom - plotTop) * ratio,
      price: geometry.priceMax - (geometry.priceMax - geometry.priceMin) * ratio,
    };
  });
  const barDuration = candles.length > 1
    ? Math.max(1, candles[1].timestamp - candles[0].timestamp)
    : 60_000;
  const signalPositions = signals
    .map((signal) => {
      let index = candles.findIndex((candle) =>
        candle.timestamp < signal.timestamp && candle.timestamp + barDuration >= signal.timestamp,
      );
      if (index < 0) {
        const distances = candles.map((candle) => Math.abs(candle.timestamp - signal.timestamp));
        const nearest = Math.min(...distances);
        index = nearest <= barDuration ? distances.indexOf(nearest) : -1;
      }
      return index < 0 ? null : { signal, index };
    })
    .filter((entry): entry is NonNullable<typeof entry> => entry !== null);

  return (
    <div className="chart-wrap">
      <svg className="candlestick-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="K 线图与交易信号">
        <defs>
          <linearGradient id="volumeFade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#32d69b" stopOpacity="0.35" />
            <stop offset="1" stopColor="#32d69b" stopOpacity="0.04" />
          </linearGradient>
          <filter id="signalGlow" x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {horizontalGrid.map(({ y, price }) => (
          <g key={y}>
            <line className="chart-grid" x1={plotLeft} x2={width - plotRight} y1={y} y2={y} />
            <text className="chart-axis-label" x={width - plotRight + 12} y={y + 4}>{money(price)}</text>
          </g>
        ))}
        {[0.2, 0.4, 0.6, 0.8].map((ratio) => (
          <line
            key={ratio}
            className="chart-grid vertical"
            x1={plotLeft + (width - plotLeft - plotRight) * ratio}
            x2={plotLeft + (width - plotLeft - plotRight) * ratio}
            y1={plotTop}
            y2={height - 20}
          />
        ))}

        <path className="ma-line ma-five" d={geometry.ma5Path} />
        <path className="ma-line ma-twenty" d={geometry.ma20Path} />

        {candles.map((candle, index) => {
          const x = geometry.xAt(index);
          const rising = candle.close >= candle.open;
          const bodyTop = geometry.priceToY(Math.max(candle.open, candle.close));
          const bodyBottom = geometry.priceToY(Math.min(candle.open, candle.close));
          const candleWidth = Math.max(2.6, geometry.step * 0.62);
          const volumeY = height - 24 - (candle.volume / geometry.maxVolume) * volumeHeight;
          return (
            <g key={candle.timestamp} className={rising ? "candle rising" : "candle falling"}>
              <line x1={x} x2={x} y1={geometry.priceToY(candle.high)} y2={geometry.priceToY(candle.low)} />
              <rect
                x={x - candleWidth / 2}
                y={bodyTop}
                width={candleWidth}
                height={Math.max(1.6, bodyBottom - bodyTop)}
                rx="0.7"
              />
              <rect className="volume-bar" x={x - candleWidth / 2} y={volumeY} width={candleWidth} height={height - 24 - volumeY} />
            </g>
          );
        })}

        {signalPositions.map(({ signal, index }) => {
          const x = geometry.xAt(index);
          const candle = candles[index];
          const isBuy = signal.side === "BUY";
          const markerY = geometry.priceToY(isBuy ? candle.low : candle.high) + (isBuy ? 22 : -22);
          const color = signal.state === "rejected" ? "#f4a261" : isBuy ? "#38dda5" : "#ff6b80";
          return (
            <g key={signal.id} className="signal-marker" transform={`translate(${x}, ${markerY})`}>
              <circle r="12" fill={color} fillOpacity="0.15" filter="url(#signalGlow)" />
              <path d={isBuy ? "M0,-8 L7,4 L2,4 L2,9 L-2,9 L-2,4 L-7,4 Z" : "M0,8 L7,-4 L2,-4 L2,-9 L-2,-9 L-2,-4 L-7,-4 Z"} fill={color} />
              <g transform={`translate(${isBuy ? 14 : -88}, -12)`}>
                <rect width="74" height="24" rx="7" fill="#0c1816" stroke={color} strokeOpacity="0.55" />
                <text x="37" y="16" textAnchor="middle" fill={color} fontSize="10" fontWeight="600">{signal.label}</text>
              </g>
            </g>
          );
        })}

        <line className="latest-price-line" x1={plotLeft} x2={width - plotRight} y1={latestY} y2={latestY} />
        <g transform={`translate(${width - plotRight + 4}, ${latestY - 11})`}>
          <rect className="latest-price-tag" width="72" height="22" rx="5" />
          <text className="latest-price-text" x="36" y="15" textAnchor="middle">{money(last.close)}</text>
        </g>

        {[0, 0.25, 0.5, 0.75, 0.99].map((ratio) => {
          const candle = timeAt(ratio);
          const x = plotLeft + (width - plotLeft - plotRight) * ratio;
          return <text key={ratio} className="chart-time-label" x={x} y={height - 5}>{new Date(candle.timestamp).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false })}</text>;
        })}
      </svg>
    </div>
  );
}
