# Relative Strength (cross-sectional momentum) variant measurement

164 S&P names, 12y of daily bars, 20-bar forward horizon, alpha per ticker against buy-and-hold. Generated 2026-10-16.

**`t by date` is the number that decides this.** A ranked rule flags many names on the same morning and those names move together, so every signal from one date is averaged into one observation before the t-stat (ACCEPTANCE.md rule 7). `t indep` is the per-ticker thinning the other strategies use, shown for comparison; where the two disagree the date-collapsed one is right.

| variant | n | n dates | names | alpha | **alpha by date** | **t by date** | t indep | win % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| rev-21d-bottom5 | 4,694 | 2,475 | 162 | +0.78% | **+0.76%** | **+3.34** | +1.49 | 58.4% |
| rev-21d-bottom10 | 8,581 | 2,673 | 164 | +0.39% | **+0.35%** | **+2.10** | +1.08 | 56.9% |

## Sub-period split, by calendar date

Every name shares one timeline here, so the split is by date, not per ticker.

| variant | n | n dates | names | alpha | **alpha by date** | **t by date** | t indep | win % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| rev-21d-bottom5 (first half) | 2,277 | 1,237 |  | +1.76% | **+1.62%** | **+5.04** | +3.07 | 63.5% |
| rev-21d-bottom5 (second half) | 2,417 | 1,238 |  | -0.15% | **-0.09%** | **-0.28** | -0.77 | 53.5% |
| rev-21d-bottom10 (first half) | 4,184 | 1,336 |  | +1.16% | **+1.00%** | **+4.12** | +3.15 | 61.4% |
| rev-21d-bottom10 (second half) | 4,397 | 1,337 |  | -0.34% | **-0.30%** | **-1.27** | -1.45 | 52.5% |

## With the best year removed (ACCEPTANCE rule 4)

| variant | n | n dates | names | alpha | **alpha by date** | **t by date** | t indep | win % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| rev-21d-bottom5 (without 2020) | 4,214 | 2,239 |  | +0.49% | **+0.46%** | **+2.16** | +0.61 | 57.8% |
| rev-21d-bottom10 (without 2020) | 7,705 | 2,424 |  | +0.13% | **+0.15%** | **+0.98** | +0.43 | 56.4% |

## Per-year alpha

| variant | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| rev-21d-bottom5 | -13.77% | +2.25% | +1.14% | -0.04% | +1.48% | +3.31% | +1.13% | -2.05% | +1.27% | +1.03% | -0.05% | -1.03% |
| rev-21d-bottom10 | -13.32% | +1.77% | +0.96% | -0.95% | +0.96% | +2.70% | +0.76% | -2.05% | +0.42% | +0.43% | +0.03% | -0.55% |
