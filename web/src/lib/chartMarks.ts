import type { Side } from "../types";

export type Bar = [number, number, number, number, number, number];
/** A trade reduced to the two dates a chart can mark. */
export type Dated = { entry_date: string | null; exit_date: string | null };

/** Turn trade dates into markers on the bars they happened on.
 *
 *  The ledger records a date; the chart is keyed by each bar's open timestamp. A date with
 *  no matching bar is dropped rather than snapped to a neighbour — a marker on the wrong
 *  candle is worse than no marker, because it would misrepresent where the bot acted.
 */
export function marksForDates(bars: Bar[], trades: Dated[]): { side: Side; bar_time: number }[] {
  const byDate = new Map<string, number>();
  for (const [time] of bars) {
    byDate.set(new Date(time * 1000).toISOString().slice(0, 10), time);
  }
  const marks: { side: Side; bar_time: number }[] = [];
  for (const t of trades) {
    const inAt = t.entry_date ? byDate.get(t.entry_date) : undefined;
    if (inAt !== undefined) marks.push({ side: "BUY", bar_time: inAt });
    const outAt = t.exit_date ? byDate.get(t.exit_date) : undefined;
    if (outAt !== undefined) marks.push({ side: "SELL", bar_time: outAt });
  }
  return marks;
}
