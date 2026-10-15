import type { LabFile } from "../../types";
import { deflatedBar } from "../../lib/labStats";

export function LabHero({ meta, summary }: Pick<LabFile, "meta" | "summary">) {
  const bar = deflatedBar(meta.trials_total);
  return (
    <section className="hero lab-hero">
      <div className="row title">
        <h1>Intraday Lab</h1>
        <span className="pill faint">Paper money</span>
      </div>
      <p>
        Ideas are written down first, tested on 5- and 15-minute bars with trading costs charged,
        and judged by a bar that rises with every idea tried. Only what survives goes near an order.
      </p>
      <p className="tag num lab-bar" aria-label="How hard the bar is right now">
        <strong>{summary.trials}</strong> ideas tried · <strong>{summary.rejected}</strong> rejected ·
        <strong> {summary.passed}</strong> passed the gate · the bar is now t ≥ <strong>{bar.toFixed(2)}</strong>
      </p>
    </section>
  );
}
