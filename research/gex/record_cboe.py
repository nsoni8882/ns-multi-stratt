"""Daily SPX chain snapshot from Cboe's free delayed feed, for the GEX test (ACCEPTANCE.md Rule 11).

Stdlib only; runs from GitHub Actions (`gex.yml`), because the feed refuses this Mac but answers a
runner. Contract set is fixed by the bar: next 6 expiries, strikes within 3% of spot. The file is
named by the feed's own timestamp, so a holiday re-serving the last session finds the file and skips.

    python -m research.gex.record_cboe --out DIR
"""
import argparse
import csv
import gzip
import json
import re
import sys
import urllib.request
from pathlib import Path

URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/_SPX.json"
N_EXPIRIES, WINDOW = 6, 0.03
SYMBOL = re.compile(r"^(SPXW?)(\d{6})([CP])(\d{8})$")
FIELDS = ["date", "spot", "root", "expiry", "strike", "right", "gamma", "delta", "iv", "oi", "bid", "ask", "volume"]


def select(data):
    """Rows for the fixed contract set from a Cboe payload's `data` object."""
    spot = float(data["current_price"])
    parsed = []
    for o in data["options"]:
        m = SYMBOL.match(o["option"])
        if m and abs(int(m[4]) / 1000 / spot - 1) <= WINDOW:
            parsed.append((m, o))
    expiries = sorted({m[2] for m, _ in parsed})[:N_EXPIRIES]
    return spot, [
        [m[1], "20" + m[2], int(m[4]) / 1000, m[3], o["gamma"], o["delta"], o["iv"], o["open_interest"],
         o["bid"], o["ask"], o["volume"]]
        for m, o in parsed if m[2] in expiries
    ]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.load(r)
    date = payload["timestamp"][:10]
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{date}.csv.gz"
    if path.exists():
        print(f"{path.name} already recorded (holiday or rerun); nothing to do")
        return 0
    spot, rows = select(payload["data"])
    if not rows:
        print("no contracts selected; refusing to write an empty snapshot")
        return 1
    with gzip.open(path, "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        w.writerows([date, spot, *r] for r in rows)
    full = sum(1 for r in rows if r[5] is not None and r[8] is not None)
    print(f"wrote {path.name}: spot {spot}, {len(rows)} rows, {full} with gamma and open interest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
