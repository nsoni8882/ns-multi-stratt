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
