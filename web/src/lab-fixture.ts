/** A deterministic, realistic lab.json for tests and the visual check. It is never published:
 *  the real file comes from lab/export.py, and the page shows an empty state until then. */
import type { LabBreakdowns, LabFile, LabMetrics, LabStage, LabStrategy, LabTrade, LabTrial } from "./types";

function rng(seed: number) {
  let a = seed >>> 0;
  const next = () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const normal = () => Math.sqrt(-2 * Math.log(next() || 1e-9)) * Math.cos(2 * Math.PI * next());
  return { next, normal };
}

const SYMBOLS = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AVGO"];
const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

function tradingDays(start: string, n: number): string[] {
  const out: string[] = [];
  const d = new Date(`${start}T12:00:00Z`);
  while (out.length < n) {
    if (d.getUTCDay() % 6 !== 0) out.push(d.toISOString().slice(0, 10));
    d.setUTCDate(d.getUTCDate() + 1);
  }
  return out;
}

function makeTrades(id: string, seed: number, meanBps: number, days: string[], perDay: number): LabTrade[] {
  const r = rng(seed);
  const trades: LabTrade[] = [];
  for (const day of days) {
    const n = Math.max(0, Math.round(perDay + r.normal() * 0.8));
    for (let i = 0; i < n; i++) {
      const hour = r.next() < 0.6 ? 14 : r.next() < 0.7 ? 15 : 16; // 9:30-11:30 ET is 14-16 UTC (EDT)
      const entry = new Date(`${day}T${String(hour).padStart(2, "0")}:${String(Math.floor(r.next() * 60)).padStart(2, "0")}:00Z`);
      const held = 2 + Math.floor(r.next() * 30);
      const exit = new Date(entry.getTime() + held * 5 * 60_000);
      const cost = 3 + r.next() * 3;
      const net = meanBps + r.normal() * 55;
      const entryPx = 80 + r.next() * 400;
      const reason = net > 60 ? "target" : net < -60 ? "stop" : r.next() < 0.5 ? "time" : "session";
      trades.push({
        strategy: id, symbol: SYMBOLS[Math.floor(r.next() * SYMBOLS.length)], side: "long",
        entry_time: entry.toISOString(), exit_time: exit.toISOString(),
        entry_px: Math.round(entryPx * 100) / 100, exit_px: Math.round(entryPx * (1 + net / 1e4) * 100) / 100,
        bars_held: held, exit_reason: reason, gross_bps: Math.round((net + cost) * 100) / 100,
        cost_bps: Math.round(cost * 100) / 100, net_bps: Math.round(net * 100) / 100,
      });
    }
  }
  return trades;
}

const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);
const sd = (xs: number[]) => {
  const m = mean(xs);
  return xs.length > 1 ? Math.sqrt(xs.reduce((a, b) => a + (b - m) ** 2, 0) / (xs.length - 1)) : 0;
};

function curveOf(trades: LabTrade[], size = 0.1) {
  const byDay = new Map<string, number>();
  for (const t of trades) byDay.set(t.entry_time.slice(0, 10), (byDay.get(t.entry_time.slice(0, 10)) ?? 0) + (t.net_bps / 1e4) * size);
  let equity = 100_000;
  let peak = equity;
  return [...byDay.entries()].sort().map(([t, r]) => {
    equity *= 1 + r;
    peak = Math.max(peak, equity);
    return { t, equity: Math.round(equity * 100) / 100, drawdown: Math.round((equity / peak - 1) * 1e5) / 1e5 };
  });
}

function metricsOf(trades: LabTrade[], threshold: number): LabMetrics {
  const byDay = new Map<string, number[]>();
  for (const t of trades) byDay.set(t.entry_time.slice(0, 10), [...(byDay.get(t.entry_time.slice(0, 10)) ?? []), t.net_bps]);
  const daily = [...byDay.entries()].sort().map(([, v]) => mean(v));
  const wins = trades.filter((t) => t.net_bps > 0).reduce((a, t) => a + t.net_bps, 0);
  const losses = -trades.filter((t) => t.net_bps < 0).reduce((a, t) => a + t.net_bps, 0);
  const half = Math.floor(daily.length / 2);
  const years: LabMetrics["years"] = {};
  for (const [day, v] of byDay) {
    const y = day.slice(0, 4);
    years[y] = { mean_bps: 0, days: (years[y]?.days ?? 0) + 1 };
    years[y].mean_bps = mean([...byDay.entries()].filter(([d]) => d.startsWith(y)).map(([, vals]) => mean(vals)));
    void v;
  }
  return {
    n_trades: trades.length, n_days: daily.length, mean_bps: mean(daily),
    t: sd(daily) ? mean(daily) / (sd(daily) / Math.sqrt(daily.length)) : 0, threshold,
    win_rate: trades.length ? trades.filter((t) => t.net_bps > 0).length / trades.length : 0,
    profit_factor: losses > 0 ? wins / losses : null,
    sharpe: sd(daily) ? (mean(daily) / sd(daily)) * Math.sqrt(252) : 0,
    halves_bps: [mean(daily.slice(0, half)), mean(daily.slice(half))], years,
  };
}

function breakdownsOf(trades: LabTrade[]): LabBreakdowns {
  const group = (key: (t: LabTrade) => string) => {
    const g = new Map<string, number[]>();
    for (const t of trades) g.set(key(t), [...(g.get(key(t)) ?? []), t.net_bps]);
    return [...g.entries()].map(([k, v]) => ({
      key: k, net_bps: Math.round(mean(v) * 100) / 100,
      total_pct: Math.round(v.reduce((a, b) => a + b, 0)) / 100, trades: v.length,
    }));
  };
  const et = (t: LabTrade) => new Date(new Date(t.entry_time).getTime() - 4 * 3_600_000);
  const daily = new Map<string, number[]>();
  for (const t of trades) daily.set(t.entry_time.slice(0, 10), [...(daily.get(t.entry_time.slice(0, 10)) ?? []), t.net_bps]);
  const vals = trades.map((t) => t.net_bps);
  const lo = Math.min(...vals, 0);
  const hi = Math.max(...vals, 1);
  const step = (hi - lo) / 20 || 1;
  const histogram = Array.from({ length: 20 }, (_, i) => ({
    from_bps: Math.round((lo + i * step) * 100) / 100, to_bps: Math.round((lo + (i + 1) * step) * 100) / 100,
    count: vals.filter((v) => v >= lo + i * step && (i === 19 ? v <= hi : v < lo + (i + 1) * step)).length,
  }));
  const reasons: Record<string, number> = {};
  for (const t of trades) reasons[t.exit_reason] = (reasons[t.exit_reason] ?? 0) + 1;
  return {
    by_symbol: group((t) => t.symbol), by_hour: group((t) => String(et(t).getUTCHours())),
    by_weekday: group((t) => WEEKDAYS[et(t).getUTCDay()]),
    daily_pnl: [...daily.entries()].sort().map(([day, v]) => ({ day, net_bps: Math.round(mean(v) * 100) / 100 })),
    exit_reasons: reasons, histogram,
  };
}

const EMPTY_BREAKDOWNS: LabBreakdowns = {
  by_symbol: [], by_hour: [], by_weekday: [], daily_pnl: [], exit_reasons: {}, histogram: [],
};
const RISK = { stop_pct: 0.006, target_pct: 0.012, max_hold_bars: 40, size_pct: 0.1, max_concurrent: 5 };

export function labFixture(): LabFile {
  const days = tradingDays("2025-10-01", 250);
  const tA = makeTrades("a1f3c9d2e7b4", 11, 11, days, 1.4);
  const tB = makeTrades("b2e4d0a3f8c5", 23, 0.5, days, 1.2);
  const build = (
    id: string, name: string, family: string, stage: LabStage, hypothesis: string, trades: LabTrade[],
    threshold: number, params: Record<string, number>,
  ): LabStrategy => ({
    id, fingerprint: id, name, family, stage, hypothesis, params, risk: RISK,
    failure_rules: stage === "shadow"
      ? [{ metric: "mean_bps", op: "lt", threshold: 0, after_trades: 30 }, { metric: "max_drawdown_pct", op: "lt", threshold: -8, after_trades: 10 }]
      : null,
    backtest: trades.length ? metricsOf(trades, threshold) : {},
    live: null, equity_curve: curveOf(trades),
    history: stage === "proposed" ? [{ stage: "proposed", when: "2026-10-14T15:02:00Z", reason: "registered" }]
      : [{ stage: "proposed", when: "2026-10-13T14:00:00Z", reason: "registered" },
         { stage: "backtested", when: "2026-10-13T14:06:00Z", reason: "gate evaluated" },
         ...(stage === "rejected" ? [{ stage: "rejected" as LabStage, when: "2026-10-13T14:06:00Z", reason: "failed: deflated_t, cost_stress" }] : [])],
    breakdowns: trades.length ? breakdownsOf(trades) : EMPTY_BREAKDOWNS,
  });

  const strategies: LabStrategy[] = [
    build("a1f3c9d2e7b4", "Opening-range breakout, stocks in play", "orb", "shadow",
      "Names breaking their first 15-minute high on heavy relative volume keep going into the late morning.",
      tA, 2.54, { range_bars: 3, last_entry_bar: 30, min_rvol: 1.5, rvol_days: 14 }),
    build("b2e4d0a3f8c5", "VWAP stretch reversion", "vwap_reversion", "rejected",
      "A stock that closes well under its session VWAP is pulled back toward it by the afternoon.",
      tB, 2.7, { dev_pct: 0.006, min_bar: 6, last_entry_bar: 60 }),
    build("c3d5e1b4a9f6", "Gap-down fade", "gap_fade", "rejected",
      "Large caps gapping down more than 1% overnight recover part of the gap in the first hour.",
      makeTrades("c3d5e1b4a9f6", 37, 2, days.slice(0, 60), 1.1), 2.7, { gap_pct: 0.01, entry_bar: 1 }),
    build("d4e6f2c5b0a7", "Intraday RSI(2) reversion", "rsi2_intraday", "backtested",
      "The daily RSI(2) reversion edge also shows up on 15-minute bars while price holds above its trend.",
      makeTrades("d4e6f2c5b0a7", 41, 6, days, 1.0), 2.7, { rsi_len: 2, buy_below: 10, trend_len: 78, last_entry_bar: 70 }),
    build("e5f7a3d6c1b8", "Opening-range breakout, 15-minute bars", "orb", "proposed",
      "The same breakout on 15-minute bars filters out five-minute noise at the open.",
      [], 2.7, { range_bars: 2, last_entry_bar: 12, min_rvol: 1.5, rvol_days: 14 }),
  ];
  const [a, b, c, d] = strategies;
  void c;
  const trial = (s: LabStrategy, over: Partial<LabTrial>): LabTrial => ({
    when: "2026-10-13T14:06:00Z", fingerprint: s.fingerprint, name: s.name, family: s.family,
    hypothesis: s.hypothesis, verdict: "fail", failed: [], threshold: 2.7, n_trades: s.backtest.n_trades ?? 0,
    mean_bps: s.backtest.mean_bps ?? 0, t: s.backtest.t ?? 0, holdout_look: false, ...over,
  });
  const fillers: LabTrial[] = Array.from({ length: 21 }, (_, i) => ({
    when: `2026-10-${String(1 + Math.floor(i / 2)).padStart(2, "0")}T15:${String(10 + i).padStart(2, "0")}:00Z`,
    fingerprint: `f${String(i).padStart(11, "0")}`, name: `Gap-down fade, variant ${i + 1}`, family: "gap_fade",
    verdict: "fail" as const, failed: i % 3 === 0 ? ["min_trades", "min_days", "deflated_t"] : ["positive_expectancy", "deflated_t", "both_halves"],
    threshold: 2.5 + i * 0.01, n_trades: 90 + i * 7, mean_bps: -3 + (i % 5), t: -1 + (i % 4) * 0.4, holdout_look: false,
  }));
  const trials = [...fillers,
    trial(b, { failed: ["deflated_t", "cost_stress"] }),
    trial(strategies[2], { failed: ["min_trades", "min_days", "deflated_t"], n_trades: 66 }),
    trial(d, { verdict: "pass", failed: [], holdout_look: true, threshold: 2.54 }),
    trial(a, { verdict: "pass", failed: [], holdout_look: true, threshold: 2.5 })];

  const live = strategies.filter((s) => ["shadow", "paper", "kept"].includes(s.stage));
  return {
    meta: {
      generated_at: "2026-10-15T16:20:00Z", universe_version: "9f2c41ab07de", rules_version: "07cd38731b91",
      trials_total: trials.length, holdout_start: "2026-04-15", cost_bps_per_side: { mega: 1.5, large: 3 },
    },
    account: null, equity_curve: [],
    summary: {
      strategies: strategies.length, live: live.length, rejected: strategies.filter((s) => s.stage === "rejected").length,
      retired: 0, trials: trials.length, passed: trials.filter((t) => t.verdict === "pass").length,
    },
    strategies, positions: [], trades: [...tA, ...tB], trials, runs: [],
  };
}
