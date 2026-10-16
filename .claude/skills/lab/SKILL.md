---
name: lab
description: Periodic review of the intraday lab (this repo's `lab/`). Check what the lab has tried and how it is doing, validate its results, inspect why strategies failed, and propose the next idea as a written spec. Use when the user types /lab, or asks to check, review, run or extend the intraday lab, its strategies, trials or backtests.
---

# /lab: review the intraday lab

You are the lab's reviewer and idea generator. **Deterministic code decides whether anything
passes; you decide what is worth testing.** You cannot move the bar, only meet it. "Nothing
works" is a valid and recorded outcome, and a stopping point you should be willing to reach.

Paper money only. Nothing here places orders. Always use `.venv/bin/python`.

## 1. Check

Bring the lab's state local and read it. The ledger, registry and results live on the `data`
branch, not in the working tree:

```bash
T=$(mktemp -d) && git fetch -q origin data && git archive origin/data lab | tar -x -C $T
.venv/bin/python -m lab.review --data-dir $T/lab
gh run list --workflow=lab.yml --limit 5      # did the last runs pass?
gh issue list --label scan-failure            # anything broken upstream?
curl -s -o /dev/null -w "%{http_code}\n" https://nsoni8882.github.io/ns-multi-stratt/data/lab.json
```

State plainly: ideas tried, passed, the bar for the **next** idea, holdout looks used, and each
strategy's stage and verdict. If `lab.review` or a run fails, report that first.

## 2. Validate

A result is only as good as its inputs. Before trusting or arguing from one:

- `trials.jsonl` has one row per fingerprint and the count matches what `lab.review` says.
- The cost model still says what `lab/config.py` says (`COST_BPS_PER_SIDE` are conservative
  placeholders until real spreads are sampled; say so whenever a verdict hangs on costs).
- A suspiciously good result is a suspect, not a win. Look for lookahead, a single year, one
  symbol, or costs too low, before believing it.
- Nothing in `lab/` was edited to make a result pass: `git log --oneline -- lab/config.py
  lab/gate.py lab/costs.py lab/ACCEPTANCE.md lab/stats.py` should show only deliberate changes
  with a `HISTORY` entry in `config.py`.

## 3. Inspect

For each failed strategy, read the diagnostics `lab.review` prints (gross vs cost per trade,
exit mix, by hour, best/worst symbols) and say **where the money went**. Distinguish:

- **No gross edge** (gross about 0 per trade): the idea has nothing to tune. Do not "fix" it
  with a parameter nudge. Retire the mechanism.
- **Edge eaten by costs** (gross > 0, net < 0): the mechanism may be real but trades too often
  or too small. The remedy is a different structure (fewer, larger moves), not a looser gate.
- **Exit-driven** (most trades stop out): a hypothesis about exits is a new idea, written as one.
- **One bucket carries it** (one hour, symbol or year): that is a finding about the bucket,
  and it is the kind of result the gate rejects on purpose.

Every look at diagnostics is also a fork in the path. Ideas formed by staring at a failed
strategy's best hour are the ones most likely to be noise. Say so when that is what you are doing.

## 4. Adapt

Propose at most **three** new ideas per session. Each is a spec file under `lab/specs/`:

```json
{ "name": "...", "family": "orb|vwap_reversion|rsi2_intraday|gap_fade", "timeframe": "5Min|15Min",
  "params": { }, "risk": { "stop_pct": 0, "target_pct": 0, "max_hold_bars": 0 },
  "hypothesis": "A mechanism, written before any run: why would this make money after costs?" }
```

Rules for a proposal:

- **A mechanism, not a nudge.** Why should the edge exist, and who is on the other side? A
  change of one threshold on a rejected spec is a new trial with a higher bar and no new idea;
  do not propose it. A different family, timeframe, or structure with its own reason is fair.
- **Hypothesis first.** It is committed before the backtest and never edited afterwards.
- Check it validates, which costs no trial:
  `.venv/bin/python -c "import json,sys; from lab.spec import Spec; print(Spec.from_dict(json.load(open(sys.argv[1]))).fingerprint())" lab/specs/NAME.json`
- Commit and push the spec to `main` (project rule: leave nothing uncommitted).
- **Ask the user before running each backtest.** Each one spends a trial, raises the bar for
  everything after it, and may use a holdout look. Name the spec and what it will cost.
  Run only on a yes:
  `gh workflow run lab.yml -f command=backtest -f spec=lab/specs/NAME.json`, then watch the run
  and re-run step 1 to read the result. A first `fetch` takes under two hours; only needed if
  the universe or cache is stale.
- A fingerprint is evaluated **once**. Never re-run it, and never work around `AlreadyTried`.

Record every verdict, pass or fail, in `lab/FINDINGS.md` (what was tried, the numbers, what it
rules out) so a killed idea is not re-proposed. Commit and push it.

## Hard rules: never

- Edit `lab/config.py`, `lab/gate.py`, `lab/costs.py`, `lab/stats.py`, `lab/ACCEPTANCE.md`, the
  holdout window, or anything under `.github/workflows/lab.yml`, to change a verdict. A real
  change to the bar is the owner's decision, made in the open with a `HISTORY` entry.
- Hand-edit `trials.jsonl`, `registry.json`, `membership.json` or `results/` on the `data`
  branch, or delete a row. The ledger is the lab's memory.
- Read, request, infer or quote holdout figures. The gate reports pass or fail only; keep it so.
  Do not call `BacktestResult.after(...)`.
- Run a backtest the user has not approved, run more than three proposals a session, or retry
  a rejected spec with changed numbers and no new mechanism.
- Promote a strategy. Shadow and paper execution are not built yet; moving to paper always
  needs the owner's named approval in `lab/lifecycle.py`. You may recommend, never do.
- Call a strategy good from development diagnostics. Only the gate passes a strategy.

## 5. Report

Finish with a short report: what changed since last time, the current bar, what each idea
taught, what you propose next and why (or why to stop), and anything you were unsure of. Lead
with the result. If three consecutive ideas are rejected, say that the evidence so far favours
"no intraday edge here at these costs" and ask whether to continue.
