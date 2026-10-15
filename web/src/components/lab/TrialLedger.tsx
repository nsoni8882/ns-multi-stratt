import { useState } from "react";
import type { LabTrial } from "../../types";
import { bps, ratio, stamp } from "../../lib/labFormat";

const WHY: Record<string, string> = {
  min_trades: "too few trades", min_days: "too few days", positive_expectancy: "loses money",
  deflated_t: "not significant enough", both_halves: "one half lost", drop_best_year: "one year carried it",
  cost_stress: "dies at doubled costs", holdout: "failed the sealed period",
};

export function TrialLedger({ trials }: { trials: LabTrial[] }) {
  const [q, setQ] = useState("");
  const [all, setAll] = useState(false);
  const list = [...trials].reverse().filter((t) => `${t.name} ${t.family} ${t.failed.join(" ")}`.toLowerCase().includes(q.toLowerCase()));
  const shown = all ? list : list.slice(0, 10);
  return (
    <section className="panel" aria-label="Trial ledger">
      <div className="row between">
        <h2>Every idea tried</h2>
        <div className="tag num">{trials.length} on record, none ever deleted</div>
      </div>
      <p className="muted">Each one raises the bar for the next, pass or fail. This list is the lab's memory.</p>
      <input className="lab-search" type="search" placeholder="Search by name, family or reason" value={q}
             aria-label="Search the ledger" onChange={(e) => setQ(e.target.value)} />
      {list.length === 0 ? <p className="muted">Nothing matches.</p> : (
        <ul className="lab-trials">{shown.map((t) => (
          <li key={t.fingerprint + t.when}>
            <span className={`pill ${t.verdict === "pass" ? "buy" : "sell"}`}>{t.verdict === "pass" ? "Passed" : "Rejected"}</span>
            <div>
              <div className="lab-t-name">{t.name}</div>
              <div className="tag num">{stamp(t.when)} · {t.n_trades} trades · {bps(t.mean_bps)}/day · t {ratio(t.t)} vs {ratio(t.threshold)}
                {t.failed.length ? ` · ${t.failed.map((f) => WHY[f] ?? f).join(", ")}` : ""}</div>
            </div>
          </li>))}
        </ul>)}
      {list.length > 10 && <button type="button" className="btn" onClick={() => setAll(!all)}>{all ? "Show fewer" : `Show all ${list.length}`}</button>}
    </section>
  );
}
