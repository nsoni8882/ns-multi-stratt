import { expect, test } from "vitest";
import { labFixture } from "../lab-fixture";
import { BASE_T, deflatedBar, filterTrades, gateRows, kpis, normInv, stageCounts, trialFor } from "./labStats";

// Values computed by lab/stats.py:deflated_threshold(n, 0.0) -- the page and the gate must agree.
const PYTHON: [number, number][] = [[2, 0.5197553442805939], [3, 0.8528044961506948], [10, 1.5745983013457499],
  [100, 2.530602893201685], [1000, 3.2551215136527225], [10000, 3.8606648555104397]];

test("the raised bar matches the Python gate", () => {
  for (const [n, expected] of PYTHON) expect(deflatedBar(n, 0)).toBeCloseTo(expected, 6);
});

test("the bar never drops below its floor and rises with the search", () => {
  expect(deflatedBar(1)).toBe(BASE_T);
  expect(deflatedBar(10)).toBe(BASE_T);
  expect(deflatedBar(10000)).toBeGreaterThan(deflatedBar(1000));
  expect(deflatedBar(1000)).toBeGreaterThan(BASE_T);
});

test("the normal quantile is symmetric and exact at the centre", () => {
  expect(normInv(0.5)).toBeCloseTo(0, 9);
  expect(normInv(0.975)).toBeCloseTo(1.959964, 5);
  expect(normInv(0.1)).toBeCloseTo(-normInv(0.9), 9);
});

test("gate rows show pass, fail and not-run honestly", () => {
  const f = labFixture();
  const rejected = f.strategies.find((s) => s.stage === "rejected")!;
  const rows = gateRows(rejected, trialFor(f.trials, rejected.fingerprint));
  expect(rows.some((r) => r.ok === false)).toBe(true);
  expect(rows.find((r) => r.name === "holdout")!.ok).toBeNull(); // never opened after a failure
  const fresh = f.strategies.find((s) => s.stage === "proposed")!;
  expect(gateRows(fresh, undefined).every((r) => r.ok === null)).toBe(true);
  const holdout = gateRows(rejected, trialFor(f.trials, rejected.fingerprint)).find((r) => r.name === "holdout")!;
  expect(holdout.detail).not.toMatch(/\d/); // the seal shows no numbers
});

test("kpis come from the equity curve and the gate metrics, and are null without them", () => {
  const f = labFixture();
  const best = f.strategies.find((s) => s.stage === "shadow")!;
  const k = kpis(best);
  expect(k.netPnl).toBeCloseTo(best.equity_curve.at(-1)!.equity - 100_000, 6);
  expect(k.maxDrawdownPct!).toBeLessThanOrEqual(0);
  expect(kpis(undefined).netPnl).toBeNull();
  expect(kpis(f.strategies.find((s) => s.stage === "proposed")).netPnl).toBeNull();
});

test("stage counts and trade filters", () => {
  const f = labFixture();
  const c = stageCounts(f.strategies);
  expect(Object.values(c).reduce((a, b) => a + b, 0)).toBe(f.strategies.length);
  const best = f.strategies.find((s) => s.stage === "shadow")!;
  const all = filterTrades(f.trades, best.id, { symbol: "", reason: "" });
  expect(all.length).toBeGreaterThan(100);
  const sym = all[0].symbol;
  expect(filterTrades(f.trades, best.id, { symbol: sym, reason: "" }).every((t) => t.symbol === sym)).toBe(true);
});

test("gate details use correct grammar for one year", () => {
  const f = labFixture();
  const s = { ...f.strategies[0], backtest: { ...f.strategies[0].backtest, years: { "2026": { mean_bps: 1, days: 10 } } } };
  expect(gateRows(s, undefined).find((r) => r.name === "drop_best_year")!.detail).toBe("1 year tested");
});

test("a result from before the per-trade check shows it as not measured, never as passed", () => {
  const f = labFixture();
  const old = f.strategies[1];
  const { per_trade_bps: _drop, ...rest } = old.backtest;
  void _drop;
  const rows = gateRows({ ...old, backtest: rest }, trialFor(f.trials, old.fingerprint));
  const row = rows.find((r) => r.name === "positive_per_trade")!;
  expect(row.ok).toBeNull();
  expect(row.detail).toBe("not measured then");
});
