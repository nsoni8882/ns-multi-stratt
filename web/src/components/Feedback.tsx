export function Loading({ what }: { what: string }) {
  return <p className="muted center" role="status">Loading {what}…</p>;
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry: () => void }) {
  return (
    <div className="errorbox" role="alert">
      <p><strong>Something went wrong.</strong> {error.message}</p>
      <button type="button" className="btn" onClick={onRetry}>Try again</button>
    </div>
  );
}

export function StaleBanner() {
  return (
    <div className="stale" role="status">
      The data looks out of date: an update is more than 3 hours overdue. The scanner may have paused.
    </div>
  );
}

/** Shown when the deploy serving this page was built from code whose test suite was failing.
 *  A scheduled scan deliberately does not stop on tests -- dependency drift must never block a
 *  data refresh -- so this is the honest way to say it rather than hiding it in health.json. */
export function FailingTestsNote({ tests }: { tests?: Record<string, string> }) {
  const failed = Object.entries(tests ?? {}).filter(([, outcome]) => outcome === "failure");
  if (failed.length === 0) return null;
  return (
    <div className="warnline" role="status">
      Heads up: this build shipped with failing tests ({failed.map(([name]) => name).join(", ")}).
      The numbers come from the same code either way — treat them with extra care.
    </div>
  );
}
