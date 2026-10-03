import type { SignalRow } from "../types";

/**
 * One line of plain English answering "why is this a BUY / SELL?", for the chart overlay.
 *
 * The prose is per strategy, but every number in it comes from the `details` the scanner
 * recorded on the signal bar — including `rsi_level`, the threshold that actually fired it.
 * Nothing here restates a threshold from the rules, so this copy cannot drift out of step
 * with `scanner/strategies/`. Data cached from before `rsi_level` shipped has no level, so
 * each sentence also reads correctly without it.
 */
export function signalReason(strategyId: string, row: SignalRow): string {
  const d = row.details ?? {};
  const rsi = fmt(d.rsi);
  const level = fmt(d.rsi_level, 0);
  const buy = row.side === "BUY";

  if (strategyId === "trend-pullback") {
    const trend = buy
      ? "Pullback in an uptrend: price and the 50 EMA above the 200 EMA"
      : "Bounce in a downtrend: price and the 50 EMA below the 200 EMA";
    return `${trend}, RSI(14) ${cross(buy, level, rsi)}.`;
  }

  if (strategyId === "macd-rsi-reversal") {
    const hist = buy
      ? "Selling exhausted: MACD histogram turning up from a deep low"
      : "Buying exhausted: MACD histogram turning down from a deep high";
    return `${hist}, RSI(14) ${cross(buy, level, rsi)}.`;
  }

  return `Every condition this strategy requires for a ${row.side} was met on this candle.`;
}

/** "crossed back above 40 to 42.9", degrading as the numbers go missing. */
function cross(buy: boolean, level: string | null, rsi: string | null): string {
  const dir = buy ? "above" : "below";
  if (level === null) return `crossed back ${dir} its trigger level${rsi ? ` to ${rsi}` : ""}`;
  return `crossed back ${dir} ${level}${rsi ? ` to ${rsi}` : ""}`;
}

function fmt(v: number | undefined, dp = 1): string | null {
  return typeof v === "number" && Number.isFinite(v) ? v.toFixed(dp) : null;
}
