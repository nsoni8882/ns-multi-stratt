import type { Side, SignalRow } from "../types";

export const ALL_SECTORS = "All sectors";

export interface Filters {
  side: "ALL" | Side;
  sector: string;
  query: string;
}

export const DEFAULT_FILTERS: Filters = { side: "ALL", sector: ALL_SECTORS, query: "" };

export function filterSignals(rows: SignalRow[], f: Filters): SignalRow[] {
  const q = f.query.trim().toLowerCase();
  return rows.filter(
    (r) =>
      (f.side === "ALL" || r.side === f.side) &&
      (f.sector === ALL_SECTORS || r.sector === f.sector) &&
      (q === "" || r.ticker.toLowerCase().includes(q) || r.name.toLowerCase().includes(q)),
  );
}

export function sectorsOf(rows: SignalRow[]): string[] {
  return [ALL_SECTORS, ...[...new Set(rows.map((r) => r.sector))].sort()];
}

export function barsAgoLabel(n: number): string {
  return n === 0 ? "Latest bar" : `${n} bar${n === 1 ? "" : "s"} ago`;
}

/** Hours between two instants, not counting Saturdays and Sundays (UTC): the scanner only runs on weekdays. */
export function weekdayHours(from: Date, to: Date): number {
  const HOUR = 3_600_000;
  let total = 0;
  for (let t = from.getTime(); t < to.getTime(); t += HOUR) {
    const day = new Date(t).getUTCDay();
    if (day !== 0 && day !== 6) total += Math.min(HOUR, to.getTime() - t) / HOUR;
  }
  return total;
}

/** Stale = no update for over 48 weekday hours (covers a weekend plus a Monday market holiday). */
export function isStale(updatedAt: string, now: Date, hours = 48): boolean {
  return weekdayHours(new Date(updatedAt), now) > hours;
}
