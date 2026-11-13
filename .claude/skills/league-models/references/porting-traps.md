# Porting traps: what a copy of existing code got wrong on a new league

Steps 2 and 3 of `SKILL.md`. Each trap below was found only by **running the
code on the new league's stored data** — never by reading it. A rename of a
working module is never enough: when the women's college game was built from
the men's code, a replay of the new card found five copy errors in one day,
every one of them invisible in review (`docs/sports/ncaabw.md`, "What a
straight copy of the men's card got wrong").

**So the rule: the new league's card replays its own research bet for bet
before it ships** (largest edge difference in that build: 0.00000004). Then go
down this list.

## Schedule and identity

- **How far ahead is the schedule stored?** The women's college schedule was
  stored 14 days ahead, so no team had enough games for its rating and every
  team was pooled into one. Hockey's `games` held 2 future rows (it was built
  from the odds feed, 25-35 hours before puck drop) while basketball held
  1,200. Load the whole season; make the card fail loudly when the schedule is
  short. Check each October that the new season is loaded.
- **Rest comes from the stored schedule**, through `data/schedule_context`,
  never from played games (`shift(1)` over game logs is the bug). A pre-game
  model never decides while a team still has an earlier game to play or log.
  Doubleheaders that share one `game_id` hide the second game from that gate.
- **Two start times.** The feed's start can differ from the league's (about 10
  minutes later in pro basketball; ESPN was 5 hours early on some games). A
  start the feed revises lets an in-play quote count as the close.
- **Team identity.** ESPN gave a school's women's team its men's team id; the
  feed named women's teams the men's way ("Cowgirls" became "Cowboys", "Lady"
  dropped); three-letter ids collided (two schools became `WIL`); accents broke
  a mapping ("Montréal"). Build a name census against the feed before the
  first pull, and a per-league identity table.
- **Neutral sites.** The feed may call our away team home. Swap names first and
  store our home team's number. `scored_line` is always the home number.
- **A league's own neutral flag can be wrong.** EuroLeague's is false on the
  Israeli clubs' and Dubai's relocated "home" games (Belgrade, Sofia, Cyprus,
  Sarajevo; attendances of 102 to 3,428 read by the scout). Tell a relocated
  home game by its arena against the club's own (`docs/sports/euroleague.md`).
- **Duplicate and orphan games.** Night games get Eastern/UTC twins; backfills
  mint ids with no score. Match an odds `game_id` to the scored row on both
  team names within a day (532 same-way and 26 home/away flipped in one
  season's college football ids), or a third of the games drop out.
- **Namesakes.** Two players with one name produced +89.8 units of fake prop
  profit. Key players on an id, never a name.
- **Season labels** differ by sport (year of play, or ending year): thread the
  season explicitly, never derive it from a date.

## The odds feed

- **A sport the feed sells per tournament** (tennis) has no fixed key: read the
  key list from the feed, and find each key's windows (`market-grid.md`, the
  sweep). One key held a stray listing two months after its real event, so a
  sweep that finds only a year's last window misses the real one.

- **History depth per sport key.** The women's college key starts 2024-11-12:
  two seasons, so "walk-forward" means one season. Ask the feed at several
  early dates before planning.
- **The feed keeps no snapshot while nothing moves**, and a request for a time
  with none is answered, and billed, with the one before. Walk
  `next_timestamp`.
- **Regions multiply the bill**: books spread over two regions bill twice.
- **A purchase runs only once its source is protected in production.** The
  odds clean-up thins every unprotected row to an opener and a close, and
  `PROTECTED_SOURCES` is code, so merge the groundwork before buying at scale.
- **The credit planner refuses a whole-history plan at its worst case** (every
  5-minute slot of every day), even when the measured cost fits; feed it
  chunks, newest season first, and let the live meter stop at the floor.
- **One long transaction of single-row writes from mike's PC** lost its
  connection in the fourth season of seven; `executemany` wrote all seven in
  31 seconds.
- **`odds` filtered on `source` alone scans the whole table** (16 GB; it
  timed out on the read-only connector): read it through the league's game
  ids.
- **Change-only capture** keeps an old stamp on an unchanged quote; a
  fetch-name label can collide so a pull never decides; a purchase can keep
  the last listed pair per book rather than the main number (ladder rungs
  mistaken for main lines).
- **A listed start that moves, and one that lies** (tennis, 2026-11-13). In a
  sport scheduled by order of play the feed's start is an estimate: revised on
  13 of 16 trial matches, up to 29 hours early for an unscheduled next round,
  once 10 minutes after the real start. Bound on the earlier of an
  independent start (ESPN's) and the feed's last listed start, with a margin.
- **"Open" rows written after the start.** 35% of one league's `open` rows and
  23% of one prop market's were received after tip or first pitch. Bound on
  `snapshot_at <= commence_time` and exclude `in_play`.
- **Typos and broken quotes.** A total of 1465.0; one-tick-wrong lines at one
  book; non-monotone ladders; a book's line mispaired with another's price
  (a coherence filter — implied probabilities summing to 1.00-1.15 — took one
  rule from +31.1% to -0.9%). Every reader goes through quote-bounds guards.
- **A main key holding an alternate rung.** The feed served BetMGM's 2026-27
  EuroLeague first-half spread as one number at +160/-235, 2+ points off every
  other book on all 104 games, under the main key. Treat a "main" number whose
  two prices are far from even as a rung before reading any per-book result
  (`docs/euroleague_market_audit.md`, round 1).
- **Missing books.** No Pinnacle, Bovada or betPARX on the women's college
  board; two books dropped first halves in one season; no two-way college
  props at two books. Know which books exist before designing a cross-book
  rule.
- **Markets the feed serves differ by league** even within one sport: probe
  them (`references/market-grid.md`).
- **The in-play snapshot is served minutes before the asked instant** (261 to
  300 seconds, men's college).

## Scores, periods and settlement

- **Settlement differs by book, not only by sport** (tennis, 2026-11-13).
  DraftKings voids a moneyline bet on a player who retires after the first
  set; Pinnacle, FanDuel and BetMGM grade it a loss; Caesars voids any
  retirement. Read each decidable book's own rules page before grading, and
  grade each book's bets at its own rule (`models/tennis_common.py`).
- **A source's format field can be wrong.** ESPN's tennis `format` says five
  sets for best-of-three events (the women's US Open, Shanghai); best-of comes
  from the tour and the event. ESPN's men's scoreboard also returns the
  women's matches of a joint event, so key rows on ESPN's match id.

- **Overtime.** The women's game has four quarters and overtime is ESPN's
  period 5 or later; the men's rule (period 3 or later) would have marked every
  women's game as overtime. Hockey's 3-way: a draw wins if the game went to
  overtime. Team totals settle on the full game.
- **Regulation-only scores in an archive** (one archive's second half
  excluded overtime) produce a phantom under edge.
- **Pushes.** Whole-number lines push; one grader had counted pushes as under
  wins.
- **Two box-score sources** for one league will both be counted unless one
  key is chosen; ESPN's game id may not be stable enough to be the key.
- **Derived stats disagree with official ones** (possession estimates 0.30 to
  0.46 below the official count; one season's box counting end-of-quarter
  heaves another season did not). Validate against the official number.
- **A stats column missing from one season's file.**
- **The target must count what the book grades** (`references/kill-tests.md`).

## Play-by-play and in-play state

- **Play order is not time order** (83% of games in one league), and **the last
  play logged is not the score**: late-entered plays carry an old running
  score. Read plays by wallclock, sort ties by (wallclock, play number), and
  take the running maximum of each team's score. 54 research bets carried a
  wrong halftime score and went -10.71 units before this was fixed.
- **Wallclock faults**: an hour's jump on the daylight-saving night (drop jumps
  of 45+ minutes), logging stalls (74 plays stamped in two seconds), archives
  whose timestamps are last-edited times, not event times.
- **Half-time scores rebuilt from plays** need two reads that agree (never a
  maximum over the half: scores get taken back) and a check against an
  independent source (99.1% equal to ESPN in one rebuild).
- **Score-feed lag.** Measure it against the book (median 75 seconds behind
  DraftKings in one league; 23 seconds after the snap in another).
- **Read state from play-by-play time, never from `commence_time`.**

## Leakage

- **Season-final numbers under a season-start date.** Two baseball stats
  tables carried each season's final numbers on every row; AUC fell from about
  0.61 to 0.53 when the leak was removed. Check `count(DISTINCT as_of_date)`
  per season and that no entity-season value is constant.
- **Postseason games numbered week 1** leaked January into September.
- **Lower-division opponents** inflated home advantage by about 80% in one
  league until handled.
- **Shuffled cross-validation** puts one game's plays on both sides of a fold:
  group folds by game and order them in time.
- **A feature constant in training** is not a feature; **a column always null**
  deletes the training matrix under `dropna`; **a missing feature at score
  time is never 0.0** (props go through `models.scorer.prop_feature_matrix`).
- **A forecast series that starts late**: issued forecasts existed only from
  2024-01-18 in one source; anything earlier is observed weather and leaks.
- **Text timestamps** in mixed shapes: parse before comparing.

## Thin data and the first weeks

- **Too few priced games in a month** for its own fit (218 in one November,
  against 300 needed): fall back to the every-game fit.
- **Line ranges copied from another league** dropped 274 real rows.
- **The first week** carries last season's final totals and league-average
  starters. Grade the early window against the rest before proposing any hold:
  the proposed hockey hold was wrong when measured, and two basketball leagues
  were told "no 10-game wait" by mike.
- **A first-come cap** ("lock the first qualifying quote") can fire far more
  often live than in the backtest (18% of games against 3.5%), because the live
  path sees many more quotes. Replay the live cadence.
- **Fetch cadence changes the bet list.** Only a handful of in-play research
  bets were the same bet at the loop's real fetch times.

## The app and the ids

- **Prefix matches**: `startsWith('ncaab')` also matched `ncaabw`.
- **A market word inside a model id** ("spread" in a moneyline model's id) led
  code to read the market wrong. `picks.prop_market` decides which column
  settles a pick; take the market from the model, never hardcode it.
- **A scorer's clear can delete other writers' rows** (dead-zone rows of
  another model on the same game).
