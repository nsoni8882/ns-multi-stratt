# Volume Breakout variant measurement

163 S&P names, 12y of daily bars (476,108 bars fetched, 407,648 of them scored once the warm-up and the trailing forward window are excluded), 20-bar forward horizon. Generated 2026-10-04.

**Do-nothing benchmark:** across those 407,648 scored bars, a random 20-bar hold returned +1.44% and was positive 57.6% of the time. Any signal's win rate has to be read against that number, not against 50%.

`mean` is the return to the *position*, so a SELL row is the short's P&L: the stock rising is a loss. `baseline` is what that position has to beat -- the ticker's own mean forward return for a BUY (12 years of drift earns no credit), cash for a SELL. `alpha` is `mean` minus `baseline`.

`n indep` thins signals so no two forward windows overlap, and `t indep` is the t-stat on that independent sample -- the naive t over all overlapping signals runs 2-3x higher and should be ignored.

| variant | leg | n | mean | baseline | alpha | win % | n indep | alpha indep | t indep |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| spike-1.5x | BUY | 54,958 | +1.41% | +1.47% | -0.06% | 57.9% | 13,718 | -0.07% | -0.89 |
| spike-1.5x | SELL | 0 | | | | | | | |
| spike-2x | BUY | 20,796 | +1.31% | +1.50% | -0.19% | 57.4% | 9,445 | -0.01% | -0.10 |
| spike-2x | SELL | 0 | | | | | | | |
| spike-3x | BUY | 5,421 | +1.13% | +1.54% | -0.41% | 57.2% | 3,809 | -0.22% | -1.46 |
| spike-3x | SELL | 0 | | | | | | | |
| spike+breakout | BUY | 3,850 | +0.77% | +1.61% | -0.84% | 55.6% | 2,611 | -0.74% | -4.56 |
| spike+breakout | SELL | 0 | | | | | | | |
| spike+uptrend | BUY | 13,300 | +1.07% | +1.57% | -0.50% | 57.0% | 6,792 | -0.35% | -3.35 |
| spike+uptrend | SELL | 0 | | | | | | | |
| spike+strong-close | BUY | 8,520 | +0.97% | +1.52% | -0.56% | 56.4% | 5,675 | -0.38% | -2.99 |
| spike+strong-close | SELL | 0 | | | | | | | |
| spike+quiet-base | BUY | 1,193 | +1.68% | +1.55% | +0.13% | 56.9% | 1,114 | +0.18% | +0.65 |
| spike+quiet-base | SELL | 0 | | | | | | | |
| spike+obv | BUY | 10,004 | +1.09% | +1.55% | -0.46% | 57.1% | 5,873 | -0.28% | -2.42 |
| spike+obv | SELL | 0 | | | | | | | |
| full | BUY | 153 | -0.30% | +1.56% | -1.86% | 53.6% | 150 | -1.61% | -2.56 |
| full | SELL | 0 | | | | | | | |
| full-no-trend | BUY | 159 | -0.40% | +1.57% | -1.97% | 52.8% | 156 | -1.73% | -2.83 |
| full-no-trend | SELL | 0 | | | | | | | |

## BUY leg by conviction tier

| variant | leg | n | mean | baseline | alpha | win % | n indep | alpha indep | t indep |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| spike-1.5x | BUY/standard | 54,958 | +1.41% | +1.47% | -0.06% | 57.9% | 13,718 | -0.07% | -0.89 |
| spike-2x | BUY/standard | 20,796 | +1.31% | +1.50% | -0.19% | 57.4% | 9,445 | -0.01% | -0.10 |
| spike-3x | BUY/standard | 5,421 | +1.13% | +1.54% | -0.41% | 57.2% | 3,809 | -0.22% | -1.46 |
| spike+breakout | BUY/standard | 3,850 | +0.77% | +1.61% | -0.84% | 55.6% | 2,611 | -0.74% | -4.56 |
| spike+uptrend | BUY/standard | 13,300 | +1.07% | +1.57% | -0.50% | 57.0% | 6,792 | -0.35% | -3.35 |
| spike+strong-close | BUY/standard | 8,520 | +0.97% | +1.52% | -0.56% | 56.4% | 5,675 | -0.38% | -2.99 |
| spike+quiet-base | BUY/standard | 1,193 | +1.68% | +1.55% | +0.13% | 56.9% | 1,114 | +0.18% | +0.65 |
| spike+obv | BUY/standard | 10,004 | +1.09% | +1.55% | -0.46% | 57.1% | 5,873 | -0.28% | -2.42 |
| full | BUY/standard | 153 | -0.30% | +1.56% | -1.86% | 53.6% | 150 | -1.61% | -2.56 |
| full-no-trend | BUY/standard | 159 | -0.40% | +1.57% | -1.97% | 52.8% | 156 | -1.73% | -2.83 |

## Sub-period check (each ticker's scored range split in half)

A cohort that only earns its alpha in one half of the sample is a period artefact.

| variant | leg | n | mean | baseline | alpha | win % | n indep | alpha indep | t indep |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| spike-1.5x (first half) | BUY | 28,058 | +1.40% | +1.48% | -0.07% | 59.6% | 6,824 | +0.01% | +0.10 |
| spike-1.5x (second half) | BUY | 26,900 | +1.43% | +1.47% | -0.04% | 56.1% | 6,925 | -0.15% | -1.35 |
| spike-1.5x (first half) | BUY/standard | 28,058 | +1.40% | +1.48% | -0.07% | 59.6% | 6,824 | +0.01% | +0.10 |
| spike-1.5x (second half) | BUY/standard | 26,900 | +1.43% | +1.47% | -0.04% | 56.1% | 6,925 | -0.15% | -1.35 |
| spike-2x (first half) | BUY | 10,609 | +1.07% | +1.50% | -0.43% | 58.2% | 4,632 | -0.02% | -0.18 |
| spike-2x (second half) | BUY | 10,187 | +1.56% | +1.49% | +0.07% | 56.6% | 4,826 | +0.02% | +0.16 |
| spike-2x (first half) | BUY/standard | 10,609 | +1.07% | +1.50% | -0.43% | 58.2% | 4,632 | -0.02% | -0.18 |
| spike-2x (second half) | BUY/standard | 10,187 | +1.56% | +1.49% | +0.07% | 56.6% | 4,826 | +0.02% | +0.16 |
| spike-3x (first half) | BUY | 2,812 | +0.69% | +1.56% | -0.87% | 56.3% | 1,901 | -0.50% | -2.31 |
| spike-3x (second half) | BUY | 2,609 | +1.60% | +1.52% | +0.09% | 58.2% | 1,908 | +0.06% | +0.29 |
| spike-3x (first half) | BUY/standard | 2,812 | +0.69% | +1.56% | -0.87% | 56.3% | 1,901 | -0.50% | -2.31 |
| spike-3x (second half) | BUY/standard | 2,609 | +1.60% | +1.52% | +0.09% | 58.2% | 1,908 | +0.06% | +0.29 |
| spike+breakout (first half) | BUY | 2,204 | +0.67% | +1.58% | -0.91% | 57.8% | 1,461 | -0.78% | -3.73 |
| spike+breakout (second half) | BUY | 1,646 | +0.91% | +1.65% | -0.74% | 52.6% | 1,150 | -0.70% | -2.71 |
| spike+breakout (first half) | BUY/standard | 2,204 | +0.67% | +1.58% | -0.91% | 57.8% | 1,461 | -0.78% | -3.73 |
| spike+breakout (second half) | BUY/standard | 1,646 | +0.91% | +1.65% | -0.74% | 52.6% | 1,150 | -0.70% | -2.71 |
| spike+uptrend (first half) | BUY | 7,366 | +1.02% | +1.56% | -0.54% | 58.7% | 3,592 | -0.35% | -2.44 |
| spike+uptrend (second half) | BUY | 5,934 | +1.14% | +1.59% | -0.45% | 54.8% | 3,210 | -0.34% | -2.19 |
| spike+uptrend (first half) | BUY/standard | 7,366 | +1.02% | +1.56% | -0.54% | 58.7% | 3,592 | -0.35% | -2.44 |
| spike+uptrend (second half) | BUY/standard | 5,934 | +1.14% | +1.59% | -0.45% | 54.8% | 3,210 | -0.34% | -2.19 |
| spike+strong-close (first half) | BUY | 4,347 | +0.62% | +1.53% | -0.91% | 57.5% | 2,810 | -0.60% | -3.31 |
| spike+strong-close (second half) | BUY | 4,173 | +1.32% | +1.51% | -0.19% | 55.2% | 2,867 | -0.16% | -0.89 |
| spike+strong-close (first half) | BUY/standard | 4,347 | +0.62% | +1.53% | -0.91% | 57.5% | 2,810 | -0.60% | -3.31 |
| spike+strong-close (second half) | BUY/standard | 4,173 | +1.32% | +1.51% | -0.19% | 55.2% | 2,867 | -0.16% | -0.89 |
| spike+quiet-base (first half) | BUY | 668 | +2.21% | +1.55% | +0.65% | 59.7% | 620 | +0.72% | +1.87 |
| spike+quiet-base (second half) | BUY | 525 | +1.01% | +1.54% | -0.53% | 53.3% | 494 | -0.51% | -1.33 |
| spike+quiet-base (first half) | BUY/standard | 668 | +2.21% | +1.55% | +0.65% | 59.7% | 620 | +0.72% | +1.87 |
| spike+quiet-base (second half) | BUY/standard | 525 | +1.01% | +1.54% | -0.53% | 53.3% | 494 | -0.51% | -1.33 |
| spike+obv (first half) | BUY | 5,251 | +1.07% | +1.56% | -0.49% | 59.6% | 2,976 | -0.27% | -1.73 |
| spike+obv (second half) | BUY | 4,753 | +1.11% | +1.55% | -0.43% | 54.3% | 2,899 | -0.28% | -1.65 |
| spike+obv (first half) | BUY/standard | 5,251 | +1.07% | +1.56% | -0.49% | 59.6% | 2,976 | -0.27% | -1.73 |
| spike+obv (second half) | BUY/standard | 4,753 | +1.11% | +1.55% | -0.43% | 54.3% | 2,899 | -0.28% | -1.65 |
| full (first half) | BUY | 90 | +0.85% | +1.57% | -0.72% | 58.9% | 88 | -0.73% | -0.98 |
| full (second half) | BUY | 63 | -1.95% | +1.54% | -3.49% | 46.0% | 62 | -2.86% | -2.64 |
| full (first half) | BUY/standard | 90 | +0.85% | +1.57% | -0.72% | 58.9% | 88 | -0.73% | -0.98 |
| full (second half) | BUY/standard | 63 | -1.95% | +1.54% | -3.49% | 46.0% | 62 | -2.86% | -2.64 |
| full-no-trend (first half) | BUY | 92 | +0.83% | +1.61% | -0.78% | 58.7% | 90 | -0.79% | -1.07 |
| full-no-trend (second half) | BUY | 67 | -2.09% | +1.51% | -3.61% | 44.8% | 66 | -3.02% | -2.94 |
| full-no-trend (first half) | BUY/standard | 92 | +0.83% | +1.61% | -0.78% | 58.7% | 90 | -0.79% | -1.07 |
| full-no-trend (second half) | BUY/standard | 67 | -2.09% | +1.51% | -3.61% | 44.8% | 66 | -3.02% | -2.94 |

## Per-year alpha by cohort

One bad quarter can carry a pooled result that a half-and-half split still hides.

| variant | cohort | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| spike-1.5x | BUY | +1.37% | +0.43% | -1.07% | +0.50% | -1.64% | +0.75% | -1.30% | +0.10% | +0.97% | -0.25% | +0.03% |
| spike-1.5x | BUY/standard | +1.37% | +0.43% | -1.07% | +0.50% | -1.64% | +0.75% | -1.30% | +0.10% | +0.97% | -0.25% | +0.03% |
| spike-2x | BUY | +1.55% | +0.35% | -1.12% | +0.14% | -3.04% | +0.32% | -1.26% | +0.13% | +1.13% | -0.05% | -0.02% |
| spike-2x | BUY/standard | +1.55% | +0.35% | -1.12% | +0.14% | -3.04% | +0.32% | -1.26% | +0.13% | +1.13% | -0.05% | -0.02% |
| spike-3x | BUY | +1.15% | -0.20% | -0.99% | -0.10% | -4.89% | +0.32% | -1.54% | +0.06% | +1.43% | -0.76% | +0.16% |
| spike-3x | BUY/standard | +1.15% | -0.20% | -0.99% | -0.10% | -4.89% | +0.32% | -1.54% | +0.06% | +1.43% | -0.76% | +0.16% |
| spike+breakout | BUY | +1.14% | -0.31% | -2.51% | -0.64% | -2.10% | -1.62% | -1.67% | -1.33% | +0.89% | -1.59% | -0.05% |
| spike+breakout | BUY/standard | +1.14% | -0.31% | -2.51% | -0.64% | -2.10% | -1.62% | -1.67% | -1.33% | +0.89% | -1.59% | -0.05% |
| spike+uptrend | BUY | +0.87% | +0.47% | -2.18% | -0.14% | -2.26% | +0.13% | -2.31% | -1.11% | +1.08% | -1.30% | -0.15% |
| spike+uptrend | BUY/standard | +0.87% | +0.47% | -2.18% | -0.14% | -2.26% | +0.13% | -2.31% | -1.11% | +1.08% | -1.30% | -0.15% |
| spike+strong-close | BUY | +1.39% | +0.12% | -1.55% | -0.31% | -4.48% | -0.50% | -1.30% | +0.05% | +1.38% | -0.55% | -0.65% |
| spike+strong-close | BUY/standard | +1.39% | +0.12% | -1.55% | -0.31% | -4.48% | -0.50% | -1.30% | +0.05% | +1.38% | -0.55% | -0.65% |
| spike+quiet-base | BUY | -0.13% | +1.69% | -2.58% | +1.14% | +3.63% | -1.56% | -1.90% | +0.23% | +0.55% | -0.52% | +0.11% |
| spike+quiet-base | BUY/standard | -0.13% | +1.69% | -2.58% | +1.14% | +3.63% | -1.56% | -1.90% | +0.23% | +0.55% | -0.52% | +0.11% |
| spike+obv | BUY | +1.16% | +0.37% | -2.39% | -0.17% | -1.46% | -0.61% | -1.92% | -0.84% | +1.14% | -1.03% | +0.07% |
| spike+obv | BUY/standard | +1.16% | +0.37% | -2.39% | -0.17% | -1.46% | -0.61% | -1.92% | -0.84% | +1.14% | -1.03% | +0.07% |
| full | BUY | -0.61% | +2.65% | -3.95% | -0.13% | -2.04% | -1.65% | -7.50% | -2.06% | -0.10% | -2.15% | -9.64% |
| full | BUY/standard | -0.61% | +2.65% | -3.95% | -0.13% | -2.04% | -1.65% | -7.50% | -2.06% | -0.10% | -2.15% | -9.64% |
| full-no-trend | BUY | -0.61% | +2.65% | -3.55% | -0.13% | -2.04% | -1.65% | -7.09% | -2.06% | -0.10% | -2.15% | -9.64% |
| full-no-trend | BUY/standard | -0.61% | +2.65% | -3.55% | -0.13% | -2.04% | -1.65% | -7.09% | -2.06% | -0.10% | -2.15% | -9.64% |
