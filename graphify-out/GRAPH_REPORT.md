# Graph Report - bm-nba-s5  (2026-10-20)

## Corpus Check
- Large corpus: 1626 files · ~2,701,674 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 32337 nodes · 77261 edges · 932 communities (722 shown, 210 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 1994 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4face0c2`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Mobile app screens and theme
- Mobile picks home filters and sorting
- Mobile stats board
- NBA player prop model fitting
- NBA book numbers and game four search
- NHL derivative odds history pull
- NBA totals luck model decision tests
- tests/test_nfl_live_leader_gameday.py
- nfl_live_leader/gameday.py
- tests/test_calibration_promotion.py
- tests/test_score_off_any_book_line.py
- Mobile lines board and all books sheet
- tests/test_ncaaf_alias_scores.py
- Alternate prop line fetching tests
- tests/test_backtester.py
- NFL in-play odds client and smoke check
- NBA prop market lab
- Discord pick notifier tests
- nfl/live_model/tests/test_backup_snaps.py
- mobile/scripts: verify_book_links + verify_betslip_combine
- tests/test_paused_keeps_real_verdict.py
- NBA team total under model tests
- X post queue drain tests
- Kalshi prop and game market ingestion
- Pick lock survives settlement tests
- NBA game line move study
- tests/test_mlb_game_market.py
- Discord full record correction posts
- Losing model review milestone tests
- UFC phantom fight filter
- Prop box score backfill
- NBA game model prop feature tests
- Best line price shopping tests
- NBA prop projection card
- tests/test_nfl_opener.py
- NHL stats and game log ingestion
- Mobile crash logging
- scripts/nfl_preflight.py
- Mobile matchup grading and stat pills
- NFL wind forecast and weekly card
- Discord publisher run lock
- tests/test_credit_budget.py
- NBA team total luck card publisher
- Mobile daily results and thresholds
- X profile update queue
- NHL player prop daily card
- tests/test_first_signal_repair.py
- Game injury gate and prop veto
- Daily pipeline runner and steps
- Prop price pregame cutoff tests
- Mobile markets and formatting
- Scheduler stale weekly work catch-up
- Pregame line poller change detection tests
- NHL goalie as-of history
- NFL in-play game state feed
- Mobile color contrast checker
- data/ingestors/nfl_inplay_history.py
- Mobile record hero and equity curve
- Mobile paywall billing and account access
- Mobile bankroll number formatting checks
- Idle database read transaction tests
- NHL market-anchored moneyline model
- Mobile push test diagnostics
- Monitor dashboard probe and cache tests
- tests/test_db_reconnect.py
- Discord recap restatement
- In-play scorer locks and push alerts
- tests/test_refresh_retry.py
- NBA results ingestion and prop settling
- NBA results ingestor tests
- NBA injury report ingest tests
- NBA second game projection engine
- tests/test_local_cache_is_additive.py
- tests/test_calibration_check_coverage.py
- Discord void notice posting tests
- tests/test_book_team_map.py
- tests/test_team_board_cache.py
- NCAAF game feature building tests
- nfl/live_model/tests/test_rush_attempt_pace.py
- NFL wind board fast publishing tests
- NBA fifth search period shares
- MLB weather forecast ingestor
- NHL team rates as of date
- NHL moneyline rebuild and grading
- models: slate_concentration + test_slate_concentration
- CLV backtests and bias scans
- View migration lock handling tests
- Worker job queue retries and locks
- NBA total luck card publishing
- Mobile performance and tracked bets
- NBA game four point estimates
- Best line threshold sweep
- NCAAF college data ingest tests
- Mobile betslip and parlay legs
- NBA pregame scoring window
- NCAAF in-play bet lock and serving
- tests/test_prop_odds_utc_stamp.py
- Live monitor web server streaming
- NCAAF opener strategy walk-forward search
- tests/test_feature_artifact_agreement.py
- NFL prop one side per line
- Closing line value math
- tests/test_cloud_retrain_artifacts.py
- NHL side models never bet against each other
- Discord pick and recap notifier
- System health and deliverability checks
- tests/test_nfl_opener.py
- Player news feed ingestion
- Prop player name matching
- Historical odds and first pitch cutoffs
- Discord and X results posting
- NHL blocked shots prop model
- tests/test_nfl_wind_publisher.py
- Pre-game odds and prop odds ingestors
- NFL live prop model tests
- tests/test_health_reason_and_cadence.py
- NBA odds history backfill
- tests/test_nfl_weather_supabase_readback.py
- Publish signals on write tests
- Pitcher stats as-of invariant tests
- NBA prop market tip timing
- NHL prop per-game limit tests
- Pipeline log reason tests
- NBA in-game study two
- NFL opener and wind writer lock tests
- NFL in-play prop settlement tests
- Voided pick and Discord live field tests
- NBA prop fetch window planning
- nfl/live_model/feeds: test_feed_resilience + espn
- NFL opener pick builder tests
- NHL player prop projection model
- Settlement CLV scan timeout retries
- Health check skip budget tests
- tests/test_live_pick_features.py
- Public fade detection quality tests
- tests/test_prop_missing_features.py
- MLB public fade top picks ranking
- Live game state poller triggers
- NCAAF FBS registry health checks
- NFL in-play decline recorder tests
- NFL line snapshot publishing
- NCAAF live state recording tests
- tests/test_run_ledger_orphans.py
- Mobile over-the-air update flow
- MLB in-play history backtest
- NBA lineup stints from play-by-play
- In-play calibrated decision tests
- NFL pass attempt bias refusal
- Pick label and scorer tests
- Pre-game game scorer and pick insert
- Sharp book odds retention pruning
- NCAAF opponent-adjusted search features
- Any-book first five line scoring
- tests/test_repair_bogus_first_pitch_labels.py
- nfl/live_model/tests/test_executor.py
- tests/test_sbr_loader.py
- Walk-forward evaluation
- mobile/scripts/ux_scan.mts
- Pick settlement and closing line capture
- Mobile player stats and game log
- tests/test_live_quote_staleness.py
- NBA prop closing line purchase tests
- In-play publish parity with pauses
- CLV backfill job tests
- NBA injury report ingestor
- supabase/functions/_shared/discord.ts
- Worker job queue validation tests
- NFL prop odds timeout-safe slicing
- NFL prop count and yardage distributions
- scripts: build_nfl_live_leader_artifact + model
- NFL DraftKings line snapshots
- Threshold review schema lockdown tests
- Schema guard and table lockdown
- tests/test_discord_channel_probe.py
- tests/test_nfl_prop_one_read_per_game.py
- Bounded odds prune retry tests
- Team stats as-of rebuild and invariants
- Injury report ingestion
- NCAAF gameday live odds cadence
- Multi-book odds ingestion
- scripts/nfl_edge_gameline_rules.py
- System health check pass tests
- tests/test_model_game_savepoint.py
- Health check pick delivery tests
- NBA historical odds archive parser
- Football alternate line rejection retries
- tests/test_calibration_watch.py
- Paused and no-signal row tests
- Push line move alert tests
- NFL weather history fetcher
- Model performance monitor tests
- Pipeline failure alerting and heartbeats
- NCAAF starter-out research dataset
- Weather step look-ahead window tests
- Mobile bankroll storage
- Score when lines open tests
- Publish keys and push alerts
- tests/test_sbr_loader.py
- NHL totals card publisher
- DraftKings direct feed event matching
- Member sportsbooks scratch database tests
- tests/test_nhl_three_way_lookahead.py
- Mobile team stats screen
- Pregame price age bound tests
- Prop odds next-day lookahead tests
- External threshold map promotion
- System health run ledger tests
- NCAAF in-play history backtest tests
- tests/test_best_line_live.py
- tests/test_sbr_loader.py
- In-play score freshness guard tests
- NCAAF college data refresh and backfill tests
- NBA residual distribution pricing
- UFC fight stats ingest tests
- Mobile load errors and abort handling
- NBA team total odds fetch tests
- NFL prop settlement tests
- tests/test_void_picks.py
- tests/test_sbr_loader.py
- Closing line value price tests
- Job heartbeat and stale jobs
- NBA turnovers prop settlement tests
- NCAAF game-day live feeds
- NFL player props and stats ingestion
- MLB renamed franchise game merge tests
- NFL in-play pick row building tests
- NBA box score repair tests
- Health check daily feed freshness
- tests/test_sbr_loader.py
- tests/test_daily_retry.py
- Results recap message id tests
- NFL prop market card publisher tests
- Odds repeat thinning keeps NBA rows
- tests/test_live_book_move_guard.py
- NHL prop settlement tests
- X manual post image fetch
- tests/test_sbr_loader.py
- MLB umpire ingestor
- Social post queue and drain
- NFL pick monitor
- Per-model expected value floor
- NFL in-play pick writer commit tests
- Odds API fetching and opener scripts
- X posting and pick refusal tests
- Recap waits for NFL box scores
- System health check test fixtures
- Mobile custom model builder and filters
- In-play pregame totals line read
- X social posting and profile
- supabase/functions/revenuecat-webhook/index.ts
- supabase/functions/whop-webhook/index.ts
- NFL pick evaluation and monitor
- tests/test_nfl_props.py
- NFL wind and opener publisher
- tests/test_sbr_loader.py
- Price freshness test database fake
- NFL live prop sharp book pull
- UFC card scorer fake database
- NFL in-play prop dataset and calibration
- Price prefilter timeout rollback tests
- Pregame price age bounds
- Prop grading timeout and rollback tests
- NHL returning starter naming
- Pregame line sweeps and features
- Daily picks email renderer
- tests/test_nfl_props.py
- NFL wind bettable book filter
- Mobile bankroll unit percent settings
- Poller leaves prop rows alone
- Lazy local store connection
- NFL live pick announce isolation tests
- tests/test_game_market_gate.py
- NBA team total closing line tests
- NHL prop EV regimes and Kalshi ladders
- NBA public splits quality backfill
- Pipeline watch findings and alerts
- NFL prop market card tests
- NBA second-model prop study
- tests/test_score_when_lines_open.py
- tests/test_score_when_lines_open.py
- tests/test_score_when_lines_open.py
- Probability calibration map tests
- Bounded odds pruning and thinning
- tests/test_pick_integrity.py
- NHL props card quote selection
- Umpire features excluded from training
- Shared database access for scoring and features
- tests/test_record_one_pick_per_event.py
- NFL test clock past schedule
- NHL dead API wrapper cleanup tests
- Weekly job catch-up tests
- MLB in-play trigger orchestrator and replay
- Pipeline report rollback tests
- NFL evaluation rows carry quoted line
- nfl/live_model/tests: test_props + props
- One NHL prop bet per game
- Prop board fake connection for tipoff
- Player prop market pricing core
- Retrain dropped feature imputation check
- Deploy checks and job queue
- tests/test_wnba_prop_market.py
- tests/test_nfl_scored_rows.py
- NHL derivative totals walk-forward model
- Prop no-bet rows survive tipoff
- Per-model EV floor card tests
- NHL prop card pick writing tests
- NBA prop card runner tests
- Prop odds book update time
- tests/test_recap_retries_a_skipped_day.py
- Database connection and shared utilities
- MLB bet record audit tally
- MLB totals public fade scorer tests
- NHL blocked shots player matching
- Four NHL prop bets per night
- Dropped game scorer board stub
- Pregame prices current health test stub
- NBA prop market decision tests
- NBA second game luck run tests
- NHL opening night goalie lookup
- Pregame poller game creation
- NFL in-play decision audit fan-out
- NFL early-signal publishing tests
- NBA team total odds billed feed stub
- Savant freshness health check tests
- NBA public betting splits ingestion
- Game feature and injury adjustments
- NHL blocked shots non-dressed voiding
- Weekly catch-up cursor stub
- tests/test_ncaaf_prop_odds.py
- MLB prop feature engine
- Stale quote price age test
- NCAAF in-play score distribution pricing
- UFC stats ingestor fake connection
- tests/test_ncaaf_pbp_store.py
- tests/test_heartbeat_watchdog.py
- Record correction social posts
- NFL edge research shared helpers
- NBA second game market fair prices
- scripts/nfl_edge_live_rush_pace.py
- NBA prop projection tests
- NFL preregistered 2026 edge study
- tests/test_prop_calibrated_decision.py
- NBA fourth search derivative markets
- tests/test_mobile_line_movement.py
- In-play calibration report tests
- NBA in-game luck study one
- NBA lineup stint derivation tests
- NBA play-by-play parsing tests
- tests/test_ncaaf_live_notify.py
- NCAAF quarterback team features
- NHL prop backtest and EV lab
- Live monitor dashboard data store
- NBA fifth search grid tests
- tests/test_settled_record_is_immutable.py
- features/golf_feature_engine.py
- ncaaf_live/tests/test_states.py
- tests/test_bovada_feed.py
- Prop ladder from books and Kalshi
- NCAAF cross-book opener tests
- NFL 2024 in-play totals grading
- NFL 2025 in-play edge research
- tests/test_health_pregame_prices_current.py
- NBA stats and player log ingestion
- scripts/nfl_edge_extreme_props.py
- scripts/nfl_edge_settlement.py
- X results and free pick posts
- WNBA points prop rebuild and sweep
- tests/test_agents_contract.py
- Live model holdout comparison
- WNBA results ingestor
- NBA public betting splits ingestor
- NBA box score enrichment
- NFL quarterback and wind edge study
- NBA derivative market lab
- Mobile source logic tests via node
- NBA halftime in-game research
- NBA game model luck feature tests
- MLB stats and pitcher ingestion
- tests/test_decide_on_calibrated.py
- tests/test_dk_direct_feed.py
- NBA prop projection lab
- Mobile live picks segment tests
- NBA in-game data staleness gate
- tests/test_model_artifacts_load.py
- Mobile team and player detail tests
- scripts/game_line_market_sweep.py
- Push notification deep link tests
- tests/test_pass_instrumentation.py
- Odds prune opener and close tests
- tests/test_db_adapt_sql.py
- Eggz channel pick parsing and grading
- tests/test_mobile_contrast_tokens.py
- Monitoring probes and HTTP timeouts
- NBA game four part one tests
- NBA second game line move tests
- NBA team total luck replay build
- NFL in-play prop flow anchoring tests
- WNBA prop context features
- NBA second game verdict
- Probability calibration fitting and sweep
- NCAAF in-play pricing engine
- tests/test_nfl_live_leader_state.py
- tests/test_ncaaf_qb_ingestor.py
- DraftKings direct feed freshness probes
- Ops alert posting and watchdogs
- House juice price floor tests
- tests/test_ncaaf_game_identity.py
- NBA second game market tests
- NFL edge luck gap study
- tests/test_dk_freshness_parse.py
- NBA game model research harness
- Discord bet price bound wording
- Kalshi prop ladder recording tests
- UFC results download caching
- College football live ESPN feed
- UFC fight feature builder
- NFL prop walk-forward and regrading
- NBA quarter game model tests
- NBA second game luck study
- NHL skater prop pricing lab
- Line CLV sign and orientation tests
- NBA game harness tests
- UFC fight results scraper
- NFL in-play flow slice backtest
- NBA game projection tests
- Model calibration check tests
- NCAAF college data ingestor
- NFL prop market card lead ceiling
- NCAAF player stats parser tests
- scripts/nfl_live_prop_feasibility.py
- tests/test_context_budget.py
- tests/test_player_h2h_stat_values_migration.py
- tests/test_retired_models.py
- NFL in-play flow pseudo CLV tests
- NFL in-play remaining-yards engine training
- Threshold cut sweeps and EV replays
- Scratch Postgres line state tests
- tests/test_live_record_start_views.py
- UFC historical CSV loader
- Odds pruning keeps closing lines
- NHL prop odds fetch gate
- NFL Kalshi edge search
- nfl/models/opener_spread.py
- MLB live slate midnight discovery tests
- tests/test_nfl_wind_fire_window.py
- tests/test_public_betting_ingestor.py
- Basketball player positions ingestor
- tests/test_service_role_split.py
- Prop ladder and NBA derivative tests
- Mobile tracked performance record checks
- NFL research edge data cache
- Mobile sport filter persistence tests
- UFC twin fight id scoring tests
- NBA game projection model tests
- NFL in-play flow snapshot validation
- Bring your own model game facts
- NCAAF in-play market pricing
- NBA period map pricing tests
- Prop box score cooled refill
- NCAAF CFBD ingestor tests
- Mobile screen source wiring tests
- Kalshi game market recorder
- CLV price taken app parity tests
- UFC results scraper tests
- NCAAF totals probability regression tests
- Mobile live game status checks
- Refresh pass step ordering tests
- NHL totals market bet finder
- Health check signal deliverability
- Mobile bankroll screen checks
- tests/test_mobile_threshold_parity.py
- NHL derivative odds job validation tests
- tests/test_track_record_views.py
- tests/test_weekly_catch_up.py
- Node runner for mobile tests
- NCAAF steam lag study
- Mobile bankroll settings card
- NFL live leader model tests
- Mobile paused catalog tests
- Free pick cheaper book naming
- NCAAF board visibility tests
- MLB play-by-play ingestor
- tests/test_promote_calibration_job.py
- tests/test_cfbd_snapshot_leakage.py
- NFL wind forecast stability tests
- In-play calibration analysis job
- NCAAF totals weather and input drift
- NCAAF outcome edge scan
- NFL prop threshold window tests
- tests/test_nhl_research_job.py
- tests/test_settlement_timing.py
- NBA schedule rest and travel features
- Push delivery ticket handling tests
- DataGolf ingestor and NHL SBR archive
- Mobile pick category tests
- College football board visibility tests
- NFL odds cache import to Supabase
- tests/test_health_check_observe.py
- NFL in-play prop flow model
- NFL 2026 opener and wind tracker
- NFL in-play prop line churn check
- Picks unique index for unnamed props
- tests/test_pick_lock_is_on_picks.py
- NFL in-play pick writer
- Pregame price age limit
- Per-model threshold config tests
- NBA game two verdict grid tests
- Worker retrain and sweep jobs
- NFL prop market remeasure pins
- MLB retrain freeze guard
- supabase/functions/discord-link/index.ts
- tests/test_nfl_prop_clv.py
- tests/test_scoring_methods.py
- NFL weather edge fetch
- Worker job queue runner
- Calibration cut sweep and grading
- Anonymous read grant planning
- nfl/scripts/backtest_opener.py
- Paused model assessment checks
- NCAAF totals lead and consensus gate
- tests/test_latest_odds_views.py
- NBA schedule ingestor
- NFL prop feature engine
- tests/test_transaction_pooler.py
- Env file database URL fallback
- NCAAF in-play history backtest
- Trainer no-register mode tests
- Database URL doctor
- supabase/functions/sharpsports/index.ts
- NFL prop settlement name fallback
- Rule model market reading tests
- tests/test_worker_deps.py
- scheduler.py
- Position defense ranks SQL checks
- Model scoring method registry
- tests/test_mobile_stat_labels_match_the_server.py
- tests/test_ncaaf_fcs_visitor_names_migration.py
- tests/test_nfl_prop_unstarted_clear.py
- Multi-sport model research labs
- tests/test_scorer_nfl_prop_like_escape.py
- Duplicate pick copy selection
- NHL stats views tests
- NHL game results parser
- Sweep price floor filter tests
- Market movement feature builder
- NCAAF margin model fit and registration
- NFL live pick price ceiling tests
- tests/test_clear_unauthorized_auto_pauses_migration.py
- tests/test_ncaaf_se_louisiana_alias_migration.py
- NFL live leader cut and price floor
- tests/test_overnight_polling.py
- NFL stale daily card clearing
- NFL opener stake sizing and EV
- Mobile type-check baseline tests
- Model trainer and calibration metrics
- NFL prop over lean concentration study
- Mobile line ruler tests
- X team hashtags
- CLV no-vig close capture tests
- tests/test_claude_rules_split.py
- tests/test_db_setup.py
- tests/test_dedupe_opening_signals.py
- tests/test_pbp_backfill_resilience.py
- In-play bet uniqueness index tests
- NFL wind forecast validation
- Paused model profitability assessment
- NCAAF quarterback ablation study
- NBA results window games
- NFL weekly wind card
- NBA in-game study one tests
- Count each event once in records
- NBA public splits pipeline step
- tests/test_prompt_reads_thresholds.py
- tests/test_system_health_meta_steps.py
- NCAAF situational spot evaluation
- NBA period score ingestion
- scripts/render_brand_icons.py
- NBA research data cache
- Results recap NFL box score ordering
- NBA prop model verification stages
- supabase/functions/stripe-webhook/index.ts
- tests/test_drop_voided_nfl_wind_opening_signals_migration.py
- tests/test_mobile_neutral_signal_label.py
- College football data checks
- tests/test_scorer_commits_per_game.py
- NCAAF in-play model resweep
- NBA ESPN box score parsing
- Declared worker job validation tests
- tests: test_wnba_availability + wnba_availability
- Mobile stat segment tabs tests
- MLB public fade pregame splits
- Mobile NHL today look-ahead tests
- supabase/functions/sharpsports-webhook: index + index
- Mobile Lines board pin tests
- supabase/functions/stripe-checkout/index.ts
- tests/test_book_list_budget.py
- Mobile type-check baseline checker
- NBA game market search lab
- NHL totals research lab
- UFC fight page parsing
- NBA game model synthetic world seeding
- NCAAF weather totals study
- mobile/scripts/verify_a11y.ts
- Football in-play game state
- tests/test_demote_ncaaf_over_under_platt.py
- tests/test_discord_post_one_pick_migration.py
- tests/test_game_scorer_spares_nfl_props.py
- NFL in-play score distribution pricing
- Mobile quiet update download tests
- NBA team total luck replay tests
- Live odds vendor feed probe
- NFL Kalshi price history fetch
- MLB totals public fade card
- NBA prop model research lab
- Mobile stats filter UX verify
- NFL prop pulled quote filter
- NHL training odds read by game
- SQL percent escaping guard
- NFL wind stake past calibration tests
- NFL kickoff-hour live wind readings
- NCAAF scoreboard yardline parsing
- NCAAF prop market rule sweep
- NFL prop market stacking studies
- NFL prop opening signal cleanup tests
- Scorer keeps off-DraftKings priced bets tests
- Historical odds file loader
- Results recap error watch
- UFC event list date parsing
- NHL derivative totals dormant card
- UFC fighter page parsing
- NBA projection price cache guard tests
- Every named sportsbook is fetched
- NHL goalie name lookup
- Model pause check in scorer
- Threshold review test isolation fixtures
- NCAAF consensus gate frame builder
- NFL prop blind under bias
- NFL scored rows fake database
- Game log backfill per-game skip
- NFL weather storage fallback tests
- NBA second game luck rating tests
- Pause table read fails open
- Mobile accessibility verify script
- Market handicap feature tests
- mobile/scripts/verify_a11y.ts
- mobile/scripts/verify_a11y.ts
- Prop CLV and SQL escaping tests
- mobile/scripts/verify_a11y.ts
- NCAAF margin and totals evaluation
- ncaaf_live/tests/test_serve.py
- Discord tipster picks grading and recaps
- Mobile error states and books tests
- Prune query literal rendering helper
- Results snapshot pass order tests
- DraftKings feed per-row rollback
- No record-only mode guard tests
- Shared fake row query helpers
- MLB public fade top-k backtest
- NFL QB wind and NBA in-game tests
- UFC rounds completed settlement
- DraftKings direct feed default off
- Empty feed run not success
- NFL weather readback fixture
- Threshold review never unpauses
- Manual X posts runbook
- NFL live pick game date resolution
- Threshold review cannot pause
- NHL box score parsing
- tests/test_team_board_commence_bound.py
- Threshold review announce test
- NBA play-by-play clock parsing
- Scorer pause check helper guard
- Review tables worker-only access
- Threshold review milestone check
- Failed prune reported as failed step
- Threshold review kill switch
- NFL in-play prop publish refusal
- mobile/scripts/verify_a11y.ts
- Prop board market coverage invariants
- NFL in-play multi-player bet locks
- Opening versus closing strategy analysis
- NBA public fade poll timing
- NBA fifth search team rating projections
- NCAAF state build file naming
- NCAAF team game stats parsing
- Weekly catch-up probe rollback test
- NHL goalie save rate regression
- NFL in-play backtest replay harness
- NFL in-play pick announcements
- College football school name matching
- Worker service role split test
- NBA second game placebo run tests
- MLB totals public fade tests
- Dashboard rule models third state
- NFL prop book bettability sweep
- Discord stale pause flag error
- Discord real pause not stale test
- NBA second game stale cache refusal
- Discord live signal embeds and prices
- NBA play-by-play ingestor
- Supabase schema tables
- mobile/app.json
- mobile/package.json
- Core odds schema and latest views
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
- NHL moneyline rebuild write-up
- NCAAF player stats leaderboard
- NCAAF tables migration
- nfl/scripts/live_prop_job.sh
- NFL player stats leaderboard
- .claude/settings.json
- NBA player game log RPCs
- scripts/refresh_pass.sh
- Player news migration
- Custom model facts tables migration
- Kalshi game markets migration
- Kalshi prop ladders migration
- NCAAF QB game migration
- Live game state schema
- Mobile app build scripts
- Custom model backtest RPCs
- NFL live model tables
- data/migrations/add_nhl_stats_views_2026_10_16.sql
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
- App error log migration
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
- Member sportsbooks migration
- Mobile developer tooling dependencies
- NFL kickoff wind reads migration
- Unmatched player positions table
- Social post queue migration
- Opening signals shadow table
- In-app feedback thread tables
- Capper picks tables migration
- NBA 2026-27 rebuild write-up
- One live bet row per pick index
- Social profile update migration
- docs/rules_evidence.md
- NFL game lines model write-up
- nfl/live_model/README.md
- docs: followups + clv
- Model search findings and assessments
- docs: best_line + config_topology
- docs/history: learnings + build_state
- NFL in-play rushing and passing studies
- NCAAF in-play model notes
- monitoring/static/dashboard.html
- Prop market and odds provider research
- docs/sports/nhl.md
- NFL game lines model documentation
- docs: mlb_market_handicap_features + mlb_game_market_gate
- docs/sports/ncaaf.md
- Cloud worker and local ops docs
- docs/discord.md
- docs/team_stats_leak.md
- docs/sports/nfl.md
- mobile: TESTFLIGHT + README
- supabase/functions/README.md
- .claude/rules/analysis-and-thresholds.md
- .claude/rules/data-integrity.md
- docs/sports/mlb.md
- docs/thresholds.md
- .claude/rules: CLAUDE + config-topology
- .github/workflows: CLAUDE + mobile-build
- docs/agents_contract.md
- .claude/rules/operations.md
- docs/live_odds_freshness.md
- mobile/docs/UX_REVIEW.md
- Daily model quality and MLB totals docs
- docs/sports: ufc + golf
- mobile/docs/BILLING.md
- NFL model bundle restore guide
- .claude/agents: frontend-ux-designer + CLAUDE
- .claude/rules/picks-and-publishing.md
- .claude/rules/model-updates.md
- docs/signal_timing.md
- mobile/docs/DISCORD_LINKING.md
- Probability calibration design notes
- docs/live_betting.md
- docs/sports/wnba.md
- mobile/docs/AUTHENTICATION.md
- .claude/rules/frontend.md
- Model artifact and health docs
- docs/retrain_2026_plan.md
- Performance gauging and record views docs
- Calibration and NFL wind opener tracking docs
- docs/reviews/2026-09-07-nfl-props-deep-dive.md
- NFL wind totals runbook and staking
- docs/market_coverage.md
- (root): pr-ci + requirements
- NFL props sources and prediction market research
- NFL sharp versus soft opener findings
- mobile/docs/BILLING.md
- docs/testing.md
- CLAUDE.md
- docs: nhl_market_lab + nhl_clv_ev_assessment
- docs/game_injury_gate.md

## God Nodes (most connected - your core abstractions)
1. `get_connection()` - 643 edges
2. `DBConnection` - 319 edges
3. `StatsScreen()` - 162 edges
4. `react` - 149 edges
5. `react-native` - 107 edges
6. `colors` - 92 edges
7. `PickCard()` - 84 edges
8. `font` - 84 edges
9. `spacing` - 81 edges
10. `radii` - 80 edges

## Surprising Connections (you probably didn't know these)
- `Forward capture (2026-27)` --references--> `run_forward()`  [INFERRED]
  docs/nba_public_splits.md → data/ingestors/nba_public_splits_ingestor.py
- `8.1 P1, the market-anchored model: choices fixed before any P1 cell was graded (2026-10-18)` --references--> `choose_C()`  [INFERRED]
  docs/nba_models_2026.md → models/nhl_moneyline_anchored.py
- `2. Data used (all in Supabase)` --references--> `odds()`  [INFERRED]
  docs/nba_models_2026.md → tests/test_latest_line_state.py
- `3. The market grid` --references--> `odds()`  [INFERRED]
  docs/nba_models_2026.md → tests/test_latest_line_state.py
- `Things a reader should know` --references--> `shot_value()`  [INFERRED]
  docs/nba_pbp_stints.md → data/ingestors/nba_stints.py

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

## Communities (932 total, 210 thin omitted)

### Community 5 - "Mobile app screens and theme"
Cohesion: 0.01
Nodes (314): AppErrorBoundary, IoniconName, Props, Props, State, Nav, Props, Props (+306 more)

### Community 0 - "Mobile picks home filters and sorting"
Cohesion: 0.02
Nodes (160): P, ActivePill, Props, Props, reachFrame, DateOption, DayRow, SelectableGame (+152 more)

### Community 1 - "Mobile stats board"
Cohesion: 0.01
Nodes (428): P, TouchSet, PlayerPropQuote, AnytimeMatchupView, AnytimeSortRow, DefenseRank, gapReason, MatchupPlacement (+420 more)

### Community 10 - "NBA player prop model fitting"
Cohesion: 0.03
Nodes (75): Spec, collapse_official(), compact_report(), predict_means(), alias_key(), apply_calibration(), _attach_report_ids(), box_panel() (+67 more)

### Community 105 - "NBA book numbers and game four search"
Cohesion: 0.05
Nodes (48): Point, even_gap(), ladder_mask(), main_rungs(), _one_rung(), split_main_rungs(), visible_numbers(), cache_for() (+40 more)

### Community 108 - "NHL derivative odds history pull"
Cohesion: 0.07
Nodes (21): Meter, _Meter, _Resp, _blank_row(), _done_ids(), _ensure_ledger(), estimate_credits(), format_plan() (+13 more)

### Community 11 - "NBA totals luck model decision tests"
Cohesion: 0.03
Nodes (75): Decision, TotalLuckBet, _Conn, _Cur, box_mismatches(), decide(), _known_team(), lead_minutes() (+67 more)

### Community 113 - "tests/test_nfl_live_leader_gameday.py"
Cohesion: 0.06
Nodes (31): FakeClock, FakeConn, FakeFeed, _Rows, art(), live_state(), quote_payload(), _run_loop() (+23 more)

### Community 114 - "nfl_live_leader/gameday.py"
Cohesion: 0.05
Nodes (31): Cadence, GameContext, LiveOddsFeed, Quote, LiveState, release_read(), parse_book_ts(), quote_predates_score() (+23 more)

### Community 115 - "tests/test_calibration_promotion.py"
Cohesion: 0.07
Nodes (26): FakeConn, eligibility_clause(), load_calibrations(), maps_materially_differ(), promote(), _payload(), _row(), test_a_broken_table_is_identity_maps_not_an_exception() (+18 more)

### Community 116 - "tests/test_score_off_any_book_line.py"
Cohesion: 0.08
Nodes (33): _FakeConn, _fallback_line_quote(), _cut(), _on(), _pick(), _row(), _sql_const(), _src() (+25 more)

### Community 12 - "Mobile lines board and all books sheet"
Cohesion: 0.03
Nodes (115): LinesMarket, LinesMarkPick, linesMarks, LinesMlMode, LinesOddsRow, LinesPickRef, LinesSheetRow, LinesSheetSide (+107 more)

### Community 120 - "tests/test_ncaaf_alias_scores.py"
Cohesion: 0.08
Nodes (33): _FakeConn, _FakeCursor, alias_score_updates(), _date_or_none(), mirror_scores_to_alias_rows(), mirror_stored_finals(), _slug_pair(), _cfbd() (+25 more)

### Community 121 - "Alternate prop line fetching tests"
Cohesion: 0.10
Nodes (18): _Conn, alt_markets_due(), _ou(), _parse(), test_a_failed_check_does_not_spend(), test_a_player_the_book_lists_at_1_5_keeps_the_0_5_alternate(), test_a_sport_with_no_alternates_never_asks(), test_a_standard_market_still_yields_one_row_per_player() (+10 more)

### Community 123 - "tests/test_backtester.py"
Cohesion: 0.05
Nodes (17): TestCalibrationError, TestComputeBacktestSummary, TestEvaluateResult, TestGoLiveGateConstants, TestIterSides, TestConfidenceTier, _backtest_golf(), _backtest_ufc_fight() (+9 more)

### Community 125 - "NFL in-play odds client and smoke check"
Cohesion: 0.07
Nodes (17): CreditMeter, LiveOddsClient, Quote, JsonlRecorder, best_price(), parse_events(), _parse_ts(), _side_of() (+9 more)

### Community 129 - "NBA prop market lab"
Cohesion: 0.09
Nodes (44): NBTable, add_units(), assemble(), best_per_key(), boot_ci(), build_quotes(), candidates_from(), choose_floor() (+36 more)

### Community 13 - "Discord pick notifier tests"
Cohesion: 0.02
Nodes (124): _FakeConn, _FakeResult, _Resp, _StampConn, test_producer_output_builds_a_live_embed(), _cand(), _et_now_iso(), _freeze_now() (+116 more)

### Community 131 - "nfl/live_model/tests/test_backup_snaps.py"
Cohesion: 0.09
Nodes (22): _FakeConn, _FakeCur, back_up(), digest(), _flush(), iter_files(), main(), _mb() (+14 more)

### Community 135 - "mobile/scripts: verify_book_links + verify_betslip_combine"
Cohesion: 0.06
Nodes (37): betslipCombineKind, combineBetMgm(), combineBetslipLinks(), combineCaesars(), combineDraftKings(), combineEspnBet(), combineFanDuel(), fanDuelPairs() (+29 more)

### Community 138 - "tests/test_paused_keeps_real_verdict.py"
Cohesion: 0.05
Nodes (37): _Capture, _prop_bets_today(), _bet(), _bodies(), _code(), _fn(), _pause(), _prop() (+29 more)

### Community 14 - "NBA team total under model tests"
Cohesion: 0.04
Nodes (44): TeamTotalDecision, book_ages(), decide(), record(), home_part(), newest_season(), pricing_dist(), quote_frame() (+36 more)

### Community 140 - "X post queue drain tests"
Cohesion: 0.09
Nodes (46): _Fetcher, Poster, QueueConn, _Rows, _Uploader, _blank(), _creds(), _drain() (+38 more)

### Community 141 - "Kalshi prop and game market ingestion"
Cohesion: 0.05
Nodes (24): Ladder, event_code(), event_date(), kalshi_school(), _num(), probe(), record_game_markets(), resolve_events() (+16 more)

### Community 143 - "Pick lock survives settlement tests"
Cohesion: 0.08
Nodes (22): _SqliteShim, conn(), _game(), _pick(), _survivors(), test_a_bet_is_never_dropped_for_an_earlier_no_signal(), test_a_dead_zone_prop_row_locks_too(), test_a_final_game_is_not_a_scoring_target() (+14 more)

### Community 144 - "NBA game line move study"
Cohesion: 0.07
Nodes (33): Data, attach(), big_home_dog_signal(), consensus(), control_specs(), coverage_text(), fade_side(), favourite_sides() (+25 more)

### Community 146 - "tests/test_mlb_game_market.py"
Cohesion: 0.08
Nodes (23): GameMarketBet, _SlateConn, find_spread_bets(), _is_runline(), pick_rows(), test_mlb_market_cards_drop_a_bet_under_the_floor(), _game_rows(), _q() (+15 more)

### Community 149 - "Discord full record correction posts"
Cohesion: 0.07
Nodes (25): LedgerUnread, Conn, delete_custom_record_post(), _jump(), _place(), _publish(), publish_full_record(), publish_full_record_standard() (+17 more)

### Community 150 - "Losing model review milestone tests"
Cohesion: 0.12
Nodes (17): _Conn, _slate(), test_a_losing_model_with_enough_bets_is_flagged(), test_a_losing_model_with_too_few_bets_is_left_alone(), test_a_milestone_fires_only_once(), test_a_model_paused_in_config_is_not_reported_again(), test_a_profitable_model_is_never_touched(), test_an_already_paused_model_is_not_flagged_again() (+9 more)

### Community 154 - "UFC phantom fight filter"
Cohesion: 0.21
Nodes (6): TestFilterUfcPhantom, TestIsKnownUfcMatchup, _filter_ufc_phantom(), _is_known_ufc_matchup(), _game(), _odds()

### Community 155 - "Prop box score backfill"
Cohesion: 0.12
Nodes (14): ScriptConn, ensure_prop_box_scores(), missing_prop_games(), _pick(), test_a_logged_game_is_not_fetched_and_a_goalie_gap_is(), test_a_probe_error_that_is_not_a_timeout_raises_after_rollback(), test_a_probe_timeout_rolls_back_and_returns_empty(), test_a_recent_nfl_attempt_is_not_repeated() (+6 more)

### Community 156 - "NBA game model prop feature tests"
Cohesion: 0.06
Nodes (40): _Stop, _box(), _g(), _games(), _inj(), _model(), _props(), _run() (+32 more)

### Community 158 - "Best line price shopping tests"
Cohesion: 0.03
Nodes (55): FakeConn, TwoOrientationConn, FakeConn, _best_game_price(), _best_game_price_one(), _best_of(), _best_prop_price(), _current_price_since() (+47 more)

### Community 160 - "NBA prop projection card"
Cohesion: 0.08
Nodes (31): ProjectionBet, step_nba_prop_project(), backfill_official(), decided_games(), ensure_tables(), espn_pulls(), espn_rows(), fill_espn_history() (+23 more)

### Community 164 - "tests/test_nfl_opener.py"
Cohesion: 0.15
Nodes (7): TestFreshNumberLabel, TestHeldMinutes, _giants_board(), _giants_prior_at_2129(), _giants_sched(), _obs(), _ts()

### Community 165 - "NHL stats and game log ingestion"
Cohesion: 0.02
Nodes (68): TestLogRowBuilders, TestNoHollowTeamRowBeforeTheFirstGame, TestOddsFeedTeamNames, TestSeasonLabel, TestThreeWayMarketKey, _default_fetch(), fetch_espn_nhl_probables(), _https() (+60 more)

### Community 166 - "Mobile crash logging"
Cohesion: 0.11
Nodes (33): CrashContext, CrashLogDeps, CrashReport, ErrorUtilsShape, KeyValueStore, LaunchMarker, LaunchStage, ReportKind (+25 more)

### Community 167 - "scripts/nfl_preflight.py"
Cohesion: 0.10
Nodes (21): TestRealSchema, TestSplitter, TestSqliteSchema, _load_postgres_schema(), _split_sql_statements(), check(), check_cards_run(), check_config_gates() (+13 more)

### Community 17 - "Mobile matchup grading and stat pills"
Cohesion: 0.04
Nodes (68): MatchupGrade, MatchupInfo, TonightMatchupRow, check(), fakeServer(), main(), read(), check() (+60 more)

### Community 171 - "NFL wind forecast and weekly card"
Cohesion: 0.12
Nodes (16): OpenMeteoError, fetch_era5(), fetch_issued_forecasts(), fetch_live_forecast(), _frame(), _get(), _issued_columns(), _issued_from_supabase() (+8 more)

### Community 174 - "Discord publisher run lock"
Cohesion: 0.07
Nodes (17): _Conn, _Result, _clear_locks(), _no_prod_threshold_sync(), _signal_row(), test_a_connection_that_cannot_lock_still_publishes(), test_an_exception_mid_publish_does_not_wedge_every_later_pass(), test_every_signal_publisher_takes_the_lock() (+9 more)

### Community 177 - "tests/test_credit_budget.py"
Cohesion: 0.05
Nodes (29): CreditBudget, _Conn, budget_for(), calls_in(), parse_shard(), shard_windows(), daily_burn(), latest_remaining() (+21 more)

### Community 178 - "NBA team total luck card publisher"
Cohesion: 0.07
Nodes (23): TeamTotalBet, step_mlb_total_public_fade(), step_nba_team_total_luck(), step_nba_total_luck(), artifact(), decided_games(), ensure_decisions_table(), games_with_a_bet() (+15 more)

### Community 18 - "Mobile daily results and thresholds"
Cohesion: 0.02
Nodes (149): Case, Bucket, FixturePick, Acc, DailyResults, DayGameSummary, DayStakeStats, ModelDayStats (+141 more)

### Community 186 - "X profile update queue"
Cohesion: 0.10
Nodes (20): ProfileConn, _Rows, Updater, ProfileUpdate, _code(), _creds(), _drain(), _row() (+12 more)

### Community 19 - "NHL player prop daily card"
Cohesion: 0.06
Nodes (23): TestTheCard, step_nhl_prop_scoring(), bs_implied(), candidates(), identities(), latest_quotes(), main(), pick_rows() (+15 more)

### Community 193 - "tests/test_first_signal_repair.py"
Cohesion: 0.07
Nodes (28): _Conn, _VoidedConn, step_restore_first_signals(), patch_conn(), _make(), _sql_of(), test_a_lane_already_holding_its_first_bet_is_untouched(), test_a_lane_with_no_sibling_still_restores() (+20 more)

### Community 194 - "Game injury gate and prop veto"
Cohesion: 0.05
Nodes (49): _InjConn, _InjConn, apply_to_picks(), _goalie_names(), load_sport_injury_index(), _pitcher_names(), player_matches_veto(), _star_names() (+41 more)

### Community 197 - "Daily pipeline runner and steps"
Cohesion: 0.01
Nodes (127): ViewMigrationResult, _run_migrations(), setup_database(), backfill_savant_stats(), _df_to_rows(), _fetch_savant_csv(), _get_col(), _normalize_name() (+119 more)

### Community 199 - "Prop price pregame cutoff tests"
Cohesion: 0.08
Nodes (14): _StubConn, _latest_dk_prop_row(), _assigned_from(), _prop_scorers(), test_every_scorer_call_site_passes_a_pregame_cutoff(), test_get_prop_dk_odds_forwards_the_cutoff(), test_in_play_snapshots_are_excluded_unconditionally(), test_it_fails_open_when_commence_time_is_missing() (+6 more)

### Community 2 - "Mobile markets and formatting"
Cohesion: 0.01
Nodes (365): Row, Props, IoniconName, Props, clvBetQuote, ClvBetRow, ClvBookRow, DecisionPriced (+357 more)

### Community 200 - "Pregame line poller change detection tests"
Cohesion: 0.04
Nodes (46): _PollConn, changed_rows(), _fingerprint(), _key(), last_known_prices(), _num(), over_credit_cap(), poll_once() (+38 more)

### Community 203 - "NHL goalie as-of history"
Cohesion: 0.20
Nodes (3): GoalieBook, TestGoalieAsOf, _g()

### Community 205 - "NFL in-play game state feed"
Cohesion: 0.10
Nodes (20): CoreClient, EventMeta, FakeClient, _abbr(), game_seconds(), https(), _int(), is_admin_play() (+12 more)

### Community 206 - "Mobile color contrast checker"
Cohesion: 0.05
Nodes (39): Pair, code(), lum(), noGreen(), over(), ratio(), read(), readUtf8() (+31 more)

### Community 209 - "data/ingestors/nfl_inplay_history.py"
Cohesion: 0.16
Nodes (22): Budget, buy_halftime(), buy_inplay(), events_for(), _floor5(), _get(), halftime_requests(), halftime_windows() (+14 more)

### Community 21 - "Mobile record hero and equity curve"
Cohesion: 0.04
Nodes (101): Slop, StatusForSpeech, EquityPoint, plotLayout, PlotPad, ParlaySummary, SportGroup, TrackRecordSummary (+93 more)

### Community 210 - "Mobile paywall billing and account access"
Cohesion: 0.03
Nodes (154): AccessState, useAccess, AuthState, AuthStatus, useAuth, useEntitlement, useSubscription, AuthCallback (+146 more)

### Community 211 - "Mobile bankroll number formatting checks"
Cohesion: 0.09
Nodes (30): BankrollCheck, BankrollCommit, BankrollPatch, BankrollRead, NumberSeparators, Part, walk(), deviceSeparators() (+22 more)

### Community 215 - "Idle database read transaction tests"
Cohesion: 0.07
Nodes (14): _Rec, _credits_used_today(), _flat(), test_a_lock_timeout_fails_that_file_and_the_next_still_runs(), test_a_locked_bet_releases_the_lock_check(), test_a_quiet_tick_rolls_the_read_back(), test_a_tick_that_writes_does_not_roll_the_insert_back(), test_is_locked_releases_the_read() (+6 more)

### Community 216 - "NHL market-anchored moneyline model"
Cohesion: 0.05
Nodes (31): OffsetLogit, _Fixed, _GamesConn, _add_rating(), build_inputs(), choose_C(), decision_window(), fit() (+23 more)

### Community 218 - "Mobile push test diagnostics"
Cohesion: 0.08
Nodes (30): PushState, ForcedOnlyReason, PushDiagnosis, PushFailureReason, TestPushResult, reasonOf(), diagnosePushError(), errorText() (+22 more)

### Community 22 - "Monitor dashboard probe and cache tests"
Cohesion: 0.04
Nodes (43): _Resp, age(), cached(), clear(), _credits_from(), _redact(), _scrub(), classify() (+35 more)

### Community 220 - "tests/test_db_reconnect.py"
Cohesion: 0.09
Nodes (16): _Conn, _Cursor, _is_write(), _lost(), test_a_committed_transaction_is_clean_again(), test_a_lost_connection_with_uncommitted_writes_raises_connection_lost(), test_a_read_on_a_lost_connection_reconnects_and_retries(), test_a_statement_timeout_is_not_a_lost_connection() (+8 more)

### Community 222 - "Discord recap restatement"
Cohesion: 0.07
Nodes (16): _Conn, test_a_restated_recap_is_labelled_and_says_why(), _resp(), test_a_404_is_an_answer_not_a_retry(), test_a_persistent_403_still_raises_after_the_last_attempt(), test_a_recap_whose_count_merely_drifted_is_not_due(), test_a_recap_with_a_late_settlement_is_due(), test_a_transient_403_is_retried_and_the_second_answer_is_used() (+8 more)

### Community 223 - "In-play scorer locks and push alerts"
Cohesion: 0.10
Nodes (20): FakeConn, _Rows, _lane_signature(), _write_live_picks(), _locked_live_lanes(), test_the_lane_signature_carries_the_deciding_price(), _log_lines(), _pick() (+12 more)

### Community 225 - "tests/test_refresh_retry.py"
Cohesion: 0.14
Nodes (23): Decision, RefreshRun, _decide(), _done(), _run(), test_a_failed_view_migration_fails_the_step(), test_a_pass_that_finished_with_failed_steps_ran_its_chain(), test_a_redeploy_between_passes_replaces_nothing() (+15 more)

### Community 226 - "NBA results ingestion and prop settling"
Cohesion: 0.06
Nodes (22): PgStore, PlayerResolver, box_is_complete(), build_dnp_rows(), build_log_rows(), fallback_id(), ingest_nba_results(), _is_team() (+14 more)

### Community 228 - "NBA results ingestor tests"
Cohesion: 0.07
Nodes (32): _Conn, _ESPN, FakeStore, _FixedNow, fill_missing(), _default_nba(), _default_nhl(), _game() (+24 more)

### Community 229 - "NBA injury report ingest tests"
Cohesion: 0.08
Nodes (23): _Conn, _Cur, _DatesConn, _PdfFetcher, _content_of_fixture(), _rows(), test_a_changed_report_stores_its_rows(), test_a_connection_lost_mid_write_re_runs_the_whole_slot() (+15 more)

### Community 23 - "NBA second game projection engine"
Cohesion: 0.03
Nodes (91): EW, Last, Model, PointInputs, State, World, actuals(), apply_models() (+83 more)

### Community 230 - "tests/test_local_cache_is_additive.py"
Cohesion: 0.10
Nodes (13): _FakeConn, main(), _merge_with_cache(), _pull_odds(), _pull_seasoned(), _register_from_feature_engine(), cached(), _frame() (+5 more)

### Community 231 - "tests/test_calibration_check_coverage.py"
Cohesion: 0.11
Nodes (18): _Shim, _bet(), _calibration_results(), db(), _graded(), _make_db(), _only(), _promote() (+10 more)

### Community 232 - "Discord void notice posting tests"
Cohesion: 0.08
Nodes (17): Ledger, _bind(), _row(), test_a_live_void_still_posts_when_a_pregame_sibling_would_block(), test_a_non_2xx_response_and_a_request_exception_record_nothing(), test_a_posted_sibling_on_the_sideless_lock_is_not_released(), test_a_rejected_post_and_a_raised_post_record_nothing(), test_a_rerun_skips_locks_that_already_have_a_notice() (+9 more)

### Community 233 - "tests/test_book_team_map.py"
Cohesion: 0.11
Nodes (15): _Conn, abbr_from_team_string(), resolve_game_id(), split_matchup(), test_a_non_mlb_sport_is_refused_rather_than_guessed(), test_a_string_with_no_at_sign_is_refused(), test_a_unique_game_resolves(), test_an_ambiguous_game_resolves_to_none() (+7 more)

### Community 234 - "tests/test_team_board_cache.py"
Cohesion: 0.08
Nodes (11): _Conn, _Cursor, refresh_team_board_cache(), team_board_pairs(), team_board_seasons(), _cols(), test_every_team_sport_gets_last_this_and_next_year(), test_one_failing_pair_does_not_stop_the_rest() (+3 more)

### Community 235 - "NCAAF game feature building tests"
Cohesion: 0.03
Nodes (47): TestComputeTarget, _SqliteShim, _compute_target(), _assemble_ncaaf_features(), _blk_points_l3(), _blk_stats(), build_bulk_ncaaf_lookups(), build_ncaaf_features_from_bulk() (+39 more)

### Community 238 - "nfl/live_model/tests/test_rush_attempt_pace.py"
Cohesion: 0.07
Nodes (21): Read, pace_ratio(), _sigmoid(), under_prob(), _price(), test_a_line_he_has_already_passed_is_not_a_live_proposition(), test_a_missing_accrued_count_is_refused_not_treated_as_zero(), test_a_reachable_over_is_declined_rather_than_faded() (+13 more)

### Community 239 - "NFL wind board fast publishing tests"
Cohesion: 0.10
Nodes (18): FakeConn, _num(), publish_board(), matchup(), _append_board(), _body(), _row(), _sent() (+10 more)

### Community 24 - "NBA fifth search period shares"
Cohesion: 0.05
Nodes (38): LazyFrames, american(), band_bounds(), band_columns(), cell_specs(), control_shuffles(), _cum_before(), emit_f7() (+30 more)

### Community 244 - "MLB weather forecast ingestor"
Cohesion: 0.06
Nodes (17): _Resp, TestTheHourIsTheGamesOwn, TestTheRequestCoversTheTargetHour, TestTheStoreReadsTheStartTime, TestTheUmpireLandsOnEveryPass, backfill_weather(), _celsius_to_f(), fetch_and_store_weather_for_date() (+9 more)

### Community 245 - "NHL team rates as of date"
Cohesion: 0.15
Nodes (5): TeamBook, TestBlendedTeamInputs, TestTeamRatesAsOf, _r(), _t()

### Community 248 - "NHL moneyline rebuild and grading"
Cohesion: 0.03
Nodes (107): OffsetLogit, accuracy(), first_games(), logloss(), main(), sweep(), units(), walk() (+99 more)

### Community 249 - "models: slate_concentration + test_slate_concentration"
Cohesion: 0.15
Nodes (15): SlateConcentration, apply_slate_guard(), apply_slate_concentration_guard(), _attr(), _edge_of(), _is_bet(), measure_side_concentration(), _side_of() (+7 more)

### Community 250 - "CLV backtests and bias scans"
Cohesion: 0.14
Nodes (9): ShrunkEnsemble, add_form(), build(), feature_columns(), market_features(), team_game_stats(), fmt(), main() (+1 more)

### Community 251 - "View migration lock handling tests"
Cohesion: 0.09
Nodes (23): _Conn, _Deadlock, _LockTimeout, _StatementTimeout, _Syntax, execute(), _before(), _code() (+15 more)

### Community 256 - "Worker job queue retries and locks"
Cohesion: 0.06
Nodes (23): _Conn, _DedupeConn, _fake(), test_a_busy_queue_claims_nothing(), fetchone(), test_a_declared_job_is_queued_once_however_often_it_is_read(), test_a_failing_job_is_requeued_until_the_attempt_cap(), _boom() (+15 more)

### Community 259 - "NBA total luck card publishing"
Cohesion: 0.06
Nodes (24): FrameConn, load_artifact(), artifact(), decided_games(), ensure_decisions_table(), ledger_exists(), load_quote_rows(), load_season() (+16 more)

### Community 26 - "Mobile performance and tracked bets"
Cohesion: 0.05
Nodes (74): Props, Props, Props, ManualBet, ManualBetInput, ManualBetResult, StakeMode, StakeState (+66 more)

### Community 261 - "NBA game four point estimates"
Cohesion: 0.05
Nodes (41): OffsetRidge, Point, base_inputs(), cell_specs(), check_cell_count(), choose_C_linear(), derivative_data(), derivative_plan() (+33 more)

### Community 265 - "Best line threshold sweep"
Cohesion: 0.10
Nodes (12): _Conn, american_to_decimal(), units_at(), _row(), test_a_better_price_pays_more_than_the_dk_price(), test_a_loss_costs_one_unit_at_every_price(), test_a_push_is_flat(), test_a_retired_model_is_never_recommended_a_cut() (+4 more)

### Community 269 - "NCAAF college data ingest tests"
Cohesion: 0.07
Nodes (8): _GamesConn, _TeamsConn, test_ingest_games_retains_a_historical_utc_id_and_uses_et_for_a_new_row(), fake_get(), test_ingest_pulls_fbs_then_everyone_and_fbs_rows_win(), test_ingest_retries_everyone_without_a_year_if_the_season_filter_is_empty(), test_prior_context_tolerates_missing_talent_and_returning(), test_weekly_snapshot_build_aborts_on_failed_fetch()

### Community 27 - "Mobile betslip and parlay legs"
Cohesion: 0.02
Nodes (200): Props, ParlayRestorePayload, ResolvedSlip, GameLineLegSpec, GameLineMarket, LineLegSpec, LineSheetInput, LineSide (+192 more)

### Community 270 - "NBA pregame scoring window"
Cohesion: 0.06
Nodes (32): PregamePlan, bucket(), label(), main(), table(), wilson(), test_projecting_runs_after_the_decisions_are_published(), _db() (+24 more)

### Community 272 - "NCAAF in-play bet lock and serving"
Cohesion: 0.05
Nodes (22): LiveEngine, FakeConn, _Rows, write_picks(), expected_value(), db(), test_both_lanes_locked_touches_nothing(), test_dry_run_never_touches_db() (+14 more)

### Community 273 - "tests/test_prop_odds_utc_stamp.py"
Cohesion: 0.12
Nodes (13): _Conn, _assert_utc_stamp(), _frozen(), _run_mlb(), capture(), events(), _run_ncaaf(), test_an_eastern_row_then_a_later_utc_row_sorts_in_time_order() (+5 more)

### Community 274 - "Live monitor web server streaming"
Cohesion: 0.29
Nodes (4): Handler, _connect(), dumps(), _json_default()

### Community 277 - "NCAAF opener strategy walk-forward search"
Cohesion: 0.06
Nodes (34): FoldResult, _apply_calibration(), exponential_recency_weights(), _logit(), make_ensemble(), fit_predict(), make_lgbm(), fit_predict() (+26 more)

### Community 278 - "tests/test_feature_artifact_agreement.py"
Cohesion: 0.11
Nodes (13): _Stub, _TolerantUnpickler, _load(), _newest_artifact(), test_artifact_width_matches_its_own_feature_cols(), test_config_list_matches_the_trained_artifact(), test_known_drift_only_names_real_models(), test_pending_features_are_not_live_without_a_retrain() (+5 more)

### Community 279 - "NFL prop one side per line"
Cohesion: 0.16
Nodes (8): _Conn, best_per_prop(), _hockenson(), test_a_different_market_on_the_same_player_is_still_its_own_bet(), test_input_order_does_not_decide_the_side(), test_nfl_publish_will_not_add_the_other_side_of_a_locked_line(), test_opposite_sides_of_one_line_collapse_to_the_bigger_edge(), test_wnba_publish_will_not_add_the_other_side_of_a_locked_line()

### Community 28 - "Closing line value math"
Cohesion: 0.06
Nodes (28): _Conn, _Res, test_a_one_way_close_is_not_de_vigged(), test_a_worse_close_is_negative_and_equal_prices_are_zero(), test_devigging_the_taken_price_is_not_what_primary_does(), test_kalshi_close_is_not_de_vigged(), test_market_edge_devigs_only_the_close(), test_other_side_prices_include_the_draw_on_a_three_way() (+20 more)

### Community 281 - "tests/test_cloud_retrain_artifacts.py"
Cohesion: 0.10
Nodes (12): _Conn, _restore_artifact(), test_a_failed_upload_does_not_lose_a_model_that_trained(), test_a_missing_artifact_table_is_not_an_error_on_restore(), test_a_no_register_run_stores_nothing(), test_load_model_actually_loads_from_the_store_when_the_file_is_gone(), fetchone(), test_load_model_returns_none_when_the_store_has_nothing_either() (+4 more)

### Community 282 - "NHL side models never bet against each other"
Cohesion: 0.08
Nodes (28): _Conn, _ThreeWay, _apply_side_conflicts(), bets(), _endings_won(), picks_cannot_both_win(), side_checked_models(), ml() (+20 more)

### Community 284 - "Discord pick and recap notifier"
Cohesion: 0.03
Nodes (61): _Posted, _Rejected, test_a_malformed_timestamp_drops_the_stamp_rather_than_raising(), test_american_odds_formatting(), test_clv_line_is_empty_when_nothing_was_measured(), test_game_time_renders_in_eastern(), test_matchup_is_sport_aware(), test_prob_only_picks_fall_back_to_the_settlement_price() (+53 more)

### Community 285 - "System health and deliverability checks"
Cohesion: 0.04
Nodes (37): HealthReport, rollback_savepoint(), test_the_health_check_compares_the_exact_definitions(), test_dedupe_and_health_use_the_shared_tuple(), test_unique_row_sql_is_key_parts_plus_date_and_side(), test_a_pick_before_the_live_date_is_caught_in_either_view(), test_a_sport_missing_from_the_daily_view_is_caught(), test_an_empty_record_is_not_a_problem() (+29 more)

### Community 288 - "tests/test_nfl_opener.py"
Cohesion: 0.20
Nodes (5): TestBettableBooksOnly, TestSelectOpenerBets, _both_sides(), _frame(), _sched()

### Community 289 - "Player news feed ingestion"
Cohesion: 0.04
Nodes (52): NewsItem, NewsPlayer, FakeConn, FakeResponse, _Result, _article_url(), _athletes_in(), build_name_index() (+44 more)

### Community 290 - "Prop player name matching"
Cohesion: 0.09
Nodes (17): FakeConn, drop_duplicate_box_ids(), normalize_player_name(), resolve_feed_name(), _get_prop_dk_odds(), test_a_player_listed_twice_in_the_box_keeps_the_id_the_plays_use(), test_accented_roster_name_matches_the_flat_feed_name(), test_ambiguity_is_a_miss_not_a_guess() (+9 more)

### Community 293 - "Historical odds and first pitch cutoffs"
Cohesion: 0.01
Nodes (111): _Conn, trusted_first_pitch(), _upsert_savant_stats(), _ledger_entry_is_resumable(), _mark_in_play(), relabel_in_play(), run_historical_odds_range(), candidate_markets() (+103 more)

### Community 295 - "Discord and X results posting"
Cohesion: 0.03
Nodes (66): UnitStake, test_a_loss_costs_the_full_stake_and_a_push_costs_nothing(), test_a_pick_with_no_price_stays_in_the_units_at_bare_conviction(), test_a_six_column_row_still_tallies(), test_a_snapshot_with_no_clv_stores_null_not_zero(), test_clv_counts_only_picks_that_have_a_closing_price(), test_conviction_floors_at_one_not_a_half(), test_conviction_is_flat_regardless_of_kelly() (+58 more)

### Community 296 - "NHL blocked shots prop model"
Cohesion: 0.07
Nodes (25): TestTonightsRowIsATrainingRow, build_frame(), _ew(), expected_value(), fit(), load_skaters(), load_teams(), p_over() (+17 more)

### Community 298 - "tests/test_nfl_wind_publisher.py"
Cohesion: 0.13
Nodes (10): TestBuildRows, TestKickFields, TestParseMatchup, build_rows(), _fmt_line(), kick_fields(), parse_matchup(), test_nfl_wind_and_opener_rows_drop_a_bet_under_the_floor() (+2 more)

### Community 3 - "Pre-game odds and prop odds ingestors"
Cohesion: 0.01
Nodes (180): Meter, Meter, TestEveryOtherSportStillMintsItsOwn, TestNflResolvesOntoTheSchedule, TestTheResolverFailsClosed, TestResolveGameId, FakeResp, _fetch_pitcher_gb_pct() (+172 more)

### Community 30 - "NFL live prop model tests"
Cohesion: 0.04
Nodes (42): CreditBudgetExceeded, _FakeOdds, _IdRecordingOdds, _Q, GamedayWorker, GameTracker, _core_worker(), test_a_deployed_bias_must_sit_inside_its_measured_interval() (+34 more)

### Community 300 - "tests/test_health_reason_and_cadence.py"
Cohesion: 0.09
Nodes (20): Report, _one(), test_a_24h_ts_check_reads_as_daily(), test_a_bare_add_still_fills_both_columns(), test_a_broken_query_is_its_own_reason(), test_a_late_check_says_how_late(), test_a_passing_check_says_fresh(), test_a_skipped_check_says_the_gate_was_shut() (+12 more)

### Community 301 - "NBA odds history backfill"
Cohesion: 0.08
Nodes (23): ConnectionLost, _Ledger, _Meter, _Resp, gap_instants(), line_snapshots(), _hourly(), _t() (+15 more)

### Community 302 - "tests/test_nfl_weather_supabase_readback.py"
Cohesion: 0.22
Nodes (9): FakeConn, _patch_conn(), _rows(), test_a_null_requested_lead_is_not_returned(), test_a_one_lead_response_is_not_stored(), test_a_partial_window_is_not_returned(), test_a_subset_of_leads_reads_only_those_columns(), test_a_window_the_table_holds_is_read_from_the_table_and_never_fetched() (+1 more)

### Community 307 - "Publish signals on write tests"
Cohesion: 0.06
Nodes (18): _Conn, _body(), _row(), _surfaces(), _make(), test_a_broken_webhook_does_not_suppress_the_push(), test_a_failed_capture_still_delivers(), test_a_publish_failure_does_not_kill_the_tick() (+10 more)

### Community 308 - "Pitcher stats as-of invariant tests"
Cohesion: 0.05
Nodes (36): _FakeConn, last3_rates(), outs_from_ip(), per_nine(), whip(), already_a_series(), appearances(), _avg_distinct() (+28 more)

### Community 31 - "NBA prop market tip timing"
Cohesion: 0.05
Nodes (34): NbaPropDecision, Roster, coherent(), fair_under(), fetch_times(), find_bets(), in_window(), load_quotes() (+26 more)

### Community 312 - "NHL prop per-game limit tests"
Cohesion: 0.16
Nodes (4): TestInsertOnce, TestTheLimitPerGame, limit_per_game(), publish()

### Community 314 - "Pipeline log reason tests"
Cohesion: 0.22
Nodes (6): _Conn, _capture(), test_a_false_step_records_the_last_error_it_logged(), test_a_false_step_that_logged_nothing_still_says_so(), test_a_raising_step_still_records_the_exception(), test_the_sink_is_removed_after_the_step()

### Community 32 - "NBA in-game study two"
Cohesion: 0.05
Nodes (51): StateModel, norm_cdf(), apply_model(), benchmark_columns(), decision_quotes(), delta_ci(), _design(), eligible() (+43 more)

### Community 320 - "NFL opener and wind writer lock tests"
Cohesion: 0.07
Nodes (7): _Pg, _PgCursor, TestPreflightCiMode, TestPreflightLockChecks, wind(), wrapped(), fake_open()

### Community 321 - "NFL in-play prop settlement tests"
Cohesion: 0.09
Nodes (20): _SqliteShim, _Shim, TestSettlement, _box(), conn(), _game(), _live_bet(), raw() (+12 more)

### Community 322 - "Voided pick and Discord live field tests"
Cohesion: 0.06
Nodes (15): _FakeConn, _Conn, test_a_live_price_is_stamped_with_when_it_was_taken(), test_a_pick_with_no_write_time_renders_without_a_stamp(), test_producer_output_renders(), test_producer_select_and_dict_stay_in_step(), test_renderer_survives_a_missing_context_field(), test_unpriced_live_signal_still_renders() (+7 more)

### Community 323 - "NBA prop fetch window planning"
Cohesion: 0.07
Nodes (24): _PlanConn, _fires(), _game(), _jobs(), _plan(), _t(), test_a_projection_too_old_to_price_does_not_block_the_retry(), test_a_tick_fetches_exactly_the_window_games_then_decides_closes_and_publishes() (+16 more)

### Community 33 - "nfl/live_model/feeds: test_feed_resilience + espn"
Cohesion: 0.04
Nodes (55): _ScriptedTick, norm_name(), _competitors(), _deref(), fetch_live_events(), _https(), make_fetcher(), fetch() (+47 more)

### Community 330 - "NFL opener pick builder tests"
Cohesion: 0.08
Nodes (11): TestBuildOpenerRows, TestFireWindow, TestModelCardSplit, TestPublishOpenerInsertOnce, build_opener_rows(), _opener_model(), _card_row(), _row() (+3 more)

### Community 331 - "NHL player prop projection model"
Cohesion: 0.10
Nodes (25): Spec, _attach_teams(), build_frame(), build_goalie_frame(), build_skater_frame(), _ew(), excess_variance(), expected_value() (+17 more)

### Community 334 - "Settlement CLV scan timeout retries"
Cohesion: 0.09
Nodes (15): _Conn, _nhl_blended_features(), d(), _fn(), _sql(), test_a_non_timeout_is_not_retried(), test_a_second_timeout_does_not_abort_the_next_statement(), test_a_timeout_is_rolled_back_and_retried_once() (+7 more)

### Community 341 - "Health check skip budget tests"
Cohesion: 0.07
Nodes (17): FakeConn, _res(), _source_outside_the_budget_table(), test_a_check_never_seen_non_skipped_counts_its_whole_history(), test_a_check_skipped_only_today_is_not_counted_as_a_streak(), test_a_non_skipped_result_is_never_touched(), test_a_stuck_gate_escalates_past_its_budget(), test_an_honest_offseason_skip_stays_skipped_but_shows_its_length() (+9 more)

### Community 342 - "tests/test_live_pick_features.py"
Cohesion: 0.18
Nodes (11): FakeConn, _record_live_features(), _pick(), test_a_live_bet_records_its_feature_row_and_lambda(), test_a_pick_with_no_feature_row_is_skipped_not_written_empty(), test_a_recorder_failure_is_rolled_back_to_its_savepoint(), test_a_recorder_failure_is_swallowed_rather_than_raised(), test_a_success_releases_its_savepoint() (+3 more)

### Community 345 - "Public fade detection quality tests"
Cohesion: 0.04
Nodes (47): _Shim, record_exclusion_sql(), _bet(), _fade_slate(), _insert_open_bet(), test_a_mixed_slate_is_ok(), test_all_home_ncaaf_slate_is_flagged_without_mlb_hardcoding(), test_all_unders_public_fade_risk_is_crit() (+39 more)

### Community 349 - "tests/test_prop_missing_features.py"
Cohesion: 0.14
Nodes (5): TestARowMissingAFeatureIsNotScored, TestEveryPropLoopGoesThroughTheHelper, TestTheUmpireIsTheDeclaredException, _frame(), helper()

### Community 350 - "MLB public fade top picks ranking"
Cohesion: 0.08
Nodes (27): PublicFadeBet, diff(), pitcher_diff(), diff(), pitcher_diff(), numeric_feature_value(), _better_under(), composite_score() (+19 more)

### Community 351 - "Live game state poller triggers"
Cohesion: 0.06
Nodes (31): _NoOpConn, _bases_state(), _detect_triggers(), _discover_active_games(), _extract_state(), _fetch_live_feed(), _game_id_from_statsapi(), _is_active_or_starting_soon() (+23 more)

### Community 352 - "NCAAF FBS registry health checks"
Cohesion: 0.05
Nodes (19): TestFbsGate, TestRefusalLog, TestRegistryHealthCheck, TestUnratedFbsClaim, fbs_refusal_claims(), _is_fbs(), unrated_fbs_claim(), _alarm_part() (+11 more)

### Community 355 - "NFL in-play decline recorder tests"
Cohesion: 0.12
Nodes (12): PicksRecorder, _AvoidConn, _mk_decline(), test_a_market_opinion_decline_is_written_as_avoid(), test_a_moved_line_is_rewritten(), test_an_unchanged_proposition_is_not_rewritten(), test_plumbing_refusals_stay_out_of_picks(), test_recording_a_decline_can_never_break_a_bet() (+4 more)

### Community 357 - "NFL line snapshot publishing"
Cohesion: 0.09
Nodes (8): TestPublishLineSnapshots, TestSnapshotRowParams, TestTickLatency, publish_line_snapshots(), snapshot_row_params(), _csv_row(), execute(), _write_snapshot_csv()

### Community 361 - "NCAAF live state recording tests"
Cohesion: 0.16
Nodes (13): _Conn, record_live_states(), state_change_row(), state_key(), _state(), test_a_failed_write_never_costs_the_pass(), test_a_score_a_period_or_a_possession_change_is_written(), test_first_sight_is_written() (+5 more)

### Community 363 - "tests/test_run_ledger_orphans.py"
Cohesion: 0.12
Nodes (18): _Conn, db(), _insert_open(), _ledger(), _open_rows(), _row(), test_a_genuine_current_hang_is_still_detectable(), test_a_second_sweep_does_not_abort_the_pass_this_process_started() (+10 more)

### Community 367 - "Mobile over-the-air update flow"
Cohesion: 0.14
Nodes (23): Calls, CheckState, CheckTrigger, UpdateAction, UpdateOutcome, UpdatesApi, check(), fakeApi() (+15 more)

### Community 368 - "MLB in-play history backtest"
Cohesion: 0.21
Nodes (9): _Conn, _Cur, _lookup_home_won(), mlb_game_final(), sbr_twin_id(), test_no_final_anywhere_is_none(), test_scored_canonical_row_wins_and_keeps_its_label(), test_twin_id_swaps_only_the_renamed_franchises() (+1 more)

### Community 37 - "NBA lineup stints from play-by-play"
Cohesion: 0.05
Nodes (45): Diagnostics, _Seg, alias_play_ids(), roster_from_plays(), _accumulate(), _add_one(), appearances(), _athletes() (+37 more)

### Community 376 - "In-play calibrated decision tests"
Cohesion: 0.09
Nodes (15): RecordingConn, _cut(), _signal(), test_a_big_enough_claim_still_fires_after_calibration(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(), test_a_hot_live_model_no_longer_fires_the_marginal_bet(), test_a_live_model_is_read_out_of_picks_not_the_matview(), test_a_live_read_bounds_on_a_real_price() (+7 more)

### Community 377 - "NFL pass attempt bias refusal"
Cohesion: 0.09
Nodes (11): Read, blind_over_prob(), over_prob(), _pass_attempt_bias_allowed(), test_blind_arm_no_longer_asserts_a_rate(), test_restoring_a_bias_is_one_constant(), test_the_gates_are_checked_before_the_no_bias_decline(), test_the_interval_spans_zero_so_the_lane_declines_to_price() (+3 more)

### Community 378 - "Pick label and scorer tests"
Cohesion: 0.04
Nodes (24): TestBuildInjuryFlag, TestBuildPickLabel, TestFeatureValue, TestMakePick, _PickConn, _Rows, _SqliteShim, _build_injury_flag() (+16 more)

### Community 38 - "Pre-game game scorer and pick insert"
Cohesion: 0.02
Nodes (104): TestPushAdjustment, TestAmericanToImpliedProb, TestMissingStarterGate, TestQuarterKelly, today_et(), relevant_players(), _make_live_pick(), american_to_implied_prob() (+96 more)

### Community 380 - "Sharp book odds retention pruning"
Cohesion: 0.09
Nodes (9): Budget, BudgetSpent, _RecordingConn, _day(), prune_table(), mark(), settle(), test_prune_table_binds_the_prop_tables_carve_out_into_the_DELETE() (+1 more)

### Community 383 - "NCAAF opponent-adjusted search features"
Cohesion: 0.07
Nodes (29): AdjRatings, blended_rating(), build_adjusted_ratings(), build_prior_season_ratings(), features_for(), fit_opponent_adjustment(), load_fbs_membership(), load_team_games() (+21 more)

### Community 385 - "Any-book first five line scoring"
Cohesion: 0.06
Nodes (34): _Clf, _GameOddsConn, _fallback_game_line_quote(), _get_scoring_odds(), _has_real_game_price(), _cut(), _mlb_feat(), _on() (+26 more)

### Community 387 - "tests/test_repair_bogus_first_pitch_labels.py"
Cohesion: 0.13
Nodes (8): _Conn, _run(), test_a_dry_run_writes_nothing_at_all(), test_a_short_backup_rolls_back_and_relabels_nothing(), test_the_backup_is_written_before_the_update(), test_the_backup_table_is_revoked_from_the_public_roles(), test_the_bogus_set_is_computed_never_listed(), test_the_query_is_scoped_to_the_scheduled_start_not_the_derived_one()

### Community 39 - "nfl/live_model/tests/test_executor.py"
Cohesion: 0.06
Nodes (46): Decision, Executor, derivative_lag(), ev_floor(), _mk(), expected_value(), honest_probability(), is_hunt_state() (+38 more)

### Community 393 - "tests/test_sbr_loader.py"
Cohesion: 0.14
Nodes (3): _SqliteConnShim, _SqliteCursorShim, loader_conn()

### Community 394 - "Walk-forward evaluation"
Cohesion: 0.10
Nodes (13): _Cols, _Frame, _frame(), main(), walk_forward(), _fake(), test_a_fold_with_too_little_history_is_skipped(), test_a_single_class_test_season_is_skipped() (+5 more)

### Community 397 - "mobile/scripts/ux_scan.mts"
Cohesion: 0.16
Nodes (18): Finding, Severity, changedFiles(), entitlementGate(), fontScaling(), fontSizeLiterals(), hexColors(), main() (+10 more)

### Community 4 - "Pick settlement and closing line capture"
Cohesion: 0.08
Nodes (28): _FakeStatsapi, _SqliteShim, conn(), _game(), _pick(), raw(), test_a_doubleheader_row_with_a_final_keeps_its_picks_grading(), test_a_final_game_is_never_voided() (+20 more)

### Community 40 - "Mobile player stats and game log"
Cohesion: 0.02
Nodes (251): Props, PlayerNextGame, Section, Args, PlayerStatKey, HitMode, HitSelection, HitDirection (+243 more)

### Community 41 - "tests/test_live_quote_staleness.py"
Cohesion: 0.04
Nodes (46): ScoreClock, _Conn, _Q, quote_from_nfl_quotes(), rows_from_quote(), _abbrev(), rows_for_quotes(), parse_event_odds() (+38 more)

### Community 410 - "NBA prop closing line purchase tests"
Cohesion: 0.09
Nodes (11): _Conn, _Resp, test_a_close_already_held_is_not_bought_again(), test_a_due_close_buys_one_call_of_the_bet_markets_and_reports_its_credits(), test_a_pass_outside_the_window_spends_nothing(), test_only_a_game_holding_a_bet_and_only_once(), test_only_twelve_to_twenty_five_minutes_before_tip(), test_the_ten_minute_evening_passes_always_land_one_inside() (+3 more)

### Community 417 - "In-play publish parity with pauses"
Cohesion: 0.17
Nodes (12): _Conn, _db(), _labels(), _pick(), test_a_bet_written_while_paused_is_not_announced_after_an_unpause(), test_a_live_health_state_still_publishes(), test_a_paused_model_is_not_announced(), test_a_retired_model_is_not_announced() (+4 more)

### Community 419 - "CLV backfill job tests"
Cohesion: 0.15
Nodes (5): _Conn, _stub_backfill(), test_hard_cap_stops_a_nonempty_queue(), test_loops_until_a_pass_fills_nothing(), test_the_runner_opens_get_connection_and_calls_backfill_clv()

### Community 421 - "NBA injury report ingestor"
Cohesion: 0.04
Nodes (65): Fetcher, Report, _Fetcher, _all_slots(), _ampm(), _bands(), _column_of(), _columns() (+57 more)

### Community 424 - "supabase/functions/_shared/discord.ts"
Cohesion: 0.20
Nodes (15): DiscordApiError, DiscordUser, RoleSyncResult, addAppRole(), addGuildMember(), botFetch(), expectOk(), isGuildMember() (+7 more)

### Community 43 - "Worker job queue validation tests"
Cohesion: 0.03
Nodes (46): _VoidConn, _posted_row(), _quiet(), _run_void(), _run_void_job(), test_a_failed_job_needs_a_new_key_to_rerun(), test_a_graded_pick_is_refused_not_rewritten(), test_a_pick_that_does_not_exist_is_reported_as_missing() (+38 more)

### Community 433 - "NFL prop odds timeout-safe slicing"
Cohesion: 0.06
Nodes (24): _Conn, _Cur, TestPropOddsLoader, _Conn, _Cur, _fetch_slice(), _iter_prop_rows(), load_nfl_prop_odds() (+16 more)

### Community 435 - "NFL prop count and yardage distributions"
Cohesion: 0.14
Nodes (6): TestBinaryMarket, TestCountDistributions, TestYardageDistribution, _nfl_prop_probs(), _art(), test_nb_head_changes_probs_only_when_nb_r_present()

### Community 44 - "scripts: build_nfl_live_leader_artifact + model"
Cohesion: 0.06
Nodes (37): Artifact, Decision, am_to_dec(), artifact_from_dict(), band_for(), decide(), leader_expected_margin(), load_artifact() (+29 more)

### Community 440 - "NFL DraftKings line snapshots"
Cohesion: 0.17
Nodes (7): TestDkLineRows, append_snapshot_csv(), dk_line_rows(), dump_dk_lines(), _num(), snapshot_schedule(), _rec()

### Community 445 - "Threshold review schema lockdown tests"
Cohesion: 0.12
Nodes (4): _DdlConn, _DdlRes, test_a_failed_lock_down_does_not_lose_the_table(), test_ensure_schema_commits_the_tables_it_creates()

### Community 446 - "Schema guard and table lockdown"
Cohesion: 0.05
Nodes (25): GuardConn, ensure_table(), _ddl(), _dk_direct_feed(), _is_guarded(), _job_queue(), _kickoff_wind(), _live_calibration() (+17 more)

### Community 448 - "tests/test_discord_channel_probe.py"
Cohesion: 0.17
Nodes (7): _Resp, test_the_probe_covers_the_per_sport_live_channels(), test_the_probe_never_posts_and_never_returns_the_url(), test_the_probe_reports_the_channel_behind_each_sport(), _get(), test_two_sports_sharing_a_channel_are_flagged(), _job_discord_probe()

### Community 45 - "tests/test_nfl_prop_one_read_per_game.py"
Cohesion: 0.06
Nodes (25): _Conn, _Log, publish_hour_missed(), publishable_games(), _at(), _games(), test_a_game_is_publishable_on_exactly_one_pass_in_its_window(), test_a_game_with_no_kickoff_is_never_published() (+17 more)

### Community 450 - "Bounded odds prune retry tests"
Cohesion: 0.05
Nodes (44): StandIn, Timeout, p(), _after_nth_delete(), build(), drain(), _expire_after_deletes(), _fails_on() (+36 more)

### Community 457 - "Team stats as-of rebuild and invariants"
Cohesion: 0.03
Nodes (54): _SeasonConn, already_a_series(), build_rows(), _games(), impossible_games_played(), live_season_snapshot_grace(), main(), _played_actual() (+46 more)

### Community 458 - "Injury report ingestion"
Cohesion: 0.03
Nodes (37): TestCoreTeamsFallback, _athlete_name(), _compute_return_ramp(), _espn_team_ids(), fetch_espn_injuries(), _fetch_espn_team_injuries(), fetch_mlb_transactions(), _fetch_nba_espn_team_ids() (+29 more)

### Community 464 - "NCAAF gameday live odds cadence"
Cohesion: 0.04
Nodes (29): _Ctx, _ev(), _feed_with_payload(), gameday_mod(), _main_source(), _modelled_monthly_cfbd_calls(), test_a_single_failed_summary_does_not_drop_the_other_games(), test_a_sustained_feed_outage_degrades_to_no_odds() (+21 more)

### Community 469 - "Multi-book odds ingestion"
Cohesion: 0.05
Nodes (26): _OddsConn, _Resp, _odds_query(), _prop_markets(), _source(), test_a_game_with_no_commence_time_keeps_every_row(), test_a_rejected_book_list_falls_back_to_the_decision_book(), _get() (+18 more)

### Community 47 - "scripts/nfl_edge_gameline_rules.py"
Cohesion: 0.09
Nodes (47): Tee, ats(), bettable_ats(), bh(), board_at(), board_open(), bstat(), cell() (+39 more)

### Community 470 - "System health check pass tests"
Cohesion: 0.11
Nodes (4): TestHealthCheckIsNotCountedAsAFailingStep, TestPassCompletion, TestPassSteps, _add_run()

### Community 471 - "tests/test_model_game_savepoint.py"
Cohesion: 0.15
Nodes (4): _PoisonConn, _games(), test_a_best_price_timeout_is_the_logged_error_and_the_next_lookup_runs(), test_a_model_sql_error_does_not_poison_the_next_model()

### Community 473 - "Health check pick delivery tests"
Cohesion: 0.17
Nodes (4): TestSignalDelivery, _add_signal(), _iso(), _results()

### Community 474 - "NBA historical odds archive parser"
Cohesion: 0.05
Nodes (41): _Conn, classify(), _fold(), _gid(), _is_half(), iso_z(), load(), match() (+33 more)

### Community 478 - "Football alternate line rejection retries"
Cohesion: 0.14
Nodes (9): _Resp, test_a_422_retries_without_the_alternates_before_going_dk_only(), fake_get(), test_a_422_with_no_alternates_still_takes_the_dk_only_retry(), fake_get(), test_a_rejected_football_alternate_chunk_costs_only_itself(), fake_get(), test_football_live_slate_requests_alternates_and_a_backfill_does_not() (+1 more)

### Community 48 - "tests/test_calibration_watch.py"
Cohesion: 0.05
Nodes (15): _Conn, _Res, TestDormantLiveModels, TestItNeverDecides, TestRosterChanges, TestTheRun, TestVerdictChanges, TestVolumeShifts (+7 more)

### Community 482 - "Paused and no-signal row tests"
Cohesion: 0.05
Nodes (26): _Conn, _nfl_prop_too_early(), _iso(), test_a_kickoff_beyond_the_ceiling_is_too_early(), test_a_started_or_unknown_kickoff_is_not_too_early(), test_the_boundary_is_inclusive_at_the_ceiling(), test_the_scorer_and_the_card_read_ONE_constant(), test_the_scorer_loop_actually_applies_the_ceiling() (+18 more)

### Community 484 - "Push line move alert tests"
Cohesion: 0.17
Nodes (5): _Conn, _Res, _alerts(), test_a_moneyline_has_no_number_and_still_alerts(), test_a_price_at_another_number_is_not_a_move()

### Community 485 - "NFL weather history fetcher"
Cohesion: 0.18
Nodes (10): DailyLimit, Pacer, consolidate(), era5_check(), game_hours(), log(), main(), om_get() (+2 more)

### Community 488 - "Model performance monitor tests"
Cohesion: 0.07
Nodes (14): FakeConn, http_server(), live_server(), test_perf_reads_the_matview_not_the_expensive_view(), test_roster_reports_a_registered_but_untrained_model(), _second_arm(), _sql(), test_a_fully_unpriced_recovered_model_reports_no_roi() (+6 more)

### Community 49 - "Pipeline failure alerting and heartbeats"
Cohesion: 0.05
Nodes (23): FakeConn, TestDeliveryAndNoise, TestHealthCheckOnlyIsNotADirtyPass, TestItCannotBreakTheWorker, TestSilentJobs, TestWhatCountsAsAFailure, _clean_runs(), _posts() (+15 more)

### Community 490 - "NCAAF starter-out research dataset"
Cohesion: 0.10
Nodes (16): LabelSet, build_label_set(), _fetch_lines(), _fetch_raw(), opener_coverage(), _pick_provider(), provider_continuity(), main() (+8 more)

### Community 493 - "Mobile bankroll storage"
Cohesion: 0.23
Nodes (12): KeyValueStore, check(), eq(), fakeStore(), interleaving(), slowStore(), storage(), createBankrollStore() (+4 more)

### Community 497 - "Publish keys and push alerts"
Cohesion: 0.02
Nodes (96): _Conn, _KeyConn, paused_row_exclusion_sql(), test_the_restate_producer_keeps_the_first_bet_only(), _sql_key(), test_a_game_level_key_has_no_tail(), test_an_opening_signal_is_live_only_when_discord_published_it(), test_discord_led_visibility() (+88 more)

### Community 499 - "NHL totals card publisher"
Cohesion: 0.10
Nodes (15): _LockConn, _SlateConn, pick_rows(), test_nfl_prop_market_card_drops_a_bet_under_the_floor(), test_wnba_prop_market_card_drops_a_bet_under_the_floor(), _bet(), _iso(), _q() (+7 more)

### Community 503 - "DraftKings direct feed event matching"
Cohesion: 0.19
Nodes (7): _Conn, _game_id_for(), poll_once(), test_a_unique_match_resolves(), test_an_ambiguous_event_name_writes_nothing(), test_an_event_name_with_no_at_sign_is_refused(), test_an_unmatched_event_name_writes_nothing()

### Community 504 - "Member sportsbooks scratch database tests"
Cohesion: 0.08
Nodes (23): ScratchPostgres, pg_bin(), _code(), test_results_keep_pushes_and_ties_and_carry_no_stake(), test_schema_applies_twice_on_scratch_postgres_and_anon_can_only_read(), test_the_migration_is_one_statement_and_registered(), test_the_second_pass_returns_before_it_locks(), test_the_skip_guard_refuses_every_write_verb() (+15 more)

### Community 51 - "Mobile team stats screen"
Cohesion: 0.04
Nodes (124): NavRef, Sport, NextGame, Section, PushRoute, TeamLineQuote, Tier, FormGame (+116 more)

### Community 510 - "Pregame price age bound tests"
Cohesion: 0.20
Nodes (5): _TwoIdConn, _h2h_row(), test_a_copy_that_was_never_priced_still_reads_the_other_orientation(), test_the_abandoned_copy_of_a_fight_does_not_borrow_the_live_copys_price(), test_the_best_price_shop_follows_the_same_rule()

### Community 511 - "Prop odds next-day lookahead tests"
Cohesion: 0.17
Nodes (4): TestTheOddsFetchReachesTomorrow, TestTheScorerReachesTomorrow, _get_events(), _events_src()

### Community 512 - "External threshold map promotion"
Cohesion: 0.18
Nodes (4): _Conn, test_external_promotion_refuses_a_map_that_does_not_transfer(), test_external_promotion_writes_only_the_promoted_columns(), test_the_scorer_reads_the_external_map_like_any_promoted_one()

### Community 517 - "NCAAF in-play history backtest tests"
Cohesion: 0.09
Nodes (18): _Conn, _StubEngine, resolve_game_id(), rows_for(), grade(), _cand(), _event(), _no_db_school_lookup() (+10 more)

### Community 52 - "tests/test_best_line_live.py"
Cohesion: 0.04
Nodes (44): _FakeConn, _best_live_price(), _best_live_side(), _live_decision_quote(), _live_quote_is_on_offer(), _tag_live(), _ev(), _live_pick() (+36 more)

### Community 522 - "In-play score freshness guard tests"
Cohesion: 0.16
Nodes (9): _FakeConn, _odds(), test_a_quote_published_before_the_score_is_declined(), test_a_quote_republished_after_the_score_is_kept(), test_the_age_bound_alone_would_have_allowed_it(), test_the_age_bound_still_fires_independently(), test_the_score_lookup_is_scoped_and_ordered(), execute() (+1 more)

### Community 526 - "NCAAF college data refresh and backfill tests"
Cohesion: 0.16
Nodes (8): _NullConn, backfill_ncaaf(), refresh_ncaaf_games(), test_backfill_returns_totals_when_every_season_succeeds(), test_backfill_survives_a_mid_run_season_failure(), test_refresh_games_happy_path_counts_games(), test_refresh_games_repairs_every_season_and_reports_failures(), test_refresh_stats_isolates_a_failing_season()

### Community 527 - "NBA residual distribution pricing"
Cohesion: 0.18
Nodes (6): ResidDist, test_a_period_moneyline_removes_the_tie_mass(), test_a_past_average_miss_does_not_move_the_centre(), test_a_skewed_distribution_is_not_read_as_normal(), test_the_empirical_model_matches_the_normal_one_on_normal_residuals(), test_whole_lines_carry_push_mass_and_half_lines_none()

### Community 528 - "UFC fight stats ingest tests"
Cohesion: 0.12
Nodes (6): _IngestConn, _ingest(), _one_fight_event(), test_a_late_replacement_is_not_scored_on_the_original_booking(), test_a_row_naming_neither_fighter_is_left_unscored(), test_the_same_fight_stored_twice_is_scored_on_both_rows_each_way_round()

### Community 53 - "Mobile load errors and abort handling"
Cohesion: 0.02
Nodes (212): Props, Props, FighterSide, Props, LivePicksState, Args, PlayerNewsState, PropContext (+204 more)

### Community 533 - "NBA team total odds fetch tests"
Cohesion: 0.04
Nodes (52): Clock, _Cur, FakeDB, FakeResp, _billed(), closes_taken(), event_rows(), fetch_team_totals() (+44 more)

### Community 54 - "tests/test_void_picks.py"
Cohesion: 0.05
Nodes (20): _FakeConn, TestAPostedSignalIsLocked, TestAPostedVoidAnnouncesAfterCommit, TestTheToolRefusesToMatchEverything, TestVoidingAPostedPickIsAnExplicitOptIn, TestWhatMayBeVoided, TestWhatTheVoidWrites, DiscordVoidRejected (+12 more)

### Community 543 - "Closing line value price tests"
Cohesion: 0.07
Nodes (23): _Conn, _Res, _fn(), _migration(), _pick(), test_a_draftkings_decided_row_is_unchanged(), test_a_legacy_row_that_cannot_be_re_measured_leaves_the_old_method(), test_a_legacy_stamped_row_is_re_measured_and_leaves_the_queue() (+15 more)

### Community 545 - "Job heartbeat and stale jobs"
Cohesion: 0.14
Nodes (8): Conn, _build(), test_a_job_marked_disabled_is_not_silent(), test_a_job_that_runs_here_is_not_marked(), test_a_service_leaves_alone_the_jobs_another_service_owns(), test_startup_marks_an_owned_job_that_is_switched_off(), ensure_schema(), stale_jobs()

### Community 549 - "NBA turnovers prop settlement tests"
Cohesion: 0.18
Nodes (5): _SelectConn, test_a_turnovers_bet_on_a_player_who_played_settles_win_not_no_action(), test_the_loader_carries_every_stat_a_market_settles_on(), test_the_loader_selects_turnovers(), _load_nba_prop_actuals()

### Community 55 - "NCAAF game-day live feeds"
Cohesion: 0.04
Nodes (39): LiveOddsFeed, GameContext, _Conn, _Result, build_row(), _mark_written(), now_iso(), _publish_key() (+31 more)

### Community 550 - "NFL player props and stats ingestion"
Cohesion: 0.02
Nodes (84): TestGamesRows, TestKickoff, TestLocalOddsCache, TestParsePlayerRows, TestParseTeamRows, TestPlaceboCannotSilentlyNotHappen, TestPriceMath, TestSnapRows (+76 more)

### Community 551 - "MLB renamed franchise game merge tests"
Cohesion: 0.05
Nodes (29): _Conn, lock_down(), _fetchone(), schema_is_current(), ensure_ledger(), scram_stored_key(), discover(), fetch_all() (+21 more)

### Community 553 - "NFL in-play pick row building tests"
Cohesion: 0.13
Nodes (10): _Decision, build_pick(), test_a_locked_lane_writes_nothing_further(), test_a_pass_is_never_announced(), test_edge_is_the_platform_edge_not_the_lanes_ev(), test_every_row_key_is_actually_bound_by_the_insert(), test_the_label_agrees_with_the_side_and_the_line_it_carries(), test_the_label_names_the_stat_the_model_actually_trades() (+2 more)

### Community 554 - "NBA box score repair tests"
Cohesion: 0.13
Nodes (8): _Conn, boxes_to_repair(), _logs(), _run(), test_a_box_that_does_not_add_up_is_never_written(), test_a_game_nba_com_does_not_list_is_refused(), test_only_the_named_game_is_replaced_delete_first(), test_the_season_repair_names_every_missing_or_wrong_box()

### Community 56 - "tests/test_daily_retry.py"
Cohesion: 0.06
Nodes (42): _Conn, _Cursor, _FrozenDatetime, DailyRun, _aborted(), _aborted_row(), _ok(), _ok_row() (+34 more)

### Community 562 - "Results recap message id tests"
Cohesion: 0.03
Nodes (30): _Conn, _Ledger, _Resp, build_parser(), _date_is_over(), main(), post_backfill(), test_a_day_that_is_not_over_is_refused() (+22 more)

### Community 566 - "Odds repeat thinning keeps NBA rows"
Cohesion: 0.14
Nodes (10): _Conn, thin_repeats(), test_a_thinning_error_that_is_not_a_timeout_is_raised(), test_a_dry_run_counts_and_deletes_nothing(), test_an_unchanged_run_keeps_its_first_and_last_row(), test_every_move_survives_and_every_as_of_price_is_unchanged(), test_paid_history_todays_games_and_other_sports_are_untouched(), test_pre_game_and_in_play_are_separate_runs() (+2 more)

### Community 57 - "tests/test_live_book_move_guard.py"
Cohesion: 0.07
Nodes (39): BookMoveClock, _Unset, _MlbConn, american_to_implied(), _at(), _delaware_ctx(), _dk(), _iso() (+31 more)

### Community 570 - "NHL prop settlement tests"
Cohesion: 0.06
Nodes (15): _Shim, TestEveryLiveModelIsWiredEverywhere, TestSettlement, TestTheDistribution, TestTheGoalieFrame, TestTonightsRowIsATrainingRow, _bet(), db() (+7 more)

### Community 571 - "X manual post image fetch"
Cohesion: 0.17
Nodes (4): ImageFetch, test_fetch_https_image_sniffs_bytes_and_refuses_gif(), fetch_https_image(), _sniff_tweet_image()

### Community 58 - "Social post queue and drain"
Cohesion: 0.10
Nodes (35): QueueRejected, _actionable(), _as_utc(), _attach_media(), _checked_media_urls(), _checked_reply(), _claim(), drain_social_posts() (+27 more)

### Community 583 - "NFL pick monitor"
Cohesion: 0.08
Nodes (10): TestClassify, TestImmutabilityContract, TestLatestPerPick, TestTheJoinKeyMatchesPicks, TestWindPublisherLock, eval_row(), _picks_game_id(), classify() (+2 more)

### Community 584 - "Per-model expected value floor"
Cohesion: 0.12
Nodes (11): Gate, expected_value(), min_ev_for(), test_ncaaf_live_ev_floor_is_wired_from_config(), test_own_ev_floor_and_model_min_ev_stay_disjoint(), test_expected_value_is_on_the_quoted_price(), test_the_floor_is_the_global_one_unless_the_model_carries_a_higher_one(), test_the_shipped_floor_is_020_and_the_ncaaf_moneyline_keeps_the_030_it_was_swept_under() (+3 more)

### Community 588 - "NFL in-play pick writer commit tests"
Cohesion: 0.12
Nodes (7): _Conn, test_a_pass_is_never_written_to_picks(), test_an_unresolvable_decision_writes_nothing(), test_game_id_resolves_from_the_book_s_team_names(), test_picks_recorder_drops_a_pass_attempt_over_before_sql(), test_the_announce_runs_after_the_commit_and_after_the_connection_closes(), commit()

### Community 59 - "Odds API fetching and opener scripts"
Cohesion: 0.02
Nodes (75): OddsAPIClient, SnapshotResult, Puller, game_index(), main(), resolve(), rows_from_file(), stored_pairs() (+67 more)

### Community 590 - "X posting and pick refusal tests"
Cohesion: 0.05
Nodes (20): FakeConn, _R, test_discord_free_pick_candidates_refuse(), execute(), fetchall(), row(), _run(), test_event_with_no_games_row_is_skipped_and_others_still_insert() (+12 more)

### Community 597 - "Recap waits for NFL box scores"
Cohesion: 0.06
Nodes (10): _CursorResult, _go(), execute(), test_a_malformed_date_is_refused_before_anything_runs(), test_the_cursor_wrapper_rowcount_is_the_cursors(), test_the_job_does_not_bypass_the_day_is_over_guard(), test_the_job_does_not_read_rowcount_off_the_cursor(), test_the_job_only_clears_its_own_ledger_kind() (+2 more)

### Community 599 - "System health check test fixtures"
Cohesion: 0.15
Nodes (4): _FrozenDatetime, _Shim, db(), mlb_wired()

### Community 6 - "Mobile custom model builder and filters"
Cohesion: 0.02
Nodes (187): Props, BacktestPickRow, CustomModelStats, ChipGroup, ChipKey, FilterablePick, BetTypeChoice, BetTypeOption (+179 more)

### Community 61 - "X social posting and profile"
Cohesion: 0.04
Nodes (40): MediaUpload, TweetDelivery, test_form_params_are_in_the_signature_and_not_in_the_header(), test_a_clean_ledger_allows_the_post(), test_a_different_secret_changes_the_signature(), test_freepicks_in_the_pool_is_dropped(), test_signature_base_string_matches_rfc5849(), test_the_header_is_deterministic_for_a_fixed_nonce_and_clock() (+32 more)

### Community 611 - "supabase/functions/revenuecat-webhook/index.ts"
Cohesion: 0.22
Nodes (3): RcEvent, admin, PRODUCT_TO_PLAN

### Community 613 - "supabase/functions/whop-webhook/index.ts"
Cohesion: 0.25
Nodes (4): WhopMembership, signatureValid(), timingSafeEqual(), admin

### Community 615 - "NFL pick evaluation and monitor"
Cohesion: 0.11
Nodes (15): Bet, american_to_decimal(), american_to_prob(), _apply_ruling_wind(), apply_slate_cap(), _as_utc(), devig_two_way(), evaluate_board() (+7 more)

### Community 616 - "tests/test_nfl_props.py"
Cohesion: 0.22
Nodes (3): TestCardReplay, execute(), fetchall()

### Community 621 - "NFL wind and opener publisher"
Cohesion: 0.11
Nodes (15): _LockConn, TestNoneRowNeverLocks, _american_to_prob(), _changed(), _clear_scored_row(), _flush_board_safe(), _flush_snapshots_safe(), latest_eval_rows() (+7 more)

### Community 630 - "NFL live prop sharp book pull"
Cohesion: 0.22
Nodes (3): TestIngestEventsDoesNotShadowItsMarkets, test_live_prop_pull_asks_for_the_sharp_book(), fake_event_props()

### Community 632 - "NFL in-play prop dataset and calibration"
Cohesion: 0.05
Nodes (22): ScoreDistribution, evaluate(), _infer_position(), main(), _pool_prior(), report(), _rows_for_market(), _to_states() (+14 more)

### Community 633 - "Price prefilter timeout rollback tests"
Cohesion: 0.15
Nodes (9): _PoisonConn, _event_index(), _games(), _run(), test_a_failed_savepoint_rollback_falls_back_to_full_rollback(), test_both_prefilters_timing_out_still_reaches_the_pipeline_log(), test_lookahead_timeout_rolls_back_and_scoring_continues(), test_ncaaf_timeout_rolls_back_and_scoring_continues() (+1 more)

### Community 636 - "Prop grading timeout and rollback tests"
Cohesion: 0.25
Nodes (4): GradeConn, test_a_non_timeout_prop_error_rolls_back_and_raises(), test_a_timed_out_prop_date_does_not_abort_the_next(), settle()

### Community 643 - "Pregame line sweeps and features"
Cohesion: 0.03
Nodes (48): TestPregameSnapshotGuard, TestAmericanToDecimalScorer, _blk_bullpen_ip(), _blk_injuries(), _blk_pitcher(), _blk_rolling_runs(), _blk_season_loc_runs(), _blk_team_stats() (+40 more)

### Community 644 - "Daily picks email renderer"
Cohesion: 0.46
Nodes (6): Pick, _fmt_edge(), _fmt_odds(), main(), _pick_card(), render_email()

### Community 651 - "NFL wind bettable book filter"
Cohesion: 0.06
Nodes (15): TestTheCardFilters, TestTheListIsShared, _et(), _game(), test_a_schedule_placeholder_with_no_teams_is_never_planned(), test_every_team_on_the_stored_schedule_is_planned(), test_the_fetch_is_the_refresh_pass_s_own_nba_fetch(), test_the_plan_creates_no_table() (+7 more)

### Community 655 - "Mobile bankroll unit percent settings"
Cohesion: 0.32
Nodes (7): BankrollSettings, useBankroll(), canStepUnitPct(), sanitizeUnitPct(), stepUnitPct(), store, BANKROLL_DEFAULTS

### Community 666 - "NFL live pick announce isolation tests"
Cohesion: 0.29
Nodes (3): _OpenConn, test_a_written_bet_is_announced_with_its_own_game_date(), test_an_unlocked_lane_does_write()

### Community 67 - "tests/test_game_market_gate.py"
Cohesion: 0.06
Nodes (49): GateVerdict, MarketBookend, PublicSplits, apply_to_picks(), _as_float(), bookend_from_odds(), evaluate(), fair_prob() (+41 more)

### Community 670 - "NBA team total closing line tests"
Cohesion: 0.08
Nodes (15): _SnapConn, _book(), _capture(), _lateral(), _oc(), _quotes(), _team_total_pick(), test_a_close_at_the_same_number_is_graded_against_the_bet_book_s_close() (+7 more)

### Community 671 - "NHL prop EV regimes and Kalshi ladders"
Cohesion: 0.07
Nodes (21): TestRegimeOrder, best_per_player(), blocked_sides(), history(), pool(), main(), regime(), show() (+13 more)

### Community 674 - "NBA public splits quality backfill"
Cohesion: 0.15
Nodes (6): _CountingConn, backfill_quality(), quality_backfill_statements(), test_an_existing_table_gets_the_quality_column(), test_the_backfill_adds_the_column_and_commits_once(), test_the_backfill_rolls_back_when_a_count_is_not_what_was_measured()

### Community 675 - "Pipeline watch findings and alerts"
Cohesion: 0.04
Nodes (43): _Conn, collect(), test_a_clean_pass_produces_no_finding(), test_a_clean_run_still_posts(), test_a_confirmed_post_is_ledgered_so_the_run_can_be_verified(), test_a_failed_ledger_does_not_lose_the_report(), execute(), test_a_failed_query_rolls_back_and_does_not_sink_the_run() (+35 more)

### Community 678 - "NFL prop market card tests"
Cohesion: 0.22
Nodes (3): TestMarketCard, execute(), fetchall()

### Community 68 - "NBA second-model prop study"
Cohesion: 0.05
Nodes (41): Shape, base_key(), appearances(), box_tables(), build(), check_close_prior(), consensus_number(), empty_times() (+33 more)

### Community 683 - "Probability calibration map tests"
Cohesion: 0.04
Nodes (29): _FakeConn, _SchemaRecordingConn, poisson_probability_metrics(), test_a_map_that_does_not_help_out_of_sample_is_not_applied(), test_a_map_that_helps_is_applied(), test_a_model_with_no_record_takes_the_pooled_correction(), test_a_model_with_too_few_graded_picks_gets_the_shrunk_offset_not_a_platt_map(), test_an_unmapped_model_is_unchanged_by_phase_2() (+21 more)

### Community 688 - "Bounded odds pruning and thinning"
Cohesion: 0.13
Nodes (8): _Ctx, main(), run_prune_odds(), test_prune_rejects_keep_days_below_one(), __init__(), test_a_thinning_failure_still_prunes_both_tables_and_is_reported(), test_the_daily_run_gives_the_thinning_a_budget(), thin()

### Community 69 - "tests/test_pick_integrity.py"
Cohesion: 0.04
Nodes (44): _Conn, _Shim, _add_pick(), discord_sent(), _health(), health_db(), test_a_label_may_not_name_a_market_the_pick_does_not_settle_on(), test_a_label_naming_the_other_team_is_refused() (+36 more)

### Community 693 - "NHL props card quote selection"
Cohesion: 0.10
Nodes (9): _Conn, TestOnlyTheNewestFetchIsShopped, TestWhoThePlayerIs, candidates(), draftkings_at(), identities(), latest_quotes(), upcoming_rows() (+1 more)

### Community 7 - "Shared database access for scoring and features"
Cohesion: 0.01
Nodes (161): DBConnection, FrontierUnreadable, call_in_savepoint(), connection_lost(), statement_timeout(), poll_once(), _event_meta_lookup(), _build_synthetic_rows() (+153 more)

### Community 70 - "tests/test_record_one_pick_per_event.py"
Cohesion: 0.06
Nodes (36): _CaptureConn, _RecordingConn, _code(), _copy_for_node(), _fn(), _node(), _read(), test_a_custom_model_counts_the_kept_copy_once() (+28 more)

### Community 708 - "Weekly job catch-up tests"
Cohesion: 0.18
Nodes (3): _Conn, test_a_failing_savant_refresh_does_not_cost_the_calibration_its_catch_up(), test_ownership_is_checked_per_job()

### Community 71 - "MLB in-play trigger orchestrator and replay"
Cohesion: 0.02
Nodes (132): GameClock, _credit_cost(), credits_used_today(), fetch_in_play_odds(), consume_triggers_once(), _last_fg_fetch_age(), _live_game_ids(), _pending_triggers() (+124 more)

### Community 711 - "Pipeline report rollback tests"
Cohesion: 0.20
Nodes (4): _Conn, _rows(), test_a_failed_query_rolls_back(), test_one_broken_section_does_not_break_the_rest()

### Community 73 - "nfl/live_model/tests: test_props + props"
Cohesion: 0.08
Nodes (34): PropProjection, GameState, PlayerState, _accrued(), _count(), detect_inactive(), price_over(), project() (+26 more)

### Community 755 - "Player prop market pricing core"
Cohesion: 0.01
Nodes (200): MarketBet, Rung, TestKickoffGate, TestLocalCacheGuards, TestMarketGrading, TestMarketRelative, TestNaNIsAbsent, TestNormaliseName (+192 more)

### Community 758 - "Deploy checks and job queue"
Cohesion: 0.07
Nodes (17): _Conn, test_a_declared_job_carries_its_run_after(), test_a_failing_check_raises_so_the_queue_announces_it(), test_a_job_can_only_name_a_registered_check(), test_enqueue_rejects_a_naive_run_after(), test_enqueue_stores_run_after(), test_every_check_is_read_only(), test_the_claim_waits_for_run_after() (+9 more)

### Community 77 - "tests/test_wnba_prop_market.py"
Cohesion: 0.05
Nodes (29): _FakeConn, _QuoteConn, apply_price_floor(), norm_name(), pick_rows(), player_ids(), publish(), render() (+21 more)

### Community 78 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.08
Nodes (20): _Conn, _RaceConn, TestBuildScoredRows, TestFlexedKickoffRefreshes, TestLockSurvivesNothing, TestNoneRowBesideABetIsCleared, TestPickEmLabel, TestPublishRace (+12 more)

### Community 79 - "NHL derivative totals walk-forward model"
Cohesion: 0.07
Nodes (38): Market, build_p1_frame(), build_team_frame(), day_interval(), _ew(), fit(), game_means(), _implied_vec() (+30 more)

### Community 790 - "Prop no-bet rows survive tipoff"
Cohesion: 0.22
Nodes (5): _Clock, _fake_datetime_class(), _game(), _iso(), _wire()

### Community 80 - "Per-model EV floor card tests"
Cohesion: 0.08
Nodes (23): NhlTotalBet, _built(), floor_030(), identity_maps(), _nfl_fixtures(), open_pregame_cut(), _pregame(), shrink_map() (+15 more)

### Community 83 - "NHL prop card pick writing tests"
Cohesion: 0.17
Nodes (6): TestTheBacktestGradesTheRuleTheCardPlays, TestTheCard, implied(), pick_rows(), _mus(), _quotes()

### Community 84 - "NBA prop card runner tests"
Cohesion: 0.04
Nodes (60): Plan, _Conn, ev_percentile(), decided_games(), ensure_decisions_table(), games_with_a_bet(), load_roster(), look() (+52 more)

### Community 848 - "Prop odds book update time"
Cohesion: 0.26
Nodes (6): _Conn, _parse(), test_a_row_built_without_the_key_still_inserts_as_null(), test_no_clock_anywhere_is_none_not_our_fetch_time(), test_the_column_is_added_only_when_the_catalog_lacks_it(), test_the_markets_own_clock_is_stored_else_the_books()

### Community 85 - "tests/test_recap_retries_a_skipped_day.py"
Cohesion: 0.06
Nodes (25): _LiteConn, World, _add_pick(), _grade(), _lite(), _schema(), test_a_day_with_nothing_counting_posts_nothing_and_logs_nothing(), test_a_failed_receipt_never_reposts_the_day() (+17 more)

### Community 850 - "Database connection and shared utilities"
Cohesion: 0.01
Nodes (162): Plan, live_slate_dates(), _connect(), _convert_params(), _convert_params_outside_literals(), get_connection(), _open(), _session_options() (+154 more)

### Community 865 - "NHL blocked shots player matching"
Cohesion: 0.36
Nodes (3): TestWhoThePlayerIs, name_key(), upcoming_rows()

### Community 88 - "NBA prop market decision tests"
Cohesion: 0.05
Nodes (50): NbaPropBet, _PublishConn, _SettleConn, pick_label(), pick_rows(), _bet(), _decision(), fair_under() (+42 more)

### Community 880 - "NBA second game luck run tests"
Cohesion: 0.25
Nodes (8): _Stop, test_full_asks_the_load_for_every_season_it_grades(), load(), test_full_runs_the_spread_sign_self_check_before_reading_anything(), check(), test_the_run_prices_the_market_with_the_empirical_distribution(), close_dist(), close_sigma()

### Community 898 - "NFL in-play decision audit fan-out"
Cohesion: 0.18
Nodes (5): TeeRecorder, test_a_failing_announcer_cannot_undo_or_fail_the_write(), test_a_failing_recorder_cannot_take_the_other_down(), boom(), test_the_audit_log_is_written_before_the_database()

### Community 9 - "NFL early-signal publishing tests"
Cohesion: 0.08
Nodes (14): _Conn, _sql_for(), test_a_started_game_is_still_never_published(), test_both_publishers_apply_the_apps_action_filter(), test_both_publishers_read_the_table_the_app_reads(), test_capture_reaches_as_far_as_the_poller_can_write(), test_capture_reaches_forward_for_the_locked_lookahead_sports(), test_ncaaf_lookahead_is_only_safe_because_the_lock_is_general() (+6 more)

### Community 904 - "NBA team total odds billed feed stub"
Cohesion: 0.22
Nodes (4): FakeFeed, fn(), logged(), call()

### Community 912 - "NBA public betting splits ingestion"
Cohesion: 0.05
Nodes (44): _NoDB, _Store, an_pct(), build_rows(), clean_pair(), match_game(), parse_v1_sides(), parse_v2_sides() (+36 more)

### Community 914 - "Game feature and injury adjustments"
Cohesion: 0.04
Nodes (16): TestComputeInjuryAdjustment, TestFeatureMap, TestHasReturnee, TestHasStarterOut, TestMarketForOdds, TestOpeningNightIsEarlySeason, _blk_nhl_asof(), _blk_nhl_loc_goals() (+8 more)

### Community 92 - "tests/test_ncaaf_prop_odds.py"
Cohesion: 0.05
Nodes (27): _Conn, _Resp, _market_chunks(), _football_map(), resolver(), scope(), test_a_book_we_did_not_ask_for_is_never_written(), test_a_day_with_no_college_games_spends_nothing() (+19 more)

### Community 926 - "MLB prop feature engine"
Cohesion: 0.03
Nodes (53): _Rec, _ScoringConn, _StubConn, _StubResult, _all_batter_rows(), _all_pitcher_rows(), _batter_rate(), _batter_rolling_avg() (+45 more)

### Community 94 - "NCAAF in-play score distribution pricing"
Cohesion: 0.04
Nodes (43): ScoreDistribution, _cluster_bootstrap(), evaluate(), main(), report(), fit(), load_states(), main() (+35 more)

### Community 95 - "tests/test_ncaaf_pbp_store.py"
Cohesion: 0.07
Nodes (23): _Conn, _extremes(), load_season_from_db(), observed_ranges(), _report_ranges(), store_season(), finalize_states(), states() (+15 more)

### Community 96 - "tests/test_heartbeat_watchdog.py"
Cohesion: 0.07
Nodes (28): _FakeConn, _FakeCursor, _break_db(), sink(), test_a_failed_post_does_not_start_the_throttle(), test_a_healthy_start_never_announces_a_recovery(), test_a_returning_outage_alerts_again_immediately(), test_a_silent_failure_alerter_is_caught_by_the_watchdog() (+20 more)

### Community 99 - "Record correction social posts"
Cohesion: 0.06
Nodes (28): Ledger, _Result, _pin(), _real_post(), _real_tweet(), x_posts(), _publish(), test_a_failed_discord_ledger_does_not_send_x() (+20 more)

### Community 100 - "NFL edge research shared helpers"
Cohesion: 0.04
Nodes (82): backfill_cost(), bets(), bh(), clean_2h(), fmt(), forward_2026(), hdr(), _line_models() (+74 more)

### Community 101 - "NBA second game market fair prices"
Cohesion: 0.07
Nodes (30): check_cells(), combine_times(), f2_cells(), f2_point(), f6a_placebo(), f6a_point(), f6a_strength(), f6d_ml_point() (+22 more)

### Community 102 - "scripts/nfl_edge_live_rush_pace.py"
Cohesion: 0.17
Nodes (26): _asof(), boot_p(), build_state(), first(), grade(), initial_last(), load_pbp(), main() (+18 more)

### Community 103 - "NBA prop projection tests"
Cohesion: 0.04
Nodes (36): minutes_cols(), rate_cols(), all_rates(), rate_features(), _art(), _committed(), _proj(), _q() (+28 more)

### Community 104 - "NFL preregistered 2026 edge study"
Cohesion: 0.09
Nodes (39): bar(), bets_frame(), bh(), binom_line(), _by_game(), cell(), fam(), first_last() (+31 more)

### Community 107 - "tests/test_prop_calibrated_decision.py"
Cohesion: 0.07
Nodes (29): apply_prop_daily_cap(), _claimed_ev(), dedupe_player_props(), _downgrade(), _bet(), _identity_cal(), _prop(), test_a_genuinely_big_edge_still_fires_after_calibration() (+21 more)

### Community 109 - "NBA fourth search derivative markets"
Cohesion: 0.07
Nodes (31): calibrated_refs(), cell_specs(), choosing(), decision_quotes(), derivative_data(), emit_f1(), emit_f4(), f1_fair() (+23 more)

### Community 110 - "tests/test_mobile_line_movement.py"
Cohesion: 0.08
Nodes (27): _fn(), _read(), _run(), test_a_cut_table_keeps_the_pick_and_says_what_it_covers(), test_a_cut_window_keeps_the_pick_row_on_the_8_row_table(), test_a_pick_made_after_the_cards_start_never_reads_since_your_pick(), test_after_the_start_the_verdict_is_not_graded(), test_an_old_snapshot_is_not_the_price_at_the_pick() (+19 more)

### Community 111 - "In-play calibration report tests"
Cohesion: 0.11
Nodes (15): test_a_peak_with_no_plateau_anywhere_is_labelled_as_one(), test_calibration_also_scores_ev_against_realised_roi(), test_calibration_is_empty_rather_than_wrong_with_nothing_settled(), test_calibration_reports_the_gap_between_claim_and_reality(), test_lockdown_statements_target_anon_and_authenticated_by_name(), test_persist_creates_its_own_table_and_is_idempotent(), test_recommender_prefers_a_plateau_to_a_higher_peak(), test_recommender_refuses_when_every_cell_loses() (+7 more)

### Community 112 - "NBA in-game luck study one"
Cohesion: 0.08
Nodes (28): attach_rates(), build(), close_totals(), decisions(), eligible(), fair_mu(), fit_w(), gate_passes() (+20 more)

### Community 117 - "NBA lineup stint derivation tests"
Cohesion: 0.07
Nodes (49): _and_one_follows(), dead_ball_rebounds(), derive_stints(), ft_info(), order_plays(), possession_ends(), _blowout_q4(), derive() (+41 more)

### Community 118 - "NBA play-by-play parsing tests"
Cohesion: 0.06
Nodes (29): _last(), match_games(), match_names(), resolve_map(), _g(), _game_recs(), _rec(), _summary() (+21 more)

### Community 119 - "tests/test_ncaaf_live_notify.py"
Cohesion: 0.05
Nodes (18): _load_write_picks(), _restore_stubbed_modules(), test_a_caller_supplied_connection_is_not_closed_by_the_write(), test_a_failing_notifier_never_breaks_pricing(), test_a_full_slate_announces_once(), test_a_live_bet_notifies_push_and_discord(), test_a_locked_lane_is_not_rewritten(), test_a_locked_lane_keeps_notifying_after_the_engine_stops_betting() (+10 more)

### Community 122 - "NCAAF quarterback team features"
Cohesion: 0.12
Nodes (24): build_qb_team_features(), load_qb_games(), merge_qb_features(), _feat(), _frame(), _games(), _qb_rows(), _qb_team() (+16 more)

### Community 124 - "NHL prop backtest and EV lab"
Cohesion: 0.14
Nodes (16): books(), card(), claimed_vs_realised(), day_interval(), line(), main(), predictions(), prices() (+8 more)

### Community 126 - "Live monitor dashboard data store"
Cohesion: 0.09
Nodes (25): meta(), ops(), snapshot(), api_rollup(), call_timeline(), calls_since(), community(), scalar() (+17 more)

### Community 127 - "NBA fifth search grid tests"
Cohesion: 0.04
Nodes (26): _blend_world(), _cell(), _grid(), _mid(), ran(), _tb_rows(), test_a_losing_band_above_the_cut_fails_too_and_a_thin_band_is_not_judged(), test_a_losing_band_below_the_cut_fails_a_cell_its_nested_neighbours_pass() (+18 more)

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

### Community 134 - "Prop ladder from books and Kalshi"
Cohesion: 0.09
Nodes (18): _ladder(), test_a_clean_ladder_is_not_reported_as_repaired(), test_a_one_sided_ladder_is_vigged_and_says_so(), test_a_quoted_strike_returns_its_own_mid(), test_a_thin_one_sided_ladder_cannot_be_anchored(), test_an_unquoted_line_interpolates_between_its_neighbours(), test_anchoring_moves_the_ladder_onto_an_honest_point(), test_anchoring_preserves_the_ordering() (+10 more)

### Community 136 - "NCAAF cross-book opener tests"
Cohesion: 0.07
Nodes (25): _minutes_apart(), build_artifact(), build_band_artifact(), _branch(), test_absent_ceiling_means_unbounded(), test_artifact_shape(), test_band_ceiling_is_enforced_in_the_scorer(), test_band_volumes_sum_to_the_single_gate_backtest() (+17 more)

### Community 137 - "NFL 2024 in-play totals grading"
Cohesion: 0.10
Nodes (44): s(), books_per_snapshot(), cell(), families(), fmt(), h1(), h1_calibration(), h2() (+36 more)

### Community 139 - "NFL 2025 in-play edge research"
Cohesion: 0.08
Nodes (42): fit_models(), summ(), async_check(), attach_games(), attach_state(), bh(), boot(), cell() (+34 more)

### Community 142 - "tests/test_health_pregame_prices_current.py"
Cohesion: 0.10
Nodes (30): _at(), _game(), _row(), _run(), test_a_broken_feed_read_is_an_error_and_rolls_back(), test_a_broken_query_is_an_error_and_rolls_back(), test_a_cancelled_fight_and_a_pulled_game_do_not_raise_the_alarm(), test_a_dead_feed_with_no_priced_game_is_a_crit() (+22 more)

### Community 145 - "NBA stats and player log ingestion"
Cohesion: 0.09
Nodes (24): backfill_nba_stats(), _box_adds_up(), _build_game_id(), _build_game_rows(), _build_player_log_rows(), _build_team_stat_rows(), _fetch_league_game_log(), ingest_nba_game_log_for_date() (+16 more)

### Community 147 - "scripts/nfl_edge_extreme_props.py"
Cohesion: 0.16
Nodes (25): actuals(), add_modes(), bar(), candidates(), cell(), decision_boards(), devig(), fit_holdout() (+17 more)

### Community 148 - "scripts/nfl_edge_settlement.py"
Cohesion: 0.14
Nodes (30): add_test(), attach(), banner(), bh(), board(), boot_draws(), cell(), choose() (+22 more)

### Community 15 - "X results and free pick posts"
Cohesion: 0.02
Nodes (63): test_a_push_only_period_does_not_invent_an_roi(), test_the_period_tweet_uses_the_daily_tally_and_states_roi(), test_the_tweet_header_says_restated(), _creds_on(), _fake_conn(), _slate(), _split(), test_a_day_with_nothing_graded_carries_no_clv_line() (+55 more)

### Community 152 - "WNBA points prop rebuild and sweep"
Cohesion: 0.08
Nodes (24): build_bulk_wnba_prop_lookups(), build_wnba_prop_training_dataset(), _dispersion(), _nb_dispersion(), _oof_predictions(), build_dataset(), fetch_injury_out_map(), fetch_pretip_lines() (+16 more)

### Community 153 - "tests/test_agents_contract.py"
Cohesion: 0.05
Nodes (20): _labelled_retired(), test_blocked_items_are_marked_so_the_agent_skips_them(), test_every_backlog_item_is_a_checkbox(), test_neither_agent_may_change_a_model_threshold(), test_the_agents_are_findable_from_the_file_every_session_reads(), test_the_backlog_does_not_promise_an_agent_that_no_longer_runs(), test_the_backlog_exists_and_has_items(), test_the_contract_documents_every_agent_by_name() (+12 more)

### Community 157 - "Live model holdout comparison"
Cohesion: 0.17
Nodes (11): bias_table(), confident_share(), load_artifact(), main(), poisson_sf(), predict(), grid(), implied() (+3 more)

### Community 159 - "WNBA results ingestor"
Cohesion: 0.04
Nodes (56): build_log_row(), _core_athlete(), _deref(), _et_date(), _fetch_core_box_players(), _fetch_core_games(), _fetch_scoreboard(), _fetch_summary() (+48 more)

### Community 16 - "NBA public betting splits ingestor"
Cohesion: 0.07
Nodes (25): active_queries(), archive_ready(), ensure_table(), et_game_date(), fetch_scoreboard(), flip_side(), _game_meta(), keep_for_poll() (+17 more)

### Community 161 - "NBA box score enrichment"
Cohesion: 0.07
Nodes (50): _blank(), box_rows(), _check_unmapped(), _create(), dnp_kind(), ensure_tables(), fetch_advanced(), fill_missing_game_logs() (+42 more)

### Community 162 - "NFL quarterback and wind edge study"
Cohesion: 0.10
Nodes (42): band_table(), bh(), build_priced(), decisions_2026(), decisions_hist(), era5_hourly(), fc_at_decision(), fetch_2026() (+34 more)

### Community 163 - "NBA derivative market lab"
Cohesion: 0.09
Nodes (35): add_team(), am_to_dec(), bars_for(), bet_list(), blind(), boot_ci(), build_line_rows(), build_outcomes() (+27 more)

### Community 168 - "Mobile source logic tests via node"
Cohesion: 0.05
Nodes (31): test_a_published_void_keeps_track_and_betslip(), test_a_tracked_void_reads_not_graded_and_detail_closes_when_over(), test_the_app_predicate_matches(), test_today_et_ignores_the_container_timezone(), _read(), _run(), test_a_stale_card_offers_no_bet(), test_a_stale_card_says_why_and_speaks_the_locked_price() (+23 more)

### Community 169 - "NBA halftime in-game research"
Cohesion: 0.08
Nodes (25): write_cells(), add_features(), attach_close(), build_halves(), centre(), day_ci(), decision_games(), decision_quotes() (+17 more)

### Community 170 - "NBA game model luck feature tests"
Cohesion: 0.07
Nodes (22): _against_bet(), _f6c_inputs(), _games_for_standings(), _gs(), _market_pricing(), _one_game_data(), _season(), _standing() (+14 more)

### Community 172 - "MLB stats and pitcher ingestion"
Cohesion: 0.04
Nodes (36): _fetch_bat_hands(), _fetch_lineup(), ingest_lineups_for_date(), _already_loaded(), backfill_pbp(), _fetch_pbp(), fill_play_times(), _game_id_from_schedule() (+28 more)

### Community 173 - "tests/test_decide_on_calibrated.py"
Cohesion: 0.06
Nodes (19): _pick(), _pick_at(), test_a_calibrated_cut_is_paired_with_a_calibrated_decision(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(), test_a_genuinely_big_edge_still_fires_after_calibration(), test_a_hot_model_no_longer_fires_the_marginal_bet(), test_a_model_on_a_calibrated_cut_is_not_paused(), test_a_paused_model_never_fires_regardless() (+11 more)

### Community 175 - "tests/test_dk_direct_feed.py"
Cohesion: 0.19
Nodes (13): _row_for(), _seen_key(), _rec(), test_a_line_move_is_a_new_quote(), test_a_market_we_do_not_understand_is_dropped_not_guessed(), test_a_price_move_is_a_new_quote(), test_a_priced_market_with_no_line_is_dropped(), test_every_row_is_tagged_dk_direct() (+5 more)

### Community 176 - "NBA prop projection lab"
Cohesion: 0.09
Nodes (47): implied(), bars(), bh_read(), blind(), boot(), by(), cal_ab(), candidates() (+39 more)

### Community 180 - "Mobile live picks segment tests"
Cohesion: 0.06
Nodes (28): _read(), test_a_sport_switch_cannot_report_a_game_finishing(), test_all_three_segments_are_unconditional(), test_live_is_not_a_bottom_tab(), test_live_is_not_in_the_tab_param_list(), test_no_app_root_component_reaches_a_focus_aware_hook(), imports_of(), strip_comments() (+20 more)

### Community 181 - "NBA in-game data staleness gate"
Cohesion: 0.04
Nodes (56): attach_pinnacle(), box_checks(), build(), drop_wild_wallclocks(), espn_map(), foul_flags(), is_heave(), keep_in_play() (+48 more)

### Community 182 - "tests/test_model_artifacts_load.py"
Cohesion: 0.07
Nodes (19): _git(), _gitignore_keep_pkls(), _ignored(), _manifest_keep_pkls(), _newest_per_model(), test_a_path_that_is_not_ignored_is_not_reported(), test_a_superseded_timestamped_pkl_is_ignored(), test_an_ignored_path_comes_back_byte_identical() (+11 more)

### Community 183 - "Mobile team and player detail tests"
Cohesion: 0.03
Nodes (67): _book_of(), part_a_card(), part_b(), _table(), test_every_revoke_names_the_roles_rather_than_public(), test_odds_keeps_select_for_the_app(), test_the_two_rls_off_tables_lose_everything(), test_the_function_revoke_names_public_as_well_as_the_roles() (+59 more)

### Community 185 - "scripts/game_line_market_sweep.py"
Cohesion: 0.08
Nodes (22): _by_month(), collect_picks(), devig(), _gap_seconds(), grade(), implied(), iter_months(), load() (+14 more)

### Community 187 - "Push notification deep link tests"
Cohesion: 0.09
Nodes (20): _code(), _py_version(), _read(), test_a_single_pick_deep_links_and_a_batch_does_not(), test_an_unreadable_payload_routes_nowhere_rather_than_guessing(), test_both_halves_pin_the_same_payload_version(), test_every_expo_message_carries_a_data_payload(), test_every_summary_producer_can_deep_link_a_single_pick() (+12 more)

### Community 188 - "tests/test_pass_instrumentation.py"
Cohesion: 0.06
Nodes (11): test_a_dead_database_does_not_fail_the_step(), test_a_raised_failure_still_records_the_exception(), test_a_step_that_raises_is_still_TIMED(), test_a_step_that_raises_still_raises(), boom(), test_a_step_that_returns_false_records_a_REASON(), test_a_successful_step_records_a_duration(), test_every_step_name_in_the_dispatch_table_is_reachable() (+3 more)

### Community 189 - "Odds prune opener and close tests"
Cohesion: 0.05
Nodes (22): ncaaf_line_bookmaker(), _prop_reference_books(), protected_for(), _thin_book_filter(), _unprotected(), test_prune_never_touches_cfbd_archive_lines(), test_the_bookmaker_these_rows_use_survives_the_daily_prune(), test_the_prune_protects_every_ladder_source_by_its_writer_s_own_name() (+14 more)

### Community 190 - "tests/test_db_adapt_sql.py"
Cohesion: 0.11
Nodes (21): _adapt_sql(), _named(), test_a_block_comment_is_skipped_too(), test_a_colon_word_inside_a_comment_is_not_a_placeholder(), test_a_dash_dash_inside_a_literal_is_data_not_a_comment(), test_a_line_comment_ends_at_the_newline(), test_a_real_param_after_a_literal_still_converts(), test_an_apostrophe_in_a_comment_does_not_swallow_a_later_literal() (+13 more)

### Community 191 - "Eggz channel pick parsing and grading"
Cohesion: 0.05
Nodes (19): _grade_conn(), test_a_final_moneyline_uses_the_settler_result(), test_a_line_that_is_not_a_pick_is_kept_for_review(), test_a_missing_price_stays_missing_and_the_stake_defaults_to_one(), test_a_non_mlb_prop_on_a_final_is_marked_for_review(), test_a_post_after_the_start_is_not_a_bet(), test_a_side_a_spread_a_total_and_a_prop_parse(), test_a_total_without_a_game_is_unmatched() (+11 more)

### Community 195 - "tests/test_mobile_contrast_tokens.py"
Cohesion: 0.12
Nodes (30): _code_lines(), _ionicon_colors(), _lum(), _over(), _ratio(), _read(), _rgb(), test_badge_glyph_tracks_dynamic_type() (+22 more)

### Community 196 - "Monitoring probes and HTTP timeouts"
Cohesion: 0.02
Nodes (55): _fmt_et_time(), get_conn(), query(), configured(), guild_stats(), main(), _drain(), _enqueue() (+47 more)

### Community 198 - "NBA game four part one tests"
Cohesion: 0.06
Nodes (32): _base(), _fair(), _ladder_quotes(), _offered(), _offers(), _period_games(), _rows(), _rung() (+24 more)

### Community 201 - "NBA second game line move tests"
Cohesion: 0.09
Nodes (28): _priced_season(), _q(), _sched(), _season_games(), _signal(), test_a_fetch_after_T_never_reaches_the_move(), test_a_game_first_quoted_after_T_has_no_model_number(), test_a_game_the_rule_gives_no_number_is_outside_the_cells_population() (+20 more)

### Community 204 - "NBA team total luck replay build"
Cohesion: 0.09
Nodes (16): load_artifact(), bucket_counts(), build(), cell_bets(), main(), store(), tt_residuals(), lab_bets() (+8 more)

### Community 207 - "NFL in-play prop flow anchoring tests"
Cohesion: 0.06
Nodes (22): grade_real(), naive_line(), _anchor_frame(), _long(), test_a_degenerate_line_is_dropped(), test_a_push_on_a_whole_number_line_is_not_a_loss(), test_accrual_is_as_of_the_mark_not_the_last_involvement(), test_accrual_is_monotone_as_the_game_progresses() (+14 more)

### Community 208 - "WNBA prop context features"
Cohesion: 0.11
Nodes (18): _build_player_row(), build_wnba_prop_scoring_rows(), _context_features_for(), _opp_team_stat(), _recent_starter(), _rest_days(), _rolling_avg(), _season_avg() (+10 more)

### Community 212 - "NBA second game verdict"
Cohesion: 0.11
Nodes (17): cell_rows(), main(), _plain(), axes_of(), bands_ok(), bar9(), cell_key(), _floats() (+9 more)

### Community 214 - "Probability calibration fitting and sweep"
Cohesion: 0.07
Nodes (29): apply_calibration(), demote(), ensure_schema(), _era_start(), fetch_graded(), fit_model(), fit_offset(), fit_platt() (+21 more)

### Community 217 - "NCAAF in-play pricing engine"
Cohesion: 0.06
Nodes (22): correct_for_pregame(), _load_pregame_calibration(), pregame_dog_points(), _real_artifact(), test_a_big_dog_is_marked_down_hard(), test_a_corrupt_artifact_leaves_the_probability_alone(), test_a_favourite_is_marked_up(), test_a_missing_artifact_leaves_the_probability_alone() (+14 more)

### Community 219 - "tests/test_nfl_live_leader_state.py"
Cohesion: 0.14
Nodes (19): situation(), status(), test_a_conversion_try_is_skipped(), test_a_previous_quarters_play_is_not_the_state(), test_a_timeout_is_skipped_for_the_play_before_it(), test_after_a_scoring_play_nothing_is_evaluated(), test_after_the_kickoff_lands_the_receiver_has_the_ball(), test_an_ordinary_snap_is_evaluable_with_the_training_inputs() (+11 more)

### Community 221 - "tests/test_ncaaf_qb_ingestor.py"
Cohesion: 0.11
Nodes (24): _athlete_stats(), _comp_att(), parse_qb_game_stats(), _split_ratio(), test_split_ratio(), _parse(), _payload(), _team() (+16 more)

### Community 224 - "DraftKings direct feed freshness probes"
Cohesion: 0.09
Nodes (18): main(), probe_book(), verdict(), egress_ip(), _probe_once(), _proxies(), reachability(), _session() (+10 more)

### Community 236 - "Ops alert posting and watchdogs"
Cohesion: 0.08
Nodes (16): _announce(), _announce_and_ledger(), _post(), _alert(), _read_state(), _state_path(), _announce(), _announce() (+8 more)

### Community 237 - "House juice price floor tests"
Cohesion: 0.11
Nodes (12): min_odds_for(), _blocked_by_min_odds(), test_a_pick_with_no_price_is_never_blocked_by_the_floor(), test_an_explicit_floor_wins_in_BOTH_directions(), test_every_registered_model_has_an_effective_floor(), test_ordinary_prices_still_fire(), test_the_default_is_overridable_without_a_code_change(), test_the_measured_blast_radius_is_recorded() (+4 more)

### Community 240 - "tests/test_ncaaf_game_identity.py"
Cohesion: 0.12
Nodes (16): _add(), _conn(), _identity_sql(), _run(), test_a_clean_slate_reports_nothing(), test_a_non_fbs_fixture_is_not_reported(), test_a_phantom_opponent_is_detected_too(), test_a_real_doubleheader_is_not_a_duplicate() (+8 more)

### Community 241 - "NBA second game market tests"
Cohesion: 0.10
Nodes (27): _close_frames(), _data(), _f2_games(), _f6a_data(), _f6d_total_data(), _game(), _pe(), _q() (+19 more)

### Community 242 - "NFL edge luck gap study"
Cohesion: 0.10
Nodes (30): add_windows(), add_windows_fast(), bh(), binom_p(), board(), boot(), cell(), fit_points() (+22 more)

### Community 247 - "tests/test_dk_freshness_parse.py"
Cohesion: 0.19
Nodes (15): _american(), parse_dk_payload(), _store(), _payload(), test_a_half_priced_market_is_dropped_rather_than_half_recorded(), test_an_event_with_no_markets_yields_nothing_rather_than_raising(), test_decimal_is_the_fallback_when_the_display_string_is_unusable(), test_live_markets_only() (+7 more)

### Community 25 - "NBA game model research harness"
Cohesion: 0.04
Nodes (64): attach_fetch(), blind_by_real_side(), blind_pool(), blind_side(), boot(), cell_report(), cents(), check() (+56 more)

### Community 252 - "Discord bet price bound wording"
Cohesion: 0.12
Nodes (13): _dec(), test_a_field_without_a_bound_renders_without_the_clause(), test_a_model_with_no_own_ev_floor_is_bound_by_the_global_one(), test_a_price_floor_can_be_the_binding_gate(), test_a_rounded_bound_still_clears_the_bound_it_came_from(), test_even_money_is_plus_one_hundred(), test_no_bound_from_junk_rather_than_a_guess(), test_no_bound_when_the_edge_floor_is_unreachable() (+5 more)

### Community 254 - "Kalshi prop ladder recording tests"
Cohesion: 0.07
Nodes (8): test_a_kalshi_outage_cannot_break_the_pass(), test_a_run_is_idempotent_within_its_snapshot(), test_one_snapshot_timestamp_for_the_whole_run(), test_the_recorder_is_scheduled_on_the_pipeline_role(), test_the_recorder_keeps_raw_prices_not_a_filtered_ladder(), test_the_recorder_walks_every_mapped_series(), _loose_summary(), s()

### Community 255 - "UFC results download caching"
Cohesion: 0.15
Nodes (9): _cached_etag(), _etag_cache_path(), _store_etag(), test_a_mounted_volume_is_preferred_over_tmp(), test_a_round_trip_actually_persists(), test_a_volume_path_that_does_not_exist_falls_back(), test_an_empty_etag_is_never_stored(), test_an_explicit_override_wins() (+1 more)

### Community 260 - "College football live ESPN feed"
Cohesion: 0.17
Nodes (16): check_feed_assumptions(), _competitors(), _count_plays(), _dig(), extract_live_events(), extract_summary_state(), _int(), _num() (+8 more)

### Community 262 - "UFC fight feature builder"
Cohesion: 0.06
Nodes (34): _age_years(), _assemble_ufc_features(), _blk_career_stats(), build_ufc_features_from_bulk(), _bulk_fighter_id(), career_stats(), compute_ufc_target(), infer_five_rounds() (+26 more)

### Community 263 - "NFL prop walk-forward and regrading"
Cohesion: 0.18
Nodes (17): build_nfl_prop_training_dataset(), main(), yes_prices(), implied(), lines_for(), main(), norm(), profit() (+9 more)

### Community 266 - "NBA quarter game model tests"
Cohesion: 0.11
Nodes (29): _data(), _game(), _ladder(), _no_real_load(), _point(), _pricing_world(), _q(), _row() (+21 more)

### Community 267 - "NBA second game luck study"
Cohesion: 0.13
Nodes (16): f4_signal(), f6c_offers(), f6c_signal(), game_situations(), _load_box(), main(), market_offers(), placebo_frames() (+8 more)

### Community 268 - "NHL skater prop pricing lab"
Cohesion: 0.19
Nodes (12): _ew(), fit_score(), main(), opponent_allowed(), coherent(), fold(), load_prices(), main() (+4 more)

### Community 271 - "Line CLV sign and orientation tests"
Cohesion: 0.06
Nodes (9): test_runner_captures_stdout_from_the_script_main(), _load(), test_a_line_that_held_is_exactly_zero_not_none(), test_a_missing_close_is_not_a_zero(), test_a_side_that_cannot_be_oriented_returns_none_rather_than_guessing(), test_the_home_and_away_sides_are_exact_mirrors(), test_the_prop_market_flag_wins_over_the_market_string(), test_the_signs_are_the_negation_of_the_apps_entry_frame() (+1 more)

### Community 275 - "NBA game harness tests"
Cohesion: 0.09
Nodes (23): _cov_data(), _fetches(), _games(), _offers(), _q(), _stale_cache(), test_a_cell_reports_its_pooled_walk_forward_and_writes_its_bets(), test_a_graded_load_refuses_a_season_the_cache_does_not_price() (+15 more)

### Community 276 - "UFC fight results scraper"
Cohesion: 0.12
Nodes (14): backfill_ufc_stats(), _build_ufc_game_id(), _fetch_event(), _fetch_event_list(), _fetch_fight(), _fetch_fighter(), _get(), _home_win_for_row() (+6 more)

### Community 280 - "NFL in-play flow slice backtest"
Cohesion: 0.13
Nodes (17): _clustered_ci(), main(), _qcut(), _rows_for(), slice_table(), verdict(), _frame(), _table() (+9 more)

### Community 283 - "NBA game projection tests"
Cohesion: 0.18
Nodes (22): _box(), _games(), _inj(), _rapm_inputs(), _segment_rows(), _state(), test_a_back_to_back_is_read_from_the_schedule(), test_a_game_gets_no_projection_while_a_previous_date_game_could_still_be_running() (+14 more)

### Community 287 - "Model calibration check tests"
Cohesion: 0.09
Nodes (12): _calibration_sql(), test_a_flagged_model_is_named_eligible_or_not(), test_a_thin_model_is_still_excluded_rather_than_accused(), test_eligibility_notes_must_not_sink_the_gap_check(), test_eligibility_notes_parse_the_payload_verdicts(), test_it_grades_the_calibrated_probability_not_the_raw_one(), test_it_joins_picks_to_reach_the_calibrated_column(), test_the_check_has_a_skip_budget_that_survives_a_regime_change() (+4 more)

### Community 29 - "NCAAF college data ingestor"
Cohesion: 0.06
Nodes (37): backfill_ncaaf_lines(), backfill_ncaaf_players(), backfill_ncaaf_qb(), _existing_ncaaf_ids(), _fold(), _get(), ingest_ncaaf_game_log(), ingest_ncaaf_games() (+29 more)

### Community 291 - "NFL prop market card lead ceiling"
Cohesion: 0.14
Nodes (7): captured(), _games(), test_a_game_beyond_the_ceiling_is_never_priced(), test_a_slate_entirely_out_of_range_says_WHY(), test_buying_the_board_and_betting_it_are_different_numbers(), test_the_boundary_is_inclusive_at_the_ceiling(), test_the_started_game_floor_still_holds()

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

### Community 306 - "NFL in-play flow pseudo CLV tests"
Cohesion: 0.13
Nodes (21): match_to_flow(), pseudo_clv(), _bet(), _preds(), _quote(), _quotes(), synthetic(), test_a_far_away_kickoff_is_a_different_season() (+13 more)

### Community 315 - "NFL in-play remaining-yards engine training"
Cohesion: 0.13
Nodes (14): _cluster_bootstrap(), evaluate(), main(), report(), fit(), load_states(), main(), walk_forward_oos() (+6 more)

### Community 316 - "Threshold cut sweeps and EV replays"
Cohesion: 0.04
Nodes (54): _in_graded_matview(), _is_live_lane(), analyse(), split(), _basis(), _cut(), fetch(), main() (+46 more)

### Community 317 - "Scratch Postgres line state tests"
Cohesion: 0.06
Nodes (35): main(), can_scratch(), env_dsn(), _free_port(), pg_bin(), scratch_cluster(), as_app(), db() (+27 more)

### Community 318 - "tests/test_live_record_start_views.py"
Cohesion: 0.09
Nodes (12): _body(), _code(), test_both_published_views_carry_the_live_date_gate(), test_it_runs_after_the_migration_that_used_to_own_the_daily_view(), test_migration_is_one_statement(), test_migration_is_registered_with_the_worker_runner(), test_neither_view_reads_the_sweep_universe(), test_no_ddl_outside_the_guarded_branches() (+4 more)

### Community 319 - "UFC historical CSV loader"
Cohesion: 0.12
Nodes (19): backfill_ufc_csv(), build_events(), build_fighter_index(), _heal_window_lo(), ingest_ufc_results_for_date_csv(), load_fighter_profiles_from_csv(), _mirror_etag(), _read_csv() (+11 more)

### Community 326 - "Odds pruning keeps closing lines"
Cohesion: 0.12
Nodes (10): _prune(), _quotes(), test_both_delete_tiers_spare_the_keep_set(), test_each_statement_reads_its_proposition_once_with_no_anti_join(), test_the_close_is_never_an_in_play_price(), test_the_cost_is_recorded_as_a_measurement_not_a_guess(), test_the_opener_is_still_selected_by_the_oldest(), test_the_protected_books_are_untouched_by_this_change() (+2 more)

### Community 327 - "NHL prop odds fetch gate"
Cohesion: 0.07
Nodes (22): due(), _book(), test_a_200_on_both_calls_merges_the_alternate_lines(), fake_fetch(), test_a_game_first_priced_inside_the_final_window_gets_nothing_more(), test_a_game_first_priced_inside_the_window_gets_one_decision_snapshot(), test_a_game_with_nothing_stored_is_owed_its_open(), test_a_moved_featured_line_keeps_the_old_number_under_the_alternate_key() (+14 more)

### Community 328 - "NFL Kalshi edge search"
Cohesion: 0.17
Nodes (20): align_check(), bh(), bins(), boot(), cell(), coverage(), cp_roi(), fee() (+12 more)

### Community 329 - "nfl/models/opener_spread.py"
Cohesion: 0.14
Nodes (11): age_tag(), american_to_prob(), _bettable_books(), clean_board(), edge_tier(), evaluate_board(), held_minutes(), model_prob_for_dev() (+3 more)

### Community 332 - "MLB live slate midnight discovery tests"
Cohesion: 0.07
Nodes (14): _at(), test_both_live_loops_share_one_definition_of_the_slate(), test_by_daytime_yesterday_is_dropped(), test_discovery_asks_statsapi_about_every_date_it_is_given(), fake_schedule(), test_discovery_still_accepts_a_bare_string(), test_just_after_midnight_still_asks_about_yesterday(), test_just_before_midnight_asks_about_today_only() (+6 more)

### Community 333 - "tests/test_nfl_wind_fire_window.py"
Cohesion: 0.07
Nodes (18): _retractable_slate(), _slate(), test_a_blank_roof_at_a_NON_retractable_venue_is_unaffected(), test_a_closed_roof_is_still_indoor(), test_a_retractable_venue_with_an_unknown_roof_does_not_fire(), test_a_waiting_game_is_not_reported_as_a_collapsed_premise(), test_a_waiting_row_keeps_its_line_price_and_edge(), test_every_blank_roof_row_is_a_retractable_venue() (+10 more)

### Community 335 - "tests/test_public_betting_ingestor.py"
Cohesion: 0.15
Nodes (18): parse_public_betting(), _pct(), probe(), _select_book(), _make_game(), test_parse_emits_six_rows(), test_parse_game_id_and_sides(), test_parse_marks_source_and_snapshot() (+10 more)

### Community 336 - "Basketball player positions ingestor"
Cohesion: 0.04
Nodes (46): _athlete_room(), _basketball(), basketball_group(), _cached_unmatched_ids(), _espn(), _fresh_source_ids(), _get_json(), ingest_player_positions() (+38 more)

### Community 339 - "tests/test_service_role_split.py"
Cohesion: 0.15
Nodes (11): _all_job_ids(), _sched(), test_an_unknown_role_runs_everything(), test_every_add_job_call_passes_an_id(), test_every_job_is_owned_by_exactly_one_role(), test_the_always_on_jobs_run_on_every_role(), test_the_default_preserves_the_single_container(), test_the_nfl_worker_stays_with_the_volume() (+3 more)

### Community 34 - "Prop ladder and NBA derivative tests"
Cohesion: 0.06
Nodes (34): _identity_maps(), _platform_gates_off(), _statements(), test_columns_and_values_line_up(), test_the_scorer_pick_insert_is_actually_covered(), _bets(), _games(), _graded_games() (+26 more)

### Community 343 - "Mobile tracked performance record checks"
Cohesion: 0.10
Nodes (18): dup, empty, half, l50, loss, noAction, open1, open2 (+10 more)

### Community 346 - "NFL research edge data cache"
Cohesion: 0.22
Nodes (14): _conn(), copy_main_local(), _df(), _games_2026(), log(), main(), nflverse_misc(), nflverse_pbp() (+6 more)

### Community 347 - "Mobile sport filter persistence tests"
Cohesion: 0.14
Nodes (10): _load_body(), _sports(), _src(), test_a_visit_scoped_sport_change_does_not_persist(), test_a_writer_landing_during_the_hydrate_is_not_overwritten(), test_every_sport_survives_a_cold_start(), test_no_retired_sport_is_a_selectable_chip(), test_no_second_hand_written_sport_list_in_the_hook() (+2 more)

### Community 348 - "UFC twin fight id scoring tests"
Cohesion: 0.23
Nodes (7): _ago(), _score_card(), test_a_bet_on_either_id_locks_the_model_for_both(), test_a_never_priced_id_is_not_scored_beside_its_priced_twin(), test_the_chosen_id_still_borrows_a_market_only_its_twin_carries(), test_two_current_ids_of_one_fight_score_only_the_newer(), _ufc_game()

### Community 35 - "NBA game projection model tests"
Cohesion: 0.07
Nodes (16): _cons(), _dist(), _neutral(), _segments(), test_f1_is_priced_through_the_projections_own_error_not_the_markets(), test_f1b_does_not_score_a_books_number_off_the_consensus(), test_f1b_strength_is_the_predicted_move_in_the_sides_favour(), test_the_consensus_number_is_pinnacles_else_the_deciding_books_median() (+8 more)

### Community 353 - "NFL in-play flow snapshot validation"
Cohesion: 0.10
Nodes (15): bias_table(), main(), apply_anchor(), attach_ids(), _game_marks(), main(), name_index(), resolve_game_ids() (+7 more)

### Community 354 - "Bring your own model game facts"
Cohesion: 0.06
Nodes (44): assemble_game(), grade_ats(), grade_ml(), grade_total(), is_primetime(), lead_hours(), line_at_start(), _num() (+36 more)

### Community 356 - "NCAAF in-play market pricing"
Cohesion: 0.12
Nodes (15): american_to_prob(), anchor_to_market(), devig_power(), margin_pmf(), _over_under(), price_moneyline(), price_quarter(), price_second_half() (+7 more)

### Community 358 - "NBA period map pricing tests"
Cohesion: 0.06
Nodes (33): _game(), _games3(), _gaps(), _ladder_quotes(), _luck_games(), _maps(), _odds_row(), _offered() (+25 more)

### Community 359 - "Prop box score cooled refill"
Cohesion: 0.13
Nodes (22): _call_fill(), _cooled(), _day(), _default_mlb(), _default_nfl(), _default_wnba(), _drop_logged(), _fill_cooled() (+14 more)

### Community 36 - "NCAAF CFBD ingestor tests"
Cohesion: 0.03
Nodes (68): build_ncaaf_game_id(), _day_before(), eastern_game_date(), _local_aggregates(), ncaaf_season_for_date(), ncaaf_slug(), parse_games(), parse_lines() (+60 more)

### Community 360 - "Mobile screen source wiring tests"
Cohesion: 0.07
Nodes (20): _bn_body(), _sql_groups(), test_a_failed_position_read_is_said_not_hidden(), test_a_failed_read_is_not_held_on_the_spinner(), test_every_mlb_stat_chip_has_a_branch(), test_every_nfl_stat_chip_has_a_branch(), test_every_roster_sport_chip_has_a_branch(), test_mlb_lineup_buckets_agree_between_app_and_server() (+12 more)

### Community 366 - "Kalshi game market recorder"
Cohesion: 0.09
Nodes (8): run_kalshi_game_record(), test_a_kalshi_outage_cannot_break_the_pass(), test_event_code_is_shared_across_series(), test_event_date_is_searched_not_anchored(), test_kalshi_labels_expand_st_and_use_the_explicit_map(), test_resolution_runs_after_every_snapshot(), test_the_recorder_is_scheduled_on_the_pipeline_role(), test_the_recorder_keeps_raw_contracts()

### Community 369 - "CLV price taken app parity tests"
Cohesion: 0.13
Nodes (17): _app(), _clv_card(), _server(), test_a_label_book_nfl_pick_compares_its_line_with_that_book(), test_a_recorded_book_differs_from_the_derived_one(), test_the_app_prefers_the_recorded_book_at_the_derived_price(), test_the_app_prices_every_row_as_the_server_grades_it(), test_the_card_prints_the_price_taken_not_draftkings() (+9 more)

### Community 370 - "UFC results scraper tests"
Cohesion: 0.09
Nodes (22): normalize_method(), _resolve_game_rows(), slugify_fighter(), _resolve(), test_a_misspelled_fighter_is_scored_for_the_side_they_fought_on(), test_alias_makes_both_sources_agree(), test_aliases_do_not_touch_unmapped_names(), test_confirmed_aliases_resolve_to_ufcstats_slug() (+14 more)

### Community 371 - "NCAAF totals probability regression tests"
Cohesion: 0.10
Nodes (14): total_over_prob(), test_artifact_kind_is_routed_by_the_scorer(), test_asymmetry_is_real_and_would_have_bitten(), test_extremes_are_clamped_away_from_certainty(), test_model_above_the_line_favours_the_over(), test_model_below_the_line_favours_the_under(), test_no_dk_total_means_skip_not_prob_only(), test_no_residuals_returns_one_half_not_a_confident_bet() (+6 more)

### Community 373 - "Mobile live game status checks"
Cohesion: 0.07
Nodes (22): deadPoller, delayed, finalNoScore, future, golfDay2, live, live1, liveFinal (+14 more)

### Community 375 - "Refresh pass step ordering tests"
Cohesion: 0.10
Nodes (13): _order(), test_a_parallel_step_that_fails_is_still_recorded(), test_no_sequential_step_runs_while_a_parallel_group_is_open(), test_opening_signals_follows_every_scorer(), test_parlay_follows_opening_signals(), test_scoring_follows_every_ingest(), test_settle_follows_every_results_ingest(), test_sync_thresholds_follows_migrations_and_precedes_scoring() (+5 more)

### Community 379 - "NHL totals market bet finder"
Cohesion: 0.17
Nodes (11): _fetch_ts(), find_bets(), _q(), test_a_different_number_is_not_the_same_bet(), test_a_soft_quote_pairs_only_with_pinnacle_from_the_same_fetch(), test_decided_on_its_own_probability(), test_one_bet_a_game_best_ev_ties_by_book_order(), test_pinnacle_withdrawn_means_no_bet_this_pass() (+3 more)

### Community 381 - "Health check signal deliverability"
Cohesion: 0.11
Nodes (10): test_a_game_date_inside_the_window_counts(), test_a_lookahead_commence_counts_even_when_game_date_is_outside(), test_a_signal_locked_after_first_pitch_was_never_deliverable(), test_a_signal_locked_before_first_pitch_still_counts(), test_a_signal_locked_exactly_at_first_pitch_counts(), test_a_started_game_outside_the_window_does_not_count(), test_it_fails_toward_noticing(), test_mixed_timestamp_shapes_are_parsed_not_string_compared() (+2 more)

### Community 382 - "Mobile bankroll screen checks"
Cohesion: 0.19
Nodes (14): _read(), test_copy_is_word_for_word(), test_display_only_nothing_sized(), test_error_text_uses_the_text_safe_red(), test_explainer_no_longer_denies_a_bankroll(), test_exposure_card_hook_and_banner_stay_removed(), test_keyboard_never_covers_the_field(), test_locale_separators_decide_the_decimal() (+6 more)

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

### Community 392 - "Node runner for mobile tests"
Cohesion: 0.04
Nodes (35): node_exe(), node_strips_types(), _node_strips_types(), _node_strips_types(), _read(), _run(), test_audited_targets(), test_betslip_bar_inset_wiring() (+27 more)

### Community 396 - "NCAAF steam lag study"
Cohesion: 0.27
Nodes (9): attach_scores(), build_events(), fmt(), grade(), lines_at_pulls(), load(), main(), summarise() (+1 more)

### Community 398 - "Mobile bankroll settings card"
Cohesion: 0.18
Nodes (20): fieldFlow(), inv(), bankrollDraft(), bankrollFieldText(), canonical(), checkBankroll(), commitBankrollText(), editBankrollInput() (+12 more)

### Community 399 - "NFL live leader model tests"
Cohesion: 0.09
Nodes (21): h1_frame(), fit_wp(), leader_view(), logit_irls(), wp_design(), wp_lookup(), art(), _d() (+13 more)

### Community 400 - "Mobile paused catalog tests"
Cohesion: 0.16
Nodes (11): _block(), _read(), test_paused_picks_reach_the_all_board_only_and_labelled(), test_stats_add_pick_refuses_a_paused_model(), test_the_behavioural_checks_pass(), test_the_bet_type_picker_filters_paused_models(), test_the_custom_model_picker_is_three_bet_types(), test_the_models_list_filters_paused_models() (+3 more)

### Community 401 - "Free pick cheaper book naming"
Cohesion: 0.10
Nodes (13): _pick(), test_a_pick_with_no_alternative_falls_back_to_draftkings(), test_every_offerable_book_has_a_human_name_on_both_surfaces(), test_the_free_card_names_the_cheaper_book(), test_the_free_card_query_reads_the_columns_it_renders(), test_the_good_to_clause_is_dropped_not_truncated_when_it_will_not_fit(), test_the_tweet_names_the_cheaper_book(), test_the_tweet_never_publishes_a_worse_price_than_draftkings() (+5 more)

### Community 402 - "NCAAF board visibility tests"
Cohesion: 0.15
Nodes (11): _line(), _patch(), test_a_fired_pick_clears_its_own_probability_floor(), test_books_agreeing_is_a_no_signal_row(), test_dk_off_its_opener_is_a_no_signal_row(), test_missing_sharp_opener_is_a_no_signal_row(), test_no_current_dk_line_writes_nothing(), test_the_band_ceiling_writes_nothing() (+3 more)

### Community 403 - "MLB play-by-play ingestor"
Cohesion: 0.16
Nodes (15): _bases_after_from_matchup(), parse_game_plays(), parse_play(), _split_event_type(), test_bases_empty_matchup(), test_bases_with_runners(), test_parse_game_plays_empty_feed(), test_parse_game_plays_walks_full_inning() (+7 more)

### Community 404 - "tests/test_promote_calibration_job.py"
Cohesion: 0.11
Nodes (3): test_a_refused_model_rolls_back_and_raises(), test_a_successful_promote_commits(), _job_promote_calibration()

### Community 406 - "tests/test_cfbd_snapshot_leakage.py"
Cohesion: 0.16
Nodes (9): _completed_before(), _ohio_state_2024(), test_boundary_is_strict(), test_datetime_like_values_are_handled(), test_empty_input(), test_end_of_regular_season_snapshot_excludes_playoffs(), test_missing_or_malformed_dates_are_dropped_not_admitted(), test_postseason_excluded_from_early_season_snapshot() (+1 more)

### Community 408 - "NFL wind forecast stability tests"
Cohesion: 0.12
Nodes (15): _series(), _slate(), test_a_covered_window_at_or_above_11_fires_and_records_the_minimum(), test_a_covered_window_whose_minimum_is_under_11_does_not_fire(), test_a_database_miss_returns_only_the_current_reading(), test_a_dip_inside_the_window_is_the_number_the_check_sees(), test_a_dip_older_than_the_lookback_does_not_count(), test_a_single_issued_forecast_still_fires() (+7 more)

### Community 409 - "In-play calibration analysis job"
Cohesion: 0.18
Nodes (11): test_expected_value_matches_the_hand_calculation(), test_expected_value_refuses_a_missing_or_zero_price(), analyse(), decimal_odds(), expected_value(), _fetch(), _fmt(), main() (+3 more)

### Community 411 - "NCAAF totals weather and input drift"
Cohesion: 0.19
Nodes (9): build_frames(), live_rows(), load_artifact(), main(), arm_frame(), load_issued(), main(), run_arm() (+1 more)

### Community 412 - "NCAAF outcome edge scan"
Cohesion: 0.19
Nodes (12): _cell(), ecdf_prob_positive(), implied(), load_ml_prices(), main(), payout(), predict_all(), _print_cells() (+4 more)

### Community 413 - "NFL prop threshold window tests"
Cohesion: 0.11
Nodes (8): test_live_webhook_map_reads_the_per_sport_env_vars(), cfg(), test_no_nfl_prop_market_is_back_on_the_uniform_placeholder(), test_one_bad_date_does_not_cost_the_others(), test_the_prop_window_has_exactly_one_declaration(), test_the_scorer_step_covers_the_whole_window_not_one_date(), fake(), test_the_three_threshold_dicts_agree_for_every_nfl_prop_market()

### Community 414 - "tests/test_nhl_research_job.py"
Cohesion: 0.15
Nodes (11): test_a_dump_argument_is_refused(), test_a_model_must_be_a_real_spec(), test_a_season_must_be_a_priced_one(), test_an_unknown_script_is_refused(), test_an_unknown_top_level_key_is_refused(), test_every_runnable_module_has_a_main(), test_every_runnable_module_writes_no_database_row(), test_the_artifact_grade_names_the_rule_production_runs() (+3 more)

### Community 415 - "tests/test_settlement_timing.py"
Cohesion: 0.14
Nodes (9): test_capture_clv_requires_the_game_to_have_started(), test_future_kickoffs_are_not_treated_as_started(), test_game_log_skips_per_game_not_per_date(), test_mirror_unchanged_is_conservative_when_it_cannot_tell(), test_started_games_are_recognised_in_every_stored_format(), test_ufc_poll_uses_the_etag_gate_and_the_daily_run_does_not(), test_unparseable_timestamps_yield_none_rather_than_a_guess(), test_z_and_offset_forms_are_the_same_instant_but_not_the_same_string() (+1 more)

### Community 416 - "NBA schedule rest and travel features"
Cohesion: 0.12
Nodes (10): _counted_schedule(), from_cache(), game_schedule_features(), haversine_miles(), home_bases(), _offsets(), previous_game_load(), team_schedule_features() (+2 more)

### Community 418 - "Push delivery ticket handling tests"
Cohesion: 0.22
Nodes (10): _msgs(), test_a_credentials_failure_disables_nobody(), test_a_request_level_rejection_accepts_nothing(), test_a_retired_device_is_named_for_disabling(), test_a_single_message_reply_may_be_a_bare_object(), test_a_ticket_that_is_not_an_object_is_not_a_delivery(), test_an_error_ticket_is_not_counted_as_sent(), test_an_unpairable_reply_counts_nothing_and_disables_nothing() (+2 more)

### Community 42 - "DataGolf ingestor and NHL SBR archive"
Cohesion: 0.06
Nodes (44): _american(), backfill_golf_rounds(), build_game_id(), _dg_get(), _earliest_commence_iso(), event_slug(), ingest_golf_field(), ingest_golf_odds() (+36 more)

### Community 422 - "Mobile pick category tests"
Cohesion: 0.11
Nodes (14): _block(), _config_scorable_ids(), _meta_ids(), _meta_types(), _read(), test_every_model_id_derives_its_own_declared_category(), derived(), test_every_scorable_model_has_a_label_in_the_app() (+6 more)

### Community 423 - "College football board visibility tests"
Cohesion: 0.12
Nodes (7): test_a_declined_rule_can_never_leak_a_signal(), test_a_no_signal_row_does_not_lock_an_ncaaf_game_for_the_week(), test_every_registered_model_has_a_feature_map_entry(), test_the_premium_tier_shares_the_spread_features(), test_the_price_prefilter_can_only_ever_skip_ncaaf(), test_the_price_prefilter_fails_open(), test_unpriced_ncaaf_games_are_skipped_before_the_feature_build()

### Community 425 - "NFL odds cache import to Supabase"
Cohesion: 0.12
Nodes (9): _allowed(), _data_dirs(), test_a_rerun_after_the_resolver_improves_adds_only_the_gap(), test_every_buying_ingestor_keys_its_resume_on_a_source_marker(), test_no_undeclared_data_store_on_disk(), test_the_importer_resolves_a_postponed_game(), test_the_importer_still_refuses_an_event_with_no_game(), test_the_nfl_odds_cache_has_an_importer() (+1 more)

### Community 426 - "tests/test_health_check_observe.py"
Cohesion: 0.14
Nodes (10): _crit(), fake(), test_a_crit_does_not_fail_the_observe_path(), test_a_crit_still_fails_the_daily_step(), test_an_exception_does_not_fail_the_observe_path(), test_daily_syncs_thresholds_after_view_migrations(), test_it_still_runs_the_check_when_observing(), test_ok_is_identity_in_both_modes() (+2 more)

### Community 427 - "NFL in-play prop flow model"
Cohesion: 0.13
Nodes (16): best_hit(), _boot_ci(), drop_degenerate(), evaluate(), fit_time_curve(), grade(), load_rows(), main() (+8 more)

### Community 428 - "NFL 2026 opener and wind tracker"
Cohesion: 0.09
Nodes (28): classify(), fetch(), grade_rows(), is_void(), lead_days(), _load_nfl_model(), main(), opener_verdict() (+20 more)

### Community 429 - "NFL in-play prop line churn check"
Cohesion: 0.17
Nodes (14): load_snapshots(), churn_table(), main(), verdict(), _snaps(), test_a_line_moving_every_interval_reads_as_under_sampled(), test_a_missing_key_column_fails_loudly_rather_than_grouping_coarser(), test_a_single_snapshot_contributes_no_interval() (+6 more)

### Community 430 - "Picks unique index for unnamed props"
Cohesion: 0.15
Nodes (8): conn(), _prop(), test_player_id_uniqueness_is_unchanged(), test_the_card_insert_tolerates_the_unique_index(), test_the_narrow_index_collides_null_player_id_props(), test_the_same_proposition_still_collides_on_the_widened_index(), test_the_widen_migration_is_property_guarded(), test_the_widened_index_allows_null_player_id_props()

### Community 431 - "tests/test_pick_lock_is_on_picks.py"
Cohesion: 0.16
Nodes (9): _between(), _sql(), test_a_bet_is_still_never_re_scored(), test_only_a_bet_locks_a_pair(), test_the_cleanup_covers_the_whole_look_ahead_window(), test_the_cleanup_never_touches_a_started_game_or_a_live_row(), test_the_lock_is_no_longer_ncaaf_specific(), test_the_prop_and_live_locks_are_unchanged() (+1 more)

### Community 434 - "NFL in-play pick writer"
Cohesion: 0.14
Nodes (7): _is_market_opinion(), _lane_is_locked(), _norm_player(), resolve_game(), resolve_game_id(), test_normalised_player_key_is_the_join_the_prop_system_uses(), test_the_lane_lock_shares_the_scorers_meaning_of_locked()

### Community 436 - "Pregame price age limit"
Cohesion: 0.15
Nodes (8): _clock(), test_a_price_stored_this_pass_still_decides(), test_a_started_game_reads_its_last_pre_game_row_whatever_its_age(), test_just_inside_and_just_outside_the_bound(), test_the_app_applies_the_same_bound(), test_the_card_passes_its_clock_to_the_rule(), test_the_nhl_totals_card_will_not_bet_a_fetch_hours_old(), _totals_row()

### Community 437 - "Per-model threshold config tests"
Cohesion: 0.08
Nodes (8): test_an_own_floor_does_not_take_a_model_off_the_calibration_map(), test_every_model_carries_its_own_thresholds(), test_every_own_floor_names_a_live_model(), test_models_on_own_probability_is_not_derived_from_the_floor_dict(), test_no_own_floor_tightens_a_model_past_the_global_floor(), test_only_a_market_priced_model_carries_a_negative_floor(), test_the_models_the_global_floor_silently_removed_can_bet_again(), test_the_nba_home_team_total_floor_does_not_move_with_the_platform_default()

### Community 438 - "NBA game two verdict grid tests"
Cohesion: 0.21
Nodes (20): _cell(), _grid(), _hgrid(), _house(), _mid(), test_a_cell_below_the_bet_count_enters_the_correction_at_p_one(), test_a_cell_clearing_every_bar_passes(), test_a_cell_with_no_dominant_side_is_not_held_to_a_blind_bet() (+12 more)

### Community 439 - "Worker retrain and sweep jobs"
Cohesion: 0.07
Nodes (11): test_the_raised_timeout_is_restored_after_the_job(), test_the_restore_puts_back_a_pre_existing_value(), test_missing_artifact_path_refuses_to_sweep_live(), test_retrain_then_sweep_passes_the_new_path(), test_marker_file_is_in_tree_so_the_freeze_would_not_block_the_worker(), test_missing_artifact_path_refuses_to_sweep_live(), test_retrain_then_sweep_passes_the_new_path(), test_the_runner_retrains_then_sweeps_the_new_artifact() (+3 more)

### Community 442 - "NFL prop market remeasure pins"
Cohesion: 0.22
Nodes (3): test_the_2026_remeasure_did_not_move_the_24h_ceiling(), test_the_2026_remeasure_did_not_move_the_side_floors(), test_the_historical_grader_does_not_read_kalshi()

### Community 443 - "MLB retrain freeze guard"
Cohesion: 0.13
Nodes (9): assert_retrain_allowed(), test_import_time_flag_follows_marker_file(), test_marker_or_env_lifts_the_freeze(), test_mlb_prop_market_sweep_is_documented_exempt(), test_mlb_retrain_refused_while_incomplete(), test_mlb_threshold_sweeps_call_the_guard(), test_non_mlb_sports_are_not_gated(), test_repo_marker_file_is_present() (+1 more)

### Community 447 - "supabase/functions/discord-link/index.ts"
Cohesion: 0.24
Nodes (15): accessFor(), handleComplete(), handleStart(), handleStatus(), handleUnlink(), hmac(), issueState(), json() (+7 more)

### Community 449 - "tests/test_nfl_prop_clv.py"
Cohesion: 0.16
Nodes (9): _assign(), _book_from_label_fn(), _fn(), test_the_book_is_read_from_the_label_suffix(), test_the_closing_prop_lookup_defaults_to_draftkings_and_binds_the_book(), test_the_label_book_map_is_the_inverse_of_both_cards(), test_the_map_test_no_longer_excludes_nfl(), test_the_market_relative_rules_take_their_market_from_the_row() (+1 more)

### Community 452 - "tests/test_scoring_methods.py"
Cohesion: 0.13
Nodes (7): _generic(), test_a_generic_model_is_never_declared_rule_or_engine(), test_accessor_defaults_to_artifact(), test_every_classified_model_carries_thresholds(), test_mlb_live_total_runs_is_artifact_backed(), test_rule_based_models_never_appear_in_a_feature_map(), test_the_map_covers_exactly_the_non_generic_models()

### Community 456 - "NFL weather edge fetch"
Cohesion: 0.15
Nodes (18): audit(), baseline(), bh(), boot(), classify(), era(), grade(), load() (+10 more)

### Community 46 - "Worker job queue runner"
Cohesion: 0.03
Nodes (30): derive_first_pitch(), run(), test_the_worker_job_is_registered_and_defaults_to_dry_run(), test_the_discord_publish_job_calls_the_ordinary_producer(), test_the_discord_publish_job_takes_an_optional_date(), _execute(), _job_derive_first_pitch(), _job_game_log_backfill() (+22 more)

### Community 460 - "Calibration cut sweep and grading"
Cohesion: 0.17
Nodes (10): pick(), test_a_prob_cut_and_an_ev_cut_select_different_picks(), test_grade_uses_flat_units_and_counts_pushes_separately(), test_projection_is_none_rather_than_zero_when_the_regime_is_empty(), test_projection_uses_the_recent_regime_not_the_lifetime_average(), test_sweep_scores_a_plateau_higher_than_an_isolated_cell(), test_sweep_skips_cells_with_no_picks_rather_than_emitting_empty_ones(), _grade() (+2 more)

### Community 462 - "Anonymous read grant planning"
Cohesion: 0.03
Nodes (50): all_readable(), closed_tables(), lock_down_sql(), write_verbs_for(), _anon_can_read(), _function_plan(), _function_signature(), main() (+42 more)

### Community 465 - "nfl/scripts/backtest_opener.py"
Cohesion: 0.24
Nodes (9): boot(), by_season(), exp_win(), load(), main(), price(), report(), residuals() (+1 more)

### Community 466 - "Paused model assessment checks"
Cohesion: 0.15
Nodes (6): _rows(), test_a_cell_below_the_floor_is_not_a_result(), test_it_sweeps_both_pause_registers(), test_the_era_check_is_applied_to_every_candidate(), test_the_grade_reports_a_lower_bound_not_just_a_headline(), test_units_are_none_when_the_pick_carries_no_price()

### Community 467 - "NCAAF totals lead and consensus gate"
Cohesion: 0.26
Nodes (10): build_lead_table(), first_cross(), fmt(), grade(), line_as_of(), load_backfill(), main(), match_frame_to_odds() (+2 more)

### Community 468 - "tests/test_latest_odds_views.py"
Cohesion: 0.25
Nodes (13): _app_columns(), _function(), test_every_log_table_has_its_insert_trigger_and_the_odds_tables_an_update_trigger(), test_every_view_reads_its_state_table_and_never_the_log(), test_no_pending_view_migration_re_creates_these_views_over_the_log(), test_the_dk_view_returns_the_apps_columns_in_order(), test_the_exclusions_survived_the_move(), test_the_game_view_returns_the_apps_columns_in_order() (+5 more)

### Community 472 - "NBA schedule ingestor"
Cohesion: 0.16
Nodes (15): fetch_season(), main(), ot_periods(), run(), schedule_rows(), season_str(), _tv(), write() (+7 more)

### Community 475 - "NFL prop feature engine"
Cohesion: 0.10
Nodes (16): _add_features(), build_nfl_prop_scoring_rows(), _cols(), derived_targets(), _load(), _nfl_season(), _pool_mask(), _read() (+8 more)

### Community 476 - "tests/test_transaction_pooler.py"
Cohesion: 0.19
Nodes (8): _transaction_endpoint(), test_a_direct_connection_is_left_alone(), test_a_local_postgres_is_left_alone(), test_a_supabase_session_url_becomes_the_transaction_url(), test_it_is_idempotent(), test_only_the_port_changes(), test_the_escape_hatch_works(), test_the_job_queue_still_gets_session_mode()

### Community 477 - "Env file database URL fallback"
Cohesion: 0.16
Nodes (11): database_url(), _default_env_path(), env_value(), parse_env_file(), test_a_missing_env_file_is_empty_not_an_error(), test_a_value_containing_equals_survives(), test_env_file_is_read_when_the_environment_is_empty(), test_env_value_reads_other_keys_too() (+3 more)

### Community 480 - "NCAAF in-play history backtest"
Cohesion: 0.13
Nodes (14): build_candidates(), decide(), first_signals(), _fmt(), load_snapshots(), main(), odds_from_rows(), report() (+6 more)

### Community 483 - "Trainer no-register mode tests"
Cohesion: 0.12
Nodes (9): not_registering(), registering(), test_a_normal_run_DOES_register(), test_baseline_artifacts_are_not_committable(), test_baseline_runs_write_somewhere_else(), test_default_is_to_register(), test_no_register_opens_no_database_connection(), _explode() (+1 more)

### Community 486 - "Database URL doctor"
Cohesion: 0.14
Nodes (18): _classes(), diagnose(), bad(), _safe(), _fails(), _levels(), test_a_correct_url_reports_no_failures(), test_bare_postgres_on_a_DIRECT_host_is_fine() (+10 more)

### Community 487 - "supabase/functions/sharpsports/index.ts"
Cohesion: 0.30
Nodes (13): americanFromBetSlip(), asArray(), createContext(), isSettled(), json(), pick(), pullAndUpsert(), readBets() (+5 more)

### Community 489 - "NFL prop settlement name fallback"
Cohesion: 0.27
Nodes (10): _never(), _row(), test_a_first_name_the_stat_log_spells_differently_still_matches(), test_a_scratched_player_is_not_graded_on_a_teammate_with_his_initial(), test_a_spelling_the_log_already_knows_is_a_scratch_not_a_spelling(), test_another_game_and_another_initial_never_match(), test_first_name_rule(), test_two_candidates_is_a_miss_not_a_guess() (+2 more)

### Community 491 - "Rule model market reading tests"
Cohesion: 0.15
Nodes (10): _case(), _clv_game_market(), _like(), _prompt_case(), _scorer_case(), test_the_case_reader_reads_the_name_patterns_as_postgres_does(), test_the_claude_mobile_prompt_reads_the_rule_card_s_market(), test_the_closing_line_functions_are_recreated_when_they_change() (+2 more)

### Community 495 - "tests/test_worker_deps.py"
Cohesion: 0.22
Nodes (4): _requirements(), test_dashboard_packages_are_not_on_the_worker(), test_only_the_dashboard_imports_them(), test_the_worker_asks_for_the_cpu_build_of_xgboost()

### Community 50 - "scheduler.py"
Cohesion: 0.05
Nodes (55): abort_orphaned_refresh_runs(), build_scheduler(), _add_job(), _with_heartbeat(), _wrapped(), catch_up_daily_pipeline(), catch_up_refresh_pass(), catch_up_weekly_jobs() (+47 more)

### Community 501 - "Position defense ranks SQL checks"
Cohesion: 0.21
Nodes (10): _read(), _sql(), test_it_is_one_statement_and_each_piece_is_guarded(), test_the_app_calls_the_function_by_its_literal_name(), test_the_blend_cut_matches_the_app(), test_the_matchup_checks_pass(), test_the_matchup_header_fills_its_column_and_large_text_is_one_line(), test_the_role_and_stat_cuts_match_the_player_card() (+2 more)

### Community 502 - "Model scoring method registry"
Cohesion: 0.15
Nodes (8): scoring_method(), publish_enabled(), test_the_measured_cut_is_eighteen_tenths(), test_totals_paper_cut_is_two_pp_and_not_the_wall(), test_the_ev_floor_is_the_model_s_own_and_the_bet_is_priced_as_a_rule(), test_the_ev_floor_is_not_a_second_cut(), test_it_is_a_live_engine_model_that_settles_as_a_moneyline(), test_the_generic_scorer_and_the_trainer_cannot_reach_it()

### Community 505 - "tests/test_mobile_stat_labels_match_the_server.py"
Cohesion: 0.21
Nodes (6): _meta_entries(), _server_stat_labels(), test_both_rushing_models_call_the_stat_the_same_thing(), test_the_live_model_names_the_market_it_actually_trades(), test_the_parser_actually_found_the_models(), test_the_unreconciled_models_are_named()

### Community 506 - "tests/test_ncaaf_fcs_visitor_names_migration.py"
Cohesion: 0.15
Nodes (5): _rows(), test_each_write_guards_on_its_own_property(), test_every_real_visitor_extends_the_wrong_one(), test_migration_is_one_statement(), test_the_nine_rows_and_their_finals_are_the_measured_ones()

### Community 507 - "tests/test_nfl_prop_unstarted_clear.py"
Cohesion: 0.25
Nodes (8): _apply(), _assert_split(), _between(), _first_sql(), _per_game_sql(), _sweep_sql(), test_per_game_clear_keeps_nfl_prop_rows_on_a_game_the_loop_reaches(), test_sweep_keeps_unstarted_nfl_prop_nones_and_still_clears_game_nones()

### Community 508 - "Multi-sport model research labs"
Cohesion: 0.03
Nodes (97): _connect(), bh_fdr(), binom_p(), eval_rule(), load(), main(), devig_power(), games() (+89 more)

### Community 513 - "tests/test_scorer_nfl_prop_like_escape.py"
Cohesion: 0.23
Nodes (9): _between(), _broken_per_game_sql(), _first_sql(), _per_game_sql(), _sweep_sql(), test_escape_tripwire_is_on_the_pr_ci_subset(), test_live_per_game_clear_interpolates_with_one_game_id(), test_live_sweep_clear_interpolates_with_date_horizon_now() (+1 more)

### Community 514 - "Duplicate pick copy selection"
Cohesion: 0.18
Nodes (6): test_a_posted_copy_stays_even_when_it_was_written_later(), test_an_unreadable_stamp_never_wins(), test_the_earlier_copy_stays_and_compares_instants_not_text(), choose_kept(), rank(), _instant()

### Community 516 - "NHL stats views tests"
Cohesion: 0.15
Nodes (14): _date_filter_runs_before_dedupe(), anywhere(), blob(), filter_wraps_unique(), has_unique(), pred(), pred_inside_unique(), _pg_bin() (+6 more)

### Community 518 - "NHL game results parser"
Cohesion: 0.38
Nodes (9): parse_nhl_game(), _g(), test_arizona_folds_into_utah(), test_missing_teams_returns_none(), test_ot_home_win_is_regulation_draw(), test_preseason_game_skipped(), test_regulation_home_win(), test_scheduled_game_has_no_scores() (+1 more)

### Community 519 - "Sweep price floor filter tests"
Cohesion: 0.29
Nodes (7): _apply_price_floor(), _row(), test_a_model_with_no_floor_is_untouched(), test_every_prop_model_in_the_sweep_has_a_floor_to_apply(), test_plus_money_always_survives(), test_prices_juicier_than_the_floor_are_dropped(), test_the_boundary_matches_the_scorer()

### Community 520 - "Market movement feature builder"
Cohesion: 0.08
Nodes (24): american_to_prob(), build_market_features(), _is_full_game_snap(), _latest_two_sided(), test_rlm_x_move_and_steam_when_line_fades_the_public(), _s(), test_a_game_with_no_decision_book_still_gets_features(), test_a_line_that_genuinely_did_not_move_is_zero_not_none() (+16 more)

### Community 524 - "NCAAF margin model fit and registration"
Cohesion: 0.18
Nodes (12): _fit(), fit_and_register(), fit_and_register_totals(), main(), _matrix(), _print_sweep(), rmse(), sweep_total() (+4 more)

### Community 525 - "NFL live pick price ceiling tests"
Cohesion: 0.10
Nodes (9): _executor_min_price(), _probe_config(), test_the_ceiling_is_a_refusal_not_a_filter(), test_the_insert_tolerates_the_one_row_per_pick_index(), test_the_lane_can_actually_settle(), test_the_lane_refuses_a_quote_past_the_ceiling(), test_the_lock_is_scoped_by_player_not_just_by_game(), test_the_retired_model_carries_no_threshold_row() (+1 more)

### Community 529 - "tests/test_clear_unauthorized_auto_pauses_migration.py"
Cohesion: 0.19
Nodes (6): _stmts(), test_clearing_auto_pauses_did_not_park_batter_runs(), test_it_clears_the_whole_auto_pause_table(), test_it_does_not_touch_picks_thresholds_or_the_review_ledger(), test_it_no_ops_when_the_table_is_missing_or_already_empty(), test_migration_is_one_statement()

### Community 530 - "tests/test_ncaaf_se_louisiana_alias_migration.py"
Cohesion: 0.15
Nodes (4): test_a_pick_is_never_deleted_and_never_regraded(), test_it_guards_on_both_names_and_both_still_unscored(), test_migration_is_one_statement(), test_odds_move_only_when_canonical_has_none()

### Community 531 - "NFL live leader cut and price floor"
Cohesion: 0.11
Nodes (7): honest_probability(), test_a_loop_that_dies_fails_its_job(), test_it_decides_on_its_own_probability(), test_the_action_threshold_key_is_on_one_line(), test_the_loop_refuses_a_price_shorter_than_the_floor(), test_the_mlb_live_scorer_skips_it(), test_the_price_floor_is_minus_140()

### Community 532 - "tests/test_overnight_polling.py"
Cohesion: 0.24
Nodes (7): _hours(), _jobs(), _match(), test_every_hour_of_the_day_is_covered(), test_the_overnight_pass_is_the_ordinary_one(), test_the_overnight_window_exists(), test_the_windows_do_not_overlap()

### Community 534 - "NFL stale daily card clearing"
Cohesion: 0.15
Nodes (9): card_path(), clear_card(), _load_script(), nfl_path(), test_a_dry_run_leaves_the_card_alone(), test_a_priced_wind_run_with_no_bets_removes_the_earlier_card(), test_clear_card_removes_todays_file_and_only_that(), test_the_path_cleared_is_the_path_the_publisher_reads() (+1 more)

### Community 535 - "NFL opener stake sizing and EV"
Cohesion: 0.09
Nodes (23): american_to_decimal(), cover_probs(), ev_per_unit(), fit_margin_pmf(), kelly_fraction(), margin_pmf_for(), add_model_mu(), load() (+15 more)

### Community 536 - "Mobile type-check baseline tests"
Cohesion: 0.29
Nodes (13): _entries(), _log(), _log_line(), _run(), test_a_clean_log_warns_for_every_baseline_entry(), test_a_compiler_crash_is_not_a_clean_run(), test_a_different_app_message_fails(), test_a_fixed_baseline_entry_warns_and_does_not_fail() (+5 more)

### Community 537 - "Model trainer and calibration metrics"
Cohesion: 0.04
Nodes (34): calibration_method(), f(), _calibration_error_weighted(), calibration_metrics(), _count_cv_splits(), _gamma_shape(), _mean_calibration_error(), _nb1_dispersion() (+26 more)

### Community 539 - "NFL prop over lean concentration study"
Cohesion: 0.25
Nodes (7): add_context(), boot(), main(), profit(), report(), tercile_split(), under_profit()

### Community 541 - "Mobile line ruler tests"
Cohesion: 0.32
Nodes (8): _read(), _slice(), test_a_bubble_tap_does_not_clear_the_tick_guard_in_the_same_turn(), test_blur_commits_and_the_clamp_is_announced_once(), test_cancel_scrolls_the_strip_back_and_does_not_change_the_board(), test_cancel_wins_when_blur_fires_before_the_click(), test_talkback_can_activate_the_bubble(), test_verify_line_ruler_script()

### Community 542 - "X team hashtags"
Cohesion: 0.17
Nodes (11): test_college_nicknames_and_a_shared_mascot_falls_back_to_the_school(), test_team_hashtags_use_the_nickname(), _both_teams(), _from_full_names(), hashtag_token(), _index(), _mlb(), _nickname() (+3 more)

### Community 544 - "CLV no-vig close capture tests"
Cohesion: 0.11
Nodes (13): _is_main_guard(), _modules_with_guard(), test_at_least_one_entrypoint_is_scanned(), test_nothing_is_defined_after_the_main_guard(), _fn(), test_a_missing_bet_book_close_is_not_filled_from_another_book(), test_backfill_revisits_anything_that_is_not_standard_v2(), test_capture_grades_raw_same_book_and_a_separate_pinnacle_edge() (+5 more)

### Community 546 - "tests/test_claude_rules_split.py"
Cohesion: 0.18
Nodes (4): test_claude_md_still_points_at_the_rules_directory(), test_every_rule_file_actually_carries_rules(), test_every_rule_file_is_path_scoped(), test_no_rule_was_lost_when_the_split_happened()

### Community 547 - "tests/test_db_setup.py"
Cohesion: 0.23
Nodes (6): _get_columns(), test_games_table_columns(), test_injuries_table_columns(), test_odds_table_columns(), test_picks_table_columns(), test_schema_is_idempotent()

### Community 548 - "tests/test_dedupe_opening_signals.py"
Cohesion: 0.12
Nodes (8): test_a_graded_row_is_never_deleted(), test_a_row_with_computed_clv_is_never_deleted(), test_every_field_that_defines_the_bet_must_agree(), test_the_delete_selects_through_the_same_gates(), test_the_pair_must_be_an_old_shape_new_shape_pair(), test_the_report_and_the_delete_share_one_definition(), test_the_row_kept_is_the_one_locked_earlier(), test_the_unresolved_report_excludes_what_the_delete_resolves()

### Community 552 - "tests/test_pbp_backfill_resilience.py"
Cohesion: 0.24
Nodes (6): _backfill_body(), test_a_failed_game_rolls_the_connection_back(), test_a_run_that_wrote_nothing_reports_an_error_not_a_success(), test_errors_are_counted_not_just_logged(), test_partial_failures_are_surfaced_too(), test_the_rollback_cannot_itself_raise()

### Community 559 - "In-play bet uniqueness index tests"
Cohesion: 0.13
Nodes (13): _db(), _insert(), _signals(), test_a_live_bet_survives_an_avoid_on_the_same_lane(), test_a_second_live_bet_on_the_same_lane_still_conflicts(), test_a_void_notice_sibling_query_keeps_a_published_bet(), test_a_void_or_no_action_live_bet_does_not_hold_the_lane(), test_mlb_and_ncaaf_already_clear_the_standing_non_bet_before_insert() (+5 more)

### Community 561 - "NFL wind forecast validation"
Cohesion: 0.29
Nodes (10): build(), games(), hourly(), main(), _rate(), sec_coverage(), sec_error(), sec_rule() (+2 more)

### Community 563 - "Paused model profitability assessment"
Cohesion: 0.22
Nodes (9): _auto_paused_models(), active_era(), assess(), _half(), fetch(), grade(), main(), sweep() (+1 more)

### Community 565 - "NCAAF quarterback ablation study"
Cohesion: 0.28
Nodes (7): _fit(), main(), _report(), run(), summarise(), walk_forward(), wilson()

### Community 567 - "NBA results window games"
Cohesion: 0.47
Nodes (5): _games(), _postponed(), _schedule(), _opp(), end()

### Community 568 - "NFL weekly wind card"
Cohesion: 0.09
Nodes (18): bettable_books(), coverage_check(), expected_true_wind(), open_air_mask(), load_nfl_model(), boot_ci(), candidate_rows(), _load_backtest() (+10 more)

### Community 569 - "NBA in-game study one tests"
Cohesion: 0.17
Nodes (15): _pin(), _q(), _rows(), _state(), test_every_fit_for_season_s_uses_earlier_seasons_only(), test_expected_rates_use_the_teams_earlier_dates_only(), test_ig1_bets_against_luck_and_the_control_with_it(), test_luck_counts_a_three_three_times_and_a_free_throw_once() (+7 more)

### Community 572 - "Count each event once in records"
Cohesion: 0.18
Nodes (7): duplicate_copy_exclusion_sql(), test_the_discord_recap_counts_each_event_once(), test_the_finder_skips_copies_already_marked(), test_the_marker_is_one_constant_and_one_predicate(), test_the_monitor_dashboard_box_score_arm_counts_each_event_once(), test_the_monitor_dashboard_picks_arm_counts_each_event_once(), test_the_predicate_keeps_rows_with_no_marker()

### Community 573 - "NBA public splits pipeline step"
Cohesion: 0.17
Nodes (11): inserted_minus_start_min(), side(), test_v1_inserted_lag_is_minutes_after_the_listed_start(), Coverage, Forward capture (2026-27), How to read it, NBA public betting splits (Action Network) — `nba_public_splits`, Rows to leave out (+3 more)

### Community 574 - "tests/test_prompt_reads_thresholds.py"
Cohesion: 0.18
Nodes (4): test_the_auto_pause_lookup_fails_open(), test_the_prompt_carries_no_per_model_cut(), test_the_prompt_still_says_it_is_pasted_once(), test_the_sync_mirrors_both_pause_registers()

### Community 575 - "tests/test_system_health_meta_steps.py"
Cohesion: 0.25
Nodes (5): _meta_steps(), test_aborted_sentinel_is_excluded(), test_health_check_is_excluded(), test_model_quality_is_excluded(), test_sentinel_matches_the_writer()

### Community 576 - "NCAAF situational spot evaluation"
Cohesion: 0.10
Nodes (10): is_bowl_game(), build_spots(), evaluate(), load_team_games(), main(), wilson(), load_data(), main() (+2 more)

### Community 577 - "NBA period score ingestion"
Cohesion: 0.32
Nodes (8): _int(), parse_period_rows(), _event(), test_espn_team_codes_map_to_ours(), test_one_row_per_period_under_our_game_id(), test_overtime_periods_follow_the_fourth(), test_quarters_that_do_not_sum_to_the_final_are_skipped(), test_unfinished_games_and_mismatched_period_counts_are_skipped()

### Community 580 - "scripts/render_brand_icons.py"
Cohesion: 0.24
Nodes (3): draw_mark(), main(), render()

### Community 581 - "NBA research data cache"
Cohesion: 0.49
Nodes (8): _by_game_ids(), cache_box(), cache_games(), cache_lines(), cache_props(), _frame(), main(), _table_exists()

### Community 582 - "Results recap NFL box score ordering"
Cohesion: 0.17
Nodes (8): _daily(), _job_body(), test_a_malformed_date_is_refused_before_anything_runs(), test_nfl_box_scores_are_ingested_before_settle(), test_nfl_finals_still_precede_the_box_scores(), test_the_job_does_not_read_rowcount_off_the_cursor(), test_the_job_only_clears_its_own_two_ledger_kinds(), test_the_job_posts_both_surfaces_through_the_ordinary_paths()

### Community 585 - "NBA prop model verification stages"
Cohesion: 0.13
Nodes (28): adv_from_log(), asof_roster(), blind_structured(), card_block(), collapse_report(), _compare(), log(), main() (+20 more)

### Community 586 - "supabase/functions/stripe-webhook/index.ts"
Cohesion: 0.31
Nodes (9): applySubscription(), iso(), resolveUserId(), stripeGet(), timingSafeEqual(), toHex(), verifySignature(), admin (+1 more)

### Community 589 - "tests/test_mobile_neutral_signal_label.py"
Cohesion: 0.31
Nodes (7): _read(), test_explainer_names_neutral(), test_filters_and_card_speak_the_display_name(), test_model_screens_speak_the_display_name(), test_no_member_label_prints_a_raw_signal_type(), test_none_badge_reads_neutral(), test_withdrawn_pick_is_not_badged_neutral()

### Community 591 - "College football data checks"
Cohesion: 0.33
Nodes (5): _check(), _lines_coverage(), main(), _null_report(), _sample_keys()

### Community 593 - "tests/test_scorer_commits_per_game.py"
Cohesion: 0.40
Nodes (8): _between(), _run_scorer_body(), test_a_lost_connection_re_runs_the_game_once_and_never_the_pass(), test_each_game_is_its_own_committed_unit(), test_no_bulk_delete_of_non_bet_rows_precedes_the_loop(), test_picks_are_only_counted_once_the_game_committed(), test_the_housekeeping_delete_is_a_sweep_after_the_loop(), test_the_outer_handler_still_records_the_failure()

### Community 595 - "NCAAF in-play model resweep"
Cohesion: 0.27
Nodes (6): attach(), first_signals(), load(), main(), summarise(), wilson()

### Community 596 - "NBA ESPN box score parsing"
Cohesion: 0.08
Nodes (24): box_team_totals(), et_date(), nba_team(), _no_minutes(), parse_nba_box(), parse_nba_dnp(), parse_nba_postponed(), parse_nba_scoreboard() (+16 more)

### Community 598 - "Declared worker job validation tests"
Cohesion: 0.15
Nodes (7): _declared(), test_an_explicit_run_date_must_be_a_real_iso_date(), test_declared_keys_are_unique(), test_every_declared_job_names_a_registered_type(), test_every_declared_job_validates(), test_no_run_date_means_the_module_resolves_it(), test_the_validator_drops_unknown_args()

### Community 60 - "tests: test_wnba_availability + wnba_availability"
Cohesion: 0.10
Nodes (33): absence_features(), absent_teammates(), build_context_features(), expected_rotation(), is_starter_tier(), _mean(), prior_rows(), recent_team_game_dates() (+25 more)

### Community 600 - "Mobile stat segment tabs tests"
Cohesion: 0.20
Nodes (10): _read(), test_one_shared_defensive_set(), test_position_is_never_inferred_from_stats(), test_runs_in_pr_ci(), test_search_and_position_review_fixes(), test_segment_labels_cap_only_on_fit(), test_tabs_speak_the_visible_label_not_the_key(), test_the_behavioural_checks_pass() (+2 more)

### Community 601 - "MLB public fade pregame splits"
Cohesion: 0.27
Nodes (6): is_pre_commence(), load_public_over_splits(), select_latest_pre_commence_over(), test_missing_clocks_fail_closed(), test_post_start_split_is_dropped_even_when_text_says_before(), test_snapshot_at_commence_is_not_pre_commence()

### Community 606 - "Mobile NHL today look-ahead tests"
Cohesion: 0.29
Nodes (5): _fn(), _read(), test_the_nhl_read_matches_the_other_look_aheads(), test_the_sport_chip_is_the_hook_not_an_allowlist(), test_use_today_picks_fetches_nhl_across_that_window()

### Community 608 - "supabase/functions/sharpsports-webhook: index + index"
Cohesion: 0.25
Nodes (5): internalIdFor(), pick(), admin, admin, cors

### Community 609 - "Mobile Lines board pin tests"
Cohesion: 0.22
Nodes (9): _read(), test_a_missing_draw_price_is_remembered(), test_lines_board_pins_are_on_the_pr_ci_subset(), test_lines_is_a_picks_view(), test_the_behavioural_checks_pass(), test_the_board_reloads_when_the_et_date_changes(), test_the_lines_read_names_the_view_and_pages(), test_the_lines_segment_is_unconditional_and_after_live() (+1 more)

### Community 612 - "supabase/functions/stripe-checkout/index.ts"
Cohesion: 0.31
Nodes (8): customerFor(), form(), json(), stripe(), admin, cors, PRICES, TRIAL_DAYS

### Community 614 - "tests/test_book_list_budget.py"
Cohesion: 0.31
Nodes (4): _names(), test_every_book_the_nfl_prop_model_bets_at_is_actually_fetched(), test_the_nfl_prop_pull_is_one_group_with_both_references_in_it(), test_the_shared_list_is_one_group()

### Community 617 - "Mobile type-check baseline checker"
Cohesion: 0.27
Nodes (8): diagnostic_key(), log_is_compiler_failure(), main(), parse_baseline(), parse_log(), render_baseline(), stale(), unexpected()

### Community 62 - "NBA game market search lab"
Cohesion: 0.05
Nodes (61): assemble(), _assert_spread_sign(), attach_close(), bars(), bet_frame(), blind_bets(), blind_first_fetch(), boot_ci() (+53 more)

### Community 620 - "NHL totals research lab"
Cohesion: 0.26
Nodes (8): grade(), imp(), interval(), load(), main(), row(), show(), wpu()

### Community 622 - "UFC fight page parsing"
Cohesion: 0.11
Nodes (15): _aggregate_stats(), _kd_int(), _int_or_none(), _mmss_to_sec(), _of_pair(), parse_event_page(), _two_ints(), parse_fight_page() (+7 more)

### Community 623 - "NBA game model synthetic world seeding"
Cohesion: 0.22
Nodes (6): _emit_world(), _spy_run_cells(), test_closing_value_is_priced_with_the_markets_empirical_distribution(), test_every_family_emits_exactly_its_cells_through_the_harness(), test_the_d_cells_are_gated_on_the_points_own_decision_times(), test_the_bootstrap_is_seeded_and_refines_small_p()

### Community 628 - "NCAAF weather totals study"
Cohesion: 0.23
Nodes (6): build_spots(), evaluate(), load_games(), main(), scoring_by_wind(), wilson()

### Community 629 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.47
Nodes (6): contentHeight(), evalExpr(), lineOf(), styleBlock(), styleProp(), visualHeight()

### Community 63 - "Football in-play game state"
Cohesion: 0.08
Nodes (24): _as_float(), _as_int(), _as_opt_float(), _as_opt_int(), from_espn(), from_extract(), from_pbp_row(), smooth_pass_rate() (+16 more)

### Community 635 - "tests/test_demote_ncaaf_over_under_platt.py"
Cohesion: 0.32
Nodes (4): _stmts(), test_it_demotes_only_the_measured_promotion(), test_it_does_not_move_the_gate_the_floor_or_a_pause(), test_migration_is_one_statement()

### Community 637 - "tests/test_discord_post_one_pick_migration.py"
Cohesion: 0.29
Nodes (3): _pairs(), test_it_names_each_measured_extra_and_the_row_kept(), test_the_update_does_not_rewrite_the_graded_outcome()

### Community 638 - "tests/test_game_scorer_spares_nfl_props.py"
Cohesion: 0.43
Nodes (5): _between(), _run_scorer_body(), test_an_nfl_game_never_enters_the_per_game_clear(), test_both_live_non_bet_clears_leave_nfl_rows(), test_the_left_out_ufc_clear_only_removes_unsettled_non_bets()

### Community 64 - "NFL in-play score distribution pricing"
Cohesion: 0.05
Nodes (49): align_states(), build_team_map(), _game_index(), kill_verdict(), load_cached_snapshots(), main(), _model_price(), replay() (+41 more)

### Community 641 - "Mobile quiet update download tests"
Cohesion: 0.17
Nodes (8): _code_only(), _read(), test_a_downloaded_update_is_announced_quietly_once(), test_app_root_mounts_the_ota_updater(), test_every_trigger_only_downloads(), test_nothing_in_the_app_reloads_a_running_app(), test_the_pieces_exist(), test_the_updater_downloads_the_update()

### Community 642 - "NBA team total luck replay tests"
Cohesion: 0.18
Nodes (6): art(), ld(), results(), test_the_artifact_holds_the_lab_s_team_total_residuals_in_order(), test_the_live_code_reproduces_the_lab_game_for_game(), test_the_live_home_parts_are_the_independent_lab_copy_s()

### Community 645 - "Live odds vendor feed probe"
Cohesion: 0.24
Nodes (8): dump_vendor(), _get(), _is_live(), _key(), _row(), run(), _totals(), _vendor_key()

### Community 647 - "NFL Kalshi price history fetch"
Cohesion: 0.21
Nodes (6): candles(), get(), map_games(), paged(), parse_event(), probe()

### Community 649 - "MLB totals public fade card"
Cohesion: 0.09
Nodes (19): load_latest_quotes(), edge_floor(), max_per_slate(), publish_enabled(), rank_kind(), ticket_threshold(), under_odds_band(), main() (+11 more)

### Community 65 - "NBA prop model research lab"
Cohesion: 0.07
Nodes (45): books(), decimal(), expected_value(), p_over(), _agg(), apply_rule(), binary_baselines(), binary_indep() (+37 more)

### Community 650 - "Mobile stats filter UX verify"
Cohesion: 0.17
Nodes (10): board, chip, lineOnlyFn, playersDay, ROOT, sportReset, stats, teams (+2 more)

### Community 653 - "NFL prop pulled quote filter"
Cohesion: 0.32
Nodes (8): drop_pulled_quotes(), _ts(), _q(), test_a_book_on_its_own_cadence_is_not_penalised_inside_three_hours(), test_a_book_that_stopped_returning_the_game_is_dropped(), test_a_player_the_book_stopped_quoting_is_dropped(), test_a_whole_market_the_book_pulled_is_dropped(), test_rows_from_one_fetch_minutes_apart_are_kept_and_a_line_move_is_not_a_pull()

### Community 659 - "SQL percent escaping guard"
Cohesion: 0.21
Nodes (5): _adapt(), _parameterised_sql(), test_check_line_movement_query_interpolates(), test_parameterised_sql_escapes_literal_percents(), test_the_scanner_actually_catches_the_regression()

### Community 662 - "NFL wind stake past calibration tests"
Cohesion: 0.22
Nodes (6): _probe(), test_an_uncalibrated_lead_is_sized_rather_than_zeroed_on_the_card(), test_at_the_default_gate_that_same_row_does_not_fire_at_all(), test_the_eval_board_agrees_with_the_card(), test_the_probability_was_already_clipping(), test_the_stake_clips_to_lead_seven_instead_of_returning_zero()

### Community 663 - "NFL kickoff-hour live wind readings"
Cohesion: 0.28
Nodes (4): attach_live_wind_reads(), _current(), _utc(), _with_current()

### Community 665 - "NCAAF scoreboard yardline parsing"
Cohesion: 0.21
Nodes (6): _abbrev_fits(), _parse_yardline(), _cfbd_game(), test_cfbd_state_carries_the_yardline_and_the_raw_situation(), test_cfbd_yardline_from_every_stored_situation(), test_cfbd_yardline_refuses_rather_than_guesses()

### Community 667 - "NCAAF prop market rule sweep"
Cohesion: 0.26
Nodes (7): candidates(), dedupe(), grade(), load_board(), main(), norm(), profit()

### Community 668 - "NFL prop market stacking studies"
Cohesion: 0.08
Nodes (29): closing_prices(), devig(), ecdf_p_over(), main(), bets(), design(), main(), analyse() (+21 more)

### Community 669 - "NFL prop opening signal cleanup tests"
Cohesion: 0.23
Nodes (6): _stmts(), test_it_deletes_exactly_the_three_measured_lock_keys(), test_it_does_not_touch_picks_or_discord(), test_it_still_skips_a_key_that_has_a_standing_bet(), test_migration_is_one_statement(), test_standing_pick_uses_lock_key_sql_not_player_id()

### Community 673 - "Scorer keeps off-DraftKings priced bets tests"
Cohesion: 0.29
Nodes (6): _bet(), db(), _left(), _statement(), test_a_bet_priced_at_another_books_line_survives_and_a_bet_with_no_price_does_not(), test_the_statement_names_both_prices()

### Community 677 - "Historical odds file loader"
Cohesion: 0.25
Nodes (3): canonical_abbrev(), parse_csv_file(), test_sbr_abbreviations_are_canonicalised_for_mlb_only()

### Community 689 - "UFC event list date parsing"
Cohesion: 0.33
Nodes (4): _parse_event_date(), parse_event_list(), test_event_date(), test_parse_event_list()

### Community 690 - "NHL derivative totals dormant card"
Cohesion: 0.40
Nodes (3): main(), run(), test_card_writes_nothing_and_the_pipeline_does_not_call_it()

### Community 692 - "UFC fighter page parsing"
Cohesion: 0.22
Nodes (7): _height_to_inches(), _parse_dob(), parse_fighter_page(), _reach_to_inches(), test_height_reach_dob(), test_parse_fighter_page(), test_parse_fighter_page_missing_fields()

### Community 694 - "NBA projection price cache guard tests"
Cohesion: 0.33
Nodes (3): _games_file(), test_a_segment_file_missing_part_of_a_season_is_refused(), test_full_checks_the_price_cache_for_every_graded_season_before_building_anything()

### Community 695 - "Every named sportsbook is fetched"
Cohesion: 0.18
Nodes (5): _param_books(), test_a_sharp_reference_is_never_also_a_soft_book(), test_every_bettable_book_can_be_named_to_a_human(), test_every_named_book_is_in_the_pull_that_serves_it(), test_the_nfl_backfill_defaults_to_the_live_pull()

### Community 697 - "Model pause check in scorer"
Cohesion: 0.40
Nodes (3): _is_paused(), test_config_pauses_still_work_through_the_same_helper(), test_the_scorer_still_honours_a_leftover_auto_pause_row()

### Community 704 - "NCAAF consensus gate frame builder"
Cohesion: 0.39
Nodes (6): fmt(), grade(), load_closes(), main(), match(), wilson()

### Community 707 - "NFL prop blind under bias"
Cohesion: 0.27
Nodes (6): bias_table(), implied(), load(), main(), norm(), profit()

### Community 713 - "Game log backfill per-game skip"
Cohesion: 0.25
Nodes (5): _backfill_body(), test_a_game_absent_from_our_games_table_is_still_skipped(), test_no_skip_is_keyed_on_date_alone(), test_the_coverage_set_is_scoped_to_the_season_being_built(), test_the_skip_is_keyed_on_game_id()

### Community 716 - "NFL weather storage fallback tests"
Cohesion: 0.50
Nodes (3): test_a_store_failure_is_a_warning_not_an_error(), test_no_database_falls_through_quietly(), boom()

### Community 717 - "NBA second game luck rating tests"
Cohesion: 0.24
Nodes (9): _pair(), _target(), _tb_row(), test_a_teams_own_shooting_is_left_as_played(), test_league_averages_use_only_games_before_the_date(), test_opponent_three_and_free_throw_pct_are_replaced_by_the_league_average(), test_ratings_ignore_the_previous_season(), test_ratings_use_only_games_before_the_date() (+1 more)

### Community 719 - "Mobile accessibility verify script"
Cohesion: 0.67
Nodes (3): read(), readUtf8(), verticalSlop()

### Community 72 - "Market handicap feature tests"
Cohesion: 0.04
Nodes (42): attach_market_handicap(), build_public_features(), build_rich_handicap(), empty_handicap(), _fav_signed_home_move(), favorite_side(), _gated_flag(), load_handicap_for_game() (+34 more)

### Community 721 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.67
Nodes (3): closeOf(), openTag(), toggleUse()

### Community 74 - "Prop CLV and SQL escaping tests"
Cohesion: 0.09
Nodes (18): _fn(), test_a_backfill_failure_never_breaks_settlement(), test_a_pick_is_only_stamped_captured_once_a_measure_resolved(), test_a_pick_stamped_after_first_pitch_is_never_measured(), test_a_prop_pick_whose_label_has_no_name_is_skipped_not_guessed(), test_both_guards_agree(), test_clv_pct_never_compares_prices_across_a_moved_line(), test_every_prop_model_maps_to_a_dk_market() (+10 more)

### Community 75 - "NCAAF margin and totals evaluation"
Cohesion: 0.13
Nodes (10): margin_cover_prob(), sweep_spread(), test_margin_cover_prob_ecdf(), test_rmse(), test_scorer_routes_margin_artifact_through_residual_prob(), test_spread_grading_home_and_away_sides(), test_spread_push_excluded_from_record(), test_threshold_filters_small_disagreements() (+2 more)

### Community 76 - "ncaaf_live/tests/test_serve.py"
Cohesion: 0.07
Nodes (37): _clock_seconds(), extract_live_states_cfbd(), school(), _parse_situation(), _strip_mascot(), _cfbd_game(), _ctx(), _no_ev_floor() (+29 more)

### Community 8 - "Discord tipster picks grading and recaps"
Cohesion: 0.07
Nodes (45): test_an_unset_webhook_posts_nothing(), test_the_embed_names_eggz_and_states_units_and_roi(), test_units_use_the_stated_stake_and_do_not_invent_a_price(), _add_last(), _aliases(), add(), _candidate_games(), configured_to_post() (+37 more)

### Community 82 - "Mobile error states and books tests"
Cohesion: 0.05
Nodes (39): tsx_cmd(), _read(), test_combiner_is_pure_and_lives_next_to_fill(), test_handoff_opens_the_combined_url_not_the_first_leg(), test_the_behavioural_checks_pass(), _load_state_dir(), _raw_error_lines(), _read() (+31 more)

### Community 851 - "Results snapshot pass order tests"
Cohesion: 0.25
Nodes (6): _between(), _code(), _pass(), test_a_second_pass_does_not_mix_posted_wins_with_all_bets_units(), test_published_rewrite_runs_once_and_uses_the_view_clv_rule(), test_recompute_rewrites_snapshots_only_while_the_old_column_exists()

### Community 853 - "No record-only mode guard tests"
Cohesion: 0.43
Nodes (4): _allowed(), _hits(), _rel(), test_the_repo_has_no_record_only_or_paper_tracking_mode()

### Community 854 - "Shared fake row query helpers"
Cohesion: 0.14
Nodes (7): test_the_halftime_distribution_refuses_a_choosing_season_without_enough_earlier_games(), rows(), fetchall(), fetchall(), fetchall(), fetchall(), fetchall()

### Community 856 - "MLB public fade top-k backtest"
Cohesion: 0.12
Nodes (17): american_units(), bucket_win_rates(), build_candidates(), _fmt(), grade_under(), holdout_take(), load_db(), load_json() (+9 more)

### Community 86 - "NFL QB wind and NBA in-game tests"
Cohesion: 0.03
Nodes (79): coerce_numeric_features(), feature_matrix(), test_baselines_never_see_the_game_they_price(), load_games(), main(), pivot_spreads(), pivot_totals(), load_games() (+71 more)

### Community 860 - "UFC rounds completed settlement"
Cohesion: 0.29
Nodes (6): rounds_completed(), _fight_minutes(), load(), test_rounds_completed_distance(), test_rounds_completed_finish(), test_rounds_completed_missing()

### Community 867 - "Manual X posts runbook"
Cohesion: 0.25
Nodes (8): pin(), How to enqueue a post with an image, How to enqueue another post or thread, Manual posts to @SignalBasePicks, Pinning, Profile, What is already queued, What the drain will not do

### Community 868 - "NFL live pick game date resolution"
Cohesion: 0.25
Nodes (3): test_a_night_game_pick_carries_the_game_s_date_not_the_utc_clock(), test_nothing_written_means_nothing_announced(), test_resolution_refuses_rather_than_guesses()

### Community 87 - "NHL box score parsing"
Cohesion: 0.12
Nodes (16): _decision(), fill_missing(), _insert_absent(), _int(), _name(), parse_boxscore(), side_rows(), store_boxscore() (+8 more)

### Community 876 - "NBA play-by-play clock parsing"
Cohesion: 0.40
Nodes (3): parse_clock(), test_field_goal_value(), test_parse_clock()

### Community 887 - "NFL in-play prop publish refusal"
Cohesion: 0.29
Nodes (4): refuse_publish_reason(), test_refuse_publish_allows_a_real_rush_under(), test_refuse_publish_blocks_pass_attempt_overs(), test_refuse_publish_blocks_the_constant_prob_fingerprint_even_on_rush()

### Community 89 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.03
Nodes (50): a11ySrc, allowHit, ALLOWLIST, app, badExempt, bar, bareClose, baselineLeft (+42 more)

### Community 892 - "Prop board market coverage invariants"
Cohesion: 0.25
Nodes (4): _board_markets(), table(), test_the_mlb_board_and_the_mlb_pull_are_one_set(), test_the_tables_are_locked_down_at_the_create_site()

### Community 896 - "Opening versus closing strategy analysis"
Cohesion: 0.43
Nodes (4): _fmt(), _profit_sql(), _row(), strategy_analysis()

### Community 899 - "NBA public fade poll timing"
Cohesion: 0.39
Nodes (7): _split(), test_public_fade_drops_the_slate_the_source_serves_reversed(), poll(), test_public_fade_reads_only_polls_observed_before_T(), test_public_fade_refuses_splits_with_no_date_to_check_the_reversed_slate(), test_public_fade_without_a_pre_T_poll_or_with_an_even_split_bets_nothing(), _times()

### Community 90 - "NBA fifth search team rating projections"
Cohesion: 0.10
Nodes (23): as_of_ratings(), _before(), f4_projections(), pair_ratings(), project_ratings(), team_targets(), blended_ratings(), early_games() (+15 more)

### Community 907 - "NCAAF team game stats parsing"
Cohesion: 0.22
Nodes (7): parse_team_game_stats(), _possession_seconds(), _to_int(), test_parse_team_game_stats_builds_one_row_per_team(), test_parse_team_game_stats_skips_games_missing_from_the_id_map(), test_plays_is_none_when_neither_attempt_stat_is_present(), test_plays_tolerates_one_attempt_stat_missing()

### Community 909 - "NHL goalie save rate regression"
Cohesion: 0.83
Nodes (4): _goalie_line(), regressed(), saved_above(), tot()

### Community 91 - "NFL in-play backtest replay harness"
Cohesion: 0.07
Nodes (23): _settle(), _team_side(), build_states(), load_pbp(), monotonicity_report(), _repair_day_offsets(), sample_states(), _pbp() (+15 more)

### Community 928 - "NBA second game placebo run tests"
Cohesion: 0.33
Nodes (3): _stub_main(), test_a_full_run_hands_exactly_twenty_placebo_runs_to_every_cell(), test_a_full_run_with_the_override_stops_before_anything_is_graded()

### Community 93 - "MLB totals public fade tests"
Cohesion: 0.13
Nodes (26): find_fade_bets(), under_in_odds_band(), _dk_board(), _quote(), _quotes(), _slate(), _split(), test_always_under_one_per_game() (+18 more)

### Community 937 - "Dashboard rule models third state"
Cohesion: 0.14
Nodes (5): test_a_rule_carries_a_cut_but_is_in_no_training_registry(), test_a_rule_is_not_styled_as_a_warning(), test_a_rule_sorts_with_the_live_models_not_the_broken_ones(), test_the_roster_query_flags_rules(), test_the_summary_counts_rules_apart_from_outages()

### Community 940 - "NFL prop book bettability sweep"
Cohesion: 0.25
Nodes (6): soft_verdict(), test_a_bettable_book_still_passes(), test_an_unbettable_book_is_excluded_however_good_its_numbers(), test_every_incumbent_soft_book_is_bettable(), test_the_clause_is_not_dead_code(), _verdict()

### Community 97 - "Discord live signal embeds and prices"
Cohesion: 0.08
Nodes (20): _sig(), test_a_strictly_better_book_becomes_the_headline(), test_an_equal_or_worse_price_never_replaces_draftkings(), test_best_odds_never_reaches_the_qualifying_gate(), test_draftkings_winning_its_own_shop_is_published_as_draftkings(), test_every_pre_game_producer_computes_good_to(), test_good_to_is_published_when_the_producer_supplies_it(), test_good_to_is_simply_absent_when_it_cannot_be_computed() (+12 more)

### Community 98 - "NBA play-by-play ingestor"
Cohesion: 0.05
Nodes (52): active_queries(), alias_map_rows(), _bool(), box_context(), box_finals(), build_game(), build_gap_game(), build_map() (+44 more)

### Community 106 - "Supabase schema tables"
Cohesion: 0.03
Nodes (103): api_call_log, app_errors, device_push_tokens, fighters, golf_players, golf_rounds, idx_api_call_api_ts, idx_api_call_ts (+95 more)

### Community 179 - "mobile/app.json"
Cohesion: 0.05
Nodes (38): backgroundColor, foregroundImage, adaptiveIcon, package, projectId, expo, android, extra (+30 more)

### Community 184 - "mobile/package.json"
Cohesion: 0.09
Nodes (23): dependencies, expo, expo-asset, expo-dev-client, expo-font, expo-notifications, expo-status-bar, expo-updates (+15 more)

### Community 202 - "Core odds schema and latest views"
Cohesion: 0.05
Nodes (36): public.v_latest_odds_all_books, public.v_latest_inplay_odds_all_books, public.v_latest_prop_odds_all_books, public.v_latest_prop_odds_all_books, public.latest_lines_rebuild_odds(), public.latest_odds_recompute(), public.latest_prop_odds_recompute(), public.v_latest_odds_all_books (+28 more)

### Community 304 - "Player game log RPCs"
Cohesion: 0.08
Nodes (25): public.v_model_full_outcome_picks, public.player_recent_games_mlb(), public.player_recent_games_nba(), public.player_recent_games_wnba(), public.player_season_stat_values_mlb(), public.player_season_stat_values_nba(), public.player_season_stat_values_wnba(), public.v_model_full_outcome_record (+17 more)

### Community 344 - "Picks and public track record views"
Cohesion: 0.07
Nodes (24): v_opening_signal_slices, v_opening_vs_live, mv_scored_pick_outcomes_model_idx, mv_scored_pick_outcomes_pick_id_idx, public.v_model_full_outcome_record, public.v_public_track_record, public.v_public_track_record_daily, public.v_public_track_record (+16 more)

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

### Community 657 - "NHL moneyline rebuild write-up"
Cohesion: 0.29
Nodes (6): Method, NHL moneyline, rebuilt (2026-10-13), Read, Results, The production version, and two checks on it (2026-10-13/14), What the live model has, and what it was missing

### Community 661 - "NCAAF player stats leaderboard"
Cohesion: 0.42
Nodes (8): idx_ncaaf_plog_player, idx_ncaaf_plog_season, idx_ncaaf_plog_team, ncaaf_player_game_log, public.player_recent_games_ncaaf(), public.player_season_stat_values_ncaaf(), public.player_window_totals_ncaaf(), v_player_season_totals_ncaaf

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

### Community 715 - "Custom model facts tables migration"
Cohesion: 0.48
Nodes (6): idx_byom_game_facts_date, idx_byom_game_facts_season, idx_byom_prop_facts_game, idx_byom_prop_facts_season, public.byom_game_facts, public.byom_prop_facts

### Community 722 - "Kalshi game markets migration"
Cohesion: 0.70
Nodes (4): kalshi_game_markets_contract, kalshi_game_markets_date, kalshi_game_markets_event, public.kalshi_game_markets

### Community 726 - "Kalshi prop ladders migration"
Cohesion: 0.70
Nodes (4): kalshi_prop_ladders_prop, kalshi_prop_ladders_rung, kalshi_prop_ladders_snapshot, public.kalshi_prop_ladders

### Community 727 - "NCAAF QB game migration"
Cohesion: 0.70
Nodes (4): idx_ncaaf_qb_game, idx_ncaaf_qb_player, idx_ncaaf_qb_team, ncaaf_qb_game

### Community 729 - "Live game state schema"
Cohesion: 0.20
Nodes (9): v_live_game_state_latest, public.latest_lines_rebuild_live_state(), idx_live_state_game, idx_live_state_snapshot, idx_live_trigger_game, idx_live_trigger_pending, live_game_state, live_trigger_events (+1 more)

### Community 731 - "Mobile app build scripts"
Cohesion: 0.25
Nodes (8): scripts, android, build:ios:preview, build:ios:production, ios, start, typecheck, web

### Community 754 - "NFL live model tables"
Cohesion: 0.60
Nodes (4): live_game_states_ts_idx, live_odds_snapshots_game_ts_idx, public.live_game_states, public.live_odds_snapshots

### Community 756 - "data/migrations/add_nhl_stats_views_2026_10_16.sql"
Cohesion: 0.24
Nodes (3): public.v_nhl_player_prop_odds, public.v_player_season_totals_nhl, public.v_team_season_totals_nhl

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

### Community 772 - "App error log migration"
Cohesion: 0.53
Nodes (4): app_errors, idx_app_errors_device_received, idx_app_errors_kind, idx_app_errors_received

### Community 882 - "Mobile developer tooling dependencies"
Cohesion: 0.29
Nodes (7): devDependencies, @babel/core, babel-plugin-module-resolver, babel-preset-expo, tsx, @types/react, typescript

### Community 929 - "Opening signals shadow table"
Cohesion: 0.70
Nodes (4): idx_opening_signals_date, idx_opening_signals_model, idx_opening_signals_settle, opening_signals

### Community 930 - "In-app feedback thread tables"
Cohesion: 0.40
Nodes (5): feedback_messages, feedback_threads, idx_feedback_messages_thread, idx_feedback_threads_device, idx_feedback_threads_status

### Community 935 - "Capper picks tables migration"
Cohesion: 0.60
Nodes (4): idx_capper_picks_status, public.capper_ingest_cursor, public.capper_messages, public.capper_picks

### Community 936 - "NBA 2026-27 rebuild write-up"
Cohesion: 0.08
Nodes (23): 1. Pre-registered bars (fixed 2026-10-15, before the first grid), 2. Data used (all in Supabase), 3. The market grid, 4.1 Game markets — closed for 2026-27, 4.2 First half / first quarter / team totals — closed for 2026-27, 4.3 Player props — one rule ships, 4.4 Player props — projection models (the NHL recipe), 4.5 The projection model on the worker's inputs only (+15 more)

### Community 151 - "docs/rules_evidence.md"
Cohesion: 0.07
Nodes (13): 'Decisions needed from you' is second person, never first, A model in config.MODELS with no FEATURE_MAP entry kills scoring for every sport, Every front-end change is reviewed by the UX designer agent before its PR opens, Gate the number that gets bet (cal_error_actionable), A health check must not gate on the thing that breaks, The settled live-prop record is zero bets, The Odds API returns x-requests-remaining on every response, including 401, How the pick rule was found: the NCAAF live loop delete-and-replaced every 45s (+5 more)

### Community 192 - "NFL game lines model write-up"
Cohesion: 0.11
Nodes (19): DataRegistry: source catalog with priority levels, scripts/edge_hunt.py: moneyline calibration clean, ML-vs-spread gap dead, Forecast validation (2026-08-15): rule holds at 57.09% under real day-3 error, Game totals model (consumes spread output as competitiveness), IngestOrchestrator: per-source fetch with no silent fallbacks, Middling does not clear vig, Moneyline derived from spread via fitted sigmoid, Oracle ceiling: perfect closing-line knowledge (+11 more)

### Community 213 - "nfl/live_model/README.md"
Cohesion: 0.10
Nodes (18): backtest/calibrate.py (the two gates), backtest/calibrate_props.py projection prop gate, check_feed_assumptions: automatic first-payload feed check, backtest/flow_eval.py flow test with control, Gate 1: win probability Brier 0.1654 PASS vs 0.20, Gate 2: total quantile coverage 1.26pp PASS vs 2.0pp, backtest/harness.py kill_verdict, NFL live model (two-stage engine) (+10 more)

### Community 227 - "docs: followups + clv"
Cohesion: 0.08
Nodes (26): Pruner keeps the opener AND the close per (proposition, book), clv_method = standard_v2 (PEDIGREE_CLV_METHODS), clv_standard_v2_2026_10_14.sql bulk rewrite, Secondary — market edge vs Pinnacle's fair close (market_clv_*), Power de-vig (bisection, 80 steps, k in [0.05, 12]), Primary CLV — same-book raw price (clv_pct, clv_pp, clv_beat_close), Same line, and the close bound, Which price is the bet — _bet_price_and_book and clv_bet_book (+18 more)

### Community 243 - "Model search findings and assessments"
Cohesion: 0.08
Nodes (13): scripts/ncaaf_search/, Live feature sensitivity (12.8pp median swing), mlb_live_total_runs (in-play total), Negative-binomial (NB1) tail, pregame_total_line feature (market anchor), Honest MLB signal is ~0.55-0.56 AUC, Live tuning panel (Models view), CollegeFootballData (CFBD) as primary source (+5 more)

### Community 246 - "docs: best_line + config_topology"
Cohesion: 0.10
Nodes (21): Book roles: fetched (LINE_SHOP_BOOKMAKERS) vs offered (BEST_LINE_BOOKMAKERS), DECIDE_ON_BEST_PRICE=0 restores DraftKings as the deciding price, Stage 2: decide, size and settle at the best price (picks.decision_*), _get_event_odds fetched DraftKings-only (MLB F5, UFC round totals), The live models join best-price deciding (2026-09-10), PREGAME_PRICE_MAX_AGE_MIN (180 min) on game-market reads, Scoring off another book's line (picks.line_book), BEST_LINE_EXCLUDE_BOOKMAKERS — unbettable books out of shopping (+13 more)

### Community 253 - "docs/history: learnings + build_state"
Cohesion: 0.09
Nodes (25): Data sources table (Odds API, SBR, MLB Stats API, Savant, Open-Meteo, NHL API, nba_api, ESPN, UFC CSV mirror, DataGolf), FanGraphs / pybaseball removed (IP-blocked); replaced by MLB Stats API + Savant, MLB_Basic.csv datawarehouse (2009-2025, 40,996 games; runline derived as -1.5), What's built (package tree) and what's not, AlphaPy rejected (deprecated, team-level only, defunct connectors), Team stats need at least 10 games before they stabilize, The go-live gate prevents going live on lucky backtests, Historical team-stat backfill uses {season}-01-01 as as_of_date (+17 more)

### Community 257 - "NFL in-play rushing and passing studies"
Cohesion: 0.09
Nodes (13): ncaaf_live_total 2025 in-play backtest, ncaaf_live_win_prob 2025 in-play backtest, Late-game leader moneyline at DraftKings, Publish backstop refuses pass-attempt overs, Accrued carries from ESPN core leaders, rush_attempt_pace model: one offset on the book's number, Pace ratio, In-play rushing-attempt UNDER on pace ratio >= 1.25 (+5 more)

### Community 258 - "NCAAF in-play model notes"
Cohesion: 0.14
Nodes (15): CFBD_MONTHLY_CALL_ALLOWANCE (Tier 4, 125k), Worker cannot reach site.api.espn.com (403); CFBD /scoreboard is the state source, ncaaf_live.gameday loop, Gate 1: win probability Brier 0.115 PASS vs 0.20, Gate 2: total shape 2.60pp FAIL vs 2.0pp, Market licenses from the calibration gates, LIVE_ODDS_MAX_AGE_SEC (180s) odds age bound, ncaaf_live_loop scheduler job (*/10 supervisor) (+7 more)

### Community 264 - "monitoring/static/dashboard.html"
Cohesion: 0.16
Nodes (26): Signalbase pipeline monitor dashboard page, dashboard.html ageNote(), dashboard.html callRow(), dashboard.html connect(), dashboard.html drawSeries(), dashboard.html drawTimeline(), dashboard.html flush(), dashboard.html ingestCalls() (+18 more)

### Community 286 - "Prop market and odds provider research"
Cohesion: 0.16
Nodes (18): scripts/nfl_prop_ladder_grade, scripts/verify_kalshi, Alternate coverage effectively begins in 2024, Anchored ladder graded: fails every clause, Provider comparison: Odds API, Kalshi, SportsGameOdds, OddsJam, Unabated, OpticOdds, 1.48M alternate-market rows already stored and unread, Kalshi (CFTC-regulated event contracts), Status: deferred, no code (as of the memo) (+10 more)

### Community 292 - "docs/sports/nhl.md"
Cohesion: 0.12
Nodes (22): NHL models code-complete, not yet trained (2026-06-13 snapshot), docs/nhl_clv_ev_assessment.md: the current CLV/EV grade of every NHL model, Per-game logs from the NHL stats API (team, goalie, skater) via data/ingestors/nhl_game_logs.py, Starting-goalie confirm via ESPN core probableStartingGoalie; game-model veto on Out/Doubtful, docs/nhl_market_research.md: six defects and the honest walk-forward, data/nhl_asof.py: one function rates goalies and teams as-of, strictly before the date, nhl_over_under is live as a rule: Pinnacle de-vigged vs the bettable books in the same fetch, NHL pipeline steps (results before settle, odds, stats, totals card, scoring, settlement) (+14 more)

### Community 309 - "NFL game lines model documentation"
Cohesion: 0.17
Nodes (18): Critical data defect: home/away sign flips in four books, Under rate falls ~0.41pp per day of forecast lead, data/odds_cache/ (~45,000 credits of snapshots), Open-Meteo (ERA5, issued forecasts, live forecasts) via data_ingest/weather.py, wind_speed_10m_previous_dayN is null before 2024-01-18, What does not work (backup QB, home dogs, cold unders, refs, rest, ...), scripts/replay_wind_card.py regression test, scripts/screen_books.py per-book integrity screen (+10 more)

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

### Community 372 - "docs/sports/mlb.md"
Cohesion: 0.13
Nodes (14): Batter prop models (hits, TB Poisson; HR logistic retired), Bulk feature loading: ~6 hours -> ~3 seconds per model, CalError requires min_samples=20 per bin, F5 O/U and RL priced off the first bettable book (DK returns 0 rows), The F5 sweep does not produce a threshold: 0.74 fired zero bets, one positive cell in fifty, Market-relative game gate (models/game_market_gate.py): no-vig fair, PASS-when-steamed, The honest MLB numbers: ~0.55-0.56 AUC, not 0.60-0.64, Read this before any number: the 2026-09-03 leak repair (+6 more)

### Community 374 - "docs/thresholds.md"
Cohesion: 0.15
Nodes (14): Min-history gate: >= 3 prior UFC fights or the fight is skipped, Breakeven is the mean DK implied probability of the bets taken, not 52.4%, The forward check on fresh quotes: the 73.5% never existed, mlb_live_total_runs on the bought 2025 in-play history (260,190 credits), The live calibration map (Platt a=0.8578, b=-0.0787, promote_external), mlb_live_total_runs cut 0.70 -> 0.72 (superseded 2026-09-10), nfl_opener_spread cut: |dev| 1.0 -> 2.0, gate 0.52 -> 0.55, nfl_prop_market: two side floors, over 6pp / under 5pp (+6 more)

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

### Community 432 - "Daily model quality and MLB totals docs"
Cohesion: 0.12
Nodes (17): Hybrid Pin-agreement filter on mlb_over_under bets, mlb_runline and mlb_over_under (paused), mlb_total_public_fade card (paper UNDER), Slate concentration guard (insert-time), F5 odds coverage (DK carries F5 ML only), clv_degradation check, model_quality_checks table, Daily model-quality monitor (+9 more)

### Community 441 - "docs/sports: ufc + golf"
Cohesion: 0.17
Nodes (12): DataGolf Scratch Plus as the sole golf source (not The Odds API), Five golf models (outright, top10, top20, make_cut, matchup), One games row per tournament, per-player picks FK to it (the MLB-prop pattern), Golf settlement: ties settle at full price as a win (v1), WD-before-cut NO_ACTION, ufc_moneyline CalErr 5.99% above the 5% gate; a retrain will not move it, Primary UFC data path is the Greco1899 CSV mirror (ufcstats behind Cloudflare), UFC: moneyline, total_rounds, method_of_victory (3-class, prob-only), Fighter name matching via slugify_fighter and config.UFC_NAME_ALIASES (+4 more)

### Community 444 - "mobile/docs/BILLING.md"
Cohesion: 0.18
Nodes (10): BILLING_ENABLED kill switch, IAP entitlement flow (configure -> purchase -> webhook -> subscriptions), has_app_access() supersedes has_active_subscription(), isEntitled() checks status AND period end, PaywallScreen (localized prices, restore, redeem), RevenueCat SDK and entitlement 'signals', scripts/verify_billing.ts (83 assertions), has_app_access() server-side check (+2 more)

### Community 451 - "NFL model bundle restore guide"
Cohesion: 0.16
Nodes (11): nfl/requirements.txt dependency set (pandas, numpy, pyarrow, requests, scipy, scikit-learn, lightgbm), Multi-layered leakage detection, The Odds API historical backfill (bet-time Tuesday 18:00 UTC; closing 10 min before kickoff clusters), The canonical write-up nfl_game_lines_model_system.md, data/credit_ledger.json spend/quota ledger, data/odds_cache/ keyed md5(date|regions|markets), data/raw/pbp_20XX.parquet not bundled; refetch from nflverse-data releases, data/processed/ (dev_long.parquet, book_screen.csv, feature matrix) (+3 more)

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

### Community 463 - "Probability calibration design notes"
Cohesion: 0.24
Nodes (14): models/honest_ev.gate and honest_probability, tracking/system_health._report_model_calibration, MODEL_OWN_EV_FLOOR and MODELS_ON_OWN_PROBABILITY for wind and opener, fetch_graded reads picks for NFL/NCAAF/UFC/rule models, GLOBAL_MIN_EV: 0.30 then 0.20, The go-live calibration gate never computed a real number, ncaaf_over_under Platt map demoted 2026-09-26, Per-model floors (#796) measured on the calibrated number (+6 more)

### Community 479 - "docs/live_betting.md"
Cohesion: 0.18
Nodes (13): The live calibration map: 126 of 150, and it does not close, BookMoveClock — the book has moved past a cap while our state has not changed, LOCK_LIVE_PICKS_AT_FIRST_SIGNAL — the first live BET per lane is the bet of record, The live staleness guards (data/live_quote_guard.py), Live cutoffs are re-derived every pass (tracking/live_calibration.py), LIVE_MAX_BETS_PER_WEEK is advisory, not a runtime cap, config.LIVE_MODELS — a separate registry from MODELS, live_pick_features — one row per lane, the first one, under its own SAVEPOINT (+5 more)

### Community 500 - "docs/sports/wnba.md"
Cohesion: 0.21
Nodes (13): Double-double is logistic, over-only, prob-only (COMPUTE_DD sentinel), NBA: 10 models live (moneyline + 9 props), O/U and spread blocked, NBA pipeline steps (odds, prop odds, stats local, scoring, settlement), stats.nba.com blocks datacenter IPs; team stats run on the local Task Scheduler job, WNBA results from the ESPN hidden API with core-API fallback, The wnba_over_under / wnba_spread sweep was leaked (latest snapshot had no pre-tipoff cutoff), WNBA models (moneyline + assists live; points/rebounds/threes/PRA/O/U/spread paused), WNBA pipeline responsibilities (odds, props, scoring, ESPN results, local game log and stats) (+5 more)

### Community 523 - "mobile/docs/AUTHENTICATION.md"
Cohesion: 0.24
Nodes (12): App Store guideline 4.8: Google on iOS requires Apple, AUTH_ENABLED kill switch, signalbase://auth-callback redirect URL, billingReady() requires AUTH_ENABLED, discordLinkReady() requires AUTH_ENABLED, RLS pre-flight: authenticated keeps full read access, SignInScreen (SignIn route), useAuth session store (+4 more)

### Community 558 - "Model artifact and health docs"
Cohesion: 0.24
Nodes (10): model_artifacts_load counts what it opened, model_artifacts table fallback restore, Three separate artifact questions, three separate failures, KNOWN_UNTRAINED — config models intentionally without artifacts, Pipeline-observability checks: refresh_pass_completion, refresh_pass_steps, signal_delivery, pick_label_integrity, pipeline_runs — the run ledger (tracking/run_ledger.py), Retrain Model workflow (retrain_model.yml), tracking/system_health.py — CRIT and WARN feed checks (Step 12) (+2 more)

### Community 560 - "docs/retrain_2026_plan.md"
Cohesion: 0.18
Nodes (12): scripts/paused_model_assessment, data.ingestors.baseball_savant_ingestor, models.trainer, F5 O/U and F5 RL paused: leak-mismatched, synthetic-line trained, NCAAF in-play season replay: -3.4% and -13.1%, No model has a cut that clears on the deployed artifact, batter_sb: opp_team_sb_allowed feature, Phase 0: train 2019-2024, holdout 2025 (+4 more)

### Community 592 - "Performance gauging and record views docs"
Cohesion: 0.14
Nodes (7): roi_collapse check, mv_scored_pick_outcomes (sweep matview), Official live date 2026-09-01, Retool port of Models and Ops, v_public_track_record (published record view), docs/followups.md, MLB pick volume efficiency assessment

### Community 594 - "Calibration and NFL wind opener tracking docs"
Cohesion: 0.16
Nodes (18): tracking.paper_tracker (_NFL_MODEL_MARKETS), scripts/nfl_rule_2026_track, tracking/opening_signals.capture_opening_signals, tracking.opening_report, tracking/opening_signals.settle_opening_signals, MAX_FIRE_LEAD = 4, nfl_opener_spread, nfl_wind_totals (+10 more)

### Community 603 - "docs/reviews/2026-09-07-nfl-props-deep-dive.md"
Cohesion: 0.33
Nodes (7): Twelve artifacts committed from a replica failed pickle.load unnoticed for two weeks, The eleven NFL projection prop models, unpaused on placeholder thresholds, nfl_prop_market: the de-vig rule (Pinnacle as truth, equal lines only), The scorer is pinned to today, the card looks ten days ahead, 112 bets on one Sunday from untuned models; 41-46% BET rates are placeholders, Eleven NFL distributional props paused 2026-09-14, NFL props deep dive — two lanes, one of them can't see the slate (2026-09-07)

### Community 624 - "NFL wind totals runbook and staking"
Cohesion: 0.36
Nodes (7): DOCUMENT STATUS block: superseded claims indexed, Under rate by forecast lead 1-7 (~0.41pp per day), Original staking: 25% Kelly capped at 3% (superseded), Kelly-proportional units with slate shading 1/sqrt(1+(k-1)rho), Stops: 2 units per bet, 3 units per slate, review at -15 units, Runbook: Wind Totals, scripts/stake_sizing.py: 1 unit = 1% of bankroll

### Community 627 - "docs/market_coverage.md"
Cohesion: 0.36
Nodes (7): ncaaf_prop_odds_ingestor and its probe, test_the_mlb_board_and_the_mlb_pull_are_one_set, MLB probe 2026-09-05 — served, unsupported and unpriced keys, NCAAF prune — FOOTBALL_MARKET_NOT_PRICED per league, scripts/probe_market_coverage.py — one market per call, writes nothing, Neither prop ingestor writes to api_call_log, Prop market coverage — what the feed actually serves

### Community 652 - "(root): pr-ci + requirements"
Cohesion: 0.33
Nodes (5): Mobile thresholds drift check (generate_mobile_thresholds --check), NFL preflight --ci, PR CI workflow — non-integration pytest subset, Render blueprint — betting-scheduler background worker, requirements.txt — >= pins for Python 3.14 wheels

### Community 66 - "NFL props sources and prediction market research"
Cohesion: 0.09
Nodes (27): scripts/nfl_prop_market_card, scripts/nfl_prop_replay, tackles_assists +21% is a measurement error (control), Traps specific to props, Anytime TD field de-vig: closed, #215 artifacts could not be deserialised, betonlineag as a second sharp reference (OR, not AND), Book census: 14 books served, 6 used (+19 more)

### Community 710 - "mobile/docs/BILLING.md"
Cohesion: 1.00
Nodes (4): useEntitlement() access gate (subscription OR Discord), useSubscription() subscription-only state, useEntitlement(), not useSubscription(), Access is one gate: useEntitlement(), never useSubscription().entitled

### Community 720 - "docs/testing.md"
Cohesion: 0.67
Nodes (3): PR CI runs a non-integration pytest subset, Pure function tests, in-memory SQLite via conftest, Test suite (testing.md)

### Community 81 - "docs: nhl_market_lab + nhl_clv_ev_assessment"
Cohesion: 0.09
Nodes (34): scripts/nhl_derivative_totals_backtest, data/ingestors/nhl_derivative_odds_history, models/nhl_props.py (Spec per market), Anytime goalscorer: not a candidate once names corrected, nhl_moneyline and nhl_moneyline_regulation: no cut clears, Team-total under flips sign between regulation and full-game goals, Anytime scorer at the best book: not trusted, The borrowed probability correction (promoted_b -0.259947) (+26 more)

### Community 890 - "docs/game_injury_gate.md"
Cohesion: 0.40
Nodes (5): ESPN core probables for the NHL starting goalie, A NONE from this gate is not locked — the reprice path, The gate rule — refuse a game-model BET on a confirmed Out starter/star/goalie, Fires in scorer.score_game and _score_nhl_3way, after best-price requalify, before insert, Game-model starter / star / goalie gate

## Ambiguous Edges - Review These
- `Claim: the app cannot write to the backend` → `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`  [AMBIGUOUS]
  docs/privacy.html · relation: conceptually_related_to

## Knowledge Gaps
- **105 isolated node(s):** `expo/tsconfig.base`, `RFC-4122`, `@babel/core`, `babel-plugin-module-resolver`, `babel-preset-expo` (+100 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 12386 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **210 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Table` connect `NBA public splits pipeline step` to `Scratch Postgres line state tests`, `Mobile color contrast checker`?**
  _High betweenness centrality (0.203) - this node is a cross-community bridge._
- **What connects `expo/tsconfig.base`, `RFC-4122`, `@babel/core` to the rest of the system?**
  _105 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Mobile app screens and theme` be split into smaller, more focused modules?**
  _Cohesion score 0.014636591478696741 - nodes in this community are weakly interconnected._
- **Why does `over()` connect `Mobile color contrast checker` to `Mobile bankroll number formatting checks`, `NBA public splits pipeline step`?**
  _High betweenness centrality (0.162) - this node is a cross-community bridge._
- **Should `Mobile picks home filters and sorting` be split into smaller, more focused modules?**
  _Cohesion score 0.021501744906000226 - nodes in this community are weakly interconnected._
- **Why does `inserted_minus_start_min()` connect `NBA public splits pipeline step` to `NBA public betting splits ingestion`, `NBA public betting splits ingestor`?**
  _High betweenness centrality (0.115) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Claim: the app cannot write to the backend` and `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._