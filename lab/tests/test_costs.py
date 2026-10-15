import pytest

from lab import config, costs


def test_costs_bite_on_both_sides():
    c = config.COST_BPS_PER_SIDE["large"] * 1e-4
    assert costs.net_return(100.0, 100.0, "large") == pytest.approx((1 - c) / (1 + c) - 1)


def test_stress_multiplier_scales_the_cost():
    assert costs.net_return(100, 101, "mega", mult=2) < costs.net_return(100, 101, "mega")


def test_tiers_by_rank():
    assert costs.tier_for(0) == "mega" and costs.tier_for(config.MEGA_RANK) == "large"
