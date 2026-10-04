import type { SignalRow } from "../types";

/**
 * One or two lines of plain English answering "why is this a BUY / SELL *here*?", for the
 * chart overlay.
 *
 * The sentence shape is per strategy; every number in it is this ticker's own, taken from
 * the `details` the scanner recorded on the signal bar — how deep the dip went, how long it
 * lasted, how far price sits from each mean, how many bars the histogram has been turning.
 * Two signals from the same strategy therefore read differently.
 *
 * Two rules hold the copy honest:
 *
 * 1. **No threshold is written here.** `rsi_level` is the level that actually fired the
 *    signal, so this text cannot drift out of step with `scanner/strategies/`. Where a
 *    window is only a descriptive lookback (the "recent high" below is 20 bars) the copy
 *    says "recent" rather than naming a number it cannot verify.
 * 2. **Every clause degrades.** Data cached before any of these fields shipped still
 *    renders: each fragment is dropped when its number is missing, and the sentence is
 *    assembled from whatever is left.
 */
export function signalReason(strategyId: string, row: SignalRow): string {
  const d = row.details ?? {};
  const buy = row.side === "BUY";
  const rsiNow = fmt(d.rsi);
  const level = fmt(d.rsi_level, 0);
  // The verb phrase alone; "RSI(14)" is prefixed only where the sentence has not said it yet.
  const crossed = cross(buy, level, rsiNow);

  if (strategyId === "trend-pullback") {
    const trend = buy
      ? "Pullback in an uptrend"
      : "Bounce in a downtrend";
    const place = join([
      distance(d.above_ema50, "the 50 EMA"),
      distance(d.above_ema200, "the 200 EMA"),
    ]);
    const dip = join([
      bars(d.dip_bars, buy ? "under" : "over", level),
      num(d.rsi_trough) ? `${buy ? "troughed" : "peaked"} at ${fmt(d.rsi_trough)}` : null,
    ]);
    return sentences([
      place ? `${trend}: price ${place}.` : `${trend}.`,
      dip ? `${dip}, and ${crossed}.` : `RSI(14) ${crossed}.`,
    ]);
  }

  if (strategyId === "macd-rsi-reversal") {
    const move = buy ? "Down" : "Up";
    const decline = num(d.off_high)
      ? `${move} ${pct(d.off_high)} from its recent ${buy ? "high" : "low"}`
      : null;
    const extreme = num(d.rsi_trough)
      ? `RSI(14) ${buy ? "bottoming" : "topping"} at ${fmt(d.rsi_trough)}`
      : null;
    // "Momentum fading", not "selling exhausted": the rule reads price and momentum only.
    // Nothing here checks volume, and every volume reading of exhaustion that was measured
    // on this strategy made it worse — see research/FINDINGS.md.
    const turn = buy ? "Downside momentum fading" : "Upside momentum fading";
    const hist = [
      histMove(d.recovery_bars, d.hist_trough, d.macd_hist, buy),
      extreme ? `RSI ${crossed}` : `RSI(14) ${crossed}`,
    ].filter((p): p is string => !!p).join(", and ");
    return sentences([
      join([decline, extreme]) ? `${join([decline, extreme])}.` : null,
      hist ? `${turn}: ${hist}.` : `${turn}.`,
    ]);
  }

  return `Every condition this strategy requires for a ${row.side} was met on this candle.`;
}

/** "MACD histogram up 3 bars from a -1.20 low to -0.41", degrading as numbers go missing. */
function histMove(barsUp: number | undefined, from: number | undefined,
                  to: number | undefined, buy: boolean): string | null {
  const dir = buy ? "up" : "down";
  const run = num(barsUp) && barsUp! > 0 ? `${barsUp} bar${barsUp === 1 ? "" : "s"}` : null;
  const low = num(from) ? `a ${fmt(from, 2)} ${buy ? "low" : "high"}` : `a deep ${buy ? "low" : "high"}`;
  const here = num(to) ? ` to ${fmt(to, 2)}` : "";
  return `MACD histogram ${dir}${run ? ` ${run}` : ""} from ${low}${here}`;
}

/** "1.8% above the 50 EMA" / "0.4% below the 200 EMA". */
function distance(v: number | undefined, what: string): string | null {
  if (!num(v)) return null;
  return `${pct(v)} ${v! >= 0 ? "above" : "below"} ${what}`;
}

/** "RSI(14) spent 6 bars under 40", only when both the count and the level are known. */
function bars(n: number | undefined, under: string, level: string | null): string | null {
  if (!num(n) || n! <= 0 || level === null) return null;
  return `RSI(14) spent ${n} bar${n === 1 ? "" : "s"} ${under} ${level}`;
}

/** "crossed back above 40 to 42.9", degrading as the numbers go missing. */
function cross(buy: boolean, level: string | null, rsi: string | null): string {
  const dir = buy ? "above" : "below";
  if (level === null) return `crossed back ${dir} its trigger level${rsi ? ` to ${rsi}` : ""}`;
  return `crossed back ${dir} ${level}${rsi ? ` to ${rsi}` : ""}`;
}

function num(v: number | undefined): boolean {
  return typeof v === "number" && Number.isFinite(v);
}

function fmt(v: number | undefined, dp = 1): string | null {
  return num(v) ? v!.toFixed(dp) : null;
}

/** A fraction as a magnitude: -0.123 -> "12.3%". The direction is carried by the words. */
function pct(v: number | undefined): string {
  return `${(Math.abs(v!) * 100).toFixed(1)}%`;
}

function join(parts: (string | null)[]): string {
  return parts.filter((p): p is string => !!p).join(", ");
}

function sentences(parts: (string | null)[]): string {
  return parts.filter((p): p is string => !!p).join(" ");
}
