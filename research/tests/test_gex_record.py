from research.gex.record_cboe import select


def _opt(symbol, gamma=0.001):
    return {"option": symbol, "gamma": gamma, "delta": 0.5, "iv": 0.2, "open_interest": 10.0,
            "bid": 1.0, "ask": 1.1, "volume": 5.0}


def test_keeps_only_the_window_and_the_first_expiries():
    options = [_opt("SPXW261020C07700000"),  # in window, first expiry
               _opt("SPXW261020C09000000"),  # far outside the window
               _opt("SPX261119P07600000")]   # in window, later expiry
    spot, rows = select({"current_price": 7700, "options": options})
    assert spot == 7700
    assert [r[:4] for r in rows] == [["SPXW", "20261020", 7700.0, "C"], ["SPX", "20261119", 7600.0, "P"]]


def test_the_expiry_cap_counts_distinct_dates_not_contracts():
    options = [_opt(f"SPXW2610{d:02d}C07700000") for d in range(20, 30)]
    _, rows = select({"current_price": 7700, "options": options})
    assert len({r[1] for r in rows}) == 6


def test_non_spx_symbols_are_ignored():
    _, rows = select({"current_price": 7700, "options": [_opt("VIX261020C00020000")]})
    assert rows == []
