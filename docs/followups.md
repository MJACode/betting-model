# Follow-ups

> **Janitor's worklist.** The durable backlog: Janitor (see `docs/agents_contract.md`)
> takes one item from here every morning, and a human can add to it any time.
>
> **Why a file:** a task list that lives only in a chat is gone the moment the
> session ends. Four small fixes below were flagged in three separate sessions
> and never done, because each time they lost to a larger ask and nothing
> carried them forward. Same reasoning as CLAUDE.md §1b.
>
> **Format:** one `## Item` per task. `[needs-decision]` means blocked on a
> human and the agent must skip it. Tick with `- [x]` and leave it in place for
> one week so a reader can see what recently changed, then delete.

---

## [x] `commence_time` is ~16-20 minutes LATER than the actual first pitch

**Done 2026-09-01 in session 166** — `data/first_pitch.py`, `games.first_pitch_at`,
the COALESCE at all three guard sites, and two queued jobs to derive and repair.
The open question (feed artefact vs genuine drift) is unchanged and still needs a
timestamped play source.

mike, 2026-09-01: "should be commence time." He is right, and the direction is
the opposite of what I assumed when I raised it.

Measured over the 413 games with live state coverage (2026-07 onward): the first
`live_game_state` row with `abstract_game_state='Live'` lands on average **19.5
minutes BEFORE** `games.commence_time`, median 15.9 minutes before. Only 4 of
413 games began after their commence_time.

So the boundary every pre-game read uses -- `snapshot_at <= commence_time`, the
§7 rule -- is systematically too late, and odds rows inside that window are
treated as pre-game while the game is already under way. This is a leak in the
PERMISSIVE direction, and it is the explanation for the 48,712 rows labelled
`in_play` by the live loop (correctly, from game state) whose timestamp is at or
before their commence_time.

What to build:
- `games.first_pitch_at`, derived from `MIN(snapshot_at)` over
  `live_game_state` where `abstract_game_state='Live'`, per game.
- Make the pre-game guard prefer it: `COALESCE(first_pitch_at, commence_time)`.
  `features/feature_engine._is_pregame_snapshot` and
  `features/market_movement.load_market_movement` are the two call sites, plus
  `data/ingestors/odds_ingestor._mark_in_play`.
- Do NOT overwrite `commence_time`. It is the scheduled time, the app shows it,
  and the schedule is the right thing to show.
- Coverage is 2026-07 onward only, so `first_pitch_at` will be NULL for
  everything older. The COALESCE handles that, and the guard already fails open.

Whether the ~19-minute gap is a feed artefact (the API marking a game Live
during warmups) or a genuine commence_time drift is worth one query before
building: compare `first_pitch_at` against the first PLAY, if a timestamped
play source can be found. `plays` carries no timestamp today.

## [ ] Market-aware MLB model, now trainable on three seasons instead of one

Blocked until the 2024/2025/2026 historical backfill finishes (declared jobs
`mlb-history-2024`, `-2025`, `-2026-preaug`; watch `odds_history_pulls`).

`features/market_movement.py` computes nine columns and NO model consumes them.
Before 2026-09-01 that was forced: movement existed for 1,906 MLB games, all in
2026, disjoint from where the game models train. The backfill removes that
constraint -- 2024, 2025 and 2026 at two snapshots a day across seven books.

The plan is in `docs/market_movement_features.md` and one thing in it is now
out of date: it says "a new model trained on 2026 alone". It should be
2024-2026, with a chronological split, compared against the incumbent on the
same games.

Check coverage per season before training. A season where the backfill hit its
credit cap is a season with a hole in it, and `stopped_early` in the job result
says so.

## [ ] Opposing-starter retrain, as a cloud job rather than a handover

`docs/activate_opp_starter_features.md` has the patch and the runbook, and it
has been "run these five commands on your machine" for a day. It should be a
`retrain_model` declaration in `jobs/declared_jobs.json` -- the queue exists
now, and `model_artifacts` means the resulting `.pkl` survives the container.

Order matters and the runbook has it: baselines FIRST (register=false, seasons
2020-2024, holdout 2025, current features), then apply the patch, then the real
runs. Comparing a patched model against the artifact in the repo measures two
changes at once.

## [ ] [needs-decision] `DATAGOLF_API_KEY` is not set on either Railway service

Golf has been silently skipping on every pass — `Golf: DATAGOLF_API_KEY not set
— skipping golf step`, three times per refresh (ingest, ingest, scorer). The
variable is absent from both the `worker` and `pollers` variable lists, though
CLAUDE.md §6 lists it as a worker secret, so it was dropped rather than never
added.

This is a SEPARATE outage from the 2026-08-31 database break and predates it.
Found while diagnosing that one; not fixed here because only Matt can supply
the key, and whether the golf models should be running at all right now is his
call, not an agent's. Evidence: worker deploy logs, any refresh pass.

## [ ] `nhl-api-py` is not installed on the worker

Every pass logs `nhl-api-py not installed — run: pip install nhl-api-py
--break-system-packages`, so the NHL results step warns and does nothing. Out
of season, so it costs nothing today — and that is exactly why it will still be
broken in October if it is not fixed now. Belongs in the image's requirements,
not in a hand-run pip. Found 2026-08-31.

## [ ] An off-platform pinger, so both containers dying is not silent

`tracking/heartbeat_watchdog.py` (2026-08-31) runs on every service role
precisely so one container can report the other's death, but it is still hosted
inside the system it watches: losing both at once is silent. Closing that needs
something outside Railway — a cron on Matt's machine, or an uptime service
hitting the monitor's `/healthz` — that alerts on the ABSENCE of a heartbeat
rather than on an error. Documented in `docs/monitoring.md` under "What it still
does not cover".

## [ ] Stop pulling the NHL 3-way market out of season

`h2h_3way` is fetched per NHL event on every pass and returns **422 on every
one** — 32 wasted round trips per pass, ~1,300 a day. Credits are not charged
on a 422 (verified), so this is latency and noise rather than money, but it is
also 32 lines of error in every pass log, which is how a real error gets
missed.

Gate the per-event 3-way fetch on the sport being in season, the same way
`PREGAME_POLL_SPORTS` already excludes NHL. Flagged 2026-08-30, three times.

## [ ] `run_ledger finish` swallows its own errors

`python -m tracking.run_ledger finish ... 2>/dev/null || true` in
`scripts/refresh_pass.sh`. So a pass that COMPLETED but failed to write its
finish row is later marked `aborted` by the next run, and "aborted" therefore
means either "the pass died" or "the bookkeeping call failed" — two very
different things that cannot be told apart.

This actively cost diagnosis time on 2026-08-30: four passes were investigated
as hangs when at least two were deploy restarts. Keep the `|| true` (a ledger
must never break the pass it observes) but log the failure somewhere visible
instead of `/dev/null`.

## [ ] Settle is step 24 of 28, so it is the first thing lost

Grading and the daily recap sit near the end of the chain. On 2026-08-30 four
passes died mid-chain and the corrected recap went unposted for five hours,
while odds — step 2 — kept updating fine.

Settle genuinely must follow the results ingests, so this is not a reorder.
The fix is to make the record not depend on a pass surviving to the end: a
small settle-and-recap entry point that can run on its own, or a late-day
guarantee pass that does only that.

## [ ] One leaked database connection

`pg_stat_activity` showed a connection idle for 1 day 20 hours. Harmless at
this scale — `data.db.get_connection()` does not pool, so one leak is one
connection — but it is a leak and it will not be the last. Find the caller
that does not close.

## [ ] Batter props never get a best price stamped

Zero August `mlb_prop_batter_*` BETs carry `best_odds`, while
`mlb_prop_pitcher_k` carries 6 of 18. So it is a live code-path bug, not
missing plumbing: the books are configured, all three append sites in
`run_batter_prop_scorer` tag `_best_ctx`, and **1,726 of 1,783 DK batter-prop
quotes (97%) have a same-line match at another book**.

Leading hypothesis, unverified: the prop lock freezes a pick at first signal,
so one written before best-price stamping shipped is never re-stamped. Needs a
reproduction against real rows — the dev sandbox has no `DATABASE_URL`, so run
it locally or on the worker.

Worth real money: on props, **1 in 3 has 1–30 cents available elsewhere and 1
in 16 has 30+**.

## [ ] Surface the best book in Discord and the betslip

Depends on the item above. mike, 2026-08-30: *"the bet should pick the best
line for the bettor, across the main books, not just DK."*

Display and betslip only. The models keep DECIDING on DraftKings — every
threshold was swept on DK-implied edge, and best-of-N prices ~2pp cheaper in
implied probability, so adopting it as the qualifying price would loosen every
cut by that much with nobody deciding to (CLAUDE.md §6).

## [ ] [needs-decision] Re-sweep `mlb_live_total_runs` at ~50 settled picks

17 settled as of 2026-08-30. A threshold move needs a named human under §1b,
so an agent may prepare the sweep and report it but must not ship the cut.

## [ ] [needs-decision] Live odds feed

Measured 2026-08-30 against a direct DK capture: the Odds API lags DK's in-play
number by a median **54s**, worst **210s**, and missed two lines entirely
inside one 80-minute window. Polling faster cannot fix it — the staleness is on
their side.

Options are a vendor with a real publish clock (OddsPapi free tier, TheRundown
~$49/mo) or accepting the lag. Blocked on mike; needs a spend decision.

## [ ] Backtest a best-line decision basis

The honest version of "does a model rebuild improve things": re-score history
with best-of-N as the qualifying price and compare against the DK-only record,
per model, with the thresholds re-swept in the same pass.

Preliminary evidence says it will NOT help game lines — on 319 settled BETs, DK
was best or tied on **316**, and units at DK equal units at the best price
exactly. Props are the open question.

Substantial: a session's work, not a corner of one.
