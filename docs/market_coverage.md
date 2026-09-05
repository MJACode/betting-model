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

## NCAAF — probed 2026-09-05 (27 keys, 30 credits), then measured on a real pass

15 of 27 served on the probe. The open question was `player_rush_attempts` and
`player_sacks`: empty on both probed events, but pulled AND mapped. **Answered
on the first real pass** (2026-09-05, 1pm ET / 17:35 UTC), which asked **all 68
events** — `68/68 events in scope (dropped: unresolved 0, no_dk_line 0,
over_cap 0)` — and got props back from 31 of them: 9,187 rows, 615 players,
7 books, **590 credits, 219.6s**, 16 of 20 requested markets returning:

| Empty across the whole pass | Verdict |
|---|---|
| `player_rush_attempts` | asked, unpriced — **pruned** |
| `player_sacks` | asked, unpriced — **pruned** |
| `player_rush_attempts_alternate` | ditto — **pruned** |
| `player_sacks_alternate` | ditto — **pruned** |

**"Empty" was separated from "never asked" by the chunking, not assumed.**
Markets go out five per call, and a 422 kills its whole chunk. Three of the
four rode in chunks whose OTHER members came back full, so the chunk succeeded
and the market itself was empty. `player_sacks` was alone in its chunk — that
case is genuinely ambiguous from row data, and the probe's one-market-per-call
result ("supported, no book") is what resolves it. **A market alone in a chunk
cannot be diagnosed from stored rows; probe it.**

**The prune is per league.** The NFL prices both keys — 3,206 and 3,718 stored
rows — and the two leagues share one stat catalog and one map, so removing
them from `FOOTBALL_STAT_TO_MARKET` would have blanked two working pro columns
to fix two dead college ones. `FOOTBALL_MARKET_NOT_PRICED` carries the
per-league exclusion instead, and it is reversible: if college books start
posting carries, the entry comes out and the column fills.

**The saving is calls, not credits, and the difference matters.** 20 markets to
16 is five chunks per event down to four: ~68 fewer calls per pass and ~20% off
a 219.6s run. It is **not** a credit saving of any size — The Odds API bills per
market RETURNED, and these returned nothing, so they were already close to free.
(590 credits over ~340 calls is 1.74 each, and 185 of those calls were against
the 37 events that returned no props at all, which puts the productive calls
near 3.8 and the empty ones near zero.) The reason to drop them is that a
request nobody answers is a lie in the config about what this sport offers.

**Cost, measured not projected:** 590 credits for the 1pm ET pass, against a
~590 projection from the three-event probe. Three passes a day (9am, 1pm, 6pm
ET) puts college props near 1,800 credits/day at Saturday slate size.

**Not in `api_call_log`:** neither prop ingestor logs its calls there (both use
bare `requests.get` with only `record_quota_headers`), so prop credit spend is
invisible in that table for every sport. Only `odds_api_quota` and the response
headers see it. Worth fixing when the ingestors are next touched.

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
