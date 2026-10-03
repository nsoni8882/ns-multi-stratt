export type Timeframe = "1d" | "4h";
export type Side = "BUY" | "SELL";
/** How much the backtested edge supports this signal; set by the scanner. See scanner/strategies/base.py. */
export type Conviction = "high" | "standard" | "low";

export interface ChartConfig {
  /** Every RSI level this strategy draws: one per threshold, including conviction tiers. */
  rsi_levels: number[];
  macd_deep: boolean;
  emas: boolean;
}

/** One entry in a strategy's change history, newest first. See scanner/strategies/base.py. */
export interface Release {
  version: string;
  /** ISO date, YYYY-MM-DD */
  date: string;
  summary: string;
}

export interface StrategySummary {
  id: string;
  name: string;
  description: string;
  chart: ChartConfig;
  timeframes: Record<Timeframe, { buy: number; sell: number }>;
  /** Semver of the rules that produced these lists. Optional: a cached strategies.json
   *  written before versioning shipped has no version, and must still render. */
  version?: string;
  history?: Release[];
  /** Fingerprint of the thresholds in force; changes whenever the rules do. */
  rules_version?: string;
}

export interface StrategiesFile {
  updated_at: string;
  strategies: StrategySummary[];
}

export interface SignalRow {
  ticker: string;
  name: string;
  sector: string;
  price: number;
  side: Side;
  conviction: Conviction;
  /** Fired on an earlier bar, and RSI has since crossed back past the level that triggered
   *  it — the setup described no longer holds. Optional: absent in data cached from before
   *  this shipped. */
  invalidated?: boolean;
  bars_ago: number;
  fired_at: string;
  bar_time: number;
  details: Record<string, number>;
  spark: (number | null)[];
}

export interface SignalsFile {
  updated_at: string;
  signals: SignalRow[];
}

export interface ChartFile {
  ticker: string;
  timeframe: Timeframe;
  /** [unix seconds, open, high, low, close, volume] */
  bars: [number, number, number, number, number, number][];
  macd: { macd: (number | null)[]; signal: (number | null)[]; hist: (number | null)[] };
  rsi: (number | null)[];
  ema50: (number | null)[];
  ema200: (number | null)[];
  signals: { strategy_id: string; side: Side; bar_time: number }[];
}

export interface MarketSession {
  date: string;
  open: string;
  close: string;
  early: boolean;
}

/** NYSE calendar written by the scanner (market.json): about 2 weeks back and 6 weeks ahead. */
export interface MarketFile {
  updated_at: string;
  sessions: MarketSession[];
  holidays: { date: string; name: string }[];
}

/** What the scan that produced this deploy knew about itself (health.json). Every field is
 *  optional: data published before the health record existed must still render. */
export interface HealthFile {
  updated_at?: string;
  duration_seconds?: number;
  universe?: number;
  fetch?: Record<Timeframe, { fetched: number; failed: number; failed_tickers: string[] }>;
  strategy_error_count?: number;
  signals?: { found: number; recorded: number };
  event?: string;
  tests?: Record<string, string>;
  published_with_failing_tests?: boolean;
}

export type CandleStyle = "ha" | "real";
