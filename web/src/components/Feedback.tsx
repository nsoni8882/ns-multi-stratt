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
