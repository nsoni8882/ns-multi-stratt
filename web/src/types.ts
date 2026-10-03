export type Timeframe = "1d" | "4h";
export type Side = "BUY" | "SELL";

export interface ChartConfig {
  rsi_levels: [number, number];
  macd_deep: boolean;
  emas: boolean;
}

export interface StrategySummary {
  id: string;
  name: string;
  description: string;
  chart: ChartConfig;
  timeframes: Record<Timeframe, { buy: number; sell: number }>;
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
