# Graph Report - bm-nba-pbp  (2026-10-16)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 27446 nodes · 65105 edges · 897 communities (676 shown, 221 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 1694 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `109ab642`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ESPN injury ingestor
- Mobile stats board
- Mobile markets and formatting
- Odds, prop odds and NHL derivative odds ingestors
- Feature engine and live scorer loading
- Mobile theme, parlays and sportsbook links
- Paper tracker bankroll and scorer database calls
- MLB over/under retrain sweep tests
- Mobile player log and matchup stats
- Database connection and CLI ingestor scripts
- NFL prop market stack and devig
- Direct sportsbook feeds and freshness probes
- Mobile pick filters and sorting
- Discord signal notifier tests
- Mobile custom model filters and metadata
- X publisher
- Daily pipeline runner and push notifier
- Discord units convention tests
- Mobile thresholds and daily results
- Picks email renderer
- Mobile formatting and live status checks
- NFL edge study shared library
- NBA prop projection card
- NFL in-play edge study 2024
- NHL market lab and live artifact grading
- NBA play-by-play ingestor
- Mobile team detail and team stats
- Parlay builder and bet slip
- CLV price-taken tests
- In-play history and play-by-play ingestors
- NFL live prop model tests
- NBA prop model core
- NCAAF in-play score distribution engine
- nfl/live_model/feeds: test_feed_resilience + espn
- Mobile feedback and social links
- Mobile app shell and push notifications
- tests/test_cfbd_ingestor.py
- EV floor and threshold sweep scripts
- Odds pruning and sharp book retention tests
- nfl/live_model/tests/test_executor.py
- NFL wind edge studies
- tests/test_live_quote_staleness.py
- DataGolf ingestor and NHL SBR archive
- tests/test_job_queue.py
- scripts: build_nfl_live_leader_artifact + model
- tests/test_nfl_prop_one_read_per_game.py
- Worker job queue
- scripts/nfl_edge_gameline_rules.py
- tests/test_calibration_watch.py
- Failure alerter fake-connection tests
- scheduler.py
- NFL live moneyline and total pricing tests
- tests/test_best_line_live.py
- NFL player stats ingestor and prop tests
- tests/test_void_picks.py
- NCAAF gameday worker and ESPN feed
- tests/test_daily_retry.py
- tests/test_live_book_move_guard.py
- tests: test_discord_notifier + test_discord_live_field
- NFL odds API pulls and snapshots
- tests: test_wnba_availability + wnba_availability
- mobile/src/hooks: verify_tracked_performance + useStakeSettings
- NBA game market lab
- NFL live game state
- NFL live model backtest harness
- NFL live score distribution and calibration
- docs/nfl_props_model.md
- tests/test_game_market_gate.py
- tests: test_db_url_doctor + test_envfile_fallback
- tests/test_pick_integrity.py
- tests/test_record_one_pick_per_event.py
- tests/test_live_orchestrator.py
- tests/test_market_handicap.py
- nfl/live_model/tests: test_props + props
- Prop CLV and SQL escaping tests
- scripts: ncaaf_margin_eval + test_ncaaf_margin_eval
- ncaaf_live/tests/test_serve.py
- tests/test_wnba_prop_market.py
- tests/test_nfl_scored_rows.py
- NHL derivative totals model
- Global EV floor and NHL totals tests
- docs: nhl_market_lab + nhl_clv_ev_assessment
- Mobile TypeScript test runners
- NHL prop wiring tests
- Discord notifier and void notices
- tests/test_recap_retries_a_skipped_day.py
- scripts/nfl_edge_preregistered_2026.py
- tests: test_player_positions + player_positions_ingestor
- NBA prop market tests
- mobile/scripts/verify_a11y.ts
- tests/test_f5_any_book_line.py
- NBA prop model lab
- tests/test_ncaaf_prop_odds.py
- tests/test_mlb_total_public_fade.py
- NFL prop model and player row parsing tests
- tests/test_ncaaf_pbp_store.py
- tests/test_heartbeat_watchdog.py
- Game injury veto gate and tests
- models: nhl_prop_blocked_shots + nhl_prop_blocked_shots_backtest
- Publish key identity tests
- NBA stint derivation tests
- NCAAF slug and orientation helpers
- scripts/nfl_edge_live_rush_pace.py
- NBA prop projection tests
- Record correction post tests
- Mobile live segment wiring tests
- Supabase schema tables
- tests/test_prop_calibrated_decision.py
- ncaaf_live/tests/test_pregame_calibration.py
- Best-price decision tests
- tests/test_mobile_line_movement.py
- tests/test_live_calibration.py
- Push deep link and mobile player detail tests
- tests/test_nfl_live_leader_gameday.py
- nfl_live_leader/gameday.py
- tests/test_calibration_promotion.py
- tests/test_score_off_any_book_line.py
- Heartbeat watchdog and ops alerts
- tests/test_recap_restatement.py
- tests/test_ncaaf_live_notify.py
- tests/test_ncaaf_alias_scores.py
- tests/test_prop_alternate_lines.py
- Game scorer core and NCAAF board visibility
- tests/test_backtester.py
- scripts: nhl_prop_backtest + nhl_prop_ev_lab
- nfl/live_model/feeds/odds_live.py
- monitoring/store.py
- NHL prop cards and cross-model publish
- tests/test_settled_record_is_immutable.py
- NBA prop market lab
- features/golf_feature_engine.py
- nfl/live_model/tests/test_backup_snaps.py
- ncaaf_live/tests/test_states.py
- tests/test_bovada_feed.py
- tests/test_market_movement.py
- mobile/scripts: verify_book_links + verify_betslip_combine
- tests/test_ncaaf_cross_book_opener.py
- NBA injury report fixture tests
- tests/test_paused_keeps_real_verdict.py
- NFL in-play edge study 2025 and devig
- mobile/scripts/verify_contrast_tokens.ts
- models/nhl_props.py
- tests/test_health_pregame_prices_current.py
- Pick lock after settlement tests
- WNBA stats and results ingestors
- NBA prop projection model
- tests/test_mlb_game_market.py
- scripts/nfl_edge_extreme_props.py
- scripts/nfl_edge_settlement.py
- X and Discord results publishers
- Threshold review run tests
- docs/rules_evidence.md
- Idle read transaction tests
- tests/test_agents_contract.py
- Market coverage and live path tests
- tests/test_prop_box_scores.py
- MLB totals public fade model
- Position vs opponent tests
- Best line and best-price decision tests
- WNBA results ingestor parsers
- NFL in-play prop flow backtests
- NBA box score enrichment
- tests/test_job_queue.py
- tests/test_nfl_opener.py
- NHL stats and game log ingestors
- Prop box score backfill
- scripts/nfl_preflight.py
- Push notifier and tickets
- Mobile sign-in and auth
- Mobile billing config and verify script
- NFL stake sizing simulation
- NFL in-play prop engine calibration
- tests/test_decide_on_calibrated.py
- tests/test_publisher_lock.py
- tests/test_dk_direct_feed.py
- NBA prop projection lab
- tests/test_credit_budget.py
- NFL prop odds backfill
- mobile/app.json
- NHL market-anchored moneyline model
- tests/test_nfl_rule_2026_track.py
- tests/test_model_artifacts_load.py
- docs: probability_calibration + nfl_rule_2026_track
- mobile/package.json
- scripts/game_line_market_sweep.py
- scripts/nfl_wind_publisher.py
- Market coverage probe
- tests/test_pass_instrumentation.py
- Settlement and self-heal tests
- tests/test_db_adapt_sql.py
- NCAAF board visibility tests
- NFL game lines model write-up
- tests/test_first_signal_repair.py
- tests/test_model_calibration_agent.py
- tests/test_mobile_contrast_tokens.py
- tests/test_ungraded_model_performance.py
- NBA stats ingestor
- Historical odds backfill tests
- Prop price pregame cutoff tests
- NFL prop odds loading tests
- Mobile bankroll card
- Games and latest odds views
- tests/test_nhl_asof.py
- NFL prop feature engine and grading
- Prop devig and market-relative pricing
- tests/test_live_inning_gate_replay.py
- scripts/ncaaf_search: dataset + starter_out
- tests: test_deploy_checks + deploy_checks
- data/ingestors/nfl_inplay_history.py
- NFL luck gap study
- Mobile bankroll store and verify script
- Probability calibration fit
- nfl/live_model/README.md
- NHL props per-game limit tests
- Live count tail probability tests
- Free pick cheaper book tests
- NCAAF live engine pricing
- Closing line value math
- tests/test_nfl_live_leader_state.py
- tests/test_db_reconnect.py
- tests/test_ncaaf_qb_ingestor.py
- NFL live prop tests and pass-attempt bias
- tests/test_live_lock.py
- NBA derivative market lab
- tests/test_refresh_retry.py
- NBA box score player name resolver
- docs: followups + clv
- NBA results ingestor tests
- NBA prop model verification script
- tests/test_local_cache_is_additive.py
- tests/test_calibration_check_coverage.py
- Record correction posting script
- tests/test_book_team_map.py
- tests/test_team_board_cache.py
- NCAAF feature engine tests
- mobile/src/lib: verify_discord_link + discordHelpers
- Discord price bound tests
- nfl/live_model/tests/test_rush_attempt_pace.py
- tests/test_nfl_poll_fast_silence.py
- tests/test_ncaaf_game_identity.py
- Batter prop feature rows
- Results recap message tests
- MLB stats ingestor
- tests/test_weather_lookahead.py
- tests/test_nhl_asof.py
- docs: best_line + config_topology
- tests/test_dk_freshness_parse.py
- tests/test_live_calibrated_decision.py
- models: slate_concentration + test_slate_concentration
- data/ingestors/nhl_boxscore.py
- View migration lock handling tests
- docs/cloud_worker.md
- docs/history: learnings + build_state
- Prop odds missing game tests
- scripts/mlb_total_public_fade_topk.py
- tests/test_ncaaf_search_features.py
- NCAAF search model runner
- NFL wind forecast and totals
- NFL player stats ingestor tests
- tests/test_live_game_features.py
- tests/test_ncaaf_totals_regression.py
- UFC feature engine and tests
- NFL model import tests
- monitoring/static/dashboard.html
- tests/test_best_line_sweep.py
- NCAAF in-play history backtest
- tests/test_ncaaf_qb_features.py
- tests/test_nfl_scored_rows.py
- tests/test_cfbd_ingestor.py
- NCAAF in-play history tests
- tests/test_line_clv.py
- Discord publish sync tests
- tests/test_prop_odds_utc_stamp.py
- Monitoring HTTP stream handler
- NFL lookahead signal tests
- NBA ESPN box score parser
- NBA injury report runner
- tests/test_feature_artifact_agreement.py
- NBA injury report pulls
- Mobile pick queries and hooks
- tests/test_cloud_retrain_artifacts.py
- NFL in-play prop flow slices
- NCAAF play-by-play state builder
- NCAAF FBS registry tests
- Health skip budget tests
- Kalshi ladder recording and prop ingestor tests
- tests/test_model_calibration_check.py
- tests/test_nfl_opener.py
- tests/test_ncaaf_player_stats_ingestor.py
- NBA play-by-play ingestor tests
- tests/test_team_stats_asof_invariants.py
- docs/sports/nhl.md
- NHL props card tests
- Dashboard app and SQL runner
- Unit stake sizing and formatting
- scripts/nfl_edge_kalshi.py
- scripts/nfl_live_prop_feasibility.py
- tests/test_nfl_wind_publisher.py
- tests/test_context_budget.py
- tests/test_health_reason_and_cadence.py
- tests/test_live_publish_parity.py
- tests/test_nfl_weather_supabase_readback.py
- tests/test_player_h2h_stat_values_migration.py
- Player game log RPCs
- tests/test_retired_models.py
- NBA schedule features
- Pregame line poller tick tests
- Pitcher stats as-of invariant tests
- tests/test_walk_forward_eval.py
- docs: mlb_market_handicap_features + mlb_game_market_gate
- docs/sports/ncaaf.md
- Live scorer score-change guard
- NFL live pick building tests
- Pipeline log reason tests
- NHL props card latest quotes
- NFL weather edge study
- Latest line state and Citadel migration cluster tests
- tests/test_live_record_start_views.py
- tests/test_model_quality.py
- tests/test_nfl_scored_rows.py
- System health signal checks
- Cursor wrapper and X results job tests
- NBA prop window scheduling tests
- docs/discord.md
- docs/team_stats_leak.md
- tests/test_api_call_rollup.py
- tests/test_ncaaf_live_states.py
- MLB prop market pregame quote cutoff
- nfl/models/opener_spread.py
- tests/test_nfl_opener.py
- NHL prop backtest and combined cap
- tests/test_live_slate_midnight.py
- tests/test_nfl_wind_fire_window.py
- College football data parsers
- tests/test_public_betting_ingestor.py
- Odds pruning and opener retention
- docs/sports/nfl.md
- mobile: TESTFLIGHT + README
- tests/test_service_role_split.py
- supabase/functions/README.md
- Mobile range slider filter
- tests/test_live_pick_features.py
- tests/test_http_timeout_floor.py
- Picks and public track record views
- NCAAF totals lead and consensus gate
- scripts/nfl_edge_cache.py
- Paused model assessment script
- Pregame price age tests
- tests/test_prop_missing_features.py
- NFL opener card and line snapshots
- tests/test_nfl_injury_ingest.py
- NHL prop odds alternate line tests
- Player news ingestor
- NBA prop closing line tests
- Live honest cut and research scripts
- NCAAF in-play model docs
- Injury fetch speed and cache tests
- NFL live pick writer failure tests
- NFL live pick recorder declines
- Prop player name matching tests
- tests/test_config.py
- Latest line state tables
- tests/test_run_ledger_orphans.py
- .claude/rules/analysis-and-thresholds.md
- .claude/rules/data-integrity.md
- Kalshi game market recorder
- Database URL doctor tests
- tests/test_mlb_pbp_ingestor.py
- UFC fighter name resolution
- UFC stats ingestor and CSV loader
- tests/test_team_stats_asof_invariants.py
- docs/sports/mlb.md
- Anon grant sweep tests
- docs/thresholds.md
- Refresh pass step ordering tests
- CFBD ingestor
- NFL game lines and wind totals docs
- NFL line snapshot tests
- Mobile in-app purchases
- NFL historical weather fetch script
- tests/test_heartbeat_disabled_jobs.py
- Pregame line poller map seeding
- NFL in-play line churn
- tests/test_mobile_threshold_parity.py
- NFL live prop assessment script
- tests/test_nhl_derivative_odds_job.py
- tests/test_repair_bogus_first_pitch_labels.py
- tests/test_track_record_views.py
- tests/test_weekly_catch_up.py
- .claude/rules: CLAUDE + config-topology
- .github/workflows: CLAUDE + mobile-build
- tests/test_live_game_state_poller.py
- tests/test_sbr_loader.py
- Discord restate signal tests
- docs/agents_contract.md
- NFL Kalshi fetch and price floor grid
- mobile/scripts/ux_scan.mts
- CLV card price taken tests
- NFL live leader model tests
- Mobile paused catalog tests
- NFL live prop rule studies
- tests/test_mobile_player_stat_groups.py
- Mobile sport filter tests
- tests/test_promote_calibration_job.py
- .claude/rules/operations.md
- tests/test_cfbd_snapshot_leakage.py
- docs/live_odds_freshness.md
- Price prefilter timeout rollback tests
- mobile/src/lib/otaUpdate.ts
- Prop market one side per line
- NCAAF search feature matrix
- tests/test_clv_backfill_job.py
- tests/test_nfl_prop_thresholds.py
- tests/test_nhl_research_job.py
- tests/test_settlement_timing.py
- NFL live pick writer
- tracking/model_quality.py
- NCAAF search walk-forward validation
- MLB runline retrain sweep job
- mobile/docs/UX_REVIEW.md
- Paused and no-signal row tests
- NBA prop stat settlement tests
- First pitch guard tests
- supabase/functions/_shared/discord.ts
- NFL odds cache import to Supabase
- tests/test_health_check_observe.py
- Intraday freshness tests
- Prop ladder and Kalshi pricing
- NFL prop shape simulation
- NFL in-play win probability fits
- tests/test_pick_lock_is_on_picks.py
- System health checks
- NFL 2026 rule track tests
- NBA prop market model and card
- UFC event ingest fakes
- tests/test_mlb_sbr_twin.py
- tests/test_ufc_phantom_filter.py
- Slate concentration and fade risk checks
- tests/test_team_stats_asof_invariants.py
- CLV off DraftKings line tests
- docs/sports: ufc + golf
- tests/test_batter_prop_log_pin.py
- tests/test_opp_starter_features.py
- mobile/docs/BILLING.md
- NFL CLV backtest and feature build
- tests/test_merge_mlb_twin_games.py
- supabase/functions/discord-link/index.ts
- tests/test_discord_channel_probe.py
- tests/test_nfl_prop_clv.py
- tests/test_prune_keeps_the_close.py
- Game outcome target tests
- tests/test_scoring_methods.py
- .claude/agents: frontend-ux-designer + CLAUDE
- .claude/rules/picks-and-publishing.md
- .claude/rules/model-updates.md
- Mobile bankroll tests
- NCAAF outcome edge scan
- Live monitor dashboard cache and docs
- docs/signal_timing.md
- scripts/ncaaf_search/situational_spots.py
- mobile/docs/DISCORD_LINKING.md
- Threshold review test fixtures
- Monitoring server tests
- NCAAF gameday cadence tests
- nfl/scripts/backtest_opener.py
- Mobile player detail tests
- MLB retrain freeze tests
- tests/test_latest_odds_views.py
- Multi-book odds tests
- Threshold review DDL tests
- tests/test_model_game_savepoint.py
- NBA schedule ingestor and tests
- tests/test_nfl_prop_settle_name_fallback.py
- NFL recap waits for box scores tests
- Results recap backfill
- tests/test_transaction_pooler.py
- NHL prop settlement tests
- CFBD refresh and backfill tests
- docs/live_betting.md
- Team stats as-of invariant tests
- mobile/tsconfig.json
- tests/test_promote_external.py
- NBA injury report slot schedule
- Declared worker job validation tests
- Local store cache and NFL prop shape simulation
- tests/test_pipeline_report_rollback.py
- supabase/functions/sharpsports/index.ts
- NBA lineup stint derivation
- NFL pick monitor game id tests
- Pregame line poller change detection
- MLB game market and public fade cards
- NFL model bundle restore docs
- Pipeline watch and burn alerts
- Discord link and Whop memberships
- tests/test_worker_deps.py
- Mobile package manifest
- Pitcher prop feature rows
- tests/test_sbr_loader.py
- Price floor and prop pick decisions
- docs/sports/wnba.md
- NFL live pick writer refusals
- NFL stale card file tests
- scripts/ncaaf_search/weather_totals.py
- Anon grants admin script
- tests/test_mobile_stat_labels_match_the_server.py
- tests/test_ncaaf_fcs_visitor_names_migration.py
- tests/test_nfl_prop_unstarted_clear.py
- NBA, NCAAF and NFL research labs
- tests/test_nhl_three_way_lookahead.py
- Trainer no-register tests
- Prop lookahead window tests
- tests/test_savant_freshness.py
- tests/test_scorer_nfl_prop_like_escape.py
- Global EV floor and honest EV
- Run ledger health tests
- Pipeline run ledger
- tests/test_score_when_lines_open.py
- NHL blocked shots settlement tests
- Monitoring server tests
- NCAAF opener strategy experiments
- tests/test_sbr_loader.py
- CLV no-vig capture tests
- mobile/docs/AUTHENTICATION.md
- NBA injury report scope dates
- Paused model assessment tests
- MLB in-play game state alignment
- Prop alternate line fetch tests
- NCAAF steam lag study
- tests/test_clear_unauthorized_auto_pauses_migration.py
- tests/test_ncaaf_se_louisiana_alias_migration.py
- tests/test_nfl_props.py
- tests/test_overnight_polling.py
- NFL wind card book filter tests
- Prop no-bet row survival tests
- tests/test_revoke_remaining_grants.py
- Mobile bankroll storage
- tests/test_live_slate_midnight.py
- tests/test_nhl_stats_ingestor.py
- NHL opening night goalie tests
- tests/test_sbr_loader.py
- NFL odds cache import
- ncaaf_live/tests/test_cfbd_yardline.py
- scripts/mlb_bet_record_audit.py
- NCAAF FBS gate tests
- NCAAF search opener cache
- tests/test_claude_rules_split.py
- tests/test_db_setup.py
- tests/test_dedupe_opening_signals.py
- Multi-book odds pregame cutoff tests
- tests/test_every_named_book_is_fetched.py
- NHL blocked shots card tests
- tests/test_pbp_backfill_resilience.py
- NCAAF starter-out study
- tests/test_scorer.py
- App read surface tests
- .claude/rules/frontend.md
- tests/test_sbr_loader.py
- docs/health_checks.md
- Prop training dataset builders
- docs/retrain_2026_plan.md
- Brand avatar and connection probes
- mobile/scripts/verify_stats_filter_ux.ts
- NFL prop backtest model and universe rate
- Feature matrix dtype coercion
- Feature map tests
- NCAAF live loop timing tests
- NFL in-play edge study helpers
- NCAAF quarterback ablation study
- tests/test_game_log_backfill_skip.py
- NFL opener tick latency tests
- tests/test_nfl_props.py
- NCAAF line move spots
- Full record post tests
- tests/test_prompt_reads_thresholds.py
- tests/test_system_health_meta_steps.py
- tests/test_weekly_catch_up.py
- NBA period scores ingestor and tests
- tests/test_sbr_loader.py
- tests/test_umpire_ingestor.py
- scripts/render_brand_icons.py
- NFL prop lean concentration study
- Prop odds book update-time tests
- NFL pick monitor
- Dashboard rule model tests
- tests/test_nhl_props.py
- supabase/functions/stripe-webhook/index.ts
- tests/test_drop_voided_nfl_wind_opening_signals_migration.py
- tests/test_live_pregame_total_line.py
- tests/test_mobile_neutral_signal_label.py
- Mobile stat segment tests
- NFL prop opening signal cleanup tests
- Live quote score clock
- tests/test_scorer_commits_per_game.py
- NFL prop card publisher tests
- Voided pick exclusion tests
- SQL percent escaping tests
- Multi-book fallback response tests
- tests/test_live_game_state_poller.py
- Wind stake calibration tests
- NFL prop pulled quote filter
- NCAAF venue feature tests
- Feedback threads migration
- docs/reviews/2026-09-07-nfl-props-deep-dive.md
- NFL prop lead ceiling tests
- NFL prop modeling tables
- NFL prop studies and monitoring docs
- railway.json
- supabase/functions/sharpsports-webhook: index + index
- Worker-only create site tests
- NHL game logs migration
- supabase/functions/revenuecat-webhook/index.ts
- supabase/functions/stripe-checkout/index.ts
- supabase/functions/whop-webhook/index.ts
- tests/test_book_list_budget.py
- tests/test_model_quality.py
- tests/test_nfl_props.py
- Model trainer and WNBA points rebuild
- Team stats board tables
- Decide on best price migration
- Mobile NHL look-ahead window tests
- NHL prop alternate line tests
- SBR historical odds loader
- NBA injury report player matching
- data/ingestors/live_game_state_poller.py
- tests/test_sbr_loader.py
- NHL as-of lookup tests
- docs/market_coverage.md
- One pick per event record tests
- mobile/scripts/verify_a11y.ts
- Scorer confidence tier and pick label tests
- Mobile auth hook
- Scorer injury flag tests
- Game line market sweep job
- Retrain job validation
- tests/test_demote_ncaaf_over_under_platt.py
- Umpire feature retirement tests
- tests/test_discord_post_one_pick_migration.py
- tests/test_game_scorer_spares_nfl_props.py
- NCAAF ESPN state fetch tests
- tests/test_mobile_ota_self_update.py
- NFL DraftKings line snapshot tests
- tracking/model_quality.py
- Live orchestrator floor pass tests
- NBA injury report PDF parser
- tests/test_nfl_props.py
- tests/test_nhl_three_way_lookahead.py
- Disk IO indexes migration
- Calibration schema migration tests
- NCAAF odds feed outage tests
- tests/test_team_board_commence_bound.py
- (root): pr-ci + requirements
- NFL prop book sweeps and two sharps
- Live game state tables
- NFL in-play edge study 2024
- Schema SQL splitter tests
- NHL moneyline rebuild write-up
- NHL four prop bets a night
- Bookmaker whitelist tests
- NBA injury report retry tests
- NCAAF player stats leaderboard
- Pregame poller and Bovada feed
- Insert column alignment tests
- NCAAF FBS registry fakes
- Mobile bankroll hook
- Scored pick outcomes lateral fix
- Mobile entitlement and subscription hooks
- NFL live pick date tests
- NHL starter name lookup tests
- NCAAF play-by-play puller
- NCAAF tables migration
- Scorer keeps off-DraftKings priced bets tests
- docs/game_injury_gate.md
- Clock and shot value parsing
- nfl/scripts/live_prop_job.sh
- NFL prop lean gradient study
- NHL blocked shots player identity tests
- Mobile package manifest
- tests/test_score_when_lines_open.py
- tests/test_score_when_lines_open.py
- tests/test_score_when_lines_open.py
- Anon grant plan tests
- NFL player stats leaderboard
- .claude/settings.json
- NBA player game log RPCs
- scripts/refresh_pass.sh
- NFL wind totals runbook and staking
- Parlay leg correlation estimates
- NFL research backup and restore script
- Board markets lock-down tests
- Model quality volume spikes
- NFL live pick multi-player tests
- NFL prop artifact parameter tests
- Market handicap features
- tests/test_score_when_lines_open.py
- tests/test_team_stats_asof_invariants.py
- tests/test_team_stats_asof_invariants.py
- tests/test_team_stats_asof_invariants.py
- Player news migration
- tests/test_weekly_catch_up.py
- NCAAF travel geography features
- NHL goalie line helpers
- Opponent starter feature stubs
- Signal publish connection fakes
- mobile/docs/BILLING.md
- Live money no record-only tests
- Team stats twin code tests
- tests/test_nfl_scored_rows.py
- tests/test_team_stats_asof_invariants.py
- NFL live pick tee recorder
- Umpire feature drop declaration tests
- tests/test_weather_lookahead.py
- Scorer subset delete tests
- Mobile accessibility verify script
- docs/testing.md
- mobile/scripts/verify_a11y.ts
- Kalshi game markets migration
- mobile/scripts/verify_a11y.ts
- Kalshi prop ladders migration
- NCAAF QB game migration
- Opening signals shadow track
- Strategy analysis report
- Live scorer pick signature
- NBA injury report name and team parsing
- CLAUDE.md
- mobile/scripts/verify_a11y.ts
- Custom model backtest RPCs
- NFL live model tables
- NCAAF state build paths
- Model pause helper tests
- Team stats verify alias test
- MLB public fade empty connection
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
- SQLite test database fixture
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
- NFL live pick announcer
- Game weather issued migration
- Odds API quota migration
- Parlay correlations migration
- Pick placement checks migration
- NHL blocked shots prop settlement tests
- App RPC declaration tests
- Stale pause flag detection tests
- Real pause not stale test
- NCAAF CFBD line bookmaker label
- NFL wind publisher lock tests
- NHL prop count distribution
- NCAAF feature assembly
- NCAAF CFBD call budget test
- Discord signals publish worker job
- SBR cross-check script
- NCAAF feature engine test database
- NFL prop lead ceiling fixture
- Weekly catch-up cursor fake
- Prop market chunking
- Pregame poller quoted keys
- NHL prop alternate line gate tests
- Pause table fails open test
- NCAAF kickoff parsing test
- NFL opener sharp-vs-soft findings
- NHL prop slate time test
- Threshold review milestone
- Threshold review kill switch
- NCAAF odds cadence test
- NCAAF naive kickoff test
- Transitive helper grant test
- Lock-down identifier test
- Archive table create site test
- SQLite schema split tests
- NCAAF bowl game test
- NCAAF provider preference test
- NCAAF sport dispatch test
- NCAAF dropna geography test
- NFL prop market rule and card
- NCAAF sparse column exemption test
- Pregame poller runaway cap test
- Pregame poller subset order test
- Pregame poller reseed interval test
- Service role job filter test
- Threshold review never unpauses
- Threshold review pause write test
- Threshold review announce test
- Scorer pause helper test
- Review tables worker-only test
- Threshold review announcement

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
- `4.3 Player props — one rule ships` --references--> `run_nba_prop_window()`  [INFERRED]
  docs/nba_models_2026.md → scheduler.py
- `2. Data used (all in Supabase)` --references--> `odds()`  [INFERRED]
  docs/nba_models_2026.md → tests/test_latest_line_state.py
- `3. The market grid` --references--> `odds()`  [INFERRED]
  docs/nba_models_2026.md → tests/test_latest_line_state.py
- `Gate 1: win probability Brier 0.115 PASS vs 0.20` --semantically_similar_to--> `Gate 1: win probability Brier 0.1654 PASS vs 0.20`  [INFERRED] [semantically similar]
  ncaaf_live/README.md → nfl/live_model/README.md
- `Gate 2: total shape 2.60pp FAIL vs 2.0pp` --semantically_similar_to--> `Gate 2: total quantile coverage 1.26pp PASS vs 2.0pp`  [INFERRED] [semantically similar]
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

## Communities (897 total, 221 thin omitted)

### Community 0 - "ESPN injury ingestor"
Cohesion: 0.07
Nodes (20): _athlete_name(), _compute_return_ramp(), _espn_team_ids(), fetch_espn_injuries(), _fetch_espn_team_injuries(), fetch_mlb_transactions(), _fetch_nba_espn_team_ids(), fetch_return_ramp_players() (+12 more)

### Community 1 - "Mobile stats board"
Cohesion: 0.01
Nodes (333): flags, players, r1, r2, r3, r4, r5, r6 (+325 more)

### Community 2 - "Mobile markets and formatting"
Cohesion: 0.02
Nodes (253): alone, dkUser, fits, hrUser, live, many, ml, mlRows (+245 more)

### Community 3 - "Odds, prop odds and NHL derivative odds ingestors"
Cohesion: 0.01
Nodes (150): ConnectionLost, build_ncaaf_game_id(), resolve_odds_api_school(), buy_derivatives(), _write(), buy_lines(), _write(), buy_props() (+142 more)

### Community 4 - "Feature engine and live scorer loading"
Cohesion: 0.01
Nodes (162): pregame_cutoff_sql(), trusted_first_pitch(), query_injuries_for_game(), _blk_bullpen_ip(), _blk_injuries(), _blk_nhl_loc_goals(), _blk_nhl_rolling_goals(), _blk_pitcher() (+154 more)

### Community 5 - "Mobile theme, parlays and sportsbook links"
Cohesion: 0.02
Nodes (228): styles, Props, styles, styles, BetslipBarSpacer(), styles, Nav, styles (+220 more)

### Community 6 - "Paper tracker bankroll and scorer database calls"
Cohesion: 0.01
Nodes (161): today_et(), connection_lost(), DBConnection, rollback_savepoint(), statement_timeout(), poll_once(), _compute_calibration_factor(), _games_needing_synthesis() (+153 more)

### Community 7 - "MLB over/under retrain sweep tests"
Cohesion: 0.10
Nodes (10): _side_rows(), test_marker_file_is_in_tree_so_the_freeze_would_not_block_the_worker(), test_missing_artifact_path_refuses_to_sweep_live(), test_over_covers_when_combined_score_beats_the_total_line(), test_price_below_the_house_floor_is_not_a_gradable_side(), test_push_on_the_total_emits_no_sides(), test_retrain_then_sweep_passes_the_new_path(), test_the_runner_retrains_then_sweeps_the_new_artifact() (+2 more)

### Community 8 - "Mobile player log and matchup stats"
Cohesion: 0.02
Nodes (206): allNull, at1, at2, axLarge, axXL, axXXXL, benchedQb, firstCommit (+198 more)

### Community 9 - "Database connection and CLI ingestor scripts"
Cohesion: 0.01
Nodes (172): _connect(), get_connection(), _open(), _session_options(), _load_postgres_schema(), setup_database(), _fetchone(), schema_is_current() (+164 more)

### Community 10 - "NFL prop market stack and devig"
Cohesion: 0.07
Nodes (30): closing_prices(), devig(), ecdf_p_over(), main(), main(), bets(), design(), main() (+22 more)

### Community 11 - "Direct sportsbook feeds and freshness probes"
Cohesion: 0.09
Nodes (18): main(), probe_book(), verdict(), egress_ip(), _probe_once(), _proxies(), reachability(), _session() (+10 more)

### Community 12 - "Mobile pick filters and sorting"
Cohesion: 0.02
Nodes (205): boardDates, detail, empty, every, filters, gfs, linkRow, oneDay (+197 more)

### Community 13 - "Discord signal notifier tests"
Cohesion: 0.02
Nodes (97): test_producer_output_builds_a_live_embed(), _cand(), _et_now_iso(), _FakeConn, _FakeResult, _freeze_now(), _live_row(), _live_setup() (+89 more)

### Community 14 - "Mobile custom model filters and metadata"
Cohesion: 0.02
Nodes (240): scorable, PAUSED, pickerIds, base, loss, msg, neg, cs (+232 more)

### Community 15 - "X publisher"
Cohesion: 0.03
Nodes (39): _creds_on(), _fake_conn(), _split(), test_a_clean_ledger_allows_the_post(), test_a_day_with_nothing_graded_carries_no_clv_line(), test_a_day_with_nothing_risked_states_units_and_does_not_divide(), test_a_split_that_cannot_fit_says_how_many_it_dropped(), test_a_transport_failure_returns_none_rather_than_raising() (+31 more)

### Community 16 - "Daily pipeline runner and push notifier"
Cohesion: 0.02
Nodes (74): run_ncaaf_stats_ingestor(), run_bullpen_ingestor(), run_nfl_results_ingestor(), run_player_news_ingestor(), format_view_migration_failure(), check_env(), _golf_enabled(), _import_step() (+66 more)

### Community 17 - "Discord units convention tests"
Cohesion: 0.29
Nodes (4): test_prob_only_picks_fall_back_to_the_settlement_price(), test_units_convention_matches_the_stated_rule(), _decimal_odds(), units_won()

### Community 18 - "Mobile thresholds and daily results"
Cohesion: 0.02
Nodes (109): all, COUNTED_MODELS, empty, games, hrOnly, liveDay, nhlScope, pendingOnly (+101 more)

### Community 19 - "Picks email renderer"
Cohesion: 0.46
Nodes (6): _fmt_edge(), _fmt_odds(), main(), Pick, _pick_card(), render_email()

### Community 20 - "Mobile formatting and live status checks"
Cohesion: 0.04
Nodes (80): check(), g(), main(), read(), ROOT, SLATE, deadPoller, delayed (+72 more)

### Community 21 - "NFL edge study shared library"
Cohesion: 0.04
Nodes (81): backfill_cost(), bets(), bh(), clean_2h(), fmt(), forward_2026(), hdr(), _line_models() (+73 more)

### Community 22 - "NBA prop projection card"
Cohesion: 0.08
Nodes (31): step_mlb_total_public_fade(), step_nba_prop_project(), backfill_official(), decided_games(), ensure_tables(), espn_pulls(), espn_rows(), fill_espn_history() (+23 more)

### Community 23 - "NFL in-play edge study 2024"
Cohesion: 0.14
Nodes (32): s(), books_per_snapshot(), cell(), h1(), h2(), h2_accuracy(), h3(), h3_accuracy() (+24 more)

### Community 24 - "NHL market lab and live artifact grading"
Cohesion: 0.03
Nodes (97): accuracy(), first_games(), logloss(), main(), sweep(), units(), walk(), decide() (+89 more)

### Community 25 - "NBA play-by-play ingestor"
Cohesion: 0.07
Nodes (38): active_queries(), _bool(), box_context(), box_finals(), build_game(), build_map(), _date10(), download() (+30 more)

### Community 26 - "Mobile team detail and team stats"
Cohesion: 0.02
Nodes (182): again, bogus, catalog, dh, dhIdx, dhIdxLate, emptyIdx, h (+174 more)

### Community 27 - "Parlay builder and bet slip"
Cohesion: 0.02
Nodes (193): barPickA, barPickB, barPicks, BOOKS, correlated, custom, ghost, ghostKeys (+185 more)

### Community 28 - "CLV price-taken tests"
Cohesion: 0.06
Nodes (27): _Conn, _fn(), _migration(), _pick(), _Res, test_a_draftkings_decided_row_is_unchanged(), test_a_legacy_row_that_cannot_be_re_measured_leaves_the_old_method(), test_a_legacy_stamped_row_is_re_measured_and_leaves_the_queue() (+19 more)

### Community 29 - "In-play history and play-by-play ingestors"
Cohesion: 0.03
Nodes (74): closed_tables(), lock_down(), lock_down_sql(), _get(), _iso(), main(), planned_calls(), pull_day() (+66 more)

### Community 30 - "NFL live prop model tests"
Cohesion: 0.04
Nodes (39): _core_worker(), _FakeOdds, _IdRecordingOdds, _Q, test_a_deployed_bias_must_sit_inside_its_measured_interval(), test_a_matching_board_keeps_the_fast_cadence(), test_a_one_sided_quote_is_skipped_rather_than_priced_on_raw_juice(), test_a_player_with_no_accrued_count_is_declined_end_to_end() (+31 more)

### Community 31 - "NBA prop model core"
Cohesion: 0.03
Nodes (78): compact_report(), minutes_cols(), predict_means(), rate_cols(), alias_key(), all_rates(), _attach_report_ids(), base_key() (+70 more)

### Community 32 - "NCAAF in-play score distribution engine"
Cohesion: 0.03
Nodes (58): _cluster_bootstrap(), evaluate(), main(), report(), fit(), load_states(), main(), walk_forward_oos() (+50 more)

### Community 33 - "nfl/live_model/feeds: test_feed_resilience + espn"
Cohesion: 0.04
Nodes (54): _competitors(), _deref(), fetch_live_events(), _https(), make_fetcher(), fetch(), parse_core_event(), _score() (+46 more)

### Community 34 - "Mobile feedback and social links"
Cohesion: 0.06
Nodes (54): RFC-4122, base, generic, input, inputOrder, pgParsed, serverWhitelist, sorted (+46 more)

### Community 35 - "Mobile app shell and push notifications"
Cohesion: 0.02
Nodes (123): App(), DailyRecap(), IoniconName, NAV_THEME, NO_BETSLIP_BAR_ROUTES, Stack, Tab, TAB_ICONS (+115 more)

### Community 36 - "tests/test_cfbd_ingestor.py"
Cohesion: 0.03
Nodes (59): _day_before(), eastern_game_date(), _local_aggregates(), parse_games(), parse_lines(), parse_teams(), retain_existing_cfbd_ids(), shrink_to_prior() (+51 more)

### Community 37 - "EV floor and threshold sweep scripts"
Cohesion: 0.08
Nodes (32): analyse(), split(), _basis(), _cut(), fetch(), main(), analyse(), _apply_price_floor() (+24 more)

### Community 38 - "Odds pruning and sharp book retention tests"
Cohesion: 0.09
Nodes (13): _prop_reference_books(), protected_for(), _RecordingConn, test_a_shopping_book_is_still_prunable(), test_every_prop_reference_book_is_protected(), test_every_sharp_book_is_protected_in_the_prop_table(), test_pinnacle_specifically_is_protected_in_the_prop_table(), test_prune_table_binds_the_prop_tables_carve_out_into_the_DELETE() (+5 more)

### Community 39 - "nfl/live_model/tests/test_executor.py"
Cohesion: 0.06
Nodes (45): Decision, derivative_lag(), ev_floor(), Executor, _mk(), expected_value(), honest_probability(), is_hunt_state() (+37 more)

### Community 40 - "NFL wind edge studies"
Cohesion: 0.06
Nodes (59): load_games(), main(), pivot_spreads(), pivot_totals(), load_games(), main(), wide_spreads(), wide_totals() (+51 more)

### Community 41 - "tests/test_live_quote_staleness.py"
Cohesion: 0.04
Nodes (48): build_row(), _mark_written(), now_iso(), _publish_key(), quote_from_nfl_quotes(), record_live_prices(), rows_from_quote(), _abbrev() (+40 more)

### Community 42 - "DataGolf ingestor and NHL SBR archive"
Cohesion: 0.05
Nodes (47): _american(), backfill_golf_rounds(), build_game_id(), _dg_get(), _earliest_commence_iso(), _event_meta_lookup(), event_slug(), ingest_golf_field() (+39 more)

### Community 43 - "tests/test_job_queue.py"
Cohesion: 0.04
Nodes (44): _DedupeConn, _posted_row(), _run_void(), _run_void_job(), test_a_declared_job_is_queued_once_however_often_it_is_read(), test_a_failed_job_needs_a_new_key_to_rerun(), test_a_graded_pick_is_refused_not_rewritten(), test_a_missing_declarations_file_is_silent() (+36 more)

### Community 44 - "scripts: build_nfl_live_leader_artifact + model"
Cohesion: 0.05
Nodes (39): am_to_dec(), Artifact, artifact_from_dict(), band_for(), decide(), Decision, leader_expected_margin(), load_artifact() (+31 more)

### Community 45 - "tests/test_nfl_prop_one_read_per_game.py"
Cohesion: 0.06
Nodes (25): publish_hour_missed(), publishable_games(), _at(), _Conn, _games(), _Log, test_a_game_is_publishable_on_exactly_one_pass_in_its_window(), test_a_game_with_no_kickoff_is_never_published() (+17 more)

### Community 46 - "Worker job queue"
Cohesion: 0.03
Nodes (30): derive_first_pitch(), test_the_worker_job_is_registered_and_defaults_to_dry_run(), test_the_discord_publish_job_takes_an_optional_date(), _announce(), _execute(), _job_derive_first_pitch(), _job_game_log_backfill(), _job_health_check() (+22 more)

### Community 47 - "scripts/nfl_edge_gameline_rules.py"
Cohesion: 0.06
Nodes (50): _nhl_blended_features(), d(), ats(), bettable_ats(), bh(), board_at(), board_open(), bstat() (+42 more)

### Community 48 - "tests/test_calibration_watch.py"
Cohesion: 0.06
Nodes (14): _Conn, _Res, _row(), TestDormantLiveModels, TestRosterChanges, TestTheRun, TestVerdictChanges, TestVolumeShifts (+6 more)

### Community 49 - "Failure alerter fake-connection tests"
Cohesion: 0.05
Nodes (22): _clean_runs(), FakeConn, _posts(), _state_dir(), TestDeliveryAndNoise, TestHealthCheckOnlyIsNotADirtyPass, TestItCannotBreakTheWorker, TestSilentJobs (+14 more)

### Community 50 - "scheduler.py"
Cohesion: 0.05
Nodes (51): _run_migrations(), serve_in_thread(), abort_orphaned_refresh_runs(), build_scheduler(), _add_job(), _with_heartbeat(), _wrapped(), catch_up_daily_pipeline() (+43 more)

### Community 51 - "NFL live moneyline and total pricing tests"
Cohesion: 0.07
Nodes (37): _model_price(), gaussian_copula_joint(), american_to_decimal(), american_to_prob(), anchor_to_market(), devig_power(), margin_pmf(), _over_under() (+29 more)

### Community 52 - "tests/test_best_line_live.py"
Cohesion: 0.04
Nodes (46): _make_live_pick(), _best_live_price(), _best_live_side(), _live_book_quotes(), _live_decision_quote(), _live_quote_is_on_offer(), _tag_live(), _ev() (+38 more)

### Community 53 - "NFL player stats ingestor and prop tests"
Cohesion: 0.06
Nodes (25): _to_int(), _to_num(), _fetch_snap_csv(), games_rows(), ingest_season(), _int_or_none(), _kickoff_utc(), _num_or_none() (+17 more)

### Community 54 - "tests/test_void_picks.py"
Cohesion: 0.05
Nodes (20): announce_posted_voids(), build_parser(), main(), plan_voids(), _posted_sql(), _select(), void(), _FakeConn (+12 more)

### Community 55 - "NCAAF gameday worker and ESPN feed"
Cohesion: 0.05
Nodes (31): fetch_scoreboard_cfbd(), fetch_team_ids(), _headers(), fetch_scoreboard(), fetch_summary(), LiveOddsFeed, _choose_context(), _fold() (+23 more)

### Community 56 - "tests/test_daily_retry.py"
Cohesion: 0.06
Nodes (42): _aborted(), _aborted_row(), _Conn, _Cursor, _FrozenDatetime, _ok(), _ok_row(), _run() (+34 more)

### Community 57 - "tests/test_live_book_move_guard.py"
Cohesion: 0.08
Nodes (38): american_to_implied(), BookMoveClock, _at(), _delaware_ctx(), _dk(), _iso(), _mlb_odds(), _mlb_ts() (+30 more)

### Community 58 - "tests: test_discord_notifier + test_discord_live_field"
Cohesion: 0.04
Nodes (40): _sig(), test_a_strictly_better_book_becomes_the_headline(), test_an_equal_or_worse_price_never_replaces_draftkings(), test_draftkings_winning_its_own_shop_is_published_as_draftkings(), test_every_pre_game_producer_computes_good_to(), test_good_to_is_published_when_the_producer_supplies_it(), test_good_to_is_simply_absent_when_it_cannot_be_computed(), test_it_works_on_plus_money_too() (+32 more)

### Community 59 - "NFL odds API pulls and snapshots"
Cohesion: 0.05
Nodes (32): _key(), _ledger_bump(), _ledger_read(), ledger_status(), _ledger_write(), OddsAPIClient, SnapshotResult, snapshot_to_frame() (+24 more)

### Community 60 - "tests: test_wnba_availability + wnba_availability"
Cohesion: 0.06
Nodes (50): absence_features(), absent_teammates(), build_context_features(), expected_rotation(), is_starter_tier(), _mean(), prior_rows(), recent_team_game_dates() (+42 more)

### Community 61 - "mobile/src/hooks: verify_tracked_performance + useStakeSettings"
Cohesion: 0.05
Nodes (58): dup, empty, half, l50, loss, noAction, open1, open2 (+50 more)

### Community 62 - "NBA game market lab"
Cohesion: 0.05
Nodes (62): assemble(), _assert_spread_sign(), attach_close(), bars(), bet_frame(), blind_bets(), blind_first_fetch(), boot_ci() (+54 more)

### Community 63 - "NFL live game state"
Cohesion: 0.10
Nodes (19): script_trigger_fired(), _as_float(), _as_int(), _as_opt_float(), _as_opt_int(), from_espn(), from_extract(), from_pbp_row() (+11 more)

### Community 64 - "NFL live model backtest harness"
Cohesion: 0.05
Nodes (33): align_states(), build_team_map(), _game_index(), kill_verdict(), load_cached_snapshots(), main(), replay(), _settle() (+25 more)

### Community 65 - "NFL live score distribution and calibration"
Cohesion: 0.10
Nodes (10): _cluster_bootstrap(), evaluate(), main(), report(), mu_bucket(), _mu_centres(), ScoreDistribution, _spearman_to_gaussian() (+2 more)

### Community 66 - "docs/nfl_props_model.md"
Cohesion: 0.06
Nodes (46): tackles_assists +21% is a measurement error (control), Prompt: build a profitable NFL player-props model, Traps specific to props, docs/nfl_props_model.md, Anytime TD field de-vig: closed, #215 artifacts could not be deserialised, betonlineag as a second sharp reference (OR, not AND), Book census: 14 books served, 6 used (+38 more)

### Community 67 - "tests/test_game_market_gate.py"
Cohesion: 0.06
Nodes (50): apply_to_picks(), _as_float(), bookend_from_odds(), evaluate(), fair_prob(), first_eligible_snapshot(), GateVerdict, _line_changed() (+42 more)

### Community 68 - "tests: test_db_url_doctor + test_envfile_fallback"
Cohesion: 0.12
Nodes (13): _classes(), main(), database_url(), _default_env_path(), env_value(), parse_env_file(), test_a_missing_env_file_is_empty_not_an_error(), test_a_value_containing_equals_survives() (+5 more)

### Community 69 - "tests/test_pick_integrity.py"
Cohesion: 0.04
Nodes (38): _add_pick(), _Conn, discord_sent(), _health(), health_db(), _Shim, test_a_label_may_not_name_a_market_the_pick_does_not_settle_on(), test_a_label_naming_the_other_team_is_refused() (+30 more)

### Community 70 - "tests/test_record_one_pick_per_event.py"
Cohesion: 0.05
Nodes (39): _CaptureConn, _code(), _copy_for_node(), _fn(), _node(), _read(), _RecordingConn, test_a_custom_model_counts_the_kept_copy_once() (+31 more)

### Community 71 - "tests/test_live_orchestrator.py"
Cohesion: 0.05
Nodes (34): should_fetch(), split_triggers(), under_credit_cap(), apply_daily_cap(), classify_live_signal(), _ev_floor(), _t(), test_a_model_with_no_floor_is_unaffected() (+26 more)

### Community 72 - "tests/test_market_handicap.py"
Cohesion: 0.05
Nodes (33): attach_market_handicap(), build_public_features(), empty_handicap(), favorite_side(), _rlm(), row_is_pregame(), select_latest_pregame_splits(), _split() (+25 more)

### Community 73 - "nfl/live_model/tests: test_props + props"
Cohesion: 0.09
Nodes (33): _accrued(), _count(), detect_inactive(), price_over(), project(), PropProjection, _rate(), remaining_team_plays() (+25 more)

### Community 74 - "Prop CLV and SQL escaping tests"
Cohesion: 0.06
Nodes (24): _is_main_guard(), _modules_with_guard(), test_at_least_one_entrypoint_is_scanned(), test_nothing_is_defined_after_the_main_guard(), test_the_report_script_exists_and_parses(), test_the_nfl_label_map_is_the_inverse_of_the_nfl_publisher(), _fn(), test_a_backfill_failure_never_breaks_settlement() (+16 more)

### Community 75 - "scripts: ncaaf_margin_eval + test_ncaaf_margin_eval"
Cohesion: 0.07
Nodes (31): margin_cover_prob(), build_frames(), _fit(), fit_and_register(), fit_and_register_totals(), main(), _matrix(), _print_sweep() (+23 more)

### Community 76 - "ncaaf_live/tests/test_serve.py"
Cohesion: 0.04
Nodes (58): _clock_seconds(), extract_live_states_cfbd(), school(), _parse_situation(), _strip_mascot(), check_feed_assumptions(), _competitors(), _count_plays() (+50 more)

### Community 77 - "tests/test_wnba_prop_market.py"
Cohesion: 0.05
Nodes (33): apply_price_floor(), main(), norm_name(), pick_rows(), player_ids(), publish(), render(), run_card() (+25 more)

### Community 78 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.09
Nodes (15): _After, _bet_row(), _Conn, _dump(), _eval(), _kick(), _none_row(), _RaceConn (+7 more)

### Community 79 - "NHL derivative totals model"
Cohesion: 0.04
Nodes (49): build_p1_frame(), build_team_frame(), day_interval(), _ew(), fit(), game_means(), _implied_vec(), Market (+41 more)

### Community 80 - "Global EV floor and NHL totals tests"
Cohesion: 0.05
Nodes (39): _coherent(), _fetch_ts(), find_bets(), load_fetch_quotes(), NhlTotalBet, _ts(), _two_way(), main() (+31 more)

### Community 81 - "docs: nhl_market_lab + nhl_clv_ev_assessment"
Cohesion: 0.08
Nodes (41): DraftKings de-vigged price sits above realised over-rate, NHL models CLV and EV assessment (2026-10-08), Anytime goalscorer: not a candidate once names corrected, nhl_moneyline and nhl_moneyline_regulation: no cut clears, Game models: lock later? Refuted, Name-key matching attached prices to both namesakes, nhl_research worker job, nhl_over_under live as a market-anchored rule (models/nhl_totals_market.py) (+33 more)

### Community 82 - "Mobile TypeScript test runners"
Cohesion: 0.02
Nodes (87): main(), node_exe(), node_strips_types(), tsx_cmd(), _node_strips_types(), test_today_et_ignores_the_container_timezone(), _node_strips_types(), _read() (+79 more)

### Community 83 - "NHL prop wiring tests"
Cohesion: 0.14
Nodes (5): _log(), _players(), TestEveryLiveModelIsWiredEverywhere, TestTheGoalieFrame, TestTonightsRowIsATrainingRow

### Community 84 - "Discord notifier and void notices"
Cohesion: 0.03
Nodes (61): test_delete_posted_degrades_when_the_column_is_missing(), test_sport_routes_to_its_own_channel_then_the_default(), _bind(), Ledger, _pg_bin(), _row(), _swap_dbname(), test_a_non_2xx_response_and_a_request_exception_record_nothing() (+53 more)

### Community 85 - "tests/test_recap_retries_a_skipped_day.py"
Cohesion: 0.06
Nodes (26): _add_pick(), _grade(), _lite(), _LiteConn, _schema(), test_a_day_with_nothing_counting_posts_nothing_and_logs_nothing(), test_a_failed_receipt_never_reposts_the_day(), test_a_failed_receipt_on_a_restatement_never_repeats_it() (+18 more)

### Community 86 - "scripts/nfl_edge_preregistered_2026.py"
Cohesion: 0.09
Nodes (39): bar(), bets_frame(), bh(), binom_line(), _by_game(), cell(), fam(), first_last() (+31 more)

### Community 87 - "tests: test_player_positions + player_positions_ingestor"
Cohesion: 0.06
Nodes (29): _basketball(), basketball_group(), _fresh_source_ids(), _get_json(), ingest_player_positions(), match_to_log(), _name_index(), _ncaaf() (+21 more)

### Community 88 - "NBA prop market tests"
Cohesion: 0.04
Nodes (57): name_key(), NbaPropBet, Roster, pick_label(), pick_rows(), _quiet(), test_reclaim_is_immediate_because_the_lock_proves_orphanhood(), test_there_is_no_shell_or_command_column() (+49 more)

### Community 89 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.04
Nodes (48): a11ySrc, allowHit, ALLOWLIST, app, badExempt, bar, bareClose, baselineLeft (+40 more)

### Community 90 - "tests/test_f5_any_book_line.py"
Cohesion: 0.08
Nodes (32): _fallback_game_line_quote(), _get_scoring_odds(), _has_real_game_price(), _make_pick(), _Clf, _cut(), _GameOddsConn, _mlb_feat() (+24 more)

### Community 91 - "NBA prop model lab"
Cohesion: 0.07
Nodes (48): books(), implied(), p_over(), settle_value(), _agg(), apply_rule(), binary_baselines(), binary_indep() (+40 more)

### Community 92 - "tests/test_ncaaf_prop_odds.py"
Cohesion: 0.05
Nodes (27): _market_chunks(), _Conn, _football_map(), resolver(), _Resp, scope(), test_a_book_we_did_not_ask_for_is_never_written(), test_a_day_with_no_college_games_spends_nothing() (+19 more)

### Community 93 - "tests/test_mlb_total_public_fade.py"
Cohesion: 0.09
Nodes (35): find_fade_bets(), is_pre_commence(), select_latest_pre_commence_over(), under_in_odds_band(), pick_rows(), rows_for_insert(), _dk_board(), _quote() (+27 more)

### Community 94 - "NFL prop model and player row parsing tests"
Cohesion: 0.02
Nodes (41): _odds_from_frame(), resolve_nfl_game_id(), resolve(), _verdict(), _art(), _odds_frame(), test_a_half_line_market_priced_to_its_own_skew_is_not_flagged(), test_a_one_way_market_stays_one_way_through_the_cache() (+33 more)

### Community 95 - "tests/test_ncaaf_pbp_store.py"
Cohesion: 0.09
Nodes (18): load_season_from_db(), _report_ranges(), store_season(), load_pbp(), _Conn, _plays(), test_a_rerun_updates_rather_than_duplicating(), test_a_season_in_neither_place_is_an_error_not_a_short_corpus() (+10 more)

### Community 96 - "tests/test_heartbeat_watchdog.py"
Cohesion: 0.08
Nodes (25): _break_db(), _FakeConn, _FakeCursor, sink(), test_a_failed_post_does_not_start_the_throttle(), test_a_healthy_start_never_announces_a_recovery(), test_a_returning_outage_alerts_again_immediately(), test_a_silent_failure_alerter_is_caught_by_the_watchdog() (+17 more)

### Community 97 - "Game injury veto gate and tests"
Cohesion: 0.05
Nodes (50): apply_to_picks(), _goalie_names(), load_sport_injury_index(), _pitcher_names(), player_matches_veto(), relevant_players(), _star_names(), stars_from_logs() (+42 more)

### Community 98 - "models: nhl_prop_blocked_shots + nhl_prop_blocked_shots_backtest"
Cohesion: 0.07
Nodes (26): build_frame(), _ew(), expected_value(), fit(), load_skaters(), load_teams(), name_key(), p_over() (+18 more)

### Community 99 - "Publish key identity tests"
Cohesion: 0.05
Nodes (25): _Conn, _key(), _KeyConn, _mobile(), _sql(), test_a_game_level_live_row_keeps_the_key_it_was_published_under(), test_a_game_level_row_keeps_the_key_it_was_published_under(), test_a_player_id_row_keeps_the_key_it_was_published_under() (+17 more)

### Community 100 - "NBA stint derivation tests"
Cohesion: 0.09
Nodes (36): order_plays(), _blowout_q4(), derive(), dreb(), end_period(), five_game(), make2(), make3() (+28 more)

### Community 101 - "NCAAF slug and orientation helpers"
Cohesion: 0.14
Nodes (8): _loose_orientation(), ncaaf_slug(), _slug_extends(), _slug_pair(), test_an_fcs_name_that_extends_an_fbs_school_passes_through_unresolved(), test_possession_seconds(), test_slug(), test_with_the_visitor_in_the_registry_it_resolves_to_itself()

### Community 102 - "scripts/nfl_edge_live_rush_pace.py"
Cohesion: 0.18
Nodes (26): _asof(), boot_p(), build_state(), first(), grade(), initial_last(), load_pbp(), main() (+18 more)

### Community 103 - "NBA prop projection tests"
Cohesion: 0.05
Nodes (29): _art(), _proj(), _q(), _run(), _settle(), test_a_book_hanging_two_lines_for_one_player_is_refused(), test_a_decision_with_no_bet_is_still_a_decision(), test_a_past_game_never_projected_gets_the_newest_espn_pull_55_minutes_before_its_tip() (+21 more)

### Community 104 - "Record correction post tests"
Cohesion: 0.06
Nodes (26): _pin(), _real_post(), _real_tweet(), x_posts(), Ledger, _publish(), _Result, test_a_failed_discord_ledger_does_not_send_x() (+18 more)

### Community 105 - "Mobile live segment wiring tests"
Cohesion: 0.06
Nodes (28): _read(), test_a_sport_switch_cannot_report_a_game_finishing(), test_all_three_segments_are_unconditional(), test_live_is_not_a_bottom_tab(), test_live_is_not_in_the_tab_param_list(), test_no_app_root_component_reaches_a_focus_aware_hook(), imports_of(), strip_comments() (+20 more)

### Community 106 - "Supabase schema tables"
Cohesion: 0.03
Nodes (101): api_call_log, device_push_tokens, feedback_messages, feedback_threads, fighters, golf_players, golf_rounds, idx_api_call_api_ts (+93 more)

### Community 107 - "tests/test_prop_calibrated_decision.py"
Cohesion: 0.07
Nodes (29): apply_prop_daily_cap(), _claimed_ev(), dedupe_player_props(), _downgrade(), _is_paused_row(), _bet(), _identity_cal(), _prop() (+21 more)

### Community 108 - "ncaaf_live/tests/test_pregame_calibration.py"
Cohesion: 0.06
Nodes (22): correct_for_pregame(), _load_pregame_calibration(), pregame_dog_points(), _real_artifact(), test_a_big_dog_is_marked_down_hard(), test_a_corrupt_artifact_leaves_the_probability_alone(), test_a_favourite_is_marked_up(), test_a_missing_artifact_leaves_the_probability_alone() (+14 more)

### Community 109 - "Best-price decision tests"
Cohesion: 0.06
Nodes (26): NFL Monday 2026-09-21: empty Today / Signals, MODEL_OWN_EV_FLOOR per model, _decision_fields(), _requalify_at_best(), _size(), emit(), main(), _dk_pick() (+18 more)

### Community 110 - "tests/test_mobile_line_movement.py"
Cohesion: 0.08
Nodes (27): _fn(), _read(), _run(), test_a_cut_table_keeps_the_pick_and_says_what_it_covers(), test_a_cut_window_keeps_the_pick_row_on_the_8_row_table(), test_a_pick_made_after_the_cards_start_never_reads_since_your_pick(), test_after_the_start_the_verdict_is_not_graded(), test_an_old_snapshot_is_not_the_price_at_the_pick() (+19 more)

### Community 111 - "tests/test_live_calibration.py"
Cohesion: 0.07
Nodes (32): pick(), test_a_peak_with_no_plateau_anywhere_is_labelled_as_one(), test_a_prob_cut_and_an_ev_cut_select_different_picks(), test_calibration_also_scores_ev_against_realised_roi(), test_calibration_is_empty_rather_than_wrong_with_nothing_settled(), test_calibration_reports_the_gap_between_claim_and_reality(), test_expected_value_matches_the_hand_calculation(), test_expected_value_refuses_a_missing_or_zero_price() (+24 more)

### Community 112 - "Push deep link and mobile player detail tests"
Cohesion: 0.03
Nodes (57): test_every_revoke_names_the_roles_rather_than_public(), test_odds_keeps_select_for_the_app(), test_the_two_rls_off_tables_lose_everything(), test_best_odds_never_reaches_the_qualifying_gate(), _navigate_blocks(), _src(), test_every_caller_states_the_stat(), test_innings_resolves_to_the_outs_chip() (+49 more)

### Community 113 - "tests/test_nfl_live_leader_gameday.py"
Cohesion: 0.05
Nodes (33): art(), FakeClient, FakeClock, FakeConn, FakeFeed, live_state(), quote_payload(), _Rows (+25 more)

### Community 114 - "nfl_live_leader/gameday.py"
Cohesion: 0.04
Nodes (47): parse_book_ts(), quote_predates_score(), _Unset, build_pick(), Cadence, evaluate(), GameContext, is_locked() (+39 more)

### Community 115 - "tests/test_calibration_promotion.py"
Cohesion: 0.07
Nodes (26): eligibility_clause(), load_calibrations(), maps_materially_differ(), promote(), FakeConn, _payload(), _row(), test_a_broken_table_is_identity_maps_not_an_exception() (+18 more)

### Community 116 - "tests/test_score_off_any_book_line.py"
Cohesion: 0.07
Nodes (34): _fallback_line_quote(), _latest_book_prop_row(), _cut(), _FakeConn, _on(), _pick(), _row(), _sql_const() (+26 more)

### Community 117 - "Heartbeat watchdog and ops alerts"
Cohesion: 0.05
Nodes (21): TestItNeverDecides, _announce(), _announce_and_ledger(), _post(), _redact_delivery_error(), _remember_delivery(), _alert(), _alerter_is_silent() (+13 more)

### Community 118 - "tests/test_recap_restatement.py"
Cohesion: 0.07
Nodes (18): _fetch_season_csv(), test_a_restated_recap_is_labelled_and_says_why(), _Conn, _resp(), test_a_404_is_an_answer_not_a_retry(), test_a_persistent_403_still_raises_after_the_last_attempt(), test_a_recap_whose_count_merely_drifted_is_not_due(), test_a_recap_with_a_late_settlement_is_due() (+10 more)

### Community 119 - "tests/test_ncaaf_live_notify.py"
Cohesion: 0.06
Nodes (17): _load_write_picks(), _restore_stubbed_modules(), test_a_caller_supplied_connection_is_not_closed_by_the_write(), test_a_failing_notifier_never_breaks_pricing(), test_a_full_slate_announces_once(), test_a_live_bet_notifies_push_and_discord(), test_a_locked_lane_keeps_notifying_after_the_engine_stops_betting(), test_a_locked_lane_still_reports_a_date_with_no_bet_this_pass() (+9 more)

### Community 120 - "tests/test_ncaaf_alias_scores.py"
Cohesion: 0.08
Nodes (31): alias_score_updates(), mirror_scores_to_alias_rows(), mirror_stored_finals(), _cfbd(), _FakeConn, _FakeCursor, _row(), test_a_bare_substring_is_not_an_extension() (+23 more)

### Community 121 - "tests/test_prop_alternate_lines.py"
Cohesion: 0.10
Nodes (18): alt_markets_due(), _Conn, _ou(), _parse(), test_a_failed_check_does_not_spend(), test_a_player_the_book_lists_at_1_5_keeps_the_0_5_alternate(), test_a_sport_with_no_alternates_never_asks(), test_a_standard_market_still_yields_one_row_per_player() (+10 more)

### Community 122 - "Game scorer core and NCAAF board visibility"
Cohesion: 0.04
Nodes (44): One BET per pitcher plus interim daily cap, _anchored_probability(), _apply_game_injury_gate(), _run(), _apply_game_market_gate(), _best_game_price_one(), _call_in_savepoint(), _current_price_since() (+36 more)

### Community 123 - "tests/test_backtester.py"
Cohesion: 0.07
Nodes (9): _calibration_error(), compute_backtest_summary(), _evaluate_result(), _iter_sides(), TestCalibrationError, TestComputeBacktestSummary, TestEvaluateResult, TestGoLiveGateConstants (+1 more)

### Community 124 - "scripts: nhl_prop_backtest + nhl_prop_ev_lab"
Cohesion: 0.09
Nodes (14): best_per_player(), history(), pool(), main(), regime(), show(), summary(), _cand() (+6 more)

### Community 125 - "nfl/live_model/feeds/odds_live.py"
Cohesion: 0.05
Nodes (27): _key(), _ledger(), main(), match_event(), Puller, _save_ledger(), snapshot_plan(), best_price() (+19 more)

### Community 126 - "monitoring/store.py"
Cohesion: 0.10
Nodes (23): meta(), ops(), snapshot(), api_rollup(), call_timeline(), calls_since(), community(), scalar() (+15 more)

### Community 127 - "NHL prop cards and cross-model publish"
Cohesion: 0.09
Nodes (19): step_nhl_prop_scoring(), bs_implied(), candidates(), identities(), latest_quotes(), main(), publish(), render() (+11 more)

### Community 128 - "tests/test_settled_record_is_immutable.py"
Cohesion: 0.05
Nodes (23): _code(), test_a_dedicated_live_lane_still_counts_and_a_pre_game_in_play_pick_does_not(), test_a_paused_model_is_not_an_excluded_model(), test_a_voided_pick_is_still_out_of_the_record(), test_both_published_views_keep_the_live_date_gate(), test_both_rules_name_the_two_exits_and_not_the_paused_flag(), test_both_views_are_redefined_by_name(), test_every_explicit_exclusion_names_who_asked_for_it() (+15 more)

### Community 129 - "NBA prop market lab"
Cohesion: 0.09
Nodes (44): add_units(), assemble(), best_per_key(), boot_ci(), build_quotes(), candidates_from(), choose_floor(), dec_from_american() (+36 more)

### Community 130 - "features/golf_feature_engine.py"
Cohesion: 0.07
Nodes (30): assemble_player_features(), _avg_finish(), build_bulk_golf_lookups(), build_golf_scoring_features(), build_golf_training_dataset(), compute_golf_target(), compute_matchup_target(), _event_finishes() (+22 more)

### Community 131 - "nfl/live_model/tests/test_backup_snaps.py"
Cohesion: 0.09
Nodes (22): back_up(), digest(), _flush(), iter_files(), main(), _mb(), psycopg2_bytes(), restore() (+14 more)

### Community 132 - "ncaaf_live/tests/test_states.py"
Cohesion: 0.13
Nodes (22): build_states(), _platform(), _plays(), _post_convention_game(), _pre_convention_game(), test_a_scoring_plays_state_does_not_contain_its_own_points(), test_ambiguous_convention_refuses_to_build(), test_halftime_scores_carried_for_2h_settlement() (+14 more)

### Community 133 - "tests/test_bovada_feed.py"
Cohesion: 0.11
Nodes (29): _american(), _complete(), _num(), parse_coupon(), _row_for(), _seen_key(), _stamp(), _coupon() (+21 more)

### Community 134 - "tests/test_market_movement.py"
Cohesion: 0.07
Nodes (26): american_to_prob(), build_market_features(), _is_full_game_snap(), _latest_two_sided(), _snap_sort_key(), _snapshot_type_rank(), _unique_ordered(), _s() (+18 more)

### Community 135 - "mobile/scripts: verify_book_links + verify_betslip_combine"
Cohesion: 0.06
Nodes (37): czr, dk3, dkHash, espn, fd, handoff, mgm, ROOT (+29 more)

### Community 136 - "tests/test_ncaaf_cross_book_opener.py"
Cohesion: 0.07
Nodes (25): _minutes_apart(), build_artifact(), build_band_artifact(), _branch(), test_absent_ceiling_means_unbounded(), test_artifact_shape(), test_band_ceiling_is_enforced_in_the_scorer(), test_band_volumes_sum_to_the_single_gate_backtest() (+17 more)

### Community 137 - "NBA injury report fixture tests"
Cohesion: 0.11
Nodes (17): _Conn, _content_of_fixture(), _Cur, _Fetcher, _PdfFetcher, _rows(), test_a_changed_report_stores_its_rows(), test_a_garbled_report_writes_its_ledger_row_and_no_rows() (+9 more)

### Community 138 - "tests/test_paused_keeps_real_verdict.py"
Cohesion: 0.05
Nodes (39): _bet(), _bodies(), _Capture, _code(), _dk(), _fn(), _game(), _pause() (+31 more)

### Community 139 - "NFL in-play edge study 2025 and devig"
Cohesion: 0.11
Nodes (33): h1_calibration(), attach_games(), attach_state(), bh(), boot(), cell(), diagnostics(), dispersion() (+25 more)

### Community 140 - "mobile/scripts/verify_contrast_tokens.ts"
Cohesion: 0.05
Nodes (40): addSrc, badgeSrc, badToneCalls, brightIcons, CASES, code(), eq, EXPECT (+32 more)

### Community 141 - "models/nhl_props.py"
Cohesion: 0.10
Nodes (25): _attach_teams(), build_frame(), build_goalie_frame(), build_skater_frame(), _ew(), excess_variance(), expected_value(), fit() (+17 more)

### Community 142 - "tests/test_health_pregame_prices_current.py"
Cohesion: 0.08
Nodes (31): _at(), _Conn, _game(), _row(), _run(), test_a_broken_feed_read_is_an_error_and_rolls_back(), test_a_broken_query_is_an_error_and_rolls_back(), test_a_cancelled_fight_and_a_pulled_game_do_not_raise_the_alarm() (+23 more)

### Community 143 - "Pick lock after settlement tests"
Cohesion: 0.08
Nodes (22): conn(), _game(), _pick(), _SqliteShim, _survivors(), test_a_bet_is_never_dropped_for_an_earlier_no_signal(), test_a_dead_zone_prop_row_locks_too(), test_a_final_game_is_not_a_scoring_target() (+14 more)

### Community 144 - "WNBA stats and results ingestors"
Cohesion: 0.07
Nodes (26): _go(), _fetch_scoreboard(), _fetch_summary(), _get_core_json(), ingest_wnba_results(), rebuild_wnba_team_stats(), _target_dates(), _upsert_games_espn() (+18 more)

### Community 145 - "NBA prop projection model"
Cohesion: 0.11
Nodes (14): asof_roster(), box_from_log(), coherent(), collapse_official(), espn_compact(), find_bets(), implied_one(), main_line() (+6 more)

### Community 146 - "tests/test_mlb_game_market.py"
Cohesion: 0.07
Nodes (27): find_spread_bets(), GameMarketBet, _is_runline(), publish_enabled(), pick_rows(), slate(), test_mlb_market_cards_drop_a_bet_under_the_floor(), _game_rows() (+19 more)

### Community 147 - "scripts/nfl_edge_extreme_props.py"
Cohesion: 0.12
Nodes (29): actuals(), add_modes(), bar(), candidates(), cell(), decision_boards(), devig(), fit_holdout() (+21 more)

### Community 148 - "scripts/nfl_edge_settlement.py"
Cohesion: 0.14
Nodes (30): add_test(), attach(), banner(), bh(), board(), boot_draws(), cell(), choose() (+22 more)

### Community 149 - "X and Discord results publishers"
Cohesion: 0.05
Nodes (33): _recap_row(), test_a_day_with_no_in_play_picks_says_nothing_about_it(), test_a_loss_costs_the_full_stake_and_a_push_costs_nothing(), test_a_pick_with_no_price_stays_in_the_units_at_bare_conviction(), test_a_six_column_row_still_tallies(), test_a_snapshot_with_no_clv_stores_null_not_zero(), test_an_in_play_pick_counts_toward_the_record(), test_clv_counts_only_picks_that_have_a_closing_price() (+25 more)

### Community 150 - "Threshold review run tests"
Cohesion: 0.12
Nodes (17): _Conn, _slate(), test_a_losing_model_with_enough_bets_is_flagged(), test_a_losing_model_with_too_few_bets_is_left_alone(), test_a_milestone_fires_only_once(), test_a_model_paused_in_config_is_not_reported_again(), test_a_profitable_model_is_never_touched(), test_an_already_paused_model_is_not_flagged_again() (+9 more)

### Community 151 - "docs/rules_evidence.md"
Cohesion: 0.07
Nodes (13): Evidence behind the standing rules (rules_evidence.md), 'Decisions needed from you' is second person, never first, A model in config.MODELS with no FEATURE_MAP entry kills scoring for every sport, Every front-end change is reviewed by the UX designer agent before its PR opens, Gate the number that gets bet (cal_error_actionable), A health check must not gate on the thing that breaks, The settled live-prop record is zero bets, The Odds API returns x-requests-remaining on every response, including 401 (+5 more)

### Community 152 - "Idle read transaction tests"
Cohesion: 0.07
Nodes (16): apply_view_migrations(), ViewMigrationResult, _flat(), _Rec, test_a_lock_timeout_fails_that_file_and_the_next_still_runs(), test_a_locked_bet_releases_the_lock_check(), test_a_quiet_tick_rolls_the_read_back(), test_a_tick_that_writes_does_not_roll_the_insert_back() (+8 more)

### Community 153 - "tests/test_agents_contract.py"
Cohesion: 0.06
Nodes (19): _labelled_retired(), test_blocked_items_are_marked_so_the_agent_skips_them(), test_every_backlog_item_is_a_checkbox(), test_neither_agent_may_change_a_model_threshold(), test_the_agents_are_findable_from_the_file_every_session_reads(), test_the_backlog_does_not_promise_an_agent_that_no_longer_runs(), test_the_backlog_exists_and_has_items(), test_the_contract_documents_every_agent_by_name() (+11 more)

### Community 154 - "Market coverage and live path tests"
Cohesion: 0.02
Nodes (49): test_a_run_that_writes_nothing_is_not_reported_as_success(), test_the_insert_rolls_back_per_row(), test_capture_compares_the_picks_own_clock_not_the_capture_clock(), test_capture_fails_open_on_a_missing_timestamp(), test_the_dry_run_count_uses_the_same_predicate_as_the_insert(), test_the_restatement_path_is_deliberately_not_guarded(), test_the_market_movement_loader_uses_the_better_bound(), test_the_nfl_prop_scorer_uses_the_better_bound() (+41 more)

### Community 155 - "tests/test_prop_box_scores.py"
Cohesion: 0.09
Nodes (18): ensure_prop_box_scores(), missing_prop_games(), GradeConn, _pick(), ScriptConn, test_a_logged_game_is_not_fetched_and_a_goalie_gap_is(), test_a_non_timeout_prop_error_rolls_back_and_raises(), test_a_probe_error_that_is_not_a_timeout_raises_after_rollback() (+10 more)

### Community 156 - "MLB totals public fade model"
Cohesion: 0.14
Nodes (17): composite_score(), estimated_edge(), PublicFadeBet, rank_score(), select_top_k(), _key(), ticket_money_gap(), take() (+9 more)

### Community 157 - "Position vs opponent tests"
Cohesion: 0.07
Nodes (19): _bn_body(), _sql_groups(), test_a_failed_position_read_is_said_not_hidden(), test_a_failed_read_is_not_held_on_the_spinner(), test_every_mlb_stat_chip_has_a_branch(), test_every_nfl_stat_chip_has_a_branch(), test_every_roster_sport_chip_has_a_branch(), test_mlb_lineup_buckets_agree_between_app_and_server() (+11 more)

### Community 158 - "Best line and best-price decision tests"
Cohesion: 0.05
Nodes (34): _best_fields(), _best_game_price(), _best_of(), _best_prop_price(), _same_line(), FakeConn, _source(), test_a_better_price_at_a_different_total_is_not_the_same_bet() (+26 more)

### Community 159 - "WNBA results ingestor parsers"
Cohesion: 0.08
Nodes (29): build_log_row(), _core_athlete(), _deref(), _et_date(), _fetch_core_box_players(), _fetch_core_games(), parse_core_event(), parse_core_stat_values() (+21 more)

### Community 160 - "NFL in-play prop flow backtests"
Cohesion: 0.03
Nodes (84): bias_table(), main(), accrual_at(), build_baselines(), build_flow_rows(), _game_context(), _season_totals(), team_context_at() (+76 more)

### Community 161 - "NBA box score enrichment"
Cohesion: 0.07
Nodes (48): _blank(), box_rows(), _check_unmapped(), _create(), dnp_kind(), ensure_tables(), fetch_advanced(), _flt() (+40 more)

### Community 163 - "tests/test_job_queue.py"
Cohesion: 0.07
Nodes (20): _job_queue(), _fake(), _Conn, test_a_busy_queue_claims_nothing(), fetchone(), test_a_failing_job_is_requeued_until_the_attempt_cap(), _boom(), test_a_final_failure_is_announced() (+12 more)

### Community 164 - "tests/test_nfl_opener.py"
Cohesion: 0.10
Nodes (10): _giants_board(), _giants_prior_at_2129(), _giants_sched(), _obs(), _row(), TestFireWindow, TestFreshNumberLabel, TestHeldMinutes (+2 more)

### Community 165 - "NHL stats and game log ingestors"
Cohesion: 0.02
Nodes (82): _default_fetch(), fetch_espn_nhl_probables(), _https(), parse_probable(), _team_abbrev(), backfill(), build_goalie_rows(), build_skater_rows() (+74 more)

### Community 166 - "Prop box score backfill"
Cohesion: 0.10
Nodes (27): call_in_savepoint(), fill_missing(), run_nfl_props_data_ingestor(), _call_fill(), _cooled(), _day(), _default_mlb(), _default_nba() (+19 more)

### Community 167 - "scripts/nfl_preflight.py"
Cohesion: 0.20
Nodes (16): check(), check_cards_run(), check_config_gates(), check_cost(), check_data(), data_check(), check_import_shadowing(), check_lock_semantics() (+8 more)

### Community 168 - "Push notifier and tickets"
Cohesion: 0.05
Nodes (43): paused_row_exclusion_sql(), Signalbase Privacy Policy, On-device storage: bankroll and placed-bet flags in AsyncStorage, Claim: the app cannot write to the backend, Signalbase privacy policy: nothing personal collected, Signal-flip push notifications, APNs key / aps-environment entitlement is the blocker, device_push_tokens table (anon INSERT/UPDATE, no SELECT) (+35 more)

### Community 169 - "Mobile sign-in and auth"
Cohesion: 0.17
Nodes (24): authSrc, failures, sendEmailCode(), signInWithProvider(), verifyEmailCode(), AUTH_ENABLED, AUTH_PROVIDERS, AUTH_REDIRECT_URL (+16 more)

### Community 170 - "Mobile billing config and verify script"
Cohesion: 0.08
Nodes (45): failures, fn, hook, iapSrc, monthly, NOW, pkgs, rcHook (+37 more)

### Community 171 - "NFL stake sizing simulation"
Cohesion: 0.21
Nodes (13): american_to_decimal(), breakeven(), kelly(), log_growth(), main(), _norm_ppf(), posterior(), _rules() (+5 more)

### Community 172 - "NFL in-play prop engine calibration"
Cohesion: 0.08
Nodes (21): evaluate(), _infer_position(), main(), _pool_prior(), report(), _rows_for_market(), _to_states(), attach_game_context() (+13 more)

### Community 173 - "tests/test_decide_on_calibrated.py"
Cohesion: 0.06
Nodes (19): _pick(), _pick_at(), test_a_calibrated_cut_is_paired_with_a_calibrated_decision(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(), test_a_genuinely_big_edge_still_fires_after_calibration(), test_a_hot_model_no_longer_fires_the_marginal_bet(), test_a_model_on_a_calibrated_cut_is_not_paused(), test_a_paused_model_never_fires_regardless() (+11 more)

### Community 174 - "tests/test_publisher_lock.py"
Cohesion: 0.07
Nodes (17): _clear_locks(), _Conn, _no_prod_threshold_sync(), _Result, _signal_row(), test_a_connection_that_cannot_lock_still_publishes(), test_an_exception_mid_publish_does_not_wedge_every_later_pass(), test_every_signal_publisher_takes_the_lock() (+9 more)

### Community 175 - "tests/test_dk_direct_feed.py"
Cohesion: 0.09
Nodes (22): _game_id_for(), _row_for(), _seen_key(), _Conn, _rec(), test_a_line_move_is_a_new_quote(), test_a_market_we_do_not_understand_is_dropped_not_guessed(), test_a_price_move_is_a_new_quote() (+14 more)

### Community 176 - "NBA prop projection lab"
Cohesion: 0.09
Nodes (48): apply_calibration(), fit_calibration_before(), fit_platt(), _logit(), bars(), bh_read(), blind(), boot() (+40 more)

### Community 177 - "tests/test_credit_budget.py"
Cohesion: 0.05
Nodes (25): parse_shard(), CreditBudget, daily_burn(), latest_remaining(), _burn_conn(), _Conn, _plan(), test_a_bad_shard_spec_is_refused() (+17 more)

### Community 178 - "NFL prop odds backfill"
Cohesion: 0.07
Nodes (19): backfill_nfl_prop_odds(), backfilled_dates(), census_books(), _credits_used(), _event_props(), _get(), _ingest_events(), list_events() (+11 more)

### Community 179 - "mobile/app.json"
Cohesion: 0.05
Nodes (38): backgroundColor, foregroundImage, adaptiveIcon, package, projectId, expo, android, extra (+30 more)

### Community 180 - "NHL market-anchored moneyline model"
Cohesion: 0.05
Nodes (31): _add_rating(), build_inputs(), choose_C(), decision_window(), fit(), _goalie_frame(), inputs_for_date(), listed_goalies() (+23 more)

### Community 181 - "tests/test_nfl_rule_2026_track.py"
Cohesion: 0.15
Nodes (15): classify(), fetch(), grade_rows(), is_void(), lead_days(), _load_nfl_model(), main(), report() (+7 more)

### Community 182 - "tests/test_model_artifacts_load.py"
Cohesion: 0.07
Nodes (19): _git(), _gitignore_keep_pkls(), _ignored(), _manifest_keep_pkls(), _newest_per_model(), test_a_path_that_is_not_ignored_is_not_reported(), test_a_superseded_timestamped_pkl_is_ignored(), test_an_ignored_path_comes_back_byte_identical() (+11 more)

### Community 183 - "docs: probability_calibration + nfl_rule_2026_track"
Cohesion: 0.10
Nodes (33): NFL 2026 live track: opener and wind, MAX_FIRE_LEAD = 4, MODEL_OWN_EV_FLOOR and MODELS_ON_OWN_PROBABILITY for wind and opener, nfl_opener_spread, nfl_wind_totals, tracking.paper_tracker (_NFL_MODEL_MARKETS), scripts/nfl_rule_2026_track, NFL wind totals lead evidence (+25 more)

### Community 184 - "mobile/package.json"
Cohesion: 0.09
Nodes (23): dependencies, expo, expo-asset, expo-dev-client, expo-font, expo-notifications, expo-status-bar, expo-updates (+15 more)

### Community 185 - "scripts/game_line_market_sweep.py"
Cohesion: 0.08
Nodes (22): _by_month(), collect_picks(), devig(), _gap_seconds(), grade(), implied(), iter_months(), load() (+14 more)

### Community 186 - "scripts/nfl_wind_publisher.py"
Cohesion: 0.09
Nodes (17): _american_to_prob(), _changed(), _clear_scored_row(), _flush_board_safe(), _flush_snapshots_safe(), latest_eval_rows(), _lock_model(), _model_lock_key() (+9 more)

### Community 187 - "Market coverage probe"
Cohesion: 0.33
Nodes (5): candidate_markets(), _standard_markets(), test_it_asks_about_the_board_columns_that_are_permanently_blank(), test_no_market_is_asked_about_twice(), test_the_probe_asks_about_every_market_we_pull_and_its_alternate()

### Community 188 - "tests/test_pass_instrumentation.py"
Cohesion: 0.06
Nodes (11): test_a_dead_database_does_not_fail_the_step(), test_a_raised_failure_still_records_the_exception(), test_a_step_that_raises_is_still_TIMED(), test_a_step_that_raises_still_raises(), boom(), test_a_step_that_returns_false_records_a_REASON(), test_a_successful_step_records_a_duration(), test_every_step_name_in_the_dispatch_table_is_reachable() (+3 more)

### Community 189 - "Settlement and self-heal tests"
Cohesion: 0.09
Nodes (25): conn(), _FakeStatsapi, _game(), _pick(), raw(), _SqliteShim, test_a_doubleheader_row_with_a_final_keeps_its_picks_grading(), test_a_final_game_is_never_voided() (+17 more)

### Community 190 - "tests/test_db_adapt_sql.py"
Cohesion: 0.09
Nodes (23): _adapt_sql(), _convert_params(), _convert_params_outside_literals(), _named(), test_a_block_comment_is_skipped_too(), test_a_colon_word_inside_a_comment_is_not_a_placeholder(), test_a_dash_dash_inside_a_literal_is_data_not_a_comment(), test_a_line_comment_ends_at_the_newline() (+15 more)

### Community 191 - "NCAAF board visibility tests"
Cohesion: 0.07
Nodes (23): _days_until(), _opener_rule(), _opening_line(), _line(), _patch(), test_a_declined_rule_can_never_leak_a_signal(), test_a_fired_pick_clears_its_own_probability_floor(), test_a_no_signal_row_does_not_lock_an_ncaaf_game_for_the_week() (+15 more)

### Community 192 - "NFL game lines model write-up"
Cohesion: 0.11
Nodes (19): NFL Game Lines Model System (canonical write-up), DataRegistry: source catalog with priority levels, scripts/edge_hunt.py: moneyline calibration clean, ML-vs-spread gap dead, Forecast validation (2026-08-15): rule holds at 57.09% under real day-3 error, Game totals model (consumes spread output as competitiveness), IngestOrchestrator: per-source fetch with no silent fallbacks, Middling does not clear vig, Moneyline derived from spread via fitted sigmoid (+11 more)

### Community 193 - "tests/test_first_signal_repair.py"
Cohesion: 0.08
Nodes (27): step_restore_first_signals(), _Conn, patch_conn(), _make(), _sql_of(), test_a_lane_already_holding_its_first_bet_is_untouched(), test_a_lane_with_no_sibling_still_restores(), test_a_lane_with_nothing_standing_is_restored() (+19 more)

### Community 194 - "tests/test_model_calibration_agent.py"
Cohesion: 0.05
Nodes (18): sweep(), _ProbeConn, _rows(), test_a_prob_only_sweep_uses_only_the_probability_dimension(), test_column_migrations_run_every_pipeline_pass(), test_home_runs_are_no_longer_exempt_from_pausing(), test_plateau_is_computed_within_the_narrow_grid(), test_the_agent_changes_nothing_on_its_own() (+10 more)

### Community 195 - "tests/test_mobile_contrast_tokens.py"
Cohesion: 0.13
Nodes (30): _code_lines(), _ionicon_colors(), _lum(), _over(), _ratio(), _read(), _rgb(), test_badge_glyph_tracks_dynamic_type() (+22 more)

### Community 196 - "tests/test_ungraded_model_performance.py"
Cohesion: 0.08
Nodes (12): FakeConn, test_perf_reads_the_matview_not_the_expensive_view(), test_roster_reports_a_registered_but_untrained_model(), _second_arm(), _sql(), test_a_fully_unpriced_recovered_model_reports_no_roi(), test_a_recovered_row_still_reports_roi_over_the_priced_bets(), test_both_arms_stay_inside_the_settled_bet_gate() (+4 more)

### Community 197 - "NBA stats ingestor"
Cohesion: 0.09
Nodes (23): fill_missing_game_logs(), backfill_nba_stats(), _build_game_id(), _build_game_rows(), _build_player_log_rows(), _build_team_stat_rows(), _fetch_league_game_log(), ingest_nba_game_log_for_date() (+15 more)

### Community 198 - "Historical odds backfill tests"
Cohesion: 0.05
Nodes (22): _ledger_entry_is_resumable(), relabel_in_play(), test_the_in_play_relabel_uses_the_better_bound(), test_a_rerun_can_be_told_to_ignore_the_pull_ledger(), test_a_snapshot_after_first_pitch_is_marked_in_play(), test_a_snapshot_exactly_at_first_pitch_stays_pregame(), test_backfill_rows_are_stamped_with_the_historical_source(), test_ignore_ledger_still_resumes_its_own_pulls() (+14 more)

### Community 199 - "Prop price pregame cutoff tests"
Cohesion: 0.08
Nodes (14): _latest_dk_prop_row(), _assigned_from(), _prop_scorers(), _StubConn, test_every_scorer_call_site_passes_a_pregame_cutoff(), test_get_prop_dk_odds_forwards_the_cutoff(), test_in_play_snapshots_are_excluded_unconditionally(), test_it_fails_open_when_commence_time_is_missing() (+6 more)

### Community 200 - "NFL prop odds loading tests"
Cohesion: 0.06
Nodes (22): _fetch_slice(), _iter_prop_rows(), load_nfl_prop_odds(), load_nfl_prop_quotes(), _prop_slice_query(), statement_timeout_error(), _Conn, _Cur (+14 more)

### Community 201 - "Mobile bankroll card"
Cohesion: 0.20
Nodes (19): fieldFlow(), inv(), bankrollDraft(), bankrollFieldText(), canonical(), checkBankroll(), commitBankrollText(), editBankrollInput() (+11 more)

### Community 202 - "Games and latest odds views"
Cohesion: 0.05
Nodes (41): public.v_latest_inplay_odds_all_books, public.v_latest_prop_odds_all_books, public.v_latest_prop_odds_all_books, public.latest_lines_rebuild_odds(), public.latest_odds_recompute(), public.latest_prop_odds_recompute(), public.v_latest_odds_all_books, public.v_latest_prop_odds_all_books (+33 more)

### Community 203 - "tests/test_nhl_asof.py"
Cohesion: 0.19
Nodes (3): GoalieBook, _g(), TestGoalieAsOf

### Community 204 - "NFL prop feature engine and grading"
Cohesion: 0.05
Nodes (46): name_key(), NFL props 2025 re-grade and walk-forward, anytime_td verdict: inert, not losing, Walk-forward re-fit 2023-2025 (-4.32% over 1,554 bets), _add_features(), build_nfl_prop_scoring_rows(), build_nfl_prop_training_dataset(), _cols() (+38 more)

### Community 205 - "Prop devig and market-relative pricing"
Cohesion: 0.04
Nodes (48): MLB prop market-relative rule (not wired), mlb_total_market paper totals logger, _parse_iso_ts(), devig(), find_bets(), implied(), MarketBet, find_total_bets() (+40 more)

### Community 206 - "tests/test_live_inning_gate_replay.py"
Cohesion: 0.12
Nodes (28): _grade(), _pair(), _refuse_tables(), _score_seen_at(), _game(), _price(), _scored(), _sig() (+20 more)

### Community 207 - "scripts/ncaaf_search: dataset + starter_out"
Cohesion: 0.16
Nodes (8): build_label_set(), _fetch_lines(), _fetch_raw(), LabelSet, opener_coverage(), _pick_provider(), provider_continuity(), main()

### Community 208 - "tests: test_deploy_checks + deploy_checks"
Cohesion: 0.07
Nodes (16): _Conn, test_a_declared_job_carries_its_run_after(), test_a_failing_check_raises_so_the_queue_announces_it(), test_a_job_can_only_name_a_registered_check(), test_enqueue_rejects_a_naive_run_after(), test_enqueue_stores_run_after(), test_every_check_is_read_only(), test_the_claim_waits_for_run_after() (+8 more)

### Community 209 - "data/ingestors/nfl_inplay_history.py"
Cohesion: 0.16
Nodes (22): Budget, buy_halftime(), buy_inplay(), events_for(), _floor5(), _get(), halftime_requests(), halftime_windows() (+14 more)

### Community 210 - "NFL luck gap study"
Cohesion: 0.10
Nodes (30): add_windows(), add_windows_fast(), bh(), binom_p(), board(), boot(), cell(), fit_points() (+22 more)

### Community 211 - "Mobile bankroll store and verify script"
Cohesion: 0.09
Nodes (31): DE, EN, explainer, files, lib, picks, settings, SRC (+23 more)

### Community 212 - "Probability calibration fit"
Cohesion: 0.03
Nodes (61): apply_calibration(), demote(), ensure_schema(), _era_start(), fetch_graded(), fit_model(), fit_offset(), fit_platt() (+53 more)

### Community 213 - "nfl/live_model/README.md"
Cohesion: 0.10
Nodes (18): NFL live (in-play) model README, backtest/calibrate.py (the two gates), backtest/calibrate_props.py projection prop gate, check_feed_assumptions: automatic first-payload feed check, backtest/flow_eval.py flow test with control, Gate 1: win probability Brier 0.1654 PASS vs 0.20, Gate 2: total quantile coverage 1.26pp PASS vs 2.0pp, backtest/harness.py kill_verdict (+10 more)

### Community 214 - "NHL props per-game limit tests"
Cohesion: 0.16
Nodes (4): limit_per_game(), publish(), TestInsertOnce, TestTheLimitPerGame

### Community 215 - "Live count tail probability tests"
Cohesion: 0.07
Nodes (21): _nb1_over_prob(), _ew(), fit_score(), main(), opponent_allowed(), coherent(), fold(), load_prices() (+13 more)

### Community 216 - "Free pick cheaper book tests"
Cohesion: 0.08
Nodes (19): _pick(), test_a_pick_with_no_alternative_falls_back_to_draftkings(), test_every_offerable_book_has_a_human_name_on_both_surfaces(), test_the_free_card_names_the_cheaper_book(), test_the_free_card_query_reads_the_columns_it_renders(), test_the_good_to_clause_is_dropped_not_truncated_when_it_will_not_fit(), test_the_tweet_names_the_cheaper_book(), test_the_tweet_never_publishes_a_worse_price_than_draftkings() (+11 more)

### Community 217 - "NCAAF live engine pricing"
Cohesion: 0.06
Nodes (19): write_picks(), _is_paused(), LiveEngine, db(), FakeConn, _Rows, test_both_lanes_locked_touches_nothing(), test_dry_run_never_touches_db() (+11 more)

### Community 218 - "Closing line value math"
Cohesion: 0.04
Nodes (38): _identity_maps(), _platform_gates_off(), test_breakeven_is_the_real_vig_hurdle(), test_a_one_way_close_is_not_de_vigged(), test_a_worse_close_is_negative_and_equal_prices_are_zero(), test_devigging_the_taken_price_is_not_what_primary_does(), test_kalshi_close_is_not_de_vigged(), test_market_edge_devigs_only_the_close() (+30 more)

### Community 219 - "tests/test_nfl_live_leader_state.py"
Cohesion: 0.12
Nodes (20): abbrev(), situation(), status(), test_a_conversion_try_is_skipped(), test_a_previous_quarters_play_is_not_the_state(), test_a_timeout_is_skipped_for_the_play_before_it(), test_after_a_scoring_play_nothing_is_evaluated(), test_after_the_kickoff_lands_the_receiver_has_the_ball() (+12 more)

### Community 220 - "tests/test_db_reconnect.py"
Cohesion: 0.09
Nodes (16): _is_write(), _Conn, _Cursor, _lost(), test_a_committed_transaction_is_clean_again(), test_a_lost_connection_with_uncommitted_writes_raises_connection_lost(), test_a_read_on_a_lost_connection_reconnects_and_retries(), test_a_statement_timeout_is_not_a_lost_connection() (+8 more)

### Community 221 - "tests/test_ncaaf_qb_ingestor.py"
Cohesion: 0.11
Nodes (24): _athlete_stats(), _comp_att(), parse_qb_game_stats(), _split_ratio(), test_split_ratio(), _parse(), _payload(), _team() (+16 more)

### Community 222 - "NFL live prop tests and pass-attempt bias"
Cohesion: 0.09
Nodes (11): blind_over_prob(), over_prob(), _pass_attempt_bias_allowed(), Read, test_blind_arm_no_longer_asserts_a_rate(), test_restoring_a_bias_is_one_constant(), test_the_gates_are_checked_before_the_no_bias_decline(), test_the_interval_spans_zero_so_the_lane_declines_to_price() (+3 more)

### Community 223 - "tests/test_live_lock.py"
Cohesion: 0.13
Nodes (18): _write_live_picks(), _locked_live_lanes(), FakeConn, _log_lines(), _pick(), _Rows, test_a_locked_lane_still_says_so_and_names_the_lane(), test_all_lanes_locked_touches_nothing() (+10 more)

### Community 224 - "NBA derivative market lab"
Cohesion: 0.09
Nodes (35): add_team(), am_to_dec(), bars_for(), bet_list(), blind(), boot_ci(), build_line_rows(), build_outcomes() (+27 more)

### Community 225 - "tests/test_refresh_retry.py"
Cohesion: 0.14
Nodes (23): _decide(), _done(), _run(), test_a_failed_view_migration_fails_the_step(), test_a_pass_that_finished_with_failed_steps_ran_its_chain(), test_a_redeploy_between_passes_replaces_nothing(), test_a_restart_loop_does_not_buy_odds_on_every_boot(), test_a_row_the_next_start_run_already_closed_as_aborted_is_the_same_orphan() (+15 more)

### Community 226 - "NBA box score player name resolver"
Cohesion: 0.08
Nodes (8): build_dnp_rows(), build_log_rows(), fallback_id(), PgStore, PlayerResolver, test_a_rookie_keeps_one_id_across_games(), test_the_fallback_cannot_collide_with_an_nba_id(), test_two_box_rows_never_share_an_id()

### Community 227 - "docs: followups + clv"
Cohesion: 0.08
Nodes (26): Pruner keeps the opener AND the close per (proposition, book), Closing line value (CLV), clv_method = standard_v2 (PEDIGREE_CLV_METHODS), clv_standard_v2_2026_10_14.sql bulk rewrite, Secondary — market edge vs Pinnacle's fair close (market_clv_*), Power de-vig (bisection, 80 steps, k in [0.05, 12]), Primary CLV — same-book raw price (clv_pct, clv_pp, clv_beat_close), Same line, and the close bound (+18 more)

### Community 228 - "NBA results ingestor tests"
Cohesion: 0.09
Nodes (24): _Conn, _ESPN, FakeStore, _FixedNow, _game(), _resolver(), _run(), test_a_different_stored_score_is_never_overwritten() (+16 more)

### Community 229 - "NBA prop model verification script"
Cohesion: 0.13
Nodes (28): adv_from_log(), asof_roster(), blind_structured(), card_block(), collapse_report(), _compare(), log(), main() (+20 more)

### Community 230 - "tests/test_local_cache_is_additive.py"
Cohesion: 0.10
Nodes (13): main(), _merge_with_cache(), _pull_odds(), _pull_seasoned(), _register_from_feature_engine(), cached(), _FakeConn, _frame() (+5 more)

### Community 231 - "tests/test_calibration_check_coverage.py"
Cohesion: 0.11
Nodes (18): _bet(), _calibration_results(), db(), _graded(), _make_db(), _only(), _promote(), _register() (+10 more)

### Community 232 - "Record correction posting script"
Cohesion: 0.10
Nodes (21): delete_custom_record_post(), _jump(), LedgerUnread, _place(), _publish(), publish_full_record(), publish_full_record_standard(), publish_oct13_line() (+13 more)

### Community 233 - "tests/test_book_team_map.py"
Cohesion: 0.11
Nodes (15): abbr_from_team_string(), resolve_game_id(), split_matchup(), _Conn, test_a_non_mlb_sport_is_refused_rather_than_guessed(), test_a_string_with_no_at_sign_is_refused(), test_a_unique_game_resolves(), test_an_ambiguous_game_resolves_to_none() (+7 more)

### Community 234 - "tests/test_team_board_cache.py"
Cohesion: 0.08
Nodes (11): refresh_team_board_cache(), team_board_pairs(), team_board_seasons(), _cols(), _Conn, _Cursor, test_every_team_sport_gets_last_this_and_next_year(), test_one_failing_pair_does_not_stop_the_rest() (+3 more)

### Community 235 - "NCAAF feature engine tests"
Cohesion: 0.15
Nodes (16): _assemble(), _stats(), test_a_push_yields_no_target(), test_assembly_diffs_and_context(), test_bulk_loads_both_markets_of_the_historical_line(), test_early_season_is_flagged_not_gated(), test_fbs_gate_rejects_an_explicitly_fcs_classification(), test_fbs_gate_rejects_an_fcs_team_that_has_a_snapshot_row() (+8 more)

### Community 236 - "mobile/src/lib: verify_discord_link + discordHelpers"
Cohesion: 0.11
Nodes (34): discordShared, failures, fnRoot, libSrc, linkFn, shared, whopFn, accessEnabled() (+26 more)

### Community 237 - "Discord price bound tests"
Cohesion: 0.11
Nodes (13): _dec(), test_a_field_without_a_bound_renders_without_the_clause(), test_a_model_with_no_own_ev_floor_is_bound_by_the_global_one(), test_a_price_floor_can_be_the_binding_gate(), test_a_rounded_bound_still_clears_the_bound_it_came_from(), test_even_money_is_plus_one_hundred(), test_no_bound_from_junk_rather_than_a_guess(), test_no_bound_when_the_edge_floor_is_unreachable() (+5 more)

### Community 238 - "nfl/live_model/tests/test_rush_attempt_pace.py"
Cohesion: 0.07
Nodes (21): pace_ratio(), Read, _sigmoid(), under_prob(), _price(), test_a_line_he_has_already_passed_is_not_a_live_proposition(), test_a_missing_accrued_count_is_refused_not_treated_as_zero(), test_a_reachable_over_is_declined_rather_than_faded() (+13 more)

### Community 239 - "tests/test_nfl_poll_fast_silence.py"
Cohesion: 0.11
Nodes (16): _num(), publish_board(), _append_board(), _body(), FakeConn, _row(), _sent(), _setup() (+8 more)

### Community 240 - "tests/test_ncaaf_game_identity.py"
Cohesion: 0.12
Nodes (16): _add(), _conn(), _identity_sql(), _run(), test_a_clean_slate_reports_nothing(), test_a_non_fbs_fixture_is_not_reported(), test_a_phantom_opponent_is_detected_too(), test_a_real_doubleheader_is_not_a_duplicate() (+8 more)

### Community 241 - "Batter prop feature rows"
Cohesion: 0.13
Nodes (10): _all_batter_rows(), _batter_rate(), _batter_rolling_avg(), _batter_savant(), _batter_season_avg(), _build_batter_row(), _opp_pitching(), _opp_team_sb_allowed() (+2 more)

### Community 242 - "Results recap message tests"
Cohesion: 0.07
Nodes (16): test_a_restate_with_nothing_settled_late_is_a_no_op(), _Conn, test_a_204_with_no_id_is_not_a_finished_recap(), test_a_posted_recap_ledgers_the_id_wait_returned(), test_a_rejected_post_is_recorded_and_the_next_pass_sends(), test_a_restate_that_raises_is_recorded(), test_a_restatement_stores_its_own_id(), all_time_fields() (+8 more)

### Community 243 - "MLB stats ingestor"
Cohesion: 0.07
Nodes (25): backfill_bullpen_stats(), backfill_f5_scores(), backfill_mlb_stats(), backfill_pitcher_stats(), backfill_player_game_log(), backfill_player_handedness(), _build_pitcher_rows(), _build_team_stats_rows() (+17 more)

### Community 244 - "tests/test_weather_lookahead.py"
Cohesion: 0.09
Nodes (11): _celsius_to_f(), _fetch_open_meteo(), _game_hour_utc(), _target_hour_utc(), _utc_offset_from_lon(), captured(), fake_get(), _hours() (+3 more)

### Community 245 - "tests/test_nhl_asof.py"
Cohesion: 0.13
Nodes (4): TeamBook, _r(), TestBlendedTeamInputs, TestTeamRatesAsOf

### Community 246 - "docs: best_line + config_topology"
Cohesion: 0.10
Nodes (21): Best line on pre-game picks, Book roles: fetched (LINE_SHOP_BOOKMAKERS) vs offered (BEST_LINE_BOOKMAKERS), DECIDE_ON_BEST_PRICE=0 restores DraftKings as the deciding price, Stage 2: decide, size and settle at the best price (picks.decision_*), _get_event_odds fetched DraftKings-only (MLB F5, UFC round totals), The live models join best-price deciding (2026-09-10), PREGAME_PRICE_MAX_AGE_MIN (180 min) on game-market reads, Scoring off another book's line (picks.line_book) (+13 more)

### Community 247 - "tests/test_dk_freshness_parse.py"
Cohesion: 0.12
Nodes (17): _american(), parse_dk_payload(), _store(), _FakeConn, _FakeResult, _payload(), test_a_half_priced_market_is_dropped_rather_than_half_recorded(), test_an_event_with_no_markets_yields_nothing_rather_than_raising() (+9 more)

### Community 248 - "tests/test_live_calibrated_decision.py"
Cohesion: 0.09
Nodes (15): _cut(), RecordingConn, _signal(), test_a_big_enough_claim_still_fires_after_calibration(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(), test_a_hot_live_model_no_longer_fires_the_marginal_bet(), test_a_live_model_is_read_out_of_picks_not_the_matview(), test_a_live_read_bounds_on_a_real_price() (+7 more)

### Community 249 - "models: slate_concentration + test_slate_concentration"
Cohesion: 0.15
Nodes (15): apply_slate_guard(), apply_slate_concentration_guard(), _attr(), _edge_of(), _is_bet(), measure_side_concentration(), _side_of(), SlateConcentration (+7 more)

### Community 250 - "data/ingestors/nhl_boxscore.py"
Cohesion: 0.12
Nodes (16): _decision(), fill_missing(), _insert_absent(), _int(), _name(), parse_boxscore(), side_rows(), store_boxscore() (+8 more)

### Community 251 - "View migration lock handling tests"
Cohesion: 0.09
Nodes (23): execute(), _before(), _code(), _Conn, _Deadlock, _LockTimeout, _sql(), _StatementTimeout (+15 more)

### Community 252 - "docs/cloud_worker.md"
Cohesion: 0.09
Nodes (27): catch_up_daily_pipeline / tracking/daily_retry.py, test_every_model_artifact_on_disk_is_tracked_by_git, Cloud worker — the pipeline on Railway, DISCORD_WEBHOOK_* variables, one channel per sport, Heartbeat watchdog -> DISCORD_WEBHOOK_OPS, LIVE_DAILY_CREDIT_CAP and RUN_LIVE_LOOP, In-play live loop under a */10 supervisor, Live monitor dashboard (monitoring/, MONITOR_TOKEN) (+19 more)

### Community 253 - "docs/history: learnings + build_state"
Cohesion: 0.09
Nodes (25): Build state, data sources, model registry, spec (2026-08 snapshot), Data sources table (Odds API, SBR, MLB Stats API, Savant, Open-Meteo, NHL API, nba_api, ESPN, UFC CSV mirror, DataGolf), FanGraphs / pybaseball removed (IP-blocked); replaced by MLB Stats API + Savant, MLB_Basic.csv datawarehouse (2009-2025, 40,996 games; runline derived as -1.5), What's built (package tree) and what's not, Learnings and rejected approaches (learnings.md), AlphaPy rejected (deprecated, team-level only, defunct connectors), Team stats need at least 10 games before they stabilize (+17 more)

### Community 254 - "Prop odds missing game tests"
Cohesion: 0.04
Nodes (13): test_the_prop_fetch_never_buys_a_game_it_was_not_given(), execute(), FakeConn, _R, _run(), test_event_with_no_games_row_is_skipped_and_others_still_insert(), test_fk_on_insert_does_not_unwrite_the_events_that_already_landed(), test_is_missing_game_fk_matches_the_production_error() (+5 more)

### Community 255 - "scripts/mlb_total_public_fade_topk.py"
Cohesion: 0.11
Nodes (18): ticket_bucket(), american_units(), bucket_win_rates(), build_candidates(), _fmt(), grade_under(), holdout_take(), load_db() (+10 more)

### Community 256 - "tests/test_ncaaf_search_features.py"
Cohesion: 0.09
Nodes (19): AdjRatings, blended_rating(), build_adjusted_ratings(), build_prior_season_ratings(), features_for(), fit_opponent_adjustment(), rolling_variants(), _synth() (+11 more)

### Community 257 - "NCAAF search model runner"
Cohesion: 0.13
Nodes (16): _apply_calibration(), exponential_recency_weights(), _logit(), make_ensemble(), fit_predict(), make_lgbm(), fit_predict(), make_logreg() (+8 more)

### Community 258 - "NFL wind forecast and totals"
Cohesion: 0.03
Nodes (64): bettable_books(), coverage_check(), expected_true_wind(), fetch_era5(), fetch_issued_forecasts(), fetch_live_forecast(), _frame(), _get() (+56 more)

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

### Community 263 - "NFL model import tests"
Cohesion: 0.15
Nodes (6): _import_under_scheduler_env(), _scheduler_env(), test_no_nfl_script_uses_the_bare_models_import(), test_the_card_imports_under_the_schedulers_invocation(), test_the_exemption_is_the_loader_and_it_still_exists(), test_the_loader_reaches_nfls_models_not_the_platforms()

### Community 264 - "monitoring/static/dashboard.html"
Cohesion: 0.16
Nodes (26): Signalbase pipeline monitor dashboard page, dashboard.html ageNote(), dashboard.html callRow(), dashboard.html connect(), dashboard.html drawSeries(), dashboard.html drawTimeline(), dashboard.html flush(), dashboard.html ingestCalls() (+18 more)

### Community 265 - "tests/test_best_line_sweep.py"
Cohesion: 0.10
Nodes (12): american_to_decimal(), units_at(), _Conn, _row(), test_a_better_price_pays_more_than_the_dk_price(), test_a_loss_costs_one_unit_at_every_price(), test_a_push_is_flat(), test_a_retired_model_is_never_recommended_a_cut() (+4 more)

### Community 266 - "NCAAF in-play history backtest"
Cohesion: 0.11
Nodes (16): build_candidates(), decide(), first_signals(), _fmt(), load_snapshots(), main(), odds_from_rows(), report() (+8 more)

### Community 267 - "tests/test_ncaaf_qb_features.py"
Cohesion: 0.14
Nodes (23): build_qb_team_features(), merge_qb_features(), _feat(), _frame(), _games(), _qb_rows(), _qb_team(), test_a_games_features_never_use_that_game() (+15 more)

### Community 268 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.11
Nodes (6): build_scored_rows(), _fmt_spread(), TestBuildScoredRows, TestPickEmLabel, TestPreflightLockChecks, TestQualifyingRowIsNotANoneRow

### Community 269 - "tests/test_cfbd_ingestor.py"
Cohesion: 0.06
Nodes (11): ingest_ncaaf_teams(), _GamesConn, _TeamsConn, test_ingest_games_retains_a_historical_utc_id_and_uses_et_for_a_new_row(), fake_get(), test_ingest_pulls_fbs_then_everyone_and_fbs_rows_win(), test_ingest_retries_everyone_without_a_year_if_the_season_filter_is_empty(), test_prior_context_tolerates_missing_talent_and_returning() (+3 more)

### Community 270 - "NCAAF in-play history tests"
Cohesion: 0.10
Nodes (15): grade(), _cand(), _Conn, _event(), _no_db_school_lookup(), _StubEngine, test_a_late_kickoff_falls_back_to_its_utc_dated_games_row(), test_a_market_filter_writes_only_that_market() (+7 more)

### Community 271 - "tests/test_line_clv.py"
Cohesion: 0.07
Nodes (7): _load(), test_a_line_that_held_is_exactly_zero_not_none(), test_a_missing_close_is_not_a_zero(), test_a_side_that_cannot_be_oriented_returns_none_rather_than_guessing(), test_the_home_and_away_sides_are_exact_mirrors(), test_the_prop_market_flag_wins_over_the_market_string(), test_the_signs_are_the_negation_of_the_apps_entry_frame()

### Community 272 - "Discord publish sync tests"
Cohesion: 0.07
Nodes (18): _sql_key(), test_a_game_level_key_has_no_tail(), test_a_published_void_keeps_track_and_betslip(), test_a_tracked_void_reads_not_graded_and_detail_closes_when_over(), test_an_opening_signal_is_live_only_when_discord_published_it(), test_discord_led_visibility(), test_opening_lock_join_is_not_wired_into_readers_yet(), test_the_app_predicate_matches() (+10 more)

### Community 273 - "tests/test_prop_odds_utc_stamp.py"
Cohesion: 0.12
Nodes (13): _assert_utc_stamp(), _Conn, _frozen(), _run_mlb(), capture(), events(), _run_ncaaf(), test_an_eastern_row_then_a_later_utc_row_sorts_in_time_order() (+5 more)

### Community 274 - "Monitoring HTTP stream handler"
Cohesion: 0.14
Nodes (8): main(), build_server(), _connect(), dumps(), Handler, _json_default(), test_loopback_without_a_token_is_allowed(), test_refuses_a_public_bind_without_a_token()

### Community 275 - "NFL lookahead signal tests"
Cohesion: 0.08
Nodes (14): _Conn, _sql_for(), test_a_started_game_is_still_never_published(), test_both_publishers_apply_the_apps_action_filter(), test_both_publishers_read_the_table_the_app_reads(), test_capture_reaches_as_far_as_the_poller_can_write(), test_capture_reaches_forward_for_the_locked_lookahead_sports(), test_ncaaf_lookahead_is_only_safe_because_the_lock_is_general() (+6 more)

### Community 276 - "NBA ESPN box score parser"
Cohesion: 0.06
Nodes (32): box_team_totals(), et_date(), nba_team(), _no_minutes(), parse_nba_box(), parse_nba_dnp(), parse_nba_scoreboard(), _played() (+24 more)

### Community 277 - "NBA injury report runner"
Cohesion: 0.17
Nodes (10): ensure_tables(), Fetcher, load_players(), load_schedule(), main(), pulled_urls(), remap_players(), retry_failed() (+2 more)

### Community 278 - "tests/test_feature_artifact_agreement.py"
Cohesion: 0.11
Nodes (13): Activating the opposing-starter features (MLB batter props), _KNOWN_DRIFT: mlb_prop_pitcher_hits and mlb_prop_batter_sb, Matched baseline with --no-register, Opposing-starter Savant features (opp_starter_k_pct, whiff_pct, xera, bb_pct), SPARSE_OK_FEATURES — a null does not dropna the row, _load(), _newest_artifact(), _Stub (+5 more)

### Community 279 - "NBA injury report pulls"
Cohesion: 0.17
Nodes (9): content_hash(), garbled_note(), previous_report(), pull_one(), slot_time(), tips_by_date(), write_report(), test_a_report_whose_cells_do_not_line_up_with_its_header_is_not_stored() (+1 more)

### Community 280 - "Mobile pick queries and hooks"
Cohesion: 0.02
Nodes (140): bad, bare, blank, pgrst, rendered, shapes, timeout, cache (+132 more)

### Community 281 - "tests/test_cloud_retrain_artifacts.py"
Cohesion: 0.10
Nodes (12): _restore_artifact(), _Conn, test_a_failed_upload_does_not_lose_a_model_that_trained(), test_a_missing_artifact_table_is_not_an_error_on_restore(), test_a_no_register_run_stores_nothing(), test_load_model_actually_loads_from_the_store_when_the_file_is_gone(), fetchone(), test_load_model_returns_none_when_the_store_has_nothing_either() (+4 more)

### Community 282 - "NFL in-play prop flow slices"
Cohesion: 0.13
Nodes (16): _clustered_ci(), _qcut(), _rows_for(), slice_table(), verdict(), _frame(), _table(), test_a_bias_living_in_one_quarter_reads_as_concentrated() (+8 more)

### Community 283 - "NCAAF play-by-play state builder"
Cohesion: 0.17
Nodes (10): main(), _classify(), classify_report(), _detect_score_convention(), load_platform_games(), pace_report(), _repair_day_offsets(), sample_states() (+2 more)

### Community 284 - "NCAAF FBS registry tests"
Cohesion: 0.12
Nodes (9): _alarm_part(), _live_db(), _promoted(), _registry_check(), _snapshot(), _team(), TestRefusalLog, TestRegistryHealthCheck (+1 more)

### Community 285 - "Health skip budget tests"
Cohesion: 0.07
Nodes (18): FakeConn, _res(), _source_outside_the_budget_table(), test_a_check_never_seen_non_skipped_counts_its_whole_history(), test_a_check_skipped_only_today_is_not_counted_as_a_streak(), test_a_non_skipped_result_is_never_touched(), test_a_stuck_gate_escalates_past_its_budget(), test_an_honest_offseason_skip_stays_skipped_but_shows_its_length() (+10 more)

### Community 286 - "Kalshi ladder recording and prop ingestor tests"
Cohesion: 0.08
Nodes (6): test_a_kalshi_outage_cannot_break_the_pass(), test_a_run_is_idempotent_within_its_snapshot(), test_one_snapshot_timestamp_for_the_whole_run(), test_the_recorder_is_scheduled_on_the_pipeline_role(), test_the_recorder_keeps_raw_prices_not_a_filtered_ladder(), test_the_recorder_walks_every_mapped_series()

### Community 287 - "tests/test_model_calibration_check.py"
Cohesion: 0.09
Nodes (12): _calibration_sql(), test_a_flagged_model_is_named_eligible_or_not(), test_a_thin_model_is_still_excluded_rather_than_accused(), test_eligibility_notes_must_not_sink_the_gap_check(), test_eligibility_notes_parse_the_payload_verdicts(), test_it_grades_the_calibrated_probability_not_the_raw_one(), test_it_joins_picks_to_reach_the_calibrated_column(), test_the_check_has_a_skip_budget_that_survives_a_regime_change() (+4 more)

### Community 288 - "tests/test_nfl_opener.py"
Cohesion: 0.20
Nodes (5): _both_sides(), _frame(), _sched(), TestBettableBooksOnly, TestSelectOpenerBets

### Community 289 - "tests/test_ncaaf_player_stats_ingestor.py"
Cohesion: 0.18
Nodes (17): parse_player_game_stats(), _cat(), _parse(), _payload(), _team(), test_a_game_missing_from_the_id_map_is_skipped_not_guessed(), test_a_player_gets_one_row_across_every_category(), test_a_player_with_nothing_we_track_is_skipped() (+9 more)

### Community 290 - "NBA play-by-play ingestor tests"
Cohesion: 0.10
Nodes (20): _last(), match_games(), match_names(), roster_from_plays(), _g(), _rec(), test_a_nickname_matches_on_initial_and_last_name_then_by_elimination(), test_a_one_day_shift_matches_only_an_unclaimed_game() (+12 more)

### Community 291 - "tests/test_team_stats_asof_invariants.py"
Cohesion: 0.13
Nodes (6): _SeasonConn, test_verify_established_live_season_with_two_snapshots_stays_thin(), test_verify_five_day_span_with_one_snapshot_is_thin(), test_verify_four_day_opening_span_is_still_grace(), test_verify_opening_live_season_is_not_thin(), test_verify_short_historical_season_is_still_thin()

### Community 292 - "docs/sports/nhl.md"
Cohesion: 0.12
Nodes (22): NHL models code-complete, not yet trained (2026-06-13 snapshot), NHL — pipeline operations (nhl.md), docs/nhl_clv_ev_assessment.md: the current CLV/EV grade of every NHL model, Per-game logs from the NHL stats API (team, goalie, skater) via data/ingestors/nhl_game_logs.py, Starting-goalie confirm via ESPN core probableStartingGoalie; game-model veto on Out/Doubtful, docs/nhl_market_research.md: six defects and the honest walk-forward, data/nhl_asof.py: one function rates goalies and teams as-of, strictly before the date, nhl_over_under is live as a rule: Pinnacle de-vigged vs the bettable books in the same fetch (+14 more)

### Community 293 - "NHL props card tests"
Cohesion: 0.17
Nodes (5): pick_rows(), _mus(), _quotes(), TestTheBacktestGradesTheRuleTheCardPlays, TestTheCard

### Community 294 - "Dashboard app and SQL runner"
Cohesion: 0.13
Nodes (5): _fmt_et_time(), get_conn(), query(), main(), _strip_outer_tx()

### Community 295 - "Unit stake sizing and formatting"
Cohesion: 0.06
Nodes (24): test_conviction_floors_at_one_not_a_half(), test_conviction_is_flat_for_every_kelly(), test_conviction_is_flat_regardless_of_kelly(), test_favourites_risk_more_until_the_cap_binds(), test_flat_conviction_is_still_price_adjusted(), test_risk_and_win_always_agree_with_the_price(), test_risk_is_capped_at_three_units_and_the_payout_is_recomputed(), test_the_minus_110_example_matt_gave() (+16 more)

### Community 296 - "scripts/nfl_edge_kalshi.py"
Cohesion: 0.17
Nodes (20): align_check(), bh(), bins(), boot(), cell(), coverage(), cp_roi(), fee() (+12 more)

### Community 297 - "scripts/nfl_live_prop_feasibility.py"
Cohesion: 0.22
Nodes (18): american_b(), bettable(), boot_roi(), brier(), design(), fit_market(), grade(), implied() (+10 more)

### Community 298 - "tests/test_nfl_wind_publisher.py"
Cohesion: 0.13
Nodes (10): build_rows(), _fmt_line(), kick_fields(), parse_matchup(), test_nfl_wind_and_opener_rows_drop_a_bet_under_the_floor(), test_the_min_chi_wind_row_is_written_as_a_bet(), _card_row(), TestBuildRows (+2 more)

### Community 299 - "tests/test_context_budget.py"
Cohesion: 0.12
Nodes (14): _expand_braces(), _hook_context(), _read(), _rule_files(), _size(), test_claude_md_stays_small_enough_to_load_every_session(), test_every_doc_referenced_by_the_index_exists(), test_every_rules_file_is_pointed_at_from_claude_md() (+6 more)

### Community 300 - "tests/test_health_reason_and_cadence.py"
Cohesion: 0.09
Nodes (20): _one(), Report, test_a_24h_ts_check_reads_as_daily(), test_a_bare_add_still_fills_both_columns(), test_a_broken_query_is_its_own_reason(), test_a_late_check_says_how_late(), test_a_passing_check_says_fresh(), test_a_skipped_check_says_the_gate_was_shut() (+12 more)

### Community 301 - "tests/test_live_publish_parity.py"
Cohesion: 0.17
Nodes (12): _Conn, _db(), _labels(), _pick(), test_a_bet_written_while_paused_is_not_announced_after_an_unpause(), test_a_live_health_state_still_publishes(), test_a_paused_model_is_not_announced(), test_a_retired_model_is_not_announced() (+4 more)

### Community 302 - "tests/test_nfl_weather_supabase_readback.py"
Cohesion: 0.13
Nodes (13): FakeConn, _patch_conn(), _rows(), test_a_null_requested_lead_is_not_returned(), test_a_one_lead_response_is_not_stored(), test_a_partial_window_is_not_returned(), test_a_store_failure_is_a_warning_not_an_error(), test_a_subset_of_leads_reads_only_those_columns() (+5 more)

### Community 303 - "tests/test_player_h2h_stat_values_migration.py"
Cohesion: 0.10
Nodes (13): _body(), test_each_function_reads_its_own_log_table(), test_it_does_its_ddl_once_and_guards_on_the_property_it_establishes(), test_it_is_one_statement_so_conn_execute_cannot_shred_it(), test_public_is_revoked_before_anon_is_granted(), test_security_invoker_like_the_season_rpcs_it_mirrors(), test_the_fixture_is_two_parallel_arrays_not_a_separator(), test_the_players_latest_team_decides_his_fixture() (+5 more)

### Community 304 - "Player game log RPCs"
Cohesion: 0.08
Nodes (25): public.v_model_full_outcome_picks, public.player_recent_games_mlb(), public.player_recent_games_nba(), public.player_recent_games_wnba(), public.player_season_stat_values_mlb(), public.player_season_stat_values_nba(), public.player_season_stat_values_wnba(), public.v_model_full_outcome_record (+17 more)

### Community 305 - "tests/test_retired_models.py"
Cohesion: 0.06
Nodes (13): test_a_retired_game_model_is_in_no_feature_map(), test_a_retired_model_is_in_no_registry_and_no_threshold_dict(), test_a_retired_prop_has_no_feature_map_and_no_training_label(), test_a_retired_sport_is_not_still_health_checked(), test_paused_nfl_props_still_in_prop_models_and_thresholds(), test_retired_prop_picks_still_settle_on_their_own_stat(), test_ten_nfl_distributional_props_are_paused(), test_the_app_mirrors_the_same_set() (+5 more)

### Community 306 - "NBA schedule features"
Cohesion: 0.12
Nodes (10): _counted_schedule(), from_cache(), game_schedule_features(), haversine_miles(), home_bases(), _offsets(), previous_game_load(), team_schedule_features() (+2 more)

### Community 307 - "Pregame line poller tick tests"
Cohesion: 0.08
Nodes (14): over_credit_cap(), test_a_failed_tick_does_not_kill_the_loop(), test_a_failed_tick_throws_the_map_away(), test_a_full_board_call_still_passes_no_subset(), test_a_zero_cap_means_uncapped(), test_an_empty_subset_scores_nothing_rather_than_everything(), test_nhl_is_not_polled_while_out_of_season(), test_the_cap_covers_a_full_day_of_the_measured_burn() (+6 more)

### Community 308 - "Pitcher stats as-of invariant tests"
Cohesion: 0.05
Nodes (36): last3_rates(), outs_from_ip(), per_nine(), whip(), already_a_series(), appearances(), _avg_distinct(), build_rows() (+28 more)

### Community 309 - "tests/test_walk_forward_eval.py"
Cohesion: 0.09
Nodes (13): _frame(), main(), walk_forward(), _Cols, _fake(), _Frame, test_a_fold_with_too_little_history_is_skipped(), test_a_single_class_test_season_is_skipped() (+5 more)

### Community 310 - "docs: mlb_market_handicap_features + mlb_game_market_gate"
Cohesion: 0.15
Nodes (20): Market-aware MLB model, trainable on three seasons, _get_dk_odds bounds on commence_time — the 'pre-game' line was a mid-game price, Activation as a new 2026-only model — superseded by SPARSE_OK, Market movement as a feature, MARKET_MOVEMENT_FEATURES — nine columns in features/market_movement.py, sbr_consensus is one snapshot per game — 17 seasons carry no movement, models/game_market_gate.py — a decision-time overlay for MLB game models, GAME_MARKET_GATE_MODE=live by default (+12 more)

### Community 311 - "docs/sports/ncaaf.md"
Cohesion: 0.13
Nodes (19): Models registry (model id, sport, market, target), NCAAF — pipeline operations (ncaaf.md), ncaaf_spread: cross-book opener rule, structurally dormant on this feed, New CFBD games are dated by Eastern kickoff; existing ids are not rewritten, Old ET/UTC twin rows stay; mirror_scores_to_alias_rows writes the final onto every alias, Issued forecasts for 2024-2025 (game_weather_issued) and the four-arm weather test, Kalshi NCAAF game markets recorded hourly (research only), The live models price FBS-vs-FBS only (shipped 2026-09-13) (+11 more)

### Community 312 - "Live scorer score-change guard"
Cohesion: 0.13
Nodes (12): _book_move(), _get_live_dk_odds(), _score_changed_at(), _FakeConn, _odds(), test_a_quote_published_before_the_score_is_declined(), test_a_quote_republished_after_the_score_is_kept(), test_the_age_bound_alone_would_have_allowed_it() (+4 more)

### Community 313 - "NFL live pick building tests"
Cohesion: 0.09
Nodes (14): build_pick(), refuse_publish_reason(), _Decision, test_a_locked_lane_writes_nothing_further(), test_a_pass_is_never_announced(), test_edge_is_the_platform_edge_not_the_lanes_ev(), test_every_row_key_is_actually_bound_by_the_insert(), test_refuse_publish_allows_a_real_rush_under() (+6 more)

### Community 314 - "Pipeline log reason tests"
Cohesion: 0.22
Nodes (6): _capture(), _Conn, test_a_false_step_records_the_last_error_it_logged(), test_a_false_step_that_logged_nothing_still_says_so(), test_a_raising_step_still_records_the_exception(), test_the_sink_is_removed_after_the_step()

### Community 315 - "NHL props card latest quotes"
Cohesion: 0.10
Nodes (8): candidates(), draftkings_at(), identities(), latest_quotes(), upcoming_rows(), _Conn, TestOnlyTheNewestFetchIsShopped, TestWhoThePlayerIs

### Community 316 - "NFL weather edge study"
Cohesion: 0.15
Nodes (18): audit(), baseline(), bh(), boot(), classify(), era(), grade(), load() (+10 more)

### Community 317 - "Latest line state and Citadel migration cluster tests"
Cohesion: 0.05
Nodes (45): 1. Pre-registered bars (fixed 2026-10-15, before the first grid), 2. Data used (all in Supabase), 3. The market grid, 4.1 Game markets — closed for 2026-27, 4.2 First half / first quarter / team totals — closed for 2026-27, 4.3 Player props — one rule ships, 4.4 Player props — projection models (the NHL recipe), 4.5 The projection model on the worker's inputs only (+37 more)

### Community 318 - "tests/test_live_record_start_views.py"
Cohesion: 0.09
Nodes (12): _body(), _code(), test_both_published_views_carry_the_live_date_gate(), test_it_runs_after_the_migration_that_used_to_own_the_daily_view(), test_migration_is_one_statement(), test_migration_is_registered_with_the_worker_runner(), test_neither_view_reads_the_sweep_universe(), test_no_ddl_outside_the_guarded_branches() (+4 more)

### Community 319 - "tests/test_model_quality.py"
Cohesion: 0.10
Nodes (9): _bet(), test_high_public_pct_on_a_fade_publisher_counts_as_a_fade(), test_low_public_pct_on_the_pick_side_counts_as_a_fade(), test_majority_share_warns_when_not_unanimous(), test_meta_steps_exclude_model_quality(), test_pipeline_step_never_fails_on_crit(), test_pipeline_step_never_fails_on_exception(), test_side_aliases_collapse_to_the_same_direction() (+1 more)

### Community 320 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.09
Nodes (6): _Pg, _PgCursor, TestPreflightCiMode, wind(), wrapped(), fake_open()

### Community 321 - "System health signal checks"
Cohesion: 0.06
Nodes (10): _add_run(), _add_signal(), _iso(), _results(), TestDailyOnlyFeedsOvernightWindow, TestHealthCheckIsNotCountedAsAFailingStep, TestPassCompletion, TestPassSteps (+2 more)

### Community 322 - "Cursor wrapper and X results job tests"
Cohesion: 0.07
Nodes (9): _CursorResult, execute(), test_a_malformed_date_is_refused_before_anything_runs(), test_the_cursor_wrapper_rowcount_is_the_cursors(), test_the_job_does_not_bypass_the_day_is_over_guard(), test_the_job_does_not_read_rowcount_off_the_cursor(), test_the_job_only_clears_its_own_ledger_kind(), test_a_dropped_connection_replays_the_migration_with_its_lock_timeout() (+1 more)

### Community 323 - "NBA prop window scheduling tests"
Cohesion: 0.11
Nodes (22): _fires(), _game(), _jobs(), _plan(), _PlanConn, _t(), test_a_projection_too_old_to_price_does_not_block_the_retry(), test_a_tick_fetches_exactly_the_window_games_then_decides_closes_and_publishes() (+14 more)

### Community 324 - "docs/discord.md"
Cohesion: 0.13
Nodes (17): Discord guarantees: never twice, only ledger what sent, never breaks the pipeline, recap covers a finished day, Discord — publishing picks over webhooks, The producers in tracking/discord_notifier.py, notify_discord_void / push_sent kind discord_void, Live MLB is one model and the loop runs at 5s, Live picks go to their sport's live channel (_live_webhook_for_sport), post_missed_recap from 7am ET on every refresh pass, posted <time ET> = picks.created_at (+9 more)

### Community 325 - "docs/team_stats_leak.md"
Cohesion: 0.15
Nodes (20): mlb_f5_moneyline v4 retrained on the rebuilt tables (holdout 2026, AUC 0.5548), WNBA ESPN team ids resolve dynamically by full team name (expansion teams PDX, TOR, GSV), docs/team_stats_leak.md, config.assert_retrain_allowed('MLB') and the TEAM_STATS_ASOF_REBUILD_COMPLETE marker, Eight features constant in every training season, The leaked seasons collapsed to the honest season's level, mlb_pitcher_stats table (season-final ERA on every start), mlb_team_stats table (+12 more)

### Community 326 - "tests/test_api_call_rollup.py"
Cohesion: 0.09
Nodes (10): test_a_fold_can_never_lower_a_stored_total(), test_a_new_process_does_not_prune_on_its_first_flush(), test_prune_rolls_up_before_it_deletes(), test_the_daily_table_is_created_and_locked_down(), test_the_daily_table_keys_on_day_api_and_source(), test_the_rollup_groups_by_eastern_day_not_utc(), test_the_rollup_reads_only_yesterday_and_today(), test_the_rollup_survives_a_failure_without_blocking_the_prune() (+2 more)

### Community 327 - "tests/test_ncaaf_live_states.py"
Cohesion: 0.16
Nodes (13): record_live_states(), state_change_row(), state_key(), _Conn, _state(), test_a_failed_write_never_costs_the_pass(), test_a_score_a_period_or_a_possession_change_is_written(), test_first_sight_is_written() (+5 more)

### Community 328 - "MLB prop market pregame quote cutoff"
Cohesion: 0.12
Nodes (7): _Conn, test_a_game_with_no_cutoff_fails_open(), test_both_market_relative_loaders_bound_on_the_cutoff(), test_it_compares_parsed_timestamps_not_strings(), test_it_joins_games_and_uses_the_shared_cutoff(), test_the_newest_qualifying_quote_still_wins(), test_the_post_first_pitch_quote_is_dropped_even_though_it_is_newest()

### Community 329 - "nfl/models/opener_spread.py"
Cohesion: 0.14
Nodes (11): age_tag(), american_to_prob(), _bettable_books(), clean_board(), edge_tier(), evaluate_board(), held_minutes(), model_prob_for_dev() (+3 more)

### Community 330 - "tests/test_nfl_opener.py"
Cohesion: 0.13
Nodes (7): build_opener_rows(), _opener_model(), _card_row(), TestBuildOpenerRows, _row(), TestPublishOpenerInsertOnce, execute()

### Community 331 - "NHL prop backtest and combined cap"
Cohesion: 0.15
Nodes (16): books(), card(), claimed_vs_realised(), day_interval(), line(), main(), predictions(), prices() (+8 more)

### Community 332 - "tests/test_live_slate_midnight.py"
Cohesion: 0.10
Nodes (10): _at(), test_both_live_loops_share_one_definition_of_the_slate(), test_by_daytime_yesterday_is_dropped(), test_just_after_midnight_still_asks_about_yesterday(), test_just_before_midnight_asks_about_today_only(), test_the_apps_live_hook_resolves_the_window_per_fetch(), test_the_apps_live_reads_take_a_LIST_of_dates(), test_the_ncaaf_live_loop_got_the_same_fix() (+2 more)

### Community 333 - "tests/test_nfl_wind_fire_window.py"
Cohesion: 0.07
Nodes (18): _retractable_slate(), _slate(), test_a_blank_roof_at_a_NON_retractable_venue_is_unaffected(), test_a_closed_roof_is_still_indoor(), test_a_retractable_venue_with_an_unknown_roof_does_not_fire(), test_a_waiting_game_is_not_reported_as_a_collapsed_premise(), test_a_waiting_row_keeps_its_line_price_and_edge(), test_every_blank_roof_row_is_a_retractable_venue() (+10 more)

### Community 334 - "College football data parsers"
Cohesion: 0.08
Nodes (23): ingest_ncaaf_team_stats(), _int(), _num(), parse_advanced_stats(), parse_ratings(), parse_returning(), parse_season_stats(), parse_talent() (+15 more)

### Community 335 - "tests/test_public_betting_ingestor.py"
Cohesion: 0.17
Nodes (17): parse_public_betting(), _pct(), _select_book(), _make_game(), test_parse_emits_six_rows(), test_parse_game_id_and_sides(), test_parse_marks_source_and_snapshot(), test_parse_missing_teams_returns_empty() (+9 more)

### Community 336 - "Odds pruning and opener retention"
Cohesion: 0.11
Nodes (11): _counts(), main(), _older_than(), prune_table(), run_prune_odds(), _unprotected(), test_cfbd_archive_prefix_is_protected(), test_historical_backfill_rows_are_protected_in_odds() (+3 more)

### Community 337 - "docs/sports/nfl.md"
Cohesion: 0.17
Nodes (20): NFL — standalone wind/opener model and the in-play leader (nfl.md), docs/nfl_edge_search.md: 14 ideas at zero credits; the in-play model retired, Possession bugs in the old core parser (situation.possession never sent; substring team-id match), DK line snapshots flushed into odds (zero extra credits) and pick-timing display, How the loop runs: ESPN core every 20 s, one DK call per due game, 1 credit, five-minute slots, nfl_live_leader_ml — in-play leader moneyline, live 2026-10-13, gate 0 of 50, Thirteen logistic regressions, one per exact lead 4..16 (nfl_live_leader_ml_wp.json), The population of record: 163 bets, +13.08u, +8.0% at lag 0 (+12 more)

### Community 338 - "mobile: TESTFLIGHT + README"
Cohesion: 0.15
Nodes (18): mlb_total_public_fade: fade consensus OVER tickets >= 70, bet UNDER (paper, INSERT gated), BET signal thresholds and the action filter (per-model prob/edge tables), App Store Connect metadata (Signalbase), App Privacy: no data collected (bankroll is on-device AsyncStorage), App review notes: read-only, anon key is intended public read-only via RLS, Signalbase — the iOS app name and listing, Signalbase iOS app README (Expo / React Native), App structure: lib, hooks, screens, components (+10 more)

### Community 339 - "tests/test_service_role_split.py"
Cohesion: 0.15
Nodes (11): _all_job_ids(), _sched(), test_an_unknown_role_runs_everything(), test_every_add_job_call_passes_an_id(), test_every_job_is_owned_by_exactly_one_role(), test_the_always_on_jobs_run_on_every_role(), test_the_default_preserves_the_single_container(), test_the_nfl_worker_stays_with_the_volume() (+3 more)

### Community 340 - "supabase/functions/README.md"
Cohesion: 0.19
Nodes (21): revenuecat-webhook Edge Function, Stripe rail (stripe-checkout / stripe-portal / stripe-webhook), dark, subscriptions table (keyed to auth.users, webhooks write), discord-link Edge Function (OAuth, guild join, role sync), _shared/discord.ts (bot API helpers), _shared/entitlement.ts (two-way rule, one place), Supabase Edge Functions README, discord-link Edge Function (verify_jwt true) (+13 more)

### Community 341 - "Mobile range slider filter"
Cohesion: 0.18
Nodes (21): at(), collapsed, crossed, crossedHigh, reopened, S, tapped, Props (+13 more)

### Community 342 - "tests/test_live_pick_features.py"
Cohesion: 0.18
Nodes (11): _record_live_features(), FakeConn, _pick(), test_a_live_bet_records_its_feature_row_and_lambda(), test_a_pick_with_no_feature_row_is_skipped_not_written_empty(), test_a_recorder_failure_is_rolled_back_to_its_savepoint(), test_a_recorder_failure_is_swallowed_rather_than_raised(), test_a_success_releases_its_savepoint() (+3 more)

### Community 343 - "tests/test_http_timeout_floor.py"
Cohesion: 0.10
Nodes (11): install_timeout_floor(), _call(), clean_requests(), test_a_call_with_no_timeout_gets_one(), test_an_explicit_timeout_is_never_overridden(), test_installing_twice_is_a_no_op(), test_the_deadline_is_env_overridable(), test_the_deadline_survives_telemetry_being_turned_off() (+3 more)

### Community 344 - "Picks and public track record views"
Cohesion: 0.09
Nodes (19): v_opening_signal_slices, v_opening_vs_live, public.v_public_track_record, public.v_public_track_record_daily, public.v_public_track_record, public.v_public_track_record_daily, public.v_public_track_record, public.v_public_track_record_daily (+11 more)

### Community 345 - "NCAAF totals lead and consensus gate"
Cohesion: 0.17
Nodes (16): fmt(), grade(), load_closes(), main(), match(), build_lead_table(), first_cross(), fmt() (+8 more)

### Community 346 - "scripts/nfl_edge_cache.py"
Cohesion: 0.10
Nodes (24): NFL edge search 2026-10-11, docs/nfl_live_prop_assessment.md, Live pass-attempt bias assessment (2026-09-21), Publish backstop refuses pass-attempt overs, docs/nfl_live_rush_attempts.md, Accrued carries from ESPN core leaders, rush_attempt_pace model: one offset on the book's number, Pace ratio (+16 more)

### Community 347 - "Paused model assessment script"
Cohesion: 0.22
Nodes (9): _auto_paused_models(), active_era(), assess(), _half(), fetch(), grade(), main(), sweep() (+1 more)

### Community 348 - "Pregame price age tests"
Cohesion: 0.04
Nodes (29): check_line_movement(), _get_dk_odds(), _swap_home_away(), _ago(), _BoardConn, _clock(), _h2h_row(), _OddsConn (+21 more)

### Community 349 - "tests/test_prop_missing_features.py"
Cohesion: 0.14
Nodes (5): _frame(), helper(), TestARowMissingAFeatureIsNotScored, TestEveryPropLoopGoesThroughTheHelper, TestTheUmpireIsTheDeclaredException

### Community 350 - "NFL opener card and line snapshots"
Cohesion: 0.11
Nodes (10): append_snapshot_csv(), dump_dk_lines(), _num(), snapshot_schedule(), dump_board(), dump_eval_rows(), _load_nfl_model(), load_prior_observations() (+2 more)

### Community 351 - "tests/test_nfl_injury_ingest.py"
Cohesion: 0.11
Nodes (9): _fetch_nfl_espn_team_ids_core(), _nfl_espn_team_to_abbrev(), _fake_fetch(), test_core_nfl_listing_failure_returns_empty(), test_core_nfl_team_ids_resolve_lar_and_wsh_to_ours(), test_injury_fetch_raises_the_page_limit(), test_nfl_active_rows_are_dropped_and_out_keeps_espn_date(), test_nfl_name_join_uses_our_abbrevs_not_espns() (+1 more)

### Community 352 - "NHL prop odds alternate line tests"
Cohesion: 0.11
Nodes (14): due(), test_a_game_first_priced_inside_the_final_window_gets_nothing_more(), test_a_game_first_priced_inside_the_window_gets_one_decision_snapshot(), test_a_game_with_nothing_stored_is_owed_its_open(), test_a_moved_featured_line_keeps_the_old_number_under_the_alternate_key(), test_a_whole_day_of_passes_buys_exactly_three(), test_after_the_close_one_final_is_bought_for_clv_and_then_nothing(), test_an_opened_game_is_owed_nothing_until_the_closing_window() (+6 more)

### Community 353 - "Player news ingestor"
Cohesion: 0.04
Nodes (51): _article_url(), _athletes_in(), build_name_index(), _fetch_espn(), fetch_espn_news(), absorb(), ingest_player_news(), main() (+43 more)

### Community 354 - "NBA prop closing line tests"
Cohesion: 0.09
Nodes (11): _Conn, _Resp, test_a_close_already_held_is_not_bought_again(), test_a_due_close_buys_one_call_of_the_bet_markets_and_reports_its_credits(), test_a_pass_outside_the_window_spends_nothing(), test_only_a_game_holding_a_bet_and_only_once(), test_only_twelve_to_twenty_five_minutes_before_tip(), test_the_ten_minute_evening_passes_always_land_one_inside() (+3 more)

### Community 355 - "Live honest cut and research scripts"
Cohesion: 0.03
Nodes (51): backfill_weather(), fetch_and_store_weather_for_date(), _is_dome_game(), _wind_out_component(), step_nfl_prop_scoring(), bets_split(), _fmt(), _grid() (+43 more)

### Community 356 - "NCAAF in-play model docs"
Cohesion: 0.14
Nodes (15): NCAAF live (in-play) model README, CFBD_MONTHLY_CALL_ALLOWANCE (Tier 4, 125k), Worker cannot reach site.api.espn.com (403); CFBD /scoreboard is the state source, ncaaf_live.gameday loop, Gate 1: win probability Brier 0.115 PASS vs 0.20, Gate 2: total shape 2.60pp FAIL vs 2.0pp, Market licenses from the calibration gates, LIVE_ODDS_MAX_AGE_SEC (180s) odds age bound (+7 more)

### Community 357 - "Injury fetch speed and cache tests"
Cohesion: 0.07
Nodes (10): _clear_cache(), test_a_dead_database_leaves_the_cache_empty_not_broken(), test_a_failed_lookup_is_not_cached(), test_a_known_athlete_costs_no_request(), test_a_SUCCESSFUL_response_with_no_name_is_not_cached(), test_an_unknown_athlete_is_fetched_and_then_remembered(), test_one_team_failing_does_not_lose_the_others(), test_output_order_follows_the_team_list_not_completion_order() (+2 more)

### Community 358 - "NFL live pick writer failure tests"
Cohesion: 0.07
Nodes (15): _executor_min_price(), _OpenConn, _probe_config(), test_a_failing_announcer_cannot_undo_or_fail_the_write(), test_a_failing_recorder_cannot_take_the_other_down(), boom(), test_a_written_bet_is_announced_with_its_own_game_date(), test_an_unlocked_lane_does_write() (+7 more)

### Community 359 - "NFL live pick recorder declines"
Cohesion: 0.12
Nodes (12): PicksRecorder, _AvoidConn, _mk_decline(), test_a_market_opinion_decline_is_written_as_avoid(), test_a_moved_line_is_rewritten(), test_an_unchanged_proposition_is_not_rewritten(), test_plumbing_refusals_stay_out_of_picks(), test_recording_a_decline_can_never_break_a_bet() (+4 more)

### Community 360 - "Prop player name matching tests"
Cohesion: 0.11
Nodes (15): normalize_player_name(), resolve_feed_name(), _get_prop_dk_odds(), FakeConn, test_accented_roster_name_matches_the_flat_feed_name(), test_ambiguity_is_a_miss_not_a_guess(), test_an_unlisted_player_is_still_a_miss(), test_every_prop_lane_keys_line_shopping_on_the_resolved_name() (+7 more)

### Community 361 - "tests/test_config.py"
Cohesion: 0.08
Nodes (8): test_an_own_floor_does_not_take_a_model_off_the_calibration_map(), test_every_model_carries_its_own_thresholds(), test_every_own_floor_names_a_live_model(), test_models_on_own_probability_is_not_derived_from_the_floor_dict(), test_no_own_floor_tightens_a_model_past_the_global_floor(), test_only_a_market_priced_model_carries_a_negative_floor(), test_own_ev_floor_and_model_min_ev_stay_disjoint(), test_the_models_the_global_floor_silently_removed_can_bet_again()

### Community 362 - "Latest line state tables"
Cohesion: 0.15
Nodes (18): public.latest_lines_rebuild_props(), public.latest_live_game_state, public.latest_live_game_state_on_insert(), public.latest_odds, public.latest_odds_on_insert(), public.latest_odds_on_update(), public.latest_prop_odds, public.latest_prop_odds_on_insert() (+10 more)

### Community 363 - "tests/test_run_ledger_orphans.py"
Cohesion: 0.12
Nodes (18): _Conn, db(), _insert_open(), _ledger(), _open_rows(), _row(), test_a_genuine_current_hang_is_still_detectable(), test_a_second_sweep_does_not_abort_the_pass_this_process_started() (+10 more)

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
Cohesion: 0.11
Nodes (15): _blk_career_stats(), build_ufc_features_from_bulk(), _bulk_fighter_id(), _fight_minutes(), resolve_slug(), _slug_tokens(), test_a_generational_suffix_resolves_either_way(), test_a_near_miss_is_not_a_match() (+7 more)

### Community 370 - "UFC stats ingestor and CSV loader"
Cohesion: 0.02
Nodes (108): _aggregate_stats(), backfill_ufc_csv(), build_events(), build_fighter_index(), _cached_etag(), _etag_cache_path(), _heal_window_lo(), ingest_ufc_results_for_date_csv() (+100 more)

### Community 371 - "tests/test_team_stats_asof_invariants.py"
Cohesion: 0.10
Nodes (11): impossible_games_played(), _played_actual(), test_a_missing_count_is_reported_not_silently_passed(), test_an_honest_row_passes(), test_claiming_fewer_games_than_played_is_fine(), test_feb_gp_climbing_vs_zero_regular_season_still_fails(), test_one_game_date_boundary_mismatch_is_tolerated(), test_season_final_in_april_is_still_caught() (+3 more)

### Community 372 - "docs/sports/mlb.md"
Cohesion: 0.13
Nodes (14): MLB — model state and player-props plan (mlb.md), Batter prop models (hits, TB Poisson; HR logistic retired), Bulk feature loading: ~6 hours -> ~3 seconds per model, CalError requires min_samples=20 per bin, F5 O/U and RL priced off the first bettable book (DK returns 0 rows), The F5 sweep does not produce a threshold: 0.74 fired zero bets, one positive cell in fifty, Market-relative game gate (models/game_market_gate.py): no-vig fair, PASS-when-steamed, The honest MLB numbers: ~0.55-0.56 AUC, not 0.60-0.64 (+6 more)

### Community 373 - "Anon grant sweep tests"
Cohesion: 0.08
Nodes (11): test_a_writable_relation_that_is_not_readable_is_still_swept(), test_every_declared_write_verb_has_a_call_site_that_needs_it(), test_public_is_stripped_from_every_declared_callable_before_it_is_granted(), test_subscriptions_stays_authenticated_only(), test_the_apply_script_reads_back_that_rls_actually_landed(), test_the_apply_script_revokes_writes_and_reads_the_result_back(), test_the_default_privilege_revoke_names_the_api_roles_only(), test_the_dynamic_backup_table_is_locked_down_where_it_is_created() (+3 more)

### Community 374 - "docs/thresholds.md"
Cohesion: 0.15
Nodes (14): Min-history gate: >= 3 prior UFC fights or the fight is skipped, docs/thresholds.md, Breakeven is the mean DK implied probability of the bets taken, not 52.4%, The forward check on fresh quotes: the 73.5% never existed, mlb_live_total_runs on the bought 2025 in-play history (260,190 credits), The live calibration map (Platt a=0.8578, b=-0.0787, promote_external), mlb_live_total_runs cut 0.70 -> 0.72 (superseded 2026-09-10), nfl_opener_spread cut: |dev| 1.0 -> 2.0, gate 0.52 -> 0.55 (+6 more)

### Community 375 - "Refresh pass step ordering tests"
Cohesion: 0.10
Nodes (13): _order(), test_a_parallel_step_that_fails_is_still_recorded(), test_no_sequential_step_runs_while_a_parallel_group_is_open(), test_opening_signals_follows_every_scorer(), test_parlay_follows_opening_signals(), test_scoring_follows_every_ingest(), test_settle_follows_every_results_ingest(), test_sync_thresholds_follows_migrations_and_precedes_scoring() (+5 more)

### Community 376 - "CFBD ingestor"
Cohesion: 0.07
Nodes (26): backfill_ncaaf_lines(), backfill_ncaaf_players(), backfill_ncaaf_qb(), _date_or_none(), _existing_ncaaf_ids(), _fold(), _get(), ingest_ncaaf_game_log() (+18 more)

### Community 377 - "NFL game lines and wind totals docs"
Cohesion: 0.17
Nodes (18): Critical data defect: home/away sign flips in four books, NFL Game Lines Model System README, Under rate falls ~0.41pp per day of forecast lead, data/odds_cache/ (~45,000 credits of snapshots), Open-Meteo (ERA5, issued forecasts, live forecasts) via data_ingest/weather.py, wind_speed_10m_previous_dayN is null before 2024-01-18, What does not work (backup QB, home dogs, cold unders, refs, rest, ...), scripts/replay_wind_card.py regression test (+10 more)

### Community 378 - "NFL line snapshot tests"
Cohesion: 0.15
Nodes (6): snapshot_row_params(), _csv_row(), TestPublishLineSnapshots, execute(), TestSnapshotRowParams, _write_snapshot_csv()

### Community 379 - "Mobile in-app purchases"
Cohesion: 0.17
Nodes (18): apiKey(), ensureConfigured(), fetchLocalizedPrices(), IapPurchaseResult, loadPurchases(), openIapManagement(), presentRedeemCodeSheet(), purchasePlan() (+10 more)

### Community 380 - "NFL historical weather fetch script"
Cohesion: 0.18
Nodes (10): consolidate(), DailyLimit, era5_check(), game_hours(), log(), main(), om_get(), Pacer (+2 more)

### Community 381 - "tests/test_heartbeat_disabled_jobs.py"
Cohesion: 0.14
Nodes (8): _build(), Conn, test_a_job_marked_disabled_is_not_silent(), test_a_job_that_runs_here_is_not_marked(), test_a_service_leaves_alone_the_jobs_another_service_owns(), test_startup_marks_an_owned_job_that_is_switched_off(), ensure_schema(), stale_jobs()

### Community 382 - "Pregame line poller map seeding"
Cohesion: 0.11
Nodes (9): _key(), _PollConn, _quiet_poll(), test_a_key_the_database_has_never_stored_is_written(), test_a_tick_given_a_map_does_not_rebuild_it(), test_a_tick_given_no_map_seeds_the_keys_it_was_quoted(), test_a_tick_with_nothing_quoted_runs_no_seed(), test_the_seed_asks_only_for_keys_the_map_does_not_hold() (+1 more)

### Community 383 - "NFL in-play line churn"
Cohesion: 0.19
Nodes (13): churn_table(), main(), verdict(), _snaps(), test_a_line_moving_every_interval_reads_as_under_sampled(), test_a_missing_key_column_fails_loudly_rather_than_grouping_coarser(), test_a_single_snapshot_contributes_no_interval(), test_a_still_line_reads_as_still() (+5 more)

### Community 384 - "tests/test_mobile_threshold_parity.py"
Cohesion: 0.16
Nodes (12): _block(), _canonical(), _mirror(), _mirror_paused(), _src(), test_every_cut_matches_config(), test_every_scorable_model_is_in_the_app_mirror(), test_the_app_mirror_holds_no_model_config_cannot_score() (+4 more)

### Community 385 - "NFL live prop assessment script"
Cohesion: 0.19
Nodes (14): _connect(), american_b(), boot_ci(), build(), cluster_se_mean(), implied(), load(), main() (+6 more)

### Community 386 - "tests/test_nhl_derivative_odds_job.py"
Cohesion: 0.12
Nodes (9): test_a_credit_ceiling_is_a_malformed_request(), test_apply_argv_is_only_apply(), test_apply_is_explicit_and_carries_no_ceiling(), test_dry_run_argv_has_no_apply_and_no_ceiling(), capture(), test_empty_args_are_a_dry_run(), test_probe_argv_does_not_apply(), _job_nhl_derivative_odds_history() (+1 more)

### Community 387 - "tests/test_repair_bogus_first_pitch_labels.py"
Cohesion: 0.13
Nodes (8): _Conn, _run(), test_a_dry_run_writes_nothing_at_all(), test_a_short_backup_rolls_back_and_relabels_nothing(), test_the_backup_is_written_before_the_update(), test_the_backup_table_is_revoked_from_the_public_roles(), test_the_bogus_set_is_computed_never_listed(), test_the_query_is_scoped_to_the_scheduled_start_not_the_derived_one()

### Community 388 - "tests/test_track_record_views.py"
Cohesion: 0.11
Nodes (10): _body(), _code(), test_migration_is_one_statement(), test_migration_is_registered_with_the_worker_runner(), test_no_ddl_outside_the_guarded_branches(), test_refresh_pass_refreshes_outcomes_after_settle(), test_the_daily_view_is_no_longer_redefined_here(), test_the_full_outcome_view_reads_the_matview_and_never_the_player_logs() (+2 more)

### Community 389 - "tests/test_weekly_catch_up.py"
Cohesion: 0.12
Nodes (10): sched(), test_a_fresh_savant_does_not_suppress_the_calibration_catch_up(), test_a_missing_sweeps_table_counts_as_stale(), test_a_recent_sweep_does_not(), test_an_old_sweep_triggers_the_catch_up(), test_model_calibration_belongs_to_the_pipeline_service(), test_the_catch_up_creates_the_review_tables_on_boot(), test_the_review_schema_is_not_gated_by_owns() (+2 more)

### Community 390 - ".claude/rules: CLAUDE + config-topology"
Cohesion: 0.17
Nodes (4): config-topology.md — path-scoped rule file, DraftKings — primary sportsbook and feature reference, model_action_thresholds — the mirrored per-model cut, picks table — every publishing surface reads it

### Community 391 - ".github/workflows: CLAUDE + mobile-build"
Cohesion: 0.15
Nodes (11): Fetch brand assets workflow, Mobile TestFlight build workflow, Latest TestFlight build tracking issue, Mobile OTA update (production) workflow, monitor probe workflow, Prune merged branches workflow, §5 Commands — pipeline, threshold sync, retrain, pytest, §8 Current state — 74 models, 29 paused, Railway worker, Supabase picks (+3 more)

### Community 392 - "tests/test_live_game_state_poller.py"
Cohesion: 0.17
Nodes (16): _detect_triggers(), _is_active_or_starting_soon(), test_active_in_progress_game_is_active(), test_combined_changes_fire_all_relevant_triggers(), test_due_up_change_fires_due_up_change(), test_final_game_is_not_active(), test_identical_state_fires_no_triggers(), test_inning_half_change_fires_inning_change() (+8 more)

### Community 393 - "tests/test_sbr_loader.py"
Cohesion: 0.14
Nodes (3): loader_conn(), _SqliteConnShim, _SqliteCursorShim

### Community 394 - "Discord restate signal tests"
Cohesion: 0.11
Nodes (14): _restate_env(), _restate_signals(), test_a_failed_restate_ledgers_nothing_so_it_retries(), test_a_rate_limited_restate_leaves_nothing_half_posted(), test_configured_is_false_only_when_nothing_is_set(), test_only_live_channels_configured_still_counts_as_configured(), test_restate_deletes_the_stale_post_when_the_id_is_known(), test_restate_fires_exactly_once() (+6 more)

### Community 395 - "docs/agents_contract.md"
Cohesion: 0.15
Nodes (13): AGENTS — one-screen agent roster, Agents contract — Sentinel and Janitor, catch_up_weekly_jobs on boot, Janitor retired 2026-09-03, ModelCalibration weekly re-measure, The pipeline watch's six rules, Sentinel (pipeline watch Routine, retired), Guardrails both agents share (+5 more)

### Community 396 - "NFL Kalshi fetch and price floor grid"
Cohesion: 0.21
Nodes (6): candles(), get(), map_games(), paged(), parse_event(), probe()

### Community 397 - "mobile/scripts/ux_scan.mts"
Cohesion: 0.16
Nodes (18): APP_ROOT_FILE, changedFiles(), entitlementGate(), Finding, fontScaling(), fontSizeLiterals(), hexColors(), main() (+10 more)

### Community 398 - "CLV card price taken tests"
Cohesion: 0.13
Nodes (17): _app(), _clv_card(), _server(), test_a_label_book_nfl_pick_compares_its_line_with_that_book(), test_a_recorded_book_differs_from_the_derived_one(), test_the_app_prefers_the_recorded_book_at_the_derived_price(), test_the_app_prices_every_row_as_the_server_grades_it(), test_the_card_prints_the_price_taken_not_draftkings() (+9 more)

### Community 399 - "NFL live leader model tests"
Cohesion: 0.13
Nodes (13): art(), _d(), _raw(), test_600_seconds_and_both_lead_ends_are_inside(), test_a_flipped_spread_sign_changes_the_decision(), test_a_qualifying_state_bets_the_leader_at_its_price(), test_artifact_identity_training_and_rule(), test_band_matches_training_leader_view_on_nflverse_sign() (+5 more)

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

### Community 407 - "docs/live_odds_freshness.md"
Cohesion: 0.16
Nodes (14): Basketball Daily Ingest stays on Matt's PC, DraftKings direct needs BOTH a browser fingerprint and a residential address, The feed has a ~45s floor and it cannot be bought past, The Odds API in-play feed is a ~45-67 s cache, Direct book feeds from both addresses (book_direct_probe.py), data/ingestors/dk_direct_feed.py (RUN_DK_DIRECT_FEED defaults 0), DK direct: fingerprint AND address are both necessary, Live odds freshness — what was measured and what to do (+6 more)

### Community 408 - "Price prefilter timeout rollback tests"
Cohesion: 0.15
Nodes (9): _event_index(), _games(), _PoisonConn, _run(), test_a_failed_savepoint_rollback_falls_back_to_full_rollback(), test_both_prefilters_timing_out_still_reaches_the_pipeline_log(), test_lookahead_timeout_rolls_back_and_scoring_continues(), test_ncaaf_timeout_rolls_back_and_scoring_continues() (+1 more)

### Community 409 - "mobile/src/lib/otaUpdate.ts"
Cohesion: 0.21
Nodes (11): Calls, check(), fakeApi(), main(), applyPendingUpdate(), CheckState, CheckTrigger, MIN_BACKGROUND_MS (+3 more)

### Community 410 - "Prop market one side per line"
Cohesion: 0.16
Nodes (8): best_per_prop(), _Conn, _hockenson(), test_a_different_market_on_the_same_player_is_still_its_own_bet(), test_input_order_does_not_decide_the_side(), test_nfl_publish_will_not_add_the_other_side_of_a_locked_line(), test_opposite_sides_of_one_line_collapse_to_the_bigger_edge(), test_wnba_publish_will_not_add_the_other_side_of_a_locked_line()

### Community 411 - "NCAAF search feature matrix"
Cohesion: 0.15
Nodes (11): load_fbs_membership(), load_team_games(), pool_fcs_opponents(), _asof_merge(), build_matrix(), _haversine(), _load_asof_stats(), _load_venues() (+3 more)

### Community 412 - "tests/test_clv_backfill_job.py"
Cohesion: 0.15
Nodes (5): _Conn, _stub_backfill(), test_hard_cap_stops_a_nonempty_queue(), test_loops_until_a_pass_fills_nothing(), test_the_runner_opens_get_connection_and_calls_backfill_clv()

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
Cohesion: 0.14
Nodes (7): _is_market_opinion(), _lane_is_locked(), _norm_player(), resolve_game(), resolve_game_id(), test_normalised_player_key_is_the_join_the_prop_system_uses(), test_the_lane_lock_shares_the_scorers_meaning_of_locked()

### Community 417 - "tracking/model_quality.py"
Cohesion: 0.12
Nodes (12): record_exclusion_sql(), test_clv_clear_negative_vs_baseline_is_flagged(), test_raw_one_sided_clv_is_ignored(), test_the_exclusion_sql_is_a_conjunction_of_negations(), _job_model_quality(), detect_clv_degradation(), _group(), _result_row() (+4 more)

### Community 418 - "NCAAF search walk-forward validation"
Cohesion: 0.17
Nodes (11): brier(), calibration_curve(), clv_report(), ece(), FoldResult, kelly_stake(), log_loss(), market_only_sanity() (+3 more)

### Community 419 - "MLB runline retrain sweep job"
Cohesion: 0.10
Nodes (8): test_the_raised_timeout_is_restored_after_the_job(), test_the_restore_puts_back_a_pre_existing_value(), test_marker_file_is_in_tree_so_the_freeze_would_not_block_the_worker(), test_missing_artifact_path_refuses_to_sweep_live(), test_retrain_then_sweep_passes_the_new_path(), test_the_runner_retrains_then_sweeps_the_new_artifact(), _job_mlb_runline_retrain_sweep(), _job_retrain_model()

### Community 420 - "mobile/docs/UX_REVIEW.md"
Cohesion: 0.16
Nodes (13): Front-end UX review checklist, A pick is a pick (re-priced line never replaces the locked one), Copy: formatAmerican/formatPct/formatCurrency, model ids never raw, Decided at the best bettable price; read via lib/decisionPrice.ts, frontend-ux-designer agent contract, Mobbin MCP connector (one route: Matt's claude.ai connector), Product rules: a violation is a Blocker, Reuse before invention (EmptyState, StatTile, SignalBadge, ...) (+5 more)

### Community 421 - "Paused and no-signal row tests"
Cohesion: 0.14
Nodes (11): _apply_no_signal(), _game_pick(), _prop_pick(), test_auto_paused_counts_as_paused(), test_no_signal_rows_persist_the_reason(), test_paused_game_model_avoid_stays_avoid_with_reason(), test_paused_game_model_bet_stays_bet_with_reason_and_stake(), test_paused_prop_model_avoid_stays_avoid_with_reason() (+3 more)

### Community 422 - "NBA prop stat settlement tests"
Cohesion: 0.12
Nodes (8): _SelectConn, test_a_missing_stat_is_none_not_zero(), test_a_turnovers_bet_on_a_player_who_played_settles_win_not_no_action(), test_combo_markets_are_mapped_to_helpers_and_only_the_nba_rule_uses_them(), test_double_double_matches_the_rule_it_replaced(), test_the_loader_carries_every_stat_a_market_settles_on(), test_the_loader_selects_turnovers(), _nba_prop_actual()

### Community 423 - "First pitch guard tests"
Cohesion: 0.18
Nodes (3): test_delivery_fails_open_too(), test_health_check_uses_the_same_first_pitch_bound_as_discord(), test_mixed_timestamp_shapes_are_parsed_not_string_compared()

### Community 424 - "supabase/functions/_shared/discord.ts"
Cohesion: 0.20
Nodes (15): addAppRole(), addGuildMember(), APP_ROLE_ID, BOT_TOKEN, botFetch(), DiscordApiError, DiscordUser, expectOk() (+7 more)

### Community 425 - "NFL odds cache import to Supabase"
Cohesion: 0.12
Nodes (9): _allowed(), _data_dirs(), test_a_rerun_after_the_resolver_improves_adds_only_the_gap(), test_every_buying_ingestor_keys_its_resume_on_a_source_marker(), test_no_undeclared_data_store_on_disk(), test_the_importer_resolves_a_postponed_game(), test_the_importer_still_refuses_an_event_with_no_game(), test_the_nfl_odds_cache_has_an_importer() (+1 more)

### Community 426 - "tests/test_health_check_observe.py"
Cohesion: 0.14
Nodes (10): _crit(), fake(), test_a_crit_does_not_fail_the_observe_path(), test_a_crit_still_fails_the_daily_step(), test_an_exception_does_not_fail_the_observe_path(), test_daily_syncs_thresholds_after_view_migrations(), test_it_still_runs_the_check_when_observing(), test_ok_is_identity_in_both_modes() (+2 more)

### Community 427 - "Intraday freshness tests"
Cohesion: 0.14
Nodes (10): _is_fresh(), _minutes_since(), _age(), test_an_unknown_age_refetches_rather_than_skipping(), test_fresh_data_is_skipped(), test_stale_data_is_refetched(), test_the_6am_pipeline_is_never_throttled(), test_the_boundary_refetches() (+2 more)

### Community 428 - "Prop ladder and Kalshi pricing"
Cohesion: 0.03
Nodes (46): _event_date(), ladders(), ladders_or_empty(), _player(), record_ladders(), find_bets(), _expit(), from_kalshi() (+38 more)

### Community 429 - "NFL prop shape simulation"
Cohesion: 0.20
Nodes (12): anchor_scale(), calibration(), grade(), latest(), load_odds(), main(), placebo_sf(), player_gamma() (+4 more)

### Community 430 - "NFL in-play win probability fits"
Cohesion: 0.13
Nodes (14): finalize_states(), fit_models(), h1_frame(), states(), check_possession(), fit_wp(), leader_view(), logit_irls() (+6 more)

### Community 431 - "tests/test_pick_lock_is_on_picks.py"
Cohesion: 0.16
Nodes (9): _between(), _sql(), test_a_bet_is_still_never_re_scored(), test_only_a_bet_locks_a_pair(), test_the_cleanup_covers_the_whole_look_ahead_window(), test_the_cleanup_never_touches_a_started_game_or_a_live_row(), test_the_lock_is_no_longer_ncaaf_specific(), test_the_prop_and_live_locks_are_unchanged() (+1 more)

### Community 432 - "System health checks"
Cohesion: 0.03
Nodes (39): ncaaf_season_for_date(), test_a_game_date_inside_the_window_counts(), test_a_lookahead_commence_counts_even_when_game_date_is_outside(), test_a_signal_locked_after_first_pitch_was_never_deliverable(), test_a_signal_locked_before_first_pitch_still_counts(), test_a_signal_locked_exactly_at_first_pitch_counts(), test_a_started_game_outside_the_window_does_not_count(), test_it_fails_toward_noticing() (+31 more)

### Community 433 - "NFL 2026 rule track tests"
Cohesion: 0.16
Nodes (13): opener_verdict(), _row(), _src(), test_config_comments_state_the_policy(), test_live_cuts_did_not_move(), test_max_fire_lead_stays_four_in_the_live_model(), test_opener_does_not_retire_mid_season_even_if_currently_up(), test_opener_retire_candidate_only_when_the_season_finished_flat_or_worse() (+5 more)

### Community 434 - "NBA prop market model and card"
Cohesion: 0.07
Nodes (29): coherent(), fair_under(), fetch_times(), find_bets(), in_window(), load_quotes(), minutes_to_tip(), NbaPropDecision (+21 more)

### Community 436 - "tests/test_mlb_sbr_twin.py"
Cohesion: 0.21
Nodes (9): _lookup_home_won(), mlb_game_final(), sbr_twin_id(), _Conn, _Cur, test_no_final_anywhere_is_none(), test_scored_canonical_row_wins_and_keeps_its_label(), test_twin_id_swaps_only_the_renamed_franchises() (+1 more)

### Community 437 - "tests/test_ufc_phantom_filter.py"
Cohesion: 0.21
Nodes (6): _filter_ufc_phantom(), _is_known_ufc_matchup(), _game(), _odds(), TestFilterUfcPhantom, TestIsKnownUfcMatchup

### Community 438 - "Slate concentration and fade risk checks"
Cohesion: 0.16
Nodes (12): _fade_slate(), test_a_mixed_slate_is_ok(), test_all_home_ncaaf_slate_is_flagged_without_mlb_hardcoding(), test_all_unders_public_fade_risk_is_crit(), test_all_unders_public_fade_slate_is_crit(), test_fade_in_the_model_id_is_sport_agnostic(), test_thin_slate_is_not_a_finding(), test_unanimous_but_small_slate_is_warn_not_crit() (+4 more)

### Community 439 - "tests/test_team_stats_asof_invariants.py"
Cohesion: 0.14
Nodes (11): build_rows(), _game(), test_a_row_never_includes_its_own_date(), test_counts_accumulate_across_dates(), test_every_emitted_column_exists_in_the_real_table(), columns_of(), test_every_sport_uses_its_own_scoring_noun(), test_home_and_away_splits_use_only_the_relevant_games() (+3 more)

### Community 440 - "CLV off DraftKings line tests"
Cohesion: 0.14
Nodes (7): _Conn, _Res, test_a_pick_draftkings_never_hung_closes_at_the_bet_book(), test_a_row_that_carries_dk_odds_keeps_its_book_and_price(), test_the_backfill_queues_the_dates_of_those_picks(), test_without_pinnacle_the_primary_is_still_the_bet_book(), _ts()

### Community 441 - "docs/sports: ufc + golf"
Cohesion: 0.17
Nodes (12): GOLF — retired 2026-09-08, kept as the revival runbook, DataGolf Scratch Plus as the sole golf source (not The Odds API), Five golf models (outright, top10, top20, make_cut, matchup), One games row per tournament, per-player picks FK to it (the MLB-prop pattern), Golf settlement: ties settle at full price as a win (v1), WD-before-cut NO_ACTION, UFC — pipeline operations (ufc.md), ufc_moneyline CalErr 5.99% above the 5% gate; a retrain will not move it, Primary UFC data path is the Greco1899 CSV mirror (ufcstats behind Cloudflare) (+4 more)

### Community 442 - "tests/test_batter_prop_log_pin.py"
Cohesion: 0.10
Nodes (10): build_batter_scoring_rows(), _log_sql(), _Rec, _ScoringConn, test_batter_log_scan_is_pinned_to_the_lookback_not_the_catalog(), test_five_models_share_one_log_load(), test_no_lineup_does_not_scan_the_log(), test_starter_log_inside_the_batter_loader_uses_the_same_floor() (+2 more)

### Community 443 - "tests/test_opp_starter_features.py"
Cohesion: 0.12
Nodes (13): _opp_starter_savant(), _starter_gb_pct(), _batter_bulk(), test_batter_bulk_carries_everything_opp_starter_savant_reads(), test_it_reads_the_starters_savant_row(), test_live_mode_falls_back_to_prior_season(), test_live_mode_prefers_the_current_season(), test_opp_starter_savant_reads_real_values_off_the_real_loader() (+5 more)

### Community 444 - "mobile/docs/BILLING.md"
Cohesion: 0.18
Nodes (10): Billing runbook (IAP via RevenueCat, Stripe dark), BILLING_ENABLED kill switch, IAP entitlement flow (configure -> purchase -> webhook -> subscriptions), has_app_access() supersedes has_active_subscription(), isEntitled() checks status AND period end, PaywallScreen (localized prices, restore, redeem), RevenueCat SDK and entitlement 'signals', scripts/verify_billing.ts (83 assertions) (+2 more)

### Community 445 - "NFL CLV backtest and feature build"
Cohesion: 0.10
Nodes (14): add_form(), build(), feature_columns(), market_features(), team_game_stats(), fmt(), main(), ShrunkEnsemble (+6 more)

### Community 446 - "tests/test_merge_mlb_twin_games.py"
Cohesion: 0.13
Nodes (12): apply_one(), canonical(), counts(), main(), plan(), _Conn, test_a_canonical_id_maps_to_nothing(), test_a_non_mlb_or_malformed_id_is_left_alone() (+4 more)

### Community 447 - "supabase/functions/discord-link/index.ts"
Cohesion: 0.24
Nodes (15): accessFor(), admin, handleComplete(), handleStart(), handleStatus(), handleUnlink(), hmac(), issueState() (+7 more)

### Community 448 - "tests/test_discord_channel_probe.py"
Cohesion: 0.17
Nodes (7): _Resp, test_the_probe_covers_the_per_sport_live_channels(), test_the_probe_never_posts_and_never_returns_the_url(), test_the_probe_reports_the_channel_behind_each_sport(), _get(), test_two_sports_sharing_a_channel_are_flagged(), _job_discord_probe()

### Community 449 - "tests/test_nfl_prop_clv.py"
Cohesion: 0.16
Nodes (9): _assign(), _book_from_label_fn(), _fn(), test_the_book_is_read_from_the_label_suffix(), test_the_closing_prop_lookup_defaults_to_draftkings_and_binds_the_book(), test_the_label_book_map_is_the_inverse_of_both_cards(), test_the_map_test_no_longer_excludes_nfl(), test_the_market_relative_rules_take_their_market_from_the_row() (+1 more)

### Community 450 - "tests/test_prune_keeps_the_close.py"
Cohesion: 0.16
Nodes (8): test_both_delete_tiers_spare_the_keep_set(), test_each_tier_uses_exactly_one_anti_join(), test_the_close_is_never_an_in_play_price(), test_the_close_is_selected_by_the_newest_snapshot(), test_the_cost_is_recorded_as_a_measurement_not_a_guess(), test_the_opener_is_still_selected_by_the_oldest(), test_the_protected_books_are_untouched_by_this_change(), _tier()

### Community 452 - "tests/test_scoring_methods.py"
Cohesion: 0.13
Nodes (7): _generic(), test_a_generic_model_is_never_declared_rule_or_engine(), test_accessor_defaults_to_artifact(), test_every_classified_model_carries_thresholds(), test_mlb_live_total_runs_is_artifact_backed(), test_rule_based_models_never_appear_in_a_feature_map(), test_the_map_covers_exactly_the_non_generic_models()

### Community 453 - ".claude/agents: frontend-ux-designer + CLAUDE"
Cohesion: 0.20
Nodes (8): frontend-ux-designer agent, Mobbin MCP connector — the only reference route, Signalbase — the iOS app in mobile/, ux_scan.mts — the deterministic front-end scan, /graphify trigger — use the installed graphify skill, /ux-review command, CLAUDE.md — Betting Model Project Context, Matt — product area leader

### Community 454 - ".claude/rules/picks-and-publishing.md"
Cohesion: 0.24
Nodes (4): The lock flags: LOCK_GAME_PICKS_AT_FIRST_RUN, LOCK_PROP_PICKS_AT_FIRST_SIGNAL, LOCK_LIVE_PICKS_AT_FIRST_SIGNAL, picks-and-publishing.md — path-scoped rule file, The pytest non-integration subset, tests/test_context_budget.py polices CLAUDE.md size

### Community 456 - "Mobile bankroll tests"
Cohesion: 0.23
Nodes (13): _read(), test_copy_is_word_for_word(), test_display_only_nothing_sized(), test_error_text_uses_the_text_safe_red(), test_explainer_no_longer_denies_a_bankroll(), test_exposure_card_hook_and_banner_stay_removed(), test_keyboard_never_covers_the_field(), test_locale_separators_decide_the_decimal() (+5 more)

### Community 457 - "NCAAF outcome edge scan"
Cohesion: 0.19
Nodes (12): _cell(), ecdf_prob_positive(), implied(), load_ml_prices(), main(), payout(), predict_all(), _print_cells() (+4 more)

### Community 458 - "Live monitor dashboard cache and docs"
Cohesion: 0.17
Nodes (9): age(), cached(), clear(), test_cache_raises_when_it_has_nothing_to_fall_back_on(), test_cache_reports_age(), test_cache_serves_stale_rather_than_failing(), boom(), test_cache_serves_within_ttl_and_recomputes_after() (+1 more)

### Community 459 - "docs/signal_timing.md"
Cohesion: 0.18
Nodes (8): Signal-timing analysis — the pick lock (signal_timing.md), Does the daily pick lock cost us signals? (2026-08-23), MAX_EDGE_CAP blind spot: games with no row at all, A model re-run harness over stored snapshots (open item), Four NONE-row coverage traps, Prop NONE/AVOID rows are a survivor sample (poller clear), The pre-game line poller wipes a game's non-BET prop picks (known issue), The lock is signal-aware for NCAAF only (NONE rows refreshed, BETs lock at first cross)

### Community 460 - "scripts/ncaaf_search/situational_spots.py"
Cohesion: 0.11
Nodes (9): is_bowl_game(), build_spots(), evaluate(), load_team_games(), main(), wilson(), load_data(), main() (+1 more)

### Community 461 - "mobile/docs/DISCORD_LINKING.md"
Cohesion: 0.23
Nodes (11): Discord linking runbook: one membership, two surfaces, Migration add_discord_link_and_whop_memberships.sql, DISCORD_LINK_ENABLED flag, discord_links table, Connect Discord flow (start -> consent -> complete -> role sync), public.my_access() computes access on every read, useAccess access state hook, scripts/verify_discord_link.ts (44 assertions) (+3 more)

### Community 463 - "Monitoring server tests"
Cohesion: 0.08
Nodes (27): _drain(), _enqueue(), _flush_on_exit(), install(), instrumented(), _now(), _patch_curl_cffi(), instrumented() (+19 more)

### Community 464 - "NCAAF gameday cadence tests"
Cohesion: 0.12
Nodes (6): gameday_mod(), test_credit_cap_covers_a_full_saturday_at_the_configured_cadence(), test_idle_cadence_is_slower_than_the_live_cadence(), test_kickoffs_already_past_are_not_counted_as_upcoming(), test_state_cadence_is_fast_enough_to_react_to_a_drive(), test_the_effective_odds_cadence_is_bounded_by_the_pass()

### Community 465 - "nfl/scripts/backtest_opener.py"
Cohesion: 0.24
Nodes (9): boot(), by_season(), exp_win(), load(), main(), price(), report(), residuals() (+1 more)

### Community 466 - "Mobile player detail tests"
Cohesion: 0.17
Nodes (12): _read(), test_every_player_page_read_names_its_relation_literally(), test_next_game_is_earliest_in_the_window_not_tonights_date(), test_results_are_units_never_dollars_and_never_paper(), test_sharp_gap_is_no_vig_vs_no_vig(), test_the_book_line_to_threshold_conversion_is_the_boards(), test_the_chart_follows_the_posted_line_until_the_reader_moves_it(), test_the_hook_is_plain_effects_only() (+4 more)

### Community 467 - "MLB retrain freeze tests"
Cohesion: 0.13
Nodes (9): assert_retrain_allowed(), test_import_time_flag_follows_marker_file(), test_marker_or_env_lifts_the_freeze(), test_mlb_prop_market_sweep_is_documented_exempt(), test_mlb_retrain_refused_while_incomplete(), test_mlb_threshold_sweeps_call_the_guard(), test_non_mlb_sports_are_not_gated(), test_repo_marker_file_is_present() (+1 more)

### Community 468 - "tests/test_latest_odds_views.py"
Cohesion: 0.25
Nodes (13): _app_columns(), _function(), test_every_log_table_has_its_insert_trigger_and_the_odds_tables_an_update_trigger(), test_every_view_reads_its_state_table_and_never_the_log(), test_no_pending_view_migration_re_creates_these_views_over_the_log(), test_the_dk_view_returns_the_apps_columns_in_order(), test_the_exclusions_survived_the_move(), test_the_game_view_returns_the_apps_columns_in_order() (+5 more)

### Community 469 - "Multi-book odds tests"
Cohesion: 0.10
Nodes (12): _odds_query(), _prop_markets(), test_a_game_with_no_commence_time_keeps_every_row(), test_draftkings_is_always_first_line_shop_book(), test_prop_bookmaker_defaults_to_draftkings(), test_prop_rows_are_stamped_with_their_bookmaker(), test_prune_identity_matches_the_all_books_views(), test_prune_never_touches_the_scoring_book() (+4 more)

### Community 470 - "Threshold review DDL tests"
Cohesion: 0.12
Nodes (4): _DdlConn, _DdlRes, test_a_failed_lock_down_does_not_lose_the_table(), test_ensure_schema_commits_the_tables_it_creates()

### Community 471 - "tests/test_model_game_savepoint.py"
Cohesion: 0.15
Nodes (4): _games(), _PoisonConn, test_a_best_price_timeout_is_the_logged_error_and_the_next_lookup_runs(), test_a_model_sql_error_does_not_poison_the_next_model()

### Community 472 - "NBA schedule ingestor and tests"
Cohesion: 0.23
Nodes (10): ot_periods(), schedule_rows(), _tv(), _row(), test_a_late_west_coast_tip_keeps_its_eastern_date(), test_an_undecided_playoff_slot_is_skipped(), test_game_type_is_read_from_the_first_three_digits(), test_overtime_periods_come_from_the_status_text() (+2 more)

### Community 473 - "tests/test_nfl_prop_settle_name_fallback.py"
Cohesion: 0.27
Nodes (10): _never(), _row(), test_a_first_name_the_stat_log_spells_differently_still_matches(), test_a_scratched_player_is_not_graded_on_a_teammate_with_his_initial(), test_a_spelling_the_log_already_knows_is_a_scratch_not_a_spelling(), test_another_game_and_another_initial_never_match(), test_first_name_rule(), test_two_candidates_is_a_miss_not_a_guess() (+2 more)

### Community 474 - "NFL recap waits for box scores tests"
Cohesion: 0.17
Nodes (8): _daily(), _job_body(), test_a_malformed_date_is_refused_before_anything_runs(), test_nfl_box_scores_are_ingested_before_settle(), test_nfl_finals_still_precede_the_box_scores(), test_the_job_does_not_read_rowcount_off_the_cursor(), test_the_job_only_clears_its_own_two_ledger_kinds(), test_the_job_posts_both_surfaces_through_the_ordinary_paths()

### Community 475 - "Results recap backfill"
Cohesion: 0.20
Nodes (8): build_parser(), _date_is_over(), main(), post_backfill(), test_a_day_that_is_not_over_is_refused(), test_apply_calls_both_notifiers_for_that_date(), test_dry_run_is_the_default_and_posts_nothing(), test_main_dry_run_prints_and_returns()

### Community 476 - "tests/test_transaction_pooler.py"
Cohesion: 0.19
Nodes (8): _transaction_endpoint(), test_a_direct_connection_is_left_alone(), test_a_local_postgres_is_left_alone(), test_a_supabase_session_url_becomes_the_transaction_url(), test_it_is_idempotent(), test_only_the_port_changes(), test_the_escape_hatch_works(), test_the_job_queue_still_gets_session_mode()

### Community 477 - "NHL prop settlement tests"
Cohesion: 0.21
Nodes (6): _bet(), _in_goal(), _result(), _Shim, _skated(), TestSettlement

### Community 478 - "CFBD refresh and backfill tests"
Cohesion: 0.14
Nodes (9): backfill_ncaaf(), refresh_ncaaf_games(), refresh_ncaaf_stats(), _NullConn, test_backfill_returns_totals_when_every_season_succeeds(), test_backfill_survives_a_mid_run_season_failure(), test_refresh_games_happy_path_counts_games(), test_refresh_games_repairs_every_season_and_reports_failures() (+1 more)

### Community 479 - "docs/live_betting.md"
Cohesion: 0.18
Nodes (13): The live calibration map: 126 of 150, and it does not close, BookMoveClock — the book has moved past a cap while our state has not changed, LOCK_LIVE_PICKS_AT_FIRST_SIGNAL — the first live BET per lane is the bet of record, The live staleness guards (data/live_quote_guard.py), Live (in-play) betting — pipeline operations, Live cutoffs are re-derived every pass (tracking/live_calibration.py), LIVE_MAX_BETS_PER_WEEK is advisory, not a runtime cap, config.LIVE_MODELS — a separate registry from MODELS (+5 more)

### Community 480 - "Team stats as-of invariant tests"
Cohesion: 0.14
Nodes (9): seasons_with_too_few_snapshots(), test_a_real_series_passes(), test_a_single_snapshot_season_is_flagged(), test_a_two_snapshot_season_is_flagged(), test_mlb_twin_alias_map_matches_sbr_canon(), test_ncaaf_shaped_weekly_snapshots_pass(), test_snapshot_grace_is_opening_night_not_a_finished_season(), test_the_guard_is_wired_so_protected_seasons_are_REMOVED() (+1 more)

### Community 481 - "mobile/tsconfig.json"
Cohesion: 0.13
Nodes (14): compilerOptions, esModuleInterop, jsx, module, moduleResolution, noUncheckedIndexedAccess, paths, resolveJsonModule (+6 more)

### Community 482 - "tests/test_promote_external.py"
Cohesion: 0.16
Nodes (5): promote_external(), _Conn, test_external_promotion_refuses_a_map_that_does_not_transfer(), test_external_promotion_writes_only_the_promoted_columns(), test_the_scorer_reads_the_external_map_like_any_promoted_one()

### Community 483 - "NBA injury report slot schedule"
Cohesion: 0.15
Nodes (12): _all_slots(), _ampm(), new_slot(), old_slot(), pre_tip_slot(), report_url(), slots_for_date(), test_format_switch_is_measured_and_both_are_probed_around_it() (+4 more)

### Community 484 - "Declared worker job validation tests"
Cohesion: 0.15
Nodes (7): _declared(), test_an_explicit_run_date_must_be_a_real_iso_date(), test_declared_keys_are_unique(), test_every_declared_job_names_a_registered_type(), test_every_declared_job_validates(), test_no_run_date_means_the_module_resolves_it(), test_the_validator_drops_unknown_args()

### Community 485 - "Local store cache and NFL prop shape simulation"
Cohesion: 0.09
Nodes (27): activate(), available(), _manifest(), _path(), read_table(), status(), _write_manifest(), write_table() (+19 more)

### Community 486 - "tests/test_pipeline_report_rollback.py"
Cohesion: 0.20
Nodes (4): _rows(), _Conn, test_a_failed_query_rolls_back(), test_one_broken_section_does_not_break_the_rest()

### Community 487 - "supabase/functions/sharpsports/index.ts"
Cohesion: 0.30
Nodes (13): admin, americanFromBetSlip(), asArray(), cors, createContext(), isSettled(), json(), pick() (+5 more)

### Community 488 - "NBA lineup stint derivation"
Cohesion: 0.05
Nodes (46): _games(), _schedule(), _accumulate(), _add_one(), _and_one_follows(), appearances(), _athletes(), _blank() (+38 more)

### Community 489 - "NFL pick monitor game id tests"
Cohesion: 0.16
Nodes (3): eval_row(), _picks_game_id(), TestTheJoinKeyMatchesPicks

### Community 490 - "Pregame line poller change detection"
Cohesion: 0.19
Nodes (11): changed_rows(), _row(), test_a_link_or_selection_id_churning_is_not_a_change(), test_a_moved_price_is_written_and_marks_its_game(), test_a_moved_total_counts_even_when_the_price_holds(), test_a_quote_we_have_never_seen_counts_as_changed(), test_an_unchanged_quote_is_not_written(), test_in_play_rows_are_ignored() (+3 more)

### Community 491 - "MLB game market and public fade cards"
Cohesion: 0.09
Nodes (19): load_latest_quotes(), _better_under(), edge_floor(), load_public_over_splits(), max_per_slate(), _price_in_window(), publish_enabled(), rank_kind() (+11 more)

### Community 492 - "NFL model bundle restore docs"
Cohesion: 0.16
Nodes (11): Multi-layered leakage detection, The Odds API historical backfill (bet-time Tuesday 18:00 UTC; closing 10 min before kickoff clusters), The canonical write-up nfl_game_lines_model_system.md, nfl/requirements.txt dependency set (pandas, numpy, pyarrow, requests, scipy, scikit-learn, lightgbm), NFL model bundle restore instructions, data/credit_ledger.json spend/quota ledger, data/odds_cache/ keyed md5(date|regions|markets), data/raw/pbp_20XX.parquet not bundled; refetch from nflverse-data releases (+3 more)

### Community 493 - "Pipeline watch and burn alerts"
Cohesion: 0.04
Nodes (39): collect(), _Conn, test_a_clean_pass_produces_no_finding(), test_a_clean_run_still_posts(), test_a_confirmed_post_is_ledgered_so_the_run_can_be_verified(), test_a_failed_ledger_does_not_lose_the_report(), execute(), test_a_failed_query_rolls_back_and_does_not_sink_the_run() (+31 more)

### Community 494 - "Discord link and Whop memberships"
Cohesion: 0.16
Nodes (14): discord_links, idx_discord_links_discord_user, idx_discord_links_email, idx_whop_memberships_discord, idx_whop_memberships_email, idx_whop_memberships_valid, public.app_subscription_access_for(), public.discord_access_for() (+6 more)

### Community 495 - "tests/test_worker_deps.py"
Cohesion: 0.22
Nodes (4): _requirements(), test_dashboard_packages_are_not_on_the_worker(), test_only_the_dashboard_imports_them(), test_the_worker_asks_for_the_cpu_build_of_xgboost()

### Community 496 - "Mobile package manifest"
Cohesion: 0.25
Nodes (8): scripts, android, build:ios:preview, build:ios:production, ios, start, typecheck, web

### Community 497 - "Pitcher prop feature rows"
Cohesion: 0.12
Nodes (6): _build_pitcher_row(), _opp_team_disc(), _opp_team_stat(), _pitcher_rolling_all(), _pitcher_savant(), _ump_bb_plus_minus()

### Community 499 - "Price floor and prop pick decisions"
Cohesion: 0.06
Nodes (17): min_odds_for(), _blocked_by_min_odds(), _calibrated(), _decide(), _make_prop_pick(), _missing_price(), test_a_pick_with_no_price_is_never_blocked_by_the_floor(), test_an_explicit_floor_wins_in_BOTH_directions() (+9 more)

### Community 500 - "docs/sports/wnba.md"
Cohesion: 0.21
Nodes (13): NBA — pipeline operations (nba.md), Double-double is logistic, over-only, prob-only (COMPUTE_DD sentinel), NBA: 10 models live (moneyline + 9 props), O/U and spread blocked, NBA pipeline steps (odds, prop odds, stats local, scoring, settlement), stats.nba.com blocks datacenter IPs; team stats run on the local Task Scheduler job, WNBA — pipeline operations (wnba.md), WNBA results from the ESPN hidden API with core-API fallback, The wnba_over_under / wnba_spread sweep was leaked (latest snapshot had no pre-tipoff cutoff) (+5 more)

### Community 501 - "NFL live pick writer refusals"
Cohesion: 0.12
Nodes (7): _Conn, test_a_pass_is_never_written_to_picks(), test_an_unresolvable_decision_writes_nothing(), test_game_id_resolves_from_the_book_s_team_names(), test_picks_recorder_drops_a_pass_attempt_over_before_sql(), test_the_announce_runs_after_the_commit_and_after_the_connection_closes(), commit()

### Community 502 - "NFL stale card file tests"
Cohesion: 0.15
Nodes (9): card_path(), clear_card(), _load_script(), nfl_path(), test_a_dry_run_leaves_the_card_alone(), test_a_priced_wind_run_with_no_bets_removes_the_earlier_card(), test_clear_card_removes_todays_file_and_only_that(), test_the_path_cleared_is_the_path_the_publisher_reads() (+1 more)

### Community 503 - "scripts/ncaaf_search/weather_totals.py"
Cohesion: 0.23
Nodes (6): build_spots(), evaluate(), load_games(), main(), scoring_by_wind(), wilson()

### Community 504 - "Anon grants admin script"
Cohesion: 0.18
Nodes (7): write_verbs_for(), _function_plan(), _function_signature(), main(), _table_exists(), test_write_verbs_for_keeps_exactly_what_a_writable_relation_declares(), test_write_verbs_for_revokes_everything_on_a_read_only_relation()

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
Nodes (79): american_to_decimal(), cover_probs(), ev_per_unit(), fit_margin_pmf(), kelly_fraction(), margin_pmf_for(), add_model_mu(), load() (+71 more)

### Community 510 - "Trainer no-register tests"
Cohesion: 0.12
Nodes (9): not_registering(), registering(), test_a_normal_run_DOES_register(), test_baseline_artifacts_are_not_committable(), test_baseline_runs_write_somewhere_else(), test_default_is_to_register(), test_no_register_opens_no_database_connection(), _explode() (+1 more)

### Community 511 - "Prop lookahead window tests"
Cohesion: 0.17
Nodes (4): _get_events(), _events_src(), TestTheOddsFetchReachesTomorrow, TestTheScorerReachesTomorrow

### Community 512 - "tests/test_savant_freshness.py"
Cohesion: 0.14
Nodes (5): test_rows_are_stamped_with_a_capture_date(), test_savant_has_a_schedule(), test_the_insert_persists_the_stamp(), test_the_savant_job_belongs_to_the_pipeline_service(), test_the_stamp_defaults_rather_than_being_required_at_call_sites()

### Community 513 - "tests/test_scorer_nfl_prop_like_escape.py"
Cohesion: 0.23
Nodes (9): _between(), _broken_per_game_sql(), _first_sql(), _per_game_sql(), _sweep_sql(), test_escape_tripwire_is_on_the_pr_ci_subset(), test_live_per_game_clear_interpolates_with_one_game_id(), test_live_sweep_clear_interpolates_with_date_horizon_now() (+1 more)

### Community 514 - "Global EV floor and honest EV"
Cohesion: 0.04
Nodes (36): expected_value(), min_ev_for(), Gate, honest_probability(), test_ncaaf_live_ev_floor_is_wired_from_config(), _built(), floor_030(), identity_maps() (+28 more)

### Community 515 - "Run ledger health tests"
Cohesion: 0.07
Nodes (4): db(), mlb_wired(), _Shim, TestRunLedger

### Community 516 - "Pipeline run ledger"
Cohesion: 0.24
Nodes (5): roll_up(), _abort_orphans(), abort_prior_refresh_orphans(), _boot_cutoff(), _now()

### Community 518 - "NHL blocked shots settlement tests"
Cohesion: 0.27
Nodes (5): _bet(), _played(), _result(), _Shim, TestSettlement

### Community 519 - "Monitoring server tests"
Cohesion: 0.05
Nodes (30): configured(), guild_stats(), _credits_from(), classify(), paid_apis(), _get(), http_server(), live_server() (+22 more)

### Community 520 - "NCAAF opener strategy experiments"
Cohesion: 0.23
Nodes (7): experiment_bands(), experiment_crossbook(), experiment_model(), _load_cross_book(), main(), _open_features(), wilson_ci()

### Community 522 - "CLV no-vig capture tests"
Cohesion: 0.20
Nodes (8): _fn(), test_a_missing_bet_book_close_is_not_filled_from_another_book(), test_backfill_revisits_anything_that_is_not_standard_v2(), test_capture_grades_raw_same_book_and_a_separate_pinnacle_edge(), test_capture_stamps_method_and_close_book(), test_game_close_never_falls_back_past_first_pitch(), test_pinnacle_is_a_second_lookup_not_the_headline_close(), test_prop_close_stays_bounded_at_first_pitch()

### Community 523 - "mobile/docs/AUTHENTICATION.md"
Cohesion: 0.24
Nodes (12): Authentication runbook (built, switched off), App Store guideline 4.8: Google on iOS requires Apple, AUTH_ENABLED kill switch, signalbase://auth-callback redirect URL, billingReady() requires AUTH_ENABLED, discordLinkReady() requires AUTH_ENABLED, RLS pre-flight: authenticated keeps full read access, SignInScreen (SignIn route) (+4 more)

### Community 524 - "NBA injury report scope dates"
Cohesion: 0.33
Nodes (3): scope_dates(), _DatesConn, test_scope_is_every_game_date_and_the_day_before_newest_first()

### Community 525 - "Paused model assessment tests"
Cohesion: 0.15
Nodes (6): _rows(), test_a_cell_below_the_floor_is_not_a_result(), test_it_sweeps_both_pause_registers(), test_the_era_check_is_applied_to_every_candidate(), test_the_grade_reports_a_lower_bound_not_just_a_headline(), test_units_are_none_when_the_pick_carries_no_price()

### Community 526 - "MLB in-play game state alignment"
Cohesion: 0.24
Nodes (6): GameClock, _t(), test_before_first_pitch_and_after_last_play_are_not_priced(), test_between_pas_across_third_out_rolls_over_to_next_half(), test_mid_plate_appearance_is_that_pa_before_state(), test_plays_without_times_are_ignored()

### Community 527 - "Prop alternate line fetch tests"
Cohesion: 0.14
Nodes (9): _Resp, test_a_422_retries_without_the_alternates_before_going_dk_only(), fake_get(), test_a_422_with_no_alternates_still_takes_the_dk_only_retry(), fake_get(), test_a_rejected_football_alternate_chunk_costs_only_itself(), fake_get(), test_football_live_slate_requests_alternates_and_a_backfill_does_not() (+1 more)

### Community 528 - "NCAAF steam lag study"
Cohesion: 0.27
Nodes (9): attach_scores(), build_events(), fmt(), grade(), lines_at_pulls(), load(), main(), summarise() (+1 more)

### Community 529 - "tests/test_clear_unauthorized_auto_pauses_migration.py"
Cohesion: 0.19
Nodes (6): _stmts(), test_clearing_auto_pauses_did_not_park_batter_runs(), test_it_clears_the_whole_auto_pause_table(), test_it_does_not_touch_picks_thresholds_or_the_review_ledger(), test_it_no_ops_when_the_table_is_missing_or_already_empty(), test_migration_is_one_statement()

### Community 530 - "tests/test_ncaaf_se_louisiana_alias_migration.py"
Cohesion: 0.15
Nodes (4): test_a_pick_is_never_deleted_and_never_regraded(), test_it_guards_on_both_names_and_both_still_unscored(), test_migration_is_one_statement(), test_odds_move_only_when_canonical_has_none()

### Community 532 - "tests/test_overnight_polling.py"
Cohesion: 0.24
Nodes (7): _hours(), _jobs(), _match(), test_every_hour_of_the_day_is_covered(), test_the_overnight_pass_is_the_ordinary_one(), test_the_overnight_window_exists(), test_the_windows_do_not_overlap()

### Community 533 - "NFL wind card book filter tests"
Cohesion: 0.07
Nodes (10): test_the_decisions_ledger_is_worker_only_and_created_behind_the_guard(), test_a_replay_never_prices_off_todays_ladder_even_when_on(), test_the_card_does_not_price_off_kalshi_until_it_is_graded(), _attach(), books(), card(), _quote(), TestTheCardFilters (+2 more)

### Community 534 - "Prop no-bet row survival tests"
Cohesion: 0.07
Nodes (9): _Board, _Clock, _fake_datetime_class(), _game(), _iso(), _PollConn, test_the_poller_keeps_prop_no_bet_rows_the_refresh_pass_still_clears(), test_the_poller_tells_the_scorer_to_leave_prop_rows_alone() (+1 more)

### Community 535 - "tests/test_revoke_remaining_grants.py"
Cohesion: 0.15
Nodes (6): test_it_asserts_the_app_write_surface_survives(), test_it_revokes_every_write_privilege(), test_select_is_never_revoked(), test_the_roles_are_named_never_public(), test_the_runners_transaction_stripping_leaves_the_do_block_intact(), test_the_set_is_computed_from_the_policy_rule_not_listed()

### Community 536 - "Mobile bankroll storage"
Cohesion: 0.23
Nodes (12): check(), eq(), fakeStore(), interleaving(), slowStore(), storage(), createBankrollStore(), KeyValueStore (+4 more)

### Community 537 - "tests/test_live_slate_midnight.py"
Cohesion: 0.18
Nodes (7): _discover_active_games(), _game_id_from_statsapi(), test_a_game_seen_twice_is_polled_once(), test_discovery_asks_statsapi_about_every_date_it_is_given(), fake_schedule(), test_discovery_still_accepts_a_bare_string(), test_one_broken_date_does_not_lose_the_other()

### Community 538 - "tests/test_nhl_stats_ingestor.py"
Cohesion: 0.38
Nodes (9): parse_nhl_game(), _g(), test_arizona_folds_into_utah(), test_missing_teams_returns_none(), test_ot_home_win_is_regulation_draw(), test_preseason_game_skipped(), test_regulation_home_win(), test_scheduled_game_has_no_scores() (+1 more)

### Community 541 - "NFL odds cache import"
Cohesion: 0.24
Nodes (7): game_index(), main(), resolve(), rows_from_file(), stored_pairs(), stored_served(), _ts()

### Community 542 - "ncaaf_live/tests/test_cfbd_yardline.py"
Cohesion: 0.21
Nodes (6): _abbrev_fits(), _parse_yardline(), _cfbd_game(), test_cfbd_state_carries_the_yardline_and_the_raw_situation(), test_cfbd_yardline_from_every_stored_situation(), test_cfbd_yardline_refuses_rather_than_guesses()

### Community 545 - "NCAAF search opener cache"
Cohesion: 0.23
Nodes (7): build_opener_cache(), coverage_report(), fetch_season(), _headers(), main(), _norm(), to_frame()

### Community 546 - "tests/test_claude_rules_split.py"
Cohesion: 0.18
Nodes (4): test_claude_md_still_points_at_the_rules_directory(), test_every_rule_file_actually_carries_rules(), test_every_rule_file_is_path_scoped(), test_no_rule_was_lost_when_the_split_happened()

### Community 547 - "tests/test_db_setup.py"
Cohesion: 0.23
Nodes (6): _get_columns(), test_games_table_columns(), test_injuries_table_columns(), test_odds_table_columns(), test_picks_table_columns(), test_schema_is_idempotent()

### Community 548 - "tests/test_dedupe_opening_signals.py"
Cohesion: 0.10
Nodes (9): test_a_graded_row_is_never_deleted(), test_a_row_with_computed_clv_is_never_deleted(), test_every_field_that_defines_the_bet_must_agree(), test_it_is_dry_run_by_default(), test_the_delete_selects_through_the_same_gates(), test_the_pair_must_be_an_old_shape_new_shape_pair(), test_the_report_and_the_delete_share_one_definition(), test_the_row_kept_is_the_one_locked_earlier() (+1 more)

### Community 549 - "Multi-book odds pregame cutoff tests"
Cohesion: 0.20
Nodes (3): _OddsConn, test_the_cutoff_is_the_19_char_utc_prefix(), test_the_ufc_sibling_lookup_is_bounded_too()

### Community 550 - "tests/test_every_named_book_is_fetched.py"
Cohesion: 0.18
Nodes (5): _param_books(), test_a_sharp_reference_is_never_also_a_soft_book(), test_every_bettable_book_can_be_named_to_a_human(), test_every_named_book_is_in_the_pull_that_serves_it(), test_the_nfl_backfill_defaults_to_the_live_pull()

### Community 551 - "NHL blocked shots card tests"
Cohesion: 0.19
Nodes (4): pick_rows(), _scored(), TestTheCard, execute()

### Community 552 - "tests/test_pbp_backfill_resilience.py"
Cohesion: 0.24
Nodes (6): _backfill_body(), test_a_failed_game_rolls_the_connection_back(), test_a_run_that_wrote_nothing_reports_an_error_not_a_success(), test_errors_are_counted_not_just_logged(), test_partial_failures_are_surfaced_too(), test_the_rollback_cannot_itself_raise()

### Community 553 - "NCAAF starter-out study"
Cohesion: 0.27
Nodes (8): build_sample(), grade(), _line(), load_qb_log(), main(), report(), starter_status(), wilson()

### Community 555 - "App read surface tests"
Cohesion: 0.17
Nodes (7): all_readable(), _app_relations(), test_every_relation_the_app_reads_is_declared(), test_everything_declared_writable_is_also_readable_or_deliberately_not(), test_lock_down_sql_refuses_every_table_the_app_reads(), test_the_manifest_does_not_grow_stale_entries(), test_the_worker_only_tables_are_not_also_declared_app_readable()

### Community 558 - "docs/health_checks.md"
Cohesion: 0.24
Nodes (10): Model artifacts: present, tracked, loadable, model_artifacts_load counts what it opened, model_artifacts table fallback restore, Three separate artifact questions, three separate failures, Daily system health check + retrain workflow, KNOWN_UNTRAINED — config models intentionally without artifacts, Pipeline-observability checks: refresh_pass_completion, refresh_pass_steps, signal_delivery, pick_label_integrity, pipeline_runs — the run ledger (tracking/run_ledger.py) (+2 more)

### Community 559 - "Prop training dataset builders"
Cohesion: 0.18
Nodes (6): _all_pitcher_rows(), _build_bulk_batter_lookups(), _build_bulk_prop_lookups(), build_pitcher_scoring_rows(), build_prop_training_dataset(), _ip_to_decimal()

### Community 560 - "docs/retrain_2026_plan.md"
Cohesion: 0.18
Nodes (12): Paused model profitability assessment, scripts/paused_model_assessment, F5 O/U and F5 RL paused: leak-mismatched, synthetic-line trained, NCAAF in-play season replay: -3.4% and -13.1%, No model has a cut that clears on the deployed artifact, 2026 retrain plan: red MLB prop models, data.ingestors.baseball_savant_ingestor, batter_sb: opp_team_sb_allowed feature (+4 more)

### Community 561 - "Brand avatar and connection probes"
Cohesion: 0.09
Nodes (20): main(), scram_stored_key(), discover(), fetch_all(), _get_image(), main(), _original_size(), store() (+12 more)

### Community 562 - "mobile/scripts/verify_stats_filter_ux.ts"
Cohesion: 0.18
Nodes (9): chip, lineOnlyFn, playersDay, ROOT, sportReset, stats, teams, teamsDay (+1 more)

### Community 563 - "NFL prop backtest model and universe rate"
Cohesion: 0.05
Nodes (22): LazyConnection, american_to_profit(), backtest_model(), _bootstrap_roi_ci(), _dispersion(), _fit(), _kickoffs(), _naive_projection() (+14 more)

### Community 564 - "Feature matrix dtype coercion"
Cohesion: 0.08
Nodes (22): diff(), pitcher_diff(), diff(), pitcher_diff(), coerce_numeric_features(), feature_matrix(), numeric_feature_value(), _pct_pair() (+14 more)

### Community 566 - "NCAAF live loop timing tests"
Cohesion: 0.15
Nodes (7): _main_source(), test_an_unanswered_state_feed_does_not_look_like_the_slate_ending(), test_loop_exits_early_when_no_kickoff_is_near(), test_loop_polls_at_the_idle_cadence_when_nothing_is_live(), test_loop_sleeps_the_remainder_not_a_flat_interval(), test_loop_warns_when_a_pass_overruns_its_interval(), test_odds_fetch_uses_the_odds_cadence_not_the_loop_cadence()

### Community 567 - "NFL in-play edge study helpers"
Cohesion: 0.18
Nodes (9): lagbook(), lagbook_catchup(), lagbook_groups(), pool_all(), summ(), async_check(), cp_roi(), p_null() (+1 more)

### Community 568 - "NCAAF quarterback ablation study"
Cohesion: 0.28
Nodes (7): _fit(), main(), _report(), run(), summarise(), walk_forward(), wilson()

### Community 569 - "tests/test_game_log_backfill_skip.py"
Cohesion: 0.25
Nodes (5): _backfill_body(), test_a_game_absent_from_our_games_table_is_still_skipped(), test_no_skip_is_keyed_on_date_alone(), test_the_coverage_set_is_scoped_to_the_season_being_built(), test_the_skip_is_keyed_on_game_id()

### Community 572 - "NCAAF line move spots"
Cohesion: 0.27
Nodes (6): eval_follow_spread(), eval_follow_total(), load(), main(), _summ(), wilson()

### Community 573 - "Full record post tests"
Cohesion: 0.18
Nodes (4): Conn, test_delete_targets_only_custom_post(), test_posts_once_and_ledgers(), test_standard_post_uses_given_embed_once()

### Community 574 - "tests/test_prompt_reads_thresholds.py"
Cohesion: 0.18
Nodes (4): test_the_auto_pause_lookup_fails_open(), test_the_prompt_carries_no_per_model_cut(), test_the_prompt_still_says_it_is_pasted_once(), test_the_sync_mirrors_both_pause_registers()

### Community 575 - "tests/test_system_health_meta_steps.py"
Cohesion: 0.25
Nodes (5): _meta_steps(), test_aborted_sentinel_is_excluded(), test_health_check_is_excluded(), test_model_quality_is_excluded(), test_sentinel_matches_the_writer()

### Community 576 - "tests/test_weekly_catch_up.py"
Cohesion: 0.18
Nodes (3): _Conn, test_a_failing_savant_refresh_does_not_cost_the_calibration_its_catch_up(), test_ownership_is_checked_per_job()

### Community 577 - "NBA period scores ingestor and tests"
Cohesion: 0.36
Nodes (7): parse_period_rows(), _event(), test_espn_team_codes_map_to_ours(), test_one_row_per_period_under_our_game_id(), test_overtime_periods_follow_the_fourth(), test_quarters_that_do_not_sum_to_the_final_are_skipped(), test_unfinished_games_and_mismatched_period_counts_are_skipped()

### Community 580 - "scripts/render_brand_icons.py"
Cohesion: 0.24
Nodes (3): draw_mark(), main(), render()

### Community 581 - "NFL prop lean concentration study"
Cohesion: 0.25
Nodes (7): add_context(), boot(), main(), profit(), report(), tercile_split(), under_profit()

### Community 582 - "Prop odds book update-time tests"
Cohesion: 0.26
Nodes (6): _Conn, _parse(), test_a_row_built_without_the_key_still_inserts_as_null(), test_no_clock_anywhere_is_none_not_our_fetch_time(), test_the_column_is_added_only_when_the_catalog_lacks_it(), test_the_markets_own_clock_is_stored_else_the_books()

### Community 583 - "NFL pick monitor"
Cohesion: 0.15
Nodes (10): classify(), _f(), latest_per_pick(), main(), monitor(), read_eval_rows(), _row(), TestClassify (+2 more)

### Community 584 - "Dashboard rule model tests"
Cohesion: 0.14
Nodes (5): test_a_rule_carries_a_cut_but_is_in_no_training_registry(), test_a_rule_is_not_styled_as_a_warning(), test_a_rule_sorts_with_the_live_models_not_the_broken_ones(), test_the_roster_query_flags_rules(), test_the_summary_counts_rules_apart_from_outages()

### Community 586 - "supabase/functions/stripe-webhook/index.ts"
Cohesion: 0.31
Nodes (9): admin, applySubscription(), iso(), PRICE_TO_PLAN, resolveUserId(), stripeGet(), timingSafeEqual(), toHex() (+1 more)

### Community 589 - "tests/test_mobile_neutral_signal_label.py"
Cohesion: 0.31
Nodes (7): _read(), test_explainer_names_neutral(), test_filters_and_card_speak_the_display_name(), test_model_screens_speak_the_display_name(), test_no_member_label_prints_a_raw_signal_type(), test_none_badge_reads_neutral(), test_withdrawn_pick_is_not_badged_neutral()

### Community 590 - "Mobile stat segment tests"
Cohesion: 0.24
Nodes (9): _read(), test_one_shared_defensive_set(), test_position_is_never_inferred_from_stats(), test_runs_in_pr_ci(), test_search_and_position_review_fixes(), test_segment_labels_cap_only_on_fit(), test_tabs_speak_the_visible_label_not_the_key(), test_the_category_dropdown_is_gone() (+1 more)

### Community 591 - "NFL prop opening signal cleanup tests"
Cohesion: 0.23
Nodes (6): _stmts(), test_it_deletes_exactly_the_three_measured_lock_keys(), test_it_does_not_touch_picks_or_discord(), test_it_still_skips_a_key_that_has_a_standing_bet(), test_migration_is_one_statement(), test_standing_pick_uses_lock_key_sql_not_player_id()

### Community 592 - "Live quote score clock"
Cohesion: 0.23
Nodes (5): ScoreClock, test_score_clock_ignores_a_dropped_score_field(), test_score_clock_keeps_games_independent(), test_score_clock_reports_no_event_at_first_sight(), test_score_clock_stamps_the_change_and_holds_it()

### Community 593 - "tests/test_scorer_commits_per_game.py"
Cohesion: 0.40
Nodes (8): _between(), _run_scorer_body(), test_a_lost_connection_re_runs_the_game_once_and_never_the_pass(), test_each_game_is_its_own_committed_unit(), test_no_bulk_delete_of_non_bet_rows_precedes_the_loop(), test_picks_are_only_counted_once_the_game_committed(), test_the_housekeeping_delete_is_a_sweep_after_the_loop(), test_the_outer_handler_still_records_the_failure()

### Community 595 - "Voided pick exclusion tests"
Cohesion: 0.21
Nodes (4): _Conn, _db(), test_a_voided_pick_is_not_a_free_pick_candidate(), test_a_voided_pick_is_not_a_parlay_leg()

### Community 596 - "SQL percent escaping tests"
Cohesion: 0.21
Nodes (5): _adapt(), _parameterised_sql(), test_check_line_movement_query_interpolates(), test_parameterised_sql_escapes_literal_percents(), test_the_scanner_actually_catches_the_regression()

### Community 597 - "Multi-book fallback response tests"
Cohesion: 0.20
Nodes (7): _Resp, test_a_rejected_book_list_falls_back_to_the_decision_book(), _get(), test_the_fallback_does_not_recurse_forever(), _get(), test_the_per_event_fetch_asks_for_every_book(), _get()

### Community 598 - "tests/test_live_game_state_poller.py"
Cohesion: 0.22
Nodes (7): _bases_state(), _extract_state(), test_bases_state_empty(), test_bases_state_loaded(), test_bases_state_single_runner(), test_extract_state_handles_empty_feed(), test_extract_state_pulls_fields_from_live_feed()

### Community 599 - "Wind stake calibration tests"
Cohesion: 0.22
Nodes (6): _probe(), test_an_uncalibrated_lead_is_sized_rather_than_zeroed_on_the_card(), test_at_the_default_gate_that_same_row_does_not_fire_at_all(), test_the_eval_board_agrees_with_the_card(), test_the_probability_was_already_clipping(), test_the_stake_clips_to_lead_seven_instead_of_returning_zero()

### Community 600 - "NFL prop pulled quote filter"
Cohesion: 0.32
Nodes (8): drop_pulled_quotes(), _ts(), _q(), test_a_book_on_its_own_cadence_is_not_penalised_inside_three_hours(), test_a_book_that_stopped_returning_the_game_is_dropped(), test_a_player_the_book_stopped_quoting_is_dropped(), test_a_whole_market_the_book_pulled_is_dropped(), test_rows_from_one_fetch_minutes_apart_are_kept_and_a_line_move_is_not_a_pull()

### Community 601 - "NCAAF venue feature tests"
Cohesion: 0.18
Nodes (6): _venue_features(), test_altitude_climb_is_signed_from_each_teams_own_elevation(), test_both_teams_travel_at_a_neutral_site(), test_eastward_travel_is_positive_tz_shift(), test_host_travels_zero_at_a_normal_home_game(), test_missing_venue_data_yields_nulls_not_zeros()

### Community 602 - "Feedback threads migration"
Cohesion: 0.36
Nodes (10): feedback_messages, feedback_threads, idx_feedback_messages_thread, idx_feedback_threads_device, idx_feedback_threads_status, public.feedback_messages_for_thread(), public.feedback_reply(), public.feedback_submit() (+2 more)

### Community 603 - "docs/reviews/2026-09-07-nfl-props-deep-dive.md"
Cohesion: 0.33
Nodes (7): NFL props deep dive — two lanes, one of them can't see the slate (2026-09-07), Twelve artifacts committed from a replica failed pickle.load unnoticed for two weeks, The eleven NFL projection prop models, unpaused on placeholder thresholds, nfl_prop_market: the de-vig rule (Pinnacle as truth, equal lines only), The scorer is pinned to today, the card looks ten days ahead, 112 bets on one Sunday from untuned models; 41-46% BET rates are placeholders, Eleven NFL distributional props paused 2026-09-14

### Community 604 - "NFL prop lead ceiling tests"
Cohesion: 0.30
Nodes (8): _nfl_prop_too_early(), _iso(), test_a_kickoff_beyond_the_ceiling_is_too_early(), test_a_started_or_unknown_kickoff_is_not_too_early(), test_the_boundary_is_inclusive_at_the_ceiling(), test_the_scorer_and_the_card_read_ONE_constant(), test_the_scorer_loop_actually_applies_the_ceiling(), test_the_z_suffix_parses_like_the_offset_form()

### Community 605 - "NFL prop modeling tables"
Cohesion: 0.27
Nodes (10): idx_nfl_plog_normname, idx_nfl_snaps_join, idx_nfl_snaps_season, idx_nfl_tgs_opp, idx_nfl_tgs_season, idx_nfl_tgs_team, nfl_snap_counts, nfl_team_game_stats (+2 more)

### Community 606 - "NFL prop studies and monitoring docs"
Cohesion: 0.02
Nodes (88): docs/cloud_worker.md, docs/clv.md, docs/followups.md, docs/health_checks.md, docs/mlb_market_handicap_features.md, MLB runline / over-under edge search, Hybrid Pin-agreement filter on mlb_over_under bets, mlb_spread_market 1.8pp run-line rule (+80 more)

### Community 607 - "railway.json"
Cohesion: 0.22
Nodes (8): build, builder, watchPatterns, deploy, numReplicas, restartPolicyType, startCommand, $schema

### Community 608 - "supabase/functions/sharpsports-webhook: index + index"
Cohesion: 0.25
Nodes (5): admin, internalIdFor(), pick(), admin, cors

### Community 609 - "Worker-only create site tests"
Cohesion: 0.17
Nodes (6): _call_source(), _repo_sources(), test_every_guard_on_a_worker_only_table_asks_about_rls(), test_every_literal_lock_down_target_is_declared(), test_every_worker_only_create_site_goes_through_the_gated_helper(), test_no_create_site_uses_the_ungated_builder()

### Community 610 - "NHL game logs migration"
Cohesion: 0.29
Nodes (11): idx_nhl_goalie_game_log_player_date, idx_nhl_goalie_game_log_source, idx_nhl_goalie_game_log_team_date, idx_nhl_skater_game_log_player_date, idx_nhl_skater_game_log_source, idx_nhl_skater_game_log_team_date, idx_nhl_team_game_log_source, idx_nhl_team_game_log_team_date (+3 more)

### Community 611 - "supabase/functions/revenuecat-webhook/index.ts"
Cohesion: 0.22
Nodes (3): admin, PRODUCT_TO_PLAN, RcEvent

### Community 612 - "supabase/functions/stripe-checkout/index.ts"
Cohesion: 0.31
Nodes (8): admin, cors, customerFor(), form(), json(), PRICES, stripe(), TRIAL_DAYS

### Community 613 - "supabase/functions/whop-webhook/index.ts"
Cohesion: 0.25
Nodes (4): admin, signatureValid(), timingSafeEqual(), WhopMembership

### Community 614 - "tests/test_book_list_budget.py"
Cohesion: 0.31
Nodes (4): _names(), test_every_book_the_nfl_prop_model_bets_at_is_actually_fetched(), test_the_nfl_prop_pull_is_one_group_with_both_references_in_it(), test_the_shared_list_is_one_group()

### Community 615 - "tests/test_model_quality.py"
Cohesion: 0.22
Nodes (3): _insert_open_bet(), _Shim, test_run_persists_all_unders_fade_slate_as_crit()

### Community 617 - "Model trainer and WNBA points rebuild"
Cohesion: 0.03
Nodes (56): calibration_method(), scoring_method(), build_bulk_wnba_prop_lookups(), build_wnba_prop_scoring_rows(), build_wnba_prop_training_dataset(), f(), _count_cv_splits(), _mean_calibration_error() (+48 more)

### Community 618 - "Team stats board tables"
Cohesion: 0.17
Nodes (9): public.team_stats_board(), idx_mlb_team, idx_nba_team, idx_nhl_team, idx_wnba_team, mlb_team_stats, nba_team_stats, nhl_team_stats (+1 more)

### Community 619 - "Decide on best price migration"
Cohesion: 0.23
Nodes (5): mv_scored_pick_outcomes_model_idx, mv_scored_pick_outcomes_pick_id_idx, public.v_model_full_outcome_picks, public.v_model_full_outcome_record, public.v_model_full_record

### Community 620 - "Mobile NHL look-ahead window tests"
Cohesion: 0.29
Nodes (5): _fn(), _read(), test_the_nhl_read_matches_the_other_look_aheads(), test_the_sport_chip_is_the_hook_not_an_allowlist(), test_use_today_picks_fetches_nhl_across_that_window()

### Community 621 - "NHL prop alternate line tests"
Cohesion: 0.20
Nodes (7): _book(), test_a_200_on_both_calls_merges_the_alternate_lines(), fake_fetch(), test_an_exception_on_the_alternate_call_keeps_the_featured_lines(), fake_fetch(), test_open_close_and_final_each_ask_for_the_alternate_lines(), fake_fetch()

### Community 622 - "SBR historical odds loader"
Cohesion: 0.25
Nodes (3): canonical_abbrev(), parse_csv_file(), test_sbr_abbreviations_are_canonicalised_for_mlb_only()

### Community 623 - "NBA injury report player matching"
Cohesion: 0.17
Nodes (7): match_player(), _near_season(), remap_changes(), _surname_key(), test_a_name_printed_differently_matches_on_surname_and_initial_within_the_team(), test_player_ids_match_on_team_first_then_a_unique_season_name(), test_remap_rewrites_only_names_whose_id_changed()

### Community 626 - "NHL as-of lookup tests"
Cohesion: 0.22
Nodes (4): _blk_nhl_asof(), _t(), test_the_training_path_reads_nhl_odds_by_game_not_by_sport(), TestOpeningNightIsEarlySeason

### Community 627 - "docs/market_coverage.md"
Cohesion: 0.36
Nodes (7): ncaaf_prop_odds_ingestor and its probe, test_the_mlb_board_and_the_mlb_pull_are_one_set, Prop market coverage — what the feed actually serves, MLB probe 2026-09-05 — served, unsupported and unpriced keys, NCAAF prune — FOOTBALL_MARKET_NOT_PRICED per league, scripts/probe_market_coverage.py — one market per call, writes nothing, Neither prop ingestor writes to api_call_log

### Community 628 - "One pick per event record tests"
Cohesion: 0.18
Nodes (7): duplicate_copy_exclusion_sql(), test_the_discord_recap_counts_each_event_once(), test_the_finder_skips_copies_already_marked(), test_the_marker_is_one_constant_and_one_predicate(), test_the_monitor_dashboard_box_score_arm_counts_each_event_once(), test_the_monitor_dashboard_picks_arm_counts_each_event_once(), test_the_predicate_keeps_rows_with_no_marker()

### Community 629 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.47
Nodes (6): contentHeight(), evalExpr(), lineOf(), styleBlock(), styleProp(), visualHeight()

### Community 630 - "Scorer confidence tier and pick label tests"
Cohesion: 0.07
Nodes (11): _build_pick_label(), _confidence_tier(), _feature_value(), _make_golf_pick(), quarter_kelly(), test_apply_game_market_gate_fail_open_without_conn(), test_scorer_live_default_downgrades_steamed_and_public_steam(), TestBuildPickLabel (+3 more)

### Community 631 - "Mobile auth hook"
Cohesion: 0.29
Nodes (10): applySession(), AuthState, AuthStatus, bootstrap(), handleAppStateChange(), listeners, setState(), state (+2 more)

### Community 633 - "Game line market sweep job"
Cohesion: 0.18
Nodes (5): test_runner_captures_stdout_from_the_script_main(), test_sport_and_market_are_bounded(), test_the_declared_key_is_present_and_valid(), test_the_runner_imports_the_script_main_not_a_shell(), _job_game_line_market_sweep()

### Community 634 - "Retrain job validation"
Cohesion: 0.18
Nodes (7): test_a_real_model_id_validates(), test_a_retrain_defaults_to_not_registering(), test_a_retrain_raises_its_own_statement_timeout(), test_the_timeout_is_bounded_at_both_ends(), _validate_mlb_over_under_retrain_sweep(), _validate_mlb_runline_retrain_sweep(), _validate_retrain()

### Community 635 - "tests/test_demote_ncaaf_over_under_platt.py"
Cohesion: 0.32
Nodes (4): _stmts(), test_it_demotes_only_the_measured_promotion(), test_it_does_not_move_the_gate_the_floor_or_a_pause(), test_migration_is_one_statement()

### Community 637 - "tests/test_discord_post_one_pick_migration.py"
Cohesion: 0.29
Nodes (3): _pairs(), test_it_names_each_measured_extra_and_the_row_kept(), test_the_update_does_not_rewrite_the_graded_outcome()

### Community 638 - "tests/test_game_scorer_spares_nfl_props.py"
Cohesion: 0.43
Nodes (5): _between(), _run_scorer_body(), test_an_nfl_game_never_enters_the_per_game_clear(), test_both_live_non_bet_clears_leave_nfl_rows(), test_the_left_out_ufc_clear_only_removes_unsettled_non_bets()

### Community 639 - "NCAAF ESPN state fetch tests"
Cohesion: 0.24
Nodes (6): _Ctx, _ev(), test_a_single_failed_summary_does_not_drop_the_other_games(), test_cfbd_mode_does_no_per_game_fetching(), test_espn_states_are_fetched_in_parallel_and_stay_aligned(), test_unknown_matchups_never_cost_a_fetch()

### Community 641 - "tests/test_mobile_ota_self_update.py"
Cohesion: 0.32
Nodes (4): _read(), test_app_root_mounts_the_ota_updater(), test_the_pieces_exist(), test_the_updater_actually_applies_the_update()

### Community 642 - "NFL DraftKings line snapshot tests"
Cohesion: 0.42
Nodes (3): dk_line_rows(), _rec(), TestDkLineRows

### Community 643 - "tracking/model_quality.py"
Cohesion: 0.25
Nodes (5): test_roi_collapse_is_crit_when_hit_rate_dies(), test_roi_ignores_unpriced_profit_flat(), detect_roi_collapse(), _sample(), units_from_profit_flat()

### Community 644 - "Live orchestrator floor pass tests"
Cohesion: 0.20
Nodes (5): _consume_source(), test_a_floor_pass_scores_every_live_game_not_just_triggered_ones(), test_no_pending_triggers_no_longer_short_circuits_unconditionally(), test_the_fetch_is_never_asked_for_every_event_the_feed_returns(), test_the_floor_is_gated_on_a_game_actually_being_live()

### Community 645 - "NBA injury report PDF parser"
Cohesion: 0.11
Nodes (16): _bands(), _column_of(), _columns(), finish_rows(), _hrules(), _lines_of(), parse_page_layout(), parse_pdf() (+8 more)

### Community 648 - "Disk IO indexes migration"
Cohesion: 0.18
Nodes (5): idx_live_state_snapshot, idx_odds_book_snap, idx_picks_game, idx_player_game_log_name, idx_prop_odds_snapshot

### Community 649 - "Calibration schema migration tests"
Cohesion: 0.20
Nodes (3): _SchemaRecordingConn, test_promote_creates_the_columns_it_writes_to(), test_the_alters_come_before_any_write_in_both_paths()

### Community 650 - "NCAAF odds feed outage tests"
Cohesion: 0.22
Nodes (5): _feed_with_payload(), test_a_sustained_feed_outage_degrades_to_no_odds(), test_cached_odds_are_served_while_fresh(), test_credit_cap_reports_no_odds_rather_than_a_frozen_line(), test_credit_cap_still_serves_a_payload_that_is_still_fresh()

### Community 652 - "(root): pr-ci + requirements"
Cohesion: 0.33
Nodes (5): Mobile thresholds drift check (generate_mobile_thresholds --check), NFL preflight --ci, PR CI workflow — non-integration pytest subset, Render blueprint — betting-scheduler background worker, requirements.txt — >= pins for Python 3.14 wheels

### Community 653 - "NFL prop book sweeps and two sharps"
Cohesion: 0.05
Nodes (29): norm_player_name(), base_market(), main(), _actuals(), _board(), p(), _line(), main() (+21 more)

### Community 654 - "Live game state tables"
Cohesion: 0.20
Nodes (9): v_live_game_state_latest, public.latest_lines_rebuild_live_state(), idx_live_state_game, idx_live_state_snapshot, idx_live_trigger_game, idx_live_trigger_pending, live_game_state, live_trigger_events (+1 more)

### Community 655 - "NFL in-play edge study 2024"
Cohesion: 0.36
Nodes (9): families(), fmt(), main(), parse_2025_output(), pooled_table(), replication(), repro_check(), row_of() (+1 more)

### Community 657 - "NHL moneyline rebuild write-up"
Cohesion: 0.29
Nodes (6): Method, NHL moneyline, rebuilt (2026-10-13), Read, Results, The production version, and two checks on it (2026-10-13/14), What the live model has, and what it was missing

### Community 659 - "Bookmaker whitelist tests"
Cohesion: 0.22
Nodes (5): _source(), test_closing_line_reads_name_the_book(), test_feature_engines_whitelist_draftkings(), test_line_shop_books_are_not_referenced_by_scoring_code(), test_scorer_prop_odds_reads_one_named_book_at_a_time()

### Community 660 - "NBA injury report retry tests"
Cohesion: 0.22
Nodes (7): pull_with_retry(), test_a_connection_lost_mid_write_re_runs_the_whole_slot(), executemany(), __init__(), test_a_statement_timeout_rolls_back_and_re_runs_the_slot(), executemany(), __init__()

### Community 661 - "NCAAF player stats leaderboard"
Cohesion: 0.42
Nodes (8): idx_ncaaf_plog_player, idx_ncaaf_plog_season, idx_ncaaf_plog_team, ncaaf_player_game_log, public.player_recent_games_ncaaf(), public.player_season_stat_values_ncaaf(), public.player_window_totals_ncaaf(), v_player_season_totals_ncaaf

### Community 662 - "Pregame poller and Bovada feed"
Cohesion: 0.04
Nodes (36): live_slate_dates(), release_read(), use_poller_session(), main(), poll_once(), run(), _ensure_schema(), run() (+28 more)

### Community 663 - "Insert column alignment tests"
Cohesion: 0.32
Nodes (3): _statements(), test_columns_and_values_line_up(), test_the_scorer_pick_insert_is_actually_covered()

### Community 666 - "Mobile bankroll hook"
Cohesion: 0.32
Nodes (7): store, useBankroll(), BANKROLL_DEFAULTS, BankrollSettings, canStepUnitPct(), sanitizeUnitPct(), stepUnitPct()

### Community 667 - "Scored pick outcomes lateral fix"
Cohesion: 0.36
Nodes (5): mv_scored_pick_outcomes_model_idx, mv_scored_pick_outcomes_pick_id_idx, public.v_model_full_outcome_record, public.v_public_track_record, public.v_public_track_record_daily

### Community 668 - "Mobile entitlement and subscription hooks"
Cohesion: 0.27
Nodes (13): DiscordLinkModal(), useEntitlement, useSubscription, fetchSubscription(), billingReady(), isEntitled(), SubscriptionRow, AccessSource (+5 more)

### Community 669 - "NFL live pick date tests"
Cohesion: 0.25
Nodes (3): test_a_night_game_pick_carries_the_game_s_date_not_the_utc_clock(), test_nothing_written_means_nothing_announced(), test_resolution_refuses_rather_than_guesses()

### Community 671 - "NCAAF play-by-play puller"
Cohesion: 0.19
Nodes (7): _extremes(), fetch_season(), _get(), main(), observed_ranges(), pull_season(), test_the_scan_survives_nulls_and_non_numeric_cells()

### Community 672 - "NCAAF tables migration"
Cohesion: 0.39
Nodes (7): idx_ncaaf_glog_game, idx_ncaaf_glog_team, idx_ncaaf_team, idx_ncaaf_teams_conf, ncaaf_team_game_log, ncaaf_team_stats, ncaaf_teams

### Community 673 - "Scorer keeps off-DraftKings priced bets tests"
Cohesion: 0.29
Nodes (6): _bet(), db(), _left(), _statement(), test_a_bet_priced_at_another_books_line_survives_and_a_bet_with_no_price_does_not(), test_the_statement_names_both_prices()

### Community 674 - "docs/game_injury_gate.md"
Cohesion: 0.40
Nodes (5): ESPN core probables for the NHL starting goalie, Game-model starter / star / goalie gate, A NONE from this gate is not locked — the reprice path, The gate rule — refuse a game-model BET on a confirmed Out starter/star/goalie, Fires in scorer.score_game and _score_nhl_3way, after best-price requalify, before insert

### Community 675 - "Clock and shot value parsing"
Cohesion: 0.29
Nodes (4): classify_field_goal(), parse_clock(), test_field_goal_value(), test_parse_clock()

### Community 676 - "nfl/scripts/live_prop_job.sh"
Cohesion: 0.33
Nodes (5): LGB_NUM_THREADS, MKL_NUM_THREADS, OMP_NUM_THREADS, OPENBLAS_NUM_THREADS, live_prop_job.sh script

### Community 677 - "NFL prop lean gradient study"
Cohesion: 0.36
Nodes (4): boot(), grade(), main(), profit()

### Community 679 - "Mobile package manifest"
Cohesion: 0.29
Nodes (7): devDependencies, @babel/core, babel-plugin-module-resolver, babel-preset-expo, tsx, @types/react, typescript

### Community 683 - "Anon grant plan tests"
Cohesion: 0.29
Nodes (4): _plan(), test_every_declared_relation_is_granted_exactly_once(), test_the_plan_revokes_before_it_grants(), test_the_view_base_tables_are_granted_but_never_read_directly()

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

### Community 688 - "NFL wind totals runbook and staking"
Cohesion: 0.36
Nodes (7): DOCUMENT STATUS block: superseded claims indexed, Under rate by forecast lead 1-7 (~0.41pp per day), Original staking: 25% Kelly capped at 3% (superseded), Kelly-proportional units with slate shading 1/sqrt(1+(k-1)rho), Stops: 2 units per bet, 3 units per slate, review at -15 units, Runbook: Wind Totals, scripts/stake_sizing.py: 1 unit = 1% of bankroll

### Community 689 - "Parlay leg correlation estimates"
Cohesion: 0.36
Nodes (5): estimate(), estimate_basketball(), estimate_mlb(), main(), _median()

### Community 692 - "NFL research backup and restore script"
Cohesion: 0.44
Nodes (5): backup(), files(), main(), restore(), verify()

### Community 693 - "Board markets lock-down tests"
Cohesion: 0.25
Nodes (4): _board_markets(), table(), test_the_mlb_board_and_the_mlb_pull_are_one_set(), test_the_tables_are_locked_down_at_the_create_site()

### Community 694 - "Model quality volume spikes"
Cohesion: 0.29
Nodes (5): test_volume_spike_vs_median(), test_volume_without_history_is_skipped_not_flagged(), detect_volume_spike(), _median(), units_from_recommended_bet()

### Community 696 - "NFL prop artifact parameter tests"
Cohesion: 0.33
Nodes (3): _models(), _newest_artifact(), test_params_file_carries_the_newest_artifacts_hyperparameters()

### Community 697 - "Market handicap features"
Cohesion: 0.29
Nodes (4): build_rich_handicap(), _fav_signed_home_move(), _gated_flag(), _mul()

### Community 703 - "Player news migration"
Cohesion: 0.60
Nodes (5): player_news_by_id, player_news_by_key, player_news_item_player, player_news_published, public.player_news

### Community 705 - "NCAAF travel geography features"
Cohesion: 0.29
Nodes (5): haversine_miles(), tz_offset_from_lon(), trip(), test_haversine_matches_real_geography(), test_timezone_offsets_land_in_the_right_zones()

### Community 707 - "NHL goalie line helpers"
Cohesion: 0.83
Nodes (4): _goalie_line(), regressed(), saved_above(), tot()

### Community 710 - "mobile/docs/BILLING.md"
Cohesion: 1.00
Nodes (4): useEntitlement() access gate (subscription OR Discord), useSubscription() subscription-only state, useEntitlement(), not useSubscription(), Access is one gate: useEntitlement(), never useSubscription().entitled

### Community 711 - "Live money no record-only tests"
Cohesion: 0.43
Nodes (4): _allowed(), _hits(), _rel(), test_the_repo_has_no_record_only_or_paper_tracking_mode()

### Community 712 - "Team stats twin code tests"
Cohesion: 0.29
Nodes (3): test_mlb_twin_codes_do_not_false_crit(), test_mlb_twin_reverse_lookup_also_resolves(), test_season_final_in_april_still_caught_on_twin_code()

### Community 718 - "Scorer subset delete tests"
Cohesion: 0.33
Nodes (3): _run_scorer_body(), test_every_housekeeping_delete_in_run_scorer_is_scoped_to_the_subset(), test_the_subset_predicate_never_builds_an_empty_IN_list()

### Community 719 - "Mobile accessibility verify script"
Cohesion: 0.67
Nodes (3): read(), readUtf8(), verticalSlop()

### Community 720 - "docs/testing.md"
Cohesion: 0.67
Nodes (3): Test suite (testing.md), PR CI runs a non-integration pytest subset, Pure function tests, in-memory SQLite via conftest

### Community 721 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.67
Nodes (3): closeOf(), openTag(), toggleUse()

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

### Community 730 - "Strategy analysis report"
Cohesion: 0.43
Nodes (4): _fmt(), _profit_sql(), _row(), strategy_analysis()

### Community 732 - "NBA injury report name and team parsing"
Cohesion: 0.22
Nodes (7): name_first_last(), norm_name(), _row(), team_code(), test_name_key_drops_accents_punctuation_and_suffixes(), test_names_turn_round_with_their_suffix_on_the_surname(), test_team_names_map_to_our_codes()

### Community 754 - "NFL live model tables"
Cohesion: 0.60
Nodes (4): live_game_states_ts_idx, live_odds_snapshots_game_ts_idx, public.live_game_states, public.live_odds_snapshots

### Community 756 - "Model pause helper tests"
Cohesion: 0.40
Nodes (3): _is_paused(), test_config_pauses_still_work_through_the_same_helper(), test_the_scorer_still_honours_a_leftover_auto_pause_row()

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

### Community 849 - "App RPC declaration tests"
Cohesion: 0.40
Nodes (3): _app_rpcs(), test_every_rpc_the_app_calls_is_declared_or_known_absent(), test_the_dynamic_rpc_resolver_actually_finds_the_ternary_names()

### Community 856 - "NCAAF feature assembly"
Cohesion: 0.20
Nodes (4): _assemble_ncaaf_features(), _game_tier(), test_assembly_carries_venue_context_and_hfa(), test_season_opener_gets_a_zero_rest_differential_not_a_null()

### Community 885 - "NFL prop market rule and card"
Cohesion: 0.06
Nodes (23): _as_dt(), grade(), season_of(), summarise(), card(), _kalshi_ladders_or_empty(), main(), pick_rows() (+15 more)

## Ambiguous Edges - Review These
- `Claim: the app cannot write to the backend` → `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`  [AMBIGUOUS]
  docs/privacy.html · relation: conceptually_related_to

## Knowledge Gaps
- **105 isolated node(s):** `RFC-4122`, `@babel/core`, `babel-plugin-module-resolver`, `babel-preset-expo`, `expo-asset` (+100 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 10481 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **221 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_connection()` connect `Database connection and CLI ingestor scripts` to `ESPN injury ingestor`, `Odds, prop odds and NHL derivative odds ingestors`, `Feature engine and live scorer loading`, `Paper tracker bankroll and scorer database calls`, `NFL prop market stack and devig`, `Discord signal notifier tests`, `Daily pipeline runner and push notifier`, `NCAAF steam lag study`, `NBA prop projection card`, `NHL market lab and live artifact grading`, `NBA play-by-play ingestor`, `In-play history and play-by-play ingestors`, `NFL odds cache import`, `EV floor and threshold sweep scripts`, `NFL wind edge studies`, `tests/test_live_quote_staleness.py`, `DataGolf ingestor and NHL SBR archive`, `NCAAF starter-out study`, `Worker job queue`, `Prop training dataset builders`, `Brand avatar and connection probes`, `scheduler.py`, `NFL prop backtest model and universe rate`, `Failure alerter fake-connection tests`, `NFL player stats ingestor and prop tests`, `tests/test_void_picks.py`, `NCAAF gameday worker and ESPN feed`, `tests: test_wnba_availability + wnba_availability`, `NFL pick monitor`, `scripts: ncaaf_margin_eval + test_ncaaf_margin_eval`, `tests/test_wnba_prop_market.py`, `NHL derivative totals model`, `Global EV floor and NHL totals tests`, `Discord notifier and void notices`, `tests/test_recap_retries_a_skipped_day.py`, `tests: test_player_positions + player_positions_ingestor`, `tests/test_ncaaf_pbp_store.py`, `tests/test_heartbeat_watchdog.py`, `models: nhl_prop_blocked_shots + nhl_prop_blocked_shots_backtest`, `Record correction post tests`, `Model trainer and WNBA points rebuild`, `tests/test_live_calibration.py`, `nfl_live_leader/gameday.py`, `Heartbeat watchdog and ops alerts`, `Game scorer core and NCAAF board visibility`, `NHL prop cards and cross-model publish`, `features/golf_feature_engine.py`, `NBA injury report PDF parser`, `NFL prop book sweeps and two sharps`, `models/nhl_props.py`, `WNBA stats and results ingestors`, `X and Discord results publishers`, `Pregame poller and Bovada feed`, `Idle read transaction tests`, `NCAAF play-by-play puller`, `NBA box score enrichment`, `NHL stats and game log ingestors`, `Prop box score backfill`, `Push notifier and tickets`, `Parlay leg correlation estimates`, `NFL prop odds backfill`, `NFL research backup and restore script`, `tests/test_nfl_rule_2026_track.py`, `scripts/game_line_market_sweep.py`, `scripts/nfl_wind_publisher.py`, `tests/test_first_signal_repair.py`, `NBA stats ingestor`, `Historical odds backfill tests`, `NFL prop feature engine and grading`, `scripts/ncaaf_search: dataset + starter_out`, `tests: test_deploy_checks + deploy_checks`, `data/ingestors/nfl_inplay_history.py`, `Probability calibration fit`, `Live count tail probability tests`, `NCAAF live engine pricing`, `Strategy analysis report`, `tests/test_local_cache_is_additive.py`, `Record correction posting script`, `tests/test_team_board_cache.py`, `tests/test_nfl_poll_fast_silence.py`, `Batter prop feature rows`, `Results recap message tests`, `MLB stats ingestor`, `data/ingestors/nhl_boxscore.py`, `scripts/mlb_total_public_fade_topk.py`, `tests/test_ncaaf_search_features.py`, `NFL wind forecast and totals`, `NCAAF in-play history backtest`, `tests/test_cfbd_ingestor.py`, `Monitoring HTTP stream handler`, `NBA ESPN box score parser`, `NBA injury report runner`, `NCAAF play-by-play state builder`, `Dashboard app and SQL runner`, `Pitcher stats as-of invariant tests`, `NHL prop backtest and combined cap`, `College football data parsers`, `Odds pruning and opener retention`, `NCAAF totals lead and consensus gate`, `Paused model assessment script`, `NFL opener card and line snapshots`, `Player news ingestor`, `Live honest cut and research scripts`, `Kalshi game market recorder`, `UFC stats ingestor and CSV loader`, `NFL prop market rule and card`, `CFBD ingestor`, `tests/test_heartbeat_disabled_jobs.py`, `Discord restate signal tests`, `tests/test_promote_calibration_job.py`, `NCAAF search feature matrix`, `NFL live pick writer`, `tracking/model_quality.py`, `Intraday freshness tests`, `Prop ladder and Kalshi pricing`, `System health checks`, `NBA prop market model and card`, `tests/test_batter_prop_log_pin.py`, `tests/test_merge_mlb_twin_games.py`, `NCAAF outcome edge scan`, `scripts/ncaaf_search/situational_spots.py`, `Monitoring server tests`, `tests/test_transaction_pooler.py`, `CFBD refresh and backfill tests`, `Local store cache and NFL prop shape simulation`, `MLB game market and public fade cards`, `Pipeline watch and burn alerts`, `Price floor and prop pick decisions`, `scripts/ncaaf_search/weather_totals.py`, `Anon grants admin script`, `NBA, NCAAF and NFL research labs`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **What connects `RFC-4122`, `@babel/core`, `babel-plugin-module-resolver` to the rest of the system?**
  _105 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `ESPN injury ingestor` be split into smaller, more focused modules?**
  _Cohesion score 0.0700354609929078 - nodes in this community are weakly interconnected._
- **Why does `DBConnection` connect `Paper tracker bankroll and scorer database calls` to `ESPN injury ingestor`, `features/golf_feature_engine.py`, `Odds, prop odds and NHL derivative odds ingestors`, `Feature engine and live scorer loading`, `Database connection and CLI ingestor scripts`, `WNBA stats and results ingestors`, `Pregame poller and Bovada feed`, `CLV price-taken tests`, `NFL odds cache import`, `In-play history and play-by-play ingestors`, `Best line and best-price decision tests`, `NHL stats and game log ingestors`, `DataGolf ingestor and NHL SBR archive`, `tests/test_dk_direct_feed.py`, `Prop training dataset builders`, `NFL prop odds backfill`, `tests/test_mlb_sbr_twin.py`, `Pitcher stats as-of invariant tests`, `tests/test_best_line_live.py`, `Live scorer score-change guard`, `tests: test_wnba_availability + wnba_availability`, `Settlement and self-heal tests`, `tests/test_db_adapt_sql.py`, `NCAAF board visibility tests`, `tests/test_sbr_loader.py`, `NBA stats ingestor`, `Prop price pregame cutoff tests`, `NFL prop odds loading tests`, `NFL prop feature engine and grading`, `Odds pruning and opener retention`, `tests/test_live_pick_features.py`, `tests/test_f5_any_book_line.py`, `Pregame price age tests`, `tests/test_db_reconnect.py`, `tests/test_live_lock.py`, `Prop player name matching tests`, `Model trainer and WNBA points rebuild`, `Batter prop feature rows`, `UFC stats ingestor and CSV loader`, `MLB stats ingestor`, `UFC fighter name resolution`, `tests/test_score_off_any_book_line.py`, `tests/test_prop_alternate_lines.py`, `Game scorer core and NCAAF board visibility`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Should `Mobile stats board` be split into smaller, more focused modules?**
  _Cohesion score 0.012661414524345457 - nodes in this community are weakly interconnected._
- **Why does `mlb_live_total_runs (in-play total)` connect `NFL prop studies and monitoring docs` to `docs/thresholds.md`?**
  _High betweenness centrality (0.015) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Claim: the app cannot write to the backend` and `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._