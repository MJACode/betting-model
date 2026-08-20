# NCAA Football (FBS) — Model Build Plan

**Status:** proposed, not started. Scope: `ncaaf_spread`, `ncaaf_over_under`,
`ncaaf_moneyline`. Sport code: `NCAAF` (7th sport, joins the global toggle —
no new mobile tab).

---

## 1. TL;DR — can we get the data free?

**Yes. All of it, including historical betting lines.**

That last part matters more than it sounds. Every totals/spread model we've
tried to build outside MLB is currently **BLOCKED for the same reason** — no
historical lines to compute the target against (`nhl_over_under`,
`nhl_puckline`, `nba_over_under`, `nba_spread`, and originally
`wnba_over_under`/`wnba_spread`, which we only unblocked by *synthesizing*
lines). NCAAF is the first new sport where a free source ships real historical
closing spreads and totals, so **all three markets are trainable and
backtestable on day one** against real prices.

| Source | Provides | Cost | Notes |
|---|---|---|---|
| **CollegeFootballData.com (CFBD)** | games/scores, **historical betting lines** (spread, total, ML — per provider incl. consensus/DraftKings/Bovada/ESPN Bet), team season + advanced stats (EPA, success rate, explosiveness, havoc), SP+/SRS/Elo/FPI ratings, 247 team talent composite, returning production, per-game team box scores, drives, full play-by-play, venues, rosters | **Free** — API key by email, no card. Paid Patreon tiers only raise rate limits / add GraphQL + live | The primary source. Everything below is supplementary |
| **The Odds API** | live DK + line-shop odds, `americanfootball_ncaaf`, h2h/spreads/totals | **$0 extra** — already on the $79/mo Starter plan | Same ingestor path as every other sport. Costs credits per request, not per book |
| **ESPN hidden API** | injuries, scores fallback, FPI | Free | Already wired for MLB/NHL/WNBA/NBA. CFB injury reporting is voluntary and thin — low value, build last |
| **Open-Meteo** | temp / wind / precip | Free | `weather_ingestor.py` already exists; needs ~135 FBS venue lat/lon + dome flags (CFBD `/venues` supplies coordinates) |
| **cfbfastR / sportsdataverse GitHub releases** | same CFBD data as bulk parquet/CSV | Free | Backup bulk-backfill path with no rate limit — the nflverse pattern we already use in §28 |

**One caveat I could not verify from the sandbox** (collegefootballdata.com is
blocked by the egress proxy): the exact free-tier rate limit. Historically it's
been generous but throttled per minute. Plan the backfill as a paced,
resumable, disk-cached job (the UFC CSV-mirror pattern), and if it's slow, pull
the same data from the sportsdataverse GitHub release assets instead.

---

## 2. What makes CFB different from every sport we've modeled

This is the honest-risk section. CFB is **not** MLB with a different ball.

**2.1 Tiny per-team sample.** 12–13 games a season vs 162 (MLB) / 82 (NBA).
Team stats never stabilize the way ours do. Our `is_early_season` / "≥10 games
played" rule would blank out ~80% of a CFB season. **Fix:** don't use flat
rolling averages — blend an in-season estimate with a **preseason prior**
(prior-year SP+, returning production, talent composite), weighted by games
played. Practically: `feature = w·in_season + (1−w)·prior`, `w = g/(g+k)`,
k≈4. This is the single most important design decision in the build.

**2.2 Blowouts break the moneyline.** Alabama vs a MAC team is −5000. On a
typical Saturday, 60–70% of games have a moneyline no bettor would touch.
**Fix:** spread + totals are the primary markets; moneyline is tertiary and
carries a hard price floor in `MODEL_MIN_ODDS` (start at −250), which we
already have plumbing for.

**2.3 Market efficiency is bimodal.** A P4 primetime game is priced as sharply
as an NFL game. A Tuesday-night MAC game or an FCS crossover has a soft number
and low limits. The public edge historically lives in the low-profile games —
which is also where the data is thinnest. **Fix:** carry a `game_tier`
feature (P4/G5/mixed) and **tune thresholds per tier**, the way we already
split thresholds per model.

**2.4 Roster continuity collapsed in 2021.** Transfer portal + NIL means
pre-2021 year-over-year team continuity behaves differently from post-2021.
**Fix:** train on 2015–2024 but include `returning_ppa` (returning production)
explicitly, and consider sample weighting recent seasons higher. Hold out 2025.

**2.5 Bowls and the playoff are a different game.** Opt-outs, interim coaches,
month-long layoffs. **Fix:** flag `is_bowl` / `is_playoff`, exclude bowls from
*training* (they're noise), and **do not bet them** in v1.

**2.6 FBS-vs-FCS games have no opponent data.** **Fix:** hard gate — only
score games where both teams are FBS (`both_fbs`).

**2.7 Slate shape is weekly, not daily.** ~60–80 FBS games clustered into four
Saturday windows. A 3% edge threshold across 80 games could fire 30+ picks in
one afternoon. **Fix:** tighter opening thresholds than MLB and a
per-week pick cap; the pipeline runs a weekly cadence (Sun/Tue/Thu/Fri/Sat)
rather than the daily 6am shape.

**2.8 Season label footgun.** Season = calendar year of the fall. The 2025
season includes January 2026 bowl/playoff games. This is the exact NBA bug the
codebase already documents — **thread `season` explicitly, never derive it
from the game date.**

---

## 3. Target markets and models

| Model ID | Market | Target | Priority |
|---|---|---|---|
| `ncaaf_spread` | `spreads` | Home covers the closing spread | **1** — best liquidity/edge tradeoff |
| `ncaaf_over_under` | `totals` | Total points > line | **2** — tempo + weather give real signal |
| `ncaaf_moneyline` | `h2h` | Home team wins | 3 — gated by a −250 price floor |

All three score against real DK lines. All three backtest against real
historical lines. Binary XGBoost + Platt calibration — identical shape to the
existing game models, so `trainer.py` needs **zero changes**.

---

## 4. Feature set (proposed v1)

Diff-style (`d_*` = home − away) to match the existing engines. All ASOF —
strictly data available before kickoff.

**Ratings / priors (the backbone — these carry CFB):**
`d_sp_plus_overall`, `d_sp_plus_offense`, `d_sp_plus_defense`,
`d_sp_plus_special_teams`, `d_elo`, `d_srs`, `d_talent` (247 composite),
`d_returning_ppa`

**Efficiency (shrunk in-season, per §2.1):**
`d_epa_per_play_off`, `d_epa_per_play_def`, `d_success_rate_off`,
`d_success_rate_def`, `d_explosiveness`, `d_havoc_rate`,
`d_finishing_drives`, `d_avg_field_position`, `d_third_down_rate`,
`d_turnover_margin`

**Tempo (the totals driver):**
`d_plays_per_game`, `d_seconds_per_play`, `d_points_per_game`,
`d_points_allowed_pg`, plus last-3 rolling variants

**Market:** `spread_home` (spreads/ML), `total_line` (totals) — the opening
line is the most predictive single feature in every model we've built

**Situational:** `is_neutral_site`, `is_conference_game`, `rest_days_home/away`,
`d_rest_days`, `is_bye_return_home/away`, `travel_distance_away`,
`timezone_shift_away`, `week_number`, `is_early_season`, `is_bowl`,
`is_playoff`, `game_tier`, `altitude_ft`

**Weather (totals + spread only):** `temp_f`, `wind_mph`, `precip_mm`,
`is_dome_game` — reuse `weather_ingestor.py` verbatim once venue coords load

**Injuries:** deliberately **excluded from v1**. CFB injury reporting is
voluntary and unreliable; adding it now buys noise. Revisit after the model
validates.

---

## 5. Build phases

Mirrors how NBA (session 56) and UFC (session 49) were added.

### Phase 1 — config + schema (~½ day)
- `config.SPORTS["NCAAF"]`: `odds_api_key="americanfootball_ncaaf"`,
  `seasons=2015..2026`, `train_seasons=2015..2024`, `test_season=2025`
- 3 entries in `MODELS`; placeholder thresholds in all three threshold dicts
  (start **tight**: spread 0.58/0.06, totals 0.58/0.06, ML 0.62/0.08 + a
  `MODEL_MIN_ODDS` floor of −250 on ML)
- `NCAAF_TEAMS` + `NCAAF_ODDS_API_MAP` — the fiddliest bit: ~135 FBS teams and
  The Odds API's names ("Ole Miss" vs "Mississippi", "Miami" vs "Miami (FL)"
  vs "Miami (OH)") must map to CFBD's canonical school names. Build the map
  programmatically from CFBD `/teams/fbs` and pin the exceptions in config
- New tables: `ncaaf_team_stats` (ASOF season snapshots) + `ncaaf_team_game_log`
  (per-game box scores for rolling features). Games/odds/picks reuse existing
  sport-agnostic tables
- Supabase migration + `db_setup.SCHEMA_SQL` + `supabase_schema.sql` +
  `EXPECTED_TABLES`

### Phase 2 — ingestion (~1–2 days)
- `data/ingestors/cfbd_ingestor.py`: pure fixture-tested parsers + idempotent
  writers. Entry points:
  - `backfill_ncaaf(start, end)` — games, box scores, season stats, ratings,
    talent (paced, resumable, disk-cached)
  - `backfill_ncaaf_lines(start, end)` — `/lines` → `odds` table as
    `bookmaker='cfbd_consensus'` (whitelisted alongside `sbr_consensus` so the
    feature engine reads it, exactly like the F5/WNBA synthetic-line precedent)
  - `run_ncaaf_stats_ingestor()` — weekly in-season refresh
  - `ingest_ncaaf_results_for_date()` — finals before settlement
- Wire `NCAAF` into `odds_ingestor.SPORT_KEYS` (live DK lines — the generic
  `_process_events` path handles h2h/spreads/totals with no new parsing)
- Venue lat/lon + dome flags → `weather_ingestor.py`

### Phase 3 — features (~1–2 days)
- `features/ncaaf_feature_engine.py`: live path + bulk ASOF/bisect path
  (same technique as MLB/NBA — non-negotiable, the per-game-query path takes
  hours). Includes the **prior-shrinkage blender** from §2.1
- Feature lists + `FEATURE_MAP` entries + `build_features_for_game` dispatch +
  `build_training_dataset` bulk branch in `feature_engine.py`
- `_compute_target` needs **no changes** — `h2h`/`totals`/`spreads` are already
  sport-generic

### Phase 4 — train + backtest (~1 day, mostly compute)
- Train 3 models, 2015–2024 / holdout 2025
- **Real-odds backtest on 2025** — flat ROI at actual closing prices. This is
  the honest gate, and we get it for free here (unlike NHL/NBA totals)
- Sweep prob×edge thresholds on the 2025 holdout, sliced by `game_tier` and by
  week bucket. **Reject the sport if the plateau isn't positive** — CFB spreads
  are efficient enough that a null result is a real possibility, and a null
  result on ~800 backtest games is trustworthy
- Commit artifacts (`git add -f models/saved/ncaaf_*.pkl`)

### Phase 5 — scoring / settlement / pipeline / mobile (~1 day)
- `run_scorer` NCAAF branch (generic — reuses the h2h/totals/spreads path)
- Settlement rides the **generic game-level path** unchanged (scores + line);
  only `_market_for_pick` needs the three model ids mapped
- Pipeline steps: `ncaaf-results` (before settle), `ncaaf-stats`,
  `ncaaf-lines`; weekly scheduler jobs
- Mobile: `'NCAAF'` in the `Sport` union, `modelMeta`, `thresholds.ts`,
  `gameMarketForModel`; §16/§17 SQL blocks; Stats tab empty state for v1
- `system_health.py` checks + `KNOWN_UNTRAINED` update

**Total: roughly 5–7 working days of build, plus backfill compute.**

---

## 6. What I'd want decided before starting

1. **Markets** — confirm spread + totals first, moneyline third with a price
   floor. (Alternative: all three at once, accepting most ML picks will be
   filtered out by the floor anyway.)
2. **Training window** — 2015–2024 (10 seasons, ~8,500 FBS games) vs 2019–2024
   (post-analytics-era, more consistent CFBD coverage, ~4,500 games). I lean
   2015–2024 with recency weighting.
3. **FCS games** — confirm hard exclusion.
4. **Bowls** — confirm excluded from training and not bet in v1.
5. **Cadence** — weekly (Sun open / Thu / Fri / Sat morning) vs daily. Weekly
   is cheaper on Odds API credits and matches how the market actually moves.
6. **Kill criterion** — what 2025-holdout result makes us walk away? I'd
   propose: if no prob×edge cell clears +3% flat ROI over ≥150 backtest bets on
   *either* spread or totals, we don't ship it.

---

## 7. Why this is worth doing

- Only new sport where **all three game markets are backtestable against real
  historical prices** — no synthetic lines, no prob-only fallbacks
- ~800–900 FBS games a season, five months, minimal overlap with MLB's peak
- Free data, and the live-odds side costs nothing beyond the existing Odds API
  plan
- The market's soft tier (G5, midweek, low-limit) is genuinely less efficient
  than anything else we're currently pricing

The counterweight: CFB is the most sample-starved sport we'd have modeled, and
the honest failure mode is "the model is fine but the market is fine too."
The Phase 4 backtest is the real go/no-go, and unlike our other sports we can
actually run it.
