import type { LabStrategy, LabTrial } from "../../types";
import { gateRows, STAGE_LABEL } from "../../lib/labStats";
import { stamp } from "../../lib/labFormat";
import { Sparkline } from "../Sparkline";

const RULE_LABEL: Record<string, string> = {
  mean_bps: "Average trade", max_drawdown_pct: "Drawdown",
};

function FailureRules({ s }: { s: LabStrategy }) {
  if (!s.failure_rules?.length) return null;
  const done = s.live?.n_trades ?? 0;
  return (
    <div className="lab-rules">
      <div className="lab-sub">Retires automatically if</div>
      {s.failure_rules.map((r) => {
        const pct = Math.min(100, (done / r.after_trades) * 100);
        return (
          <div key={`${r.metric}${r.op}`} className="lab-rule">
            <span>{RULE_LABEL[r.metric] ?? r.metric} {r.op === "lt" ? "falls below" : "rises above"} {r.threshold}
              {" "}after {r.after_trades} trades</span>
            <span className="lab-meter" role="progressbar" aria-valuemin={0} aria-valuemax={r.after_trades}
                  aria-valuenow={done} aria-label={`${done} of ${r.after_trades} trades before this rule applies`}>
              <span style={{ width: `${pct}%` }} />
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function StrategyCard({ s, trial, selected, onSelect }: {
  s: LabStrategy; trial?: LabTrial; selected: boolean; onSelect: () => void;
}) {
  const rows = gateRows(s, trial);
  const values = s.equity_curve.map((p) => p.equity);
  const up = values.length > 1 && values[values.length - 1] >= values[0];
  return (
    <article className={`lab-card${selected ? " selected" : ""}`} aria-label={s.name}>
      <header>
        <div>
          <span className={`pill lab-stage stage-${s.stage}`}>{STAGE_LABEL[s.stage]}</span>
          <h3>{s.name}</h3>
          <div className="tag">{s.family.replace(/_/g, " ")} · {s.risk.stop_pct * 100}% stop · {s.risk.target_pct * 100}% target</div>
        </div>
        <Sparkline values={values} color={up ? "var(--buy)" : "var(--sell)"} />
      </header>
      <p className="lab-hyp">{s.hypothesis}</p>
      <div className="lab-sub">{trial ? "The gate" : "The gate has not run"}</div>
      <ul className="lab-gate">
        {rows.map((r) => (
          <li key={r.name} className={r.ok === null ? "na" : r.ok ? "ok" : "no"}>
            <span className="lab-glyph" aria-hidden="true">{r.ok === null ? "·" : r.ok ? "✓" : "✕"}</span>
            <span className="lab-gate-l">{r.label}
              <span className="sr-only">{r.ok === null ? " not run" : r.ok ? " passed" : " failed"}</span>
            </span>
            <span className="tag num">{r.detail}</span>
          </li>
        ))}
      </ul>
      <FailureRules s={s} />
      <details className="lab-history">
        <summary>History ({s.history.length})</summary>
        <ol>{s.history.map((h, i) => <li key={i}><strong>{STAGE_LABEL[h.stage]}</strong> · {stamp(h.when)} · {h.reason}</li>)}</ol>
      </details>
      <button type="button" className="btn" onClick={onSelect} aria-pressed={selected}>
        {selected ? "Showing above" : "Show performance"}
      </button>
    </article>
  );
}
