import type { UTCTimestamp } from "lightweight-charts";
import type { CandleStyle, ChartConfig, ChartFile, Side } from "../types";
import { quantile } from "./stats";

// Candle and histogram colours follow TradingView's default theme (teal-green up, red down).
export const COLORS = {
  up: "#089981",
  upLight: "rgba(8,153,129,0.4)",
  down: "#F23645",
  downLight: "rgba(242,54,69,0.4)",
  accent: "#A5472A",
  rsi: "#6B4FA3",
  macd: "#2F5D8A",
  signal: "#C98A2B",
  ema50: "#C98A2B",
  ema200: "#2F5D8A",
};

type Point = { time: UTCTimestamp; value: number };

const t = (s: number) => s as UTCTimestamp;

function line(times: number[], values: (number | null)[]): Point[] {
  const out: Point[] = [];
  values.forEach((v, i) => {
    if (v !== null) out.push({ time: t(times[i]), value: v });
  });
  return out;
}

/**
 * Heikin-Ashi candles: close = (O+H+L+C)/4, open = midpoint of the previous HA candle, and
 * high/low span the real extremes plus the HA open/close. Smooths noise so trends read more clearly.
 */
export function toHeikinAshi(bars: ChartFile["bars"]): ChartFile["bars"] {
  const out: ChartFile["bars"] = [];
  let prevOpen = 0;
  let prevClose = 0;
  bars.forEach(([time, o, h, l, c, v], i) => {
    const close = (o + h + l + c) / 4;
    const open = i === 0 ? (o + c) / 2 : (prevOpen + prevClose) / 2;
    out.push([time, open, Math.max(h, open, close), Math.min(l, open, close), close, v]);
    prevOpen = open;
    prevClose = close;
  });
  return out;
}

export interface BuiltChart {
  candles: { time: UTCTimestamp; open: number; high: number; low: number; close: number }[];
  rsi: Point[];
  macd: Point[];
  signal: Point[];
  hist: (Point & { color: string })[];
  ema50: Point[];
  ema200: Point[];
  /** A BUY/SELL label box anchored under the candle's low (BUY) or over its high (SELL). */
  markers: { time: UTCTimestamp; price: number; side: Side; color: string }[];
  deepLow: number | null;
  deepHigh: number | null;
  rsiLevels: [number, number];
  showEmas: boolean;
}

/** Turn the scanner's chart JSON into ready-to-draw series. Pure, so it is unit-tested. */
export function buildChartData(chart: ChartFile, config: ChartConfig, strategyId: string, style: CandleStyle = "ha"): BuiltChart {
  // Only the drawn candles change with the style. RSI, MACD and EMAs always come from real closes,
  // because those are what the scanner evaluates its signals on.
  const shown = style === "ha" ? toHeikinAshi(chart.bars) : chart.bars;
  const times = chart.bars.map((b) => b[0]);
  const histValues = chart.macd.hist;
  const hist = histValues.flatMap((v, i) => {
    if (v === null) return [];
    const prev = i > 0 ? histValues[i - 1] : null;
    const rising = prev === null || v > prev;
    // Four shades: strong when the bar is growing away from zero, light when it is shrinking.
    const color = v >= 0 ? (rising ? COLORS.up : COLORS.upLight) : rising ? COLORS.downLight : COLORS.down;
    return [{ time: t(times[i]), value: v, color }];
  });
  const recent = histValues.slice(-100).filter((v): v is number => v !== null);
  const deep = config.macd_deep && recent.length >= 20;

  return {
    candles: shown.map(([time, open, high, low, close]) => ({ time: t(time), open, high, low, close })),
    rsi: line(times, chart.rsi),
    macd: line(times, chart.macd.macd),
    signal: line(times, chart.macd.signal),
    hist,
    ema50: config.emas ? line(times, chart.ema50) : [],
    ema200: config.emas ? line(times, chart.ema200) : [],
    markers: chart.signals.flatMap((sig) => {
      if (sig.strategy_id !== strategyId) return [];
      const bar = shown.find((x) => x[0] === sig.bar_time);
      if (!bar) return [];
      const buy = sig.side === "BUY";
      return [{ time: t(sig.bar_time), price: buy ? bar[3] : bar[2], side: sig.side, color: buy ? COLORS.up : COLORS.down }];
    }),
    deepLow: deep ? quantile(recent, 0.1) : null,
    deepHigh: deep ? quantile(recent, 0.9) : null,
    rsiLevels: config.rsi_levels,
    showEmas: config.emas,
  };
}
