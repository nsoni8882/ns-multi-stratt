import { useEffect, useRef, useState } from "react";
import { getChart } from "../api";
import { useAsync } from "../hooks";
import type { CandleStyle, ChartConfig, SignalRow, Timeframe } from "../types";
import { chartView, loadChartView } from "../lib/chartViewLoader";
import { COLORS } from "../lib/chartData";
import { SMC_COLORS } from "../lib/smc";
import { ErrorState, Loading } from "./Feedback";
import { SignalPill } from "./SignalPill";
import { signalReason } from "../lib/signalReason";

interface Props {
  row: SignalRow;
  tf: Timeframe;
  strategyId: string;
  config: ChartConfig;
  onClose: () => void;
}

const PREF_KEY = "candleStyle";
const SMC_KEY = "showSmc";

/** Both preferences fall back to their default when storage is blocked (private mode). */
function readStyle(): CandleStyle {
  try {
    return window.localStorage.getItem(PREF_KEY) === "real" ? "real" : "ha";
  } catch {
    return "ha";
  }
}

function readSmc(): boolean {
  try {
    return window.localStorage.getItem(SMC_KEY) !== "off";
  } catch {
    return true;
  }
}

function remember(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* the preference just isn't remembered */
  }
}

export function ChartModal({ row, tf, strategyId, config, onClose }: Props) {
  const chart = useAsync(() => getChart(tf, row.ticker), [tf, row.ticker]);
  const closeBtn = useRef<HTMLButtonElement>(null);
  const [style, setStyle] = useState<CandleStyle>(readStyle);
  const [showSmc, setShowSmc] = useState<boolean>(readSmc);
  // StrategyPage warms this while the browser is idle, so it is usually here already and the
  // chart draws on the first frame. If it is not, the loading state covers the one-off wait.
  const [ChartView, setChartView] = useState(() => chartView());
  const pick = (next: CandleStyle) => {
    setStyle(next);
    remember(PREF_KEY, next);
  };
  const toggleSmc = () => {
    setShowSmc((on) => {
      remember(SMC_KEY, on ? "off" : "on");
      return !on;
    });
  };

  useEffect(() => {
    if (ChartView) return;
    let alive = true;
    void loadChartView().then(() => alive && setChartView(() => chartView()));
    return () => {
      alive = false;
    };
  }, [ChartView]);

  useEffect(() => {
    // Stop the page behind the modal from scrolling (iOS Safari scrolls it otherwise).
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    closeBtn.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      opener?.focus();
    };
  }, [onClose]);

  return (
    <div className="modal" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet" role="dialog" aria-modal="true" aria-label={`${row.ticker} chart`}>
        <div className="head">
          <div>
            <h2>{row.ticker}</h2>
            <div className="tag">{row.name} · {row.sector} · {tf.toUpperCase()}</div>
          </div>
          <div className="row">
            <SignalPill side={row.side} />
            <button ref={closeBtn} type="button" className="x" aria-label="Close chart" onClick={onClose}>×</button>
          </div>
        </div>
        <div className="row between chartbar">
          <div className="seg" role="group" aria-label="Candle style">
            <button type="button" aria-pressed={style === "ha"} onClick={() => pick("ha")}>Heikin-Ashi</button>
            <button type="button" aria-pressed={style === "real"} onClick={() => pick("real")}>Real</button>
          </div>
          <div className="seg" role="group" aria-label="Overlays">
            <button type="button" aria-pressed={showSmc} onClick={toggleSmc} title="Structure, order blocks, fair value gaps and premium/discount zones">SMC</button>
          </div>
        </div>
        {chart.loading && <Loading what="chart" />}
        {chart.error && <ErrorState error={chart.error} onRetry={chart.retry} />}
        {chart.data && !ChartView && <Loading what="chart" />}
        {chart.data && ChartView && (
          <ChartView data={chart.data} config={config} strategyId={strategyId} candleStyle={style} showSmc={showSmc} />
        )}
        <div className="why">
          <div className="whysig"><SignalPill side={row.side} conviction={row.conviction} /></div>
          <p>{signalReason(strategyId, row)}</p>
        </div>
        <div className="legend">
          {config.emas && (
            <>
              <span><i className="sw" style={{ background: COLORS.ema50 }} />EMA 50</span>
              <span><i className="sw" style={{ background: COLORS.ema200 }} />EMA 200</span>
            </>
          )}
          {showSmc && (
            <>
              <span><i className="sw" style={{ background: SMC_COLORS.bull }} />BOS / CHoCH — a close through the last swing high or low</span>
              <span><i className="sw" style={{ background: SMC_COLORS.internalBullOb }} />Order blocks, newest darkest, drawn until price trades through them</span>
              <span><i className="sw" style={{ background: SMC_COLORS.bullFvg }} />Fair value gaps</span>
              <span>Premium / Equilibrium / Discount split the last swing range</span>
            </>
          )}
          <span>The BUY / SELL box marks the candle where the signal fired</span>
          <span><i className="sw" style={{ background: COLORS.volumeUp }} />Volume, shaded by the direction of the candle above it{style === "ha" ? " — the Heikin-Ashi one, as drawn" : ""}</span>
          <span>RSI, MACD, EMAs{showSmc && " and the SMC overlay"} always use real prices, not Heikin-Ashi</span>
          <span>Terracotta lines = this strategy's RSI levels and MACD thresholds</span>
        </div>
      </div>
    </div>
  );
}
