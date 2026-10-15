import { type Kpis } from "../../lib/labStats";
import { bps, pctPlain, ratio, signedPct, signedUsd, toneClass } from "../../lib/labFormat";

export function LabKpis({ k, name }: { k: Kpis; name?: string }) {
  const cells: [string, string, number | null][] = [
    ["Net P&L", signedUsd(k.netPnl), k.netPnl],
    ["Return", signedPct(k.returnPct), k.returnPct],
    ["Win rate", pctPlain(k.winRate), null],
    ["Profit factor", ratio(k.profitFactor), null],
    ["Sharpe", ratio(k.sharpe), k.sharpe],
    ["Max drawdown", signedPct(k.maxDrawdownPct, 1), k.maxDrawdownPct],
    ["Expectancy", bps(k.expectancyBps), k.expectancyBps],
  ];
  return (
    <section className="panel" aria-label="Key figures">
      <div className="row between">
        <h2>Performance</h2>
        <div className="tag">{name ? `${name} · backtest, costs charged` : "Select a strategy"}</div>
      </div>
      <div className="lab-kpis">
        {cells.map(([label, text, tone]) => (
          <div className="stat" key={label}>
            <div className="tag">{label}</div>
            <div className={`n num ${toneClass(tone)}`}>{text}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
