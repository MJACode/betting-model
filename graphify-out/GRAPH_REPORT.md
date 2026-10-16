# Graph Report - betting-model  (2026-10-16)

## Corpus Check
- Large corpus: 1451 files · ~2,332,912 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 27225 nodes · 64571 edges · 877 communities (681 shown, 196 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 1690 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `aa13f4ba`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ESPN injury ingestor
- Mobile stats board
- NFL prop market stack and devig
- Record correction and full record posts
- nfl_live_leader/state.py
- tests/test_nfl_live_leader_gameday.py
- nfl_live_leader/gameday.py
- tests/test_calibration_promotion.py
- tests/test_recap_restatement.py
- Mobile pick filters and sorting
- tests/test_ncaaf_alias_scores.py
- tests/test_prop_alternate_lines.py
- Game scorer core and NCAAF board visibility
- tests/test_backtester.py
- scripts: nhl_prop_backtest + nhl_prop_ev_lab
- nfl/live_model/feeds/odds_live.py
- NHL prop cards and cross-model publish
- NBA prop market lab
- Discord signal notifier tests
- nfl/live_model/tests/test_backup_snaps.py
- mobile/scripts: verify_book_links + verify_betslip_combine
- NBA injury report fixture pull tests
- tests/test_paused_keeps_real_verdict.py
- Mobile pick queries, types and custom filters
- mobile/scripts/verify_contrast_tokens.ts
- models/nhl_props.py
- Pick lock after settlement tests
- NFL weather ingest and forecast persistence
- tests/test_mlb_game_market.py
- X and Discord results recap publishers
- Threshold review run tests
- Idle read transaction tests
- tests/test_prop_box_scores.py
- MLB totals public fade model
- Best line and best-price decision tests
- tests/test_ddl_guard.py
- tests/test_job_queue.py
- tests/test_nfl_opener.py
- scripts/nfl_preflight.py
- Mobile sign-in and auth
- Mobile billing config and verify script
- tests/test_publisher_lock.py
- tests/test_dk_direct_feed.py
- tests/test_credit_budget.py
- Mobile thresholds and daily results
- NHL market-anchored moneyline model
- scripts/nfl_wind_publisher.py
- Settlement and self-heal tests
- Live game state and trigger pollers
- tests/test_first_signal_repair.py
- tests/test_ungraded_model_performance.py
- mobile/scripts/verify_push.ts
- Prop price pregame cutoff tests
- Mobile markets and formatting
- NFL prop odds loading tests
- tests/test_nhl_asof.py
- scripts/ncaaf_search: dataset + starter_out
- tests: test_deploy_checks + deploy_checks
- data/ingestors/nfl_inplay_history.py
- Mobile bankroll store and verify script
- Probability calibration tests
- NHL props per-game limit tests
- NCAAF live engine pricing
- Closing line value math
- NBA prop projection card
- tests/test_db_reconnect.py
- NFL live prop tests and pass-attempt bias
- tests/test_live_lock.py
- tests/test_refresh_retry.py
- NBA box score player name resolver
- NBA results ingestor tests
- tests/test_local_cache_is_additive.py
- tests/test_calibration_check_coverage.py
- tests/test_book_team_map.py
- tests/test_team_board_cache.py
- mobile/src/lib: verify_discord_link + discordHelpers
- tests/test_nfl_poll_fast_silence.py
- NHL market lab and live artifact grading
- Prop feature engine rows
- tests/test_weather_lookahead.py
- tests/test_nhl_asof.py
- tests/test_dk_freshness_parse.py
- tests/test_live_calibrated_decision.py
- models: slate_concentration + test_slate_concentration
- NBA prop market publish tests
- View migration lock handling tests
- Prop odds missing game tests
- tests/test_ncaaf_search_features.py
- NCAAF opener strategy search
- Mobile team detail and team stats
- tests/test_nfl_scored_rows.py
- tests/test_cfbd_ingestor.py
- Parlay builder and bet slip
- NCAAF in-play history tests
- tests/test_prop_odds_utc_stamp.py
- Monitoring HTTP stream handler
- NHL game logs as-of windows
- NBA official injury report ingestor
- tests/test_feature_artifact_agreement.py
- CLV price-taken tests
- Mobile matchup, head-to-head and record verify
- tests/test_cloud_retrain_artifacts.py
- NCAAF gameday lock tests
- NCAAF FBS registry tests
- Health skip budget tests
- tests/test_nfl_opener.py
- tests/test_team_stats_asof_invariants.py
- NHL props card tests
- Unit stake sizing and formatting
- tests/test_nfl_wind_publisher.py
- Odds, prop odds and NHL derivative odds ingestors
- NFL live prop model tests
- tests/test_health_reason_and_cadence.py
- tests/test_live_publish_parity.py
- tests/test_nfl_weather_supabase_readback.py
- Pregame line poller tests
- Pitcher stats as-of invariant tests
- tests/test_walk_forward_eval.py
- NBA prop model core
- Live scorer score-change guard
- Pipeline log reason tests
- NHL props card latest quotes
- NCAAF game-day duplicate game tests
- NCAAF in-play score distribution engine
- tests/test_nfl_scored_rows.py
- tests/test_system_health_checks.py
- DB cursor result wrapper
- tests/test_ncaaf_live_states.py
- MLB prop market pregame quote cutoff
- nfl/live_model/feeds: test_feed_resilience + espn
- tests/test_nfl_opener.py
- Mobile feedback and social links
- NFL wind totals model
- tests/test_live_pick_features.py
- Pregame price age tests
- tests/test_prop_missing_features.py
- Mobile app shell and push notifications
- Mobile paywall and billing errors
- tests/test_player_news_ingestor.py
- NBA prop closing line tests
- NFL live pick writer and recorder tests
- tests/test_cfbd_ingestor.py
- Prop player name matching tests
- tests/test_run_ledger_orphans.py
- NFL line snapshot tests
- Mobile in-app purchases
- Odds pruning and sharp book retention tests
- NFL historical weather fetch script
- tests/test_heartbeat_disabled_jobs.py
- tests/test_repair_bogus_first_pitch_labels.py
- nfl/live_model/tests/test_executor.py
- tests/test_sbr_loader.py
- mobile/scripts/ux_scan.mts
- Settlement tracker and feature engine
- Price prefilter timeout rollback tests
- mobile/src/lib/otaUpdate.ts
- tests/test_live_quote_staleness.py
- Prop market one side per line and card publisher tests
- tests/test_clv_backfill_job.py
- UFC stats ingestor resolve tests
- NBA prop stat settlement tests
- supabase/functions/_shared/discord.ts
- Injury fetch and prop odds fake responses
- Prop ladder interpolation and Kalshi pricing tests
- tests/test_job_queue.py
- System health checks and first-pitch guard
- tests/test_system_health_checks.py
- NBA prop market model and card
- UFC event ingest tests
- tests/test_mlb_sbr_twin.py
- tests/test_ufc_phantom_filter.py
- scripts: build_nfl_live_leader_artifact + model
- tests/test_batter_prop_log_pin.py
- tests/test_opp_starter_features.py
- NFL CLV backtest and feature build
- tests/test_merge_mlb_twin_games.py
- tests/test_discord_channel_probe.py
- tests/test_nfl_prop_one_read_per_game.py
- Game outcome target tests
- NCAAF live cadence and odds feed tests
- Mobile error states and load handling
- scripts/nfl_edge_gameline_rules.py
- Threshold review DDL tests
- tests/test_model_game_savepoint.py
- tests/test_system_health_checks.py
- tests/test_calibration_watch.py
- tests/test_promote_external.py
- Local store cache and NFL prop shape simulation
- tests/test_pipeline_report_rollback.py
- NBA results Postgres store
- NFL pick monitor game id tests
- Failure alerter fake-connection tests
- Pipeline watch and burn alerts
- Player news ingestor tests
- tests/test_sbr_loader.py
- Mobile theme, parlays and sportsbook links
- Score off any book line tests
- tests/test_nhl_three_way_lookahead.py
- Prop lookahead window tests
- tests/test_system_health_checks.py
- tests/test_score_when_lines_open.py
- NHL blocked shots settlement tests
- Monitoring server tests
- tests/test_best_line_live.py
- tests/test_sbr_loader.py
- NBA injury report scope dates
- NBA prop window plan tests
- MLB in-play game state alignment
- tests/test_nfl_props.py
- NFL wind card book filter tests
- Prop no-bet row survival tests
- Mobile bankroll storage
- NHL opening night goalie tests
- tests/test_void_picks.py
- tests/test_sbr_loader.py
- scripts/mlb_bet_record_audit.py
- Discord void notice ledger tests
- Multi-book odds pregame cutoff tests
- NCAAF gameday worker and ESPN feed
- NHL blocked shots card tests
- tests/test_scorer.py
- tests/test_system_health_checks.py
- tests/test_sbr_loader.py
- Odds API credit budget
- tests/test_daily_retry.py
- NFL prop backtest model and universe rate
- Feature matrix dtypes and line sweeps
- Feature map tests
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
- NFL odds pulls and live prop assessment
- Live quote score clock
- Voided pick, restate and X results job tests
- Multi-book fallback response tests
- Live scorer and pick insertion
- Player news ingestor
- mobile/src/hooks: verify_tracked_performance + useStakeSettings
- supabase/functions/revenuecat-webhook/index.ts
- supabase/functions/whop-webhook/index.ts
- tests/test_model_quality.py
- tests/test_nfl_props.py
- data/ingestors/live_game_state_poller.py
- tests/test_sbr_loader.py
- NHL as-of lookup tests
- NFL live game state math
- Scorer confidence tier and pick label tests
- NFL prop count and yardage distribution tests
- Best line sweep tests
- NFL prop odds game matching tests
- NBA injury report PDF parser
- tests/test_nfl_props.py
- tests/test_nhl_three_way_lookahead.py
- NFL live score distribution and calibration
- NBA prop market roster resolver
- Signal publish-on-write tests
- NBA injury report slot time and URL
- Mobile bankroll hook
- Mobile entitlement and subscription hooks
- tests/test_game_market_gate.py
- tests/test_system_health_checks.py
- NHL blocked shots player identity tests
- Health pregame prices fake connection
- tests/test_score_when_lines_open.py
- tests/test_score_when_lines_open.py
- tests/test_score_when_lines_open.py
- tests/test_system_health_checks.py
- tests/test_pick_integrity.py
- Calibration agent scheduler probe tests
- NCAAF FBS registry and refusal claims
- tests/test_score_when_lines_open.py
- tests/test_record_one_pick_per_event.py
- NFL backup snaps fake cursor
- tests/test_nfl_scored_rows.py
- NCAAF alias scores fake cursor
- Umpire feature drop declaration tests
- tests/test_weather_lookahead.py
- NHL season label tests
- nfl/live_model/tests: test_props + props
- MLB public fade empty connection
- tests/test_wnba_prop_market.py
- tests/test_nfl_scored_rows.py
- NHL derivative totals model
- Mobile player log and matchup stats
- Global EV floor and NHL totals tests
- tests/test_nhl_props.py
- Discord notifier, void notices and price bound tests
- NHL blocked shots prop settlement tests
- tests/test_recap_retries_a_skipped_day.py
- NCAAF feature engine test database
- NBA injury report fake cursor
- Void picks refusal tests
- NHL hollow team row test
- SQLite schema split tests
- NFL prop market rule and card
- Model trainer and research CLI scripts
- tests/test_f5_any_book_line.py
- tests/test_ncaaf_prop_odds.py
- NFL prop model and player row parsing tests
- tests/test_ncaaf_pbp_store.py
- tests/test_heartbeat_watchdog.py
- Game injury veto gate and tests
- models: nhl_prop_blocked_shots + nhl_prop_blocked_shots_backtest
- Publish key identity fake connection
- Pipeline run ledger
- scripts/nfl_edge_halftime_oos.py
- NCAAF slug and orientation helpers
- scripts/nfl_edge_live_rush_pace.py
- NBA prop projection tests
- Mobile live segment wiring tests
- tests/test_prop_calibrated_decision.py
- ncaaf_live/tests/test_pregame_calibration.py
- Direct sportsbook feeds and freshness probes
- tests/test_mobile_line_movement.py
- tests/test_live_calibration.py
- Push deep link and mobile player detail tests
- tests/test_score_off_any_book_line.py
- NHL lab summaries and early-season blend
- tests/test_ncaaf_live_notify.py
- monitoring/store.py
- tests/test_settled_record_is_immutable.py
- features/golf_feature_engine.py
- ncaaf_live/tests/test_states.py
- tests/test_bovada_feed.py
- tests/test_market_movement.py
- tests/test_ncaaf_cross_book_opener.py
- NFL in-play edge study 2025 and devig
- tests/test_health_pregame_prices_current.py
- NBA prop projection model
- scripts/nfl_edge_extreme_props.py
- scripts/nfl_edge_settlement.py
- X publisher
- tests/test_agents_contract.py
- Historical backfill and sub-10s live path tests
- Position vs opponent tests
- WNBA results ingestor parsers
- Daily pipeline runner and push notifier
- NFL in-play prop flow backtests
- NBA box score enrichment
- NHL stats ingestor
- Prop box score backfill
- Push notifier and tickets
- Discord units convention tests
- NFL stake sizing and EV backtest
- nfl/live_model/tests/test_flow.py
- tests/test_decide_on_calibrated.py
- NBA prop projection lab
- NFL backfill resilience tests
- tests/test_nfl_rule_2026_track.py
- tests/test_model_artifacts_load.py
- scripts/game_line_market_sweep.py
- Market coverage probe tests
- tests/test_pass_instrumentation.py
- tests/test_db_adapt_sql.py
- Calibration apply and live sweep
- tests/test_model_calibration_agent.py
- tests/test_mobile_contrast_tokens.py
- NBA stats ingestor
- Probability calibration fit and schema
- Mobile bankroll card
- NFL prop feature engine
- MLB prop market tests
- tests/test_live_inning_gate_replay.py
- NFL edge studies: luck gap and Wong teasers
- Live count tail probability tests
- Free pick cheaper book tests
- tests/test_nfl_live_leader_state.py
- tests/test_ncaaf_qb_ingestor.py
- NBA derivative market lab
- NBA prop model verification script
- NFL in-play edge study 2024
- Mobile pick category tests
- NCAAF feature engine tests
- Discord price bound tests
- nfl/live_model/tests/test_rush_attempt_pace.py
- tests/test_ncaaf_game_identity.py
- data/ingestors/ncaaf_inplay_history.py
- MLB and WNBA stats ingestors and pitcher rebuild
- data/ingestors/nhl_boxscore.py
- scripts/mlb_total_public_fade_topk.py
- NFL wind card and opener sweep scripts
- NFL player stats ingestor tests
- tests/test_live_game_features.py
- tests/test_ncaaf_totals_regression.py
- UFC feature engine and tests
- Mobile pick CTA, NFL import and wind stake tests
- tests/test_best_line_sweep.py
- NCAAF in-play history backtest
- tests/test_ncaaf_qb_features.py
- tests/test_line_clv.py
- tests/test_mobile_team_detail.py
- NBA ESPN box score parser
- NBA injury report garbled row tests
- NCAAF play-by-play state builder
- Kalshi ladder recording and prop ingestor tests
- tests/test_model_calibration_check.py
- tests/test_ncaaf_player_stats_ingestor.py
- Public read access grants
- First pitch time trust tests
- UFC stats ingestor and dashboard app
- scripts/nfl_edge_kalshi.py
- scripts/nfl_live_prop_feasibility.py
- tests/test_context_budget.py
- tests/test_player_h2h_stat_values_migration.py
- tests/test_retired_models.py
- NBA schedule features
- Best line threshold sweep analysis
- Latest line state and Citadel migration cluster tests
- tests/test_live_record_start_views.py
- tests/test_model_quality.py
- NBA prop window scheduling tests
- tests/test_api_call_rollup.py
- nfl/models/opener_spread.py
- NHL prop backtest and combined cap
- tests/test_live_slate_midnight.py
- tests/test_nfl_wind_fire_window.py
- College football data parsers
- tests/test_public_betting_ingestor.py
- NFL live backtest harness replay
- tests/test_service_role_split.py
- tests/test_http_timeout_floor.py
- NCAAF totals lead and consensus gate
- scripts/nfl_edge_cache.py
- Paused model assessment tests
- tests/test_nfl_injury_ingest.py
- NHL prop odds alternate line tests
- Live honest cut script
- Injury fetch speed and cache tests
- NBA props model core tests
- tests/test_config.py
- Kalshi game market recorder
- Database URL doctor tests
- tests/test_mlb_pbp_ingestor.py
- UFC fighter name resolution
- EV floor and cut replay sweeps
- UFC CSV fight loader
- tests/test_team_stats_asof_invariants.py
- NCAAF ESPN feed summary state
- Refresh pass step ordering tests
- CFBD verification script
- UFC etag cache tests
- NFL live remaining-score engine training
- tests/test_mobile_threshold_parity.py
- NFL live prop assessment script
- tests/test_nhl_derivative_odds_job.py
- tests/test_track_record_views.py
- tests/test_weekly_catch_up.py
- tests/test_live_game_state_poller.py
- Discord restate signal tests
- NFL Kalshi fetch and price floor grid
- CLV card price taken tests
- NFL live leader model tests
- NFL wind edge studies
- Mobile paused catalog tests
- NFL live prop rule studies
- tests/test_mobile_player_stat_groups.py
- Mobile sport filter tests
- tests/test_promote_calibration_job.py
- tests/test_cfbd_snapshot_leakage.py
- Mobile accessibility verify tests
- tests/test_nfl_prop_thresholds.py
- tests/test_nhl_research_job.py
- tests/test_settlement_timing.py
- tracking/model_quality.py
- NFL weather cache import
- DataGolf ingestor and NHL SBR archive
- Paused rows, prop lead ceiling and NHL regulation tests
- First pitch guard tests
- NFL odds cache import to Supabase
- tests/test_health_check_observe.py
- CFBD team game stats parsing tests
- Health check deliverability tests
- tests/test_pick_lock_is_on_picks.py
- Slate concentration and fade risk checks
- tests/test_team_stats_asof_invariants.py
- NFL halftime edge study
- supabase/functions/discord-link/index.ts
- tests/test_nfl_prop_clv.py
- tests/test_prune_keeps_the_close.py
- tests/test_scoring_methods.py
- Mobile bankroll tests
- NCAAF outcome edge scan
- Live monitor dashboard cache and docs
- Worker job queue and CFBD ingestor
- scripts/ncaaf_search/situational_spots.py
- Threshold review worker-only tests
- Monitoring server tests
- nfl/scripts/backtest_opener.py
- MLB retrain freeze tests
- tests/test_latest_odds_views.py
- Multi-book odds tests
- NBA schedule ingestor and tests
- tests/test_nfl_prop_settle_name_fallback.py
- NFL recap waits for box scores tests
- tests/test_transaction_pooler.py
- tests/test_espn_nhl_probables.py
- Team stats as-of invariant tests
- NBA injury report slot dates
- Declared worker job validation tests
- supabase/functions/sharpsports/index.ts
- UFC fighter slug tests
- MLB game market and public fade cards
- tests/test_worker_deps.py
- Price floor and threshold sweep
- scheduler.py
- NFL stale card file tests
- scripts/ncaaf_search/weather_totals.py
- Published record reconciliation tests
- tests/test_mobile_stat_labels_match_the_server.py
- tests/test_ncaaf_fcs_visitor_names_migration.py
- tests/test_nfl_prop_unstarted_clear.py
- NBA, NCAAF and NFL research labs
- NFL live moneyline and total pricing tests
- Trainer no-register tests
- tests/test_savant_freshness.py
- tests/test_scorer_nfl_prop_like_escape.py
- NFL live leader config tests
- NFL prop over lean study
- CLV no-vig capture tests
- scripts/live_feed_probe.py
- NCAAF steam lag study
- tests/test_clear_unauthorized_auto_pauses_migration.py
- Prop ladder, picks unique row and as-of verify tests
- tests/test_ncaaf_se_louisiana_alias_migration.py
- tests/test_overnight_polling.py
- tests/test_revoke_remaining_grants.py
- tests/test_live_slate_midnight.py
- tests/test_nhl_stats_ingestor.py
- NHL totals lab
- ncaaf_live/tests/test_cfbd_yardline.py
- tests/test_claude_rules_split.py
- tests/test_db_setup.py
- tests/test_dedupe_opening_signals.py
- tests/test_every_named_book_is_fetched.py
- tests/test_pbp_backfill_resilience.py
- Database URL and SCRAM probes
- mobile/scripts/verify_stats_filter_ux.ts
- NFL wind forecast validation
- MLB prop market sweep
- NCAAF quarterback ablation study
- tests/test_game_log_backfill_skip.py
- NCAAF line move spots
- NFL live prop state builder
- tests/test_prompt_reads_thresholds.py
- tests/test_system_health_meta_steps.py
- NBA period scores ingestor and tests
- scripts/render_brand_icons.py
- NFL prop lean concentration study
- Dashboard rule model tests
- supabase/functions/stripe-webhook/index.ts
- tests/test_drop_voided_nfl_wind_opening_signals_migration.py
- tests/test_mobile_neutral_signal_label.py
- Live model holdout comparison script
- NFL prop opening signal cleanup tests
- tests/test_scorer_commits_per_game.py
- NFL live gaussian copula tests
- NCAAF structure scan
- tests/test_live_game_state_poller.py
- NFL prop tick tests
- tests: test_wnba_availability + wnba_availability
- NCAAF venue feature tests
- UFC fighter page parser
- NFL prop two-sharps study and offset docs
- supabase/functions/sharpsports-webhook: index + index
- NCAAF qualify at DraftKings tests
- supabase/functions/stripe-checkout/index.ts
- tests/test_book_list_budget.py
- Live CV grouping tests
- NBA game market lab
- Mobile NHL look-ahead window tests
- NFL prop week-one candidate pool tests
- SBR historical odds loader
- NBA injury report player matching
- NFL live backtest states
- mobile/scripts/verify_a11y.ts
- NFL wind lead calibration
- Eastern game date tests
- NCAAF weather backfill
- tests/test_demote_ncaaf_over_under_platt.py
- NBA prop window fetch tests
- tests/test_discord_post_one_pick_migration.py
- tests/test_game_scorer_spares_nfl_props.py
- Calibration agent sweep tests
- NFL live model backtest harness
- tests/test_mobile_ota_self_update.py
- tracking/model_quality.py
- MLB totals public fade model
- tests/test_team_board_commence_bound.py
- NFL prop book sweep
- UFC stats page parsers
- Calibration eligibility notes
- Bookmaker whitelist tests
- NBA injury report retry tests
- Eastern game date tests
- NCAAF weather forecast backfill
- NCAAF play-by-play puller
- Scorer keeps off-DraftKings priced bets tests
- NFL odds table builder
- NFL prop lean gradient study
- tests: test_db_url_doctor + test_envfile_fallback
- Parlay leg correlation estimates
- NFL research backup and restore script
- Board markets lock-down tests
- View migration apply and lock retry
- Market handicap features
- tests/test_team_stats_asof_invariants.py
- MLB over/under retrain sweep tests
- tests/test_team_stats_asof_invariants.py
- tests/test_team_stats_asof_invariants.py
- tests/test_weekly_catch_up.py
- NCAAF travel geography features
- NHL goalie line helpers
- Team stats rebuild and verify
- NFL opener calibration
- tests/test_live_orchestrator.py
- Live money no record-only tests
- tests/test_team_stats_asof_invariants.py
- Mobile accessibility verify script
- tests/test_market_handicap.py
- mobile/scripts/verify_a11y.ts
- mobile/scripts/verify_a11y.ts
- Strategy analysis report
- NBA injury report slot naming
- NBA injury report name and team parsing
- Prop CLV and SQL escaping tests
- mobile/scripts/verify_a11y.ts
- scripts: ncaaf_margin_eval + test_ncaaf_margin_eval
- NHL opening week rekey script
- Model pause helper tests
- Team stats verify alias test
- ncaaf_live/tests/test_serve.py
- SQLite test database fixture
- Discord void publish worker job
- Mobile error state and stat segment tests
- Discord free pick integrity tests
- Stale pause flag detection tests
- Real pause not stale test
- NCAAF CFBD line bookmaker label
- NBA prop market slate test
- NBA prop market read window test
- NCAAF feature assembly
- Pregame price fingerprint
- Discord signals publish worker job
- scripts/nfl_edge_preregistered_2026.py
- MLB prop backfill anchoring tests
- Calibration probe staleness test
- Odds prune keep-days tests
- NBA prop projection posting cap test
- NHL prop alternate line gate tests
- Pause table fails open test
- tests: test_player_positions + player_positions_ingestor
- NFL backup snaps no-psycopg fixture
- Threshold review milestone
- Threshold review kill switch
- NBA prop market tests
- mobile/scripts/verify_a11y.ts
- NBA prop model lab
- tests/test_mlb_total_public_fade.py
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
- docs/rules_evidence.md
- docs: probability_calibration + nfl_rule_2026_track
- NFL game lines model write-up
- Model quality and MLB docs
- nfl/live_model/README.md
- docs: followups + clv
- docs: best_line + config_topology
- docs/cloud_worker.md
- docs/history: learnings + build_state
- monitoring/static/dashboard.html
- docs/sports/nhl.md
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
- .claude/rules: CLAUDE + config-topology
- .github/workflows: CLAUDE + mobile-build
- docs/agents_contract.md
- .claude/rules/operations.md
- docs/live_odds_freshness.md
- NFL in-play edge search findings
- mobile/docs/UX_REVIEW.md
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
- In-play backtest and volume efficiency docs
- Monitoring and model state docs
- .claude/rules/frontend.md
- docs/health_checks.md
- docs/retrain_2026_plan.md
- docs/reviews/2026-09-07-nfl-props-deep-dive.md
- docs/market_coverage.md
- (root): pr-ci + requirements
- docs/nfl_props_model.md
- docs/game_injury_gate.md
- NFL wind totals runbook and staking
- mobile/docs/BILLING.md
- docs/testing.md
- CLAUDE.md
- NFL opener sharp-vs-soft findings

## God Nodes (most connected - your core abstractions)
1. `get_connection()` - 591 edges
2. `DBConnection` - 309 edges
3. `react` - 139 edges
4. `StatsScreen()` - 136 edges
5. `react-native` - 98 edges
6. `colors` - 84 edges
7. `font` - 78 edges
8. `PlayerStatsScreen()` - 75 edges
9. `norm_player_name()` - 75 edges
10. `radii` - 75 edges

## Surprising Connections (you probably didn't know these)
- `run_nba_prop_window()` --references--> `4.3 Player props — one rule ships`  [INFERRED]
  scheduler.py → docs/nba_models_2026.md
- `odds()` --references--> `2. Data used (all in Supabase)`  [INFERRED]
  tests/test_latest_line_state.py → docs/nba_models_2026.md
- `odds()` --references--> `3. The market grid`  [INFERRED]
  tests/test_latest_line_state.py → docs/nba_models_2026.md
- `Gate 1: win probability Brier 0.1654 PASS vs 0.20` --semantically_similar_to--> `Gate 1: win probability Brier 0.115 PASS vs 0.20`  [INFERRED] [semantically similar]
  nfl/live_model/README.md → ncaaf_live/README.md
- `Gate 2: total quantile coverage 1.26pp PASS vs 2.0pp` --semantically_similar_to--> `Gate 2: total shape 2.60pp FAIL vs 2.0pp`  [INFERRED] [semantically similar]
  nfl/live_model/README.md → ncaaf_live/README.md

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

## Communities (877 total, 196 thin omitted)

### Community 0 - "ESPN injury ingestor"
Cohesion: 0.07
Nodes (20): TestCoreTeamsFallback, _athlete_name(), _compute_return_ramp(), _espn_team_ids(), fetch_espn_injuries(), _fetch_espn_team_injuries(), fetch_mlb_transactions(), _fetch_nba_espn_team_ids() (+12 more)

### Community 1 - "Mobile stats board"
Cohesion: 0.01
Nodes (317): P, TouchSet, PlayerPropQuote, errorKind, gameStatus, PropLineLike, StatGroup, PricedPlayer (+309 more)

### Community 10 - "NFL prop market stack and devig"
Cohesion: 0.04
Nodes (45): TestNaNIsAbsent, pregame_cutoff_sql(), devig(), implied(), card(), load_quotes(), closing_prices(), devig() (+37 more)

### Community 104 - "Record correction and full record posts"
Cohesion: 0.04
Nodes (49): LedgerUnread, Conn, Ledger, _Result, delete_custom_record_post(), _jump(), _pin(), _place() (+41 more)

### Community 109 - "nfl_live_leader/state.py"
Cohesion: 0.12
Nodes (18): CoreClient, EventMeta, _abbr(), game_seconds(), https(), _int(), is_admin_play(), is_conversion_play() (+10 more)

### Community 113 - "tests/test_nfl_live_leader_gameday.py"
Cohesion: 0.05
Nodes (32): FakeClient, FakeClock, FakeConn, FakeFeed, _Rows, art(), live_state(), quote_payload() (+24 more)

### Community 114 - "nfl_live_leader/gameday.py"
Cohesion: 0.05
Nodes (32): _Unset, Cadence, GameContext, LiveOddsFeed, Quote, LiveState, release_read(), parse_book_ts() (+24 more)

### Community 115 - "tests/test_calibration_promotion.py"
Cohesion: 0.07
Nodes (26): FakeConn, eligibility_clause(), load_calibrations(), maps_materially_differ(), promote(), _payload(), _row(), test_a_broken_table_is_identity_maps_not_an_exception() (+18 more)

### Community 118 - "tests/test_recap_restatement.py"
Cohesion: 0.08
Nodes (16): _Conn, test_a_restated_recap_is_labelled_and_says_why(), _resp(), test_a_404_is_an_answer_not_a_retry(), test_a_persistent_403_still_raises_after_the_last_attempt(), test_a_recap_whose_count_merely_drifted_is_not_due(), test_a_recap_with_a_late_settlement_is_due(), test_a_transient_403_is_retried_and_the_second_answer_is_used() (+8 more)

### Community 12 - "Mobile pick filters and sorting"
Cohesion: 0.03
Nodes (115): P, ActivePill, Props, Props, DateOption, DayRow, SelectableGame, modelCategory (+107 more)

### Community 120 - "tests/test_ncaaf_alias_scores.py"
Cohesion: 0.10
Nodes (28): _FakeConn, alias_score_updates(), _date_or_none(), mirror_scores_to_alias_rows(), _cfbd(), _row(), test_a_bare_substring_is_not_an_extension(), test_a_daytime_game_has_no_duplicate_and_is_untouched() (+20 more)

### Community 121 - "tests/test_prop_alternate_lines.py"
Cohesion: 0.06
Nodes (29): _Conn, _Resp, _market_chunks(), alt_markets_due(), _ou(), _parse(), test_a_422_retries_without_the_alternates_before_going_dk_only(), fake_get() (+21 more)

### Community 122 - "Game scorer core and NCAAF board visibility"
Cohesion: 0.03
Nodes (71): TestMissingStarterGate, load_sport_injury_index(), _anchored_probability(), _apply_game_injury_gate(), _run(), _apply_game_market_gate(), _apply_no_signal(), _best_game_price_one() (+63 more)

### Community 123 - "tests/test_backtester.py"
Cohesion: 0.07
Nodes (9): TestCalibrationError, TestComputeBacktestSummary, TestEvaluateResult, TestGoLiveGateConstants, TestIterSides, _calibration_error(), compute_backtest_summary(), _evaluate_result() (+1 more)

### Community 124 - "scripts: nhl_prop_backtest + nhl_prop_ev_lab"
Cohesion: 0.08
Nodes (17): TestRegimeOrder, books(), sides(), best_per_player(), blocked_sides(), engine_sides(), history(), pool() (+9 more)

### Community 125 - "nfl/live_model/feeds/odds_live.py"
Cohesion: 0.07
Nodes (18): CreditBudgetExceeded, CreditMeter, LiveOddsClient, Quote, JsonlRecorder, best_price(), parse_events(), _parse_ts() (+10 more)

### Community 127 - "NHL prop cards and cross-model publish"
Cohesion: 0.07
Nodes (20): TestFourNhlPropBetsANight, bs_implied(), candidates(), identities(), latest_quotes(), main(), publish(), render() (+12 more)

### Community 129 - "NBA prop market lab"
Cohesion: 0.08
Nodes (45): NBTable, name_resemblance(), add_units(), assemble(), best_per_key(), boot_ci(), build_quotes(), candidates_from() (+37 more)

### Community 13 - "Discord signal notifier tests"
Cohesion: 0.02
Nodes (86): _FakeConn, _FakeResult, _Resp, _StampConn, _cand(), _et_now_iso(), _freeze_now(), _live_row() (+78 more)

### Community 131 - "nfl/live_model/tests/test_backup_snaps.py"
Cohesion: 0.12
Nodes (20): _FakeConn, back_up(), digest(), _flush(), iter_files(), main(), _mb(), psycopg2_bytes() (+12 more)

### Community 135 - "mobile/scripts: verify_book_links + verify_betslip_combine"
Cohesion: 0.06
Nodes (37): betslipCombineKind, combineBetMgm(), combineBetslipLinks(), combineCaesars(), combineDraftKings(), combineEspnBet(), combineFanDuel(), fanDuelPairs() (+29 more)

### Community 137 - "NBA injury report fixture pull tests"
Cohesion: 0.16
Nodes (10): _Conn, _PdfFetcher, content_hash(), pull_one(), _content_of_fixture(), test_a_changed_report_stores_its_rows(), test_a_garbled_report_writes_its_ledger_row_and_no_rows(), test_a_repeat_of_a_repeat_points_at_the_report_that_holds_the_rows() (+2 more)

### Community 138 - "tests/test_paused_keeps_real_verdict.py"
Cohesion: 0.05
Nodes (40): _Capture, _prop_bets_today(), _bet(), _bodies(), _code(), _dk(), _fn(), _game() (+32 more)

### Community 14 - "Mobile pick queries, types and custom filters"
Cohesion: 0.02
Nodes (228): Props, Props, FighterSide, Props, Props, PropContext, BacktestPickRow, CustomBacktestPickRow (+220 more)

### Community 140 - "mobile/scripts/verify_contrast_tokens.ts"
Cohesion: 0.05
Nodes (40): Pair, code(), lum(), noGreen(), over(), ratio(), read(), readUtf8() (+32 more)

### Community 141 - "models/nhl_props.py"
Cohesion: 0.10
Nodes (25): Spec, _attach_teams(), build_frame(), build_goalie_frame(), build_skater_frame(), _ew(), expected_value(), fit() (+17 more)

### Community 143 - "Pick lock after settlement tests"
Cohesion: 0.08
Nodes (22): _SqliteShim, conn(), _game(), _pick(), _survivors(), test_a_bet_is_never_dropped_for_an_earlier_no_signal(), test_a_dead_zone_prop_row_locks_too(), test_a_final_game_is_not_a_scoring_target() (+14 more)

### Community 144 - "NFL weather ingest and forecast persistence"
Cohesion: 0.11
Nodes (16): OpenMeteoError, fetch_era5(), fetch_issued_forecasts(), fetch_live_forecast(), _frame(), _get(), _issued_columns(), _issued_from_supabase() (+8 more)

### Community 146 - "tests/test_mlb_game_market.py"
Cohesion: 0.07
Nodes (28): GameMarketBet, _SlateConn, find_spread_bets(), find_total_bets(), _gap_seconds(), _is_runline(), publish_enabled(), pick_rows() (+20 more)

### Community 149 - "X and Discord results recap publishers"
Cohesion: 0.03
Nodes (46): _Conn, build_parser(), _date_is_over(), main(), post_backfill(), test_a_day_that_is_not_over_is_refused(), test_apply_calls_both_notifiers_for_that_date(), test_dry_run_is_the_default_and_posts_nothing() (+38 more)

### Community 150 - "Threshold review run tests"
Cohesion: 0.11
Nodes (17): _Conn, _slate(), test_a_losing_model_with_enough_bets_is_flagged(), test_a_losing_model_with_too_few_bets_is_left_alone(), test_a_milestone_fires_only_once(), test_a_model_paused_in_config_is_not_reported_again(), test_a_profitable_model_is_never_touched(), test_an_already_paused_model_is_not_flagged_again() (+9 more)

### Community 152 - "Idle read transaction tests"
Cohesion: 0.07
Nodes (17): ViewMigrationResult, _Rec, _credits_used_today(), apply_view_migrations(), _flat(), test_a_lock_timeout_fails_that_file_and_the_next_still_runs(), test_a_locked_bet_releases_the_lock_check(), test_a_quiet_tick_rolls_the_read_back() (+9 more)

### Community 155 - "tests/test_prop_box_scores.py"
Cohesion: 0.09
Nodes (18): GradeConn, ScriptConn, ensure_prop_box_scores(), missing_prop_games(), _pick(), test_a_logged_game_is_not_fetched_and_a_goalie_gap_is(), test_a_non_timeout_prop_error_rolls_back_and_raises(), test_a_probe_error_that_is_not_a_timeout_raises_after_rollback() (+10 more)

### Community 156 - "MLB totals public fade model"
Cohesion: 0.12
Nodes (19): PublicFadeBet, composite_score(), estimated_edge(), rank_score(), select_top_k(), _key(), ticket_money_gap(), pick_rows() (+11 more)

### Community 158 - "Best line and best-price decision tests"
Cohesion: 0.03
Nodes (53): FakeConn, TwoOrientationConn, FakeConn, _best_game_price(), _best_of(), _best_prop_price(), _same_line(), emit() (+45 more)

### Community 162 - "tests/test_ddl_guard.py"
Cohesion: 0.06
Nodes (19): GuardConn, _ddl(), _dk_direct_feed(), _is_guarded(), _job_queue(), _live_calibration(), _modules_with_write_time_ddl(), _run_ledger() (+11 more)

### Community 163 - "tests/test_job_queue.py"
Cohesion: 0.08
Nodes (18): _Conn, _DedupeConn, _fake(), test_a_busy_queue_claims_nothing(), fetchone(), test_a_failing_job_is_requeued_until_the_attempt_cap(), _boom(), test_a_final_failure_is_announced() (+10 more)

### Community 164 - "tests/test_nfl_opener.py"
Cohesion: 0.15
Nodes (7): TestFreshNumberLabel, TestHeldMinutes, _giants_board(), _giants_prior_at_2129(), _giants_sched(), _obs(), _ts()

### Community 167 - "scripts/nfl_preflight.py"
Cohesion: 0.12
Nodes (20): TestRealSchema, TestSplitter, _load_postgres_schema(), _split_sql_statements(), check(), check_cards_run(), check_config_gates(), check_cost() (+12 more)

### Community 169 - "Mobile sign-in and auth"
Cohesion: 0.11
Nodes (37): AuthState, AuthStatus, useAuth, AuthCallback, AuthDisabledError, AuthProvider, Nav, applySession() (+29 more)

### Community 170 - "Mobile billing config and verify script"
Cohesion: 0.09
Nodes (29): BillingRail, Plan, planFor(), describeSubscription(), isEntitled(), isPlanKey(), perMonth(), trialDaysLeft() (+21 more)

### Community 174 - "tests/test_publisher_lock.py"
Cohesion: 0.07
Nodes (17): _Conn, _Result, _clear_locks(), _no_prod_threshold_sync(), _signal_row(), test_a_connection_that_cannot_lock_still_publishes(), test_an_exception_mid_publish_does_not_wedge_every_later_pass(), test_every_signal_publisher_takes_the_lock() (+9 more)

### Community 175 - "tests/test_dk_direct_feed.py"
Cohesion: 0.09
Nodes (22): _Conn, _game_id_for(), _row_for(), _seen_key(), _rec(), test_a_line_move_is_a_new_quote(), test_a_market_we_do_not_understand_is_dropped_not_guessed(), test_a_price_move_is_a_new_quote() (+14 more)

### Community 177 - "tests/test_credit_budget.py"
Cohesion: 0.09
Nodes (22): _Conn, daily_burn(), latest_remaining(), plan_credit_budget(), _burn_conn(), _plan(), test_a_billing_reset_is_not_a_refund(), test_a_call_is_billed_at_what_the_api_says_it_cost() (+14 more)

### Community 18 - "Mobile thresholds and daily results"
Cohesion: 0.02
Nodes (200): Case, EquityPoint, Props, CustomModelStats, Acc, DailyResults, DayGameSummary, ModelDayStats (+192 more)

### Community 180 - "NHL market-anchored moneyline model"
Cohesion: 0.05
Nodes (31): OffsetLogit, _Fixed, _GamesConn, _add_rating(), build_inputs(), choose_C(), decision_window(), fit() (+23 more)

### Community 186 - "scripts/nfl_wind_publisher.py"
Cohesion: 0.09
Nodes (15): _LockConn, TestNoneRowNeverLocks, _changed(), _clear_scored_row(), _flush_board_safe(), _flush_snapshots_safe(), latest_eval_rows(), _lock_model() (+7 more)

### Community 189 - "Settlement and self-heal tests"
Cohesion: 0.05
Nodes (41): _SqliteShim, _FakeStatsapi, _SqliteShim, _box(), conn(), _game(), _live_bet(), raw() (+33 more)

### Community 19 - "Live game state and trigger pollers"
Cohesion: 0.06
Nodes (30): Pick, _fetch_live_feed(), _insert_state(), _insert_triggers(), _load_last_state(), poll_forever(), poll_once(), _poll_one_game() (+22 more)

### Community 193 - "tests/test_first_signal_repair.py"
Cohesion: 0.08
Nodes (27): _Conn, _VoidedConn, step_restore_first_signals(), patch_conn(), _make(), _sql_of(), test_a_lane_already_holding_its_first_bet_is_untouched(), test_a_lane_with_no_sibling_still_restores() (+19 more)

### Community 196 - "tests/test_ungraded_model_performance.py"
Cohesion: 0.08
Nodes (12): FakeConn, test_perf_reads_the_matview_not_the_expensive_view(), test_roster_reports_a_registered_but_untrained_model(), _second_arm(), _sql(), test_a_fully_unpriced_recovered_model_reports_no_roi(), test_a_recovered_row_still_reports_roi_over_the_priced_bets(), test_both_arms_stay_inside_the_settled_bet_gate() (+4 more)

### Community 198 - "mobile/scripts/verify_push.ts"
Cohesion: 0.08
Nodes (30): PushState, ForcedOnlyReason, PushDiagnosis, PushFailureReason, TestPushResult, reasonOf(), diagnosePushError(), errorText() (+22 more)

### Community 199 - "Prop price pregame cutoff tests"
Cohesion: 0.08
Nodes (14): _StubConn, _latest_dk_prop_row(), _assigned_from(), _prop_scorers(), test_every_scorer_call_site_passes_a_pregame_cutoff(), test_get_prop_dk_odds_forwards_the_cutoff(), test_in_play_snapshots_are_excluded_unconditionally(), test_it_fails_open_when_commence_time_is_missing() (+6 more)

### Community 2 - "Mobile markets and formatting"
Cohesion: 0.02
Nodes (296): Row, Props, Props, Props, IoniconName, Props, Props, clvBetQuote (+288 more)

### Community 200 - "NFL prop odds loading tests"
Cohesion: 0.06
Nodes (22): _Conn, _Cur, TestPropOddsLoader, _Conn, _Cur, _fetch_slice(), _iter_prop_rows(), load_nfl_prop_odds() (+14 more)

### Community 203 - "tests/test_nhl_asof.py"
Cohesion: 0.12
Nodes (4): GoalieBook, TestGoalieAsOf, TestReturningStarterIsNamedFromTheLog, _g()

### Community 207 - "scripts/ncaaf_search: dataset + starter_out"
Cohesion: 0.10
Nodes (16): LabelSet, build_label_set(), _fetch_lines(), _fetch_raw(), opener_coverage(), _pick_provider(), provider_continuity(), main() (+8 more)

### Community 208 - "tests: test_deploy_checks + deploy_checks"
Cohesion: 0.07
Nodes (18): _Conn, test_a_declared_job_carries_its_run_after(), test_a_failing_check_raises_so_the_queue_announces_it(), test_a_job_can_only_name_a_registered_check(), test_enqueue_rejects_a_naive_run_after(), test_enqueue_stores_run_after(), test_every_check_is_read_only(), test_the_claim_waits_for_run_after() (+10 more)

### Community 209 - "data/ingestors/nfl_inplay_history.py"
Cohesion: 0.16
Nodes (22): Budget, buy_halftime(), buy_inplay(), events_for(), _floor5(), _get(), halftime_requests(), halftime_windows() (+14 more)

### Community 211 - "Mobile bankroll store and verify script"
Cohesion: 0.09
Nodes (31): BankrollCheck, BankrollCommit, BankrollPatch, BankrollRead, NumberSeparators, Part, walk(), deviceSeparators() (+23 more)

### Community 212 - "Probability calibration tests"
Cohesion: 0.04
Nodes (28): _FakeConn, _SchemaRecordingConn, _calibration_error_weighted(), calibration_metrics(), poisson_probability_metrics(), test_a_map_that_does_not_help_out_of_sample_is_not_applied(), test_a_map_that_helps_is_applied(), test_a_model_with_no_record_takes_the_pooled_correction() (+20 more)

### Community 214 - "NHL props per-game limit tests"
Cohesion: 0.16
Nodes (4): TestInsertOnce, TestTheLimitPerGame, limit_per_game(), publish()

### Community 217 - "NCAAF live engine pricing"
Cohesion: 0.07
Nodes (13): LiveEngine, american_to_prob(), devig_power(), expected_value(), _is_paused(), test_ev_floor_cannot_fire_without_a_price(), test_ev_floor_declines_a_qualifying_pick_that_is_priced_too_short(), test_ev_floor_only_tightens_and_never_touches_avoid() (+5 more)

### Community 218 - "Closing line value math"
Cohesion: 0.06
Nodes (28): _Conn, _Res, test_a_one_way_close_is_not_de_vigged(), test_a_worse_close_is_negative_and_equal_prices_are_zero(), test_devigging_the_taken_price_is_not_what_primary_does(), test_kalshi_close_is_not_de_vigged(), test_market_edge_devigs_only_the_close(), test_other_side_prices_include_the_draw_on_a_three_way() (+20 more)

### Community 22 - "NBA prop projection card"
Cohesion: 0.09
Nodes (28): ProjectionBet, step_nba_prop_project(), backfill_official(), decided_games(), ensure_tables(), espn_pulls(), espn_rows(), fill_espn_history() (+20 more)

### Community 220 - "tests/test_db_reconnect.py"
Cohesion: 0.09
Nodes (16): _Conn, _Cursor, _is_write(), _lost(), test_a_committed_transaction_is_clean_again(), test_a_lost_connection_with_uncommitted_writes_raises_connection_lost(), test_a_read_on_a_lost_connection_reconnects_and_retries(), test_a_statement_timeout_is_not_a_lost_connection() (+8 more)

### Community 222 - "NFL live prop tests and pass-attempt bias"
Cohesion: 0.09
Nodes (11): Read, blind_over_prob(), over_prob(), _pass_attempt_bias_allowed(), test_blind_arm_no_longer_asserts_a_rate(), test_restoring_a_bias_is_one_constant(), test_the_gates_are_checked_before_the_no_bias_decline(), test_the_interval_spans_zero_so_the_lane_declines_to_price() (+3 more)

### Community 223 - "tests/test_live_lock.py"
Cohesion: 0.13
Nodes (18): FakeConn, _Rows, _write_live_picks(), _locked_live_lanes(), _log_lines(), _pick(), test_a_locked_lane_still_says_so_and_names_the_lane(), test_all_lanes_locked_touches_nothing() (+10 more)

### Community 225 - "tests/test_refresh_retry.py"
Cohesion: 0.14
Nodes (23): RefreshRun, _decide(), _done(), _run(), test_a_failed_view_migration_fails_the_step(), test_a_pass_that_finished_with_failed_steps_ran_its_chain(), test_a_redeploy_between_passes_replaces_nothing(), test_a_restart_loop_does_not_buy_odds_on_every_boot() (+15 more)

### Community 226 - "NBA box score player name resolver"
Cohesion: 0.15
Nodes (9): PlayerResolver, build_dnp_rows(), build_log_rows(), fallback_id(), norm_player_name(), test_a_rookie_keeps_one_id_across_games(), test_the_fallback_cannot_collide_with_an_nba_id(), test_two_box_rows_never_share_an_id() (+1 more)

### Community 228 - "NBA results ingestor tests"
Cohesion: 0.09
Nodes (24): _Conn, _ESPN, FakeStore, _FixedNow, _game(), _resolver(), _run(), test_a_different_stored_score_is_never_overwritten() (+16 more)

### Community 230 - "tests/test_local_cache_is_additive.py"
Cohesion: 0.10
Nodes (13): _FakeConn, main(), _merge_with_cache(), _pull_odds(), _pull_seasoned(), _register_from_feature_engine(), cached(), _frame() (+5 more)

### Community 231 - "tests/test_calibration_check_coverage.py"
Cohesion: 0.11
Nodes (18): _Shim, _bet(), _calibration_results(), db(), _graded(), _make_db(), _only(), _promote() (+10 more)

### Community 233 - "tests/test_book_team_map.py"
Cohesion: 0.11
Nodes (15): _Conn, abbr_from_team_string(), resolve_game_id(), split_matchup(), test_a_non_mlb_sport_is_refused_rather_than_guessed(), test_a_string_with_no_at_sign_is_refused(), test_a_unique_game_resolves(), test_an_ambiguous_game_resolves_to_none() (+7 more)

### Community 234 - "tests/test_team_board_cache.py"
Cohesion: 0.08
Nodes (11): _Conn, _Cursor, refresh_team_board_cache(), team_board_pairs(), team_board_seasons(), _cols(), test_every_team_sport_gets_last_this_and_next_year(), test_one_failing_pair_does_not_stop_the_rest() (+3 more)

### Community 236 - "mobile/src/lib: verify_discord_link + discordHelpers"
Cohesion: 0.11
Nodes (34): AccessState, useAccess, FunctionResponse, LinkResult, AccessRow, DiscordCallback, DiscordLinkDisabledError, accessEnabled() (+26 more)

### Community 239 - "tests/test_nfl_poll_fast_silence.py"
Cohesion: 0.11
Nodes (15): FakeConn, publish_board(), _append_board(), _body(), _row(), _sent(), _setup(), test_a_half_written_last_row_waits_for_the_next_tick() (+7 more)

### Community 24 - "NHL market lab and live artifact grading"
Cohesion: 0.05
Nodes (61): OffsetLogit, add_rating(), build(), bets(), line(), main(), goalie_frame(), grid() (+53 more)

### Community 241 - "Prop feature engine rows"
Cohesion: 0.05
Nodes (20): TestTrainingExcludesThemAndScoringDoesNot, _all_batter_rows(), _all_pitcher_rows(), _batter_rate(), _batter_rolling_avg(), _batter_savant(), _batter_season_avg(), _build_batter_row() (+12 more)

### Community 244 - "tests/test_weather_lookahead.py"
Cohesion: 0.09
Nodes (11): _Resp, TestTheHourIsTheGamesOwn, TestTheRequestCoversTheTargetHour, _celsius_to_f(), _fetch_open_meteo(), _game_hour_utc(), _target_hour_utc(), _utc_offset_from_lon() (+3 more)

### Community 245 - "tests/test_nhl_asof.py"
Cohesion: 0.11
Nodes (6): TeamBook, TestBlendedTeamInputs, TestTeamRatesAsOf, _r(), _t(), test_the_training_path_reads_nhl_odds_by_game_not_by_sport()

### Community 247 - "tests/test_dk_freshness_parse.py"
Cohesion: 0.12
Nodes (17): _FakeConn, _FakeResult, _american(), parse_dk_payload(), _store(), _payload(), test_a_half_priced_market_is_dropped_rather_than_half_recorded(), test_an_event_with_no_markets_yields_nothing_rather_than_raising() (+9 more)

### Community 248 - "tests/test_live_calibrated_decision.py"
Cohesion: 0.09
Nodes (15): RecordingConn, _cut(), _signal(), test_a_big_enough_claim_still_fires_after_calibration(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(), test_a_hot_live_model_no_longer_fires_the_marginal_bet(), test_a_live_model_is_read_out_of_picks_not_the_matview(), test_a_live_read_bounds_on_a_real_price() (+7 more)

### Community 249 - "models: slate_concentration + test_slate_concentration"
Cohesion: 0.15
Nodes (15): SlateConcentration, apply_slate_guard(), apply_slate_concentration_guard(), _attr(), _edge_of(), _is_bet(), measure_side_concentration(), _side_of() (+7 more)

### Community 25 - "NBA prop market publish tests"
Cohesion: 0.09
Nodes (16): NbaPropBet, _PublishConn, _SettleConn, pick_label(), pick_rows(), _bet(), _decision(), test_a_bet_at_draftkings_carries_no_best_columns() (+8 more)

### Community 251 - "View migration lock handling tests"
Cohesion: 0.07
Nodes (25): _Conn, _Deadlock, _LockTimeout, _StatementTimeout, _Syntax, execute(), _before(), _code() (+17 more)

### Community 254 - "Prop odds missing game tests"
Cohesion: 0.15
Nodes (4): FakeConn, _run(), test_event_with_no_games_row_is_skipped_and_others_still_insert(), test_fk_on_insert_does_not_unwrite_the_events_that_already_landed()

### Community 256 - "tests/test_ncaaf_search_features.py"
Cohesion: 0.07
Nodes (28): AdjRatings, blended_rating(), build_adjusted_ratings(), build_prior_season_ratings(), fit_opponent_adjustment(), load_fbs_membership(), load_team_games(), pool_fcs_opponents() (+20 more)

### Community 257 - "NCAAF opener strategy search"
Cohesion: 0.05
Nodes (40): FoldResult, features_for(), _apply_calibration(), exponential_recency_weights(), _logit(), make_ensemble(), fit_predict(), make_lgbm() (+32 more)

### Community 26 - "Mobile team detail and team stats"
Cohesion: 0.05
Nodes (93): Sport, NextGame, Section, TeamLineQuote, Tier, FormGame, FormSummary, headToHead (+85 more)

### Community 268 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.10
Nodes (8): TestBuildScoredRows, TestPickEmLabel, TestPreflightLockChecks, TestQualifyingRowIsNotANoneRow, _american_to_prob(), build_scored_rows(), _fmt_spread(), _num()

### Community 269 - "tests/test_cfbd_ingestor.py"
Cohesion: 0.07
Nodes (8): _GamesConn, _TeamsConn, test_ingest_games_retains_a_historical_utc_id_and_uses_et_for_a_new_row(), fake_get(), test_ingest_pulls_fbs_then_everyone_and_fbs_rows_win(), test_ingest_retries_everyone_without_a_year_if_the_season_filter_is_empty(), test_prior_context_tolerates_missing_talent_and_returning(), test_weekly_snapshot_build_aborts_on_failed_fetch()

### Community 27 - "Parlay builder and bet slip"
Cohesion: 0.02
Nodes (201): Props, ParlayRestorePayload, ResolvedSlip, GameLineLegSpec, GameLineMarket, LineLegSpec, LineSheetInput, LineSide (+193 more)

### Community 270 - "NCAAF in-play history tests"
Cohesion: 0.11
Nodes (15): _Conn, _StubEngine, resolve_game_id(), rows_for(), _cand(), _event(), _no_db_school_lookup(), test_a_late_kickoff_falls_back_to_its_utc_dated_games_row() (+7 more)

### Community 273 - "tests/test_prop_odds_utc_stamp.py"
Cohesion: 0.12
Nodes (13): _Conn, _assert_utc_stamp(), _frozen(), _run_mlb(), capture(), events(), _run_ncaaf(), test_an_eastern_row_then_a_later_utc_row_sorts_in_time_order() (+5 more)

### Community 274 - "Monitoring HTTP stream handler"
Cohesion: 0.29
Nodes (4): Handler, _connect(), dumps(), _json_default()

### Community 275 - "NHL game logs as-of windows"
Cohesion: 0.14
Nodes (12): TestLogRowBuilders, backfill(), build_goalie_rows(), build_skater_rows(), build_team_rows(), _complete(), _game_key(), _int() (+4 more)

### Community 277 - "NBA official injury report ingestor"
Cohesion: 0.06
Nodes (32): ConnectionLost, Fetcher, _all_slots(), _bands(), _column_of(), _columns(), ensure_tables(), _hrules() (+24 more)

### Community 278 - "tests/test_feature_artifact_agreement.py"
Cohesion: 0.11
Nodes (13): _Stub, _TolerantUnpickler, _load(), _newest_artifact(), test_artifact_width_matches_its_own_feature_cols(), test_config_list_matches_the_trained_artifact(), test_known_drift_only_names_real_models(), test_pending_features_are_not_live_without_a_retrain() (+5 more)

### Community 28 - "CLV price-taken tests"
Cohesion: 0.07
Nodes (23): _Conn, _Res, _fn(), _migration(), _pick(), test_a_draftkings_decided_row_is_unchanged(), test_a_legacy_row_that_cannot_be_re_measured_leaves_the_old_method(), test_a_legacy_stamped_row_is_re_measured_and_leaves_the_queue() (+15 more)

### Community 280 - "Mobile matchup, head-to-head and record verify"
Cohesion: 0.03
Nodes (87): MatchupGrade, MatchupInfo, TonightMatchupRow, walk(), check(), fakeServer(), main(), read() (+79 more)

### Community 281 - "tests/test_cloud_retrain_artifacts.py"
Cohesion: 0.10
Nodes (12): _Conn, _restore_artifact(), test_a_failed_upload_does_not_lose_a_model_that_trained(), test_a_missing_artifact_table_is_not_an_error_on_restore(), test_a_no_register_run_stores_nothing(), test_load_model_actually_loads_from_the_store_when_the_file_is_gone(), fetchone(), test_load_model_returns_none_when_the_store_has_nothing_either() (+4 more)

### Community 282 - "NCAAF gameday lock tests"
Cohesion: 0.13
Nodes (12): FakeConn, _Rows, write_picks(), db(), test_both_lanes_locked_touches_nothing(), test_dry_run_never_touches_db(), test_first_bet_is_written_and_will_lock(), test_flag_off_restores_delete_and_replace() (+4 more)

### Community 284 - "NCAAF FBS registry tests"
Cohesion: 0.09
Nodes (11): TestRefusalLog, TestRegistryHealthCheck, _alarm_part(), hdb(), _live_db(), _promoted(), _rating(), _registry_check() (+3 more)

### Community 285 - "Health skip budget tests"
Cohesion: 0.07
Nodes (17): FakeConn, _res(), _source_outside_the_budget_table(), test_a_check_never_seen_non_skipped_counts_its_whole_history(), test_a_check_skipped_only_today_is_not_counted_as_a_streak(), test_a_non_skipped_result_is_never_touched(), test_a_stuck_gate_escalates_past_its_budget(), test_an_honest_offseason_skip_stays_skipped_but_shows_its_length() (+9 more)

### Community 288 - "tests/test_nfl_opener.py"
Cohesion: 0.20
Nodes (5): TestBettableBooksOnly, TestSelectOpenerBets, _both_sides(), _frame(), _sched()

### Community 291 - "tests/test_team_stats_asof_invariants.py"
Cohesion: 0.13
Nodes (6): _SeasonConn, test_verify_established_live_season_with_two_snapshots_stays_thin(), test_verify_five_day_span_with_one_snapshot_is_thin(), test_verify_four_day_opening_span_is_still_grace(), test_verify_opening_live_season_is_not_thin(), test_verify_short_historical_season_is_still_thin()

### Community 293 - "NHL props card tests"
Cohesion: 0.16
Nodes (6): TestTheBacktestGradesTheRuleTheCardPlays, TestTheCard, implied(), pick_rows(), _mus(), _quotes()

### Community 295 - "Unit stake sizing and formatting"
Cohesion: 0.07
Nodes (21): UnitStake, test_favourites_risk_more_until_the_cap_binds(), test_flat_conviction_is_still_price_adjusted(), test_risk_and_win_always_agree_with_the_price(), test_risk_is_capped_at_three_units_and_the_payout_is_recomputed(), test_the_minus_110_example_matt_gave(), test_the_risk_cap_can_no_longer_bind(), test_underdogs_risk_less_than_their_conviction() (+13 more)

### Community 298 - "tests/test_nfl_wind_publisher.py"
Cohesion: 0.13
Nodes (10): TestBuildRows, TestKickFields, TestParseMatchup, build_rows(), _fmt_line(), kick_fields(), parse_matchup(), test_nfl_wind_and_opener_rows_drop_a_bet_under_the_floor() (+2 more)

### Community 3 - "Odds, prop odds and NHL derivative odds ingestors"
Cohesion: 0.01
Nodes (205): Meter, Meter, Meter, TestEveryOtherSportStillMintsItsOwn, TestNflResolvesOntoTheSchedule, TestTheResolverFailsClosed, TestOddsFeedTeamNames, TestThreeWayMarketKey (+197 more)

### Community 30 - "NFL live prop model tests"
Cohesion: 0.04
Nodes (39): _FakeOdds, _IdRecordingOdds, _Q, GamedayWorker, GameTracker, _core_worker(), test_a_deployed_bias_must_sit_inside_its_measured_interval(), test_a_matching_board_keeps_the_fast_cadence() (+31 more)

### Community 300 - "tests/test_health_reason_and_cadence.py"
Cohesion: 0.09
Nodes (20): Report, _one(), test_a_24h_ts_check_reads_as_daily(), test_a_bare_add_still_fills_both_columns(), test_a_broken_query_is_its_own_reason(), test_a_late_check_says_how_late(), test_a_passing_check_says_fresh(), test_a_skipped_check_says_the_gate_was_shut() (+12 more)

### Community 301 - "tests/test_live_publish_parity.py"
Cohesion: 0.17
Nodes (12): _Conn, _db(), _labels(), _pick(), test_a_bet_written_while_paused_is_not_announced_after_an_unpause(), test_a_live_health_state_still_publishes(), test_a_paused_model_is_not_announced(), test_a_retired_model_is_not_announced() (+4 more)

### Community 302 - "tests/test_nfl_weather_supabase_readback.py"
Cohesion: 0.13
Nodes (13): FakeConn, _patch_conn(), _rows(), test_a_null_requested_lead_is_not_returned(), test_a_one_lead_response_is_not_stored(), test_a_partial_window_is_not_returned(), test_a_store_failure_is_a_warning_not_an_error(), test_a_subset_of_leads_reads_only_those_columns() (+5 more)

### Community 307 - "Pregame line poller tests"
Cohesion: 0.04
Nodes (43): _PollConn, changed_rows(), _key(), over_credit_cap(), poll_once(), quoted_keys(), _quiet_poll(), _row() (+35 more)

### Community 308 - "Pitcher stats as-of invariant tests"
Cohesion: 0.06
Nodes (22): _FakeConn, build_rows(), _app(), test_a_doubleheader_emits_one_row_per_date(), test_a_fractional_part_that_is_not_thirds_raises(), test_a_rounding_artifact_on_a_tiny_sample_is_not_a_defect(), test_a_row_never_includes_its_own_start(), test_a_season_already_stored_as_a_real_series_is_protected() (+14 more)

### Community 309 - "tests/test_walk_forward_eval.py"
Cohesion: 0.12
Nodes (10): _Cols, _Frame, _fake(), test_a_fold_with_too_little_history_is_skipped(), test_a_single_class_test_season_is_skipped(), _frame(), test_every_fold_trains_only_on_earlier_seasons(), _frame() (+2 more)

### Community 31 - "NBA prop model core"
Cohesion: 0.05
Nodes (53): Spec, compact_report(), predict_means(), alias_key(), _attach_report_ids(), base_key(), box_panel(), build_frame() (+45 more)

### Community 312 - "Live scorer score-change guard"
Cohesion: 0.09
Nodes (19): _MlbConn, _FakeConn, _book_move(), _get_live_dk_odds(), _score_changed_at(), _mlb_odds(), _mlb_ts(), test_mlb_declines_a_total_that_moved_a_full_run_on_an_unchanged_state() (+11 more)

### Community 314 - "Pipeline log reason tests"
Cohesion: 0.22
Nodes (6): _Conn, _capture(), test_a_false_step_records_the_last_error_it_logged(), test_a_false_step_that_logged_nothing_still_says_so(), test_a_raising_step_still_records_the_exception(), test_the_sink_is_removed_after_the_step()

### Community 315 - "NHL props card latest quotes"
Cohesion: 0.10
Nodes (8): _Conn, TestOnlyTheNewestFetchIsShopped, TestWhoThePlayerIs, candidates(), draftkings_at(), identities(), latest_quotes(), upcoming_rows()

### Community 316 - "NCAAF game-day duplicate game tests"
Cohesion: 0.16
Nodes (12): _Conn, _Result, _fold(), load_context(), _night_twin(), _pair_key(), _row(), test_a_twin_does_not_silently_take_the_row_without_lines() (+4 more)

### Community 32 - "NCAAF in-play score distribution engine"
Cohesion: 0.03
Nodes (56): ScoreDistribution, _cluster_bootstrap(), evaluate(), main(), report(), fit(), load_states(), main() (+48 more)

### Community 320 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.09
Nodes (6): _Pg, _PgCursor, TestPreflightCiMode, wind(), wrapped(), fake_open()

### Community 321 - "tests/test_system_health_checks.py"
Cohesion: 0.17
Nodes (4): TestSignalDelivery, _add_signal(), _iso(), _results()

### Community 322 - "DB cursor result wrapper"
Cohesion: 0.22
Nodes (3): _CursorResult, execute(), test_the_cursor_wrapper_rowcount_is_the_cursors()

### Community 327 - "tests/test_ncaaf_live_states.py"
Cohesion: 0.16
Nodes (13): _Conn, record_live_states(), state_change_row(), state_key(), _state(), test_a_failed_write_never_costs_the_pass(), test_a_score_a_period_or_a_possession_change_is_written(), test_first_sight_is_written() (+5 more)

### Community 328 - "MLB prop market pregame quote cutoff"
Cohesion: 0.12
Nodes (7): _Conn, test_a_game_with_no_cutoff_fails_open(), test_both_market_relative_loaders_bound_on_the_cutoff(), test_it_compares_parsed_timestamps_not_strings(), test_it_joins_games_and_uses_the_shared_cutoff(), test_the_newest_qualifying_quote_still_wins(), test_the_post_first_pitch_quote_is_dropped_even_though_it_is_newest()

### Community 33 - "nfl/live_model/feeds: test_feed_resilience + espn"
Cohesion: 0.04
Nodes (54): _ScriptedTick, _competitors(), _deref(), fetch_live_events(), _https(), make_fetcher(), fetch(), parse_core_event() (+46 more)

### Community 330 - "tests/test_nfl_opener.py"
Cohesion: 0.07
Nodes (11): TestBuildOpenerRows, TestFireWindow, TestModelCardSplit, TestPublishOpenerInsertOnce, build_opener_rows(), _opener_model(), _card_row(), _row() (+3 more)

### Community 34 - "Mobile feedback and social links"
Cohesion: 0.07
Nodes (53): FeedbackCategory, FeedbackMessage, FeedbackSender, FeedbackStatus, FeedbackThread, Validation, Nav, Route (+45 more)

### Community 341 - "NFL wind totals model"
Cohesion: 0.14
Nodes (12): Bet, american_to_decimal(), american_to_prob(), apply_slate_cap(), devig_two_way(), evaluate_board(), kelly_stake(), model_under_prob() (+4 more)

### Community 342 - "tests/test_live_pick_features.py"
Cohesion: 0.18
Nodes (11): FakeConn, _record_live_features(), _pick(), test_a_live_bet_records_its_feature_row_and_lambda(), test_a_pick_with_no_feature_row_is_skipped_not_written_empty(), test_a_recorder_failure_is_rolled_back_to_its_savepoint(), test_a_recorder_failure_is_swallowed_rather_than_raised(), test_a_success_releases_its_savepoint() (+3 more)

### Community 348 - "Pregame price age tests"
Cohesion: 0.04
Nodes (27): _BoardConn, _OddsConn, _ShopConn, _TwoIdConn, _UfcBoardConn, _ago(), _clock(), _h2h_row() (+19 more)

### Community 349 - "tests/test_prop_missing_features.py"
Cohesion: 0.14
Nodes (5): TestARowMissingAFeatureIsNotScored, TestEveryPropLoopGoesThroughTheHelper, TestTheUmpireIsTheDeclaredException, _frame(), helper()

### Community 35 - "Mobile app shell and push notifications"
Cohesion: 0.03
Nodes (94): IoniconName, NavRef, PushStatus, PushRoute, PicksView, TabParamList, App(), DailyRecap() (+86 more)

### Community 350 - "Mobile paywall and billing errors"
Cohesion: 0.17
Nodes (21): BillingDisabledError, CheckoutResult, PlanKey, Nav, assertBillingReady(), billingErrorMessage(), openManageSubscription(), redeemCode() (+13 more)

### Community 353 - "tests/test_player_news_ingestor.py"
Cohesion: 0.10
Nodes (21): FakeResponse, fetch_espn_news(), absorb(), _to_item(), _article(), test_a_dead_feed_is_a_quiet_zero(), test_a_sport_with_no_espn_path_is_skipped(), test_a_sport_with_no_team_id_map_still_gets_its_league_feed() (+13 more)

### Community 354 - "NBA prop closing line tests"
Cohesion: 0.09
Nodes (11): _Conn, _Resp, test_a_close_already_held_is_not_bought_again(), test_a_due_close_buys_one_call_of_the_bet_markets_and_reports_its_credits(), test_a_pass_outside_the_window_spends_nothing(), test_only_a_game_holding_a_bet_and_only_once(), test_only_twelve_to_twenty_five_minutes_before_tip(), test_the_ten_minute_evening_passes_always_land_one_inside() (+3 more)

### Community 358 - "NFL live pick writer and recorder tests"
Cohesion: 0.02
Nodes (64): PicksRecorder, TeeRecorder, _AvoidConn, _Conn, _Decision, _OpenConn, announce_live_picks(), build_pick() (+56 more)

### Community 36 - "tests/test_cfbd_ingestor.py"
Cohesion: 0.03
Nodes (54): _NullConn, _day_before(), _local_aggregates(), parse_games(), parse_lines(), retain_existing_cfbd_ids(), shrink_to_prior(), _stat_row() (+46 more)

### Community 360 - "Prop player name matching tests"
Cohesion: 0.11
Nodes (15): FakeConn, normalize_player_name(), resolve_feed_name(), _get_prop_dk_odds(), test_accented_roster_name_matches_the_flat_feed_name(), test_ambiguity_is_a_miss_not_a_guess(), test_an_unlisted_player_is_still_a_miss(), test_every_prop_lane_keys_line_shopping_on_the_resolved_name() (+7 more)

### Community 363 - "tests/test_run_ledger_orphans.py"
Cohesion: 0.12
Nodes (18): _Conn, db(), _insert_open(), _ledger(), _open_rows(), _row(), test_a_genuine_current_hang_is_still_detectable(), test_a_second_sweep_does_not_abort_the_pass_this_process_started() (+10 more)

### Community 378 - "NFL line snapshot tests"
Cohesion: 0.10
Nodes (10): TestDkLineRows, TestPublishLineSnapshots, TestSnapshotRowParams, dk_line_rows(), _num(), snapshot_row_params(), _csv_row(), _rec() (+2 more)

### Community 379 - "Mobile in-app purchases"
Cohesion: 0.19
Nodes (14): IapPurchaseResult, PurchasesSDK, MinimalCustomerInfo, MinimalPackage, apiKey(), ensureConfigured(), fetchLocalizedPrices(), loadPurchases() (+6 more)

### Community 38 - "Odds pruning and sharp book retention tests"
Cohesion: 0.05
Nodes (21): _RecordingConn, _older_than(), _prop_reference_books(), protected_for(), prune_table(), _unprotected(), test_cfbd_archive_prefix_is_protected(), test_historical_backfill_rows_are_protected_in_odds() (+13 more)

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
Nodes (45): Decision, Executor, derivative_lag(), ev_floor(), _mk(), expected_value(), honest_probability(), is_hunt_state() (+37 more)

### Community 393 - "tests/test_sbr_loader.py"
Cohesion: 0.14
Nodes (3): _SqliteConnShim, _SqliteCursorShim, loader_conn()

### Community 397 - "mobile/scripts/ux_scan.mts"
Cohesion: 0.16
Nodes (18): Finding, Severity, changedFiles(), entitlementGate(), fontScaling(), fontSizeLiterals(), hexColors(), main() (+10 more)

### Community 4 - "Settlement tracker and feature engine"
Cohesion: 0.01
Nodes (192): DBConnection, TestComputeInjuryAdjustment, TestHasReturnee, TestHasStarterOut, TestMarketForOdds, TestPregameSnapshotGuard, TestFbsGate, call_in_savepoint() (+184 more)

### Community 408 - "Price prefilter timeout rollback tests"
Cohesion: 0.15
Nodes (9): _PoisonConn, _event_index(), _games(), _run(), test_a_failed_savepoint_rollback_falls_back_to_full_rollback(), test_both_prefilters_timing_out_still_reaches_the_pipeline_log(), test_lookahead_timeout_rolls_back_and_scoring_continues(), test_ncaaf_timeout_rolls_back_and_scoring_continues() (+1 more)

### Community 409 - "mobile/src/lib/otaUpdate.ts"
Cohesion: 0.21
Nodes (11): Calls, CheckState, CheckTrigger, UpdateOutcome, UpdatesApi, check(), fakeApi(), main() (+3 more)

### Community 41 - "tests/test_live_quote_staleness.py"
Cohesion: 0.05
Nodes (42): _Conn, _Q, build_row(), _mark_written(), _publish_key(), quote_from_nfl_quotes(), record_live_prices(), rows_from_quote() (+34 more)

### Community 410 - "Prop market one side per line and card publisher tests"
Cohesion: 0.07
Nodes (15): MarketBet, TestMarketCardPublisher, _Conn, best_per_prop(), test_nfl_prop_market_card_drops_a_bet_under_the_floor(), test_wnba_prop_market_card_drops_a_bet_under_the_floor(), test_publish_skips_games_with_no_games_row(), execute() (+7 more)

### Community 412 - "tests/test_clv_backfill_job.py"
Cohesion: 0.15
Nodes (5): _Conn, _stub_backfill(), test_hard_cap_stops_a_nonempty_queue(), test_loops_until_a_pass_fills_nothing(), test_the_runner_opens_get_connection_and_calls_backfill_clv()

### Community 416 - "UFC stats ingestor resolve tests"
Cohesion: 0.09
Nodes (11): _FakeConn, _resolve_game_rows(), _resolve(), test_resolve_anchor_declines_when_opponent_changed(), test_resolve_anchor_refuses_a_late_replacement(), test_resolve_anchor_rescues_unmapped_variant(), test_resolve_anchor_returns_a_fight_stored_twice_but_not_beside_a_changed_opponent(), test_resolve_exact_pair_wins() (+3 more)

### Community 422 - "NBA prop stat settlement tests"
Cohesion: 0.12
Nodes (8): _SelectConn, test_a_missing_stat_is_none_not_zero(), test_a_turnovers_bet_on_a_player_who_played_settles_win_not_no_action(), test_combo_markets_are_mapped_to_helpers_and_only_the_nba_rule_uses_them(), test_double_double_matches_the_rule_it_replaced(), test_the_loader_carries_every_stat_a_market_settles_on(), test_the_loader_selects_turnovers(), _nba_prop_actual()

### Community 424 - "supabase/functions/_shared/discord.ts"
Cohesion: 0.20
Nodes (15): DiscordApiError, DiscordUser, RoleSyncResult, addAppRole(), addGuildMember(), botFetch(), expectOk(), isGuildMember() (+7 more)

### Community 427 - "Injury fetch and prop odds fake responses"
Cohesion: 0.11
Nodes (4): _R, test_a_SUCCESSFUL_response_with_no_name_is_not_cached(), test_an_unknown_athlete_is_fetched_and_then_remembered(), execute()

### Community 428 - "Prop ladder interpolation and Kalshi pricing tests"
Cohesion: 0.04
Nodes (26): Ladder, Rung, TestMarketRelative, _bets_from_kalshi(), find_bets(), _zero_vig_american(), _expit(), from_one_sided_overs() (+18 more)

### Community 43 - "tests/test_job_queue.py"
Cohesion: 0.03
Nodes (54): _VoidConn, _posted_row(), _quiet(), _run_void(), _run_void_job(), test_a_declared_job_is_queued_once_however_often_it_is_read(), test_a_failed_job_needs_a_new_key_to_rerun(), test_a_graded_pick_is_refused_not_rewritten() (+46 more)

### Community 432 - "System health checks and first-pitch guard"
Cohesion: 0.06
Nodes (22): HealthReport, ncaaf_season_for_date(), test_january_games_belong_to_the_prior_season(), test_dedupe_and_health_use_the_shared_tuple(), test_unique_row_sql_is_key_parts_plus_date_and_side(), _job_health_check(), still_pre_game(), unique_row_sql() (+14 more)

### Community 433 - "tests/test_system_health_checks.py"
Cohesion: 0.16
Nodes (3): TestPassCompletion, TestPassSteps, _add_run()

### Community 434 - "NBA prop market model and card"
Cohesion: 0.09
Nodes (25): NbaPropDecision, Plan, coherent(), fair_under(), fetch_times(), find_bets(), in_window(), load_quotes() (+17 more)

### Community 435 - "UFC event ingest tests"
Cohesion: 0.11
Nodes (7): _IngestConn, _ingest(), _one_fight_event(), test_a_late_replacement_is_not_scored_on_the_original_booking(), test_a_misspelled_fighter_is_scored_for_the_side_they_fought_on(), test_a_row_naming_neither_fighter_is_left_unscored(), test_the_same_fight_stored_twice_is_scored_on_both_rows_each_way_round()

### Community 436 - "tests/test_mlb_sbr_twin.py"
Cohesion: 0.21
Nodes (9): _Conn, _Cur, _lookup_home_won(), mlb_game_final(), sbr_twin_id(), test_no_final_anywhere_is_none(), test_scored_canonical_row_wins_and_keeps_its_label(), test_twin_id_swaps_only_the_renamed_franchises() (+1 more)

### Community 437 - "tests/test_ufc_phantom_filter.py"
Cohesion: 0.21
Nodes (6): TestFilterUfcPhantom, TestIsKnownUfcMatchup, _filter_ufc_phantom(), _is_known_ufc_matchup(), _game(), _odds()

### Community 44 - "scripts: build_nfl_live_leader_artifact + model"
Cohesion: 0.06
Nodes (36): Artifact, Decision, am_to_dec(), artifact_from_dict(), band_for(), decide(), leader_expected_margin(), load_artifact() (+28 more)

### Community 442 - "tests/test_batter_prop_log_pin.py"
Cohesion: 0.09
Nodes (11): _Rec, _ScoringConn, build_batter_scoring_rows(), build_pitcher_scoring_rows(), _log_sql(), test_batter_log_scan_is_pinned_to_the_lookback_not_the_catalog(), test_five_models_share_one_log_load(), test_no_lineup_does_not_scan_the_log() (+3 more)

### Community 443 - "tests/test_opp_starter_features.py"
Cohesion: 0.09
Nodes (14): _StubConn, _StubResult, _opp_starter_savant(), _batter_bulk(), test_batter_bulk_carries_everything_opp_starter_savant_reads(), test_it_reads_the_starters_savant_row(), test_live_mode_falls_back_to_prior_season(), test_live_mode_prefers_the_current_season() (+6 more)

### Community 445 - "NFL CLV backtest and feature build"
Cohesion: 0.14
Nodes (9): ShrunkEnsemble, add_form(), build(), feature_columns(), market_features(), team_game_stats(), fmt(), main() (+1 more)

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

### Community 464 - "NCAAF live cadence and odds feed tests"
Cohesion: 0.04
Nodes (29): _Ctx, _ev(), _feed_with_payload(), gameday_mod(), _main_source(), _modelled_monthly_cfbd_calls(), test_a_single_failed_summary_does_not_drop_the_other_games(), test_a_sustained_feed_outage_degrades_to_no_odds() (+21 more)

### Community 466 - "Mobile error states and load handling"
Cohesion: 0.03
Nodes (116): Props, LivePicksState, Args, PlayerNewsState, ConnectionMap, providerMeta, SportsbookConnection, SportsbookProvider (+108 more)

### Community 47 - "scripts/nfl_edge_gameline_rules.py"
Cohesion: 0.06
Nodes (50): Tee, TestTheWeatherStepWalksTheWindow, _nhl_blended_features(), d(), ats(), bettable_ats(), bh(), board_at() (+42 more)

### Community 470 - "Threshold review DDL tests"
Cohesion: 0.12
Nodes (4): _DdlConn, _DdlRes, test_a_failed_lock_down_does_not_lose_the_table(), test_ensure_schema_commits_the_tables_it_creates()

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
Cohesion: 0.16
Nodes (5): _Conn, promote_external(), test_external_promotion_refuses_a_map_that_does_not_transfer(), test_external_promotion_writes_only_the_promoted_columns(), test_the_scorer_reads_the_external_map_like_any_promoted_one()

### Community 485 - "Local store cache and NFL prop shape simulation"
Cohesion: 0.07
Nodes (37): TestLocalCacheGuards, activate(), available(), _manifest(), _path(), read_table(), status(), _write_manifest() (+29 more)

### Community 486 - "tests/test_pipeline_report_rollback.py"
Cohesion: 0.20
Nodes (4): _Conn, _rows(), test_a_failed_query_rolls_back(), test_one_broken_section_does_not_break_the_rest()

### Community 489 - "NFL pick monitor game id tests"
Cohesion: 0.16
Nodes (3): TestTheJoinKeyMatchesPicks, eval_row(), _picks_game_id()

### Community 49 - "Failure alerter fake-connection tests"
Cohesion: 0.06
Nodes (18): FakeConn, TestDeliveryAndNoise, TestHealthCheckOnlyIsNotADirtyPass, TestItCannotBreakTheWorker, TestSilentJobs, TestWhatCountsAsAFailure, _clean_runs(), _posts() (+10 more)

### Community 493 - "Pipeline watch and burn alerts"
Cohesion: 0.04
Nodes (44): _Conn, collect(), test_a_clean_pass_produces_no_finding(), test_a_clean_run_still_posts(), test_a_confirmed_post_is_ledgered_so_the_run_can_be_verified(), test_a_failed_ledger_does_not_lose_the_report(), execute(), test_a_failed_query_rolls_back_and_does_not_sink_the_run() (+36 more)

### Community 497 - "Player news ingestor tests"
Cohesion: 0.07
Nodes (16): FakeConn, _Result, build_name_index(), ingest_player_news(), main(), prune_old(), teams_with_props_today(), test_a_fresh_table_is_not_refetched() (+8 more)

### Community 5 - "Mobile theme, parlays and sportsbook links"
Cohesion: 0.02
Nodes (275): Props, Nav, Props, Props, FilterChipProps, Props, Props, Props (+267 more)

### Community 501 - "Score off any book line tests"
Cohesion: 0.16
Nodes (12): _FakeConn, _fallback_line_quote(), _latest_book_prop_row(), _row(), test_a_book_with_a_line_but_no_price_is_skipped(), test_a_book_with_a_price_but_no_line_is_skipped(), test_draftkings_is_not_asked_twice(), test_no_bettable_book_lists_it_is_none_not_a_crash() (+4 more)

### Community 511 - "Prop lookahead window tests"
Cohesion: 0.17
Nodes (4): TestTheOddsFetchReachesTomorrow, TestTheScorerReachesTomorrow, _get_events(), _events_src()

### Community 518 - "NHL blocked shots settlement tests"
Cohesion: 0.27
Nodes (5): _Shim, TestSettlement, _bet(), _played(), _result()

### Community 519 - "Monitoring server tests"
Cohesion: 0.05
Nodes (26): _Resp, _credits_from(), classify(), paid_apis(), _get(), http_server(), live_server(), _perf_rows() (+18 more)

### Community 52 - "tests/test_best_line_live.py"
Cohesion: 0.04
Nodes (46): _FakeConn, _best_live_price(), _live_decision_quote(), _live_quote_is_on_offer(), _tag_live(), _parse_book_markets(), parse_event_odds(), _ev() (+38 more)

### Community 524 - "NBA injury report scope dates"
Cohesion: 0.33
Nodes (3): _DatesConn, scope_dates(), test_scope_is_every_game_date_and_the_day_before_newest_first()

### Community 525 - "NBA prop window plan tests"
Cohesion: 0.21
Nodes (9): _PlanConn, _game(), _plan(), _t(), test_a_projection_too_old_to_price_does_not_block_the_retry(), test_the_plan_owes_a_close_with_no_game_to_decide(), test_the_plan_projects_games_about_an_hour_out_and_any_in_the_window_never_projected(), test_the_plan_says_publish_while_any_game_is_near() (+1 more)

### Community 526 - "MLB in-play game state alignment"
Cohesion: 0.22
Nodes (6): GameClock, _t(), test_before_first_pitch_and_after_last_play_are_not_priced(), test_between_pas_across_third_out_rolls_over_to_next_half(), test_mid_plate_appearance_is_that_pa_before_state(), test_plays_without_times_are_ignored()

### Community 533 - "NFL wind card book filter tests"
Cohesion: 0.06
Nodes (11): TestTheCardFilters, TestTheListIsShared, test_the_card_records_a_decision_when_nothing_qualifies(), test_the_decisions_ledger_is_worker_only_and_created_behind_the_guard(), test_a_replay_never_prices_off_todays_ladder_even_when_on(), test_the_card_does_not_price_off_kalshi_until_it_is_graded(), _attach(), books() (+3 more)

### Community 534 - "Prop no-bet row survival tests"
Cohesion: 0.07
Nodes (9): _Board, _Clock, _PollConn, _fake_datetime_class(), _game(), _iso(), test_the_poller_keeps_prop_no_bet_rows_the_refresh_pass_still_clears(), test_the_poller_tells_the_scorer_to_leave_prop_rows_alone() (+1 more)

### Community 536 - "Mobile bankroll storage"
Cohesion: 0.23
Nodes (12): KeyValueStore, check(), eq(), fakeStore(), interleaving(), slowStore(), storage(), createBankrollStore() (+4 more)

### Community 54 - "tests/test_void_picks.py"
Cohesion: 0.06
Nodes (10): _FakeConn, TestAPostedSignalIsLocked, TestAPostedVoidAnnouncesAfterCommit, TestVoidingAPostedPickIsAnExplicitOptIn, TestWhatMayBeVoided, TestWhatTheVoidWrites, plan_voids(), _row() (+2 more)

### Community 549 - "Multi-book odds pregame cutoff tests"
Cohesion: 0.15
Nodes (6): _OddsConn, _odds_query(), test_a_game_with_no_commence_time_keeps_every_row(), test_the_cutoff_is_the_19_char_utc_prefix(), test_the_pregame_read_is_bounded_at_first_pitch(), test_the_ufc_sibling_lookup_is_bounded_too()

### Community 55 - "NCAAF gameday worker and ESPN feed"
Cohesion: 0.07
Nodes (21): LiveOddsFeed, GameContext, now_iso(), school(), fetch_scoreboard_cfbd(), fetch_team_ids(), _headers(), _strip_mascot() (+13 more)

### Community 551 - "NHL blocked shots card tests"
Cohesion: 0.19
Nodes (4): TestTheCard, pick_rows(), _scored(), execute()

### Community 56 - "tests/test_daily_retry.py"
Cohesion: 0.06
Nodes (42): _Conn, _Cursor, _FrozenDatetime, DailyRun, Decision, _aborted(), _aborted_row(), _ok() (+34 more)

### Community 563 - "NFL prop backtest model and universe rate"
Cohesion: 0.06
Nodes (17): LazyConnection, TestPlaceboCannotSilentlyNotHappen, TestPriceMath, backtest_model(), _bootstrap_roi_ci(), _dispersion(), _fit(), _kickoffs() (+9 more)

### Community 564 - "Feature matrix dtypes and line sweeps"
Cohesion: 0.03
Nodes (37): TestAmericanToDecimalScorer, coerce_numeric_features(), feature_matrix(), _backtest_ufc_fight(), _emit(), american_to_decimal(), build_side_table(), _fetch_games() (+29 more)

### Community 57 - "tests/test_live_book_move_guard.py"
Cohesion: 0.10
Nodes (31): BookMoveClock, american_to_implied(), _at(), _delaware_ctx(), _dk(), _iso(), _ncaaf_engine(), _nfl() (+23 more)

### Community 570 - "tests/test_nfl_opener.py"
Cohesion: 0.09
Nodes (10): TestTickLatency, bucket(), label(), main(), table(), wilson(), test_projecting_runs_after_the_decisions_are_published(), test_the_tick_passes_a_days_that_covers_the_whole_window() (+2 more)

### Community 576 - "tests/test_weekly_catch_up.py"
Cohesion: 0.15
Nodes (3): _Conn, _Cursor, test_a_failing_savant_refresh_does_not_cost_the_calibration_its_catch_up()

### Community 58 - "tests: test_discord_notifier + test_discord_live_field"
Cohesion: 0.03
Nodes (55): _FakeConn, _sig(), test_a_strictly_better_book_becomes_the_headline(), test_an_equal_or_worse_price_never_replaces_draftkings(), test_best_odds_never_reaches_the_qualifying_gate(), test_draftkings_winning_its_own_shop_is_published_as_draftkings(), test_every_pre_game_producer_computes_good_to(), test_good_to_is_published_when_the_producer_supplies_it() (+47 more)

### Community 582 - "Prop odds book update-time tests"
Cohesion: 0.26
Nodes (6): _Conn, _parse(), test_a_row_built_without_the_key_still_inserts_as_null(), test_no_clock_anywhere_is_none_not_our_fetch_time(), test_the_column_is_added_only_when_the_catalog_lacks_it(), test_the_markets_own_clock_is_stored_else_the_books()

### Community 583 - "NFL pick monitor"
Cohesion: 0.11
Nodes (11): TestClassify, TestImmutabilityContract, TestLatestPerPick, TestWindPublisherLock, classify(), _f(), latest_per_pick(), main() (+3 more)

### Community 59 - "NFL odds pulls and live prop assessment"
Cohesion: 0.02
Nodes (62): OddsAPIClient, SnapshotResult, Puller, configured(), guild_stats(), main(), build_server(), serve_in_thread() (+54 more)

### Community 592 - "Live quote score clock"
Cohesion: 0.23
Nodes (5): ScoreClock, test_score_clock_ignores_a_dropped_score_field(), test_score_clock_keeps_games_independent(), test_score_clock_reports_no_event_at_first_sight(), test_score_clock_stamps_the_change_and_holds_it()

### Community 595 - "Voided pick, restate and X results job tests"
Cohesion: 0.07
Nodes (12): _Conn, test_the_job_does_not_bypass_the_day_is_over_guard(), test_the_job_does_not_read_rowcount_off_the_cursor(), test_the_job_only_clears_its_own_ledger_kind(), _producer(), test_a_restated_pick_still_names_the_cheaper_book(), test_a_worse_price_elsewhere_never_replaces_draftkings(), test_both_signal_producers_select_the_better_price() (+4 more)

### Community 597 - "Multi-book fallback response tests"
Cohesion: 0.20
Nodes (7): _Resp, test_a_rejected_book_list_falls_back_to_the_decision_book(), _get(), test_the_fallback_does_not_recurse_forever(), _get(), test_the_per_event_fetch_asks_for_every_book(), _get()

### Community 6 - "Live scorer and pick insertion"
Cohesion: 0.04
Nodes (44): TestAmericanToImpliedProb, today_et(), build_wnba_prop_scoring_rows(), _age_seconds(), _lane_signature(), _latest_live_state(), _live_bets_today(), _make_live_pick() (+36 more)

### Community 600 - "Player news ingestor"
Cohesion: 0.11
Nodes (14): NewsItem, NewsPlayer, _article_url(), _athletes_in(), _fetch_espn(), _minutes_since_last_ingest(), _parse_published(), store_items() (+6 more)

### Community 61 - "mobile/src/hooks: verify_tracked_performance + useStakeSettings"
Cohesion: 0.05
Nodes (58): StakeMode, StakeState, LiveTrackSnapshot, TrackedBetRow, trackedBetStatus, TrackedBetSummary, emit(), load() (+50 more)

### Community 611 - "supabase/functions/revenuecat-webhook/index.ts"
Cohesion: 0.22
Nodes (3): RcEvent, admin, PRODUCT_TO_PLAN

### Community 613 - "supabase/functions/whop-webhook/index.ts"
Cohesion: 0.25
Nodes (4): WhopMembership, signatureValid(), timingSafeEqual(), admin

### Community 615 - "tests/test_model_quality.py"
Cohesion: 0.22
Nodes (3): _Shim, _insert_open_bet(), test_run_persists_all_unders_fade_slate_as_crit()

### Community 63 - "NFL live game state math"
Cohesion: 0.05
Nodes (34): Read, game_index(), record_nfl_anchor_prices(), pace_ratio(), _sigmoid(), under_prob(), _as_float(), _as_int() (+26 more)

### Community 630 - "Scorer confidence tier and pick label tests"
Cohesion: 0.06
Nodes (15): TestBuildInjuryFlag, TestBuildPickLabel, TestConfidenceTier, TestFeatureValue, TestQuarterKelly, _build_injury_flag(), _build_pick_label(), _confidence_tier() (+7 more)

### Community 633 - "NFL prop count and yardage distribution tests"
Cohesion: 0.14
Nodes (6): TestBinaryMarket, TestCountDistributions, TestYardageDistribution, _nfl_prop_probs(), _art(), test_nb_head_changes_probs_only_when_nb_r_present()

### Community 642 - "Best line sweep tests"
Cohesion: 0.22
Nodes (3): _Conn, _row(), test_the_free_half_never_changes_the_pick_set()

### Community 644 - "NFL prop odds game matching tests"
Cohesion: 0.29
Nodes (3): TestResolveGameId, resolve_nfl_game_id(), resolve()

### Community 645 - "NBA injury report PDF parser"
Cohesion: 0.18
Nodes (9): Report, finish_rows(), parse_pdf(), parse_title(), rows_from_pages(), season_of(), test_finish_rows_builds_our_game_id_and_season(), test_report_time_comes_from_the_header_and_is_stored_in_utc() (+1 more)

### Community 65 - "NFL live score distribution and calibration"
Cohesion: 0.10
Nodes (10): ScoreDistribution, _cluster_bootstrap(), evaluate(), main(), report(), mu_bucket(), _mu_centres(), _spearman_to_gaussian() (+2 more)

### Community 658 - "NBA prop market roster resolver"
Cohesion: 0.23
Nodes (5): Roster, name_key(), test_a_books_initials_match_the_logs(), test_a_rookie_logged_under_an_espn_id_resolves_to_it(), test_the_resolver_uses_the_results_writers_normaliser()

### Community 662 - "Signal publish-on-write tests"
Cohesion: 0.06
Nodes (18): _Conn, _body(), _row(), _surfaces(), _make(), test_a_broken_webhook_does_not_suppress_the_push(), test_a_failed_capture_still_delivers(), test_a_publish_failure_does_not_kill_the_tick() (+10 more)

### Community 665 - "NBA injury report slot time and URL"
Cohesion: 0.29
Nodes (6): _Fetcher, report_url(), slot_time(), test_a_recent_403_is_not_written_so_a_later_run_can_still_fetch_it(), test_an_old_403_is_written_so_a_rerun_never_asks_again(), test_slot_time_is_eastern()

### Community 666 - "Mobile bankroll hook"
Cohesion: 0.32
Nodes (7): BankrollSettings, useBankroll(), canStepUnitPct(), sanitizeUnitPct(), stepUnitPct(), store, BANKROLL_DEFAULTS

### Community 668 - "Mobile entitlement and subscription hooks"
Cohesion: 0.57
Nodes (6): useEntitlement, useSubscription, SubscriptionRow, AccessSource, fetchSubscription(), billingReady()

### Community 67 - "tests/test_game_market_gate.py"
Cohesion: 0.06
Nodes (49): GateVerdict, MarketBookend, PublicSplits, apply_to_picks(), _as_float(), bookend_from_odds(), evaluate(), fair_prob() (+41 more)

### Community 69 - "tests/test_pick_integrity.py"
Cohesion: 0.04
Nodes (37): _Conn, _Shim, _add_pick(), discord_sent(), _health(), health_db(), test_a_label_may_not_name_a_market_the_pick_does_not_settle_on(), test_a_label_naming_the_other_team_is_refused() (+29 more)

### Community 695 - "NCAAF FBS registry and refusal claims"
Cohesion: 0.15
Nodes (6): TestUnratedFbsClaim, fbs_refusal_claims(), unrated_fbs_claim(), test_the_promoted_list_names_the_2026_schools(), test_the_registry_refresh_is_declared_and_validates(), test_the_scorer_reads_the_registry_once_per_pass_and_only_for_the_log()

### Community 70 - "tests/test_record_one_pick_per_event.py"
Cohesion: 0.04
Nodes (48): _CaptureConn, _RecordingConn, duplicate_copy_exclusion_sql(), _code(), _copy_for_node(), _fn(), _node(), _read() (+40 more)

### Community 715 - "NCAAF alias scores fake cursor"
Cohesion: 0.33
Nodes (3): _FakeCursor, test_stored_finals_are_mirrored_without_a_cfbd_pull(), execute()

### Community 73 - "nfl/live_model/tests: test_props + props"
Cohesion: 0.08
Nodes (34): PropProjection, GameState, PlayerState, _accrued(), _count(), detect_inactive(), price_over(), project() (+26 more)

### Community 77 - "tests/test_wnba_prop_market.py"
Cohesion: 0.05
Nodes (32): _FakeConn, _QuoteConn, load_wnba_prop_quotes(), apply_price_floor(), norm_name(), pick_rows(), player_ids(), publish() (+24 more)

### Community 78 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.09
Nodes (16): _After, _Conn, _RaceConn, TestFlexedKickoffRefreshes, TestLockSurvivesNothing, TestNoneRowBesideABetIsCleared, TestPublishRace, TestPublishScored (+8 more)

### Community 79 - "NHL derivative totals model"
Cohesion: 0.04
Nodes (49): Market, _Meter, _Resp, build_p1_frame(), build_team_frame(), day_interval(), _ew(), fit() (+41 more)

### Community 8 - "Mobile player log and matchup stats"
Cohesion: 0.02
Nodes (265): Props, PlayerNextGame, Section, Args, PlayerStatKey, HitMode, HitSelection, HitDirection (+257 more)

### Community 80 - "Global EV floor and NHL totals tests"
Cohesion: 0.03
Nodes (64): Gate, NhlTotalBet, _LockConn, _SlateConn, expected_value(), min_ev_for(), _parse_iso_ts(), _snap_sort_key() (+56 more)

### Community 83 - "tests/test_nhl_props.py"
Cohesion: 0.06
Nodes (15): _Shim, TestEveryLiveModelIsWiredEverywhere, TestSettlement, TestTheDistribution, TestTheGoalieFrame, TestTonightsRowIsATrainingRow, _bet(), db() (+7 more)

### Community 84 - "Discord notifier, void notices and price bound tests"
Cohesion: 0.01
Nodes (126): _Conn, _KeyConn, DiscordVoidRejected, paused_row_exclusion_sql(), announce_posted_voids(), build_parser(), main(), _posted_sql() (+118 more)

### Community 85 - "tests/test_recap_retries_a_skipped_day.py"
Cohesion: 0.06
Nodes (27): _LiteConn, World, _add_pick(), _grade(), _lite(), _schema(), test_a_day_with_nothing_counting_posts_nothing_and_logs_nothing(), test_a_failed_receipt_never_reposts_the_day() (+19 more)

### Community 885 - "NFL prop market rule and card"
Cohesion: 0.04
Nodes (37): TestKickoffGate, TestMarketGrading, ladders_or_empty(), american_to_profit(), _as_dt(), drop_pulled_quotes(), grade(), season_of() (+29 more)

### Community 9 - "Model trainer and research CLI scripts"
Cohesion: 0.01
Nodes (207): TestParseNflverseScores, TestTheStoreReadsTheStartTime, assert_retrain_allowed(), calibration_method(), scoring_method(), get_connection(), ladders(), backfill_nfl_player_stats() (+199 more)

### Community 90 - "tests/test_f5_any_book_line.py"
Cohesion: 0.08
Nodes (31): _Clf, _GameOddsConn, _fallback_game_line_quote(), _get_scoring_odds(), _has_real_game_price(), _cut(), _mlb_feat(), _on() (+23 more)

### Community 92 - "tests/test_ncaaf_prop_odds.py"
Cohesion: 0.05
Nodes (27): _Conn, _Resp, _market_chunks(), _football_map(), resolver(), scope(), test_a_book_we_did_not_ask_for_is_never_written(), test_a_day_with_no_college_games_spends_nothing() (+19 more)

### Community 94 - "NFL prop model and player row parsing tests"
Cohesion: 0.02
Nodes (48): TestGamesRows, TestIngestEventsDoesNotShadowItsMarkets, TestKickoff, TestLocalOddsCache, TestParsePlayerRows, TestParseTeamRows, TestPushAdjustment, TestSnapRows (+40 more)

### Community 95 - "tests/test_ncaaf_pbp_store.py"
Cohesion: 0.07
Nodes (22): _Conn, _extremes(), load_season_from_db(), observed_ranges(), _report_ranges(), store_season(), finalize_states(), states() (+14 more)

### Community 96 - "tests/test_heartbeat_watchdog.py"
Cohesion: 0.05
Nodes (36): _FakeConn, _FakeCursor, _break_db(), sink(), test_a_failed_post_does_not_start_the_throttle(), test_a_healthy_start_never_announces_a_recovery(), test_a_returning_outage_alerts_again_immediately(), test_a_silent_failure_alerter_is_caught_by_the_watchdog() (+28 more)

### Community 97 - "Game injury veto gate and tests"
Cohesion: 0.05
Nodes (51): _InjConn, _InjConn, TestNormaliseName, norm_player_name(), apply_to_picks(), _goalie_names(), _pitcher_names(), player_matches_veto() (+43 more)

### Community 98 - "models: nhl_prop_blocked_shots + nhl_prop_blocked_shots_backtest"
Cohesion: 0.08
Nodes (20): TestTonightsRowIsATrainingRow, build_frame(), _ew(), expected_value(), fit(), load_skaters(), load_teams(), name_key() (+12 more)

### Community 516 - "Pipeline run ledger"
Cohesion: 0.18
Nodes (9): roll_up(), _abort_orphans(), abort_prior_refresh_orphans(), _boot_cutoff(), _ensure_table(), finish_run(), main(), _now() (+1 more)

### Community 100 - "scripts/nfl_edge_halftime_oos.py"
Cohesion: 0.12
Nodes (22): assert_same_as_earlier(), bh(), boot(), boot_coef(), build(), ci(), coverage(), fmt() (+14 more)

### Community 101 - "NCAAF slug and orientation helpers"
Cohesion: 0.22
Nodes (5): _loose_orientation(), ncaaf_slug(), _slug_extends(), _slug_pair(), test_slug()

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
Cohesion: 0.06
Nodes (30): apply_prop_daily_cap(), _claimed_ev(), dedupe_player_props(), _downgrade(), _is_paused_row(), _bet(), _identity_cal(), _prop() (+22 more)

### Community 108 - "ncaaf_live/tests/test_pregame_calibration.py"
Cohesion: 0.08
Nodes (18): correct_for_pregame(), _load_pregame_calibration(), pregame_dog_points(), _real_artifact(), test_a_big_dog_is_marked_down_hard(), test_a_corrupt_artifact_leaves_the_probability_alone(), test_a_favourite_is_marked_up(), test_a_missing_artifact_leaves_the_probability_alone() (+10 more)

### Community 11 - "Direct sportsbook feeds and freshness probes"
Cohesion: 0.03
Nodes (61): live_slate_dates(), _connect(), _open(), _session_options(), use_poller_session(), main(), poll_once(), run() (+53 more)

### Community 110 - "tests/test_mobile_line_movement.py"
Cohesion: 0.08
Nodes (27): _fn(), _read(), _run(), test_a_cut_table_keeps_the_pick_and_says_what_it_covers(), test_a_cut_window_keeps_the_pick_row_on_the_8_row_table(), test_a_pick_made_after_the_cards_start_never_reads_since_your_pick(), test_after_the_start_the_verdict_is_not_graded(), test_an_old_snapshot_is_not_the_price_at_the_pick() (+19 more)

### Community 111 - "tests/test_live_calibration.py"
Cohesion: 0.07
Nodes (32): pick(), test_a_peak_with_no_plateau_anywhere_is_labelled_as_one(), test_a_prob_cut_and_an_ev_cut_select_different_picks(), test_calibration_also_scores_ev_against_realised_roi(), test_calibration_is_empty_rather_than_wrong_with_nothing_settled(), test_calibration_reports_the_gap_between_claim_and_reality(), test_expected_value_matches_the_hand_calculation(), test_expected_value_refuses_a_missing_or_zero_price() (+24 more)

### Community 112 - "Push deep link and mobile player detail tests"
Cohesion: 0.03
Nodes (53): test_every_revoke_names_the_roles_rather_than_public(), test_odds_keeps_select_for_the_app(), test_the_two_rls_off_tables_lose_everything(), test_the_function_revoke_names_public_as_well_as_the_roles(), _read(), test_every_player_page_read_names_its_relation_literally(), test_next_game_is_earliest_in_the_window_not_tonights_date(), test_results_are_units_never_dollars_and_never_paper() (+45 more)

### Community 116 - "tests/test_score_off_any_book_line.py"
Cohesion: 0.11
Nodes (22): _cut(), _on(), _pick(), _sql_const(), _src(), test_a_pick_draftkings_never_priced_is_a_parlay_leg_at_its_own_book(), test_a_pick_off_another_books_line_carries_no_draftkings_numbers(), test_a_pick_with_no_price_anywhere_is_left_alone() (+14 more)

### Community 117 - "NHL lab summaries and early-season blend"
Cohesion: 0.05
Nodes (54): accuracy(), first_games(), logloss(), main(), sweep(), units(), walk(), decide() (+46 more)

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
Cohesion: 0.08
Nodes (26): assemble_player_features(), _avg_finish(), build_golf_scoring_features(), _event_finishes(), _f(), _field_features(), _made_cut_rate(), matchup_diff_features() (+18 more)

### Community 132 - "ncaaf_live/tests/test_states.py"
Cohesion: 0.13
Nodes (23): build_states(), _detect_score_convention(), _platform(), _plays(), _post_convention_game(), _pre_convention_game(), test_a_scoring_plays_state_does_not_contain_its_own_points(), test_ambiguous_convention_refuses_to_build() (+15 more)

### Community 133 - "tests/test_bovada_feed.py"
Cohesion: 0.11
Nodes (29): _american(), _complete(), _num(), parse_coupon(), _row_for(), _seen_key(), _stamp(), _coupon() (+21 more)

### Community 134 - "tests/test_market_movement.py"
Cohesion: 0.09
Nodes (23): american_to_prob(), build_market_features(), _is_full_game_snap(), _latest_two_sided(), _s(), test_a_game_with_no_decision_book_still_gets_features(), test_a_line_that_genuinely_did_not_move_is_zero_not_none(), test_a_one_way_sharp_quote_yields_nothing() (+15 more)

### Community 136 - "tests/test_ncaaf_cross_book_opener.py"
Cohesion: 0.07
Nodes (25): _minutes_apart(), build_artifact(), build_band_artifact(), _branch(), test_absent_ceiling_means_unbounded(), test_artifact_shape(), test_band_ceiling_is_enforced_in_the_scorer(), test_band_volumes_sum_to_the_single_gate_backtest() (+17 more)

### Community 139 - "NFL in-play edge study 2025 and devig"
Cohesion: 0.07
Nodes (44): s(), fit_models(), async_check(), attach_games(), bh(), cell(), check_possession(), diagnostics() (+36 more)

### Community 142 - "tests/test_health_pregame_prices_current.py"
Cohesion: 0.10
Nodes (30): _at(), _game(), _row(), _run(), test_a_broken_feed_read_is_an_error_and_rolls_back(), test_a_broken_query_is_an_error_and_rolls_back(), test_a_cancelled_fight_and_a_pulled_game_do_not_raise_the_alarm(), test_a_dead_feed_with_no_priced_game_is_a_crit() (+22 more)

### Community 145 - "NBA prop projection model"
Cohesion: 0.07
Nodes (26): asof_roster(), box_from_log(), coherent(), collapse_official(), espn_compact(), find_bets(), implied_one(), main_line() (+18 more)

### Community 147 - "scripts/nfl_edge_extreme_props.py"
Cohesion: 0.12
Nodes (29): actuals(), add_modes(), bar(), candidates(), cell(), decision_boards(), devig(), fit_holdout() (+21 more)

### Community 148 - "scripts/nfl_edge_settlement.py"
Cohesion: 0.14
Nodes (30): add_test(), attach(), banner(), bh(), board(), boot_draws(), cell(), choose() (+22 more)

### Community 15 - "X publisher"
Cohesion: 0.02
Nodes (74): discover(), fetch_all(), _get_image(), main(), _original_size(), store(), _x_api_profile(), test_the_record_restatement_and_the_slate_restatement_are_separate() (+66 more)

### Community 153 - "tests/test_agents_contract.py"
Cohesion: 0.05
Nodes (20): _labelled_retired(), test_blocked_items_are_marked_so_the_agent_skips_them(), test_every_backlog_item_is_a_checkbox(), test_neither_agent_may_change_a_model_threshold(), test_the_agents_are_findable_from_the_file_every_session_reads(), test_the_backlog_does_not_promise_an_agent_that_no_longer_runs(), test_the_backlog_exists_and_has_items(), test_the_contract_documents_every_agent_by_name() (+12 more)

### Community 154 - "Historical backfill and sub-10s live path tests"
Cohesion: 0.03
Nodes (43): relabel_in_play(), test_a_run_that_writes_nothing_is_not_reported_as_success(), test_the_insert_rolls_back_per_row(), test_the_in_play_relabel_uses_the_better_bound(), test_a_rerun_can_be_told_to_ignore_the_pull_ledger(), test_a_snapshot_after_first_pitch_is_marked_in_play(), test_a_snapshot_exactly_at_first_pitch_stays_pregame(), test_backfill_rows_are_stamped_with_the_historical_source() (+35 more)

### Community 157 - "Position vs opponent tests"
Cohesion: 0.07
Nodes (19): _bn_body(), _sql_groups(), test_a_failed_position_read_is_said_not_hidden(), test_a_failed_read_is_not_held_on_the_spinner(), test_every_mlb_stat_chip_has_a_branch(), test_every_nfl_stat_chip_has_a_branch(), test_every_roster_sport_chip_has_a_branch(), test_mlb_lineup_buckets_agree_between_app_and_server() (+11 more)

### Community 159 - "WNBA results ingestor parsers"
Cohesion: 0.08
Nodes (28): build_log_row(), _core_athlete(), _deref(), _et_date(), _fetch_core_box_players(), parse_core_event(), parse_core_stat_values(), parse_scoreboard() (+20 more)

### Community 16 - "Daily pipeline runner and push notifier"
Cohesion: 0.02
Nodes (89): _run_migrations(), setup_database(), run_ncaaf_stats_ingestor(), run_player_news_ingestor(), run_nba_prop_odds_ingestor(), run_wnba_prop_odds_ingestor(), format_view_migration_failure(), check_env() (+81 more)

### Community 160 - "NFL in-play prop flow backtests"
Cohesion: 0.03
Nodes (89): bias_table(), main(), apply_anchor(), best_hit(), _boot_ci(), drop_degenerate(), evaluate(), fit_time_curve() (+81 more)

### Community 161 - "NBA box score enrichment"
Cohesion: 0.07
Nodes (49): _blank(), box_rows(), _check_unmapped(), _create(), dnp_kind(), ensure_tables(), fetch_advanced(), fill_missing_game_logs() (+41 more)

### Community 165 - "NHL stats ingestor"
Cohesion: 0.08
Nodes (24): top_up(), _apply_asof_team_rates(), backfill_nhl_goalies(), backfill_nhl_stats(), _build_goalie_rows(), _build_nhl_team_rows(), _fetch_goalie_season_stats(), _fetch_nhl_advanced_stats() (+16 more)

### Community 166 - "Prop box score backfill"
Cohesion: 0.10
Nodes (26): statement_timeout(), fill_missing(), _call_fill(), _cooled(), _day(), _default_mlb(), _default_nba(), _default_nfl() (+18 more)

### Community 168 - "Push notifier and tickets"
Cohesion: 0.07
Nodes (32): test_push_live_refuses_and_does_not_ledger(), test_the_route_helper_only_sets_sport_when_it_is_unambiguous(), _msgs(), test_a_credentials_failure_disables_nobody(), test_a_request_level_rejection_accepts_nothing(), test_a_retired_device_is_named_for_disabling(), test_a_single_message_reply_may_be_a_bare_object(), test_a_ticket_that_is_not_an_object_is_not_a_delivery() (+24 more)

### Community 17 - "Discord units convention tests"
Cohesion: 0.29
Nodes (4): test_prob_only_picks_fall_back_to_the_settlement_price(), test_units_convention_matches_the_stated_rule(), _decimal_odds(), units_won()

### Community 171 - "NFL stake sizing and EV backtest"
Cohesion: 0.09
Nodes (23): american_to_decimal(), cover_probs(), ev_per_unit(), fit_margin_pmf(), kelly_fraction(), margin_pmf_for(), add_model_mu(), load() (+15 more)

### Community 172 - "nfl/live_model/tests/test_flow.py"
Cohesion: 0.05
Nodes (36): evaluate(), _infer_position(), main(), _pool_prior(), report(), _rows_for_market(), _to_states(), accrual_at() (+28 more)

### Community 173 - "tests/test_decide_on_calibrated.py"
Cohesion: 0.06
Nodes (19): _pick(), _pick_at(), test_a_calibrated_cut_is_paired_with_a_calibrated_decision(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(), test_a_genuinely_big_edge_still_fires_after_calibration(), test_a_hot_model_no_longer_fires_the_marginal_bet(), test_a_model_on_a_calibrated_cut_is_not_paused(), test_a_paused_model_never_fires_regardless() (+11 more)

### Community 176 - "NBA prop projection lab"
Cohesion: 0.09
Nodes (48): implied(), _logit(), bars(), bh_read(), blind(), boot(), by(), cal_ab() (+40 more)

### Community 178 - "NFL backfill resilience tests"
Cohesion: 0.12
Nodes (5): test_a_dropped_connection_is_retried(), test_an_http_error_is_NOT_retried(), test_it_gives_up_rather_than_looping_forever(), test_resume_probes_ONE_market_not_any_row(), test_resume_with_no_probe_market_skips_nothing()

### Community 181 - "tests/test_nfl_rule_2026_track.py"
Cohesion: 0.09
Nodes (28): classify(), fetch(), grade_rows(), is_void(), lead_days(), _load_nfl_model(), main(), opener_verdict() (+20 more)

### Community 182 - "tests/test_model_artifacts_load.py"
Cohesion: 0.09
Nodes (17): _git(), _gitignore_keep_pkls(), _ignored(), _manifest_keep_pkls(), _newest_per_model(), test_a_path_that_is_not_ignored_is_not_reported(), test_a_superseded_timestamped_pkl_is_ignored(), test_an_ignored_path_comes_back_byte_identical() (+9 more)

### Community 185 - "scripts/game_line_market_sweep.py"
Cohesion: 0.08
Nodes (22): _by_month(), collect_picks(), devig(), _gap_seconds(), grade(), implied(), iter_months(), load() (+14 more)

### Community 187 - "Market coverage probe tests"
Cohesion: 0.07
Nodes (17): candidate_markets(), _standard_markets(), test_a_two_sided_market_is_never_reported_one_sided(), test_an_all_line_leg_slip_does_not_claim_a_model(), test_it_asks_about_the_board_columns_that_are_permanently_blank(), test_it_reports_supported_but_empty_apart_from_unsupported(), test_no_market_is_asked_about_twice(), test_one_market_per_call_so_a_rejected_key_is_identified_exactly() (+9 more)

### Community 188 - "tests/test_pass_instrumentation.py"
Cohesion: 0.06
Nodes (11): test_a_dead_database_does_not_fail_the_step(), test_a_raised_failure_still_records_the_exception(), test_a_step_that_raises_is_still_TIMED(), test_a_step_that_raises_still_raises(), boom(), test_a_step_that_returns_false_records_a_REASON(), test_a_successful_step_records_a_duration(), test_every_step_name_in_the_dispatch_table_is_reachable() (+3 more)

### Community 190 - "tests/test_db_adapt_sql.py"
Cohesion: 0.09
Nodes (23): _adapt_sql(), _convert_params(), _convert_params_outside_literals(), _named(), test_a_block_comment_is_skipped_too(), test_a_colon_word_inside_a_comment_is_not_a_placeholder(), test_a_dash_dash_inside_a_literal_is_data_not_a_comment(), test_a_line_comment_ends_at_the_newline() (+15 more)

### Community 191 - "Calibration apply and live sweep"
Cohesion: 0.09
Nodes (16): apply_calibration(), fit_platt(), invert_calibration(), _logit(), _sigmoid(), main(), pairs_from(), recalibrate() (+8 more)

### Community 194 - "tests/test_model_calibration_agent.py"
Cohesion: 0.08
Nodes (10): test_column_migrations_run_every_pipeline_pass(), test_home_runs_are_no_longer_exempt_from_pausing(), test_the_agent_changes_nothing_on_its_own(), test_the_agent_sweeps_every_registered_model_except_live_ones(), test_the_catch_up_applies_column_migrations_first(), test_the_ddl_is_guarded_so_it_does_not_fire_pgrst_ddl_watch_every_sweep(), test_the_guard_asks_about_the_things_the_lockdown_sets(), test_the_review_rule_exempts_no_model() (+2 more)

### Community 195 - "tests/test_mobile_contrast_tokens.py"
Cohesion: 0.13
Nodes (30): _code_lines(), _ionicon_colors(), _lum(), _over(), _ratio(), _read(), _rgb(), test_badge_glyph_tracks_dynamic_type() (+22 more)

### Community 197 - "NBA stats ingestor"
Cohesion: 0.09
Nodes (22): backfill_nba_stats(), _build_game_id(), _build_game_rows(), _build_player_log_rows(), _build_team_stat_rows(), _fetch_league_game_log(), ingest_nba_game_log_for_date(), _ingest_season() (+14 more)

### Community 20 - "Probability calibration fit and schema"
Cohesion: 0.10
Nodes (19): demote(), ensure_schema(), _era_start(), fetch_graded(), fit_model(), fit_offset(), fit_pool(), _gap_pp() (+11 more)

### Community 201 - "Mobile bankroll card"
Cohesion: 0.20
Nodes (19): fieldFlow(), inv(), bankrollDraft(), bankrollFieldText(), canonical(), checkBankroll(), commitBankrollText(), editBankrollInput() (+11 more)

### Community 204 - "NFL prop feature engine"
Cohesion: 0.16
Nodes (11): _add_features(), build_nfl_prop_scoring_rows(), _cols(), derived_targets(), _load(), _nfl_season(), _pool_mask(), _read() (+3 more)

### Community 205 - "MLB prop market tests"
Cohesion: 0.09
Nodes (19): find_bets(), _q(), test_a_different_line_is_never_compared(), test_a_market_under_the_coverage_floor_is_excluded(), test_a_prop_the_sharp_book_did_not_price_is_counted_not_traded(), test_agreement_produces_no_bet(), test_an_equal_line_with_a_real_disagreement_is_a_bet(), test_devig_removes_the_hold_symmetrically() (+11 more)

### Community 206 - "tests/test_live_inning_gate_replay.py"
Cohesion: 0.12
Nodes (29): _grade(), _pair(), ts(), _refuse_tables(), _score_seen_at(), _game(), _price(), _scored() (+21 more)

### Community 21 - "NFL edge studies: luck gap and Wong teasers"
Cohesion: 0.03
Nodes (101): load_games(), main(), pivot_spreads(), pivot_totals(), am_to_dec(), at_lead(), boot_ci(), ev() (+93 more)

### Community 215 - "Live count tail probability tests"
Cohesion: 0.09
Nodes (12): _count_over_prob(), _nb1_over_prob(), _poisson_over_prob(), _setup(), test_an_artifact_wanting_an_unmapped_column_is_never_scored(), test_an_unknown_family_refuses_to_price_rather_than_falling_back(), test_every_mapped_model_can_be_built_from_the_map(), test_nb1_has_the_mean_it_claims_and_a_wider_variance() (+4 more)

### Community 216 - "Free pick cheaper book tests"
Cohesion: 0.10
Nodes (17): _pick(), test_a_pick_with_no_alternative_falls_back_to_draftkings(), test_every_offerable_book_has_a_human_name_on_both_surfaces(), test_the_free_card_names_the_cheaper_book(), test_the_free_card_query_reads_the_columns_it_renders(), test_the_good_to_clause_is_dropped_not_truncated_when_it_will_not_fit(), test_the_tweet_names_the_cheaper_book(), test_the_tweet_never_publishes_a_worse_price_than_draftkings() (+9 more)

### Community 219 - "tests/test_nfl_live_leader_state.py"
Cohesion: 0.14
Nodes (19): situation(), status(), test_a_conversion_try_is_skipped(), test_a_previous_quarters_play_is_not_the_state(), test_a_timeout_is_skipped_for_the_play_before_it(), test_after_a_scoring_play_nothing_is_evaluated(), test_after_the_kickoff_lands_the_receiver_has_the_ball(), test_an_ordinary_snap_is_evaluable_with_the_training_inputs() (+11 more)

### Community 221 - "tests/test_ncaaf_qb_ingestor.py"
Cohesion: 0.12
Nodes (22): _athlete_stats(), _comp_att(), parse_qb_game_stats(), _parse(), _payload(), _team(), test_athlete_stats_helper_is_category_scoped(), test_athlete_without_an_id_is_ignored() (+14 more)

### Community 224 - "NBA derivative market lab"
Cohesion: 0.09
Nodes (35): add_team(), am_to_dec(), bars_for(), bet_list(), blind(), boot_ci(), build_line_rows(), build_outcomes() (+27 more)

### Community 229 - "NBA prop model verification script"
Cohesion: 0.11
Nodes (30): decisions_for(), adv_from_log(), asof_roster(), blind_structured(), card_block(), collapse_report(), _compare(), log() (+22 more)

### Community 23 - "NFL in-play edge study 2024"
Cohesion: 0.09
Nodes (51): books_per_snapshot(), cell(), families(), fmt(), h1(), h1_calibration(), h1_frame(), h2() (+43 more)

### Community 232 - "Mobile pick category tests"
Cohesion: 0.11
Nodes (13): _block(), _config_scorable_ids(), _meta_ids(), _meta_types(), _read(), test_every_model_id_derives_its_own_declared_category(), test_every_scorable_model_has_a_label_in_the_app(), test_picks_idle_chrome_is_search_and_filters_only() (+5 more)

### Community 235 - "NCAAF feature engine tests"
Cohesion: 0.10
Nodes (19): shrink_hfa(), _assemble(), _stats(), test_assembly_carries_venue_context_and_hfa(), test_assembly_diffs_and_context(), test_backtester_and_scorer_dispatch_ncaaf_explicitly(), test_backtester_feature_vector_exempts_sparse_columns(), test_bulk_loads_both_markets_of_the_historical_line() (+11 more)

### Community 237 - "Discord price bound tests"
Cohesion: 0.11
Nodes (15): _dec(), test_a_field_without_a_bound_renders_without_the_clause(), test_a_model_with_no_own_ev_floor_is_bound_by_the_global_one(), test_a_price_floor_can_be_the_binding_gate(), test_a_rounded_bound_still_clears_the_bound_it_came_from(), test_even_money_is_plus_one_hundred(), test_no_bound_from_junk_rather_than_a_guess(), test_no_bound_when_the_edge_floor_is_unreachable() (+7 more)

### Community 238 - "nfl/live_model/tests/test_rush_attempt_pace.py"
Cohesion: 0.09
Nodes (16): _price(), test_a_line_he_has_already_passed_is_not_a_live_proposition(), test_a_missing_accrued_count_is_refused_not_treated_as_zero(), test_a_reachable_over_is_declined_rather_than_faded(), test_a_surge_requirement_reaches_a_price(), test_no_bet_before_a_pace_exists(), test_settlement_resolves_this_model_per_pick_not_per_model_id(), test_the_book_move_guard_covers_the_new_market() (+8 more)

### Community 240 - "tests/test_ncaaf_game_identity.py"
Cohesion: 0.12
Nodes (16): _add(), _conn(), _identity_sql(), _run(), test_a_clean_slate_reports_nothing(), test_a_non_fbs_fixture_is_not_reported(), test_a_phantom_opponent_is_detected_too(), test_a_real_doubleheader_is_not_a_duplicate() (+8 more)

### Community 242 - "data/ingestors/ncaaf_inplay_history.py"
Cohesion: 0.16
Nodes (17): _blank_row(), budget_for(), calls_in(), _floor5(), _get(), _iso(), main(), parse_shard() (+9 more)

### Community 243 - "MLB and WNBA stats ingestors and pitcher rebuild"
Cohesion: 0.03
Nodes (58): _go(), backfill_bullpen_stats(), backfill_mlb_stats(), backfill_pitcher_stats(), backfill_player_handedness(), _build_pitcher_rows(), _build_team_stats_rows(), _fetch_mlb_api_batting() (+50 more)

### Community 250 - "data/ingestors/nhl_boxscore.py"
Cohesion: 0.12
Nodes (16): _decision(), fill_missing(), _insert_absent(), _int(), _name(), parse_boxscore(), side_rows(), store_boxscore() (+8 more)

### Community 255 - "scripts/mlb_total_public_fade_topk.py"
Cohesion: 0.11
Nodes (19): ticket_bucket(), american_units(), bucket_win_rates(), build_candidates(), _fmt(), grade_under(), holdout_take(), load_db() (+11 more)

### Community 258 - "NFL wind card and opener sweep scripts"
Cohesion: 0.09
Nodes (18): bettable_books(), coverage_check(), expected_true_wind(), open_air_mask(), load_nfl_model(), boot_ci(), candidate_rows(), _load_backtest() (+10 more)

### Community 259 - "NFL player stats ingestor tests"
Cohesion: 0.26
Nodes (9): current_nfl_season(), parse_player_week_csv(), _csv(), test_all_zero_rows_are_skipped(), test_current_nfl_season_labels(), test_fractional_def_sacks_kept(), test_negative_yards_parse(), test_parse_qb_row() (+1 more)

### Community 260 - "tests/test_live_game_features.py"
Cohesion: 0.11
Nodes (19): compute_live_target(), half_innings_left(), parse_bases(), state_features(), test_build_live_state_row_merges_pregame_context(), test_build_live_state_row_unusable_state(), test_half_innings_left_bottom_ninth(), test_half_innings_left_extras_clamps_to_one() (+11 more)

### Community 261 - "tests/test_ncaaf_totals_regression.py"
Cohesion: 0.10
Nodes (14): total_over_prob(), test_artifact_kind_is_routed_by_the_scorer(), test_asymmetry_is_real_and_would_have_bitten(), test_extremes_are_clamped_away_from_certainty(), test_model_above_the_line_favours_the_over(), test_model_below_the_line_favours_the_under(), test_no_dk_total_means_skip_not_prob_only(), test_no_residuals_returns_one_half_not_a_confident_bet() (+6 more)

### Community 262 - "UFC feature engine and tests"
Cohesion: 0.13
Nodes (20): _age_years(), _assemble_ufc_features(), career_stats(), compute_ufc_target(), infer_five_rounds(), synthetic_round_total(), _fight(), _stats_pair() (+12 more)

### Community 263 - "Mobile pick CTA, NFL import and wind stake tests"
Cohesion: 0.04
Nodes (35): test_a_published_void_keeps_track_and_betslip(), test_a_tracked_void_reads_not_graded_and_detail_closes_when_over(), test_the_app_predicate_matches(), test_today_et_ignores_the_container_timezone(), _read(), _run(), test_a_stale_card_offers_no_bet(), test_a_stale_card_says_why_and_speaks_the_locked_price() (+27 more)

### Community 265 - "tests/test_best_line_sweep.py"
Cohesion: 0.16
Nodes (9): american_to_decimal(), units_at(), test_a_better_price_pays_more_than_the_dk_price(), test_a_loss_costs_one_unit_at_every_price(), test_a_push_is_flat(), test_a_retired_model_is_never_recommended_a_cut(), test_a_win_pays_the_stored_convention(), test_the_free_half_is_worth_more_than_the_dk_price() (+1 more)

### Community 266 - "NCAAF in-play history backtest"
Cohesion: 0.10
Nodes (18): build_candidates(), decide(), first_signals(), _fmt(), grade(), load_snapshots(), main(), odds_from_rows() (+10 more)

### Community 267 - "tests/test_ncaaf_qb_features.py"
Cohesion: 0.12
Nodes (24): build_qb_team_features(), load_qb_games(), merge_qb_features(), _feat(), _frame(), _games(), _qb_rows(), _qb_team() (+16 more)

### Community 271 - "tests/test_line_clv.py"
Cohesion: 0.06
Nodes (11): test_runner_captures_stdout_from_the_script_main(), test_sport_and_market_are_bounded(), test_the_declared_key_is_present_and_valid(), test_the_runner_imports_the_script_main_not_a_shell(), _load(), test_a_line_that_held_is_exactly_zero_not_none(), test_a_missing_close_is_not_a_zero(), test_a_side_that_cannot_be_oriented_returns_none_rather_than_guessing() (+3 more)

### Community 272 - "tests/test_mobile_team_detail.py"
Cohesion: 0.11
Nodes (15): _read(), test_every_team_page_read_names_its_relation_literally(), test_next_game_is_earliest_in_the_window_not_tonights_date(), test_no_paper_trading_copy(), test_public_betting_policy_migration_exists_and_is_select_only(), test_recent_games_are_scoped_by_sport(), test_results_are_units_never_dollars(), test_sharp_gap_is_no_vig_vs_no_vig() (+7 more)

### Community 276 - "NBA ESPN box score parser"
Cohesion: 0.06
Nodes (32): box_team_totals(), et_date(), nba_team(), _no_minutes(), parse_nba_box(), parse_nba_dnp(), parse_nba_scoreboard(), _played() (+24 more)

### Community 279 - "NBA injury report garbled row tests"
Cohesion: 0.25
Nodes (8): garbled_note(), _rows(), test_a_report_whose_cells_do_not_line_up_with_its_header_is_not_stored(), test_all_players_available_is_a_team_row_not_the_tail_of_a_reason(), test_current_layout_2026(), test_name_key_drops_accents_punctuation_and_suffixes(), test_nine_column_layout_2019(), test_seven_column_layout_2020()

### Community 283 - "NCAAF play-by-play state builder"
Cohesion: 0.13
Nodes (12): main(), out_path(), _classify(), classify_report(), load_pbp(), load_platform_games(), pace_report(), _repair_day_offsets() (+4 more)

### Community 286 - "Kalshi ladder recording and prop ingestor tests"
Cohesion: 0.05
Nodes (18): _event_date(), _player(), record_ladders(), test_a_kalshi_outage_cannot_break_the_pass(), test_a_run_is_idempotent_within_its_snapshot(), test_one_snapshot_timestamp_for_the_whole_run(), test_the_recorder_is_scheduled_on_the_pipeline_role(), test_the_recorder_keeps_raw_prices_not_a_filtered_ladder() (+10 more)

### Community 287 - "tests/test_model_calibration_check.py"
Cohesion: 0.11
Nodes (11): _calibration_sql(), test_a_flagged_model_is_named_eligible_or_not(), test_a_thin_model_is_still_excluded_rather_than_accused(), test_eligibility_notes_must_not_sink_the_gap_check(), test_it_grades_the_calibrated_probability_not_the_raw_one(), test_it_joins_picks_to_reach_the_calibrated_column(), test_the_check_has_a_skip_budget_that_survives_a_regime_change(), test_the_probability_floor_applies_to_the_decision_number_too() (+3 more)

### Community 289 - "tests/test_ncaaf_player_stats_ingestor.py"
Cohesion: 0.18
Nodes (17): parse_player_game_stats(), _cat(), _parse(), _payload(), _team(), test_a_game_missing_from_the_id_map_is_skipped_not_guessed(), test_a_player_gets_one_row_across_every_category(), test_a_player_with_nothing_we_track_is_skipped() (+9 more)

### Community 29 - "Public read access grants"
Cohesion: 0.03
Nodes (59): all_readable(), closed_tables(), lock_down(), lock_down_sql(), write_verbs_for(), ensure_table(), fetch_date(), main() (+51 more)

### Community 290 - "First pitch time trust tests"
Cohesion: 0.06
Nodes (17): test_a_late_start_is_believed_because_it_is_real(), test_a_missing_actual_start_falls_back_to_the_schedule(), test_both_missing_still_fails_open(), test_every_is_pregame_snapshot_caller_passes_first_pitch(), test_it_never_overwrites_commence_time(), test_the_actual_start_wins_over_the_schedule(), test_the_backfills_in_play_marker_prefers_the_actual_start(), test_the_boundary_itself_is_pregame() (+9 more)

### Community 294 - "UFC stats ingestor and dashboard app"
Cohesion: 0.06
Nodes (20): _fmt_et_time(), get_conn(), query(), backfill_ufc_stats(), _build_ufc_game_id(), _fetch_event(), _fetch_event_list(), _fetch_fight() (+12 more)

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
Nodes (13): test_a_retired_game_model_is_in_no_feature_map(), test_a_retired_model_is_in_no_registry_and_no_threshold_dict(), test_a_retired_prop_has_no_feature_map_and_no_training_label(), test_a_retired_sport_is_not_still_health_checked(), test_paused_nfl_props_still_in_prop_models_and_thresholds(), test_retired_prop_picks_still_settle_on_their_own_stat(), test_ten_nfl_distributional_props_are_paused(), test_the_app_mirrors_the_same_set() (+5 more)

### Community 306 - "NBA schedule features"
Cohesion: 0.12
Nodes (10): _counted_schedule(), from_cache(), game_schedule_features(), haversine_miles(), home_bases(), _offsets(), previous_game_load(), team_schedule_features() (+2 more)

### Community 313 - "Best line threshold sweep analysis"
Cohesion: 0.29
Nodes (5): analyse(), split(), _basis(), _cut(), fetch()

### Community 317 - "Latest line state and Citadel migration cluster tests"
Cohesion: 0.05
Nodes (45): can_scratch(), env_dsn(), _free_port(), pg_bin(), scratch_cluster(), as_app(), db(), dsn() (+37 more)

### Community 318 - "tests/test_live_record_start_views.py"
Cohesion: 0.09
Nodes (12): _body(), _code(), test_both_published_views_carry_the_live_date_gate(), test_it_runs_after_the_migration_that_used_to_own_the_daily_view(), test_migration_is_one_statement(), test_migration_is_registered_with_the_worker_runner(), test_neither_view_reads_the_sweep_universe(), test_no_ddl_outside_the_guarded_branches() (+4 more)

### Community 319 - "tests/test_model_quality.py"
Cohesion: 0.10
Nodes (9): _bet(), test_high_public_pct_on_a_fade_publisher_counts_as_a_fade(), test_low_public_pct_on_the_pick_side_counts_as_a_fade(), test_majority_share_warns_when_not_unanimous(), test_meta_steps_exclude_model_quality(), test_pipeline_step_never_fails_on_crit(), test_pipeline_step_never_fails_on_exception(), test_side_aliases_collapse_to_the_same_direction() (+1 more)

### Community 323 - "NBA prop window scheduling tests"
Cohesion: 0.21
Nodes (12): _fires(), _jobs(), test_a_tick_fetches_exactly_the_window_games_then_decides_closes_and_publishes(), test_a_tick_with_nothing_near_spends_nothing(), test_a_tick_with_only_a_close_due_does_not_return_early(), test_a_tick_with_only_a_game_near_tip_publishes_and_spends_nothing(), test_a_tick_with_only_projections_due_spends_no_api_call(), test_every_tip_time_gets_a_look_inside_its_window() (+4 more)

### Community 326 - "tests/test_api_call_rollup.py"
Cohesion: 0.06
Nodes (15): test_a_fold_can_never_lower_a_stored_total(), test_a_new_process_does_not_prune_on_its_first_flush(), test_prune_rolls_up_before_it_deletes(), test_the_daily_table_is_created_and_locked_down(), test_the_daily_table_keys_on_day_api_and_source(), test_the_rollup_groups_by_eastern_day_not_utc(), test_the_rollup_reads_only_yesterday_and_today(), test_the_rollup_survives_a_failure_without_blocking_the_prune() (+7 more)

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

### Community 336 - "NFL live backtest harness replay"
Cohesion: 0.13
Nodes (11): align_states(), build_team_map(), _game_index(), kill_verdict(), load_cached_snapshots(), main(), replay(), _state_at() (+3 more)

### Community 339 - "tests/test_service_role_split.py"
Cohesion: 0.13
Nodes (12): _all_job_ids(), _sched(), test_an_unknown_role_runs_everything(), test_every_add_job_call_passes_an_id(), test_every_job_is_owned_by_exactly_one_role(), test_role_filtering_wraps_add_job_once(), test_the_always_on_jobs_run_on_every_role(), test_the_default_preserves_the_single_container() (+4 more)

### Community 343 - "tests/test_http_timeout_floor.py"
Cohesion: 0.11
Nodes (11): install_timeout_floor(), _call(), clean_requests(), test_a_call_with_no_timeout_gets_one(), test_an_explicit_timeout_is_never_overridden(), test_installing_twice_is_a_no_op(), test_the_deadline_is_env_overridable(), test_the_deadline_survives_telemetry_being_turned_off() (+3 more)

### Community 345 - "NCAAF totals lead and consensus gate"
Cohesion: 0.17
Nodes (16): fmt(), grade(), load_closes(), main(), match(), build_lead_table(), first_cross(), fmt() (+8 more)

### Community 346 - "scripts/nfl_edge_cache.py"
Cohesion: 0.22
Nodes (14): _conn(), copy_main_local(), _df(), _games_2026(), log(), main(), nflverse_misc(), nflverse_pbp() (+6 more)

### Community 347 - "Paused model assessment tests"
Cohesion: 0.10
Nodes (15): _auto_paused_models(), active_era(), assess(), _half(), fetch(), grade(), main(), sweep() (+7 more)

### Community 351 - "tests/test_nfl_injury_ingest.py"
Cohesion: 0.11
Nodes (9): _fetch_nfl_espn_team_ids_core(), _nfl_espn_team_to_abbrev(), _fake_fetch(), test_core_nfl_listing_failure_returns_empty(), test_core_nfl_team_ids_resolve_lar_and_wsh_to_ours(), test_injury_fetch_raises_the_page_limit(), test_nfl_active_rows_are_dropped_and_out_keeps_espn_date(), test_nfl_name_join_uses_our_abbrevs_not_espns() (+1 more)

### Community 352 - "NHL prop odds alternate line tests"
Cohesion: 0.07
Nodes (21): due(), _book(), test_a_200_on_both_calls_merges_the_alternate_lines(), fake_fetch(), test_a_game_first_priced_inside_the_final_window_gets_nothing_more(), test_a_game_first_priced_inside_the_window_gets_one_decision_snapshot(), test_a_game_with_nothing_stored_is_owed_its_open(), test_a_moved_featured_line_keeps_the_old_number_under_the_alternate_key() (+13 more)

### Community 355 - "Live honest cut script"
Cohesion: 0.33
Nodes (9): bets_split(), _fmt(), _grid(), main(), _print_grid(), run_mlb(), run_ncaaf(), _summ() (+1 more)

### Community 357 - "Injury fetch speed and cache tests"
Cohesion: 0.09
Nodes (8): _clear_cache(), test_a_dead_database_leaves_the_cache_empty_not_broken(), test_a_failed_lookup_is_not_cached(), test_a_known_athlete_costs_no_request(), test_one_team_failing_does_not_lose_the_others(), test_output_order_follows_the_team_list_not_completion_order(), test_the_cache_seeds_from_our_own_stored_injuries(), test_the_pool_is_small_because_espn_has_blocked_us_twice()

### Community 359 - "NBA props model core tests"
Cohesion: 0.10
Nodes (17): apply_calibration(), exclude_taken(), p_push(), stake(), team_spread(), regrade(), _synthetic_pairs(), test_a_proposition_another_model_bets_is_removed_on_every_line_and_side() (+9 more)

### Community 361 - "tests/test_config.py"
Cohesion: 0.08
Nodes (8): test_an_own_floor_does_not_take_a_model_off_the_calibration_map(), test_every_model_carries_its_own_thresholds(), test_every_own_floor_names_a_live_model(), test_models_on_own_probability_is_not_derived_from_the_floor_dict(), test_no_own_floor_tightens_a_model_past_the_global_floor(), test_only_a_market_priced_model_carries_a_negative_floor(), test_own_ev_floor_and_model_min_ev_stay_disjoint(), test_the_models_the_global_floor_silently_removed_can_bet_again()

### Community 366 - "Kalshi game market recorder"
Cohesion: 0.07
Nodes (17): event_code(), event_date(), kalshi_school(), _num(), probe(), record_game_markets(), resolve_events(), rows_for() (+9 more)

### Community 367 - "Database URL doctor tests"
Cohesion: 0.16
Nodes (17): diagnose(), bad(), _safe(), _fails(), _levels(), test_a_correct_url_reports_no_failures(), test_bare_postgres_on_a_DIRECT_host_is_fine(), test_bare_postgres_on_a_pooler_host_is_named() (+9 more)

### Community 368 - "tests/test_mlb_pbp_ingestor.py"
Cohesion: 0.16
Nodes (15): _bases_after_from_matchup(), parse_game_plays(), parse_play(), _split_event_type(), test_bases_empty_matchup(), test_bases_with_runners(), test_parse_game_plays_empty_feed(), test_parse_game_plays_walks_full_inning() (+7 more)

### Community 369 - "UFC fighter name resolution"
Cohesion: 0.17
Nodes (10): resolve_slug(), test_a_generational_suffix_resolves_either_way(), test_a_near_miss_is_not_a_match(), test_a_reversed_name_order_resolves(), test_a_shared_surname_alone_is_not_a_match(), test_an_ambiguous_token_set_resolves_to_nothing(), test_an_empty_or_tokenless_name_is_safe(), test_an_exact_slug_still_wins_untouched() (+2 more)

### Community 37 - "EV floor and cut replay sweeps"
Cohesion: 0.20
Nodes (15): _era(), grade(), wilson(), _cell(), _decimal(), fetch_rows(), grade(), halves() (+7 more)

### Community 370 - "UFC CSV fight loader"
Cohesion: 0.10
Nodes (22): _aggregate_stats(), backfill_ufc_csv(), build_events(), build_fighter_index(), _heal_window_lo(), ingest_ufc_results_for_date_csv(), _kd_int(), load_fighter_profiles_from_csv() (+14 more)

### Community 371 - "tests/test_team_stats_asof_invariants.py"
Cohesion: 0.08
Nodes (14): impossible_games_played(), _played_actual(), test_a_missing_count_is_reported_not_silently_passed(), test_an_honest_row_passes(), test_claiming_fewer_games_than_played_is_fine(), test_feb_gp_climbing_vs_zero_regular_season_still_fails(), test_mlb_twin_codes_do_not_false_crit(), test_mlb_twin_reverse_lookup_also_resolves() (+6 more)

### Community 373 - "NCAAF ESPN feed summary state"
Cohesion: 0.17
Nodes (16): check_feed_assumptions(), _competitors(), _count_plays(), _dig(), extract_live_events(), extract_summary_state(), _int(), _num() (+8 more)

### Community 375 - "Refresh pass step ordering tests"
Cohesion: 0.10
Nodes (13): _order(), test_a_parallel_step_that_fails_is_still_recorded(), test_no_sequential_step_runs_while_a_parallel_group_is_open(), test_opening_signals_follows_every_scorer(), test_parlay_follows_opening_signals(), test_scoring_follows_every_ingest(), test_settle_follows_every_results_ingest(), test_sync_thresholds_follows_migrations_and_precedes_scoring() (+5 more)

### Community 376 - "CFBD verification script"
Cohesion: 0.17
Nodes (9): parse_teams(), _check(), _lines_coverage(), main(), _null_report(), _sample_keys(), test_parse_teams_all_schools_pull_never_defaults_to_fbs(), test_parse_teams_joins_alt_names() (+1 more)

### Community 382 - "UFC etag cache tests"
Cohesion: 0.09
Nodes (15): _cached_etag(), _etag_cache_path(), mirror_unchanged(), _store_etag(), test_mirror_unchanged_is_conservative_when_it_cannot_tell(), _clean_env(), test_a_mounted_volume_is_preferred_over_tmp(), test_a_round_trip_actually_persists() (+7 more)

### Community 383 - "NFL live remaining-score engine training"
Cohesion: 0.17
Nodes (10): fit(), load_states(), main(), walk_forward_oos(), build_features(), features_from_state(), load_models(), predict_remaining() (+2 more)

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
Cohesion: 0.11
Nodes (11): sched(), test_a_fresh_savant_does_not_suppress_the_calibration_catch_up(), test_a_missing_sweeps_table_counts_as_stale(), test_a_recent_sweep_does_not(), test_an_old_sweep_triggers_the_catch_up(), test_model_calibration_belongs_to_the_pipeline_service(), test_ownership_is_checked_per_job(), test_the_catch_up_creates_the_review_tables_on_boot() (+3 more)

### Community 392 - "tests/test_live_game_state_poller.py"
Cohesion: 0.17
Nodes (16): _detect_triggers(), _is_active_or_starting_soon(), test_active_in_progress_game_is_active(), test_combined_changes_fire_all_relevant_triggers(), test_due_up_change_fires_due_up_change(), test_final_game_is_not_active(), test_identical_state_fires_no_triggers(), test_inning_half_change_fires_inning_change() (+8 more)

### Community 394 - "Discord restate signal tests"
Cohesion: 0.13
Nodes (10): _restate_env(), _restate_signals(), test_a_failed_restate_ledgers_nothing_so_it_retries(), test_a_rate_limited_restate_leaves_nothing_half_posted(), test_restate_deletes_the_stale_post_when_the_id_is_known(), test_restate_fires_exactly_once(), test_restate_never_fires_for_an_unlisted_date(), test_restate_posts_a_labelled_correction_with_the_new_stakes() (+2 more)

### Community 396 - "NFL Kalshi fetch and price floor grid"
Cohesion: 0.21
Nodes (6): candles(), get(), map_games(), paged(), parse_event(), probe()

### Community 398 - "CLV card price taken tests"
Cohesion: 0.13
Nodes (17): _app(), _clv_card(), _server(), test_a_label_book_nfl_pick_compares_its_line_with_that_book(), test_a_recorded_book_differs_from_the_derived_one(), test_the_app_prefers_the_recorded_book_at_the_derived_price(), test_the_app_prices_every_row_as_the_server_grades_it(), test_the_card_prints_the_price_taken_not_draftkings() (+9 more)

### Community 399 - "NFL live leader model tests"
Cohesion: 0.12
Nodes (14): art(), _d(), _raw(), test_600_seconds_and_both_lead_ends_are_inside(), test_a_flipped_spread_sign_changes_the_decision(), test_a_qualifying_state_bets_the_leader_at_its_price(), test_artifact_identity_training_and_rule(), test_band_matches_training_leader_view_on_nflverse_sign() (+6 more)

### Community 40 - "NFL wind edge studies"
Cohesion: 0.10
Nodes (42): band_table(), bh(), build_priced(), decisions_2026(), decisions_hist(), era5_hourly(), fc_at_decision(), fetch_2026() (+34 more)

### Community 400 - "Mobile paused catalog tests"
Cohesion: 0.16
Nodes (11): _block(), _read(), test_paused_picks_reach_the_all_board_only_and_labelled(), test_stats_add_pick_refuses_a_paused_model(), test_the_behavioural_checks_pass(), test_the_bet_type_picker_filters_paused_models(), test_the_custom_model_picker_is_three_bet_types(), test_the_models_list_filters_paused_models() (+3 more)

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

### Community 411 - "Mobile accessibility verify tests"
Cohesion: 0.12
Nodes (12): _read(), _run(), test_audited_targets(), test_betslip_bar_inset_wiring(), test_h9_rows_reach_44pt_inside_their_bounds(), test_pick_card_label_is_complete(), test_reach_frame_and_add_bet_hint(), test_sheet_backdrops_do_not_wrap_the_sheet() (+4 more)

### Community 413 - "tests/test_nfl_prop_thresholds.py"
Cohesion: 0.11
Nodes (8): test_live_webhook_map_reads_the_per_sport_env_vars(), cfg(), test_no_nfl_prop_market_is_back_on_the_uniform_placeholder(), test_one_bad_date_does_not_cost_the_others(), test_the_prop_window_has_exactly_one_declaration(), test_the_scorer_step_covers_the_whole_window_not_one_date(), fake(), test_the_three_threshold_dicts_agree_for_every_nfl_prop_market()

### Community 414 - "tests/test_nhl_research_job.py"
Cohesion: 0.15
Nodes (11): test_a_dump_argument_is_refused(), test_a_model_must_be_a_real_spec(), test_a_season_must_be_a_priced_one(), test_an_unknown_script_is_refused(), test_an_unknown_top_level_key_is_refused(), test_every_runnable_module_has_a_main(), test_every_runnable_module_writes_no_database_row(), test_the_artifact_grade_names_the_rule_production_runs() (+3 more)

### Community 415 - "tests/test_settlement_timing.py"
Cohesion: 0.16
Nodes (8): test_capture_clv_requires_the_game_to_have_started(), test_future_kickoffs_are_not_treated_as_started(), test_game_log_skips_per_game_not_per_date(), test_started_games_are_recognised_in_every_stored_format(), test_ufc_poll_uses_the_etag_gate_and_the_daily_run_does_not(), test_unparseable_timestamps_yield_none_rather_than_a_guess(), test_z_and_offset_forms_are_the_same_instant_but_not_the_same_string(), _as_utc()

### Community 417 - "tracking/model_quality.py"
Cohesion: 0.13
Nodes (15): record_exclusion_sql(), test_volume_spike_vs_median(), test_volume_without_history_is_skipped_not_flagged(), test_the_exclusion_sql_is_a_conjunction_of_negations(), _job_model_quality(), detect_volume_spike(), ensure_schema(), _group() (+7 more)

### Community 418 - "NFL weather cache import"
Cohesion: 0.15
Nodes (10): main(), rows_from_file(), source_for(), stadium_from_name(), _INSERT_PLACEHOLDERS(), test_a_non_issued_or_empty_payload_yields_nothing(), test_every_hour_becomes_one_row_in_column_order(), test_stored_files_reads_the_marker_back() (+2 more)

### Community 42 - "DataGolf ingestor and NHL SBR archive"
Cohesion: 0.03
Nodes (68): _american(), backfill_golf_rounds(), build_game_id(), _dg_get(), _earliest_commence_iso(), event_slug(), ingest_golf_field(), ingest_golf_odds() (+60 more)

### Community 421 - "Paused rows, prop lead ceiling and NHL regulation tests"
Cohesion: 0.06
Nodes (22): _calibrated(), _nfl_prop_too_early(), _iso(), test_a_kickoff_beyond_the_ceiling_is_too_early(), test_a_started_or_unknown_kickoff_is_not_too_early(), test_the_boundary_is_inclusive_at_the_ceiling(), test_the_scorer_and_the_card_read_ONE_constant(), test_the_scorer_loop_actually_applies_the_ceiling() (+14 more)

### Community 423 - "First pitch guard tests"
Cohesion: 0.11
Nodes (7): test_capture_compares_the_picks_own_clock_not_the_capture_clock(), test_capture_fails_open_on_a_missing_timestamp(), test_delivery_fails_open_too(), test_health_check_uses_the_same_first_pitch_bound_as_discord(), test_mixed_timestamp_shapes_are_parsed_not_string_compared(), test_the_dry_run_count_uses_the_same_predicate_as_the_insert(), test_the_restatement_path_is_deliberately_not_guarded()

### Community 425 - "NFL odds cache import to Supabase"
Cohesion: 0.12
Nodes (9): _allowed(), _data_dirs(), test_a_rerun_after_the_resolver_improves_adds_only_the_gap(), test_every_buying_ingestor_keys_its_resume_on_a_source_marker(), test_no_undeclared_data_store_on_disk(), test_the_importer_resolves_a_postponed_game(), test_the_importer_still_refuses_an_event_with_no_game(), test_the_nfl_odds_cache_has_an_importer() (+1 more)

### Community 426 - "tests/test_health_check_observe.py"
Cohesion: 0.14
Nodes (10): _crit(), fake(), test_a_crit_does_not_fail_the_observe_path(), test_a_crit_still_fails_the_daily_step(), test_an_exception_does_not_fail_the_observe_path(), test_daily_syncs_thresholds_after_view_migrations(), test_it_still_runs_the_check_when_observing(), test_ok_is_identity_in_both_modes() (+2 more)

### Community 429 - "CFBD team game stats parsing tests"
Cohesion: 0.12
Nodes (12): parse_team_game_stats(), _possession_seconds(), _split_ratio(), _to_int(), test_an_fcs_name_that_extends_an_fbs_school_passes_through_unresolved(), test_parse_team_game_stats_builds_one_row_per_team(), test_parse_team_game_stats_skips_games_missing_from_the_id_map(), test_plays_is_none_when_neither_attempt_stat_is_present() (+4 more)

### Community 430 - "Health check deliverability tests"
Cohesion: 0.11
Nodes (10): test_a_game_date_inside_the_window_counts(), test_a_lookahead_commence_counts_even_when_game_date_is_outside(), test_a_signal_locked_after_first_pitch_was_never_deliverable(), test_a_signal_locked_before_first_pitch_still_counts(), test_a_signal_locked_exactly_at_first_pitch_counts(), test_a_started_game_outside_the_window_does_not_count(), test_it_fails_toward_noticing(), test_mixed_timestamp_shapes_are_parsed_not_string_compared() (+2 more)

### Community 431 - "tests/test_pick_lock_is_on_picks.py"
Cohesion: 0.16
Nodes (9): _between(), _sql(), test_a_bet_is_still_never_re_scored(), test_only_a_bet_locks_a_pair(), test_the_cleanup_covers_the_whole_look_ahead_window(), test_the_cleanup_never_touches_a_started_game_or_a_live_row(), test_the_lock_is_no_longer_ncaaf_specific(), test_the_prop_and_live_locks_are_unchanged() (+1 more)

### Community 438 - "Slate concentration and fade risk checks"
Cohesion: 0.16
Nodes (12): _fade_slate(), test_a_mixed_slate_is_ok(), test_all_home_ncaaf_slate_is_flagged_without_mlb_hardcoding(), test_all_unders_public_fade_risk_is_crit(), test_all_unders_public_fade_slate_is_crit(), test_fade_in_the_model_id_is_sport_agnostic(), test_thin_slate_is_not_a_finding(), test_unanimous_but_small_slate_is_warn_not_crit() (+4 more)

### Community 439 - "tests/test_team_stats_asof_invariants.py"
Cohesion: 0.15
Nodes (10): build_rows(), _game(), test_a_row_never_includes_its_own_date(), test_counts_accumulate_across_dates(), test_every_emitted_column_exists_in_the_real_table(), test_every_sport_uses_its_own_scoring_noun(), test_home_and_away_splits_use_only_the_relevant_games(), test_last_n_is_a_rolling_window_not_a_season_constant() (+2 more)

### Community 440 - "NFL halftime edge study"
Cohesion: 0.29
Nodes (13): backfill_cost(), bets(), bh(), clean_2h(), fmt(), forward_2026(), hdr(), _line_models() (+5 more)

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

### Community 457 - "NCAAF outcome edge scan"
Cohesion: 0.19
Nodes (12): _cell(), ecdf_prob_positive(), implied(), load_ml_prices(), main(), payout(), predict_all(), _print_cells() (+4 more)

### Community 458 - "Live monitor dashboard cache and docs"
Cohesion: 0.13
Nodes (10): age(), cached(), clear(), test_cache_raises_when_it_has_nothing_to_fall_back_on(), test_cache_reports_age(), test_cache_serves_stale_rather_than_failing(), boom(), test_cache_serves_within_ttl_and_recomputes_after() (+2 more)

### Community 46 - "Worker job queue and CFBD ingestor"
Cohesion: 0.02
Nodes (67): derive_first_pitch(), backfill_savant_stats(), _df_to_rows(), _fetch_savant_csv(), _get_col(), _normalize_name(), _parse_pct(), run_savant_ingestor() (+59 more)

### Community 460 - "scripts/ncaaf_search/situational_spots.py"
Cohesion: 0.18
Nodes (7): is_bowl_game(), build_spots(), evaluate(), load_team_games(), main(), wilson(), test_is_bowl_game()

### Community 462 - "Threshold review worker-only tests"
Cohesion: 0.12
Nodes (7): _quiet(), rule_only(), test_both_review_tables_are_declared_worker_only(), test_every_pause_check_in_the_scorer_goes_through_the_helper(), test_it_never_unpauses(), test_the_announce_does_not_claim_a_pause(), test_the_review_cannot_write_a_pause_even_when_enabled()

### Community 463 - "Monitoring server tests"
Cohesion: 0.08
Nodes (27): _drain(), _enqueue(), _flush_on_exit(), install(), instrumented(), _now(), _patch_curl_cffi(), instrumented() (+19 more)

### Community 465 - "nfl/scripts/backtest_opener.py"
Cohesion: 0.24
Nodes (9): boot(), by_season(), exp_win(), load(), main(), price(), report(), residuals() (+1 more)

### Community 467 - "MLB retrain freeze tests"
Cohesion: 0.12
Nodes (8): test_import_time_flag_follows_marker_file(), test_marker_or_env_lifts_the_freeze(), test_mlb_prop_market_sweep_is_documented_exempt(), test_mlb_retrain_refused_while_incomplete(), test_mlb_threshold_sweeps_call_the_guard(), test_non_mlb_sports_are_not_gated(), test_repo_marker_file_is_present(), test_trainer_calls_the_guard()

### Community 468 - "tests/test_latest_odds_views.py"
Cohesion: 0.25
Nodes (13): _app_columns(), _function(), test_every_log_table_has_its_insert_trigger_and_the_odds_tables_an_update_trigger(), test_every_view_reads_its_state_table_and_never_the_log(), test_no_pending_view_migration_re_creates_these_views_over_the_log(), test_the_dk_view_returns_the_apps_columns_in_order(), test_the_exclusions_survived_the_move(), test_the_game_view_returns_the_apps_columns_in_order() (+5 more)

### Community 469 - "Multi-book odds tests"
Cohesion: 0.15
Nodes (7): _prop_markets(), test_draftkings_is_always_first_line_shop_book(), test_prop_bookmaker_defaults_to_draftkings(), test_prop_rows_are_stamped_with_their_bookmaker(), test_prune_never_touches_the_scoring_book(), test_prune_predicates_date_by_game_not_snapshot(), test_same_player_at_two_books_does_not_merge_prices()

### Community 472 - "NBA schedule ingestor and tests"
Cohesion: 0.20
Nodes (11): ot_periods(), schedule_rows(), season_str(), _tv(), _row(), test_a_late_west_coast_tip_keeps_its_eastern_date(), test_an_undecided_playoff_slot_is_skipped(), test_game_type_is_read_from_the_first_three_digits() (+3 more)

### Community 473 - "tests/test_nfl_prop_settle_name_fallback.py"
Cohesion: 0.27
Nodes (10): _never(), _row(), test_a_first_name_the_stat_log_spells_differently_still_matches(), test_a_scratched_player_is_not_graded_on_a_teammate_with_his_initial(), test_a_spelling_the_log_already_knows_is_a_scratch_not_a_spelling(), test_another_game_and_another_initial_never_match(), test_first_name_rule(), test_two_candidates_is_a_miss_not_a_guess() (+2 more)

### Community 474 - "NFL recap waits for box scores tests"
Cohesion: 0.17
Nodes (8): _daily(), _job_body(), test_a_malformed_date_is_refused_before_anything_runs(), test_nfl_box_scores_are_ingested_before_settle(), test_nfl_finals_still_precede_the_box_scores(), test_the_job_does_not_read_rowcount_off_the_cursor(), test_the_job_only_clears_its_own_two_ledger_kinds(), test_the_job_posts_both_surfaces_through_the_ordinary_paths()

### Community 476 - "tests/test_transaction_pooler.py"
Cohesion: 0.19
Nodes (8): _transaction_endpoint(), test_a_direct_connection_is_left_alone(), test_a_local_postgres_is_left_alone(), test_a_supabase_session_url_becomes_the_transaction_url(), test_it_is_idempotent(), test_only_the_port_changes(), test_the_escape_hatch_works(), test_the_job_queue_still_gets_session_mode()

### Community 477 - "tests/test_espn_nhl_probables.py"
Cohesion: 0.15
Nodes (7): fetch_espn_nhl_probables(), parse_probable(), _team_abbrev(), test_fetch_fail_open(), test_fetch_uses_injected_fetch_and_keys_by_our_abbrev(), test_parse_probable_joins_display_name_to_our_abbrev(), test_parse_probable_skips_missing_name_or_slot()

### Community 480 - "Team stats as-of invariant tests"
Cohesion: 0.16
Nodes (8): seasons_with_too_few_snapshots(), test_a_real_series_passes(), test_a_single_snapshot_season_is_flagged(), test_a_two_snapshot_season_is_flagged(), test_mlb_twin_alias_map_matches_sbr_canon(), test_ncaaf_shaped_weekly_snapshots_pass(), test_the_guard_is_wired_so_protected_seasons_are_REMOVED(), test_the_guard_uses_the_same_threshold_as_the_invariant()

### Community 483 - "NBA injury report slot dates"
Cohesion: 0.17
Nodes (9): pre_tip_slot(), previous_report(), slots_for_date(), tips_by_date(), write_report(), test_format_switch_is_measured_and_both_are_probed_around_it(), test_hourly_dates_get_sixteen_hourly_slots(), test_pre_tip_slot_is_strictly_before_the_tip() (+1 more)

### Community 484 - "Declared worker job validation tests"
Cohesion: 0.15
Nodes (7): _declared(), test_an_explicit_run_date_must_be_a_real_iso_date(), test_declared_keys_are_unique(), test_every_declared_job_names_a_registered_type(), test_every_declared_job_validates(), test_no_run_date_means_the_module_resolves_it(), test_the_validator_drops_unknown_args()

### Community 487 - "supabase/functions/sharpsports/index.ts"
Cohesion: 0.30
Nodes (13): americanFromBetSlip(), asArray(), createContext(), isSettled(), json(), pick(), pullAndUpsert(), readBets() (+5 more)

### Community 490 - "UFC fighter slug tests"
Cohesion: 0.15
Nodes (10): _home_win_for_row(), slugify_fighter(), test_alias_makes_both_sources_agree(), test_aliases_do_not_touch_unmapped_names(), test_confirmed_aliases_resolve_to_ufcstats_slug(), test_resolve_anchor_matches_every_real_name_variant(), test_resolve_anchor_refuses_every_real_stale_booking_on_its_own(), test_slugify_accents_and_punctuation() (+2 more)

### Community 491 - "MLB game market and public fade cards"
Cohesion: 0.09
Nodes (21): load_latest_quotes(), edge_floor(), max_per_slate(), publish_enabled(), rank_kind(), under_odds_band(), main(), publish() (+13 more)

### Community 495 - "tests/test_worker_deps.py"
Cohesion: 0.22
Nodes (4): _requirements(), test_dashboard_packages_are_not_on_the_worker(), test_only_the_dashboard_imports_them(), test_the_worker_asks_for_the_cpu_build_of_xgboost()

### Community 499 - "Price floor and threshold sweep"
Cohesion: 0.08
Nodes (19): min_odds_for(), _blocked_by_min_odds(), _apply_price_floor(), test_a_pick_with_no_price_is_never_blocked_by_the_floor(), test_an_explicit_floor_wins_in_BOTH_directions(), test_every_registered_model_has_an_effective_floor(), test_ordinary_prices_still_fire(), test_the_default_is_overridable_without_a_code_change() (+11 more)

### Community 50 - "scheduler.py"
Cohesion: 0.05
Nodes (50): abort_orphaned_refresh_runs(), build_scheduler(), _add_job(), _with_heartbeat(), _wrapped(), catch_up_daily_pipeline(), catch_up_refresh_pass(), catch_up_weekly_jobs() (+42 more)

### Community 502 - "NFL stale card file tests"
Cohesion: 0.15
Nodes (9): card_path(), clear_card(), _load_script(), nfl_path(), test_a_dry_run_leaves_the_card_alone(), test_a_priced_wind_run_with_no_bets_removes_the_earlier_card(), test_clear_card_removes_todays_file_and_only_that(), test_the_path_cleared_is_the_path_the_publisher_reads() (+1 more)

### Community 503 - "scripts/ncaaf_search/weather_totals.py"
Cohesion: 0.23
Nodes (6): build_spots(), evaluate(), load_games(), main(), scoring_by_wind(), wilson()

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

### Community 508 - "NBA, NCAAF and NFL research labs"
Cohesion: 0.04
Nodes (79): bh_fdr(), binom_p(), eval_rule(), load(), main(), devig_power(), games(), main() (+71 more)

### Community 51 - "NFL live moneyline and total pricing tests"
Cohesion: 0.08
Nodes (31): _model_price(), american_to_decimal(), american_to_prob(), anchor_to_market(), devig_power(), margin_pmf(), _over_under(), price_moneyline() (+23 more)

### Community 510 - "Trainer no-register tests"
Cohesion: 0.12
Nodes (9): not_registering(), registering(), test_a_normal_run_DOES_register(), test_baseline_artifacts_are_not_committable(), test_baseline_runs_write_somewhere_else(), test_default_is_to_register(), test_no_register_opens_no_database_connection(), _explode() (+1 more)

### Community 512 - "tests/test_savant_freshness.py"
Cohesion: 0.14
Nodes (5): test_rows_are_stamped_with_a_capture_date(), test_savant_has_a_schedule(), test_the_insert_persists_the_stamp(), test_the_savant_job_belongs_to_the_pipeline_service(), test_the_stamp_defaults_rather_than_being_required_at_call_sites()

### Community 513 - "tests/test_scorer_nfl_prop_like_escape.py"
Cohesion: 0.23
Nodes (9): _between(), _broken_per_game_sql(), _first_sql(), _per_game_sql(), _sweep_sql(), test_escape_tripwire_is_on_the_pr_ci_subset(), test_live_per_game_clear_interpolates_with_one_game_id(), test_live_sweep_clear_interpolates_with_date_horizon_now() (+1 more)

### Community 514 - "NFL live leader config tests"
Cohesion: 0.10
Nodes (7): honest_probability(), test_a_loop_that_dies_fails_its_job(), test_it_decides_on_its_own_probability(), test_the_action_threshold_key_is_on_one_line(), test_the_loop_refuses_a_price_shorter_than_the_floor(), test_the_mlb_live_scorer_skips_it(), test_the_price_floor_is_minus_140()

### Community 520 - "NFL prop over lean study"
Cohesion: 0.25
Nodes (8): boot(), build(), grade(), implied(), lean_table(), load(), main(), profit()

### Community 522 - "CLV no-vig capture tests"
Cohesion: 0.20
Nodes (8): _fn(), test_a_missing_bet_book_close_is_not_filled_from_another_book(), test_backfill_revisits_anything_that_is_not_standard_v2(), test_capture_grades_raw_same_book_and_a_separate_pinnacle_edge(), test_capture_stamps_method_and_close_book(), test_game_close_never_falls_back_past_first_pitch(), test_pinnacle_is_a_second_lookup_not_the_headline_close(), test_prop_close_stays_bounded_at_first_pitch()

### Community 527 - "scripts/live_feed_probe.py"
Cohesion: 0.24
Nodes (8): dump_vendor(), _get(), _is_live(), _key(), _row(), run(), _totals(), _vendor_key()

### Community 528 - "NCAAF steam lag study"
Cohesion: 0.27
Nodes (9): attach_scores(), build_events(), fmt(), grade(), lines_at_pulls(), load(), main(), summarise() (+1 more)

### Community 529 - "tests/test_clear_unauthorized_auto_pauses_migration.py"
Cohesion: 0.19
Nodes (6): _stmts(), test_clearing_auto_pauses_did_not_park_batter_runs(), test_it_clears_the_whole_auto_pause_table(), test_it_does_not_touch_picks_thresholds_or_the_review_ledger(), test_it_no_ops_when_the_table_is_missing_or_already_empty(), test_migration_is_one_statement()

### Community 53 - "Prop ladder, picks unique row and as-of verify tests"
Cohesion: 0.03
Nodes (40): _identity_maps(), _platform_gates_off(), _statements(), test_columns_and_values_line_up(), test_the_scorer_pick_insert_is_actually_covered(), _derive(), _frame(), test_a_game_log_without_the_column_cannot_build_tackles() (+32 more)

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

### Community 541 - "NHL totals lab"
Cohesion: 0.26
Nodes (8): grade(), imp(), interval(), load(), main(), row(), show(), wpu()

### Community 542 - "ncaaf_live/tests/test_cfbd_yardline.py"
Cohesion: 0.21
Nodes (6): _abbrev_fits(), _parse_yardline(), _cfbd_game(), test_cfbd_state_carries_the_yardline_and_the_raw_situation(), test_cfbd_yardline_from_every_stored_situation(), test_cfbd_yardline_refuses_rather_than_guesses()

### Community 546 - "tests/test_claude_rules_split.py"
Cohesion: 0.18
Nodes (4): test_claude_md_still_points_at_the_rules_directory(), test_every_rule_file_actually_carries_rules(), test_every_rule_file_is_path_scoped(), test_no_rule_was_lost_when_the_split_happened()

### Community 547 - "tests/test_db_setup.py"
Cohesion: 0.23
Nodes (6): _get_columns(), test_games_table_columns(), test_injuries_table_columns(), test_odds_table_columns(), test_picks_table_columns(), test_schema_is_idempotent()

### Community 548 - "tests/test_dedupe_opening_signals.py"
Cohesion: 0.10
Nodes (9): test_a_graded_row_is_never_deleted(), test_a_row_with_computed_clv_is_never_deleted(), test_every_field_that_defines_the_bet_must_agree(), test_it_is_dry_run_by_default(), test_the_delete_selects_through_the_same_gates(), test_the_pair_must_be_an_old_shape_new_shape_pair(), test_the_report_and_the_delete_share_one_definition(), test_the_row_kept_is_the_one_locked_earlier() (+1 more)

### Community 550 - "tests/test_every_named_book_is_fetched.py"
Cohesion: 0.18
Nodes (5): _param_books(), test_a_sharp_reference_is_never_also_a_soft_book(), test_every_bettable_book_can_be_named_to_a_human(), test_every_named_book_is_in_the_pull_that_serves_it(), test_the_nfl_backfill_defaults_to_the_live_pull()

### Community 552 - "tests/test_pbp_backfill_resilience.py"
Cohesion: 0.24
Nodes (6): _backfill_body(), test_a_failed_game_rolls_the_connection_back(), test_a_run_that_wrote_nothing_reports_an_error_not_a_success(), test_errors_are_counted_not_just_logged(), test_partial_failures_are_surfaced_too(), test_the_rollback_cannot_itself_raise()

### Community 561 - "Database URL and SCRAM probes"
Cohesion: 0.26
Nodes (6): main(), scram_stored_key(), test_a_different_password_gives_a_different_key(), test_a_different_salt_gives_a_different_key(), test_iterations_matter(), test_rfc7677_test_vector()

### Community 562 - "mobile/scripts/verify_stats_filter_ux.ts"
Cohesion: 0.18
Nodes (9): chip, lineOnlyFn, playersDay, ROOT, sportReset, stats, teams, teamsDay (+1 more)

### Community 566 - "NFL wind forecast validation"
Cohesion: 0.29
Nodes (10): build(), games(), hourly(), main(), _rate(), sec_coverage(), sec_error(), sec_rule() (+2 more)

### Community 567 - "MLB prop market sweep"
Cohesion: 0.23
Nodes (6): actuals(), grade_day(), main(), norm(), outs_from_ip(), profit()

### Community 568 - "NCAAF quarterback ablation study"
Cohesion: 0.28
Nodes (7): _fit(), main(), _report(), run(), summarise(), walk_forward(), wilson()

### Community 569 - "tests/test_game_log_backfill_skip.py"
Cohesion: 0.25
Nodes (5): _backfill_body(), test_a_game_absent_from_our_games_table_is_still_skipped(), test_no_skip_is_keyed_on_date_alone(), test_the_coverage_set_is_scoped_to_the_season_being_built(), test_the_skip_is_keyed_on_game_id()

### Community 572 - "NCAAF line move spots"
Cohesion: 0.27
Nodes (6): eval_follow_spread(), eval_follow_total(), load(), main(), _summ(), wilson()

### Community 573 - "NFL live prop state builder"
Cohesion: 0.27
Nodes (5): build(), events(), _key(), load_pbp(), verify()

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

### Community 581 - "NFL prop lean concentration study"
Cohesion: 0.25
Nodes (7): add_context(), boot(), main(), profit(), report(), tercile_split(), under_profit()

### Community 584 - "Dashboard rule model tests"
Cohesion: 0.14
Nodes (5): test_a_rule_carries_a_cut_but_is_in_no_training_registry(), test_a_rule_is_not_styled_as_a_warning(), test_a_rule_sorts_with_the_live_models_not_the_broken_ones(), test_the_roster_query_flags_rules(), test_the_summary_counts_rules_apart_from_outages()

### Community 586 - "supabase/functions/stripe-webhook/index.ts"
Cohesion: 0.31
Nodes (9): applySubscription(), iso(), resolveUserId(), stripeGet(), timingSafeEqual(), toHex(), verifySignature(), admin (+1 more)

### Community 589 - "tests/test_mobile_neutral_signal_label.py"
Cohesion: 0.31
Nodes (7): _read(), test_explainer_names_neutral(), test_filters_and_card_speak_the_display_name(), test_model_screens_speak_the_display_name(), test_no_member_label_prints_a_raw_signal_type(), test_none_badge_reads_neutral(), test_withdrawn_pick_is_not_badged_neutral()

### Community 590 - "Live model holdout comparison script"
Cohesion: 0.31
Nodes (6): bias_table(), confident_share(), load_artifact(), main(), poisson_sf(), predict()

### Community 591 - "NFL prop opening signal cleanup tests"
Cohesion: 0.23
Nodes (6): _stmts(), test_it_deletes_exactly_the_three_measured_lock_keys(), test_it_does_not_touch_picks_or_discord(), test_it_still_skips_a_key_that_has_a_standing_bet(), test_migration_is_one_statement(), test_standing_pick_uses_lock_key_sql_not_player_id()

### Community 593 - "tests/test_scorer_commits_per_game.py"
Cohesion: 0.40
Nodes (8): _between(), _run_scorer_body(), test_a_lost_connection_re_runs_the_game_once_and_never_the_pass(), test_each_game_is_its_own_committed_unit(), test_no_bulk_delete_of_non_bet_rows_precedes_the_loop(), test_picks_are_only_counted_once_the_game_committed(), test_the_housekeeping_delete_is_a_sweep_after_the_loop(), test_the_outer_handler_still_records_the_failure()

### Community 594 - "NFL live gaussian copula tests"
Cohesion: 0.20
Nodes (6): gaussian_copula_joint(), dist_out(), _pmf(), test_copula_covariance_takes_the_sign_of_rho(), cov(), test_copula_preserves_both_marginals_exactly()

### Community 596 - "NCAAF structure scan"
Cohesion: 0.21
Nodes (3): load_data(), main(), scan_spot()

### Community 598 - "tests/test_live_game_state_poller.py"
Cohesion: 0.22
Nodes (7): _bases_state(), _extract_state(), test_bases_state_empty(), test_bases_state_loaded(), test_bases_state_single_runner(), test_extract_state_handles_empty_feed(), test_extract_state_pulls_fields_from_live_feed()

### Community 599 - "NFL prop tick tests"
Cohesion: 0.17
Nodes (5): test_days_is_derived_from_the_window_not_pinned(), test_every_live_nfl_prop_model_still_carries_its_own_cut(), test_the_live_ten_are_not_a_clean_bill_of_health(), test_the_window_reaches_at_least_the_ten_day_horizon_the_other_nfl_jobs_use(), test_twelve_are_live_and_none_is_paused()

### Community 60 - "tests: test_wnba_availability + wnba_availability"
Cohesion: 0.07
Nodes (45): absence_features(), absent_teammates(), build_context_features(), expected_rotation(), is_starter_tier(), _mean(), prior_rows(), recent_team_game_dates() (+37 more)

### Community 601 - "NCAAF venue feature tests"
Cohesion: 0.18
Nodes (6): _venue_features(), test_altitude_climb_is_signed_from_each_teams_own_elevation(), test_both_teams_travel_at_a_neutral_site(), test_eastward_travel_is_positive_tz_shift(), test_host_travels_zero_at_a_normal_home_game(), test_missing_venue_data_yields_nulls_not_zeros()

### Community 604 - "UFC fighter page parser"
Cohesion: 0.22
Nodes (7): _height_to_inches(), _parse_dob(), parse_fighter_page(), _reach_to_inches(), test_height_reach_dob(), test_parse_fighter_page(), test_parse_fighter_page_missing_fields()

### Community 606 - "NFL prop two-sharps study and offset docs"
Cohesion: 0.03
Nodes (57): _actuals(), build(), _lead_hours(), main(), profit(), _report(), season_of(), test_season_of_reads_the_game_id_token() (+49 more)

### Community 608 - "supabase/functions/sharpsports-webhook: index + index"
Cohesion: 0.25
Nodes (5): internalIdFor(), pick(), admin, admin, cors

### Community 609 - "NCAAF qualify at DraftKings tests"
Cohesion: 0.18
Nodes (4): test_a_cheaper_book_no_longer_buys_its_way_past_the_floor(), test_the_bet_is_still_recorded_at_the_best_price(), test_the_gate_reads_the_draftkings_numbers(), test_the_stale_line_cap_still_judges_the_dk_edge()

### Community 612 - "supabase/functions/stripe-checkout/index.ts"
Cohesion: 0.31
Nodes (8): customerFor(), form(), json(), stripe(), admin, cors, PRICES, TRIAL_DAYS

### Community 614 - "tests/test_book_list_budget.py"
Cohesion: 0.31
Nodes (4): _names(), test_every_book_the_nfl_prop_model_bets_at_is_actually_fetched(), test_the_nfl_prop_pull_is_one_group_with_both_references_in_it(), test_the_shared_list_is_one_group()

### Community 617 - "Live CV grouping tests"
Cohesion: 0.20
Nodes (5): _memorisable_plays(), test_game_ids_sort_chronologically(), test_groups_default_to_none_so_ungrouped_callers_are_unchanged(), test_the_live_trainer_passes_game_ids(), test_ungrouped_cv_scores_a_lookup()

### Community 62 - "NBA game market lab"
Cohesion: 0.05
Nodes (62): assemble(), _assert_spread_sign(), attach_close(), bars(), bet_frame(), blind_bets(), blind_first_fetch(), boot_ci() (+54 more)

### Community 620 - "Mobile NHL look-ahead window tests"
Cohesion: 0.29
Nodes (5): _fn(), _read(), test_the_nhl_read_matches_the_other_look_aheads(), test_the_sport_chip_is_the_hook_not_an_allowlist(), test_use_today_picks_fetches_nhl_across_that_window()

### Community 621 - "NFL prop week-one candidate pool tests"
Cohesion: 0.22
Nodes (5): partially_played_week_one(), _player_row(), _team_row(), test_a_clean_week_one_is_unchanged(), test_teams_still_to_play_keep_a_candidate_pool()

### Community 622 - "SBR historical odds loader"
Cohesion: 0.25
Nodes (3): canonical_abbrev(), parse_csv_file(), test_sbr_abbreviations_are_canonicalised_for_mlb_only()

### Community 623 - "NBA injury report player matching"
Cohesion: 0.20
Nodes (6): match_player(), _near_season(), remap_changes(), test_a_name_printed_differently_matches_on_surname_and_initial_within_the_team(), test_player_ids_match_on_team_first_then_a_unique_season_name(), test_remap_rewrites_only_names_whose_id_changed()

### Community 628 - "NFL live backtest states"
Cohesion: 0.24
Nodes (3): load_pbp(), _repair_day_offsets(), sample_states()

### Community 629 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.47
Nodes (6): contentHeight(), evalExpr(), lineOf(), styleBlock(), styleProp(), visualHeight()

### Community 631 - "NFL wind lead calibration"
Cohesion: 0.36
Nodes (5): build(), fetch_issued_all_leads(), games(), main(), resample()

### Community 632 - "Eastern game date tests"
Cohesion: 0.25
Nodes (4): _sources(), test_no_game_date_is_derived_from_the_container_clock(), test_the_live_modules_cannot_even_name_date_today(), test_today_et_is_eastern_inside_the_window_that_broke()

### Community 634 - "NCAAF weather backfill"
Cohesion: 0.29
Nodes (5): backfill(), _celsius_to_f(), _fetch_weather(), ingest_upcoming(), _utc_offset_from_lon()

### Community 635 - "tests/test_demote_ncaaf_over_under_platt.py"
Cohesion: 0.32
Nodes (4): _stmts(), test_it_demotes_only_the_measured_promotion(), test_it_does_not_move_the_gate_the_floor_or_a_pause(), test_migration_is_one_statement()

### Community 637 - "tests/test_discord_post_one_pick_migration.py"
Cohesion: 0.29
Nodes (3): _pairs(), test_it_names_each_measured_extra_and_the_row_kept(), test_the_update_does_not_rewrite_the_graded_outcome()

### Community 638 - "tests/test_game_scorer_spares_nfl_props.py"
Cohesion: 0.43
Nodes (5): _between(), _run_scorer_body(), test_an_nfl_game_never_enters_the_per_game_clear(), test_both_live_non_bet_clears_leave_nfl_rows(), test_the_left_out_ufc_clear_only_removes_unsettled_non_bets()

### Community 639 - "Calibration agent sweep tests"
Cohesion: 0.28
Nodes (5): sweep(), _rows(), test_a_prob_only_sweep_uses_only_the_probability_dimension(), test_plateau_is_computed_within_the_narrow_grid(), test_the_full_sweep_is_unchanged_when_no_grid_is_passed()

### Community 64 - "NFL live model backtest harness"
Cohesion: 0.11
Nodes (19): _settle(), _team_side(), build_states(), _pbp(), test_a_dome_suppresses_wind(), test_a_push_settles_to_nan_not_to_a_loss(), test_a_team_total_without_a_resolved_team_is_not_adjudicated(), test_a_wrong_date_component_is_repaired() (+11 more)

### Community 641 - "tests/test_mobile_ota_self_update.py"
Cohesion: 0.32
Nodes (4): _read(), test_app_root_mounts_the_ota_updater(), test_the_pieces_exist(), test_the_updater_actually_applies_the_update()

### Community 643 - "tracking/model_quality.py"
Cohesion: 0.14
Nodes (8): test_clv_clear_negative_vs_baseline_is_flagged(), test_raw_one_sided_clv_is_ignored(), test_roi_collapse_is_crit_when_hit_rate_dies(), test_roi_ignores_unpriced_profit_flat(), detect_clv_degradation(), detect_roi_collapse(), _sample(), units_from_profit_flat()

### Community 649 - "MLB totals public fade model"
Cohesion: 0.09
Nodes (20): diff(), pitcher_diff(), diff(), pitcher_diff(), numeric_feature_value(), _pct_pair(), _better_under(), is_pre_commence() (+12 more)

### Community 653 - "NFL prop book sweep"
Cohesion: 0.14
Nodes (12): _actuals(), _board(), p(), _line(), main(), _run(), soft_verdict(), test_a_bettable_book_still_passes() (+4 more)

### Community 655 - "UFC stats page parsers"
Cohesion: 0.10
Nodes (21): _int_or_none(), _mmss_to_sec(), normalize_method(), _of_pair(), _parse_event_date(), parse_event_list(), parse_event_page(), _two_ints() (+13 more)

### Community 656 - "Calibration eligibility notes"
Cohesion: 0.22
Nodes (3): test_eligibility_notes_parse_the_payload_verdicts(), _calibration_eligibility_notes(), _report_model_calibration()

### Community 659 - "Bookmaker whitelist tests"
Cohesion: 0.22
Nodes (5): _source(), test_closing_line_reads_name_the_book(), test_feature_engines_whitelist_draftkings(), test_line_shop_books_are_not_referenced_by_scoring_code(), test_scorer_prop_odds_reads_one_named_book_at_a_time()

### Community 660 - "NBA injury report retry tests"
Cohesion: 0.25
Nodes (6): test_a_connection_lost_mid_write_re_runs_the_whole_slot(), executemany(), __init__(), test_a_statement_timeout_rolls_back_and_re_runs_the_slot(), executemany(), __init__()

### Community 663 - "Eastern game date tests"
Cohesion: 0.25
Nodes (5): eastern_game_date(), test_eastern_game_date_agrees_with_utc_before_8pm_et(), test_eastern_game_date_falls_back_to_the_utc_prefix_when_unparseable(), test_eastern_game_date_leaves_a_bare_calendar_date_alone(), test_eastern_game_date_matches_the_odds_ingestor_for_a_night_kick()

### Community 669 - "NCAAF weather forecast backfill"
Cohesion: 0.36
Nodes (6): backfill(), fetch_venue_season(), _get(), _kick_date(), _kick_hour(), _parse_kick()

### Community 671 - "NCAAF play-by-play puller"
Cohesion: 0.36
Nodes (4): fetch_season(), _get(), main(), pull_season()

### Community 673 - "Scorer keeps off-DraftKings priced bets tests"
Cohesion: 0.29
Nodes (6): _bet(), db(), _left(), _statement(), test_a_bet_priced_at_another_books_line_survives_and_a_bet_with_no_price_does_not(), test_the_statement_names_both_prices()

### Community 675 - "NFL odds table builder"
Cohesion: 0.43
Nodes (4): load_games(), main(), wide_spreads(), wide_totals()

### Community 677 - "NFL prop lean gradient study"
Cohesion: 0.36
Nodes (4): boot(), grade(), main(), profit()

### Community 68 - "tests: test_db_url_doctor + test_envfile_fallback"
Cohesion: 0.12
Nodes (13): _classes(), main(), database_url(), _default_env_path(), env_value(), parse_env_file(), test_a_missing_env_file_is_empty_not_an_error(), test_a_value_containing_equals_survives() (+5 more)

### Community 689 - "Parlay leg correlation estimates"
Cohesion: 0.36
Nodes (5): estimate(), estimate_basketball(), estimate_mlb(), main(), _median()

### Community 692 - "NFL research backup and restore script"
Cohesion: 0.44
Nodes (5): backup(), files(), main(), restore(), verify()

### Community 693 - "Board markets lock-down tests"
Cohesion: 0.25
Nodes (4): _board_markets(), table(), test_the_mlb_board_and_the_mlb_pull_are_one_set(), test_the_tables_are_locked_down_at_the_create_site()

### Community 696 - "View migration apply and lock retry"
Cohesion: 0.29
Nodes (3): _apply_one(), _is_transient_lock_error(), _with_lock_timeout()

### Community 697 - "Market handicap features"
Cohesion: 0.29
Nodes (4): build_rich_handicap(), _fav_signed_home_move(), _gated_flag(), _mul()

### Community 7 - "MLB over/under retrain sweep tests"
Cohesion: 0.05
Nodes (20): _side_rows(), test_the_raised_timeout_is_restored_after_the_job(), test_the_restore_puts_back_a_pre_existing_value(), test_marker_file_is_in_tree_so_the_freeze_would_not_block_the_worker(), test_missing_artifact_path_refuses_to_sweep_live(), test_over_covers_when_combined_score_beats_the_total_line(), test_price_below_the_house_floor_is_not_a_gradable_side(), test_push_on_the_total_emits_no_sides() (+12 more)

### Community 705 - "NCAAF travel geography features"
Cohesion: 0.29
Nodes (5): haversine_miles(), tz_offset_from_lon(), trip(), test_haversine_matches_real_geography(), test_timezone_offsets_land_in_the_right_zones()

### Community 707 - "NHL goalie line helpers"
Cohesion: 0.83
Nodes (4): _goalie_line(), regressed(), saved_above(), tot()

### Community 708 - "Team stats rebuild and verify"
Cohesion: 0.18
Nodes (9): already_a_series(), _games(), live_season_snapshot_grace(), main(), _prior_season_rates(), rebuild_sport(), _team_games(), verify() (+1 more)

### Community 709 - "NFL opener calibration"
Cohesion: 0.38
Nodes (3): _load_backtest(), main(), selected_bets()

### Community 71 - "tests/test_live_orchestrator.py"
Cohesion: 0.04
Nodes (43): should_fetch(), split_triggers(), under_credit_cap(), apply_daily_cap(), classify_live_signal(), _ev_floor(), expected_value(), test_decide_agrees_with_classify_live_signal() (+35 more)

### Community 711 - "Live money no record-only tests"
Cohesion: 0.43
Nodes (4): _allowed(), _hits(), _rel(), test_the_repo_has_no_record_only_or_paper_tracking_mode()

### Community 719 - "Mobile accessibility verify script"
Cohesion: 0.67
Nodes (3): read(), readUtf8(), verticalSlop()

### Community 72 - "tests/test_market_handicap.py"
Cohesion: 0.05
Nodes (36): attach_market_handicap(), build_public_features(), empty_handicap(), favorite_side(), _rlm(), row_is_pregame(), select_latest_pregame_splits(), _split() (+28 more)

### Community 721 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.67
Nodes (3): closeOf(), openTag(), toggleUse()

### Community 730 - "Strategy analysis report"
Cohesion: 0.43
Nodes (4): _fmt(), _profit_sql(), _row(), strategy_analysis()

### Community 731 - "NBA injury report slot naming"
Cohesion: 0.40
Nodes (4): _ampm(), new_slot(), old_slot(), test_slot_names_both_formats()

### Community 732 - "NBA injury report name and team parsing"
Cohesion: 0.33
Nodes (5): name_first_last(), _row(), team_code(), test_names_turn_round_with_their_suffix_on_the_surname(), test_team_names_map_to_our_codes()

### Community 74 - "Prop CLV and SQL escaping tests"
Cohesion: 0.05
Nodes (28): _is_main_guard(), _modules_with_guard(), test_at_least_one_entrypoint_is_scanned(), test_nothing_is_defined_after_the_main_guard(), test_the_backfill_queues_the_dates_of_those_picks(), _fn(), test_a_backfill_failure_never_breaks_settlement(), test_a_pick_is_only_stamped_captured_once_a_measure_resolved() (+20 more)

### Community 75 - "scripts: ncaaf_margin_eval + test_ncaaf_margin_eval"
Cohesion: 0.08
Nodes (28): margin_cover_prob(), build_frames(), _fit(), fit_and_register(), fit_and_register_totals(), main(), _matrix(), _print_sweep() (+20 more)

### Community 755 - "NHL opening week rekey script"
Cohesion: 0.47
Nodes (3): main(), _mapping(), _tables_with_game_id()

### Community 756 - "Model pause helper tests"
Cohesion: 0.40
Nodes (3): _is_paused(), test_config_pauses_still_work_through_the_same_helper(), test_the_scorer_still_honours_a_leftover_auto_pause_row()

### Community 76 - "ncaaf_live/tests/test_serve.py"
Cohesion: 0.07
Nodes (37): _clock_seconds(), extract_live_states_cfbd(), _parse_situation(), _cfbd_game(), _ctx(), _no_ev_floor(), _settled(), _stamped() (+29 more)

### Community 790 - "Discord void publish worker job"
Cohesion: 0.40
Nodes (3): test_the_worker_job_is_registered_and_defaults_to_dry_run(), _job_publish_discord_void(), _validate_publish_discord_void()

### Community 82 - "Mobile error state and stat segment tests"
Cohesion: 0.05
Nodes (49): main(), node_exe(), node_strips_types(), tsx_cmd(), _node_strips_types(), _node_strips_types(), _read(), test_combiner_is_pure_and_lives_next_to_fill() (+41 more)

### Community 849 - "Discord free pick integrity tests"
Cohesion: 0.50
Nodes (4): test_discord_free_pick_candidates_refuse(), execute(), fetchall(), row()

### Community 856 - "NCAAF feature assembly"
Cohesion: 0.22
Nodes (3): _assemble_ncaaf_features(), _game_tier(), test_season_opener_gets_a_zero_rest_differential_not_a_null()

### Community 86 - "scripts/nfl_edge_preregistered_2026.py"
Cohesion: 0.09
Nodes (39): bar(), bets_frame(), bh(), binom_line(), _by_game(), cell(), fam(), first_last() (+31 more)

### Community 87 - "tests: test_player_positions + player_positions_ingestor"
Cohesion: 0.06
Nodes (26): _basketball(), basketball_group(), _fresh_source_ids(), _get_json(), ingest_player_positions(), match_to_log(), _name_index(), _ncaaf() (+18 more)

### Community 88 - "NBA prop market tests"
Cohesion: 0.08
Nodes (33): fair_under(), q(), run(), run_full(), _settle(), test_a_fetch_after_now_or_at_tip_and_a_close_row_never_decide(), test_a_fetch_older_than_the_window_is_not_a_price(), test_a_game_already_bet_is_never_decided_again() (+25 more)

### Community 89 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.04
Nodes (48): a11ySrc, allowHit, ALLOWLIST, app, badExempt, bar, bareClose, baselineLeft (+40 more)

### Community 91 - "NBA prop model lab"
Cohesion: 0.07
Nodes (48): books(), decimal(), expected_value(), fit_alpha(), nb_logpmf(), p_over(), _agg(), apply_rule() (+40 more)

### Community 93 - "tests/test_mlb_total_public_fade.py"
Cohesion: 0.12
Nodes (27): find_fade_bets(), under_in_odds_band(), rows_for_insert(), _dk_board(), _quote(), _quotes(), _slate(), _split() (+19 more)

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

### Community 496 - "Mobile package manifest"
Cohesion: 0.12
Nodes (15): devDependencies, @babel/core, babel-plugin-module-resolver, babel-preset-expo, tsx, @types/react, typescript, scripts (+7 more)

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

### Community 81 - "docs: nhl_market_lab + nhl_clv_ev_assessment"
Cohesion: 0.08
Nodes (41): nhl_research worker job, scripts/nhl_derivative_totals_backtest, data/ingestors/nhl_derivative_odds_history, models/nhl_props.py (Spec per market), DraftKings de-vigged price sits above realised over-rate, Anytime goalscorer: not a candidate once names corrected, nhl_moneyline and nhl_moneyline_regulation: no cut clears, Game models: lock later? Refuted (+33 more)

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
Cohesion: 0.10
Nodes (19): Hybrid Pin-agreement filter on mlb_over_under bets, mlb_spread_market 1.8pp run-line rule, mlb_total_market paper totals logger, mlb_runline and mlb_over_under (paused), mlb_total_public_fade card (paper UNDER), Slate concentration guard (insert-time), F5 odds coverage (DK carries F5 ML only), clv_degradation check (+11 more)

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
Cohesion: 0.18
Nodes (8): Publish backstop refuses pass-attempt overs, Pace ratio, In-play rushing-attempt UNDER on pace ratio >= 1.25, NFL edge search 2026-10-11, docs/nfl_live_prop_assessment.md, Live pass-attempt bias assessment (2026-09-21), docs/nfl_live_rush_attempts.md, docs/nfl_prop_method_search.md

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

### Community 478 - "Probability calibration and EV floor docs"
Cohesion: 0.23
Nodes (15): models/honest_ev.gate and honest_probability, tracking/system_health._report_model_calibration, MODEL_OWN_EV_FLOOR and MODELS_ON_OWN_PROBABILITY for wind and opener, fetch_graded reads picks for NFL/NCAAF/UFC/rule models, GLOBAL_MIN_EV: 0.30 then 0.20, The go-live calibration gate never computed a real number, ncaaf_over_under Platt map demoted 2026-09-26, Twelve models 6-16pp overconfident; it tracks sample size (+7 more)

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

### Community 545 - "In-play backtest and volume efficiency docs"
Cohesion: 0.14
Nodes (7): Live feature sensitivity (12.8pp median swing), mlb_live_total_runs (in-play total), Negative-binomial (NB1) tail, pregame_total_line feature (market anchor), ncaaf_live_total 2025 in-play backtest, ncaaf_live_win_prob 2025 in-play backtest, Late-game leader moneyline at DraftKings

### Community 553 - "Monitoring and model state docs"
Cohesion: 0.10
Nodes (12): roi_collapse check, api_call_log table, Heartbeat watchdog, Live monitor dashboard (monitoring/), Live tuning panel (Models view), mv_scored_pick_outcomes (sweep matview), Official live date 2026-09-01, The request probe: one patch, not 75 call-site edits (+4 more)

### Community 558 - "docs/health_checks.md"
Cohesion: 0.24
Nodes (10): model_artifacts_load counts what it opened, model_artifacts table fallback restore, Three separate artifact questions, three separate failures, KNOWN_UNTRAINED — config models intentionally without artifacts, Pipeline-observability checks: refresh_pass_completion, refresh_pass_steps, signal_delivery, pick_label_integrity, pipeline_runs — the run ledger (tracking/run_ledger.py), Retrain Model workflow (retrain_model.yml), tracking/system_health.py — CRIT and WARN feed checks (Step 12) (+2 more)

### Community 560 - "docs/retrain_2026_plan.md"
Cohesion: 0.18
Nodes (12): scripts/paused_model_assessment, data.ingestors.baseball_savant_ingestor, models.trainer, F5 O/U and F5 RL paused: leak-mismatched, synthetic-line trained, NCAAF in-play season replay: -3.4% and -13.1%, No model has a cut that clears on the deployed artifact, batter_sb: opp_team_sb_allowed feature, Phase 0: train 2019-2024, holdout 2025 (+4 more)

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
Nodes (44): scripts/nfl_prop_market_card, scripts/nfl_prop_replay, scripts/nfl_prop_ladder_grade, scripts/verify_kalshi, tackles_assists +21% is a measurement error (control), Traps specific to props, Anytime TD field de-vig: closed, #215 artifacts could not be deserialised (+36 more)

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
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 10409 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **196 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_connection()` connect `Model trainer and research CLI scripts` to `ESPN injury ingestor`, `Odds, prop odds and NHL derivative odds ingestors`, `Settlement tracker and feature engine`, `Pipeline run ledger`, `Live scorer and pick insertion`, `NFL prop market stack and devig`, `Direct sportsbook feeds and freshness probes`, `Discord signal notifier tests`, `X publisher`, `Daily pipeline runner and push notifier`, `scripts/live_feed_probe.py`, `NCAAF steam lag study`, `Live game state and trigger pollers`, `Probability calibration fit and schema`, `NBA prop projection card`, `NHL market lab and live artifact grading`, `Public read access grants`, `NHL totals lab`, `EV floor and cut replay sweeps`, `DataGolf ingestor and NHL SBR archive`, `Worker job queue and CFBD ingestor`, `Failure alerter fake-connection tests`, `scheduler.py`, `NFL prop backtest model and universe rate`, `Feature matrix dtypes and line sweeps`, `NCAAF gameday worker and ESPN feed`, `MLB prop market sweep`, `NFL odds pulls and live prop assessment`, `NFL live game state math`, `NFL pick monitor`, `scripts: ncaaf_margin_eval + test_ncaaf_margin_eval`, `tests/test_wnba_prop_market.py`, `NHL derivative totals model`, `docs: nhl_market_lab + nhl_clv_ev_assessment`, `NCAAF structure scan`, `Discord notifier, void notices and price bound tests`, `tests/test_recap_retries_a_skipped_day.py`, `tests: test_player_positions + player_positions_ingestor`, `Player news ingestor`, `tests/test_heartbeat_watchdog.py`, `models: nhl_prop_blocked_shots + nhl_prop_blocked_shots_backtest`, `Record correction and full record posts`, `tests/test_live_calibration.py`, `nfl_live_leader/gameday.py`, `NHL lab summaries and early-season blend`, `Game scorer core and NCAAF board visibility`, `NCAAF weather backfill`, `scripts: nhl_prop_backtest + nhl_prop_ev_lab`, `NHL prop cards and cross-model publish`, `features/golf_feature_engine.py`, `models/nhl_props.py`, `NFL weather ingest and forecast persistence`, `NBA prop projection model`, `X and Discord results recap publishers`, `Idle read transaction tests`, `Historical backfill and sub-10s live path tests`, `NCAAF weather forecast backfill`, `NCAAF play-by-play puller`, `NBA box score enrichment`, `NHL stats ingestor`, `Prop box score backfill`, `Push notifier and tickets`, `Parlay leg correlation estimates`, `NFL research backup and restore script`, `tests/test_nfl_rule_2026_track.py`, `scripts/game_line_market_sweep.py`, `scripts/nfl_wind_publisher.py`, `tests/test_first_signal_repair.py`, `Team stats rebuild and verify`, `NBA stats ingestor`, `NFL prop feature engine`, `scripts/ncaaf_search: dataset + starter_out`, `data/ingestors/nfl_inplay_history.py`, `Strategy analysis report`, `tests/test_local_cache_is_additive.py`, `tests/test_team_board_cache.py`, `tests/test_nfl_poll_fast_silence.py`, `Prop feature engine rows`, `data/ingestors/ncaaf_inplay_history.py`, `MLB and WNBA stats ingestors and pitcher rebuild`, `NHL opening week rekey script`, `data/ingestors/nhl_boxscore.py`, `scripts/mlb_total_public_fade_topk.py`, `tests/test_ncaaf_search_features.py`, `NCAAF in-play history backtest`, `tests/test_ncaaf_qb_features.py`, `Monitoring HTTP stream handler`, `NHL game logs as-of windows`, `NBA ESPN box score parser`, `NBA official injury report ingestor`, `NCAAF gameday lock tests`, `NCAAF play-by-play state builder`, `Kalshi ladder recording and prop ingestor tests`, `UFC stats ingestor and dashboard app`, `NCAAF game-day duplicate game tests`, `NHL prop backtest and combined cap`, `NCAAF totals lead and consensus gate`, `Paused model assessment tests`, `Live honest cut script`, `NFL live pick writer and recorder tests`, `Kalshi game market recorder`, `UFC CSV fight loader`, `NFL prop market rule and card`, `tests/test_heartbeat_disabled_jobs.py`, `tests/test_promote_calibration_job.py`, `tracking/model_quality.py`, `NFL weather cache import`, `Paused rows, prop lead ceiling and NHL regulation tests`, `System health checks and first-pitch guard`, `NBA prop market model and card`, `tests/test_batter_prop_log_pin.py`, `tests/test_merge_mlb_twin_games.py`, `NCAAF outcome edge scan`, `scripts/ncaaf_search/situational_spots.py`, `Monitoring server tests`, `tests/test_transaction_pooler.py`, `Local store cache and NFL prop shape simulation`, `MLB game market and public fade cards`, `Pipeline watch and burn alerts`, `Player news ingestor tests`, `scripts/ncaaf_search/weather_totals.py`, `NBA, NCAAF and NFL research labs`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **What connects `RFC-4122`, `@babel/core`, `babel-plugin-module-resolver` to the rest of the system?**
  _105 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `ESPN injury ingestor` be split into smaller, more focused modules?**
  _Cohesion score 0.0700354609929078 - nodes in this community are weakly interconnected._
- **Why does `mlb_live_total_runs (in-play total)` connect `In-play backtest and volume efficiency docs` to `NFL prop two-sharps study and offset docs`, `docs/thresholds.md`, `Monitoring and model state docs`?**
  _High betweenness centrality (0.015) - this node is a cross-community bridge._
- **Should `Mobile stats board` be split into smaller, more focused modules?**
  _Cohesion score 0.013763644992880873 - nodes in this community are weakly interconnected._
- **Should `NFL prop market stack and devig` be split into smaller, more focused modules?**
  _Cohesion score 0.03978678850180849 - nodes in this community are weakly interconnected._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Claim: the app cannot write to the backend` and `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._