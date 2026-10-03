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

it("isStale is true only after 36 hours", () => {
  const now = new Date("2026-10-03T12:00:00Z");
  expect(isStale("2026-10-02T12:00:00Z", now)).toBe(false);
  expect(isStale("2026-10-01T23:00:00Z", now)).toBe(true);
});
