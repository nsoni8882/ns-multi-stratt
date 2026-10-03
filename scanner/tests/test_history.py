"""The change history shown on the site has to stay true, so it is asserted, not trusted.

The load-bearing test is `test_live_rules_match_the_newest_release_fingerprint`: it fails the
moment a threshold moves without a new history entry, which is the only thing that would let
the published history drift out of date.
"""
import re

import pytest

from scanner.strategies import STRATEGIES
from scanner.strategies.base import Release, current_version, rules_version

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
IDS = [s.id for s in STRATEGIES]


@pytest.mark.parametrize("strat", STRATEGIES, ids=IDS)
def test_live_rules_match_the_newest_release_fingerprint(strat):
    """If this fails you changed the rules: add a history entry at the top of `history`
    describing what changed for a reader of the site, with this fingerprint."""
    live = rules_version(strat.params)
    newest = strat.history[0]
    assert newest.fingerprint == live, (
        f"{strat.id} params changed: add a Release at the top of its history with "
        f"fingerprint={live!r} (newest entry is {newest.version}, "
        f"fingerprint={newest.fingerprint!r})"
    )


@pytest.mark.parametrize("strat", STRATEGIES, ids=IDS)
def test_history_is_newest_first_and_versions_are_unique(strat):
    versions = [r.version for r in strat.history]
    assert versions == sorted(versions, key=lambda v: [int(p) for p in v.split(".")], reverse=True)
    assert len(set(versions)) == len(versions)
    assert current_version(strat.history) == versions[0]


@pytest.mark.parametrize("strat", STRATEGIES, ids=IDS)
def test_every_release_is_well_formed(strat):
    assert strat.history, f"{strat.id} has no history"
    for r in strat.history:
        assert SEMVER.match(r.version), f"{strat.id} {r.version!r} is not semver"
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", r.date), f"{strat.id} {r.date!r} is not a date"
        assert r.summary.strip() and r.summary[0].isupper() and r.summary.rstrip().endswith(".")


@pytest.mark.parametrize("strat", STRATEGIES, ids=IDS)
def test_summaries_are_short_and_jargon_free(strat):
    """These render in a user-facing overlay: one or two lines, no identifiers."""
    for r in strat.history:
        assert len(r.summary) <= 320, f"{strat.id} {r.version} summary is too long for the overlay"
        assert "_" not in r.summary and "()" not in r.summary, (
            f"{strat.id} {r.version} summary reads like code, not a change note"
        )


@pytest.mark.parametrize("strat", STRATEGIES, ids=IDS)
def test_history_dates_do_not_go_backwards(strat):
    dates = [r.date for r in strat.history]
    assert dates == sorted(dates, reverse=True)


def test_oldest_release_is_the_first_version(strat=None):
    for s in STRATEGIES:
        assert s.history[-1].version.startswith("1.0."), f"{s.id} history does not reach 1.0.x"


def test_as_dict_is_what_the_site_receives_and_hides_the_fingerprint():
    r = Release("1.2.3", "2026-01-01", "Did a thing.", fingerprint="deadbeef1234")
    assert r.as_dict() == {"version": "1.2.3", "date": "2026-01-01", "summary": "Did a thing."}


def test_current_version_of_an_empty_history_is_zero():
    assert current_version(()) == "0.0.0"
