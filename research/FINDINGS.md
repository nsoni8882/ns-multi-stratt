# Trend Pullback: what the measurement actually said

Run `python -m research.measure` to regenerate `results/trend_pullback.md`. This file is the
interpretation; that one is the numbers. Sample: 163 S&P names, 12y of daily bars, 476k scored
bars, 20-bar forward horizon, alpha measured per ticker against buy-and-hold.

**Headline: none of the proposed changes survived measurement, and the shipped rule has no
measurable long edge either.** The 50/200 EMA periods were never the problem.

## The two changes that were wired up and tested

| hypothesis | prediction | result (independent sample) |
|---|---|---|
| Deeper RSI trigger (40 → 35) buys better | higher alpha | **−0.25%, t=−1.18** vs shipped +0.11%, t=+0.74 |
| ADX ≥ 20 gate removes chop | higher alpha | **−0.08%, t=−0.44**; at ADX ≥ 25, −0.38%, t=−1.65 |

Both are *worse* than the shipped rule, and tightening either one makes it monotonically
worse. The "chop above the 200 EMA" story was wrong: strong-ADX trends are where pullback
entries do badly, because by the time ADX is high the move is already extended.

The deeper-trigger result also has a structural catch worth keeping in mind — `rsi35` is not a
stricter filter on the same signals. RSI crosses 35 on the way back up *before* it crosses 40,
so the deeper level buys the same pullback a couple of bars earlier at a lower price. It is a
different entry, not a subset, which is why its n drops to 2,558 while firing on the same
underlying events. (`test_a_lower_rsi_trigger_moves_the_entry_rather_than_filtering_it`.)

## The finding that looked strong and wasn't

Grading conviction by how deep the pullback went produced the only large, highly significant
number in the whole run — in the **opposite** direction to the Reversal strategy's depth table:

| pullback depth | n indep | alpha indep | t |
|---|---:|---:|---:|
| RSI dipped ≤ 30 (deep) | 692 | **−1.55%** | −4.04 |
| RSI dipped 30–35 | 1,295 | +0.15% | +0.66 |
| RSI dipped > 35 (shallow) | 2,687 | **+0.28%** | +1.79 |

t = −4.04 on 692 independent observations is the kind of number that gets shipped. It should
not be. Split the sample in half and it is entirely in the first half (−2.97%, t=−5.21) and
absent from the second (+0.19%, t=+0.40). The per-year table says why:

| year | 2016 | 2017 | 2018 | 2019 | **2020** | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| deep cohort alpha | −0.11% | −1.17% | −1.24% | +2.44% | **−15.16%** | +1.34% | −2.25% | +2.42% | +0.90% | −1.89% | +1.16% |

70 signals in 2020 at −15.16% carry the entire effect; every other year sits between −2.25%
and +2.44%. This is the COVID crash, not a property of deep pullbacks: a deep RSI dip inside
an intact uptrend is exactly what the first leg down of February 2020 looked like, and the
next 20 sessions were the fastest drawdown on record. One event, 163 correlated names.

The same caution applies in reverse to the shallow cohort's +0.28%: first half +0.64%
(t=+2.85), second half −0.08% (t=−0.36). Not robust either.

## What did not matter at all

- **Dropping `ema50 > ema200`** moved alpha from +0.11% to +0.09% and added 17 signals out of
  6,258. The condition is near-collinear with `close > ema200`, as suspected — so it is dead
  weight, but removing it buys nothing. Left in place.
- **Requiring a rising EMA200** changed alpha by +0.00pp. The 200 EMA being below price almost
  always implies it is rising.

## Where the strategy actually stands

- **BUY leg: +0.11% alpha, t=+0.74, n=3,589 independent.** Indistinguishable from zero. The
  58.5% win rate sounds good until you price the do-nothing benchmark: across all 407,648
  scored bars, a random 20-day hold in this sample was positive **57.6%** of the time and
  returned +1.44%. The signal buys you 0.9pp of win rate and 5bp of return. The edge is in
  the drift, not the signal. Treat this strategy as a *timing/attention* tool for names you
  already want to own, not as an alpha source.
- **SELL leg: −2.08% alpha, t=−8.14.** Decisively negative, consistent across both halves.
  This is the one statistically solid result in the run and it says the short leg loses money.
  It stays tagged LOW; dropping it entirely is defensible.

## What would be worth testing next

Nothing in the gate-tuning direction — that avenue is measured out. The untested idea with a
real mechanism behind it is **#2 from the original review: requiring the pullback to actually
reach a reference level** (`close` within ~2% of the EMA50, or below the EMA20), which is a
structural condition rather than another oscillator threshold, and is the one thing that
distinguishes a pullback from a dip in a name that is 25% extended. Add `pullback_to_ema`
to `TrendPullbackConfig` and measure it the same way.

Whatever is tested next, two guards from this run should stay: score the independent
(non-overlapping) sample, and look at the per-year table before believing any t-stat.
