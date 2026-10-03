import type { Conviction, Side } from "../types";

/** Short badge text, or null when the signal is an ordinary one needing no annotation. */
export function convictionLabel(c: Conviction): string | null {
  if (c === "high") return "Strong";
  if (c === "low") return "Weaker";
  return null;
}

/**
 * Why a signal is tiered, for the card's tooltip. The tiers come from the scanner's own
 * backtest (see scanner/strategies/base.py): deeper RSI crosses carried a much larger edge,
 * and the short legs of both strategies carried none.
 */
export function convictionTitle(c: Conviction, side: Side): string {
  if (c === "high") return "Strongest tier: the deepest RSI cross, which carried the largest backtested edge.";
  if (c === "low") {
    return side === "SELL"
      ? "Weaker signal: over 12 years of backtesting this short leg did not beat holding cash."
      : "Weaker signal: this tier carried little backtested edge.";
  }
  return "";
}

/** Sparkline colour: low-conviction signals are drawn muted so they read as secondary. */
export function sparkColor(side: Side, c: Conviction): string {
  if (c === "low") return "#A89F93";
  return side === "BUY" ? "#27694B" : "#9E2F45";
}
