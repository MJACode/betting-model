# Graph Report - bm-nba-total-luck  (2026-10-17)

## Corpus Check
- Large corpus: 1490 files · ~2,449,071 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 28915 nodes · 68700 edges · 926 communities (703 shown, 223 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 1742 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1b529b64`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Injury report ingestion with WNBA fallback
- Mobile stats board
- App feedback and support screens
- Live monitor API probe
- Publish key identity tests
- Record correction posts to Discord
- tests/test_nfl_live_leader_gameday.py
- nfl_live_leader/gameday.py
- tests/test_calibration_promotion.py
- tests/test_score_off_any_book_line.py
- NCAAF FBS team registry tests
- Mobile pick filters and sorting
- tests/test_ncaaf_alias_scores.py
- Prop alternate line parsing tests
- NFL prop odds loader slice tests
- tests/test_backtester.py
- NHL prop expected value lab
- nfl/live_model/feeds/odds_live.py
- NHL props newest quote shopping
- NBA prop market lab
- Discord pick notifier tests
- nfl/live_model/tests/test_backup_snaps.py
- mobile/scripts: verify_book_links + verify_betslip_combine
- NBA official injury report parser
- tests/test_paused_keeps_real_verdict.py
- Best-price decision tests
- mobile/scripts/verify_contrast_tokens.ts
- models/nhl_props.py
- Pick lock after settlement tests
- NBA game line move study
- NBA prop market card publisher
- tests/test_mlb_game_market.py
- Threshold review tests
- Idle read transaction tests
- UFC phantom fight filter
- tests/test_prop_box_scores.py
- NBA game model prop feature tests
- In-play scorer and cut sweeps
- Best line and best-price decision tests
- Worker job queue claim and run
- Database schema guard and brand avatar
- Discord results recap
- tests/test_nfl_opener.py
- NHL stats and game log ingest
- scripts/nfl_preflight.py
- NBA game model luck feature tests
- CLV math and devig functions
- tests/test_publisher_lock.py
- tests/test_dk_direct_feed.py
- tests/test_credit_budget.py
- Mobile thresholds and sharp score
- Player news ingest
- NHL prop card publishing
- Sharp-price de-vig helpers
- tests/test_first_signal_repair.py
- tests/test_ungraded_model_performance.py
- mobile/scripts/verify_push.ts
- Prop price pregame cutoff tests
- Mobile markets and formatting
- tests/test_nhl_asof.py
- Shared database access and scripts
- NFL in-play game state feed
- data/ingestors/nfl_inplay_history.py
- App model list and detail screens
- Mobile bankroll number formatting
- App sign-in and sportsbook connection
- Health check skip budget tests
- WNBA prop training and rebuild
- NCAAF in-play engine and pick lock
- NBA prop projection model and card
- tests/test_db_reconnect.py
- NHL derivative totals card tests
- In-play pick lock tests
- tests/test_refresh_retry.py
- NBA results and lineup segments store
- NBA results ingestor tests
- NBA game projection rebuild script
- tests/test_local_cache_is_additive.py
- tests/test_calibration_check_coverage.py
- tests/test_book_team_map.py
- tests/test_team_board_cache.py
- nfl/live_model/tests/test_rush_attempt_pace.py
- tests/test_nfl_poll_fast_silence.py
- NHL moneyline and market research labs
- Umpire step on every refresh pass
- tests/test_nhl_asof.py
- tests/test_dk_freshness_parse.py
- NBA historical odds gap backfill
- models: slate_concentration + test_slate_concentration
- View migration lock handling tests
- Publisher and injury fetch test fakes
- NCAAF in-play history backtest
- Deploy checks and worker job queue
- Mobile teams board and team detail
- Best line threshold sweep
- NBA official injury report ingestor
- NCAAF college data ingest tests
- Mobile betslip and parlay legs
- NHL starting goalie lookup tests
- tests/test_prop_odds_utc_stamp.py
- Live monitor web server
- NFL publisher lookahead and key tests
- tests/test_feature_artifact_agreement.py
- NFL prop market one side per line
- CLV graded at the price taken
- tests/test_cloud_retrain_artifacts.py
- NHL totals card writer
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
- College football feature tests
- Pregame line poller change tests
- Pitcher stats as-of invariant tests
- NHL props card slate tests
- Pipeline log reason tests
- Stats and prop data ingest
- NCAAF in-play score distribution pricing
- tests/test_nfl_scored_rows.py
- System health signal delivery tests
- X results job and cursor wrapper tests
- NBA prop window scheduling tests
- NHL totals market model
- nfl/live_model/feeds: test_feed_resilience + espn
- NFL opener card rows
- In-play score change guard
- NBA prop rule card tests
- Kalshi prop ladders and game markets
- NFL prop rule with Kalshi tests
- tests/test_live_pick_features.py
- Pregame price age tests
- tests/test_prop_missing_features.py
- MLB public fade top picks ranking
- MLB game line rule card
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
- Team stats rebuild checks
- In-play calibrated decision tests
- NFL DraftKings line snapshots
- Sharp book odds retention in pruning
- Price conversion and side tables
- tests/test_heartbeat_disabled_jobs.py
- Scorer any-book game line fallback
- tests/test_repair_bogus_first_pitch_labels.py
- nfl/live_model/tests/test_executor.py
- Discord in-play pick rendering
- tests/test_sbr_loader.py
- mobile/scripts/ux_scan.mts
- NFL prop stat distributions
- Pre-game scorer and pick writing
- mobile/src/lib/otaUpdate.ts
- tests/test_live_quote_staleness.py
- College football search validation
- App push links and sport filter
- NBA prop settlement stats tests
- Pipeline report with per-section rollback
- supabase/functions/_shared/discord.ts
- NFL weather edge study
- Worker job queue validation tests
- NBA totals card ledger and label tests
- MLB prop pre-game quote tests
- NFL CLV backtest and feature build
- MLB doubleheader twin game merge
- tests/test_discord_channel_probe.py
- tests/test_nfl_prop_one_read_per_game.py
- Game outcome target tests
- Voided and restated pick tests
- Discord recap restatement
- Mobile billing, paywall and sign-in
- Multi-book odds and pruning
- scripts/nfl_edge_gameline_rules.py
- tests/test_model_game_savepoint.py
- tests/test_calibration_watch.py
- tests/test_promote_external.py
- Weather look-ahead tests
- Batter prop log lookback tests
- Failure alerter fake-connection tests
- Score when lines open tests
- tests/test_sbr_loader.py
- NFL opener daily card evaluation
- Mobile app screens and theme
- Local research cache store
- Price prefilter rollback tests
- MLB in-play state alignment
- tests/test_nhl_three_way_lookahead.py
- NFL in-play gameday worker
- Scorer pricing and label helpers
- Prop odds next-day lookahead
- NFL live leader win model
- Run ledger table tests
- NHL blocked shots settlement shim
- Stale weekly sweep watch tests
- Weather forecast hour lookup
- Mobile bankroll storage
- tests/test_best_line_live.py
- Threshold review table creation tests
- tests/test_sbr_loader.py
- NFL wind card book filter tests
- Prop no-bet rows until tip tests
- Closing line value backfill job
- NFL prop settlement tests
- NFL prop local odds cache tests
- tests/test_void_picks.py
- tests/test_sbr_loader.py
- Odds credit budget
- NCAAF starter-out search dataset
- College football game-day feeds
- Scorer BET and AVOID signal tests
- tests/test_system_health_checks.py
- tests/test_sbr_loader.py
- tests/test_daily_retry.py
- NFL prop market card publisher
- Feature map tests
- Odds feed probes and snapshot pulls
- tests/test_live_book_move_guard.py
- NCAAF in-play underdog calibration
- tests/test_nfl_props.py
- tests/test_weekly_catch_up.py
- tests/test_sbr_loader.py
- MLB umpire ingestor
- Prop odds book update-time tests
- NFL pick monitor
- tests/test_nhl_props.py
- NFL odds client and opener card
- NHL blocked shots prop card
- NFL wind totals model and monitor
- App data queries and pick details
- Prop alternate lines fetch tests
- Mobile tracked bets and stakes
- supabase/functions/revenuecat-webhook/index.ts
- supabase/functions/whop-webhook/index.ts
- tests/test_nfl_props.py
- NCAAF in-play FBS context loading
- tests/test_sbr_loader.py
- NHL as-of feature leak tests
- Mobile bankroll unit size hook
- College football state feed tests
- NHL props four per night cap
- tests/test_nfl_props.py
- tests/test_nhl_three_way_lookahead.py
- MLB totals public fade card
- NHL prop newest fetch tests
- Model calibration sweep tests
- Model quality database end-to-end test
- College football stored finals mirror
- Signal publish-on-write tests
- NFL prop rule card
- tests/test_game_market_gate.py
- NFL prop pull market list tests
- NBA public splits quality backfill
- MLB bet record audit tally
- Prop box score grading tests
- NBA prop player name resolver
- NBA second-model prop study
- tests/test_score_when_lines_open.py
- tests/test_score_when_lines_open.py
- tests/test_score_when_lines_open.py
- tests/test_system_health_checks.py
- Settlement test database shim
- tests/test_pick_integrity.py
- NFL prop price math tests
- NBA public splits late game archiving
- Pre-game price freshness tests
- Database connection and feature reads
- tests/test_record_one_pick_per_event.py
- NHL returning starter name tests
- Batter prop shared log load test
- nfl/live_model/tests: test_props + props
- Opponent starter stub connection
- NFL prop odds game matching
- WNBA prop rule fake connection
- Local store lazy connection
- tests/test_wnba_prop_market.py
- Weekly catch-up fake cursor
- tests/test_nfl_scored_rows.py
- NHL period and team totals model
- App player stat log
- Global EV floor tests
- tests/test_nhl_props.py
- Publish key identity and push alerts
- NHL blocked shots prop settlement tests
- NFL wind forecast and lead
- tests/test_recap_retries_a_skipped_day.py
- NBA odds archive rerun safety
- NFL prop placebo tests
- Picks email rendering
- NCAAF feature engine test database
- NFL in-play settlement database shim
- NBA prop settlement fake connection
- Settlement fake MLB schedule
- Pregame poller game creation
- Umpire feature retirement tests
- Probability calibration fitting tests
- Mobile matchup stats verify scripts
- NFL in-play remaining score distribution
- NBA game residual distribution
- NFL evaluation rows carry the line
- tests/test_ncaaf_prop_odds.py
- NFL prop verdict tests
- tests/test_ncaaf_pbp_store.py
- tests/test_heartbeat_watchdog.py
- Game injury veto gate and tests
- Record correction post tests
- Daily pipeline runner and push notifier
- scripts/nfl_edge_live_rush_pace.py
- NBA prop projection tests
- NBA game market feature study
- tests/test_prop_calibrated_decision.py
- NCAAF in-play quote serving
- NFL in-play backtest game states
- NFL prop information and stacking studies
- tests/test_mobile_line_movement.py
- tests/test_live_calibration.py
- Mobile live board segment tests
- NBA lineup stint derivation tests
- tests/test_ncaaf_live_notify.py
- monitoring/store.py
- tests/test_settled_record_is_immutable.py
- features/golf_feature_engine.py
- ncaaf_live/tests/test_states.py
- tests/test_bovada_feed.py
- tests/test_market_movement.py
- NCAAF cross-book opener rule tests
- NFL in-play edge seasonal backtest
- tests/test_health_pregame_prices_current.py
- scripts/nfl_edge_extreme_props.py
- scripts/nfl_edge_settlement.py
- NBA totals overs rule tests
- X publisher
- tests/test_agents_contract.py
- WNBA results and stats ingestors
- NBA box score enrichment tests
- Prop box score backfill
- Push delivery ticket tests
- NFL expected value stake engine
- NFL quarterback wind edge study
- Probability calibration jobs
- tests/test_decide_on_calibrated.py
- NBA prop projection lab
- NFL edge versus luck gap study
- NBA totals overs shooting luck model
- tests/test_model_artifacts_load.py
- scripts/game_line_market_sweep.py
- Push notification deep link tests
- tests/test_pass_instrumentation.py
- Settlement self-healing tests
- tests/test_db_adapt_sql.py
- NFL in-play 2025 edge report
- tests/test_mobile_contrast_tokens.py
- NBA box score stats ingestor
- Threshold and EV floor sweeps
- Live monitor cache
- NBA second game line move tests
- NBA shooting luck and motivation lab
- DraftKings direct feed freshness probes
- NBA play-by-play game matching tests
- WNBA stats and results ingestion
- NBA public betting splits ingestor
- Database row and SQL safety tests
- tests/test_nfl_live_leader_state.py
- tests/test_ncaaf_qb_ingestor.py
- NBA derivative market lab
- NBA public betting splits ingestor tests
- Mobile pick category tests
- NCAAF feature engine tests
- First pitch bound tests
- House juice price floor tests
- tests/test_ncaaf_game_identity.py
- NBA second game market tests
- Position versus opponent tests
- MLB and WNBA stats ingestors and pitcher rebuild
- NBA game search grading harness
- College football in-play history pull
- NBA totals overs card
- tests/test_ncaaf_search_features.py
- College football model search runner
- NFL wind card and opener sweep
- tests/test_live_game_features.py
- tests/test_ncaaf_totals_regression.py
- UFC feature engine and tests
- App script tests run through node
- tests/test_ncaaf_qb_features.py
- Discord price bound tests
- Line CLV sign and orientation tests
- Mobile screen source wiring tests
- NBA game harness tests
- NBA results ingest
- MLB live game state trigger tests
- College football in-play game states
- Kalshi prop ingest
- Model calibration check tests
- NBA prop market bet finder
- NCAAF college data ingestor
- NBA second game model verdict
- Source inspection guard tests
- NCAAF player stats parser tests
- NHL namesake player tests
- scripts/nfl_live_prop_feasibility.py
- tests/test_context_budget.py
- tests/test_player_h2h_stat_values_migration.py
- tests/test_retired_models.py
- Free pick post rendering
- NBA prop model lab and verification
- MLB totals public fade pre-start split
- Real database trigger tests
- tests/test_live_record_start_views.py
- Model quality volume spike checks
- NBA rest and schedule features
- NFL Kalshi edge search
- nfl/models/opener_spread.py
- NHL prop backtest and EV lab
- Live slate midnight date tests
- tests/test_nfl_wind_fire_window.py
- tests/test_public_betting_ingestor.py
- tests/test_service_role_split.py
- tests/test_http_timeout_floor.py
- Model quality public fade tests
- NFL edge research data cache
- Paused model assessment
- NBA second game projection tests
- Slate concentration and fade risk detection
- NHL prop odds alternate line tests
- Ops alert watchdogs
- Kalshi game market recorder
- Odds pruning keeps openers
- UFC fighter name resolution
- NBA second game projection fixtures
- Refresh pass step ordering tests
- NBA historical odds archive parser
- NFL in-play backtest replay harness
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
- NFL in-play prop rule and staleness studies
- NFL prop two sharp books study
- MLB play-by-play ingestor
- tests/test_promote_calibration_job.py
- tests/test_cfbd_snapshot_leakage.py
- NFL weather cache importer
- NFL in-play remaining-points engine
- NCAAF outcome edge scan
- tests/test_nfl_prop_thresholds.py
- tests/test_nhl_research_job.py
- tests/test_settlement_timing.py
- App and server closing value parity
- Per-model threshold config tests
- App accessibility checks
- DataGolf ingestor and NHL SBR archive
- Mobile bankroll settings card
- NFL odds cache import to Supabase
- tests/test_health_check_observe.py
- Health check deliverability tests
- NFL 2026 opener and wind tracker
- NFL prop shape simulation
- tests/test_pick_lock_is_on_picks.py
- NFL in-play prop settlement tests
- NCAAF board visibility tests
- NBA box score enrichment
- Env file fallback reader
- College football margin cover tests
- NFL prop lead-time ceiling tests
- scripts: build_nfl_live_leader_artifact + model
- NFL in-play line churn study
- tests/test_opp_starter_features.py
- supabase/functions/discord-link/index.ts
- tests/test_nfl_prop_clv.py
- tests/test_prune_keeps_the_close.py
- tests/test_scoring_methods.py
- College football team stats parsing
- NFL ESPN injury ingest tests
- Worker job queue and retrain jobs
- Anonymous read access lockdown
- NFL in-play leader model config tests
- College football game-day odds cadence
- nfl/scripts/backtest_opener.py
- NFL stale card file cleanup
- tests/test_latest_odds_views.py
- NFL prop scoring feature builder
- NBA schedule ingestor and tests
- tests/test_nfl_prop_settle_name_fallback.py
- Recap waits for NFL box scores
- NFL prop injury and signal sweeps
- tests/test_transaction_pooler.py
- NBA historical odds archive parsing
- MLB totals retrain sweep job tests
- Mobile sport filter persistence tests
- Trainer no-register mode tests
- MLB run line feature types
- supabase/functions/sharpsports/index.ts
- NBA totals overs replay of the lab
- Results recap backfill
- NBA second game grid verdict tests
- MLB retrain freeze guard tests
- tests/test_worker_deps.py
- College football totals lead study
- scheduler.py
- NFL model import tests
- tests/test_mobile_stat_labels_match_the_server.py
- tests/test_ncaaf_fcs_visitor_names_migration.py
- tests/test_nfl_prop_unstarted_clear.py
- NBA game model lab and NFL staking
- tests/test_savant_freshness.py
- tests/test_scorer_nfl_prop_like_escape.py
- CLV no-vig close capture tests
- Paused and no-signal pick rows
- College football opener strategy study
- NFL prop over lean study
- Paused model assessment tests
- Streamlit dashboard
- tests/test_clear_unauthorized_auto_pauses_migration.py
- Declared worker job validation tests
- tests/test_ncaaf_se_louisiana_alias_migration.py
- NCAAF quarterback ablation study
- tests/test_overnight_polling.py
- NCAAF weather and wind totals study
- NFL Kalshi price history fetch
- Pipeline watch post ledger tests
- NCAAF situational spot search
- tests/test_claude_rules_split.py
- In-play honest cut sweep
- tests/test_dedupe_opening_signals.py
- NFL backfill retry resilience
- NFL prop odds ingestion
- Live model holdout side-by-side comparison
- tests/test_pbp_backfill_resilience.py
- MLB live game discovery tests
- NFL prop pulled quote filtering
- College football loop timing tests
- NFL in-play prop state builder
- Voiding picks
- NFL prop book sweep
- tests/test_game_log_backfill_skip.py
- NCAAF line move spots
- NBA public splits pipeline step
- tests/test_prompt_reads_thresholds.py
- tests/test_system_health_meta_steps.py
- NBA quarter scores parser
- tests: test_discord_notifier + test_discord_live_field
- scripts/render_brand_icons.py
- NFL wind stake sizing tests
- NBA injury report page parsing
- supabase/functions/stripe-webhook/index.ts
- tests/test_drop_voided_nfl_wind_opening_signals_migration.py
- NFL in-play joint distribution
- tests/test_mobile_neutral_signal_label.py
- College football team list parsing
- tests/test_scorer_commits_per_game.py
- NCAAF scoreboard yardline parsing tests
- First pitch delivery guard tests
- Threshold sweep price floor tests
- Database setup column tests
- College football stats ingestion
- Pipeline watch run tests
- tests: test_wnba_availability + wnba_availability
- NBA inactives and officials rows
- Market coverage probe tests
- NFL prop universe summary tests
- supabase/functions/sharpsports-webhook: index + index
- NFL odds cache import
- supabase/functions/stripe-checkout/index.ts
- tests/test_book_list_budget.py
- College football in-play price gate tests
- API call daily rollup
- NBA game market search lab
- MLB live game state poller
- SBR odds CSV loader
- College football totals weather study
- NCAAF steam lag study
- mobile/scripts/verify_a11y.ts
- Football in-play game state
- Live slate dates around midnight
- Model quality CLV and ROI alerts
- tests/test_demote_ncaaf_over_under_platt.py
- MLB runline retrain sweep job
- tests/test_discord_post_one_pick_migration.py
- tests/test_game_scorer_spares_nfl_props.py
- NFL in-play backtest states
- NFL in-play market pricing engine
- tests/test_mobile_ota_self_update.py
- NBA second game emit and bootstrap tests
- College football weather backfill
- NBA archive odds row shaping
- College football issued forecast backfill
- NFL in-play flow model tests
- College football team name slugs
- NBA public splits side parsing
- NBA box and archive sample checks
- Parlay correlation estimates
- College football consensus gate study
- NFL wind forecast validation
- Revoke remaining write grants tests
- Published record units
- Calibration eligibility notes
- Scorer keeps off-DraftKings priced bets tests
- Drop voided NFL prop signals tests
- NFL prop scorer kickoff ceiling
- NCAAF structural spot scan
- Every named sportsbook is fetched
- NFL odds table builder
- Market board and pull agreement tests
- Odds credit burn watch tests
- tests/test_weekly_catch_up.py
- Mobile stats filter checks
- NHL goalie line helpers
- Registered but not firing models tests
- Team board start time bound tests
- tests/test_live_orchestrator.py
- Every model is real money test
- NBA missing game log fill
- NBA second game price cache checks
- NFL opener calibration
- NCAAF venue travel features
- Eastern game date everywhere
- NFL prop publish without a game row
- Mobile accessibility verify script
- Market handicap feature tests
- mobile/scripts/verify_a11y.ts
- mobile/scripts/verify_a11y.ts
- Pipeline silence findings
- Prop CLV and SQL escaping tests
- mobile/scripts/verify_a11y.ts
- College football margin evaluation
- Game pick settlement window
- NCAAF game feature assembly
- ncaaf_live/tests/test_serve.py
- docs: nhl_market_lab + nhl_clv_ev_assessment
- Mobile script test runner via Node
- Mobile NHL look-ahead window tests
- NBA prop decisions ledger test
- Refresh pass finding tests
- Worker service role split
- scripts/nfl_edge_preregistered_2026.py
- Pause check helper tests
- Shared test fixtures
- NBA public splits game dating
- NBA public splits quality flags
- Threshold review test fixtures
- MLB market handicap signals
- NCAAF travel distance and time zones
- tests: test_player_positions + player_positions_ingestor
- College football archived line books
- College football scoreboard call budget
- NBA prop read window test
- Opening versus closing strategy analysis
- NBA public splits pair validation
- NFL prop market census test
- Pipeline watch ledger failure test
- Unreadable pause table test
- College football unknown kickoff test
- NBA prop market decision tests
- College football shipped artifact fixture
- Refresh step time limit test
- NBA prop projection pull timing test
- Pregame scorer cleanup scoping tests
- NBA SBR archive moneyline timing
- Pre-game poller number compare
- mobile/scripts/verify_a11y.ts
- College football preferred line provider test
- Pending starter features guard
- Home run model starter features
- Pre-game poller daily cap test
- Pre-game poller runaway guard test
- MLB prop backfill pre-game anchoring
- NBA prop posting near tipoff
- Pre-game poller subset order test
- NBA public splits game matching
- Pre-game poller empty subset test
- Pre-game poller failed tick test
- NBA public splits side flipping
- Pre-game poller seed probe test
- NBA public splits preseason skip
- Pregame poller full board unchanged
- Pregame line poller kill switch
- Pre-game poller price map commit test
- Pregame line poller interval cost
- NHL off-season polling skip test
- Pregame line poller reseed schedule
- Pregame poller failed tick recovery
- Pregame line poller reseed interval
- Threshold review never unpauses
- Threshold review cannot write a pause
- Threshold review announce wording
- Scorer pause checks use one helper
- Threshold review tables kept private
- Postponed MLB games lookup
- Threshold review milestone
- Threshold review on or off switch
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
- Mobile app build scripts
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
- Calibration and NFL opener-wind docs
- NFL game lines model write-up
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
- mobile/docs/UX_REVIEW.md
- Monitoring and model quality notes
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
- NFL and college football search notes
- .claude/rules/frontend.md
- docs/health_checks.md
- docs/retrain_2026_plan.md
- Calibration and EV floor docs
- docs/reviews/2026-09-07-nfl-props-deep-dive.md
- docs/market_coverage.md
- (root): pr-ci + requirements
- docs/nfl_props_model.md
- NFL wind totals runbook and staking
- mobile/docs/BILLING.md
- docs/testing.md
- CLAUDE.md
- Game model starter gate notes
- NFL opener sharp-vs-soft findings

## God Nodes (most connected - your core abstractions)
1. `get_connection()` - 610 edges
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
- `2. Data used (all in Supabase)` --references--> `odds()`  [INFERRED]
  docs/nba_models_2026.md → tests/test_latest_line_state.py
- `3. The market grid` --references--> `odds()`  [INFERRED]
  docs/nba_models_2026.md → tests/test_latest_line_state.py
- `Things a reader should know` --references--> `shot_value()`  [INFERRED]
  docs/nba_pbp_stints.md → data/ingestors/nba_stints.py
- `4.3 Player props — one rule ships` --references--> `run_nba_prop_window()`  [INFERRED]
  docs/nba_models_2026.md → scheduler.py
- `Table` --references--> `over()`  [INFERRED]
  docs/nba_public_splits.md → mobile/scripts/verify_contrast_tokens.ts

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

## Communities (926 total, 223 thin omitted)

### Community 0 - "Injury report ingestion with WNBA fallback"
Cohesion: 0.07
Nodes (20): TestCoreTeamsFallback, _athlete_name(), _compute_return_ramp(), _espn_team_ids(), fetch_espn_injuries(), _fetch_espn_team_injuries(), fetch_mlb_transactions(), _fetch_nba_espn_team_ids() (+12 more)

### Community 1 - "Mobile stats board"
Cohesion: 0.01
Nodes (388): P, TouchSet, PlayerPropQuote, Sport, errorKind, gameStatus, HitRate, HitRateBandName (+380 more)

### Community 10 - "App feedback and support screens"
Cohesion: 0.07
Nodes (54): FeedbackCategory, FeedbackMessage, FeedbackSender, FeedbackStatus, FeedbackThread, Validation, Nav, Route (+46 more)

### Community 100 - "Live monitor API probe"
Cohesion: 0.04
Nodes (52): _Resp, _credits_from(), _drain(), _enqueue(), _flush_on_exit(), install(), instrumented(), _now() (+44 more)

### Community 101 - "Publish key identity tests"
Cohesion: 0.05
Nodes (23): _Conn, _KeyConn, _key(), _mobile(), _sql(), test_a_game_level_live_row_keeps_the_key_it_was_published_under(), test_a_game_level_row_keeps_the_key_it_was_published_under(), test_a_player_id_row_keeps_the_key_it_was_published_under() (+15 more)

### Community 104 - "Record correction posts to Discord"
Cohesion: 0.09
Nodes (22): LedgerUnread, Conn, delete_custom_record_post(), _jump(), _place(), _publish(), publish_full_record(), publish_full_record_standard() (+14 more)

### Community 113 - "tests/test_nfl_live_leader_gameday.py"
Cohesion: 0.05
Nodes (33): FakeClient, FakeClock, FakeConn, FakeFeed, _Rows, art(), live_state(), quote_payload() (+25 more)

### Community 114 - "nfl_live_leader/gameday.py"
Cohesion: 0.05
Nodes (35): ScoreClock, _Unset, Cadence, GameContext, LiveOddsFeed, Quote, LiveState, parse_book_ts() (+27 more)

### Community 115 - "tests/test_calibration_promotion.py"
Cohesion: 0.07
Nodes (26): FakeConn, eligibility_clause(), load_calibrations(), maps_materially_differ(), promote(), _payload(), _row(), test_a_broken_table_is_identity_maps_not_an_exception() (+18 more)

### Community 116 - "tests/test_score_off_any_book_line.py"
Cohesion: 0.09
Nodes (29): _FakeConn, _fallback_line_quote(), _cut(), _on(), _row(), _sql_const(), _src(), test_a_book_with_a_line_but_no_price_is_skipped() (+21 more)

### Community 118 - "NCAAF FBS team registry tests"
Cohesion: 0.06
Nodes (17): TestRefusalLog, TestRegistryHealthCheck, TestUnratedFbsClaim, fbs_refusal_claims(), unrated_fbs_claim(), _alarm_part(), hdb(), _live_db() (+9 more)

### Community 12 - "Mobile pick filters and sorting"
Cohesion: 0.02
Nodes (183): P, ActivePill, Props, Props, BacktestPickRow, DateOption, DayRow, SelectableGame (+175 more)

### Community 120 - "tests/test_ncaaf_alias_scores.py"
Cohesion: 0.10
Nodes (28): _FakeConn, alias_score_updates(), _date_or_none(), mirror_scores_to_alias_rows(), _cfbd(), _row(), test_a_bare_substring_is_not_an_extension(), test_a_daytime_game_has_no_duplicate_and_is_untouched() (+20 more)

### Community 121 - "Prop alternate line parsing tests"
Cohesion: 0.10
Nodes (18): _Conn, alt_markets_due(), _ou(), _parse(), test_a_failed_check_does_not_spend(), test_a_player_the_book_lists_at_1_5_keeps_the_0_5_alternate(), test_a_sport_with_no_alternates_never_asks(), test_a_standard_market_still_yields_one_row_per_player() (+10 more)

### Community 122 - "NFL prop odds loader slice tests"
Cohesion: 0.06
Nodes (22): _Conn, _Cur, TestPropOddsLoader, _Conn, _Cur, _fetch_slice(), _iter_prop_rows(), load_nfl_prop_odds() (+14 more)

### Community 123 - "tests/test_backtester.py"
Cohesion: 0.07
Nodes (9): TestCalibrationError, TestComputeBacktestSummary, TestEvaluateResult, TestGoLiveGateConstants, TestIterSides, _calibration_error(), compute_backtest_summary(), _evaluate_result() (+1 more)

### Community 124 - "NHL prop expected value lab"
Cohesion: 0.11
Nodes (9): TestRegimeOrder, main(), regime(), _cand(), _league(), _loose_summary(), s(), _name() (+1 more)

### Community 125 - "nfl/live_model/feeds/odds_live.py"
Cohesion: 0.07
Nodes (17): CreditMeter, LiveOddsClient, Quote, JsonlRecorder, best_price(), parse_events(), _parse_ts(), _side_of() (+9 more)

### Community 127 - "NHL props newest quote shopping"
Cohesion: 0.19
Nodes (5): TestWhoThePlayerIs, candidates(), draftkings_at(), identities(), upcoming_rows()

### Community 129 - "NBA prop market lab"
Cohesion: 0.09
Nodes (44): NBTable, add_units(), assemble(), best_per_key(), boot_ci(), build_quotes(), candidates_from(), choose_floor() (+36 more)

### Community 13 - "Discord pick notifier tests"
Cohesion: 0.02
Nodes (92): _FakeConn, _FakeResult, _Resp, _StampConn, _cand(), _et_now_iso(), _freeze_now(), _live_row() (+84 more)

### Community 131 - "nfl/live_model/tests/test_backup_snaps.py"
Cohesion: 0.09
Nodes (22): _FakeConn, _FakeCur, back_up(), digest(), _flush(), iter_files(), main(), _mb() (+14 more)

### Community 135 - "mobile/scripts: verify_book_links + verify_betslip_combine"
Cohesion: 0.06
Nodes (37): betslipCombineKind, combineBetMgm(), combineBetslipLinks(), combineCaesars(), combineDraftKings(), combineEspnBet(), combineFanDuel(), fanDuelPairs() (+29 more)

### Community 137 - "NBA official injury report parser"
Cohesion: 0.04
Nodes (45): Report, _Conn, _Cur, _DatesConn, _PdfFetcher, finish_rows(), match_player(), name_first_last() (+37 more)

### Community 138 - "tests/test_paused_keeps_real_verdict.py"
Cohesion: 0.05
Nodes (40): _Capture, _prop_bets_today(), _bet(), _bodies(), _code(), _dk(), _fn(), _game() (+32 more)

### Community 14 - "Best-price decision tests"
Cohesion: 0.05
Nodes (31): FakeConn, _decide(), _decision_fields(), _make_prop_pick(), _missing_price(), _requalify_at_best(), _size(), emit() (+23 more)

### Community 140 - "mobile/scripts/verify_contrast_tokens.ts"
Cohesion: 0.05
Nodes (41): Pair, code(), lum(), noGreen(), over(), ratio(), read(), readUtf8() (+33 more)

### Community 141 - "models/nhl_props.py"
Cohesion: 0.12
Nodes (22): Spec, _attach_teams(), build_frame(), build_goalie_frame(), build_skater_frame(), _ew(), excess_variance(), expected_value() (+14 more)

### Community 143 - "Pick lock after settlement tests"
Cohesion: 0.08
Nodes (22): _SqliteShim, conn(), _game(), _pick(), _survivors(), test_a_bet_is_never_dropped_for_an_earlier_no_signal(), test_a_dead_zone_prop_row_locks_too(), test_a_final_game_is_not_a_scoring_target() (+14 more)

### Community 144 - "NBA game line move study"
Cohesion: 0.07
Nodes (33): Data, attach(), big_home_dog_signal(), consensus(), control_specs(), coverage_text(), fade_side(), favourite_sides() (+25 more)

### Community 145 - "NBA prop market card publisher"
Cohesion: 0.10
Nodes (13): Plan, decided_games(), ensure_decisions_table(), games_with_a_bet(), load_roster(), main(), projection_holdings(), publish() (+5 more)

### Community 146 - "tests/test_mlb_game_market.py"
Cohesion: 0.08
Nodes (27): GameMarketBet, _SlateConn, find_spread_bets(), find_total_bets(), _gap_seconds(), _is_runline(), publish_enabled(), pick_rows() (+19 more)

### Community 150 - "Threshold review tests"
Cohesion: 0.12
Nodes (17): _Conn, _slate(), test_a_losing_model_with_enough_bets_is_flagged(), test_a_losing_model_with_too_few_bets_is_left_alone(), test_a_milestone_fires_only_once(), test_a_model_paused_in_config_is_not_reported_again(), test_a_profitable_model_is_never_touched(), test_an_already_paused_model_is_not_flagged_again() (+9 more)

### Community 152 - "Idle read transaction tests"
Cohesion: 0.07
Nodes (16): ViewMigrationResult, _Rec, apply_view_migrations(), _flat(), test_a_lock_timeout_fails_that_file_and_the_next_still_runs(), test_a_locked_bet_releases_the_lock_check(), test_a_quiet_tick_rolls_the_read_back(), test_a_tick_that_writes_does_not_roll_the_insert_back() (+8 more)

### Community 154 - "UFC phantom fight filter"
Cohesion: 0.21
Nodes (6): TestFilterUfcPhantom, TestIsKnownUfcMatchup, _filter_ufc_phantom(), _is_known_ufc_matchup(), _game(), _odds()

### Community 155 - "tests/test_prop_box_scores.py"
Cohesion: 0.12
Nodes (14): ScriptConn, ensure_prop_box_scores(), missing_prop_games(), _pick(), test_a_logged_game_is_not_fetched_and_a_goalie_gap_is(), test_a_probe_error_that_is_not_a_timeout_raises_after_rollback(), test_a_probe_timeout_rolls_back_and_returns_empty(), test_a_recent_nfl_attempt_is_not_repeated() (+6 more)

### Community 156 - "NBA game model prop feature tests"
Cohesion: 0.06
Nodes (40): _Stop, _box(), _g(), _games(), _inj(), _model(), _props(), _run() (+32 more)

### Community 157 - "In-play scorer and cut sweeps"
Cohesion: 0.03
Nodes (87): _RecordingConn, build_live_state_row(), _age_seconds(), expected_value(), _latest_live_state(), _live_bets_today(), _make_live_pick(), _pregame_features() (+79 more)

### Community 158 - "Best line and best-price decision tests"
Cohesion: 0.05
Nodes (34): FakeConn, TwoOrientationConn, _best_fields(), _best_game_price(), _best_of(), _best_prop_price(), _same_line(), _source() (+26 more)

### Community 160 - "Worker job queue claim and run"
Cohesion: 0.06
Nodes (23): _Conn, _DedupeConn, _fake(), test_a_busy_queue_claims_nothing(), fetchone(), test_a_declared_job_is_queued_once_however_often_it_is_read(), test_a_failing_job_is_requeued_until_the_attempt_cap(), _boom() (+15 more)

### Community 162 - "Database schema guard and brand avatar"
Cohesion: 0.06
Nodes (19): GuardConn, _ddl(), _dk_direct_feed(), _is_guarded(), _job_queue(), _modules_with_write_time_ddl(), _run_ledger(), test_ddl_still_runs_on_a_database_that_needs_it() (+11 more)

### Community 163 - "Discord results recap"
Cohesion: 0.04
Nodes (36): _Conn, _recap_row(), test_a_day_with_no_in_play_picks_says_nothing_about_it(), test_a_loss_costs_the_full_stake_and_a_push_costs_nothing(), test_a_pick_with_no_price_stays_in_the_units_at_bare_conviction(), test_a_restate_with_nothing_settled_late_is_a_no_op(), test_a_six_column_row_still_tallies(), test_a_snapshot_with_no_clv_stores_null_not_zero() (+28 more)

### Community 164 - "tests/test_nfl_opener.py"
Cohesion: 0.09
Nodes (11): TestFireWindow, TestFreshNumberLabel, TestHeldMinutes, TestModelCardSplit, _giants_board(), _giants_prior_at_2129(), _giants_sched(), _obs() (+3 more)

### Community 165 - "NHL stats and game log ingest"
Cohesion: 0.02
Nodes (90): TestLogRowBuilders, TestNoHollowTeamRowBeforeTheFirstGame, TestOddsFeedTeamNames, TestSeasonLabel, TestThreeWayMarketKey, _default_fetch(), fetch_espn_nhl_probables(), _https() (+82 more)

### Community 167 - "scripts/nfl_preflight.py"
Cohesion: 0.10
Nodes (21): TestRealSchema, TestSplitter, TestSqliteSchema, _load_postgres_schema(), _split_sql_statements(), check(), check_cards_run(), check_config_gates() (+13 more)

### Community 170 - "NBA game model luck feature tests"
Cohesion: 0.05
Nodes (39): _Stop, _against_bet(), _f6c_inputs(), _games_for_standings(), _gs(), _market_pricing(), _one_game_data(), _pair() (+31 more)

### Community 171 - "CLV math and devig functions"
Cohesion: 0.06
Nodes (29): _Conn, _Res, test_a_one_way_close_is_not_de_vigged(), test_a_worse_close_is_negative_and_equal_prices_are_zero(), test_devigging_the_taken_price_is_not_what_primary_does(), test_kalshi_close_is_not_de_vigged(), test_market_edge_devigs_only_the_close(), test_other_side_prices_include_the_draw_on_a_three_way() (+21 more)

### Community 174 - "tests/test_publisher_lock.py"
Cohesion: 0.07
Nodes (17): _Conn, _Result, _clear_locks(), _no_prod_threshold_sync(), _signal_row(), test_a_connection_that_cannot_lock_still_publishes(), test_an_exception_mid_publish_does_not_wedge_every_later_pass(), test_every_signal_publisher_takes_the_lock() (+9 more)

### Community 175 - "tests/test_dk_direct_feed.py"
Cohesion: 0.09
Nodes (23): _Conn, _game_id_for(), _row_for(), _seen_key(), _slate_dates(), _rec(), test_a_line_move_is_a_new_quote(), test_a_market_we_do_not_understand_is_dropped_not_guessed() (+15 more)

### Community 177 - "tests/test_credit_budget.py"
Cohesion: 0.09
Nodes (22): _Conn, daily_burn(), latest_remaining(), plan_credit_budget(), _burn_conn(), _plan(), test_a_billing_reset_is_not_a_refund(), test_a_call_is_billed_at_what_the_api_says_it_cost() (+14 more)

### Community 18 - "Mobile thresholds and sharp score"
Cohesion: 0.03
Nodes (74): Case, ContrarianTone, ModelClv, PublicTone, sharpScore, SharpScoreParts, ActionFilterable, ModelThreshold (+66 more)

### Community 181 - "Player news ingest"
Cohesion: 0.03
Nodes (54): NewsItem, NewsPlayer, FakeConn, FakeResponse, _Result, _article_url(), _athletes_in(), build_name_index() (+46 more)

### Community 19 - "NHL prop card publishing"
Cohesion: 0.05
Nodes (35): TestTonightsRowIsATrainingRow, TestWhoThePlayerIs, build_frame(), _ew(), expected_value(), fit(), load_skaters(), load_teams() (+27 more)

### Community 191 - "Sharp-price de-vig helpers"
Cohesion: 0.03
Nodes (64): MarketBet, TestNaNIsAbsent, devig(), find_bets(), implied(), card(), load_quotes(), _bets_from_kalshi() (+56 more)

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
Cohesion: 0.05
Nodes (27): FakeConn, _StubConn, resolve_feed_name(), _get_prop_dk_odds(), _latest_book_prop_row(), _latest_dk_prop_row(), test_accented_roster_name_matches_the_flat_feed_name(), test_ambiguity_is_a_miss_not_a_guess() (+19 more)

### Community 2 - "Mobile markets and formatting"
Cohesion: 0.01
Nodes (280): Row, Props, Props, Props, IoniconName, Props, clvBetQuote, ClvBetRow (+272 more)

### Community 203 - "tests/test_nhl_asof.py"
Cohesion: 0.19
Nodes (3): GoalieBook, TestGoalieAsOf, _g()

### Community 204 - "Shared database access and scripts"
Cohesion: 0.01
Nodes (190): TestTheStoreReadsTheStartTime, calibration_method(), scoring_method(), get_connection(), ladders(), ladders_or_empty(), ingest_pbp_for_game_id(), validate_sides() (+182 more)

### Community 205 - "NFL in-play game state feed"
Cohesion: 0.12
Nodes (18): CoreClient, EventMeta, _abbr(), game_seconds(), https(), _int(), is_admin_play(), is_conversion_play() (+10 more)

### Community 209 - "data/ingestors/nfl_inplay_history.py"
Cohesion: 0.16
Nodes (22): Budget, buy_halftime(), buy_inplay(), events_for(), _floor5(), _get(), halftime_requests(), halftime_windows() (+14 more)

### Community 21 - "App model list and detail screens"
Cohesion: 0.01
Nodes (318): EquityPoint, Props, Props, CustomBacktestPickRow, CustomBacktestSummary, CustomModelStats, ChipGroup, ChipKey (+310 more)

### Community 211 - "Mobile bankroll number formatting"
Cohesion: 0.09
Nodes (30): BankrollCheck, BankrollCommit, BankrollPatch, BankrollRead, NumberSeparators, Part, walk(), deviceSeparators() (+22 more)

### Community 212 - "App sign-in and sportsbook connection"
Cohesion: 0.02
Nodes (141): IoniconName, IoniconName, Slide, AuthState, AuthStatus, PushStatus, ConnectionMap, providerMeta (+133 more)

### Community 214 - "Health check skip budget tests"
Cohesion: 0.07
Nodes (17): FakeConn, _res(), _source_outside_the_budget_table(), test_a_check_never_seen_non_skipped_counts_its_whole_history(), test_a_check_skipped_only_today_is_not_counted_as_a_streak(), test_a_non_skipped_result_is_never_touched(), test_a_stuck_gate_escalates_past_its_budget(), test_an_honest_offseason_skip_stays_skipped_but_shows_its_length() (+9 more)

### Community 215 - "WNBA prop training and rebuild"
Cohesion: 0.03
Nodes (59): TestTrainingExcludesThemAndScoringDoesNot, training_feature_cols(), build_bulk_wnba_prop_lookups(), build_wnba_prop_scoring_rows(), build_wnba_prop_training_dataset(), _opp_team_stat(), _recent_starter(), _rolling_avg() (+51 more)

### Community 217 - "NCAAF in-play engine and pick lock"
Cohesion: 0.05
Nodes (22): LiveEngine, FakeConn, _Rows, american_to_prob(), devig_power(), write_picks(), expected_value(), _is_paused() (+14 more)

### Community 22 - "NBA prop projection model and card"
Cohesion: 0.02
Nodes (121): ProjectionBet, Spec, asof_roster(), box_from_log(), collapse_official(), compact_report(), espn_compact(), minutes_cols() (+113 more)

### Community 220 - "tests/test_db_reconnect.py"
Cohesion: 0.10
Nodes (14): _Conn, _Cursor, _lost(), test_a_committed_transaction_is_clean_again(), test_a_lost_connection_with_uncommitted_writes_raises_connection_lost(), test_a_read_on_a_lost_connection_reconnects_and_retries(), test_a_statement_timeout_is_not_a_lost_connection(), test_a_wrapper_without_a_url_cannot_reconnect_and_re_raises() (+6 more)

### Community 222 - "NHL derivative totals card tests"
Cohesion: 0.10
Nodes (11): _Meter, _Resp, main(), run(), _markets(), test_apply_and_probe_without_a_key_return_before_any_call(), test_card_writes_nothing_and_the_pipeline_does_not_call_it(), test_parser_splits_team_totals_and_keeps_every_alternate_line() (+3 more)

### Community 223 - "In-play pick lock tests"
Cohesion: 0.11
Nodes (19): FakeConn, _Rows, _lane_signature(), _write_live_picks(), _locked_live_lanes(), _log_lines(), _pick(), test_a_locked_lane_still_says_so_and_names_the_lane() (+11 more)

### Community 225 - "tests/test_refresh_retry.py"
Cohesion: 0.14
Nodes (23): RefreshRun, _decide(), _done(), _run(), test_a_failed_view_migration_fails_the_step(), test_a_pass_that_finished_with_failed_steps_ran_its_chain(), test_a_redeploy_between_passes_replaces_nothing(), test_a_restart_loop_does_not_buy_odds_on_every_boot() (+15 more)

### Community 226 - "NBA results and lineup segments store"
Cohesion: 0.14
Nodes (5): PgStore, _games(), _schedule(), _opp(), end()

### Community 228 - "NBA results ingestor tests"
Cohesion: 0.06
Nodes (31): PlayerResolver, _Conn, _ESPN, FakeStore, _FixedNow, build_dnp_rows(), build_log_rows(), fallback_id() (+23 more)

### Community 23 - "NBA game projection rebuild script"
Cohesion: 0.03
Nodes (91): EW, Last, Model, PointInputs, State, World, actuals(), apply_models() (+83 more)

### Community 230 - "tests/test_local_cache_is_additive.py"
Cohesion: 0.10
Nodes (13): _FakeConn, main(), _merge_with_cache(), _pull_odds(), _pull_seasoned(), _register_from_feature_engine(), cached(), _frame() (+5 more)

### Community 231 - "tests/test_calibration_check_coverage.py"
Cohesion: 0.12
Nodes (17): _Shim, _bet(), _calibration_results(), db(), _graded(), _make_db(), _only(), _promote() (+9 more)

### Community 233 - "tests/test_book_team_map.py"
Cohesion: 0.11
Nodes (13): _Conn, abbr_from_team_string(), test_a_non_mlb_sport_is_refused_rather_than_guessed(), test_a_string_with_no_at_sign_is_refused(), test_a_unique_game_resolves(), test_an_ambiguous_game_resolves_to_none(), test_an_unrecognised_club_is_refused_not_guessed(), test_draftkings_and_bovada_formats_resolve_the_same() (+5 more)

### Community 234 - "tests/test_team_board_cache.py"
Cohesion: 0.08
Nodes (10): _Conn, _Cursor, team_board_pairs(), team_board_seasons(), _cols(), test_every_team_sport_gets_last_this_and_next_year(), test_one_failing_pair_does_not_stop_the_rest(), test_the_cache_the_refresh_and_the_thin_function_name_the_same_columns() (+2 more)

### Community 238 - "nfl/live_model/tests/test_rush_attempt_pace.py"
Cohesion: 0.07
Nodes (21): Read, pace_ratio(), _sigmoid(), under_prob(), _price(), test_a_line_he_has_already_passed_is_not_a_live_proposition(), test_a_missing_accrued_count_is_refused_not_treated_as_zero(), test_a_reachable_over_is_declined_rather_than_faded() (+13 more)

### Community 239 - "tests/test_nfl_poll_fast_silence.py"
Cohesion: 0.11
Nodes (15): FakeConn, publish_board(), _append_board(), _body(), _row(), _sent(), _setup(), test_a_half_written_last_row_waits_for_the_next_tick() (+7 more)

### Community 24 - "NHL moneyline and market research labs"
Cohesion: 0.03
Nodes (125): OffsetLogit, accuracy(), first_games(), logloss(), main(), sweep(), units(), walk() (+117 more)

### Community 245 - "tests/test_nhl_asof.py"
Cohesion: 0.13
Nodes (4): TeamBook, TestBlendedTeamInputs, TestTeamRatesAsOf, _r()

### Community 247 - "tests/test_dk_freshness_parse.py"
Cohesion: 0.12
Nodes (17): _FakeConn, _FakeResult, _american(), parse_dk_payload(), _store(), _payload(), test_a_half_priced_market_is_dropped_rather_than_half_recorded(), test_an_event_with_no_markets_yields_nothing_rather_than_raising() (+9 more)

### Community 248 - "NBA historical odds gap backfill"
Cohesion: 0.08
Nodes (22): ConnectionLost, _Ledger, _Meter, _Resp, gap_instants(), line_snapshots(), _hourly(), _t() (+14 more)

### Community 249 - "models: slate_concentration + test_slate_concentration"
Cohesion: 0.15
Nodes (15): SlateConcentration, apply_slate_guard(), apply_slate_concentration_guard(), _attr(), _edge_of(), _is_bet(), measure_side_concentration(), _side_of() (+7 more)

### Community 251 - "View migration lock handling tests"
Cohesion: 0.07
Nodes (25): _Conn, _Deadlock, _LockTimeout, _StatementTimeout, _Syntax, execute(), _before(), _code() (+17 more)

### Community 254 - "Publisher and injury fetch test fakes"
Cohesion: 0.05
Nodes (11): FakeConn, _R, test_the_prop_fetch_never_buys_a_game_it_was_not_given(), execute(), test_discord_free_pick_candidates_refuse(), execute(), fetchall(), row() (+3 more)

### Community 255 - "NCAAF in-play history backtest"
Cohesion: 0.06
Nodes (31): _Conn, _StubEngine, build_candidates(), decide(), first_signals(), _fmt(), grade(), load_snapshots() (+23 more)

### Community 258 - "Deploy checks and worker job queue"
Cohesion: 0.07
Nodes (17): _Conn, test_a_declared_job_carries_its_run_after(), test_a_failing_check_raises_so_the_queue_announces_it(), test_a_job_can_only_name_a_registered_check(), test_enqueue_rejects_a_naive_run_after(), test_enqueue_stores_run_after(), test_every_check_is_read_only(), test_the_claim_waits_for_run_after() (+9 more)

### Community 26 - "Mobile teams board and team detail"
Cohesion: 0.03
Nodes (133): Props, NextGame, Section, HitSelection, HitDirection, BasketballGroup, PlayerSummary, PositionGroup (+125 more)

### Community 265 - "Best line threshold sweep"
Cohesion: 0.07
Nodes (22): _Conn, american_to_decimal(), analyse(), split(), _basis(), _cut(), fetch(), units_at() (+14 more)

### Community 266 - "NBA official injury report ingestor"
Cohesion: 0.07
Nodes (36): Fetcher, _Fetcher, _all_slots(), _ampm(), content_hash(), ensure_tables(), garbled_note(), load_players() (+28 more)

### Community 269 - "NCAAF college data ingest tests"
Cohesion: 0.07
Nodes (8): _GamesConn, _TeamsConn, test_ingest_games_retains_a_historical_utc_id_and_uses_et_for_a_new_row(), fake_get(), test_ingest_pulls_fbs_then_everyone_and_fbs_rows_win(), test_ingest_retries_everyone_without_a_year_if_the_season_filter_is_empty(), test_prior_context_tolerates_missing_talent_and_returning(), test_weekly_snapshot_build_aborts_on_failed_fetch()

### Community 27 - "Mobile betslip and parlay legs"
Cohesion: 0.02
Nodes (164): ResolvedSlip, GameLineLegSpec, GameLineMarket, LineLegSpec, LineSide, PropLineLegSpec, MarketClass, BestBookPrice (+156 more)

### Community 273 - "tests/test_prop_odds_utc_stamp.py"
Cohesion: 0.12
Nodes (13): _Conn, _assert_utc_stamp(), _frozen(), _run_mlb(), capture(), events(), _run_ncaaf(), test_an_eastern_row_then_a_later_utc_row_sorts_in_time_order() (+5 more)

### Community 274 - "Live monitor web server"
Cohesion: 0.29
Nodes (4): Handler, _connect(), dumps(), _json_default()

### Community 277 - "NFL publisher lookahead and key tests"
Cohesion: 0.08
Nodes (15): _Conn, _sql_for(), test_a_started_game_is_still_never_published(), test_both_publishers_apply_the_apps_action_filter(), test_both_publishers_read_the_table_the_app_reads(), test_capture_reaches_as_far_as_the_poller_can_write(), test_capture_reaches_forward_for_the_locked_lookahead_sports(), test_ncaaf_lookahead_is_only_safe_because_the_lock_is_general() (+7 more)

### Community 278 - "tests/test_feature_artifact_agreement.py"
Cohesion: 0.11
Nodes (13): _Stub, _TolerantUnpickler, _load(), _newest_artifact(), test_artifact_width_matches_its_own_feature_cols(), test_config_list_matches_the_trained_artifact(), test_known_drift_only_names_real_models(), test_pending_features_are_not_live_without_a_retrain() (+5 more)

### Community 279 - "NFL prop market one side per line"
Cohesion: 0.14
Nodes (9): _Conn, best_per_prop(), select_prop(), _hockenson(), test_a_different_market_on_the_same_player_is_still_its_own_bet(), test_input_order_does_not_decide_the_side(), test_nfl_publish_will_not_add_the_other_side_of_a_locked_line(), test_opposite_sides_of_one_line_collapse_to_the_bigger_edge() (+1 more)

### Community 28 - "CLV graded at the price taken"
Cohesion: 0.07
Nodes (22): _Conn, _Res, _fn(), _migration(), _pick(), test_a_draftkings_decided_row_is_unchanged(), test_a_legacy_row_that_cannot_be_re_measured_leaves_the_old_method(), test_a_legacy_stamped_row_is_re_measured_and_leaves_the_queue() (+14 more)

### Community 281 - "tests/test_cloud_retrain_artifacts.py"
Cohesion: 0.10
Nodes (12): _Conn, _restore_artifact(), test_a_failed_upload_does_not_lose_a_model_that_trained(), test_a_missing_artifact_table_is_not_an_error_on_restore(), test_a_no_register_run_stores_nothing(), test_load_model_actually_loads_from_the_store_when_the_file_is_gone(), fetchone(), test_load_model_returns_none_when_the_store_has_nothing_either() (+4 more)

### Community 282 - "NHL totals card writer"
Cohesion: 0.07
Nodes (22): _LockConn, _SlateConn, _lock_model(), main(), pick_rows(), publish(), render(), run_card() (+14 more)

### Community 285 - "System health and published record checks"
Cohesion: 0.05
Nodes (28): HealthReport, ncaaf_season_for_date(), test_january_games_belong_to_the_prior_season(), test_a_pick_before_the_live_date_is_caught_in_either_view(), test_a_sport_missing_from_the_daily_view_is_caught(), test_an_empty_record_is_not_a_problem(), test_cent_level_agreement_is_required(), test_same_picks_but_different_money_is_caught() (+20 more)

### Community 288 - "tests/test_nfl_opener.py"
Cohesion: 0.20
Nodes (5): TestBettableBooksOnly, TestSelectOpenerBets, _both_sides(), _frame(), _sched()

### Community 291 - "NFL prop data parsing tests"
Cohesion: 0.11
Nodes (10): TestGamesRows, TestKickoff, TestParseTeamRows, TestUpcomingRows, games_rows(), _int_or_none(), _kickoff_utc(), _num_or_none() (+2 more)

### Community 295 - "Discord pick posting and restates"
Cohesion: 0.02
Nodes (75): DiscordVoidRejected, UnitStake, _restate_env(), _restate_signals(), test_a_failed_restate_ledgers_nothing_so_it_retries(), test_a_malformed_timestamp_drops_the_stamp_rather_than_raising(), test_a_rate_limited_restate_leaves_nothing_half_posted(), test_american_odds_formatting() (+67 more)

### Community 298 - "tests/test_nfl_wind_publisher.py"
Cohesion: 0.13
Nodes (10): TestBuildRows, TestKickFields, TestParseMatchup, build_rows(), _fmt_line(), kick_fields(), parse_matchup(), test_nfl_wind_and_opener_rows_drop_a_bet_under_the_floor() (+2 more)

### Community 3 - "Odds feed fetching and quota tracking"
Cohesion: 0.01
Nodes (198): Meter, Meter, Meter, TestEveryOtherSportStillMintsItsOwn, TestNflResolvesOntoTheSchedule, TestTheResolverFailsClosed, FakeResp, build_ncaaf_game_id() (+190 more)

### Community 30 - "NFL live prop model tests"
Cohesion: 0.04
Nodes (37): Read, _FakeOdds, _IdRecordingOdds, blind_over_prob(), over_prob(), _pass_attempt_bias_allowed(), _core_worker(), test_a_deployed_bias_must_sit_inside_its_measured_interval() (+29 more)

### Community 300 - "tests/test_health_reason_and_cadence.py"
Cohesion: 0.09
Nodes (20): Report, _one(), test_a_24h_ts_check_reads_as_daily(), test_a_bare_add_still_fills_both_columns(), test_a_broken_query_is_its_own_reason(), test_a_late_check_says_how_late(), test_a_passing_check_says_fresh(), test_a_skipped_check_says_the_gate_was_shut() (+12 more)

### Community 301 - "tests/test_live_publish_parity.py"
Cohesion: 0.17
Nodes (12): _Conn, _db(), _labels(), _pick(), test_a_bet_written_while_paused_is_not_announced_after_an_unpause(), test_a_live_health_state_still_publishes(), test_a_paused_model_is_not_announced(), test_a_retired_model_is_not_announced() (+4 more)

### Community 302 - "tests/test_nfl_weather_supabase_readback.py"
Cohesion: 0.13
Nodes (13): FakeConn, _patch_conn(), _rows(), test_a_null_requested_lead_is_not_returned(), test_a_one_lead_response_is_not_stored(), test_a_partial_window_is_not_returned(), test_a_store_failure_is_a_warning_not_an_error(), test_a_subset_of_leads_reads_only_those_columns() (+5 more)

### Community 306 - "College football feature tests"
Cohesion: 0.11
Nodes (15): AdjRatings, blended_rating(), fit_opponent_adjustment(), _synth(), test_blend_falls_back_when_one_side_missing(), test_blend_weights_move_from_prior_to_current(), test_confounded_home_assignment_plus_heavy_alpha_corrupts_hfa(), test_features_for_dedupes_and_preserves_order() (+7 more)

### Community 307 - "Pregame line poller change tests"
Cohesion: 0.09
Nodes (28): _PollConn, changed_rows(), _fingerprint(), _key(), last_known_prices(), over_credit_cap(), poll_once(), quoted_keys() (+20 more)

### Community 308 - "Pitcher stats as-of invariant tests"
Cohesion: 0.05
Nodes (36): _FakeConn, last3_rates(), outs_from_ip(), per_nine(), whip(), already_a_series(), appearances(), _avg_distinct() (+28 more)

### Community 312 - "NHL props card slate tests"
Cohesion: 0.09
Nodes (10): TestTheBacktestGradesTheRuleTheCardPlays, TestTheCard, TestTheLimitPerGame, implied(), best_bet(), limit_per_game(), pick_rows(), render() (+2 more)

### Community 314 - "Pipeline log reason tests"
Cohesion: 0.22
Nodes (6): _Conn, _capture(), test_a_false_step_records_the_last_error_it_logged(), test_a_false_step_that_logged_nothing_still_says_so(), test_a_raising_step_still_records_the_exception(), test_the_sink_is_removed_after_the_step()

### Community 316 - "Stats and prop data ingest"
Cohesion: 0.03
Nodes (51): TestParsePlayerRows, TestParseNflverseScores, backfill_savant_stats(), _df_to_rows(), _fetch_pitcher_gb_pct(), _fetch_savant_csv(), _get_col(), _normalize_name() (+43 more)

### Community 32 - "NCAAF in-play score distribution pricing"
Cohesion: 0.03
Nodes (56): ScoreDistribution, _cluster_bootstrap(), evaluate(), main(), report(), fit(), load_states(), main() (+48 more)

### Community 320 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.09
Nodes (6): _Pg, _PgCursor, TestPreflightCiMode, wind(), wrapped(), fake_open()

### Community 321 - "System health signal delivery tests"
Cohesion: 0.07
Nodes (9): _FrozenDatetime, TestHealthCheckIsNotCountedAsAFailingStep, TestPassCompletion, TestPassSteps, TestSignalDelivery, _add_run(), _add_signal(), _iso() (+1 more)

### Community 322 - "X results job and cursor wrapper tests"
Cohesion: 0.10
Nodes (7): _CursorResult, execute(), test_a_malformed_date_is_refused_before_anything_runs(), test_the_cursor_wrapper_rowcount_is_the_cursors(), test_the_job_does_not_bypass_the_day_is_over_guard(), test_the_job_does_not_read_rowcount_off_the_cursor(), test_the_job_only_clears_its_own_ledger_kind()

### Community 323 - "NBA prop window scheduling tests"
Cohesion: 0.12
Nodes (21): _PlanConn, _fires(), _game(), _jobs(), _plan(), _t(), test_a_projection_too_old_to_price_does_not_block_the_retry(), test_a_tick_fetches_exactly_the_window_games_then_decides_closes_and_publishes() (+13 more)

### Community 327 - "NHL totals market model"
Cohesion: 0.09
Nodes (21): NhlTotalBet, _coherent(), _fetch_ts(), find_bets(), load_fetch_quotes(), _ts(), _two_way(), test_nhl_totals_card_drops_a_bet_under_the_floor() (+13 more)

### Community 33 - "nfl/live_model/feeds: test_feed_resilience + espn"
Cohesion: 0.04
Nodes (52): _ScriptedTick, _competitors(), _deref(), fetch_live_events(), _https(), make_fetcher(), fetch(), parse_core_event() (+44 more)

### Community 330 - "NFL opener card rows"
Cohesion: 0.13
Nodes (8): TestBuildOpenerRows, TestPublishOpenerInsertOnce, build_opener_rows(), _opener_model(), publish_opener(), _card_row(), _row(), execute()

### Community 334 - "In-play score change guard"
Cohesion: 0.13
Nodes (12): _FakeConn, _book_move(), _get_live_dk_odds(), _score_changed_at(), _odds(), test_a_quote_published_before_the_score_is_declined(), test_a_quote_republished_after_the_score_is_kept(), test_the_age_bound_alone_would_have_allowed_it() (+4 more)

### Community 336 - "NBA prop rule card tests"
Cohesion: 0.11
Nodes (15): NbaPropBet, NbaPropDecision, _PublishConn, pick_label(), pick_rows(), _bet(), _decision(), test_a_bet_at_draftkings_carries_no_best_columns() (+7 more)

### Community 34 - "Kalshi prop ladders and game markets"
Cohesion: 0.06
Nodes (25): Ladder, Rung, _expit(), from_kalshi(), from_one_sided_overs(), _logit(), _monotone(), _ladder() (+17 more)

### Community 341 - "NFL prop rule with Kalshi tests"
Cohesion: 0.11
Nodes (11): TestMarketRelative, find_bets(), _ladder(), test_a_replay_never_prices_off_todays_ladder_even_when_on(), test_fetch_helper_swallows_errors(), test_kalshi_is_not_graded_until_settled_history_exists(), test_kalshi_outside_the_ladder_is_refused_not_extrapolated(), test_kalshi_prices_a_line_pinnacle_cannot() (+3 more)

### Community 342 - "tests/test_live_pick_features.py"
Cohesion: 0.09
Nodes (16): FakeConn, _record_live_features(), _calibrated(), _pick(), test_a_live_bet_records_its_feature_row_and_lambda(), test_a_pick_with_no_feature_row_is_skipped_not_written_empty(), test_a_recorder_failure_is_rolled_back_to_its_savepoint(), test_a_recorder_failure_is_swallowed_rather_than_raised() (+8 more)

### Community 348 - "Pregame price age tests"
Cohesion: 0.04
Nodes (28): _BoardConn, _OddsConn, _ShopConn, _TwoIdConn, _UfcBoardConn, _get_dk_odds(), _swap_home_away(), _ago() (+20 more)

### Community 349 - "tests/test_prop_missing_features.py"
Cohesion: 0.14
Nodes (5): TestARowMissingAFeatureIsNotScored, TestEveryPropLoopGoesThroughTheHelper, TestTheUmpireIsTheDeclaredException, _frame(), helper()

### Community 350 - "MLB public fade top picks ranking"
Cohesion: 0.15
Nodes (16): PublicFadeBet, composite_score(), estimated_edge(), rank_score(), select_top_k(), _key(), ticket_money_gap(), ev_of() (+8 more)

### Community 353 - "MLB game line rule card"
Cohesion: 0.12
Nodes (11): TestQuarterKelly, _get_public_betting(), quarter_kelly(), main(), publish(), render(), run_both(), run_card() (+3 more)

### Community 354 - "NBA prop closing line tests"
Cohesion: 0.09
Nodes (11): _Conn, _Resp, test_a_close_already_held_is_not_bought_again(), test_a_due_close_buys_one_call_of_the_bet_markets_and_reports_its_credits(), test_a_pass_outside_the_window_spends_nothing(), test_only_a_game_holding_a_bet_and_only_once(), test_only_twelve_to_twenty_five_minutes_before_tip(), test_the_ten_minute_evening_passes_always_land_one_inside() (+3 more)

### Community 355 - "NFL in-play pick writer"
Cohesion: 0.02
Nodes (63): PicksRecorder, _AvoidConn, _Conn, _Decision, _OpenConn, announce_live_picks(), build_pick(), _is_market_opinion() (+55 more)

### Community 357 - "NFL wind scored row building"
Cohesion: 0.09
Nodes (9): TestBuildScoredRows, TestPickEmLabel, TestPreflightLockChecks, TestQualifyingRowIsNotANoneRow, _american_to_prob(), build_scored_rows(), _fmt_spread(), latest_eval_rows() (+1 more)

### Community 359 - "NHL moneyline anchored model"
Cohesion: 0.05
Nodes (31): OffsetLogit, _Fixed, _GamesConn, _add_rating(), build_inputs(), choose_C(), decision_window(), fit() (+23 more)

### Community 36 - "NCAAF CFBD ingestor tests"
Cohesion: 0.03
Nodes (59): _NullConn, _day_before(), eastern_game_date(), _local_aggregates(), parse_games(), parse_lines(), retain_existing_cfbd_ids(), shrink_to_prior() (+51 more)

### Community 360 - "Walk-forward evaluation tests"
Cohesion: 0.11
Nodes (11): _Cols, _Frame, walk_forward(), _fake(), test_a_fold_with_too_little_history_is_skipped(), test_a_single_class_test_season_is_skipped(), _frame(), test_every_fold_trains_only_on_earlier_seasons() (+3 more)

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
Cohesion: 0.04
Nodes (50): Diagnostics, _Seg, alias_play_ids(), roster_from_plays(), _accumulate(), _add_one(), _and_one_follows(), appearances() (+42 more)

### Community 370 - "UFC stats ingest"
Cohesion: 0.02
Nodes (115): _FakeConn, _IngestConn, _aggregate_stats(), backfill_ufc_csv(), build_events(), build_fighter_index(), _cached_etag(), _etag_cache_path() (+107 more)

### Community 371 - "Team stats rebuild checks"
Cohesion: 0.03
Nodes (52): _SeasonConn, already_a_series(), build_rows(), _games(), impossible_games_played(), live_season_snapshot_grace(), main(), _played_actual() (+44 more)

### Community 376 - "In-play calibrated decision tests"
Cohesion: 0.09
Nodes (16): RecordingConn, fetch_graded(), _cut(), _signal(), test_a_big_enough_claim_still_fires_after_calibration(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(), test_a_hot_live_model_no_longer_fires_the_marginal_bet(), test_a_live_model_is_read_out_of_picks_not_the_matview() (+8 more)

### Community 378 - "NFL DraftKings line snapshots"
Cohesion: 0.08
Nodes (13): TestDkLineRows, TestPublishLineSnapshots, TestSnapshotRowParams, append_snapshot_csv(), dk_line_rows(), dump_dk_lines(), _num(), snapshot_schedule() (+5 more)

### Community 38 - "Sharp book odds retention in pruning"
Cohesion: 0.09
Nodes (12): _RecordingConn, _prop_reference_books(), protected_for(), test_a_shopping_book_is_still_prunable(), test_every_prop_reference_book_is_protected(), test_every_sharp_book_is_protected_in_the_prop_table(), test_pinnacle_specifically_is_protected_in_the_prop_table(), test_prune_table_binds_the_prop_tables_carve_out_into_the_DELETE() (+4 more)

### Community 380 - "Price conversion and side tables"
Cohesion: 0.11
Nodes (10): TestAmericanToDecimalScorer, _backtest_ufc_fight(), _emit(), american_to_decimal(), build_side_table(), _fetch_games(), main(), _pregame_odds() (+2 more)

### Community 381 - "tests/test_heartbeat_disabled_jobs.py"
Cohesion: 0.14
Nodes (8): Conn, _build(), test_a_job_marked_disabled_is_not_silent(), test_a_job_that_runs_here_is_not_marked(), test_a_service_leaves_alone_the_jobs_another_service_owns(), test_startup_marks_an_owned_job_that_is_switched_off(), ensure_schema(), stale_jobs()

### Community 385 - "Scorer any-book game line fallback"
Cohesion: 0.07
Nodes (35): _Clf, _GameOddsConn, TestMissingStarterGate, _anchored_probability(), _fallback_game_line_quote(), _get_scoring_odds(), _has_real_game_price(), _make_pick() (+27 more)

### Community 387 - "tests/test_repair_bogus_first_pitch_labels.py"
Cohesion: 0.13
Nodes (8): _Conn, _run(), test_a_dry_run_writes_nothing_at_all(), test_a_short_backup_rolls_back_and_relabels_nothing(), test_the_backup_is_written_before_the_update(), test_the_backup_table_is_revoked_from_the_public_roles(), test_the_bogus_set_is_computed_never_listed(), test_the_query_is_scoped_to_the_scheduled_start_not_the_derived_one()

### Community 39 - "nfl/live_model/tests/test_executor.py"
Cohesion: 0.06
Nodes (47): Decision, Executor, derivative_lag(), ev_floor(), _mk(), expected_value(), honest_probability(), is_hunt_state() (+39 more)

### Community 392 - "Discord in-play pick rendering"
Cohesion: 0.10
Nodes (14): _FakeConn, paused_row_exclusion_sql(), test_a_live_price_is_stamped_with_when_it_was_taken(), test_a_pick_with_no_write_time_renders_without_a_stamp(), test_producer_output_builds_a_live_embed(), test_producer_output_renders(), test_producer_select_and_dict_stay_in_step(), test_renderer_survives_a_missing_context_field() (+6 more)

### Community 393 - "tests/test_sbr_loader.py"
Cohesion: 0.14
Nodes (3): _SqliteConnShim, _SqliteCursorShim, loader_conn()

### Community 397 - "mobile/scripts/ux_scan.mts"
Cohesion: 0.16
Nodes (18): Finding, Severity, changedFiles(), entitlementGate(), fontScaling(), fontSizeLiterals(), hexColors(), main() (+10 more)

### Community 398 - "NFL prop stat distributions"
Cohesion: 0.14
Nodes (6): TestBinaryMarket, TestCountDistributions, TestYardageDistribution, _nfl_prop_probs(), _art(), test_nb_head_changes_probs_only_when_nb_r_present()

### Community 4 - "Pre-game scorer and pick writing"
Cohesion: 0.03
Nodes (66): TestPushAdjustment, today_et(), load_sport_injury_index(), relevant_players(), _apply_game_injury_gate(), _run(), _apply_game_market_gate(), _best_game_price_one() (+58 more)

### Community 409 - "mobile/src/lib/otaUpdate.ts"
Cohesion: 0.20
Nodes (13): Calls, CheckState, CheckTrigger, UpdateOutcome, UpdatesApi, check(), fakeApi(), main() (+5 more)

### Community 41 - "tests/test_live_quote_staleness.py"
Cohesion: 0.05
Nodes (41): _Conn, _Q, build_row(), _mark_written(), _publish_key(), quote_from_nfl_quotes(), record_live_prices(), rows_from_quote() (+33 more)

### Community 411 - "College football search validation"
Cohesion: 0.17
Nodes (11): FoldResult, brier(), calibration_curve(), clv_report(), ece(), kelly_stake(), log_loss(), market_only_sanity() (+3 more)

### Community 419 - "App push links and sport filter"
Cohesion: 0.16
Nodes (18): NavRef, PushRoute, PicksView, clearNativeLastResponse(), navigateTo(), responseIdentifier(), usePushDeepLink(), load() (+10 more)

### Community 422 - "NBA prop settlement stats tests"
Cohesion: 0.11
Nodes (9): _SelectConn, test_a_missing_stat_is_none_not_zero(), test_a_turnovers_bet_on_a_player_who_played_settles_win_not_no_action(), test_combo_markets_are_mapped_to_helpers_and_only_the_nba_rule_uses_them(), test_double_double_matches_the_rule_it_replaced(), test_the_loader_carries_every_stat_a_market_settles_on(), test_the_loader_selects_turnovers(), _load_nba_prop_actuals() (+1 more)

### Community 423 - "Pipeline report with per-section rollback"
Cohesion: 0.16
Nodes (5): _Conn, _rows(), test_a_failed_query_rolls_back(), test_every_section_is_still_present(), test_one_broken_section_does_not_break_the_rest()

### Community 424 - "supabase/functions/_shared/discord.ts"
Cohesion: 0.20
Nodes (15): DiscordApiError, DiscordUser, RoleSyncResult, addAppRole(), addGuildMember(), botFetch(), expectOk(), isGuildMember() (+7 more)

### Community 429 - "NFL weather edge study"
Cohesion: 0.08
Nodes (28): DailyLimit, Pacer, audit(), baseline(), bh(), boot(), classify(), era() (+20 more)

### Community 43 - "Worker job queue validation tests"
Cohesion: 0.03
Nodes (49): _VoidConn, _posted_row(), _quiet(), _run_void(), _run_void_job(), test_a_failed_job_needs_a_new_key_to_rerun(), test_a_graded_pick_is_refused_not_rewritten(), test_a_pick_that_does_not_exist_is_reported_as_missing() (+41 more)

### Community 439 - "NBA totals card ledger and label tests"
Cohesion: 0.13
Nodes (10): Decision, TotalLuckBet, _Conn, _Cur, pick_rows(), _bet(), test_a_bet_under_the_ev_floor_is_refused(), test_a_decided_game_is_never_decided_again() (+2 more)

### Community 440 - "MLB prop pre-game quote tests"
Cohesion: 0.12
Nodes (7): _Conn, test_a_game_with_no_cutoff_fails_open(), test_both_market_relative_loaders_bound_on_the_cutoff(), test_it_compares_parsed_timestamps_not_strings(), test_it_joins_games_and_uses_the_shared_cutoff(), test_the_newest_qualifying_quote_still_wins(), test_the_post_first_pitch_quote_is_dropped_even_though_it_is_newest()

### Community 445 - "NFL CLV backtest and feature build"
Cohesion: 0.15
Nodes (9): ShrunkEnsemble, add_form(), build(), feature_columns(), market_features(), team_game_stats(), fmt(), main() (+1 more)

### Community 446 - "MLB doubleheader twin game merge"
Cohesion: 0.09
Nodes (15): _Conn, _fetchone(), schema_is_current(), store(), apply_one(), canonical(), counts(), main() (+7 more)

### Community 448 - "tests/test_discord_channel_probe.py"
Cohesion: 0.17
Nodes (7): _Resp, test_the_probe_covers_the_per_sport_live_channels(), test_the_probe_never_posts_and_never_returns_the_url(), test_the_probe_reports_the_channel_behind_each_sport(), _get(), test_two_sports_sharing_a_channel_are_flagged(), _job_discord_probe()

### Community 45 - "tests/test_nfl_prop_one_read_per_game.py"
Cohesion: 0.06
Nodes (25): _Conn, _Log, publish_hour_missed(), publishable_games(), _at(), _games(), test_a_game_is_publishable_on_exactly_one_pass_in_its_window(), test_a_game_with_no_kickoff_is_never_published() (+17 more)

### Community 457 - "Voided and restated pick tests"
Cohesion: 0.10
Nodes (9): _Conn, _producer(), test_a_restated_pick_still_names_the_cheaper_book(), test_a_worse_price_elsewhere_never_replaces_draftkings(), test_both_signal_producers_select_the_better_price(), test_the_locked_producer_maps_the_columns_into_the_dict(), _db(), test_a_voided_pick_is_not_a_free_pick_candidate() (+1 more)

### Community 460 - "Discord recap restatement"
Cohesion: 0.08
Nodes (16): _Conn, test_a_restated_recap_is_labelled_and_says_why(), _resp(), test_a_404_is_an_answer_not_a_retry(), test_a_persistent_403_still_raises_after_the_last_attempt(), test_a_recap_whose_count_merely_drifted_is_not_due(), test_a_recap_with_a_late_settlement_is_due(), test_a_transient_403_is_retried_and_the_second_answer_is_used() (+8 more)

### Community 466 - "Mobile billing, paywall and sign-in"
Cohesion: 0.04
Nodes (111): AccessState, useAccess, useAuth, useEntitlement, useSubscription, BillingDisabledError, CheckoutResult, BillingRail (+103 more)

### Community 469 - "Multi-book odds and pruning"
Cohesion: 0.05
Nodes (28): _OddsConn, _Resp, _older_than(), _odds_query(), _prop_markets(), _source(), test_a_game_with_no_commence_time_keeps_every_row(), test_a_rejected_book_list_falls_back_to_the_decision_book() (+20 more)

### Community 47 - "scripts/nfl_edge_gameline_rules.py"
Cohesion: 0.09
Nodes (47): Tee, ats(), bettable_ats(), bh(), board_at(), board_open(), bstat(), cell() (+39 more)

### Community 471 - "tests/test_model_game_savepoint.py"
Cohesion: 0.15
Nodes (4): _PoisonConn, _games(), test_a_best_price_timeout_is_the_logged_error_and_the_next_lookup_runs(), test_a_model_sql_error_does_not_poison_the_next_model()

### Community 48 - "tests/test_calibration_watch.py"
Cohesion: 0.05
Nodes (15): _Conn, _Res, TestDormantLiveModels, TestItNeverDecides, TestRosterChanges, TestTheRun, TestVerdictChanges, TestVolumeShifts (+7 more)

### Community 482 - "tests/test_promote_external.py"
Cohesion: 0.16
Nodes (5): _Conn, promote_external(), test_external_promotion_refuses_a_map_that_does_not_transfer(), test_external_promotion_writes_only_the_promoted_columns(), test_the_scorer_reads_the_external_map_like_any_promoted_one()

### Community 485 - "Weather look-ahead tests"
Cohesion: 0.13
Nodes (3): TestTheWeatherStepWalksTheWindow, _nhl_blended_features(), d()

### Community 488 - "Batter prop log lookback tests"
Cohesion: 0.15
Nodes (7): _Rec, _log_sql(), test_batter_log_scan_is_pinned_to_the_lookback_not_the_catalog(), test_no_lineup_does_not_scan_the_log(), test_starter_log_inside_the_batter_loader_uses_the_same_floor(), test_the_batter_loop_hands_one_cache_to_every_model(), test_training_from_the_tables_first_season_still_reads_the_prior_year()

### Community 49 - "Failure alerter fake-connection tests"
Cohesion: 0.05
Nodes (23): FakeConn, TestDeliveryAndNoise, TestHealthCheckOnlyIsNotADirtyPass, TestItCannotBreakTheWorker, TestSilentJobs, TestWhatCountsAsAFailure, _clean_runs(), _posts() (+15 more)

### Community 499 - "NFL opener daily card evaluation"
Cohesion: 0.09
Nodes (9): TestTheJoinKeyMatchesPicks, dump_board(), dump_eval_rows(), eval_row(), _picks_game_id(), _load_nfl_model(), load_prior_observations(), load_window_schedule() (+1 more)

### Community 5 - "Mobile app screens and theme"
Cohesion: 0.02
Nodes (248): Props, Nav, Props, Props, FilterChipProps, Props, Props, Props (+240 more)

### Community 501 - "Local research cache store"
Cohesion: 0.07
Nodes (34): TestLocalCacheGuards, activate(), available(), _manifest(), _path(), read_table(), status(), _write_manifest() (+26 more)

### Community 502 - "Price prefilter rollback tests"
Cohesion: 0.15
Nodes (9): _PoisonConn, _event_index(), _games(), _run(), test_a_failed_savepoint_rollback_falls_back_to_full_rollback(), test_both_prefilters_timing_out_still_reaches_the_pipeline_log(), test_lookahead_timeout_rolls_back_and_scoring_continues(), test_ncaaf_timeout_rolls_back_and_scoring_continues() (+1 more)

### Community 503 - "MLB in-play state alignment"
Cohesion: 0.24
Nodes (6): GameClock, _t(), test_before_first_pitch_and_after_last_play_are_not_priced(), test_between_pas_across_third_out_rolls_over_to_next_half(), test_mid_plate_appearance_is_that_pa_before_state(), test_plays_without_times_are_ignored()

### Community 51 - "NFL in-play gameday worker"
Cohesion: 0.05
Nodes (19): CreditBudgetExceeded, TeeRecorder, _Q, GamedayWorker, GameTracker, test_a_host_switch_is_alerted(), test_the_worker_self_checks_once_and_alerts_on_a_broken_feed(), test_a_one_sided_quote_is_skipped_rather_than_priced_on_raw_juice() (+11 more)

### Community 510 - "Scorer pricing and label helpers"
Cohesion: 0.06
Nodes (14): TestAmericanToImpliedProb, TestBuildInjuryFlag, TestBuildPickLabel, TestConfidenceTier, TestFeatureValue, american_to_implied_prob(), _build_injury_flag(), _build_pick_label() (+6 more)

### Community 511 - "Prop odds next-day lookahead"
Cohesion: 0.19
Nodes (3): TestTheOddsFetchReachesTomorrow, TestTheScorerReachesTomorrow, _events_src()

### Community 514 - "NFL live leader win model"
Cohesion: 0.17
Nodes (10): Artifact, Decision, am_to_dec(), artifact_from_dict(), band_for(), decide(), leader_expected_margin(), load_artifact() (+2 more)

### Community 515 - "Run ledger table tests"
Cohesion: 0.07
Nodes (4): _Shim, TestRunLedger, db(), mlb_wired()

### Community 516 - "NHL blocked shots settlement shim"
Cohesion: 0.27
Nodes (5): _Shim, TestSettlement, _bet(), _played(), _result()

### Community 517 - "Stale weekly sweep watch tests"
Cohesion: 0.15
Nodes (7): _Conn, test_a_fresh_sweep_and_savant_produce_no_finding(), test_a_missing_sweeps_table_is_reported_not_swallowed(), test_a_missing_webhook_is_not_ledgered_either(), test_a_stale_sweep_date_is_reported(), test_savant_with_only_one_player_type_is_stale_even_when_dated_today(), _stale_weeklies()

### Community 518 - "Weather forecast hour lookup"
Cohesion: 0.09
Nodes (11): _Resp, TestTheHourIsTheGamesOwn, TestTheRequestCoversTheTargetHour, _celsius_to_f(), _fetch_open_meteo(), _game_hour_utc(), _target_hour_utc(), _utc_offset_from_lon() (+3 more)

### Community 519 - "Mobile bankroll storage"
Cohesion: 0.23
Nodes (12): KeyValueStore, check(), eq(), fakeStore(), interleaving(), slowStore(), storage(), createBankrollStore() (+4 more)

### Community 52 - "tests/test_best_line_live.py"
Cohesion: 0.04
Nodes (42): _FakeConn, _best_live_price(), _live_book_quotes(), _live_quote_is_on_offer(), best_takeable_quote(), _ev(), _live_pick(), _open_cut() (+34 more)

### Community 520 - "Threshold review table creation tests"
Cohesion: 0.12
Nodes (4): _DdlConn, _DdlRes, test_a_failed_lock_down_does_not_lose_the_table(), test_ensure_schema_commits_the_tables_it_creates()

### Community 533 - "NFL wind card book filter tests"
Cohesion: 0.09
Nodes (8): TestTheCardFilters, TestTheListIsShared, test_a_label_that_disagrees_with_its_line_is_refused(), test_the_card_does_not_price_off_kalshi_until_it_is_graded(), _attach(), books(), card(), _quote()

### Community 534 - "Prop no-bet rows until tip tests"
Cohesion: 0.07
Nodes (9): _Board, _Clock, _PollConn, _fake_datetime_class(), _game(), _iso(), test_the_poller_keeps_prop_no_bet_rows_the_refresh_pass_still_clears(), test_the_poller_tells_the_scorer_to_leave_prop_rows_alone() (+1 more)

### Community 536 - "Closing line value backfill job"
Cohesion: 0.15
Nodes (5): _Conn, _stub_backfill(), test_hard_cap_stops_a_nonempty_queue(), test_loops_until_a_pass_fills_nothing(), test_the_runner_opens_get_connection_and_calls_backfill_clv()

### Community 539 - "NFL prop local odds cache tests"
Cohesion: 0.26
Nodes (5): TestLocalOddsCache, _odds_from_frame(), _p(), _odds_frame(), test_a_one_way_market_stays_one_way_through_the_cache()

### Community 54 - "tests/test_void_picks.py"
Cohesion: 0.05
Nodes (11): _FakeConn, TestAPostedSignalIsLocked, TestAPostedVoidAnnouncesAfterCommit, TestTheToolRefusesToMatchEverything, TestVoidingAPostedPickIsAnExplicitOptIn, TestWhatMayBeVoided, TestWhatTheVoidWrites, plan_voids() (+3 more)

### Community 544 - "NCAAF starter-out search dataset"
Cohesion: 0.10
Nodes (16): LabelSet, build_label_set(), _fetch_lines(), _fetch_raw(), opener_coverage(), _pick_provider(), provider_continuity(), main() (+8 more)

### Community 55 - "College football game-day feeds"
Cohesion: 0.04
Nodes (43): LiveOddsFeed, GameContext, TestFbsGate, now_iso(), _is_fbs(), school(), fetch_scoreboard_cfbd(), fetch_team_ids() (+35 more)

### Community 56 - "tests/test_daily_retry.py"
Cohesion: 0.06
Nodes (42): _Conn, _Cursor, _FrozenDatetime, DailyRun, Decision, _aborted(), _aborted_row(), _ok() (+34 more)

### Community 566 - "Odds feed probes and snapshot pulls"
Cohesion: 0.03
Nodes (44): Puller, configured(), guild_stats(), _key(), _ledger(), main(), match_event(), _save_ledger() (+36 more)

### Community 57 - "tests/test_live_book_move_guard.py"
Cohesion: 0.08
Nodes (34): BookMoveClock, _MlbConn, american_to_implied(), _at(), _delaware_ctx(), _dk(), _iso(), _mlb_odds() (+26 more)

### Community 570 - "NCAAF in-play underdog calibration"
Cohesion: 0.11
Nodes (6): TestTickLatency, label(), test_projecting_runs_after_the_decisions_are_published(), test_the_tick_passes_a_days_that_covers_the_whole_window(), test_the_tick_returns_free_outside_the_window(), test_the_twelve_distributional_models_score_off_the_ticks_own_fetch()

### Community 576 - "tests/test_weekly_catch_up.py"
Cohesion: 0.18
Nodes (3): _Conn, test_a_failing_savant_refresh_does_not_cost_the_calibration_its_catch_up(), test_ownership_is_checked_per_job()

### Community 582 - "Prop odds book update-time tests"
Cohesion: 0.26
Nodes (6): _Conn, _parse(), test_a_row_built_without_the_key_still_inserts_as_null(), test_no_clock_anywhere_is_none_not_our_fetch_time(), test_the_column_is_added_only_when_the_catalog_lacks_it(), test_the_markets_own_clock_is_stored_else_the_books()

### Community 583 - "NFL pick monitor"
Cohesion: 0.11
Nodes (11): TestClassify, TestImmutabilityContract, TestLatestPerPick, TestWindPublisherLock, classify(), _f(), latest_per_pick(), main() (+3 more)

### Community 59 - "NFL odds client and opener card"
Cohesion: 0.06
Nodes (26): OddsAPIClient, SnapshotResult, _key(), _ledger_bump(), _ledger_read(), ledger_status(), _ledger_write(), snapshot_to_frame() (+18 more)

### Community 590 - "NHL blocked shots prop card"
Cohesion: 0.19
Nodes (4): TestTheCard, pick_rows(), _scored(), execute()

### Community 592 - "NFL wind totals model and monitor"
Cohesion: 0.14
Nodes (12): Bet, american_to_decimal(), american_to_prob(), apply_slate_cap(), devig_two_way(), evaluate_board(), kelly_stake(), model_under_prob() (+4 more)

### Community 6 - "App data queries and pick details"
Cohesion: 0.02
Nodes (228): Props, FighterSide, Props, Props, LivePicksState, PlayerNextGame, Section, Args (+220 more)

### Community 601 - "Prop alternate lines fetch tests"
Cohesion: 0.14
Nodes (9): _Resp, test_a_422_retries_without_the_alternates_before_going_dk_only(), fake_get(), test_a_422_with_no_alternates_still_takes_the_dk_only_retry(), fake_get(), test_a_rejected_football_alternate_chunk_costs_only_itself(), fake_get(), test_football_live_slate_requests_alternates_and_a_backfill_does_not() (+1 more)

### Community 61 - "Mobile tracked bets and stakes"
Cohesion: 0.08
Nodes (43): Props, Props, StakeMode, StakeState, LiveTrackSnapshot, TrackedBetRow, trackedBetStatus, TrackedBetSummary (+35 more)

### Community 611 - "supabase/functions/revenuecat-webhook/index.ts"
Cohesion: 0.22
Nodes (3): RcEvent, admin, PRODUCT_TO_PLAN

### Community 613 - "supabase/functions/whop-webhook/index.ts"
Cohesion: 0.25
Nodes (4): WhopMembership, signatureValid(), timingSafeEqual(), admin

### Community 620 - "NCAAF in-play FBS context loading"
Cohesion: 0.16
Nodes (10): _Conn, _Result, _night_twin(), _pair_key(), _row(), test_a_twin_does_not_silently_take_the_row_without_lines(), test_an_unrelated_game_is_unaffected_by_a_collision(), test_context_carries_the_fbs_rule_for_both_teams() (+2 more)

### Community 626 - "NHL as-of feature leak tests"
Cohesion: 0.22
Nodes (4): TestOpeningNightIsEarlySeason, _blk_nhl_asof(), _t(), test_the_training_path_reads_nhl_odds_by_game_not_by_sport()

### Community 631 - "Mobile bankroll unit size hook"
Cohesion: 0.32
Nodes (7): BankrollSettings, useBankroll(), canStepUnitPct(), sanitizeUnitPct(), stepUnitPct(), store, BANKROLL_DEFAULTS

### Community 632 - "College football state feed tests"
Cohesion: 0.24
Nodes (6): _Ctx, _ev(), test_a_single_failed_summary_does_not_drop_the_other_games(), test_cfbd_mode_does_no_per_game_fetching(), test_espn_states_are_fetched_in_parallel_and_stay_aligned(), test_unknown_matchups_never_cost_a_fetch()

### Community 649 - "MLB totals public fade card"
Cohesion: 0.07
Nodes (21): _EmptyConn, load_latest_quotes(), edge_floor(), max_per_slate(), publish_enabled(), rank_kind(), ticket_threshold(), under_odds_band() (+13 more)

### Community 651 - "Model calibration sweep tests"
Cohesion: 0.05
Nodes (17): _ProbeConn, _rows(), test_a_prob_only_sweep_uses_only_the_probability_dimension(), test_column_migrations_run_every_pipeline_pass(), test_home_runs_are_no_longer_exempt_from_pausing(), test_plateau_is_computed_within_the_narrow_grid(), test_the_agent_changes_nothing_on_its_own(), test_the_agent_sweeps_every_registered_model_except_live_ones() (+9 more)

### Community 653 - "Model quality database end-to-end test"
Cohesion: 0.22
Nodes (3): _Shim, _insert_open_bet(), test_run_persists_all_unders_fade_slate_as_crit()

### Community 658 - "College football stored finals mirror"
Cohesion: 0.25
Nodes (4): _FakeCursor, mirror_stored_finals(), test_stored_finals_are_mirrored_without_a_cfbd_pull(), execute()

### Community 662 - "Signal publish-on-write tests"
Cohesion: 0.06
Nodes (18): _Conn, _body(), _row(), _surfaces(), _make(), test_a_broken_webhook_does_not_suppress_the_push(), test_a_failed_capture_still_delivers(), test_a_publish_failure_does_not_kill_the_tick() (+10 more)

### Community 668 - "NFL prop rule card"
Cohesion: 0.06
Nodes (23): TestKickoffGate, TestMarketGrading, _as_dt(), grade(), season_of(), summarise(), card(), _kalshi_ladders_or_empty() (+15 more)

### Community 67 - "tests/test_game_market_gate.py"
Cohesion: 0.06
Nodes (49): GateVerdict, MarketBookend, PublicSplits, apply_to_picks(), _as_float(), bookend_from_odds(), evaluate(), fair_prob() (+41 more)

### Community 671 - "NFL prop pull market list tests"
Cohesion: 0.22
Nodes (3): TestIngestEventsDoesNotShadowItsMarkets, test_live_prop_pull_asks_for_the_sharp_book(), fake_event_props()

### Community 674 - "NBA public splits quality backfill"
Cohesion: 0.18
Nodes (5): _CountingConn, backfill_quality(), test_an_existing_table_gets_the_quality_column(), test_the_backfill_adds_the_column_and_commits_once(), test_the_backfill_rolls_back_when_a_count_is_not_what_was_measured()

### Community 678 - "Prop box score grading tests"
Cohesion: 0.25
Nodes (4): GradeConn, test_a_non_timeout_prop_error_rolls_back_and_raises(), test_a_timed_out_prop_date_does_not_abort_the_next(), settle()

### Community 679 - "NBA prop player name resolver"
Cohesion: 0.23
Nodes (5): Roster, name_key(), test_a_books_initials_match_the_logs(), test_a_rookie_logged_under_an_espn_id_resolves_to_it(), test_the_resolver_uses_the_results_writers_normaliser()

### Community 68 - "NBA second-model prop study"
Cohesion: 0.06
Nodes (39): Shape, appearances(), box_tables(), build(), check_close_prior(), consensus_number(), empty_times(), fit_shape() (+31 more)

### Community 689 - "Settlement test database shim"
Cohesion: 0.22
Nodes (3): _SqliteShim, conn(), raw()

### Community 69 - "tests/test_pick_integrity.py"
Cohesion: 0.03
Nodes (56): _Conn, _Shim, test_retired_live_picks_still_settle_on_their_own_market(), test_settlement_grades_spreads_not_h2h(), test_it_settles_as_a_total(), _add_pick(), discord_sent(), _health() (+48 more)

### Community 696 - "NBA public splits late game archiving"
Cohesion: 0.12
Nodes (6): _NoDB, _Store, _scoreboard(), test_a_late_game_still_in_play_after_midnight_is_archived_at_the_next_pass(), test_a_stored_game_is_not_written_again_and_a_splitless_game_is_retried(), _wire_archive()

### Community 7 - "Database connection and feature reads"
Cohesion: 0.01
Nodes (216): DBConnection, TestComputeInjuryAdjustment, TestHasReturnee, TestHasStarterOut, TestMarketForOdds, TestPregameSnapshotGuard, connection_lost(), _is_write() (+208 more)

### Community 70 - "tests/test_record_one_pick_per_event.py"
Cohesion: 0.04
Nodes (48): _CaptureConn, _RecordingConn, duplicate_copy_exclusion_sql(), _code(), _copy_for_node(), _fn(), _node(), _read() (+40 more)

### Community 73 - "nfl/live_model/tests: test_props + props"
Cohesion: 0.08
Nodes (38): PropProjection, GameState, PlayerState, _accrued(), _count(), detect_inactive(), price_over(), project() (+30 more)

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
Nodes (38): Market, build_p1_frame(), build_team_frame(), day_interval(), _ew(), fit(), game_means(), _implied_vec() (+30 more)

### Community 8 - "App player stat log"
Cohesion: 0.04
Nodes (73): GameWindow, stepperRowLayout, StepperRowMeasure, WindowOption, statOf(), PositionVsOpponentPending(), asHitMode(), chipKey() (+65 more)

### Community 80 - "Global EV floor tests"
Cohesion: 0.06
Nodes (28): Gate, expected_value(), min_ev_for(), test_ncaaf_live_ev_floor_is_wired_from_config(), _built(), floor_030(), identity_maps(), open_pregame_cut() (+20 more)

### Community 83 - "tests/test_nhl_props.py"
Cohesion: 0.06
Nodes (17): _Shim, TestEveryLiveModelIsWiredEverywhere, TestInsertOnce, TestSettlement, TestTheDistribution, TestTheGoalieFrame, TestTonightsRowIsATrainingRow, publish() (+9 more)

### Community 84 - "Publish key identity and push alerts"
Cohesion: 0.03
Nodes (54): Ledger, _posted_sql(), test_a_real_pause_is_not_logged_as_stale(), execute(), test_empty_set_errors_when_a_stale_pause_flag_hides_bets(), execute(), _sql_key(), test_a_game_level_key_has_no_tail() (+46 more)

### Community 849 - "NFL wind forecast and lead"
Cohesion: 0.09
Nodes (21): OpenMeteoError, fetch_era5(), fetch_issued_forecasts(), fetch_live_forecast(), _frame(), _get(), _issued_columns(), _issued_from_supabase() (+13 more)

### Community 85 - "tests/test_recap_retries_a_skipped_day.py"
Cohesion: 0.06
Nodes (26): _LiteConn, World, step_settle(), _add_pick(), _grade(), _lite(), _schema(), test_a_day_with_nothing_counting_posts_nothing_and_logs_nothing() (+18 more)

### Community 851 - "NBA odds archive rerun safety"
Cohesion: 0.22
Nodes (5): _Conn, load(), stored_keys(), test_a_rerun_writes_nothing_already_stored(), test_stored_rows_are_read_by_game_id_not_by_scanning_for_the_source()

### Community 857 - "Picks email rendering"
Cohesion: 0.46
Nodes (6): Pick, _fmt_edge(), _fmt_odds(), main(), _pick_card(), render_email()

### Community 9 - "Probability calibration fitting tests"
Cohesion: 0.04
Nodes (27): _FakeConn, _SchemaRecordingConn, fit_model(), poisson_probability_metrics(), test_a_map_that_does_not_help_out_of_sample_is_not_applied(), test_a_map_that_helps_is_applied(), test_a_model_with_no_record_takes_the_pooled_correction(), test_a_model_with_too_few_graded_picks_gets_the_shrunk_offset_not_a_platt_map() (+19 more)

### Community 90 - "Mobile matchup stats verify scripts"
Cohesion: 0.04
Nodes (67): MatchupInfo, TonightMatchupRow, check(), fakeServer(), main(), read(), check(), grade() (+59 more)

### Community 91 - "NFL in-play remaining score distribution"
Cohesion: 0.10
Nodes (10): ScoreDistribution, _cluster_bootstrap(), evaluate(), main(), report(), mu_bucket(), _mu_centres(), _spearman_to_gaussian() (+2 more)

### Community 92 - "tests/test_ncaaf_prop_odds.py"
Cohesion: 0.05
Nodes (27): _Conn, _Resp, _market_chunks(), _football_map(), resolver(), scope(), test_a_book_we_did_not_ask_for_is_never_written(), test_a_day_with_no_college_games_spends_nothing() (+19 more)

### Community 94 - "NFL prop verdict tests"
Cohesion: 0.05
Nodes (25): TestSnapRows, TestVerdict, TestYesNoMarkets, _verdict(), test_a_half_line_market_priced_to_its_own_skew_is_not_flagged(), test_a_sharp_reference_is_never_a_book_we_bet(), test_a_targeted_backfill_never_substitutes_draftkings(), test_a_timing_run_can_be_labelled_so_it_cannot_displace_the_main_series() (+17 more)

### Community 95 - "tests/test_ncaaf_pbp_store.py"
Cohesion: 0.07
Nodes (20): _Conn, _extremes(), load_season_from_db(), observed_ranges(), _report_ranges(), store_season(), _plays(), test_a_rerun_updates_rather_than_duplicating() (+12 more)

### Community 96 - "tests/test_heartbeat_watchdog.py"
Cohesion: 0.07
Nodes (28): _FakeConn, _FakeCursor, _break_db(), sink(), test_a_failed_post_does_not_start_the_throttle(), test_a_healthy_start_never_announces_a_recovery(), test_a_returning_outage_alerts_again_immediately(), test_a_silent_failure_alerter_is_caught_by_the_watchdog() (+20 more)

### Community 97 - "Game injury veto gate and tests"
Cohesion: 0.05
Nodes (50): _InjConn, _InjConn, TestNormaliseName, norm_player_name(), apply_to_picks(), _goalie_names(), _pitcher_names(), player_matches_veto() (+42 more)

### Community 99 - "Record correction post tests"
Cohesion: 0.06
Nodes (26): Ledger, _Result, _pin(), _real_post(), _real_tweet(), x_posts(), _publish(), test_a_failed_discord_ledger_does_not_send_x() (+18 more)

### Community 16 - "Daily pipeline runner and push notifier"
Cohesion: 0.01
Nodes (104): _run_migrations(), setup_database(), ingest_ncaaf_results_for_date(), run_ncaaf_stats_ingestor(), run_bullpen_ingestor(), backfill_nba_stats(), run_nfl_results_ingestor(), ingest_nhl_scores_for_date() (+96 more)

### Community 102 - "scripts/nfl_edge_live_rush_pace.py"
Cohesion: 0.18
Nodes (26): _asof(), boot_p(), build_state(), first(), grade(), initial_last(), load_pbp(), main() (+18 more)

### Community 103 - "NBA prop projection tests"
Cohesion: 0.07
Nodes (26): _art(), _proj(), _q(), _run(), _settle(), test_a_book_hanging_two_lines_for_one_player_is_refused(), test_a_decision_with_no_bet_is_still_a_decision(), test_a_pick_row_names_its_side_book_and_market() (+18 more)

### Community 105 - "NBA game market feature study"
Cohesion: 0.06
Nodes (37): cache_for(), check_cells(), combine_times(), f2_cells(), f2_point(), f6a_placebo(), f6a_point(), f6a_strength() (+29 more)

### Community 107 - "tests/test_prop_calibrated_decision.py"
Cohesion: 0.07
Nodes (29): apply_prop_daily_cap(), _claimed_ev(), dedupe_player_props(), _downgrade(), _bet(), _identity_cal(), _prop(), test_a_genuinely_big_edge_still_fires_after_calibration() (+21 more)

### Community 108 - "NCAAF in-play quote serving"
Cohesion: 0.09
Nodes (17): correct_for_pregame(), _load_pregame_calibration(), pregame_dog_points(), test_a_big_dog_is_marked_down_hard(), test_a_corrupt_artifact_leaves_the_probability_alone(), test_a_favourite_is_marked_up(), test_a_missing_artifact_leaves_the_probability_alone(), test_a_pick_em_is_barely_touched() (+9 more)

### Community 109 - "NFL in-play backtest game states"
Cohesion: 0.11
Nodes (19): _settle(), _team_side(), build_states(), _pbp(), test_a_dome_suppresses_wind(), test_a_push_settles_to_nan_not_to_a_loss(), test_a_team_total_without_a_resolved_team_is_not_adjudicated(), test_a_wrong_date_component_is_repaired() (+11 more)

### Community 11 - "NFL prop information and stacking studies"
Cohesion: 0.07
Nodes (30): closing_prices(), devig(), ecdf_p_over(), main(), bets(), design(), main(), analyse() (+22 more)

### Community 110 - "tests/test_mobile_line_movement.py"
Cohesion: 0.08
Nodes (27): _fn(), _read(), _run(), test_a_cut_table_keeps_the_pick_and_says_what_it_covers(), test_a_cut_window_keeps_the_pick_row_on_the_8_row_table(), test_a_pick_made_after_the_cards_start_never_reads_since_your_pick(), test_after_the_start_the_verdict_is_not_graded(), test_an_old_snapshot_is_not_the_price_at_the_pick() (+19 more)

### Community 111 - "tests/test_live_calibration.py"
Cohesion: 0.07
Nodes (35): _live_calibration(), pick(), test_a_peak_with_no_plateau_anywhere_is_labelled_as_one(), test_a_prob_cut_and_an_ev_cut_select_different_picks(), test_calibration_also_scores_ev_against_realised_roi(), test_calibration_is_empty_rather_than_wrong_with_nothing_settled(), test_calibration_reports_the_gap_between_claim_and_reality(), test_expected_value_matches_the_hand_calculation() (+27 more)

### Community 112 - "Mobile live board segment tests"
Cohesion: 0.06
Nodes (28): _read(), test_a_sport_switch_cannot_report_a_game_finishing(), test_all_three_segments_are_unconditional(), test_live_is_not_a_bottom_tab(), test_live_is_not_in_the_tab_param_list(), test_no_app_root_component_reaches_a_focus_aware_hook(), imports_of(), strip_comments() (+20 more)

### Community 117 - "NBA lineup stint derivation tests"
Cohesion: 0.08
Nodes (46): order_plays(), possession_ends(), _blowout_q4(), derive(), dreb(), _dup_game(), end_period(), five_game() (+38 more)

### Community 119 - "tests/test_ncaaf_live_notify.py"
Cohesion: 0.05
Nodes (18): _load_write_picks(), _restore_stubbed_modules(), test_a_caller_supplied_connection_is_not_closed_by_the_write(), test_a_failing_notifier_never_breaks_pricing(), test_a_full_slate_announces_once(), test_a_live_bet_notifies_push_and_discord(), test_a_locked_lane_is_not_rewritten(), test_a_locked_lane_keeps_notifying_after_the_engine_stops_betting() (+10 more)

### Community 126 - "monitoring/store.py"
Cohesion: 0.07
Nodes (29): meta(), ops(), snapshot(), api_rollup(), call_timeline(), calls_since(), community(), scalar() (+21 more)

### Community 128 - "tests/test_settled_record_is_immutable.py"
Cohesion: 0.05
Nodes (23): _code(), test_a_dedicated_live_lane_still_counts_and_a_pre_game_in_play_pick_does_not(), test_a_paused_model_is_not_an_excluded_model(), test_a_voided_pick_is_still_out_of_the_record(), test_both_published_views_keep_the_live_date_gate(), test_both_rules_name_the_two_exits_and_not_the_paused_flag(), test_both_views_are_redefined_by_name(), test_every_explicit_exclusion_names_who_asked_for_it() (+15 more)

### Community 130 - "features/golf_feature_engine.py"
Cohesion: 0.07
Nodes (30): assemble_player_features(), _avg_finish(), build_bulk_golf_lookups(), build_golf_scoring_features(), build_golf_training_dataset(), compute_golf_target(), compute_matchup_target(), _event_finishes() (+22 more)

### Community 132 - "ncaaf_live/tests/test_states.py"
Cohesion: 0.13
Nodes (23): build_states(), _detect_score_convention(), _platform(), _plays(), _post_convention_game(), _pre_convention_game(), test_a_scoring_plays_state_does_not_contain_its_own_points(), test_ambiguous_convention_refuses_to_build() (+15 more)

### Community 133 - "tests/test_bovada_feed.py"
Cohesion: 0.11
Nodes (29): _american(), _complete(), _num(), parse_coupon(), _row_for(), _seen_key(), _stamp(), _coupon() (+21 more)

### Community 134 - "tests/test_market_movement.py"
Cohesion: 0.09
Nodes (23): american_to_prob(), build_market_features(), _is_full_game_snap(), _latest_two_sided(), _s(), test_a_game_with_no_decision_book_still_gets_features(), test_a_line_that_genuinely_did_not_move_is_zero_not_none(), test_a_one_way_sharp_quote_yields_nothing() (+15 more)

### Community 136 - "NCAAF cross-book opener rule tests"
Cohesion: 0.07
Nodes (25): _minutes_apart(), build_artifact(), build_band_artifact(), _branch(), test_absent_ceiling_means_unbounded(), test_artifact_shape(), test_band_ceiling_is_enforced_in_the_scorer(), test_band_volumes_sum_to_the_single_gate_backtest() (+17 more)

### Community 139 - "NFL in-play edge seasonal backtest"
Cohesion: 0.08
Nodes (47): books_per_snapshot(), cell(), families(), finalize_states(), fit_models(), fmt(), h1(), h1_calibration() (+39 more)

### Community 142 - "tests/test_health_pregame_prices_current.py"
Cohesion: 0.10
Nodes (30): _at(), _game(), _row(), _run(), test_a_broken_feed_read_is_an_error_and_rolls_back(), test_a_broken_query_is_an_error_and_rolls_back(), test_a_cancelled_fight_and_a_pulled_game_do_not_raise_the_alarm(), test_a_dead_feed_with_no_priced_game_is_a_crit() (+22 more)

### Community 147 - "scripts/nfl_edge_extreme_props.py"
Cohesion: 0.12
Nodes (29): actuals(), add_modes(), bar(), candidates(), cell(), decision_boards(), devig(), fit_holdout() (+21 more)

### Community 148 - "scripts/nfl_edge_settlement.py"
Cohesion: 0.14
Nodes (30): add_test(), attach(), banner(), bh(), board(), boot_draws(), cell(), choose() (+22 more)

### Community 149 - "NBA totals overs rule tests"
Cohesion: 0.07
Nodes (27): quote_frame(), _decide(), _et(), _fires(), _refresh_jobs(), _rows(), _season(), _target() (+19 more)

### Community 15 - "X publisher"
Cohesion: 0.02
Nodes (77): discover(), fetch_all(), _get_image(), main(), _original_size(), _x_api_profile(), test_the_record_restatement_and_the_slate_restatement_are_separate(), test_the_tweet_header_says_restated() (+69 more)

### Community 153 - "tests/test_agents_contract.py"
Cohesion: 0.05
Nodes (20): _labelled_retired(), test_blocked_items_are_marked_so_the_agent_skips_them(), test_every_backlog_item_is_a_checkbox(), test_neither_agent_may_change_a_model_threshold(), test_the_agents_are_findable_from_the_file_every_session_reads(), test_the_backlog_does_not_promise_an_agent_that_no_longer_runs(), test_the_backlog_exists_and_has_items(), test_the_contract_documents_every_agent_by_name() (+12 more)

### Community 159 - "WNBA results and stats ingestors"
Cohesion: 0.05
Nodes (46): box_team_totals(), _no_minutes(), parse_nba_box(), parse_nba_dnp(), parse_nba_scoreboard(), _played(), _team_blocks(), board() (+38 more)

### Community 161 - "NBA box score enrichment tests"
Cohesion: 0.16
Nodes (18): box_rows(), dnp_kind(), minutes_to_float(), minutes_to_seconds(), starter_update_batches(), _box(), test_a_blank_minutes_string_is_null_not_zero(), test_a_dnp_row_has_null_minutes_and_its_reason_and_is_not_a_starter() (+10 more)

### Community 166 - "Prop box score backfill"
Cohesion: 0.11
Nodes (25): fill_missing(), _call_fill(), _cooled(), _day(), _default_mlb(), _default_nba(), _default_nfl(), _default_nhl() (+17 more)

### Community 168 - "Push delivery ticket tests"
Cohesion: 0.16
Nodes (14): _msgs(), test_a_credentials_failure_disables_nobody(), test_a_request_level_rejection_accepts_nothing(), test_a_retired_device_is_named_for_disabling(), test_a_single_message_reply_may_be_a_bare_object(), test_a_ticket_that_is_not_an_object_is_not_a_delivery(), test_an_error_ticket_is_not_counted_as_sent(), test_an_unpairable_reply_counts_nothing_and_disables_nothing() (+6 more)

### Community 169 - "NFL expected value stake engine"
Cohesion: 0.09
Nodes (23): american_to_decimal(), cover_probs(), ev_per_unit(), fit_margin_pmf(), kelly_fraction(), margin_pmf_for(), add_model_mu(), load() (+15 more)

### Community 17 - "NFL quarterback wind edge study"
Cohesion: 0.10
Nodes (42): band_table(), bh(), build_priced(), decisions_2026(), decisions_hist(), era5_hourly(), fc_at_decision(), fetch_2026() (+34 more)

### Community 172 - "Probability calibration jobs"
Cohesion: 0.07
Nodes (24): demote(), ensure_schema(), _era_start(), fit_offset(), fit_platt(), fit_pool(), _gap_pp(), invert_calibration() (+16 more)

### Community 173 - "tests/test_decide_on_calibrated.py"
Cohesion: 0.06
Nodes (19): _pick(), _pick_at(), test_a_calibrated_cut_is_paired_with_a_calibrated_decision(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(), test_a_genuinely_big_edge_still_fires_after_calibration(), test_a_hot_model_no_longer_fires_the_marginal_bet(), test_a_model_on_a_calibrated_cut_is_not_paused(), test_a_paused_model_never_fires_regardless() (+11 more)

### Community 176 - "NBA prop projection lab"
Cohesion: 0.10
Nodes (46): implied(), bars(), bh_read(), blind(), boot(), by(), cal_ab(), candidates() (+38 more)

### Community 178 - "NFL edge versus luck gap study"
Cohesion: 0.10
Nodes (30): add_windows(), add_windows_fast(), bh(), binom_p(), board(), boot(), cell(), fit_points() (+22 more)

### Community 180 - "NBA totals overs shooting luck model"
Cohesion: 0.09
Nodes (20): as_of_ratings(), decide(), f4_projections(), f4_signal(), is_last_look(), lead_minutes(), missing_boxes(), newest_season() (+12 more)

### Community 182 - "tests/test_model_artifacts_load.py"
Cohesion: 0.09
Nodes (17): _git(), _gitignore_keep_pkls(), _ignored(), _manifest_keep_pkls(), _newest_per_model(), test_a_path_that_is_not_ignored_is_not_reported(), test_a_superseded_timestamped_pkl_is_ignored(), test_an_ignored_path_comes_back_byte_identical() (+9 more)

### Community 185 - "scripts/game_line_market_sweep.py"
Cohesion: 0.08
Nodes (22): _by_month(), collect_picks(), devig(), _gap_seconds(), grade(), implied(), iter_months(), load() (+14 more)

### Community 187 - "Push notification deep link tests"
Cohesion: 0.08
Nodes (23): _code(), _py_version(), _read(), test_a_single_pick_deep_links_and_a_batch_does_not(), test_an_unreadable_payload_routes_nowhere_rather_than_guessing(), test_both_halves_pin_the_same_payload_version(), test_every_expo_message_carries_a_data_payload(), test_every_summary_producer_can_deep_link_a_single_pick() (+15 more)

### Community 188 - "tests/test_pass_instrumentation.py"
Cohesion: 0.06
Nodes (11): test_a_dead_database_does_not_fail_the_step(), test_a_raised_failure_still_records_the_exception(), test_a_step_that_raises_is_still_TIMED(), test_a_step_that_raises_still_raises(), boom(), test_a_step_that_returns_false_records_a_REASON(), test_a_successful_step_records_a_duration(), test_every_step_name_in_the_dispatch_table_is_reachable() (+3 more)

### Community 189 - "Settlement self-healing tests"
Cohesion: 0.15
Nodes (21): _game(), _pick(), test_a_doubleheader_row_with_a_final_keeps_its_picks_grading(), test_a_final_game_is_never_voided(), test_a_game_with_any_box_score_row_is_not_refetched(), test_a_postponed_game_voids_its_pending_bets(), test_a_recent_postponement_waits_for_a_same_day_resumption(), test_a_scored_game_whose_props_have_no_box_score_is_found() (+13 more)

### Community 190 - "tests/test_db_adapt_sql.py"
Cohesion: 0.09
Nodes (23): _adapt_sql(), _convert_params(), _convert_params_outside_literals(), _named(), test_a_block_comment_is_skipped_too(), test_a_colon_word_inside_a_comment_is_not_a_placeholder(), test_a_dash_dash_inside_a_literal_is_data_not_a_comment(), test_a_line_comment_ends_at_the_newline() (+15 more)

### Community 194 - "NFL in-play 2025 edge report"
Cohesion: 0.08
Nodes (44): h2(), h5(), tot_offers(), async_check(), attach_games(), attach_state(), best_by(), boot() (+36 more)

### Community 195 - "tests/test_mobile_contrast_tokens.py"
Cohesion: 0.13
Nodes (29): _code_lines(), _ionicon_colors(), _lum(), _over(), _ratio(), _read(), _rgb(), test_badge_glyph_tracks_dynamic_type() (+21 more)

### Community 197 - "NBA box score stats ingestor"
Cohesion: 0.10
Nodes (20): _build_game_id(), _build_game_rows(), _build_player_log_rows(), _build_team_stat_rows(), _fetch_league_game_log(), ingest_nba_game_log_for_date(), _ingest_season(), _log_pipeline() (+12 more)

### Community 20 - "Threshold and EV floor sweeps"
Cohesion: 0.12
Nodes (19): _in_graded_matview(), _is_live_lane(), _era(), _guard_mlb(), _cell(), _decimal(), fetch_rows(), grade() (+11 more)

### Community 200 - "Live monitor cache"
Cohesion: 0.13
Nodes (10): age(), cached(), clear(), test_cache_raises_when_it_has_nothing_to_fall_back_on(), test_cache_reports_age(), test_cache_serves_stale_rather_than_failing(), boom(), test_cache_serves_within_ttl_and_recomputes_after() (+2 more)

### Community 201 - "NBA second game line move tests"
Cohesion: 0.06
Nodes (39): _priced_season(), _q(), _sched(), _season_games(), _signal(), _split(), _stub_main(), test_a_fetch_after_T_never_reaches_the_move() (+31 more)

### Community 206 - "NBA shooting luck and motivation lab"
Cohesion: 0.10
Nodes (17): _before(), f6c_offers(), f6c_signal(), game_situations(), _load_box(), main(), market_offers(), placebo_frames() (+9 more)

### Community 207 - "DraftKings direct feed freshness probes"
Cohesion: 0.05
Nodes (32): _connect(), _open(), release_read(), _session_options(), use_poller_session(), resolve_game_id(), split_matchup(), main() (+24 more)

### Community 208 - "NBA play-by-play game matching tests"
Cohesion: 0.06
Nodes (29): _last(), match_games(), match_names(), _g(), _game_recs(), _rec(), _summary(), test_a_gap_game_found_a_day_off_is_dated_by_our_games_row() (+21 more)

### Community 210 - "WNBA stats and results ingestion"
Cohesion: 0.06
Nodes (33): _go(), _upsert_nhl_games(), _upsert_public_betting(), _deref(), _fetch_core_games(), _fetch_scoreboard(), _fetch_summary(), ingest_wnba_results() (+25 more)

### Community 216 - "NBA public betting splits ingestor"
Cohesion: 0.11
Nodes (16): active_queries(), archive_ready(), ensure_table(), fetch_scoreboard(), keep_for_poll(), _known_abbrs(), load_games_index(), not_started() (+8 more)

### Community 218 - "Database row and SQL safety tests"
Cohesion: 0.04
Nodes (24): _identity_maps(), _platform_gates_off(), test_breakeven_is_the_real_vig_hurdle(), _statements(), test_columns_and_values_line_up(), test_the_scorer_pick_insert_is_actually_covered(), conn(), _prop() (+16 more)

### Community 219 - "tests/test_nfl_live_leader_state.py"
Cohesion: 0.12
Nodes (20): abbrev(), situation(), status(), test_a_conversion_try_is_skipped(), test_a_previous_quarters_play_is_not_the_state(), test_a_timeout_is_skipped_for_the_play_before_it(), test_after_a_scoring_play_nothing_is_evaluated(), test_after_the_kickoff_lands_the_receiver_has_the_ball() (+12 more)

### Community 221 - "tests/test_ncaaf_qb_ingestor.py"
Cohesion: 0.12
Nodes (22): _athlete_stats(), _comp_att(), parse_qb_game_stats(), _parse(), _payload(), _team(), test_athlete_stats_helper_is_category_scoped(), test_athlete_without_an_id_is_ignored() (+14 more)

### Community 224 - "NBA derivative market lab"
Cohesion: 0.09
Nodes (35): add_team(), am_to_dec(), bars_for(), bet_list(), blind(), boot_ci(), build_line_rows(), build_outcomes() (+27 more)

### Community 229 - "NBA public betting splits ingestor tests"
Cohesion: 0.14
Nodes (20): build_rows(), _entry(), test_a_late_tip_matches_its_et_dated_game_id(), test_a_swapped_listing_flips_team_sides_into_our_orientation(), test_a_v1_listing_rewritten_more_than_400_minutes_after_tip_is_late(), test_an_unknown_team_is_reported_not_invented(), test_archive_rows_carry_no_observation_time(), test_every_inserted_column_exists_in_the_table() (+12 more)

### Community 232 - "Mobile pick category tests"
Cohesion: 0.13
Nodes (12): _block(), _config_scorable_ids(), _meta_ids(), _meta_types(), _read(), test_every_model_id_derives_its_own_declared_category(), test_every_scorable_model_has_a_label_in_the_app(), test_picks_idle_chrome_is_search_and_filters_only() (+4 more)

### Community 235 - "NCAAF feature engine tests"
Cohesion: 0.11
Nodes (19): _assemble(), _stats(), test_a_push_yields_no_target(), test_assembly_diffs_and_context(), test_backtester_and_scorer_dispatch_ncaaf_explicitly(), test_backtester_feature_vector_exempts_sparse_columns(), test_bulk_loads_both_markets_of_the_historical_line(), test_dropna_keeps_null_geography_but_drops_null_core() (+11 more)

### Community 236 - "First pitch bound tests"
Cohesion: 0.06
Nodes (17): test_a_late_start_is_believed_because_it_is_real(), test_a_missing_actual_start_falls_back_to_the_schedule(), test_both_missing_still_fails_open(), test_every_is_pregame_snapshot_caller_passes_first_pitch(), test_it_never_overwrites_commence_time(), test_the_actual_start_wins_over_the_schedule(), test_the_backfills_in_play_marker_prefers_the_actual_start(), test_the_boundary_itself_is_pregame() (+9 more)

### Community 237 - "House juice price floor tests"
Cohesion: 0.10
Nodes (13): min_odds_for(), _blocked_by_min_odds(), test_a_pick_with_no_price_is_never_blocked_by_the_floor(), test_an_explicit_floor_wins_in_BOTH_directions(), test_every_registered_model_has_an_effective_floor(), test_ordinary_prices_still_fire(), test_the_default_is_overridable_without_a_code_change(), test_the_measured_blast_radius_is_recorded() (+5 more)

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
Cohesion: 0.07
Nodes (25): backfill_bullpen_stats(), backfill_mlb_stats(), backfill_pitcher_stats(), backfill_player_game_log(), backfill_player_handedness(), _build_pitcher_rows(), _build_team_stats_rows(), _fetch_mlb_api_batting() (+17 more)

### Community 25 - "NBA game search grading harness"
Cohesion: 0.04
Nodes (51): attach_fetch(), blind_by_real_side(), blind_pool(), blind_side(), boot(), cell_report(), cents(), check() (+43 more)

### Community 250 - "College football in-play history pull"
Cohesion: 0.14
Nodes (19): _blank_row(), budget_for(), calls_in(), _floor5(), _get(), _iso(), main(), parse_shard() (+11 more)

### Community 252 - "NBA totals overs card"
Cohesion: 0.11
Nodes (15): step_mlb_total_public_fade(), step_nba_total_luck(), artifact(), decided_games(), ensure_decisions_table(), ledger_exists(), load_quote_rows(), load_season() (+7 more)

### Community 256 - "tests/test_ncaaf_search_features.py"
Cohesion: 0.11
Nodes (15): build_adjusted_ratings(), build_prior_season_ratings(), load_fbs_membership(), load_team_games(), pool_fcs_opponents(), rolling_variants(), _asof_merge(), build_matrix() (+7 more)

### Community 257 - "College football model search runner"
Cohesion: 0.12
Nodes (17): features_for(), _apply_calibration(), exponential_recency_weights(), _logit(), make_ensemble(), fit_predict(), make_lgbm(), fit_predict() (+9 more)

### Community 259 - "NFL wind card and opener sweep"
Cohesion: 0.09
Nodes (18): bettable_books(), coverage_check(), expected_true_wind(), open_air_mask(), load_nfl_model(), boot_ci(), candidate_rows(), _load_backtest() (+10 more)

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
Nodes (63): node_strips_types(), tsx_cmd(), _node_strips_types(), test_a_published_void_keeps_track_and_betslip(), test_a_tracked_void_reads_not_graded_and_detail_closes_when_over(), test_the_app_predicate_matches(), test_today_et_ignores_the_container_timezone(), _read() (+55 more)

### Community 267 - "tests/test_ncaaf_qb_features.py"
Cohesion: 0.14
Nodes (22): build_qb_team_features(), _feat(), _frame(), _games(), _qb_rows(), _qb_team(), test_a_games_features_never_use_that_game(), test_current_qb_is_the_previous_games_primary() (+14 more)

### Community 268 - "Discord price bound tests"
Cohesion: 0.10
Nodes (16): _dec(), test_a_field_without_a_bound_renders_without_the_clause(), test_a_model_with_no_own_ev_floor_is_bound_by_the_global_one(), test_a_price_floor_can_be_the_binding_gate(), test_a_rounded_bound_still_clears_the_bound_it_came_from(), test_even_money_is_plus_one_hundred(), test_no_bound_from_junk_rather_than_a_guess(), test_no_bound_when_the_edge_floor_is_unreachable() (+8 more)

### Community 271 - "Line CLV sign and orientation tests"
Cohesion: 0.07
Nodes (7): _load(), test_a_line_that_held_is_exactly_zero_not_none(), test_a_missing_close_is_not_a_zero(), test_a_side_that_cannot_be_oriented_returns_none_rather_than_guessing(), test_the_home_and_away_sides_are_exact_mirrors(), test_the_prop_market_flag_wins_over_the_market_string(), test_the_signs_are_the_negation_of_the_apps_entry_frame()

### Community 272 - "Mobile screen source wiring tests"
Cohesion: 0.03
Nodes (57): test_every_revoke_names_the_roles_rather_than_public(), test_odds_keeps_select_for_the_app(), test_the_two_rls_off_tables_lose_everything(), test_it_is_dry_run_by_default(), test_best_odds_never_reaches_the_qualifying_gate(), _read(), test_every_player_page_read_names_its_relation_literally(), test_next_game_is_earliest_in_the_window_not_tonights_date() (+49 more)

### Community 275 - "NBA game harness tests"
Cohesion: 0.08
Nodes (27): _cov_data(), _fetches(), _games(), _offers(), _q(), _stale_cache(), test_a_cell_reports_its_pooled_walk_forward_and_writes_its_bets(), test_a_graded_load_refuses_a_season_the_cache_does_not_price() (+19 more)

### Community 276 - "NBA results ingest"
Cohesion: 0.13
Nodes (13): call_in_savepoint(), rollback_savepoint(), statement_timeout(), box_is_complete(), ingest_nba_results(), main(), match_game(), needs_work() (+5 more)

### Community 280 - "MLB live game state trigger tests"
Cohesion: 0.17
Nodes (16): _detect_triggers(), _is_active_or_starting_soon(), test_active_in_progress_game_is_active(), test_combined_changes_fire_all_relevant_triggers(), test_due_up_change_fires_due_up_change(), test_final_game_is_not_active(), test_identical_state_fires_no_triggers(), test_inning_half_change_fires_inning_change() (+8 more)

### Community 283 - "College football in-play game states"
Cohesion: 0.13
Nodes (12): main(), out_path(), _classify(), classify_report(), load_pbp(), load_platform_games(), pace_report(), _repair_day_offsets() (+4 more)

### Community 286 - "Kalshi prop ingest"
Cohesion: 0.05
Nodes (16): _event_date(), _player(), record_ladders(), test_a_kalshi_outage_cannot_break_the_pass(), test_a_run_is_idempotent_within_its_snapshot(), test_one_snapshot_timestamp_for_the_whole_run(), test_the_recorder_is_scheduled_on_the_pipeline_role(), test_the_recorder_keeps_raw_prices_not_a_filtered_ladder() (+8 more)

### Community 287 - "Model calibration check tests"
Cohesion: 0.11
Nodes (11): _calibration_sql(), test_a_flagged_model_is_named_eligible_or_not(), test_a_thin_model_is_still_excluded_rather_than_accused(), test_eligibility_notes_must_not_sink_the_gap_check(), test_it_grades_the_calibrated_probability_not_the_raw_one(), test_it_joins_picks_to_reach_the_calibrated_column(), test_the_check_has_a_skip_budget_that_survives_a_regime_change(), test_the_probability_floor_applies_to_the_decision_number_too() (+3 more)

### Community 289 - "NBA prop market bet finder"
Cohesion: 0.10
Nodes (20): coherent(), fair_under(), fetch_times(), find_bets(), in_window(), load_quotes(), minutes_to_tip(), parse_ts() (+12 more)

### Community 29 - "NCAAF college data ingestor"
Cohesion: 0.06
Nodes (27): backfill_ncaaf(), backfill_ncaaf_lines(), backfill_ncaaf_players(), backfill_ncaaf_qb(), _existing_ncaaf_ids(), _get(), ingest_ncaaf_game_log(), ingest_ncaaf_games() (+19 more)

### Community 290 - "NBA second game model verdict"
Cohesion: 0.13
Nodes (14): cell_rows(), main(), _plain(), axes_of(), bar9(), cell_key(), _floats(), house_bar4() (+6 more)

### Community 293 - "Source inspection guard tests"
Cohesion: 0.02
Nodes (60): relabel_in_play(), test_the_artifact_table_revokes_at_its_own_creation(), test_a_run_that_writes_nothing_is_not_reported_as_success(), test_the_insert_rolls_back_per_row(), test_the_in_play_relabel_uses_the_better_bound(), test_sport_and_market_are_bounded(), test_the_declared_key_is_present_and_valid(), test_the_runner_imports_the_script_main_not_a_shell() (+52 more)

### Community 294 - "NCAAF player stats parser tests"
Cohesion: 0.18
Nodes (17): parse_player_game_stats(), _cat(), _parse(), _payload(), _team(), test_a_game_missing_from_the_id_map_is_skipped_not_guessed(), test_a_player_gets_one_row_across_every_category(), test_a_player_with_nothing_we_track_is_skipped() (+9 more)

### Community 296 - "NHL namesake player tests"
Cohesion: 0.38
Nodes (6): namesakes(), _frame(), test_a_namesake_who_played_for_the_team_last_season_still_counts(), test_a_unique_name_is_kept(), test_namesakes_on_two_teams_collide_only_when_those_teams_meet(), test_two_teammates_with_one_name_are_both_refused()

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

### Community 309 - "Free pick post rendering"
Cohesion: 0.11
Nodes (15): _pick(), test_a_pick_with_no_alternative_falls_back_to_draftkings(), test_every_offerable_book_has_a_human_name_on_both_surfaces(), test_the_free_card_names_the_cheaper_book(), test_the_free_card_query_reads_the_columns_it_renders(), test_the_good_to_clause_is_dropped_not_truncated_when_it_will_not_fit(), test_the_tweet_names_the_cheaper_book(), test_the_tweet_never_publishes_a_worse_price_than_draftkings() (+7 more)

### Community 31 - "NBA prop model lab and verification"
Cohesion: 0.04
Nodes (81): p_over_calibrated(), books(), decimal(), expected_value(), fit_alpha(), nb_logpmf(), p_over(), settle_value() (+73 more)

### Community 315 - "MLB totals public fade pre-start split"
Cohesion: 0.10
Nodes (18): diff(), pitcher_diff(), diff(), pitcher_diff(), numeric_feature_value(), _pct_pair(), _better_under(), is_pre_commence() (+10 more)

### Community 317 - "Real database trigger tests"
Cohesion: 0.06
Nodes (35): main(), can_scratch(), env_dsn(), _free_port(), pg_bin(), scratch_cluster(), as_app(), db() (+27 more)

### Community 318 - "tests/test_live_record_start_views.py"
Cohesion: 0.09
Nodes (12): _body(), _code(), test_both_published_views_carry_the_live_date_gate(), test_it_runs_after_the_migration_that_used_to_own_the_daily_view(), test_migration_is_one_statement(), test_migration_is_registered_with_the_worker_runner(), test_neither_view_reads_the_sweep_universe(), test_no_ddl_outside_the_guarded_branches() (+4 more)

### Community 319 - "Model quality volume spike checks"
Cohesion: 0.13
Nodes (15): record_exclusion_sql(), test_volume_spike_vs_median(), test_volume_without_history_is_skipped_not_flagged(), test_the_exclusion_sql_is_a_conjunction_of_negations(), _job_model_quality(), detect_volume_spike(), ensure_schema(), _group() (+7 more)

### Community 326 - "NBA rest and schedule features"
Cohesion: 0.12
Nodes (10): _counted_schedule(), from_cache(), game_schedule_features(), haversine_miles(), home_bases(), _offsets(), previous_game_load(), team_schedule_features() (+2 more)

### Community 328 - "NFL Kalshi edge search"
Cohesion: 0.17
Nodes (20): align_check(), bh(), bins(), boot(), cell(), coverage(), cp_roi(), fee() (+12 more)

### Community 329 - "nfl/models/opener_spread.py"
Cohesion: 0.14
Nodes (11): age_tag(), american_to_prob(), _bettable_books(), clean_board(), edge_tier(), evaluate_board(), held_minutes(), model_prob_for_dev() (+3 more)

### Community 331 - "NHL prop backtest and EV lab"
Cohesion: 0.11
Nodes (22): books(), card(), claimed_vs_realised(), day_interval(), line(), load(), main(), predictions() (+14 more)

### Community 332 - "Live slate midnight date tests"
Cohesion: 0.12
Nodes (5): test_both_live_loops_share_one_definition_of_the_slate(), test_the_apps_live_hook_resolves_the_window_per_fetch(), test_the_apps_live_reads_take_a_LIST_of_dates(), test_the_ncaaf_live_loop_got_the_same_fix(), test_the_scorer_announces_every_date_it_scored()

### Community 333 - "tests/test_nfl_wind_fire_window.py"
Cohesion: 0.07
Nodes (18): _retractable_slate(), _slate(), test_a_blank_roof_at_a_NON_retractable_venue_is_unaffected(), test_a_closed_roof_is_still_indoor(), test_a_retractable_venue_with_an_unknown_roof_does_not_fire(), test_a_waiting_game_is_not_reported_as_a_collapsed_premise(), test_a_waiting_row_keeps_its_line_price_and_edge(), test_every_blank_roof_row_is_a_retractable_venue() (+10 more)

### Community 335 - "tests/test_public_betting_ingestor.py"
Cohesion: 0.17
Nodes (17): parse_public_betting(), _pct(), _select_book(), _make_game(), test_parse_emits_six_rows(), test_parse_game_id_and_sides(), test_parse_marks_source_and_snapshot(), test_parse_missing_teams_returns_empty() (+9 more)

### Community 339 - "tests/test_service_role_split.py"
Cohesion: 0.15
Nodes (11): _all_job_ids(), _sched(), test_an_unknown_role_runs_everything(), test_every_add_job_call_passes_an_id(), test_every_job_is_owned_by_exactly_one_role(), test_the_always_on_jobs_run_on_every_role(), test_the_default_preserves_the_single_container(), test_the_nfl_worker_stays_with_the_volume() (+3 more)

### Community 343 - "tests/test_http_timeout_floor.py"
Cohesion: 0.11
Nodes (11): install_timeout_floor(), _call(), clean_requests(), test_a_call_with_no_timeout_gets_one(), test_an_explicit_timeout_is_never_overridden(), test_installing_twice_is_a_no_op(), test_the_deadline_is_env_overridable(), test_the_deadline_survives_telemetry_being_turned_off() (+3 more)

### Community 345 - "Model quality public fade tests"
Cohesion: 0.10
Nodes (9): _bet(), test_high_public_pct_on_a_fade_publisher_counts_as_a_fade(), test_low_public_pct_on_the_pick_side_counts_as_a_fade(), test_majority_share_warns_when_not_unanimous(), test_meta_steps_exclude_model_quality(), test_pipeline_step_never_fails_on_crit(), test_pipeline_step_never_fails_on_exception(), test_side_aliases_collapse_to_the_same_direction() (+1 more)

### Community 346 - "NFL edge research data cache"
Cohesion: 0.22
Nodes (14): _conn(), copy_main_local(), _df(), _games_2026(), log(), main(), nflverse_misc(), nflverse_pbp() (+6 more)

### Community 347 - "Paused model assessment"
Cohesion: 0.22
Nodes (9): _auto_paused_models(), active_era(), assess(), _half(), fetch(), grade(), main(), sweep() (+1 more)

### Community 35 - "NBA second game projection tests"
Cohesion: 0.07
Nodes (16): _cons(), _dist(), _neutral(), _segments(), test_f1_is_priced_through_the_projections_own_error_not_the_markets(), test_f1b_does_not_score_a_books_number_off_the_consensus(), test_f1b_strength_is_the_predicted_move_in_the_sides_favour(), test_the_consensus_number_is_pinnacles_else_the_deciding_books_median() (+8 more)

### Community 351 - "Slate concentration and fade risk detection"
Cohesion: 0.16
Nodes (12): _fade_slate(), test_a_mixed_slate_is_ok(), test_all_home_ncaaf_slate_is_flagged_without_mlb_hardcoding(), test_all_unders_public_fade_risk_is_crit(), test_all_unders_public_fade_slate_is_crit(), test_fade_in_the_model_id_is_sport_agnostic(), test_thin_slate_is_not_a_finding(), test_unanimous_but_small_slate_is_warn_not_crit() (+4 more)

### Community 352 - "NHL prop odds alternate line tests"
Cohesion: 0.07
Nodes (22): due(), _book(), test_a_200_on_both_calls_merges_the_alternate_lines(), fake_fetch(), test_a_game_first_priced_inside_the_final_window_gets_nothing_more(), test_a_game_first_priced_inside_the_window_gets_one_decision_snapshot(), test_a_game_with_nothing_stored_is_owed_its_open(), test_a_moved_featured_line_keeps_the_old_number_under_the_alternate_key() (+14 more)

### Community 358 - "Ops alert watchdogs"
Cohesion: 0.09
Nodes (16): _announce(), _announce_and_ledger(), _post(), _alert(), _read_state(), _state_path(), _announce(), _announce() (+8 more)

### Community 366 - "Kalshi game market recorder"
Cohesion: 0.07
Nodes (17): event_code(), event_date(), kalshi_school(), _num(), probe(), record_game_markets(), resolve_events(), rows_for() (+9 more)

### Community 367 - "Odds pruning keeps openers"
Cohesion: 0.10
Nodes (11): _unprotected(), test_the_bookmaker_these_rows_use_survives_the_daily_prune(), test_both_delete_tiers_exclude_openers(), test_cfbd_archive_prefix_is_protected(), test_historical_backfill_rows_are_protected_in_odds(), test_line_shop_books_are_not_protected_wholesale(), test_openers_subquery_exists_and_orders_ascending(), test_prop_table_has_no_source_column_so_no_source_clause() (+3 more)

### Community 369 - "UFC fighter name resolution"
Cohesion: 0.16
Nodes (11): resolve_slug(), _slug_tokens(), test_a_generational_suffix_resolves_either_way(), test_a_near_miss_is_not_a_match(), test_a_reversed_name_order_resolves(), test_a_shared_surname_alone_is_not_a_match(), test_an_ambiguous_token_set_resolves_to_nothing(), test_an_empty_or_tokenless_name_is_safe() (+3 more)

### Community 373 - "NBA second game projection fixtures"
Cohesion: 0.18
Nodes (22): _box(), _games(), _inj(), _rapm_inputs(), _segment_rows(), _state(), test_a_back_to_back_is_read_from_the_schedule(), test_a_game_gets_no_projection_while_a_previous_date_game_could_still_be_running() (+14 more)

### Community 375 - "Refresh pass step ordering tests"
Cohesion: 0.10
Nodes (13): _order(), test_a_parallel_step_that_fails_is_still_recorded(), test_no_sequential_step_runs_while_a_parallel_group_is_open(), test_opening_signals_follows_every_scorer(), test_parlay_follows_opening_signals(), test_scoring_follows_every_ingest(), test_settle_follows_every_results_ingest(), test_sync_thresholds_follows_migrations_and_precedes_scoring() (+5 more)

### Community 379 - "NBA historical odds archive parser"
Cohesion: 0.15
Nodes (18): classify(), _fold(), _is_half(), _num(), parse_season(), _price(), team(), _page() (+10 more)

### Community 382 - "NFL in-play backtest replay harness"
Cohesion: 0.13
Nodes (11): align_states(), build_team_map(), _game_index(), kill_verdict(), load_cached_snapshots(), main(), replay(), _state_at() (+3 more)

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
Cohesion: 0.12
Nodes (10): sched(), test_a_fresh_savant_does_not_suppress_the_calibration_catch_up(), test_a_missing_sweeps_table_counts_as_stale(), test_a_recent_sweep_does_not(), test_an_old_sweep_triggers_the_catch_up(), test_model_calibration_belongs_to_the_pipeline_service(), test_the_catch_up_creates_the_review_tables_on_boot(), test_the_review_schema_is_not_gated_by_owns() (+2 more)

### Community 394 - "Injury fetch cache speed tests"
Cohesion: 0.07
Nodes (10): _clear_cache(), test_a_dead_database_leaves_the_cache_empty_not_broken(), test_a_failed_lookup_is_not_cached(), test_a_known_athlete_costs_no_request(), test_a_SUCCESSFUL_response_with_no_name_is_not_cached(), test_an_unknown_athlete_is_fetched_and_then_remembered(), test_one_team_failing_does_not_lose_the_others(), test_output_order_follows_the_team_list_not_completion_order() (+2 more)

### Community 396 - "MLB public fade top-K holdout"
Cohesion: 0.11
Nodes (19): ticket_bucket(), american_units(), bucket_win_rates(), build_candidates(), _fmt(), grade_under(), holdout_take(), load_db() (+11 more)

### Community 399 - "NFL live leader model tests"
Cohesion: 0.10
Nodes (19): fit_wp(), logit_irls(), wp_design(), wp_lookup(), art(), _d(), _raw(), test_600_seconds_and_both_lead_ends_are_inside() (+11 more)

### Community 40 - "NFL edge search helpers"
Cohesion: 0.04
Nodes (81): backfill_cost(), bets(), bh(), clean_2h(), fmt(), forward_2026(), hdr(), _line_models() (+73 more)

### Community 400 - "Mobile paused catalog tests"
Cohesion: 0.18
Nodes (10): _block(), _read(), test_paused_picks_reach_the_all_board_only_and_labelled(), test_stats_add_pick_refuses_a_paused_model(), test_the_bet_type_picker_filters_paused_models(), test_the_custom_model_picker_is_three_bet_types(), test_the_models_list_filters_paused_models(), test_the_pause_source_is_isModelPaused_not_a_hand_copied_set() (+2 more)

### Community 401 - "NFL in-play prop rule and staleness studies"
Cohesion: 0.19
Nodes (11): american_b(), boot_roi(), first_per_player(), grade(), load(), main(), report(), main() (+3 more)

### Community 402 - "NFL prop two sharp books study"
Cohesion: 0.17
Nodes (5): season_of(), test_season_of_reads_the_game_id_token(), test_the_2026_remeasure_did_not_move_the_24h_ceiling(), test_the_2026_remeasure_did_not_move_the_side_floors(), test_the_historical_grader_does_not_read_kalshi()

### Community 403 - "MLB play-by-play ingestor"
Cohesion: 0.16
Nodes (15): _bases_after_from_matchup(), parse_game_plays(), parse_play(), _split_event_type(), test_bases_empty_matchup(), test_bases_with_runners(), test_parse_game_plays_empty_feed(), test_parse_game_plays_walks_full_inning() (+7 more)

### Community 404 - "tests/test_promote_calibration_job.py"
Cohesion: 0.11
Nodes (3): test_a_refused_model_rolls_back_and_raises(), test_a_successful_promote_commits(), _job_promote_calibration()

### Community 406 - "tests/test_cfbd_snapshot_leakage.py"
Cohesion: 0.16
Nodes (9): _completed_before(), _ohio_state_2024(), test_boundary_is_strict(), test_datetime_like_values_are_handled(), test_empty_input(), test_end_of_regular_season_snapshot_excludes_playoffs(), test_missing_or_malformed_dates_are_dropped_not_admitted(), test_postseason_excluded_from_early_season_snapshot() (+1 more)

### Community 408 - "NFL weather cache importer"
Cohesion: 0.14
Nodes (11): main(), rows_from_file(), source_for(), stadium_from_name(), stored_files(), _INSERT_PLACEHOLDERS(), test_a_non_issued_or_empty_payload_yields_nothing(), test_every_hour_becomes_one_row_in_column_order() (+3 more)

### Community 410 - "NFL in-play remaining-points engine"
Cohesion: 0.17
Nodes (10): fit(), load_states(), main(), walk_forward_oos(), build_features(), features_from_state(), load_models(), predict_remaining() (+2 more)

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
Nodes (46): _american(), backfill_golf_rounds(), build_game_id(), _dg_get(), _earliest_commence_iso(), _event_meta_lookup(), event_slug(), ingest_golf_field() (+38 more)

### Community 421 - "Mobile bankroll settings card"
Cohesion: 0.18
Nodes (20): fieldFlow(), inv(), bankrollDraft(), bankrollFieldText(), canonical(), checkBankroll(), commitBankrollText(), editBankrollInput() (+12 more)

### Community 425 - "NFL odds cache import to Supabase"
Cohesion: 0.12
Nodes (9): _allowed(), _data_dirs(), test_a_rerun_after_the_resolver_improves_adds_only_the_gap(), test_every_buying_ingestor_keys_its_resume_on_a_source_marker(), test_no_undeclared_data_store_on_disk(), test_the_importer_resolves_a_postponed_game(), test_the_importer_still_refuses_an_event_with_no_game(), test_the_nfl_odds_cache_has_an_importer() (+1 more)

### Community 426 - "tests/test_health_check_observe.py"
Cohesion: 0.14
Nodes (10): _crit(), fake(), test_a_crit_does_not_fail_the_observe_path(), test_a_crit_still_fails_the_daily_step(), test_an_exception_does_not_fail_the_observe_path(), test_daily_syncs_thresholds_after_view_migrations(), test_it_still_runs_the_check_when_observing(), test_ok_is_identity_in_both_modes() (+2 more)

### Community 427 - "Health check deliverability tests"
Cohesion: 0.11
Nodes (10): test_a_game_date_inside_the_window_counts(), test_a_lookahead_commence_counts_even_when_game_date_is_outside(), test_a_signal_locked_after_first_pitch_was_never_deliverable(), test_a_signal_locked_before_first_pitch_still_counts(), test_a_signal_locked_exactly_at_first_pitch_counts(), test_a_started_game_outside_the_window_does_not_count(), test_it_fails_toward_noticing(), test_mixed_timestamp_shapes_are_parsed_not_string_compared() (+2 more)

### Community 428 - "NFL 2026 opener and wind tracker"
Cohesion: 0.09
Nodes (28): classify(), fetch(), grade_rows(), is_void(), lead_days(), _load_nfl_model(), main(), opener_verdict() (+20 more)

### Community 430 - "NFL prop shape simulation"
Cohesion: 0.20
Nodes (12): anchor_scale(), calibration(), grade(), latest(), load_odds(), main(), placebo_sf(), player_gamma() (+4 more)

### Community 431 - "tests/test_pick_lock_is_on_picks.py"
Cohesion: 0.16
Nodes (9): _between(), _sql(), test_a_bet_is_still_never_re_scored(), test_only_a_bet_locks_a_pair(), test_the_cleanup_covers_the_whole_look_ahead_window(), test_the_cleanup_never_touches_a_started_game_or_a_live_row(), test_the_lock_is_no_longer_ncaaf_specific(), test_the_prop_and_live_locks_are_unchanged() (+1 more)

### Community 433 - "NFL in-play prop settlement tests"
Cohesion: 0.20
Nodes (13): _box(), conn(), _game(), _live_bet(), raw(), _row(), test_a_final_with_no_box_score_yet_waits(), test_a_neighbouring_days_game_does_not_grade_the_wrong_player() (+5 more)

### Community 434 - "NCAAF board visibility tests"
Cohesion: 0.08
Nodes (22): _days_until(), _opener_rule(), _line(), _patch(), test_a_declined_rule_can_never_leak_a_signal(), test_a_fired_pick_clears_its_own_probability_floor(), test_a_no_signal_row_does_not_lock_an_ncaaf_game_for_the_week(), test_books_agreeing_is_a_no_signal_row() (+14 more)

### Community 435 - "NBA box score enrichment"
Cohesion: 0.21
Nodes (14): _check_unmapped(), _create(), ensure_tables(), load_schedule(), main(), run(), sdv_file(), _stored() (+6 more)

### Community 436 - "Env file fallback reader"
Cohesion: 0.06
Nodes (36): main(), scram_stored_key(), _classes(), diagnose(), bad(), _safe(), main(), database_url() (+28 more)

### Community 437 - "College football margin cover tests"
Cohesion: 0.13
Nodes (10): margin_cover_prob(), sweep_spread(), test_margin_cover_prob_ecdf(), test_rmse(), test_scorer_routes_margin_artifact_through_residual_prob(), test_spread_grading_home_and_away_sides(), test_spread_push_excluded_from_record(), test_threshold_filters_small_disagreements() (+2 more)

### Community 44 - "scripts: build_nfl_live_leader_artifact + model"
Cohesion: 0.09
Nodes (26): wp_design(), wp_lookup(), attach_games(), build_artifact(), check_possession(), _dk_pregame_spread(), _download(), _first_bets() (+18 more)

### Community 442 - "NFL in-play line churn study"
Cohesion: 0.19
Nodes (13): churn_table(), main(), verdict(), _snaps(), test_a_line_moving_every_interval_reads_as_under_sampled(), test_a_missing_key_column_fails_loudly_rather_than_grouping_coarser(), test_a_single_snapshot_contributes_no_interval(), test_a_still_line_reads_as_still() (+5 more)

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

### Community 456 - "College football team stats parsing"
Cohesion: 0.12
Nodes (12): parse_team_game_stats(), _possession_seconds(), _split_ratio(), _to_int(), test_an_fcs_name_that_extends_an_fbs_school_passes_through_unresolved(), test_parse_team_game_stats_builds_one_row_per_team(), test_parse_team_game_stats_skips_games_missing_from_the_id_map(), test_plays_is_none_when_neither_attempt_stat_is_present() (+4 more)

### Community 458 - "NFL ESPN injury ingest tests"
Cohesion: 0.11
Nodes (9): _fetch_nfl_espn_team_ids_core(), _nfl_espn_team_to_abbrev(), _fake_fetch(), test_core_nfl_listing_failure_returns_empty(), test_core_nfl_team_ids_resolve_lar_and_wsh_to_ours(), test_injury_fetch_raises_the_page_limit(), test_nfl_active_rows_are_dropped_and_out_keeps_espn_date(), test_nfl_name_join_uses_our_abbrevs_not_espns() (+1 more)

### Community 46 - "Worker job queue and retrain jobs"
Cohesion: 0.03
Nodes (35): derive_first_pitch(), run(), test_the_worker_job_is_registered_and_defaults_to_dry_run(), test_runner_captures_stdout_from_the_script_main(), test_the_discord_publish_job_calls_the_ordinary_producer(), test_the_discord_publish_job_takes_an_optional_date(), _execute(), _job_delete_custom_record_post() (+27 more)

### Community 462 - "Anonymous read access lockdown"
Cohesion: 0.03
Nodes (46): all_readable(), closed_tables(), lock_down(), lock_down_sql(), write_verbs_for(), _function_plan(), _function_signature(), main() (+38 more)

### Community 463 - "NFL in-play leader model config tests"
Cohesion: 0.12
Nodes (7): honest_probability(), test_a_loop_that_dies_fails_its_job(), test_it_decides_on_its_own_probability(), test_it_is_a_live_engine_model_that_settles_as_a_moneyline(), test_the_action_threshold_key_is_on_one_line(), test_the_loop_refuses_a_price_shorter_than_the_floor(), test_the_mlb_live_scorer_skips_it()

### Community 464 - "College football game-day odds cadence"
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

### Community 470 - "NFL prop scoring feature builder"
Cohesion: 0.08
Nodes (21): _add_features(), build_nfl_prop_scoring_rows(), _cols(), derived_targets(), _load(), _nfl_season(), _pool_mask(), _read() (+13 more)

### Community 472 - "NBA schedule ingestor and tests"
Cohesion: 0.20
Nodes (11): ot_periods(), schedule_rows(), season_str(), _tv(), _row(), test_a_late_west_coast_tip_keeps_its_eastern_date(), test_an_undecided_playoff_slot_is_skipped(), test_game_type_is_read_from_the_first_three_digits() (+3 more)

### Community 473 - "tests/test_nfl_prop_settle_name_fallback.py"
Cohesion: 0.27
Nodes (10): _never(), _row(), test_a_first_name_the_stat_log_spells_differently_still_matches(), test_a_scratched_player_is_not_graded_on_a_teammate_with_his_initial(), test_a_spelling_the_log_already_knows_is_a_scratch_not_a_spelling(), test_another_game_and_another_initial_never_match(), test_first_name_rule(), test_two_candidates_is_a_miss_not_a_guess() (+2 more)

### Community 474 - "Recap waits for NFL box scores"
Cohesion: 0.17
Nodes (8): _daily(), _job_body(), test_a_malformed_date_is_refused_before_anything_runs(), test_nfl_box_scores_are_ingested_before_settle(), test_nfl_finals_still_precede_the_box_scores(), test_the_job_does_not_read_rowcount_off_the_cursor(), test_the_job_only_clears_its_own_two_ledger_kinds(), test_the_job_posts_both_surfaces_through_the_ordinary_paths()

### Community 475 - "NFL prop injury and signal sweeps"
Cohesion: 0.18
Nodes (7): _bet(), _grade(), main(), signals(), load_injuries(), main(), The market stack (every signal that could locate the median)

### Community 476 - "tests/test_transaction_pooler.py"
Cohesion: 0.19
Nodes (8): _transaction_endpoint(), test_a_direct_connection_is_left_alone(), test_a_local_postgres_is_left_alone(), test_a_supabase_session_url_becomes_the_transaction_url(), test_it_is_idempotent(), test_only_the_port_changes(), test_the_escape_hatch_works(), test_the_job_queue_still_gets_session_mode()

### Community 477 - "NBA historical odds archive parsing"
Cohesion: 0.19
Nodes (11): _gid(), match(), odds_rows(), _swap(), _g(), test_a_labelled_pair_is_never_swapped(), test_a_neutral_pair_listed_the_other_way_is_swapped_with_its_signs(), test_a_refused_column_writes_no_row_for_it() (+3 more)

### Community 478 - "MLB totals retrain sweep job tests"
Cohesion: 0.10
Nodes (10): _side_rows(), test_marker_file_is_in_tree_so_the_freeze_would_not_block_the_worker(), test_missing_artifact_path_refuses_to_sweep_live(), test_over_covers_when_combined_score_beats_the_total_line(), test_price_below_the_house_floor_is_not_a_gradable_side(), test_push_on_the_total_emits_no_sides(), test_retrain_then_sweep_passes_the_new_path(), test_the_runner_retrains_then_sweeps_the_new_artifact() (+2 more)

### Community 480 - "Mobile sport filter persistence tests"
Cohesion: 0.14
Nodes (10): _load_body(), _sports(), _src(), test_a_visit_scoped_sport_change_does_not_persist(), test_a_writer_landing_during_the_hydrate_is_not_overwritten(), test_every_sport_survives_a_cold_start(), test_no_retired_sport_is_a_selectable_chip(), test_no_second_hand_written_sport_list_in_the_hook() (+2 more)

### Community 483 - "Trainer no-register mode tests"
Cohesion: 0.12
Nodes (9): not_registering(), registering(), test_a_normal_run_DOES_register(), test_baseline_artifacts_are_not_committable(), test_baseline_runs_write_somewhere_else(), test_default_is_to_register(), test_no_register_opens_no_database_connection(), _explode() (+1 more)

### Community 486 - "MLB run line feature types"
Cohesion: 0.18
Nodes (9): feature_matrix(), _runline_row(), test_empty_last3_is_missing_so_strict_dropna_drops_the_row(), test_feature_matrix_coerces_decimal_last3_to_float(), test_feature_matrix_coerces_last3_empty_and_none_to_numeric_nan(), test_raw_pandas_frame_leaves_last3_non_numeric(), test_train_and_runline_sweep_use_the_shared_coerce(), test_training_frame_empty_last3_becomes_nan_then_numeric() (+1 more)

### Community 487 - "supabase/functions/sharpsports/index.ts"
Cohesion: 0.30
Nodes (13): americanFromBetSlip(), asArray(), createContext(), isSettled(), json(), pick(), pullAndUpsert(), readBets() (+5 more)

### Community 489 - "NBA totals overs replay of the lab"
Cohesion: 0.16
Nodes (7): load_artifact(), lab_bets(), lab_gaps(), load(), main(), replay(), art()

### Community 490 - "Results recap backfill"
Cohesion: 0.20
Nodes (8): build_parser(), _date_is_over(), main(), post_backfill(), test_a_day_that_is_not_over_is_refused(), test_apply_calls_both_notifiers_for_that_date(), test_dry_run_is_the_default_and_posts_nothing(), test_main_dry_run_prints_and_returns()

### Community 491 - "NBA second game grid verdict tests"
Cohesion: 0.21
Nodes (20): _cell(), _grid(), _hgrid(), _house(), _mid(), test_a_cell_below_the_bet_count_enters_the_correction_at_p_one(), test_a_cell_clearing_every_bar_passes(), test_a_cell_with_no_dominant_side_is_not_held_to_a_blind_bet() (+12 more)

### Community 493 - "MLB retrain freeze guard tests"
Cohesion: 0.13
Nodes (9): assert_retrain_allowed(), test_import_time_flag_follows_marker_file(), test_marker_or_env_lifts_the_freeze(), test_mlb_prop_market_sweep_is_documented_exempt(), test_mlb_retrain_refused_while_incomplete(), test_mlb_threshold_sweeps_call_the_guard(), test_non_mlb_sports_are_not_gated(), test_repo_marker_file_is_present() (+1 more)

### Community 495 - "tests/test_worker_deps.py"
Cohesion: 0.22
Nodes (4): _requirements(), test_dashboard_packages_are_not_on_the_worker(), test_only_the_dashboard_imports_them(), test_the_worker_asks_for_the_cpu_build_of_xgboost()

### Community 497 - "College football totals lead study"
Cohesion: 0.26
Nodes (10): build_lead_table(), first_cross(), fmt(), grade(), line_as_of(), load_backfill(), main(), match_frame_to_odds() (+2 more)

### Community 50 - "scheduler.py"
Cohesion: 0.05
Nodes (51): abort_orphaned_refresh_runs(), build_scheduler(), _add_job(), _with_heartbeat(), _wrapped(), catch_up_daily_pipeline(), catch_up_refresh_pass(), catch_up_weekly_jobs() (+43 more)

### Community 504 - "NFL model import tests"
Cohesion: 0.15
Nodes (6): _import_under_scheduler_env(), _scheduler_env(), test_no_nfl_script_uses_the_bare_models_import(), test_the_card_imports_under_the_schedulers_invocation(), test_the_exemption_is_the_loader_and_it_still_exists(), test_the_loader_reaches_nfls_models_not_the_platforms()

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
Nodes (93): bh_fdr(), binom_p(), eval_rule(), load(), main(), devig_power(), games(), main() (+85 more)

### Community 512 - "tests/test_savant_freshness.py"
Cohesion: 0.14
Nodes (5): test_rows_are_stamped_with_a_capture_date(), test_savant_has_a_schedule(), test_the_insert_persists_the_stamp(), test_the_savant_job_belongs_to_the_pipeline_service(), test_the_stamp_defaults_rather_than_being_required_at_call_sites()

### Community 513 - "tests/test_scorer_nfl_prop_like_escape.py"
Cohesion: 0.23
Nodes (9): _between(), _broken_per_game_sql(), _first_sql(), _per_game_sql(), _sweep_sql(), test_escape_tripwire_is_on_the_pr_ci_subset(), test_live_per_game_clear_interpolates_with_one_game_id(), test_live_sweep_clear_interpolates_with_date_horizon_now() (+1 more)

### Community 522 - "CLV no-vig close capture tests"
Cohesion: 0.20
Nodes (8): _fn(), test_a_missing_bet_book_close_is_not_filled_from_another_book(), test_backfill_revisits_anything_that_is_not_standard_v2(), test_capture_grades_raw_same_book_and_a_separate_pinnacle_edge(), test_capture_stamps_method_and_close_book(), test_game_close_never_falls_back_past_first_pitch(), test_pinnacle_is_a_second_lookup_not_the_headline_close(), test_prop_close_stays_bounded_at_first_pitch()

### Community 524 - "Paused and no-signal pick rows"
Cohesion: 0.14
Nodes (11): _apply_no_signal(), _game_pick(), _prop_pick(), test_auto_paused_counts_as_paused(), test_no_signal_rows_persist_the_reason(), test_paused_game_model_avoid_stays_avoid_with_reason(), test_paused_game_model_bet_stays_bet_with_reason_and_stake(), test_paused_prop_model_avoid_stays_avoid_with_reason() (+3 more)

### Community 525 - "College football opener strategy study"
Cohesion: 0.23
Nodes (7): experiment_bands(), experiment_crossbook(), experiment_model(), _load_cross_book(), main(), _open_features(), wilson_ci()

### Community 526 - "NFL prop over lean study"
Cohesion: 0.25
Nodes (8): boot(), build(), grade(), implied(), lean_table(), load(), main(), profit()

### Community 527 - "Paused model assessment tests"
Cohesion: 0.15
Nodes (6): _rows(), test_a_cell_below_the_floor_is_not_a_result(), test_it_sweeps_both_pause_registers(), test_the_era_check_is_applied_to_every_candidate(), test_the_grade_reports_a_lower_bound_not_just_a_headline(), test_units_are_none_when_the_pick_carries_no_price()

### Community 528 - "Streamlit dashboard"
Cohesion: 0.16
Nodes (3): _fmt_et_time(), get_conn(), query()

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
Cohesion: 0.28
Nodes (7): _fit(), main(), _report(), run(), summarise(), walk_forward(), wilson()

### Community 532 - "tests/test_overnight_polling.py"
Cohesion: 0.24
Nodes (7): _hours(), _jobs(), _match(), test_every_hour_of_the_day_is_covered(), test_the_overnight_pass_is_the_ordinary_one(), test_the_overnight_window_exists(), test_the_windows_do_not_overlap()

### Community 535 - "NCAAF weather and wind totals study"
Cohesion: 0.23
Nodes (6): build_spots(), evaluate(), load_games(), main(), scoring_by_wind(), wilson()

### Community 537 - "NFL Kalshi price history fetch"
Cohesion: 0.11
Nodes (11): s(), candles(), get(), map_games(), paged(), parse_event(), probe(), games() (+3 more)

### Community 541 - "Pipeline watch post ledger tests"
Cohesion: 0.15
Nodes (7): test_a_confirmed_post_is_ledgered_so_the_run_can_be_verified(), test_a_missing_webhook_escalates_rather_than_vanishing(), test_an_occasional_kind_is_not_flagged_for_being_quiet(), test_an_unconfirmed_post_is_never_ledgered(), test_the_ledger_is_one_row_per_day_so_a_retry_cannot_double_count(), test_the_watch_belongs_to_the_pipeline_service(), _wire()

### Community 542 - "NCAAF situational spot search"
Cohesion: 0.18
Nodes (7): is_bowl_game(), build_spots(), evaluate(), load_team_games(), main(), wilson(), test_is_bowl_game()

### Community 546 - "tests/test_claude_rules_split.py"
Cohesion: 0.18
Nodes (4): test_claude_md_still_points_at_the_rules_directory(), test_every_rule_file_actually_carries_rules(), test_every_rule_file_is_path_scoped(), test_no_rule_was_lost_when_the_split_happened()

### Community 547 - "In-play honest cut sweep"
Cohesion: 0.35
Nodes (9): bets_split(), _fmt(), _grid(), main(), _print_grid(), run_mlb(), run_ncaaf(), _summ() (+1 more)

### Community 548 - "tests/test_dedupe_opening_signals.py"
Cohesion: 0.12
Nodes (8): test_a_graded_row_is_never_deleted(), test_a_row_with_computed_clv_is_never_deleted(), test_every_field_that_defines_the_bet_must_agree(), test_the_delete_selects_through_the_same_gates(), test_the_pair_must_be_an_old_shape_new_shape_pair(), test_the_report_and_the_delete_share_one_definition(), test_the_row_kept_is_the_one_locked_earlier(), test_the_unresolved_report_excludes_what_the_delete_resolves()

### Community 549 - "NFL backfill retry resilience"
Cohesion: 0.12
Nodes (5): test_a_dropped_connection_is_retried(), test_an_http_error_is_NOT_retried(), test_it_gives_up_rather_than_looping_forever(), test_resume_probes_ONE_market_not_any_row(), test_resume_with_no_probe_market_skips_nothing()

### Community 550 - "NFL prop odds ingestion"
Cohesion: 0.12
Nodes (15): backfill_nfl_prop_odds(), backfilled_dates(), census_books(), _credits_used(), _event_props(), _get(), _ingest_events(), list_events() (+7 more)

### Community 551 - "Live model holdout side-by-side comparison"
Cohesion: 0.31
Nodes (6): bias_table(), confident_share(), load_artifact(), main(), poisson_sf(), predict()

### Community 552 - "tests/test_pbp_backfill_resilience.py"
Cohesion: 0.24
Nodes (6): _backfill_body(), test_a_failed_game_rolls_the_connection_back(), test_a_run_that_wrote_nothing_reports_an_error_not_a_success(), test_errors_are_counted_not_just_logged(), test_partial_failures_are_surfaced_too(), test_the_rollback_cannot_itself_raise()

### Community 553 - "MLB live game discovery tests"
Cohesion: 0.18
Nodes (7): _discover_active_games(), _game_id_from_statsapi(), test_a_game_seen_twice_is_polled_once(), test_discovery_asks_statsapi_about_every_date_it_is_given(), fake_schedule(), test_discovery_still_accepts_a_bare_string(), test_one_broken_date_does_not_lose_the_other()

### Community 559 - "NFL prop pulled quote filtering"
Cohesion: 0.32
Nodes (8): drop_pulled_quotes(), _ts(), _q(), test_a_book_on_its_own_cadence_is_not_penalised_inside_three_hours(), test_a_book_that_stopped_returning_the_game_is_dropped(), test_a_player_the_book_stopped_quoting_is_dropped(), test_a_whole_market_the_book_pulled_is_dropped(), test_rows_from_one_fetch_minutes_apart_are_kept_and_a_line_move_is_not_a_pull()

### Community 562 - "College football loop timing tests"
Cohesion: 0.15
Nodes (7): _main_source(), test_an_unanswered_state_feed_does_not_look_like_the_slate_ending(), test_loop_exits_early_when_no_kickoff_is_near(), test_loop_polls_at_the_idle_cadence_when_nothing_is_live(), test_loop_sleeps_the_remainder_not_a_flat_interval(), test_loop_warns_when_a_pass_overruns_its_interval(), test_odds_fetch_uses_the_odds_cadence_not_the_loop_cadence()

### Community 563 - "NFL in-play prop state builder"
Cohesion: 0.27
Nodes (5): build(), events(), _key(), load_pbp(), verify()

### Community 567 - "Voiding picks"
Cohesion: 0.23
Nodes (6): announce_posted_voids(), build_parser(), main(), _select(), void(), _job_void_picks()

### Community 568 - "NFL prop book sweep"
Cohesion: 0.14
Nodes (12): _actuals(), _board(), p(), _line(), main(), _run(), soft_verdict(), test_a_bettable_book_still_passes() (+4 more)

### Community 569 - "tests/test_game_log_backfill_skip.py"
Cohesion: 0.25
Nodes (5): _backfill_body(), test_a_game_absent_from_our_games_table_is_still_skipped(), test_no_skip_is_keyed_on_date_alone(), test_the_coverage_set_is_scoped_to_the_season_being_built(), test_the_skip_is_keyed_on_game_id()

### Community 572 - "NCAAF line move spots"
Cohesion: 0.27
Nodes (6): eval_follow_spread(), eval_follow_total(), load(), main(), _summ(), wilson()

### Community 573 - "NBA public splits pipeline step"
Cohesion: 0.13
Nodes (12): inserted_minus_start_min(), run_forward(), step_nba_public_splits(), test_v1_inserted_lag_is_minutes_after_the_listed_start(), Coverage, Forward capture (2026-27), How to read it, NBA public betting splits (Action Network) — `nba_public_splits` (+4 more)

### Community 574 - "tests/test_prompt_reads_thresholds.py"
Cohesion: 0.18
Nodes (4): test_the_auto_pause_lookup_fails_open(), test_the_prompt_carries_no_per_model_cut(), test_the_prompt_still_says_it_is_pasted_once(), test_the_sync_mirrors_both_pause_registers()

### Community 575 - "tests/test_system_health_meta_steps.py"
Cohesion: 0.25
Nodes (5): _meta_steps(), test_aborted_sentinel_is_excluded(), test_health_check_is_excluded(), test_model_quality_is_excluded(), test_sentinel_matches_the_writer()

### Community 577 - "NBA quarter scores parser"
Cohesion: 0.25
Nodes (9): et_date(), _int(), parse_period_rows(), _event(), test_espn_team_codes_map_to_ours(), test_one_row_per_period_under_our_game_id(), test_overtime_periods_follow_the_fourth(), test_quarters_that_do_not_sum_to_the_final_are_skipped() (+1 more)

### Community 58 - "tests: test_discord_notifier + test_discord_live_field"
Cohesion: 0.17
Nodes (13): _sig(), test_a_strictly_better_book_becomes_the_headline(), test_an_equal_or_worse_price_never_replaces_draftkings(), test_draftkings_winning_its_own_shop_is_published_as_draftkings(), test_every_pre_game_producer_computes_good_to(), test_good_to_is_published_when_the_producer_supplies_it(), test_good_to_is_simply_absent_when_it_cannot_be_computed(), test_it_works_on_plus_money_too() (+5 more)

### Community 580 - "scripts/render_brand_icons.py"
Cohesion: 0.24
Nodes (3): draw_mark(), main(), render()

### Community 581 - "NFL wind stake sizing tests"
Cohesion: 0.22
Nodes (6): _probe(), test_an_uncalibrated_lead_is_sized_rather_than_zeroed_on_the_card(), test_at_the_default_gate_that_same_row_does_not_fire_at_all(), test_the_eval_board_agrees_with_the_card(), test_the_probability_was_already_clipping(), test_the_stake_clips_to_lead_seven_instead_of_returning_zero()

### Community 584 - "NBA injury report page parsing"
Cohesion: 0.18
Nodes (7): _bands(), _column_of(), _columns(), _hrules(), _lines_of(), parse_page_layout(), _text()

### Community 586 - "supabase/functions/stripe-webhook/index.ts"
Cohesion: 0.31
Nodes (9): applySubscription(), iso(), resolveUserId(), stripeGet(), timingSafeEqual(), toHex(), verifySignature(), admin (+1 more)

### Community 588 - "NFL in-play joint distribution"
Cohesion: 0.20
Nodes (6): gaussian_copula_joint(), dist_out(), _pmf(), test_copula_covariance_takes_the_sign_of_rho(), cov(), test_copula_preserves_both_marginals_exactly()

### Community 589 - "tests/test_mobile_neutral_signal_label.py"
Cohesion: 0.31
Nodes (7): _read(), test_explainer_names_neutral(), test_filters_and_card_speak_the_display_name(), test_model_screens_speak_the_display_name(), test_no_member_label_prints_a_raw_signal_type(), test_none_badge_reads_neutral(), test_withdrawn_pick_is_not_badged_neutral()

### Community 591 - "College football team list parsing"
Cohesion: 0.33
Nodes (4): parse_teams(), test_parse_teams_all_schools_pull_never_defaults_to_fbs(), test_parse_teams_joins_alt_names(), test_parse_teams_keeps_cfbd_classification_and_lowercases_it()

### Community 593 - "tests/test_scorer_commits_per_game.py"
Cohesion: 0.40
Nodes (8): _between(), _run_scorer_body(), test_a_lost_connection_re_runs_the_game_once_and_never_the_pass(), test_each_game_is_its_own_committed_unit(), test_no_bulk_delete_of_non_bet_rows_precedes_the_loop(), test_picks_are_only_counted_once_the_game_committed(), test_the_housekeeping_delete_is_a_sweep_after_the_loop(), test_the_outer_handler_still_records_the_failure()

### Community 594 - "NCAAF scoreboard yardline parsing tests"
Cohesion: 0.21
Nodes (6): _abbrev_fits(), _parse_yardline(), _cfbd_game(), test_cfbd_state_carries_the_yardline_and_the_raw_situation(), test_cfbd_yardline_from_every_stored_situation(), test_cfbd_yardline_refuses_rather_than_guesses()

### Community 595 - "First pitch delivery guard tests"
Cohesion: 0.11
Nodes (7): test_capture_compares_the_picks_own_clock_not_the_capture_clock(), test_capture_fails_open_on_a_missing_timestamp(), test_delivery_fails_open_too(), test_health_check_uses_the_same_first_pitch_bound_as_discord(), test_mixed_timestamp_shapes_are_parsed_not_string_compared(), test_the_dry_run_count_uses_the_same_predicate_as_the_insert(), test_the_restatement_path_is_deliberately_not_guarded()

### Community 596 - "Threshold sweep price floor tests"
Cohesion: 0.29
Nodes (7): _apply_price_floor(), _row(), test_a_model_with_no_floor_is_untouched(), test_every_prop_model_in_the_sweep_has_a_floor_to_apply(), test_plus_money_always_survives(), test_prices_juicier_than_the_floor_are_dropped(), test_the_boundary_matches_the_scorer()

### Community 597 - "Database setup column tests"
Cohesion: 0.23
Nodes (6): _get_columns(), test_games_table_columns(), test_injuries_table_columns(), test_odds_table_columns(), test_picks_table_columns(), test_schema_is_idempotent()

### Community 598 - "College football stats ingestion"
Cohesion: 0.12
Nodes (15): _int(), _num(), parse_advanced_stats(), parse_ratings(), parse_returning(), parse_season_stats(), parse_talent(), parse_venues() (+7 more)

### Community 599 - "Pipeline watch run tests"
Cohesion: 0.17
Nodes (8): test_a_clean_run_still_posts(), test_a_failed_query_rolls_back_and_does_not_sink_the_run(), test_a_run_with_findings_posts_them(), test_every_not_ok_health_check_is_reported(), test_the_kill_switch_works(), _enabled(), findings_from_checks(), run_watch()

### Community 60 - "tests: test_wnba_availability + wnba_availability"
Cohesion: 0.07
Nodes (45): absence_features(), absent_teammates(), build_context_features(), expected_rotation(), is_starter_tier(), _mean(), prior_rows(), recent_team_game_dates() (+37 more)

### Community 600 - "NBA inactives and officials rows"
Cohesion: 0.24
Nodes (8): fetch_advanced(), _game(), _gid(), inactive_rows(), official_rows(), _season_str(), test_inactive_rows_carry_team_and_leave_reason_null(), test_officials_rows_strip_the_jersey_and_join_the_name()

### Community 604 - "Market coverage probe tests"
Cohesion: 0.33
Nodes (5): candidate_markets(), _standard_markets(), test_it_asks_about_the_board_columns_that_are_permanently_blank(), test_no_market_is_asked_about_twice(), test_the_probe_asks_about_every_market_we_pull_and_its_alternate()

### Community 606 - "NFL prop universe summary tests"
Cohesion: 0.29
Nodes (6): _universe_summary(), test_a_universe_without_the_model_sums_still_summarises(), test_mean_projection_and_mean_actual_separate_mean_bias_from_shape_bias(), test_model_over_rate_and_its_gap_are_reported(), _universe(), test_a_nonfinite_fair_price_cannot_switch_the_gate_off()

### Community 608 - "supabase/functions/sharpsports-webhook: index + index"
Cohesion: 0.25
Nodes (5): internalIdFor(), pick(), admin, admin, cors

### Community 609 - "NFL odds cache import"
Cohesion: 0.24
Nodes (7): game_index(), main(), resolve(), rows_from_file(), stored_pairs(), stored_served(), _ts()

### Community 612 - "supabase/functions/stripe-checkout/index.ts"
Cohesion: 0.31
Nodes (8): customerFor(), form(), json(), stripe(), admin, cors, PRICES, TRIAL_DAYS

### Community 614 - "tests/test_book_list_budget.py"
Cohesion: 0.31
Nodes (4): _names(), test_every_book_the_nfl_prop_model_bets_at_is_actually_fetched(), test_the_nfl_prop_pull_is_one_group_with_both_references_in_it(), test_the_shared_list_is_one_group()

### Community 615 - "College football in-play price gate tests"
Cohesion: 0.18
Nodes (4): test_a_cheaper_book_no_longer_buys_its_way_past_the_floor(), test_the_bet_is_still_recorded_at_the_best_price(), test_the_gate_reads_the_draftkings_numbers(), test_the_stale_line_cap_still_judges_the_dk_edge()

### Community 617 - "API call daily rollup"
Cohesion: 0.09
Nodes (10): test_a_fold_can_never_lower_a_stored_total(), test_a_new_process_does_not_prune_on_its_first_flush(), test_prune_rolls_up_before_it_deletes(), test_the_daily_table_is_created_and_locked_down(), test_the_daily_table_keys_on_day_api_and_source(), test_the_rollup_groups_by_eastern_day_not_utc(), test_the_rollup_reads_only_yesterday_and_today(), test_the_rollup_survives_a_failure_without_blocking_the_prune() (+2 more)

### Community 62 - "NBA game market search lab"
Cohesion: 0.05
Nodes (60): assemble(), attach_close(), bars(), bet_frame(), blind_bets(), blind_first_fetch(), boot_ci(), by_season() (+52 more)

### Community 621 - "MLB live game state poller"
Cohesion: 0.22
Nodes (7): _bases_state(), _extract_state(), test_bases_state_empty(), test_bases_state_loaded(), test_bases_state_single_runner(), test_extract_state_handles_empty_feed(), test_extract_state_pulls_fields_from_live_feed()

### Community 622 - "SBR odds CSV loader"
Cohesion: 0.25
Nodes (3): canonical_abbrev(), parse_csv_file(), test_sbr_abbreviations_are_canonicalised_for_mlb_only()

### Community 623 - "College football totals weather study"
Cohesion: 0.31
Nodes (7): sweep_total(), arm_frame(), load_issued(), main(), run_arm(), wilson(), test_total_grading_both_sides_and_push()

### Community 624 - "NCAAF steam lag study"
Cohesion: 0.27
Nodes (9): attach_scores(), build_events(), fmt(), grade(), lines_at_pulls(), load(), main(), summarise() (+1 more)

### Community 629 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.47
Nodes (6): contentHeight(), evalExpr(), lineOf(), styleBlock(), styleProp(), visualHeight()

### Community 63 - "Football in-play game state"
Cohesion: 0.12
Nodes (18): _as_float(), _as_int(), _as_opt_float(), _as_opt_int(), from_espn(), from_extract(), from_pbp_row(), smooth_pass_rate() (+10 more)

### Community 630 - "Live slate dates around midnight"
Cohesion: 0.27
Nodes (6): live_slate_dates(), _at(), test_by_daytime_yesterday_is_dropped(), test_just_after_midnight_still_asks_about_yesterday(), test_just_before_midnight_asks_about_today_only(), test_today_is_always_first()

### Community 633 - "Model quality CLV and ROI alerts"
Cohesion: 0.14
Nodes (8): test_clv_clear_negative_vs_baseline_is_flagged(), test_raw_one_sided_clv_is_ignored(), test_roi_collapse_is_crit_when_hit_rate_dies(), test_roi_ignores_unpriced_profit_flat(), detect_clv_degradation(), detect_roi_collapse(), _sample(), units_from_profit_flat()

### Community 635 - "tests/test_demote_ncaaf_over_under_platt.py"
Cohesion: 0.32
Nodes (4): _stmts(), test_it_demotes_only_the_measured_promotion(), test_it_does_not_move_the_gate_the_floor_or_a_pause(), test_migration_is_one_statement()

### Community 636 - "MLB runline retrain sweep job"
Cohesion: 0.10
Nodes (8): test_the_raised_timeout_is_restored_after_the_job(), test_the_restore_puts_back_a_pre_existing_value(), test_marker_file_is_in_tree_so_the_freeze_would_not_block_the_worker(), test_missing_artifact_path_refuses_to_sweep_live(), test_retrain_then_sweep_passes_the_new_path(), test_the_runner_retrains_then_sweeps_the_new_artifact(), _job_mlb_runline_retrain_sweep(), _job_retrain_model()

### Community 637 - "tests/test_discord_post_one_pick_migration.py"
Cohesion: 0.29
Nodes (3): _pairs(), test_it_names_each_measured_extra_and_the_row_kept(), test_the_update_does_not_rewrite_the_graded_outcome()

### Community 638 - "tests/test_game_scorer_spares_nfl_props.py"
Cohesion: 0.43
Nodes (5): _between(), _run_scorer_body(), test_an_nfl_game_never_enters_the_per_game_clear(), test_both_live_non_bet_clears_leave_nfl_rows(), test_the_left_out_ufc_clear_only_removes_unsettled_non_bets()

### Community 639 - "NFL in-play backtest states"
Cohesion: 0.24
Nodes (3): load_pbp(), _repair_day_offsets(), sample_states()

### Community 64 - "NFL in-play market pricing engine"
Cohesion: 0.08
Nodes (31): _model_price(), american_to_decimal(), american_to_prob(), anchor_to_market(), devig_power(), margin_pmf(), _over_under(), price_moneyline() (+23 more)

### Community 641 - "tests/test_mobile_ota_self_update.py"
Cohesion: 0.32
Nodes (4): _read(), test_app_root_mounts_the_ota_updater(), test_the_pieces_exist(), test_the_updater_actually_applies_the_update()

### Community 642 - "NBA second game emit and bootstrap tests"
Cohesion: 0.22
Nodes (6): _emit_world(), _spy_run_cells(), test_closing_value_is_priced_with_the_markets_empirical_distribution(), test_every_family_emits_exactly_its_cells_through_the_harness(), test_the_d_cells_are_gated_on_the_points_own_decision_times(), test_the_bootstrap_is_seeded_and_refines_small_p()

### Community 643 - "College football weather backfill"
Cohesion: 0.29
Nodes (5): backfill(), _celsius_to_f(), _fetch_weather(), ingest_upcoming(), _utc_offset_from_lon()

### Community 644 - "NBA archive odds row shaping"
Cohesion: 0.40
Nodes (3): iso_z(), snapshot_times(), test_snapshot_times_are_noon_on_the_date_and_one_minute_before_tip()

### Community 645 - "College football issued forecast backfill"
Cohesion: 0.36
Nodes (6): backfill(), fetch_venue_season(), _get(), _kick_date(), _kick_hour(), _parse_kick()

### Community 65 - "NFL in-play flow model tests"
Cohesion: 0.02
Nodes (125): _connect(), evaluate(), _infer_position(), main(), _pool_prior(), report(), _rows_for_market(), _to_states() (+117 more)

### Community 655 - "College football team name slugs"
Cohesion: 0.22
Nodes (5): _loose_orientation(), ncaaf_slug(), _slug_extends(), _slug_pair(), test_slug()

### Community 656 - "NBA public splits side parsing"
Cohesion: 0.15
Nodes (8): an_pct(), parse_v1_sides(), parse_v2_sides(), v1_consensus_row(), test_a_one_percent_side_is_not_inflated_to_100(), test_live_entries_of_an_in_progress_game_are_ignored(), test_out_of_range_or_junk_percentages_are_refused(), test_v2_values_land_on_the_right_side()

### Community 659 - "NBA box and archive sample checks"
Cohesion: 0.25
Nodes (6): _blank(), _flt(), _int(), sample_compare(), _txt(), sign_sample()

### Community 660 - "Parlay correlation estimates"
Cohesion: 0.36
Nodes (5): estimate(), estimate_basketball(), estimate_mlb(), main(), _median()

### Community 663 - "College football consensus gate study"
Cohesion: 0.39
Nodes (6): fmt(), grade(), load_closes(), main(), match(), wilson()

### Community 665 - "NFL wind forecast validation"
Cohesion: 0.29
Nodes (10): build(), games(), hourly(), main(), _rate(), sec_coverage(), sec_error(), sec_rule() (+2 more)

### Community 666 - "Revoke remaining write grants tests"
Cohesion: 0.15
Nodes (6): test_it_asserts_the_app_write_surface_survives(), test_it_revokes_every_write_privilege(), test_select_is_never_revoked(), test_the_roles_are_named_never_public(), test_the_runners_transaction_stripping_leaves_the_do_block_intact(), test_the_set_is_computed_from_the_policy_rule_not_listed()

### Community 669 - "Published record units"
Cohesion: 0.05
Nodes (35): _apply_one(), _is_transient_lock_error(), _with_lock_timeout(), test_conviction_floors_at_one_not_a_half(), test_conviction_is_flat_for_every_kelly(), test_conviction_is_flat_regardless_of_kelly(), test_favourites_risk_more_until_the_cap_binds(), test_flat_conviction_is_still_price_adjusted() (+27 more)

### Community 670 - "Calibration eligibility notes"
Cohesion: 0.22
Nodes (3): test_eligibility_notes_parse_the_payload_verdicts(), _calibration_eligibility_notes(), _report_model_calibration()

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
Cohesion: 0.22
Nodes (3): load_data(), main(), scan_spot()

### Community 695 - "Every named sportsbook is fetched"
Cohesion: 0.18
Nodes (5): _param_books(), test_a_sharp_reference_is_never_also_a_soft_book(), test_every_bettable_book_can_be_named_to_a_human(), test_every_named_book_is_in_the_pull_that_serves_it(), test_the_nfl_backfill_defaults_to_the_live_pull()

### Community 697 - "NFL odds table builder"
Cohesion: 0.43
Nodes (4): load_games(), main(), wide_spreads(), wide_totals()

### Community 699 - "Market board and pull agreement tests"
Cohesion: 0.25
Nodes (4): _board_markets(), table(), test_the_mlb_board_and_the_mlb_pull_are_one_set(), test_the_tables_are_locked_down_at_the_create_site()

### Community 701 - "Odds credit burn watch tests"
Cohesion: 0.25
Nodes (4): test_burn_is_judged_against_the_cap_not_against_yesterday(), test_burn_survives_a_non_numeric_credits_column(), test_failed_api_calls_are_reported_even_when_burn_is_low(), findings_from_burn()

### Community 705 - "Mobile stats filter checks"
Cohesion: 0.18
Nodes (9): chip, lineOnlyFn, playersDay, ROOT, sportReset, stats, teams, teamsDay (+1 more)

### Community 707 - "NHL goalie line helpers"
Cohesion: 0.83
Nodes (4): _goalie_line(), regressed(), saved_above(), tot()

### Community 708 - "Registered but not firing models tests"
Cohesion: 0.17
Nodes (5): test_a_model_with_picks_but_no_threshold_row_is_still_listed(), test_it_reports_whether_the_model_is_paused_and_whether_it_is_trained(), test_performance_starts_from_the_registered_models_not_the_graded_picks(), test_the_sport_survives_when_there_are_no_graded_picks(), test_the_zero_state_short_circuits_before_the_roi_row()

### Community 71 - "tests/test_live_orchestrator.py"
Cohesion: 0.05
Nodes (38): should_fetch(), split_triggers(), under_credit_cap(), apply_daily_cap(), classify_live_signal(), _ev_floor(), _consume_source(), _t() (+30 more)

### Community 711 - "Every model is real money test"
Cohesion: 0.43
Nodes (4): _allowed(), _hits(), _rel(), test_the_repo_has_no_record_only_or_paper_tracking_mode()

### Community 712 - "NBA missing game log fill"
Cohesion: 0.29
Nodes (5): fill_missing_game_logs(), neutral_fill_rows(), _upsert_player_log(), test_the_neutral_fill_matches_a_game_id_that_lost_its_leading_zeros(), test_the_neutral_fill_writes_only_the_missing_games()

### Community 713 - "NBA second game price cache checks"
Cohesion: 0.33
Nodes (3): _games_file(), test_a_segment_file_missing_part_of_a_season_is_refused(), test_full_checks_the_price_cache_for_every_graded_season_before_building_anything()

### Community 714 - "NFL opener calibration"
Cohesion: 0.38
Nodes (3): _load_backtest(), main(), selected_bets()

### Community 715 - "NCAAF venue travel features"
Cohesion: 0.18
Nodes (6): _venue_features(), test_altitude_climb_is_signed_from_each_teams_own_elevation(), test_both_teams_travel_at_a_neutral_site(), test_eastward_travel_is_positive_tz_shift(), test_host_travels_zero_at_a_normal_home_game(), test_missing_venue_data_yields_nulls_not_zeros()

### Community 717 - "Eastern game date everywhere"
Cohesion: 0.25
Nodes (4): _sources(), test_no_game_date_is_derived_from_the_container_clock(), test_the_live_modules_cannot_even_name_date_today(), test_today_et_is_eastern_inside_the_window_that_broke()

### Community 719 - "Mobile accessibility verify script"
Cohesion: 0.67
Nodes (3): read(), readUtf8(), verticalSlop()

### Community 72 - "Market handicap feature tests"
Cohesion: 0.05
Nodes (36): attach_market_handicap(), build_public_features(), empty_handicap(), favorite_side(), _rlm(), row_is_pregame(), select_latest_pregame_splits(), _split() (+28 more)

### Community 721 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.67
Nodes (3): closeOf(), openTag(), toggleUse()

### Community 731 - "Pipeline silence findings"
Cohesion: 0.29
Nodes (4): test_the_silence_finding_says_how_regular_the_kind_was(), _rows(), _silent_kinds(), _step_regressions()

### Community 74 - "Prop CLV and SQL escaping tests"
Cohesion: 0.06
Nodes (23): _is_main_guard(), _modules_with_guard(), test_at_least_one_entrypoint_is_scanned(), test_nothing_is_defined_after_the_main_guard(), test_the_nfl_label_map_is_the_inverse_of_the_nfl_publisher(), _fn(), test_a_backfill_failure_never_breaks_settlement(), test_a_pick_is_only_stamped_captured_once_a_measure_resolved() (+15 more)

### Community 75 - "College football margin evaluation"
Cohesion: 0.21
Nodes (11): build_frames(), _fit(), fit_and_register(), fit_and_register_totals(), main(), _matrix(), _print_sweep(), rmse() (+3 more)

### Community 755 - "Game pick settlement window"
Cohesion: 0.29
Nodes (4): test_the_game_window_stays_fixed_when_nothing_is_stranded(), _game_settle_window_days(), _settle_game_picks(), _settle_game_picks_window()

### Community 758 - "NCAAF game feature assembly"
Cohesion: 0.20
Nodes (4): _assemble_ncaaf_features(), _game_tier(), test_assembly_carries_venue_context_and_hfa(), test_season_opener_gets_a_zero_rest_differential_not_a_null()

### Community 76 - "ncaaf_live/tests/test_serve.py"
Cohesion: 0.06
Nodes (40): _clock_seconds(), extract_live_states_cfbd(), _parse_situation(), _cfbd_game(), _ctx(), engine(), _no_ev_floor(), _settled() (+32 more)

### Community 81 - "docs: nhl_market_lab + nhl_clv_ev_assessment"
Cohesion: 0.07
Nodes (41): show(), nhl_research worker job, scripts/nhl_derivative_totals_backtest, data/ingestors/nhl_derivative_odds_history, models/nhl_props.py (Spec per market), Anytime goalscorer: not a candidate once names corrected, nhl_moneyline and nhl_moneyline_regulation: no cut clears, Game models: lock later? Refuted (+33 more)

### Community 82 - "Mobile script test runner via Node"
Cohesion: 0.11
Nodes (24): _load_state_dir(), _raw_error_lines(), _read(), _run_node(), test_aborts_are_silent_and_offline_slow_are_narrow(), test_aborts_render_nothing_and_every_catch_skips_them(), test_designer_review_fixes_behaviour(), test_error_state_component() (+16 more)

### Community 852 - "Mobile NHL look-ahead window tests"
Cohesion: 0.29
Nodes (5): _fn(), _read(), test_the_nhl_read_matches_the_other_look_aheads(), test_the_sport_chip_is_the_hook_not_an_allowlist(), test_use_today_picks_fetches_nhl_across_that_window()

### Community 856 - "Refresh pass finding tests"
Cohesion: 0.33
Nodes (4): test_a_clean_pass_produces_no_finding(), test_a_pass_with_failed_steps_is_reported(), test_a_pass_with_no_finish_is_reported_without_over_reading_it(), findings_from_passes()

### Community 86 - "scripts/nfl_edge_preregistered_2026.py"
Cohesion: 0.10
Nodes (38): bar(), bets_frame(), bh(), binom_line(), _by_game(), cell(), fam(), first_last() (+30 more)

### Community 860 - "Pause check helper tests"
Cohesion: 0.40
Nodes (3): _is_paused(), test_config_pauses_still_work_through_the_same_helper(), test_the_scorer_still_honours_a_leftover_auto_pause_row()

### Community 864 - "NBA public splits game dating"
Cohesion: 0.29
Nodes (5): et_game_date(), _game_meta(), team_abbr(), test_a_late_west_coast_tip_belongs_to_the_previous_et_date(), test_team_ids_come_from_the_abbr_then_the_full_name()

### Community 865 - "NBA public splits quality flags"
Cohesion: 0.29
Nodes (4): quality_backfill_statements(), quality_flag(), test_the_quality_rule_puts_reversed_ahead_of_late(), test_the_stored_row_backfill_flags_exactly_what_the_rule_flags()

### Community 867 - "MLB market handicap signals"
Cohesion: 0.29
Nodes (4): build_rich_handicap(), _fav_signed_home_move(), _gated_flag(), _mul()

### Community 868 - "NCAAF travel distance and time zones"
Cohesion: 0.29
Nodes (5): haversine_miles(), tz_offset_from_lon(), trip(), test_haversine_matches_real_geography(), test_timezone_offsets_land_in_the_right_zones()

### Community 87 - "tests: test_player_positions + player_positions_ingestor"
Cohesion: 0.06
Nodes (28): _basketball(), basketball_group(), _fresh_source_ids(), _get_json(), ingest_player_positions(), match_to_log(), _name_index(), _ncaaf() (+20 more)

### Community 874 - "Opening versus closing strategy analysis"
Cohesion: 0.43
Nodes (4): _fmt(), _profit_sql(), _row(), strategy_analysis()

### Community 875 - "NBA public splits pair validation"
Cohesion: 0.33
Nodes (5): clean_pair(), test_a_lone_side_is_kept_as_served(), test_a_pair_that_does_not_sum_to_100_is_dropped(), test_a_valid_pair_sums_to_100_within_rounding(), test_a_zero_zero_pair_is_missing_not_zero()

### Community 88 - "NBA prop market decision tests"
Cohesion: 0.08
Nodes (33): fair_under(), q(), run(), run_full(), _settle(), test_a_fetch_after_now_or_at_tip_and_a_close_row_never_decide(), test_a_fetch_older_than_the_window_is_not_a_price(), test_a_game_already_bet_is_never_decided_again() (+25 more)

### Community 884 - "Pregame scorer cleanup scoping tests"
Cohesion: 0.33
Nodes (3): _run_scorer_body(), test_every_housekeeping_delete_in_run_scorer_is_scoped_to_the_subset(), test_the_subset_predicate_never_builds_an_empty_IN_list()

### Community 885 - "NBA SBR archive moneyline timing"
Cohesion: 0.40
Nodes (3): ml_timing(), sign_agreement(), test_ml_timing_and_sign_agreement_count_what_they_say()

### Community 89 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.04
Nodes (48): a11ySrc, allowHit, ALLOWLIST, app, badExempt, bar, bareClose, baselineLeft (+40 more)

### Community 93 - "MLB totals public fade tests"
Cohesion: 0.14
Nodes (25): find_fade_bets(), under_in_odds_band(), _dk_board(), _quote(), _quotes(), _slate(), _split(), test_always_under_one_per_game() (+17 more)

### Community 98 - "NBA play-by-play ingestor"
Cohesion: 0.05
Nodes (56): nba_team(), active_queries(), alias_map_rows(), _bool(), box_context(), box_finals(), build_game(), build_gap_game() (+48 more)

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

### Community 484 - "NBA 2026-27 rebuild write-up"
Cohesion: 0.10
Nodes (19): 1. Pre-registered bars (fixed 2026-10-15, before the first grid), 2. Data used (all in Supabase), 3. The market grid, 4.1 Game markets — closed for 2026-27, 4.2 First half / first quarter / team totals — closed for 2026-27, 4.3 Player props — one rule ships, 4.4 Player props — projection models (the NHL recipe), 4.5 The projection model on the worker's inputs only (+11 more)

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
Cohesion: 0.16
Nodes (18): tracking.paper_tracker (_NFL_MODEL_MARKETS), scripts/nfl_rule_2026_track, tracking/opening_signals.capture_opening_signals, tracking.opening_report, tracking/opening_signals.settle_opening_signals, MAX_FIRE_LEAD = 4, nfl_opener_spread, nfl_wind_totals (+10 more)

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

### Community 420 - "mobile/docs/UX_REVIEW.md"
Cohesion: 0.16
Nodes (13): dashboard.html renderRoster(), A pick is a pick (re-priced line never replaces the locked one), Copy: formatAmerican/formatPct/formatCurrency, model ids never raw, Decided at the best bettable price; read via lib/decisionPrice.ts, frontend-ux-designer agent contract, Mobbin MCP connector (one route: Matt's claude.ai connector), Product rules: a violation is a Blocker, Reuse before invention (EmptyState, StatTile, SignalBadge, ...) (+5 more)

### Community 432 - "Monitoring and model quality notes"
Cohesion: 0.03
Nodes (43): Hybrid Pin-agreement filter on mlb_over_under bets, mlb_runline and mlb_over_under (paused), mlb_total_public_fade card (paper UNDER), Slate concentration guard (insert-time), Live feature sensitivity (12.8pp median swing), mlb_live_total_runs (in-play total), Negative-binomial (NB1) tail, pregame_total_line feature (market anchor) (+35 more)

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

### Community 545 - "NFL and college football search notes"
Cohesion: 0.04
Nodes (29): scripts/ncaaf_search/, Live inning gate replay, ncaaf_live_total 2025 in-play backtest, ncaaf_live_win_prob 2025 in-play backtest, CollegeFootballData (CFBD) as primary source, ncaaf_spread / ncaaf_over_under / ncaaf_moneyline, Cross-book opener signal (DK vs Bovada), prune_odds keeps the earliest snapshot per proposition (+21 more)

### Community 558 - "docs/health_checks.md"
Cohesion: 0.24
Nodes (10): model_artifacts_load counts what it opened, model_artifacts table fallback restore, Three separate artifact questions, three separate failures, KNOWN_UNTRAINED — config models intentionally without artifacts, Pipeline-observability checks: refresh_pass_completion, refresh_pass_steps, signal_delivery, pick_label_integrity, pipeline_runs — the run ledger (tracking/run_ledger.py), Retrain Model workflow (retrain_model.yml), tracking/system_health.py — CRIT and WARN feed checks (Step 12) (+2 more)

### Community 560 - "docs/retrain_2026_plan.md"
Cohesion: 0.18
Nodes (13): scripts/paused_model_assessment, data.ingestors.baseball_savant_ingestor, models.trainer, anytime_td verdict: inert, not losing, F5 O/U and F5 RL paused: leak-mismatched, synthetic-line trained, NCAAF in-play season replay: -3.4% and -13.1%, No model has a cut that clears on the deployed artifact, batter_sb: opp_team_sb_allowed feature (+5 more)

### Community 561 - "Calibration and EV floor docs"
Cohesion: 0.23
Nodes (15): models/honest_ev.gate and honest_probability, tracking/system_health._report_model_calibration, MODEL_OWN_EV_FLOOR and MODELS_ON_OWN_PROBABILITY for wind and opener, fetch_graded reads picks for NFL/NCAAF/UFC/rule models, GLOBAL_MIN_EV: 0.30 then 0.20, The go-live calibration gate never computed a real number, ncaaf_over_under Platt map demoted 2026-09-26, Twelve models 6-16pp overconfident; it tracks sample size (+7 more)

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
Nodes (49): scripts/nfl_prop_market_card, scripts/nfl_prop_replay, scripts/nfl_prop_ladder_grade, scripts/verify_kalshi, data/ingestors/kalshi_prop_ingestor.py (SERIES_MARKET, record_ladders), DraftKings de-vigged price sits above realised over-rate, tackles_assists +21% is a measurement error (control), Walk-forward re-fit 2023-2025 (-4.32% over 1,554 bets) (+41 more)

### Community 688 - "NFL wind totals runbook and staking"
Cohesion: 0.36
Nodes (7): DOCUMENT STATUS block: superseded claims indexed, Under rate by forecast lead 1-7 (~0.41pp per day), Original staking: 25% Kelly capped at 3% (superseded), Kelly-proportional units with slate shading 1/sqrt(1+(k-1)rho), Stops: 2 units per bet, 3 units per slate, review at -15 units, Runbook: Wind Totals, scripts/stake_sizing.py: 1 unit = 1% of bankroll

### Community 710 - "mobile/docs/BILLING.md"
Cohesion: 1.00
Nodes (4): useEntitlement() access gate (subscription OR Discord), useSubscription() subscription-only state, useEntitlement(), not useSubscription(), Access is one gate: useEntitlement(), never useSubscription().entitled

### Community 720 - "docs/testing.md"
Cohesion: 0.67
Nodes (3): PR CI runs a non-integration pytest subset, Pure function tests, in-memory SQLite via conftest, Test suite (testing.md)

### Community 850 - "Game model starter gate notes"
Cohesion: 0.40
Nodes (5): ESPN core probables for the NHL starting goalie, A NONE from this gate is not locked — the reprice path, The gate rule — refuse a game-model BET on a confirmed Out starter/star/goalie, Fires in scorer.score_game and _score_nhl_3way, after best-price requalify, before insert, Game-model starter / star / goalie gate

## Ambiguous Edges - Review These
- `Claim: the app cannot write to the backend` → `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`  [AMBIGUOUS]
  docs/privacy.html · relation: conceptually_related_to

## Knowledge Gaps
- **106 isolated node(s):** `RFC-4122`, `@babel/core`, `babel-plugin-module-resolver`, `babel-preset-expo`, `expo-asset` (+101 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 11052 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **223 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Table` connect `NBA public splits pipeline step` to `mobile/scripts/verify_contrast_tokens.ts`, `Real database trigger tests`?**
  _High betweenness centrality (0.197) - this node is a cross-community bridge._
- **What connects `RFC-4122`, `@babel/core`, `babel-plugin-module-resolver` to the rest of the system?**
  _106 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Injury report ingestion with WNBA fallback` be split into smaller, more focused modules?**
  _Cohesion score 0.0700354609929078 - nodes in this community are weakly interconnected._
- **Why does `over()` connect `mobile/scripts/verify_contrast_tokens.ts` to `Mobile bankroll number formatting`, `NBA public splits pipeline step`?**
  _High betweenness centrality (0.196) - this node is a cross-community bridge._
- **Should `Mobile stats board` be split into smaller, more focused modules?**
  _Cohesion score 0.011221336802732152 - nodes in this community are weakly interconnected._
- **Why does `inserted_minus_start_min()` connect `NBA public splits pipeline step` to `NBA public betting splits ingestor`, `NBA public betting splits ingestor tests`?**
  _High betweenness centrality (0.115) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Claim: the app cannot write to the backend` and `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._