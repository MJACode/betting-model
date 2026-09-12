# Session log — index

The engineering changelog for this project, archived out of CLAUDE.md on
2026-08-30 (it had reached 909 KB / ~225k tokens and was being re-read in full
at the start of every session).

**How to use it.** Don't load a month file wholesale — grep it. Every entry
keeps its original heading, so `grep -n "session 106" docs/sessions/*.md` or
`grep -rn "leak" docs/sessions/` lands on the right block.

**What belongs here vs in CLAUDE.md.** A session entry is a record of one piece
of work. The moment something in it becomes a rule that governs future work — a
convention, a threshold, a trap that bit us twice — it gets promoted into
CLAUDE.md and stated there in its own right. CLAUDE.md should be readable
without ever opening this directory.

Two truncated empty stubs (`**Session summary (2026-`) were dropped as
artifacts. Nothing else was edited; text is verbatim.

| Date | File | Entry |
|---|---|---|
| 2026-09-12 | [2026-09](./2026-09.md) | 2026-09-12, session 295 - the Claude-mobile prompt carried 52 per-model cuts as literals, so it went stale on every threshold change and only a human could refresh it; it now joins model_action_thresholds and is pasted once. Found while fixing it: threshold_sync wrote `paused` from config alone, so a model auto-paused by the 250-bet review read paused=false to the app, Discord and push - 4 mlb_prop_pitcher_k picks on the two busiest recent slates - and a hand UPDATE was erased by the next 6am run |
| 2026-09-12 | [2026-09](./2026-09.md) | 2026-09-12, session 293 - push notifications: TestFlight was never the blocker (those builds use production APNs); build 12201's provisioning profile predates expo-notifications by two months and `eas build --non-interactive` reuses the profile it holds, so the binary carries no aps-environment and Apple will not issue it a token. Four silent failures closed on the way: registration errors swallowed into console.warn with .upsert()'s error never read, opt-OUT never implemented at all (turning notifications off left enabled=true forever), no setNotificationHandler so a foreground push was never displayed, and _expo_send counting HTTP 200 as delivery. The TestFlight workflow now reads aps-environment out of the finished IPA and refuses to submit without it; Settings splits intent (the switch) from reality (a status block) and can send itself a test push. UX review ship-with-fixes, 2 blockers + 8 should-fixes + 4 considers all taken. Outstanding and Matt's alone: `eas credentials` -> Push Key |
| 2026-09-12 | [2026-09](./2026-09.md) | 2026-09-12, session 294 - EVERYTHING GOES IN SUPABASE (mike), rewritten with no exceptions after the old rule's tolerated ones turned out to be hiding 655 MB / 6,769 files of PAID NFL odds history (2020-2026, every book) on one laptop while `odds` held NFL 2026 only. data/ingestors/nfl_odds_cache_import.py moves it in, keyed on the served snapshot so a re-run imports nothing; tests/test_everything_in_supabase.py fails on any undeclared on-disk store and says the fix is an importer, not an allowlist entry |
| 2026-09-12 | [2026-09](./2026-09.md) | 2026-09-12, session 292 - the NCAAF in-play backtest mike approved: the 2025 season cost 8,360 credits not 373,240 because 5,765 snapshots were already in Supabase and the resume skipped them; states built from ncaaf_plays with no CFBD call. Production cut on FRESH quotes: ncaaf_live_total -3.4% over 280 bets, ncaaf_live_win_prob -13.1% over 51, no cut in the grid rescues either. Calibration is honest in every band and every band still loses - a model problem, not a cut problem. nfl/data/odds_cache (655 MB of paid NFL history) is still laptop-only |
| 2026-09-12 | [2026-09](./2026-09.md) | 2026-09-12, session 291 - a losing model is an ASSESSMENT to run, not a model to pause (mike; CLAUDE.md 1b). scripts/paused_model_assessment.py sweeps BOTH pause registers over the graded universe with plateau + time split + CI + the ERA check: NO model has a cut that clears on the artifact actually deployed - the three that clear pooled (pitcher_k 0.54/0.16 +3.5% over 134, runline, wnba threes) collapse to 19, 3 and 8 settled once scoped to the live model. pitcher_er is flat everywhere = a model problem, not a cut problem. NCAAF in-play needs the 2025 replay (373,240 credits of 2,178,760 left) |
| 2026-09-12 | [2026-09](./2026-09.md) | 291 — a pause must not erase a settled record, on any surface |
| 2026-09-12 | [2026-09](./2026-09.md) | 2026-09-12, session 290 - a player prop DraftKings does not list is now scored off the first bettable book that does, in BEST_LINE_BOOKMAKERS order (the line is the proposition, so never by price); picks.line_book records it and the DraftKings columns stay NULL because DraftKings never quoted it. 1,357 such propositions since 08-28 against DraftKings' 11,780 in the same markets. Two guards would have dropped them silently - the best-price re-check and the published-units gate both keyed on dk_odds - and now read the deciding price. UX review: two blockers fixed, two of my own copy changes removed as unreachable |
| 2026-09-12 | [2026-09](./2026-09.md) | 2026-09-12, session 288 - NFL prop lines lean over: blind unders -1.3% vs blind overs -7.9% over 27,976 propositions at the best price, the gradient survives at a FLAT -110 and its ordering replicates in all three seasons, and line shopping alone is worth 5.2pp. The lean predicted the split of nfl_prop_market's own record (unders +12.36% CI clear of zero, overs +4.11% spanning it), so the rule is now cut per side (over 6pp, under 5pp): 1,248 bets +166.3u +13.33% against 1,990 / +155.9u / +7.84% - more profit from fewer bets |
| 2026-09-12 | [2026-09](./2026-09.md) | 2026-09-12, session 287 - Stats filter sheet: the sort picker removed (compareRows loses its key; the module surface is now guarded against it returning) and the hit-rate band replaced by a two-thumb slider, its geometry/bounds/gesture-intent split into lib/rangeSlider.ts and pinned by 44 checks; the UX review caught two defects tsc could not - the responder committed a value on GRANT so a failed scroll silently re-filtered the board, and half of each thumb was outside the responder's view at 0%/100% - both fixed, plus four more findings and three Considers; a SECOND review pass on the fixes found four more (the sort arrow appended inside a fixed truncating cell, a sloppy tap set nothing because release used the drag slop, end labels that read as tick marks once a thumb moved, and a capital mid-phrase in the pill) |
| 2026-09-11 | [2026-09](./2026-09.md) | 2026-09-11, session 286 - prop window stays 24h (re-measure October); the market-anchored shape simulation was built and run on receiving and rushing yards against DK's alternate ladder and FAILED its pre-registered bars (every arm -8% to -17%, both seasons negative, placebo worse); the ladder itself is over-priced on every over band and quotes no under; under-bias audit = distribution mis-fit, not level. Stat-model line closed; pausing the ten put to mike |
| 2026-09-12 | [2026-09](./2026-09.md) | 2026-09-12, session 285 - the Live segment was invisible on the other sports because it was conditional on a live PICK (not a live game), and only MLB/NCAAF/NFL have an in-play lane at all (WNBA's 102 live BETs were prop models flagged is_live); matt's call reverses 2026-09-06 - it is now ALWAYS on for every sport and called Live Signals, the dot becomes the conditional thing, both auto-redirects removed, and the empty state distinguishes 'no edge right now' from 'no live model for this sport' via the new mobile/src/lib/liveSports.ts pinned to config.LIVE_MODELS |
| 2026-09-11 | [2026-09](./2026-09.md) | 2026-09-11, session 286 - the credit guards on the paid backfills were decoration: I hand-picked --max-credits 400,000 and --floor 2,000,000, the ceiling was PER PROCESS (4 shards = 1.6M against a 373,240 plan), the refuse-to-start check compared the season's plan to one shard's ceiling, and the floor sat below where the run lands so it could never fire. Both halves now derived in odds_quota.py (ceiling = the run's own printed plan split by shard share; floor = reserve_days x MEDIAN measured burn from odds_api_quota, refusing when it cannot measure), shared by both ingestors, plus parse_shard refusing `4/4` which silently pulled nothing. NCAAF pull restarted under them |
| 2026-09-11 | [2026-09](./2026-09.md) | 2026-09-11, session 285 - both NCAAF live lanes PAUSED (mike): 55 settled 28-27 -2.99u claiming 67.5% winning 50.9%, ~86% of priceable 09-05 games got a bet; the pause now reaches the NCAAF loop (it was a silent no-op there); production thresholds table mirrored the same evening; the Live board honours the pause; proof path = 2025 DK in-play replay (ingestor + harness written and tested on synthetic data, dry-run 18,662 calls / 373,240 credits, NOT run - spend is mike's call) |
| 2026-09-11 | [2026-09](./2026-09.md) | 2026-09-11, session 284 - the prop-offset grader dropped every same-UTC-day quote ('T' > ' ' string compare); corrected, nfl_prop_market is 1,990 bets +7.84% (CI clear of zero, 3/3 seasons), the last 4h is its weakest band and the Saturday-morning read its strongest, so the ceiling is NOT tightened (36h widening put to mike); docs/nfl_prop_method_search.md sets out the one method left for the stat models (market-anchored shape simulation vs alt ladders) with pre-registered bars |
| 2026-09-11 | [2026-09](./2026-09.md) | 2026-09-11, session 283 - the app's bundled thresholds.ts is the cold-start fallback and nothing tested it against config.py: 1 live model absent outright (nfl_live_prop, announcing on Discord while the app refused all its BETs), 16 paused-here-live-there, 3 live-here-paused-there, 24 cut mismatches and 40 missing price floors; synced and pinned by tests/test_mobile_threshold_parity.py. Separately measured: 11 paused models hold 1,395 settled BETs the Models tab drops entirely - not fixed |
| 2026-09-11 | [2026-09](./2026-09.md) | 2026-09-11, session 279 - the live lock_key was already fixed (#631/#633, verified 92 -> 0 unannounceable, not rebuilt); its residue was opening_signals holding 15 rows for 8 propositions, all seven duplicates stamped by one re-capture pass - scripts/dedupe_opening_signals.py clears them behind four gates, 15 -> 8 |\n| 2026-09-10 | [2026-09](./2026-09.md) | 2026-09-10, session 278 - the Gilbert / deGrom Under 6.5 K picks were scored by the look-ahead pass with no weather row, so temp_f was filled 0.0 (a 0°F game); reproduced to four decimals; 814 of 3,971 2026 starts had no weather row (72 earlier BETs scored the same way). Fixed: a prop row missing a feature is not scored (only the umpire pair is imputed, by name), weather is fetched for the look-ahead window at the game's own hour, umpires refresh every pass, the 814 rows backfilled; picks stand (mike) |
| 2026-09-11 | [2026-09](./2026-09.md) | 2026-09-11, session 282 - the settled-pick cache guard pinned the literal "v3", so the two CORRECT key bumps that followed (#630, #634) turned it red and kept it red; it now pins the invariant (version >= 3) instead of the version, watched failing on a v2 regression and on an unversioned key |
| 2026-09-11 | [2026-09](./2026-09.md) | 2026-09-11, session 281 - the opener's 1-point rule measured -0.03% over 728 bets on bettable books (no cut is statistically profitable); floor raised to |dev| >= 2.0 with the 0.55 gate restored, seven open Week-1 openers voided; the six pre-09-10 wind picks and twenty pre-Tuesday NFL prop picks DELETED with their ledger rows on mike's instruction (snapshot local, picks_log has all 26) |
| 2026-09-11 | [2026-09](./2026-09.md) | 2026-09-11, session 280 - the Games filter on Picks and Stats (one shared selection, not persisted because a game_id is one fixture on one date) plus a matchup-grade floor; the review's blocker was that BOTH screens pruned the shared selection against their own games list, and Picks - which never unmounts - pruned away every id picked on the other tab |
| 2026-09-11 | [2026-09](./2026-09.md) | 2026-09-11, session 279 - the live lock_key was already fixed (#631/#633, verified 92 -> 0 unannounceable, not rebuilt); its residue was opening_signals holding 15 rows for 8 propositions, all seven duplicates stamped by one re-capture pass - scripts/dedupe_opening_signals.py clears them behind four gates, 15 -> 8 |
| 2026-09-11 | [2026-09](./2026-09.md) | 2026-09-11, session 279 - the live lock_key was already fixed (#631/#633, verified 92 -> 0 unannounceable, not rebuilt); its residue was opening_signals holding 15 rows for 8 propositions, all seven duplicates stamped by one re-capture pass - scripts/dedupe_opening_signals.py clears them behind four gates, 15 -> 8 |\n| 2026-09-10 | [2026-09](./2026-09.md) | 2026-09-10, session 278 - the Gilbert / deGrom Under 6.5 K picks were scored by the look-ahead pass with no weather row, so temp_f was filled 0.0 (a 0°F game); reproduced to four decimals; 814 of 3,971 2026 starts had no weather row (72 earlier BETs scored the same way). Fixed: a prop row missing a feature is not scored (only the umpire pair is imputed, by name), weather is fetched for the look-ahead window at the game's own hour, umpires refresh every pass, the 814 rows backfilled; picks stand (mike) |
| 2026-09-10 | [2026-09](./2026-09.md) | 2026-09-10, session 280 - NCAAF pre-game investigation, then the approved work: the board is one model (moneyline paused; both spread tiers cannot fire on this feed - 18 of 249 games had a Bovada opener within 90 min and 17 of those agreed within 0.5 pts, zero premium-band candidates); the totals model leans under on ~3/4 of the 2026 board at every lead while the market is unmoved (53.2 vs a 52.6 early-season close mean 2023-25) and every backtest season leaned over or flat - cause not established, the feature-vector comparison is the next query; the "watching" NONE rows persist no reason (0 of 1,012); a paused model still writes AVOID rows (80); Kalshi lists NCAAF game/total/spread series. Shipped after approval (mike): a paused model is paused on BOTH sides (scorer._paused_signal, sport-agnostic) and declined rules persist their reason (scorer._apply_no_signal); the under-lean traced to the 2026 inputs (spread across scoring/defence features, no NaN or artifact bias; scripts/ncaaf_search/totals_input_drift.py); the information test on the totals rule (b +0.14 / +0.10, neither excluding zero, book beats raw model both seasons); a 20-credit 19-book snapshot (FanDuel and the Kambi-fed books post ahead of DK, every never-requested book behind); Kalshi NCAAF game markets recorded hourly (kalshi_game_markets, 5,027 contracts at first snapshot); issued-forecast weather for 2024-25 (game_weather_issued) with the four-arm experiment. Spread tiers stay live at mike's call; third part (09-11): PR #645 merged and deployed, both scorer fixes verified on the first post-deploy pass (75/75 NCAAF non-BET rows carry a reason, zero paused-model AVOIDs), the 11 snapshot-created games rows removed, and the Kalshi event-to-game join built (kalshi_ncaaf_events: 154/239 events resolved, every FBS-vs-FBS one); fourth part: worker_jobs.run_after + a verify_checks job type (tracking/deploy_checks.py) so a read-only check runs on the worker at a chosen time and its verdict lands in the ops channel; two declared jobs confirm the AVOID sweep and the Kalshi snapshot |
| 2026-09-11 | [2026-09](./2026-09.md) | 2026-09-11, session 289 - the live lanes decide at the best bettable in-play price (mike, "yes do everything"): MLB through classify_live_signal with the cap on the DK edge, NCAAF's poll widened to the five single-region bettable books at zero extra credits (measured), every candidate quote score-gated; nfl_live_prop cannot (DK-only feed); #634 merged and proven on the running system (878 of 883 new rows carry decision_book, 348 at a non-DK book) |
| 2026-09-10 | [2026-09](./2026-09.md) | 2026-09-10, session 278 - the Gilbert / deGrom Under 6.5 K picks were scored by the look-ahead pass with no weather row, so temp_f was filled 0.0 (a 0°F game); reproduced to four decimals; 814 of 3,971 2026 starts had no weather row (72 earlier BETs scored the same way). Fixed: a prop row missing a feature is not scored (only the umpire pair is imputed, by name), weather is fetched for the look-ahead window at the game's own hour, umpires refresh every pass, the 814 rows backfilled; picks stand (mike) |
| 2026-09-10 | [2026-09](./2026-09.md) | 2026-09-10, session 277 - the 47-slate live cut result was carried by stale quotes production declines (fresh: 21 bets 12-9); the 2025 calibration map is fitted (helps, transfers) but no calibrated cut is a plateau on fresh quotes of both seasons; twin-game merge script (dry-run) and the SBR loader fix |
| 2026-09-10 | [2026-09](./2026-09.md) | 2026-09-10, session 276 - mlb_live_total_runs against a bought season of DK in-play history (260k credits): shipped cut delivers 66% all-quotes / 61% fresh-only, probability ~8 pts over-confident, cut not moved; plays gain clock times; four franchises filed twice in games |
| 2026-09-10 | [2026-09](./2026-09.md) | 2026-09-10, session 275 - a recap that a later settlement invalidated is restated automatically on Discord and X (trigger: settled_at > the snapshot's published_at, never a count difference, because the recap query applies today's cuts and every 09-01..09-08 count has drifted); forward-looking from 2026-09-10; the nflverse CSV fetch retries a transient 403 |
| 2026-09-10 | [2026-09](./2026-09.md) | 2026-09-10, session 274 - NFL prop CLV was never captured: the prop-CLV model-to-market map had no NFL entries and its guard test excluded nfl_prop; twelve models added, the market-relative rules take the market from the row and close at their own book (label suffix), backfill is automatic on the next settle |
| 2026-09-10 | [2026-09](./2026-09.md) | 2026-09-10, session 273 - the 2026-09-09 recap posted MLB-only to Discord and X: NFL box scores were ingested after settle, so the three NFL BETs settled at 07:24, an hour after the recap was ledgered. Steps 4b/4c moved before settle (Step 0h); new publish_results worker job re-posts both surfaces; same shape measured on 09-04 (NCAAF) and 09-05 (NCAAF + UFC) |
| 2026-09-09 | [2026-09](./2026-09.md) | 2026-09-09, session 279 - DK-only removed (mike): a pre-game pick is decided, sized and settled at the best bettable price at the DraftKings line, recorded as picks.decision_*; no cut moved (the best-price sweep found none shippable, so each is 0.68pp looser); scorer, settlement, matview, record views, RPCs, Discord, push, the app and the prompt SQL all cut at the decision price; migration applied to production first |
| 2026-09-09 | [2026-09](./2026-09.md) | 2026-09-09, session 268 - the Stats board's leaderboard reads were never paged and every one is over the 1,000-row cap (NFL last-10 is 12,850 rows, NCAAF 54,687), so the NFL board - which opens filtered to the slate - had 6 of tonight's players and no quarterback; paged and narrowed to the slate's teams server-side. Separately: NFL game lines are DK spreads only, because odds_ingestor.SPORT_KEYS has no NFL entry |
| 2026-09-09 | [2026-09](./2026-09.md) | 2026-09-09, session 266 - the live cut re-swept on the new model over 47 slates: 0.70 -> 0.72, ~1.9 bets a slate, chosen as the centre of a plateau; scripts/live_cut_sweep.py |
| 2026-09-09 | [2026-09](./2026-09.md) | 2026-09-09, session 272 - the Picks market filter offered MLB's Pitcher/Batter markets on every sport's board; scoped to the picks on screen, and the thirteen unlabelled NFL models (twelve prop + nfl_live_prop) that were rendering their raw model_id AND skipping the category cut entirely now carry labels and a derived category |
| 2026-09-09 | [2026-09](./2026-09.md) | 2026-09-09, session 271 - the betslip's five-line negative-EV note becomes one line plus a Details tooltip, the green "Bet on DraftKings" button is replaced by the book tiles themselves (which now open the hand-off sheet at the tapped book), and Save joins a two-up grid below the card |
| 2026-09-09 | [2026-09](./2026-09.md) | 2026-09-09, session 271 - first live NFL game: the prop poll sent ESPN's event id to The Odds API and got 422 on every call, so the lane never saw a quote; the book's id is now resolved from the slate anchor by matchup |
| 2026-09-09 | [2026-09](./2026-09.md) | 2026-09-09, session 270 - the NFL board did not line up with Discord: one lock_key served a whole game's nfl_prop_market props (8 BETs, 7 keys - one pick could never publish), and six VOIDED wind picks were still green in the app; the key moved to tracking/publish_keys.py with the ledger migrated first |
| 2026-09-09 | [2026-09](./2026-09.md) | 2026-09-09, session 270 - the live lock_key carries the player columns, so two players' live props in one game are two announcements; one settled ledger row moves, re-ledgered by a new backfill_publish_keys worker job because the session's Supabase MCP is read-only |
| 2026-09-09 | [2026-09](./2026-09.md) | 2026-09-09, session 269 - live picks post to their sport's live Discord channel (DISCORD_WEBHOOK_LIVE_{NFL,MLB,NCAAF}, mike's rule promoted to CLAUDE.md); the NFL in-play lane announced nowhere since 2026-09-05 and now announces every committed live BET |
| 2026-09-09 | [2026-09](./2026-09.md) | 2026-09-09, session 268 - tackles unpaused (#623, #624); the second pass over every DraftKings prop data set: earlier snapshots, the alternate ladders, the line's own movement (which the models predict, worth less than the vig) and a boosted stack -- DK is efficient against the ten at every snapshot and on its ladder |
| 2026-09-09 | [2026-09](./2026-09.md) | 2026-09-09, session 267 - the profitable NFL prop model was tackles all along, grading the wrong stat: solo+with_assist+assists matches the box score, and on it the model is +50.24u over 363 bets, positive all three seasons; at DraftKings nothing else beats a line the book prices flat; pass attempts at the soft books is a two-of-three lead |
| 2026-09-09 | [2026-09](./2026-09.md) | 2026-09-09, session 267 - the live cut re-swept on the new model over 47 slates: 0.70 -> 0.72, ~1.9 bets a slate, the centre of a plateau; scripts/live_cut_sweep.py; a shared-checkout collision recorded |
| 2026-09-09 | [2026-09](./2026-09.md) | 2026-09-09, session 266 - the eleven NFL prop models hold no information the DraftKings line lacks: the book beats every one on Brier, calibration reaches the book and no further, the residual coefficient never clears zero out of sample; the 87%-unders lane was a mean bias, and correcting it produces zero bets |
| 2026-09-09 | [2026-09](./2026-09.md) | 2026-09-09, session 265 - #620 merged and mlb_live_total_runs v20260908_230751 promoted, registered only after the worker deploy went green; the running-system proof is tonight's first live pick |
| 2026-09-08 | [2026-09](./2026-09.md) | 2026-09-08, session 264 - the live totals model was memorising its training games: KFold(shuffle=True) on play rows made its CV a lookup (CV NLL 1.92, holdout 2.74), which is the real cause of "claims 73%, delivers 54%"; the approved feature swap is good and was never the fix |
| 2026-09-08 | [2026-09](./2026-09.md) | 2026-09-08, session 259 - the model_calibration check was grading the RAW probability over a window that predated every promoted map, so three of the four models it accused were artefacts; four becomes one, and that one is real |
| 2026-09-08 | [2026-09](./2026-09.md) | 2026-09-08, session 258 - the "tons of skipped and stale" was my own wrong-dated verification run; the NCAAF residue cleared (36 split slots -> 0, 1,211 paid odds rows repointed rather than deleted); and a health row now carries a one-word reason and a derived refresh frequency |
| 2026-09-08 | [2026-09](./2026-09.md) | 2026-09-08, session 257 - golf retired (the DataGolf key was never set, so the sport produced nothing ever) and its dead chips removed; the health clock was the container's UTC, not ET; and NCAAF is writing games nobody will play - 76 duplicated matchup slots, two mechanisms, one CRIT check |
| 2026-09-08 | [2026-09](./2026-09.md) | 2026-09-08, session 256 - why health checks are routinely SKIPPED: three of four were honest (NBA offseason, the WNBA's FIBA World Cup break), golf_odds had never once produced a verdict in 59 runs, and model_calibration was computed and then thrown away before the persist |
| 2026-09-07 | [2026-09](./2026-09.md) | 2026-09-07, session 255 - the ops roster called seven working models broken: five score from a frozen rule and two from an off-registry LightGBM engine, config.SCORING_METHODS declares which, and PAUSED moving to the front of the CASE makes the red banner true for the first time |
| 2026-09-07 | [2026-09](./2026-09.md) | 2026-09-07, session 254 - "highest conviction plays only": the conviction sort does not exist pre-game and is inverted on the live lane, so the cut was made on price instead |
| 2026-09-08 | [2026-09](./2026-09.md) | 2026-09-08, session 252, fifth part — steam lag and consensus-anchor tests on the 13-book backfill, both null: the NCAAF game-line market is one number across books; the totals rule's edge is model-side and early-season |
| 2026-09-08 | [2026-09](./2026-09.md) | 2026-09-08, session 252, fourth part — a dropped connection no longer costs a pass: the DB wrapper reconnects, the scorer commits one game at a time, the ops log records each failed step's own reason; the three-day failure table and its causes |
| 2026-09-07 | [2026-09](./2026-09.md) | 2026-09-07, session 252, third part — the NCAAF totals lead limit removed (fires at line release) and the scoring window widened to the season; "all books" measured: every book posts within the same day, no speed to gain |
| 2026-09-07 | [2026-09](./2026-09.md) | 2026-09-07, session 252 continued — the NCAAF totals rule measured at 0-5 days out on the DK backfill: flat at every lead (53.8-56.4% vs 56.4% at the close, no CLV), so the 1-day limit is a timing choice; 5 days proposed with Matt's stamp |
| 2026-09-07 | [2026-09](./2026-09.md) | 2026-09-07, session 253 - sixteen unsettled BETs: an FCS visitor resolved to the FBS school it starts with (six NCAAF live totals), three MLB windows that could not self-heal, and an NFL prop path that would have voided week 1 |
| 2026-09-07 | [2026-09](./2026-09.md) | 2026-09-07, session 252 — why NCAAF has no picks for next week (the opener rule is structurally dormant on this feed, measured with one historical call), rebuild declined, and the starter-out hindsight test comes back null |
| 2026-09-07 | [2026-09](./2026-09.md) | 2026-09-07, session 251 — NFL prop cuts tightened to the top decile (112 BETs -> 16 on one slate), and the scorer stops reading one date while its card reads ten |
| 2026-09-07 | [2026-09](./2026-09.md) | 2026-09-07, session 250 — NFL props: the rule fired for the first time ever, and the eleven models unpaused yesterday score only today's date while the card looks ten days ahead ([deep dive](../reviews/2026-09-07-nfl-props-deep-dive.md)) |
| 2026-09-07 | [2026-09](./2026-09.md) | 2026-09-07, session 249 — MLB volume: half the picks come from a calibration switch that never reached the props |
| 2026-09-06 | [2026-09](./2026-09.md) | 2026-09-06, session 248 — a live pick reached Discord and never reached the app, and the pre-game card posted twice |
| 2026-09-06 | [2026-09](./2026-09.md) | 2026-09-06, session 247 — the line ruler is drawn in the mode's own idiom, so Over is the book's line |
| 2026-09-06 | [2026-09](./2026-09.md) | 2026-09-06, session 246 — why the prop rule never fired, in any sport |
| 2026-09-06 | [2026-09](./2026-09.md) | 2026-09-06, session 245 — the go-live gate comes out of the app's copy entirely |
| 2026-09-06 | [2026-09](./2026-09.md) | 2026-09-06, session 244 — the Live tab was empty 81% of the time, so it became a segment |
| 2026-09-07 | [2026-09](./2026-09.md) | 2026-09-07, session 244 — six wind picks stop being official, without being deleted |
| 2026-09-06 | [2026-09](./2026-09.md) | 2026-09-06, session 243 — the wind model was firing at 8 days out, and the gate that used to stop it was a side effect |
| 2026-09-06 | [2026-09](./2026-09.md) | 2026-09-06, session 242 — the go-live gate stops being quoted at models it does not apply to |
| 2026-09-06 | [2026-09](./2026-09.md) | 2026-09-06, session 241 — the parlay save → edit → save round trip, and the exit that scrolled away |
| 2026-09-05 | [2026-09](./2026-09.md) | 2026-09-05, session 240 — "when there is a bet from the model, post the pick": publishing moves to whoever writes the pick |
| 2026-09-05 | [2026-09](./2026-09.md) | 2026-09-05, session 239 — calibration comes out of the app UI entirely, and the opening-signal experiment link with it |
| 2026-09-05 | [2026-09](./2026-09.md) | 2026-09-05, session 239a — the calibration chart and the opening-signal experiment link come off the Record screen |
| 2026-09-05 | [2026-09](./2026-09.md) | 2026-09-05, session 238 — the build asks iOS whether each book's app is installed; the App Store is only for members who don't have it |
| 2026-09-05 | [2026-09](./2026-09.md) | 2026-09-05, session 235 — latest-line state tables: the Stats/Picks line timeouts, fixed structurally |
| 2026-09-05 | [2026-09](./2026-09.md) | 2026-09-05, session 234 — the At-Most side is missing from the FEED, and the parser is exonerated |
| 2026-09-05 | [2026-09](./2026-09.md) | 2026-09-05, session 237 — Doubles and Triples were never blank because the market didn't exist; nobody had asked |
| 2026-09-05 | [2026-09](./2026-09.md) | 2026-09-05, session 236 — the Movement tab and the per-card Context button come off the Picks surface |
| 2026-09-05 | [2026-09](./2026-09.md) | 2026-09-05, session 235 — the wind bet that showed in the app and not in Discord, and the repair path that still read the abandoned table |
| 2026-09-05 | [2026-09](./2026-09.md) | 2026-09-05, session 234 — the game time went under the name, and SPOT became a graded matchup difficulty |
| 2026-09-05 | [2026-09](./2026-09.md) | 2026-09-05, session 233 — "nothing shows for Cesar's and FanDuel": we have their lines, and the side we do not have is the one that was on screen |
| 2026-09-05 | [2026-09](./2026-09.md) | 2026-09-05, session 232 — the app and Discord are one board: publishing moved off the capture table |
| 2026-09-05 | [2026-09](./2026-09.md) | 2026-09-05, session 231 — the college prop probe came back 12x cheaper than I said, and Matt turned it on |
| 2026-09-05 | [2026-09](./2026-09.md) | 2026-09-05, session 230 — the same bet, eleven times: a lock that released when a pick was graded |
| 2026-09-05 | [2026-09](./2026-09.md) | 2026-09-05, session 229 — college football player props, built and measured before they are scheduled |
| 2026-09-05 | [2026-09](./2026-09.md) | 2026-09-05, session 228 — alternates on every pass, and for WNBA, NBA and NFL |
| 2026-09-05 | [2026-09](./2026-09.md) | 2026-09-05, session 227 — "Yes to alternate lines", team line legs, the Picks screen says when its lines fail, and Mobbin is one route |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 223 — "filters not working" was a LIVE/Live name collision, not a bug; a footnote was never going to fix an ambiguous control |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 222 — "monthly API calls" was unobtainable (log pruned at 7 days); rollup added, plus model sport/lane filters and an Odds API panel |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 221 — the last three write grants were measurable from the call sites, not a decision; feedback needed no grant at all |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 220 — the read surface was never checked against the write surface; game_weather plus sixteen views gave up writes no policy backed |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 226 — three complaints after the betslip flow shipped: dashes at game time, BetMGM not opening, and "take me to the App Store" |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 225 — "I gave you bad info": the line pill asks to add to the betslip, and the betslip opens at any book |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 224 — the "What {sport} models look at" card is removed from the Models tab, one day after it shipped |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 223 — "pulling some lines but not all of them": every response is capped at 1,000 rows, and the Stats board asked for 20,000 |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 222 — "still not seeing the lines": the poller's re-seed was a 700 MB table scan every 15 minutes, and the views had to survive it |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 221 — the Teams board timed out, and so did "today's lines": one view keyed wrong, one function recomputing a season per tap |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 220 — your sportsbooks becomes a SET: the Stats board shows the best of them, and the betslip button follows |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 219 — the equity curve was still on the April window, because a migration in the active list restored it every pass |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 218 — the SPOT column's second review: a spoken tier that said "TGH", a column that ate the player's name, and "Jr." for every suffixed pitcher |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 217 — 2026-09-01 is the official live date, and the app now mirrors Retool by reading the same view |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 216 — eleven models told the dashboard they had never fired; the whole of UFC was one of them |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 215 — the Stats line pill becomes the bet button, the rows lose their sublines, and the stat groups become tabs |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 214 — the sportsbook picker is the Stats page's setting; Picks and Signals are best-line across books and not switchable |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 213 — the Stats tab shows the user’s sportsbook’s current line for every player and team, separate from the models; the pre-game poller is wiping prop rows |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 212 — the last RLS-off table closed (0 of 84 now); the guard bug recurred within the hour, so three guards are derived rather than named |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 211 — RLS on the three worker-only tables; the DDL guard moved inside the helper after operations.md caught an "idempotent so free" comment |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 210 — the PUBLIC grant swept off all 20 declared callables that still carried it; callable-by-PUBLIC 21 -> 1 |
| 2026-09-04 | [2026-09](./2026-09.md) | 2026-09-04, session 208 — the function grants; a literal grep for .rpc() misses eight the app reaches by ternary |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 210 — a live NCAAF total was bet 0.6s after a touchdown against the book's pre-touchdown price; an event-relative staleness guard (`quote_predates_score`) for NCAAF and NFL |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 209 — the Models tab priced unpriced UFC picks at a fabricated -110 and the Record tab did not; one `flatPnl` rule for every client tally, `· N unpriced` on both rows |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 208 — the model-inputs card drops its closing note (Matt) |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 207 — pick card: "No MGM line" note removed, post time is the footer, raw timestamp fixed |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 207 — default privileges revoked; the silent-failure trap that creates gets a manifest and a tripwire |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 206 — the pitcher-stats leak; all four MLB models re-measured; over_under paused, f5 retrained, era_last3 made a true rolling window |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 205 — the anon grant on odds is inert under RLS; the one on worker_jobs is not, and followups.md said the opposite |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 204 — the pre-game bound moves off the schedule, and the derivation it moves onto is wrong for 7 of 415 games |
| 2026-09-03 | [2026-08](./2026-08.md) | 2026-09-03, session 203 — all four repairs applied on the Railway worker; the first attempt rolled back on an unwalked third-level view dependency |
| 2026-09-03 | [2026-08](./2026-08.md) | 2026-09-03, session 202 — matview LATERAL fix verified read-only before applying; 69 orphans is really 51 once live and future games are excluded |
| 2026-09-03 | [2026-08](./2026-08.md) | 2026-09-03, session 201 — the matview's grading LATERAL uses LIMIT 1 without ORDER BY on a table with 20k duplicate rows |
| 2026-09-03 | [2026-08](./2026-08.md) | 2026-09-03, session 200 — UFC units, an UNPRICED state, and a date filter whose preset buttons were silently no-ops |
| 2026-09-03 | [2026-08](./2026-08.md) | 2026-09-03, session 199 — profit_flat invents -110 for unpriced picks; UFC/NCAAF absent from the matview; the date filter uses UTC |
| 2026-09-03 | [2026-08](./2026-08.md) | 2026-09-03, session 198 — the pre-game prop price bound ships; 47 picks priced off in-play quotes queued for deletion |
| 2026-09-03 | [2026-08](./2026-08.md) | 2026-09-03, session 197 — the prop scorer priced pre-game picks off in-play quotes; 45 of 113 batter_hits bets had no real edge |
| 2026-09-03 | [2026-08](./2026-08.md) | 2026-09-03, session 196 — there has never been a live player prop model, and the go-live gate cannot tell +7% from -14% |
| 2026-09-03 | [2026-08](./2026-08.md) | 2026-09-03, session 195 — the CLV backlog is not a backlog (99.7% of capturable picks are measured), and the live record is real, negative, and invisible to the matview |
| 2026-09-03 | [2026-08](./2026-08.md) | 2026-09-03, session 194 — a Picks & CLV tab on the Retool dash; two-thirds of measured CLV is exactly zero, and two rollup denominators were wrong before it shipped |
| 2026-08-31 | [2026-08](./2026-08.md) | 2026-08-31, session 193 — Models and Ops ported to Retool; the roster is 70 models not 84, q_runs names two columns that don't exist, and the health filter can never fire |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 185 — Phase 1: four team-stats tables rebuilt; the bigger leak is in mlb_pitcher_stats |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 184 — the team-stats leak is four sports (NCAAF clean); the rebuild scoped |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 183 — mlb_team_stats carries season-final numbers under a season-start date: every MLB model is trained on the future |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 182 — the Models tab says what each sport's models look at |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 182 — the parlay line shop stops comparing prices across different lines |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 182 — shuffled CV in the tuner; walk-forward shows f5 worked for four seasons and broke in 2026 |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 181 — bet card shows every book's line as a button; Live tab is DK only |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 181 — mlb_f5_moneyline retrained on 2019-2025: no better, and the live model's registry accuracy was in-sample |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 180 — f5 sweep says no min_edge works; the first-pitch guard is two guards |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 179 — house juice floor, the health check nobody could fix, and the .claude/rules split |
| 2026-09-02 | [2026-09](./2026-09.md) | 2026-09-02, session 178 — retired models are absent, not decorated: the first change shipped through the UX designer agent |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 180 — the rebrand re-reviewed with Mobbin live: the betslip bar floats, one BrandMark, and what the library actually holds |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 179 — the app wears the real brand: @signalbasepicks mark, amber-on-navy chrome, icon set re-drawn |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 172 — the NFL wind card had been failing on every run, behind a comment that said it could not |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 171 — the worker image was 60% GPU driver and dashboard it never runs |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 178 — card leads with the best book; the missed X recap recovered, after I read a UTC stamp as ET |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 177 — free surfaces name the cheaper book; five us2 books DOUBLE the odds bill |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 176 — a restatement published a worse book than the post it corrected |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 175 — CLAUDE.md trimmed 45.6 KB to 39.4 KB: every rule verbatim, the evidence moved to docs/rules_evidence.md |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 174 — retention keeps the close, and the first version timed the pruner out |
| 2026-09-03 | [2026-09](./2026-09.md) | 2026-09-03, session 173 — Stage 2 step 1: the best-price threshold sweep, and a test that did not test what it claimed |
| 2026-09-02 | [2026-09](./2026-09.md) | 2026-09-02, session 172 — pre-game best line: two DK-only markets, and 26% of best prices could not be bet |
| 2026-09-02 | [2026-09](./2026-09.md) | 2026-09-02, session 171 — X and Discord published different records for the same day: 0-1 vs 23-12 |
| 2026-09-02 | [2026-09](./2026-09.md) | 2026-09-02, session 178 — the Record tab was empty because the record view had outgrown the API timeout |
| 2026-09-02 | [2026-09](./2026-09.md) | 2026-09-02, session 170 — batter HR and batter RBI RETIRED: out of the app, out of every model total, picks kept |
| 2026-09-02 | [2026-09](./2026-09.md) | 2026-09-02, session 169 — the 24.6-hour query nobody had measured, and two PRs merged |
| 2026-09-02 | [2026-09](./2026-09.md) | 2026-09-02, session 169 — the front-end UX designer: a subagent, its checklist, and the scan that makes two reviews comparable |
| 2026-09-02 | [2026-09](./2026-09.md) | 2026-09-02, session 132 — WNBA: model-first path CLOSED by experiment; the market-relative prop rule ported; my assists re-cut WITHDRAWN at merge (moved out of CLAUDE.md 2026-09-02) |
| 2026-09-01 | [2026-09](./2026-09.md) | 2026-09-01, session 168 — the fix verified in production, and the tripwire that would not have caught the next one |
| 2026-09-01 | [2026-09](./2026-09.md) | 2026-09-01, session 167 — the Stats page error was the whole API, and the cause was our own DDL |
| 2026-08-31 | [2026-08](./2026-08.md) | 2026-08-31, session 164 — "under 10 seconds" was already true; the gap was the moves we never saw |
| 2026-09-01 | [2026-08](./2026-08.md) | 2026-09-01, session 166 — the shortcuts named; the job queue, the Pinnacle backfill, and three bugs the work found in itself |
| 2026-08-31 | [2026-08](./2026-08.md) | 2026-08-31, session 166 — the app was right and a day behind: OTA bundles now apply themselves |
| 2026-08-31 | [2026-08](./2026-08.md) | 2026-08-31, session 165 — model quality: calibrated decisions, market-relative props, Savant freshness, opposing-starter activation |
| 2026-08-31 | [2026-08](./2026-08.md) | 2026-08-31, session 164 — the database credential outage nothing caught, and the watchdog that would have |
| 2026-08-31 | [2026-08](./2026-08.md) | 2026-08-31, session 163 — the case collision that broke a test for days; bovada on; BetRivers solved |
| 2026-08-31 | [2026-08](./2026-08.md) | 2026-08-31, session 162 — every book probed from BOTH addresses; a 400 is a lead, not a failure |
| 2026-08-31 | [2026-08](./2026-08.md) | 2026-08-31, session 161 — bovada is the second live source, and DK runs on mike's machine |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 159 — the Stats board qualifier is gone: no games-played minimum in any sport or mode |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 159 — the iOS build that never started: an EAS quota refusal reported as a bare "exit code 1" |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 160 — the MLB record audited end to end: grading clean at 2,734/2,734, and the published board counts picks that were never bets |
| 2026-08-31 | [2026-08](./2026-08.md) | 2026-08-31, session 160 — the DK direct feed is built and cannot run on Railway; bovada can |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 159 — 30s on mike's reaffirmed call; and the NFL models were never missing, they were invisible |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 158 — line shopping reaches the live board; the pre-game half was already done |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 157 — the live loop's midnight blind spot: #296 fixed one boundary, not the bug |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 156 — DK's own line, pulled and compared: the aggregator is coarse, not behind |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 155 — the profitable-looking models, put through a time split: four unpaused, the headline candidate killed |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 154 — the models publish probabilities 6-16pp above what they deliver; a calibration layer, and the gate that never caught it |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 152 — Recent News on the prop screens: a newspaper icon, a sheet, and a provider seam |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 151 — the custom-model builder stopped putting our numbers in the user's mouth, and the card leads with bets instead of filters |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 150 — NCAAF gets a player leaderboard: the CFBD box score the QB pull was already fetching and throwing away |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 149 — the X placeholder points at the real account (@signalbasepicks) |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 153 — live cutoffs set, plus a recalibration loop that re-derives them every pass and publishes to the dashboard |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 148 — the accented-name prop gap: every José, Acuña and Hernández was skipped by every priced prop market |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 147 — "cards show DK, should be dynamic" (3rd ask): audited already-shipped, saved parlays book-aware, card's book stat opens the picker |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 146 — the Picks board sorts by where the public is, and the card prints the number |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 145 — one membership, two surfaces: App Store auth/billing + Discord (Whop) linking |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 144 — CLV across a moved line: the signal line vs the closing line for NCAAF, MLB and WNBA |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 143 — the published stake is the exact number: units go to two decimals |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 141 — the monitor becomes a one-stop operational dashboard: Models + Ops views |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 140 — CLAUDE.md split: 909 KB → 31.7 KB, the session log archived, the threshold SQL generated |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 135 — the two binary MLB live models RETIRED (registry, artifacts, thresholds), totals stays |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 137 — every signal and live bet now carries the time it posted |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 139 — an evening NCAAF pick can finally settle: the ET/UTC duplicate games row |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 138 — Supabase "Disk IO Budget depleting" alert: five missing indexes found and fixed in production |
| 2026-08-30 | [2026-08](./2026-08.md) | 2026-08-30, session 138 — real-time monitoring dashboard: every API call and every pick, live |
| 2026-08-29 | [2026-08](./2026-08.md) | 2026-08-29, session 134 — NCAAF live loop polls state every 10s (was 45s), on split cadences |
| 2026-08-29 | [2026-08](./2026-08.md) | 2026-08-29, session 133 — live picks lock at first BET signal (MLB + NCAAF) + "Locked" indicator |
| 2026-08-29 | [2026-08](./2026-08.md) | 2026-08-29, session 132 — NCAAF was invisible because scoring was CRASHING; plus "watching" rows so the board is never empty |
| 2026-08-29 | [2026-08](./2026-08.md) | 2026-08-29, session 134 — sportsbook picker: reference-style sheet with a green Apply button; Settings opens the same sheet |
| 2026-08-29 | [2026-08](./2026-08.md) | 2026-08-29, session 133 — Betslip is only the user's slip: Optimize + Same-game removed, and a phantom badge can now be cleared |
| 2026-08-29 | [2026-08](./2026-08.md) | 2026-08-29, session 132 — filter sheet rebuilt as a compact bottom sheet of collapsed rows |
| 2026-08-29 | [2026-08](./2026-08.md) | 2026-08-29, session 131 — the Betslip TAB is gone: one persistent betslip bar across every page, opening the slip as a pushed screen |
| 2026-08-29 | [2026-08](./2026-08.md) | 2026-08-29, session 136 — betslip: stale selections are pruned, and the bar hides when nothing resolves |
| 2026-08-28 | [2026-08](./2026-08.md) | 2026-08-28, session 130b — stat-line ruler is now scrollable (global) + NFL non-participants dropped from the boards |
| 2026-08-28 | [2026-08](./2026-08.md) | 2026-08-28, session 130 — betslip resurrected + per-book "Open with" pricing; sportsbook picker sheet; Stats odds sheet with add-to-betslip |
| 2026-08-28 | [2026-08](./2026-08.md) | 2026-08-28, session 129 — best line across all 7 books stamped on every pick; builder pickers replace free text |
| 2026-08-27 | [2026-08](./2026-08.md) | 2026-08-27, session 128 — the NCAAF model search is CLOSED: QB, weather, and line-movement all tested null; the two live rules are the best models |
| 2026-08-27 | [2026-08](./2026-08.md) | 2026-08-27, session 128 — Stats tab: Teams board for every team sport (efficiency + derived betting records |
| 2026-08-26 | [2026-08](./2026-08.md) | 2026-08-26, session 127 — Supabase "Table publicly accessible" advisor email resolved: RLS on the two NFL history tables |
| 2026-08-24 | [2026-08](./2026-08.md) | 2026-08-24, session 126 — "still only seeing Bet with DraftKings": delivery gap diagnosed (OTA never run) + always-visible sportsbook indicator |
| 2026-08-24 | [2026-08](./2026-08.md) | 2026-08-24, session 126c — stakes publish in UNITS, app + Discord |
| 2026-08-24 | [2026-08](./2026-08.md) | 2026-08-24, session 126c — in-app feedback replaces the mailto:, with a reply that comes back into the app |
| 2026-08-24 | [2026-08](./2026-08.md) | 2026-08-24, session 126b — GitHub Actions removed entirely |
| 2026-08-24 | [2026-08](./2026-08.md) | 2026-08-24, session 126 — Discord webhooks: picks routed to per-sport channels |
| 2026-08-24 | [2026-08](./2026-08.md) | 2026-08-24, session 126 — NCAAF verdicts: classifiers dead, margin regression LIVE for spread; totals + moneyline closed |
| 2026-08-24 | [2026-08](./2026-08.md) | 2026-08-24, session 126b — UFC name-variant orphans fixed (15 aliases + anchor-rule fallback |
| 2026-08-24 | [2026-08](./2026-08.md) | 2026-08-24, session 126 — UFC: signals confirmed settling; look-ahead lock question answered + first-signal shadow capture |
| 2026-08-23 | [2026-08](./2026-08.md) | 2026-08-23, session 125 — Stats tab: stat picker condensed to group tabs + one scoped chip row |
| 2026-08-23 | [2026-08](./2026-08.md) | 2026-08-23, session 125 — the selected sportsbook's line + hand-off on EVERY board (UFC / NFL / Live), not just today's board |
| 2026-08-23 | [2026-08](./2026-08.md) | 2026-08-23, session 124 — signal-timing analysis: does the daily pick lock cost us bets? + the "all picks" evaluation rule |
| 2026-08-23 | [2026-08](./2026-08.md) | 2026-08-23, session 124 — Stats tab: sample-size qualifier, hit-rate band, sort control, global "playing today" toggle |
| 2026-08-22 | [2026-08](./2026-08.md) | 2026-08-22, session 122 cont. — subscriptions built DARK: $29.99/$129.99/$199.99 ladder, IAP (RevenueCat) rail chosen over Stripe |
| 2026-08-22 | [2026-08](./2026-08.md) | 2026-08-22, session 123 — Stats tab: denser leaderboard rows + hit/miss dot strips removed |
| 2026-08-22 | [2026-08](./2026-08.md) | 2026-08-22, session 123 — custom model builder: bet types replace "Add model", signal filter removed, EV floor + day-of-week + line-value filters |
| 2026-08-21 | [2026-08](./2026-08.md) | 2026-08-21, session 122 — `mlb_runline` dormancy diagnosed: not paused, unreachable floor; retrain + sweep tooling shipped |
| 2026-08-21 | [2026-08](./2026-08.md) | 2026-08-21, session 122 — authentication built and shipped DARK (Apple / Google / email, feature-flagged off |
| 2026-08-20 | [2026-08](./2026-08.md) | 2026-08-20, session 122 — NCAAF (FBS) Phases 1-3: sport registered, CFBD ingestor, feature engine |
| 2026-08-19 | [2026-08](./2026-08.md) | 2026-08-19, session 121 — NFL day-of context: "Locked on X" + line movement since lock |
| 2026-08-19 | [2026-08](./2026-08.md) | 2026-08-19, session 121 — Stats tab: NFL player leaderboard added (WNBA verified already live |
| 2026-08-19 | [2026-08](./2026-08.md) | 2026-08-19, session 121 — Stats tab: "Tonight" chip in the window strip replaced by a real "Season" window (season hit rates |
| 2026-08-18 | [2026-08](./2026-08.md) | 2026-08-18, session 120 — Odds API quota outage post-mortem: credit telemetry + odds_dk_lines blind-spot fix |
| 2026-08-17 | [2026-08](./2026-08.md) | 2026-08-17, session 119b — the OPENER rule deployed as a second NFL model (`nfl_opener_spread` |
| 2026-08-16 | [2026-08](./2026-08.md) | 2026-08-16, session 119 — NFL wind-card picks published into the app (picks table + mobile NFL toggle |
| 2026-08-15 | [2026-08](./2026-08.md) | 2026-08-15, session 118 — finished games stop showing the LIVE badge |
| 2026-08-15 | [2026-08](./2026-08.md) | 2026-08-15, session 117 — NFL wind card automated on the Railway worker |
| 2026-08-15 | [2026-08](./2026-08.md) | 2026-08-15, session 116 — NFL model system imported as standalone `nfl/` package |
| 2026-08-14 | [2026-08](./2026-08.md) | 2026-08-14, session 116 — staleness sweep fixes: umpires self-heal, WNBA expansion-team injuries via core fallback, UFC phantom-event filter |
| 2026-08-11 | [2026-08](./2026-08.md) | 2026-08-11, session 115 — WNBA results ingest: sports.core.api.espn.com fallback for the site.api 403 block |
| 2026-08-09 | [2026-08](./2026-08.md) | 2026-08-09, session 114 — losing-models reevaluation: IN-PLAY PROP SCORING BUG found + fixed; batter_runs UNPAUSED; RBI exonerated |
| 2026-08-08 | [2026-08](./2026-08.md) | 2026-08-08, session 113 — custom model builder: filter on side, price, game time, confidence, public and injuries + live preview |
| 2026-08-08 | [2026-08](./2026-08.md) | 2026-08-08, session 113 continued — custom models now backtest against EVERY scored pick (the graded universe), not just settled BETs |
| 2026-08-07 | [2026-08](./2026-08.md) | 2026-08-07, session 112 — WNBA finals stopped landing: site.api.espn.com refusing the worker; health check made non-silent |
| 2026-08-02 | [2026-08](./2026-08.md) | 2026-08-02, session 112 — all app filters unified into one shared system |
| 2026-08-02 | [2026-08](./2026-08.md) | 2026-08-02, session 111 — "no live bets showing" diagnosis + Live tab is picks-only |
| 2026-08-01 | [2026-08](./2026-08.md) | 2026-08-01, session 110 — picks show the user's book's line + hand off to that book |
| 2026-08-01 | [2026-08](./2026-08.md) | 2026-08-01, session 109 — Stats tab front page rebuilt to mirror the HOF "Leaders" layout |
| 2026-08-01 | [2026-08](./2026-08.md) | 2026-08-01, session 108 — multi-book lines (US top 5) + user-selectable sportsbook |
| 2026-07-29 | [2026-07](./2026-07.md) | 2026-07-29, session 107 — live score + inning on the pick cards (real in-play feed |
| 2026-07-29 | [2026-07](./2026-07.md) | 2026-07-29, session 106 — WNBA: post-tipoff odds LEAK found + fixed; O/U + spread + rebounds paused |
| 2026-07-22 | [2026-07](./2026-07.md) | 2026-07-22, session 105 — live picks: Track + Bet-on-DraftKings on the Live tab; BET-only Live board |
| 2026-07-22 | [2026-07](./2026-07.md) | 2026-07-22, session 105 — blanket -140 price floor on EVERY MLB + WNBA player prop |
| 2026-07-21 | [2026-07](./2026-07.md) | 2026-07-21, session 104 — in-play live betting loop added to the Railway worker |
| 2026-07-19 | [2026-07](./2026-07.md) | 2026-07-19, session 103 — Railway worker confirmed LIVE; docs synced; GitHub cron audit (nothing left to discontinue |
| 2026-07-19 | [2026-07](./2026-07.md) | 2026-07-19, session 103 — UFC picks never settled: mirror lag vs the fixed 8-day ingest window — FIXED (self-heal + dup-row scoring + unbounded settle |
| 2026-07-19 | [2026-07](./2026-07.md) | 2026-07-19, session 103 — WNBA O/U + spread models LIVE (synthetic-line training); points/threes/PRA retrained + pause CONFIRMED; worker daily-job outage found |
| 2026-07-14 | [2026-07](./2026-07.md) | 2026-07-14, session 103 — mlb_over_under RE-PAUSED + retrain dispatched (summer run-environment drift, live 3-8 |
| 2026-07-12 | [2026-07](./2026-07.md) | 2026-07-12, session 102 — pipeline scheduling moved OFF GitHub Actions to an always-on cloud worker (Actions-minutes overage |
| 2026-07-11 | [2026-07](./2026-07.md) | 2026-07-11, session 101b — O/U record views gated to the honest era (>= 2026-07-05 |
| 2026-07-11 | [2026-07](./2026-07.md) | 2026-07-11, session 101 — mlb_over_under tightened 0.57/0.05 → 0.59/0.07 (fewer picks at plateau ROI |
| 2026-07-11 | [2026-07](./2026-07.md) | 2026-07-11, session 100b — WNBA-only ROI pass: points/threes/PRA PAUSED; everything else confirmed at ROI-max cuts |
| 2026-07-11 | [2026-07](./2026-07.md) | 2026-07-11, session 100 — per-model -140 price floor (MODEL_MIN_ODDS) on pitcher_k / batter_rbi / batter_walks (+ paused batter_runs |
| 2026-07-11 | [2026-07](./2026-07.md) | 2026-07-11, session 99b — WNBA results ingestor outage: is_starter bool→INTEGER fixed + per-date fault tolerance |
| 2026-07-11 | [2026-07](./2026-07.md) | 2026-07-11, session 99 — TestFlight submission failure diagnosed (EAS-side, no repo cause) + self-diagnosing submit step |
| 2026-07-11 | [2026-07](./2026-07.md) | 2026-07-11, session 99 — PAUSED mlb_prop_pitcher_er + mlb_prop_pitcher_walks |
| 2026-07-10 | [2026-07](./2026-07.md) | 2026-07-10, session 98 — daily recap: HR is record-only (stops counting toward the day's record/P&L |
| 2026-07-09 | [2026-07](./2026-07.md) | 2026-07-09, session 97 — WNBA settlement made cloud-native (ESPN results ingestor) + WNBA/NBA finals downgraded to WARN in the health check |
| 2026-07-06 | [2026-07](./2026-07.md) | 2026-07-06, session 96b — "daily pipeline keeps failing": health-check CRIT on phantom non-UFC MMA games — FIXED |
| 2026-07-06 | [2026-07](./2026-07.md) | 2026-07-06, session 96 — props/WNBA "not scoring after the morning run": settlement ran BEFORE game-log ingest — FIXED + 7/5 backlog settled |
| 2026-07-05 | [2026-07](./2026-07.md) | 2026-07-05, session 95b — ROOT CAUSE of the O/U under-lean: live totals/spreads scored with NaN line all season (train/serve skew) — FIXED |
| 2026-07-05 | [2026-07](./2026-07.md) | 2026-07-05, session 95 — HR is record-only on the Models tab |
| 2026-07-04 | [2026-07](./2026-07.md) | 2026-07-04, session 94f — Performance tab: selectable stake sizing for tracked bets ($100 flat \| Kelly \| Custom |
| 2026-07-04 | [2026-07](./2026-07.md) | 2026-07-04, session 94e — Stats tab "Tonight" filter + opponent-strength matchup lines |
| 2026-07-04 | [2026-07](./2026-07.md) | 2026-07-04, session 94d — ML REVERSAL: back to the v20260413 model at 0.72/0.11 (green-2026 mandate |
| 2026-07-04 | [2026-07](./2026-07.md) | 2026-07-04, session 94c — June prop-model outage fixed + HR excluded from public track record |
| 2026-07-04 | [2026-07](./2026-07.md) | 2026-07-04, session 94b — ML + RL retrained on 2026 data; ML re-cut 0.60/0.10; RL model swapped at 0.68/0.11 |
| 2026-07-04 | [2026-07](./2026-07.md) | 2026-07-04, session 94 — O/U retrained on 2026 data, re-cut to 0.57/0.05, UNPAUSED |
| 2026-07-04 | [2026-07](./2026-07.md) | 2026-07-04, session 93 — PR #147 merged + daily system health check + Retrain Model workflow |
| 2026-07-04 | [2026-07](./2026-07.md) | 2026-07-04, session 92 — Track available on every pick until it settles (props + started games |
| 2026-07-03 | [2026-07](./2026-07.md) | 2026-07-03, session 92 — O/U under-drift diagnosis → bullpen ingest fix + temporary mlb_over_under pause |
| 2026-07-03 | [2026-07](./2026-07.md) | 2026-07-03, session 91 — removed the stale "Dropped" signal board (picks lock, they don't flip to AVOID anymore |
| 2026-07-03 | [2026-07](./2026-07.md) | 2026-07-03, session 90 — daily recap: WNBA "missing signals" diagnosis, sport filter chips, pending picks, games-scored list + game-settle self-heal |
| 2026-07-03 | [2026-07](./2026-07.md) | 2026-07-03, session 90 — model detail pick history collapses to the latest day + "See all" expand |
| 2026-07-03 | [2026-07](./2026-07.md) | 2026-07-03, session 89 — "only 3 picks in the record" diagnosis + production OTA workflow |
| 2026-07-03 | [2026-07](./2026-07.md) | 2026-07-03, session 89 — daily recap: every sport always listed |
| 2026-07-02 | [2026-07](./2026-07.md) | 2026-07-02, session 88 — model detail screen: full pick-by-pick history behind the record |
| 2026-07-02 | [2026-07](./2026-07.md) | 2026-07-02, session 88 — Record tab: daily recap fixed (refetch on open) + any-past-day selector + picks list + header overflow fix |
| 2026-07-02 | [2026-07](./2026-07.md) | 2026-07-02, session 87 — ROI audit: runline sign bug in the full-outcome views; runline + WNBA re-cuts |
| 2026-07-01 | [2026-07](./2026-07.md) | 2026-07-01, session 86 — calibration chart: overflow fix + serious-bettor polish |
| 2026-07-01 | [2026-07](./2026-07.md) | 2026-07-01, session 85 — fast betting-line refreshes: hourly 6am–6pm + every 10 min 6pm–11pm |
| 2026-07-01 | [2026-07](./2026-07.md) | 2026-07-01, session 84 — tracked bets score on the Performance tab |
| 2026-06-30 | [2026-06](./2026-06.md) | 2026-06-30, session 83 — "Yesterday's results" recap modal (per-model record + ROI |
| 2026-06-28 | [2026-06](./2026-06.md) | 2026-06-28, session 82 — model reevaluation: full-outcome record view, unpause/retune, HR stake cut |
| 2026-06-27 | [2026-06](./2026-06.md) | 2026-06-27, session 81 — live-signal push (Phase 4, final phase of the notify roadmap |
| 2026-06-27 | [2026-06](./2026-06.md) | 2026-06-27, session 80 — Track-a-bet mobile icon (Phase 3b |
| 2026-06-27 | [2026-06](./2026-06.md) | 2026-06-27, session 79 — Track-a-bet line-change alerts (Phase 3a backend) + Line Movement view (Phase 2 |
| 2026-06-27 | [2026-06](./2026-06.md) | 2026-06-27, session 78 — player props lock at first signal (Phase 1 of the notifications/track-bet roadmap |
| 2026-06-27 | [2026-06](./2026-06.md) | 2026-06-27, session 77 — ML / over-under / all WNBA props threshold sweep |
| 2026-06-26 | [2026-06](./2026-06.md) | 2026-06-26, session 76 — F5 moneyline threshold → 0.67/0.07 (more picks AND higher ROI); runline kept at 0.68/0.09 |
| 2026-06-26 | [2026-06](./2026-06.md) | 2026-06-26, session 75 — lock game-level picks at the first run of the day + strategy analysis |
| 2026-06-26 | [2026-06](./2026-06.md) | 2026-06-26, session 74 — runline threshold CORRECTION: prior "+23.8%" was an outcome sign-bug; full-outcome re-sweep → 0.68/0.08 |
| 2026-06-26 | [2026-06](./2026-06.md) | 2026-06-26, session 73 — competitive UI/UX analysis → 5 merged PRs (filters/cards/nav, Sharp Score, calibration, shareable record, push-notifications backend |
| 2026-06-21 | [2026-06](./2026-06.md) | 2026-06-21, session 72 — NHL TRAINED (moneyline + regulation LIVE) after fixing 4 stacked ingestion bugs; + paused sub-10% MLB models hidden everywhere |
| 2026-06-21 | [2026-06](./2026-06.md) | 2026-06-21, session 71 — Signals tab: persistent "Live \| Dropped" board |
| 2026-06-21 | [2026-06](./2026-06.md) | 2026-06-21, session 70 — easier create/delete of saved parlays |
| 2026-06-21 | [2026-06](./2026-06.md) | 2026-06-21, session 69 — push every MLB model to ≥10% ROI: 7 via cuts, 8 to retrain |
| 2026-06-21 | [2026-06](./2026-06.md) | 2026-06-21, session 68 — MLB full-outcome threshold RE-SWEEP (definitive) + 20-7→11-5 explained |
| 2026-06-21 | [2026-06](./2026-06.md) | 2026-06-21, session 67 — parlay Phase 2.x: basketball team resolution + non-MLB empirical ρ; roadmap item 4 of 4 — DONE |
| 2026-06-21 | [2026-06](./2026-06.md) | 2026-06-21, session 66 — line-shopped parlays; roadmap item 3 of 4 |
| 2026-06-21 | [2026-06](./2026-06.md) | 2026-06-21, session 65 — server-driven action thresholds (config.py edits now need NO mobile rebuild |
| 2026-06-21 | [2026-06](./2026-06.md) | 2026-06-21, session 64 — +EV same-game parlay (SGP) finder; roadmap item 2 of 4 |
| 2026-06-20 | [2026-06](./2026-06.md) | 2026-06-20, session 63 — public parlay track record |
| 2026-06-20 | [2026-06](./2026-06.md) | 2026-06-20, session 62 — parlay correlation engine Phase 2: empirical ρ + team resolution |
| 2026-06-20 | [2026-06](./2026-06.md) | 2026-06-20, session 61 — parlay competitive analysis + correlation-aware parlay engine, Phase 1 |
| 2026-06-20 | [2026-06](./2026-06.md) | 2026-06-20, session 60 — MLB threshold re-opt + retrains + HR odds fix/unpause |
| 2026-06-20 | [2026-06](./2026-06.md) | 2026-06-20, session 59 — start time on all games and props |
| 2026-06-20 | [2026-06](./2026-06.md) | 2026-06-20, session 58 — opening-signal shadow track + line/public movement comparison |
| 2026-06-17 | [2026-06](./2026-06.md) | 2026-06-17, session 56 — NBA added as the 5th sport |
| 2026-06-15 | [2026-06](./2026-06.md) | 2026-06-15, session 55 — GOLF (PGA Tour) added as the 4th sport |
| 2026-06-15 | [2026-06](./2026-06.md) | 2026-06-15, session 54 — live betting Phases 2b–4 implemented, trained, and merged |
| 2026-06-13 | [2026-06](./2026-06.md) | 2026-06-13, session 53 — NHL added (4 models, full pipeline |
| 2026-06-12 | [2026-06](./2026-06.md) | 2026-06-12, session 53 — parlay custom-leg input hidden by keyboard + Stats-tab leg-picking flow |
| 2026-06-12 | [2026-06](./2026-06.md) | 2026-06-12, session 52 — MLB threshold re-optimization + batter_sb v2 retrain, merged into master |
| 2026-06-11 | [2026-06](./2026-06.md) | 2026-06-11, session 51 — Models tab records now reflect current thresholds (mobile |
| 2026-06-11 | [2026-06](./2026-06.md) | 2026-06-11, session 51 — UFC review: look-ahead scoring + upcoming-card display |
| 2026-06-11 | [2026-06](./2026-06.md) | 2026-06-11, session 51 — WNBA prop picks stamped NO_ACTION by the game-level settler ("24 picks · 8-4" Models-tab discrepancy |
| 2026-06-11 | [2026-06](./2026-06.md) | 2026-06-11, session 50 — UFC data source: ufcstats.com Cloudflare-blocked → CSV mirror |
| 2026-06-11 | [2026-06](./2026-06.md) | 2026-06-11, session 50 — UX review: line movement, prop matchup context, model transparency |
| 2026-06-10 | [2026-06](./2026-06.md) | 2026-06-10, session 49 — UFC betting model: full backend + mobile integration |
| 2026-06-10 | [2026-06](./2026-06.md) | 2026-06-10, session 48 — manual parlay builder: select players → Add to play → package together |
| 2026-06-10 | [2026-06](./2026-06.md) | 2026-06-10, session 47 — DraftKings: betslip hand-off + SharpSports account link/bet sync |
| 2026-06-10 | [2026-06](./2026-06.md) | 2026-06-10, session 47 — customer feedback link in app |
| 2026-06-07 | [2026-06](./2026-06.md) | 2026-06-07, session 46 — Stats tab: last-N-games player performance leaderboard |
| 2026-06-07 | [2026-06](./2026-06.md) | 2026-06-07, session 45 — CLV at close on official picks |
| 2026-06-06 | [2026-06](./2026-06.md) | 2026-06-06, session 44 — account for WNBA injuries |
| 2026-06-06 | [2026-06](./2026-06.md) | 2026-06-06, session 43 — Parlay Builder (mobile, new 8th tab |
| 2026-06-06 | [2026-06](./2026-06.md) | 2026-06-06, session 42 — FanDuel added to sportsbook connection (mobile |
| 2026-06-06 | [2026-06](./2026-06.md) | 2026-06-06, session 41 — pipeline schedule: 7am kickoff + hourly 11am–11pm |
| 2026-06-03 | [2026-06](./2026-06.md) | 2026-06-03, session 40 — Stats tab → stat leaderboard browser (MLB + WNBA |
| 2026-06-03 | [2026-06](./2026-06.md) | 2026-06-03, session 39 — fixed WNBA prop scoring (0 picks bug) + Models tab sport separation |
| 2026-06-03 | [2026-06](./2026-06.md) | 2026-06-03, session 38 — re-optimized all MLB thresholds from this season's settled picks |
| 2026-06-03 | [2026-06](./2026-06.md) | 2026-06-03, session 37 — dynamic filter on the Signals screen |
| 2026-06-02 | [2026-06](./2026-06.md) | 2026-06-02, session 36 — removed My Bets / manual bet tracking from mobile |
| 2026-05-31 | [2026-05](./2026-05.md) | 2026-05-31, session 34 — WNBA Phase 4: model training + backtester fixes |
| 2026-05-31 | [2026-05](./2026-05.md) | 2026-05-31, session 35 — WNBA Phase 5: settlement + pipeline wiring + task scheduler |
| 2026-05-31 | [2026-05](./2026-05.md) | 2026-05-31, session 33 — WNBA Phase 3: feature engines |
| 2026-05-31 | [2026-05](./2026-05.md) | 2026-05-31, session 33 — WNBA Phase 2: ingestors + pipeline wiring |
| 2026-05-31 | [2026-05](./2026-05.md) | 2026-05-31, session 33 — WNBA Phase 1: config + schema + separate UI |
| 2026-05-30 | [2026-05](./2026-05.md) | 2026-05-30, session 33 — public betting coverage (BAB-58 |
| 2026-05-25 | [2026-05](./2026-05.md) | 2026-05-25, session 32 — Phase 2a: PBP ingest + plays schema |
| 2026-05-25 | [2026-05](./2026-05.md) | 2026-05-25, session 31 — Phase 1 of live (in-play) betting |
| 2026-05-25 | [2026-05](./2026-05.md) | 2026-05-25, session 30 — editable stakes, My Bets tab, adjustable Kelly |
| 2026-05-25 | [2026-05](./2026-05.md) | 2026-05-25, session 29 — hourly pipeline schedule + mobile UI note |
| 2026-05-24 | [2026-05](./2026-05.md) | 2026-05-24, session 28 — season stats views for website |
| 2026-05-20 | [2026-05](./2026-05.md) | 2026-05-20, session 27 — RLS on player_handedness |
| 2026-05-17 | [2026-05](./2026-05.md) | 2026-05-17, session 26 — HR picks fire without DK odds |
| 2026-05-16 | [2026-05](./2026-05.md) | 2026-05-16, session 25 — HR picks now prob-only |
| 2026-05-14 | [2026-05](./2026-05.md) | 2026-05-14, session 24 — pitcher K model v2 retrain complete |
| 2026-05-13 | [2026-05](./2026-05.md) | 2026-05-13, session 23 — umpire ingestor + pitcher player_id fix |
| 2026-05-13 | [2026-05](./2026-05.md) | 2026-05-13, session 22 — prop pick settlement complete |
| 2026-05-13 | [2026-05](./2026-05.md) | 2026-05-13, session 21 — remaining batter props trained, all 11 prop models complete |
| 2026-05-13 | [2026-05](./2026-05.md) | 2026-05-13, session 20 — pitcher hits/ER/outs/walks trained |
| 2026-05-13 | [2026-05](./2026-05.md) | 2026-05-13, session 19 — mlb_prop_batter_hr v2 enabled |
| 2026-05-13 | [2026-05](./2026-05.md) | 2026-05-13, session 18b — Supabase RLS critical fix |
| 2026-05-12 | [2026-05](./2026-05.md) | 2026-05-12, session 18 — batter prop models trained + scorer wired |
| 2026-05-12 | [2026-05](./2026-05.md) | 2026-05-12, session 17 — F5 ML v3 retrain + threshold reduction |
| 2026-05-12 | [2026-05](./2026-05.md) | 2026-05-12, session 16 — lineup ingestor + NONE signal rows for website |
| 2026-05-10 | [2026-05](./2026-05.md) | 2026-05-10, session 15 — pitcher K prop pipeline complete + F5 O/U and RL disabled |
| 2026-05-09 | [2026-05](./2026-05.md) | 2026-05-09, session 14 — F5 live odds + 11am schedule |
| 2026-05-08 | [2026-05](./2026-05.md) | 2026-05-08, session 15 |
| 2026-05-08 | [2026-05](./2026-05.md) | 2026-05-08, session 14 |
| 2026-05-08 | [2026-05](./2026-05.md) | 2026-05-08, session 13 |
| 2026-05-04 | [2026-05](./2026-05.md) | 2026-05-04, session 12 |
| 2026-05-03 | [2026-05](./2026-05.md) | 2026-05-03, session 11 |
| 2026-04-23 | [2026-04](./2026-04.md) | 2026-04-23, session 10 |
| 2026-04-14 | [2026-04](./2026-04.md) | 2026-04-14, session 9 |
| 2026-04-14 | [2026-04](./2026-04.md) | 2026-04-14, session 8 |
| 2026-04-12 | [2026-04](./2026-04.md) | 2026-04-12 |
| 2026-04-11 | [2026-04](./2026-04.md) | 2026-04-11 |
| 2026-04-05 | [2026-04](./2026-04.md) | 2026-04-05 |
| 2026-04-01 | [2026-04](./2026-04.md) | 2026-04-01, continued |
| 2026-04-01 | [2026-04](./2026-04.md) | 2026-04-01, morning |
| 2026-03-31 | [2026-03](./2026-03.md) | 2026-03-31 |
