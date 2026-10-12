# Signal-timing analysis — the pick lock

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

## 29. Signal-Timing Analysis — the pick lock, and the "all picks" evaluation rule
### 29.1 THE EVALUATION RULE (applies to every future analysis)

**Any analysis of model performance, thresholds, or signal timing MUST evaluate every
scored pick — `BET`, `AVOID`, and dead-zone `NONE` alike — not just `BET` rows.**
A `BET`-only sample only contains picks that already cleared the live bar, so it is
systematically optimistic and it cannot see the population a looser cut would draw
from. This is the same lesson as the session-68 full-outcome sweep (the `BET`-only
sweep overstated `mlb_moneyline` at +29% on 23 bets; the full-outcome sample said
+4.1% on 50) and it is why `mv_scored_pick_outcomes` (§113) grades the whole universe.

Four coverage traps to check BEFORE trusting any such analysis:

1. **`NONE` rows did not always exist.** They were only introduced 2026-05-12
   (session 16). Anything before that date has no dead-zone rows to grade.
2. **`NONE` rows were DELETED for ~6 weeks.** The retired `step_cleanup_picks`
   started-game prune destroyed dead-zone rows from ~2026-06-26 until it was retired
   2026-08-09 (session 114). **July 2026 has literally zero `NONE` rows for every MLB
   model** — verified. A sweep over that window silently sees only `BET`+`AVOID`.
   **Clean windows for full-universe work: 2026-05-12 → 2026-06-25, and 2026-08-09 →
   present.** Re-verify this by month before any new sweep — do not assume.
3. **Some games have NO row at all.** `_make_pick` returns None (writes nothing) when
   `abs(edge) > MAX_EDGE_CAP` (0.20), so a game where the model wildly disagrees with
   the market on both sides is absent entirely and its `model_probability` is never
   persisted. Measured share of DK-priced games with zero rows, clean windows:
   `mlb_moneyline` 8.3%, `mlb_f5_moneyline` 7.4%, `mlb_over_under` 7.2%,
   **`mlb_runline` 35.3%**. Only a model re-run can recover those probabilities.
4. **Player-prop `NONE`/`AVOID` rows are a survivor sample from 2026-08-30.** Two
   clears in the game scorer took them, and the 2026-10-12 fix closes only the first:
   - **The 30-second pre-game line poller** (shipped 2026-08-30) re-ran the game
     scorer on any game whose line moved, and that scorer's clear took every prop
     no-bet row on the game. The prop scorers did not run again before the start
     unless a refresh pass did. **Fixed once the 2026-10-12 change is running on the
     pollers service**: the poller now clears game-level rows only
     (`run_scorer(game_models_only=True)`).
   - **A refresh pass still clears a game that starts while the pass is running**,
     and the prop scorers then usually skip it as started, so those rows are still
     lost (WNBA_2026-10-09_ATL_NY: 91 rows, 2m48s after its start). Exempting such a
     game was tried and withdrawn because it is not bet-neutral. The odds feed
     pushes a start back around first pitch or tip, the poller writes that into
     `games.commence_time` every 30 s, and the prop scorers re-read it and score the
     game as pre-game. A kept `NONE` row would then hold that player under the prop
     lock, where today's clear frees him to become a BET. Measured 2026-10-12, games
     with picks dated 2026-10-01 → 10-12: the stored start is later than the
     earliest start stamped on the game's picks for 12 of 20 MLB games (10 by more
     than 5 min, at most 15 min) and 8 of 8 WNBA games (3 by more than 5 min, at
     most 7 min). Closing this neutrally needs a start the feed cannot revise.

   Measured 2026-10-12 from `picks` and `games`: of 18 MLB games 2026-10-01 → 10-11,
   **10 ended with zero prop no-bet rows** (the other 8 kept 131–146 each), and **all
   10 WNBA games** in that span ended with zero. Which games survived depends on
   whether a line moved after the last pass, and on whether a pass straddled the
   start, so the survivors are not a random sample. Prop BET rows were never touched
   by either clear.

   **One narrow cost of the fix, disclosed because it can change a bet.** The
   refresh pass's own clear, which runs right before every prop step, is what frees a
   prop player held at `NONE`. If a pass reads a game as already started (so its
   clear skips it) and the feed then pushes the start back before that pass's prop
   step, a poller tick in between used to free the game's prop players for that
   step. Now they stay held until the next pass's clear, or for good if the game
   starts first. The same applies if the pass's end-of-run clear gives up on its
   10 s lock wait (0 times in the worker's logs 2026-10-05 → 10-12, 352 scoring
   runs) or the scoring step fails outright (0 of 663 scoring steps
   2026-09-28 → 10-12 in `pipeline_log`). Production has not been searched for a
   case where this cost a bet.

### 29.2 Analysis: does the daily pick lock cost us signals? (2026-08-23)

Question (Matt): game picks lock at the first run of the day (§ session 75), so a game
that only enters BET criteria later in the day is never picked up. Are we losing bets
that would help the record — and is the opening line even the right number to lock?

**Method.** Rebuilt every pre-game DraftKings snapshot (~45 per game per market; avg
**11.3 hours** between lock and first pitch) and re-scored both sides at every snapshot
at current thresholds. Universe = all `BET`+`AVOID`+`NONE` rows per §29.1, restricted to
the clean windows. Exactness: `mlb_moneyline` / `mlb_f5_moneyline` are line-independent
(no odds-derived feature), so the recompute is exact; `mlb_over_under` uses `total_line`
as a top-6 feature so snapshots were restricted to price-only moves (the line itself
moves in **53%** of totals games — those are NOT evaluable without a model re-run).
Validated first: implied-prob, edge and grading reproduce stored picks with **0
mismatches on 344 settled bets**, and baselines reproduce `v_model_full_outcome_record`
exactly (F5 194 bets / 104-67-23 / 4.84u; O/U 19 / 12-7 / 4.04u).

**Result — the lock costs almost nothing.**

| Model | Locked baseline (clean windows) | "Match at any point" would ADD |
|---|---|---|
| `mlb_f5_moneyline` | 128 bets, +4.7% | +3 (3-0, +1.42u) |
| `mlb_moneyline` | 10 bets, +17.7% | +2 (1-1, −0.37u) |
| `mlb_over_under` | 12 bets, +27.8% | +4 (3-1, +1.61u) |
| `mlb_runline` | 11 bets, −2.3% | 0 — **but see the 35% blind spot, treat as unproven** |

9 incremental bets in ~2.5 clean months (43 across the full season including the
corrupted window). Their ROI at that sample is **noise — do not read it as a result.**

**The durable finding is the mechanism, which is not sample-dependent.** Of all 43
incremental bets, **43 arose from the price drifting AGAINST our side; zero from it
drifting toward us** (avg −1.8pp F5, −2.1pp ML). This is structural: after the lock,
edge only rises when our side gets cheaper, i.e. when the market is moving off it. An
"any point in the day" rule is therefore a machine for buying sides the market is
fading — adverse selection by construction.

**Is the opening line the better number? No — it is neutral.** Captured CLV:
`mlb_f5_moneyline` avg **+0.12pp** (of lines that moved, 46 beat the close vs 29 worse),
`mlb_over_under` **−0.08pp** (17 vs 22), `mlb_runline` **−0.14pp**. There is no opening
edge to protect and none to chase by waiting. Consistent with session 75's finding on a
much larger sample.

**DECISION: keep `LOCK_GAME_PICKS_AT_FIRST_RUN = 1`.** Upside is ~2–4 bets per model per
month, the selection mechanism is adverse, and unlocking would reintroduce the board
churn sessions 75/78 deliberately removed.

### 29.3 Open items / future research

- **`mlb_runline` is genuinely unanswered.** 35.3% of its games have no stored row
  (edge cap), and that invisible population is precisely the one that could produce
  *favorable*-drift crossings (a capped game re-enters range only when the price moves
  TOWARD us). The "adds 0 bets" result above does not cover it. Answering it needs a
  model re-run over historical snapshots, not a SQL simulation.
- **`mlb_over_under` when it unpauses** (after the `docs/health_checks.md`-flagged July-inclusive retrain):
  it is the only model where added volume was material vs its baseline (+4 on 12). A
  real answer needs the model re-run on moved lines — 53% of totals games are excluded
  from the price-only simulation.
- **A model re-run harness would close all three gaps at once** (edge-capped games,
  moved totals lines, runline). Rough shape: replay stored DK snapshots through
  `build_features_for_game` + `load_model`, persisting `model_probability` per snapshot.
  This is the single highest-value tool for any future signal-timing question.
- **Prospective alternative:** `opening_signals` (`docs/opening_signals.md`) already locks the first BET cross.
  Extending it to also log near-miss games (prob above bar, edge below) would answer
  this forward-looking with no simulation and no blind spots.
- **Do not re-sweep thresholds on July 2026 data** until the §29.1 trap 2 window is
  accounted for.
