"""Daily SPX option chain snapshot from IB Gateway, for the GEX test (ACCEPTANCE.md Rule 11).

Read-only: no orders. Run after the close with Gateway logged in:
    .venv/bin/python -m research.gex.record [port]
Writes research/gex/data/YYYY-MM-DD.csv (gitignored; copy to the data branch with `--publish`
is not built yet). The contract set is fixed by the bar: next 6 expiries, strikes within 3% of spot.
"""
import asyncio
import csv
import datetime as dt
import sys
from pathlib import Path

asyncio.set_event_loop(asyncio.new_event_loop())  # eventkit needs a loop at import time
from ib_insync import IB, Index, Option  # noqa: E402

OUT = Path(__file__).parent / "data"
N_EXPIRIES, WINDOW, BATCH = 6, 0.03, 80  # BATCH: free accounts cap concurrent market-data lines at 100
FIELDS = ["date", "spot", "expiry", "strike", "right", "gamma", "delta", "iv", "oi", "bid", "ask", "volume"]


def main(port=4001):
    ib = IB()
    ib.connect("127.0.0.1", port, clientId=12, timeout=10)
    ib.reqMarketDataType(3)
    spx = Index("SPX", "CBOE", "USD")
    ib.qualifyContracts(spx)
    spot = ib.reqTickers(spx)[0].marketPrice()
    today = dt.date.today().isoformat()
    wanted = []
    for p in ib.reqSecDefOptParams("SPX", "", "IND", spx.conId):
        if p.exchange != "SMART":
            continue
        for e in sorted(p.expirations)[:N_EXPIRIES * 3]:
            strikes = [k for k in p.strikes if abs(k / spot - 1) <= WINDOW]
            wanted += [(e, k, r, p.tradingClass) for k in strikes for r in "CP"]
    expiries = sorted({w[0] for w in wanted})[:N_EXPIRIES]
    wanted = [w for w in wanted if w[0] in expiries]
    contracts = [Option("SPX", e, k, r, "SMART", tradingClass=tc) for e, k, r, tc in wanted]
    qualified = [c for c in ib.qualifyContracts(*contracts) if c.conId]
    print(f"spot {spot:.2f}, expiries {expiries}, {len(qualified)}/{len(contracts)} contracts exist")

    rows = []
    for i in range(0, len(qualified), BATCH):
        batch = qualified[i:i + BATCH]
        ticks = [ib.reqMarketDataType(3) or ib.reqMktData(c, "101", False, False) for c in batch]
        ib.sleep(5)
        for _ in range(5):  # greeks and open interest arrive on separate ticks, some late
            late = [t for c, t in zip(batch, ticks)
                    if t.modelGreeks is None or (t.callOpenInterest if c.right == "C" else t.putOpenInterest) != (
                        t.callOpenInterest if c.right == "C" else t.putOpenInterest)]
            if not late:
                break
            ib.sleep(4)
        for c, t in zip(batch, ticks):
            g = t.modelGreeks
            oi = t.callOpenInterest if c.right == "C" else t.putOpenInterest
            rows.append([today, spot, c.lastTradeDateOrContractMonth, c.strike, c.right,
                         g and g.gamma, g and g.delta, g and g.impliedVol, oi, t.bid, t.ask, t.volume])
            ib.cancelMktData(c)
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{today}.csv"
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        w.writerows(rows)
    got = sum(1 for r in rows if r[5] is not None and r[8] == r[8])
    print(f"wrote {path}: {len(rows)} rows, {got} with gamma and open interest")
    ib.disconnect()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4001)
