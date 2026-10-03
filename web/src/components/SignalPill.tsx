import type { Conviction, Side } from "../types";

/**
 * BUY / SELL badge. A low-conviction signal is drawn as an outline rather than a filled
 * badge, so it does not read as a peer of the signals that carry a measured edge.
 */
export function SignalPill({ side, conviction = "standard" }: { side: Side; conviction?: Conviction }) {
  const tone = side === "BUY" ? "buy" : "sell";
  return (
    <span className={`pill ${tone}${conviction === "low" ? " faint" : ""}`}>
      <svg viewBox="0 0 12 12" aria-hidden="true">
        <path d={side === "BUY" ? "M6 2l4 5H2z" : "M6 10L2 5h8z"} fill="currentColor" />
      </svg>
      {side}
    </span>
  );
}
