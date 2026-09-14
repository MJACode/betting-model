# NFL prop Out/Doubtful veto

A gate, not a feature. ESPN injury statuses do **not** enter the XGB models
and do **not** reprice a line. They decide whether `nfl_prop_market` (and
any sibling NFL prop scorer that would still write a BET) may emit a pick
on that player.

## Rule

Refuse the bet when **all** of:

1. The player's latest NFL injury row is **Out** or **Doubtful** (Injured
   Reserve is stored as Out).
2. That row's `status_ts` (ESPN's injury `date`) is **≤** the quote's
   `snapshot_at`.

News that arrived **after** the line is ignored. Missing either clock
fails **open** — we cannot prove the news predates the quote, so we do
not veto. Questionable / Active / unknown players are unaffected.

This is the same timestamp discipline as `scripts/nfl_prop_injury_signal`
(drop reports modified after the row's snapshot). It is the opposite of
training on the designation: §3a of `docs/nfl_prop_profitability_search.md`
already measured that the Friday report is in the DraftKings line by
Sunday. The failure mode this gate exists for is a **stale quote still
up after a late scratch**, not a training edge.

## Source

Same ESPN core path as MLB/NHL/WNBA/NBA (`data/ingestors/injury_ingestor.py`).

Measured 2026-09-14 from this environment:

- `sports.core.api.espn.com/v2/sports/football/leagues/nfl/teams` → 200,
  32 teams.
- `.../teams/12/injuries` (KC) → 200, 54 items. Each injury doc has
  `date` (`2026-09-12T18:14Z`), `status` (`Out` / `Active` / `Doubtful` /
  `Questionable` / `Injured Reserve`), `type.description`.
- `site.api.espn.com` → 403 (same host the worker lost on 2026-08-05).
  NFL team ids therefore resolve from **core**, with `ESPN_NFL_TEAM_IDS`
  as the offline fallback. ESPN's LAR/WSH become our LA/WAS via
  `NFL_ODDS_API_MAP` name join.

**Active is skipped.** It is the majority status on the NFL list
(cleared, still on the report). The historical unmapped default was Out;
storing Active as Out would veto healthy players.

`player_news` stays display-only. No RotoWire/RotoBaller in this path.

## Where it fires

- `scripts/nfl_prop_market_card.card` — after `find_bets`, before
  `best_per_prop` / publish.
- `models.scorer.run_nfl_prop_scorer` — the live distributional sibling
  (`nfl_prop_tackles_assists`) and any later unpause. Paused models still
  score NONE rows; a BET on a scratched player is still refused.

Not applied to `nfl_opener_spread` / `nfl_wind_totals` (game lines) or to
`nfl_live_prop` (in-play inactivity is a different gate).

## Placebo sketch (follow-up)

A proper placebo randomly reassigns the Out/Doubtful flags across the
same week's board, bounded at each row's `snapshot_at`, and asks whether
the vetoed-vs-kept split prints CLV. If the book has already moved, it
should not.

That study is **not** in this PR: `injuries` had **zero** `sport='NFL'`
rows as of 2026-09-14 (production counts were MLB/NBA/NHL/WNBA only).
The ingest starts on the first worker pass after merge. Re-run then:

```text
python -m scripts.nfl_prop_injury_signal --feats <dk cache>
```

is the nflverse-weekly analogue (already showed no offensive-market cell
positive in more than one season). The ESPN-path placebo needs a few
weeks of `injuries.status_ts` plus the existing `player_prop_odds`
snapshots; it belongs in a script next to that one, not in the XGB
feature list.

## Out of scope (deliberate)

- Paid news feeds (`PLAYER_NEWS_PROVIDER`)
- Unpausing paused distributional props / sacks
- Teammate-volume (QB out → WR over) — §3a found no CLV
- MLB ace / NHL goalie / NBA star DNP gates
- Changing `nfl_opener_spread` / `nfl_wind_totals` units
