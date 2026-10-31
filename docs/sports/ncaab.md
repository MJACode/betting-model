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
| Opener capture | Every 5 minutes, change-only (a row is written only when a book's price or line moved), so the time each book first posts is known | `scripts/ncaab_odds_capture.py`, job `ncaab_odds_capture` |
| Price-path retention | NCAAB keeps every book's whole price path (the clean-up job only removes unchanged middles), and the close it keeps for any sport is the last price before the start | `data/prune_odds.py` (`PATH_KEPT_SPORTS`) |
| Paid history | Game lines 2020-21 → 2025-26 (bulk snapshots: the evening before, mid-morning, and the hour before every tip); first-half and team-total lines 2023-24 → 2025-26, opener and close. Unmatched events are kept raw in `ncaab_odds_unmatched`, never dropped | `data/ingestors/ncaab_odds_history.py`, job `ncaab_odds_history` |
| Free history | Prediction Tracker lines and systems 2004-26, SBRO lines 2007-21 (matched onto ESPN games by date and final score), NCAA possession box scores and season player minutes 2010-26 | `data/ingestors/ncaab_archive_import.py`, `ncaab_sdv_import.py` |
| Feed probe | Which NCAAB events the odds feed lists and which names fail to resolve; which markets each book prices; whether the football data key opens College Basketball Data | `scripts/ncaab_feed_probe.py`, job `ncaab_feed_probe` |
| Replay of kept raw events | Stores the kept raw events that resolve now; no paid call (Replaying the kept raw events, above) | `data/ingestors/ncaab_odds_history.py --replay-unmatched`, job `ncaab_odds_history` mode `replay_unmatched` |
| Box and period scores (2026-27 on) | Each final's team box score into `ncaab_team_game_stats` (source `espn_summary`) and its half and overtime scores into `ncaab_period_scores`, one ESPN game summary per final, on the hourly refresh passes after the results step (Box scores and period scores, below) | `data/ingestors/ncaab_espn_box.py`, step `ncaab-box`; backfill job `ncaab_box_backfill` |

## Box scores and period scores (ESPN, from 2026-27)

**Why.** The rating models refit on `ncaab_team_game_stats`: possessions,
points, shooting, rebounds and turnovers per team per game. Until
2026-10-30 its only source was the sportsdataverse season files (NCAA's own
play-by-play), which have no 2026-27 file and no in-season build. ESPN's free
game summary carries the box score, so the table now fills as the season is
played. `data/ingestors/ncaab_espn_box.py` is the writer.

**What it stores, per final game, in one transaction:**

- Two rows in `ncaab_team_game_stats` with source `espn_summary`.
  `contest_id` is `espn:<ESPN event id>`; NCAA's contest ids are digits only
  (all 188,424 rows, 2026-10-30), so the two sources never share a key.
  `team` is the school name `games` carries. Filled: points for and against,
  FGA, FGM, 3PA, 3PM, FTA, FTM, offensive and defensive rebounds, turnovers,
  assists, blocks, the game's length in `mins` (40, plus 5 per overtime),
  ESPN's team and event ids and the possession estimate below. Left empty,
  because ESPN has no equivalent: shots at the rim, `e_poss`,
  `time_per_poss` and NCAA's team id.
- One row per period in `ncaab_period_scores`: periods 1 and 2 are the
  halves, 3 and later the overtimes, in the stored home/away orientation.
  `source` names the ESPN endpoint (`espn_summary` here, `espn_scoreboard`
  from the backfill).
- A game it will not store gets a row in `ncaab_box_misses` instead: the
  reason and the attempt count.

**When it runs.** Step `ncaab-box` on the hourly refresh passes, at :17
from midnight to 5 am and from 7 am to 5 pm ET, after the `ncaab-results`
step that writes the finals it reads (and after settle, since nothing settles
off it). Not on the 10-minute evening passes (6 to 11 pm ET): those already
take 455-526 seconds (median and 90th percentile, `pipeline_runs`, 7 days to
2026-10-30) of their 600-second tick, and a pass that overruns makes the next
one skip. The evening's finals are stored from the 12:17 am pass on; nothing
reads them sooner. It looks at the finals of the last 3 ET dates that have
no `espn_summary` row, newest first. A pass takes at most 80 games and about
150 seconds of fetching (checked before each call), one request at a time
with 0.3 seconds between them; the rest wait for the next pass. With nothing
due it makes no ESPN call.

**The possession estimate.** ESPN's summary has no possession count, so
`o_poss` is each team's box-score estimate, FGA − offensive rebounds +
turnovers + 0.475 × FTA, and `d_poss` is the opponent's (one team's `o_poss`
is the other's `d_poss`, as in NCAA's rows). It is NOT NCAA's play-by-play
count. Against that count in 2020-21 to 2025-26 it runs 0.30 to 0.46
possessions a team-game below it (the mean, by season), with a mean absolute
gap of about 1.2 a team and a correlation of about 0.967; averaged over the
two teams of a game the correlation is 0.978 and the gap about 1.0. Given to
the frozen rating model in place of NCAA's count it left totals error where
it was (13.638 against 13.644 points, 2012-19). Measured in the NCAAB
research round (`poss_agreement.csv`, `poss_substitution.csv`, 2026-10-30);
the per-team figures were measured the same day on the research copy of the
stored NCAA rows (188,424 rows, 2010-11 to 2025-26).

**Two sources, one game.** If a game is ever held under both sources (for
example a sportsdataverse 2026-27 file appears), it has two pairs of rows
with the same `espn_game_id` and different `contest_id`. Keep one source per
game, both of its rows, NCAA's where it holds the game. This query keeps
every row of the table today (188,424 of 188,424, read 2026-10-30) and runs
as printed on Postgres and in the tests:

    SELECT * FROM (
      SELECT s.*, RANK() OVER (
               PARTITION BY COALESCE('espn:' || s.espn_game_id, s.contest_id)
               ORDER BY (s.source = 'sportsdataverse_ncaa') DESC) AS source_rank
        FROM ncaab_team_game_stats s) ranked
     WHERE source_rank = 1;

Two traps it avoids:

- **Older seasons have no `espn_game_id`.** NCAA's rows carry none before
  2022-23 (138,338 of 188,424 rows). A query that requires one keeps only the
  last four seasons, without an error. The game key is the ESPN id where the
  row has one and the `contest_id` where it does not.
- **A non-Division I team has no `team_espn_id` in NCAA's rows** (8,854 rows),
  and this feed fills it (Hawaii Pacific is 2269). A query keyed on the team id
  would keep three rows of such a game, NCAA's two and ESPN's row for that
  side. To match one side across the two sources, use the game and `pts`.
  No game ends level, and the two sources' points agreed on every row
  compared. Not the team id: in 31 of NCAA's 25,054 games from 2022-23 on,
  neither row has one. Not `is_home`: at neutral sites the two sources can
  disagree (below).

A reader that matches on date and team pair and drops duplicate keys (the
research prep does) would lose such a game rather than choose, so choose the
source first.

**Four more columns follow each source's own rules.** Measured 2026-10-30 on
2025-26, NCAA's rows joined to the stored events and games (12,047 team rows):

- `team`: this feed writes the name `games` carries ("Arizona State"), NCAA's
  rows carry NCAA's ("Arizona St."). They differ for 121 of 365 schools. Key
  a team on `team_espn_id`, never on `team`.
- `is_home`: this feed follows the stored event, NCAA its own home team. At
  neutral sites they disagree: 74 rows, 37 games, every one neutral.
- `game_date`: this feed uses the ET date from `games`, NCAA its own. Tips at
  03:59Z or 04:59Z land a day apart: 48 rows, 24 games.
- `mins`: this feed writes 40 plus 5 per overtime, NCAA the measured playing
  time (season means 39.50 to 39.69). A pace per 40 minutes moves about 1%
  across the boundary between the sources.

`ast` and `blk` are stored as ESPN reports them. In a 10-game check against
NCAA's rows, assists matched on 20 of 20 team rows and blocks on 19 of 20.

**What it refuses.** A summary that is not final, names other teams than the
stored event, or lacks any of the shooting, rebound or turnover numbers; a
box whose points are not 2 × FGM + 3PM + FTM; an ESPN final that differs
from the stored one (the stored final settled the picks); period scores that
do not sum to the stored final, differ in count between the teams, or
disagree with `went_to_ot`. Nothing of a refused game is stored. It is tried
again after 50 minutes, at most 6 times. A 404 for a game is a miss. A 403
or 429 stops the pass's run and turns the step red, since ESPN has blocked
the worker before. So does the first fetch that fails outright (no answer
after the fetch's own retry): the next pass is the retry, so an ESPN outage
costs one fetch a pass, about 46 seconds at worst. The season backfills stop
after three.

**When every game is refused.** If ESPN changes its game summary (a renamed
statistic, a moved endpoint), every game is refused, and each one alone is
only a miss. So after each pass the step counts the newest finals of the
3-date window that ESPN answered for and that were refused, back to the
newest one stored. Five in a row turns the step red (`espn-box-refused` in
the log, the step named in `pipeline_runs`). It stays red on every pass,
including passes with nothing due, until a game is stored again. Counted from
the stored rows, it catches a break that arrives one game a pass, and it
stays green while an occasional bad game is retried behind newer stored ones.
The refused games use up their 6 attempts meanwhile; once the cause is fixed,
the box backfill (`--box`, or the `ncaab-box-scores-2027` declaration
switched on) fetches them again, ignoring the misses.

**Measured 2026-10-30, 25 games of 2025-26 (`summary?event=`).** Every call
answered 200 in 1.00 s on average (max 1.12 s), 447-566 KB each. On the 49
team rows NCAA also holds, every one of points, FGA, FGM, 3PA, 3PM, FTA,
FTM, offensive and defensive rebounds and turnovers matched NCAA's number;
points = 2 × FGM + 3PM + FTM and the periods summed to the final on all 50.
One scoreboard date (2026-02-07, 155 events) carried every period,
overtimes included, and every completed side's periods summed to its score
(310 of 310).

**Backfill.** `python -m data.ingestors.ncaab_espn_box --periods --seasons
2021 2026` reads one scoreboard per date and stores the period scores of
every final with none (855 dates, 35,323 finals in 2020-21 to 2025-26,
counted 2026-10-30). `--box --seasons 2027 2027` fetches a summary for every
2026-27 final with no ESPN box row. Both skip what is stored. On the worker:
job `ncaab_box_backfill` with `{"kind": "periods", "first": 2021, "last":
2026}` or `{"kind": "box"}` (box is held to 2026-27, the season NCAA's files
do not cover). Both are declared in `jobs/declared_jobs.json`.
`ncaab-period-scores-2021-2026` ships ON (mike, 2026-10-30), so the worker
queues it once on its first tick after the merge. `ncaab-box-scores-2027`
ships off. Turning it on is one line: set `enabled` to true and merge. No test
pins either switch, and the NCAAB credit-approval test leaves this free job
out. The ESPN schedule backfill made the same kind of calls on the worker on
2026-10-28/29: 17 seasons, one scoreboard per date, about 13 minutes a season,
all 17 done.

**The research round's halves file.** It held first- and second-half scores
for 36,796 ESPN events of 2020-21 to 2025-26, on one laptop only. It is not
imported: it keeps the two halves and a period count but not each overtime's
score, and it was built by a script outside the repo. The period backfill
re-reads the same ESPN scoreboards through the repo's own code, so every
stored row names its endpoint.

## In the app (2026-10-30)

- **NCAAB is a sport chip beside NCAAF** on the Picks, Models and Stats tabs
  (`mobile/src/hooks/useSportFilter.ts`). A push that names NCAAB opens its
  board, because the push router accepts only the sports on that list.
- **A model whose id starts `ncaab` is filed under NCAAB.** Before this, the
  app had no `ncaab` prefix and filed every such model under MLB
  (`modelMeta.sportOfModel`, and its copy in `ModelsScreen`).
- **The totals model's label is "NCAAB Totals", badge O/U, under the id
  `ncaab_total_blend`**, the id the model writes its picks under
  (`models/ncaab_total_blend.py`). The app first used `ncaab_over_under`, the
  id in the model's build plan; no model writes that id. If config scores an
  id the app has no label for, `tests/test_mobile_pick_categories.py` fails.
- **It is priced off the `totals` rows because it is named.** An id with
  `over_under` in it reaches the totals rows on its own; `ncaab_total_blend`
  does not, so `markets.gameMarketForModel` names it (else every price,
  movement and line-shop lookup reads the moneyline rows), and so does
  `marketClassForModel` (else a parlay treats it as independent of the same
  game's other legs).
- **Its page and its picks say when it decides.** The model page says it
  decides each game once, the evening before, at DraftKings' total, and that a
  posted bet is never re-priced (`modelMeta.modelPageTiming`). It prints no
  Eastern clock time: the card runs at 22:00 UTC, which is 6pm ET until
  1 November and 5pm ET after it. Pick Detail says "Posted" once, not "the
  first scoring run of the day" (`markets.pickTimingInfo`). A row for a game
  that is not today shows its day as well as its time, as the Signals card
  does.
- **The Today board reads NCAAB picks up to 7 days ahead**
  (`fetchUpcomingNcaabPicks`), because the totals model decides the evening
  before the game. It reads the picks first, then only those
  picks' games and lines, 80 game ids per request. Reading the whole window
  instead would have been too big: over 2025-26 the biggest day held 4,417
  main-market rows across all books, and the biggest seven days held 10,424
  (Supabase, read only, 2026-10-30).
- **Today's DraftKings lines are read in pages, main markets only.** The
  same-day read was one request, and a full college basketball day went past
  the 1,000-row response cap: 1,132 DraftKings rows for 2026-01-10, of which
  743 were in the markets a pick reads. Past the cap the server returns an
  arbitrary 1,000 rows without saying so, which could blank any sport's line
  pill.
- **When a game leaves the board.** Three hours after the tip if ESPN's final
  has not landed by then (`format.GAME_DURATION_HOURS`); it stops reading
  LIVE on the clock alone after four (`BLIND_LIVE_WINDOW_MS`).
- **Not in the app yet.** NCAAB player and team stats (the Stats tab shows its
  "No player leaderboard" state, and every Stats read returns nothing for
  NCAAB before it asks the server). School abbreviations: cards show the
  school name, because the app cannot read `ncaab_teams` (anon has no SELECT
  on it, RLS is on and it has no policy; read only, 2026-10-30). Opening it is
  a worker-side change as well as an app one: the code that creates the table
  (`data/ingestors/ncaab_teams.py`, `ensure_tables`) re-runs its create and
  lock-down whenever it finds anon holding a grant, so a grant alone would be
  revoked the next time that runs. Every school name on the games from 1 to
  8 November matches `ncaab_teams.school` (492 of 492). Nine school names
  appear twice in `ncaab_teams`, six of them with two different
  abbreviations, so those six must keep the school name. Live scores and the
  Scoreboard: the live scoreboard poller (`data/ingestors/live_scoreboard.py`)
  does not cover NCAAB.

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
