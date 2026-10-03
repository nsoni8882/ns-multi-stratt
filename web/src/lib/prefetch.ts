/**
 * Run `work` when the browser has nothing better to do, or shortly after if it never does.
 * Returns a cancel function. Safari only grew requestIdleCallback in 16.4, hence the fallback.
 */
export function whenIdle(work: () => void): () => void {
  const w = window as typeof window & {
    requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number;
    cancelIdleCallback?: (id: number) => void;
  };
  if (w.requestIdleCallback) {
    const id = w.requestIdleCallback(work, { timeout: 2000 });
    return () => w.cancelIdleCallback?.(id);
  }
  const id = window.setTimeout(work, 200);
  return () => window.clearTimeout(id);
}

/**
 * Whether to spend bandwidth on something nobody has asked for yet. Speculative fetching is
 * worth most on a slow connection and rudest on a metered one, so Save-Data and 2G opt out
 * and everything there loads on demand instead.
 */
export function wantsPrefetch(): boolean {
  const link = (navigator as Navigator & {
    connection?: { saveData?: boolean; effectiveType?: string };
  }).connection;
  if (!link) return true; // only Chromium reports this; elsewhere, assume it is fine
  return !link.saveData && !/2g$/.test(link.effectiveType ?? "");
}
