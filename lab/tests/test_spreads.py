from lab import spreads


def test_half_spread_is_in_bps_of_the_midpoint_and_ignores_bad_quotes():
    q = [{"bp": 99.99, "ap": 100.01}, {"bp": 0, "ap": 100}, {"bp": 100, "ap": 99},
         {"bp": 50, "ap": 100}, {"bp": 10, "ap": None}]
    out = spreads.half_spread_bps(q)
    assert len(out) == 1 and abs(out[0] - 1.0) < 0.01  # a 2c spread on $100 is 1 bp each side


def test_stratify_takes_the_top_and_a_spread_of_the_rest():
    t = spreads.stratify([f"S{i}" for i in range(50)], mega=10, others=5)
    assert t["mega"] == [f"S{i}" for i in range(10)]
    assert len(t["large"]) == 5 and t["large"][0] == "S10" and t["large"][-1] > "S10"


def test_sample_and_summary_by_tier_and_time():
    class C:
        def quotes(self, symbol, start, end, limit=500):
            wide = 0.02 if symbol == "BIG" else 0.06  # spread in dollars on a $100 stock
            return [{"bp": 100 - wide / 2, "ap": 100 + wide / 2}] * 3
    rows = spreads.sample(C(), {"mega": ["BIG"], "large": ["SMALL"]}, ["2026-10-14", "2026-10-15"])
    assert len(rows) == 2 * 2 * 3
    s = spreads.summarize(rows)
    assert s["by_tier"]["mega"]["median"] < s["by_tier"]["large"]["median"]
    assert list(s["by_time"]) == ["10:00", "12:30", "15:00"]
