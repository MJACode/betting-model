---
paths:
  - "config.py"
  - "models/**"
  - "scripts/paused_model_assessment.py"
  - "scripts/void_picks.py"
  - "data/threshold_sync.py"
  - "nfl/live_model/**"
  - "docs/thresholds.md"
  - "docs/paused_model_assessment.md"
---

# Model updates — attribution and scope

> **Path-scoped rule file.** It loads into context the moment Claude opens a
> file matching the paths above, and costs nothing on a session that never
> touches them. Moved out of CLAUDE.md on 2026-09-12, verbatim — the rule is
> unchanged. CLAUDE.md keeps a one-line pointer so a session that never opens
> these paths still knows the rule exists.
>
> **A rule only belongs here if it can ONLY be broken by editing one of these
> files.** Anything reachable without opening a file — pausing a model, running
> SQL, answering a question — must stay in CLAUDE.md, or it will not load for
> the session that breaks it. That is not hypothetical: a pause erased 55
> settled bets on 2026-09-12, and that session opened none of these paths.
> Measured story: `docs/rules_evidence.md`.

**EVERY MODEL UPDATE IS STAMPED WITH WHO ASKED FOR IT — `mike` or `matt`.**
(Repo-level rule, 2026-08-29.) Six months later "why is this model paused?" is
unanswerable if the commit does not say whose call it was, and threshold sweeps
get re-litigated constantly — the person is part of the evidence.

The stamp is a **git trailer on the commit** that lands the change:

```
Updated-By: mike
```

It goes on the branch commit, so it survives the squash-merge into master and
is greppable forever (`git log --grep="Updated-By: matt"`).

**What counts as a model update** — anything that changes what a model does or
whether it fires:
- a retrain, or a `model_registry` version swap / rollback
- a threshold change in `MODEL_PROB_THRESHOLDS` / `MODEL_EDGE_THRESHOLDS` /
  `ACTION_THRESHOLDS` / `MODEL_MIN_ODDS`
- a pause or unpause (`PAUSED_MODELS`)
- a feature-list change, a new model, or a retired one

**Not** a model update: cadence, plumbing, notifications, mobile UI, docs. Those
do not need the trailer.

**If you do not know whose call it is, ASK before committing.** Guessing an
attribution is worse than none — it puts a decision in someone's mouth. Where a
session's own user is the one directing, that is the name; where they are
relaying ("Matt wants…"), the name is the originator, not the relayer.

**A CHANGE TO HOW ONE MODEL OPERATES IS ASSESSED AGAINST ALL OF THEM.**
(Repo-level rule, 2026-08-29.) Before shipping an operational change — how a
loop prices, what it records, how it locks, what it publishes — ask whether the
other models, sports, or publishing surfaces want it too, and say so either way.

The test is mechanical: *if this had been a problem in sport X, would we have
noticed?* If the answer is "only after someone questioned a number", the change
belongs in shared code, not in one loop. Prefer a sport-agnostic helper the
loops call over a per-sport implementation — `data/ingestors/live_price_log.py`
is the shape.

This applies to model MECHANICS, not to model CUTS: a threshold is measured per
model on its own record and must never be copied across.

**Live player props are a priority and an UNTESTED HYPOTHESIS — not a proven
market.** (Downgraded 2026-09-03 by mike, after measurement.) The thesis: NOT
beating line movement, but a statistical model for live prop over/unders priced
RELATIVE TO THE STARTING LINE. The book re-anchors its live line mechanically
off the pregame number and the clock; the edge is predicting where true
remaining production deviates from that. Do not rebuild a player projection
from scratch and throw the pregame line away. Detail: `docs/live_betting.md`.

**The settled live-prop record is ZERO BETS — there has never been a live
player prop model in production, and the ~400 settled picks that look like one
are not.** Do not read them as evidence in either direction
(`docs/rules_evidence.md`).

> **Not here on purpose:** *everything goes in Supabase* and *a losing
> model is an assessment to run* stay in CLAUDE.md §1b. Both are reachable
> without opening any file here — the second is answered in chat — and
> `tests/test_everything_in_supabase.py` and
> `tests/test_paused_model_assessment.py` assert they are there.
