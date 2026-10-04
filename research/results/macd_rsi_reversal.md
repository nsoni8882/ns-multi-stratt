# MACD + RSI Reversal variant measurement

164 S&P names, 12y of daily bars (476,343 bars fetched, 448,463 of them scored once the warm-up and the trailing forward window are excluded), 20-bar forward horizon. Generated 2026-10-03.

**Do-nothing benchmark:** across those 448,463 scored bars, a random 20-bar hold returned +1.34% and was positive 57.0% of the time. Any signal's win rate has to be read against that number, not against 50%.

`mean` is the return to the *position*, so a SELL row is the short's P&L: the stock rising is a loss. `baseline` is what that position has to beat -- the ticker's own mean forward return for a BUY (12 years of drift earns no credit), cash for a SELL. `alpha` is `mean` minus `baseline`.

`n indep` thins signals so no two forward windows overlap, and `t indep` is the t-stat on that independent sample -- the naive t over all overlapping signals runs 2-3x higher and should be ignored.

| variant | leg | n | mean | baseline | alpha | win % | n indep | alpha indep | t indep |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| shipped | BUY | 427 | +3.07% | +1.29% | +1.78% | 60.2% | 332 | +1.65% | +2.73 |
| shipped | SELL | 0 | | | | | | | |
| with-shorts | BUY | 427 | +3.07% | +1.29% | +1.78% | 60.2% | 332 | +1.65% | +2.73 |
| with-shorts | SELL | 266 | -0.05% | +0.00% | -0.05% | 50.4% | 239 | +0.05% | +0.09 |
| capitulation-1.5x | BUY | 324 | +2.77% | +1.31% | +1.47% | 59.9% | 265 | +1.06% | +1.52 |
| capitulation-1.5x | SELL | 0 | | | | | | | |
| capitulation-2x | BUY | 213 | +2.52% | +1.33% | +1.19% | 60.1% | 183 | +1.19% | +1.43 |
| capitulation-2x | SELL | 0 | | | | | | | |
| trigger-rvol-1.2 | BUY | 172 | +2.07% | +1.26% | +0.81% | 54.7% | 157 | +0.59% | +0.63 |
| trigger-rvol-1.2 | SELL | 0 | | | | | | | |
| obv-above-ema | BUY | 7 | +12.54% | +1.20% | +11.34% | 71.4% | 7 | +11.34% | +2.21 |
| obv-above-ema | SELL | 0 | | | | | | | |
| obv-divergence | BUY | 55 | +1.52% | +1.18% | +0.34% | 58.2% | 54 | +0.32% | +0.30 |
| obv-divergence | SELL | 0 | | | | | | | |
| mfi-confluence | BUY | 71 | +4.23% | +1.26% | +2.97% | 63.4% | 66 | +3.12% | +2.30 |
| mfi-confluence | SELL | 0 | | | | | | | |
| capitulation+divergence | BUY | 36 | +1.08% | +1.18% | -0.10% | 58.3% | 36 | -0.10% | -0.07 |
| capitulation+divergence | SELL | 0 | | | | | | | |

## BUY leg by conviction tier

| variant | leg | n | mean | baseline | alpha | win % | n indep | alpha indep | t indep |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| shipped | BUY/high | 85 | +3.87% | +1.32% | +2.55% | 60.0% | 82 | +2.34% | +2.11 |
| shipped | BUY/standard | 342 | +2.87% | +1.29% | +1.59% | 60.2% | 292 | +1.46% | +2.23 |
| with-shorts | BUY/high | 85 | +3.87% | +1.32% | +2.55% | 60.0% | 82 | +2.34% | +2.11 |
| with-shorts | BUY/standard | 342 | +2.87% | +1.29% | +1.59% | 60.2% | 292 | +1.46% | +2.23 |
| capitulation-1.5x | BUY/high | 73 | +3.68% | +1.34% | +2.34% | 60.3% | 71 | +2.01% | +1.72 |
| capitulation-1.5x | BUY/standard | 251 | +2.51% | +1.29% | +1.21% | 59.8% | 225 | +1.15% | +1.47 |
| capitulation-2x | BUY/high | 52 | +3.41% | +1.42% | +1.98% | 61.5% | 51 | +1.88% | +1.39 |
| capitulation-2x | BUY/standard | 161 | +2.24% | +1.30% | +0.94% | 59.6% | 147 | +1.06% | +1.11 |
| trigger-rvol-1.2 | BUY/high | 42 | +1.43% | +1.27% | +0.16% | 50.0% | 42 | +0.16% | +0.11 |
| trigger-rvol-1.2 | BUY/standard | 130 | +2.28% | +1.25% | +1.02% | 56.2% | 124 | +0.90% | +0.82 |
| obv-above-ema | BUY/high | 2 | +2.25% | +0.91% | +1.34% | 50.0% | 2 | +1.34% | +0.26 |
| obv-above-ema | BUY/standard | 5 | +16.65% | +1.31% | +15.34% | 80.0% | 5 | +15.34% | +2.47 |
| obv-divergence | BUY/high | 12 | +0.95% | +1.36% | -0.41% | 58.3% | 12 | -0.41% | -0.26 |
| obv-divergence | BUY/standard | 43 | +1.68% | +1.13% | +0.55% | 58.1% | 42 | +0.52% | +0.40 |
| mfi-confluence | BUY/high | 13 | +1.88% | +1.25% | +0.63% | 46.2% | 13 | +0.63% | +0.32 |
| mfi-confluence | BUY/standard | 58 | +4.75% | +1.26% | +3.49% | 67.2% | 56 | +3.70% | +2.41 |
| capitulation+divergence | BUY/high | 9 | +0.65% | +1.50% | -0.85% | 55.6% | 9 | -0.85% | -0.46 |
| capitulation+divergence | BUY/standard | 27 | +1.22% | +1.07% | +0.15% | 59.3% | 27 | +0.15% | +0.08 |

## Sub-period check (each ticker's scored range split in half)

A cohort that only earns its alpha in one half of the sample is a period artefact.

| variant | leg | n | mean | baseline | alpha | win % | n indep | alpha indep | t indep |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| shipped (first half) | BUY | 233 | +4.44% | +1.30% | +3.14% | 63.9% | 179 | +3.15% | +3.37 |
| shipped (second half) | BUY | 194 | +1.42% | +1.28% | +0.14% | 55.7% | 153 | -0.11% | -0.15 |
| shipped (first half) | BUY/high | 50 | +5.75% | +1.28% | +4.48% | 66.0% | 49 | +4.15% | +2.71 |
| shipped (second half) | BUY/high | 35 | +1.17% | +1.39% | -0.21% | 51.4% | 33 | -0.35% | -0.24 |
| shipped (first half) | BUY/standard | 183 | +4.09% | +1.31% | +2.78% | 63.4% | 157 | +2.79% | +2.71 |
| shipped (second half) | BUY/standard | 159 | +1.48% | +1.26% | +0.22% | 56.6% | 135 | -0.09% | -0.12 |
| with-shorts (first half) | BUY | 233 | +4.44% | +1.30% | +3.14% | 63.9% | 179 | +3.15% | +3.37 |
| with-shorts (second half) | BUY | 194 | +1.42% | +1.28% | +0.14% | 55.7% | 153 | -0.11% | -0.15 |
| with-shorts (first half) | BUY/high | 50 | +5.75% | +1.28% | +4.48% | 66.0% | 49 | +4.15% | +2.71 |
| with-shorts (second half) | BUY/high | 35 | +1.17% | +1.39% | -0.21% | 51.4% | 33 | -0.35% | -0.24 |
| with-shorts (first half) | BUY/standard | 183 | +4.09% | +1.31% | +2.78% | 63.4% | 157 | +2.79% | +2.71 |
| with-shorts (second half) | BUY/standard | 159 | +1.48% | +1.26% | +0.22% | 56.6% | 135 | -0.09% | -0.12 |
| capitulation-1.5x (first half) | BUY | 177 | +4.18% | +1.30% | +2.88% | 63.8% | 141 | +2.53% | +2.31 |
| capitulation-1.5x (second half) | BUY | 147 | +1.07% | +1.32% | -0.24% | 55.1% | 124 | -0.61% | -0.78 |
| capitulation-1.5x (first half) | BUY/high | 42 | +5.63% | +1.26% | +4.37% | 64.3% | 41 | +3.98% | +2.33 |
| capitulation-1.5x (second half) | BUY/high | 31 | +1.04% | +1.46% | -0.42% | 54.8% | 30 | -0.68% | -0.50 |
| capitulation-1.5x (first half) | BUY/standard | 135 | +3.73% | +1.31% | +2.42% | 63.7% | 122 | +2.43% | +2.00 |
| capitulation-1.5x (second half) | BUY/standard | 116 | +1.08% | +1.28% | -0.20% | 55.2% | 103 | -0.37% | -0.42 |
| capitulation-2x (first half) | BUY | 118 | +3.46% | +1.33% | +2.13% | 63.6% | 100 | +2.26% | +1.78 |
| capitulation-2x (second half) | BUY | 95 | +1.35% | +1.33% | +0.03% | 55.8% | 83 | -0.10% | -0.10 |
| capitulation-2x (first half) | BUY/high | 29 | +5.44% | +1.29% | +4.15% | 69.0% | 29 | +4.15% | +2.20 |
| capitulation-2x (second half) | BUY/high | 23 | +0.84% | +1.59% | -0.75% | 52.2% | 22 | -1.12% | -0.63 |
| capitulation-2x (first half) | BUY/standard | 89 | +2.82% | +1.34% | +1.48% | 61.8% | 81 | +1.54% | +1.04 |
| capitulation-2x (second half) | BUY/standard | 72 | +1.52% | +1.24% | +0.27% | 56.9% | 66 | +0.48% | +0.41 |
| trigger-rvol-1.2 (first half) | BUY | 89 | +2.52% | +1.25% | +1.27% | 58.4% | 80 | +1.24% | +0.80 |
| trigger-rvol-1.2 (second half) | BUY | 83 | +1.59% | +1.27% | +0.32% | 50.6% | 77 | -0.09% | -0.08 |
| trigger-rvol-1.2 (first half) | BUY/high | 21 | +2.83% | +1.09% | +1.73% | 57.1% | 21 | +1.73% | +0.77 |
| trigger-rvol-1.2 (second half) | BUY/high | 21 | +0.03% | +1.44% | -1.41% | 42.9% | 21 | -1.41% | -0.74 |
| trigger-rvol-1.2 (first half) | BUY/standard | 68 | +2.42% | +1.29% | +1.13% | 58.8% | 64 | +1.06% | +0.58 |
| trigger-rvol-1.2 (second half) | BUY/standard | 62 | +2.12% | +1.21% | +0.91% | 53.2% | 60 | +0.73% | +0.62 |
| obv-above-ema (first half) | BUY | 5 | +19.04% | +1.36% | +17.69% | 100.0% | 5 | +17.69% | +3.96 |
| obv-above-ema (second half) | BUY | 2 | -3.73% | +0.80% | -4.53% | 0.0% | 2 | -4.53% | -6.48 |
| obv-above-ema (first half) | BUY/high | 1 | +7.50% | +1.00% | +6.50% | 100.0% | 1 | +6.50% | +nan |
| obv-above-ema (second half) | BUY/high | 1 | -3.00% | +0.82% | -3.83% | 0.0% | 1 | -3.83% | +nan |
| obv-above-ema (first half) | BUY/standard | 4 | +21.93% | +1.45% | +20.48% | 100.0% | 4 | +20.48% | +4.55 |
| obv-above-ema (second half) | BUY/standard | 1 | -4.46% | +0.77% | -5.23% | 0.0% | 1 | -5.23% | +nan |
| obv-divergence (first half) | BUY | 26 | +0.92% | +1.06% | -0.13% | 53.8% | 25 | -0.20% | -0.13 |
| obv-divergence (second half) | BUY | 29 | +2.06% | +1.30% | +0.76% | 62.1% | 29 | +0.76% | +0.52 |
| obv-divergence (first half) | BUY/high | 4 | +0.24% | +1.37% | -1.13% | 50.0% | 4 | -1.13% | -0.34 |
| obv-divergence (second half) | BUY/high | 8 | +1.30% | +1.36% | -0.06% | 62.5% | 8 | -0.06% | -0.03 |
| obv-divergence (first half) | BUY/standard | 22 | +1.05% | +1.00% | +0.05% | 54.5% | 21 | -0.02% | -0.01 |
| obv-divergence (second half) | BUY/standard | 21 | +2.35% | +1.28% | +1.07% | 61.9% | 21 | +1.07% | +0.56 |
| mfi-confluence (first half) | BUY | 43 | +4.88% | +1.27% | +3.61% | 62.8% | 39 | +3.84% | +1.89 |
| mfi-confluence (second half) | BUY | 28 | +3.23% | +1.24% | +1.98% | 64.3% | 27 | +2.08% | +1.31 |
| mfi-confluence (first half) | BUY/high | 8 | +2.26% | +1.02% | +1.24% | 50.0% | 8 | +1.24% | +0.49 |
| mfi-confluence (second half) | BUY/high | 5 | +1.28% | +1.62% | -0.34% | 40.0% | 5 | -0.34% | -0.10 |
| mfi-confluence (first half) | BUY/standard | 35 | +5.48% | +1.33% | +4.15% | 65.7% | 34 | +4.39% | +1.94 |
| mfi-confluence (second half) | BUY/standard | 23 | +3.65% | +1.16% | +2.49% | 69.6% | 22 | +2.63% | +1.47 |
| capitulation+divergence (first half) | BUY | 15 | +0.96% | +0.96% | -0.00% | 53.3% | 15 | -0.00% | -0.00 |
| capitulation+divergence (second half) | BUY | 21 | +1.16% | +1.33% | -0.17% | 61.9% | 21 | -0.17% | -0.09 |
| capitulation+divergence (first half) | BUY/high | 2 | -4.41% | +1.65% | -6.06% | 0.0% | 2 | -6.06% | -2.09 |
| capitulation+divergence (second half) | BUY/high | 7 | +2.10% | +1.45% | +0.64% | 71.4% | 7 | +0.64% | +0.33 |
| capitulation+divergence (first half) | BUY/standard | 13 | +1.78% | +0.86% | +0.93% | 61.5% | 13 | +0.93% | +0.35 |
| capitulation+divergence (second half) | BUY/standard | 14 | +0.70% | +1.27% | -0.57% | 57.1% | 14 | -0.57% | -0.23 |

## Per-year alpha by cohort

One bad quarter can carry a pooled result that a half-and-half split still hides.

| variant | cohort | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| shipped | BUY | -3.19% | +2.86% | -3.21% | +2.22% | +2.37% | +10.06% | +2.32% | -0.41% | +0.37% | +2.72% | -3.76% | +1.64% |
| shipped | BUY/high | -3.70% | +2.58% | -5.32% | +2.64% | -0.45% | +19.17% | -4.35% | -2.16% | +3.31% | +2.63% | -1.50% | +0.31% |
| shipped | BUY/standard | -3.09% | +2.91% | -2.39% | +2.07% | +3.08% | +7.90% | +2.87% | -0.09% | -0.71% | +2.75% | -4.28% | +1.96% |
| with-shorts | BUY | -3.19% | +2.86% | -3.21% | +2.22% | +2.37% | +10.06% | +2.32% | -0.41% | +0.37% | +2.72% | -3.76% | +1.64% |
| with-shorts | BUY/high | -3.70% | +2.58% | -5.32% | +2.64% | -0.45% | +19.17% | -4.35% | -2.16% | +3.31% | +2.63% | -1.50% | +0.31% |
| with-shorts | BUY/standard | -3.09% | +2.91% | -2.39% | +2.07% | +3.08% | +7.90% | +2.87% | -0.09% | -0.71% | +2.75% | -4.28% | +1.96% |
| capitulation-1.5x | BUY | -5.46% | +3.04% | -3.97% | +2.95% | +2.08% | +8.67% | +4.28% | -1.55% | +1.39% | +2.11% | -3.79% | +1.12% |
| capitulation-1.5x | BUY/high | -9.03% | +0.58% | -8.54% | +2.64% | +0.27% | +20.14% | -4.35% | -5.36% | +5.42% | +2.63% | -1.19% | +0.31% |
| capitulation-1.5x | BUY/standard | -4.95% | +3.52% | -2.96% | +3.10% | +2.74% | +5.70% | +5.71% | -0.84% | -0.22% | +1.94% | -4.44% | +1.37% |
| capitulation-2x | BUY | -6.75% | +3.17% | -5.19% | +3.04% | +2.00% | +6.16% | +2.78% | -0.91% | +2.60% | +1.97% | -3.75% | +0.94% |
| capitulation-2x | BUY/high | -9.03% | +1.82% | -8.54% | +4.47% | -2.36% | +16.81% | -4.35% | -5.76% | +5.42% | +1.71% | -0.81% | +0.82% |
| capitulation-2x | BUY/standard | -6.18% | +3.47% | -4.23% | +2.48% | +3.64% | +2.36% | +6.34% | +0.71% | +1.06% | +2.06% | -4.37% | +0.96% |
| trigger-rvol-1.2 | BUY | -6.22% | +1.54% | -2.49% | +0.42% | +5.10% | +6.64% | +11.91% | -1.69% | +1.15% | +2.06% | -1.58% | +0.75% |
| trigger-rvol-1.2 | BUY/high | -9.03% | +9.97% | -8.54% | -1.00% | +4.74% | +15.64% |  | -10.98% | +4.43% | +3.27% | -4.01% | +0.82% |
| trigger-rvol-1.2 | BUY/standard | -5.75% | -1.27% | +1.54% | +1.21% | +5.13% | +4.95% | +11.91% | +0.52% | -0.82% | +1.58% | -0.50% | +0.73% |
| obv-above-ema | BUY |  |  |  |  | +7.58% | +20.21% |  |  |  | -3.83% |  | -5.23% |
| obv-above-ema | BUY/high |  |  |  |  |  | +6.50% |  |  |  | -3.83% |  |  |
| obv-above-ema | BUY/standard |  |  |  |  | +7.58% | +24.78% |  |  |  |  |  | -5.23% |
| obv-divergence | BUY | +1.63% | +1.60% | -1.96% | +2.64% | -4.24% | -13.15% | +2.80% | -5.26% | -5.90% | +4.65% | +0.59% | -0.90% |
| obv-divergence | BUY/high | +6.97% | -8.97% | +0.65% | -3.16% |  |  | -4.35% | -3.94% |  | +3.17% |  | -0.90% |
| obv-divergence | BUY/standard | -1.04% | +3.36% | -2.40% | +3.79% | -4.24% | -13.15% | +4.59% | -6.58% | -5.90% | +5.51% | +0.59% |  |
| mfi-confluence | BUY | -1.80% | +5.87% | +3.91% | +1.98% | +0.71% | +9.60% | +13.32% | +0.48% | +1.30% | +6.14% | -1.79% | +4.89% |
| mfi-confluence | BUY/high |  | -5.65% |  | +2.81% | +0.74% |  |  |  |  | +0.05% | -0.60% |  |
| mfi-confluence | BUY/standard | -1.80% | +8.17% | +3.91% | +1.66% | +0.69% | +9.60% | +13.32% | +0.48% | +1.30% | +10.19% | -2.30% | +4.89% |
| capitulation+divergence | BUY | -1.04% | +2.29% | -4.96% | +2.64% | -12.37% |  | +3.26% | -5.62% | -5.90% | +2.35% | +1.22% | -0.90% |
| capitulation+divergence | BUY/high |  | -8.97% |  | -3.16% |  |  | -4.35% | -2.92% |  | +3.17% |  | -0.90% |
| capitulation+divergence | BUY/standard | -1.04% | +4.55% | -4.96% | +4.57% | -12.37% |  | +7.06% | -8.32% | -5.90% | +1.54% | +1.22% |  |
