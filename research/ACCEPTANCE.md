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
