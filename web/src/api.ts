import type { ChartFile, HealthFile, MarketFile, SignalsFile, StrategiesFile, Timeframe } from "./types";

/**
 * Responses, in flight or settled, keyed by path. A scan's output does not change while the
 * page is open, so a file fetched once is reused for the rest of the session: flipping
 * 1D/4H, going back to a list, or reopening a chart costs nothing the second time.
 * Failures are evicted, so Retry actually retries.
 */
const cache = new Map<string, Promise<unknown>>();

/** Requests index.html started before this bundle had finished loading. */
type Preload = Record<string, Promise<Response> | undefined>;

/** Take a head-start request if there is one; it can only be read once, so it is consumed. */
function headStart(path: string): Promise<Response> | undefined {
  const started = (window as { __preload?: Preload }).__preload;
  const res = started?.[path];
  if (started && res) delete started[path];
  return res;
}

export function getJson<T>(path: string): Promise<T> {
  const hit = cache.get(path) as Promise<T> | undefined;
  if (hit) return hit;
  const request = headStart(path) ?? fetch(`${import.meta.env.BASE_URL}data/${path}`);
  const pending = request.then(async (res) => {
    if (!res.ok) throw new Error(`Could not load ${path} (HTTP ${res.status})`);
    return (await res.json()) as T;
  });
  pending.catch(() => cache.delete(path));
  cache.set(path, pending);
  return pending;
}

/** Forget every cached response. Tests call this between cases; the app never needs it. */
export function clearCache(): void {
  cache.clear();
  delete (window as { __preload?: Preload }).__preload;
}

export const getStrategies = () => getJson<StrategiesFile>("strategies.json");
export const getSignals = (strategyId: string, tf: Timeframe) => getJson<SignalsFile>(`${strategyId}/${tf}.json`);
export const getChart = (tf: Timeframe, ticker: string) => getJson<ChartFile>(`charts/${tf}/${ticker}.json`);
export const getMarket = () => getJson<MarketFile>("market.json");
export const getHealth = () => getJson<HealthFile>("health.json");

/** Warm the cache without caring about the outcome, for hover and idle prefetching. */
export const prefetchChart = (tf: Timeframe, ticker: string) => void getChart(tf, ticker).catch(() => {});
