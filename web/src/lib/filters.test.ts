import { signals } from "../test-fixtures";
import { ALL_SECTORS, DEFAULT_FILTERS, barsAgoLabel, filterSignals, isStale, sectorsOf } from "./filters";

const rows = signals["macd-rsi-reversal/1d.json"].signals;

describe("filterSignals", () => {
  it("returns everything by default", () => {
    expect(filterSignals(rows, DEFAULT_FILTERS)).toHaveLength(2);
  });
  it("filters by side, sector and query (ticker or name, case-insensitive)", () => {
    expect(filterSignals(rows, { ...DEFAULT_FILTERS, side: "SELL" }).map((r) => r.ticker)).toEqual(["NVDA"]);
    expect(filterSignals(rows, { ...DEFAULT_FILTERS, sector: "Energy" }).map((r) => r.ticker)).toEqual(["XOM"]);
    expect(filterSignals(rows, { ...DEFAULT_FILTERS, query: " exxon " }).map((r) => r.ticker)).toEqual(["XOM"]);
    expect(filterSignals(rows, { ...DEFAULT_FILTERS, query: "nv" }).map((r) => r.ticker)).toEqual(["NVDA"]);
  });
  it("returns an empty list when nothing matches", () => {
    expect(filterSignals(rows, { ...DEFAULT_FILTERS, query: "zzz" })).toEqual([]);
  });
});

it("sectorsOf lists unique sectors alphabetically after 'All sectors'", () => {
  expect(sectorsOf(rows)).toEqual([ALL_SECTORS, "Energy", "Information Technology"]);
  expect(sectorsOf([])).toEqual([ALL_SECTORS]);
});

it("barsAgoLabel", () => {
  expect(barsAgoLabel(0)).toBe("Latest bar");
  expect(barsAgoLabel(1)).toBe("1 bar ago");
  expect(barsAgoLabel(2)).toBe("2 bars ago");
});

describe("isStale (weekday hours, so weekends do not trigger it)", () => {
  it("is false over a normal weekend (Fri 20:05 UTC run, checked Mon 12:00 UTC)", () => {
    expect(isStale("2026-10-02T20:05:00Z", new Date("2026-10-05T12:00:00Z"))).toBe(false);
  });
  it("is false after a Monday market holiday (Fri run, checked Tue 14:00 UTC)", () => {
    expect(isStale("2026-10-02T20:05:00Z", new Date("2026-10-06T14:00:00Z"))).toBe(false);
  });
  it("is true when a weekday run has been missing for over 48 weekday hours", () => {
    expect(isStale("2026-10-01T23:00:00Z", new Date("2026-10-06T12:00:00Z"))).toBe(true);
    expect(isStale("2026-09-28T12:00:00Z", new Date("2026-09-30T20:00:00Z"))).toBe(true);
  });
  it("is false for a fresh update", () => {
    expect(isStale("2026-10-02T12:00:00Z", new Date("2026-10-02T20:00:00Z"))).toBe(false);
  });
});
