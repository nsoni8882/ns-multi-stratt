import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  LineStyle,
  createChart,
  type UTCTimestamp,
} from "lightweight-charts";
import { useEffect, useRef } from "react";
import { COLORS, buildChartData } from "../lib/chartData";
import { SignalLabelPrimitive } from "../lib/signalLabel";
import type { CandleStyle, ChartConfig, ChartFile } from "../types";

const ET = "America/New_York";
const dayFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const tickFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
const etFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: ET });

interface Props {
  data: ChartFile;
  config: ChartConfig;
  strategyId: string;
  candleStyle: CandleStyle;
}

/** TradingView-style chart: candles + signal marker, RSI pane with strategy levels, MACD pane. */
export function ChartView({ data, config, strategyId, candleStyle }: Props) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const b = buildChartData(data, config, strategyId, candleStyle);
    const intraday = data.timeframe === "4h";
    const toMs = (t: UTCTimestamp) => (t as number) * 1000;

    const chart = createChart(el, {
      autoSize: true,
      handleScroll: { vertTouchDrag: false }, // on phones a vertical swipe scrolls the page, not the chart
      layout: { background: { type: ColorType.Solid, color: "#FFFFFF" }, textColor: "#625C55", fontFamily: "Inter, system-ui, sans-serif", fontSize: 12, panes: { separatorColor: "#EFE6DB" } },
      grid: { vertLines: { color: "#F3EBE0" }, horzLines: { color: "#F3EBE0" } },
      rightPriceScale: { borderVisible: false },
      timeScale: {
        borderVisible: false,
        timeVisible: intraday,
        tickMarkFormatter: (t: UTCTimestamp) => (intraday ? etFmt : tickFmt).format(toMs(t)),
      },
      localization: { timeFormatter: (t: UTCTimestamp) => (intraday ? etFmt : dayFmt).format(toMs(t)) },
    });

    // Pane 0: price
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: COLORS.up, borderUpColor: COLORS.up, wickUpColor: COLORS.up,
      downColor: COLORS.down, borderDownColor: COLORS.down, wickDownColor: COLORS.down, // solid, TradingView style
    }, 0);
    candles.setData(b.candles);
    b.markers.forEach((m) => candles.attachPrimitive(new SignalLabelPrimitive(m)));
    if (b.showEmas) {
      chart.addSeries(LineSeries, { color: COLORS.ema50, lineWidth: 2, priceLineVisible: false, lastValueVisible: false, title: "" }, 0).setData(b.ema50);
      chart.addSeries(LineSeries, { color: COLORS.ema200, lineWidth: 2, priceLineVisible: false, lastValueVisible: false, title: "" }, 0).setData(b.ema200);
    }

    // Pane 1: RSI with the strategy's own levels (solid lines, no tags) plus faint 30/50/70 references
    const rsi = chart.addSeries(LineSeries, { color: COLORS.rsi, lineWidth: 2, priceLineVisible: false, lastValueVisible: true, title: "" }, 1);
    rsi.setData(b.rsi);
    // RSI at the crosshair, as a tag on that pane's scale. The crosshair's own label only
    // appears in the pane the pointer is in, and the pointer is almost always over the candles,
    // so reading "what was RSI on that bar" otherwise means counting gridlines.
    const rsiAt = new Map(b.rsi.map((p) => [p.time as number, p.value]));
    const hover = rsi.createPriceLine({
      price: 0, color: COLORS.rsi, lineWidth: 1, lineStyle: LineStyle.Dotted,
      axisLabelVisible: false, title: "",
    });
    chart.subscribeCrosshairMove((param) => {
      const v = param.time === undefined ? undefined : rsiAt.get(param.time as number);
      hover.applyOptions(v === undefined ? { axisLabelVisible: false } : { price: v, axisLabelVisible: true });
    });
    [30, 50, 70].forEach((price) =>
      rsi.createPriceLine({ price, color: "#E0D6C8", lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: false, title: "" }),
    );
    b.rsiLevels.forEach((price) =>
      rsi.createPriceLine({ price, color: COLORS.accent, lineWidth: 1, lineStyle: LineStyle.Solid, axisLabelVisible: false, title: "" }),
    );

    // Pane 2: MACD histogram + lines, zero line, and (Strategy 1) the deep-histogram thresholds
    const hist = chart.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false }, 2);
    hist.setData(b.hist);
    hist.createPriceLine({ price: 0, color: "#625C55", lineWidth: 1, lineStyle: LineStyle.Solid, axisLabelVisible: false, title: "" });
    if (b.deepLow !== null && b.deepHigh !== null) {
      hist.createPriceLine({ price: b.deepHigh, color: COLORS.accent, lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: false, title: "" });
      hist.createPriceLine({ price: b.deepLow, color: COLORS.accent, lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: false, title: "" });
    }
    // Only the current MACD and signal values are shown, as coloured tags on the price scale (no names).
    chart.addSeries(LineSeries, { color: COLORS.macd, lineWidth: 2, priceLineVisible: false, lastValueVisible: true, title: "" }, 2).setData(b.macd);
    chart.addSeries(LineSeries, { color: COLORS.signal, lineWidth: 2, priceLineVisible: false, lastValueVisible: true, title: "" }, 2).setData(b.signal);

    // Price gets the most room; RSI and MACD share the rest. Stretch factors survive container resizes.
    const [price, rsiPane, macdPane] = chart.panes();
    price.setStretchFactor(0.56);
    rsiPane.setStretchFactor(0.19);
    macdPane.setStretchFactor(0.25);
    // Show the most recent ~130 bars with room on the right so the last marker label is not clipped.
    chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, b.candles.length - 130), to: b.candles.length + 6 });

    return () => chart.remove();
  }, [data, config, strategyId, candleStyle]);

  const last = data.signals.find((s) => s.strategy_id === strategyId);
  return (
    <div
      ref={host}
      className="chart-canvas"
      role="img"
      aria-label={`${data.ticker} ${data.timeframe === "1d" ? "daily" : "4 hour"} candlestick chart with RSI and MACD${last ? `, ${last.side} signal marked` : ""}`}
    />
  );
}
