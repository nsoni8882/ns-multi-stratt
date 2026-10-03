import type { ChartFile, MarketFile, SignalRow, SignalsFile, StrategiesFile } from "./types";

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
      row({ ticker: "NVDA", name: "NVIDIA", sector: "Information Technology", side: "SELL", conviction: "low", bars_ago: 1 }),
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
