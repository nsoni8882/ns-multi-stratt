import { useNow } from "../hooks";
import { formatNextUpdate, marketStatus } from "../lib/market";
import type { MarketFile } from "../types";

/** One line under the top bar: is the market open, and when the next update is due. */
export function MarketBar({ market }: { market: MarketFile }) {
  const now = useNow(60_000);
  const s = marketStatus(market, now);
  const parts = [
    s.open ? "Market open" : "Market closed",
    s.open ? (s.earlyClose ? "Early close today" : null) : s.reason,
    s.nextUpdate ? `next update ${formatNextUpdate(s.nextUpdate, now)}` : null,
  ].filter(Boolean);
  return (
    <div className="marketbar" data-testid="market-status" role="status">
      <span className={`dot ${s.open ? "on" : "off"}`} aria-hidden="true" />
      <span>{parts.join(" · ")}</span>
    </div>
  );
}
