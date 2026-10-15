import pandas as pd

from lab import universe


def dv():
    idx = pd.to_datetime(["2022-06-01", "2023-06-01", "2023-07-03"])
    return pd.DataFrame({"AAA": [9, 1, 1], "BBB": [5, 8, 8], "CCC": [1, 9, 9]}, index=idx)


def test_membership_for_a_year_is_ranked_on_the_year_before():
    m = universe.freeze(dv(), size=2)
    assert m[2023] == ["AAA", "BBB"]     # ranked on 2022
    assert m[2024] == ["CCC", "BBB"]     # ranked on 2023
    assert 2022 not in m                 # no prior year to rank on


def test_allowed_years_and_tiers():
    m = universe.freeze(dv(), size=2)
    assert universe.allowed_years(m) == {"AAA": {2023}, "BBB": {2023, 2024}, "CCC": {2024}}
    t = universe.tiers_from(m)
    assert t["CCC"] == "mega" and t["AAA"] == "large"  # tiers follow the latest year's order


def test_version_changes_when_membership_changes():
    m = universe.freeze(dv(), size=2)
    assert universe.version(m) == universe.version(dict(m))
    assert universe.version(m) != universe.version({**m, 2024: ["AAA"]})
