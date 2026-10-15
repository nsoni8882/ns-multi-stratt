import { Fragment, useMemo, useState } from "react";
import type { LabPosition, LabRun, LabTrade } from "../../types";
import { bps, px, shortDay, signedUsd, stamp, toneClass } from "../../lib/labFormat";
import { filterTrades } from "../../lib/labStats";

export function PositionsTable({ positions }: { positions: LabPosition[] }) {
  return (
    <section className="panel" aria-label="Active positions">
      <h2>Active positions</h2>
      {positions.length === 0 ? (
        <p className="muted">Nothing is open. Positions appear here once a strategy has graduated to paper trading.</p>
      ) : (
        <div className="lab-scroll"><table className="lab-table">
          <thead><tr><th>Symbol</th><th>Qty</th><th>Entry</th><th>Mark</th><th>P&L</th><th>Stop</th><th>Target</th><th>Bars</th></tr></thead>
          <tbody>{positions.map((p) => (
            <tr key={`${p.strategy}${p.symbol}`}>
              <th scope="row">{p.symbol}</th><td className="num">{p.qty}</td><td className="num">{px(p.entry_price)}</td>
              <td className="num">{px(p.mark)}</td><td className={`num ${toneClass(p.unrealised_pnl)}`}>{signedUsd(p.unrealised_pnl)}</td>
              <td className="num">{px(p.stop)}</td><td className="num">{px(p.target)}</td><td className="num">{p.bars_held}</td>
            </tr>))}
          </tbody></table></div>
      )}
    </section>
  );
}

const PAGE = 15;
type SortKey = "time" | "net";

export function TradesTable({ trades, strategyId, name }: { trades: LabTrade[]; strategyId?: string; name?: string }) {
  const [symbol, setSymbol] = useState("");
  const [reason, setReason] = useState("");
  const [sort, setSort] = useState<SortKey>("time");
  const [page, setPage] = useState(0);
  const [open, setOpen] = useState<string | null>(null);

  const pool = useMemo(() => filterTrades(trades, strategyId, { symbol: "", reason: "" }), [trades, strategyId]);
  const symbols = useMemo(() => [...new Set(pool.map((t) => t.symbol))].sort(), [pool]);
  const reasons = useMemo(() => [...new Set(pool.map((t) => t.exit_reason))].sort(), [pool]);
  const rows = useMemo(() => {
    const f = filterTrades(trades, strategyId, { symbol, reason });
    return [...f].sort((a, b) => (sort === "net" ? b.net_bps - a.net_bps : b.entry_time.localeCompare(a.entry_time)));
  }, [trades, strategyId, symbol, reason, sort]);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE));
  const shown = rows.slice(page * PAGE, page * PAGE + PAGE);
  const reset = <T,>(set: (v: T) => void) => (v: T) => { set(v); setPage(0); };

  return (
    <section className="panel" aria-label="Trade history">
      <div className="row between">
        <h2>Trade history</h2>
        <div className="tag num">{rows.length} trades{name ? ` · ${name}` : ""}</div>
      </div>
      {pool.length === 0 ? (
        <p className="muted">No trades yet for this idea. Backtested trades appear here once it has been through the gate.</p>
      ) : (
        <>
          <div className="lab-filters">
            <label>Symbol <select value={symbol} onChange={(e) => reset(setSymbol)(e.target.value)}>
              <option value="">All</option>{symbols.map((s) => <option key={s}>{s}</option>)}</select></label>
            <label>Exit <select value={reason} onChange={(e) => reset(setReason)(e.target.value)}>
              <option value="">All</option>{reasons.map((s) => <option key={s}>{s}</option>)}</select></label>
            <div className="seg" role="group" aria-label="Sort">
              <button type="button" aria-pressed={sort === "time"} onClick={() => reset(setSort)("time")}>Newest</button>
              <button type="button" aria-pressed={sort === "net"} onClick={() => reset(setSort)("net")}>Best first</button>
            </div>
          </div>
          <div className="lab-scroll"><table className="lab-table">
            <thead><tr><th>When</th><th>Symbol</th><th>Exit</th><th>Gross</th><th>Cost</th><th>Net</th></tr></thead>
            <tbody>{shown.map((t) => {
              const id = `${t.strategy}${t.entry_time}${t.symbol}`;
              return (
                <Fragment key={id}>
                  <tr className="lab-row" onClick={() => setOpen(open === id ? null : id)}>
                    <th scope="row"><button type="button" className="lab-rowbtn" aria-expanded={open === id}>{stamp(t.entry_time)}</button></th>
                    <td>{t.symbol}</td><td>{t.exit_reason}</td>
                    <td className="num">{bps(t.gross_bps)}</td><td className="num muted">{bps(-t.cost_bps)}</td>
                    <td className={`num ${toneClass(t.net_bps)}`}>{bps(t.net_bps)}</td>
                  </tr>
                  {open === id && (
                    <tr className="lab-detail"><td colSpan={6}>
                      Bought {px(t.entry_px)} on {shortDay(t.entry_time)}, sold {px(t.exit_px)} after {t.bars_held} bars
                      ({t.bars_held * 5} min) by {t.exit_reason}. Costs took {t.cost_bps.toFixed(1)} bps of the {bps(t.gross_bps)} gross.
                    </td></tr>
                  )}
                </Fragment>
              );
            })}</tbody></table></div>
          <div className="row between lab-pager">
            <button type="button" className="btn" disabled={page === 0} onClick={() => setPage(page - 1)}>Newer</button>
            <span className="tag num">Page {page + 1} of {pages}</span>
            <button type="button" className="btn" disabled={page >= pages - 1} onClick={() => setPage(page + 1)}>Older</button>
          </div>
        </>
      )}
    </section>
  );
}

export function LabRuns({ runs }: { runs: LabRun[] }) {
  return (
    <section className="panel" aria-label="Run log">
      <h2>Run log</h2>
      {runs.length === 0 ? <p className="muted">No runs yet. The paper executor writes one line here per run, trade or no trade.</p> : (
        <ul className="lab-runs">{runs.map((r) => (
          <li key={r.time + r.strategy}><span className="tag num">{stamp(r.time)}</span> {r.decision}
            {r.orders ? ` · ${r.orders} orders` : ""}{r.errors.length ? ` · ${r.errors.join("; ")}` : ""}</li>))}
        </ul>)}
    </section>
  );
}
