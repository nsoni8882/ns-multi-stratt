"""NYSE trading calendar: when a new 4H or daily bar closes, and therefore when an update is due.

An update is due 5 minutes after each bar close: the first 4H bar (open + 4h = 13:30 ET, or the
close on an early-close day) and the final bar at the close. Weekends, holidays and early closes
come from the exchange_calendars XNYS calendar, so DST and one-off closures are handled for us.

Also the CLI used by the workflow's gate job:
    python -m scanner.market --event schedule --updated-at 2026-10-02T20:07:00+00:00
"""
import argparse
import os
import sys
from dataclasses import dataclass
from functools import lru_cache

import exchange_calendars as xc
import pandas as pd

UPDATE_DELAY = pd.Timedelta(minutes=5)
FIRST_BAR_LENGTH = pd.Timedelta(hours=4)
WINDOW_BACK = pd.Timedelta(days=14)
WINDOW_FORWARD = pd.Timedelta(days=45)


@dataclass(frozen=True)
class Session:
    date: str  # YYYY-MM-DD, the exchange's trading date
    open: pd.Timestamp  # UTC
    close: pd.Timestamp  # UTC
    early: bool


@lru_cache(maxsize=1)
def _cal():
    return xc.get_calendar("XNYS")


def _dates(start: pd.Timestamp, end: pd.Timestamp) -> "tuple[pd.Timestamp, pd.Timestamp]":
    cal = _cal()
    first = max(start.tz_convert("UTC").tz_localize(None).normalize(), cal.first_session)
    last = min(end.tz_convert("UTC").tz_localize(None).normalize(), cal.last_session)
    return first, last


def sessions(start: pd.Timestamp, end: pd.Timestamp) -> "list[Session]":
    """Trading sessions whose date falls between the UTC dates of start and end (inclusive)."""
    cal = _cal()
    first, last = _dates(start, end)
    if first > last:
        return []
    early = set(cal.early_closes)
    return [
        Session(s.strftime("%Y-%m-%d"), cal.session_open(s), cal.session_close(s), s in early)
        for s in cal.sessions_in_range(first, last)
    ]


def update_due_times(session: Session) -> "list[pd.Timestamp]":
    first_bar_close = min(session.open + FIRST_BAR_LENGTH, session.close)
    return [t + UPDATE_DELAY for t in sorted({first_bar_close, session.close})]


def _all_due(start: pd.Timestamp, end: pd.Timestamp) -> "list[pd.Timestamp]":
    return sorted(t for s in sessions(start, end) for t in update_due_times(s))


def latest_due(now: pd.Timestamp) -> "pd.Timestamp | None":
    past = [t for t in _all_due(now - pd.Timedelta(days=10), now) if t <= now]
    return past[-1] if past else None


def next_due(now: pd.Timestamp) -> "pd.Timestamp | None":
    future = [t for t in _all_due(now - pd.Timedelta(days=1), now + pd.Timedelta(days=10)) if t > now]
    return future[0] if future else None


def is_behind(now: pd.Timestamp, updated_at: pd.Timestamp) -> bool:
    """True when an update has come due since the data was last refreshed."""
    latest = latest_due(now)
    return latest is not None and updated_at < latest


def holidays(start: pd.Timestamp, end: pd.Timestamp) -> "list[dict]":
    """Weekdays in the range on which the exchange is closed, with the holiday's name."""
    cal = _cal()
    first, last = _dates(start, end)
    if first > last:
        return []
    trading = set(cal.sessions_in_range(first, last))
    names = cal.regular_holidays.holidays(first, last, return_name=True)
    return [
        {"date": d.strftime("%Y-%m-%d"), "name": str(names.get(d, "Market closed"))}
        for d in pd.bdate_range(first, last)
        if d not in trading
    ]


def market_payload(now: pd.Timestamp) -> dict:
    """What the site needs to know about the calendar (market.json)."""
    start, end = now - WINDOW_BACK, now + WINDOW_FORWARD
    return {
        "updated_at": now.isoformat(),
        "sessions": [
            {"date": s.date, "open": s.open.isoformat(), "close": s.close.isoformat(), "early": s.early}
            for s in sessions(start, end)
        ],
        "holidays": holidays(start, end),
    }


def should_run(event: str, now: pd.Timestamp, updated_at: "pd.Timestamp | None") -> "tuple[bool, str]":
    """Gate for the scan job. Pushes and manual runs always scan; scheduled runs only when due."""
    if event != "schedule":
        return True, f"{event} run"
    if updated_at is None:
        return True, "deployed data unknown"
    if is_behind(now, updated_at):
        return True, f"an update came due after {updated_at.isoformat()}"
    return False, "no update due (weekend, holiday, or already up to date)"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--updated-at", default="", help="updated_at of the currently deployed data")
    args = parser.parse_args()
    updated = pd.Timestamp(args.updated_at).tz_convert("UTC") if args.updated_at.strip() else None
    run, reason = should_run(args.event, pd.Timestamp.now(tz="UTC"), updated)
    print(f"run={'true' if run else 'false'} ({reason})")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"run={'true' if run else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
