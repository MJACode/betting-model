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

## 2026-11-13 — UFC, a rebuild from zero

1. **Scope.** mike: *"Use the model building skill to build models for UFC.
   Ignore and delete any existing models in the repo."* The three old models
   retired; every market the feed and the free archives price, worked to a
   verdict (`docs/ufc_market_audit.md`, `docs/sports/ufc.md` grid).
2. **Tried.** Fight winner: blind bets by price band, the market-anchored
   rating model walk-forward 2014-2026 at the close and at the first posted
   price, the frozen model at each US book's first stored 2026 price,
   Pinnacle-anchored line shopping, five-round fights. Round totals: blind
   by book, a finish-time model. Method of victory: blind by method and
   side. **Nothing clears.** The open-anchored model is +7.8% on 1,531 bets
   at BestFightOdds' open with positive closing-line value every year since
   2018, and has negative closing-line value at DraftKings' own opener.
3. **New.**
   - Method (`methods.md` §2): the first-posted price anchored model, with
     the line it failed on: the soft open lives at whichever book posts
     first, not at a book a pick may name.
   - Kill test (`kill-tests.md`): a mechanism proven on an archive's
     "opening line" is not proven at a decidable book until the same model
     is graded at that book's own first price, with closing-line value
     against the sharp close. Here the archive read +7.8% and DraftKings'
     opener read negative closing-line value.
   - Price routes (`market-grid.md`): the MMA feed key's coverage; two free
     archives (fight-canon-db, the Ultimate UFC Dataset) and what each holds;
     the feed's history starts 2020-06-06.
   - Trap (`porting-traps.md`): our UFC ingest stores a fight only once
     DraftKings lists it, so no other book's opener is ever in the store.
   - Scout routes (`scouting.md`): six answers and refusals.
4. **Corrected.** The open question in the first entry (is `ufc_total_rounds`
   paused?) is closed: it was paused in `config.PAUSED_MODELS` and is now
   retired. The fighting shape in `market-grid.md` said "method and duration
   props, often with no price history at all": method props have a free
   near-close history (2012+); duration props have none.
5. **The framework.** A free archive was analysed before it was stored, and
   the importer came after; step 2 now says to store a free archive the same
   way as a bought one, before the first table is read from it.

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
