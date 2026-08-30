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
