import { clearCache } from "./api";
import type { ChartFile, MarketFile, PaperTradingFile, SignalRow, SignalsFile, StrategiesFile } from "./types";

export const UPDATED = new Date().toISOString();

const sess = (date: string, open: string, close: string, early = false) => ({
  date, open: `${date}T${open}:00+00:00`, close: `${date}T${close}:00+00:00`, early,
});

/** Calendar around Fri 2 Oct 2026 (EDT) and Thanksgiving 2026 (EST). Sat/Sun have no session. */
export const market: MarketFile = {
  updated_at: "2026-10-02T20:07:00+00:00",
  sessions: [
    sess("2026-10-01", "13:30", "20:00"), sess("2026-10-02", "13:30", "20:00"),
    sess("2026-10-05", "13:30", "20:00"), sess("2026-10-06", "13:30", "20:00"),
    sess("2026-11-25", "14:30", "21:00"), sess("2026-11-27", "14:30", "18:00", true),
  ],
  holidays: [{ date: "2026-11-26", name: "Thanksgiving" }],
};

export const strategies: StrategiesFile = {
  updated_at: UPDATED,
  strategies: [
    {
      id: "macd-rsi-reversal",
      name: "MACD + RSI Reversal",
      description: "Histogram climbs from a deep low while RSI crosses back above 20.",
      chart: { rsi_levels: [20, 25, 80], macd_deep: true, emas: false },
      timeframes: { "1d": { buy: 1, sell: 1 }, "4h": { buy: 1, sell: 0 } },
      version: "1.1.0",
      rules_version: "aa531796650b",
      history: [
        { version: "1.1.0", date: "2026-10-03", summary: "Signals now carry a conviction tier." },
        { version: "1.0.0", date: "2026-10-01", summary: "First version." },
      ],
    },
    {
      id: "trend-pullback",
      name: "Trend Pullback",
      description: "Pullback in an established trend.",
      chart: { rsi_levels: [40, 60], macd_deep: false, emas: true },
      timeframes: { "1d": { buy: 0, sell: 0 }, "4h": { buy: 0, sell: 0 } },
      version: "1.2.0",
      rules_version: "165d10977239",
      history: [
        { version: "1.2.0", date: "2026-10-03", summary: "Tested extra filters; none beat the current rules." },
        { version: "1.1.0", date: "2026-10-02", summary: "Raised the minimum history to 400 bars." },
        { version: "1.0.0", date: "2026-10-01", summary: "First version." },
      ],
    },
  ],
};

export const row = (over: Partial<SignalRow> = {}): SignalRow => ({
  ticker: "XOM", name: "Exxon Mobil", sector: "Energy", price: 108.42, side: "BUY", conviction: "standard",
  bars_ago: 0, fired_at: "2026-10-02T20:00:00+00:00", bar_time: 1790899200, details: {}, spark: [1, 2, 3, 2, 3],
  ...over,
});

export const signals: Record<string, SignalsFile> = {
  "macd-rsi-reversal/1d.json": {
    updated_at: UPDATED,
    signals: [
      row({}),
      // SELL is always low conviction: see scanner/strategies/base.py.
      row({ ticker: "NVDA", name: "NVIDIA", sector: "Information Technology", side: "SELL", conviction: "low", bars_ago: 1, invalidated: true }),
    ],
  },
  "macd-rsi-reversal/4h.json": { updated_at: UPDATED, signals: [row({ ticker: "AAL", name: "American Airlines", sector: "Industrials" })] },
  "trend-pullback/1d.json": { updated_at: UPDATED, signals: [] },
  "trend-pullback/4h.json": { updated_at: UPDATED, signals: [] },
};

export const chart: ChartFile = {
  ticker: "XOM", timeframe: "1d",
  bars: [[1, 10, 12, 9, 11, 100], [2, 11, 13, 10, 12, 100], [3, 12, 14, 11, 13, 100]],
  macd: { macd: [null, 0.1, 0.2], signal: [null, 0.05, 0.1], hist: [null, 0.05, 0.1] },
  rsi: [null, 40, 45], ema50: [10, 11, 12], ema200: [9, 9, 9],
  signals: [{ strategy_id: "macd-rsi-reversal", side: "BUY", bar_time: 3 }],
};

/** fetch stub serving the fixtures; any key in `fail` returns HTTP 500. */
export function stubFetch(fail: string[] = [], overrides: Record<string, unknown> = {}) {
  clearCache(); // api.ts keeps responses for the session, so each case starts from nothing
  const table: Record<string, unknown> = { "strategies.json": strategies, "market.json": market, "charts/1d/XOM.json": chart, ...signals, ...overrides };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const key = Object.keys(table).find((k) => url.endsWith(`data/${k}`));
      if (!key || fail.includes(key)) return new Response("nope", { status: 500 });
      return new Response(JSON.stringify(table[key]), { status: 200 });
    }),
  );
}

/** A paper-trading account holding one position, nothing closed yet. */
export const paperTradingFile: PaperTradingFile = {
  updated_at: "2026-10-12T20:10:00+00:00",
  as_of: "close",
  rules_version: "512f04ab1a78",
  version: "1.0.0",
  history: [{ version: "1.0.0", date: "2026-10-10", summary: "First version. Buys AMZN or AAPL when RSI(2) falls under 10 while the price is still above its 200-day average." }],
  symbols: ["AMZN", "AAPL"],
  account: {
    opening_balance: 100000, equity: 100592, cash: 50780, deployed_pct: 49.5,
    total_pl: 592, total_pl_pct: 0.592, realised_pl: 0, unrealised_pl: 592,
  },
  equity_curve: [
    { date: "2026-10-09", equity: 100000, in_position: false },
    { date: "2026-10-12", equity: 100592, in_position: true },
  ],
  positions: [{
    symbol: "AAPL", entry_date: "2026-10-06", entry_price: 332.64, qty: 148,
    price: 336.64, unrealised_pl: 592, unrealised_pl_pct: 1.21, bars_held: 4, max_hold: 10,
  }],
  signal_state: [
    { symbol: "AMZN", rsi2: 64.2, sma200: 230.1, price: 262.43, trend_gap_pct: 14,
      buy_below: 10, sell_above: 65, verdict: "Waiting", reason: "not oversold" },
    { symbol: "AAPL", rsi2: 31, sma200: 300, price: 336.64, trend_gap_pct: 12.2,
      buy_below: 10, sell_above: 65, verdict: "Held", reason: "4 of 10 bars" },
  ],
  trades: [],
  evaluation: {
    trades_closed: 0, trades_needed: 30, bps_per_trade: null, win_rate: null,
    mean_bars_held: null, slippage_bps: null, per_symbol: {}, per_rules_version: {},
    per_year: {},
    backtest: {
      AMZN: { trades: 232, bps_per_trade: 150.1, win_rate: 75.9, t_stat: 5.53, p_vs_random: 0.002, max_dd_pct: -27.7, mean_bars_held: 3.68, positive_years: "19/24", worst_trade_pct: -16.9 },
      AAPL: { trades: 245, bps_per_trade: 117.5, win_rate: 75.1, t_stat: 5.1, p_vs_random: 0.01, max_dd_pct: -32.4, mean_bars_held: 4.16, positive_years: "23/26", worst_trade_pct: -18.6 },
    },
    verdict: null,
  },
  runs: [{ at: "2026-10-12T19:25:08+00:00", date: "2026-10-12", mode: "live", orders: 1,
           late: false, skip_reason: null, minutes_to_close: 35 }],
};
