import type { EquityPoint } from "../types";
import { money } from "./paperFormat";

const W = 720;
const H = 180;
const RIBBON = 10; // the exposure ribbon under the plot

/** Equity since inception, against the opening balance as a flat reference.
 *
 *  The ribbon below the plot is the point of this panel rather than decoration: this rule is
 *  in the market about 13% of days, so the curve is flat most of the time. Without saying
 *  which days held a position, a reader cannot tell deliberate idleness from a broken chart
 *  -- and that is the single most misread thing about a low-exposure overlay.
 */
export function PaperEquityCurve({ curve, opening }: { curve: EquityPoint[]; opening: number }) {
  if (curve.length === 0) {
    return (
      <section className="panel" aria-label="Equity curve">
        <h2>Equity</h2>
        <p className="muted">
          No history yet. The curve starts once the account has been through a trading session.
        </p>
      </section>
    );
  }

  const values = [...curve.map((p) => p.equity), opening];
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const pad = (hi - lo) * 0.12 || Math.max(opening * 0.002, 1);
  const top = hi + pad;
  const bottom = lo - pad;
  const x = (i: number) => (curve.length === 1 ? W / 2 : (i / (curve.length - 1)) * W);
  const y = (v: number) => H - ((v - bottom) / (top - bottom)) * H;

  const line = curve.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.equity).toFixed(1)}`).join(" ");
  const band = (i: number) => {
    const half = curve.length === 1 ? W / 2 : W / (curve.length - 1) / 2;
    return { x: Math.max(0, x(i) - half), width: Math.min(W, half * 2) };
  };
  const last = curve[curve.length - 1];
  const held = curve.filter((p) => p.in_position).length;

  return (
    <section className="panel" aria-label="Equity curve">
      <div className="row between">
        <h2>Equity</h2>
        <div className="tag num">
          {money.format(last.equity)} · in the market {Math.round((held / curve.length) * 100)}% of days
        </div>
      </div>
      <svg className="paper-curve" viewBox={`0 0 ${W} ${H + RIBBON + 6}`} role="img"
           aria-label={`Account equity from ${curve[0].date} to ${last.date}, against an opening balance of ${money.format(opening)}`}>
        {/* Days a position was open, behind the line. */}
        {curve.map((p, i) => p.in_position && (
          <rect key={p.date} x={band(i).x} y={0} width={band(i).width} height={H}
                className="paper-held" />
        ))}
        <line x1={0} x2={W} y1={y(opening)} y2={y(opening)} className="paper-opening" />
        <path d={line} className="paper-line" />
        {/* The exposure ribbon: solid where capital was at work, hollow where it idled. */}
        <rect x={0} y={H + 4} width={W} height={RIBBON} className="paper-ribbon-bg" />
        {curve.map((p, i) => p.in_position && (
          <rect key={`r-${p.date}`} x={band(i).x} y={H + 4} width={band(i).width}
                height={RIBBON} className="paper-ribbon-on" />
        ))}
      </svg>
      <p className="tag">
        The flat stretches are the strategy waiting, not a gap in the data. The shaded days are
        the ones it held something; the line below them is the same thing in one strip.
      </p>
    </section>
  );
}
