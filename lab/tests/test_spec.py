import math

import pytest

from lab.spec import Spec, SpecError

GOOD = {
    "name": "ORB-3", "family": "orb", "timeframe": "5Min",
    "params": {"range_bars": 3},
    "risk": {"stop_pct": 0.01, "target_pct": 0.02, "max_hold_bars": 40},
    "hypothesis": "Stocks that break the first 15 minutes high on heavy volume keep going.",
}


def test_defaults_are_filled_and_fingerprint_is_stable():
    a = Spec.from_dict(GOOD)
    assert a.params["last_entry_bar"] == 30
    b = Spec.from_dict({**GOOD, "name": "renamed", "hypothesis": "different words"})
    assert a.fingerprint() == b.fingerprint()  # name and prose do not change behaviour
    c = Spec.from_dict({**GOOD, "params": {"range_bars": 4}})
    assert a.fingerprint() != c.fingerprint()


def test_round_trips_through_dict():
    a = Spec.from_dict(GOOD)
    assert Spec.from_dict(a.to_dict()).fingerprint() == a.fingerprint()


@pytest.mark.parametrize("patch", [
    {"family": "nope"},
    {"timeframe": "1Min"},
    {"params": {"range_bars": 999}},
    {"params": {"range_bars": math.nan}},
    {"params": {"surprise": 1}},
    {"params": {"range_bars": "3"}},
    {"hypothesis": "   "},
    {"risk": {"stop_pct": 0.0, "target_pct": 0.02, "max_hold_bars": 40}},
    {"risk": {"stop_pct": 0.01, "target_pct": 0.02, "max_hold_bars": 0}},
    {"risk": {"stop_pct": 0.01, "target_pct": 0.02, "max_hold_bars": 40, "size_pct": 0.9}},
])
def test_bad_specs_are_rejected_not_crashed(patch):
    with pytest.raises(SpecError):
        Spec.from_dict({**GOOD, **patch})
