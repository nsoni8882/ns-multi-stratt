import type { PaperPosition } from "../types";
import { Figure, pct, price, signedMoney, tone } from "./paperFormat";

/** What is open right now, and how close each one is to the ten-session time stop. */
export function PaperPositions({ positions }: { positions: PaperPosition[] }) {
  if (positions.length === 0) {
    return (
      <section className="panel" aria-label="Open positions">
        <h2>Positions</h2>
        <p className="muted">
          Flat. The rule waits for RSI(2) under 10 while the price holds above its 200-day
          average, which puts it in the market about 13% of days.
        </p>
      </section>
    );
  }
  return (
    <section className="panel" aria-label="Open positions">
      <h2>Positions</h2>
      <div className="big">
        {positions.map((p) => {
          const label = p.bars_held === null
            ? "Bars held unknown"
            : `${p.bars_held} of ${p.max_hold} bars held`;
          return (
            <article key={p.symbol} className="bigcard">
              <div className="row between">
                <h3 className="tk">{p.symbol}</h3>
                <span className={`pill ${p.unrealised_pl >= 0 ? "buy" : "sell"}`}>
                  {pct(p.unrealised_pl_pct)}
                </span>
              </div>
              <dl className="paper-kv">
                <dt>Entry</dt>
                <dd className="num">
                  {price.format(p.entry_price)}
                  {p.entry_date ? ` on ${p.entry_date}` : ""}
                </dd>
                <dt>Now</dt>
                <dd className="num">{price.format(p.price)}</dd>
                <dt>Shares</dt>
                <dd className="num">{p.qty}</dd>
                <dt>Unrealised</dt>
                <dd className={`num${tone(p.unrealised_pl)}`}>
                  {signedMoney.format(p.unrealised_pl)}
                </dd>
              </dl>
              <div className="paper-meter" role="progressbar" aria-label={label}
                   aria-valuemin={0} aria-valuemax={p.max_hold}
                   aria-valuenow={p.bars_held ?? undefined}>
                <span style={{ width: `${((p.bars_held ?? 0) / p.max_hold) * 100}%` }} />
              </div>
              <div className="tag">
                <Figure value={p.bars_held} format={(n) => `${n} of ${p.max_hold} bars`}
                        why="No entry date is known for this position, so the time stop cannot be counted" />
                {p.bars_held !== null && " until the time stop sells it"}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
