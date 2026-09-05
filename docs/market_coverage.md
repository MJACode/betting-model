# Prop market coverage — what the feed actually serves

> The answer to "why is that column blank?" is one of three things, and stored
> data can only tell you the first two apart from each other by accident.
> **Run the probe rather than querying `player_prop_odds`.**

```bash
python -m scripts.probe_market_coverage --sport MLB
python -m scripts.probe_market_coverage --sport NCAAF --markets player_sacks
```

The script (`scripts/probe_market_coverage.py`) asks The Odds API for **one
market per call** against a live event and writes nothing. Its own docstring
carries the mechanics and the per-book alternate-key findings; this file is the
standing answer table, so nobody re-spends credits to re-learn it.

## The three states, and why a table cannot distinguish them

| State | What the API does | What our tables look like |
|---|---|---|
| **Unsupported key** | 422s the call | empty |
| **Supported, unpriced** | returns the market with no outcomes | empty |
| **Served, never requested** | returns books and prices | empty |

All three are an empty table. Only the probe separates them — which is why
"the data doesn't exist" is never a finding until the probe has been run
(CLAUDE.md §1b: the current state of a system is not its capability).

## MLB — probed 2026-09-05, 30 keys, 44 credits

- **Served, and now pulled:** `batter_doubles`, `batter_triples`,
  `batter_stolen_bases_alternate`. Doubles and Triples had been blank columns
  on the Stats board since it shipped; nobody had asked for them.
- **Unsupported keys — these columns are correctly blank forever:**
  `batter_at_bats`, `pitcher_home_runs_allowed`, `pitcher_pitches`.
- **Supported but no book priced it — dropped or never added:**
  `pitcher_hits_allowed_alternate`, `pitcher_walks_alternate`,
  `pitcher_earned_runs_alternate`, `pitcher_outs_alternate`. Each costs ~2.5
  credits per event call, every pass, for nothing.
- **Supported, empty on the one probed event — not added:**
  `batter_strikeouts`. One event is not a population; re-probe wider first.

## NCAAF — probed 2026-09-05, 27 keys, 30 credits

15 of 27 served. `player_rush_attempts` and `player_sacks` came back empty on
both probed events but are pulled AND mapped — **open**, pending a measurement
across a full college slate rather than two events.

## WNBA — not answered

No games on the slate on 2026-09-05, so the probe had no event. The open
question: the board carries Steals and Blocks columns, `PROP_MARKETS_WNBA`
carries neither market, and NBA pulls both. Re-probe on a day with games.

## The invariant that keeps this from drifting again

`tests/test_market_coverage_probe.py::test_the_mlb_board_and_the_mlb_pull_are_one_set`
walks both routes from a board stat to a market key — through the model id
(`STAT_KEY_TO_MODEL` -> `PROP_MARKET_BY_MODEL`), and through the direct maps
for stats with no model (`STAT_KEY_TO_MARKET`, `FOOTBALL_STAT_TO_MARKET`) —
and asserts set equality with `config.PROP_MARKETS_ALL` **in both directions**.
A market we pull that nothing can display is credits spent on every pass; a
column with no market is a permanent dash.
