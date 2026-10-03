import { convictionLabel, convictionTitle, sparkColor } from "../lib/conviction";
import { barsAgoLabel } from "../lib/filters";
import type { SignalRow } from "../types";
import { Sparkline } from "./Sparkline";
import { SignalPill } from "./SignalPill";

export function StockCard({ row, onOpen }: { row: SignalRow; onOpen: (row: SignalRow) => void }) {
  const badge = convictionLabel(row.conviction);
  const fired = `Fired ${new Date(row.fired_at).toLocaleString()}`;
  const why = convictionTitle(row.conviction, row.side);
  return (
    <button
      type="button"
      className={`scard${row.conviction === "low" ? " weak" : ""}`}
      onClick={() => onOpen(row)}
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
      {badge && <span className={`conv ${row.conviction}`}>{badge}</span>}
    </button>
  );
}
