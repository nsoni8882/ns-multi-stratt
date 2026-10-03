import { chart } from "../test-fixtures";
import type { ChartFile } from "../types";
import { COLORS, buildChartData } from "./chartData";

const macdCfg = { rsi_levels: [20, 80] as [number, number], macd_deep: true, emas: false };
const trendCfg = { rsi_levels: [40, 60] as [number, number], macd_deep: false, emas: true };

it("drops null points and keeps candle times", () => {
  const b = buildChartData(chart, macdCfg, "macd-rsi-reversal");
  expect(b.candles.map((c) => c.time)).toEqual([1, 2, 3]);
  expect(b.rsi).toEqual([{ time: 2, value: 40 }, { time: 3, value: 45 }]);
  expect(b.macd).toHaveLength(2);
});

it("places a BUY label under the signal candle's low and a SELL label over its high, only for this strategy", () => {
  const two: ChartFile = {
    ...chart,
    signals: [
      { strategy_id: "macd-rsi-reversal", side: "BUY", bar_time: 3 },
      { strategy_id: "trend-pullback", side: "SELL", bar_time: 2 },
    ],
  };
  // bars: time 3 = [open 12, high 14, low 11, close 13]; time 2 = [11, 13, 10, 12]
  expect(buildChartData(two, macdCfg, "macd-rsi-reversal").markers).toEqual([{ time: 3, price: 11, side: "BUY", color: COLORS.up }]);
  expect(buildChartData(two, trendCfg, "trend-pullback").markers).toEqual([{ time: 2, price: 13, side: "SELL", color: COLORS.down }]);
});

it("skips a signal whose candle is not in the chart window", () => {
  const gone: ChartFile = { ...chart, signals: [{ strategy_id: "macd-rsi-reversal", side: "BUY", bar_time: 999 }] };
  expect(buildChartData(gone, macdCfg, "macd-rsi-reversal").markers).toEqual([]);
});

it("colours the histogram in four shades", () => {
  const c: ChartFile = { ...chart, macd: { ...chart.macd, hist: [1, 2, 1, -1, -2, -1] }, bars: Array.from({ length: 6 }, (_, i) => [i + 1, 1, 1, 1, 1, 1]) };
  const colors = buildChartData(c, macdCfg, "x").hist.map((h) => h.color);
  // first bar has no previous value (treated as rising); then: grow, shrink, drop below zero, deepen, shrink
  expect(colors).toEqual([COLORS.up, COLORS.up, COLORS.upLight, COLORS.down, COLORS.down, COLORS.downLight]);
});

it("shows the deep thresholds only for strategies that ask for them (needs 20+ recent values)", () => {
  const n = 120;
  const long: ChartFile = {
    ...chart,
    bars: Array.from({ length: n }, (_, i) => [i + 1, 1, 1, 1, 1, 1]),
    macd: { macd: Array(n).fill(0), signal: Array(n).fill(0), hist: Array.from({ length: n }, (_, i) => i - 60) },
    rsi: Array(n).fill(50), ema50: Array(n).fill(1), ema200: Array(n).fill(1),
  };
  const on = buildChartData(long, macdCfg, "x");
  expect(on.deepLow).toBeLessThan(on.deepHigh!);
  expect(buildChartData(long, trendCfg, "x").deepLow).toBeNull();
  expect(buildChartData(chart, macdCfg, "x").deepLow).toBeNull(); // only 2 valid hist values
});

it("includes EMAs only when the strategy config asks for them, and carries RSI levels", () => {
  expect(buildChartData(chart, macdCfg, "x").ema50).toEqual([]);
  expect(buildChartData(chart, trendCfg, "x").ema50).toHaveLength(3);
  expect(buildChartData(chart, trendCfg, "x").rsiLevels).toEqual([40, 60]);
});
