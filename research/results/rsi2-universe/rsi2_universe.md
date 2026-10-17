# RSI(2) across the point-in-time S&P 500

764 symbols with prices. Alpha = trade return net of 5.5 bps less the name's own drift over the hold. Decisive: t by week, on the universe excluding AMZN and AAPL.

## rsi2

- all names: 30,934 trades, 572 weeks, alpha +0.35%, **t by week +4.77**, net/trade +33 bps, win 68%
- excluding AMZN/AAPL: 30,760 trades, 572 weeks, alpha +0.36%, **t by week +4.79**, net/trade +32 bps, win 68%
- first half: 15,362 trades, 303 weeks, alpha +0.36%, **t by week +3.48**, net/trade +27 bps, win 69%
- second half: 15,398 trades, 270 weeks, alpha +0.36%, **t by week +3.31**, net/trade +38 bps, win 68%
- without 2021: 26,818 trades, 520 weeks, alpha +0.34%, **t by week +4.41**, net/trade +25 bps, win 68%
- AMZN/AAPL among names by mean net trade: {'AMZN': {'rank': 185, 'of': 576, 'net_bps': 50.13292772515518}, 'AAPL': {'rank': 215, 'of': 576, 'net_bps': 45.60109141497264}, 'median_net_bps': 29.17929272700454}

| year | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| alpha | -0.35% | +0.11% | +0.20% | -0.63% | +0.15% | -0.22% | +0.57% | -0.71% | -0.12% | +0.06% | +0.34% | +0.33% |

## ibs

- all names: 87,158 trades, 579 weeks, alpha +0.10%, **t by week +1.78**, net/trade +24 bps, win 64%
- excluding AMZN/AAPL: 86,660 trades, 579 weeks, alpha +0.10%, **t by week +1.77**, net/trade +24 bps, win 64%
- first half: 43,308 trades, 304 weeks, alpha +0.20%, **t by week +2.44**, net/trade +32 bps, win 65%
- second half: 43,352 trades, 276 weeks, alpha -0.01%, **t by week -0.12**, net/trade +16 bps, win 62%
- without 2020: 78,972 trades, 527 weeks, alpha +0.03%, **t by week +0.60**, net/trade +19 bps, win 63%
- AMZN/AAPL among names by mean net trade: {'AMZN': {'rank': 134, 'of': 579, 'net_bps': 43.10475447019974}, 'AAPL': {'rank': 93, 'of': 579, 'net_bps': 50.60495046767171}, 'median_net_bps': 19.002045472327538}

| year | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| alpha | -0.66% | +0.08% | +0.20% | -0.51% | +0.05% | +0.50% | +0.20% | -0.36% | -0.26% | -0.10% | +0.01% | +0.09% |
