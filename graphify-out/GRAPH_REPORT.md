# Graph Report - bm-nba-game  (2026-10-17)

## Corpus Check
- Large corpus: 1470 files · ~2,402,285 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 28277 nodes · 67043 edges · 926 communities (717 shown, 209 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 1717 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e7bd537d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ESPN injury ingestor
- Mobile stats board
- NFL prop data and player names
- Record correction posts to Discord
- ncaaf_live/tests/test_pregame_calibration.py
- nfl_live_leader/state.py
- Sports stats ingestors and database helpers
- tests/test_nfl_live_leader_gameday.py
- nfl_live_leader/gameday.py
- tests/test_calibration_promotion.py
- tests/test_score_off_any_book_line.py
- tests/test_recap_restatement.py
- Mobile pick filters and sorting
- tests/test_ncaaf_alias_scores.py
- tests/test_prop_alternate_lines.py
- tests/test_backtester.py
- NHL prop expected value lab
- nfl/live_model/feeds/odds_live.py
- NHL props nightly bet cap
- NBA prop market lab
- Discord pick notifier tests
- nfl/live_model/tests/test_backup_snaps.py
- mobile/scripts: verify_book_links + verify_betslip_combine
- NBA injury report ingest tests
- Mobile custom model builder filters
- mobile/scripts/verify_contrast_tokens.ts
- models/nhl_props.py
- Pick lock after settlement tests
- NBA prop projection and market card
- tests/test_mlb_game_market.py
- Discord daily results recap
- Threshold review report tests
- Idle read transaction tests
- tests/test_prop_box_scores.py
- NBA game model prop feature tests
- Best line and best-price decision tests
- tests/test_ddl_guard.py
- Deploy checks and worker job queue
- tests/test_nfl_opener.py
- NHL stats and goalie ingestors
- Discord pick posting and void notices
- NBA game model luck feature tests
- tests/test_publisher_lock.py
- tests/test_dk_direct_feed.py
- tests/test_credit_budget.py
- Mobile thresholds and daily results
- NHL market-anchored moneyline model
- NFL wind and opener publisher
- Settlement and self-heal tests
- NHL prop cards and blocked shots
- Scheduler stale weekly catch-up test
- tests/test_ungraded_model_performance.py
- Mobile pick detail load states
- mobile/scripts/verify_push.ts
- Prop price pregame cutoff tests
- Mobile markets and formatting
- Probability calibration and cut sweeps
- NFL prop odds loading tests
- tests/test_nhl_asof.py
- NFL prop features and walk-forward
- Market-relative prop model edges
- Script connections and health utilities
- data/ingestors/nfl_inplay_history.py
- Mobile bankroll card math
- Mobile in-app feedback flow
- NHL props per-game limit tests
- Core game scorer and config
- NCAAF in-play locked pick tests
- NBA prop projection card
- tests/test_db_reconnect.py
- tests/test_live_lock.py
- tests/test_refresh_retry.py
- NBA results and box score ingestor
- NBA results ingestor tests
- Mobile sportsbook betslip links
- tests/test_local_cache_is_additive.py
- tests/test_calibration_check_coverage.py
- tests/test_book_team_map.py
- tests/test_team_board_cache.py
- Discord signal notifier tests
- nfl/live_model/tests/test_rush_attempt_pace.py
- tests/test_nfl_poll_fast_silence.py
- NHL moneyline and market research scripts
- tests/test_weather_lookahead.py
- tests/test_nhl_asof.py
- tests/test_dk_freshness_parse.py
- NBA odds history gap filling tests
- models: slate_concentration + test_slate_concentration
- NBA game rule testing harness
- View migration lock handling tests
- NFL prop injury veto
- Fake database connection test doubles
- tests/test_ncaaf_search_features.py
- NCAAF walk-forward model search
- Mobile data queries and team detail
- Best line threshold sweep
- tests/test_nfl_scored_rows.py
- tests/test_cfbd_ingestor.py
- Parlay builder and bet slip
- NCAAF in-play history tests
- tests/test_prop_odds_utc_stamp.py
- Monitoring HTTP stream handler
- NCAAF game-day context tests
- tests/test_feature_artifact_agreement.py
- NBA injury report date scope tests
- CLV price-taken tests
- Mobile matchup, head-to-head and record verify
- tests/test_cloud_retrain_artifacts.py
- NHL totals card publishing
- NCAAF FBS registry tests
- tests/test_nfl_opener.py
- NBA injury report and schema guards
- tests/test_team_stats_asof_invariants.py
- Game feature engines and backtester
- Unit stake sizing and formatting
- tests/test_nfl_wind_publisher.py
- Odds, prop odds and NHL derivative odds ingestors
- NFL live prop model tests
- tests/test_health_reason_and_cadence.py
- tests/test_live_publish_parity.py
- tests/test_nfl_weather_supabase_readback.py
- Pitcher stats as-of invariant tests
- tests/test_walk_forward_eval.py
- NBA prop model core
- Live scorer score-change guard
- Pipeline log reason tests
- NHL props latest quote shopping
- NFL prop stats data ingestion
- NCAAF in-play score distribution pricing
- tests/test_nfl_scored_rows.py
- tests/test_system_health_checks.py
- Database cursor wrapper and replays
- NBA prop window scheduling tests
- tests/test_ncaaf_live_states.py
- nfl/live_model/feeds: test_feed_resilience + espn
- NFL opener card rows
- NFL pass attempt bias model
- Prop alternate line ladder
- NFL wind totals model
- tests/test_live_pick_features.py
- Pregame price age tests
- tests/test_prop_missing_features.py
- Push notification deep link routing
- MLB public fade top picks ranking
- NFL in-play prop settlement
- tests/test_player_news_ingestor.py
- NBA prop closing line tests
- NFL in-play decline recording tests
- Prop player name matching tests
- tests/test_run_ledger_orphans.py
- NBA lineup stints from play-by-play
- NFL DraftKings line snapshots
- NFL historical weather fetch script
- tests/test_heartbeat_disabled_jobs.py
- tests/test_repair_bogus_first_pitch_labels.py
- nfl/live_model/tests/test_executor.py
- tests/test_sbr_loader.py
- mobile/scripts/ux_scan.mts
- Shared database connection and settlement
- Price prefilter timeout rollback tests
- mobile/src/lib/otaUpdate.ts
- tests/test_live_quote_staleness.py
- NFL prop one side per line
- NHL goalie saves settlement tests
- UFC stats fighter resolution
- NBA prop stat settlement tests
- Weather lookahead window tests
- supabase/functions/_shared/discord.ts
- NFL prop market Kalshi bet finding
- tests/test_job_queue.py
- System health report checks
- tests/test_system_health_checks.py
- UFC event ingest tests
- tests/test_mlb_sbr_twin.py
- tests/test_ufc_phantom_filter.py
- tests/test_batter_prop_log_pin.py
- NFL CLV backtest and feature build
- tests/test_merge_mlb_twin_games.py
- tests/test_discord_channel_probe.py
- tests/test_nfl_prop_one_read_per_game.py
- Game outcome target tests
- NFL in-play pick builder tests
- Mobile billing paywall and purchases
- Multi-book odds reading tests
- scripts/nfl_edge_gameline_rules.py
- CLV off DraftKings line tests
- tests/test_model_game_savepoint.py
- tests/test_system_health_checks.py
- tests/test_calibration_watch.py
- tests/test_promote_external.py
- NFL in-play leader decision model
- tests/test_pipeline_report_rollback.py
- NBA results Postgres store
- Failure alerter fake-connection tests
- MLB prop pregame price cutoff tests
- Player news ingestor tests
- tests/test_sbr_loader.py
- Mobile app screens and theme
- NFL prop stat distribution tests
- tests/test_nhl_three_way_lookahead.py
- Prop odds next-day lookahead
- NFL live leader config tests
- tests/test_system_health_checks.py
- tests/test_score_when_lines_open.py
- NHL blocked shots settlement tests
- Monitoring server tests
- tests/test_best_line_live.py
- tests/test_sbr_loader.py
- MLB in-play game state alignment
- WNBA injury returnee feature tests
- tests/test_nfl_props.py
- NFL wind card book filter tests
- Prop no-bet rows survive tests
- Closing line value backfill job
- NHL opening night goalie tests
- tests/test_void_picks.py
- tests/test_sbr_loader.py
- Pipeline staleness watch tests
- scripts/mlb_bet_record_audit.py
- NCAAF in-play gameday loop
- NHL blocked shots card tests
- tests/test_scorer.py
- tests/test_system_health_checks.py
- tests/test_sbr_loader.py
- Odds API credit budget
- tests/test_daily_retry.py
- Feature engine injury adjustment
- NFL prop market card publisher
- Feature map tests
- NFL in-play pick writer commit order
- tests/test_live_book_move_guard.py
- tests/test_nfl_opener.py
- tests/test_nfl_props.py
- tests/test_weekly_catch_up.py
- tests/test_sbr_loader.py
- tests/test_umpire_ingestor.py
- tests: test_discord_notifier + test_discord_live_field
- Prop odds book update-time tests
- NFL pick monitor
- tests/test_nhl_props.py
- tests/test_live_pregame_total_line.py
- Shared scripts, probes and odds pulls
- Push notifier and publish key identity
- NFL pick monitor id matching
- Voided picks never rechosen tests
- Multi-book fallback response tests
- Stale quote price decision tests
- Player news feed ingest
- mobile/src/hooks: verify_tracked_performance + useStakeSettings
- supabase/functions/revenuecat-webhook/index.ts
- supabase/functions/whop-webhook/index.ts
- tests/test_model_quality.py
- tests/test_nfl_props.py
- Health check skip budget
- data/ingestors/live_game_state_poller.py
- tests/test_sbr_loader.py
- NHL as-of feature leak tests
- Football in-play game state
- Scorer injury flag building
- NFL forecast weather fetching
- NFL prop odds local cache
- Starter-out injury flag tests
- Prop alternate lines fetch tests
- NFL prop odds reader tests
- Mobile bankroll storage
- NBA injury report PDF parser
- tests/test_nfl_props.py
- tests/test_nhl_three_way_lookahead.py
- NFL live score distribution and calibration
- Signal publish-on-write tests
- NFL prop market grading
- tests/test_game_market_gate.py
- tests/test_system_health_checks.py
- Pregame price age board
- NHL blocked shots player identity tests
- Health pregame prices fake connection
- NBA second-model prop study
- tests/test_score_when_lines_open.py
- tests/test_score_when_lines_open.py
- tests/test_score_when_lines_open.py
- tests/test_system_health_checks.py
- First signal repair tests
- tests/test_pick_integrity.py
- NFL prop pull market list tests
- NFL games rows from player data
- tests/test_score_when_lines_open.py
- tests/test_record_one_pick_per_event.py
- Umpire feature drop declaration tests
- tests/test_weather_lookahead.py
- nfl/live_model/tests: test_props + props
- NHL returning starter name matching
- Prop no-bet rows kept to tipoff
- ncaaf_live/tests/test_serve.py
- tests/test_wnba_prop_market.py
- Paused bets bankroll exclusion tests
- tests/test_nfl_scored_rows.py
- NHL derivative totals model
- Mobile player log and matchup stats
- tests/test_nhl_props.py
- Discord publish sync and void notices
- NHL blocked shots prop settlement tests
- NFL prop kickoff time gate
- tests/test_recap_retries_a_skipped_day.py
- NBA odds archive rerun safety
- NFL odds event game matching
- Pregame line poller polling loop
- NCAAF game-day fetch cadence
- CFBD ingestor season failure tests
- NCAAF feature engine test database
- Odds pruning and sharp book retention
- NFL results ingestion
- NFL prop placebo baselines
- Stale pregame quote shopping test
- NFL in-play recorder fan-out
- NFL in-play pick writer locking
- NHL prop count distribution tests
- NBA prop market card tests
- Database schema statement splitter tests
- Pick integrity test shims
- SQLite connection shim for settlement
- Mobile bankroll unit settings
- Weekly catch-up job tests
- NFL prop no-vig price math
- Scorer feature value coercion tests
- NBA results ingest tests
- Prop push probability adjustment
- Model training and probability calibration
- tests/test_f5_any_book_line.py
- Batter prop shared log load test
- Opposing starter feature stubs
- NBA game residual distribution
- Player news fake database result
- NBA injury report fake cursor
- NFL evaluation rows carry the line
- tests/test_ncaaf_prop_odds.py
- MLB totals public fade tests
- NFL prop backtest verdicts
- tests/test_ncaaf_pbp_store.py
- tests/test_heartbeat_watchdog.py
- Game injury veto gate and tests
- Record correction post tests
- Pipeline run ledger and orphan cleanup
- NFL prop information and market tests
- NCAAF college data ingestor
- scripts/nfl_edge_live_rush_pace.py
- NBA prop projection tests
- NBA game market feature study
- tests/test_prop_calibrated_decision.py
- tests/test_mobile_line_movement.py
- tests/test_live_calibration.py
- Push deep link and mobile player detail tests
- NBA lineup stint derivation tests
- tests/test_ncaaf_live_notify.py
- Pregame best game price lookup
- monitoring/store.py
- tests/test_settled_record_is_immutable.py
- features/golf_feature_engine.py
- ncaaf_live/tests/test_states.py
- tests/test_bovada_feed.py
- tests/test_market_movement.py
- NCAAF cross-book opener artifact tests
- tests/test_paused_keeps_real_verdict.py
- NFL in-play edge season backtests
- tests/test_health_pregame_prices_current.py
- NBA game line move study
- scripts/nfl_edge_extreme_props.py
- scripts/nfl_edge_settlement.py
- X publisher
- tests/test_agents_contract.py
- Historical odds backfill tests
- Position vs opponent tests
- WNBA results ingestor parsers
- Daily pipeline runner and push notifier
- NFL in-play flow validation
- NBA box score enrichment
- Prop box score backfill
- scripts/nfl_preflight.py
- Push receipt ticket handling tests
- NCAAF board visibility tests
- NFL stake sizing and EV engine
- nfl/live_model/tests/test_flow.py
- tests/test_decide_on_calibrated.py
- NBA prop projection lab
- NFL edge versus luck gap study
- tests/test_nfl_rule_2026_track.py
- tests/test_model_artifacts_load.py
- scripts/game_line_market_sweep.py
- Push notification deep link tests
- tests/test_pass_instrumentation.py
- tests/test_db_adapt_sql.py
- NHL totals market model
- tests/test_first_signal_repair.py
- tests/test_mobile_contrast_tokens.py
- NBA second game line move tests
- tests/test_live_inning_gate_replay.py
- NBA play-by-play game matching tests
- NFL halftime and prop wind edge studies
- Free pick cheaper book tests
- Closing line value math
- tests/test_nfl_live_leader_state.py
- tests/test_ncaaf_qb_ingestor.py
- NHL derivative totals card
- NBA derivative market lab
- NBA prop model verification script
- Mobile pick category tests
- NCAAF feature engine tests
- MLB first pitch time trust
- tests/test_ncaaf_game_identity.py
- NBA second game market tests
- data/ingestors/ncaaf_inplay_history.py
- MLB and WNBA stats ingestors and pitcher rebuild
- data/ingestors/nhl_boxscore.py
- scripts/mlb_total_public_fade_topk.py
- NFL wind cards and kickoff weather
- NFL teaser leg study
- tests/test_live_game_features.py
- tests/test_ncaaf_totals_regression.py
- UFC feature engine and tests
- Mobile verify scripts run from pytest
- NCAAF in-play history backtest
- tests/test_ncaaf_qb_features.py
- Line CLV sign and orientation tests
- tests/test_mobile_team_detail.py
- NBA game harness tests
- NBA ESPN box score parsing
- NCAAF play-by-play state builder
- Health skip budget tests
- Kalshi ladder recorder tests
- Calibration check and stake tests
- tests/test_ncaaf_player_stats_ingestor.py
- NBA second game model verdict
- Market coverage probe tests
- scripts/nfl_edge_kalshi.py
- scripts/nfl_live_prop_feasibility.py
- tests/test_context_budget.py
- tests/test_player_h2h_stat_values_migration.py
- tests/test_retired_models.py
- NBA schedule features
- Pregame line poller change tests
- Latest line state and Citadel migration cluster tests
- tests/test_live_record_start_views.py
- tests/test_model_quality.py
- tests/test_api_call_rollup.py
- NFL weather edge study
- nfl/models/opener_spread.py
- NHL prop backtest namesake handling
- tests/test_live_slate_midnight.py
- tests/test_nfl_wind_fire_window.py
- College football data parsers
- tests/test_public_betting_ingestor.py
- tests/test_service_role_split.py
- tests/test_http_timeout_floor.py
- Line churn measurement and verdict
- scripts/nfl_edge_cache.py
- Paused model assessment tests
- NHL prop odds alternate line tests
- NFL in-play pick writer
- Injury fetch speed and cache tests
- Published record and stake tests
- tests/test_cfbd_ingestor.py
- tests/test_config.py
- Kalshi game market recorder
- Database URL doctor tests
- tests/test_mlb_pbp_ingestor.py
- UFC fighter name resolution
- UFC fight history loader
- tests/test_team_stats_asof_invariants.py
- MLB run line retrain and sweep job
- Refresh pass step ordering tests
- CFBD verification script
- NBA historical odds archive parser
- Sharp book odds retention in pruning
- UFC event stats ingestor
- Mobile tracked performance checks
- tests/test_mobile_threshold_parity.py
- NFL live prop assessment script
- tests/test_nhl_derivative_odds_job.py
- tests/test_track_record_views.py
- tests/test_weekly_catch_up.py
- tests/test_live_game_state_poller.py
- NCAAF live ESPN feed parser
- Fast live odds path tests
- CLV card price taken tests
- NFL live leader model tests
- NFL wind edge studies
- Mobile paused catalog tests
- NFL live prop rule studies
- tests/test_mobile_player_stat_groups.py
- Mobile sport filter tests
- tests/test_promote_calibration_job.py
- tests/test_cfbd_snapshot_leakage.py
- Intraday data freshness tests
- tests/test_nfl_prop_thresholds.py
- tests/test_nhl_research_job.py
- tests/test_settlement_timing.py
- Model quality and CLV checks
- NFL injury ingest from ESPN tests
- DataGolf ingestor and NHL SBR archive
- Paused and no-signal pick rows
- NFL odds cache import to Supabase
- tests/test_health_check_observe.py
- NCAAF school name slugs
- Health check deliverability tests
- tests/test_pick_lock_is_on_picks.py
- NCAAF opener rule scoring tests
- NFL prop lead ceiling capture fixture
- tests/test_team_stats_asof_invariants.py
- scripts: build_nfl_live_leader_artifact + model
- NCAAF outcome edge scan
- tests/test_opp_starter_features.py
- supabase/functions/discord-link/index.ts
- tests/test_nfl_prop_clv.py
- tests/test_prune_keeps_the_close.py
- tests/test_scoring_methods.py
- MLB prop market sweep research
- Live monitor dashboard cache and docs
- Worker job queue runner
- Results recap backfill to X
- Anonymous read access audit
- NCAAF totals weather and margin evaluation
- NCAAF game day polling cadence tests
- nfl/scripts/backtest_opener.py
- MLB retrain freeze tests
- tests/test_latest_odds_views.py
- NBA schedule ingestor and tests
- tests/test_nfl_prop_settle_name_fallback.py
- NFL recap waits for box scores tests
- tests/test_transaction_pooler.py
- NBA historical odds archive parsing
- Team stats as-of invariant tests
- NBA injury report slot dates
- Mobile bankroll settings card
- supabase/functions/sharpsports/index.ts
- NCAAF in-play underdog correction fit
- WNBA prop market card
- NFL model imports under scheduler
- Watchdogs and calibration monitors
- tests/test_worker_deps.py
- Minimum odds price floor tests
- scheduler.py
- NFL stale card file tests
- NCAAF steam lag study
- Published record reconciliation tests
- tests/test_mobile_stat_labels_match_the_server.py
- tests/test_ncaaf_fcs_visitor_names_migration.py
- tests/test_nfl_prop_unstarted_clear.py
- NBA game lab and NFL edge hunts
- NFL live moneyline and total pricing tests
- Trainer no-register tests
- tests/test_savant_freshness.py
- tests/test_scorer_nfl_prop_like_escape.py
- App read access lockdown
- Source code static guard tests
- Odds pruning keeps openers tests
- Slate concentration and fade risk checks
- Kalshi prop market ingest
- tests/test_clear_unauthorized_auto_pauses_migration.py
- Declared worker job validation tests
- tests/test_ncaaf_se_louisiana_alias_migration.py
- tests/test_overnight_polling.py
- tests/test_revoke_remaining_grants.py
- tests/test_live_slate_midnight.py
- tests/test_nhl_stats_ingestor.py
- NCAAF situational spot search
- NCAAF starting quarterback absence study
- tests/test_claude_rules_split.py
- tests/test_db_setup.py
- tests/test_dedupe_opening_signals.py
- NCAAF totals lead timing study
- tests/test_every_named_book_is_fetched.py
- tests/test_pbp_backfill_resilience.py
- MLB backfill retry tests
- NFL prop universe model rate summary
- Mobile bankroll copy and behaviour tests
- Anonymous read grants application
- tests/test_game_log_backfill_skip.py
- NCAAF line move spots
- NBA luck study and feature frames
- tests/test_prompt_reads_thresholds.py
- tests/test_system_health_meta_steps.py
- NBA period scores ingestor and tests
- scripts/render_brand_icons.py
- NHL blocked shots backtest
- Dashboard rule model tests
- supabase/functions/stripe-webhook/index.ts
- tests/test_drop_voided_nfl_wind_opening_signals_migration.py
- tests/test_mobile_neutral_signal_label.py
- NFL wind stake sizing tests
- tests/test_scorer_commits_per_game.py
- NCAAF in-play underdog calibration tables
- NCAAF structure scan
- tests/test_live_game_state_poller.py
- NFL prop pulled quote filtering
- tests: test_wnba_availability + wnba_availability
- NCAAF venue feature tests
- NFL prop scorer kickoff ceiling tests
- supabase/functions/sharpsports-webhook: index + index
- Live monitor web server
- supabase/functions/stripe-checkout/index.ts
- tests/test_book_list_budget.py
- NFL prop over-lean study
- NBA game market lab
- Anonymous access revoke migration tests
- SBR historical odds loader
- NBA injury report player matching
- Worker-only table security guard tests
- mobile/scripts/verify_a11y.ts
- One pick per event record counting
- tests/test_demote_ncaaf_over_under_platt.py
- tests/test_discord_post_one_pick_migration.py
- tests/test_game_scorer_spares_nfl_props.py
- In-play count model column guard
- NFL in-play model backtest states
- tests/test_mobile_ota_self_update.py
- Registered models not firing
- MLB totals public fade model
- tests/test_team_board_commence_bound.py
- NFL prop book sweep
- UFC stats page parsers
- Weather effect on game totals
- NFL Kalshi price history fetch
- NFL prop lean concentration study
- Pipeline watch post ledger
- NBA play-by-play roster and alias repair
- Game day loop early exit
- Live feed vendor probe
- Scorer keeps off-DraftKings priced bets tests
- NCAAF quarterback ablation study
- Drop voided NFL prop signals tests
- NCAAF cross-book opener guards
- Pipeline watch run findings
- UFC fighter page parser
- Market handicap features
- tests/test_team_stats_asof_invariants.py
- MLB over/under retrain sweep tests
- tests/test_team_stats_asof_invariants.py
- tests/test_team_stats_asof_invariants.py
- tests/test_weekly_catch_up.py
- Mobile stats filter checks
- NHL goalie line helpers
- Team stats rebuild and verify
- NFL opener cut sweep
- tests/test_live_orchestrator.py
- Live money no record-only tests
- Cross-book opener timestamp skew guard
- NFL weather forecast persistence
- tests/test_team_stats_asof_invariants.py
- Health pass SQLite test database
- NCAAF consensus gate study
- Mobile accessibility verify script
- Market handicap feature tests
- mobile/scripts/verify_a11y.ts
- mobile/scripts/verify_a11y.ts
- Eastern time game date rules
- Game-line market sweep job
- NBA injury report name and team parsing
- Prop CLV and SQL escaping tests
- mobile/scripts/verify_a11y.ts
- NCAAF margin cover evaluation
- Team stats verify alias test
- NFL prop week one candidate pool
- Global EV floor tests
- Mobile error state tests
- Restated pick keeps better price
- NCAAF CFBD line bookmaker label
- MLB public split pre-start filter
- NCAAF feature assembly
- scripts/nfl_edge_preregistered_2026.py
- NFL prop publish skip checks
- Live orchestrator floor pass tests
- NCAAF play-by-play value range scan
- NCAAF in-play odds outage handling
- tests: test_player_positions + player_positions_ingestor
- NCAAF play by play state store
- NFL in-play pick writer price ceiling
- NFL 2024 in-play edge replication
- Anonymous grants apply plan
- App RPC anonymous access guard
- NFL prop ladder calibration
- Pregame prices freshness health check
- Anonymous access table lockdown
- Live pick expected value per unit
- mobile/scripts/verify_a11y.ts
- Discord notifier units convention
- Insert column alignment checks
- Model ROI collapse detection
- NFL in-play pick date and announce tests
- NFL tackles total target tests
- Pipeline watch credit burn checks
- NFL in-play pick publish refusal
- Model bet volume spike check
- NFL in-play multi player bets
- Worker service role job filtering
- Pipeline watch missing webhook alert
- MLB prop board market coverage test
- Pipeline pass watch findings
- NBA archive moneyline timing checks
- NBA game clock parsing
- NBA prop model lab
- First signal repair comparison
- NCAAF live notify connection close test
- Game day college data call budget
- Calibration freshness probe test
- NFL prop market census request
- Pipeline watch ledger failure test
- Game day unknown kickoff handling
- NCAAF gameday odds cadence test
- NCAAF kickoff time zone handling
- Pending opposing starter features guard
- Home run starter features test
- NBA play-by-play ingestor
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
- Disk IO indexes migration
- Live game state tables
- NHL moneyline rebuild write-up
- NCAAF player stats leaderboard
- Scored pick outcomes lateral fix
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
- Mobile build dev dependencies
- Game weather issued migration
- Odds API quota migration
- Parlay correlations migration
- Pick placement checks migration
- docs: nhl_market_lab + nhl_clv_ev_assessment
- NBA play-by-play lineup docs
- docs/rules_evidence.md
- docs: probability_calibration + nfl_rule_2026_track
- NFL game lines model write-up
- Model quality and MLB docs
- nfl/live_model/README.md
- docs: followups + clv
- docs: best_line + config_topology
- docs/history: learnings + build_state
- monitoring/static/dashboard.html
- docs/sports/nhl.md
- docs: mlb_market_handicap_features + mlb_game_market_gate
- docs/sports/ncaaf.md
- Cloud worker and local ops docs
- docs/discord.md
- docs/team_stats_leak.md
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
- NFL in-play edge search findings
- mobile/docs/UX_REVIEW.md
- Odds sources and prediction markets research
- docs/sports: ufc + golf
- mobile/docs/BILLING.md
- .claude/agents: frontend-ux-designer + CLAUDE
- .claude/rules/picks-and-publishing.md
- .claude/rules/model-updates.md
- docs/signal_timing.md
- mobile/docs/DISCORD_LINKING.md
- Probability calibration and EV floor docs
- docs/live_betting.md
- NFL model bundle restore docs
- docs/sports/wnba.md
- mobile/docs/AUTHENTICATION.md
- NFL prop market and edge research docs
- Monitoring and model state docs
- .claude/rules/frontend.md
- docs/health_checks.md
- docs/retrain_2026_plan.md
- docs/reviews/2026-09-07-nfl-props-deep-dive.md
- NCAAF search findings and plans
- docs/market_coverage.md
- (root): pr-ci + requirements
- docs/nfl_props_model.md
- Push notifications and privacy docs
- docs/game_injury_gate.md
- NFL wind totals runbook and staking
- mobile/docs/BILLING.md
- docs/testing.md
- CLAUDE.md
- NFL opener sharp-vs-soft findings

## God Nodes (most connected - your core abstractions)
1. `get_connection()` - 594 edges
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
- `Things a reader should know` --references--> `shot_value()`  [INFERRED]
  docs/nba_pbp_stints.md → data/ingestors/nba_stints.py
- `4.3 Player props — one rule ships` --references--> `run_nba_prop_window()`  [INFERRED]
  docs/nba_models_2026.md → scheduler.py
- `2. Data used (all in Supabase)` --references--> `odds()`  [INFERRED]
  docs/nba_models_2026.md → tests/test_latest_line_state.py
- `3. The market grid` --references--> `odds()`  [INFERRED]
  docs/nba_models_2026.md → tests/test_latest_line_state.py
- `Gate 1: win probability Brier 0.115 PASS vs 0.20` --semantically_similar_to--> `Gate 1: win probability Brier 0.1654 PASS vs 0.20`  [INFERRED] [semantically similar]
  ncaaf_live/README.md → nfl/live_model/README.md

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

## Communities (926 total, 209 thin omitted)

### Community 0 - "ESPN injury ingestor"
Cohesion: 0.07
Nodes (19): TestCoreTeamsFallback, _compute_return_ramp(), _espn_team_ids(), fetch_espn_injuries(), _fetch_espn_team_injuries(), fetch_mlb_transactions(), _fetch_nba_espn_team_ids(), fetch_return_ramp_players() (+11 more)

### Community 1 - "Mobile stats board"
Cohesion: 0.01
Nodes (315): P, TouchSet, Sport, errorKind, gameStatus, RulerHold, RulerScale, StatDef (+307 more)

### Community 10 - "NFL prop data and player names"
Cohesion: 0.02
Nodes (98): TestLocalCacheGuards, event_code(), event_date(), kalshi_school(), _num(), probe(), record_game_markets(), resolve_events() (+90 more)

### Community 104 - "Record correction posts to Discord"
Cohesion: 0.07
Nodes (25): LedgerUnread, Conn, delete_custom_record_post(), _jump(), _place(), _publish(), publish_full_record(), publish_full_record_standard() (+17 more)

### Community 108 - "ncaaf_live/tests/test_pregame_calibration.py"
Cohesion: 0.04
Nodes (30): LiveEngine, american_to_prob(), devig_power(), correct_for_pregame(), expected_value(), _is_paused(), _load_pregame_calibration(), pregame_dog_points() (+22 more)

### Community 109 - "nfl_live_leader/state.py"
Cohesion: 0.12
Nodes (18): CoreClient, EventMeta, _abbr(), game_seconds(), https(), _int(), is_admin_play(), is_conversion_play() (+10 more)

### Community 11 - "Sports stats ingestors and database helpers"
Cohesion: 0.01
Nodes (169): ViewMigrationResult, TestTheStoreReadsTheStartTime, live_slate_dates(), _connect(), connection_lost(), _go(), _open(), rollback_savepoint() (+161 more)

### Community 113 - "tests/test_nfl_live_leader_gameday.py"
Cohesion: 0.05
Nodes (33): FakeClient, FakeClock, FakeConn, FakeFeed, _Rows, art(), live_state(), quote_payload() (+25 more)

### Community 114 - "nfl_live_leader/gameday.py"
Cohesion: 0.04
Nodes (36): ScoreClock, _Unset, Cadence, GameContext, LiveOddsFeed, Quote, LiveState, release_read() (+28 more)

### Community 115 - "tests/test_calibration_promotion.py"
Cohesion: 0.05
Nodes (29): FakeConn, _SchemaRecordingConn, eligibility_clause(), maps_materially_differ(), promote(), _payload(), _row(), test_a_broken_table_is_identity_maps_not_an_exception() (+21 more)

### Community 116 - "tests/test_score_off_any_book_line.py"
Cohesion: 0.08
Nodes (33): _FakeConn, _fallback_line_quote(), _cut(), _on(), _pick(), _row(), _sql_const(), _src() (+25 more)

### Community 118 - "tests/test_recap_restatement.py"
Cohesion: 0.07
Nodes (18): _Conn, test_a_restated_recap_is_labelled_and_says_why(), test_the_record_restatement_and_the_slate_restatement_are_separate(), _resp(), test_a_404_is_an_answer_not_a_retry(), test_a_persistent_403_still_raises_after_the_last_attempt(), test_a_recap_whose_count_merely_drifted_is_not_due(), test_a_recap_with_a_late_settlement_is_due() (+10 more)

### Community 12 - "Mobile pick filters and sorting"
Cohesion: 0.01
Nodes (215): P, ActivePill, Props, Props, Props, reachFrame, DateOption, DayRow (+207 more)

### Community 120 - "tests/test_ncaaf_alias_scores.py"
Cohesion: 0.08
Nodes (32): _FakeConn, _FakeCursor, alias_score_updates(), _date_or_none(), mirror_scores_to_alias_rows(), mirror_stored_finals(), _cfbd(), _row() (+24 more)

### Community 121 - "tests/test_prop_alternate_lines.py"
Cohesion: 0.09
Nodes (20): _Conn, _market_chunks(), alt_markets_due(), _ou(), _parse(), test_a_failed_check_does_not_spend(), test_a_player_the_book_lists_at_1_5_keeps_the_0_5_alternate(), test_a_sport_with_no_alternates_never_asks() (+12 more)

### Community 123 - "tests/test_backtester.py"
Cohesion: 0.07
Nodes (9): TestCalibrationError, TestComputeBacktestSummary, TestEvaluateResult, TestGoLiveGateConstants, TestIterSides, _calibration_error(), compute_backtest_summary(), _evaluate_result() (+1 more)

### Community 124 - "NHL prop expected value lab"
Cohesion: 0.06
Nodes (19): TestRegimeOrder, books(), sides(), best_per_player(), blocked_sides(), engine_sides(), history(), pool() (+11 more)

### Community 125 - "nfl/live_model/feeds/odds_live.py"
Cohesion: 0.09
Nodes (15): CreditBudgetExceeded, CreditMeter, LiveOddsClient, Quote, best_price(), parse_events(), _parse_ts(), _side_of() (+7 more)

### Community 129 - "NBA prop market lab"
Cohesion: 0.09
Nodes (44): NBTable, add_units(), assemble(), best_per_key(), boot_ci(), build_quotes(), candidates_from(), choose_floor() (+36 more)

### Community 13 - "Discord pick notifier tests"
Cohesion: 0.02
Nodes (90): _Resp, _cand(), _et_now_iso(), _live_row(), _live_setup(), _no_prod_threshold_sync(), _restate_env(), _restate_signals() (+82 more)

### Community 131 - "nfl/live_model/tests/test_backup_snaps.py"
Cohesion: 0.08
Nodes (27): _FakeConn, _FakeCur, back_up(), digest(), _flush(), iter_files(), main(), _mb() (+19 more)

### Community 135 - "mobile/scripts: verify_book_links + verify_betslip_combine"
Cohesion: 0.06
Nodes (37): betslipCombineKind, combineBetMgm(), combineBetslipLinks(), combineCaesars(), combineDraftKings(), combineEspnBet(), combineFanDuel(), fanDuelPairs() (+29 more)

### Community 137 - "NBA injury report ingest tests"
Cohesion: 0.12
Nodes (12): _Conn, _PdfFetcher, _content_of_fixture(), test_a_changed_report_stores_its_rows(), __init__(), test_a_garbled_report_writes_its_ledger_row_and_no_rows(), test_a_repeat_of_a_repeat_points_at_the_report_that_holds_the_rows(), test_a_report_identical_to_its_predecessor_stores_no_rows_and_points_at_it() (+4 more)

### Community 14 - "Mobile custom model builder filters"
Cohesion: 0.03
Nodes (134): Props, Props, BacktestPickRow, ChipGroup, ChipKey, FilterablePick, BetTypeChoice, BetTypeOption (+126 more)

### Community 140 - "mobile/scripts/verify_contrast_tokens.ts"
Cohesion: 0.05
Nodes (40): Pair, code(), lum(), noGreen(), over(), ratio(), read(), readUtf8() (+32 more)

### Community 141 - "models/nhl_props.py"
Cohesion: 0.09
Nodes (27): Spec, _attach_teams(), build_frame(), build_goalie_frame(), build_skater_frame(), _ew(), excess_variance(), expected_value() (+19 more)

### Community 143 - "Pick lock after settlement tests"
Cohesion: 0.09
Nodes (21): _SqliteShim, _game(), _pick(), _survivors(), test_a_bet_is_never_dropped_for_an_earlier_no_signal(), test_a_dead_zone_prop_row_locks_too(), test_a_final_game_is_not_a_scoring_target(), test_a_game_with_no_score_is_still_scoreable() (+13 more)

### Community 145 - "NBA prop projection and market card"
Cohesion: 0.06
Nodes (36): Roster, ProjectionBet, coherent(), fair_under(), fetch_times(), find_bets(), in_window(), load_quotes() (+28 more)

### Community 146 - "tests/test_mlb_game_market.py"
Cohesion: 0.08
Nodes (25): GameMarketBet, _SlateConn, find_spread_bets(), find_total_bets(), _is_runline(), pick_rows(), test_mlb_market_cards_drop_a_bet_under_the_floor(), _game_rows() (+17 more)

### Community 149 - "Discord daily results recap"
Cohesion: 0.04
Nodes (34): _Conn, _recap_row(), test_a_day_with_no_in_play_picks_says_nothing_about_it(), test_a_loss_costs_the_full_stake_and_a_push_costs_nothing(), test_a_pick_with_no_price_stays_in_the_units_at_bare_conviction(), test_a_restate_with_nothing_settled_late_is_a_no_op(), test_a_six_column_row_still_tallies(), test_a_snapshot_with_no_clv_stores_null_not_zero() (+26 more)

### Community 150 - "Threshold review report tests"
Cohesion: 0.04
Nodes (36): _Conn, _DdlConn, _DdlRes, _quiet(), rule_only(), _slate(), test_a_failed_lock_down_does_not_lose_the_table(), test_a_losing_model_with_enough_bets_is_flagged() (+28 more)

### Community 152 - "Idle read transaction tests"
Cohesion: 0.08
Nodes (14): _Rec, _flat(), test_a_lock_timeout_fails_that_file_and_the_next_still_runs(), test_a_locked_bet_releases_the_lock_check(), test_a_quiet_tick_rolls_the_read_back(), test_a_tick_that_writes_does_not_roll_the_insert_back(), test_an_unresolved_game_releases_the_context_read(), test_is_locked_releases_the_read() (+6 more)

### Community 155 - "tests/test_prop_box_scores.py"
Cohesion: 0.09
Nodes (18): GradeConn, ScriptConn, ensure_prop_box_scores(), missing_prop_games(), _pick(), test_a_logged_game_is_not_fetched_and_a_goalie_gap_is(), test_a_non_timeout_prop_error_rolls_back_and_raises(), test_a_probe_error_that_is_not_a_timeout_raises_after_rollback() (+10 more)

### Community 156 - "NBA game model prop feature tests"
Cohesion: 0.06
Nodes (40): _Stop, _box(), _g(), _games(), _inj(), _model(), _props(), _run() (+32 more)

### Community 158 - "Best line and best-price decision tests"
Cohesion: 0.05
Nodes (33): FakeConn, TwoOrientationConn, _best_game_price(), _best_of(), _best_prop_price(), _same_line(), _source(), test_a_better_price_at_a_different_total_is_not_the_same_bet() (+25 more)

### Community 162 - "tests/test_ddl_guard.py"
Cohesion: 0.06
Nodes (20): GuardConn, _ddl(), _dk_direct_feed(), _is_guarded(), _job_queue(), _modules_with_write_time_ddl(), _monitoring(), _probability_calibration() (+12 more)

### Community 163 - "Deploy checks and worker job queue"
Cohesion: 0.07
Nodes (16): _Conn, test_a_declared_job_carries_its_run_after(), test_a_failing_check_raises_so_the_queue_announces_it(), test_a_job_can_only_name_a_registered_check(), test_enqueue_rejects_a_naive_run_after(), test_enqueue_stores_run_after(), test_every_check_is_read_only(), test_the_claim_waits_for_run_after() (+8 more)

### Community 164 - "tests/test_nfl_opener.py"
Cohesion: 0.09
Nodes (10): TestFireWindow, TestFreshNumberLabel, TestHeldMinutes, TestModelCardSplit, _giants_board(), _giants_prior_at_2129(), _giants_sched(), _obs() (+2 more)

### Community 165 - "NHL stats and goalie ingestors"
Cohesion: 0.03
Nodes (48): TestLogRowBuilders, TestNoHollowTeamRowBeforeTheFirstGame, TestThreeWayMarketKey, _default_fetch(), fetch_espn_nhl_probables(), _https(), parse_probable(), _team_abbrev() (+40 more)

### Community 17 - "Discord pick posting and void notices"
Cohesion: 0.02
Nodes (74): DiscordVoidRejected, paused_row_exclusion_sql(), test_a_malformed_timestamp_drops_the_stamp_rather_than_raising(), test_a_real_pause_is_not_logged_as_stale(), execute(), test_american_odds_formatting(), test_delete_posted_degrades_when_the_column_is_missing(), test_empty_set_errors_when_a_stale_pause_flag_hides_bets() (+66 more)

### Community 170 - "NBA game model luck feature tests"
Cohesion: 0.05
Nodes (39): _Stop, _against_bet(), _f6c_inputs(), _games_for_standings(), _gs(), _market_pricing(), _one_game_data(), _pair() (+31 more)

### Community 174 - "tests/test_publisher_lock.py"
Cohesion: 0.07
Nodes (16): _Conn, _Result, _clear_locks(), _no_prod_threshold_sync(), _signal_row(), test_a_connection_that_cannot_lock_still_publishes(), test_an_exception_mid_publish_does_not_wedge_every_later_pass(), test_every_signal_publisher_takes_the_lock() (+8 more)

### Community 175 - "tests/test_dk_direct_feed.py"
Cohesion: 0.09
Nodes (22): _Conn, _game_id_for(), _row_for(), _seen_key(), _rec(), test_a_line_move_is_a_new_quote(), test_a_market_we_do_not_understand_is_dropped_not_guessed(), test_a_price_move_is_a_new_quote() (+14 more)

### Community 177 - "tests/test_credit_budget.py"
Cohesion: 0.09
Nodes (22): _Conn, daily_burn(), latest_remaining(), plan_credit_budget(), _burn_conn(), _plan(), test_a_billing_reset_is_not_a_refund(), test_a_call_is_billed_at_what_the_api_says_it_cost() (+14 more)

### Community 18 - "Mobile thresholds and daily results"
Cohesion: 0.02
Nodes (155): Case, Props, Props, CustomModelStats, Acc, DailyResults, DayGameSummary, ModelDayStats (+147 more)

### Community 180 - "NHL market-anchored moneyline model"
Cohesion: 0.05
Nodes (31): OffsetLogit, _Fixed, _GamesConn, _add_rating(), build_inputs(), choose_C(), decision_window(), fit() (+23 more)

### Community 186 - "NFL wind and opener publisher"
Cohesion: 0.08
Nodes (16): TestPublishOpenerInsertOnce, _LockConn, TestNoneRowNeverLocks, _changed(), _clear_scored_row(), _flush_board_safe(), _flush_snapshots_safe(), latest_eval_rows() (+8 more)

### Community 189 - "Settlement and self-heal tests"
Cohesion: 0.11
Nodes (25): _FakeStatsapi, _game(), _pick(), test_a_doubleheader_row_with_a_final_keeps_its_picks_grading(), test_a_final_game_is_never_voided(), test_a_game_with_any_box_score_row_is_not_refetched(), test_a_postponed_game_voids_its_pending_bets(), test_a_recent_postponement_waits_for_a_same_day_resumption() (+17 more)

### Community 19 - "NHL prop cards and blocked shots"
Cohesion: 0.03
Nodes (46): TestOddsFeedTeamNames, TestSeasonLabel, TestTonightsRowIsATrainingRow, fetch_all(), _fold(), load(), load_period_scores(), _num() (+38 more)

### Community 196 - "tests/test_ungraded_model_performance.py"
Cohesion: 0.08
Nodes (12): FakeConn, test_perf_reads_the_matview_not_the_expensive_view(), test_roster_reports_a_registered_but_untrained_model(), _second_arm(), _sql(), test_a_fully_unpriced_recovered_model_reports_no_roi(), test_a_recovered_row_still_reports_roi_over_the_priced_bets(), test_both_arms_stay_inside_the_settled_bet_gate() (+4 more)

### Community 197 - "Mobile pick detail load states"
Cohesion: 0.05
Nodes (53): CountInput, DetailBody, LoadBody, LoadInput, D(), K(), P(), R() (+45 more)

### Community 198 - "mobile/scripts/verify_push.ts"
Cohesion: 0.06
Nodes (46): PushState, PushStatus, ForcedOnlyReason, PushDiagnosis, PushFailureReason, TestPushResult, reasonOf(), NotificationsCard() (+38 more)

### Community 199 - "Prop price pregame cutoff tests"
Cohesion: 0.08
Nodes (14): _StubConn, _latest_dk_prop_row(), _assigned_from(), _prop_scorers(), test_every_scorer_call_site_passes_a_pregame_cutoff(), test_get_prop_dk_odds_forwards_the_cutoff(), test_in_play_snapshots_are_excluded_unconditionally(), test_it_fails_open_when_commence_time_is_missing() (+6 more)

### Community 2 - "Mobile markets and formatting"
Cohesion: 0.02
Nodes (238): Row, Props, IoniconName, Props, ClvBetRow, ClvBookRow, DecisionPriced, gameStartState (+230 more)

### Community 20 - "Probability calibration and cut sweeps"
Cohesion: 0.02
Nodes (92): RecordingConn, apply_calibration(), demote(), ensure_schema(), _era_start(), fetch_graded(), fit_model(), fit_offset() (+84 more)

### Community 200 - "NFL prop odds loading tests"
Cohesion: 0.09
Nodes (18): _Conn, _Cur, _fetch_slice(), _iter_prop_rows(), load_nfl_prop_odds(), load_nfl_prop_quotes(), _prop_slice_query(), statement_timeout_error() (+10 more)

### Community 203 - "tests/test_nhl_asof.py"
Cohesion: 0.19
Nodes (3): GoalieBook, TestGoalieAsOf, _g()

### Community 204 - "NFL prop features and walk-forward"
Cohesion: 0.04
Nodes (43): LazyConnection, name_key(), _add_features(), build_nfl_prop_scoring_rows(), build_nfl_prop_training_dataset(), _cols(), derived_targets(), _load() (+35 more)

### Community 205 - "Market-relative prop model edges"
Cohesion: 0.07
Nodes (26): MarketBet, devig(), find_bets(), card(), load_quotes(), _bets_from_kalshi(), _zero_vig_american(), _q() (+18 more)

### Community 207 - "Script connections and health utilities"
Cohesion: 0.01
Nodes (157): Pick, LabelSet, TestEveryOtherSportStillMintsItsOwn, get_connection(), main(), stored_files(), _etag_cache_path(), run_synthesizer() (+149 more)

### Community 209 - "data/ingestors/nfl_inplay_history.py"
Cohesion: 0.16
Nodes (22): Budget, buy_halftime(), buy_inplay(), events_for(), _floor5(), _get(), halftime_requests(), halftime_windows() (+14 more)

### Community 211 - "Mobile bankroll card math"
Cohesion: 0.09
Nodes (31): BankrollCheck, BankrollCommit, BankrollPatch, BankrollRead, NumberSeparators, Part, walk(), deviceSeparators() (+23 more)

### Community 212 - "Mobile in-app feedback flow"
Cohesion: 0.08
Nodes (46): useAuth, FeedbackCategory, FeedbackMessage, FeedbackSender, FeedbackStatus, FeedbackThread, Validation, showToast() (+38 more)

### Community 214 - "NHL props per-game limit tests"
Cohesion: 0.16
Nodes (4): TestInsertOnce, TestTheLimitPerGame, limit_per_game(), publish()

### Community 215 - "Core game scorer and config"
Cohesion: 0.01
Nodes (181): TestAmericanToImpliedProb, TestBuildPickLabel, TestConfidenceTier, TestMissingStarterGate, TestQuarterKelly, calibration_method(), today_et(), pregame_cutoff_sql() (+173 more)

### Community 217 - "NCAAF in-play locked pick tests"
Cohesion: 0.13
Nodes (12): FakeConn, _Rows, write_picks(), db(), test_both_lanes_locked_touches_nothing(), test_dry_run_never_touches_db(), test_first_bet_is_written_and_will_lock(), test_flag_off_restores_delete_and_replace() (+4 more)

### Community 22 - "NBA prop projection card"
Cohesion: 0.06
Nodes (37): Plan, step_mlb_total_public_fade(), step_nba_prop_project(), decided_games(), slate(), backfill_official(), decided_games(), ensure_tables() (+29 more)

### Community 220 - "tests/test_db_reconnect.py"
Cohesion: 0.09
Nodes (16): _Conn, _Cursor, _is_write(), _lost(), test_a_committed_transaction_is_clean_again(), test_a_lost_connection_with_uncommitted_writes_raises_connection_lost(), test_a_read_on_a_lost_connection_reconnects_and_retries(), test_a_statement_timeout_is_not_a_lost_connection() (+8 more)

### Community 223 - "tests/test_live_lock.py"
Cohesion: 0.10
Nodes (20): FakeConn, _Rows, _lane_signature(), _write_live_picks(), _locked_live_lanes(), test_the_lane_signature_carries_the_deciding_price(), _log_lines(), _pick() (+12 more)

### Community 225 - "tests/test_refresh_retry.py"
Cohesion: 0.14
Nodes (23): Decision, RefreshRun, _decide(), _done(), _run(), test_a_failed_view_migration_fails_the_step(), test_a_pass_that_finished_with_failed_steps_ran_its_chain(), test_a_redeploy_between_passes_replaces_nothing() (+15 more)

### Community 226 - "NBA results and box score ingestor"
Cohesion: 0.08
Nodes (20): PlayerResolver, call_in_savepoint(), statement_timeout(), parse_nba_dnp(), box_is_complete(), build_dnp_rows(), build_log_rows(), fallback_id() (+12 more)

### Community 228 - "NBA results ingestor tests"
Cohesion: 0.12
Nodes (23): _ESPN, FakeStore, _FixedNow, _game(), _resolver(), _run(), test_a_different_stored_score_is_never_overwritten(), test_a_failed_scoreboard_turns_the_step_red() (+15 more)

### Community 23 - "Mobile sportsbook betslip links"
Cohesion: 0.10
Nodes (39): BookApp, bookMarkLabel(), ParlayDkHandoff(), PlayerBetBar(), TeamLineCell(), useBookAppInstalled(), fillBetslipLink(), linkNeedsState() (+31 more)

### Community 230 - "tests/test_local_cache_is_additive.py"
Cohesion: 0.12
Nodes (8): _FakeConn, cached(), _frame(), test_a_first_ever_pull_still_works(), test_a_pull_that_lost_rows_keeps_them(), test_an_unreadable_cache_refuses_rather_than_overwrites(), test_rows_present_in_both_are_kept_once(), test_the_pull_ITSELF_is_additive()

### Community 231 - "tests/test_calibration_check_coverage.py"
Cohesion: 0.11
Nodes (18): _Shim, _bet(), _calibration_results(), db(), _graded(), _make_db(), _only(), _promote() (+10 more)

### Community 233 - "tests/test_book_team_map.py"
Cohesion: 0.11
Nodes (15): _Conn, abbr_from_team_string(), resolve_game_id(), split_matchup(), test_a_non_mlb_sport_is_refused_rather_than_guessed(), test_a_string_with_no_at_sign_is_refused(), test_a_unique_game_resolves(), test_an_ambiguous_game_resolves_to_none() (+7 more)

### Community 234 - "tests/test_team_board_cache.py"
Cohesion: 0.08
Nodes (11): _Conn, _Cursor, refresh_team_board_cache(), team_board_pairs(), team_board_seasons(), _cols(), test_every_team_sport_gets_last_this_and_next_year(), test_one_failing_pair_does_not_stop_the_rest() (+3 more)

### Community 236 - "Discord signal notifier tests"
Cohesion: 0.06
Nodes (24): _FakeConn, _FakeResult, _StampConn, _freeze_now(), _row(), _setup(), test_a_pick_for_tomorrow_is_announced_under_TOMORROWS_date(), test_a_pre_game_stamp_is_to_the_minute_not_the_second() (+16 more)

### Community 238 - "nfl/live_model/tests/test_rush_attempt_pace.py"
Cohesion: 0.07
Nodes (21): Read, pace_ratio(), _sigmoid(), under_prob(), _price(), test_a_line_he_has_already_passed_is_not_a_live_proposition(), test_a_missing_accrued_count_is_refused_not_treated_as_zero(), test_a_reachable_over_is_declined_rather_than_faded() (+13 more)

### Community 239 - "tests/test_nfl_poll_fast_silence.py"
Cohesion: 0.11
Nodes (15): FakeConn, publish_board(), _append_board(), _body(), _row(), _sent(), _setup(), test_a_half_written_last_row_waits_for_the_next_tick() (+7 more)

### Community 24 - "NHL moneyline and market research scripts"
Cohesion: 0.03
Nodes (116): OffsetLogit, accuracy(), first_games(), logloss(), main(), sweep(), units(), walk() (+108 more)

### Community 244 - "tests/test_weather_lookahead.py"
Cohesion: 0.09
Nodes (11): _Resp, TestTheHourIsTheGamesOwn, TestTheRequestCoversTheTargetHour, _celsius_to_f(), _fetch_open_meteo(), _game_hour_utc(), _target_hour_utc(), _utc_offset_from_lon() (+3 more)

### Community 245 - "tests/test_nhl_asof.py"
Cohesion: 0.13
Nodes (4): TeamBook, TestBlendedTeamInputs, TestTeamRatesAsOf, _r()

### Community 247 - "tests/test_dk_freshness_parse.py"
Cohesion: 0.12
Nodes (17): _FakeConn, _FakeResult, _american(), parse_dk_payload(), _store(), _payload(), test_a_half_priced_market_is_dropped_rather_than_half_recorded(), test_an_event_with_no_markets_yields_nothing_rather_than_raising() (+9 more)

### Community 248 - "NBA odds history gap filling tests"
Cohesion: 0.08
Nodes (22): _Ledger, _Meter, _Resp, gap_instants(), line_snapshots(), _hourly(), _t(), test_a_dropped_connection_replays_the_whole_write() (+14 more)

### Community 249 - "models: slate_concentration + test_slate_concentration"
Cohesion: 0.15
Nodes (15): SlateConcentration, apply_slate_guard(), apply_slate_concentration_guard(), _attr(), _edge_of(), _is_bet(), measure_side_concentration(), _side_of() (+7 more)

### Community 25 - "NBA game rule testing harness"
Cohesion: 0.05
Nodes (48): Data, attach_fetch(), blind_by_real_side(), blind_side(), boot(), cell_report(), cents(), check() (+40 more)

### Community 251 - "View migration lock handling tests"
Cohesion: 0.09
Nodes (23): _Conn, _Deadlock, _LockTimeout, _StatementTimeout, _Syntax, execute(), _before(), _code() (+15 more)

### Community 252 - "NFL prop injury veto"
Cohesion: 0.09
Nodes (19): _InjConn, apply_injury_veto(), _as_dt(), load_nfl_injury_index(), player_is_vetoed(), _bet(), _idx(), _quotes() (+11 more)

### Community 254 - "Fake database connection test doubles"
Cohesion: 0.05
Nodes (8): FakeConn, _R, test_the_prop_fetch_never_buys_a_game_it_was_not_given(), execute(), test_discord_free_pick_candidates_refuse(), execute(), fetchall(), row()

### Community 256 - "tests/test_ncaaf_search_features.py"
Cohesion: 0.07
Nodes (24): AdjRatings, blended_rating(), build_adjusted_ratings(), build_prior_season_ratings(), fit_opponent_adjustment(), rolling_variants(), _asof_merge(), build_matrix() (+16 more)

### Community 257 - "NCAAF walk-forward model search"
Cohesion: 0.06
Nodes (36): FoldResult, features_for(), _apply_calibration(), exponential_recency_weights(), _logit(), make_ensemble(), fit_predict(), make_lgbm() (+28 more)

### Community 26 - "Mobile data queries and team detail"
Cohesion: 0.02
Nodes (198): Props, FighterSide, Props, Props, Args, PlayerNewsState, PlayerPropQuote, PropContext (+190 more)

### Community 265 - "Best line threshold sweep"
Cohesion: 0.10
Nodes (12): _Conn, american_to_decimal(), units_at(), _row(), test_a_better_price_pays_more_than_the_dk_price(), test_a_loss_costs_one_unit_at_every_price(), test_a_push_is_flat(), test_a_retired_model_is_never_recommended_a_cut() (+4 more)

### Community 268 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.09
Nodes (8): TestBuildScoredRows, TestPickEmLabel, TestPreflightLockChecks, TestQualifyingRowIsNotANoneRow, _american_to_prob(), build_scored_rows(), _fmt_spread(), _num()

### Community 269 - "tests/test_cfbd_ingestor.py"
Cohesion: 0.07
Nodes (8): _GamesConn, _TeamsConn, test_ingest_games_retains_a_historical_utc_id_and_uses_et_for_a_new_row(), fake_get(), test_ingest_pulls_fbs_then_everyone_and_fbs_rows_win(), test_ingest_retries_everyone_without_a_year_if_the_season_filter_is_empty(), test_prior_context_tolerates_missing_talent_and_returning(), test_weekly_snapshot_build_aborts_on_failed_fetch()

### Community 27 - "Parlay builder and bet slip"
Cohesion: 0.02
Nodes (188): Props, ParlayRestorePayload, ResolvedSlip, GameLineLegSpec, GameLineMarket, LineLegSpec, LineSheetInput, LineSide (+180 more)

### Community 270 - "NCAAF in-play history tests"
Cohesion: 0.11
Nodes (15): _Conn, _StubEngine, resolve_game_id(), rows_for(), _cand(), _event(), _no_db_school_lookup(), test_a_late_kickoff_falls_back_to_its_utc_dated_games_row() (+7 more)

### Community 273 - "tests/test_prop_odds_utc_stamp.py"
Cohesion: 0.12
Nodes (13): _Conn, _assert_utc_stamp(), _frozen(), _run_mlb(), capture(), events(), _run_ncaaf(), test_an_eastern_row_then_a_later_utc_row_sorts_in_time_order() (+5 more)

### Community 274 - "Monitoring HTTP stream handler"
Cohesion: 0.29
Nodes (4): Handler, _connect(), dumps(), _json_default()

### Community 277 - "NCAAF game-day context tests"
Cohesion: 0.09
Nodes (16): _Conn, _Result, _fold(), load_context(), _night_twin(), _pair_key(), _row(), test_a_twin_does_not_silently_take_the_row_without_lines() (+8 more)

### Community 278 - "tests/test_feature_artifact_agreement.py"
Cohesion: 0.11
Nodes (13): _Stub, _TolerantUnpickler, _load(), _newest_artifact(), test_artifact_width_matches_its_own_feature_cols(), test_config_list_matches_the_trained_artifact(), test_known_drift_only_names_real_models(), test_pending_features_are_not_live_without_a_retrain() (+5 more)

### Community 279 - "NBA injury report date scope tests"
Cohesion: 0.20
Nodes (10): _DatesConn, garbled_note(), _rows(), test_a_report_whose_cells_do_not_line_up_with_its_header_is_not_stored(), test_all_players_available_is_a_team_row_not_the_tail_of_a_reason(), test_current_layout_2026(), test_nine_column_layout_2019(), test_scope_is_every_game_date_and_the_day_before_newest_first() (+2 more)

### Community 28 - "CLV price-taken tests"
Cohesion: 0.06
Nodes (27): _Conn, _Res, _fn(), _migration(), _pick(), test_a_draftkings_decided_row_is_unchanged(), test_a_legacy_row_that_cannot_be_re_measured_leaves_the_old_method(), test_a_legacy_stamped_row_is_re_measured_and_leaves_the_queue() (+19 more)

### Community 280 - "Mobile matchup, head-to-head and record verify"
Cohesion: 0.03
Nodes (81): MatchupGrade, MatchupInfo, TonightMatchupRow, walk(), check(), fakeServer(), main(), read() (+73 more)

### Community 281 - "tests/test_cloud_retrain_artifacts.py"
Cohesion: 0.10
Nodes (12): _Conn, _restore_artifact(), test_a_failed_upload_does_not_lose_a_model_that_trained(), test_a_missing_artifact_table_is_not_an_error_on_restore(), test_a_no_register_run_stores_nothing(), test_load_model_actually_loads_from_the_store_when_the_file_is_gone(), fetchone(), test_load_model_returns_none_when_the_store_has_nothing_either() (+4 more)

### Community 282 - "NHL totals card publishing"
Cohesion: 0.09
Nodes (18): NhlTotalBet, _LockConn, _SlateConn, pick_rows(), test_nfl_prop_market_card_drops_a_bet_under_the_floor(), test_nhl_totals_card_drops_a_bet_under_the_floor(), bet(), test_wnba_prop_market_card_drops_a_bet_under_the_floor() (+10 more)

### Community 284 - "NCAAF FBS registry tests"
Cohesion: 0.12
Nodes (10): TestRefusalLog, TestRegistryHealthCheck, _alarm_part(), _live_db(), _promoted(), _rating(), _registry_check(), _snapshot() (+2 more)

### Community 288 - "tests/test_nfl_opener.py"
Cohesion: 0.20
Nodes (5): TestBettableBooksOnly, TestSelectOpenerBets, _both_sides(), _frame(), _sched()

### Community 29 - "NBA injury report and schema guards"
Cohesion: 0.03
Nodes (53): ConnectionLost, Fetcher, _Fetcher, scoring_method(), lock_down(), _fetchone(), schema_is_current(), _all_slots() (+45 more)

### Community 291 - "tests/test_team_stats_asof_invariants.py"
Cohesion: 0.13
Nodes (6): _SeasonConn, test_verify_established_live_season_with_two_snapshots_stays_thin(), test_verify_five_day_span_with_one_snapshot_is_thin(), test_verify_four_day_opening_span_is_still_grace(), test_verify_opening_live_season_is_not_thin(), test_verify_short_historical_season_is_still_thin()

### Community 294 - "Game feature engines and backtester"
Cohesion: 0.02
Nodes (87): TestPregameSnapshotGuard, TestAmericanToDecimalScorer, query_injuries_for_game(), _blk_bullpen_ip(), _blk_injuries(), _blk_nhl_loc_goals(), _blk_nhl_rolling_goals(), _blk_pitcher() (+79 more)

### Community 295 - "Unit stake sizing and formatting"
Cohesion: 0.11
Nodes (12): UnitStake, test_flat_conviction_is_still_price_adjusted(), test_the_minus_110_example_matt_gave(), test_units_format_drops_the_trailing_zero(), test_units_format_keeps_the_second_decimal(), test_unpriced_picks_publish_conviction_and_claim_no_payout(), _doc(), _rows() (+4 more)

### Community 298 - "tests/test_nfl_wind_publisher.py"
Cohesion: 0.13
Nodes (10): TestBuildRows, TestKickFields, TestParseMatchup, build_rows(), _fmt_line(), kick_fields(), parse_matchup(), test_nfl_wind_and_opener_rows_drop_a_bet_under_the_floor() (+2 more)

### Community 3 - "Odds, prop odds and NHL derivative odds ingestors"
Cohesion: 0.01
Nodes (151): Meter, Meter, Meter, _Meter, _Resp, FakeResp, build_ncaaf_game_id(), _fold() (+143 more)

### Community 30 - "NFL live prop model tests"
Cohesion: 0.04
Nodes (39): _FakeOdds, _IdRecordingOdds, _Q, GamedayWorker, GameTracker, _core_worker(), test_a_deployed_bias_must_sit_inside_its_measured_interval(), test_a_matching_board_keeps_the_fast_cadence() (+31 more)

### Community 300 - "tests/test_health_reason_and_cadence.py"
Cohesion: 0.13
Nodes (16): Report, _one(), test_a_24h_ts_check_reads_as_daily(), test_a_bare_add_still_fills_both_columns(), test_a_broken_query_is_its_own_reason(), test_a_passing_check_says_fresh(), test_a_skipped_check_says_the_gate_was_shut(), test_a_ts_check_reports_its_own_max_age() (+8 more)

### Community 301 - "tests/test_live_publish_parity.py"
Cohesion: 0.17
Nodes (12): _Conn, _db(), _labels(), _pick(), test_a_bet_written_while_paused_is_not_announced_after_an_unpause(), test_a_live_health_state_still_publishes(), test_a_paused_model_is_not_announced(), test_a_retired_model_is_not_announced() (+4 more)

### Community 302 - "tests/test_nfl_weather_supabase_readback.py"
Cohesion: 0.13
Nodes (13): FakeConn, _patch_conn(), _rows(), test_a_null_requested_lead_is_not_returned(), test_a_one_lead_response_is_not_stored(), test_a_partial_window_is_not_returned(), test_a_store_failure_is_a_warning_not_an_error(), test_a_subset_of_leads_reads_only_those_columns() (+5 more)

### Community 308 - "Pitcher stats as-of invariant tests"
Cohesion: 0.06
Nodes (22): _FakeConn, build_rows(), _app(), test_a_doubleheader_emits_one_row_per_date(), test_a_fractional_part_that_is_not_thirds_raises(), test_a_rounding_artifact_on_a_tiny_sample_is_not_a_defect(), test_a_row_never_includes_its_own_start(), test_a_season_already_stored_as_a_real_series_is_protected() (+14 more)

### Community 309 - "tests/test_walk_forward_eval.py"
Cohesion: 0.11
Nodes (11): _Cols, _Frame, walk_forward(), _fake(), test_a_fold_with_too_little_history_is_skipped(), test_a_single_class_test_season_is_skipped(), _frame(), test_every_fold_trains_only_on_earlier_seasons() (+3 more)

### Community 31 - "NBA prop model core"
Cohesion: 0.03
Nodes (76): Spec, compact_report(), minutes_cols(), predict_means(), rate_cols(), alias_key(), all_rates(), apply_calibration() (+68 more)

### Community 312 - "Live scorer score-change guard"
Cohesion: 0.09
Nodes (19): _MlbConn, _FakeConn, _book_move(), _get_live_dk_odds(), _score_changed_at(), _mlb_odds(), _mlb_ts(), test_mlb_declines_a_total_that_moved_a_full_run_on_an_unchanged_state() (+11 more)

### Community 314 - "Pipeline log reason tests"
Cohesion: 0.22
Nodes (6): _Conn, _capture(), test_a_false_step_records_the_last_error_it_logged(), test_a_false_step_that_logged_nothing_still_says_so(), test_a_raising_step_still_records_the_exception(), test_the_sink_is_removed_after_the_step()

### Community 315 - "NHL props latest quote shopping"
Cohesion: 0.10
Nodes (8): _Conn, TestOnlyTheNewestFetchIsShopped, TestWhoThePlayerIs, candidates(), draftkings_at(), identities(), latest_quotes(), upcoming_rows()

### Community 316 - "NFL prop stats data ingestion"
Cohesion: 0.08
Nodes (16): TestKickoff, TestParsePlayerRows, TestParseTeamRows, TestUpcomingRows, backfill(), fetch_schedule(), _fetch_snap_csv(), ingest_season() (+8 more)

### Community 32 - "NCAAF in-play score distribution pricing"
Cohesion: 0.03
Nodes (56): ScoreDistribution, _cluster_bootstrap(), evaluate(), main(), report(), fit(), load_states(), main() (+48 more)

### Community 320 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.09
Nodes (6): _Pg, _PgCursor, TestPreflightCiMode, wind(), wrapped(), fake_open()

### Community 321 - "tests/test_system_health_checks.py"
Cohesion: 0.17
Nodes (4): TestSignalDelivery, _add_signal(), _iso(), _results()

### Community 322 - "Database cursor wrapper and replays"
Cohesion: 0.11
Nodes (5): _CursorResult, execute(), test_the_cursor_wrapper_rowcount_is_the_cursors(), test_a_dropped_connection_replays_the_migration_with_its_lock_timeout(), cursor()

### Community 323 - "NBA prop window scheduling tests"
Cohesion: 0.12
Nodes (21): _PlanConn, _fires(), _game(), _jobs(), _plan(), _t(), test_a_projection_too_old_to_price_does_not_block_the_retry(), test_a_tick_fetches_exactly_the_window_games_then_decides_closes_and_publishes() (+13 more)

### Community 327 - "tests/test_ncaaf_live_states.py"
Cohesion: 0.16
Nodes (13): _Conn, record_live_states(), state_change_row(), state_key(), _state(), test_a_failed_write_never_costs_the_pass(), test_a_score_a_period_or_a_possession_change_is_written(), test_first_sight_is_written() (+5 more)

### Community 33 - "nfl/live_model/feeds: test_feed_resilience + espn"
Cohesion: 0.04
Nodes (56): _ScriptedTick, norm_name(), _competitors(), _deref(), fetch_live_events(), _https(), make_fetcher(), fetch() (+48 more)

### Community 330 - "NFL opener card rows"
Cohesion: 0.27
Nodes (5): TestBuildOpenerRows, build_opener_rows(), _opener_model(), _card_row(), _row()

### Community 336 - "NFL pass attempt bias model"
Cohesion: 0.09
Nodes (11): Read, blind_over_prob(), over_prob(), _pass_attempt_bias_allowed(), test_blind_arm_no_longer_asserts_a_rate(), test_restoring_a_bias_is_one_constant(), test_the_gates_are_checked_before_the_no_bias_decline(), test_the_interval_spans_zero_so_the_lane_declines_to_price() (+3 more)

### Community 34 - "Prop alternate line ladder"
Cohesion: 0.06
Nodes (25): Ladder, Rung, _expit(), from_kalshi(), from_one_sided_overs(), _logit(), _monotone(), _ladder() (+17 more)

### Community 341 - "NFL wind totals model"
Cohesion: 0.14
Nodes (12): Bet, american_to_decimal(), american_to_prob(), apply_slate_cap(), devig_two_way(), evaluate_board(), kelly_stake(), model_under_prob() (+4 more)

### Community 342 - "tests/test_live_pick_features.py"
Cohesion: 0.18
Nodes (11): FakeConn, _record_live_features(), _pick(), test_a_live_bet_records_its_feature_row_and_lambda(), test_a_pick_with_no_feature_row_is_skipped_not_written_empty(), test_a_recorder_failure_is_rolled_back_to_its_savepoint(), test_a_recorder_failure_is_swallowed_rather_than_raised(), test_a_success_releases_its_savepoint() (+3 more)

### Community 348 - "Pregame price age tests"
Cohesion: 0.06
Nodes (22): _OddsConn, _TwoIdConn, _UfcBoardConn, _ago(), _clock(), _h2h_row(), _score_card(), test_a_bet_on_either_id_locks_the_model_for_both() (+14 more)

### Community 349 - "tests/test_prop_missing_features.py"
Cohesion: 0.14
Nodes (5): TestARowMissingAFeatureIsNotScored, TestEveryPropLoopGoesThroughTheHelper, TestTheUmpireIsTheDeclaredException, _frame(), helper()

### Community 35 - "Push notification deep link routing"
Cohesion: 0.16
Nodes (16): NavRef, PushRoute, PicksView, clearNativeLastResponse(), navigateTo(), responseIdentifier(), usePushDeepLink(), setSportForVisit() (+8 more)

### Community 350 - "MLB public fade top picks ranking"
Cohesion: 0.14
Nodes (17): PublicFadeBet, composite_score(), estimated_edge(), rank_score(), select_top_k(), _key(), ticket_money_gap(), take() (+9 more)

### Community 351 - "NFL in-play prop settlement"
Cohesion: 0.15
Nodes (14): _SqliteShim, _box(), conn(), _game(), _live_bet(), raw(), _row(), test_a_final_with_no_box_score_yet_waits() (+6 more)

### Community 353 - "tests/test_player_news_ingestor.py"
Cohesion: 0.10
Nodes (21): FakeResponse, fetch_espn_news(), absorb(), _to_item(), _article(), test_a_dead_feed_is_a_quiet_zero(), test_a_sport_with_no_espn_path_is_skipped(), test_a_sport_with_no_team_id_map_still_gets_its_league_feed() (+13 more)

### Community 354 - "NBA prop closing line tests"
Cohesion: 0.09
Nodes (12): _Conn, _Resp, due(), test_a_close_already_held_is_not_bought_again(), test_a_due_close_buys_one_call_of_the_bet_markets_and_reports_its_credits(), test_a_pass_outside_the_window_spends_nothing(), test_only_a_game_holding_a_bet_and_only_once(), test_only_twelve_to_twenty_five_minutes_before_tip() (+4 more)

### Community 358 - "NFL in-play decline recording tests"
Cohesion: 0.12
Nodes (12): PicksRecorder, _AvoidConn, _mk_decline(), test_a_market_opinion_decline_is_written_as_avoid(), test_a_moved_line_is_rewritten(), test_an_unchanged_proposition_is_not_rewritten(), test_plumbing_refusals_stay_out_of_picks(), test_recording_a_decline_can_never_break_a_bet() (+4 more)

### Community 360 - "Prop player name matching tests"
Cohesion: 0.11
Nodes (15): FakeConn, normalize_player_name(), resolve_feed_name(), _get_prop_dk_odds(), test_accented_roster_name_matches_the_flat_feed_name(), test_ambiguity_is_a_miss_not_a_guess(), test_an_unlisted_player_is_still_a_miss(), test_every_prop_lane_keys_line_shopping_on_the_resolved_name() (+7 more)

### Community 363 - "tests/test_run_ledger_orphans.py"
Cohesion: 0.12
Nodes (18): _Conn, db(), _insert_open(), _ledger(), _open_rows(), _row(), test_a_genuine_current_hang_is_still_detectable(), test_a_second_sweep_does_not_abort_the_pass_this_process_started() (+10 more)

### Community 37 - "NBA lineup stints from play-by-play"
Cohesion: 0.05
Nodes (48): Diagnostics, _Seg, score_plays(), _accumulate(), _add_one(), _and_one_follows(), appearances(), _athletes() (+40 more)

### Community 378 - "NFL DraftKings line snapshots"
Cohesion: 0.08
Nodes (13): TestDkLineRows, TestPublishLineSnapshots, TestSnapshotRowParams, append_snapshot_csv(), dk_line_rows(), dump_dk_lines(), _num(), snapshot_schedule() (+5 more)

### Community 380 - "NFL historical weather fetch script"
Cohesion: 0.18
Nodes (10): DailyLimit, Pacer, consolidate(), era5_check(), game_hours(), log(), main(), om_get() (+2 more)

### Community 381 - "tests/test_heartbeat_disabled_jobs.py"
Cohesion: 0.14
Nodes (8): Conn, _build(), test_a_job_marked_disabled_is_not_silent(), test_a_job_that_runs_here_is_not_marked(), test_a_service_leaves_alone_the_jobs_another_service_owns(), test_startup_marks_an_owned_job_that_is_switched_off(), ensure_schema(), stale_jobs()

### Community 387 - "tests/test_repair_bogus_first_pitch_labels.py"
Cohesion: 0.13
Nodes (8): _Conn, _run(), test_a_dry_run_writes_nothing_at_all(), test_a_short_backup_rolls_back_and_relabels_nothing(), test_the_backup_is_written_before_the_update(), test_the_backup_table_is_revoked_from_the_public_roles(), test_the_bogus_set_is_computed_never_listed(), test_the_query_is_scoped_to_the_scheduled_start_not_the_derived_one()

### Community 39 - "nfl/live_model/tests/test_executor.py"
Cohesion: 0.06
Nodes (46): Decision, Executor, derivative_lag(), ev_floor(), _mk(), expected_value(), honest_probability(), is_hunt_state() (+38 more)

### Community 393 - "tests/test_sbr_loader.py"
Cohesion: 0.14
Nodes (3): _SqliteConnShim, _SqliteCursorShim, loader_conn()

### Community 397 - "mobile/scripts/ux_scan.mts"
Cohesion: 0.16
Nodes (18): Finding, Severity, changedFiles(), entitlementGate(), fontScaling(), fontSizeLiterals(), hexColors(), main() (+10 more)

### Community 4 - "Shared database connection and settlement"
Cohesion: 0.01
Nodes (165): DBConnection, TestFbsGate, TestUnratedFbsClaim, TestNflResolvesOntoTheSchedule, TestTheResolverFailsClosed, TestTrainingExcludesThemAndScoringDoesNot, _build_synthetic_rows(), _compute_calibration_factor() (+157 more)

### Community 408 - "Price prefilter timeout rollback tests"
Cohesion: 0.15
Nodes (9): _PoisonConn, _event_index(), _games(), _run(), test_a_failed_savepoint_rollback_falls_back_to_full_rollback(), test_both_prefilters_timing_out_still_reaches_the_pipeline_log(), test_lookahead_timeout_rolls_back_and_scoring_continues(), test_ncaaf_timeout_rolls_back_and_scoring_continues() (+1 more)

### Community 409 - "mobile/src/lib/otaUpdate.ts"
Cohesion: 0.21
Nodes (11): Calls, CheckState, CheckTrigger, UpdateOutcome, UpdatesApi, check(), fakeApi(), main() (+3 more)

### Community 41 - "tests/test_live_quote_staleness.py"
Cohesion: 0.05
Nodes (42): _Conn, _Q, build_row(), quote_from_nfl_quotes(), rows_from_quote(), _abbrev(), rows_for_quotes(), _parse_book_markets() (+34 more)

### Community 410 - "NFL prop one side per line"
Cohesion: 0.14
Nodes (9): _Conn, best_per_prop(), select_prop(), _hockenson(), test_a_different_market_on_the_same_player_is_still_its_own_bet(), test_input_order_does_not_decide_the_side(), test_nfl_publish_will_not_add_the_other_side_of_a_locked_line(), test_opposite_sides_of_one_line_collapse_to_the_bigger_edge() (+1 more)

### Community 412 - "NHL goalie saves settlement tests"
Cohesion: 0.20
Nodes (6): _Shim, TestSettlement, _bet(), _in_goal(), _result(), _skated()

### Community 416 - "UFC stats fighter resolution"
Cohesion: 0.09
Nodes (13): _FakeConn, _resolve(), test_confirmed_aliases_resolve_to_ufcstats_slug(), test_resolve_anchor_declines_when_opponent_changed(), test_resolve_anchor_matches_every_real_name_variant(), test_resolve_anchor_refuses_a_late_replacement(), test_resolve_anchor_refuses_every_real_stale_booking_on_its_own(), test_resolve_anchor_rescues_unmapped_variant() (+5 more)

### Community 422 - "NBA prop stat settlement tests"
Cohesion: 0.11
Nodes (9): _SelectConn, test_a_missing_stat_is_none_not_zero(), test_a_turnovers_bet_on_a_player_who_played_settles_win_not_no_action(), test_combo_markets_are_mapped_to_helpers_and_only_the_nba_rule_uses_them(), test_double_double_matches_the_rule_it_replaced(), test_the_loader_carries_every_stat_a_market_settles_on(), test_the_loader_selects_turnovers(), _load_nba_prop_actuals() (+1 more)

### Community 423 - "Weather lookahead window tests"
Cohesion: 0.12
Nodes (3): TestTheWeatherStepWalksTheWindow, _nhl_blended_features(), d()

### Community 424 - "supabase/functions/_shared/discord.ts"
Cohesion: 0.20
Nodes (15): DiscordApiError, DiscordUser, RoleSyncResult, addAppRole(), addGuildMember(), botFetch(), expectOk(), isGuildMember() (+7 more)

### Community 428 - "NFL prop market Kalshi bet finding"
Cohesion: 0.09
Nodes (11): TestMarketRelative, TestNaNIsAbsent, find_bets(), _ladder(), test_fetch_helper_swallows_errors(), test_kalshi_is_not_graded_until_settled_history_exists(), test_kalshi_outside_the_ladder_is_refused_not_extrapolated(), test_kalshi_prices_a_line_pinnacle_cannot() (+3 more)

### Community 43 - "tests/test_job_queue.py"
Cohesion: 0.02
Nodes (70): _Conn, _DedupeConn, _VoidConn, _fake(), _posted_row(), _run_void(), _run_void_job(), test_a_busy_queue_claims_nothing() (+62 more)

### Community 432 - "System health report checks"
Cohesion: 0.16
Nodes (6): HealthReport, test_a_late_check_says_how_late(), test_days_late_falls_back_rather_than_lying(), _days_late(), _games_count(), _scalar()

### Community 433 - "tests/test_system_health_checks.py"
Cohesion: 0.16
Nodes (3): TestPassCompletion, TestPassSteps, _add_run()

### Community 435 - "UFC event ingest tests"
Cohesion: 0.11
Nodes (7): _IngestConn, _ingest(), _one_fight_event(), test_a_late_replacement_is_not_scored_on_the_original_booking(), test_a_misspelled_fighter_is_scored_for_the_side_they_fought_on(), test_a_row_naming_neither_fighter_is_left_unscored(), test_the_same_fight_stored_twice_is_scored_on_both_rows_each_way_round()

### Community 436 - "tests/test_mlb_sbr_twin.py"
Cohesion: 0.21
Nodes (9): _Conn, _Cur, _lookup_home_won(), mlb_game_final(), sbr_twin_id(), test_no_final_anywhere_is_none(), test_scored_canonical_row_wins_and_keeps_its_label(), test_twin_id_swaps_only_the_renamed_franchises() (+1 more)

### Community 437 - "tests/test_ufc_phantom_filter.py"
Cohesion: 0.21
Nodes (6): TestFilterUfcPhantom, TestIsKnownUfcMatchup, _filter_ufc_phantom(), _is_known_ufc_matchup(), _game(), _odds()

### Community 442 - "tests/test_batter_prop_log_pin.py"
Cohesion: 0.15
Nodes (7): _Rec, _log_sql(), test_batter_log_scan_is_pinned_to_the_lookback_not_the_catalog(), test_no_lineup_does_not_scan_the_log(), test_starter_log_inside_the_batter_loader_uses_the_same_floor(), test_the_batter_loop_hands_one_cache_to_every_model(), test_training_from_the_tables_first_season_still_reads_the_prior_year()

### Community 445 - "NFL CLV backtest and feature build"
Cohesion: 0.08
Nodes (21): ShrunkEnsemble, add_form(), build(), feature_columns(), market_features(), team_game_stats(), fmt(), main() (+13 more)

### Community 446 - "tests/test_merge_mlb_twin_games.py"
Cohesion: 0.13
Nodes (12): _Conn, apply_one(), canonical(), counts(), main(), plan(), test_a_canonical_id_maps_to_nothing(), test_a_non_mlb_or_malformed_id_is_left_alone() (+4 more)

### Community 448 - "tests/test_discord_channel_probe.py"
Cohesion: 0.17
Nodes (7): _Resp, test_the_probe_covers_the_per_sport_live_channels(), test_the_probe_never_posts_and_never_returns_the_url(), test_the_probe_reports_the_channel_behind_each_sport(), _get(), test_two_sports_sharing_a_channel_are_flagged(), _job_discord_probe()

### Community 45 - "tests/test_nfl_prop_one_read_per_game.py"
Cohesion: 0.06
Nodes (25): _Conn, _Log, publish_hour_missed(), publishable_games(), _at(), _games(), test_a_game_is_publishable_on_exactly_one_pass_in_its_window(), test_a_game_with_no_kickoff_is_never_published() (+17 more)

### Community 451 - "Game outcome target tests"
Cohesion: 0.17
Nodes (5): TestComputeTarget, _compute_target(), test_a_push_yields_no_target(), test_spread_target_uses_the_home_relative_line(), test_totals_and_moneyline_targets()

### Community 457 - "NFL in-play pick builder tests"
Cohesion: 0.13
Nodes (10): _Decision, build_pick(), test_a_locked_lane_writes_nothing_further(), test_a_pass_is_never_announced(), test_edge_is_the_platform_edge_not_the_lanes_ev(), test_every_row_key_is_actually_bound_by_the_insert(), test_the_label_agrees_with_the_side_and_the_line_it_carries(), test_the_label_names_the_stat_the_model_actually_trades() (+2 more)

### Community 466 - "Mobile billing paywall and purchases"
Cohesion: 0.02
Nodes (248): AccessState, useAccess, AuthState, AuthStatus, useEntitlement, LivePicksState, ConnectionMap, providerMeta (+240 more)

### Community 469 - "Multi-book odds reading tests"
Cohesion: 0.07
Nodes (18): _OddsConn, _odds_query(), _prop_markets(), _source(), test_a_game_with_no_commence_time_keeps_every_row(), test_closing_line_reads_name_the_book(), test_draftkings_is_always_first_line_shop_book(), test_feature_engines_whitelist_draftkings() (+10 more)

### Community 47 - "scripts/nfl_edge_gameline_rules.py"
Cohesion: 0.09
Nodes (47): Tee, ats(), bettable_ats(), bh(), board_at(), board_open(), bstat(), cell() (+39 more)

### Community 470 - "CLV off DraftKings line tests"
Cohesion: 0.14
Nodes (7): _Conn, _Res, test_a_pick_draftkings_never_hung_closes_at_the_bet_book(), test_a_row_that_carries_dk_odds_keeps_its_book_and_price(), test_the_backfill_queues_the_dates_of_those_picks(), test_without_pinnacle_the_primary_is_still_the_bet_book(), _ts()

### Community 471 - "tests/test_model_game_savepoint.py"
Cohesion: 0.15
Nodes (4): _PoisonConn, _games(), test_a_best_price_timeout_is_the_logged_error_and_the_next_lookup_runs(), test_a_model_sql_error_does_not_poison_the_next_model()

### Community 475 - "tests/test_system_health_checks.py"
Cohesion: 0.14
Nodes (4): _FrozenDatetime, _Shim, db(), mlb_wired()

### Community 48 - "tests/test_calibration_watch.py"
Cohesion: 0.05
Nodes (15): _Conn, _Res, TestDormantLiveModels, TestItNeverDecides, TestRosterChanges, TestTheRun, TestVerdictChanges, TestVolumeShifts (+7 more)

### Community 482 - "tests/test_promote_external.py"
Cohesion: 0.18
Nodes (4): _Conn, test_external_promotion_refuses_a_map_that_does_not_transfer(), test_external_promotion_writes_only_the_promoted_columns(), test_the_scorer_reads_the_external_map_like_any_promoted_one()

### Community 485 - "NFL in-play leader decision model"
Cohesion: 0.17
Nodes (10): Artifact, Decision, am_to_dec(), artifact_from_dict(), band_for(), decide(), leader_expected_margin(), load_artifact() (+2 more)

### Community 486 - "tests/test_pipeline_report_rollback.py"
Cohesion: 0.14
Nodes (6): _Conn, _rows(), test_a_failed_query_rolls_back(), test_every_section_is_still_present(), test_one_broken_section_does_not_break_the_rest(), test_the_health_check_query_does_not_compare_text_to_a_date()

### Community 488 - "NBA results Postgres store"
Cohesion: 0.15
Nodes (4): PgStore, _games(), _schedule(), end()

### Community 49 - "Failure alerter fake-connection tests"
Cohesion: 0.06
Nodes (19): FakeConn, TestDeliveryAndNoise, TestHealthCheckOnlyIsNotADirtyPass, TestItCannotBreakTheWorker, TestSilentJobs, TestWhatCountsAsAFailure, _clean_runs(), _posts() (+11 more)

### Community 496 - "MLB prop pregame price cutoff tests"
Cohesion: 0.12
Nodes (7): _Conn, test_a_game_with_no_cutoff_fails_open(), test_both_market_relative_loaders_bound_on_the_cutoff(), test_it_compares_parsed_timestamps_not_strings(), test_it_joins_games_and_uses_the_shared_cutoff(), test_the_newest_qualifying_quote_still_wins(), test_the_post_first_pitch_quote_is_dropped_even_though_it_is_newest()

### Community 497 - "Player news ingestor tests"
Cohesion: 0.10
Nodes (13): FakeConn, build_name_index(), ingest_player_news(), main(), prune_old(), test_a_fresh_table_is_not_refetched(), test_a_sport_with_no_game_log_has_no_index(), test_an_accented_name_resolves_to_our_player_id() (+5 more)

### Community 5 - "Mobile app screens and theme"
Cohesion: 0.02
Nodes (320): IoniconName, Props, Nav, Props, EquityPoint, Props, Props, FilterChipProps (+312 more)

### Community 501 - "NFL prop stat distribution tests"
Cohesion: 0.12
Nodes (4): TestBinaryMarket, TestCountDistributions, TestYardageDistribution, _art()

### Community 511 - "Prop odds next-day lookahead"
Cohesion: 0.17
Nodes (4): TestTheOddsFetchReachesTomorrow, TestTheScorerReachesTomorrow, _get_events(), _events_src()

### Community 514 - "NFL live leader config tests"
Cohesion: 0.09
Nodes (10): Gate, expected_value(), honest_probability(), test_expected_value_is_on_the_quoted_price(), test_a_loop_that_dies_fails_its_job(), test_it_decides_on_its_own_probability(), test_the_action_threshold_key_is_on_one_line(), test_the_ev_floor_cannot_bind_with_the_live_global_floor() (+2 more)

### Community 518 - "NHL blocked shots settlement tests"
Cohesion: 0.27
Nodes (5): _Shim, TestSettlement, _bet(), _played(), _result()

### Community 519 - "Monitoring server tests"
Cohesion: 0.04
Nodes (44): _Resp, _credits_from(), _drain(), _enqueue(), instrumented(), _patch_curl_cffi(), instrumented(), record() (+36 more)

### Community 52 - "tests/test_best_line_live.py"
Cohesion: 0.04
Nodes (45): _FakeConn, _best_live_price(), _best_live_side(), _live_book_quotes(), _live_decision_quote(), _live_quote_is_on_offer(), best_takeable_quote(), _ev() (+37 more)

### Community 526 - "MLB in-play game state alignment"
Cohesion: 0.24
Nodes (6): GameClock, _t(), test_before_first_pitch_and_after_last_play_are_not_priced(), test_between_pas_across_third_out_rolls_over_to_next_half(), test_mid_plate_appearance_is_that_pa_before_state(), test_plays_without_times_are_ignored()

### Community 528 - "WNBA injury returnee feature tests"
Cohesion: 0.18
Nodes (3): TestHasReturnee, _has_returnee(), _assemble_wnba_features()

### Community 533 - "NFL wind card book filter tests"
Cohesion: 0.07
Nodes (10): TestTheCardFilters, TestTheListIsShared, test_the_decisions_ledger_is_worker_only_and_created_behind_the_guard(), test_a_replay_never_prices_off_todays_ladder_even_when_on(), test_the_card_does_not_price_off_kalshi_until_it_is_graded(), _attach(), books(), card() (+2 more)

### Community 536 - "Closing line value backfill job"
Cohesion: 0.15
Nodes (5): _Conn, _stub_backfill(), test_hard_cap_stops_a_nonempty_queue(), test_loops_until_a_pass_fills_nothing(), test_the_runner_opens_get_connection_and_calls_backfill_clv()

### Community 54 - "tests/test_void_picks.py"
Cohesion: 0.05
Nodes (18): _FakeConn, TestAPostedSignalIsLocked, TestAPostedVoidAnnouncesAfterCommit, TestTheToolRefusesToMatchEverything, TestVoidingAPostedPickIsAnExplicitOptIn, TestWhatMayBeVoided, TestWhatTheVoidWrites, announce_posted_voids() (+10 more)

### Community 541 - "Pipeline staleness watch tests"
Cohesion: 0.14
Nodes (8): _Conn, test_a_fresh_sweep_and_savant_produce_no_finding(), test_a_missing_sweeps_table_is_reported_not_swallowed(), test_a_missing_webhook_is_not_ledgered_either(), test_a_stale_sweep_date_is_reported(), test_savant_with_only_one_player_type_is_stale_even_when_dated_today(), test_the_silence_finding_says_how_regular_the_kind_was(), _stale_weeklies()

### Community 55 - "NCAAF in-play gameday loop"
Cohesion: 0.05
Nodes (24): LiveOddsFeed, _mark_written(), now_iso(), _publish_key(), record_live_prices(), game_index(), record_nfl_anchor_prices(), fetch_scoreboard_cfbd() (+16 more)

### Community 551 - "NHL blocked shots card tests"
Cohesion: 0.19
Nodes (4): TestTheCard, pick_rows(), _scored(), execute()

### Community 56 - "tests/test_daily_retry.py"
Cohesion: 0.06
Nodes (42): _Conn, _Cursor, _FrozenDatetime, DailyRun, _aborted(), _aborted_row(), _ok(), _ok_row() (+34 more)

### Community 561 - "Feature engine injury adjustment"
Cohesion: 0.16
Nodes (4): TestComputeInjuryAdjustment, TestMarketForOdds, _compute_injury_adjustment(), _market_for_odds()

### Community 567 - "NFL in-play pick writer commit order"
Cohesion: 0.12
Nodes (7): _Conn, test_a_pass_is_never_written_to_picks(), test_an_unresolvable_decision_writes_nothing(), test_game_id_resolves_from_the_book_s_team_names(), test_picks_recorder_drops_a_pass_attempt_over_before_sql(), test_the_announce_runs_after_the_commit_and_after_the_connection_closes(), commit()

### Community 57 - "tests/test_live_book_move_guard.py"
Cohesion: 0.10
Nodes (31): BookMoveClock, american_to_implied(), _at(), _delaware_ctx(), _dk(), _iso(), _ncaaf_engine(), _nfl() (+23 more)

### Community 576 - "tests/test_weekly_catch_up.py"
Cohesion: 0.18
Nodes (3): _Conn, test_a_failing_savant_refresh_does_not_cost_the_calibration_its_catch_up(), test_ownership_is_checked_per_job()

### Community 58 - "tests: test_discord_notifier + test_discord_live_field"
Cohesion: 0.08
Nodes (23): _FakeConn, _sig(), test_a_strictly_better_book_becomes_the_headline(), test_an_equal_or_worse_price_never_replaces_draftkings(), test_draftkings_winning_its_own_shop_is_published_as_draftkings(), test_every_pre_game_producer_computes_good_to(), test_good_to_is_published_when_the_producer_supplies_it(), test_good_to_is_simply_absent_when_it_cannot_be_computed() (+15 more)

### Community 582 - "Prop odds book update-time tests"
Cohesion: 0.26
Nodes (6): _Conn, _parse(), test_a_row_built_without_the_key_still_inserts_as_null(), test_no_clock_anywhere_is_none_not_our_fetch_time(), test_the_column_is_added_only_when_the_catalog_lacks_it(), test_the_markets_own_clock_is_stored_else_the_books()

### Community 583 - "NFL pick monitor"
Cohesion: 0.14
Nodes (7): TestClassify, TestImmutabilityContract, TestLatestPerPick, TestWindPublisherLock, classify(), latest_per_pick(), _row()

### Community 59 - "Shared scripts, probes and odds pulls"
Cohesion: 0.02
Nodes (83): OddsAPIClient, SnapshotResult, Puller, JsonlRecorder, _fmt_et_time(), get_conn(), query(), configured() (+75 more)

### Community 591 - "Push notifier and publish key identity"
Cohesion: 0.02
Nodes (58): _Conn, _Conn, _KeyConn, run(), _sql_key(), _sql_for(), test_a_started_game_is_still_never_published(), test_both_publishers_apply_the_apps_action_filter() (+50 more)

### Community 592 - "NFL pick monitor id matching"
Cohesion: 0.16
Nodes (3): TestTheJoinKeyMatchesPicks, eval_row(), _picks_game_id()

### Community 595 - "Voided picks never rechosen tests"
Cohesion: 0.21
Nodes (4): _Conn, _db(), test_a_voided_pick_is_not_a_free_pick_candidate(), test_a_voided_pick_is_not_a_parlay_leg()

### Community 597 - "Multi-book fallback response tests"
Cohesion: 0.20
Nodes (7): _Resp, test_a_rejected_book_list_falls_back_to_the_decision_book(), _get(), test_the_fallback_does_not_recurse_forever(), _get(), test_the_per_event_fetch_asks_for_every_book(), _get()

### Community 6 - "Stale quote price decision tests"
Cohesion: 0.10
Nodes (14): FakeConn, emit(), main(), _rules(), _source(), test_a_quote_with_no_stamp_is_kept(), test_a_stale_quote_cannot_decide(), test_every_scorer_insert_carries_the_decision_columns() (+6 more)

### Community 600 - "Player news feed ingest"
Cohesion: 0.09
Nodes (16): NewsItem, NewsPlayer, _article_url(), _athletes_in(), _fetch_espn(), _minutes_since_last_ingest(), _parse_published(), store_items() (+8 more)

### Community 61 - "mobile/src/hooks: verify_tracked_performance + useStakeSettings"
Cohesion: 0.09
Nodes (40): StakeMode, StakeState, LiveTrackSnapshot, TrackedBetRow, trackedBetStatus, TrackedBetSummary, emit(), load() (+32 more)

### Community 611 - "supabase/functions/revenuecat-webhook/index.ts"
Cohesion: 0.22
Nodes (3): RcEvent, admin, PRODUCT_TO_PLAN

### Community 613 - "supabase/functions/whop-webhook/index.ts"
Cohesion: 0.25
Nodes (4): WhopMembership, signatureValid(), timingSafeEqual(), admin

### Community 615 - "tests/test_model_quality.py"
Cohesion: 0.22
Nodes (3): _Shim, _insert_open_bet(), test_run_persists_all_unders_fade_slate_as_crit()

### Community 621 - "Health check skip budget"
Cohesion: 0.16
Nodes (6): FakeConn, test_a_check_never_seen_non_skipped_counts_its_whole_history(), test_a_check_skipped_only_today_is_not_counted_as_a_streak(), test_streak_counts_calendar_days_from_the_last_non_skipped_run(), test_the_streak_query_fails_open(), _skip_run_days()

### Community 626 - "NHL as-of feature leak tests"
Cohesion: 0.22
Nodes (4): TestOpeningNightIsEarlySeason, _blk_nhl_asof(), _t(), test_the_training_path_reads_nhl_odds_by_game_not_by_sport()

### Community 63 - "Football in-play game state"
Cohesion: 0.09
Nodes (24): GameState, _as_float(), _as_int(), _as_opt_float(), _as_opt_int(), from_espn(), from_extract(), from_pbp_row() (+16 more)

### Community 631 - "NFL forecast weather fetching"
Cohesion: 0.09
Nodes (19): OpenMeteoError, rows_from_file(), source_for(), stadium_from_name(), fetch_era5(), fetch_issued_forecasts(), fetch_live_forecast(), _frame() (+11 more)

### Community 633 - "NFL prop odds local cache"
Cohesion: 0.26
Nodes (5): TestLocalOddsCache, _odds_from_frame(), _p(), _odds_frame(), test_a_one_way_market_stays_one_way_through_the_cache()

### Community 636 - "Prop alternate lines fetch tests"
Cohesion: 0.14
Nodes (9): _Resp, test_a_422_retries_without_the_alternates_before_going_dk_only(), fake_get(), test_a_422_with_no_alternates_still_takes_the_dk_only_retry(), fake_get(), test_a_rejected_football_alternate_chunk_costs_only_itself(), fake_get(), test_football_live_slate_requests_alternates_and_a_backfill_does_not() (+1 more)

### Community 642 - "NFL prop odds reader tests"
Cohesion: 0.24
Nodes (3): TestPropOddsLoader, _Conn, _Cur

### Community 643 - "Mobile bankroll storage"
Cohesion: 0.23
Nodes (12): KeyValueStore, check(), eq(), fakeStore(), interleaving(), slowStore(), storage(), createBankrollStore() (+4 more)

### Community 645 - "NBA injury report PDF parser"
Cohesion: 0.18
Nodes (9): Report, finish_rows(), parse_pdf(), parse_title(), rows_from_pages(), season_of(), test_finish_rows_builds_our_game_id_and_season(), test_report_time_comes_from_the_header_and_is_stored_in_utc() (+1 more)

### Community 65 - "NFL live score distribution and calibration"
Cohesion: 0.07
Nodes (20): ScoreDistribution, _cluster_bootstrap(), evaluate(), main(), report(), fit(), load_states(), main() (+12 more)

### Community 662 - "Signal publish-on-write tests"
Cohesion: 0.06
Nodes (18): _Conn, _body(), _row(), _surfaces(), _make(), test_a_broken_webhook_does_not_suppress_the_push(), test_a_failed_capture_still_delivers(), test_a_publish_failure_does_not_kill_the_tick() (+10 more)

### Community 668 - "NFL prop market grading"
Cohesion: 0.33
Nodes (3): TestMarketGrading, grade(), season_of()

### Community 67 - "tests/test_game_market_gate.py"
Cohesion: 0.06
Nodes (49): GateVerdict, MarketBookend, PublicSplits, apply_to_picks(), _as_float(), bookend_from_odds(), evaluate(), fair_prob() (+41 more)

### Community 68 - "NBA second-model prop study"
Cohesion: 0.06
Nodes (40): Shape, appearances(), box_tables(), build(), check_close_prior(), consensus_number(), empty_times(), fit_shape() (+32 more)

### Community 689 - "First signal repair tests"
Cohesion: 0.18
Nodes (3): _Conn, _VoidedConn, _make()

### Community 69 - "tests/test_pick_integrity.py"
Cohesion: 0.05
Nodes (32): _Conn, _add_pick(), _health(), test_a_label_may_not_name_a_market_the_pick_does_not_settle_on(), test_a_label_naming_the_other_team_is_refused(), test_a_market_nobody_has_taught_it_is_never_refused(), test_a_moneyline_naming_the_other_team_is_refused(), test_a_producer_that_does_not_supply_side_and_line_is_refused() (+24 more)

### Community 693 - "NFL prop pull market list tests"
Cohesion: 0.22
Nodes (3): TestIngestEventsDoesNotShadowItsMarkets, test_live_prop_pull_asks_for_the_sharp_book(), fake_event_props()

### Community 70 - "tests/test_record_one_pick_per_event.py"
Cohesion: 0.04
Nodes (45): _CaptureConn, _RecordingConn, _code(), _copy_for_node(), _fn(), _node(), _read(), test_a_custom_model_counts_the_kept_copy_once() (+37 more)

### Community 73 - "nfl/live_model/tests: test_props + props"
Cohesion: 0.09
Nodes (33): PropProjection, PlayerState, _accrued(), _count(), detect_inactive(), price_over(), project(), _rate() (+25 more)

### Community 756 - "Prop no-bet rows kept to tipoff"
Cohesion: 0.12
Nodes (8): _Clock, _PollConn, _fake_datetime_class(), _game(), _iso(), test_the_poller_keeps_prop_no_bet_rows_the_refresh_pass_still_clears(), test_the_poller_tells_the_scorer_to_leave_prop_rows_alone(), _wire()

### Community 76 - "ncaaf_live/tests/test_serve.py"
Cohesion: 0.05
Nodes (47): GameContext, _abbrev_fits(), _clock_seconds(), extract_live_states_cfbd(), school(), _parse_situation(), _parse_yardline(), _strip_mascot() (+39 more)

### Community 77 - "tests/test_wnba_prop_market.py"
Cohesion: 0.06
Nodes (27): _FakeConn, _QuoteConn, apply_price_floor(), norm_name(), pick_rows(), f(), _bet(), _q() (+19 more)

### Community 772 - "Paused bets bankroll exclusion tests"
Cohesion: 0.18
Nodes (3): _Capture, test_a_paused_settled_bet_never_moves_the_kelly_bankroll(), test_todays_standing_bets_ignore_a_paused_row()

### Community 78 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.08
Nodes (17): _After, _Conn, _RaceConn, TestFlexedKickoffRefreshes, TestLockSurvivesNothing, TestNoneRowBesideABetIsCleared, TestPublishRace, TestPublishScored (+9 more)

### Community 79 - "NHL derivative totals model"
Cohesion: 0.07
Nodes (39): Market, build_p1_frame(), build_team_frame(), day_interval(), _ew(), fit(), game_means(), _implied_vec() (+31 more)

### Community 8 - "Mobile player log and matchup stats"
Cohesion: 0.02
Nodes (219): Props, PlayerNextGame, Section, Args, PlayerStatKey, HitMode, HitSelection, HitDirection (+211 more)

### Community 83 - "tests/test_nhl_props.py"
Cohesion: 0.07
Nodes (14): TestEveryLiveModelIsWiredEverywhere, TestTheBacktestGradesTheRuleTheCardPlays, TestTheCard, TestTheGoalieFrame, TestTonightsRowIsATrainingRow, implied(), card(), pick_rows() (+6 more)

### Community 84 - "Discord publish sync and void notices"
Cohesion: 0.03
Nodes (38): Ledger, test_a_game_level_key_has_no_tail(), test_a_published_void_keeps_track_and_betslip(), test_a_tracked_void_reads_not_graded_and_detail_closes_when_over(), test_an_opening_signal_is_live_only_when_discord_published_it(), test_discord_led_visibility(), test_opening_lock_join_is_not_wired_into_readers_yet(), test_the_app_predicate_matches() (+30 more)

### Community 85 - "tests/test_recap_retries_a_skipped_day.py"
Cohesion: 0.06
Nodes (25): _LiteConn, World, _add_pick(), _grade(), _lite(), _schema(), test_a_day_with_nothing_counting_posts_nothing_and_logs_nothing(), test_a_failed_receipt_never_reposts_the_day() (+17 more)

### Community 851 - "NBA odds archive rerun safety"
Cohesion: 0.22
Nodes (5): _Conn, load(), stored_keys(), test_a_rerun_writes_nothing_already_stored(), test_stored_rows_are_read_by_game_id_not_by_scanning_for_the_source()

### Community 853 - "NFL odds event game matching"
Cohesion: 0.29
Nodes (3): TestResolveGameId, resolve_nfl_game_id(), resolve()

### Community 857 - "Pregame line poller polling loop"
Cohesion: 0.09
Nodes (14): _PollConn, _fingerprint(), _key(), last_known_prices(), _num(), poll_once(), quoted_keys(), _quiet_poll() (+6 more)

### Community 858 - "NCAAF game-day fetch cadence"
Cohesion: 0.24
Nodes (6): _Ctx, _ev(), test_a_single_failed_summary_does_not_drop_the_other_games(), test_cfbd_mode_does_no_per_game_fetching(), test_espn_states_are_fetched_in_parallel_and_stay_aligned(), test_unknown_matchups_never_cost_a_fetch()

### Community 860 - "CFBD ingestor season failure tests"
Cohesion: 0.20
Nodes (6): _NullConn, test_backfill_returns_totals_when_every_season_succeeds(), test_backfill_survives_a_mid_run_season_failure(), test_refresh_games_happy_path_counts_games(), test_refresh_games_repairs_every_season_and_reports_failures(), test_refresh_stats_isolates_a_failing_season()

### Community 863 - "Odds pruning and sharp book retention"
Cohesion: 0.11
Nodes (9): _RecordingConn, _counts(), _older_than(), prune_table(), run_prune_odds(), test_prune_predicates_date_by_game_not_snapshot(), test_prune_rejects_keep_days_below_one(), test_prune_table_binds_the_prop_tables_carve_out_into_the_DELETE() (+1 more)

### Community 871 - "NFL in-play recorder fan-out"
Cohesion: 0.22
Nodes (4): TeeRecorder, test_a_failing_recorder_cannot_take_the_other_down(), boom(), test_the_audit_log_is_written_before_the_database()

### Community 878 - "NFL in-play pick writer locking"
Cohesion: 0.22
Nodes (4): _OpenConn, test_a_failing_announcer_cannot_undo_or_fail_the_write(), test_a_written_bet_is_announced_with_its_own_game_date(), test_an_unlocked_lane_does_write()

### Community 88 - "NBA prop market card tests"
Cohesion: 0.03
Nodes (60): NbaPropBet, NbaPropDecision, _PublishConn, _SettleConn, games_with_a_bet(), pick_label(), pick_rows(), projection_holdings() (+52 more)

### Community 880 - "Database schema statement splitter tests"
Cohesion: 0.19
Nodes (4): TestRealSchema, TestSplitter, TestSqliteSchema, _split_sql_statements()

### Community 881 - "Pick integrity test shims"
Cohesion: 0.22
Nodes (3): _Shim, discord_sent(), health_db()

### Community 882 - "SQLite connection shim for settlement"
Cohesion: 0.22
Nodes (3): _SqliteShim, conn(), raw()

### Community 885 - "Mobile bankroll unit settings"
Cohesion: 0.32
Nodes (7): BankrollSettings, useBankroll(), canStepUnitPct(), sanitizeUnitPct(), stepUnitPct(), store, BANKROLL_DEFAULTS

### Community 9 - "Model training and probability calibration"
Cohesion: 0.02
Nodes (78): _FakeConn, build_bulk_wnba_prop_lookups(), build_wnba_prop_scoring_rows(), build_wnba_prop_training_dataset(), _dispersion(), f(), _calibration_error_weighted(), calibration_metrics() (+70 more)

### Community 90 - "tests/test_f5_any_book_line.py"
Cohesion: 0.08
Nodes (31): _Clf, _GameOddsConn, _fallback_game_line_quote(), _get_scoring_odds(), _has_real_game_price(), _cut(), _mlb_feat(), _on() (+23 more)

### Community 92 - "tests/test_ncaaf_prop_odds.py"
Cohesion: 0.05
Nodes (27): _Conn, _Resp, _market_chunks(), _football_map(), resolver(), scope(), test_a_book_we_did_not_ask_for_is_never_written(), test_a_day_with_no_college_games_spends_nothing() (+19 more)

### Community 93 - "MLB totals public fade tests"
Cohesion: 0.09
Nodes (31): _EmptyConn, find_fade_bets(), under_in_odds_band(), pick_rows(), rows_for_insert(), _dk_board(), _quote(), _quotes() (+23 more)

### Community 94 - "NFL prop backtest verdicts"
Cohesion: 0.04
Nodes (27): TestNormaliseName, TestSnapRows, TestVerdict, TestYesNoMarkets, _verdict(), test_a_half_line_market_priced_to_its_own_skew_is_not_flagged(), test_a_sharp_reference_is_never_a_book_we_bet(), test_a_targeted_backfill_never_substitutes_draftkings() (+19 more)

### Community 95 - "tests/test_ncaaf_pbp_store.py"
Cohesion: 0.09
Nodes (17): _Conn, load_season_from_db(), _report_ranges(), store_season(), _plays(), test_a_rerun_updates_rather_than_duplicating(), test_a_season_in_neither_place_is_an_error_not_a_short_corpus(), test_a_season_survives_the_round_trip_in_the_cfbd_spelling() (+9 more)

### Community 96 - "tests/test_heartbeat_watchdog.py"
Cohesion: 0.07
Nodes (28): _FakeConn, _FakeCursor, _break_db(), sink(), test_a_failed_post_does_not_start_the_throttle(), test_a_healthy_start_never_announces_a_recovery(), test_a_returning_outage_alerts_again_immediately(), test_a_silent_failure_alerter_is_caught_by_the_watchdog() (+20 more)

### Community 97 - "Game injury veto gate and tests"
Cohesion: 0.09
Nodes (31): _InjConn, apply_to_picks(), _goalie_names(), load_sport_injury_index(), _pitcher_names(), player_matches_veto(), relevant_players(), _star_names() (+23 more)

### Community 99 - "Record correction post tests"
Cohesion: 0.06
Nodes (26): Ledger, _Result, _pin(), _real_post(), _real_tweet(), x_posts(), _publish(), test_a_failed_discord_ledger_does_not_send_x() (+18 more)

### Community 516 - "Pipeline run ledger and orphan cleanup"
Cohesion: 0.22
Nodes (8): _abort_orphans(), abort_prior_refresh_orphans(), _boot_cutoff(), _ensure_table(), finish_run(), main(), _now(), start_run()

### Community 100 - "NFL prop information and market tests"
Cohesion: 0.06
Nodes (34): closing_prices(), devig(), ecdf_p_over(), main(), bets(), design(), main(), _bet() (+26 more)

### Community 101 - "NCAAF college data ingestor"
Cohesion: 0.08
Nodes (25): backfill_ncaaf(), backfill_ncaaf_lines(), backfill_ncaaf_players(), backfill_ncaaf_qb(), _existing_ncaaf_ids(), _get(), ingest_ncaaf_game_log(), ingest_ncaaf_games() (+17 more)

### Community 102 - "scripts/nfl_edge_live_rush_pace.py"
Cohesion: 0.18
Nodes (26): _asof(), boot_p(), build_state(), first(), grade(), initial_last(), load_pbp(), main() (+18 more)

### Community 103 - "NBA prop projection tests"
Cohesion: 0.05
Nodes (29): _art(), _proj(), _q(), _run(), _settle(), test_a_book_hanging_two_lines_for_one_player_is_refused(), test_a_decision_with_no_bet_is_still_a_decision(), test_a_past_game_never_projected_gets_the_newest_espn_pull_55_minutes_before_its_tip() (+21 more)

### Community 105 - "NBA game market feature study"
Cohesion: 0.06
Nodes (37): cache_for(), check_cells(), combine_times(), f2_cells(), f2_point(), f6a_placebo(), f6a_point(), f6a_strength() (+29 more)

### Community 107 - "tests/test_prop_calibrated_decision.py"
Cohesion: 0.07
Nodes (28): apply_prop_daily_cap(), dedupe_player_props(), _downgrade(), _bet(), _identity_cal(), _prop(), test_a_genuinely_big_edge_still_fires_after_calibration(), test_a_hot_prop_model_no_longer_fires_the_marginal_bet() (+20 more)

### Community 110 - "tests/test_mobile_line_movement.py"
Cohesion: 0.08
Nodes (27): _fn(), _read(), _run(), test_a_cut_table_keeps_the_pick_and_says_what_it_covers(), test_a_cut_window_keeps_the_pick_row_on_the_8_row_table(), test_a_pick_made_after_the_cards_start_never_reads_since_your_pick(), test_after_the_start_the_verdict_is_not_graded(), test_an_old_snapshot_is_not_the_price_at_the_pick() (+19 more)

### Community 111 - "tests/test_live_calibration.py"
Cohesion: 0.07
Nodes (35): _live_calibration(), pick(), test_a_peak_with_no_plateau_anywhere_is_labelled_as_one(), test_a_prob_cut_and_an_ev_cut_select_different_picks(), test_calibration_also_scores_ev_against_realised_roi(), test_calibration_is_empty_rather_than_wrong_with_nothing_settled(), test_calibration_reports_the_gap_between_claim_and_reality(), test_expected_value_matches_the_hand_calculation() (+27 more)

### Community 112 - "Push deep link and mobile player detail tests"
Cohesion: 0.04
Nodes (54): test_best_odds_never_reaches_the_qualifying_gate(), _read(), test_a_sport_switch_cannot_report_a_game_finishing(), test_all_three_segments_are_unconditional(), test_live_is_not_a_bottom_tab(), test_live_is_not_in_the_tab_param_list(), test_no_app_root_component_reaches_a_focus_aware_hook(), imports_of() (+46 more)

### Community 117 - "NBA lineup stint derivation tests"
Cohesion: 0.08
Nodes (45): order_plays(), _blowout_q4(), derive(), dreb(), _dup_game(), end_period(), five_game(), make2() (+37 more)

### Community 119 - "tests/test_ncaaf_live_notify.py"
Cohesion: 0.06
Nodes (17): _load_write_picks(), _restore_stubbed_modules(), test_a_caller_supplied_connection_is_not_closed_by_the_write(), test_a_failing_notifier_never_breaks_pricing(), test_a_full_slate_announces_once(), test_a_live_bet_notifies_push_and_discord(), test_a_locked_lane_is_not_rewritten(), test_a_locked_lane_keeps_notifying_after_the_engine_stops_betting() (+9 more)

### Community 122 - "Pregame best game price lookup"
Cohesion: 0.11
Nodes (13): _best_game_price_one(), _current_price_since(), _fresh_quotes(), _game_spread_filter_sql(), _latest_book_game_odds(), _newest_book_game_row(), _parse_snapshot(), _pregame_price_floor() (+5 more)

### Community 126 - "monitoring/store.py"
Cohesion: 0.09
Nodes (25): meta(), ops(), snapshot(), api_rollup(), call_timeline(), calls_since(), community(), scalar() (+17 more)

### Community 128 - "tests/test_settled_record_is_immutable.py"
Cohesion: 0.05
Nodes (23): _code(), test_a_dedicated_live_lane_still_counts_and_a_pre_game_in_play_pick_does_not(), test_a_paused_model_is_not_an_excluded_model(), test_a_voided_pick_is_still_out_of_the_record(), test_both_published_views_keep_the_live_date_gate(), test_both_rules_name_the_two_exits_and_not_the_paused_flag(), test_both_views_are_redefined_by_name(), test_every_explicit_exclusion_names_who_asked_for_it() (+15 more)

### Community 130 - "features/golf_feature_engine.py"
Cohesion: 0.08
Nodes (27): assemble_player_features(), _avg_finish(), compute_golf_target(), compute_matchup_target(), _event_finishes(), _f(), _field_features(), _made_cut_rate() (+19 more)

### Community 132 - "ncaaf_live/tests/test_states.py"
Cohesion: 0.13
Nodes (22): build_states(), _platform(), _plays(), _post_convention_game(), _pre_convention_game(), test_a_scoring_plays_state_does_not_contain_its_own_points(), test_ambiguous_convention_refuses_to_build(), test_halftime_scores_carried_for_2h_settlement() (+14 more)

### Community 133 - "tests/test_bovada_feed.py"
Cohesion: 0.11
Nodes (29): _american(), _complete(), _num(), parse_coupon(), _row_for(), _seen_key(), _stamp(), _coupon() (+21 more)

### Community 134 - "tests/test_market_movement.py"
Cohesion: 0.09
Nodes (23): american_to_prob(), build_market_features(), _is_full_game_snap(), _latest_two_sided(), _s(), test_a_game_with_no_decision_book_still_gets_features(), test_a_line_that_genuinely_did_not_move_is_zero_not_none(), test_a_one_way_sharp_quote_yields_nothing() (+15 more)

### Community 136 - "NCAAF cross-book opener artifact tests"
Cohesion: 0.13
Nodes (12): build_artifact(), build_band_artifact(), test_absent_ceiling_means_unbounded(), test_artifact_shape(), test_band_volumes_sum_to_the_single_gate_backtest(), test_both_band_probs_clear_their_configured_floors(), test_each_band_stands_on_its_own_above_the_4pct_bar(), test_flat_prob_clears_the_configured_floor() (+4 more)

### Community 138 - "tests/test_paused_keeps_real_verdict.py"
Cohesion: 0.07
Nodes (33): _bet(), _bodies(), _code(), _fn(), _pause(), _prop(), _rules(), _sql_of() (+25 more)

### Community 139 - "NFL in-play edge season backtests"
Cohesion: 0.05
Nodes (87): s(), books_per_snapshot(), cell(), finalize_states(), fit_models(), h1(), h1_calibration(), h1_frame() (+79 more)

### Community 142 - "tests/test_health_pregame_prices_current.py"
Cohesion: 0.10
Nodes (30): _at(), _game(), _row(), _run(), test_a_broken_feed_read_is_an_error_and_rolls_back(), test_a_broken_query_is_an_error_and_rolls_back(), test_a_cancelled_fight_and_a_pulled_game_do_not_raise_the_alarm(), test_a_dead_feed_with_no_priced_game_is_a_crit() (+22 more)

### Community 144 - "NBA game line move study"
Cohesion: 0.07
Nodes (32): attach(), big_home_dog_signal(), consensus(), control_specs(), coverage_text(), fade_side(), favourite_sides(), first_fetch() (+24 more)

### Community 147 - "scripts/nfl_edge_extreme_props.py"
Cohesion: 0.12
Nodes (29): actuals(), add_modes(), bar(), candidates(), cell(), decision_boards(), devig(), fit_holdout() (+21 more)

### Community 148 - "scripts/nfl_edge_settlement.py"
Cohesion: 0.14
Nodes (30): add_test(), attach(), banner(), bh(), board(), boot_draws(), cell(), choose() (+22 more)

### Community 15 - "X publisher"
Cohesion: 0.03
Nodes (51): test_the_tweet_header_says_restated(), _creds_on(), _fake_conn(), _split(), test_a_429_rate_limit_is_not_reported_as_posted(), test_a_clean_ledger_allows_the_post(), test_a_day_with_nothing_graded_carries_no_clv_line(), test_a_day_with_nothing_risked_states_units_and_does_not_divide() (+43 more)

### Community 153 - "tests/test_agents_contract.py"
Cohesion: 0.05
Nodes (20): _labelled_retired(), test_blocked_items_are_marked_so_the_agent_skips_them(), test_every_backlog_item_is_a_checkbox(), test_neither_agent_may_change_a_model_threshold(), test_the_agents_are_findable_from_the_file_every_session_reads(), test_the_backlog_does_not_promise_an_agent_that_no_longer_runs(), test_the_backlog_exists_and_has_items(), test_the_contract_documents_every_agent_by_name() (+12 more)

### Community 154 - "Historical odds backfill tests"
Cohesion: 0.04
Nodes (33): _ledger_entry_is_resumable(), relabel_in_play(), run_historical_odds_range(), test_a_run_that_writes_nothing_is_not_reported_as_success(), test_the_insert_rolls_back_per_row(), test_capture_compares_the_picks_own_clock_not_the_capture_clock(), test_capture_fails_open_on_a_missing_timestamp(), test_the_dry_run_count_uses_the_same_predicate_as_the_insert() (+25 more)

### Community 157 - "Position vs opponent tests"
Cohesion: 0.07
Nodes (19): _bn_body(), _sql_groups(), test_a_failed_position_read_is_said_not_hidden(), test_a_failed_read_is_not_held_on_the_spinner(), test_every_mlb_stat_chip_has_a_branch(), test_every_nfl_stat_chip_has_a_branch(), test_every_roster_sport_chip_has_a_branch(), test_mlb_lineup_buckets_agree_between_app_and_server() (+11 more)

### Community 159 - "WNBA results ingestor parsers"
Cohesion: 0.06
Nodes (35): _no_minutes(), _played(), build_log_row(), _core_athlete(), _deref(), _et_date(), _fetch_core_box_players(), _fetch_core_games() (+27 more)

### Community 16 - "Daily pipeline runner and push notifier"
Cohesion: 0.02
Nodes (86): ncaaf_season_for_date(), run_ncaaf_stats_ingestor(), run_bullpen_ingestor(), run_player_news_ingestor(), ingest_player_positions(), run_nba_prop_odds_ingestor(), run_wnba_prop_odds_ingestor(), mirror_unchanged() (+78 more)

### Community 160 - "NFL in-play flow validation"
Cohesion: 0.03
Nodes (92): bias_table(), main(), apply_anchor(), best_hit(), _boot_ci(), drop_degenerate(), evaluate(), fit_time_curve() (+84 more)

### Community 161 - "NBA box score enrichment"
Cohesion: 0.06
Nodes (57): _blank(), box_rows(), _check_unmapped(), _create(), dnp_kind(), ensure_tables(), fetch_advanced(), fill_missing_game_logs() (+49 more)

### Community 166 - "Prop box score backfill"
Cohesion: 0.11
Nodes (25): fill_missing(), _call_fill(), _cooled(), _day(), _default_mlb(), _default_nba(), _default_nfl(), _default_nhl() (+17 more)

### Community 167 - "scripts/nfl_preflight.py"
Cohesion: 0.19
Nodes (17): _load_postgres_schema(), check(), check_cards_run(), check_config_gates(), check_cost(), check_data(), data_check(), check_import_shadowing() (+9 more)

### Community 168 - "Push receipt ticket handling tests"
Cohesion: 0.22
Nodes (10): _msgs(), test_a_credentials_failure_disables_nobody(), test_a_request_level_rejection_accepts_nothing(), test_a_retired_device_is_named_for_disabling(), test_a_single_message_reply_may_be_a_bare_object(), test_a_ticket_that_is_not_an_object_is_not_a_delivery(), test_an_error_ticket_is_not_counted_as_sent(), test_an_unpairable_reply_counts_nothing_and_disables_nothing() (+2 more)

### Community 169 - "NCAAF board visibility tests"
Cohesion: 0.10
Nodes (10): _days_until(), test_a_declined_rule_can_never_leak_a_signal(), test_a_no_signal_row_does_not_lock_an_ncaaf_game_for_the_week(), test_days_until_is_none_without_a_kickoff_time(), test_days_until_is_positive_for_a_future_kickoff(), test_every_registered_model_has_a_feature_map_entry(), test_the_premium_tier_shares_the_spread_features(), test_the_price_prefilter_can_only_ever_skip_ncaaf() (+2 more)

### Community 171 - "NFL stake sizing and EV engine"
Cohesion: 0.09
Nodes (23): american_to_decimal(), cover_probs(), ev_per_unit(), fit_margin_pmf(), kelly_fraction(), margin_pmf_for(), add_model_mu(), load() (+15 more)

### Community 172 - "nfl/live_model/tests/test_flow.py"
Cohesion: 0.09
Nodes (18): evaluate(), _infer_position(), main(), _pool_prior(), report(), _rows_for_market(), _to_states(), accrual_at() (+10 more)

### Community 173 - "tests/test_decide_on_calibrated.py"
Cohesion: 0.06
Nodes (19): _pick(), _pick_at(), test_a_calibrated_cut_is_paired_with_a_calibrated_decision(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(), test_a_genuinely_big_edge_still_fires_after_calibration(), test_a_hot_model_no_longer_fires_the_marginal_bet(), test_a_model_on_a_calibrated_cut_is_not_paused(), test_a_paused_model_never_fires_regardless() (+11 more)

### Community 176 - "NBA prop projection lab"
Cohesion: 0.10
Nodes (44): bars(), bh_read(), blind(), boot(), by(), cal_ab(), candidates(), card_bets() (+36 more)

### Community 178 - "NFL edge versus luck gap study"
Cohesion: 0.10
Nodes (30): add_windows(), add_windows_fast(), bh(), binom_p(), board(), boot(), cell(), fit_points() (+22 more)

### Community 181 - "tests/test_nfl_rule_2026_track.py"
Cohesion: 0.11
Nodes (19): grade_rows(), lead_days(), opener_verdict(), units_from_profit_flat(), _row(), _src(), test_a_wind_lock_past_four_days_is_flagged_not_resized(), test_config_comments_state_the_policy() (+11 more)

### Community 182 - "tests/test_model_artifacts_load.py"
Cohesion: 0.07
Nodes (19): _git(), _gitignore_keep_pkls(), _ignored(), _manifest_keep_pkls(), _newest_per_model(), test_a_path_that_is_not_ignored_is_not_reported(), test_a_superseded_timestamped_pkl_is_ignored(), test_an_ignored_path_comes_back_byte_identical() (+11 more)

### Community 185 - "scripts/game_line_market_sweep.py"
Cohesion: 0.07
Nodes (21): _by_month(), collect_picks(), devig(), grade(), implied(), iter_months(), load(), load_chunked() (+13 more)

### Community 187 - "Push notification deep link tests"
Cohesion: 0.08
Nodes (23): _code(), _py_version(), _read(), test_a_single_pick_deep_links_and_a_batch_does_not(), test_an_unreadable_payload_routes_nowhere_rather_than_guessing(), test_both_halves_pin_the_same_payload_version(), test_every_expo_message_carries_a_data_payload(), test_every_summary_producer_can_deep_link_a_single_pick() (+15 more)

### Community 188 - "tests/test_pass_instrumentation.py"
Cohesion: 0.06
Nodes (11): test_a_dead_database_does_not_fail_the_step(), test_a_raised_failure_still_records_the_exception(), test_a_step_that_raises_is_still_TIMED(), test_a_step_that_raises_still_raises(), boom(), test_a_step_that_returns_false_records_a_REASON(), test_a_successful_step_records_a_duration(), test_every_step_name_in_the_dispatch_table_is_reachable() (+3 more)

### Community 190 - "tests/test_db_adapt_sql.py"
Cohesion: 0.09
Nodes (23): _adapt_sql(), _convert_params(), _convert_params_outside_literals(), _named(), test_a_block_comment_is_skipped_too(), test_a_colon_word_inside_a_comment_is_not_a_placeholder(), test_a_dash_dash_inside_a_literal_is_data_not_a_comment(), test_a_line_comment_ends_at_the_newline() (+15 more)

### Community 191 - "NHL totals market model"
Cohesion: 0.11
Nodes (17): _coherent(), _fetch_ts(), find_bets(), load_fetch_quotes(), _ts(), _two_way(), _q(), test_a_different_number_is_not_the_same_bet() (+9 more)

### Community 193 - "tests/test_first_signal_repair.py"
Cohesion: 0.13
Nodes (22): step_restore_first_signals(), patch_conn(), _sql_of(), test_a_lane_already_holding_its_first_bet_is_untouched(), test_a_lane_with_no_sibling_still_restores(), test_a_lane_with_nothing_standing_is_restored(), test_a_pregame_model_is_not_marked_live(), test_a_price_move_alone_is_a_different_bet() (+14 more)

### Community 195 - "tests/test_mobile_contrast_tokens.py"
Cohesion: 0.13
Nodes (29): _code_lines(), _ionicon_colors(), _lum(), _over(), _ratio(), _read(), _rgb(), test_badge_glyph_tracks_dynamic_type() (+21 more)

### Community 201 - "NBA second game line move tests"
Cohesion: 0.06
Nodes (39): _priced_season(), _q(), _sched(), _season_games(), _signal(), _split(), _stub_main(), test_a_fetch_after_T_never_reaches_the_move() (+31 more)

### Community 206 - "tests/test_live_inning_gate_replay.py"
Cohesion: 0.12
Nodes (28): _grade(), _pair(), _refuse_tables(), _score_seen_at(), _game(), _price(), _scored(), _sig() (+20 more)

### Community 208 - "NBA play-by-play game matching tests"
Cohesion: 0.05
Nodes (33): drop_duplicate_box_ids(), _last(), match_games(), match_names(), our_ids(), resolve_map(), _g(), _game_recs() (+25 more)

### Community 21 - "NFL halftime and prop wind edge studies"
Cohesion: 0.04
Nodes (60): backfill_cost(), bets(), bh(), clean_2h(), fmt(), forward_2026(), hdr(), _line_models() (+52 more)

### Community 216 - "Free pick cheaper book tests"
Cohesion: 0.08
Nodes (19): _pick(), test_a_pick_with_no_alternative_falls_back_to_draftkings(), test_every_offerable_book_has_a_human_name_on_both_surfaces(), test_the_free_card_names_the_cheaper_book(), test_the_free_card_query_reads_the_columns_it_renders(), test_the_good_to_clause_is_dropped_not_truncated_when_it_will_not_fit(), test_the_tweet_names_the_cheaper_book(), test_the_tweet_never_publishes_a_worse_price_than_draftkings() (+11 more)

### Community 218 - "Closing line value math"
Cohesion: 0.04
Nodes (38): implied(), _identity_maps(), _platform_gates_off(), test_breakeven_is_the_real_vig_hurdle(), test_a_one_way_close_is_not_de_vigged(), test_a_worse_close_is_negative_and_equal_prices_are_zero(), test_devigging_the_taken_price_is_not_what_primary_does(), test_kalshi_close_is_not_de_vigged() (+30 more)

### Community 219 - "tests/test_nfl_live_leader_state.py"
Cohesion: 0.14
Nodes (19): situation(), status(), test_a_conversion_try_is_skipped(), test_a_previous_quarters_play_is_not_the_state(), test_a_timeout_is_skipped_for_the_play_before_it(), test_after_a_scoring_play_nothing_is_evaluated(), test_after_the_kickoff_lands_the_receiver_has_the_ball(), test_an_ordinary_snap_is_evaluable_with_the_training_inputs() (+11 more)

### Community 221 - "tests/test_ncaaf_qb_ingestor.py"
Cohesion: 0.12
Nodes (23): _athlete_stats(), _comp_att(), parse_qb_game_stats(), _split_ratio(), _parse(), _payload(), _team(), test_athlete_stats_helper_is_category_scoped() (+15 more)

### Community 222 - "NHL derivative totals card"
Cohesion: 0.40
Nodes (3): main(), run(), test_card_writes_nothing_and_the_pipeline_does_not_call_it()

### Community 224 - "NBA derivative market lab"
Cohesion: 0.09
Nodes (35): add_team(), am_to_dec(), bars_for(), bet_list(), blind(), boot_ci(), build_line_rows(), build_outcomes() (+27 more)

### Community 229 - "NBA prop model verification script"
Cohesion: 0.12
Nodes (29): adv_from_log(), asof_roster(), blind_structured(), card_block(), collapse_report(), _compare(), log(), main() (+21 more)

### Community 232 - "Mobile pick category tests"
Cohesion: 0.13
Nodes (12): _block(), _config_scorable_ids(), _meta_ids(), _meta_types(), _read(), test_every_model_id_derives_its_own_declared_category(), test_every_scorable_model_has_a_label_in_the_app(), test_picks_idle_chrome_is_search_and_filters_only() (+4 more)

### Community 235 - "NCAAF feature engine tests"
Cohesion: 0.09
Nodes (22): build_bulk_ncaaf_lookups(), shrink_hfa(), _assemble(), _stats(), test_assembly_diffs_and_context(), test_backtester_and_scorer_dispatch_ncaaf_explicitly(), test_backtester_feature_vector_exempts_sparse_columns(), test_bulk_asof_never_reads_a_future_snapshot() (+14 more)

### Community 237 - "MLB first pitch time trust"
Cohesion: 0.05
Nodes (23): trusted_first_pitch(), _mark_in_play(), test_a_late_start_is_believed_because_it_is_real(), test_a_missing_actual_start_falls_back_to_the_schedule(), test_an_implausibly_early_first_pitch_is_not_believed(), test_both_missing_still_fails_open(), test_every_is_pregame_snapshot_caller_passes_first_pitch(), test_it_never_overwrites_commence_time() (+15 more)

### Community 240 - "tests/test_ncaaf_game_identity.py"
Cohesion: 0.12
Nodes (16): _add(), _conn(), _identity_sql(), _run(), test_a_clean_slate_reports_nothing(), test_a_non_fbs_fixture_is_not_reported(), test_a_phantom_opponent_is_detected_too(), test_a_real_doubleheader_is_not_a_duplicate() (+8 more)

### Community 241 - "NBA second game market tests"
Cohesion: 0.10
Nodes (27): _close_frames(), _data(), _f2_games(), _f6a_data(), _f6d_total_data(), _game(), _pe(), _q() (+19 more)

### Community 242 - "data/ingestors/ncaaf_inplay_history.py"
Cohesion: 0.16
Nodes (17): _blank_row(), budget_for(), calls_in(), _floor5(), _get(), _iso(), main(), parse_shard() (+9 more)

### Community 243 - "MLB and WNBA stats ingestors and pitcher rebuild"
Cohesion: 0.04
Nodes (42): setup_database(), backfill_bullpen_stats(), backfill_f5_scores(), backfill_mlb_stats(), backfill_pitcher_stats(), backfill_player_game_log(), backfill_player_handedness(), _build_pitcher_rows() (+34 more)

### Community 250 - "data/ingestors/nhl_boxscore.py"
Cohesion: 0.12
Nodes (16): _decision(), fill_missing(), _insert_absent(), _int(), _name(), parse_boxscore(), side_rows(), store_boxscore() (+8 more)

### Community 255 - "scripts/mlb_total_public_fade_topk.py"
Cohesion: 0.12
Nodes (17): american_units(), bucket_win_rates(), build_candidates(), _fmt(), grade_under(), holdout_take(), load_db(), load_json() (+9 more)

### Community 258 - "NFL wind cards and kickoff weather"
Cohesion: 0.13
Nodes (13): coverage_check(), expected_true_wind(), open_air_mask(), wind_at_kickoff(), load_nfl_model(), cached_totals(), issued_wind(), load_week() (+5 more)

### Community 259 - "NFL teaser leg study"
Cohesion: 0.17
Nodes (21): boot_ci(), be(), bettable_board(), bettable_legs(), era_grid(), era_slice(), ev_k(), ev_row() (+13 more)

### Community 260 - "tests/test_live_game_features.py"
Cohesion: 0.11
Nodes (19): compute_live_target(), half_innings_left(), parse_bases(), state_features(), test_build_live_state_row_merges_pregame_context(), test_build_live_state_row_unusable_state(), test_half_innings_left_bottom_ninth(), test_half_innings_left_extras_clamps_to_one() (+11 more)

### Community 261 - "tests/test_ncaaf_totals_regression.py"
Cohesion: 0.10
Nodes (14): total_over_prob(), test_artifact_kind_is_routed_by_the_scorer(), test_asymmetry_is_real_and_would_have_bitten(), test_extremes_are_clamped_away_from_certainty(), test_model_above_the_line_favours_the_over(), test_model_below_the_line_favours_the_under(), test_no_dk_total_means_skip_not_prob_only(), test_no_residuals_returns_one_half_not_a_confident_bet() (+6 more)

### Community 262 - "UFC feature engine and tests"
Cohesion: 0.13
Nodes (21): _age_years(), _assemble_ufc_features(), career_stats(), compute_ufc_target(), _fight_minutes(), infer_five_rounds(), synthetic_round_total(), _fight() (+13 more)

### Community 263 - "Mobile verify scripts run from pytest"
Cohesion: 0.03
Nodes (59): node_exe(), node_strips_types(), tsx_cmd(), test_today_et_ignores_the_container_timezone(), _node_strips_types(), _read(), _run(), test_audited_targets() (+51 more)

### Community 266 - "NCAAF in-play history backtest"
Cohesion: 0.09
Nodes (17): build_candidates(), decide(), first_signals(), _fmt(), grade(), load_snapshots(), odds_from_rows(), report() (+9 more)

### Community 267 - "tests/test_ncaaf_qb_features.py"
Cohesion: 0.13
Nodes (23): build_qb_team_features(), merge_qb_features(), _feat(), _frame(), _games(), _qb_rows(), _qb_team(), test_a_games_features_never_use_that_game() (+15 more)

### Community 271 - "Line CLV sign and orientation tests"
Cohesion: 0.07
Nodes (7): _load(), test_a_line_that_held_is_exactly_zero_not_none(), test_a_missing_close_is_not_a_zero(), test_a_side_that_cannot_be_oriented_returns_none_rather_than_guessing(), test_the_home_and_away_sides_are_exact_mirrors(), test_the_prop_market_flag_wins_over_the_market_string(), test_the_signs_are_the_negation_of_the_apps_entry_frame()

### Community 272 - "tests/test_mobile_team_detail.py"
Cohesion: 0.11
Nodes (15): _read(), test_every_team_page_read_names_its_relation_literally(), test_next_game_is_earliest_in_the_window_not_tonights_date(), test_no_paper_trading_copy(), test_public_betting_policy_migration_exists_and_is_select_only(), test_recent_games_are_scoped_by_sport(), test_results_are_units_never_dollars(), test_sharp_gap_is_no_vig_vs_no_vig() (+7 more)

### Community 275 - "NBA game harness tests"
Cohesion: 0.08
Nodes (26): _cov_data(), _fetches(), _games(), _offers(), _q(), _stale_cache(), test_a_graded_load_refuses_a_season_the_cache_does_not_price(), test_a_graded_load_refuses_rows_that_match_no_purchase() (+18 more)

### Community 276 - "NBA ESPN box score parsing"
Cohesion: 0.11
Nodes (14): box_team_totals(), parse_nba_box(), parse_nba_scoreboard(), _team_blocks(), board(), _board(), _summary(), test_stats_are_read_by_label_and_a_dnp_is_omitted() (+6 more)

### Community 283 - "NCAAF play-by-play state builder"
Cohesion: 0.16
Nodes (11): main(), _classify(), classify_report(), _detect_score_convention(), load_pbp(), load_platform_games(), pace_report(), _repair_day_offsets() (+3 more)

### Community 285 - "Health skip budget tests"
Cohesion: 0.10
Nodes (13): test_a_stuck_gate_is_not_reported_as_stale_data(), _res(), _source_outside_the_budget_table(), test_a_non_skipped_result_is_never_touched(), test_a_stuck_gate_escalates_past_its_budget(), test_an_honest_offseason_skip_stays_skipped_but_shows_its_length(), test_applying_twice_does_not_double_annotate(), test_every_budgeted_check_is_a_real_check_name() (+5 more)

### Community 286 - "Kalshi ladder recorder tests"
Cohesion: 0.10
Nodes (5): test_a_kalshi_outage_cannot_break_the_pass(), test_a_run_is_idempotent_within_its_snapshot(), test_one_snapshot_timestamp_for_the_whole_run(), test_the_recorder_is_scheduled_on_the_pipeline_role(), test_the_recorder_keeps_raw_prices_not_a_filtered_ladder()

### Community 287 - "Calibration check and stake tests"
Cohesion: 0.05
Nodes (21): games(), first_bets(), main(), test_favourites_risk_more_until_the_cap_binds(), test_risk_is_capped_at_three_units_and_the_payout_is_recomputed(), test_the_risk_cap_can_no_longer_bind(), test_underdogs_risk_less_than_their_conviction(), test_no_pending_view_migration_re_creates_these_views_over_the_log() (+13 more)

### Community 289 - "tests/test_ncaaf_player_stats_ingestor.py"
Cohesion: 0.18
Nodes (17): parse_player_game_stats(), _cat(), _parse(), _payload(), _team(), test_a_game_missing_from_the_id_map_is_skipped_not_guessed(), test_a_player_gets_one_row_across_every_category(), test_a_player_with_nothing_we_track_is_skipped() (+9 more)

### Community 290 - "NBA second game model verdict"
Cohesion: 0.11
Nodes (22): axes_of(), bar9(), cell_key(), _floats(), load_cells(), main(), plateau_ok(), verdict() (+14 more)

### Community 293 - "Market coverage probe tests"
Cohesion: 0.07
Nodes (17): candidate_markets(), _standard_markets(), test_a_two_sided_market_is_never_reported_one_sided(), test_an_all_line_leg_slip_does_not_claim_a_model(), test_it_asks_about_the_board_columns_that_are_permanently_blank(), test_it_reports_supported_but_empty_apart_from_unsupported(), test_no_market_is_asked_about_twice(), test_one_market_per_call_so_a_rejected_key_is_identified_exactly() (+9 more)

### Community 296 - "scripts/nfl_edge_kalshi.py"
Cohesion: 0.17
Nodes (20): align_check(), bh(), bins(), boot(), cell(), coverage(), cp_roi(), fee() (+12 more)

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
Nodes (12): test_a_retired_game_model_is_in_no_feature_map(), test_a_retired_model_is_in_no_registry_and_no_threshold_dict(), test_a_retired_prop_has_no_feature_map_and_no_training_label(), test_a_retired_sport_is_not_still_health_checked(), test_paused_nfl_props_still_in_prop_models_and_thresholds(), test_retired_prop_picks_still_settle_on_their_own_stat(), test_ten_nfl_distributional_props_are_paused(), test_the_app_mirrors_the_same_set() (+4 more)

### Community 306 - "NBA schedule features"
Cohesion: 0.12
Nodes (10): _counted_schedule(), from_cache(), game_schedule_features(), haversine_miles(), home_bases(), _offsets(), previous_game_load(), team_schedule_features() (+2 more)

### Community 307 - "Pregame line poller change tests"
Cohesion: 0.05
Nodes (32): changed_rows(), over_credit_cap(), _row(), _run_scorer_body(), test_a_failed_tick_does_not_kill_the_loop(), test_a_failed_tick_throws_the_map_away(), test_a_full_board_call_still_passes_no_subset(), test_a_link_or_selection_id_churning_is_not_a_change() (+24 more)

### Community 317 - "Latest line state and Citadel migration cluster tests"
Cohesion: 0.04
Nodes (52): main(), can_scratch(), env_dsn(), _free_port(), pg_bin(), scratch_cluster(), as_app(), db() (+44 more)

### Community 318 - "tests/test_live_record_start_views.py"
Cohesion: 0.09
Nodes (12): _body(), _code(), test_both_published_views_carry_the_live_date_gate(), test_it_runs_after_the_migration_that_used_to_own_the_daily_view(), test_migration_is_one_statement(), test_migration_is_registered_with_the_worker_runner(), test_neither_view_reads_the_sweep_universe(), test_no_ddl_outside_the_guarded_branches() (+4 more)

### Community 319 - "tests/test_model_quality.py"
Cohesion: 0.10
Nodes (9): _bet(), test_high_public_pct_on_a_fade_publisher_counts_as_a_fade(), test_low_public_pct_on_the_pick_side_counts_as_a_fade(), test_majority_share_warns_when_not_unanimous(), test_meta_steps_exclude_model_quality(), test_pipeline_step_never_fails_on_crit(), test_pipeline_step_never_fails_on_exception(), test_side_aliases_collapse_to_the_same_direction() (+1 more)

### Community 326 - "tests/test_api_call_rollup.py"
Cohesion: 0.09
Nodes (10): test_a_fold_can_never_lower_a_stored_total(), test_a_new_process_does_not_prune_on_its_first_flush(), test_prune_rolls_up_before_it_deletes(), test_the_daily_table_is_created_and_locked_down(), test_the_daily_table_keys_on_day_api_and_source(), test_the_rollup_groups_by_eastern_day_not_utc(), test_the_rollup_reads_only_yesterday_and_today(), test_the_rollup_survives_a_failure_without_blocking_the_prune() (+2 more)

### Community 328 - "NFL weather edge study"
Cohesion: 0.14
Nodes (18): audit(), baseline(), bh(), boot(), classify(), era(), grade(), load() (+10 more)

### Community 329 - "nfl/models/opener_spread.py"
Cohesion: 0.14
Nodes (11): age_tag(), american_to_prob(), _bettable_books(), clean_board(), edge_tier(), evaluate_board(), held_minutes(), model_prob_for_dev() (+3 more)

### Community 331 - "NHL prop backtest namesake handling"
Cohesion: 0.13
Nodes (16): claimed_vs_realised(), day_interval(), line(), namesakes(), prices(), report(), show(), build() (+8 more)

### Community 332 - "tests/test_live_slate_midnight.py"
Cohesion: 0.10
Nodes (10): _at(), test_both_live_loops_share_one_definition_of_the_slate(), test_by_daytime_yesterday_is_dropped(), test_just_after_midnight_still_asks_about_yesterday(), test_just_before_midnight_asks_about_today_only(), test_the_apps_live_hook_resolves_the_window_per_fetch(), test_the_apps_live_reads_take_a_LIST_of_dates(), test_the_ncaaf_live_loop_got_the_same_fix() (+2 more)

### Community 333 - "tests/test_nfl_wind_fire_window.py"
Cohesion: 0.07
Nodes (18): _retractable_slate(), _slate(), test_a_blank_roof_at_a_NON_retractable_venue_is_unaffected(), test_a_closed_roof_is_still_indoor(), test_a_retractable_venue_with_an_unknown_roof_does_not_fire(), test_a_waiting_game_is_not_reported_as_a_collapsed_premise(), test_a_waiting_row_keeps_its_line_price_and_edge(), test_every_blank_roof_row_is_a_retractable_venue() (+10 more)

### Community 334 - "College football data parsers"
Cohesion: 0.08
Nodes (23): _int(), _num(), parse_advanced_stats(), parse_ratings(), parse_returning(), parse_season_stats(), parse_talent(), parse_team_game_stats() (+15 more)

### Community 335 - "tests/test_public_betting_ingestor.py"
Cohesion: 0.17
Nodes (17): parse_public_betting(), _pct(), _select_book(), _make_game(), test_parse_emits_six_rows(), test_parse_game_id_and_sides(), test_parse_marks_source_and_snapshot(), test_parse_missing_teams_returns_empty() (+9 more)

### Community 339 - "tests/test_service_role_split.py"
Cohesion: 0.15
Nodes (11): _all_job_ids(), _sched(), test_an_unknown_role_runs_everything(), test_every_add_job_call_passes_an_id(), test_every_job_is_owned_by_exactly_one_role(), test_the_always_on_jobs_run_on_every_role(), test_the_default_preserves_the_single_container(), test_the_nfl_worker_stays_with_the_volume() (+3 more)

### Community 343 - "tests/test_http_timeout_floor.py"
Cohesion: 0.11
Nodes (11): install_timeout_floor(), _call(), clean_requests(), test_a_call_with_no_timeout_gets_one(), test_an_explicit_timeout_is_never_overridden(), test_installing_twice_is_a_no_op(), test_the_deadline_is_env_overridable(), test_the_deadline_survives_telemetry_being_turned_off() (+3 more)

### Community 345 - "Line churn measurement and verdict"
Cohesion: 0.21
Nodes (12): churn_table(), verdict(), _snaps(), test_a_line_moving_every_interval_reads_as_under_sampled(), test_a_missing_key_column_fails_loudly_rather_than_grouping_coarser(), test_a_single_snapshot_contributes_no_interval(), test_a_still_line_reads_as_still(), test_markets_are_not_pooled() (+4 more)

### Community 346 - "scripts/nfl_edge_cache.py"
Cohesion: 0.22
Nodes (14): _conn(), copy_main_local(), _df(), _games_2026(), log(), main(), nflverse_misc(), nflverse_pbp() (+6 more)

### Community 347 - "Paused model assessment tests"
Cohesion: 0.11
Nodes (12): assess(), _half(), fetch(), grade(), sweep(), _units(), _rows(), test_a_cell_below_the_floor_is_not_a_result() (+4 more)

### Community 352 - "NHL prop odds alternate line tests"
Cohesion: 0.07
Nodes (22): due(), _book(), test_a_200_on_both_calls_merges_the_alternate_lines(), fake_fetch(), test_a_game_first_priced_inside_the_final_window_gets_nothing_more(), test_a_game_first_priced_inside_the_window_gets_one_decision_snapshot(), test_a_game_with_nothing_stored_is_owed_its_open(), test_a_moved_featured_line_keeps_the_old_number_under_the_alternate_key() (+14 more)

### Community 355 - "NFL in-play pick writer"
Cohesion: 0.12
Nodes (8): _is_market_opinion(), _lane_is_locked(), _norm_player(), resolve_game(), resolve_game_id(), test_normalised_player_key_is_the_join_the_prop_system_uses(), test_the_lane_lock_shares_the_scorers_meaning_of_locked(), test_the_lock_is_scoped_by_player_not_just_by_game()

### Community 357 - "Injury fetch speed and cache tests"
Cohesion: 0.07
Nodes (11): _athlete_name(), _clear_cache(), test_a_dead_database_leaves_the_cache_empty_not_broken(), test_a_failed_lookup_is_not_cached(), test_a_known_athlete_costs_no_request(), test_a_SUCCESSFUL_response_with_no_name_is_not_cached(), test_an_unknown_athlete_is_fetched_and_then_remembered(), test_one_team_failing_does_not_lose_the_others() (+3 more)

### Community 359 - "Published record and stake tests"
Cohesion: 0.11
Nodes (13): test_persist_creates_its_own_table_and_is_idempotent(), db(), db(), conn(), conn(), _code(), _marked(), test_the_app_record_leaves_an_unpublished_graded_bet_out() (+5 more)

### Community 36 - "tests/test_cfbd_ingestor.py"
Cohesion: 0.03
Nodes (54): _day_before(), eastern_game_date(), _local_aggregates(), parse_games(), parse_lines(), retain_existing_cfbd_ids(), shrink_to_prior(), _stat_row() (+46 more)

### Community 361 - "tests/test_config.py"
Cohesion: 0.08
Nodes (8): test_an_own_floor_does_not_take_a_model_off_the_calibration_map(), test_every_model_carries_its_own_thresholds(), test_every_own_floor_names_a_live_model(), test_models_on_own_probability_is_not_derived_from_the_floor_dict(), test_no_own_floor_tightens_a_model_past_the_global_floor(), test_only_a_market_priced_model_carries_a_negative_floor(), test_own_ev_floor_and_model_min_ev_stay_disjoint(), test_the_models_the_global_floor_silently_removed_can_bet_again()

### Community 366 - "Kalshi game market recorder"
Cohesion: 0.09
Nodes (8): run_kalshi_game_record(), test_a_kalshi_outage_cannot_break_the_pass(), test_event_code_is_shared_across_series(), test_event_date_is_searched_not_anchored(), test_kalshi_labels_expand_st_and_use_the_explicit_map(), test_resolution_runs_after_every_snapshot(), test_the_recorder_is_scheduled_on_the_pipeline_role(), test_the_recorder_keeps_raw_contracts()

### Community 367 - "Database URL doctor tests"
Cohesion: 0.07
Nodes (30): _classes(), diagnose(), bad(), _safe(), main(), database_url(), _default_env_path(), env_value() (+22 more)

### Community 368 - "tests/test_mlb_pbp_ingestor.py"
Cohesion: 0.16
Nodes (15): _bases_after_from_matchup(), parse_game_plays(), parse_play(), _split_event_type(), test_bases_empty_matchup(), test_bases_with_runners(), test_parse_game_plays_empty_feed(), test_parse_game_plays_walks_full_inning() (+7 more)

### Community 369 - "UFC fighter name resolution"
Cohesion: 0.16
Nodes (11): resolve_slug(), _slug_tokens(), test_a_generational_suffix_resolves_either_way(), test_a_near_miss_is_not_a_match(), test_a_reversed_name_order_resolves(), test_a_shared_surname_alone_is_not_a_match(), test_an_ambiguous_token_set_resolves_to_nothing(), test_an_empty_or_tokenless_name_is_safe() (+3 more)

### Community 370 - "UFC fight history loader"
Cohesion: 0.16
Nodes (14): _aggregate_stats(), build_events(), build_fighter_index(), _kd_int(), _scheduled_rounds(), _split_bout(), _fixture(), test_build_events_draw_and_nc() (+6 more)

### Community 371 - "tests/test_team_stats_asof_invariants.py"
Cohesion: 0.08
Nodes (14): impossible_games_played(), _played_actual(), test_a_missing_count_is_reported_not_silently_passed(), test_an_honest_row_passes(), test_claiming_fewer_games_than_played_is_fine(), test_feb_gp_climbing_vs_zero_regular_season_still_fails(), test_mlb_twin_codes_do_not_false_crit(), test_mlb_twin_reverse_lookup_also_resolves() (+6 more)

### Community 373 - "MLB run line retrain and sweep job"
Cohesion: 0.10
Nodes (8): test_the_raised_timeout_is_restored_after_the_job(), test_the_restore_puts_back_a_pre_existing_value(), test_marker_file_is_in_tree_so_the_freeze_would_not_block_the_worker(), test_missing_artifact_path_refuses_to_sweep_live(), test_retrain_then_sweep_passes_the_new_path(), test_the_runner_retrains_then_sweeps_the_new_artifact(), _job_mlb_runline_retrain_sweep(), _job_retrain_model()

### Community 375 - "Refresh pass step ordering tests"
Cohesion: 0.10
Nodes (13): _order(), test_a_parallel_step_that_fails_is_still_recorded(), test_no_sequential_step_runs_while_a_parallel_group_is_open(), test_opening_signals_follows_every_scorer(), test_parlay_follows_opening_signals(), test_scoring_follows_every_ingest(), test_settle_follows_every_results_ingest(), test_sync_thresholds_follows_migrations_and_precedes_scoring() (+5 more)

### Community 376 - "CFBD verification script"
Cohesion: 0.17
Nodes (9): parse_teams(), _check(), _lines_coverage(), main(), _null_report(), _sample_keys(), test_parse_teams_all_schools_pull_never_defaults_to_fbs(), test_parse_teams_joins_alt_names() (+1 more)

### Community 379 - "NBA historical odds archive parser"
Cohesion: 0.15
Nodes (18): classify(), _fold(), _is_half(), _num(), parse_season(), _price(), team(), _page() (+10 more)

### Community 38 - "Sharp book odds retention in pruning"
Cohesion: 0.11
Nodes (12): _prop_reference_books(), protected_for(), _unprotected(), test_the_bookmaker_these_rows_use_survives_the_daily_prune(), test_a_shopping_book_is_still_prunable(), test_every_prop_reference_book_is_protected(), test_every_sharp_book_is_protected_in_the_prop_table(), test_pinnacle_specifically_is_protected_in_the_prop_table() (+4 more)

### Community 382 - "UFC event stats ingestor"
Cohesion: 0.09
Nodes (19): backfill_ufc_stats(), _build_ufc_game_id(), _fetch_event(), _fetch_event_list(), _fetch_fight(), _fetch_fighter(), _get(), _home_win_for_row() (+11 more)

### Community 383 - "Mobile tracked performance checks"
Cohesion: 0.10
Nodes (18): dup, empty, half, l50, loss, noAction, open1, open2 (+10 more)

### Community 384 - "tests/test_mobile_threshold_parity.py"
Cohesion: 0.16
Nodes (12): _block(), _canonical(), _mirror(), _mirror_paused(), _src(), test_every_cut_matches_config(), test_every_scorable_model_is_in_the_app_mirror(), test_the_app_mirror_holds_no_model_config_cannot_score() (+4 more)

### Community 385 - "NFL live prop assessment script"
Cohesion: 0.19
Nodes (14): _connect(), american_b(), boot_ci(), build(), cluster_se_mean(), implied(), load(), main() (+6 more)

### Community 386 - "tests/test_nhl_derivative_odds_job.py"
Cohesion: 0.12
Nodes (9): test_a_credit_ceiling_is_a_malformed_request(), test_apply_argv_is_only_apply(), test_apply_is_explicit_and_carries_no_ceiling(), test_dry_run_argv_has_no_apply_and_no_ceiling(), capture(), test_empty_args_are_a_dry_run(), test_probe_argv_does_not_apply(), _job_nhl_derivative_odds_history() (+1 more)

### Community 388 - "tests/test_track_record_views.py"
Cohesion: 0.11
Nodes (10): _body(), _code(), test_migration_is_one_statement(), test_migration_is_registered_with_the_worker_runner(), test_no_ddl_outside_the_guarded_branches(), test_refresh_pass_refreshes_outcomes_after_settle(), test_the_daily_view_is_no_longer_redefined_here(), test_the_full_outcome_view_reads_the_matview_and_never_the_player_logs() (+2 more)

### Community 389 - "tests/test_weekly_catch_up.py"
Cohesion: 0.12
Nodes (10): sched(), test_a_fresh_savant_does_not_suppress_the_calibration_catch_up(), test_a_missing_sweeps_table_counts_as_stale(), test_a_recent_sweep_does_not(), test_an_old_sweep_triggers_the_catch_up(), test_model_calibration_belongs_to_the_pipeline_service(), test_the_catch_up_creates_the_review_tables_on_boot(), test_the_review_schema_is_not_gated_by_owns() (+2 more)

### Community 392 - "tests/test_live_game_state_poller.py"
Cohesion: 0.17
Nodes (16): _detect_triggers(), _is_active_or_starting_soon(), test_active_in_progress_game_is_active(), test_combined_changes_fire_all_relevant_triggers(), test_due_up_change_fires_due_up_change(), test_final_game_is_not_active(), test_identical_state_fires_no_triggers(), test_inning_half_change_fires_inning_change() (+8 more)

### Community 394 - "NCAAF live ESPN feed parser"
Cohesion: 0.17
Nodes (16): check_feed_assumptions(), _competitors(), _count_plays(), _dig(), extract_live_events(), extract_summary_state(), _int(), _num() (+8 more)

### Community 396 - "Fast live odds path tests"
Cohesion: 0.09
Nodes (11): test_a_quote_already_seen_does_not_count_as_a_move(), test_a_scoring_failure_never_kills_the_feed(), test_poll_once_reports_which_games_moved(), test_scoring_is_opt_in(), test_scoring_runs_in_the_same_tick_as_the_write(), test_the_budget_is_written_down_where_it_can_be_checked(), test_the_expected_consequence_is_stated(), test_the_loop_sleeps_the_REMAINDER_of_the_interval() (+3 more)

### Community 398 - "CLV card price taken tests"
Cohesion: 0.13
Nodes (18): _app(), _clv_card(), _node_strips_types(), _server(), test_a_label_book_nfl_pick_compares_its_line_with_that_book(), test_a_recorded_book_differs_from_the_derived_one(), test_the_app_prefers_the_recorded_book_at_the_derived_price(), test_the_app_prices_every_row_as_the_server_grades_it() (+10 more)

### Community 399 - "NFL live leader model tests"
Cohesion: 0.10
Nodes (17): wp_design(), wp_lookup(), art(), _d(), _raw(), test_600_seconds_and_both_lead_ends_are_inside(), test_a_flipped_spread_sign_changes_the_decision(), test_a_qualifying_state_bets_the_leader_at_its_price() (+9 more)

### Community 40 - "NFL wind edge studies"
Cohesion: 0.10
Nodes (42): band_table(), bh(), build_priced(), decisions_2026(), decisions_hist(), era5_hourly(), fc_at_decision(), fetch_2026() (+34 more)

### Community 400 - "Mobile paused catalog tests"
Cohesion: 0.18
Nodes (10): _block(), _read(), test_paused_picks_reach_the_all_board_only_and_labelled(), test_stats_add_pick_refuses_a_paused_model(), test_the_bet_type_picker_filters_paused_models(), test_the_custom_model_picker_is_three_bet_types(), test_the_models_list_filters_paused_models(), test_the_pause_source_is_isModelPaused_not_a_hand_copied_set() (+2 more)

### Community 401 - "NFL live prop rule studies"
Cohesion: 0.19
Nodes (11): american_b(), boot_roi(), first_per_player(), grade(), load(), main(), report(), main() (+3 more)

### Community 402 - "tests/test_mobile_player_stat_groups.py"
Cohesion: 0.15
Nodes (10): _set_literal(), _src(), test_a_group_is_filled_only_by_a_real_number(), test_a_tab_opens_on_the_stat_the_player_fills_most(), test_defensive_positions_get_only_the_defense_group(), test_every_logged_position_is_classified(), test_non_defensive_positions_get_no_defense_group(), test_offensive_positions_are_not_defensive() (+2 more)

### Community 403 - "Mobile sport filter tests"
Cohesion: 0.14
Nodes (10): _load_body(), _sports(), _src(), test_a_visit_scoped_sport_change_does_not_persist(), test_a_writer_landing_during_the_hydrate_is_not_overwritten(), test_every_sport_survives_a_cold_start(), test_no_retired_sport_is_a_selectable_chip(), test_no_second_hand_written_sport_list_in_the_hook() (+2 more)

### Community 404 - "tests/test_promote_calibration_job.py"
Cohesion: 0.11
Nodes (3): test_a_refused_model_rolls_back_and_raises(), test_a_successful_promote_commits(), _job_promote_calibration()

### Community 406 - "tests/test_cfbd_snapshot_leakage.py"
Cohesion: 0.16
Nodes (9): _completed_before(), _ohio_state_2024(), test_boundary_is_strict(), test_datetime_like_values_are_handled(), test_empty_input(), test_end_of_regular_season_snapshot_excludes_playoffs(), test_missing_or_malformed_dates_are_dropped_not_admitted(), test_postseason_excluded_from_early_season_snapshot() (+1 more)

### Community 411 - "Intraday data freshness tests"
Cohesion: 0.14
Nodes (10): _is_fresh(), _minutes_since(), _age(), test_an_unknown_age_refetches_rather_than_skipping(), test_fresh_data_is_skipped(), test_stale_data_is_refetched(), test_the_6am_pipeline_is_never_throttled(), test_the_boundary_refetches() (+2 more)

### Community 413 - "tests/test_nfl_prop_thresholds.py"
Cohesion: 0.11
Nodes (8): test_live_webhook_map_reads_the_per_sport_env_vars(), cfg(), test_no_nfl_prop_market_is_back_on_the_uniform_placeholder(), test_one_bad_date_does_not_cost_the_others(), test_the_prop_window_has_exactly_one_declaration(), test_the_scorer_step_covers_the_whole_window_not_one_date(), fake(), test_the_three_threshold_dicts_agree_for_every_nfl_prop_market()

### Community 414 - "tests/test_nhl_research_job.py"
Cohesion: 0.15
Nodes (11): test_a_dump_argument_is_refused(), test_a_model_must_be_a_real_spec(), test_a_season_must_be_a_priced_one(), test_an_unknown_script_is_refused(), test_an_unknown_top_level_key_is_refused(), test_every_runnable_module_has_a_main(), test_every_runnable_module_writes_no_database_row(), test_the_artifact_grade_names_the_rule_production_runs() (+3 more)

### Community 415 - "tests/test_settlement_timing.py"
Cohesion: 0.14
Nodes (9): test_capture_clv_requires_the_game_to_have_started(), test_future_kickoffs_are_not_treated_as_started(), test_game_log_skips_per_game_not_per_date(), test_mirror_unchanged_is_conservative_when_it_cannot_tell(), test_started_games_are_recognised_in_every_stored_format(), test_ufc_poll_uses_the_etag_gate_and_the_daily_run_does_not(), test_unparseable_timestamps_yield_none_rather_than_a_guess(), test_z_and_offset_forms_are_the_same_instant_but_not_the_same_string() (+1 more)

### Community 417 - "Model quality and CLV checks"
Cohesion: 0.12
Nodes (12): record_exclusion_sql(), test_clv_clear_negative_vs_baseline_is_flagged(), test_raw_one_sided_clv_is_ignored(), test_the_exclusion_sql_is_a_conjunction_of_negations(), _job_model_quality(), detect_clv_degradation(), _group(), _result_row() (+4 more)

### Community 418 - "NFL injury ingest from ESPN tests"
Cohesion: 0.11
Nodes (9): _fetch_nfl_espn_team_ids_core(), _nfl_espn_team_to_abbrev(), _fake_fetch(), test_core_nfl_listing_failure_returns_empty(), test_core_nfl_team_ids_resolve_lar_and_wsh_to_ours(), test_injury_fetch_raises_the_page_limit(), test_nfl_active_rows_are_dropped_and_out_keeps_espn_date(), test_nfl_name_join_uses_our_abbrevs_not_espns() (+1 more)

### Community 42 - "DataGolf ingestor and NHL SBR archive"
Cohesion: 0.05
Nodes (45): _american(), backfill_golf_rounds(), build_game_id(), _dg_get(), _earliest_commence_iso(), _event_meta_lookup(), event_slug(), ingest_golf_field() (+37 more)

### Community 421 - "Paused and no-signal pick rows"
Cohesion: 0.14
Nodes (11): _apply_no_signal(), _game_pick(), _prop_pick(), test_auto_paused_counts_as_paused(), test_no_signal_rows_persist_the_reason(), test_paused_game_model_avoid_stays_avoid_with_reason(), test_paused_game_model_bet_stays_bet_with_reason_and_stake(), test_paused_prop_model_avoid_stays_avoid_with_reason() (+3 more)

### Community 425 - "NFL odds cache import to Supabase"
Cohesion: 0.12
Nodes (9): _allowed(), _data_dirs(), test_a_rerun_after_the_resolver_improves_adds_only_the_gap(), test_every_buying_ingestor_keys_its_resume_on_a_source_marker(), test_no_undeclared_data_store_on_disk(), test_the_importer_resolves_a_postponed_game(), test_the_importer_still_refuses_an_event_with_no_game(), test_the_nfl_odds_cache_has_an_importer() (+1 more)

### Community 426 - "tests/test_health_check_observe.py"
Cohesion: 0.14
Nodes (10): _crit(), fake(), test_a_crit_does_not_fail_the_observe_path(), test_a_crit_still_fails_the_daily_step(), test_an_exception_does_not_fail_the_observe_path(), test_daily_syncs_thresholds_after_view_migrations(), test_it_still_runs_the_check_when_observing(), test_ok_is_identity_in_both_modes() (+2 more)

### Community 429 - "NCAAF school name slugs"
Cohesion: 0.14
Nodes (8): _loose_orientation(), ncaaf_slug(), _slug_extends(), _slug_pair(), test_an_fcs_name_that_extends_an_fbs_school_passes_through_unresolved(), test_slug(), test_split_ratio(), test_with_the_visitor_in_the_registry_it_resolves_to_itself()

### Community 430 - "Health check deliverability tests"
Cohesion: 0.11
Nodes (12): test_a_game_date_inside_the_window_counts(), test_a_lookahead_commence_counts_even_when_game_date_is_outside(), test_a_signal_locked_after_first_pitch_was_never_deliverable(), test_a_signal_locked_before_first_pitch_still_counts(), test_a_signal_locked_exactly_at_first_pitch_counts(), test_a_started_game_outside_the_window_does_not_count(), test_it_fails_toward_noticing(), test_mixed_timestamp_shapes_are_parsed_not_string_compared() (+4 more)

### Community 431 - "tests/test_pick_lock_is_on_picks.py"
Cohesion: 0.16
Nodes (9): _between(), _sql(), test_a_bet_is_still_never_re_scored(), test_only_a_bet_locks_a_pair(), test_the_cleanup_covers_the_whole_look_ahead_window(), test_the_cleanup_never_touches_a_started_game_or_a_live_row(), test_the_lock_is_no_longer_ncaaf_specific(), test_the_prop_and_live_locks_are_unchanged() (+1 more)

### Community 434 - "NCAAF opener rule scoring tests"
Cohesion: 0.17
Nodes (12): _opener_rule(), _line(), _patch(), test_a_fired_pick_clears_its_own_probability_floor(), test_books_agreeing_is_a_no_signal_row(), test_dk_off_its_opener_is_a_no_signal_row(), test_missing_sharp_opener_is_a_no_signal_row(), test_no_current_dk_line_writes_nothing() (+4 more)

### Community 439 - "tests/test_team_stats_asof_invariants.py"
Cohesion: 0.14
Nodes (11): build_rows(), _game(), test_a_row_never_includes_its_own_date(), test_counts_accumulate_across_dates(), test_every_emitted_column_exists_in_the_real_table(), columns_of(), test_every_sport_uses_its_own_scoring_noun(), test_home_and_away_splits_use_only_the_relevant_games() (+3 more)

### Community 44 - "scripts: build_nfl_live_leader_artifact + model"
Cohesion: 0.09
Nodes (26): wp_design(), wp_lookup(), attach_games(), build_artifact(), check_possession(), _dk_pregame_spread(), _download(), _first_bets() (+18 more)

### Community 440 - "NCAAF outcome edge scan"
Cohesion: 0.19
Nodes (12): _cell(), ecdf_prob_positive(), implied(), load_ml_prices(), main(), payout(), predict_all(), _print_cells() (+4 more)

### Community 443 - "tests/test_opp_starter_features.py"
Cohesion: 0.16
Nodes (10): _opp_starter_savant(), _batter_bulk(), test_batter_bulk_carries_everything_opp_starter_savant_reads(), test_it_reads_the_starters_savant_row(), test_live_mode_falls_back_to_prior_season(), test_live_mode_prefers_the_current_season(), test_opp_starter_savant_reads_real_values_off_the_real_loader(), test_starter_gb_pct_still_works_off_the_same_query() (+2 more)

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
Cohesion: 0.13
Nodes (7): _generic(), test_a_generic_model_is_never_declared_rule_or_engine(), test_accessor_defaults_to_artifact(), test_every_classified_model_carries_thresholds(), test_mlb_live_total_runs_is_artifact_backed(), test_rule_based_models_never_appear_in_a_feature_map(), test_the_map_covers_exactly_the_non_generic_models()

### Community 456 - "MLB prop market sweep research"
Cohesion: 0.13
Nodes (9): actuals(), grade_day(), main(), norm(), outs_from_ip(), profit(), MLB prop market-relative rule (not wired), mlb_spread_market 1.8pp run-line rule (+1 more)

### Community 458 - "Live monitor dashboard cache and docs"
Cohesion: 0.13
Nodes (10): age(), cached(), clear(), test_cache_raises_when_it_has_nothing_to_fall_back_on(), test_cache_reports_age(), test_cache_serves_stale_rather_than_failing(), boom(), test_cache_serves_within_ttl_and_recomputes_after() (+2 more)

### Community 46 - "Worker job queue runner"
Cohesion: 0.03
Nodes (34): derive_first_pitch(), test_the_worker_job_is_registered_and_defaults_to_dry_run(), test_the_discord_publish_job_calls_the_ordinary_producer(), test_the_discord_publish_job_takes_an_optional_date(), _announce(), _execute(), _job_derive_first_pitch(), _job_game_log_backfill() (+26 more)

### Community 460 - "Results recap backfill to X"
Cohesion: 0.09
Nodes (16): build_parser(), _date_is_over(), main(), post_backfill(), test_a_day_that_is_not_over_is_refused(), test_apply_calls_both_notifiers_for_that_date(), test_dry_run_is_the_default_and_posts_nothing(), test_main_dry_run_prints_and_returns() (+8 more)

### Community 462 - "Anonymous read access audit"
Cohesion: 0.07
Nodes (13): test_a_writable_relation_that_is_not_readable_is_still_swept(), test_every_declared_write_verb_has_a_call_site_that_needs_it(), test_public_is_stripped_from_every_declared_callable_before_it_is_granted(), test_subscriptions_stays_authenticated_only(), test_the_apply_script_reads_back_that_rls_actually_landed(), test_the_apply_script_revokes_writes_and_reads_the_result_back(), test_the_archive_tables_have_no_create_site_and_the_worker_only_ones_do(), test_the_default_privilege_revoke_names_the_api_roles_only() (+5 more)

### Community 463 - "NCAAF totals weather and margin evaluation"
Cohesion: 0.17
Nodes (11): _fit(), fit_and_register_totals(), _matrix(), sweep_total(), walk_forward_totals(), arm_frame(), load_issued(), main() (+3 more)

### Community 464 - "NCAAF game day polling cadence tests"
Cohesion: 0.12
Nodes (6): gameday_mod(), test_credit_cap_covers_a_full_saturday_at_the_configured_cadence(), test_idle_cadence_is_slower_than_the_live_cadence(), test_kickoffs_already_past_are_not_counted_as_upcoming(), test_state_cadence_is_fast_enough_to_react_to_a_drive(), test_the_effective_odds_cadence_is_bounded_by_the_pass()

### Community 465 - "nfl/scripts/backtest_opener.py"
Cohesion: 0.24
Nodes (9): boot(), by_season(), exp_win(), load(), main(), price(), report(), residuals() (+1 more)

### Community 467 - "MLB retrain freeze tests"
Cohesion: 0.13
Nodes (9): assert_retrain_allowed(), test_import_time_flag_follows_marker_file(), test_marker_or_env_lifts_the_freeze(), test_mlb_prop_market_sweep_is_documented_exempt(), test_mlb_retrain_refused_while_incomplete(), test_mlb_threshold_sweeps_call_the_guard(), test_non_mlb_sports_are_not_gated(), test_repo_marker_file_is_present() (+1 more)

### Community 468 - "tests/test_latest_odds_views.py"
Cohesion: 0.31
Nodes (12): _app_columns(), _function(), test_every_log_table_has_its_insert_trigger_and_the_odds_tables_an_update_trigger(), test_every_view_reads_its_state_table_and_never_the_log(), test_the_dk_view_returns_the_apps_columns_in_order(), test_the_exclusions_survived_the_move(), test_the_game_view_returns_the_apps_columns_in_order(), test_the_live_view_returns_the_apps_columns_in_order() (+4 more)

### Community 472 - "NBA schedule ingestor and tests"
Cohesion: 0.20
Nodes (11): ot_periods(), schedule_rows(), season_str(), _tv(), _row(), test_a_late_west_coast_tip_keeps_its_eastern_date(), test_an_undecided_playoff_slot_is_skipped(), test_game_type_is_read_from_the_first_three_digits() (+3 more)

### Community 473 - "tests/test_nfl_prop_settle_name_fallback.py"
Cohesion: 0.27
Nodes (10): _never(), _row(), test_a_first_name_the_stat_log_spells_differently_still_matches(), test_a_scratched_player_is_not_graded_on_a_teammate_with_his_initial(), test_a_spelling_the_log_already_knows_is_a_scratch_not_a_spelling(), test_another_game_and_another_initial_never_match(), test_first_name_rule(), test_two_candidates_is_a_miss_not_a_guess() (+2 more)

### Community 474 - "NFL recap waits for box scores tests"
Cohesion: 0.08
Nodes (12): test_a_malformed_date_is_refused_before_anything_runs(), test_the_job_does_not_bypass_the_day_is_over_guard(), test_the_job_does_not_read_rowcount_off_the_cursor(), test_the_job_only_clears_its_own_ledger_kind(), _daily(), _job_body(), test_a_malformed_date_is_refused_before_anything_runs(), test_nfl_box_scores_are_ingested_before_settle() (+4 more)

### Community 476 - "tests/test_transaction_pooler.py"
Cohesion: 0.19
Nodes (8): _transaction_endpoint(), test_a_direct_connection_is_left_alone(), test_a_local_postgres_is_left_alone(), test_a_supabase_session_url_becomes_the_transaction_url(), test_it_is_idempotent(), test_only_the_port_changes(), test_the_escape_hatch_works(), test_the_job_queue_still_gets_session_mode()

### Community 477 - "NBA historical odds archive parsing"
Cohesion: 0.13
Nodes (14): _gid(), iso_z(), match(), odds_rows(), snapshot_times(), _swap(), _g(), test_a_labelled_pair_is_never_swapped() (+6 more)

### Community 480 - "Team stats as-of invariant tests"
Cohesion: 0.16
Nodes (8): seasons_with_too_few_snapshots(), test_a_real_series_passes(), test_a_single_snapshot_season_is_flagged(), test_a_two_snapshot_season_is_flagged(), test_mlb_twin_alias_map_matches_sbr_canon(), test_ncaaf_shaped_weekly_snapshots_pass(), test_the_guard_is_wired_so_protected_seasons_are_REMOVED(), test_the_guard_uses_the_same_threshold_as_the_invariant()

### Community 483 - "NBA injury report slot dates"
Cohesion: 0.16
Nodes (10): _ampm(), new_slot(), old_slot(), pre_tip_slot(), slots_for_date(), test_format_switch_is_measured_and_both_are_probed_around_it(), test_hourly_dates_get_sixteen_hourly_slots(), test_pre_tip_slot_is_strictly_before_the_tip() (+2 more)

### Community 484 - "Mobile bankroll settings card"
Cohesion: 0.20
Nodes (19): fieldFlow(), inv(), bankrollDraft(), bankrollFieldText(), canonical(), checkBankroll(), commitBankrollText(), editBankrollInput() (+11 more)

### Community 487 - "supabase/functions/sharpsports/index.ts"
Cohesion: 0.30
Nodes (13): americanFromBetSlip(), asArray(), createContext(), isSettled(), json(), pick(), pullAndUpsert(), readBets() (+5 more)

### Community 489 - "NCAAF in-play underdog correction fit"
Cohesion: 0.18
Nodes (11): brier(), conditional_table(), fit_logistic(), load(), logit(), logloss(), main(), design() (+3 more)

### Community 490 - "WNBA prop market card"
Cohesion: 0.23
Nodes (6): main(), player_ids(), publish(), render(), run_card(), slate()

### Community 491 - "NFL model imports under scheduler"
Cohesion: 0.15
Nodes (6): _import_under_scheduler_env(), _scheduler_env(), test_no_nfl_script_uses_the_bare_models_import(), test_the_card_imports_under_the_schedulers_invocation(), test_the_exemption_is_the_loader_and_it_still_exists(), test_the_loader_reaches_nfls_models_not_the_platforms()

### Community 493 - "Watchdogs and calibration monitors"
Cohesion: 0.03
Nodes (43): main(), build_opener_cache(), coverage_report(), fetch_season(), _headers(), main(), _norm(), to_frame() (+35 more)

### Community 495 - "tests/test_worker_deps.py"
Cohesion: 0.22
Nodes (4): _requirements(), test_dashboard_packages_are_not_on_the_worker(), test_only_the_dashboard_imports_them(), test_the_worker_asks_for_the_cpu_build_of_xgboost()

### Community 499 - "Minimum odds price floor tests"
Cohesion: 0.10
Nodes (16): min_odds_for(), _blocked_by_min_odds(), _apply_price_floor(), test_a_pick_with_no_price_is_never_blocked_by_the_floor(), test_an_explicit_floor_wins_in_BOTH_directions(), test_every_registered_model_has_an_effective_floor(), test_ordinary_prices_still_fire(), test_the_offending_pick_would_now_be_blocked() (+8 more)

### Community 50 - "scheduler.py"
Cohesion: 0.05
Nodes (49): _run_migrations(), abort_orphaned_refresh_runs(), build_scheduler(), _add_job(), _with_heartbeat(), _wrapped(), catch_up_daily_pipeline(), catch_up_refresh_pass() (+41 more)

### Community 502 - "NFL stale card file tests"
Cohesion: 0.15
Nodes (9): card_path(), clear_card(), _load_script(), nfl_path(), test_a_dry_run_leaves_the_card_alone(), test_a_priced_wind_run_with_no_bets_removes_the_earlier_card(), test_clear_card_removes_todays_file_and_only_that(), test_the_path_cleared_is_the_path_the_publisher_reads() (+1 more)

### Community 503 - "NCAAF steam lag study"
Cohesion: 0.27
Nodes (9): attach_scores(), build_events(), fmt(), grade(), lines_at_pulls(), load(), main(), summarise() (+1 more)

### Community 504 - "Published record reconciliation tests"
Cohesion: 0.16
Nodes (8): test_a_pick_before_the_live_date_is_caught_in_either_view(), test_a_sport_missing_from_the_daily_view_is_caught(), test_an_empty_record_is_not_a_problem(), test_cent_level_agreement_is_required(), test_same_picks_but_different_money_is_caught(), test_the_fixed_production_numbers_reconcile(), test_the_real_production_drift_is_caught(), _published_record_problems()

### Community 505 - "tests/test_mobile_stat_labels_match_the_server.py"
Cohesion: 0.21
Nodes (6): _meta_entries(), _server_stat_labels(), test_both_rushing_models_call_the_stat_the_same_thing(), test_the_live_model_names_the_market_it_actually_trades(), test_the_parser_actually_found_the_models(), test_the_unreconciled_models_are_named()

### Community 506 - "tests/test_ncaaf_fcs_visitor_names_migration.py"
Cohesion: 0.15
Nodes (5): _rows(), test_each_write_guards_on_its_own_property(), test_every_real_visitor_extends_the_wrong_one(), test_migration_is_one_statement(), test_the_nine_rows_and_their_finals_are_the_measured_ones()

### Community 507 - "tests/test_nfl_prop_unstarted_clear.py"
Cohesion: 0.25
Nodes (8): _apply(), _assert_split(), _between(), _first_sql(), _per_game_sql(), _sweep_sql(), test_per_game_clear_keeps_nfl_prop_rows_on_a_game_the_loop_reaches(), test_sweep_keeps_unstarted_nfl_prop_nones_and_still_clears_game_nones()

### Community 508 - "NBA game lab and NFL edge hunts"
Cohesion: 0.04
Nodes (89): bh_fdr(), binom_p(), eval_rule(), load(), main(), devig_power(), games(), main() (+81 more)

### Community 51 - "NFL live moneyline and total pricing tests"
Cohesion: 0.05
Nodes (48): align_states(), build_team_map(), _game_index(), kill_verdict(), load_cached_snapshots(), main(), _model_price(), replay() (+40 more)

### Community 510 - "Trainer no-register tests"
Cohesion: 0.12
Nodes (9): not_registering(), registering(), test_a_normal_run_DOES_register(), test_baseline_artifacts_are_not_committable(), test_baseline_runs_write_somewhere_else(), test_default_is_to_register(), test_no_register_opens_no_database_connection(), _explode() (+1 more)

### Community 512 - "tests/test_savant_freshness.py"
Cohesion: 0.14
Nodes (5): test_rows_are_stamped_with_a_capture_date(), test_savant_has_a_schedule(), test_the_insert_persists_the_stamp(), test_the_savant_job_belongs_to_the_pipeline_service(), test_the_stamp_defaults_rather_than_being_required_at_call_sites()

### Community 513 - "tests/test_scorer_nfl_prop_like_escape.py"
Cohesion: 0.23
Nodes (9): _between(), _broken_per_game_sql(), _first_sql(), _per_game_sql(), _sweep_sql(), test_escape_tripwire_is_on_the_pr_ci_subset(), test_live_per_game_clear_interpolates_with_one_game_id(), test_live_sweep_clear_interpolates_with_date_horizon_now() (+1 more)

### Community 520 - "App read access lockdown"
Cohesion: 0.15
Nodes (9): all_readable(), lock_down_sql(), _app_relations(), test_every_relation_the_app_reads_is_declared(), test_everything_declared_writable_is_also_readable_or_deliberately_not(), test_lock_down_sql_refuses_anything_that_is_not_a_plain_identifier(), test_lock_down_sql_refuses_every_table_the_app_reads(), test_the_manifest_does_not_grow_stale_entries() (+1 more)

### Community 522 - "Source code static guard tests"
Cohesion: 0.07
Nodes (19): _is_main_guard(), _modules_with_guard(), test_at_least_one_entrypoint_is_scanned(), test_nothing_is_defined_after_the_main_guard(), _fn(), test_a_missing_bet_book_close_is_not_filled_from_another_book(), test_backfill_revisits_anything_that_is_not_standard_v2(), test_capture_grades_raw_same_book_and_a_separate_pinnacle_edge() (+11 more)

### Community 524 - "Odds pruning keeps openers tests"
Cohesion: 0.11
Nodes (8): test_both_delete_tiers_exclude_openers(), test_cfbd_archive_prefix_is_protected(), test_historical_backfill_rows_are_protected_in_odds(), test_line_shop_books_are_not_protected_wholesale(), test_openers_subquery_exists_and_orders_ascending(), test_prop_table_has_no_source_column_so_no_source_clause(), test_tier2_still_prunes_intermediate_snapshots(), test_unprotected_predicate_covers_every_prefix()

### Community 525 - "Slate concentration and fade risk checks"
Cohesion: 0.16
Nodes (12): _fade_slate(), test_a_mixed_slate_is_ok(), test_all_home_ncaaf_slate_is_flagged_without_mlb_hardcoding(), test_all_unders_public_fade_risk_is_crit(), test_all_unders_public_fade_slate_is_crit(), test_fade_in_the_model_id_is_sport_agnostic(), test_thin_slate_is_not_a_finding(), test_unanimous_but_small_slate_is_warn_not_crit() (+4 more)

### Community 527 - "Kalshi prop market ingest"
Cohesion: 0.15
Nodes (9): _event_date(), _player(), test_a_ticker_with_no_event_code_returns_none_not_a_wrong_date(), test_a_title_without_a_player_returns_none(), test_an_impossible_date_is_rejected(), test_only_per_game_player_series_are_mapped(), test_the_event_date_is_searched_not_anchored(), test_the_mapped_series_are_exactly_the_probed_per_game_player_board() (+1 more)

### Community 529 - "tests/test_clear_unauthorized_auto_pauses_migration.py"
Cohesion: 0.19
Nodes (6): _stmts(), test_clearing_auto_pauses_did_not_park_batter_runs(), test_it_clears_the_whole_auto_pause_table(), test_it_does_not_touch_picks_thresholds_or_the_review_ledger(), test_it_no_ops_when_the_table_is_missing_or_already_empty(), test_migration_is_one_statement()

### Community 53 - "Declared worker job validation tests"
Cohesion: 0.15
Nodes (7): _declared(), test_an_explicit_run_date_must_be_a_real_iso_date(), test_declared_keys_are_unique(), test_every_declared_job_names_a_registered_type(), test_every_declared_job_validates(), test_no_run_date_means_the_module_resolves_it(), test_the_validator_drops_unknown_args()

### Community 530 - "tests/test_ncaaf_se_louisiana_alias_migration.py"
Cohesion: 0.15
Nodes (4): test_a_pick_is_never_deleted_and_never_regraded(), test_it_guards_on_both_names_and_both_still_unscored(), test_migration_is_one_statement(), test_odds_move_only_when_canonical_has_none()

### Community 532 - "tests/test_overnight_polling.py"
Cohesion: 0.24
Nodes (7): _hours(), _jobs(), _match(), test_every_hour_of_the_day_is_covered(), test_the_overnight_pass_is_the_ordinary_one(), test_the_overnight_window_exists(), test_the_windows_do_not_overlap()

### Community 535 - "tests/test_revoke_remaining_grants.py"
Cohesion: 0.15
Nodes (6): test_it_asserts_the_app_write_surface_survives(), test_it_revokes_every_write_privilege(), test_select_is_never_revoked(), test_the_roles_are_named_never_public(), test_the_runners_transaction_stripping_leaves_the_do_block_intact(), test_the_set_is_computed_from_the_policy_rule_not_listed()

### Community 537 - "tests/test_live_slate_midnight.py"
Cohesion: 0.18
Nodes (7): _discover_active_games(), _game_id_from_statsapi(), test_a_game_seen_twice_is_polled_once(), test_discovery_asks_statsapi_about_every_date_it_is_given(), fake_schedule(), test_discovery_still_accepts_a_bare_string(), test_one_broken_date_does_not_lose_the_other()

### Community 538 - "tests/test_nhl_stats_ingestor.py"
Cohesion: 0.38
Nodes (9): parse_nhl_game(), _g(), test_arizona_folds_into_utah(), test_missing_teams_returns_none(), test_ot_home_win_is_regulation_draw(), test_preseason_game_skipped(), test_regulation_home_win(), test_scheduled_game_has_no_scores() (+1 more)

### Community 542 - "NCAAF situational spot search"
Cohesion: 0.18
Nodes (7): is_bowl_game(), build_spots(), evaluate(), load_team_games(), main(), wilson(), test_is_bowl_game()

### Community 544 - "NCAAF starting quarterback absence study"
Cohesion: 0.27
Nodes (8): build_sample(), grade(), _line(), load_qb_log(), main(), report(), starter_status(), wilson()

### Community 546 - "tests/test_claude_rules_split.py"
Cohesion: 0.18
Nodes (4): test_claude_md_still_points_at_the_rules_directory(), test_every_rule_file_actually_carries_rules(), test_every_rule_file_is_path_scoped(), test_no_rule_was_lost_when_the_split_happened()

### Community 547 - "tests/test_db_setup.py"
Cohesion: 0.23
Nodes (6): _get_columns(), test_games_table_columns(), test_injuries_table_columns(), test_odds_table_columns(), test_picks_table_columns(), test_schema_is_idempotent()

### Community 548 - "tests/test_dedupe_opening_signals.py"
Cohesion: 0.10
Nodes (9): test_a_graded_row_is_never_deleted(), test_a_row_with_computed_clv_is_never_deleted(), test_every_field_that_defines_the_bet_must_agree(), test_it_is_dry_run_by_default(), test_the_delete_selects_through_the_same_gates(), test_the_pair_must_be_an_old_shape_new_shape_pair(), test_the_report_and_the_delete_share_one_definition(), test_the_row_kept_is_the_one_locked_earlier() (+1 more)

### Community 549 - "NCAAF totals lead timing study"
Cohesion: 0.26
Nodes (10): build_lead_table(), first_cross(), fmt(), grade(), line_as_of(), load_backfill(), main(), match_frame_to_odds() (+2 more)

### Community 550 - "tests/test_every_named_book_is_fetched.py"
Cohesion: 0.18
Nodes (5): _param_books(), test_a_sharp_reference_is_never_also_a_soft_book(), test_every_bettable_book_can_be_named_to_a_human(), test_every_named_book_is_in_the_pull_that_serves_it(), test_the_nfl_backfill_defaults_to_the_live_pull()

### Community 552 - "tests/test_pbp_backfill_resilience.py"
Cohesion: 0.24
Nodes (6): _backfill_body(), test_a_failed_game_rolls_the_connection_back(), test_a_run_that_wrote_nothing_reports_an_error_not_a_success(), test_errors_are_counted_not_just_logged(), test_partial_failures_are_surfaced_too(), test_the_rollback_cannot_itself_raise()

### Community 562 - "MLB backfill retry tests"
Cohesion: 0.12
Nodes (6): test_a_failed_date_does_not_end_the_run_and_is_left_unmarked(), test_a_transient_network_error_is_retried(), test_an_http_error_is_NOT_retried(), test_it_gives_up_rather_than_looping_forever(), test_skip_existing_is_on_by_default(), test_the_resume_marker_distinguishes_historical_from_live_rows()

### Community 563 - "NFL prop universe model rate summary"
Cohesion: 0.29
Nodes (6): _universe_summary(), test_a_universe_without_the_model_sums_still_summarises(), test_mean_projection_and_mean_actual_separate_mean_bias_from_shape_bias(), test_model_over_rate_and_its_gap_are_reported(), _universe(), test_a_nonfinite_fair_price_cannot_switch_the_gate_off()

### Community 566 - "Mobile bankroll copy and behaviour tests"
Cohesion: 0.23
Nodes (13): _read(), test_copy_is_word_for_word(), test_display_only_nothing_sized(), test_error_text_uses_the_text_safe_red(), test_explainer_no_longer_denies_a_bankroll(), test_exposure_card_hook_and_banner_stay_removed(), test_keyboard_never_covers_the_field(), test_locale_separators_decide_the_decimal() (+5 more)

### Community 568 - "Anonymous read grants application"
Cohesion: 0.18
Nodes (7): write_verbs_for(), _function_plan(), _function_signature(), main(), _table_exists(), test_write_verbs_for_keeps_exactly_what_a_writable_relation_declares(), test_write_verbs_for_revokes_everything_on_a_read_only_relation()

### Community 569 - "tests/test_game_log_backfill_skip.py"
Cohesion: 0.25
Nodes (5): _backfill_body(), test_a_game_absent_from_our_games_table_is_still_skipped(), test_no_skip_is_keyed_on_date_alone(), test_the_coverage_set_is_scoped_to_the_season_being_built(), test_the_skip_is_keyed_on_game_id()

### Community 572 - "NCAAF line move spots"
Cohesion: 0.27
Nodes (6): eval_follow_spread(), eval_follow_total(), load(), main(), _summ(), wilson()

### Community 573 - "NBA luck study and feature frames"
Cohesion: 0.04
Nodes (57): coerce_numeric_features(), feature_matrix(), test_a_push_settles_to_nan_not_to_a_loss(), test_a_team_total_without_a_resolved_team_is_not_adjudicated(), load_games(), main(), pivot_spreads(), pivot_totals() (+49 more)

### Community 574 - "tests/test_prompt_reads_thresholds.py"
Cohesion: 0.18
Nodes (4): test_the_auto_pause_lookup_fails_open(), test_the_prompt_carries_no_per_model_cut(), test_the_prompt_still_says_it_is_pasted_once(), test_the_sync_mirrors_both_pause_registers()

### Community 575 - "tests/test_system_health_meta_steps.py"
Cohesion: 0.25
Nodes (5): _meta_steps(), test_aborted_sentinel_is_excluded(), test_health_check_is_excluded(), test_model_quality_is_excluded(), test_sentinel_matches_the_writer()

### Community 577 - "NBA period scores ingestor and tests"
Cohesion: 0.32
Nodes (8): _int(), parse_period_rows(), _event(), test_espn_team_codes_map_to_ours(), test_one_row_per_period_under_our_game_id(), test_overtime_periods_follow_the_fourth(), test_quarters_that_do_not_sum_to_the_final_are_skipped(), test_unfinished_games_and_mismatched_period_counts_are_skipped()

### Community 580 - "scripts/render_brand_icons.py"
Cohesion: 0.24
Nodes (3): draw_mark(), main(), render()

### Community 581 - "NHL blocked shots backtest"
Cohesion: 0.21
Nodes (8): p_over(), bets(), card(), line(), main(), prices(), show(), decide()

### Community 584 - "Dashboard rule model tests"
Cohesion: 0.14
Nodes (5): test_a_rule_carries_a_cut_but_is_in_no_training_registry(), test_a_rule_is_not_styled_as_a_warning(), test_a_rule_sorts_with_the_live_models_not_the_broken_ones(), test_the_roster_query_flags_rules(), test_the_summary_counts_rules_apart_from_outages()

### Community 586 - "supabase/functions/stripe-webhook/index.ts"
Cohesion: 0.31
Nodes (9): applySubscription(), iso(), resolveUserId(), stripeGet(), timingSafeEqual(), toHex(), verifySignature(), admin (+1 more)

### Community 589 - "tests/test_mobile_neutral_signal_label.py"
Cohesion: 0.31
Nodes (7): _read(), test_explainer_names_neutral(), test_filters_and_card_speak_the_display_name(), test_model_screens_speak_the_display_name(), test_no_member_label_prints_a_raw_signal_type(), test_none_badge_reads_neutral(), test_withdrawn_pick_is_not_badged_neutral()

### Community 590 - "NFL wind stake sizing tests"
Cohesion: 0.22
Nodes (6): _probe(), test_an_uncalibrated_lead_is_sized_rather_than_zeroed_on_the_card(), test_at_the_default_gate_that_same_row_does_not_fire_at_all(), test_the_eval_board_agrees_with_the_card(), test_the_probability_was_already_clipping(), test_the_stake_clips_to_lead_seven_instead_of_returning_zero()

### Community 593 - "tests/test_scorer_commits_per_game.py"
Cohesion: 0.40
Nodes (8): _between(), _run_scorer_body(), test_a_lost_connection_re_runs_the_game_once_and_never_the_pass(), test_each_game_is_its_own_committed_unit(), test_no_bulk_delete_of_non_bet_rows_precedes_the_loop(), test_picks_are_only_counted_once_the_game_committed(), test_the_housekeeping_delete_is_a_sweep_after_the_loop(), test_the_outer_handler_still_records_the_failure()

### Community 594 - "NCAAF in-play underdog calibration tables"
Cohesion: 0.17
Nodes (9): bucket(), label(), main(), table(), wilson(), test_projecting_runs_after_the_decisions_are_published(), test_the_tick_passes_a_days_that_covers_the_whole_window(), test_the_tick_returns_free_outside_the_window() (+1 more)

### Community 596 - "NCAAF structure scan"
Cohesion: 0.21
Nodes (3): load_data(), main(), scan_spot()

### Community 598 - "tests/test_live_game_state_poller.py"
Cohesion: 0.22
Nodes (7): _bases_state(), _extract_state(), test_bases_state_empty(), test_bases_state_loaded(), test_bases_state_single_runner(), test_extract_state_handles_empty_feed(), test_extract_state_pulls_fields_from_live_feed()

### Community 599 - "NFL prop pulled quote filtering"
Cohesion: 0.32
Nodes (8): drop_pulled_quotes(), _ts(), _q(), test_a_book_on_its_own_cadence_is_not_penalised_inside_three_hours(), test_a_book_that_stopped_returning_the_game_is_dropped(), test_a_player_the_book_stopped_quoting_is_dropped(), test_a_whole_market_the_book_pulled_is_dropped(), test_rows_from_one_fetch_minutes_apart_are_kept_and_a_line_move_is_not_a_pull()

### Community 60 - "tests: test_wnba_availability + wnba_availability"
Cohesion: 0.06
Nodes (50): absence_features(), absent_teammates(), build_context_features(), expected_rotation(), is_starter_tier(), _mean(), prior_rows(), recent_team_game_dates() (+42 more)

### Community 601 - "NCAAF venue feature tests"
Cohesion: 0.11
Nodes (11): haversine_miles(), tz_offset_from_lon(), _venue_features(), trip(), test_altitude_climb_is_signed_from_each_teams_own_elevation(), test_both_teams_travel_at_a_neutral_site(), test_eastward_travel_is_positive_tz_shift(), test_haversine_matches_real_geography() (+3 more)

### Community 604 - "NFL prop scorer kickoff ceiling tests"
Cohesion: 0.30
Nodes (8): _nfl_prop_too_early(), _iso(), test_a_kickoff_beyond_the_ceiling_is_too_early(), test_a_started_or_unknown_kickoff_is_not_too_early(), test_the_boundary_is_inclusive_at_the_ceiling(), test_the_scorer_and_the_card_read_ONE_constant(), test_the_scorer_loop_actually_applies_the_ceiling(), test_the_z_suffix_parses_like_the_offset_form()

### Community 608 - "supabase/functions/sharpsports-webhook: index + index"
Cohesion: 0.25
Nodes (5): internalIdFor(), pick(), admin, admin, cors

### Community 609 - "Live monitor web server"
Cohesion: 0.20
Nodes (6): build_server(), serve_in_thread(), http_server(), live_server(), test_loopback_without_a_token_is_allowed(), test_refuses_a_public_bind_without_a_token()

### Community 612 - "supabase/functions/stripe-checkout/index.ts"
Cohesion: 0.31
Nodes (8): customerFor(), form(), json(), stripe(), admin, cors, PRICES, TRIAL_DAYS

### Community 614 - "tests/test_book_list_budget.py"
Cohesion: 0.31
Nodes (4): _names(), test_every_book_the_nfl_prop_model_bets_at_is_actually_fetched(), test_the_nfl_prop_pull_is_one_group_with_both_references_in_it(), test_the_shared_list_is_one_group()

### Community 617 - "NFL prop over-lean study"
Cohesion: 0.25
Nodes (8): boot(), build(), grade(), implied(), lean_table(), load(), main(), profit()

### Community 62 - "NBA game market lab"
Cohesion: 0.05
Nodes (61): assemble(), _assert_spread_sign(), attach_close(), bars(), bet_frame(), blind_bets(), blind_first_fetch(), boot_ci() (+53 more)

### Community 620 - "Anonymous access revoke migration tests"
Cohesion: 0.13
Nodes (6): test_every_revoke_names_the_roles_rather_than_public(), test_it_does_not_enable_rls_blind(), test_odds_keeps_select_for_the_app(), test_the_app_write_tables_are_not_touched(), test_the_artifact_table_revokes_at_its_own_creation(), test_the_two_rls_off_tables_lose_everything()

### Community 622 - "SBR historical odds loader"
Cohesion: 0.25
Nodes (3): canonical_abbrev(), parse_csv_file(), test_sbr_abbreviations_are_canonicalised_for_mlb_only()

### Community 623 - "NBA injury report player matching"
Cohesion: 0.20
Nodes (6): match_player(), _near_season(), remap_changes(), test_a_name_printed_differently_matches_on_surname_and_initial_within_the_team(), test_player_ids_match_on_team_first_then_a_unique_season_name(), test_remap_rewrites_only_names_whose_id_changed()

### Community 628 - "Worker-only table security guard tests"
Cohesion: 0.17
Nodes (6): _call_source(), _repo_sources(), test_every_guard_on_a_worker_only_table_asks_about_rls(), test_every_literal_lock_down_target_is_declared(), test_every_worker_only_create_site_goes_through_the_gated_helper(), test_no_create_site_uses_the_ungated_builder()

### Community 629 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.47
Nodes (6): contentHeight(), evalExpr(), lineOf(), styleBlock(), styleProp(), visualHeight()

### Community 632 - "One pick per event record counting"
Cohesion: 0.15
Nodes (8): duplicate_copy_exclusion_sql(), test_the_discord_recap_counts_each_event_once(), test_the_finder_skips_copies_already_marked(), test_the_marker_is_one_constant_and_one_predicate(), test_the_monitor_dashboard_box_score_arm_counts_each_event_once(), test_the_monitor_dashboard_picks_arm_counts_each_event_once(), test_the_predicate_keeps_rows_with_no_marker(), _calibration_bet_only_rows()

### Community 635 - "tests/test_demote_ncaaf_over_under_platt.py"
Cohesion: 0.32
Nodes (4): _stmts(), test_it_demotes_only_the_measured_promotion(), test_it_does_not_move_the_gate_the_floor_or_a_pause(), test_migration_is_one_statement()

### Community 637 - "tests/test_discord_post_one_pick_migration.py"
Cohesion: 0.29
Nodes (3): _pairs(), test_it_names_each_measured_extra_and_the_row_kept(), test_the_update_does_not_rewrite_the_graded_outcome()

### Community 638 - "tests/test_game_scorer_spares_nfl_props.py"
Cohesion: 0.43
Nodes (5): _between(), _run_scorer_body(), test_an_nfl_game_never_enters_the_per_game_clear(), test_both_live_non_bet_clears_leave_nfl_rows(), test_the_left_out_ufc_clear_only_removes_unsettled_non_bets()

### Community 639 - "In-play count model column guard"
Cohesion: 0.18
Nodes (3): _setup(), test_an_artifact_wanting_an_unmapped_column_is_never_scored(), test_the_same_fixture_does_reach_the_model_when_the_map_agrees()

### Community 64 - "NFL in-play model backtest states"
Cohesion: 0.08
Nodes (20): _settle(), build_states(), load_pbp(), monotonicity_report(), _repair_day_offsets(), sample_states(), _pbp(), test_a_dome_suppresses_wind() (+12 more)

### Community 641 - "tests/test_mobile_ota_self_update.py"
Cohesion: 0.32
Nodes (4): _read(), test_app_root_mounts_the_ota_updater(), test_the_pieces_exist(), test_the_updater_actually_applies_the_update()

### Community 644 - "Registered models not firing"
Cohesion: 0.14
Nodes (5): test_a_model_with_picks_but_no_threshold_row_is_still_listed(), test_it_reports_whether_the_model_is_paused_and_whether_it_is_trained(), test_performance_starts_from_the_registered_models_not_the_graded_picks(), test_the_sport_survives_when_there_are_no_graded_picks(), test_the_zero_state_short_circuits_before_the_roi_row()

### Community 649 - "MLB totals public fade model"
Cohesion: 0.07
Nodes (23): diff(), pitcher_diff(), diff(), pitcher_diff(), numeric_feature_value(), _pct_pair(), _better_under(), edge_floor() (+15 more)

### Community 653 - "NFL prop book sweep"
Cohesion: 0.14
Nodes (12): _actuals(), _board(), p(), _line(), main(), _run(), soft_verdict(), test_a_bettable_book_still_passes() (+4 more)

### Community 655 - "UFC stats page parsers"
Cohesion: 0.09
Nodes (22): _int_or_none(), _mmss_to_sec(), _of_pair(), parse_event_page(), _two_ints(), parse_fight_page(), rounds_completed(), test_alias_makes_both_sources_agree() (+14 more)

### Community 656 - "Weather effect on game totals"
Cohesion: 0.23
Nodes (6): build_spots(), evaluate(), load_games(), main(), scoring_by_wind(), wilson()

### Community 658 - "NFL Kalshi price history fetch"
Cohesion: 0.21
Nodes (6): candles(), get(), map_games(), paged(), parse_event(), probe()

### Community 659 - "NFL prop lean concentration study"
Cohesion: 0.25
Nodes (7): add_context(), boot(), main(), profit(), report(), tercile_split(), under_profit()

### Community 660 - "Pipeline watch post ledger"
Cohesion: 0.18
Nodes (6): test_a_confirmed_post_is_ledgered_so_the_run_can_be_verified(), test_an_occasional_kind_is_not_flagged_for_being_quiet(), test_an_unconfirmed_post_is_never_ledgered(), test_the_ledger_is_one_row_per_day_so_a_retry_cannot_double_count(), test_the_watch_belongs_to_the_pipeline_service(), _wire()

### Community 663 - "NBA play-by-play roster and alias repair"
Cohesion: 0.15
Nodes (7): alias_play_ids(), derive_game(), roster_from_plays(), sides_inferred(), _with_aliases(), test_a_player_logged_under_a_second_id_is_read_as_his_box_id(), test_players_missing_from_the_box_get_the_side_of_their_own_plays()

### Community 666 - "Game day loop early exit"
Cohesion: 0.15
Nodes (7): _main_source(), test_an_unanswered_state_feed_does_not_look_like_the_slate_ending(), test_loop_exits_early_when_no_kickoff_is_near(), test_loop_polls_at_the_idle_cadence_when_nothing_is_live(), test_loop_sleeps_the_remainder_not_a_flat_interval(), test_loop_warns_when_a_pass_overruns_its_interval(), test_odds_fetch_uses_the_odds_cadence_not_the_loop_cadence()

### Community 669 - "Live feed vendor probe"
Cohesion: 0.24
Nodes (8): dump_vendor(), _get(), _is_live(), _key(), _row(), run(), _totals(), _vendor_key()

### Community 673 - "Scorer keeps off-DraftKings priced bets tests"
Cohesion: 0.29
Nodes (6): _bet(), db(), _left(), _statement(), test_a_bet_priced_at_another_books_line_survives_and_a_bet_with_no_price_does_not(), test_the_statement_names_both_prices()

### Community 675 - "NCAAF quarterback ablation study"
Cohesion: 0.28
Nodes (7): _fit(), main(), _report(), run(), summarise(), walk_forward(), wilson()

### Community 677 - "Drop voided NFL prop signals tests"
Cohesion: 0.23
Nodes (6): _stmts(), test_it_deletes_exactly_the_three_measured_lock_keys(), test_it_does_not_touch_picks_or_discord(), test_it_still_skips_a_key_that_has_a_standing_bet(), test_migration_is_one_statement(), test_standing_pick_uses_lock_key_sql_not_player_id()

### Community 692 - "NCAAF cross-book opener guards"
Cohesion: 0.17
Nodes (7): _branch(), test_band_ceiling_is_enforced_in_the_scorer(), test_dev_sign_maps_to_the_side_the_sharp_book_favours(), test_every_precondition_failure_returns_no_bet(), test_gate_is_enforced_and_read_from_the_artifact(), test_simultaneity_is_enforced(), test_still_gettable_is_enforced()

### Community 694 - "Pipeline watch run findings"
Cohesion: 0.17
Nodes (8): test_a_clean_run_still_posts(), test_a_failed_query_rolls_back_and_does_not_sink_the_run(), test_a_run_with_findings_posts_them(), test_every_not_ok_health_check_is_reported(), test_the_kill_switch_works(), _enabled(), findings_from_checks(), run_watch()

### Community 696 - "UFC fighter page parser"
Cohesion: 0.22
Nodes (7): _height_to_inches(), _parse_dob(), parse_fighter_page(), _reach_to_inches(), test_height_reach_dob(), test_parse_fighter_page(), test_parse_fighter_page_missing_fields()

### Community 697 - "Market handicap features"
Cohesion: 0.29
Nodes (4): build_rich_handicap(), _fav_signed_home_move(), _gated_flag(), _mul()

### Community 7 - "MLB over/under retrain sweep tests"
Cohesion: 0.10
Nodes (10): _side_rows(), test_marker_file_is_in_tree_so_the_freeze_would_not_block_the_worker(), test_missing_artifact_path_refuses_to_sweep_live(), test_over_covers_when_combined_score_beats_the_total_line(), test_price_below_the_house_floor_is_not_a_gradable_side(), test_push_on_the_total_emits_no_sides(), test_retrain_then_sweep_passes_the_new_path(), test_the_runner_retrains_then_sweeps_the_new_artifact() (+2 more)

### Community 705 - "Mobile stats filter checks"
Cohesion: 0.18
Nodes (9): chip, lineOnlyFn, playersDay, ROOT, sportReset, stats, teams, teamsDay (+1 more)

### Community 707 - "NHL goalie line helpers"
Cohesion: 0.83
Nodes (4): _goalie_line(), regressed(), saved_above(), tot()

### Community 708 - "Team stats rebuild and verify"
Cohesion: 0.18
Nodes (9): already_a_series(), _games(), live_season_snapshot_grace(), main(), _prior_season_rates(), rebuild_sport(), _team_games(), verify() (+1 more)

### Community 709 - "NFL opener cut sweep"
Cohesion: 0.23
Nodes (6): bettable_books(), boot_ci(), candidate_rows(), _load_backtest(), main(), select()

### Community 71 - "tests/test_live_orchestrator.py"
Cohesion: 0.05
Nodes (34): should_fetch(), split_triggers(), under_credit_cap(), apply_daily_cap(), classify_live_signal(), _ev_floor(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(), test_an_unmapped_live_model_is_completely_unaffected() (+26 more)

### Community 711 - "Live money no record-only tests"
Cohesion: 0.43
Nodes (4): _allowed(), _hits(), _rel(), test_the_repo_has_no_record_only_or_paper_tracking_mode()

### Community 712 - "Cross-book opener timestamp skew guard"
Cohesion: 0.18
Nodes (6): _minutes_apart(), test_identical_timestamps_are_zero_apart(), test_one_refresh_pass_late_is_tolerated(), test_the_real_production_skew_is_rejected(), test_timezone_suffixes_do_not_crash(), test_unparseable_timestamps_fail_closed()

### Community 713 - "NFL weather forecast persistence"
Cohesion: 0.35
Nodes (6): attach_issued(), _fmt(), load_games(), main(), report(), _under_rate()

### Community 718 - "NCAAF consensus gate study"
Cohesion: 0.31
Nodes (7): build_frames(), fmt(), grade(), load_closes(), main(), match(), wilson()

### Community 719 - "Mobile accessibility verify script"
Cohesion: 0.67
Nodes (3): read(), readUtf8(), verticalSlop()

### Community 72 - "Market handicap feature tests"
Cohesion: 0.05
Nodes (34): attach_market_handicap(), build_public_features(), empty_handicap(), favorite_side(), _rlm(), row_is_pregame(), select_latest_pregame_splits(), _split() (+26 more)

### Community 721 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.67
Nodes (3): closeOf(), openTag(), toggleUse()

### Community 730 - "Eastern time game date rules"
Cohesion: 0.20
Nodes (5): _sources(), test_no_game_date_is_derived_from_the_container_clock(), test_the_live_modules_cannot_even_name_date_today(), test_today_et_is_eastern_inside_the_window_that_broke(), test_today_et_matches_the_pipelines_own_derivation()

### Community 731 - "Game-line market sweep job"
Cohesion: 0.18
Nodes (5): test_runner_captures_stdout_from_the_script_main(), test_sport_and_market_are_bounded(), test_the_declared_key_is_present_and_valid(), test_the_runner_imports_the_script_main_not_a_shell(), _job_game_line_market_sweep()

### Community 732 - "NBA injury report name and team parsing"
Cohesion: 0.22
Nodes (7): name_first_last(), norm_name(), _row(), team_code(), test_name_key_drops_accents_punctuation_and_suffixes(), test_names_turn_round_with_their_suffix_on_the_surname(), test_team_names_map_to_our_codes()

### Community 74 - "Prop CLV and SQL escaping tests"
Cohesion: 0.09
Nodes (17): _fn(), test_a_backfill_failure_never_breaks_settlement(), test_a_pick_is_only_stamped_captured_once_a_measure_resolved(), test_a_pick_stamped_after_first_pitch_is_never_measured(), test_a_prop_pick_whose_label_has_no_name_is_skipped_not_guessed(), test_both_guards_agree(), test_clv_pct_never_compares_prices_across_a_moved_line(), test_golf_stays_excluded() (+9 more)

### Community 75 - "NCAAF margin cover evaluation"
Cohesion: 0.11
Nodes (16): margin_cover_prob(), fit_and_register(), main(), _print_sweep(), rmse(), sweep_spread(), verdict(), walk_forward() (+8 more)

### Community 758 - "NFL prop week one candidate pool"
Cohesion: 0.22
Nodes (5): partially_played_week_one(), _player_row(), _team_row(), test_a_clean_week_one_is_unchanged(), test_teams_still_to_play_keep_a_candidate_pool()

### Community 80 - "Global EV floor tests"
Cohesion: 0.07
Nodes (25): min_ev_for(), test_ncaaf_live_ev_floor_is_wired_from_config(), _built(), floor_030(), identity_maps(), _nfl_fixtures(), open_pregame_cut(), _pregame() (+17 more)

### Community 82 - "Mobile error state tests"
Cohesion: 0.11
Nodes (24): _load_state_dir(), _raw_error_lines(), _read(), _run_node(), test_aborts_are_silent_and_offline_slow_are_narrow(), test_aborts_render_nothing_and_every_catch_skips_them(), test_designer_review_fixes_behaviour(), test_error_state_component() (+16 more)

### Community 850 - "Restated pick keeps better price"
Cohesion: 0.22
Nodes (5): _producer(), test_a_restated_pick_still_names_the_cheaper_book(), test_a_worse_price_elsewhere_never_replaces_draftkings(), test_both_signal_producers_select_the_better_price(), test_the_locked_producer_maps_the_columns_into_the_dict()

### Community 854 - "MLB public split pre-start filter"
Cohesion: 0.27
Nodes (6): is_pre_commence(), load_public_over_splits(), select_latest_pre_commence_over(), test_missing_clocks_fail_closed(), test_post_start_split_is_dropped_even_when_text_says_before(), test_snapshot_at_commence_is_not_pre_commence()

### Community 856 - "NCAAF feature assembly"
Cohesion: 0.20
Nodes (4): _assemble_ncaaf_features(), _game_tier(), test_assembly_carries_venue_context_and_hfa(), test_season_opener_gets_a_zero_rest_differential_not_a_null()

### Community 86 - "scripts/nfl_edge_preregistered_2026.py"
Cohesion: 0.10
Nodes (38): bar(), bets_frame(), bh(), binom_line(), _by_game(), cell(), fam(), first_last() (+30 more)

### Community 864 - "Live orchestrator floor pass tests"
Cohesion: 0.20
Nodes (5): _consume_source(), test_a_floor_pass_scores_every_live_game_not_just_triggered_ones(), test_no_pending_triggers_no_longer_short_circuits_unconditionally(), test_the_fetch_is_never_asked_for_every_event_the_feed_returns(), test_the_floor_is_gated_on_a_game_actually_being_live()

### Community 867 - "NCAAF play-by-play value range scan"
Cohesion: 0.33
Nodes (3): _extremes(), observed_ranges(), test_the_scan_survives_nulls_and_non_numeric_cells()

### Community 868 - "NCAAF in-play odds outage handling"
Cohesion: 0.22
Nodes (5): _feed_with_payload(), test_a_sustained_feed_outage_degrades_to_no_odds(), test_cached_odds_are_served_while_fresh(), test_credit_cap_reports_no_odds_rather_than_a_frozen_line(), test_credit_cap_still_serves_a_payload_that_is_still_fresh()

### Community 87 - "tests: test_player_positions + player_positions_ingestor"
Cohesion: 0.07
Nodes (16): match_to_log(), parse_athlete(), parse_cfbd_roster(), roster_candidates(), test_a_real_run_before_the_table_exists_fails_so_it_is_retried(), test_a_shared_name_is_settled_by_team_then_by_most_recent_game(), test_a_unique_name_matches_its_log_id(), test_an_unexpected_athlete_shape_is_skipped_not_raised() (+8 more)

### Community 873 - "NFL in-play pick writer price ceiling"
Cohesion: 0.10
Nodes (9): _executor_min_price(), _probe_config(), test_the_ceiling_is_a_refusal_not_a_filter(), test_the_default_announcer_calls_both_live_notifiers(), test_the_insert_tolerates_the_one_row_per_pick_index(), test_the_lane_can_actually_settle(), test_the_lane_refuses_a_quote_past_the_ceiling(), test_the_retired_model_carries_no_threshold_row() (+1 more)

### Community 874 - "NFL 2024 in-play edge replication"
Cohesion: 0.36
Nodes (9): families(), fmt(), main(), parse_2025_output(), pooled_table(), replication(), repro_check(), row_of() (+1 more)

### Community 875 - "Anonymous grants apply plan"
Cohesion: 0.40
Nodes (3): _plan(), test_every_declared_relation_is_granted_exactly_once(), test_the_plan_revokes_before_it_grants()

### Community 876 - "App RPC anonymous access guard"
Cohesion: 0.40
Nodes (3): _app_rpcs(), test_every_rpc_the_app_calls_is_declared_or_known_absent(), test_the_dynamic_rpc_resolver_actually_finds_the_ternary_names()

### Community 877 - "NFL prop ladder calibration"
Cohesion: 0.42
Nodes (6): actual_for(), build(), load(), main(), profit(), _table()

### Community 883 - "Pregame prices freshness health check"
Cohesion: 0.25
Nodes (4): check_pregame_prices_current(), _leftover(), _same_game(), _swapped_ufc_id()

### Community 884 - "Anonymous access table lockdown"
Cohesion: 0.25
Nodes (4): closed_tables(), test_lock_down_never_uses_force_row_level_security(), test_lock_down_sql_revokes_before_it_enables_rls(), test_the_worker_only_tables_are_not_also_declared_app_readable()

### Community 886 - "Live pick expected value per unit"
Cohesion: 0.25
Nodes (4): expected_value(), _signals(), test_ev_is_the_payout_aware_number_edge_is_not(), test_ev_is_unmeasurable_without_a_price()

### Community 89 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.04
Nodes (48): a11ySrc, allowHit, ALLOWLIST, app, badExempt, bar, bareClose, baselineLeft (+40 more)

### Community 890 - "Discord notifier units convention"
Cohesion: 0.29
Nodes (4): test_prob_only_picks_fall_back_to_the_settlement_price(), test_units_convention_matches_the_stated_rule(), _decimal_odds(), units_won()

### Community 891 - "Insert column alignment checks"
Cohesion: 0.32
Nodes (3): _statements(), test_columns_and_values_line_up(), test_the_scorer_pick_insert_is_actually_covered()

### Community 892 - "Model ROI collapse detection"
Cohesion: 0.25
Nodes (5): test_roi_collapse_is_crit_when_hit_rate_dies(), test_roi_ignores_unpriced_profit_flat(), detect_roi_collapse(), _sample(), units_from_profit_flat()

### Community 894 - "NFL in-play pick date and announce tests"
Cohesion: 0.25
Nodes (3): test_a_night_game_pick_carries_the_game_s_date_not_the_utc_clock(), test_nothing_written_means_nothing_announced(), test_resolution_refuses_rather_than_guesses()

### Community 895 - "NFL tackles total target tests"
Cohesion: 0.39
Nodes (5): _derive(), _frame(), test_a_game_log_without_the_column_cannot_build_tackles(), test_the_ingestor_carries_tackles_with_assist(), test_the_target_is_the_box_score_total()

### Community 896 - "Pipeline watch credit burn checks"
Cohesion: 0.25
Nodes (4): test_burn_is_judged_against_the_cap_not_against_yesterday(), test_burn_survives_a_non_numeric_credits_column(), test_failed_api_calls_are_reported_even_when_burn_is_low(), findings_from_burn()

### Community 899 - "NFL in-play pick publish refusal"
Cohesion: 0.29
Nodes (4): refuse_publish_reason(), test_refuse_publish_allows_a_real_rush_under(), test_refuse_publish_blocks_pass_attempt_overs(), test_refuse_publish_blocks_the_constant_prob_fingerprint_even_on_rush()

### Community 901 - "Model bet volume spike check"
Cohesion: 0.29
Nodes (5): test_volume_spike_vs_median(), test_volume_without_history_is_skipped_not_flagged(), detect_volume_spike(), _median(), units_from_recommended_bet()

### Community 905 - "Pipeline watch missing webhook alert"
Cohesion: 0.29
Nodes (3): test_a_missing_webhook_escalates_rather_than_vanishing(), _announce(), _announce_and_ledger()

### Community 906 - "MLB prop board market coverage test"
Cohesion: 0.33
Nodes (3): _board_markets(), table(), test_the_mlb_board_and_the_mlb_pull_are_one_set()

### Community 907 - "Pipeline pass watch findings"
Cohesion: 0.33
Nodes (4): test_a_clean_pass_produces_no_finding(), test_a_pass_with_failed_steps_is_reported(), test_a_pass_with_no_finish_is_reported_without_over_reading_it(), findings_from_passes()

### Community 908 - "NBA archive moneyline timing checks"
Cohesion: 0.40
Nodes (3): ml_timing(), sign_agreement(), test_ml_timing_and_sign_agreement_count_what_they_say()

### Community 909 - "NBA game clock parsing"
Cohesion: 0.40
Nodes (3): parse_clock(), test_field_goal_value(), test_parse_clock()

### Community 91 - "NBA prop model lab"
Cohesion: 0.06
Nodes (51): books(), decimal(), expected_value(), fit_alpha(), implied(), nb_logpmf(), p_over(), settle_value() (+43 more)

### Community 98 - "NBA play-by-play ingestor"
Cohesion: 0.06
Nodes (46): nba_team(), active_queries(), alias_map_rows(), _bool(), box_context(), box_finals(), build_game(), build_gap_game() (+38 more)

### Community 106 - "Supabase schema tables"
Cohesion: 0.03
Nodes (101): api_call_log, device_push_tokens, feedback_messages, feedback_threads, fighters, golf_players, golf_rounds, idx_api_call_api_ts (+93 more)

### Community 179 - "mobile/app.json"
Cohesion: 0.05
Nodes (38): backgroundColor, foregroundImage, adaptiveIcon, package, projectId, expo, android, extra (+30 more)

### Community 184 - "mobile/package.json"
Cohesion: 0.06
Nodes (31): dependencies, expo, expo-asset, expo-dev-client, expo-font, expo-notifications, expo-status-bar, expo-updates (+23 more)

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
Cohesion: 0.70
Nodes (4): par(), par_wait(), refresh_pass.sh script, step()

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

### Community 790 - "Mobile build dev dependencies"
Cohesion: 0.29
Nodes (7): devDependencies, @babel/core, babel-plugin-module-resolver, babel-preset-expo, tsx, @types/react, typescript

### Community 81 - "docs: nhl_market_lab + nhl_clv_ev_assessment"
Cohesion: 0.08
Nodes (38): nhl_research worker job, scripts/nhl_derivative_totals_backtest, data/ingestors/nhl_derivative_odds_history, models/nhl_props.py (Spec per market), Anytime goalscorer: not a candidate once names corrected, nhl_moneyline and nhl_moneyline_regulation: no cut clears, Game models: lock later? Refuted, The overnight pass takes the night's slots (+30 more)

### Community 897 - "NBA play-by-play lineup docs"
Cohesion: 0.29
Nodes (6): Commands, How a stretch is built (each rule is pinned by a test that was watched to fail), NBA play-by-play and on-court lineup segments, Source, Things a reader should know, What was loaded, and the checks (re-measured 2026-10-17 on production, after the rebuild)

### Community 151 - "docs/rules_evidence.md"
Cohesion: 0.07
Nodes (13): 'Decisions needed from you' is second person, never first, A model in config.MODELS with no FEATURE_MAP entry kills scoring for every sport, Every front-end change is reviewed by the UX designer agent before its PR opens, Gate the number that gets bet (cal_error_actionable), A health check must not gate on the thing that breaks, The settled live-prop record is zero bets, The Odds API returns x-requests-remaining on every response, including 401, How the pick rule was found: the NCAAF live loop delete-and-replaced every 45s (+5 more)

### Community 183 - "docs: probability_calibration + nfl_rule_2026_track"
Cohesion: 0.16
Nodes (18): tracking.paper_tracker (_NFL_MODEL_MARKETS), scripts/nfl_rule_2026_track, tracking/opening_signals.capture_opening_signals, tracking.opening_report, tracking/opening_signals.settle_opening_signals, MAX_FIRE_LEAD = 4, nfl_opener_spread, nfl_wind_totals (+10 more)

### Community 192 - "NFL game lines model write-up"
Cohesion: 0.11
Nodes (19): DataRegistry: source catalog with priority levels, scripts/edge_hunt.py: moneyline calibration clean, ML-vs-spread gap dead, Forecast validation (2026-08-15): rule holds at 57.09% under real day-3 error, Game totals model (consumes spread output as competitiveness), IngestOrchestrator: per-source fetch with no silent fallbacks, Middling does not clear vig, Moneyline derived from spread via fitted sigmoid, Oracle ceiling: perfect closing-line knowledge (+11 more)

### Community 210 - "Model quality and MLB docs"
Cohesion: 0.12
Nodes (17): Hybrid Pin-agreement filter on mlb_over_under bets, mlb_runline and mlb_over_under (paused), mlb_total_public_fade card (paper UNDER), Slate concentration guard (insert-time), F5 odds coverage (DK carries F5 ML only), clv_degradation check, model_quality_checks table, Daily model-quality monitor (+9 more)

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

### Community 419 - "NFL in-play edge search findings"
Cohesion: 0.06
Nodes (28): Halftime second-half lines, out of sample at real prices, The live prop market leans over like the pre-game one, Publish backstop refuses pass-attempt overs, Accrued carries from ESPN core leaders, rush_attempt_pace model: one offset on the book's number, Pace ratio, In-play rushing-attempt UNDER on pace ratio >= 1.25, The eleven NFL distributional prop models (+20 more)

### Community 420 - "mobile/docs/UX_REVIEW.md"
Cohesion: 0.16
Nodes (13): dashboard.html renderRoster(), A pick is a pick (re-priced line never replaces the locked one), Copy: formatAmerican/formatPct/formatCurrency, model ids never raw, Decided at the best bettable price; read via lib/decisionPrice.ts, frontend-ux-designer agent contract, Mobbin MCP connector (one route: Matt's claude.ai connector), Product rules: a violation is a Blocker, Reuse before invention (EmptyState, StatTile, SignalBadge, ...) (+5 more)

### Community 427 - "Odds sources and prediction markets research"
Cohesion: 0.16
Nodes (18): scripts/nfl_prop_ladder_grade, scripts/verify_kalshi, Alternate coverage effectively begins in 2024, Anchored ladder graded: fails every clause, Provider comparison: Odds API, Kalshi, SportsGameOdds, OddsJam, Unabated, OpticOdds, 1.48M alternate-market rows already stored and unread, Kalshi (CFTC-regulated event contracts), Status: deferred, no code (as of the memo) (+10 more)

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

### Community 478 - "Probability calibration and EV floor docs"
Cohesion: 0.24
Nodes (14): models/honest_ev.gate and honest_probability, tracking/system_health._report_model_calibration, MODEL_OWN_EV_FLOOR and MODELS_ON_OWN_PROBABILITY for wind and opener, fetch_graded reads picks for NFL/NCAAF/UFC/rule models, GLOBAL_MIN_EV: 0.30 then 0.20, The go-live calibration gate never computed a real number, ncaaf_over_under Platt map demoted 2026-09-26, Per-model floors (#796) measured on the calibrated number (+6 more)

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

### Community 545 - "NFL prop market and edge research docs"
Cohesion: 0.05
Nodes (24): Live inning gate replay, Live feature sensitivity (12.8pp median swing), mlb_live_total_runs (in-play total), Negative-binomial (NB1) tail, pregame_total_line feature (market anchor), ncaaf_live_total 2025 in-play backtest, ncaaf_live_win_prob 2025 in-play backtest, Cross-book opener signal (DK vs Bovada) (+16 more)

### Community 553 - "Monitoring and model state docs"
Cohesion: 0.10
Nodes (12): roi_collapse check, api_call_log table, Heartbeat watchdog, Live monitor dashboard (monitoring/), Live tuning panel (Models view), mv_scored_pick_outcomes (sweep matview), Official live date 2026-09-01, The request probe: one patch, not 75 call-site edits (+4 more)

### Community 558 - "docs/health_checks.md"
Cohesion: 0.24
Nodes (10): model_artifacts_load counts what it opened, model_artifacts table fallback restore, Three separate artifact questions, three separate failures, KNOWN_UNTRAINED — config models intentionally without artifacts, Pipeline-observability checks: refresh_pass_completion, refresh_pass_steps, signal_delivery, pick_label_integrity, pipeline_runs — the run ledger (tracking/run_ledger.py), Retrain Model workflow (retrain_model.yml), tracking/system_health.py — CRIT and WARN feed checks (Step 12) (+2 more)

### Community 560 - "docs/retrain_2026_plan.md"
Cohesion: 0.18
Nodes (13): scripts/paused_model_assessment, data.ingestors.baseball_savant_ingestor, models.trainer, anytime_td verdict: inert, not losing, F5 O/U and F5 RL paused: leak-mismatched, synthetic-line trained, NCAAF in-play season replay: -3.4% and -13.1%, No model has a cut that clears on the deployed artifact, batter_sb: opp_team_sb_allowed feature (+5 more)

### Community 603 - "docs/reviews/2026-09-07-nfl-props-deep-dive.md"
Cohesion: 0.33
Nodes (7): Twelve artifacts committed from a replica failed pickle.load unnoticed for two weeks, The eleven NFL projection prop models, unpaused on placeholder thresholds, nfl_prop_market: the de-vig rule (Pinnacle as truth, equal lines only), The scorer is pinned to today, the card looks ten days ahead, 112 bets on one Sunday from untuned models; 41-46% BET rates are placeholders, Eleven NFL distributional props paused 2026-09-14, NFL props deep dive — two lanes, one of them can't see the slate (2026-09-07)

### Community 606 - "NCAAF search findings and plans"
Cohesion: 0.12
Nodes (7): scripts/ncaaf_search/, Honest MLB signal is ~0.55-0.56 AUC, CollegeFootballData (CFBD) as primary source, ncaaf_spread / ncaaf_over_under / ncaaf_moneyline, Model state assessment, all 71 models (2026-09-03 snapshot), NCAA Football model build plan, NCAAF model search findings (2026-08-25)

### Community 627 - "docs/market_coverage.md"
Cohesion: 0.36
Nodes (7): ncaaf_prop_odds_ingestor and its probe, test_the_mlb_board_and_the_mlb_pull_are_one_set, MLB probe 2026-09-05 — served, unsupported and unpriced keys, NCAAF prune — FOOTBALL_MARKET_NOT_PRICED per league, scripts/probe_market_coverage.py — one market per call, writes nothing, Neither prop ingestor writes to api_call_log, Prop market coverage — what the feed actually serves

### Community 652 - "(root): pr-ci + requirements"
Cohesion: 0.33
Nodes (5): Mobile thresholds drift check (generate_mobile_thresholds --check), NFL preflight --ci, PR CI workflow — non-integration pytest subset, Render blueprint — betting-scheduler background worker, requirements.txt — >= pins for Python 3.14 wheels

### Community 66 - "docs/nfl_props_model.md"
Cohesion: 0.08
Nodes (33): scripts/nfl_prop_market_card, scripts/nfl_prop_replay, data/ingestors/kalshi_prop_ingestor.py (SERIES_MARKET, record_ladders), DraftKings de-vigged price sits above realised over-rate, tackles_assists +21% is a measurement error (control), Walk-forward re-fit 2023-2025 (-4.32% over 1,554 bets), Traps specific to props, Anytime TD field de-vig: closed (+25 more)

### Community 665 - "Push notifications and privacy docs"
Cohesion: 0.23
Nodes (12): mobile usePushNotifications / NotificationsCard / pushDiagnosis, On-device storage: bankroll and placed-bet flags in AsyncStorage, Claim: the app cannot write to the backend, Signalbase privacy policy: nothing personal collected, APNs key / aps-environment entitlement is the blocker, device_push_tokens table (anon INSERT/UPDATE, no SELECT), No push has ever reached a phone (2026-09-12), push_sent ledger means considered, not delivered (+4 more)

### Community 674 - "docs/game_injury_gate.md"
Cohesion: 0.40
Nodes (5): ESPN core probables for the NHL starting goalie, A NONE from this gate is not locked — the reprice path, The gate rule — refuse a game-model BET on a confirmed Out starter/star/goalie, Fires in scorer.score_game and _score_nhl_3way, after best-price requalify, before insert, Game-model starter / star / goalie gate

### Community 688 - "NFL wind totals runbook and staking"
Cohesion: 0.36
Nodes (7): DOCUMENT STATUS block: superseded claims indexed, Under rate by forecast lead 1-7 (~0.41pp per day), Original staking: 25% Kelly capped at 3% (superseded), Kelly-proportional units with slate shading 1/sqrt(1+(k-1)rho), Stops: 2 units per bet, 3 units per slate, review at -15 units, Runbook: Wind Totals, scripts/stake_sizing.py: 1 unit = 1% of bankroll

### Community 710 - "mobile/docs/BILLING.md"
Cohesion: 1.00
Nodes (4): useEntitlement() access gate (subscription OR Discord), useSubscription() subscription-only state, useEntitlement(), not useSubscription(), Access is one gate: useEntitlement(), never useSubscription().entitled

### Community 720 - "docs/testing.md"
Cohesion: 0.67
Nodes (3): PR CI runs a non-integration pytest subset, Pure function tests, in-memory SQLite via conftest, Test suite (testing.md)

## Ambiguous Edges - Review These
- `Claim: the app cannot write to the backend` → `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`  [AMBIGUOUS]
  docs/privacy.html · relation: conceptually_related_to

## Knowledge Gaps
- **105 isolated node(s):** `RFC-4122`, `@babel/core`, `babel-plugin-module-resolver`, `babel-preset-expo`, `expo-asset` (+100 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 10797 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **209 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_connection()` connect `Script connections and health utilities` to `ESPN injury ingestor`, `Odds, prop odds and NHL derivative odds ingestors`, `Shared database connection and settlement`, `Pipeline run ledger and orphan cleanup`, `Model training and probability calibration`, `NFL prop data and player names`, `Sports stats ingestors and database helpers`, `Discord pick notifier tests`, `Daily pipeline runner and push notifier`, `Discord pick posting and void notices`, `NHL prop cards and blocked shots`, `Probability calibration and cut sweeps`, `NBA prop projection card`, `NHL moneyline and market research scripts`, `NBA injury report and schema guards`, `NCAAF situational spot search`, `NBA prop model core`, `NCAAF starting quarterback absence study`, `NCAAF totals lead timing study`, `DataGolf ingestor and NHL SBR archive`, `Worker job queue runner`, `Failure alerter fake-connection tests`, `scheduler.py`, `tests/test_void_picks.py`, `NCAAF in-play gameday loop`, `Anonymous read grants application`, `Shared scripts, probes and odds pulls`, `tests: test_wnba_availability + wnba_availability`, `NHL blocked shots backtest`, `NCAAF margin cover evaluation`, `Push notifier and publish key identity`, `NHL derivative totals model`, `docs: nhl_market_lab + nhl_clv_ev_assessment`, `NCAAF structure scan`, `tests/test_recap_retries_a_skipped_day.py`, `Player news feed ingest`, `tests/test_ncaaf_pbp_store.py`, `tests/test_heartbeat_watchdog.py`, `NBA play-by-play ingestor`, `Record correction post tests`, `NFL prop information and market tests`, `NCAAF college data ingestor`, `Record correction posts to Discord`, `tests/test_live_calibration.py`, `nfl_live_leader/gameday.py`, `NFL forecast weather fetching`, `NHL prop expected value lab`, `features/golf_feature_engine.py`, `nfl/live_model/tests/test_backup_snaps.py`, `models/nhl_props.py`, `Weather effect on game totals`, `NBA prop projection and market card`, `Discord daily results recap`, `Historical odds backfill tests`, `Live feed vendor probe`, `NBA box score enrichment`, `Deploy checks and worker job queue`, `NHL stats and goalie ingestors`, `Prop box score backfill`, `scripts/game_line_market_sweep.py`, `NFL wind and opener publisher`, `tests/test_first_signal_repair.py`, `Team stats rebuild and verify`, `NFL prop features and walk-forward`, `NCAAF consensus gate study`, `data/ingestors/nfl_inplay_history.py`, `Core game scorer and config`, `NCAAF in-play locked pick tests`, `NBA results and box score ingestor`, `tests/test_team_board_cache.py`, `Discord signal notifier tests`, `tests/test_nfl_poll_fast_silence.py`, `data/ingestors/ncaaf_inplay_history.py`, `MLB and WNBA stats ingestors and pitcher rebuild`, `data/ingestors/nhl_boxscore.py`, `scripts/mlb_total_public_fade_topk.py`, `tests/test_ncaaf_search_features.py`, `NCAAF in-play history backtest`, `Monitoring HTTP stream handler`, `NCAAF game-day context tests`, `NCAAF play-by-play state builder`, `Game feature engines and backtester`, `NFL prop stats data ingestion`, `NHL prop backtest namesake handling`, `Odds pruning and sharp book retention`, `NFL in-play pick writer`, `tests/test_heartbeat_disabled_jobs.py`, `UFC event stats ingestor`, `tests/test_promote_calibration_job.py`, `Intraday data freshness tests`, `Model quality and CLV checks`, `NCAAF outcome edge scan`, `tests/test_merge_mlb_twin_games.py`, `MLB prop market sweep research`, `Results recap backfill to X`, `NCAAF totals weather and margin evaluation`, `tests/test_transaction_pooler.py`, `WNBA prop market card`, `Watchdogs and calibration monitors`, `Player news ingestor tests`, `NCAAF steam lag study`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **What connects `RFC-4122`, `@babel/core`, `babel-plugin-module-resolver` to the rest of the system?**
  _105 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `ESPN injury ingestor` be split into smaller, more focused modules?**
  _Cohesion score 0.07342995169082125 - nodes in this community are weakly interconnected._
- **Why does `mlb_live_total_runs (in-play total)` connect `NFL prop market and edge research docs` to `Monitoring and model state docs`, `docs/thresholds.md`, `NCAAF search findings and plans`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Should `Mobile stats board` be split into smaller, more focused modules?**
  _Cohesion score 0.01430605464777273 - nodes in this community are weakly interconnected._
- **Why does `docs/thresholds.md` connect `docs/thresholds.md` to `NFL prop market and edge research docs`, `docs/sports/nhl.md`, `docs/sports/nfl.md`, `mobile: TESTFLIGHT + README`, `docs/sports/mlb.md`, `docs/sports/wnba.md`, `docs/sports/ncaaf.md`, `docs/reviews/2026-09-07-nfl-props-deep-dive.md`, `docs/history: learnings + build_state`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Claim: the app cannot write to the backend` and `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._