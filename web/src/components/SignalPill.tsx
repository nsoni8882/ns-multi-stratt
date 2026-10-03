import type { Side } from "../types";

export function SignalPill({ side }: { side: Side }) {
  return (
    <span className={`pill ${side === "BUY" ? "buy" : "sell"}`}>
      <svg viewBox="0 0 12 12" aria-hidden="true">
        <path d={side === "BUY" ? "M6 2l4 5H2z" : "M6 10L2 5h8z"} fill="currentColor" />
      </svg>
      {side}
    </span>
  );
}
