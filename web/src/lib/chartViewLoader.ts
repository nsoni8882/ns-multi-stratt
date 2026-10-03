import type { ChartView } from "../components/ChartView";

/**
 * Loads the chart component, which carries lightweight-charts — 57KB gzip, a third of what
 * the site would otherwise ship on every page view, and useless until a chart opens.
 *
 * Deliberately not React.lazy. A Suspense boundary that shows its fallback is held there for
 * about 300ms by React's anti-flicker throttle, which is longer than fetching the chunk and
 * drawing the chart put together. Keeping the module here instead lets ChartModal ask for it
 * synchronously: once StrategyPage has warmed it, the chart renders on the first frame.
 */
type Loaded = typeof ChartView;

let loaded: Loaded | null = null;
let inFlight: Promise<void> | null = null;

/** The component if it is already here, else null. Cheap, synchronous, no side effects. */
export const chartView = (): Loaded | null => loaded;

export function loadChartView(): Promise<void> {
  inFlight ??= import("../components/ChartView").then((m) => {
    loaded = m.ChartView;
  });
  return inFlight;
}
