# NBA public betting splits (Action Network) — `nba_public_splits`

Built 2026-10-16 as a **control** for the NBA game-market search: fading the
public is graded, never a candidate. Coverage and timing honesty come first.

Code: `data/ingestors/nba_public_splits_ingestor.py` (archive backfill and the
forward pre-tip capture), `scripts/action_network_archive_timing.py` (the MLB
timing calibration), `scripts/nba_public_splits_spot_check.py` (stored vs
served). Tests: `tests/test_nba_public_splits_ingestor.py`.

## Source

Action Network's free scoreboard JSON, consensus pseudo-book 15 — the same
source `public_betting` uses for MLB. No key, no paid call. A bare client is
refused (HTTP 403); the browser headers in the ingestor answer HTTP 200.

| Endpoint | Splits for | Extra |
|---|---|---|
| v1 `/web/v1/scoreboard/nba?period=game&bookIds=15&date=YYYYMMDD` | 2020-21 opening night on (see coverage) | `inserted`: last write of the consensus row |
| v2 `/web/v2/scoreboard/nba?bookIds=15&date=YYYYMMDD&periods=event` | 2023-24 on | serves `0` on both sides where it has no split |

Routes that do **not** give NBA history: the per-game page
(`/nba-game/<slug>/<id>`) answers HTTP 410 with an empty payload; the
public-betting page ignores `?date=` server-side; the per-game history endpoint
(`/web/v2/markets/event/<id>/history`) holds price and line moves only, never a
split, and is empty for NBA games.

## What the archived number is (timing)

**One number per side, with no time on it.** It is the split as it stood at,
or very near, the listed start. It is a *closing split*, not a value a model
could have read hours before tip. Four measurements:

1. **MLB calibration** (`scripts/action_network_archive_timing.py`, run
   2026-10-16). `public_betting` holds 9,198 Action Network rows our own
   ingestor fetched; 1,564 of the 9,105 with an archive value were fetched
   before the listed start. Archive vs our capture, by how long before the
   start we captured:

   | Captured before start | Rows | Tickets % identical | Money % identical | Tickets abs. gap median / 90th pct | Money abs. gap median / 90th pct |
   |---|---|---|---|---|---|
   | 0–15 min | 696 | 95.1% | 91.8% | 0 / 0 | 0 / 0 |
   | 15–60 min | 634 | 74.0% | 64.7% | 0 / 1 | 0 / 4 |
   | 60–180 min | 234 | 46.6% | 12.0% | 1 / 2 | 2 / 9 |

   The archive keeps moving right up to the start, and equals what was showing
   in the last quarter hour.

2. **NBA, dated pages from the Wayback Machine** — captures of
   `actionnetwork.com/nba/public-betting` from the Wayback Machine. The CDX
   index lists 195 day-level captures 2020–2026; of the 25 fetched, 4 carried no
   page data and 1 (06:49Z) only last night's games, leaving 20 captures
   (2021-01-27 to 2026-04-14) with 157 games not yet started — 942 side-level
   readings, taken a median 8.1 hours before the listed start (0.9 to 19.8; 152
   of the 157 games 3 hours or more).
   Against the stored archive:

   | Archive | Sides compared | Tickets % identical | Money % identical | Tickets abs. gap median / 90th pct | Money abs. gap median / 90th pct |
   |---|---|---|---|---|---|
   | v1 | 918 | 36 of 852 | 36 of 740 | 8 / 30 | 12 / 46 |
   | v2 | 288 | 12 of 276 | 8 of 230 | 7 / 32 | 8 / 42 |

   And the ticket count: for the 48 games with both, the count at capture was a
   median **19.8%** of the archive's (range 5.2%–35.7%). Roughly four in five
   of the tickets behind an archived split arrived after a morning or afternoon
   look at the page.

3. **Tip-off poll, 2026-10-16 preseason** — Twelve preseason games polled every
   5 minutes from 00:34Z (`poll_tip.py`, a one-off). The nine games already
   under way held the same pre-game split and the same ticket count on every
   poll for over an hour (one finished in that time); the only change was one
   pre-game price (-110 to -107, split unchanged). The three not yet started
   kept moving: ticket counts 848→913, 812→853, 1,024→1,115 and 6–9 split or
   price changes each in 70 minutes.

4. **v1 `inserted`** is after the listed start for 7,233 of 7,254 games (median 19.4 minutes after,
   10th–90th percentile 11.4 to 144.9) — it
   marks the last write of the consensus row (a price can still be updated
   after the start), not when the split was observed. Kept per row as
   `source_inserted_at` / `inserted_minus_start_min`; do not read it as an
   observation time.

**Consequence for an analysis.** Treat `archive_undated` as "the public split
at the close". A rule that fades it is graded against the close and must not
be described as available earlier. Only `pregame_poll` rows (2026-27 on) carry
a real observation time.

## Table

`nba_public_splits` — worker-only (RLS on, no app-role grant), created on
demand by the ingestor. One row per Action Network game × market × side ×
endpoint × capture.

| Column | Meaning |
|---|---|
| `game_id` | our `games.game_id`; NULL when the Action Network game is not in `games` (see `match_kind`) |
| `season` | ours (ENDING year), from the `games` row — never Action Network's, which is the starting year |
| `game_date` | ET date of Action Network's start time |
| `match_kind` | `exact`, `swapped` (same teams/date, home and away reversed: `side` was flipped into OUR orientation), `not_found`, `team_unknown` |
| `market`, `side` | `h2h`/`spreads`/`totals`; `home`/`away`/`over`/`under` in our orientation |
| `line_value` | THAT side's number: the home spread row holds the home number (the `scored_line` convention), the away row the away number; the total for over/under; NULL for moneyline |
| `odds` | that side's American price at the consensus book |
| `tickets_pct`, `money_pct` | 0–100 as served. NULL when absent, when v2 served 0 on both sides, or when the pair did not sum to 100 ± 1 |
| `num_bets` | Action Network's ticket count for the game (v2) or the consensus row (v1) |
| `endpoint` | `v1` or `v2` — both stored; they disagree on a minority of values |
| `capture_kind` | `archive_undated` (fetched after the game; `observed_at` NULL) or `pregame_poll` (fetched before the listed start; a CHECK refuses a poll row at or after it) |
| `observed_at` | poll fetch time; NULL for the archive |
| `source_inserted_at`, `inserted_minus_start_min` | v1's `inserted` and its gap to the listed start, evidence only |
| `snapshot_key` | `archive`, or the poll's fetch time — part of the unique key |

Unique key `(an_game_id, market, side, endpoint, capture_kind, snapshot_key)`;
every write is `ON CONFLICT DO NOTHING`, so a re-run writes nothing already
stored.

## Coverage

Regular-season games in `games` with at least one archived split
(the query below), 2026-10-16:

| Season | Games in `games` | Any split | v1 | v2 | Moneyline tickets | Spread tickets | Total tickets | Moneyline money | Spread money | Total money |
|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 1,080 | 1,080 | 1,080 | 0 | 1,080 | 1,080 | 1,080 | 1,065 | 1,079 | 1,073 |
| 2022 | 1,230 | 1,230 | 1,230 | 0 | 1,183 | 1,230 | 1,230 | 1,213 | 1,226 | 1,149 |
| 2023 | 1,230 | 1,230 | 1,230 | 0 | 1,230 | 1,230 | 1,230 | 1,192 | 1,230 | 1,209 |
| 2024 | 1,230 | 1,230 | 1,230 | 1,034 | 1,230 | 1,230 | 1,230 | 1,073 | 1,173 | 1,125 |
| 2025 | 1,230 | 1,230 | 1,230 | 1,216 | 1,230 | 1,230 | 1,230 | 1,230 | 1,230 | 1,230 |
| 2026 | 1,230 | 1,230 | 1,230 | 1,186 | 1,230 | 1,230 | 1,230 | 1,230 | 1,230 | 1,230 |

v2's first split is 2023-11-20. Rows: 64,027 archive rows (v1 43,504, v2
20,523). **Unmatched:** 55 Action Network listings per endpoint on our dates
are all `status = postponed` (January 2021 COVID dates, GSW @ UTA 2024-01-17,
the January 2025 Los Angeles fires and storms, and others); the rescheduled
games match on their real dates. v2 has no split for any of them; v1 does for
24 (132 rows, `game_id` NULL, `match_kind = 'not_found'`) — betting on the
original date before the postponement. Playoffs and play-in are not in
`games` and were not fetched.

Dropped by validation, both endpoints together: 26 ticket pairs and 28 money
pairs that did not sum to 100 ± 1 (all v2; e.g. 0 against 34), 667 ticket and
1,445 money pairs that were absent or 0/0. v1 and v2 hold the same ticket % on
19,637 of the 20,523 sides both carry; on the 856 that differ the median gap is
2 points.

```sql
WITH s AS (
  SELECT game_id, endpoint FROM nba_public_splits
  WHERE capture_kind = 'archive_undated' AND game_id IS NOT NULL
  GROUP BY game_id, endpoint)
SELECT g.season, count(*) AS games,
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM s WHERE s.game_id = g.game_id)) AS any_split,
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM s WHERE s.game_id = g.game_id AND s.endpoint = 'v1')) AS v1,
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM s WHERE s.game_id = g.game_id AND s.endpoint = 'v2')) AS v2
FROM games g WHERE g.sport = 'NBA' AND g.season BETWEEN 2021 AND 2026
GROUP BY g.season ORDER BY g.season;
```

**Spot check** (`scripts/nba_public_splits_spot_check.py`, 2026-10-16): one
game per season — ATL @ DAL 2021-02-10, BKN @ CHI 2022-01-12, BKN @ NYK
2023-03-01, BOS @ TOR 2024-01-15, ATL @ CHI 2025-01-15, BOS @ SAS 2026-03-10 —
every stored line, price, ticket % and money % equal to the JSON the
public-betting page loads for that date, fetched fresh: 0 mismatches.

## Forward capture (2026-27)

`par nba-public-splits` in `scripts/refresh_pass.sh` (hourly 7am–5pm ET, every
10 minutes 6–11pm ET) runs `run_forward`: archive yesterday once (v2, plus v1
if it ever carries splits again), then one `pregame_poll` row per side for
every regular-season or playoff game that has not reached its listed start.
For a decision at time T read the latest poll row with `observed_at <= T`.

It never writes `public_betting`: `models/scorer.py` copies that table onto
every pick by game id with no sport filter, and `tracking/model_quality.py`
reads it back, so NBA rows there would change what live NBA picks carry.

## How to read it

```sql
-- the closing split for each regular-season game (v2 where it exists, else v1)
SELECT DISTINCT ON (game_id, market, side)
       game_id, season, market, side, line_value, odds,
       tickets_pct, money_pct, endpoint
FROM nba_public_splits
WHERE capture_kind = 'archive_undated' AND game_id IS NOT NULL
ORDER BY game_id, market, side, (endpoint = 'v2') DESC;
```

Join to `games` on `game_id`. Read a pick's line from its label, never rebuild
it from `line_value` (CLAUDE.md §00).
