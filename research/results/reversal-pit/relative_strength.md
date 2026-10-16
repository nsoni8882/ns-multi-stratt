# Relative Strength (cross-sectional momentum) variant measurement

730 S&P names, 12y of daily bars, 5-bar forward horizon, alpha per ticker against buy-and-hold. Generated 2026-10-16.

**`t by date` is the number that decides this.** A ranked rule flags many names on the same morning and those names move together, so every signal from one date is averaged into one observation before the t-stat (ACCEPTANCE.md rule 7). `t indep` is the per-ticker thinning the other strategies use, shown for comparison; where the two disagree the date-collapsed one is right.

| variant | n | n dates | names | alpha | **alpha by date** | **t by date** | t indep | win % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| pit-rev-5d-bottom5 | 25,041 | 2,685 | 583 | +0.11% | **+0.07%** | **+0.84** | +3.24 | 53.3% |
| pit-rev-5d-bottom10 | 46,555 | 2,685 | 584 | +0.07% | **+0.06%** | **+0.86** | +3.85 | 53.6% |

## Sub-period split, by calendar date

Every name shares one timeline here, so the split is by date, not per ticker.

| variant | n | n dates | names | alpha | **alpha by date** | **t by date** | t indep | win % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| pit-rev-5d-bottom5 (first half) | 11,636 | 1,342 |  | +0.24% | **+0.10%** | **+0.81** | +4.92 | 54.5% |
| pit-rev-5d-bottom5 (second half) | 13,405 | 1,343 |  | +0.01% | **+0.03%** | **+0.32** | -0.36 | 52.3% |
| pit-rev-5d-bottom10 (first half) | 21,519 | 1,342 |  | +0.18% | **+0.11%** | **+0.98** | +5.12 | 54.7% |
| pit-rev-5d-bottom10 (second half) | 25,036 | 1,343 |  | -0.01% | **+0.01%** | **+0.11** | +0.24 | 52.6% |

## With the best year removed (ACCEPTANCE rule 4)

| variant | n | n dates | names | alpha | **alpha by date** | **t by date** | t indep | win % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| pit-rev-5d-bottom5 (without 2020) | 22,536 | 2,432 |  | +0.03% | **+0.03%** | **+0.41** | +0.66 | 53.1% |
| pit-rev-5d-bottom10 (without 2020) | 41,964 | 2,432 |  | +0.01% | **+0.03%** | **+0.43** | +1.17 | 53.5% |

## Per-year alpha

| variant | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pit-rev-5d-bottom5 | -1.13% | +0.33% | +0.13% | -0.59% | +0.23% | +0.92% | +0.17% | -0.48% | +0.12% | -0.01% | +0.10% | +0.47% |
| pit-rev-5d-bottom10 | -1.58% | +0.29% | +0.08% | -0.48% | +0.23% | +0.67% | +0.24% | -0.51% | +0.00% | -0.07% | +0.08% | +0.45% |

## Point-in-time coverage

730 of 1209 symbols that were ever members had prices. Share of member-days with a price, by year (the rest are names Yahoo no longer serves, mostly acquired or bankrupt, which is the bias still left in):

| year | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| coverage | 88% | 97% | 98% | 98% | 99% | 99% | 99% | 99% | 100% | 100% | 100% | 100% | 100% |

## Net of cost (5.5 bps a round trip)

| variant | alpha by date | net | 1st half net | 2nd half net |
|---|---:|---:|---:|---:|
| pit-rev-5d-bottom5 | +0.07% | +0.01% | +0.05% | -0.02% |
| pit-rev-5d-bottom10 | +0.06% | +0.01% | +0.06% | -0.05% |
