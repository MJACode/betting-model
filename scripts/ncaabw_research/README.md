# Women's college basketball (NCAABW) research scripts

The scripts behind `docs/sports/ncaabw.md`, "Research". They read a local
cache and the odds purchase's spool, never production at analysis time.
Set `NCAABW_RESEARCH_DIR` (default `~/ncaabw_research`); the spool is its
`spool/` folder unless `NCAABW_RESEARCH_SPOOL` names another.

Run from the repo root, in this order:

| Step | Command | What it does |
|---|---|---|
| 1 | `python -m scripts.ncaabw_research.cache` | One read of the stored schedule and results (needs production settings), and NCAA's box scores from sportsdataverse's season files |
| 2 | `python -m data.ingestors.ncaabw_odds_history --seasons 2025 2027 --spool <spool> --fetch --store` | The paid odds history (skips what the spool holds) |
| 3 | `python -m scripts.ncaabw_research.quotes` | The spool as research tables, through the production parser: pre-game quotes, in-play quotes, boards at fixed leads before the tip |
| 4 | `python -m scripts.ncaabw_research.totals_a` | The men's rating model on the women's games: accuracy by season (no prices) |
| 5 | `python -m scripts.ncaabw_research.espn_odds 2023 2024`, then `espn_odds_tab 2023 2024`, then `totals_espn` | ESPN's own stored odds, and the rating model against those lines |
| 6 | `python -m scripts.ncaabw_research.totals_b`, then `totals_c` | The totals model at DraftKings' first posted total: the replay, then the cut, calibration and splits |
| 7 | `python -m scripts.ncaabw_research.market` | The men's spread and moneyline market rules on the women's boards |
| 8 | `python -m scripts.ncaabw_research.inplay` | The in-play game-state model against every snapshot's in-play quotes (needs `pbp_<season>.parquet` in the cache: sportsdataverse's `espn_womens_college_basketball_pbp/play_by_play_<season>.parquet`) |
| 9 | `python -m scripts.ncaabw_research.inplay_checks` | The halftime total's and halftime spread's four checks (blind sides, claimed-EV bands, a placebo, stale prices), on the priced quotes step 8 leaves in the cache |
| 10 | `python -m scripts.ncaabw_research.sides`, then `sides grid` | Spread and moneyline off the totals model's team ratings at DraftKings' first posted line; the same with the ratings' settings moved |

Two more read production through the totals card's own reads (they need
production settings, and write nothing). `box_coverage` prints this season's
box coverage after one source is kept per game. `season_to_date` replays the
card's decision on every priced game of the season so far, with the committed
artifact. Read the caveat in `totals_a`'s section of the doc first: until
2026-11-10 only the played games of 2026-27 were stored, so anything computed
on that season before then had every team pooled into one.

`check_tips` answers one question about the purchase: whether games with
in-play quotes and no pre-game ones have an early stored tip (they do not).

Stake everywhere: one unit to win, risk capped at 3, at the quoted price.
Intervals are 95%, resampled by date.
