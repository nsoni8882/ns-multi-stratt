import { useEffect, useRef } from "react";
import { getChart } from "../api";
import { useAsync } from "../hooks";
import type { ChartConfig, SignalRow, Timeframe } from "../types";
import { ChartView } from "./ChartView";
import { COLORS } from "../lib/chartData";
import { ErrorState, Loading } from "./Feedback";
import { SignalPill } from "./SignalPill";

interface Props {
  row: SignalRow;
  tf: Timeframe;
  strategyId: string;
  config: ChartConfig;
  onClose: () => void;
}

export function ChartModal({ row, tf, strategyId, config, onClose }: Props) {
  const chart = useAsync(() => getChart(tf, row.ticker), [tf, row.ticker]);
  const closeBtn = useRef<HTMLButtonElement>(null);

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
        {chart.loading && <Loading what="chart" />}
        {chart.error && <ErrorState error={chart.error} onRetry={chart.retry} />}
        {chart.data && <ChartView data={chart.data} config={config} strategyId={strategyId} />}
        <div className="legend">
          {config.emas && (
            <>
              <span><i className="sw" style={{ background: COLORS.ema50 }} />EMA 50</span>
              <span><i className="sw" style={{ background: COLORS.ema200 }} />EMA 200</span>
            </>
          )}
          <span>The BUY / SELL box marks the candle where the signal fired</span>
          <span>Terracotta lines = this strategy's RSI levels and MACD thresholds</span>
        </div>
      </div>
    </div>
  );
}
