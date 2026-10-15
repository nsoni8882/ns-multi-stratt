import { useSearchParams } from "react-router-dom";
import { getLab } from "../api";
import { ErrorState, Loading } from "../components/Feedback";
import { EdgeCharts } from "../components/lab/EdgeCharts";
import { LabEquityChart } from "../components/lab/LabEquityChart";
import { LabHero } from "../components/lab/LabHero";
import { LabKpis } from "../components/lab/LabKpis";
import { PipelineStrip } from "../components/lab/PipelineStrip";
import { StrategyCard } from "../components/lab/StrategyCard";
import { LabRuns, PositionsTable, TradesTable } from "../components/lab/LabTables";
import { TrialLedger } from "../components/lab/TrialLedger";
import { useAsync } from "../hooks";
import { kpis, stageCounts, trialFor } from "../lib/labStats";
import type { LabStage } from "../types";

const STAGES: LabStage[] = ["proposed", "backtested", "shadow", "paper", "kept", "rejected", "retired"];

function EmptyLab() {
  return (
    <>
      <section className="hero lab-hero">
        <div className="row title"><h1>Intraday Lab</h1><span className="pill faint">Paper money</span></div>
        <p>
          The lab has not tried anything yet. Once a strategy spec has been through the gate, it
          appears here with its checklist, its trades and why it passed or failed.
        </p>
      </section>
    </>
  );
}

export function LabPage() {
  const lab = useAsync(() => getLab(), []);
  const [params, setParams] = useSearchParams();

  if (lab.loading) return <Loading what="the lab" />;
  if (lab.error) {
    // The file does not exist until the lab first publishes; that is not a fault.
    if (/\b404\b/.test(lab.error.message)) return <EmptyLab />;
    return <ErrorState error={lab.error} onRetry={lab.retry} />;
  }
  const data = lab.data;
  if (!data) return <ErrorState error={new Error("No data")} onRetry={lab.retry} />;
  if (data.strategies.length === 0) return <EmptyLab />;

  const stage = STAGES.find((s) => s === params.get("stage")) ?? null;
  const withTrades = data.strategies.filter((s) => s.equity_curve.length > 1);
  const pick = data.strategies.find((s) => s.id === params.get("s"))
    ?? withTrades.find((s) => s.stage !== "rejected") ?? withTrades[0] ?? data.strategies[0];
  const set = (key: string, value: string | null) => {
    const p = new URLSearchParams(params);
    if (value) p.set(key, value); else p.delete(key);
    setParams(p, { replace: true });
  };
  const cards = data.strategies.filter((s) => !stage || s.stage === stage);

  return (
    <>
      <LabHero meta={data.meta} summary={data.summary} />
      <PipelineStrip counts={stageCounts(data.strategies)} active={stage} onPick={(s) => set("stage", s)} />
      <LabKpis k={kpis(pick)} name={pick?.name} />
      <LabEquityChart strategy={pick} />
      <section className="panel" aria-label="Strategies">
        <h2>Strategies</h2>
        <div className="lab-cards">
          {cards.length === 0 ? <p className="muted">Nothing at this stage.</p> : cards.map((s) => (
            <StrategyCard key={s.id} s={s} trial={trialFor(data.trials, s.fingerprint)}
                          selected={s.id === pick?.id} onSelect={() => set("s", s.id)} />
          ))}
        </div>
      </section>
      <PositionsTable positions={data.positions} />
      <TradesTable trades={data.trades} strategyId={pick?.id} name={pick?.name} />
      <EdgeCharts b={pick?.breakdowns} name={pick?.name} />
      <TrialLedger trials={data.trials} />
      <LabRuns runs={data.runs} />
    </>
  );
}
