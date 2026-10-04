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
import { PaneValue } from "../lib/paneValue";
import { SignalLabelPrimitive } from "../lib/signalLabel";
import { smc } from "../lib/smc";
import { SmcOverlay } from "../lib/smcDraw";
import type { CandleStyle, ChartConfig, ChartFile } from "../types";

const ET = "America/New_York";
/** 12,345,678 -> "12.3M". Share counts are only ever read as an order of magnitude. */
const compact = (v: number) =>
  new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(v);
const dayFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const tickFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
const etFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: ET });

interface Props {
  data: ChartFile;
  config: ChartConfig;
  strategyId: string;
  candleStyle: CandleStyle;
  /** Smart Money Concepts overlay: structure, order blocks, gaps and zones. */
  showSmc: boolean;
}

/** TradingView-style chart: candles + signal marker, RSI pane with strategy levels, MACD pane. */
export function ChartView({ data, config, strategyId, candleStyle, showSmc }: Props) {
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
      // Tinted like the page rather than white, so the chart reads as part of the sheet, and
      // the three panes are divided by a visible rule instead of a hairline.
      layout: {
        background: { type: ColorType.Solid, color: COLORS.chartBg },
        textColor: "#625C55", fontFamily: "Inter, system-ui, sans-serif", fontSize: 12,
        panes: { separatorColor: COLORS.paneSeparator, separatorHoverColor: COLORS.accent, enableResize: false },
      },
      grid: { vertLines: { color: COLORS.grid }, horzLines: { color: COLORS.grid } },
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
    // Structure is read off real OHLC even when Heikin-Ashi candles are drawn, the same way
    // RSI and MACD are. Bar indices line up either way, so the overlay still registers.
    if (showSmc) candles.attachPrimitive(new SmcOverlay(smc(data.bars)));
    // Volume, TradingView's layout: an overlay in the bottom fifth of the price pane on its
    // own hidden scale, so it costs no vertical space and never rescales the candles. Drawn
    // before the EMAs so the lines stay on top of it.
    const volume = chart.addSeries(HistogramSeries, {
      priceScaleId: "", // an overlay scale of its own; the price axis keeps showing prices
      priceFormat: { type: "volume" },
      priceLineVisible: false, lastValueVisible: false,
    }, 0);
    volume.setData(b.volume);
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });

    if (b.showEmas) {
      chart.addSeries(LineSeries, { color: COLORS.ema50, lineWidth: 2, priceLineVisible: false, lastValueVisible: false, title: "" }, 0).setData(b.ema50);
      chart.addSeries(LineSeries, { color: COLORS.ema200, lineWidth: 2, priceLineVisible: false, lastValueVisible: false, title: "" }, 0).setData(b.ema200);
    }

    // Pane 1: RSI with the strategy's own levels (solid lines, no tags) plus faint 30/50/70 references
    const rsi = chart.addSeries(LineSeries, { color: COLORS.rsi, lineWidth: 2, priceLineVisible: false, lastValueVisible: false, title: "" }, 1);
    rsi.setData(b.rsi);
    // A dotted guide at the RSI value under the crosshair. Its reading is named in the pane's
    // corner rather than tagged on the scale; see PaneValue for why the scale will not do.
    const rsiAt = new Map(b.rsi.map((p) => [p.time as number, p.value]));
    const hover = rsi.createPriceLine({
      price: 0, color: COLORS.rsi, lineWidth: 1, lineStyle: LineStyle.Dotted,
      axisLabelVisible: false, title: "",
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
    chart.addSeries(LineSeries, { color: COLORS.macd, lineWidth: 2, priceLineVisible: false, lastValueVisible: false, title: "" }, 2).setData(b.macd);
    chart.addSeries(LineSeries, { color: COLORS.signal, lineWidth: 2, priceLineVisible: false, lastValueVisible: false, title: "" }, 2).setData(b.signal);

    // Named readings in each oscillator pane's corner, following the crosshair and falling back
    // to the latest bar. The crosshair's own price tag stays on the price pane, where the number
    // under the pointer is the price; on RSI and MACD it is an arbitrary y and only gets in the way.
    const at: { time: number | null } = { time: null };
    const macdAt = new Map(b.macd.map((p) => [p.time as number, p.value]));
    const signalAt = new Map(b.signal.map((p) => [p.time as number, p.value]));
    const reading = (by: Map<number, number>, series: { value: number }[]) => {
      const live = at.time === null ? undefined : by.get(at.time);
      return live ?? (series.length ? series[series.length - 1].value : null);
    };
    const chunk = (label: string, value: number | null, color: string) =>
      value === null ? [] : [{ text: `${label} ${value.toFixed(2)}`, color }];

    // The price pane gets a volume readout, because an overlay histogram has no scale of its
    // own to read and "how big was that bar" is the only question it is there to answer.
    const volAt = new Map(b.volume.map((p) => [p.time as number, p.value]));
    const volumeValue = new PaneValue(() => {
      const live = at.time === null ? undefined : volAt.get(at.time);
      const v = live ?? (b.volume.length ? b.volume[b.volume.length - 1].value : null);
      return v === null ? [] : [{ text: `Vol ${compact(v)}`, color: "#625C55" }];
    }, COLORS.chartBg);
    volume.attachPrimitive(volumeValue);

    const rsiValue = new PaneValue(() => chunk("RSI", reading(rsiAt, b.rsi), COLORS.rsi), COLORS.chartBg);
    const macdValue = new PaneValue(() => [
      ...chunk("MACD", reading(macdAt, b.macd), COLORS.macd),
      ...chunk("signal", reading(signalAt, b.signal), COLORS.signal),
    ], COLORS.chartBg);
    rsi.attachPrimitive(rsiValue);
    hist.attachPrimitive(macdValue);

    let priceTagOn = true;
    chart.subscribeCrosshairMove((param) => {
      at.time = param.time === undefined ? null : (param.time as number);
      const v = at.time === null ? undefined : rsiAt.get(at.time);
      hover.applyOptions(v === undefined ? { lineVisible: false } : { price: v, lineVisible: true });
      rsiValue.refresh();
      macdValue.refresh();
      volumeValue.refresh();
      if (param.paneIndex === undefined) return; // pointer left the chart; the crosshair is gone anyway
      const onPrice = param.paneIndex === 0;
      if (onPrice !== priceTagOn) {
        priceTagOn = onPrice;
        chart.applyOptions({ crosshair: { horzLine: { labelVisible: onPrice } } });
      }
    });

    // Price gets the most room; RSI and MACD share the rest. Stretch factors survive container resizes.
    const [price, rsiPane, macdPane] = chart.panes();
    price.setStretchFactor(0.56);
    rsiPane.setStretchFactor(0.19);
    macdPane.setStretchFactor(0.25);
    // Show the most recent ~130 bars with room on the right so the last marker label is not clipped.
    chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, b.candles.length - 130), to: b.candles.length + 6 });

    return () => chart.remove();
  }, [data, config, strategyId, candleStyle, showSmc]);

  const last = data.signals.find((s) => s.strategy_id === strategyId);
  return (
    <div
      ref={host}
      className="chart-canvas"
      role="img"
      aria-label={`${data.ticker} ${data.timeframe === "1d" ? "daily" : "4 hour"} candlestick chart with volume, RSI and MACD${last ? `, ${last.side} signal marked` : ""}`}
    />
  );
}
