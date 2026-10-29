# NCAAB — men's college basketball: data, odds capture, models

> **Started 2026-10-26 (mike: "built an ncaab model - season starts early
> nov"; the brief was rewritten into a build prompt and he answered "1) yes,
> 2) yes, 3 approved").** The 2026-27 season opens Sunday 2026-11-01 (Notre
> Dame vs Villanova, Rome, 9:30 a.m. ET); the full US slate starts Monday
> 2026-11-02 (182 games on ESPN). Season label: the ENDING year (2026-27 is
> 2027), as ESPN labels it, like the NBA and NHL.

## The models

None yet. A model goes live when it passes bars written down before its first
test (the build prompt's acceptance list: walk-forward by season with the
newest season held out; units, ROI with a confidence interval and closing-line
value against Pinnacle's vig-free close; its record against the opening and the
updated line on the Prediction Tracker's games; early season against late).
The research and its results will be recorded here once the first grid has
run.

## Identity: ESPN owns the games row

`data/ingestors/ncaab_teams.py` is the contract every other piece reads.

- **Team ids are ESPN team ids**, held in `ncaab_teams` with the school name
  (ESPN's `location`), a slug, mascot, display name and conference, for every
  Division I school AND every non-D1 opponent ESPN lists. `games.home_team` is
  the school name; the slug only appears in the game id.
- **Game ids** are `NCAAB_<ET date>_<away slug>_<home slug>` in ESPN's
  orientation, written only by the ESPN ingestor. `ncaab_events` maps ESPN's
  event id to that game id with both ESPN team ids, and a postponed game keeps
  its id.
- **The odds feed never mints an NCAAB game.** Its events resolve onto ESPN's
  games by the UNORDERED team pair within a day of the tip
  (`ncaab_teams.make_resolver`). When the feed calls ESPN's away team home (a
  neutral court: ESPN shows 30 of 69 games neutral on 2026-11-25), the names
  are swapped before the outcomes are parsed, so the stored spread is ESPN's
  home number. Unresolved names are dropped, counted, and fixed by an entry in
  `config.NCAAB_ODDS_API_MAP` (name -> ESPN id).
- Three-letter ids were never an option: the old fallback turned "Kentucky
  Wildcats" and "Kansas State Wildcats" into the same team (measured
  2026-10-26: `NCAAB_2026-11-03_WIL_WIL`).

## What runs, and where it lands

| Piece | What | Where |
|---|---|---|
| ESPN schedule + results | Teams, venues, every game (neutral flag, conference game), finals for settlement; the daily pipeline refreshes 14 days ahead, every refresh pass fills finals for started games | `data/ingestors/ncaab_espn_ingestor.py`, steps `ncaab-schedule` / `ncaab-results` |
| Live odds | Full-game moneyline, spread and total from the ten line-shop books on every refresh pass; NCAAB is exempt from the DraftKings-must-list gate so every book's first post is kept | `data/ingestors/odds_ingestor.py` |
| Opener capture | Every 5 minutes, change-only (a row is written only when a book's price or line moved), so the time each book first posts is known | `scripts/ncaab_odds_capture.py`, job `ncaab_odds_capture` |
| Price-path retention | NCAAB keeps every book's whole price path (the clean-up job only removes unchanged middles), and the close it keeps for any sport is the last price before the start | `data/prune_odds.py` (`PATH_KEPT_SPORTS`) |
| Paid history | Game lines 2020-21 → 2025-26 (bulk snapshots: the evening before, mid-morning, and the hour before every tip); first-half and team-total lines 2023-24 → 2025-26, opener and close. Unmatched events are kept raw in `ncaab_odds_unmatched`, never dropped | `data/ingestors/ncaab_odds_history.py`, job `ncaab_odds_history` |
| Free history | Prediction Tracker lines and systems 2004-26, SBRO lines 2007-21 (matched onto ESPN games by date and final score), NCAA possession box scores and season player minutes 2010-26 | `data/ingestors/ncaab_archive_import.py`, `ncaab_sdv_import.py` |
| Feed probe | Which NCAAB events the odds feed lists and which names fail to resolve; which markets each book prices; whether the football data key opens College Basketball Data | `scripts/ncaab_feed_probe.py`, job `ncaab_feed_probe` |

## Data accounts and sources (measured 2026-10-28)

- **cbbdata (Torvik's API).** Account created 2026-10-28 (mike: "articulate the
  cbbdata sign-up with your email") and re-registered 2026-10-29 under the
  dedicated sign-up mailbox (mike: "change email for signups"): username
  `signalbaseskinny`, no confirmation e-mail required; the first account
  (`malkatrazz`, personal Gmail) is superseded and its values are kept as
  `CBBDATA_OLD_*`. The password and API key are in the local `.env` as
  `CBBDATA_USER`, `CBBDATA_EMAIL`, `CBBDATA_PASSWORD`, `CBBDATA_API_KEY`; they
  are NOT on the worker yet (Railway variable, mike's or an OAuth grant). Calls are
  `https://www.cbbdata.com/api/<endpoint>?key=<key>&year=2025&team=Duke` and
  return Parquet. Measured: `torvik/ratings/archive` holds daily T-Rank
  ratings for 364 teams per date for the seasons 2014-15 → 2024-25 (2024-25:
  232 dates, 2024-11-02 → 2025-06-30, 84,383 rows; columns rank, team, conf,
  record, barthag, adj_o, adj_d, adj_tempo, wab, proj_record, date, year);
  `torvik/ratings` holds season-end ratings 2008 → 2025; `torvik/game/stats`,
  `torvik/game/factors` and `torvik/player/game` answer for 2024-25;
  `torvik/team/schedule` is 404 and `torvik/game/prediction` 500. **The
  2025-26 season (`year` 2026) returned zero rows everywhere** — the API has
  no current-season Torvik data as of 2026-10-28, the package's issue tracker
  has had "No Bart Torvik Data for 2025-26 Season" open since 2025-11-11 with
  no maintainer reply, and two independent projects report the API stopped
  updating after June 2025, so nothing says it will return. The archive serves
  backtests; current-season ratings come from Torvik's own season file
  (`https://barttorvik.com/2027_team_results.csv`, HTTP 200 on 2026-10-28),
  which his robots.txt lets general agents fetch (Load-bearing facts below).
  Terms of use: none exist in writing for cbbdata or for Torvik's data; mike,
  2026-10-29: no permission requests to any data source.
- **KenPom.** The API subscription is $145.00 for 12 months with web access;
  web-only is $24.95 and has no data feed (live pages read 2026-10-28 23:34Z;
  the API page read $95.00 in June 2026). mike buys it in his own browser
  under the sign-up mailbox; the key then goes into the local `.env` and the
  worker as `KENPOM_API_KEY`, and the checks in the hand-off doc run. Eleven
  endpoints, the daily archive and preseason ratings included; no player
  availability. No permission request (mike, 2026-10-29).
- **College Basketball Data (api.collegebasketballdata.com).** Matt's
  question, answered by the feed probe on the worker (`ncaab-feed-probe-2026-10-26`,
  2026-10-28 23:25Z): **the football data key opens it.** `/teams` season
  2027 → 365 records; `/games` 2026 Duke → 38; `/lines` 2026 Duke → 38 with
  providers ESPN BET, Bovada, DraftKings, consensus, teamrankings,
  numberfire; `X-CallLimit-Remaining` 121,421. Lines coverage by season,
  plays, lineups and substitutions are unmeasured — the next probe.
- **The odds feed, first look (same probe).** 7 NCAAB events listed for
  2026-11-01 → 11-03; every one of 7 books prices h2h, spreads and totals;
  FanDuel also listed first-half, second-half, team-total, alternate and
  player-points markets on one game; BetRivers and Hard Rock alternate lines
  and odd/even; William Hill first basket. 14 of 14 feed names were
  unresolved only because the ESPN registry was still empty (the schedule
  job runs after the probe).
- **First night, measured 2026-10-28 23:36Z.** 747 ESPN teams and 3,491 games were stored within six minutes of the schedule job starting; the 5-minute capture resolved all 7 listed feed events onto ESPN rows (one of them flipped: the feed's "High Point @ Liberty" is ESPN's `NCAAB_2026-11-01_liberty_high-point`) and `latest_odds` held 143 prices from 7 books.
- **The purchase floor is 300,000 credits** (lowered from 500,000 on
  2026-10-28, mike: "dont stop the spend"): 3.5 of October's worst organic
  days (84,534 on 2026-10-04, `odds_api_quota`). The refill lands between
  the last day's 23:50Z reading and roughly 01:00Z on the 1st (Sept and Oct
  both show a full day's burn by the 1st's 23:40Z reading), so the resumes
  fire at 06:00Z–06:20Z on 2026-11-01 with 2026-11-02 copies as backstops.

## Load-bearing facts

- **Sign conventions.** `scored_line` / `spread_home` is the HOME number
  (CLAUDE.md §4). The Prediction Tracker's sign is the reverse (+3 means home
  favoured); the importer stores `-line`.
- **SBRO's second-half score is regulation only.** Grading a second-half total
  on it shows a phantom under edge (46.25% overs, against 50.04% with overtime,
  SBRO 2015-19).
- **Overtime** happens in about 6% of games: in full-game and second-half
  markets, never in first-half ones.
- **Player availability** has no free structured feed. Official reports exist
  for Big 12, ACC and SEC conference games (and the NCAA tournament pilot).
- **Torvik's robots.txt** (read 2026-10-29) bars six named crawlers, ClaudeBot
  and anthropic-ai among them, from the whole site, and every agent from the
  time-machine pages, `db.php`, `box.php`, `results.php`, `playerstat.php`
  and `.json` files; general agents may fetch the season CSVs with a
  10-second crawl delay. cbbdata holds nothing after 2024-25. The headline
  projection in his schedule files is rewritten after games (61.8% against
  the line in 2025-26) and must never be used.
- **College player props** are barred in 13 states (Unabated, 2026-07-29).
