import { useMemo, useState } from "react";
import type { ChartConfig, PaperPosition, PaperRoundTrip, StrategySummary } from "../types";
import type { Dated } from "../lib/chartMarks";
import { ChartModal } from "./ChartModal";
import { price } from "./paperFormat";

/** The indicator setup these charts use. Read from the shipped MACD + RSI Reversal entry
 *  rather than copied, so if that strategy's chart changes, these follow it instead of
 *  quietly drifting into a different set of overlays. */
const BORROW_FROM = "macd-rsi-reversal";
const FALLBACK: ChartConfig = { rsi_levels: [20, 25, 80], macd_deep: true, emas: false };

/** This strategy trades daily bars only, so its charts are always the daily ones. */
const TF = "1d" as const;

export function PaperCharts({ symbols, positions, trades, strategies }: {
  symbols: string[];
  positions: PaperPosition[];
  trades: PaperRoundTrip[];
  strategies?: StrategySummary[];
}) {
  const [open, setOpen] = useState<string | null>(null);
  const config = strategies?.find((s) => s.id === BORROW_FROM)?.chart ?? FALLBACK;
  const held = useMemo(() => new Map(positions.map((p) => [p.symbol, p])), [positions]);

  return (
    <section className="panel" aria-label="Charts">
      <div className="row between">
        <h2>Charts</h2>
        <div className="tag">Daily bars, with every fill marked</div>
      </div>
      <div className="big">
        {symbols.map((symbol) => {
          const pos = held.get(symbol);
          const done = trades.filter((t) => t.symbol === symbol).length;
          return (
            <button
              key={symbol}
              type="button"
              className="bigcard paper-tile"
              aria-label={`${symbol} chart`}
              onClick={() => setOpen(symbol)}
            >
              <div className="row between">
                <span className="tk">{symbol}</span>
                <span className={`pill ${pos ? "buy" : "faint"}`}>{pos ? "Held" : "Flat"}</span>
              </div>
              <p className="tag">
                {pos
                  ? `${pos.qty} shares from ${price.format(pos.entry_price)}`
                  : "No position"}
                {done > 0 && ` · ${done} closed ${done === 1 ? "trade" : "trades"} marked`}
              </p>
              <span className="link">Open chart</span>
            </button>
          );
        })}
      </div>
      {open && (
        <PaperChartModal
          symbol={open}
          config={config}
          positions={positions}
          trades={trades}
          onClose={() => setOpen(null)}
        />
      )}
    </section>
  );
}

/** Wraps ChartModal so the markers can be built from the chart's own bars, which only exist
 *  once the chart file has loaded. */
function PaperChartModal({ symbol, config, positions, trades, onClose }: {
  symbol: string;
  config: ChartConfig;
  positions: PaperPosition[];
  trades: PaperRoundTrip[];
  onClose: () => void;
}) {
  const pos = positions.find((p) => p.symbol === symbol);
  const mine: Dated[] = [
    ...trades.filter((t) => t.symbol === symbol),
    ...(pos ? [{ entry_date: pos.entry_date, exit_date: null }] : []),
  ];
  const note = pos
    ? `Holding ${pos.qty} shares bought at ${price.format(pos.entry_price)}` +
      `${pos.entry_date ? ` on ${pos.entry_date}` : ""}. ` +
      "Arrows mark where this strategy actually bought and sold."
    : mine.length > 0
      ? "Not holding this one. Arrows mark where this strategy bought and sold it."
      : "Not holding this one, and it has not traded yet. " +
        "Arrows will appear here once it does.";

  return (
    <ChartModal
      subject={{ ticker: symbol, name: symbol, sector: "Paper account" }}
      tf={TF}
      strategyId="rsi2-reversion"
      config={config}
      note={note}
      markerDates={mine}
      onClose={onClose}
    />
  );
}
