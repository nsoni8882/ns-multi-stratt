# Multi Strategy

S&P 500 signal screener: two strategies on the Daily and 4H charts, hosted on GitHub Pages.

Live site: https://nsoni8882.github.io/ns-multi-stratt/

Not financial advice. Data from Yahoo Finance, may be delayed or inaccurate.

## How it works

A scheduled GitHub Actions workflow (after each 4H close and the daily close, aware of weekends, NYSE holidays and early closes) runs the Python scanner in `scanner/`, writes JSON into `web/public/data/`, builds the Vite site in `web/`, and deploys it to Pages. Every signal is also recorded in `signals.db` on the `data` branch for later validation.

## Develop

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q                      # scanner tests (RUN_NETWORK=1 adds a live Yahoo smoke test)
.venv/bin/python -m scanner.run --out web/public/data --db /tmp/signals.db   # real scan, a few minutes
cd web && npm ci && npm test && npm run dev        # site at http://localhost:5173/ns-multi-stratt/
```

Add a strategy: create a module in `scanner/strategies/`, register it in `scanner/strategies/__init__.py`. The site picks it up from `strategies.json`.

## Thresholds and conviction

Every signal carries a `conviction` of `high`, `standard` or `low`, and the site ranks and styles them accordingly. The tiers come from a sweep over 165 S&P names × 12 years of daily bars plus 63 names × 2 years of 4H bars; the measured numbers and the reasoning behind each threshold are in the comments in `scanner/strategies/base.py` and the two strategy modules. In short:

- **Trend Pullback stays at RSI 40/60**, not 30/70 or 20/80. That is Cardwell's range shift (RSI holds 40–80 in an uptrend, 20–60 in a downtrend); the classic bands barely fire inside a trend — 20/80 produced 17 signals in 12 years across 165 names.
- **MACD + RSI Reversal keeps 20 as its deepest tier** and adds 25 as a standard tier. The edge is steeply monotonic in depth (+5.3% / +2.1% / +1.9% / −0.3% per 20 bars at 20 / 25 / 30 / 35), so the levels are not loosened further just to fill the page.
- **Neither strategy publishes a SELL leg.** Re-measured against a per-ticker baseline on a non-overlapping sample, Trend Pullback's short returned −2.08% over 20 bars (t = −8.14, negative in 9 of 11 years) and the Reversal short +0.05% (t = +0.09, and that from one month of 2020). Both legs are off by default (`enable_short=False`) and kept only so the measurement can be reproduced; the site shows the long side alone. The `low` conviction tier remains in `base.py` for whatever next earns it.
- **Trend Pullback needs 400 bars**, not 250: EMA200 with `adjust=False` is still seed-biased at 250 bars, which flipped the close-vs-EMA200 trend verdict on 5 of 161 names.
