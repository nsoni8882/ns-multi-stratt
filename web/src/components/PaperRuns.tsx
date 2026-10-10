import type { PaperRun } from "../types";

const MODE = { live: "live", "dry-run": "dry run" } as const;

function when(at: string) {
  return new Date(at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

/** The last ten runs, collapsed -- on a normal day there is nothing to see.
 *
 *  Two things are not collapsed, because a panel that looks current while the bot has
 *  stopped is worse than no panel: a run that stood down or hit an error, and a session
 *  that passed with no run at all.
 */
export function PaperRuns({ runs, missedSince }: {
  runs: PaperRun[]; missedSince?: string | null;
}) {
  const latest = runs[0];
  const errors = latest?.errors ?? [];
  const problem = latest && (latest.late || errors.length > 0);
  // Built from what happened rather than branched on one flag: a run can place an order and
  // still hit an error on the other symbol, and saying "placed no orders" there is false.
  const placed = !latest || latest.orders === 0
    ? "placed no orders"
    : `placed ${latest.orders === 1 ? "an order" : `${latest.orders} orders`}`;
  const because = latest?.late
    ? ` and stood down: ${latest.skip_reason}`
    : errors.length > 0
      ? `, but ${errors.map((e) => e.symbol ?? "one symbol").join(" and ")} was skipped: ${errors[0]?.error}`
      : latest?.skip_reason
        ? `: ${latest.skip_reason}`
        : "";

  return (
    <section className="panel" aria-label="Run log">
      {missedSince && (
        <div className="warnline" role="status" aria-label="Missed runs">
          The bot has not run since {missedSince}, and at least one trading session has closed
          since. Nothing below is current.
        </div>
      )}
      {problem && (
        <div className="warnline" role="status" aria-label="Last run warning">
          The last run at {when(latest.at)} {placed}{because}
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
                  {MODE[r.mode as keyof typeof MODE] ?? r.mode} ·{" "}
                  {r.orders === 1 ? "1 order" : `${r.orders} orders`}
                  {r.skip_reason ? ` · ${r.skip_reason}` : ""}
                  {(r.errors?.length ?? 0) > 0 ? ` · ${r.errors?.length} error(s)` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </details>
    </section>
  );
}
