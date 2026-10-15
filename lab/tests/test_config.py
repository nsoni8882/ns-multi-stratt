"""The numbers that decide a verdict cannot change without a visible history entry."""
import re

from lab import config


def test_newest_release_fingerprint_matches_live_params():
    assert config.HISTORY[0].fingerprint == config.rules_version(), (
        "lab/config.py changed without a new Release in HISTORY; add one with fingerprint="
        + config.rules_version()
    )


def test_history_is_newest_first_semver_and_plain_english():
    dates = [r.date for r in config.HISTORY]
    assert dates == sorted(dates, reverse=True)
    for r in config.HISTORY:
        assert re.fullmatch(r"\d+\.\d+\.\d+", r.version)
        assert r.summary.strip() and "_" not in r.summary


def test_fingerprint_is_stable():
    assert config.rules_version() == config.rules_version()


def test_every_gate_number_is_in_params():
    p = config.params()
    for key in ("base_t", "min_trades", "min_days", "min_years", "stress_mult", "holdout_months",
                "max_holdout_looks", "holdout_min_ratio", "min_holdout_trades",
                "cost_bps_per_side", "mega_rank", "universe_size"):
        assert key in p, key
