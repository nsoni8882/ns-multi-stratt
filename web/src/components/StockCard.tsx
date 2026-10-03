import { barsAgoLabel } from "../lib/filters";
import type { SignalRow } from "../types";
import { Sparkline } from "./Sparkline";
import { SignalPill } from "./SignalPill";

export function StockCard({ row, onOpen }: { row: SignalRow; onOpen: (row: SignalRow) => void }) {
  return (
    <button type="button" className="scard" onClick={() => onOpen(row)} title={`Fired ${new Date(row.fired_at).toLocaleString()}`}>
      <span className="row between">
        <span className="tk">{row.ticker}</span>
        <SignalPill side={row.side} />
      </span>
      <span className="tag">{row.name}</span>
      <Sparkline values={row.spark} color={row.side === "BUY" ? "#27694B" : "#9E2F45"} />
      <span className="row between">
        <span className="num"><strong>${row.price.toFixed(2)}</strong></span>
        <span className="tag">{barsAgoLabel(row.bars_ago)}</span>
      </span>
    </button>
  );
}
