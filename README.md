# Multi Strategy

S&P 500 signal screener: two strategies on the Daily and 4H charts, hosted on GitHub Pages.

Live site: https://nsoni8882.github.io/ns-multi-stratt/

Not financial advice. Data from Yahoo Finance, may be delayed or inaccurate.

## How it works

A scheduled GitHub Actions workflow (after each 4H close and the daily close, aware of weekends, NYSE holidays and early closes) runs the Python scanner in `scanner/`, writes JSON into `web/public/data/`, builds the Vite site in `web/`, and deploys it to Pages. Every signal is also recorded in `signals.db` on the `data` branch for later validation.

## Develop

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q                      # scanner + research tests (RUN_NETWORK=1 adds a live Yahoo smoke test)
.venv/bin/python -m scanner.run --out web/public/data --db /tmp/signals.db   # real scan, a few minutes
cd web && npm ci && npm test && npm run dev        # site at http://localhost:5173/ns-multi-stratt/
```

Add a strategy: create a module in `scanner/strategies/`, register it in `scanner/strategies/__init__.py`. It needs `id`, `name`, `description`, `min_bars`, `chart`, `evaluate(df)`, plus `params` (every threshold that can change which bars fire — it is fingerprinted into `strategies.json`) and `history` (a newest-first tuple of `Release` entries, whose top entry carries that fingerprint). Both are asserted by the test suite, so a strategy without them, or a threshold change without a new history entry, fails the build. The site picks the strategy up from `strategies.json`.

## The chart

Clicking a signal opens a TradingView-style chart (Lightweight Charts v5): candles with the signal bar boxed, an RSI pane carrying that strategy's own levels, and a MACD pane. Candles default to Heikin-Ashi with a toggle for real ones — but every indicator and overlay is computed from real closes, never from the smoothed ones.

The optional SMC overlay (structure breaks, order blocks, fair value gaps, premium/discount zones) is a port of [LuxAlgo's Smart Money Concepts](https://www.tradingview.com/script/CnB3fSph-Smart-Money-Concepts-LuxAlgo/) Pine v5 indicator, used under **CC BY-NC-SA 4.0**; `web/src/lib/smc.ts` carries the attribution and documents where it deliberately diverges from the original. That licence is non-commercial and share-alike, which this personal, source-available site is — keep it that way.

## Thresholds and conviction

Every signal carries a `conviction` of `high`, `standard` or `low`, and the site ranks and styles them accordingly. The tiers come from a sweep over 165 S&P names × 12 years of daily bars plus 63 names × 2 years of 4H bars; the measured numbers and the reasoning behind each threshold are in the comments in `scanner/strategies/base.py` and the two strategy modules. In short:

- **Trend Pullback stays at RSI 40/60**, not 30/70 or 20/80. That is Cardwell's range shift (RSI holds 40–80 in an uptrend, 20–60 in a downtrend); the classic bands barely fire inside a trend — 20/80 produced 17 signals in 12 years across 165 names.
- **MACD + RSI Reversal keeps 20 as its deepest tier** and adds 25 as a standard tier. The edge is steeply monotonic in depth (+5.3% / +2.1% / +1.9% / −0.3% per 20 bars at 20 / 25 / 30 / 35), so the levels are not loosened further just to fill the page.
- **Neither strategy publishes a SELL leg.** Re-measured against a per-ticker baseline on a non-overlapping sample, Trend Pullback's short returned −2.08% over 20 bars (t = −8.14, negative in 9 of 11 years) and the Reversal short +0.05% (t = +0.09, and that from one month of 2020). Both legs are off by default (`enable_short=False`) and kept only so the measurement can be reproduced; the site shows the long side alone. The `low` conviction tier remains in `base.py` for whatever next earns it.
- **Trend Pullback needs 400 bars**, not 250: EMA200 with `adjust=False` is still seed-biased at 250 bars, which flipped the close-vs-EMA200 trend verdict on 5 of 161 names.
