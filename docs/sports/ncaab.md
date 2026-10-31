# NCAAB — men's college basketball: data, odds capture, models

> **Started 2026-10-26 (mike: "built an ncaab model - season starts early
> nov"; the brief was rewritten into a build prompt and he answered "1) yes,
> 2) yes, 3 approved").** The 2026-27 season opens Sunday 2026-11-01 (Notre
> Dame vs Villanova, Rome, 9:30 a.m. ET); the full US slate starts Monday
> 2026-11-02 (182 games on ESPN). Season label: the ENDING year (2026-27 is
> 2027), as ESPN labels it, like the NBA and NHL.

## The models

### The NCAAB totals model (`ncaab_total_blend`), live from 2026-10-30

mike, 2026-10-30: *"Yes to the totals model."* Real money, like every model
(CLAUDE.md §2). Code: `models/ncaab_total_blend.py` (the model),
`scripts/ncaab_total_card.py` (the card that writes its picks),
`scripts/ncaab_total_blend_build.py` (the frozen numbers),
`models/saved/ncaab_total_blend_2027.json` (those numbers for 2026-27).

**What it does, per game, as of the moment DraftKings' total is read:**

1. **Ratings.** Every team's offence, defence and pace, refit on this
   season's finals that had ENDED (tip + 2.5 hours) by DraftKings' own time on
   the quote, rounded down to the hour. Recent games weigh more (half-life 45
   days). The starting point is last season's final rating, carried at 0.72
   (scoring) and 0.9 (pace); a team new to Division I starts near the bottom.
   A team with fewer than 10 games on the schedule is pooled into one "other"
   team. Possessions are the box-score estimate (field-goal attempts minus
   offensive rebounds plus turnovers plus 0.475 free-throw attempts, the two
   teams averaged), because that is all the in-season ESPN feed gives. It runs
   0.30-0.46 possessions a game below NCAA's play-by-play count.
2. **A correction for luck and style.** A fixed linear adjustment on each
   team's three-point and free-throw percentages made and allowed so far, and
   its free-throw rate, three-point attempt rate, offensive-rebound rate and
   turnover rate, each pulled toward last season's league rate. Fitted on the
   2012-2026 seasons.
3. **Blended with DraftKings' total:** mean = line + c + beta x (model −
   line), normal spread sigma, with c, beta and sigma fitted separately for
   November and for December on, on the paid seasons 2021-2026.
4. **Priced at DraftKings' own two prices** on that total: the chance the bet
   wins, a push left out, minus the price's implied chance. The better side
   is bet when that edge is above **0.04**. DraftKings only: the evidence
   priced DraftKings and nothing else, so the line is not shopped.
5. **Both teams 10+ games** that ended before the quote (CLAUDE.md §3).

**When a game is decided.** The evidence bet DraftKings' FIRST stored total,
and the history it bought was snapshots at 22:00 UTC the evening before, at
15:00 UTC on the day and the hour before tip. So the card (hourly at five
past, UTC) decides a game at 22:00 UTC the evening before its date if
DraftKings has a total up then, else at 15:00 UTC on the day, else at each
hour after until tip. "Up" means DraftKings' newest pre-game row was stored in
the last 90 minutes. The decision, bet or not, goes into
`ncaab_total_decisions` with the quote, the cutoff and the reason, and the game
is never decided again (CLAUDE.md §1c). Only BET rows go into `picks`.

**A hold is not a decision.** A game waits for its next decision hour while
either team has, among its games that ended before the quote, one from the
last 36 hours without a final score or both box rows (`box_pending`), or two
or more older ones without them (`box_missing`). One older game without a box
does not hold (the evidence also had a few games with no possessions). The
boxes come from the ESPN box feed (`data/ingestors/ncaab_espn_box.py`, source
`espn_summary`, PR #1103). **Before that feed runs no box is stored**: a
team's first game, and its second if the first ended more than 36 hours
before the quote, is decided `below_10_games`, which is final; from the third
game on its games hold. Nothing reaches 10 boxed games, so nothing is bet
(measured 2026-10-31 on the tests' synthetic season with no box rows, games
three days apart).

**A run that cannot decide a due game fails.** `box_missing` can hold a
team's games all season, so it fails the run, as do an artifact built for
another season and a missing blend. The card first decides and writes every
other game, then exits 1: the job's heartbeat records `error` and the failure
alerter reports it (`CardIncomplete` in `scripts/ncaab_total_card.py`). The
worker log names the games and the teams.

**One box source per game.** The game key is ESPN's game id where the row
has one, else its contest id. Where NCAA's play-by-play rows hold a game, only
they are kept, both of them; otherwise the ESPN feed's rows. This is the source
rule the box feed (#1103) documents for `ncaab_team_game_stats`: choose the
source first. Never by team id: in 145 of NCAA's games (31 from 2022-23 on)
neither row has one (Mercy at FDU, 2022-11-09), and a key on the team id kept
one row of each, so its possessions were one team's estimate and the hold
counted it unboxed. Fixed 2026-10-31; the frozen numbers were rebuilt with it.

**Under the 10-game rule it has never bet in November.** Expect a card of
`below_10_games` decisions and no bets until about the first week of December.

| Setting | Value | Where |
|---|---|---|
| the cut | edge > 0.04 (P(win, push left out) minus DraftKings' implied) | `config.MODEL_EDGE_THRESHOLDS` |
| prob / edge filter | 0.0 / 0.04: the edge filter IS the card's cut, because model_probability is that same P(win, push left out) | `ACTION_THRESHOLDS` |
| EV floor | 0.07, just under the smallest EV the cut admitted on 2021-2025 (+0.0743; median +0.0996), on its own probability | `MODEL_OWN_EV_FLOOR`, `MODELS_ON_OWN_PROBABILITY` |
| price floor | -200, pinned (it laid -120 to +102) | `MODEL_MIN_ODDS` |
| decision hours | 22:00 UTC the evening before; else 15:00 UTC on the day and each hour to tip | `models/ncaab_total_blend.decision_hour` |
| decided once | a row in `ncaab_total_decisions`, bet or not | `scripts/ncaab_total_card.py` |
| settlement | full-game total, overtime included | `tracking/paper_tracker._RULE_MODEL_MARKETS` |
| kill switch | `RUN_NCAAB_TOTAL_CARD=0` | the card |
| frozen numbers | built from 2011-2026 | `models/saved/ncaab_total_blend_2027.json` |

**The evidence, graded exactly as it runs live** (scratch chain of
2026-10-30: box-score possessions in every season, no returning-minutes input,
ratings and inputs as of the hour-floored DraftKings first stored total, the
10-game rule, stake_for; 95% interval resampled by date):

| Cut | Seasons | Bets | Units | ROI | 95% interval | Close EV | Seasons positive |
|---|---|---|---|---|---|---|---|
| 0.02 | 2021-2025 | 3,380 | +191.68 | +5.18% | [1.9, 8.9] | -0.80% | 5/5 |
| 0.03 | 2021-2025 | 1,983 | +118.27 | +5.45% | [1.3, 9.7] | -0.31% | 5/5 |
| **0.04** | **2021-2025** | **1,094** | **+87.48** | **+7.32%** | **[2.0, 12.7]** | **+0.27%** | **5/5** |
| 0.05 | 2021-2025 | 605 | +65.02 | +9.85% | [2.7, 16.9] | +0.58% | 4/5 |
| 0.06 | 2021-2025 | 329 | +37.53 | +10.45% | [0.6, 20.5] | +1.17% | 4/5 |
| 0.02 | 2025-26 | 1,041 | +50.25 | +4.41% | [-1.5, 10.2] | +1.58% | |
| 0.03 | 2025-26 | 631 | +28.05 | +4.07% | [-3.3, 10.6] | +2.76% | |
| **0.04** | **2025-26** | **349** | **+26.76** | **+7.03%** | **[-2.0, 16.2]** | **+3.89%** | |
| 0.05 | 2025-26 | 182 | +23.27 | +11.74% | [-2.9, 26.0] | +4.86% | |
| 0.06 | 2025-26 | 85 | +20.05 | +21.64% | [0.3, 41.8] | +8.62% | |

At 0.04 by season: 2021 +6.46% (285 bets), 2022 +10.90% (110), 2023 +21.14%
(46), 2024 +4.14% (271), 2025 +7.57% (382), 2026 +7.03% (349). Record
606-475-13 on 2021-2025 and 195-154-0 on 2025-26. Calibration error over every
scored game: 0.70% on 2021-2025, 2.72% on 2025-26. No bet in November in any
season. The round-2 research version (NCAA possessions, returning minutes) made
+6.82% on 1,085 bets at the same cut; the live inputs did not weaken it.

**The shipped code reproduces it** (re-measured 2026-10-31, after the
one-source-per-game fix and the rebuild). `scripts/ncaab_total_blend_build.py`
replays the repo's own model walk-forward (blend fit on the paid seasons before
each one) on 2022-2026: 1,157 bets at 0.04 against the evidence's 1,158, 1,147
of them the same game (mean edge difference 0.0004). 2022-2025: 809 bets,
+63.28 units, +7.17% (the evidence: 809, +67.30, +7.63%). 2025-26: 348 bets,
+25.76 units, +6.78% (the evidence: 349, +26.76, +7.03%). The build prints this
replay and stores it in the artifact. **The card's own code path** (the season
load, the hold, the refit at one cutoff, the decision) run over 2025-26 at each
game's DraftKings first stored total, with numbers built through 2024-25, writes
the same 348 bets as the build on the same sides (largest edge difference
7e-9), and holds no game.

**Where the port differs from the evidence on 2025-26, measured game by game**
against the evidence's own predictions (5,586 quoted games): the 10-game counts
agree on every game, the model totals differ by a mean of 0.011 points, and the
edges by a mean of 0.0001. The one bet the evidence makes and the card does not
is Iowa vs Ohio State, 2026-03-12, over 140.5 at -110: edge 0.039946 against the
evidence's 0.040012, at the cut. The model total does not move it (the
evidence's total with the card's blend gives 0.039943). The blend does: the
build refits c and beta on its own predictions (Dec+ c 0.721, beta 0.367,
against the evidence's 0.719 and 0.368), and the card's total with the
evidence's blend gives 0.040016, a bet. The model-total differences that remain
sit on the 22 teams that played one of NCAA's 31 games from 2022-23 on with no
team id on either row: the build places those games and the evidence never did.
Their 110 games differ by a mean of 0.158 points, every other game by 0.008,
and 18 of the 20 games that differ by more than 0.3 involve one of them.

Four defects were found by replaying the card's path or in review, and
fixed: a game against an opponent with no ESPN id was dropped from the luck
and style inputs; the same game was read as unboxed (which held 2,857 of 5,586
games); the build pooled a team by another season's schedule; and a game with
no team id on either NCAA row kept one row, which on 2024-25 would have held
Fairleigh Dickinson and Saint Francis as `box_missing` all season (five such
games each).

**The risks, plainly:**

- **92% of its bets are overs** (1,007 of 1,094 on 2021-2025; 344 of 349 in
  2025-26). Betting every over blind at the same prices lost 1.75% on
  2021-2025, so it is not just an over lean, but expect an over-heavy card.
- **Closing-line value is thin.** Close EV against Pinnacle's no-vig close is
  +0.27% at 0.04, and its interval in the research version ([-0.28, 0.90])
  includes zero. At 0.03 it is negative. The realised return runs well above
  what the close implies, which holds only if the model's information against
  the close is real.
- **2025-26 rests on its best days.** Without its 5 best dates the research
  version's 2025-26 was -0.78% (282 bets); without its 10 best, -6.88%.
- **The 10-game rule decides whether it clears.** Without it the same cut is
  +4.36% with an interval that crosses zero (research version).
- **The cut was chosen on the seasons it is graded on**, though the returns
  form a plateau (+5.18% to +10.45% across 0.02-0.06), not a peak.
- **Pinnacle had posted no 2026-27 NCAAB totals** when this shipped (seven
  books in `odds` for season 2027 on 2026-10-30), so the closing-value
  columns start empty.

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
  home number. Names resolve through ESPN's display name, "school mascot",
  school, short name, alternate names, a school that starts the name followed
  by its mascot, and last the feed's shortened school names (Feed team names,
  below). A name none of them places is dropped, counted, and fixed by an
  entry in `config.NCAAB_ODDS_API_MAP` (name -> ESPN id).
- Three-letter ids were never an option: the old fallback turned "Kentucky
  Wildcats" and "Kansas State Wildcats" into the same team (measured
  2026-10-26: `NCAAB_2026-11-03_WIL_WIL`).

## Feed team names (2026-10-29)

The odds feed shortens school names that ESPN spells out: "Michigan St
Spartans", "CSU Fullerton Titans", "Loyola (Chi) Ramblers". On 2026-10-29 82
feed names placed no team. The game-lines purchase (worker job 805227) keeps
every event it cannot place raw in `ncaab_odds_unmatched`, which then held
137,007 rows, nearly all because of those names. The job itself counted
137,083; the table keeps one row per event and feed time.

- **The rule** (`ncaab_teams._resolve_shortened_school`). It is tried only
  after every other step finds nothing, so a name that resolved before still
  resolves to the same team. The name is split into a school part and a
  mascot at every word. The school part's abbreviations are expanded (St, SE,
  Univ., CSU, Cal, Chi, Mt., BKN, Int'l; each one is there because a stored
  feed name needs it). The school part must then equal the school, short name
  or an alternate name of exactly one ESPN team, and the rest must be that
  team's mascot, or one of two aliases kept per team (Grand Canyon
  "Antelopes", Florida International "Golden Panthers"). The name resolves
  to nothing when two teams share that school and that mascot, or when two
  schools of the same length both start it (the step before this one; the
  rule is then not tried). A spelling two teams share places nothing by
  itself.
- **The overrides.** 20 names no rule can place are in
  `config.NCAAB_ODDS_API_MAP`, each with the ESPN team and how many of the
  name's events ESPN's schedule plays as that team: schools or mascots ESPN
  names differently ("Dixie State", "Houston Baptist", "IUPUI", "UMKC",
  "George Washington Colonials", "Valparaiso Crusaders", "Long Beach St
  49ers") and names unlike ESPN's ("Albany", "Fort Wayne", "Tenn-Martin").
  "LIU Brooklyn Blackbirds" is ESPN 112358, Long Island University, not the
  non-Division I row 6446 called "LIU Brooklyn": ESPN's schedule has all 19
  of its events under 112358.
- **Measured 2026-10-29.** Over 7,468 names, no name changed team from the
  resolver before this rule: every feed name in `ncaab_odds_unmatched` and
  every name form built from the ESPN registry (display name, school, short
  name and abbreviation, with and without the mascot, and the feed's
  contractions of each). 80 feed names now resolve, 60 by the rule and 20 by
  override, each to the team ESPN's schedule plays it as. Two stay unresolved
  on purpose: "Regent University Royals" and "Western State Colorado
  Mountaineers" each fit two ESPN rows.
- **The live capture uses the same resolver**, so these names now place from
  opening night too.

## Replaying the kept raw events

`python -m data.ingestors.ncaab_odds_history --replay-unmatched --seasons 2021 2026 --apply`
re-reads the events the purchase kept raw and stores the ones that resolve
now, as the purchase would have stored them: ESPN's game, ESPN's home number,
the in-play label from ESPN's tip, and the same filter of what is kept (the
first quote, the evening-before and morning anchors, and the three hours
before the tip). It makes no paid call, never writes the pull ledger, never
deletes a raw row, and does not store a quote that is already stored, so a
second run stores nothing new. Each insert into `odds` also updates
`latest_odds`, through that table's insert trigger.

- **Without `--apply` it is a dry run** that prints what it would store, and
  its database connection is read only: every transaction opens READ ONLY.
- **The raw rows carry the feed's own time** (21:55:38Z for the 22Z
  snapshot). The replay maps each one back to the hour that was bought: the
  first pull-ledger hour at or after it, within an hour. A time with no such
  hour is counted and skipped. Stored rows carry each market's own last-update
  time as `snapshot_at` (the bought hour only when the feed sends none), as
  the purchase's rows do.
- **Two differences from the purchase.** A listing whose start is 12 hours
  or more from the ESPN game it lands on is not stored. The matcher takes the
  nearest game within a day either side, so a second listing of the same two
  teams a day later lands on the same game; in the kept events every such
  game also has a listing within the hour (24 events, 144 event snapshots;
  SQL on the Supabase connector, 2026-10-29). And when the feed answered
  several bought hours with the same stale snapshot, the raw table kept it
  once, so it is replayed only at the first of those hours (2020-11-27, 18Z
  to 20Z, the one case found).
- **A write cut off at its commit is retried safely.** Each write reads
  `odds` back before it inserts, so a retry after a commit that did land
  stores nothing twice.
- **On the worker:** job `ncaab_odds_history` with `{"mode":
  "replay_unmatched"}` stores (every purchased season, 2020-21 to 2025-26);
  `{"mode": "replay_unmatched", "dry_run": true}` only prints what it would
  store. It takes no credit limit because it spends nothing.
- **What to expect.** The 2025-26 dry run, read only, 2026-10-29 23:26Z to
  23:41Z: 1,260 raw feed times, all mapped to a bought hour; 24,914 event
  snapshots, of which 24,692 place on an ESPN game, 209 do not (31 team pairs
  ESPN has no game for) and 13 (2 events) are refused as far listings; 1,956
  events placed; 484,773 rows parsed, 59,867 of them in play; 256,684 kept,
  none already stored, so 256,684 would be stored. A placed event snapshot
  parses into about 20 rows and the keep filter keeps about half of them, so
  the replay stores far more rows than event snapshots. Across the six
  seasons, SQL on the Supabase connector (2026-10-29, the new name answers)
  places 11,349 of the 11,857 kept events on 11,300 ESPN games, before the
  24 far-listing events are set aside; the dry-run job prints the rest.
- **What it stored.** Worker job 827394, 2026-10-30 04:00-04:40Z, seasons
  2020-21 to 2025-26: 7,340 raw feed times, all mapped to a bought hour;
  137,007 event snapshots, of which 133,064 placed, 3,799 not (508 events)
  and 144 (24 events) refused as far listings; 2,239,062 rows parsed,
  245,242 of them in play; 1,201,028 kept and stored, none already stored,
  no write failed. Read back from `odds` (sport NCAAB, source
  `odds_api_historical`): 1,201,028 rows on 11,296 games, every game in
  `games`, no row after its game's tip.

## What runs, and where it lands

| Piece | What | Where |
|---|---|---|
| ESPN schedule + results | Teams, venues, every game (neutral flag, conference game), finals for settlement; the daily pipeline refreshes 14 days ahead, every refresh pass fills finals for started games | `data/ingestors/ncaab_espn_ingestor.py`, steps `ncaab-schedule` / `ncaab-results` |
| Live odds | Full-game moneyline, spread and total from the ten line-shop books on every refresh pass; NCAAB is exempt from the DraftKings-must-list gate so every book's first post is kept | `data/ingestors/odds_ingestor.py` |
| Totals model card | Hourly at five past, UTC: decides each game once at DraftKings' standing total (22:00 UTC the evening before, else 15:00 UTC on the day and each hour to tip), writes the bets, then publishes them | `scripts/ncaab_total_card.py`, job `ncaab_total_card` |
| Opener capture | Every 5 minutes, change-only (a row is written only when a book's price or line moved), so the time each book first posts is known | `scripts/ncaab_odds_capture.py`, job `ncaab_odds_capture` |
| Price-path retention | NCAAB keeps every book's whole price path (the clean-up job only removes unchanged middles), and the close it keeps for any sport is the last price before the start | `data/prune_odds.py` (`PATH_KEPT_SPORTS`) |
| Paid history | Game lines 2020-21 → 2025-26 (bulk snapshots: the evening before, mid-morning, and the hour before every tip); first-half and team-total lines 2023-24 → 2025-26, opener and close. Unmatched events are kept raw in `ncaab_odds_unmatched`, never dropped | `data/ingestors/ncaab_odds_history.py`, job `ncaab_odds_history` |
| Free history | Prediction Tracker lines and systems 2004-26, SBRO lines 2007-21 (matched onto ESPN games by date and final score), NCAA possession box scores and season player minutes 2010-26 | `data/ingestors/ncaab_archive_import.py`, `ncaab_sdv_import.py` |
| Feed probe | Which NCAAB events the odds feed lists and which names fail to resolve; which markets each book prices; whether the football data key opens College Basketball Data | `scripts/ncaab_feed_probe.py`, job `ncaab_feed_probe` |
| Replay of kept raw events | Stores the kept raw events that resolve now; no paid call (Replaying the kept raw events, above) | `data/ingestors/ncaab_odds_history.py --replay-unmatched`, job `ncaab_odds_history` mode `replay_unmatched` |

## Data accounts and sources (measured 2026-10-28)

- **cbbdata (Torvik's API).** Account created 2026-10-28 (mike: "articulate the
  cbbdata sign-up with your email") and re-registered 2026-10-29 under the
  dedicated sign-up mailbox (mike: "change email for signups"): username
  `signalbaseskinny`, no confirmation e-mail required; the first account
  (`malkatrazz`, personal Gmail) is superseded and its values are kept as
  `CBBDATA_OLD_*`. The password and API key are in the local `.env` as
  `CBBDATA_USER`, `CBBDATA_EMAIL`, `CBBDATA_PASSWORD`, `CBBDATA_API_KEY`, and
  on the Railway worker since 2026-10-29 about 22:58Z (names checked with
  list-variables). Calls are
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
