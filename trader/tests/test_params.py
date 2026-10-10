"""The published history cannot drift out of date, because what would make it stale is what
breaks this test. Same contract as scanner/tests/test_history.py."""
import re

from scanner.strategies import base as scanner_base
from trader import params


def test_history_is_newest_first():
    dates = [r.date for r in params.HISTORY]
    assert dates == sorted(dates, reverse=True)


def test_every_release_is_semver_and_iso_dated():
    for r in params.HISTORY:
        assert re.fullmatch(r"\d+\.\d+\.\d+", r.version), r.version
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", r.date), r.date
        assert r.summary.strip()


def test_the_newest_release_fingerprint_matches_the_live_params():
    """Changing a threshold without adding a history entry must fail here."""
    assert params.HISTORY[0].fingerprint == params.rules_version(), (
        "params changed without a new Release entry. Add one to trader/params.py:HISTORY "
        "with fingerprint=" + params.rules_version()
    )


def test_current_version_reads_the_top_entry():
    assert params.current_version(params.HISTORY) == params.HISTORY[0].version


def test_summaries_name_no_identifiers():
    """Plain English, at the altitude a reader of the site cares about."""
    for r in params.HISTORY:
        for banned in ("RSI_LEN", "SLICE_PCT", "def ", "params.py", "_"):
            assert banned not in r.summary, f"{r.version}: {banned}"


def test_fingerprint_is_stable_across_calls():
    assert params.rules_version() == params.rules_version()
    assert len(params.rules_version()) == 12


def test_the_stdlib_fingerprint_helpers_agree_with_the_scanners():
    """trader/params.py reimplements these rather than importing them, because the scanner's
    module pulls in pandas and the live order path must not depend on it. That duplication is
    only safe while the two agree, so this is what holds them to the same contract."""
    assert params.rules_version() == scanner_base.rules_version(params.params())
    assert params.current_version(params.HISTORY) == scanner_base.current_version(params.HISTORY)
    mine = params.Release("1.2.3", "2026-01-01", "a summary", fingerprint="deadbeef")
    theirs = scanner_base.Release("1.2.3", "2026-01-01", "a summary", fingerprint="deadbeef")
    assert mine.as_dict() == theirs.as_dict()
