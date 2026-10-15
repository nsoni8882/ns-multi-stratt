import type { LabBreakdowns, LabBucket } from "../../types";
import { bps, hourLabel, shortDay } from "../../lib/labFormat";
import { hourOrder, weekdayOrder } from "../../lib/labStats";

const BW = 360;
const BH = 130;

/** Signed columns around a zero line: gains rise in green, losses fall in red. */
function Columns({ title, items }: { title: string; items: { label: string; value: number; note: string }[] }) {
  const max = Math.max(...items.map((i) => Math.abs(i.value)), 1);
  const gap = 6;
  // Capped, so a chart with three buckets is three tidy columns rather than three slabs.
  const w = Math.min(44, (BW - gap * (items.length + 1)) / Math.max(items.length, 1));
  const inset = (BW - items.length * w - gap * (items.length - 1)) / 2;
  const mid = BH / 2;
  return (
    <figure className="lab-fig">
      <figcaption>{title}</figcaption>
      <svg viewBox={`0 0 ${BW} ${BH + 18}`} role="img" aria-label={`${title}: ${items.map((i) => `${i.label} ${i.note}`).join(", ")}`}>
        <line x1={0} x2={BW} y1={mid} y2={mid} className="lab-ref" />
        {items.map((it, k) => {
          const h = (Math.abs(it.value) / max) * (mid - 6);
          const x = inset + k * (w + gap);
          return (
            <g key={it.label}>
              <rect x={x} y={it.value >= 0 ? mid - h : mid} width={w} height={Math.max(h, 1)} rx={3}
                    className={it.value >= 0 ? "lab-up" : "lab-down"}><title>{`${it.label}: ${it.note}`}</title></rect>
              <text x={x + w / 2} y={BH + 13} textAnchor="middle" className="lab-axis">{it.label}</text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}

const asItems = (b: LabBucket[], label: (k: string) => string) =>
  b.map((x) => ({ label: label(x.key), value: x.net_bps, note: `${bps(x.net_bps)} avg over ${x.trades} trades` }));

function Histogram({ h }: { h: LabBreakdowns["histogram"] }) {
  const max = Math.max(...h.map((b) => b.count), 1);
  const w = BW / h.length;
  return (
    <figure className="lab-fig">
      <figcaption>How each trade ended (net bps)</figcaption>
      <svg viewBox={`0 0 ${BW} ${BH + 18}`} role="img" aria-label="Distribution of trade returns">
        {h.map((b, i) => {
          const bh = (b.count / max) * (BH - 6);
          const positive = (b.from_bps + b.to_bps) / 2 >= 0;
          return <rect key={i} x={i * w + 1} y={BH - bh} width={w - 2} height={Math.max(bh, b.count ? 1 : 0)} rx={2}
                       className={positive ? "lab-up" : "lab-down"}><title>{`${bps(b.from_bps, 0)} to ${bps(b.to_bps, 0)}: ${b.count} trades`}</title></rect>;
        })}
        <text x={0} y={BH + 13} className="lab-axis">{bps(h[0].from_bps, 0)}</text>
        <text x={BW} y={BH + 13} textAnchor="end" className="lab-axis">{bps(h[h.length - 1].to_bps, 0)}</text>
      </svg>
    </figure>
  );
}

/** One square per trading day, weeks left to right, Monday at the top. */
function CalendarHeat({ days }: { days: LabBreakdowns["daily_pnl"] }) {
  const max = Math.max(...days.map((d) => Math.abs(d.net_bps)), 1);
  const first = new Date(`${days[0].day}T12:00:00Z`);
  const monday = new Date(first);
  monday.setUTCDate(first.getUTCDate() - ((first.getUTCDay() + 6) % 7));
  const cell = 11;
  const cells = days.map((d) => {
    const dt = new Date(`${d.day}T12:00:00Z`);
    const col = Math.floor((dt.getTime() - monday.getTime()) / (7 * 86_400_000));
    return { ...d, col, row: (dt.getUTCDay() + 6) % 7 };
  });
  const cols = Math.max(...cells.map((c) => c.col)) + 1;
  return (
    <figure className="lab-fig lab-wide">
      <figcaption>Every trading day (green: made money, red: lost it)</figcaption>
      <svg viewBox={`0 0 ${cols * (cell + 2)} ${5 * (cell + 2)}`} role="img" aria-label="Daily average return per trading day">
        {cells.map((c) => (
          <rect key={c.day} x={c.col * (cell + 2)} y={c.row * (cell + 2)} width={cell} height={cell} rx={2.5}
                className={c.net_bps >= 0 ? "lab-up" : "lab-down"}
                style={{ opacity: 0.25 + 0.75 * (Math.abs(c.net_bps) / max) }}>
            <title>{`${shortDay(c.day)}: ${bps(c.net_bps)}`}</title></rect>
        ))}
      </svg>
    </figure>
  );
}

export function EdgeCharts({ b, name }: { b?: LabBreakdowns; name?: string }) {
  const empty = !b || b.histogram.length === 0;
  return (
    <section className="panel" aria-label="Where the edge is">
      <div className="row between">
        <h2>Where the edge is</h2>
        {name && <div className="tag">{name}</div>}
      </div>
      {empty ? <p className="muted">Nothing to break down until this idea has trades.</p> : (
        <div className="lab-figs">
          <Columns title="By time of day (ET)" items={asItems(hourOrder(b.by_hour), hourLabel)} />
          <Columns title="By weekday" items={asItems(weekdayOrder(b.by_weekday), (k) => k.slice(0, 3))} />
          <Columns title="By symbol" items={asItems([...b.by_symbol].sort((x, y) => y.total_pct - x.total_pct), (k) => k)} />
          <Histogram h={b.histogram} />
          <CalendarHeat days={b.daily_pnl} />
        </div>
      )}
    </section>
  );
}
