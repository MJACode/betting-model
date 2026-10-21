# Graph Report - bm-nba-s5  (2026-10-20)

## Corpus Check
- Large corpus: 1628 files · ~2,709,967 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 32508 nodes · 77654 edges · 943 communities (736 shown, 207 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 2009 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7aa5060b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Mobile app shell, push and sharp score
- Mobile picks home filters and sorting
- Mobile stats board
- NBA player prop model fitting
- NBA book numbers and game four search
- Best line price shopping tests
- NBA totals luck model decision tests
- tests/test_nfl_live_leader_gameday.py
- NFL in-play leader gameday runner
- tests/test_calibration_promotion.py
- tests/test_score_off_any_book_line.py
- Mobile lines board and all books sheet
- tests/test_ncaaf_alias_scores.py
- Alternate prop line fetching tests
- tests/test_backtester.py
- NFL in-play gameday worker loop
- NBA prop market lab
- Discord pick notifier tests
- nfl/live_model/tests/test_backup_snaps.py
- Prop ladder from books and Kalshi
- mobile/scripts: verify_book_links + verify_betslip_combine
- NBA team total under model tests
- X post queue drain tests
- NFL prop Kalshi pricing
- Pick lock survives settlement tests
- NBA game line move study
- Market-relative devig and MLB game market
- Discord full record correction posts
- X post publisher tests
- Threshold review and scorer tests
- Publish key identity tests
- UFC phantom fight filter
- Prop box score backfill
- NBA game model prop feature tests
- One-off data pull and asset scripts
- Discord void notice sender
- NFL prop odds sliced loader
- NFL opener signal tests
- NHL stats and game log ingestion
- Mobile crash logging
- NBA game model luck feature tests
- Discord publisher run lock
- tests/test_dk_direct_feed.py
- tests/test_credit_budget.py
- Odds prune budget tests
- X profile update queue
- Sharp book odds retention on prune
- NHL blocked shots prop card
- tests/test_first_signal_repair.py
- Prop price pregame cutoff tests
- Mobile markets and formatting
- Model calibration sweep tests
- NHL goalie starters as of date
- NFL in-play game state feed
- Mobile color contrast checker
- CLV deciding price grading tests
- Mobile record hero and equity curve
- Mobile paywall billing and account access
- Mobile bankroll number formatting checks
- Idle database read transaction tests
- NHL market-anchored moneyline model
- In-play score change quote guard
- Monitor dashboard probe and cache tests
- tests/test_db_reconnect.py
- Discord recap restatement
- In-play scorer locks and push alerts
- NHL blocked shots prop model
- tests/test_refresh_retry.py
- NBA results ingestion and prop settling
- NBA results ingestor tests
- NBA second game projection engine
- tests/test_local_cache_is_additive.py
- tests/test_calibration_check_coverage.py
- NFL in-play odds client smoke check
- tests/test_book_team_map.py
- tests/test_team_board_cache.py
- NCAAF feature engine and targets
- Minimum odds price floor checks
- NFL wind board fast publishing tests
- NBA fifth search period shares
- NFL in-play odds history purchase
- MLB weather forecast ingestor
- NHL team rates as of date
- tests/test_dk_freshness_parse.py
- NHL moneyline rebuild and grading
- models: slate_concentration + test_slate_concentration
- View migration lock handling tests
- Discord pick notifier price fields
- NBA total luck card publishing
- Mobile performance and tracked bets
- NHL season labels and opening week
- NBA game four point estimates
- Best line threshold sweep
- NCAAF college data ingest tests
- Mobile bet slip and parlay legs
- NBA pregame scoring window
- NCAAF in-play bet lock and serving
- tests/test_prop_odds_utc_stamp.py
- Live monitor web server streaming
- NBA game harness tests
- NCAAF opener strategy search
- tests/test_feature_artifact_agreement.py
- NFL prop one side per line
- Closing line value math
- tests/test_cloud_retrain_artifacts.py
- NHL side models never bet against each other
- Odds prune frontier and retries
- System health and deliverability checks
- Player news feed ingestion
- Prop player name matching
- Discord and X results posting
- MLB batter prop log scoring tests
- tests/test_nfl_wind_publisher.py
- Pre-game odds and prop odds ingestors
- NFL in-play prop polling tests
- tests/test_health_reason_and_cadence.py
- NBA odds history gap fetching
- tests/test_nfl_weather_supabase_readback.py
- Publish signals on write tests
- Pitcher stats as-of invariant tests
- NBA prop market tip timing
- NFL in-play feed resilience tests
- Pipeline log reason tests
- NFL in-play remaining-yards engine training
- NBA in-game study two
- NFL opener and wind writer lock tests
- NFL team game rows parsing
- NBA prop fetch window planning
- NFL opener pick builder tests
- NHL player prop projection model
- Pregame line poller key map seeding
- Health check skip budget tests
- tests/test_live_pick_features.py
- Model quality detectors and tests
- tests/test_prop_missing_features.py
- Pregame snapshot first pitch guard
- NCAAF FBS registry health checks
- NFL in-play pick writer tests
- NCAAF live state recording tests
- tests/test_run_ledger_orphans.py
- NFL opener and NCAAF calibration tests
- NBA lineup stints from play-by-play
- In-play calibrated decision tests
- Team total market decision tests
- Game-level star injury gate
- Pregame game scorer and best price
- NFL in-play leader game state
- NCAAF opponent-adjusted search features
- Any-book first five line scoring
- tests/test_repair_bogus_first_pitch_labels.py
- nfl/live_model/tests/test_executor.py
- tests/test_sbr_loader.py
- Walk-forward evaluation
- mobile/scripts/ux_scan.mts
- Pick settlement and self-healing grading
- Mobile player stats and game log
- Free pick card and X results tests
- tests/test_live_quote_staleness.py
- NBA prop closing line purchase tests
- NBA prop settlement stats tests
- In-play publish parity with pauses
- CLV backfill job tests
- NBA injury report storage tests
- supabase/functions/_shared/discord.ts
- Worker job queue validation tests
- NFL in-play pick writer
- Pre-game price age and NHL totals
- NFL DraftKings line snapshots
- Database schema setup and splitting
- Schema guard and table lockdown
- tests/test_discord_channel_probe.py
- tests/test_nfl_prop_one_read_per_game.py
- Bounded odds prune retry tests
- ESPN injury team lookup fallback
- NCAAF gameday live odds cadence
- Multi-book odds ingestion
- scripts/nfl_edge_gameline_rules.py
- System health check pass tests
- tests/test_model_game_savepoint.py
- Health check pick delivery tests
- NBA SBR odds archive importer
- NFL prop feature and walk-forward scripts
- NFL prop count and yardage distributions
- tests/test_calibration_watch.py
- NCAAF in-play odds history backtest
- NFL weather history fetcher
- Model performance monitor tests
- In-play pregame total anchor tests
- Pipeline failure alerting and heartbeats
- NCAAF starter-out research dataset
- NFL in-play leader win probability
- Mobile bankroll storage
- Score when lines open tests
- tests/test_sbr_loader.py
- NHL totals market model and card
- Mobile app screens and theme
- NHL prop settlement tests
- Member sportsbooks scratch database tests
- tests/test_mobile_stat_labels_match_the_server.py
- tests/test_nhl_three_way_lookahead.py
- Mobile team stats screen
- NBA injury report daily runs
- Prop scorer next-day lookahead tests
- External threshold map promotion
- System health run ledger tests
- In-play best line price tests
- tests/test_sbr_loader.py
- NCAAF college data refresh and backfill tests
- UFC fight stats ingest tests
- Mobile data queries and pick types
- NFL live leader cut and price floor
- NBA team total odds fetch tests
- Model training and prop features
- tests/test_void_picks.py
- tests/test_sbr_loader.py
- MLB final score twin lookup
- NBA team total odds fake database
- Job heartbeat and stale jobs
- NCAAF gameday context twin rows
- NFL prop backtest verdict tests
- MLB duplicate game id merge
- NBA box score repair tests
- Health check daily feed freshness
- tests/test_sbr_loader.py
- tests/test_daily_retry.py
- Results recap message id tests
- X image upload and tweeting
- NFL prop market card publisher tests
- Odds repeat thinning keeps NBA rows
- NFL weather and opener cards
- tests/test_live_book_move_guard.py
- NHL player props card tests
- NFL pick monitor game id join
- tests/test_sbr_loader.py
- Umpire ingest and script utilities
- NFL pick monitor
- In-play game clock alignment
- Discord and X results notifier
- Prop odds missing game insert tests
- NHL blocked shots prop settlement tests
- System health check test fixtures
- Mobile model catalog and thresholds
- Team stats live season span checks
- supabase/functions/revenuecat-webhook/index.ts
- supabase/functions/whop-webhook/index.ts
- NFL pick evaluation and monitor
- tests/test_nfl_props.py
- NFL wind and opener publisher
- tests/test_sbr_loader.py
- Football in-play game state
- Price prefilter timeout rollback tests
- NFL prop local odds cache
- Market sweep and holdout scripts
- tests/test_nfl_props.py
- Mobile matchup and stats verify scripts
- NFL wind bettable book filter
- NFL prop settlement tests
- Mobile bankroll unit percent settings
- Poller leaves prop rows alone
- NBA official injury report parser
- Social post enqueue checks
- NBA public splits late-game archiving
- Scorer pick signal classification tests
- tests/test_game_market_gate.py
- NBA team total closing line tests
- NHL prop EV regimes and Kalshi ladders
- NBA public splits quality backfill
- Pipeline watch findings and alerts
- NFL prop market card tests
- NBA second-model prop study
- tests/test_score_when_lines_open.py
- Scorer injury flag tests
- Probability calibration map tests
- Bounded odds pruning and thinning
- tests/test_pick_integrity.py
- NHL derivative totals card tests
- Paused bets keep real verdict tests
- NHL prop newest fetch shopping tests
- Calibration schema column tests
- Database connection and feature builders
- tests/test_record_one_pick_per_event.py
- NFL odds event game matching
- Weekly job catch-up tests
- Shared database connection and sweeps
- Pipeline report rollback tests
- First signal repair test fakes
- NFL evaluation rows carry quoted line
- nfl/live_model/tests: test_props + props
- One NHL prop bet per game
- Prop board fake connection for tipoff
- NFL prop player name matching
- Deploy checks and job queue
- tests/test_wnba_prop_market.py
- tests/test_nfl_scored_rows.py
- NHL derivative totals walk-forward model
- NFL prop placebo projection tests
- NBA prop cards across models
- Prop odds book update time
- tests/test_recap_retries_a_skipped_day.py
- Game-day workers and shared stdlib
- NFL injury index loader
- NFL prop pulls and recap error tests
- MLB bet record audit tally
- Live state poller dry-run connection
- NFL prop no-vig price math tests
- Scorer feature value encoding
- NFL live leader evaluation cadence
- NFL opener card and model split
- NFL opener fire window tests
- NHL prop count distribution tests
- Pregame price freshness health tests
- Dead NHL API import removal
- NFL player stats and props ingestion
- NHL player props scoring card
- NBA prop market decision tests
- X tweet delivery attempt
- Push-adjusted win probability
- NBA injury report date scope
- Future game price gate tests
- Score when lines open window tests
- Social post test database stub
- NFL early-signal publishing tests
- NFL live leader fake clock
- NBA team total odds billed feed stub
- NFL live leader fake rows
- NHL blocked shots prop settlement
- Savant freshness health check tests
- Odds poller creates missing games
- WNBA injury adjustment features
- UFC stats ingestor tests
- Weekly catch-up cursor stub
- tests/test_ncaaf_prop_odds.py
- MLB opposing starter feature tests
- MLB totals public fade model
- NCAAF in-play score distribution pricing
- tests/test_ncaaf_pbp_store.py
- tests/test_heartbeat_watchdog.py
- NCAAF in-play quote selection engine
- Record correction social posts
- Pipeline run start and orphan cleanup
- NFL edge research shared helpers
- NBA second game market fair prices
- scripts/nfl_edge_live_rush_pace.py
- NBA prop projection tests
- NFL preregistered 2026 edge study
- tests/test_prop_calibrated_decision.py
- NBA fourth search derivative markets
- tests/test_mobile_line_movement.py
- In-play calibration analysis
- NBA in-game luck study one
- NBA lineup stint derivation tests
- NBA play-by-play parsing tests
- tests/test_ncaaf_live_notify.py
- NCAAF quarterback team features
- NHL prop backtest shared-name guard
- Live monitor dashboard data store
- NBA fifth search grid tests
- tests/test_settled_record_is_immutable.py
- features/golf_feature_engine.py
- NCAAF in-play state building tests
- tests/test_bovada_feed.py
- NCAAF cross-book opener tests
- NFL 2024 in-play totals grading
- tests/test_paused_keeps_real_verdict.py
- NFL 2025 in-play edge research
- tests/test_health_pregame_prices_current.py
- NBA stats and player log ingestion
- scripts/nfl_edge_extreme_props.py
- scripts/nfl_edge_settlement.py
- tests/test_agents_contract.py
- NFL prop market information tests
- WNBA results ingestor
- NBA public betting splits ingestor
- NBA box score enrichment
- NBA derivative market lab
- scripts/nfl_preflight.py
- Mobile live board segment tests
- NBA halftime in-game research
- Ops alert watchdog and state
- MLB stats and pitcher ingestion
- tests/test_decide_on_calibrated.py
- NBA prop projection lab
- NBA team total luck card
- MLB game market betting card
- NBA in-game data staleness gate
- tests/test_model_artifacts_load.py
- Mobile pick button and player detail tests
- scripts/game_line_market_sweep.py
- Push notification deep link tests
- tests/test_pass_instrumentation.py
- tests/test_db_adapt_sql.py
- Market-relative prop bet finder tests
- NFL prop injury veto
- tests/test_mobile_contrast_tokens.py
- Monitor probe HTTP call recording
- Daily pipeline runner and step imports
- NBA game four part one tests
- Pregame line poller change detection tests
- NBA second game line move tests
- NBA team total luck builder
- NFL in-play prop flow anchoring tests
- NBA second game verdict
- Probability calibration fitting and sweep
- NCAAF in-play pricing engine
- tests/test_nfl_live_leader_state.py
- tests/test_ncaaf_qb_ingestor.py
- DraftKings feed freshness probes
- NHL period scores ingestor
- nfl/live_model/tests/test_rush_attempt_pace.py
- tests/test_ncaaf_game_identity.py
- NBA second game market tests
- Live monitor stale cache
- NBA game model research harness
- MLB in-play inning gate replay
- Kalshi prop ladder recording tests
- UFC results download caching
- Prop market coverage probe tests
- WNBA stats and game log ingestion
- UFC fight feature builder
- Injury fetch athlete name cache
- NBA quarter game model tests
- NBA second game luck study
- No-vig capture and entrypoint guards
- Line CLV sign and orientation tests
- UFC fight results scraper
- NFL in-play flow slice backtest
- Weekly and monthly results recap timing
- Model calibration check tests
- MLB live game state poller
- NCAAF college data ingestor
- NFL prop pulled quote filter
- Historical odds backfill tests
- NCAAF player stats parser tests
- scripts/nfl_live_prop_feasibility.py
- tests/test_context_budget.py
- tests/test_player_h2h_stat_values_migration.py
- tests/test_retired_models.py
- NFL in-play flow pseudo CLV tests
- Threshold and EV floor replay sweeps
- Scratch Postgres latest line tests
- tests/test_live_record_start_views.py
- UFC historical CSV loader
- Discord price bound tests
- Mobile team detail page tests
- NHL prop odds fetch gate
- NFL Kalshi edge search
- nfl/models/opener_spread.py
- nfl/live_model/feeds: test_feed_resilience + espn
- tests/test_nfl_wind_fire_window.py
- Build your own model NFL facts
- tests/test_public_betting_ingestor.py
- Basketball player positions ingestor
- tests/test_service_role_split.py
- Prop ladder and NBA derivative tests
- API call log daily rollup tests
- MLB over under retrain sweep job
- Mobile sport filter persistence tests
- Custom model game facts tests
- NBA second game projection tests
- Live slate midnight date discovery
- NFL in-play flow bias validation
- Custom model season facts loader
- Intraday weather and news freshness
- In-play count tail dispersion tests
- NBA period map pricing tests
- Prop box score cooled refill
- NCAAF CFBD ingestor tests
- Mobile screen source wiring tests
- Kalshi game market recorder
- HTTP request timeout floor
- CLV price taken app parity tests
- UFC results scraper tests
- NCAAF totals probability regression tests
- NCAAF search team and QB matrix
- Refresh pass step ordering tests
- First pitch time trust tests
- Game injury veto gate
- Mobile bankroll screen checks
- tests/test_mobile_threshold_parity.py
- NHL derivative odds job validation tests
- tests/test_track_record_views.py
- tests/test_weekly_catch_up.py
- Mobile team total line tests
- NFL weather cache importer
- Mobile bankroll settings card
- NFL live leader model tests
- Mobile paused catalog tests
- NCAAF opener board visibility tests
- MLB play-by-play and in-play history
- tests/test_promote_calibration_job.py
- tests/test_cfbd_snapshot_leakage.py
- NFL wind forecast stability tests
- NFL edge research local cache
- NFL in-play prop assessment report
- NFL prop threshold window tests
- tests/test_nhl_research_job.py
- tests/test_settlement_timing.py
- NBA schedule rest and travel features
- Push delivery ticket parsing tests
- DataGolf ingestor and NHL SBR archive
- Mobile tests run through node
- NBA prop decisions ledger guard test
- NFL odds cache import to Supabase
- tests/test_health_check_observe.py
- NFL in-play prop flow model
- NFL 2026 opener and wind tracker
- NFL in-play prop line churn check
- NBA totals luck fetch window tests
- tests/test_pick_lock_is_on_picks.py
- Sub-ten-second live odds path tests
- NFL in-play prop rule and staleness reports
- Per-model threshold config tests
- NBA game two verdict grid tests
- Worker retrain and sweep jobs
- scripts: build_nfl_live_leader_artifact + model
- Mobile player stat groups tests
- NBA public splits game dating
- supabase/functions/discord-link/index.ts
- tests/test_nfl_prop_clv.py
- tests/test_scoring_methods.py
- Team stats impossible games played checks
- Worker job queue runner
- Anon read access sweep tests
- nfl/scripts/backtest_opener.py
- Paused model profitability assessment
- NCAAF totals lead and consensus gate
- tests/test_latest_odds_views.py
- NBA schedule ingestor
- tests/test_transaction_pooler.py
- Env file database URL fallback
- Paused and no-signal pick rows tests
- MLB play-by-play ingestor
- MLB runline feature type coercion
- Database URL doctor
- supabase/functions/sharpsports/index.ts
- Rule model market reading tests
- tests/test_worker_deps.py
- Discord publish keys and push notifier
- scheduler.py
- First pitch posting guard tests
- Team stats snapshot invariant tests
- tests/test_ncaaf_fcs_visitor_names_migration.py
- tests/test_nfl_prop_unstarted_clear.py
- Multi-sport model research labs
- tests/test_scorer_nfl_prop_like_escape.py
- Published record views reconciliation
- NHL stats views tests
- Trainer no-register mode tests
- NHL game results parser
- Social post transport error tests
- Market movement feature builder
- Team stats rebuild row tests
- NCAAF margin evaluation and weather totals
- Anon grant apply script
- ESPN NHL probable goalies
- tests/test_clear_unauthorized_auto_pauses_migration.py
- tests/test_ncaaf_se_louisiana_alias_migration.py
- tests/test_overnight_polling.py
- NFL stale daily card clearing
- NFL EV engine and stake sizing
- Mobile type-check baseline tests
- Kalshi game market ingestor
- NFL prop over-lean concentration study
- X team hashtags
- Results recap backfill command
- tests/test_claude_rules_split.py
- tests/test_db_setup.py
- tests/test_dedupe_opening_signals.py
- NBA injury report snapshot writer
- tests/test_pbp_backfill_resilience.py
- Pregame line change detection
- In-play bet uniqueness index tests
- NFL wind forecast lead calibration
- NCAAF quarterback ablation study
- NBA injury report slot schedule
- NBA in-game study one tests
- NFL model import path tests
- NBA public splits pipeline step
- tests/test_prompt_reads_thresholds.py
- tests/test_system_health_meta_steps.py
- NCAAF situational spot evaluation
- NBA period score ingestion
- Social post queue and drain
- scripts/render_brand_icons.py
- NCAAF search QB feature merge
- Results recap NFL box score ordering
- NBA prop model verification stages
- supabase/functions/stripe-webhook/index.ts
- tests/test_drop_voided_nfl_wind_opening_signals_migration.py
- Ungraded model performance tests
- tests/test_mobile_neutral_signal_label.py
- College football data checks
- Worker-only table lock-down SQL
- tests/test_scorer_commits_per_game.py
- NBA ESPN box score parsing
- NFL paid odds cache import
- Declared worker job validation tests
- tests: test_wnba_availability + wnba_availability
- NFL prop market EV floor study
- NCAAF starter-out study grading
- Mobile NHL today look-ahead tests
- supabase/functions/sharpsports-webhook: index + index
- Mobile Lines board pin tests
- X social pick publisher
- supabase/functions/stripe-checkout/index.ts
- tests/test_book_list_budget.py
- Mobile type-check baseline checker
- NBA game market search lab
- Monitor probe call instrumentation
- UFC fight page parsing
- Pipeline signal push and opening capture
- Baseball Savant capture date stamping
- NCAAF weather totals study
- mobile/scripts/verify_a11y.ts
- NCAAF CFBD opener research cache
- NHL totals research lab
- NFL in-play prop dataset and calibration
- Yesterday Discord units parity tests
- tests/test_demote_ncaaf_over_under_platt.py
- tests/test_discord_post_one_pick_migration.py
- tests/test_game_scorer_spares_nfl_props.py
- NFL in-play score distribution pricing
- Mobile quiet update download tests
- NBA team total luck replay tests
- MLB in-play game state features
- NCAAF line move spot evaluation
- NHL period goals feed parsing
- Live feed vendor probe
- NBA prop model research lab
- Anon write grant revocation tests
- NFL wind stake past calibration tests
- NBA injury report player matching
- NCAAF scoreboard yardline parsing
- NFL prop kickoff lead ceiling tests
- Repo-wide lock-down call site guards
- Scorer keeps off-DraftKings priced bets tests
- Historical odds file loader
- Build your own model facts schema
- NFL prop market opening signal cleanup tests
- UFC event list date parsing
- UFC fighter page parsing
- Every named sportsbook is fetched
- App-readable relation manifest checks
- NBA injury report write retry
- NFL prop backtest universe summary
- NCAAF in-play DraftKings gate tests
- NHL regulation moneyline own probability
- First-time database setup
- Discord units won settlement
- Anon grant plan tests
- NFL in-play 2024 replication report
- NCAAF school slug matching
- MLB injury and return ramp ingestor
- Mobile accessibility verify script
- Market handicap feature tests
- mobile/scripts/verify_a11y.ts
- mobile/scripts/verify_a11y.ts
- MLB twin team code leak checks
- Prop CLV and SQL escaping tests
- mobile/scripts/verify_a11y.ts
- Pre-game bound source inspection tests
- NBA injury report name normalising
- ncaaf_live/tests/test_serve.py
- Eggz capper picks Discord recaps
- Per-model EV floor card tests
- Mobile error states and books tests
- In-play trigger orchestrator and daily cap
- NBA public betting splits parser
- Results snapshot pass order tests
- No record-only mode guard tests
- MLB public fade top-k backtest
- NFL QB wind and NBA in-game tests
- NCAAF play-by-play column range scan
- NBA prop pipeline steps
- NHL box score parsing
- Team stats live season skip checks
- Team board commence cutoff tests
- NBA play-by-play clock parsing
- Team stats hist season boundary tests
- Team stats as-of date normalization
- MLB twin alias verification test
- NBA public splits quality flags
- Team stats season label guard
- NBA team total CLV settlement safety
- NFL prop publish skip tests
- mobile/scripts/verify_a11y.ts
- Prop board market coverage invariants
- NHL derivative totals card stub
- NCAAF state build output path
- First signal same bet comparison
- NBA fifth search team rating projections
- Monitoring dashboard test server
- NCAAF in-play backtest state building
- NHL period scores top-up tests
- NCAAF CFBD team game stats parsing
- Weekly catch-up probe rollback test
- NFL in-play model backtest replay
- NBA public betting splits ingestion
- NFL in-play pick announcements
- SQL parameter conversion helper
- Team stats opening night grace
- Discord stale pause empty set alert
- Worker service role split test
- Discord pause quiet logging test
- MLB prop backfill pre-game anchor
- NFL live leader call cap test
- NFL in-play leader EV gate test
- NHL period scores source marker
- NBA public splits side flip
- Restore first signals pipeline step
- NBA public splits preseason skip test
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
- NBA play-by-play stints guide
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
- docs: nhl_market_lab + nhl_clv_ev_assessment
- Member sportsbooks migration
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
- Model search findings and protocol docs
- nfl/live_model/README.md
- docs: followups + clv
- docs: best_line + config_topology
- docs/history: learnings + build_state
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
- Performance monitoring and record views docs
- docs/sports: ufc + golf
- mobile/docs/BILLING.md
- NFL model bundle restore guide
- .claude/agents: frontend-ux-designer + CLAUDE
- .claude/rules/picks-and-publishing.md
- .claude/rules/model-updates.md
- NFL in-play prop assessments docs
- docs/signal_timing.md
- NFL stat prop method search docs
- mobile/docs/DISCORD_LINKING.md
- Probability calibration design notes
- docs/live_betting.md
- docs/sports/wnba.md
- mobile/docs/AUTHENTICATION.md
- .claude/rules/frontend.md
- Model artifact and retrain docs
- docs/retrain_2026_plan.md
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
- In-app feedback replies runbook
- docs/game_injury_gate.md

## God Nodes (most connected - your core abstractions)
1. `get_connection()` - 645 edges
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

## Communities (943 total, 207 thin omitted)

### Community 17 - "Mobile app shell, push and sharp score"
Cohesion: 0.02
Nodes (154): AppErrorBoundary, IoniconName, NavRef, PushState, PushStatus, ForcedOnlyReason, PushDiagnosis, PushFailureReason (+146 more)

### Community 0 - "Mobile picks home filters and sorting"
Cohesion: 0.02
Nodes (218): P, Props, Props, BacktestPickRow, DateOption, DayRow, SelectableGame, CountInput (+210 more)

### Community 1 - "Mobile stats board"
Cohesion: 0.01
Nodes (379): P, TouchSet, ActivePill, Props, Sport, AnytimeMatchupView, AnytimeSortRow, DefenseRank (+371 more)

### Community 10 - "NBA player prop model fitting"
Cohesion: 0.03
Nodes (79): Spec, compact_report(), minutes_cols(), predict_means(), rate_cols(), alias_key(), all_rates(), apply_calibration() (+71 more)

### Community 105 - "NBA book numbers and game four search"
Cohesion: 0.06
Nodes (41): Point, even_gap(), ladder_mask(), main_rungs(), _one_rung(), split_main_rungs(), visible_numbers(), _american() (+33 more)

### Community 108 - "Best line price shopping tests"
Cohesion: 0.06
Nodes (31): FakeConn, TwoOrientationConn, _best_game_price(), _best_of(), _source(), test_a_better_price_at_a_different_total_is_not_the_same_bet(), test_a_better_price_at_the_same_total_wins(), test_a_book_can_only_be_offered_if_it_is_also_fetched() (+23 more)

### Community 11 - "NBA totals luck model decision tests"
Cohesion: 0.03
Nodes (64): Decision, TotalLuckBet, _Conn, _Cur, decide(), pricing_dist(), quote_frame(), scheduled_games() (+56 more)

### Community 113 - "tests/test_nfl_live_leader_gameday.py"
Cohesion: 0.10
Nodes (27): FakeConn, FakeFeed, art(), live_state(), quote_payload(), _run_loop(), test_a_failed_odds_fetch_backs_off_instead_of_calling_every_tick(), test_a_game_with_a_bet_from_an_earlier_process_is_not_rebet() (+19 more)

### Community 114 - "NFL in-play leader gameday runner"
Cohesion: 0.09
Nodes (18): GameContext, build_pick(), evaluate(), is_locked(), load_context(), main(), _conn(), _parse_ts() (+10 more)

### Community 115 - "tests/test_calibration_promotion.py"
Cohesion: 0.07
Nodes (26): FakeConn, eligibility_clause(), load_calibrations(), maps_materially_differ(), promote(), _payload(), _row(), test_a_broken_table_is_identity_maps_not_an_exception() (+18 more)

### Community 116 - "tests/test_score_off_any_book_line.py"
Cohesion: 0.08
Nodes (33): _FakeConn, _fallback_line_quote(), _cut(), _on(), _pick(), _row(), _sql_const(), _src() (+25 more)

### Community 12 - "Mobile lines board and all books sheet"
Cohesion: 0.03
Nodes (107): ManualBet, ManualBetInput, ManualBetResult, LinesMarket, LinesMarkPick, linesMarks, LinesMlMode, LinesOddsRow (+99 more)

### Community 120 - "tests/test_ncaaf_alias_scores.py"
Cohesion: 0.09
Nodes (30): _FakeConn, _FakeCursor, alias_score_updates(), mirror_scores_to_alias_rows(), _cfbd(), _row(), test_a_bare_substring_is_not_an_extension(), test_a_daytime_game_has_no_duplicate_and_is_untouched() (+22 more)

### Community 121 - "Alternate prop line fetching tests"
Cohesion: 0.07
Nodes (27): _Conn, _Resp, alt_markets_due(), _ou(), _parse(), test_a_422_retries_without_the_alternates_before_going_dk_only(), fake_get(), test_a_422_with_no_alternates_still_takes_the_dk_only_retry() (+19 more)

### Community 123 - "tests/test_backtester.py"
Cohesion: 0.07
Nodes (9): TestCalibrationError, TestComputeBacktestSummary, TestEvaluateResult, TestGoLiveGateConstants, TestIterSides, _calibration_error(), compute_backtest_summary(), _evaluate_result() (+1 more)

### Community 125 - "NFL in-play gameday worker loop"
Cohesion: 0.06
Nodes (15): _Q, GamedayWorker, GameTracker, test_a_host_switch_is_alerted(), test_the_worker_self_checks_once_and_alerts_on_a_broken_feed(), test_a_one_sided_quote_is_skipped_rather_than_priced_on_raw_juice(), test_anchor_does_not_match_a_different_game(), test_anchor_matches_on_the_matchup_not_the_event_id() (+7 more)

### Community 129 - "NBA prop market lab"
Cohesion: 0.09
Nodes (44): NBTable, add_units(), assemble(), best_per_key(), boot_ci(), build_quotes(), candidates_from(), choose_floor() (+36 more)

### Community 13 - "Discord pick notifier tests"
Cohesion: 0.02
Nodes (118): _FakeConn, _FakeResult, _Resp, _StampConn, _cand(), _et_now_iso(), _freeze_now(), _live_row() (+110 more)

### Community 131 - "nfl/live_model/tests/test_backup_snaps.py"
Cohesion: 0.09
Nodes (22): _FakeConn, _FakeCur, back_up(), digest(), _flush(), iter_files(), main(), _mb() (+14 more)

### Community 134 - "Prop ladder from books and Kalshi"
Cohesion: 0.06
Nodes (25): Ladder, Rung, _expit(), from_kalshi(), from_one_sided_overs(), _logit(), _monotone(), _ladder() (+17 more)

### Community 135 - "mobile/scripts: verify_book_links + verify_betslip_combine"
Cohesion: 0.06
Nodes (37): betslipCombineKind, combineBetMgm(), combineBetslipLinks(), combineCaesars(), combineDraftKings(), combineEspnBet(), combineFanDuel(), fanDuelPairs() (+29 more)

### Community 14 - "NBA team total under model tests"
Cohesion: 0.03
Nodes (55): TeamTotalDecision, book_ages(), decide(), record(), home_part(), load_artifact(), newest_season(), pricing_dist() (+47 more)

### Community 140 - "X post queue drain tests"
Cohesion: 0.15
Nodes (31): Poster, QueueConn, _blank(), _drain(), _no_network(), test_a_bad_reply_target_fails_without_posting(), test_a_fresh_claim_is_not_posted_again(), test_a_future_row_waits() (+23 more)

### Community 141 - "NFL prop Kalshi pricing"
Cohesion: 0.08
Nodes (15): TestMarketRelative, _bets_from_kalshi(), find_bets(), _zero_vig_american(), _ladder(), test_a_replay_never_prices_off_todays_ladder_even_when_on(), test_fetch_helper_swallows_errors(), test_kalshi_is_not_graded_until_settled_history_exists() (+7 more)

### Community 143 - "Pick lock survives settlement tests"
Cohesion: 0.09
Nodes (21): _SqliteShim, _game(), _pick(), _survivors(), test_a_bet_is_never_dropped_for_an_earlier_no_signal(), test_a_dead_zone_prop_row_locks_too(), test_a_final_game_is_not_a_scoring_target(), test_a_game_with_no_score_is_still_scoreable() (+13 more)

### Community 144 - "NBA game line move study"
Cohesion: 0.07
Nodes (33): Data, attach(), big_home_dog_signal(), consensus(), control_specs(), coverage_text(), fade_side(), favourite_sides() (+25 more)

### Community 146 - "Market-relative devig and MLB game market"
Cohesion: 0.04
Nodes (51): GameMarketBet, _SlateConn, TestNaNIsAbsent, devig(), find_spread_bets(), find_total_bets(), _gap_seconds(), _is_runline() (+43 more)

### Community 149 - "Discord full record correction posts"
Cohesion: 0.06
Nodes (31): LedgerUnread, Conn, delete_custom_record_post(), _jump(), _place(), _publish(), publish_full_record(), publish_full_record_standard() (+23 more)

### Community 15 - "X post publisher tests"
Cohesion: 0.02
Nodes (71): _R, test_a_push_only_period_does_not_invent_an_roi(), test_the_tweet_header_says_restated(), test_allow_link_is_off_on_the_pick_client(), _post(), _afternoon(), _creds_on(), _fake_conn() (+63 more)

### Community 150 - "Threshold review and scorer tests"
Cohesion: 0.04
Nodes (37): _Conn, _DdlConn, _DdlRes, _is_paused(), _quiet(), rule_only(), _slate(), test_a_failed_lock_down_does_not_lose_the_table() (+29 more)

### Community 152 - "Publish key identity tests"
Cohesion: 0.05
Nodes (24): _Conn, _KeyConn, _key(), _mobile(), _sql(), test_a_game_level_live_row_keeps_the_key_it_was_published_under(), test_a_game_level_row_keeps_the_key_it_was_published_under(), test_a_player_id_row_keeps_the_key_it_was_published_under() (+16 more)

### Community 154 - "UFC phantom fight filter"
Cohesion: 0.21
Nodes (6): TestFilterUfcPhantom, TestIsKnownUfcMatchup, _filter_ufc_phantom(), _is_known_ufc_matchup(), _game(), _odds()

### Community 155 - "Prop box score backfill"
Cohesion: 0.09
Nodes (18): GradeConn, ScriptConn, ensure_prop_box_scores(), missing_prop_games(), _pick(), test_a_logged_game_is_not_fetched_and_a_goalie_gap_is(), test_a_non_timeout_prop_error_rolls_back_and_raises(), test_a_probe_error_that_is_not_a_timeout_raises_after_rollback() (+10 more)

### Community 156 - "NBA game model prop feature tests"
Cohesion: 0.06
Nodes (40): _Stop, _box(), _g(), _games(), _inj(), _model(), _props(), _run() (+32 more)

### Community 157 - "One-off data pull and asset scripts"
Cohesion: 0.03
Nodes (40): Puller, _fmt_et_time(), get_conn(), query(), _key(), _ledger(), main(), match_event() (+32 more)

### Community 160 - "Discord void notice sender"
Cohesion: 0.06
Nodes (23): Ledger, TestAPostedVoidAnnouncesAfterCommit, DiscordVoidRejected, announce_posted_voids(), _bind(), _row(), test_a_live_void_still_posts_when_a_pregame_sibling_would_block(), test_a_non_2xx_response_and_a_request_exception_record_nothing() (+15 more)

### Community 162 - "NFL prop odds sliced loader"
Cohesion: 0.06
Nodes (23): _Conn, _Cur, TestPropOddsLoader, _Conn, _Cur, _fetch_slice(), _iter_prop_rows(), load_nfl_prop_odds() (+15 more)

### Community 164 - "NFL opener signal tests"
Cohesion: 0.08
Nodes (14): TestBettableBooksOnly, TestFreshNumberLabel, TestHeldMinutes, TestSelectOpenerBets, _both_sides(), _frame(), _giants_board(), _giants_prior_at_2129() (+6 more)

### Community 165 - "NHL stats and game log ingestion"
Cohesion: 0.04
Nodes (40): TestLogRowBuilders, TestOpeningNightIsEarlySeason, TestNoHollowTeamRowBeforeTheFirstGame, backfill(), build_goalie_rows(), build_skater_rows(), build_team_rows(), _fetch() (+32 more)

### Community 166 - "Mobile crash logging"
Cohesion: 0.09
Nodes (40): CrashContext, CrashLogDeps, CrashReport, ErrorUtilsShape, KeyValueStore, LaunchMarker, LaunchStage, ReportKind (+32 more)

### Community 170 - "NBA game model luck feature tests"
Cohesion: 0.05
Nodes (39): _Stop, _against_bet(), _f6c_inputs(), _games_for_standings(), _gs(), _market_pricing(), _one_game_data(), _pair() (+31 more)

### Community 174 - "Discord publisher run lock"
Cohesion: 0.07
Nodes (17): _Conn, _Result, _clear_locks(), _no_prod_threshold_sync(), _signal_row(), test_a_connection_that_cannot_lock_still_publishes(), test_an_exception_mid_publish_does_not_wedge_every_later_pass(), test_every_signal_publisher_takes_the_lock() (+9 more)

### Community 175 - "tests/test_dk_direct_feed.py"
Cohesion: 0.09
Nodes (22): _Conn, _game_id_for(), _row_for(), _seen_key(), _rec(), test_a_line_move_is_a_new_quote(), test_a_market_we_do_not_understand_is_dropped_not_guessed(), test_a_price_move_is_a_new_quote() (+14 more)

### Community 177 - "tests/test_credit_budget.py"
Cohesion: 0.06
Nodes (23): CreditBudget, _Conn, daily_burn(), latest_remaining(), plan_credit_budget(), _burn_conn(), _plan(), test_a_billing_reset_is_not_a_refund() (+15 more)

### Community 180 - "Odds prune budget tests"
Cohesion: 0.05
Nodes (33): Budget, StandIn, _day(), prune_table(), mark(), settle(), build(), drain() (+25 more)

### Community 186 - "X profile update queue"
Cohesion: 0.10
Nodes (20): ProfileConn, _Rows, Updater, ProfileUpdate, _code(), _creds(), _drain(), _row() (+12 more)

### Community 189 - "Sharp book odds retention on prune"
Cohesion: 0.05
Nodes (24): _RecordingConn, ncaaf_line_bookmaker(), _prop_reference_books(), protected_for(), _thin_book_filter(), _unprotected(), test_prune_never_touches_cfbd_archive_lines(), test_the_bookmaker_these_rows_use_survives_the_daily_prune() (+16 more)

### Community 19 - "NHL blocked shots prop card"
Cohesion: 0.07
Nodes (19): TestTheCard, TestWhoThePlayerIs, name_key(), bs_implied(), candidates(), identities(), latest_quotes(), main() (+11 more)

### Community 193 - "tests/test_first_signal_repair.py"
Cohesion: 0.13
Nodes (22): _VoidedConn, patch_conn(), _sql_of(), test_a_lane_already_holding_its_first_bet_is_untouched(), test_a_lane_with_no_sibling_still_restores(), test_a_lane_with_nothing_standing_is_restored(), test_a_pregame_model_is_not_marked_live(), test_a_price_move_alone_is_a_different_bet() (+14 more)

### Community 199 - "Prop price pregame cutoff tests"
Cohesion: 0.08
Nodes (15): _StubConn, _latest_book_prop_row(), _latest_dk_prop_row(), _assigned_from(), _prop_scorers(), test_every_scorer_call_site_passes_a_pregame_cutoff(), test_get_prop_dk_odds_forwards_the_cutoff(), test_in_play_snapshots_are_excluded_unconditionally() (+7 more)

### Community 2 - "Mobile markets and formatting"
Cohesion: 0.01
Nodes (355): Row, Props, Props, IoniconName, Props, clvBetQuote, ClvBetRow, ClvBookRow (+347 more)

### Community 20 - "Model calibration sweep tests"
Cohesion: 0.05
Nodes (17): _ProbeConn, _rows(), test_a_prob_only_sweep_uses_only_the_probability_dimension(), test_column_migrations_run_every_pipeline_pass(), test_home_runs_are_no_longer_exempt_from_pausing(), test_plateau_is_computed_within_the_narrow_grid(), test_the_agent_changes_nothing_on_its_own(), test_the_agent_sweeps_every_registered_model_except_live_ones() (+9 more)

### Community 203 - "NHL goalie starters as of date"
Cohesion: 0.08
Nodes (10): GoalieBook, TestGoalieAsOf, TestReturningStarterIsNamedFromTheLog, TestGoalieLookup, _goalie_line(), regressed(), saved_above(), tot() (+2 more)

### Community 205 - "NFL in-play game state feed"
Cohesion: 0.14
Nodes (7): CoreClient, EventMeta, FakeClient, _abbr(), https(), ref_of(), team_id()

### Community 206 - "Mobile color contrast checker"
Cohesion: 0.05
Nodes (40): Pair, code(), lum(), noGreen(), over(), ratio(), read(), readUtf8() (+32 more)

### Community 208 - "CLV deciding price grading tests"
Cohesion: 0.07
Nodes (22): _Conn, _Res, _fn(), _migration(), _pick(), test_a_draftkings_decided_row_is_unchanged(), test_a_legacy_row_that_cannot_be_re_measured_leaves_the_old_method(), test_a_legacy_stamped_row_is_re_measured_and_leaves_the_queue() (+14 more)

### Community 21 - "Mobile record hero and equity curve"
Cohesion: 0.07
Nodes (65): EquityPoint, plotLayout, PlotPad, EquityCurve(), GridCell(), RecordHeroCard(), RecordInfoSheet(), RecordSparkline() (+57 more)

### Community 210 - "Mobile paywall billing and account access"
Cohesion: 0.02
Nodes (205): Calls, AccessState, useAccess, AuthState, AuthStatus, useAuth, useEntitlement, ConnectionMap (+197 more)

### Community 211 - "Mobile bankroll number formatting checks"
Cohesion: 0.09
Nodes (31): BankrollCheck, BankrollCommit, BankrollPatch, BankrollRead, NumberSeparators, Part, walk(), deviceSeparators() (+23 more)

### Community 215 - "Idle database read transaction tests"
Cohesion: 0.07
Nodes (16): ViewMigrationResult, _Rec, apply_view_migrations(), _flat(), test_a_lock_timeout_fails_that_file_and_the_next_still_runs(), test_a_locked_bet_releases_the_lock_check(), test_a_quiet_tick_rolls_the_read_back(), test_a_tick_that_writes_does_not_roll_the_insert_back() (+8 more)

### Community 216 - "NHL market-anchored moneyline model"
Cohesion: 0.05
Nodes (32): OffsetLogit, _Fixed, _GamesConn, _add_rating(), build_inputs(), choose_C(), decision_window(), fit() (+24 more)

### Community 218 - "In-play score change quote guard"
Cohesion: 0.09
Nodes (19): _MlbConn, _FakeConn, _book_move(), _get_live_dk_odds(), _score_changed_at(), _mlb_odds(), _mlb_ts(), test_mlb_declines_a_total_that_moved_a_full_run_on_an_unchanged_state() (+11 more)

### Community 22 - "Monitor dashboard probe and cache tests"
Cohesion: 0.06
Nodes (21): _Resp, _credits_from(), _scrub(), paid_apis(), _get(), test_billing_reset_reports_no_credits_rather_than_a_negative(), test_credits_are_the_delta_of_requests_used(), test_dashboard_is_served() (+13 more)

### Community 220 - "tests/test_db_reconnect.py"
Cohesion: 0.09
Nodes (16): _Conn, _Cursor, _is_write(), _lost(), test_a_committed_transaction_is_clean_again(), test_a_lost_connection_with_uncommitted_writes_raises_connection_lost(), test_a_read_on_a_lost_connection_reconnects_and_retries(), test_a_statement_timeout_is_not_a_lost_connection() (+8 more)

### Community 222 - "Discord recap restatement"
Cohesion: 0.06
Nodes (16): _Conn, test_a_restated_recap_is_labelled_and_says_why(), _resp(), test_a_404_is_an_answer_not_a_retry(), test_a_persistent_403_still_raises_after_the_last_attempt(), test_a_recap_whose_count_merely_drifted_is_not_due(), test_a_recap_with_a_late_settlement_is_due(), test_a_restatement_waits_out_a_live_game_and_posts_the_next_morning() (+8 more)

### Community 223 - "In-play scorer locks and push alerts"
Cohesion: 0.10
Nodes (20): FakeConn, _Rows, _lane_signature(), _write_live_picks(), _locked_live_lanes(), write_bet(), _log_lines(), _pick() (+12 more)

### Community 224 - "NHL blocked shots prop model"
Cohesion: 0.09
Nodes (19): TestTonightsRowIsATrainingRow, build_frame(), _ew(), expected_value(), fit(), load_skaters(), load_teams(), p_over() (+11 more)

### Community 225 - "tests/test_refresh_retry.py"
Cohesion: 0.14
Nodes (23): Decision, RefreshRun, _decide(), _done(), _run(), test_a_failed_view_migration_fails_the_step(), test_a_pass_that_finished_with_failed_steps_ran_its_chain(), test_a_redeploy_between_passes_replaces_nothing() (+15 more)

### Community 226 - "NBA results ingestion and prop settling"
Cohesion: 0.05
Nodes (28): PgStore, PlayerResolver, call_in_savepoint(), rollback_savepoint(), box_is_complete(), build_dnp_rows(), build_log_rows(), fallback_id() (+20 more)

### Community 228 - "NBA results ingestor tests"
Cohesion: 0.08
Nodes (29): _Conn, _ESPN, FakeStore, _FixedNow, _game(), _ppd_game(), _resolver(), _run() (+21 more)

### Community 23 - "NBA second game projection engine"
Cohesion: 0.03
Nodes (91): EW, Last, Model, PointInputs, State, World, actuals(), apply_models() (+83 more)

### Community 230 - "tests/test_local_cache_is_additive.py"
Cohesion: 0.11
Nodes (10): _FakeConn, _merge_with_cache(), _pull_odds(), cached(), _frame(), test_a_first_ever_pull_still_works(), test_a_pull_that_lost_rows_keeps_them(), test_an_unreadable_cache_refuses_rather_than_overwrites() (+2 more)

### Community 231 - "tests/test_calibration_check_coverage.py"
Cohesion: 0.10
Nodes (19): _Shim, _bet(), _calibration_results(), db(), _graded(), _make_db(), _only(), _promote() (+11 more)

### Community 232 - "NFL in-play odds client smoke check"
Cohesion: 0.10
Nodes (13): CreditMeter, LiveOddsClient, Quote, best_price(), parse_events(), _parse_ts(), _side_of(), check_espn() (+5 more)

### Community 233 - "tests/test_book_team_map.py"
Cohesion: 0.11
Nodes (15): _Conn, abbr_from_team_string(), resolve_game_id(), split_matchup(), test_a_non_mlb_sport_is_refused_rather_than_guessed(), test_a_string_with_no_at_sign_is_refused(), test_a_unique_game_resolves(), test_an_ambiguous_game_resolves_to_none() (+7 more)

### Community 234 - "tests/test_team_board_cache.py"
Cohesion: 0.08
Nodes (11): _Conn, _Cursor, refresh_team_board_cache(), team_board_pairs(), team_board_seasons(), _cols(), test_every_team_sport_gets_last_this_and_next_year(), test_one_failing_pair_does_not_stop_the_rest() (+3 more)

### Community 235 - "NCAAF feature engine and targets"
Cohesion: 0.03
Nodes (53): TestComputeTarget, TestFeatureMap, TestHasStarterOut, TestFbsGate, _SqliteShim, _compute_target(), _has_starter_out(), _assemble_ncaaf_features() (+45 more)

### Community 237 - "Minimum odds price floor checks"
Cohesion: 0.05
Nodes (27): TestAmericanToDecimalScorer, min_odds_for(), _backtest_ufc_fight(), _emit(), american_to_decimal(), _blocked_by_min_odds(), _apply_price_floor(), emit() (+19 more)

### Community 239 - "NFL wind board fast publishing tests"
Cohesion: 0.13
Nodes (16): FakeConn, publish_board(), matchup(), _append_board(), _body(), _row(), _sent(), _setup() (+8 more)

### Community 24 - "NBA fifth search period shares"
Cohesion: 0.04
Nodes (44): LazyFrames, side_strength(), american(), band_bounds(), band_columns(), blended_ratings(), cell_specs(), control_shuffles() (+36 more)

### Community 242 - "NFL in-play odds history purchase"
Cohesion: 0.16
Nodes (22): Budget, buy_halftime(), buy_inplay(), events_for(), _floor5(), _get(), halftime_requests(), halftime_windows() (+14 more)

### Community 244 - "MLB weather forecast ingestor"
Cohesion: 0.06
Nodes (17): _Resp, TestTheHourIsTheGamesOwn, TestTheRequestCoversTheTargetHour, TestTheStoreReadsTheStartTime, TestTheUmpireLandsOnEveryPass, backfill_weather(), _celsius_to_f(), fetch_and_store_weather_for_date() (+9 more)

### Community 245 - "NHL team rates as of date"
Cohesion: 0.13
Nodes (5): TeamBook, TestBlendedTeamInputs, TestTeamRatesAsOf, _r(), _t()

### Community 247 - "tests/test_dk_freshness_parse.py"
Cohesion: 0.12
Nodes (17): _FakeConn, _FakeResult, _american(), parse_dk_payload(), _store(), _payload(), test_a_half_priced_market_is_dropped_rather_than_half_recorded(), test_an_event_with_no_markets_yields_nothing_rather_than_raising() (+9 more)

### Community 248 - "NHL moneyline rebuild and grading"
Cohesion: 0.02
Nodes (125): OffsetLogit, apply_calibration(), log_loss(), accuracy(), first_games(), logloss(), main(), sweep() (+117 more)

### Community 249 - "models: slate_concentration + test_slate_concentration"
Cohesion: 0.07
Nodes (33): SlateConcentration, apply_slate_guard(), apply_slate_concentration_guard(), _attr(), _edge_of(), _is_bet(), measure_side_concentration(), _side_of() (+25 more)

### Community 251 - "View migration lock handling tests"
Cohesion: 0.07
Nodes (25): _Conn, _Deadlock, _LockTimeout, _StatementTimeout, _Syntax, execute(), _before(), _code() (+17 more)

### Community 252 - "Discord pick notifier price fields"
Cohesion: 0.04
Nodes (43): _FakeConn, _sig(), test_a_strictly_better_book_becomes_the_headline(), test_an_equal_or_worse_price_never_replaces_draftkings(), test_best_odds_never_reaches_the_qualifying_gate(), test_draftkings_winning_its_own_shop_is_published_as_draftkings(), test_every_pre_game_producer_computes_good_to(), test_good_to_is_published_when_the_producer_supplies_it() (+35 more)

### Community 259 - "NBA total luck card publishing"
Cohesion: 0.06
Nodes (24): FrameConn, load_artifact(), artifact(), decided_games(), ensure_decisions_table(), ledger_exists(), load_quote_rows(), load_season() (+16 more)

### Community 26 - "Mobile performance and tracked bets"
Cohesion: 0.03
Nodes (114): Props, Props, Props, StakeMode, StakeState, LiveTrackSnapshot, ScopedDailyResults, FeedbackCategory (+106 more)

### Community 260 - "NHL season labels and opening week"
Cohesion: 0.09
Nodes (15): TestSeasonLabel, fetch_all(), _fold(), load(), load_period_scores(), _num(), _odds_rows(), parse_season() (+7 more)

### Community 261 - "NBA game four point estimates"
Cohesion: 0.05
Nodes (41): OffsetRidge, Point, base_inputs(), cell_specs(), check_cell_count(), choose_C_linear(), derivative_data(), derivative_plan() (+33 more)

### Community 265 - "Best line threshold sweep"
Cohesion: 0.10
Nodes (12): _Conn, american_to_decimal(), units_at(), _row(), test_a_better_price_pays_more_than_the_dk_price(), test_a_loss_costs_one_unit_at_every_price(), test_a_push_is_flat(), test_a_retired_model_is_never_recommended_a_cut() (+4 more)

### Community 269 - "NCAAF college data ingest tests"
Cohesion: 0.06
Nodes (11): _GamesConn, _TeamsConn, ingest_ncaaf_teams(), test_ingest_games_retains_a_historical_utc_id_and_uses_et_for_a_new_row(), fake_get(), test_ingest_pulls_fbs_then_everyone_and_fbs_rows_win(), test_ingest_retries_everyone_without_a_year_if_the_season_filter_is_empty(), test_prior_context_tolerates_missing_talent_and_returning() (+3 more)

### Community 27 - "Mobile bet slip and parlay legs"
Cohesion: 0.01
Nodes (217): Props, ParlayRestorePayload, PlayerPropQuote, ResolvedSlip, GameLineLegSpec, GameLineMarket, LineLegSpec, LineSheetInput (+209 more)

### Community 270 - "NBA pregame scoring window"
Cohesion: 0.07
Nodes (30): PregamePlan, _fires(), _jobs(), test_every_tip_time_gets_a_look_inside_its_window(), test_the_first_look_inside_the_window_is_at_the_graded_lead(), test_the_refresh_passes_alone_reached_none_of_these_tips(), test_the_window_job_is_every_five_minutes_on_the_pipeline_service(), _db() (+22 more)

### Community 272 - "NCAAF in-play bet lock and serving"
Cohesion: 0.13
Nodes (12): FakeConn, _Rows, write_picks(), db(), test_both_lanes_locked_touches_nothing(), test_dry_run_never_touches_db(), test_first_bet_is_written_and_will_lock(), test_flag_off_restores_delete_and_replace() (+4 more)

### Community 273 - "tests/test_prop_odds_utc_stamp.py"
Cohesion: 0.12
Nodes (13): _Conn, _assert_utc_stamp(), _frozen(), _run_mlb(), capture(), events(), _run_ncaaf(), test_an_eastern_row_then_a_later_utc_row_sorts_in_time_order() (+5 more)

### Community 274 - "Live monitor web server streaming"
Cohesion: 0.29
Nodes (4): Handler, _connect(), dumps(), _json_default()

### Community 275 - "NBA game harness tests"
Cohesion: 0.07
Nodes (29): ResidDist, test_a_period_moneyline_removes_the_tie_mass(), _cov_data(), _fetches(), _games(), _offers(), _q(), _stale_cache() (+21 more)

### Community 277 - "NCAAF opener strategy search"
Cohesion: 0.06
Nodes (36): FoldResult, features_for(), _apply_calibration(), exponential_recency_weights(), _logit(), make_ensemble(), fit_predict(), make_lgbm() (+28 more)

### Community 278 - "tests/test_feature_artifact_agreement.py"
Cohesion: 0.15
Nodes (8): _Stub, _TolerantUnpickler, _load(), _newest_artifact(), test_artifact_width_matches_its_own_feature_cols(), test_config_list_matches_the_trained_artifact(), test_known_drift_only_names_real_models(), test_pending_features_are_not_live_without_a_retrain()

### Community 279 - "NFL prop one side per line"
Cohesion: 0.16
Nodes (8): _Conn, best_per_prop(), _hockenson(), test_a_different_market_on_the_same_player_is_still_its_own_bet(), test_input_order_does_not_decide_the_side(), test_nfl_publish_will_not_add_the_other_side_of_a_locked_line(), test_opposite_sides_of_one_line_collapse_to_the_bigger_edge(), test_wnba_publish_will_not_add_the_other_side_of_a_locked_line()

### Community 28 - "Closing line value math"
Cohesion: 0.06
Nodes (29): _Conn, _Res, implied(), test_a_one_way_close_is_not_de_vigged(), test_a_worse_close_is_negative_and_equal_prices_are_zero(), test_devigging_the_taken_price_is_not_what_primary_does(), test_kalshi_close_is_not_de_vigged(), test_market_edge_devigs_only_the_close() (+21 more)

### Community 281 - "tests/test_cloud_retrain_artifacts.py"
Cohesion: 0.10
Nodes (12): _Conn, _restore_artifact(), test_a_failed_upload_does_not_lose_a_model_that_trained(), test_a_missing_artifact_table_is_not_an_error_on_restore(), test_a_no_register_run_stores_nothing(), test_load_model_actually_loads_from_the_store_when_the_file_is_gone(), fetchone(), test_load_model_returns_none_when_the_store_has_nothing_either() (+4 more)

### Community 282 - "NHL side models never bet against each other"
Cohesion: 0.09
Nodes (23): _Conn, _ThreeWay, ml(), _pick(), reg(), _score_regulation(), test_a_market_not_listed_is_never_a_conflict(), test_a_paused_models_bet_neither_holds_nor_loses_the_game() (+15 more)

### Community 283 - "Odds prune frontier and retries"
Cohesion: 0.09
Nodes (15): ConnectionLost, BudgetSpent, FrontierUnreadable, count_sql(), delete_sql(), doomed_sql(), _frontier_job(), _pk() (+7 more)

### Community 285 - "System health and deliverability checks"
Cohesion: 0.04
Nodes (33): HealthReport, ncaaf_season_for_date(), test_january_games_belong_to_the_prior_season(), test_a_game_date_inside_the_window_counts(), test_a_lookahead_commence_counts_even_when_game_date_is_outside(), test_a_signal_locked_after_first_pitch_was_never_deliverable(), test_a_signal_locked_before_first_pitch_still_counts(), test_a_signal_locked_exactly_at_first_pitch_counts() (+25 more)

### Community 289 - "Player news feed ingestion"
Cohesion: 0.04
Nodes (47): NewsItem, NewsPlayer, FakeConn, FakeResponse, _Result, _article_url(), _athletes_in(), build_name_index() (+39 more)

### Community 290 - "Prop player name matching"
Cohesion: 0.08
Nodes (18): FakeConn, alias_play_ids(), drop_duplicate_box_ids(), normalize_player_name(), resolve_feed_name(), test_a_player_listed_twice_in_the_box_keeps_the_id_the_plays_use(), test_a_player_logged_under_a_second_id_is_read_as_his_box_id(), test_accented_roster_name_matches_the_flat_feed_name() (+10 more)

### Community 295 - "Discord and X results posting"
Cohesion: 0.02
Nodes (67): UnitStake, _apply_one(), _is_transient_lock_error(), _with_lock_timeout(), test_a_loss_costs_the_full_stake_and_a_push_costs_nothing(), test_a_pick_with_no_price_stays_in_the_units_at_bare_conviction(), test_a_six_column_row_still_tallies(), test_a_snapshot_with_no_clv_stores_null_not_zero() (+59 more)

### Community 296 - "MLB batter prop log scoring tests"
Cohesion: 0.09
Nodes (11): _Rec, _ScoringConn, build_batter_scoring_rows(), build_pitcher_scoring_rows(), _log_sql(), test_batter_log_scan_is_pinned_to_the_lookback_not_the_catalog(), test_five_models_share_one_log_load(), test_no_lineup_does_not_scan_the_log() (+3 more)

### Community 298 - "tests/test_nfl_wind_publisher.py"
Cohesion: 0.13
Nodes (10): TestBuildRows, TestKickFields, TestParseMatchup, build_rows(), _fmt_line(), kick_fields(), parse_matchup(), test_nfl_wind_and_opener_rows_drop_a_bet_under_the_floor() (+2 more)

### Community 3 - "Pre-game odds and prop odds ingestors"
Cohesion: 0.01
Nodes (183): Meter, Meter, Meter, TestEveryOtherSportStillMintsItsOwn, TestNflResolvesOntoTheSchedule, TestTheResolverFailsClosed, TestOddsFeedTeamNames, TestThreeWayMarketKey (+175 more)

### Community 30 - "NFL in-play prop polling tests"
Cohesion: 0.04
Nodes (37): Read, _FakeOdds, _IdRecordingOdds, blind_over_prob(), over_prob(), _pass_attempt_bias_allowed(), _core_worker(), test_a_deployed_bias_must_sit_inside_its_measured_interval() (+29 more)

### Community 300 - "tests/test_health_reason_and_cadence.py"
Cohesion: 0.10
Nodes (19): Report, _one(), test_a_24h_ts_check_reads_as_daily(), test_a_bare_add_still_fills_both_columns(), test_a_broken_query_is_its_own_reason(), test_a_late_check_says_how_late(), test_a_passing_check_says_fresh(), test_a_skipped_check_says_the_gate_was_shut() (+11 more)

### Community 301 - "NBA odds history gap fetching"
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
Nodes (33): _FakeConn, last3_rates(), outs_from_ip(), per_nine(), whip(), _avg_distinct(), build_rows(), constant_era_pitcher_seasons() (+25 more)

### Community 31 - "NBA prop market tip timing"
Cohesion: 0.05
Nodes (37): NbaPropDecision, Roster, coherent(), fair_under(), fetch_times(), find_bets(), in_window(), load_quotes() (+29 more)

### Community 312 - "NFL in-play feed resilience tests"
Cohesion: 0.08
Nodes (20): _ScriptedTick, _core_docs(), _core_event(), _fetch(), _run_scripted(), test_a_healthy_payload_raises_no_problems(), test_a_hunted_game_counts_as_busy(), test_a_live_game_resets_the_idle_counter() (+12 more)

### Community 314 - "Pipeline log reason tests"
Cohesion: 0.22
Nodes (6): _Conn, _capture(), test_a_false_step_records_the_last_error_it_logged(), test_a_false_step_that_logged_nothing_still_says_so(), test_a_raising_step_still_records_the_exception(), test_the_sink_is_removed_after_the_step()

### Community 315 - "NFL in-play remaining-yards engine training"
Cohesion: 0.07
Nodes (20): ScoreDistribution, _cluster_bootstrap(), evaluate(), main(), report(), fit(), load_states(), main() (+12 more)

### Community 32 - "NBA in-game study two"
Cohesion: 0.07
Nodes (33): StateModel, apply_model(), benchmark_columns(), decision_quotes(), delta_ci(), _design(), eligible(), _expit() (+25 more)

### Community 320 - "NFL opener and wind writer lock tests"
Cohesion: 0.07
Nodes (7): _Pg, _PgCursor, TestPreflightCiMode, TestPreflightLockChecks, wind(), wrapped(), fake_open()

### Community 321 - "NFL team game rows parsing"
Cohesion: 0.11
Nodes (10): TestGamesRows, TestKickoff, TestParseTeamRows, TestUpcomingRows, games_rows(), _int_or_none(), _kickoff_utc(), _num_or_none() (+2 more)

### Community 323 - "NBA prop fetch window planning"
Cohesion: 0.09
Nodes (17): _PlanConn, _game(), _plan(), _t(), test_a_projection_too_old_to_price_does_not_block_the_retry(), test_a_tick_fetches_exactly_the_window_games_then_decides_closes_and_publishes(), test_a_tick_with_nothing_near_spends_nothing(), test_a_tick_with_only_a_close_due_does_not_return_early() (+9 more)

### Community 330 - "NFL opener pick builder tests"
Cohesion: 0.27
Nodes (5): TestBuildOpenerRows, build_opener_rows(), _opener_model(), _card_row(), _row()

### Community 331 - "NHL player prop projection model"
Cohesion: 0.07
Nodes (37): Spec, _attach_teams(), books(), build_frame(), build_goalie_frame(), build_skater_frame(), _ew(), excess_variance() (+29 more)

### Community 332 - "Pregame line poller key map seeding"
Cohesion: 0.10
Nodes (15): _PollConn, _fingerprint(), _key(), last_known_prices(), _num(), poll_once(), quoted_keys(), _quiet_poll() (+7 more)

### Community 341 - "Health check skip budget tests"
Cohesion: 0.07
Nodes (20): FakeConn, test_a_stuck_gate_is_not_reported_as_stale_data(), _res(), _source_outside_the_budget_table(), test_a_check_never_seen_non_skipped_counts_its_whole_history(), test_a_check_skipped_only_today_is_not_counted_as_a_streak(), test_a_non_skipped_result_is_never_touched(), test_a_stuck_gate_escalates_past_its_budget() (+12 more)

### Community 342 - "tests/test_live_pick_features.py"
Cohesion: 0.18
Nodes (11): FakeConn, _record_live_features(), _pick(), test_a_live_bet_records_its_feature_row_and_lambda(), test_a_pick_with_no_feature_row_is_skipped_not_written_empty(), test_a_recorder_failure_is_rolled_back_to_its_savepoint(), test_a_recorder_failure_is_swallowed_rather_than_raised(), test_a_success_releases_its_savepoint() (+3 more)

### Community 345 - "Model quality detectors and tests"
Cohesion: 0.04
Nodes (46): _Shim, record_exclusion_sql(), _bet(), _fade_slate(), _insert_open_bet(), test_a_mixed_slate_is_ok(), test_all_home_ncaaf_slate_is_flagged_without_mlb_hardcoding(), test_all_unders_public_fade_risk_is_crit() (+38 more)

### Community 349 - "tests/test_prop_missing_features.py"
Cohesion: 0.14
Nodes (5): TestARowMissingAFeatureIsNotScored, TestEveryPropLoopGoesThroughTheHelper, TestTheUmpireIsTheDeclaredException, _frame(), helper()

### Community 350 - "Pregame snapshot first pitch guard"
Cohesion: 0.11
Nodes (9): TestPregameSnapshotGuard, trusted_first_pitch(), _is_pregame_snapshot(), build_side_table(), _fetch_games(), main(), _pregame_odds(), sweep() (+1 more)

### Community 352 - "NCAAF FBS registry health checks"
Cohesion: 0.06
Nodes (17): TestRefusalLog, TestRegistryHealthCheck, TestUnratedFbsClaim, fbs_refusal_claims(), unrated_fbs_claim(), _alarm_part(), hdb(), _live_db() (+9 more)

### Community 355 - "NFL in-play pick writer tests"
Cohesion: 0.03
Nodes (53): PicksRecorder, _AvoidConn, _Conn, _Decision, _OpenConn, build_pick(), refuse_publish_reason(), _executor_min_price() (+45 more)

### Community 361 - "NCAAF live state recording tests"
Cohesion: 0.16
Nodes (13): _Conn, record_live_states(), state_change_row(), state_key(), _state(), test_a_failed_write_never_costs_the_pass(), test_a_score_a_period_or_a_possession_change_is_written(), test_first_sight_is_written() (+5 more)

### Community 363 - "tests/test_run_ledger_orphans.py"
Cohesion: 0.12
Nodes (18): _Conn, db(), _insert_open(), _ledger(), _open_rows(), _row(), test_a_genuine_current_hang_is_still_detectable(), test_a_second_sweep_does_not_abort_the_pass_this_process_started() (+10 more)

### Community 367 - "NFL opener and NCAAF calibration tests"
Cohesion: 0.09
Nodes (10): TestTickLatency, bucket(), label(), main(), table(), wilson(), test_projecting_runs_after_the_decisions_are_published(), test_the_tick_passes_a_days_that_covers_the_whole_window() (+2 more)

### Community 37 - "NBA lineup stints from play-by-play"
Cohesion: 0.05
Nodes (50): Diagnostics, _Seg, roster_from_plays(), score_plays(), _accumulate(), _add_one(), _and_one_follows(), appearances() (+42 more)

### Community 376 - "In-play calibrated decision tests"
Cohesion: 0.08
Nodes (18): RecordingConn, fetch_graded(), _in_graded_matview(), _is_live_lane(), _cut(), _signal(), test_a_big_enough_claim_still_fires_after_calibration(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking() (+10 more)

### Community 378 - "Team total market decision tests"
Cohesion: 0.06
Nodes (17): TestBuildPickLabel, _PickConn, _Rows, _SqliteShim, _build_pick_label(), raw(), _result(), test_a_line_that_dropped_under_an_under_is_a_skip() (+9 more)

### Community 379 - "Game-level star injury gate"
Cohesion: 0.11
Nodes (14): _InjConn, _goalie_names(), load_sport_injury_index(), _pitcher_names(), relevant_players(), _star_names(), stars_from_logs(), _apply_game_injury_gate() (+6 more)

### Community 38 - "Pregame game scorer and best price"
Cohesion: 0.01
Nodes (133): FakeConn, TestAmericanToImpliedProb, TestConfidenceTier, TestMissingStarterGate, TestQuarterKelly, today_et(), build_golf_scoring_features(), _make_live_pick() (+125 more)

### Community 381 - "NFL in-play leader game state"
Cohesion: 0.17
Nodes (14): LiveState, game_seconds(), in_window(), _int(), is_admin_play(), is_conversion_play(), is_scoring_play(), last_real_play() (+6 more)

### Community 383 - "NCAAF opponent-adjusted search features"
Cohesion: 0.11
Nodes (14): AdjRatings, blended_rating(), fit_opponent_adjustment(), _synth(), test_blend_falls_back_when_one_side_missing(), test_blend_weights_move_from_prior_to_current(), test_confounded_home_assignment_plus_heavy_alpha_corrupts_hfa(), test_hfa_is_positive_and_neutral_site_excluded() (+6 more)

### Community 385 - "Any-book first five line scoring"
Cohesion: 0.08
Nodes (31): _Clf, _GameOddsConn, _fallback_game_line_quote(), _get_scoring_odds(), _has_real_game_price(), _cut(), _mlb_feat(), _on() (+23 more)

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

### Community 4 - "Pick settlement and self-healing grading"
Cohesion: 0.02
Nodes (98): _SqliteShim, _Conn, _FakeStatsapi, _SqliteShim, statement_timeout(), mirror_stored_finals(), _box(), conn() (+90 more)

### Community 40 - "Mobile player stats and game log"
Cohesion: 0.02
Nodes (240): Props, PlayerNextGame, Section, Args, PlayerStatKey, reachFrame, DecisionPriced, HitSelection (+232 more)

### Community 401 - "Free pick card and X results tests"
Cohesion: 0.04
Nodes (22): _CursorResult, _Conn, _pick(), test_every_offerable_book_has_a_human_name_on_both_surfaces(), test_the_free_card_names_the_cheaper_book(), test_the_free_card_query_reads_the_columns_it_renders(), test_the_good_to_clause_is_dropped_not_truncated_when_it_will_not_fit(), test_the_tweet_names_the_cheaper_book() (+14 more)

### Community 41 - "tests/test_live_quote_staleness.py"
Cohesion: 0.05
Nodes (36): ScoreClock, _Conn, _Q, build_row(), quote_from_nfl_quotes(), rows_from_quote(), _abbrev(), rows_for_quotes() (+28 more)

### Community 410 - "NBA prop closing line purchase tests"
Cohesion: 0.09
Nodes (11): _Conn, _Resp, test_a_close_already_held_is_not_bought_again(), test_a_due_close_buys_one_call_of_the_bet_markets_and_reports_its_credits(), test_a_pass_outside_the_window_spends_nothing(), test_only_a_game_holding_a_bet_and_only_once(), test_only_twelve_to_twenty_five_minutes_before_tip(), test_the_ten_minute_evening_passes_always_land_one_inside() (+3 more)

### Community 412 - "NBA prop settlement stats tests"
Cohesion: 0.11
Nodes (9): _SelectConn, test_a_missing_stat_is_none_not_zero(), test_a_turnovers_bet_on_a_player_who_played_settles_win_not_no_action(), test_combo_markets_are_mapped_to_helpers_and_only_the_nba_rule_uses_them(), test_double_double_matches_the_rule_it_replaced(), test_the_loader_carries_every_stat_a_market_settles_on(), test_the_loader_selects_turnovers(), _load_nba_prop_actuals() (+1 more)

### Community 417 - "In-play publish parity with pauses"
Cohesion: 0.09
Nodes (17): _Conn, _Conn, _Res, _db(), _labels(), _pick(), test_a_bet_written_while_paused_is_not_announced_after_an_unpause(), test_a_live_health_state_still_publishes() (+9 more)

### Community 419 - "CLV backfill job tests"
Cohesion: 0.13
Nodes (6): _Conn, _stub_backfill(), test_hard_cap_stops_a_nonempty_queue(), test_loops_until_a_pass_fills_nothing(), test_the_runner_opens_get_connection_and_calls_backfill_clv(), _job_clv_backfill()

### Community 421 - "NBA injury report storage tests"
Cohesion: 0.11
Nodes (17): _Conn, _Cur, _Fetcher, _PdfFetcher, _content_of_fixture(), _rows(), test_a_changed_report_stores_its_rows(), test_a_garbled_report_writes_its_ledger_row_and_no_rows() (+9 more)

### Community 424 - "supabase/functions/_shared/discord.ts"
Cohesion: 0.20
Nodes (15): DiscordApiError, DiscordUser, RoleSyncResult, addAppRole(), addGuildMember(), botFetch(), expectOk(), isGuildMember() (+7 more)

### Community 43 - "Worker job queue validation tests"
Cohesion: 0.02
Nodes (69): _Conn, _DedupeConn, _VoidConn, _fake(), _posted_row(), _quiet(), _run_void(), _run_void_job() (+61 more)

### Community 434 - "NFL in-play pick writer"
Cohesion: 0.10
Nodes (9): TeeRecorder, _is_market_opinion(), _lane_is_locked(), _norm_player(), resolve_game(), resolve_game_id(), test_normalised_player_key_is_the_join_the_prop_system_uses(), test_the_lane_lock_shares_the_scorers_meaning_of_locked() (+1 more)

### Community 436 - "Pre-game price age and NHL totals"
Cohesion: 0.04
Nodes (31): _BoardConn, _OddsConn, _ShopConn, _TwoIdConn, _UfcBoardConn, main(), publish(), render() (+23 more)

### Community 440 - "NFL DraftKings line snapshots"
Cohesion: 0.08
Nodes (13): TestDkLineRows, TestPublishLineSnapshots, TestSnapshotRowParams, append_snapshot_csv(), dk_line_rows(), dump_dk_lines(), _num(), snapshot_schedule() (+5 more)

### Community 443 - "Database schema setup and splitting"
Cohesion: 0.19
Nodes (4): TestRealSchema, TestSplitter, TestSqliteSchema, _split_sql_statements()

### Community 446 - "Schema guard and table lockdown"
Cohesion: 0.03
Nodes (56): GuardConn, lock_down(), _fetchone(), schema_is_current(), ensure_table(), fetch_date(), main(), run() (+48 more)

### Community 448 - "tests/test_discord_channel_probe.py"
Cohesion: 0.17
Nodes (7): _Resp, test_the_probe_covers_the_per_sport_live_channels(), test_the_probe_never_posts_and_never_returns_the_url(), test_the_probe_reports_the_channel_behind_each_sport(), _get(), test_two_sports_sharing_a_channel_are_flagged(), _job_discord_probe()

### Community 45 - "tests/test_nfl_prop_one_read_per_game.py"
Cohesion: 0.06
Nodes (25): _Conn, _Log, publish_hour_missed(), publishable_games(), _at(), _games(), test_a_game_is_publishable_on_exactly_one_pass_in_its_window(), test_a_game_with_no_kickoff_is_never_published() (+17 more)

### Community 450 - "Bounded odds prune retry tests"
Cohesion: 0.06
Nodes (29): Timeout, p(), _after_nth_delete(), _expire_after_deletes(), _fails_on(), _lit(), nba_paths(), old_prune() (+21 more)

### Community 458 - "ESPN injury team lookup fallback"
Cohesion: 0.06
Nodes (18): TestCoreTeamsFallback, _espn_team_ids(), _fetch_nba_espn_team_ids(), _fetch_nfl_espn_team_ids_core(), _fetch_wnba_espn_team_ids(), _fetch_wnba_espn_team_ids_core(), _nba_espn_team_to_abbrev(), _nfl_espn_team_to_abbrev() (+10 more)

### Community 464 - "NCAAF gameday live odds cadence"
Cohesion: 0.04
Nodes (30): LiveOddsFeed, _Ctx, _ev(), _feed_with_payload(), gameday_mod(), _main_source(), _modelled_monthly_cfbd_calls(), test_a_single_failed_summary_does_not_drop_the_other_games() (+22 more)

### Community 469 - "Multi-book odds ingestion"
Cohesion: 0.05
Nodes (26): _OddsConn, _Resp, _odds_query(), _prop_markets(), _source(), test_a_game_with_no_commence_time_keeps_every_row(), test_a_rejected_book_list_falls_back_to_the_decision_book(), _get() (+18 more)

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

### Community 474 - "NBA SBR odds archive importer"
Cohesion: 0.06
Nodes (40): _Conn, classify(), _fold(), _gid(), _is_half(), iso_z(), load(), match() (+32 more)

### Community 475 - "NFL prop feature and walk-forward scripts"
Cohesion: 0.03
Nodes (52): LazyConnection, ShrunkEnsemble, _add_features(), build_nfl_prop_scoring_rows(), build_nfl_prop_training_dataset(), _cols(), derived_targets(), _load() (+44 more)

### Community 478 - "NFL prop count and yardage distributions"
Cohesion: 0.14
Nodes (6): TestBinaryMarket, TestCountDistributions, TestYardageDistribution, _nfl_prop_probs(), _art(), test_nb_head_changes_probs_only_when_nb_r_present()

### Community 48 - "tests/test_calibration_watch.py"
Cohesion: 0.04
Nodes (20): _Conn, _Res, TestDormantLiveModels, TestItNeverDecides, TestRosterChanges, TestTheRun, TestVerdictChanges, TestVolumeShifts (+12 more)

### Community 480 - "NCAAF in-play odds history backtest"
Cohesion: 0.04
Nodes (49): _Conn, _StubEngine, _blank_row(), budget_for(), calls_in(), _floor5(), _get(), _iso() (+41 more)

### Community 485 - "NFL weather history fetcher"
Cohesion: 0.18
Nodes (10): DailyLimit, Pacer, consolidate(), era5_check(), game_hours(), log(), main(), om_get() (+2 more)

### Community 488 - "Model performance monitor tests"
Cohesion: 0.08
Nodes (11): FakeConn, model_performance(), _perf_rows(), test_an_unpriced_model_reports_no_roi(), test_partially_priced_model_keeps_its_denominator_visible(), test_perf_reads_the_matview_not_the_expensive_view(), test_roi_denominator_excludes_pushes(), test_roster_reports_a_registered_but_untrained_model() (+3 more)

### Community 489 - "In-play pregame total anchor tests"
Cohesion: 0.12
Nodes (6): _RecordingConn, _pregame_features(), test_h2h_row_alone_never_fills_the_anchor(), test_pregame_features_reads_both_markets(), test_serve_side_cutoff_uses_the_shared_first_pitch_bound(), test_the_anchor_is_not_wired_into_a_model_by_accident()

### Community 49 - "Pipeline failure alerting and heartbeats"
Cohesion: 0.07
Nodes (12): FakeConn, TestDeliveryAndNoise, TestHealthCheckOnlyIsNotADirtyPass, TestItCannotBreakTheWorker, TestSilentJobs, TestWhatCountsAsAFailure, _clean_runs(), _posts() (+4 more)

### Community 490 - "NCAAF starter-out research dataset"
Cohesion: 0.16
Nodes (8): LabelSet, build_label_set(), _fetch_lines(), _fetch_raw(), opener_coverage(), _pick_provider(), provider_continuity(), main()

### Community 492 - "NFL in-play leader win probability"
Cohesion: 0.17
Nodes (10): Artifact, Decision, am_to_dec(), artifact_from_dict(), band_for(), decide(), leader_expected_margin(), load_artifact() (+2 more)

### Community 493 - "Mobile bankroll storage"
Cohesion: 0.23
Nodes (12): KeyValueStore, check(), eq(), fakeStore(), interleaving(), slowStore(), storage(), createBankrollStore() (+4 more)

### Community 499 - "NHL totals market model and card"
Cohesion: 0.05
Nodes (36): NhlTotalBet, _LockConn, _SlateConn, expected_value(), _coherent(), _fetch_ts(), find_bets(), load_fetch_quotes() (+28 more)

### Community 5 - "Mobile app screens and theme"
Cohesion: 0.02
Nodes (224): Props, Props, State, Nav, Props, Props, Props, FilterChipProps (+216 more)

### Community 502 - "NHL prop settlement tests"
Cohesion: 0.20
Nodes (6): _Shim, TestSettlement, _bet(), _in_goal(), _result(), _skated()

### Community 504 - "Member sportsbooks scratch database tests"
Cohesion: 0.12
Nodes (17): ScratchPostgres, pg_bin(), test_schema_applies_twice_on_scratch_postgres_and_anon_can_only_read(), test_build_on_scratch_postgres_grades_the_stored_lines(), _code(), test_rpcs_on_scratch_postgres(), test_the_migration_is_one_statement_and_registered(), test_the_second_pass_returns_before_it_locks() (+9 more)

### Community 505 - "tests/test_mobile_stat_labels_match_the_server.py"
Cohesion: 0.12
Nodes (11): Read, pace_ratio(), _sigmoid(), under_prob(), test_the_ratio_is_the_requirement_against_the_actual_pace(), _meta_entries(), _server_stat_labels(), test_both_rushing_models_call_the_stat_the_same_thing() (+3 more)

### Community 51 - "Mobile team stats screen"
Cohesion: 0.04
Nodes (115): NextGame, Section, Tier, FormGame, FormSummary, headToHead, lineMove, PickRecord (+107 more)

### Community 510 - "NBA injury report daily runs"
Cohesion: 0.17
Nodes (10): Fetcher, ensure_tables(), load_players(), load_schedule(), main(), pulled_urls(), remap_players(), retry_failed() (+2 more)

### Community 512 - "External threshold map promotion"
Cohesion: 0.16
Nodes (5): _Conn, promote_external(), test_external_promotion_refuses_a_map_that_does_not_transfer(), test_external_promotion_writes_only_the_promoted_columns(), test_the_scorer_reads_the_external_map_like_any_promoted_one()

### Community 52 - "In-play best line price tests"
Cohesion: 0.04
Nodes (40): _FakeConn, _live_quote_is_on_offer(), _ev(), _live_pick(), _open_cut(), _row(), test_a_book_on_a_different_line_is_not_a_better_price(), test_a_book_with_no_price_is_skipped() (+32 more)

### Community 526 - "NCAAF college data refresh and backfill tests"
Cohesion: 0.16
Nodes (8): _NullConn, backfill_ncaaf(), refresh_ncaaf_games(), test_backfill_returns_totals_when_every_season_succeeds(), test_backfill_survives_a_mid_run_season_failure(), test_refresh_games_happy_path_counts_games(), test_refresh_games_repairs_every_season_and_reports_failures(), test_refresh_stats_isolates_a_failing_season()

### Community 528 - "UFC fight stats ingest tests"
Cohesion: 0.12
Nodes (6): _IngestConn, _ingest(), _one_fight_event(), test_a_late_replacement_is_not_scored_on_the_original_booking(), test_a_row_naming_neither_fighter_is_left_unscored(), test_the_same_fight_stored_twice_is_scored_on_both_rows_each_way_round()

### Community 53 - "Mobile data queries and pick types"
Cohesion: 0.02
Nodes (148): Props, FighterSide, Props, LivePicksState, Args, PlayerNewsState, PropContext, DailyResults (+140 more)

### Community 531 - "NFL live leader cut and price floor"
Cohesion: 0.09
Nodes (9): Gate, honest_probability(), test_a_loop_that_dies_fails_its_job(), test_it_decides_on_its_own_probability(), test_it_is_a_live_engine_model_that_settles_as_a_moneyline(), test_the_action_threshold_key_is_on_one_line(), test_the_loop_refuses_a_price_shorter_than_the_floor(), test_the_mlb_live_scorer_skips_it() (+1 more)

### Community 533 - "NBA team total odds fetch tests"
Cohesion: 0.04
Nodes (60): TeamTotalBet, Clock, FakeResp, _billed(), event_ids(), event_rows(), fetch_team_totals(), fetches() (+52 more)

### Community 537 - "Model training and prop features"
Cohesion: 0.01
Nodes (121): TestTheDropIsDeclared, TestTrainingExcludesThemAndScoringDoesNot, calibration_method(), _blk_bullpen_ip(), _blk_injuries(), _blk_rolling_runs(), _blk_season_loc_runs(), _blk_team_stats() (+113 more)

### Community 54 - "tests/test_void_picks.py"
Cohesion: 0.05
Nodes (14): _FakeConn, TestAPostedSignalIsLocked, TestTheToolRefusesToMatchEverything, TestVoidingAPostedPickIsAnExplicitOptIn, TestWhatMayBeVoided, TestWhatTheVoidWrites, build_parser(), main() (+6 more)

### Community 541 - "MLB final score twin lookup"
Cohesion: 0.21
Nodes (9): _Conn, _Cur, _lookup_home_won(), mlb_game_final(), sbr_twin_id(), test_no_final_anywhere_is_none(), test_scored_canonical_row_wins_and_keeps_its_label(), test_twin_id_swaps_only_the_renamed_franchises() (+1 more)

### Community 545 - "Job heartbeat and stale jobs"
Cohesion: 0.14
Nodes (8): Conn, _build(), test_a_job_marked_disabled_is_not_silent(), test_a_job_that_runs_here_is_not_marked(), test_a_service_leaves_alone_the_jobs_another_service_owns(), test_startup_marks_an_owned_job_that_is_switched_off(), failing_jobs(), stale_jobs()

### Community 55 - "NCAAF gameday context twin rows"
Cohesion: 0.13
Nodes (13): _Conn, _Result, _choose_context(), _has_pregame_lines(), load_context(), _night_twin(), _pair_key(), _row() (+5 more)

### Community 550 - "NFL prop backtest verdict tests"
Cohesion: 0.04
Nodes (26): TestSnapRows, TestVerdict, TestYesNoMarkets, _verdict(), test_a_half_line_market_priced_to_its_own_skew_is_not_flagged(), test_a_sharp_reference_is_never_a_book_we_bet(), test_a_targeted_backfill_never_substitutes_draftkings(), test_a_timing_run_can_be_labelled_so_it_cannot_displace_the_main_series() (+18 more)

### Community 551 - "MLB duplicate game id merge"
Cohesion: 0.13
Nodes (12): _Conn, apply_one(), canonical(), counts(), main(), plan(), test_a_canonical_id_maps_to_nothing(), test_a_non_mlb_or_malformed_id_is_left_alone() (+4 more)

### Community 554 - "NBA box score repair tests"
Cohesion: 0.13
Nodes (8): _Conn, boxes_to_repair(), _logs(), _run(), test_a_box_that_does_not_add_up_is_never_written(), test_a_game_nba_com_does_not_list_is_refused(), test_only_the_named_game_is_replaced_delete_first(), test_the_season_repair_names_every_missing_or_wrong_box()

### Community 56 - "tests/test_daily_retry.py"
Cohesion: 0.06
Nodes (42): _Conn, _Cursor, _FrozenDatetime, DailyRun, _aborted(), _aborted_row(), _ok(), _ok_row() (+34 more)

### Community 562 - "Results recap message id tests"
Cohesion: 0.05
Nodes (16): _Conn, _Ledger, _Resp, _silence_alert(), test_a_204_with_no_id_is_not_a_finished_recap(), test_a_failed_error_insert_rolls_back_before_the_read(), test_a_posted_recap_ledgers_the_id_wait_returned(), test_a_rejected_post_is_recorded_and_the_next_pass_sends() (+8 more)

### Community 563 - "X image upload and tweeting"
Cohesion: 0.16
Nodes (9): _Fetcher, _Uploader, ImageFetch, MediaUpload, test_a_failed_upload_does_not_tweet(), test_a_partial_upload_is_not_repeated_on_requeue(), test_a_rate_limit_after_one_upload_keeps_that_id(), test_an_image_is_uploaded_then_attached() (+1 more)

### Community 564 - "NFL prop market card publisher tests"
Cohesion: 0.19
Nodes (5): MarketBet, TestMarketCardPublisher, test_nfl_prop_market_card_drops_a_bet_under_the_floor(), test_wnba_prop_market_card_drops_a_bet_under_the_floor(), execute()

### Community 566 - "Odds repeat thinning keeps NBA rows"
Cohesion: 0.14
Nodes (10): _Conn, thin_repeats(), test_a_thinning_error_that_is_not_a_timeout_is_raised(), test_a_dry_run_counts_and_deletes_nothing(), test_an_unchanged_run_keeps_its_first_and_last_row(), test_every_move_survives_and_every_as_of_price_is_unchanged(), test_paid_history_todays_games_and_other_sports_are_untouched(), test_pre_game_and_in_play_are_separate_runs() (+2 more)

### Community 568 - "NFL weather and opener cards"
Cohesion: 0.03
Nodes (72): OddsAPIClient, SnapshotResult, OpenMeteoError, bettable_books(), _key(), _ledger_bump(), _ledger_read(), ledger_status() (+64 more)

### Community 57 - "tests/test_live_book_move_guard.py"
Cohesion: 0.10
Nodes (31): BookMoveClock, american_to_implied(), _at(), _delaware_ctx(), _dk(), _iso(), _ncaaf_engine(), _nfl() (+23 more)

### Community 570 - "NHL player props card tests"
Cohesion: 0.05
Nodes (18): TestEveryLiveModelIsWiredEverywhere, TestInsertOnce, TestTheBacktestGradesTheRuleTheCardPlays, TestTheCard, TestTheGoalieFrame, TestTheLimitPerGame, TestTonightsRowIsATrainingRow, card() (+10 more)

### Community 571 - "NFL pick monitor game id join"
Cohesion: 0.16
Nodes (3): TestTheJoinKeyMatchesPicks, eval_row(), _picks_game_id()

### Community 579 - "Umpire ingest and script utilities"
Cohesion: 0.03
Nodes (35): TestTheOddsFetchReachesTomorrow, _Clock, TestHealWindowLo, backfill_umpires(), _fetch_umpires_for_date(), _heal_window_lo(), ingest_umpires_for_date(), run_umpire_ingestor() (+27 more)

### Community 583 - "NFL pick monitor"
Cohesion: 0.14
Nodes (7): TestClassify, TestImmutabilityContract, TestLatestPerPick, TestWindPublisherLock, classify(), latest_per_pick(), _row()

### Community 584 - "In-play game clock alignment"
Cohesion: 0.24
Nodes (6): GameClock, _t(), test_before_first_pitch_and_after_last_play_are_not_priced(), test_between_pas_across_third_out_rolls_over_to_next_half(), test_mid_plate_appearance_is_that_pa_before_state(), test_plays_without_times_are_ignored()

### Community 59 - "Discord and X results notifier"
Cohesion: 0.03
Nodes (59): _Posted, _Rejected, step_settle(), test_a_restate_with_nothing_settled_late_is_a_no_op(), test_clv_line_is_empty_when_nothing_was_measured(), test_free_pick_does_not_fall_back_to_the_default_channel(), test_the_record_restatement_and_the_slate_restatement_are_separate(), test_embeds_chunk_at_the_field_cap_and_the_size_cap() (+51 more)

### Community 590 - "Prop odds missing game insert tests"
Cohesion: 0.15
Nodes (4): FakeConn, _run(), test_event_with_no_games_row_is_skipped_and_others_still_insert(), test_fk_on_insert_does_not_unwrite_the_events_that_already_landed()

### Community 595 - "NHL blocked shots prop settlement tests"
Cohesion: 0.27
Nodes (5): _Shim, TestSettlement, _bet(), _played(), _result()

### Community 599 - "System health check test fixtures"
Cohesion: 0.14
Nodes (4): _FrozenDatetime, _Shim, db(), mlb_wired()

### Community 6 - "Mobile model catalog and thresholds"
Cohesion: 0.01
Nodes (362): Case, Bucket, FixturePick, Nav, CustomBacktestPickRow, CustomBacktestSummary, CustomModelStats, ChipGroup (+354 more)

### Community 601 - "Team stats live season span checks"
Cohesion: 0.13
Nodes (6): _SeasonConn, test_verify_established_live_season_with_two_snapshots_stays_thin(), test_verify_five_day_span_with_one_snapshot_is_thin(), test_verify_four_day_opening_span_is_still_grace(), test_verify_opening_live_season_is_not_thin(), test_verify_short_historical_season_is_still_thin()

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
Cohesion: 0.08
Nodes (18): TestPublishOpenerInsertOnce, _LockConn, TestNoneRowNeverLocks, _changed(), _clear_scored_row(), _flush_board_safe(), _flush_snapshots_safe(), latest_eval_rows() (+10 more)

### Community 63 - "Football in-play game state"
Cohesion: 0.11
Nodes (19): GameState, _as_float(), _as_int(), _as_opt_float(), _as_opt_int(), from_espn(), from_extract(), from_pbp_row() (+11 more)

### Community 633 - "Price prefilter timeout rollback tests"
Cohesion: 0.15
Nodes (9): _PoisonConn, _event_index(), _games(), _run(), test_a_failed_savepoint_rollback_falls_back_to_full_rollback(), test_both_prefilters_timing_out_still_reaches_the_pipeline_log(), test_lookahead_timeout_rolls_back_and_scoring_continues(), test_ncaaf_timeout_rolls_back_and_scoring_continues() (+1 more)

### Community 639 - "NFL prop local odds cache"
Cohesion: 0.26
Nodes (5): TestLocalOddsCache, _odds_from_frame(), _p(), _odds_frame(), test_a_one_way_market_stays_one_way_through_the_cache()

### Community 644 - "Market sweep and holdout scripts"
Cohesion: 0.02
Nodes (68): Pick, _fmt_edge(), _fmt_odds(), main(), _pick_card(), render_email(), fetch_season(), _get() (+60 more)

### Community 650 - "Mobile matchup and stats verify scripts"
Cohesion: 0.03
Nodes (94): MatchupGrade, MatchupInfo, TonightMatchupRow, walk(), check(), fakeServer(), main(), read() (+86 more)

### Community 651 - "NFL wind bettable book filter"
Cohesion: 0.09
Nodes (7): TestTheCardFilters, TestTheListIsShared, _load_backtest(), main(), selected_bets(), _attach(), _quote()

### Community 655 - "Mobile bankroll unit percent settings"
Cohesion: 0.32
Nodes (7): BankrollSettings, useBankroll(), canStepUnitPct(), sanitizeUnitPct(), stepUnitPct(), store, BANKROLL_DEFAULTS

### Community 658 - "NBA official injury report parser"
Cohesion: 0.11
Nodes (16): Report, _bands(), _column_of(), _columns(), finish_rows(), _hrules(), _lines_of(), parse_page_layout() (+8 more)

### Community 659 - "Social post enqueue checks"
Cohesion: 0.19
Nodes (9): QueueRejected, test_enqueue_inserts_a_thread_and_refuses_a_second_copy(), test_enqueue_refuses_a_url_unless_allow_link_is_set(), test_enqueue_stores_images_and_a_reply_target(), _checked_media_urls(), _checked_reply(), enqueue(), posts_to_rows() (+1 more)

### Community 668 - "NBA public splits late-game archiving"
Cohesion: 0.12
Nodes (6): _NoDB, _Store, _scoreboard(), test_a_late_game_still_in_play_after_midnight_is_archived_at_the_next_pass(), test_a_stored_game_is_not_written_again_and_a_splitless_game_is_retried(), _wire_archive()

### Community 67 - "tests/test_game_market_gate.py"
Cohesion: 0.06
Nodes (49): GateVerdict, MarketBookend, PublicSplits, apply_to_picks(), _as_float(), bookend_from_odds(), evaluate(), fair_prob() (+41 more)

### Community 670 - "NBA team total closing line tests"
Cohesion: 0.11
Nodes (14): _SnapConn, _book(), _capture(), _lateral(), _oc(), _quotes(), _team_total_pick(), test_a_close_at_the_same_number_is_graded_against_the_bet_book_s_close() (+6 more)

### Community 671 - "NHL prop EV regimes and Kalshi ladders"
Cohesion: 0.07
Nodes (20): TestRegimeOrder, best_per_player(), blocked_sides(), engine_sides(), history(), pool(), main(), regime() (+12 more)

### Community 674 - "NBA public splits quality backfill"
Cohesion: 0.18
Nodes (5): _CountingConn, backfill_quality(), test_an_existing_table_gets_the_quality_column(), test_the_backfill_adds_the_column_and_commits_once(), test_the_backfill_rolls_back_when_a_count_is_not_what_was_measured()

### Community 675 - "Pipeline watch findings and alerts"
Cohesion: 0.04
Nodes (43): _Conn, collect(), test_a_clean_pass_produces_no_finding(), test_a_clean_run_still_posts(), test_a_confirmed_post_is_ledgered_so_the_run_can_be_verified(), test_a_failed_ledger_does_not_lose_the_report(), execute(), test_a_failed_query_rolls_back_and_does_not_sink_the_run() (+35 more)

### Community 678 - "NFL prop market card tests"
Cohesion: 0.22
Nodes (3): TestMarketCard, execute(), fetchall()

### Community 68 - "NBA second-model prop study"
Cohesion: 0.05
Nodes (42): Shape, base_key(), match_names(), appearances(), box_tables(), build(), check_close_prior(), consensus_number() (+34 more)

### Community 683 - "Probability calibration map tests"
Cohesion: 0.05
Nodes (26): _FakeConn, _era_start(), fit_model(), test_a_map_that_does_not_help_out_of_sample_is_not_applied(), test_a_map_that_helps_is_applied(), test_a_model_with_no_record_takes_the_pooled_correction(), test_a_model_with_too_few_graded_picks_gets_the_shrunk_offset_not_a_platt_map(), test_a_side_under_0_5_never_comes_out_as_the_favourite() (+18 more)

### Community 688 - "Bounded odds pruning and thinning"
Cohesion: 0.12
Nodes (9): _Ctx, main(), run_prune_odds(), test_prune_rejects_keep_days_below_one(), test_a_thinning_failure_still_prunes_both_tables_and_is_reported(), test_every_statement_the_prune_sends_names_its_game(), test_the_daily_run_gives_the_thinning_a_budget(), thin() (+1 more)

### Community 69 - "tests/test_pick_integrity.py"
Cohesion: 0.03
Nodes (47): _Conn, _Shim, _add_pick(), discord_sent(), _health(), health_db(), test_a_label_may_not_name_a_market_the_pick_does_not_settle_on(), test_a_label_naming_the_other_team_is_refused() (+39 more)

### Community 690 - "NHL derivative totals card tests"
Cohesion: 0.12
Nodes (8): _Meter, _Resp, _markets(), test_apply_and_probe_without_a_key_return_before_any_call(), test_parser_splits_team_totals_and_keeps_every_alternate_line(), test_profit_pays_the_side_that_won(), test_pull_buys_the_game_with_no_credit_stop(), test_snapshot_after_start_is_in_play()

### Community 691 - "Paused bets keep real verdict tests"
Cohesion: 0.18
Nodes (3): _Capture, test_a_paused_settled_bet_never_moves_the_kelly_bankroll(), test_todays_standing_bets_ignore_a_paused_row()

### Community 693 - "NHL prop newest fetch shopping tests"
Cohesion: 0.24
Nodes (3): _Conn, TestOnlyTheNewestFetchIsShopped, fetchall()

### Community 694 - "Calibration schema column tests"
Cohesion: 0.17
Nodes (4): _SchemaRecordingConn, test_persist_still_creates_them_too(), test_promote_creates_the_columns_it_writes_to(), test_the_alters_come_before_any_write_in_both_paths()

### Community 7 - "Database connection and feature builders"
Cohesion: 0.01
Nodes (155): DBConnection, TestMarketForOdds, _Conn, connection_lost(), _go(), release_read(), pregame_cutoff_sql(), _upsert_savant_stats() (+147 more)

### Community 70 - "tests/test_record_one_pick_per_event.py"
Cohesion: 0.04
Nodes (47): _CaptureConn, _RecordingConn, duplicate_copy_exclusion_sql(), _code(), _copy_for_node(), _fn(), _node(), _read() (+39 more)

### Community 704 - "NFL odds event game matching"
Cohesion: 0.29
Nodes (3): TestResolveGameId, resolve_nfl_game_id(), resolve()

### Community 708 - "Weekly job catch-up tests"
Cohesion: 0.18
Nodes (3): _Conn, test_a_failing_savant_refresh_does_not_cost_the_calibration_its_catch_up(), test_ownership_is_checked_per_job()

### Community 71 - "Shared database connection and sweeps"
Cohesion: 0.02
Nodes (121): _Unset, live_slate_dates(), scoring_method(), _connect(), get_connection(), _open(), _session_options(), use_poller_session() (+113 more)

### Community 711 - "Pipeline report rollback tests"
Cohesion: 0.13
Nodes (7): _Conn, main(), render(), _rows(), test_a_failed_query_rolls_back(), test_every_section_is_still_present(), test_one_broken_section_does_not_break_the_rest()

### Community 73 - "nfl/live_model/tests: test_props + props"
Cohesion: 0.09
Nodes (33): PropProjection, PlayerState, _accrued(), _count(), detect_inactive(), price_over(), project(), _rate() (+25 more)

### Community 755 - "NFL prop player name matching"
Cohesion: 0.02
Nodes (124): TestKickoffGate, TestLocalCacheGuards, TestMarketGrading, TestNormaliseName, _event_date(), fetch_series(), ladders(), ladders_or_empty() (+116 more)

### Community 758 - "Deploy checks and job queue"
Cohesion: 0.07
Nodes (17): _Conn, test_a_declared_job_carries_its_run_after(), test_a_failing_check_raises_so_the_queue_announces_it(), test_a_job_can_only_name_a_registered_check(), test_enqueue_rejects_a_naive_run_after(), test_enqueue_stores_run_after(), test_every_check_is_read_only(), test_the_claim_waits_for_run_after() (+9 more)

### Community 77 - "tests/test_wnba_prop_market.py"
Cohesion: 0.05
Nodes (29): _FakeConn, _QuoteConn, apply_price_floor(), norm_name(), pick_rows(), player_ids(), publish(), render() (+21 more)

### Community 78 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.06
Nodes (23): _After, _Conn, _RaceConn, TestBuildScoredRows, TestFlexedKickoffRefreshes, TestLockSurvivesNothing, TestNoneRowBesideABetIsCleared, TestPickEmLabel (+15 more)

### Community 79 - "NHL derivative totals walk-forward model"
Cohesion: 0.07
Nodes (37): Market, build_p1_frame(), build_team_frame(), day_interval(), _ew(), fit(), game_means(), _implied_vec() (+29 more)

### Community 84 - "NBA prop cards across models"
Cohesion: 0.03
Nodes (86): ProjectionBet, Plan, _Conn, ev_percentile(), decided_games(), ensure_decisions_table(), games_with_a_bet(), main() (+78 more)

### Community 848 - "Prop odds book update time"
Cohesion: 0.26
Nodes (6): _Conn, _parse(), test_a_row_built_without_the_key_still_inserts_as_null(), test_no_clock_anywhere_is_none_not_our_fetch_time(), test_the_column_is_added_only_when_the_catalog_lacks_it(), test_the_markets_own_clock_is_stored_else_the_books()

### Community 85 - "tests/test_recap_retries_a_skipped_day.py"
Cohesion: 0.07
Nodes (24): _LiteConn, World, _add_pick(), _grade(), _lite(), _schema(), test_a_day_with_nothing_counting_posts_nothing_and_logs_nothing(), test_a_failed_receipt_never_reposts_the_day() (+16 more)

### Community 850 - "Game-day workers and shared stdlib"
Cohesion: 0.02
Nodes (84): LiveOddsFeed, Quote, CreditBudgetExceeded, JsonlRecorder, Plan, _Conn, _mark_written(), now_iso() (+76 more)

### Community 852 - "NFL injury index loader"
Cohesion: 0.22
Nodes (3): _InjConn, load_nfl_injury_index(), test_loader_keys_by_norm_name_and_skips_empty()

### Community 854 - "NFL prop pulls and recap error tests"
Cohesion: 0.07
Nodes (12): TestIngestEventsDoesNotShadowItsMarkets, test_the_halftime_distribution_refuses_a_choosing_season_without_enough_earlier_games(), rows(), fetchall(), test_live_prop_pull_asks_for_the_sharp_book(), fake_event_props(), fetchall(), fetchall() (+4 more)

### Community 870 - "NFL player stats and props ingestion"
Cohesion: 0.03
Nodes (40): TestParsePlayerRows, TestParseNflverseScores, backfill_nfl_player_stats(), current_nfl_season(), _fetch_game_dates(), _fetch_season_csv(), ingest_nfl_player_stats(), parse_player_week_csv() (+32 more)

### Community 871 - "NHL player props scoring card"
Cohesion: 0.07
Nodes (18): TestFourNhlPropBetsANight, TestWhoThePlayerIs, name_key(), step_nhl_prop_scoring(), candidates(), draftkings_at(), existing_picks(), games_with_a_prop_bet() (+10 more)

### Community 88 - "NBA prop market decision tests"
Cohesion: 0.05
Nodes (51): NbaPropBet, _PublishConn, _SettleConn, pick_label(), pick_rows(), _bet(), _decision(), fair_under() (+43 more)

### Community 893 - "NBA injury report date scope"
Cohesion: 0.33
Nodes (3): _DatesConn, scope_dates(), test_scope_is_every_game_date_and_the_day_before_newest_first()

### Community 9 - "NFL early-signal publishing tests"
Cohesion: 0.08
Nodes (15): _Conn, _sql_for(), test_a_started_game_is_still_never_published(), test_both_publishers_apply_the_apps_action_filter(), test_both_publishers_read_the_table_the_app_reads(), test_capture_reaches_as_far_as_the_poller_can_write(), test_capture_reaches_forward_for_the_locked_lookahead_sports(), test_ncaaf_lookahead_is_only_safe_because_the_lock_is_general() (+7 more)

### Community 904 - "NBA team total odds billed feed stub"
Cohesion: 0.22
Nodes (4): FakeFeed, fn(), logged(), call()

### Community 914 - "WNBA injury adjustment features"
Cohesion: 0.11
Nodes (5): TestComputeInjuryAdjustment, TestHasReturnee, _compute_injury_adjustment(), _has_returnee(), _assemble_wnba_features()

### Community 92 - "tests/test_ncaaf_prop_odds.py"
Cohesion: 0.05
Nodes (27): _Conn, _Resp, _market_chunks(), _football_map(), resolver(), scope(), test_a_book_we_did_not_ask_for_is_never_written(), test_a_day_with_no_college_games_spends_nothing() (+19 more)

### Community 926 - "MLB opposing starter feature tests"
Cohesion: 0.09
Nodes (15): _StubConn, _StubResult, _opp_starter_savant(), _starter_gb_pct(), _batter_bulk(), test_batter_bulk_carries_everything_opp_starter_savant_reads(), test_it_reads_the_starters_savant_row(), test_live_mode_falls_back_to_prior_season() (+7 more)

### Community 93 - "MLB totals public fade model"
Cohesion: 0.04
Nodes (71): PublicFadeBet, _EmptyConn, _better_under(), composite_score(), edge_floor(), estimated_edge(), find_fade_bets(), is_pre_commence() (+63 more)

### Community 94 - "NCAAF in-play score distribution pricing"
Cohesion: 0.03
Nodes (56): ScoreDistribution, _cluster_bootstrap(), evaluate(), main(), report(), fit(), load_states(), main() (+48 more)

### Community 95 - "tests/test_ncaaf_pbp_store.py"
Cohesion: 0.09
Nodes (18): _Conn, load_season_from_db(), _report_ranges(), store_season(), _plays(), test_a_rerun_updates_rather_than_duplicating(), test_a_season_in_neither_place_is_an_error_not_a_short_corpus(), test_a_season_survives_the_round_trip_in_the_cfbd_spelling() (+10 more)

### Community 96 - "tests/test_heartbeat_watchdog.py"
Cohesion: 0.08
Nodes (25): _FakeConn, _FakeCursor, _break_db(), sink(), test_a_failed_post_does_not_start_the_throttle(), test_a_healthy_start_never_announces_a_recovery(), test_a_returning_outage_alerts_again_immediately(), test_a_silent_failure_alerter_is_caught_by_the_watchdog() (+17 more)

### Community 97 - "NCAAF in-play quote selection engine"
Cohesion: 0.05
Nodes (21): GameContext, LiveEngine, american_to_prob(), devig_power(), best_takeable_quote(), expected_value(), _is_paused(), market_is_takeable() (+13 more)

### Community 99 - "Record correction social posts"
Cohesion: 0.06
Nodes (28): Ledger, _Result, _pin(), _real_post(), _real_tweet(), x_posts(), _publish(), test_a_failed_discord_ledger_does_not_send_x() (+20 more)

### Community 636 - "Pipeline run start and orphan cleanup"
Cohesion: 0.21
Nodes (7): _abort_orphans(), abort_prior_refresh_orphans(), _boot_cutoff(), finish_run(), main(), _now(), start_run()

### Community 100 - "NFL edge research shared helpers"
Cohesion: 0.03
Nodes (125): backfill_cost(), bets(), bh(), clean_2h(), fmt(), forward_2026(), hdr(), _line_models() (+117 more)

### Community 101 - "NBA second game market fair prices"
Cohesion: 0.06
Nodes (37): cache_for(), check_cells(), combine_times(), f2_cells(), f2_point(), f6a_placebo(), f6a_point(), f6a_strength() (+29 more)

### Community 102 - "scripts/nfl_edge_live_rush_pace.py"
Cohesion: 0.18
Nodes (26): _asof(), boot_p(), build_state(), first(), grade(), initial_last(), load_pbp(), main() (+18 more)

### Community 103 - "NBA prop projection tests"
Cohesion: 0.06
Nodes (28): _art(), _proj(), _q(), _run(), _settle(), test_a_book_hanging_two_lines_for_one_player_is_refused(), test_a_decision_with_no_bet_is_still_a_decision(), test_a_past_game_never_projected_gets_the_newest_espn_pull_55_minutes_before_its_tip() (+20 more)

### Community 104 - "NFL preregistered 2026 edge study"
Cohesion: 0.09
Nodes (39): bar(), bets_frame(), bh(), binom_line(), _by_game(), cell(), fam(), first_last() (+31 more)

### Community 107 - "tests/test_prop_calibrated_decision.py"
Cohesion: 0.07
Nodes (26): dedupe_player_props(), _bet(), _identity_cal(), _prop(), test_a_genuinely_big_edge_still_fires_after_calibration(), test_a_hot_prop_model_no_longer_fires_the_marginal_bet(), test_a_model_outside_every_pool_is_untouched(), test_a_pick_with_no_player_id_never_participates() (+18 more)

### Community 109 - "NBA fourth search derivative markets"
Cohesion: 0.07
Nodes (31): calibrated_refs(), cell_specs(), choosing(), decision_quotes(), derivative_data(), emit_f1(), emit_f4(), f1_fair() (+23 more)

### Community 110 - "tests/test_mobile_line_movement.py"
Cohesion: 0.08
Nodes (27): _fn(), _read(), _run(), test_a_cut_table_keeps_the_pick_and_says_what_it_covers(), test_a_cut_window_keeps_the_pick_row_on_the_8_row_table(), test_a_pick_made_after_the_cards_start_never_reads_since_your_pick(), test_after_the_start_the_verdict_is_not_graded(), test_an_old_snapshot_is_not_the_price_at_the_pick() (+19 more)

### Community 111 - "In-play calibration analysis"
Cohesion: 0.06
Nodes (33): pick(), test_a_peak_with_no_plateau_anywhere_is_labelled_as_one(), test_a_prob_cut_and_an_ev_cut_select_different_picks(), test_calibration_also_scores_ev_against_realised_roi(), test_calibration_is_empty_rather_than_wrong_with_nothing_settled(), test_calibration_reports_the_gap_between_claim_and_reality(), test_expected_value_matches_the_hand_calculation(), test_expected_value_refuses_a_missing_or_zero_price() (+25 more)

### Community 112 - "NBA in-game luck study one"
Cohesion: 0.08
Nodes (29): threshold(), attach_rates(), build(), close_totals(), decisions(), eligible(), fair_mu(), fit_w() (+21 more)

### Community 117 - "NBA lineup stint derivation tests"
Cohesion: 0.08
Nodes (45): order_plays(), _blowout_q4(), derive(), dreb(), _dup_game(), end_period(), five_game(), make2() (+37 more)

### Community 118 - "NBA play-by-play parsing tests"
Cohesion: 0.06
Nodes (29): _last(), match_games(), match_names(), resolve_map(), _g(), _game_recs(), _rec(), _summary() (+21 more)

### Community 119 - "tests/test_ncaaf_live_notify.py"
Cohesion: 0.05
Nodes (18): _load_write_picks(), _restore_stubbed_modules(), test_a_caller_supplied_connection_is_not_closed_by_the_write(), test_a_failing_notifier_never_breaks_pricing(), test_a_full_slate_announces_once(), test_a_live_bet_notifies_push_and_discord(), test_a_locked_lane_is_not_rewritten(), test_a_locked_lane_keeps_notifying_after_the_engine_stops_betting() (+10 more)

### Community 122 - "NCAAF quarterback team features"
Cohesion: 0.19
Nodes (16): build_qb_team_features(), _feat(), _frame(), _qb_rows(), test_a_games_features_never_use_that_game(), test_current_qb_is_the_previous_games_primary(), test_empty_input_returns_the_right_shape(), test_first_game_has_no_qb_features_at_all() (+8 more)

### Community 124 - "NHL prop backtest shared-name guard"
Cohesion: 0.38
Nodes (6): namesakes(), _frame(), test_a_namesake_who_played_for_the_team_last_season_still_counts(), test_a_unique_name_is_kept(), test_namesakes_on_two_teams_collide_only_when_those_teams_meet(), test_two_teammates_with_one_name_are_both_refused()

### Community 126 - "Live monitor dashboard data store"
Cohesion: 0.10
Nodes (23): meta(), ops(), snapshot(), api_rollup(), call_timeline(), calls_since(), community(), scalar() (+15 more)

### Community 127 - "NBA fifth search grid tests"
Cohesion: 0.04
Nodes (26): _blend_world(), _cell(), _grid(), _mid(), ran(), _tb_rows(), test_a_losing_band_above_the_cut_fails_too_and_a_thin_band_is_not_judged(), test_a_losing_band_below_the_cut_fails_a_cell_its_nested_neighbours_pass() (+18 more)

### Community 128 - "tests/test_settled_record_is_immutable.py"
Cohesion: 0.05
Nodes (23): _code(), test_a_dedicated_live_lane_still_counts_and_a_pre_game_in_play_pick_does_not(), test_a_paused_model_is_not_an_excluded_model(), test_a_voided_pick_is_still_out_of_the_record(), test_both_published_views_keep_the_live_date_gate(), test_both_rules_name_the_two_exits_and_not_the_paused_flag(), test_both_views_are_redefined_by_name(), test_every_explicit_exclusion_names_who_asked_for_it() (+15 more)

### Community 130 - "features/golf_feature_engine.py"
Cohesion: 0.08
Nodes (27): assemble_player_features(), _avg_finish(), compute_golf_target(), compute_matchup_target(), _event_finishes(), _f(), _field_features(), _made_cut_rate() (+19 more)

### Community 132 - "NCAAF in-play state building tests"
Cohesion: 0.13
Nodes (22): build_states(), _platform(), _plays(), _post_convention_game(), _pre_convention_game(), test_a_scoring_plays_state_does_not_contain_its_own_points(), test_ambiguous_convention_refuses_to_build(), test_halftime_scores_carried_for_2h_settlement() (+14 more)

### Community 133 - "tests/test_bovada_feed.py"
Cohesion: 0.11
Nodes (29): _american(), _complete(), _num(), parse_coupon(), _row_for(), _seen_key(), _stamp(), _coupon() (+21 more)

### Community 136 - "NCAAF cross-book opener tests"
Cohesion: 0.06
Nodes (27): _minutes_apart(), build_artifact(), build_band_artifact(), main(), register(), _branch(), test_absent_ceiling_means_unbounded(), test_artifact_shape() (+19 more)

### Community 137 - "NFL 2024 in-play totals grading"
Cohesion: 0.11
Nodes (39): s(), books_per_snapshot(), cell(), h1(), h1_calibration(), h1_frame(), h2(), h2_accuracy() (+31 more)

### Community 138 - "tests/test_paused_keeps_real_verdict.py"
Cohesion: 0.07
Nodes (33): _bet(), _bodies(), _code(), _fn(), _pause(), _prop(), _rules(), _sql_of() (+25 more)

### Community 139 - "NFL 2025 in-play edge research"
Cohesion: 0.08
Nodes (44): finalize_states(), fit_models(), states(), summ(), async_check(), attach_games(), attach_state(), bh() (+36 more)

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

### Community 153 - "tests/test_agents_contract.py"
Cohesion: 0.05
Nodes (20): _labelled_retired(), test_blocked_items_are_marked_so_the_agent_skips_them(), test_every_backlog_item_is_a_checkbox(), test_neither_agent_may_change_a_model_threshold(), test_the_agents_are_findable_from_the_file_every_session_reads(), test_the_backlog_does_not_promise_an_agent_that_no_longer_runs(), test_the_backlog_exists_and_has_items(), test_the_contract_documents_every_agent_by_name() (+12 more)

### Community 158 - "NFL prop market information tests"
Cohesion: 0.08
Nodes (28): closing_prices(), devig(), ecdf_p_over(), main(), bets(), design(), main(), analyse() (+20 more)

### Community 159 - "WNBA results ingestor"
Cohesion: 0.07
Nodes (36): build_log_row(), _core_athlete(), _deref(), _et_date(), _fetch_core_box_players(), _fetch_core_games(), _fetch_scoreboard(), _fetch_summary() (+28 more)

### Community 16 - "NBA public betting splits ingestor"
Cohesion: 0.11
Nodes (16): active_queries(), archive_ready(), ensure_table(), fetch_scoreboard(), keep_for_poll(), _known_abbrs(), load_games_index(), not_started() (+8 more)

### Community 161 - "NBA box score enrichment"
Cohesion: 0.07
Nodes (50): _blank(), box_rows(), _check_unmapped(), _create(), dnp_kind(), ensure_tables(), fetch_advanced(), fill_missing_game_logs() (+42 more)

### Community 163 - "NBA derivative market lab"
Cohesion: 0.09
Nodes (35): add_team(), am_to_dec(), bars_for(), bet_list(), blind(), boot_ci(), build_line_rows(), build_outcomes() (+27 more)

### Community 167 - "scripts/nfl_preflight.py"
Cohesion: 0.19
Nodes (17): _load_postgres_schema(), check(), check_cards_run(), check_config_gates(), check_cost(), check_data(), data_check(), check_import_shadowing() (+9 more)

### Community 168 - "Mobile live board segment tests"
Cohesion: 0.06
Nodes (28): _read(), test_a_sport_switch_cannot_report_a_game_finishing(), test_all_three_segments_are_unconditional(), test_live_is_not_a_bottom_tab(), test_live_is_not_in_the_tab_param_list(), test_no_app_root_component_reaches_a_focus_aware_hook(), imports_of(), strip_comments() (+20 more)

### Community 169 - "NBA halftime in-game research"
Cohesion: 0.08
Nodes (24): add_features(), attach_close(), build_halves(), centre(), day_ci(), decision_games(), decision_quotes(), first_part() (+16 more)

### Community 171 - "Ops alert watchdog and state"
Cohesion: 0.07
Nodes (19): auto_pause_caveat(), _is_health_check_step(), _latest_health_rows(), _pass_is_clean(), _producer_failures(), run_failure_alerter(), _step_names(), _alert() (+11 more)

### Community 172 - "MLB stats and pitcher ingestion"
Cohesion: 0.06
Nodes (25): backfill_bullpen_stats(), backfill_mlb_stats(), backfill_pitcher_stats(), backfill_player_game_log(), backfill_player_handedness(), _build_pitcher_rows(), _build_team_stats_rows(), _fetch_mlb_api_batting() (+17 more)

### Community 173 - "tests/test_decide_on_calibrated.py"
Cohesion: 0.06
Nodes (19): _pick(), _pick_at(), test_a_calibrated_cut_is_paired_with_a_calibrated_decision(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(), test_a_genuinely_big_edge_still_fires_after_calibration(), test_a_hot_model_no_longer_fires_the_marginal_bet(), test_a_model_on_a_calibrated_cut_is_not_paused(), test_a_paused_model_never_fires_regardless() (+11 more)

### Community 176 - "NBA prop projection lab"
Cohesion: 0.09
Nodes (47): implied(), bars(), bh_read(), blind(), boot(), by(), cal_ab(), candidates() (+39 more)

### Community 178 - "NBA team total luck card"
Cohesion: 0.15
Nodes (8): step_mlb_total_public_fade(), step_nba_team_total_luck(), step_nba_total_luck(), load_quote_rows(), newest_fetch(), render(), run_card(), slate()

### Community 18 - "MLB game market betting card"
Cohesion: 0.19
Nodes (9): _get_public_betting(), main(), publish(), render(), run_both(), run_card(), _shadow_gate(), slate() (+1 more)

### Community 181 - "NBA in-game data staleness gate"
Cohesion: 0.04
Nodes (50): attach_pinnacle(), box_checks(), build(), drop_wild_wallclocks(), espn_map(), foul_flags(), is_heave(), keep_in_play() (+42 more)

### Community 182 - "tests/test_model_artifacts_load.py"
Cohesion: 0.09
Nodes (17): _git(), _gitignore_keep_pkls(), _ignored(), _manifest_keep_pkls(), _newest_per_model(), test_a_path_that_is_not_ignored_is_not_reported(), test_a_superseded_timestamped_pkl_is_ignored(), test_an_ignored_path_comes_back_byte_identical() (+9 more)

### Community 183 - "Mobile pick button and player detail tests"
Cohesion: 0.03
Nodes (55): test_every_revoke_names_the_roles_rather_than_public(), test_odds_keeps_select_for_the_app(), test_the_two_rls_off_tables_lose_everything(), test_it_is_dry_run_by_default(), _backfill_body(), test_a_game_absent_from_our_games_table_is_still_skipped(), test_no_skip_is_keyed_on_date_alone(), test_the_coverage_set_is_scoped_to_the_season_being_built() (+47 more)

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

### Community 191 - "Market-relative prop bet finder tests"
Cohesion: 0.09
Nodes (19): find_bets(), _q(), test_a_different_line_is_never_compared(), test_a_market_under_the_coverage_floor_is_excluded(), test_a_prop_the_sharp_book_did_not_price_is_counted_not_traded(), test_agreement_produces_no_bet(), test_an_equal_line_with_a_real_disagreement_is_a_bet(), test_devig_removes_the_hold_symmetrically() (+11 more)

### Community 194 - "NFL prop injury veto"
Cohesion: 0.13
Nodes (18): apply_injury_veto(), _as_dt(), player_is_vetoed(), should_veto(), test_equal_timestamps_veto(), _bet(), _idx(), _quotes() (+10 more)

### Community 195 - "tests/test_mobile_contrast_tokens.py"
Cohesion: 0.13
Nodes (29): _code_lines(), _ionicon_colors(), _lum(), _over(), _ratio(), _read(), _rgb(), test_badge_glyph_tracks_dynamic_type() (+21 more)

### Community 196 - "Monitor probe HTTP call recording"
Cohesion: 0.25
Nodes (9): _drain(), _enqueue(), _patch_curl_cffi(), _drain_dicts(), test_curl_cffi_calls_are_recorded_and_redacted(), test_curl_cffi_is_patched_only_once(), test_probe_records_failures_and_transport_errors(), test_probe_records_without_changing_the_response() (+1 more)

### Community 197 - "Daily pipeline runner and step imports"
Cohesion: 0.02
Nodes (60): run_bullpen_ingestor(), run_nfl_results_ingestor(), run_nba_prop_odds_ingestor(), run_wnba_prop_odds_ingestor(), format_view_migration_failure(), check_env(), _golf_enabled(), _import_step() (+52 more)

### Community 198 - "NBA game four part one tests"
Cohesion: 0.06
Nodes (32): _base(), _fair(), _ladder_quotes(), _offered(), _offers(), _period_games(), _rows(), _rung() (+24 more)

### Community 200 - "Pregame line poller change detection tests"
Cohesion: 0.06
Nodes (20): over_credit_cap(), _run_scorer_body(), test_a_failed_tick_does_not_kill_the_loop(), test_a_failed_tick_throws_the_map_away(), test_a_full_board_call_still_passes_no_subset(), test_a_zero_cap_means_uncapped(), test_an_empty_subset_scores_nothing_rather_than_everything(), test_every_housekeeping_delete_in_run_scorer_is_scoped_to_the_subset() (+12 more)

### Community 201 - "NBA second game line move tests"
Cohesion: 0.06
Nodes (39): _priced_season(), _q(), _sched(), _season_games(), _signal(), _split(), _stub_main(), test_a_fetch_after_T_never_reaches_the_move() (+31 more)

### Community 204 - "NBA team total luck builder"
Cohesion: 0.32
Nodes (6): bucket_counts(), build(), cell_bets(), main(), store(), tt_residuals()

### Community 207 - "NFL in-play prop flow anchoring tests"
Cohesion: 0.06
Nodes (22): grade(), grade_real(), naive_line(), _anchor_frame(), _long(), test_a_degenerate_line_is_dropped(), test_a_push_on_a_whole_number_line_is_not_a_loss(), test_accrual_is_as_of_the_mark_not_the_last_involvement() (+14 more)

### Community 212 - "NBA second game verdict"
Cohesion: 0.14
Nodes (14): axes_of(), bands_ok(), bar9(), cell_key(), _floats(), house_bar4(), house_verdict(), house_verdict_bands() (+6 more)

### Community 214 - "Probability calibration fitting and sweep"
Cohesion: 0.11
Nodes (18): demote(), ensure_schema(), fit_offset(), fit_platt(), fit_pool(), _gap_pp(), invert_calibration(), _logit() (+10 more)

### Community 217 - "NCAAF in-play pricing engine"
Cohesion: 0.08
Nodes (18): correct_for_pregame(), _load_pregame_calibration(), pregame_dog_points(), _real_artifact(), test_a_big_dog_is_marked_down_hard(), test_a_corrupt_artifact_leaves_the_probability_alone(), test_a_favourite_is_marked_up(), test_a_missing_artifact_leaves_the_probability_alone() (+10 more)

### Community 219 - "tests/test_nfl_live_leader_state.py"
Cohesion: 0.15
Nodes (18): situation(), status(), test_a_conversion_try_is_skipped(), test_a_previous_quarters_play_is_not_the_state(), test_a_timeout_is_skipped_for_the_play_before_it(), test_after_a_scoring_play_nothing_is_evaluated(), test_after_the_kickoff_lands_the_receiver_has_the_ball(), test_an_ordinary_snap_is_evaluable_with_the_training_inputs() (+10 more)

### Community 221 - "tests/test_ncaaf_qb_ingestor.py"
Cohesion: 0.12
Nodes (23): _athlete_stats(), _comp_att(), parse_qb_game_stats(), _pick(), _parse(), _payload(), _team(), test_athlete_stats_helper_is_category_scoped() (+15 more)

### Community 229 - "DraftKings feed freshness probes"
Cohesion: 0.09
Nodes (19): main(), probe_book(), verdict(), egress_ip(), _probe_once(), _proxies(), reachability(), _session() (+11 more)

### Community 236 - "NHL period scores ingestor"
Cohesion: 0.21
Nodes (8): agrees(), fetch(), main(), missing_dates(), rows_for_feed(), top_up(), _write(), test_the_final_may_exceed_the_periods_by_one_overtime_goal_and_nothing_else()

### Community 238 - "nfl/live_model/tests/test_rush_attempt_pace.py"
Cohesion: 0.09
Nodes (16): _price(), test_a_line_he_has_already_passed_is_not_a_live_proposition(), test_a_missing_accrued_count_is_refused_not_treated_as_zero(), test_a_reachable_over_is_declined_rather_than_faded(), test_a_surge_requirement_reaches_a_price(), test_no_bet_before_a_pace_exists(), test_settlement_resolves_this_model_per_pick_not_per_model_id(), test_the_book_move_guard_covers_the_new_market() (+8 more)

### Community 240 - "tests/test_ncaaf_game_identity.py"
Cohesion: 0.12
Nodes (16): _add(), _conn(), _identity_sql(), _run(), test_a_clean_slate_reports_nothing(), test_a_non_fbs_fixture_is_not_reported(), test_a_phantom_opponent_is_detected_too(), test_a_real_doubleheader_is_not_a_duplicate() (+8 more)

### Community 241 - "NBA second game market tests"
Cohesion: 0.10
Nodes (27): _close_frames(), _data(), _f2_games(), _f6a_data(), _f6d_total_data(), _game(), _pe(), _q() (+19 more)

### Community 243 - "Live monitor stale cache"
Cohesion: 0.15
Nodes (10): age(), cached(), clear(), test_cache_raises_when_it_has_nothing_to_fall_back_on(), test_cache_reports_age(), test_cache_serves_stale_rather_than_failing(), boom(), test_cache_serves_within_ttl_and_recomputes_after() (+2 more)

### Community 25 - "NBA game model research harness"
Cohesion: 0.04
Nodes (56): attach_fetch(), blind_by_real_side(), blind_pool(), blind_side(), boot(), cell_report(), cents(), check() (+48 more)

### Community 250 - "MLB in-play inning gate replay"
Cohesion: 0.13
Nodes (26): _grade(), _refuse_tables(), _game(), _price(), _scored(), _sig(), _state(), test_a_clean_control_prints_the_tables() (+18 more)

### Community 254 - "Kalshi prop ladder recording tests"
Cohesion: 0.10
Nodes (5): test_a_kalshi_outage_cannot_break_the_pass(), test_a_run_is_idempotent_within_its_snapshot(), test_one_snapshot_timestamp_for_the_whole_run(), test_the_recorder_is_scheduled_on_the_pipeline_role(), test_the_recorder_keeps_raw_prices_not_a_filtered_ladder()

### Community 255 - "UFC results download caching"
Cohesion: 0.08
Nodes (16): _cached_etag(), _etag_cache_path(), mirror_unchanged(), _store_etag(), step_ufc_results(), test_mirror_unchanged_is_conservative_when_it_cannot_tell(), _clean_env(), test_a_mounted_volume_is_preferred_over_tmp() (+8 more)

### Community 256 - "Prop market coverage probe tests"
Cohesion: 0.07
Nodes (18): candidate_markets(), _standard_markets(), test_a_two_sided_market_is_never_reported_one_sided(), test_an_all_line_leg_slip_does_not_claim_a_model(), test_it_asks_about_the_board_columns_that_are_permanently_blank(), test_it_reports_supported_but_empty_apart_from_unsupported(), test_no_market_is_asked_about_twice(), test_one_market_per_call_so_a_rejected_key_is_identified_exactly() (+10 more)

### Community 257 - "WNBA stats and game log ingestion"
Cohesion: 0.11
Nodes (18): rebuild_wnba_team_stats(), backfill_wnba_stats(), _build_game_id(), _build_game_rows(), _build_player_log_rows(), _build_team_stat_rows(), _fetch_league_game_log(), _ingest_season() (+10 more)

### Community 262 - "UFC fight feature builder"
Cohesion: 0.06
Nodes (38): _age_years(), _assemble_ufc_features(), _blk_career_stats(), build_ufc_game_features(), _bulk_fighter_id(), career_stats(), compute_ufc_target(), _fight_minutes() (+30 more)

### Community 263 - "Injury fetch athlete name cache"
Cohesion: 0.07
Nodes (11): _athlete_name(), _clear_cache(), test_a_dead_database_leaves_the_cache_empty_not_broken(), test_a_failed_lookup_is_not_cached(), test_a_known_athlete_costs_no_request(), test_a_SUCCESSFUL_response_with_no_name_is_not_cached(), test_an_unknown_athlete_is_fetched_and_then_remembered(), test_one_team_failing_does_not_lose_the_others() (+3 more)

### Community 266 - "NBA quarter game model tests"
Cohesion: 0.11
Nodes (29): _data(), _game(), _ladder(), _no_real_load(), _point(), _pricing_world(), _q(), _row() (+21 more)

### Community 267 - "NBA second game luck study"
Cohesion: 0.12
Nodes (16): f6c_offers(), f6c_signal(), game_situations(), _load_box(), main(), market_offers(), placebo_frames(), population() (+8 more)

### Community 268 - "No-vig capture and entrypoint guards"
Cohesion: 0.09
Nodes (15): _is_main_guard(), _modules_with_guard(), test_at_least_one_entrypoint_is_scanned(), test_nothing_is_defined_after_the_main_guard(), _fn(), test_a_missing_bet_book_close_is_not_filled_from_another_book(), test_backfill_revisits_anything_that_is_not_standard_v2(), test_capture_grades_raw_same_book_and_a_separate_pinnacle_edge() (+7 more)

### Community 271 - "Line CLV sign and orientation tests"
Cohesion: 0.07
Nodes (8): test_runner_captures_stdout_from_the_script_main(), _load(), test_a_line_that_held_is_exactly_zero_not_none(), test_a_missing_close_is_not_a_zero(), test_a_side_that_cannot_be_oriented_returns_none_rather_than_guessing(), test_the_home_and_away_sides_are_exact_mirrors(), test_the_prop_market_flag_wins_over_the_market_string(), test_the_signs_are_the_negation_of_the_apps_entry_frame()

### Community 276 - "UFC fight results scraper"
Cohesion: 0.11
Nodes (15): backfill_ufc_stats(), _build_ufc_game_id(), _fetch_event(), _fetch_event_list(), _fetch_fight(), _fetch_fighter(), _get(), _home_win_for_row() (+7 more)

### Community 280 - "NFL in-play flow slice backtest"
Cohesion: 0.13
Nodes (17): _clustered_ci(), main(), _qcut(), _rows_for(), slice_table(), verdict(), _frame(), _table() (+9 more)

### Community 284 - "Weekly and monthly results recap timing"
Cohesion: 0.07
Nodes (18): _at(), test_a_later_weekday_still_retries_that_week(), test_a_week_that_crosses_months_names_both(), test_an_evening_with_a_live_game_waits_for_the_next_morning(), test_discord_period_uses_the_results_webhook_and_ledgers_once(), test_monday_at_730_opens_the_prior_mon_sun_week(), test_monday_before_730_has_not_opened_the_new_week(), test_sunday_does_not_open_the_week_that_is_still_in_progress() (+10 more)

### Community 287 - "Model calibration check tests"
Cohesion: 0.07
Nodes (14): _calibration_sql(), test_a_flagged_model_is_named_eligible_or_not(), test_a_thin_model_is_still_excluded_rather_than_accused(), test_eligibility_notes_must_not_sink_the_gap_check(), test_eligibility_notes_parse_the_payload_verdicts(), test_it_grades_the_calibrated_probability_not_the_raw_one(), test_it_joins_picks_to_reach_the_calibrated_column(), test_the_check_has_a_skip_budget_that_survives_a_regime_change() (+6 more)

### Community 288 - "MLB live game state poller"
Cohesion: 0.12
Nodes (23): _bases_state(), _detect_triggers(), _extract_state(), _is_active_or_starting_soon(), test_active_in_progress_game_is_active(), test_bases_state_empty(), test_bases_state_loaded(), test_bases_state_single_runner() (+15 more)

### Community 29 - "NCAAF college data ingestor"
Cohesion: 0.05
Nodes (47): backfill_ncaaf_lines(), backfill_ncaaf_players(), backfill_ncaaf_qb(), _date_or_none(), _existing_ncaaf_ids(), _fold(), _get(), ingest_ncaaf_game_log() (+39 more)

### Community 291 - "NFL prop pulled quote filter"
Cohesion: 0.32
Nodes (8): drop_pulled_quotes(), _ts(), _q(), test_a_book_on_its_own_cadence_is_not_penalised_inside_three_hours(), test_a_book_that_stopped_returning_the_game_is_dropped(), test_a_player_the_book_stopped_quoting_is_dropped(), test_a_whole_market_the_book_pulled_is_dropped(), test_rows_from_one_fetch_minutes_apart_are_kept_and_a_line_move_is_not_a_pull()

### Community 293 - "Historical odds backfill tests"
Cohesion: 0.05
Nodes (21): relabel_in_play(), test_the_in_play_relabel_uses_the_better_bound(), test_a_rerun_can_be_told_to_ignore_the_pull_ledger(), test_a_snapshot_after_first_pitch_is_marked_in_play(), test_a_snapshot_exactly_at_first_pitch_stays_pregame(), test_backfill_rows_are_stamped_with_the_historical_source(), test_ignore_ledger_still_resumes_its_own_pulls(), test_insert_tolerates_rows_without_a_source_key() (+13 more)

### Community 294 - "NCAAF player stats parser tests"
Cohesion: 0.18
Nodes (17): parse_player_game_stats(), _cat(), _parse(), _payload(), _team(), test_a_game_missing_from_the_id_map_is_skipped_not_guessed(), test_a_player_gets_one_row_across_every_category(), test_a_player_with_nothing_we_track_is_skipped() (+9 more)

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

### Community 306 - "NFL in-play flow pseudo CLV tests"
Cohesion: 0.14
Nodes (21): match_to_flow(), pseudo_clv(), _bet(), _preds(), _quote(), _quotes(), synthetic(), test_a_far_away_kickoff_is_a_different_season() (+13 more)

### Community 316 - "Threshold and EV floor replay sweeps"
Cohesion: 0.06
Nodes (35): assert_retrain_allowed(), analyse(), split(), _basis(), _cut(), fetch(), main(), analyse() (+27 more)

### Community 317 - "Scratch Postgres latest line tests"
Cohesion: 0.06
Nodes (37): can_scratch(), env_dsn(), _free_port(), pg_bin(), scratch_cluster(), _pg_bin(), _swap_dbname(), test_anon_reads_both_discord_views() (+29 more)

### Community 318 - "tests/test_live_record_start_views.py"
Cohesion: 0.09
Nodes (12): _body(), _code(), test_both_published_views_carry_the_live_date_gate(), test_it_runs_after_the_migration_that_used_to_own_the_daily_view(), test_migration_is_one_statement(), test_migration_is_registered_with_the_worker_runner(), test_neither_view_reads_the_sweep_universe(), test_no_ddl_outside_the_guarded_branches() (+4 more)

### Community 319 - "UFC historical CSV loader"
Cohesion: 0.11
Nodes (21): backfill_ufc_csv(), build_events(), build_fighter_index(), _heal_window_lo(), ingest_ufc_results_for_date_csv(), _kd_int(), load_fighter_profiles_from_csv(), _mirror_etag() (+13 more)

### Community 322 - "Discord price bound tests"
Cohesion: 0.11
Nodes (15): _dec(), test_a_field_without_a_bound_renders_without_the_clause(), test_a_model_with_no_own_ev_floor_is_bound_by_the_global_one(), test_a_price_floor_can_be_the_binding_gate(), test_a_rounded_bound_still_clears_the_bound_it_came_from(), test_even_money_is_plus_one_hundred(), test_no_bound_from_junk_rather_than_a_guess(), test_no_bound_when_the_edge_floor_is_unreachable() (+7 more)

### Community 326 - "Mobile team detail page tests"
Cohesion: 0.11
Nodes (15): _read(), test_every_team_page_read_names_its_relation_literally(), test_next_game_is_earliest_in_the_window_not_tonights_date(), test_no_paper_trading_copy(), test_public_betting_policy_migration_exists_and_is_select_only(), test_recent_games_are_scoped_by_sport(), test_results_are_units_never_dollars(), test_sharp_gap_is_no_vig_vs_no_vig() (+7 more)

### Community 327 - "NHL prop odds fetch gate"
Cohesion: 0.07
Nodes (22): due(), _book(), test_a_200_on_both_calls_merges_the_alternate_lines(), fake_fetch(), test_a_game_first_priced_inside_the_final_window_gets_nothing_more(), test_a_game_first_priced_inside_the_window_gets_one_decision_snapshot(), test_a_game_with_nothing_stored_is_owed_its_open(), test_a_moved_featured_line_keeps_the_old_number_under_the_alternate_key() (+14 more)

### Community 328 - "NFL Kalshi edge search"
Cohesion: 0.11
Nodes (24): align_check(), bh(), bins(), boot(), cell(), coverage(), cp_roi(), fee() (+16 more)

### Community 329 - "nfl/models/opener_spread.py"
Cohesion: 0.14
Nodes (11): age_tag(), american_to_prob(), _bettable_books(), clean_board(), edge_tier(), evaluate_board(), held_minutes(), model_prob_for_dev() (+3 more)

### Community 33 - "nfl/live_model/feeds: test_feed_resilience + espn"
Cohesion: 0.07
Nodes (32): _competitors(), _deref(), fetch_live_events(), _https(), make_fetcher(), fetch(), parse_core_event(), _score() (+24 more)

### Community 333 - "tests/test_nfl_wind_fire_window.py"
Cohesion: 0.07
Nodes (18): _retractable_slate(), _slate(), test_a_blank_roof_at_a_NON_retractable_venue_is_unaffected(), test_a_closed_roof_is_still_indoor(), test_a_retractable_venue_with_an_unknown_roof_does_not_fire(), test_a_waiting_game_is_not_reported_as_a_collapsed_premise(), test_a_waiting_row_keeps_its_line_price_and_edge(), test_every_blank_roof_row_is_a_retractable_venue() (+10 more)

### Community 334 - "Build your own model NFL facts"
Cohesion: 0.25
Nodes (5): is_primetime(), lead_hours(), parse_ts(), _pre_start(), Build Your Own Model — NFL facts

### Community 335 - "tests/test_public_betting_ingestor.py"
Cohesion: 0.17
Nodes (17): parse_public_betting(), _pct(), _select_book(), _make_game(), test_parse_emits_six_rows(), test_parse_game_id_and_sides(), test_parse_marks_source_and_snapshot(), test_parse_missing_teams_returns_empty() (+9 more)

### Community 336 - "Basketball player positions ingestor"
Cohesion: 0.04
Nodes (45): _athlete_room(), _basketball(), basketball_group(), _cached_unmatched_ids(), _espn(), _fresh_source_ids(), ingest_player_positions(), is_within_window() (+37 more)

### Community 339 - "tests/test_service_role_split.py"
Cohesion: 0.15
Nodes (11): _all_job_ids(), _sched(), test_an_unknown_role_runs_everything(), test_every_add_job_call_passes_an_id(), test_every_job_is_owned_by_exactly_one_role(), test_the_always_on_jobs_run_on_every_role(), test_the_default_preserves_the_single_container(), test_the_nfl_worker_stays_with_the_volume() (+3 more)

### Community 34 - "Prop ladder and NBA derivative tests"
Cohesion: 0.04
Nodes (46): _identity_maps(), _platform_gates_off(), _statements(), test_columns_and_values_line_up(), test_the_scorer_pick_insert_is_actually_covered(), test_rich_columns_coerce_numeric_like_738(), _bets(), _games() (+38 more)

### Community 343 - "API call log daily rollup tests"
Cohesion: 0.09
Nodes (10): test_a_fold_can_never_lower_a_stored_total(), test_a_new_process_does_not_prune_on_its_first_flush(), test_prune_rolls_up_before_it_deletes(), test_the_daily_table_is_created_and_locked_down(), test_the_daily_table_keys_on_day_api_and_source(), test_the_rollup_groups_by_eastern_day_not_utc(), test_the_rollup_reads_only_yesterday_and_today(), test_the_rollup_survives_a_failure_without_blocking_the_prune() (+2 more)

### Community 346 - "MLB over under retrain sweep job"
Cohesion: 0.10
Nodes (10): _side_rows(), test_marker_file_is_in_tree_so_the_freeze_would_not_block_the_worker(), test_missing_artifact_path_refuses_to_sweep_live(), test_over_covers_when_combined_score_beats_the_total_line(), test_price_below_the_house_floor_is_not_a_gradable_side(), test_push_on_the_total_emits_no_sides(), test_retrain_then_sweep_passes_the_new_path(), test_the_runner_retrains_then_sweeps_the_new_artifact() (+2 more)

### Community 347 - "Mobile sport filter persistence tests"
Cohesion: 0.14
Nodes (10): _load_body(), _sports(), _src(), test_a_visit_scoped_sport_change_does_not_persist(), test_a_writer_landing_during_the_hydrate_is_not_overwritten(), test_every_sport_survives_a_cold_start(), test_no_retired_sport_is_a_selectable_chip(), test_no_second_hand_written_sport_list_in_the_hook() (+2 more)

### Community 348 - "Custom model game facts tests"
Cohesion: 0.18
Nodes (19): assemble_game(), grade_ats(), grade_ml(), grade_total(), _game(), _q(), _quotes(), test_a_large_spread_is_kept() (+11 more)

### Community 35 - "NBA second game projection tests"
Cohesion: 0.05
Nodes (47): _box(), _cons(), _dist(), _emit_world(), _games(), _games_file(), _inj(), _neutral() (+39 more)

### Community 351 - "Live slate midnight date discovery"
Cohesion: 0.07
Nodes (15): _at(), test_a_game_seen_twice_is_polled_once(), test_both_live_loops_share_one_definition_of_the_slate(), test_by_daytime_yesterday_is_dropped(), test_discovery_asks_statsapi_about_every_date_it_is_given(), fake_schedule(), test_discovery_still_accepts_a_bare_string(), test_just_after_midnight_still_asks_about_yesterday() (+7 more)

### Community 353 - "NFL in-play flow bias validation"
Cohesion: 0.15
Nodes (9): bias_table(), main(), attach_ids(), _game_marks(), load_snapshots(), name_index(), resolve_game_ids(), resolve_snaps() (+1 more)

### Community 354 - "Custom model season facts loader"
Cohesion: 0.10
Nodes (19): line_at_start(), _num(), parse_date(), parse_game_id(), rest_days(), roles(), _side(), _as_quotes() (+11 more)

### Community 356 - "Intraday weather and news freshness"
Cohesion: 0.10
Nodes (13): run_player_news_ingestor(), _is_fresh(), _minutes_since(), step_player_news(), step_weather(), _age(), test_an_unknown_age_refetches_rather_than_skipping(), test_fresh_data_is_skipped() (+5 more)

### Community 357 - "In-play count tail dispersion tests"
Cohesion: 0.09
Nodes (10): _nb1_over_prob(), _setup(), test_an_artifact_wanting_an_unmapped_column_is_never_scored(), test_an_unknown_family_refuses_to_price_rather_than_falling_back(), test_every_mapped_model_can_be_built_from_the_map(), test_nb1_has_the_mean_it_claims_and_a_wider_variance(), test_nb1_with_an_unusable_alpha_refuses_too(), test_no_dispersion_is_exactly_the_old_poisson_behaviour() (+2 more)

### Community 358 - "NBA period map pricing tests"
Cohesion: 0.06
Nodes (33): _game(), _games3(), _gaps(), _ladder_quotes(), _luck_games(), _maps(), _odds_row(), _offered() (+25 more)

### Community 359 - "Prop box score cooled refill"
Cohesion: 0.11
Nodes (25): fill_missing(), _call_fill(), _cooled(), _day(), _default_mlb(), _default_nba(), _default_nfl(), _default_nhl() (+17 more)

### Community 36 - "NCAAF CFBD ingestor tests"
Cohesion: 0.03
Nodes (49): build_ncaaf_game_id(), _day_before(), eastern_game_date(), _local_aggregates(), parse_lines(), parse_teams(), shrink_to_prior(), _stamp_game_identity() (+41 more)

### Community 360 - "Mobile screen source wiring tests"
Cohesion: 0.07
Nodes (20): _bn_body(), _sql_groups(), test_a_failed_position_read_is_said_not_hidden(), test_a_failed_read_is_not_held_on_the_spinner(), test_every_mlb_stat_chip_has_a_branch(), test_every_nfl_stat_chip_has_a_branch(), test_every_roster_sport_chip_has_a_branch(), test_mlb_lineup_buckets_agree_between_app_and_server() (+12 more)

### Community 366 - "Kalshi game market recorder"
Cohesion: 0.09
Nodes (8): run_kalshi_game_record(), test_a_kalshi_outage_cannot_break_the_pass(), test_event_code_is_shared_across_series(), test_event_date_is_searched_not_anchored(), test_kalshi_labels_expand_st_and_use_the_explicit_map(), test_resolution_runs_after_every_snapshot(), test_the_recorder_is_scheduled_on_the_pipeline_role(), test_the_recorder_keeps_raw_contracts()

### Community 368 - "HTTP request timeout floor"
Cohesion: 0.11
Nodes (11): install_timeout_floor(), _call(), clean_requests(), test_a_call_with_no_timeout_gets_one(), test_an_explicit_timeout_is_never_overridden(), test_installing_twice_is_a_no_op(), test_the_deadline_is_env_overridable(), test_the_deadline_survives_telemetry_being_turned_off() (+3 more)

### Community 369 - "CLV price taken app parity tests"
Cohesion: 0.13
Nodes (18): _app(), _clv_card(), _node_strips_types(), _server(), test_a_label_book_nfl_pick_compares_its_line_with_that_book(), test_a_recorded_book_differs_from_the_derived_one(), test_the_app_prefers_the_recorded_book_at_the_derived_price(), test_the_app_prices_every_row_as_the_server_grades_it() (+10 more)

### Community 370 - "UFC results scraper tests"
Cohesion: 0.08
Nodes (26): _resolve_game_rows(), rounds_completed(), slugify_fighter(), load(), _resolve(), test_a_misspelled_fighter_is_scored_for_the_side_they_fought_on(), test_alias_makes_both_sources_agree(), test_aliases_do_not_touch_unmapped_names() (+18 more)

### Community 371 - "NCAAF totals probability regression tests"
Cohesion: 0.09
Nodes (15): margin_cover_prob(), total_over_prob(), test_artifact_kind_is_routed_by_the_scorer(), test_asymmetry_is_real_and_would_have_bitten(), test_extremes_are_clamped_away_from_certainty(), test_model_above_the_line_favours_the_over(), test_model_below_the_line_favours_the_under(), test_no_dk_total_means_skip_not_prob_only() (+7 more)

### Community 373 - "NCAAF search team and QB matrix"
Cohesion: 0.14
Nodes (13): build_adjusted_ratings(), build_prior_season_ratings(), load_fbs_membership(), load_team_games(), pool_fcs_opponents(), rolling_variants(), _asof_merge(), build_matrix() (+5 more)

### Community 375 - "Refresh pass step ordering tests"
Cohesion: 0.06
Nodes (27): bets_split(), _fmt(), _grid(), main(), _print_grid(), run_mlb(), run_ncaaf(), _summ() (+19 more)

### Community 377 - "First pitch time trust tests"
Cohesion: 0.08
Nodes (12): test_a_late_start_is_believed_because_it_is_real(), test_a_missing_actual_start_falls_back_to_the_schedule(), test_both_missing_still_fails_open(), test_every_is_pregame_snapshot_caller_passes_first_pitch(), test_it_never_overwrites_commence_time(), test_the_actual_start_wins_over_the_schedule(), test_the_boundary_itself_is_pregame(), test_the_clamp_sits_in_the_gap_the_data_leaves() (+4 more)

### Community 380 - "Game injury veto gate"
Cohesion: 0.21
Nodes (17): apply_to_picks(), player_matches_veto(), veto_reason(), _bet(), _idx(), _relevant(), test_avoid_and_none_are_not_downgraded(), test_gate_is_not_an_xgb_column() (+9 more)

### Community 382 - "Mobile bankroll screen checks"
Cohesion: 0.23
Nodes (13): _read(), test_copy_is_word_for_word(), test_display_only_nothing_sized(), test_error_text_uses_the_text_safe_red(), test_explainer_no_longer_denies_a_bankroll(), test_exposure_card_hook_and_banner_stay_removed(), test_keyboard_never_covers_the_field(), test_locale_separators_decide_the_decimal() (+5 more)

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

### Community 392 - "Mobile team total line tests"
Cohesion: 0.24
Nodes (6): _run(), test_a_move_off_the_deciding_book_s_number_is_against_the_bet(), test_the_line_movement_card_shows_the_team_total_line(), test_the_model_has_its_own_chip_and_no_picker_slot(), test_the_pick_reads_the_home_team_total_market_and_its_number(), test_the_team_page_leaves_the_team_total_out_of_every_tile()

### Community 396 - "NFL weather cache importer"
Cohesion: 0.18
Nodes (8): main(), rows_from_file(), source_for(), stadium_from_name(), _INSERT_PLACEHOLDERS(), test_a_non_issued_or_empty_payload_yields_nothing(), test_every_hour_becomes_one_row_in_column_order(), test_the_file_name_names_the_stadium()

### Community 398 - "Mobile bankroll settings card"
Cohesion: 0.20
Nodes (19): fieldFlow(), inv(), bankrollDraft(), bankrollFieldText(), canonical(), checkBankroll(), commitBankrollText(), editBankrollInput() (+11 more)

### Community 399 - "NFL live leader model tests"
Cohesion: 0.11
Nodes (17): wp_design(), wp_lookup(), art(), _d(), _raw(), test_600_seconds_and_both_lead_ends_are_inside(), test_a_flipped_spread_sign_changes_the_decision(), test_a_qualifying_state_bets_the_leader_at_its_price() (+9 more)

### Community 400 - "Mobile paused catalog tests"
Cohesion: 0.18
Nodes (10): _block(), _read(), test_paused_picks_reach_the_all_board_only_and_labelled(), test_stats_add_pick_refuses_a_paused_model(), test_the_bet_type_picker_filters_paused_models(), test_the_custom_model_picker_is_three_bet_types(), test_the_models_list_filters_paused_models(), test_the_pause_source_is_isModelPaused_not_a_hand_copied_set() (+2 more)

### Community 402 - "NCAAF opener board visibility tests"
Cohesion: 0.08
Nodes (22): _days_until(), _opener_rule(), _line(), _patch(), test_a_declined_rule_can_never_leak_a_signal(), test_a_fired_pick_clears_its_own_probability_floor(), test_a_no_signal_row_does_not_lock_an_ncaaf_game_for_the_week(), test_books_agreeing_is_a_no_signal_row() (+14 more)

### Community 403 - "MLB play-by-play and in-play history"
Cohesion: 0.11
Nodes (23): _get(), _iso(), main(), planned_calls(), pull_day(), rows_for(), _served_already(), shard_windows() (+15 more)

### Community 404 - "tests/test_promote_calibration_job.py"
Cohesion: 0.11
Nodes (3): test_a_refused_model_rolls_back_and_raises(), test_a_successful_promote_commits(), _job_promote_calibration()

### Community 406 - "tests/test_cfbd_snapshot_leakage.py"
Cohesion: 0.16
Nodes (9): _completed_before(), _ohio_state_2024(), test_boundary_is_strict(), test_datetime_like_values_are_handled(), test_empty_input(), test_end_of_regular_season_snapshot_excludes_playoffs(), test_missing_or_malformed_dates_are_dropped_not_admitted(), test_postseason_excluded_from_early_season_snapshot() (+1 more)

### Community 408 - "NFL wind forecast stability tests"
Cohesion: 0.12
Nodes (15): _series(), _slate(), test_a_covered_window_at_or_above_11_fires_and_records_the_minimum(), test_a_covered_window_whose_minimum_is_under_11_does_not_fire(), test_a_database_miss_returns_only_the_current_reading(), test_a_dip_inside_the_window_is_the_number_the_check_sees(), test_a_dip_older_than_the_lookback_does_not_count(), test_a_single_issued_forecast_still_fires() (+7 more)

### Community 409 - "NFL edge research local cache"
Cohesion: 0.22
Nodes (14): _conn(), copy_main_local(), _df(), _games_2026(), log(), main(), nflverse_misc(), nflverse_pbp() (+6 more)

### Community 411 - "NFL in-play prop assessment report"
Cohesion: 0.16
Nodes (16): _connect(), norm_name(), test_name_normalisation_handles_the_real_hard_cases(), american_b(), boot_ci(), build(), cluster_se_mean(), implied() (+8 more)

### Community 413 - "NFL prop threshold window tests"
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

### Community 418 - "Push delivery ticket parsing tests"
Cohesion: 0.22
Nodes (10): _msgs(), test_a_credentials_failure_disables_nobody(), test_a_request_level_rejection_accepts_nothing(), test_a_retired_device_is_named_for_disabling(), test_a_single_message_reply_may_be_a_bare_object(), test_a_ticket_that_is_not_an_object_is_not_a_delivery(), test_an_error_ticket_is_not_counted_as_sent(), test_an_unpairable_reply_counts_nothing_and_disables_nothing() (+2 more)

### Community 42 - "DataGolf ingestor and NHL SBR archive"
Cohesion: 0.05
Nodes (45): _american(), backfill_golf_rounds(), build_game_id(), _dg_get(), _earliest_commence_iso(), event_slug(), ingest_golf_field(), ingest_golf_odds() (+37 more)

### Community 422 - "Mobile tests run through node"
Cohesion: 0.02
Nodes (94): main(), node_exe(), node_strips_types(), tsx_cmd(), test_a_published_void_keeps_track_and_betslip(), test_a_tracked_void_reads_not_graded_and_detail_closes_when_over(), test_the_app_predicate_matches(), test_today_et_ignores_the_container_timezone() (+86 more)

### Community 425 - "NFL odds cache import to Supabase"
Cohesion: 0.12
Nodes (9): _allowed(), _data_dirs(), test_a_rerun_after_the_resolver_improves_adds_only_the_gap(), test_every_buying_ingestor_keys_its_resume_on_a_source_marker(), test_no_undeclared_data_store_on_disk(), test_the_importer_resolves_a_postponed_game(), test_the_importer_still_refuses_an_event_with_no_game(), test_the_nfl_odds_cache_has_an_importer() (+1 more)

### Community 426 - "tests/test_health_check_observe.py"
Cohesion: 0.14
Nodes (10): _crit(), fake(), test_a_crit_does_not_fail_the_observe_path(), test_a_crit_still_fails_the_daily_step(), test_an_exception_does_not_fail_the_observe_path(), test_daily_syncs_thresholds_after_view_migrations(), test_it_still_runs_the_check_when_observing(), test_ok_is_identity_in_both_modes() (+2 more)

### Community 427 - "NFL in-play prop flow model"
Cohesion: 0.09
Nodes (24): apply_anchor(), best_hit(), _boot_ci(), drop_degenerate(), evaluate(), fit_time_curve(), load_rows(), main() (+16 more)

### Community 428 - "NFL 2026 opener and wind tracker"
Cohesion: 0.09
Nodes (28): classify(), fetch(), grade_rows(), is_void(), lead_days(), _load_nfl_model(), main(), opener_verdict() (+20 more)

### Community 429 - "NFL in-play prop line churn check"
Cohesion: 0.21
Nodes (12): churn_table(), verdict(), _snaps(), test_a_line_moving_every_interval_reads_as_under_sampled(), test_a_missing_key_column_fails_loudly_rather_than_grouping_coarser(), test_a_single_snapshot_contributes_no_interval(), test_a_still_line_reads_as_still(), test_markets_are_not_pooled() (+4 more)

### Community 430 - "NBA totals luck fetch window tests"
Cohesion: 0.14
Nodes (13): _et(), _game(), _jobs(), test_a_fetch_that_stored_nothing_exits_non_zero(), test_a_schedule_placeholder_with_no_teams_is_never_planned(), test_a_tick_fetches_then_decides_then_publishes_each_step_bounded(), test_a_tick_with_nothing_due_spends_nothing(), test_every_team_on_the_stored_schedule_is_planned() (+5 more)

### Community 431 - "tests/test_pick_lock_is_on_picks.py"
Cohesion: 0.16
Nodes (9): _between(), _sql(), test_a_bet_is_still_never_re_scored(), test_only_a_bet_locks_a_pair(), test_the_cleanup_covers_the_whole_look_ahead_window(), test_the_cleanup_never_touches_a_started_game_or_a_live_row(), test_the_lock_is_no_longer_ncaaf_specific(), test_the_prop_and_live_locks_are_unchanged() (+1 more)

### Community 433 - "Sub-ten-second live odds path tests"
Cohesion: 0.09
Nodes (11): test_a_quote_already_seen_does_not_count_as_a_move(), test_a_scoring_failure_never_kills_the_feed(), test_poll_once_reports_which_games_moved(), test_scoring_is_opt_in(), test_scoring_runs_in_the_same_tick_as_the_write(), test_the_budget_is_written_down_where_it_can_be_checked(), test_the_expected_consequence_is_stated(), test_the_loop_sleeps_the_REMAINDER_of_the_interval() (+3 more)

### Community 435 - "NFL in-play prop rule and staleness reports"
Cohesion: 0.19
Nodes (11): american_b(), boot_roi(), first_per_player(), grade(), load(), main(), report(), main() (+3 more)

### Community 437 - "Per-model threshold config tests"
Cohesion: 0.07
Nodes (9): test_an_own_floor_does_not_take_a_model_off_the_calibration_map(), test_every_model_carries_its_own_thresholds(), test_every_own_floor_names_a_live_model(), test_models_on_own_probability_is_not_derived_from_the_floor_dict(), test_no_own_floor_tightens_a_model_past_the_global_floor(), test_only_a_market_priced_model_carries_a_negative_floor(), test_own_ev_floor_and_model_min_ev_stay_disjoint(), test_the_models_the_global_floor_silently_removed_can_bet_again() (+1 more)

### Community 438 - "NBA game two verdict grid tests"
Cohesion: 0.21
Nodes (20): _cell(), _grid(), _hgrid(), _house(), _mid(), test_a_cell_below_the_bet_count_enters_the_correction_at_p_one(), test_a_cell_clearing_every_bar_passes(), test_a_cell_with_no_dominant_side_is_not_held_to_a_blind_bet() (+12 more)

### Community 439 - "Worker retrain and sweep jobs"
Cohesion: 0.10
Nodes (8): test_the_raised_timeout_is_restored_after_the_job(), test_the_restore_puts_back_a_pre_existing_value(), test_marker_file_is_in_tree_so_the_freeze_would_not_block_the_worker(), test_missing_artifact_path_refuses_to_sweep_live(), test_retrain_then_sweep_passes_the_new_path(), test_the_runner_retrains_then_sweeps_the_new_artifact(), _job_mlb_runline_retrain_sweep(), _job_retrain_model()

### Community 44 - "scripts: build_nfl_live_leader_artifact + model"
Cohesion: 0.09
Nodes (26): wp_design(), wp_lookup(), attach_games(), build_artifact(), check_possession(), _dk_pregame_spread(), _download(), _first_bets() (+18 more)

### Community 442 - "Mobile player stat groups tests"
Cohesion: 0.15
Nodes (10): _set_literal(), _src(), test_a_group_is_filled_only_by_a_real_number(), test_a_tab_opens_on_the_stat_the_player_fills_most(), test_defensive_positions_get_only_the_defense_group(), test_every_logged_position_is_classified(), test_non_defensive_positions_get_no_defense_group(), test_offensive_positions_are_not_defensive() (+2 more)

### Community 445 - "NBA public splits game dating"
Cohesion: 0.29
Nodes (5): et_game_date(), _game_meta(), team_abbr(), test_a_late_west_coast_tip_belongs_to_the_previous_et_date(), test_team_ids_come_from_the_abbr_then_the_full_name()

### Community 447 - "supabase/functions/discord-link/index.ts"
Cohesion: 0.24
Nodes (15): accessFor(), handleComplete(), handleStart(), handleStatus(), handleUnlink(), hmac(), issueState(), json() (+7 more)

### Community 449 - "tests/test_nfl_prop_clv.py"
Cohesion: 0.16
Nodes (9): _assign(), _book_from_label_fn(), _fn(), test_the_book_is_read_from_the_label_suffix(), test_the_closing_prop_lookup_defaults_to_draftkings_and_binds_the_book(), test_the_label_book_map_is_the_inverse_of_both_cards(), test_the_map_test_no_longer_excludes_nfl(), test_the_market_relative_rules_take_their_market_from_the_row() (+1 more)

### Community 452 - "tests/test_scoring_methods.py"
Cohesion: 0.13
Nodes (7): _generic(), test_a_generic_model_is_never_declared_rule_or_engine(), test_accessor_defaults_to_artifact(), test_every_classified_model_carries_thresholds(), test_mlb_live_total_runs_is_artifact_backed(), test_rule_based_models_never_appear_in_a_feature_map(), test_the_map_covers_exactly_the_non_generic_models()

### Community 457 - "Team stats impossible games played checks"
Cohesion: 0.10
Nodes (11): impossible_games_played(), _played_actual(), test_a_missing_count_is_reported_not_silently_passed(), test_an_honest_row_passes(), test_claiming_fewer_games_than_played_is_fine(), test_feb_gp_climbing_vs_zero_regular_season_still_fails(), test_one_game_date_boundary_mismatch_is_tolerated(), test_season_final_in_april_is_still_caught() (+3 more)

### Community 46 - "Worker job queue runner"
Cohesion: 0.03
Nodes (35): derive_first_pitch(), test_the_worker_job_is_registered_and_defaults_to_dry_run(), test_the_discord_publish_job_calls_the_ordinary_producer(), test_the_discord_publish_job_takes_an_optional_date(), _announce(), _execute(), _job_byom_game_facts(), _job_derive_first_pitch() (+27 more)

### Community 462 - "Anon read access sweep tests"
Cohesion: 0.06
Nodes (16): _app_rpcs(), test_a_writable_relation_that_is_not_readable_is_still_swept(), test_every_declared_write_verb_has_a_call_site_that_needs_it(), test_every_rpc_the_app_calls_is_declared_or_known_absent(), test_public_is_stripped_from_every_declared_callable_before_it_is_granted(), test_subscriptions_stays_authenticated_only(), test_the_apply_script_reads_back_that_rls_actually_landed(), test_the_apply_script_revokes_writes_and_reads_the_result_back() (+8 more)

### Community 465 - "nfl/scripts/backtest_opener.py"
Cohesion: 0.24
Nodes (9): boot(), by_season(), exp_win(), load(), main(), price(), report(), residuals() (+1 more)

### Community 466 - "Paused model profitability assessment"
Cohesion: 0.09
Nodes (16): _auto_paused_models(), active_era(), assess(), _half(), fetch(), grade(), main(), sweep() (+8 more)

### Community 467 - "NCAAF totals lead and consensus gate"
Cohesion: 0.17
Nodes (16): fmt(), grade(), load_closes(), main(), match(), build_lead_table(), first_cross(), fmt() (+8 more)

### Community 468 - "tests/test_latest_odds_views.py"
Cohesion: 0.25
Nodes (13): _app_columns(), _function(), test_every_log_table_has_its_insert_trigger_and_the_odds_tables_an_update_trigger(), test_every_view_reads_its_state_table_and_never_the_log(), test_no_pending_view_migration_re_creates_these_views_over_the_log(), test_the_dk_view_returns_the_apps_columns_in_order(), test_the_exclusions_survived_the_move(), test_the_game_view_returns_the_apps_columns_in_order() (+5 more)

### Community 472 - "NBA schedule ingestor"
Cohesion: 0.20
Nodes (11): ot_periods(), schedule_rows(), season_str(), _tv(), _row(), test_a_late_west_coast_tip_keeps_its_eastern_date(), test_an_undecided_playoff_slot_is_skipped(), test_game_type_is_read_from_the_first_three_digits() (+3 more)

### Community 476 - "tests/test_transaction_pooler.py"
Cohesion: 0.19
Nodes (8): _transaction_endpoint(), test_a_direct_connection_is_left_alone(), test_a_local_postgres_is_left_alone(), test_a_supabase_session_url_becomes_the_transaction_url(), test_it_is_idempotent(), test_only_the_port_changes(), test_the_escape_hatch_works(), test_the_job_queue_still_gets_session_mode()

### Community 477 - "Env file database URL fallback"
Cohesion: 0.16
Nodes (11): database_url(), _default_env_path(), env_value(), parse_env_file(), test_a_missing_env_file_is_empty_not_an_error(), test_a_value_containing_equals_survives(), test_env_file_is_read_when_the_environment_is_empty(), test_env_value_reads_other_keys_too() (+3 more)

### Community 482 - "Paused and no-signal pick rows tests"
Cohesion: 0.17
Nodes (10): _game_pick(), _prop_pick(), test_auto_paused_counts_as_paused(), test_no_signal_rows_persist_the_reason(), test_paused_game_model_avoid_stays_avoid_with_reason(), test_paused_game_model_bet_stays_bet_with_reason_and_stake(), test_paused_prop_model_avoid_stays_avoid_with_reason(), test_score_game_routes_no_signal_through_the_helper() (+2 more)

### Community 483 - "MLB play-by-play ingestor"
Cohesion: 0.16
Nodes (15): _bases_after_from_matchup(), parse_game_plays(), parse_play(), _split_event_type(), test_bases_empty_matchup(), test_bases_with_runners(), test_parse_game_plays_empty_feed(), test_parse_game_plays_walks_full_inning() (+7 more)

### Community 484 - "MLB runline feature type coercion"
Cohesion: 0.15
Nodes (10): coerce_numeric_features(), test_a_row_with_all_handicap_null_survives_dropna(), _runline_row(), test_empty_last3_is_missing_so_strict_dropna_drops_the_row(), test_feature_matrix_coerces_decimal_last3_to_float(), test_feature_matrix_coerces_last3_empty_and_none_to_numeric_nan(), test_raw_pandas_frame_leaves_last3_non_numeric(), test_train_and_runline_sweep_use_the_shared_coerce() (+2 more)

### Community 486 - "Database URL doctor"
Cohesion: 0.14
Nodes (18): _classes(), diagnose(), bad(), _safe(), _fails(), _levels(), test_a_correct_url_reports_no_failures(), test_bare_postgres_on_a_DIRECT_host_is_fine() (+10 more)

### Community 487 - "supabase/functions/sharpsports/index.ts"
Cohesion: 0.30
Nodes (13): americanFromBetSlip(), asArray(), createContext(), isSettled(), json(), pick(), pullAndUpsert(), readBets() (+5 more)

### Community 491 - "Rule model market reading tests"
Cohesion: 0.15
Nodes (10): _case(), _clv_game_market(), _like(), _prompt_case(), _scorer_case(), test_the_case_reader_reads_the_name_patterns_as_postgres_does(), test_the_claude_mobile_prompt_reads_the_rule_card_s_market(), test_the_closing_line_functions_are_recreated_when_they_change() (+2 more)

### Community 495 - "tests/test_worker_deps.py"
Cohesion: 0.22
Nodes (4): _requirements(), test_dashboard_packages_are_not_on_the_worker(), test_only_the_dashboard_imports_them(), test_the_worker_asks_for_the_cpu_build_of_xgboost()

### Community 497 - "Discord publish keys and push notifier"
Cohesion: 0.03
Nodes (65): paused_row_exclusion_sql(), run(), _sql_key(), test_a_game_level_key_has_no_tail(), test_an_opening_signal_is_live_only_when_discord_published_it(), test_discord_led_visibility(), test_opening_lock_join_is_not_wired_into_readers_yet(), test_the_discord_pins_are_on_the_pr_ci_subset() (+57 more)

### Community 50 - "scheduler.py"
Cohesion: 0.05
Nodes (52): abort_orphaned_refresh_runs(), build_scheduler(), _add_job(), _with_heartbeat(), _wrapped(), catch_up_daily_pipeline(), catch_up_refresh_pass(), catch_up_weekly_jobs() (+44 more)

### Community 501 - "First pitch posting guard tests"
Cohesion: 0.11
Nodes (7): test_capture_compares_the_picks_own_clock_not_the_capture_clock(), test_capture_fails_open_on_a_missing_timestamp(), test_delivery_fails_open_too(), test_health_check_uses_the_same_first_pitch_bound_as_discord(), test_mixed_timestamp_shapes_are_parsed_not_string_compared(), test_the_dry_run_count_uses_the_same_predicate_as_the_insert(), test_the_restatement_path_is_deliberately_not_guarded()

### Community 503 - "Team stats snapshot invariant tests"
Cohesion: 0.16
Nodes (8): seasons_with_too_few_snapshots(), test_a_real_series_passes(), test_a_single_snapshot_season_is_flagged(), test_a_two_snapshot_season_is_flagged(), test_mlb_twin_alias_map_matches_sbr_canon(), test_ncaaf_shaped_weekly_snapshots_pass(), test_the_guard_is_wired_so_protected_seasons_are_REMOVED(), test_the_guard_uses_the_same_threshold_as_the_invariant()

### Community 506 - "tests/test_ncaaf_fcs_visitor_names_migration.py"
Cohesion: 0.15
Nodes (5): _rows(), test_each_write_guards_on_its_own_property(), test_every_real_visitor_extends_the_wrong_one(), test_migration_is_one_statement(), test_the_nine_rows_and_their_finals_are_the_measured_ones()

### Community 507 - "tests/test_nfl_prop_unstarted_clear.py"
Cohesion: 0.25
Nodes (8): _apply(), _assert_split(), _between(), _first_sql(), _per_game_sql(), _sweep_sql(), test_per_game_clear_keeps_nfl_prop_rows_on_a_game_the_loop_reaches(), test_sweep_keeps_unstarted_nfl_prop_nones_and_still_clears_game_nones()

### Community 508 - "Multi-sport model research labs"
Cohesion: 0.03
Nodes (106): bh_fdr(), binom_p(), eval_rule(), load(), main(), devig_power(), games(), main() (+98 more)

### Community 513 - "tests/test_scorer_nfl_prop_like_escape.py"
Cohesion: 0.23
Nodes (9): _between(), _broken_per_game_sql(), _first_sql(), _per_game_sql(), _sweep_sql(), test_escape_tripwire_is_on_the_pr_ci_subset(), test_live_per_game_clear_interpolates_with_one_game_id(), test_live_sweep_clear_interpolates_with_date_horizon_now() (+1 more)

### Community 514 - "Published record views reconciliation"
Cohesion: 0.16
Nodes (8): test_a_pick_before_the_live_date_is_caught_in_either_view(), test_a_sport_missing_from_the_daily_view_is_caught(), test_an_empty_record_is_not_a_problem(), test_cent_level_agreement_is_required(), test_same_picks_but_different_money_is_caught(), test_the_fixed_production_numbers_reconcile(), test_the_real_production_drift_is_caught(), _published_record_problems()

### Community 516 - "NHL stats views tests"
Cohesion: 0.15
Nodes (14): _date_filter_runs_before_dedupe(), anywhere(), blob(), filter_wraps_unique(), has_unique(), pred(), pred_inside_unique(), _pg_bin() (+6 more)

### Community 517 - "Trainer no-register mode tests"
Cohesion: 0.12
Nodes (9): not_registering(), registering(), test_a_normal_run_DOES_register(), test_baseline_artifacts_are_not_committable(), test_baseline_runs_write_somewhere_else(), test_default_is_to_register(), test_no_register_opens_no_database_connection(), _explode() (+1 more)

### Community 518 - "NHL game results parser"
Cohesion: 0.38
Nodes (9): parse_nhl_game(), _g(), test_arizona_folds_into_utah(), test_missing_teams_returns_none(), test_ot_home_win_is_regulation_draw(), test_preseason_game_skipped(), test_regulation_home_win(), test_scheduled_game_has_no_scores() (+1 more)

### Community 519 - "Social post transport error tests"
Cohesion: 0.33
Nodes (3): _creds(), test_a_5xx_is_transport_and_not_a_tweet_id(), test_a_missing_table_is_a_no_op()

### Community 520 - "Market movement feature builder"
Cohesion: 0.09
Nodes (23): american_to_prob(), build_market_features(), _is_full_game_snap(), _latest_two_sided(), _s(), test_a_game_with_no_decision_book_still_gets_features(), test_a_line_that_genuinely_did_not_move_is_zero_not_none(), test_a_one_way_sharp_quote_yields_nothing() (+15 more)

### Community 522 - "Team stats rebuild row tests"
Cohesion: 0.12
Nodes (12): build_rows(), _team_games(), _game(), test_a_row_never_includes_its_own_date(), test_counts_accumulate_across_dates(), test_every_emitted_column_exists_in_the_real_table(), columns_of(), test_every_sport_uses_its_own_scoring_noun() (+4 more)

### Community 524 - "NCAAF margin evaluation and weather totals"
Cohesion: 0.06
Nodes (39): build_frames(), _fit(), fit_and_register(), fit_and_register_totals(), main(), _matrix(), _print_sweep(), rmse() (+31 more)

### Community 525 - "Anon grant apply script"
Cohesion: 0.17
Nodes (8): write_verbs_for(), _anon_can_read(), _function_plan(), _function_signature(), main(), _table_exists(), test_write_verbs_for_keeps_exactly_what_a_writable_relation_declares(), test_write_verbs_for_revokes_everything_on_a_read_only_relation()

### Community 527 - "ESPN NHL probable goalies"
Cohesion: 0.15
Nodes (7): fetch_espn_nhl_probables(), parse_probable(), _team_abbrev(), test_fetch_fail_open(), test_fetch_uses_injected_fetch_and_keys_by_our_abbrev(), test_parse_probable_joins_display_name_to_our_abbrev(), test_parse_probable_skips_missing_name_or_slot()

### Community 529 - "tests/test_clear_unauthorized_auto_pauses_migration.py"
Cohesion: 0.19
Nodes (6): _stmts(), test_clearing_auto_pauses_did_not_park_batter_runs(), test_it_clears_the_whole_auto_pause_table(), test_it_does_not_touch_picks_thresholds_or_the_review_ledger(), test_it_no_ops_when_the_table_is_missing_or_already_empty(), test_migration_is_one_statement()

### Community 530 - "tests/test_ncaaf_se_louisiana_alias_migration.py"
Cohesion: 0.15
Nodes (4): test_a_pick_is_never_deleted_and_never_regraded(), test_it_guards_on_both_names_and_both_still_unscored(), test_migration_is_one_statement(), test_odds_move_only_when_canonical_has_none()

### Community 532 - "tests/test_overnight_polling.py"
Cohesion: 0.24
Nodes (7): _hours(), _jobs(), _match(), test_every_hour_of_the_day_is_covered(), test_the_overnight_pass_is_the_ordinary_one(), test_the_overnight_window_exists(), test_the_windows_do_not_overlap()

### Community 534 - "NFL stale daily card clearing"
Cohesion: 0.15
Nodes (9): card_path(), clear_card(), _load_script(), nfl_path(), test_a_dry_run_leaves_the_card_alone(), test_a_priced_wind_run_with_no_bets_removes_the_earlier_card(), test_clear_card_removes_todays_file_and_only_that(), test_the_path_cleared_is_the_path_the_publisher_reads() (+1 more)

### Community 535 - "NFL EV engine and stake sizing"
Cohesion: 0.09
Nodes (23): american_to_decimal(), cover_probs(), ev_per_unit(), fit_margin_pmf(), kelly_fraction(), margin_pmf_for(), add_model_mu(), load() (+15 more)

### Community 536 - "Mobile type-check baseline tests"
Cohesion: 0.29
Nodes (13): _entries(), _log(), _log_line(), _run(), test_a_clean_log_warns_for_every_baseline_entry(), test_a_compiler_crash_is_not_a_clean_run(), test_a_different_app_message_fails(), test_a_fixed_baseline_entry_warns_and_does_not_fail() (+5 more)

### Community 538 - "Kalshi game market ingestor"
Cohesion: 0.17
Nodes (8): event_code(), event_date(), kalshi_school(), _num(), probe(), record_game_markets(), resolve_events(), rows_for()

### Community 539 - "NFL prop over-lean concentration study"
Cohesion: 0.25
Nodes (7): add_context(), boot(), main(), profit(), report(), tercile_split(), under_profit()

### Community 542 - "X team hashtags"
Cohesion: 0.17
Nodes (11): test_college_nicknames_and_a_shared_mascot_falls_back_to_the_school(), test_team_hashtags_use_the_nickname(), _both_teams(), _from_full_names(), hashtag_token(), _index(), _mlb(), _nickname() (+3 more)

### Community 543 - "Results recap backfill command"
Cohesion: 0.20
Nodes (8): build_parser(), _date_is_over(), main(), post_backfill(), test_a_day_that_is_not_over_is_refused(), test_apply_calls_both_notifiers_for_that_date(), test_dry_run_is_the_default_and_posts_nothing(), test_main_dry_run_prints_and_returns()

### Community 546 - "tests/test_claude_rules_split.py"
Cohesion: 0.18
Nodes (4): test_claude_md_still_points_at_the_rules_directory(), test_every_rule_file_actually_carries_rules(), test_every_rule_file_is_path_scoped(), test_no_rule_was_lost_when_the_split_happened()

### Community 547 - "tests/test_db_setup.py"
Cohesion: 0.23
Nodes (6): _get_columns(), test_games_table_columns(), test_injuries_table_columns(), test_odds_table_columns(), test_picks_table_columns(), test_schema_is_idempotent()

### Community 548 - "tests/test_dedupe_opening_signals.py"
Cohesion: 0.12
Nodes (8): test_a_graded_row_is_never_deleted(), test_a_row_with_computed_clv_is_never_deleted(), test_every_field_that_defines_the_bet_must_agree(), test_the_delete_selects_through_the_same_gates(), test_the_pair_must_be_an_old_shape_new_shape_pair(), test_the_report_and_the_delete_share_one_definition(), test_the_row_kept_is_the_one_locked_earlier(), test_the_unresolved_report_excludes_what_the_delete_resolves()

### Community 549 - "NBA injury report snapshot writer"
Cohesion: 0.17
Nodes (9): content_hash(), garbled_note(), previous_report(), pull_one(), slot_time(), tips_by_date(), write_report(), test_a_report_whose_cells_do_not_line_up_with_its_header_is_not_stored() (+1 more)

### Community 552 - "tests/test_pbp_backfill_resilience.py"
Cohesion: 0.24
Nodes (6): _backfill_body(), test_a_failed_game_rolls_the_connection_back(), test_a_run_that_wrote_nothing_reports_an_error_not_a_success(), test_errors_are_counted_not_just_logged(), test_partial_failures_are_surfaced_too(), test_the_rollback_cannot_itself_raise()

### Community 553 - "Pregame line change detection"
Cohesion: 0.18
Nodes (12): changed_rows(), _row(), test_a_link_or_selection_id_churning_is_not_a_change(), test_a_moved_price_is_written_and_marks_its_game(), test_a_moved_total_counts_even_when_the_price_holds(), test_a_quote_we_have_never_seen_counts_as_changed(), test_an_unchanged_quote_is_not_written(), test_in_play_rows_are_ignored() (+4 more)

### Community 559 - "In-play bet uniqueness index tests"
Cohesion: 0.14
Nodes (13): _db(), _insert(), _signals(), test_a_live_bet_survives_an_avoid_on_the_same_lane(), test_a_second_live_bet_on_the_same_lane_still_conflicts(), test_a_void_or_no_action_live_bet_does_not_hold_the_lane(), test_mlb_and_ncaaf_already_clear_the_standing_non_bet_before_insert(), test_the_health_check_compares_the_exact_definitions() (+5 more)

### Community 561 - "NFL wind forecast lead calibration"
Cohesion: 0.36
Nodes (5): build(), fetch_issued_all_leads(), games(), main(), resample()

### Community 565 - "NCAAF quarterback ablation study"
Cohesion: 0.28
Nodes (7): _fit(), main(), _report(), run(), summarise(), walk_forward(), wilson()

### Community 567 - "NBA injury report slot schedule"
Cohesion: 0.15
Nodes (12): _all_slots(), _ampm(), new_slot(), old_slot(), pre_tip_slot(), report_url(), slots_for_date(), test_format_switch_is_measured_and_both_are_probed_around_it() (+4 more)

### Community 569 - "NBA in-game study one tests"
Cohesion: 0.17
Nodes (15): _pin(), _q(), _rows(), _state(), test_every_fit_for_season_s_uses_earlier_seasons_only(), test_expected_rates_use_the_teams_earlier_dates_only(), test_ig1_bets_against_luck_and_the_control_with_it(), test_luck_counts_a_three_three_times_and_a_free_throw_once() (+7 more)

### Community 572 - "NFL model import path tests"
Cohesion: 0.15
Nodes (6): _import_under_scheduler_env(), _scheduler_env(), test_no_nfl_script_uses_the_bare_models_import(), test_the_card_imports_under_the_schedulers_invocation(), test_the_exemption_is_the_loader_and_it_still_exists(), test_the_loader_reaches_nfls_models_not_the_platforms()

### Community 573 - "NBA public splits pipeline step"
Cohesion: 0.12
Nodes (13): inserted_minus_start_min(), run_forward(), side(), step_nba_public_splits(), test_v1_inserted_lag_is_minutes_after_the_listed_start(), Coverage, Forward capture (2026-27), How to read it (+5 more)

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

### Community 58 - "Social post queue and drain"
Cohesion: 0.12
Nodes (30): test_the_cli_can_enqueue_one_image_without_posting(), _actionable(), _as_utc(), _attach_media(), _claim(), drain_social_posts(), _external_reply(), _fail_queued() (+22 more)

### Community 580 - "scripts/render_brand_icons.py"
Cohesion: 0.24
Nodes (3): draw_mark(), main(), render()

### Community 581 - "NCAAF search QB feature merge"
Cohesion: 0.19
Nodes (8): load_qb_games(), merge_qb_features(), _games(), _qb_team(), test_either_changed_is_a_game_level_flag_the_diff_would_cancel(), test_every_declared_feature_is_actually_produced(), test_missing_qb_table_yields_nan_columns_not_a_crash(), test_positive_diff_always_means_good_for_home()

### Community 582 - "Results recap NFL box score ordering"
Cohesion: 0.17
Nodes (8): _daily(), _job_body(), test_a_malformed_date_is_refused_before_anything_runs(), test_nfl_box_scores_are_ingested_before_settle(), test_nfl_finals_still_precede_the_box_scores(), test_the_job_does_not_read_rowcount_off_the_cursor(), test_the_job_only_clears_its_own_two_ledger_kinds(), test_the_job_posts_both_surfaces_through_the_ordinary_paths()

### Community 585 - "NBA prop model verification stages"
Cohesion: 0.13
Nodes (28): adv_from_log(), asof_roster(), blind_structured(), card_block(), collapse_report(), _compare(), log(), main() (+20 more)

### Community 586 - "supabase/functions/stripe-webhook/index.ts"
Cohesion: 0.31
Nodes (9): applySubscription(), iso(), resolveUserId(), stripeGet(), timingSafeEqual(), toHex(), verifySignature(), admin (+1 more)

### Community 588 - "Ungraded model performance tests"
Cohesion: 0.19
Nodes (7): _second_arm(), _sql(), test_both_arms_stay_inside_the_settled_bet_gate(), test_models_the_matview_does_not_grade_are_sourced_from_picks(), test_the_arm_does_not_key_on_is_live(), test_the_arm_is_scoped_by_absence_from_the_matview_not_by_model_id(), test_the_arm_prices_units_the_same_way_the_matview_does()

### Community 589 - "tests/test_mobile_neutral_signal_label.py"
Cohesion: 0.31
Nodes (7): _read(), test_explainer_names_neutral(), test_filters_and_card_speak_the_display_name(), test_model_screens_speak_the_display_name(), test_no_member_label_prints_a_raw_signal_type(), test_none_badge_reads_neutral(), test_withdrawn_pick_is_not_badged_neutral()

### Community 591 - "College football data checks"
Cohesion: 0.33
Nodes (5): _check(), _lines_coverage(), main(), _null_report(), _sample_keys()

### Community 592 - "Worker-only table lock-down SQL"
Cohesion: 0.15
Nodes (7): closed_tables(), lock_down_sql(), test_lock_down_never_uses_force_row_level_security(), test_lock_down_sql_refuses_anything_that_is_not_a_plain_identifier(), test_lock_down_sql_refuses_every_table_the_app_reads(), test_lock_down_sql_revokes_before_it_enables_rls(), test_the_worker_only_tables_are_not_also_declared_app_readable()

### Community 593 - "tests/test_scorer_commits_per_game.py"
Cohesion: 0.40
Nodes (8): _between(), _run_scorer_body(), test_a_lost_connection_re_runs_the_game_once_and_never_the_pass(), test_each_game_is_its_own_committed_unit(), test_no_bulk_delete_of_non_bet_rows_precedes_the_loop(), test_picks_are_only_counted_once_the_game_committed(), test_the_housekeeping_delete_is_a_sweep_after_the_loop(), test_the_outer_handler_still_records_the_failure()

### Community 596 - "NBA ESPN box score parsing"
Cohesion: 0.08
Nodes (24): box_team_totals(), et_date(), nba_team(), _no_minutes(), parse_nba_box(), parse_nba_dnp(), parse_nba_postponed(), parse_nba_scoreboard() (+16 more)

### Community 597 - "NFL paid odds cache import"
Cohesion: 0.24
Nodes (7): game_index(), main(), resolve(), rows_from_file(), stored_pairs(), stored_served(), _ts()

### Community 598 - "Declared worker job validation tests"
Cohesion: 0.15
Nodes (7): _declared(), test_an_explicit_run_date_must_be_a_real_iso_date(), test_declared_keys_are_unique(), test_every_declared_job_names_a_registered_type(), test_every_declared_job_validates(), test_no_run_date_means_the_module_resolves_it(), test_the_validator_drops_unknown_args()

### Community 60 - "tests: test_wnba_availability + wnba_availability"
Cohesion: 0.07
Nodes (43): absence_features(), absent_teammates(), build_context_features(), expected_rotation(), is_starter_tier(), _mean(), prior_rows(), recent_team_game_dates() (+35 more)

### Community 600 - "NFL prop market EV floor study"
Cohesion: 0.16
Nodes (8): _book_of(), part_a_card(), part_b(), _table(), Nickname-aware settlement join, nfl_prop_market EV floor 0.20 -> 0.07, MODEL_OWN_EV_FLOOR per model, NFL Monday 2026-09-21: empty Today / Signals

### Community 604 - "NCAAF starter-out study grading"
Cohesion: 0.27
Nodes (8): build_sample(), grade(), _line(), load_qb_log(), main(), report(), starter_status(), wilson()

### Community 606 - "Mobile NHL today look-ahead tests"
Cohesion: 0.29
Nodes (5): _fn(), _read(), test_the_nhl_read_matches_the_other_look_aheads(), test_the_sport_chip_is_the_hook_not_an_allowlist(), test_use_today_picks_fetches_nhl_across_that_window()

### Community 608 - "supabase/functions/sharpsports-webhook: index + index"
Cohesion: 0.25
Nodes (5): internalIdFor(), pick(), admin, admin, cors

### Community 609 - "Mobile Lines board pin tests"
Cohesion: 0.22
Nodes (9): _read(), test_a_missing_draw_price_is_remembered(), test_lines_board_pins_are_on_the_pr_ci_subset(), test_lines_is_a_picks_view(), test_the_behavioural_checks_pass(), test_the_board_reloads_when_the_et_date_changes(), test_the_lines_read_names_the_view_and_pages(), test_the_lines_segment_is_unconditional_and_after_live() (+1 more)

### Community 61 - "X social pick publisher"
Cohesion: 0.03
Nodes (69): run_social_post_queue(), test_a_pick_with_no_alternative_falls_back_to_draftkings(), pin(), test_form_params_are_in_the_signature_and_not_in_the_header(), test_a_clean_ledger_allows_the_post(), test_a_different_secret_changes_the_signature(), test_a_long_post_drops_reach_tags_before_team_tags(), test_a_long_post_drops_reach_tags_before_the_date_and_the_matchup() (+61 more)

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

### Community 620 - "Monitor probe call instrumentation"
Cohesion: 0.15
Nodes (10): instrumented(), instrumented(), record(), _redact(), _with_params(), classify(), test_garbage_url_does_not_raise(), test_query_is_dropped_except_the_allowlist() (+2 more)

### Community 622 - "UFC fight page parsing"
Cohesion: 0.13
Nodes (13): _aggregate_stats(), _int_or_none(), _mmss_to_sec(), _of_pair(), parse_event_page(), _two_ints(), parse_fight_page(), test_mmss_to_sec() (+5 more)

### Community 623 - "Pipeline signal push and opening capture"
Cohesion: 0.14
Nodes (6): step_capture_opening_signals(), step_push_notifications(), capture_opening_signals(), notify_feedback_replies(), notify_signal_changes(), _unpushed_feedback_replies()

### Community 626 - "Baseball Savant capture date stamping"
Cohesion: 0.20
Nodes (3): test_savant_has_a_schedule(), test_the_savant_job_belongs_to_the_pipeline_service(), test_the_stamp_defaults_rather_than_being_required_at_call_sites()

### Community 628 - "NCAAF weather totals study"
Cohesion: 0.23
Nodes (6): build_spots(), evaluate(), load_games(), main(), scoring_by_wind(), wilson()

### Community 629 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.47
Nodes (6): contentHeight(), evalExpr(), lineOf(), styleBlock(), styleProp(), visualHeight()

### Community 630 - "NCAAF CFBD opener research cache"
Cohesion: 0.23
Nodes (7): build_opener_cache(), coverage_report(), fetch_season(), _headers(), main(), _norm(), to_frame()

### Community 631 - "NHL totals research lab"
Cohesion: 0.26
Nodes (8): grade(), imp(), interval(), load(), main(), row(), show(), wpu()

### Community 632 - "NFL in-play prop dataset and calibration"
Cohesion: 0.09
Nodes (18): evaluate(), _infer_position(), main(), _pool_prior(), report(), _rows_for_market(), _to_states(), accrual_at() (+10 more)

### Community 634 - "Yesterday Discord units parity tests"
Cohesion: 0.25
Nodes (7): _bucket(), _expected(), _line(), _rewrite(), test_the_existing_daily_recap_verifier_passes(), test_the_unpriced_pnl_verifier_passes(), test_yesterday_matches_discord_on_the_fixture_day()

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
Cohesion: 0.07
Nodes (36): _model_price(), gaussian_copula_joint(), american_to_prob(), anchor_to_market(), devig_power(), margin_pmf(), _over_under(), price_moneyline() (+28 more)

### Community 641 - "Mobile quiet update download tests"
Cohesion: 0.17
Nodes (8): _code_only(), _read(), test_a_downloaded_update_is_announced_quietly_once(), test_app_root_mounts_the_ota_updater(), test_every_trigger_only_downloads(), test_nothing_in_the_app_reloads_a_running_app(), test_the_pieces_exist(), test_the_updater_downloads_the_update()

### Community 642 - "NBA team total luck replay tests"
Cohesion: 0.18
Nodes (6): art(), ld(), results(), test_the_artifact_holds_the_lab_s_team_total_residuals_in_order(), test_the_live_code_reproduces_the_lab_game_for_game(), test_the_live_home_parts_are_the_independent_lab_copy_s()

### Community 643 - "MLB in-play game state features"
Cohesion: 0.11
Nodes (19): compute_live_target(), half_innings_left(), parse_bases(), state_features(), test_build_live_state_row_merges_pregame_context(), test_build_live_state_row_unusable_state(), test_half_innings_left_bottom_ninth(), test_half_innings_left_extras_clamps_to_one() (+11 more)

### Community 645 - "NCAAF line move spot evaluation"
Cohesion: 0.27
Nodes (6): eval_follow_spread(), eval_follow_total(), load(), main(), _summ(), wilson()

### Community 647 - "NHL period goals feed parsing"
Cohesion: 0.32
Nodes (9): period_goals(), _game(), _goal(), test_a_feed_game_becomes_the_same_game_id_the_games_table_uses(), test_a_game_still_in_play_or_a_goal_for_neither_side_is_not_a_result(), test_a_team_named_as_an_object_is_read_too(), test_goals_are_counted_into_the_period_they_were_scored_in(), test_overtime_and_shootout_goals_belong_to_no_period() (+1 more)

### Community 649 - "Live feed vendor probe"
Cohesion: 0.24
Nodes (8): dump_vendor(), _get(), _is_live(), _key(), _row(), run(), _totals(), _vendor_key()

### Community 65 - "NBA prop model research lab"
Cohesion: 0.07
Nodes (46): books(), decimal(), expected_value(), p_over(), _agg(), apply_rule(), binary_baselines(), binary_indep() (+38 more)

### Community 654 - "Anon write grant revocation tests"
Cohesion: 0.15
Nodes (6): test_it_asserts_the_app_write_surface_survives(), test_it_revokes_every_write_privilege(), test_select_is_never_revoked(), test_the_roles_are_named_never_public(), test_the_runners_transaction_stripping_leaves_the_do_block_intact(), test_the_set_is_computed_from_the_policy_rule_not_listed()

### Community 662 - "NFL wind stake past calibration tests"
Cohesion: 0.22
Nodes (6): _probe(), test_an_uncalibrated_lead_is_sized_rather_than_zeroed_on_the_card(), test_at_the_default_gate_that_same_row_does_not_fire_at_all(), test_the_eval_board_agrees_with_the_card(), test_the_probability_was_already_clipping(), test_the_stake_clips_to_lead_seven_instead_of_returning_zero()

### Community 663 - "NBA injury report player matching"
Cohesion: 0.17
Nodes (7): match_player(), _near_season(), remap_changes(), _surname_key(), test_a_name_printed_differently_matches_on_surname_and_initial_within_the_team(), test_player_ids_match_on_team_first_then_a_unique_season_name(), test_remap_rewrites_only_names_whose_id_changed()

### Community 665 - "NCAAF scoreboard yardline parsing"
Cohesion: 0.21
Nodes (6): _abbrev_fits(), _parse_yardline(), _cfbd_game(), test_cfbd_state_carries_the_yardline_and_the_raw_situation(), test_cfbd_yardline_from_every_stored_situation(), test_cfbd_yardline_refuses_rather_than_guesses()

### Community 666 - "NFL prop kickoff lead ceiling tests"
Cohesion: 0.30
Nodes (8): _nfl_prop_too_early(), _iso(), test_a_kickoff_beyond_the_ceiling_is_too_early(), test_a_started_or_unknown_kickoff_is_not_too_early(), test_the_boundary_is_inclusive_at_the_ceiling(), test_the_scorer_and_the_card_read_ONE_constant(), test_the_scorer_loop_actually_applies_the_ceiling(), test_the_z_suffix_parses_like_the_offset_form()

### Community 667 - "Repo-wide lock-down call site guards"
Cohesion: 0.17
Nodes (6): _call_source(), _repo_sources(), test_every_guard_on_a_worker_only_table_asks_about_rls(), test_every_literal_lock_down_target_is_declared(), test_every_worker_only_create_site_goes_through_the_gated_helper(), test_no_create_site_uses_the_ungated_builder()

### Community 673 - "Scorer keeps off-DraftKings priced bets tests"
Cohesion: 0.29
Nodes (6): _bet(), db(), _left(), _statement(), test_a_bet_priced_at_another_books_line_survives_and_a_bet_with_no_price_does_not(), test_the_statement_names_both_prices()

### Community 677 - "Historical odds file loader"
Cohesion: 0.25
Nodes (3): canonical_abbrev(), parse_csv_file(), test_sbr_abbreviations_are_canonicalised_for_mlb_only()

### Community 679 - "Build your own model facts schema"
Cohesion: 0.24
Nodes (6): _code(), test_results_keep_pushes_and_ties_and_carry_no_stake(), test_the_migration_is_one_statement_and_registered(), test_the_second_pass_returns_before_it_locks(), test_the_skip_guard_refuses_every_write_verb(), test_there_is_no_lock_price_or_unit_column()

### Community 681 - "NFL prop market opening signal cleanup tests"
Cohesion: 0.23
Nodes (6): _stmts(), test_it_deletes_exactly_the_three_measured_lock_keys(), test_it_does_not_touch_picks_or_discord(), test_it_still_skips_a_key_that_has_a_standing_bet(), test_migration_is_one_statement(), test_standing_pick_uses_lock_key_sql_not_player_id()

### Community 689 - "UFC event list date parsing"
Cohesion: 0.33
Nodes (4): _parse_event_date(), parse_event_list(), test_event_date(), test_parse_event_list()

### Community 692 - "UFC fighter page parsing"
Cohesion: 0.22
Nodes (7): _height_to_inches(), _parse_dob(), parse_fighter_page(), _reach_to_inches(), test_height_reach_dob(), test_parse_fighter_page(), test_parse_fighter_page_missing_fields()

### Community 695 - "Every named sportsbook is fetched"
Cohesion: 0.18
Nodes (5): _param_books(), test_a_sharp_reference_is_never_also_a_soft_book(), test_every_bettable_book_can_be_named_to_a_human(), test_every_named_book_is_in_the_pull_that_serves_it(), test_the_nfl_backfill_defaults_to_the_live_pull()

### Community 696 - "App-readable relation manifest checks"
Cohesion: 0.22
Nodes (6): all_readable(), _app_relations(), test_every_relation_the_app_reads_is_declared(), test_everything_declared_writable_is_also_readable_or_deliberately_not(), test_the_manifest_does_not_grow_stale_entries(), test_the_view_base_tables_are_granted_but_never_read_directly()

### Community 697 - "NBA injury report write retry"
Cohesion: 0.22
Nodes (7): pull_with_retry(), test_a_connection_lost_mid_write_re_runs_the_whole_slot(), executemany(), __init__(), test_a_statement_timeout_rolls_back_and_re_runs_the_slot(), executemany(), __init__()

### Community 698 - "NFL prop backtest universe summary"
Cohesion: 0.29
Nodes (6): _universe_summary(), test_a_universe_without_the_model_sums_still_summarises(), test_mean_projection_and_mean_actual_separate_mean_bias_from_shape_bias(), test_model_over_rate_and_its_gap_are_reported(), _universe(), test_a_nonfinite_fair_price_cannot_switch_the_gate_off()

### Community 699 - "NCAAF in-play DraftKings gate tests"
Cohesion: 0.18
Nodes (4): test_a_cheaper_book_no_longer_buys_its_way_past_the_floor(), test_the_bet_is_still_recorded_at_the_best_price(), test_the_gate_reads_the_draftkings_numbers(), test_the_stale_line_cap_still_judges_the_dk_edge()

### Community 700 - "NHL regulation moneyline own probability"
Cohesion: 0.18
Nodes (4): mapped(), test_nyr_regulation_2026_10_02_is_not_a_bet(), test_the_correction_does_not_touch_a_regulation_probability(), test_the_rebuilt_moneyline_decides_on_its_own_probability()

### Community 701 - "First-time database setup"
Cohesion: 0.20
Nodes (5): _run_migrations(), setup_database(), first_time_setup(), setup_database(), step_apply_column_migrations()

### Community 705 - "Discord units won settlement"
Cohesion: 0.29
Nodes (4): test_prob_only_picks_fall_back_to_the_settlement_price(), test_units_convention_matches_the_stated_rule(), _decimal_odds(), units_won()

### Community 707 - "Anon grant plan tests"
Cohesion: 0.20
Nodes (4): _plan(), test_every_declared_relation_is_granted_exactly_once(), test_the_plan_revokes_before_it_grants(), test_unapplied_facts_tables_are_not_granted_until_they_exist()

### Community 712 - "NFL in-play 2024 replication report"
Cohesion: 0.31
Nodes (10): families(), fmt(), main(), parse_2025_output(), pool_all(), pooled_table(), replication(), repro_check() (+2 more)

### Community 717 - "NCAAF school slug matching"
Cohesion: 0.22
Nodes (5): _loose_orientation(), ncaaf_slug(), _slug_extends(), _slug_pair(), test_slug()

### Community 718 - "MLB injury and return ramp ingestor"
Cohesion: 0.22
Nodes (4): _compute_return_ramp(), fetch_mlb_transactions(), fetch_return_ramp_players(), run_injury_ingestor()

### Community 719 - "Mobile accessibility verify script"
Cohesion: 0.67
Nodes (3): read(), readUtf8(), verticalSlop()

### Community 72 - "Market handicap feature tests"
Cohesion: 0.04
Nodes (51): diff(), pitcher_diff(), diff(), pitcher_diff(), numeric_feature_value(), attach_market_handicap(), build_public_features(), build_rich_handicap() (+43 more)

### Community 721 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.67
Nodes (3): closeOf(), openTag(), toggleUse()

### Community 731 - "MLB twin team code leak checks"
Cohesion: 0.29
Nodes (3): test_mlb_twin_codes_do_not_false_crit(), test_mlb_twin_reverse_lookup_also_resolves(), test_season_final_in_april_still_caught_on_twin_code()

### Community 74 - "Prop CLV and SQL escaping tests"
Cohesion: 0.09
Nodes (17): _fn(), test_a_backfill_failure_never_breaks_settlement(), test_a_pick_is_only_stamped_captured_once_a_measure_resolved(), test_a_pick_stamped_after_first_pitch_is_never_measured(), test_a_prop_pick_whose_label_has_no_name_is_skipped_not_guessed(), test_both_guards_agree(), test_clv_pct_never_compares_prices_across_a_moved_line(), test_golf_stays_excluded() (+9 more)

### Community 75 - "Pre-game bound source inspection tests"
Cohesion: 0.04
Nodes (30): test_a_run_that_writes_nothing_is_not_reported_as_success(), test_the_insert_rolls_back_per_row(), test_the_backfills_in_play_marker_prefers_the_actual_start(), test_the_market_movement_loader_uses_the_better_bound(), test_the_nfl_prop_scorer_uses_the_better_bound(), test_the_prop_scorer_uses_the_better_bound(), test_the_wnba_prop_market_loader_coalesces_in_sql(), test_sport_and_market_are_bounded() (+22 more)

### Community 757 - "NBA injury report name normalising"
Cohesion: 0.22
Nodes (7): name_first_last(), norm_name(), _row(), team_code(), test_name_key_drops_accents_punctuation_and_suffixes(), test_names_turn_round_with_their_suffix_on_the_surname(), test_team_names_map_to_our_codes()

### Community 76 - "ncaaf_live/tests/test_serve.py"
Cohesion: 0.04
Nodes (58): _clock_seconds(), extract_live_states_cfbd(), school(), _parse_situation(), _strip_mascot(), check_feed_assumptions(), _competitors(), _count_plays() (+50 more)

### Community 8 - "Eggz capper picks Discord recaps"
Cohesion: 0.02
Nodes (92): _grade_conn(), _reg_conn(), test_a_final_moneyline_uses_the_settler_result(), test_a_line_that_is_not_a_pick_is_kept_for_review(), test_a_live_game_on_the_slate_date_holds_the_recap(), test_a_missed_eggz_day_posts_the_next_morning_for_that_date(), test_a_missing_price_stays_missing_and_the_stake_defaults_to_one(), test_a_non_mlb_prop_on_a_final_is_marked_for_review() (+84 more)

### Community 80 - "Per-model EV floor card tests"
Cohesion: 0.06
Nodes (27): min_ev_for(), test_ncaaf_live_ev_floor_is_wired_from_config(), _built(), floor_030(), identity_maps(), _nfl_fixtures(), open_pregame_cut(), _pregame() (+19 more)

### Community 82 - "Mobile error states and books tests"
Cohesion: 0.11
Nodes (24): _load_state_dir(), _raw_error_lines(), _read(), _run_node(), test_aborts_are_silent_and_offline_slow_are_narrow(), test_aborts_render_nothing_and_every_catch_skips_them(), test_designer_review_fixes_behaviour(), test_error_state_component() (+16 more)

### Community 83 - "In-play trigger orchestrator and daily cap"
Cohesion: 0.04
Nodes (40): should_fetch(), split_triggers(), under_credit_cap(), apply_daily_cap(), classify_live_signal(), _ev_floor(), test_live_signal_is_refused_under_the_global_floor(), _consume_source() (+32 more)

### Community 849 - "NBA public betting splits parser"
Cohesion: 0.17
Nodes (9): an_pct(), parse_v1_sides(), v1_consensus_row(), test_a_one_percent_side_is_not_inflated_to_100(), test_out_of_range_or_junk_percentages_are_refused(), test_v1_flat_fields_map_to_market_side_and_metric(), test_v1_reads_only_the_consensus_book(), test_v1_rows_carry_the_inserted_stamp_and_its_lag() (+1 more)

### Community 851 - "Results snapshot pass order tests"
Cohesion: 0.25
Nodes (6): _between(), _code(), _pass(), test_a_second_pass_does_not_mix_posted_wins_with_all_bets_units(), test_published_rewrite_runs_once_and_uses_the_view_clv_rule(), test_recompute_rewrites_snapshots_only_while_the_old_column_exists()

### Community 853 - "No record-only mode guard tests"
Cohesion: 0.43
Nodes (4): _allowed(), _hits(), _rel(), test_the_repo_has_no_record_only_or_paper_tracking_mode()

### Community 856 - "MLB public fade top-k backtest"
Cohesion: 0.12
Nodes (18): american_units(), bucket_win_rates(), build_candidates(), _fmt(), grade_under(), holdout_take(), load_db(), load_json() (+10 more)

### Community 86 - "NFL QB wind and NBA in-game tests"
Cohesion: 0.03
Nodes (103): add_form(), build(), feature_columns(), market_features(), team_game_stats(), load_games(), main(), pivot_spreads() (+95 more)

### Community 860 - "NCAAF play-by-play column range scan"
Cohesion: 0.33
Nodes (3): _extremes(), observed_ranges(), test_the_scan_survives_nulls_and_non_numeric_cells()

### Community 864 - "NBA prop pipeline steps"
Cohesion: 0.25
Nodes (4): step_nba_prop_market(), step_nba_prop_projection(), step_nba_prop_scoring(), step_nba_props()

### Community 87 - "NHL box score parsing"
Cohesion: 0.12
Nodes (16): _decision(), fill_missing(), _insert_absent(), _int(), _name(), parse_boxscore(), side_rows(), store_boxscore() (+8 more)

### Community 876 - "NBA play-by-play clock parsing"
Cohesion: 0.40
Nodes (3): parse_clock(), test_field_goal_value(), test_parse_clock()

### Community 880 - "NBA public splits quality flags"
Cohesion: 0.29
Nodes (4): quality_backfill_statements(), quality_flag(), test_the_quality_rule_puts_reversed_ahead_of_late(), test_the_stored_row_backfill_flags_exactly_what_the_rule_flags()

### Community 89 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.03
Nodes (50): a11ySrc, allowHit, ALLOWLIST, app, badExempt, bar, bareClose, baselineLeft (+42 more)

### Community 892 - "Prop board market coverage invariants"
Cohesion: 0.33
Nodes (3): _board_markets(), table(), test_the_mlb_board_and_the_mlb_pull_are_one_set()

### Community 894 - "NHL derivative totals card stub"
Cohesion: 0.40
Nodes (3): main(), run(), test_card_writes_nothing_and_the_pipeline_does_not_call_it()

### Community 90 - "NBA fifth search team rating projections"
Cohesion: 0.07
Nodes (30): as_of_ratings(), _before(), box_mismatches(), f4_projections(), f4_signal(), _known_team(), lead_minutes(), missing_inputs() (+22 more)

### Community 903 - "NCAAF in-play backtest state building"
Cohesion: 0.16
Nodes (11): main(), _classify(), classify_report(), _detect_score_convention(), load_pbp(), load_platform_games(), pace_report(), _repair_day_offsets() (+3 more)

### Community 907 - "NCAAF CFBD team game stats parsing"
Cohesion: 0.12
Nodes (12): parse_team_game_stats(), _possession_seconds(), _split_ratio(), _to_int(), test_an_fcs_name_that_extends_an_fbs_school_passes_through_unresolved(), test_parse_team_game_stats_builds_one_row_per_team(), test_parse_team_game_stats_skips_games_missing_from_the_id_map(), test_plays_is_none_when_neither_attempt_stat_is_present() (+4 more)

### Community 91 - "NFL in-play model backtest replay"
Cohesion: 0.05
Nodes (34): align_states(), build_team_map(), _game_index(), kill_verdict(), load_cached_snapshots(), main(), replay(), _settle() (+26 more)

### Community 912 - "NBA public betting splits ingestion"
Cohesion: 0.09
Nodes (26): build_rows(), clean_pair(), match_game(), parse_v2_sides(), _entry(), test_a_late_tip_matches_its_et_dated_game_id(), test_a_lone_side_is_kept_as_served(), test_a_pair_that_does_not_sum_to_100_is_dropped() (+18 more)

### Community 98 - "NBA play-by-play ingestor"
Cohesion: 0.05
Nodes (50): active_queries(), alias_map_rows(), _bool(), box_context(), box_finals(), build_game(), build_gap_game(), build_map() (+42 more)

### Community 106 - "Supabase schema tables"
Cohesion: 0.03
Nodes (103): api_call_log, app_errors, device_push_tokens, fighters, golf_players, golf_rounds, idx_api_call_api_ts, idx_api_call_ts (+95 more)

### Community 179 - "mobile/app.json"
Cohesion: 0.05
Nodes (38): backgroundColor, foregroundImage, adaptiveIcon, package, projectId, expo, android, extra (+30 more)

### Community 184 - "mobile/package.json"
Cohesion: 0.05
Nodes (38): dependencies, expo, expo-asset, expo-dev-client, expo-font, expo-notifications, expo-status-bar, expo-updates (+30 more)

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

### Community 716 - "NBA play-by-play stints guide"
Cohesion: 0.25
Nodes (7): Commands, How a stretch is built (each rule is pinned by a test that was watched to fail), NBA play-by-play and on-court lineup segments, Source, Tables (all worker-only, locked down where they are created), Things a reader should know, What was loaded, and the checks (re-measured 2026-10-17 on production, after the rebuild)

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

### Community 81 - "docs: nhl_market_lab + nhl_clv_ev_assessment"
Cohesion: 0.08
Nodes (41): nhl_research worker job, scripts/nhl_derivative_totals_backtest, data/ingestors/nhl_derivative_odds_history, models/nhl_props.py (Spec per market), DraftKings de-vigged price sits above realised over-rate, Anytime goalscorer: not a candidate once names corrected, nhl_moneyline and nhl_moneyline_regulation: no cut clears, Game models: lock later? Refuted (+33 more)

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
Cohesion: 0.06
Nodes (31): 1. Pre-registered bars (fixed 2026-10-15, before the first grid), 2. Data used (all in Supabase), 3. The market grid, 4.1 Game markets — closed for 2026-27, 4.2 First half / first quarter / team totals — closed for 2026-27, 4.3 Player props — one rule ships, 4.4 Player props — projection models (the NHL recipe), 4.5 The projection model on the worker's inputs only (+23 more)

### Community 151 - "docs/rules_evidence.md"
Cohesion: 0.07
Nodes (13): 'Decisions needed from you' is second person, never first, A model in config.MODELS with no FEATURE_MAP entry kills scoring for every sport, Every front-end change is reviewed by the UX designer agent before its PR opens, Gate the number that gets bet (cal_error_actionable), A health check must not gate on the thing that breaks, The settled live-prop record is zero bets, The Odds API returns x-requests-remaining on every response, including 401, How the pick rule was found: the NCAAF live loop delete-and-replaced every 45s (+5 more)

### Community 192 - "NFL game lines model write-up"
Cohesion: 0.11
Nodes (19): DataRegistry: source catalog with priority levels, scripts/edge_hunt.py: moneyline calibration clean, ML-vs-spread gap dead, Forecast validation (2026-08-15): rule holds at 57.09% under real day-3 error, Game totals model (consumes spread output as competitiveness), IngestOrchestrator: per-source fetch with no silent fallbacks, Middling does not clear vig, Moneyline derived from spread via fitted sigmoid, Oracle ceiling: perfect closing-line knowledge (+11 more)

### Community 209 - "Model search findings and protocol docs"
Cohesion: 0.05
Nodes (18): scripts/ncaaf_search/, Live inning gate replay, mlb_live_total_runs (in-play total), Negative-binomial (NB1) tail, pregame_total_line feature (market anchor), Live tuning panel (Models view), ncaaf_live_total 2025 in-play backtest, ncaaf_live_win_prob 2025 in-play backtest (+10 more)

### Community 213 - "nfl/live_model/README.md"
Cohesion: 0.10
Nodes (18): backtest/calibrate.py (the two gates), backtest/calibrate_props.py projection prop gate, check_feed_assumptions: automatic first-payload feed check, backtest/flow_eval.py flow test with control, Gate 1: win probability Brier 0.1654 PASS vs 0.20, Gate 2: total quantile coverage 1.26pp PASS vs 2.0pp, backtest/harness.py kill_verdict, NFL live model (two-stage engine) (+10 more)

### Community 227 - "docs: followups + clv"
Cohesion: 0.11
Nodes (22): PREGAME_PRICE_MAX_AGE_MIN (180 min) on game-market reads, Pruner keeps the opener AND the close per (proposition, book), clv_method = standard_v2 (PEDIGREE_CLV_METHODS), clv_standard_v2_2026_10_14.sql bulk rewrite, Secondary — market edge vs Pinnacle's fair close (market_clv_*), Power de-vig (bisection, 80 steps, k in [0.05, 12]), Primary CLV — same-book raw price (clv_pct, clv_pp, clv_beat_close), Same line, and the close bound (+14 more)

### Community 246 - "docs: best_line + config_topology"
Cohesion: 0.11
Nodes (19): Book roles: fetched (LINE_SHOP_BOOKMAKERS) vs offered (BEST_LINE_BOOKMAKERS), DECIDE_ON_BEST_PRICE=0 restores DraftKings as the deciding price, Stage 2: decide, size and settle at the best price (picks.decision_*), _get_event_odds fetched DraftKings-only (MLB F5, UFC round totals), The live models join best-price deciding (2026-09-10), Scoring off another book's line (picks.line_book), BEST_LINE_EXCLUDE_BOOKMAKERS — unbettable books out of shopping, BookMark.tsx / BOOK_GLYPHS registry (+11 more)

### Community 253 - "docs/history: learnings + build_state"
Cohesion: 0.09
Nodes (25): Data sources table (Odds API, SBR, MLB Stats API, Savant, Open-Meteo, NHL API, nba_api, ESPN, UFC CSV mirror, DataGolf), FanGraphs / pybaseball removed (IP-blocked); replaced by MLB Stats API + Savant, MLB_Basic.csv datawarehouse (2009-2025, 40,996 games; runline derived as -1.5), What's built (package tree) and what's not, AlphaPy rejected (deprecated, team-level only, defunct connectors), Team stats need at least 10 games before they stabilize, The go-live gate prevents going live on lucky backtests, Historical team-stat backfill uses {season}-01-01 as as_of_date (+17 more)

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
Nodes (25): catch_up_daily_pipeline / tracking/daily_retry.py, DISCORD_WEBHOOK_* variables, one channel per sport, Heartbeat watchdog -> DISCORD_WEBHOOK_OPS, LIVE_DAILY_CREDIT_CAP and RUN_LIVE_LOOP, In-play live loop under a */10 supervisor, Live monitor dashboard (monitoring/, MONITOR_TOKEN), NFL poll driver — hourly from T-10, every 10 min inside 3h, NFL wind-totals and opener-spread card jobs (+17 more)

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
Cohesion: 0.14
Nodes (14): catch_up_weekly_jobs on boot, Janitor retired 2026-09-03, ModelCalibration weekly re-measure, The pipeline watch's six rules, Sentinel (pipeline watch Routine, retired), Guardrails both agents share, UX Designer — the front-end review, Janitor (scheduled backlog runner, cannot land work) (+6 more)

### Community 407 - "docs/live_odds_freshness.md"
Cohesion: 0.16
Nodes (14): Basketball Daily Ingest stays on Matt's PC, DraftKings direct needs BOTH a browser fingerprint and a residential address, The feed has a ~45s floor and it cannot be bought past, The Odds API in-play feed is a ~45-67 s cache, Direct book feeds from both addresses (book_direct_probe.py), data/ingestors/dk_direct_feed.py (RUN_DK_DIRECT_FEED defaults 0), DK direct: fingerprint AND address are both necessary, config.live_slate_dates() — the midnight blind spot (+6 more)

### Community 420 - "mobile/docs/UX_REVIEW.md"
Cohesion: 0.16
Nodes (13): dashboard.html renderRoster(), A pick is a pick (re-priced line never replaces the locked one), Copy: formatAmerican/formatPct/formatCurrency, model ids never raw, Decided at the best bettable price; read via lib/decisionPrice.ts, frontend-ux-designer agent contract, Mobbin MCP connector (one route: Matt's claude.ai connector), Product rules: a violation is a Blocker, Reuse before invention (EmptyState, StatTile, SignalBadge, ...) (+5 more)

### Community 432 - "Performance monitoring and record views docs"
Cohesion: 0.10
Nodes (11): roi_collapse check, api_call_log table, Heartbeat watchdog, Live monitor dashboard (monitoring/), mv_scored_pick_outcomes (sweep matview), Official live date 2026-09-01, The request probe: one patch, not 75 call-site edits, Retool port of Models and Ops (+3 more)

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

### Community 456 - "NFL in-play prop assessments docs"
Cohesion: 0.12
Nodes (12): The live prop market leans over like the pre-game one, Publish backstop refuses pass-attempt overs, Accrued carries from ESPN core leaders, rush_attempt_pace model: one offset on the book's number, Pace ratio, In-play rushing-attempt UNDER on pace ratio >= 1.25, NFL prop lines lean over, NFL edge search 2026-10-11 (+4 more)

### Community 459 - "docs/signal_timing.md"
Cohesion: 0.18
Nodes (8): Does the daily pick lock cost us signals? (2026-08-23), MAX_EDGE_CAP blind spot: games with no row at all, A model re-run harness over stored snapshots (open item), Four NONE-row coverage traps, Prop NONE/AVOID rows are a survivor sample (poller clear), The pre-game line poller wipes a game's non-BET prop picks (known issue), The lock is signal-aware for NCAAF only (NONE rows refreshed, BETs lock at first cross), Signal-timing analysis — the pick lock (signal_timing.md)

### Community 460 - "NFL stat prop method search docs"
Cohesion: 0.13
Nodes (17): The eleven NFL distributional prop models, The information test: does the projection add to the line?, ESPN core injuries endpoint for NFL, NFL prop Out/Doubtful veto, DraftKings' alternate ladder over-prices every over, Market-anchored shape simulation, The eleven distributional models at their live cuts, The market stack (every signal that could locate the median) (+9 more)

### Community 461 - "mobile/docs/DISCORD_LINKING.md"
Cohesion: 0.23
Nodes (11): Migration add_discord_link_and_whop_memberships.sql, DISCORD_LINK_ENABLED flag, discord_links table, Connect Discord flow (start -> consent -> complete -> role sync), public.my_access() computes access on every read, useAccess access state hook, scripts/verify_discord_link.ts (44 assertions), whop_memberships table (+3 more)

### Community 463 - "Probability calibration design notes"
Cohesion: 0.24
Nodes (14): models/honest_ev.gate and honest_probability, tracking/system_health._report_model_calibration, MODEL_OWN_EV_FLOOR and MODELS_ON_OWN_PROBABILITY for wind and opener, fetch_graded reads picks for NFL/NCAAF/UFC/rule models, GLOBAL_MIN_EV: 0.30 then 0.20, The go-live calibration gate never computed a real number, ncaaf_over_under Platt map demoted 2026-09-26, Per-model floors (#796) measured on the calibrated number (+6 more)

### Community 479 - "docs/live_betting.md"
Cohesion: 0.20
Nodes (12): BookMoveClock — the book has moved past a cap while our state has not changed, LOCK_LIVE_PICKS_AT_FIRST_SIGNAL — the first live BET per lane is the bet of record, The live staleness guards (data/live_quote_guard.py), Live cutoffs are re-derived every pass (tracking/live_calibration.py), LIVE_MAX_BETS_PER_WEEK is advisory, not a runtime cap, config.LIVE_MODELS — a separate registry from MODELS, live_pick_features — one row per lane, the first one, under its own SAVEPOINT, The Live Signals segment on the Picks screen (+4 more)

### Community 500 - "docs/sports/wnba.md"
Cohesion: 0.21
Nodes (13): Double-double is logistic, over-only, prob-only (COMPUTE_DD sentinel), NBA: 10 models live (moneyline + 9 props), O/U and spread blocked, NBA pipeline steps (odds, prop odds, stats local, scoring, settlement), stats.nba.com blocks datacenter IPs; team stats run on the local Task Scheduler job, WNBA results from the ESPN hidden API with core-API fallback, The wnba_over_under / wnba_spread sweep was leaked (latest snapshot had no pre-tipoff cutoff), WNBA models (moneyline + assists live; points/rebounds/threes/PRA/O/U/spread paused), WNBA pipeline responsibilities (odds, props, scoring, ESPN results, local game log and stats) (+5 more)

### Community 523 - "mobile/docs/AUTHENTICATION.md"
Cohesion: 0.24
Nodes (12): App Store guideline 4.8: Google on iOS requires Apple, AUTH_ENABLED kill switch, signalbase://auth-callback redirect URL, billingReady() requires AUTH_ENABLED, discordLinkReady() requires AUTH_ENABLED, RLS pre-flight: authenticated keeps full read access, SignInScreen (SignIn route), useAuth session store (+4 more)

### Community 558 - "Model artifact and retrain docs"
Cohesion: 0.12
Nodes (17): _KNOWN_DRIFT: mlb_prop_pitcher_hits and mlb_prop_batter_sb, Matched baseline with --no-register, Opposing-starter Savant features (opp_starter_k_pct, whiff_pct, xera, bb_pct), model_artifacts_load counts what it opened, model_artifacts table fallback restore, Three separate artifact questions, three separate failures, test_every_model_artifact_on_disk_is_tracked_by_git, KNOWN_UNTRAINED — config models intentionally without artifacts (+9 more)

### Community 560 - "docs/retrain_2026_plan.md"
Cohesion: 0.18
Nodes (12): scripts/paused_model_assessment, data.ingestors.baseball_savant_ingestor, models.trainer, F5 O/U and F5 RL paused: leak-mismatched, synthetic-line trained, NCAAF in-play season replay: -3.4% and -13.1%, No model has a cut that clears on the deployed artifact, batter_sb: opp_team_sb_allowed feature, Phase 0: train 2019-2024, holdout 2025 (+4 more)

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
Cohesion: 0.31
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

### Community 883 - "In-app feedback replies runbook"
Cohesion: 0.38
Nodes (6): Abuse guards in feedback_submit (4,000 chars, 20/hour, 25 open), feedback_reply is service-role only, feedback_threads / feedback_messages, push_notifier.notify_feedback_replies, Anon grants and RLS: the schema-wide sweep (anon_readable.py, apply_anon_grants.py), In-app feedback — reading it and replying

### Community 890 - "docs/game_injury_gate.md"
Cohesion: 0.40
Nodes (5): ESPN core probables for the NHL starting goalie, A NONE from this gate is not locked — the reprice path, The gate rule — refuse a game-model BET on a confirmed Out starter/star/goalie, Fires in scorer.score_game and _score_nhl_3way, after best-price requalify, before insert, Game-model starter / star / goalie gate

## Ambiguous Edges - Review These
- `Claim: the app cannot write to the backend` → `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`  [AMBIGUOUS]
  docs/privacy.html · relation: conceptually_related_to

## Knowledge Gaps
- **105 isolated node(s):** `@babel/core`, `babel-plugin-module-resolver`, `babel-preset-expo`, `expo-asset`, `expo-dev-client` (+100 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 12479 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **207 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Table` connect `NBA public splits pipeline step` to `Scratch Postgres latest line tests`, `Mobile color contrast checker`?**
  _High betweenness centrality (0.200) - this node is a cross-community bridge._
- **What connects `@babel/core`, `babel-plugin-module-resolver`, `babel-preset-expo` to the rest of the system?**
  _105 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Mobile app shell, push and sharp score` be split into smaller, more focused modules?**
  _Cohesion score 0.017135299867747686 - nodes in this community are weakly interconnected._
- **Why does `over()` connect `Mobile color contrast checker` to `Mobile bankroll number formatting checks`, `NBA public splits pipeline step`?**
  _High betweenness centrality (0.156) - this node is a cross-community bridge._
- **Should `Mobile picks home filters and sorting` be split into smaller, more focused modules?**
  _Cohesion score 0.01596392482143445 - nodes in this community are weakly interconnected._
- **Why does `inserted_minus_start_min()` connect `NBA public splits pipeline step` to `NBA public betting splits ingestion`, `NBA public betting splits ingestor`?**
  _High betweenness centrality (0.118) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Claim: the app cannot write to the backend` and `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._