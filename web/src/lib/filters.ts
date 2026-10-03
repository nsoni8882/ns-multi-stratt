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

export function isStale(updatedAt: string, now: Date, hours = 36): boolean {
  return now.getTime() - new Date(updatedAt).getTime() > hours * 3_600_000;
}
