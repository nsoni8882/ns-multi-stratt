import pandas as pd

from research import quality_factors as qf


def facts():
    def row(val, accn, start=None, end="2019-12-31", filed="2020-02-20"):
        r = {"val": val, "accn": accn, "form": "10-K", "end": end, "filed": filed}
        if start:
            r["start"] = start
        return r
    ann = dict(start="2019-01-01")
    us = {"Assets": {"units": {"USD": [row(1000, "A1")]}},
          "Revenues": {"units": {"USD": [row(800, "A1", **ann)]}},
          "CostOfRevenue": {"units": {"USD": [row(500, "A1", **ann)]}},
          "NetIncomeLoss": {"units": {"USD": [row(100, "A1", **ann)]}},
          "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [row(60, "A1", **ann)]}}}
    return {"facts": {"us-gaap": us}}


def test_profitability_and_accruals_come_from_the_same_10k_and_are_scaled_by_assets():
    f = qf.annual_features(facts())
    assert len(f) == 1
    assert f["profitability"].iloc[0] == 0.3 and f["accruals"].iloc[0] == 0.04
    assert f["filed"].iloc[0] == pd.Timestamp("2020-02-20")


def test_a_quarterly_duration_is_not_taken_as_a_year():
    d = facts()
    d["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]["start"] = "2019-10-01"  # three months
    f = qf.annual_features(d)
    assert f["profitability"].isna().all()
