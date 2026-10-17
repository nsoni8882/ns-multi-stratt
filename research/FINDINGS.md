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
  (Written when it was still listed and tagged LOW. It was dropped later in the same round —
  see "Both short legs are gone" below.)

## Round two: the structural pullback condition

The one idea left with a real mechanism behind it was requiring price to have actually come
back to a mean, rather than taking an RSI dip wherever it happens — the thing that separates
a pullback from a wobble in a name 25% above its EMA50. Measured against the bar
pre-registered in `ACCEPTANCE.md`:

| variant | n indep | alpha indep | t | both halves positive? |
|---|---:|---:|---:|---|
| shipped | 3,589 | +0.11% | +0.74 | no (2nd −0.01%) |
| **near-ema50-2pct** | 3,510 | **+0.15%** | **+1.05** | yes (+0.24% / +0.04%) |
| below-ema20 | 3,388 | +0.12% | +0.82 | no (2nd −0.01%) |
| below-ema20 + near-ema50-5pct | 3,387 | +0.12% | +0.82 | no |
| at-ema50 | 3,156 | +0.10% | +0.63 | no (2nd −0.00%) |
| near-ema50-5pct | 3,577 | +0.11% | +0.74 | no |

**Nothing shipped.** `near-ema50-2pct` is the best configuration found anywhere in this
project and the only one positive in both halves, and it still fails the pre-registered
t ≥ 2.5 by a wide margin at t=+1.05. The direction is mildly encouraging — every structural
variant is ≥ the shipped rule, which is more than the ADX or RSI-depth families managed — but
+4bp at t=1 after twelve configurations on one sample is indistinguishable from noise. The
2% threshold is also barely binding: it removes only 127 of 6,258 signals, so most of the
"extended name" cohort the idea was aimed at is not actually there to filter.

If this gets revisited, the honest next step is not another threshold on the same sample. It
is out-of-sample data — other indices, or the 4H timeframe — because this 12-year S&P window
has now been queried enough times that another pass through it cannot settle anything.

## Signal invalidation (prompted by a live CCL SELL)

CCL fired a Trend Pullback SELL on 2026-09-30 at 24.54 with RSI 56.9, crossing down through
60 from 61.6. Two bars later RSI was 63.6 — higher than before the cross — price was +4.97%
(the short down 4.97%), and the site still listed it as a live SELL. The obvious fix was to
drop signals whose premise has died. Measured first, and the measurement said not to:

| stale listing (1–2 bars old) | n | return from the current bar |
|---|---:|---:|
| BUY, premise still alive | 9,316 | +1.52% |
| BUY, **premise dead** | 2,717 | **+1.93%** |
| SELL, premise still alive | 3,628 | −1.59% |
| SELL, **premise dead** | 1,287 | **−0.71%** |

Hiding dead-premise signals would have thrown away the better half of the stale BUYs, which
makes mechanical sense: RSI falling back under 40 means price dipped further, so the entry is
cheaper. 22.6% of stale BUY listings and 26.2% of stale SELL listings have a dead premise.

So they are flagged, not dropped. The defect was never that the signal lost money — the SELL
leg loses money by construction — it was that the card described a setup that no longer
held. That is a labelling bug with a labelling fix.

## Volume: the quiet pullback is the best thing measured here, and it still does not ship

Five volume gates, 163 names x 12y, 20-bar horizon, against the shipped rule's +0.11%
(t indep +0.74, n indep 3,589). Independent sample:

| variant | n indep | alpha indep | t indep |
|---|---:|---:|---:|
| **dryup-0.9** (dip trades under 0.9x its own median volume) | 705 | **+0.50%** | **+1.75** |
| dryup-0.75 (same idea, stricter) | 263 | +0.75% | +1.56 |
| trigger-rvol-1.2 (recovery bar trades 1.2x normal) | 1,913 | −0.03% | −0.14 |
| obv-accumulation (OBV above its 20-EMA) | 1,257 | +0.04% | +0.17 |
| mfi-confluence (volume-weighted RSI crosses too) | 798 | −0.32% | −1.09 |

**Half the textbook is wrong here.** "Loud recovery bar" is worthless (−0.03%) and the
volume-weighted RSI is actively harmful (−0.32%). Only the *quiet pullback* half carries
anything, and it is dose-responsive: tightening 0.9 → 0.75 raises alpha +0.50% → +0.75%
while thinning the sample, which is the shape a real effect has. **Superseded: three more
thresholds were measured on 2026-10-12 and the gradient does not hold -- see round three
below.**

Against `ACCEPTANCE.md`, `dryup-0.9` scores 3 of 5:

1. Positive and above shipped — **pass** (+0.50% vs +0.11%).
2. |t indep| ≥ 2.5 — **fail, 1.75.** This is the one that decides it.
3. Positive in both halves — pass on the letter, fail on the meaning: first half +1.02%
   (t +2.63), second half **+0.05%** (t +0.12). The edge lives in the early years.
4. Survives dropping its best year — **pass, and comfortably**: +0.42% without 2019. Worth
   noting that the *shipped* rule fails this test outright (−0.21% without 2021).
5. n indep ≥ 500 — pass, 705.

So it is recorded, not shipped, and not re-tried at a third threshold. The honest reading is
that a pullback nobody sells into was worth something up to about 2020 and has not been worth
much since — which is what you would expect of an edge that became widely known.

The gates stay in `TrendPullbackConfig`, all defaulting to off, so the result can be
re-measured when there is more out-of-sample data rather than rebuilt from scratch.

## Round three, asked for directly: can the rule be tightened to 2-3 signals a day? (2026-10-12)

The live list shows ~46 names on 1d, against 1 for the reversal, and the owner asked for
fewer and more confident ones. Everything already measured that tightens entry is above and
*lowers* alpha -- RSI 35, ADX 20/25, every price-structure gate. The one exception is the
quiet pullback, so the dry-up threshold was extended from the two points measured before
(0.9, 0.75) to five, in both directions: 1.1 and 1.0 to buy back the sample size the t-stat
is short of, 0.8 to fill the gap. The previous section says the gate was not to be re-tried
at a third threshold; this is a deliberate exception, run as a monotonicity check rather than
a search for a better cut, and every point measured is reported here.

163 names x 12y, 20-bar horizon, independent sample. Shipped rule: +0.11%, t +0.74, n 3,589.

| max dip rvol | n indep | alpha indep | t indep | share of shipped signals |
|---|---:|---:|---:|---:|
| 1.1 | 1,580 | +0.28% | +1.43 | 35% |
| 1.0 | 1,146 | +0.04% | +0.17 | 24% |
| 0.9 | 705 | +0.50% | +1.75 | 13% |
| 0.8 | 378 | +0.89% | +2.19 | 7% |
| 0.75 | 263 | +0.75% | +1.56 | 5% |

**The dose-response claim in the previous section does not survive the extra points.** Read
off two thresholds it looked like a clean gradient; read off five it is +0.28, +0.04, +0.50,
+0.89, +0.75 -- noisy, non-monotone at 1.0 and reversing at 0.75. That is what a two-point
"gradient" is worth, and it is the same mistake as believing a pooled t-stat before looking
at the per-year table, one layer up.

Crossing dry-up with the gates that were individually too weak to ship adds nothing except in
one case:

| variant | n indep | alpha indep | t indep | 1st half | 2nd half |
|---|---:|---:|---:|---:|---:|
| dryup-0.9 + near-ema50-2pct | 700 | +0.54% | +1.88 | +1.02% | +0.05% |
| dryup-0.9 + below-ema20 | 661 | +0.50% | +1.66 | | |
| dryup-0.9 + rising EMA200 | 698 | +0.52% | +1.78 | | |
| **dryup-0.9 + OBV above its EMA** | 223 | **+1.30%** | **+2.47** | +0.85% | **+1.77%** |

`dryup-0.9+obv` is the only cohort measured in this repo whose edge is *larger in the second
half than the first* (+1.77%, t +2.09, against +0.85%, t +1.33). Every other candidate,
including dry-up on its own, earns its alpha before 2020 and nothing after. It also survives
dropping its best year (2021, +6.40%) and is positive in 9 of 11.

**Neither candidate clears ACCEPTANCE.md:**

- `dryup-0.8`: passes 1, 3, 4. Fails 2 (t 2.19 < 2.5) and 5 (n indep 378 < 500).
- `dryup-0.9+obv`: passes 1, 3, 4, and 3 in the strong form. Fails 2 (t 2.47, *just* under)
  and 5 (n indep 223 < 500).

Both fail on the same two rules, and the pattern is structural rather than bad luck: with a
20-bar horizon the per-signal standard deviation is ~8-9%, so t >= 2.5 at n = 500 needs alpha
near +1.0%. A gate selective enough to leave 2-3 names a day cannot also leave 500
independent events in twelve years. **Rule 5 and "fewer, better signals" are in direct
conflict, and no amount of measuring resolves it** -- it is a decision about how much evidence
is enough, and measuring harder does not make it.

**`dryup-0.9+obv` shipped anyway, as 1.7.0, on the owner's instruction** -- the brief was a
list short enough to read, and this leaves about 2 names a day against 46. The two failures
are on the record in the amendment at the end of ACCEPTANCE.md, together with what did *not*
change: the t 2.5 bar was not lowered for anything else, and the next candidate is measured
against the original numbers. The case for making this the exception rather than `dryup-0.8`
is rule 3 in its strong form -- it is the only cohort in this repo whose second half beats its
first, which is the opposite of every variant rejected here, several of which were killed
precisely because their edge died after 2020.

It ships on probation, and the test is forward: ~25 independent signals a year, re-measured
on the pinned universe. If the second half that justified it stops holding, 1.7.0 goes back
to the price-only rule rather than being defended. The price-only rule stays measurable as
`VARIANTS["price-only"]` for exactly that reason, and it is what every other variant is still
a delta from, so the tables above remain comparable.

Two things found on the way, both now fixed in the tree:

- **The dry-up gate silently deleted the entire SELL leg**, and for an arithmetic reason, not
  a measured one: `dip_mean_rvol` walks back through *sub*-level RSI bars, but the run before
  a SELL sits above the level, so on the raw series it averaged nothing, returned NaN, and the
  gate read NaN as "unmeasured, reject". It is mirrored now, the same way `evaluate` already
  mirrored the descriptive helpers, and the short leg measures -1.75% (t -2.13, n indep 130)
  under the shipped gates -- reliably wrong, as it has been in every cut of this data.
- **The yardstick was moving:** see below.

## The yardstick was moving (2026-10-12)

`research/measure.py` called `load_universe()`, which **scrapes Wikipedia live**, and
`pick_tickers` strides through the sorted result -- so a single S&P constituent change shifts
which 163 names are sampled and every number in every table moves with it. Re-running the
committed table nine days later, with no code change and an untouched price cache, moved the
shipped rule's alpha from +0.11% to +0.01% and `dryup-0.9` from +0.50% (t 1.75) to +0.13%
(t 0.42) -- which reads exactly like an edge failing to replicate, and is not.

Research now pins `scanner/universe_fallback.csv`, the committed snapshot, and `--universe
live` is opt-in. With it pinned, every number in `results/trend_pullback.md` reproduces the
2026-10-03 run exactly. A yardstick that changes length between measurements is worse than a
coarse one, because its movements look like findings.

## The reversal strategy's exhaustion thesis predicts a volume climax. It isn't there.

Same five gates on MACD + RSI Reversal, 164 names x 12y, against its shipped +1.65%
(t indep +2.73, n indep 332). Independent sample, BUY leg:

| variant | n indep | alpha indep | t indep |
|---|---:|---:|---:|
| **shipped (no volume condition)** | 332 | **+1.65%** | **+2.73** |
| capitulation-1.5x | 265 | +1.06% | +1.52 |
| capitulation-2x | 183 | +1.19% | +1.43 |
| trigger-rvol-1.2 | 157 | +0.59% | +0.63 |
| obv-divergence | 54 | +0.32% | +0.30 |
| mfi-confluence | 66 | +3.12% | +2.30 |
| capitulation+divergence | 36 | −0.10% | −0.07 |

The strategy's own story is that a deep histogram plus oversold RSI marks sellers giving up,
and giving up is supposed to be loud. **Requiring the volume climax removes good signals**:
every capitulation threshold lowers alpha, monotonically. The lows worth buying are often
quiet ones. OBV divergence, the other textbook tell, is worth nothing here either.

`mfi-confluence` looks best on alpha but has n indep 66 against a bar of 500. It is noise
with a good hairstyle, and is recorded so it is not re-proposed as a discovery.

Nothing shipped. The shipped rule is already the best variant of itself.

## Both short legs are gone

Measured on the same run, and this one was decisive.

| leg | n indep | alpha indep | t indep | win |
|---|---:|---:|---:|---:|
| Trend Pullback SELL | 1,487 | **−2.08%** | **−8.14** | 43.5% |
| MACD + RSI Reversal SELL | 239 | +0.05% | +0.09 | 50.4% |

A short's benchmark is cash, not the stock, so −2.08% means shorting these lost 2.08% over
20 bars. That is not "no edge", it is **reliably wrong**, and it is the most significant
result in this repo by a distance: negative in 9 of 11 years, win rate 34–47% in nine of
them, with only 2021 and a +0.54% 2022 on the other side. The reversal's short leg is simply
nothing: what little it has comes from one month of 2020.

Both were switched off on the strength of that table.

### ...and both are published again, deliberately, as of 2026-10-04

The owner asked for the short legs back so the live signals can be watched and tested against
the numbers above. **Nothing re-measured in their favour. This change does not clear
`ACCEPTANCE.md` and is not claimed to.** It is a monitoring decision, not a research result,
and the table above is still what the evidence says.

What holds the honesty of it:

- Every SELL is pinned to `LOW` conviction in `rule_side` — the tier cannot be earned by a
  short, whatever its rally height, because `depth_tiers` only grades the long leg.
- Both strategies' `description` and the newest `history` entry say in plain English that the
  SELLs lost money in backtest and are listed to be watched, not traded.
- `enable_short=True` is now the default, and `VARIANTS["long-only"]` is the configuration
  that reproduces the measurements in this section. The `with-shorts` variant is retained as
  the label the published rule runs under.

Re-measuring is a config swap, not a code change: compare `shipped` against `long-only`. If
the live SELLs track the −2.08%, turn the flag back off.

## Open, unmeasured: does the *reason* for a dip matter? (news judgment)

Every gate tried so far asks the price series a sharper question, and every one has failed.
The one question the price series cannot answer is *why* the dip happened. Trend Pullback
assumes an RSI dip inside an uptrend is noise; the failure mode it cannot see is the dip that
is a company coming apart — guidance pulled, an investigation opened, a trial failed.

`research/news_judgment.py` records a semantic judgment of that, per live signal, using
TypeSafe's Jev model (two Nouls: is there a company-specific adverse event, and is this feed
substantive at all). **It is a recorder, not a gate.** It reads the published lists, writes to
`research/judgments/`, and touches nothing in `scanner/`.

It is built forward rather than backtested on purpose. A 12-year news corpus that can be
obtained today is edited after the fact and missing de-listed names, so measuring against it
would manufacture an edge instead of testing one. The sample therefore accumulates in real
time and cannot be scored until it is large enough — see `ACCEPTANCE.md` for the bar, which
was written before any of these numbers exist.

Known weakness to fix before the sample is worth much: the news source is Yahoo's RSS feed,
which throttles hard (429 after a handful of requests) and carries a lot of listicle noise.
`fetch_headlines` is one function, so swapping in a real news API changes nothing else.

## A third strategy was built on the best-documented volume effect. It is worse than nothing.

`scanner/strategies/volume_breakout.py`, measured against the six rules written for a new
strategy in `ACCEPTANCE.md` before any of this existed. 164 names x 12y, 20-bar horizon,
alpha per ticker against buy-and-hold. Regenerate with
`python -m research.measure --strategy volume-breakout`.

The starting point was deliberately the one volume result with independent evidence outside
this repo: the **high-volume return premium** (Gervais, Kaniel and Mingelgrin, 2001) — names
that trade unusually heavily outperform over the following month, on the reading that a
volume spike is attention. The core gate is that spike; everything else is confluence layered
on one at a time.

| variant | n indep | alpha indep | t indep |
|---|---:|---:|---:|
| spike 1.5x its 20-bar median volume | 13,718 | −0.07% | −0.89 |
| **spike 2x (the core effect, alone)** | 9,445 | **−0.01%** | **−0.10** |
| spike 3x | 3,809 | −0.22% | −1.46 |
| spike + 50-bar closing-high breakout | 2,611 | **−0.74%** | **−4.56** |
| spike + above the 200 EMA | 6,792 | −0.35% | −3.35 |
| spike + closed in the top 40% of its range | 5,675 | −0.38% | −2.99 |
| spike + OBV above its 20-EMA | 5,873 | −0.28% | −2.42 |
| spike + quiet base before it | 1,114 | +0.18% | +0.65 |
| all four confluences at once | 150 | −1.61% | −2.56 |

**The premium is not here.** On S&P 500 names over these 12 years the spike alone is exactly
nothing (−0.01%, t −0.10), and raising the threshold makes it worse rather than better —
the opposite of the dose-response a real effect shows. The published result was found on a
much broader NYSE cross-section in an earlier era; large caps are the part of the market
where attention is least scarce, which is the obvious place for it to have been arbitraged
away or never to have existed.

**Every confluence condition made it worse, and the breakout made it much worse.** Buying a
volume spike *that is also a 50-bar closing high* underperformed simply holding the same
stock by 0.74% over the next 20 bars, t = −4.56 on 2,611 independent signals. That one is not
a period artefact and does not get the 2020 treatment: first half −0.78% (t −3.73), second
half −0.70% (t −2.71), negative in 9 of the 11 years. The textbook setup in full is −1.61%.

The honest reading is that the loud breakout is where the move has already happened and the
buyer is the last one in. It is consistent with what this repo has measured twice before: on
the Reversal strategy every capitulation-volume threshold lowered alpha monotonically, and on
Trend Pullback the loud recovery bar was worthless while the *quiet* dip was the only volume
gate ever to measure positive. **Three strategies, one direction: in this universe loud
volume is a cost and quiet volume is mildly good.** The quiet-base variant here is the fourth
appearance of that same effect (+0.18%, t +0.65) and, like the other three, not significant.

Against `ACCEPTANCE.md` the candidate fails rules 1 and 2 outright — no positive alpha, no
t ≥ 2.5 — so rules 3 to 6 never come into it. **Nothing ships. The site keeps two
strategies.** The module stays in the tree, unregistered and absent from `STRATEGIES`, with
its variants intact so the numbers can be reproduced; `test_volume_breakout.py` asserts it is
not published. Do not re-propose a volume-spike entry without reading this table first.

What this does *not* say: that volume is uninformative. It says that every rule tried here
which requires volume to be *high* has lost money relative to holding the stock, four
independent times. If there is an edge in volume in this universe it is on the quiet side,
and it has now been measured four times at between +0.13% and +0.75% with t between 0.65 and
1.75 — always the right sign, never significant. That is the thing to re-measure when there
is more out-of-sample data, not another breakout.

## Momentum, ranked across the universe: chasing the leader is the losing side of the trade

Three crypto momentum rules were put forward as the basis for a third strategy: go long the
strongest 7-day mover while price and volume keep rising; chase whichever name currently
leads and switch when another overtakes it; and DCA into the top 20 by market cap.

Only the first two have signal content — the third is an allocation policy, and its
"shortlist" is the largest names by definition, which needs no scanner. What survives
translation from both is the same object: a **cross-sectional momentum rank**, which this
repo had no way to express, because both shipped strategies read one ticker at a time.
`research/cross.py` adds the panel and `research/measure_cross.py` scores it; the rule itself
was never written into `scanner/`, for the reason below.

163 names, 12y of daily bars, 20-bar horizon, alpha per ticker against buy-and-hold. A name
fires on the bar it *joins* the leaders. **`t by date` is the number that counts** — rule 7
in ACCEPTANCE.md, written before this ran: a ranked rule flags many names on one morning and
those names move together, so each date is collapsed to one observation first.

| variant | n | n dates | alpha by date | t by date |
|---|---:|---:|---:|---:|
| **5-day leaders (rules 1 and 2 as written)** | 10,153 | 2,692 | **−0.24%** | **−1.75** |
| 5-day + volume at or above normal | 8,244 | 2,578 | −0.29% | −1.87 |
| 5-day + price above its 50-bar mean | 8,528 | 2,633 | −0.38% | −2.65 |
| 5-day + the move still accelerating | 9,759 | 2,680 | −0.25% | −1.76 |
| 5-day, all three confirmations | 6,749 | 2,449 | −0.24% | −1.51 |
| 5-day, top 1% only (rule 2's single leader) | 2,787 | 2,138 | −0.51% | −2.09 |
| 21-day leaders | 5,256 | 2,535 | −0.35% | −2.05 |
| 63-day leaders | 3,265 | 2,162 | −0.51% | −2.62 |
| 126-day leaders | 2,294 | 1,807 | −0.52% | −2.31 |
| 12-1 momentum (252 bars, skipping the last 21) | 1,776 | 1,549 | +0.22% | +0.84 |

**The 7-day rule is not merely unprofitable here, it is the wrong sign, and every
confirmation the rules ask for makes it worse.** Requiring price to keep rising takes it from
−0.24% to −0.38% (t −2.65). Requiring volume to keep rising makes it worse. Taking only the
single strongest name — rule 2's leader — makes it worse again, −0.51%. Buying last week's
strongest S&P name underperformed simply holding that name by about a quarter of a percent
over the next month, and the stricter the reading of "strongest", the more it lost.

This is not a surprise and it is not a crypto-versus-stocks quibble about volatility. A
one-week horizon in equities is the **short-term reversal** window: last week's winners are
systematically next week's laggards, which is one of the oldest documented effects in the
cross-section. Momentum in stocks is an *intermediate-horizon* phenomenon — the textbook
definition is a 12-month lookback that deliberately skips the most recent month precisely
because the last few weeks reverse. Measured here, that definition is the only one of the ten
that comes out positive at all: +0.22%, t +0.84. Right sign, no significance, and it fails
on its own terms.

**The one number that looked shippable isn't.** The top 1% of 126-day leaders scored +1.16%
at t = +2.45 on 627 dates, which is close enough to the bar to be worth saying out loud why
it does not pass:

* t by date 2.45 is under the 2.5 in ACCEPTANCE.md, and that bar exists because fifteen
  variants were scored on one sample.
* n independent is 322, under the 500 in rule 5.
* It is **not monotone in the threshold**, which is the tell. The top 5% of the *same*
  lookback is −0.52%. An effect that is strongly positive in the top 1% and negative in the
  top 5% of the same ranking is not an effect, it is a thin tail of a noisy distribution.
* It is negative in 5 of its 12 years, and dropping its best year takes it to +0.80%,
  t +1.64.
* Two post-hoc variants were then run to see whether it generalised to the adjacent
  definition — the top 1% of 12-1 momentum, which the declared grid had not crossed. It does
  not: +0.37%, t +0.62, and **negative in the first half**. These two are labelled
  `posthoc-` in the variants list because they were chosen after seeing the table, and their
  bar is higher for that reason.

**Nothing ships. The site keeps two strategies.** No module was added to `scanner/` at all
this time: the rule does not exist outside the research harness, so there is nothing to
register and nothing to keep in step. What was kept is the harness, because it is the piece
that was genuinely missing — `cross.py` can rank the universe on any definition, and rule 7
is now wired into the reporting so the next ranked idea gets collapsed by date automatically.

One guard this run added by failing first: every boolean panel is forced to `bool` dtype. A
NaN anywhere makes a pandas boolean frame object-dtype, and `~` on an object column is
bitwise arithmetic on the underlying ints, so `not False` comes out as −1, which is truthy.
It produced a plausible-looking table rather than an error. `test_cross.py` pins it.

## Short-term reversal, long the losers: close, and it decays (2026-10-16)

Prompted by a literature sweep for edges that survive costs. Four variants, declared in
`cross.py` before any was run (lookback 5 or 21 bars x bottom 5% or 10% of the cross-section,
each scored at the horizon its lookback names), 164 names x 12y of daily bars, alpha against each
name's buy-and-hold. Long only, because nothing here shorts; published reversal returns are
long-short, so this is the half that could be traded. Results are in `research/results/reversal-5d`
and `reversal-21d`. Bar: ACCEPTANCE rules 1-5 and 7, unchanged, and net of ~5.5 bps a round trip.

| variant | n dates | alpha by date | t by date | 1st half | 2nd half | without 2020 (t) |
|---|---:|---:|---:|---:|---:|---:|
| rev-5d-bottom5 | 2,706 | +0.19% | +1.87 | +0.22% | +0.15% | +0.10% (1.08) |
| rev-5d-bottom10 | 2,717 | +0.18% | +2.32 | +0.22% | +0.14% | +0.13% (1.82) |
| rev-21d-bottom5 | 2,475 | +0.76% | **+3.34** | +1.62% | **-0.09%** | +0.46% (2.16) |
| rev-21d-bottom10 | 2,673 | +0.35% | +2.10 | +1.00% | **-0.30%** | +0.15% (0.98) |

**None passes.** Why, variant by variant:

* **rev-21d-bottom5 is the only t above 2.5 and it is a historical note, not a screener.** The
  first half earns +1.62% (t +5.04); the second half earns -0.09% (t -0.28), which fails rule 3.
  Without 2020 it falls to t 2.16, which fails rule 4's spirit and the 2.5 bar. 2015 alone is
  -13.77%. The edge existed and then went, which is what the literature says happened to published
  reversal.
* **The 5-day variants are positive in both halves but under the bar.** Gross +18 to +19 bps a
  trade is real against ~5.5 bps of cost, so the mechanism is not dead at the weekly horizon, but
  t by date is 1.87 and 2.32, below 2.5, and 2020 carries the larger part of the 5% cut (t 1.08
  without it). rev-5d-bottom10 is the closest: both halves positive, t indep +3.95, second half
  weaker (+0.14%, t 1.37).
* **Survivorship flatters all of this.** The universe is today's S&P 500, so names that fell and
  never recovered are absent, and buying last month's biggest losers is exactly the trade that
  bias helps. The true figures are lower than these.

What it rules out: the 21-day reversal as a live rule (second half is zero). What stays open, and
only as a weak lead: the weekly reversal, where the sign is stable and the size is small. Not
re-proposed: a different threshold on these four. A follow-up needs a new reason, a
point-in-time universe, and a bar that accounts for the four trials already spent here.

### ...and on a point-in-time universe the weekly edge is gone (2026-10-16)

The two weekly variants were re-measured with each date ranked only against the names that were
in the S&P 500 that day (`research/pit.py`, `--pit`, membership from fja05680/sp500; declared in
`cross.py` before the run). 730 of the 1,209 symbols that were ever members had prices, but that is
97 to 100% of member-days from 2015 on (88% in 2014), so the hole is small for this window. Results:
`research/results/reversal-pit`.

| variant | n dates | alpha by date | t by date | 1st half | 2nd half | net of 5.5 bps |
|---|---:|---:|---:|---:|---:|---:|
| pit-rev-5d-bottom5 | 2,685 | +0.07% | +0.84 | +0.10% | +0.03% | +0.01% |
| pit-rev-5d-bottom10 | 2,685 | +0.06% | +0.86 | +0.11% | +0.01% | +0.01% |

**Rejected.** Alpha fell from +0.19% to +0.07% and t from 1.87-2.32 to 0.84-0.86; without 2020 it is
+0.03% (t 0.41); the second half is zero and net of cost both variants are roughly nil. So most of
the earlier weekly alpha was the survivor universe, as flagged. (`t indep` stays high, 3.2-3.9, and is
the number the date-collapse rule exists to overrule: the signals are many names on the same days.)
Remaining bias is the ~500 names without prices, so the true figure is if anything lower.

Closed: long-only short-term reversal in S&P 500 names at 5 and 21 days, on this data and these
costs. Not re-proposed. The literature's reversal is long-short and in less liquid names; neither is
available here.

## The RSI(2) rule, tested beyond AMZN and AAPL, and a bug in its backtest (2026-10-17)

`research/rsi2_universe.py`, declared before it ran: the live rule on every name in the
point-in-time S&P 500 (764 symbols with prices, 2014-10 to 2026-10), a trade counting only if the
name was a member on its signal day, alpha against the name's own drift over the same hold.
Two variants: the live rule (`rsi2`) and an IBS cousin (`ibs`).

**1. The backtest that justifies the trader double-counted a bar.** `rsi2_edge_backtest.backtest`
re-entered on the bar it exited whenever the prior bar also signalled. An exit on RSI(2) > 65 is a
big rebound day, so the phantom entry booked that day's return a second time as a one-bar trade:
AMZN 29 such trades averaging +283 bps, AAPL 18 averaging +352 bps (2014+). Without them the same
backtest averages +30 and +21 bps. The fix (`was_in`) makes it agree trade for trade with the
live rule (`test_rsi2_universe.py`), and with the Pine strategy's AMZN trade count (199).

| 2000 to 2026, one position at a time | old backtest | corrected | drift over the hold | alpha, t |
|---|---:|---:|---:|---:|
| AMZN | 232 trades, +150 bps | 199 trades, +112 bps | 43 bps | +68 bps, t 2.30 |
| SPY | 214 trades, +61 bps | 187 trades, +50 bps | 15 bps | +35 bps, t 2.61 |

(AAPL could not be re-pulled; Yahoo rate-limited. The 2014+ cache gives AAPL +46 bps against a 51 bps
drift over the hold.) So the edge is real-looking but about half the documented size and t about
2.3, not above 5. `trader/ACCEPTANCE.md` still carries the old +150 / +117 bps bar and the
"t above 5" in the research notes. That is the owner's to revisit; nothing in `trader/` was changed.

**2. Since 2014, across the universe, the rule earns the drift and nothing more.** Excluding
AMZN and AAPL (576 names, 30,760 trades): trade-weighted alpha **+0.04%, t +0.40** (cluster-robust by
week); +0.13%, t +1.27 against the uptrend-conditional drift; first half +0.00%, second half +0.08%.
Capacity-capped portfolios (2, 5 or 10 open names, random pick on busy days) give +0.03%, +0.01% and
0.00%. Net +32 bps a trade is the name's drift over a 4.5-bar hold, which is what any long position
in these names earned. AMZN and AAPL rank 185 and 215 of 576 by mean net trade: not outliers, and
their own alpha over drift since 2014 is about 0 (-0 and -5 bps). IBS is worse (alpha +0.10%, t 1.8,
second half -0.01%).

**3. A flaw in my own pre-declared bar.** The bar named `t by week` (alpha averaged within each
week, then a t across weeks) as decisive, and by it `rsi2` passed everything (alpha +0.36%, t +4.79,
both halves 3.3+, 572 weeks). That statistic weights a quiet week with three trades the same as a
crash week with 200, and the crash weeks are where the rule loses (2015, 2018, 2020, 2022 all negative
per trade). The trade-weighted number above is the one a portfolio earns. The declared bar was wrong,
the pass is an artifact, and it is recorded as one rather than quietly replaced. A weekly-mean t is
not used again for a signal that clusters in selloffs.

What this rules out: RSI(2) mean reversion as a source of alpha over the drift in S&P 500 names since
2014. What it leaves: a modest edge in AMZN and SPY over 2000 to 2026 that sits largely before 2014.
Not re-proposed: IBS and other close-location variants of the same mechanism.

## Trend on asset-class ETFs: a drawdown overlay, not an edge (2026-10-17)

`research/trend_etf.py`, bar declared before it ran: long while close > SMA(200) (yesterday's
close), else cash, 5 bps a switch, on SPY QQQ IWM EFA EEM TLT GLD DBC, equal weight, 2007 to 2026,
against buying and holding the same basket. The claim in the literature is similar return for a much
smaller drawdown, so the bar was risk-adjusted: Sharpe at least equal, max drawdown at least 30%
smaller, beta-adjusted alpha positive in both halves, and all of it still true without 2008.

| | trend | hold | alpha (t) |
|---|---:|---:|---:|
| all: Sharpe / max DD / return | 0.72 / -12.3% / 6.1% | 0.64 / -40.5% / 9.4% | +2.7%/yr (1.98) |
| first half | 0.49 / -12.3% | 0.44 / -40.5% | +2.1%/yr (1.04) |
| second half | 0.97 / -10.4% | 0.89 / -24.4% | +2.6%/yr (1.47) |
| **without 2008** | **0.77** / -12.3% | **0.84** / -24.4% | +1.4%/yr (1.10) |

**Does not pass as declared: rule 4 fails, as flagged in advance.** With 2008 removed the Sharpe falls
below buy-and-hold (0.77 vs 0.84). The drawdown benefit survives (-12.3% against -24.4%, half) and
alpha stays positive, but it is small and not significant (t 1.1 to 2.0). What the rule does: sits at
beta 0.37, gives up about 3 points of return a year (6.1% against 9.4%) and cuts the worst drawdown by
70%. Per asset it helps SPY (Sharpe 0.76 vs 0.63) and DBC, is neutral on QQQ and EFA, and hurts TLT, GLD,
IWM and EEM.

So it is insurance against a crash, priced at the return it forgoes in calm years, not a source of
alpha. Worth knowing for sizing a portfolio; not a strategy to publish as an edge. Not re-proposed: a
different average length on the same basket.

## Standing guards

Two things from these runs should stay regardless of what is tested next: score the
independent (non-overlapping) sample, and look at the per-year table before believing any
t-stat. Both are built into `measure.py`, and `ACCEPTANCE.md` holds the bar.
