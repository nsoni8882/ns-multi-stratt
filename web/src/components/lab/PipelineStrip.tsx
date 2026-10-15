import type { LabStage } from "../../types";
import { PIPELINE, SIDELINED, STAGE_LABEL } from "../../lib/labStats";

export function PipelineStrip({ counts, active, onPick }: {
  counts: Record<LabStage, number>; active: LabStage | null; onPick: (s: LabStage | null) => void;
}) {
  const chip = (s: LabStage, arrow: boolean) => (
    <li key={s} className="lab-step">
      <button type="button" className={`lab-chip stage-${s}`} aria-pressed={active === s}
              onClick={() => onPick(active === s ? null : s)}>
        <span className="lab-chip-n num">{counts[s]}</span>
        <span className="lab-chip-l">{STAGE_LABEL[s]}</span>
      </button>
      {arrow && <span className="lab-arrow" aria-hidden="true">→</span>}
    </li>
  );
  return (
    <nav className="panel lab-pipeline" aria-label="Where ideas are in the lab">
      <ol className="lab-flow">{PIPELINE.map((s, i) => chip(s, i < PIPELINE.length - 1))}</ol>
      <ol className="lab-flow lab-side">{SIDELINED.map((s) => chip(s, false))}</ol>
    </nav>
  );
}
