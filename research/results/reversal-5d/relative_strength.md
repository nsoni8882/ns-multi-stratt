# Relative Strength (cross-sectional momentum) variant measurement

164 S&P names, 12y of daily bars, 5-bar forward horizon, alpha per ticker against buy-and-hold. Generated 2026-10-16.

**`t by date` is the number that decides this.** A ranked rule flags many names on the same morning and those names move together, so every signal from one date is averaged into one observation before the t-stat (ACCEPTANCE.md rule 7). `t indep` is the per-ticker thinning the other strategies use, shown for comparison; where the two disagree the date-collapsed one is right.

| variant | n | n dates | names | alpha | **alpha by date** | **t by date** | t indep | win % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| rev-5d-bottom5 | 9,061 | 2,706 | 164 | +0.20% | **+0.19%** | **+1.87** | +2.33 | 53.8% |
| rev-5d-bottom10 | 16,924 | 2,717 | 164 | +0.18% | **+0.18%** | **+2.32** | +3.95 | 54.4% |

## Sub-period split, by calendar date

Every name shares one timeline here, so the split is by date, not per ticker.

| variant | n | n dates | names | alpha | **alpha by date** | **t by date** | t indep | win % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| rev-5d-bottom5 (first half) | 4,245 | 1,353 |  | +0.34% | **+0.22%** | **+1.45** | +3.07 | 54.9% |
| rev-5d-bottom5 (second half) | 4,816 | 1,353 |  | +0.08% | **+0.15%** | **+1.19** | +0.32 | 52.9% |
| rev-5d-bottom10 (first half) | 8,133 | 1,358 |  | +0.28% | **+0.22%** | **+1.89** | +3.93 | 55.8% |
| rev-5d-bottom10 (second half) | 8,791 | 1,359 |  | +0.09% | **+0.14%** | **+1.37** | +1.70 | 53.0% |

## With the best year removed (ACCEPTANCE rule 4)

| variant | n | n dates | names | alpha | **alpha by date** | **t by date** | t indep | win % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| rev-5d-bottom5 (without 2020) | 8,199 | 2,455 |  | +0.08% | **+0.10%** | **+1.08** | +0.69 | 53.5% |
| rev-5d-bottom10 (without 2020) | 15,311 | 2,464 |  | +0.10% | **+0.13%** | **+1.82** | +2.39 | 54.2% |

## Per-year alpha

| variant | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| rev-5d-bottom5 | -3.22% | +0.59% | -0.09% | -0.30% | +0.27% | +1.34% | -0.14% | -0.91% | +0.63% | +0.28% | +0.17% | +0.51% |
| rev-5d-bottom10 | -2.11% | +0.48% | +0.17% | -0.51% | +0.32% | +0.98% | +0.13% | -0.59% | +0.37% | +0.12% | +0.19% | +0.46% |
