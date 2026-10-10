from trader import params
from trader.sizing import shares_for


def test_half_the_equity_in_whole_shares():
    qty, refusal = shares_for(equity=100_000.0, price=262.43, buying_power=400_000.0, n_held=0)
    assert qty == 190  # floor(50_000 / 262.43)
    assert refusal is None


def test_sizing_ignores_margin_buying_power():
    """The account reports 4x buying power. Slices come off equity, never off that."""
    small, _ = shares_for(equity=10_000.0, price=100.0, buying_power=40_000.0, n_held=0)
    assert small == 50


def test_concurrency_cap_refuses_a_third_position():
    qty, refusal = shares_for(equity=100_000.0, price=100.0, buying_power=400_000.0,
                              n_held=params.MAX_CONCURRENT)
    assert qty == 0
    assert refusal == f"already holding {params.MAX_CONCURRENT} of {params.MAX_CONCURRENT}"


def test_slice_too_small_for_one_whole_share_is_refused():
    qty, refusal = shares_for(equity=100.0, price=262.43, buying_power=400.0, n_held=0)
    assert qty == 0
    assert "0 whole shares" in refusal


def test_insufficient_buying_power_is_refused():
    qty, refusal = shares_for(equity=100_000.0, price=100.0, buying_power=200.0, n_held=0)
    assert qty == 0
    assert "buying power" in refusal
