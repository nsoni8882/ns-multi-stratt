import type { PaperSignalState } from "../types";
import { Figure, price } from "./paperFormat";

const PILL: Record<string, string> = {
  Oversold: "buy", Exiting: "sell", Held: "faint", Waiting: "faint",
  "Trend gate blocked": "faint", "No data": "faint",
};

/** Why the bot did or did not act today, per symbol. The two numbers that decide it, next to
 *  the thresholds they are measured against. */
export function PaperSignalRows({ state }: { state: PaperSignalState[] }) {
  return (
    <section className="panel" aria-label="Rule state">
      <h2>What the rule sees</h2>
      <ul className="paper-rows">
        {state.map((s) => (
          <li key={s.symbol} className="paper-row">
            <span className="tk">{s.symbol}</span>
            <span className="num">
              <Figure value={s.price} format={price.format} why="No price was recorded on the last run" />
            </span>
            <span className="tag num">
              RSI(2) <Figure value={s.rsi2} format={(n) => n.toFixed(1)}
                             why="Not enough history to compute RSI(2)" />
              {" "}· buys under {s.buy_below}, sells over {s.sell_above}
            </span>
            <span className="tag num">
              200-day <Figure value={s.sma200} format={price.format}
                              why="Not enough history for a 200-day average" />
              {" "}· <Figure value={s.trend_gap_pct} format={(n) => `${n >= 0 ? "+" : ""}${n.toFixed(1)}% above`}
                             why="No 200-day average to compare against" />
            </span>
            <span className={`pill ${PILL[s.verdict] ?? "faint"}`}>{s.verdict}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
