import type { PaperAccount } from "../types";
import { money, pct, signedMoney, tone } from "./paperFormat";

/** The account in five figures. Realised and unrealised are split because at ~13% exposure
 *  they tell different stories: one is settled, the other is still exposed to the tape. */
export function PaperBalance({ account }: { account: PaperAccount }) {
  const t = tone(account.total_pl);
  return (
    <section className="stats paper-stats" aria-label="Account balance">
      <div className="stat">
        <div className="tag">Opening balance</div>
        <div className="n num">{money.format(account.opening_balance)}</div>
      </div>
      <div className="stat">
        <div className="tag">Current equity</div>
        <div className="n num">{money.format(account.equity)}</div>
      </div>
      <div className="stat">
        <div className="tag">Total P/L</div>
        <div className={`n num${t}`}>{signedMoney.format(account.total_pl)}</div>
        <div className={`tag num${t}`}>{pct(account.total_pl_pct)}</div>
      </div>
      <div className="stat">
        <div className="tag">Realised</div>
        <div className={`n num${tone(account.realised_pl)}`}>
          {signedMoney.format(account.realised_pl)}
        </div>
        <div className="tag">Unrealised {signedMoney.format(account.unrealised_pl)}</div>
      </div>
      <div className="stat">
        <div className="tag">Capital deployed</div>
        <div className="n num">{account.deployed_pct.toFixed(1)}%</div>
        <div className="tag">{money.format(account.cash)} in cash</div>
      </div>
    </section>
  );
}
