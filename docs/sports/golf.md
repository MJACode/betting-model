# GOLF — pipeline operations

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

## 22. GOLF — Pipeline Operations
Golf is the 4th sport (MLB | WNBA | UFC | GOLF in the global toggle). Scope: ALL
weekly PGA Tour events; markets = outright winner, top-10, top-20, make-the-cut,
tournament head-to-head matchup. **All five price against real DraftKings odds**
— DataGolf's betting-tools feed carries DK lines for every weekly event, so unlike
WNBA ML / UFC method, no golf market is prob-only.

### Data source — DataGolf Scratch Plus (NOT The Odds API)

One API key (`DATAGOLF_API_KEY` in `.env` / repo secret) unlocks everything:

| Endpoint | Used for |
|---|---|
| `/get-player-list` | `golf_players` (dg_id ↔ name ↔ slug) |
| `/historical-raw-data/event-list` + `/rounds` | round-level scoring + strokes gained since ~2017 → `golf_rounds` (the training backbone) |
| `/field-updates` (+ `/get-schedule`) | the week's field → `games` + `golf_tournaments` rows |
| `/betting-tools/outrights?market=win\|top_5\|top_10\|top_20\|make_cut` | live DK odds → `golf_odds` |
| `/betting-tools/matchups?market=tournament_matchups` | live DK matchup odds → `golf_odds` |

The Odds API is **not** used for golf (it only carries the 4 majors, outrights only).
All DataGolf calls run from GitHub Actions (paid keyed API — no residential-IP
constraint like nba_api/ufcstats).

### Models (registered; trained on Matt's machine after backfill)

| Model ID | Market | Target | Type |
|---|---|---|---|
| `golf_outright` | win | finish_pos == 1 | binary XGBoost+Platt; ~0.7% base → scale_pos_weight; **field renormalization** at score time |
| `golf_top10` | top_10 | finish_pos ≤ 10 | binary |
| `golf_top20` | top_20 | finish_pos ≤ 20 | binary (separate model, not derived) |
| `golf_make_cut` | make_cut | made_cut == 1 | binary (skipped for no-cut signature events) |
| `golf_matchup` | matchup_tournament | A beats B | binary on sampled historical pairs, diff-features |

Features (`features/golf_feature_engine.py`): rolling strokes-gained (last 8/24
rounds, by component), form delta, recent finishes, made-cut rate, course history
(same event prior years), field strength, days since last event — all ASOF
**strictly before** the tournament start. `MIN_GOLF_ROUNDS = 20` history gate.
Outright win probs are renormalized across the field (`renormalize_field_probs`)
before pricing — independent binaries don't sum to 1 over a 150-man field.

### Conventions (load-bearing)

- **One `games` row per tournament:** `game_id = GOLF_{start_date}_{event_slug}`,
  `sport='GOLF'`, `home_team` = event name, `away_team = 'FIELD'`, scores stay NULL.
  Per-player picks FK to it and carry `picks.player_id = str(dg_id)` + a
  self-describing `pick_label` ("Scottie Scheffler Top 10" / "Scheffler over McIlroy
  (matchup)"). This is the MLB-prop pattern, not the UFC pseudo-game pattern.
- **Settlement** (`_settle_golf_picks`, trailing 14-day window): from `golf_rounds`.
  Top-N **ties settle at full price as a win** (v1 — no dead-heat reduction;
  documented caveat, revisit before go-live). make_cut WD-before-cut → NO_ACTION.
  Matchup opponent recovered from `golf_odds`. Generic settle + CLV exclude `golf_%`.
- **Team events** (Zurich Classic) excluded via `GOLF_TEAM_EVENT_MARKERS`.
- `GOLF_SCORE_AHEAD_DAYS = 7` — tournaments are scored up to a week early (UFC
  look-ahead pattern; delete+rescore unstarted picks each run).

### Pipeline (rides existing crons; no-ops off-weeks)

`step_golf_results` (before settle, step 0b) → `golf-field` + `golf-odds` (after
WNBA odds) → `golf-scoring` (after WNBA prop scoring). Hourly refresh runs
`golf-field`/`golf-odds`/`golf-scoring`. CLI: `--step golf-field|golf-odds|golf-results|golf-scoring`.

### Mobile

Golf picks render player-first (the event name as the subtitle, not "A @ B").
Stats tab shows a "leaderboards coming soon" empty state for golf v1. The
`docs/mobile_picks_prompt.md` mobile SQL filters `game_date = today`, so on Claude-mobile chat golf
picks appear on the tournament's start day only (same date-range gap UFC has —
add a date-range OR if pre-tournament picks are wanted there; the app itself uses
`fetchUpcomingGolfPicks` and shows them up to 7 days early).

### First-time setup (Matt's machine — pending DataGolf subscription)

```bash
# 0. Verify endpoint shapes + historical-odds archive tier (read-only)
python -m scripts.verify_datagolf

# 1. Historical backfill (~40 events/yr × ~150 players × 2–4 rounds, 2017–2025)
python -m data.ingestors.datagolf_ingestor --backfill 2017 2025

# 2. Train (binary XGBoost+Platt; golf_outright auto-gets scale_pos_weight)
python -m models.trainer --model golf_top10
python -m models.trainer --model golf_top20
python -m models.trainer --model golf_make_cut
python -m models.trainer --model golf_outright
python -m models.trainer --model golf_matchup

# 3. Holdout metrics (AUC/CalError/lift — no historical DK odds, so no flat ROI yet)
python -m models.backtester --model golf_top10 --season 2025

# 4. Commit the trained artifacts so GitHub Actions can score (UFC session-51 lesson)
git add -f models/saved/golf_*.pkl && git commit -m "Add trained golf model artifacts"
```

**Open items / caveats:** (1) DataGolf endpoint field names are provisional until
Phase-0 verification — parsers in `datagolf_ingestor.py` document every assumption
up top and are isolated for a one-line fix. (2) Real-odds backtest needs the
DataGolf historical-odds archive (tier unverified) — until then golf is validated
by holdout classification metrics + live paper trading. (3) Thresholds are
placeholders on a market-relative prob scale (win ~3%, top-N ~15-25%, make-cut
~65%) — sweep after 50+ settled picks per model.

---
