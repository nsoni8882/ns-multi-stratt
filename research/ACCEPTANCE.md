# The bar a variant has to clear to get shipped

Written before the structural-pullback variants were measured, and committed before their
numbers existed, so the thresholds cannot be bent to fit whatever came out. By the end of
that run roughly a dozen configurations will have been scored on one 12-year sample; at a
conventional t > 2 that alone yields a false positive most of the time, which is how the
deep-pullback artefact in `FINDINGS.md` nearly got shipped.

A variant replaces the shipped default only if **all five** hold on the BUY leg:

1. **Positive alpha** on the non-overlapping sample, and larger than the shipped rule's.
2. **|t| ≥ 2.5** on the non-overlapping sample — not 2.0, because of the multiple testing above.
3. **Positive in both halves** of the sub-period split. Either half negative disqualifies it.
4. **No single year carries it.** Drop the best year; alpha must stay positive and above the
   shipped rule. (This is the check the deep-pullback variant failed: drop 2020 and it vanishes.)
5. **n_independent ≥ 500**, so the result is not a handful of events.

A variant that passes 1–2 but fails 3–5 is recorded in `FINDINGS.md` as measured-and-rejected,
not shipped and not quietly re-tried with a different threshold.

Anything that only tightens entry criteria also has to justify its cost in signal count: a
gate that halves n to buy 2bp of alpha makes the screener quieter without making it better.

**Amended 2026-10-03, on the owner's instruction:** accuracy is worth more than coverage here,
so the signal-count clause above no longer blocks a variant on its own. A gate that halves n
for a real improvement in per-signal edge is acceptable. Nothing else moves — in particular
the t >= 2.5 bar stands, because it is not a preference about how many signals to show, it is
the protection against shipping a result that is noise. Wanting fewer, better signals is not a
reason to lower the standard of evidence for what "better" means.

## The bar for a whole new strategy (written 2026-10-04, before Volume Breakout was measured)

The five rules above compare a variant against the rule it would replace. A new strategy has
nothing to replace, so "better than shipped" is not available and the bar has to be written
differently — before its numbers exist, for the usual reason.

A third strategy gets published only if **all six** hold on its BUY leg:

1. **Positive alpha** on the non-overlapping sample, against the per-ticker buy-and-hold
   baseline. Beating cash is not the test; beating holding the same name is.
2. **t indep ≥ 2.5.** Same bar, same reason, and it is the one that decides this.
3. **Positive in both halves** of the sub-period split, and meaningfully so in the second.
   An edge that lived until 2020 and died is a historical note, not a screener.
4. **No single year carries it.** Drop the best year; alpha stays positive.
5. **n indep ≥ 500.**
6. **It is not one of the other two in disguise.** If most of its signals land within a few
   bars of a Trend Pullback or Reversal signal on the same name, it is a relabelling that
   adds a third list without adding information, and it does not ship.

Rule 6 is new here and exists because the obvious volume strategies are built from the same
RSI and trend conditions the other two already use.

If a candidate fails, it is recorded in `FINDINGS.md` as measured-and-rejected with its
numbers, the module stays in the tree with its variants intact so the result can be
reproduced, and it is simply not registered in `STRATEGIES`. The site keeps two strategies.
An unmeasured third strategy is worse than no third strategy: it would be the only list on
the site with no evidence behind it, which is the property that makes the other two worth
reading.

## Rule 7, for a strategy that ranks the universe (written 2026-10-04, before Relative Strength was measured)

Everything above assumes signals are independent once their forward windows do not overlap,
which is true for a rule that reads one ticker at a time. A cross-sectional rule breaks that
assumption in a new way: it fires on *many names on the same day*, and those names rise and
fall together. Forty leaders flagged on one morning is close to one observation, not forty,
and the existing per-ticker thinning will not catch it — it thins within a ticker, not across
the market.

So a ranked strategy also has to clear:

7. **t ≥ 2.5 on the date-collapsed sample.** Average the alpha of every signal that fired on
   the same date into one number per date, then take the t-stat across dates. That is the
   sample size the market actually provided. Where this differs from the per-ticker
   independent t, the date-collapsed one wins, and `n dates` is reported next to it.

This is the same class of mistake as the overlap and the single-year traps already guarded in
`measure.py`, found one layer up, and it is the one most likely to make a ranked rule look
significant when it is one bull market seen forty times at once.

## The bar for the news judgment (written 2026-10-03, before any judgments existed)

`research/news_judgment.py` records a model's reading of the news behind each live signal. It
is a recorder today and must stay one until all of the following hold. Written now, while the
sample is empty, for the same reason as the rules above: so the threshold cannot be chosen
once the numbers are in.

1. **A real sample.** n_independent ≥ 500 judged signals, accumulated forward. Judgments made
   about a bar after the fact do not count, whatever the source claims.
2. **The usual five**, unchanged, applied to the filtered variant against the shipped rule.
3. **The judgment has to be answerable.** Signals where `substantive_company_news` is low are
   excluded from the test rather than counted as "no adverse event" — an empty feed is missing
   evidence, not a verdict.
4. **Stability across the probability threshold.** The result must hold over a range of cutoffs
   (say 0.6 to 0.9), not at one tuned value. A finding that exists only at p > 0.83 is a
   fitted threshold, not an effect.
5. **A model version is part of the rule.** The answers carry the model that produced them.
   If that version changes mid-sample, the sample splits; results do not carry across it.

Ship order if it ever clears the bar: flag first (extend the existing "Setup changed" label),
conviction demotion second, entry gate last and only on its own evidence. Each step goes into
`params` and needs its own history entry.

## The one thing shipped below this bar (2026-10-12)

`TrendPullback` 1.7.0 gates on a quiet pullback — volume through the dip under 0.9x that
stock's normal, with OBV above its own EMA — and **it does not clear the five rules above.**
It is recorded here rather than tidied away, because an acceptance bar that is silently
stepped over is worse than none.

What it scores, 163 names x 12y, independent sample, against the price-only rule's +0.11%
(t +0.74, n indep 3,589):

1. Positive and above the rule it replaces — **pass**, +1.30% against +0.11%.
2. |t indep| >= 2.5 — **fail, 2.47.** Short by 0.03.
3. Positive in both halves — **pass, in the strong form**: +0.85% (t +1.33) then +1.77%
   (t +2.09). It is the only cohort measured in this repo that is *better* in the second
   half, which is the opposite of the pattern every rejected variant shows.
4. Survives dropping its best year — **pass**: positive in 9 of 11 years, worst −2.05%
   (2020), and still positive without 2021.
5. n indep >= 500 — **fail, 223.**

It was shipped anyway, on the owner's instruction, to make the published list short enough to
be read: the price-only rule put ~46 names on the daily page against 1 for the reversal, and
this leaves about 2. The decision was taken knowing both failures.

**What this does not change.** The bar stands as written for everything else, and in
particular:

- **t >= 2.5 is not now 2.4.** Rules 2 and 5 were not lowered, amended, or re-scoped. One
  variant was shipped in spite of them, which is a different act from moving them, and the
  next candidate is measured against the original numbers.
- **Rules 2 and 5 are in permanent tension with a short list, and that is now explicit.** At
  a 20-bar horizon the per-signal standard deviation is ~8–9%, so t >= 2.5 at n = 500 needs
  alpha near +1.0%. A gate selective enough to leave 2–3 names a day cannot also leave 500
  independent events in twelve years. Any future request for a quieter screener runs into the
  same wall, and the answer is a judgement call, not a measurement.
- **It is on probation, forward.** The gate fires ~4% as often as the rule it replaced, which
  is roughly 25 independent signals a year across the S&P 500. `research/measure.py` re-run on
  the pinned universe is the check: if the second-half result that justified this does not
  hold up as live signals accumulate, 1.7.0 is reverted to the price-only rule rather than
  defended.

## Rule 8, for an allocation method (written 2026-10-20, before HRP was measured)

Source: `davidalmeida90/quant-models` (hierarchical risk parity, risk-based allocation). These
methods do not pick entries; they split money across names already held. The question is
whether any beats equal weight (EW) on the same universe, after costs. Universe: S&P names
in `research/.cache` with full 12y history (survivorship-biased; it flatters every method
equally, so the comparison, not the level, is what counts). Monthly rebalance, 252-day
lookback, 10 bps per side on turnover. Candidates: IVP, HRP, HCAA, min-variance, vs EW. Five
candidates against one baseline, so the bar is set for multiple testing.

A method is adopted only if **all five** hold, measured on monthly net return *difference* vs EW:

1. **Sharpe higher than EW** net of costs, and the difference has **|t| >= 2.5** (monthly
   differences, 12y, n about 140).
2. **Positive difference in both halves** of the sample.
3. **No single year carries it**: drop the best year, difference stays positive.
4. **Max drawdown no worse than EW.**
5. **Turnover cost below half the gross improvement.**

Fail goes in `research/FINDINGS.md` as measured-and-rejected, not retried with another
lookback or linkage. A low-vol tilt that only beats EW by holding less beta is not an
edge: report beta to EW alongside, and discount accordingly.
