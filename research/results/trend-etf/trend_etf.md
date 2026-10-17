# Time-series trend (close > SMA 200) on 8 asset-class ETFs

2006-11-20 to 2026-10-16, equal-weight basket, 5 bps per switch.

- all: Sharpe 0.72 vs 0.64, max DD -12.3% vs -40.5%, return 6.1% vs 9.4%, beta 0.37, alpha +2.7%/yr (t +1.98)
- first_half: Sharpe 0.49 vs 0.44, max DD -12.3% vs -40.5%, return 4.3% vs 7.2%, beta 0.31, alpha +2.1%/yr (t +1.04)
- second_half: Sharpe 0.97 vs 0.89, max DD -10.4% vs -24.4%, return 7.9% vs 11.6%, beta 0.45, alpha +2.6%/yr (t +1.47)
- without_2008: Sharpe 0.77 vs 0.84, max DD -12.3% vs -24.4%, return 6.6% vs 11.2%, beta 0.47, alpha +1.4%/yr (t +1.10)

| ETF | trend Sharpe | hold Sharpe | trend max DD | hold max DD |
|---|---:|---:|---:|---:|
| DBC | 0.37 | 0.24 | -42.9% | -76.4% |
| EEM | 0.25 | 0.32 | -45.2% | -66.4% |
| EFA | 0.35 | 0.34 | -28.8% | -61.0% |
| GLD | 0.52 | 0.60 | -35.1% | -45.6% |
| IWM | 0.39 | 0.43 | -28.2% | -58.6% |
| QQQ | 0.80 | 0.78 | -27.1% | -53.4% |
| SPY | 0.76 | 0.63 | -21.5% | -55.2% |
| TLT | 0.04 | 0.25 | -48.4% | -48.4% |
