# Game-model starter / star / goalie gate

A gate, not a feature. ESPN injury statuses (and ESPN NHL
`probableStartingGoalie`) do **not** enter the XGB models and do **not**
fudge `injury_adj`. They decide whether a game-model BET may be written.

`home_starter_out` / `_compute_injury_adjustment` in
`features/feature_engine.py` remain the trained averages they always were.
`_has_starter_out` still fires on any IL player with no position — that is
why it is the wrong shape for this product.

## Rule

Refuse the BET when **all** of:

1. The named player is the one the features currently use:
   - **MLB** — `mlb_pitcher_stats.player_name` for that team and game date
     (the probable starter). Status **Out / IL10 / IL15 / IL60**.
   - **NHL** — `nhl_goalie_stats.player_name` on the **game-date** row (no
     ASOF fallback to the season-start snapshot — that is last year's #1).
     Status **Out / Doubtful**.
   - **NBA / WNBA** — the team's top-2 by average minutes over the last 10
     team-games (min 5 appearances, min 20 mpg). Status **Out** (star DNP).
     Measured 2026-09-14 on WNBA 2026: 198 rotation players, 42 at ≥28 mpg;
     top-2 at ≥20 mpg is the star tier, not the 6th man.
2. That row's `status_ts` (ESPN's injury `date`) is **≤** the quote's
   `snapshot_at` (the decision-book clock stamped as `_quote_snapshot_at`,
   falling back to the DK snapshot).

News that arrived **after** the line is ignored. Missing either clock
fails **open**. Questionable / Day-To-Day / Active / unknown players are
unaffected. AVOID and NONE rows are not rewritten.

This is the same timestamp discipline as `models/nfl_prop_injury_veto.py`.

## Reprice

A NONE from this gate is **not locked**. The game lock is BET-only
(`LOCK_GAME_PICKS_AT_FIRST_RUN`). The next scoring pass that sees a new
probable in `mlb_pitcher_stats` / `nhl_goalie_stats` rebuilds features
from that pitcher/goalie and may fire a BET. That is the reprice path —
not an `injury_adj` fudge.

## NHL goalie confirm — ingest extension

NHL `/v1/schedule/now` **does not** carry `probableGoalie` (measured
2026-09-14: 43 games, 0 populated). The daily stats write used to fall
through to the season leader.

ESPN core competitor `probables` **does**: `name=probableStartingGoalie`,
athlete `$ref`, `status.type` `expected` / `confirmed`.
`data/ingestors/espn_probables.py` reads that (core, not site.api — 403
from this sandbox) and `nhl_stats_ingestor._build_goalie_rows` prefers
the ESPN name. Join is on displayName via `NHL_ODDS_API_MAP` (LA Kings
→ LAK, Utah Mammoth → UTA). `config.ESPN_NHL_TEAM_IDS` is **not** used:
that map collides (ANA and DAL both 25).

The probable object itself has **no date**. A scratch's clock is still
`injuries.status_ts`.

## Where it fires

- `models.scorer.score_game` — after best-price requalify, before insert.
- `models.scorer._score_nhl_3way` — same.

Not applied to NCAAF (injuries excluded by design), UFC, `nfl_opener_spread`
(the edge IS a stale number), or `nfl_wind_totals` (the physical residual).

## Out of scope (deliberate)

- Motivation / revenge
- Public % as a feature (stays app fade-display)
- Steam / close as a beat-the-close feature (`market_movement.py` stays a
  CLV read)
- Weather as anything but the existing physical residual
- Paid RotoWire / RotoBaller
- Unpausing NFL XGB props
- Changing opener / wind thresholds
- Adding `injury_adj` / starter-out columns to XGB
