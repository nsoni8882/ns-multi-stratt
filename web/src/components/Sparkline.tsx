export function Sparkline({ values, color }: { values: (number | null)[]; color: string }) {
  const v = values.filter((x): x is number => x !== null);
  if (v.length < 2) return <div className="spark" />;
  const lo = Math.min(...v);
  const hi = Math.max(...v);
  const pts = v.map((x, i) => `${((i * 100) / (v.length - 1)).toFixed(1)},${(34 - ((x - lo) / (hi - lo || 1)) * 32).toFixed(1)}`).join(" ");
  return (
    <svg className="spark" viewBox="0 0 100 36" preserveAspectRatio="none" aria-hidden="true">
      <polyline fill="none" stroke={color} strokeWidth="2" points={pts} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
