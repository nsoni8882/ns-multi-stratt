import type { ChartFile, SignalsFile, StrategiesFile, Timeframe } from "./types";

export async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${import.meta.env.BASE_URL}data/${path}`);
  if (!res.ok) throw new Error(`Could not load ${path} (HTTP ${res.status})`);
  return (await res.json()) as T;
}

export const getStrategies = () => getJson<StrategiesFile>("strategies.json");
export const getSignals = (strategyId: string, tf: Timeframe) => getJson<SignalsFile>(`${strategyId}/${tf}.json`);
export const getChart = (tf: Timeframe, ticker: string) => getJson<ChartFile>(`charts/${tf}/${ticker}.json`);
