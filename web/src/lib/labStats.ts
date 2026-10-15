import type { LabBreakdowns, LabStage, LabStrategy, LabTrade, LabTrial } from "../types";
import { NA, ratio } from "./labFormat";

/** These mirror lab/config.py. They are display constants: the gate itself only ever runs in
 *  Python, and the page must not decide anything. If config.py moves, move these. */
export const START_EQUITY = 100_000;
export const MIN_TRADES = 400;
export const MIN_DAYS = 150;
export const BASE_T = 2.5;

export const PIPELINE: LabStage[] = ["proposed", "backtested", "shadow", "paper", "kept"];
export const SIDELINED: LabStage[] = ["rejected", "retired"];
export const STAGE_LABEL: Record<LabStage, string> = {
  proposed: "Proposed", backtested: "Backtested", shadow: "Shadow", paper: "Paper",
  kept: "Kept", rejected: "Rejected", retired: "Retired",
};

/** Acklam's rational approximation of the standard normal quantile (|error| < 1.2e-9). */
export function normInv(p: number): number {
  const a = [-3.969683028665376e1, 2.209460984245205e2, -2.759285104469687e2, 1.38357751867269e2, -3.066479806614716e1, 2.506628277459239];
  const b = [-5.447609879822406e1, 1.615858368580409e2, -1.556989798598866e2, 6.680131188771972e1, -1.328068155288572e1];
  const c = [-7.784894002430293e-3, -3.223964580411365e-1, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783];
  const d = [7.784695709041462e-3, 3.224671290700398e-1, 2.445134137142996, 3.754408661907416];
  const lo = 0.02425;
  if (p < lo) {
    const q = Math.sqrt(-2 * Math.log(p));
    return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  }
  if (p > 1 - lo) return -normInv(1 - p);
  const q = p - 0.5;
  const r = q * q;
  return ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q) /
    (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
}

/** The t a strategy has to reach after `n` ideas have been tried. Mirrors lab/stats.py. */
export function deflatedBar(n: number, base = BASE_T): number {
  if (n < 2) return base;
  const gamma = 0.5772156649015329;
  const eMax = (1 - gamma) * normInv(1 - 1 / n) + gamma * normInv(1 - 1 / (n * Math.E));
  return Math.max(base, eMax);
}

export interface GateRow { name: string; label: string; ok: boolean | null; detail: string }

const GATE_LABEL: [string, string][] = [
  ["min_trades", "Enough trades"], ["min_days", "Enough days"],
  ["positive_expectancy", "Positive expectancy"], ["deflated_t", "Clears the raised bar"],
  ["both_halves", "Both halves positive"], ["drop_best_year", "No single year carries it"],
  ["cost_stress", "Survives doubled costs"], ["holdout", "Sealed holdout"],
];

/** The gate checklist for one strategy. `ok` is null when the gate has not run (or, for the
 *  holdout, was never opened because an earlier check failed). The holdout shows no numbers,
 *  by design. */
export function gateRows(s: LabStrategy, trial: LabTrial | undefined): GateRow[] {
  const m = s.backtest;
  const detail: Record<string, string> = {
    min_trades: m.n_trades == null ? NA : `${m.n_trades} of ${MIN_TRADES}`,
    min_days: m.n_days == null ? NA : `${m.n_days} of ${MIN_DAYS}`,
    positive_expectancy: m.mean_bps == null ? NA : `${m.mean_bps.toFixed(1)} bps a day`,
    deflated_t: m.t == null ? NA : `t ${ratio(m.t)} vs ${ratio(m.threshold ?? trial?.threshold)}`,
    both_halves: m.halves_bps ? `${m.halves_bps[0].toFixed(1)} / ${m.halves_bps[1].toFixed(1)} bps` : NA,
    drop_best_year: Object.keys(m.years ?? {}).length ? `${Object.keys(m.years ?? {}).length} years tested` : NA,
    cost_stress: "at 2x costs",
    holdout: "pass or fail only",
  };
  return GATE_LABEL.map(([name, label]) => {
    let ok: boolean | null = null;
    if (trial) {
      if (name === "holdout") ok = trial.holdout_look ? !trial.failed.includes("holdout") : null;
      else ok = !trial.failed.includes(name);
    }
    return { name, label, ok, detail: name === "holdout" && ok === null ? "not opened" : detail[name] };
  });
}

export interface Kpis {
  netPnl: number | null; returnPct: number | null; winRate: number | null;
  profitFactor: number | null; sharpe: number | null; maxDrawdownPct: number | null; expectancyBps: number | null;
}

export function kpis(s: LabStrategy | undefined): Kpis {
  const none: Kpis = { netPnl: null, returnPct: null, winRate: null, profitFactor: null, sharpe: null, maxDrawdownPct: null, expectancyBps: null };
  if (!s) return none;
  const curve = s.equity_curve;
  const last = curve[curve.length - 1];
  return {
    netPnl: last ? last.equity - START_EQUITY : null,
    returnPct: last ? (last.equity / START_EQUITY - 1) * 100 : null,
    winRate: s.backtest.win_rate ?? null,
    profitFactor: s.backtest.profit_factor ?? null,
    sharpe: s.backtest.sharpe ?? null,
    maxDrawdownPct: curve.length ? Math.min(...curve.map((p) => p.drawdown)) * 100 : null,
    expectancyBps: s.backtest.mean_bps ?? null,
  };
}

export function stageCounts(strategies: LabStrategy[]): Record<LabStage, number> {
  const out = Object.fromEntries([...PIPELINE, ...SIDELINED].map((st) => [st, 0])) as Record<LabStage, number>;
  for (const s of strategies) out[s.stage] += 1;
  return out;
}

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
export const weekdayOrder = (b: LabBreakdowns["by_weekday"]) =>
  [...b].sort((x, y) => WEEKDAYS.indexOf(x.key) - WEEKDAYS.indexOf(y.key));
export const hourOrder = (b: LabBreakdowns["by_hour"]) => [...b].sort((x, y) => Number(x.key) - Number(y.key));

export interface TradeFilter { symbol: string; reason: string }
export const filterTrades = (trades: LabTrade[], strategyId: string | undefined, f: TradeFilter) =>
  trades.filter((t) => (!strategyId || t.strategy === strategyId) &&
    (!f.symbol || t.symbol === f.symbol) && (!f.reason || t.exit_reason === f.reason));

export const trialFor = (trials: LabTrial[], fingerprint: string) =>
  [...trials].reverse().find((t) => t.fingerprint === fingerprint);
