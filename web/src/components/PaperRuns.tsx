import type { PaperRun } from "../types";

const EXIT = { live: "live", "dry-run": "dry run" } as const;

/** The last ten runs. Collapsed, because on a normal day there is nothing to see -- but a run
 *  that landed past the cutoff or failed is worth saying out loud, so that is not collapsed. */
export function PaperRuns({ runs }: { runs: PaperRun[] }) {
  const latest = runs[0];
  const problem = latest && (latest.late || (latest.errors?.length ?? 0) > 0);
  return (
    <section className="panel" aria-label="Run log">
      {problem && (
        <div className="warnline" role="status" aria-label="Last run warning">
          The last run at {new Date(latest.at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}{" "}
          placed no orders: {latest.skip_reason ?? latest.errors?.[0]?.error}
        </div>
      )}
      <details className="paper-runs">
        <summary>Run log ({runs.length})</summary>
        {runs.length === 0 ? (
          <p className="muted">The bot has not run yet.</p>
        ) : (
          <ul>
            {runs.map((r) => (
              <li key={r.at}>
                <span className="num">{r.date}</span>{" "}
                <span className="tag">
                  {EXIT[r.mode as keyof typeof EXIT] ?? r.mode} ·{" "}
                  {r.orders === 1 ? "1 order" : `${r.orders} orders`}
                  {r.skip_reason ? ` · ${r.skip_reason}` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </details>
    </section>
  );
}
