import { useEffect, useRef } from "react";
import { convictionLabel, convictionTitle, sparkColor } from "../lib/conviction";
import { barsAgoLabel } from "../lib/filters";
import type { SignalRow } from "../types";
import { Sparkline } from "./Sparkline";
import { SignalPill } from "./SignalPill";

/** Deliberately not "ignore this": backtested over 12 years, stale signals whose premise had
 *  died actually did slightly better than ones still intact. The badge reports that the
 *  described setup no longer holds, and leaves the judgement to the reader. */
const STALE_WHY =
  "This fired on an earlier bar and RSI has since crossed back past the level that triggered it, " +
  "so the setup described above no longer holds.";

interface Props {
  row: SignalRow;
  onOpen: (row: SignalRow) => void;
  /** Called once the pointer settles, to fetch this ticker's chart before it is asked for. */
  onPrefetch?: (row: SignalRow) => void;
}

export function StockCard({ row, onOpen, onPrefetch }: Props) {
  // Sweeping the mouse across the grid should not request forty charts, so the pointer has
  // to rest on a card before its chart is fetched.
  const timer = useRef<number | undefined>(undefined);
  const cool = () => window.clearTimeout(timer.current);
  const warm = () => {
    cool();
    if (onPrefetch) timer.current = window.setTimeout(() => onPrefetch(row), 150);
  };
  useEffect(() => cool, []);
  const badge = convictionLabel(row.conviction);
  const fired = `Fired ${new Date(row.fired_at).toLocaleString()}`;
  const why = convictionTitle(row.conviction, row.side);
  return (
    <button
      type="button"
      className={`scard${row.conviction === "low" ? " weak" : ""}`}
      onClick={() => onOpen(row)}
      onMouseEnter={warm}
      onMouseLeave={cool}
      onFocus={warm}
      onBlur={cool}
      title={why ? `${fired}\n${why}` : fired}
    >
      <span className="row between">
        <span className="tk">{row.ticker}</span>
        <SignalPill side={row.side} conviction={row.conviction} />
      </span>
      <span className="tag">{row.name}</span>
      <Sparkline values={row.spark} color={sparkColor(row.side, row.conviction)} />
      <span className="row between">
        <span className="num"><strong>${row.price.toFixed(2)}</strong></span>
        <span className="tag">{barsAgoLabel(row.bars_ago)}</span>
      </span>
      <span className="row">
        {badge && <span className={`conv ${row.conviction}`}>{badge}</span>}
        {row.invalidated && (
          <span className="conv stale" title={STALE_WHY}>Setup changed</span>
        )}
      </span>
    </button>
  );
}
