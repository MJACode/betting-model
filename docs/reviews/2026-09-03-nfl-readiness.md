# NFL health check — every lane, and readiness to operationalize

> Requested by Matt, 2026-09-03, with Pinnacle lines imminent.
> **Next kickoff is 2026-09-09** (from `nfl/data/games.csv`, 272 future games).
>
> Verification boundary: Supabase and Railway connectors are unauthenticated in
> this session, so **no live worker state, env-var value or deploy time was
> checked**. Everything below is from code, config, the offline preflight and
> the schedule file. The three things only Matt can confirm are in §6.

---

## The clock

`nfl_opener_spread` fires in a **T-7 to T-2 day window** before kickoff
(`opener_spread.py:LEAD_LO_DAYS/LEAD_HI_DAYS`). With first kickoff 2026-09-09:

```
  Sep 2  ────────── window OPENS
  Sep 3  ◄── TODAY
  Sep 7  ────────── window CLOSES
  Sep 9  kickoff
```

**The capture window is open right now.** The opener rule is a race — its own
docstring says *"the edge IS staleness, and waiting destroys it. There is
nothing left at the close."* So whatever is decided about this lane needs
deciding in the next few days, not next week.

---

## The five lanes (not twelve models)

| # | Lane | What it does | Status |
|---|---|---|---|
| 1 | `nfl_opener_spread` | bets a soft book where it disagrees with **Pinnacle's** opener by ≥1.0 pt | ⚠️ **READY BUT THE EDGE IS NOT ESTABLISHED** |
| 2 | `nfl_wind_totals` | UNDER on outdoor games, forecast wind ≥12mph | ✅ **READY** — the only NFL rule its own docs clear for live money |
| 3 | `nfl_prop_market` | de-vig **Pinnacle**, bet DraftKings' outlier at equal lines | ✅ **READY** — strongest evidence of the five |
| 4 | NFL in-play (pass attempts) | live prop lane on the volume-mounted worker | ⚠️ **READY AFTER a rebase completes** |
| 5 | 12 × `nfl_prop_*` projections | from-scratch player projections | ⛔ **PAUSED BY DESIGN — leave paused** |

**The offline preflight passes clean: `python -m scripts.nfl_preflight` →
44 passed, 0 failed, 0 warnings.** Models import, the per-bet probability curve
scales correctly, the insert-once locks are intact, both poll jobs are
registered, both cards run with `cwd=nfl/`, the schema splits, and the defective
books are excluded. The plumbing is in good shape. The problems below are about
*evidence* and *deployment*, not wiring.

---

### Lane 1 — `nfl_opener_spread` ⚠️ the one that needs a decision today

**This is the Pinnacle lane.** When Pinnacle posts, the card looks for a soft
book still sitting ≥1.0 point away from it and bets that stale number.

**The headline problem: the edge was restated downward on 2026-08-23 and the
sport doc never caught up.** Until I corrected it an hour ago,
`docs/sports/nfl.md` listed this strategy under *"What works (validated)"* at
**ROI +6.98%**. The model file itself (`nfl/models/opener_spread.py:22-40`) has
carried the corrected figure for eleven days:

| | old (3 seasons) | **restated (6 seasons)** |
|---|---|---|
| ROI | +6.98% [−0.6, +14.5] | **+1.34% [−3.9, +6.4]** |
| ATS excess | +5.78pp [+1.8, +9.6] | **+2.27pp [−0.6, +5.1]** |
| DK placebo | "no excess" | **+0.95pp [−1.7, +3.7]** |
| n | — | 1,178 |

A 27,300-credit scan added 2020-2022 at the same resolution and **all three
added seasons are negative**: 2020 −2.62%, 2021 −1.78%, 2022 −2.80%, against
2023 +4.72%, 2024 +10.86%, 2025 +0.32%. Both confidence intervals now span
zero, the placebo gap is "too small to call", and raising the threshold does not
rescue it (|dev| ≥ 2.0 → +2.63% [−6.3, +11.0] on n=356).

The preflight states the position honestly: *"opener edge is NOT established …
live by decision, Kelly-sized. Retire on a 2026 season at or below flat."*

**What is genuinely good here:** it is Kelly-sized rather than flat, a
juice-eaten quote is skipped rather than floored, the lock is insert-once, and
the monitor records whether conditions still hold without ever touching the bet.
If it runs, it runs safely. The question is only whether it should.

**Decision needed** — see §5.

---

### Lane 2 — `nfl_wind_totals` ✅ ready, and the strongest-founded

Bet the UNDER on outdoor games with forecast wind ≥12mph. The market moves the
total ~2.6 points across the wind range while actual scoring falls ~6.2, so it
prices about 40% of the true effect.

- Rule **frozen on 1999-2015, tested on 2016-2025**: 58.09% under on nflverse
  observed wind (n=408), 59.32% on ERA5 reanalysis (n=354) — two independent
  data sources agreeing.
- Under *measured* forecast error (298,944 forecast/reanalysis pairs, not an
  assumed Gaussian): day-3 lead, threshold 12 → **57.09% [52.4, 61.9], P(beat
  vig) 0.975**, ~38 bets/season.
- Edge decays ~0.41pp per day of lead; an uncalibrated lead sizes to **zero**
  rather than guessing.

This is a standing closing-line inefficiency, not a race — it can be placed any
time up to kickoff. Totals only; it is explicitly not a spread play.

**One caveat that is not in the numbers:** lane 2 shares a kill switch with
lane 1 (below).

---

### Lane 3 — `nfl_prop_market` ✅ ready, best evidence of the five

Take Pinnacle's price as the estimate of truth, de-vig it, and bet wherever
DraftKings disagrees by more than the juice. **+10.76% blind over 954 bets.**

- `min_edge = 0.05` is **pre-committed** — the config note records that a
  greedily-chosen 6pp went negative out of sample. That is the right discipline.
- Only **equal lines** are compared. Pinnacle at 5.5 receptions and DK at 6.5
  are different propositions, and the module's docstring names the exact prior
  incident where ignoring this manufactured a fake +13% over two seasons.
- **8 of 12 markets** — Pinnacle declines to quote rush attempts, rush+rec
  yards, sacks and tackles+assists. A market maker declining is itself
  information; those four stay unplayed.
- One pooled model id, not eight, because the validated number is pooled — per
  market splits were never validated at volume.
- Fires **hourly inside T-30h** of kickoff, ~61 credits per event.

This is the same construction that produced the NCAAF opener result (+10.9% over
1,050) and has since been ported to WNBA. It is the house's one repeatedly
validated edge class.

---

### Lane 4 — NFL in-play (pass attempts) ⚠️ blocked on a stopped rebase

The live worker supervisor runs 9am–midnight ET, every 10 minutes, and idles
free (no live game → no odds call). Credit burn during a slate is capped by an
in-worker meter.

**The blocker:** session 210 built an event-relative staleness guard
(`quote_predates_score`) after a live NCAAF total was bet **0.6 seconds after a
touchdown, against the book's pre-touchdown price**. The NFL half of that fix is
`nfl/live_model/executor.py` (+81 lines) and `data/live_quote_guard.py`.

**State as of the end of this session:** that work is now **committed** — commit
`2709c404` on branch `live-quote-score-guard`, **7 commits ahead of master**.
(It was stopped mid-rebase on conflicts for part of this session; that resolved
cleanly while the health check was being written — see §7.)

So the guard exists but is **not merged to master and therefore not deployed**.
Running the NFL live lane before that branch merges *and the worker redeploys*
means running without the protection built for exactly this failure — on the
same weekend the NFL season starts.

**Unblock: merge `live-quote-score-guard` to master, then redeploy the worker.**

---

### Lane 5 — the 12 `nfl_prop_*` projection models ⛔ correctly paused

`nfl_prop_pass_yards`, `pass_attempts`, `pass_completions`, `pass_tds`,
`rush_yards`, `rush_attempts`, `rec_yards`, `receptions`, `rush_rec_yards`,
`anytime_td`, `tackles_assists`, `sacks`.

**Plain version: these tried to out-predict the market from scratch, and lost in
11 of 12 markets.** That does not mean NFL props are unbeatable — it means our
projection is not better than the bookmaker's. Lane 3 replaced them with the
opposite construction (trust the sharp book, bet the soft one), and that works.

**Recommendation: leave all 12 paused.** Nothing has changed since the
measurement, and unpausing them would put projection-based picks on the board
beside the market-relative ones with no way for a user to tell which is which.

---

## 4. Readiness verdict

| Lane | Verdict |
|---|---|
| `nfl_prop_market` | **GO** — best evidence, pre-committed threshold, safe failure modes |
| `nfl_wind_totals` | **GO** — provided the shared kill switch is on (§6) |
| `nfl_opener_spread` | **DECISION** — plumbing ready, edge not established |
| NFL live | **GO AFTER** the rebase lands the staleness guard |
| 12 prop projections | **NO** — stay paused |

---

## 5. The opener decision, in plain terms

You have three options and there is no wrong answer — only a wrong way to
discover it later.

1. **Run it as-is, small.** It is Kelly-sized on a probability curve that is
   itself calibrated, so a weak edge produces small bets rather than the same
   bet as a strong one. The retire condition is already written down: a 2026
   season at or below flat and it goes. **This is the option the code was built
   for.**
2. **Run it paper-only for 2026.** Publish it to the board flagged as not
   live-money, collect a clean forward season, decide in January. Costs a season
   of upside if the edge is real; costs nothing if it is not.
3. **Stand it down for 2026** and keep the credits. Wind and prop_market are
   both better founded and neither depends on it.

**My recommendation is option 1 or 2, not 3** — because the lane is a race, and
standing it down means you cannot even *measure* it this season; there is no
closing number to reconstruct the bet from later. Between 1 and 2, the honest
read is that this is a coin-flip-with-a-tilt: three good seasons, three bad
ones, and a placebo you cannot distinguish from the signal. If NFL is meant to
carry real money this season, wind and prop_market are the lanes to carry it.

---

## 6. What only you can confirm (and it is urgent)

**`RUN_NFL_WIND_CARD` controls BOTH the wind card and the opener card.** It
gates `run_nfl_poll` (`scheduler.py:995`), and that one function runs both
(`scheduler.py:547-548`). The variable name only mentions wind.

**Why this matters right now:** session 172 (today) found the wind card had been
failing on *every* run. If that failure was ever silenced by setting
`RUN_NFL_WIND_CARD=0`, then **the opener capture is off too — during the exact
window that is open today.** The preflight flags the same coupling: *"RUN_NFL_WIND_CARD
gates all NFL jobs."*

Three checks in the Railway dashboard (service → Variables, then Deployments):

1. **`RUN_NFL_WIND_CARD` — is it `1`?** If it is `0`, wind *and* opener are
   both dark.
2. **Has the worker redeployed since session 172's wind-card fix landed?**
   Railway only picks up code and variable changes on redeploy, so a fix
   committed today is not running until then.
3. **`THE_ODDS_API_KEY` or `ODDS_API_KEY` set?** Without either, the wind card
   silently runs `--dry-run` and the opener card no-ops. Also worth a glance at
   `odds_api_quota` before the season starts — the poll costs ~96 credits/day in
   season, plus ~72 per kickoff cluster in the fast window.

Authorizing the Railway and Supabase connectors (claude.ai connector settings,
or `/mcp` in an interactive session) would let me check all three directly
instead of asking.

---

## 7. Git state — resolved, but read this before committing

For part of this session an interactive rebase of **`live-quote-score-guard`**
was **stopped on merge conflicts** in `docs/sessions/2026-09.md` and
`docs/sessions/README.md` (session 211's log entry against session 210's — a
docs collision, not a code one), with HEAD detached. **Because of that, every
change made in this session was written to the working tree only and nothing was
staged**, so nothing could be swept into someone else's commit.

**It resolved cleanly while this document was being written.** Current state:

```
branch : live-quote-score-guard  (7 commits ahead of master)
HEAD   : 2709c404  Decline a live quote the book stamped before the score...
markers: none remaining in either session-log file
```

Both session entries survived the resolution.

**Two things to know before the next commit:**

1. **You are on `live-quote-score-guard`, not master.** This session's file
   changes are unstaged on top of that branch. They are unrelated to the live
   guard, so they want their own branch and their own commit — not a fold into
   210's work.
2. **Two stray temp files sit at the repo root**, `_t_s211.md` and `_t_mine.md`,
   which look like conflict-resolution scratch. They are not mine and were left
   untouched — worth deleting once you have confirmed they are spent.

No `Updated-By:` trailer is needed for any of this session's changes: nothing
here changes what a model does or whether it fires. **The opener decision in §5
does need one when it is made.**

---

*Written 2026-09-03. **The health check itself is read-only** — no live system was
touched and no credits were spent. The same session also carried out Matt's
approved fixes and archiving (both `nfl.md` corrections, 12 dead files removed,
4 plan docs moved to `docs/history/`, 6 inbound links repointed); the full file
list is in the session-212 log entry. **Nothing was staged and no git command
was run** — every change is an unstaged working-tree edit, because the tree
began this session mid-rebase.*
