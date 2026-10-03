"""Record a semantic judgment about the news behind each live signal, for later measurement.

This is a *recorder*, not a gate. It changes nothing in `scanner/`: it reads the signal lists
the scanner already published, asks TypeSafe's Jev model two questions about the recent news
for each name, and appends the answers to `research/judgments/`. Nothing here decides whether
a signal fires, is shown, or is invalidated.

The reason it exists is the one hypothesis in this repo that measurement cannot reach today.
Trend Pullback assumes an RSI dip inside an uptrend is noise; its obvious failure mode is the
dip that is actually a company falling apart. Telling those apart is a question about meaning,
not about numbers, so it is the one place a language model could add something the indicators
cannot. But the gate it implies can only be judged against `research/ACCEPTANCE.md`, and that
needs point-in-time news for ~165 names over 12 years. The versions of that corpus you can
actually obtain are edited after the fact and miss de-listed names, so backtesting against
them would manufacture an edge rather than measure one.

So the sample is built forward instead: judge today's signals today, store the answer with the
bar it refers to, and in 12-18 months there is a clean, genuinely point-in-time sample that
`measure.py` can score the usual way. Slow, but it is the only version of this experiment
whose numbers would mean anything.

Usage:
    export TYPESAFE_API_KEY=...
    .venv/bin/python -m research.news_judgment --data web/public/data
    .venv/bin/python -m research.news_judgment --dry-run   # build the state, call nothing

Judgments land in `research/judgments/<date>.jsonl` and are committed, unlike `.cache/` --
a forward sample that a fresh clone loses is not a sample.
"""
import argparse
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests
from lxml import etree

JUDGMENTS_DIR = Path(__file__).parent / "judgments"
API_URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
NEWS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
# Yahoo's RSS rejects a bare python-requests UA.
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/140 Safari/537.36"
MAX_HEADLINES = 8  # the feed returns ~20; the oldest are rarely about the bar in question
PAUSE = 1.5  # between tickers, for Yahoo rather than for TypeSafe
RETRY_PAUSE = 5.0  # after a 429, multiplied by the attempt number
TIMEOUT = 20

log = logging.getLogger("news_judgment")


# --- the questions ----------------------------------------------------------------------

# Two Nouls, asked together over the same state so they cost one request. They are separate
# questions rather than one compound one because they fail in different ways: the first is the
# hypothesis, the second is the check on whether the first was answerable at all. A feed of
# analyst-ratings roundups and "3 stocks to watch" listicles will still produce a confident
# answer to the first question, and it would be noise.
QUESTIONS = {
    "adverse_company_event": {
        "type": "noul",
        "instructions": {
            "question": (
                "Do these headlines report a specific, adverse development at this company "
                "itself that would plausibly justify the recent fall in its share price?"
            ),
            "note": (
                "Judge the company's own situation. Weakness shared by the whole market, the "
                "sector or the economy is not a company-specific event."
            ),
        },
        "criteria": {
            "true": (
                "The news describes something that went wrong at this company: cut or withdrawn "
                "guidance, a missed quarter, a regulatory or legal investigation, an accounting "
                "problem, a failed trial or product, a lost major customer or contract, an "
                "abrupt executive departure, a credit downgrade, or a similar concrete setback."
            ),
            "false": (
                "The news is routine coverage, broad market or sector commentary, price or "
                "ratings chatter, speculation, or describes a positive or neutral development. "
                "Nothing specific has gone wrong at this company."
            ),
        },
    },
    "substantive_company_news": {
        "type": "noul",
        "instructions": (
            "Do these headlines report actual developments at this company, as opposed to "
            "generic market commentary about it?"
        ),
        "criteria": {
            "true": "At least one item reports something the company did, reported or disclosed.",
            "false": (
                "Every item is price commentary, an analyst rating change, a listicle, a stock "
                "screen, or an opinion piece. Nothing happened at the company itself."
            ),
        },
    },
}


# --- news -------------------------------------------------------------------------------

@dataclass(frozen=True)
class Headline:
    title: str
    published: str  # as the feed gives it; normalising it would only lose information
    summary: str


def parse_feed(xml: bytes, limit: int = MAX_HEADLINES) -> "list[Headline]":
    """Headlines out of a Yahoo Finance RSS body, newest first as the feed orders them."""
    root = etree.fromstring(xml)
    out = []
    for item in list(root.iterfind(".//item"))[:limit]:
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        summary = " ".join((item.findtext("description") or "").split())
        out.append(Headline(title=title, published=(item.findtext("pubDate") or "").strip(),
                            summary=summary[:600]))  # long bodies add tokens, not meaning
    return out


def fetch_headlines(ticker: str, session: "requests.Session | None" = None,
                    attempts: int = 3) -> "list[Headline]":
    """Yahoo throttles this feed aggressively -- a few requests in quick succession earn a 429
    -- so back off and retry rather than dropping the name from the sample."""
    get = (session or requests).get
    for attempt in range(1, attempts + 1):
        r = get(NEWS_URL.format(ticker=ticker), headers={"User-Agent": UA}, timeout=TIMEOUT)
        if r.status_code == 429 and attempt < attempts:
            time.sleep(RETRY_PAUSE * attempt)
            continue
        r.raise_for_status()
        return parse_feed(r.content)
    return []


# --- state ------------------------------------------------------------------------------

def build_state(row: dict, strategy_id: str, timeframe: str, headlines: "list[Headline]") -> dict:
    """What the model is told. The indicator numbers are context for reading the news, not the
    thing being judged -- the whole point is to ask the one question the numbers cannot."""
    return {
        "company": {"name": row["name"], "ticker": row["ticker"], "sector": row["sector"]},
        "signal": {
            "direction": row["side"],
            "fired_at": row["fired_at"],
            "timeframe": timeframe,
            "strategy": strategy_id,
            "what_the_rules_saw": _setup_sentence(row, strategy_id),
        },
        "recent_news": [asdict(h) for h in headlines],
    }


def _setup_sentence(row: dict, strategy_id: str) -> str:
    """One line of context so the model knows which price move the news has to explain. Kept
    in step with the site's own wording in web/src/lib/signalReason.ts."""
    d = row.get("details", {})
    rsi, level = d.get("rsi"), d.get("rsi_level")
    moved = "fell then began to recover" if row["side"] == "BUY" else "rose then began to roll over"
    bits = []
    if isinstance(rsi, (int, float)):
        bits.append(f"RSI(14) is {rsi:.1f}")
    if isinstance(level, (int, float)):
        bits.append(f"back past its {level:.0f} trigger")
    detail = f" {', '.join(bits).capitalize()}." if bits else ""
    if strategy_id == "trend-pullback":
        trend = "a longer uptrend" if row["side"] == "BUY" else "a longer downtrend"
        return f"The share price {moved} inside {trend}.{detail}"
    return f"The share price {moved} sharply, and momentum has started to turn.{detail}"


# --- the call ---------------------------------------------------------------------------

class MissingKey(RuntimeError):
    pass


def api_key() -> str:
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not key:
        raise MissingKey("TYPESAFE_API_KEY is not set. Get a key from typesafe.ai, then: "
                         "export TYPESAFE_API_KEY=...")
    return key


def judge(state: dict, key: str, session: "requests.Session | None" = None) -> dict:
    """Both questions in one request: they are independent and share the same state, so they
    run in parallel and cost one round trip."""
    post = (session or requests).post
    r = post(API_URL, timeout=TIMEOUT,
             headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
             json={"model": MODEL, "state": state, "questions": QUESTIONS})
    r.raise_for_status()
    return r.json()


def to_record(row: dict, strategy_id: str, timeframe: str, headlines: "list[Headline]",
              response: dict, now: "datetime | None" = None) -> dict:
    """One line of the forward sample. `bar_time` is what joins it back to the signal, so a
    judgment can never drift onto a different bar than the one it was made about."""
    answers = response.get("answers", {})
    now = now or datetime.now(timezone.utc)
    return {
        "recorded_at": now.isoformat(timespec="seconds"),
        "strategy_id": strategy_id,
        "timeframe": timeframe,
        "ticker": row["ticker"],
        "bar_time": row["bar_time"],
        "fired_at": row["fired_at"],
        "side": row["side"],
        "conviction": row.get("conviction"),
        "invalidated": bool(row.get("invalidated")),
        "model": response.get("model"),
        "answers": {k: v.get("noul") for k, v in answers.items()},
        "headline_count": len(headlines),
        "headlines": [h.title for h in headlines],  # titles only; enough to audit a judgment
        "usage": response.get("usage"),
    }


# --- storage ----------------------------------------------------------------------------

def record_path(now: "datetime | None" = None, out_dir: "Path | None" = None) -> Path:
    now = now or datetime.now(timezone.utc)
    return (out_dir or JUDGMENTS_DIR) / f"{now:%Y-%m}.jsonl"


def already_judged(path: Path) -> "set[tuple]":
    """(strategy, timeframe, ticker, bar_time) already in the file. Re-running on the same day
    is normal -- the scan runs several times -- and a signal must not be judged twice, or the
    sample would weight long-lived signals by how often someone happened to run this."""
    if not path.exists():
        return set()
    seen = set()
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        seen.add((r["strategy_id"], r["timeframe"], r["ticker"], r["bar_time"]))
    return seen


def append(path: Path, records: "list[dict]") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        for r in records:
            fh.write(json.dumps(r, sort_keys=True) + "\n")


def load_signals(data_dir: Path) -> "list[tuple[str, str, dict]]":
    """(strategy_id, timeframe, row) for every published signal. Reads what the scanner wrote
    rather than re-scanning: a second sweep of 500 names would cost a lot and could disagree."""
    out = []
    for path in sorted(data_dir.glob("*/*.json")):
        if path.parent.name == "charts":
            continue
        payload = json.loads(path.read_text())
        for row in payload.get("signals", []):
            out.append((path.parent.name, path.stem, row))
    return out


# --- entry point ------------------------------------------------------------------------

def run(data_dir: Path, out_dir: Path, dry_run: bool = False, limit: "int | None" = None) -> int:
    signals = load_signals(data_dir)
    if limit:
        signals = signals[:limit]
    path = record_path(out_dir=out_dir)
    seen = already_judged(path)
    todo = [s for s in signals if (s[0], s[1], s[2]["ticker"], s[2]["bar_time"]) not in seen]
    log.info("%d signals published, %d already judged, %d to do", len(signals), len(seen), len(todo))
    if not todo:
        return 0

    key = None if dry_run else api_key()
    session = requests.Session()
    records, failures = [], 0
    for n, (strategy_id, timeframe, row) in enumerate(todo):
        if n:
            time.sleep(PAUSE)  # every iteration, not just the ones that reached the model
        try:
            headlines = fetch_headlines(row["ticker"], session)
        except Exception as exc:  # a dead feed for one name must not stop the sweep
            log.warning("%s: news fetch failed: %s", row["ticker"], exc)
            failures += 1
            continue
        state = build_state(row, strategy_id, timeframe, headlines)
        if dry_run:
            print(json.dumps(state, indent=1))
            continue
        try:
            response = judge(state, key, session)
        except Exception as exc:
            log.warning("%s: judgment failed: %s", row["ticker"], exc)
            failures += 1
            continue
        records.append(to_record(row, strategy_id, timeframe, headlines, response))

    if records:
        append(path, records)
        log.info("wrote %d judgments to %s", len(records), path)
    if failures:
        log.info("%d skipped", failures)
    return len(records)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--data", type=Path, default=Path("web/public/data"),
                   help="directory the scanner wrote its signal lists to")
    p.add_argument("--out", type=Path, default=JUDGMENTS_DIR)
    p.add_argument("--limit", type=int, default=None, help="only the first N signals")
    p.add_argument("--dry-run", action="store_true",
                   help="fetch news and print the state; call TypeSafe for nothing")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run(args.data, args.out, dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
