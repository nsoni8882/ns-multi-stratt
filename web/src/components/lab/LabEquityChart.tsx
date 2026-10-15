import { useState } from "react";
import type { LabStrategy } from "../../types";
import { shortDay, signedPct, usd } from "../../lib/labFormat";
import { START_EQUITY } from "../../lib/labStats";

const W = 720;
const H = 200;
const DD = 54;

/** Equity with the drawdown beneath it. Hand-drawn SVG: the series is a point per trading day,
 *  so it needs no charting library and does not touch the measured chart load path. */
export function LabEquityChart({ strategy }: { strategy?: LabStrategy }) {
  const [hover, setHover] = useState<number | null>(null);
  const curve = strategy?.equity_curve ?? [];
  if (!strategy || curve.length < 2) {
    return (
      <section className="panel" aria-label="Equity curve">
        <h2>Equity</h2>
        <p className="muted">{strategy ? "This idea has no trades to draw yet." : "Pick a strategy to see its curve."}</p>
      </section>
    );
  }
  const lo = Math.min(START_EQUITY, ...curve.map((p) => p.equity));
  const hi = Math.max(START_EQUITY, ...curve.map((p) => p.equity));
  const pad = (hi - lo) * 0.1 || 1;
  const x = (i: number) => (i / (curve.length - 1)) * W;
  const y = (v: number) => H - ((v - (lo - pad)) / (hi - lo + 2 * pad)) * H;
  const worst = Math.min(...curve.map((p) => p.drawdown), -0.0001);
  const yd = (v: number) => (v / worst) * DD;
  const line = curve.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.equity).toFixed(1)}`).join(" ");
  const area = `${line} L${W},${H} L0,${H} Z`;
  const dd = `M0,0 ${curve.map((p, i) => `L${x(i).toFixed(1)},${yd(p.drawdown).toFixed(1)}`).join(" ")} L${W},0 Z`;
  const last = curve[curve.length - 1];
  const at = hover ?? curve.length - 1;
  const cursor = curve[at];

  const move = (e: React.PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const f = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
    setHover(Math.round(f * (curve.length - 1)));
  };

  return (
    <section className="panel" aria-label="Equity curve">
      <div className="row between">
        <h2>Equity</h2>
        <div className="seg" role="group" aria-label="Source">
          <button type="button" aria-pressed="true">Backtest</button>
          <button type="button" aria-pressed="false" disabled title="Live results appear once this strategy trades on paper">Live</button>
        </div>
      </div>
      <p className="tag num lab-readout">
        {shortDay(cursor.t)} · <strong>{usd(cursor.equity)}</strong> · {signedPct((cursor.equity / START_EQUITY - 1) * 100)}
        {" "}· drawdown {signedPct(cursor.drawdown * 100, 1)}
      </p>
      <svg className="lab-equity" viewBox={`0 0 ${W} ${H + DD + 14}`} role="img"
           aria-label={`Backtest equity from ${shortDay(curve[0].t)} to ${shortDay(last.t)}, ending at ${usd(last.equity)}`}
           onPointerMove={move} onPointerLeave={() => setHover(null)}>
        <line x1={0} x2={W} y1={y(START_EQUITY)} y2={y(START_EQUITY)} className="lab-ref" />
        <path d={area} className="lab-area" />
        <path d={line} className="lab-line" />
        <g transform={`translate(0 ${H + 12})`}>
          <path d={dd} className="lab-dd" />
        </g>
        <line x1={x(at)} x2={x(at)} y1={0} y2={H + DD + 12} className="lab-cursor" />
        <circle cx={x(at)} cy={y(cursor.equity)} r={4} className="lab-dot" />
      </svg>
      <p className="tag">Dashed line: the {usd(START_EQUITY)} start. Beneath: how far below its own high the account sat.</p>
    </section>
  );
}
