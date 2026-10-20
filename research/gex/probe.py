"""Read-only probe: does IB Gateway return SPX gamma and open interest on this account? Places no orders.

Run with Gateway logged in and API enabled: `.venv/bin/python -m research.gex.probe [port]`.
Port 4001 is the Hermes setting (live Gateway); 4002 is the paper Gateway.
"""
import asyncio
import sys

asyncio.set_event_loop(asyncio.new_event_loop())  # eventkit needs a loop at import time
from ib_insync import IB, Index  # noqa: E402


def main(port=4001):
    ib = IB()
    ib.connect("127.0.0.1", port, clientId=11, timeout=10)
    ib.reqMarketDataType(3)  # delayed where live is not entitled, as Hermes does
    spx = Index("SPX", "CBOE", "USD")
    ib.qualifyContracts(spx)
    spot = ib.reqTickers(spx)[0]
    print("SPX last:", spot.marketPrice())
    from ib_insync import Option
    # Ask IB which contracts exist (the chain's strike list is a union across expiries).
    details = ib.reqContractDetails(Option("SPX", "", 0, "", "SMART", tradingClass="SPX"))
    cons = [d.contract for d in details]
    expiry = sorted({c.lastTradeDateOrContractMonth for c in cons})[0]
    near = sorted((c for c in cons if c.lastTradeDateOrContractMonth == expiry),
                  key=lambda c: abs(c.strike - spot.marketPrice()))[:8]
    print("expiry", expiry, "contracts that day", sum(c.lastTradeDateOrContractMonth == expiry for c in cons))
    tickers = [ib.reqMktData(c, "101", False, False) for c in near]  # 101 = open interest
    ib.sleep(6)
    for t in tickers:
        g = t.modelGreeks
        print(t.contract.strike, t.contract.right, "gamma", None if g is None else g.gamma,
              "OI call/put", t.callOpenInterest, t.putOpenInterest, "bid/ask", t.bid, t.ask)
    ib.disconnect()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4001)
