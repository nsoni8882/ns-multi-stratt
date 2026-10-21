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

/** The minimum a chart overlay needs to title itself. SignalRow satisfies it structurally. */
export interface ChartSubject {
  ticker: string;
  name: string;
  sector: string;
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

/** The paper-trading account's state, as trader/export.py publishes it. */
export interface PaperAccount {
  opening_balance: number;
  equity: number;
  cash: number;
  deployed_pct: number;
  total_pl: number;
  total_pl_pct: number;
  realised_pl: number;
  unrealised_pl: number;
}

export interface EquityPoint {
  date: string;
  equity: number;
  /** Was the bot holding something that day? Flat stretches are deliberate, not a gap. */
  in_position: boolean;
}

export interface PaperPosition {
  symbol: string;
  entry_date: string | null;
  entry_price: number;
  qty: number;
  price: number;
  unrealised_pl: number;
  unrealised_pl_pct: number;
  bars_held: number | null;
  max_hold: number;
}

export interface PaperSignalState {
  symbol: string;
  rsi2: number | null;
  sma200: number | null;
  price: number | null;
  trend_gap_pct: number | null;
  buy_below: number;
  sell_above: number;
  /** "Oversold" | "Waiting" | "Held" | "Trend gate blocked" | "Exiting" | "No data" */
  verdict: string;
  reason: string | null;
}

export interface PaperRoundTrip {
  symbol: string;
  entry_date: string | null;
  entry_price: number;
  exit_date: string | null;
  exit_price: number;
  qty: number | null;
  bars_held: number | null;
  exit_reason: string | null;
  pl: number;
  pl_pct: number | null;
  /** The cost of deciding on a 15:25 partial bar but filling in the closing auction. */
  slippage_bps: number | null;
  rules_version: string | null;
}

export interface PaperStats {
  trades_closed: number;
  bps_per_trade: number | null;
  win_rate: number | null;
  mean_bars_held: number | null;
  slippage_bps: number | null;
}

export interface BacktestExpectation {
  trades: number;
  bps_per_trade: number;
  win_rate: number;
  t_stat: number;
  p_vs_random: number;
  max_dd_pct: number;
  mean_bars_held: number;
  positive_years: string;
  worst_trade_pct: number;
}

export interface PaperEvaluation extends PaperStats {
  trades_needed: number;
  /** Fills the ledger could not pair into a round trip. Surfaced, not hidden. */
  unpaired_buys?: number;
  unpaired_sells?: number;
  per_symbol: Record<string, PaperStats>;
  per_rules_version: Record<string, PaperStats>;
  per_year: Record<string, PaperStats>;
  backtest: Record<string, BacktestExpectation>;
  /** Stays null until trades_closed >= trades_needed. See trader/ACCEPTANCE.md. */
  verdict: string | null;
}

export interface PaperRun {
  at: string;
  date: string;
  mode: string;
  orders: number;
  late: boolean;
  skip_reason: string | null;
  minutes_to_close?: number;
  errors?: { symbol?: string; stage?: string; error?: string }[];
}

export interface PaperTradingFile {
  updated_at: string;
  /** What the account figures are marked at. */
  as_of: "close" | "intraday";
  rules_version: string;
  /** Semver of the trading rules that produced this file. */
  version: string;
  /** Newest first, shown in the clock-icon overlay like the strategy tabs. */
  history: Release[];
  symbols: string[];
  /** The session the rule state was read on; null before the bot has ever decided. */
  signal_state_as_of: string | null;
  account: PaperAccount;
  equity_curve: EquityPoint[];
  positions: PaperPosition[];
  signal_state: PaperSignalState[];
  trades: PaperRoundTrip[];
  evaluation: PaperEvaluation;
  runs: PaperRun[];
}
