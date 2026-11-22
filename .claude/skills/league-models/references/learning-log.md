# Learning log

Read this first, at step 0 of every use. Append to it last, at step 9, in the
same branch as the work. Newest entry first.

Each entry answers five questions:

1. **League and scope**: what was asked, by whom, the date.
2. **Tried**: the grid rows worked and the methods run on each.
3. **New**: each new method, trap, price route or kill test, and the
   reference file it was written into.
4. **Corrected**: each claim in the skill that a measurement contradicted, as
   "was X, now Y, because Z (doc)". A method that failed on re-measure moves to
   failed in `methods.md`; a null is never deleted.
5. **The framework**: anything in `SKILL.md` that was wrong, missing or in the
   wrong order, and what changed.

"Nothing new" is a valid entry only with one sentence saying what was checked.

**Promotion.** When the same trap or failure appears in two entries, it stops
being a note and becomes a rule: one line in the `SKILL.md` step it belongs
to, pointing here. A method that has failed in three leagues gets a warning
at the top of its entry in `methods.md`. This is the same rule CLAUDE.md uses
for itself: a trap that has bitten twice is promoted.

**Review.** At the fifth entry after the last review, read the whole log for
patterns (a step that keeps being skipped, a trap that keeps recurring, a
method that only ever works in one sport shape) and change `SKILL.md`. Log the
review as its own entry.

---

## 2026-11-22 — NHL best bet a night built as four rule cards (one bet a night)

1. **League and scope**: NHL, mike ("Yes" to building the best bet a night on the puck line,
   moneyline, regulation 3-way and total, after both goalies are confirmed, one bet a night, flat
   stake, skipping a game that already holds an NHL bet). `models/nhl_best_bet_night.py`,
   `scripts/nhl_best_bet_night_card.py`, ids `nhl_night_puckline`, `nhl_night_total`,
   `nhl_night_moneyline`, `nhl_night_regulation`.
2. **Tried**: the live code replayed over 2021-22 to 2025-26 against the research's version C
   (`scripts/nhl_best_bet_night_replay.py`): 349 bets, +62.6u, +15.3% (+2.0..+28.6), every season
   positive; 303 of the research's 323 nights the same game, market and side. A live dry run on
   2026-11-22's slate (reads only): all 5 games held for goalies at 09:41 ET; with the hold lifted
   in memory, 111 book-to-Pinnacle comparisons, none at 1% EV.
3. **New**: two traps in `porting-traps.md` (a stored start time is two clocks; a new card must be
   seen by every model on the game). The side-conflict check now works over final scores, so the
   puck line and the total joined the moneyline and 3-way (`models/scorer._SIDE_ENDINGS`).
4. **Corrected**: the first replay read +31.9u on 278 bets and looked like half the research. The
   replay was wrong, not the research: it cut at the stored start less 10 minutes, and the stored
   start is the scheduled time for many games. Cut at the scheduled puck drop, it matches.
   Two build bugs the dry run and the tests caught before any merge: the pipeline's step list did
   not accept `nhl-best-bet-night` (argparse would have refused every pass), and the price query
   named two columns `created_at` (it failed on the database every time; unit tests cannot see SQL).
5. **The framework**: step 7 gained two lines: cut a replay where the live rule stops, and a new
   card is seen by every model on the same game (promoted: EuroLeague 2026-11-14 was the first).

## 2026-11-21 — NHL, every market against Pinnacle's no-vig price (the totals rule's method)

1. **League and scope**: NHL, mike ("build models that beat the pinnacle no vig line … Yes, run
   it"), after finding the NHL moneyline loses to Pinnacle's close at every lead time. One method,
   the live `nhl_over_under` rule unchanged, run on every market the odds table stores: puck line,
   moneyline, regulation 3-way, first-period total, team totals, alternate totals and spreads.
2. **Tried**: a same-fetch replay that reproduces `nhl_over_under`'s evidence bet for bet first
   (`scripts/nhl_sharp_vs_soft_lab.py validate`), then every market at eight floors and three lead
   windows, then the kill tests on the two positive markets. Puck line: positive at every floor
   (+6.0% on 1,710 at 0.015), grading sign checked against Pinnacle's close, blind both-sides loses
   the margin, retail placebos (DraftKings, FanDuel, Bovada) all negative, quotes a median 1 s apart.
   Then it falls to +1.4% without its ten best dates and +1.5% on the power de-vig: not
   established. First-period total: +16.2% on 250 (+1.9, +30.0), still positive without its ten best
   dates and on the power de-vig, retail placebos -3.7% to +2.8%, the bet book's blind under -2.4%;
   but 88% unders and 74% at one book, one snapshot a game. The current season, bought on mike's
   go-ahead (346 games, 10,430 credits), shows that book no longer quotes the market in the feed:
   4 bets on 362 games. A one-book edge can vanish between seasons; check the book still quotes
   the market before spending on the re-test's model work. 3-way, moneyline, team and alternate totals: nothing for this rule.
3. **New**: two traps in `porting-traps.md` (the odds clean-up leaves a settled game only each
   book's opener and close, so an in-season replay is not the rule's input; bought-history rows carry
   their import time in `created_at`), and one kill test in `kill-tests.md` (grade the live
   comparator on the same test). Results in `methods.md` §2. A purchase the session's permission
   check refused (10,370 credits, a buyer mike pre-approved) was put to the user in chat, not routed
   around; it ran on his "Yes, buy them".
4. **Corrected**: `docs/data_archive.md` says the clean-up spares "the sharp books"; in `odds` it
   does not (`data/prune_odds.PROTECTED_BY_TABLE` protects Pinnacle in `player_prop_odds` only).
5. **The framework**: nothing changed in `SKILL.md`. Worth promoting if it recurs: before reading a
   neighbourhood as a plateau, run "without the ten best dates" — it moved this one more than any
   other test.
6. **Follow-up, 2026-11-22** (mike: fewer bets, 1-5 unit stakes): per market, return does not
   reliably rise with EV (the bands flip with the de-vig method), so sizing by EV mostly
   multiplies noise. Selecting ACROSS markets at one moment and keeping only the night's
   largest EV is the version that held on both de-vig methods. Run the retail-reference
   placebo on any cross-market selection: it kept two-thirds of this one.

## 2026-11-20 — NBA first basket: a market never priced, built live on a five-of-six grade

1. **League and scope**: NBA, mike after an 0-6 night ("invent a new way"). One market no NBA search
   had priced: who scores the game's first points (`player_first_basket`), and each team's
   (`player_first_team_basket`). New model id `nba_prop_first_basket`.
2. **Tried**: the structure on stored play-by-play (tip win rate split-half 0.79; the tip winner
   scores first 66.6%; a points-per-game share prices it worse than a flat fifth), a walk-forward
   fair price (beats both baselines in four unseen seasons), then three registered tests at bought
   prices (10 credits a game a market; 3,368 games): the model alone +5.9% and the books' median
   prices it better; the median alone +3.2%; a 0.25 / 0.75 blend +7.5% on 1,930 (first basket) and
   +9.5% on 1,056 (team), five bars of six, every interval below zero at its low end. mike shipped
   the first-basket blend (`docs/nba_first_basket.md`).
3. **New**: a market whose books do not agree on what settles it: DraftKings, BetMGM, Fanatics and
   BetRivers pay on the first made field goal, FanDuel, Caesars and Hard Rock on the first points.
   Read every book's house rule before grading, and settle per bet book. And a trap: this repo tells
   a prop from a game pick by `_prop_` in the model id (settlers, views, the app), so a prop model id
   without it is graded and shown as a game pick.
4. **Corrected**: was "the model is the edge" (the plan), now "the books' median knows more than the
   model; the blend is the edge", because the model alone lost to the median on log loss (0.32249
   against 0.32142).
5. **The framework**: nothing in `SKILL.md`. One note for the price step: a market priced as a set of
   names (first basket, anytime) needs each book's no-vig over its own list, and a fair price from
   the OTHER books, or the bet book's margin is in its own reference.

## 2026-11-17 — Horse racing: US Hong Kong payouts measured against the Club's dividends

1. **League and scope**: thoroughbred racing, the "whats next" after the
   daily Betfair store (#1433). The one free check the racing doc had left:
   does a US outlet's Hong Kong bet join the Jockey Club's pool?
2. **Tried**: the payout comparison `scouting.md` named on 2026-11-16. The
   Club's win, place and exotic dividends for Sha Tin 2026-11-14 and Happy
   Valley 2026-11-11 (its own results pages), against the $2 payouts Off
   Track Betting published for the same races. Result: 77 of 77 win and
   place payouts and 7 of 7 exotics equal to the cent, including a $2.02
   place payout (`docs/horse_racing_scout_us_outlets.md`, "Measured,
   2026-11-17"; `scripts/horse/hk_pooling_check.py`, which was watched
   failing on one changed payout). The site's own Hong Kong page says its
   customers can bet both tracks, in "co-mingled" pools.
3. **New**: a price route, written into `scouting.md`: a US wagering site's
   own results pages carry the payouts it publishes, for US and overseas
   tracks. Open web searches on both days found nothing; a search limited to
   the site found its results index; the fetch tool got HTTP 403; the
   browser opened the page on the first try. And a limit, written there
   too: a published payout is not a settled one (a feed converting the
   host's dividends would print the same figures). The Hong Kong archive was
   re-read the same day (US$499, one payment, refundable until downloaded;
   one-minute polls before the off in three spans, five-minute in between;
   odds only, so results and form for 2018 on come from the Club's results
   pages, which load for 2019 and 2022 dates) and the racing doc carries it.
4. **Corrected**: was "whether any US outlet still bets into the Club's
   pools is not established" (`docs/sports/racing.md`, 2026-11-16), now "a
   US site that takes Hong Kong bets publishes the Club's own dividends",
   because the payouts match race by race and the site says it pools. Still
   open: a settled bet, which other outlets, which states, and how late a US
   outlet takes the bet. The order changed too: the late-bet question only
   matters if the archive's test clears, so it is checked after the test,
   not before buying.
5. **The framework**: nothing in `SKILL.md`. One note for step 2: "two web
   searches found no page" was the stated reason for leaving a question open
   that one site's own results index answered. Search the sites that would
   hold the page (here, US wagering sites' results), not only the open web;
   and a site that blocks the fetch tool is not a site with no page.

## 2026-11-16 — Women's college basketball against the men's: why it trails, and in-play bets that were never stored

1. **League and scope**: women's college basketball against the men's. mike,
   2026-11-16: *"Why isn't the ncaabw models as successful as the ncaab? What
   are we missing"*. An audit of the live records, the market grid and the
   in-play loop, not a build (PR #1407). The answer, with every number's
   source, is `docs/sports/ncaabw.md`, "Why the women's record trails the
   men's".
2. **Tried**: the live records model by model; a census of ESPN's games
   against the games each book priced (2026-11-03 to 11-15); the women's
   totals model at other books' first posted totals; the halftime model's
   live decisions against its replay, by EV band and share that bets; the
   replay with every model fit on every season; DraftKings' own board against
   the feed's DraftKings quote in the break; every decided bet in the
   pollers' log against `picks`.
3. **New**:
   - A trap: an in-play pick row written with an empty DraftKings probability
     is never stored. `picks` refuses it, the loop logs "write failed
     (non-fatal)", and nothing is posted. The men's loop had it and the
     women's and EuroLeague loops were copied from it: 20 of the men's 24 and
     13 of the women's 22 bets were lost, 2026-11-09 to 11-15
     (`porting-traps.md`, "Writing the pick"; the check after a merge in
     `shipping.md`).
   - A kill test: a live model that bets far less often than its replay is
     replayed with every fit on every season; if each fit splits the seasons
     alike, the books moved, not the model file (`kill-tests.md`, "Is it
     stable?").
   - A null: the ratings blend at another book's first posted total, on the
     games the anchor book never prices (`methods.md` §1).
   - A coverage measurement to make before comparing two leagues: DraftKings
     priced 69 of 701 women's games against 519 of 681 men's, and its own
     board agreed (`market-grid.md`, "Which book's price counts").
4. **Corrected**: `methods.md`, the halftime break as the decision point. Was
   "*Worked*: 669 bets +11.84%" with no word on this season; now it also says
   2026-27's books hang halftime totals closer to the model (it bets 25% of
   decided games against 60–64% in the stored seasons, every fit alike) and
   this season's 36 bets went 16-20, because the replay of 2026-11-01 to
   11-09 and the live ledger both show it (`docs/sports/ncaabw.md`; re-check
   #1405). A hypothesis of the session, not a claim of the skill, was also
   wrong: the move to DraftKings' own board on 2026-11-13 is not the cause (on
   the 11 games both covered, the feed's DraftKings total was the board's).
5. **The framework**: step 8 graded a live record without first checking that
   the model's decisions reached `picks`; it now opens with that check. The
   reply section's five headings, with the results table leading "Outcome /
   findings", come with #1422 (mike, 2026-11-16).

## 2026-11-16 — Review

1. **Scope.** The weekly self-review, run on mike's PC. Since: the
   2026-11-13 Review (second, from mike's PC) entry (merged as 267733a5).
2. **Tried.** `git log` on master since: 368 commits. `config.py` gained eight
   model ids in `ACTION_THRESHOLDS` (`atp_moneyline_shop`, `wta_moneyline_shop`,
   `euroleague_home_ml`, `euroleague_h1_dog_ml`, `euroleague_home_dog_spread`,
   `euroleague_live_spread_ht`, `euroleague_q1_club_share_total`,
   `ufc_open_moneyline`) and lost three (`ufc_moneyline`, `ufc_total_rounds`,
   `ufc_method_of_victory`, retired 2026-11-13); each added model is already
   named in this log, so no gap to fill. **Live records, read directly and
   read-only** (settled BETs by `model_id`, units on the posted stake, all
   time / since 2026-11-13 14:00 UTC): `ncaaf_over_under` 105 bets 62-43,
   +14.42 units, +12.4% / 1 bet; `nba_prop_projection` 99 bets 41-58, -2.54,
   -3.2% / 15 bets -2.12; `ncaab_first_half_total` 82 bets 51-31, +13.07,
   +13.0% / 10 bets +7.55; `ncaaf_live_total` 98 bets, -5.20, -4.4% (no new
   bets); `mlb_live_total_runs` 162 bets, +18.90, +9.5% (no new bets);
   `nhl_moneyline` since its rebuild (2026-10-15) 61 bets 32-29, +2.70,
   +4.1% (all time 67, -0.29, -0.4%); `nfl_wind_totals` 38 bets +1.50, +3.7%
   (under 50). Under 50 settled bets, nothing changed: `ncaab_first_half_spread`
   39 (+10.62, +23.7%), `nba_total_luck` 27 (-0.7%), `nba_team_total_luck` 31
   (-14.4%), `nba_first_half_total_luck` 18, `ncaabw_total_blend` 9,
   `ncaabw_live_total_ht` 9 (-3.84, -37.4%), `ncaab_total_blend` 2,
   `nfl_live_leader_ml` 6, `ncaaf_moneyline_market` 7 (+0.72),
   `ufc_open_moneyline` none settled under that id yet (`ufc_moneyline` 5
   bets and `ufc_total_rounds` 7 are the retired models), the EuroLeague and
   tennis models none settled. The tennis models' rows are absent from `picks`
   (no settled BET by that id).
3. **New.** Scouting routes re-probed from this PC and dated in `scouting.md`:
   racing.draftkings.com now answers 200 (403 on 2026-11-15), drf.com 403,
   twinspires.com no answer, eprints.soton.ac.uk 401. The earlier probes did
   not record a user agent, so those four changes may be the agent, not the
   site; this run used a browser one.
4. **Corrected.** No claim was contradicted. Two annotations moved: the
   college football totals live figure in `methods.md` (was 94 bets +9.76
   units, now 105 bets +14.42 units, +12.4%, because 11 more settled) and the
   pro basketball projection line (was 84 bets -0.42 units -0.6%, now 99 bets
   -2.54 units -3.2%, because 15 more settled; the verdict is unchanged: 99
   bets against a 66,588-bet backtest cannot overturn it, but the live return
   has turned from "about zero" to "below zero" and is the one to watch).
5. **The framework.** Nothing changed. Open: the log has 14 entries since
   the last Review, past the "every fifth entry" whole-log read; this run
   checked each entry's Corrected line for a repeat and found none promoted,
   but did not re-read every entry in full.

## 2026-11-16 — Horse racing: Hong Kong before the off, and UK/Ireland at starting price

1. **League and scope**: thoroughbred racing (mike, 2026-11-15: *"lets use the
   free hong kong history, and what do you need from me for uk irel;and"*;
   licences are never a blocker). Two free sets, stored in Supabase first
   (`scripts/horse/store_files.py`): nch015's Hong Kong pools with snapshots
   before the off (2016–2018), and deltaromeo's UK/Ireland results at starting
   price (5.1 million runners, 1988–2026; the 1.12 GB zip stored in 34 parts).
2. **Tried**: Hong Kong, decided on the pool 2 to 33 minutes out and paid at
   the dividend: blind bets, late money (six lead pairs), place off the win
   pool, Benter's blend against the pool before the off (183 bet sets).
   UK/Ireland at SP: calibration by band, year and code; blind win and
   each-way bets by race shape; official-rating rules; a place model;
   Bolton–Chapman then Benter walk-forward 1995–2026 with removal of each
   group, a leak check and four model-free figure picks. Two reviewers per
   study reran the scripts, and one per study re-graded the bets from the
   raw rows with its own code. **Every row: nothing clears.**
3. **New**: pre-off Benter and pre-off Dr Z, and late money decided before
   the off (`methods.md`); the UK results (`methods.md` §1 and §6); three
   kill tests (`kill-tests.md`: rows stored in finishing order, a stored
   rating checked as the one going into the race, print every obvious
   variant); the Hong Kong pre-off route and how the UK zip is stored
   (`market-grid.md`); a payout comparison to test whether an outlet's bets
   join the host's pool (`scouting.md`), after a 2026-11-16 search could not
   confirm that any US outlet still pools with the Hong Kong Jockey Club.
4. **Corrected**: the 2026-11-15 entry said the scope's 60/30/15/5-minute
   neighbourhood "cannot run on any free file". Now: nch015's Hong Kong set
   holds a snapshot every 12 minutes, then every 6 inside about 216 minutes,
   to about 5.6 minutes before the start (`docs/horse_racing_market_audit.md`
   §7). The neighbourhood ran; the last minute or two still cannot.
5. **The framework**: steps unchanged. One kill test added
   (`kill-tests.md`), from a trap that bit twice in this build, both times
   caught by a reviewer: **a study reported less than it seemed to test**
   (two Hong Kong lead pairs dropped after their results were seen; one UK
   figure-based pick reported alone when three obvious siblings existed,
   all of which lost). Every obvious variant is printed, and a split chosen
   after looking is printed whole, as a neighbourhood and in halves. If it
   recurs in another build, promote it to step 6 of `SKILL.md`.

What this build taught the skill: against the closing price a form model
adds about nothing (in Hong Kong it holds a little 5–12 minutes before the
off and none at the close; at the UK starting price it has added about
nothing since 2022); a starting price is a close, so any table that chooses
on it is an upper bound; and when a source lists runners in finishing
order, shuffle inside each race before any tie-break.

## 2026-11-15 — Horse racing, first market audit on the free files

1. **League and scope**: thoroughbred racing (mike, 2026-11-15: *"pickup the
   pr that was created and merged on horse racing. do additional research,
   invoke model skill"*), following PR #1357's scope. On the free files only:
   Betfair Australia's ANZ CSVs (132,750 races 2020-01 to 2026-10) and Hong
   Kong's final pools (1997–2005, 2014–2017). Stored in Supabase first
   (`scripts/horse/store_files.py`, 86 files, restore-and-hash verified, PC
   mirror matched by row count).
2. **Tried**: per market (`docs/sports/racing.md`, the grid): blind bets by
   band at two prices, gross and net of the real commission; calibration;
   favourites by year, meeting and track size; Harville place against the
   win market, raw, discounted and calibrated, in both markets; Bolton–Chapman
   plus Benter, walk-forward with removal of each feature group and a leak
   check; a logit on the exchange's scheduled-start prices (Sung and
   Johnson); place by field size. Two scouts: 28 method leads, and where a US
   bettor can bet a race and at what price. **Every row: nothing clears.**
3. **New**: the field-and-pool sport shape and racing's free price routes
   (`market-grid.md`); the place-against-win result and the untested
   sharp-against-pool rule (`methods.md` §2), the pool's even take and the
   exchange's calibration (§6), the Benter null (§1), four frontier lines;
   three data checks (`kill-tests.md`: a broken snapshot under a fine close,
   a display cap is not a price, prove the harness sees a leak); three
   scouting routes (`scouting.md`).
4. **Corrected**: the scope said a backtest that bets final odds "is betting
   the close" and must be refused. For a pool bet the final odds are the
   price paid: grading at them is right, deciding on them is not (corrected
   in place in `docs/horse_racing_scope.md`). And the scope's 60/30/15/5-minute
   neighbourhood cannot run on any free file: they hold one decision moment.
5. **The framework**: unchanged steps. One addition in practice: when the
   users' only bettable price is a pool, the "book a pick may name" question
   decides which free file is a test and which is a reference, so it was
   scouted first (US outlets offer Hong Kong, commingled with its pools as
   of 2014, 2026 not confirmed; the Betfair exchange is not open to US
   residents).

What this build taught the skill: in a field market, calibrate the place
model before any place test (Harville's bias is priced in both markets),
prove a null harness can see a leak, and start a racing jurisdiction from a
pre-off price path, because every free price is a close.

## 2026-11-15 — Horse racing public files, still no model

1. **League and scope**: same planning request. Mike asked for the research
   notes and the public datasets on the scope branch. No model was fit.
2. **Tried**: no prices were graded. The Betfair Australia listing page was
   fetched and its thoroughbred filenames were copied into
   `scripts/horse/manifest.json`.
3. **New**: `docs/horse_racing_sources.md` and
   `scripts/horse/fetch_datasets.py`. The download directory is gitignored.
   Nothing was added to `methods.md`.
4. **Corrected**: the scope's Punting Form row had no dollar amount. The
   14 Nov note prints Starter $59.00/Month and Professional $297.00/Month.
   New Zealand is in the free Betfair CSVs, not a missing card.
5. **The framework**: unchanged. The files are not a build.

## 2026-11-15 — Horse racing scoped, not built

1. **League and scope**: thoroughbred racing, US and international (a
   planning request, 2026-11-15). No market was fit and no pick was written.
   The design is `docs/horse_racing_scope.md`.
2. **Tried**: nothing on a price history. Vendor pages were read for
   coverage and cost. The Racing API coverage page (fetched that day) shows
   full US and Australia cards on add-ons the FAQ says are closed to new
   subscribers. Core 2026 counts: GB 8,730, Ireland 2,546, Hong Kong 737,
   France 2,723, USA 199, Australia 190, UAE 150, Japan 74.
3. **New**: the multi-runner, pari-mutuel shape (a field, a tote or
   exchange close, one win bet per race, dead heat not a WIN/PUSH). It is
   written in the scope doc, not in `market-grid.md`, because that file says
   to define a new shape when the league is built. Sources and the license
   limits that block the paid app are in the scope doc. No method was added
   to `methods.md`.
4. **Corrected**: nothing in the skill. The Odds API sports list fetched
   that day has no racing, which matches the scope's "do not spend
   `ODDS_API_KEY`".
5. **The framework**: unchanged. A scope is not a build, so step 7's
   shipping list was used as the checklist and not executed.

## 2026-11-14: NCAAF moneyline, its decision timing replayed at every hour (`ncaaf_moneyline_market`)

1. **League and scope**: college football's moneyline model, live since
   2026-11-10 and decided once at 14:00 UTC. mike, 2026-11-14: when a model
   decides is a per-model parameter, chosen by out-of-sample expected units;
   "Buy all of it now" for every hour of 2023-2025 (152,680 credits).
2. **Tried**: the live card's own read and decision at every whole UTC hour
   of three seasons, graded as 26 timings (each fixed hour on game day,
   every hour until it bets, the last read before kickoff) after the card's
   price and EV floors; chosen on 2023-2024, confirmed on 2025, BH-FDR over
   all 26 (`scripts/ncaaf_moneyline_timing.py`).
3. **New**: "When the model decides" in `porting-traps.md` (the method, and
   the hockey evidence for the live check rate); the timing inventory of
   every model with its credit number (`docs/decision_timing.md`); a light
   read of a purchase's rows by primary-key range instead of a by-hand
   mirror run (`scripts/ncaaf_hourly_extract.py`).
4. **Corrected**: `shipping.md` said "a game is decided once"; the lock is on
   a BET, and a card's "EACH GAME DECIDED ONCE (CLAUDE.md 1c)" is a timing
   choice under the pick rule's name. Measured on the bought hours: the
   feed's own stamp on every row is within a minute of its pull at every
   UTC hour, so the card's 60-minute window thins no quiet hour; an old
   stamp in a change-only store is the store's doing, not the feed's.
5. **The framework**: step 7 now measures the timing before shipping and
   says the lock is on a BET.

Result: no timing clears. 14:00 UTC (live) is the 2023-2024 choice, +0.81
units on 2025; checking every hour until it bets triples the bets for +1.6%;
the bet price sits 3-4% below Pinnacle's close at every fixed hour. And a
purchase can damage what it touches: the history job's game upsert moved
1,690 stored kickoffs (fixed, restored). Read a purchase's side effects on
`games`, not only its odds rows.

## 2026-11-14 — NBL (Australia), groundwork: one book a pick may name, and a purchase the balance cannot hold this cycle

1. **League and scope**: the NBL, mike, 2026-11-14: *"Invoke model skill and
   build Australia nbl models"*. A new sport, `NBL`. Steps 0 to 2b and the
   groundwork; no grid row has a priced result yet (`docs/sports/nbl.md`).
2. **Tried**: the feed's history depth (five empty event lists, first snapshot
   2024-09-24), its books at every region on two history days and at the
   line-shop ten on four, its per-event markets today, and the per-event
   history of BetRivers and Pinnacle on six past games for every period,
   team-total and alternate key (free when empty); ESPN's NBL scoreboard and
   summaries by season; the league's own stats API (refused, below); a scout;
   three trial days of the purchase (0, 1 and 2 games); a projection of the
   whole history from the stored schedule and the three measured day costs.
3. **New**:
   - `market-grid.md`: an NBL line in the basketball shape. **One book a pick
     may name** (BetRivers, full game only) and a sharp book that enters the
     feed mid-history (Pinnacle from 2026-27, so two seasons measure value
     against the exchange and the local consensus). Price route 2: measure a
     no-game day as well as a game day before projecting a purchase (here a
     no-game day held a snapshot every five minutes and cost 70% of a game
     day). Route 3: prediction-market history as a free second price (Kalshi's
     NBL game markets from 2025-12-04, liquid; Polymarket from 2026-01-09).
   - `porting-traps.md`: ESPN labels a preseason game regular-season
     (401707730), caught by every club's regular-season count; stale ESPN
     events years old ("end of period" with no score, "scheduled"), kept out
     of `games` by a 36-hour rule; ESPN's ranged `dates=` form answers 400 for
     this league; venue blank for whole seasons; plays with no wall clock.
     And a trap in the EuroLeague purchaser, fixed in the NBL fork only: its
     one-day path (`--only-days`) ignored `--pregame-step-min`, so a trial
     measured every snapshot, not what the thinned purchase would cost.
   - `shipping.md`: the tests a new resolve-only sport extends (the
     college basketball odds-intake pins and the price-path pin). And a trap
     seen twice, so a rule there: the bounded clean-up test's tie fixture drew
     each row's source from the whole protected list, so each new protected
     source changed which rows were protected and took its ties away
     (EuroLeague's period source, seed 11; the NBL's two, seeds 7 and 11). It
     now draws from a fixed first 25. Found by comparing the full suite's
     failures on the branch and on master: 6 only on the branch, 17 on both.
   - `scouting.md`: eleven routes dated (ESPN's NBL, Kalshi, Polymarket,
     FIBA LiveStats answered; the league site's API refused by the permission
     check; AusSportsBetting's file refused, its robots.txt naming Claude's
     crawlers; hoops.com.au 403).
4. **Corrected**: nothing in the skill was contradicted by a measurement.
5. **The framework**: one promotion, one gap.
   - **Promoted.** The skill did not load because the session's checkout was
     on a branch without it: the Skill tool answered "Unknown skill", the
     second time (the first is the 2026-11-13 entry, "the skill never
     loaded"). Step 0 now says what to do: a worktree from `origin/master`,
     read `SKILL.md` there, build there.
   - **A gap, written into step 0.** The purchase is sized against the credit
     balance and the days to the plan's refill before it is put to mike: here
     the whole history (at most 1.70M) does not fit beside the platform's
     burn to a 12-08 refill, which turns the purchase decision into a top-up
     decision.

What this build taught the skill: price a purchase on a no-game day as well
as a game day, size it against the balance and the refill before asking, and
when the skill does not load, build from a worktree off master.

## 2026-11-14 — Tennis round 1: the match winner live (`atp_moneyline_shop`, `wta_moneyline_shop`), the games markets' line shop null

1. **League and scope**: tennis, both tours (mike, 2026-11-13: *"build
   professional tennis models"*; 2026-11-14: *"Why can't you do it now"* when
   the research waited on a nightly copy). On the bought history, 53
   tour-level keys, 2020-09 to 2026-11, read once into a local cache.
2. **Tried**: baselines on the match winner, total games and games spreads at
   every decidable book; the line shop against Pinnacle and the Betfair
   exchange at three decision times, multiplicative and power de-vig, with
   each book's retirement rule; the reference's calibration, overround and
   time since last change; a replay of the frozen rule through the live
   card's own code at the live moment, with two soft-book placebos and a
   walk-forward cut. Running in parallel: a serve-and-return games model and
   a fatigue and retirement-risk study.
3. **New**: three data checks in `kill-tests.md` ("Is the data right?"):
   power de-vig against a longshot lean, an exchange's first post is not a
   reference, and age in a change-only store. The tennis result in
   `methods.md` §2. A decision code shared by replay and card
   (`models/tennis_moneyline_shop.decide`), so the backtest is the live path.
4. **Corrected**: round 1's first grid (multiplicative de-vig, a 6-hour
   reference window) looked best in underdogs at the first post and against
   the exchange; both were the reference, not an edge. The candidate came
   only after the power de-vig, and its value moved with each principled fix
   (+4.0% at 0.01 with DraftKings' term only, +0.9% once Caesars' void-all
   rule was priced too): a result that moves under correct specification is
   weaker than its headline. And a feed can store one market under another's
   key: Pinnacle's total sets and set handicaps sat under tennis "totals" and
   "spreads" at the 2023 Australian and French Opens, which turned Pinnacle's
   blind over from -4.59% into an apparent -1.19%. Read each market's line
   range per book and tournament before the first baseline.
   Games markets: the serve-and-return model (round 1) and a model centred on
   the line (round 2) are both null.
5. **The framework**: the live decision moment was chosen after the close
   looked best, and the replay at that moment (+11.0%) was run before
   building; the skill's "the backtest runs what the live path runs" was what
   caught that the close is not decidable live. Nothing in `SKILL.md`
   changed.

What this build taught the skill: de-vig the sharp pair by the power method
before any shop grid on a market with longshots, an exchange's first-post
pair is not a reference, and in a change-only store a reference's age is
time since it moved.
## 2026-11-14 — EuroLeague, the big-favourite moneyline removed before it went live

1. **Scope.** mike, 2026-11-14: "odds cutoff for favorites should be -200".
   `euroleague_heavy_fav_ml` bet only favourites at -500 or shorter, so at a
   -200 floor it could never bet: removed (PR #1323, unmerged), not shipped as
   a model that cannot place a bet. The other four pre-game rules unchanged.
2. **Tried.** Rebuilt the artifact from the research cache
   (`scripts/euroleague_pregame_build.py --write`). Every read still matches
   the research bet for bet. The spread, first-half and first-quarter rules'
   artifact entries are identical. The home moneyline gains the 6 games the
   conflict rule took: 984 bets, +64.80 units (was 978, +65.80), uplift
   +0.0520 (was +0.0523), smallest EV +0.0401 (floor 0.04 still under it).
3. **New.** Nothing new as a method. The same-pass conflict branch was only
   reachable through the removed rule (the two full-game rules left both bet
   the home side), so it went with it; a test now pins that no two of the four
   decided in one pass conflict.
4. **Corrected.** `shipping.md`'s price-floor line: was "a model that lays
   shorter by design pins the research's shortest price, EuroLeague's big
   favourites -4000", now a rule whose every bet lays shorter than -200 is not
   shipped (mike, 2026-11-14). `porting-traps.md`'s conflict trap gained what
   a removal does to it.
5. **The framework.** No step changed.

## 2026-11-14 — EuroLeague, five pre-game rules shipped: `euroleague_home_ml`, `euroleague_heavy_fav_ml`, `euroleague_home_dog_spread`, `euroleague_h1_dog_ml`, `euroleague_q1_club_share_total`

1. **Scope.** mike, 2026-11-14: "I told you to build all the models": the
   five frozen leads of the full-game, first-half/quarter and round-2 studies
   shipped live, each knowing what it missed of the bar. Step 7 for five rule
   cards in one card, plus a live period feed.
2. **Tried.** One rules module, one card, one build. The build decides every
   cached game again through the card's own decision code and runs the
   research's own scripts (r1_/r2_/r3_) on the same cache: all eight reads
   (the three full-game rules at DraftKings alone and at the best deciding
   book, the two period rules at the best book) matched bet for bet, game,
   side, number, price and book, with no tie broken differently.
3. **New.** In `shipping.md` and `porting-traps.md`:
   - **The research cache moves under the build.** The cache had gained a
     game since the research read it (2026-11-13), and that game's full-game
     "close" was a stale board (the purchase's quotes end at 05:45 UTC that
     day). Replay on the research's own data state (`RESEARCH_LAST_DATE`) and
     report later games apart; never compare across the two.
   - **Two blind rules on one market can bet opposite sides of one game.**
     The home moneyline at -200 or longer and the favourite at -500 or
     shorter met on 6 games (the away favourite's game is the home dog's).
     The brief said they could not conflict; the replay measured that they
     do. Run every new model's bets through the conflict rule in the build
     and report what it costs (here -1.00 and -0.69 units).
   - **A blind rule's probability**: the market's no-vig chance plus the
     rule's walk-forward uplift (the nba_q1_trend_ml shape), with the EV
     floor and edge cut set just under the smallest replayed EV and edge,
     printed by the build, so no gate removes a research bet. A decision
     fetch that also carries the full game: the hourly refresh window does
     not reach tip minus 10 for an afternoon-ET league.
   - **A new period market needs its settlement arm, its period-score route
     and its closing-line rule** (`h2h_h1` had no arm at all, `totals_q1` was
     in no totals arm, and every non-NCAAB period read `nba_period_scores`):
     check `tracking/paper_tracker` before shipping any period market in a new
     sport.
4. **Corrected.** `shipping.md`'s "the price floor (default -200)": a model
   that lays shorter than -200 by design (the big favourites, to -4000) pins
   its own floor at the research's shortest price and says so. A test fixture
   that draws with `rnd.choice(PROTECTED_SOURCES)` changes shape with every
   new protected source (`tests/test_prune_bounded.py` lost its tie groups
   for seed 11); its source now draws from its own stream.
5. **The framework.** No step changed. Step 7's "the card replays the research
   bet for bet" held again: it is what showed the six conflicting games.

## 2026-11-14 — UFC props graded on BestFightOdds' per-book history

1. **Scope.** mike asked why the markets beside the fight winner were not
   tested. Method of victory, goes the distance, round betting and inside
   the distance had been parked for want of a price; #1304 found the route
   (BestFightOdds per-book pages). This entry is the crawl and the grade
   (`docs/ufc_market_audit.md` §5f, `docs/sports/ufc.md` grid).
2. **Tried.** 328 card pages stored (563,286 prices, five US books a pick
   may name plus three others, 2021-06 to 2026-11). Blind by market, side,
   book, year and favourite/underdog. Three mechanisms per market, fitted
   walk-forward by year: a book straying from the other four's power no-vig
   consensus; the anchored model (the consensus as offset, a free slope and
   per-outcome intercepts, ridge fighter inputs) with the market merely
   recalibrated as its control; method and round prices made coherent with
   the fight-winner price. Kill tests: cut and penalty neighbourhoods,
   early/late, side, price band, book, a 50-run placebo, DQ graded both
   ways, and each lead's bets re-graded at the price its history showed an
   hour and a day before the fight. Nothing clears. One lead (goes the
   distance, anchored) was +10.0% on 791 at the last recorded price and is
   +6.8% [-0.9, +14.4] on 745 at the price an hour before, with 2026 losing
   (-3.6%): to the frontier. It loses at DraftKings, the only live prop
   board read.
3. **New.**
   - Kill test (`kill-tests.md`, "Is the data right?"): a last recorded
     price is not a price at a time; re-grade the picked bets on the
     site's own price history.
   - Price route (`market-grid.md` route 4): how to crawl a comparison site
     cheaply, pages first, histories only for what a test points at, and
     the template ingestor.
   - Method notes (`methods.md` §1): on a many-outcome market the anchor
     needs a free slope on the market's logit and one intercept per outcome
     type; a two-way market is fitted once per pair (fitted on both sides,
     the inputs cancel, which made the first run's anchored rows equal the
     price rows exactly).
   - Trap: the comparison site splits one fight into two when books spell a
     fighter differently; fold both halves before grading, or every prop is
     counted twice.
4. **Corrected.** Was "BestFightOdds' per-book prop pages as a price route,
   to try" on the frontier, now run, with the goes-the-distance lead in its
   place (`methods.md`). A lead that passed every kill test at the page's
   last recorded price (+10.0%, a plateau, 0 of 50 placebos) fell from
   +8.4% to +6.8% on the same 745 bets at the price an hour before, and on
   those bets the cut neighbourhood is a hump at either price (the plateau
   rested on fights with no start time): the page's price is longer than the hour-before price on
   25% of bets and shorter on 5%. Was "DraftKings and BetMGM are missing from the
   November 2026 pages", now measured: DraftKings' prop prices thin out on
   the site from 2023 and are absent in 2026, BetMGM's nearly so.
5. **The framework.** Nothing in `SKILL.md` was wrong for this pass; step 1
   (no market parks for want of a price until every route has a result)
   is what sent these markets here. One gap, written into route 4 rather
   than `SKILL.md`: a comparison site's prices need dating before a rule
   graded on them is believed.

## 2026-11-13 — EuroLeague halftime spread shipped: `euroleague_live_spread_ht`

1. **Scope.** mike, 2026-11-13: "yes" to shipping the halftime spread lead
   (the women's halftime method with Pinnacle's close as the pre-game number,
   cut 0.05) knowing it missed the false-discovery correction and had a
   negative 2023-24. Step 7 for an in-play model in a new sport.
2. **Tried.** The replay on the loop's own decision code against the
   research's own code on the same cache: 364 identical bets, +45.34 units,
   every cut matching. The live inputs: EuroLeague's free live API for the
   break and the half-time score, stored Pinnacle closes for the pre-game
   number, the Odds API live endpoint at the ten history books for the read;
   DraftKings' own board checked and not usable yet.
3. **New.** Two traps in `porting-traps.md`: the next period's lineups are
   logged during the break (EuroLeague's third-quarter substitutions sit
   before its 'BP'), so "the next quarter is not empty" is not "it has begun";
   and a research stake is not the posted stake (replay on the research's to
   match bet for bet, report the posted one beside it). A check for any new
   in-play league: DraftKings lists a league in its navigation only while it
   has offers, so its league id is read on a day with a posted round (none
   listed for EuroLeague in Ohio, New Jersey or Massachusetts 89 hours before
   a game).
4. **Corrected.** `shipping.md` said every new model goes into the CLV market
   `CASE`. The closing-line recompute filters `p.is_live IS NOT TRUE`
   (`data/migrations/clv_standard_v2_2026_10_14.sql`), and none of the five
   in-play models since 2026-11-04 is in it, so an in-play model is not added
   there; the line now says so. `shipping.md` also said every new table goes in
   `WORKER_ONLY_TABLES`; a table a migration creates cannot
   (`tests/test_anon_readable.py` requires a Python create site for every name
   there), so the migration locks it down itself, as every in-play ledger does.
5. **The framework.** Nothing in `SKILL.md` changed.

## 2026-11-13 — Tennis (ATP and WTA), groundwork, settlement and the purchase

1. **Scope.** mike, 2026-11-13: *"Use the model building skill to build
   professional tennis models"*, then *"mens and womans should be different
   model groups / discord channels. But not just major tournaments, all pro
   tennis matches"*. Two new sports: `ATP` (men's singles at every level) and
   `WTA` (women's). Steps 0 to 2b, the settlement rules,
   a rating model and the purchase plan; no grid row has a priced result yet
   (`docs/sports/tennis.md`).
2. **Tried.** Measured the feed (53 per-tournament keys, history from the 2020
   US Open, books by year, markets one at a time on a live match), ESPN's free
   scoreboard, a results archive with serve and return counts (393,131 rows
   stored), and DraftKings' own tennis rules. A coverage sweep found 129
   windows for 337 credits; a one-day trial of the purchase cost 1,500 credits
   for 25 hourly snapshots of both book groups. An Elo trails the market as
   published (Brier 0.215-0.219 on men's tour matches, 2023-2025). Measured the
   retirement rate the DraftKings rule turns into an option (1.13% a side).
   Scout: no published method beats Pinnacle's close on the match winner; no
   test of total games or games spreads exists at all.
3. **New.** `market-grid.md`: tennis in the one-against-one shape, and finding
   a part-year key's windows with three 1-credit event lists. `porting-traps.md`:
   settlement differs by book (a retirement), a source's format field can be
   wrong, a per-tournament key can hold two windows a year, a listed start
   that moves and once came after the real start. `methods.md` §7: a
   settlement rule that hands the bettor an option, with its measured size;
   three tennis lines in the frontier. `scouting.md`: seven routes (three
   refused). A league whose lower levels the feed does not sell: Pinnacle's
   public site prices every level (collected from day one), and a results
   site's one price per match measured to be an average near the close (a
   baseline, never a decidable price).
4. **Corrected.** Nothing in the skill was contradicted by a measurement.
   One claim of this build was corrected before it was written down: "the
   retiring player is almost always the one losing" was too strong (the
   archive lists the advancing player as winner by definition; the retiring
   player was ahead on completed sets in 9 of 109 men's retirements of 2025).
5. **The framework.** Step 2's order held. One addition worth promoting if it
   recurs: when a price route refuses (a site block), the copy of its data
   elsewhere is not a route; the permission check refused it, and the feed's
   own history was the price source that matched the live path anyway.

## 2026-11-13 — UFC round totals, run to the end of the ladder

1. **Scope.** mike asked why the markets beside the fight winner were not
   tested, and whether the skill was followed. Round totals had been called
   null without the anchored model on the bought history, without three
   mechanisms of our own and without the stuck ladder. This entry is that
   search (`docs/ufc_market_audit.md` §4).
2. **Tried.** A Pinnacle-anchored finish model in three nested forms,
   walk-forward by year, at DraftKings (the only book a pick may name with
   totals in the history); blind sides by line and pull; DraftKings against
   Pinnacle in the same pull; four mechanisms of our own (stale DraftKings
   total after a moneyline move, women's and flyweight overs, five-round
   overs, short-notice unders); every rung of the stuck ladder. Nothing
   clears. One lead, the card-day over (+6.92% on 228, interval below zero,
   2025 negative), fails the bar and goes to the frontier.
3. **New.**
   - Kill test (`kill-tests.md`, "Is the data right?"): check the no-vig
     split before trusting closing value; on UFC totals the proportional
     split charges the over about 2.5 points.
   - Method note (`methods.md` §1): an anchored model needs a free intercept
     per line; fighter inputs on a UFC total failed the donor placebo.
   - Frontier (`methods.md`): the card-day over, graded forward only.
4. **Corrected.** Was "DraftKings' totals in the bought history from 2025",
   now "from late 2023, 1,072 fights", because the history was counted by
   year (`docs/ufc_market_audit.md` §4, `docs/sports/ufc.md`). Was "22 bets
   of DraftKings against Pinnacle in one pull", now 8,090 comparable pulls,
   43 with DraftKings above Pinnacle's fair price.
5. **The framework.** Two failures, one a skipped rule, one a hole in the
   skill. Both changed in `SKILL.md` and `references/market-grid.md`.
   - **Skipped.** The first UFC entry called round totals null after one
     model, before the three mechanisms and the ladder. `SKILL.md` already
     required both, so the rule was there and was skipped. Now the rule says
     it binds each market, and a null row names its three mechanisms and
     the ladder's rungs, so a skipped step shows in the text (step 5).
   - **A hole.** Step 1 let a row park as "no price source", and
     the price routes never named a book's own board or a comparison
     site's per-book history. Parking is not null, so nothing sent the
     row up the ladder. UFC parked method of victory, goes the distance and
     round betting that way, because the odds feed refused their keys
     (HTTP 422). DraftKings' own board priced all three on 2026-11-14,
     and BestFightOdds holds the US books' prices for them from mid-2021
     (#1304). **The same park stood in two more leagues**: EuroLeague
     player props, and women's college basketball's first halves, quarters,
     team totals, alternates and props. Three leagues meets the promotion
     bar, so it is now a rule. In step 1, "no price" is never a reason to
     park until every route has a written result. The route list gains the
     book's board and the comparison sites (market-grid route 4). The
     ladder now runs before a market parks for want of a price. The two
     other leagues' rows are reopened as to-dos.

## 2026-11-13 — UFC, a rebuild from zero

1. **Scope.** mike: *"Use the model building skill to build models for UFC.
   Ignore and delete any existing models in the repo."* The three old models
   retired; every market the feed and the free archives price worked to a
   verdict (`docs/ufc_market_audit.md`, `docs/sports/ufc.md` grid).
2. **Tried.** Fight winner: blind bets by band, a market-anchored rating
   model walk-forward at the close and at the first posted price, the same
   at each US book's first price, Pinnacle-anchored line shopping,
   five-round fights, big line moves. Round totals: blind by book, a
   finish-time model. Method of victory: blind by method and side. Then the
   feed's history was bought (150,240 credits) and the open-anchored model
   graded at the books a pick may name. **One model ships,
   `ufc_open_moneyline`**: Pinnacle-anchored at a week out, 846 bets
   +12.85% [+8.0, +17.5], every year positive, +2.2% against Pinnacle's
   close. Totals and method: nothing clears.
3. **New.**
   - Method (`methods.md` §1): a rating model anchored on the sharp book's
     price a week or more out, bet at the best deciding book; the edge
     grows with the lead (7-14 days +7%, 14-30 +20%, inside a week negative).
   - Kill test (`kill-tests.md`): an archive's open is not a book we can
     bet; and a small forward sample can say the opposite of the history
     (104 bets with negative closing value, against 846 positive on 2,457
     fights), so a purchase settles it, not the sample.
   - Price routes (`market-grid.md`): the MMA key's coverage; two free
     archives; the bulk history from 2020-06-06 at 20 credits a market.
   - Trap (`porting-traps.md`): our UFC ingest stores a fight only once
     DraftKings lists it, and kept DraftKings alone before 2026-08.
   - Scout routes (`scouting.md`): six answers and refusals.
4. **Corrected.** The first entry's open question (is `ufc_total_rounds`
   paused?) is closed: it was, and it is retired. The fighting shape in
   `market-grid.md` said method and duration props have no price history:
   method props have a free one (2012+), round totals the feed's (2021+).
   A 2026 pilot said round totals carry their margin on the over; 2,403
   fights say the under (-6.8% blind at Pinnacle).
5. **The framework.** A free archive was analysed before it was stored;
   step 2 now stores a free archive like a bought one, before the first
   table is read from it. The card decides on the same cadence the history
   was bought at (one noon pull a day), the first-come-lock trap avoided by
   construction rather than by replay.

## 2026-11-13 — EuroLeague halftime

1. **Scope.** The EuroLeague build: the halftime break, now that the shot
   chart places it on the wall clock.
2. **Tried.** Fresh-quote coverage by book, blind bets at the break, the
   women's halftime method ported unchanged for total, spread and moneyline,
   a structural check of how the books re-hang the halftime line, 183 cells
   with a false-discovery correction. Nothing clears.
3. **New.** In `methods.md`, the halftime method's EuroLeague result and its
   mechanism: a book that carries too much of the pre-game margin into the
   second half. A check worth running in every league with in-play history:
   measure the share of the pre-game margin and of the first-half surprise
   the books carry into the halftime line, against what the games carried.
4. **Corrected.** Nothing in the skill was contradicted.
5. **The framework.** Nothing changed.

## 2026-11-13 — EuroLeague round 2, and halftime placed on the wall clock

1. **Scope.** The EuroLeague build, round 2 (`docs/euroleague_market_audit.md`).
2. **Tried.** The home lean within a -200 floor, market-anchored models with
   home, crowd, venue, rest and schedule inputs, referee crews and the opening
   total, and the invention floor for the first half and quarter (three
   mechanisms each, all run). 109 cells; nothing clears.
3. **New.** A price route for in-play timing (`market-grid.md`): EuroLeague's
   play-by-play has only the game clock, but its shot chart stamps every shot
   in UTC, which brackets halftime. A trap (`porting-traps.md`): the shot
   chart's host rate-limits through Cloudflare (HTTP 429, error 1015) after
   about 60 calls four at a time; one call every 1.5 seconds holds. And a
   research trap: a hold-out read needs a cache refreshed past the freeze
   date, or the frozen rule only reproduces itself.
4. **Corrected.** Nothing in the skill was contradicted.
5. **The framework.** Nothing changed in `SKILL.md`; the stuck ladder's
   remaining rungs (new information, the halftime moment, a fresh read) are
   the next round.

## 2026-11-13 — EuroLeague full game, round 1

1. **Scope.** The EuroLeague build: moneyline, spread and total, 2021-22 on.
2. **Tried.** The data check, baselines at the first post and the close, the
   four catalogued basketball methods unchanged, the scout's relocation and
   club-home-edge leads, 283 cells with a false-discovery correction
   (`docs/euroleague_market_audit.md`, full game round 1). Nothing clears.
3. **New.** Three method results in `methods.md` (line shopping and a
   book's moneyline against its own spread both fail here; the first post
   could not run because the sharp book was rarely up). A lead that is a
   decision, not a pass: favourites at -500 or shorter win 93.1% against an
   84.1% price, on a price band whose neighbour loses -7.11%.
4. **Corrected.** "DraftKings posts nearest the tip" (the league doc and an
   `odds_ingestor` comment) came from one day's board; the history says a
   median 45-73 hours before the tip. The research brief's "DraftKings
   priced nothing in 2021-22" was a misreading of the 2020-21 census.
5. **The framework.** Nothing changed in `SKILL.md`.

## 2026-11-13 — EuroLeague first half and first quarter, round 1

1. **Scope.** The EuroLeague build (mike, 2026-11-12, "all markets including
   1h and 1q"), the first research round on its first-half and first-quarter
   markets, once their history was bought (mike, 2026-11-13: "Do the 4.4m").
2. **Tried.** Settlement, bettable coverage by season, 556 blind cells, the
   close's accuracy, the catalogued half-from-the-full-game method unchanged,
   cross-book disagreement, and the kill tests on every positive cell
   (`docs/euroleague_market_audit.md`, round 1). Nothing clears; one
   first-quarter under lead is frozen.
3. **New.** In `methods.md`, the half-from-the-full-game method's EuroLeague
   failure (the books hold the half at 50.05-50.29% of the full-game total).
   In `porting-traps.md`, a book's main key can hold only an alternate rung.
   And a practice: a whole-history purchase sized for one cycle can be cut to
   about 40% by asking every snapshot only from 30 minutes before each tip to
   2.5 hours after it, and one every 15 minutes otherwise
   (`euroleague_odds_history --pregame-step-min`), keeping the close and the
   in-play path whole.
4. **Corrected.** The league doc's claim that first-quarter lines exist only
   from 2025-26 came from a three-game sample: the bought history holds them
   from 2023-24 (`docs/sports/euroleague.md`, corrected in place). Nothing in
   the skill's own files was contradicted.
5. **The framework.** Nothing changed in `SKILL.md`. Not called null: the
   invention floor (three mechanisms of our own) and the stuck ladder are the
   next round.

## 2026-11-13 — Review (second, from mike's PC)

1. **Scope.** The weekly self-review run on mike's PC, after the cloud run
   earlier the same day could not read the database or probe the routes. Since:
   the 2026-11-13 Review entry below.
2. **Tried.** `git log` on master since that entry: only the merge of that
   review (#1271); `config.py` and `docs/sports` unchanged, so no model or
   sport lacks a log entry. **Live records, read directly and read-only**
   (settled BETs by `model_id`, units on the posted stake): `ncaaf_over_under`
   94 bets 54-40, +9.76 units, +9.3% (matches the claim in `methods.md`);
   `nhl_moneyline` since its rebuild (2026-10-15) 51 bets, +0.75 units, +1.4%
   (all time 57 bets, -2.24, -3.7%, mostly the old model); `nba_prop_projection`
   84 bets 36-48, -0.42 units, -0.6%; `ncaab_first_half_total` 72 bets +5.52
   units, +6.3% (backtest +5.98%); `ncaaf_live_total` 98 bets -5.20 units, -4.4%
   (consistent with "college football in-play failed"); `mlb_live_total_runs`
   162 bets +18.90 units, +9.5%. Under 50 settled bets, nothing changed:
   `nfl_wind_totals` 36 (+1.60, +4.2%), `ncaabw_total_blend` 4,
   `ncaab_total_blend` 2, `ncaabw_live_total_ht` 7 (-3.55, -45.5%),
   `nba_total_luck` 23 (-16.7%), `nba_team_total_luck` 29 (-15.0%),
   `nba_first_half_total_luck` 14, `nfl_live_leader_ml` 5.
3. **New.** Routes re-probed from this PC (`scouting.md`, dated): all answers
   of 2026-11-12 held; `forum.sportsbookreview.com` gave no answer but
   `sportsbookreview.com/forum/` gave 200; Pinnacle's old path now redirects
   to `/en/betting-articles/` (200); centaur.reading.ac.uk now 200. Reddit, the
   EuroLeague site, cris.unibo.it and iris.uniroma4.it still refuse.
4. **Corrected.** One annotation, no verdict: the pro basketball
   minutes x rate props line in `methods.md` quoted only the backtest (+3.60%);
   it now carries the live 84-bet record (-0.6%), which is too few bets to
   overturn it. The shooting-luck totals are live at 14 to 29 bets each with
   negative returns; they stay unchanged until 50 settle.
5. **The framework.** Nothing changed. Open: the cloud run and the PC run can
   both fire on one day; this one used the `-2` branch name as instructed.

## 2026-11-13 — Review

1. **Scope.** The first weekly self-review (mike, 2026-11-13: *"the skill
   should review itself every week"*), run from the cloud. Since: the start,
   2026-11-12, because no earlier Review entry exists.
2. **Tried.** `git log` on master since 2026-11-12: 68 commits. `config.py`
   changed once (c5da32f3, the EuroLeague groundwork) and only the book lists
   in it; no model id was added to `ACTION_THRESHOLDS`, none retired or paused.
   New docs: `docs/sports/euroleague.md` (already in the log, 2026-11-12). The
   NCAAB in-play fast path, the NBA Betting tab and the same-game parlay price
   are not league builds. **Live records: not measured.** The Supabase
   connector failed to connect in this session (CONNECT_TIMEOUT, retried three
   times), so the 94-bet / +9.76-unit college football totals claim and the
   402-bet women's college totals claim in `methods.md` were neither confirmed
   nor contradicted, and no verdict was touched. Next review: for each live
   model, settled BETs in `picks` by `model_id` and date, units through
   `published_pick_unit_profit` (columns looked up first).
3. **New.** The cloud cannot re-probe the scouting routes: of 18 sites, only
   `api.github.com` answered (200; `github.com` bare gave 400). Every other
   site, including the ones that answered from the PC, returned code 0 with a
   403 from the egress proxy. That is the sandbox allowlist, not the sites. The
   review first added these answers as a column in `scouting.md`; the same day
   that column was replaced by one note under the table, because 17 "blocked"
   cells beside the PC's answers would read as the sites being down. The
   routine no longer probes routes from the cloud.
4. **Corrected.** Nothing measured was contradicted. Nothing was promoted:
   no trap or failure appears in two entries yet (the clean-up-thins-the-purchase
   and the curl-from-the-cloud limits each appear once).
5. **The framework.** Review mode step 3 now says what to do when the database
   connector is down: report the count as not measured, with the query, and
   change no verdict.

## 2026-11-13 — The write-back enforced: a Stop hook, a merge gate, review mode

1. **Scope.** mike: *"for self improvement, how can we ensure the skill auto
   updates itself ?"*
2. **Tried.** Read the first real use (the EuroLeague groundwork, 2026-11-12):
   it wrote an entry and three reference files and corrected the new-league
   order, without being forced. It also showed the gap: that session started
   in a checkout whose branch did not hold the skill, so the skill never
   loaded; the session found it in git and read its files by path.
3. **New.**
   - A Stop hook (`.claude/hooks/league_models_writeback.py`, project
     settings): a session that used the skill (the Skill tool, a typed
     `/league-models`, or reading the skill's SKILL.md by path) and changed
     files, but never touched this log, is stopped once and told what to
     write. It fails open. Run on five of the 2026-11-12 transcripts it
     blocks none: each one that used the skill had written the log.
   - A merge gate in `tests/test_league_models_skill.py`: a model id in
     `config.ACTION_THRESHOLDS` or a sport in the odds feed's `SPORT_KEYS` or
     `config.DISCORD_SPORTS` that is not in the sets frozen on 2026-11-13 must
     be named in this log.
   - Review mode (`/league-models review`, `SKILL.md`): the skill checked
     against the repo's changes and the live records since the last review,
     ending in a pull request.
4. **Corrected.** Nothing measured was contradicted.
5. **The framework.** `SKILL.md` now names what enforces the write-back. The
   Stop hook is in the project settings, so it runs in every session in this
   repo, Matt's included.

## 2026-11-12 — EuroLeague, the first league built with the skill (groundwork)

1. **Scope.** mike: *"invoke the new skill to build the euroleague model. all
   markets including 1h and 1q"*.
2. **Tried.** Steps 0 to 2b only. Measured the odds feed (history from
   2020-21, a snapshot every 5 minutes on game days from 2022-23 and every 10
   before, books by season, period markets per event only and only from 2023)
   and EuroLeague's own API (open: finals, quarter scores, referees, venue, the
   whole season ahead). Built the identity, the results ingest, both history
   purchases and the forward pull; trialled each purchase on one day; ran the
   scout. **No grid row has a result yet**: the purchase waits for the merge
   and for mike's yes to its cost (`docs/sports/euroleague.md`).
3. **New.**
   - Price route (`market-grid.md`): this league's per-event history serves
     period markets only from 2023 (HTTP 422 on a 2022-12 game); it bills 10
     credits per market returned; "ten named books are one region" holds on
     the history endpoint too (30 credits for ten books, 60 for eleven).
   - Traps (`porting-traps.md`): a bought history is thinned by the odds
     clean-up until its source is protected IN PRODUCTION, so the groundwork
     merges before the purchase runs at scale; the league's neutral-venue flag
     was false on relocated "home" games; one long transaction of single-row
     writes from mike's PC lost its connection mid-season (batched, all seven
     seasons took 31 seconds); `odds` filtered on `source` alone scans 16 GB and
     timed out, so read it by `game_id`; the credit planner refuses a
     whole-history plan at its worst case when the measured cost would fit, so
     it is fed 30-day chunks, newest season first.
   - Scout routes (`scouting.md`): eight new answers and refusals.
4. **Corrected.** Nothing measured contradicted the skill.
5. **The framework.** The new-league order put "buy and store the price
   history" before anything protected it from the clean-up. It now says to
   protect the sources (merge the groundwork) first, and that a purchase of
   this size is asked in chat with its measured cost: a detached launch of the
   full purchase was refused by the permission check on 2026-11-12.

## 2026-11-12 — Scouting outside the repo, and inventing before a null

1. **Scope.** mike: *"will it hunt for new appraches, data sources, sleuth
   online forums and repos anything it can find, OR invest new approaches if
   it cant find edge in a market?"*
2. **Tried.** It looked outside only from inside the stuck ladder, with no
   routes, no way to judge a lead and nothing written back. Probed the routes
   from mike's PC: web search, GitHub repository and code search, two betting
   forums, arXiv, Kaggle and Pinnacle's articles answered; Reddit refused a
   plain fetch (403 on reddit.com and old.reddit.com). One web search for
   women's college basketball totals models returned mostly picks sites.
3. **New.** `references/scouting.md` (when, where, the measured routes, search
   terms, the leads table, how to judge a lead, the rules for code, data,
   terms, sign-ups and paid sources, and the write-back). Step 2b in
   `SKILL.md`: a scout on every build. Rung 6 of the ladder points at it. An
   invention floor: three mechanisms of the session's own before any market is
   called null, the cheapest one run, the rest written into the frontier.
4. **Corrected.** Nothing measured was contradicted.
5. **The framework.** A scout now sits between the price inventory and the
   method search, and is repeated each season and when a live model decays.

## 2026-11-12 — How the skill learns, and what to do when stuck

1. **Scope.** mike: *"I want this skill to be self learning and self evolving
   and self correcting - is that the case? Will you look outside the box when
   stuck?"*
2. **Tried.** A review of the first version against that question. It was not
   self-learning: it had an instruction to write back and nothing that made it
   happen, no record of what each use taught it, no defined moment to call a
   search stuck, and nothing that noticed when a file or setting it cites had
   moved.
3. **New.** This log; the write-back gate and the line in the reply; the
   correction rule; the stuck signals and the ladder (all in `SKILL.md`). A
   test that fails when a cited file or setting no longer exists
   (`tests/test_league_models_skill.py`) is written on its own branch and
   merged separately, because any Python file redeploys the worker and the
   pollers, and in-play models were live when this merged.
4. **Corrected.** Nothing measured was contradicted.
5. **The framework.** Step 0 now starts with this log; step 9 is a gate, not
   a suggestion; a "when stuck" section sits between steps 5 and 6.
6. **Found while landing it.** The skill's own markdown-only merge (#1262,
   22:39:57 UTC) redeployed the in-play service (pollers BUILDING 22:40:00,
   DEPLOYING 22:44:05) with college basketball games live, because another
   session's code merge was still deploying there. The worker skipped it.
   Written into `shipping.md`, "After mike's merge", step 1.

## 2026-11-12 — The skill is written

1. **Scope.** mike: *"can we build a generalized skill for model building -
   all markets for a given league ... include approaches, the ultimate goals
   and leave open to explore and define and create and invent new
   frameworks."*
2. **Tried.** Every rule file, CLAUDE.md, the memory files, and every
   per-sport and market-search doc, read by four read-only agents. Every figure
   carried into the skill was checked by script against the docs.
3. **New.** All six files.
4. **Corrected.** The first frontmatter did not parse (an unquoted colon).
5. **Open, not resolved — re-check before relying on either:** whether
   `nfl_prop_tackles_assists` is live (`config.py` says it stays paused;
   `docs/nfl_prop_method_search.md` says it was unpaused 2026-09-09), and
   whether `ufc_total_rounds` is paused (`docs/sports/ufc.md` against
   `docs/paused_model_assessment.md`).
