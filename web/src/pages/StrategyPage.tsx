import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { getSignals, prefetchChart } from "../api";
import { ChartModal } from "../components/ChartModal";
import { ErrorState, Loading } from "../components/Feedback";
import { HistoryModal } from "../components/HistoryModal";
import { SignalPill } from "../components/SignalPill";
import { StockCard } from "../components/StockCard";
import { useAsync, useTimeframe } from "../hooks";
import { loadChartView } from "../lib/chartViewLoader";
import { wantsPrefetch, whenIdle } from "../lib/prefetch";
import { ALL_SECTORS, DEFAULT_FILTERS, filterSignals, sectorsOf, type Filters } from "../lib/filters";
import { signalReason } from "../lib/signalReason";
import { useStrategies } from "../strategiesContext";
import type { SignalRow } from "../types";

/** Roughly a desktop screenful. At ~21KB gzip a chart, six is about 125KB of guessing. */
const PREFETCH_CARDS = 6;

export function StrategyPage() {
  const { id = "" } = useParams();
  const [tf] = useTimeframe();
  const strategies = useStrategies();
  const signals = useAsync(() => getSignals(id, tf), [id, tf]);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [open, setOpen] = useState<SignalRow | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const close = useCallback(() => setOpen(null), []);
  const closeHistory = useCallback(() => setShowHistory(false), []);
  const warmChart = useCallback((r: SignalRow) => wantsPrefetch() && prefetchChart(tf, r.ticker), [tf]);
  // Fetch the chart code before anyone clicks, so opening the first chart is one request, not two.
  useEffect(() => (wantsPrefetch() ? whenIdle(loadChartView) : undefined), []);

  const rows = signals.data?.signals ?? [];
  const sectors = useMemo(() => sectorsOf(rows), [rows]);
  // A sector picked on one timeframe may not exist on the other; never filter by an option the user cannot see.
  const effective = useMemo(() => (sectors.includes(filters.sector) ? filters : { ...filters, sector: ALL_SECTORS }), [filters, sectors]);
  const shown = useMemo(() => filterSignals(rows, effective), [rows, effective]);
  const hasSells = useMemo(() => rows.some((r) => r.side === "SELL"), [rows]);
  // Touch has no hover, so the cards at the top of the list are fetched on idle instead.
  // Keyed by ticker rather than by the array, so re-filtering to the same top six is free.
  const warmList = useMemo(() => shown.slice(0, PREFETCH_CARDS).map((r) => r.ticker).join(" "), [shown]);
  useEffect(() => {
    if (!warmList || !wantsPrefetch()) return;
    return whenIdle(() => warmList.split(" ").forEach((ticker) => prefetchChart(tf, ticker)));
  }, [warmList, tf]);
  useEffect(() => setFilters((f) => (f.sector === ALL_SECTORS ? f : { ...f, sector: ALL_SECTORS })), [id, tf]);
  // A SELL filter left over from a list that had them would otherwise show an empty page.
  useEffect(() => {
    if (!hasSells) setFilters((f) => (f.side === "SELL" ? { ...f, side: "ALL" } : f));
  }, [hasSells]);
  const strategy = strategies.data?.strategies.find((s) => s.id === id);

  if (strategies.loading) return <Loading what="strategy" />;
  if (strategies.error) return <ErrorState error={strategies.error} onRetry={strategies.retry} />;
  if (!strategy) return <p className="muted center">Unknown strategy "{id}".</p>;

  return (
    <>
      {showHistory && (
        <HistoryModal
          strategyName={strategy.name}
          history={strategy.history ?? []}
          onClose={closeHistory}
        />
      )}
      <section className="hero">
        <div className="row title">
          <h1>{strategy.name}</h1>
          {strategy.version && (
          <button
            type="button"
            className="histbtn"
            aria-label={`Change history for ${strategy.name}, currently version ${strategy.version}`}
            title={`v${strategy.version} — view change history`}
            onClick={() => setShowHistory(true)}
          >
            {/* clock-with-arrow: "history", not "info" */}
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path d="M12 8v4l3 2" />
              <path d="M3.1 13a9 9 0 1 0 2.6-7.1" />
              <path d="M3 4v4h4" />
            </svg>
            <span className="vtag">v{strategy.version}</span>
          </button>
          )}
        </div>
        <p>{strategy.description}</p>
      </section>

      <div className="tools">
        <div className="seg" role="group" aria-label="Signal filter">
          {/* The SELL tab appears only when there are SELLs to show, so the control follows
              the data rather than a claim about the rules. Both strategies publish shorts
              again, at low conviction and under observation, so expect three tabs where a
              scan found any. */}
          {(hasSells ? (["ALL", "BUY", "SELL"] as const) : (["ALL", "BUY"] as const)).map((s) => (
            <button key={s} type="button" aria-pressed={filters.side === s} onClick={() => setFilters({ ...filters, side: s })}>
              {s === "ALL" ? "All" : s}
            </button>
          ))}
        </div>
        <input
          aria-label="Search ticker or name"
          placeholder="Search ticker or name"
          value={filters.query}
          onChange={(e) => setFilters({ ...filters, query: e.target.value })}
        />
        <select aria-label="Sector" value={effective.sector} onChange={(e) => setFilters({ ...filters, sector: e.target.value })}>
          {sectors.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {signals.loading && <Loading what="signals" />}
      {signals.error && <ErrorState error={signals.error} onRetry={signals.retry} />}
      {signals.data && (
        shown.length === 0 ? (
          <p className="muted center">
            {rows.length === 0 ? "No signals right now." : "No signals match these filters."}
            {filters !== DEFAULT_FILTERS && rows.length > 0 && (
              <> <button type="button" className="linkbtn" onClick={() => setFilters({ ...DEFAULT_FILTERS, sector: ALL_SECTORS })}>Clear filters</button></>
            )}
          </p>
        ) : (
          <div className="grid">
            {shown.map((r) => <StockCard key={`${r.ticker}-${r.side}`} row={r} onOpen={setOpen} onPrefetch={warmChart} />)}
          </div>
        )
      )}

      {open && (
        <ChartModal
          subject={open}
          tf={tf}
          strategyId={strategy.id}
          config={strategy.chart}
          pill={<SignalPill side={open.side} conviction={open.conviction} />}
          note={signalReason(strategy.id, open)}
          onClose={close}
        />
      )}
    </>
  );
}
