import { Link, useLocation } from "react-router-dom";
import { ErrorState, Loading } from "../components/Feedback";
import { SignalPill } from "../components/SignalPill";
import { useTimeframe } from "../hooks";
import { useStrategies } from "../strategiesContext";

export function Home() {
  const { data, error, loading, retry } = useStrategies();
  const [tf] = useTimeframe();
  const { search } = useLocation();

  if (loading) return <Loading what="strategies" />;
  if (error || !data) return <ErrorState error={error ?? new Error("No data")} onRetry={retry} />;

  const totals = data.strategies.reduce(
    (a, s) => ({ buy: a.buy + s.timeframes[tf].buy, sell: a.sell + s.timeframes[tf].sell }),
    { buy: 0, sell: 0 },
  );

  return (
    <>
      <section className="hero">
        <h1>What's moving today</h1>
        <p>
          Strategy scans across every S&amp;P 500 stock, refreshed after each 4H and daily close.
        </p>
      </section>
      <div className="stats">
        <div className="stat"><div className="tag">Buy signals</div><div className="n num buy-text">{totals.buy}</div></div>
        <div className="stat"><div className="tag">Sell signals</div><div className="n num sell-text">{totals.sell}</div></div>
        <div className="stat"><div className="tag">Timeframe</div><div className="n">{tf === "1d" ? "Daily" : "4 hour"}</div></div>
      </div>
      <div className="big">
        {data.strategies.map((s, i) => (
          <article key={s.id} className={`bigcard ${i % 2 ? "two" : "one"}`}>
            <h2>{s.name}</h2>
            <p className="muted">{s.description}</p>
            <div className="row">
              <span className="count-pill"><SignalPill side="BUY" /> {s.timeframes[tf].buy}</span>
              <span className="count-pill"><SignalPill side="SELL" /> {s.timeframes[tf].sell}</span>
            </div>
            <Link className="link" to={{ pathname: `/strategy/${s.id}`, search }}>See the stocks →</Link>
          </article>
        ))}
      </div>
    </>
  );
}
