# Graph Report - bm-nba-game  (2026-10-17)

## Corpus Check
- Large corpus: 1474 files · ~2,419,223 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 28522 nodes · 67740 edges · 875 communities (680 shown, 195 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 1729 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d40dbb7c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ESPN injury ingestor
- Mobile stats board
- Record correction posts to Discord
- Mobile stats odds and line legs
- tests/test_nfl_live_leader_gameday.py
- nfl_live_leader/gameday.py
- tests/test_calibration_promotion.py
- tests/test_score_off_any_book_line.py
- Mobile daily results calendar
- Mobile pick filters and sorting
- tests/test_ncaaf_alias_scores.py
- tests/test_prop_alternate_lines.py
- Mobile error and not-found states
- tests/test_backtester.py
- NHL prop expected value lab
- nfl/live_model/feeds/odds_live.py
- NHL props nightly card
- NBA prop market lab
- Discord pick notifier tests
- nfl/live_model/tests/test_backup_snaps.py
- mobile/scripts: verify_book_links + verify_betslip_combine
- NBA official injury report ingestor
- Mobile data queries and shared types
- mobile/scripts/verify_contrast_tokens.ts
- models/nhl_props.py
- tests/test_health_pregame_prices_current.py
- Pick lock after settlement tests
- NBA game line move study
- NBA prop market card publisher
- tests/test_mlb_game_market.py
- Mobile sign-in and auth
- Threshold review report tests
- Idle read transaction tests
- Game odds ingestor and historical backfill
- tests/test_prop_box_scores.py
- NBA game model prop feature tests
- Best line and best-price decision tests
- Mobile Discord linking and access
- tests/test_ddl_guard.py
- tests/test_nfl_opener.py
- NHL stats and probable goalies ingest
- Discord pick posting and void notices
- NBA game model luck feature tests
- tests/test_publisher_lock.py
- tests/test_dk_direct_feed.py
- tests/test_credit_budget.py
- Mobile model catalog and thresholds
- NHL market-anchored moneyline model
- Worker job queue run tests
- NFL wind and opener publisher
- Settlement and self-heal tests
- NHL blocked shots prop card
- Prop market devig and bet finding
- tests/test_ungraded_model_performance.py
- mobile/scripts/verify_push.ts
- Prop price pregame cutoff tests
- Mobile markets and formatting
- Threshold and EV floor sweeps
- Monitoring registry and probe tests
- tests/test_nhl_asof.py
- NFL prop features and backtests
- NFL in-play game state feed
- MLB in-play inning gate replay
- data/ingestors/nfl_inplay_history.py
- Mobile bankroll setting store
- Mobile in-app feedback flow
- NHL props per-game limit tests
- Pick scorer and bet sizing
- NCAAF in-play engine and pick lock
- NBA prop projection card
- tests/test_db_reconnect.py
- NHL derivative totals card tests
- tests/test_live_lock.py
- tests/test_refresh_retry.py
- NBA results and box score ingestor
- NBA results ingestor tests
- NBA second game calibration fitting
- tests/test_local_cache_is_additive.py
- tests/test_calibration_check_coverage.py
- tests/test_book_team_map.py
- tests/test_team_board_cache.py
- NBA second game model fitting
- Mobile settings and sportsbook connection
- nfl/live_model/tests/test_rush_attempt_pace.py
- tests/test_nfl_poll_fast_silence.py
- NHL moneyline and market research scripts
- data/ingestors/ncaaf_inplay_history.py
- MLB and WNBA stats ingestors and pitcher rebuild
- tests/test_weather_lookahead.py
- tests/test_nhl_asof.py
- tests/test_dk_freshness_parse.py
- NBA historical odds archive buyer
- models: slate_concentration + test_slate_concentration
- View migration lock handling tests
- Publisher and injury fetch test fakes
- tests/test_ncaaf_search_features.py
- NCAAF walk-forward model search
- Deploy checks and worker job queue
- Mobile teams board and team detail
- Best line threshold sweep
- tests/test_nfl_scored_rows.py
- NCAAF college data ingest tests
- Mobile parlay builder and correlation
- tests/test_prop_odds_utc_stamp.py
- Monitoring HTTP stream handler
- NFL publisher lookahead and key tests
- tests/test_feature_artifact_agreement.py
- CLV graded at the price taken
- tests/test_cloud_retrain_artifacts.py
- NHL totals card publishing
- MLB live game state polling loop
- System health checks and record reconciliation
- tests/test_nfl_opener.py
- tests/test_team_stats_asof_invariants.py
- Stake sizing and units parity
- NFL Kalshi edge and NHL blocked shots
- tests/test_nfl_wind_publisher.py
- Prop odds ingestors and quota tracking
- NFL live prop model tests
- tests/test_health_reason_and_cadence.py
- tests/test_live_publish_parity.py
- tests/test_nfl_weather_supabase_readback.py
- NFL in-play pass attempt prop model
- Pregame line poller change tests
- Pitcher stats as-of invariant tests
- tests/test_walk_forward_eval.py
- NBA prop model core
- NHL props card slate tests
- Pipeline log reason tests
- NHL prop newest fetch shopping tests
- NFL player stats and props data
- NCAAF in-play score distribution pricing
- tests/test_nfl_scored_rows.py
- tests/test_system_health_checks.py
- X results job and cursor wrapper tests
- NBA prop window scheduling tests
- NBA second game projection engine
- NFL opener card rows
- Kalshi prop ladders and game markets
- NFL wind totals model
- tests/test_live_pick_features.py
- Pregame price age tests
- tests/test_prop_missing_features.py
- MLB public fade top picks ranking
- Player news ingestor and name matching
- NBA prop closing line tests
- NFL in-play decline recording tests
- NHL anchored moneyline inputs and fit
- tests/test_run_ledger_orphans.py
- MLB play-by-play ingestor
- NBA lineup stints from play-by-play
- In-play calibrated decision tests
- NFL DraftKings line snapshots
- Sharp book odds retention in pruning
- NFL historical weather fetch script
- tests/test_heartbeat_disabled_jobs.py
- tests/test_repair_bogus_first_pitch_labels.py
- nfl/live_model/tests/test_executor.py
- tests/test_sbr_loader.py
- NHL totals EV floor gate
- mobile/scripts/ux_scan.mts
- Database connection and game features
- NBA second game market family frames
- Price prefilter timeout rollback tests
- mobile/src/lib/otaUpdate.ts
- tests/test_live_quote_staleness.py
- Mobile game status and date formatting
- NHL derivative odds history purchase
- Prop pick settlement across sports
- Pipeline report with per-section rollback
- supabase/functions/_shared/discord.ts
- Worker job queue validation tests
- tests/test_system_health_checks.py
- UFC event ingest tests
- tests/test_batter_prop_log_pin.py
- tests/test_opp_starter_features.py
- NFL CLV backtest and feature build
- MLB doubleheader twin game merge
- tests/test_discord_channel_probe.py
- tests/test_nfl_prop_one_read_per_game.py
- Game outcome target tests
- NFL forecast and historical weather fetch
- NFL in-play pick writer row tests
- Discord results recap backfill
- Mobile paywall and in-app billing
- scripts/nfl_edge_gameline_rules.py
- tests/test_model_game_savepoint.py
- tests/test_system_health_checks.py
- NFL live leader decision model
- tests/test_calibration_watch.py
- tests/test_promote_external.py
- NFL in-play prop snapshot puller
- Failure alerter fake-connection tests
- Prop odds with missing game tests
- Job heartbeat watchdog and ops alerts
- MLB prop pregame price cutoff tests
- tests/test_sbr_loader.py
- Mobile app screens and theme
- CLV off DraftKings line tests
- tests/test_nhl_three_way_lookahead.py
- Model trainer and prop retrains
- Prop odds next-day lookahead
- tests/test_system_health_checks.py
- NFL in-play pick writer tests
- tests/test_best_line_live.py
- tests/test_sbr_loader.py
- NCAAF college data refresh and backfill tests
- NCAAF FBS team gate tests
- NFL wind card book filter tests
- Prop no-bet rows survive tests
- Closing line value backfill job
- First signal repair tests
- tests/test_void_picks.py
- tests/test_sbr_loader.py
- Pipeline staleness watch tests
- Pregame odds read cutoff tests
- NCAAF starter-out search dataset
- NCAAF in-play gameday loop and feeds
- NFL prop market stacking research
- Scorer confidence tiers and pick labels
- tests/test_system_health_checks.py
- tests/test_sbr_loader.py
- tests/test_daily_retry.py
- Injury adjustment feature tests
- NFL prop market card publisher
- Feature map tests
- MLB live book move guard tests
- tests/test_live_book_move_guard.py
- tests/test_nfl_opener.py
- tests/test_nfl_props.py
- tests/test_weekly_catch_up.py
- tests/test_sbr_loader.py
- tests/test_umpire_ingestor.py
- tests: test_discord_notifier + test_discord_live_field
- In-play score change clock
- Prop odds book update-time tests
- NFL pick monitor
- tests/test_nhl_props.py
- MLB in-play pregame total anchor tests
- NFL odds client and opener card
- NFL pick monitor id matching
- Voided picks never rechosen tests
- Multi-book fallback response tests
- Mobile custom model builder and backtest
- NFL in-play pick writer failure tests
- Calibration schema ordering tests
- Mobile tracked bets and stake settings
- supabase/functions/revenuecat-webhook/index.ts
- supabase/functions/whop-webhook/index.ts
- tests/test_nfl_props.py
- Mobile auth session hook
- NFL backup snaps fake cursor
- tests/test_sbr_loader.py
- NHL as-of feature leak tests
- Paused bets keep real verdict tests
- NCAAF in-play fetch cadence tests
- Prop scorer tipoff test wiring
- Starter-out injury flag tests
- MLB public fade empty connection stub
- tests/test_nfl_props.py
- tests/test_nhl_three_way_lookahead.py
- NFL in-play score distribution
- Model quality database end-to-end test
- UFC ingestor fake connection
- Signal publish-on-write tests
- Player name matching and local cache
- NFL in-play prop sharp book pull tests
- tests/test_game_market_gate.py
- tests/test_system_health_checks.py
- MLB bet record audit tally
- NHL returning starter name lookup
- NBA second-model prop study
- tests/test_score_when_lines_open.py
- tests/test_score_when_lines_open.py
- tests/test_score_when_lines_open.py
- tests/test_system_health_checks.py
- NFL prop push adjustment
- tests/test_pick_integrity.py
- tests/test_score_when_lines_open.py
- MLB game features and market sweeps
- tests/test_record_one_pick_per_event.py
- WNBA prop market fake connection
- NFL in-play audit log recorder
- Umpire feature drop declaration tests
- nfl/live_model/tests: test_props + props
- NFL opener fire window tests
- Prop rows survive to tipoff
- tests/test_wnba_prop_market.py
- Weekly catch-up fake cursor
- tests/test_nfl_scored_rows.py
- NHL derivative totals model
- Mobile player log and matchup stats
- tests/test_nhl_props.py
- Publish key identity and push alerts
- NHL blocked shots prop settlement tests
- tests/test_recap_retries_a_skipped_day.py
- NBA odds archive rerun safety
- NCAAF feature engine test database
- NFL in-play feed resilience tests
- NBA prop market decision tests
- Database schema statement splitter tests
- Per-model probability calibration fitting tests
- tests/test_f5_any_book_line.py
- NBA game residual distribution
- NFL evaluation rows carry the line
- tests/test_ncaaf_prop_odds.py
- NFL prop model tests
- tests/test_ncaaf_pbp_store.py
- tests/test_heartbeat_watchdog.py
- Game injury veto gate and tests
- Record correction post tests
- Shared database connection core
- NFL prop over lean concentration study
- NHL prop priced lab
- NBA prop projection model internals
- scripts/nfl_edge_live_rush_pace.py
- NBA prop projection tests
- NBA game market feature study
- tests/test_prop_calibrated_decision.py
- NCAAF in-play pregame spread correction
- MLB batter and pitcher prop features
- tests/test_mobile_line_movement.py
- tests/test_live_calibration.py
- Mobile screen source wiring tests
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
- NFL in-play edge seasonal backtest
- scripts/nfl_edge_extreme_props.py
- scripts/nfl_edge_settlement.py
- X publisher
- tests/test_agents_contract.py
- Position vs opponent parity tests
- WNBA results and stats ingestors
- Daily pipeline runner and push notifier
- NBA box score enrichment
- X posting auth and database probes
- Prop box score backfill
- scripts/nfl_preflight.py
- Push delivery ticket tests
- NCAAF board visibility tests
- CLV math and devig functions
- NFL in-play flow validation backtest
- tests/test_decide_on_calibrated.py
- NBA prop projection lab
- NFL edge versus luck gap study
- tests/test_model_artifacts_load.py
- scripts/game_line_market_sweep.py
- Push notification deep link tests
- tests/test_pass_instrumentation.py
- tests/test_db_adapt_sql.py
- tests/test_first_signal_repair.py
- NFL in-play 2025 edge report
- tests/test_mobile_contrast_tokens.py
- NBA box score stats ingestor
- NBA second game line move tests
- NBA play-by-play game matching tests
- NFL edge research shared toolkit
- Free pick cheaper book tests
- SQL safety and pick row tests
- tests/test_nfl_live_leader_state.py
- tests/test_ncaaf_qb_ingestor.py
- NBA derivative market lab
- NBA prop model verification script
- Mobile pick category tests
- NCAAF feature engine tests
- tests/test_ncaaf_game_identity.py
- NBA second game market tests
- NBA game rule testing harness
- data/ingestors/nhl_boxscore.py
- X tweet id storage test
- NFL prop tick and NCAAF underdog calibration
- NFL kickoff wind card
- tests/test_live_game_features.py
- tests/test_ncaaf_totals_regression.py
- UFC feature engine and tests
- Source reading guard tests
- NCAAF in-play history backtest
- tests/test_ncaaf_qb_features.py
- Prop ladder interpolation tests
- Line CLV sign and orientation tests
- tests/test_mobile_team_detail.py
- NBA game harness tests
- NBA ESPN box score parsing
- EV floor replay and honest cut sweep
- MLB live game state trigger tests
- NCAAF play-by-play state builder
- Kalshi prop ladder recording
- Model calibration check tests
- Calibration fit job and health
- NCAAF college data ingestor
- NBA second game model verdict
- Historical odds backfill and first pitch
- NCAAF player stats parser tests
- scripts/nfl_live_prop_feasibility.py
- tests/test_context_budget.py
- tests/test_player_h2h_stat_values_migration.py
- tests/test_retired_models.py
- Latest line state and Citadel migration cluster tests
- tests/test_live_record_start_views.py
- Model quality degradation monitor
- tests/test_api_call_rollup.py
- NFL wind forecast persistence study
- nfl/models/opener_spread.py
- nfl/live_model/feeds: test_feed_resilience + espn
- NHL prop backtest and EV lab
- Live slate midnight date tests
- tests/test_nfl_wind_fire_window.py
- WNBA prop player feature engine
- tests/test_public_betting_ingestor.py
- NCAAF totals lead and consensus gate
- tests/test_service_role_split.py
- tests/test_http_timeout_floor.py
- Model quality public fade tests
- NFL edge cache and feed probe
- Paused model profitability assessment
- NBA second game projection tests
- Slate concentration and fade risk detection
- NHL prop odds alternate line tests
- NCAAF team game stats parsing
- NCAAF in-play ESPN feed parsing
- NCAAF CFBD ingestor tests
- NFL in-play pick writer
- tests/test_config.py
- Kalshi game market recorder
- Database URL doctor tests
- UFC fighter name resolution
- UFC fight history loader
- tests/test_team_stats_asof_invariants.py
- NBA second game projection fixtures
- Refresh pass step ordering tests
- NBA historical odds archive parser
- UFC event stats ingestor
- Mobile tracked performance checks
- tests/test_mobile_threshold_parity.py
- Sub-ten-second live path tests
- NHL derivative odds job validation tests
- tests/test_track_record_views.py
- tests/test_weekly_catch_up.py
- Discord price bound tests
- MLB public fade top-K holdout
- NBA game market gap analysis
- NFL live leader model tests
- NFL wind edge studies
- Mobile paused catalog tests
- NFL in-play prop rule and staleness studies
- Mobile sport filter tests
- tests/test_promote_calibration_job.py
- tests/test_cfbd_snapshot_leakage.py
- NBA game rule grid sections
- NCAAF outcome edge scan
- tests/test_nfl_prop_thresholds.py
- tests/test_nhl_research_job.py
- tests/test_settlement_timing.py
- UFC stats ingestor and fighters
- Mobile source checks run under node
- DataGolf ingestor and NHL SBR archive
- Paused and no-signal pick rows
- NFL odds cache import to Supabase
- tests/test_health_check_observe.py
- NBA second game quality and smoke runs
- NFL 2026 opener and wind tracker
- NFL weather edge and prop assessment
- NFL live pick writer tests
- tests/test_pick_lock_is_on_picks.py
- NCAAF opener rule scoring tests
- Env file fallback reader
- NFL prop lead ceiling capture fixture
- tests/test_team_stats_asof_invariants.py
- scripts: build_nfl_live_leader_artifact + model
- House juice minimum odds floor tests
- supabase/functions/discord-link/index.ts
- tests/test_nfl_prop_clv.py
- tests/test_prune_keeps_the_close.py
- tests/test_scoring_methods.py
- Live monitor dashboard cache and docs
- Worker job queue and retrain jobs
- Anonymous read access lockdown
- NFL in-play leader model config tests
- NCAAF in-play gameday cadence tests
- nfl/scripts/backtest_opener.py
- NFL stale card file cleanup
- tests/test_latest_odds_views.py
- Multi-book odds fetch tests
- Module entrypoint guard tests
- NBA schedule ingestor and tests
- tests/test_nfl_prop_settle_name_fallback.py
- Recap waits for NFL box scores
- tests/test_transaction_pooler.py
- NBA historical odds archive parsing
- NBA second game world and panel builder
- ESPN versus DraftKings freshness check
- NCAAF in-play underdog correction fit
- supabase/functions/sharpsports/index.ts
- UFC CSV download cache
- NBA second game grid verdict tests
- tests/test_worker_deps.py
- Sportsbook direct reachability probes
- NBA player availability reallocation
- scheduler.py
- Dashboard queries and SQL file runner
- Mobile player stat handoff tests
- Team stats as-of snapshot checks
- tests/test_mobile_stat_labels_match_the_server.py
- tests/test_ncaaf_fcs_visitor_names_migration.py
- tests/test_nfl_prop_unstarted_clear.py
- NBA game model lab and NFL staking
- NFL live moneyline and total pricing tests
- tests/test_savant_freshness.py
- tests/test_scorer_nfl_prop_like_escape.py
- NBA game market fair pricing
- NCAAF college data verification script
- In-play model holdout comparison
- Outbound API request probe recorder
- NHL historical odds archive ingestor
- CLV no-vig close capture tests
- Odds pruning keeps openers
- Mobile stat segment tests
- NFL opener cut sweep by book
- tests/test_clear_unauthorized_auto_pauses_migration.py
- Declared worker job validation tests
- tests/test_ncaaf_se_louisiana_alias_migration.py
- NCAAF starter-out grading study
- tests/test_overnight_polling.py
- NCAAF weather and wind totals study
- NFL Kalshi price history fetch
- NHL totals lab
- NCAAF situational spot search
- NFL prop two-sharp-book research
- tests/test_claude_rules_split.py
- tests/test_db_setup.py
- tests/test_dedupe_opening_signals.py
- Direct sportsbook feed pollers
- NFL prop odds ingestor
- tests/test_pbp_backfill_resilience.py
- NCAAF in-play loop cadence tests
- NFL wind forecast validation
- NBA second game line move fit
- NFL prop universe model rate summary
- Mobile bankroll copy and behaviour tests
- SQL percent escaping tripwire
- tests/test_game_log_backfill_skip.py
- NCAAF line move spots
- NBA second game luck study
- tests/test_prompt_reads_thresholds.py
- tests/test_system_health_meta_steps.py
- NBA period scores ingestor and tests
- scripts/render_brand_icons.py
- Dashboard rule model tests
- supabase/functions/stripe-webhook/index.ts
- tests/test_drop_voided_nfl_wind_opening_signals_migration.py
- tests/test_mobile_neutral_signal_label.py
- NFL prop kickoff lead ceiling
- Discord community size stats
- tests/test_scorer_commits_per_game.py
- NCAAF scoreboard yardline parsing tests
- Supabase connection credential probe
- In-play honest cut sweep
- NBA game market decision ordering
- tests: test_wnba_availability + wnba_availability
- NCAAF prop market rule sweep
- Market coverage probe tests
- supabase/functions/sharpsports-webhook: index + index
- Pipeline watch silent job finding
- supabase/functions/stripe-checkout/index.ts
- tests/test_book_list_budget.py
- Opening vs closing strategy analysis
- NBA game market lab report
- NCAAF in-play DraftKings qualifying gate
- NBA game market blind bet grading
- SBR odds CSV loader
- NCAAF in-play model re-sweep
- NHL regulation own probability tests
- mobile/scripts/verify_a11y.ts
- Football in-play game state
- NHL prop backtest shared names
- tests/test_demote_ncaaf_over_under_platt.py
- MLB runline retrain sweep job
- tests/test_discord_post_one_pick_migration.py
- tests/test_game_scorer_spares_nfl_props.py
- Mobile NHL look-ahead tests
- NFL in-play model backtest states
- tests/test_mobile_ota_self_update.py
- NBA second game emit and bootstrap tests
- NBA archive odds row shaping
- NFL in-play 2024 pooled tables
- MLB totals public fade card
- NFL research files backup to Supabase
- UFC event page parsing
- Discord stale pause empty-set alert
- Discord paused model quiet test
- Pipeline watch post ledger
- Multi-book odds named book reads
- NFL in-play snapshot backup tests
- Scorer keeps off-DraftKings priced bets tests
- Drop voided NFL prop signals tests
- NFL in-play pick date and resolution tests
- NFL live publish refusal guard
- NFL in-play per-player lock test
- Pipeline watch run findings
- Paused model view migration tests
- UFC fighter page parser
- Pipeline watch alert posting
- tests/test_team_stats_asof_invariants.py
- tests/test_team_stats_asof_invariants.py
- tests/test_team_stats_asof_invariants.py
- tests/test_weekly_catch_up.py
- Mobile stats filter checks
- NHL goalie line helpers
- Team stats rebuild and verify
- tests/test_live_orchestrator.py
- Live money no record-only tests
- NBA second game price cache checks
- tests/test_team_stats_asof_invariants.py
- NHL goalie name lookup as-of
- NFL live pick announcer
- First signal same-bet comparison
- Mobile accessibility verify script
- Market handicap feature tests
- mobile/scripts/verify_a11y.ts
- mobile/scripts/verify_a11y.ts
- Monitoring dashboard test server
- NCAAF school name mascot matching
- Prop CLV and SQL escaping tests
- mobile/scripts/verify_a11y.ts
- NCAAF margin and totals evaluation
- NCAAF college data call budget test
- Team stats verify alias test
- NBA Pinnacle no-vig close
- ncaaf_live/tests/test_serve.py
- Global EV floor prop card tests
- Mobile script test runner via Node
- NCAAF scoreboard mascot stripping
- NCAAF game-day uptime safety test
- NCAAF CFBD line bookmaker label
- NCAAF pregame calibration artifact fixture
- Football play-by-play state finalizing
- Restore first BET signals step
- Worker service role split
- scripts/nfl_edge_preregistered_2026.py
- Restored pick paused note
- Multi-book odds pruning safety tests
- tests: test_player_positions + player_positions_ingestor
- mobile/scripts/verify_a11y.ts
- Pipeline watch credit burn checks
- Mobile prop board market set
- Pipeline pass watch findings
- NBA archive moneyline timing checks
- NBA game clock parsing
- NBA prop model lab
- Pipeline watch ledger failure test
- MLB totals public fade tests
- NBA play-by-play ingestor
- Supabase schema tables
- mobile/app.json
- mobile/package.json
- Games and latest odds views
- Player game log RPCs
- Picks and public track record views
- Latest line state tables
- mobile/tsconfig.json
- NBA 2026-27 rebuild write-up
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
- Mobile development dependencies
- Game weather issued migration
- Odds API quota migration
- Parlay correlations migration
- Pick placement checks migration
- NBA play-by-play lineup docs
- docs/rules_evidence.md
- Probability calibration and EV floors docs
- NFL game lines model write-up
- Performance gauging and monitoring docs
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
- NFL in-play rushing and passing prop findings
- mobile/docs/UX_REVIEW.md
- Daily model-quality monitor and MLB fade docs
- NCAAF and NFL model search write-ups
- docs/sports: ufc + golf
- mobile/docs/BILLING.md
- .claude/agents: frontend-ux-designer + CLAUDE
- .claude/rules/picks-and-publishing.md
- .claude/rules/model-updates.md
- docs/signal_timing.md
- mobile/docs/DISCORD_LINKING.md
- docs/live_betting.md
- In-play backtest findings docs
- NFL model bundle restore docs
- docs/sports/wnba.md
- mobile/docs/AUTHENTICATION.md
- .claude/rules/frontend.md
- docs/health_checks.md
- docs/retrain_2026_plan.md
- docs/reviews/2026-09-07-nfl-props-deep-dive.md
- docs/market_coverage.md
- (root): pr-ci + requirements
- docs/nfl_props_model.md
- Signal-flip push and privacy docs
- Opening-signal shadow track docs
- docs/game_injury_gate.md
- NFL wind totals runbook and staking
- mobile/docs/BILLING.md
- docs/testing.md
- CLAUDE.md
- docs: nhl_market_lab + nhl_clv_ev_assessment
- NFL opener sharp-vs-soft findings

## God Nodes (most connected - your core abstractions)
1. `get_connection()` - 596 edges
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
- `2. Data used (all in Supabase)` --references--> `odds()`  [INFERRED]
  docs/nba_models_2026.md → tests/test_latest_line_state.py
- `3. The market grid` --references--> `odds()`  [INFERRED]
  docs/nba_models_2026.md → tests/test_latest_line_state.py
- `Things a reader should know` --references--> `shot_value()`  [INFERRED]
  docs/nba_pbp_stints.md → data/ingestors/nba_stints.py
- `4.3 Player props — one rule ships` --references--> `run_nba_prop_window()`  [INFERRED]
  docs/nba_models_2026.md → scheduler.py
- `Tables (all worker-only, locked down where they are created)` --references--> `diagnostics()`  [INFERRED]
  docs/nba_pbp_stints.md → scripts/nfl_edge_inplay_2025.py

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

## Communities (875 total, 195 thin omitted)

### Community 0 - "ESPN injury ingestor"
Cohesion: 0.03
Nodes (38): TestCoreTeamsFallback, _athlete_name(), _compute_return_ramp(), _espn_team_ids(), fetch_espn_injuries(), _fetch_espn_team_injuries(), fetch_mlb_transactions(), _fetch_nba_espn_team_ids() (+30 more)

### Community 1 - "Mobile stats board"
Cohesion: 0.01
Nodes (339): P, TouchSet, errorKind, gameStatus, HitMode, HitRate, HitRateBandName, RulerHold (+331 more)

### Community 104 - "Record correction posts to Discord"
Cohesion: 0.07
Nodes (26): LedgerUnread, Conn, delete_custom_record_post(), _jump(), _place(), _publish(), publish_full_record(), publish_full_record_standard() (+18 more)

### Community 11 - "Mobile stats odds and line legs"
Cohesion: 0.04
Nodes (77): PlayerPropQuote, GameLineLegSpec, GameLineMarket, LineSheetInput, LineSide, PropLineLegSpec, LegBookPrice, PropLineLike (+69 more)

### Community 113 - "tests/test_nfl_live_leader_gameday.py"
Cohesion: 0.05
Nodes (33): FakeClient, FakeClock, FakeConn, FakeFeed, _Rows, art(), live_state(), quote_payload() (+25 more)

### Community 114 - "nfl_live_leader/gameday.py"
Cohesion: 0.05
Nodes (33): _Unset, Cadence, GameContext, LiveOddsFeed, Quote, LiveState, release_read(), parse_book_ts() (+25 more)

### Community 115 - "tests/test_calibration_promotion.py"
Cohesion: 0.07
Nodes (26): FakeConn, eligibility_clause(), load_calibrations(), maps_materially_differ(), promote(), _payload(), _row(), test_a_broken_table_is_identity_maps_not_an_exception() (+18 more)

### Community 116 - "tests/test_score_off_any_book_line.py"
Cohesion: 0.08
Nodes (33): _FakeConn, _fallback_line_quote(), _cut(), _on(), _pick(), _row(), _sql_const(), _src() (+25 more)

### Community 118 - "Mobile daily results calendar"
Cohesion: 0.05
Nodes (58): CustomModelStats, Acc, DailyResults, DayGameSummary, ModelDayStats, ScopedDailyResults, SportDayBreakdown, addMonths() (+50 more)

### Community 12 - "Mobile pick filters and sorting"
Cohesion: 0.02
Nodes (147): P, ActivePill, Props, reachFrame, DateOption, DayRow, SelectableGame, modelCategory (+139 more)

### Community 120 - "tests/test_ncaaf_alias_scores.py"
Cohesion: 0.08
Nodes (32): _FakeConn, _FakeCursor, alias_score_updates(), _date_or_none(), mirror_scores_to_alias_rows(), mirror_stored_finals(), _cfbd(), _row() (+24 more)

### Community 121 - "tests/test_prop_alternate_lines.py"
Cohesion: 0.03
Nodes (46): _Conn, _Resp, alt_markets_due(), backfill_mlb_prop_odds(), _backfill_one_date(), backfilled_dates(), ensure_book_last_update_column(), _get_event_props() (+38 more)

### Community 122 - "Mobile error and not-found states"
Cohesion: 0.04
Nodes (52): CountInput, DetailBody, LoadBody, LoadInput, D(), K(), P(), R() (+44 more)

### Community 123 - "tests/test_backtester.py"
Cohesion: 0.07
Nodes (9): TestCalibrationError, TestComputeBacktestSummary, TestEvaluateResult, TestGoLiveGateConstants, TestIterSides, _calibration_error(), compute_backtest_summary(), _evaluate_result() (+1 more)

### Community 124 - "NHL prop expected value lab"
Cohesion: 0.13
Nodes (6): TestRegimeOrder, regime(), _cand(), _league(), _name(), test_the_whole_script_runs_on_a_synthetic_league()

### Community 125 - "nfl/live_model/feeds/odds_live.py"
Cohesion: 0.07
Nodes (18): CreditBudgetExceeded, CreditMeter, LiveOddsClient, Quote, JsonlRecorder, best_price(), parse_events(), _parse_ts() (+10 more)

### Community 127 - "NHL props nightly card"
Cohesion: 0.07
Nodes (17): TestFourNhlPropBetsANight, TestWhoThePlayerIs, step_nhl_prop_scoring(), candidates(), draftkings_at(), existing_picks(), games_with_a_prop_bet(), identities() (+9 more)

### Community 129 - "NBA prop market lab"
Cohesion: 0.09
Nodes (44): NBTable, add_units(), assemble(), best_per_key(), boot_ci(), build_quotes(), candidates_from(), choose_floor() (+36 more)

### Community 13 - "Discord pick notifier tests"
Cohesion: 0.02
Nodes (109): _Resp, _cand(), _et_now_iso(), _live_row(), _live_setup(), _no_prod_threshold_sync(), _recap_row(), _restate_env() (+101 more)

### Community 131 - "nfl/live_model/tests/test_backup_snaps.py"
Cohesion: 0.12
Nodes (22): _FakeConn, back_up(), _connect(), digest(), _flush(), iter_files(), main(), _mb() (+14 more)

### Community 135 - "mobile/scripts: verify_book_links + verify_betslip_combine"
Cohesion: 0.06
Nodes (37): betslipCombineKind, combineBetMgm(), combineBetslipLinks(), combineCaesars(), combineDraftKings(), combineEspnBet(), combineFanDuel(), fanDuelPairs() (+29 more)

### Community 137 - "NBA official injury report ingestor"
Cohesion: 0.03
Nodes (88): Fetcher, Report, _Conn, _Cur, _DatesConn, _Fetcher, _PdfFetcher, _all_slots() (+80 more)

### Community 14 - "Mobile data queries and shared types"
Cohesion: 0.03
Nodes (138): Props, FighterSide, Props, Props, LivePicksState, Args, PlayerNewsState, PropContext (+130 more)

### Community 140 - "mobile/scripts/verify_contrast_tokens.ts"
Cohesion: 0.05
Nodes (40): Pair, code(), lum(), noGreen(), over(), ratio(), read(), readUtf8() (+32 more)

### Community 141 - "models/nhl_props.py"
Cohesion: 0.15
Nodes (16): Spec, _attach_teams(), build_goalie_frame(), build_skater_frame(), _ew(), excess_variance(), expected_value(), fit() (+8 more)

### Community 142 - "tests/test_health_pregame_prices_current.py"
Cohesion: 0.08
Nodes (31): _Conn, _at(), _game(), _row(), _run(), test_a_broken_feed_read_is_an_error_and_rolls_back(), test_a_broken_query_is_an_error_and_rolls_back(), test_a_cancelled_fight_and_a_pulled_game_do_not_raise_the_alarm() (+23 more)

### Community 143 - "Pick lock after settlement tests"
Cohesion: 0.09
Nodes (21): _SqliteShim, _game(), _pick(), _survivors(), test_a_bet_is_never_dropped_for_an_earlier_no_signal(), test_a_dead_zone_prop_row_locks_too(), test_a_final_game_is_not_a_scoring_target(), test_a_game_with_no_score_is_still_scoreable() (+13 more)

### Community 144 - "NBA game line move study"
Cohesion: 0.04
Nodes (43): Data, _counted_schedule(), from_cache(), game_schedule_features(), haversine_miles(), home_bases(), _offsets(), previous_game_load() (+35 more)

### Community 145 - "NBA prop market card publisher"
Cohesion: 0.05
Nodes (41): NbaPropBet, NbaPropDecision, Roster, _PublishConn, coherent(), fair_under(), fetch_times(), find_bets() (+33 more)

### Community 146 - "tests/test_mlb_game_market.py"
Cohesion: 0.08
Nodes (24): GameMarketBet, _SlateConn, find_spread_bets(), _is_runline(), pick_rows(), slate(), test_mlb_market_cards_drop_a_bet_under_the_floor(), _game_rows() (+16 more)

### Community 149 - "Mobile sign-in and auth"
Cohesion: 0.10
Nodes (35): AuthCallback, AuthDisabledError, AuthProvider, PlayerSearchResult, LinkedAccount, SyncedBet, SyncResponse, SyncSummary (+27 more)

### Community 150 - "Threshold review report tests"
Cohesion: 0.04
Nodes (37): _Conn, _DdlConn, _DdlRes, _is_paused(), _quiet(), rule_only(), _slate(), test_a_failed_lock_down_does_not_lose_the_table() (+29 more)

### Community 152 - "Idle read transaction tests"
Cohesion: 0.06
Nodes (20): ViewMigrationResult, _Rec, run_forever(), _apply_one(), apply_view_migrations(), _is_transient_lock_error(), _with_lock_timeout(), _flat() (+12 more)

### Community 154 - "Game odds ingestor and historical backfill"
Cohesion: 0.03
Nodes (44): TestEveryOtherSportStillMintsItsOwn, TestNflResolvesOntoTheSchedule, TestTheResolverFailsClosed, TestResolveGameId, TestThreeWayMarketKey, TestFilterUfcPhantom, TestIsKnownUfcMatchup, resolve_nfl_game_id() (+36 more)

### Community 155 - "tests/test_prop_box_scores.py"
Cohesion: 0.09
Nodes (18): GradeConn, ScriptConn, ensure_prop_box_scores(), missing_prop_games(), _pick(), test_a_logged_game_is_not_fetched_and_a_goalie_gap_is(), test_a_non_timeout_prop_error_rolls_back_and_raises(), test_a_probe_error_that_is_not_a_timeout_raises_after_rollback() (+10 more)

### Community 156 - "NBA game model prop feature tests"
Cohesion: 0.06
Nodes (40): _Stop, _box(), _g(), _games(), _inj(), _model(), _props(), _run() (+32 more)

### Community 158 - "Best line and best-price decision tests"
Cohesion: 0.04
Nodes (49): FakeConn, TwoOrientationConn, FakeConn, _best_fields(), _best_game_price(), _best_game_price_one(), _best_of(), _best_prop_price() (+41 more)

### Community 160 - "Mobile Discord linking and access"
Cohesion: 0.11
Nodes (36): AccessState, useAccess, useEntitlement, FunctionResponse, LinkResult, AccessRow, AccessSource, DiscordCallback (+28 more)

### Community 162 - "tests/test_ddl_guard.py"
Cohesion: 0.07
Nodes (17): GuardConn, _ddl(), _dk_direct_feed(), _is_guarded(), _modules_with_write_time_ddl(), _run_ledger(), test_ddl_still_runs_on_a_database_that_needs_it(), test_every_write_time_ddl_module_goes_through_the_guard() (+9 more)

### Community 164 - "tests/test_nfl_opener.py"
Cohesion: 0.11
Nodes (10): TestFreshNumberLabel, TestHeldMinutes, TestModelCardSplit, _giants_board(), _giants_prior_at_2129(), _giants_sched(), _obs(), _row() (+2 more)

### Community 165 - "NHL stats and probable goalies ingest"
Cohesion: 0.02
Nodes (64): TestLogRowBuilders, TestGoalieLookup, TestNoHollowTeamRowBeforeTheFirstGame, TestSeasonLabel, _upsert_savant_stats(), _default_fetch(), fetch_espn_nhl_probables(), _https() (+56 more)

### Community 17 - "Discord pick posting and void notices"
Cohesion: 0.03
Nodes (49): Ledger, DiscordVoidRejected, test_a_malformed_timestamp_drops_the_stamp_rather_than_raising(), test_american_odds_formatting(), test_delete_posted_degrades_when_the_column_is_missing(), test_game_time_renders_in_eastern(), test_matchup_is_sport_aware(), test_prob_only_picks_fall_back_to_the_settlement_price() (+41 more)

### Community 170 - "NBA game model luck feature tests"
Cohesion: 0.05
Nodes (39): _Stop, _against_bet(), _f6c_inputs(), _games_for_standings(), _gs(), _market_pricing(), _one_game_data(), _pair() (+31 more)

### Community 174 - "tests/test_publisher_lock.py"
Cohesion: 0.05
Nodes (32): _FakeConn, _FakeResult, _Conn, _Result, _row(), _setup(), test_a_pick_for_tomorrow_is_announced_under_TOMORROWS_date(), test_dry_run_posts_nothing_and_ledgers_nothing() (+24 more)

### Community 175 - "tests/test_dk_direct_feed.py"
Cohesion: 0.09
Nodes (22): _Conn, _game_id_for(), _row_for(), _seen_key(), _rec(), test_a_line_move_is_a_new_quote(), test_a_market_we_do_not_understand_is_dropped_not_guessed(), test_a_price_move_is_a_new_quote() (+14 more)

### Community 177 - "tests/test_credit_budget.py"
Cohesion: 0.06
Nodes (23): CreditBudget, _Conn, daily_burn(), latest_remaining(), plan_credit_budget(), _burn_conn(), _plan(), test_a_billing_reset_is_not_a_refund() (+15 more)

### Community 18 - "Mobile model catalog and thresholds"
Cohesion: 0.02
Nodes (195): Case, EquityPoint, Props, NavRef, friendlyError, BetTypeChoice, BetTypeOption, BetTypeSlot (+187 more)

### Community 180 - "NHL market-anchored moneyline model"
Cohesion: 0.10
Nodes (17): _Fixed, _GamesConn, decision_window(), _logs(), _served(), test_a_later_result_cannot_reach_an_earlier_game(), test_a_matinee_closes_the_window_at_puck_drop(), test_a_missing_input_skips_the_game() (+9 more)

### Community 181 - "Worker job queue run tests"
Cohesion: 0.06
Nodes (23): _Conn, _DedupeConn, _fake(), test_a_busy_queue_claims_nothing(), fetchone(), test_a_declared_job_is_queued_once_however_often_it_is_read(), test_a_failing_job_is_requeued_until_the_attempt_cap(), _boom() (+15 more)

### Community 186 - "NFL wind and opener publisher"
Cohesion: 0.09
Nodes (16): _LockConn, TestNoneRowNeverLocks, _changed(), _clear_scored_row(), _flush_board_safe(), _flush_snapshots_safe(), latest_eval_rows(), _lock_model() (+8 more)

### Community 189 - "Settlement and self-heal tests"
Cohesion: 0.04
Nodes (56): _FakeStatsapi, _SqliteShim, call_in_savepoint(), statement_timeout(), test_it_settles_as_totals_off_the_final_score(), conn(), _game(), _pick() (+48 more)

### Community 19 - "NHL blocked shots prop card"
Cohesion: 0.08
Nodes (18): TestTheCard, TestWhoThePlayerIs, bs_implied(), candidates(), identities(), latest_quotes(), main(), pick_rows() (+10 more)

### Community 191 - "Prop market devig and bet finding"
Cohesion: 0.02
Nodes (80): MarketBet, TestMarketRelative, TestNaNIsAbsent, _Conn, scoring_method(), _parse_iso_ts(), devig(), find_bets() (+72 more)

### Community 196 - "tests/test_ungraded_model_performance.py"
Cohesion: 0.08
Nodes (12): FakeConn, test_perf_reads_the_matview_not_the_expensive_view(), test_roster_reports_a_registered_but_untrained_model(), _second_arm(), _sql(), test_a_fully_unpriced_recovered_model_reports_no_roi(), test_a_recovered_row_still_reports_roi_over_the_priced_bets(), test_both_arms_stay_inside_the_settled_bet_gate() (+4 more)

### Community 198 - "mobile/scripts/verify_push.ts"
Cohesion: 0.08
Nodes (30): PushState, ForcedOnlyReason, PushDiagnosis, PushFailureReason, TestPushResult, reasonOf(), diagnosePushError(), errorText() (+22 more)

### Community 199 - "Prop price pregame cutoff tests"
Cohesion: 0.05
Nodes (26): FakeConn, _StubConn, resolve_feed_name(), _get_prop_dk_odds(), _latest_dk_prop_row(), test_accented_roster_name_matches_the_flat_feed_name(), test_ambiguity_is_a_miss_not_a_guess(), test_an_unlisted_player_is_still_a_miss() (+18 more)

### Community 2 - "Mobile markets and formatting"
Cohesion: 0.02
Nodes (240): Row, Props, IoniconName, clvBetQuote, ClvBetRow, ClvBookRow, DecisionPriced, gameStartState (+232 more)

### Community 20 - "Threshold and EV floor sweeps"
Cohesion: 0.04
Nodes (28): _ProbeConn, analyse(), split(), _basis(), _cut(), fetch(), main(), analyse() (+20 more)

### Community 200 - "Monitoring registry and probe tests"
Cohesion: 0.07
Nodes (23): _Resp, _credits_from(), classify(), paid_apis(), _get(), _perf_rows(), test_an_unpriced_model_reports_no_roi(), test_billing_reset_reports_no_credits_rather_than_a_negative() (+15 more)

### Community 203 - "tests/test_nhl_asof.py"
Cohesion: 0.20
Nodes (3): GoalieBook, TestGoalieAsOf, _g()

### Community 204 - "NFL prop features and backtests"
Cohesion: 0.03
Nodes (51): LazyConnection, TestPlaceboCannotSilentlyNotHappen, TestPriceMath, TestYardageDistribution, _add_features(), build_nfl_prop_scoring_rows(), build_nfl_prop_training_dataset(), _cols() (+43 more)

### Community 205 - "NFL in-play game state feed"
Cohesion: 0.12
Nodes (18): CoreClient, EventMeta, _abbr(), game_seconds(), https(), _int(), is_admin_play(), is_conversion_play() (+10 more)

### Community 206 - "MLB in-play inning gate replay"
Cohesion: 0.03
Nodes (88): GameClock, build_mlb_game_features(), _get_bullpen_workload(), _get_game_weather(), _get_mlb_pitcher_stats(), _get_mlb_team_stats(), _rolling_runs_from_games(), _season_runs_by_location() (+80 more)

### Community 209 - "data/ingestors/nfl_inplay_history.py"
Cohesion: 0.16
Nodes (22): Budget, buy_halftime(), buy_inplay(), events_for(), _floor5(), _get(), halftime_requests(), halftime_windows() (+14 more)

### Community 211 - "Mobile bankroll setting store"
Cohesion: 0.06
Nodes (69): BankrollCheck, BankrollCommit, BankrollPatch, BankrollRead, BankrollSettings, KeyValueStore, NumberSeparators, Part (+61 more)

### Community 212 - "Mobile in-app feedback flow"
Cohesion: 0.10
Nodes (32): FeedbackCategory, FeedbackMessage, FeedbackSender, FeedbackStatus, FeedbackThread, Validation, emit(), refreshFeedbackUnread() (+24 more)

### Community 214 - "NHL props per-game limit tests"
Cohesion: 0.16
Nodes (4): TestInsertOnce, TestTheLimitPerGame, limit_per_game(), publish()

### Community 215 - "Pick scorer and bet sizing"
Cohesion: 0.02
Nodes (109): DBConnection, TestAmericanToImpliedProb, TestMissingStarterGate, today_et(), pregame_cutoff_sql(), build_golf_scoring_features(), load_sport_injury_index(), american_to_implied_prob() (+101 more)

### Community 217 - "NCAAF in-play engine and pick lock"
Cohesion: 0.05
Nodes (24): GameContext, LiveEngine, FakeConn, _Rows, write_picks(), expected_value(), _is_paused(), db() (+16 more)

### Community 22 - "NBA prop projection card"
Cohesion: 0.06
Nodes (37): ProjectionBet, Plan, step_mlb_total_public_fade(), step_nba_prop_project(), slate(), backfill_official(), decided_games(), ensure_tables() (+29 more)

### Community 220 - "tests/test_db_reconnect.py"
Cohesion: 0.09
Nodes (16): _Conn, _Cursor, _is_write(), _lost(), test_a_committed_transaction_is_clean_again(), test_a_lost_connection_with_uncommitted_writes_raises_connection_lost(), test_a_read_on_a_lost_connection_reconnects_and_retries(), test_a_statement_timeout_is_not_a_lost_connection() (+8 more)

### Community 222 - "NHL derivative totals card tests"
Cohesion: 0.13
Nodes (8): _Meter, _Resp, main(), run(), _markets(), test_card_writes_nothing_and_the_pipeline_does_not_call_it(), test_parser_splits_team_totals_and_keeps_every_alternate_line(), test_pull_buys_the_game_with_no_credit_stop()

### Community 223 - "tests/test_live_lock.py"
Cohesion: 0.10
Nodes (21): FakeConn, _Rows, _existing_live_lanes(), _lane_signature(), _write_live_picks(), _locked_live_lanes(), test_the_lane_signature_carries_the_deciding_price(), _log_lines() (+13 more)

### Community 225 - "tests/test_refresh_retry.py"
Cohesion: 0.15
Nodes (22): RefreshRun, _decide(), _done(), _run(), test_a_failed_view_migration_fails_the_step(), test_a_pass_that_finished_with_failed_steps_ran_its_chain(), test_a_redeploy_between_passes_replaces_nothing(), test_a_restart_loop_does_not_buy_odds_on_every_boot() (+14 more)

### Community 226 - "NBA results and box score ingestor"
Cohesion: 0.06
Nodes (21): PgStore, PlayerResolver, box_is_complete(), build_dnp_rows(), build_log_rows(), fallback_id(), ingest_nba_results(), main() (+13 more)

### Community 228 - "NBA results ingestor tests"
Cohesion: 0.09
Nodes (24): _Conn, _ESPN, FakeStore, _FixedNow, _game(), _resolver(), _run(), test_a_different_stored_score_is_never_overwritten() (+16 more)

### Community 23 - "NBA second game calibration fitting"
Cohesion: 0.14
Nodes (13): Last, actuals(), apply_models(), calib_design(), f5_design(), fit_calibration(), fit_f5(), league_total() (+5 more)

### Community 230 - "tests/test_local_cache_is_additive.py"
Cohesion: 0.12
Nodes (8): _FakeConn, cached(), _frame(), test_a_first_ever_pull_still_works(), test_a_pull_that_lost_rows_keeps_them(), test_an_unreadable_cache_refuses_rather_than_overwrites(), test_rows_present_in_both_are_kept_once(), test_the_pull_ITSELF_is_additive()

### Community 231 - "tests/test_calibration_check_coverage.py"
Cohesion: 0.12
Nodes (17): _Shim, _bet(), _calibration_results(), db(), _graded(), _make_db(), _only(), _promote() (+9 more)

### Community 233 - "tests/test_book_team_map.py"
Cohesion: 0.11
Nodes (15): _Conn, abbr_from_team_string(), resolve_game_id(), split_matchup(), test_a_non_mlb_sport_is_refused_rather_than_guessed(), test_a_string_with_no_at_sign_is_refused(), test_a_unique_game_resolves(), test_an_ambiguous_game_resolves_to_none() (+7 more)

### Community 234 - "tests/test_team_board_cache.py"
Cohesion: 0.08
Nodes (11): _Conn, _Cursor, refresh_team_board_cache(), team_board_pairs(), team_board_seasons(), _cols(), test_every_team_sport_gets_last_this_and_next_year(), test_one_failing_pair_does_not_stop_the_rest() (+3 more)

### Community 236 - "NBA second game model fitting"
Cohesion: 0.11
Nodes (13): EW, Model, build_models(), build_state(), fit_hyper(), fit_play(), hyper_seasons(), league_rates() (+5 more)

### Community 237 - "Mobile settings and sportsbook connection"
Cohesion: 0.09
Nodes (32): ConnectionMap, providerMeta, SportsbookConnection, SportsbookProvider, Nav, DiscordLinkModal(), StatePickerSheet(), load() (+24 more)

### Community 238 - "nfl/live_model/tests/test_rush_attempt_pace.py"
Cohesion: 0.07
Nodes (21): Read, pace_ratio(), _sigmoid(), under_prob(), _price(), test_a_line_he_has_already_passed_is_not_a_live_proposition(), test_a_missing_accrued_count_is_refused_not_treated_as_zero(), test_a_reachable_over_is_declined_rather_than_faded() (+13 more)

### Community 239 - "tests/test_nfl_poll_fast_silence.py"
Cohesion: 0.11
Nodes (15): FakeConn, publish_board(), _append_board(), _body(), _row(), _sent(), _setup(), test_a_half_written_last_row_waits_for_the_next_tick() (+7 more)

### Community 24 - "NHL moneyline and market research scripts"
Cohesion: 0.03
Nodes (114): OffsetLogit, apply_calibration(), accuracy(), first_games(), logloss(), main(), sweep(), units() (+106 more)

### Community 242 - "data/ingestors/ncaaf_inplay_history.py"
Cohesion: 0.07
Nodes (33): _Conn, _StubEngine, _blank_row(), budget_for(), calls_in(), _floor5(), _get(), _iso() (+25 more)

### Community 243 - "MLB and WNBA stats ingestors and pitcher rebuild"
Cohesion: 0.04
Nodes (30): _FakeConn, TestProbablesReachTomorrow, backfill_bullpen_stats(), backfill_f5_scores(), backfill_mlb_stats(), backfill_pitcher_stats(), backfill_player_handedness(), _build_pitcher_rows() (+22 more)

### Community 244 - "tests/test_weather_lookahead.py"
Cohesion: 0.06
Nodes (17): _Resp, TestTheHourIsTheGamesOwn, TestTheRequestCoversTheTargetHour, TestTheStoreReadsTheStartTime, TestTheUmpireLandsOnEveryPass, backfill_weather(), _celsius_to_f(), fetch_and_store_weather_for_date() (+9 more)

### Community 245 - "tests/test_nhl_asof.py"
Cohesion: 0.15
Nodes (4): TeamBook, TestBlendedTeamInputs, TestTeamRatesAsOf, _r()

### Community 247 - "tests/test_dk_freshness_parse.py"
Cohesion: 0.11
Nodes (18): _FakeConn, _FakeResult, _american(), parse_dk_payload(), run(), _store(), _payload(), test_a_half_priced_market_is_dropped_rather_than_half_recorded() (+10 more)

### Community 248 - "NBA historical odds archive buyer"
Cohesion: 0.04
Nodes (47): ConnectionLost, Meter, _Ledger, _Meter, _Resp, TestOddsFeedTeamNames, connection_lost(), buy_derivatives() (+39 more)

### Community 249 - "models: slate_concentration + test_slate_concentration"
Cohesion: 0.15
Nodes (15): SlateConcentration, apply_slate_guard(), apply_slate_concentration_guard(), _attr(), _edge_of(), _is_bet(), measure_side_concentration(), _side_of() (+7 more)

### Community 251 - "View migration lock handling tests"
Cohesion: 0.07
Nodes (25): _Conn, _Deadlock, _LockTimeout, _StatementTimeout, _Syntax, execute(), _before(), _code() (+17 more)

### Community 254 - "Publisher and injury fetch test fakes"
Cohesion: 0.05
Nodes (8): _R, test_the_prop_fetch_never_buys_a_game_it_was_not_given(), execute(), test_a_429_rate_limit_is_not_reported_as_posted(), test_a_non_2xx_is_not_reported_as_posted(), test_a_reply_carries_the_parent_id(), _post(), test_a_success_returns_the_tweet_id()

### Community 256 - "tests/test_ncaaf_search_features.py"
Cohesion: 0.07
Nodes (28): AdjRatings, blended_rating(), build_adjusted_ratings(), build_prior_season_ratings(), fit_opponent_adjustment(), load_fbs_membership(), load_team_games(), pool_fcs_opponents() (+20 more)

### Community 257 - "NCAAF walk-forward model search"
Cohesion: 0.05
Nodes (42): FoldResult, features_for(), _apply_calibration(), exponential_recency_weights(), _logit(), make_ensemble(), fit_predict(), make_lgbm() (+34 more)

### Community 258 - "Deploy checks and worker job queue"
Cohesion: 0.07
Nodes (17): _Conn, test_a_declared_job_carries_its_run_after(), test_a_failing_check_raises_so_the_queue_announces_it(), test_a_job_can_only_name_a_registered_check(), test_enqueue_rejects_a_naive_run_after(), test_enqueue_stores_run_after(), test_every_check_is_read_only(), test_the_claim_waits_for_run_after() (+9 more)

### Community 26 - "Mobile teams board and team detail"
Cohesion: 0.04
Nodes (112): Sport, NextGame, Section, TeamLineQuote, Tier, FormGame, FormSummary, headToHead (+104 more)

### Community 265 - "Best line threshold sweep"
Cohesion: 0.10
Nodes (12): _Conn, american_to_decimal(), units_at(), _row(), test_a_better_price_pays_more_than_the_dk_price(), test_a_loss_costs_one_unit_at_every_price(), test_a_push_is_flat(), test_a_retired_model_is_never_recommended_a_cut() (+4 more)

### Community 268 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.09
Nodes (8): TestBuildScoredRows, TestPickEmLabel, TestPreflightLockChecks, TestQualifyingRowIsNotANoneRow, _american_to_prob(), build_scored_rows(), _fmt_spread(), _num()

### Community 269 - "NCAAF college data ingest tests"
Cohesion: 0.07
Nodes (8): _GamesConn, _TeamsConn, test_ingest_games_retains_a_historical_utc_id_and_uses_et_for_a_new_row(), fake_get(), test_ingest_pulls_fbs_then_everyone_and_fbs_rows_win(), test_ingest_retries_everyone_without_a_year_if_the_season_filter_is_empty(), test_prior_context_tolerates_missing_talent_and_returning(), test_weekly_snapshot_build_aborts_on_failed_fetch()

### Community 27 - "Mobile parlay builder and correlation"
Cohesion: 0.02
Nodes (141): Props, ParlayRestorePayload, ResolvedSlip, LineLegSpec, MarketClass, BestBookPrice, BetslipBookQuote, Handoff (+133 more)

### Community 273 - "tests/test_prop_odds_utc_stamp.py"
Cohesion: 0.11
Nodes (13): _Conn, _assert_utc_stamp(), _frozen(), _run_mlb(), capture(), events(), _run_ncaaf(), test_an_eastern_row_then_a_later_utc_row_sorts_in_time_order() (+5 more)

### Community 274 - "Monitoring HTTP stream handler"
Cohesion: 0.14
Nodes (8): Handler, build_server(), _connect(), dumps(), _json_default(), serve_in_thread(), test_loopback_without_a_token_is_allowed(), test_refuses_a_public_bind_without_a_token()

### Community 277 - "NFL publisher lookahead and key tests"
Cohesion: 0.08
Nodes (14): _Conn, _sql_for(), test_a_started_game_is_still_never_published(), test_both_publishers_apply_the_apps_action_filter(), test_both_publishers_read_the_table_the_app_reads(), test_capture_reaches_as_far_as_the_poller_can_write(), test_capture_reaches_forward_for_the_locked_lookahead_sports(), test_ncaaf_lookahead_is_only_safe_because_the_lock_is_general() (+6 more)

### Community 278 - "tests/test_feature_artifact_agreement.py"
Cohesion: 0.11
Nodes (13): _Stub, _TolerantUnpickler, _load(), _newest_artifact(), test_artifact_width_matches_its_own_feature_cols(), test_config_list_matches_the_trained_artifact(), test_known_drift_only_names_real_models(), test_pending_features_are_not_live_without_a_retrain() (+5 more)

### Community 28 - "CLV graded at the price taken"
Cohesion: 0.06
Nodes (27): _Conn, _Res, _fn(), _migration(), _pick(), test_a_draftkings_decided_row_is_unchanged(), test_a_legacy_row_that_cannot_be_re_measured_leaves_the_old_method(), test_a_legacy_stamped_row_is_re_measured_and_leaves_the_queue() (+19 more)

### Community 281 - "tests/test_cloud_retrain_artifacts.py"
Cohesion: 0.10
Nodes (12): _Conn, _restore_artifact(), test_a_failed_upload_does_not_lose_a_model_that_trained(), test_a_missing_artifact_table_is_not_an_error_on_restore(), test_a_no_register_run_stores_nothing(), test_load_model_actually_loads_from_the_store_when_the_file_is_gone(), fetchone(), test_load_model_returns_none_when_the_store_has_nothing_either() (+4 more)

### Community 282 - "NHL totals card publishing"
Cohesion: 0.09
Nodes (17): NhlTotalBet, _LockConn, _SlateConn, pick_rows(), publish(), test_nhl_totals_card_drops_a_bet_under_the_floor(), bet(), _bet() (+9 more)

### Community 284 - "MLB live game state polling loop"
Cohesion: 0.10
Nodes (12): _NoOpConn, _discover_active_games(), _fetch_live_feed(), _game_id_from_statsapi(), _insert_state(), _insert_triggers(), _load_last_state(), poll_forever() (+4 more)

### Community 285 - "System health checks and record reconciliation"
Cohesion: 0.02
Nodes (58): FakeConn, HealthReport, rollback_savepoint(), ncaaf_season_for_date(), test_a_game_date_inside_the_window_counts(), test_a_lookahead_commence_counts_even_when_game_date_is_outside(), test_a_signal_locked_after_first_pitch_was_never_deliverable(), test_a_signal_locked_before_first_pitch_still_counts() (+50 more)

### Community 288 - "tests/test_nfl_opener.py"
Cohesion: 0.20
Nodes (5): TestBettableBooksOnly, TestSelectOpenerBets, _both_sides(), _frame(), _sched()

### Community 291 - "tests/test_team_stats_asof_invariants.py"
Cohesion: 0.13
Nodes (6): _SeasonConn, test_verify_established_live_season_with_two_snapshots_stays_thin(), test_verify_five_day_span_with_one_snapshot_is_thin(), test_verify_four_day_opening_span_is_still_grace(), test_verify_opening_live_season_is_not_thin(), test_verify_short_historical_season_is_still_thin()

### Community 295 - "Stake sizing and units parity"
Cohesion: 0.06
Nodes (21): UnitStake, test_conviction_floors_at_one_not_a_half(), test_conviction_is_flat_for_every_kelly(), test_conviction_is_flat_regardless_of_kelly(), test_favourites_risk_more_until_the_cap_binds(), test_flat_conviction_is_still_price_adjusted(), test_risk_and_win_always_agree_with_the_price(), test_risk_is_capped_at_three_units_and_the_payout_is_recomputed() (+13 more)

### Community 296 - "NFL Kalshi edge and NHL blocked shots"
Cohesion: 0.05
Nodes (41): TestTonightsRowIsATrainingRow, build_frame(), _ew(), expected_value(), fit(), load_skaters(), load_teams(), name_key() (+33 more)

### Community 298 - "tests/test_nfl_wind_publisher.py"
Cohesion: 0.13
Nodes (10): TestBuildRows, TestKickFields, TestParseMatchup, build_rows(), _fmt_line(), kick_fields(), parse_matchup(), test_nfl_wind_and_opener_rows_drop_a_bet_under_the_floor() (+2 more)

### Community 3 - "Prop odds ingestors and quota tracking"
Cohesion: 0.04
Nodes (46): Meter, FakeResp, _write(), _backfill_ncaaf_one_date(), backfill_ncaaf_prop_odds(), _credits_used(), _dk_lined_game_ids(), _event_props() (+38 more)

### Community 30 - "NFL live prop model tests"
Cohesion: 0.04
Nodes (40): _FakeOdds, _IdRecordingOdds, _Q, GamedayWorker, GameTracker, _core_worker(), test_a_deployed_bias_must_sit_inside_its_measured_interval(), test_a_matching_board_keeps_the_fast_cadence() (+32 more)

### Community 300 - "tests/test_health_reason_and_cadence.py"
Cohesion: 0.09
Nodes (20): Report, _one(), test_a_24h_ts_check_reads_as_daily(), test_a_bare_add_still_fills_both_columns(), test_a_broken_query_is_its_own_reason(), test_a_late_check_says_how_late(), test_a_passing_check_says_fresh(), test_a_skipped_check_says_the_gate_was_shut() (+12 more)

### Community 301 - "tests/test_live_publish_parity.py"
Cohesion: 0.17
Nodes (12): _Conn, _db(), _labels(), _pick(), test_a_bet_written_while_paused_is_not_announced_after_an_unpause(), test_a_live_health_state_still_publishes(), test_a_paused_model_is_not_announced(), test_a_retired_model_is_not_announced() (+4 more)

### Community 302 - "tests/test_nfl_weather_supabase_readback.py"
Cohesion: 0.13
Nodes (13): FakeConn, _patch_conn(), _rows(), test_a_null_requested_lead_is_not_returned(), test_a_one_lead_response_is_not_stored(), test_a_partial_window_is_not_returned(), test_a_store_failure_is_a_warning_not_an_error(), test_a_subset_of_leads_reads_only_those_columns() (+5 more)

### Community 306 - "NFL in-play pass attempt prop model"
Cohesion: 0.09
Nodes (11): Read, blind_over_prob(), over_prob(), _pass_attempt_bias_allowed(), test_blind_arm_no_longer_asserts_a_rate(), test_restoring_a_bias_is_one_constant(), test_the_gates_are_checked_before_the_no_bias_decline(), test_the_interval_spans_zero_so_the_lane_declines_to_price() (+3 more)

### Community 307 - "Pregame line poller change tests"
Cohesion: 0.04
Nodes (47): _PollConn, changed_rows(), _credits_used_today(), _fingerprint(), _key(), last_known_prices(), _num(), over_credit_cap() (+39 more)

### Community 308 - "Pitcher stats as-of invariant tests"
Cohesion: 0.05
Nodes (36): _FakeConn, last3_rates(), outs_from_ip(), per_nine(), whip(), already_a_series(), appearances(), _avg_distinct() (+28 more)

### Community 309 - "tests/test_walk_forward_eval.py"
Cohesion: 0.12
Nodes (10): _Cols, _Frame, _fake(), test_a_fold_with_too_little_history_is_skipped(), test_a_single_class_test_season_is_skipped(), _frame(), test_every_fold_trains_only_on_earlier_seasons(), _frame() (+2 more)

### Community 31 - "NBA prop model core"
Cohesion: 0.04
Nodes (69): Spec, collapse_official(), compact_report(), predict_means(), alias_key(), _attach_report_ids(), base_key(), box_panel() (+61 more)

### Community 312 - "NHL props card slate tests"
Cohesion: 0.17
Nodes (5): TestTheBacktestGradesTheRuleTheCardPlays, TestTheCard, pick_rows(), _mus(), _quotes()

### Community 314 - "Pipeline log reason tests"
Cohesion: 0.22
Nodes (6): _Conn, _capture(), test_a_false_step_records_the_last_error_it_logged(), test_a_false_step_that_logged_nothing_still_says_so(), test_a_raising_step_still_records_the_exception(), test_the_sink_is_removed_after_the_step()

### Community 316 - "NFL player stats and props data"
Cohesion: 0.03
Nodes (42): TestGamesRows, TestKickoff, TestParsePlayerRows, TestParseTeamRows, TestUpcomingRows, TestParseNflverseScores, backfill_nfl_player_stats(), current_nfl_season() (+34 more)

### Community 32 - "NCAAF in-play score distribution pricing"
Cohesion: 0.03
Nodes (58): ScoreDistribution, _cluster_bootstrap(), evaluate(), main(), report(), fit(), load_states(), main() (+50 more)

### Community 320 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.09
Nodes (6): _Pg, _PgCursor, TestPreflightCiMode, wind(), wrapped(), fake_open()

### Community 321 - "tests/test_system_health_checks.py"
Cohesion: 0.17
Nodes (4): TestSignalDelivery, _add_signal(), _iso(), _results()

### Community 322 - "X results job and cursor wrapper tests"
Cohesion: 0.10
Nodes (8): _CursorResult, _go(), execute(), test_a_malformed_date_is_refused_before_anything_runs(), test_the_cursor_wrapper_rowcount_is_the_cursors(), test_the_job_does_not_bypass_the_day_is_over_guard(), test_the_job_does_not_read_rowcount_off_the_cursor(), test_the_job_only_clears_its_own_ledger_kind()

### Community 323 - "NBA prop window scheduling tests"
Cohesion: 0.11
Nodes (22): _PlanConn, _fires(), _game(), _jobs(), _plan(), _t(), test_a_projection_too_old_to_price_does_not_block_the_retry(), test_a_tick_fetches_exactly_the_window_games_then_decides_closes_and_publishes() (+14 more)

### Community 328 - "NBA second game projection engine"
Cohesion: 0.16
Nodes (15): State, World, box_design(), box_guard(), box_rating(), f5_player_terms(), fit_box(), league_asof() (+7 more)

### Community 330 - "NFL opener card rows"
Cohesion: 0.13
Nodes (7): TestBuildOpenerRows, TestPublishOpenerInsertOnce, build_opener_rows(), _opener_model(), _card_row(), _row(), execute()

### Community 34 - "Kalshi prop ladders and game markets"
Cohesion: 0.04
Nodes (33): Ladder, Rung, event_code(), event_date(), kalshi_school(), _num(), probe(), record_game_markets() (+25 more)

### Community 341 - "NFL wind totals model"
Cohesion: 0.14
Nodes (12): Bet, american_to_decimal(), american_to_prob(), apply_slate_cap(), devig_two_way(), evaluate_board(), kelly_stake(), model_under_prob() (+4 more)

### Community 342 - "tests/test_live_pick_features.py"
Cohesion: 0.18
Nodes (11): FakeConn, _record_live_features(), _pick(), test_a_live_bet_records_its_feature_row_and_lambda(), test_a_pick_with_no_feature_row_is_skipped_not_written_empty(), test_a_recorder_failure_is_rolled_back_to_its_savepoint(), test_a_recorder_failure_is_swallowed_rather_than_raised(), test_a_success_releases_its_savepoint() (+3 more)

### Community 348 - "Pregame price age tests"
Cohesion: 0.04
Nodes (29): _BoardConn, _OddsConn, _ShopConn, _TwoIdConn, _UfcBoardConn, _get_dk_odds(), _swap_home_away(), _ago() (+21 more)

### Community 349 - "tests/test_prop_missing_features.py"
Cohesion: 0.14
Nodes (5): TestARowMissingAFeatureIsNotScored, TestEveryPropLoopGoesThroughTheHelper, TestTheUmpireIsTheDeclaredException, _frame(), helper()

### Community 350 - "MLB public fade top picks ranking"
Cohesion: 0.10
Nodes (21): PublicFadeBet, composite_score(), estimated_edge(), rank_score(), select_top_k(), _key(), ticket_bucket(), ticket_money_gap() (+13 more)

### Community 353 - "Player news ingestor and name matching"
Cohesion: 0.03
Nodes (54): NewsItem, NewsPlayer, FakeConn, FakeResponse, _Result, drop_duplicate_box_ids(), _article_url(), _athletes_in() (+46 more)

### Community 354 - "NBA prop closing line tests"
Cohesion: 0.07
Nodes (17): _Conn, _Resp, bet_games(), closes_taken(), due(), _event_props(), _events(), run_nba_prop_close_ingestor() (+9 more)

### Community 355 - "NFL in-play decline recording tests"
Cohesion: 0.12
Nodes (12): PicksRecorder, _AvoidConn, _mk_decline(), test_a_market_opinion_decline_is_written_as_avoid(), test_a_moved_line_is_rewritten(), test_an_unchanged_proposition_is_not_rewritten(), test_plumbing_refusals_stay_out_of_picks(), test_recording_a_decline_can_never_break_a_bet() (+4 more)

### Community 359 - "NHL anchored moneyline inputs and fit"
Cohesion: 0.10
Nodes (14): OffsetLogit, _add_rating(), build_inputs(), choose_C(), fit(), _goalie_frame(), inputs_for_date(), listed_goalies() (+6 more)

### Community 363 - "tests/test_run_ledger_orphans.py"
Cohesion: 0.12
Nodes (18): _Conn, db(), _insert_open(), _ledger(), _open_rows(), _row(), test_a_genuine_current_hang_is_still_detectable(), test_a_second_sweep_does_not_abort_the_pass_this_process_started() (+10 more)

### Community 368 - "MLB play-by-play ingestor"
Cohesion: 0.05
Nodes (48): _Conn, _Cur, _get(), _iso(), main(), planned_calls(), pull_day(), rows_for() (+40 more)

### Community 37 - "NBA lineup stints from play-by-play"
Cohesion: 0.05
Nodes (48): Diagnostics, _Seg, alias_play_ids(), roster_from_plays(), score_plays(), _accumulate(), _add_one(), _and_one_follows() (+40 more)

### Community 376 - "In-play calibrated decision tests"
Cohesion: 0.09
Nodes (16): RecordingConn, fetch_graded(), _cut(), _signal(), test_a_big_enough_claim_still_fires_after_calibration(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(), test_a_hot_live_model_no_longer_fires_the_marginal_bet(), test_a_live_model_is_read_out_of_picks_not_the_matview() (+8 more)

### Community 378 - "NFL DraftKings line snapshots"
Cohesion: 0.08
Nodes (13): TestDkLineRows, TestPublishLineSnapshots, TestSnapshotRowParams, append_snapshot_csv(), dk_line_rows(), dump_dk_lines(), _num(), snapshot_schedule() (+5 more)

### Community 38 - "Sharp book odds retention in pruning"
Cohesion: 0.08
Nodes (14): _RecordingConn, _prop_reference_books(), protected_for(), test_the_bookmaker_these_rows_use_survives_the_daily_prune(), test_a_shopping_book_is_still_prunable(), test_every_prop_reference_book_is_protected(), test_every_sharp_book_is_protected_in_the_prop_table(), test_pinnacle_specifically_is_protected_in_the_prop_table() (+6 more)

### Community 380 - "NFL historical weather fetch script"
Cohesion: 0.18
Nodes (10): DailyLimit, Pacer, consolidate(), era5_check(), game_hours(), log(), main(), om_get() (+2 more)

### Community 381 - "tests/test_heartbeat_disabled_jobs.py"
Cohesion: 0.23
Nodes (6): Conn, _build(), test_a_job_marked_disabled_is_not_silent(), test_a_job_that_runs_here_is_not_marked(), test_a_service_leaves_alone_the_jobs_another_service_owns(), test_startup_marks_an_owned_job_that_is_switched_off()

### Community 387 - "tests/test_repair_bogus_first_pitch_labels.py"
Cohesion: 0.13
Nodes (8): _Conn, _run(), test_a_dry_run_writes_nothing_at_all(), test_a_short_backup_rolls_back_and_relabels_nothing(), test_the_backup_is_written_before_the_update(), test_the_backup_table_is_revoked_from_the_public_roles(), test_the_bogus_set_is_computed_never_listed(), test_the_query_is_scoped_to_the_scheduled_start_not_the_derived_one()

### Community 39 - "nfl/live_model/tests/test_executor.py"
Cohesion: 0.06
Nodes (46): Decision, Executor, american_to_decimal(), derivative_lag(), ev_floor(), _mk(), expected_value(), honest_probability() (+38 more)

### Community 393 - "tests/test_sbr_loader.py"
Cohesion: 0.14
Nodes (3): _SqliteConnShim, _SqliteCursorShim, loader_conn()

### Community 394 - "NHL totals EV floor gate"
Cohesion: 0.08
Nodes (21): Gate, expected_value(), min_ev_for(), find_bets(), test_ncaaf_live_ev_floor_is_wired_from_config(), test_expected_value_is_on_the_quoted_price(), test_the_floor_is_the_global_one_unless_the_model_carries_a_higher_one(), test_the_shipped_floor_is_020_and_the_ncaaf_moneyline_keeps_the_030_it_was_swept_under() (+13 more)

### Community 397 - "mobile/scripts/ux_scan.mts"
Cohesion: 0.16
Nodes (18): Finding, Severity, changedFiles(), entitlementGate(), fontScaling(), fontSizeLiterals(), hexColors(), main() (+10 more)

### Community 4 - "Database connection and game features"
Cohesion: 0.03
Nodes (52): TestRefusalLog, TestRegistryHealthCheck, TestUnratedFbsClaim, _log_pipeline(), query_injuries_for_game(), nfl_game_dates(), _stored(), get_latest_odds_for_game() (+44 more)

### Community 402 - "NBA second game market family frames"
Cohesion: 0.10
Nodes (11): PointInputs, emit_family(), fair_frame(), family_frames(), gap_strength(), move_strength(), move_strength_by_season(), population() (+3 more)

### Community 408 - "Price prefilter timeout rollback tests"
Cohesion: 0.15
Nodes (9): _PoisonConn, _event_index(), _games(), _run(), test_a_failed_savepoint_rollback_falls_back_to_full_rollback(), test_both_prefilters_timing_out_still_reaches_the_pipeline_log(), test_lookahead_timeout_rolls_back_and_scoring_continues(), test_ncaaf_timeout_rolls_back_and_scoring_continues() (+1 more)

### Community 409 - "mobile/src/lib/otaUpdate.ts"
Cohesion: 0.21
Nodes (11): Calls, CheckState, CheckTrigger, UpdateOutcome, UpdatesApi, check(), fakeApi(), main() (+3 more)

### Community 41 - "tests/test_live_quote_staleness.py"
Cohesion: 0.05
Nodes (43): _Conn, _Q, build_row(), _mark_written(), _publish_key(), quote_from_nfl_quotes(), record_live_prices(), rows_from_quote() (+35 more)

### Community 411 - "Mobile game status and date formatting"
Cohesion: 0.03
Nodes (75): Props, Props, Slop, StatusForSpeech, GameLike, InningHalf, LiveStateLike, LiveGameStateRow (+67 more)

### Community 417 - "NHL derivative odds history purchase"
Cohesion: 0.10
Nodes (16): Meter, _blank_row(), _done_ids(), _ensure_ledger(), estimate_credits(), format_plan(), _games_by_date(), main() (+8 more)

### Community 422 - "Prop pick settlement across sports"
Cohesion: 0.03
Nodes (37): _SelectConn, _SqliteShim, TestNflPropSettlement, _Shim, TestSettlement, test_a_missing_stat_is_none_not_zero(), test_a_turnovers_bet_on_a_player_who_played_settles_win_not_no_action(), test_combo_markets_are_mapped_to_helpers_and_only_the_nba_rule_uses_them() (+29 more)

### Community 423 - "Pipeline report with per-section rollback"
Cohesion: 0.13
Nodes (8): _Conn, collect(), main(), render(), _rows(), test_a_failed_query_rolls_back(), test_every_section_is_still_present(), test_one_broken_section_does_not_break_the_rest()

### Community 424 - "supabase/functions/_shared/discord.ts"
Cohesion: 0.20
Nodes (15): DiscordApiError, DiscordUser, RoleSyncResult, addAppRole(), addGuildMember(), botFetch(), expectOk(), isGuildMember() (+7 more)

### Community 43 - "Worker job queue validation tests"
Cohesion: 0.03
Nodes (48): _VoidConn, _posted_row(), _quiet(), _run_void(), _run_void_job(), test_a_failed_job_needs_a_new_key_to_rerun(), test_a_graded_pick_is_refused_not_rewritten(), test_a_pick_that_does_not_exist_is_reported_as_missing() (+40 more)

### Community 433 - "tests/test_system_health_checks.py"
Cohesion: 0.16
Nodes (3): TestPassCompletion, TestPassSteps, _add_run()

### Community 435 - "UFC event ingest tests"
Cohesion: 0.12
Nodes (6): _IngestConn, _ingest(), _one_fight_event(), test_a_late_replacement_is_not_scored_on_the_original_booking(), test_a_row_naming_neither_fighter_is_left_unscored(), test_the_same_fight_stored_twice_is_scored_on_both_rows_each_way_round()

### Community 442 - "tests/test_batter_prop_log_pin.py"
Cohesion: 0.10
Nodes (10): _Rec, _ScoringConn, build_batter_scoring_rows(), _log_sql(), test_batter_log_scan_is_pinned_to_the_lookback_not_the_catalog(), test_five_models_share_one_log_load(), test_no_lineup_does_not_scan_the_log(), test_starter_log_inside_the_batter_loader_uses_the_same_floor() (+2 more)

### Community 443 - "tests/test_opp_starter_features.py"
Cohesion: 0.08
Nodes (16): _StubConn, _StubResult, _build_bulk_batter_lookups(), _opp_starter_savant(), _starter_gb_pct(), _batter_bulk(), test_batter_bulk_carries_everything_opp_starter_savant_reads(), test_it_reads_the_starters_savant_row() (+8 more)

### Community 445 - "NFL CLV backtest and feature build"
Cohesion: 0.10
Nodes (14): ShrunkEnsemble, add_form(), build(), feature_columns(), market_features(), team_game_stats(), fmt(), main() (+6 more)

### Community 446 - "MLB doubleheader twin game merge"
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

### Community 456 - "NFL forecast and historical weather fetch"
Cohesion: 0.18
Nodes (9): OpenMeteoError, fetch_era5(), fetch_issued_forecasts(), fetch_live_forecast(), _frame(), _get(), _issued_columns(), _issued_from_supabase() (+1 more)

### Community 457 - "NFL in-play pick writer row tests"
Cohesion: 0.13
Nodes (10): _Decision, build_pick(), test_a_locked_lane_writes_nothing_further(), test_a_pass_is_never_announced(), test_edge_is_the_platform_edge_not_the_lanes_ev(), test_every_row_key_is_actually_bound_by_the_insert(), test_the_label_agrees_with_the_side_and_the_line_it_carries(), test_the_label_names_the_stat_the_model_actually_trades() (+2 more)

### Community 460 - "Discord results recap backfill"
Cohesion: 0.03
Nodes (41): _Conn, _Conn, build_parser(), _date_is_over(), main(), post_backfill(), test_a_day_that_is_not_over_is_refused(), test_apply_calls_both_notifiers_for_that_date() (+33 more)

### Community 466 - "Mobile paywall and in-app billing"
Cohesion: 0.06
Nodes (72): useSubscription, BillingDisabledError, CheckoutResult, BillingRail, Plan, PlanKey, SubscriptionRow, IapPurchaseResult (+64 more)

### Community 47 - "scripts/nfl_edge_gameline_rules.py"
Cohesion: 0.06
Nodes (50): Tee, TestTheWeatherStepWalksTheWindow, _nhl_blended_features(), d(), ats(), bettable_ats(), bh(), board_at() (+42 more)

### Community 471 - "tests/test_model_game_savepoint.py"
Cohesion: 0.15
Nodes (4): _PoisonConn, _games(), test_a_best_price_timeout_is_the_logged_error_and_the_next_lookup_runs(), test_a_model_sql_error_does_not_poison_the_next_model()

### Community 475 - "tests/test_system_health_checks.py"
Cohesion: 0.14
Nodes (4): _FrozenDatetime, _Shim, db(), mlb_wired()

### Community 478 - "NFL live leader decision model"
Cohesion: 0.17
Nodes (10): Artifact, Decision, am_to_dec(), artifact_from_dict(), band_for(), decide(), leader_expected_margin(), load_artifact() (+2 more)

### Community 48 - "tests/test_calibration_watch.py"
Cohesion: 0.05
Nodes (14): _Conn, _Res, TestDormantLiveModels, TestRosterChanges, TestTheRun, TestVerdictChanges, TestVolumeShifts, _row() (+6 more)

### Community 482 - "tests/test_promote_external.py"
Cohesion: 0.16
Nodes (5): _Conn, promote_external(), test_external_promotion_refuses_a_map_that_does_not_transfer(), test_external_promotion_writes_only_the_promoted_columns(), test_the_scorer_reads_the_external_map_like_any_promoted_one()

### Community 489 - "NFL in-play prop snapshot puller"
Cohesion: 0.21
Nodes (7): Puller, _key(), _ledger(), main(), match_event(), _save_ledger(), snapshot_plan()

### Community 49 - "Failure alerter fake-connection tests"
Cohesion: 0.08
Nodes (12): FakeConn, TestDeliveryAndNoise, TestHealthCheckOnlyIsNotADirtyPass, TestItCannotBreakTheWorker, TestSilentJobs, TestWhatCountsAsAFailure, _clean_runs(), _posts() (+4 more)

### Community 490 - "Prop odds with missing game tests"
Cohesion: 0.15
Nodes (4): FakeConn, _run(), test_event_with_no_games_row_is_skipped_and_others_still_insert(), test_fk_on_insert_does_not_unwrite_the_events_that_already_landed()

### Community 493 - "Job heartbeat watchdog and ops alerts"
Cohesion: 0.05
Nodes (26): TestItNeverDecides, _announce(), _announce_and_ledger(), _post(), _remember_delivery(), _is_health_check_step(), _latest_health_rows(), _pass_is_clean() (+18 more)

### Community 496 - "MLB prop pregame price cutoff tests"
Cohesion: 0.12
Nodes (7): _Conn, test_a_game_with_no_cutoff_fails_open(), test_both_market_relative_loaders_bound_on_the_cutoff(), test_it_compares_parsed_timestamps_not_strings(), test_it_joins_games_and_uses_the_shared_cutoff(), test_the_newest_qualifying_quote_still_wins(), test_the_post_first_pitch_quote_is_dropped_even_though_it_is_newest()

### Community 5 - "Mobile app screens and theme"
Cohesion: 0.02
Nodes (300): IoniconName, Props, Nav, Props, Props, Props, FilterChipProps, Props (+292 more)

### Community 501 - "CLV off DraftKings line tests"
Cohesion: 0.15
Nodes (6): _Conn, _Res, test_a_row_that_carries_dk_odds_keeps_its_book_and_price(), test_the_backfill_queues_the_dates_of_those_picks(), test_without_pinnacle_the_primary_is_still_the_bet_book(), _ts()

### Community 510 - "Model trainer and prop retrains"
Cohesion: 0.02
Nodes (100): TestTrainingExcludesThemAndScoringDoesNot, assert_retrain_allowed(), calibration_method(), training_feature_cols(), build_bulk_wnba_prop_lookups(), build_wnba_prop_training_dataset(), f(), _calibration_error_weighted() (+92 more)

### Community 511 - "Prop odds next-day lookahead"
Cohesion: 0.17
Nodes (4): TestTheOddsFetchReachesTomorrow, TestTheScorerReachesTomorrow, _get_events(), _events_src()

### Community 516 - "NFL in-play pick writer tests"
Cohesion: 0.12
Nodes (7): _Conn, test_a_pass_is_never_written_to_picks(), test_an_unresolvable_decision_writes_nothing(), test_game_id_resolves_from_the_book_s_team_names(), test_picks_recorder_drops_a_pass_attempt_over_before_sql(), test_the_announce_runs_after_the_commit_and_after_the_connection_closes(), commit()

### Community 52 - "tests/test_best_line_live.py"
Cohesion: 0.03
Nodes (66): _FakeConn, _FakeConn, _age_seconds(), _book_move(), _dk_odds_after(), _get_live_dk_odds(), _latest_live_state(), _live_bets_today() (+58 more)

### Community 526 - "NCAAF college data refresh and backfill tests"
Cohesion: 0.16
Nodes (8): _NullConn, backfill_ncaaf(), refresh_ncaaf_games(), test_backfill_returns_totals_when_every_season_succeeds(), test_backfill_survives_a_mid_run_season_failure(), test_refresh_games_happy_path_counts_games(), test_refresh_games_repairs_every_season_and_reports_failures(), test_refresh_stats_isolates_a_failing_season()

### Community 533 - "NFL wind card book filter tests"
Cohesion: 0.07
Nodes (10): TestTheCardFilters, TestTheListIsShared, test_the_decisions_ledger_is_worker_only_and_created_behind_the_guard(), test_a_replay_never_prices_off_todays_ladder_even_when_on(), test_the_card_does_not_price_off_kalshi_until_it_is_graded(), _attach(), books(), card() (+2 more)

### Community 536 - "Closing line value backfill job"
Cohesion: 0.13
Nodes (6): _Conn, _stub_backfill(), test_hard_cap_stops_a_nonempty_queue(), test_loops_until_a_pass_fills_nothing(), test_the_runner_opens_get_connection_and_calls_backfill_clv(), _job_clv_backfill()

### Community 539 - "First signal repair tests"
Cohesion: 0.15
Nodes (4): _Conn, _VoidedConn, _make(), test_a_voided_lane_is_left_alone()

### Community 54 - "tests/test_void_picks.py"
Cohesion: 0.05
Nodes (18): _FakeConn, TestAPostedSignalIsLocked, TestAPostedVoidAnnouncesAfterCommit, TestTheToolRefusesToMatchEverything, TestVoidingAPostedPickIsAnExplicitOptIn, TestWhatMayBeVoided, TestWhatTheVoidWrites, announce_posted_voids() (+10 more)

### Community 541 - "Pipeline staleness watch tests"
Cohesion: 0.16
Nodes (7): _Conn, test_a_fresh_sweep_and_savant_produce_no_finding(), test_a_missing_sweeps_table_is_reported_not_swallowed(), test_a_missing_webhook_is_not_ledgered_either(), test_a_stale_sweep_date_is_reported(), test_savant_with_only_one_player_type_is_stale_even_when_dated_today(), _stale_weeklies()

### Community 543 - "Pregame odds read cutoff tests"
Cohesion: 0.15
Nodes (6): _OddsConn, _odds_query(), test_a_game_with_no_commence_time_keeps_every_row(), test_the_cutoff_is_the_19_char_utc_prefix(), test_the_pregame_read_is_bounded_at_first_pitch(), test_the_ufc_sibling_lookup_is_bounded_too()

### Community 544 - "NCAAF starter-out search dataset"
Cohesion: 0.16
Nodes (8): LabelSet, build_label_set(), _fetch_lines(), _fetch_raw(), opener_coverage(), _pick_provider(), provider_continuity(), main()

### Community 55 - "NCAAF in-play gameday loop and feeds"
Cohesion: 0.04
Nodes (44): LiveOddsFeed, _Conn, _Result, _Conn, resolve_odds_api_school(), now_iso(), fetch_scoreboard_cfbd(), fetch_team_ids() (+36 more)

### Community 551 - "NFL prop market stacking research"
Cohesion: 0.03
Nodes (74): Pick, _fmt_edge(), _fmt_odds(), main(), _pick_card(), render_email(), main(), fetch_season() (+66 more)

### Community 554 - "Scorer confidence tiers and pick labels"
Cohesion: 0.05
Nodes (13): TestBuildInjuryFlag, TestBuildPickLabel, TestConfidenceTier, TestFeatureValue, TestMakePick, TestQuarterKelly, _build_injury_flag(), _build_pick_label() (+5 more)

### Community 56 - "tests/test_daily_retry.py"
Cohesion: 0.06
Nodes (43): _Conn, _Cursor, _FrozenDatetime, DailyRun, Decision, _aborted(), _aborted_row(), _ok() (+35 more)

### Community 561 - "Injury adjustment feature tests"
Cohesion: 0.11
Nodes (5): TestComputeInjuryAdjustment, TestHasReturnee, _compute_injury_adjustment(), _has_returnee(), _assemble_wnba_features()

### Community 564 - "NFL prop market card publisher"
Cohesion: 0.13
Nodes (10): TestMarketCardPublisher, drop_pulled_quotes(), _ts(), _q(), test_a_book_on_its_own_cadence_is_not_penalised_inside_three_hours(), test_a_book_that_stopped_returning_the_game_is_dropped(), test_a_player_the_book_stopped_quoting_is_dropped(), test_a_whole_market_the_book_pulled_is_dropped() (+2 more)

### Community 567 - "MLB live book move guard tests"
Cohesion: 0.23
Nodes (7): _MlbConn, _mlb_odds(), _mlb_ts(), test_mlb_declines_a_total_that_moved_a_full_run_on_an_unchanged_state(), test_mlb_first_sight_is_not_a_move(), test_mlb_keeps_a_total_that_has_not_moved_since_the_state_changed(), test_mlb_state_change_lookup_reads_the_full_base_out_state()

### Community 57 - "tests/test_live_book_move_guard.py"
Cohesion: 0.10
Nodes (31): BookMoveClock, american_to_implied(), _at(), _delaware_ctx(), _dk(), _iso(), _ncaaf_engine(), _nfl() (+23 more)

### Community 576 - "tests/test_weekly_catch_up.py"
Cohesion: 0.18
Nodes (3): _Conn, test_a_failing_savant_refresh_does_not_cost_the_calibration_its_catch_up(), test_ownership_is_checked_per_job()

### Community 579 - "tests/test_umpire_ingestor.py"
Cohesion: 0.15
Nodes (5): TestHealWindowLo, backfill_umpires(), _fetch_umpires_for_date(), _heal_window_lo(), ingest_umpires_for_date()

### Community 58 - "tests: test_discord_notifier + test_discord_live_field"
Cohesion: 0.04
Nodes (37): _FakeConn, _StampConn, _sig(), test_a_strictly_better_book_becomes_the_headline(), test_an_equal_or_worse_price_never_replaces_draftkings(), test_best_odds_never_reaches_the_qualifying_gate(), test_draftkings_winning_its_own_shop_is_published_as_draftkings(), test_every_pre_game_producer_computes_good_to() (+29 more)

### Community 581 - "In-play score change clock"
Cohesion: 0.23
Nodes (5): ScoreClock, test_score_clock_ignores_a_dropped_score_field(), test_score_clock_keeps_games_independent(), test_score_clock_reports_no_event_at_first_sight(), test_score_clock_stamps_the_change_and_holds_it()

### Community 582 - "Prop odds book update-time tests"
Cohesion: 0.26
Nodes (6): _Conn, _parse(), test_a_row_built_without_the_key_still_inserts_as_null(), test_no_clock_anywhere_is_none_not_our_fetch_time(), test_the_column_is_added_only_when_the_catalog_lacks_it(), test_the_markets_own_clock_is_stored_else_the_books()

### Community 583 - "NFL pick monitor"
Cohesion: 0.14
Nodes (7): TestClassify, TestImmutabilityContract, TestLatestPerPick, TestWindPublisherLock, classify(), latest_per_pick(), _row()

### Community 588 - "MLB in-play pregame total anchor tests"
Cohesion: 0.12
Nodes (6): _RecordingConn, _pregame_features(), test_h2h_row_alone_never_fills_the_anchor(), test_pregame_features_reads_both_markets(), test_serve_side_cutoff_uses_the_shared_first_pitch_bound(), test_the_anchor_is_not_wired_into_a_model_by_accident()

### Community 59 - "NFL odds client and opener card"
Cohesion: 0.05
Nodes (31): OddsAPIClient, SnapshotResult, _key(), _ledger_bump(), _ledger_read(), ledger_status(), _ledger_write(), snapshot_to_frame() (+23 more)

### Community 592 - "NFL pick monitor id matching"
Cohesion: 0.16
Nodes (3): TestTheJoinKeyMatchesPicks, eval_row(), _picks_game_id()

### Community 595 - "Voided picks never rechosen tests"
Cohesion: 0.21
Nodes (4): _Conn, _db(), test_a_voided_pick_is_not_a_free_pick_candidate(), test_a_voided_pick_is_not_a_parlay_leg()

### Community 597 - "Multi-book fallback response tests"
Cohesion: 0.20
Nodes (7): _Resp, test_a_rejected_book_list_falls_back_to_the_decision_book(), _get(), test_the_fallback_does_not_recurse_forever(), _get(), test_the_per_event_fetch_asks_for_every_book(), _get()

### Community 6 - "Mobile custom model builder and backtest"
Cohesion: 0.03
Nodes (130): Props, Props, BacktestPickRow, ChipGroup, ChipKey, FilterablePick, FilterablePick, GestureIntent (+122 more)

### Community 601 - "NFL in-play pick writer failure tests"
Cohesion: 0.17
Nodes (6): _OpenConn, test_a_failing_announcer_cannot_undo_or_fail_the_write(), test_a_failing_recorder_cannot_take_the_other_down(), boom(), test_a_written_bet_is_announced_with_its_own_game_date(), test_an_unlocked_lane_does_write()

### Community 606 - "Calibration schema ordering tests"
Cohesion: 0.17
Nodes (4): _SchemaRecordingConn, test_persist_still_creates_them_too(), test_promote_creates_the_columns_it_writes_to(), test_the_alters_come_before_any_write_in_both_paths()

### Community 61 - "Mobile tracked bets and stake settings"
Cohesion: 0.03
Nodes (88): Props, Props, PushStatus, StakeMode, StakeState, LiveTrackSnapshot, TrackedBetRow, trackedBetStatus (+80 more)

### Community 611 - "supabase/functions/revenuecat-webhook/index.ts"
Cohesion: 0.22
Nodes (3): RcEvent, admin, PRODUCT_TO_PLAN

### Community 613 - "supabase/functions/whop-webhook/index.ts"
Cohesion: 0.25
Nodes (4): WhopMembership, signatureValid(), timingSafeEqual(), admin

### Community 617 - "Mobile auth session hook"
Cohesion: 0.29
Nodes (10): AuthState, AuthStatus, useAuth, applySession(), bootstrap(), handleAppStateChange(), setState(), signOut() (+2 more)

### Community 626 - "NHL as-of feature leak tests"
Cohesion: 0.22
Nodes (4): TestOpeningNightIsEarlySeason, _blk_nhl_asof(), _t(), test_the_training_path_reads_nhl_odds_by_game_not_by_sport()

### Community 630 - "Paused bets keep real verdict tests"
Cohesion: 0.18
Nodes (3): _Capture, test_a_paused_settled_bet_never_moves_the_kelly_bankroll(), test_todays_standing_bets_ignore_a_paused_row()

### Community 631 - "NCAAF in-play fetch cadence tests"
Cohesion: 0.24
Nodes (6): _Ctx, _ev(), test_a_single_failed_summary_does_not_drop_the_other_games(), test_cfbd_mode_does_no_per_game_fetching(), test_espn_states_are_fetched_in_parallel_and_stay_aligned(), test_unknown_matchups_never_cost_a_fetch()

### Community 633 - "Prop scorer tipoff test wiring"
Cohesion: 0.22
Nodes (5): _Clock, _fake_datetime_class(), _game(), _iso(), _wire()

### Community 65 - "NFL in-play score distribution"
Cohesion: 0.10
Nodes (9): ScoreDistribution, gaussian_copula_joint(), mu_bucket(), _mu_centres(), _spearman_to_gaussian(), time_bucket(), test_buckets_are_monotone_and_bounded(), test_copula_covariance_takes_the_sign_of_rho() (+1 more)

### Community 653 - "Model quality database end-to-end test"
Cohesion: 0.22
Nodes (3): _Shim, _insert_open_bet(), test_run_persists_all_unders_fade_slate_as_crit()

### Community 662 - "Signal publish-on-write tests"
Cohesion: 0.06
Nodes (18): _Conn, _body(), _row(), _surfaces(), _make(), test_a_broken_webhook_does_not_suppress_the_push(), test_a_failed_capture_still_delivers(), test_a_publish_failure_does_not_kill_the_tick() (+10 more)

### Community 668 - "Player name matching and local cache"
Cohesion: 0.02
Nodes (90): TestKickoffGate, TestLocalCacheGuards, TestMarketGrading, TestNormaliseName, ladders_or_empty(), norm_player_name(), activate(), available() (+82 more)

### Community 669 - "NFL in-play prop sharp book pull tests"
Cohesion: 0.22
Nodes (3): TestIngestEventsDoesNotShadowItsMarkets, test_live_prop_pull_asks_for_the_sharp_book(), fake_event_props()

### Community 67 - "tests/test_game_market_gate.py"
Cohesion: 0.06
Nodes (49): GateVerdict, MarketBookend, PublicSplits, apply_to_picks(), _as_float(), bookend_from_odds(), evaluate(), fair_prob() (+41 more)

### Community 68 - "NBA second-model prop study"
Cohesion: 0.06
Nodes (40): Shape, appearances(), box_tables(), build(), check_close_prior(), consensus_number(), empty_times(), fit_shape() (+32 more)

### Community 69 - "tests/test_pick_integrity.py"
Cohesion: 0.04
Nodes (40): _Conn, _Shim, _add_pick(), discord_sent(), _health(), health_db(), test_a_label_may_not_name_a_market_the_pick_does_not_settle_on(), test_a_label_naming_the_other_team_is_refused() (+32 more)

### Community 7 - "MLB game features and market sweeps"
Cohesion: 0.02
Nodes (79): TestMarketForOdds, TestPregameSnapshotGuard, TestAmericanToDecimalScorer, trusted_first_pitch(), _blk_bullpen_ip(), _blk_injuries(), _blk_nhl_loc_goals(), _blk_nhl_rolling_goals() (+71 more)

### Community 70 - "tests/test_record_one_pick_per_event.py"
Cohesion: 0.04
Nodes (47): _CaptureConn, _RecordingConn, duplicate_copy_exclusion_sql(), _code(), _copy_for_node(), _fn(), _node(), _read() (+39 more)

### Community 73 - "nfl/live_model/tests: test_props + props"
Cohesion: 0.08
Nodes (34): PropProjection, GameState, PlayerState, _accrued(), _count(), detect_inactive(), price_over(), project() (+26 more)

### Community 77 - "tests/test_wnba_prop_market.py"
Cohesion: 0.06
Nodes (31): _QuoteConn, apply_price_floor(), norm_name(), pick_rows(), player_ids(), publish(), render(), run_card() (+23 more)

### Community 78 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.09
Nodes (15): _After, _Conn, _RaceConn, TestFlexedKickoffRefreshes, TestLockSurvivesNothing, TestNoneRowBesideABetIsCleared, TestPublishRace, TestPublishScored (+7 more)

### Community 79 - "NHL derivative totals model"
Cohesion: 0.06
Nodes (41): Market, build_p1_frame(), build_team_frame(), day_interval(), _ew(), fit(), game_means(), _implied_vec() (+33 more)

### Community 8 - "Mobile player log and matchup stats"
Cohesion: 0.02
Nodes (212): Props, PlayerNextGame, Section, Args, PlayerStatKey, HitSelection, HitDirection, BookQuote (+204 more)

### Community 83 - "tests/test_nhl_props.py"
Cohesion: 0.07
Nodes (15): _Shim, TestEveryLiveModelIsWiredEverywhere, TestSettlement, TestTheDistribution, TestTheGoalieFrame, TestTonightsRowIsATrainingRow, _bet(), db() (+7 more)

### Community 84 - "Publish key identity and push alerts"
Cohesion: 0.02
Nodes (90): _Conn, _KeyConn, paused_row_exclusion_sql(), test_the_restate_producer_keeps_the_first_bet_only(), _sql_key(), test_a_game_level_key_has_no_tail(), test_an_opening_signal_is_live_only_when_discord_published_it(), test_discord_led_visibility() (+82 more)

### Community 85 - "tests/test_recap_retries_a_skipped_day.py"
Cohesion: 0.06
Nodes (26): _LiteConn, World, _add_pick(), _grade(), _lite(), _schema(), test_a_day_with_nothing_counting_posts_nothing_and_logs_nothing(), test_a_failed_receipt_never_reposts_the_day() (+18 more)

### Community 851 - "NBA odds archive rerun safety"
Cohesion: 0.22
Nodes (5): _Conn, load(), stored_keys(), test_a_rerun_writes_nothing_already_stored(), test_stored_rows_are_read_by_game_id_not_by_scanning_for_the_source()

### Community 871 - "NFL in-play feed resilience tests"
Cohesion: 0.07
Nodes (21): _ScriptedTick, _core_docs(), _core_event(), _fetch(), _run_scripted(), test_a_host_switch_is_alerted(), test_a_hunted_game_counts_as_busy(), test_a_live_game_resets_the_idle_counter() (+13 more)

### Community 88 - "NBA prop market decision tests"
Cohesion: 0.05
Nodes (38): _SettleConn, fair_under(), q(), run(), run_full(), _settle(), test_a_fetch_after_now_or_at_tip_and_a_close_row_never_decide(), test_a_fetch_older_than_the_window_is_not_a_price() (+30 more)

### Community 880 - "Database schema statement splitter tests"
Cohesion: 0.18
Nodes (5): TestRealSchema, TestSplitter, TestSqliteSchema, _load_postgres_schema(), _split_sql_statements()

### Community 9 - "Per-model probability calibration fitting tests"
Cohesion: 0.05
Nodes (25): _FakeConn, fit_model(), test_a_map_that_does_not_help_out_of_sample_is_not_applied(), test_a_map_that_helps_is_applied(), test_a_model_with_no_record_takes_the_pooled_correction(), test_a_model_with_too_few_graded_picks_gets_the_shrunk_offset_not_a_platt_map(), test_a_side_under_0_5_never_comes_out_as_the_favourite(), test_an_unmapped_model_is_unchanged_by_phase_2() (+17 more)

### Community 90 - "tests/test_f5_any_book_line.py"
Cohesion: 0.09
Nodes (29): _Clf, _GameOddsConn, _fallback_game_line_quote(), _get_scoring_odds(), _has_real_game_price(), _cut(), _mlb_feat(), _on() (+21 more)

### Community 92 - "tests/test_ncaaf_prop_odds.py"
Cohesion: 0.05
Nodes (27): _Conn, _Resp, _market_chunks(), _football_map(), resolver(), scope(), test_a_book_we_did_not_ask_for_is_never_written(), test_a_day_with_no_college_games_spends_nothing() (+19 more)

### Community 94 - "NFL prop model tests"
Cohesion: 0.02
Nodes (58): _Conn, _Cur, TestBinaryMarket, TestCountDistributions, TestLocalOddsCache, TestPropOddsLoader, _Conn, _Cur (+50 more)

### Community 95 - "tests/test_ncaaf_pbp_store.py"
Cohesion: 0.07
Nodes (20): _Conn, _extremes(), load_season_from_db(), observed_ranges(), _report_ranges(), store_season(), _plays(), test_a_rerun_updates_rather_than_duplicating() (+12 more)

### Community 96 - "tests/test_heartbeat_watchdog.py"
Cohesion: 0.08
Nodes (24): _FakeConn, _FakeCursor, _break_db(), sink(), test_a_failed_post_does_not_start_the_throttle(), test_a_healthy_start_never_announces_a_recovery(), test_a_returning_outage_alerts_again_immediately(), test_a_silent_failure_alerter_is_caught_by_the_watchdog() (+16 more)

### Community 97 - "Game injury veto gate and tests"
Cohesion: 0.05
Nodes (49): _InjConn, _InjConn, apply_to_picks(), _goalie_names(), _pitcher_names(), player_matches_veto(), relevant_players(), _star_names() (+41 more)

### Community 99 - "Record correction post tests"
Cohesion: 0.06
Nodes (26): Ledger, _Result, _pin(), _real_post(), _real_tweet(), x_posts(), _publish(), test_a_failed_discord_ledger_does_not_send_x() (+18 more)

### Community 207 - "Shared database connection core"
Cohesion: 0.01
Nodes (106): _connect(), _convert_params(), _convert_params_outside_literals(), get_connection(), _open(), _session_options(), setup_database(), _fetchone() (+98 more)

### Community 10 - "NFL prop over lean concentration study"
Cohesion: 0.25
Nodes (7): add_context(), boot(), main(), profit(), report(), tercile_split(), under_profit()

### Community 100 - "NHL prop priced lab"
Cohesion: 0.20
Nodes (12): _ew(), fit_score(), main(), opponent_allowed(), coherent(), fold(), load_prices(), main() (+4 more)

### Community 101 - "NBA prop projection model internals"
Cohesion: 0.08
Nodes (21): asof_roster(), box_from_log(), coherent(), espn_compact(), find_bets(), implied_one(), main_line(), minutes_cols() (+13 more)

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
Cohesion: 0.06
Nodes (30): apply_prop_daily_cap(), _claimed_ev(), dedupe_player_props(), _downgrade(), _is_paused_row(), _bet(), _identity_cal(), _prop() (+22 more)

### Community 108 - "NCAAF in-play pregame spread correction"
Cohesion: 0.09
Nodes (17): correct_for_pregame(), _load_pregame_calibration(), pregame_dog_points(), test_a_big_dog_is_marked_down_hard(), test_a_corrupt_artifact_leaves_the_probability_alone(), test_a_favourite_is_marked_up(), test_a_missing_artifact_leaves_the_probability_alone(), test_a_pick_em_is_barely_touched() (+9 more)

### Community 109 - "MLB batter and pitcher prop features"
Cohesion: 0.06
Nodes (21): _all_batter_rows(), _all_pitcher_rows(), _batter_rate(), _batter_rolling_avg(), _batter_savant(), _batter_season_avg(), _build_batter_row(), _build_bulk_prop_lookups() (+13 more)

### Community 110 - "tests/test_mobile_line_movement.py"
Cohesion: 0.08
Nodes (27): _fn(), _read(), _run(), test_a_cut_table_keeps_the_pick_and_says_what_it_covers(), test_a_cut_window_keeps_the_pick_row_on_the_8_row_table(), test_a_pick_made_after_the_cards_start_never_reads_since_your_pick(), test_after_the_start_the_verdict_is_not_graded(), test_an_old_snapshot_is_not_the_price_at_the_pick() (+19 more)

### Community 111 - "tests/test_live_calibration.py"
Cohesion: 0.06
Nodes (36): _live_calibration(), pick(), test_a_peak_with_no_plateau_anywhere_is_labelled_as_one(), test_a_prob_cut_and_an_ev_cut_select_different_picks(), test_calibration_also_scores_ev_against_realised_roi(), test_calibration_is_empty_rather_than_wrong_with_nothing_settled(), test_calibration_reports_the_gap_between_claim_and_reality(), test_expected_value_matches_the_hand_calculation() (+28 more)

### Community 112 - "Mobile screen source wiring tests"
Cohesion: 0.02
Nodes (73): _book_of(), part_a_card(), part_b(), _table(), test_every_revoke_names_the_roles_rather_than_public(), test_odds_keeps_select_for_the_app(), test_the_two_rls_off_tables_lose_everything(), test_the_function_revoke_names_public_as_well_as_the_roles() (+65 more)

### Community 117 - "NBA lineup stint derivation tests"
Cohesion: 0.07
Nodes (48): dead_ball_rebounds(), derive_stints(), order_plays(), possession_ends(), _blowout_q4(), derive(), dreb(), _dup_game() (+40 more)

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
Nodes (29): assemble_player_features(), _avg_finish(), build_bulk_golf_lookups(), build_golf_training_dataset(), compute_golf_target(), compute_matchup_target(), _event_finishes(), _f() (+21 more)

### Community 132 - "ncaaf_live/tests/test_states.py"
Cohesion: 0.13
Nodes (22): build_states(), _platform(), _plays(), _post_convention_game(), _pre_convention_game(), test_a_scoring_plays_state_does_not_contain_its_own_points(), test_ambiguous_convention_refuses_to_build(), test_halftime_scores_carried_for_2h_settlement() (+14 more)

### Community 133 - "tests/test_bovada_feed.py"
Cohesion: 0.10
Nodes (32): _american(), _complete(), _num(), parse_coupon(), poll_once(), _row_for(), _seen_key(), _stamp() (+24 more)

### Community 134 - "tests/test_market_movement.py"
Cohesion: 0.07
Nodes (27): american_to_prob(), build_market_features(), _is_full_game_snap(), _latest_two_sided(), load_market_movement(), _snap_sort_key(), _snapshot_type_rank(), _unique_ordered() (+19 more)

### Community 136 - "NCAAF cross-book opener rule tests"
Cohesion: 0.07
Nodes (25): _minutes_apart(), build_artifact(), build_band_artifact(), _branch(), test_absent_ceiling_means_unbounded(), test_artifact_shape(), test_band_ceiling_is_enforced_in_the_scorer(), test_band_volumes_sum_to_the_single_gate_backtest() (+17 more)

### Community 138 - "tests/test_paused_keeps_real_verdict.py"
Cohesion: 0.09
Nodes (27): _bet(), _fn(), _pause(), _prop(), _rules(), _sql_of(), _src(), test_a_paused_bet_never_takes_a_live_models_player_slot() (+19 more)

### Community 139 - "NFL in-play edge seasonal backtest"
Cohesion: 0.08
Nodes (47): books_per_snapshot(), cell(), h1(), h1_calibration(), h1_frame(), h2(), h2_accuracy(), h3_accuracy() (+39 more)

### Community 147 - "scripts/nfl_edge_extreme_props.py"
Cohesion: 0.16
Nodes (25): actuals(), add_modes(), bar(), candidates(), cell(), decision_boards(), devig(), fit_holdout() (+17 more)

### Community 148 - "scripts/nfl_edge_settlement.py"
Cohesion: 0.14
Nodes (30): add_test(), attach(), banner(), bh(), board(), boot_draws(), cell(), choose() (+22 more)

### Community 15 - "X publisher"
Cohesion: 0.03
Nodes (45): test_the_tweet_still_has_no_link(), _creds_on(), _fake_conn(), _split(), test_a_clean_ledger_allows_the_post(), test_a_day_with_nothing_graded_carries_no_clv_line(), test_a_day_with_nothing_risked_states_units_and_does_not_divide(), test_a_split_that_cannot_fit_says_how_many_it_dropped() (+37 more)

### Community 153 - "tests/test_agents_contract.py"
Cohesion: 0.06
Nodes (19): _labelled_retired(), test_blocked_items_are_marked_so_the_agent_skips_them(), test_every_backlog_item_is_a_checkbox(), test_neither_agent_may_change_a_model_threshold(), test_the_agents_are_findable_from_the_file_every_session_reads(), test_the_backlog_does_not_promise_an_agent_that_no_longer_runs(), test_the_backlog_exists_and_has_items(), test_the_contract_documents_every_agent_by_name() (+11 more)

### Community 157 - "Position vs opponent parity tests"
Cohesion: 0.07
Nodes (19): _bn_body(), _sql_groups(), test_a_failed_position_read_is_said_not_hidden(), test_a_failed_read_is_not_held_on_the_spinner(), test_every_mlb_stat_chip_has_a_branch(), test_every_nfl_stat_chip_has_a_branch(), test_every_roster_sport_chip_has_a_branch(), test_mlb_lineup_buckets_agree_between_app_and_server() (+11 more)

### Community 159 - "WNBA results and stats ingestors"
Cohesion: 0.04
Nodes (58): _default_wnba(), build_log_row(), _core_athlete(), _deref(), _et_date(), _fetch_core_box_players(), _fetch_core_games(), _fetch_scoreboard() (+50 more)

### Community 16 - "Daily pipeline runner and push notifier"
Cohesion: 0.02
Nodes (92): run_savant_ingestor(), ingest_lineups_for_date(), run_bullpen_ingestor(), run_nfl_results_ingestor(), run_player_news_ingestor(), run_nba_prop_odds_ingestor(), run_prop_odds_ingestor(), run_wnba_prop_odds_ingestor() (+84 more)

### Community 161 - "NBA box score enrichment"
Cohesion: 0.07
Nodes (49): _blank(), box_rows(), _check_unmapped(), _create(), dnp_kind(), ensure_tables(), fetch_advanced(), _flt() (+41 more)

### Community 163 - "X posting auth and database probes"
Cohesion: 0.08
Nodes (22): discover(), fetch_all(), _get_image(), main(), _original_size(), store(), _x_api_profile(), test_a_different_secret_changes_the_signature() (+14 more)

### Community 166 - "Prop box score backfill"
Cohesion: 0.12
Nodes (23): fill_missing(), _call_fill(), _cooled(), _day(), _default_nba(), _default_nfl(), _default_nhl(), _drop_logged() (+15 more)

### Community 167 - "scripts/nfl_preflight.py"
Cohesion: 0.20
Nodes (16): check(), check_cards_run(), check_config_gates(), check_cost(), check_data(), data_check(), check_import_shadowing(), check_lock_semantics() (+8 more)

### Community 168 - "Push delivery ticket tests"
Cohesion: 0.22
Nodes (10): _msgs(), test_a_credentials_failure_disables_nobody(), test_a_request_level_rejection_accepts_nothing(), test_a_retired_device_is_named_for_disabling(), test_a_single_message_reply_may_be_a_bare_object(), test_a_ticket_that_is_not_an_object_is_not_a_delivery(), test_an_error_ticket_is_not_counted_as_sent(), test_an_unpairable_reply_counts_nothing_and_disables_nothing() (+2 more)

### Community 169 - "NCAAF board visibility tests"
Cohesion: 0.12
Nodes (7): test_a_declined_rule_can_never_leak_a_signal(), test_a_no_signal_row_does_not_lock_an_ncaaf_game_for_the_week(), test_every_registered_model_has_a_feature_map_entry(), test_the_premium_tier_shares_the_spread_features(), test_the_price_prefilter_can_only_ever_skip_ncaaf(), test_the_price_prefilter_fails_open(), test_unpriced_ncaaf_games_are_skipped_before_the_feature_build()

### Community 171 - "CLV math and devig functions"
Cohesion: 0.09
Nodes (23): test_a_one_way_close_is_not_de_vigged(), test_a_worse_close_is_negative_and_equal_prices_are_zero(), test_devigging_the_taken_price_is_not_what_primary_does(), test_kalshi_close_is_not_de_vigged(), test_market_edge_devigs_only_the_close(), test_other_side_prices_include_the_draw_on_a_three_way(), test_power_devig_of_a_balanced_market_is_a_coin_flip(), test_primary_does_not_move_when_the_other_side_changes() (+15 more)

### Community 172 - "NFL in-play flow validation backtest"
Cohesion: 0.02
Nodes (124): evaluate(), _infer_position(), main(), _pool_prior(), report(), _rows_for_market(), _to_states(), bias_table() (+116 more)

### Community 173 - "tests/test_decide_on_calibrated.py"
Cohesion: 0.06
Nodes (19): _pick(), _pick_at(), test_a_calibrated_cut_is_paired_with_a_calibrated_decision(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(), test_a_genuinely_big_edge_still_fires_after_calibration(), test_a_hot_model_no_longer_fires_the_marginal_bet(), test_a_model_on_a_calibrated_cut_is_not_paused(), test_a_paused_model_never_fires_regardless() (+11 more)

### Community 176 - "NBA prop projection lab"
Cohesion: 0.09
Nodes (49): apply_calibration(), implied(), _logit(), bars(), bh_read(), blind(), boot(), by() (+41 more)

### Community 178 - "NFL edge versus luck gap study"
Cohesion: 0.10
Nodes (30): add_windows(), add_windows_fast(), bh(), binom_p(), board(), boot(), cell(), fit_points() (+22 more)

### Community 182 - "tests/test_model_artifacts_load.py"
Cohesion: 0.09
Nodes (17): _git(), _gitignore_keep_pkls(), _ignored(), _manifest_keep_pkls(), _newest_per_model(), test_a_path_that_is_not_ignored_is_not_reported(), test_a_superseded_timestamped_pkl_is_ignored(), test_an_ignored_path_comes_back_byte_identical() (+9 more)

### Community 185 - "scripts/game_line_market_sweep.py"
Cohesion: 0.08
Nodes (22): _by_month(), collect_picks(), devig(), _gap_seconds(), grade(), implied(), iter_months(), load() (+14 more)

### Community 187 - "Push notification deep link tests"
Cohesion: 0.09
Nodes (20): _code(), _py_version(), _read(), test_a_single_pick_deep_links_and_a_batch_does_not(), test_an_unreadable_payload_routes_nowhere_rather_than_guessing(), test_both_halves_pin_the_same_payload_version(), test_every_expo_message_carries_a_data_payload(), test_every_summary_producer_can_deep_link_a_single_pick() (+12 more)

### Community 188 - "tests/test_pass_instrumentation.py"
Cohesion: 0.06
Nodes (11): test_a_dead_database_does_not_fail_the_step(), test_a_raised_failure_still_records_the_exception(), test_a_step_that_raises_is_still_TIMED(), test_a_step_that_raises_still_raises(), boom(), test_a_step_that_returns_false_records_a_REASON(), test_a_successful_step_records_a_duration(), test_every_step_name_in_the_dispatch_table_is_reachable() (+3 more)

### Community 190 - "tests/test_db_adapt_sql.py"
Cohesion: 0.11
Nodes (21): _adapt_sql(), _named(), test_a_block_comment_is_skipped_too(), test_a_colon_word_inside_a_comment_is_not_a_placeholder(), test_a_dash_dash_inside_a_literal_is_data_not_a_comment(), test_a_line_comment_ends_at_the_newline(), test_a_real_param_after_a_literal_still_converts(), test_an_apostrophe_in_a_comment_does_not_swallow_a_later_literal() (+13 more)

### Community 193 - "tests/test_first_signal_repair.py"
Cohesion: 0.15
Nodes (20): patch_conn(), _sql_of(), test_a_lane_already_holding_its_first_bet_is_untouched(), test_a_lane_with_no_sibling_still_restores(), test_a_lane_with_nothing_standing_is_restored(), test_a_pregame_model_is_not_marked_live(), test_a_price_move_alone_is_a_different_bet(), test_a_restored_live_pick_stays_live() (+12 more)

### Community 194 - "NFL in-play 2025 edge report"
Cohesion: 0.10
Nodes (34): s(), fit_models(), h3(), attach_games(), attach_state(), bh(), check_possession(), diagnostics() (+26 more)

### Community 195 - "tests/test_mobile_contrast_tokens.py"
Cohesion: 0.13
Nodes (30): _code_lines(), _ionicon_colors(), _lum(), _over(), _ratio(), _read(), _rgb(), test_badge_glyph_tracks_dynamic_type() (+22 more)

### Community 197 - "NBA box score stats ingestor"
Cohesion: 0.09
Nodes (23): fill_missing_game_logs(), backfill_nba_stats(), _build_game_id(), _build_game_rows(), _build_player_log_rows(), _build_team_stat_rows(), _fetch_league_game_log(), ingest_nba_game_log_for_date() (+15 more)

### Community 201 - "NBA second game line move tests"
Cohesion: 0.06
Nodes (39): _priced_season(), _q(), _sched(), _season_games(), _signal(), _split(), _stub_main(), test_a_fetch_after_T_never_reaches_the_move() (+31 more)

### Community 208 - "NBA play-by-play game matching tests"
Cohesion: 0.08
Nodes (23): _last(), match_games(), match_names(), _g(), _rec(), _summary(), test_a_gap_game_found_a_day_off_is_dated_by_our_games_row(), test_a_gap_game_is_found_by_its_teams_a_day_off_and_never_twice() (+15 more)

### Community 21 - "NFL edge research shared toolkit"
Cohesion: 0.04
Nodes (81): backfill_cost(), bets(), bh(), clean_2h(), fmt(), forward_2026(), hdr(), _line_models() (+73 more)

### Community 216 - "Free pick cheaper book tests"
Cohesion: 0.11
Nodes (12): _pick(), test_a_pick_with_no_alternative_falls_back_to_draftkings(), test_every_offerable_book_has_a_human_name_on_both_surfaces(), test_the_free_card_names_the_cheaper_book(), test_the_free_card_query_reads_the_columns_it_renders(), test_the_good_to_clause_is_dropped_not_truncated_when_it_will_not_fit(), test_the_tweet_names_the_cheaper_book(), test_the_tweet_never_publishes_a_worse_price_than_draftkings() (+4 more)

### Community 218 - "SQL safety and pick row tests"
Cohesion: 0.05
Nodes (24): _identity_maps(), _platform_gates_off(), test_breakeven_is_the_real_vig_hurdle(), _statements(), test_columns_and_values_line_up(), test_the_scorer_pick_insert_is_actually_covered(), _derive(), _frame() (+16 more)

### Community 219 - "tests/test_nfl_live_leader_state.py"
Cohesion: 0.13
Nodes (19): situation(), status(), test_a_conversion_try_is_skipped(), test_a_previous_quarters_play_is_not_the_state(), test_a_timeout_is_skipped_for_the_play_before_it(), test_after_a_scoring_play_nothing_is_evaluated(), test_after_the_kickoff_lands_the_receiver_has_the_ball(), test_an_ordinary_snap_is_evaluable_with_the_training_inputs() (+11 more)

### Community 221 - "tests/test_ncaaf_qb_ingestor.py"
Cohesion: 0.11
Nodes (24): _athlete_stats(), _comp_att(), parse_qb_game_stats(), _split_ratio(), test_split_ratio(), _parse(), _payload(), _team() (+16 more)

### Community 224 - "NBA derivative market lab"
Cohesion: 0.09
Nodes (35): add_team(), am_to_dec(), bars_for(), bet_list(), blind(), boot_ci(), build_line_rows(), build_outcomes() (+27 more)

### Community 229 - "NBA prop model verification script"
Cohesion: 0.12
Nodes (29): adv_from_log(), asof_roster(), blind_structured(), card_block(), collapse_report(), _compare(), log(), main() (+21 more)

### Community 232 - "Mobile pick category tests"
Cohesion: 0.11
Nodes (13): _block(), _config_scorable_ids(), _meta_ids(), _meta_types(), _read(), test_every_model_id_derives_its_own_declared_category(), test_every_scorable_model_has_a_label_in_the_app(), test_picks_idle_chrome_is_search_and_filters_only() (+5 more)

### Community 235 - "NCAAF feature engine tests"
Cohesion: 0.05
Nodes (40): _assemble_ncaaf_features(), _blk_points_l3(), _blk_stats(), build_bulk_ncaaf_lookups(), build_ncaaf_features_from_bulk(), _game_tier(), haversine_miles(), shrink_hfa() (+32 more)

### Community 240 - "tests/test_ncaaf_game_identity.py"
Cohesion: 0.12
Nodes (16): _add(), _conn(), _identity_sql(), _run(), test_a_clean_slate_reports_nothing(), test_a_non_fbs_fixture_is_not_reported(), test_a_phantom_opponent_is_detected_too(), test_a_real_doubleheader_is_not_a_duplicate() (+8 more)

### Community 241 - "NBA second game market tests"
Cohesion: 0.10
Nodes (27): _close_frames(), _data(), _f2_games(), _f6a_data(), _f6d_total_data(), _game(), _pe(), _q() (+19 more)

### Community 25 - "NBA game rule testing harness"
Cohesion: 0.06
Nodes (38): attach_fetch(), blind_by_real_side(), blind_side(), boot(), cell_report(), cents(), check(), choose() (+30 more)

### Community 250 - "data/ingestors/nhl_boxscore.py"
Cohesion: 0.12
Nodes (16): _decision(), fill_missing(), _insert_absent(), _int(), _name(), parse_boxscore(), side_rows(), store_boxscore() (+8 more)

### Community 255 - "NFL prop tick and NCAAF underdog calibration"
Cohesion: 0.10
Nodes (13): bucket(), label(), main(), table(), wilson(), test_days_is_derived_from_the_window_not_pinned(), test_every_live_nfl_prop_model_still_carries_its_own_cut(), test_the_live_ten_are_not_a_clean_bill_of_health() (+5 more)

### Community 259 - "NFL kickoff wind card"
Cohesion: 0.12
Nodes (14): dump_eval_rows(), coverage_check(), expected_true_wind(), open_air_mask(), wind_at_kickoff(), load_nfl_model(), cached_totals(), issued_wind() (+6 more)

### Community 260 - "tests/test_live_game_features.py"
Cohesion: 0.11
Nodes (19): compute_live_target(), half_innings_left(), parse_bases(), state_features(), test_build_live_state_row_merges_pregame_context(), test_build_live_state_row_unusable_state(), test_half_innings_left_bottom_ninth(), test_half_innings_left_extras_clamps_to_one() (+11 more)

### Community 261 - "tests/test_ncaaf_totals_regression.py"
Cohesion: 0.09
Nodes (15): margin_cover_prob(), total_over_prob(), test_artifact_kind_is_routed_by_the_scorer(), test_asymmetry_is_real_and_would_have_bitten(), test_extremes_are_clamped_away_from_certainty(), test_model_above_the_line_favours_the_over(), test_model_below_the_line_favours_the_under(), test_no_dk_total_means_skip_not_prob_only() (+7 more)

### Community 262 - "UFC feature engine and tests"
Cohesion: 0.13
Nodes (20): _age_years(), _assemble_ufc_features(), career_stats(), compute_ufc_target(), infer_five_rounds(), synthetic_round_total(), _fight(), _stats_pair() (+12 more)

### Community 263 - "Source reading guard tests"
Cohesion: 0.04
Nodes (35): test_a_published_void_keeps_track_and_betslip(), test_a_tracked_void_reads_not_graded_and_detail_closes_when_over(), test_the_app_predicate_matches(), test_today_et_ignores_the_container_timezone(), _read(), _run(), test_a_stale_card_offers_no_bet(), test_a_stale_card_says_why_and_speaks_the_locked_price() (+27 more)

### Community 266 - "NCAAF in-play history backtest"
Cohesion: 0.08
Nodes (19): out_path(), build_candidates(), decide(), first_signals(), _fmt(), grade(), load_snapshots(), main() (+11 more)

### Community 267 - "tests/test_ncaaf_qb_features.py"
Cohesion: 0.12
Nodes (24): build_qb_team_features(), load_qb_games(), merge_qb_features(), _feat(), _frame(), _games(), _qb_rows(), _qb_team() (+16 more)

### Community 270 - "Prop ladder interpolation tests"
Cohesion: 0.09
Nodes (19): from_one_sided_overs(), _ladder(), test_a_clean_ladder_is_not_reported_as_repaired(), test_a_one_sided_ladder_is_vigged_and_says_so(), test_a_quoted_strike_returns_its_own_mid(), test_a_thin_one_sided_ladder_cannot_be_anchored(), test_an_unquoted_line_interpolates_between_its_neighbours(), test_anchoring_moves_the_ladder_onto_an_honest_point() (+11 more)

### Community 271 - "Line CLV sign and orientation tests"
Cohesion: 0.06
Nodes (11): test_runner_captures_stdout_from_the_script_main(), test_sport_and_market_are_bounded(), test_the_declared_key_is_present_and_valid(), test_the_runner_imports_the_script_main_not_a_shell(), _load(), test_a_line_that_held_is_exactly_zero_not_none(), test_a_missing_close_is_not_a_zero(), test_a_side_that_cannot_be_oriented_returns_none_rather_than_guessing() (+3 more)

### Community 272 - "tests/test_mobile_team_detail.py"
Cohesion: 0.11
Nodes (15): _read(), test_every_team_page_read_names_its_relation_literally(), test_next_game_is_earliest_in_the_window_not_tonights_date(), test_no_paper_trading_copy(), test_public_betting_policy_migration_exists_and_is_select_only(), test_recent_games_are_scoped_by_sport(), test_results_are_units_never_dollars(), test_sharp_gap_is_no_vig_vs_no_vig() (+7 more)

### Community 275 - "NBA game harness tests"
Cohesion: 0.08
Nodes (26): _cov_data(), _fetches(), _games(), _offers(), _q(), _stale_cache(), test_a_graded_load_refuses_a_season_the_cache_does_not_price(), test_a_graded_load_refuses_rows_that_match_no_purchase() (+18 more)

### Community 276 - "NBA ESPN box score parsing"
Cohesion: 0.09
Nodes (20): box_team_totals(), _no_minutes(), parse_nba_box(), parse_nba_dnp(), parse_nba_scoreboard(), _played(), _team_blocks(), board() (+12 more)

### Community 279 - "EV floor replay and honest cut sweep"
Cohesion: 0.12
Nodes (20): _in_graded_matview(), _is_live_lane(), _era(), grade(), wilson(), _cell(), _decimal(), fetch_rows() (+12 more)

### Community 280 - "MLB live game state trigger tests"
Cohesion: 0.12
Nodes (23): _bases_state(), _detect_triggers(), _extract_state(), _is_active_or_starting_soon(), test_active_in_progress_game_is_active(), test_bases_state_empty(), test_bases_state_loaded(), test_bases_state_single_runner() (+15 more)

### Community 283 - "NCAAF play-by-play state builder"
Cohesion: 0.16
Nodes (11): main(), _classify(), classify_report(), _detect_score_convention(), load_pbp(), load_platform_games(), pace_report(), _repair_day_offsets() (+3 more)

### Community 286 - "Kalshi prop ladder recording"
Cohesion: 0.07
Nodes (8): test_a_kalshi_outage_cannot_break_the_pass(), test_a_run_is_idempotent_within_its_snapshot(), test_one_snapshot_timestamp_for_the_whole_run(), test_the_recorder_is_scheduled_on_the_pipeline_role(), test_the_recorder_keeps_raw_prices_not_a_filtered_ladder(), test_the_recorder_walks_every_mapped_series(), _loose_summary(), s()

### Community 287 - "Model calibration check tests"
Cohesion: 0.09
Nodes (12): _calibration_sql(), test_a_flagged_model_is_named_eligible_or_not(), test_a_thin_model_is_still_excluded_rather_than_accused(), test_eligibility_notes_must_not_sink_the_gap_check(), test_eligibility_notes_parse_the_payload_verdicts(), test_it_grades_the_calibrated_probability_not_the_raw_one(), test_it_joins_picks_to_reach_the_calibrated_column(), test_the_check_has_a_skip_budget_that_survives_a_regime_change() (+4 more)

### Community 289 - "Calibration fit job and health"
Cohesion: 0.11
Nodes (17): demote(), ensure_schema(), _era_start(), fit_offset(), fit_platt(), fit_pool(), _gap_pp(), invert_calibration() (+9 more)

### Community 29 - "NCAAF college data ingestor"
Cohesion: 0.05
Nodes (46): backfill_ncaaf_lines(), backfill_ncaaf_players(), backfill_ncaaf_qb(), _existing_ncaaf_ids(), _get(), ingest_ncaaf_game_log(), ingest_ncaaf_games(), ingest_ncaaf_lines() (+38 more)

### Community 290 - "NBA second game model verdict"
Cohesion: 0.18
Nodes (9): axes_of(), bar9(), cell_key(), _floats(), load_cells(), main(), plateau_ok(), verdict() (+1 more)

### Community 293 - "Historical odds backfill and first pitch"
Cohesion: 0.02
Nodes (59): _ledger_entry_is_resumable(), _mark_in_play(), relabel_in_play(), run_historical_odds_range(), test_capture_compares_the_picks_own_clock_not_the_capture_clock(), test_capture_fails_open_on_a_missing_timestamp(), test_the_dry_run_count_uses_the_same_predicate_as_the_insert(), test_the_restatement_path_is_deliberately_not_guarded() (+51 more)

### Community 294 - "NCAAF player stats parser tests"
Cohesion: 0.18
Nodes (17): parse_player_game_stats(), _cat(), _parse(), _payload(), _team(), test_a_game_missing_from_the_id_map_is_skipped_not_guessed(), test_a_player_gets_one_row_across_every_category(), test_a_player_with_nothing_we_track_is_skipped() (+9 more)

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

### Community 317 - "Latest line state and Citadel migration cluster tests"
Cohesion: 0.06
Nodes (35): main(), can_scratch(), env_dsn(), _free_port(), pg_bin(), scratch_cluster(), as_app(), db() (+27 more)

### Community 318 - "tests/test_live_record_start_views.py"
Cohesion: 0.09
Nodes (12): _body(), _code(), test_both_published_views_carry_the_live_date_gate(), test_it_runs_after_the_migration_that_used_to_own_the_daily_view(), test_migration_is_one_statement(), test_migration_is_registered_with_the_worker_runner(), test_neither_view_reads_the_sweep_universe(), test_no_ddl_outside_the_guarded_branches() (+4 more)

### Community 319 - "Model quality degradation monitor"
Cohesion: 0.10
Nodes (17): record_exclusion_sql(), test_clv_clear_negative_vs_baseline_is_flagged(), test_raw_one_sided_clv_is_ignored(), test_roi_collapse_is_crit_when_hit_rate_dies(), test_roi_ignores_unpriced_profit_flat(), test_the_exclusion_sql_is_a_conjunction_of_negations(), detect_clv_degradation(), detect_roi_collapse() (+9 more)

### Community 326 - "tests/test_api_call_rollup.py"
Cohesion: 0.08
Nodes (10): test_a_fold_can_never_lower_a_stored_total(), test_a_new_process_does_not_prune_on_its_first_flush(), test_prune_rolls_up_before_it_deletes(), test_the_daily_table_is_created_and_locked_down(), test_the_daily_table_keys_on_day_api_and_source(), test_the_rollup_groups_by_eastern_day_not_utc(), test_the_rollup_reads_only_yesterday_and_today(), test_the_rollup_survives_a_failure_without_blocking_the_prune() (+2 more)

### Community 327 - "NFL wind forecast persistence study"
Cohesion: 0.15
Nodes (17): attach_issued(), _fmt(), load_games(), main(), report(), _under_rate(), tracking.paper_tracker (_NFL_MODEL_MARKETS), scripts/nfl_rule_2026_track (+9 more)

### Community 329 - "nfl/models/opener_spread.py"
Cohesion: 0.14
Nodes (11): age_tag(), american_to_prob(), _bettable_books(), clean_board(), edge_tier(), evaluate_board(), held_minutes(), model_prob_for_dev() (+3 more)

### Community 33 - "nfl/live_model/feeds: test_feed_resilience + espn"
Cohesion: 0.07
Nodes (33): _competitors(), _deref(), fetch_live_events(), _https(), make_fetcher(), fetch(), parse_core_event(), _score() (+25 more)

### Community 331 - "NHL prop backtest and EV lab"
Cohesion: 0.09
Nodes (28): books(), build_frame(), load_players(), load_teams(), card(), claimed_vs_realised(), day_interval(), line() (+20 more)

### Community 332 - "Live slate midnight date tests"
Cohesion: 0.07
Nodes (16): live_slate_dates(), _slate_dates(), _at(), test_both_live_loops_share_one_definition_of_the_slate(), test_by_daytime_yesterday_is_dropped(), test_discovery_asks_statsapi_about_every_date_it_is_given(), fake_schedule(), test_discovery_still_accepts_a_bare_string() (+8 more)

### Community 333 - "tests/test_nfl_wind_fire_window.py"
Cohesion: 0.07
Nodes (18): _retractable_slate(), _slate(), test_a_blank_roof_at_a_NON_retractable_venue_is_unaffected(), test_a_closed_roof_is_still_indoor(), test_a_retractable_venue_with_an_unknown_roof_does_not_fire(), test_a_waiting_game_is_not_reported_as_a_collapsed_premise(), test_a_waiting_row_keeps_its_line_price_and_edge(), test_every_blank_roof_row_is_a_retractable_venue() (+10 more)

### Community 334 - "WNBA prop player feature engine"
Cohesion: 0.10
Nodes (20): is_starter_tier(), rotation_rank(), _build_player_row(), build_wnba_prop_scoring_rows(), _context_features_for(), _opp_team_stat(), _recent_starter(), _rest_days() (+12 more)

### Community 335 - "tests/test_public_betting_ingestor.py"
Cohesion: 0.15
Nodes (18): parse_public_betting(), _pct(), probe(), _select_book(), _make_game(), test_parse_emits_six_rows(), test_parse_game_id_and_sides(), test_parse_marks_source_and_snapshot() (+10 more)

### Community 336 - "NCAAF totals lead and consensus gate"
Cohesion: 0.17
Nodes (16): fmt(), grade(), load_closes(), main(), match(), build_lead_table(), first_cross(), fmt() (+8 more)

### Community 339 - "tests/test_service_role_split.py"
Cohesion: 0.15
Nodes (11): _all_job_ids(), _sched(), test_an_unknown_role_runs_everything(), test_every_add_job_call_passes_an_id(), test_every_job_is_owned_by_exactly_one_role(), test_the_always_on_jobs_run_on_every_role(), test_the_default_preserves_the_single_container(), test_the_nfl_worker_stays_with_the_volume() (+3 more)

### Community 343 - "tests/test_http_timeout_floor.py"
Cohesion: 0.11
Nodes (11): install_timeout_floor(), _call(), clean_requests(), test_a_call_with_no_timeout_gets_one(), test_an_explicit_timeout_is_never_overridden(), test_installing_twice_is_a_no_op(), test_the_deadline_is_env_overridable(), test_the_deadline_survives_telemetry_being_turned_off() (+3 more)

### Community 345 - "Model quality public fade tests"
Cohesion: 0.10
Nodes (9): _bet(), test_high_public_pct_on_a_fade_publisher_counts_as_a_fade(), test_low_public_pct_on_the_pick_side_counts_as_a_fade(), test_majority_share_warns_when_not_unanimous(), test_meta_steps_exclude_model_quality(), test_pipeline_step_never_fails_on_crit(), test_pipeline_step_never_fails_on_exception(), test_side_aliases_collapse_to_the_same_direction() (+1 more)

### Community 346 - "NFL edge cache and feed probe"
Cohesion: 0.09
Nodes (28): backfill_savant_stats(), _fetch_pitcher_gb_pct(), _fetch_bat_hands(), _get(), dump_vendor(), _get(), _is_live(), _key() (+20 more)

### Community 347 - "Paused model profitability assessment"
Cohesion: 0.10
Nodes (15): _auto_paused_models(), active_era(), assess(), _half(), fetch(), grade(), main(), sweep() (+7 more)

### Community 35 - "NBA second game projection tests"
Cohesion: 0.07
Nodes (16): _cons(), _dist(), _neutral(), _segments(), test_f1_is_priced_through_the_projections_own_error_not_the_markets(), test_f1b_does_not_score_a_books_number_off_the_consensus(), test_f1b_strength_is_the_predicted_move_in_the_sides_favour(), test_the_consensus_number_is_pinnacles_else_the_deciding_books_median() (+8 more)

### Community 351 - "Slate concentration and fade risk detection"
Cohesion: 0.11
Nodes (17): _fade_slate(), test_a_mixed_slate_is_ok(), test_all_home_ncaaf_slate_is_flagged_without_mlb_hardcoding(), test_all_unders_public_fade_risk_is_crit(), test_all_unders_public_fade_slate_is_crit(), test_fade_in_the_model_id_is_sport_agnostic(), test_thin_slate_is_not_a_finding(), test_unanimous_but_small_slate_is_warn_not_crit() (+9 more)

### Community 352 - "NHL prop odds alternate line tests"
Cohesion: 0.06
Nodes (23): due(), _event_props(), _book(), test_a_200_on_both_calls_merges_the_alternate_lines(), fake_fetch(), test_a_game_first_priced_inside_the_final_window_gets_nothing_more(), test_a_game_first_priced_inside_the_window_gets_one_decision_snapshot(), test_a_game_with_nothing_stored_is_owed_its_open() (+15 more)

### Community 357 - "NCAAF team game stats parsing"
Cohesion: 0.09
Nodes (15): _loose_orientation(), ncaaf_slug(), parse_team_game_stats(), _possession_seconds(), _slug_extends(), _slug_pair(), _to_int(), test_an_fcs_name_that_extends_an_fbs_school_passes_through_unresolved() (+7 more)

### Community 358 - "NCAAF in-play ESPN feed parsing"
Cohesion: 0.17
Nodes (16): check_feed_assumptions(), _competitors(), _count_plays(), _dig(), extract_live_events(), extract_summary_state(), _int(), _num() (+8 more)

### Community 36 - "NCAAF CFBD ingestor tests"
Cohesion: 0.03
Nodes (49): build_ncaaf_game_id(), _day_before(), eastern_game_date(), _local_aggregates(), parse_lines(), shrink_to_prior(), _stamp_game_identity(), _stat_row() (+41 more)

### Community 360 - "NFL in-play pick writer"
Cohesion: 0.13
Nodes (7): _is_market_opinion(), _lane_is_locked(), _norm_player(), resolve_game(), resolve_game_id(), test_normalised_player_key_is_the_join_the_prop_system_uses(), test_the_lane_lock_shares_the_scorers_meaning_of_locked()

### Community 361 - "tests/test_config.py"
Cohesion: 0.08
Nodes (8): test_an_own_floor_does_not_take_a_model_off_the_calibration_map(), test_every_model_carries_its_own_thresholds(), test_every_own_floor_names_a_live_model(), test_models_on_own_probability_is_not_derived_from_the_floor_dict(), test_no_own_floor_tightens_a_model_past_the_global_floor(), test_only_a_market_priced_model_carries_a_negative_floor(), test_own_ev_floor_and_model_min_ev_stay_disjoint(), test_the_models_the_global_floor_silently_removed_can_bet_again()

### Community 366 - "Kalshi game market recorder"
Cohesion: 0.09
Nodes (8): run_kalshi_game_record(), test_a_kalshi_outage_cannot_break_the_pass(), test_event_code_is_shared_across_series(), test_event_date_is_searched_not_anchored(), test_kalshi_labels_expand_st_and_use_the_explicit_map(), test_resolution_runs_after_every_snapshot(), test_the_recorder_is_scheduled_on_the_pipeline_role(), test_the_recorder_keeps_raw_contracts()

### Community 367 - "Database URL doctor tests"
Cohesion: 0.16
Nodes (17): diagnose(), bad(), _safe(), _fails(), _levels(), test_a_correct_url_reports_no_failures(), test_bare_postgres_on_a_DIRECT_host_is_fine(), test_bare_postgres_on_a_pooler_host_is_named() (+9 more)

### Community 369 - "UFC fighter name resolution"
Cohesion: 0.16
Nodes (11): resolve_slug(), _slug_tokens(), test_a_generational_suffix_resolves_either_way(), test_a_near_miss_is_not_a_match(), test_a_reversed_name_order_resolves(), test_a_shared_surname_alone_is_not_a_match(), test_an_ambiguous_token_set_resolves_to_nothing(), test_an_empty_or_tokenless_name_is_safe() (+3 more)

### Community 370 - "UFC fight history loader"
Cohesion: 0.10
Nodes (24): _aggregate_stats(), backfill_ufc_csv(), build_events(), build_fighter_index(), _heal_window_lo(), ingest_ufc_results_for_date_csv(), _kd_int(), load_fighter_profiles_from_csv() (+16 more)

### Community 371 - "tests/test_team_stats_asof_invariants.py"
Cohesion: 0.08
Nodes (14): impossible_games_played(), _played_actual(), test_a_missing_count_is_reported_not_silently_passed(), test_an_honest_row_passes(), test_claiming_fewer_games_than_played_is_fine(), test_feb_gp_climbing_vs_zero_regular_season_still_fails(), test_mlb_twin_codes_do_not_false_crit(), test_mlb_twin_reverse_lookup_also_resolves() (+6 more)

### Community 373 - "NBA second game projection fixtures"
Cohesion: 0.18
Nodes (22): _box(), _games(), _inj(), _rapm_inputs(), _segment_rows(), _state(), test_a_back_to_back_is_read_from_the_schedule(), test_a_game_gets_no_projection_while_a_previous_date_game_could_still_be_running() (+14 more)

### Community 375 - "Refresh pass step ordering tests"
Cohesion: 0.10
Nodes (13): _order(), test_a_parallel_step_that_fails_is_still_recorded(), test_no_sequential_step_runs_while_a_parallel_group_is_open(), test_opening_signals_follows_every_scorer(), test_parlay_follows_opening_signals(), test_scoring_follows_every_ingest(), test_settle_follows_every_results_ingest(), test_sync_thresholds_follows_migrations_and_precedes_scoring() (+5 more)

### Community 379 - "NBA historical odds archive parser"
Cohesion: 0.14
Nodes (19): classify(), fetch_all(), _fold(), _is_half(), _num(), parse_season(), _price(), team() (+11 more)

### Community 382 - "UFC event stats ingestor"
Cohesion: 0.09
Nodes (19): backfill_ufc_stats(), _build_ufc_game_id(), _fetch_event(), _fetch_event_list(), _fetch_fight(), _fetch_fighter(), _get(), _home_win_for_row() (+11 more)

### Community 383 - "Mobile tracked performance checks"
Cohesion: 0.10
Nodes (18): dup, empty, half, l50, loss, noAction, open1, open2 (+10 more)

### Community 384 - "tests/test_mobile_threshold_parity.py"
Cohesion: 0.16
Nodes (12): _block(), _canonical(), _mirror(), _mirror_paused(), _src(), test_every_cut_matches_config(), test_every_scorable_model_is_in_the_app_mirror(), test_the_app_mirror_holds_no_model_config_cannot_score() (+4 more)

### Community 385 - "Sub-ten-second live path tests"
Cohesion: 0.09
Nodes (11): test_a_quote_already_seen_does_not_count_as_a_move(), test_a_scoring_failure_never_kills_the_feed(), test_poll_once_reports_which_games_moved(), test_scoring_is_opt_in(), test_scoring_runs_in_the_same_tick_as_the_write(), test_the_budget_is_written_down_where_it_can_be_checked(), test_the_expected_consequence_is_stated(), test_the_loop_sleeps_the_REMAINDER_of_the_interval() (+3 more)

### Community 386 - "NHL derivative odds job validation tests"
Cohesion: 0.12
Nodes (9): test_a_credit_ceiling_is_a_malformed_request(), test_apply_argv_is_only_apply(), test_apply_is_explicit_and_carries_no_ceiling(), test_dry_run_argv_has_no_apply_and_no_ceiling(), capture(), test_empty_args_are_a_dry_run(), test_probe_argv_does_not_apply(), _job_nhl_derivative_odds_history() (+1 more)

### Community 388 - "tests/test_track_record_views.py"
Cohesion: 0.11
Nodes (10): _body(), _code(), test_migration_is_one_statement(), test_migration_is_registered_with_the_worker_runner(), test_no_ddl_outside_the_guarded_branches(), test_refresh_pass_refreshes_outcomes_after_settle(), test_the_daily_view_is_no_longer_redefined_here(), test_the_full_outcome_view_reads_the_matview_and_never_the_player_logs() (+2 more)

### Community 389 - "tests/test_weekly_catch_up.py"
Cohesion: 0.12
Nodes (10): sched(), test_a_fresh_savant_does_not_suppress_the_calibration_catch_up(), test_a_missing_sweeps_table_counts_as_stale(), test_a_recent_sweep_does_not(), test_an_old_sweep_triggers_the_catch_up(), test_model_calibration_belongs_to_the_pipeline_service(), test_the_catch_up_creates_the_review_tables_on_boot(), test_the_review_schema_is_not_gated_by_owns() (+2 more)

### Community 392 - "Discord price bound tests"
Cohesion: 0.11
Nodes (13): _dec(), test_a_field_without_a_bound_renders_without_the_clause(), test_a_model_with_no_own_ev_floor_is_bound_by_the_global_one(), test_a_price_floor_can_be_the_binding_gate(), test_a_rounded_bound_still_clears_the_bound_it_came_from(), test_even_money_is_plus_one_hundred(), test_no_bound_from_junk_rather_than_a_guess(), test_no_bound_when_the_edge_floor_is_unreachable() (+5 more)

### Community 396 - "MLB public fade top-K holdout"
Cohesion: 0.15
Nodes (14): bucket_win_rates(), build_candidates(), _fmt(), holdout_take(), load_db(), load_json(), lomo_rates(), main() (+6 more)

### Community 398 - "NBA game market gap analysis"
Cohesion: 0.15
Nodes (13): fair_offers(), probs_any(), side_probs(), with_ev(), attach_close(), dec(), gap_candidates(), probs_at() (+5 more)

### Community 399 - "NFL live leader model tests"
Cohesion: 0.10
Nodes (19): fit_wp(), logit_irls(), wp_design(), wp_lookup(), art(), _d(), _raw(), test_600_seconds_and_both_lead_ends_are_inside() (+11 more)

### Community 40 - "NFL wind edge studies"
Cohesion: 0.10
Nodes (42): band_table(), bh(), build_priced(), decisions_2026(), decisions_hist(), era5_hourly(), fc_at_decision(), fetch_2026() (+34 more)

### Community 400 - "Mobile paused catalog tests"
Cohesion: 0.16
Nodes (11): _block(), _read(), test_paused_picks_reach_the_all_board_only_and_labelled(), test_stats_add_pick_refuses_a_paused_model(), test_the_behavioural_checks_pass(), test_the_bet_type_picker_filters_paused_models(), test_the_custom_model_picker_is_three_bet_types(), test_the_models_list_filters_paused_models() (+3 more)

### Community 401 - "NFL in-play prop rule and staleness studies"
Cohesion: 0.19
Nodes (11): american_b(), boot_roi(), first_per_player(), grade(), load(), main(), report(), main() (+3 more)

### Community 403 - "Mobile sport filter tests"
Cohesion: 0.14
Nodes (10): _load_body(), _sports(), _src(), test_a_visit_scoped_sport_change_does_not_persist(), test_a_writer_landing_during_the_hydrate_is_not_overwritten(), test_every_sport_survives_a_cold_start(), test_no_retired_sport_is_a_selectable_chip(), test_no_second_hand_written_sport_list_in_the_hook() (+2 more)

### Community 404 - "tests/test_promote_calibration_job.py"
Cohesion: 0.11
Nodes (3): test_a_refused_model_rolls_back_and_raises(), test_a_successful_promote_commits(), _job_promote_calibration()

### Community 406 - "tests/test_cfbd_snapshot_leakage.py"
Cohesion: 0.16
Nodes (9): _completed_before(), _ohio_state_2024(), test_boundary_is_strict(), test_datetime_like_values_are_handled(), test_empty_input(), test_end_of_regular_season_snapshot_excludes_playoffs(), test_missing_or_malformed_dates_are_dropped_not_admitted(), test_postseason_excluded_from_early_season_snapshot() (+1 more)

### Community 410 - "NBA game rule grid sections"
Cohesion: 0.16
Nodes (13): bars(), bet_frame(), boot_ci(), by_season(), cell_row(), first_qualifying(), fit_sigma(), halves() (+5 more)

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
Cohesion: 0.14
Nodes (9): test_capture_clv_requires_the_game_to_have_started(), test_future_kickoffs_are_not_treated_as_started(), test_game_log_skips_per_game_not_per_date(), test_mirror_unchanged_is_conservative_when_it_cannot_tell(), test_started_games_are_recognised_in_every_stored_format(), test_ufc_poll_uses_the_etag_gate_and_the_daily_run_does_not(), test_unparseable_timestamps_yield_none_rather_than_a_guess(), test_z_and_offset_forms_are_the_same_instant_but_not_the_same_string() (+1 more)

### Community 416 - "UFC stats ingestor and fighters"
Cohesion: 0.08
Nodes (26): normalize_method(), rounds_completed(), slugify_fighter(), _fight_minutes(), _resolve(), test_a_misspelled_fighter_is_scored_for_the_side_they_fought_on(), test_alias_makes_both_sources_agree(), test_aliases_do_not_touch_unmapped_names() (+18 more)

### Community 418 - "Mobile source checks run under node"
Cohesion: 0.05
Nodes (41): node_exe(), node_strips_types(), _app(), _clv_card(), _node_strips_types(), _server(), test_a_label_book_nfl_pick_compares_its_line_with_that_book(), test_a_recorded_book_differs_from_the_derived_one() (+33 more)

### Community 42 - "DataGolf ingestor and NHL SBR archive"
Cohesion: 0.05
Nodes (48): _american(), backfill_golf_rounds(), build_game_id(), _dg_get(), _earliest_commence_iso(), _event_meta_lookup(), event_slug(), ingest_golf_field() (+40 more)

### Community 421 - "Paused and no-signal pick rows"
Cohesion: 0.14
Nodes (11): _apply_no_signal(), _game_pick(), _prop_pick(), test_auto_paused_counts_as_paused(), test_no_signal_rows_persist_the_reason(), test_paused_game_model_avoid_stays_avoid_with_reason(), test_paused_game_model_bet_stays_bet_with_reason_and_stake(), test_paused_prop_model_avoid_stays_avoid_with_reason() (+3 more)

### Community 425 - "NFL odds cache import to Supabase"
Cohesion: 0.09
Nodes (16): game_index(), main(), resolve(), rows_from_file(), stored_pairs(), stored_served(), _ts(), _allowed() (+8 more)

### Community 426 - "tests/test_health_check_observe.py"
Cohesion: 0.14
Nodes (10): _crit(), fake(), test_a_crit_does_not_fail_the_observe_path(), test_a_crit_still_fails_the_daily_step(), test_an_exception_does_not_fail_the_observe_path(), test_daily_syncs_thresholds_after_view_migrations(), test_it_still_runs_the_check_when_observing(), test_ok_is_identity_in_both_modes() (+2 more)

### Community 427 - "NBA second game quality and smoke runs"
Cohesion: 0.15
Nodes (11): full(), load_world(), main(), pd_baseline(), quality(), ratings_used(), ref_games(), refuse() (+3 more)

### Community 428 - "NFL 2026 opener and wind tracker"
Cohesion: 0.09
Nodes (28): classify(), fetch(), grade_rows(), is_void(), lead_days(), _load_nfl_model(), main(), opener_verdict() (+20 more)

### Community 429 - "NFL weather edge and prop assessment"
Cohesion: 0.02
Nodes (87): coerce_numeric_features(), feature_matrix(), load_games(), main(), pivot_spreads(), pivot_totals(), load_games(), main() (+79 more)

### Community 430 - "NFL live pick writer tests"
Cohesion: 0.10
Nodes (9): _executor_min_price(), _probe_config(), test_the_ceiling_is_a_refusal_not_a_filter(), test_the_insert_tolerates_the_one_row_per_pick_index(), test_the_lane_can_actually_settle(), test_the_lane_refuses_a_quote_past_the_ceiling(), test_the_lock_is_scoped_by_player_not_just_by_game(), test_the_retired_model_carries_no_threshold_row() (+1 more)

### Community 431 - "tests/test_pick_lock_is_on_picks.py"
Cohesion: 0.16
Nodes (9): _between(), _sql(), test_a_bet_is_still_never_re_scored(), test_only_a_bet_locks_a_pair(), test_the_cleanup_covers_the_whole_look_ahead_window(), test_the_cleanup_never_touches_a_started_game_or_a_live_row(), test_the_lock_is_no_longer_ncaaf_specific(), test_the_prop_and_live_locks_are_unchanged() (+1 more)

### Community 434 - "NCAAF opener rule scoring tests"
Cohesion: 0.15
Nodes (11): _line(), _patch(), test_a_fired_pick_clears_its_own_probability_floor(), test_books_agreeing_is_a_no_signal_row(), test_dk_off_its_opener_is_a_no_signal_row(), test_missing_sharp_opener_is_a_no_signal_row(), test_no_current_dk_line_writes_nothing(), test_the_band_ceiling_writes_nothing() (+3 more)

### Community 436 - "Env file fallback reader"
Cohesion: 0.12
Nodes (13): _classes(), main(), database_url(), _default_env_path(), env_value(), parse_env_file(), test_a_missing_env_file_is_empty_not_an_error(), test_a_value_containing_equals_survives() (+5 more)

### Community 439 - "tests/test_team_stats_asof_invariants.py"
Cohesion: 0.14
Nodes (11): build_rows(), _game(), test_a_row_never_includes_its_own_date(), test_counts_accumulate_across_dates(), test_every_emitted_column_exists_in_the_real_table(), columns_of(), test_every_sport_uses_its_own_scoring_noun(), test_home_and_away_splits_use_only_the_relevant_games() (+3 more)

### Community 44 - "scripts: build_nfl_live_leader_artifact + model"
Cohesion: 0.09
Nodes (26): wp_design(), wp_lookup(), attach_games(), build_artifact(), check_possession(), _dk_pregame_spread(), _download(), _first_bets() (+18 more)

### Community 440 - "House juice minimum odds floor tests"
Cohesion: 0.08
Nodes (19): min_odds_for(), _blocked_by_min_odds(), _apply_price_floor(), test_a_pick_with_no_price_is_never_blocked_by_the_floor(), test_an_explicit_floor_wins_in_BOTH_directions(), test_every_registered_model_has_an_effective_floor(), test_ordinary_prices_still_fire(), test_the_default_is_overridable_without_a_code_change() (+11 more)

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

### Community 458 - "Live monitor dashboard cache and docs"
Cohesion: 0.17
Nodes (9): age(), cached(), clear(), test_cache_raises_when_it_has_nothing_to_fall_back_on(), test_cache_reports_age(), test_cache_serves_stale_rather_than_failing(), boom(), test_cache_serves_within_ttl_and_recomputes_after() (+1 more)

### Community 46 - "Worker job queue and retrain jobs"
Cohesion: 0.02
Nodes (43): derive_first_pitch(), backfill_player_game_log(), run(), test_the_worker_job_is_registered_and_defaults_to_dry_run(), test_the_discord_publish_job_calls_the_ordinary_producer(), test_the_discord_publish_job_takes_an_optional_date(), test_the_raised_timeout_is_restored_after_the_job(), test_the_restore_puts_back_a_pre_existing_value() (+35 more)

### Community 462 - "Anonymous read access lockdown"
Cohesion: 0.03
Nodes (56): all_readable(), closed_tables(), lock_down(), lock_down_sql(), write_verbs_for(), _function_plan(), _function_signature(), main() (+48 more)

### Community 463 - "NFL in-play leader model config tests"
Cohesion: 0.11
Nodes (7): honest_probability(), test_a_loop_that_dies_fails_its_job(), test_it_decides_on_its_own_probability(), test_the_action_threshold_key_is_on_one_line(), test_the_loop_refuses_a_price_shorter_than_the_floor(), test_the_mlb_live_scorer_skips_it(), test_the_price_floor_is_minus_140()

### Community 464 - "NCAAF in-play gameday cadence tests"
Cohesion: 0.08
Nodes (13): _feed_with_payload(), gameday_mod(), test_a_sustained_feed_outage_degrades_to_no_odds(), test_cached_odds_are_served_while_fresh(), test_credit_cap_covers_a_full_saturday_at_the_configured_cadence(), test_credit_cap_reports_no_odds_rather_than_a_frozen_line(), test_credit_cap_still_serves_a_payload_that_is_still_fresh(), test_idle_cadence_is_slower_than_the_live_cadence() (+5 more)

### Community 465 - "nfl/scripts/backtest_opener.py"
Cohesion: 0.24
Nodes (9): boot(), by_season(), exp_win(), load(), main(), price(), report(), residuals() (+1 more)

### Community 467 - "NFL stale card file cleanup"
Cohesion: 0.15
Nodes (9): card_path(), clear_card(), _load_script(), nfl_path(), test_a_dry_run_leaves_the_card_alone(), test_a_priced_wind_run_with_no_bets_removes_the_earlier_card(), test_clear_card_removes_todays_file_and_only_that(), test_the_path_cleared_is_the_path_the_publisher_reads() (+1 more)

### Community 468 - "tests/test_latest_odds_views.py"
Cohesion: 0.25
Nodes (13): _app_columns(), _function(), test_every_log_table_has_its_insert_trigger_and_the_odds_tables_an_update_trigger(), test_every_view_reads_its_state_table_and_never_the_log(), test_no_pending_view_migration_re_creates_these_views_over_the_log(), test_the_dk_view_returns_the_apps_columns_in_order(), test_the_exclusions_survived_the_move(), test_the_game_view_returns_the_apps_columns_in_order() (+5 more)

### Community 469 - "Multi-book odds fetch tests"
Cohesion: 0.15
Nodes (7): _prop_markets(), test_draftkings_is_always_first_line_shop_book(), test_prop_bookmaker_defaults_to_draftkings(), test_prop_rows_are_stamped_with_their_bookmaker(), test_prune_never_touches_the_scoring_book(), test_prune_predicates_date_by_game_not_snapshot(), test_same_player_at_two_books_does_not_merge_prices()

### Community 470 - "Module entrypoint guard tests"
Cohesion: 0.15
Nodes (7): _is_main_guard(), _modules_with_guard(), test_at_least_one_entrypoint_is_scanned(), test_nothing_is_defined_after_the_main_guard(), test_the_report_script_exists_and_parses(), test_the_nfl_label_map_is_the_inverse_of_the_nfl_publisher(), test_every_prop_model_maps_to_a_dk_market()

### Community 472 - "NBA schedule ingestor and tests"
Cohesion: 0.16
Nodes (15): fetch_season(), main(), ot_periods(), run(), schedule_rows(), season_str(), _tv(), write() (+7 more)

### Community 473 - "tests/test_nfl_prop_settle_name_fallback.py"
Cohesion: 0.27
Nodes (10): _never(), _row(), test_a_first_name_the_stat_log_spells_differently_still_matches(), test_a_scratched_player_is_not_graded_on_a_teammate_with_his_initial(), test_a_spelling_the_log_already_knows_is_a_scratch_not_a_spelling(), test_another_game_and_another_initial_never_match(), test_first_name_rule(), test_two_candidates_is_a_miss_not_a_guess() (+2 more)

### Community 474 - "Recap waits for NFL box scores"
Cohesion: 0.17
Nodes (8): _daily(), _job_body(), test_a_malformed_date_is_refused_before_anything_runs(), test_nfl_box_scores_are_ingested_before_settle(), test_nfl_finals_still_precede_the_box_scores(), test_the_job_does_not_read_rowcount_off_the_cursor(), test_the_job_only_clears_its_own_two_ledger_kinds(), test_the_job_posts_both_surfaces_through_the_ordinary_paths()

### Community 476 - "tests/test_transaction_pooler.py"
Cohesion: 0.19
Nodes (8): _transaction_endpoint(), test_a_direct_connection_is_left_alone(), test_a_local_postgres_is_left_alone(), test_a_supabase_session_url_becomes_the_transaction_url(), test_it_is_idempotent(), test_only_the_port_changes(), test_the_escape_hatch_works(), test_the_job_queue_still_gets_session_mode()

### Community 477 - "NBA historical odds archive parsing"
Cohesion: 0.27
Nodes (8): _gid(), match(), _swap(), _g(), test_a_labelled_pair_is_never_swapped(), test_a_neutral_pair_listed_the_other_way_is_swapped_with_its_signs(), test_a_score_that_disagrees_with_games_is_not_loaded(), test_direct_match_keeps_the_page_orientation()

### Community 480 - "NBA second game world and panel builder"
Cohesion: 0.15
Nodes (11): build_panel(), build_world(), cell_specs(), check_cell_count(), _ids(), ledger_2021(), _norm_id(), normalize_stints() (+3 more)

### Community 483 - "ESPN versus DraftKings freshness check"
Cohesion: 0.16
Nodes (10): dk_live_quotes(), espn_live_quotes(), _key(), main(), _norm_dk_game(), _norm_espn_game(), _now(), _price() (+2 more)

### Community 485 - "NCAAF in-play underdog correction fit"
Cohesion: 0.18
Nodes (11): brier(), conditional_table(), fit_logistic(), load(), logit(), logloss(), main(), design() (+3 more)

### Community 487 - "supabase/functions/sharpsports/index.ts"
Cohesion: 0.30
Nodes (13): americanFromBetSlip(), asArray(), createContext(), isSettled(), json(), pick(), pullAndUpsert(), readBets() (+5 more)

### Community 488 - "UFC CSV download cache"
Cohesion: 0.13
Nodes (10): _cached_etag(), _etag_cache_path(), _store_etag(), test_a_mounted_volume_is_preferred_over_tmp(), test_a_round_trip_actually_persists(), test_a_volume_path_that_does_not_exist_falls_back(), test_an_empty_etag_is_never_stored(), test_an_explicit_override_wins() (+2 more)

### Community 491 - "NBA second game grid verdict tests"
Cohesion: 0.28
Nodes (13): _cell(), _grid(), _mid(), test_a_cell_clearing_every_bar_passes(), test_a_cell_with_no_dominant_side_is_not_held_to_a_blind_bet(), test_a_losing_neighbour_breaks_the_plateau(), test_an_all_empty_placebo_list_reads_as_no_placebo_not_a_crash(), test_an_extra_axis_keeps_neighbours_apart() (+5 more)

### Community 495 - "tests/test_worker_deps.py"
Cohesion: 0.19
Nodes (5): _requirements(), test_dashboard_packages_are_not_on_the_worker(), test_only_the_dashboard_imports_them(), test_the_dashboard_file_is_additive_not_a_replacement(), test_the_worker_asks_for_the_cpu_build_of_xgboost()

### Community 497 - "Sportsbook direct reachability probes"
Cohesion: 0.20
Nodes (8): main(), probe_book(), verdict(), egress_ip(), _probe_once(), _proxies(), reachability(), _session()

### Community 499 - "NBA player availability reallocation"
Cohesion: 0.13
Nodes (10): availability(), injury_at(), lead_bucket(), play_observations(), play_prob(), played_flags(), reallocate(), ridge_with_prior() (+2 more)

### Community 50 - "scheduler.py"
Cohesion: 0.05
Nodes (50): _run_migrations(), abort_orphaned_refresh_runs(), build_scheduler(), _add_job(), _with_heartbeat(), _wrapped(), catch_up_daily_pipeline(), catch_up_refresh_pass() (+42 more)

### Community 502 - "Dashboard queries and SQL file runner"
Cohesion: 0.08
Nodes (9): _fmt_et_time(), get_conn(), query(), main(), _strip_outer_tx(), test_it_asserts_the_app_write_surface_survives(), test_the_roles_are_named_never_public(), test_the_runners_transaction_stripping_leaves_the_do_block_intact() (+1 more)

### Community 503 - "Mobile player stat handoff tests"
Cohesion: 0.17
Nodes (8): _navigate_blocks(), _src(), test_every_caller_states_the_stat(), test_innings_resolves_to_the_outs_chip(), test_route_carries_the_stat(), test_screen_opens_on_the_requested_stat(), test_the_requested_stat_survives_the_loaded_player_filter(), test_the_side_travels_with_the_stat()

### Community 504 - "Team stats as-of snapshot checks"
Cohesion: 0.16
Nodes (8): seasons_with_too_few_snapshots(), test_a_real_series_passes(), test_a_single_snapshot_season_is_flagged(), test_a_two_snapshot_season_is_flagged(), test_mlb_twin_alias_map_matches_sbr_canon(), test_ncaaf_shaped_weekly_snapshots_pass(), test_the_guard_is_wired_so_protected_seasons_are_REMOVED(), test_the_guard_uses_the_same_threshold_as_the_invariant()

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
Cohesion: 0.03
Nodes (101): _bootstrap_roi_ci(), _summarise(), american_to_decimal(), cover_probs(), ev_per_unit(), fit_margin_pmf(), kelly_fraction(), margin_pmf_for() (+93 more)

### Community 51 - "NFL live moneyline and total pricing tests"
Cohesion: 0.07
Nodes (33): _model_price(), american_to_prob(), anchor_to_market(), devig_power(), margin_pmf(), _over_under(), price_moneyline(), price_quarter() (+25 more)

### Community 512 - "tests/test_savant_freshness.py"
Cohesion: 0.14
Nodes (5): test_rows_are_stamped_with_a_capture_date(), test_savant_has_a_schedule(), test_the_insert_persists_the_stamp(), test_the_savant_job_belongs_to_the_pipeline_service(), test_the_stamp_defaults_rather_than_being_required_at_call_sites()

### Community 513 - "tests/test_scorer_nfl_prop_like_escape.py"
Cohesion: 0.23
Nodes (9): _between(), _broken_per_game_sql(), _first_sql(), _per_game_sql(), _sweep_sql(), test_escape_tripwire_is_on_the_pr_ci_subset(), test_live_per_game_clear_interpolates_with_one_game_id(), test_live_sweep_clear_interpolates_with_date_horizon_now() (+1 more)

### Community 514 - "NBA game market fair pricing"
Cohesion: 0.12
Nodes (9): _groups(), market_fair(), pinnacle_close(), solve_any(), imp(), load_games(), load_lines(), quote_points() (+1 more)

### Community 517 - "NCAAF college data verification script"
Cohesion: 0.17
Nodes (9): parse_teams(), _check(), _lines_coverage(), main(), _null_report(), _sample_keys(), test_parse_teams_all_schools_pull_never_defaults_to_fbs(), test_parse_teams_joins_alt_names() (+1 more)

### Community 518 - "In-play model holdout comparison"
Cohesion: 0.23
Nodes (7): build_live_training_dataset(), bias_table(), confident_share(), load_artifact(), main(), poisson_sf(), predict()

### Community 519 - "Outbound API request probe recorder"
Cohesion: 0.07
Nodes (28): _drain(), _enqueue(), _flush_on_exit(), install(), instrumented(), _now(), _patch_curl_cffi(), instrumented() (+20 more)

### Community 520 - "NHL historical odds archive ingestor"
Cohesion: 0.20
Nodes (10): fetch_all(), _fold(), load(), load_period_scores(), _num(), _odds_rows(), parse_season(), _price() (+2 more)

### Community 522 - "CLV no-vig close capture tests"
Cohesion: 0.20
Nodes (8): _fn(), test_a_missing_bet_book_close_is_not_filled_from_another_book(), test_backfill_revisits_anything_that_is_not_standard_v2(), test_capture_grades_raw_same_book_and_a_separate_pinnacle_edge(), test_capture_stamps_method_and_close_book(), test_game_close_never_falls_back_past_first_pitch(), test_pinnacle_is_a_second_lookup_not_the_headline_close(), test_prop_close_stays_bounded_at_first_pitch()

### Community 524 - "Odds pruning keeps openers"
Cohesion: 0.11
Nodes (11): _counts(), main(), _older_than(), prune_table(), run_prune_odds(), _unprotected(), test_cfbd_archive_prefix_is_protected(), test_historical_backfill_rows_are_protected_in_odds() (+3 more)

### Community 525 - "Mobile stat segment tests"
Cohesion: 0.20
Nodes (10): _read(), test_one_shared_defensive_set(), test_position_is_never_inferred_from_stats(), test_runs_in_pr_ci(), test_search_and_position_review_fixes(), test_segment_labels_cap_only_on_fit(), test_tabs_speak_the_visible_label_not_the_key(), test_the_behavioural_checks_pass() (+2 more)

### Community 528 - "NFL opener cut sweep by book"
Cohesion: 0.23
Nodes (6): bettable_books(), boot_ci(), candidate_rows(), _load_backtest(), main(), select()

### Community 529 - "tests/test_clear_unauthorized_auto_pauses_migration.py"
Cohesion: 0.19
Nodes (6): _stmts(), test_clearing_auto_pauses_did_not_park_batter_runs(), test_it_clears_the_whole_auto_pause_table(), test_it_does_not_touch_picks_thresholds_or_the_review_ledger(), test_it_no_ops_when_the_table_is_missing_or_already_empty(), test_migration_is_one_statement()

### Community 53 - "Declared worker job validation tests"
Cohesion: 0.15
Nodes (7): _declared(), test_an_explicit_run_date_must_be_a_real_iso_date(), test_declared_keys_are_unique(), test_every_declared_job_names_a_registered_type(), test_every_declared_job_validates(), test_no_run_date_means_the_module_resolves_it(), test_the_validator_drops_unknown_args()

### Community 530 - "tests/test_ncaaf_se_louisiana_alias_migration.py"
Cohesion: 0.15
Nodes (4): test_a_pick_is_never_deleted_and_never_regraded(), test_it_guards_on_both_names_and_both_still_unscored(), test_migration_is_one_statement(), test_odds_move_only_when_canonical_has_none()

### Community 531 - "NCAAF starter-out grading study"
Cohesion: 0.27
Nodes (8): build_sample(), grade(), _line(), load_qb_log(), main(), report(), starter_status(), wilson()

### Community 532 - "tests/test_overnight_polling.py"
Cohesion: 0.24
Nodes (7): _hours(), _jobs(), _match(), test_every_hour_of_the_day_is_covered(), test_the_overnight_pass_is_the_ordinary_one(), test_the_overnight_window_exists(), test_the_windows_do_not_overlap()

### Community 535 - "NCAAF weather and wind totals study"
Cohesion: 0.23
Nodes (6): build_spots(), evaluate(), load_games(), main(), scoring_by_wind(), wilson()

### Community 537 - "NFL Kalshi price history fetch"
Cohesion: 0.21
Nodes (6): candles(), get(), map_games(), paged(), parse_event(), probe()

### Community 538 - "NHL totals lab"
Cohesion: 0.26
Nodes (8): grade(), imp(), interval(), load(), main(), row(), show(), wpu()

### Community 542 - "NCAAF situational spot search"
Cohesion: 0.10
Nodes (10): is_bowl_game(), build_spots(), evaluate(), load_team_games(), main(), wilson(), load_data(), main() (+2 more)

### Community 545 - "NFL prop two-sharp-book research"
Cohesion: 0.03
Nodes (49): _actuals(), build(), _lead_hours(), main(), profit(), _report(), season_of(), test_season_of_reads_the_game_id_token() (+41 more)

### Community 547 - "tests/test_db_setup.py"
Cohesion: 0.23
Nodes (6): _get_columns(), test_games_table_columns(), test_injuries_table_columns(), test_odds_table_columns(), test_picks_table_columns(), test_schema_is_idempotent()

### Community 548 - "tests/test_dedupe_opening_signals.py"
Cohesion: 0.12
Nodes (8): test_a_graded_row_is_never_deleted(), test_a_row_with_computed_clv_is_never_deleted(), test_every_field_that_defines_the_bet_must_agree(), test_the_delete_selects_through_the_same_gates(), test_the_pair_must_be_an_old_shape_new_shape_pair(), test_the_report_and_the_delete_share_one_definition(), test_the_row_kept_is_the_one_locked_earlier(), test_the_unresolved_report_excludes_what_the_delete_resolves()

### Community 549 - "Direct sportsbook feed pollers"
Cohesion: 0.22
Nodes (8): use_poller_session(), main(), run(), _ensure_schema(), main(), poll_once(), run(), test_a_poller_session_sets_the_idle_timeout_and_only_then()

### Community 550 - "NFL prop odds ingestor"
Cohesion: 0.04
Nodes (24): backfill_nfl_prop_odds(), backfilled_dates(), census_books(), _credits_used(), _event_props(), _get(), list_events(), list_historical_events() (+16 more)

### Community 552 - "tests/test_pbp_backfill_resilience.py"
Cohesion: 0.24
Nodes (6): _backfill_body(), test_a_failed_game_rolls_the_connection_back(), test_a_run_that_wrote_nothing_reports_an_error_not_a_success(), test_errors_are_counted_not_just_logged(), test_partial_failures_are_surfaced_too(), test_the_rollback_cannot_itself_raise()

### Community 553 - "NCAAF in-play loop cadence tests"
Cohesion: 0.15
Nodes (7): _main_source(), test_an_unanswered_state_feed_does_not_look_like_the_slate_ending(), test_loop_exits_early_when_no_kickoff_is_near(), test_loop_polls_at_the_idle_cadence_when_nothing_is_live(), test_loop_sleeps_the_remainder_not_a_flat_interval(), test_loop_warns_when_a_pass_overruns_its_interval(), test_odds_fetch_uses_the_odds_cadence_not_the_loop_cadence()

### Community 559 - "NFL wind forecast validation"
Cohesion: 0.29
Nodes (10): build(), games(), hourly(), main(), _rate(), sec_coverage(), sec_error(), sec_rule() (+2 more)

### Community 562 - "NBA second game line move fit"
Cohesion: 0.15
Nodes (7): close_times(), consensus(), f1b_coefficients(), fit_move(), move_rows(), mu_frame(), ols()

### Community 563 - "NFL prop universe model rate summary"
Cohesion: 0.29
Nodes (6): _universe_summary(), test_a_universe_without_the_model_sums_still_summarises(), test_mean_projection_and_mean_actual_separate_mean_bias_from_shape_bias(), test_model_over_rate_and_its_gap_are_reported(), _universe(), test_a_nonfinite_fair_price_cannot_switch_the_gate_off()

### Community 566 - "Mobile bankroll copy and behaviour tests"
Cohesion: 0.19
Nodes (14): _read(), test_copy_is_word_for_word(), test_display_only_nothing_sized(), test_error_text_uses_the_text_safe_red(), test_explainer_no_longer_denies_a_bankroll(), test_exposure_card_hook_and_banner_stay_removed(), test_keyboard_never_covers_the_field(), test_locale_separators_decide_the_decimal() (+6 more)

### Community 568 - "SQL percent escaping tripwire"
Cohesion: 0.21
Nodes (5): _adapt(), _parameterised_sql(), test_check_line_movement_query_interpolates(), test_parameterised_sql_escapes_literal_percents(), test_the_scanner_actually_catches_the_regression()

### Community 569 - "tests/test_game_log_backfill_skip.py"
Cohesion: 0.25
Nodes (5): _backfill_body(), test_a_game_absent_from_our_games_table_is_still_skipped(), test_no_skip_is_keyed_on_date_alone(), test_the_coverage_set_is_scoped_to_the_season_being_built(), test_the_skip_is_keyed_on_game_id()

### Community 572 - "NCAAF line move spots"
Cohesion: 0.27
Nodes (6): eval_follow_spread(), eval_follow_total(), load(), main(), _summ(), wilson()

### Community 573 - "NBA second game luck study"
Cohesion: 0.09
Nodes (22): as_of_ratings(), _before(), f4_projections(), f4_signal(), f6c_offers(), f6c_signal(), game_situations(), _load_box() (+14 more)

### Community 574 - "tests/test_prompt_reads_thresholds.py"
Cohesion: 0.18
Nodes (4): test_the_auto_pause_lookup_fails_open(), test_the_prompt_carries_no_per_model_cut(), test_the_prompt_still_says_it_is_pasted_once(), test_the_sync_mirrors_both_pause_registers()

### Community 575 - "tests/test_system_health_meta_steps.py"
Cohesion: 0.25
Nodes (5): _meta_steps(), test_aborted_sentinel_is_excluded(), test_health_check_is_excluded(), test_model_quality_is_excluded(), test_sentinel_matches_the_writer()

### Community 577 - "NBA period scores ingestor and tests"
Cohesion: 0.17
Nodes (14): et_date(), ensure_table(), fetch_date(), _int(), main(), parse_period_rows(), run(), write() (+6 more)

### Community 580 - "scripts/render_brand_icons.py"
Cohesion: 0.24
Nodes (3): draw_mark(), main(), render()

### Community 584 - "Dashboard rule model tests"
Cohesion: 0.14
Nodes (5): test_a_rule_carries_a_cut_but_is_in_no_training_registry(), test_a_rule_is_not_styled_as_a_warning(), test_a_rule_sorts_with_the_live_models_not_the_broken_ones(), test_the_roster_query_flags_rules(), test_the_summary_counts_rules_apart_from_outages()

### Community 586 - "supabase/functions/stripe-webhook/index.ts"
Cohesion: 0.31
Nodes (9): applySubscription(), iso(), resolveUserId(), stripeGet(), timingSafeEqual(), toHex(), verifySignature(), admin (+1 more)

### Community 589 - "tests/test_mobile_neutral_signal_label.py"
Cohesion: 0.31
Nodes (7): _read(), test_explainer_names_neutral(), test_filters_and_card_speak_the_display_name(), test_model_screens_speak_the_display_name(), test_no_member_label_prints_a_raw_signal_type(), test_none_badge_reads_neutral(), test_withdrawn_pick_is_not_badged_neutral()

### Community 590 - "NFL prop kickoff lead ceiling"
Cohesion: 0.30
Nodes (8): _nfl_prop_too_early(), _iso(), test_a_kickoff_beyond_the_ceiling_is_too_early(), test_a_started_or_unknown_kickoff_is_not_too_early(), test_the_boundary_is_inclusive_at_the_ceiling(), test_the_scorer_and_the_card_read_ONE_constant(), test_the_scorer_loop_actually_applies_the_ceiling(), test_the_z_suffix_parses_like_the_offset_form()

### Community 591 - "Discord community size stats"
Cohesion: 0.18
Nodes (5): configured(), guild_stats(), test_discord_names_the_missing_variables(), test_discord_never_raises(), test_discord_success_parses_counts()

### Community 593 - "tests/test_scorer_commits_per_game.py"
Cohesion: 0.40
Nodes (8): _between(), _run_scorer_body(), test_a_lost_connection_re_runs_the_game_once_and_never_the_pass(), test_each_game_is_its_own_committed_unit(), test_no_bulk_delete_of_non_bet_rows_precedes_the_loop(), test_picks_are_only_counted_once_the_game_committed(), test_the_housekeeping_delete_is_a_sweep_after_the_loop(), test_the_outer_handler_still_records_the_failure()

### Community 594 - "NCAAF scoreboard yardline parsing tests"
Cohesion: 0.21
Nodes (6): _abbrev_fits(), _parse_yardline(), _cfbd_game(), test_cfbd_state_carries_the_yardline_and_the_raw_situation(), test_cfbd_yardline_from_every_stored_situation(), test_cfbd_yardline_refuses_rather_than_guesses()

### Community 596 - "Supabase connection credential probe"
Cohesion: 0.27
Nodes (6): main(), scram_stored_key(), test_a_different_password_gives_a_different_key(), test_a_different_salt_gives_a_different_key(), test_iterations_matter(), test_rfc7677_test_vector()

### Community 598 - "In-play honest cut sweep"
Cohesion: 0.35
Nodes (9): bets_split(), _fmt(), _grid(), main(), _print_grid(), run_mlb(), run_ncaaf(), _summ() (+1 more)

### Community 599 - "NBA game market decision ordering"
Cohesion: 0.20
Nodes (6): blind_first_fetch(), decision_order(), family_mask(), rule_mask(), timing_bucket(), ts_int()

### Community 60 - "tests: test_wnba_availability + wnba_availability"
Cohesion: 0.11
Nodes (31): absence_features(), absent_teammates(), build_context_features(), expected_rotation(), _mean(), prior_rows(), recent_team_game_dates(), _safe_div() (+23 more)

### Community 600 - "NCAAF prop market rule sweep"
Cohesion: 0.26
Nodes (7): candidates(), dedupe(), grade(), load_board(), main(), norm(), profit()

### Community 604 - "Market coverage probe tests"
Cohesion: 0.07
Nodes (14): test_a_two_sided_market_is_never_reported_one_sided(), test_an_all_line_leg_slip_does_not_claim_a_model(), test_it_asks_about_the_board_columns_that_are_permanently_blank(), test_it_reports_supported_but_empty_apart_from_unsupported(), test_no_market_is_asked_about_twice(), test_one_market_per_call_so_a_rejected_key_is_identified_exactly(), test_only_books_we_asked_for_are_ever_counted(), test_the_alternates_nobody_prices_are_gone() (+6 more)

### Community 608 - "supabase/functions/sharpsports-webhook: index + index"
Cohesion: 0.25
Nodes (5): internalIdFor(), pick(), admin, admin, cors

### Community 612 - "supabase/functions/stripe-checkout/index.ts"
Cohesion: 0.31
Nodes (8): customerFor(), form(), json(), stripe(), admin, cors, PRICES, TRIAL_DAYS

### Community 614 - "tests/test_book_list_budget.py"
Cohesion: 0.31
Nodes (4): _names(), test_every_book_the_nfl_prop_model_bets_at_is_actually_fetched(), test_the_nfl_prop_pull_is_one_group_with_both_references_in_it(), test_the_shared_list_is_one_group()

### Community 615 - "Opening vs closing strategy analysis"
Cohesion: 0.43
Nodes (4): _fmt(), _profit_sql(), _row(), strategy_analysis()

### Community 62 - "NBA game market lab report"
Cohesion: 0.13
Nodes (20): assemble(), fetch_table(), gap_report(), hours_bucket(), log(), md_table(), norm_cdf(), _pivot_cells() (+12 more)

### Community 620 - "NCAAF in-play DraftKings qualifying gate"
Cohesion: 0.18
Nodes (4): test_a_cheaper_book_no_longer_buys_its_way_past_the_floor(), test_the_bet_is_still_recorded_at_the_best_price(), test_the_gate_reads_the_draftkings_numbers(), test_the_stale_line_cap_still_judges_the_dk_edge()

### Community 621 - "NBA game market blind bet grading"
Cohesion: 0.22
Nodes (7): _assert_spread_sign(), blind_bets(), grade(), prepare_candidates(), risk_win(), settle(), units_for()

### Community 622 - "SBR odds CSV loader"
Cohesion: 0.25
Nodes (3): canonical_abbrev(), parse_csv_file(), test_sbr_abbreviations_are_canonicalised_for_mlb_only()

### Community 623 - "NCAAF in-play model re-sweep"
Cohesion: 0.27
Nodes (6): attach(), first_signals(), load(), main(), summarise(), wilson()

### Community 628 - "NHL regulation own probability tests"
Cohesion: 0.18
Nodes (4): mapped(), test_nyr_regulation_2026_10_02_is_not_a_bet(), test_the_correction_does_not_touch_a_regulation_probability(), test_the_rebuilt_moneyline_decides_on_its_own_probability()

### Community 629 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.47
Nodes (6): contentHeight(), evalExpr(), lineOf(), styleBlock(), styleProp(), visualHeight()

### Community 63 - "Football in-play game state"
Cohesion: 0.12
Nodes (18): _as_float(), _as_int(), _as_opt_float(), _as_opt_int(), from_espn(), from_extract(), from_pbp_row(), smooth_pass_rate() (+10 more)

### Community 632 - "NHL prop backtest shared names"
Cohesion: 0.38
Nodes (6): namesakes(), _frame(), test_a_namesake_who_played_for_the_team_last_season_still_counts(), test_a_unique_name_is_kept(), test_namesakes_on_two_teams_collide_only_when_those_teams_meet(), test_two_teammates_with_one_name_are_both_refused()

### Community 635 - "tests/test_demote_ncaaf_over_under_platt.py"
Cohesion: 0.32
Nodes (4): _stmts(), test_it_demotes_only_the_measured_promotion(), test_it_does_not_move_the_gate_the_floor_or_a_pause(), test_migration_is_one_statement()

### Community 637 - "tests/test_discord_post_one_pick_migration.py"
Cohesion: 0.29
Nodes (3): _pairs(), test_it_names_each_measured_extra_and_the_row_kept(), test_the_update_does_not_rewrite_the_graded_outcome()

### Community 638 - "tests/test_game_scorer_spares_nfl_props.py"
Cohesion: 0.43
Nodes (5): _between(), _run_scorer_body(), test_an_nfl_game_never_enters_the_per_game_clear(), test_both_live_non_bet_clears_leave_nfl_rows(), test_the_left_out_ufc_clear_only_removes_unsettled_non_bets()

### Community 639 - "Mobile NHL look-ahead tests"
Cohesion: 0.29
Nodes (5): _fn(), _read(), test_the_nhl_read_matches_the_other_look_aheads(), test_the_sport_chip_is_the_hook_not_an_allowlist(), test_use_today_picks_fetches_nhl_across_that_window()

### Community 64 - "NFL in-play model backtest states"
Cohesion: 0.04
Nodes (47): _cluster_bootstrap(), evaluate(), main(), report(), align_states(), build_team_map(), _game_index(), kill_verdict() (+39 more)

### Community 641 - "tests/test_mobile_ota_self_update.py"
Cohesion: 0.32
Nodes (4): _read(), test_app_root_mounts_the_ota_updater(), test_the_pieces_exist(), test_the_updater_actually_applies_the_update()

### Community 642 - "NBA second game emit and bootstrap tests"
Cohesion: 0.22
Nodes (6): _emit_world(), _spy_run_cells(), test_closing_value_is_priced_with_the_markets_empirical_distribution(), test_every_family_emits_exactly_its_cells_through_the_harness(), test_the_d_cells_are_gated_on_the_points_own_decision_times(), test_the_bootstrap_is_seeded_and_refines_small_p()

### Community 644 - "NBA archive odds row shaping"
Cohesion: 0.22
Nodes (6): iso_z(), odds_rows(), snapshot_times(), test_a_refused_column_writes_no_row_for_it(), test_odds_rows_shape(), test_snapshot_times_are_noon_on_the_date_and_one_minute_before_tip()

### Community 645 - "NFL in-play 2024 pooled tables"
Cohesion: 0.36
Nodes (9): families(), fmt(), main(), parse_2025_output(), pooled_table(), replication(), repro_check(), row_of() (+1 more)

### Community 649 - "MLB totals public fade card"
Cohesion: 0.09
Nodes (20): load_latest_quotes(), _better_under(), edge_floor(), load_public_over_splits(), max_per_slate(), _price_in_window(), publish_enabled(), rank_kind() (+12 more)

### Community 651 - "NFL research files backup to Supabase"
Cohesion: 0.44
Nodes (5): backup(), files(), main(), restore(), verify()

### Community 655 - "UFC event page parsing"
Cohesion: 0.17
Nodes (10): _int_or_none(), _parse_event_date(), parse_event_list(), parse_event_page(), _two_ints(), test_event_date(), test_parse_event_list(), test_parse_event_page_draw_fight() (+2 more)

### Community 660 - "Pipeline watch post ledger"
Cohesion: 0.18
Nodes (6): test_a_confirmed_post_is_ledgered_so_the_run_can_be_verified(), test_an_occasional_kind_is_not_flagged_for_being_quiet(), test_an_unconfirmed_post_is_never_ledgered(), test_the_ledger_is_one_row_per_day_so_a_retry_cannot_double_count(), test_the_watch_belongs_to_the_pipeline_service(), _wire()

### Community 663 - "Multi-book odds named book reads"
Cohesion: 0.22
Nodes (5): _source(), test_closing_line_reads_name_the_book(), test_feature_engines_whitelist_draftkings(), test_line_shop_books_are_not_referenced_by_scoring_code(), test_scorer_prop_odds_reads_one_named_book_at_a_time()

### Community 673 - "Scorer keeps off-DraftKings priced bets tests"
Cohesion: 0.29
Nodes (6): _bet(), db(), _left(), _statement(), test_a_bet_priced_at_another_books_line_survives_and_a_bet_with_no_price_does_not(), test_the_statement_names_both_prices()

### Community 677 - "Drop voided NFL prop signals tests"
Cohesion: 0.23
Nodes (6): _stmts(), test_it_deletes_exactly_the_three_measured_lock_keys(), test_it_does_not_touch_picks_or_discord(), test_it_still_skips_a_key_that_has_a_standing_bet(), test_migration_is_one_statement(), test_standing_pick_uses_lock_key_sql_not_player_id()

### Community 678 - "NFL in-play pick date and resolution tests"
Cohesion: 0.25
Nodes (3): test_a_night_game_pick_carries_the_game_s_date_not_the_utc_clock(), test_nothing_written_means_nothing_announced(), test_resolution_refuses_rather_than_guesses()

### Community 692 - "NFL live publish refusal guard"
Cohesion: 0.29
Nodes (4): refuse_publish_reason(), test_refuse_publish_allows_a_real_rush_under(), test_refuse_publish_blocks_pass_attempt_overs(), test_refuse_publish_blocks_the_constant_prob_fingerprint_even_on_rush()

### Community 694 - "Pipeline watch run findings"
Cohesion: 0.17
Nodes (8): test_a_clean_run_still_posts(), test_a_failed_query_rolls_back_and_does_not_sink_the_run(), test_a_run_with_findings_posts_them(), test_every_not_ok_health_check_is_reported(), test_the_kill_switch_works(), _enabled(), findings_from_checks(), run_watch()

### Community 695 - "Paused model view migration tests"
Cohesion: 0.33
Nodes (5): _bodies(), _code(), test_both_public_views_exclude_the_paused_row(), test_no_earlier_owner_guard_reverts_the_new_definition(), test_the_view_migration_is_registered_after_its_owners_and_is_one_statement()

### Community 696 - "UFC fighter page parser"
Cohesion: 0.22
Nodes (7): _height_to_inches(), _parse_dob(), parse_fighter_page(), _reach_to_inches(), test_height_reach_dob(), test_parse_fighter_page(), test_parse_fighter_page_missing_fields()

### Community 697 - "Pipeline watch alert posting"
Cohesion: 0.29
Nodes (3): test_a_missing_webhook_escalates_rather_than_vanishing(), _announce(), _announce_and_ledger()

### Community 705 - "Mobile stats filter checks"
Cohesion: 0.18
Nodes (9): chip, lineOnlyFn, playersDay, ROOT, sportReset, stats, teams, teamsDay (+1 more)

### Community 707 - "NHL goalie line helpers"
Cohesion: 0.83
Nodes (4): _goalie_line(), regressed(), saved_above(), tot()

### Community 708 - "Team stats rebuild and verify"
Cohesion: 0.18
Nodes (9): already_a_series(), _games(), live_season_snapshot_grace(), main(), _prior_season_rates(), rebuild_sport(), _team_games(), verify() (+1 more)

### Community 71 - "tests/test_live_orchestrator.py"
Cohesion: 0.04
Nodes (49): _credit_cost(), credits_used_today(), fetch_in_play_odds(), record_credits(), consume_triggers_once(), _last_fg_fetch_age(), _live_game_ids(), _pending_triggers() (+41 more)

### Community 711 - "Live money no record-only tests"
Cohesion: 0.43
Nodes (4): _allowed(), _hits(), _rel(), test_the_repo_has_no_record_only_or_paper_tracking_mode()

### Community 713 - "NBA second game price cache checks"
Cohesion: 0.33
Nodes (3): _games_file(), test_a_segment_file_missing_part_of_a_season_is_refused(), test_full_checks_the_price_cache_for_every_graded_season_before_building_anything()

### Community 719 - "Mobile accessibility verify script"
Cohesion: 0.67
Nodes (3): read(), readUtf8(), verticalSlop()

### Community 72 - "Market handicap feature tests"
Cohesion: 0.04
Nodes (49): diff(), pitcher_diff(), diff(), pitcher_diff(), numeric_feature_value(), attach_market_handicap(), build_public_features(), build_rich_handicap() (+41 more)

### Community 721 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.67
Nodes (3): closeOf(), openTag(), toggleUse()

### Community 74 - "Prop CLV and SQL escaping tests"
Cohesion: 0.09
Nodes (17): _fn(), test_a_backfill_failure_never_breaks_settlement(), test_a_pick_is_only_stamped_captured_once_a_measure_resolved(), test_a_pick_stamped_after_first_pitch_is_never_measured(), test_a_prop_pick_whose_label_has_no_name_is_skipped_not_guessed(), test_both_guards_agree(), test_clv_pct_never_compares_prices_across_a_moved_line(), test_golf_stays_excluded() (+9 more)

### Community 75 - "NCAAF margin and totals evaluation"
Cohesion: 0.08
Nodes (27): build_frames(), _fit(), fit_and_register(), fit_and_register_totals(), main(), _matrix(), _print_sweep(), rmse() (+19 more)

### Community 76 - "ncaaf_live/tests/test_serve.py"
Cohesion: 0.07
Nodes (37): _clock_seconds(), extract_live_states_cfbd(), _parse_situation(), _cfbd_game(), _ctx(), _no_ev_floor(), _settled(), _stamped() (+29 more)

### Community 80 - "Global EV floor prop card tests"
Cohesion: 0.08
Nodes (22): _built(), floor_030(), identity_maps(), _nfl_fixtures(), open_pregame_cut(), _pregame(), shrink_map(), test_a_floor_note_does_not_stop_the_best_price_recheck() (+14 more)

### Community 82 - "Mobile script test runner via Node"
Cohesion: 0.09
Nodes (26): tsx_cmd(), test_the_behavioural_checks_pass(), _load_state_dir(), _raw_error_lines(), _read(), _run_node(), test_aborts_are_silent_and_offline_slow_are_narrow(), test_aborts_render_nothing_and_every_catch_skips_them() (+18 more)

### Community 854 - "Football play-by-play state finalizing"
Cohesion: 0.67
Nodes (3): finalize_states(), states(), test_load_pbp_falls_back_to_the_db_when_the_parquet_is_missing()

### Community 86 - "scripts/nfl_edge_preregistered_2026.py"
Cohesion: 0.09
Nodes (39): bar(), bets_frame(), bh(), binom_line(), _by_game(), cell(), fam(), first_last() (+31 more)

### Community 87 - "tests: test_player_positions + player_positions_ingestor"
Cohesion: 0.06
Nodes (29): _basketball(), basketball_group(), _fresh_source_ids(), _get_json(), ingest_player_positions(), match_to_log(), _name_index(), _ncaaf() (+21 more)

### Community 89 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.04
Nodes (48): a11ySrc, allowHit, ALLOWLIST, app, badExempt, bar, bareClose, baselineLeft (+40 more)

### Community 896 - "Pipeline watch credit burn checks"
Cohesion: 0.25
Nodes (4): test_burn_is_judged_against_the_cap_not_against_yesterday(), test_burn_survives_a_non_numeric_credits_column(), test_failed_api_calls_are_reported_even_when_burn_is_low(), findings_from_burn()

### Community 906 - "Mobile prop board market set"
Cohesion: 0.33
Nodes (3): _board_markets(), table(), test_the_mlb_board_and_the_mlb_pull_are_one_set()

### Community 907 - "Pipeline pass watch findings"
Cohesion: 0.33
Nodes (4): test_a_clean_pass_produces_no_finding(), test_a_pass_with_failed_steps_is_reported(), test_a_pass_with_no_finish_is_reported_without_over_reading_it(), findings_from_passes()

### Community 908 - "NBA archive moneyline timing checks"
Cohesion: 0.40
Nodes (3): ml_timing(), sign_agreement(), test_ml_timing_and_sign_agreement_count_what_they_say()

### Community 909 - "NBA game clock parsing"
Cohesion: 0.29
Nodes (4): classify_field_goal(), parse_clock(), test_field_goal_value(), test_parse_clock()

### Community 91 - "NBA prop model lab"
Cohesion: 0.07
Nodes (46): books(), decimal(), expected_value(), p_over(), settle_value(), _agg(), apply_rule(), binary_baselines() (+38 more)

### Community 93 - "MLB totals public fade tests"
Cohesion: 0.09
Nodes (34): find_fade_bets(), is_pre_commence(), select_latest_pre_commence_over(), under_in_odds_band(), american_units(), grade_under(), _dk_board(), _quote() (+26 more)

### Community 98 - "NBA play-by-play ingestor"
Cohesion: 0.04
Nodes (57): nba_team(), active_queries(), alias_map_rows(), _bool(), box_context(), box_finals(), build_game(), build_gap_game() (+49 more)

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

### Community 484 - "NBA 2026-27 rebuild write-up"
Cohesion: 0.11
Nodes (17): 1. Pre-registered bars (fixed 2026-10-15, before the first grid), 2. Data used (all in Supabase), 3. The market grid, 4.1 Game markets — closed for 2026-27, 4.2 First half / first quarter / team totals — closed for 2026-27, 4.3 Player props — one rule ships, 4.4 Player props — projection models (the NHL recipe), 4.5 The projection model on the worker's inputs only (+9 more)

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

### Community 790 - "Mobile development dependencies"
Cohesion: 0.29
Nodes (7): devDependencies, @babel/core, babel-plugin-module-resolver, babel-preset-expo, tsx, @types/react, typescript

### Community 897 - "NBA play-by-play lineup docs"
Cohesion: 0.25
Nodes (7): Commands, How a stretch is built (each rule is pinned by a test that was watched to fail), NBA play-by-play and on-court lineup segments, Source, Tables (all worker-only, locked down where they are created), Things a reader should know, What was loaded, and the checks (re-measured 2026-10-17 on production, after the rebuild)

### Community 151 - "docs/rules_evidence.md"
Cohesion: 0.07
Nodes (13): 'Decisions needed from you' is second person, never first, A model in config.MODELS with no FEATURE_MAP entry kills scoring for every sport, Every front-end change is reviewed by the UX designer agent before its PR opens, Gate the number that gets bet (cal_error_actionable), A health check must not gate on the thing that breaks, The settled live-prop record is zero bets, The Odds API returns x-requests-remaining on every response, including 401, How the pick rule was found: the NCAAF live loop delete-and-replaced every 45s (+5 more)

### Community 183 - "Probability calibration and EV floors docs"
Cohesion: 0.24
Nodes (14): models/honest_ev.gate and honest_probability, tracking/system_health._report_model_calibration, MODEL_OWN_EV_FLOOR and MODELS_ON_OWN_PROBABILITY for wind and opener, fetch_graded reads picks for NFL/NCAAF/UFC/rule models, GLOBAL_MIN_EV: 0.30 then 0.20, The go-live calibration gate never computed a real number, ncaaf_over_under Platt map demoted 2026-09-26, Per-model floors (#796) measured on the calibrated number (+6 more)

### Community 192 - "NFL game lines model write-up"
Cohesion: 0.11
Nodes (19): DataRegistry: source catalog with priority levels, scripts/edge_hunt.py: moneyline calibration clean, ML-vs-spread gap dead, Forecast validation (2026-08-15): rule holds at 57.09% under real day-3 error, Game totals model (consumes spread output as competitiveness), IngestOrchestrator: per-source fetch with no silent fallbacks, Middling does not clear vig, Moneyline derived from spread via fitted sigmoid, Oracle ceiling: perfect closing-line knowledge (+11 more)

### Community 210 - "Performance gauging and monitoring docs"
Cohesion: 0.10
Nodes (12): roi_collapse check, api_call_log table, Heartbeat watchdog, Live monitor dashboard (monitoring/), Live tuning panel (Models view), mv_scored_pick_outcomes (sweep matview), Official live date 2026-09-01, The request probe: one patch, not 75 call-site edits (+4 more)

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

### Community 419 - "NFL in-play rushing and passing prop findings"
Cohesion: 0.15
Nodes (10): Publish backstop refuses pass-attempt overs, Accrued carries from ESPN core leaders, rush_attempt_pace model: one offset on the book's number, Pace ratio, In-play rushing-attempt UNDER on pace ratio >= 1.25, NFL edge search 2026-10-11, docs/nfl_live_prop_assessment.md, Live pass-attempt bias assessment (2026-09-21) (+2 more)

### Community 420 - "mobile/docs/UX_REVIEW.md"
Cohesion: 0.16
Nodes (13): dashboard.html renderRoster(), A pick is a pick (re-priced line never replaces the locked one), Copy: formatAmerican/formatPct/formatCurrency, model ids never raw, Decided at the best bettable price; read via lib/decisionPrice.ts, frontend-ux-designer agent contract, Mobbin MCP connector (one route: Matt's claude.ai connector), Product rules: a violation is a Blocker, Reuse before invention (EmptyState, StatTile, SignalBadge, ...) (+5 more)

### Community 432 - "Daily model-quality monitor and MLB fade docs"
Cohesion: 0.12
Nodes (17): Hybrid Pin-agreement filter on mlb_over_under bets, mlb_runline and mlb_over_under (paused), mlb_total_public_fade card (paper UNDER), Slate concentration guard (insert-time), F5 odds coverage (DK carries F5 ML only), clv_degradation check, model_quality_checks table, Daily model-quality monitor (+9 more)

### Community 437 - "NCAAF and NFL model search write-ups"
Cohesion: 0.11
Nodes (8): scripts/ncaaf_search/, Honest MLB signal is ~0.55-0.56 AUC, CollegeFootballData (CFBD) as primary source, ncaaf_spread / ncaaf_over_under / ncaaf_moneyline, Halftime second-half lines, out of sample at real prices, Model state assessment, all 71 models (2026-09-03 snapshot), NCAA Football model build plan, NCAAF model search findings (2026-08-25)

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

### Community 486 - "In-play backtest findings docs"
Cohesion: 0.12
Nodes (8): Live inning gate replay, Live feature sensitivity (12.8pp median swing), mlb_live_total_runs (in-play total), Negative-binomial (NB1) tail, pregame_total_line feature (market anchor), ncaaf_live_total 2025 in-play backtest, ncaaf_live_win_prob 2025 in-play backtest, Late-game leader moneyline at DraftKings

### Community 492 - "NFL model bundle restore docs"
Cohesion: 0.16
Nodes (11): nfl/requirements.txt dependency set (pandas, numpy, pyarrow, requests, scipy, scikit-learn, lightgbm), Multi-layered leakage detection, The Odds API historical backfill (bet-time Tuesday 18:00 UTC; closing 10 min before kickoff clusters), The canonical write-up nfl_game_lines_model_system.md, data/credit_ledger.json spend/quota ledger, data/odds_cache/ keyed md5(date|regions|markets), data/raw/pbp_20XX.parquet not bundled; refetch from nflverse-data releases, data/processed/ (dev_long.parquet, book_screen.csv, feature matrix) (+3 more)

### Community 500 - "docs/sports/wnba.md"
Cohesion: 0.21
Nodes (13): Double-double is logistic, over-only, prob-only (COMPUTE_DD sentinel), NBA: 10 models live (moneyline + 9 props), O/U and spread blocked, NBA pipeline steps (odds, prop odds, stats local, scoring, settlement), stats.nba.com blocks datacenter IPs; team stats run on the local Task Scheduler job, WNBA results from the ESPN hidden API with core-API fallback, The wnba_over_under / wnba_spread sweep was leaked (latest snapshot had no pre-tipoff cutoff), WNBA models (moneyline + assists live; points/rebounds/threes/PRA/O/U/spread paused), WNBA pipeline responsibilities (odds, props, scoring, ESPN results, local game log and stats) (+5 more)

### Community 523 - "mobile/docs/AUTHENTICATION.md"
Cohesion: 0.24
Nodes (12): App Store guideline 4.8: Google on iOS requires Apple, AUTH_ENABLED kill switch, signalbase://auth-callback redirect URL, billingReady() requires AUTH_ENABLED, discordLinkReady() requires AUTH_ENABLED, RLS pre-flight: authenticated keeps full read access, SignInScreen (SignIn route), useAuth session store (+4 more)

### Community 558 - "docs/health_checks.md"
Cohesion: 0.24
Nodes (10): model_artifacts_load counts what it opened, model_artifacts table fallback restore, Three separate artifact questions, three separate failures, KNOWN_UNTRAINED — config models intentionally without artifacts, Pipeline-observability checks: refresh_pass_completion, refresh_pass_steps, signal_delivery, pick_label_integrity, pipeline_runs — the run ledger (tracking/run_ledger.py), Retrain Model workflow (retrain_model.yml), tracking/system_health.py — CRIT and WARN feed checks (Step 12) (+2 more)

### Community 560 - "docs/retrain_2026_plan.md"
Cohesion: 0.18
Nodes (13): scripts/paused_model_assessment, data.ingestors.baseball_savant_ingestor, models.trainer, anytime_td verdict: inert, not losing, F5 O/U and F5 RL paused: leak-mismatched, synthetic-line trained, NCAAF in-play season replay: -3.4% and -13.1%, No model has a cut that clears on the deployed artifact, batter_sb: opp_team_sb_allowed feature (+5 more)

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
Nodes (51): scripts/nfl_prop_market_card, scripts/nfl_prop_replay, scripts/nfl_prop_ladder_grade, scripts/verify_kalshi, data/ingestors/kalshi_prop_ingestor.py (SERIES_MARKET, record_ladders), DraftKings de-vigged price sits above realised over-rate, tackles_assists +21% is a measurement error (control), Walk-forward re-fit 2023-2025 (-4.32% over 1,554 bets) (+43 more)

### Community 665 - "Signal-flip push and privacy docs"
Cohesion: 0.23
Nodes (12): mobile usePushNotifications / NotificationsCard / pushDiagnosis, On-device storage: bankroll and placed-bet flags in AsyncStorage, Claim: the app cannot write to the backend, Signalbase privacy policy: nothing personal collected, APNs key / aps-environment entitlement is the blocker, device_push_tokens table (anon INSERT/UPDATE, no SELECT), No push has ever reached a phone (2026-09-12), push_sent ledger means considered, not delivered (+4 more)

### Community 671 - "Opening-signal shadow track docs"
Cohesion: 0.43
Nodes (7): tracking/opening_signals.capture_opening_signals, tracking.opening_report, tracking/opening_signals.settle_opening_signals, opening_signals table, Opening-signal shadow track, Worker migrations sweeping voided captures, Opening-signal shadow track

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

### Community 81 - "docs: nhl_market_lab + nhl_clv_ev_assessment"
Cohesion: 0.08
Nodes (39): nhl_research worker job, scripts/nhl_derivative_totals_backtest, data/ingestors/nhl_derivative_odds_history, models/nhl_props.py (Spec per market), Anytime goalscorer: not a candidate once names corrected, nhl_moneyline and nhl_moneyline_regulation: no cut clears, Game models: lock later? Refuted, Name-key matching attached prices to both namesakes (+31 more)

## Ambiguous Edges - Review These
- `Claim: the app cannot write to the backend` → `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`  [AMBIGUOUS]
  docs/privacy.html · relation: conceptually_related_to

## Knowledge Gaps
- **105 isolated node(s):** `expo/tsconfig.base`, `RFC-4122`, `@babel/core`, `babel-plugin-module-resolver`, `babel-preset-expo` (+100 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 10888 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **195 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_connection()` connect `Shared database connection core` to `ESPN injury ingestor`, `Prop odds ingestors and quota tracking`, `Database connection and game features`, `In-play model holdout comparison`, `MLB game features and market sweeps`, `Outbound API request probe recorder`, `NHL historical odds archive ingestor`, `Odds pruning keeps openers`, `Discord pick notifier tests`, `NCAAF college data refresh and backfill tests`, `Daily pipeline runner and push notifier`, `Discord pick posting and void notices`, `NCAAF starter-out grading study`, `Threshold and EV floor sweeps`, `NHL blocked shots prop card`, `NBA prop projection card`, `NCAAF weather and wind totals study`, `NHL moneyline and market research scripts`, `Closing line value backfill job`, `NHL totals lab`, `NCAAF college data ingestor`, `NCAAF situational spot search`, `NCAAF starter-out search dataset`, `Kalshi prop ladders and game markets`, `Direct sportsbook feed pollers`, `NFL prop odds ingestor`, `NFL prop market stacking research`, `DataGolf ingestor and NHL SBR archive`, `Worker job queue and retrain jobs`, `Failure alerter fake-connection tests`, `scheduler.py`, `tests/test_best_line_live.py`, `tests/test_void_picks.py`, `NCAAF in-play gameday loop and feeds`, `NFL odds client and opener card`, `NBA period scores ingestor and tests`, `tests/test_umpire_ingestor.py`, `tests/test_live_orchestrator.py`, `NCAAF margin and totals evaluation`, `tests/test_wnba_prop_market.py`, `NHL derivative totals model`, `Publish key identity and push alerts`, `tests/test_recap_retries_a_skipped_day.py`, `In-play honest cut sweep`, `tests: test_player_positions + player_positions_ingestor`, `NCAAF prop market rule sweep`, `NFL prop model tests`, `tests/test_ncaaf_pbp_store.py`, `tests/test_heartbeat_watchdog.py`, `NBA play-by-play ingestor`, `Record correction post tests`, `NHL prop priced lab`, `Opening vs closing strategy analysis`, `Record correction posts to Discord`, `MLB batter and pitcher prop features`, `tests/test_live_calibration.py`, `nfl_live_leader/gameday.py`, `tests/test_prop_alternate_lines.py`, `NHL props nightly card`, `features/golf_feature_engine.py`, `tests/test_bovada_feed.py`, `NBA official injury report ingestor`, `MLB totals public fade card`, `NFL research files backup to Supabase`, `NBA prop market card publisher`, `Idle read transaction tests`, `Game odds ingestor and historical backfill`, `Player name matching and local cache`, `WNBA results and stats ingestors`, `NBA box score enrichment`, `X posting auth and database probes`, `NHL stats and probable goalies ingest`, `Prop box score backfill`, `tests/test_publisher_lock.py`, `scripts/game_line_market_sweep.py`, `NFL wind and opener publisher`, `Settlement and self-heal tests`, `Prop market devig and bet finding`, `tests/test_first_signal_repair.py`, `Team stats rebuild and verify`, `NBA box score stats ingestor`, `NFL prop features and backtests`, `MLB in-play inning gate replay`, `data/ingestors/nfl_inplay_history.py`, `Pick scorer and bet sizing`, `NCAAF in-play engine and pick lock`, `NBA results and box score ingestor`, `tests/test_team_board_cache.py`, `tests/test_nfl_poll_fast_silence.py`, `data/ingestors/ncaaf_inplay_history.py`, `MLB and WNBA stats ingestors and pitcher rebuild`, `tests/test_weather_lookahead.py`, `tests/test_dk_freshness_parse.py`, `NBA historical odds archive buyer`, `data/ingestors/nhl_boxscore.py`, `tests/test_ncaaf_search_features.py`, `Deploy checks and worker job queue`, `NCAAF in-play history backtest`, `tests/test_ncaaf_qb_features.py`, `Monitoring HTTP stream handler`, `EV floor replay and honest cut sweep`, `NCAAF play-by-play state builder`, `MLB live game state polling loop`, `System health checks and record reconciliation`, `Calibration fit job and health`, `Historical odds backfill and first pitch`, `NFL Kalshi edge and NHL blocked shots`, `Pregame line poller change tests`, `Pitcher stats as-of invariant tests`, `NFL player stats and props data`, `Model quality degradation monitor`, `NHL prop backtest and EV lab`, `WNBA prop player feature engine`, `NCAAF totals lead and consensus gate`, `NFL edge cache and feed probe`, `Paused model profitability assessment`, `Player news ingestor and name matching`, `NBA prop closing line tests`, `NFL in-play pick writer`, `MLB play-by-play ingestor`, `UFC fight history loader`, `UFC event stats ingestor`, `MLB public fade top-K holdout`, `tests/test_promote_calibration_job.py`, `NCAAF outcome edge scan`, `NHL derivative odds history purchase`, `Pipeline report with per-section rollback`, `NFL odds cache import to Supabase`, `NFL 2026 opener and wind tracker`, `NFL weather edge and prop assessment`, `tests/test_batter_prop_log_pin.py`, `MLB doubleheader twin game merge`, `NFL forecast and historical weather fetch`, `Discord results recap backfill`, `Anonymous read access lockdown`, `NBA schedule ingestor and tests`, `tests/test_transaction_pooler.py`, `Job heartbeat watchdog and ops alerts`, `Dashboard queries and SQL file runner`, `NBA game model lab and NFL staking`, `Model trainer and prop retrains`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **What connects `expo/tsconfig.base`, `RFC-4122`, `@babel/core` to the rest of the system?**
  _105 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `ESPN injury ingestor` be split into smaller, more focused modules?**
  _Cohesion score 0.03049828178694158 - nodes in this community are weakly interconnected._
- **Why does `mlb_live_total_runs (in-play total)` connect `In-play backtest findings docs` to `NFL prop two-sharp-book research`, `Performance gauging and monitoring docs`, `NCAAF and NFL model search write-ups`, `docs/thresholds.md`?**
  _High betweenness centrality (0.015) - this node is a cross-community bridge._
- **Should `Mobile stats board` be split into smaller, more focused modules?**
  _Cohesion score 0.01175468721642864 - nodes in this community are weakly interconnected._
- **Why does `docs/thresholds.md` connect `docs/thresholds.md` to `docs/sports/nhl.md`, `In-play backtest findings docs`, `docs/sports/nfl.md`, `mobile: TESTFLIGHT + README`, `docs/sports/mlb.md`, `docs/sports/wnba.md`, `docs/sports/ncaaf.md`, `docs/reviews/2026-09-07-nfl-props-deep-dive.md`, `docs/history: learnings + build_state`?**
  _High betweenness centrality (0.015) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Claim: the app cannot write to the backend` and `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._