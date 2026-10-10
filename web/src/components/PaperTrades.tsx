import type { PaperEvaluation, PaperRoundTrip } from "../types";
import { Figure, pct, price, signedMoney, tone } from "./paperFormat";

const REASON: Record<string, string> = { rsi: "RSI exit", time_stop: "Time stop" };

function Stat({ label, live, format }: {
  label: string; live: number | null; format: (n: number) => string;
}) {
  return (
    <div className="stat">
      <div className="tag">{label}</div>
      <div className="n num">
        <Figure value={live} format={format} why="No closed round trips yet" />
      </div>
    </div>
  );
}

/** Closed round trips, and the live record against what the backtest said to expect.
 *
 *  No verdict is offered until trades_needed round trips exist. That bar was written before
 *  any live trade did -- see trader/ACCEPTANCE.md -- and the panel renders its absence
 *  rather than hiding the section, so the reader can see how far off a conclusion is.
 */
export function PaperTrades({ trades, evaluation }: {
  trades: PaperRoundTrip[]; evaluation: PaperEvaluation;
}) {
  // Per symbol, never averaged: AMZN backtested +150 bps a trade and AAPL +118, so a single
  // blended figure would describe neither of them.
  const expectations = Object.entries(evaluation.backtest);

  return (
    <section className="panel" aria-label="Trades">
      <div className="row between">
        <h2>Trades</h2>
        <div className="tag num">
          {evaluation.trades_closed} of {evaluation.trades_needed} round trips needed before
          this record means anything
        </div>
      </div>

      <div className="stats paper-stats">
        <Stat label="Per trade" live={evaluation.bps_per_trade}
              format={(b) => `${b >= 0 ? "+" : ""}${b.toFixed(0)} bps`} />
        <Stat label="Win rate" live={evaluation.win_rate} format={(w) => `${w.toFixed(0)}%`} />
        <Stat label="Bars held" live={evaluation.mean_bars_held} format={(b) => b.toFixed(1)} />
        <Stat label="Fill vs decision" live={evaluation.slippage_bps}
              format={(s) => `${s >= 0 ? "+" : ""}${s.toFixed(1)} bps`} />
      </div>

      {(evaluation.unpaired_buys ?? 0) + (evaluation.unpaired_sells ?? 0) > 0 && (
        <p className="warnline" role="status" aria-label="Incomplete ledger">
          {(evaluation.unpaired_buys ?? 0) + (evaluation.unpaired_sells ?? 0)} fills could not
          be paired into a round trip, so the record below is incomplete. This usually means a
          run failed partway through.
        </p>
      )}

      <p className="tag">
        What the backtest said to expect, per name:{" "}
        {expectations.map(([symbol, b], i) => (
          <span key={symbol}>
            {i > 0 ? " · " : ""}
            {symbol} {b.bps_per_trade >= 0 ? "+" : ""}{b.bps_per_trade.toFixed(1)} bps a trade,{" "}
            {b.win_rate.toFixed(0)}% winners over {b.trades} trades
          </span>
        ))}
      </p>

      {trades.length === 0 ? (
        <p className="muted">
          Nothing has closed yet. Each row here will pair an entry with the exit that ended it.
        </p>
      ) : (
        <table className="paper-table">
          <thead>
            <tr>
              <th scope="col">Symbol</th>
              <th scope="col">In</th>
              <th scope="col">Out</th>
              <th scope="col">Shares</th>
              <th scope="col">Held</th>
              <th scope="col">Why it closed</th>
              <th scope="col">P/L</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t) => (
              <tr key={`${t.symbol}-${t.entry_date}-${t.exit_date}`}>
                <td className="tk">{t.symbol}</td>
                <td className="num">
                  {price.format(t.entry_price)}
                  <span className="tag"> <Figure value={t.entry_date ? 1 : null}
                    format={() => t.entry_date as string} why="The entry date was not recorded" /></span>
                </td>
                <td className="num">
                  {price.format(t.exit_price)}
                  <span className="tag"> <Figure value={t.exit_date ? 1 : null}
                    format={() => t.exit_date as string} why="The exit date was not recorded" /></span>
                </td>
                <td className="num">
                  <Figure value={t.qty} format={(q) => `${q}`} why="The share count was not recorded" />
                </td>
                <td className="num">
                  <Figure value={t.bars_held} format={(b) => `${b}`} why="Bars held was not recorded" />
                </td>
                <td>
                  <Figure value={t.exit_reason ? 1 : null}
                          format={() => REASON[t.exit_reason as string] ?? (t.exit_reason as string)}
                          why="No exit reason was recorded" />
                </td>
                <td className={`num${tone(t.pl)}`}>
                  {signedMoney.format(t.pl)}
                  <span className="tag"> <Figure value={t.pl_pct} format={pct}
                    why="No percentage could be computed for this trade" /></span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
