# Graph Report - bm-nba-propcap  (2026-10-20)

## Corpus Check
- Large corpus: 1613 files · ~2,670,630 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 31927 nodes · 76352 edges · 942 communities (744 shown, 198 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 1971 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e2e46896`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Mobile app screens and theme
- Discord pick and live signal notifier
- Mobile stats board
- NBA player prop model fitting
- NFL ESPN live feed resilience
- NBA totals luck model decision tests
- tests/test_nfl_live_leader_gameday.py
- nfl_live_leader/gameday.py
- tests/test_calibration_promotion.py
- tests/test_score_off_any_book_line.py
- Mobile pick list filters and sorting
- tests/test_ncaaf_alias_scores.py
- Alternate prop line fetching tests
- tests/test_backtester.py
- NHL prop EV research lab
- NFL in-play odds client and smoke check
- NBA prop market lab
- Discord pick notifier tests
- nfl/live_model/tests/test_backup_snaps.py
- Pipeline report rollback tests
- mobile/scripts: verify_book_links + verify_betslip_combine
- NBA injury report PDF dedupe tests
- tests/test_paused_keeps_real_verdict.py
- mobile/scripts/verify_contrast_tokens.ts
- Manual social post queue tests
- Pick lock after settlement tests
- NBA game line move study
- tests/test_mlb_game_market.py
- NBA game four part two study
- X results and free pick posts
- Threshold review core tests
- Idle read transaction tests
- UFC phantom fight filter
- Prop box score backfill
- NBA game model prop feature tests
- MLB in-play scorer and inning gate
- Best line price shopping tests
- Per-model EV floor gate
- Player name matching for props
- tests/test_nfl_opener.py
- NHL stats ingestor and opening night
- Mobile crash logging
- NBA game model luck feature tests
- CLV math same-book and market edge
- NBA team total luck pick card
- Push notifications and publisher lock
- tests/test_dk_direct_feed.py
- tests/test_credit_budget.py
- Odds table pruning with time budget
- Mobile daily results recap
- Feature engine and line sweeps
- NHL prop card and blocked shots
- tests/test_first_signal_repair.py
- Game injury gate and prop veto
- Outbound call probe recording tests
- Prop price pregame cutoff tests
- Mobile markets and formatting
- Pregame line poller change detection tests
- tests/test_nhl_asof.py
- NFL wind publisher and line snapshots
- NFL in-play game state feed
- Mobile range slider filter
- data/ingestors/nfl_inplay_history.py
- Mobile record hero and equity curve
- Mobile billing and paywall
- Mobile bankroll storage and settings card
- Prop over probability ladder
- Market-anchored offset logistic fit
- NCAAF in-play pricing engine
- Mobile push test diagnostics
- NBA prop projection card
- tests/test_db_reconnect.py
- Discord recap restatement
- In-play scorer locks and push alerts
- tests/test_refresh_retry.py
- NBA results ingestion
- NBA results ingestor tests
- NBA second game projection study
- tests/test_local_cache_is_additive.py
- tests/test_calibration_check_coverage.py
- NBA injury report PDF parsing
- tests/test_book_team_map.py
- NCAAF game features and FBS registry
- NCAAF in-play total repricing engine
- NFL wind board fast publishing tests
- Mobile picks queries and Discord status
- Mobile Discord link and access
- NHL team rates as of a date
- tests/test_dk_freshness_parse.py
- NHL moneyline and market labs
- models: slate_concentration + test_slate_concentration
- View migration lock handling tests
- In-play stale score quote guard
- NFL closing line value backtest features
- Mobile performance and tracked bets
- NBA game four point estimates
- Best line threshold sweep
- NCAAF game-day twin game handling
- NCAAF college data ingest tests
- Mobile betslip and parlay legs
- NBA pregame scoring window
- Line CLV sign and orientation tests
- tests/test_prop_odds_utc_stamp.py
- Live monitor web server streaming
- NCAAF opener strategy walk-forward search
- tests/test_feature_artifact_agreement.py
- NFL prop one side per line
- CLV graded at the price taken
- tests/test_cloud_retrain_artifacts.py
- NHL side models never bet against each other
- NFL prop Kalshi ladder pricing tests
- System health checks and record reconciliation
- tests/test_nfl_opener.py
- Player news ingest from ESPN
- Mobile in-app purchase billing
- NHL blocked shots prop model
- tests/test_nfl_wind_publisher.py
- Odds and prop odds ingestion
- NFL in-play game-day worker
- tests/test_health_reason_and_cadence.py
- NBA odds history gap fetch tests
- tests/test_nfl_weather_supabase_readback.py
- Publish signals on write tests
- Pitcher stats as-of invariant tests
- NBA prop market card and bet finder
- NHL prop per-game limit tests
- Pipeline log reason tests
- NFL in-play score distribution engine
- NBA in-game study two
- NFL scored rows preflight database fake
- NFL in-play prop settlement tests
- Odds pruning time budget tests
- NBA prop and total fetch window tests
- NFL pick publisher lookahead tests
- Mobile error text and load states
- NFL opener publisher tests
- NHL player prop projection model
- CLV settlement timeout retry tests
- Health check skip budget tests
- Live pick features and paused rows tests
- Model quality monitor checks
- Pregame price age and twin game tests
- tests/test_prop_missing_features.py
- MLB public fade top picks ranking
- NFL in-play decline recorder tests
- NFL wind scored row building
- NBA prop settlement stats
- NCAAF live state recording tests
- tests/test_run_ledger_orphans.py
- MLB in-play history backtest
- NHL anchored moneyline tests
- NBA lineup stints from play-by-play
- UFC results scraper tests
- In-play calibrated decision tests
- Team total market skip rules tests
- Pregame pick scorer and bet insertion
- Sharp book odds retention
- Eastern time dates and schema guards
- NCAAF opponent-adjusted search features
- MLB first five any-book line tests
- tests/test_repair_bogus_first_pitch_labels.py
- nfl/live_model/tests/test_executor.py
- NBA injury report daily runner
- tests/test_sbr_loader.py
- Walk-forward evaluation
- mobile/scripts/ux_scan.mts
- tests/test_live_quote_staleness.py
- NBA prop closing line purchase tests
- In-play publish parity with pauses
- Network timeouts and health probes
- supabase/functions/_shared/discord.ts
- Worker job queue validation tests
- Fake database for team total odds tests
- X post image uploads
- NBA totals luck replay graders
- NCAAF game-day pick lock tests
- scripts: build_nfl_live_leader_artifact + model
- NFL DraftKings line snapshot capture
- Run ledger and schema change guard
- tests/test_discord_channel_probe.py
- tests/test_nfl_prop_one_read_per_game.py
- Bounded odds pruning keeps openers and close
- NFL pass attempt bias model
- NFL historical weather fetch
- Mobile push notification routing
- Mobile settings, sign-in and sportsbooks
- Multi-book odds ingestion
- scripts/nfl_edge_gameline_rules.py
- System health check pass tests
- tests/test_model_game_savepoint.py
- Health check pick delivery tests
- NBA historical odds archive loader
- MLB batter prop log lookback tests
- tests/test_calibration_watch.py
- Probability calibration fitting and sweep
- Ungraded model performance reporting tests
- MLB prop market pre-game tests
- Pipeline failure alerting and heartbeats
- NCAAF starter-out research dataset
- Score when lines open tests
- Discord void notices and publish keys
- tests/test_sbr_loader.py
- NHL totals card publishing tests
- Dashboard queries and SQL file runner
- MLB in-play state alignment
- Member sportsbooks scratch database tests
- tests/test_nhl_three_way_lookahead.py
- Mobile team stats board and odds
- Game scorer, Kelly sizing and backtester
- Prop odds next-day lookahead tests
- Team stats thin season checks
- System health run ledger tests
- NCAAF in-play history ingest tests
- Weather forecast hour lookahead
- tests/test_best_line_live.py
- tests/test_sbr_loader.py
- NCAAF college data refresh and backfill tests
- UFC fight stats scoring tests
- NBA prop card publishing tests
- NBA team total odds fetch tests
- NFL prop settlement tests
- NFL in-play pick row builder
- tests/test_void_picks.py
- tests/test_sbr_loader.py
- Job heartbeat and stale jobs
- Database setup and SQL statement splitting
- NCAAF game-day live loop and feeds
- NFL prop odds and backtest
- MLB renamed franchise game merge tests
- Team board cache refresh step
- NBA box score repair tests
- Health check daily feed freshness
- tests/test_sbr_loader.py
- Injury adjustment scenario tests
- tests/test_daily_retry.py
- Discord results recap message tracking
- NFL prop market card publisher tests
- NFL prop sharp devig bet finder
- NBA line history pruning protection
- Push line change alert tests
- tests/test_live_book_move_guard.py
- NHL prop settlement tests
- tests/test_weekly_catch_up.py
- tests/test_sbr_loader.py
- MLB umpire ingestor
- NFL pick game id join tests
- NFL pick monitor
- In-play score change clock
- NFL wind forecast and totals model
- Prop odds missing game skip
- Shared scripts using JSON and environment
- System health check test fixtures
- Mobile model catalog, filters and thresholds
- NFL in-play pick writer commit tests
- MLB stats and pitcher ingestor
- supabase/functions/revenuecat-webhook/index.ts
- supabase/functions/whop-webhook/index.ts
- tests/test_nfl_props.py
- tests/test_sbr_loader.py
- Football in-play game state
- NHL blocked shots prop settlement tests
- Threshold review schema setup tests
- Game feature engine helper tests
- MLB prop umpire feature retirement
- NCAAF game-day fetch cadence tests
- tests/test_nfl_props.py
- NFL wind bettable book filter
- Mobile subscription entitlement
- WNBA injury team id fallback
- Odds API credit budget
- Mobile bankroll local store
- Prop pricing, devig and player names
- Pick integrity test database shim
- tests/test_game_market_gate.py
- Team total market settlement tests
- NBA public splits quality backfill
- NFL prop market card tests
- NBA second-model prop study
- tests/test_score_when_lines_open.py
- tests/test_score_when_lines_open.py
- tests/test_score_when_lines_open.py
- Probability calibration fitting tests
- tests/test_pick_integrity.py
- NHL props one bet per game
- NHL props newest fetch shopping
- NBA public splits archive store tests
- Mobile bankroll unit size stepper
- NFL leader five-minute evaluation grid
- Pick settlement and CLV capture
- tests/test_record_one_pick_per_event.py
- NFL wind and opener publishing
- Scheduler catch-up of weekly jobs
- NBA results test connection fake
- NHL game features and starter injuries
- Dead NHL wrapper import cleanup tests
- Free pick and X results publishing tests
- NFL in-play pick audit recorder
- nfl/live_model/tests: test_props + props
- NFL opener tick latency tests
- Deploy checks and job queue
- tests/test_wnba_prop_market.py
- tests/test_nfl_scored_rows.py
- NHL derivative totals walk-forward model
- Prop no-bet rows tipoff tests
- Mobile player log and matchup stats
- tests/test_nhl_props.py
- NBA team total luck replay study
- Prop odds book update time
- tests/test_recap_retries_a_skipped_day.py
- NHL derivative odds history purchase
- Mixed pipeline and prop tests
- NHL stale team log detection
- NFL line snapshot publishing tests
- Live game poller no-op connection
- Opposing starter loader stub connection
- NBA offset ridge regression
- NHL blocked shots player placement
- NHL prop four per night cap
- Pregame prices current health test stub
- NBA prop market decision tests
- NHL opening night goalie lookup
- MLB public fade empty connection stub
- Pipeline watch reporting and ledger
- Mobile Lines board on Picks
- Mobile matchup grading and stat pills
- NBA team total odds fake feed
- Savant freshness health check tests
- NFL evaluation rows carry lines
- Single tweet delivery attempt
- NBA injury report date scope
- Social posts test row fake
- NHL blocked shots DNP settlement
- tests/test_ncaaf_prop_odds.py
- NBA game residual distribution
- Command-line research scripts
- Weekly catch-up cursor fake
- NFL wind publisher lock tests
- Social post queue and drain
- NFL opener fire window timing
- tests/test_ncaaf_pbp_store.py
- tests/test_heartbeat_watchdog.py
- Discord pick price and field rendering
- Record correction posts to Discord and X
- Odds pruning opener and close tests
- scripts/nfl_edge_live_rush_pace.py
- NBA prop projection tests
- Kalshi ladder and game ingestors
- NBA game market feature study
- tests/test_prop_calibrated_decision.py
- NCAAF in-play quote serving
- NBA fourth search derivative markets
- tests/test_mobile_line_movement.py
- tests/test_live_calibration.py
- NBA in-game luck study one
- NBA lineup stint derivation tests
- NBA play-by-play parsing tests
- tests/test_ncaaf_live_notify.py
- NCAAF quarterback team features
- Live monitor dashboard data store
- Prop book sweep bettability guard
- tests/test_settled_record_is_immutable.py
- features/golf_feature_engine.py
- ncaaf_live/tests/test_states.py
- tests/test_bovada_feed.py
- NCAAF cross-book opener model
- NFL in-play edge season replays
- NBA team total under model tests
- tests/test_health_pregame_prices_current.py
- WNBA prop feature building
- scripts/nfl_edge_extreme_props.py
- scripts/nfl_edge_settlement.py
- tests/test_agents_contract.py
- WNBA results ingestor
- NBA public betting splits ingestor
- NBA stats and box score ingestor
- NBA derivative market lab
- scripts/nfl_preflight.py
- Mobile live and deep link source checks
- NBA halftime in-game research
- NFL luck gap edge study
- tests/test_decide_on_calibrated.py
- NBA prop projection lab
- NBA in-game play data and staleness
- tests/test_model_artifacts_load.py
- Model quality alerts monitor
- scripts/game_line_market_sweep.py
- NHL prop backtest and namesakes
- NFL 2025 in-play edge study
- tests/test_pass_instrumentation.py
- Team stats games played invariants
- tests/test_db_adapt_sql.py
- Market-relative prop edge tests
- tests/test_mobile_contrast_tokens.py
- Daily pipeline runner and steps
- NBA game four part one tests
- Shared config and database scripts
- NBA second game line move tests
- Mobile live game status checks
- NBA box score row building tests
- NFL prop 2026 remeasure pins
- Intraday refresh freshness skipping
- tests/test_nfl_live_leader_state.py
- tests/test_ncaaf_qb_ingestor.py
- NFL in-play win probability hypotheses
- NBA public splits parsing tests
- tests/test_team_board_cache.py
- House juice price floor tests
- nfl/live_model/tests/test_rush_attempt_pace.py
- tests/test_ncaaf_game_identity.py
- NBA second game market tests
- Live feed probes and game polling
- NBA second game projection fixtures
- NBA game model research harness
- NBA boxscore enrichment ingest
- NFL halftime out-of-sample study
- UFC results download caching
- Signal publishing and push pipeline steps
- NBA game total luck pick card
- tests/test_live_game_features.py
- UFC fight feature builder
- Node-run mobile source tests
- NBA quarter game model tests
- NBA second game luck studies
- Mobile player stat group tests
- NBA game harness tests
- UFC fight results scraper
- Push notification delivery tickets
- NCAAF opener rule board tests
- Kalshi prop ladder recording
- Model calibration check tests
- NCAAF college data ingestor
- Team stats as-of invariants tests
- Historical odds backfill and API rollup tests
- NCAAF player stats parser tests
- Discord and X results posting
- scripts/nfl_live_prop_feasibility.py
- tests/test_context_budget.py
- tests/test_player_h2h_stat_values_migration.py
- tests/test_retired_models.py
- Prop box score gap filling
- Signal delivery window health tests
- Mobile sport filter chips
- Scratch Postgres migration test harness
- tests/test_live_record_start_views.py
- UFC historical CSV loader
- NHL prop odds fetch gate
- NFL Kalshi edge search
- nfl/models/opener_spread.py
- Mobile bankroll settings card
- tests/test_nfl_wind_fire_window.py
- tests/test_public_betting_ingestor.py
- Basketball player positions ingestor
- tests/test_service_role_split.py
- Kalshi prop ladders and game markets
- NCAAF weather totals walk-forward fit
- NFL research edge data cache
- NFL weather cache import into database
- NBA second game projection tests
- Live game state poller triggers
- Team stats history rebuild and verify
- College football rating matrix and QB priors
- Custom model game facts builder
- NBA period map pricing tests
- NCAAF CFBD ingestor tests
- Mobile screen source wiring tests
- Kalshi game market recorder
- Database URL doctor tests
- NCAAF totals probability regression tests
- NFL stale wind card cleanup
- Refresh pass step ordering tests
- Team hashtags for X posts
- NFL in-play pick writer
- tests/test_mobile_threshold_parity.py
- NHL derivative odds job validation tests
- tests/test_track_record_views.py
- tests/test_weekly_catch_up.py
- MLB public fade top-k holdout study
- Mobile team detail page tests
- NFL live leader model tests
- NFL prop settlement name matching
- NFL wind and teaser edge research
- Mobile paused catalog tests
- X posting and brand avatar
- MLB play-by-play ingestor
- tests/test_promote_calibration_job.py
- tests/test_cfbd_snapshot_leakage.py
- NFL wind forecast stability tests
- NFL opener cut sweep and calibration
- Mobile bankroll field tests
- NCAAF outcome edge scan
- tests/test_nfl_prop_thresholds.py
- tests/test_nhl_research_job.py
- tests/test_settlement_timing.py
- NBA schedule rest and travel features
- CLV card at the price taken
- ESPN injury fetch and NFL ingest
- DataGolf ingestor and NHL SBR archive
- Mobile pick category tests
- Picks unique row index tests
- NFL odds cache import to Supabase
- tests/test_health_check_observe.py
- NFL in-play prop flow validation
- NFL 2026 opener and wind tracker
- Published record views reconciliation
- tests/test_pick_lock_is_on_picks.py
- MLB prop feature engine
- Per-model threshold config tests
- NBA game two verdict grid tests
- Script entrypoint structure checks
- NCAAF in-play odds history pull
- MLB retrain freeze guard
- NCAAF board visibility scorer tests
- supabase/functions/discord-link/index.ts
- tests/test_nfl_prop_clv.py
- tests/test_scoring_methods.py
- NBA game model phase one checks
- UFC fighter name slugs and aliases
- Worker job queue runner
- Discord and X period recaps
- Anonymous read and grant sweep tests
- NCAAF in-play odds polling cadence
- nfl/scripts/backtest_opener.py
- NCAAF totals lead and consensus gate
- tests/test_latest_odds_views.py
- NBA schedule ingestor
- tests/test_transaction_pooler.py
- NBA injury report pull and storage
- MLB totals retrain sweep job tests
- Position defense ranks matchup
- Trainer no-register mode tests
- NBA inactives, officials and advanced box
- NCAAF in-play game state building
- Env file database URL fallback
- supabase/functions/sharpsports/index.ts
- Rule model market reading tests
- NCAAF quarterback change features
- tests/test_worker_deps.py
- scheduler.py
- Mobile stat segment tabs tests
- tests/test_mobile_stat_labels_match_the_server.py
- tests/test_ncaaf_fcs_visitor_names_migration.py
- tests/test_nfl_prop_unstarted_clear.py
- Numeric research labs and staking
- tests/test_savant_freshness.py
- tests/test_scorer_nfl_prop_like_escape.py
- NHL stats views tests
- Paid NFL odds file importer
- Market movement feature builder
- NFL prop per-side edge cut
- NCAAF opener and close pull from CFBD
- NBA injury report time slots
- NFL in-play pick writer safety tests
- tests/test_clear_unauthorized_auto_pauses_migration.py
- tests/test_ncaaf_se_louisiana_alias_migration.py
- NFL in-play leader model decision
- tests/test_overnight_polling.py
- NCAAF steam lag study
- NCAAF weather and wind totals study
- Mobile type-check baseline tests
- NFL prop feature research scripts
- Tracked performance verification script
- NBA public splits consensus parsing
- Live monitor cache tests
- No-vig closing line capture tests
- tests/test_claude_rules_split.py
- tests/test_db_setup.py
- tests/test_dedupe_opening_signals.py
- tests/test_pbp_backfill_resilience.py
- First pitch guard tests
- Paused model profitability assessment
- NCAAF game-day loop cadence
- NBA in-game study one tests
- NCAAF quarterback ablation study
- NCAAF line move spots
- NBA public splits pipeline step
- tests/test_prompt_reads_thresholds.py
- tests/test_system_health_meta_steps.py
- NBA period score ingestion
- NFL preregistered 2026 edge study
- scripts/render_brand_icons.py
- NHL game results parsing
- NBA prop model verification stages
- supabase/functions/stripe-webhook/index.ts
- tests/test_drop_voided_nfl_wind_opening_signals_migration.py
- NFL backfill retry resilience
- tests/test_mobile_neutral_signal_label.py
- College football data checks
- tests/test_scorer_commits_per_game.py
- NFL model import checks
- NBA ESPN box score parsing
- NFL box scores before recap
- tests: test_wnba_availability + wnba_availability
- NCAAF in-play candidate grading
- NCAAF cross-book opener guard tests
- NFL prop scoring window tests
- supabase/functions/sharpsports-webhook: index + index
- Mobile Lines board pin tests
- supabase/functions/stripe-checkout/index.ts
- tests/test_book_list_budget.py
- NFL 2026 track policy pins
- Mobile type-check baseline checker
- NBA game market search lab
- NFL prop backtest universe summary
- NCAAF opener timestamp gap checks
- NCAAF in-play DraftKings qualifying gate
- NCAAF consensus gate frame builder
- NBA prop fetch game scope test
- Shared pytest SQL and harness checks
- mobile/scripts/verify_a11y.ts
- NCAAF in-play history credit sharding
- NFL in-play prop calibration dataset
- Postgres scripts and grant revokes
- NFL in-play two-sided offer grid
- tests/test_demote_ncaaf_over_under_platt.py
- tests/test_discord_post_one_pick_migration.py
- tests/test_game_scorer_spares_nfl_props.py
- NBA injury report player matching
- NFL in-play score distribution pricing
- Mobile quiet update download tests
- NBA team total luck replay
- NFL Kalshi price history fetch
- X client posting safety tests
- NBA prop model research lab
- Mobile stats filter UX verify
- NFL prop pulled quote filter
- Duplicate pick exclusion across records
- NBA box score spot checks
- NFL prop too-early kickoff ceiling
- SBR CSV loader and abbreviations
- NFL in-play edge replication tables
- Worker-only table lockdown tests
- Voided NFL prop opening signals cleanup
- Game log backfill skip tests
- Scorer keeps off-DraftKings priced bets tests
- Row-level security lockdown order tests
- UFC mirror ETag cache store
- NCAAF situational spot scans
- App-readable table manifest
- Manual X account posts guide
- Every named sportsbook is fetched
- NBA injury report slot retries
- NBA harness cell emission fakes
- UFC fight stats scraping
- tests/test_weekly_catch_up.py
- NBA prop pipeline steps
- In-play trigger orchestrator and odds fetch
- NCAAF scoreboard yardline parsing
- NBA splits game date mapping
- Mobile accessibility verify script
- Market handicap feature tests
- mobile/scripts/verify_a11y.ts
- mobile/scripts/verify_a11y.ts
- Mobile NHL Today look-ahead tests
- NBA splits row quality flag rule
- Prop CLV and SQL escaping tests
- mobile/scripts/verify_a11y.ts
- NCAAF margin and totals evaluation
- Anonymous read grant apply script
- ncaaf_live/tests/test_serve.py
- Per-model EV floor card tests
- Mobile screen checks run from Python
- First-time setup and full backtest
- Model training and WNBA points rebuild
- Market coverage probe tests
- No record-only mode guard tests
- Time-ordered cross validation
- Pandas research scripts and dtype tests
- NFL research files backup to Supabase
- NBA injury report name matching
- NBA game outcome probability harness
- UFC results skip-unchanged check
- Pitcher rolling prop stats
- NHL box score parsing
- tests/test_team_board_commence_bound.py
- Injury return ramp players
- Golf pipeline steps
- NHL derivative totals card stub
- In-memory test database fixture
- NBA projection price cache checks
- NBA prop decisions ledger guard test
- NBA results game window
- Unapplied facts tables grant guard
- NFL in-play pick date and announce tests
- Team stats live season check test
- mobile/scripts/verify_a11y.ts
- Team stats season boundary tolerance
- NFL in-play two players one game
- Team stats as-of date normalizing
- Team stats MLB twin alias check
- Pipeline credit burn findings
- Units won convention
- Pipeline watch announce and escalation
- NCAAF school name slug matching
- NCAAF CFBD monthly call budget
- Discord paused model quiet logging
- UFC stats event list parsing
- NCAAF play-by-play season pull
- NCAAF CFBD stats parsing
- Calibration eligibility notes parsing test
- NFL in-play backtest replay harness
- NCAAF state build output naming
- Team stats series season refusal
- NCAAF game-day early exit guard
- Pipeline pass failure findings
- App RPC declaration guard
- NCAAF pregame calibration test fixture
- Failed prune reported as failed step
- MLB totals public fade tests
- Public splits side flipping
- NHL goalie saves above expected
- Database service role split
- NBA splits preseason skip test
- Recap delivery failure findings
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
- NFL kickoff wind reads migration
- Unmatched player positions table
- Mobile app build scripts
- Mobile dev dependencies
- Opening signals shadow table
- In-app feedback thread tables
- Social post queue migration
- NBA 2026-27 rebuild write-up
- docs/rules_evidence.md
- NFL game lines model write-up
- nfl/live_model/README.md
- docs: followups + clv
- docs: best_line + config_topology
- docs/history: learnings + build_state
- Prop markets and odds provider research
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
- NFL prop and in-play research notes
- .claude/rules/operations.md
- docs/live_odds_freshness.md
- mobile/docs/UX_REVIEW.md
- Model quality monitor and MLB totals docs
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
- Model artifact integrity and health docs
- docs/retrain_2026_plan.md
- Probability calibration documentation
- NCAAF model search plan and findings
- docs/reviews/2026-09-07-nfl-props-deep-dive.md
- All-model state assessment snapshot
- docs/market_coverage.md
- (root): pr-ci + requirements
- NFL props sources and prediction market research
- NFL wind totals runbook and staking
- Opening-signal shadow track design
- mobile/docs/BILLING.md
- docs/testing.md
- CLAUDE.md
- Analysis protocol and backtest notes
- docs: nhl_market_lab + nhl_clv_ev_assessment
- Cross-book opener search findings
- NFL opener sharp-vs-soft findings
- docs/game_injury_gate.md

## God Nodes (most connected - your core abstractions)
1. `get_connection()` - 640 edges
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
- `What is captured` --references--> `AppErrorBoundary`  [INFERRED]
  docs/app_errors.md → mobile/src/components/AppErrorBoundary.tsx
- `8.1 P1, the market-anchored model: choices fixed before any P1 cell was graded (2026-10-18)` --references--> `choose_C()`  [INFERRED]
  docs/nba_models_2026.md → models/nhl_moneyline_anchored.py
- `IG-1: how the lab reads the row above (2026-10-17, written before any IG-1 number)` --references--> `run_cells()`  [INFERRED]
  docs/nba_models_2026.md → scripts/nba_game_harness.py
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

## Communities (942 total, 198 thin omitted)

### Community 5 - "Mobile app screens and theme"
Cohesion: 0.02
Nodes (286): AppErrorBoundary, IoniconName, Props, Props, State, Nav, Props, Props (+278 more)

### Community 0 - "Discord pick and live signal notifier"
Cohesion: 0.02
Nodes (84): DiscordVoidRejected, _Posted, _Rejected, UnitStake, test_american_odds_formatting(), test_empty_set_errors_when_a_stale_pause_flag_hides_bets(), execute(), test_free_pick_does_not_fall_back_to_the_default_channel() (+76 more)

### Community 1 - "Mobile stats board"
Cohesion: 0.01
Nodes (458): P, TouchSet, PlayerPropQuote, Sport, AnytimeMatchupView, AnytimeSortRow, DefenseRank, gapReason (+450 more)

### Community 10 - "NBA player prop model fitting"
Cohesion: 0.03
Nodes (78): Spec, compact_report(), minutes_cols(), predict_means(), rate_cols(), alias_key(), all_rates(), _attach_report_ids() (+70 more)

### Community 101 - "NFL ESPN live feed resilience"
Cohesion: 0.04
Nodes (53): _ScriptedTick, _competitors(), _deref(), fetch_live_events(), _https(), make_fetcher(), fetch(), parse_core_event() (+45 more)

### Community 11 - "NBA totals luck model decision tests"
Cohesion: 0.04
Nodes (60): Decision, TotalLuckBet, _Conn, _Cur, quote_frame(), pick_label(), pick_rows(), _bet() (+52 more)

### Community 113 - "tests/test_nfl_live_leader_gameday.py"
Cohesion: 0.05
Nodes (33): FakeClient, FakeClock, FakeConn, FakeFeed, _Rows, art(), live_state(), quote_payload() (+25 more)

### Community 114 - "nfl_live_leader/gameday.py"
Cohesion: 0.06
Nodes (28): GameContext, LiveOddsFeed, Quote, LiveState, release_read(), parse_book_ts(), quote_predates_score(), build_pick() (+20 more)

### Community 115 - "tests/test_calibration_promotion.py"
Cohesion: 0.07
Nodes (25): FakeConn, eligibility_clause(), maps_materially_differ(), promote(), _payload(), _row(), test_a_broken_table_is_identity_maps_not_an_exception(), test_a_map_that_does_not_help_is_silent() (+17 more)

### Community 116 - "tests/test_score_off_any_book_line.py"
Cohesion: 0.08
Nodes (33): _FakeConn, _fallback_line_quote(), _cut(), _on(), _pick(), _row(), _sql_const(), _src() (+25 more)

### Community 12 - "Mobile pick list filters and sorting"
Cohesion: 0.02
Nodes (136): P, ActivePill, Props, DateOption, DayRow, SelectableGame, modelCategory, FilterablePick (+128 more)

### Community 120 - "tests/test_ncaaf_alias_scores.py"
Cohesion: 0.08
Nodes (32): _FakeConn, _FakeCursor, alias_score_updates(), mirror_scores_to_alias_rows(), mirror_stored_finals(), _slug_pair(), _cfbd(), _row() (+24 more)

### Community 121 - "Alternate prop line fetching tests"
Cohesion: 0.07
Nodes (26): _Conn, _Resp, alt_markets_due(), _ou(), _parse(), test_a_422_retries_without_the_alternates_before_going_dk_only(), fake_get(), test_a_422_with_no_alternates_still_takes_the_dk_only_retry() (+18 more)

### Community 123 - "tests/test_backtester.py"
Cohesion: 0.07
Nodes (9): TestCalibrationError, TestComputeBacktestSummary, TestEvaluateResult, TestGoLiveGateConstants, TestIterSides, _calibration_error(), compute_backtest_summary(), _evaluate_result() (+1 more)

### Community 124 - "NHL prop EV research lab"
Cohesion: 0.09
Nodes (16): TestRegimeOrder, best_per_player(), blocked_sides(), history(), pool(), main(), regime(), show() (+8 more)

### Community 125 - "NFL in-play odds client and smoke check"
Cohesion: 0.09
Nodes (15): CreditBudgetExceeded, CreditMeter, LiveOddsClient, Quote, best_price(), parse_events(), _parse_ts(), _side_of() (+7 more)

### Community 129 - "NBA prop market lab"
Cohesion: 0.09
Nodes (44): NBTable, add_units(), assemble(), best_per_key(), boot_ci(), build_quotes(), candidates_from(), choose_floor() (+36 more)

### Community 13 - "Discord pick notifier tests"
Cohesion: 0.02
Nodes (94): _FakeConn, _FakeResult, _Resp, _StampConn, _cand(), _et_now_iso(), _freeze_now(), _live_row() (+86 more)

### Community 131 - "nfl/live_model/tests/test_backup_snaps.py"
Cohesion: 0.09
Nodes (22): _FakeConn, _FakeCur, back_up(), digest(), _flush(), iter_files(), main(), _mb() (+14 more)

### Community 134 - "Pipeline report rollback tests"
Cohesion: 0.14
Nodes (6): _Conn, _rows(), test_a_failed_query_rolls_back(), test_every_section_is_still_present(), test_one_broken_section_does_not_break_the_rest(), test_the_health_check_query_does_not_compare_text_to_a_date()

### Community 135 - "mobile/scripts: verify_book_links + verify_betslip_combine"
Cohesion: 0.06
Nodes (37): betslipCombineKind, combineBetMgm(), combineBetslipLinks(), combineCaesars(), combineDraftKings(), combineEspnBet(), combineFanDuel(), fanDuelPairs() (+29 more)

### Community 137 - "NBA injury report PDF dedupe tests"
Cohesion: 0.11
Nodes (17): _Conn, _Cur, _Fetcher, _PdfFetcher, _content_of_fixture(), _rows(), test_a_changed_report_stores_its_rows(), test_a_garbled_report_writes_its_ledger_row_and_no_rows() (+9 more)

### Community 138 - "tests/test_paused_keeps_real_verdict.py"
Cohesion: 0.06
Nodes (35): _Capture, _prop_bets_today(), _bet(), _bodies(), _code(), _fn(), _pause(), _prop() (+27 more)

### Community 140 - "mobile/scripts/verify_contrast_tokens.ts"
Cohesion: 0.05
Nodes (39): Pair, code(), lum(), noGreen(), over(), ratio(), read(), readUtf8() (+31 more)

### Community 141 - "Manual social post queue tests"
Cohesion: 0.14
Nodes (31): Poster, QueueConn, _blank(), _drain(), _no_network(), test_a_bad_reply_target_fails_without_posting(), test_a_fresh_claim_is_not_posted_again(), test_a_future_row_waits() (+23 more)

### Community 143 - "Pick lock after settlement tests"
Cohesion: 0.09
Nodes (21): _SqliteShim, _game(), _pick(), _survivors(), test_a_bet_is_never_dropped_for_an_earlier_no_signal(), test_a_dead_zone_prop_row_locks_too(), test_a_final_game_is_not_a_scoring_target(), test_a_game_with_no_score_is_still_scoreable() (+13 more)

### Community 144 - "NBA game line move study"
Cohesion: 0.07
Nodes (33): Data, attach(), big_home_dog_signal(), consensus(), control_specs(), coverage_text(), fade_side(), favourite_sides() (+25 more)

### Community 146 - "tests/test_mlb_game_market.py"
Cohesion: 0.08
Nodes (25): GameMarketBet, _SlateConn, find_spread_bets(), find_total_bets(), _is_runline(), pick_rows(), test_mlb_market_cards_drop_a_bet_under_the_floor(), _game_rows() (+17 more)

### Community 149 - "NBA game four part two study"
Cohesion: 0.06
Nodes (42): Point, even_gap(), ladder_mask(), main_rungs(), _one_rung(), split_main_rungs(), visible_numbers(), go_guard() (+34 more)

### Community 15 - "X results and free pick posts"
Cohesion: 0.02
Nodes (71): _R, test_a_push_only_period_does_not_invent_an_roi(), test_the_period_tweet_uses_the_daily_tally_and_states_roi(), test_discord_free_pick_candidates_refuse(), execute(), fetchall(), row(), _creds_on() (+63 more)

### Community 150 - "Threshold review core tests"
Cohesion: 0.05
Nodes (31): _Conn, _is_paused(), _quiet(), rule_only(), _slate(), test_a_losing_model_with_enough_bets_is_flagged(), test_a_losing_model_with_too_few_bets_is_left_alone(), test_a_milestone_fires_only_once() (+23 more)

### Community 152 - "Idle read transaction tests"
Cohesion: 0.07
Nodes (16): ViewMigrationResult, _Rec, apply_view_migrations(), _flat(), test_a_lock_timeout_fails_that_file_and_the_next_still_runs(), test_a_locked_bet_releases_the_lock_check(), test_a_quiet_tick_rolls_the_read_back(), test_a_tick_that_writes_does_not_roll_the_insert_back() (+8 more)

### Community 154 - "UFC phantom fight filter"
Cohesion: 0.21
Nodes (6): TestFilterUfcPhantom, TestIsKnownUfcMatchup, _filter_ufc_phantom(), _is_known_ufc_matchup(), _game(), _odds()

### Community 155 - "Prop box score backfill"
Cohesion: 0.09
Nodes (19): GradeConn, ScriptConn, ensure_prop_box_scores(), missing_prop_games(), _pick(), test_a_logged_game_is_not_fetched_and_a_goalie_gap_is(), test_a_non_timeout_prop_error_rolls_back_and_raises(), test_a_probe_error_that_is_not_a_timeout_raises_after_rollback() (+11 more)

### Community 156 - "NBA game model prop feature tests"
Cohesion: 0.06
Nodes (40): _Stop, _box(), _g(), _games(), _inj(), _model(), _props(), _run() (+32 more)

### Community 157 - "MLB in-play scorer and inning gate"
Cohesion: 0.02
Nodes (94): _RecordingConn, build_mlb_game_features(), build_live_state_row(), _age_seconds(), expected_value(), _latest_live_state(), _live_bets_today(), _make_live_pick() (+86 more)

### Community 158 - "Best line price shopping tests"
Cohesion: 0.05
Nodes (33): FakeConn, TwoOrientationConn, _best_game_price(), _best_game_price_one(), _best_of(), _same_line(), _source(), test_a_better_price_at_a_different_total_is_not_the_same_bet() (+25 more)

### Community 160 - "Per-model EV floor gate"
Cohesion: 0.06
Nodes (29): Gate, expected_value(), min_ev_for(), scoring_method(), publish_enabled(), find_bets(), test_ncaaf_live_ev_floor_is_wired_from_config(), test_the_models_the_global_floor_silently_removed_can_bet_again() (+21 more)

### Community 162 - "Player name matching for props"
Cohesion: 0.09
Nodes (17): FakeConn, drop_duplicate_box_ids(), normalize_player_name(), resolve_feed_name(), _get_prop_dk_odds(), test_a_player_listed_twice_in_the_box_keeps_the_id_the_plays_use(), test_accented_roster_name_matches_the_flat_feed_name(), test_ambiguity_is_a_miss_not_a_guess() (+9 more)

### Community 164 - "tests/test_nfl_opener.py"
Cohesion: 0.11
Nodes (9): TestFreshNumberLabel, TestHeldMinutes, TestModelCardSplit, _giants_board(), _giants_prior_at_2129(), _giants_sched(), _obs(), _row() (+1 more)

### Community 165 - "NHL stats ingestor and opening night"
Cohesion: 0.02
Nodes (67): TestLogRowBuilders, TestNoHollowTeamRowBeforeTheFirstGame, TestSeasonLabel, TestThreeWayMarketKey, _default_fetch(), fetch_espn_nhl_probables(), _https(), parse_probable() (+59 more)

### Community 166 - "Mobile crash logging"
Cohesion: 0.11
Nodes (34): CrashContext, CrashLogDeps, CrashReport, ErrorUtilsShape, KeyValueStore, LaunchMarker, LaunchStage, ReportKind (+26 more)

### Community 170 - "NBA game model luck feature tests"
Cohesion: 0.05
Nodes (39): _Stop, _against_bet(), _f6c_inputs(), _games_for_standings(), _gs(), _market_pricing(), _one_game_data(), _pair() (+31 more)

### Community 171 - "CLV math same-book and market edge"
Cohesion: 0.06
Nodes (29): _Conn, _Res, test_a_one_way_close_is_not_de_vigged(), test_a_worse_close_is_negative_and_equal_prices_are_zero(), test_devigging_the_taken_price_is_not_what_primary_does(), test_kalshi_close_is_not_de_vigged(), test_market_edge_devigs_only_the_close(), test_other_side_prices_include_the_draw_on_a_three_way() (+21 more)

### Community 172 - "NBA team total luck pick card"
Cohesion: 0.09
Nodes (20): TeamTotalBet, artifact(), decided_games(), ensure_decisions_table(), games_with_a_bet(), ledger_exists(), load_quote_rows(), main() (+12 more)

### Community 174 - "Push notifications and publisher lock"
Cohesion: 0.04
Nodes (45): _Conn, _Result, paused_row_exclusion_sql(), announce_live_picks(), test_live_publishers_share_the_row_gate(), test_push_live_refuses_and_does_not_ledger(), _clear_locks(), _no_prod_threshold_sync() (+37 more)

### Community 175 - "tests/test_dk_direct_feed.py"
Cohesion: 0.09
Nodes (22): _Conn, _game_id_for(), _row_for(), _seen_key(), _rec(), test_a_line_move_is_a_new_quote(), test_a_market_we_do_not_understand_is_dropped_not_guessed(), test_a_price_move_is_a_new_quote() (+14 more)

### Community 177 - "tests/test_credit_budget.py"
Cohesion: 0.09
Nodes (22): _Conn, daily_burn(), latest_remaining(), plan_credit_budget(), _burn_conn(), _plan(), test_a_billing_reset_is_not_a_refund(), test_a_call_is_billed_at_what_the_api_says_it_cost() (+14 more)

### Community 178 - "Odds table pruning with time budget"
Cohesion: 0.08
Nodes (17): Budget, BudgetSpent, FrontierUnreadable, count_sql(), _day(), delete_sql(), doomed_sql(), _frontier_job() (+9 more)

### Community 18 - "Mobile daily results recap"
Cohesion: 0.05
Nodes (66): Bucket, FixturePick, Acc, DailyResults, DayGameSummary, DayStakeStats, ModelDayStats, ScopedDailyResults (+58 more)

### Community 180 - "Feature engine and line sweeps"
Cohesion: 0.02
Nodes (70): TestPregameSnapshotGuard, pregame_cutoff_sql(), trusted_first_pitch(), _mark_in_play(), _blk_bullpen_ip(), _blk_injuries(), _blk_pitcher(), _blk_rolling_runs() (+62 more)

### Community 19 - "NHL prop card and blocked shots"
Cohesion: 0.07
Nodes (20): TestTheCard, step_nhl_prop_scoring(), bs_implied(), candidates(), identities(), latest_quotes(), main(), pick_rows() (+12 more)

### Community 193 - "tests/test_first_signal_repair.py"
Cohesion: 0.07
Nodes (28): _Conn, _VoidedConn, step_restore_first_signals(), patch_conn(), _make(), _sql_of(), test_a_lane_already_holding_its_first_bet_is_untouched(), test_a_lane_with_no_sibling_still_restores() (+20 more)

### Community 194 - "Game injury gate and prop veto"
Cohesion: 0.05
Nodes (50): _InjConn, _InjConn, apply_to_picks(), _goalie_names(), load_sport_injury_index(), _pitcher_names(), player_matches_veto(), relevant_players() (+42 more)

### Community 196 - "Outbound call probe recording tests"
Cohesion: 0.04
Nodes (47): _Resp, _credits_from(), _drain(), _enqueue(), instrumented(), _now(), _patch_curl_cffi(), instrumented() (+39 more)

### Community 199 - "Prop price pregame cutoff tests"
Cohesion: 0.08
Nodes (14): _StubConn, _latest_dk_prop_row(), _assigned_from(), _prop_scorers(), test_every_scorer_call_site_passes_a_pregame_cutoff(), test_get_prop_dk_odds_forwards_the_cutoff(), test_in_play_snapshots_are_excluded_unconditionally(), test_it_fails_open_when_commence_time_is_missing() (+6 more)

### Community 2 - "Mobile markets and formatting"
Cohesion: 0.01
Nodes (361): Row, Props, Props, Props, IoniconName, Props, Props, clvBetQuote (+353 more)

### Community 200 - "Pregame line poller change detection tests"
Cohesion: 0.04
Nodes (47): _PollConn, changed_rows(), _credits_used_today(), _fingerprint(), _key(), last_known_prices(), _num(), over_credit_cap() (+39 more)

### Community 203 - "tests/test_nhl_asof.py"
Cohesion: 0.11
Nodes (5): GoalieBook, TestGoalieAsOf, TestReturningStarterIsNamedFromTheLog, name_key(), _g()

### Community 204 - "NFL wind publisher and line snapshots"
Cohesion: 0.03
Nodes (43): TestGamesRows, TestKickoff, TestParsePlayerRows, TestParseTeamRows, TestUpcomingRows, TestParseNflverseScores, backfill_nfl_player_stats(), current_nfl_season() (+35 more)

### Community 205 - "NFL in-play game state feed"
Cohesion: 0.12
Nodes (18): CoreClient, EventMeta, _abbr(), game_seconds(), https(), _int(), is_admin_play(), is_conversion_play() (+10 more)

### Community 208 - "Mobile range slider filter"
Cohesion: 0.18
Nodes (21): Props, GestureIntent, Scale, at(), RangeSlider(), applyBound(), grabTarget(), readIntent() (+13 more)

### Community 209 - "data/ingestors/nfl_inplay_history.py"
Cohesion: 0.16
Nodes (22): Budget, buy_halftime(), buy_inplay(), events_for(), _floor5(), _get(), halftime_requests(), halftime_windows() (+14 more)

### Community 21 - "Mobile record hero and equity curve"
Cohesion: 0.05
Nodes (78): EquityPoint, plotLayout, PlotPad, ParlaySummary, SportGroup, TrackRecordSummary, ParlayTrackRow, TrackRecordRow (+70 more)

### Community 210 - "Mobile billing and paywall"
Cohesion: 0.09
Nodes (39): BillingRail, Plan, PlanKey, Nav, planFor(), describeSubscription(), formatPerMonth(), formatPrice() (+31 more)

### Community 211 - "Mobile bankroll storage and settings card"
Cohesion: 0.09
Nodes (30): BankrollCheck, BankrollCommit, BankrollPatch, BankrollRead, NumberSeparators, Part, walk(), deviceSeparators() (+22 more)

### Community 212 - "Prop over probability ladder"
Cohesion: 0.12
Nodes (6): Ladder, _expit(), from_kalshi(), _logit(), _monotone(), test_from_kalshi_reads_the_dollars_fields()

### Community 216 - "Market-anchored offset logistic fit"
Cohesion: 0.17
Nodes (6): OffsetLogit, choose_C(), _log_loss(), market_logit(), fit_one(), test_with_nothing_to_say_it_returns_the_market()

### Community 217 - "NCAAF in-play pricing engine"
Cohesion: 0.08
Nodes (11): LiveEngine, expected_value(), _is_paused(), test_ev_floor_cannot_fire_without_a_price(), test_ev_floor_declines_a_qualifying_pick_that_is_priced_too_short(), test_ev_floor_only_tightens_and_never_touches_avoid(), engine(), test_the_cap_applies_to_the_avoid_side_too() (+3 more)

### Community 218 - "Mobile push test diagnostics"
Cohesion: 0.07
Nodes (47): PushState, PushStatus, ForcedOnlyReason, PushDiagnosis, PushFailureReason, TestPushResult, reasonOf(), NotificationsCard() (+39 more)

### Community 22 - "NBA prop projection card"
Cohesion: 0.07
Nodes (34): ProjectionBet, espn_compact(), decided_games(), backfill_official(), decided_games(), ensure_tables(), espn_pulls(), espn_rows() (+26 more)

### Community 220 - "tests/test_db_reconnect.py"
Cohesion: 0.09
Nodes (16): _Conn, _Cursor, _is_write(), _lost(), test_a_committed_transaction_is_clean_again(), test_a_lost_connection_with_uncommitted_writes_raises_connection_lost(), test_a_read_on_a_lost_connection_reconnects_and_retries(), test_a_statement_timeout_is_not_a_lost_connection() (+8 more)

### Community 222 - "Discord recap restatement"
Cohesion: 0.07
Nodes (17): _Conn, test_a_restated_recap_is_labelled_and_says_why(), _resp(), test_a_404_is_an_answer_not_a_retry(), test_a_persistent_403_still_raises_after_the_last_attempt(), test_a_recap_whose_count_merely_drifted_is_not_due(), test_a_recap_with_a_late_settlement_is_due(), test_a_transient_403_is_retried_and_the_second_answer_is_used() (+9 more)

### Community 223 - "In-play scorer locks and push alerts"
Cohesion: 0.11
Nodes (19): FakeConn, _Rows, _lane_signature(), _write_live_picks(), _locked_live_lanes(), _log_lines(), _pick(), test_a_locked_lane_still_says_so_and_names_the_lane() (+11 more)

### Community 225 - "tests/test_refresh_retry.py"
Cohesion: 0.14
Nodes (23): Decision, RefreshRun, _decide(), _done(), _run(), test_a_failed_view_migration_fails_the_step(), test_a_pass_that_finished_with_failed_steps_ran_its_chain(), test_a_redeploy_between_passes_replaces_nothing() (+15 more)

### Community 226 - "NBA results ingestion"
Cohesion: 0.05
Nodes (25): PgStore, PlayerResolver, call_in_savepoint(), rollback_savepoint(), statement_timeout(), box_is_complete(), build_dnp_rows(), build_log_rows() (+17 more)

### Community 228 - "NBA results ingestor tests"
Cohesion: 0.10
Nodes (28): _ESPN, FakeStore, _FixedNow, _game(), _ppd_game(), _resolver(), _run(), test_a_box_still_missing_since_opening_week_is_retried_all_season() (+20 more)

### Community 23 - "NBA second game projection study"
Cohesion: 0.03
Nodes (91): EW, Last, Model, PointInputs, State, World, actuals(), apply_models() (+83 more)

### Community 230 - "tests/test_local_cache_is_additive.py"
Cohesion: 0.11
Nodes (10): _FakeConn, _merge_with_cache(), _pull_odds(), cached(), _frame(), test_a_first_ever_pull_still_works(), test_a_pull_that_lost_rows_keeps_them(), test_an_unreadable_cache_refuses_rather_than_overwrites() (+2 more)

### Community 231 - "tests/test_calibration_check_coverage.py"
Cohesion: 0.11
Nodes (18): _Shim, _bet(), _calibration_results(), db(), _graded(), _make_db(), _only(), _promote() (+10 more)

### Community 232 - "NBA injury report PDF parsing"
Cohesion: 0.11
Nodes (16): Report, _bands(), _column_of(), _columns(), finish_rows(), _hrules(), _lines_of(), parse_page_layout() (+8 more)

### Community 233 - "tests/test_book_team_map.py"
Cohesion: 0.11
Nodes (15): _Conn, abbr_from_team_string(), resolve_game_id(), split_matchup(), test_a_non_mlb_sport_is_refused_rather_than_guessed(), test_a_string_with_no_at_sign_is_refused(), test_a_unique_game_resolves(), test_an_ambiguous_game_resolves_to_none() (+7 more)

### Community 235 - "NCAAF game features and FBS registry"
Cohesion: 0.02
Nodes (71): TestComputeTarget, TestFbsGate, TestRefusalLog, TestRegistryHealthCheck, TestUnratedFbsClaim, _SqliteShim, _compute_target(), _assemble_ncaaf_features() (+63 more)

### Community 236 - "NCAAF in-play total repricing engine"
Cohesion: 0.03
Nodes (58): ScoreDistribution, _cluster_bootstrap(), evaluate(), main(), report(), fit(), load_states(), main() (+50 more)

### Community 239 - "NFL wind board fast publishing tests"
Cohesion: 0.13
Nodes (16): FakeConn, publish_board(), matchup(), _append_board(), _body(), _row(), _sent(), _setup() (+8 more)

### Community 24 - "Mobile picks queries and Discord status"
Cohesion: 0.02
Nodes (120): FighterSide, Props, CustomBacktestPickRow, CustomBacktestSummary, DiscordPublish, LockPick, NcaafTeamRow, PropLineLike (+112 more)

### Community 242 - "Mobile Discord link and access"
Cohesion: 0.11
Nodes (36): AccessState, useAccess, useEntitlement, FunctionResponse, LinkResult, AccessRow, AccessSource, DiscordCallback (+28 more)

### Community 245 - "NHL team rates as of a date"
Cohesion: 0.11
Nodes (6): TeamBook, TestBlendedTeamInputs, TestTeamRatesAsOf, _r(), _t(), test_the_training_path_reads_nhl_odds_by_game_not_by_sport()

### Community 247 - "tests/test_dk_freshness_parse.py"
Cohesion: 0.12
Nodes (17): _FakeConn, _FakeResult, _american(), parse_dk_payload(), _store(), _payload(), test_a_half_priced_market_is_dropped_rather_than_half_recorded(), test_an_event_with_no_markets_yields_nothing_rather_than_raising() (+9 more)

### Community 248 - "NHL moneyline and market labs"
Cohesion: 0.02
Nodes (157): OffsetLogit, build_training_dataset(), build_golf_training_dataset(), _add_rating(), build_inputs(), fit(), _goalie_frame(), inputs_for_date() (+149 more)

### Community 249 - "models: slate_concentration + test_slate_concentration"
Cohesion: 0.15
Nodes (15): SlateConcentration, apply_slate_guard(), apply_slate_concentration_guard(), _attr(), _edge_of(), _is_bet(), measure_side_concentration(), _side_of() (+7 more)

### Community 251 - "View migration lock handling tests"
Cohesion: 0.07
Nodes (25): _Conn, _Deadlock, _LockTimeout, _StatementTimeout, _Syntax, execute(), _before(), _code() (+17 more)

### Community 252 - "In-play stale score quote guard"
Cohesion: 0.14
Nodes (11): _FakeConn, _book_move(), _get_live_dk_odds(), _odds(), test_a_quote_published_before_the_score_is_declined(), test_a_quote_republished_after_the_score_is_kept(), test_the_age_bound_alone_would_have_allowed_it(), test_the_age_bound_still_fires_independently() (+3 more)

### Community 258 - "NFL closing line value backtest features"
Cohesion: 0.14
Nodes (9): ShrunkEnsemble, add_form(), build(), feature_columns(), market_features(), team_game_stats(), fmt(), main() (+1 more)

### Community 26 - "Mobile performance and tracked bets"
Cohesion: 0.09
Nodes (40): StakeMode, StakeState, LiveTrackSnapshot, TrackedBetRow, trackedBetStatus, TrackedBetSummary, emit(), load() (+32 more)

### Community 261 - "NBA game four point estimates"
Cohesion: 0.10
Nodes (16): Point, base_inputs(), emit_point(), features_of(), label_kind(), make_point(), members(), model_fair() (+8 more)

### Community 265 - "Best line threshold sweep"
Cohesion: 0.10
Nodes (12): _Conn, american_to_decimal(), units_at(), _row(), test_a_better_price_pays_more_than_the_dk_price(), test_a_loss_costs_one_unit_at_every_price(), test_a_push_is_flat(), test_a_retired_model_is_never_recommended_a_cut() (+4 more)

### Community 268 - "NCAAF game-day twin game handling"
Cohesion: 0.16
Nodes (10): _Conn, _Result, _night_twin(), _pair_key(), _row(), test_a_twin_does_not_silently_take_the_row_without_lines(), test_an_unrelated_game_is_unaffected_by_a_collision(), test_context_carries_the_fbs_rule_for_both_teams() (+2 more)

### Community 269 - "NCAAF college data ingest tests"
Cohesion: 0.07
Nodes (8): _GamesConn, _TeamsConn, test_ingest_games_retains_a_historical_utc_id_and_uses_et_for_a_new_row(), fake_get(), test_ingest_pulls_fbs_then_everyone_and_fbs_rows_win(), test_ingest_retries_everyone_without_a_year_if_the_season_filter_is_empty(), test_prior_context_tolerates_missing_talent_and_returning(), test_weekly_snapshot_build_aborts_on_failed_fetch()

### Community 27 - "Mobile betslip and parlay legs"
Cohesion: 0.02
Nodes (195): Props, ParlayRestorePayload, ResolvedSlip, GameLineLegSpec, GameLineMarket, LineLegSpec, LineSheetInput, LineSide (+187 more)

### Community 270 - "NBA pregame scoring window"
Cohesion: 0.08
Nodes (23): PregamePlan, _db(), _decided_by(), _fires(), _job(), _slate(), test_a_close_alone_runs_only_the_close(), test_a_failed_team_total_step_is_an_error_after_publishing() (+15 more)

### Community 271 - "Line CLV sign and orientation tests"
Cohesion: 0.04
Nodes (17): _Conn, _stub_backfill(), test_hard_cap_stops_a_nonempty_queue(), test_loops_until_a_pass_fills_nothing(), test_the_runner_opens_get_connection_and_calls_backfill_clv(), test_runner_captures_stdout_from_the_script_main(), test_sport_and_market_are_bounded(), test_the_declared_key_is_present_and_valid() (+9 more)

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

### Community 28 - "CLV graded at the price taken"
Cohesion: 0.04
Nodes (38): _Conn, _Res, _SnapConn, _fn(), _migration(), _pick(), test_a_draftkings_decided_row_is_unchanged(), test_a_legacy_row_that_cannot_be_re_measured_leaves_the_old_method() (+30 more)

### Community 281 - "tests/test_cloud_retrain_artifacts.py"
Cohesion: 0.10
Nodes (12): _Conn, _restore_artifact(), test_a_failed_upload_does_not_lose_a_model_that_trained(), test_a_missing_artifact_table_is_not_an_error_on_restore(), test_a_no_register_run_stores_nothing(), test_load_model_actually_loads_from_the_store_when_the_file_is_gone(), fetchone(), test_load_model_returns_none_when_the_store_has_nothing_either() (+4 more)

### Community 282 - "NHL side models never bet against each other"
Cohesion: 0.08
Nodes (27): _Conn, _ThreeWay, _apply_side_conflicts(), _endings_won(), picks_cannot_both_win(), side_checked_models(), ml(), _pick() (+19 more)

### Community 283 - "NFL prop Kalshi ladder pricing tests"
Cohesion: 0.11
Nodes (9): Rung, _ladder(), test_a_replay_never_prices_off_todays_ladder_even_when_on(), test_fetch_helper_swallows_errors(), test_kalshi_is_not_graded_until_settled_history_exists(), test_kalshi_outside_the_ladder_is_refused_not_extrapolated(), test_kalshi_prices_a_line_pinnacle_cannot(), test_missing_game_date_fails_closed_for_that_row() (+1 more)

### Community 285 - "System health checks and record reconciliation"
Cohesion: 0.06
Nodes (23): HealthReport, ncaaf_season_for_date(), test_january_games_belong_to_the_prior_season(), still_pre_game(), unique_row_sql(), describe(), find_duplicate_pairs(), _calibration_bet_only_rows() (+15 more)

### Community 288 - "tests/test_nfl_opener.py"
Cohesion: 0.20
Nodes (5): TestBettableBooksOnly, TestSelectOpenerBets, _both_sides(), _frame(), _sched()

### Community 289 - "Player news ingest from ESPN"
Cohesion: 0.04
Nodes (53): NewsItem, NewsPlayer, FakeConn, FakeResponse, _Result, _article_url(), _athletes_in(), build_name_index() (+45 more)

### Community 290 - "Mobile in-app purchase billing"
Cohesion: 0.13
Nodes (25): BillingDisabledError, CheckoutResult, IapPurchaseResult, PurchasesSDK, MinimalCustomerInfo, MinimalPackage, assertBillingReady(), billingErrorMessage() (+17 more)

### Community 296 - "NHL blocked shots prop model"
Cohesion: 0.08
Nodes (20): TestTonightsRowIsATrainingRow, build_frame(), _ew(), expected_value(), fit(), load_skaters(), load_teams(), name_key() (+12 more)

### Community 298 - "tests/test_nfl_wind_publisher.py"
Cohesion: 0.13
Nodes (10): TestBuildRows, TestKickFields, TestParseMatchup, build_rows(), _fmt_line(), kick_fields(), parse_matchup(), test_nfl_wind_and_opener_rows_drop_a_bet_under_the_floor() (+2 more)

### Community 3 - "Odds and prop odds ingestion"
Cohesion: 0.02
Nodes (139): Meter, Meter, TestEveryOtherSportStillMintsItsOwn, TestNflResolvesOntoTheSchedule, TestTheResolverFailsClosed, TestOddsFeedTeamNames, FakeResp, _load_schools() (+131 more)

### Community 30 - "NFL in-play game-day worker"
Cohesion: 0.04
Nodes (40): _FakeOdds, _IdRecordingOdds, _Q, GamedayWorker, GameTracker, test_the_worker_self_checks_once_and_alerts_on_a_broken_feed(), _core_worker(), test_a_deployed_bias_must_sit_inside_its_measured_interval() (+32 more)

### Community 300 - "tests/test_health_reason_and_cadence.py"
Cohesion: 0.10
Nodes (19): Report, _one(), test_a_24h_ts_check_reads_as_daily(), test_a_bare_add_still_fills_both_columns(), test_a_broken_query_is_its_own_reason(), test_a_late_check_says_how_late(), test_a_passing_check_says_fresh(), test_a_skipped_check_says_the_gate_was_shut() (+11 more)

### Community 301 - "NBA odds history gap fetch tests"
Cohesion: 0.09
Nodes (18): _Ledger, _Meter, _Resp, gap_instants(), line_snapshots(), _hourly(), _t(), test_a_fetch_is_ledgered_by_its_instant_off_the_hour_and_by_its_hour_on_it() (+10 more)

### Community 302 - "tests/test_nfl_weather_supabase_readback.py"
Cohesion: 0.14
Nodes (13): FakeConn, _patch_conn(), _rows(), test_a_null_requested_lead_is_not_returned(), test_a_one_lead_response_is_not_stored(), test_a_partial_window_is_not_returned(), test_a_store_failure_is_a_warning_not_an_error(), test_a_subset_of_leads_reads_only_those_columns() (+5 more)

### Community 307 - "Publish signals on write tests"
Cohesion: 0.06
Nodes (18): _Conn, _body(), _row(), _surfaces(), _make(), test_a_broken_webhook_does_not_suppress_the_push(), test_a_failed_capture_still_delivers(), test_a_publish_failure_does_not_kill_the_tick() (+10 more)

### Community 308 - "Pitcher stats as-of invariant tests"
Cohesion: 0.05
Nodes (36): _FakeConn, last3_rates(), outs_from_ip(), per_nine(), whip(), already_a_series(), appearances(), _avg_distinct() (+28 more)

### Community 31 - "NBA prop market card and bet finder"
Cohesion: 0.04
Nodes (39): NbaPropDecision, Roster, coherent(), fair_under(), fetch_times(), find_bets(), in_window(), load_quotes() (+31 more)

### Community 312 - "NHL prop per-game limit tests"
Cohesion: 0.16
Nodes (4): TestInsertOnce, TestTheLimitPerGame, limit_per_game(), publish()

### Community 314 - "Pipeline log reason tests"
Cohesion: 0.22
Nodes (6): _Conn, _capture(), test_a_false_step_records_the_last_error_it_logged(), test_a_false_step_that_logged_nothing_still_says_so(), test_a_raising_step_still_records_the_exception(), test_the_sink_is_removed_after_the_step()

### Community 315 - "NFL in-play score distribution engine"
Cohesion: 0.06
Nodes (21): ScoreDistribution, _cluster_bootstrap(), evaluate(), main(), report(), fit(), load_states(), main() (+13 more)

### Community 32 - "NBA in-game study two"
Cohesion: 0.05
Nodes (51): StateModel, norm_cdf(), apply_model(), benchmark_columns(), decision_quotes(), delta_ci(), _design(), eligible() (+43 more)

### Community 320 - "NFL scored rows preflight database fake"
Cohesion: 0.09
Nodes (6): _Pg, _PgCursor, TestPreflightCiMode, wind(), wrapped(), fake_open()

### Community 321 - "NFL in-play prop settlement tests"
Cohesion: 0.16
Nodes (13): _SqliteShim, _box(), conn(), _game(), _live_bet(), raw(), _row(), test_a_neighbouring_days_game_does_not_grade_the_wrong_player() (+5 more)

### Community 322 - "Odds pruning time budget tests"
Cohesion: 0.10
Nodes (10): _Ctx, Timeout, _lit(), render(), test_a_record_write_that_fails_for_a_bug_fails_the_table(), execute(), __init__(), test_a_thinning_failure_still_prunes_both_tables_and_is_reported() (+2 more)

### Community 323 - "NBA prop and total fetch window tests"
Cohesion: 0.06
Nodes (36): _PlanConn, _fires(), _game(), _jobs(), _plan(), _t(), test_a_projection_too_old_to_price_does_not_block_the_retry(), test_a_tick_fetches_exactly_the_window_games_then_decides_closes_and_publishes() (+28 more)

### Community 326 - "NFL pick publisher lookahead tests"
Cohesion: 0.08
Nodes (15): _Conn, _sql_for(), test_a_started_game_is_still_never_published(), test_both_publishers_apply_the_apps_action_filter(), test_both_publishers_read_the_table_the_app_reads(), test_capture_reaches_as_far_as_the_poller_can_write(), test_capture_reaches_forward_for_the_locked_lookahead_sports(), test_ncaaf_lookahead_is_only_safe_because_the_lock_is_general() (+7 more)

### Community 33 - "Mobile error text and load states"
Cohesion: 0.03
Nodes (107): Props, LivePicksState, Args, PlayerNewsState, CountInput, DetailBody, LoadBody, LoadInput (+99 more)

### Community 330 - "NFL opener publisher tests"
Cohesion: 0.14
Nodes (7): TestBuildOpenerRows, TestPublishOpenerInsertOnce, build_opener_rows(), _opener_model(), _card_row(), _row(), execute()

### Community 331 - "NHL player prop projection model"
Cohesion: 0.07
Nodes (29): Spec, TestWhoThePlayerIs, _attach_teams(), build_frame(), build_goalie_frame(), build_skater_frame(), _ew(), excess_variance() (+21 more)

### Community 334 - "CLV settlement timeout retry tests"
Cohesion: 0.10
Nodes (13): _Conn, _fn(), _sql(), test_a_non_timeout_is_not_retried(), test_a_second_timeout_does_not_abort_the_next_statement(), test_a_timeout_is_rolled_back_and_retried_once(), test_one_date_timeout_does_not_drop_the_next_date(), test_query_canceled_with_sqlstate_is_a_timeout() (+5 more)

### Community 341 - "Health check skip budget tests"
Cohesion: 0.07
Nodes (19): FakeConn, test_a_stuck_gate_is_not_reported_as_stale_data(), _res(), _source_outside_the_budget_table(), test_a_check_never_seen_non_skipped_counts_its_whole_history(), test_a_check_skipped_only_today_is_not_counted_as_a_streak(), test_a_non_skipped_result_is_never_touched(), test_a_stuck_gate_escalates_past_its_budget() (+11 more)

### Community 342 - "Live pick features and paused rows tests"
Cohesion: 0.05
Nodes (29): FakeConn, _Conn, _record_live_features(), _pick(), test_a_live_bet_records_its_feature_row_and_lambda(), test_a_pick_with_no_feature_row_is_skipped_not_written_empty(), test_a_recorder_failure_is_rolled_back_to_its_savepoint(), test_a_recorder_failure_is_swallowed_rather_than_raised() (+21 more)

### Community 345 - "Model quality monitor checks"
Cohesion: 0.06
Nodes (25): _Shim, _bet(), _fade_slate(), _insert_open_bet(), test_a_mixed_slate_is_ok(), test_all_home_ncaaf_slate_is_flagged_without_mlb_hardcoding(), test_all_unders_public_fade_risk_is_crit(), test_all_unders_public_fade_slate_is_crit() (+17 more)

### Community 348 - "Pregame price age and twin game tests"
Cohesion: 0.04
Nodes (26): _BoardConn, _OddsConn, _ShopConn, _TwoIdConn, _UfcBoardConn, _ago(), _clock(), _h2h_row() (+18 more)

### Community 349 - "tests/test_prop_missing_features.py"
Cohesion: 0.14
Nodes (5): TestARowMissingAFeatureIsNotScored, TestEveryPropLoopGoesThroughTheHelper, TestTheUmpireIsTheDeclaredException, _frame(), helper()

### Community 350 - "MLB public fade top picks ranking"
Cohesion: 0.06
Nodes (32): PublicFadeBet, _better_under(), composite_score(), edge_floor(), estimated_edge(), max_per_slate(), _price_in_window(), publish_enabled() (+24 more)

### Community 355 - "NFL in-play decline recorder tests"
Cohesion: 0.12
Nodes (12): PicksRecorder, _AvoidConn, _mk_decline(), test_a_market_opinion_decline_is_written_as_avoid(), test_a_moved_line_is_rewritten(), test_an_unchanged_proposition_is_not_rewritten(), test_plumbing_refusals_stay_out_of_picks(), test_recording_a_decline_can_never_break_a_bet() (+4 more)

### Community 357 - "NFL wind scored row building"
Cohesion: 0.11
Nodes (6): TestBuildScoredRows, TestPickEmLabel, TestPreflightLockChecks, TestQualifyingRowIsNotANoneRow, build_scored_rows(), _fmt_spread()

### Community 359 - "NBA prop settlement stats"
Cohesion: 0.11
Nodes (9): _SelectConn, test_a_missing_stat_is_none_not_zero(), test_a_turnovers_bet_on_a_player_who_played_settles_win_not_no_action(), test_combo_markets_are_mapped_to_helpers_and_only_the_nba_rule_uses_them(), test_double_double_matches_the_rule_it_replaced(), test_the_loader_carries_every_stat_a_market_settles_on(), test_the_loader_selects_turnovers(), _load_nba_prop_actuals() (+1 more)

### Community 361 - "NCAAF live state recording tests"
Cohesion: 0.16
Nodes (13): _Conn, record_live_states(), state_change_row(), state_key(), _state(), test_a_failed_write_never_costs_the_pass(), test_a_score_a_period_or_a_possession_change_is_written(), test_first_sight_is_written() (+5 more)

### Community 363 - "tests/test_run_ledger_orphans.py"
Cohesion: 0.12
Nodes (18): _Conn, db(), _insert_open(), _ledger(), _open_rows(), _row(), test_a_genuine_current_hang_is_still_detectable(), test_a_second_sweep_does_not_abort_the_pass_this_process_started() (+10 more)

### Community 368 - "MLB in-play history backtest"
Cohesion: 0.21
Nodes (9): _Conn, _Cur, _lookup_home_won(), mlb_game_final(), sbr_twin_id(), test_no_final_anywhere_is_none(), test_scored_canonical_row_wins_and_keeps_its_label(), test_twin_id_swaps_only_the_renamed_franchises() (+1 more)

### Community 369 - "NHL anchored moneyline tests"
Cohesion: 0.11
Nodes (15): _Fixed, decision_window(), _logs(), _served(), test_a_later_result_cannot_reach_an_earlier_game(), test_a_matinee_closes_the_window_at_puck_drop(), test_a_missing_input_skips_the_game(), test_in_the_window_it_bets_ev_and_never_writes_avoid() (+7 more)

### Community 37 - "NBA lineup stints from play-by-play"
Cohesion: 0.04
Nodes (49): Diagnostics, _Seg, alias_play_ids(), roster_from_plays(), score_plays(), _accumulate(), _add_one(), appearances() (+41 more)

### Community 370 - "UFC results scraper tests"
Cohesion: 0.08
Nodes (22): _FakeConn, _height_to_inches(), _parse_dob(), parse_fighter_page(), _reach_to_inches(), rounds_completed(), _fight_minutes(), _resolve() (+14 more)

### Community 376 - "In-play calibrated decision tests"
Cohesion: 0.07
Nodes (20): RecordingConn, fetch_graded(), _in_graded_matview(), _is_live_lane(), test_every_model_is_visible_to_exactly_one_source(), _cut(), _signal(), test_a_big_enough_claim_still_fires_after_calibration() (+12 more)

### Community 378 - "Team total market skip rules tests"
Cohesion: 0.12
Nodes (10): _PickConn, _Rows, raw(), _result(), test_a_line_that_dropped_under_an_under_is_a_skip(), test_an_away_team_total_settles_on_the_away_team_s_points(), test_an_overtime_final_counts_and_a_full_game_total_would_not(), test_no_line_is_no_action_not_a_guess() (+2 more)

### Community 38 - "Pregame pick scorer and bet insertion"
Cohesion: 0.02
Nodes (109): FakeConn, TestPushAdjustment, TestAmericanToImpliedProb, TestMissingStarterGate, today_et(), build_golf_scoring_features(), matchup_diff_features(), american_to_implied_prob() (+101 more)

### Community 380 - "Sharp book odds retention"
Cohesion: 0.07
Nodes (14): _RecordingConn, _prop_reference_books(), protected_for(), _thin_book_filter(), test_the_bookmaker_these_rows_use_survives_the_daily_prune(), test_a_shopping_book_is_still_prunable(), test_every_prop_reference_book_is_protected(), test_every_sharp_book_is_protected_in_the_prop_table() (+6 more)

### Community 381 - "Eastern time dates and schema guards"
Cohesion: 0.04
Nodes (39): Plan, lock_down(), _fetchone(), schema_is_current(), fetch_season(), main(), run(), write() (+31 more)

### Community 383 - "NCAAF opponent-adjusted search features"
Cohesion: 0.09
Nodes (18): AdjRatings, blended_rating(), build_adjusted_ratings(), features_for(), fit_opponent_adjustment(), rolling_variants(), _synth(), test_blend_falls_back_when_one_side_missing() (+10 more)

### Community 385 - "MLB first five any-book line tests"
Cohesion: 0.08
Nodes (31): _Clf, _GameOddsConn, _fallback_game_line_quote(), _get_scoring_odds(), _has_real_game_price(), _cut(), _mlb_feat(), _on() (+23 more)

### Community 387 - "tests/test_repair_bogus_first_pitch_labels.py"
Cohesion: 0.13
Nodes (8): _Conn, _run(), test_a_dry_run_writes_nothing_at_all(), test_a_short_backup_rolls_back_and_relabels_nothing(), test_the_backup_is_written_before_the_update(), test_the_backup_table_is_revoked_from_the_public_roles(), test_the_bogus_set_is_computed_never_listed(), test_the_query_is_scoped_to_the_scheduled_start_not_the_derived_one()

### Community 39 - "nfl/live_model/tests/test_executor.py"
Cohesion: 0.06
Nodes (47): Decision, Executor, american_to_decimal(), derivative_lag(), ev_floor(), _mk(), expected_value(), honest_probability() (+39 more)

### Community 392 - "NBA injury report daily runner"
Cohesion: 0.17
Nodes (10): Fetcher, ensure_tables(), load_players(), load_schedule(), main(), pulled_urls(), remap_players(), retry_failed() (+2 more)

### Community 393 - "tests/test_sbr_loader.py"
Cohesion: 0.14
Nodes (3): _SqliteConnShim, _SqliteCursorShim, loader_conn()

### Community 394 - "Walk-forward evaluation"
Cohesion: 0.12
Nodes (10): _Cols, _Frame, _fake(), test_a_fold_with_too_little_history_is_skipped(), test_a_single_class_test_season_is_skipped(), _frame(), test_every_fold_trains_only_on_earlier_seasons(), _frame() (+2 more)

### Community 397 - "mobile/scripts/ux_scan.mts"
Cohesion: 0.16
Nodes (18): Finding, Severity, changedFiles(), entitlementGate(), fontScaling(), fontSizeLiterals(), hexColors(), main() (+10 more)

### Community 41 - "tests/test_live_quote_staleness.py"
Cohesion: 0.05
Nodes (40): _Conn, _Q, build_row(), quote_from_nfl_quotes(), rows_from_quote(), _abbrev(), rows_for_quotes(), _parse_book_markets() (+32 more)

### Community 410 - "NBA prop closing line purchase tests"
Cohesion: 0.09
Nodes (11): _Conn, _Resp, test_a_close_already_held_is_not_bought_again(), test_a_due_close_buys_one_call_of_the_bet_markets_and_reports_its_credits(), test_a_pass_outside_the_window_spends_nothing(), test_only_a_game_holding_a_bet_and_only_once(), test_only_twelve_to_twenty_five_minutes_before_tip(), test_the_ten_minute_evening_passes_always_land_one_inside() (+3 more)

### Community 417 - "In-play publish parity with pauses"
Cohesion: 0.17
Nodes (12): _Conn, _db(), _labels(), _pick(), test_a_bet_written_while_paused_is_not_announced_after_an_unpause(), test_a_live_health_state_still_publishes(), test_a_paused_model_is_not_announced(), test_a_retired_model_is_not_announced() (+4 more)

### Community 421 - "Network timeouts and health probes"
Cohesion: 0.03
Nodes (50): JsonlRecorder, Plan, _mark_written(), now_iso(), _publish_key(), record_live_prices(), game_index(), record_nfl_anchor_prices() (+42 more)

### Community 424 - "supabase/functions/_shared/discord.ts"
Cohesion: 0.20
Nodes (15): DiscordApiError, DiscordUser, RoleSyncResult, addAppRole(), addGuildMember(), botFetch(), expectOk(), isGuildMember() (+7 more)

### Community 43 - "Worker job queue validation tests"
Cohesion: 0.03
Nodes (66): _Conn, _DedupeConn, _VoidConn, _fake(), _posted_row(), _run_void(), _run_void_job(), test_a_busy_queue_claims_nothing() (+58 more)

### Community 433 - "X post image uploads"
Cohesion: 0.16
Nodes (9): _Fetcher, _Uploader, ImageFetch, MediaUpload, test_a_failed_upload_does_not_tweet(), test_a_partial_upload_is_not_repeated_on_requeue(), test_a_rate_limit_after_one_upload_keeps_that_id(), test_an_image_is_uploaded_then_attached() (+1 more)

### Community 435 - "NBA totals luck replay graders"
Cohesion: 0.13
Nodes (9): FrameConn, load_artifact(), grade_window(), lab_bets(), lab_gaps(), load(), main(), replay() (+1 more)

### Community 436 - "NCAAF game-day pick lock tests"
Cohesion: 0.13
Nodes (12): FakeConn, _Rows, write_picks(), db(), test_both_lanes_locked_touches_nothing(), test_dry_run_never_touches_db(), test_first_bet_is_written_and_will_lock(), test_flag_off_restores_delete_and_replace() (+4 more)

### Community 44 - "scripts: build_nfl_live_leader_artifact + model"
Cohesion: 0.06
Nodes (37): Artifact, Decision, am_to_dec(), artifact_from_dict(), band_for(), decide(), leader_expected_margin(), load_artifact() (+29 more)

### Community 440 - "NFL DraftKings line snapshot capture"
Cohesion: 0.17
Nodes (7): TestDkLineRows, append_snapshot_csv(), dk_line_rows(), dump_dk_lines(), _num(), snapshot_schedule(), _rec()

### Community 446 - "Run ledger and schema change guard"
Cohesion: 0.05
Nodes (31): GuardConn, _ddl(), _dk_direct_feed(), _is_guarded(), _job_queue(), _kickoff_wind(), _live_calibration(), _modules_with_write_time_ddl() (+23 more)

### Community 448 - "tests/test_discord_channel_probe.py"
Cohesion: 0.17
Nodes (7): _Resp, test_the_probe_covers_the_per_sport_live_channels(), test_the_probe_never_posts_and_never_returns_the_url(), test_the_probe_reports_the_channel_behind_each_sport(), _get(), test_two_sports_sharing_a_channel_are_flagged(), _job_discord_probe()

### Community 45 - "tests/test_nfl_prop_one_read_per_game.py"
Cohesion: 0.06
Nodes (25): _Conn, _Log, publish_hour_missed(), publishable_games(), _at(), _games(), test_a_game_is_publishable_on_exactly_one_pass_in_its_window(), test_a_game_with_no_kickoff_is_never_published() (+17 more)

### Community 450 - "Bounded odds pruning keeps openers and close"
Cohesion: 0.06
Nodes (40): StandIn, p(), _after_nth_delete(), build(), drain(), _fails_on(), nba_paths(), old_prune() (+32 more)

### Community 451 - "NFL pass attempt bias model"
Cohesion: 0.09
Nodes (11): Read, blind_over_prob(), over_prob(), _pass_attempt_bias_allowed(), test_blind_arm_no_longer_asserts_a_rate(), test_restoring_a_bias_is_one_constant(), test_the_gates_are_checked_before_the_no_bias_decline(), test_the_interval_spans_zero_so_the_lane_declines_to_price() (+3 more)

### Community 456 - "NFL historical weather fetch"
Cohesion: 0.18
Nodes (10): DailyLimit, Pacer, consolidate(), era5_check(), game_hours(), log(), main(), om_get() (+2 more)

### Community 463 - "Mobile push notification routing"
Cohesion: 0.20
Nodes (14): NavRef, PushRoute, PicksView, clearNativeLastResponse(), navigateTo(), responseIdentifier(), usePushDeepLink(), setSportForVisit() (+6 more)

### Community 466 - "Mobile settings, sign-in and sportsbooks"
Cohesion: 0.02
Nodes (166): Calls, AuthState, AuthStatus, State, ConnectionMap, providerMeta, SportsbookConnection, SportsbookProvider (+158 more)

### Community 469 - "Multi-book odds ingestion"
Cohesion: 0.05
Nodes (27): _OddsConn, _Resp, _odds_query(), _prop_markets(), _source(), test_a_game_with_no_commence_time_keeps_every_row(), test_a_rejected_book_list_falls_back_to_the_decision_book(), _get() (+19 more)

### Community 47 - "scripts/nfl_edge_gameline_rules.py"
Cohesion: 0.06
Nodes (50): Tee, TestTheWeatherStepWalksTheWindow, _nhl_blended_features(), d(), ats(), bettable_ats(), bh(), board_at() (+42 more)

### Community 470 - "System health check pass tests"
Cohesion: 0.11
Nodes (4): TestHealthCheckIsNotCountedAsAFailingStep, TestPassCompletion, TestPassSteps, _add_run()

### Community 471 - "tests/test_model_game_savepoint.py"
Cohesion: 0.15
Nodes (4): _PoisonConn, _games(), test_a_best_price_timeout_is_the_logged_error_and_the_next_lookup_runs(), test_a_model_sql_error_does_not_poison_the_next_model()

### Community 473 - "Health check pick delivery tests"
Cohesion: 0.17
Nodes (4): TestSignalDelivery, _add_signal(), _iso(), _results()

### Community 474 - "NBA historical odds archive loader"
Cohesion: 0.05
Nodes (41): _Conn, classify(), _fold(), _gid(), _is_half(), iso_z(), load(), match() (+33 more)

### Community 475 - "MLB batter prop log lookback tests"
Cohesion: 0.10
Nodes (9): _Rec, _ScoringConn, _log_sql(), test_batter_log_scan_is_pinned_to_the_lookback_not_the_catalog(), test_five_models_share_one_log_load(), test_no_lineup_does_not_scan_the_log(), test_starter_log_inside_the_batter_loader_uses_the_same_floor(), test_the_batter_loop_hands_one_cache_to_every_model() (+1 more)

### Community 48 - "tests/test_calibration_watch.py"
Cohesion: 0.05
Nodes (15): _Conn, _Res, TestDormantLiveModels, TestItNeverDecides, TestRosterChanges, TestTheRun, TestVerdictChanges, TestVolumeShifts (+7 more)

### Community 482 - "Probability calibration fitting and sweep"
Cohesion: 0.05
Nodes (32): _Conn, apply_calibration(), demote(), ensure_schema(), _era_start(), fit_offset(), fit_platt(), fit_pool() (+24 more)

### Community 488 - "Ungraded model performance reporting tests"
Cohesion: 0.07
Nodes (14): FakeConn, http_server(), live_server(), test_perf_reads_the_matview_not_the_expensive_view(), test_roster_reports_a_registered_but_untrained_model(), _second_arm(), _sql(), test_a_fully_unpriced_recovered_model_reports_no_roi() (+6 more)

### Community 489 - "MLB prop market pre-game tests"
Cohesion: 0.12
Nodes (7): _Conn, test_a_game_with_no_cutoff_fails_open(), test_both_market_relative_loaders_bound_on_the_cutoff(), test_it_compares_parsed_timestamps_not_strings(), test_it_joins_games_and_uses_the_shared_cutoff(), test_the_newest_qualifying_quote_still_wins(), test_the_post_first_pitch_quote_is_dropped_even_though_it_is_newest()

### Community 49 - "Pipeline failure alerting and heartbeats"
Cohesion: 0.06
Nodes (20): FakeConn, TestDeliveryAndNoise, TestHealthCheckOnlyIsNotADirtyPass, TestItCannotBreakTheWorker, TestSilentJobs, TestWhatCountsAsAFailure, _clean_runs(), _posts() (+12 more)

### Community 490 - "NCAAF starter-out research dataset"
Cohesion: 0.10
Nodes (16): LabelSet, build_label_set(), _fetch_lines(), _fetch_raw(), opener_coverage(), _pick_provider(), provider_continuity(), main() (+8 more)

### Community 497 - "Discord void notices and publish keys"
Cohesion: 0.02
Nodes (62): Ledger, _Conn, _KeyConn, _sql_key(), test_a_game_level_key_has_no_tail(), test_discord_led_visibility(), test_the_lock_key_matches_the_sql_the_ledger_was_written_with(), _bind() (+54 more)

### Community 499 - "NHL totals card publishing tests"
Cohesion: 0.10
Nodes (16): NhlTotalBet, _LockConn, _SlateConn, pick_rows(), test_nhl_totals_card_drops_a_bet_under_the_floor(), bet(), _bet(), _iso() (+8 more)

### Community 502 - "Dashboard queries and SQL file runner"
Cohesion: 0.15
Nodes (9): _PoisonConn, _event_index(), _games(), _run(), test_a_failed_savepoint_rollback_falls_back_to_full_rollback(), test_both_prefilters_timing_out_still_reaches_the_pipeline_log(), test_lookahead_timeout_rolls_back_and_scoring_continues(), test_ncaaf_timeout_rolls_back_and_scoring_continues() (+1 more)

### Community 503 - "MLB in-play state alignment"
Cohesion: 0.22
Nodes (6): GameClock, _t(), test_before_first_pitch_and_after_last_play_are_not_priced(), test_between_pas_across_third_out_rolls_over_to_next_half(), test_mid_plate_appearance_is_that_pa_before_state(), test_plays_without_times_are_ignored()

### Community 504 - "Member sportsbooks scratch database tests"
Cohesion: 0.11
Nodes (14): ScratchPostgres, pg_bin(), _code(), test_results_keep_pushes_and_ties_and_carry_no_stake(), test_schema_applies_twice_on_scratch_postgres_and_anon_can_only_read(), test_the_migration_is_one_statement_and_registered(), test_the_second_pass_returns_before_it_locks(), test_the_skip_guard_refuses_every_write_verb() (+6 more)

### Community 51 - "Mobile team stats board and odds"
Cohesion: 0.07
Nodes (63): NextGame, Section, TeamLineQuote, FormGame, FormSummary, headToHead, lineMove, PickRecord (+55 more)

### Community 510 - "Game scorer, Kelly sizing and backtester"
Cohesion: 0.03
Nodes (30): TestAmericanToDecimalScorer, TestBuildInjuryFlag, TestBuildPickLabel, TestConfidenceTier, TestFeatureValue, TestMakePick, TestQuarterKelly, _backtest_golf() (+22 more)

### Community 511 - "Prop odds next-day lookahead tests"
Cohesion: 0.17
Nodes (4): TestTheOddsFetchReachesTomorrow, TestTheScorerReachesTomorrow, _get_events(), _events_src()

### Community 514 - "Team stats thin season checks"
Cohesion: 0.13
Nodes (6): _SeasonConn, test_verify_established_live_season_with_two_snapshots_stays_thin(), test_verify_five_day_span_with_one_snapshot_is_thin(), test_verify_four_day_opening_span_is_still_grace(), test_verify_opening_live_season_is_not_thin(), test_verify_short_historical_season_is_still_thin()

### Community 517 - "NCAAF in-play history ingest tests"
Cohesion: 0.10
Nodes (15): _Conn, _StubEngine, first_signals(), _cand(), _event(), _no_db_school_lookup(), test_a_late_kickoff_falls_back_to_its_utc_dated_games_row(), test_a_market_filter_writes_only_that_market() (+7 more)

### Community 518 - "Weather forecast hour lookahead"
Cohesion: 0.06
Nodes (17): _Resp, TestTheHourIsTheGamesOwn, TestTheRequestCoversTheTargetHour, TestTheStoreReadsTheStartTime, TestTheUmpireLandsOnEveryPass, backfill_weather(), _celsius_to_f(), fetch_and_store_weather_for_date() (+9 more)

### Community 52 - "tests/test_best_line_live.py"
Cohesion: 0.04
Nodes (43): _FakeConn, _best_live_price(), _best_live_side(), _live_book_quotes(), _live_quote_is_on_offer(), best_takeable_quote(), _ev(), _live_pick() (+35 more)

### Community 526 - "NCAAF college data refresh and backfill tests"
Cohesion: 0.16
Nodes (8): _NullConn, backfill_ncaaf(), refresh_ncaaf_games(), test_backfill_returns_totals_when_every_season_succeeds(), test_backfill_survives_a_mid_run_season_failure(), test_refresh_games_happy_path_counts_games(), test_refresh_games_repairs_every_season_and_reports_failures(), test_refresh_stats_isolates_a_failing_season()

### Community 528 - "UFC fight stats scoring tests"
Cohesion: 0.11
Nodes (7): _IngestConn, _ingest(), _one_fight_event(), test_a_late_replacement_is_not_scored_on_the_original_booking(), test_a_misspelled_fighter_is_scored_for_the_side_they_fought_on(), test_a_row_naming_neither_fighter_is_left_unscored(), test_the_same_fight_stored_twice_is_scored_on_both_rows_each_way_round()

### Community 53 - "NBA prop card publishing tests"
Cohesion: 0.05
Nodes (46): _Conn, ev_percentile(), choose(), _detail(), games_with_a_prop_bet(), one_per_game(), per_night(), prop_bets_by_night() (+38 more)

### Community 533 - "NBA team total odds fetch tests"
Cohesion: 0.05
Nodes (49): Clock, FakeResp, _billed(), closes_taken(), event_rows(), fetch_team_totals(), fetches(), _known_games() (+41 more)

### Community 539 - "NFL in-play pick row builder"
Cohesion: 0.09
Nodes (14): _Decision, build_pick(), refuse_publish_reason(), test_a_locked_lane_writes_nothing_further(), test_a_pass_is_never_announced(), test_edge_is_the_platform_edge_not_the_lanes_ev(), test_every_row_key_is_actually_bound_by_the_insert(), test_refuse_publish_allows_a_real_rush_under() (+6 more)

### Community 54 - "tests/test_void_picks.py"
Cohesion: 0.05
Nodes (18): _FakeConn, TestAPostedSignalIsLocked, TestAPostedVoidAnnouncesAfterCommit, TestTheToolRefusesToMatchEverything, TestVoidingAPostedPickIsAnExplicitOptIn, TestWhatMayBeVoided, TestWhatTheVoidWrites, announce_posted_voids() (+10 more)

### Community 545 - "Job heartbeat and stale jobs"
Cohesion: 0.16
Nodes (7): Conn, _build(), test_a_job_marked_disabled_is_not_silent(), test_a_job_that_runs_here_is_not_marked(), test_a_service_leaves_alone_the_jobs_another_service_owns(), test_startup_marks_an_owned_job_that_is_switched_off(), stale_jobs()

### Community 549 - "Database setup and SQL statement splitting"
Cohesion: 0.19
Nodes (4): TestRealSchema, TestSplitter, TestSqliteSchema, _split_sql_statements()

### Community 55 - "NCAAF game-day live loop and feeds"
Cohesion: 0.07
Nodes (22): LiveOddsFeed, GameContext, school(), fetch_scoreboard_cfbd(), fetch_team_ids(), _headers(), _strip_mascot(), fetch_scoreboard() (+14 more)

### Community 550 - "NFL prop odds and backtest"
Cohesion: 0.01
Nodes (92): LazyConnection, _Conn, _Cur, TestBinaryMarket, TestCountDistributions, TestKickoffGate, TestLocalOddsCache, TestPlaceboCannotSilentlyNotHappen (+84 more)

### Community 551 - "MLB renamed franchise game merge tests"
Cohesion: 0.13
Nodes (12): _Conn, apply_one(), canonical(), counts(), main(), plan(), test_a_canonical_id_maps_to_nothing(), test_a_non_mlb_or_malformed_id_is_left_alone() (+4 more)

### Community 553 - "Team board cache refresh step"
Cohesion: 0.15
Nodes (5): _Conn, _Cursor, refresh_team_board_cache(), step_refresh_team_board(), test_one_failing_pair_does_not_stop_the_rest()

### Community 554 - "NBA box score repair tests"
Cohesion: 0.13
Nodes (8): _Conn, boxes_to_repair(), _logs(), _run(), test_a_box_that_does_not_add_up_is_never_written(), test_a_game_nba_com_does_not_list_is_refused(), test_only_the_named_game_is_replaced_delete_first(), test_the_season_repair_names_every_missing_or_wrong_box()

### Community 559 - "Injury adjustment scenario tests"
Cohesion: 0.16
Nodes (3): TestComputeInjuryAdjustment, _compute_injury_adjustment(), _assemble_wnba_features()

### Community 56 - "tests/test_daily_retry.py"
Cohesion: 0.06
Nodes (42): _Conn, _Cursor, _FrozenDatetime, DailyRun, _aborted(), _aborted_row(), _ok(), _ok_row() (+34 more)

### Community 562 - "Discord results recap message tracking"
Cohesion: 0.03
Nodes (37): _Conn, _Ledger, _Resp, build_parser(), _date_is_over(), main(), post_backfill(), test_a_day_that_is_not_over_is_refused() (+29 more)

### Community 565 - "NFL prop sharp devig bet finder"
Cohesion: 0.26
Nodes (4): TestMarketRelative, find_bets(), test_without_ladders_the_pinnacle_path_is_unchanged(), _q()

### Community 566 - "NBA line history pruning protection"
Cohesion: 0.14
Nodes (10): _Conn, thin_repeats(), test_a_thinning_error_that_is_not_a_timeout_is_raised(), test_a_dry_run_counts_and_deletes_nothing(), test_an_unchanged_run_keeps_its_first_and_last_row(), test_every_move_survives_and_every_as_of_price_is_unchanged(), test_paid_history_todays_games_and_other_sports_are_untouched(), test_pre_game_and_in_play_are_separate_runs() (+2 more)

### Community 567 - "Push line change alert tests"
Cohesion: 0.17
Nodes (5): _Conn, _Res, _alerts(), test_a_moneyline_has_no_number_and_still_alerts(), test_a_price_at_another_number_is_not_a_move()

### Community 57 - "tests/test_live_book_move_guard.py"
Cohesion: 0.07
Nodes (39): BookMoveClock, _Unset, _MlbConn, american_to_implied(), _at(), _delaware_ctx(), _dk(), _iso() (+31 more)

### Community 570 - "NHL prop settlement tests"
Cohesion: 0.20
Nodes (6): _Shim, TestSettlement, _bet(), _in_goal(), _result(), _skated()

### Community 576 - "tests/test_weekly_catch_up.py"
Cohesion: 0.18
Nodes (3): _Conn, test_a_failing_savant_refresh_does_not_cost_the_calibration_its_catch_up(), test_ownership_is_checked_per_job()

### Community 581 - "NFL pick game id join tests"
Cohesion: 0.16
Nodes (3): TestTheJoinKeyMatchesPicks, eval_row(), _picks_game_id()

### Community 583 - "NFL pick monitor"
Cohesion: 0.19
Nodes (6): TestClassify, TestImmutabilityContract, TestLatestPerPick, classify(), latest_per_pick(), _row()

### Community 584 - "In-play score change clock"
Cohesion: 0.23
Nodes (5): ScoreClock, test_score_clock_ignores_a_dropped_score_field(), test_score_clock_keeps_games_independent(), test_score_clock_reports_no_event_at_first_sight(), test_score_clock_stamps_the_change_and_holds_it()

### Community 59 - "NFL wind forecast and totals model"
Cohesion: 0.03
Nodes (68): OpenMeteoError, Bet, coverage_check(), expected_true_wind(), fetch_era5(), fetch_issued_forecasts(), fetch_live_forecast(), _frame() (+60 more)

### Community 590 - "Prop odds missing game skip"
Cohesion: 0.15
Nodes (4): FakeConn, _run(), test_event_with_no_games_row_is_skipped_and_others_still_insert(), test_fk_on_insert_does_not_unwrite_the_events_that_already_landed()

### Community 592 - "Shared scripts using JSON and environment"
Cohesion: 0.02
Nodes (95): OddsAPIClient, SnapshotResult, Puller, _ledger_row(), _key(), _ledger_bump(), _ledger_read(), ledger_status() (+87 more)

### Community 599 - "System health check test fixtures"
Cohesion: 0.14
Nodes (4): _FrozenDatetime, _Shim, db(), mlb_wired()

### Community 6 - "Mobile model catalog, filters and thresholds"
Cohesion: 0.02
Nodes (252): Case, Props, RowDef, Props, PropContext, BacktestPickRow, CustomModelStats, ChipGroup (+244 more)

### Community 606 - "NFL in-play pick writer commit tests"
Cohesion: 0.12
Nodes (7): _Conn, test_a_pass_is_never_written_to_picks(), test_an_unresolvable_decision_writes_nothing(), test_game_id_resolves_from_the_book_s_team_names(), test_picks_recorder_drops_a_pass_attempt_over_before_sql(), test_the_announce_runs_after_the_commit_and_after_the_connection_closes(), commit()

### Community 61 - "MLB stats and pitcher ingestor"
Cohesion: 0.04
Nodes (40): TestThePollerCanCreateAGame, backfill_bullpen_stats(), backfill_mlb_stats(), backfill_pitcher_stats(), backfill_player_game_log(), backfill_player_handedness(), _build_pitcher_rows(), _build_team_stats_rows() (+32 more)

### Community 611 - "supabase/functions/revenuecat-webhook/index.ts"
Cohesion: 0.22
Nodes (3): RcEvent, admin, PRODUCT_TO_PLAN

### Community 613 - "supabase/functions/whop-webhook/index.ts"
Cohesion: 0.25
Nodes (4): WhopMembership, signatureValid(), timingSafeEqual(), admin

### Community 616 - "tests/test_nfl_props.py"
Cohesion: 0.22
Nodes (3): TestCardReplay, execute(), fetchall()

### Community 63 - "Football in-play game state"
Cohesion: 0.06
Nodes (31): Read, pace_ratio(), _sigmoid(), under_prob(), _as_float(), _as_int(), _as_opt_float(), _as_opt_int() (+23 more)

### Community 630 - "NHL blocked shots prop settlement tests"
Cohesion: 0.27
Nodes (5): _Shim, TestSettlement, _bet(), _played(), _result()

### Community 636 - "Threshold review schema setup tests"
Cohesion: 0.08
Nodes (8): _DdlConn, _DdlRes, _board_markets(), table(), test_the_mlb_board_and_the_mlb_pull_are_one_set(), test_a_failed_lock_down_does_not_lose_the_table(), test_ensure_schema_commits_the_tables_it_creates(), test_the_tables_are_locked_down_at_the_create_site()

### Community 643 - "Game feature engine helper tests"
Cohesion: 0.12
Nodes (5): TestFeatureMap, TestHasReturnee, TestMarketForOdds, _has_returnee(), _market_for_odds()

### Community 645 - "NCAAF game-day fetch cadence tests"
Cohesion: 0.24
Nodes (6): _Ctx, _ev(), test_a_single_failed_summary_does_not_drop_the_other_games(), test_cfbd_mode_does_no_per_game_fetching(), test_espn_states_are_fetched_in_parallel_and_stay_aligned(), test_unknown_matchups_never_cost_a_fetch()

### Community 651 - "NFL wind bettable book filter"
Cohesion: 0.11
Nodes (5): TestTheCardFilters, TestTheListIsShared, _attach(), books(), _quote()

### Community 655 - "Mobile subscription entitlement"
Cohesion: 0.60
Nodes (5): useAuth, useSubscription, SubscriptionRow, fetchSubscription(), isEntitled()

### Community 659 - "WNBA injury team id fallback"
Cohesion: 0.26
Nodes (4): TestCoreTeamsFallback, _fetch_wnba_espn_team_ids_core(), _fake_fetch(), _listing()

### Community 667 - "Mobile bankroll local store"
Cohesion: 0.23
Nodes (12): KeyValueStore, check(), eq(), fakeStore(), interleaving(), slowStore(), storage(), createBankrollStore() (+4 more)

### Community 668 - "Prop pricing, devig and player names"
Cohesion: 0.01
Nodes (171): MarketBet, TestLocalCacheGuards, TestMarketGrading, TestNaNIsAbsent, TestNormaliseName, ladders_or_empty(), norm_player_name(), activate() (+163 more)

### Community 669 - "Pick integrity test database shim"
Cohesion: 0.22
Nodes (3): _Shim, discord_sent(), health_db()

### Community 67 - "tests/test_game_market_gate.py"
Cohesion: 0.06
Nodes (49): GateVerdict, MarketBookend, PublicSplits, apply_to_picks(), _as_float(), bookend_from_odds(), evaluate(), fair_prob() (+41 more)

### Community 671 - "Team total market settlement tests"
Cohesion: 0.22
Nodes (3): _SqliteShim, test_the_opening_signal_shadow_track_grades_it_the_same_way(), test_the_settler_writes_the_home_team_s_result()

### Community 674 - "NBA public splits quality backfill"
Cohesion: 0.18
Nodes (5): _CountingConn, backfill_quality(), test_an_existing_table_gets_the_quality_column(), test_the_backfill_adds_the_column_and_commits_once(), test_the_backfill_rolls_back_when_a_count_is_not_what_was_measured()

### Community 678 - "NFL prop market card tests"
Cohesion: 0.22
Nodes (3): TestMarketCard, execute(), fetchall()

### Community 68 - "NBA second-model prop study"
Cohesion: 0.05
Nodes (41): Rec, Shape, appearances(), box_tables(), build(), check_close_prior(), consensus_number(), empty_times() (+33 more)

### Community 683 - "Probability calibration fitting tests"
Cohesion: 0.04
Nodes (31): _FakeConn, _SchemaRecordingConn, fit_model(), _calibration_error_weighted(), calibration_metrics(), poisson_probability_metrics(), test_a_map_that_does_not_help_out_of_sample_is_not_applied(), test_a_map_that_helps_is_applied() (+23 more)

### Community 69 - "tests/test_pick_integrity.py"
Cohesion: 0.04
Nodes (40): _Conn, _add_pick(), _health(), test_a_label_may_not_name_a_market_the_pick_does_not_settle_on(), test_a_label_naming_the_other_team_is_refused(), test_a_market_nobody_has_taught_it_is_never_refused(), test_a_moneyline_naming_the_other_team_is_refused(), test_a_producer_that_does_not_supply_side_and_line_is_refused() (+32 more)

### Community 693 - "NHL props newest fetch shopping"
Cohesion: 0.21
Nodes (4): _Conn, TestOnlyTheNewestFetchIsShopped, latest_quotes(), fetchall()

### Community 696 - "NBA public splits archive store tests"
Cohesion: 0.12
Nodes (6): _NoDB, _Store, _scoreboard(), test_a_late_game_still_in_play_after_midnight_is_archived_at_the_next_pass(), test_a_stored_game_is_not_written_again_and_a_splitless_game_is_retried(), _wire_archive()

### Community 698 - "Mobile bankroll unit size stepper"
Cohesion: 0.32
Nodes (7): BankrollSettings, useBankroll(), canStepUnitPct(), sanitizeUnitPct(), stepUnitPct(), store, BANKROLL_DEFAULTS

### Community 7 - "Pick settlement and CLV capture"
Cohesion: 0.01
Nodes (137): ConnectionLost, DBConnection, _FakeStatsapi, _SqliteShim, connection_lost(), poll_once(), _games_needing_synthesis(), _log_pipeline() (+129 more)

### Community 70 - "tests/test_record_one_pick_per_event.py"
Cohesion: 0.05
Nodes (42): _CaptureConn, _RecordingConn, _code(), _copy_for_node(), _fn(), _node(), _read(), test_a_custom_model_counts_the_kept_copy_once() (+34 more)

### Community 705 - "NFL wind and opener publishing"
Cohesion: 0.10
Nodes (17): _LockConn, TestNoneRowNeverLocks, _american_to_prob(), _changed(), _clear_scored_row(), _flush_board_safe(), _flush_snapshots_safe(), latest_eval_rows() (+9 more)

### Community 711 - "NHL game features and starter injuries"
Cohesion: 0.11
Nodes (7): TestHasStarterOut, TestOpeningNightIsEarlySeason, _blk_nhl_asof(), _blk_nhl_loc_goals(), _blk_nhl_rolling_goals(), _build_nhl_features_from_bulk(), _has_starter_out()

### Community 713 - "Free pick and X results publishing tests"
Cohesion: 0.04
Nodes (23): _CursorResult, _Conn, _go(), _pick(), test_every_offerable_book_has_a_human_name_on_both_surfaces(), test_the_free_card_names_the_cheaper_book(), test_the_free_card_query_reads_the_columns_it_renders(), test_the_good_to_clause_is_dropped_not_truncated_when_it_will_not_fit() (+15 more)

### Community 717 - "NFL in-play pick audit recorder"
Cohesion: 0.11
Nodes (8): TeeRecorder, _OpenConn, test_a_failing_announcer_cannot_undo_or_fail_the_write(), test_a_failing_recorder_cannot_take_the_other_down(), boom(), test_a_written_bet_is_announced_with_its_own_game_date(), test_an_unlocked_lane_does_write(), test_the_audit_log_is_written_before_the_database()

### Community 73 - "nfl/live_model/tests: test_props + props"
Cohesion: 0.08
Nodes (34): PropProjection, GameState, PlayerState, _accrued(), _count(), detect_inactive(), price_over(), project() (+26 more)

### Community 758 - "Deploy checks and job queue"
Cohesion: 0.07
Nodes (17): _Conn, test_a_declared_job_carries_its_run_after(), test_a_failing_check_raises_so_the_queue_announces_it(), test_a_job_can_only_name_a_registered_check(), test_enqueue_rejects_a_naive_run_after(), test_enqueue_stores_run_after(), test_every_check_is_read_only(), test_the_claim_waits_for_run_after() (+9 more)

### Community 77 - "tests/test_wnba_prop_market.py"
Cohesion: 0.05
Nodes (29): _FakeConn, _QuoteConn, apply_price_floor(), norm_name(), pick_rows(), player_ids(), publish(), render() (+21 more)

### Community 78 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.09
Nodes (16): _After, _Conn, _RaceConn, TestFlexedKickoffRefreshes, TestLockSurvivesNothing, TestNoneRowBesideABetIsCleared, TestPublishRace, TestPublishScored (+8 more)

### Community 79 - "NHL derivative totals walk-forward model"
Cohesion: 0.07
Nodes (38): Market, build_p1_frame(), build_team_frame(), day_interval(), _ew(), fit(), game_means(), _implied_vec() (+30 more)

### Community 790 - "Prop no-bet rows tipoff tests"
Cohesion: 0.07
Nodes (9): _Board, _Clock, _PollConn, _fake_datetime_class(), _game(), _iso(), test_the_poller_keeps_prop_no_bet_rows_the_refresh_pass_still_clears(), test_the_poller_tells_the_scorer_to_leave_prop_rows_alone() (+1 more)

### Community 8 - "Mobile player log and matchup stats"
Cohesion: 0.02
Nodes (264): Props, PlayerNextGame, Section, Args, PlayerStatKey, reachFrame, HitMode, HitSelection (+256 more)

### Community 83 - "tests/test_nhl_props.py"
Cohesion: 0.06
Nodes (14): TestEveryLiveModelIsWiredEverywhere, TestTheBacktestGradesTheRuleTheCardPlays, TestTheCard, TestTheDistribution, TestTheGoalieFrame, TestTonightsRowIsATrainingRow, implied(), pick_rows() (+6 more)

### Community 84 - "NBA team total luck replay study"
Cohesion: 0.05
Nodes (30): TeamTotalDecision, book_ages(), decide(), record(), home_part(), load_artifact(), newest_season(), pricing_dist() (+22 more)

### Community 848 - "Prop odds book update time"
Cohesion: 0.26
Nodes (6): _Conn, _parse(), test_a_row_built_without_the_key_still_inserts_as_null(), test_no_clock_anywhere_is_none_not_our_fetch_time(), test_the_column_is_added_only_when_the_catalog_lacks_it(), test_the_markets_own_clock_is_stored_else_the_books()

### Community 85 - "tests/test_recap_retries_a_skipped_day.py"
Cohesion: 0.06
Nodes (25): _LiteConn, World, _add_pick(), _grade(), _lite(), _schema(), test_a_day_with_nothing_counting_posts_nothing_and_logs_nothing(), test_a_failed_receipt_never_reposts_the_day() (+17 more)

### Community 851 - "NHL derivative odds history purchase"
Cohesion: 0.07
Nodes (22): Meter, _Meter, _Resp, _blank_row(), _done_ids(), _ensure_ledger(), estimate_credits(), format_plan() (+14 more)

### Community 854 - "Mixed pipeline and prop tests"
Cohesion: 0.07
Nodes (12): TestIngestEventsDoesNotShadowItsMarkets, _write(), test_the_halftime_distribution_refuses_a_choosing_season_without_enough_earlier_games(), rows(), test_live_prop_pull_asks_for_the_sharp_book(), fake_event_props(), fetchall(), fetchall() (+4 more)

### Community 856 - "NHL stale team log detection"
Cohesion: 0.29
Nodes (4): _GamesConn, stale_teams(), fetchall(), test_a_scheduled_game_missing_from_the_logs_marks_both_teams_stale()

### Community 861 - "NFL line snapshot publishing tests"
Cohesion: 0.15
Nodes (7): TestPublishLineSnapshots, TestSnapshotRowParams, publish_line_snapshots(), snapshot_row_params(), _csv_row(), execute(), _write_snapshot_csv()

### Community 866 - "NBA offset ridge regression"
Cohesion: 0.15
Nodes (5): OffsetRidge, choose_C_linear(), model_move(), _mse(), outcome()

### Community 88 - "NBA prop market decision tests"
Cohesion: 0.04
Nodes (53): NbaPropBet, _PublishConn, _SettleConn, pick_label(), pick_rows(), _quiet(), test_reclaim_is_immediate_because_the_lock_proves_orphanhood(), test_there_is_no_shell_or_command_column() (+45 more)

### Community 898 - "Pipeline watch reporting and ledger"
Cohesion: 0.07
Nodes (24): _Conn, test_a_clean_run_still_posts(), test_a_confirmed_post_is_ledgered_so_the_run_can_be_verified(), test_a_failed_ledger_does_not_lose_the_report(), execute(), test_a_failed_query_rolls_back_and_does_not_sink_the_run(), test_a_fresh_sweep_and_savant_produce_no_finding(), test_a_missing_sweeps_table_is_reported_not_swallowed() (+16 more)

### Community 9 - "Mobile Lines board on Picks"
Cohesion: 0.04
Nodes (113): LinesMarket, LinesMarkPick, linesMarks, LinesMlMode, LinesOddsRow, LinesPickRef, LinesSheetRow, LinesSheetSide (+105 more)

### Community 90 - "Mobile matchup grading and stat pills"
Cohesion: 0.04
Nodes (62): MatchupGrade, MatchupInfo, TonightMatchupRow, check(), grade(), main(), read(), defenceMetricLabel() (+54 more)

### Community 909 - "NBA team total odds fake feed"
Cohesion: 0.22
Nodes (4): FakeFeed, fn(), logged(), call()

### Community 914 - "NBA injury report date scope"
Cohesion: 0.33
Nodes (3): _DatesConn, scope_dates(), test_scope_is_every_game_date_and_the_day_before_newest_first()

### Community 92 - "tests/test_ncaaf_prop_odds.py"
Cohesion: 0.05
Nodes (27): _Conn, _Resp, _market_chunks(), _football_map(), resolver(), scope(), test_a_book_we_did_not_ask_for_is_never_written(), test_a_day_with_no_college_games_spends_nothing() (+19 more)

### Community 926 - "Command-line research scripts"
Cohesion: 0.02
Nodes (78): Pick, TestTheDropIsDeclared, run_synthesizer(), _fmt_edge(), _fmt_odds(), main(), _pick_card(), render_email() (+70 more)

### Community 94 - "Social post queue and drain"
Cohesion: 0.08
Nodes (40): QueueRejected, test_enqueue_inserts_a_thread_and_refuses_a_second_copy(), test_enqueue_refuses_a_url_unless_allow_link_is_set(), test_enqueue_stores_images_and_a_reply_target(), test_the_cli_can_enqueue_one_image_without_posting(), _actionable(), _as_utc(), _attach_media() (+32 more)

### Community 95 - "tests/test_ncaaf_pbp_store.py"
Cohesion: 0.09
Nodes (16): _Conn, load_season_from_db(), _report_ranges(), _plays(), test_a_rerun_updates_rather_than_duplicating(), test_a_season_in_neither_place_is_an_error_not_a_short_corpus(), test_a_season_survives_the_round_trip_in_the_cfbd_spelling(), test_a_season_with_no_plays_writes_nothing_and_says_so() (+8 more)

### Community 96 - "tests/test_heartbeat_watchdog.py"
Cohesion: 0.07
Nodes (28): _FakeConn, _FakeCursor, _break_db(), sink(), test_a_failed_post_does_not_start_the_throttle(), test_a_healthy_start_never_announces_a_recovery(), test_a_returning_outage_alerts_again_immediately(), test_a_silent_failure_alerter_is_caught_by_the_watchdog() (+20 more)

### Community 97 - "Discord pick price and field rendering"
Cohesion: 0.04
Nodes (43): _FakeConn, _sig(), test_a_strictly_better_book_becomes_the_headline(), test_an_equal_or_worse_price_never_replaces_draftkings(), test_best_odds_never_reaches_the_qualifying_gate(), test_draftkings_winning_its_own_shop_is_published_as_draftkings(), test_every_pre_game_producer_computes_good_to(), test_good_to_is_published_when_the_producer_supplies_it() (+35 more)

### Community 99 - "Record correction posts to Discord and X"
Cohesion: 0.03
Nodes (54): LedgerUnread, Conn, Ledger, _Result, delete_custom_record_post(), _jump(), _pin(), _place() (+46 more)

### Community 100 - "Odds pruning opener and close tests"
Cohesion: 0.05
Nodes (22): ncaaf_line_bookmaker(), _unprotected(), test_prune_never_touches_cfbd_archive_lines(), test_the_prune_protects_every_ladder_source_by_its_writer_s_own_name(), test_the_two_prune_tiers_never_select_a_path_kept_sport(), _prune(), _quotes(), test_both_delete_tiers_spare_the_keep_set() (+14 more)

### Community 102 - "scripts/nfl_edge_live_rush_pace.py"
Cohesion: 0.18
Nodes (26): _asof(), boot_p(), build_state(), first(), grade(), initial_last(), load_pbp(), main() (+18 more)

### Community 103 - "NBA prop projection tests"
Cohesion: 0.05
Nodes (29): _art(), _proj(), _q(), _run(), _settle(), test_a_book_hanging_two_lines_for_one_player_is_refused(), test_a_decision_with_no_bet_is_still_a_decision(), test_a_past_game_never_projected_gets_the_newest_espn_pull_55_minutes_before_its_tip() (+21 more)

### Community 104 - "Kalshi ladder and game ingestors"
Cohesion: 0.06
Nodes (23): event_code(), event_date(), kalshi_school(), _num(), probe(), record_game_markets(), resolve_events(), rows_for() (+15 more)

### Community 105 - "NBA game market feature study"
Cohesion: 0.06
Nodes (35): cache_for(), check_cells(), combine_times(), f2_cells(), f2_point(), f6a_placebo(), f6a_point(), f6a_strength() (+27 more)

### Community 107 - "tests/test_prop_calibrated_decision.py"
Cohesion: 0.06
Nodes (30): apply_prop_daily_cap(), bets(), dedupe_player_props(), _downgrade(), _is_paused_row(), _bet(), _identity_cal(), _prop() (+22 more)

### Community 108 - "NCAAF in-play quote serving"
Cohesion: 0.09
Nodes (17): correct_for_pregame(), _load_pregame_calibration(), pregame_dog_points(), test_a_big_dog_is_marked_down_hard(), test_a_corrupt_artifact_leaves_the_probability_alone(), test_a_favourite_is_marked_up(), test_a_missing_artifact_leaves_the_probability_alone(), test_a_pick_em_is_barely_touched() (+9 more)

### Community 109 - "NBA fourth search derivative markets"
Cohesion: 0.07
Nodes (31): calibrated_refs(), cell_specs(), choosing(), decision_quotes(), derivative_data(), emit_f1(), emit_f4(), f1_fair() (+23 more)

### Community 110 - "tests/test_mobile_line_movement.py"
Cohesion: 0.08
Nodes (27): _fn(), _read(), _run(), test_a_cut_table_keeps_the_pick_and_says_what_it_covers(), test_a_cut_window_keeps_the_pick_row_on_the_8_row_table(), test_a_pick_made_after_the_cards_start_never_reads_since_your_pick(), test_after_the_start_the_verdict_is_not_graded(), test_an_old_snapshot_is_not_the_price_at_the_pick() (+19 more)

### Community 111 - "tests/test_live_calibration.py"
Cohesion: 0.06
Nodes (33): decide(), pick(), test_a_peak_with_no_plateau_anywhere_is_labelled_as_one(), test_a_prob_cut_and_an_ev_cut_select_different_picks(), test_calibration_also_scores_ev_against_realised_roi(), test_calibration_is_empty_rather_than_wrong_with_nothing_settled(), test_calibration_reports_the_gap_between_claim_and_reality(), test_expected_value_matches_the_hand_calculation() (+25 more)

### Community 112 - "NBA in-game luck study one"
Cohesion: 0.08
Nodes (28): attach_rates(), build(), close_totals(), decisions(), eligible(), fair_mu(), fit_w(), gate_passes() (+20 more)

### Community 117 - "NBA lineup stint derivation tests"
Cohesion: 0.07
Nodes (50): _and_one_follows(), dead_ball_rebounds(), derive_stints(), ft_info(), order_plays(), possession_ends(), _blowout_q4(), derive() (+42 more)

### Community 118 - "NBA play-by-play parsing tests"
Cohesion: 0.06
Nodes (28): _last(), match_games(), match_names(), resolve_map(), _g(), _game_recs(), _rec(), _summary() (+20 more)

### Community 119 - "tests/test_ncaaf_live_notify.py"
Cohesion: 0.05
Nodes (18): _load_write_picks(), _restore_stubbed_modules(), test_a_caller_supplied_connection_is_not_closed_by_the_write(), test_a_failing_notifier_never_breaks_pricing(), test_a_full_slate_announces_once(), test_a_live_bet_notifies_push_and_discord(), test_a_locked_lane_is_not_rewritten(), test_a_locked_lane_keeps_notifying_after_the_engine_stops_betting() (+10 more)

### Community 122 - "NCAAF quarterback team features"
Cohesion: 0.19
Nodes (16): build_qb_team_features(), _feat(), _frame(), _qb_rows(), test_a_games_features_never_use_that_game(), test_current_qb_is_the_previous_games_primary(), test_empty_input_returns_the_right_shape(), test_first_game_has_no_qb_features_at_all() (+8 more)

### Community 126 - "Live monitor dashboard data store"
Cohesion: 0.09
Nodes (25): meta(), ops(), snapshot(), api_rollup(), call_timeline(), calls_since(), community(), scalar() (+17 more)

### Community 127 - "Prop book sweep bettability guard"
Cohesion: 0.25
Nodes (6): soft_verdict(), test_a_bettable_book_still_passes(), test_an_unbettable_book_is_excluded_however_good_its_numbers(), test_every_incumbent_soft_book_is_bettable(), test_the_clause_is_not_dead_code(), _verdict()

### Community 128 - "tests/test_settled_record_is_immutable.py"
Cohesion: 0.05
Nodes (23): _code(), test_a_dedicated_live_lane_still_counts_and_a_pre_game_in_play_pick_does_not(), test_a_paused_model_is_not_an_excluded_model(), test_a_voided_pick_is_still_out_of_the_record(), test_both_published_views_keep_the_live_date_gate(), test_both_rules_name_the_two_exits_and_not_the_paused_flag(), test_both_views_are_redefined_by_name(), test_every_explicit_exclusion_names_who_asked_for_it() (+15 more)

### Community 130 - "features/golf_feature_engine.py"
Cohesion: 0.08
Nodes (26): assemble_player_features(), _avg_finish(), compute_golf_target(), compute_matchup_target(), _event_finishes(), _f(), _field_features(), _made_cut_rate() (+18 more)

### Community 132 - "ncaaf_live/tests/test_states.py"
Cohesion: 0.13
Nodes (23): build_states(), _detect_score_convention(), _platform(), _plays(), _post_convention_game(), _pre_convention_game(), test_a_scoring_plays_state_does_not_contain_its_own_points(), test_ambiguous_convention_refuses_to_build() (+15 more)

### Community 133 - "tests/test_bovada_feed.py"
Cohesion: 0.10
Nodes (30): _american(), _complete(), _num(), parse_coupon(), poll_once(), _row_for(), _seen_key(), _stamp() (+22 more)

### Community 136 - "NCAAF cross-book opener model"
Cohesion: 0.13
Nodes (12): build_artifact(), build_band_artifact(), test_absent_ceiling_means_unbounded(), test_artifact_shape(), test_band_volumes_sum_to_the_single_gate_backtest(), test_both_band_probs_clear_their_configured_floors(), test_each_band_stands_on_its_own_above_the_4pct_bar(), test_flat_prob_clears_the_configured_floor() (+4 more)

### Community 139 - "NFL in-play edge season replays"
Cohesion: 0.13
Nodes (34): books_per_snapshot(), cell(), finalize_states(), h1(), h2(), h2_accuracy(), h3(), h3_accuracy() (+26 more)

### Community 14 - "NBA team total under model tests"
Cohesion: 0.05
Nodes (32): quote_frame(), _decide(), _proj(), _rows(), _season(), _target(), test_a_fetch_older_than_an_hour_is_not_visible(), test_a_game_is_decided_on_a_fresh_fetch_45_to_66_minutes_before_tip() (+24 more)

### Community 142 - "tests/test_health_pregame_prices_current.py"
Cohesion: 0.10
Nodes (30): _at(), _game(), _row(), _run(), test_a_broken_feed_read_is_an_error_and_rolls_back(), test_a_broken_query_is_an_error_and_rolls_back(), test_a_cancelled_fight_and_a_pulled_game_do_not_raise_the_alarm(), test_a_dead_feed_with_no_priced_game_is_a_crit() (+22 more)

### Community 145 - "WNBA prop feature building"
Cohesion: 0.09
Nodes (21): build_bulk_wnba_prop_lookups(), _build_player_row(), build_wnba_prop_scoring_rows(), build_wnba_prop_training_dataset(), _context_features_for(), _opp_team_stat(), _recent_starter(), _rest_days() (+13 more)

### Community 147 - "scripts/nfl_edge_extreme_props.py"
Cohesion: 0.12
Nodes (29): actuals(), add_modes(), bar(), candidates(), cell(), decision_boards(), devig(), fit_holdout() (+21 more)

### Community 148 - "scripts/nfl_edge_settlement.py"
Cohesion: 0.14
Nodes (30): add_test(), attach(), banner(), bh(), board(), boot_draws(), cell(), choose() (+22 more)

### Community 153 - "tests/test_agents_contract.py"
Cohesion: 0.06
Nodes (19): _labelled_retired(), test_blocked_items_are_marked_so_the_agent_skips_them(), test_every_backlog_item_is_a_checkbox(), test_neither_agent_may_change_a_model_threshold(), test_the_agents_are_findable_from_the_file_every_session_reads(), test_the_backlog_does_not_promise_an_agent_that_no_longer_runs(), test_the_backlog_exists_and_has_items(), test_the_contract_documents_every_agent_by_name() (+11 more)

### Community 159 - "WNBA results ingestor"
Cohesion: 0.04
Nodes (57): _default_wnba(), build_log_row(), _core_athlete(), _deref(), _et_date(), _fetch_core_box_players(), _fetch_core_games(), _fetch_scoreboard() (+49 more)

### Community 16 - "NBA public betting splits ingestor"
Cohesion: 0.11
Nodes (16): active_queries(), archive_ready(), ensure_table(), fetch_scoreboard(), keep_for_poll(), _known_abbrs(), load_games_index(), not_started() (+8 more)

### Community 161 - "NBA stats and box score ingestor"
Cohesion: 0.09
Nodes (24): backfill_nba_stats(), _box_adds_up(), _build_game_id(), _build_game_rows(), _build_player_log_rows(), _build_team_stat_rows(), _fetch_league_game_log(), ingest_nba_game_log_for_date() (+16 more)

### Community 163 - "NBA derivative market lab"
Cohesion: 0.09
Nodes (35): add_team(), am_to_dec(), bars_for(), bet_list(), blind(), boot_ci(), build_line_rows(), build_outcomes() (+27 more)

### Community 167 - "scripts/nfl_preflight.py"
Cohesion: 0.19
Nodes (17): _load_postgres_schema(), check(), check_cards_run(), check_config_gates(), check_cost(), check_data(), data_check(), check_import_shadowing() (+9 more)

### Community 168 - "Mobile live and deep link source checks"
Cohesion: 0.02
Nodes (78): test_every_revoke_names_the_roles_rather_than_public(), test_it_does_not_enable_rls_blind(), test_odds_keeps_select_for_the_app(), test_the_app_write_tables_are_not_touched(), test_the_two_rls_off_tables_lose_everything(), _read(), test_a_sport_switch_cannot_report_a_game_finishing(), test_all_three_segments_are_unconditional() (+70 more)

### Community 169 - "NBA halftime in-game research"
Cohesion: 0.06
Nodes (35): axes_of(), bar9(), cell_key(), _floats(), house_bar4(), house_verdict(), load_cells(), main() (+27 more)

### Community 17 - "NFL luck gap edge study"
Cohesion: 0.08
Nodes (44): backfill_cost(), bets(), bh(), clean_2h(), fmt(), forward_2026(), hdr(), _line_models() (+36 more)

### Community 173 - "tests/test_decide_on_calibrated.py"
Cohesion: 0.06
Nodes (19): _pick(), _pick_at(), test_a_calibrated_cut_is_paired_with_a_calibrated_decision(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(), test_a_genuinely_big_edge_still_fires_after_calibration(), test_a_hot_model_no_longer_fires_the_marginal_bet(), test_a_model_on_a_calibrated_cut_is_not_paused(), test_a_paused_model_never_fires_regardless() (+11 more)

### Community 176 - "NBA prop projection lab"
Cohesion: 0.08
Nodes (50): apply_calibration(), fit_platt(), implied(), _logit(), bars(), bh_read(), blind(), boot() (+42 more)

### Community 181 - "NBA in-game play data and staleness"
Cohesion: 0.04
Nodes (56): attach_pinnacle(), box_checks(), build(), drop_wild_wallclocks(), espn_map(), foul_flags(), is_heave(), keep_in_play() (+48 more)

### Community 182 - "tests/test_model_artifacts_load.py"
Cohesion: 0.09
Nodes (17): _git(), _gitignore_keep_pkls(), _ignored(), _manifest_keep_pkls(), _newest_per_model(), test_a_path_that_is_not_ignored_is_not_reported(), test_a_superseded_timestamped_pkl_is_ignored(), test_an_ignored_path_comes_back_byte_identical() (+9 more)

### Community 183 - "Model quality alerts monitor"
Cohesion: 0.08
Nodes (22): record_exclusion_sql(), test_clv_clear_negative_vs_baseline_is_flagged(), test_raw_one_sided_clv_is_ignored(), test_roi_collapse_is_crit_when_hit_rate_dies(), test_roi_ignores_unpriced_profit_flat(), test_volume_spike_vs_median(), test_the_exclusion_sql_is_a_conjunction_of_negations(), _job_model_quality() (+14 more)

### Community 185 - "scripts/game_line_market_sweep.py"
Cohesion: 0.08
Nodes (22): _by_month(), collect_picks(), devig(), _gap_seconds(), grade(), implied(), iter_months(), load() (+14 more)

### Community 186 - "NHL prop backtest and namesakes"
Cohesion: 0.11
Nodes (23): books(), card(), claimed_vs_realised(), day_interval(), line(), load(), main(), namesakes() (+15 more)

### Community 187 - "NFL 2025 in-play edge study"
Cohesion: 0.12
Nodes (26): fit_models(), attach_games(), attach_state(), bh(), check_possession(), diagnostics(), dispersion(), fit_totals_margin() (+18 more)

### Community 188 - "tests/test_pass_instrumentation.py"
Cohesion: 0.06
Nodes (11): test_a_dead_database_does_not_fail_the_step(), test_a_raised_failure_still_records_the_exception(), test_a_step_that_raises_is_still_TIMED(), test_a_step_that_raises_still_raises(), boom(), test_a_step_that_returns_false_records_a_REASON(), test_a_successful_step_records_a_duration(), test_every_step_name_in_the_dispatch_table_is_reachable() (+3 more)

### Community 189 - "Team stats games played invariants"
Cohesion: 0.08
Nodes (14): impossible_games_played(), _played_actual(), test_a_missing_count_is_reported_not_silently_passed(), test_an_honest_row_passes(), test_claiming_fewer_games_than_played_is_fine(), test_feb_gp_climbing_vs_zero_regular_season_still_fails(), test_mlb_twin_codes_do_not_false_crit(), test_mlb_twin_reverse_lookup_also_resolves() (+6 more)

### Community 190 - "tests/test_db_adapt_sql.py"
Cohesion: 0.09
Nodes (23): _adapt_sql(), _convert_params(), _convert_params_outside_literals(), _named(), test_a_block_comment_is_skipped_too(), test_a_colon_word_inside_a_comment_is_not_a_placeholder(), test_a_dash_dash_inside_a_literal_is_data_not_a_comment(), test_a_line_comment_ends_at_the_newline() (+15 more)

### Community 191 - "Market-relative prop edge tests"
Cohesion: 0.12
Nodes (12): _q(), test_a_different_line_is_never_compared(), test_a_market_under_the_coverage_floor_is_excluded(), test_a_prop_the_sharp_book_did_not_price_is_counted_not_traded(), test_agreement_produces_no_bet(), test_an_equal_line_with_a_real_disagreement_is_a_bet(), test_devig_removes_the_hold_symmetrically(), test_devig_reports_one_way_markets_as_none() (+4 more)

### Community 195 - "tests/test_mobile_contrast_tokens.py"
Cohesion: 0.12
Nodes (30): _code_lines(), _ionicon_colors(), _lum(), _over(), _ratio(), _read(), _rgb(), test_badge_glyph_tracks_dynamic_type() (+22 more)

### Community 197 - "Daily pipeline runner and steps"
Cohesion: 0.03
Nodes (57): run_bullpen_ingestor(), run_nba_prop_odds_ingestor(), run_wnba_prop_odds_ingestor(), format_view_migration_failure(), check_env(), _import_step(), run_daily_pipeline(), step_apply_column_migrations() (+49 more)

### Community 198 - "NBA game four part one tests"
Cohesion: 0.06
Nodes (32): _base(), _fair(), _ladder_quotes(), _offered(), _offers(), _period_games(), _rows(), _rung() (+24 more)

### Community 20 - "Shared config and database scripts"
Cohesion: 0.01
Nodes (95): _connect(), _open(), _session_options(), setup_database(), backfill_savant_stats(), _df_to_rows(), _fetch_pitcher_gb_pct(), _fetch_savant_csv() (+87 more)

### Community 201 - "NBA second game line move tests"
Cohesion: 0.06
Nodes (39): _priced_season(), _q(), _sched(), _season_games(), _signal(), _split(), _stub_main(), test_a_fetch_after_T_never_reaches_the_move() (+31 more)

### Community 206 - "Mobile live game status checks"
Cohesion: 0.07
Nodes (22): deadPoller, delayed, finalNoScore, future, golfDay2, live, live1, liveFinal (+14 more)

### Community 207 - "NBA box score row building tests"
Cohesion: 0.16
Nodes (18): box_rows(), dnp_kind(), minutes_to_float(), minutes_to_seconds(), starter_update_batches(), _box(), test_a_blank_minutes_string_is_null_not_zero(), test_a_dnp_row_has_null_minutes_and_its_reason_and_is_not_a_starter() (+10 more)

### Community 214 - "NFL prop 2026 remeasure pins"
Cohesion: 0.22
Nodes (3): test_the_2026_remeasure_did_not_move_the_24h_ceiling(), test_the_2026_remeasure_did_not_move_the_side_floors(), test_the_historical_grader_does_not_read_kalshi()

### Community 215 - "Intraday refresh freshness skipping"
Cohesion: 0.11
Nodes (12): _is_fresh(), _minutes_since(), step_player_news(), step_weather(), _age(), test_an_unknown_age_refetches_rather_than_skipping(), test_fresh_data_is_skipped(), test_stale_data_is_refetched() (+4 more)

### Community 219 - "tests/test_nfl_live_leader_state.py"
Cohesion: 0.14
Nodes (19): situation(), status(), test_a_conversion_try_is_skipped(), test_a_previous_quarters_play_is_not_the_state(), test_a_timeout_is_skipped_for_the_play_before_it(), test_after_a_scoring_play_nothing_is_evaluated(), test_after_the_kickoff_lands_the_receiver_has_the_ball(), test_an_ordinary_snap_is_evaluable_with_the_training_inputs() (+11 more)

### Community 221 - "tests/test_ncaaf_qb_ingestor.py"
Cohesion: 0.11
Nodes (24): _athlete_stats(), _comp_att(), parse_qb_game_stats(), _split_ratio(), test_split_ratio(), _parse(), _payload(), _team() (+16 more)

### Community 224 - "NFL in-play win probability hypotheses"
Cohesion: 0.13
Nodes (18): h1_calibration(), h1_frame(), pool_all(), summ(), async_check(), boot(), cell(), cp_roi() (+10 more)

### Community 229 - "NBA public splits parsing tests"
Cohesion: 0.09
Nodes (26): build_rows(), clean_pair(), match_game(), parse_v2_sides(), _entry(), test_a_late_tip_matches_its_et_dated_game_id(), test_a_lone_side_is_kept_as_served(), test_a_pair_that_does_not_sum_to_100_is_dropped() (+18 more)

### Community 234 - "tests/test_team_board_cache.py"
Cohesion: 0.11
Nodes (7): team_board_pairs(), team_board_seasons(), _cols(), test_every_team_sport_gets_last_this_and_next_year(), test_the_cache_the_refresh_and_the_thin_function_name_the_same_columns(), test_the_compute_and_the_refresh_are_revoked_by_name(), test_the_two_functions_are_recorded_as_revoked_in_the_manifest()

### Community 237 - "House juice price floor tests"
Cohesion: 0.08
Nodes (19): min_odds_for(), _blocked_by_min_odds(), _apply_price_floor(), test_a_pick_with_no_price_is_never_blocked_by_the_floor(), test_an_explicit_floor_wins_in_BOTH_directions(), test_every_registered_model_has_an_effective_floor(), test_ordinary_prices_still_fire(), test_the_default_is_overridable_without_a_code_change() (+11 more)

### Community 238 - "nfl/live_model/tests/test_rush_attempt_pace.py"
Cohesion: 0.09
Nodes (16): _price(), test_a_line_he_has_already_passed_is_not_a_live_proposition(), test_a_missing_accrued_count_is_refused_not_treated_as_zero(), test_a_reachable_over_is_declined_rather_than_faded(), test_a_surge_requirement_reaches_a_price(), test_no_bet_before_a_pace_exists(), test_settlement_resolves_this_model_per_pick_not_per_model_id(), test_the_book_move_guard_covers_the_new_market() (+8 more)

### Community 240 - "tests/test_ncaaf_game_identity.py"
Cohesion: 0.12
Nodes (16): _add(), _conn(), _identity_sql(), _run(), test_a_clean_slate_reports_nothing(), test_a_non_fbs_fixture_is_not_reported(), test_a_phantom_opponent_is_detected_too(), test_a_real_doubleheader_is_not_a_duplicate() (+8 more)

### Community 241 - "NBA second game market tests"
Cohesion: 0.10
Nodes (27): _close_frames(), _data(), _f2_games(), _f6a_data(), _f6d_total_data(), _game(), _pe(), _q() (+19 more)

### Community 243 - "Live feed probes and game polling"
Cohesion: 0.02
Nodes (106): live_slate_dates(), get_connection(), use_poller_session(), main(), run(), _ensure_schema(), main(), run() (+98 more)

### Community 244 - "NBA second game projection fixtures"
Cohesion: 0.18
Nodes (22): _box(), _games(), _inj(), _rapm_inputs(), _segment_rows(), _state(), test_a_back_to_back_is_read_from_the_schedule(), test_a_game_gets_no_projection_while_a_previous_date_game_could_still_be_running() (+14 more)

### Community 25 - "NBA game model research harness"
Cohesion: 0.04
Nodes (56): attach_fetch(), blind_by_real_side(), blind_pool(), blind_side(), boot(), cell_report(), cents(), check() (+48 more)

### Community 250 - "NBA boxscore enrichment ingest"
Cohesion: 0.19
Nodes (15): _check_unmapped(), _create(), ensure_tables(), fill_missing_game_logs(), load_schedule(), main(), run(), sdv_file() (+7 more)

### Community 254 - "NFL halftime out-of-sample study"
Cohesion: 0.12
Nodes (22): assert_same_as_earlier(), bh(), boot(), boot_coef(), build(), ci(), coverage(), fmt() (+14 more)

### Community 255 - "UFC results download caching"
Cohesion: 0.14
Nodes (8): _etag_cache_path(), _clean_env(), test_a_mounted_volume_is_preferred_over_tmp(), test_a_volume_path_that_does_not_exist_falls_back(), test_an_explicit_override_wins(), test_no_volume_still_falls_back_to_tmp(), test_the_daily_run_never_takes_the_skip_path(), test_the_path_is_resolved_per_call_not_at_import()

### Community 256 - "Signal publishing and push pipeline steps"
Cohesion: 0.10
Nodes (10): sync_action_thresholds(), step_capture_opening_signals(), step_push_notifications(), step_sync_thresholds(), capture_opening_signals(), notify_feedback_replies(), notify_line_changes(), notify_signal_changes() (+2 more)

### Community 259 - "NBA game total luck pick card"
Cohesion: 0.11
Nodes (15): artifact(), decided_games(), ensure_decisions_table(), ledger_exists(), load_quote_rows(), load_season(), main(), newest_fetch() (+7 more)

### Community 260 - "tests/test_live_game_features.py"
Cohesion: 0.11
Nodes (19): compute_live_target(), half_innings_left(), parse_bases(), state_features(), test_build_live_state_row_merges_pregame_context(), test_build_live_state_row_unusable_state(), test_half_innings_left_bottom_ninth(), test_half_innings_left_extras_clamps_to_one() (+11 more)

### Community 262 - "UFC fight feature builder"
Cohesion: 0.06
Nodes (38): _age_years(), _assemble_ufc_features(), _blk_career_stats(), build_ufc_features_from_bulk(), build_ufc_game_features(), _bulk_fighter_id(), career_stats(), compute_ufc_target() (+30 more)

### Community 263 - "Node-run mobile source tests"
Cohesion: 0.02
Nodes (73): node_exe(), node_strips_types(), test_a_published_void_keeps_track_and_betslip(), test_a_tracked_void_reads_not_graded_and_detail_closes_when_over(), test_an_opening_signal_is_live_only_when_discord_published_it(), test_opening_lock_join_is_not_wired_into_readers_yet(), test_the_app_predicate_matches(), test_the_discord_pins_are_on_the_pr_ci_subset() (+65 more)

### Community 266 - "NBA quarter game model tests"
Cohesion: 0.11
Nodes (29): _data(), _game(), _ladder(), _no_real_load(), _point(), _pricing_world(), _q(), _row() (+21 more)

### Community 267 - "NBA second game luck studies"
Cohesion: 0.06
Nodes (35): as_of_ratings(), _before(), box_mismatches(), decide(), f4_projections(), f4_signal(), _known_team(), missing_inputs() (+27 more)

### Community 272 - "Mobile player stat group tests"
Cohesion: 0.15
Nodes (10): _set_literal(), _src(), test_a_group_is_filled_only_by_a_real_number(), test_a_tab_opens_on_the_stat_the_player_fills_most(), test_defensive_positions_get_only_the_defense_group(), test_every_logged_position_is_classified(), test_non_defensive_positions_get_no_defense_group(), test_offensive_positions_are_not_defensive() (+2 more)

### Community 275 - "NBA game harness tests"
Cohesion: 0.09
Nodes (23): _cov_data(), _fetches(), _games(), _offers(), _q(), _stale_cache(), test_a_cell_reports_its_pooled_walk_forward_and_writes_its_bets(), test_a_graded_load_refuses_a_season_the_cache_does_not_price() (+15 more)

### Community 276 - "UFC fight results scraper"
Cohesion: 0.11
Nodes (15): backfill_ufc_stats(), _build_ufc_game_id(), _fetch_event(), _fetch_event_list(), _fetch_fight(), _fetch_fighter(), _get(), _home_win_for_row() (+7 more)

### Community 280 - "Push notification delivery tickets"
Cohesion: 0.16
Nodes (12): _msgs(), test_a_credentials_failure_disables_nobody(), test_a_request_level_rejection_accepts_nothing(), test_a_retired_device_is_named_for_disabling(), test_a_single_message_reply_may_be_a_bare_object(), test_a_ticket_that_is_not_an_object_is_not_a_delivery(), test_an_error_ticket_is_not_counted_as_sent(), test_an_unpairable_reply_counts_nothing_and_disables_nothing() (+4 more)

### Community 284 - "NCAAF opener rule board tests"
Cohesion: 0.17
Nodes (12): _opener_rule(), _line(), _patch(), test_a_fired_pick_clears_its_own_probability_floor(), test_books_agreeing_is_a_no_signal_row(), test_dk_off_its_opener_is_a_no_signal_row(), test_missing_sharp_opener_is_a_no_signal_row(), test_no_current_dk_line_writes_nothing() (+4 more)

### Community 286 - "Kalshi prop ladder recording"
Cohesion: 0.07
Nodes (8): test_a_kalshi_outage_cannot_break_the_pass(), test_a_run_is_idempotent_within_its_snapshot(), test_one_snapshot_timestamp_for_the_whole_run(), test_the_recorder_is_scheduled_on_the_pipeline_role(), test_the_recorder_keeps_raw_prices_not_a_filtered_ladder(), test_the_recorder_walks_every_mapped_series(), _loose_summary(), s()

### Community 287 - "Model calibration check tests"
Cohesion: 0.11
Nodes (11): _calibration_sql(), test_a_flagged_model_is_named_eligible_or_not(), test_a_thin_model_is_still_excluded_rather_than_accused(), test_eligibility_notes_must_not_sink_the_gap_check(), test_it_grades_the_calibrated_probability_not_the_raw_one(), test_it_joins_picks_to_reach_the_calibrated_column(), test_the_check_has_a_skip_budget_that_survives_a_regime_change(), test_the_probability_floor_applies_to_the_decision_number_too() (+3 more)

### Community 29 - "NCAAF college data ingestor"
Cohesion: 0.06
Nodes (35): backfill_ncaaf_lines(), backfill_ncaaf_players(), backfill_ncaaf_qb(), _date_or_none(), _existing_ncaaf_ids(), _fold(), _get(), ingest_ncaaf_game_log() (+27 more)

### Community 291 - "Team stats as-of invariants tests"
Cohesion: 0.09
Nodes (19): build_rows(), seasons_with_too_few_snapshots(), _game(), test_a_real_series_passes(), test_a_row_never_includes_its_own_date(), test_a_single_snapshot_season_is_flagged(), test_a_two_snapshot_season_is_flagged(), test_counts_accumulate_across_dates() (+11 more)

### Community 293 - "Historical odds backfill and API rollup tests"
Cohesion: 0.02
Nodes (65): _ledger_entry_is_resumable(), relabel_in_play(), run_historical_odds_range(), test_a_fold_can_never_lower_a_stored_total(), test_a_new_process_does_not_prune_on_its_first_flush(), test_prune_rolls_up_before_it_deletes(), test_the_daily_table_is_created_and_locked_down(), test_the_daily_table_keys_on_day_api_and_source() (+57 more)

### Community 294 - "NCAAF player stats parser tests"
Cohesion: 0.18
Nodes (17): parse_player_game_stats(), _cat(), _parse(), _payload(), _team(), test_a_game_missing_from_the_id_map_is_skipped_not_guessed(), test_a_player_gets_one_row_across_every_category(), test_a_player_with_nothing_we_track_is_skipped() (+9 more)

### Community 295 - "Discord and X results posting"
Cohesion: 0.02
Nodes (65): _apply_one(), _is_transient_lock_error(), _with_lock_timeout(), _recap_row(), test_a_day_with_no_in_play_picks_says_nothing_about_it(), test_a_loss_costs_the_full_stake_and_a_push_costs_nothing(), test_a_pick_with_no_price_stays_in_the_units_at_bare_conviction(), test_a_six_column_row_still_tallies() (+57 more)

### Community 297 - "scripts/nfl_live_prop_feasibility.py"
Cohesion: 0.23
Nodes (17): american_b(), bettable(), boot_roi(), brier(), design(), fit_market(), grade(), implied() (+9 more)

### Community 299 - "tests/test_context_budget.py"
Cohesion: 0.12
Nodes (14): _expand_braces(), _hook_context(), _read(), _rule_files(), _size(), test_claude_md_stays_small_enough_to_load_every_session(), test_every_doc_referenced_by_the_index_exists(), test_every_rules_file_is_pointed_at_from_claude_md() (+6 more)

### Community 303 - "tests/test_player_h2h_stat_values_migration.py"
Cohesion: 0.10
Nodes (13): _body(), test_each_function_reads_its_own_log_table(), test_it_does_its_ddl_once_and_guards_on_the_property_it_establishes(), test_it_is_one_statement_so_conn_execute_cannot_shred_it(), test_public_is_revoked_before_anon_is_granted(), test_security_invoker_like_the_season_rpcs_it_mirrors(), test_the_fixture_is_two_parallel_arrays_not_a_separator(), test_the_players_latest_team_decides_his_fixture() (+5 more)

### Community 305 - "tests/test_retired_models.py"
Cohesion: 0.06
Nodes (13): test_a_retired_game_model_is_in_no_feature_map(), test_a_retired_model_is_in_no_registry_and_no_threshold_dict(), test_a_retired_prop_has_no_feature_map_and_no_training_label(), test_a_retired_sport_is_not_still_health_checked(), test_paused_nfl_props_still_in_prop_models_and_thresholds(), test_retired_prop_picks_still_settle_on_their_own_stat(), test_ten_nfl_distributional_props_are_paused(), test_the_app_mirrors_the_same_set() (+5 more)

### Community 306 - "Prop box score gap filling"
Cohesion: 0.12
Nodes (24): fill_missing(), _call_fill(), _cooled(), _day(), _default_mlb(), _default_nba(), _default_nfl(), _default_nhl() (+16 more)

### Community 309 - "Signal delivery window health tests"
Cohesion: 0.11
Nodes (10): test_a_game_date_inside_the_window_counts(), test_a_lookahead_commence_counts_even_when_game_date_is_outside(), test_a_signal_locked_after_first_pitch_was_never_deliverable(), test_a_signal_locked_before_first_pitch_still_counts(), test_a_signal_locked_exactly_at_first_pitch_counts(), test_a_started_game_outside_the_window_does_not_count(), test_it_fails_toward_noticing(), test_mixed_timestamp_shapes_are_parsed_not_string_compared() (+2 more)

### Community 316 - "Mobile sport filter chips"
Cohesion: 0.14
Nodes (10): _load_body(), _sports(), _src(), test_a_visit_scoped_sport_change_does_not_persist(), test_a_writer_landing_during_the_hydrate_is_not_overwritten(), test_every_sport_survives_a_cold_start(), test_no_retired_sport_is_a_selectable_chip(), test_no_second_hand_written_sport_list_in_the_hook() (+2 more)

### Community 317 - "Scratch Postgres migration test harness"
Cohesion: 0.06
Nodes (35): main(), can_scratch(), env_dsn(), _free_port(), pg_bin(), scratch_cluster(), as_app(), db() (+27 more)

### Community 318 - "tests/test_live_record_start_views.py"
Cohesion: 0.09
Nodes (12): _body(), _code(), test_both_published_views_carry_the_live_date_gate(), test_it_runs_after_the_migration_that_used_to_own_the_daily_view(), test_migration_is_one_statement(), test_migration_is_registered_with_the_worker_runner(), test_neither_view_reads_the_sweep_universe(), test_no_ddl_outside_the_guarded_branches() (+4 more)

### Community 319 - "UFC historical CSV loader"
Cohesion: 0.11
Nodes (20): backfill_ufc_csv(), build_events(), build_fighter_index(), ingest_ufc_results_for_date_csv(), _kd_int(), load_fighter_profiles_from_csv(), _mirror_etag(), _read_csv() (+12 more)

### Community 327 - "NHL prop odds fetch gate"
Cohesion: 0.07
Nodes (22): due(), _book(), test_a_200_on_both_calls_merges_the_alternate_lines(), fake_fetch(), test_a_game_first_priced_inside_the_final_window_gets_nothing_more(), test_a_game_first_priced_inside_the_window_gets_one_decision_snapshot(), test_a_game_with_nothing_stored_is_owed_its_open(), test_a_moved_featured_line_keeps_the_old_number_under_the_alternate_key() (+14 more)

### Community 328 - "NFL Kalshi edge search"
Cohesion: 0.17
Nodes (20): align_check(), bh(), bins(), boot(), cell(), coverage(), cp_roi(), fee() (+12 more)

### Community 329 - "nfl/models/opener_spread.py"
Cohesion: 0.13
Nodes (12): bettable_books(), age_tag(), american_to_prob(), _bettable_books(), clean_board(), edge_tier(), evaluate_board(), held_minutes() (+4 more)

### Community 332 - "Mobile bankroll settings card"
Cohesion: 0.18
Nodes (20): fieldFlow(), inv(), bankrollDraft(), bankrollFieldText(), canonical(), checkBankroll(), commitBankrollText(), editBankrollInput() (+12 more)

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

### Community 34 - "Kalshi prop ladders and game markets"
Cohesion: 0.10
Nodes (18): from_one_sided_overs(), _ladder(), test_a_clean_ladder_is_not_reported_as_repaired(), test_a_one_sided_ladder_is_vigged_and_says_so(), test_a_quoted_strike_returns_its_own_mid(), test_a_thin_one_sided_ladder_cannot_be_anchored(), test_an_unquoted_line_interpolates_between_its_neighbours(), test_anchoring_moves_the_ladder_onto_an_honest_point() (+10 more)

### Community 343 - "NCAAF weather totals walk-forward fit"
Cohesion: 0.17
Nodes (11): _fit(), fit_and_register_totals(), _matrix(), sweep_total(), walk_forward_totals(), arm_frame(), load_issued(), main() (+3 more)

### Community 346 - "NFL research edge data cache"
Cohesion: 0.22
Nodes (14): _conn(), copy_main_local(), _df(), _games_2026(), log(), main(), nflverse_misc(), nflverse_pbp() (+6 more)

### Community 347 - "NFL weather cache import into database"
Cohesion: 0.15
Nodes (10): main(), rows_from_file(), source_for(), stadium_from_name(), _INSERT_PLACEHOLDERS(), test_a_non_issued_or_empty_payload_yields_nothing(), test_every_hour_becomes_one_row_in_column_order(), test_stored_files_reads_the_marker_back() (+2 more)

### Community 35 - "NBA second game projection tests"
Cohesion: 0.07
Nodes (16): _cons(), _dist(), _neutral(), _segments(), test_f1_is_priced_through_the_projections_own_error_not_the_markets(), test_f1b_does_not_score_a_books_number_off_the_consensus(), test_f1b_strength_is_the_predicted_move_in_the_sides_favour(), test_the_consensus_number_is_pinnacles_else_the_deciding_books_median() (+8 more)

### Community 351 - "Live game state poller triggers"
Cohesion: 0.12
Nodes (23): _bases_state(), _detect_triggers(), _extract_state(), _is_active_or_starting_soon(), test_active_in_progress_game_is_active(), test_bases_state_empty(), test_bases_state_loaded(), test_bases_state_single_runner() (+15 more)

### Community 352 - "Team stats history rebuild and verify"
Cohesion: 0.15
Nodes (10): already_a_series(), _games(), live_season_snapshot_grace(), main(), _prior_season_rates(), rebuild_sport(), _team_games(), verify() (+2 more)

### Community 353 - "College football rating matrix and QB priors"
Cohesion: 0.15
Nodes (11): build_prior_season_ratings(), load_fbs_membership(), load_team_games(), pool_fcs_opponents(), _asof_merge(), build_matrix(), _haversine(), _load_asof_stats() (+3 more)

### Community 354 - "Custom model game facts builder"
Cohesion: 0.06
Nodes (44): assemble_game(), grade_ats(), grade_ml(), grade_total(), is_primetime(), lead_hours(), line_at_start(), _num() (+36 more)

### Community 358 - "NBA period map pricing tests"
Cohesion: 0.06
Nodes (32): _game(), _games3(), _gaps(), _ladder_quotes(), _luck_games(), _maps(), _odds_row(), _offered() (+24 more)

### Community 36 - "NCAAF CFBD ingestor tests"
Cohesion: 0.03
Nodes (54): build_ncaaf_game_id(), _day_before(), eastern_game_date(), _local_aggregates(), ncaaf_slug(), parse_lines(), parse_teams(), shrink_to_prior() (+46 more)

### Community 360 - "Mobile screen source wiring tests"
Cohesion: 0.07
Nodes (20): _bn_body(), _sql_groups(), test_a_failed_position_read_is_said_not_hidden(), test_a_failed_read_is_not_held_on_the_spinner(), test_every_mlb_stat_chip_has_a_branch(), test_every_nfl_stat_chip_has_a_branch(), test_every_roster_sport_chip_has_a_branch(), test_mlb_lineup_buckets_agree_between_app_and_server() (+12 more)

### Community 366 - "Kalshi game market recorder"
Cohesion: 0.09
Nodes (8): run_kalshi_game_record(), test_a_kalshi_outage_cannot_break_the_pass(), test_event_code_is_shared_across_series(), test_event_date_is_searched_not_anchored(), test_kalshi_labels_expand_st_and_use_the_explicit_map(), test_resolution_runs_after_every_snapshot(), test_the_recorder_is_scheduled_on_the_pipeline_role(), test_the_recorder_keeps_raw_contracts()

### Community 367 - "Database URL doctor tests"
Cohesion: 0.14
Nodes (18): _classes(), diagnose(), bad(), _safe(), _fails(), _levels(), test_a_correct_url_reports_no_failures(), test_bare_postgres_on_a_DIRECT_host_is_fine() (+10 more)

### Community 371 - "NCAAF totals probability regression tests"
Cohesion: 0.10
Nodes (14): total_over_prob(), test_artifact_kind_is_routed_by_the_scorer(), test_asymmetry_is_real_and_would_have_bitten(), test_extremes_are_clamped_away_from_certainty(), test_model_above_the_line_favours_the_over(), test_model_below_the_line_favours_the_under(), test_no_dk_total_means_skip_not_prob_only(), test_no_residuals_returns_one_half_not_a_confident_bet() (+6 more)

### Community 373 - "NFL stale wind card cleanup"
Cohesion: 0.15
Nodes (9): card_path(), clear_card(), _load_script(), nfl_path(), test_a_dry_run_leaves_the_card_alone(), test_a_priced_wind_run_with_no_bets_removes_the_earlier_card(), test_clear_card_removes_todays_file_and_only_that(), test_the_path_cleared_is_the_path_the_publisher_reads() (+1 more)

### Community 375 - "Refresh pass step ordering tests"
Cohesion: 0.10
Nodes (13): _order(), test_a_parallel_step_that_fails_is_still_recorded(), test_no_sequential_step_runs_while_a_parallel_group_is_open(), test_opening_signals_follows_every_scorer(), test_parlay_follows_opening_signals(), test_scoring_follows_every_ingest(), test_settle_follows_every_results_ingest(), test_sync_thresholds_follows_migrations_and_precedes_scoring() (+5 more)

### Community 379 - "Team hashtags for X posts"
Cohesion: 0.17
Nodes (11): test_college_nicknames_and_a_shared_mascot_falls_back_to_the_school(), test_team_hashtags_use_the_nickname(), _both_teams(), _from_full_names(), hashtag_token(), _index(), _mlb(), _nickname() (+3 more)

### Community 382 - "NFL in-play pick writer"
Cohesion: 0.12
Nodes (8): _is_market_opinion(), _lane_is_locked(), _norm_player(), resolve_game(), resolve_game_id(), test_normalised_player_key_is_the_join_the_prop_system_uses(), test_the_lane_lock_shares_the_scorers_meaning_of_locked(), test_the_lock_is_scoped_by_player_not_just_by_game()

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

### Community 396 - "MLB public fade top-k holdout study"
Cohesion: 0.15
Nodes (14): bucket_win_rates(), build_candidates(), _fmt(), holdout_take(), load_db(), load_json(), lomo_rates(), main() (+6 more)

### Community 398 - "Mobile team detail page tests"
Cohesion: 0.11
Nodes (15): _read(), test_every_team_page_read_names_its_relation_literally(), test_next_game_is_earliest_in_the_window_not_tonights_date(), test_no_paper_trading_copy(), test_public_betting_policy_migration_exists_and_is_select_only(), test_recent_games_are_scoped_by_sport(), test_results_are_units_never_dollars(), test_sharp_gap_is_no_vig_vs_no_vig() (+7 more)

### Community 399 - "NFL live leader model tests"
Cohesion: 0.12
Nodes (14): art(), _d(), _raw(), test_600_seconds_and_both_lead_ends_are_inside(), test_a_flipped_spread_sign_changes_the_decision(), test_a_qualifying_state_bets_the_leader_at_its_price(), test_artifact_identity_training_and_rule(), test_band_matches_training_leader_view_on_nflverse_sign() (+6 more)

### Community 4 - "NFL prop settlement name matching"
Cohesion: 0.27
Nodes (10): _never(), _row(), test_a_first_name_the_stat_log_spells_differently_still_matches(), test_a_scratched_player_is_not_graded_on_a_teammate_with_his_initial(), test_a_spelling_the_log_already_knows_is_a_scratch_not_a_spelling(), test_another_game_and_another_initial_never_match(), test_first_name_rule(), test_two_candidates_is_a_miss_not_a_guess() (+2 more)

### Community 40 - "NFL wind and teaser edge research"
Cohesion: 0.04
Nodes (89): am_to_dec(), at_lead(), boot_ci(), devig2(), ev(), odds_2026(), odds_hist(), pbp() (+81 more)

### Community 400 - "Mobile paused catalog tests"
Cohesion: 0.16
Nodes (11): _block(), _read(), test_paused_picks_reach_the_all_board_only_and_labelled(), test_stats_add_pick_refuses_a_paused_model(), test_the_behavioural_checks_pass(), test_the_bet_type_picker_filters_paused_models(), test_the_custom_model_picker_is_three_bet_types(), test_the_models_list_filters_paused_models() (+3 more)

### Community 401 - "X posting and brand avatar"
Cohesion: 0.03
Nodes (56): main(), scram_stored_key(), discover(), fetch_all(), _get_image(), main(), _original_size(), store() (+48 more)

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

### Community 409 - "NFL opener cut sweep and calibration"
Cohesion: 0.16
Nodes (8): _load_backtest(), main(), selected_bets(), boot_ci(), candidate_rows(), _load_backtest(), main(), select()

### Community 411 - "Mobile bankroll field tests"
Cohesion: 0.19
Nodes (14): _read(), test_copy_is_word_for_word(), test_display_only_nothing_sized(), test_error_text_uses_the_text_safe_red(), test_explainer_no_longer_denies_a_bankroll(), test_exposure_card_hook_and_banner_stay_removed(), test_keyboard_never_covers_the_field(), test_locale_separators_decide_the_decimal() (+6 more)

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
Cohesion: 0.16
Nodes (8): test_capture_clv_requires_the_game_to_have_started(), test_future_kickoffs_are_not_treated_as_started(), test_game_log_skips_per_game_not_per_date(), test_started_games_are_recognised_in_every_stored_format(), test_ufc_poll_uses_the_etag_gate_and_the_daily_run_does_not(), test_unparseable_timestamps_yield_none_rather_than_a_guess(), test_z_and_offset_forms_are_the_same_instant_but_not_the_same_string(), _as_utc()

### Community 416 - "NBA schedule rest and travel features"
Cohesion: 0.12
Nodes (10): _counted_schedule(), from_cache(), game_schedule_features(), haversine_miles(), home_bases(), _offsets(), previous_game_load(), team_schedule_features() (+2 more)

### Community 418 - "CLV card at the price taken"
Cohesion: 0.13
Nodes (18): _app(), _clv_card(), _node_strips_types(), _server(), test_a_label_book_nfl_pick_compares_its_line_with_that_book(), test_a_recorded_book_differs_from_the_derived_one(), test_the_app_prefers_the_recorded_book_at_the_derived_price(), test_the_app_prices_every_row_as_the_server_grades_it() (+10 more)

### Community 419 - "ESPN injury fetch and NFL ingest"
Cohesion: 0.04
Nodes (30): _athlete_name(), _espn_team_ids(), fetch_espn_injuries(), _fetch_espn_team_injuries(), _fetch_nba_espn_team_ids(), _fetch_nfl_espn_team_ids_core(), _fetch_wnba_espn_team_ids(), _nba_espn_team_to_abbrev() (+22 more)

### Community 42 - "DataGolf ingestor and NHL SBR archive"
Cohesion: 0.05
Nodes (46): _american(), backfill_golf_rounds(), build_game_id(), _dg_get(), _earliest_commence_iso(), _event_meta_lookup(), event_slug(), ingest_golf_field() (+38 more)

### Community 422 - "Mobile pick category tests"
Cohesion: 0.11
Nodes (13): _block(), _config_scorable_ids(), _meta_ids(), _meta_types(), _read(), test_every_model_id_derives_its_own_declared_category(), test_every_scorable_model_has_a_label_in_the_app(), test_picks_idle_chrome_is_search_and_filters_only() (+5 more)

### Community 423 - "Picks unique row index tests"
Cohesion: 0.11
Nodes (10): conn(), _prop(), test_dedupe_and_health_use_the_shared_tuple(), test_player_id_uniqueness_is_unchanged(), test_the_card_insert_tolerates_the_unique_index(), test_the_narrow_index_collides_null_player_id_props(), test_the_same_proposition_still_collides_on_the_widened_index(), test_the_widen_migration_is_property_guarded() (+2 more)

### Community 425 - "NFL odds cache import to Supabase"
Cohesion: 0.12
Nodes (9): _allowed(), _data_dirs(), test_a_rerun_after_the_resolver_improves_adds_only_the_gap(), test_every_buying_ingestor_keys_its_resume_on_a_source_marker(), test_no_undeclared_data_store_on_disk(), test_the_importer_resolves_a_postponed_game(), test_the_importer_still_refuses_an_event_with_no_game(), test_the_nfl_odds_cache_has_an_importer() (+1 more)

### Community 426 - "tests/test_health_check_observe.py"
Cohesion: 0.14
Nodes (10): _crit(), fake(), test_a_crit_does_not_fail_the_observe_path(), test_a_crit_still_fails_the_daily_step(), test_an_exception_does_not_fail_the_observe_path(), test_daily_syncs_thresholds_after_view_migrations(), test_it_still_runs_the_check_when_observing(), test_ok_is_identity_in_both_modes() (+2 more)

### Community 427 - "NFL in-play prop flow validation"
Cohesion: 0.02
Nodes (121): _connect(), bias_table(), main(), apply_anchor(), best_hit(), _boot_ci(), drop_degenerate(), evaluate() (+113 more)

### Community 428 - "NFL 2026 opener and wind tracker"
Cohesion: 0.12
Nodes (20): classify(), fetch(), grade_rows(), is_void(), lead_days(), _load_nfl_model(), main(), opener_verdict() (+12 more)

### Community 429 - "Published record views reconciliation"
Cohesion: 0.16
Nodes (8): test_a_pick_before_the_live_date_is_caught_in_either_view(), test_a_sport_missing_from_the_daily_view_is_caught(), test_an_empty_record_is_not_a_problem(), test_cent_level_agreement_is_required(), test_same_picks_but_different_money_is_caught(), test_the_fixed_production_numbers_reconcile(), test_the_real_production_drift_is_caught(), _published_record_problems()

### Community 431 - "tests/test_pick_lock_is_on_picks.py"
Cohesion: 0.16
Nodes (9): _between(), _sql(), test_a_bet_is_still_never_re_scored(), test_only_a_bet_locks_a_pair(), test_the_cleanup_covers_the_whole_look_ahead_window(), test_the_cleanup_never_touches_a_started_game_or_a_live_row(), test_the_lock_is_no_longer_ncaaf_specific(), test_the_prop_and_live_locks_are_unchanged() (+1 more)

### Community 434 - "MLB prop feature engine"
Cohesion: 0.05
Nodes (35): _all_batter_rows(), _all_pitcher_rows(), _batter_rate(), _batter_rolling_avg(), _batter_savant(), _batter_season_avg(), _build_batter_row(), build_batter_scoring_rows() (+27 more)

### Community 437 - "Per-model threshold config tests"
Cohesion: 0.08
Nodes (8): test_an_own_floor_does_not_take_a_model_off_the_calibration_map(), test_every_model_carries_its_own_thresholds(), test_every_own_floor_names_a_live_model(), test_models_on_own_probability_is_not_derived_from_the_floor_dict(), test_no_own_floor_tightens_a_model_past_the_global_floor(), test_only_a_market_priced_model_carries_a_negative_floor(), test_own_ev_floor_and_model_min_ev_stay_disjoint(), test_the_nba_home_team_total_floor_does_not_move_with_the_platform_default()

### Community 438 - "NBA game two verdict grid tests"
Cohesion: 0.21
Nodes (20): _cell(), _grid(), _hgrid(), _house(), _mid(), test_a_cell_below_the_bet_count_enters_the_correction_at_p_one(), test_a_cell_clearing_every_bar_passes(), test_a_cell_with_no_dominant_side_is_not_held_to_a_blind_bet() (+12 more)

### Community 439 - "Script entrypoint structure checks"
Cohesion: 0.15
Nodes (7): _is_main_guard(), _modules_with_guard(), test_at_least_one_entrypoint_is_scanned(), test_nothing_is_defined_after_the_main_guard(), test_the_report_script_exists_and_parses(), test_the_backfill_queues_the_dates_of_those_picks(), test_every_prop_model_maps_to_a_dk_market()

### Community 442 - "NCAAF in-play odds history pull"
Cohesion: 0.24
Nodes (13): _blank_row(), _floor5(), _get(), _iso(), main(), planned_calls(), pull_day(), resolve_game_id() (+5 more)

### Community 443 - "MLB retrain freeze guard"
Cohesion: 0.13
Nodes (9): assert_retrain_allowed(), test_import_time_flag_follows_marker_file(), test_marker_or_env_lifts_the_freeze(), test_mlb_prop_market_sweep_is_documented_exempt(), test_mlb_retrain_refused_while_incomplete(), test_mlb_threshold_sweeps_call_the_guard(), test_non_mlb_sports_are_not_gated(), test_repo_marker_file_is_present() (+1 more)

### Community 445 - "NCAAF board visibility scorer tests"
Cohesion: 0.10
Nodes (10): _days_until(), test_a_declined_rule_can_never_leak_a_signal(), test_a_no_signal_row_does_not_lock_an_ncaaf_game_for_the_week(), test_days_until_is_none_without_a_kickoff_time(), test_days_until_is_positive_for_a_future_kickoff(), test_every_registered_model_has_a_feature_map_entry(), test_the_premium_tier_shares_the_spread_features(), test_the_price_prefilter_can_only_ever_skip_ncaaf() (+2 more)

### Community 447 - "supabase/functions/discord-link/index.ts"
Cohesion: 0.24
Nodes (15): accessFor(), handleComplete(), handleStart(), handleStatus(), handleUnlink(), hmac(), issueState(), json() (+7 more)

### Community 449 - "tests/test_nfl_prop_clv.py"
Cohesion: 0.16
Nodes (9): _assign(), _book_from_label_fn(), _fn(), test_the_book_is_read_from_the_label_suffix(), test_the_closing_prop_lookup_defaults_to_draftkings_and_binds_the_book(), test_the_label_book_map_is_the_inverse_of_both_cards(), test_the_map_test_no_longer_excludes_nfl(), test_the_market_relative_rules_take_their_market_from_the_row() (+1 more)

### Community 452 - "tests/test_scoring_methods.py"
Cohesion: 0.13
Nodes (7): _generic(), test_a_generic_model_is_never_declared_rule_or_engine(), test_accessor_defaults_to_artifact(), test_every_classified_model_carries_thresholds(), test_mlb_live_total_runs_is_artifact_backed(), test_rule_based_models_never_appear_in_a_feature_map(), test_the_map_covers_exactly_the_non_generic_models()

### Community 457 - "NBA game model phase one checks"
Cohesion: 0.11
Nodes (19): cell_specs(), check_cell_count(), derivative_data(), derivative_plan(), derivative_plumbing(), derivative_seasons(), derivative_times(), early_games() (+11 more)

### Community 458 - "UFC fighter name slugs and aliases"
Cohesion: 0.14
Nodes (11): normalize_method(), slugify_fighter(), test_alias_makes_both_sources_agree(), test_aliases_do_not_touch_unmapped_names(), test_confirmed_aliases_resolve_to_ufcstats_slug(), test_normalize_method(), test_resolve_anchor_matches_every_real_name_variant(), test_resolve_anchor_refuses_every_real_stale_booking_on_its_own() (+3 more)

### Community 46 - "Worker job queue runner"
Cohesion: 0.02
Nodes (38): derive_first_pitch(), test_the_worker_job_is_registered_and_defaults_to_dry_run(), test_the_discord_publish_job_calls_the_ordinary_producer(), test_the_discord_publish_job_takes_an_optional_date(), test_the_raised_timeout_is_restored_after_the_job(), test_the_restore_puts_back_a_pre_existing_value(), test_marker_file_is_in_tree_so_the_freeze_would_not_block_the_worker(), test_missing_artifact_path_refuses_to_sweep_live() (+30 more)

### Community 460 - "Discord and X period recaps"
Cohesion: 0.09
Nodes (16): _at(), test_a_later_weekday_still_retries_that_week(), test_a_week_that_crosses_months_names_both(), test_discord_period_uses_the_results_webhook_and_ledgers_once(), test_monday_at_730_opens_the_prior_mon_sun_week(), test_monday_before_730_has_not_opened_the_new_week(), test_sunday_does_not_open_the_week_that_is_still_in_progress(), test_the_first_monday_opens_the_previous_calendar_month() (+8 more)

### Community 462 - "Anonymous read and grant sweep tests"
Cohesion: 0.07
Nodes (13): test_a_writable_relation_that_is_not_readable_is_still_swept(), test_every_declared_write_verb_has_a_call_site_that_needs_it(), test_public_is_stripped_from_every_declared_callable_before_it_is_granted(), test_subscriptions_stays_authenticated_only(), test_the_apply_script_reads_back_that_rls_actually_landed(), test_the_apply_script_revokes_writes_and_reads_the_result_back(), test_the_archive_tables_have_no_create_site_and_the_worker_only_ones_do(), test_the_default_privilege_revoke_names_the_api_roles_only() (+5 more)

### Community 464 - "NCAAF in-play odds polling cadence"
Cohesion: 0.08
Nodes (13): _feed_with_payload(), gameday_mod(), test_a_sustained_feed_outage_degrades_to_no_odds(), test_cached_odds_are_served_while_fresh(), test_credit_cap_covers_a_full_saturday_at_the_configured_cadence(), test_credit_cap_reports_no_odds_rather_than_a_frozen_line(), test_credit_cap_still_serves_a_payload_that_is_still_fresh(), test_idle_cadence_is_slower_than_the_live_cadence() (+5 more)

### Community 465 - "nfl/scripts/backtest_opener.py"
Cohesion: 0.24
Nodes (9): boot(), by_season(), exp_win(), load(), main(), price(), report(), residuals() (+1 more)

### Community 467 - "NCAAF totals lead and consensus gate"
Cohesion: 0.26
Nodes (10): build_lead_table(), first_cross(), fmt(), grade(), line_as_of(), load_backfill(), main(), match_frame_to_odds() (+2 more)

### Community 468 - "tests/test_latest_odds_views.py"
Cohesion: 0.25
Nodes (13): _app_columns(), _function(), test_every_log_table_has_its_insert_trigger_and_the_odds_tables_an_update_trigger(), test_every_view_reads_its_state_table_and_never_the_log(), test_no_pending_view_migration_re_creates_these_views_over_the_log(), test_the_dk_view_returns_the_apps_columns_in_order(), test_the_exclusions_survived_the_move(), test_the_game_view_returns_the_apps_columns_in_order() (+5 more)

### Community 472 - "NBA schedule ingestor"
Cohesion: 0.20
Nodes (11): ot_periods(), schedule_rows(), season_str(), _tv(), _row(), test_a_late_west_coast_tip_keeps_its_eastern_date(), test_an_undecided_playoff_slot_is_skipped(), test_game_type_is_read_from_the_first_three_digits() (+3 more)

### Community 476 - "tests/test_transaction_pooler.py"
Cohesion: 0.19
Nodes (8): _transaction_endpoint(), test_a_direct_connection_is_left_alone(), test_a_local_postgres_is_left_alone(), test_a_supabase_session_url_becomes_the_transaction_url(), test_it_is_idempotent(), test_only_the_port_changes(), test_the_escape_hatch_works(), test_the_job_queue_still_gets_session_mode()

### Community 477 - "NBA injury report pull and storage"
Cohesion: 0.17
Nodes (9): content_hash(), garbled_note(), previous_report(), pull_one(), slot_time(), tips_by_date(), write_report(), test_a_report_whose_cells_do_not_line_up_with_its_header_is_not_stored() (+1 more)

### Community 478 - "MLB totals retrain sweep job tests"
Cohesion: 0.10
Nodes (10): _side_rows(), test_marker_file_is_in_tree_so_the_freeze_would_not_block_the_worker(), test_missing_artifact_path_refuses_to_sweep_live(), test_over_covers_when_combined_score_beats_the_total_line(), test_price_below_the_house_floor_is_not_a_gradable_side(), test_push_on_the_total_emits_no_sides(), test_retrain_then_sweep_passes_the_new_path(), test_the_runner_retrains_then_sweeps_the_new_artifact() (+2 more)

### Community 480 - "Position defense ranks matchup"
Cohesion: 0.21
Nodes (10): _read(), _sql(), test_it_is_one_statement_and_each_piece_is_guarded(), test_the_app_calls_the_function_by_its_literal_name(), test_the_blend_cut_matches_the_app(), test_the_matchup_checks_pass(), test_the_matchup_header_fills_its_column_and_large_text_is_one_line(), test_the_role_and_stat_cuts_match_the_player_card() (+2 more)

### Community 483 - "Trainer no-register mode tests"
Cohesion: 0.12
Nodes (9): not_registering(), registering(), test_a_normal_run_DOES_register(), test_baseline_artifacts_are_not_committable(), test_baseline_runs_write_somewhere_else(), test_default_is_to_register(), test_no_register_opens_no_database_connection(), _explode() (+1 more)

### Community 484 - "NBA inactives, officials and advanced box"
Cohesion: 0.17
Nodes (11): fetch_advanced(), _game(), _gid(), inactive_rows(), neutral_fill_rows(), official_rows(), _season_str(), test_inactive_rows_carry_team_and_leave_reason_null() (+3 more)

### Community 485 - "NCAAF in-play game state building"
Cohesion: 0.18
Nodes (10): main(), _classify(), classify_report(), load_pbp(), load_platform_games(), pace_report(), _repair_day_offsets(), sample_states() (+2 more)

### Community 486 - "Env file database URL fallback"
Cohesion: 0.16
Nodes (11): database_url(), _default_env_path(), env_value(), parse_env_file(), test_a_missing_env_file_is_empty_not_an_error(), test_a_value_containing_equals_survives(), test_env_file_is_read_when_the_environment_is_empty(), test_env_value_reads_other_keys_too() (+3 more)

### Community 487 - "supabase/functions/sharpsports/index.ts"
Cohesion: 0.30
Nodes (13): americanFromBetSlip(), asArray(), createContext(), isSettled(), json(), pick(), pullAndUpsert(), readBets() (+5 more)

### Community 491 - "Rule model market reading tests"
Cohesion: 0.15
Nodes (10): _case(), _clv_game_market(), _like(), _prompt_case(), _scorer_case(), test_the_case_reader_reads_the_name_patterns_as_postgres_does(), test_the_claude_mobile_prompt_reads_the_rule_card_s_market(), test_the_closing_line_functions_are_recreated_when_they_change() (+2 more)

### Community 493 - "NCAAF quarterback change features"
Cohesion: 0.19
Nodes (8): load_qb_games(), merge_qb_features(), _games(), _qb_team(), test_either_changed_is_a_game_level_flag_the_diff_would_cancel(), test_every_declared_feature_is_actually_produced(), test_missing_qb_table_yields_nan_columns_not_a_crash(), test_positive_diff_always_means_good_for_home()

### Community 495 - "tests/test_worker_deps.py"
Cohesion: 0.16
Nodes (6): _requirements(), test_dashboard_packages_are_not_on_the_worker(), test_nothing_in_the_repo_actually_wants_a_gpu(), test_only_the_dashboard_imports_them(), test_the_dashboard_file_is_additive_not_a_replacement(), test_the_worker_asks_for_the_cpu_build_of_xgboost()

### Community 50 - "scheduler.py"
Cohesion: 0.04
Nodes (57): _run_migrations(), abort_orphaned_refresh_runs(), build_scheduler(), _add_job(), _with_heartbeat(), _wrapped(), catch_up_daily_pipeline(), catch_up_refresh_pass() (+49 more)

### Community 501 - "Mobile stat segment tabs tests"
Cohesion: 0.20
Nodes (10): _read(), test_one_shared_defensive_set(), test_position_is_never_inferred_from_stats(), test_runs_in_pr_ci(), test_search_and_position_review_fixes(), test_segment_labels_cap_only_on_fit(), test_tabs_speak_the_visible_label_not_the_key(), test_the_behavioural_checks_pass() (+2 more)

### Community 505 - "tests/test_mobile_stat_labels_match_the_server.py"
Cohesion: 0.21
Nodes (6): _meta_entries(), _server_stat_labels(), test_both_rushing_models_call_the_stat_the_same_thing(), test_the_live_model_names_the_market_it_actually_trades(), test_the_parser_actually_found_the_models(), test_the_unreconciled_models_are_named()

### Community 506 - "tests/test_ncaaf_fcs_visitor_names_migration.py"
Cohesion: 0.15
Nodes (5): _rows(), test_each_write_guards_on_its_own_property(), test_every_real_visitor_extends_the_wrong_one(), test_migration_is_one_statement(), test_the_nine_rows_and_their_finals_are_the_measured_ones()

### Community 507 - "tests/test_nfl_prop_unstarted_clear.py"
Cohesion: 0.12
Nodes (14): test_the_join_is_the_discord_ledger_and_not_a_new_bet_row(), test_persist_creates_its_own_table_and_is_idempotent(), _apply(), _assert_split(), _between(), _first_sql(), _per_game_sql(), _sweep_sql() (+6 more)

### Community 508 - "Numeric research labs and staking"
Cohesion: 0.03
Nodes (114): american_to_decimal(), cover_probs(), ev_per_unit(), fit_margin_pmf(), kelly_fraction(), margin_pmf_for(), add_model_mu(), load() (+106 more)

### Community 512 - "tests/test_savant_freshness.py"
Cohesion: 0.20
Nodes (3): test_savant_has_a_schedule(), test_the_savant_job_belongs_to_the_pipeline_service(), test_the_stamp_defaults_rather_than_being_required_at_call_sites()

### Community 513 - "tests/test_scorer_nfl_prop_like_escape.py"
Cohesion: 0.23
Nodes (9): _between(), _broken_per_game_sql(), _first_sql(), _per_game_sql(), _sweep_sql(), test_escape_tripwire_is_on_the_pr_ci_subset(), test_live_per_game_clear_interpolates_with_one_game_id(), test_live_sweep_clear_interpolates_with_date_horizon_now() (+1 more)

### Community 516 - "NHL stats views tests"
Cohesion: 0.15
Nodes (14): _date_filter_runs_before_dedupe(), anywhere(), blob(), filter_wraps_unique(), has_unique(), pred(), pred_inside_unique(), _pg_bin() (+6 more)

### Community 519 - "Paid NFL odds file importer"
Cohesion: 0.24
Nodes (7): game_index(), main(), resolve(), rows_from_file(), stored_pairs(), stored_served(), _ts()

### Community 520 - "Market movement feature builder"
Cohesion: 0.09
Nodes (23): american_to_prob(), build_market_features(), _is_full_game_snap(), _latest_two_sided(), _s(), test_a_game_with_no_decision_book_still_gets_features(), test_a_line_that_genuinely_did_not_move_is_zero_not_none(), test_a_one_way_sharp_quote_yields_nothing() (+15 more)

### Community 522 - "NFL prop per-side edge cut"
Cohesion: 0.26
Nodes (7): find_bets(), _edges(), _quotes(), test_a_side_map_tightens_only_the_side_it_names(), test_the_nfl_binding_passes_the_side_map_through(), test_the_shared_helper_is_unchanged_when_no_side_map_is_given(), test_the_side_map_can_never_loosen_the_base_cut()

### Community 524 - "NCAAF opener and close pull from CFBD"
Cohesion: 0.23
Nodes (7): build_opener_cache(), coverage_report(), fetch_season(), _headers(), main(), _norm(), to_frame()

### Community 525 - "NBA injury report time slots"
Cohesion: 0.15
Nodes (12): _all_slots(), _ampm(), new_slot(), old_slot(), pre_tip_slot(), report_url(), slots_for_date(), test_format_switch_is_measured_and_both_are_probed_around_it() (+4 more)

### Community 527 - "NFL in-play pick writer safety tests"
Cohesion: 0.10
Nodes (9): _executor_min_price(), _probe_config(), test_the_ceiling_is_a_refusal_not_a_filter(), test_the_default_announcer_calls_both_live_notifiers(), test_the_insert_tolerates_the_one_row_per_pick_index(), test_the_lane_can_actually_settle(), test_the_lane_refuses_a_quote_past_the_ceiling(), test_the_retired_model_carries_no_threshold_row() (+1 more)

### Community 529 - "tests/test_clear_unauthorized_auto_pauses_migration.py"
Cohesion: 0.19
Nodes (6): _stmts(), test_clearing_auto_pauses_did_not_park_batter_runs(), test_it_clears_the_whole_auto_pause_table(), test_it_does_not_touch_picks_thresholds_or_the_review_ledger(), test_it_no_ops_when_the_table_is_missing_or_already_empty(), test_migration_is_one_statement()

### Community 530 - "tests/test_ncaaf_se_louisiana_alias_migration.py"
Cohesion: 0.15
Nodes (4): test_a_pick_is_never_deleted_and_never_regraded(), test_it_guards_on_both_names_and_both_still_unscored(), test_migration_is_one_statement(), test_odds_move_only_when_canonical_has_none()

### Community 531 - "NFL in-play leader model decision"
Cohesion: 0.11
Nodes (7): honest_probability(), test_a_loop_that_dies_fails_its_job(), test_it_decides_on_its_own_probability(), test_the_action_threshold_key_is_on_one_line(), test_the_loop_refuses_a_price_shorter_than_the_floor(), test_the_mlb_live_scorer_skips_it(), test_the_price_floor_is_minus_140()

### Community 532 - "tests/test_overnight_polling.py"
Cohesion: 0.24
Nodes (7): _hours(), _jobs(), _match(), test_every_hour_of_the_day_is_covered(), test_the_overnight_pass_is_the_ordinary_one(), test_the_overnight_window_exists(), test_the_windows_do_not_overlap()

### Community 534 - "NCAAF steam lag study"
Cohesion: 0.27
Nodes (9): attach_scores(), build_events(), fmt(), grade(), lines_at_pulls(), load(), main(), summarise() (+1 more)

### Community 535 - "NCAAF weather and wind totals study"
Cohesion: 0.23
Nodes (6): build_spots(), evaluate(), load_games(), main(), scoring_by_wind(), wilson()

### Community 536 - "Mobile type-check baseline tests"
Cohesion: 0.29
Nodes (13): _entries(), _log(), _log_line(), _run(), test_a_clean_log_warns_for_every_baseline_entry(), test_a_compiler_crash_is_not_a_clean_run(), test_a_different_app_message_fails(), test_a_fixed_baseline_entry_warns_and_does_not_fail() (+5 more)

### Community 537 - "NFL prop feature research scripts"
Cohesion: 0.07
Nodes (29): _add_features(), build_nfl_prop_scoring_rows(), build_nfl_prop_training_dataset(), _cols(), derived_targets(), _load(), _nfl_season(), _pool_mask() (+21 more)

### Community 541 - "Tracked performance verification script"
Cohesion: 0.10
Nodes (18): dup, empty, half, l50, loss, noAction, open1, open2 (+10 more)

### Community 542 - "NBA public splits consensus parsing"
Cohesion: 0.17
Nodes (9): an_pct(), parse_v1_sides(), v1_consensus_row(), test_a_one_percent_side_is_not_inflated_to_100(), test_out_of_range_or_junk_percentages_are_refused(), test_v1_flat_fields_map_to_market_side_and_metric(), test_v1_reads_only_the_consensus_book(), test_v1_rows_carry_the_inserted_stamp_and_its_lag() (+1 more)

### Community 543 - "Live monitor cache tests"
Cohesion: 0.15
Nodes (10): age(), cached(), clear(), test_cache_raises_when_it_has_nothing_to_fall_back_on(), test_cache_reports_age(), test_cache_serves_stale_rather_than_failing(), boom(), test_cache_serves_within_ttl_and_recomputes_after() (+2 more)

### Community 544 - "No-vig closing line capture tests"
Cohesion: 0.20
Nodes (8): _fn(), test_a_missing_bet_book_close_is_not_filled_from_another_book(), test_backfill_revisits_anything_that_is_not_standard_v2(), test_capture_grades_raw_same_book_and_a_separate_pinnacle_edge(), test_capture_stamps_method_and_close_book(), test_game_close_never_falls_back_past_first_pitch(), test_pinnacle_is_a_second_lookup_not_the_headline_close(), test_prop_close_stays_bounded_at_first_pitch()

### Community 546 - "tests/test_claude_rules_split.py"
Cohesion: 0.18
Nodes (4): test_claude_md_still_points_at_the_rules_directory(), test_every_rule_file_actually_carries_rules(), test_every_rule_file_is_path_scoped(), test_no_rule_was_lost_when_the_split_happened()

### Community 547 - "tests/test_db_setup.py"
Cohesion: 0.23
Nodes (6): _get_columns(), test_games_table_columns(), test_injuries_table_columns(), test_odds_table_columns(), test_picks_table_columns(), test_schema_is_idempotent()

### Community 548 - "tests/test_dedupe_opening_signals.py"
Cohesion: 0.10
Nodes (9): test_a_graded_row_is_never_deleted(), test_a_row_with_computed_clv_is_never_deleted(), test_every_field_that_defines_the_bet_must_agree(), test_it_is_dry_run_by_default(), test_the_delete_selects_through_the_same_gates(), test_the_pair_must_be_an_old_shape_new_shape_pair(), test_the_report_and_the_delete_share_one_definition(), test_the_row_kept_is_the_one_locked_earlier() (+1 more)

### Community 552 - "tests/test_pbp_backfill_resilience.py"
Cohesion: 0.24
Nodes (6): _backfill_body(), test_a_failed_game_rolls_the_connection_back(), test_a_run_that_wrote_nothing_reports_an_error_not_a_success(), test_errors_are_counted_not_just_logged(), test_partial_failures_are_surfaced_too(), test_the_rollback_cannot_itself_raise()

### Community 561 - "First pitch guard tests"
Cohesion: 0.11
Nodes (7): test_capture_compares_the_picks_own_clock_not_the_capture_clock(), test_capture_fails_open_on_a_missing_timestamp(), test_delivery_fails_open_too(), test_health_check_uses_the_same_first_pitch_bound_as_discord(), test_mixed_timestamp_shapes_are_parsed_not_string_compared(), test_the_dry_run_count_uses_the_same_predicate_as_the_insert(), test_the_restatement_path_is_deliberately_not_guarded()

### Community 563 - "Paused model profitability assessment"
Cohesion: 0.10
Nodes (15): _auto_paused_models(), active_era(), assess(), _half(), fetch(), grade(), main(), sweep() (+7 more)

### Community 568 - "NCAAF game-day loop cadence"
Cohesion: 0.15
Nodes (7): _main_source(), test_an_unanswered_state_feed_does_not_look_like_the_slate_ending(), test_loop_exits_early_when_no_kickoff_is_near(), test_loop_polls_at_the_idle_cadence_when_nothing_is_live(), test_loop_sleeps_the_remainder_not_a_flat_interval(), test_loop_warns_when_a_pass_overruns_its_interval(), test_odds_fetch_uses_the_odds_cadence_not_the_loop_cadence()

### Community 569 - "NBA in-game study one tests"
Cohesion: 0.17
Nodes (15): _pin(), _q(), _rows(), _state(), test_every_fit_for_season_s_uses_earlier_seasons_only(), test_expected_rates_use_the_teams_earlier_dates_only(), test_ig1_bets_against_luck_and_the_control_with_it(), test_luck_counts_a_three_three_times_and_a_free_throw_once() (+7 more)

### Community 571 - "NCAAF quarterback ablation study"
Cohesion: 0.28
Nodes (7): _fit(), main(), _report(), run(), summarise(), walk_forward(), wilson()

### Community 572 - "NCAAF line move spots"
Cohesion: 0.27
Nodes (6): eval_follow_spread(), eval_follow_total(), load(), main(), _summ(), wilson()

### Community 573 - "NBA public splits pipeline step"
Cohesion: 0.12
Nodes (13): inserted_minus_start_min(), run_forward(), side(), step_nba_public_splits(), test_v1_inserted_lag_is_minutes_after_the_listed_start(), Coverage, Forward capture (2026-27), How to read it (+5 more)

### Community 574 - "tests/test_prompt_reads_thresholds.py"
Cohesion: 0.18
Nodes (4): test_the_auto_pause_lookup_fails_open(), test_the_prompt_carries_no_per_model_cut(), test_the_prompt_still_says_it_is_pasted_once(), test_the_sync_mirrors_both_pause_registers()

### Community 575 - "tests/test_system_health_meta_steps.py"
Cohesion: 0.25
Nodes (5): _meta_steps(), test_aborted_sentinel_is_excluded(), test_health_check_is_excluded(), test_model_quality_is_excluded(), test_sentinel_matches_the_writer()

### Community 577 - "NBA period score ingestion"
Cohesion: 0.19
Nodes (13): ensure_table(), fetch_date(), _int(), main(), parse_period_rows(), run(), write(), _event() (+5 more)

### Community 58 - "NFL preregistered 2026 edge study"
Cohesion: 0.09
Nodes (39): bar(), bets_frame(), bh(), binom_line(), _by_game(), cell(), fam(), first_last() (+31 more)

### Community 580 - "scripts/render_brand_icons.py"
Cohesion: 0.24
Nodes (3): draw_mark(), main(), render()

### Community 582 - "NHL game results parsing"
Cohesion: 0.38
Nodes (9): parse_nhl_game(), _g(), test_arizona_folds_into_utah(), test_missing_teams_returns_none(), test_ot_home_win_is_regulation_draw(), test_preseason_game_skipped(), test_regulation_home_win(), test_scheduled_game_has_no_scores() (+1 more)

### Community 585 - "NBA prop model verification stages"
Cohesion: 0.12
Nodes (29): decisions_for(), adv_from_log(), asof_roster(), blind_structured(), card_block(), collapse_report(), _compare(), log() (+21 more)

### Community 586 - "supabase/functions/stripe-webhook/index.ts"
Cohesion: 0.31
Nodes (9): applySubscription(), iso(), resolveUserId(), stripeGet(), timingSafeEqual(), toHex(), verifySignature(), admin (+1 more)

### Community 588 - "NFL backfill retry resilience"
Cohesion: 0.12
Nodes (5): test_a_dropped_connection_is_retried(), test_an_http_error_is_NOT_retried(), test_it_gives_up_rather_than_looping_forever(), test_resume_probes_ONE_market_not_any_row(), test_resume_with_no_probe_market_skips_nothing()

### Community 589 - "tests/test_mobile_neutral_signal_label.py"
Cohesion: 0.31
Nodes (7): _read(), test_explainer_names_neutral(), test_filters_and_card_speak_the_display_name(), test_model_screens_speak_the_display_name(), test_no_member_label_prints_a_raw_signal_type(), test_none_badge_reads_neutral(), test_withdrawn_pick_is_not_badged_neutral()

### Community 591 - "College football data checks"
Cohesion: 0.33
Nodes (5): _check(), _lines_coverage(), main(), _null_report(), _sample_keys()

### Community 593 - "tests/test_scorer_commits_per_game.py"
Cohesion: 0.40
Nodes (8): _between(), _run_scorer_body(), test_a_lost_connection_re_runs_the_game_once_and_never_the_pass(), test_each_game_is_its_own_committed_unit(), test_no_bulk_delete_of_non_bet_rows_precedes_the_loop(), test_picks_are_only_counted_once_the_game_committed(), test_the_housekeeping_delete_is_a_sweep_after_the_loop(), test_the_outer_handler_still_records_the_failure()

### Community 595 - "NFL model import checks"
Cohesion: 0.15
Nodes (6): _import_under_scheduler_env(), _scheduler_env(), test_no_nfl_script_uses_the_bare_models_import(), test_the_card_imports_under_the_schedulers_invocation(), test_the_exemption_is_the_loader_and_it_still_exists(), test_the_loader_reaches_nfls_models_not_the_platforms()

### Community 596 - "NBA ESPN box score parsing"
Cohesion: 0.08
Nodes (24): box_team_totals(), et_date(), nba_team(), _no_minutes(), parse_nba_box(), parse_nba_dnp(), parse_nba_postponed(), parse_nba_scoreboard() (+16 more)

### Community 597 - "NFL box scores before recap"
Cohesion: 0.17
Nodes (8): _daily(), _job_body(), test_a_malformed_date_is_refused_before_anything_runs(), test_nfl_box_scores_are_ingested_before_settle(), test_nfl_finals_still_precede_the_box_scores(), test_the_job_does_not_read_rowcount_off_the_cursor(), test_the_job_only_clears_its_own_two_ledger_kinds(), test_the_job_posts_both_surfaces_through_the_ordinary_paths()

### Community 60 - "tests: test_wnba_availability + wnba_availability"
Cohesion: 0.10
Nodes (33): absence_features(), absent_teammates(), build_context_features(), expected_rotation(), is_starter_tier(), _mean(), prior_rows(), recent_team_game_dates() (+25 more)

### Community 600 - "NCAAF in-play candidate grading"
Cohesion: 0.17
Nodes (6): build_candidates(), grade(), odds_from_rows(), state_index_at(), test_grade_totals_and_moneyline(), test_odds_dict_has_the_shape_the_loop_reads()

### Community 601 - "NCAAF cross-book opener guard tests"
Cohesion: 0.17
Nodes (7): _branch(), test_band_ceiling_is_enforced_in_the_scorer(), test_dev_sign_maps_to_the_side_the_sharp_book_favours(), test_every_precondition_failure_returns_no_bet(), test_gate_is_enforced_and_read_from_the_artifact(), test_simultaneity_is_enforced(), test_still_gettable_is_enforced()

### Community 604 - "NFL prop scoring window tests"
Cohesion: 0.17
Nodes (5): test_days_is_derived_from_the_window_not_pinned(), test_every_live_nfl_prop_model_still_carries_its_own_cut(), test_the_live_ten_are_not_a_clean_bill_of_health(), test_the_window_reaches_at_least_the_ten_day_horizon_the_other_nfl_jobs_use(), test_twelve_are_live_and_none_is_paused()

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

### Community 615 - "NFL 2026 track policy pins"
Cohesion: 0.24
Nodes (8): _src(), test_config_comments_state_the_policy(), test_live_cuts_did_not_move(), test_max_fire_lead_stays_four_in_the_live_model(), test_paused_xgb_props_stay_paused(), test_the_script_does_not_write_thresholds_or_units(), test_tracking_doc_names_the_command_and_the_criteria(), test_units_stay_at_one_percent_on_both_cards()

### Community 617 - "Mobile type-check baseline checker"
Cohesion: 0.27
Nodes (8): diagnostic_key(), log_is_compiler_failure(), main(), parse_baseline(), parse_log(), render_baseline(), stale(), unexpected()

### Community 62 - "NBA game market search lab"
Cohesion: 0.05
Nodes (61): assemble(), _assert_spread_sign(), attach_close(), bars(), bet_frame(), blind_bets(), blind_first_fetch(), boot_ci() (+53 more)

### Community 620 - "NFL prop backtest universe summary"
Cohesion: 0.29
Nodes (6): _universe_summary(), test_a_universe_without_the_model_sums_still_summarises(), test_mean_projection_and_mean_actual_separate_mean_bias_from_shape_bias(), test_model_over_rate_and_its_gap_are_reported(), _universe(), test_a_nonfinite_fair_price_cannot_switch_the_gate_off()

### Community 621 - "NCAAF opener timestamp gap checks"
Cohesion: 0.18
Nodes (6): _minutes_apart(), test_identical_timestamps_are_zero_apart(), test_one_refresh_pass_late_is_tolerated(), test_the_real_production_skew_is_rejected(), test_timezone_suffixes_do_not_crash(), test_unparseable_timestamps_fail_closed()

### Community 622 - "NCAAF in-play DraftKings qualifying gate"
Cohesion: 0.18
Nodes (4): test_a_cheaper_book_no_longer_buys_its_way_past_the_floor(), test_the_bet_is_still_recorded_at_the_best_price(), test_the_gate_reads_the_draftkings_numbers(), test_the_stale_line_cap_still_judges_the_dk_edge()

### Community 624 - "NCAAF consensus gate frame builder"
Cohesion: 0.31
Nodes (7): build_frames(), fmt(), grade(), load_closes(), main(), match(), wilson()

### Community 628 - "Shared pytest SQL and harness checks"
Cohesion: 0.04
Nodes (45): _identity_maps(), _platform_gates_off(), _declared(), test_an_explicit_run_date_must_be_a_real_iso_date(), test_declared_keys_are_unique(), test_every_declared_job_names_a_registered_type(), test_every_declared_job_validates(), test_no_run_date_means_the_module_resolves_it() (+37 more)

### Community 629 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.47
Nodes (6): contentHeight(), evalExpr(), lineOf(), styleBlock(), styleProp(), visualHeight()

### Community 631 - "NCAAF in-play history credit sharding"
Cohesion: 0.22
Nodes (6): budget_for(), calls_in(), parse_shard(), shard_windows(), test_a_bad_shard_spec_is_refused(), test_shard_parsing_and_splitting_is_round_robin_and_total()

### Community 632 - "NFL in-play prop calibration dataset"
Cohesion: 0.09
Nodes (18): evaluate(), _infer_position(), main(), _pool_prior(), report(), _rows_for_market(), _to_states(), accrual_at() (+10 more)

### Community 633 - "Postgres scripts and grant revokes"
Cohesion: 0.07
Nodes (9): _fmt_et_time(), get_conn(), query(), main(), _strip_outer_tx(), test_it_asserts_the_app_write_surface_survives(), test_the_roles_are_named_never_public(), test_the_runners_transaction_stripping_leaves_the_do_block_intact() (+1 more)

### Community 634 - "NFL in-play two-sided offer grid"
Cohesion: 0.22
Nodes (8): s(), h2(), h3(), spread_offers(), total_offers(), two_sided_bets(), x_margin(), grid()

### Community 635 - "tests/test_demote_ncaaf_over_under_platt.py"
Cohesion: 0.32
Nodes (4): _stmts(), test_it_demotes_only_the_measured_promotion(), test_it_does_not_move_the_gate_the_floor_or_a_pause(), test_migration_is_one_statement()

### Community 637 - "tests/test_discord_post_one_pick_migration.py"
Cohesion: 0.29
Nodes (3): _pairs(), test_it_names_each_measured_extra_and_the_row_kept(), test_the_update_does_not_rewrite_the_graded_outcome()

### Community 638 - "tests/test_game_scorer_spares_nfl_props.py"
Cohesion: 0.43
Nodes (5): _between(), _run_scorer_body(), test_an_nfl_game_never_enters_the_per_game_clear(), test_both_live_non_bet_clears_leave_nfl_rows(), test_the_left_out_ufc_clear_only_removes_unsettled_non_bets()

### Community 639 - "NBA injury report player matching"
Cohesion: 0.17
Nodes (7): match_player(), _near_season(), remap_changes(), _surname_key(), test_a_name_printed_differently_matches_on_surname_and_initial_within_the_team(), test_player_ids_match_on_team_first_then_a_unique_season_name(), test_remap_rewrites_only_names_whose_id_changed()

### Community 64 - "NFL in-play score distribution pricing"
Cohesion: 0.07
Nodes (35): _model_price(), american_to_prob(), anchor_to_market(), devig_power(), margin_pmf(), _over_under(), price_moneyline(), price_quarter() (+27 more)

### Community 641 - "Mobile quiet update download tests"
Cohesion: 0.17
Nodes (8): _code_only(), _read(), test_a_downloaded_update_is_announced_quietly_once(), test_app_root_mounts_the_ota_updater(), test_every_trigger_only_downloads(), test_nothing_in_the_app_reloads_a_running_app(), test_the_pieces_exist(), test_the_updater_downloads_the_update()

### Community 642 - "NBA team total luck replay"
Cohesion: 0.16
Nodes (7): team_total_resid(), art(), ld(), results(), test_the_artifact_holds_the_lab_s_team_total_residuals_in_order(), test_the_live_code_reproduces_the_lab_game_for_game(), test_the_live_home_parts_are_the_independent_lab_copy_s()

### Community 647 - "NFL Kalshi price history fetch"
Cohesion: 0.21
Nodes (6): candles(), get(), map_games(), paged(), parse_event(), probe()

### Community 649 - "X client posting safety tests"
Cohesion: 0.20
Nodes (5): _creds(), test_a_5xx_is_transport_and_not_a_tweet_id(), test_a_missing_table_is_a_no_op(), test_allow_link_is_off_on_the_pick_client(), _post()

### Community 65 - "NBA prop model research lab"
Cohesion: 0.07
Nodes (46): books(), decimal(), expected_value(), p_over(), _agg(), apply_rule(), binary_baselines(), binary_indep() (+38 more)

### Community 650 - "Mobile stats filter UX verify"
Cohesion: 0.17
Nodes (10): board, chip, lineOnlyFn, playersDay, ROOT, sportReset, stats, teams (+2 more)

### Community 653 - "NFL prop pulled quote filter"
Cohesion: 0.32
Nodes (8): drop_pulled_quotes(), _ts(), _q(), test_a_book_on_its_own_cadence_is_not_penalised_inside_three_hours(), test_a_book_that_stopped_returning_the_game_is_dropped(), test_a_player_the_book_stopped_quoting_is_dropped(), test_a_whole_market_the_book_pulled_is_dropped(), test_rows_from_one_fetch_minutes_apart_are_kept_and_a_line_move_is_not_a_pull()

### Community 654 - "Duplicate pick exclusion across records"
Cohesion: 0.22
Nodes (6): duplicate_copy_exclusion_sql(), test_the_discord_recap_counts_each_event_once(), test_the_finder_skips_copies_already_marked(), test_the_marker_is_one_constant_and_one_predicate(), test_the_monitor_dashboard_box_score_arm_counts_each_event_once(), test_the_monitor_dashboard_picks_arm_counts_each_event_once()

### Community 656 - "NBA box score spot checks"
Cohesion: 0.25
Nodes (6): _blank(), _flt(), _int(), sample_compare(), _txt(), sign_sample()

### Community 658 - "NFL prop too-early kickoff ceiling"
Cohesion: 0.30
Nodes (8): _nfl_prop_too_early(), _iso(), test_a_kickoff_beyond_the_ceiling_is_too_early(), test_a_started_or_unknown_kickoff_is_not_too_early(), test_the_boundary_is_inclusive_at_the_ceiling(), test_the_scorer_and_the_card_read_ONE_constant(), test_the_scorer_loop_actually_applies_the_ceiling(), test_the_z_suffix_parses_like_the_offset_form()

### Community 662 - "SBR CSV loader and abbreviations"
Cohesion: 0.25
Nodes (3): canonical_abbrev(), parse_csv_file(), test_sbr_abbreviations_are_canonicalised_for_mlb_only()

### Community 663 - "NFL in-play edge replication tables"
Cohesion: 0.36
Nodes (9): families(), fmt(), main(), parse_2025_output(), pooled_table(), replication(), repro_check(), row_of() (+1 more)

### Community 665 - "Worker-only table lockdown tests"
Cohesion: 0.17
Nodes (6): _call_source(), _repo_sources(), test_every_guard_on_a_worker_only_table_asks_about_rls(), test_every_literal_lock_down_target_is_declared(), test_every_worker_only_create_site_goes_through_the_gated_helper(), test_no_create_site_uses_the_ungated_builder()

### Community 666 - "Voided NFL prop opening signals cleanup"
Cohesion: 0.23
Nodes (6): _stmts(), test_it_deletes_exactly_the_three_measured_lock_keys(), test_it_does_not_touch_picks_or_discord(), test_it_still_skips_a_key_that_has_a_standing_bet(), test_migration_is_one_statement(), test_standing_pick_uses_lock_key_sql_not_player_id()

### Community 670 - "Game log backfill skip tests"
Cohesion: 0.11
Nodes (10): test_app_errors_is_write_only_for_the_anon_key(), test_crash_log_is_free_of_app_imports(), test_kinds_agree_between_app_and_server(), test_the_crash_log_logic_holds(), test_the_fallback_never_renders_blank(), _backfill_body(), test_a_game_absent_from_our_games_table_is_still_skipped(), test_no_skip_is_keyed_on_date_alone() (+2 more)

### Community 673 - "Scorer keeps off-DraftKings priced bets tests"
Cohesion: 0.29
Nodes (6): _bet(), db(), _left(), _statement(), test_a_bet_priced_at_another_books_line_survives_and_a_bet_with_no_price_does_not(), test_the_statement_names_both_prices()

### Community 675 - "Row-level security lockdown order tests"
Cohesion: 0.25
Nodes (4): closed_tables(), test_lock_down_never_uses_force_row_level_security(), test_lock_down_sql_revokes_before_it_enables_rls(), test_the_worker_only_tables_are_not_also_declared_app_readable()

### Community 677 - "UFC mirror ETag cache store"
Cohesion: 0.29
Nodes (5): _cached_etag(), _store_etag(), test_a_round_trip_actually_persists(), test_an_empty_etag_is_never_stored(), test_mirror_unchanged_is_false_when_anything_is_unknown()

### Community 679 - "NCAAF situational spot scans"
Cohesion: 0.10
Nodes (10): is_bowl_game(), build_spots(), evaluate(), load_team_games(), main(), wilson(), load_data(), main() (+2 more)

### Community 689 - "App-readable table manifest"
Cohesion: 0.13
Nodes (10): all_readable(), lock_down_sql(), test_the_artifact_table_revokes_at_its_own_creation(), _app_relations(), test_every_relation_the_app_reads_is_declared(), test_everything_declared_writable_is_also_readable_or_deliberately_not(), test_lock_down_sql_refuses_anything_that_is_not_a_plain_identifier(), test_lock_down_sql_refuses_every_table_the_app_reads() (+2 more)

### Community 694 - "Manual X account posts guide"
Cohesion: 0.29
Nodes (7): pin(), How to enqueue a post with an image, How to enqueue another post or thread, Manual posts to @SignalBasePicks, Pinning, What is already queued, What the drain will not do

### Community 695 - "Every named sportsbook is fetched"
Cohesion: 0.18
Nodes (5): _param_books(), test_a_sharp_reference_is_never_also_a_soft_book(), test_every_bettable_book_can_be_named_to_a_human(), test_every_named_book_is_in_the_pull_that_serves_it(), test_the_nfl_backfill_defaults_to_the_live_pull()

### Community 697 - "NBA injury report slot retries"
Cohesion: 0.22
Nodes (7): pull_with_retry(), test_a_connection_lost_mid_write_re_runs_the_whole_slot(), executemany(), __init__(), test_a_statement_timeout_rolls_back_and_re_runs_the_slot(), executemany(), __init__()

### Community 700 - "NBA harness cell emission fakes"
Cohesion: 0.22
Nodes (6): _emit_world(), _spy_run_cells(), test_closing_value_is_priced_with_the_markets_empirical_distribution(), test_every_family_emits_exactly_its_cells_through_the_harness(), test_the_d_cells_are_gated_on_the_points_own_decision_times(), test_the_bootstrap_is_seeded_and_refines_small_p()

### Community 701 - "UFC fight stats scraping"
Cohesion: 0.13
Nodes (13): _aggregate_stats(), _int_or_none(), _mmss_to_sec(), _of_pair(), parse_event_page(), _two_ints(), parse_fight_page(), test_mmss_to_sec() (+5 more)

### Community 707 - "NBA prop pipeline steps"
Cohesion: 0.25
Nodes (4): step_nba_prop_market(), step_nba_prop_projection(), step_nba_prop_scoring(), step_nba_props()

### Community 71 - "In-play trigger orchestrator and odds fetch"
Cohesion: 0.04
Nodes (48): _credit_cost(), credits_used_today(), fetch_in_play_odds(), consume_triggers_once(), _last_fg_fetch_age(), _live_game_ids(), _pending_triggers(), run_live_loop() (+40 more)

### Community 716 - "NCAAF scoreboard yardline parsing"
Cohesion: 0.21
Nodes (6): _abbrev_fits(), _parse_yardline(), _cfbd_game(), test_cfbd_state_carries_the_yardline_and_the_raw_situation(), test_cfbd_yardline_from_every_stored_situation(), test_cfbd_yardline_refuses_rather_than_guesses()

### Community 718 - "NBA splits game date mapping"
Cohesion: 0.29
Nodes (5): et_game_date(), _game_meta(), team_abbr(), test_a_late_west_coast_tip_belongs_to_the_previous_et_date(), test_team_ids_come_from_the_abbr_then_the_full_name()

### Community 719 - "Mobile accessibility verify script"
Cohesion: 0.67
Nodes (3): read(), readUtf8(), verticalSlop()

### Community 72 - "Market handicap feature tests"
Cohesion: 0.04
Nodes (52): diff(), pitcher_diff(), diff(), pitcher_diff(), numeric_feature_value(), attach_market_handicap(), build_public_features(), build_rich_handicap() (+44 more)

### Community 721 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.67
Nodes (3): closeOf(), openTag(), toggleUse()

### Community 731 - "Mobile NHL Today look-ahead tests"
Cohesion: 0.29
Nodes (5): _fn(), _read(), test_the_nhl_read_matches_the_other_look_aheads(), test_the_sport_chip_is_the_hook_not_an_allowlist(), test_use_today_picks_fetches_nhl_across_that_window()

### Community 732 - "NBA splits row quality flag rule"
Cohesion: 0.29
Nodes (4): quality_backfill_statements(), quality_flag(), test_the_quality_rule_puts_reversed_ahead_of_late(), test_the_stored_row_backfill_flags_exactly_what_the_rule_flags()

### Community 74 - "Prop CLV and SQL escaping tests"
Cohesion: 0.09
Nodes (17): _fn(), test_a_backfill_failure_never_breaks_settlement(), test_a_pick_is_only_stamped_captured_once_a_measure_resolved(), test_a_pick_stamped_after_first_pitch_is_never_measured(), test_a_prop_pick_whose_label_has_no_name_is_skipped_not_guessed(), test_both_guards_agree(), test_clv_pct_never_compares_prices_across_a_moved_line(), test_golf_stays_excluded() (+9 more)

### Community 75 - "NCAAF margin and totals evaluation"
Cohesion: 0.11
Nodes (16): margin_cover_prob(), fit_and_register(), main(), _print_sweep(), rmse(), sweep_spread(), verdict(), walk_forward() (+8 more)

### Community 757 - "Anonymous read grant apply script"
Cohesion: 0.13
Nodes (11): write_verbs_for(), _anon_can_read(), _function_plan(), _function_signature(), main(), _plan(), _table_exists(), test_every_declared_relation_is_granted_exactly_once() (+3 more)

### Community 76 - "ncaaf_live/tests/test_serve.py"
Cohesion: 0.05
Nodes (53): _clock_seconds(), extract_live_states_cfbd(), _parse_situation(), check_feed_assumptions(), _competitors(), _count_plays(), _dig(), extract_live_events() (+45 more)

### Community 80 - "Per-model EV floor card tests"
Cohesion: 0.08
Nodes (22): _built(), floor_030(), identity_maps(), _nfl_fixtures(), open_pregame_cut(), _pregame(), shrink_map(), test_a_floor_note_does_not_stop_the_best_price_recheck() (+14 more)

### Community 82 - "Mobile screen checks run from Python"
Cohesion: 0.04
Nodes (47): tsx_cmd(), _read(), test_combiner_is_pure_and_lives_next_to_fill(), test_handoff_opens_the_combined_url_not_the_first_leg(), test_the_behavioural_checks_pass(), _load_state_dir(), _raw_error_lines(), _read() (+39 more)

### Community 849 - "First-time setup and full backtest"
Cohesion: 0.29
Nodes (4): _print_summary(), run_full_backtest(), first_time_setup(), setup_database()

### Community 850 - "Model training and WNBA points rebuild"
Cohesion: 0.04
Nodes (48): calibration_method(), _dispersion(), f(), _count_cv_splits(), _gamma_shape(), _mean_calibration_error(), _nb1_dispersion(), _nb_dispersion() (+40 more)

### Community 852 - "Market coverage probe tests"
Cohesion: 0.07
Nodes (18): candidate_markets(), _standard_markets(), test_a_two_sided_market_is_never_reported_one_sided(), test_an_all_line_leg_slip_does_not_claim_a_model(), test_it_asks_about_the_board_columns_that_are_permanently_blank(), test_it_reports_supported_but_empty_apart_from_unsupported(), test_no_market_is_asked_about_twice(), test_one_market_per_call_so_a_rejected_key_is_identified_exactly() (+10 more)

### Community 853 - "No record-only mode guard tests"
Cohesion: 0.43
Nodes (4): _allowed(), _hits(), _rel(), test_the_repo_has_no_record_only_or_paper_tracking_mode()

### Community 858 - "Time-ordered cross validation"
Cohesion: 0.29
Nodes (3): _time_ordered_cv(), test_every_validation_fold_is_later_than_its_training_fold(), test_the_training_window_expands()

### Community 86 - "Pandas research scripts and dtype tests"
Cohesion: 0.03
Nodes (83): coerce_numeric_features(), load_games(), main(), pivot_spreads(), pivot_totals(), load_games(), main(), wide_spreads() (+75 more)

### Community 860 - "NFL research files backup to Supabase"
Cohesion: 0.44
Nodes (5): backup(), files(), main(), restore(), verify()

### Community 863 - "NBA injury report name matching"
Cohesion: 0.22
Nodes (7): name_first_last(), norm_name(), _row(), team_code(), test_name_key_drops_accents_punctuation_and_suffixes(), test_names_turn_round_with_their_suffix_on_the_surname(), test_team_names_map_to_our_codes()

### Community 864 - "NBA game outcome probability harness"
Cohesion: 0.29
Nodes (5): test_a_period_moneyline_removes_the_tie_mass(), test_a_past_average_miss_does_not_move_the_centre(), test_a_skewed_distribution_is_not_read_as_normal(), test_the_empirical_model_matches_the_normal_one_on_normal_residuals(), test_whole_lines_carry_push_mass_and_half_lines_none()

### Community 867 - "UFC results skip-unchanged check"
Cohesion: 0.33
Nodes (3): mirror_unchanged(), step_ufc_results(), test_mirror_unchanged_is_conservative_when_it_cannot_tell()

### Community 87 - "NHL box score parsing"
Cohesion: 0.12
Nodes (16): _decision(), fill_missing(), _insert_absent(), _int(), _name(), parse_boxscore(), side_rows(), store_boxscore() (+8 more)

### Community 874 - "Injury return ramp players"
Cohesion: 0.22
Nodes (4): _compute_return_ramp(), fetch_mlb_transactions(), fetch_return_ramp_players(), run_injury_ingestor()

### Community 876 - "Golf pipeline steps"
Cohesion: 0.33
Nodes (3): _golf_enabled(), step_golf_odds(), step_golf_results()

### Community 877 - "NHL derivative totals card stub"
Cohesion: 0.40
Nodes (3): main(), run(), test_card_writes_nothing_and_the_pipeline_does_not_call_it()

### Community 880 - "NBA projection price cache checks"
Cohesion: 0.33
Nodes (3): _games_file(), test_a_segment_file_missing_part_of_a_season_is_refused(), test_full_checks_the_price_cache_for_every_graded_season_before_building_anything()

### Community 882 - "NBA results game window"
Cohesion: 0.60
Nodes (4): _games(), _postponed(), _schedule(), end()

### Community 884 - "NFL in-play pick date and announce tests"
Cohesion: 0.25
Nodes (3): test_a_night_game_pick_carries_the_game_s_date_not_the_utc_clock(), test_nothing_written_means_nothing_announced(), test_resolution_refuses_rather_than_guesses()

### Community 89 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.03
Nodes (50): a11ySrc, allowHit, ALLOWLIST, app, badExempt, bar, bareClose, baselineLeft (+42 more)

### Community 897 - "Pipeline credit burn findings"
Cohesion: 0.25
Nodes (4): test_burn_is_judged_against_the_cap_not_against_yesterday(), test_burn_survives_a_non_numeric_credits_column(), test_failed_api_calls_are_reported_even_when_burn_is_low(), findings_from_burn()

### Community 899 - "Units won convention"
Cohesion: 0.29
Nodes (4): test_prob_only_picks_fall_back_to_the_settlement_price(), test_units_convention_matches_the_stated_rule(), _decimal_odds(), units_won()

### Community 900 - "Pipeline watch announce and escalation"
Cohesion: 0.29
Nodes (3): test_a_missing_webhook_escalates_rather_than_vanishing(), _announce(), _announce_and_ledger()

### Community 905 - "UFC stats event list parsing"
Cohesion: 0.33
Nodes (4): _parse_event_date(), parse_event_list(), test_event_date(), test_parse_event_list()

### Community 906 - "NCAAF play-by-play season pull"
Cohesion: 0.15
Nodes (9): _extremes(), fetch_season(), _get(), main(), observed_ranges(), pull_season(), store_season(), test_the_scan_survives_nulls_and_non_numeric_cells() (+1 more)

### Community 907 - "NCAAF CFBD stats parsing"
Cohesion: 0.08
Nodes (22): _int(), _num(), parse_advanced_stats(), parse_ratings(), parse_returning(), parse_season_stats(), parse_talent(), parse_team_game_stats() (+14 more)

### Community 91 - "NFL in-play backtest replay harness"
Cohesion: 0.05
Nodes (33): align_states(), build_team_map(), _game_index(), kill_verdict(), load_cached_snapshots(), main(), replay(), _settle() (+25 more)

### Community 921 - "Pipeline pass failure findings"
Cohesion: 0.33
Nodes (4): test_a_clean_pass_produces_no_finding(), test_a_pass_with_failed_steps_is_reported(), test_a_pass_with_no_finish_is_reported_without_over_reading_it(), findings_from_passes()

### Community 922 - "App RPC declaration guard"
Cohesion: 0.40
Nodes (3): _app_rpcs(), test_every_rpc_the_app_calls_is_declared_or_known_absent(), test_the_dynamic_rpc_resolver_actually_finds_the_ternary_names()

### Community 93 - "MLB totals public fade tests"
Cohesion: 0.07
Nodes (42): load_latest_quotes(), find_fade_bets(), is_pre_commence(), load_public_over_splits(), select_latest_pre_commence_over(), under_in_odds_band(), pick_rows(), publish() (+34 more)

### Community 932 - "NHL goalie saves above expected"
Cohesion: 0.83
Nodes (4): _goalie_line(), regressed(), saved_above(), tot()

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

### Community 892 - "Mobile app build scripts"
Cohesion: 0.25
Nodes (8): scripts, android, build:ios:preview, build:ios:production, ios, start, typecheck, web

### Community 904 - "Mobile dev dependencies"
Cohesion: 0.29
Nodes (7): devDependencies, @babel/core, babel-plugin-module-resolver, babel-preset-expo, tsx, @types/react, typescript

### Community 929 - "Opening signals shadow table"
Cohesion: 0.70
Nodes (4): idx_opening_signals_date, idx_opening_signals_model, idx_opening_signals_settle, opening_signals

### Community 930 - "In-app feedback thread tables"
Cohesion: 0.40
Nodes (5): feedback_messages, feedback_threads, idx_feedback_messages_thread, idx_feedback_threads_device, idx_feedback_threads_status

### Community 936 - "NBA 2026-27 rebuild write-up"
Cohesion: 0.06
Nodes (31): 1. Pre-registered bars (fixed 2026-10-15, before the first grid), 2. Data used (all in Supabase), 3. The market grid, 4.1 Game markets — closed for 2026-27, 4.2 First half / first quarter / team totals — closed for 2026-27, 4.3 Player props — one rule ships, 4.4 Player props — projection models (the NHL recipe), 4.5 The projection model on the worker's inputs only (+23 more)

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

### Community 246 - "docs: best_line + config_topology"
Cohesion: 0.10
Nodes (21): Book roles: fetched (LINE_SHOP_BOOKMAKERS) vs offered (BEST_LINE_BOOKMAKERS), DECIDE_ON_BEST_PRICE=0 restores DraftKings as the deciding price, Stage 2: decide, size and settle at the best price (picks.decision_*), _get_event_odds fetched DraftKings-only (MLB F5, UFC round totals), The live models join best-price deciding (2026-09-10), PREGAME_PRICE_MAX_AGE_MIN (180 min) on game-market reads, Scoring off another book's line (picks.line_book), BEST_LINE_EXCLUDE_BOOKMAKERS — unbettable books out of shopping (+13 more)

### Community 253 - "docs/history: learnings + build_state"
Cohesion: 0.09
Nodes (25): Data sources table (Odds API, SBR, MLB Stats API, Savant, Open-Meteo, NHL API, nba_api, ESPN, UFC CSV mirror, DataGolf), FanGraphs / pybaseball removed (IP-blocked); replaced by MLB Stats API + Savant, MLB_Basic.csv datawarehouse (2009-2025, 40,996 games; runline derived as -1.5), What's built (package tree) and what's not, AlphaPy rejected (deprecated, team-level only, defunct connectors), Team stats need at least 10 games before they stabilize, The go-live gate prevents going live on lucky backtests, Historical team-stat backfill uses {season}-01-01 as as_of_date (+17 more)

### Community 257 - "Prop markets and odds provider research"
Cohesion: 0.16
Nodes (18): scripts/nfl_prop_ladder_grade, scripts/verify_kalshi, Alternate coverage effectively begins in 2024, Anchored ladder graded: fails every clause, Provider comparison: Odds API, Kalshi, SportsGameOdds, OddsJam, Unabated, OpticOdds, 1.48M alternate-market rows already stored and unread, Kalshi (CFTC-regulated event contracts), Status: deferred, no code (as of the memo) (+10 more)

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

### Community 402 - "NFL prop and in-play research notes"
Cohesion: 0.11
Nodes (13): The live prop market leans over like the pre-game one, Publish backstop refuses pass-attempt overs, Accrued carries from ESPN core leaders, rush_attempt_pace model: one offset on the book's number, Pace ratio, In-play rushing-attempt UNDER on pace ratio >= 1.25, NFL prop lines lean over, NFL edge search 2026-10-11 (+5 more)

### Community 407 - "docs/live_odds_freshness.md"
Cohesion: 0.16
Nodes (14): Basketball Daily Ingest stays on Matt's PC, DraftKings direct needs BOTH a browser fingerprint and a residential address, The feed has a ~45s floor and it cannot be bought past, The Odds API in-play feed is a ~45-67 s cache, Direct book feeds from both addresses (book_direct_probe.py), data/ingestors/dk_direct_feed.py (RUN_DK_DIRECT_FEED defaults 0), DK direct: fingerprint AND address are both necessary, config.live_slate_dates() — the midnight blind spot (+6 more)

### Community 420 - "mobile/docs/UX_REVIEW.md"
Cohesion: 0.16
Nodes (13): dashboard.html renderRoster(), A pick is a pick (re-priced line never replaces the locked one), Copy: formatAmerican/formatPct/formatCurrency, model ids never raw, Decided at the best bettable price; read via lib/decisionPrice.ts, frontend-ux-designer agent contract, Mobbin MCP connector (one route: Matt's claude.ai connector), Product rules: a violation is a Blocker, Reuse before invention (EmptyState, StatTile, SignalBadge, ...) (+5 more)

### Community 432 - "Model quality monitor and MLB totals docs"
Cohesion: 0.11
Nodes (18): Hybrid Pin-agreement filter on mlb_over_under bets, mlb_runline and mlb_over_under (paused), mlb_total_public_fade card (paper UNDER), Slate concentration guard (insert-time), F5 odds coverage (DK carries F5 ML only), clv_degradation check, model_quality_checks table, Daily model-quality monitor (+10 more)

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

### Community 558 - "Model artifact integrity and health docs"
Cohesion: 0.24
Nodes (10): model_artifacts_load counts what it opened, model_artifacts table fallback restore, Three separate artifact questions, three separate failures, KNOWN_UNTRAINED — config models intentionally without artifacts, Pipeline-observability checks: refresh_pass_completion, refresh_pass_steps, signal_delivery, pick_label_integrity, pipeline_runs — the run ledger (tracking/run_ledger.py), Retrain Model workflow (retrain_model.yml), tracking/system_health.py — CRIT and WARN feed checks (Step 12) (+2 more)

### Community 560 - "docs/retrain_2026_plan.md"
Cohesion: 0.17
Nodes (13): scripts/paused_model_assessment, data.ingestors.baseball_savant_ingestor, models.trainer, #215 artifacts could not be deserialised, F5 O/U and F5 RL paused: leak-mismatched, synthetic-line trained, NCAAF in-play season replay: -3.4% and -13.1%, No model has a cut that clears on the deployed artifact, batter_sb: opp_team_sb_allowed feature (+5 more)

### Community 594 - "Probability calibration documentation"
Cohesion: 0.24
Nodes (14): models/honest_ev.gate and honest_probability, tracking/system_health._report_model_calibration, MODEL_OWN_EV_FLOOR and MODELS_ON_OWN_PROBABILITY for wind and opener, fetch_graded reads picks for NFL/NCAAF/UFC/rule models, GLOBAL_MIN_EV: 0.30 then 0.20, The go-live calibration gate never computed a real number, ncaaf_over_under Platt map demoted 2026-09-26, Per-model floors (#796) measured on the calibrated number (+6 more)

### Community 598 - "NCAAF model search plan and findings"
Cohesion: 0.18
Nodes (5): scripts/ncaaf_search/, CollegeFootballData (CFBD) as primary source, ncaaf_spread / ncaaf_over_under / ncaaf_moneyline, NCAA Football model build plan, NCAAF model search findings (2026-08-25)

### Community 603 - "docs/reviews/2026-09-07-nfl-props-deep-dive.md"
Cohesion: 0.33
Nodes (7): Twelve artifacts committed from a replica failed pickle.load unnoticed for two weeks, The eleven NFL projection prop models, unpaused on placeholder thresholds, nfl_prop_market: the de-vig rule (Pinnacle as truth, equal lines only), The scorer is pinned to today, the card looks ten days ahead, 112 bets on one Sunday from untuned models; 41-46% BET rates are placeholders, Eleven NFL distributional props paused 2026-09-14, NFL props deep dive — two lanes, one of them can't see the slate (2026-09-07)

### Community 623 - "All-model state assessment snapshot"
Cohesion: 0.11
Nodes (8): roi_collapse check, mv_scored_pick_outcomes (sweep matview), Official live date 2026-09-01, Retool port of Models and Ops, v_public_track_record (published record view), docs/followups.md, MLB pick volume efficiency assessment, Model state assessment, all 71 models (2026-09-03 snapshot)

### Community 627 - "docs/market_coverage.md"
Cohesion: 0.36
Nodes (7): ncaaf_prop_odds_ingestor and its probe, test_the_mlb_board_and_the_mlb_pull_are_one_set, MLB probe 2026-09-05 — served, unsupported and unpriced keys, NCAAF prune — FOOTBALL_MARKET_NOT_PRICED per league, scripts/probe_market_coverage.py — one market per call, writes nothing, Neither prop ingestor writes to api_call_log, Prop market coverage — what the feed actually serves

### Community 652 - "(root): pr-ci + requirements"
Cohesion: 0.33
Nodes (5): Mobile thresholds drift check (generate_mobile_thresholds --check), NFL preflight --ci, PR CI workflow — non-integration pytest subset, Render blueprint — betting-scheduler background worker, requirements.txt — >= pins for Python 3.14 wheels

### Community 66 - "NFL props sources and prediction market research"
Cohesion: 0.07
Nodes (32): scripts/nfl_prop_market_card, scripts/nfl_prop_replay, anytime_td verdict: inert, not losing, DraftKings de-vigged price sits above realised over-rate, tackles_assists +21% is a measurement error (control), Walk-forward re-fit 2023-2025 (-4.32% over 1,554 bets), Traps specific to props, Anytime TD field de-vig: closed (+24 more)

### Community 688 - "NFL wind totals runbook and staking"
Cohesion: 0.36
Nodes (7): DOCUMENT STATUS block: superseded claims indexed, Under rate by forecast lead 1-7 (~0.41pp per day), Original staking: 25% Kelly capped at 3% (superseded), Kelly-proportional units with slate shading 1/sqrt(1+(k-1)rho), Stops: 2 units per bet, 3 units per slate, review at -15 units, Runbook: Wind Totals, scripts/stake_sizing.py: 1 unit = 1% of bankroll

### Community 691 - "Opening-signal shadow track design"
Cohesion: 0.43
Nodes (7): tracking/opening_signals.capture_opening_signals, tracking.opening_report, tracking/opening_signals.settle_opening_signals, opening_signals table, Opening-signal shadow track, Worker migrations sweeping voided captures, Opening-signal shadow track

### Community 710 - "mobile/docs/BILLING.md"
Cohesion: 1.00
Nodes (4): useEntitlement() access gate (subscription OR Discord), useSubscription() subscription-only state, useEntitlement(), not useSubscription(), Access is one gate: useEntitlement(), never useSubscription().entitled

### Community 720 - "docs/testing.md"
Cohesion: 0.67
Nodes (3): PR CI runs a non-integration pytest subset, Pure function tests, in-memory SQLite via conftest, Test suite (testing.md)

### Community 755 - "Analysis protocol and backtest notes"
Cohesion: 0.17
Nodes (7): Live inning gate replay, mlb_live_total_runs (in-play total), Negative-binomial (NB1) tail, pregame_total_line feature (market anchor), Live tuning panel (Models view), ncaaf_live_total 2025 in-play backtest, Halftime second-half lines, out of sample at real prices

### Community 81 - "docs: nhl_market_lab + nhl_clv_ev_assessment"
Cohesion: 0.09
Nodes (37): nhl_research worker job, scripts/nhl_derivative_totals_backtest, data/ingestors/nhl_derivative_odds_history, models/nhl_props.py (Spec per market), Anytime goalscorer: not a candidate once names corrected, nhl_moneyline and nhl_moneyline_regulation: no cut clears, Game models: lock later? Refuted, The overnight pass takes the night's slots (+29 more)

### Community 857 - "Cross-book opener search findings"
Cohesion: 0.22
Nodes (4): ncaaf_live_win_prob 2025 in-play backtest, Cross-book opener signal (DK vs Bovada), prune_odds keeps the earliest snapshot per proposition, Late-game leader moneyline at DraftKings

### Community 890 - "docs/game_injury_gate.md"
Cohesion: 0.40
Nodes (5): ESPN core probables for the NHL starting goalie, A NONE from this gate is not locked — the reprice path, The gate rule — refuse a game-model BET on a confirmed Out starter/star/goalie, Fires in scorer.score_game and _score_nhl_3way, after best-price requalify, before insert, Game-model starter / star / goalie gate

## Ambiguous Edges - Review These
- `Claim: the app cannot write to the backend` → `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`  [AMBIGUOUS]
  docs/privacy.html · relation: conceptually_related_to

## Knowledge Gaps
- **105 isolated node(s):** `RFC-4122`, `expo/tsconfig.base`, `@babel/core`, `babel-plugin-module-resolver`, `babel-preset-expo` (+100 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 12207 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **198 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Table` connect `NBA public splits pipeline step` to `mobile/scripts/verify_contrast_tokens.ts`, `Scratch Postgres migration test harness`?**
  _High betweenness centrality (0.232) - this node is a cross-community bridge._
- **What connects `RFC-4122`, `expo/tsconfig.base`, `@babel/core` to the rest of the system?**
  _105 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Mobile app screens and theme` be split into smaller, more focused modules?**
  _Cohesion score 0.01667634490254761 - nodes in this community are weakly interconnected._
- **Why does `over()` connect `mobile/scripts/verify_contrast_tokens.ts` to `Mobile bankroll storage and settings card`, `NBA public splits pipeline step`?**
  _High betweenness centrality (0.204) - this node is a cross-community bridge._
- **Should `Discord pick and live signal notifier` be split into smaller, more focused modules?**
  _Cohesion score 0.020062096966802005 - nodes in this community are weakly interconnected._
- **Why does `inserted_minus_start_min()` connect `NBA public splits pipeline step` to `NBA public betting splits ingestor`, `NBA public splits parsing tests`?**
  _High betweenness centrality (0.125) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Claim: the app cannot write to the backend` and `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._