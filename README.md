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
