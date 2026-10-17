# Graph Report - bm-nba-pbp  (2026-10-17)

## Corpus Check
- Large corpus: 1456 files · ~2,354,436 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 27524 nodes · 65294 edges · 892 communities (679 shown, 213 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 1698 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `53a2ad0b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ESPN injury team id fallback
- Mobile stats board
- Mobile error and load states
- Record correction post tests
- Odds, WNBA and shared ingestor plumbing
- tests/test_nfl_live_leader_gameday.py
- nfl_live_leader/gameday.py
- tests/test_calibration_promotion.py
- tests/test_score_off_any_book_line.py
- tests/test_recap_restatement.py
- Mobile pick filters and sorting
- tests/test_ncaaf_alias_scores.py
- tests/test_prop_alternate_lines.py
- Game scorer core and live scorer
- tests/test_backtester.py
- scripts: nhl_prop_backtest + nhl_prop_ev_lab
- nfl/live_model/feeds/odds_live.py
- NHL props newest quotes and upcoming rows
- NBA prop market lab
- Discord signal notifier tests
- DDL guard and research backup snaps
- mobile/scripts: verify_book_links + verify_betslip_combine
- NBA injury report pull retries
- Mobile custom model filters and metadata
- models/nhl_props.py
- tests/test_health_pregame_prices_current.py
- Pick lock after settlement tests
- Mobile push test and diagnosis
- tests/test_mlb_game_market.py
- Discord results recap restates
- Threshold review run tests
- Idle read transaction tests
- tests/test_prop_box_scores.py
- MLB totals public fade model
- tests/test_nfl_opener.py
- NHL stats, game logs and SBR archive
- scripts/nfl_preflight.py
- Mobile sign-in and auth
- Mobile billing config and verify script
- tests/test_publisher_lock.py
- tests/test_dk_direct_feed.py
- tests/test_credit_budget.py
- Mobile model screens and thresholds
- NHL market-anchored moneyline model
- NFL opener publisher and lock keys
- Settlement and self-heal tests
- NFL prop market stack, devig and information test
- Mobile contrast token checks
- tests/test_model_calibration_agent.py
- Monitoring and one-pick-per-event tests
- Prop price pregame cutoff tests
- Mobile markets and formatting
- Mobile formatting and live status checks
- NFL prop odds loading tests
- Per-market EV floors and honest EV
- tests/test_nhl_asof.py
- NFL prop model verdict tests
- NFL prop research readers and local store
- tests: test_deploy_checks + deploy_checks
- data/ingestors/nfl_inplay_history.py
- Mobile bankroll separators check
- Probability calibration and its sweep
- NHL props card pick rows and quotes
- NFL prop injury veto
- NCAAF live engine pricing
- NBA prop projection card
- tests/test_db_reconnect.py
- tests/test_live_lock.py
- tests/test_refresh_retry.py
- NBA results ingestor store
- NBA results ingestor tests
- NHL derivative odds history
- tests/test_local_cache_is_additive.py
- tests/test_calibration_check_coverage.py
- Record correction posting script
- tests/test_book_team_map.py
- tests/test_team_board_cache.py
- mobile/src/lib: verify_discord_link + discordHelpers
- nfl/live_model/tests/test_rush_attempt_pace.py
- tests/test_nfl_poll_fast_silence.py
- NHL market lab and live artifact grading
- MLB prop market sweep
- Failure alerter and calibration watch
- tests/test_weather_lookahead.py
- tests/test_nhl_asof.py
- tests/test_dk_freshness_parse.py
- tests/test_live_calibrated_decision.py
- models: slate_concentration + test_slate_concentration
- View migration lock handling tests
- Prop odds missing-game and window tests
- Search feature matrices and opponent adjustment
- NCAAF search validation and openers
- NFL weather and wind totals
- NFL player stats ingestors
- Mobile team detail and team stats
- Best line threshold sweep
- tests/test_nfl_scored_rows.py
- tests/test_cfbd_ingestor.py
- Parlay builder and bet slip
- NCAAF in-play history tests
- tests/test_line_clv.py
- tests/test_prop_odds_utc_stamp.py
- Monitoring HTTP stream handler
- NFL lookahead signal tests
- tests/test_feature_artifact_agreement.py
- Player name matching tests
- CLV price-taken tests
- Mobile pick queries and hooks
- tests/test_cloud_retrain_artifacts.py
- Decide-on-best-price and threshold SQL
- NCAAF FBS registry tests
- tests/test_nfl_opener.py
- NBA prop market publishing tests
- tests/test_team_stats_asof_invariants.py
- NHL props card tests
- Starter-out dataset builder
- tests/test_nfl_wind_publisher.py
- Prop odds and odds history ingestors
- NFL live prop model tests
- tests/test_health_reason_and_cadence.py
- tests/test_live_publish_parity.py
- tests/test_nfl_weather_supabase_readback.py
- Pregame line poller
- Pitcher stats as-of invariant tests
- tests/test_walk_forward_eval.py
- NBA prop model core
- Injury adjustment feature tests
- NCAAF gameday pick lock tests
- Pipeline log reason tests
- NFL weather edge study
- Model quality monitor
- NCAAF live pricing and score distribution
- tests/test_nfl_scored_rows.py
- System health signal delivery tests
- Cursor wrapper and X results job tests
- NBA prop window scheduling tests
- tests/test_ncaaf_live_states.py
- nfl/live_model/feeds: test_feed_resilience + espn
- tests/test_nfl_opener.py
- Mobile app shell, feedback and sportsbook connect
- Live scorer score guard tests
- tests/test_live_pick_features.py
- CLV backtest and shrunk ensemble build
- Pregame price age: borrowed market quotes
- tests/test_prop_missing_features.py
- NFL weekly wind card and odds snapshots
- UFC fighter name resolution tests
- ESPN player news ingestor
- NBA prop closing line tests
- NFL live pick writer: declines and refusals
- tests/test_cfbd_ingestor.py
- tests/test_run_ledger_orphans.py
- NFL line snapshot tests
- Mobile in-app purchases
- Odds pruning and sharp book retention tests
- NFL live pick writer: decision rows
- tests/test_heartbeat_disabled_jobs.py
- tests/test_repair_bogus_first_pitch_labels.py
- nfl/live_model/tests/test_executor.py
- tests/test_sbr_loader.py
- mobile/scripts/ux_scan.mts
- Feature engine and MLB line sweeps
- Prop ladder and Kalshi prop market tests
- Price prefilter rollback and UFC model compare
- mobile/src/lib/otaUpdate.ts
- tests/test_live_quote_staleness.py
- Prop market one side per line
- Best game price tests
- NFL prop market grading and kickoff gate
- NBA prop stat settlement tests
- NFL live leader model
- supabase/functions/_shared/discord.ts
- CLV price-taken and paper tracker
- tests/test_job_queue.py
- System health checks
- NBA prop market model and card
- UFC late replacement tests
- tests/test_mlb_sbr_twin.py
- tests/test_ufc_phantom_filter.py
- NFL live pick writer: pass attempts and commits
- tests/test_batter_prop_log_pin.py
- tests/test_opp_starter_features.py
- tests/test_merge_mlb_twin_games.py
- tests/test_discord_channel_probe.py
- tests/test_nfl_prop_one_read_per_game.py
- Game outcome target tests
- Pipeline pass completion tests
- NCAAF gameday cadence and live odds
- Multi-book odds tests
- scripts/nfl_edge_gameline_rules.py
- Threshold review DDL tests
- tests/test_model_game_savepoint.py
- Mobile bankroll storage
- tests/test_calibration_watch.py
- Calibration agent and external promote
- NBA injury report scheduler
- NFL weather, odds and wind card scripts
- tests/test_pipeline_report_rollback.py
- NBA lineup stint derivation
- NFL pick monitor game id tests
- Failure alerter fake-connection tests
- Pipeline watch: stale weeklies
- tests/test_sbr_loader.py
- Mobile theme, parlays and sportsbook links
- tests/test_nhl_three_way_lookahead.py
- Prop odds lookahead window
- Run ledger tests
- tests/test_score_when_lines_open.py
- NHL blocked shots settlement tests
- Monitoring server tests
- Live best-takeable quote tests
- System health test fixtures
- tests/test_sbr_loader.py
- MLB in-play game state alignment
- NFL prop odds frame loading
- NFL team row parsing tests
- tests/test_nfl_props.py
- NFL wind card bettable books
- Prop no-bet rows to tipoff
- Health skip budget tests
- NHL opening night goalie tests
- tests/test_void_picks.py
- tests/test_sbr_loader.py
- scripts/mlb_bet_record_audit.py
- NCAAF feature engine and FBS registry
- NCAAF gameday worker and CFBD feed
- tests/test_sbr_loader.py
- First-signal repair fake connections
- tests/test_daily_retry.py
- NBA prop roster name resolution
- NFL live pick writer: failure isolation
- Feature map tests
- Odds API credit budget
- Scorer make-pick signal tests
- tests/test_live_book_move_guard.py
- NFL opener tick latency tests
- tests/test_nfl_props.py
- tests/test_weekly_catch_up.py
- tests/test_sbr_loader.py
- tests/test_umpire_ingestor.py
- Discord signal fields and best-price restates
- NBA prop settlement tests
- Prop odds book update-time tests
- NFL pick monitor
- tests/test_nhl_props.py
- tests/test_live_pregame_total_line.py
- NFL live leader state client
- Live quote score clock
- NFL prop card publisher tests
- Voided pick exclusion tests
- Scorer injury flag tests
- Paper tracker bankroll and scorer database calls
- Best line and best-price decision tests
- mobile/src/hooks: verify_tracked_performance + useStakeSettings
- supabase/functions/revenuecat-webhook/index.ts
- supabase/functions/whop-webhook/index.ts
- tests/test_nfl_props.py
- Model trainer, WNBA and NHL research scripts
- NFL prop odds loader tests
- data/ingestors/live_game_state_poller.py
- tests/test_sbr_loader.py
- NHL as-of lookup tests
- NFL live game state and parity
- Scorer feature values and starter gate tests
- Mobile auth hook
- Overnight feed window tests
- Paused bets keep their verdict
- Recap retry for skipped days
- NFL DraftKings line snapshot tests
- Odds, prop odds and NHL derivative odds ingestors
- NFL prop price math tests
- NBA injury report PDF parser
- tests/test_nfl_props.py
- tests/test_nhl_three_way_lookahead.py
- Scorer confidence tier and pick label tests
- NFL live backtest harness and calibration
- Pregame board dropped-game tests
- NFL prop tests and feature engine
- UFC board price age tests
- NFL prop market stack and devig
- Mobile bankroll store
- tests/test_game_market_gate.py
- NHL props card and cross-model publish
- Calibration watch announcer
- NFL wind book list tests
- tests/test_score_when_lines_open.py
- tests/test_score_when_lines_open.py
- tests/test_score_when_lines_open.py
- tests/test_pick_integrity.py
- Push adjustment tests
- NHL returning-starter name tests
- tests/test_score_when_lines_open.py
- Mobile track record and sharp score checks
- tests/test_record_one_pick_per_event.py
- tests/test_nfl_scored_rows.py
- Pregame price age: two-id games
- Umpire feature drop declaration tests
- tests/test_weather_lookahead.py
- Health check step alarm tests
- nfl/live_model/tests: test_props + props
- Prop no-bet row survival tests
- First-five any-book line tests
- Heartbeat watchdog fake cursor
- NCAAF alias score mirroring
- tests/test_wnba_prop_market.py
- tests/test_nfl_scored_rows.py
- NHL derivative totals model
- Savant freshness check tests
- Mobile player log and matchup stats
- NHL totals card and market
- Publish key identity tests
- Discord notifier and void notices
- NHL blocked shots prop settlement tests
- Signal publish fake connection
- tests/test_recap_retries_a_skipped_day.py
- NFL live pick audit tee recorder
- Pregame price age tests
- NFL opener fire window tests
- NCAAF feature engine test database
- Weekly catch-up cursor fake
- NFL opener card split tests
- Prop lookahead window tests
- NFL scored rows clock fixture
- SQLite schema split tests
- tests/test_f5_any_book_line.py
- tests/test_ncaaf_prop_odds.py
- tests/test_mlb_total_public_fade.py
- NFL prop event market list tests
- tests/test_ncaaf_pbp_store.py
- Game injury veto gate and tests
- NHL prop card and blocked shots model
- Publish keys and Discord sync tests
- NBA stint derivation tests
- NCAAF slug and orientation helpers
- scripts/nfl_edge_live_rush_pace.py
- NBA prop projection tests
- Mobile live segment wiring tests
- tests/test_prop_calibrated_decision.py
- ncaaf_live/tests/test_pregame_calibration.py
- tests/test_mobile_line_movement.py
- tests/test_live_calibration.py
- Push deep link and mobile player detail tests
- Heartbeat watchdog and ops alerts
- tests/test_ncaaf_live_notify.py
- monitoring/store.py
- tests/test_settled_record_is_immutable.py
- features/golf_feature_engine.py
- NCAAF live state building tests
- tests/test_bovada_feed.py
- tests/test_market_movement.py
- tests/test_ncaaf_cross_book_opener.py
- tests/test_paused_keeps_real_verdict.py
- NFL in-play edge studies 2024-25
- UFC event and fight page parsers
- NBA prop projection model
- scripts/nfl_edge_extreme_props.py
- scripts/nfl_edge_settlement.py
- X publisher tests
- tests/test_agents_contract.py
- Market coverage probe tests
- Position vs opponent tests
- Best prop and game price selection tests
- WNBA results ingestor parsers
- Daily pipeline runner and push notifier
- NFL in-play flow evaluation and validation
- NBA box score enrichment
- X publisher and brand avatar
- NFL in-play edge study 2025
- Mobile preferred book and line-shop checks
- Push notifier and tickets
- MLB in-play history and live cut sweeps
- NFL stake sizing simulation
- NFL in-play prop engine calibration
- tests/test_decide_on_calibrated.py
- NBA prop projection lab
- NFL prop odds ingestor and backfill
- tests/test_nfl_rule_2026_track.py
- tests/test_model_artifacts_load.py
- scripts/game_line_market_sweep.py
- Push deep link tests
- tests/test_pass_instrumentation.py
- tests/test_db_adapt_sql.py
- tests/test_first_signal_repair.py
- tests/test_mobile_contrast_tokens.py
- NBA stats ingestor
- Historical odds backfill tests
- tests/test_live_inning_gate_replay.py
- NBA prop over probability and calibration
- NFL edge studies: luck gap and halftime
- CLV math: same-book and market-edge
- First pitch pregame snapshot tests
- Prop ladder and unique pick tests
- tests/test_nfl_live_leader_state.py
- tests/test_ncaaf_qb_ingestor.py
- NBA ESPN box and scoreboard parsers
- NBA derivative market lab
- NBA prop model verification script
- NCAAF feature engine tests
- Discord price bound tests
- tests/test_ncaaf_game_identity.py
- MLB stats ingestor and pitcher backfill
- NBA play-by-play ingestor
- data/ingestors/nhl_boxscore.py
- MLB totals public fade top-k study
- tests/test_live_game_features.py
- tests/test_ncaaf_totals_regression.py
- UFC feature engine and tests
- Mobile pick CTA and NFL import checks
- NCAAF in-play history backtest
- tests/test_ncaaf_qb_features.py
- Database URL doctor
- Prop box score fill
- X publisher and free pick
- NBA schedule features
- Health skip budget tests
- Kalshi ladder recording and prop ingestor tests
- tests/test_model_calibration_check.py
- tests/test_ncaaf_player_stats_ingestor.py
- NCAAF in-play history pulls
- Unit stake sizing and formatting
- scripts/nfl_edge_kalshi.py
- Mobile pick category tests
- tests/test_context_budget.py
- tests/test_player_h2h_stat_values_migration.py
- tests/test_retired_models.py
- NFL live prop feasibility study
- Latest line state and Citadel migration cluster tests
- tests/test_live_record_start_views.py
- tests/test_api_call_rollup.py
- UFC CSV loader
- nfl/models/opener_spread.py
- NHL prop backtest and combined cap
- tests/test_live_slate_midnight.py
- tests/test_nfl_wind_fire_window.py
- College football data parsers
- tests/test_public_betting_ingestor.py
- Mobile TypeScript test runners
- tests/test_service_role_split.py
- tests/test_http_timeout_floor.py
- UFC stats ingestor and page cache
- scripts/nfl_edge_cache.py
- tests/test_nfl_injury_ingest.py
- NHL prop odds alternate line tests
- Live honest cut and NHL regulation probability
- NHL derivative totals backtest
- NCAAF ESPN live feed parser
- Sub-10-second live path tests
- tests/test_config.py
- Kalshi game market recorder
- Outcome edge scan
- tests/test_mlb_pbp_ingestor.py
- UFC fighter name resolution
- EV floor replay and honest cut
- UFC stats ingestor and fighter pages
- tests/test_team_stats_asof_invariants.py
- Anon grants and lock-down tests
- Refresh pass step ordering tests
- NFL live pick writer: price and lock scope
- NFL in-play line churn
- tests/test_mobile_threshold_parity.py
- NFL live prop assessment and book screen
- tests/test_nhl_derivative_odds_job.py
- tests/test_track_record_views.py
- tests/test_weekly_catch_up.py
- tests/test_live_game_state_poller.py
- Mobile tracked performance check
- NFL Kalshi fetch and price floor grid
- MLB prop market tests
- NFL live leader model tests
- NFL wind edge studies
- Mobile paused catalog tests
- NFL live prop rule studies
- NFL prop shape simulation
- tests/test_promote_calibration_job.py
- tests/test_cfbd_snapshot_leakage.py
- Mobile player stat groups test
- Mobile bankroll card field flow
- tests/test_nfl_prop_thresholds.py
- tests/test_nhl_research_job.py
- tests/test_settlement_timing.py
- NFL live pick writer
- First-signal repair
- DataGolf ingestor and NHL SBR archive
- Paused and no-signal pick rows
- NFL odds cache import to Supabase
- tests/test_health_check_observe.py
- Intraday freshness tests
- Kalshi prop ladder ingestor
- Module entrypoint guard tests
- tests/test_pick_lock_is_on_picks.py
- NFL 2026 rule track tests
- Public betting features and reverse line moves
- tests/test_team_stats_asof_invariants.py
- scripts: build_nfl_live_leader_artifact + model
- Published record reconciliation tests
- supabase/functions/discord-link/index.ts
- tests/test_nfl_prop_clv.py
- tests/test_prune_keeps_the_close.py
- tests/test_scoring_methods.py
- Mobile bankroll tests
- Live monitor dashboard cache and docs
- Worker job queue
- NCAAF situational spots
- Calibration and pipeline watchers
- Monitoring server tests
- nfl/scripts/backtest_opener.py
- Injury ingestor and ESPN NHL probables
- MLB retrain freeze tests
- tests/test_latest_odds_views.py
- NBA schedule ingestor and tests
- tests/test_nfl_prop_settle_name_fallback.py
- NFL recap waits for box scores tests
- tests/test_market_handicap.py
- tests/test_transaction_pooler.py
- NHL prop card and blocked shots
- Team stats as-of invariant tests
- NFL opener cut sweep and bettable books
- supabase/functions/sharpsports/index.ts
- NCAAF steam lag study
- MLB game market and public fade cards
- tests/test_worker_deps.py
- NCAAF research scripts and steam lag
- House juice price floor and retrain sweep job
- scheduler.py
- NFL prop lean concentration study
- NFL stale card file tests
- NHL totals lab
- Pipeline watch: posting ledger
- tests/test_mobile_stat_labels_match_the_server.py
- tests/test_ncaaf_fcs_visitor_names_migration.py
- tests/test_nfl_prop_unstarted_clear.py
- NBA, NCAAF and NFL research labs
- NFL live moneyline and total pricing tests
- Trainer no-register tests
- tests/test_savant_freshness.py
- tests/test_scorer_nfl_prop_like_escape.py
- NFL live leader config tests
- Signal publish-on-write ordering
- CLV no-vig capture tests
- NBA play-by-play aliases and derivation inputs
- Paused model assessment tests
- MLB backfill resilience tests
- tests/test_clear_unauthorized_auto_pauses_migration.py
- tests/test_ncaaf_se_louisiana_alias_migration.py
- tests/test_overnight_polling.py
- tests/test_revoke_remaining_grants.py
- tests/test_live_slate_midnight.py
- tests/test_nhl_stats_ingestor.py
- Bettable book card tests
- ncaaf_live/tests/test_cfbd_yardline.py
- Discord results recap and backfill
- tests/test_claude_rules_split.py
- tests/test_db_setup.py
- tests/test_dedupe_opening_signals.py
- Feature matrices across sports
- tests/test_every_named_book_is_fetched.py
- WNBA prop market card
- tests/test_pbp_backfill_resilience.py
- CLV no-vig and entrypoint tests
- Paused rows and NFL prop lead ceiling
- NCAAF prop market sweep
- MLB prop odds backfill tests
- NFL prop universe model rate
- Mobile stats filter UX check
- tests/test_game_log_backfill_skip.py
- NCAAF line move spots
- Live feed probe script
- tests/test_prompt_reads_thresholds.py
- tests/test_system_health_meta_steps.py
- NBA period scores ingestor
- scripts/render_brand_icons.py
- Dashboard rule model tests
- supabase/functions/stripe-webhook/index.ts
- tests/test_drop_voided_nfl_wind_opening_signals_migration.py
- tests/test_mobile_neutral_signal_label.py
- Mobile stat segment tests
- NFL prop opening signal cleanup tests
- tests/test_scorer_commits_per_game.py
- Model trainer and research scripts
- tests/test_live_game_state_poller.py
- NFL prop under bias study
- tests: test_wnba_availability + wnba_availability
- NFL prop pulled quote filter
- NCAAF venue feature tests
- supabase/functions/sharpsports-webhook: index + index
- ET game date tests
- supabase/functions/stripe-checkout/index.ts
- tests/test_book_list_budget.py
- Live scorer best line tests
- NBA game market lab
- Mobile NHL look-ahead window tests
- NFL prop week-one candidate pool
- NBA injury report player matching
- Registered not firing tests
- mobile/scripts/verify_a11y.ts
- Game line market sweep job
- tests/test_demote_ncaaf_over_under_platt.py
- Pipeline watch run and announce
- tests/test_discord_post_one_pick_migration.py
- tests/test_game_scorer_spares_nfl_props.py
- NBA play-by-play loader and gap fill
- tests/test_mobile_ota_self_update.py
- Decide on calibrated probability tests
- tests/test_team_board_commence_bound.py
- NFL prop book sweep and bettability
- Push notifier step
- scripts/nfl_wind_publisher.py
- Worker-only table guard tests
- SBR loader parsing
- Signal publish-on-write tests
- NFL research backup
- NHL moneyline market lab
- NFL live prop settlement tests
- Discord void notices
- NCAAF registry fake database
- Database URL doctor tests
- Parlay leg correlation estimates
- NFL live pick writer: night games and resolution
- Health check cadence tests
- Market handicap features
- tests/test_team_stats_asof_invariants.py
- tests/test_team_stats_asof_invariants.py
- tests/test_team_stats_asof_invariants.py
- tests/test_weekly_catch_up.py
- NCAAF travel geography features
- NHL goalie line helpers
- Pipeline watch: credit burn
- NHL prop EV lab and Kalshi ladder recording
- tests/test_live_orchestrator.py
- Live money no record-only tests
- Team stats twin code tests
- tests/test_team_stats_asof_invariants.py
- Mobile accessibility verify script
- Market handicap attach tests
- mobile/scripts/verify_a11y.ts
- mobile/scripts/verify_a11y.ts
- UFC event page parsers
- NFL live pick writer: publish refusals
- Prop CLV and SQL escaping tests
- mobile/scripts/verify_a11y.ts
- scripts: ncaaf_margin_eval + test_ncaaf_margin_eval
- Team stats verify alias test
- ncaaf_live/tests/test_serve.py
- NFL live pick writer tests
- Mobile TypeScript runners: error states and CLV card
- Database connection and CLI ingestors
- Pipeline watch: unfinished passes
- Health check lateness tests
- NCAAF feature assembly
- scripts/nfl_edge_preregistered_2026.py
- CFBD local season aggregates
- NFL prop market card and lead ceiling
- NBA stint clock and shot value tests
- Health skip budget names test
- NFL live pick announcer
- Calibration check coverage fixtures
- Worker job: Discord void notice
- tests: test_player_positions + player_positions_ingestor
- NBA prop slate test
- NBA prop read window test
- NBA play-by-play ledger column test
- Heartbeat watchdog state fixtures
- NFL weather cache import
- Pipeline watch and burn alerts
- NBA prop market card tests
- Pipeline watch: missing webhook
- NCAAF preferred provider resolution
- Market movement full-game snapshot filter
- Market movement newest two-sided quote
- Market movement in-play exclusion test
- Market movement pregame guard test
- NCAAF backtester and scorer dispatch test
- NCAAF null geography dropna test
- mobile/scripts/verify_a11y.ts
- Service role job filter test
- NCAAF backtester feature vector tripwire
- CFBD ingestor and school map
- NBA prop model lab
- tests/test_heartbeat_watchdog.py
- Supabase schema tables
- mobile/app.json
- mobile/package.json
- Games and latest odds views
- Player game log RPCs
- Picks and public track record views
- Latest line state tables
- mobile/tsconfig.json
- Discord link and Whop memberships
- Mobile package manifest
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
- NBA play-by-play write-up
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
- Game weather issued migration
- Odds API quota migration
- Parlay correlations migration
- Pick placement checks migration
- docs: nhl_market_lab + nhl_clv_ev_assessment
- Monitoring and record view docs
- docs/rules_evidence.md
- docs: probability_calibration + nfl_rule_2026_track
- NFL game lines model write-up
- nfl/live_model/README.md
- docs: followups + clv
- docs: best_line + config_topology
- docs/cloud_worker.md
- docs/history: learnings + build_state
- monitoring/static/dashboard.html
- docs/sports/nhl.md
- Model quality and MLB research docs
- docs: mlb_market_handicap_features + mlb_game_market_gate
- docs/sports/ncaaf.md
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
- NFL prop and live research write-ups
- .claude/rules: CLAUDE + config-topology
- .github/workflows: CLAUDE + mobile-build
- docs/agents_contract.md
- .claude/rules/operations.md
- docs/live_odds_freshness.md
- mobile/docs/UX_REVIEW.md
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
- .claude/rules/frontend.md
- docs/health_checks.md
- docs/retrain_2026_plan.md
- docs/reviews/2026-09-07-nfl-props-deep-dive.md
- NCAAF and MLB research docs
- docs/market_coverage.md
- (root): pr-ci + requirements
- docs/nfl_props_model.md
- docs/game_injury_gate.md
- NFL wind totals runbook and staking
- mobile/docs/BILLING.md
- docs/testing.md
- CLAUDE.md
- Player news docs
- NFL opener sharp-vs-soft findings

## God Nodes (most connected - your core abstractions)
1. `get_connection()` - 593 edges
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
- `Tables (all worker-only, locked down where they are created)` --references--> `diagnostics()`  [INFERRED]
  docs/nba_pbp_stints.md → scripts/nfl_edge_inplay_2025.py
- `2. Data used (all in Supabase)` --references--> `odds()`  [INFERRED]
  docs/nba_models_2026.md → tests/test_latest_line_state.py
- `3. The market grid` --references--> `odds()`  [INFERRED]
  docs/nba_models_2026.md → tests/test_latest_line_state.py

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

## Communities (892 total, 213 thin omitted)

### Community 0 - "ESPN injury team id fallback"
Cohesion: 0.26
Nodes (4): TestCoreTeamsFallback, _fetch_wnba_espn_team_ids_core(), _fake_fetch(), _listing()

### Community 1 - "Mobile stats board"
Cohesion: 0.01
Nodes (307): P, TouchSet, errorKind, gameStatus, RulerHold, RulerScale, MatchupGrade, MatchupInfo (+299 more)

### Community 10 - "Mobile error and load states"
Cohesion: 0.03
Nodes (87): LivePicksState, CountInput, DetailBody, LoadBody, LoadInput, PlayerSearchResult, OpeningSliceRow, OpeningVsLiveRow (+79 more)

### Community 104 - "Record correction post tests"
Cohesion: 0.06
Nodes (26): Ledger, _Result, _pin(), _real_post(), _real_tweet(), x_posts(), _publish(), test_a_failed_discord_ledger_does_not_send_x() (+18 more)

### Community 11 - "Odds, WNBA and shared ingestor plumbing"
Cohesion: 0.01
Nodes (263): ViewMigrationResult, TestTheResolverFailsClosed, TestTheStoreReadsTheStartTime, live_slate_dates(), get_connection(), release_read(), use_poller_session(), backfill_savant_stats() (+255 more)

### Community 113 - "tests/test_nfl_live_leader_gameday.py"
Cohesion: 0.05
Nodes (32): FakeClient, FakeClock, FakeConn, FakeFeed, _Rows, art(), live_state(), quote_payload() (+24 more)

### Community 114 - "nfl_live_leader/gameday.py"
Cohesion: 0.06
Nodes (28): Cadence, GameContext, LiveOddsFeed, Quote, LiveState, parse_book_ts(), build_pick(), evaluate() (+20 more)

### Community 115 - "tests/test_calibration_promotion.py"
Cohesion: 0.06
Nodes (28): FakeConn, _SchemaRecordingConn, eligibility_clause(), maps_materially_differ(), promote(), _payload(), _row(), test_a_broken_table_is_identity_maps_not_an_exception() (+20 more)

### Community 116 - "tests/test_score_off_any_book_line.py"
Cohesion: 0.08
Nodes (33): _FakeConn, _fallback_line_quote(), _cut(), _on(), _pick(), _row(), _sql_const(), _src() (+25 more)

### Community 118 - "tests/test_recap_restatement.py"
Cohesion: 0.07
Nodes (17): _Conn, test_a_restated_recap_is_labelled_and_says_why(), _resp(), test_a_404_is_an_answer_not_a_retry(), test_a_persistent_403_still_raises_after_the_last_attempt(), test_a_recap_whose_count_merely_drifted_is_not_due(), test_a_recap_with_a_late_settlement_is_due(), test_a_transient_403_is_retried_and_the_second_answer_is_used() (+9 more)

### Community 12 - "Mobile pick filters and sorting"
Cohesion: 0.02
Nodes (142): P, ActivePill, Props, reachFrame, DateOption, DayRow, SelectableGame, modelCategory (+134 more)

### Community 120 - "tests/test_ncaaf_alias_scores.py"
Cohesion: 0.10
Nodes (28): _FakeConn, alias_score_updates(), _date_or_none(), mirror_scores_to_alias_rows(), _cfbd(), _row(), test_a_bare_substring_is_not_an_extension(), test_a_daytime_game_has_no_duplicate_and_is_untouched() (+20 more)

### Community 121 - "tests/test_prop_alternate_lines.py"
Cohesion: 0.07
Nodes (27): _Conn, _Resp, alt_markets_due(), _ou(), _parse(), test_a_422_retries_without_the_alternates_before_going_dk_only(), fake_get(), test_a_422_with_no_alternates_still_takes_the_dk_only_retry() (+19 more)

### Community 122 - "Game scorer core and live scorer"
Cohesion: 0.01
Nodes (168): _Clock, TestAmericanToImpliedProb, TestConfidenceTier, TestQuarterKelly, today_et(), pregame_cutoff_sql(), build_mlb_game_features(), build_live_state_row() (+160 more)

### Community 123 - "tests/test_backtester.py"
Cohesion: 0.07
Nodes (9): TestCalibrationError, TestComputeBacktestSummary, TestEvaluateResult, TestGoLiveGateConstants, TestIterSides, _calibration_error(), compute_backtest_summary(), _evaluate_result() (+1 more)

### Community 124 - "scripts: nhl_prop_backtest + nhl_prop_ev_lab"
Cohesion: 0.12
Nodes (15): TestRegimeOrder, books(), sides(), best_per_player(), blocked_sides(), engine_sides(), history(), pool() (+7 more)

### Community 125 - "nfl/live_model/feeds/odds_live.py"
Cohesion: 0.04
Nodes (37): CreditBudgetExceeded, CreditMeter, LiveOddsClient, Quote, JsonlRecorder, best_price(), parse_events(), _parse_ts() (+29 more)

### Community 127 - "NHL props newest quotes and upcoming rows"
Cohesion: 0.11
Nodes (7): _Conn, TestOnlyTheNewestFetchIsShopped, TestWhoThePlayerIs, candidates(), identities(), latest_quotes(), upcoming_rows()

### Community 129 - "NBA prop market lab"
Cohesion: 0.09
Nodes (44): NBTable, add_units(), assemble(), best_per_key(), boot_ci(), build_quotes(), candidates_from(), choose_floor() (+36 more)

### Community 13 - "Discord signal notifier tests"
Cohesion: 0.02
Nodes (88): _FakeConn, _FakeResult, _StampConn, _cand(), _freeze_now(), _live_row(), _live_setup(), _no_prod_threshold_sync() (+80 more)

### Community 131 - "DDL guard and research backup snaps"
Cohesion: 0.03
Nodes (48): _FakeConn, _FakeCur, GuardConn, _fetchone(), schema_is_current(), back_up(), _connect(), digest() (+40 more)

### Community 135 - "mobile/scripts: verify_book_links + verify_betslip_combine"
Cohesion: 0.06
Nodes (37): betslipCombineKind, combineBetMgm(), combineBetslipLinks(), combineCaesars(), combineDraftKings(), combineEspnBet(), combineFanDuel(), fanDuelPairs() (+29 more)

### Community 137 - "NBA injury report pull retries"
Cohesion: 0.06
Nodes (32): _Conn, _Cur, _DatesConn, _Fetcher, _PdfFetcher, content_hash(), garbled_note(), pull_one() (+24 more)

### Community 14 - "Mobile custom model filters and metadata"
Cohesion: 0.03
Nodes (126): Props, Props, BacktestPickRow, CustomBacktestPickRow, CustomBacktestSummary, ChipGroup, ChipKey, FilterablePick (+118 more)

### Community 141 - "models/nhl_props.py"
Cohesion: 0.09
Nodes (26): Spec, _attach_teams(), build_frame(), build_goalie_frame(), build_skater_frame(), _ew(), excess_variance(), expected_value() (+18 more)

### Community 142 - "tests/test_health_pregame_prices_current.py"
Cohesion: 0.08
Nodes (31): _Conn, _at(), _game(), _row(), _run(), test_a_broken_feed_read_is_an_error_and_rolls_back(), test_a_broken_query_is_an_error_and_rolls_back(), test_a_cancelled_fight_and_a_pulled_game_do_not_raise_the_alarm() (+23 more)

### Community 143 - "Pick lock after settlement tests"
Cohesion: 0.08
Nodes (22): _SqliteShim, conn(), _game(), _pick(), _survivors(), test_a_bet_is_never_dropped_for_an_earlier_no_signal(), test_a_dead_zone_prop_row_locks_too(), test_a_final_game_is_not_a_scoring_target() (+14 more)

### Community 144 - "Mobile push test and diagnosis"
Cohesion: 0.08
Nodes (30): PushState, ForcedOnlyReason, PushDiagnosis, PushFailureReason, TestPushResult, reasonOf(), diagnosePushError(), errorText() (+22 more)

### Community 146 - "tests/test_mlb_game_market.py"
Cohesion: 0.05
Nodes (38): GameMarketBet, _SlateConn, find_spread_bets(), find_total_bets(), _gap_seconds(), _is_runline(), load_latest_quotes(), publish_enabled() (+30 more)

### Community 149 - "Discord results recap restates"
Cohesion: 0.10
Nodes (11): _Conn, step_settle(), test_a_restate_with_nothing_settled_late_is_a_no_op(), test_a_204_with_no_id_is_not_a_finished_recap(), test_a_posted_recap_ledgers_the_id_wait_returned(), test_a_rejected_post_is_recorded_and_the_next_pass_sends(), test_a_restate_that_raises_is_recorded(), test_a_restatement_stores_its_own_id() (+3 more)

### Community 150 - "Threshold review run tests"
Cohesion: 0.05
Nodes (30): _Conn, _quiet(), rule_only(), _slate(), test_a_losing_model_with_enough_bets_is_flagged(), test_a_losing_model_with_too_few_bets_is_left_alone(), test_a_milestone_fires_only_once(), test_a_model_paused_in_config_is_not_reported_again() (+22 more)

### Community 152 - "Idle read transaction tests"
Cohesion: 0.08
Nodes (14): _Rec, _flat(), test_a_lock_timeout_fails_that_file_and_the_next_still_runs(), test_a_locked_bet_releases_the_lock_check(), test_a_quiet_tick_rolls_the_read_back(), test_a_tick_that_writes_does_not_roll_the_insert_back(), test_an_unresolved_game_releases_the_context_read(), test_is_locked_releases_the_read() (+6 more)

### Community 155 - "tests/test_prop_box_scores.py"
Cohesion: 0.09
Nodes (18): GradeConn, ScriptConn, ensure_prop_box_scores(), missing_prop_games(), _pick(), test_a_logged_game_is_not_fetched_and_a_goalie_gap_is(), test_a_non_timeout_prop_error_rolls_back_and_raises(), test_a_probe_error_that_is_not_a_timeout_raises_after_rollback() (+10 more)

### Community 156 - "MLB totals public fade model"
Cohesion: 0.08
Nodes (29): PublicFadeBet, diff(), pitcher_diff(), diff(), pitcher_diff(), numeric_feature_value(), _better_under(), composite_score() (+21 more)

### Community 164 - "tests/test_nfl_opener.py"
Cohesion: 0.13
Nodes (8): TestFreshNumberLabel, TestHeldMinutes, _giants_board(), _giants_prior_at_2129(), _giants_sched(), _obs(), _ts(), book_for_pick()

### Community 165 - "NHL stats, game logs and SBR archive"
Cohesion: 0.03
Nodes (53): TestLogRowBuilders, TestNoHollowTeamRowBeforeTheFirstGame, TestSeasonLabel, backfill(), build_goalie_rows(), build_skater_rows(), build_team_rows(), _complete() (+45 more)

### Community 167 - "scripts/nfl_preflight.py"
Cohesion: 0.11
Nodes (22): TestRealSchema, TestSplitter, _load_postgres_schema(), setup_database(), _split_sql_statements(), setup_database(), check(), check_cards_run() (+14 more)

### Community 169 - "Mobile sign-in and auth"
Cohesion: 0.17
Nodes (24): AuthCallback, AuthDisabledError, AuthProvider, Nav, sendEmailCode(), signInWithProvider(), verifyEmailCode(), assertAuthEnabled() (+16 more)

### Community 170 - "Mobile billing config and verify script"
Cohesion: 0.09
Nodes (40): BillingRail, Plan, PlanKey, Nav, planFor(), describeSubscription(), formatPerMonth(), formatPrice() (+32 more)

### Community 174 - "tests/test_publisher_lock.py"
Cohesion: 0.07
Nodes (17): _Conn, _Result, _clear_locks(), _no_prod_threshold_sync(), _signal_row(), test_a_connection_that_cannot_lock_still_publishes(), test_an_exception_mid_publish_does_not_wedge_every_later_pass(), test_every_signal_publisher_takes_the_lock() (+9 more)

### Community 175 - "tests/test_dk_direct_feed.py"
Cohesion: 0.09
Nodes (22): _Conn, _game_id_for(), _row_for(), _seen_key(), _rec(), test_a_line_move_is_a_new_quote(), test_a_market_we_do_not_understand_is_dropped_not_guessed(), test_a_price_move_is_a_new_quote() (+14 more)

### Community 177 - "tests/test_credit_budget.py"
Cohesion: 0.09
Nodes (22): _Conn, daily_burn(), latest_remaining(), plan_credit_budget(), _burn_conn(), _plan(), test_a_billing_reset_is_not_a_refund(), test_a_call_is_billed_at_what_the_api_says_it_cost() (+14 more)

### Community 18 - "Mobile model screens and thresholds"
Cohesion: 0.02
Nodes (235): Case, Props, Props, ManualBet, ManualBetInput, ManualBetResult, CustomModelStats, Acc (+227 more)

### Community 180 - "NHL market-anchored moneyline model"
Cohesion: 0.05
Nodes (31): OffsetLogit, _Fixed, _GamesConn, _add_rating(), build_inputs(), choose_C(), decision_window(), fit() (+23 more)

### Community 186 - "NFL opener publisher and lock keys"
Cohesion: 0.10
Nodes (8): TestPublishOpenerInsertOnce, _LockConn, TestNoneRowNeverLocks, _model_lock_key(), publish_opener(), execute(), _lock_index(), _write_card()

### Community 189 - "Settlement and self-heal tests"
Cohesion: 0.06
Nodes (40): _SqliteShim, _FakeStatsapi, _SqliteShim, _box(), conn(), _game(), _live_bet(), raw() (+32 more)

### Community 19 - "NFL prop market stack, devig and information test"
Cohesion: 0.06
Nodes (37): TestNaNIsAbsent, devig(), closing_prices(), devig(), ecdf_p_over(), main(), bets(), design() (+29 more)

### Community 191 - "Mobile contrast token checks"
Cohesion: 0.05
Nodes (40): Pair, code(), lum(), noGreen(), over(), ratio(), read(), readUtf8() (+32 more)

### Community 194 - "tests/test_model_calibration_agent.py"
Cohesion: 0.05
Nodes (17): _ProbeConn, _rows(), test_a_prob_only_sweep_uses_only_the_probability_dimension(), test_column_migrations_run_every_pipeline_pass(), test_home_runs_are_no_longer_exempt_from_pausing(), test_plateau_is_computed_within_the_narrow_grid(), test_the_agent_changes_nothing_on_its_own(), test_the_agent_sweeps_every_registered_model_except_live_ones() (+9 more)

### Community 196 - "Monitoring and one-pick-per-event tests"
Cohesion: 0.06
Nodes (14): FakeConn, test_perf_reads_the_matview_not_the_expensive_view(), test_roster_reports_a_registered_but_untrained_model(), test_the_monitor_dashboard_box_score_arm_counts_each_event_once(), test_the_monitor_dashboard_picks_arm_counts_each_event_once(), _second_arm(), _sql(), test_a_fully_unpriced_recovered_model_reports_no_roi() (+6 more)

### Community 199 - "Prop price pregame cutoff tests"
Cohesion: 0.08
Nodes (14): _StubConn, _latest_dk_prop_row(), _assigned_from(), _prop_scorers(), test_every_scorer_call_site_passes_a_pregame_cutoff(), test_get_prop_dk_odds_forwards_the_cutoff(), test_in_play_snapshots_are_excluded_unconditionally(), test_it_fails_open_when_commence_time_is_missing() (+6 more)

### Community 2 - "Mobile markets and formatting"
Cohesion: 0.02
Nodes (236): Row, Props, Props, IoniconName, clvBetQuote, ClvBetRow, ClvBookRow, DecisionPriced (+228 more)

### Community 20 - "Mobile formatting and live status checks"
Cohesion: 0.04
Nodes (71): Props, Props, GameLike, InningHalf, LiveStateLike, LiveGameStateRow, check(), g() (+63 more)

### Community 200 - "NFL prop odds loading tests"
Cohesion: 0.09
Nodes (19): _Conn, _Cur, _fetch_slice(), _iter_prop_rows(), load_nfl_prop_odds(), load_nfl_prop_quotes(), _prop_slice_query(), statement_timeout_error() (+11 more)

### Community 201 - "Per-market EV floors and honest EV"
Cohesion: 0.09
Nodes (14): Gate, TestTheCard, expected_value(), min_ev_for(), test_ncaaf_live_ev_floor_is_wired_from_config(), pick_rows(), test_expected_value_is_on_the_quoted_price(), test_the_floor_is_the_global_one_unless_the_model_carries_a_higher_one() (+6 more)

### Community 203 - "tests/test_nhl_asof.py"
Cohesion: 0.19
Nodes (3): GoalieBook, TestGoalieAsOf, _g()

### Community 204 - "NFL prop model verdict tests"
Cohesion: 0.04
Nodes (30): TestBinaryMarket, TestCountDistributions, TestNormaliseName, TestSnapRows, TestVerdict, TestYesNoMarkets, _verdict(), _art() (+22 more)

### Community 205 - "NFL prop research readers and local store"
Cohesion: 0.03
Nodes (68): TestLocalCacheGuards, norm_player_name(), activate(), available(), _manifest(), _path(), read_table(), status() (+60 more)

### Community 208 - "tests: test_deploy_checks + deploy_checks"
Cohesion: 0.07
Nodes (17): _Conn, test_a_declared_job_carries_its_run_after(), test_a_failing_check_raises_so_the_queue_announces_it(), test_a_job_can_only_name_a_registered_check(), test_enqueue_rejects_a_naive_run_after(), test_enqueue_stores_run_after(), test_every_check_is_read_only(), test_the_claim_waits_for_run_after() (+9 more)

### Community 209 - "data/ingestors/nfl_inplay_history.py"
Cohesion: 0.16
Nodes (22): Budget, buy_halftime(), buy_inplay(), events_for(), _floor5(), _get(), halftime_requests(), halftime_windows() (+14 more)

### Community 211 - "Mobile bankroll separators check"
Cohesion: 0.09
Nodes (31): BankrollCheck, BankrollCommit, BankrollPatch, BankrollRead, NumberSeparators, Part, walk(), deviceSeparators() (+23 more)

### Community 212 - "Probability calibration and its sweep"
Cohesion: 0.03
Nodes (53): _FakeConn, apply_calibration(), demote(), ensure_schema(), _era_start(), fit_model(), fit_offset(), fit_platt() (+45 more)

### Community 214 - "NHL props card pick rows and quotes"
Cohesion: 0.08
Nodes (11): TestInsertOnce, TestTheBacktestGradesTheRuleTheCardPlays, TestTheCard, TestTheLimitPerGame, implied(), draftkings_at(), limit_per_game(), pick_rows() (+3 more)

### Community 216 - "NFL prop injury veto"
Cohesion: 0.11
Nodes (19): _InjConn, apply_injury_veto(), _as_dt(), player_is_vetoed(), should_veto(), _bet(), _idx(), _quotes() (+11 more)

### Community 217 - "NCAAF live engine pricing"
Cohesion: 0.08
Nodes (11): LiveEngine, expected_value(), _is_paused(), test_ev_floor_cannot_fire_without_a_price(), test_ev_floor_declines_a_qualifying_pick_that_is_priced_too_short(), test_ev_floor_only_tightens_and_never_touches_avoid(), engine(), test_the_cap_applies_to_the_avoid_side_too() (+3 more)

### Community 22 - "NBA prop projection card"
Cohesion: 0.07
Nodes (33): ProjectionBet, step_mlb_total_public_fade(), step_nba_prop_project(), backfill_official(), decided_games(), ensure_tables(), espn_pulls(), espn_rows() (+25 more)

### Community 220 - "tests/test_db_reconnect.py"
Cohesion: 0.08
Nodes (15): _Conn, _Cursor, _is_write(), _lost(), test_a_committed_transaction_is_clean_again(), test_a_lost_connection_with_uncommitted_writes_raises_connection_lost(), test_a_read_on_a_lost_connection_reconnects_and_retries(), test_a_statement_timeout_is_not_a_lost_connection() (+7 more)

### Community 223 - "tests/test_live_lock.py"
Cohesion: 0.13
Nodes (18): FakeConn, _Rows, _write_live_picks(), _locked_live_lanes(), _log_lines(), _pick(), test_a_locked_lane_still_says_so_and_names_the_lane(), test_all_lanes_locked_touches_nothing() (+10 more)

### Community 225 - "tests/test_refresh_retry.py"
Cohesion: 0.15
Nodes (22): RefreshRun, _decide(), _done(), _run(), test_a_failed_view_migration_fails_the_step(), test_a_pass_that_finished_with_failed_steps_ran_its_chain(), test_a_redeploy_between_passes_replaces_nothing(), test_a_restart_loop_does_not_buy_odds_on_every_boot() (+14 more)

### Community 226 - "NBA results ingestor store"
Cohesion: 0.06
Nodes (22): PgStore, PlayerResolver, call_in_savepoint(), box_is_complete(), build_dnp_rows(), build_log_rows(), fallback_id(), ingest_nba_results() (+14 more)

### Community 228 - "NBA results ingestor tests"
Cohesion: 0.09
Nodes (24): _Conn, _ESPN, FakeStore, _FixedNow, _game(), _resolver(), _run(), test_a_different_stored_score_is_never_overwritten() (+16 more)

### Community 23 - "NHL derivative odds history"
Cohesion: 0.08
Nodes (14): _Meter, _Resp, estimate_credits(), format_plan(), main(), run(), _markets(), test_apply_and_probe_without_a_key_return_before_any_call() (+6 more)

### Community 230 - "tests/test_local_cache_is_additive.py"
Cohesion: 0.11
Nodes (10): _FakeConn, _merge_with_cache(), _pull_odds(), cached(), _frame(), test_a_first_ever_pull_still_works(), test_a_pull_that_lost_rows_keeps_them(), test_an_unreadable_cache_refuses_rather_than_overwrites() (+2 more)

### Community 231 - "tests/test_calibration_check_coverage.py"
Cohesion: 0.10
Nodes (19): _Shim, _bet(), _calibration_results(), db(), _graded(), _make_db(), _only(), _promote() (+11 more)

### Community 232 - "Record correction posting script"
Cohesion: 0.09
Nodes (22): LedgerUnread, Conn, delete_custom_record_post(), _jump(), _place(), _publish(), publish_full_record(), publish_full_record_standard() (+14 more)

### Community 233 - "tests/test_book_team_map.py"
Cohesion: 0.11
Nodes (15): _Conn, abbr_from_team_string(), resolve_game_id(), split_matchup(), test_a_non_mlb_sport_is_refused_rather_than_guessed(), test_a_string_with_no_at_sign_is_refused(), test_a_unique_game_resolves(), test_an_ambiguous_game_resolves_to_none() (+7 more)

### Community 234 - "tests/test_team_board_cache.py"
Cohesion: 0.08
Nodes (11): _Conn, _Cursor, refresh_team_board_cache(), team_board_pairs(), team_board_seasons(), _cols(), test_every_team_sport_gets_last_this_and_next_year(), test_one_failing_pair_does_not_stop_the_rest() (+3 more)

### Community 236 - "mobile/src/lib: verify_discord_link + discordHelpers"
Cohesion: 0.11
Nodes (36): AccessState, useAccess, useEntitlement, FunctionResponse, LinkResult, AccessRow, AccessSource, DiscordCallback (+28 more)

### Community 238 - "nfl/live_model/tests/test_rush_attempt_pace.py"
Cohesion: 0.07
Nodes (21): Read, pace_ratio(), _sigmoid(), under_prob(), _price(), test_a_line_he_has_already_passed_is_not_a_live_proposition(), test_a_missing_accrued_count_is_refused_not_treated_as_zero(), test_a_reachable_over_is_declined_rather_than_faded() (+13 more)

### Community 239 - "tests/test_nfl_poll_fast_silence.py"
Cohesion: 0.12
Nodes (14): FakeConn, _append_board(), _body(), _row(), _sent(), _setup(), test_a_half_written_last_row_waits_for_the_next_tick(), test_a_killed_step_fails_the_run_loudly_after_publishing() (+6 more)

### Community 24 - "NHL market lab and live artifact grading"
Cohesion: 0.03
Nodes (102): OffsetLogit, accuracy(), first_games(), logloss(), main(), sweep(), units(), walk() (+94 more)

### Community 241 - "MLB prop market sweep"
Cohesion: 0.08
Nodes (13): _Conn, card(), load_quotes(), actuals(), grade_day(), main(), norm(), outs_from_ip() (+5 more)

### Community 242 - "Failure alerter and calibration watch"
Cohesion: 0.08
Nodes (12): TestHealthCheckOnlyIsNotADirtyPass, auto_pause_caveat(), _sweep(), _sweep_dates(), _clean_rate(), _is_health_check_step(), _latest_health_rows(), _pass_is_clean() (+4 more)

### Community 244 - "tests/test_weather_lookahead.py"
Cohesion: 0.09
Nodes (11): _Resp, TestTheHourIsTheGamesOwn, TestTheRequestCoversTheTargetHour, _celsius_to_f(), _fetch_open_meteo(), _game_hour_utc(), _target_hour_utc(), _utc_offset_from_lon() (+3 more)

### Community 245 - "tests/test_nhl_asof.py"
Cohesion: 0.13
Nodes (4): TeamBook, TestBlendedTeamInputs, TestTeamRatesAsOf, _r()

### Community 247 - "tests/test_dk_freshness_parse.py"
Cohesion: 0.12
Nodes (17): _FakeConn, _FakeResult, _american(), parse_dk_payload(), _store(), _payload(), test_a_half_priced_market_is_dropped_rather_than_half_recorded(), test_an_event_with_no_markets_yields_nothing_rather_than_raising() (+9 more)

### Community 248 - "tests/test_live_calibrated_decision.py"
Cohesion: 0.08
Nodes (18): RecordingConn, fetch_graded(), _in_graded_matview(), _is_live_lane(), _cut(), _signal(), test_a_big_enough_claim_still_fires_after_calibration(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking() (+10 more)

### Community 249 - "models: slate_concentration + test_slate_concentration"
Cohesion: 0.15
Nodes (15): SlateConcentration, apply_slate_guard(), apply_slate_concentration_guard(), _attr(), _edge_of(), _is_bet(), measure_side_concentration(), _side_of() (+7 more)

### Community 251 - "View migration lock handling tests"
Cohesion: 0.09
Nodes (23): _Conn, _Deadlock, _LockTimeout, _StatementTimeout, _Syntax, execute(), _before(), _code() (+15 more)

### Community 254 - "Prop odds missing-game and window tests"
Cohesion: 0.03
Nodes (21): FakeConn, _R, _athlete_name(), test_a_failed_lookup_is_not_cached(), test_a_known_athlete_costs_no_request(), test_a_SUCCESSFUL_response_with_no_name_is_not_cached(), test_an_unknown_athlete_is_fetched_and_then_remembered(), test_the_prop_fetch_never_buys_a_game_it_was_not_given() (+13 more)

### Community 256 - "Search feature matrices and opponent adjustment"
Cohesion: 0.07
Nodes (27): AdjRatings, blended_rating(), build_adjusted_ratings(), build_prior_season_ratings(), fit_opponent_adjustment(), load_fbs_membership(), load_team_games(), pool_fcs_opponents() (+19 more)

### Community 257 - "NCAAF search validation and openers"
Cohesion: 0.06
Nodes (36): FoldResult, features_for(), _apply_calibration(), exponential_recency_weights(), _logit(), make_ensemble(), fit_predict(), make_lgbm() (+28 more)

### Community 258 - "NFL weather and wind totals"
Cohesion: 0.04
Nodes (49): OpenMeteoError, Bet, coverage_check(), expected_true_wind(), fetch_era5(), fetch_issued_forecasts(), fetch_live_forecast(), _frame() (+41 more)

### Community 259 - "NFL player stats ingestors"
Cohesion: 0.03
Nodes (45): TestPublishLineSnapshots, TestParsePlayerRows, TestParseNflverseScores, backfill_nfl_player_stats(), current_nfl_season(), _fetch_game_dates(), _fetch_season_csv(), ingest_nfl_player_stats() (+37 more)

### Community 26 - "Mobile team detail and team stats"
Cohesion: 0.05
Nodes (98): NextGame, Section, TeamLineQuote, Tier, FormGame, FormSummary, headToHead, lineMove (+90 more)

### Community 265 - "Best line threshold sweep"
Cohesion: 0.08
Nodes (17): _Conn, american_to_decimal(), analyse(), split(), _basis(), _cut(), fetch(), units_at() (+9 more)

### Community 268 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.10
Nodes (7): TestBuildScoredRows, TestPickEmLabel, TestPreflightLockChecks, TestQualifyingRowIsNotANoneRow, _american_to_prob(), build_scored_rows(), _fmt_spread()

### Community 269 - "tests/test_cfbd_ingestor.py"
Cohesion: 0.07
Nodes (8): _GamesConn, _TeamsConn, test_ingest_games_retains_a_historical_utc_id_and_uses_et_for_a_new_row(), fake_get(), test_ingest_pulls_fbs_then_everyone_and_fbs_rows_win(), test_ingest_retries_everyone_without_a_year_if_the_season_filter_is_empty(), test_prior_context_tolerates_missing_talent_and_returning(), test_weekly_snapshot_build_aborts_on_failed_fetch()

### Community 27 - "Parlay builder and bet slip"
Cohesion: 0.02
Nodes (146): Props, ParlayRestorePayload, ResolvedSlip, LineLegSpec, MarketClass, BestBookPrice, LineShop, ParlayLeg (+138 more)

### Community 270 - "NCAAF in-play history tests"
Cohesion: 0.09
Nodes (18): _Conn, _StubEngine, decide(), first_signals(), grade(), _cand(), _event(), _no_db_school_lookup() (+10 more)

### Community 271 - "tests/test_line_clv.py"
Cohesion: 0.05
Nodes (12): _Conn, _stub_backfill(), test_hard_cap_stops_a_nonempty_queue(), test_loops_until_a_pass_fills_nothing(), test_the_runner_opens_get_connection_and_calls_backfill_clv(), _load(), test_a_line_that_held_is_exactly_zero_not_none(), test_a_missing_close_is_not_a_zero() (+4 more)

### Community 273 - "tests/test_prop_odds_utc_stamp.py"
Cohesion: 0.12
Nodes (13): _Conn, _assert_utc_stamp(), _frozen(), _run_mlb(), capture(), events(), _run_ncaaf(), test_an_eastern_row_then_a_later_utc_row_sorts_in_time_order() (+5 more)

### Community 274 - "Monitoring HTTP stream handler"
Cohesion: 0.29
Nodes (4): Handler, _connect(), dumps(), _json_default()

### Community 275 - "NFL lookahead signal tests"
Cohesion: 0.08
Nodes (15): _Conn, _sql_for(), test_a_started_game_is_still_never_published(), test_both_publishers_apply_the_apps_action_filter(), test_both_publishers_read_the_table_the_app_reads(), test_capture_reaches_as_far_as_the_poller_can_write(), test_capture_reaches_forward_for_the_locked_lookahead_sports(), test_ncaaf_lookahead_is_only_safe_because_the_lock_is_general() (+7 more)

### Community 278 - "tests/test_feature_artifact_agreement.py"
Cohesion: 0.11
Nodes (13): _Stub, _TolerantUnpickler, _load(), _newest_artifact(), test_artifact_width_matches_its_own_feature_cols(), test_config_list_matches_the_trained_artifact(), test_known_drift_only_names_real_models(), test_pending_features_are_not_live_without_a_retrain() (+5 more)

### Community 279 - "Player name matching tests"
Cohesion: 0.10
Nodes (14): FakeConn, normalize_player_name(), resolve_feed_name(), test_accented_roster_name_matches_the_flat_feed_name(), test_ambiguity_is_a_miss_not_a_guess(), test_an_unlisted_player_is_still_a_miss(), test_every_prop_lane_keys_line_shopping_on_the_resolved_name(), test_exact_spelling_still_takes_the_fast_path() (+6 more)

### Community 28 - "CLV price-taken tests"
Cohesion: 0.07
Nodes (22): _Conn, _Res, _fn(), _migration(), _pick(), test_a_draftkings_decided_row_is_unchanged(), test_a_legacy_row_that_cannot_be_re_measured_leaves_the_old_method(), test_a_legacy_stamped_row_is_re_measured_and_leaves_the_queue() (+14 more)

### Community 280 - "Mobile pick queries and hooks"
Cohesion: 0.02
Nodes (149): Props, FighterSide, Props, Args, PlayerNewsState, PlayerPropQuote, PropContext, DiscordPublish (+141 more)

### Community 281 - "tests/test_cloud_retrain_artifacts.py"
Cohesion: 0.10
Nodes (12): _Conn, _restore_artifact(), test_a_failed_upload_does_not_lose_a_model_that_trained(), test_a_missing_artifact_table_is_not_an_error_on_restore(), test_a_no_register_run_stores_nothing(), test_load_model_actually_loads_from_the_store_when_the_file_is_gone(), fetchone(), test_load_model_returns_none_when_the_store_has_nothing_either() (+4 more)

### Community 283 - "Decide-on-best-price and threshold SQL"
Cohesion: 0.10
Nodes (13): FakeConn, emit(), main(), _rules(), _source(), test_a_quote_with_no_stamp_is_kept(), test_a_stale_quote_cannot_decide(), test_every_scorer_insert_carries_the_decision_columns() (+5 more)

### Community 284 - "NCAAF FBS registry tests"
Cohesion: 0.12
Nodes (10): TestRefusalLog, TestRegistryHealthCheck, _alarm_part(), _live_db(), _promoted(), _rating(), _registry_check(), _snapshot() (+2 more)

### Community 288 - "tests/test_nfl_opener.py"
Cohesion: 0.18
Nodes (6): TestBettableBooksOnly, TestSelectOpenerBets, _both_sides(), _frame(), _row(), _sched()

### Community 290 - "NBA prop market publishing tests"
Cohesion: 0.13
Nodes (14): NbaPropBet, _PublishConn, pick_label(), pick_rows(), _bet(), _decision(), test_a_bet_at_draftkings_carries_no_best_columns(), test_a_bet_away_from_draftkings_with_dk_at_the_line() (+6 more)

### Community 291 - "tests/test_team_stats_asof_invariants.py"
Cohesion: 0.13
Nodes (6): _SeasonConn, test_verify_established_live_season_with_two_snapshots_stays_thin(), test_verify_five_day_span_with_one_snapshot_is_thin(), test_verify_four_day_opening_span_is_still_grace(), test_verify_opening_live_season_is_not_thin(), test_verify_short_historical_season_is_still_thin()

### Community 293 - "NHL props card tests"
Cohesion: 0.07
Nodes (14): _Shim, TestEveryLiveModelIsWiredEverywhere, TestSettlement, TestTheDistribution, TestTheGoalieFrame, TestTonightsRowIsATrainingRow, _bet(), _in_goal() (+6 more)

### Community 294 - "Starter-out dataset builder"
Cohesion: 0.12
Nodes (13): LabelSet, build_label_set(), _fetch_lines(), _fetch_raw(), _pick_provider(), build_sample(), grade(), _line() (+5 more)

### Community 298 - "tests/test_nfl_wind_publisher.py"
Cohesion: 0.13
Nodes (10): TestBuildRows, TestKickFields, TestParseMatchup, build_rows(), _fmt_line(), kick_fields(), parse_matchup(), test_nfl_wind_and_opener_rows_drop_a_bet_under_the_floor() (+2 more)

### Community 3 - "Prop odds and odds history ingestors"
Cohesion: 0.02
Nodes (103): ConnectionLost, Meter, Meter, Meter, TestEveryOtherSportStillMintsItsOwn, TestNflResolvesOntoTheSchedule, TestOddsFeedTeamNames, TestThreeWayMarketKey (+95 more)

### Community 30 - "NFL live prop model tests"
Cohesion: 0.04
Nodes (40): _FakeOdds, _IdRecordingOdds, _Q, GamedayWorker, GameTracker, _core_worker(), test_a_deployed_bias_must_sit_inside_its_measured_interval(), test_a_matching_board_keeps_the_fast_cadence() (+32 more)

### Community 300 - "tests/test_health_reason_and_cadence.py"
Cohesion: 0.19
Nodes (11): Report, _one(), test_a_24h_ts_check_reads_as_daily(), test_a_bare_add_still_fills_both_columns(), test_a_broken_query_is_its_own_reason(), test_a_passing_check_says_fresh(), test_a_skipped_check_says_the_gate_was_shut(), test_a_ts_check_reports_its_own_max_age() (+3 more)

### Community 301 - "tests/test_live_publish_parity.py"
Cohesion: 0.17
Nodes (12): _Conn, _db(), _labels(), _pick(), test_a_bet_written_while_paused_is_not_announced_after_an_unpause(), test_a_live_health_state_still_publishes(), test_a_paused_model_is_not_announced(), test_a_retired_model_is_not_announced() (+4 more)

### Community 302 - "tests/test_nfl_weather_supabase_readback.py"
Cohesion: 0.13
Nodes (13): FakeConn, _patch_conn(), _rows(), test_a_null_requested_lead_is_not_returned(), test_a_one_lead_response_is_not_stored(), test_a_partial_window_is_not_returned(), test_a_store_failure_is_a_warning_not_an_error(), test_a_subset_of_leads_reads_only_those_columns() (+5 more)

### Community 307 - "Pregame line poller"
Cohesion: 0.04
Nodes (45): _PollConn, changed_rows(), _fingerprint(), _key(), _num(), over_credit_cap(), poll_once(), quoted_keys() (+37 more)

### Community 308 - "Pitcher stats as-of invariant tests"
Cohesion: 0.05
Nodes (31): _FakeConn, last3_rates(), outs_from_ip(), per_nine(), whip(), _avg_distinct(), build_rows(), constant_era_pitcher_seasons() (+23 more)

### Community 309 - "tests/test_walk_forward_eval.py"
Cohesion: 0.11
Nodes (11): _Cols, _Frame, walk_forward(), _fake(), test_a_fold_with_too_little_history_is_skipped(), test_a_single_class_test_season_is_skipped(), _frame(), test_every_fold_trains_only_on_earlier_seasons() (+3 more)

### Community 31 - "NBA prop model core"
Cohesion: 0.05
Nodes (51): Spec, compact_report(), predict_means(), alias_key(), _attach_report_ids(), base_key(), box_panel(), build_frame() (+43 more)

### Community 313 - "NCAAF gameday pick lock tests"
Cohesion: 0.13
Nodes (12): FakeConn, _Rows, write_picks(), db(), test_both_lanes_locked_touches_nothing(), test_dry_run_never_touches_db(), test_first_bet_is_written_and_will_lock(), test_flag_off_restores_delete_and_replace() (+4 more)

### Community 314 - "Pipeline log reason tests"
Cohesion: 0.22
Nodes (6): _Conn, _capture(), test_a_false_step_records_the_last_error_it_logged(), test_a_false_step_that_logged_nothing_still_says_so(), test_a_raising_step_still_records_the_exception(), test_the_sink_is_removed_after_the_step()

### Community 316 - "NFL weather edge study"
Cohesion: 0.08
Nodes (28): DailyLimit, Pacer, audit(), baseline(), bh(), boot(), classify(), era() (+20 more)

### Community 319 - "Model quality monitor"
Cohesion: 0.03
Nodes (52): _Shim, duplicate_copy_exclusion_sql(), record_exclusion_sql(), _bet(), _fade_slate(), _insert_open_bet(), test_a_mixed_slate_is_ok(), test_all_home_ncaaf_slate_is_flagged_without_mlb_hardcoding() (+44 more)

### Community 32 - "NCAAF live pricing and score distribution"
Cohesion: 0.03
Nodes (56): ScoreDistribution, _cluster_bootstrap(), evaluate(), main(), report(), fit(), load_states(), main() (+48 more)

### Community 320 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.09
Nodes (6): _Pg, _PgCursor, TestPreflightCiMode, wind(), wrapped(), fake_open()

### Community 321 - "System health signal delivery tests"
Cohesion: 0.17
Nodes (4): TestSignalDelivery, _add_signal(), _iso(), _results()

### Community 322 - "Cursor wrapper and X results job tests"
Cohesion: 0.07
Nodes (9): _CursorResult, execute(), test_a_malformed_date_is_refused_before_anything_runs(), test_the_cursor_wrapper_rowcount_is_the_cursors(), test_the_job_does_not_bypass_the_day_is_over_guard(), test_the_job_does_not_read_rowcount_off_the_cursor(), test_the_job_only_clears_its_own_ledger_kind(), test_a_dropped_connection_replays_the_migration_with_its_lock_timeout() (+1 more)

### Community 323 - "NBA prop window scheduling tests"
Cohesion: 0.12
Nodes (21): _PlanConn, _fires(), _game(), _jobs(), _plan(), _t(), test_a_projection_too_old_to_price_does_not_block_the_retry(), test_a_tick_fetches_exactly_the_window_games_then_decides_closes_and_publishes() (+13 more)

### Community 327 - "tests/test_ncaaf_live_states.py"
Cohesion: 0.16
Nodes (13): _Conn, record_live_states(), state_change_row(), state_key(), _state(), test_a_failed_write_never_costs_the_pass(), test_a_score_a_period_or_a_possession_change_is_written(), test_first_sight_is_written() (+5 more)

### Community 33 - "nfl/live_model/feeds: test_feed_resilience + espn"
Cohesion: 0.04
Nodes (55): _ScriptedTick, _competitors(), _deref(), fetch_live_events(), _https(), make_fetcher(), fetch(), parse_core_event() (+47 more)

### Community 330 - "tests/test_nfl_opener.py"
Cohesion: 0.27
Nodes (5): TestBuildOpenerRows, build_opener_rows(), _opener_model(), _card_row(), _row()

### Community 34 - "Mobile app shell, feedback and sportsbook connect"
Cohesion: 0.02
Nodes (163): IoniconName, NavRef, PushStatus, ConnectionMap, providerMeta, SportsbookConnection, SportsbookProvider, FeedbackCategory (+155 more)

### Community 341 - "Live scorer score guard tests"
Cohesion: 0.14
Nodes (11): _FakeConn, _book_move(), _get_live_dk_odds(), _odds(), test_a_quote_published_before_the_score_is_declined(), test_a_quote_republished_after_the_score_is_kept(), test_the_age_bound_alone_would_have_allowed_it(), test_the_age_bound_still_fires_independently() (+3 more)

### Community 342 - "tests/test_live_pick_features.py"
Cohesion: 0.18
Nodes (11): FakeConn, _record_live_features(), _pick(), test_a_live_bet_records_its_feature_row_and_lambda(), test_a_pick_with_no_feature_row_is_skipped_not_written_empty(), test_a_recorder_failure_is_rolled_back_to_its_savepoint(), test_a_recorder_failure_is_swallowed_rather_than_raised(), test_a_success_releases_its_savepoint() (+3 more)

### Community 347 - "CLV backtest and shrunk ensemble build"
Cohesion: 0.14
Nodes (9): ShrunkEnsemble, add_form(), build(), feature_columns(), market_features(), team_game_stats(), fmt(), main() (+1 more)

### Community 348 - "Pregame price age: borrowed market quotes"
Cohesion: 0.09
Nodes (19): _OddsConn, _ago(), _clock(), _h2h_row(), _score_card(), test_a_bet_on_either_id_locks_the_model_for_both(), test_a_never_priced_id_is_not_scored_beside_its_priced_twin(), test_a_price_stored_this_pass_still_decides() (+11 more)

### Community 349 - "tests/test_prop_missing_features.py"
Cohesion: 0.14
Nodes (5): TestARowMissingAFeatureIsNotScored, TestEveryPropLoopGoesThroughTheHelper, TestTheUmpireIsTheDeclaredException, _frame(), helper()

### Community 35 - "NFL weekly wind card and odds snapshots"
Cohesion: 0.06
Nodes (30): OddsAPIClient, SnapshotResult, _key(), _ledger_bump(), _ledger_read(), ledger_status(), snapshot_to_frame(), unmapped_teams() (+22 more)

### Community 350 - "UFC fighter name resolution tests"
Cohesion: 0.07
Nodes (27): _FakeConn, normalize_method(), rounds_completed(), _fight_minutes(), _resolve(), test_alias_makes_both_sources_agree(), test_aliases_do_not_touch_unmapped_names(), test_confirmed_aliases_resolve_to_ufcstats_slug() (+19 more)

### Community 353 - "ESPN player news ingestor"
Cohesion: 0.03
Nodes (51): NewsItem, NewsPlayer, FakeConn, FakeResponse, _Result, _article_url(), _athletes_in(), build_name_index() (+43 more)

### Community 354 - "NBA prop closing line tests"
Cohesion: 0.09
Nodes (12): _Conn, _Resp, due(), test_a_close_already_held_is_not_bought_again(), test_a_due_close_buys_one_call_of_the_bet_markets_and_reports_its_credits(), test_a_pass_outside_the_window_spends_nothing(), test_only_a_game_holding_a_bet_and_only_once(), test_only_twelve_to_twenty_five_minutes_before_tip() (+4 more)

### Community 358 - "NFL live pick writer: declines and refusals"
Cohesion: 0.12
Nodes (12): PicksRecorder, _AvoidConn, _mk_decline(), test_a_market_opinion_decline_is_written_as_avoid(), test_a_moved_line_is_rewritten(), test_an_unchanged_proposition_is_not_rewritten(), test_plumbing_refusals_stay_out_of_picks(), test_recording_a_decline_can_never_break_a_bet() (+4 more)

### Community 36 - "tests/test_cfbd_ingestor.py"
Cohesion: 0.03
Nodes (63): _NullConn, build_ncaaf_game_id(), _day_before(), eastern_game_date(), parse_games(), parse_lines(), parse_teams(), retain_existing_cfbd_ids() (+55 more)

### Community 363 - "tests/test_run_ledger_orphans.py"
Cohesion: 0.12
Nodes (18): _Conn, db(), _insert_open(), _ledger(), _open_rows(), _row(), test_a_genuine_current_hang_is_still_detectable(), test_a_second_sweep_does_not_abort_the_pass_this_process_started() (+10 more)

### Community 378 - "NFL line snapshot tests"
Cohesion: 0.39
Nodes (3): TestSnapshotRowParams, snapshot_row_params(), _csv_row()

### Community 379 - "Mobile in-app purchases"
Cohesion: 0.13
Nodes (24): BillingDisabledError, CheckoutResult, IapPurchaseResult, PurchasesSDK, MinimalCustomerInfo, MinimalPackage, assertBillingReady(), billingErrorMessage() (+16 more)

### Community 38 - "Odds pruning and sharp book retention tests"
Cohesion: 0.09
Nodes (13): _RecordingConn, _prop_reference_books(), protected_for(), test_a_shopping_book_is_still_prunable(), test_every_prop_reference_book_is_protected(), test_every_sharp_book_is_protected_in_the_prop_table(), test_pinnacle_specifically_is_protected_in_the_prop_table(), test_prune_table_binds_the_prop_tables_carve_out_into_the_DELETE() (+5 more)

### Community 380 - "NFL live pick writer: decision rows"
Cohesion: 0.13
Nodes (10): _Decision, build_pick(), test_a_locked_lane_writes_nothing_further(), test_a_pass_is_never_announced(), test_edge_is_the_platform_edge_not_the_lanes_ev(), test_every_row_key_is_actually_bound_by_the_insert(), test_the_label_agrees_with_the_side_and_the_line_it_carries(), test_the_label_names_the_stat_the_model_actually_trades() (+2 more)

### Community 381 - "tests/test_heartbeat_disabled_jobs.py"
Cohesion: 0.23
Nodes (6): Conn, _build(), test_a_job_marked_disabled_is_not_silent(), test_a_job_that_runs_here_is_not_marked(), test_a_service_leaves_alone_the_jobs_another_service_owns(), test_startup_marks_an_owned_job_that_is_switched_off()

### Community 387 - "tests/test_repair_bogus_first_pitch_labels.py"
Cohesion: 0.13
Nodes (8): _Conn, _run(), test_a_dry_run_writes_nothing_at_all(), test_a_short_backup_rolls_back_and_relabels_nothing(), test_the_backup_is_written_before_the_update(), test_the_backup_table_is_revoked_from_the_public_roles(), test_the_bogus_set_is_computed_never_listed(), test_the_query_is_scoped_to_the_scheduled_start_not_the_derived_one()

### Community 39 - "nfl/live_model/tests/test_executor.py"
Cohesion: 0.06
Nodes (48): Decision, Executor, GameState, american_to_decimal(), derivative_lag(), ev_floor(), _mk(), expected_value() (+40 more)

### Community 393 - "tests/test_sbr_loader.py"
Cohesion: 0.14
Nodes (3): _SqliteConnShim, _SqliteCursorShim, loader_conn()

### Community 397 - "mobile/scripts/ux_scan.mts"
Cohesion: 0.16
Nodes (18): Finding, Severity, changedFiles(), entitlementGate(), fontScaling(), fontSizeLiterals(), hexColors(), main() (+10 more)

### Community 4 - "Feature engine and MLB line sweeps"
Cohesion: 0.01
Nodes (112): TestHasReturnee, TestHasStarterOut, TestMarketForOdds, TestPregameSnapshotGuard, TestAmericanToDecimalScorer, trusted_first_pitch(), query_injuries_for_game(), _blk_bullpen_ip() (+104 more)

### Community 402 - "Prop ladder and Kalshi prop market tests"
Cohesion: 0.04
Nodes (37): Ladder, Rung, TestMarketRelative, ladders(), ladders_or_empty(), find_bets(), _expit(), from_kalshi() (+29 more)

### Community 408 - "Price prefilter rollback and UFC model compare"
Cohesion: 0.06
Nodes (15): _PoisonConn, _fmt_et_time(), get_conn(), query(), implied(), payout(), rows_for(), _event_index() (+7 more)

### Community 409 - "mobile/src/lib/otaUpdate.ts"
Cohesion: 0.20
Nodes (13): Calls, CheckState, CheckTrigger, UpdateOutcome, UpdatesApi, check(), fakeApi(), main() (+5 more)

### Community 41 - "tests/test_live_quote_staleness.py"
Cohesion: 0.05
Nodes (42): _Conn, _Q, build_row(), _mark_written(), _publish_key(), quote_from_nfl_quotes(), record_live_prices(), rows_from_quote() (+34 more)

### Community 410 - "Prop market one side per line"
Cohesion: 0.16
Nodes (8): _Conn, best_per_prop(), _hockenson(), test_a_different_market_on_the_same_player_is_still_its_own_bet(), test_input_order_does_not_decide_the_side(), test_nfl_publish_will_not_add_the_other_side_of_a_locked_line(), test_opposite_sides_of_one_line_collapse_to_the_bigger_edge(), test_wnba_publish_will_not_add_the_other_side_of_a_locked_line()

### Community 417 - "Best game price tests"
Cohesion: 0.16
Nodes (10): FakeConn, _best_game_price(), test_a_better_price_at_a_different_total_is_not_the_same_bet(), test_a_better_price_at_the_same_total_wins(), test_an_unbettable_book_does_not_win_the_shop(), test_in_play_prices_are_excluded_from_best_line(), test_moneyline_has_no_line_to_match(), test_only_the_newest_snapshot_per_book_counts() (+2 more)

### Community 419 - "NFL prop market grading and kickoff gate"
Cohesion: 0.18
Nodes (5): TestKickoffGate, TestMarketGrading, _as_dt(), grade(), season_of()

### Community 422 - "NBA prop stat settlement tests"
Cohesion: 0.12
Nodes (8): _SelectConn, test_a_missing_stat_is_none_not_zero(), test_a_turnovers_bet_on_a_player_who_played_settles_win_not_no_action(), test_combo_markets_are_mapped_to_helpers_and_only_the_nba_rule_uses_them(), test_double_double_matches_the_rule_it_replaced(), test_the_loader_carries_every_stat_a_market_settles_on(), test_the_loader_selects_turnovers(), _nba_prop_actual()

### Community 423 - "NFL live leader model"
Cohesion: 0.17
Nodes (10): Artifact, Decision, am_to_dec(), artifact_from_dict(), band_for(), decide(), leader_expected_margin(), load_artifact() (+2 more)

### Community 424 - "supabase/functions/_shared/discord.ts"
Cohesion: 0.20
Nodes (15): DiscordApiError, DiscordUser, RoleSyncResult, addAppRole(), addGuildMember(), botFetch(), expectOk(), isGuildMember() (+7 more)

### Community 429 - "CLV price-taken and paper tracker"
Cohesion: 0.16
Nodes (6): _Conn, _Res, test_a_pick_draftkings_never_hung_closes_at_the_bet_book(), test_a_row_that_carries_dk_odds_keeps_its_book_and_price(), test_without_pinnacle_the_primary_is_still_the_bet_book(), _ts()

### Community 43 - "tests/test_job_queue.py"
Cohesion: 0.02
Nodes (72): _Conn, _DedupeConn, _VoidConn, _job_queue(), _fake(), _posted_row(), _quiet(), _run_void() (+64 more)

### Community 432 - "System health checks"
Cohesion: 0.04
Nodes (34): HealthReport, rollback_savepoint(), ncaaf_season_for_date(), test_delivery_fails_open_too(), test_health_check_uses_the_same_first_pitch_bound_as_discord(), test_mixed_timestamp_shapes_are_parsed_not_string_compared(), test_a_game_date_inside_the_window_counts(), test_a_lookahead_commence_counts_even_when_game_date_is_outside() (+26 more)

### Community 434 - "NBA prop market model and card"
Cohesion: 0.09
Nodes (25): NbaPropDecision, Plan, coherent(), fair_under(), fetch_times(), find_bets(), in_window(), load_quotes() (+17 more)

### Community 435 - "UFC late replacement tests"
Cohesion: 0.11
Nodes (7): _IngestConn, _ingest(), _one_fight_event(), test_a_late_replacement_is_not_scored_on_the_original_booking(), test_a_misspelled_fighter_is_scored_for_the_side_they_fought_on(), test_a_row_naming_neither_fighter_is_left_unscored(), test_the_same_fight_stored_twice_is_scored_on_both_rows_each_way_round()

### Community 436 - "tests/test_mlb_sbr_twin.py"
Cohesion: 0.21
Nodes (9): _Conn, _Cur, _lookup_home_won(), mlb_game_final(), sbr_twin_id(), test_no_final_anywhere_is_none(), test_scored_canonical_row_wins_and_keeps_its_label(), test_twin_id_swaps_only_the_renamed_franchises() (+1 more)

### Community 437 - "tests/test_ufc_phantom_filter.py"
Cohesion: 0.21
Nodes (6): TestFilterUfcPhantom, TestIsKnownUfcMatchup, _filter_ufc_phantom(), _is_known_ufc_matchup(), _game(), _odds()

### Community 440 - "NFL live pick writer: pass attempts and commits"
Cohesion: 0.12
Nodes (7): _Conn, test_a_pass_is_never_written_to_picks(), test_an_unresolvable_decision_writes_nothing(), test_game_id_resolves_from_the_book_s_team_names(), test_picks_recorder_drops_a_pass_attempt_over_before_sql(), test_the_announce_runs_after_the_commit_and_after_the_connection_closes(), commit()

### Community 442 - "tests/test_batter_prop_log_pin.py"
Cohesion: 0.10
Nodes (10): _Rec, _ScoringConn, build_batter_scoring_rows(), _log_sql(), test_batter_log_scan_is_pinned_to_the_lookback_not_the_catalog(), test_five_models_share_one_log_load(), test_no_lineup_does_not_scan_the_log(), test_starter_log_inside_the_batter_loader_uses_the_same_floor() (+2 more)

### Community 443 - "tests/test_opp_starter_features.py"
Cohesion: 0.09
Nodes (15): _StubConn, _StubResult, _opp_starter_savant(), _starter_gb_pct(), _batter_bulk(), test_batter_bulk_carries_everything_opp_starter_savant_reads(), test_it_reads_the_starters_savant_row(), test_live_mode_falls_back_to_prior_season() (+7 more)

### Community 446 - "tests/test_merge_mlb_twin_games.py"
Cohesion: 0.15
Nodes (9): _Conn, canonical(), counts(), test_a_canonical_id_maps_to_nothing(), test_a_non_mlb_or_malformed_id_is_left_alone(), test_an_empty_scope_counts_zero_rather_than_none(), test_both_teams_are_mapped_in_one_id(), test_only_the_four_renamed_franchises_map() (+1 more)

### Community 448 - "tests/test_discord_channel_probe.py"
Cohesion: 0.18
Nodes (7): _Resp, test_the_probe_covers_the_per_sport_live_channels(), test_the_probe_never_posts_and_never_returns_the_url(), test_the_probe_reports_the_channel_behind_each_sport(), _get(), test_two_sports_sharing_a_channel_are_flagged(), _job_discord_probe()

### Community 45 - "tests/test_nfl_prop_one_read_per_game.py"
Cohesion: 0.06
Nodes (25): _Conn, _Log, publish_hour_missed(), publishable_games(), _at(), _games(), test_a_game_is_publishable_on_exactly_one_pass_in_its_window(), test_a_game_with_no_kickoff_is_never_published() (+17 more)

### Community 457 - "Pipeline pass completion tests"
Cohesion: 0.16
Nodes (3): TestPassCompletion, TestPassSteps, _add_run()

### Community 464 - "NCAAF gameday cadence and live odds"
Cohesion: 0.04
Nodes (29): _Ctx, _ev(), _feed_with_payload(), gameday_mod(), _main_source(), _modelled_monthly_cfbd_calls(), test_a_single_failed_summary_does_not_drop_the_other_games(), test_a_sustained_feed_outage_degrades_to_no_odds() (+21 more)

### Community 469 - "Multi-book odds tests"
Cohesion: 0.04
Nodes (30): _OddsConn, _Resp, ncaaf_line_bookmaker(), _older_than(), _odds_query(), _prop_markets(), _source(), test_a_game_with_no_commence_time_keeps_every_row() (+22 more)

### Community 47 - "scripts/nfl_edge_gameline_rules.py"
Cohesion: 0.06
Nodes (50): Tee, TestTheWeatherStepWalksTheWindow, _nhl_blended_features(), d(), ats(), bettable_ats(), bh(), board_at() (+42 more)

### Community 470 - "Threshold review DDL tests"
Cohesion: 0.08
Nodes (9): _DdlConn, _DdlRes, _board_markets(), table(), test_the_mlb_board_and_the_mlb_pull_are_one_set(), test_a_failed_lock_down_does_not_lose_the_table(), test_ensure_schema_commits_the_tables_it_creates(), test_the_tables_are_locked_down_at_the_create_site() (+1 more)

### Community 471 - "tests/test_model_game_savepoint.py"
Cohesion: 0.15
Nodes (4): _PoisonConn, _games(), test_a_best_price_timeout_is_the_logged_error_and_the_next_lookup_runs(), test_a_model_sql_error_does_not_poison_the_next_model()

### Community 478 - "Mobile bankroll storage"
Cohesion: 0.23
Nodes (12): KeyValueStore, check(), eq(), fakeStore(), interleaving(), slowStore(), storage(), createBankrollStore() (+4 more)

### Community 48 - "tests/test_calibration_watch.py"
Cohesion: 0.06
Nodes (14): _Conn, _Res, TestDormantLiveModels, TestRosterChanges, TestTheRun, TestVerdictChanges, TestVolumeShifts, _row() (+6 more)

### Community 482 - "Calibration agent and external promote"
Cohesion: 0.16
Nodes (5): _Conn, promote_external(), test_external_promotion_refuses_a_map_that_does_not_transfer(), test_external_promotion_writes_only_the_promoted_columns(), test_the_scorer_reads_the_external_map_like_any_promoted_one()

### Community 483 - "NBA injury report scheduler"
Cohesion: 0.06
Nodes (34): Fetcher, _all_slots(), _ampm(), _bands(), _column_of(), _columns(), ensure_tables(), _hrules() (+26 more)

### Community 485 - "NFL weather, odds and wind card scripts"
Cohesion: 0.21
Nodes (6): Puller, _ledger(), main(), match_event(), _save_ledger(), snapshot_plan()

### Community 486 - "tests/test_pipeline_report_rollback.py"
Cohesion: 0.17
Nodes (5): _Conn, collect(), _rows(), test_a_failed_query_rolls_back(), test_one_broken_section_does_not_break_the_rest()

### Community 488 - "NBA lineup stint derivation"
Cohesion: 0.05
Nodes (48): Diagnostics, _Seg, score_plays(), _accumulate(), _add_one(), _and_one_follows(), appearances(), _athletes() (+40 more)

### Community 489 - "NFL pick monitor game id tests"
Cohesion: 0.16
Nodes (3): TestTheJoinKeyMatchesPicks, eval_row(), _picks_game_id()

### Community 49 - "Failure alerter fake-connection tests"
Cohesion: 0.10
Nodes (10): FakeConn, TestDeliveryAndNoise, TestItCannotBreakTheWorker, TestSilentJobs, TestWhatCountsAsAFailure, _clean_runs(), _posts(), _state_dir() (+2 more)

### Community 493 - "Pipeline watch: stale weeklies"
Cohesion: 0.16
Nodes (7): _Conn, test_a_fresh_sweep_and_savant_produce_no_finding(), test_a_missing_sweeps_table_is_reported_not_swallowed(), test_a_stale_sweep_date_is_reported(), test_savant_with_only_one_player_type_is_stale_even_when_dated_today(), test_the_kill_switch_works(), _stale_weeklies()

### Community 5 - "Mobile theme, parlays and sportsbook links"
Cohesion: 0.02
Nodes (204): Props, Nav, Props, Props, Props, FilterChipProps, Props, Props (+196 more)

### Community 518 - "NHL blocked shots settlement tests"
Cohesion: 0.27
Nodes (5): _Shim, TestSettlement, _bet(), _played(), _result()

### Community 519 - "Monitoring server tests"
Cohesion: 0.05
Nodes (30): _Resp, _credits_from(), classify(), paid_apis(), build_server(), serve_in_thread(), _get(), http_server() (+22 more)

### Community 52 - "Live best-takeable quote tests"
Cohesion: 0.04
Nodes (43): _FakeConn, _lane_signature(), _live_decision_quote(), _live_quote_is_on_offer(), best_takeable_quote(), _ev(), _live_pick(), _open_cut() (+35 more)

### Community 520 - "System health test fixtures"
Cohesion: 0.14
Nodes (4): _FrozenDatetime, _Shim, db(), mlb_wired()

### Community 526 - "MLB in-play game state alignment"
Cohesion: 0.22
Nodes (6): GameClock, _t(), test_before_first_pitch_and_after_last_play_are_not_priced(), test_between_pas_across_third_out_rolls_over_to_next_half(), test_mid_plate_appearance_is_that_pa_before_state(), test_plays_without_times_are_ignored()

### Community 528 - "NFL prop odds frame loading"
Cohesion: 0.26
Nodes (5): TestLocalOddsCache, _odds_from_frame(), _p(), _odds_frame(), test_a_one_way_market_stays_one_way_through_the_cache()

### Community 53 - "NFL team row parsing tests"
Cohesion: 0.11
Nodes (10): TestGamesRows, TestKickoff, TestParseTeamRows, TestUpcomingRows, games_rows(), _int_or_none(), _kickoff_utc(), _num_or_none() (+2 more)

### Community 533 - "NFL wind card bettable books"
Cohesion: 0.10
Nodes (9): TestTheCardFilters, test_the_card_records_a_decision_when_nothing_qualifies(), test_a_replay_never_prices_off_todays_ladder_even_when_on(), test_the_card_does_not_price_off_kalshi_until_it_is_graded(), _attach(), books(), card(), _quote() (+1 more)

### Community 536 - "Health skip budget tests"
Cohesion: 0.16
Nodes (6): FakeConn, test_a_check_never_seen_non_skipped_counts_its_whole_history(), test_a_check_skipped_only_today_is_not_counted_as_a_streak(), test_streak_counts_calendar_days_from_the_last_non_skipped_run(), test_the_streak_query_fails_open(), _skip_run_days()

### Community 54 - "tests/test_void_picks.py"
Cohesion: 0.05
Nodes (12): _FakeConn, TestAPostedSignalIsLocked, TestAPostedVoidAnnouncesAfterCommit, TestTheToolRefusesToMatchEverything, TestVoidingAPostedPickIsAnExplicitOptIn, TestWhatMayBeVoided, TestWhatTheVoidWrites, build_parser() (+4 more)

### Community 544 - "NCAAF feature engine and FBS registry"
Cohesion: 0.04
Nodes (29): TestFbsGate, TestUnratedFbsClaim, build_ncaaf_game_features(), fbs_refusal_claims(), _get_ncaaf_team_stats(), _hfa_live(), _home_venue_live(), is_bowl_game() (+21 more)

### Community 55 - "NCAAF gameday worker and CFBD feed"
Cohesion: 0.05
Nodes (34): LiveOddsFeed, GameContext, _Conn, _Result, now_iso(), school(), fetch_scoreboard_cfbd(), fetch_team_ids() (+26 more)

### Community 559 - "First-signal repair fake connections"
Cohesion: 0.18
Nodes (3): _Conn, _VoidedConn, _make()

### Community 56 - "tests/test_daily_retry.py"
Cohesion: 0.06
Nodes (43): _Conn, _Cursor, _FrozenDatetime, DailyRun, Decision, _aborted(), _aborted_row(), _ok() (+35 more)

### Community 562 - "NBA prop roster name resolution"
Cohesion: 0.23
Nodes (5): Roster, name_key(), test_a_books_initials_match_the_logs(), test_a_rookie_logged_under_an_espn_id_resolves_to_it(), test_the_resolver_uses_the_results_writers_normaliser()

### Community 564 - "NFL live pick writer: failure isolation"
Cohesion: 0.17
Nodes (6): _OpenConn, test_a_failing_announcer_cannot_undo_or_fail_the_write(), test_a_failing_recorder_cannot_take_the_other_down(), boom(), test_a_written_bet_is_announced_with_its_own_game_date(), test_an_unlocked_lane_does_write()

### Community 57 - "tests/test_live_book_move_guard.py"
Cohesion: 0.08
Nodes (38): BookMoveClock, _MlbConn, american_to_implied(), _at(), _delaware_ctx(), _dk(), _iso(), _mlb_odds() (+30 more)

### Community 570 - "NFL opener tick latency tests"
Cohesion: 0.11
Nodes (6): TestTickLatency, label(), test_projecting_runs_after_the_decisions_are_published(), test_the_tick_passes_a_days_that_covers_the_whole_window(), test_the_tick_returns_free_outside_the_window(), test_the_twelve_distributional_models_score_off_the_ticks_own_fetch()

### Community 576 - "tests/test_weekly_catch_up.py"
Cohesion: 0.18
Nodes (3): _Conn, test_a_failing_savant_refresh_does_not_cost_the_calibration_its_catch_up(), test_ownership_is_checked_per_job()

### Community 579 - "tests/test_umpire_ingestor.py"
Cohesion: 0.26
Nodes (3): TestHealWindowLo, _heal_window_lo(), run_umpire_ingestor()

### Community 58 - "Discord signal fields and best-price restates"
Cohesion: 0.04
Nodes (48): _FakeConn, _sig(), test_a_strictly_better_book_becomes_the_headline(), test_an_equal_or_worse_price_never_replaces_draftkings(), test_best_odds_never_reaches_the_qualifying_gate(), test_draftkings_winning_its_own_shop_is_published_as_draftkings(), test_every_pre_game_producer_computes_good_to(), test_good_to_is_published_when_the_producer_supplies_it() (+40 more)

### Community 582 - "Prop odds book update-time tests"
Cohesion: 0.26
Nodes (6): _Conn, _parse(), test_a_row_built_without_the_key_still_inserts_as_null(), test_no_clock_anywhere_is_none_not_our_fetch_time(), test_the_column_is_added_only_when_the_catalog_lacks_it(), test_the_markets_own_clock_is_stored_else_the_books()

### Community 583 - "NFL pick monitor"
Cohesion: 0.11
Nodes (11): TestClassify, TestImmutabilityContract, TestLatestPerPick, TestWindPublisherLock, classify(), _f(), latest_per_pick(), main() (+3 more)

### Community 59 - "NFL live leader state client"
Cohesion: 0.12
Nodes (18): CoreClient, EventMeta, _abbr(), game_seconds(), https(), _int(), is_admin_play(), is_conversion_play() (+10 more)

### Community 592 - "Live quote score clock"
Cohesion: 0.14
Nodes (6): ScoreClock, _Unset, test_score_clock_ignores_a_dropped_score_field(), test_score_clock_keeps_games_independent(), test_score_clock_reports_no_event_at_first_sight(), test_score_clock_stamps_the_change_and_holds_it()

### Community 594 - "NFL prop card publisher tests"
Cohesion: 0.12
Nodes (7): MarketBet, TestMarketCardPublisher, test_nfl_prop_market_card_drops_a_bet_under_the_floor(), test_wnba_prop_market_card_drops_a_bet_under_the_floor(), test_publish_skips_games_with_no_games_row(), execute(), execute()

### Community 595 - "Voided pick exclusion tests"
Cohesion: 0.21
Nodes (4): _Conn, _db(), test_a_voided_pick_is_not_a_free_pick_candidate(), test_a_voided_pick_is_not_a_parlay_leg()

### Community 6 - "Paper tracker bankroll and scorer database calls"
Cohesion: 0.01
Nodes (167): DBConnection, _connect(), connection_lost(), _go(), _open(), _session_options(), statement_timeout(), mirror_stored_finals() (+159 more)

### Community 604 - "Best line and best-price decision tests"
Cohesion: 0.18
Nodes (4): TwoOrientationConn, test_a_non_ufc_game_is_not_looked_up_twice(), test_ufc_h2h_resolves_the_sibling_orientation_and_flips_the_side(), test_ufc_totals_keep_their_side_on_the_sibling()

### Community 61 - "mobile/src/hooks: verify_tracked_performance + useStakeSettings"
Cohesion: 0.09
Nodes (40): StakeMode, StakeState, LiveTrackSnapshot, TrackedBetRow, trackedBetStatus, TrackedBetSummary, emit(), load() (+32 more)

### Community 611 - "supabase/functions/revenuecat-webhook/index.ts"
Cohesion: 0.22
Nodes (3): RcEvent, admin, PRODUCT_TO_PLAN

### Community 613 - "supabase/functions/whop-webhook/index.ts"
Cohesion: 0.25
Nodes (4): WhopMembership, signatureValid(), timingSafeEqual(), admin

### Community 617 - "Model trainer, WNBA and NHL research scripts"
Cohesion: 0.02
Nodes (103): LazyConnection, TestYardageDistribution, TestTrainingExcludesThemAndScoringDoesNot, assert_retrain_allowed(), calibration_method(), scoring_method(), name_key(), _add_features() (+95 more)

### Community 622 - "NFL prop odds loader tests"
Cohesion: 0.24
Nodes (3): TestPropOddsLoader, _Conn, _Cur

### Community 626 - "NHL as-of lookup tests"
Cohesion: 0.22
Nodes (4): TestOpeningNightIsEarlySeason, _blk_nhl_asof(), _t(), test_the_training_path_reads_nhl_odds_by_game_not_by_sport()

### Community 63 - "NFL live game state and parity"
Cohesion: 0.05
Nodes (30): Read, blind_over_prob(), over_prob(), _pass_attempt_bias_allowed(), _as_float(), _as_int(), _as_opt_float(), _as_opt_int() (+22 more)

### Community 630 - "Scorer feature values and starter gate tests"
Cohesion: 0.13
Nodes (5): TestFeatureValue, TestMissingStarterGate, _feature_value(), test_apply_game_market_gate_fail_open_without_conn(), test_scorer_live_default_downgrades_steamed_and_public_steam()

### Community 631 - "Mobile auth hook"
Cohesion: 0.22
Nodes (14): AuthState, AuthStatus, useAuth, useSubscription, SubscriptionRow, applySession(), bootstrap(), handleAppStateChange() (+6 more)

### Community 634 - "Paused bets keep their verdict"
Cohesion: 0.18
Nodes (3): _Capture, test_a_paused_settled_bet_never_moves_the_kelly_bankroll(), test_todays_standing_bets_ignore_a_paused_row()

### Community 642 - "NFL DraftKings line snapshot tests"
Cohesion: 0.32
Nodes (4): TestDkLineRows, dk_line_rows(), _num(), _rec()

### Community 643 - "Odds, prop odds and NHL derivative odds ingestors"
Cohesion: 0.29
Nodes (3): TestResolveGameId, resolve_nfl_game_id(), resolve()

### Community 644 - "NFL prop price math tests"
Cohesion: 0.22
Nodes (3): TestPriceMath, american_to_profit(), no_vig_pair()

### Community 645 - "NBA injury report PDF parser"
Cohesion: 0.18
Nodes (9): Report, finish_rows(), parse_pdf(), parse_title(), rows_from_pages(), season_of(), test_finish_rows_builds_our_game_id_and_season(), test_report_time_comes_from_the_header_and_is_stored_in_utc() (+1 more)

### Community 65 - "NFL live backtest harness and calibration"
Cohesion: 0.03
Nodes (53): ScoreDistribution, _cluster_bootstrap(), evaluate(), main(), report(), align_states(), build_team_map(), _game_index() (+45 more)

### Community 668 - "NFL prop market stack and devig"
Cohesion: 0.46
Nodes (6): Pick, _fmt_edge(), _fmt_odds(), main(), _pick_card(), render_email()

### Community 669 - "Mobile bankroll store"
Cohesion: 0.32
Nodes (7): BankrollSettings, useBankroll(), canStepUnitPct(), sanitizeUnitPct(), stepUnitPct(), store, BANKROLL_DEFAULTS

### Community 67 - "tests/test_game_market_gate.py"
Cohesion: 0.06
Nodes (49): GateVerdict, MarketBookend, PublicSplits, apply_to_picks(), _as_float(), bookend_from_odds(), evaluate(), fair_prob() (+41 more)

### Community 675 - "Calibration watch announcer"
Cohesion: 0.25
Nodes (3): TestItNeverDecides, _announce(), _announce_and_ledger()

### Community 69 - "tests/test_pick_integrity.py"
Cohesion: 0.04
Nodes (38): _Conn, _Shim, _add_pick(), discord_sent(), _health(), health_db(), test_a_label_may_not_name_a_market_the_pick_does_not_settle_on(), test_a_label_naming_the_other_team_is_refused() (+30 more)

### Community 7 - "Mobile track record and sharp score checks"
Cohesion: 0.03
Nodes (92): EquityPoint, Slop, StatusForSpeech, ContrarianTone, ModelClv, publicSplit, PublicTone, SharpBand (+84 more)

### Community 70 - "tests/test_record_one_pick_per_event.py"
Cohesion: 0.04
Nodes (42): _CaptureConn, _RecordingConn, _code(), _copy_for_node(), _fn(), _node(), _read(), test_a_custom_model_counts_the_kept_copy_once() (+34 more)

### Community 73 - "nfl/live_model/tests: test_props + props"
Cohesion: 0.09
Nodes (33): PropProjection, PlayerState, _accrued(), _count(), detect_inactive(), price_over(), project(), _rate() (+25 more)

### Community 755 - "First-five any-book line tests"
Cohesion: 0.43
Nodes (6): _Clf, _mlb_feat(), test_score_game_fires_f5_ou_when_fanduel_prices_it(), test_score_game_fires_f5_rl_when_fanduel_prices_it(), test_score_game_skips_f5_when_no_real_price(), test_score_game_skips_unpriced_synthetic_sbr()

### Community 758 - "NCAAF alias score mirroring"
Cohesion: 0.33
Nodes (3): _FakeCursor, test_stored_finals_are_mirrored_without_a_cfbd_pull(), execute()

### Community 77 - "tests/test_wnba_prop_market.py"
Cohesion: 0.06
Nodes (27): _FakeConn, _QuoteConn, apply_price_floor(), norm_name(), pick_rows(), f(), _bet(), _q() (+19 more)

### Community 78 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.11
Nodes (12): _Conn, _RaceConn, TestFlexedKickoffRefreshes, TestLockSurvivesNothing, TestNoneRowBesideABetIsCleared, TestPublishRace, TestPublishScored, _bet_row() (+4 more)

### Community 79 - "NHL derivative totals model"
Cohesion: 0.09
Nodes (24): Market, build_p1_frame(), build_team_frame(), day_interval(), _ew(), fit(), game_means(), _implied_vec() (+16 more)

### Community 8 - "Mobile player log and matchup stats"
Cohesion: 0.02
Nodes (246): Props, PlayerNextGame, Section, Args, PlayerStatKey, Sport, HitMode, HitSelection (+238 more)

### Community 80 - "NHL totals card and market"
Cohesion: 0.06
Nodes (34): NhlTotalBet, _LockConn, _SlateConn, implied(), _coherent(), _fetch_ts(), find_bets(), load_fetch_quotes() (+26 more)

### Community 83 - "Publish key identity tests"
Cohesion: 0.05
Nodes (25): _Conn, _KeyConn, _key(), _mobile(), _sql(), test_a_game_level_live_row_keeps_the_key_it_was_published_under(), test_a_game_level_row_keeps_the_key_it_was_published_under(), test_a_player_id_row_keeps_the_key_it_was_published_under() (+17 more)

### Community 84 - "Discord notifier and void notices"
Cohesion: 0.02
Nodes (81): _Resp, DiscordVoidRejected, UnitStake, announce_posted_voids(), main(), _select(), void(), test_a_429_reports_what_discord_asked_for() (+73 more)

### Community 85 - "tests/test_recap_retries_a_skipped_day.py"
Cohesion: 0.08
Nodes (24): World, _add_pick(), _grade(), _schema(), test_a_day_with_nothing_counting_posts_nothing_and_logs_nothing(), test_a_failed_receipt_never_reposts_the_day(), test_a_failed_receipt_on_a_restatement_never_repeats_it(), test_a_late_pick_after_the_retry_is_restated_once_not_reposted() (+16 more)

### Community 90 - "tests/test_f5_any_book_line.py"
Cohesion: 0.11
Nodes (22): _GameOddsConn, _fallback_game_line_quote(), _has_real_game_price(), _cut(), _on(), _spreads_row(), _src(), test_a_quote_after_first_pitch_does_not_score() (+14 more)

### Community 92 - "tests/test_ncaaf_prop_odds.py"
Cohesion: 0.05
Nodes (27): _Conn, _Resp, _market_chunks(), _football_map(), resolver(), scope(), test_a_book_we_did_not_ask_for_is_never_written(), test_a_day_with_no_college_games_spends_nothing() (+19 more)

### Community 93 - "tests/test_mlb_total_public_fade.py"
Cohesion: 0.08
Nodes (36): _EmptyConn, find_fade_bets(), is_pre_commence(), select_latest_pre_commence_over(), under_in_odds_band(), pick_rows(), publish(), _dk_board() (+28 more)

### Community 94 - "NFL prop event market list tests"
Cohesion: 0.22
Nodes (3): TestIngestEventsDoesNotShadowItsMarkets, test_live_prop_pull_asks_for_the_sharp_book(), fake_event_props()

### Community 95 - "tests/test_ncaaf_pbp_store.py"
Cohesion: 0.07
Nodes (22): _Conn, _extremes(), load_season_from_db(), observed_ranges(), _report_ranges(), store_season(), _plays(), test_a_one_season_build_gets_its_own_filename() (+14 more)

### Community 97 - "Game injury veto gate and tests"
Cohesion: 0.09
Nodes (32): _InjConn, apply_to_picks(), _goalie_names(), load_sport_injury_index(), _pitcher_names(), player_matches_veto(), relevant_players(), _star_names() (+24 more)

### Community 98 - "NHL prop card and blocked shots model"
Cohesion: 0.05
Nodes (32): TestTonightsRowIsATrainingRow, TestWhoThePlayerIs, build_frame(), _ew(), expected_value(), fit(), load_skaters(), load_teams() (+24 more)

### Community 99 - "Publish keys and Discord sync tests"
Cohesion: 0.02
Nodes (60): Ledger, _posted_sql(), test_a_real_pause_is_not_logged_as_stale(), execute(), test_empty_set_errors_when_a_stale_pause_flag_hides_bets(), execute(), _sql_key(), test_a_game_level_key_has_no_tail() (+52 more)

### Community 100 - "NBA stint derivation tests"
Cohesion: 0.08
Nodes (45): order_plays(), _blowout_q4(), derive(), dreb(), _dup_game(), end_period(), five_game(), make2() (+37 more)

### Community 101 - "NCAAF slug and orientation helpers"
Cohesion: 0.08
Nodes (17): _loose_orientation(), ncaaf_slug(), parse_team_game_stats(), _possession_seconds(), _slug_extends(), _slug_pair(), _split_ratio(), _to_int() (+9 more)

### Community 102 - "scripts/nfl_edge_live_rush_pace.py"
Cohesion: 0.18
Nodes (26): _asof(), boot_p(), build_state(), first(), grade(), initial_last(), load_pbp(), main() (+18 more)

### Community 103 - "NBA prop projection tests"
Cohesion: 0.06
Nodes (27): _art(), _proj(), _q(), _run(), _settle(), test_a_book_hanging_two_lines_for_one_player_is_refused(), test_a_decision_with_no_bet_is_still_a_decision(), test_a_past_game_never_projected_gets_the_newest_espn_pull_55_minutes_before_its_tip() (+19 more)

### Community 105 - "Mobile live segment wiring tests"
Cohesion: 0.06
Nodes (28): _read(), test_a_sport_switch_cannot_report_a_game_finishing(), test_all_three_segments_are_unconditional(), test_live_is_not_a_bottom_tab(), test_live_is_not_in_the_tab_param_list(), test_no_app_root_component_reaches_a_focus_aware_hook(), imports_of(), strip_comments() (+20 more)

### Community 107 - "tests/test_prop_calibrated_decision.py"
Cohesion: 0.07
Nodes (29): apply_prop_daily_cap(), _claimed_ev(), dedupe_player_props(), _downgrade(), _bet(), _identity_cal(), _prop(), test_a_genuinely_big_edge_still_fires_after_calibration() (+21 more)

### Community 108 - "ncaaf_live/tests/test_pregame_calibration.py"
Cohesion: 0.05
Nodes (24): american_to_prob(), devig_power(), correct_for_pregame(), _load_pregame_calibration(), pregame_dog_points(), _real_artifact(), test_a_big_dog_is_marked_down_hard(), test_a_corrupt_artifact_leaves_the_probability_alone() (+16 more)

### Community 110 - "tests/test_mobile_line_movement.py"
Cohesion: 0.08
Nodes (27): _fn(), _read(), _run(), test_a_cut_table_keeps_the_pick_and_says_what_it_covers(), test_a_cut_window_keeps_the_pick_row_on_the_8_row_table(), test_a_pick_made_after_the_cards_start_never_reads_since_your_pick(), test_after_the_start_the_verdict_is_not_graded(), test_an_old_snapshot_is_not_the_price_at_the_pick() (+19 more)

### Community 111 - "tests/test_live_calibration.py"
Cohesion: 0.06
Nodes (36): _live_calibration(), pick(), test_a_peak_with_no_plateau_anywhere_is_labelled_as_one(), test_a_prob_cut_and_an_ev_cut_select_different_picks(), test_calibration_also_scores_ev_against_realised_roi(), test_calibration_is_empty_rather_than_wrong_with_nothing_settled(), test_calibration_reports_the_gap_between_claim_and_reality(), test_expected_value_matches_the_hand_calculation() (+28 more)

### Community 112 - "Push deep link and mobile player detail tests"
Cohesion: 0.03
Nodes (56): test_every_revoke_names_the_roles_rather_than_public(), test_odds_keeps_select_for_the_app(), test_the_two_rls_off_tables_lose_everything(), _read(), test_every_player_page_read_names_its_relation_literally(), test_next_game_is_earliest_in_the_window_not_tonights_date(), test_results_are_units_never_dollars_and_never_paper(), test_sharp_gap_is_no_vig_vs_no_vig() (+48 more)

### Community 117 - "Heartbeat watchdog and ops alerts"
Cohesion: 0.09
Nodes (13): _alert(), _alerter_is_silent(), _newest_run_age_minutes(), _read_state(), _should_notify(), _state_path(), _write_state(), stale_jobs() (+5 more)

### Community 119 - "tests/test_ncaaf_live_notify.py"
Cohesion: 0.05
Nodes (18): _load_write_picks(), _restore_stubbed_modules(), test_a_caller_supplied_connection_is_not_closed_by_the_write(), test_a_failing_notifier_never_breaks_pricing(), test_a_full_slate_announces_once(), test_a_live_bet_notifies_push_and_discord(), test_a_locked_lane_is_not_rewritten(), test_a_locked_lane_keeps_notifying_after_the_engine_stops_betting() (+10 more)

### Community 126 - "monitoring/store.py"
Cohesion: 0.10
Nodes (23): meta(), ops(), snapshot(), api_rollup(), call_timeline(), calls_since(), community(), scalar() (+15 more)

### Community 128 - "tests/test_settled_record_is_immutable.py"
Cohesion: 0.05
Nodes (26): paused_row_exclusion_sql(), _code(), test_a_dedicated_live_lane_still_counts_and_a_pre_game_in_play_pick_does_not(), test_a_paused_model_is_not_an_excluded_model(), test_a_voided_pick_is_still_out_of_the_record(), test_both_published_views_keep_the_live_date_gate(), test_both_rules_name_the_two_exits_and_not_the_paused_flag(), test_both_views_are_redefined_by_name() (+18 more)

### Community 130 - "features/golf_feature_engine.py"
Cohesion: 0.08
Nodes (25): assemble_player_features(), _avg_finish(), _event_finishes(), _f(), _field_features(), _made_cut_rate(), matchup_diff_features(), _mean() (+17 more)

### Community 132 - "NCAAF live state building tests"
Cohesion: 0.08
Nodes (33): main(), build_states(), _classify(), classify_report(), _detect_score_convention(), load_pbp(), load_platform_games(), pace_report() (+25 more)

### Community 133 - "tests/test_bovada_feed.py"
Cohesion: 0.11
Nodes (29): _american(), _complete(), _num(), parse_coupon(), _row_for(), _seen_key(), _stamp(), _coupon() (+21 more)

### Community 134 - "tests/test_market_movement.py"
Cohesion: 0.12
Nodes (19): american_to_prob(), build_market_features(), _s(), test_a_game_with_no_decision_book_still_gets_features(), test_a_line_that_genuinely_did_not_move_is_zero_not_none(), test_a_one_way_sharp_quote_yields_nothing(), test_a_single_snapshot_yields_no_movement_rather_than_zero(), test_american_to_prob_both_signs() (+11 more)

### Community 136 - "tests/test_ncaaf_cross_book_opener.py"
Cohesion: 0.07
Nodes (25): _minutes_apart(), build_artifact(), build_band_artifact(), _branch(), test_absent_ceiling_means_unbounded(), test_artifact_shape(), test_band_ceiling_is_enforced_in_the_scorer(), test_band_volumes_sum_to_the_single_gate_backtest() (+17 more)

### Community 138 - "tests/test_paused_keeps_real_verdict.py"
Cohesion: 0.07
Nodes (35): _bet(), _bodies(), _code(), _fn(), _game(), _pause(), _prop(), _rules() (+27 more)

### Community 139 - "NFL in-play edge studies 2024-25"
Cohesion: 0.09
Nodes (48): books_per_snapshot(), cell(), families(), finalize_states(), fmt(), h1(), h1_calibration(), h1_frame() (+40 more)

### Community 140 - "UFC event and fight page parsers"
Cohesion: 0.15
Nodes (9): _aggregate_stats(), _kd_int(), _mmss_to_sec(), _of_pair(), parse_fight_page(), test_kd_int_handles_float_strings_and_blanks(), test_mmss_to_sec(), test_of_pair() (+1 more)

### Community 145 - "NBA prop projection model"
Cohesion: 0.08
Nodes (22): asof_roster(), box_from_log(), coherent(), collapse_official(), espn_compact(), find_bets(), implied_one(), main_line() (+14 more)

### Community 147 - "scripts/nfl_edge_extreme_props.py"
Cohesion: 0.12
Nodes (29): actuals(), add_modes(), bar(), candidates(), cell(), decision_boards(), devig(), fit_holdout() (+21 more)

### Community 148 - "scripts/nfl_edge_settlement.py"
Cohesion: 0.14
Nodes (30): add_test(), attach(), banner(), bh(), board(), boot_draws(), cell(), choose() (+22 more)

### Community 15 - "X publisher tests"
Cohesion: 0.03
Nodes (41): _creds_on(), _fake_conn(), _split(), test_a_day_with_nothing_graded_carries_no_clv_line(), test_a_day_with_nothing_risked_states_units_and_does_not_divide(), test_a_different_secret_changes_the_signature(), test_a_split_that_cannot_fit_says_how_many_it_dropped(), test_a_transport_failure_returns_none_rather_than_raising() (+33 more)

### Community 153 - "tests/test_agents_contract.py"
Cohesion: 0.06
Nodes (19): _labelled_retired(), test_blocked_items_are_marked_so_the_agent_skips_them(), test_every_backlog_item_is_a_checkbox(), test_neither_agent_may_change_a_model_threshold(), test_the_agents_are_findable_from_the_file_every_session_reads(), test_the_backlog_does_not_promise_an_agent_that_no_longer_runs(), test_the_backlog_exists_and_has_items(), test_the_contract_documents_every_agent_by_name() (+11 more)

### Community 154 - "Market coverage probe tests"
Cohesion: 0.07
Nodes (17): candidate_markets(), _standard_markets(), test_a_two_sided_market_is_never_reported_one_sided(), test_an_all_line_leg_slip_does_not_claim_a_model(), test_it_asks_about_the_board_columns_that_are_permanently_blank(), test_it_reports_supported_but_empty_apart_from_unsupported(), test_no_market_is_asked_about_twice(), test_one_market_per_call_so_a_rejected_key_is_identified_exactly() (+9 more)

### Community 157 - "Position vs opponent tests"
Cohesion: 0.07
Nodes (19): _bn_body(), _sql_groups(), test_a_failed_position_read_is_said_not_hidden(), test_a_failed_read_is_not_held_on_the_spinner(), test_every_mlb_stat_chip_has_a_branch(), test_every_nfl_stat_chip_has_a_branch(), test_every_roster_sport_chip_has_a_branch(), test_mlb_lineup_buckets_agree_between_app_and_server() (+11 more)

### Community 158 - "Best prop and game price selection tests"
Cohesion: 0.08
Nodes (20): _best_of(), _best_prop_price(), _same_line(), _source(), test_a_book_can_only_be_offered_if_it_is_also_fetched(), test_best_fields_are_all_null_when_no_book_priced_the_side(), test_best_fields_report_the_edge_at_the_price_offered(), test_best_of_ignores_books_with_no_price() (+12 more)

### Community 159 - "WNBA results ingestor parsers"
Cohesion: 0.08
Nodes (28): build_log_row(), _core_athlete(), _deref(), _et_date(), _fetch_core_box_players(), _fetch_core_games(), parse_core_event(), parse_core_stat_values() (+20 more)

### Community 16 - "Daily pipeline runner and push notifier"
Cohesion: 0.02
Nodes (69): _run_migrations(), run_bullpen_ingestor(), run_nfl_player_stats_ingestor(), run_nba_prop_odds_ingestor(), run_wnba_prop_odds_ingestor(), mirror_unchanged(), format_view_migration_failure(), check_env() (+61 more)

### Community 160 - "NFL in-play flow evaluation and validation"
Cohesion: 0.03
Nodes (91): bias_table(), main(), apply_anchor(), best_hit(), _boot_ci(), drop_degenerate(), evaluate(), fit_time_curve() (+83 more)

### Community 161 - "NBA box score enrichment"
Cohesion: 0.07
Nodes (49): _blank(), box_rows(), _check_unmapped(), _create(), dnp_kind(), ensure_tables(), fetch_advanced(), fill_missing_game_logs() (+41 more)

### Community 162 - "X publisher and brand avatar"
Cohesion: 0.07
Nodes (29): discover(), fetch_all(), _get_image(), main(), _original_size(), store(), _x_api_profile(), test_the_record_restatement_and_the_slate_restatement_are_separate() (+21 more)

### Community 163 - "NFL in-play edge study 2025"
Cohesion: 0.08
Nodes (43): s(), fit_models(), async_check(), attach_games(), attach_state(), best_by(), bh(), boot() (+35 more)

### Community 166 - "Mobile preferred book and line-shop checks"
Cohesion: 0.04
Nodes (39): alone, dkUser, fits, hrUser, live, many, ml, mlRows (+31 more)

### Community 168 - "Push notifier and tickets"
Cohesion: 0.09
Nodes (26): _msgs(), test_a_credentials_failure_disables_nobody(), test_a_request_level_rejection_accepts_nothing(), test_a_retired_device_is_named_for_disabling(), test_a_single_message_reply_may_be_a_bare_object(), test_a_ticket_that_is_not_an_object_is_not_a_delivery(), test_an_error_ticket_is_not_counted_as_sent(), test_an_unpairable_reply_counts_nothing_and_disables_nothing() (+18 more)

### Community 17 - "MLB in-play history and live cut sweeps"
Cohesion: 0.04
Nodes (60): _get(), _iso(), main(), planned_calls(), pull_day(), rows_for(), _served_already(), shard_windows() (+52 more)

### Community 171 - "NFL stake sizing simulation"
Cohesion: 0.21
Nodes (13): american_to_decimal(), breakeven(), kelly(), log_growth(), main(), _norm_ppf(), posterior(), _rules() (+5 more)

### Community 172 - "NFL in-play prop engine calibration"
Cohesion: 0.08
Nodes (20): evaluate(), _infer_position(), main(), _pool_prior(), report(), _rows_for_market(), _to_states(), accrual_at() (+12 more)

### Community 173 - "tests/test_decide_on_calibrated.py"
Cohesion: 0.07
Nodes (16): _pick(), test_a_calibrated_cut_is_paired_with_a_calibrated_decision(), test_a_genuinely_big_edge_still_fires_after_calibration(), test_a_hot_model_no_longer_fires_the_marginal_bet(), test_a_model_on_a_calibrated_cut_is_not_paused(), test_a_paused_model_never_fires_regardless(), test_an_unmapped_model_is_completely_unaffected(), test_live_pitcher_props_paused_on_current_artifact_remesure() (+8 more)

### Community 176 - "NBA prop projection lab"
Cohesion: 0.08
Nodes (51): apply_calibration(), fit_calibration(), fit_platt(), _logit(), bars(), bh_read(), blind(), boot() (+43 more)

### Community 178 - "NFL prop odds ingestor and backfill"
Cohesion: 0.07
Nodes (20): backfill_nfl_prop_odds(), backfilled_dates(), census_books(), _credits_used(), _event_props(), _get(), _ingest_events(), list_events() (+12 more)

### Community 181 - "tests/test_nfl_rule_2026_track.py"
Cohesion: 0.15
Nodes (15): classify(), fetch(), grade_rows(), is_void(), lead_days(), _load_nfl_model(), main(), report() (+7 more)

### Community 182 - "tests/test_model_artifacts_load.py"
Cohesion: 0.09
Nodes (17): _git(), _gitignore_keep_pkls(), _ignored(), _manifest_keep_pkls(), _newest_per_model(), test_a_path_that_is_not_ignored_is_not_reported(), test_a_superseded_timestamped_pkl_is_ignored(), test_an_ignored_path_comes_back_byte_identical() (+9 more)

### Community 185 - "scripts/game_line_market_sweep.py"
Cohesion: 0.07
Nodes (21): _by_month(), collect_picks(), devig(), grade(), implied(), iter_months(), load(), load_chunked() (+13 more)

### Community 187 - "Push deep link tests"
Cohesion: 0.08
Nodes (23): _code(), _py_version(), _read(), test_a_single_pick_deep_links_and_a_batch_does_not(), test_an_unreadable_payload_routes_nowhere_rather_than_guessing(), test_both_halves_pin_the_same_payload_version(), test_every_expo_message_carries_a_data_payload(), test_every_summary_producer_can_deep_link_a_single_pick() (+15 more)

### Community 188 - "tests/test_pass_instrumentation.py"
Cohesion: 0.06
Nodes (11): test_a_dead_database_does_not_fail_the_step(), test_a_raised_failure_still_records_the_exception(), test_a_step_that_raises_is_still_TIMED(), test_a_step_that_raises_still_raises(), boom(), test_a_step_that_returns_false_records_a_REASON(), test_a_successful_step_records_a_duration(), test_every_step_name_in_the_dispatch_table_is_reachable() (+3 more)

### Community 190 - "tests/test_db_adapt_sql.py"
Cohesion: 0.09
Nodes (23): _adapt_sql(), _convert_params(), _convert_params_outside_literals(), _named(), test_a_block_comment_is_skipped_too(), test_a_colon_word_inside_a_comment_is_not_a_placeholder(), test_a_dash_dash_inside_a_literal_is_data_not_a_comment(), test_a_line_comment_ends_at_the_newline() (+15 more)

### Community 193 - "tests/test_first_signal_repair.py"
Cohesion: 0.13
Nodes (22): step_restore_first_signals(), patch_conn(), _sql_of(), test_a_lane_already_holding_its_first_bet_is_untouched(), test_a_lane_with_no_sibling_still_restores(), test_a_lane_with_nothing_standing_is_restored(), test_a_pregame_model_is_not_marked_live(), test_a_price_move_alone_is_a_different_bet() (+14 more)

### Community 195 - "tests/test_mobile_contrast_tokens.py"
Cohesion: 0.13
Nodes (30): _code_lines(), _ionicon_colors(), _lum(), _over(), _ratio(), _read(), _rgb(), test_badge_glyph_tracks_dynamic_type() (+22 more)

### Community 197 - "NBA stats ingestor"
Cohesion: 0.09
Nodes (22): backfill_nba_stats(), _build_game_id(), _build_game_rows(), _build_player_log_rows(), _build_team_stat_rows(), _fetch_league_game_log(), ingest_nba_game_log_for_date(), _ingest_season() (+14 more)

### Community 198 - "Historical odds backfill tests"
Cohesion: 0.04
Nodes (38): _ledger_entry_is_resumable(), _mark_in_play(), relabel_in_play(), run_historical_odds_range(), test_a_run_that_writes_nothing_is_not_reported_as_success(), test_the_insert_rolls_back_per_row(), test_capture_compares_the_picks_own_clock_not_the_capture_clock(), test_capture_fails_open_on_a_missing_timestamp() (+30 more)

### Community 206 - "tests/test_live_inning_gate_replay.py"
Cohesion: 0.12
Nodes (28): _grade(), _pair(), _refuse_tables(), _score_seen_at(), _game(), _price(), _scored(), _sig() (+20 more)

### Community 207 - "NBA prop over probability and calibration"
Cohesion: 0.09
Nodes (16): exclude_taken(), fit_calibration_before(), p_push(), stake(), team_spread(), regrade(), _synthetic_pairs(), test_a_proposition_another_model_bets_is_removed_on_every_line_and_side() (+8 more)

### Community 21 - "NFL edge studies: luck gap and halftime"
Cohesion: 0.03
Nodes (112): backfill_cost(), bets(), bh(), clean_2h(), fmt(), forward_2026(), hdr(), _line_models() (+104 more)

### Community 210 - "CLV math: same-book and market-edge"
Cohesion: 0.09
Nodes (22): test_a_one_way_close_is_not_de_vigged(), test_a_worse_close_is_negative_and_equal_prices_are_zero(), test_devigging_the_taken_price_is_not_what_primary_does(), test_kalshi_close_is_not_de_vigged(), test_market_edge_devigs_only_the_close(), test_other_side_prices_include_the_draw_on_a_three_way(), test_power_devig_of_a_balanced_market_is_a_coin_flip(), test_primary_does_not_move_when_the_other_side_changes() (+14 more)

### Community 215 - "First pitch pregame snapshot tests"
Cohesion: 0.06
Nodes (16): test_a_late_start_is_believed_because_it_is_real(), test_a_missing_actual_start_falls_back_to_the_schedule(), test_both_missing_still_fails_open(), test_every_is_pregame_snapshot_caller_passes_first_pitch(), test_it_never_overwrites_commence_time(), test_the_actual_start_wins_over_the_schedule(), test_the_boundary_itself_is_pregame(), test_the_clamp_sits_in_the_gap_the_data_leaves() (+8 more)

### Community 218 - "Prop ladder and unique pick tests"
Cohesion: 0.04
Nodes (30): _identity_maps(), _platform_gates_off(), test_breakeven_is_the_real_vig_hurdle(), _declared(), test_an_explicit_run_date_must_be_a_real_iso_date(), test_declared_keys_are_unique(), test_every_declared_job_names_a_registered_type(), test_every_declared_job_validates() (+22 more)

### Community 219 - "tests/test_nfl_live_leader_state.py"
Cohesion: 0.14
Nodes (19): situation(), status(), test_a_conversion_try_is_skipped(), test_a_previous_quarters_play_is_not_the_state(), test_a_timeout_is_skipped_for_the_play_before_it(), test_after_a_scoring_play_nothing_is_evaluated(), test_after_the_kickoff_lands_the_receiver_has_the_ball(), test_an_ordinary_snap_is_evaluable_with_the_training_inputs() (+11 more)

### Community 221 - "tests/test_ncaaf_qb_ingestor.py"
Cohesion: 0.12
Nodes (22): _athlete_stats(), _comp_att(), parse_qb_game_stats(), _parse(), _payload(), _team(), test_athlete_stats_helper_is_category_scoped(), test_athlete_without_an_id_is_ignored() (+14 more)

### Community 222 - "NBA ESPN box and scoreboard parsers"
Cohesion: 0.09
Nodes (21): box_team_totals(), nba_team(), _no_minutes(), parse_nba_box(), parse_nba_dnp(), parse_nba_scoreboard(), _played(), _team_blocks() (+13 more)

### Community 224 - "NBA derivative market lab"
Cohesion: 0.09
Nodes (35): add_team(), am_to_dec(), bars_for(), bet_list(), blind(), boot_ci(), build_line_rows(), build_outcomes() (+27 more)

### Community 229 - "NBA prop model verification script"
Cohesion: 0.12
Nodes (29): adv_from_log(), asof_roster(), blind_structured(), card_block(), collapse_report(), _compare(), log(), main() (+21 more)

### Community 235 - "NCAAF feature engine tests"
Cohesion: 0.15
Nodes (16): _assemble(), _stats(), test_a_push_yields_no_target(), test_assembly_diffs_and_context(), test_bulk_loads_both_markets_of_the_historical_line(), test_early_season_is_flagged_not_gated(), test_fbs_gate_rejects_an_explicitly_fcs_classification(), test_fbs_gate_rejects_an_fcs_team_that_has_a_snapshot_row() (+8 more)

### Community 237 - "Discord price bound tests"
Cohesion: 0.10
Nodes (16): _dec(), test_a_field_without_a_bound_renders_without_the_clause(), test_a_model_with_no_own_ev_floor_is_bound_by_the_global_one(), test_a_price_floor_can_be_the_binding_gate(), test_a_rounded_bound_still_clears_the_bound_it_came_from(), test_even_money_is_plus_one_hundred(), test_no_bound_from_junk_rather_than_a_guess(), test_no_bound_when_the_edge_floor_is_unreachable() (+8 more)

### Community 240 - "tests/test_ncaaf_game_identity.py"
Cohesion: 0.12
Nodes (16): _add(), _conn(), _identity_sql(), _run(), test_a_clean_slate_reports_nothing(), test_a_non_fbs_fixture_is_not_reported(), test_a_phantom_opponent_is_detected_too(), test_a_real_doubleheader_is_not_a_duplicate() (+8 more)

### Community 243 - "MLB stats ingestor and pitcher backfill"
Cohesion: 0.07
Nodes (24): backfill_bullpen_stats(), backfill_mlb_stats(), backfill_pitcher_stats(), backfill_player_game_log(), _build_pitcher_rows(), _build_team_stats_rows(), _fetch_mlb_api_batting(), _fetch_mlb_api_pitcher_stats() (+16 more)

### Community 25 - "NBA play-by-play ingestor"
Cohesion: 0.06
Nodes (40): _bool(), box_context(), box_finals(), build_game(), drop_duplicate_box_ids(), _float(), _int(), _last() (+32 more)

### Community 250 - "data/ingestors/nhl_boxscore.py"
Cohesion: 0.11
Nodes (16): _decision(), fill_missing(), _insert_absent(), _int(), _name(), parse_boxscore(), side_rows(), store_boxscore() (+8 more)

### Community 255 - "MLB totals public fade top-k study"
Cohesion: 0.12
Nodes (17): american_units(), bucket_win_rates(), build_candidates(), _fmt(), grade_under(), holdout_take(), load_db(), load_json() (+9 more)

### Community 260 - "tests/test_live_game_features.py"
Cohesion: 0.11
Nodes (19): compute_live_target(), half_innings_left(), parse_bases(), state_features(), test_build_live_state_row_merges_pregame_context(), test_build_live_state_row_unusable_state(), test_half_innings_left_bottom_ninth(), test_half_innings_left_extras_clamps_to_one() (+11 more)

### Community 261 - "tests/test_ncaaf_totals_regression.py"
Cohesion: 0.10
Nodes (14): total_over_prob(), test_artifact_kind_is_routed_by_the_scorer(), test_asymmetry_is_real_and_would_have_bitten(), test_extremes_are_clamped_away_from_certainty(), test_model_above_the_line_favours_the_over(), test_model_below_the_line_favours_the_under(), test_no_dk_total_means_skip_not_prob_only(), test_no_residuals_returns_one_half_not_a_confident_bet() (+6 more)

### Community 262 - "UFC feature engine and tests"
Cohesion: 0.13
Nodes (20): _age_years(), _assemble_ufc_features(), career_stats(), compute_ufc_target(), infer_five_rounds(), synthetic_round_total(), _fight(), _stats_pair() (+12 more)

### Community 263 - "Mobile pick CTA and NFL import checks"
Cohesion: 0.04
Nodes (35): main(), test_today_et_ignores_the_container_timezone(), _read(), _run(), test_a_stale_card_offers_no_bet(), test_a_stale_card_says_why_and_speaks_the_locked_price(), test_a_stale_pre_game_price_is_no_price_on_the_card(), test_best_handoff_rerank_is_wired() (+27 more)

### Community 266 - "NCAAF in-play history backtest"
Cohesion: 0.12
Nodes (14): out_path(), build_candidates(), _fmt(), load_snapshots(), main(), odds_from_rows(), report(), split_halves() (+6 more)

### Community 267 - "tests/test_ncaaf_qb_features.py"
Cohesion: 0.12
Nodes (24): build_qb_team_features(), load_qb_games(), merge_qb_features(), _feat(), _frame(), _games(), _qb_rows(), _qb_team() (+16 more)

### Community 272 - "Database URL doctor"
Cohesion: 0.13
Nodes (19): _classes(), diagnose(), bad(), _safe(), main(), _fails(), _levels(), test_a_correct_url_reports_no_failures() (+11 more)

### Community 276 - "Prop box score fill"
Cohesion: 0.11
Nodes (25): fill_missing(), _call_fill(), _cooled(), _day(), _default_mlb(), _default_nba(), _default_nfl(), _default_nhl() (+17 more)

### Community 277 - "X publisher and free pick"
Cohesion: 0.10
Nodes (17): _pick(), test_a_pick_with_no_alternative_falls_back_to_draftkings(), test_every_offerable_book_has_a_human_name_on_both_surfaces(), test_the_free_card_names_the_cheaper_book(), test_the_free_card_query_reads_the_columns_it_renders(), test_the_good_to_clause_is_dropped_not_truncated_when_it_will_not_fit(), test_the_tweet_names_the_cheaper_book(), test_the_tweet_never_publishes_a_worse_price_than_draftkings() (+9 more)

### Community 282 - "NBA schedule features"
Cohesion: 0.12
Nodes (10): _counted_schedule(), from_cache(), game_schedule_features(), haversine_miles(), home_bases(), _offsets(), previous_game_load(), team_schedule_features() (+2 more)

### Community 285 - "Health skip budget tests"
Cohesion: 0.12
Nodes (11): test_a_stuck_gate_is_not_reported_as_stale_data(), _res(), test_a_non_skipped_result_is_never_touched(), test_a_stuck_gate_escalates_past_its_budget(), test_an_honest_offseason_skip_stays_skipped_but_shows_its_length(), test_applying_twice_does_not_double_annotate(), test_model_calibration_is_persisted(), test_the_default_budget_is_short_enough_to_surface_a_stuck_gate() (+3 more)

### Community 286 - "Kalshi ladder recording and prop ingestor tests"
Cohesion: 0.18
Nodes (3): test_a_kalshi_outage_cannot_break_the_pass(), test_a_run_is_idempotent_within_its_snapshot(), test_the_recorder_is_scheduled_on_the_pipeline_role()

### Community 287 - "tests/test_model_calibration_check.py"
Cohesion: 0.09
Nodes (12): _calibration_sql(), test_a_flagged_model_is_named_eligible_or_not(), test_a_thin_model_is_still_excluded_rather_than_accused(), test_eligibility_notes_must_not_sink_the_gap_check(), test_eligibility_notes_parse_the_payload_verdicts(), test_it_grades_the_calibrated_probability_not_the_raw_one(), test_it_joins_picks_to_reach_the_calibrated_column(), test_the_check_has_a_skip_budget_that_survives_a_regime_change() (+4 more)

### Community 289 - "tests/test_ncaaf_player_stats_ingestor.py"
Cohesion: 0.18
Nodes (17): parse_player_game_stats(), _cat(), _parse(), _payload(), _team(), test_a_game_missing_from_the_id_map_is_skipped_not_guessed(), test_a_player_gets_one_row_across_every_category(), test_a_player_with_nothing_we_track_is_skipped() (+9 more)

### Community 29 - "NCAAF in-play history pulls"
Cohesion: 0.14
Nodes (19): _blank_row(), budget_for(), calls_in(), _floor5(), _get(), _iso(), main(), parse_shard() (+11 more)

### Community 295 - "Unit stake sizing and formatting"
Cohesion: 0.06
Nodes (20): test_conviction_floors_at_one_not_a_half(), test_conviction_is_flat_for_every_kelly(), test_conviction_is_flat_regardless_of_kelly(), test_favourites_risk_more_until_the_cap_binds(), test_flat_conviction_is_still_price_adjusted(), test_risk_and_win_always_agree_with_the_price(), test_risk_is_capped_at_three_units_and_the_payout_is_recomputed(), test_the_minus_110_example_matt_gave() (+12 more)

### Community 296 - "scripts/nfl_edge_kalshi.py"
Cohesion: 0.17
Nodes (20): align_check(), bh(), bins(), boot(), cell(), coverage(), cp_roi(), fee() (+12 more)

### Community 297 - "Mobile pick category tests"
Cohesion: 0.11
Nodes (13): _block(), _config_scorable_ids(), _meta_ids(), _meta_types(), _read(), test_every_model_id_derives_its_own_declared_category(), test_every_scorable_model_has_a_label_in_the_app(), test_picks_idle_chrome_is_search_and_filters_only() (+5 more)

### Community 299 - "tests/test_context_budget.py"
Cohesion: 0.12
Nodes (14): _expand_braces(), _hook_context(), _read(), _rule_files(), _size(), test_claude_md_stays_small_enough_to_load_every_session(), test_every_doc_referenced_by_the_index_exists(), test_every_rules_file_is_pointed_at_from_claude_md() (+6 more)

### Community 303 - "tests/test_player_h2h_stat_values_migration.py"
Cohesion: 0.10
Nodes (13): _body(), test_each_function_reads_its_own_log_table(), test_it_does_its_ddl_once_and_guards_on_the_property_it_establishes(), test_it_is_one_statement_so_conn_execute_cannot_shred_it(), test_public_is_revoked_before_anon_is_granted(), test_security_invoker_like_the_season_rpcs_it_mirrors(), test_the_fixture_is_two_parallel_arrays_not_a_separator(), test_the_players_latest_team_decides_his_fixture() (+5 more)

### Community 305 - "tests/test_retired_models.py"
Cohesion: 0.06
Nodes (13): test_a_retired_game_model_is_in_no_feature_map(), test_a_retired_model_is_in_no_registry_and_no_threshold_dict(), test_a_retired_prop_has_no_feature_map_and_no_training_label(), test_a_retired_sport_is_not_still_health_checked(), test_paused_nfl_props_still_in_prop_models_and_thresholds(), test_retired_prop_picks_still_settle_on_their_own_stat(), test_ten_nfl_distributional_props_are_paused(), test_the_app_mirrors_the_same_set() (+5 more)

### Community 315 - "NFL live prop feasibility study"
Cohesion: 0.22
Nodes (18): american_b(), bettable(), boot_roi(), brier(), design(), fit_market(), grade(), implied() (+10 more)

### Community 317 - "Latest line state and Citadel migration cluster tests"
Cohesion: 0.05
Nodes (45): can_scratch(), env_dsn(), _free_port(), pg_bin(), scratch_cluster(), as_app(), db(), dsn() (+37 more)

### Community 318 - "tests/test_live_record_start_views.py"
Cohesion: 0.09
Nodes (12): _body(), _code(), test_both_published_views_carry_the_live_date_gate(), test_it_runs_after_the_migration_that_used_to_own_the_daily_view(), test_migration_is_one_statement(), test_migration_is_registered_with_the_worker_runner(), test_neither_view_reads_the_sweep_universe(), test_no_ddl_outside_the_guarded_branches() (+4 more)

### Community 326 - "tests/test_api_call_rollup.py"
Cohesion: 0.09
Nodes (10): test_a_fold_can_never_lower_a_stored_total(), test_a_new_process_does_not_prune_on_its_first_flush(), test_prune_rolls_up_before_it_deletes(), test_the_daily_table_is_created_and_locked_down(), test_the_daily_table_keys_on_day_api_and_source(), test_the_rollup_groups_by_eastern_day_not_utc(), test_the_rollup_reads_only_yesterday_and_today(), test_the_rollup_survives_a_failure_without_blocking_the_prune() (+2 more)

### Community 328 - "UFC CSV loader"
Cohesion: 0.18
Nodes (13): backfill_ufc_csv(), build_events(), build_fighter_index(), _scheduled_rounds(), _split_bout(), _id_from_url(), _fixture(), test_build_events_draw_and_nc() (+5 more)

### Community 329 - "nfl/models/opener_spread.py"
Cohesion: 0.14
Nodes (11): age_tag(), american_to_prob(), _bettable_books(), clean_board(), edge_tier(), evaluate_board(), held_minutes(), model_prob_for_dev() (+3 more)

### Community 331 - "NHL prop backtest and combined cap"
Cohesion: 0.12
Nodes (17): card(), claimed_vs_realised(), day_interval(), line(), namesakes(), prices(), report(), show() (+9 more)

### Community 332 - "tests/test_live_slate_midnight.py"
Cohesion: 0.10
Nodes (10): _at(), test_both_live_loops_share_one_definition_of_the_slate(), test_by_daytime_yesterday_is_dropped(), test_just_after_midnight_still_asks_about_yesterday(), test_just_before_midnight_asks_about_today_only(), test_the_apps_live_hook_resolves_the_window_per_fetch(), test_the_apps_live_reads_take_a_LIST_of_dates(), test_the_ncaaf_live_loop_got_the_same_fix() (+2 more)

### Community 333 - "tests/test_nfl_wind_fire_window.py"
Cohesion: 0.07
Nodes (18): _retractable_slate(), _slate(), test_a_blank_roof_at_a_NON_retractable_venue_is_unaffected(), test_a_closed_roof_is_still_indoor(), test_a_retractable_venue_with_an_unknown_roof_does_not_fire(), test_a_waiting_game_is_not_reported_as_a_collapsed_premise(), test_a_waiting_row_keeps_its_line_price_and_edge(), test_every_blank_roof_row_is_a_retractable_venue() (+10 more)

### Community 334 - "College football data parsers"
Cohesion: 0.12
Nodes (15): _int(), _num(), parse_advanced_stats(), parse_ratings(), parse_returning(), parse_season_stats(), parse_talent(), parse_venues() (+7 more)

### Community 335 - "tests/test_public_betting_ingestor.py"
Cohesion: 0.17
Nodes (17): parse_public_betting(), _pct(), _select_book(), _make_game(), test_parse_emits_six_rows(), test_parse_game_id_and_sides(), test_parse_marks_source_and_snapshot(), test_parse_missing_teams_returns_empty() (+9 more)

### Community 336 - "Mobile TypeScript test runners"
Cohesion: 0.12
Nodes (13): _node_strips_types(), _read(), _run(), test_audited_targets(), test_betslip_bar_inset_wiring(), test_h9_rows_reach_44pt_inside_their_bounds(), test_pick_card_label_is_complete(), test_reach_frame_and_add_bet_hint() (+5 more)

### Community 339 - "tests/test_service_role_split.py"
Cohesion: 0.15
Nodes (11): _all_job_ids(), _sched(), test_an_unknown_role_runs_everything(), test_every_add_job_call_passes_an_id(), test_every_job_is_owned_by_exactly_one_role(), test_the_always_on_jobs_run_on_every_role(), test_the_default_preserves_the_single_container(), test_the_nfl_worker_stays_with_the_volume() (+3 more)

### Community 343 - "tests/test_http_timeout_floor.py"
Cohesion: 0.11
Nodes (11): install_timeout_floor(), _call(), clean_requests(), test_a_call_with_no_timeout_gets_one(), test_an_explicit_timeout_is_never_overridden(), test_installing_twice_is_a_no_op(), test_the_deadline_is_env_overridable(), test_the_deadline_survives_telemetry_being_turned_off() (+3 more)

### Community 345 - "UFC stats ingestor and page cache"
Cohesion: 0.10
Nodes (12): _cached_etag(), _etag_cache_path(), _clean_env(), test_a_mounted_volume_is_preferred_over_tmp(), test_a_round_trip_actually_persists(), test_a_volume_path_that_does_not_exist_falls_back(), test_an_empty_etag_is_never_stored(), test_an_explicit_override_wins() (+4 more)

### Community 346 - "scripts/nfl_edge_cache.py"
Cohesion: 0.22
Nodes (14): _conn(), copy_main_local(), _df(), _games_2026(), log(), main(), nflverse_misc(), nflverse_pbp() (+6 more)

### Community 351 - "tests/test_nfl_injury_ingest.py"
Cohesion: 0.11
Nodes (9): _fetch_nfl_espn_team_ids_core(), _nfl_espn_team_to_abbrev(), _fake_fetch(), test_core_nfl_listing_failure_returns_empty(), test_core_nfl_team_ids_resolve_lar_and_wsh_to_ours(), test_injury_fetch_raises_the_page_limit(), test_nfl_active_rows_are_dropped_and_out_keeps_espn_date(), test_nfl_name_join_uses_our_abbrevs_not_espns() (+1 more)

### Community 352 - "NHL prop odds alternate line tests"
Cohesion: 0.07
Nodes (22): due(), _book(), test_a_200_on_both_calls_merges_the_alternate_lines(), fake_fetch(), test_a_game_first_priced_inside_the_final_window_gets_nothing_more(), test_a_game_first_priced_inside_the_window_gets_one_decision_snapshot(), test_a_game_with_nothing_stored_is_owed_its_open(), test_a_moved_featured_line_keeps_the_old_number_under_the_alternate_key() (+14 more)

### Community 355 - "Live honest cut and NHL regulation probability"
Cohesion: 0.13
Nodes (13): bets_split(), _fmt(), _grid(), main(), _print_grid(), run_mlb(), run_ncaaf(), _summ() (+5 more)

### Community 357 - "NHL derivative totals backtest"
Cohesion: 0.20
Nodes (14): select_bets(), blind_rows(), _csv(), even_money(), game_sides(), _line(), load(), main() (+6 more)

### Community 359 - "NCAAF ESPN live feed parser"
Cohesion: 0.17
Nodes (16): check_feed_assumptions(), _competitors(), _count_plays(), _dig(), extract_live_events(), extract_summary_state(), _int(), _num() (+8 more)

### Community 360 - "Sub-10-second live path tests"
Cohesion: 0.09
Nodes (11): test_a_quote_already_seen_does_not_count_as_a_move(), test_a_scoring_failure_never_kills_the_feed(), test_poll_once_reports_which_games_moved(), test_scoring_is_opt_in(), test_scoring_runs_in_the_same_tick_as_the_write(), test_the_budget_is_written_down_where_it_can_be_checked(), test_the_expected_consequence_is_stated(), test_the_loop_sleeps_the_REMAINDER_of_the_interval() (+3 more)

### Community 361 - "tests/test_config.py"
Cohesion: 0.08
Nodes (8): test_an_own_floor_does_not_take_a_model_off_the_calibration_map(), test_every_model_carries_its_own_thresholds(), test_every_own_floor_names_a_live_model(), test_models_on_own_probability_is_not_derived_from_the_floor_dict(), test_no_own_floor_tightens_a_model_past_the_global_floor(), test_only_a_market_priced_model_carries_a_negative_floor(), test_own_ev_floor_and_model_min_ev_stay_disjoint(), test_the_models_the_global_floor_silently_removed_can_bet_again()

### Community 366 - "Kalshi game market recorder"
Cohesion: 0.07
Nodes (17): event_code(), event_date(), kalshi_school(), _num(), probe(), record_game_markets(), resolve_events(), rows_for() (+9 more)

### Community 367 - "Outcome edge scan"
Cohesion: 0.19
Nodes (12): _cell(), ecdf_prob_positive(), implied(), load_ml_prices(), main(), payout(), predict_all(), _print_cells() (+4 more)

### Community 368 - "tests/test_mlb_pbp_ingestor.py"
Cohesion: 0.16
Nodes (15): _bases_after_from_matchup(), parse_game_plays(), parse_play(), _split_event_type(), test_bases_empty_matchup(), test_bases_with_runners(), test_parse_game_plays_empty_feed(), test_parse_game_plays_walks_full_inning() (+7 more)

### Community 369 - "UFC fighter name resolution"
Cohesion: 0.16
Nodes (11): resolve_slug(), _slug_tokens(), test_a_generational_suffix_resolves_either_way(), test_a_near_miss_is_not_a_match(), test_a_reversed_name_order_resolves(), test_a_shared_surname_alone_is_not_a_match(), test_an_ambiguous_token_set_resolves_to_nothing(), test_an_empty_or_tokenless_name_is_safe() (+3 more)

### Community 37 - "EV floor replay and honest cut"
Cohesion: 0.09
Nodes (28): load_calibrations(), analyse(), _apply_price_floor(), _era(), fetch(), grade(), _guard_mlb(), main() (+20 more)

### Community 370 - "UFC stats ingestor and fighter pages"
Cohesion: 0.08
Nodes (23): load_fighter_profiles_from_csv(), refresh_fighter_profiles_from_csv(), backfill_ufc_stats(), _build_ufc_game_id(), _fetch_event(), _fetch_event_list(), _fetch_fight(), _fetch_fighter() (+15 more)

### Community 371 - "tests/test_team_stats_asof_invariants.py"
Cohesion: 0.10
Nodes (11): impossible_games_played(), _played_actual(), test_a_missing_count_is_reported_not_silently_passed(), test_an_honest_row_passes(), test_claiming_fewer_games_than_played_is_fine(), test_feb_gp_climbing_vs_zero_regular_season_still_fails(), test_one_game_date_boundary_mismatch_is_tolerated(), test_season_final_in_april_is_still_caught() (+3 more)

### Community 373 - "Anon grants and lock-down tests"
Cohesion: 0.03
Nodes (42): all_readable(), closed_tables(), lock_down(), lock_down_sql(), write_verbs_for(), _function_plan(), _function_signature(), main() (+34 more)

### Community 375 - "Refresh pass step ordering tests"
Cohesion: 0.11
Nodes (11): _order(), test_no_sequential_step_runs_while_a_parallel_group_is_open(), test_opening_signals_follows_every_scorer(), test_parlay_follows_opening_signals(), test_scoring_follows_every_ingest(), test_settle_follows_every_results_ingest(), test_sync_thresholds_follows_migrations_and_precedes_scoring(), test_the_nba_prop_card_reads_the_fetch_it_follows() (+3 more)

### Community 376 - "NFL live pick writer: price and lock scope"
Cohesion: 0.10
Nodes (9): _executor_min_price(), _probe_config(), test_the_ceiling_is_a_refusal_not_a_filter(), test_the_insert_tolerates_the_one_row_per_pick_index(), test_the_lane_can_actually_settle(), test_the_lane_refuses_a_quote_past_the_ceiling(), test_the_lock_is_scoped_by_player_not_just_by_game(), test_the_retired_model_carries_no_threshold_row() (+1 more)

### Community 383 - "NFL in-play line churn"
Cohesion: 0.19
Nodes (13): churn_table(), main(), verdict(), _snaps(), test_a_line_moving_every_interval_reads_as_under_sampled(), test_a_missing_key_column_fails_loudly_rather_than_grouping_coarser(), test_a_single_snapshot_contributes_no_interval(), test_a_still_line_reads_as_still() (+5 more)

### Community 384 - "tests/test_mobile_threshold_parity.py"
Cohesion: 0.16
Nodes (12): _block(), _canonical(), _mirror(), _mirror_paused(), _src(), test_every_cut_matches_config(), test_every_scorable_model_is_in_the_app_mirror(), test_the_app_mirror_holds_no_model_config_cannot_score() (+4 more)

### Community 385 - "NFL live prop assessment and book screen"
Cohesion: 0.08
Nodes (23): devig_series(), main(), _one(), _prob(), rebuild(), _two_sided(), american_b(), boot_ci() (+15 more)

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

### Community 394 - "Mobile tracked performance check"
Cohesion: 0.10
Nodes (18): dup, empty, half, l50, loss, noAction, open1, open2 (+10 more)

### Community 396 - "NFL Kalshi fetch and price floor grid"
Cohesion: 0.21
Nodes (6): candles(), get(), map_games(), paged(), parse_event(), probe()

### Community 398 - "MLB prop market tests"
Cohesion: 0.09
Nodes (19): find_bets(), _q(), test_a_different_line_is_never_compared(), test_a_market_under_the_coverage_floor_is_excluded(), test_a_prop_the_sharp_book_did_not_price_is_counted_not_traded(), test_agreement_produces_no_bet(), test_an_equal_line_with_a_real_disagreement_is_a_bet(), test_devig_removes_the_hold_symmetrically() (+11 more)

### Community 399 - "NFL live leader model tests"
Cohesion: 0.10
Nodes (19): fit_wp(), logit_irls(), wp_design(), wp_lookup(), art(), _d(), _raw(), test_600_seconds_and_both_lead_ends_are_inside() (+11 more)

### Community 40 - "NFL wind edge studies"
Cohesion: 0.05
Nodes (69): coerce_numeric_features(), feature_matrix(), add_model_mu(), load(), main(), load_games(), main(), pivot_spreads() (+61 more)

### Community 400 - "Mobile paused catalog tests"
Cohesion: 0.16
Nodes (11): _block(), _read(), test_paused_picks_reach_the_all_board_only_and_labelled(), test_stats_add_pick_refuses_a_paused_model(), test_the_behavioural_checks_pass(), test_the_bet_type_picker_filters_paused_models(), test_the_custom_model_picker_is_three_bet_types(), test_the_models_list_filters_paused_models() (+3 more)

### Community 401 - "NFL live prop rule studies"
Cohesion: 0.19
Nodes (11): american_b(), boot_roi(), first_per_player(), grade(), load(), main(), report(), main() (+3 more)

### Community 403 - "NFL prop shape simulation"
Cohesion: 0.20
Nodes (12): anchor_scale(), calibration(), grade(), latest(), load_odds(), main(), placebo_sf(), player_gamma() (+4 more)

### Community 404 - "tests/test_promote_calibration_job.py"
Cohesion: 0.11
Nodes (3): test_a_refused_model_rolls_back_and_raises(), test_a_successful_promote_commits(), _job_promote_calibration()

### Community 406 - "tests/test_cfbd_snapshot_leakage.py"
Cohesion: 0.16
Nodes (9): _completed_before(), _ohio_state_2024(), test_boundary_is_strict(), test_datetime_like_values_are_handled(), test_empty_input(), test_end_of_regular_season_snapshot_excludes_playoffs(), test_missing_or_malformed_dates_are_dropped_not_admitted(), test_postseason_excluded_from_early_season_snapshot() (+1 more)

### Community 411 - "Mobile player stat groups test"
Cohesion: 0.15
Nodes (10): _set_literal(), _src(), test_a_group_is_filled_only_by_a_real_number(), test_a_tab_opens_on_the_stat_the_player_fills_most(), test_defensive_positions_get_only_the_defense_group(), test_every_logged_position_is_classified(), test_non_defensive_positions_get_no_defense_group(), test_offensive_positions_are_not_defensive() (+2 more)

### Community 412 - "Mobile bankroll card field flow"
Cohesion: 0.20
Nodes (19): fieldFlow(), inv(), bankrollDraft(), bankrollFieldText(), canonical(), checkBankroll(), commitBankrollText(), editBankrollInput() (+11 more)

### Community 413 - "tests/test_nfl_prop_thresholds.py"
Cohesion: 0.11
Nodes (8): test_live_webhook_map_reads_the_per_sport_env_vars(), cfg(), test_no_nfl_prop_market_is_back_on_the_uniform_placeholder(), test_one_bad_date_does_not_cost_the_others(), test_the_prop_window_has_exactly_one_declaration(), test_the_scorer_step_covers_the_whole_window_not_one_date(), fake(), test_the_three_threshold_dicts_agree_for_every_nfl_prop_market()

### Community 414 - "tests/test_nhl_research_job.py"
Cohesion: 0.15
Nodes (11): test_a_dump_argument_is_refused(), test_a_model_must_be_a_real_spec(), test_a_season_must_be_a_priced_one(), test_an_unknown_script_is_refused(), test_an_unknown_top_level_key_is_refused(), test_every_runnable_module_has_a_main(), test_every_runnable_module_writes_no_database_row(), test_the_artifact_grade_names_the_rule_production_runs() (+3 more)

### Community 415 - "tests/test_settlement_timing.py"
Cohesion: 0.14
Nodes (9): test_capture_clv_requires_the_game_to_have_started(), test_future_kickoffs_are_not_treated_as_started(), test_game_log_skips_per_game_not_per_date(), test_mirror_unchanged_is_conservative_when_it_cannot_tell(), test_started_games_are_recognised_in_every_stored_format(), test_ufc_poll_uses_the_etag_gate_and_the_daily_run_does_not(), test_unparseable_timestamps_yield_none_rather_than_a_guess(), test_z_and_offset_forms_are_the_same_instant_but_not_the_same_string() (+1 more)

### Community 416 - "NFL live pick writer"
Cohesion: 0.13
Nodes (7): _is_market_opinion(), _lane_is_locked(), _norm_player(), resolve_game(), resolve_game_id(), test_normalised_player_key_is_the_join_the_prop_system_uses(), test_the_lane_lock_shares_the_scorers_meaning_of_locked()

### Community 418 - "First-signal repair"
Cohesion: 0.11
Nodes (8): test_comparison_ignores_pick_id_and_label(), _first_bets(), _lane_voided(), main(), _restore_as_paused(), _same_bet(), _sibling_rows(), _standing()

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

### Community 427 - "Intraday freshness tests"
Cohesion: 0.10
Nodes (13): run_player_news_ingestor(), _is_fresh(), _minutes_since(), step_player_news(), step_weather(), _age(), test_an_unknown_age_refetches_rather_than_skipping(), test_fresh_data_is_skipped() (+5 more)

### Community 428 - "Kalshi prop ladder ingestor"
Cohesion: 0.10
Nodes (11): _event_date(), _player(), record_ladders(), test_the_recorder_keeps_raw_prices_not_a_filtered_ladder(), test_a_ticker_with_no_event_code_returns_none_not_a_wrong_date(), test_a_title_without_a_player_returns_none(), test_an_impossible_date_is_rejected(), test_only_per_game_player_series_are_mapped() (+3 more)

### Community 430 - "Module entrypoint guard tests"
Cohesion: 0.15
Nodes (7): _is_main_guard(), _modules_with_guard(), test_at_least_one_entrypoint_is_scanned(), test_nothing_is_defined_after_the_main_guard(), test_the_report_script_exists_and_parses(), test_the_backfill_queues_the_dates_of_those_picks(), test_the_nfl_label_map_is_the_inverse_of_the_nfl_publisher()

### Community 431 - "tests/test_pick_lock_is_on_picks.py"
Cohesion: 0.16
Nodes (9): _between(), _sql(), test_a_bet_is_still_never_re_scored(), test_only_a_bet_locks_a_pair(), test_the_cleanup_covers_the_whole_look_ahead_window(), test_the_cleanup_never_touches_a_started_game_or_a_live_row(), test_the_lock_is_no_longer_ncaaf_specific(), test_the_prop_and_live_locks_are_unchanged() (+1 more)

### Community 433 - "NFL 2026 rule track tests"
Cohesion: 0.16
Nodes (13): opener_verdict(), _row(), _src(), test_config_comments_state_the_policy(), test_live_cuts_did_not_move(), test_max_fire_lead_stays_four_in_the_live_model(), test_opener_does_not_retire_mid_season_even_if_currently_up(), test_opener_retire_candidate_only_when_the_season_finished_flat_or_worse() (+5 more)

### Community 438 - "Public betting features and reverse line moves"
Cohesion: 0.15
Nodes (11): build_public_features(), favorite_side(), _pct_pair(), _rlm(), test_classic_rlm_ninety_tickets_twenty_money_leans_the_dog(), test_decimal_and_empty_public_pcts_coerce_numeric(), test_favorite_framing_flips_when_home_is_the_dog(), test_flat_split_is_zero_rlm_not_none() (+3 more)

### Community 439 - "tests/test_team_stats_asof_invariants.py"
Cohesion: 0.15
Nodes (10): build_rows(), _game(), test_a_row_never_includes_its_own_date(), test_counts_accumulate_across_dates(), test_every_emitted_column_exists_in_the_real_table(), test_every_sport_uses_its_own_scoring_noun(), test_home_and_away_splits_use_only_the_relevant_games(), test_last_n_is_a_rolling_window_not_a_season_constant() (+2 more)

### Community 44 - "scripts: build_nfl_live_leader_artifact + model"
Cohesion: 0.09
Nodes (26): wp_design(), wp_lookup(), attach_games(), build_artifact(), check_possession(), _dk_pregame_spread(), _download(), _first_bets() (+18 more)

### Community 445 - "Published record reconciliation tests"
Cohesion: 0.16
Nodes (8): test_a_pick_before_the_live_date_is_caught_in_either_view(), test_a_sport_missing_from_the_daily_view_is_caught(), test_an_empty_record_is_not_a_problem(), test_cent_level_agreement_is_required(), test_same_picks_but_different_money_is_caught(), test_the_fixed_production_numbers_reconcile(), test_the_real_production_drift_is_caught(), _published_record_problems()

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

### Community 456 - "Mobile bankroll tests"
Cohesion: 0.19
Nodes (14): _read(), test_copy_is_word_for_word(), test_display_only_nothing_sized(), test_error_text_uses_the_text_safe_red(), test_explainer_no_longer_denies_a_bankroll(), test_exposure_card_hook_and_banner_stay_removed(), test_keyboard_never_covers_the_field(), test_locale_separators_decide_the_decimal() (+6 more)

### Community 458 - "Live monitor dashboard cache and docs"
Cohesion: 0.13
Nodes (10): age(), cached(), clear(), test_cache_raises_when_it_has_nothing_to_fall_back_on(), test_cache_reports_age(), test_cache_serves_stale_rather_than_failing(), boom(), test_cache_serves_within_ttl_and_recomputes_after() (+2 more)

### Community 46 - "Worker job queue"
Cohesion: 0.02
Nodes (47): derive_first_pitch(), test_runner_captures_stdout_from_the_script_main(), test_the_discord_publish_job_calls_the_ordinary_producer(), test_the_discord_publish_job_takes_an_optional_date(), test_the_raised_timeout_is_restored_after_the_job(), test_the_restore_puts_back_a_pre_existing_value(), test_missing_artifact_path_refuses_to_sweep_live(), test_retrain_then_sweep_passes_the_new_path() (+39 more)

### Community 462 - "Calibration and pipeline watchers"
Cohesion: 0.14
Nodes (8): test_every_not_ok_health_check_is_reported(), test_the_silence_finding_says_how_regular_the_kind_was(), _enabled(), findings_from_checks(), _rows(), _silent_kinds(), _step_regressions(), post_and_ledger()

### Community 463 - "Monitoring server tests"
Cohesion: 0.07
Nodes (28): _drain(), _enqueue(), _flush_on_exit(), install(), instrumented(), _now(), _patch_curl_cffi(), instrumented() (+20 more)

### Community 465 - "nfl/scripts/backtest_opener.py"
Cohesion: 0.24
Nodes (9): boot(), by_season(), exp_win(), load(), main(), price(), report(), residuals() (+1 more)

### Community 466 - "Injury ingestor and ESPN NHL probables"
Cohesion: 0.04
Nodes (30): _default_fetch(), fetch_espn_nhl_probables(), _https(), parse_probable(), _team_abbrev(), _compute_return_ramp(), _espn_team_ids(), fetch_espn_injuries() (+22 more)

### Community 467 - "MLB retrain freeze tests"
Cohesion: 0.12
Nodes (8): test_import_time_flag_follows_marker_file(), test_marker_or_env_lifts_the_freeze(), test_mlb_prop_market_sweep_is_documented_exempt(), test_mlb_retrain_refused_while_incomplete(), test_mlb_threshold_sweeps_call_the_guard(), test_non_mlb_sports_are_not_gated(), test_repo_marker_file_is_present(), test_trainer_calls_the_guard()

### Community 468 - "tests/test_latest_odds_views.py"
Cohesion: 0.25
Nodes (13): _app_columns(), _function(), test_every_log_table_has_its_insert_trigger_and_the_odds_tables_an_update_trigger(), test_every_view_reads_its_state_table_and_never_the_log(), test_no_pending_view_migration_re_creates_these_views_over_the_log(), test_the_dk_view_returns_the_apps_columns_in_order(), test_the_exclusions_survived_the_move(), test_the_game_view_returns_the_apps_columns_in_order() (+5 more)

### Community 472 - "NBA schedule ingestor and tests"
Cohesion: 0.16
Nodes (15): fetch_season(), main(), ot_periods(), run(), schedule_rows(), season_str(), _tv(), write() (+7 more)

### Community 473 - "tests/test_nfl_prop_settle_name_fallback.py"
Cohesion: 0.27
Nodes (10): _never(), _row(), test_a_first_name_the_stat_log_spells_differently_still_matches(), test_a_scratched_player_is_not_graded_on_a_teammate_with_his_initial(), test_a_spelling_the_log_already_knows_is_a_scratch_not_a_spelling(), test_another_game_and_another_initial_never_match(), test_first_name_rule(), test_two_candidates_is_a_miss_not_a_guess() (+2 more)

### Community 474 - "NFL recap waits for box scores tests"
Cohesion: 0.17
Nodes (8): _daily(), _job_body(), test_a_malformed_date_is_refused_before_anything_runs(), test_nfl_box_scores_are_ingested_before_settle(), test_nfl_finals_still_precede_the_box_scores(), test_the_job_does_not_read_rowcount_off_the_cursor(), test_the_job_only_clears_its_own_two_ledger_kinds(), test_the_job_posts_both_surfaces_through_the_ordinary_paths()

### Community 475 - "tests/test_market_handicap.py"
Cohesion: 0.18
Nodes (10): row_is_pregame(), select_latest_pregame_splits(), _split(), test_as_of_ceiling_drops_a_snapshot_after_the_tick(), test_newer_pregame_snapshot_wins_older_is_not_used(), test_offset_aware_public_snapshot_after_utc_commence_is_dropped(), test_offset_aware_public_snapshot_before_utc_commence_is_kept(), test_post_start_public_snapshot_is_dropped() (+2 more)

### Community 476 - "tests/test_transaction_pooler.py"
Cohesion: 0.19
Nodes (8): _transaction_endpoint(), test_a_direct_connection_is_left_alone(), test_a_local_postgres_is_left_alone(), test_a_supabase_session_url_becomes_the_transaction_url(), test_it_is_idempotent(), test_only_the_port_changes(), test_the_escape_hatch_works(), test_the_job_queue_still_gets_session_mode()

### Community 477 - "NHL prop card and blocked shots"
Cohesion: 0.21
Nodes (8): p_over(), bets(), card(), line(), main(), prices(), show(), decide()

### Community 480 - "Team stats as-of invariant tests"
Cohesion: 0.14
Nodes (9): seasons_with_too_few_snapshots(), test_a_real_series_passes(), test_a_single_snapshot_season_is_flagged(), test_a_two_snapshot_season_is_flagged(), test_mlb_twin_alias_map_matches_sbr_canon(), test_ncaaf_shaped_weekly_snapshots_pass(), test_snapshot_grace_is_opening_night_not_a_finished_season(), test_the_guard_is_wired_so_protected_seasons_are_REMOVED() (+1 more)

### Community 484 - "NFL opener cut sweep and bettable books"
Cohesion: 0.23
Nodes (6): bettable_books(), boot_ci(), candidate_rows(), _load_backtest(), main(), select()

### Community 487 - "supabase/functions/sharpsports/index.ts"
Cohesion: 0.30
Nodes (13): americanFromBetSlip(), asArray(), createContext(), isSettled(), json(), pick(), pullAndUpsert(), readBets() (+5 more)

### Community 490 - "NCAAF steam lag study"
Cohesion: 0.27
Nodes (9): attach_scores(), build_events(), fmt(), grade(), lines_at_pulls(), load(), main(), summarise() (+1 more)

### Community 491 - "MLB game market and public fade cards"
Cohesion: 0.12
Nodes (15): edge_floor(), load_public_over_splits(), max_per_slate(), publish_enabled(), rank_kind(), ticket_threshold(), under_odds_band(), main() (+7 more)

### Community 495 - "tests/test_worker_deps.py"
Cohesion: 0.16
Nodes (6): _requirements(), test_dashboard_packages_are_not_on_the_worker(), test_nothing_in_the_repo_actually_wants_a_gpu(), test_only_the_dashboard_imports_them(), test_the_dashboard_file_is_additive_not_a_replacement(), test_the_worker_asks_for_the_cpu_build_of_xgboost()

### Community 497 - "NCAAF research scripts and steam lag"
Cohesion: 0.23
Nodes (6): build_spots(), evaluate(), load_games(), main(), scoring_by_wind(), wilson()

### Community 499 - "House juice price floor and retrain sweep job"
Cohesion: 0.05
Nodes (22): min_odds_for(), _blocked_by_min_odds(), _fmt(), main(), render(), _strip_date(), _side_rows(), test_a_pick_with_no_price_is_never_blocked_by_the_floor() (+14 more)

### Community 50 - "scheduler.py"
Cohesion: 0.06
Nodes (48): abort_orphaned_refresh_runs(), build_scheduler(), _add_job(), _with_heartbeat(), _wrapped(), catch_up_daily_pipeline(), catch_up_refresh_pass(), catch_up_weekly_jobs() (+40 more)

### Community 501 - "NFL prop lean concentration study"
Cohesion: 0.25
Nodes (7): add_context(), boot(), main(), profit(), report(), tercile_split(), under_profit()

### Community 502 - "NFL stale card file tests"
Cohesion: 0.15
Nodes (9): card_path(), clear_card(), _load_script(), nfl_path(), test_a_dry_run_leaves_the_card_alone(), test_a_priced_wind_run_with_no_bets_removes_the_earlier_card(), test_clear_card_removes_todays_file_and_only_that(), test_the_path_cleared_is_the_path_the_publisher_reads() (+1 more)

### Community 503 - "NHL totals lab"
Cohesion: 0.26
Nodes (8): grade(), imp(), interval(), load(), main(), row(), show(), wpu()

### Community 504 - "Pipeline watch: posting ledger"
Cohesion: 0.18
Nodes (6): test_a_confirmed_post_is_ledgered_so_the_run_can_be_verified(), test_an_occasional_kind_is_not_flagged_for_being_quiet(), test_an_unconfirmed_post_is_never_ledgered(), test_the_ledger_is_one_row_per_day_so_a_retry_cannot_double_count(), test_the_watch_belongs_to_the_pipeline_service(), _wire()

### Community 505 - "tests/test_mobile_stat_labels_match_the_server.py"
Cohesion: 0.21
Nodes (6): _meta_entries(), _server_stat_labels(), test_both_rushing_models_call_the_stat_the_same_thing(), test_the_live_model_names_the_market_it_actually_trades(), test_the_parser_actually_found_the_models(), test_the_unreconciled_models_are_named()

### Community 506 - "tests/test_ncaaf_fcs_visitor_names_migration.py"
Cohesion: 0.15
Nodes (5): _rows(), test_each_write_guards_on_its_own_property(), test_every_real_visitor_extends_the_wrong_one(), test_migration_is_one_statement(), test_the_nine_rows_and_their_finals_are_the_measured_ones()

### Community 507 - "tests/test_nfl_prop_unstarted_clear.py"
Cohesion: 0.25
Nodes (8): _apply(), _assert_split(), _between(), _first_sql(), _per_game_sql(), _sweep_sql(), test_per_game_clear_keeps_nfl_prop_rows_on_a_game_the_loop_reaches(), test_sweep_keeps_unstarted_nfl_prop_nones_and_still_clears_game_nones()

### Community 508 - "NBA, NCAAF and NFL research labs"
Cohesion: 0.03
Nodes (89): _bootstrap_roi_ci(), _summarise(), american_to_decimal(), cover_probs(), ev_per_unit(), fit_margin_pmf(), kelly_fraction(), margin_pmf_for() (+81 more)

### Community 51 - "NFL live moneyline and total pricing tests"
Cohesion: 0.07
Nodes (36): _model_price(), gaussian_copula_joint(), american_to_prob(), anchor_to_market(), devig_power(), margin_pmf(), _over_under(), price_moneyline() (+28 more)

### Community 510 - "Trainer no-register tests"
Cohesion: 0.12
Nodes (9): not_registering(), registering(), test_a_normal_run_DOES_register(), test_baseline_artifacts_are_not_committable(), test_baseline_runs_write_somewhere_else(), test_default_is_to_register(), test_no_register_opens_no_database_connection(), _explode() (+1 more)

### Community 512 - "tests/test_savant_freshness.py"
Cohesion: 0.20
Nodes (3): test_savant_has_a_schedule(), test_the_savant_job_belongs_to_the_pipeline_service(), test_the_stamp_defaults_rather_than_being_required_at_call_sites()

### Community 513 - "tests/test_scorer_nfl_prop_like_escape.py"
Cohesion: 0.23
Nodes (9): _between(), _broken_per_game_sql(), _first_sql(), _per_game_sql(), _sweep_sql(), test_escape_tripwire_is_on_the_pr_ci_subset(), test_live_per_game_clear_interpolates_with_one_game_id(), test_live_sweep_clear_interpolates_with_date_horizon_now() (+1 more)

### Community 514 - "NFL live leader config tests"
Cohesion: 0.11
Nodes (7): honest_probability(), test_a_loop_that_dies_fails_its_job(), test_it_decides_on_its_own_probability(), test_the_action_threshold_key_is_on_one_line(), test_the_loop_refuses_a_price_shorter_than_the_floor(), test_the_mlb_live_scorer_skips_it(), test_the_price_floor_is_minus_140()

### Community 516 - "Signal publish-on-write ordering"
Cohesion: 0.18
Nodes (7): _surfaces(), _make(), test_a_broken_webhook_does_not_suppress_the_push(), test_a_failed_capture_still_delivers(), test_capture_runs_before_either_notifier(), test_publish_never_raises(), publish_new_signals()

### Community 522 - "CLV no-vig capture tests"
Cohesion: 0.20
Nodes (8): _fn(), test_a_missing_bet_book_close_is_not_filled_from_another_book(), test_backfill_revisits_anything_that_is_not_standard_v2(), test_capture_grades_raw_same_book_and_a_separate_pinnacle_edge(), test_capture_stamps_method_and_close_book(), test_game_close_never_falls_back_past_first_pitch(), test_pinnacle_is_a_second_lookup_not_the_headline_close(), test_prop_close_stays_bounded_at_first_pitch()

### Community 524 - "NBA play-by-play aliases and derivation inputs"
Cohesion: 0.15
Nodes (7): alias_play_ids(), derive_game(), roster_from_plays(), sides_inferred(), _with_aliases(), test_a_player_logged_under_a_second_id_is_read_as_his_box_id(), test_players_missing_from_the_box_get_the_side_of_their_own_plays()

### Community 525 - "Paused model assessment tests"
Cohesion: 0.11
Nodes (12): assess(), _half(), fetch(), grade(), sweep(), _units(), _rows(), test_a_cell_below_the_floor_is_not_a_result() (+4 more)

### Community 527 - "MLB backfill resilience tests"
Cohesion: 0.12
Nodes (6): test_a_failed_date_does_not_end_the_run_and_is_left_unmarked(), test_a_transient_network_error_is_retried(), test_an_http_error_is_NOT_retried(), test_it_gives_up_rather_than_looping_forever(), test_skip_existing_is_on_by_default(), test_the_resume_marker_distinguishes_historical_from_live_rows()

### Community 529 - "tests/test_clear_unauthorized_auto_pauses_migration.py"
Cohesion: 0.19
Nodes (6): _stmts(), test_clearing_auto_pauses_did_not_park_batter_runs(), test_it_clears_the_whole_auto_pause_table(), test_it_does_not_touch_picks_thresholds_or_the_review_ledger(), test_it_no_ops_when_the_table_is_missing_or_already_empty(), test_migration_is_one_statement()

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

### Community 542 - "ncaaf_live/tests/test_cfbd_yardline.py"
Cohesion: 0.21
Nodes (6): _abbrev_fits(), _parse_yardline(), _cfbd_game(), test_cfbd_state_carries_the_yardline_and_the_raw_situation(), test_cfbd_yardline_from_every_stored_situation(), test_cfbd_yardline_refuses_rather_than_guesses()

### Community 545 - "Discord results recap and backfill"
Cohesion: 0.24
Nodes (7): build_parser(), main(), post_backfill(), test_a_day_that_is_not_over_is_refused(), test_apply_calls_both_notifiers_for_that_date(), test_dry_run_is_the_default_and_posts_nothing(), test_main_dry_run_prints_and_returns()

### Community 546 - "tests/test_claude_rules_split.py"
Cohesion: 0.18
Nodes (4): test_claude_md_still_points_at_the_rules_directory(), test_every_rule_file_actually_carries_rules(), test_every_rule_file_is_path_scoped(), test_no_rule_was_lost_when_the_split_happened()

### Community 547 - "tests/test_db_setup.py"
Cohesion: 0.23
Nodes (6): _get_columns(), test_games_table_columns(), test_injuries_table_columns(), test_odds_table_columns(), test_picks_table_columns(), test_schema_is_idempotent()

### Community 548 - "tests/test_dedupe_opening_signals.py"
Cohesion: 0.10
Nodes (9): test_a_graded_row_is_never_deleted(), test_a_row_with_computed_clv_is_never_deleted(), test_every_field_that_defines_the_bet_must_agree(), test_it_is_dry_run_by_default(), test_the_delete_selects_through_the_same_gates(), test_the_pair_must_be_an_old_shape_new_shape_pair(), test_the_report_and_the_delete_share_one_definition(), test_the_row_kept_is_the_one_locked_earlier() (+1 more)

### Community 549 - "Feature matrices across sports"
Cohesion: 0.28
Nodes (7): _fit(), main(), _report(), run(), summarise(), walk_forward(), wilson()

### Community 550 - "tests/test_every_named_book_is_fetched.py"
Cohesion: 0.18
Nodes (5): _param_books(), test_a_sharp_reference_is_never_also_a_soft_book(), test_every_bettable_book_can_be_named_to_a_human(), test_every_named_book_is_in_the_pull_that_serves_it(), test_the_nfl_backfill_defaults_to_the_live_pull()

### Community 551 - "WNBA prop market card"
Cohesion: 0.23
Nodes (6): main(), player_ids(), publish(), render(), run_card(), slate()

### Community 552 - "tests/test_pbp_backfill_resilience.py"
Cohesion: 0.24
Nodes (6): _backfill_body(), test_a_failed_game_rolls_the_connection_back(), test_a_run_that_wrote_nothing_reports_an_error_not_a_success(), test_errors_are_counted_not_just_logged(), test_partial_failures_are_surfaced_too(), test_the_rollback_cannot_itself_raise()

### Community 553 - "CLV no-vig and entrypoint tests"
Cohesion: 0.21
Nodes (5): _adapt(), _parameterised_sql(), test_check_line_movement_query_interpolates(), test_parameterised_sql_escapes_literal_percents(), test_the_scanner_actually_catches_the_regression()

### Community 554 - "Paused rows and NFL prop lead ceiling"
Cohesion: 0.30
Nodes (8): _nfl_prop_too_early(), _iso(), test_a_kickoff_beyond_the_ceiling_is_too_early(), test_a_started_or_unknown_kickoff_is_not_too_early(), test_the_boundary_is_inclusive_at_the_ceiling(), test_the_scorer_and_the_card_read_ONE_constant(), test_the_scorer_loop_actually_applies_the_ceiling(), test_the_z_suffix_parses_like_the_offset_form()

### Community 555 - "NCAAF prop market sweep"
Cohesion: 0.26
Nodes (7): candidates(), dedupe(), grade(), load_board(), main(), norm(), profit()

### Community 561 - "MLB prop odds backfill tests"
Cohesion: 0.17
Nodes (5): test_each_event_is_anchored_to_its_own_first_pitch(), test_it_is_append_only(), test_it_records_the_served_snapshot_not_the_requested_one(), test_the_anchor_arithmetic_is_pre_game_for_every_start_time(), test_the_listing_instant_precedes_every_first_pitch()

### Community 563 - "NFL prop universe model rate"
Cohesion: 0.29
Nodes (6): _universe_summary(), test_a_universe_without_the_model_sums_still_summarises(), test_mean_projection_and_mean_actual_separate_mean_bias_from_shape_bias(), test_model_over_rate_and_its_gap_are_reported(), _universe(), test_a_nonfinite_fair_price_cannot_switch_the_gate_off()

### Community 568 - "Mobile stats filter UX check"
Cohesion: 0.18
Nodes (9): chip, lineOnlyFn, playersDay, ROOT, sportReset, stats, teams, teamsDay (+1 more)

### Community 569 - "tests/test_game_log_backfill_skip.py"
Cohesion: 0.25
Nodes (5): _backfill_body(), test_a_game_absent_from_our_games_table_is_still_skipped(), test_no_skip_is_keyed_on_date_alone(), test_the_coverage_set_is_scoped_to_the_season_being_built(), test_the_skip_is_keyed_on_game_id()

### Community 572 - "NCAAF line move spots"
Cohesion: 0.27
Nodes (6): eval_follow_spread(), eval_follow_total(), load(), main(), _summ(), wilson()

### Community 573 - "Live feed probe script"
Cohesion: 0.24
Nodes (8): dump_vendor(), _get(), _is_live(), _key(), _row(), run(), _totals(), _vendor_key()

### Community 574 - "tests/test_prompt_reads_thresholds.py"
Cohesion: 0.18
Nodes (4): test_the_auto_pause_lookup_fails_open(), test_the_prompt_carries_no_per_model_cut(), test_the_prompt_still_says_it_is_pasted_once(), test_the_sync_mirrors_both_pause_registers()

### Community 575 - "tests/test_system_health_meta_steps.py"
Cohesion: 0.25
Nodes (5): _meta_steps(), test_aborted_sentinel_is_excluded(), test_health_check_is_excluded(), test_model_quality_is_excluded(), test_sentinel_matches_the_writer()

### Community 577 - "NBA period scores ingestor"
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

### Community 590 - "Mobile stat segment tests"
Cohesion: 0.20
Nodes (10): _read(), test_one_shared_defensive_set(), test_position_is_never_inferred_from_stats(), test_runs_in_pr_ci(), test_search_and_position_review_fixes(), test_segment_labels_cap_only_on_fit(), test_tabs_speak_the_visible_label_not_the_key(), test_the_behavioural_checks_pass() (+2 more)

### Community 591 - "NFL prop opening signal cleanup tests"
Cohesion: 0.23
Nodes (6): _stmts(), test_it_deletes_exactly_the_three_measured_lock_keys(), test_it_does_not_touch_picks_or_discord(), test_it_still_skips_a_key_that_has_a_standing_bet(), test_migration_is_one_statement(), test_standing_pick_uses_lock_key_sql_not_player_id()

### Community 593 - "tests/test_scorer_commits_per_game.py"
Cohesion: 0.40
Nodes (8): _between(), _run_scorer_body(), test_a_lost_connection_re_runs_the_game_once_and_never_the_pass(), test_each_game_is_its_own_committed_unit(), test_no_bulk_delete_of_non_bet_rows_precedes_the_loop(), test_picks_are_only_counted_once_the_game_committed(), test_the_housekeeping_delete_is_a_sweep_after_the_loop(), test_the_outer_handler_still_records_the_failure()

### Community 597 - "Model trainer and research scripts"
Cohesion: 0.31
Nodes (6): bias_table(), confident_share(), load_artifact(), main(), poisson_sf(), predict()

### Community 598 - "tests/test_live_game_state_poller.py"
Cohesion: 0.22
Nodes (7): _bases_state(), _extract_state(), test_bases_state_empty(), test_bases_state_loaded(), test_bases_state_single_runner(), test_extract_state_handles_empty_feed(), test_extract_state_pulls_fields_from_live_feed()

### Community 599 - "NFL prop under bias study"
Cohesion: 0.27
Nodes (6): bias_table(), implied(), load(), main(), norm(), profit()

### Community 60 - "tests: test_wnba_availability + wnba_availability"
Cohesion: 0.07
Nodes (43): absence_features(), absent_teammates(), build_context_features(), expected_rotation(), is_starter_tier(), _mean(), prior_rows(), recent_team_game_dates() (+35 more)

### Community 600 - "NFL prop pulled quote filter"
Cohesion: 0.17
Nodes (11): _bets_from_kalshi(), drop_pulled_quotes(), _ts(), _zero_vig_american(), test_zero_vig_american_round_trips_through_devig(), _q(), test_a_book_on_its_own_cadence_is_not_penalised_inside_three_hours(), test_a_book_that_stopped_returning_the_game_is_dropped() (+3 more)

### Community 601 - "NCAAF venue feature tests"
Cohesion: 0.18
Nodes (6): _venue_features(), test_altitude_climb_is_signed_from_each_teams_own_elevation(), test_both_teams_travel_at_a_neutral_site(), test_eastward_travel_is_positive_tz_shift(), test_host_travels_zero_at_a_normal_home_game(), test_missing_venue_data_yields_nulls_not_zeros()

### Community 608 - "supabase/functions/sharpsports-webhook: index + index"
Cohesion: 0.25
Nodes (5): internalIdFor(), pick(), admin, admin, cors

### Community 609 - "ET game date tests"
Cohesion: 0.20
Nodes (5): _sources(), test_no_game_date_is_derived_from_the_container_clock(), test_the_live_modules_cannot_even_name_date_today(), test_today_et_is_eastern_inside_the_window_that_broke(), test_today_et_matches_the_pipelines_own_derivation()

### Community 612 - "supabase/functions/stripe-checkout/index.ts"
Cohesion: 0.31
Nodes (8): customerFor(), form(), json(), stripe(), admin, cors, PRICES, TRIAL_DAYS

### Community 614 - "tests/test_book_list_budget.py"
Cohesion: 0.31
Nodes (4): _names(), test_every_book_the_nfl_prop_model_bets_at_is_actually_fetched(), test_the_nfl_prop_pull_is_one_group_with_both_references_in_it(), test_the_shared_list_is_one_group()

### Community 615 - "Live scorer best line tests"
Cohesion: 0.18
Nodes (3): _setup(), test_an_artifact_wanting_an_unmapped_column_is_never_scored(), test_the_same_fixture_does_reach_the_model_when_the_map_agrees()

### Community 62 - "NBA game market lab"
Cohesion: 0.05
Nodes (62): assemble(), _assert_spread_sign(), attach_close(), bars(), bet_frame(), blind_bets(), blind_first_fetch(), boot_ci() (+54 more)

### Community 620 - "Mobile NHL look-ahead window tests"
Cohesion: 0.29
Nodes (5): _fn(), _read(), test_the_nhl_read_matches_the_other_look_aheads(), test_the_sport_chip_is_the_hook_not_an_allowlist(), test_use_today_picks_fetches_nhl_across_that_window()

### Community 621 - "NFL prop week-one candidate pool"
Cohesion: 0.22
Nodes (5): partially_played_week_one(), _player_row(), _team_row(), test_a_clean_week_one_is_unchanged(), test_teams_still_to_play_keep_a_candidate_pool()

### Community 623 - "NBA injury report player matching"
Cohesion: 0.11
Nodes (13): match_player(), name_first_last(), _near_season(), norm_name(), remap_changes(), _row(), team_code(), test_a_name_printed_differently_matches_on_surname_and_initial_within_the_team() (+5 more)

### Community 628 - "Registered not firing tests"
Cohesion: 0.17
Nodes (5): test_a_model_with_picks_but_no_threshold_row_is_still_listed(), test_it_reports_whether_the_model_is_paused_and_whether_it_is_trained(), test_performance_starts_from_the_registered_models_not_the_graded_picks(), test_the_sport_survives_when_there_are_no_graded_picks(), test_the_zero_state_short_circuits_before_the_roi_row()

### Community 629 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.47
Nodes (6): contentHeight(), evalExpr(), lineOf(), styleBlock(), styleProp(), visualHeight()

### Community 633 - "Game line market sweep job"
Cohesion: 0.29
Nodes (3): test_sport_and_market_are_bounded(), test_the_declared_key_is_present_and_valid(), test_the_runner_imports_the_script_main_not_a_shell()

### Community 635 - "tests/test_demote_ncaaf_over_under_platt.py"
Cohesion: 0.32
Nodes (4): _stmts(), test_it_demotes_only_the_measured_promotion(), test_it_does_not_move_the_gate_the_floor_or_a_pause(), test_migration_is_one_statement()

### Community 636 - "Pipeline watch run and announce"
Cohesion: 0.20
Nodes (6): test_a_clean_run_still_posts(), test_a_failed_query_rolls_back_and_does_not_sink_the_run(), test_a_missing_webhook_is_not_ledgered_either(), test_a_run_with_findings_posts_them(), _announce_and_ledger(), run_watch()

### Community 637 - "tests/test_discord_post_one_pick_migration.py"
Cohesion: 0.29
Nodes (3): _pairs(), test_it_names_each_measured_extra_and_the_row_kept(), test_the_update_does_not_rewrite_the_graded_outcome()

### Community 638 - "tests/test_game_scorer_spares_nfl_props.py"
Cohesion: 0.43
Nodes (5): _between(), _run_scorer_body(), test_an_nfl_game_never_enters_the_per_game_clear(), test_both_live_non_bet_clears_leave_nfl_rows(), test_the_left_out_ufc_clear_only_removes_unsettled_non_bets()

### Community 64 - "NBA play-by-play loader and gap fill"
Cohesion: 0.06
Nodes (37): active_queries(), alias_map_rows(), build_gap_game(), build_map(), _date10(), _dicts(), download(), ensure_tables() (+29 more)

### Community 641 - "tests/test_mobile_ota_self_update.py"
Cohesion: 0.32
Nodes (4): _read(), test_app_root_mounts_the_ota_updater(), test_the_pieces_exist(), test_the_updater_actually_applies_the_update()

### Community 650 - "Decide on calibrated probability tests"
Cohesion: 0.20
Nodes (6): _make_pick(), _pick_at(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(), test_avoid_is_judged_on_the_calibrated_number_too(), test_a_non_dk_f5_spread_pick_keeps_dk_columns_null(), test_a_non_dk_f5_total_pick_keeps_dk_columns_null()

### Community 653 - "NFL prop book sweep and bettability"
Cohesion: 0.14
Nodes (12): _actuals(), _board(), p(), _line(), main(), _run(), soft_verdict(), test_a_bettable_book_still_passes() (+4 more)

### Community 655 - "Push notifier step"
Cohesion: 0.22
Nodes (5): step_push_notifications(), _expo_send(), notify_feedback_replies(), notify_line_changes(), notify_signal_changes()

### Community 656 - "scripts/nfl_wind_publisher.py"
Cohesion: 0.20
Nodes (6): _changed(), _clear_scored_row(), latest_eval_rows(), publish_scored(), _dump(), _run()

### Community 658 - "Worker-only table guard tests"
Cohesion: 0.20
Nodes (5): _call_source(), _repo_sources(), test_every_guard_on_a_worker_only_table_asks_about_rls(), test_every_worker_only_create_site_goes_through_the_gated_helper(), test_no_create_site_uses_the_ungated_builder()

### Community 660 - "SBR loader parsing"
Cohesion: 0.25
Nodes (3): canonical_abbrev(), parse_csv_file(), test_sbr_abbreviations_are_canonicalised_for_mlb_only()

### Community 662 - "Signal publish-on-write tests"
Cohesion: 0.10
Nodes (11): _body(), _row(), test_a_publish_failure_does_not_kill_the_tick(), test_a_tick_that_writes_a_bet_publishes_it(), test_a_tick_that_writes_no_bet_publishes_nothing(), test_every_pick_writing_scheduler_job_publishes(), test_publish_syncs_thresholds_before_either_notifier(), test_the_poller_no_longer_claims_it_does_not_notify() (+3 more)

### Community 665 - "NFL research backup"
Cohesion: 0.44
Nodes (5): backup(), files(), main(), restore(), verify()

### Community 670 - "NHL moneyline market lab"
Cohesion: 0.39
Nodes (5): grid(), load(), main(), show(), _ts()

### Community 673 - "NFL live prop settlement tests"
Cohesion: 0.29
Nodes (6): _bet(), db(), _left(), _statement(), test_a_bet_priced_at_another_books_line_survives_and_a_bet_with_no_price_does_not(), test_the_statement_names_both_prices()

### Community 677 - "Discord void notices"
Cohesion: 0.29
Nodes (4): test_prob_only_picks_fall_back_to_the_settlement_price(), test_units_convention_matches_the_stated_rule(), _decimal_odds(), units_won()

### Community 68 - "Database URL doctor tests"
Cohesion: 0.10
Nodes (17): main(), scram_stored_key(), database_url(), _default_env_path(), env_value(), parse_env_file(), test_a_missing_env_file_is_empty_not_an_error(), test_a_value_containing_equals_survives() (+9 more)

### Community 689 - "Parlay leg correlation estimates"
Cohesion: 0.36
Nodes (5): estimate(), estimate_basketball(), estimate_mlb(), main(), _median()

### Community 693 - "NFL live pick writer: night games and resolution"
Cohesion: 0.25
Nodes (3): test_a_night_game_pick_carries_the_game_s_date_not_the_utc_clock(), test_nothing_written_means_nothing_announced(), test_resolution_refuses_rather_than_guesses()

### Community 696 - "Health check cadence tests"
Cohesion: 0.29
Nodes (5): test_cadence_reads_a_daily_bar_off_the_dates(), test_cadence_reads_a_multi_day_window(), test_cadence_reads_a_same_day_bar(), test_cadence_survives_a_missing_or_unparseable_date(), _cadence_from_dates()

### Community 697 - "Market handicap features"
Cohesion: 0.29
Nodes (4): build_rich_handicap(), _fav_signed_home_move(), _gated_flag(), _mul()

### Community 705 - "NCAAF travel geography features"
Cohesion: 0.29
Nodes (5): haversine_miles(), tz_offset_from_lon(), trip(), test_haversine_matches_real_geography(), test_timezone_offsets_land_in_the_right_zones()

### Community 707 - "NHL goalie line helpers"
Cohesion: 0.83
Nodes (4): _goalie_line(), regressed(), saved_above(), tot()

### Community 708 - "Pipeline watch: credit burn"
Cohesion: 0.25
Nodes (4): test_burn_is_judged_against_the_cap_not_against_yesterday(), test_burn_survives_a_non_numeric_credits_column(), test_failed_api_calls_are_reported_even_when_burn_is_low(), findings_from_burn()

### Community 709 - "NHL prop EV lab and Kalshi ladder recording"
Cohesion: 0.12
Nodes (5): test_the_recorder_walks_every_mapped_series(), _league(), _loose_summary(), s(), _name()

### Community 71 - "tests/test_live_orchestrator.py"
Cohesion: 0.04
Nodes (44): should_fetch(), split_triggers(), under_credit_cap(), apply_daily_cap(), classify_live_signal(), _ev_floor(), expected_value(), decide() (+36 more)

### Community 711 - "Live money no record-only tests"
Cohesion: 0.43
Nodes (4): _allowed(), _hits(), _rel(), test_the_repo_has_no_record_only_or_paper_tracking_mode()

### Community 712 - "Team stats twin code tests"
Cohesion: 0.29
Nodes (3): test_mlb_twin_codes_do_not_false_crit(), test_mlb_twin_reverse_lookup_also_resolves(), test_season_final_in_april_still_caught_on_twin_code()

### Community 719 - "Mobile accessibility verify script"
Cohesion: 0.67
Nodes (3): read(), readUtf8(), verticalSlop()

### Community 72 - "Market handicap attach tests"
Cohesion: 0.07
Nodes (16): attach_market_handicap(), empty_handicap(), test_a_row_with_all_handicap_null_survives_dropna(), test_attach_overlays_movement_and_public_without_clobbering_fundamentals(), test_attach_with_nothing_fills_none_not_zero(), test_every_handicap_column_is_sparse_ok(), test_favorite_signed_move_flips_when_home_is_the_dog(), test_in_play_open_rows_are_still_bounded_in_the_movement_loader() (+8 more)

### Community 721 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.67
Nodes (3): closeOf(), openTag(), toggleUse()

### Community 731 - "UFC event page parsers"
Cohesion: 0.17
Nodes (10): _int_or_none(), _parse_event_date(), parse_event_list(), parse_event_page(), _two_ints(), test_event_date(), test_parse_event_list(), test_parse_event_page_draw_fight() (+2 more)

### Community 732 - "NFL live pick writer: publish refusals"
Cohesion: 0.29
Nodes (4): refuse_publish_reason(), test_refuse_publish_allows_a_real_rush_under(), test_refuse_publish_blocks_pass_attempt_overs(), test_refuse_publish_blocks_the_constant_prob_fingerprint_even_on_rush()

### Community 74 - "Prop CLV and SQL escaping tests"
Cohesion: 0.09
Nodes (18): _fn(), test_a_backfill_failure_never_breaks_settlement(), test_a_pick_is_only_stamped_captured_once_a_measure_resolved(), test_a_pick_stamped_after_first_pitch_is_never_measured(), test_a_prop_pick_whose_label_has_no_name_is_skipped_not_guessed(), test_both_guards_agree(), test_clv_pct_never_compares_prices_across_a_moved_line(), test_every_prop_model_maps_to_a_dk_market() (+10 more)

### Community 75 - "scripts: ncaaf_margin_eval + test_ncaaf_margin_eval"
Cohesion: 0.06
Nodes (44): margin_cover_prob(), build_frames(), _fit(), fit_and_register(), fit_and_register_totals(), main(), _matrix(), _print_sweep() (+36 more)

### Community 76 - "ncaaf_live/tests/test_serve.py"
Cohesion: 0.07
Nodes (37): _clock_seconds(), extract_live_states_cfbd(), _parse_situation(), _cfbd_game(), _ctx(), _no_ev_floor(), _settled(), _stamped() (+29 more)

### Community 82 - "Mobile TypeScript runners: error states and CLV card"
Cohesion: 0.04
Nodes (54): node_exe(), node_strips_types(), tsx_cmd(), _app(), _clv_card(), _node_strips_types(), _server(), test_a_label_book_nfl_pick_compares_its_line_with_that_book() (+46 more)

### Community 850 - "Database connection and CLI ingestors"
Cohesion: 0.43
Nodes (4): _fmt(), _profit_sql(), _row(), strategy_analysis()

### Community 853 - "Pipeline watch: unfinished passes"
Cohesion: 0.33
Nodes (4): test_a_clean_pass_produces_no_finding(), test_a_pass_with_failed_steps_is_reported(), test_a_pass_with_no_finish_is_reported_without_over_reading_it(), findings_from_passes()

### Community 854 - "Health check lateness tests"
Cohesion: 0.40
Nodes (3): test_a_late_check_says_how_late(), test_days_late_falls_back_rather_than_lying(), _days_late()

### Community 856 - "NCAAF feature assembly"
Cohesion: 0.20
Nodes (4): _assemble_ncaaf_features(), _game_tier(), test_assembly_carries_venue_context_and_hfa(), test_season_opener_gets_a_zero_rest_differential_not_a_null()

### Community 86 - "scripts/nfl_edge_preregistered_2026.py"
Cohesion: 0.08
Nodes (41): _load_backtest(), main(), selected_bets(), bar(), bets_frame(), bh(), binom_line(), _by_game() (+33 more)

### Community 860 - "CFBD local season aggregates"
Cohesion: 0.40
Nodes (3): _local_aggregates(), test_local_aggregates_computes_season_to_date_form(), test_local_aggregates_does_no_date_filtering_of_its_own()

### Community 862 - "NFL prop market card and lead ceiling"
Cohesion: 0.08
Nodes (16): card(), _kalshi_ladders_or_empty(), main(), pick_rows(), publish(), reference_ladders(), render(), slate() (+8 more)

### Community 864 - "NBA stint clock and shot value tests"
Cohesion: 0.40
Nodes (3): parse_clock(), test_field_goal_value(), test_parse_clock()

### Community 868 - "Worker job: Discord void notice"
Cohesion: 0.40
Nodes (3): test_the_worker_job_is_registered_and_defaults_to_dry_run(), _job_publish_discord_void(), _validate_publish_discord_void()

### Community 87 - "tests: test_player_positions + player_positions_ingestor"
Cohesion: 0.06
Nodes (28): _basketball(), basketball_group(), _fresh_source_ids(), _get_json(), ingest_player_positions(), match_to_log(), _name_index(), _ncaaf() (+20 more)

### Community 878 - "NFL weather cache import"
Cohesion: 0.14
Nodes (11): main(), rows_from_file(), source_for(), stadium_from_name(), stored_files(), _INSERT_PLACEHOLDERS(), test_a_non_issued_or_empty_payload_yields_nothing(), test_every_hour_becomes_one_row_in_column_order() (+3 more)

### Community 88 - "NBA prop market card tests"
Cohesion: 0.08
Nodes (33): fair_under(), q(), run(), run_full(), _settle(), test_a_fetch_after_now_or_at_tip_and_a_close_row_never_decide(), test_a_fetch_older_than_the_window_is_not_a_price(), test_a_game_already_bet_is_never_decided_again() (+25 more)

### Community 89 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.04
Nodes (48): a11ySrc, allowHit, ALLOWLIST, app, badExempt, bar, bareClose, baselineLeft (+40 more)

### Community 9 - "CFBD ingestor and school map"
Cohesion: 0.06
Nodes (33): backfill_ncaaf(), backfill_ncaaf_lines(), backfill_ncaaf_players(), backfill_ncaaf_qb(), _existing_ncaaf_ids(), _fold(), _get(), ingest_ncaaf_game_log() (+25 more)

### Community 91 - "NBA prop model lab"
Cohesion: 0.07
Nodes (49): books(), decimal(), expected_value(), fit_alpha(), implied(), nb_logpmf(), p_over(), _agg() (+41 more)

### Community 96 - "tests/test_heartbeat_watchdog.py"
Cohesion: 0.12
Nodes (21): _break_db(), test_a_failed_post_does_not_start_the_throttle(), test_a_healthy_start_never_announces_a_recovery(), test_a_returning_outage_alerts_again_immediately(), test_a_silent_failure_alerter_is_caught_by_the_watchdog(), test_a_stalled_pipeline_outranks_a_silent_alerter(), test_an_unreadable_heartbeat_table_does_not_raise_a_second_alarm(), test_connection_is_closed_even_when_the_check_alerts() (+13 more)

### Community 106 - "Supabase schema tables"
Cohesion: 0.03
Nodes (101): api_call_log, device_push_tokens, feedback_messages, feedback_threads, fighters, golf_players, golf_rounds, idx_api_call_api_ts (+93 more)

### Community 179 - "mobile/app.json"
Cohesion: 0.05
Nodes (38): backgroundColor, foregroundImage, adaptiveIcon, package, projectId, expo, android, extra (+30 more)

### Community 184 - "mobile/package.json"
Cohesion: 0.06
Nodes (30): dependencies, expo, expo-asset, expo-dev-client, expo-font, expo-notifications, expo-status-bar, expo-updates (+22 more)

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

### Community 496 - "Mobile package manifest"
Cohesion: 0.25
Nodes (8): scripts, android, build:ios:preview, build:ios:production, ios, start, typecheck, web

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

### Community 692 - "NBA play-by-play write-up"
Cohesion: 0.25
Nodes (7): Commands, How a stretch is built (each rule is pinned by a test that was watched to fail), NBA play-by-play and on-court lineup segments, Source, Tables (all worker-only, locked down where they are created), Things a reader should know, What was loaded, and the checks (re-measured 2026-10-17 on production, after the rebuild)

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

### Community 81 - "docs: nhl_market_lab + nhl_clv_ev_assessment"
Cohesion: 0.08
Nodes (40): nhl_research worker job, scripts/nhl_derivative_totals_backtest, data/ingestors/nhl_derivative_odds_history, models/nhl_props.py (Spec per market), DraftKings de-vigged price sits above realised over-rate, Anytime goalscorer: not a candidate once names corrected, nhl_moneyline and nhl_moneyline_regulation: no cut clears, Game models: lock later? Refuted (+32 more)

### Community 109 - "Monitoring and record view docs"
Cohesion: 0.05
Nodes (24): Hybrid Pin-agreement filter on mlb_over_under bets, mlb_runline and mlb_over_under (paused), F5 odds coverage (DK carries F5 ML only), roi_collapse check, Honest MLB signal is ~0.55-0.56 AUC, api_call_log table, Heartbeat watchdog, Live monitor dashboard (monitoring/) (+16 more)

### Community 151 - "docs/rules_evidence.md"
Cohesion: 0.07
Nodes (13): 'Decisions needed from you' is second person, never first, A model in config.MODELS with no FEATURE_MAP entry kills scoring for every sport, Every front-end change is reviewed by the UX designer agent before its PR opens, Gate the number that gets bet (cal_error_actionable), A health check must not gate on the thing that breaks, The settled live-prop record is zero bets, The Odds API returns x-requests-remaining on every response, including 401, How the pick rule was found: the NCAAF live loop delete-and-replaced every 45s (+5 more)

### Community 183 - "docs: probability_calibration + nfl_rule_2026_track"
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

### Community 252 - "docs/cloud_worker.md"
Cohesion: 0.09
Nodes (27): catch_up_daily_pipeline / tracking/daily_retry.py, test_every_model_artifact_on_disk_is_tracked_by_git, DISCORD_WEBHOOK_* variables, one channel per sport, Heartbeat watchdog -> DISCORD_WEBHOOK_OPS, LIVE_DAILY_CREDIT_CAP and RUN_LIVE_LOOP, In-play live loop under a */10 supervisor, Live monitor dashboard (monitoring/, MONITOR_TOKEN), NFL poll driver — hourly from T-10, every 10 min inside 3h (+19 more)

### Community 253 - "docs/history: learnings + build_state"
Cohesion: 0.09
Nodes (25): Data sources table (Odds API, SBR, MLB Stats API, Savant, Open-Meteo, NHL API, nba_api, ESPN, UFC CSV mirror, DataGolf), FanGraphs / pybaseball removed (IP-blocked); replaced by MLB Stats API + Savant, MLB_Basic.csv datawarehouse (2009-2025, 40,996 games; runline derived as -1.5), What's built (package tree) and what's not, AlphaPy rejected (deprecated, team-level only, defunct connectors), Team stats need at least 10 games before they stabilize, The go-live gate prevents going live on lucky backtests, Historical team-stat backfill uses {season}-01-01 as as_of_date (+17 more)

### Community 264 - "monitoring/static/dashboard.html"
Cohesion: 0.16
Nodes (26): Signalbase pipeline monitor dashboard page, dashboard.html ageNote(), dashboard.html callRow(), dashboard.html connect(), dashboard.html drawSeries(), dashboard.html drawTimeline(), dashboard.html flush(), dashboard.html ingestCalls() (+18 more)

### Community 292 - "docs/sports/nhl.md"
Cohesion: 0.12
Nodes (22): NHL models code-complete, not yet trained (2026-06-13 snapshot), docs/nhl_clv_ev_assessment.md: the current CLV/EV grade of every NHL model, Per-game logs from the NHL stats API (team, goalie, skater) via data/ingestors/nhl_game_logs.py, Starting-goalie confirm via ESPN core probableStartingGoalie; game-model veto on Out/Doubtful, docs/nhl_market_research.md: six defects and the honest walk-forward, data/nhl_asof.py: one function rates goalies and teams as-of, strictly before the date, nhl_over_under is live as a rule: Pinnacle de-vigged vs the bettable books in the same fetch, NHL pipeline steps (results before settle, odds, stats, totals card, scoring, settlement) (+14 more)

### Community 306 - "Model quality and MLB research docs"
Cohesion: 0.12
Nodes (14): mlb_spread_market 1.8pp run-line rule, mlb_total_market paper totals logger, mlb_total_public_fade card (paper UNDER), Slate concentration guard (insert-time), clv_degradation check, model_quality_checks table, Daily model-quality monitor, public_fade_risk check (+6 more)

### Community 310 - "docs: mlb_market_handicap_features + mlb_game_market_gate"
Cohesion: 0.15
Nodes (20): Market-aware MLB model, trainable on three seasons, _get_dk_odds bounds on commence_time — the 'pre-game' line was a mid-game price, Activation as a new 2026-only model — superseded by SPARSE_OK, MARKET_MOVEMENT_FEATURES — nine columns in features/market_movement.py, sbr_consensus is one snapshot per game — 17 seasons carry no movement, models/game_market_gate.py — a decision-time overlay for MLB game models, GAME_MARKET_GATE_MODE=live by default, Live-artifact record of the four MLB game models (2026-09-15) (+12 more)

### Community 311 - "docs/sports/ncaaf.md"
Cohesion: 0.13
Nodes (19): Models registry (model id, sport, market, target), ncaaf_spread: cross-book opener rule, structurally dormant on this feed, New CFBD games are dated by Eastern kickoff; existing ids are not rewritten, Old ET/UTC twin rows stay; mirror_scores_to_alias_rows writes the final onto every alias, Issued forecasts for 2024-2025 (game_weather_issued) and the four-arm weather test, Kalshi NCAAF game markets recorded hourly (research only), The live models price FBS-vs-FBS only (shipped 2026-09-13), ncaaf_live_total: what has been tried (six attempts on the 2025 replay) (+11 more)

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

### Community 382 - "NFL prop and live research write-ups"
Cohesion: 0.06
Nodes (31): Halftime second-half lines, out of sample at real prices, The live prop market leans over like the pre-game one, Publish backstop refuses pass-attempt overs, Accrued carries from ESPN core leaders, rush_attempt_pace model: one offset on the book's number, Pace ratio, In-play rushing-attempt UNDER on pace ratio >= 1.25, The eleven NFL distributional prop models (+23 more)

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

### Community 558 - "docs/health_checks.md"
Cohesion: 0.24
Nodes (10): model_artifacts_load counts what it opened, model_artifacts table fallback restore, Three separate artifact questions, three separate failures, KNOWN_UNTRAINED — config models intentionally without artifacts, Pipeline-observability checks: refresh_pass_completion, refresh_pass_steps, signal_delivery, pick_label_integrity, pipeline_runs — the run ledger (tracking/run_ledger.py), Retrain Model workflow (retrain_model.yml), tracking/system_health.py — CRIT and WARN feed checks (Step 12) (+2 more)

### Community 560 - "docs/retrain_2026_plan.md"
Cohesion: 0.18
Nodes (12): scripts/paused_model_assessment, data.ingestors.baseball_savant_ingestor, models.trainer, F5 O/U and F5 RL paused: leak-mismatched, synthetic-line trained, NCAAF in-play season replay: -3.4% and -13.1%, No model has a cut that clears on the deployed artifact, batter_sb: opp_team_sb_allowed feature, Phase 0: train 2019-2024, holdout 2025 (+4 more)

### Community 603 - "docs/reviews/2026-09-07-nfl-props-deep-dive.md"
Cohesion: 0.33
Nodes (7): Twelve artifacts committed from a replica failed pickle.load unnoticed for two weeks, The eleven NFL projection prop models, unpaused on placeholder thresholds, nfl_prop_market: the de-vig rule (Pinnacle as truth, equal lines only), The scorer is pinned to today, the card looks ten days ahead, 112 bets on one Sunday from untuned models; 41-46% BET rates are placeholders, Eleven NFL distributional props paused 2026-09-14, NFL props deep dive — two lanes, one of them can't see the slate (2026-09-07)

### Community 606 - "NCAAF and MLB research docs"
Cohesion: 0.05
Nodes (22): scripts/ncaaf_search/, Live inning gate replay, mlb_live_total_runs (in-play total), Negative-binomial (NB1) tail, pregame_total_line feature (market anchor), ncaaf_live_total 2025 in-play backtest, ncaaf_live_win_prob 2025 in-play backtest, CollegeFootballData (CFBD) as primary source (+14 more)

### Community 627 - "docs/market_coverage.md"
Cohesion: 0.36
Nodes (7): ncaaf_prop_odds_ingestor and its probe, test_the_mlb_board_and_the_mlb_pull_are_one_set, MLB probe 2026-09-05 — served, unsupported and unpriced keys, NCAAF prune — FOOTBALL_MARKET_NOT_PRICED per league, scripts/probe_market_coverage.py — one market per call, writes nothing, Neither prop ingestor writes to api_call_log, Prop market coverage — what the feed actually serves

### Community 652 - "(root): pr-ci + requirements"
Cohesion: 0.33
Nodes (5): Mobile thresholds drift check (generate_mobile_thresholds --check), NFL preflight --ci, PR CI workflow — non-integration pytest subset, Render blueprint — betting-scheduler background worker, requirements.txt — >= pins for Python 3.14 wheels

### Community 66 - "docs/nfl_props_model.md"
Cohesion: 0.06
Nodes (47): scripts/nfl_prop_market_card, scripts/nfl_prop_replay, scripts/nfl_prop_ladder_grade, scripts/verify_kalshi, data/ingestors/kalshi_prop_ingestor.py (SERIES_MARKET, record_ladders), tackles_assists +21% is a measurement error (control), Traps specific to props, Anytime TD field de-vig: closed (+39 more)

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

### Community 851 - "Player news docs"
Cohesion: 0.53
Nodes (4): PlayerNewsButton / PlayerNewsSheet / usePlayerNews / fetchPlayerNews, player_news table: player_id plus player_key, Recent News sheet on prop player screens, Player news: Recent News sheet

## Ambiguous Edges - Review These
- `Claim: the app cannot write to the backend` → `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`  [AMBIGUOUS]
  docs/privacy.html · relation: conceptually_related_to

## Knowledge Gaps
- **105 isolated node(s):** `RFC-4122`, `@babel/core`, `babel-plugin-module-resolver`, `babel-preset-expo`, `expo-asset` (+100 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 10516 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **213 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_connection()` connect `Odds, WNBA and shared ingestor plumbing` to `Prop odds and odds history ingestors`, `Feature engine and MLB line sweeps`, `Paper tracker bankroll and scorer database calls`, `CFBD ingestor and school map`, `Discord signal notifier tests`, `Daily pipeline runner and push notifier`, `MLB in-play history and live cut sweeps`, `NFL prop market stack, devig and information test`, `NBA prop projection card`, `NHL market lab and live artifact grading`, `NCAAF in-play history pulls`, `NCAAF feature engine and FBS registry`, `NFL weekly wind card and odds snapshots`, `EV floor replay and honest cut`, `WNBA prop market card`, `DataGolf ingestor and NHL SBR archive`, `NCAAF prop market sweep`, `Worker job queue`, `Failure alerter fake-connection tests`, `scheduler.py`, `NCAAF gameday worker and CFBD feed`, `Live feed probe script`, `NBA play-by-play loader and gap fill`, `NBA period scores ingestor`, `tests/test_umpire_ingestor.py`, `tests/test_pick_integrity.py`, `NFL pick monitor`, `scripts: ncaaf_margin_eval + test_ncaaf_margin_eval`, `docs: nhl_market_lab + nhl_clv_ev_assessment`, `Discord notifier and void notices`, `tests/test_recap_retries_a_skipped_day.py`, `tests: test_player_positions + player_positions_ingestor`, `NFL prop under bias study`, `tests/test_ncaaf_pbp_store.py`, `tests/test_heartbeat_watchdog.py`, `NHL prop card and blocked shots model`, `Record correction post tests`, `Model trainer, WNBA and NHL research scripts`, `tests/test_live_calibration.py`, `nfl_live_leader/gameday.py`, `Heartbeat watchdog and ops alerts`, `Game scorer core and live scorer`, `scripts: nhl_prop_backtest + nhl_prop_ev_lab`, `features/golf_feature_engine.py`, `DDL guard and research backup snaps`, `NCAAF live state building tests`, `models/nhl_props.py`, `Push notifier step`, `scripts/nfl_wind_publisher.py`, `tests/test_mlb_game_market.py`, `Discord results recap restates`, `NFL research backup`, `NHL moneyline market lab`, `NBA box score enrichment`, `X publisher and brand avatar`, `NHL stats, game logs and SBR archive`, `scripts/nfl_preflight.py`, `Push notifier and tickets`, `Parlay leg correlation estimates`, `NFL prop odds ingestor and backfill`, `tests/test_nfl_rule_2026_track.py`, `scripts/game_line_market_sweep.py`, `NFL opener publisher and lock keys`, `tests/test_first_signal_repair.py`, `NBA stats ingestor`, `Historical odds backfill tests`, `NFL prop research readers and local store`, `tests: test_deploy_checks + deploy_checks`, `data/ingestors/nfl_inplay_history.py`, `Probability calibration and its sweep`, `NBA results ingestor store`, `Record correction posting script`, `tests/test_team_board_cache.py`, `MLB prop market sweep`, `Failure alerter and calibration watch`, `MLB stats ingestor and pitcher backfill`, `MLB totals public fade top-k study`, `Search feature matrices and opponent adjustment`, `NFL weather and wind totals`, `NFL player stats ingestors`, `Best line threshold sweep`, `NCAAF in-play history backtest`, `tests/test_ncaaf_qb_features.py`, `Monitoring HTTP stream handler`, `Prop box score fill`, `Starter-out dataset builder`, `Pitcher stats as-of invariant tests`, `NCAAF gameday pick lock tests`, `Model quality monitor`, `UFC CSV loader`, `NHL prop backtest and combined cap`, `Database connection and CLI ingestors`, `NFL prop market card and lead ceiling`, `ESPN player news ingestor`, `Live honest cut and NHL regulation probability`, `NHL derivative totals backtest`, `Kalshi game market recorder`, `NFL weather cache import`, `Outcome edge scan`, `UFC stats ingestor and fighter pages`, `Anon grants and lock-down tests`, `Prop ladder and Kalshi prop market tests`, `tests/test_promote_calibration_job.py`, `Price prefilter rollback and UFC model compare`, `NFL live pick writer`, `First-signal repair`, `Intraday freshness tests`, `Kalshi prop ladder ingestor`, `System health checks`, `NBA prop market model and card`, `tests/test_batter_prop_log_pin.py`, `Calibration and pipeline watchers`, `Monitoring server tests`, `Injury ingestor and ESPN NHL probables`, `NBA schedule ingestor and tests`, `tests/test_transaction_pooler.py`, `NHL prop card and blocked shots`, `NBA injury report scheduler`, `NCAAF steam lag study`, `MLB game market and public fade cards`, `NCAAF research scripts and steam lag`, `NHL totals lab`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **What connects `RFC-4122`, `@babel/core`, `babel-plugin-module-resolver` to the rest of the system?**
  _105 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Mobile stats board` be split into smaller, more focused modules?**
  _Cohesion score 0.013219616204690832 - nodes in this community are weakly interconnected._
- **Why does `Best line on pre-game picks` connect `docs: best_line + config_topology` to `Best line threshold sweep`, `docs: followups + clv`, `docs/live_betting.md`?**
  _High betweenness centrality (0.010) - this node is a cross-community bridge._
- **Should `Mobile error and load states` be split into smaller, more focused modules?**
  _Cohesion score 0.0297029702970297 - nodes in this community are weakly interconnected._
- **Why does `Model state assessment, all 71 models (2026-09-03 snapshot)` connect `Monitoring and record view docs` to `docs/team_stats_leak.md`?**
  _High betweenness centrality (0.010) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Claim: the app cannot write to the backend` and `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._