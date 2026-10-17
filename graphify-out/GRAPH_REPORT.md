# Graph Report - bm-nba-total-luck  (2026-10-17)

## Corpus Check
- Large corpus: 1492 files · ~2,454,177 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 28984 nodes · 68850 edges · 891 communities (686 shown, 205 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 1746 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6b9c7083`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Injury report ingestion with WNBA fallback
- Mobile stats board
- App settings, feedback and push setup
- Live monitor API probe
- NBA injury report ingest tests
- tests/test_nfl_live_leader_gameday.py
- nfl_live_leader/gameday.py
- tests/test_calibration_promotion.py
- tests/test_score_off_any_book_line.py
- NCAAF FBS team registry tests
- Mobile pick filters and sorting
- tests/test_ncaaf_alias_scores.py
- Prop alternate line parsing tests
- NBA injury report pulls and retries
- tests/test_backtester.py
- Weather lookahead and NHL league helpers
- nfl/live_model/feeds/odds_live.py
- NHL props newest quote shopping
- NBA prop market lab
- Discord pick notifier tests
- nfl/live_model/tests/test_backup_snaps.py
- mobile/scripts: verify_book_links + verify_betslip_combine
- NBA official injury report ingest
- College football features and FBS list
- mobile/scripts/verify_contrast_tokens.ts
- models/nhl_props.py
- tests/test_health_pregame_prices_current.py
- Pick lock after settlement tests
- NBA game line move study
- NBA prop rule model and card
- tests/test_mlb_game_market.py
- Threshold review job
- Idle read transaction tests
- UFC phantom fight filter
- tests/test_prop_box_scores.py
- NBA game model prop feature tests
- Worker job queue claim and run
- NBA prop market card
- Database schema guard and brand avatar
- College football ratings feature tests
- tests/test_nfl_opener.py
- NHL stats, game logs and odds archive
- NBA game model luck feature tests
- CLV math and devig functions
- NHL derivative totals card tests
- tests/test_publisher_lock.py
- tests/test_credit_budget.py
- NBA prop market publish tests
- App custom model filters and sliders
- Player news ingest
- NFL wind and opener publisher
- Settlement self-healing tests
- NHL prop card publishing
- tests/test_first_signal_repair.py
- tests/test_ungraded_model_performance.py
- mobile/scripts/verify_push.ts
- Prop price pregame cutoff tests
- Mobile markets and formatting
- tests/test_nhl_asof.py
- Trainer, features and shared setup
- NFL in-play game state feed
- data/ingestors/nfl_inplay_history.py
- App thresholds and daily results
- App bankroll card
- App theme, links and parlay screen
- Prop trainer and WNBA rebuilds
- NCAAF in-play engine and pick lock
- NBA prop projection model and card
- tests/test_db_reconnect.py
- In-play pick lock tests
- tests/test_refresh_retry.py
- NBA results and lineup segments store
- NBA results ingestor tests
- NBA public betting splits ingestor tests
- NBA game projection search lab
- tests/test_local_cache_is_additive.py
- tests/test_calibration_check_coverage.py
- tests/test_book_team_map.py
- tests/test_team_board_cache.py
- NHL blocked shots prop model
- nfl/live_model/tests/test_rush_attempt_pace.py
- tests/test_nfl_poll_fast_silence.py
- NHL moneyline rebuild labs
- Umpire step on every refresh pass
- tests/test_nhl_asof.py
- tests/test_dk_freshness_parse.py
- NBA historical odds gap backfill
- models: slate_concentration + test_slate_concentration
- College football in-play history pull
- View migration lock handling tests
- Prop odds missing game tests
- NCAAF in-play history backtest
- College football model search and validation
- Deploy checks and worker job queue
- MLB twin game merge
- Mobile teams board and team detail
- Best line threshold sweep
- NFL weather fetch for edge studies
- NCAAF college data ingest tests
- Mobile betslip and parlay legs
- NHL starting goalie lookup tests
- tests/test_prop_odds_utc_stamp.py
- Live monitor server
- NFL publisher lookahead and key tests
- tests/test_feature_artifact_agreement.py
- NFL prop market one side per line
- CLV graded at the price taken
- tests/test_cloud_retrain_artifacts.py
- Live game poller no-op connection
- System health and published record checks
- tests/test_nfl_opener.py
- NFL prop data parsing tests
- Discord pick posting and restates
- tests/test_nfl_wind_publisher.py
- Odds feed fetching and quota tracking
- NFL live prop model tests
- tests/test_health_reason_and_cadence.py
- tests/test_live_publish_parity.py
- tests/test_nfl_weather_supabase_readback.py
- NBA game projection world and models
- Pregame line poller change tests
- Pitcher stats as-of invariant tests
- NHL props card slate tests
- Pipeline log reason tests
- Stats and prop data ingest
- NCAAF in-play score distribution pricing
- tests/test_nfl_scored_rows.py
- Signal delivery health tests
- X results job and cursor wrapper tests
- NHL totals rule model and card
- nfl/live_model/feeds: test_feed_resilience + espn
- NFL opener card rows
- NHL prop backtest and EV lab
- In-play score change guard
- NFL prop rule with Kalshi tests
- tests/test_live_pick_features.py
- Fight board test connection
- tests/test_prop_missing_features.py
- App sport filter and push routing
- Injury fetch and prop odds test fakes
- NBA prop closing line tests
- NFL in-play pick writer
- NFL wind scored row building
- NHL moneyline anchored model
- NCAAF CFBD ingestor tests
- Walk-forward evaluation tests
- NCAAF live state recording tests
- tests/test_run_ledger_orphans.py
- MLB play-by-play twin game lookup
- NBA lineup stints from play-by-play
- UFC stats ingest
- Team stats rebuild and as-of checks
- In-play calibrated decision tests
- NFL DraftKings line snapshots
- Feature engine returnee and odds tests
- tests/test_heartbeat_disabled_jobs.py
- NBA game projection family cells
- Scorer any-book game line fallback
- tests/test_repair_bogus_first_pitch_labels.py
- nfl/live_model/tests/test_executor.py
- Odds pruning and sharp book retention
- tests/test_sbr_loader.py
- mobile/scripts/ux_scan.mts
- NFL prop stat distributions
- Pre-game scoring and best-price decisions
- NBA game projection availability state
- mobile/src/lib/otaUpdate.ts
- tests/test_live_quote_staleness.py
- Best game price selection tests
- Player name matching
- NHL opening night season labels
- NBA prop settlement stats tests
- Pipeline report with per-section rollback
- supabase/functions/_shared/discord.ts
- Worker job queue validation tests
- NFL in-play prop settlement tests
- NHL prop model wiring tests
- NBA totals card ledger and label tests
- scripts: build_nfl_live_leader_artifact + model
- NFL CLV backtest and feature build
- tests/test_discord_channel_probe.py
- tests/test_nfl_prop_one_read_per_game.py
- Game outcome target tests
- Worker job queue and record corrections
- Discord recap restatement
- App sign-in, billing and paywall
- Multi-book odds and pruning
- NFL prop features and regrades
- tests/test_model_game_savepoint.py
- tests/test_calibration_watch.py
- tests/test_promote_external.py
- Closing-line backfill job tests
- Batter prop log lookback tests
- Failure alerter fake-connection tests
- NFL pick monitor join tests
- Health skip budget streak tests
- Score when lines open tests
- tests/test_sbr_loader.py
- NBA prop window plan tests
- App screens and model catalog
- NFL prop market and local cache reads
- Price prefilter rollback tests
- MLB in-play state alignment
- Prop alternate line fetch tests
- tests/test_nhl_three_way_lookahead.py
- NFL in-play gameday worker
- Injury flag tests
- Prop odds next-day lookahead
- Run ledger health tests
- NHL blocked shots settlement shim
- Pipeline watch job
- Weather forecast hour lookup
- tests/test_best_line_live.py
- App bankroll storage
- tests/test_sbr_loader.py
- NFL wind card book filter tests
- Prop rows until tip and lab spies
- Injury adjustment scenario tests
- NFL prop settlement tests
- NFL prop local odds cache tests
- tests/test_void_picks.py
- tests/test_sbr_loader.py
- Odds credit budget
- NCAAF starter-out search dataset
- NHL prop card limits and insert-once
- College football game-day feeds
- NFL prop odds ingest and backfill
- Scorer BET and AVOID signal tests
- tests/test_system_health_checks.py
- tests/test_sbr_loader.py
- tests/test_daily_retry.py
- Prop no-bet rows kept to tip-off
- NFL prop market card publisher
- Feature map tests
- Pass completion health tests
- tests/test_live_book_move_guard.py
- NCAAF in-play underdog calibration
- tests/test_nfl_props.py
- tests/test_weekly_catch_up.py
- tests/test_sbr_loader.py
- MLB umpire ingestor
- Discord live and best-price fields
- Prop odds book update-time tests
- NFL pick monitor
- Multi-book odds fetch fallback tests
- tests/test_nhl_props.py
- NFL live prop assessment and odds client
- DraftKings direct feed matching
- Starter-out flag tests
- NBA box score player resolver
- App queries for today's picks
- College football state fetch tests
- supabase/functions/revenuecat-webhook/index.ts
- supabase/functions/whop-webhook/index.ts
- tests/test_nfl_props.py
- Health check database shim tests
- tests/test_sbr_loader.py
- NHL as-of feature leak tests
- NFL in-play pricing engine and backtest
- Stale pre-game price tests
- Prop grading timeout tests
- Settlement self-heal test shim
- App bankroll unit percent hook
- tests/test_nfl_props.py
- tests/test_nhl_three_way_lookahead.py
- NHL returning starter name lookup
- Pre-game price age for fights
- Model calibration sweep tests
- Model quality database end-to-end test
- Batter prop log load tests
- Opponent starter feature test stubs
- Signal publish-on-write tests
- NFL prop grading and kickoff gate
- tests/test_game_market_gate.py
- NFL prop pull market list tests
- NBA public splits quality backfill
- MLB bet record audit tally
- Fight orientation best-line tests
- NFL prop odds loader tests
- NBA second-model prop study
- tests/test_score_when_lines_open.py
- tests/test_score_when_lines_open.py
- tests/test_score_when_lines_open.py
- tests/test_system_health_checks.py
- Paused bet bankroll tests
- tests/test_pick_integrity.py
- NFL prop price math tests
- NBA injury report date scope
- Threshold review table setup tests
- Database calls from tracking and scoring
- tests/test_record_one_pick_per_event.py
- NFL backup snapshot test cursor
- Live pre-game total line tests
- NBA prop market settlement fake
- Dropped game scoring tests
- nfl/live_model/tests: test_props + props
- Database setup and schema split
- NFL prop odds game matching
- Feature value encoding tests
- WNBA prop rule fake connection
- Push-adjusted win probability
- tests/test_wnba_prop_market.py
- tests/test_nfl_scored_rows.py
- NHL period and team totals model
- App player stats and opponent splits
- Global EV floor tests
- tests/test_nhl_props.py
- Publish key identity and push alerts
- NFL prop backtest and placebo
- NFL wind forecast and lead
- tests/test_recap_retries_a_skipped_day.py
- NBA odds archive rerun safety
- NFL wind publisher lock tests
- Picks email rendering
- NCAAF feature engine test database
- NFL game line study output tee
- NBA results ingest test connection
- Prop no-bet poller tests
- Health check step counting tests
- Pregame poller game creation
- Stale quote line shopping test
- Database schema shape tests
- Umpire feature retirement tests
- Probability calibration fitting tests
- App matchup grades and stats pills
- App book prices and closing-line labels
- NBA game residual distribution
- NFL evaluation rows carry the line
- tests/test_ncaaf_prop_odds.py
- MLB totals public fade tests
- NFL prop verdict tests
- tests/test_ncaaf_pbp_store.py
- tests/test_heartbeat_watchdog.py
- Game injury veto gate and tests
- Pipeline run ledger
- scripts/nfl_edge_live_rush_pace.py
- NBA prop projection tests
- Live monitor probe and store
- NBA game market feature study
- tests/test_prop_calibrated_decision.py
- NCAAF in-play quote serving
- Schema guard and table lock-down
- NFL prop information and stacking studies
- tests/test_mobile_line_movement.py
- tests/test_live_calibration.py
- NFL in-play flow validation tests
- NBA lineup stint derivation tests
- tests/test_ncaaf_live_notify.py
- monitoring/store.py
- tests/test_settled_record_is_immutable.py
- features/golf_feature_engine.py
- ncaaf_live/tests/test_states.py
- tests/test_bovada_feed.py
- tests/test_market_movement.py
- NCAAF cross-book opener rule tests
- tests/test_paused_keeps_real_verdict.py
- NFL in-play edge studies by season
- scripts/nfl_edge_extreme_props.py
- scripts/nfl_edge_settlement.py
- NBA totals overs rule tests
- X publisher
- tests/test_agents_contract.py
- In-play scorer and inning gate replay
- Best line and best-price decision tests
- WNBA results and stats ingestors
- Daily pipeline runner and push notifier
- Prop box score backfill
- scripts/nfl_preflight.py
- Push notifier and delivery tickets
- NFL expected value stake engine
- NFL quarterback wind edge study
- tests/test_decide_on_calibrated.py
- tests/test_dk_direct_feed.py
- NBA prop projection lab
- NBA totals overs shooting luck model
- tests/test_model_artifacts_load.py
- scripts/game_line_market_sweep.py
- Push notification deep link tests
- tests/test_pass_instrumentation.py
- tests/test_db_adapt_sql.py
- Sharp-price de-vig helpers
- NFL in-play 2025 edge report
- tests/test_mobile_contrast_tokens.py
- NBA box score stats ingestor
- Threshold and EV floor sweeps
- Live monitor cache
- NBA second game line move tests
- NBA shooting luck and motivation lab
- Shared database connection and sweeps
- NBA play-by-play game matching tests
- WNBA stats and results ingestion
- Health check skip budget tests
- NBA public betting splits ingestor
- Picks unique row tests
- tests/test_nfl_live_leader_state.py
- tests/test_ncaaf_qb_ingestor.py
- Discord price bound tests
- NBA derivative market lab
- Mobile pick category tests
- NCAAF feature engine tests
- House juice price floor tests
- tests/test_ncaaf_game_identity.py
- NBA second game market tests
- Position versus opponent tests
- MLB and WNBA stats ingestors and pitcher rebuild
- NBA game search grading harness
- NBA totals overs card
- College football search features
- tests/test_live_game_features.py
- tests/test_ncaaf_totals_regression.py
- UFC feature engine and tests
- App script tests run through node
- tests/test_ncaaf_qb_features.py
- NFL in-play prop flow calibration
- Line CLV sign and orientation tests
- Mobile screen source wiring tests
- NBA game harness tests
- MLB live game state trigger tests
- Fight board price age tests
- NFL in-play line churn study
- Kalshi prop ingest
- Model calibration check tests
- NBA ESPN box score parsing
- NCAAF college data ingestor
- NBA second game model verdict
- Historical odds backfill and in-play marking
- NCAAF player stats parser tests
- In-play inning gate replay tests
- scripts/nfl_live_prop_feasibility.py
- tests/test_context_budget.py
- tests/test_player_h2h_stat_values_migration.py
- tests/test_retired_models.py
- NBA game projection test fixtures
- NBA prop model lab and verification
- NFL weather cache import
- Latest line state trigger tests
- tests/test_live_record_start_views.py
- Model quality volume spike checks
- NBA prop window scheduling tests
- NBA rest and schedule features
- NFL Kalshi edge search
- nfl/models/opener_spread.py
- Live game state poller and slate dates
- tests/test_nfl_wind_fire_window.py
- tests/test_public_betting_ingestor.py
- tests/test_service_role_split.py
- Kalshi prop ladders and game markets
- tests/test_http_timeout_floor.py
- Model quality public fade tests
- NFL edge research data cache
- Paused model assessment script
- NBA second game projection tests
- Slate concentration and fade risk detection
- NHL prop odds alternate line tests
- Ops alert watchdogs
- Kalshi game market recorder
- Odds pruning keeps openers
- UFC fighter name resolution
- NFL in-play lag book grading
- Refresh pass step ordering tests
- NBA historical odds archive parser
- Sharp book odds retention in pruning
- Mobile tracked performance checks
- tests/test_mobile_threshold_parity.py
- NHL derivative odds job validation tests
- tests/test_track_record_views.py
- tests/test_weekly_catch_up.py
- Injury fetch cache speed tests
- MLB public fade top-K holdout
- NFL live leader model tests
- NFL edge search helpers
- Mobile paused catalog tests
- App bankroll field and unit rows
- NBA totals overs replay of the lab
- MLB play-by-play ingestor
- tests/test_promote_calibration_job.py
- tests/test_cfbd_snapshot_leakage.py
- Rule model market mapping tests
- NCAAF outcome edge scan
- tests/test_nfl_prop_thresholds.py
- tests/test_nhl_research_job.py
- tests/test_settlement_timing.py
- App and server closing value parity
- Per-model threshold config tests
- App accessibility checks
- DataGolf ingestor and NHL SBR archive
- NFL odds cache import to Supabase
- tests/test_health_check_observe.py
- NHL box score ingest
- NFL 2026 opener and wind tracker
- NFL edge luck and weather studies
- NFL prop shape simulation
- tests/test_pick_lock_is_on_picks.py
- NCAAF board visibility tests
- NBA box score enrichment
- Env file fallback reader
- College football margin cover tests
- ESPN and DraftKings live freshness
- Database address checker
- tests/test_opp_starter_features.py
- MLB in-play history pull
- supabase/functions/discord-link/index.ts
- tests/test_nfl_prop_clv.py
- tests/test_prune_keeps_the_close.py
- tests/test_scoring_methods.py
- NBA game projection lab runs
- NBA game projection world build
- NFL ESPN injury ingest tests
- Anonymous read access lockdown
- NFL 2026 opener and wind tracking
- College football game-day cadence tests
- nfl/scripts/backtest_opener.py
- NFL stale card file cleanup
- tests/test_latest_odds_views.py
- scripts/nfl_edge_gameline_rules.py
- NBA schedule ingestor and tests
- tests/test_nfl_prop_settle_name_fallback.py
- Recap waits for NFL box scores
- NFL backfill retry tests
- tests/test_transaction_pooler.py
- NBA historical odds archive parsing
- MLB totals retrain sweep job tests
- Mobile sport filter persistence tests
- Trainer no-register mode tests
- NBA game projection player availability
- NHL prop labs
- supabase/functions/sharpsports/index.ts
- NFL model import path tests
- NBA second game grid verdict tests
- tests/test_worker_deps.py
- College football totals lead study
- scheduler.py
- tests/test_mobile_stat_labels_match_the_server.py
- tests/test_ncaaf_fcs_visitor_names_migration.py
- tests/test_nfl_prop_unstarted_clear.py
- NBA game model lab and NFL staking
- tests/test_savant_freshness.py
- tests/test_scorer_nfl_prop_like_escape.py
- NBA injury report time slots
- Threshold SQL and EV floor notes
- SQL escaping and closing-line source tests
- Paused and no-signal pick rows
- College football starter-out study
- NFL prop lean concentration study
- Dashboard rule model display tests
- tests/test_clear_unauthorized_auto_pauses_migration.py
- Declared worker job validation tests
- tests/test_ncaaf_se_louisiana_alias_migration.py
- NCAAF quarterback ablation study
- tests/test_overnight_polling.py
- College football loop timing tests
- NFL Kalshi price history fetch
- College football live underdog correction
- NCAAF situational spot search
- tests/test_claude_rules_split.py
- NBA line move fit helpers
- tests/test_dedupe_opening_signals.py
- Live model holdout side-by-side comparison
- tests/test_pbp_backfill_resilience.py
- College football line move spots
- College football quarterback features
- Live game discovery across dates
- NFL prop tick window tests
- Live money record-only guard tests
- NFL prop book sweep
- NHL regulation own probability tests
- NBA public splits pipeline step
- tests/test_prompt_reads_thresholds.py
- NFL prop pulled quote filter
- NBA quarter scores parser
- scripts/render_brand_icons.py
- NFL wind stake sizing tests
- supabase/functions/stripe-webhook/index.ts
- tests/test_drop_voided_nfl_wind_opening_signals_migration.py
- NHL prop alternate line calls
- tests/test_mobile_neutral_signal_label.py
- College football CFBD game parsing
- tests/test_scorer_commits_per_game.py
- NCAAF scoreboard yardline parsing tests
- College football totals weather study
- Database setup column tests
- College football stats ingestion
- tests: test_wnba_availability + wnba_availability
- Retrain job validation
- Live cut sweep decision tests
- NFL prop universe summary tests
- supabase/functions/sharpsports-webhook: index + index
- NHL backtest player namesakes
- NHL artifact grading and underdog grid
- supabase/functions/stripe-checkout/index.ts
- tests/test_book_list_budget.py
- Live orchestrator trigger tests
- API call daily rollup
- NBA game market search lab
- NBA game search cell emission tests
- SBR odds CSV loader
- NHL probable goalie parsing
- NCAAF steam lag study
- mobile/scripts/verify_a11y.ts
- Football in-play game state
- NBA projection publish lock tests
- NBA prop fetch scope tests
- MLB live state extraction
- Model quality CLV and ROI alerts
- College football feed outage tests
- tests/test_demote_ncaaf_over_under_platt.py
- MLB runline retrain sweep job
- tests/test_discord_post_one_pick_migration.py
- tests/test_game_scorer_spares_nfl_props.py
- NBA projection settlement tests
- tests/test_mobile_ota_self_update.py
- NFL in-play flow model tests
- Health check cadence reading
- NFL prop parameters match artifacts
- NHL game parsing tests
- College football consensus gate study
- Revoke remaining write grants tests
- Published record units
- Scorer keeps off-DraftKings priced bets tests
- Drop voided NFL prop signals tests
- NFL prop scorer kickoff ceiling
- NCAAF structural spot scan
- Every named sportsbook is fetched
- Weather game hour helpers
- WNBA feature assembly
- NFL tackles total target
- tests/test_weekly_catch_up.py
- Mobile stats filter checks
- NHL goalie line helpers
- Registered but not firing models tests
- Team board start time bound tests
- tests/test_live_orchestrator.py
- NFL standings and division flags
- NBA game search cache checks
- NFL in-play lag summaries
- NFL prop publish without a game row
- Mobile accessibility verify script
- Market handicap feature tests
- mobile/scripts/verify_a11y.ts
- mobile/scripts/verify_a11y.ts
- NFL research backup
- Prop CLV and SQL escaping tests
- mobile/scripts/verify_a11y.ts
- College football margin evaluation
- NCAAF game feature assembly
- ncaaf_live/tests/test_serve.py
- NBA projection late game pull tests
- Mobile script test runner via Node
- Health check lateness wording
- Mobile NHL look-ahead window tests
- NBA prop decisions ledger test
- Pitcher groundball rate feature
- scripts/nfl_edge_preregistered_2026.py
- College football data call budget
- Insert column alignment test
- Health skip budget source checks
- NHL prop rejected alternate call test
- College football registry test database
- College football kickoff parsing guard
- tests: test_player_positions + player_positions_ingestor
- College football archived line books
- NBA play clock and shot parsing
- College football odds cadence test
- College football naive kickoff time test
- Pending feature live list guard
- NBA prop market decision tests
- Home run model starter feature test
- NBA SBR archive moneyline timing
- mobile/scripts/verify_a11y.ts
- Pre-game line poller
- NBA play-by-play ingestor
- App live segment wiring tests
- Supabase schema tables
- mobile/app.json
- mobile/package.json
- Games and latest odds views
- Player game log RPCs
- Picks and public track record views
- Latest line state tables
- mobile/tsconfig.json
- Discord link and Whop memberships
- Feedback threads migration
- NFL prop modeling tables
- railway.json
- NHL game logs migration
- Team stats board tables
- Decide on best price migration
- Mobile app build scripts
- Disk IO indexes migration
- Live game state tables
- NHL moneyline rebuild write-up
- NCAAF player stats leaderboard
- Scored pick outcomes lateral fix
- NBA models research record
- NCAAF tables migration
- nfl/scripts/live_prop_job.sh
- NFL player stats leaderboard
- .claude/settings.json
- NBA player game log RPCs
- scripts/refresh_pass.sh
- Player news migration
- Kalshi game markets migration
- Kalshi prop ladders migration
- NCAAF QB game migration
- Opening signals shadow track
- Custom model backtest RPCs
- NFL live model tables
- API call log migration
- Model quality checks migration
- NCAAF plays migration
- Parlay track record migration
- Pipeline runs table
- Push notifications migration
- Results snapshots migration
- Team stats board cache
- Discord one pick per publish
- Discord void notice views
- Materialize scored pick outcomes
- Track record reads graded matview
- Game market gate migration
- Kalshi NCAAF events migration
- NCAAF live states migration
- NCAAF venues migration
- NFL odds history pulls migration
- NFL research data backup
- NFL stadium weather hourly
- NHL period scores migration
- Player positions migration
- NFL player season stat values
- System health checks migration
- Live pick features table
- Picks one row per pick index
- Picks open non-bet index
- Published picks record backfill
- Recompute snapshot units
- Mobile development dependencies
- Game weather issued migration
- Odds API quota migration
- Parlay correlations migration
- Pick placement checks migration
- NBA play-by-play lineup docs
- docs/rules_evidence.md
- Calibration and NFL opener-wind docs
- NFL game lines model write-up
- nfl/live_model/README.md
- docs: followups + clv
- docs: best_line + config_topology
- docs/history: learnings + build_state
- monitoring/static/dashboard.html
- NFL live prop lean notes
- docs/sports/nhl.md
- docs: mlb_market_handicap_features + mlb_game_market_gate
- docs/sports/ncaaf.md
- Cloud worker and local ops docs
- docs/discord.md
- docs/team_stats_leak.md
- Live total and search protocol notes
- docs/sports/nfl.md
- mobile: TESTFLIGHT + README
- supabase/functions/README.md
- NCAAF in-play model docs
- .claude/rules/analysis-and-thresholds.md
- .claude/rules/data-integrity.md
- docs/sports/mlb.md
- docs/thresholds.md
- NFL game lines and wind totals docs
- .claude/rules: CLAUDE + config-topology
- .github/workflows: CLAUDE + mobile-build
- docs/agents_contract.md
- .claude/rules/operations.md
- docs/live_odds_freshness.md
- mobile/docs/UX_REVIEW.md
- MLB model quality and totals notes
- docs/sports: ufc + golf
- mobile/docs/BILLING.md
- .claude/agents: frontend-ux-designer + CLAUDE
- .claude/rules/picks-and-publishing.md
- .claude/rules/model-updates.md
- docs/signal_timing.md
- mobile/docs/DISCORD_LINKING.md
- docs/live_betting.md
- NFL model bundle restore docs
- docs/sports/wnba.md
- mobile/docs/AUTHENTICATION.md
- Model state and volume assessments
- NFL prop and college research notes
- .claude/rules/frontend.md
- docs/health_checks.md
- docs/retrain_2026_plan.md
- Live monitor and record view notes
- docs/reviews/2026-09-07-nfl-props-deep-dive.md
- docs/market_coverage.md
- (root): pr-ci + requirements
- docs/nfl_props_model.md
- NFL wind totals runbook and staking
- Game model injury gate notes
- mobile/docs/BILLING.md
- docs/testing.md
- CLAUDE.md
- docs: nhl_market_lab + nhl_clv_ev_assessment
- App privacy policy
- NFL opener sharp-vs-soft findings

## God Nodes (most connected - your core abstractions)
1. `get_connection()` - 610 edges
2. `DBConnection` - 309 edges
3. `react` - 139 edges
4. `StatsScreen()` - 136 edges
5. `react-native` - 98 edges
6. `colors` - 84 edges
7. `font` - 78 edges
8. `norm_player_name()` - 75 edges
9. `PlayerStatsScreen()` - 75 edges
10. `radii` - 75 edges

## Surprising Connections (you probably didn't know these)
- `Forward capture (2026-27)` --references--> `run_forward()`  [INFERRED]
  docs/nba_public_splits.md → data/ingestors/nba_public_splits_ingestor.py
- `2. Data used (all in Supabase)` --references--> `odds()`  [INFERRED]
  docs/nba_models_2026.md → tests/test_latest_line_state.py
- `3. The market grid` --references--> `odds()`  [INFERRED]
  docs/nba_models_2026.md → tests/test_latest_line_state.py
- `Things a reader should know` --references--> `shot_value()`  [INFERRED]
  docs/nba_pbp_stints.md → data/ingestors/nba_stints.py
- `4.3 Player props — one rule ships` --references--> `run_nba_prop_window()`  [INFERRED]
  docs/nba_models_2026.md → scheduler.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **The three-layer repair that produced the 2026-09-08 mlb_live_total_runs artifact** — docs_mlb_volume_efficiency_pregame_total_line_anchor, docs_mlb_volume_efficiency_grouped_time_ordered_cv, docs_mlb_volume_efficiency_nb1_dispersion_tail, docs_mlb_volume_efficiency_mlb_live_total_runs [EXTRACTED 1.00]
- **The five model-quality checks form the daily monitor** — docs_model_quality_slate_concentration_check, docs_model_quality_public_fade_risk_check, docs_model_quality_clv_degradation_check, docs_model_quality_roi_collapse_check, docs_model_quality_volume_spike_check, docs_model_quality_model_quality_monitor [EXTRACTED 1.00]
- **The market-relative NFL prop rule and its validation** — docs_nfl_props_model_nfl_prop_market, docs_nfl_props_model_pinnacle_reference, docs_nfl_props_model_betonlineag_second_reference, docs_nfl_props_model_placebo_test, docs_nfl_props_model_threshold_fragile_strategy_robust, docs_nfl_props_model_polling_cadence_t24_t3, docs_prop_market_research_kalshi_or_reference [EXTRACTED 1.00]
- **NHL unders prop models and the margin-on-the-over structure** — docs_nhl_market_lab_over_margin_structure, docs_nhl_market_lab_nhl_prop_blocked_shots, docs_nhl_market_lab_nhl_prop_saves, docs_nhl_market_lab_nhl_prop_shots_on_goal, docs_nhl_market_lab_nhl_prop_assists, docs_nhl_market_lab_nhl_props_engine, docs_nhl_clv_ev_assessment_four_bets_a_night [EXTRACTED 1.00]
- **One board: app, Discord, push and health all cut picks on model_action_thresholds** — docs_discord_one_board, docs_discord_publish_filters_live_parity, docs_discord_discord_producers, docs_config_topology_threshold_sync, docs_health_checks_pipeline_observability_checks, docs_followups_scorer_corrected_vs_publishers_model_prob [EXTRACTED 1.00]
- **One membership, two surfaces: AUTH_ENABLED -> billing -> Discord link -> my_access()** — mobile_docs_authentication_auth_enabled, mobile_docs_billing_billingready, mobile_docs_discord_linking_discordlinkready, mobile_docs_billing_revenuecat_webhook, mobile_docs_discord_linking_discord_link, mobile_docs_discord_linking_whop_webhook, mobile_docs_discord_linking_shared_entitlement_ts, mobile_docs_discord_linking_my_access, mobile_docs_discord_linking_useentitlement, supabase_functions_readme_verify_jwt [EXTRACTED 1.00]
- **Path-scoped rule files that load beside the code they govern** — _claude_rules_analysis_and_thresholds_rule_file, _claude_rules_config_topology_rule_file, _claude_rules_data_integrity_rule_file, _claude_rules_frontend_rule_file, _claude_rules_model_updates_rule_file, _claude_rules_operations_rule_file, _claude_rules_picks_and_publishing_rule_file, claude_rule_placement_decision, _claude_rules_config_topology_path_scoped_rule_pattern [EXTRACTED 1.00]
- **The front-end UX review flow: rule, command, agent, scan, references** — _claude_rules_frontend_ux_review_before_pr, _claude_skills_ux_review_skill_ux_review_command, _claude_agents_frontend_ux_designer_agent, _claude_agents_frontend_ux_designer_ux_scan, _claude_agents_frontend_ux_designer_mobbin_connector, claude_frontend_ux_review_pointer [EXTRACTED 1.00]
- **Wind totals runbook: rule -> Pinnacle gate -> lead calibration -> unit sizing -> poller** — nfl_nfl_game_lines_model_system_wind_totals_rule, nfl_nfl_game_lines_model_system_pinnacle_gate, nfl_nfl_game_lines_model_system_forecast_lead_calibration, nfl_nfl_game_lines_model_system_unit_sizing_policy, nfl_nfl_game_lines_model_system_kelly_proportional_slate_shading, nfl_readme_wind_poller, nfl_readme_weekly_wind_card, nfl_readme_wind_totals_model, nfl_readme_stake_sizing, nfl_scripts_calibrate_lead [EXTRACTED 1.00]
- **In-play stale-state guards: phantom edges when our state and the book's disagree in time** — docs_rules_evidence_book_move_clock, docs_rules_evidence_live_settled_sec, docs_thresholds_edge_cap_phantom_edges, docs_thresholds_fresh_quote_forward_check, docs_sports_nfl_live_leader_state_lag [INFERRED 0.75]
- **The EV floor regime: global floor, per-model floors, the standing board and the honest re-sweep** — docs_thresholds_global_min_ev, docs_rules_evidence_model_own_ev_floor, docs_rules_evidence_standing_board_held_to_floor, docs_thresholds_honest_cut_sweep, docs_thresholds_nfl_prop_market_ev_floor [INFERRED 0.85]
- **Honest probability and the EV floor gate** — docs_probability_calibration_pooled_offset, docs_probability_calibration_global_min_ev, docs_probability_calibration_honest_ev_gate, docs_nfl_rule_2026_track_model_own_ev_floor, docs_nhl_market_lab_borrowed_correction [INFERRED 0.85]
- **NFL -> NCAAF live-model lineage: two calibration gates, market licensing, kill criteria** — nfl_live_model_readme_nfl_live_model, nfl_live_model_readme_gate_1_win_probability, nfl_live_model_readme_gate_2_total_coverage, nfl_live_model_readme_kill_criterion_two_seasons, ncaaf_live_readme_ncaaf_live_model, ncaaf_live_readme_gate_1_win_probability, ncaaf_live_readme_gate_2_total_shape, ncaaf_live_readme_lane_licenses, ncaaf_live_readme_edge_question_phase_3 [INFERRED 0.85]
- **Live price freshness: the staleness guards and the measured feed floor they bound** — docs_live_betting_five_live_staleness_guards, docs_live_betting_book_move_clock, docs_live_betting_settled_state_rule, docs_config_topology_frozen_book_must_not_win, docs_config_topology_live_odds_max_age_sec_60, docs_discord_books_publish_clock_only_freshness, docs_discord_feed_has_45s_floor, docs_live_odds_freshness_45_second_aggregator_cache, docs_live_odds_freshness_coarse_not_behind [INFERRED 0.85]
- **The constants and gates that govern what nfl_prop_market may publish** — docs_nfl_prop_offset_evidence_nfl_prop_market, docs_nfl_prop_over_lean_side_edge_cuts, docs_nfl_prop_offset_evidence_nfl_prop_max_lead_hours, docs_nfl_prop_offset_evidence_nfl_prop_publish_hour_utc, docs_nfl_edge_search_prop_market_ev_floor, docs_nfl_prop_injury_veto_out_doubtful_veto [INFERRED 0.85]
- **GitHub Actions runners used as the open-egress route the sandbox lacks** — _github_workflows_fetch_brand_assets_fetch_brand_assets_workflow, _github_workflows_monitor_probe_monitor_probe_workflow, _github_workflows_live_prop_validation_live_prop_validation_workflow, _github_workflows_prune_merged_branches_prune_workflow, claude_sandbox_limits_are_not_system_limits [INFERRED 0.85]
- **The team-stats leak: discovery, rebuild, freeze gate and the honest retrain** — docs_team_stats_leak_season_final_snapshot_leak, docs_team_stats_leak_pitcher_stats_rebuild, docs_team_stats_rebuild_scope_phased_sequencing, docs_team_stats_leak_assert_retrain_allowed, docs_team_stats_leak_team_stats_asof_verify, docs_sports_mlb_leak_repair_2026_09_03, docs_sports_mlb_f5_moneyline_v4 [INFERRED 0.85]
- **From DK-decides to deciding, settling and grading CLV at the price actually taken** — docs_config_topology_models_only_decide_on_draftkings, docs_best_line_decision_columns_stage_2, docs_best_line_live_lanes_join_best_price, docs_live_betting_live_pick_decided_at_best_in_play_price, docs_clv_which_price_is_the_bet, docs_followups_clv_at_price_taken_decided [INFERRED 0.95]

## Communities (891 total, 205 thin omitted)

### Community 0 - "Injury report ingestion with WNBA fallback"
Cohesion: 0.07
Nodes (21): TestCoreTeamsFallback, _athlete_name(), _compute_return_ramp(), _espn_team_ids(), fetch_espn_injuries(), _fetch_espn_team_injuries(), fetch_mlb_transactions(), _fetch_nba_espn_team_ids() (+13 more)

### Community 1 - "Mobile stats board"
Cohesion: 0.01
Nodes (341): P, TouchSet, PlayerPropQuote, Sport, errorKind, gameStatus, RulerHold, RulerScale (+333 more)

### Community 10 - "App settings, feedback and push setup"
Cohesion: 0.02
Nodes (139): IoniconName, Listener, ConnectionMap, providerMeta, SportsbookConnection, SportsbookProvider, FeedbackCategory, FeedbackMessage (+131 more)

### Community 100 - "Live monitor API probe"
Cohesion: 0.04
Nodes (36): _Resp, configured(), guild_stats(), main(), _credits_from(), _scrub(), classify(), paid_apis() (+28 more)

### Community 101 - "NBA injury report ingest tests"
Cohesion: 0.07
Nodes (25): _Conn, _Cur, _PdfFetcher, content_hash(), garbled_note(), _content_of_fixture(), _rows(), test_a_changed_report_stores_its_rows() (+17 more)

### Community 113 - "tests/test_nfl_live_leader_gameday.py"
Cohesion: 0.05
Nodes (33): FakeClient, FakeClock, FakeConn, FakeFeed, _Rows, art(), live_state(), quote_payload() (+25 more)

### Community 114 - "nfl_live_leader/gameday.py"
Cohesion: 0.05
Nodes (31): Cadence, GameContext, LiveOddsFeed, Quote, LiveState, release_read(), parse_book_ts(), quote_predates_score() (+23 more)

### Community 115 - "tests/test_calibration_promotion.py"
Cohesion: 0.07
Nodes (25): FakeConn, eligibility_clause(), maps_materially_differ(), promote(), _payload(), _row(), test_a_broken_table_is_identity_maps_not_an_exception(), test_a_map_that_does_not_help_is_silent() (+17 more)

### Community 116 - "tests/test_score_off_any_book_line.py"
Cohesion: 0.08
Nodes (33): _FakeConn, _fallback_line_quote(), _cut(), _on(), _pick(), _row(), _sql_const(), _src() (+25 more)

### Community 118 - "NCAAF FBS team registry tests"
Cohesion: 0.12
Nodes (9): TestRefusalLog, TestRegistryHealthCheck, _alarm_part(), _live_db(), _promoted(), _registry_check(), _snapshot(), _team() (+1 more)

### Community 12 - "Mobile pick filters and sorting"
Cohesion: 0.02
Nodes (219): P, Props, ActivePill, Props, Props, LivePicksState, reachFrame, DateOption (+211 more)

### Community 120 - "tests/test_ncaaf_alias_scores.py"
Cohesion: 0.08
Nodes (32): _FakeConn, _FakeCursor, alias_score_updates(), _date_or_none(), mirror_scores_to_alias_rows(), mirror_stored_finals(), _cfbd(), _row() (+24 more)

### Community 121 - "Prop alternate line parsing tests"
Cohesion: 0.09
Nodes (20): _Conn, _market_chunks(), alt_markets_due(), _ou(), _parse(), test_a_failed_check_does_not_spend(), test_a_player_the_book_lists_at_1_5_keeps_the_0_5_alternate(), test_a_sport_with_no_alternates_never_asks() (+12 more)

### Community 122 - "NBA injury report pulls and retries"
Cohesion: 0.13
Nodes (18): Fetcher, _Fetcher, _all_slots(), ensure_tables(), load_schedule(), main(), previous_report(), pull_one() (+10 more)

### Community 123 - "tests/test_backtester.py"
Cohesion: 0.07
Nodes (9): TestCalibrationError, TestComputeBacktestSummary, TestEvaluateResult, TestGoLiveGateConstants, TestIterSides, _calibration_error(), compute_backtest_summary(), _evaluate_result() (+1 more)

### Community 124 - "Weather lookahead and NHL league helpers"
Cohesion: 0.07
Nodes (7): TestTheWeatherStepWalksTheWindow, _nhl_blended_features(), d(), _league(), _loose_summary(), s(), _name()

### Community 125 - "nfl/live_model/feeds/odds_live.py"
Cohesion: 0.08
Nodes (16): CreditMeter, LiveOddsClient, Quote, JsonlRecorder, best_price(), parse_events(), _parse_ts(), _side_of() (+8 more)

### Community 127 - "NHL props newest quote shopping"
Cohesion: 0.10
Nodes (8): _Conn, TestOnlyTheNewestFetchIsShopped, TestWhoThePlayerIs, candidates(), draftkings_at(), identities(), latest_quotes(), upcoming_rows()

### Community 129 - "NBA prop market lab"
Cohesion: 0.09
Nodes (44): NBTable, add_units(), assemble(), best_per_key(), boot_ci(), build_quotes(), candidates_from(), choose_floor() (+36 more)

### Community 13 - "Discord pick notifier tests"
Cohesion: 0.02
Nodes (113): _FakeConn, _FakeResult, _Resp, _cand(), _et_now_iso(), _live_row(), _live_setup(), _no_prod_threshold_sync() (+105 more)

### Community 131 - "nfl/live_model/tests/test_backup_snaps.py"
Cohesion: 0.11
Nodes (21): _FakeConn, back_up(), digest(), _flush(), iter_files(), main(), _mb(), psycopg2_bytes() (+13 more)

### Community 135 - "mobile/scripts: verify_book_links + verify_betslip_combine"
Cohesion: 0.06
Nodes (37): betslipCombineKind, combineBetMgm(), combineBetslipLinks(), combineCaesars(), combineDraftKings(), combineEspnBet(), combineFanDuel(), fanDuelPairs() (+29 more)

### Community 137 - "NBA official injury report ingest"
Cohesion: 0.06
Nodes (32): Report, _bands(), _column_of(), _columns(), finish_rows(), _hrules(), _lines_of(), load_players() (+24 more)

### Community 14 - "College football features and FBS list"
Cohesion: 0.05
Nodes (28): TestFbsGate, TestUnratedFbsClaim, _blk_points_l3(), _blk_stats(), build_bulk_ncaaf_lookups(), build_ncaaf_features_from_bulk(), build_ncaaf_game_features(), fbs_refusal_claims() (+20 more)

### Community 140 - "mobile/scripts/verify_contrast_tokens.ts"
Cohesion: 0.05
Nodes (41): Pair, code(), lum(), noGreen(), over(), ratio(), read(), readUtf8() (+33 more)

### Community 141 - "models/nhl_props.py"
Cohesion: 0.11
Nodes (23): Spec, _attach_teams(), build_frame(), build_goalie_frame(), build_skater_frame(), _ew(), excess_variance(), expected_value() (+15 more)

### Community 142 - "tests/test_health_pregame_prices_current.py"
Cohesion: 0.08
Nodes (31): _Conn, _at(), _game(), _row(), _run(), test_a_broken_feed_read_is_an_error_and_rolls_back(), test_a_broken_query_is_an_error_and_rolls_back(), test_a_cancelled_fight_and_a_pulled_game_do_not_raise_the_alarm() (+23 more)

### Community 143 - "Pick lock after settlement tests"
Cohesion: 0.08
Nodes (22): _SqliteShim, conn(), _game(), _pick(), _survivors(), test_a_bet_is_never_dropped_for_an_earlier_no_signal(), test_a_dead_zone_prop_row_locks_too(), test_a_final_game_is_not_a_scoring_target() (+14 more)

### Community 144 - "NBA game line move study"
Cohesion: 0.07
Nodes (33): Data, attach(), big_home_dog_signal(), consensus(), control_specs(), coverage_text(), fade_side(), favourite_sides() (+25 more)

### Community 145 - "NBA prop rule model and card"
Cohesion: 0.11
Nodes (18): Roster, coherent(), fair_under(), fetch_times(), find_bets(), in_window(), load_quotes(), minutes_to_tip() (+10 more)

### Community 146 - "tests/test_mlb_game_market.py"
Cohesion: 0.06
Nodes (33): GameMarketBet, _SlateConn, scoring_method(), find_spread_bets(), find_total_bets(), _gap_seconds(), _is_runline(), load_latest_quotes() (+25 more)

### Community 150 - "Threshold review job"
Cohesion: 0.06
Nodes (28): _Conn, _is_paused(), _quiet(), rule_only(), _slate(), test_a_losing_model_with_enough_bets_is_flagged(), test_a_losing_model_with_too_few_bets_is_left_alone(), test_a_milestone_fires_only_once() (+20 more)

### Community 152 - "Idle read transaction tests"
Cohesion: 0.06
Nodes (19): ViewMigrationResult, _Rec, _apply_one(), apply_view_migrations(), _is_transient_lock_error(), _with_lock_timeout(), _flat(), test_a_lock_timeout_fails_that_file_and_the_next_still_runs() (+11 more)

### Community 154 - "UFC phantom fight filter"
Cohesion: 0.21
Nodes (6): TestFilterUfcPhantom, TestIsKnownUfcMatchup, _filter_ufc_phantom(), _is_known_ufc_matchup(), _game(), _odds()

### Community 155 - "tests/test_prop_box_scores.py"
Cohesion: 0.12
Nodes (14): ScriptConn, ensure_prop_box_scores(), missing_prop_games(), _pick(), test_a_logged_game_is_not_fetched_and_a_goalie_gap_is(), test_a_probe_error_that_is_not_a_timeout_raises_after_rollback(), test_a_probe_timeout_rolls_back_and_returns_empty(), test_a_recent_nfl_attempt_is_not_repeated() (+6 more)

### Community 156 - "NBA game model prop feature tests"
Cohesion: 0.06
Nodes (40): _Stop, _box(), _g(), _games(), _inj(), _model(), _props(), _run() (+32 more)

### Community 160 - "Worker job queue claim and run"
Cohesion: 0.06
Nodes (23): _Conn, _DedupeConn, _fake(), test_a_busy_queue_claims_nothing(), fetchone(), test_a_declared_job_is_queued_once_however_often_it_is_read(), test_a_failing_job_is_requeued_until_the_attempt_cap(), _boom() (+15 more)

### Community 161 - "NBA prop market card"
Cohesion: 0.10
Nodes (13): Plan, decided_games(), ensure_decisions_table(), games_with_a_bet(), load_roster(), main(), projection_holdings(), publish() (+5 more)

### Community 162 - "Database schema guard and brand avatar"
Cohesion: 0.06
Nodes (20): GuardConn, _ddl(), _dk_direct_feed(), _is_guarded(), _job_queue(), _live_calibration(), _modules_with_write_time_ddl(), _run_ledger() (+12 more)

### Community 163 - "College football ratings feature tests"
Cohesion: 0.11
Nodes (15): AdjRatings, blended_rating(), fit_opponent_adjustment(), _synth(), test_blend_falls_back_when_one_side_missing(), test_blend_weights_move_from_prior_to_current(), test_confounded_home_assignment_plus_heavy_alpha_corrupts_hfa(), test_features_for_dedupes_and_preserves_order() (+7 more)

### Community 164 - "tests/test_nfl_opener.py"
Cohesion: 0.09
Nodes (10): TestFireWindow, TestFreshNumberLabel, TestHeldMinutes, TestModelCardSplit, _giants_board(), _giants_prior_at_2129(), _giants_sched(), _obs() (+2 more)

### Community 165 - "NHL stats, game logs and odds archive"
Cohesion: 0.03
Nodes (76): TestLogRowBuilders, fetch_all(), backfill(), build_goalie_rows(), build_skater_rows(), build_team_rows(), _complete(), _fetch() (+68 more)

### Community 170 - "NBA game model luck feature tests"
Cohesion: 0.05
Nodes (39): _Stop, _against_bet(), _f6c_inputs(), _games_for_standings(), _gs(), _market_pricing(), _one_game_data(), _pair() (+31 more)

### Community 171 - "CLV math and devig functions"
Cohesion: 0.04
Nodes (35): _Conn, _Res, _identity_maps(), _platform_gates_off(), test_breakeven_is_the_real_vig_hurdle(), test_a_one_way_close_is_not_de_vigged(), test_a_worse_close_is_negative_and_equal_prices_are_zero(), test_devigging_the_taken_price_is_not_what_primary_does() (+27 more)

### Community 172 - "NHL derivative totals card tests"
Cohesion: 0.09
Nodes (13): _Meter, _Resp, main(), run(), _clear_bets(), _markets(), test_apply_and_probe_without_a_key_return_before_any_call(), test_card_writes_nothing_and_the_pipeline_does_not_call_it() (+5 more)

### Community 174 - "tests/test_publisher_lock.py"
Cohesion: 0.08
Nodes (15): _Conn, _Result, _clear_locks(), _no_prod_threshold_sync(), _signal_row(), test_a_connection_that_cannot_lock_still_publishes(), test_an_exception_mid_publish_does_not_wedge_every_later_pass(), test_every_signal_publisher_takes_the_lock() (+7 more)

### Community 177 - "tests/test_credit_budget.py"
Cohesion: 0.09
Nodes (22): _Conn, daily_burn(), latest_remaining(), plan_credit_budget(), _burn_conn(), _plan(), test_a_billing_reset_is_not_a_refund(), test_a_call_is_billed_at_what_the_api_says_it_cost() (+14 more)

### Community 178 - "NBA prop market publish tests"
Cohesion: 0.11
Nodes (15): NbaPropBet, NbaPropDecision, _PublishConn, pick_label(), pick_rows(), _bet(), _decision(), test_a_bet_at_draftkings_carries_no_best_columns() (+7 more)

### Community 18 - "App custom model filters and sliders"
Cohesion: 0.18
Nodes (20): Props, GestureIntent, Scale, RangeSlider(), applyBound(), grabTarget(), readIntent(), resolveTie() (+12 more)

### Community 181 - "Player news ingest"
Cohesion: 0.04
Nodes (51): NewsItem, NewsPlayer, FakeConn, FakeResponse, _Result, _article_url(), _athletes_in(), build_name_index() (+43 more)

### Community 186 - "NFL wind and opener publisher"
Cohesion: 0.11
Nodes (13): TestPublishOpenerInsertOnce, _changed(), _clear_scored_row(), _flush_board_safe(), _flush_snapshots_safe(), latest_eval_rows(), _lock_model(), publish() (+5 more)

### Community 189 - "Settlement self-healing tests"
Cohesion: 0.12
Nodes (23): _FakeStatsapi, _game(), _pick(), test_a_doubleheader_row_with_a_final_keeps_its_picks_grading(), test_a_final_game_is_never_voided(), test_a_game_with_any_box_score_row_is_not_refetched(), test_a_postponed_game_voids_its_pending_bets(), test_a_recent_postponement_waits_for_a_same_day_resumption() (+15 more)

### Community 19 - "NHL prop card publishing"
Cohesion: 0.05
Nodes (25): TestTheCard, TestWhoThePlayerIs, TestFourNhlPropBetsANight, step_nhl_prop_scoring(), bs_implied(), candidates(), identities(), latest_quotes() (+17 more)

### Community 193 - "tests/test_first_signal_repair.py"
Cohesion: 0.08
Nodes (27): _Conn, _VoidedConn, step_restore_first_signals(), patch_conn(), _make(), _sql_of(), test_a_lane_already_holding_its_first_bet_is_untouched(), test_a_lane_with_no_sibling_still_restores() (+19 more)

### Community 196 - "tests/test_ungraded_model_performance.py"
Cohesion: 0.08
Nodes (12): FakeConn, test_perf_reads_the_matview_not_the_expensive_view(), test_roster_reports_a_registered_but_untrained_model(), _second_arm(), _sql(), test_a_fully_unpriced_recovered_model_reports_no_roi(), test_a_recovered_row_still_reports_roi_over_the_priced_bets(), test_both_arms_stay_inside_the_settled_bet_gate() (+4 more)

### Community 198 - "mobile/scripts/verify_push.ts"
Cohesion: 0.06
Nodes (46): PushState, PushStatus, ForcedOnlyReason, PushDiagnosis, PushFailureReason, TestPushResult, reasonOf(), NotificationsCard() (+38 more)

### Community 199 - "Prop price pregame cutoff tests"
Cohesion: 0.08
Nodes (15): _StubConn, _latest_book_prop_row(), _latest_dk_prop_row(), _assigned_from(), _prop_scorers(), test_every_scorer_call_site_passes_a_pregame_cutoff(), test_get_prop_dk_odds_forwards_the_cutoff(), test_in_play_snapshots_are_excluded_unconditionally() (+7 more)

### Community 2 - "Mobile markets and formatting"
Cohesion: 0.02
Nodes (234): Row, Props, Props, IoniconName, Props, DecisionPriced, GameLike, gameStartState (+226 more)

### Community 203 - "tests/test_nhl_asof.py"
Cohesion: 0.17
Nodes (3): GoalieBook, TestGoalieAsOf, _g()

### Community 204 - "Trainer, features and shared setup"
Cohesion: 0.02
Nodes (72): TestPregameSnapshotGuard, _Conn, pregame_cutoff_sql(), trusted_first_pitch(), _blk_bullpen_ip(), _blk_injuries(), _blk_nhl_loc_goals(), _blk_nhl_rolling_goals() (+64 more)

### Community 205 - "NFL in-play game state feed"
Cohesion: 0.12
Nodes (18): CoreClient, EventMeta, _abbr(), game_seconds(), https(), _int(), is_admin_play(), is_conversion_play() (+10 more)

### Community 209 - "data/ingestors/nfl_inplay_history.py"
Cohesion: 0.16
Nodes (22): Budget, buy_halftime(), buy_inplay(), events_for(), _floor5(), _get(), halftime_requests(), halftime_windows() (+14 more)

### Community 21 - "App thresholds and daily results"
Cohesion: 0.02
Nodes (160): Case, CustomModelStats, Acc, DailyResults, DayGameSummary, ModelDayStats, ScopedDailyResults, SportDayBreakdown (+152 more)

### Community 211 - "App bankroll card"
Cohesion: 0.09
Nodes (30): BankrollCheck, BankrollCommit, BankrollPatch, BankrollRead, NumberSeparators, Part, walk(), deviceSeparators() (+22 more)

### Community 212 - "App theme, links and parlay screen"
Cohesion: 0.02
Nodes (186): Props, Nav, Props, Props, FilterChipProps, Props, Props, Props (+178 more)

### Community 215 - "Prop trainer and WNBA rebuilds"
Cohesion: 0.02
Nodes (94): TestTrainingExcludesThemAndScoringDoesNot, assert_retrain_allowed(), calibration_method(), _all_batter_rows(), _all_pitcher_rows(), _batter_rate(), _batter_rolling_avg(), _batter_savant() (+86 more)

### Community 217 - "NCAAF in-play engine and pick lock"
Cohesion: 0.05
Nodes (22): LiveEngine, FakeConn, _Rows, american_to_prob(), devig_power(), write_picks(), expected_value(), _is_paused() (+14 more)

### Community 22 - "NBA prop projection model and card"
Cohesion: 0.02
Nodes (116): ProjectionBet, Spec, asof_roster(), box_from_log(), coherent(), collapse_official(), compact_report(), espn_compact() (+108 more)

### Community 220 - "tests/test_db_reconnect.py"
Cohesion: 0.09
Nodes (16): _Conn, _Cursor, _is_write(), _lost(), test_a_committed_transaction_is_clean_again(), test_a_lost_connection_with_uncommitted_writes_raises_connection_lost(), test_a_read_on_a_lost_connection_reconnects_and_retries(), test_a_statement_timeout_is_not_a_lost_connection() (+8 more)

### Community 223 - "In-play pick lock tests"
Cohesion: 0.10
Nodes (20): FakeConn, _Rows, _lane_signature(), _write_live_picks(), _locked_live_lanes(), test_the_lane_signature_carries_the_deciding_price(), _log_lines(), _pick() (+12 more)

### Community 225 - "tests/test_refresh_retry.py"
Cohesion: 0.14
Nodes (23): Decision, RefreshRun, _decide(), _done(), _run(), test_a_failed_view_migration_fails_the_step(), test_a_pass_that_finished_with_failed_steps_ran_its_chain(), test_a_redeploy_between_passes_replaces_nothing() (+15 more)

### Community 226 - "NBA results and lineup segments store"
Cohesion: 0.13
Nodes (5): PgStore, _games(), _postponed(), _schedule(), end()

### Community 228 - "NBA results ingestor tests"
Cohesion: 0.10
Nodes (28): _ESPN, FakeStore, _FixedNow, _game(), _ppd_game(), _resolver(), _run(), test_a_box_still_missing_since_opening_week_is_retried_all_season() (+20 more)

### Community 229 - "NBA public betting splits ingestor tests"
Cohesion: 0.05
Nodes (41): _NoDB, _Store, an_pct(), build_rows(), clean_pair(), match_game(), parse_v1_sides(), parse_v2_sides() (+33 more)

### Community 23 - "NBA game projection search lab"
Cohesion: 0.14
Nodes (13): Last, actuals(), apply_models(), calib_design(), f5_design(), fit_calibration(), fit_f5(), league_total() (+5 more)

### Community 230 - "tests/test_local_cache_is_additive.py"
Cohesion: 0.10
Nodes (13): _FakeConn, main(), _merge_with_cache(), _pull_odds(), _pull_seasoned(), _register_from_feature_engine(), cached(), _frame() (+5 more)

### Community 231 - "tests/test_calibration_check_coverage.py"
Cohesion: 0.10
Nodes (19): _Shim, _bet(), _calibration_results(), db(), _graded(), _make_db(), _only(), _promote() (+11 more)

### Community 233 - "tests/test_book_team_map.py"
Cohesion: 0.11
Nodes (15): _Conn, abbr_from_team_string(), resolve_game_id(), split_matchup(), test_a_non_mlb_sport_is_refused_rather_than_guessed(), test_a_string_with_no_at_sign_is_refused(), test_a_unique_game_resolves(), test_an_ambiguous_game_resolves_to_none() (+7 more)

### Community 234 - "tests/test_team_board_cache.py"
Cohesion: 0.08
Nodes (10): _Conn, _Cursor, team_board_pairs(), team_board_seasons(), _cols(), test_every_team_sport_gets_last_this_and_next_year(), test_one_failing_pair_does_not_stop_the_rest(), test_the_cache_the_refresh_and_the_thin_function_name_the_same_columns() (+2 more)

### Community 236 - "NHL blocked shots prop model"
Cohesion: 0.08
Nodes (20): TestTonightsRowIsATrainingRow, build_frame(), _ew(), expected_value(), fit(), load_skaters(), load_teams(), name_key() (+12 more)

### Community 238 - "nfl/live_model/tests/test_rush_attempt_pace.py"
Cohesion: 0.07
Nodes (21): Read, pace_ratio(), _sigmoid(), under_prob(), _price(), test_a_line_he_has_already_passed_is_not_a_live_proposition(), test_a_missing_accrued_count_is_refused_not_treated_as_zero(), test_a_reachable_over_is_declined_rather_than_faded() (+13 more)

### Community 239 - "tests/test_nfl_poll_fast_silence.py"
Cohesion: 0.11
Nodes (15): FakeConn, publish_board(), _append_board(), _body(), _row(), _sent(), _setup(), test_a_half_written_last_row_waits_for_the_next_tick() (+7 more)

### Community 24 - "NHL moneyline rebuild labs"
Cohesion: 0.10
Nodes (26): OffsetLogit, feed_prices(), _ts(), floored(), main(), module_frame(), _best(), _px() (+18 more)

### Community 245 - "tests/test_nhl_asof.py"
Cohesion: 0.11
Nodes (6): TeamBook, TestBlendedTeamInputs, TestTeamRatesAsOf, _r(), _t(), test_the_training_path_reads_nhl_odds_by_game_not_by_sport()

### Community 247 - "tests/test_dk_freshness_parse.py"
Cohesion: 0.12
Nodes (17): _FakeConn, _FakeResult, _american(), parse_dk_payload(), _store(), _payload(), test_a_half_priced_market_is_dropped_rather_than_half_recorded(), test_an_event_with_no_markets_yields_nothing_rather_than_raising() (+9 more)

### Community 248 - "NBA historical odds gap backfill"
Cohesion: 0.09
Nodes (18): _Ledger, _Meter, _Resp, gap_instants(), line_snapshots(), _hourly(), _t(), test_a_fetch_is_ledgered_by_its_instant_off_the_hour_and_by_its_hour_on_it() (+10 more)

### Community 249 - "models: slate_concentration + test_slate_concentration"
Cohesion: 0.15
Nodes (15): SlateConcentration, apply_slate_guard(), apply_slate_concentration_guard(), _attr(), _edge_of(), _is_bet(), measure_side_concentration(), _side_of() (+7 more)

### Community 250 - "College football in-play history pull"
Cohesion: 0.08
Nodes (29): _Conn, _blank_row(), budget_for(), calls_in(), _floor5(), _get(), _iso(), main() (+21 more)

### Community 251 - "View migration lock handling tests"
Cohesion: 0.09
Nodes (23): _Conn, _Deadlock, _LockTimeout, _StatementTimeout, _Syntax, execute(), _before(), _code() (+15 more)

### Community 254 - "Prop odds missing game tests"
Cohesion: 0.15
Nodes (4): FakeConn, _run(), test_event_with_no_games_row_is_skipped_and_others_still_insert(), test_fk_on_insert_does_not_unwrite_the_events_that_already_landed()

### Community 255 - "NCAAF in-play history backtest"
Cohesion: 0.07
Nodes (23): _StubEngine, out_path(), build_candidates(), decide(), first_signals(), _fmt(), grade(), load_snapshots() (+15 more)

### Community 257 - "College football model search and validation"
Cohesion: 0.05
Nodes (42): FoldResult, features_for(), _apply_calibration(), exponential_recency_weights(), _logit(), make_ensemble(), fit_predict(), make_lgbm() (+34 more)

### Community 258 - "Deploy checks and worker job queue"
Cohesion: 0.07
Nodes (17): _Conn, test_a_declared_job_carries_its_run_after(), test_a_failing_check_raises_so_the_queue_announces_it(), test_a_job_can_only_name_a_registered_check(), test_enqueue_rejects_a_naive_run_after(), test_enqueue_stores_run_after(), test_every_check_is_read_only(), test_the_claim_waits_for_run_after() (+9 more)

### Community 259 - "MLB twin game merge"
Cohesion: 0.13
Nodes (12): _Conn, apply_one(), canonical(), counts(), main(), plan(), test_a_canonical_id_maps_to_nothing(), test_a_non_mlb_or_malformed_id_is_left_alone() (+4 more)

### Community 26 - "Mobile teams board and team detail"
Cohesion: 0.05
Nodes (105): NextGame, Section, Tier, FormGame, FormSummary, headToHead, lineMove, PickRecord (+97 more)

### Community 265 - "Best line threshold sweep"
Cohesion: 0.10
Nodes (12): _Conn, american_to_decimal(), units_at(), _row(), test_a_better_price_pays_more_than_the_dk_price(), test_a_loss_costs_one_unit_at_every_price(), test_a_push_is_flat(), test_a_retired_model_is_never_recommended_a_cut() (+4 more)

### Community 266 - "NFL weather fetch for edge studies"
Cohesion: 0.18
Nodes (10): DailyLimit, Pacer, consolidate(), era5_check(), game_hours(), log(), main(), om_get() (+2 more)

### Community 269 - "NCAAF college data ingest tests"
Cohesion: 0.07
Nodes (8): _GamesConn, _TeamsConn, test_ingest_games_retains_a_historical_utc_id_and_uses_et_for_a_new_row(), fake_get(), test_ingest_pulls_fbs_then_everyone_and_fbs_rows_win(), test_ingest_retries_everyone_without_a_year_if_the_season_filter_is_empty(), test_prior_context_tolerates_missing_talent_and_returning(), test_weekly_snapshot_build_aborts_on_failed_fetch()

### Community 27 - "Mobile betslip and parlay legs"
Cohesion: 0.02
Nodes (186): Props, ParlayRestorePayload, ResolvedSlip, GameLineLegSpec, GameLineMarket, LineLegSpec, LineSheetInput, LineSide (+178 more)

### Community 270 - "NHL starting goalie lookup tests"
Cohesion: 0.12
Nodes (4): TestGoalieLookup, TestNoHollowTeamRowBeforeTheFirstGame, TestThreeWayMarketKey, _same_goalie_name()

### Community 273 - "tests/test_prop_odds_utc_stamp.py"
Cohesion: 0.12
Nodes (13): _Conn, _assert_utc_stamp(), _frozen(), _run_mlb(), capture(), events(), _run_ncaaf(), test_an_eastern_row_then_a_later_utc_row_sorts_in_time_order() (+5 more)

### Community 274 - "Live monitor server"
Cohesion: 0.24
Nodes (4): Handler, _connect(), dumps(), _json_default()

### Community 277 - "NFL publisher lookahead and key tests"
Cohesion: 0.08
Nodes (14): _Conn, _sql_for(), test_a_started_game_is_still_never_published(), test_both_publishers_apply_the_apps_action_filter(), test_both_publishers_read_the_table_the_app_reads(), test_capture_reaches_as_far_as_the_poller_can_write(), test_capture_reaches_forward_for_the_locked_lookahead_sports(), test_ncaaf_lookahead_is_only_safe_because_the_lock_is_general() (+6 more)

### Community 278 - "tests/test_feature_artifact_agreement.py"
Cohesion: 0.11
Nodes (13): _Stub, _TolerantUnpickler, _load(), _newest_artifact(), test_artifact_width_matches_its_own_feature_cols(), test_config_list_matches_the_trained_artifact(), test_known_drift_only_names_real_models(), test_pending_features_are_not_live_without_a_retrain() (+5 more)

### Community 279 - "NFL prop market one side per line"
Cohesion: 0.16
Nodes (8): _Conn, best_per_prop(), _hockenson(), test_a_different_market_on_the_same_player_is_still_its_own_bet(), test_input_order_does_not_decide_the_side(), test_nfl_publish_will_not_add_the_other_side_of_a_locked_line(), test_opposite_sides_of_one_line_collapse_to_the_bigger_edge(), test_wnba_publish_will_not_add_the_other_side_of_a_locked_line()

### Community 28 - "CLV graded at the price taken"
Cohesion: 0.07
Nodes (22): _Conn, _Res, _fn(), _migration(), _pick(), test_a_draftkings_decided_row_is_unchanged(), test_a_legacy_row_that_cannot_be_re_measured_leaves_the_old_method(), test_a_legacy_stamped_row_is_re_measured_and_leaves_the_queue() (+14 more)

### Community 281 - "tests/test_cloud_retrain_artifacts.py"
Cohesion: 0.10
Nodes (12): _Conn, _restore_artifact(), test_a_failed_upload_does_not_lose_a_model_that_trained(), test_a_missing_artifact_table_is_not_an_error_on_restore(), test_a_no_register_run_stores_nothing(), test_load_model_actually_loads_from_the_store_when_the_file_is_gone(), fetchone(), test_load_model_returns_none_when_the_store_has_nothing_either() (+4 more)

### Community 285 - "System health and published record checks"
Cohesion: 0.03
Nodes (41): HealthReport, ncaaf_season_for_date(), test_a_game_date_inside_the_window_counts(), test_a_lookahead_commence_counts_even_when_game_date_is_outside(), test_a_signal_locked_after_first_pitch_was_never_deliverable(), test_a_signal_locked_before_first_pitch_still_counts(), test_a_signal_locked_exactly_at_first_pitch_counts(), test_a_started_game_outside_the_window_does_not_count() (+33 more)

### Community 288 - "tests/test_nfl_opener.py"
Cohesion: 0.20
Nodes (5): TestBettableBooksOnly, TestSelectOpenerBets, _both_sides(), _frame(), _sched()

### Community 291 - "NFL prop data parsing tests"
Cohesion: 0.11
Nodes (10): TestGamesRows, TestKickoff, TestParseTeamRows, TestUpcomingRows, games_rows(), _int_or_none(), _kickoff_utc(), _num_or_none() (+2 more)

### Community 295 - "Discord pick posting and restates"
Cohesion: 0.03
Nodes (60): Ledger, DiscordVoidRejected, UnitStake, test_a_malformed_timestamp_drops_the_stamp_rather_than_raising(), test_american_odds_formatting(), test_delete_posted_degrades_when_the_column_is_missing(), test_matchup_is_sport_aware(), test_prob_only_picks_fall_back_to_the_settlement_price() (+52 more)

### Community 298 - "tests/test_nfl_wind_publisher.py"
Cohesion: 0.13
Nodes (10): TestBuildRows, TestKickFields, TestParseMatchup, build_rows(), _fmt_line(), kick_fields(), parse_matchup(), test_nfl_wind_and_opener_rows_drop_a_bet_under_the_floor() (+2 more)

### Community 3 - "Odds feed fetching and quota tracking"
Cohesion: 0.01
Nodes (142): ConnectionLost, Meter, Meter, Meter, TestEveryOtherSportStillMintsItsOwn, TestNflResolvesOntoTheSchedule, TestTheResolverFailsClosed, FakeResp (+134 more)

### Community 30 - "NFL live prop model tests"
Cohesion: 0.04
Nodes (37): Read, _FakeOdds, _IdRecordingOdds, blind_over_prob(), over_prob(), _pass_attempt_bias_allowed(), _core_worker(), test_a_deployed_bias_must_sit_inside_its_measured_interval() (+29 more)

### Community 300 - "tests/test_health_reason_and_cadence.py"
Cohesion: 0.19
Nodes (11): Report, _one(), test_a_24h_ts_check_reads_as_daily(), test_a_bare_add_still_fills_both_columns(), test_a_broken_query_is_its_own_reason(), test_a_passing_check_says_fresh(), test_a_skipped_check_says_the_gate_was_shut(), test_a_ts_check_reports_its_own_max_age() (+3 more)

### Community 301 - "tests/test_live_publish_parity.py"
Cohesion: 0.17
Nodes (12): _Conn, _db(), _labels(), _pick(), test_a_bet_written_while_paused_is_not_announced_after_an_unpause(), test_a_live_health_state_still_publishes(), test_a_paused_model_is_not_announced(), test_a_retired_model_is_not_announced() (+4 more)

### Community 302 - "tests/test_nfl_weather_supabase_readback.py"
Cohesion: 0.13
Nodes (13): FakeConn, _patch_conn(), _rows(), test_a_null_requested_lead_is_not_returned(), test_a_one_lead_response_is_not_stored(), test_a_partial_window_is_not_returned(), test_a_store_failure_is_a_warning_not_an_error(), test_a_subset_of_leads_reads_only_those_columns() (+5 more)

### Community 306 - "NBA game projection world and models"
Cohesion: 0.11
Nodes (13): EW, Model, build_models(), build_state(), fit_hyper(), fit_play(), hyper_seasons(), league_rates() (+5 more)

### Community 307 - "Pregame line poller change tests"
Cohesion: 0.09
Nodes (14): _PollConn, _credits_used_today(), _fingerprint(), _key(), last_known_prices(), _num(), poll_once(), quoted_keys() (+6 more)

### Community 308 - "Pitcher stats as-of invariant tests"
Cohesion: 0.05
Nodes (27): _FakeConn, last3_rates(), outs_from_ip(), per_nine(), whip(), build_rows(), _row(), _app() (+19 more)

### Community 312 - "NHL props card slate tests"
Cohesion: 0.17
Nodes (6): TestTheBacktestGradesTheRuleTheCardPlays, TestTheCard, implied(), pick_rows(), _mus(), _quotes()

### Community 314 - "Pipeline log reason tests"
Cohesion: 0.22
Nodes (6): _Conn, _capture(), test_a_false_step_records_the_last_error_it_logged(), test_a_false_step_that_logged_nothing_still_says_so(), test_a_raising_step_still_records_the_exception(), test_the_sink_is_removed_after_the_step()

### Community 316 - "Stats and prop data ingest"
Cohesion: 0.05
Nodes (33): TestParsePlayerRows, TestParseNflverseScores, _df_to_rows(), _fetch_savant_csv(), _get_col(), _normalize_name(), _parse_pct(), backfill_nfl_player_stats() (+25 more)

### Community 32 - "NCAAF in-play score distribution pricing"
Cohesion: 0.03
Nodes (56): ScoreDistribution, _cluster_bootstrap(), evaluate(), main(), report(), fit(), load_states(), main() (+48 more)

### Community 320 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.09
Nodes (6): _Pg, _PgCursor, TestPreflightCiMode, wind(), wrapped(), fake_open()

### Community 321 - "Signal delivery health tests"
Cohesion: 0.17
Nodes (4): TestSignalDelivery, _add_signal(), _iso(), _results()

### Community 322 - "X results job and cursor wrapper tests"
Cohesion: 0.07
Nodes (9): _CursorResult, execute(), test_a_malformed_date_is_refused_before_anything_runs(), test_the_cursor_wrapper_rowcount_is_the_cursors(), test_the_job_does_not_bypass_the_day_is_over_guard(), test_the_job_does_not_read_rowcount_off_the_cursor(), test_the_job_only_clears_its_own_ledger_kind(), test_a_dropped_connection_replays_the_migration_with_its_lock_timeout() (+1 more)

### Community 327 - "NHL totals rule model and card"
Cohesion: 0.05
Nodes (36): NhlTotalBet, _LockConn, _SlateConn, implied(), _coherent(), _fetch_ts(), find_bets(), load_fetch_quotes() (+28 more)

### Community 33 - "nfl/live_model/feeds: test_feed_resilience + espn"
Cohesion: 0.04
Nodes (52): _ScriptedTick, _competitors(), _deref(), fetch_live_events(), _https(), make_fetcher(), fetch(), parse_core_event() (+44 more)

### Community 330 - "NFL opener card rows"
Cohesion: 0.27
Nodes (5): TestBuildOpenerRows, build_opener_rows(), _opener_model(), _card_row(), _row()

### Community 331 - "NHL prop backtest and EV lab"
Cohesion: 0.07
Nodes (29): TestRegimeOrder, books(), card(), claimed_vs_realised(), day_interval(), line(), load(), main() (+21 more)

### Community 334 - "In-play score change guard"
Cohesion: 0.13
Nodes (12): _FakeConn, _age_seconds(), _book_move(), _get_live_dk_odds(), _odds(), test_a_quote_published_before_the_score_is_declined(), test_a_quote_republished_after_the_score_is_kept(), test_the_age_bound_alone_would_have_allowed_it() (+4 more)

### Community 341 - "NFL prop rule with Kalshi tests"
Cohesion: 0.05
Nodes (18): Ladder, Rung, TestMarketRelative, TestNaNIsAbsent, find_bets(), _expit(), _logit(), _monotone() (+10 more)

### Community 342 - "tests/test_live_pick_features.py"
Cohesion: 0.18
Nodes (11): FakeConn, _record_live_features(), _pick(), test_a_live_bet_records_its_feature_row_and_lambda(), test_a_pick_with_no_feature_row_is_skipped_not_written_empty(), test_a_recorder_failure_is_rolled_back_to_its_savepoint(), test_a_recorder_failure_is_swallowed_rather_than_raised(), test_a_success_releases_its_savepoint() (+3 more)

### Community 349 - "tests/test_prop_missing_features.py"
Cohesion: 0.14
Nodes (5): TestARowMissingAFeatureIsNotScored, TestEveryPropLoopGoesThroughTheHelper, TestTheUmpireIsTheDeclaredException, _frame(), helper()

### Community 350 - "App sport filter and push routing"
Cohesion: 0.16
Nodes (18): NavRef, PushRoute, PicksView, clearNativeLastResponse(), navigateTo(), responseIdentifier(), usePushDeepLink(), load() (+10 more)

### Community 353 - "Injury fetch and prop odds test fakes"
Cohesion: 0.10
Nodes (4): _R, test_a_SUCCESSFUL_response_with_no_name_is_not_cached(), test_an_unknown_athlete_is_fetched_and_then_remembered(), execute()

### Community 354 - "NBA prop closing line tests"
Cohesion: 0.09
Nodes (11): _Conn, _Resp, test_a_close_already_held_is_not_bought_again(), test_a_due_close_buys_one_call_of_the_bet_markets_and_reports_its_credits(), test_a_pass_outside_the_window_spends_nothing(), test_only_a_game_holding_a_bet_and_only_once(), test_only_twelve_to_twenty_five_minutes_before_tip(), test_the_ten_minute_evening_passes_always_land_one_inside() (+3 more)

### Community 355 - "NFL in-play pick writer"
Cohesion: 0.02
Nodes (63): PicksRecorder, _AvoidConn, _Conn, _Decision, _OpenConn, announce_live_picks(), build_pick(), _is_market_opinion() (+55 more)

### Community 357 - "NFL wind scored row building"
Cohesion: 0.09
Nodes (8): TestBuildScoredRows, TestPickEmLabel, TestPreflightLockChecks, TestQualifyingRowIsNotANoneRow, _american_to_prob(), build_scored_rows(), _fmt_spread(), _num()

### Community 359 - "NHL moneyline anchored model"
Cohesion: 0.05
Nodes (32): OffsetLogit, _Fixed, _GamesConn, _add_rating(), build_inputs(), choose_C(), decision_window(), fit() (+24 more)

### Community 36 - "NCAAF CFBD ingestor tests"
Cohesion: 0.03
Nodes (62): _NullConn, backfill_ncaaf(), build_ncaaf_game_id(), _day_before(), eastern_game_date(), _local_aggregates(), ncaaf_slug(), parse_lines() (+54 more)

### Community 360 - "Walk-forward evaluation tests"
Cohesion: 0.12
Nodes (10): _Cols, _Frame, _fake(), test_a_fold_with_too_little_history_is_skipped(), test_a_single_class_test_season_is_skipped(), _frame(), test_every_fold_trains_only_on_earlier_seasons(), _frame() (+2 more)

### Community 361 - "NCAAF live state recording tests"
Cohesion: 0.16
Nodes (13): _Conn, record_live_states(), state_change_row(), state_key(), _state(), test_a_failed_write_never_costs_the_pass(), test_a_score_a_period_or_a_possession_change_is_written(), test_first_sight_is_written() (+5 more)

### Community 363 - "tests/test_run_ledger_orphans.py"
Cohesion: 0.12
Nodes (18): _Conn, db(), _insert_open(), _ledger(), _open_rows(), _row(), test_a_genuine_current_hang_is_still_detectable(), test_a_second_sweep_does_not_abort_the_pass_this_process_started() (+10 more)

### Community 368 - "MLB play-by-play twin game lookup"
Cohesion: 0.21
Nodes (9): _Conn, _Cur, _lookup_home_won(), mlb_game_final(), sbr_twin_id(), test_no_final_anywhere_is_none(), test_scored_canonical_row_wins_and_keeps_its_label(), test_twin_id_swaps_only_the_renamed_franchises() (+1 more)

### Community 37 - "NBA lineup stints from play-by-play"
Cohesion: 0.05
Nodes (50): Diagnostics, _Seg, alias_play_ids(), roster_from_plays(), score_plays(), _accumulate(), _add_one(), _and_one_follows() (+42 more)

### Community 370 - "UFC stats ingest"
Cohesion: 0.02
Nodes (108): _FakeConn, _IngestConn, _aggregate_stats(), backfill_ufc_csv(), build_events(), build_fighter_index(), _cached_etag(), _etag_cache_path() (+100 more)

### Community 371 - "Team stats rebuild and as-of checks"
Cohesion: 0.03
Nodes (53): _SeasonConn, already_a_series(), build_rows(), _games(), impossible_games_played(), live_season_snapshot_grace(), main(), _played_actual() (+45 more)

### Community 376 - "In-play calibrated decision tests"
Cohesion: 0.08
Nodes (18): RecordingConn, fetch_graded(), _in_graded_matview(), _is_live_lane(), _cut(), _signal(), test_a_big_enough_claim_still_fires_after_calibration(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking() (+10 more)

### Community 378 - "NFL DraftKings line snapshots"
Cohesion: 0.08
Nodes (13): TestDkLineRows, TestPublishLineSnapshots, TestSnapshotRowParams, append_snapshot_csv(), dk_line_rows(), dump_dk_lines(), _num(), snapshot_schedule() (+5 more)

### Community 380 - "Feature engine returnee and odds tests"
Cohesion: 0.21
Nodes (3): TestHasReturnee, TestMarketForOdds, _has_returnee()

### Community 381 - "tests/test_heartbeat_disabled_jobs.py"
Cohesion: 0.12
Nodes (9): Conn, _build(), test_a_job_marked_disabled_is_not_silent(), test_a_job_that_runs_here_is_not_marked(), test_a_service_leaves_alone_the_jobs_another_service_owns(), test_startup_marks_an_owned_job_that_is_switched_off(), ensure_schema(), failing_jobs() (+1 more)

### Community 382 - "NBA game projection family cells"
Cohesion: 0.10
Nodes (11): PointInputs, emit_family(), fair_frame(), family_frames(), gap_strength(), move_strength(), move_strength_by_season(), population() (+3 more)

### Community 385 - "Scorer any-book game line fallback"
Cohesion: 0.06
Nodes (34): _Clf, _GameOddsConn, _fallback_game_line_quote(), _get_scoring_odds(), _has_real_game_price(), _cut(), _mlb_feat(), _on() (+26 more)

### Community 387 - "tests/test_repair_bogus_first_pitch_labels.py"
Cohesion: 0.13
Nodes (8): _Conn, _run(), test_a_dry_run_writes_nothing_at_all(), test_a_short_backup_rolls_back_and_relabels_nothing(), test_the_backup_is_written_before_the_update(), test_the_backup_table_is_revoked_from_the_public_roles(), test_the_bogus_set_is_computed_never_listed(), test_the_query_is_scoped_to_the_scheduled_start_not_the_derived_one()

### Community 39 - "nfl/live_model/tests/test_executor.py"
Cohesion: 0.06
Nodes (48): Decision, Executor, american_to_decimal(), american_to_prob(), derivative_lag(), ev_floor(), _mk(), expected_value() (+40 more)

### Community 392 - "Odds pruning and sharp book retention"
Cohesion: 0.11
Nodes (9): _RecordingConn, _counts(), _older_than(), prune_table(), run_prune_odds(), test_prune_predicates_date_by_game_not_snapshot(), test_prune_rejects_keep_days_below_one(), test_prune_table_binds_the_prop_tables_carve_out_into_the_DELETE() (+1 more)

### Community 393 - "tests/test_sbr_loader.py"
Cohesion: 0.14
Nodes (3): _SqliteConnShim, _SqliteCursorShim, loader_conn()

### Community 397 - "mobile/scripts/ux_scan.mts"
Cohesion: 0.16
Nodes (18): Finding, Severity, changedFiles(), entitlementGate(), fontScaling(), fontSizeLiterals(), hexColors(), main() (+10 more)

### Community 398 - "NFL prop stat distributions"
Cohesion: 0.14
Nodes (6): TestBinaryMarket, TestCountDistributions, TestYardageDistribution, _nfl_prop_probs(), _art(), test_nb_head_changes_probs_only_when_nb_r_present()

### Community 4 - "Pre-game scoring and best-price decisions"
Cohesion: 0.01
Nodes (132): FakeConn, TestAmericanToImpliedProb, TestBuildPickLabel, TestConfidenceTier, TestMissingStarterGate, TestQuarterKelly, today_et(), margin_cover_prob() (+124 more)

### Community 408 - "NBA game projection availability state"
Cohesion: 0.16
Nodes (15): State, World, box_design(), box_guard(), box_rating(), f5_player_terms(), fit_box(), league_asof() (+7 more)

### Community 409 - "mobile/src/lib/otaUpdate.ts"
Cohesion: 0.20
Nodes (13): Calls, CheckState, CheckTrigger, UpdateOutcome, UpdatesApi, check(), fakeApi(), main() (+5 more)

### Community 41 - "tests/test_live_quote_staleness.py"
Cohesion: 0.04
Nodes (49): ScoreClock, _Conn, _Q, build_row(), _mark_written(), now_iso(), _publish_key(), quote_from_nfl_quotes() (+41 more)

### Community 410 - "Best game price selection tests"
Cohesion: 0.14
Nodes (12): FakeConn, _best_game_price(), test_a_better_price_at_a_different_total_is_not_the_same_bet(), test_a_better_price_at_the_same_total_wins(), test_an_unbettable_book_does_not_win_the_shop(), test_in_play_prices_are_excluded_from_best_line(), test_moneyline_has_no_line_to_match(), test_only_the_newest_snapshot_per_book_counts() (+4 more)

### Community 419 - "Player name matching"
Cohesion: 0.08
Nodes (18): FakeConn, drop_duplicate_box_ids(), season_fallback(), normalize_player_name(), resolve_feed_name(), test_a_player_listed_twice_in_the_box_keeps_the_id_the_plays_use(), test_an_id_no_game_matched_falls_back_to_its_team_season(), test_accented_roster_name_matches_the_flat_feed_name() (+10 more)

### Community 422 - "NBA prop settlement stats tests"
Cohesion: 0.12
Nodes (8): _SelectConn, test_a_missing_stat_is_none_not_zero(), test_a_turnovers_bet_on_a_player_who_played_settles_win_not_no_action(), test_combo_markets_are_mapped_to_helpers_and_only_the_nba_rule_uses_them(), test_double_double_matches_the_rule_it_replaced(), test_the_loader_carries_every_stat_a_market_settles_on(), test_the_loader_selects_turnovers(), _nba_prop_actual()

### Community 423 - "Pipeline report with per-section rollback"
Cohesion: 0.20
Nodes (4): _Conn, _rows(), test_a_failed_query_rolls_back(), test_one_broken_section_does_not_break_the_rest()

### Community 424 - "supabase/functions/_shared/discord.ts"
Cohesion: 0.20
Nodes (15): DiscordApiError, DiscordUser, RoleSyncResult, addAppRole(), addGuildMember(), botFetch(), expectOk(), isGuildMember() (+7 more)

### Community 43 - "Worker job queue validation tests"
Cohesion: 0.04
Nodes (43): _VoidConn, _posted_row(), _quiet(), _run_void(), _run_void_job(), test_a_failed_job_needs_a_new_key_to_rerun(), test_a_graded_pick_is_refused_not_rewritten(), test_a_pick_that_does_not_exist_is_reported_as_missing() (+35 more)

### Community 433 - "NFL in-play prop settlement tests"
Cohesion: 0.15
Nodes (14): _SqliteShim, _box(), conn(), _game(), _live_bet(), raw(), _row(), test_a_final_with_no_box_score_yet_waits() (+6 more)

### Community 438 - "NHL prop model wiring tests"
Cohesion: 0.14
Nodes (5): TestEveryLiveModelIsWiredEverywhere, TestTheGoalieFrame, TestTonightsRowIsATrainingRow, _log(), _players()

### Community 439 - "NBA totals card ledger and label tests"
Cohesion: 0.09
Nodes (17): Decision, TotalLuckBet, _Conn, _Cur, pick_label(), pick_rows(), _bet(), test_a_bet_under_the_ev_floor_is_refused() (+9 more)

### Community 44 - "scripts: build_nfl_live_leader_artifact + model"
Cohesion: 0.06
Nodes (36): Artifact, Decision, am_to_dec(), artifact_from_dict(), band_for(), decide(), leader_expected_margin(), load_artifact() (+28 more)

### Community 445 - "NFL CLV backtest and feature build"
Cohesion: 0.14
Nodes (9): ShrunkEnsemble, add_form(), build(), feature_columns(), market_features(), team_game_stats(), fmt(), main() (+1 more)

### Community 448 - "tests/test_discord_channel_probe.py"
Cohesion: 0.17
Nodes (7): _Resp, test_the_probe_covers_the_per_sport_live_channels(), test_the_probe_never_posts_and_never_returns_the_url(), test_the_probe_reports_the_channel_behind_each_sport(), _get(), test_two_sports_sharing_a_channel_are_flagged(), _job_discord_probe()

### Community 45 - "tests/test_nfl_prop_one_read_per_game.py"
Cohesion: 0.06
Nodes (28): _Conn, _Log, main(), publish(), publish_hour_missed(), publishable_games(), render(), _at() (+20 more)

### Community 451 - "Game outcome target tests"
Cohesion: 0.17
Nodes (5): TestComputeTarget, _compute_target(), test_a_push_yields_no_target(), test_spread_target_uses_the_home_relative_line(), test_totals_and_moneyline_targets()

### Community 46 - "Worker job queue and record corrections"
Cohesion: 0.02
Nodes (82): LedgerUnread, Conn, Ledger, _Result, derive_first_pitch(), backfill_savant_stats(), run_savant_ingestor(), run() (+74 more)

### Community 460 - "Discord recap restatement"
Cohesion: 0.03
Nodes (39): _Conn, _Conn, build_parser(), _date_is_over(), main(), post_backfill(), test_a_day_that_is_not_over_is_refused(), test_apply_calls_both_notifiers_for_that_date() (+31 more)

### Community 466 - "App sign-in, billing and paywall"
Cohesion: 0.03
Nodes (174): AccessState, useAccess, AuthState, AuthStatus, useAuth, useEntitlement, useSubscription, AuthCallback (+166 more)

### Community 469 - "Multi-book odds and pruning"
Cohesion: 0.07
Nodes (18): _OddsConn, _odds_query(), _prop_markets(), _source(), test_a_game_with_no_commence_time_keeps_every_row(), test_closing_line_reads_name_the_book(), test_draftkings_is_always_first_line_shop_book(), test_feature_engines_whitelist_draftkings() (+10 more)

### Community 470 - "NFL prop features and regrades"
Cohesion: 0.05
Nodes (37): LazyConnection, _add_features(), build_nfl_prop_scoring_rows(), build_nfl_prop_training_dataset(), _cols(), derived_targets(), _load(), _nfl_season() (+29 more)

### Community 471 - "tests/test_model_game_savepoint.py"
Cohesion: 0.15
Nodes (4): _PoisonConn, _games(), test_a_best_price_timeout_is_the_logged_error_and_the_next_lookup_runs(), test_a_model_sql_error_does_not_poison_the_next_model()

### Community 48 - "tests/test_calibration_watch.py"
Cohesion: 0.05
Nodes (16): _Conn, _Res, TestDormantLiveModels, TestItNeverDecides, TestRosterChanges, TestTheRun, TestVerdictChanges, TestVolumeShifts (+8 more)

### Community 482 - "tests/test_promote_external.py"
Cohesion: 0.16
Nodes (5): _Conn, promote_external(), test_external_promotion_refuses_a_map_that_does_not_transfer(), test_external_promotion_writes_only_the_promoted_columns(), test_the_scorer_reads_the_external_map_like_any_promoted_one()

### Community 486 - "Closing-line backfill job tests"
Cohesion: 0.15
Nodes (5): _Conn, _stub_backfill(), test_hard_cap_stops_a_nonempty_queue(), test_loops_until_a_pass_fills_nothing(), test_the_runner_opens_get_connection_and_calls_backfill_clv()

### Community 488 - "Batter prop log lookback tests"
Cohesion: 0.15
Nodes (7): _Rec, _log_sql(), test_batter_log_scan_is_pinned_to_the_lookback_not_the_catalog(), test_no_lineup_does_not_scan_the_log(), test_starter_log_inside_the_batter_loader_uses_the_same_floor(), test_the_batter_loop_hands_one_cache_to_every_model(), test_training_from_the_tables_first_season_still_reads_the_prior_year()

### Community 49 - "Failure alerter fake-connection tests"
Cohesion: 0.08
Nodes (12): FakeConn, TestDeliveryAndNoise, TestHealthCheckOnlyIsNotADirtyPass, TestItCannotBreakTheWorker, TestSilentJobs, TestWhatCountsAsAFailure, _clean_runs(), _posts() (+4 more)

### Community 490 - "NFL pick monitor join tests"
Cohesion: 0.16
Nodes (3): TestTheJoinKeyMatchesPicks, eval_row(), _picks_game_id()

### Community 493 - "Health skip budget streak tests"
Cohesion: 0.16
Nodes (6): FakeConn, test_a_check_never_seen_non_skipped_counts_its_whole_history(), test_a_check_skipped_only_today_is_not_counted_as_a_streak(), test_streak_counts_calendar_days_from_the_last_non_skipped_run(), test_the_streak_query_fails_open(), _skip_run_days()

### Community 499 - "NBA prop window plan tests"
Cohesion: 0.21
Nodes (9): _PlanConn, _game(), _plan(), _t(), test_a_projection_too_old_to_price_does_not_block_the_retry(), test_the_plan_owes_a_close_with_no_game_to_decide(), test_the_plan_projects_games_about_an_hour_out_and_any_in_the_window_never_projected(), test_the_plan_says_publish_while_any_game_is_near() (+1 more)

### Community 5 - "App screens and model catalog"
Cohesion: 0.02
Nodes (226): EquityPoint, ManualBet, ManualBetInput, ManualBetResult, BacktestPickRow, ChipGroup, ChipKey, FilterablePick (+218 more)

### Community 501 - "NFL prop market and local cache reads"
Cohesion: 0.02
Nodes (120): MarketBet, TestLocalCacheGuards, ladders(), ladders_or_empty(), norm_player_name(), activate(), available(), _manifest() (+112 more)

### Community 502 - "Price prefilter rollback tests"
Cohesion: 0.07
Nodes (14): _PoisonConn, _fmt_et_time(), get_conn(), query(), main(), _strip_outer_tx(), _event_index(), _games() (+6 more)

### Community 503 - "MLB in-play state alignment"
Cohesion: 0.22
Nodes (6): GameClock, _t(), test_before_first_pitch_and_after_last_play_are_not_priced(), test_between_pas_across_third_out_rolls_over_to_next_half(), test_mid_plate_appearance_is_that_pa_before_state(), test_plays_without_times_are_ignored()

### Community 504 - "Prop alternate line fetch tests"
Cohesion: 0.14
Nodes (9): _Resp, test_a_422_retries_without_the_alternates_before_going_dk_only(), fake_get(), test_a_422_with_no_alternates_still_takes_the_dk_only_retry(), fake_get(), test_a_rejected_football_alternate_chunk_costs_only_itself(), fake_get(), test_football_live_slate_requests_alternates_and_a_backfill_does_not() (+1 more)

### Community 51 - "NFL in-play gameday worker"
Cohesion: 0.05
Nodes (19): CreditBudgetExceeded, TeeRecorder, _Q, GamedayWorker, GameTracker, test_a_host_switch_is_alerted(), test_the_worker_self_checks_once_and_alerts_on_a_broken_feed(), test_a_one_sided_quote_is_skipped_rather_than_priced_on_raw_juice() (+11 more)

### Community 511 - "Prop odds next-day lookahead"
Cohesion: 0.17
Nodes (4): TestTheOddsFetchReachesTomorrow, TestTheScorerReachesTomorrow, _get_events(), _events_src()

### Community 516 - "NHL blocked shots settlement shim"
Cohesion: 0.12
Nodes (10): _Shim, TestItSettlesAsAPropNotAsAGame, TestSettlement, _bet(), db(), _played(), _result(), test_slate_only_holds_games_that_have_not_started() (+2 more)

### Community 517 - "Pipeline watch job"
Cohesion: 0.04
Nodes (40): _Conn, collect(), test_a_clean_pass_produces_no_finding(), test_a_clean_run_still_posts(), test_a_confirmed_post_is_ledgered_so_the_run_can_be_verified(), test_a_failed_ledger_does_not_lose_the_report(), execute(), test_a_failed_query_rolls_back_and_does_not_sink_the_run() (+32 more)

### Community 518 - "Weather forecast hour lookup"
Cohesion: 0.08
Nodes (12): _Resp, TestTheHourIsTheGamesOwn, TestTheRequestCoversTheTargetHour, TestTheStoreReadsTheStartTime, _celsius_to_f(), fetch_and_store_weather_for_date(), _fetch_open_meteo(), _is_dome_game() (+4 more)

### Community 52 - "tests/test_best_line_live.py"
Cohesion: 0.04
Nodes (44): _FakeConn, _best_live_price(), _best_live_side(), _live_book_quotes(), _live_quote_is_on_offer(), best_takeable_quote(), _ev(), _live_pick() (+36 more)

### Community 520 - "App bankroll storage"
Cohesion: 0.23
Nodes (12): KeyValueStore, check(), eq(), fakeStore(), interleaving(), slowStore(), storage(), createBankrollStore() (+4 more)

### Community 533 - "NFL wind card book filter tests"
Cohesion: 0.13
Nodes (4): TestTheCardFilters, TestTheListIsShared, _attach(), _quote()

### Community 539 - "NFL prop local odds cache tests"
Cohesion: 0.33
Nodes (4): TestLocalOddsCache, _odds_from_frame(), _odds_frame(), test_a_one_way_market_stays_one_way_through_the_cache()

### Community 54 - "tests/test_void_picks.py"
Cohesion: 0.05
Nodes (18): _FakeConn, TestAPostedSignalIsLocked, TestAPostedVoidAnnouncesAfterCommit, TestTheToolRefusesToMatchEverything, TestVoidingAPostedPickIsAnExplicitOptIn, TestWhatMayBeVoided, TestWhatTheVoidWrites, announce_posted_voids() (+10 more)

### Community 544 - "NCAAF starter-out search dataset"
Cohesion: 0.16
Nodes (8): LabelSet, build_label_set(), _fetch_lines(), _fetch_raw(), opener_coverage(), _pick_provider(), provider_continuity(), main()

### Community 549 - "NHL prop card limits and insert-once"
Cohesion: 0.16
Nodes (4): TestInsertOnce, TestTheLimitPerGame, limit_per_game(), publish()

### Community 55 - "College football game-day feeds"
Cohesion: 0.05
Nodes (34): LiveOddsFeed, GameContext, _Conn, _Result, school(), fetch_scoreboard_cfbd(), fetch_team_ids(), _headers() (+26 more)

### Community 550 - "NFL prop odds ingest and backfill"
Cohesion: 0.06
Nodes (31): _Conn, _Cur, backfill_nfl_prop_odds(), backfilled_dates(), census_books(), _credits_used(), _event_props(), _fetch_slice() (+23 more)

### Community 56 - "tests/test_daily_retry.py"
Cohesion: 0.06
Nodes (42): _Conn, _Cursor, _FrozenDatetime, DailyRun, _aborted(), _aborted_row(), _ok(), _ok_row() (+34 more)

### Community 561 - "Prop no-bet rows kept to tip-off"
Cohesion: 0.21
Nodes (6): _Clock, _fake_datetime_class(), _game(), _iso(), test_the_poller_keeps_prop_no_bet_rows_the_refresh_pass_still_clears(), _wire()

### Community 567 - "Pass completion health tests"
Cohesion: 0.16
Nodes (3): TestPassCompletion, TestPassSteps, _add_run()

### Community 57 - "tests/test_live_book_move_guard.py"
Cohesion: 0.07
Nodes (39): BookMoveClock, _Unset, _MlbConn, american_to_implied(), _at(), _delaware_ctx(), _dk(), _iso() (+31 more)

### Community 576 - "tests/test_weekly_catch_up.py"
Cohesion: 0.15
Nodes (3): _Conn, _Cursor, test_a_failing_savant_refresh_does_not_cost_the_calibration_its_catch_up()

### Community 58 - "Discord live and best-price fields"
Cohesion: 0.04
Nodes (37): _FakeConn, _StampConn, _sig(), test_a_strictly_better_book_becomes_the_headline(), test_an_equal_or_worse_price_never_replaces_draftkings(), test_draftkings_winning_its_own_shop_is_published_as_draftkings(), test_every_pre_game_producer_computes_good_to(), test_good_to_is_published_when_the_producer_supplies_it() (+29 more)

### Community 582 - "Prop odds book update-time tests"
Cohesion: 0.26
Nodes (6): _Conn, _parse(), test_a_row_built_without_the_key_still_inserts_as_null(), test_no_clock_anywhere_is_none_not_our_fetch_time(), test_the_column_is_added_only_when_the_catalog_lacks_it(), test_the_markets_own_clock_is_stored_else_the_books()

### Community 583 - "NFL pick monitor"
Cohesion: 0.15
Nodes (10): TestClassify, TestImmutabilityContract, TestLatestPerPick, classify(), _f(), latest_per_pick(), main(), monitor() (+2 more)

### Community 584 - "Multi-book odds fetch fallback tests"
Cohesion: 0.20
Nodes (7): _Resp, test_a_rejected_book_list_falls_back_to_the_decision_book(), _get(), test_the_fallback_does_not_recurse_forever(), _get(), test_the_per_event_fetch_asks_for_every_book(), _get()

### Community 59 - "NFL live prop assessment and odds client"
Cohesion: 0.03
Nodes (64): OddsAPIClient, SnapshotResult, Puller, _key(), _ledger_bump(), _ledger_read(), ledger_status(), _ledger_write() (+56 more)

### Community 590 - "DraftKings direct feed matching"
Cohesion: 0.24
Nodes (6): _Conn, _game_id_for(), test_a_unique_match_resolves(), test_an_ambiguous_event_name_writes_nothing(), test_an_event_name_with_no_at_sign_is_refused(), test_an_unmatched_event_name_writes_nothing()

### Community 595 - "NBA box score player resolver"
Cohesion: 0.17
Nodes (6): PlayerResolver, build_log_rows(), fallback_id(), test_a_rookie_keeps_one_id_across_games(), test_the_fallback_cannot_collide_with_an_nba_id(), test_two_box_rows_never_share_an_id()

### Community 6 - "App queries for today's picks"
Cohesion: 0.02
Nodes (175): Props, Props, Props, Props, FighterSide, Props, Props, Args (+167 more)

### Community 601 - "College football state fetch tests"
Cohesion: 0.24
Nodes (6): _Ctx, _ev(), test_a_single_failed_summary_does_not_drop_the_other_games(), test_cfbd_mode_does_no_per_game_fetching(), test_espn_states_are_fetched_in_parallel_and_stay_aligned(), test_unknown_matchups_never_cost_a_fetch()

### Community 611 - "supabase/functions/revenuecat-webhook/index.ts"
Cohesion: 0.22
Nodes (3): RcEvent, admin, PRODUCT_TO_PLAN

### Community 613 - "supabase/functions/whop-webhook/index.ts"
Cohesion: 0.25
Nodes (4): WhopMembership, signatureValid(), timingSafeEqual(), admin

### Community 621 - "Health check database shim tests"
Cohesion: 0.15
Nodes (4): _FrozenDatetime, _Shim, db(), mlb_wired()

### Community 64 - "NFL in-play pricing engine and backtest"
Cohesion: 0.02
Nodes (87): ScoreDistribution, _cluster_bootstrap(), evaluate(), main(), report(), align_states(), build_team_map(), _game_index() (+79 more)

### Community 642 - "Stale pre-game price tests"
Cohesion: 0.20
Nodes (3): _OddsConn, test_a_started_game_reads_its_last_pre_game_row_whatever_its_age(), test_the_feature_row_and_the_opener_read_the_same_bounded_price()

### Community 643 - "Prop grading timeout tests"
Cohesion: 0.25
Nodes (4): GradeConn, test_a_non_timeout_prop_error_rolls_back_and_raises(), test_a_timed_out_prop_date_does_not_abort_the_next(), settle()

### Community 644 - "Settlement self-heal test shim"
Cohesion: 0.22
Nodes (3): _SqliteShim, conn(), raw()

### Community 645 - "App bankroll unit percent hook"
Cohesion: 0.32
Nodes (7): BankrollSettings, useBankroll(), canStepUnitPct(), sanitizeUnitPct(), stepUnitPct(), store, BANKROLL_DEFAULTS

### Community 651 - "Model calibration sweep tests"
Cohesion: 0.05
Nodes (17): _ProbeConn, _rows(), test_a_prob_only_sweep_uses_only_the_probability_dimension(), test_column_migrations_run_every_pipeline_pass(), test_home_runs_are_no_longer_exempt_from_pausing(), test_plateau_is_computed_within_the_narrow_grid(), test_the_agent_changes_nothing_on_its_own(), test_the_agent_sweeps_every_registered_model_except_live_ones() (+9 more)

### Community 653 - "Model quality database end-to-end test"
Cohesion: 0.22
Nodes (3): _Shim, _insert_open_bet(), test_run_persists_all_unders_fade_slate_as_crit()

### Community 662 - "Signal publish-on-write tests"
Cohesion: 0.06
Nodes (18): _Conn, _body(), _row(), _surfaces(), _make(), test_a_broken_webhook_does_not_suppress_the_push(), test_a_failed_capture_still_delivers(), test_a_publish_failure_does_not_kill_the_tick() (+10 more)

### Community 668 - "NFL prop grading and kickoff gate"
Cohesion: 0.18
Nodes (5): TestKickoffGate, TestMarketGrading, _as_dt(), grade(), season_of()

### Community 67 - "tests/test_game_market_gate.py"
Cohesion: 0.06
Nodes (49): GateVerdict, MarketBookend, PublicSplits, apply_to_picks(), _as_float(), bookend_from_odds(), evaluate(), fair_prob() (+41 more)

### Community 671 - "NFL prop pull market list tests"
Cohesion: 0.22
Nodes (3): TestIngestEventsDoesNotShadowItsMarkets, test_live_prop_pull_asks_for_the_sharp_book(), fake_event_props()

### Community 674 - "NBA public splits quality backfill"
Cohesion: 0.11
Nodes (9): _CountingConn, backfill_quality(), quality_backfill_statements(), quality_flag(), test_an_existing_table_gets_the_quality_column(), test_the_backfill_adds_the_column_and_commits_once(), test_the_backfill_rolls_back_when_a_count_is_not_what_was_measured(), test_the_quality_rule_puts_reversed_ahead_of_late() (+1 more)

### Community 678 - "Fight orientation best-line tests"
Cohesion: 0.18
Nodes (4): TwoOrientationConn, test_a_non_ufc_game_is_not_looked_up_twice(), test_ufc_h2h_resolves_the_sibling_orientation_and_flips_the_side(), test_ufc_totals_keep_their_side_on_the_sibling()

### Community 679 - "NFL prop odds loader tests"
Cohesion: 0.24
Nodes (3): TestPropOddsLoader, _Conn, _Cur

### Community 68 - "NBA second-model prop study"
Cohesion: 0.05
Nodes (49): Shape, alias_key(), _flat(), initial_key(), _initial_of_full(), match_names(), name_key(), token_key() (+41 more)

### Community 689 - "Paused bet bankroll tests"
Cohesion: 0.18
Nodes (3): _Capture, test_a_paused_settled_bet_never_moves_the_kelly_bankroll(), test_todays_standing_bets_ignore_a_paused_row()

### Community 69 - "tests/test_pick_integrity.py"
Cohesion: 0.04
Nodes (41): _Conn, _Shim, _add_pick(), discord_sent(), _health(), health_db(), test_a_label_may_not_name_a_market_the_pick_does_not_settle_on(), test_a_label_naming_the_other_team_is_refused() (+33 more)

### Community 696 - "NBA injury report date scope"
Cohesion: 0.33
Nodes (3): _DatesConn, scope_dates(), test_scope_is_every_game_date_and_the_day_before_newest_first()

### Community 699 - "Threshold review table setup tests"
Cohesion: 0.08
Nodes (8): _DdlConn, _DdlRes, _board_markets(), table(), test_the_mlb_board_and_the_mlb_pull_are_one_set(), test_a_failed_lock_down_does_not_lose_the_table(), test_ensure_schema_commits_the_tables_it_creates(), test_the_tables_are_locked_down_at_the_create_site()

### Community 7 - "Database calls from tracking and scoring"
Cohesion: 0.01
Nodes (155): DBConnection, TestAmericanToDecimalScorer, call_in_savepoint(), connection_lost(), _go(), rollback_savepoint(), statement_timeout(), _upsert_savant_stats() (+147 more)

### Community 70 - "tests/test_record_one_pick_per_event.py"
Cohesion: 0.04
Nodes (47): _CaptureConn, _RecordingConn, duplicate_copy_exclusion_sql(), _code(), _copy_for_node(), _fn(), _node(), _read() (+39 more)

### Community 73 - "nfl/live_model/tests: test_props + props"
Cohesion: 0.07
Nodes (36): PropProjection, GameState, PlayerState, _accrued(), _count(), detect_inactive(), price_over(), project() (+28 more)

### Community 731 - "Database setup and schema split"
Cohesion: 0.17
Nodes (6): TestRealSchema, TestSplitter, _load_postgres_schema(), setup_database(), _split_sql_statements(), setup_database()

### Community 732 - "NFL prop odds game matching"
Cohesion: 0.29
Nodes (3): TestResolveGameId, resolve_nfl_game_id(), resolve()

### Community 77 - "tests/test_wnba_prop_market.py"
Cohesion: 0.06
Nodes (30): _QuoteConn, apply_price_floor(), norm_name(), pick_rows(), player_ids(), publish(), render(), run_card() (+22 more)

### Community 78 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.07
Nodes (20): _After, _Conn, _LockConn, _RaceConn, TestFlexedKickoffRefreshes, TestLockSurvivesNothing, TestNoneRowBesideABetIsCleared, TestNoneRowNeverLocks (+12 more)

### Community 79 - "NHL period and team totals model"
Cohesion: 0.07
Nodes (36): Market, build_p1_frame(), build_team_frame(), day_interval(), _ew(), fit(), game_means(), _implied_vec() (+28 more)

### Community 8 - "App player stats and opponent splits"
Cohesion: 0.02
Nodes (229): Props, PlayerNextGame, Section, Args, PlayerStatKey, HitMode, HitSelection, HitDirection (+221 more)

### Community 80 - "Global EV floor tests"
Cohesion: 0.06
Nodes (28): Gate, expected_value(), min_ev_for(), test_ncaaf_live_ev_floor_is_wired_from_config(), pick_rows(), _built(), floor_030(), identity_maps() (+20 more)

### Community 83 - "tests/test_nhl_props.py"
Cohesion: 0.07
Nodes (14): _Shim, TestSettlement, TestTheDistribution, _Conn, _bet(), db(), _in_goal(), _result() (+6 more)

### Community 84 - "Publish key identity and push alerts"
Cohesion: 0.02
Nodes (96): _Conn, _KeyConn, paused_row_exclusion_sql(), test_a_real_pause_is_not_logged_as_stale(), execute(), test_empty_set_errors_when_a_stale_pause_flag_hides_bets(), execute(), test_the_restate_producer_keeps_the_first_bet_only() (+88 more)

### Community 849 - "NFL wind forecast and lead"
Cohesion: 0.03
Nodes (62): OpenMeteoError, Bet, bettable_books(), dump_eval_rows(), coverage_check(), expected_true_wind(), fetch_era5(), fetch_issued_forecasts() (+54 more)

### Community 85 - "tests/test_recap_retries_a_skipped_day.py"
Cohesion: 0.06
Nodes (25): _LiteConn, World, _add_pick(), _grade(), _lite(), _schema(), test_a_day_with_nothing_counting_posts_nothing_and_logs_nothing(), test_a_failed_receipt_never_reposts_the_day() (+17 more)

### Community 851 - "NBA odds archive rerun safety"
Cohesion: 0.18
Nodes (5): _Conn, load(), stored_keys(), test_a_rerun_writes_nothing_already_stored(), test_stored_rows_are_read_by_game_id_not_by_scanning_for_the_source()

### Community 857 - "Picks email rendering"
Cohesion: 0.46
Nodes (6): Pick, _fmt_edge(), _fmt_odds(), main(), _pick_card(), render_email()

### Community 9 - "Probability calibration fitting tests"
Cohesion: 0.03
Nodes (54): _FakeConn, _SchemaRecordingConn, apply_calibration(), demote(), ensure_schema(), _era_start(), fit_model(), fit_offset() (+46 more)

### Community 90 - "App matchup grades and stats pills"
Cohesion: 0.07
Nodes (46): MatchupGrade, MatchupInfo, TonightMatchupRow, check(), fakeServer(), main(), read(), check() (+38 more)

### Community 91 - "App book prices and closing-line labels"
Cohesion: 0.04
Nodes (49): clvBetQuote, ClvBetRow, ClvBookRow, derive(), fromLabel(), labelBook(), alone, dkUser (+41 more)

### Community 92 - "tests/test_ncaaf_prop_odds.py"
Cohesion: 0.05
Nodes (27): _Conn, _Resp, _market_chunks(), _football_map(), resolver(), scope(), test_a_book_we_did_not_ask_for_is_never_written(), test_a_day_with_no_college_games_spends_nothing() (+19 more)

### Community 93 - "MLB totals public fade tests"
Cohesion: 0.04
Nodes (70): PublicFadeBet, _EmptyConn, _better_under(), composite_score(), edge_floor(), estimated_edge(), find_fade_bets(), is_pre_commence() (+62 more)

### Community 94 - "NFL prop verdict tests"
Cohesion: 0.04
Nodes (29): TestNormaliseName, TestSnapRows, TestVerdict, TestYesNoMarkets, _verdict(), test_a_half_line_market_priced_to_its_own_skew_is_not_flagged(), test_a_sharp_reference_is_never_a_book_we_bet(), test_a_targeted_backfill_never_substitutes_draftkings() (+21 more)

### Community 95 - "tests/test_ncaaf_pbp_store.py"
Cohesion: 0.07
Nodes (24): _Conn, _extremes(), fetch_season(), _get(), load_season_from_db(), main(), observed_ranges(), pull_season() (+16 more)

### Community 96 - "tests/test_heartbeat_watchdog.py"
Cohesion: 0.08
Nodes (24): _FakeConn, _FakeCursor, _break_db(), sink(), test_a_failed_post_does_not_start_the_throttle(), test_a_healthy_start_never_announces_a_recovery(), test_a_returning_outage_alerts_again_immediately(), test_a_silent_failure_alerter_is_caught_by_the_watchdog() (+16 more)

### Community 97 - "Game injury veto gate and tests"
Cohesion: 0.05
Nodes (48): _InjConn, _InjConn, apply_to_picks(), _goalie_names(), _pitcher_names(), player_matches_veto(), relevant_players(), _star_names() (+40 more)

### Community 569 - "Pipeline run ledger"
Cohesion: 0.20
Nodes (8): _abort_orphans(), abort_prior_refresh_orphans(), _boot_cutoff(), _ensure_table(), finish_run(), main(), _now(), start_run()

### Community 102 - "scripts/nfl_edge_live_rush_pace.py"
Cohesion: 0.18
Nodes (26): _asof(), boot_p(), build_state(), first(), grade(), initial_last(), load_pbp(), main() (+18 more)

### Community 103 - "NBA prop projection tests"
Cohesion: 0.08
Nodes (27): test_the_probe_writes_nothing(), _art(), _committed(), _proj(), _q(), _run(), test_a_book_hanging_two_lines_for_one_player_is_refused(), test_a_decision_with_no_bet_is_still_a_decision() (+19 more)

### Community 104 - "Live monitor probe and store"
Cohesion: 0.08
Nodes (26): _drain(), _enqueue(), _flush_on_exit(), install(), instrumented(), _now(), _patch_curl_cffi(), instrumented() (+18 more)

### Community 105 - "NBA game market feature study"
Cohesion: 0.06
Nodes (37): cache_for(), check_cells(), combine_times(), f2_cells(), f2_point(), f6a_placebo(), f6a_point(), f6a_strength() (+29 more)

### Community 107 - "tests/test_prop_calibrated_decision.py"
Cohesion: 0.06
Nodes (30): apply_prop_daily_cap(), _claimed_ev(), dedupe_player_props(), _downgrade(), _is_paused_row(), _bet(), _identity_cal(), _prop() (+22 more)

### Community 108 - "NCAAF in-play quote serving"
Cohesion: 0.06
Nodes (22): correct_for_pregame(), _load_pregame_calibration(), pregame_dog_points(), _real_artifact(), test_a_big_dog_is_marked_down_hard(), test_a_corrupt_artifact_leaves_the_probability_alone(), test_a_favourite_is_marked_up(), test_a_missing_artifact_leaves_the_probability_alone() (+14 more)

### Community 109 - "Schema guard and table lock-down"
Cohesion: 0.09
Nodes (14): lock_down(), _fetchone(), schema_is_current(), discover(), fetch_all(), _get_image(), main(), _original_size() (+6 more)

### Community 11 - "NFL prop information and stacking studies"
Cohesion: 0.07
Nodes (30): closing_prices(), devig(), ecdf_p_over(), main(), main(), bets(), design(), main() (+22 more)

### Community 110 - "tests/test_mobile_line_movement.py"
Cohesion: 0.08
Nodes (27): _fn(), _read(), _run(), test_a_cut_table_keeps_the_pick_and_says_what_it_covers(), test_a_cut_window_keeps_the_pick_row_on_the_8_row_table(), test_a_pick_made_after_the_cards_start_never_reads_since_your_pick(), test_after_the_start_the_verdict_is_not_graded(), test_an_old_snapshot_is_not_the_price_at_the_pick() (+19 more)

### Community 111 - "tests/test_live_calibration.py"
Cohesion: 0.07
Nodes (31): pick(), test_a_peak_with_no_plateau_anywhere_is_labelled_as_one(), test_a_prob_cut_and_an_ev_cut_select_different_picks(), test_calibration_also_scores_ev_against_realised_roi(), test_calibration_is_empty_rather_than_wrong_with_nothing_settled(), test_calibration_reports_the_gap_between_claim_and_reality(), test_expected_value_matches_the_hand_calculation(), test_expected_value_refuses_a_missing_or_zero_price() (+23 more)

### Community 112 - "NFL in-play flow validation tests"
Cohesion: 0.13
Nodes (22): pseudo_clv(), _bet(), _preds(), _quote(), _quotes(), synthetic(), test_a_far_away_kickoff_is_a_different_season(), test_a_push_is_not_a_loss() (+14 more)

### Community 117 - "NBA lineup stint derivation tests"
Cohesion: 0.08
Nodes (45): order_plays(), _blowout_q4(), derive(), dreb(), _dup_game(), end_period(), five_game(), make2() (+37 more)

### Community 119 - "tests/test_ncaaf_live_notify.py"
Cohesion: 0.05
Nodes (18): _load_write_picks(), _restore_stubbed_modules(), test_a_caller_supplied_connection_is_not_closed_by_the_write(), test_a_failing_notifier_never_breaks_pricing(), test_a_full_slate_announces_once(), test_a_live_bet_notifies_push_and_discord(), test_a_locked_lane_is_not_rewritten(), test_a_locked_lane_keeps_notifying_after_the_engine_stops_betting() (+10 more)

### Community 126 - "monitoring/store.py"
Cohesion: 0.10
Nodes (23): meta(), ops(), snapshot(), api_rollup(), call_timeline(), calls_since(), community(), scalar() (+15 more)

### Community 128 - "tests/test_settled_record_is_immutable.py"
Cohesion: 0.05
Nodes (23): _code(), test_a_dedicated_live_lane_still_counts_and_a_pre_game_in_play_pick_does_not(), test_a_paused_model_is_not_an_excluded_model(), test_a_voided_pick_is_still_out_of_the_record(), test_both_published_views_keep_the_live_date_gate(), test_both_rules_name_the_two_exits_and_not_the_paused_flag(), test_both_views_are_redefined_by_name(), test_every_explicit_exclusion_names_who_asked_for_it() (+15 more)

### Community 130 - "features/golf_feature_engine.py"
Cohesion: 0.07
Nodes (30): assemble_player_features(), _avg_finish(), build_bulk_golf_lookups(), build_golf_scoring_features(), build_golf_training_dataset(), compute_golf_target(), compute_matchup_target(), _event_finishes() (+22 more)

### Community 132 - "ncaaf_live/tests/test_states.py"
Cohesion: 0.08
Nodes (33): main(), build_states(), _classify(), classify_report(), _detect_score_convention(), load_pbp(), load_platform_games(), pace_report() (+25 more)

### Community 133 - "tests/test_bovada_feed.py"
Cohesion: 0.10
Nodes (31): _american(), _complete(), _num(), parse_coupon(), _row_for(), _seen_key(), _stamp(), _coupon() (+23 more)

### Community 134 - "tests/test_market_movement.py"
Cohesion: 0.07
Nodes (26): american_to_prob(), build_market_features(), _is_full_game_snap(), _latest_two_sided(), _snap_sort_key(), _snapshot_type_rank(), _unique_ordered(), _s() (+18 more)

### Community 136 - "NCAAF cross-book opener rule tests"
Cohesion: 0.07
Nodes (25): _minutes_apart(), build_artifact(), build_band_artifact(), _branch(), test_absent_ceiling_means_unbounded(), test_artifact_shape(), test_band_ceiling_is_enforced_in_the_scorer(), test_band_volumes_sum_to_the_single_gate_backtest() (+17 more)

### Community 138 - "tests/test_paused_keeps_real_verdict.py"
Cohesion: 0.07
Nodes (33): _bet(), _bodies(), _code(), _fn(), _pause(), _prop(), _rules(), _sql_of() (+25 more)

### Community 139 - "NFL in-play edge studies by season"
Cohesion: 0.15
Nodes (26): books_per_snapshot(), families(), finalize_states(), fit_models(), fmt(), h2_accuracy(), h3_accuracy(), hold_table() (+18 more)

### Community 147 - "scripts/nfl_edge_extreme_props.py"
Cohesion: 0.12
Nodes (29): actuals(), add_modes(), bar(), candidates(), cell(), decision_boards(), devig(), fit_holdout() (+21 more)

### Community 148 - "scripts/nfl_edge_settlement.py"
Cohesion: 0.14
Nodes (30): add_test(), attach(), banner(), bh(), board(), boot_draws(), cell(), choose() (+22 more)

### Community 149 - "NBA totals overs rule tests"
Cohesion: 0.06
Nodes (34): quote_frame(), _complete_case(), _decide(), _et(), _fires(), _refresh_jobs(), _rows(), _season() (+26 more)

### Community 15 - "X publisher"
Cohesion: 0.02
Nodes (90): _x_api_profile(), test_clv_counts_only_picks_that_have_a_closing_price(), test_the_record_restatement_and_the_slate_restatement_are_separate(), _pick(), test_a_pick_with_no_alternative_falls_back_to_draftkings(), test_every_offerable_book_has_a_human_name_on_both_surfaces(), test_the_free_card_names_the_cheaper_book(), test_the_free_card_query_reads_the_columns_it_renders() (+82 more)

### Community 153 - "tests/test_agents_contract.py"
Cohesion: 0.05
Nodes (20): _labelled_retired(), test_blocked_items_are_marked_so_the_agent_skips_them(), test_every_backlog_item_is_a_checkbox(), test_neither_agent_may_change_a_model_threshold(), test_the_agents_are_findable_from_the_file_every_session_reads(), test_the_backlog_does_not_promise_an_agent_that_no_longer_runs(), test_the_backlog_exists_and_has_items(), test_the_contract_documents_every_agent_by_name() (+12 more)

### Community 157 - "In-play scorer and inning gate replay"
Cohesion: 0.03
Nodes (78): build_mlb_game_features(), build_live_state_row(), build_live_training_dataset(), expected_value(), _latest_live_state(), _live_bets_today(), _make_live_pick(), _pregame_features() (+70 more)

### Community 158 - "Best line and best-price decision tests"
Cohesion: 0.09
Nodes (16): _best_of(), _same_line(), _source(), test_a_book_can_only_be_offered_if_it_is_also_fetched(), test_best_fields_are_all_null_when_no_book_priced_the_side(), test_best_fields_report_the_edge_at_the_price_offered(), test_best_of_ignores_books_with_no_price(), test_best_of_picks_the_highest_payout_across_the_sign_flip() (+8 more)

### Community 159 - "WNBA results and stats ingestors"
Cohesion: 0.08
Nodes (33): build_log_row(), _core_athlete(), _deref(), _et_date(), _fetch_core_box_players(), _fetch_core_games(), _fetch_scoreboard(), _fetch_summary() (+25 more)

### Community 16 - "Daily pipeline runner and push notifier"
Cohesion: 0.02
Nodes (93): _run_migrations(), run_ncaaf_stats_ingestor(), run_bullpen_ingestor(), run_nfl_results_ingestor(), run_player_news_ingestor(), run_nba_prop_odds_ingestor(), run_wnba_prop_odds_ingestor(), refresh_team_board_cache() (+85 more)

### Community 166 - "Prop box score backfill"
Cohesion: 0.13
Nodes (22): _call_fill(), _cooled(), _day(), _default_mlb(), _default_nfl(), _default_wnba(), _drop_logged(), _fill_cooled() (+14 more)

### Community 167 - "scripts/nfl_preflight.py"
Cohesion: 0.20
Nodes (16): check(), check_cards_run(), check_config_gates(), check_cost(), check_data(), data_check(), check_import_shadowing(), check_lock_semantics() (+8 more)

### Community 168 - "Push notifier and delivery tickets"
Cohesion: 0.22
Nodes (10): _msgs(), test_a_credentials_failure_disables_nobody(), test_a_request_level_rejection_accepts_nothing(), test_a_retired_device_is_named_for_disabling(), test_a_single_message_reply_may_be_a_bare_object(), test_a_ticket_that_is_not_an_object_is_not_a_delivery(), test_an_error_ticket_is_not_counted_as_sent(), test_an_unpairable_reply_counts_nothing_and_disables_nothing() (+2 more)

### Community 169 - "NFL expected value stake engine"
Cohesion: 0.09
Nodes (23): american_to_decimal(), cover_probs(), ev_per_unit(), fit_margin_pmf(), kelly_fraction(), margin_pmf_for(), add_model_mu(), load() (+15 more)

### Community 17 - "NFL quarterback wind edge study"
Cohesion: 0.10
Nodes (43): band_table(), bh(), build_priced(), decisions_2026(), decisions_hist(), era5_hourly(), fc_at_decision(), fetch_2026() (+35 more)

### Community 173 - "tests/test_decide_on_calibrated.py"
Cohesion: 0.06
Nodes (19): _pick(), _pick_at(), test_a_calibrated_cut_is_paired_with_a_calibrated_decision(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(), test_a_genuinely_big_edge_still_fires_after_calibration(), test_a_hot_model_no_longer_fires_the_marginal_bet(), test_a_model_on_a_calibrated_cut_is_not_paused(), test_a_paused_model_never_fires_regardless() (+11 more)

### Community 175 - "tests/test_dk_direct_feed.py"
Cohesion: 0.13
Nodes (16): _row_for(), _seen_key(), _rec(), test_a_line_move_is_a_new_quote(), test_a_market_we_do_not_understand_is_dropped_not_guessed(), test_a_price_move_is_a_new_quote(), test_a_priced_market_with_no_line_is_dropped(), test_a_run_that_writes_nothing_is_not_reported_as_success() (+8 more)

### Community 176 - "NBA prop projection lab"
Cohesion: 0.10
Nodes (46): implied(), bars(), bh_read(), blind(), boot(), by(), cal_ab(), candidates() (+38 more)

### Community 180 - "NBA totals overs shooting luck model"
Cohesion: 0.08
Nodes (24): as_of_ratings(), _before(), decide(), f4_projections(), f4_signal(), is_last_look(), _known_team(), lead_minutes() (+16 more)

### Community 182 - "tests/test_model_artifacts_load.py"
Cohesion: 0.09
Nodes (17): _git(), _gitignore_keep_pkls(), _ignored(), _manifest_keep_pkls(), _newest_per_model(), test_a_path_that_is_not_ignored_is_not_reported(), test_a_superseded_timestamped_pkl_is_ignored(), test_an_ignored_path_comes_back_byte_identical() (+9 more)

### Community 185 - "scripts/game_line_market_sweep.py"
Cohesion: 0.08
Nodes (22): _by_month(), collect_picks(), devig(), _gap_seconds(), grade(), implied(), iter_months(), load() (+14 more)

### Community 187 - "Push notification deep link tests"
Cohesion: 0.09
Nodes (19): _code(), _py_version(), _read(), test_an_unreadable_payload_routes_nowhere_rather_than_guessing(), test_both_halves_pin_the_same_payload_version(), test_every_expo_message_carries_a_data_payload(), test_every_summary_producer_can_deep_link_a_single_pick(), test_every_type_the_sender_emits_is_one_the_app_can_route() (+11 more)

### Community 188 - "tests/test_pass_instrumentation.py"
Cohesion: 0.06
Nodes (11): test_a_dead_database_does_not_fail_the_step(), test_a_raised_failure_still_records_the_exception(), test_a_step_that_raises_is_still_TIMED(), test_a_step_that_raises_still_raises(), boom(), test_a_step_that_returns_false_records_a_REASON(), test_a_successful_step_records_a_duration(), test_every_step_name_in_the_dispatch_table_is_reachable() (+3 more)

### Community 190 - "tests/test_db_adapt_sql.py"
Cohesion: 0.09
Nodes (23): _adapt_sql(), _convert_params(), _convert_params_outside_literals(), _named(), test_a_block_comment_is_skipped_too(), test_a_colon_word_inside_a_comment_is_not_a_placeholder(), test_a_dash_dash_inside_a_literal_is_data_not_a_comment(), test_a_line_comment_ends_at_the_newline() (+15 more)

### Community 191 - "Sharp-price de-vig helpers"
Cohesion: 0.08
Nodes (20): find_bets(), _q(), test_a_different_line_is_never_compared(), test_a_market_under_the_coverage_floor_is_excluded(), test_a_prop_the_sharp_book_did_not_price_is_counted_not_traded(), test_agreement_produces_no_bet(), test_an_equal_line_with_a_real_disagreement_is_a_bet(), test_devig_removes_the_hold_symmetrically() (+12 more)

### Community 194 - "NFL in-play 2025 edge report"
Cohesion: 0.14
Nodes (22): attach_games(), attach_state(), diagnostics(), dispersion(), fit_totals_margin(), h2_accuracy(), h3_accuracy(), h4() (+14 more)

### Community 195 - "tests/test_mobile_contrast_tokens.py"
Cohesion: 0.13
Nodes (29): _code_lines(), _ionicon_colors(), _lum(), _over(), _ratio(), _read(), _rgb(), test_badge_glyph_tracks_dynamic_type() (+21 more)

### Community 197 - "NBA box score stats ingestor"
Cohesion: 0.09
Nodes (23): fill_missing_game_logs(), backfill_nba_stats(), _build_game_id(), _build_game_rows(), _build_player_log_rows(), _build_team_stat_rows(), _fetch_league_game_log(), ingest_nba_game_log_for_date() (+15 more)

### Community 20 - "Threshold and EV floor sweeps"
Cohesion: 0.06
Nodes (36): load_calibrations(), analyse(), split(), _basis(), _cut(), fetch(), analyse(), _apply_price_floor() (+28 more)

### Community 200 - "Live monitor cache"
Cohesion: 0.17
Nodes (9): age(), cached(), clear(), test_cache_raises_when_it_has_nothing_to_fall_back_on(), test_cache_reports_age(), test_cache_serves_stale_rather_than_failing(), boom(), test_cache_serves_within_ttl_and_recomputes_after() (+1 more)

### Community 201 - "NBA second game line move tests"
Cohesion: 0.06
Nodes (39): _priced_season(), _q(), _sched(), _season_games(), _signal(), _split(), _stub_main(), test_a_fetch_after_T_never_reaches_the_move() (+31 more)

### Community 206 - "NBA shooting luck and motivation lab"
Cohesion: 0.11
Nodes (16): f6c_offers(), f6c_signal(), game_situations(), _load_box(), main(), market_offers(), placebo_frames(), population() (+8 more)

### Community 207 - "Shared database connection and sweeps"
Cohesion: 0.01
Nodes (152): live_slate_dates(), _connect(), get_connection(), _open(), _session_options(), use_poller_session(), _fetch_pitcher_gb_pct(), main() (+144 more)

### Community 208 - "NBA play-by-play game matching tests"
Cohesion: 0.06
Nodes (28): _last(), match_games(), match_names(), resolve_map(), _g(), _game_recs(), _rec(), _summary() (+20 more)

### Community 210 - "WNBA stats and results ingestion"
Cohesion: 0.09
Nodes (21): rebuild_wnba_team_stats(), backfill_wnba_stats(), _build_game_id(), _build_game_rows(), _build_player_log_rows(), _build_team_stat_rows(), _fetch_league_game_log(), _ingest_season() (+13 more)

### Community 214 - "Health check skip budget tests"
Cohesion: 0.12
Nodes (11): test_a_stuck_gate_is_not_reported_as_stale_data(), _res(), test_a_non_skipped_result_is_never_touched(), test_a_stuck_gate_escalates_past_its_budget(), test_an_honest_offseason_skip_stays_skipped_but_shows_its_length(), test_applying_twice_does_not_double_annotate(), test_model_calibration_is_persisted(), test_the_default_budget_is_short_enough_to_surface_a_stuck_gate() (+3 more)

### Community 216 - "NBA public betting splits ingestor"
Cohesion: 0.07
Nodes (25): active_queries(), archive_ready(), ensure_table(), et_game_date(), fetch_scoreboard(), flip_side(), _game_meta(), keep_for_poll() (+17 more)

### Community 218 - "Picks unique row tests"
Cohesion: 0.11
Nodes (10): conn(), _prop(), test_dedupe_and_health_use_the_shared_tuple(), test_player_id_uniqueness_is_unchanged(), test_the_card_insert_tolerates_the_unique_index(), test_the_narrow_index_collides_null_player_id_props(), test_the_same_proposition_still_collides_on_the_widened_index(), test_the_widen_migration_is_property_guarded() (+2 more)

### Community 219 - "tests/test_nfl_live_leader_state.py"
Cohesion: 0.14
Nodes (19): situation(), status(), test_a_conversion_try_is_skipped(), test_a_previous_quarters_play_is_not_the_state(), test_a_timeout_is_skipped_for_the_play_before_it(), test_after_a_scoring_play_nothing_is_evaluated(), test_after_the_kickoff_lands_the_receiver_has_the_ball(), test_an_ordinary_snap_is_evaluable_with_the_training_inputs() (+11 more)

### Community 221 - "tests/test_ncaaf_qb_ingestor.py"
Cohesion: 0.11
Nodes (24): _athlete_stats(), _comp_att(), parse_qb_game_stats(), _split_ratio(), test_split_ratio(), _parse(), _payload(), _team() (+16 more)

### Community 222 - "Discord price bound tests"
Cohesion: 0.12
Nodes (14): _dec(), test_a_field_without_a_bound_renders_without_the_clause(), test_a_model_with_no_own_ev_floor_is_bound_by_the_global_one(), test_a_price_floor_can_be_the_binding_gate(), test_a_rounded_bound_still_clears_the_bound_it_came_from(), test_even_money_is_plus_one_hundred(), test_no_bound_from_junk_rather_than_a_guess(), test_no_bound_when_the_edge_floor_is_unreachable() (+6 more)

### Community 224 - "NBA derivative market lab"
Cohesion: 0.09
Nodes (35): add_team(), am_to_dec(), bars_for(), bet_list(), blind(), boot_ci(), build_line_rows(), build_outcomes() (+27 more)

### Community 232 - "Mobile pick category tests"
Cohesion: 0.13
Nodes (12): _block(), _config_scorable_ids(), _meta_ids(), _meta_types(), _read(), test_every_model_id_derives_its_own_declared_category(), test_every_scorable_model_has_a_label_in_the_app(), test_picks_idle_chrome_is_search_and_filters_only() (+4 more)

### Community 235 - "NCAAF feature engine tests"
Cohesion: 0.07
Nodes (29): haversine_miles(), tz_offset_from_lon(), _venue_features(), trip(), _assemble(), _stats(), test_altitude_climb_is_signed_from_each_teams_own_elevation(), test_assembly_carries_venue_context_and_hfa() (+21 more)

### Community 237 - "House juice price floor tests"
Cohesion: 0.05
Nodes (19): min_odds_for(), honest_probability(), _blocked_by_min_odds(), test_a_pick_with_no_price_is_never_blocked_by_the_floor(), test_an_explicit_floor_wins_in_BOTH_directions(), test_every_registered_model_has_an_effective_floor(), test_ordinary_prices_still_fire(), test_the_default_is_overridable_without_a_code_change() (+11 more)

### Community 240 - "tests/test_ncaaf_game_identity.py"
Cohesion: 0.12
Nodes (16): _add(), _conn(), _identity_sql(), _run(), test_a_clean_slate_reports_nothing(), test_a_non_fbs_fixture_is_not_reported(), test_a_phantom_opponent_is_detected_too(), test_a_real_doubleheader_is_not_a_duplicate() (+8 more)

### Community 241 - "NBA second game market tests"
Cohesion: 0.10
Nodes (27): _close_frames(), _data(), _f2_games(), _f6a_data(), _f6d_total_data(), _game(), _pe(), _q() (+19 more)

### Community 242 - "Position versus opponent tests"
Cohesion: 0.07
Nodes (19): _bn_body(), _sql_groups(), test_a_failed_position_read_is_said_not_hidden(), test_a_failed_read_is_not_held_on_the_spinner(), test_every_mlb_stat_chip_has_a_branch(), test_every_nfl_stat_chip_has_a_branch(), test_every_roster_sport_chip_has_a_branch(), test_mlb_lineup_buckets_agree_between_app_and_server() (+11 more)

### Community 243 - "MLB and WNBA stats ingestors and pitcher rebuild"
Cohesion: 0.04
Nodes (39): backfill_bullpen_stats(), backfill_mlb_stats(), backfill_pitcher_stats(), backfill_player_game_log(), backfill_player_handedness(), _build_pitcher_rows(), _build_team_stats_rows(), _fetch_mlb_api_batting() (+31 more)

### Community 25 - "NBA game search grading harness"
Cohesion: 0.04
Nodes (50): blind_by_real_side(), blind_pool(), blind_side(), boot(), cell_report(), cents(), check(), choose() (+42 more)

### Community 252 - "NBA totals overs card"
Cohesion: 0.10
Nodes (16): step_mlb_total_public_fade(), step_nba_total_luck(), artifact(), decided_games(), ensure_decisions_table(), ledger_exists(), load_quote_rows(), load_season() (+8 more)

### Community 256 - "College football search features"
Cohesion: 0.14
Nodes (13): build_adjusted_ratings(), build_prior_season_ratings(), load_fbs_membership(), load_team_games(), pool_fcs_opponents(), rolling_variants(), _asof_merge(), build_matrix() (+5 more)

### Community 260 - "tests/test_live_game_features.py"
Cohesion: 0.11
Nodes (19): compute_live_target(), half_innings_left(), parse_bases(), state_features(), test_build_live_state_row_merges_pregame_context(), test_build_live_state_row_unusable_state(), test_half_innings_left_bottom_ninth(), test_half_innings_left_extras_clamps_to_one() (+11 more)

### Community 261 - "tests/test_ncaaf_totals_regression.py"
Cohesion: 0.10
Nodes (14): total_over_prob(), test_artifact_kind_is_routed_by_the_scorer(), test_asymmetry_is_real_and_would_have_bitten(), test_extremes_are_clamped_away_from_certainty(), test_model_above_the_line_favours_the_over(), test_model_below_the_line_favours_the_under(), test_no_dk_total_means_skip_not_prob_only(), test_no_residuals_returns_one_half_not_a_confident_bet() (+6 more)

### Community 262 - "UFC feature engine and tests"
Cohesion: 0.13
Nodes (20): _age_years(), _assemble_ufc_features(), career_stats(), compute_ufc_target(), infer_five_rounds(), synthetic_round_total(), _fight(), _stats_pair() (+12 more)

### Community 263 - "App script tests run through node"
Cohesion: 0.03
Nodes (64): main(), node_strips_types(), tsx_cmd(), _node_strips_types(), test_a_published_void_keeps_track_and_betslip(), test_a_tracked_void_reads_not_graded_and_detail_closes_when_over(), test_the_app_predicate_matches(), test_today_et_ignores_the_container_timezone() (+56 more)

### Community 267 - "tests/test_ncaaf_qb_features.py"
Cohesion: 0.19
Nodes (16): build_qb_team_features(), _feat(), _frame(), _qb_rows(), test_a_games_features_never_use_that_game(), test_current_qb_is_the_previous_games_primary(), test_empty_input_returns_the_right_shape(), test_first_game_has_no_qb_features_at_all() (+8 more)

### Community 268 - "NFL in-play prop flow calibration"
Cohesion: 0.08
Nodes (20): evaluate(), _infer_position(), main(), _pool_prior(), report(), _rows_for_market(), _to_states(), accrual_at() (+12 more)

### Community 271 - "Line CLV sign and orientation tests"
Cohesion: 0.05
Nodes (12): test_runner_captures_stdout_from_the_script_main(), test_sport_and_market_are_bounded(), test_the_declared_key_is_present_and_valid(), test_the_runner_imports_the_script_main_not_a_shell(), _load(), test_a_line_that_held_is_exactly_zero_not_none(), test_a_missing_close_is_not_a_zero(), test_a_side_that_cannot_be_oriented_returns_none_rather_than_guessing() (+4 more)

### Community 272 - "Mobile screen source wiring tests"
Cohesion: 0.03
Nodes (67): test_every_revoke_names_the_roles_rather_than_public(), test_odds_keeps_select_for_the_app(), test_the_two_rls_off_tables_lose_everything(), test_best_odds_never_reaches_the_qualifying_gate(), _backfill_body(), test_a_game_absent_from_our_games_table_is_still_skipped(), test_no_skip_is_keyed_on_date_alone(), test_the_coverage_set_is_scoped_to_the_season_being_built() (+59 more)

### Community 275 - "NBA game harness tests"
Cohesion: 0.08
Nodes (27): _cov_data(), _fetches(), _games(), _offers(), _q(), _stale_cache(), test_a_cell_reports_its_pooled_walk_forward_and_writes_its_bets(), test_a_graded_load_refuses_a_season_the_cache_does_not_price() (+19 more)

### Community 280 - "MLB live game state trigger tests"
Cohesion: 0.17
Nodes (16): _detect_triggers(), _is_active_or_starting_soon(), test_active_in_progress_game_is_active(), test_combined_changes_fire_all_relevant_triggers(), test_due_up_change_fires_due_up_change(), test_final_game_is_not_active(), test_identical_state_fires_no_triggers(), test_inning_half_change_fires_inning_change() (+8 more)

### Community 282 - "Fight board price age tests"
Cohesion: 0.12
Nodes (17): _ago(), _clock(), _h2h_row(), _score_card(), test_a_bet_on_either_id_locks_the_model_for_both(), test_a_never_priced_id_is_not_scored_beside_its_priced_twin(), test_a_price_stored_this_pass_still_decides(), test_just_inside_and_just_outside_the_bound() (+9 more)

### Community 283 - "NFL in-play line churn study"
Cohesion: 0.19
Nodes (13): churn_table(), main(), verdict(), _snaps(), test_a_line_moving_every_interval_reads_as_under_sampled(), test_a_missing_key_column_fails_loudly_rather_than_grouping_coarser(), test_a_single_snapshot_contributes_no_interval(), test_a_still_line_reads_as_still() (+5 more)

### Community 286 - "Kalshi prop ingest"
Cohesion: 0.05
Nodes (16): _event_date(), _player(), record_ladders(), test_a_kalshi_outage_cannot_break_the_pass(), test_a_run_is_idempotent_within_its_snapshot(), test_one_snapshot_timestamp_for_the_whole_run(), test_the_recorder_is_scheduled_on_the_pipeline_role(), test_the_recorder_keeps_raw_prices_not_a_filtered_ladder() (+8 more)

### Community 287 - "Model calibration check tests"
Cohesion: 0.09
Nodes (12): _calibration_sql(), test_a_flagged_model_is_named_eligible_or_not(), test_a_thin_model_is_still_excluded_rather_than_accused(), test_eligibility_notes_must_not_sink_the_gap_check(), test_eligibility_notes_parse_the_payload_verdicts(), test_it_grades_the_calibrated_probability_not_the_raw_one(), test_it_joins_picks_to_reach_the_calibrated_column(), test_the_check_has_a_skip_budget_that_survives_a_regime_change() (+4 more)

### Community 289 - "NBA ESPN box score parsing"
Cohesion: 0.05
Nodes (40): box_team_totals(), et_date(), fill_missing(), nba_team(), _no_minutes(), parse_nba_box(), parse_nba_dnp(), parse_nba_postponed() (+32 more)

### Community 29 - "NCAAF college data ingestor"
Cohesion: 0.06
Nodes (28): backfill_ncaaf_lines(), backfill_ncaaf_players(), backfill_ncaaf_qb(), _existing_ncaaf_ids(), _fold(), _get(), ingest_ncaaf_game_log(), ingest_ncaaf_games() (+20 more)

### Community 290 - "NBA second game model verdict"
Cohesion: 0.13
Nodes (14): cell_rows(), main(), _plain(), axes_of(), bar9(), cell_key(), _floats(), house_bar4() (+6 more)

### Community 293 - "Historical odds backfill and in-play marking"
Cohesion: 0.02
Nodes (80): _ledger_entry_is_resumable(), relabel_in_play(), run_historical_odds_range(), candidate_markets(), _standard_markets(), test_it_does_not_enable_rls_blind(), test_the_app_write_tables_are_not_touched(), test_the_artifact_table_revokes_at_its_own_creation() (+72 more)

### Community 294 - "NCAAF player stats parser tests"
Cohesion: 0.18
Nodes (17): parse_player_game_stats(), _cat(), _parse(), _payload(), _team(), test_a_game_missing_from_the_id_map_is_skipped_not_guessed(), test_a_player_gets_one_row_across_every_category(), test_a_player_with_nothing_we_track_is_skipped() (+9 more)

### Community 296 - "In-play inning gate replay tests"
Cohesion: 0.12
Nodes (28): _grade(), _pair(), _refuse_tables(), _score_seen_at(), _game(), _price(), _scored(), _sig() (+20 more)

### Community 297 - "scripts/nfl_live_prop_feasibility.py"
Cohesion: 0.22
Nodes (18): american_b(), bettable(), boot_roi(), brier(), design(), fit_market(), grade(), implied() (+10 more)

### Community 299 - "tests/test_context_budget.py"
Cohesion: 0.12
Nodes (14): _expand_braces(), _hook_context(), _read(), _rule_files(), _size(), test_claude_md_stays_small_enough_to_load_every_session(), test_every_doc_referenced_by_the_index_exists(), test_every_rules_file_is_pointed_at_from_claude_md() (+6 more)

### Community 303 - "tests/test_player_h2h_stat_values_migration.py"
Cohesion: 0.10
Nodes (13): _body(), test_each_function_reads_its_own_log_table(), test_it_does_its_ddl_once_and_guards_on_the_property_it_establishes(), test_it_is_one_statement_so_conn_execute_cannot_shred_it(), test_public_is_revoked_before_anon_is_granted(), test_security_invoker_like_the_season_rpcs_it_mirrors(), test_the_fixture_is_two_parallel_arrays_not_a_separator(), test_the_players_latest_team_decides_his_fixture() (+5 more)

### Community 305 - "tests/test_retired_models.py"
Cohesion: 0.06
Nodes (13): test_a_retired_game_model_is_in_no_feature_map(), test_a_retired_model_is_in_no_registry_and_no_threshold_dict(), test_a_retired_prop_has_no_feature_map_and_no_training_label(), test_a_retired_sport_is_not_still_health_checked(), test_paused_nfl_props_still_in_prop_models_and_thresholds(), test_retired_prop_picks_still_settle_on_their_own_stat(), test_ten_nfl_distributional_props_are_paused(), test_the_app_mirrors_the_same_set() (+5 more)

### Community 309 - "NBA game projection test fixtures"
Cohesion: 0.18
Nodes (22): _box(), _games(), _inj(), _rapm_inputs(), _segment_rows(), _state(), test_a_back_to_back_is_read_from_the_schedule(), test_a_game_gets_no_projection_while_a_previous_date_game_could_still_be_running() (+14 more)

### Community 31 - "NBA prop model lab and verification"
Cohesion: 0.04
Nodes (79): books(), load_cache(), p_over(), main(), _agg(), apply_rule(), binary_baselines(), binary_indep() (+71 more)

### Community 315 - "NFL weather cache import"
Cohesion: 0.14
Nodes (11): main(), rows_from_file(), source_for(), stadium_from_name(), stored_files(), _INSERT_PLACEHOLDERS(), test_a_non_issued_or_empty_payload_yields_nothing(), test_every_hour_becomes_one_row_in_column_order() (+3 more)

### Community 317 - "Latest line state trigger tests"
Cohesion: 0.07
Nodes (34): can_scratch(), env_dsn(), _free_port(), pg_bin(), scratch_cluster(), as_app(), db(), dsn() (+26 more)

### Community 318 - "tests/test_live_record_start_views.py"
Cohesion: 0.09
Nodes (12): _body(), _code(), test_both_published_views_carry_the_live_date_gate(), test_it_runs_after_the_migration_that_used_to_own_the_daily_view(), test_migration_is_one_statement(), test_migration_is_registered_with_the_worker_runner(), test_neither_view_reads_the_sweep_universe(), test_no_ddl_outside_the_guarded_branches() (+4 more)

### Community 319 - "Model quality volume spike checks"
Cohesion: 0.13
Nodes (15): record_exclusion_sql(), test_volume_spike_vs_median(), test_volume_without_history_is_skipped_not_flagged(), test_the_exclusion_sql_is_a_conjunction_of_negations(), _job_model_quality(), detect_volume_spike(), ensure_schema(), _group() (+7 more)

### Community 323 - "NBA prop window scheduling tests"
Cohesion: 0.18
Nodes (13): _fires(), _jobs(), test_a_tick_fetches_exactly_the_window_games_then_decides_closes_and_publishes(), test_a_tick_with_nothing_near_spends_nothing(), test_a_tick_with_only_a_close_due_does_not_return_early(), test_a_tick_with_only_a_game_near_tip_publishes_and_spends_nothing(), test_a_tick_with_only_projections_due_spends_no_api_call(), test_every_tip_time_gets_a_look_inside_its_window() (+5 more)

### Community 326 - "NBA rest and schedule features"
Cohesion: 0.12
Nodes (10): _counted_schedule(), from_cache(), game_schedule_features(), haversine_miles(), home_bases(), _offsets(), previous_game_load(), team_schedule_features() (+2 more)

### Community 328 - "NFL Kalshi edge search"
Cohesion: 0.17
Nodes (20): align_check(), bh(), bins(), boot(), cell(), coverage(), cp_roi(), fee() (+12 more)

### Community 329 - "nfl/models/opener_spread.py"
Cohesion: 0.14
Nodes (11): age_tag(), american_to_prob(), _bettable_books(), clean_board(), edge_tier(), evaluate_board(), held_minutes(), model_prob_for_dev() (+3 more)

### Community 332 - "Live game state poller and slate dates"
Cohesion: 0.10
Nodes (10): _at(), test_both_live_loops_share_one_definition_of_the_slate(), test_by_daytime_yesterday_is_dropped(), test_just_after_midnight_still_asks_about_yesterday(), test_just_before_midnight_asks_about_today_only(), test_the_apps_live_hook_resolves_the_window_per_fetch(), test_the_apps_live_reads_take_a_LIST_of_dates(), test_the_ncaaf_live_loop_got_the_same_fix() (+2 more)

### Community 333 - "tests/test_nfl_wind_fire_window.py"
Cohesion: 0.07
Nodes (18): _retractable_slate(), _slate(), test_a_blank_roof_at_a_NON_retractable_venue_is_unaffected(), test_a_closed_roof_is_still_indoor(), test_a_retractable_venue_with_an_unknown_roof_does_not_fire(), test_a_waiting_game_is_not_reported_as_a_collapsed_premise(), test_a_waiting_row_keeps_its_line_price_and_edge(), test_every_blank_roof_row_is_a_retractable_venue() (+10 more)

### Community 335 - "tests/test_public_betting_ingestor.py"
Cohesion: 0.15
Nodes (18): parse_public_betting(), _pct(), probe(), _select_book(), _make_game(), test_parse_emits_six_rows(), test_parse_game_id_and_sides(), test_parse_marks_source_and_snapshot() (+10 more)

### Community 339 - "tests/test_service_role_split.py"
Cohesion: 0.13
Nodes (12): _all_job_ids(), _sched(), test_an_unknown_role_runs_everything(), test_every_add_job_call_passes_an_id(), test_every_job_is_owned_by_exactly_one_role(), test_role_filtering_wraps_add_job_once(), test_the_always_on_jobs_run_on_every_role(), test_the_default_preserves_the_single_container() (+4 more)

### Community 34 - "Kalshi prop ladders and game markets"
Cohesion: 0.09
Nodes (19): from_one_sided_overs(), _ladder(), test_a_clean_ladder_is_not_reported_as_repaired(), test_a_one_sided_ladder_is_vigged_and_says_so(), test_a_quoted_strike_returns_its_own_mid(), test_a_thin_one_sided_ladder_cannot_be_anchored(), test_an_unquoted_line_interpolates_between_its_neighbours(), test_anchoring_moves_the_ladder_onto_an_honest_point() (+11 more)

### Community 343 - "tests/test_http_timeout_floor.py"
Cohesion: 0.11
Nodes (11): install_timeout_floor(), _call(), clean_requests(), test_a_call_with_no_timeout_gets_one(), test_an_explicit_timeout_is_never_overridden(), test_installing_twice_is_a_no_op(), test_the_deadline_is_env_overridable(), test_the_deadline_survives_telemetry_being_turned_off() (+3 more)

### Community 345 - "Model quality public fade tests"
Cohesion: 0.10
Nodes (9): _bet(), test_high_public_pct_on_a_fade_publisher_counts_as_a_fade(), test_low_public_pct_on_the_pick_side_counts_as_a_fade(), test_majority_share_warns_when_not_unanimous(), test_meta_steps_exclude_model_quality(), test_pipeline_step_never_fails_on_crit(), test_pipeline_step_never_fails_on_exception(), test_side_aliases_collapse_to_the_same_direction() (+1 more)

### Community 346 - "NFL edge research data cache"
Cohesion: 0.22
Nodes (14): _conn(), copy_main_local(), _df(), _games_2026(), log(), main(), nflverse_misc(), nflverse_pbp() (+6 more)

### Community 347 - "Paused model assessment script"
Cohesion: 0.10
Nodes (15): _auto_paused_models(), active_era(), assess(), _half(), fetch(), grade(), main(), sweep() (+7 more)

### Community 35 - "NBA second game projection tests"
Cohesion: 0.07
Nodes (16): _cons(), _dist(), _neutral(), _segments(), test_f1_is_priced_through_the_projections_own_error_not_the_markets(), test_f1b_does_not_score_a_books_number_off_the_consensus(), test_f1b_strength_is_the_predicted_move_in_the_sides_favour(), test_the_consensus_number_is_pinnacles_else_the_deciding_books_median() (+8 more)

### Community 351 - "Slate concentration and fade risk detection"
Cohesion: 0.16
Nodes (12): _fade_slate(), test_a_mixed_slate_is_ok(), test_all_home_ncaaf_slate_is_flagged_without_mlb_hardcoding(), test_all_unders_public_fade_risk_is_crit(), test_all_unders_public_fade_slate_is_crit(), test_fade_in_the_model_id_is_sport_agnostic(), test_thin_slate_is_not_a_finding(), test_unanimous_but_small_slate_is_warn_not_crit() (+4 more)

### Community 352 - "NHL prop odds alternate line tests"
Cohesion: 0.11
Nodes (14): due(), test_a_game_first_priced_inside_the_final_window_gets_nothing_more(), test_a_game_first_priced_inside_the_window_gets_one_decision_snapshot(), test_a_game_with_nothing_stored_is_owed_its_open(), test_a_moved_featured_line_keeps_the_old_number_under_the_alternate_key(), test_a_whole_day_of_passes_buys_exactly_three(), test_after_the_close_one_final_is_bought_for_clv_and_then_nothing(), test_an_opened_game_is_owed_nothing_until_the_closing_window() (+6 more)

### Community 358 - "Ops alert watchdogs"
Cohesion: 0.06
Nodes (21): auto_pause_caveat(), _sweep(), _sweep_dates(), _is_health_check_step(), _latest_health_rows(), _pass_is_clean(), _producer_failures(), _step_names() (+13 more)

### Community 366 - "Kalshi game market recorder"
Cohesion: 0.07
Nodes (17): event_code(), event_date(), kalshi_school(), _num(), probe(), record_game_markets(), resolve_events(), rows_for() (+9 more)

### Community 367 - "Odds pruning keeps openers"
Cohesion: 0.11
Nodes (8): test_both_delete_tiers_exclude_openers(), test_cfbd_archive_prefix_is_protected(), test_historical_backfill_rows_are_protected_in_odds(), test_line_shop_books_are_not_protected_wholesale(), test_openers_subquery_exists_and_orders_ascending(), test_prop_table_has_no_source_column_so_no_source_clause(), test_tier2_still_prunes_intermediate_snapshots(), test_unprotected_predicate_covers_every_prefix()

### Community 369 - "UFC fighter name resolution"
Cohesion: 0.17
Nodes (10): resolve_slug(), test_a_generational_suffix_resolves_either_way(), test_a_near_miss_is_not_a_match(), test_a_reversed_name_order_resolves(), test_a_shared_surname_alone_is_not_a_match(), test_an_ambiguous_token_set_resolves_to_nothing(), test_an_empty_or_tokenless_name_is_safe(), test_an_exact_slug_still_wins_untouched() (+2 more)

### Community 373 - "NFL in-play lag book grading"
Cohesion: 0.12
Nodes (28): s(), cell(), h1(), h2(), h3(), h4(), h5(), h6() (+20 more)

### Community 375 - "Refresh pass step ordering tests"
Cohesion: 0.10
Nodes (13): _order(), test_a_parallel_step_that_fails_is_still_recorded(), test_no_sequential_step_runs_while_a_parallel_group_is_open(), test_opening_signals_follows_every_scorer(), test_parlay_follows_opening_signals(), test_scoring_follows_every_ingest(), test_settle_follows_every_results_ingest(), test_sync_thresholds_follows_migrations_and_precedes_scoring() (+5 more)

### Community 379 - "NBA historical odds archive parser"
Cohesion: 0.15
Nodes (18): classify(), _fold(), _is_half(), _num(), parse_season(), _price(), team(), _page() (+10 more)

### Community 38 - "Sharp book odds retention in pruning"
Cohesion: 0.11
Nodes (12): _prop_reference_books(), protected_for(), _unprotected(), test_the_bookmaker_these_rows_use_survives_the_daily_prune(), test_a_shopping_book_is_still_prunable(), test_every_prop_reference_book_is_protected(), test_every_sharp_book_is_protected_in_the_prop_table(), test_pinnacle_specifically_is_protected_in_the_prop_table() (+4 more)

### Community 383 - "Mobile tracked performance checks"
Cohesion: 0.10
Nodes (18): dup, empty, half, l50, loss, noAction, open1, open2 (+10 more)

### Community 384 - "tests/test_mobile_threshold_parity.py"
Cohesion: 0.16
Nodes (12): _block(), _canonical(), _mirror(), _mirror_paused(), _src(), test_every_cut_matches_config(), test_every_scorable_model_is_in_the_app_mirror(), test_the_app_mirror_holds_no_model_config_cannot_score() (+4 more)

### Community 386 - "NHL derivative odds job validation tests"
Cohesion: 0.12
Nodes (9): test_a_credit_ceiling_is_a_malformed_request(), test_apply_argv_is_only_apply(), test_apply_is_explicit_and_carries_no_ceiling(), test_dry_run_argv_has_no_apply_and_no_ceiling(), capture(), test_empty_args_are_a_dry_run(), test_probe_argv_does_not_apply(), _job_nhl_derivative_odds_history() (+1 more)

### Community 388 - "tests/test_track_record_views.py"
Cohesion: 0.11
Nodes (10): _body(), _code(), test_migration_is_one_statement(), test_migration_is_registered_with_the_worker_runner(), test_no_ddl_outside_the_guarded_branches(), test_refresh_pass_refreshes_outcomes_after_settle(), test_the_daily_view_is_no_longer_redefined_here(), test_the_full_outcome_view_reads_the_matview_and_never_the_player_logs() (+2 more)

### Community 389 - "tests/test_weekly_catch_up.py"
Cohesion: 0.11
Nodes (11): sched(), test_a_fresh_savant_does_not_suppress_the_calibration_catch_up(), test_a_missing_sweeps_table_counts_as_stale(), test_a_recent_sweep_does_not(), test_an_old_sweep_triggers_the_catch_up(), test_model_calibration_belongs_to_the_pipeline_service(), test_ownership_is_checked_per_job(), test_the_catch_up_creates_the_review_tables_on_boot() (+3 more)

### Community 394 - "Injury fetch cache speed tests"
Cohesion: 0.09
Nodes (8): _clear_cache(), test_a_dead_database_leaves_the_cache_empty_not_broken(), test_a_failed_lookup_is_not_cached(), test_a_known_athlete_costs_no_request(), test_one_team_failing_does_not_lose_the_others(), test_output_order_follows_the_team_list_not_completion_order(), test_the_cache_seeds_from_our_own_stored_injuries(), test_the_pool_is_small_because_espn_has_blocked_us_twice()

### Community 396 - "MLB public fade top-K holdout"
Cohesion: 0.12
Nodes (18): american_units(), bucket_win_rates(), build_candidates(), _fmt(), grade_under(), holdout_take(), load_db(), load_json() (+10 more)

### Community 399 - "NFL live leader model tests"
Cohesion: 0.10
Nodes (19): fit_wp(), logit_irls(), wp_design(), wp_lookup(), art(), _d(), _raw(), test_600_seconds_and_both_lead_ends_are_inside() (+11 more)

### Community 40 - "NFL edge search helpers"
Cohesion: 0.03
Nodes (85): backfill_cost(), bets(), bh(), clean_2h(), fmt(), forward_2026(), hdr(), _line_models() (+77 more)

### Community 400 - "Mobile paused catalog tests"
Cohesion: 0.18
Nodes (10): _block(), _read(), test_paused_picks_reach_the_all_board_only_and_labelled(), test_stats_add_pick_refuses_a_paused_model(), test_the_bet_type_picker_filters_paused_models(), test_the_custom_model_picker_is_three_bet_types(), test_the_models_list_filters_paused_models(), test_the_pause_source_is_isModelPaused_not_a_hand_copied_set() (+2 more)

### Community 401 - "App bankroll field and unit rows"
Cohesion: 0.18
Nodes (20): fieldFlow(), inv(), bankrollDraft(), bankrollFieldText(), canonical(), checkBankroll(), commitBankrollText(), editBankrollInput() (+12 more)

### Community 402 - "NBA totals overs replay of the lab"
Cohesion: 0.13
Nodes (7): load_artifact(), lab_bets(), lab_gaps(), load(), main(), replay(), art()

### Community 403 - "MLB play-by-play ingestor"
Cohesion: 0.16
Nodes (15): _bases_after_from_matchup(), parse_game_plays(), parse_play(), _split_event_type(), test_bases_empty_matchup(), test_bases_with_runners(), test_parse_game_plays_empty_feed(), test_parse_game_plays_walks_full_inning() (+7 more)

### Community 404 - "tests/test_promote_calibration_job.py"
Cohesion: 0.11
Nodes (3): test_a_refused_model_rolls_back_and_raises(), test_a_successful_promote_commits(), _job_promote_calibration()

### Community 406 - "tests/test_cfbd_snapshot_leakage.py"
Cohesion: 0.16
Nodes (9): _completed_before(), _ohio_state_2024(), test_boundary_is_strict(), test_datetime_like_values_are_handled(), test_empty_input(), test_end_of_regular_season_snapshot_excludes_playoffs(), test_missing_or_malformed_dates_are_dropped_not_admitted(), test_postseason_excluded_from_early_season_snapshot() (+1 more)

### Community 411 - "Rule model market mapping tests"
Cohesion: 0.15
Nodes (10): _case(), _clv_game_market(), _like(), _prompt_case(), _scorer_case(), test_the_case_reader_reads_the_name_patterns_as_postgres_does(), test_the_claude_mobile_prompt_reads_the_rule_card_s_market(), test_the_closing_line_functions_are_recreated_when_they_change() (+2 more)

### Community 412 - "NCAAF outcome edge scan"
Cohesion: 0.19
Nodes (12): _cell(), ecdf_prob_positive(), implied(), load_ml_prices(), main(), payout(), predict_all(), _print_cells() (+4 more)

### Community 413 - "tests/test_nfl_prop_thresholds.py"
Cohesion: 0.11
Nodes (8): test_live_webhook_map_reads_the_per_sport_env_vars(), cfg(), test_no_nfl_prop_market_is_back_on_the_uniform_placeholder(), test_one_bad_date_does_not_cost_the_others(), test_the_prop_window_has_exactly_one_declaration(), test_the_scorer_step_covers_the_whole_window_not_one_date(), fake(), test_the_three_threshold_dicts_agree_for_every_nfl_prop_market()

### Community 414 - "tests/test_nhl_research_job.py"
Cohesion: 0.15
Nodes (11): test_a_dump_argument_is_refused(), test_a_model_must_be_a_real_spec(), test_a_season_must_be_a_priced_one(), test_an_unknown_script_is_refused(), test_an_unknown_top_level_key_is_refused(), test_every_runnable_module_has_a_main(), test_every_runnable_module_writes_no_database_row(), test_the_artifact_grade_names_the_rule_production_runs() (+3 more)

### Community 415 - "tests/test_settlement_timing.py"
Cohesion: 0.19
Nodes (7): test_future_kickoffs_are_not_treated_as_started(), test_game_log_skips_per_game_not_per_date(), test_mirror_unchanged_is_conservative_when_it_cannot_tell(), test_started_games_are_recognised_in_every_stored_format(), test_unparseable_timestamps_yield_none_rather_than_a_guess(), test_z_and_offset_forms_are_the_same_instant_but_not_the_same_string(), _as_utc()

### Community 416 - "App and server closing value parity"
Cohesion: 0.13
Nodes (17): _app(), _clv_card(), _server(), test_a_label_book_nfl_pick_compares_its_line_with_that_book(), test_a_recorded_book_differs_from_the_derived_one(), test_the_app_prefers_the_recorded_book_at_the_derived_price(), test_the_app_prices_every_row_as_the_server_grades_it(), test_the_card_prints_the_price_taken_not_draftkings() (+9 more)

### Community 417 - "Per-model threshold config tests"
Cohesion: 0.08
Nodes (8): test_an_own_floor_does_not_take_a_model_off_the_calibration_map(), test_every_model_carries_its_own_thresholds(), test_every_own_floor_names_a_live_model(), test_models_on_own_probability_is_not_derived_from_the_floor_dict(), test_no_own_floor_tightens_a_model_past_the_global_floor(), test_only_a_market_priced_model_carries_a_negative_floor(), test_own_ev_floor_and_model_min_ev_stay_disjoint(), test_the_models_the_global_floor_silently_removed_can_bet_again()

### Community 418 - "App accessibility checks"
Cohesion: 0.11
Nodes (14): node_exe(), _node_strips_types(), _read(), _run(), test_audited_targets(), test_betslip_bar_inset_wiring(), test_h9_rows_reach_44pt_inside_their_bounds(), test_pick_card_label_is_complete() (+6 more)

### Community 42 - "DataGolf ingestor and NHL SBR archive"
Cohesion: 0.05
Nodes (45): _american(), backfill_golf_rounds(), build_game_id(), _dg_get(), _earliest_commence_iso(), _event_meta_lookup(), event_slug(), ingest_golf_field() (+37 more)

### Community 425 - "NFL odds cache import to Supabase"
Cohesion: 0.12
Nodes (9): _allowed(), _data_dirs(), test_a_rerun_after_the_resolver_improves_adds_only_the_gap(), test_every_buying_ingestor_keys_its_resume_on_a_source_marker(), test_no_undeclared_data_store_on_disk(), test_the_importer_resolves_a_postponed_game(), test_the_importer_still_refuses_an_event_with_no_game(), test_the_nfl_odds_cache_has_an_importer() (+1 more)

### Community 426 - "tests/test_health_check_observe.py"
Cohesion: 0.14
Nodes (10): _crit(), fake(), test_a_crit_does_not_fail_the_observe_path(), test_a_crit_still_fails_the_daily_step(), test_an_exception_does_not_fail_the_observe_path(), test_daily_syncs_thresholds_after_view_migrations(), test_it_still_runs_the_check_when_observing(), test_ok_is_identity_in_both_modes() (+2 more)

### Community 427 - "NHL box score ingest"
Cohesion: 0.12
Nodes (16): _decision(), fill_missing(), _insert_absent(), _int(), _name(), parse_boxscore(), side_rows(), store_boxscore() (+8 more)

### Community 428 - "NFL 2026 opener and wind tracker"
Cohesion: 0.15
Nodes (15): classify(), fetch(), grade_rows(), is_void(), lead_days(), _load_nfl_model(), main(), report() (+7 more)

### Community 429 - "NFL edge luck and weather studies"
Cohesion: 0.03
Nodes (83): load_games(), main(), wide_spreads(), wide_totals(), attach_fetch(), audit(), main(), add_windows() (+75 more)

### Community 430 - "NFL prop shape simulation"
Cohesion: 0.20
Nodes (12): anchor_scale(), calibration(), grade(), latest(), load_odds(), main(), placebo_sf(), player_gamma() (+4 more)

### Community 431 - "tests/test_pick_lock_is_on_picks.py"
Cohesion: 0.16
Nodes (9): _between(), _sql(), test_a_bet_is_still_never_re_scored(), test_only_a_bet_locks_a_pair(), test_the_cleanup_covers_the_whole_look_ahead_window(), test_the_cleanup_never_touches_a_started_game_or_a_live_row(), test_the_lock_is_no_longer_ncaaf_specific(), test_the_prop_and_live_locks_are_unchanged() (+1 more)

### Community 434 - "NCAAF board visibility tests"
Cohesion: 0.07
Nodes (21): _days_until(), _line(), _patch(), test_a_declined_rule_can_never_leak_a_signal(), test_a_fired_pick_clears_its_own_probability_floor(), test_a_no_signal_row_does_not_lock_an_ncaaf_game_for_the_week(), test_books_agreeing_is_a_no_signal_row(), test_days_until_is_none_without_a_kickoff_time() (+13 more)

### Community 435 - "NBA box score enrichment"
Cohesion: 0.07
Nodes (49): _blank(), box_rows(), _check_unmapped(), _create(), dnp_kind(), ensure_tables(), fetch_advanced(), _flt() (+41 more)

### Community 436 - "Env file fallback reader"
Cohesion: 0.09
Nodes (19): main(), scram_stored_key(), _classes(), main(), database_url(), _default_env_path(), env_value(), parse_env_file() (+11 more)

### Community 437 - "College football margin cover tests"
Cohesion: 0.13
Nodes (9): sweep_spread(), test_margin_cover_prob_ecdf(), test_rmse(), test_scorer_routes_margin_artifact_through_residual_prob(), test_spread_grading_home_and_away_sides(), test_spread_push_excluded_from_record(), test_threshold_filters_small_disagreements(), test_verdict_enforces_volume_and_breakeven() (+1 more)

### Community 440 - "ESPN and DraftKings live freshness"
Cohesion: 0.16
Nodes (10): dk_live_quotes(), espn_live_quotes(), _key(), main(), _norm_dk_game(), _norm_espn_game(), _now(), _price() (+2 more)

### Community 442 - "Database address checker"
Cohesion: 0.16
Nodes (17): diagnose(), bad(), _safe(), _fails(), _levels(), test_a_correct_url_reports_no_failures(), test_bare_postgres_on_a_DIRECT_host_is_fine(), test_bare_postgres_on_a_pooler_host_is_named() (+9 more)

### Community 443 - "tests/test_opp_starter_features.py"
Cohesion: 0.18
Nodes (9): _opp_starter_savant(), _batter_bulk(), test_batter_bulk_carries_everything_opp_starter_savant_reads(), test_it_reads_the_starters_savant_row(), test_live_mode_falls_back_to_prior_season(), test_live_mode_prefers_the_current_season(), test_opp_starter_savant_reads_real_values_off_the_real_loader(), test_the_helper_returns_all_four_columns_even_with_no_starter() (+1 more)

### Community 446 - "MLB in-play history pull"
Cohesion: 0.11
Nodes (23): _get(), _iso(), main(), planned_calls(), pull_day(), rows_for(), _served_already(), shard_windows() (+15 more)

### Community 447 - "supabase/functions/discord-link/index.ts"
Cohesion: 0.24
Nodes (15): accessFor(), handleComplete(), handleStart(), handleStatus(), handleUnlink(), hmac(), issueState(), json() (+7 more)

### Community 449 - "tests/test_nfl_prop_clv.py"
Cohesion: 0.16
Nodes (9): _assign(), _book_from_label_fn(), _fn(), test_the_book_is_read_from_the_label_suffix(), test_the_closing_prop_lookup_defaults_to_draftkings_and_binds_the_book(), test_the_label_book_map_is_the_inverse_of_both_cards(), test_the_map_test_no_longer_excludes_nfl(), test_the_market_relative_rules_take_their_market_from_the_row() (+1 more)

### Community 450 - "tests/test_prune_keeps_the_close.py"
Cohesion: 0.16
Nodes (8): test_both_delete_tiers_spare_the_keep_set(), test_each_tier_uses_exactly_one_anti_join(), test_the_close_is_never_an_in_play_price(), test_the_close_is_selected_by_the_newest_snapshot(), test_the_cost_is_recorded_as_a_measurement_not_a_guess(), test_the_opener_is_still_selected_by_the_oldest(), test_the_protected_books_are_untouched_by_this_change(), _tier()

### Community 452 - "tests/test_scoring_methods.py"
Cohesion: 0.15
Nodes (6): _generic(), test_a_generic_model_is_never_declared_rule_or_engine(), test_every_classified_model_carries_thresholds(), test_mlb_live_total_runs_is_artifact_backed(), test_rule_based_models_never_appear_in_a_feature_map(), test_the_map_covers_exactly_the_non_generic_models()

### Community 456 - "NBA game projection lab runs"
Cohesion: 0.15
Nodes (11): full(), load_world(), main(), pd_baseline(), quality(), ratings_used(), ref_games(), refuse() (+3 more)

### Community 457 - "NBA game projection world build"
Cohesion: 0.15
Nodes (11): build_panel(), build_world(), cell_specs(), check_cell_count(), _ids(), ledger_2021(), _norm_id(), normalize_stints() (+3 more)

### Community 458 - "NFL ESPN injury ingest tests"
Cohesion: 0.11
Nodes (9): _fetch_nfl_espn_team_ids_core(), _nfl_espn_team_to_abbrev(), _fake_fetch(), test_core_nfl_listing_failure_returns_empty(), test_core_nfl_team_ids_resolve_lar_and_wsh_to_ours(), test_injury_fetch_raises_the_page_limit(), test_nfl_active_rows_are_dropped_and_out_keeps_espn_date(), test_nfl_name_join_uses_our_abbrevs_not_espns() (+1 more)

### Community 462 - "Anonymous read access lockdown"
Cohesion: 0.03
Nodes (45): all_readable(), closed_tables(), lock_down_sql(), write_verbs_for(), _function_plan(), _function_signature(), main(), _plan() (+37 more)

### Community 463 - "NFL 2026 opener and wind tracking"
Cohesion: 0.16
Nodes (13): opener_verdict(), _row(), _src(), test_config_comments_state_the_policy(), test_live_cuts_did_not_move(), test_max_fire_lead_stays_four_in_the_live_model(), test_opener_does_not_retire_mid_season_even_if_currently_up(), test_opener_retire_candidate_only_when_the_season_finished_flat_or_worse() (+5 more)

### Community 464 - "College football game-day cadence tests"
Cohesion: 0.12
Nodes (6): gameday_mod(), test_credit_cap_covers_a_full_saturday_at_the_configured_cadence(), test_idle_cadence_is_slower_than_the_live_cadence(), test_kickoffs_already_past_are_not_counted_as_upcoming(), test_state_cadence_is_fast_enough_to_react_to_a_drive(), test_the_effective_odds_cadence_is_bounded_by_the_pass()

### Community 465 - "nfl/scripts/backtest_opener.py"
Cohesion: 0.24
Nodes (9): boot(), by_season(), exp_win(), load(), main(), price(), report(), residuals() (+1 more)

### Community 467 - "NFL stale card file cleanup"
Cohesion: 0.15
Nodes (9): card_path(), clear_card(), _load_script(), nfl_path(), test_a_dry_run_leaves_the_card_alone(), test_a_priced_wind_run_with_no_bets_removes_the_earlier_card(), test_clear_card_removes_todays_file_and_only_that(), test_the_path_cleared_is_the_path_the_publisher_reads() (+1 more)

### Community 468 - "tests/test_latest_odds_views.py"
Cohesion: 0.25
Nodes (13): _app_columns(), _function(), test_every_log_table_has_its_insert_trigger_and_the_odds_tables_an_update_trigger(), test_every_view_reads_its_state_table_and_never_the_log(), test_no_pending_view_migration_re_creates_these_views_over_the_log(), test_the_dk_view_returns_the_apps_columns_in_order(), test_the_exclusions_survived_the_move(), test_the_game_view_returns_the_apps_columns_in_order() (+5 more)

### Community 47 - "scripts/nfl_edge_gameline_rules.py"
Cohesion: 0.11
Nodes (42): ats(), bettable_ats(), bh(), board_at(), board_open(), bstat(), cell(), dog_ats_frame() (+34 more)

### Community 472 - "NBA schedule ingestor and tests"
Cohesion: 0.16
Nodes (15): fetch_season(), main(), ot_periods(), run(), schedule_rows(), season_str(), _tv(), write() (+7 more)

### Community 473 - "tests/test_nfl_prop_settle_name_fallback.py"
Cohesion: 0.27
Nodes (10): _never(), _row(), test_a_first_name_the_stat_log_spells_differently_still_matches(), test_a_scratched_player_is_not_graded_on_a_teammate_with_his_initial(), test_a_spelling_the_log_already_knows_is_a_scratch_not_a_spelling(), test_another_game_and_another_initial_never_match(), test_first_name_rule(), test_two_candidates_is_a_miss_not_a_guess() (+2 more)

### Community 474 - "Recap waits for NFL box scores"
Cohesion: 0.17
Nodes (8): _daily(), _job_body(), test_a_malformed_date_is_refused_before_anything_runs(), test_nfl_box_scores_are_ingested_before_settle(), test_nfl_finals_still_precede_the_box_scores(), test_the_job_does_not_read_rowcount_off_the_cursor(), test_the_job_only_clears_its_own_two_ledger_kinds(), test_the_job_posts_both_surfaces_through_the_ordinary_paths()

### Community 475 - "NFL backfill retry tests"
Cohesion: 0.12
Nodes (5): test_a_dropped_connection_is_retried(), test_an_http_error_is_NOT_retried(), test_it_gives_up_rather_than_looping_forever(), test_resume_probes_ONE_market_not_any_row(), test_resume_with_no_probe_market_skips_nothing()

### Community 476 - "tests/test_transaction_pooler.py"
Cohesion: 0.19
Nodes (8): _transaction_endpoint(), test_a_direct_connection_is_left_alone(), test_a_local_postgres_is_left_alone(), test_a_supabase_session_url_becomes_the_transaction_url(), test_it_is_idempotent(), test_only_the_port_changes(), test_the_escape_hatch_works(), test_the_job_queue_still_gets_session_mode()

### Community 477 - "NBA historical odds archive parsing"
Cohesion: 0.13
Nodes (14): _gid(), iso_z(), match(), odds_rows(), snapshot_times(), _swap(), _g(), test_a_labelled_pair_is_never_swapped() (+6 more)

### Community 478 - "MLB totals retrain sweep job tests"
Cohesion: 0.08
Nodes (13): _side_rows(), test_the_raised_timeout_is_restored_after_the_job(), test_the_restore_puts_back_a_pre_existing_value(), test_marker_file_is_in_tree_so_the_freeze_would_not_block_the_worker(), test_missing_artifact_path_refuses_to_sweep_live(), test_over_covers_when_combined_score_beats_the_total_line(), test_price_below_the_house_floor_is_not_a_gradable_side(), test_push_on_the_total_emits_no_sides() (+5 more)

### Community 480 - "Mobile sport filter persistence tests"
Cohesion: 0.14
Nodes (10): _load_body(), _sports(), _src(), test_a_visit_scoped_sport_change_does_not_persist(), test_a_writer_landing_during_the_hydrate_is_not_overwritten(), test_every_sport_survives_a_cold_start(), test_no_retired_sport_is_a_selectable_chip(), test_no_second_hand_written_sport_list_in_the_hook() (+2 more)

### Community 483 - "Trainer no-register mode tests"
Cohesion: 0.13
Nodes (8): not_registering(), registering(), test_a_normal_run_DOES_register(), test_baseline_artifacts_are_not_committable(), test_baseline_runs_write_somewhere_else(), test_default_is_to_register(), test_no_register_opens_no_database_connection(), _explode()

### Community 484 - "NBA game projection player availability"
Cohesion: 0.13
Nodes (10): availability(), injury_at(), lead_bucket(), play_observations(), play_prob(), played_flags(), reallocate(), ridge_with_prior() (+2 more)

### Community 485 - "NHL prop labs"
Cohesion: 0.20
Nodes (12): _ew(), fit_score(), main(), opponent_allowed(), coherent(), fold(), load_prices(), main() (+4 more)

### Community 487 - "supabase/functions/sharpsports/index.ts"
Cohesion: 0.30
Nodes (13): americanFromBetSlip(), asArray(), createContext(), isSettled(), json(), pick(), pullAndUpsert(), readBets() (+5 more)

### Community 489 - "NFL model import path tests"
Cohesion: 0.15
Nodes (6): _import_under_scheduler_env(), _scheduler_env(), test_no_nfl_script_uses_the_bare_models_import(), test_the_card_imports_under_the_schedulers_invocation(), test_the_exemption_is_the_loader_and_it_still_exists(), test_the_loader_reaches_nfls_models_not_the_platforms()

### Community 491 - "NBA second game grid verdict tests"
Cohesion: 0.21
Nodes (20): _cell(), _grid(), _hgrid(), _house(), _mid(), test_a_cell_below_the_bet_count_enters_the_correction_at_p_one(), test_a_cell_clearing_every_bar_passes(), test_a_cell_with_no_dominant_side_is_not_held_to_a_blind_bet() (+12 more)

### Community 495 - "tests/test_worker_deps.py"
Cohesion: 0.22
Nodes (4): _requirements(), test_dashboard_packages_are_not_on_the_worker(), test_only_the_dashboard_imports_them(), test_the_worker_asks_for_the_cpu_build_of_xgboost()

### Community 497 - "College football totals lead study"
Cohesion: 0.26
Nodes (10): build_lead_table(), first_cross(), fmt(), grade(), line_as_of(), load_backfill(), main(), match_frame_to_odds() (+2 more)

### Community 50 - "scheduler.py"
Cohesion: 0.05
Nodes (50): serve_in_thread(), abort_orphaned_refresh_runs(), build_scheduler(), _add_job(), _with_heartbeat(), _wrapped(), catch_up_daily_pipeline(), catch_up_refresh_pass() (+42 more)

### Community 505 - "tests/test_mobile_stat_labels_match_the_server.py"
Cohesion: 0.21
Nodes (6): _meta_entries(), _server_stat_labels(), test_both_rushing_models_call_the_stat_the_same_thing(), test_the_live_model_names_the_market_it_actually_trades(), test_the_parser_actually_found_the_models(), test_the_unreconciled_models_are_named()

### Community 506 - "tests/test_ncaaf_fcs_visitor_names_migration.py"
Cohesion: 0.15
Nodes (5): _rows(), test_each_write_guards_on_its_own_property(), test_every_real_visitor_extends_the_wrong_one(), test_migration_is_one_statement(), test_the_nine_rows_and_their_finals_are_the_measured_ones()

### Community 507 - "tests/test_nfl_prop_unstarted_clear.py"
Cohesion: 0.25
Nodes (8): _apply(), _assert_split(), _between(), _first_sql(), _per_game_sql(), _sweep_sql(), test_per_game_clear_keeps_nfl_prop_rows_on_a_game_the_loop_reaches(), test_sweep_keeps_unstarted_nfl_prop_nones_and_still_clears_game_nones()

### Community 508 - "NBA game model lab and NFL staking"
Cohesion: 0.04
Nodes (77): bh_fdr(), binom_p(), eval_rule(), load(), main(), devig_power(), games(), main() (+69 more)

### Community 512 - "tests/test_savant_freshness.py"
Cohesion: 0.14
Nodes (5): test_rows_are_stamped_with_a_capture_date(), test_savant_has_a_schedule(), test_the_insert_persists_the_stamp(), test_the_savant_job_belongs_to_the_pipeline_service(), test_the_stamp_defaults_rather_than_being_required_at_call_sites()

### Community 513 - "tests/test_scorer_nfl_prop_like_escape.py"
Cohesion: 0.23
Nodes (9): _between(), _broken_per_game_sql(), _first_sql(), _per_game_sql(), _sweep_sql(), test_escape_tripwire_is_on_the_pr_ci_subset(), test_live_per_game_clear_interpolates_with_one_game_id(), test_live_sweep_clear_interpolates_with_date_horizon_now() (+1 more)

### Community 514 - "NBA injury report time slots"
Cohesion: 0.16
Nodes (10): _ampm(), new_slot(), old_slot(), pre_tip_slot(), slots_for_date(), test_format_switch_is_measured_and_both_are_probed_around_it(), test_hourly_dates_get_sixteen_hourly_slots(), test_pre_tip_slot_is_strictly_before_the_tip() (+2 more)

### Community 519 - "Threshold SQL and EV floor notes"
Cohesion: 0.15
Nodes (7): emit(), main(), test_the_emitted_action_filter_cuts_at_the_deciding_price(), Nickname-aware settlement join, nfl_prop_market EV floor 0.20 -> 0.07, MODEL_OWN_EV_FLOOR per model, NFL Monday 2026-09-21: empty Today / Signals

### Community 522 - "SQL escaping and closing-line source tests"
Cohesion: 0.06
Nodes (20): _is_main_guard(), _modules_with_guard(), test_at_least_one_entrypoint_is_scanned(), test_nothing_is_defined_after_the_main_guard(), _fn(), test_a_missing_bet_book_close_is_not_filled_from_another_book(), test_backfill_revisits_anything_that_is_not_standard_v2(), test_capture_grades_raw_same_book_and_a_separate_pinnacle_edge() (+12 more)

### Community 524 - "Paused and no-signal pick rows"
Cohesion: 0.14
Nodes (11): _apply_no_signal(), _game_pick(), _prop_pick(), test_auto_paused_counts_as_paused(), test_no_signal_rows_persist_the_reason(), test_paused_game_model_avoid_stays_avoid_with_reason(), test_paused_game_model_bet_stays_bet_with_reason_and_stake(), test_paused_prop_model_avoid_stays_avoid_with_reason() (+3 more)

### Community 525 - "College football starter-out study"
Cohesion: 0.27
Nodes (8): build_sample(), grade(), _line(), load_qb_log(), main(), report(), starter_status(), wilson()

### Community 526 - "NFL prop lean concentration study"
Cohesion: 0.25
Nodes (7): add_context(), boot(), main(), profit(), report(), tercile_split(), under_profit()

### Community 527 - "Dashboard rule model display tests"
Cohesion: 0.14
Nodes (5): test_a_rule_carries_a_cut_but_is_in_no_training_registry(), test_a_rule_is_not_styled_as_a_warning(), test_a_rule_sorts_with_the_live_models_not_the_broken_ones(), test_the_roster_query_flags_rules(), test_the_summary_counts_rules_apart_from_outages()

### Community 529 - "tests/test_clear_unauthorized_auto_pauses_migration.py"
Cohesion: 0.19
Nodes (6): _stmts(), test_clearing_auto_pauses_did_not_park_batter_runs(), test_it_clears_the_whole_auto_pause_table(), test_it_does_not_touch_picks_thresholds_or_the_review_ledger(), test_it_no_ops_when_the_table_is_missing_or_already_empty(), test_migration_is_one_statement()

### Community 53 - "Declared worker job validation tests"
Cohesion: 0.15
Nodes (7): _declared(), test_an_explicit_run_date_must_be_a_real_iso_date(), test_declared_keys_are_unique(), test_every_declared_job_names_a_registered_type(), test_every_declared_job_validates(), test_no_run_date_means_the_module_resolves_it(), test_the_validator_drops_unknown_args()

### Community 530 - "tests/test_ncaaf_se_louisiana_alias_migration.py"
Cohesion: 0.15
Nodes (4): test_a_pick_is_never_deleted_and_never_regraded(), test_it_guards_on_both_names_and_both_still_unscored(), test_migration_is_one_statement(), test_odds_move_only_when_canonical_has_none()

### Community 531 - "NCAAF quarterback ablation study"
Cohesion: 0.23
Nodes (7): _fit(), main(), _report(), run(), summarise(), walk_forward(), wilson()

### Community 532 - "tests/test_overnight_polling.py"
Cohesion: 0.24
Nodes (7): _hours(), _jobs(), _match(), test_every_hour_of_the_day_is_covered(), test_the_overnight_pass_is_the_ordinary_one(), test_the_overnight_window_exists(), test_the_windows_do_not_overlap()

### Community 536 - "College football loop timing tests"
Cohesion: 0.15
Nodes (7): _main_source(), test_an_unanswered_state_feed_does_not_look_like_the_slate_ending(), test_loop_exits_early_when_no_kickoff_is_near(), test_loop_polls_at_the_idle_cadence_when_nothing_is_live(), test_loop_sleeps_the_remainder_not_a_flat_interval(), test_loop_warns_when_a_pass_overruns_its_interval(), test_odds_fetch_uses_the_odds_cadence_not_the_loop_cadence()

### Community 537 - "NFL Kalshi price history fetch"
Cohesion: 0.21
Nodes (6): candles(), get(), map_games(), paged(), parse_event(), probe()

### Community 541 - "College football live underdog correction"
Cohesion: 0.18
Nodes (11): brier(), conditional_table(), fit_logistic(), load(), logit(), logloss(), main(), design() (+3 more)

### Community 542 - "NCAAF situational spot search"
Cohesion: 0.26
Nodes (5): build_spots(), evaluate(), load_team_games(), main(), wilson()

### Community 546 - "tests/test_claude_rules_split.py"
Cohesion: 0.18
Nodes (4): test_claude_md_still_points_at_the_rules_directory(), test_every_rule_file_actually_carries_rules(), test_every_rule_file_is_path_scoped(), test_no_rule_was_lost_when_the_split_happened()

### Community 547 - "NBA line move fit helpers"
Cohesion: 0.15
Nodes (7): close_times(), consensus(), f1b_coefficients(), fit_move(), move_rows(), mu_frame(), ols()

### Community 548 - "tests/test_dedupe_opening_signals.py"
Cohesion: 0.10
Nodes (9): test_a_graded_row_is_never_deleted(), test_a_row_with_computed_clv_is_never_deleted(), test_every_field_that_defines_the_bet_must_agree(), test_it_is_dry_run_by_default(), test_the_delete_selects_through_the_same_gates(), test_the_pair_must_be_an_old_shape_new_shape_pair(), test_the_report_and_the_delete_share_one_definition(), test_the_row_kept_is_the_one_locked_earlier() (+1 more)

### Community 551 - "Live model holdout side-by-side comparison"
Cohesion: 0.31
Nodes (6): bias_table(), confident_share(), load_artifact(), main(), poisson_sf(), predict()

### Community 552 - "tests/test_pbp_backfill_resilience.py"
Cohesion: 0.24
Nodes (6): _backfill_body(), test_a_failed_game_rolls_the_connection_back(), test_a_run_that_wrote_nothing_reports_an_error_not_a_success(), test_errors_are_counted_not_just_logged(), test_partial_failures_are_surfaced_too(), test_the_rollback_cannot_itself_raise()

### Community 553 - "College football line move spots"
Cohesion: 0.27
Nodes (6): eval_follow_spread(), eval_follow_total(), load(), main(), _summ(), wilson()

### Community 559 - "College football quarterback features"
Cohesion: 0.22
Nodes (8): load_qb_games(), merge_qb_features(), _games(), _qb_team(), test_either_changed_is_a_game_level_flag_the_diff_would_cancel(), test_every_declared_feature_is_actually_produced(), test_missing_qb_table_yields_nan_columns_not_a_crash(), test_positive_diff_always_means_good_for_home()

### Community 562 - "Live game discovery across dates"
Cohesion: 0.18
Nodes (7): _discover_active_games(), _game_id_from_statsapi(), test_a_game_seen_twice_is_polled_once(), test_discovery_asks_statsapi_about_every_date_it_is_given(), fake_schedule(), test_discovery_still_accepts_a_bare_string(), test_one_broken_date_does_not_lose_the_other()

### Community 563 - "NFL prop tick window tests"
Cohesion: 0.11
Nodes (8): test_days_is_derived_from_the_window_not_pinned(), test_every_live_nfl_prop_model_still_carries_its_own_cut(), test_the_live_ten_are_not_a_clean_bill_of_health(), test_the_tick_passes_a_days_that_covers_the_whole_window(), test_the_tick_returns_free_outside_the_window(), test_the_twelve_distributional_models_score_off_the_ticks_own_fetch(), test_the_window_reaches_at_least_the_ten_day_horizon_the_other_nfl_jobs_use(), test_twelve_are_live_and_none_is_paused()

### Community 566 - "Live money record-only guard tests"
Cohesion: 0.43
Nodes (4): _allowed(), _hits(), _rel(), test_the_repo_has_no_record_only_or_paper_tracking_mode()

### Community 568 - "NFL prop book sweep"
Cohesion: 0.25
Nodes (6): soft_verdict(), test_a_bettable_book_still_passes(), test_an_unbettable_book_is_excluded_however_good_its_numbers(), test_every_incumbent_soft_book_is_bettable(), test_the_clause_is_not_dead_code(), _verdict()

### Community 572 - "NHL regulation own probability tests"
Cohesion: 0.17
Nodes (4): mapped(), test_nyr_regulation_2026_10_02_is_not_a_bet(), test_the_correction_does_not_touch_a_regulation_probability(), test_the_rebuilt_moneyline_decides_on_its_own_probability()

### Community 573 - "NBA public splits pipeline step"
Cohesion: 0.18
Nodes (10): inserted_minus_start_min(), test_v1_inserted_lag_is_minutes_after_the_listed_start(), Coverage, Forward capture (2026-27), How to read it, NBA public betting splits (Action Network) — `nba_public_splits`, Rows to leave out, Source (+2 more)

### Community 574 - "tests/test_prompt_reads_thresholds.py"
Cohesion: 0.18
Nodes (4): test_the_auto_pause_lookup_fails_open(), test_the_prompt_carries_no_per_model_cut(), test_the_prompt_still_says_it_is_pasted_once(), test_the_sync_mirrors_both_pause_registers()

### Community 575 - "NFL prop pulled quote filter"
Cohesion: 0.32
Nodes (8): drop_pulled_quotes(), _ts(), _q(), test_a_book_on_its_own_cadence_is_not_penalised_inside_three_hours(), test_a_book_that_stopped_returning_the_game_is_dropped(), test_a_player_the_book_stopped_quoting_is_dropped(), test_a_whole_market_the_book_pulled_is_dropped(), test_rows_from_one_fetch_minutes_apart_are_kept_and_a_line_move_is_not_a_pull()

### Community 577 - "NBA quarter scores parser"
Cohesion: 0.19
Nodes (13): ensure_table(), fetch_date(), _int(), main(), parse_period_rows(), run(), write(), _event() (+5 more)

### Community 580 - "scripts/render_brand_icons.py"
Cohesion: 0.24
Nodes (3): draw_mark(), main(), render()

### Community 581 - "NFL wind stake sizing tests"
Cohesion: 0.22
Nodes (6): _probe(), test_an_uncalibrated_lead_is_sized_rather_than_zeroed_on_the_card(), test_at_the_default_gate_that_same_row_does_not_fire_at_all(), test_the_eval_board_agrees_with_the_card(), test_the_probability_was_already_clipping(), test_the_stake_clips_to_lead_seven_instead_of_returning_zero()

### Community 586 - "supabase/functions/stripe-webhook/index.ts"
Cohesion: 0.31
Nodes (9): applySubscription(), iso(), resolveUserId(), stripeGet(), timingSafeEqual(), toHex(), verifySignature(), admin (+1 more)

### Community 588 - "NHL prop alternate line calls"
Cohesion: 0.20
Nodes (7): _book(), test_a_200_on_both_calls_merges_the_alternate_lines(), fake_fetch(), test_an_exception_on_the_alternate_call_keeps_the_featured_lines(), fake_fetch(), test_open_close_and_final_each_ask_for_the_alternate_lines(), fake_fetch()

### Community 589 - "tests/test_mobile_neutral_signal_label.py"
Cohesion: 0.31
Nodes (7): _read(), test_explainer_names_neutral(), test_filters_and_card_speak_the_display_name(), test_model_screens_speak_the_display_name(), test_no_member_label_prints_a_raw_signal_type(), test_none_badge_reads_neutral(), test_withdrawn_pick_is_not_badged_neutral()

### Community 591 - "College football CFBD game parsing"
Cohesion: 0.12
Nodes (15): parse_games(), retain_existing_cfbd_ids(), _check(), _lines_coverage(), main(), _null_report(), _sample_keys(), test_parse_games_dates_a_night_kick_by_et_not_utc() (+7 more)

### Community 593 - "tests/test_scorer_commits_per_game.py"
Cohesion: 0.40
Nodes (8): _between(), _run_scorer_body(), test_a_lost_connection_re_runs_the_game_once_and_never_the_pass(), test_each_game_is_its_own_committed_unit(), test_no_bulk_delete_of_non_bet_rows_precedes_the_loop(), test_picks_are_only_counted_once_the_game_committed(), test_the_housekeeping_delete_is_a_sweep_after_the_loop(), test_the_outer_handler_still_records_the_failure()

### Community 594 - "NCAAF scoreboard yardline parsing tests"
Cohesion: 0.21
Nodes (6): _abbrev_fits(), _parse_yardline(), _cfbd_game(), test_cfbd_state_carries_the_yardline_and_the_raw_situation(), test_cfbd_yardline_from_every_stored_situation(), test_cfbd_yardline_refuses_rather_than_guesses()

### Community 596 - "College football totals weather study"
Cohesion: 0.31
Nodes (7): sweep_total(), arm_frame(), load_issued(), main(), run_arm(), wilson(), test_total_grading_both_sides_and_push()

### Community 597 - "Database setup column tests"
Cohesion: 0.23
Nodes (6): _get_columns(), test_games_table_columns(), test_injuries_table_columns(), test_odds_table_columns(), test_picks_table_columns(), test_schema_is_idempotent()

### Community 598 - "College football stats ingestion"
Cohesion: 0.08
Nodes (22): _int(), _num(), parse_advanced_stats(), parse_ratings(), parse_returning(), parse_season_stats(), parse_talent(), parse_team_game_stats() (+14 more)

### Community 60 - "tests: test_wnba_availability + wnba_availability"
Cohesion: 0.06
Nodes (50): absence_features(), absent_teammates(), build_context_features(), expected_rotation(), is_starter_tier(), _mean(), prior_rows(), recent_team_game_dates() (+42 more)

### Community 600 - "Retrain job validation"
Cohesion: 0.18
Nodes (7): test_a_real_model_id_validates(), test_a_retrain_defaults_to_not_registering(), test_a_retrain_raises_its_own_statement_timeout(), test_the_timeout_is_bounded_at_both_ends(), _validate_mlb_over_under_retrain_sweep(), _validate_mlb_runline_retrain_sweep(), _validate_retrain()

### Community 604 - "Live cut sweep decision tests"
Cohesion: 0.27
Nodes (4): decide(), test_decide_agrees_with_classify_live_signal(), test_decide_caps_on_the_raw_edge_when_a_map_is_promoted(), test_first_signal_lock_takes_the_earliest_qualifier()

### Community 606 - "NFL prop universe summary tests"
Cohesion: 0.29
Nodes (6): _universe_summary(), test_a_universe_without_the_model_sums_still_summarises(), test_mean_projection_and_mean_actual_separate_mean_bias_from_shape_bias(), test_model_over_rate_and_its_gap_are_reported(), _universe(), test_a_nonfinite_fair_price_cannot_switch_the_gate_off()

### Community 608 - "supabase/functions/sharpsports-webhook: index + index"
Cohesion: 0.25
Nodes (5): internalIdFor(), pick(), admin, admin, cors

### Community 609 - "NHL backtest player namesakes"
Cohesion: 0.38
Nodes (6): namesakes(), _frame(), test_a_namesake_who_played_for_the_team_last_season_still_counts(), test_a_unique_name_is_kept(), test_namesakes_on_two_teams_collide_only_when_those_teams_meet(), test_two_teammates_with_one_name_are_both_refused()

### Community 61 - "NHL artifact grading and underdog grid"
Cohesion: 0.05
Nodes (67): accuracy(), first_games(), logloss(), main(), sweep(), units(), walk(), artifact() (+59 more)

### Community 612 - "supabase/functions/stripe-checkout/index.ts"
Cohesion: 0.31
Nodes (8): customerFor(), form(), json(), stripe(), admin, cors, PRICES, TRIAL_DAYS

### Community 614 - "tests/test_book_list_budget.py"
Cohesion: 0.31
Nodes (4): _names(), test_every_book_the_nfl_prop_model_bets_at_is_actually_fetched(), test_the_nfl_prop_pull_is_one_group_with_both_references_in_it(), test_the_shared_list_is_one_group()

### Community 615 - "Live orchestrator trigger tests"
Cohesion: 0.20
Nodes (5): _consume_source(), test_a_floor_pass_scores_every_live_game_not_just_triggered_ones(), test_no_pending_triggers_no_longer_short_circuits_unconditionally(), test_the_fetch_is_never_asked_for_every_event_the_feed_returns(), test_the_floor_is_gated_on_a_game_actually_being_live()

### Community 617 - "API call daily rollup"
Cohesion: 0.09
Nodes (10): test_a_fold_can_never_lower_a_stored_total(), test_a_new_process_does_not_prune_on_its_first_flush(), test_prune_rolls_up_before_it_deletes(), test_the_daily_table_is_created_and_locked_down(), test_the_daily_table_keys_on_day_api_and_source(), test_the_rollup_groups_by_eastern_day_not_utc(), test_the_rollup_reads_only_yesterday_and_today(), test_the_rollup_survives_a_failure_without_blocking_the_prune() (+2 more)

### Community 62 - "NBA game market search lab"
Cohesion: 0.05
Nodes (60): assemble(), attach_close(), bars(), bet_frame(), blind_bets(), blind_first_fetch(), boot_ci(), by_season() (+52 more)

### Community 620 - "NBA game search cell emission tests"
Cohesion: 0.22
Nodes (6): _emit_world(), _spy_run_cells(), test_closing_value_is_priced_with_the_markets_empirical_distribution(), test_every_family_emits_exactly_its_cells_through_the_harness(), test_the_d_cells_are_gated_on_the_points_own_decision_times(), test_the_bootstrap_is_seeded_and_refines_small_p()

### Community 622 - "SBR odds CSV loader"
Cohesion: 0.25
Nodes (3): canonical_abbrev(), parse_csv_file(), test_sbr_abbreviations_are_canonicalised_for_mlb_only()

### Community 623 - "NHL probable goalie parsing"
Cohesion: 0.14
Nodes (9): _default_fetch(), fetch_espn_nhl_probables(), _https(), parse_probable(), _team_abbrev(), test_fetch_fail_open(), test_fetch_uses_injected_fetch_and_keys_by_our_abbrev(), test_parse_probable_joins_display_name_to_our_abbrev() (+1 more)

### Community 624 - "NCAAF steam lag study"
Cohesion: 0.27
Nodes (9): attach_scores(), build_events(), fmt(), grade(), lines_at_pulls(), load(), main(), summarise() (+1 more)

### Community 629 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.47
Nodes (6): contentHeight(), evalExpr(), lineOf(), styleBlock(), styleProp(), visualHeight()

### Community 63 - "Football in-play game state"
Cohesion: 0.07
Nodes (25): _as_float(), _as_int(), _as_opt_float(), _as_opt_int(), from_espn(), from_extract(), from_pbp_row(), smooth_pass_rate() (+17 more)

### Community 632 - "MLB live state extraction"
Cohesion: 0.22
Nodes (7): _bases_state(), _extract_state(), test_bases_state_empty(), test_bases_state_loaded(), test_bases_state_single_runner(), test_extract_state_handles_empty_feed(), test_extract_state_pulls_fields_from_live_feed()

### Community 633 - "Model quality CLV and ROI alerts"
Cohesion: 0.14
Nodes (8): test_clv_clear_negative_vs_baseline_is_flagged(), test_raw_one_sided_clv_is_ignored(), test_roi_collapse_is_crit_when_hit_rate_dies(), test_roi_ignores_unpriced_profit_flat(), detect_clv_degradation(), detect_roi_collapse(), _sample(), units_from_profit_flat()

### Community 634 - "College football feed outage tests"
Cohesion: 0.22
Nodes (5): _feed_with_payload(), test_a_sustained_feed_outage_degrades_to_no_odds(), test_cached_odds_are_served_while_fresh(), test_credit_cap_reports_no_odds_rather_than_a_frozen_line(), test_credit_cap_still_serves_a_payload_that_is_still_fresh()

### Community 635 - "tests/test_demote_ncaaf_over_under_platt.py"
Cohesion: 0.32
Nodes (4): _stmts(), test_it_demotes_only_the_measured_promotion(), test_it_does_not_move_the_gate_the_floor_or_a_pause(), test_migration_is_one_statement()

### Community 636 - "MLB runline retrain sweep job"
Cohesion: 0.13
Nodes (5): test_marker_file_is_in_tree_so_the_freeze_would_not_block_the_worker(), test_missing_artifact_path_refuses_to_sweep_live(), test_retrain_then_sweep_passes_the_new_path(), test_the_runner_retrains_then_sweeps_the_new_artifact(), _job_mlb_runline_retrain_sweep()

### Community 637 - "tests/test_discord_post_one_pick_migration.py"
Cohesion: 0.29
Nodes (3): _pairs(), test_it_names_each_measured_extra_and_the_row_kept(), test_the_update_does_not_rewrite_the_graded_outcome()

### Community 638 - "tests/test_game_scorer_spares_nfl_props.py"
Cohesion: 0.43
Nodes (5): _between(), _run_scorer_body(), test_an_nfl_game_never_enters_the_per_game_clear(), test_both_live_non_bet_clears_leave_nfl_rows(), test_the_left_out_ufc_clear_only_removes_unsettled_non_bets()

### Community 639 - "NBA projection settlement tests"
Cohesion: 0.22
Nodes (3): _settle(), test_each_market_settles_either_side_from_the_box(), test_every_label_passes_the_publishing_check()

### Community 641 - "tests/test_mobile_ota_self_update.py"
Cohesion: 0.32
Nodes (4): _read(), test_app_root_mounts_the_ota_updater(), test_the_pieces_exist(), test_the_updater_actually_applies_the_update()

### Community 65 - "NFL in-play flow model tests"
Cohesion: 0.03
Nodes (69): bias_table(), main(), apply_anchor(), best_hit(), _boot_ci(), drop_degenerate(), evaluate(), fit_time_curve() (+61 more)

### Community 656 - "Health check cadence reading"
Cohesion: 0.29
Nodes (5): test_cadence_reads_a_daily_bar_off_the_dates(), test_cadence_reads_a_multi_day_window(), test_cadence_reads_a_same_day_bar(), test_cadence_survives_a_missing_or_unparseable_date(), _cadence_from_dates()

### Community 658 - "NFL prop parameters match artifacts"
Cohesion: 0.33
Nodes (3): _models(), _newest_artifact(), test_params_file_carries_the_newest_artifacts_hyperparameters()

### Community 659 - "NHL game parsing tests"
Cohesion: 0.38
Nodes (9): parse_nhl_game(), _g(), test_arizona_folds_into_utah(), test_missing_teams_returns_none(), test_ot_home_win_is_regulation_draw(), test_preseason_game_skipped(), test_regulation_home_win(), test_scheduled_game_has_no_scores() (+1 more)

### Community 663 - "College football consensus gate study"
Cohesion: 0.39
Nodes (6): fmt(), grade(), load_closes(), main(), match(), wilson()

### Community 666 - "Revoke remaining write grants tests"
Cohesion: 0.15
Nodes (6): test_it_asserts_the_app_write_surface_survives(), test_it_revokes_every_write_privilege(), test_select_is_never_revoked(), test_the_roles_are_named_never_public(), test_the_runners_transaction_stripping_leaves_the_do_block_intact(), test_the_set_is_computed_from_the_policy_rule_not_listed()

### Community 669 - "Published record units"
Cohesion: 0.04
Nodes (43): test_a_loss_costs_the_full_stake_and_a_push_costs_nothing(), test_a_pick_with_no_price_stays_in_the_units_at_bare_conviction(), test_a_six_column_row_still_tallies(), test_a_snapshot_with_no_clv_stores_null_not_zero(), test_conviction_floors_at_one_not_a_half(), test_conviction_is_flat_for_every_kelly(), test_conviction_is_flat_regardless_of_kelly(), test_every_graded_pick_counts_in_units_at_its_taken_price() (+35 more)

### Community 673 - "Scorer keeps off-DraftKings priced bets tests"
Cohesion: 0.29
Nodes (6): _bet(), db(), _left(), _statement(), test_a_bet_priced_at_another_books_line_survives_and_a_bet_with_no_price_does_not(), test_the_statement_names_both_prices()

### Community 677 - "Drop voided NFL prop signals tests"
Cohesion: 0.23
Nodes (6): _stmts(), test_it_deletes_exactly_the_three_measured_lock_keys(), test_it_does_not_touch_picks_or_discord(), test_it_still_skips_a_key_that_has_a_standing_bet(), test_migration_is_one_statement(), test_standing_pick_uses_lock_key_sql_not_player_id()

### Community 692 - "NFL prop scorer kickoff ceiling"
Cohesion: 0.30
Nodes (8): _nfl_prop_too_early(), _iso(), test_a_kickoff_beyond_the_ceiling_is_too_early(), test_a_started_or_unknown_kickoff_is_not_too_early(), test_the_boundary_is_inclusive_at_the_ceiling(), test_the_scorer_and_the_card_read_ONE_constant(), test_the_scorer_loop_actually_applies_the_ceiling(), test_the_z_suffix_parses_like_the_offset_form()

### Community 693 - "NCAAF structural spot scan"
Cohesion: 0.16
Nodes (5): is_bowl_game(), load_data(), main(), scan_spot(), test_is_bowl_game()

### Community 695 - "Every named sportsbook is fetched"
Cohesion: 0.18
Nodes (5): _param_books(), test_a_sharp_reference_is_never_also_a_soft_book(), test_every_bettable_book_can_be_named_to_a_human(), test_every_named_book_is_in_the_pull_that_serves_it(), test_the_nfl_backfill_defaults_to_the_live_pull()

### Community 697 - "Weather game hour helpers"
Cohesion: 0.33
Nodes (3): _game_hour_utc(), _target_hour_utc(), _utc_offset_from_lon()

### Community 701 - "NFL tackles total target"
Cohesion: 0.39
Nodes (5): _derive(), _frame(), test_a_game_log_without_the_column_cannot_build_tackles(), test_the_ingestor_carries_tackles_with_assist(), test_the_target_is_the_box_score_total()

### Community 705 - "Mobile stats filter checks"
Cohesion: 0.18
Nodes (9): chip, lineOnlyFn, playersDay, ROOT, sportReset, stats, teams, teamsDay (+1 more)

### Community 707 - "NHL goalie line helpers"
Cohesion: 0.83
Nodes (4): _goalie_line(), regressed(), saved_above(), tot()

### Community 708 - "Registered but not firing models tests"
Cohesion: 0.14
Nodes (5): test_a_model_with_picks_but_no_threshold_row_is_still_listed(), test_it_reports_whether_the_model_is_paused_and_whether_it_is_trained(), test_performance_starts_from_the_registered_models_not_the_graded_picks(), test_the_sport_survives_when_there_are_no_graded_picks(), test_the_zero_state_short_circuits_before_the_roi_row()

### Community 71 - "tests/test_live_orchestrator.py"
Cohesion: 0.05
Nodes (35): should_fetch(), split_triggers(), under_credit_cap(), apply_daily_cap(), classify_live_signal(), _ev_floor(), test_live_signal_is_refused_under_the_global_floor(), _t() (+27 more)

### Community 712 - "NFL standings and division flags"
Cohesion: 0.33
Nodes (4): conference(), divisions(), f(), standings_flags()

### Community 713 - "NBA game search cache checks"
Cohesion: 0.33
Nodes (3): _games_file(), test_a_segment_file_missing_part_of_a_season_is_refused(), test_full_checks_the_price_cache_for_every_graded_season_before_building_anything()

### Community 717 - "NFL in-play lag summaries"
Cohesion: 0.15
Nodes (15): h1_calibration(), h1_frame(), lagbook(), lagbook_catchup(), lagbook_groups(), summ(), async_check(), boot() (+7 more)

### Community 719 - "Mobile accessibility verify script"
Cohesion: 0.67
Nodes (3): read(), readUtf8(), verticalSlop()

### Community 72 - "Market handicap feature tests"
Cohesion: 0.03
Nodes (59): diff(), pitcher_diff(), diff(), pitcher_diff(), coerce_numeric_features(), feature_matrix(), numeric_feature_value(), attach_market_handicap() (+51 more)

### Community 721 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.67
Nodes (3): closeOf(), openTag(), toggleUse()

### Community 730 - "NFL research backup"
Cohesion: 0.44
Nodes (5): backup(), files(), main(), restore(), verify()

### Community 74 - "Prop CLV and SQL escaping tests"
Cohesion: 0.09
Nodes (17): _fn(), test_a_backfill_failure_never_breaks_settlement(), test_a_pick_is_only_stamped_captured_once_a_measure_resolved(), test_a_pick_stamped_after_first_pitch_is_never_measured(), test_a_prop_pick_whose_label_has_no_name_is_skipped_not_guessed(), test_both_guards_agree(), test_clv_pct_never_compares_prices_across_a_moved_line(), test_golf_stays_excluded() (+9 more)

### Community 75 - "College football margin evaluation"
Cohesion: 0.21
Nodes (11): build_frames(), _fit(), fit_and_register(), fit_and_register_totals(), main(), _matrix(), _print_sweep(), rmse() (+3 more)

### Community 758 - "NCAAF game feature assembly"
Cohesion: 0.22
Nodes (3): _assemble_ncaaf_features(), _game_tier(), test_season_opener_gets_a_zero_rest_differential_not_a_null()

### Community 76 - "ncaaf_live/tests/test_serve.py"
Cohesion: 0.05
Nodes (56): _clock_seconds(), extract_live_states_cfbd(), _parse_situation(), check_feed_assumptions(), _competitors(), _count_plays(), _dig(), extract_live_events() (+48 more)

### Community 82 - "Mobile script test runner via Node"
Cohesion: 0.11
Nodes (24): _load_state_dir(), _raw_error_lines(), _read(), _run_node(), test_aborts_are_silent_and_offline_slow_are_narrow(), test_aborts_render_nothing_and_every_catch_skips_them(), test_designer_review_fixes_behaviour(), test_error_state_component() (+16 more)

### Community 850 - "Health check lateness wording"
Cohesion: 0.40
Nodes (3): test_a_late_check_says_how_late(), test_days_late_falls_back_rather_than_lying(), _days_late()

### Community 852 - "Mobile NHL look-ahead window tests"
Cohesion: 0.29
Nodes (5): _fn(), _read(), test_the_nhl_read_matches_the_other_look_aheads(), test_the_sport_chip_is_the_hook_not_an_allowlist(), test_use_today_picks_fetches_nhl_across_that_window()

### Community 86 - "scripts/nfl_edge_preregistered_2026.py"
Cohesion: 0.09
Nodes (38): bar(), bets_frame(), bh(), binom_line(), _by_game(), cell(), fam(), first_last() (+30 more)

### Community 862 - "Insert column alignment test"
Cohesion: 0.32
Nodes (3): _statements(), test_columns_and_values_line_up(), test_the_scorer_pick_insert_is_actually_covered()

### Community 87 - "tests: test_player_positions + player_positions_ingestor"
Cohesion: 0.06
Nodes (29): _basketball(), basketball_group(), _fresh_source_ids(), _get_json(), ingest_player_positions(), match_to_log(), _name_index(), _ncaaf() (+21 more)

### Community 874 - "NBA play clock and shot parsing"
Cohesion: 0.29
Nodes (4): classify_field_goal(), parse_clock(), test_field_goal_value(), test_parse_clock()

### Community 88 - "NBA prop market decision tests"
Cohesion: 0.08
Nodes (33): fair_under(), q(), run(), run_full(), _settle(), test_a_fetch_after_now_or_at_tip_and_a_close_row_never_decide(), test_a_fetch_older_than_the_window_is_not_a_price(), test_a_game_already_bet_is_never_decided_again() (+25 more)

### Community 885 - "NBA SBR archive moneyline timing"
Cohesion: 0.40
Nodes (3): ml_timing(), sign_agreement(), test_ml_timing_and_sign_agreement_count_what_they_say()

### Community 89 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.04
Nodes (48): a11ySrc, allowHit, ALLOWLIST, app, badExempt, bar, bareClose, baselineLeft (+40 more)

### Community 893 - "Pre-game line poller"
Cohesion: 0.05
Nodes (33): changed_rows(), over_credit_cap(), _row(), _run_scorer_body(), test_a_failed_tick_does_not_kill_the_loop(), test_a_failed_tick_throws_the_map_away(), test_a_full_board_call_still_passes_no_subset(), test_a_link_or_selection_id_churning_is_not_a_change() (+25 more)

### Community 98 - "NBA play-by-play ingestor"
Cohesion: 0.05
Nodes (50): active_queries(), alias_map_rows(), _bool(), box_context(), box_finals(), build_game(), build_gap_game(), build_map() (+42 more)

### Community 99 - "App live segment wiring tests"
Cohesion: 0.06
Nodes (28): _read(), test_a_sport_switch_cannot_report_a_game_finishing(), test_all_three_segments_are_unconditional(), test_live_is_not_a_bottom_tab(), test_live_is_not_in_the_tab_param_list(), test_no_app_root_component_reaches_a_focus_aware_hook(), imports_of(), strip_comments() (+20 more)

### Community 106 - "Supabase schema tables"
Cohesion: 0.03
Nodes (101): api_call_log, device_push_tokens, feedback_messages, feedback_threads, fighters, golf_players, golf_rounds, idx_api_call_api_ts (+93 more)

### Community 179 - "mobile/app.json"
Cohesion: 0.05
Nodes (38): backgroundColor, foregroundImage, adaptiveIcon, package, projectId, expo, android, extra (+30 more)

### Community 184 - "mobile/package.json"
Cohesion: 0.09
Nodes (23): dependencies, expo, expo-asset, expo-dev-client, expo-font, expo-notifications, expo-status-bar, expo-updates (+15 more)

### Community 202 - "Games and latest odds views"
Cohesion: 0.05
Nodes (41): public.v_latest_inplay_odds_all_books, public.v_latest_prop_odds_all_books, public.v_latest_prop_odds_all_books, public.latest_lines_rebuild_odds(), public.latest_odds_recompute(), public.latest_prop_odds_recompute(), public.v_latest_odds_all_books, public.v_latest_prop_odds_all_books (+33 more)

### Community 304 - "Player game log RPCs"
Cohesion: 0.08
Nodes (25): public.v_model_full_outcome_picks, public.player_recent_games_mlb(), public.player_recent_games_nba(), public.player_recent_games_wnba(), public.player_season_stat_values_mlb(), public.player_season_stat_values_nba(), public.player_season_stat_values_wnba(), public.v_model_full_outcome_record (+17 more)

### Community 344 - "Picks and public track record views"
Cohesion: 0.09
Nodes (19): v_opening_signal_slices, v_opening_vs_live, public.v_public_track_record, public.v_public_track_record_daily, public.v_public_track_record, public.v_public_track_record_daily, public.v_public_track_record, public.v_public_track_record_daily (+11 more)

### Community 362 - "Latest line state tables"
Cohesion: 0.15
Nodes (18): public.latest_lines_rebuild_props(), public.latest_live_game_state, public.latest_live_game_state_on_insert(), public.latest_odds, public.latest_odds_on_insert(), public.latest_odds_on_update(), public.latest_prop_odds, public.latest_prop_odds_on_insert() (+10 more)

### Community 481 - "mobile/tsconfig.json"
Cohesion: 0.13
Nodes (14): compilerOptions, esModuleInterop, jsx, module, moduleResolution, noUncheckedIndexedAccess, paths, resolveJsonModule (+6 more)

### Community 494 - "Discord link and Whop memberships"
Cohesion: 0.16
Nodes (14): discord_links, idx_discord_links_discord_user, idx_discord_links_email, idx_whop_memberships_discord, idx_whop_memberships_email, idx_whop_memberships_valid, public.app_subscription_access_for(), public.discord_access_for() (+6 more)

### Community 602 - "Feedback threads migration"
Cohesion: 0.36
Nodes (10): feedback_messages, feedback_threads, idx_feedback_messages_thread, idx_feedback_threads_device, idx_feedback_threads_status, public.feedback_messages_for_thread(), public.feedback_reply(), public.feedback_submit() (+2 more)

### Community 605 - "NFL prop modeling tables"
Cohesion: 0.27
Nodes (10): idx_nfl_plog_normname, idx_nfl_snaps_join, idx_nfl_snaps_season, idx_nfl_tgs_opp, idx_nfl_tgs_season, idx_nfl_tgs_team, nfl_snap_counts, nfl_team_game_stats (+2 more)

### Community 607 - "railway.json"
Cohesion: 0.22
Nodes (8): build, builder, watchPatterns, deploy, numReplicas, restartPolicyType, startCommand, $schema

### Community 610 - "NHL game logs migration"
Cohesion: 0.29
Nodes (11): idx_nhl_goalie_game_log_player_date, idx_nhl_goalie_game_log_source, idx_nhl_goalie_game_log_team_date, idx_nhl_skater_game_log_player_date, idx_nhl_skater_game_log_source, idx_nhl_skater_game_log_team_date, idx_nhl_team_game_log_source, idx_nhl_team_game_log_team_date (+3 more)

### Community 618 - "Team stats board tables"
Cohesion: 0.17
Nodes (9): public.team_stats_board(), idx_mlb_team, idx_nba_team, idx_nhl_team, idx_wnba_team, mlb_team_stats, nba_team_stats, nhl_team_stats (+1 more)

### Community 619 - "Decide on best price migration"
Cohesion: 0.23
Nodes (5): mv_scored_pick_outcomes_model_idx, mv_scored_pick_outcomes_pick_id_idx, public.v_model_full_outcome_picks, public.v_model_full_outcome_record, public.v_model_full_record

### Community 628 - "Mobile app build scripts"
Cohesion: 0.25
Nodes (8): scripts, android, build:ios:preview, build:ios:production, ios, start, typecheck, web

### Community 648 - "Disk IO indexes migration"
Cohesion: 0.18
Nodes (5): idx_live_state_snapshot, idx_odds_book_snap, idx_picks_game, idx_player_game_log_name, idx_prop_odds_snapshot

### Community 654 - "Live game state tables"
Cohesion: 0.20
Nodes (9): v_live_game_state_latest, public.latest_lines_rebuild_live_state(), idx_live_state_game, idx_live_state_snapshot, idx_live_trigger_game, idx_live_trigger_pending, live_game_state, live_trigger_events (+1 more)

### Community 657 - "NHL moneyline rebuild write-up"
Cohesion: 0.29
Nodes (6): Method, NHL moneyline, rebuilt (2026-10-13), Read, Results, The production version, and two checks on it (2026-10-13/14), What the live model has, and what it was missing

### Community 661 - "NCAAF player stats leaderboard"
Cohesion: 0.42
Nodes (8): idx_ncaaf_plog_player, idx_ncaaf_plog_season, idx_ncaaf_plog_team, ncaaf_player_game_log, public.player_recent_games_ncaaf(), public.player_season_stat_values_ncaaf(), public.player_window_totals_ncaaf(), v_player_season_totals_ncaaf

### Community 667 - "Scored pick outcomes lateral fix"
Cohesion: 0.36
Nodes (5): mv_scored_pick_outcomes_model_idx, mv_scored_pick_outcomes_pick_id_idx, public.v_model_full_outcome_record, public.v_public_track_record, public.v_public_track_record_daily

### Community 670 - "NBA models research record"
Cohesion: 0.08
Nodes (24): 1. Pre-registered bars (fixed 2026-10-15, before the first grid), 2. Data used (all in Supabase), 3. The market grid, 4.1 Game markets — closed for 2026-27, 4.2 First half / first quarter / team totals — closed for 2026-27, 4.3 Player props — one rule ships, 4.4 Player props — projection models (the NHL recipe), 4.5 The projection model on the worker's inputs only (+16 more)

### Community 672 - "NCAAF tables migration"
Cohesion: 0.39
Nodes (7): idx_ncaaf_glog_game, idx_ncaaf_glog_team, idx_ncaaf_team, idx_ncaaf_teams_conf, ncaaf_team_game_log, ncaaf_team_stats, ncaaf_teams

### Community 676 - "nfl/scripts/live_prop_job.sh"
Cohesion: 0.33
Nodes (5): LGB_NUM_THREADS, MKL_NUM_THREADS, OMP_NUM_THREADS, OPENBLAS_NUM_THREADS, live_prop_job.sh script

### Community 684 - "NFL player stats leaderboard"
Cohesion: 0.52
Nodes (6): idx_nfl_plog_player, idx_nfl_plog_season, nfl_player_game_log, public.player_recent_games_nfl(), public.player_window_totals_nfl(), v_player_season_totals_nfl

### Community 685 - ".claude/settings.json"
Cohesion: 0.40
Nodes (4): hooks, PreToolUse, SessionStart, $schema

### Community 686 - "NBA player game log RPCs"
Cohesion: 0.29
Nodes (7): idx_nba_plog_game, idx_nba_plog_player, nba_player_game_log, public.player_recent_games_nba(), public.player_season_stat_values_nba(), public.player_window_totals_nba(), v_player_season_totals_nba

### Community 687 - "scripts/refresh_pass.sh"
Cohesion: 0.53
Nodes (5): par(), par_wait(), refresh_pass.sh script, step(), STEP_TIMEOUT_S

### Community 703 - "Player news migration"
Cohesion: 0.60
Nodes (5): player_news_by_id, player_news_by_key, player_news_item_player, player_news_published, public.player_news

### Community 722 - "Kalshi game markets migration"
Cohesion: 0.70
Nodes (4): kalshi_game_markets_contract, kalshi_game_markets_date, kalshi_game_markets_event, public.kalshi_game_markets

### Community 726 - "Kalshi prop ladders migration"
Cohesion: 0.70
Nodes (4): kalshi_prop_ladders_prop, kalshi_prop_ladders_rung, kalshi_prop_ladders_snapshot, public.kalshi_prop_ladders

### Community 727 - "NCAAF QB game migration"
Cohesion: 0.70
Nodes (4): idx_ncaaf_qb_game, idx_ncaaf_qb_player, idx_ncaaf_qb_team, ncaaf_qb_game

### Community 729 - "Opening signals shadow track"
Cohesion: 0.70
Nodes (4): idx_opening_signals_date, idx_opening_signals_model, idx_opening_signals_settle, opening_signals

### Community 754 - "NFL live model tables"
Cohesion: 0.60
Nodes (4): live_game_states_ts_idx, live_odds_snapshots_game_ts_idx, public.live_game_states, public.live_odds_snapshots

### Community 759 - "API call log migration"
Cohesion: 0.83
Nodes (3): api_call_log, idx_api_call_api_ts, idx_api_call_ts

### Community 760 - "Model quality checks migration"
Cohesion: 0.83
Nodes (3): idx_model_quality_run_date, model_quality_checks_key, public.model_quality_checks

### Community 761 - "NCAAF plays migration"
Cohesion: 0.83
Nodes (3): ncaaf_plays_game, ncaaf_plays_season, public.ncaaf_plays

### Community 762 - "Parlay track record migration"
Cohesion: 0.83
Nodes (3): idx_parlay_track_date, idx_parlay_track_sport, public.parlay_track_record

### Community 763 - "Pipeline runs table"
Cohesion: 0.83
Nodes (3): idx_pipeline_runs_kind, idx_pipeline_runs_started, pipeline_runs

### Community 765 - "Push notifications migration"
Cohesion: 0.67
Nodes (3): device_push_tokens, idx_push_sent_kind, push_sent

### Community 766 - "Results snapshots migration"
Cohesion: 0.83
Nodes (3): public.results_snapshots, results_snapshots_date, results_snapshots_key

### Community 790 - "Mobile development dependencies"
Cohesion: 0.29
Nodes (7): devDependencies, @babel/core, babel-plugin-module-resolver, babel-preset-expo, tsx, @types/react, typescript

### Community 897 - "NBA play-by-play lineup docs"
Cohesion: 0.25
Nodes (7): Commands, How a stretch is built (each rule is pinned by a test that was watched to fail), NBA play-by-play and on-court lineup segments, Source, Tables (all worker-only, locked down where they are created), Things a reader should know, What was loaded, and the checks (re-measured 2026-10-17 on production, after the rebuild)

### Community 151 - "docs/rules_evidence.md"
Cohesion: 0.07
Nodes (13): 'Decisions needed from you' is second person, never first, A model in config.MODELS with no FEATURE_MAP entry kills scoring for every sport, Every front-end change is reviewed by the UX designer agent before its PR opens, Gate the number that gets bet (cal_error_actionable), A health check must not gate on the thing that breaks, The settled live-prop record is zero bets, The Odds API returns x-requests-remaining on every response, including 401, How the pick rule was found: the NCAAF live loop delete-and-replaced every 45s (+5 more)

### Community 183 - "Calibration and NFL opener-wind docs"
Cohesion: 0.10
Nodes (33): tracking.paper_tracker (_NFL_MODEL_MARKETS), scripts/nfl_rule_2026_track, tracking/opening_signals.capture_opening_signals, tracking.opening_report, tracking/opening_signals.settle_opening_signals, models/honest_ev.gate and honest_probability, tracking/system_health._report_model_calibration, MAX_FIRE_LEAD = 4 (+25 more)

### Community 192 - "NFL game lines model write-up"
Cohesion: 0.11
Nodes (19): DataRegistry: source catalog with priority levels, scripts/edge_hunt.py: moneyline calibration clean, ML-vs-spread gap dead, Forecast validation (2026-08-15): rule holds at 57.09% under real day-3 error, Game totals model (consumes spread output as competitiveness), IngestOrchestrator: per-source fetch with no silent fallbacks, Middling does not clear vig, Moneyline derived from spread via fitted sigmoid, Oracle ceiling: perfect closing-line knowledge (+11 more)

### Community 213 - "nfl/live_model/README.md"
Cohesion: 0.10
Nodes (18): backtest/calibrate.py (the two gates), backtest/calibrate_props.py projection prop gate, check_feed_assumptions: automatic first-payload feed check, backtest/flow_eval.py flow test with control, Gate 1: win probability Brier 0.1654 PASS vs 0.20, Gate 2: total quantile coverage 1.26pp PASS vs 2.0pp, backtest/harness.py kill_verdict, NFL live model (two-stage engine) (+10 more)

### Community 227 - "docs: followups + clv"
Cohesion: 0.08
Nodes (26): Pruner keeps the opener AND the close per (proposition, book), clv_method = standard_v2 (PEDIGREE_CLV_METHODS), clv_standard_v2_2026_10_14.sql bulk rewrite, Secondary — market edge vs Pinnacle's fair close (market_clv_*), Power de-vig (bisection, 80 steps, k in [0.05, 12]), Primary CLV — same-book raw price (clv_pct, clv_pp, clv_beat_close), Same line, and the close bound, Which price is the bet — _bet_price_and_book and clv_bet_book (+18 more)

### Community 246 - "docs: best_line + config_topology"
Cohesion: 0.10
Nodes (21): Book roles: fetched (LINE_SHOP_BOOKMAKERS) vs offered (BEST_LINE_BOOKMAKERS), DECIDE_ON_BEST_PRICE=0 restores DraftKings as the deciding price, Stage 2: decide, size and settle at the best price (picks.decision_*), _get_event_odds fetched DraftKings-only (MLB F5, UFC round totals), The live models join best-price deciding (2026-09-10), PREGAME_PRICE_MAX_AGE_MIN (180 min) on game-market reads, Scoring off another book's line (picks.line_book), BEST_LINE_EXCLUDE_BOOKMAKERS — unbettable books out of shopping (+13 more)

### Community 253 - "docs/history: learnings + build_state"
Cohesion: 0.09
Nodes (25): Data sources table (Odds API, SBR, MLB Stats API, Savant, Open-Meteo, NHL API, nba_api, ESPN, UFC CSV mirror, DataGolf), FanGraphs / pybaseball removed (IP-blocked); replaced by MLB Stats API + Savant, MLB_Basic.csv datawarehouse (2009-2025, 40,996 games; runline derived as -1.5), What's built (package tree) and what's not, AlphaPy rejected (deprecated, team-level only, defunct connectors), Team stats need at least 10 games before they stabilize, The go-live gate prevents going live on lucky backtests, Historical team-stat backfill uses {season}-01-01 as as_of_date (+17 more)

### Community 264 - "monitoring/static/dashboard.html"
Cohesion: 0.16
Nodes (26): Signalbase pipeline monitor dashboard page, dashboard.html ageNote(), dashboard.html callRow(), dashboard.html connect(), dashboard.html drawSeries(), dashboard.html drawTimeline(), dashboard.html flush(), dashboard.html ingestCalls() (+18 more)

### Community 276 - "NFL live prop lean notes"
Cohesion: 0.11
Nodes (13): The live prop market leans over like the pre-game one, Publish backstop refuses pass-attempt overs, Accrued carries from ESPN core leaders, rush_attempt_pace model: one offset on the book's number, Pace ratio, In-play rushing-attempt UNDER on pace ratio >= 1.25, NFL prop lines lean over, NFL edge search 2026-10-11 (+5 more)

### Community 292 - "docs/sports/nhl.md"
Cohesion: 0.12
Nodes (22): NHL models code-complete, not yet trained (2026-06-13 snapshot), docs/nhl_clv_ev_assessment.md: the current CLV/EV grade of every NHL model, Per-game logs from the NHL stats API (team, goalie, skater) via data/ingestors/nhl_game_logs.py, Starting-goalie confirm via ESPN core probableStartingGoalie; game-model veto on Out/Doubtful, docs/nhl_market_research.md: six defects and the honest walk-forward, data/nhl_asof.py: one function rates goalies and teams as-of, strictly before the date, nhl_over_under is live as a rule: Pinnacle de-vigged vs the bettable books in the same fetch, NHL pipeline steps (results before settle, odds, stats, totals card, scoring, settlement) (+14 more)

### Community 310 - "docs: mlb_market_handicap_features + mlb_game_market_gate"
Cohesion: 0.15
Nodes (20): Market-aware MLB model, trainable on three seasons, _get_dk_odds bounds on commence_time — the 'pre-game' line was a mid-game price, Activation as a new 2026-only model — superseded by SPARSE_OK, MARKET_MOVEMENT_FEATURES — nine columns in features/market_movement.py, sbr_consensus is one snapshot per game — 17 seasons carry no movement, models/game_market_gate.py — a decision-time overlay for MLB game models, GAME_MARKET_GATE_MODE=live by default, Live-artifact record of the four MLB game models (2026-09-15) (+12 more)

### Community 311 - "docs/sports/ncaaf.md"
Cohesion: 0.13
Nodes (19): Models registry (model id, sport, market, target), ncaaf_spread: cross-book opener rule, structurally dormant on this feed, New CFBD games are dated by Eastern kickoff; existing ids are not rewritten, Old ET/UTC twin rows stay; mirror_scores_to_alias_rows writes the final onto every alias, Issued forecasts for 2024-2025 (game_weather_issued) and the four-arm weather test, Kalshi NCAAF game markets recorded hourly (research only), The live models price FBS-vs-FBS only (shipped 2026-09-13), ncaaf_live_total: what has been tried (six attempts on the 2025 replay) (+11 more)

### Community 313 - "Cloud worker and local ops docs"
Cohesion: 0.09
Nodes (27): catch_up_daily_pipeline / tracking/daily_retry.py, test_every_model_artifact_on_disk_is_tracked_by_git, DISCORD_WEBHOOK_* variables, one channel per sport, Heartbeat watchdog -> DISCORD_WEBHOOK_OPS, LIVE_DAILY_CREDIT_CAP and RUN_LIVE_LOOP, In-play live loop under a */10 supervisor, Live monitor dashboard (monitoring/, MONITOR_TOKEN), NFL poll driver — hourly from T-10, every 10 min inside 3h (+19 more)

### Community 324 - "docs/discord.md"
Cohesion: 0.13
Nodes (17): Discord guarantees: never twice, only ledger what sent, never breaks the pipeline, recap covers a finished day, The producers in tracking/discord_notifier.py, notify_discord_void / push_sent kind discord_void, Live MLB is one model and the loop runs at 5s, Live picks go to their sport's live channel (_live_webhook_for_sport), post_missed_recap from 7am ET on every refresh pass, posted <time ET> = picks.created_at, publish_discord_signals worker job (+9 more)

### Community 325 - "docs/team_stats_leak.md"
Cohesion: 0.15
Nodes (20): mlb_f5_moneyline v4 retrained on the rebuilt tables (holdout 2026, AUC 0.5548), WNBA ESPN team ids resolve dynamically by full team name (expansion teams PDX, TOR, GSV), config.assert_retrain_allowed('MLB') and the TEAM_STATS_ASOF_REBUILD_COMPLETE marker, Eight features constant in every training season, The leaked seasons collapsed to the honest season's level, mlb_pitcher_stats table (season-final ERA on every start), mlb_team_stats table, Phase 2: data/pitcher_stats_rebuild.py (+12 more)

### Community 336 - "Live total and search protocol notes"
Cohesion: 0.10
Nodes (9): Live inning gate replay, mlb_live_total_runs (in-play total), Negative-binomial (NB1) tail, pregame_total_line feature (market anchor), Live tuning panel (Models view), ncaaf_live_total 2025 in-play backtest, ncaaf_live_win_prob 2025 in-play backtest, Halftime second-half lines, out of sample at real prices (+1 more)

### Community 337 - "docs/sports/nfl.md"
Cohesion: 0.17
Nodes (20): docs/nfl_edge_search.md: 14 ideas at zero credits; the in-play model retired, Possession bugs in the old core parser (situation.possession never sent; substring team-id match), DK line snapshots flushed into odds (zero extra credits) and pick-timing display, How the loop runs: ESPN core every 20 s, one DK call per due game, 1 credit, five-minute slots, nfl_live_leader_ml — in-play leader moneyline, live 2026-10-13, gate 0 of 50, Thirteen logistic regressions, one per exact lead 4..16 (nfl_live_leader_ml_wp.json), The population of record: 163 bets, +13.08u, +8.0% at lag 0, At the published stake (1u to win, risk capped 3u) the return is +5.0% (+12 more)

### Community 338 - "mobile: TESTFLIGHT + README"
Cohesion: 0.15
Nodes (18): mlb_total_public_fade: fade consensus OVER tickets >= 70, bet UNDER (paper, INSERT gated), BET signal thresholds and the action filter (per-model prob/edge tables), App Privacy: no data collected (bankroll is on-device AsyncStorage), App review notes: read-only, anon key is intended public read-only via RLS, Signalbase — the iOS app name and listing, App structure: lib, hooks, screens, components, Branch previews via eas update (GitHub Actions removed 2026-08-24), Supabase RLS: anon SELECT policies reused from the Lovable website (+10 more)

### Community 340 - "supabase/functions/README.md"
Cohesion: 0.19
Nodes (21): revenuecat-webhook Edge Function, Stripe rail (stripe-checkout / stripe-portal / stripe-webhook), dark, subscriptions table (keyed to auth.users, webhooks write), discord-link Edge Function (OAuth, guild join, role sync), _shared/discord.ts (bot API helpers), _shared/entitlement.ts (two-way rule, one place), discord-link Edge Function (verify_jwt true), linked_sportsbook_accounts table (RLS on, no anon policy) (+13 more)

### Community 356 - "NCAAF in-play model docs"
Cohesion: 0.14
Nodes (15): CFBD_MONTHLY_CALL_ALLOWANCE (Tier 4, 125k), Worker cannot reach site.api.espn.com (403); CFBD /scoreboard is the state source, ncaaf_live.gameday loop, Gate 1: win probability Brier 0.115 PASS vs 0.20, Gate 2: total shape 2.60pp FAIL vs 2.0pp, Market licenses from the calibration gates, LIVE_ODDS_MAX_AGE_SEC (180s) odds age bound, ncaaf_live_loop scheduler job (*/10 supervisor) (+7 more)

### Community 372 - "docs/sports/mlb.md"
Cohesion: 0.13
Nodes (14): Batter prop models (hits, TB Poisson; HR logistic retired), Bulk feature loading: ~6 hours -> ~3 seconds per model, CalError requires min_samples=20 per bin, F5 O/U and RL priced off the first bettable book (DK returns 0 rows), The F5 sweep does not produce a threshold: 0.74 fired zero bets, one positive cell in fifty, Market-relative game gate (models/game_market_gate.py): no-vig fair, PASS-when-steamed, The honest MLB numbers: ~0.55-0.56 AUC, not 0.60-0.64, Read this before any number: the 2026-09-03 leak repair (+6 more)

### Community 374 - "docs/thresholds.md"
Cohesion: 0.15
Nodes (14): Min-history gate: >= 3 prior UFC fights or the fight is skipped, Breakeven is the mean DK implied probability of the bets taken, not 52.4%, The forward check on fresh quotes: the 73.5% never existed, mlb_live_total_runs on the bought 2025 in-play history (260,190 credits), The live calibration map (Platt a=0.8578, b=-0.0787, promote_external), mlb_live_total_runs cut 0.70 -> 0.72 (superseded 2026-09-10), nfl_opener_spread cut: |dev| 1.0 -> 2.0, gate 0.52 -> 0.55, nfl_prop_market: two side floors, over 6pp / under 5pp (+6 more)

### Community 377 - "NFL game lines and wind totals docs"
Cohesion: 0.17
Nodes (18): Critical data defect: home/away sign flips in four books, Under rate falls ~0.41pp per day of forecast lead, data/odds_cache/ (~45,000 credits of snapshots), Open-Meteo (ERA5, issued forecasts, live forecasts) via data_ingest/weather.py, wind_speed_10m_previous_dayN is null before 2024-01-18, What does not work (backup QB, home dogs, cold unders, refs, rest, ...), scripts/replay_wind_card.py regression test, scripts/screen_books.py per-book integrity screen (+10 more)

### Community 390 - ".claude/rules: CLAUDE + config-topology"
Cohesion: 0.17
Nodes (4): DraftKings — primary sportsbook and feature reference, model_action_thresholds — the mirrored per-model cut, picks table — every publishing surface reads it, config-topology.md — path-scoped rule file

### Community 391 - ".github/workflows: CLAUDE + mobile-build"
Cohesion: 0.15
Nodes (11): Fetch brand assets workflow, Mobile TestFlight build workflow, Mobile OTA update (production) workflow, monitor probe workflow, Prune merged branches workflow, APScheduler drives scheduler.py, Latest TestFlight build tracking issue, Railway worker (scheduler.py) (+3 more)

### Community 395 - "docs/agents_contract.md"
Cohesion: 0.15
Nodes (13): catch_up_weekly_jobs on boot, Janitor retired 2026-09-03, ModelCalibration weekly re-measure, The pipeline watch's six rules, Sentinel (pipeline watch Routine, retired), Guardrails both agents share, UX Designer — the front-end review, Janitor (scheduled backlog runner, cannot land work) (+5 more)

### Community 407 - "docs/live_odds_freshness.md"
Cohesion: 0.16
Nodes (14): Basketball Daily Ingest stays on Matt's PC, DraftKings direct needs BOTH a browser fingerprint and a residential address, The feed has a ~45s floor and it cannot be bought past, The Odds API in-play feed is a ~45-67 s cache, Direct book feeds from both addresses (book_direct_probe.py), data/ingestors/dk_direct_feed.py (RUN_DK_DIRECT_FEED defaults 0), DK direct: fingerprint AND address are both necessary, config.live_slate_dates() — the midnight blind spot (+6 more)

### Community 420 - "mobile/docs/UX_REVIEW.md"
Cohesion: 0.16
Nodes (13): dashboard.html renderRoster(), A pick is a pick (re-priced line never replaces the locked one), Copy: formatAmerican/formatPct/formatCurrency, model ids never raw, Decided at the best bettable price; read via lib/decisionPrice.ts, frontend-ux-designer agent contract, Mobbin MCP connector (one route: Matt's claude.ai connector), Product rules: a violation is a Blocker, Reuse before invention (EmptyState, StatTile, SignalBadge, ...) (+5 more)

### Community 432 - "MLB model quality and totals notes"
Cohesion: 0.08
Nodes (21): MLB prop market-relative rule (not wired), Hybrid Pin-agreement filter on mlb_over_under bets, mlb_spread_market 1.8pp run-line rule, mlb_total_market paper totals logger, mlb_runline and mlb_over_under (paused), mlb_total_public_fade card (paper UNDER), Slate concentration guard (insert-time), F5 odds coverage (DK carries F5 ML only) (+13 more)

### Community 441 - "docs/sports: ufc + golf"
Cohesion: 0.17
Nodes (12): DataGolf Scratch Plus as the sole golf source (not The Odds API), Five golf models (outright, top10, top20, make_cut, matchup), One games row per tournament, per-player picks FK to it (the MLB-prop pattern), Golf settlement: ties settle at full price as a win (v1), WD-before-cut NO_ACTION, ufc_moneyline CalErr 5.99% above the 5% gate; a retrain will not move it, Primary UFC data path is the Greco1899 CSV mirror (ufcstats behind Cloudflare), UFC: moneyline, total_rounds, method_of_victory (3-class, prob-only), Fighter name matching via slugify_fighter and config.UFC_NAME_ALIASES (+4 more)

### Community 444 - "mobile/docs/BILLING.md"
Cohesion: 0.18
Nodes (10): BILLING_ENABLED kill switch, IAP entitlement flow (configure -> purchase -> webhook -> subscriptions), has_app_access() supersedes has_active_subscription(), isEntitled() checks status AND period end, PaywallScreen (localized prices, restore, redeem), RevenueCat SDK and entitlement 'signals', scripts/verify_billing.ts (83 assertions), has_app_access() server-side check (+2 more)

### Community 453 - ".claude/agents: frontend-ux-designer + CLAUDE"
Cohesion: 0.20
Nodes (8): ux_scan.mts — the deterministic front-end scan, frontend-ux-designer agent, Mobbin MCP connector — the only reference route, Signalbase — the iOS app in mobile/, /ux-review command, Matt — product area leader, /graphify trigger — use the installed graphify skill, CLAUDE.md — Betting Model Project Context

### Community 454 - ".claude/rules/picks-and-publishing.md"
Cohesion: 0.24
Nodes (4): The pytest non-integration subset, The lock flags: LOCK_GAME_PICKS_AT_FIRST_RUN, LOCK_PROP_PICKS_AT_FIRST_SIGNAL, LOCK_LIVE_PICKS_AT_FIRST_SIGNAL, tests/test_context_budget.py polices CLAUDE.md size, picks-and-publishing.md — path-scoped rule file

### Community 459 - "docs/signal_timing.md"
Cohesion: 0.18
Nodes (8): Does the daily pick lock cost us signals? (2026-08-23), MAX_EDGE_CAP blind spot: games with no row at all, A model re-run harness over stored snapshots (open item), Four NONE-row coverage traps, Prop NONE/AVOID rows are a survivor sample (poller clear), The pre-game line poller wipes a game's non-BET prop picks (known issue), The lock is signal-aware for NCAAF only (NONE rows refreshed, BETs lock at first cross), Signal-timing analysis — the pick lock (signal_timing.md)

### Community 461 - "mobile/docs/DISCORD_LINKING.md"
Cohesion: 0.23
Nodes (11): Migration add_discord_link_and_whop_memberships.sql, DISCORD_LINK_ENABLED flag, discord_links table, Connect Discord flow (start -> consent -> complete -> role sync), public.my_access() computes access on every read, useAccess access state hook, scripts/verify_discord_link.ts (44 assertions), whop_memberships table (+3 more)

### Community 479 - "docs/live_betting.md"
Cohesion: 0.18
Nodes (13): The live calibration map: 126 of 150, and it does not close, BookMoveClock — the book has moved past a cap while our state has not changed, LOCK_LIVE_PICKS_AT_FIRST_SIGNAL — the first live BET per lane is the bet of record, The live staleness guards (data/live_quote_guard.py), Live cutoffs are re-derived every pass (tracking/live_calibration.py), LIVE_MAX_BETS_PER_WEEK is advisory, not a runtime cap, config.LIVE_MODELS — a separate registry from MODELS, live_pick_features — one row per lane, the first one, under its own SAVEPOINT (+5 more)

### Community 492 - "NFL model bundle restore docs"
Cohesion: 0.16
Nodes (11): nfl/requirements.txt dependency set (pandas, numpy, pyarrow, requests, scipy, scikit-learn, lightgbm), Multi-layered leakage detection, The Odds API historical backfill (bet-time Tuesday 18:00 UTC; closing 10 min before kickoff clusters), The canonical write-up nfl_game_lines_model_system.md, data/credit_ledger.json spend/quota ledger, data/odds_cache/ keyed md5(date|regions|markets), data/raw/pbp_20XX.parquet not bundled; refetch from nflverse-data releases, data/processed/ (dev_long.parquet, book_screen.csv, feature matrix) (+3 more)

### Community 500 - "docs/sports/wnba.md"
Cohesion: 0.21
Nodes (13): Double-double is logistic, over-only, prob-only (COMPUTE_DD sentinel), NBA: 10 models live (moneyline + 9 props), O/U and spread blocked, NBA pipeline steps (odds, prop odds, stats local, scoring, settlement), stats.nba.com blocks datacenter IPs; team stats run on the local Task Scheduler job, WNBA results from the ESPN hidden API with core-API fallback, The wnba_over_under / wnba_spread sweep was leaked (latest snapshot had no pre-tipoff cutoff), WNBA models (moneyline + assists live; points/rebounds/threes/PRA/O/U/spread paused), WNBA pipeline responsibilities (odds, props, scoring, ESPN results, local game log and stats) (+5 more)

### Community 523 - "mobile/docs/AUTHENTICATION.md"
Cohesion: 0.24
Nodes (12): App Store guideline 4.8: Google on iOS requires Apple, AUTH_ENABLED kill switch, signalbase://auth-callback redirect URL, billingReady() requires AUTH_ENABLED, discordLinkReady() requires AUTH_ENABLED, RLS pre-flight: authenticated keeps full read access, SignInScreen (SignIn route), useAuth session store (+4 more)

### Community 528 - "Model state and volume assessments"
Cohesion: 0.15
Nodes (3): docs/followups.md, MLB pick volume efficiency assessment, Model state assessment, all 71 models (2026-09-03 snapshot)

### Community 545 - "NFL prop and college research notes"
Cohesion: 0.13
Nodes (11): scripts/ncaaf_search/, CollegeFootballData (CFBD) as primary source, ncaaf_spread / ncaaf_over_under / ncaaf_moneyline, DraftKings' alternate ladder over-prices every over, Market-anchored shape simulation, NCAA Football model build plan, NCAAF model search findings (2026-08-25), NFL stat-prop method search (2026-09-11) (+3 more)

### Community 558 - "docs/health_checks.md"
Cohesion: 0.24
Nodes (10): model_artifacts_load counts what it opened, model_artifacts table fallback restore, Three separate artifact questions, three separate failures, KNOWN_UNTRAINED — config models intentionally without artifacts, Pipeline-observability checks: refresh_pass_completion, refresh_pass_steps, signal_delivery, pick_label_integrity, pipeline_runs — the run ledger (tracking/run_ledger.py), Retrain Model workflow (retrain_model.yml), tracking/system_health.py — CRIT and WARN feed checks (Step 12) (+2 more)

### Community 560 - "docs/retrain_2026_plan.md"
Cohesion: 0.17
Nodes (13): scripts/paused_model_assessment, data.ingestors.baseball_savant_ingestor, models.trainer, #215 artifacts could not be deserialised, F5 O/U and F5 RL paused: leak-mismatched, synthetic-line trained, NCAAF in-play season replay: -3.4% and -13.1%, No model has a cut that clears on the deployed artifact, batter_sb: opp_team_sb_allowed feature (+5 more)

### Community 599 - "Live monitor and record view notes"
Cohesion: 0.18
Nodes (9): roi_collapse check, api_call_log table, Heartbeat watchdog, Live monitor dashboard (monitoring/), mv_scored_pick_outcomes (sweep matview), Official live date 2026-09-01, The request probe: one patch, not 75 call-site edits, Retool port of Models and Ops (+1 more)

### Community 603 - "docs/reviews/2026-09-07-nfl-props-deep-dive.md"
Cohesion: 0.33
Nodes (7): Twelve artifacts committed from a replica failed pickle.load unnoticed for two weeks, The eleven NFL projection prop models, unpaused on placeholder thresholds, nfl_prop_market: the de-vig rule (Pinnacle as truth, equal lines only), The scorer is pinned to today, the card looks ten days ahead, 112 bets on one Sunday from untuned models; 41-46% BET rates are placeholders, Eleven NFL distributional props paused 2026-09-14, NFL props deep dive — two lanes, one of them can't see the slate (2026-09-07)

### Community 627 - "docs/market_coverage.md"
Cohesion: 0.36
Nodes (7): ncaaf_prop_odds_ingestor and its probe, test_the_mlb_board_and_the_mlb_pull_are_one_set, MLB probe 2026-09-05 — served, unsupported and unpriced keys, NCAAF prune — FOOTBALL_MARKET_NOT_PRICED per league, scripts/probe_market_coverage.py — one market per call, writes nothing, Neither prop ingestor writes to api_call_log, Prop market coverage — what the feed actually serves

### Community 652 - "(root): pr-ci + requirements"
Cohesion: 0.33
Nodes (5): Mobile thresholds drift check (generate_mobile_thresholds --check), NFL preflight --ci, PR CI workflow — non-integration pytest subset, Render blueprint — betting-scheduler background worker, requirements.txt — >= pins for Python 3.14 wheels

### Community 66 - "docs/nfl_props_model.md"
Cohesion: 0.06
Nodes (43): scripts/nfl_prop_market_card, scripts/nfl_prop_replay, scripts/nfl_prop_ladder_grade, scripts/verify_kalshi, tackles_assists +21% is a measurement error (control), Traps specific to props, Anytime TD field de-vig: closed, betonlineag as a second sharp reference (OR, not AND) (+35 more)

### Community 688 - "NFL wind totals runbook and staking"
Cohesion: 0.36
Nodes (7): DOCUMENT STATUS block: superseded claims indexed, Under rate by forecast lead 1-7 (~0.41pp per day), Original staking: 25% Kelly capped at 3% (superseded), Kelly-proportional units with slate shading 1/sqrt(1+(k-1)rho), Stops: 2 units per bet, 3 units per slate, review at -15 units, Runbook: Wind Totals, scripts/stake_sizing.py: 1 unit = 1% of bankroll

### Community 698 - "Game model injury gate notes"
Cohesion: 0.40
Nodes (5): ESPN core probables for the NHL starting goalie, A NONE from this gate is not locked — the reprice path, The gate rule — refuse a game-model BET on a confirmed Out starter/star/goalie, Fires in scorer.score_game and _score_nhl_3way, after best-price requalify, before insert, Game-model starter / star / goalie gate

### Community 710 - "mobile/docs/BILLING.md"
Cohesion: 1.00
Nodes (4): useEntitlement() access gate (subscription OR Discord), useSubscription() subscription-only state, useEntitlement(), not useSubscription(), Access is one gate: useEntitlement(), never useSubscription().entitled

### Community 720 - "docs/testing.md"
Cohesion: 0.67
Nodes (3): PR CI runs a non-integration pytest subset, Pure function tests, in-memory SQLite via conftest, Test suite (testing.md)

### Community 81 - "docs: nhl_market_lab + nhl_clv_ev_assessment"
Cohesion: 0.08
Nodes (40): scripts/nhl_derivative_totals_backtest, data/ingestors/nhl_derivative_odds_history, models/nhl_props.py (Spec per market), DraftKings de-vigged price sits above realised over-rate, Anytime goalscorer: not a candidate once names corrected, nhl_moneyline and nhl_moneyline_regulation: no cut clears, Game models: lock later? Refuted, Name-key matching attached prices to both namesakes (+32 more)

### Community 856 - "App privacy policy"
Cohesion: 0.83
Nodes (4): On-device storage: bankroll and placed-bet flags in AsyncStorage, Claim: the app cannot write to the backend, Signalbase privacy policy: nothing personal collected, Signalbase Privacy Policy

## Ambiguous Edges - Review These
- `device_push_tokens table (anon INSERT/UPDATE, no SELECT)` → `Claim: the app cannot write to the backend`  [AMBIGUOUS]
  docs/privacy.html · relation: conceptually_related_to

## Knowledge Gaps
- **106 isolated node(s):** `RFC-4122`, `@babel/core`, `babel-plugin-module-resolver`, `babel-preset-expo`, `expo-asset` (+101 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 11084 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **205 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Table` connect `NBA public splits pipeline step` to `mobile/scripts/verify_contrast_tokens.ts`, `Latest line state trigger tests`?**
  _High betweenness centrality (0.235) - this node is a cross-community bridge._
- **What connects `RFC-4122`, `@babel/core`, `babel-plugin-module-resolver` to the rest of the system?**
  _106 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Injury report ingestion with WNBA fallback` be split into smaller, more focused modules?**
  _Cohesion score 0.06509803921568627 - nodes in this community are weakly interconnected._
- **Why does `over()` connect `mobile/scripts/verify_contrast_tokens.ts` to `App bankroll card`, `NBA public splits pipeline step`?**
  _High betweenness centrality (0.235) - this node is a cross-community bridge._
- **Should `Mobile stats board` be split into smaller, more focused modules?**
  _Cohesion score 0.012842687883767188 - nodes in this community are weakly interconnected._
- **Why does `inserted_minus_start_min()` connect `NBA public splits pipeline step` to `NBA public betting splits ingestor`, `NBA public betting splits ingestor tests`?**
  _High betweenness centrality (0.137) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `device_push_tokens table (anon INSERT/UPDATE, no SELECT)` and `Claim: the app cannot write to the backend`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._