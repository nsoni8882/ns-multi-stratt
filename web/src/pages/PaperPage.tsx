import { useCallback, useState } from "react";
import { getPaperTrading } from "../api";
import { ErrorState, Loading } from "../components/Feedback";
import { HistoryModal } from "../components/HistoryModal";
import { PaperBalance } from "../components/PaperBalance";
import { PaperEquityCurve } from "../components/PaperEquityCurve";
import { PaperPositions } from "../components/PaperPositions";
import { PaperRuns } from "../components/PaperRuns";
import { PaperSignalRows } from "../components/PaperSignalRows";
import { PaperTrades } from "../components/PaperTrades";
import { useAsync } from "../hooks";
import { missedRunSince } from "../lib/market";
import { useStrategies } from "../strategiesContext";

// Named after its rule, like the two screener tabs. The "Paper money" pill carries the
// fact that this is the one strategy that actually places orders.
const NAME = "RSI(2) Reversion";

export function PaperPage() {
  const paper = useAsync(() => getPaperTrading(), []);
  const { market } = useStrategies();
  const [showHistory, setShowHistory] = useState(false);
  const closeHistory = useCallback(() => setShowHistory(false), []);

  if (paper.loading) return <Loading what="the account" />;
  if (paper.error) {
    // The file does not exist until the trader's first run, and a 404 then is normal rather
    // than a fault -- saying "something went wrong" would be wrong.
    if (/\b404\b/.test(paper.error.message)) {
      return (
        <p className="muted center">
          No paper-trading data is published yet. The bot writes this after its first run,
          on a weekday at 15:25 New York time.
        </p>
      );
    }
    return <ErrorState error={paper.error} onRetry={paper.retry} />;
  }
  const data = paper.data;
  if (!data) return <ErrorState error={new Error("No data")} onRetry={paper.retry} />;

  const marked = data.as_of === "close" ? "at the close" : "intraday";
  const lastRun = data.runs[0];
  // A session that closed with no run means the bot stopped; the panels below are then not
  // current, and saying so matters more than any of them.
  const missed = missedRunSince(lastRun?.date, market, new Date());

  return (
    <>
      {showHistory && (
        <HistoryModal strategyName={NAME} history={data.history} onClose={closeHistory} />
      )}
      <section className="hero">
        <div className="row title">
          <h1>{NAME}</h1>
          <span className="pill faint">Paper money</span>
          <button
            type="button"
            className="histbtn"
            aria-label={`${NAME} change history, currently version ${data.version}`}
            title={`v${data.version} — view change history`}
            onClick={() => setShowHistory(true)}
          >
            {/* The same clock-with-arrow the strategy tabs use, so the affordance is learnt once. */}
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path d="M12 8v4l3 2" />
              <path d="M3.1 13a9 9 0 1 0 2.6-7.1" />
              <path d="M3 4v4h4" />
            </svg>
            <span className="vtag">v{data.version}</span>
          </button>
        </div>
        <p>
          Buys {data.symbols.join(" or ")} when RSI(2) falls under 10 while the price is still
          above its 200-day average, and sells when RSI(2) recovers past 65 or ten trading days
          pass. Half the account per name, no stop. Orders go in at the closing auction.
        </p>
        <p className="tag num">
          Account marked {marked} · updated{" "}
          {new Date(data.updated_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}
          {lastRun ? ` · last run ${lastRun.date}` : " · the bot has not run yet"}
        </p>
      </section>

      <PaperBalance account={data.account} />
      <PaperEquityCurve curve={data.equity_curve} opening={data.account.opening_balance} />
      <PaperPositions positions={data.positions} />
      <PaperSignalRows state={data.signal_state} asOf={data.signal_state_as_of} />
      <PaperTrades trades={data.trades} evaluation={data.evaluation} />
      <PaperRuns runs={data.runs} missedSince={missed} />
    </>
  );
}
