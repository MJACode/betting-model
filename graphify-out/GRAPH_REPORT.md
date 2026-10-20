# Graph Report - bm-nba-propcap  (2026-10-20)

## Corpus Check
- Large corpus: 1613 files · ~2,670,945 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 31931 nodes · 76365 edges · 945 communities (735 shown, 210 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 1971 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `970eaede`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Mobile app screens and theme
- Mobile picks home filters and sorting
- Mobile stats board
- NBA player prop model fitting
- Pregame snapshot cutoff before first pitch
- NBA book numbers and game four search
- Ingestor resilience and cache import tests
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
- Prop ladder from books and Kalshi
- mobile/scripts: verify_book_links + verify_betslip_combine
- tests/test_paused_keeps_real_verdict.py
- NBA team total under model tests
- X post queue drain tests
- Pick lock survives settlement tests
- tests/test_mlb_game_market.py
- Discord full record correction posts
- X results and free pick posts
- Threshold review report tests
- UFC phantom fight filter
- Prop box score backfill
- NBA game model prop feature tests
- Best line price shopping tests
- Mobile paywall and subscription billing
- Mobile Discord linking and access
- tests/test_nfl_opener.py
- NHL and MLB stats ingestors
- Mobile crash logging
- Mobile matchup grading and stat pills
- NBA game model luck feature tests
- CLV math same-book and market edge
- Discord publisher run lock
- tests/test_dk_direct_feed.py
- tests/test_credit_budget.py
- NBA team total luck card publisher
- Mobile daily results recap modal
- Odds prune opener and close tests
- NHL prop card publishing
- Market-relative prop edge tests
- tests/test_first_signal_repair.py
- Game injury gate and prop veto
- API call monitoring probe
- Prop price pregame cutoff tests
- Mobile markets and formatting
- Pregame line poller change detection tests
- NHL goalie as-of history
- NFL in-play game state feed
- NFL prop injury veto
- data/ingestors/nfl_inplay_history.py
- Mobile record hero and equity curve
- Mobile settings, sign-in and sportsbooks
- Mobile bankroll math and copy
- Idle database read transaction tests
- NHL market-anchored moneyline model
- NCAAF in-play pricing engine
- Mobile push test diagnostics
- NBA prop projection card
- tests/test_db_reconnect.py
- Discord recap restatement
- In-play scorer locks and push alerts
- NCAAF FBS twin game resolution tests
- tests/test_refresh_retry.py
- NBA results ingestion and prop settling
- NBA results ingestor tests
- NBA second game projection engine
- tests/test_calibration_check_coverage.py
- tests/test_book_team_map.py
- tests/test_team_board_cache.py
- NCAAF feature engine and tests
- Mobile in-app purchase billing
- nfl/live_model/tests/test_rush_attempt_pace.py
- NFL wind board fast publishing tests
- NFL in-play gameday worker
- NBA injury report daily fetch
- NFL player stats CSV ingestion
- MLB weather forecast ingestor
- NHL team rates as of date
- tests/test_dk_freshness_parse.py
- NHL moneyline rebuild and grading
- models: slate_concentration + test_slate_concentration
- NBA game model research harness
- CLV backtests and bias scans
- View migration lock handling tests
- Worker job queue retries and locks
- MLB batter prop log loading tests
- Mobile performance and tracked bets
- NBA game four point estimates
- Best line threshold sweep
- NCAAF college data ingest tests
- Mobile betslip and parlay legs
- NBA pregame scoring window
- tests/test_prop_odds_utc_stamp.py
- Live monitor web server streaming
- NCAAF opener strategy walk-forward search
- tests/test_feature_artifact_agreement.py
- NFL prop one side per line
- CLV graded at the price taken
- tests/test_cloud_retrain_artifacts.py
- NHL side models never bet against each other
- Odds pruning job and frontier
- System health checks runner
- NFL prop market Kalshi pricing tests
- tests/test_nfl_opener.py
- Player news ingestor and tests
- Discord and X results posting
- NHL blocked shots prop model
- tests/test_nfl_wind_publisher.py
- Pre-game odds and prop odds ingestors
- NFL live prop model tests
- tests/test_health_reason_and_cadence.py
- NBA odds history gap fetch tests
- tests/test_nfl_weather_supabase_readback.py
- Publish signals on write tests
- Pitcher stats as-of invariant tests
- Scorer pick label and Kelly sizing
- NBA prop market tip timing
- NHL prop per-game limit tests
- Pipeline log reason tests
- NBA in-game study two
- NFL opener and wind writer lock tests
- NFL in-play prop settlement tests
- NBA prop settlement stat loading tests
- NBA prop pricing window tests
- NFL wind publisher scored rows
- nfl/live_model/feeds: test_feed_resilience + espn
- NFL opener publisher tests
- NHL player prop projection model
- CLV settlement timeout retry tests
- Health check skip budget tests
- tests/test_live_pick_features.py
- HTTP timeout floor and probes
- Public fade detection quality tests
- Pregame price age and twin game tests
- tests/test_prop_missing_features.py
- MLB public fade top picks ranking
- NCAAF FBS registry health checks
- NFL in-play decline recorder tests
- NFL wind and opener publisher
- NCAAF live state recording tests
- tests/test_run_ledger_orphans.py
- MLB in-play history backtest
- NBA lineup stints from play-by-play
- UFC results scraper tests
- In-play calibrated decision tests
- Team total market skip rules tests
- Pre-game scorer and pick insertion
- Sharp book odds retention
- NCAAF opponent-adjusted search features
- MLB first five any-book line tests
- tests/test_repair_bogus_first_pitch_labels.py
- nfl/live_model/tests/test_executor.py
- tests/test_sbr_loader.py
- Walk-forward evaluation
- mobile/scripts/ux_scan.mts
- Mobile range slider logic
- Pick settlement and closing line capture
- Mobile player stats and game log
- Free pick and line alert tests
- NCAAF in-play underdog calibration and tick tests
- tests/test_live_quote_staleness.py
- NBA prop closing line purchase tests
- In-play publish parity with pauses
- NBA injury report fetching
- supabase/functions/_shared/discord.ts
- Worker job queue validation tests
- NFL prop odds timeout-safe slicing
- NBA totals luck replay
- NCAAF game-day pick lock tests
- scripts: build_nfl_live_leader_artifact + model
- NFL DraftKings line snapshots
- Discord post ledger and announcements
- Schema guard and table lockdown
- tests/test_discord_channel_probe.py
- tests/test_nfl_prop_one_read_per_game.py
- Bounded odds pruning keeps openers and close
- NCAAF gameday live odds cadence
- MLB prop pregame quote cutoff tests
- Multi-book odds ingestion
- scripts/nfl_edge_gameline_rules.py
- System health check pass tests
- tests/test_model_game_savepoint.py
- Health check pick delivery tests
- NBA historical odds archive parser
- tests/test_calibration_watch.py
- NBA team total odds fake database
- NFL weather history fetcher
- Ungraded model performance monitor tests
- Pipeline failure alerting and heartbeats
- NCAAF starter-out research dataset
- Score when lines open tests
- Discord publish keys and void notices
- tests/test_sbr_loader.py
- NHL totals card publisher
- MLB in-play state alignment
- Member sportsbooks scratch database tests
- tests/test_nhl_three_way_lookahead.py
- Mobile team detail stats screen
- Database write retry on dropped connection
- Prop odds next-day lookahead tests
- System health run ledger tests
- NCAAF in-play history backtest tests
- tests/test_best_line_live.py
- tests/test_sbr_loader.py
- In-play score freshness guard tests
- Team stats snapshot thinness tests
- NCAAF college data refresh and backfill tests
- UFC fight stats scoring tests
- Mobile load errors and abort handling
- NFL in-play leader model decision
- NBA team total odds fetch tests
- NFL prop settlement tests
- tests/test_void_picks.py
- tests/test_sbr_loader.py
- Mobile push notification deep links
- Job heartbeat and stale jobs
- Database setup and SQL statement splitting
- NCAAF game-day live feeds
- NFL prop backtests and walk-forward
- MLB renamed franchise game merge tests
- NFL in-play pick row building tests
- NBA box score repair tests
- Health check daily feed freshness
- tests/test_sbr_loader.py
- tests/test_daily_retry.py
- Results recap message id tests
- NFL prop market card publisher tests
- NBA line history pruning protection
- NBA results Postgres store
- tests/test_live_book_move_guard.py
- NHL prop settlement tests
- tests/test_sbr_loader.py
- MLB umpire ingestor
- Social post queue and drain
- X post image fetching
- NFL pick monitor
- NFL in-play pick writer commit tests
- NFL gameday odds and weather feeds
- Prop odds missing game skip tests
- Odds research scripts and probes
- Recap waits for NFL box scores
- NFL pick monitor join keys
- System health check test fixtures
- Mobile custom model filters and metadata
- Mobile bankroll local storage
- supabase/functions/revenuecat-webhook/index.ts
- supabase/functions/whop-webhook/index.ts
- NFL pick evaluation and monitor
- tests/test_nfl_props.py
- CLV backfill job tests
- NBA injury report PDF parsing
- Odds API credit budget
- tests/test_sbr_loader.py
- NHL blocked shots prop settlement tests
- Database grant revocation and UFC sweep
- NHL returning starter naming
- NFL in-play score distribution pricing
- Injury adjustment game features
- External feature map promotion tests
- tests/test_nfl_props.py
- NFL wind bettable book filter
- NHL blended team inputs tests
- WNBA injury team id fallback
- NFL live pick announce isolation tests
- tests/test_game_market_gate.py
- NHL prop EV regimes and Kalshi ladders
- NBA public splits quality backfill
- Pipeline watch report posting tests
- NFL prop market card tests
- NBA second-model prop study
- tests/test_score_when_lines_open.py
- tests/test_score_when_lines_open.py
- tests/test_score_when_lines_open.py
- Probability calibration map tests
- tests/test_pick_integrity.py
- NHL props newest fetch shopping
- NBA public splits archive tests
- Umpire features excluded from training
- NFL live leader moneyline odds feed
- Database connection and game feature builders
- tests/test_record_one_pick_per_event.py
- NHL opening night early season
- NHL dead API wrapper cleanup tests
- In-play pregame total line tests
- Weekly job catch-up tests
- Picks email rendering
- nfl/live_model/tests: test_props + props
- One NHL prop bet per game
- Mobile bankroll unit size hook
- NFL in-play leader gameday cadence
- Deploy checks and job queue
- ncaaf_live/tests/test_serve.py
- tests/test_wnba_prop_market.py
- tests/test_nfl_scored_rows.py
- NHL derivative totals walk-forward model
- Prop no-bet rows survive tipoff
- Mobile pick queries and stats odds
- Per-model EV floor card tests
- NHL prop card pick writing tests
- NBA prop card runner tests
- Prop odds book update time
- tests/test_recap_retries_a_skipped_day.py
- Mixed pipeline and prop tests
- MLB bet record audit tally
- MLB totals public fade scorer tests
- NFL line snapshot publishing
- Live game poller no-op connection
- NBA results ingestor fake connection
- Four NHL prop bets per night
- Weekly job boot catch-up probe
- Pregame prices current health test stub
- NBA prop market decision tests
- NHL opening night goalie lookup
- Push-adjusted win probability
- Pregame poller game creation
- Mobile subscription entitlement hook
- NFL in-play decision audit fan-out
- Publish keys and push free picks
- Mobile contrast tones and range slider
- NFL live leader game-day fake feed
- Social post test rows
- Local cache additive guard test
- Savant freshness health check tests
- NFL leader gameday fake rows
- NFL wind publisher insert-once lock
- NHL blocked shots non-dressed voiding
- Weekly catch-up cursor stub
- tests/test_ncaaf_prop_odds.py
- NBA game harness residual distribution
- MLB prop feature engine
- NBA injury report date scope test
- NCAAF in-play history tests
- X tweet delivery attempt
- X media upload step
- Retired umpire feature retrain tests
- NCAAF in-play score distribution pricing
- NFL prop player names and research cards
- tests/test_ncaaf_pbp_store.py
- tests/test_heartbeat_watchdog.py
- Discord live signal embeds and prices
- Record correction social posts
- NFL edge research shared helpers
- scripts/nfl_edge_live_rush_pace.py
- NBA prop projection tests
- NFL preregistered 2026 edge study
- tests/test_prop_calibrated_decision.py
- NBA fourth search derivative markets
- tests/test_mobile_line_movement.py
- tests/test_live_calibration.py
- NBA in-game luck study one
- NBA lineup stint derivation tests
- NBA play-by-play parsing tests
- tests/test_ncaaf_live_notify.py
- NCAAF quarterback team features
- NHL prop backtest and EV lab
- Live monitor dashboard data store
- NFL prop book bettability check
- tests/test_settled_record_is_immutable.py
- features/golf_feature_engine.py
- ncaaf_live/tests/test_states.py
- tests/test_bovada_feed.py
- NCAAF cross-book opener tests
- NFL 2024 in-play totals grading
- NFL 2025 in-play edge research
- MLB in-play odds history pull
- tests/test_health_pregame_prices_current.py
- NBA game line move study
- NBA stats and player log ingestion
- scripts/nfl_edge_extreme_props.py
- scripts/nfl_edge_settlement.py
- WNBA points prop rebuild and sweep
- tests/test_agents_contract.py
- Live model holdout comparison
- WNBA results ingestor
- NBA public betting splits ingestor
- NBA box score enrichment
- NBA derivative market lab
- scripts/nfl_preflight.py
- Mobile source logic tests via node
- NBA halftime in-game research
- MLB totals public fade under shopping
- tests/test_decide_on_calibrated.py
- NBA prop projection lab
- Kalshi game and prop ladder ingestor
- NBA in-game data staleness gate
- tests/test_model_artifacts_load.py
- Mobile live, team and player screen tests
- scripts/game_line_market_sweep.py
- Historical odds backfill and resume
- Push notification deep link tests
- tests/test_pass_instrumentation.py
- tests/test_db_adapt_sql.py
- tests/test_mobile_contrast_tokens.py
- Daily pipeline runner and steps
- NBA game four part one tests
- Calibration agent threshold sweep tests
- NBA second game line move tests
- NBA team total luck replay build
- NFL in-play prop flow anchoring tests
- WNBA prop context features
- NBA second game verdict
- Probability calibration fitting and sweep
- tests/test_nfl_live_leader_state.py
- tests/test_ncaaf_qb_ingestor.py
- NBA public splits side flipping
- tests/test_local_cache_is_additive.py
- First pitch guard for capture and delivery
- House juice price floor tests
- tests/test_ncaaf_game_identity.py
- NBA second game market tests
- Count prop over-probability dispersion
- Kalshi ladder recorder tests
- UFC results download caching
- Prop market coverage board probe
- NBA total luck card publishing
- tests/test_live_game_features.py
- UFC fight feature builder
- NFL halftime edge out-of-sample replay
- NBA quarter game model tests
- NBA second game luck studies
- Signal deliverability window tests
- Line CLV sign and orientation tests
- Mobile player stat group tests
- NBA game harness tests
- UFC fight results scraper
- NFL in-play flow slice backtest
- Discord price bound and voided picks
- Model calibration check tests
- NCAAF college data ingestor
- MLB game market card and gate
- Team stats games played invariants
- Market coverage and firing guard tests
- NCAAF player stats parser tests
- scripts/nfl_live_prop_feasibility.py
- tests/test_context_budget.py
- tests/test_player_h2h_stat_values_migration.py
- tests/test_retired_models.py
- NFL in-play flow pseudo CLV tests
- NFL in-play remaining-yards engine training
- EV floor and honest cut replays
- Scratch Postgres line state tests
- tests/test_live_record_start_views.py
- UFC historical CSV loader
- NHL prop odds fetch gate
- NFL Kalshi edge search
- nfl/models/opener_spread.py
- MLB live slate midnight discovery tests
- tests/test_nfl_wind_fire_window.py
- tests/test_public_betting_ingestor.py
- Basketball player positions ingestor
- tests/test_service_role_split.py
- Prop ladder and NBA derivative tests
- NFL research edge data cache
- Mobile sport filter persistence tests
- NBA second game projection tests
- Live game state poller triggers
- NFL in-play flow snapshot validation
- Bring your own model game facts
- NBA period map pricing tests
- NCAAF model search runner
- NCAAF CFBD ingestor tests
- Mobile screen source wiring tests
- Kalshi game market recorder
- Mobile team detail page tests
- CLV price taken app parity tests
- NCAAF totals probability regression tests
- Mobile live game status checks
- Refresh pass step ordering tests
- NHL totals market model
- NCAAF search feature leakage tests
- Mobile bankroll screen checks
- tests/test_mobile_threshold_parity.py
- NHL derivative odds job validation tests
- tests/test_track_record_views.py
- tests/test_weekly_catch_up.py
- API call rollup and pruning tests
- NCAAF steam lag study
- NFL live leader model tests
- Mobile paused catalog tests
- NFL prop shape simulation
- MLB play-by-play ingestor
- tests/test_promote_calibration_job.py
- tests/test_cfbd_snapshot_leakage.py
- NFL wind forecast stability tests
- NCAAF outcome edge scan
- NFL prop threshold window tests
- tests/test_nhl_research_job.py
- tests/test_settlement_timing.py
- NBA schedule rest and travel features
- Push delivery ticket handling tests
- NCAAF in-play play-by-play state builder
- DataGolf ingestor and NHL SBR archive
- Mobile pick category tests
- Picks unique row index tests
- NFL odds cache import to Supabase
- tests/test_health_check_observe.py
- NFL in-play prop flow model
- NFL 2026 opener and wind tracker
- NFL in-play prop line churn check
- NFL in-play prop staleness reports
- tests/test_pick_lock_is_on_picks.py
- NFL in-play pick writer
- Per-model threshold config tests
- NBA game two verdict grid tests
- MLB runline retrain sweep job tests
- MLB retrain freeze guard
- Live monitor server and feature matrix
- supabase/functions/discord-link/index.ts
- tests/test_nfl_prop_clv.py
- Team stats rebuild and verify
- tests/test_scoring_methods.py
- NFL weather edge fetch
- Team stats as-of leak invariants
- NFL ESPN injury ingestion
- Worker job queue runner
- Discord and X period recaps
- Anonymous read grant planning
- nfl/scripts/backtest_opener.py
- NCAAF totals lead and consensus gate
- tests/test_latest_odds_views.py
- NBA schedule ingestor
- NFL prop feature engine
- tests/test_transaction_pooler.py
- Env file database URL fallback
- MLB totals retrain sweep job tests
- NCAAF in-play history backtest
- Paused and no-signal pick rows tests
- Trainer no-register mode tests
- Database URL doctor
- supabase/functions/sharpsports/index.ts
- NFL prop settlement name fallback
- Rule model market reading tests
- UFC fighter name resolution
- tests/test_worker_deps.py
- scheduler.py
- Position defense ranks SQL checks
- NFL in-play leader win probability
- tests/test_mobile_stat_labels_match_the_server.py
- tests/test_ncaaf_fcs_visitor_names_migration.py
- tests/test_nfl_prop_unstarted_clear.py
- Multi-sport model research labs
- tests/test_savant_freshness.py
- tests/test_scorer_nfl_prop_like_escape.py
- NFL in-play prop model assessment
- NHL stats views tests
- Concurrent injury fetch speed tests
- Published record reconciliation checks
- Market movement feature builder
- NFL live pick price ceiling tests
- NCAAF in-play odds history pull
- tests/test_clear_unauthorized_auto_pauses_migration.py
- tests/test_ncaaf_se_louisiana_alias_migration.py
- tests/test_overnight_polling.py
- Mobile bankroll settings card
- NFL opener stake sizing and EV
- Mobile type-check baseline tests
- Model trainer and calibration metrics
- NFL prop lean concentration report
- Tracked performance verification script
- Live monitor cache tests
- CLV no-vig close capture tests
- tests/test_claude_rules_split.py
- tests/test_db_setup.py
- tests/test_dedupe_opening_signals.py
- tests/test_pbp_backfill_resilience.py
- Odds prune protected sources tests
- NFL wind forecast validation
- Paused model profitability assessment
- NCAAF quarterback ablation study
- NFL opener cut sweep and calibration
- NBA in-game study one tests
- MLB backfill retry resilience tests
- NCAAF line move spots
- NBA public splits pipeline step
- tests/test_prompt_reads_thresholds.py
- tests/test_system_health_meta_steps.py
- NCAAF situational spot evaluation
- NBA period score ingestion
- scripts/render_brand_icons.py
- Results recap NFL box score ordering
- Mobile line ruler checks
- NBA prop model verification stages
- supabase/functions/stripe-webhook/index.ts
- tests/test_drop_voided_nfl_wind_opening_signals_migration.py
- tests/test_mobile_neutral_signal_label.py
- College football data checks
- tests/test_scorer_commits_per_game.py
- NFL model import checks
- NBA ESPN box score parsing
- tests: test_wnba_availability + wnba_availability
- Mobile stat segment tabs tests
- NBA injury report time slots
- NCAAF play-by-play history puller
- supabase/functions/sharpsports-webhook: index + index
- Mobile Lines board pin tests
- X post publisher and database key checks
- supabase/functions/stripe-checkout/index.ts
- tests/test_book_list_budget.py
- Mobile type-check baseline checker
- NBA game market search lab
- NHL totals research lab
- UFC stats page parsing
- In-play honest cut sweep
- NCAAF weather totals study
- mobile/scripts/verify_a11y.ts
- Football in-play game state
- Mobile team total tests
- NFL in-play prop dataset and calibration
- Pipeline watch freshness findings
- tests/test_demote_ncaaf_over_under_platt.py
- Model quality degradation monitor
- tests/test_discord_post_one_pick_migration.py
- tests/test_game_scorer_spares_nfl_props.py
- Mobile quiet update download tests
- NBA team total luck replay tests
- NFL prop week one candidate pool
- NFL Kalshi price history fetch
- MLB totals public fade card
- NBA prop model research lab
- Mobile stats filter UX verify
- NFL prop pulled quote filter
- NBA injury report PDF layout parser
- Pipeline watch silence and regressions
- NFL prop too-early kickoff ceiling
- NBA injury report player matching
- NFL wind stake past calibration tests
- NFL kickoff-hour live wind readings
- Threshold sweep price floor tests
- NCAAF prop market rule sweep
- NFL prop market stacking studies
- NFL 2026 track policy pins
- NCAAF in-play model re-sweep
- Scorer keeps off-DraftKings priced bets tests
- Historical odds file loader
- NCAAF structural spot scan
- Live model grouped cross-validation
- NCAAF in-play history credit sharding
- Social post client tests
- Every named sportsbook is fetched
- Duplicate pick copy exclusion
- NBA harness cell emission fakes
- NFL prop local cache pull
- MLB in-play inning gate replay
- Mobile NHL look-ahead window tests
- NBA public betting splits ingestion
- NBA injury report name normalising
- NBA public splits quality flags
- Parlay leg correlation estimates
- Eastern time game date tests
- Mobile accessibility verify script
- Market handicap feature tests
- mobile/scripts/verify_a11y.ts
- mobile/scripts/verify_a11y.ts
- Prop CLV and SQL escaping tests
- mobile/scripts/verify_a11y.ts
- NCAAF margin and totals evaluation
- Mobile error states and books tests
- NFL 2024 in-play replication tables
- Shared database and config helpers
- NHL derivative totals card
- Calibration eligibility notes test
- No record-only mode guard tests
- MLB public fade top-k backtest
- NFL QB wind and NBA in-game tests
- Team stats live season verify test
- Team stats boundary tolerance check
- Team stats date format checks
- Team stats MLB alias leak test
- Manual X posts runbook
- NFL live pick game date resolution
- NHL box score parsing
- tests/test_team_board_commence_bound.py
- Calibration watch sweep queries
- NBA play-by-play clock parsing
- NBA public splits game dating
- Team stats series refusal test
- Rich market handicap feature builder
- Failed prune reported as failed step
- NFL in-play prop publish refusal
- mobile/scripts/verify_a11y.ts
- Market coverage probe candidates
- NFL in-play multi-player bet locks
- NFL prop publish skips missing games
- Opening versus closing strategy analysis
- Pipeline credit burn findings
- NBA game projection consensus gap tests
- Pipeline watch announce and escalation
- NCAAF state build file naming
- NBA team total feed test patching
- Test fixtures and in-memory database
- NCAAF college stats payload parsing
- Weekly catch-up probe rollback test
- NHL goalie save rate regression
- NFL in-play backtest replay harness
- NBA public splits row building tests
- NFL in-play pick announcements
- College football school name matching
- NBA play-by-play player id aliases
- Worker service role split test
- NBA game two price cache check
- MLB totals public fade tests
- NFL live leader call cap test
- Dashboard rule model cut test
- Pipeline watch health findings
- Recap delivery failure findings
- NFL prop feature group concatenation
- NBA public splits preseason skip test
- Social posts dry-run default
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
- NBA play-by-play lineup stints doc
- Mobile developer tooling dependencies
- NFL kickoff wind reads migration
- Unmatched player positions table
- Social post queue migration
- Opening signals shadow table
- In-app feedback thread tables
- NBA 2026-27 rebuild write-up
- docs/rules_evidence.md
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
- NFL prop over-lean research docs
- mobile/docs/UX_REVIEW.md
- Model quality monitor and MLB totals docs
- docs/sports: ufc + golf
- mobile/docs/BILLING.md
- .claude/agents: frontend-ux-designer + CLAUDE
- .claude/rules/picks-and-publishing.md
- .claude/rules/model-updates.md
- docs/signal_timing.md
- mobile/docs/DISCORD_LINKING.md
- Probability calibration design notes
- docs/live_betting.md
- NFL model bundle restore docs
- docs/sports/wnba.md
- mobile/docs/AUTHENTICATION.md
- .claude/rules/frontend.md
- Model artifact and health docs
- docs/retrain_2026_plan.md
- Calibration and NFL wind opener tracking docs
- docs/reviews/2026-09-07-nfl-props-deep-dive.md
- docs/market_coverage.md
- (root): pr-ci + requirements
- NFL props sources and prediction market research
- NFL wind totals runbook and staking
- mobile/docs/BILLING.md
- docs/testing.md
- CLAUDE.md
- Model research findings docs
- docs: nhl_market_lab + nhl_clv_ev_assessment
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

## Communities (945 total, 210 thin omitted)

### Community 5 - "Mobile app screens and theme"
Cohesion: 0.02
Nodes (286): AppErrorBoundary, IoniconName, Props, Props, State, Nav, Props, Props (+278 more)

### Community 0 - "Mobile picks home filters and sorting"
Cohesion: 0.02
Nodes (136): P, ActivePill, Props, DateOption, DayRow, SelectableGame, modelCategory, FilterablePick (+128 more)

### Community 1 - "Mobile stats board"
Cohesion: 0.01
Nodes (458): P, TouchSet, PlayerPropQuote, Sport, AnytimeMatchupView, AnytimeSortRow, DefenseRank, gapReason (+450 more)

### Community 10 - "NBA player prop model fitting"
Cohesion: 0.03
Nodes (84): Spec, collapse_official(), compact_report(), minutes_cols(), predict_means(), rate_cols(), alias_key(), all_rates() (+76 more)

### Community 101 - "Pregame snapshot cutoff before first pitch"
Cohesion: 0.03
Nodes (39): TestPregameSnapshotGuard, pregame_cutoff_sql(), trusted_first_pitch(), _mark_in_play(), _is_pregame_snapshot(), _parse_iso_ts(), load_market_movement(), _snap_sort_key() (+31 more)

### Community 105 - "NBA book numbers and game four search"
Cohesion: 0.03
Nodes (77): Point, even_gap(), ladder_mask(), main_rungs(), _one_rung(), split_main_rungs(), visible_numbers(), cache_for() (+69 more)

### Community 108 - "Ingestor resilience and cache import tests"
Cohesion: 0.03
Nodes (27): _Meter, _Resp, main(), rows_from_file(), source_for(), stadium_from_name(), test_a_dropped_connection_is_retried(), test_an_http_error_is_NOT_retried() (+19 more)

### Community 11 - "NBA totals luck model decision tests"
Cohesion: 0.03
Nodes (64): Decision, TotalLuckBet, _Conn, _Cur, decide(), pricing_dist(), quote_frame(), scheduled_games() (+56 more)

### Community 113 - "tests/test_nfl_live_leader_gameday.py"
Cohesion: 0.07
Nodes (30): FakeClock, FakeConn, FakeFeed, art(), live_state(), quote_payload(), _run_loop(), test_a_failed_odds_fetch_backs_off_instead_of_calling_every_tick() (+22 more)

### Community 114 - "nfl_live_leader/gameday.py"
Cohesion: 0.08
Nodes (25): GameContext, release_read(), parse_book_ts(), quote_predates_score(), build_pick(), evaluate(), is_locked(), load_context() (+17 more)

### Community 115 - "tests/test_calibration_promotion.py"
Cohesion: 0.07
Nodes (25): FakeConn, eligibility_clause(), maps_materially_differ(), promote(), _payload(), _row(), test_a_broken_table_is_identity_maps_not_an_exception(), test_a_map_that_does_not_help_is_silent() (+17 more)

### Community 116 - "tests/test_score_off_any_book_line.py"
Cohesion: 0.08
Nodes (33): _FakeConn, _fallback_line_quote(), _cut(), _on(), _pick(), _row(), _sql_const(), _src() (+25 more)

### Community 12 - "Mobile lines board and all books sheet"
Cohesion: 0.04
Nodes (113): LinesMarket, LinesMarkPick, linesMarks, LinesMlMode, LinesOddsRow, LinesPickRef, LinesSheetRow, LinesSheetSide (+105 more)

### Community 120 - "tests/test_ncaaf_alias_scores.py"
Cohesion: 0.08
Nodes (32): _FakeConn, _FakeCursor, alias_score_updates(), mirror_scores_to_alias_rows(), mirror_stored_finals(), _slug_pair(), _cfbd(), _row() (+24 more)

### Community 121 - "Alternate prop line fetching tests"
Cohesion: 0.07
Nodes (27): _Conn, _Resp, alt_markets_due(), _ou(), _parse(), test_a_422_retries_without_the_alternates_before_going_dk_only(), fake_get(), test_a_422_with_no_alternates_still_takes_the_dk_only_retry() (+19 more)

### Community 123 - "tests/test_backtester.py"
Cohesion: 0.07
Nodes (9): TestCalibrationError, TestComputeBacktestSummary, TestEvaluateResult, TestGoLiveGateConstants, TestIterSides, _calibration_error(), compute_backtest_summary(), _evaluate_result() (+1 more)

### Community 125 - "NFL in-play odds client and smoke check"
Cohesion: 0.09
Nodes (15): CreditBudgetExceeded, CreditMeter, LiveOddsClient, Quote, best_price(), parse_events(), _parse_ts(), _side_of() (+7 more)

### Community 129 - "NBA prop market lab"
Cohesion: 0.09
Nodes (44): NBTable, add_units(), assemble(), best_per_key(), boot_ci(), build_quotes(), candidates_from(), choose_floor() (+36 more)

### Community 13 - "Discord pick notifier tests"
Cohesion: 0.02
Nodes (119): _FakeConn, _FakeResult, _Resp, _StampConn, test_producer_output_builds_a_live_embed(), _cand(), _et_now_iso(), _freeze_now() (+111 more)

### Community 131 - "nfl/live_model/tests/test_backup_snaps.py"
Cohesion: 0.09
Nodes (23): _FakeConn, _FakeCur, back_up(), _connect(), digest(), _flush(), iter_files(), main() (+15 more)

### Community 134 - "Prop ladder from books and Kalshi"
Cohesion: 0.06
Nodes (25): Ladder, Rung, _expit(), from_kalshi(), from_one_sided_overs(), _logit(), _monotone(), _ladder() (+17 more)

### Community 135 - "mobile/scripts: verify_book_links + verify_betslip_combine"
Cohesion: 0.06
Nodes (37): betslipCombineKind, combineBetMgm(), combineBetslipLinks(), combineCaesars(), combineDraftKings(), combineEspnBet(), combineFanDuel(), fanDuelPairs() (+29 more)

### Community 138 - "tests/test_paused_keeps_real_verdict.py"
Cohesion: 0.06
Nodes (35): _Capture, _bet(), _bodies(), _code(), _fn(), _pause(), _prop(), _rules() (+27 more)

### Community 14 - "NBA team total under model tests"
Cohesion: 0.04
Nodes (41): TeamTotalDecision, min_odds_for(), book_ages(), decide(), record(), home_part(), signal(), _named() (+33 more)

### Community 140 - "X post queue drain tests"
Cohesion: 0.14
Nodes (37): _Fetcher, Poster, QueueConn, _Uploader, _blank(), _drain(), _no_network(), test_a_bad_reply_target_fails_without_posting() (+29 more)

### Community 143 - "Pick lock survives settlement tests"
Cohesion: 0.08
Nodes (22): _SqliteShim, conn(), _game(), _pick(), _survivors(), test_a_bet_is_never_dropped_for_an_earlier_no_signal(), test_a_dead_zone_prop_row_locks_too(), test_a_final_game_is_not_a_scoring_target() (+14 more)

### Community 146 - "tests/test_mlb_game_market.py"
Cohesion: 0.07
Nodes (28): GameMarketBet, _SlateConn, find_spread_bets(), find_total_bets(), _gap_seconds(), _is_runline(), publish_enabled(), pick_rows() (+20 more)

### Community 149 - "Discord full record correction posts"
Cohesion: 0.07
Nodes (26): LedgerUnread, Conn, delete_custom_record_post(), _jump(), _place(), _publish(), publish_full_record(), publish_full_record_standard() (+18 more)

### Community 15 - "X results and free pick posts"
Cohesion: 0.02
Nodes (72): _R, test_the_prop_fetch_never_buys_a_game_it_was_not_given(), execute(), test_a_push_only_period_does_not_invent_an_roi(), test_the_period_tweet_uses_the_daily_tally_and_states_roi(), test_discord_free_pick_candidates_refuse(), execute(), fetchall() (+64 more)

### Community 150 - "Threshold review report tests"
Cohesion: 0.04
Nodes (36): _Conn, _DdlConn, _DdlRes, _is_paused(), _quiet(), rule_only(), _slate(), test_a_failed_lock_down_does_not_lose_the_table() (+28 more)

### Community 154 - "UFC phantom fight filter"
Cohesion: 0.21
Nodes (6): TestFilterUfcPhantom, TestIsKnownUfcMatchup, _filter_ufc_phantom(), _is_known_ufc_matchup(), _game(), _odds()

### Community 155 - "Prop box score backfill"
Cohesion: 0.05
Nodes (44): GradeConn, ScriptConn, call_in_savepoint(), statement_timeout(), _call_fill(), _cooled(), _day(), _default_mlb() (+36 more)

### Community 156 - "NBA game model prop feature tests"
Cohesion: 0.06
Nodes (40): _Stop, _box(), _g(), _games(), _inj(), _model(), _props(), _run() (+32 more)

### Community 158 - "Best line price shopping tests"
Cohesion: 0.04
Nodes (39): FakeConn, TwoOrientationConn, FakeConn, _best_game_price(), _best_game_price_one(), _best_of(), _best_prop_price(), _same_line() (+31 more)

### Community 160 - "Mobile paywall and subscription billing"
Cohesion: 0.09
Nodes (39): BillingRail, Plan, PlanKey, Nav, planFor(), describeSubscription(), formatPerMonth(), formatPrice() (+31 more)

### Community 162 - "Mobile Discord linking and access"
Cohesion: 0.11
Nodes (36): AccessState, useAccess, useEntitlement, FunctionResponse, LinkResult, AccessRow, AccessSource, DiscordCallback (+28 more)

### Community 164 - "tests/test_nfl_opener.py"
Cohesion: 0.15
Nodes (7): TestFreshNumberLabel, TestHeldMinutes, _giants_board(), _giants_prior_at_2129(), _giants_sched(), _obs(), _ts()

### Community 165 - "NHL and MLB stats ingestors"
Cohesion: 0.01
Nodes (127): TestLogRowBuilders, TestNoHollowTeamRowBeforeTheFirstGame, _default_fetch(), fetch_espn_nhl_probables(), _https(), parse_probable(), _team_abbrev(), _fetch_bat_hands() (+119 more)

### Community 166 - "Mobile crash logging"
Cohesion: 0.11
Nodes (34): CrashContext, CrashLogDeps, CrashReport, ErrorUtilsShape, KeyValueStore, LaunchMarker, LaunchStage, ReportKind (+26 more)

### Community 17 - "Mobile matchup grading and stat pills"
Cohesion: 0.04
Nodes (62): MatchupGrade, MatchupInfo, TonightMatchupRow, check(), grade(), main(), read(), defenceMetricLabel() (+54 more)

### Community 170 - "NBA game model luck feature tests"
Cohesion: 0.05
Nodes (39): _Stop, _against_bet(), _f6c_inputs(), _games_for_standings(), _gs(), _market_pricing(), _one_game_data(), _pair() (+31 more)

### Community 171 - "CLV math same-book and market edge"
Cohesion: 0.06
Nodes (29): _Conn, _Res, implied(), test_a_one_way_close_is_not_de_vigged(), test_a_worse_close_is_negative_and_equal_prices_are_zero(), test_devigging_the_taken_price_is_not_what_primary_does(), test_kalshi_close_is_not_de_vigged(), test_market_edge_devigs_only_the_close() (+21 more)

### Community 174 - "Discord publisher run lock"
Cohesion: 0.08
Nodes (15): _Conn, _Result, _clear_locks(), _no_prod_threshold_sync(), _signal_row(), test_a_connection_that_cannot_lock_still_publishes(), test_an_exception_mid_publish_does_not_wedge_every_later_pass(), test_every_signal_publisher_takes_the_lock() (+7 more)

### Community 175 - "tests/test_dk_direct_feed.py"
Cohesion: 0.09
Nodes (23): _Conn, _game_id_for(), poll_once(), _row_for(), _seen_key(), _rec(), test_a_line_move_is_a_new_quote(), test_a_market_we_do_not_understand_is_dropped_not_guessed() (+15 more)

### Community 177 - "tests/test_credit_budget.py"
Cohesion: 0.09
Nodes (22): _Conn, daily_burn(), latest_remaining(), plan_credit_budget(), _burn_conn(), _plan(), test_a_billing_reset_is_not_a_refund(), test_a_call_is_billed_at_what_the_api_says_it_cost() (+14 more)

### Community 178 - "NBA team total luck card publisher"
Cohesion: 0.07
Nodes (25): TeamTotalBet, newest_season(), step_mlb_total_public_fade(), step_nba_team_total_luck(), step_nba_total_luck(), artifact(), decided_games(), ensure_decisions_table() (+17 more)

### Community 18 - "Mobile daily results recap modal"
Cohesion: 0.05
Nodes (66): Bucket, FixturePick, Acc, DailyResults, DayGameSummary, DayStakeStats, ModelDayStats, ScopedDailyResults (+58 more)

### Community 189 - "Odds prune opener and close tests"
Cohesion: 0.07
Nodes (18): StandIn, drain(), test_a_prop_row_on_a_game_moved_past_today_waits_for_the_game(), test_dates_below_the_floor_are_left_alone(), test_every_delete_is_committed_on_its_own(), test_the_odds_prune_never_visits_a_path_kept_sport_s_games(), test_ties_keep_the_lowest_id_as_the_opener(), _prune() (+10 more)

### Community 19 - "NHL prop card publishing"
Cohesion: 0.06
Nodes (23): TestTheCard, TestWhoThePlayerIs, step_nhl_prop_scoring(), bs_implied(), candidates(), decide(), identities(), latest_quotes() (+15 more)

### Community 191 - "Market-relative prop edge tests"
Cohesion: 0.06
Nodes (27): MarketBet, TestNaNIsAbsent, devig(), find_bets(), card(), load_quotes(), _bets_from_kalshi(), _zero_vig_american() (+19 more)

### Community 193 - "tests/test_first_signal_repair.py"
Cohesion: 0.07
Nodes (28): _Conn, _VoidedConn, step_restore_first_signals(), patch_conn(), _make(), _sql_of(), test_a_lane_already_holding_its_first_bet_is_untouched(), test_a_lane_with_no_sibling_still_restores() (+20 more)

### Community 194 - "Game injury gate and prop veto"
Cohesion: 0.09
Nodes (30): _InjConn, apply_to_picks(), _goalie_names(), load_sport_injury_index(), _pitcher_names(), player_matches_veto(), _star_names(), stars_from_logs() (+22 more)

### Community 196 - "API call monitoring probe"
Cohesion: 0.04
Nodes (47): _Resp, _credits_from(), _drain(), _enqueue(), instrumented(), _now(), _patch_curl_cffi(), instrumented() (+39 more)

### Community 199 - "Prop price pregame cutoff tests"
Cohesion: 0.05
Nodes (28): FakeConn, _StubConn, resolve_feed_name(), _get_prop_dk_odds(), _latest_book_prop_row(), _latest_dk_prop_row(), test_accented_roster_name_matches_the_flat_feed_name(), test_ambiguity_is_a_miss_not_a_guess() (+20 more)

### Community 2 - "Mobile markets and formatting"
Cohesion: 0.01
Nodes (361): Row, Props, Props, Props, IoniconName, Props, Props, clvBetQuote (+353 more)

### Community 200 - "Pregame line poller change detection tests"
Cohesion: 0.04
Nodes (46): _PollConn, changed_rows(), _fingerprint(), _key(), last_known_prices(), _num(), over_credit_cap(), poll_once() (+38 more)

### Community 203 - "NHL goalie as-of history"
Cohesion: 0.20
Nodes (3): GoalieBook, TestGoalieAsOf, _g()

### Community 205 - "NFL in-play game state feed"
Cohesion: 0.10
Nodes (20): CoreClient, EventMeta, LiveState, _abbr(), game_seconds(), https(), in_window(), _int() (+12 more)

### Community 206 - "NFL prop injury veto"
Cohesion: 0.09
Nodes (19): _InjConn, apply_injury_veto(), _as_dt(), load_nfl_injury_index(), player_is_vetoed(), _bet(), _idx(), _quotes() (+11 more)

### Community 209 - "data/ingestors/nfl_inplay_history.py"
Cohesion: 0.16
Nodes (22): Budget, buy_halftime(), buy_inplay(), events_for(), _floor5(), _get(), halftime_requests(), halftime_windows() (+14 more)

### Community 21 - "Mobile record hero and equity curve"
Cohesion: 0.05
Nodes (78): EquityPoint, plotLayout, PlotPad, ParlaySummary, SportGroup, TrackRecordSummary, ParlayTrackRow, TrackRecordRow (+70 more)

### Community 210 - "Mobile settings, sign-in and sportsbooks"
Cohesion: 0.02
Nodes (166): Calls, AuthState, AuthStatus, State, ConnectionMap, providerMeta, SportsbookConnection, SportsbookProvider (+158 more)

### Community 211 - "Mobile bankroll math and copy"
Cohesion: 0.09
Nodes (30): BankrollCheck, BankrollCommit, BankrollPatch, BankrollRead, NumberSeparators, Part, walk(), deviceSeparators() (+22 more)

### Community 215 - "Idle database read transaction tests"
Cohesion: 0.07
Nodes (15): ViewMigrationResult, _Rec, apply_view_migrations(), _flat(), test_a_lock_timeout_fails_that_file_and_the_next_still_runs(), test_a_locked_bet_releases_the_lock_check(), test_a_quiet_tick_rolls_the_read_back(), test_a_tick_that_writes_does_not_roll_the_insert_back() (+7 more)

### Community 216 - "NHL market-anchored moneyline model"
Cohesion: 0.05
Nodes (32): OffsetLogit, _Fixed, _GamesConn, _add_rating(), build_inputs(), choose_C(), decision_window(), fit() (+24 more)

### Community 217 - "NCAAF in-play pricing engine"
Cohesion: 0.04
Nodes (31): LiveEngine, american_to_prob(), correct_for_pregame(), expected_value(), _is_paused(), _load_pregame_calibration(), pregame_dog_points(), test_ev_floor_cannot_fire_without_a_price() (+23 more)

### Community 218 - "Mobile push test diagnostics"
Cohesion: 0.07
Nodes (47): PushState, PushStatus, ForcedOnlyReason, PushDiagnosis, PushFailureReason, TestPushResult, reasonOf(), NotificationsCard() (+39 more)

### Community 22 - "NBA prop projection card"
Cohesion: 0.06
Nodes (35): ProjectionBet, espn_compact(), step_nba_prop_project(), decided_games(), backfill_official(), decided_games(), ensure_tables(), espn_pulls() (+27 more)

### Community 220 - "tests/test_db_reconnect.py"
Cohesion: 0.09
Nodes (16): _Conn, _Cursor, _is_write(), _lost(), test_a_committed_transaction_is_clean_again(), test_a_lost_connection_with_uncommitted_writes_raises_connection_lost(), test_a_read_on_a_lost_connection_reconnects_and_retries(), test_a_statement_timeout_is_not_a_lost_connection() (+8 more)

### Community 222 - "Discord recap restatement"
Cohesion: 0.08
Nodes (16): _Conn, test_a_restated_recap_is_labelled_and_says_why(), _resp(), test_a_404_is_an_answer_not_a_retry(), test_a_persistent_403_still_raises_after_the_last_attempt(), test_a_recap_whose_count_merely_drifted_is_not_due(), test_a_recap_with_a_late_settlement_is_due(), test_a_transient_403_is_retried_and_the_second_answer_is_used() (+8 more)

### Community 223 - "In-play scorer locks and push alerts"
Cohesion: 0.13
Nodes (18): FakeConn, _Rows, _write_live_picks(), _locked_live_lanes(), _log_lines(), _pick(), test_a_locked_lane_still_says_so_and_names_the_lane(), test_all_lanes_locked_touches_nothing() (+10 more)

### Community 224 - "NCAAF FBS twin game resolution tests"
Cohesion: 0.16
Nodes (12): _Conn, _Result, _fold(), load_context(), _night_twin(), _pair_key(), _row(), test_a_twin_does_not_silently_take_the_row_without_lines() (+4 more)

### Community 225 - "tests/test_refresh_retry.py"
Cohesion: 0.15
Nodes (22): RefreshRun, _decide(), _done(), _run(), test_a_failed_view_migration_fails_the_step(), test_a_pass_that_finished_with_failed_steps_ran_its_chain(), test_a_redeploy_between_passes_replaces_nothing(), test_a_restart_loop_does_not_buy_odds_on_every_boot() (+14 more)

### Community 226 - "NBA results ingestion and prop settling"
Cohesion: 0.08
Nodes (21): PlayerResolver, box_is_complete(), build_dnp_rows(), build_log_rows(), fallback_id(), ingest_nba_results(), _is_team(), main() (+13 more)

### Community 228 - "NBA results ingestor tests"
Cohesion: 0.09
Nodes (31): _ESPN, FakeStore, _FixedNow, fill_missing(), _default_nba(), _default_nhl(), _game(), _ppd_game() (+23 more)

### Community 23 - "NBA second game projection engine"
Cohesion: 0.03
Nodes (91): EW, Last, Model, PointInputs, State, World, actuals(), apply_models() (+83 more)

### Community 231 - "tests/test_calibration_check_coverage.py"
Cohesion: 0.12
Nodes (17): _Shim, _bet(), _calibration_results(), db(), _graded(), _make_db(), _only(), _promote() (+9 more)

### Community 233 - "tests/test_book_team_map.py"
Cohesion: 0.06
Nodes (26): _Conn, abbr_from_team_string(), resolve_game_id(), split_matchup(), test_a_non_mlb_sport_is_refused_rather_than_guessed(), test_a_string_with_no_at_sign_is_refused(), test_a_unique_game_resolves(), test_an_ambiguous_game_resolves_to_none() (+18 more)

### Community 234 - "tests/test_team_board_cache.py"
Cohesion: 0.08
Nodes (10): _Conn, _Cursor, team_board_pairs(), team_board_seasons(), _cols(), test_every_team_sport_gets_last_this_and_next_year(), test_one_failing_pair_does_not_stop_the_rest(), test_the_cache_the_refresh_and_the_thin_function_name_the_same_columns() (+2 more)

### Community 235 - "NCAAF feature engine and tests"
Cohesion: 0.03
Nodes (49): TestComputeTarget, _SqliteShim, _compute_target(), _assemble_ncaaf_features(), _blk_points_l3(), _blk_stats(), build_bulk_ncaaf_lookups(), build_ncaaf_features_from_bulk() (+41 more)

### Community 236 - "Mobile in-app purchase billing"
Cohesion: 0.13
Nodes (25): BillingDisabledError, CheckoutResult, IapPurchaseResult, PurchasesSDK, MinimalCustomerInfo, MinimalPackage, assertBillingReady(), billingErrorMessage() (+17 more)

### Community 238 - "nfl/live_model/tests/test_rush_attempt_pace.py"
Cohesion: 0.07
Nodes (21): Read, pace_ratio(), _sigmoid(), under_prob(), _price(), test_a_line_he_has_already_passed_is_not_a_live_proposition(), test_a_missing_accrued_count_is_refused_not_treated_as_zero(), test_a_reachable_over_is_declined_rather_than_faded() (+13 more)

### Community 239 - "NFL wind board fast publishing tests"
Cohesion: 0.12
Nodes (14): FakeConn, _append_board(), _body(), _row(), _sent(), _setup(), test_a_half_written_last_row_waits_for_the_next_tick(), test_a_killed_step_fails_the_run_loudly_after_publishing() (+6 more)

### Community 24 - "NFL in-play gameday worker"
Cohesion: 0.06
Nodes (15): _Q, GamedayWorker, GameTracker, test_a_host_switch_is_alerted(), test_the_worker_self_checks_once_and_alerts_on_a_broken_feed(), test_a_one_sided_quote_is_skipped_rather_than_priced_on_raw_juice(), test_anchor_does_not_match_a_different_game(), test_anchor_matches_on_the_matchup_not_the_event_id() (+7 more)

### Community 242 - "NBA injury report daily fetch"
Cohesion: 0.12
Nodes (17): Fetcher, _all_slots(), ensure_tables(), load_players(), load_schedule(), main(), previous_report(), pull_with_retry() (+9 more)

### Community 243 - "NFL player stats CSV ingestion"
Cohesion: 0.03
Nodes (47): TestGamesRows, TestKickoff, TestParsePlayerRows, TestParseTeamRows, TestUpcomingRows, TestParseNflverseScores, backfill_savant_stats(), _df_to_rows() (+39 more)

### Community 244 - "MLB weather forecast ingestor"
Cohesion: 0.06
Nodes (16): _Resp, TestTheHourIsTheGamesOwn, TestTheRequestCoversTheTargetHour, TestTheStoreReadsTheStartTime, TestTheUmpireLandsOnEveryPass, _celsius_to_f(), fetch_and_store_weather_for_date(), _fetch_open_meteo() (+8 more)

### Community 247 - "tests/test_dk_freshness_parse.py"
Cohesion: 0.12
Nodes (17): _FakeConn, _FakeResult, _american(), parse_dk_payload(), _store(), _payload(), test_a_half_priced_market_is_dropped_rather_than_half_recorded(), test_an_event_with_no_markets_yields_nothing_rather_than_raising() (+9 more)

### Community 248 - "NHL moneyline rebuild and grading"
Cohesion: 0.02
Nodes (126): OffsetLogit, build_training_dataset(), log_loss(), accuracy(), first_games(), logloss(), main(), sweep() (+118 more)

### Community 249 - "models: slate_concentration + test_slate_concentration"
Cohesion: 0.15
Nodes (15): SlateConcentration, apply_slate_guard(), apply_slate_concentration_guard(), _attr(), _edge_of(), _is_bet(), measure_side_concentration(), _side_of() (+7 more)

### Community 25 - "NBA game model research harness"
Cohesion: 0.04
Nodes (57): Data, attach_fetch(), blind_by_real_side(), blind_pool(), blind_side(), boot(), cell_report(), cents() (+49 more)

### Community 250 - "CLV backtests and bias scans"
Cohesion: 0.14
Nodes (9): ShrunkEnsemble, add_form(), build(), feature_columns(), market_features(), team_game_stats(), fmt(), main() (+1 more)

### Community 251 - "View migration lock handling tests"
Cohesion: 0.09
Nodes (23): _Conn, _Deadlock, _LockTimeout, _StatementTimeout, _Syntax, execute(), _before(), _code() (+15 more)

### Community 256 - "Worker job queue retries and locks"
Cohesion: 0.08
Nodes (17): _Conn, _fake(), test_a_busy_queue_claims_nothing(), fetchone(), test_a_failing_job_is_requeued_until_the_attempt_cap(), _boom(), test_a_final_failure_is_announced(), test_a_success_is_announced_too() (+9 more)

### Community 257 - "MLB batter prop log loading tests"
Cohesion: 0.10
Nodes (9): _Rec, _ScoringConn, _log_sql(), test_batter_log_scan_is_pinned_to_the_lookback_not_the_catalog(), test_five_models_share_one_log_load(), test_no_lineup_does_not_scan_the_log(), test_starter_log_inside_the_batter_loader_uses_the_same_floor(), test_the_batter_loop_hands_one_cache_to_every_model() (+1 more)

### Community 26 - "Mobile performance and tracked bets"
Cohesion: 0.09
Nodes (40): StakeMode, StakeState, LiveTrackSnapshot, TrackedBetRow, trackedBetStatus, TrackedBetSummary, emit(), load() (+32 more)

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
Nodes (195): Props, ParlayRestorePayload, ResolvedSlip, GameLineLegSpec, GameLineMarket, LineLegSpec, LineSheetInput, LineSide (+187 more)

### Community 270 - "NBA pregame scoring window"
Cohesion: 0.08
Nodes (23): PregamePlan, _db(), _decided_by(), _fires(), _job(), _slate(), test_a_close_alone_runs_only_the_close(), test_a_failed_team_total_step_is_an_error_after_publishing() (+15 more)

### Community 273 - "tests/test_prop_odds_utc_stamp.py"
Cohesion: 0.12
Nodes (13): _Conn, _assert_utc_stamp(), _frozen(), _run_mlb(), capture(), events(), _run_ncaaf(), test_an_eastern_row_then_a_later_utc_row_sorts_in_time_order() (+5 more)

### Community 274 - "Live monitor web server streaming"
Cohesion: 0.29
Nodes (4): Handler, _connect(), dumps(), _json_default()

### Community 277 - "NCAAF opener strategy walk-forward search"
Cohesion: 0.10
Nodes (18): FoldResult, experiment_bands(), experiment_crossbook(), experiment_model(), _load_cross_book(), main(), _open_features(), brier() (+10 more)

### Community 278 - "tests/test_feature_artifact_agreement.py"
Cohesion: 0.11
Nodes (13): _Stub, _TolerantUnpickler, _load(), _newest_artifact(), test_artifact_width_matches_its_own_feature_cols(), test_config_list_matches_the_trained_artifact(), test_known_drift_only_names_real_models(), test_pending_features_are_not_live_without_a_retrain() (+5 more)

### Community 279 - "NFL prop one side per line"
Cohesion: 0.16
Nodes (8): _Conn, best_per_prop(), _hockenson(), test_a_different_market_on_the_same_player_is_still_its_own_bet(), test_input_order_does_not_decide_the_side(), test_nfl_publish_will_not_add_the_other_side_of_a_locked_line(), test_opposite_sides_of_one_line_collapse_to_the_bigger_edge(), test_wnba_publish_will_not_add_the_other_side_of_a_locked_line()

### Community 28 - "CLV graded at the price taken"
Cohesion: 0.03
Nodes (43): _Conn, _Res, _SnapConn, _fn(), _migration(), _pick(), test_a_draftkings_decided_row_is_unchanged(), test_a_legacy_row_that_cannot_be_re_measured_leaves_the_old_method() (+35 more)

### Community 281 - "tests/test_cloud_retrain_artifacts.py"
Cohesion: 0.10
Nodes (12): _Conn, _restore_artifact(), test_a_failed_upload_does_not_lose_a_model_that_trained(), test_a_missing_artifact_table_is_not_an_error_on_restore(), test_a_no_register_run_stores_nothing(), test_load_model_actually_loads_from_the_store_when_the_file_is_gone(), fetchone(), test_load_model_returns_none_when_the_store_has_nothing_either() (+4 more)

### Community 282 - "NHL side models never bet against each other"
Cohesion: 0.08
Nodes (28): _Conn, _ThreeWay, _apply_side_conflicts(), bets(), _endings_won(), picks_cannot_both_win(), side_checked_models(), ml() (+20 more)

### Community 283 - "Odds pruning job and frontier"
Cohesion: 0.07
Nodes (21): Budget, BudgetSpent, FrontierUnreadable, _absorb(), count_sql(), _day(), delete_sql(), doomed_sql() (+13 more)

### Community 285 - "System health checks runner"
Cohesion: 0.05
Nodes (25): HealthReport, rollback_savepoint(), ncaaf_season_for_date(), _rollback_nfl_prop_conn(), test_january_games_belong_to_the_prior_season(), still_pre_game(), unique_row_sql(), describe() (+17 more)

### Community 286 - "NFL prop market Kalshi pricing tests"
Cohesion: 0.10
Nodes (12): TestMarketRelative, find_bets(), _ladder(), test_a_replay_never_prices_off_todays_ladder_even_when_on(), test_fetch_helper_swallows_errors(), test_kalshi_is_not_graded_until_settled_history_exists(), test_kalshi_outside_the_ladder_is_refused_not_extrapolated(), test_kalshi_prices_a_line_pinnacle_cannot() (+4 more)

### Community 288 - "tests/test_nfl_opener.py"
Cohesion: 0.20
Nodes (5): TestBettableBooksOnly, TestSelectOpenerBets, _both_sides(), _frame(), _sched()

### Community 289 - "Player news ingestor and tests"
Cohesion: 0.03
Nodes (55): NewsItem, NewsPlayer, FakeConn, FakeResponse, _Result, _article_url(), _athletes_in(), build_name_index() (+47 more)

### Community 295 - "Discord and X results posting"
Cohesion: 0.02
Nodes (72): UnitStake, _apply_one(), _is_transient_lock_error(), _with_lock_timeout(), test_a_loss_costs_the_full_stake_and_a_push_costs_nothing(), test_a_pick_with_no_price_stays_in_the_units_at_bare_conviction(), test_a_six_column_row_still_tallies(), test_a_snapshot_with_no_clv_stores_null_not_zero() (+64 more)

### Community 296 - "NHL blocked shots prop model"
Cohesion: 0.09
Nodes (19): TestTonightsRowIsATrainingRow, build_frame(), _ew(), expected_value(), fit(), load_skaters(), load_teams(), name_key() (+11 more)

### Community 298 - "tests/test_nfl_wind_publisher.py"
Cohesion: 0.14
Nodes (9): TestBuildRows, TestKickFields, TestParseMatchup, build_rows(), kick_fields(), parse_matchup(), test_nfl_wind_and_opener_rows_drop_a_bet_under_the_floor(), test_the_min_chi_wind_row_is_written_as_a_bet() (+1 more)

### Community 3 - "Pre-game odds and prop odds ingestors"
Cohesion: 0.01
Nodes (162): Meter, Meter, Meter, Plan, TestEveryOtherSportStillMintsItsOwn, TestNflResolvesOntoTheSchedule, TestTheResolverFailsClosed, TestOddsFeedTeamNames (+154 more)

### Community 30 - "NFL live prop model tests"
Cohesion: 0.04
Nodes (37): Read, _FakeOdds, _IdRecordingOdds, blind_over_prob(), over_prob(), _pass_attempt_bias_allowed(), _core_worker(), test_a_deployed_bias_must_sit_inside_its_measured_interval() (+29 more)

### Community 300 - "tests/test_health_reason_and_cadence.py"
Cohesion: 0.09
Nodes (20): Report, _one(), test_a_24h_ts_check_reads_as_daily(), test_a_bare_add_still_fills_both_columns(), test_a_broken_query_is_its_own_reason(), test_a_late_check_says_how_late(), test_a_passing_check_says_fresh(), test_a_skipped_check_says_the_gate_was_shut() (+12 more)

### Community 301 - "NBA odds history gap fetch tests"
Cohesion: 0.10
Nodes (17): _Ledger, _Meter, _Resp, gap_instants(), line_snapshots(), _hourly(), _t(), test_a_fetch_is_ledgered_by_its_instant_off_the_hour_and_by_its_hour_on_it() (+9 more)

### Community 302 - "tests/test_nfl_weather_supabase_readback.py"
Cohesion: 0.14
Nodes (13): FakeConn, _patch_conn(), _rows(), test_a_null_requested_lead_is_not_returned(), test_a_one_lead_response_is_not_stored(), test_a_partial_window_is_not_returned(), test_a_store_failure_is_a_warning_not_an_error(), test_a_subset_of_leads_reads_only_those_columns() (+5 more)

### Community 307 - "Publish signals on write tests"
Cohesion: 0.06
Nodes (18): _Conn, _body(), _row(), _surfaces(), _make(), test_a_broken_webhook_does_not_suppress_the_push(), test_a_failed_capture_still_delivers(), test_a_publish_failure_does_not_kill_the_tick() (+10 more)

### Community 308 - "Pitcher stats as-of invariant tests"
Cohesion: 0.04
Nodes (42): _FakeConn, _upsert_injuries(), backfill_player_game_log(), ingest_game_log_for_date(), _safe_int(), _upsert_player_game_log(), _upsert(), last3_rates() (+34 more)

### Community 309 - "Scorer pick label and Kelly sizing"
Cohesion: 0.04
Nodes (19): TestAmericanToDecimalScorer, TestBuildInjuryFlag, TestBuildPickLabel, TestConfidenceTier, TestFeatureValue, TestMakePick, TestQuarterKelly, _backtest_ufc_fight() (+11 more)

### Community 31 - "NBA prop market tip timing"
Cohesion: 0.05
Nodes (36): NbaPropDecision, Roster, coherent(), fair_under(), fetch_times(), find_bets(), in_window(), load_quotes() (+28 more)

### Community 312 - "NHL prop per-game limit tests"
Cohesion: 0.16
Nodes (4): TestInsertOnce, TestTheLimitPerGame, limit_per_game(), publish()

### Community 314 - "Pipeline log reason tests"
Cohesion: 0.22
Nodes (6): _Conn, _capture(), test_a_false_step_records_the_last_error_it_logged(), test_a_false_step_that_logged_nothing_still_says_so(), test_a_raising_step_still_records_the_exception(), test_the_sink_is_removed_after_the_step()

### Community 32 - "NBA in-game study two"
Cohesion: 0.07
Nodes (35): StateModel, norm_cdf(), threshold(), apply_model(), benchmark_columns(), decision_quotes(), delta_ci(), _design() (+27 more)

### Community 320 - "NFL opener and wind writer lock tests"
Cohesion: 0.05
Nodes (16): _After, _LockConn, _Pg, _PgCursor, TestEvalRowsCarryTheLine, TestFlexedKickoffRefreshes, TestNoneRowNeverLocks, TestPreflightCiMode (+8 more)

### Community 321 - "NFL in-play prop settlement tests"
Cohesion: 0.12
Nodes (16): _SqliteShim, _box(), conn(), _game(), _live_bet(), raw(), _row(), test_a_final_with_no_box_score_yet_waits() (+8 more)

### Community 322 - "NBA prop settlement stat loading tests"
Cohesion: 0.11
Nodes (9): _SelectConn, test_a_missing_stat_is_none_not_zero(), test_a_turnovers_bet_on_a_player_who_played_settles_win_not_no_action(), test_combo_markets_are_mapped_to_helpers_and_only_the_nba_rule_uses_them(), test_double_double_matches_the_rule_it_replaced(), test_the_loader_carries_every_stat_a_market_settles_on(), test_the_loader_selects_turnovers(), _load_nba_prop_actuals() (+1 more)

### Community 323 - "NBA prop pricing window tests"
Cohesion: 0.06
Nodes (36): _PlanConn, _fires(), _game(), _jobs(), _plan(), _t(), test_a_projection_too_old_to_price_does_not_block_the_retry(), test_a_tick_fetches_exactly_the_window_games_then_decides_closes_and_publishes() (+28 more)

### Community 326 - "NFL wind publisher scored rows"
Cohesion: 0.10
Nodes (7): TestBuildScoredRows, TestPickEmLabel, TestPreflightLockChecks, TestQualifyingRowIsNotANoneRow, _american_to_prob(), build_scored_rows(), _num()

### Community 33 - "nfl/live_model/feeds: test_feed_resilience + espn"
Cohesion: 0.04
Nodes (52): _ScriptedTick, _competitors(), _deref(), fetch_live_events(), _https(), make_fetcher(), fetch(), parse_core_event() (+44 more)

### Community 330 - "NFL opener publisher tests"
Cohesion: 0.11
Nodes (9): TestBuildOpenerRows, TestFireWindow, TestModelCardSplit, build_opener_rows(), _opener_model(), _card_row(), _row(), _row() (+1 more)

### Community 331 - "NHL player prop projection model"
Cohesion: 0.07
Nodes (28): Spec, TestWhoThePlayerIs, _attach_teams(), build_goalie_frame(), build_skater_frame(), _ew(), excess_variance(), expected_value() (+20 more)

### Community 334 - "CLV settlement timeout retry tests"
Cohesion: 0.10
Nodes (14): _Conn, _fn(), _sql(), test_a_non_timeout_is_not_retried(), test_a_second_timeout_does_not_abort_the_next_statement(), test_a_timeout_is_rolled_back_and_retried_once(), test_one_date_timeout_does_not_drop_the_next_date(), test_query_canceled_with_sqlstate_is_a_timeout() (+6 more)

### Community 341 - "Health check skip budget tests"
Cohesion: 0.07
Nodes (18): FakeConn, _res(), _source_outside_the_budget_table(), test_a_check_never_seen_non_skipped_counts_its_whole_history(), test_a_check_skipped_only_today_is_not_counted_as_a_streak(), test_a_non_skipped_result_is_never_touched(), test_a_stuck_gate_escalates_past_its_budget(), test_an_honest_offseason_skip_stays_skipped_but_shows_its_length() (+10 more)

### Community 342 - "tests/test_live_pick_features.py"
Cohesion: 0.07
Nodes (19): FakeConn, _Conn, _record_live_features(), _pick(), test_a_live_bet_records_its_feature_row_and_lambda(), test_a_pick_with_no_feature_row_is_skipped_not_written_empty(), test_a_recorder_failure_is_rolled_back_to_its_savepoint(), test_a_recorder_failure_is_swallowed_rather_than_raised() (+11 more)

### Community 343 - "HTTP timeout floor and probes"
Cohesion: 0.05
Nodes (30): Plan, _flush_on_exit(), install(), install_timeout_floor(), _writer_loop(), ensure_table(), close_due(), fetch() (+22 more)

### Community 345 - "Public fade detection quality tests"
Cohesion: 0.06
Nodes (25): _Shim, _bet(), _fade_slate(), _insert_open_bet(), test_a_mixed_slate_is_ok(), test_all_home_ncaaf_slate_is_flagged_without_mlb_hardcoding(), test_all_unders_public_fade_risk_is_crit(), test_all_unders_public_fade_slate_is_crit() (+17 more)

### Community 348 - "Pregame price age and twin game tests"
Cohesion: 0.04
Nodes (26): _BoardConn, _OddsConn, _ShopConn, _TwoIdConn, _UfcBoardConn, _ago(), _clock(), _h2h_row() (+18 more)

### Community 349 - "tests/test_prop_missing_features.py"
Cohesion: 0.13
Nodes (6): TestARowMissingAFeatureIsNotScored, TestEveryPropLoopGoesThroughTheHelper, TestTheUmpireIsTheDeclaredException, prop_feature_matrix(), _frame(), helper()

### Community 350 - "MLB public fade top picks ranking"
Cohesion: 0.15
Nodes (16): PublicFadeBet, composite_score(), estimated_edge(), rank_score(), select_top_k(), _key(), ticket_money_gap(), ev_of() (+8 more)

### Community 352 - "NCAAF FBS registry health checks"
Cohesion: 0.05
Nodes (19): TestFbsGate, TestRefusalLog, TestRegistryHealthCheck, TestUnratedFbsClaim, fbs_refusal_claims(), _is_fbs(), unrated_fbs_claim(), _alarm_part() (+11 more)

### Community 355 - "NFL in-play decline recorder tests"
Cohesion: 0.12
Nodes (12): PicksRecorder, _AvoidConn, _mk_decline(), test_a_market_opinion_decline_is_written_as_avoid(), test_a_moved_line_is_rewritten(), test_an_unchanged_proposition_is_not_rewritten(), test_plumbing_refusals_stay_out_of_picks(), test_recording_a_decline_can_never_break_a_bet() (+4 more)

### Community 357 - "NFL wind and opener publisher"
Cohesion: 0.09
Nodes (15): TestPublishOpenerInsertOnce, _changed(), _clear_scored_row(), _flush_board_safe(), _flush_snapshots_safe(), _fmt_line(), _fmt_spread(), latest_eval_rows() (+7 more)

### Community 361 - "NCAAF live state recording tests"
Cohesion: 0.16
Nodes (13): _Conn, record_live_states(), state_change_row(), state_key(), _state(), test_a_failed_write_never_costs_the_pass(), test_a_score_a_period_or_a_possession_change_is_written(), test_first_sight_is_written() (+5 more)

### Community 363 - "tests/test_run_ledger_orphans.py"
Cohesion: 0.12
Nodes (18): _Conn, db(), _insert_open(), _ledger(), _open_rows(), _row(), test_a_genuine_current_hang_is_still_detectable(), test_a_second_sweep_does_not_abort_the_pass_this_process_started() (+10 more)

### Community 368 - "MLB in-play history backtest"
Cohesion: 0.21
Nodes (9): _Conn, _Cur, _lookup_home_won(), mlb_game_final(), sbr_twin_id(), test_no_final_anywhere_is_none(), test_scored_canonical_row_wins_and_keeps_its_label(), test_twin_id_swaps_only_the_renamed_franchises() (+1 more)

### Community 37 - "NBA lineup stints from play-by-play"
Cohesion: 0.05
Nodes (50): Diagnostics, _Seg, roster_from_plays(), score_plays(), _accumulate(), _add_one(), _and_one_follows(), appearances() (+42 more)

### Community 370 - "UFC results scraper tests"
Cohesion: 0.06
Nodes (22): _FakeConn, slugify_fighter(), _resolve(), test_alias_makes_both_sources_agree(), test_aliases_do_not_touch_unmapped_names(), test_confirmed_aliases_resolve_to_ufcstats_slug(), test_resolve_anchor_declines_when_opponent_changed(), test_resolve_anchor_matches_every_real_name_variant() (+14 more)

### Community 376 - "In-play calibrated decision tests"
Cohesion: 0.09
Nodes (15): RecordingConn, _cut(), _signal(), test_a_big_enough_claim_still_fires_after_calibration(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(), test_a_hot_live_model_no_longer_fires_the_marginal_bet(), test_a_live_model_is_read_out_of_picks_not_the_matview(), test_a_live_read_bounds_on_a_real_price() (+7 more)

### Community 378 - "Team total market skip rules tests"
Cohesion: 0.08
Nodes (14): _PickConn, _Rows, _SqliteShim, raw(), _result(), test_a_line_that_dropped_under_an_under_is_a_skip(), test_an_away_team_total_settles_on_the_away_team_s_points(), test_an_overtime_final_counts_and_a_full_game_total_would_not() (+6 more)

### Community 38 - "Pre-game scorer and pick insertion"
Cohesion: 0.02
Nodes (99): TestAmericanToImpliedProb, TestMissingStarterGate, relevant_players(), _make_live_pick(), american_to_implied_prob(), _anchored_probability(), _apply_game_injury_gate(), _run() (+91 more)

### Community 380 - "Sharp book odds retention"
Cohesion: 0.07
Nodes (14): _RecordingConn, _prop_reference_books(), protected_for(), _thin_book_filter(), test_the_bookmaker_these_rows_use_survives_the_daily_prune(), test_a_shopping_book_is_still_prunable(), test_every_prop_reference_book_is_protected(), test_every_sharp_book_is_protected_in_the_prop_table() (+6 more)

### Community 383 - "NCAAF opponent-adjusted search features"
Cohesion: 0.12
Nodes (15): AdjRatings, build_adjusted_ratings(), build_prior_season_ratings(), fit_opponent_adjustment(), load_fbs_membership(), load_team_games(), pool_fcs_opponents(), rolling_variants() (+7 more)

### Community 385 - "MLB first five any-book line tests"
Cohesion: 0.08
Nodes (31): _Clf, _GameOddsConn, _fallback_game_line_quote(), _get_scoring_odds(), _has_real_game_price(), _cut(), _mlb_feat(), _on() (+23 more)

### Community 387 - "tests/test_repair_bogus_first_pitch_labels.py"
Cohesion: 0.13
Nodes (8): _Conn, _run(), test_a_dry_run_writes_nothing_at_all(), test_a_short_backup_rolls_back_and_relabels_nothing(), test_the_backup_is_written_before_the_update(), test_the_backup_table_is_revoked_from_the_public_roles(), test_the_bogus_set_is_computed_never_listed(), test_the_query_is_scoped_to_the_scheduled_start_not_the_derived_one()

### Community 39 - "nfl/live_model/tests/test_executor.py"
Cohesion: 0.06
Nodes (47): Decision, Executor, GameState, derivative_lag(), ev_floor(), _mk(), expected_value(), honest_probability() (+39 more)

### Community 393 - "tests/test_sbr_loader.py"
Cohesion: 0.14
Nodes (3): _SqliteConnShim, _SqliteCursorShim, loader_conn()

### Community 394 - "Walk-forward evaluation"
Cohesion: 0.10
Nodes (13): _Cols, _Frame, _frame(), main(), walk_forward(), _fake(), test_a_fold_with_too_little_history_is_skipped(), test_a_single_class_test_season_is_skipped() (+5 more)

### Community 397 - "mobile/scripts/ux_scan.mts"
Cohesion: 0.16
Nodes (18): Finding, Severity, changedFiles(), entitlementGate(), fontScaling(), fontSizeLiterals(), hexColors(), main() (+10 more)

### Community 398 - "Mobile range slider logic"
Cohesion: 0.18
Nodes (21): Props, GestureIntent, Scale, at(), RangeSlider(), applyBound(), grabTarget(), readIntent() (+13 more)

### Community 4 - "Pick settlement and closing line capture"
Cohesion: 0.05
Nodes (46): _FakeStatsapi, _SqliteShim, test_it_settles_as_a_total(), test_it_settles_as_totals_off_the_final_score(), conn(), _game(), _pick(), raw() (+38 more)

### Community 40 - "Mobile player stats and game log"
Cohesion: 0.02
Nodes (264): Props, PlayerNextGame, Section, Args, PlayerStatKey, reachFrame, HitMode, HitSelection (+256 more)

### Community 401 - "Free pick and line alert tests"
Cohesion: 0.05
Nodes (20): _Conn, _Res, _Conn, _pick(), test_every_offerable_book_has_a_human_name_on_both_surfaces(), test_the_free_card_names_the_cheaper_book(), test_the_free_card_query_reads_the_columns_it_renders(), test_the_good_to_clause_is_dropped_not_truncated_when_it_will_not_fit() (+12 more)

### Community 409 - "NCAAF in-play underdog calibration and tick tests"
Cohesion: 0.10
Nodes (9): TestTickLatency, bucket(), label(), main(), table(), wilson(), test_the_tick_passes_a_days_that_covers_the_whole_window(), test_the_tick_returns_free_outside_the_window() (+1 more)

### Community 41 - "tests/test_live_quote_staleness.py"
Cohesion: 0.05
Nodes (42): ScoreClock, _Conn, _Q, quote_from_nfl_quotes(), _abbrev(), rows_for_quotes(), parse_event_odds(), market_is_takeable() (+34 more)

### Community 410 - "NBA prop closing line purchase tests"
Cohesion: 0.09
Nodes (11): _Conn, _Resp, test_a_close_already_held_is_not_bought_again(), test_a_due_close_buys_one_call_of_the_bet_markets_and_reports_its_credits(), test_a_pass_outside_the_window_spends_nothing(), test_only_a_game_holding_a_bet_and_only_once(), test_only_twelve_to_twenty_five_minutes_before_tip(), test_the_ten_minute_evening_passes_always_land_one_inside() (+3 more)

### Community 417 - "In-play publish parity with pauses"
Cohesion: 0.17
Nodes (12): _Conn, _db(), _labels(), _pick(), test_a_bet_written_while_paused_is_not_announced_after_an_unpause(), test_a_live_health_state_still_publishes(), test_a_paused_model_is_not_announced(), test_a_retired_model_is_not_announced() (+4 more)

### Community 421 - "NBA injury report fetching"
Cohesion: 0.09
Nodes (23): _Conn, _Cur, _Fetcher, _PdfFetcher, content_hash(), garbled_note(), pull_one(), slot_time() (+15 more)

### Community 424 - "supabase/functions/_shared/discord.ts"
Cohesion: 0.20
Nodes (15): DiscordApiError, DiscordUser, RoleSyncResult, addAppRole(), addGuildMember(), botFetch(), expectOk(), isGuildMember() (+7 more)

### Community 43 - "Worker job queue validation tests"
Cohesion: 0.03
Nodes (54): _DedupeConn, _VoidConn, _posted_row(), _quiet(), _run_void(), _run_void_job(), test_a_declared_job_is_queued_once_however_often_it_is_read(), test_a_failed_job_needs_a_new_key_to_rerun() (+46 more)

### Community 433 - "NFL prop odds timeout-safe slicing"
Cohesion: 0.06
Nodes (23): _Conn, _Cur, TestPropOddsLoader, _Conn, _Cur, _fetch_slice(), _iter_prop_rows(), load_nfl_prop_odds() (+15 more)

### Community 435 - "NBA totals luck replay"
Cohesion: 0.13
Nodes (9): FrameConn, load_artifact(), grade_window(), lab_bets(), lab_gaps(), load(), main(), replay() (+1 more)

### Community 436 - "NCAAF game-day pick lock tests"
Cohesion: 0.13
Nodes (12): FakeConn, _Rows, write_picks(), db(), test_both_lanes_locked_touches_nothing(), test_dry_run_never_touches_db(), test_first_bet_is_written_and_will_lock(), test_flag_off_restores_delete_and_replace() (+4 more)

### Community 44 - "scripts: build_nfl_live_leader_artifact + model"
Cohesion: 0.06
Nodes (36): Artifact, Decision, am_to_dec(), artifact_from_dict(), band_for(), decide(), leader_expected_margin(), load_artifact() (+28 more)

### Community 440 - "NFL DraftKings line snapshots"
Cohesion: 0.32
Nodes (4): TestDkLineRows, dk_line_rows(), _num(), _rec()

### Community 442 - "Discord post ledger and announcements"
Cohesion: 0.09
Nodes (8): TestItNeverDecides, _Posted, _Rejected, _announce(), _announce_and_ledger(), _post(), _announce(), post_and_ledger()

### Community 446 - "Schema guard and table lockdown"
Cohesion: 0.04
Nodes (31): GuardConn, _ddl(), _dk_direct_feed(), _is_guarded(), _job_queue(), _kickoff_wind(), _live_calibration(), _modules_with_write_time_ddl() (+23 more)

### Community 448 - "tests/test_discord_channel_probe.py"
Cohesion: 0.17
Nodes (7): _Resp, test_the_probe_covers_the_per_sport_live_channels(), test_the_probe_never_posts_and_never_returns_the_url(), test_the_probe_reports_the_channel_behind_each_sport(), _get(), test_two_sports_sharing_a_channel_are_flagged(), _job_discord_probe()

### Community 45 - "tests/test_nfl_prop_one_read_per_game.py"
Cohesion: 0.06
Nodes (25): _Conn, _Log, publish_hour_missed(), publishable_games(), _at(), _games(), test_a_game_is_publishable_on_exactly_one_pass_in_its_window(), test_a_game_with_no_kickoff_is_never_published() (+17 more)

### Community 450 - "Bounded odds pruning keeps openers and close"
Cohesion: 0.06
Nodes (33): _Ctx, Timeout, p(), _after_nth_delete(), build(), _fails_on(), _lit(), old_prune() (+25 more)

### Community 464 - "NCAAF gameday live odds cadence"
Cohesion: 0.04
Nodes (29): _Ctx, _ev(), _feed_with_payload(), gameday_mod(), _main_source(), _modelled_monthly_cfbd_calls(), test_a_single_failed_summary_does_not_drop_the_other_games(), test_a_sustained_feed_outage_degrades_to_no_odds() (+21 more)

### Community 466 - "MLB prop pregame quote cutoff tests"
Cohesion: 0.12
Nodes (7): _Conn, test_a_game_with_no_cutoff_fails_open(), test_both_market_relative_loaders_bound_on_the_cutoff(), test_it_compares_parsed_timestamps_not_strings(), test_it_joins_games_and_uses_the_shared_cutoff(), test_the_newest_qualifying_quote_still_wins(), test_the_post_first_pitch_quote_is_dropped_even_though_it_is_newest()

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

### Community 474 - "NBA historical odds archive parser"
Cohesion: 0.06
Nodes (40): _Conn, classify(), _fold(), _gid(), _is_half(), iso_z(), load(), match() (+32 more)

### Community 48 - "tests/test_calibration_watch.py"
Cohesion: 0.06
Nodes (14): _Conn, _Res, TestDormantLiveModels, TestRosterChanges, TestTheRun, TestVerdictChanges, TestVolumeShifts, _row() (+6 more)

### Community 485 - "NFL weather history fetcher"
Cohesion: 0.18
Nodes (10): DailyLimit, Pacer, consolidate(), era5_check(), game_hours(), log(), main(), om_get() (+2 more)

### Community 488 - "Ungraded model performance monitor tests"
Cohesion: 0.07
Nodes (14): FakeConn, http_server(), live_server(), test_perf_reads_the_matview_not_the_expensive_view(), test_roster_reports_a_registered_but_untrained_model(), _second_arm(), _sql(), test_a_fully_unpriced_recovered_model_reports_no_roi() (+6 more)

### Community 49 - "Pipeline failure alerting and heartbeats"
Cohesion: 0.06
Nodes (18): FakeConn, TestDeliveryAndNoise, TestHealthCheckOnlyIsNotADirtyPass, TestItCannotBreakTheWorker, TestSilentJobs, TestWhatCountsAsAFailure, _clean_runs(), _posts() (+10 more)

### Community 490 - "NCAAF starter-out research dataset"
Cohesion: 0.10
Nodes (16): LabelSet, build_label_set(), _fetch_lines(), _fetch_raw(), opener_coverage(), _pick_provider(), provider_continuity(), main() (+8 more)

### Community 497 - "Discord publish keys and void notices"
Cohesion: 0.04
Nodes (40): Ledger, _sql_key(), test_a_game_level_key_has_no_tail(), test_an_opening_signal_is_live_only_when_discord_published_it(), test_discord_led_visibility(), test_opening_lock_join_is_not_wired_into_readers_yet(), test_the_discord_pins_are_on_the_pr_ci_subset(), test_the_join_is_the_discord_ledger_and_not_a_new_bet_row() (+32 more)

### Community 499 - "NHL totals card publisher"
Cohesion: 0.08
Nodes (19): _LockConn, _SlateConn, main(), pick_rows(), publish(), render(), run_card(), slate() (+11 more)

### Community 503 - "MLB in-play state alignment"
Cohesion: 0.22
Nodes (6): GameClock, _t(), test_before_first_pitch_and_after_last_play_are_not_priced(), test_between_pas_across_third_out_rolls_over_to_next_half(), test_mid_plate_appearance_is_that_pa_before_state(), test_plays_without_times_are_ignored()

### Community 504 - "Member sportsbooks scratch database tests"
Cohesion: 0.09
Nodes (17): ScratchPostgres, pg_bin(), _code(), test_results_keep_pushes_and_ties_and_carry_no_stake(), test_schema_applies_twice_on_scratch_postgres_and_anon_can_only_read(), test_the_migration_is_one_statement_and_registered(), test_the_second_pass_returns_before_it_locks(), test_the_skip_guard_refuses_every_write_verb() (+9 more)

### Community 51 - "Mobile team detail stats screen"
Cohesion: 0.07
Nodes (63): NextGame, Section, TeamLineQuote, FormGame, FormSummary, headToHead, lineMove, PickRecord (+55 more)

### Community 510 - "Database write retry on dropped connection"
Cohesion: 0.13
Nodes (13): ConnectionLost, _write_with_retry(), test_a_connection_lost_mid_write_re_runs_the_whole_slot(), executemany(), __init__(), test_a_statement_timeout_rolls_back_and_re_runs_the_slot(), executemany(), __init__() (+5 more)

### Community 511 - "Prop odds next-day lookahead tests"
Cohesion: 0.17
Nodes (4): TestTheOddsFetchReachesTomorrow, TestTheScorerReachesTomorrow, _get_events(), _events_src()

### Community 517 - "NCAAF in-play history backtest tests"
Cohesion: 0.11
Nodes (16): _StubEngine, first_signals(), grade(), _cand(), _event(), _no_db_school_lookup(), test_a_late_kickoff_falls_back_to_its_utc_dated_games_row(), test_a_market_filter_writes_only_that_market() (+8 more)

### Community 52 - "tests/test_best_line_live.py"
Cohesion: 0.04
Nodes (47): _FakeConn, _best_live_price(), _best_live_side(), _live_book_quotes(), _live_decision_quote(), _live_quote_is_on_offer(), _tag_live(), best_takeable_quote() (+39 more)

### Community 522 - "In-play score freshness guard tests"
Cohesion: 0.16
Nodes (9): _FakeConn, _odds(), test_a_quote_published_before_the_score_is_declined(), test_a_quote_republished_after_the_score_is_kept(), test_the_age_bound_alone_would_have_allowed_it(), test_the_age_bound_still_fires_independently(), test_the_score_lookup_is_scoped_and_ordered(), execute() (+1 more)

### Community 524 - "Team stats snapshot thinness tests"
Cohesion: 0.13
Nodes (6): _SeasonConn, test_verify_established_live_season_with_two_snapshots_stays_thin(), test_verify_five_day_span_with_one_snapshot_is_thin(), test_verify_four_day_opening_span_is_still_grace(), test_verify_opening_live_season_is_not_thin(), test_verify_short_historical_season_is_still_thin()

### Community 526 - "NCAAF college data refresh and backfill tests"
Cohesion: 0.16
Nodes (8): _NullConn, backfill_ncaaf(), refresh_ncaaf_games(), test_backfill_returns_totals_when_every_season_succeeds(), test_backfill_survives_a_mid_run_season_failure(), test_refresh_games_happy_path_counts_games(), test_refresh_games_repairs_every_season_and_reports_failures(), test_refresh_stats_isolates_a_failing_season()

### Community 528 - "UFC fight stats scoring tests"
Cohesion: 0.11
Nodes (7): _IngestConn, _ingest(), _one_fight_event(), test_a_late_replacement_is_not_scored_on_the_original_booking(), test_a_misspelled_fighter_is_scored_for_the_side_they_fought_on(), test_a_row_naming_neither_fighter_is_left_unscored(), test_the_same_fight_stored_twice_is_scored_on_both_rows_each_way_round()

### Community 53 - "Mobile load errors and abort handling"
Cohesion: 0.03
Nodes (107): Props, LivePicksState, Args, PlayerNewsState, CountInput, DetailBody, LoadBody, LoadInput (+99 more)

### Community 531 - "NFL in-play leader model decision"
Cohesion: 0.05
Nodes (24): Gate, expected_value(), min_ev_for(), scoring_method(), honest_probability(), test_ncaaf_live_ev_floor_is_wired_from_config(), test_the_models_the_global_floor_silently_removed_can_bet_again(), test_expected_value_is_on_the_quoted_price() (+16 more)

### Community 533 - "NBA team total odds fetch tests"
Cohesion: 0.04
Nodes (51): Clock, FakeFeed, FakeResp, _billed(), closes_taken(), event_rows(), fetch_team_totals(), fetches() (+43 more)

### Community 54 - "tests/test_void_picks.py"
Cohesion: 0.04
Nodes (22): _FakeConn, TestAPostedSignalIsLocked, TestAPostedVoidAnnouncesAfterCommit, TestTheToolRefusesToMatchEverything, TestVoidingAPostedPickIsAnExplicitOptIn, TestWhatMayBeVoided, TestWhatTheVoidWrites, DiscordVoidRejected (+14 more)

### Community 542 - "Mobile push notification deep links"
Cohesion: 0.20
Nodes (14): NavRef, PushRoute, PicksView, clearNativeLastResponse(), navigateTo(), responseIdentifier(), usePushDeepLink(), setSportForVisit() (+6 more)

### Community 545 - "Job heartbeat and stale jobs"
Cohesion: 0.16
Nodes (7): Conn, _build(), test_a_job_marked_disabled_is_not_silent(), test_a_job_that_runs_here_is_not_marked(), test_a_service_leaves_alone_the_jobs_another_service_owns(), test_startup_marks_an_owned_job_that_is_switched_off(), stale_jobs()

### Community 549 - "Database setup and SQL statement splitting"
Cohesion: 0.19
Nodes (4): TestRealSchema, TestSplitter, TestSqliteSchema, _split_sql_statements()

### Community 55 - "NCAAF game-day live feeds"
Cohesion: 0.04
Nodes (43): LiveOddsFeed, build_row(), _mark_written(), now_iso(), _publish_key(), record_live_prices(), rows_from_quote(), school() (+35 more)

### Community 550 - "NFL prop backtests and walk-forward"
Cohesion: 0.02
Nodes (81): LazyConnection, TestBinaryMarket, TestCountDistributions, TestKickoffGate, TestLocalOddsCache, TestPlaceboCannotSilentlyNotHappen, TestPriceMath, TestResolveGameId (+73 more)

### Community 551 - "MLB renamed franchise game merge tests"
Cohesion: 0.13
Nodes (12): _Conn, apply_one(), canonical(), counts(), main(), plan(), test_a_canonical_id_maps_to_nothing(), test_a_non_mlb_or_malformed_id_is_left_alone() (+4 more)

### Community 553 - "NFL in-play pick row building tests"
Cohesion: 0.13
Nodes (10): _Decision, build_pick(), test_a_locked_lane_writes_nothing_further(), test_a_pass_is_never_announced(), test_edge_is_the_platform_edge_not_the_lanes_ev(), test_every_row_key_is_actually_bound_by_the_insert(), test_the_label_agrees_with_the_side_and_the_line_it_carries(), test_the_label_names_the_stat_the_model_actually_trades() (+2 more)

### Community 554 - "NBA box score repair tests"
Cohesion: 0.13
Nodes (8): _Conn, boxes_to_repair(), _logs(), _run(), test_a_box_that_does_not_add_up_is_never_written(), test_a_game_nba_com_does_not_list_is_refused(), test_only_the_named_game_is_replaced_delete_first(), test_the_season_repair_names_every_missing_or_wrong_box()

### Community 56 - "tests/test_daily_retry.py"
Cohesion: 0.06
Nodes (43): _Conn, _Cursor, _FrozenDatetime, DailyRun, Decision, _aborted(), _aborted_row(), _ok() (+35 more)

### Community 562 - "Results recap message id tests"
Cohesion: 0.03
Nodes (32): _Conn, _Ledger, _Resp, build_parser(), _date_is_over(), main(), post_backfill(), test_a_day_that_is_not_over_is_refused() (+24 more)

### Community 566 - "NBA line history pruning protection"
Cohesion: 0.07
Nodes (20): _Conn, thin_repeats(), _expire_after_deletes(), nba_paths(), old_thin(), _rows_of(), test_a_thinning_error_that_is_not_a_timeout_is_raised(), test_a_thinning_listing_timeout_costs_its_own_game() (+12 more)

### Community 567 - "NBA results Postgres store"
Cohesion: 0.13
Nodes (5): PgStore, _games(), _postponed(), _schedule(), end()

### Community 57 - "tests/test_live_book_move_guard.py"
Cohesion: 0.07
Nodes (40): BookMoveClock, _Unset, _MlbConn, american_to_implied(), _book_move(), _at(), _delaware_ctx(), _dk() (+32 more)

### Community 570 - "NHL prop settlement tests"
Cohesion: 0.06
Nodes (15): _Shim, TestEveryLiveModelIsWiredEverywhere, TestSettlement, TestTheDistribution, TestTheGoalieFrame, TestTonightsRowIsATrainingRow, _bet(), db() (+7 more)

### Community 58 - "Social post queue and drain"
Cohesion: 0.08
Nodes (40): QueueRejected, test_enqueue_inserts_a_thread_and_refuses_a_second_copy(), test_enqueue_refuses_a_url_unless_allow_link_is_set(), test_enqueue_stores_images_and_a_reply_target(), test_the_cli_can_enqueue_one_image_without_posting(), _actionable(), _as_utc(), _attach_media() (+32 more)

### Community 581 - "X post image fetching"
Cohesion: 0.17
Nodes (4): ImageFetch, test_fetch_https_image_sniffs_bytes_and_refuses_gif(), fetch_https_image(), _sniff_tweet_image()

### Community 583 - "NFL pick monitor"
Cohesion: 0.19
Nodes (6): TestClassify, TestImmutabilityContract, TestLatestPerPick, classify(), latest_per_pick(), _row()

### Community 588 - "NFL in-play pick writer commit tests"
Cohesion: 0.12
Nodes (7): _Conn, test_a_pass_is_never_written_to_picks(), test_an_unresolvable_decision_writes_nothing(), test_game_id_resolves_from_the_book_s_team_names(), test_picks_recorder_drops_a_pass_attempt_over_before_sql(), test_the_announce_runs_after_the_commit_and_after_the_connection_closes(), commit()

### Community 59 - "NFL gameday odds and weather feeds"
Cohesion: 0.02
Nodes (95): OddsAPIClient, SnapshotResult, OpenMeteoError, JsonlRecorder, game_index(), record_nfl_anchor_prices(), card_path(), clear_card() (+87 more)

### Community 590 - "Prop odds missing game skip tests"
Cohesion: 0.15
Nodes (4): FakeConn, _run(), test_event_with_no_games_row_is_skipped_and_others_still_insert(), test_fk_on_insert_does_not_unwrite_the_events_that_already_landed()

### Community 592 - "Odds research scripts and probes"
Cohesion: 0.02
Nodes (79): Puller, _Conn, validate_sides(), _ledger_row(), game_index(), main(), resolve(), rows_from_file() (+71 more)

### Community 597 - "Recap waits for NFL box scores"
Cohesion: 0.07
Nodes (9): _CursorResult, _go(), test_a_malformed_date_is_refused_before_anything_runs(), test_the_cursor_wrapper_rowcount_is_the_cursors(), test_the_job_does_not_bypass_the_day_is_over_guard(), test_the_job_does_not_read_rowcount_off_the_cursor(), test_the_job_only_clears_its_own_ledger_kind(), test_a_dropped_connection_replays_the_migration_with_its_lock_timeout() (+1 more)

### Community 598 - "NFL pick monitor join keys"
Cohesion: 0.16
Nodes (3): TestTheJoinKeyMatchesPicks, eval_row(), _picks_game_id()

### Community 599 - "System health check test fixtures"
Cohesion: 0.14
Nodes (4): _FrozenDatetime, _Shim, db(), mlb_wired()

### Community 6 - "Mobile custom model filters and metadata"
Cohesion: 0.02
Nodes (252): Case, Props, RowDef, Props, PropContext, BacktestPickRow, CustomModelStats, ChipGroup (+244 more)

### Community 604 - "Mobile bankroll local storage"
Cohesion: 0.23
Nodes (12): KeyValueStore, check(), eq(), fakeStore(), interleaving(), slowStore(), storage(), createBankrollStore() (+4 more)

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

### Community 621 - "CLV backfill job tests"
Cohesion: 0.13
Nodes (6): _Conn, _stub_backfill(), test_hard_cap_stops_a_nonempty_queue(), test_loops_until_a_pass_fills_nothing(), test_the_runner_opens_get_connection_and_calls_backfill_clv(), _job_clv_backfill()

### Community 623 - "NBA injury report PDF parsing"
Cohesion: 0.18
Nodes (9): Report, finish_rows(), parse_pdf(), parse_title(), rows_from_pages(), season_of(), test_finish_rows_builds_our_game_id_and_season(), test_report_time_comes_from_the_header_and_is_stored_in_utc() (+1 more)

### Community 630 - "NHL blocked shots prop settlement tests"
Cohesion: 0.27
Nodes (5): _Shim, TestSettlement, _bet(), _played(), _result()

### Community 633 - "Database grant revocation and UFC sweep"
Cohesion: 0.05
Nodes (18): _PoisonConn, _fmt_et_time(), get_conn(), query(), main(), _strip_outer_tx(), _event_index(), _games() (+10 more)

### Community 64 - "NFL in-play score distribution pricing"
Cohesion: 0.04
Nodes (42): ScoreDistribution, _model_price(), gaussian_copula_joint(), mu_bucket(), _mu_centres(), _spearman_to_gaussian(), time_bucket(), american_to_prob() (+34 more)

### Community 643 - "Injury adjustment game features"
Cohesion: 0.05
Nodes (13): TestComputeInjuryAdjustment, TestFeatureMap, TestHasReturnee, TestHasStarterOut, TestMarketForOdds, _blk_nhl_rolling_goals(), _build_nhl_features_from_bulk(), build_nhl_game_features() (+5 more)

### Community 644 - "External feature map promotion tests"
Cohesion: 0.18
Nodes (4): _Conn, test_external_promotion_refuses_a_map_that_does_not_transfer(), test_external_promotion_writes_only_the_promoted_columns(), test_the_scorer_reads_the_external_map_like_any_promoted_one()

### Community 651 - "NFL wind bettable book filter"
Cohesion: 0.11
Nodes (5): TestTheCardFilters, TestTheListIsShared, _attach(), books(), _quote()

### Community 659 - "WNBA injury team id fallback"
Cohesion: 0.26
Nodes (4): TestCoreTeamsFallback, _fetch_wnba_espn_team_ids_core(), _fake_fetch(), _listing()

### Community 666 - "NFL live pick announce isolation tests"
Cohesion: 0.17
Nodes (6): _OpenConn, test_a_failing_announcer_cannot_undo_or_fail_the_write(), test_a_failing_recorder_cannot_take_the_other_down(), boom(), test_a_written_bet_is_announced_with_its_own_game_date(), test_an_unlocked_lane_does_write()

### Community 67 - "tests/test_game_market_gate.py"
Cohesion: 0.08
Nodes (43): GateVerdict, MarketBookend, PublicSplits, apply_to_picks(), _as_float(), bookend_from_odds(), evaluate(), fair_prob() (+35 more)

### Community 671 - "NHL prop EV regimes and Kalshi ladders"
Cohesion: 0.10
Nodes (9): TestRegimeOrder, regime(), test_the_recorder_walks_every_mapped_series(), _cand(), _league(), _loose_summary(), s(), _name() (+1 more)

### Community 674 - "NBA public splits quality backfill"
Cohesion: 0.18
Nodes (5): _CountingConn, backfill_quality(), test_an_existing_table_gets_the_quality_column(), test_the_backfill_adds_the_column_and_commits_once(), test_the_backfill_rolls_back_when_a_count_is_not_what_was_measured()

### Community 675 - "Pipeline watch report posting tests"
Cohesion: 0.12
Nodes (14): _Conn, test_a_clean_run_still_posts(), test_a_confirmed_post_is_ledgered_so_the_run_can_be_verified(), test_a_failed_ledger_does_not_lose_the_report(), execute(), test_a_failed_query_rolls_back_and_does_not_sink_the_run(), test_a_missing_webhook_is_not_ledgered_either(), test_a_run_with_findings_posts_them() (+6 more)

### Community 678 - "NFL prop market card tests"
Cohesion: 0.22
Nodes (3): TestMarketCard, execute(), fetchall()

### Community 68 - "NBA second-model prop study"
Cohesion: 0.06
Nodes (40): Shape, appearances(), box_tables(), build(), check_close_prior(), consensus_number(), empty_times(), fit_shape() (+32 more)

### Community 683 - "Probability calibration map tests"
Cohesion: 0.04
Nodes (28): _FakeConn, _SchemaRecordingConn, test_a_map_that_does_not_help_out_of_sample_is_not_applied(), test_a_map_that_helps_is_applied(), test_a_model_with_no_record_takes_the_pooled_correction(), test_a_model_with_too_few_graded_picks_gets_the_shrunk_offset_not_a_platt_map(), test_an_unmapped_model_is_unchanged_by_phase_2(), test_applied_is_a_column_not_a_json_substring_match() (+20 more)

### Community 69 - "tests/test_pick_integrity.py"
Cohesion: 0.03
Nodes (50): _Conn, _Shim, _add_pick(), discord_sent(), _health(), health_db(), test_a_label_may_not_name_a_market_the_pick_does_not_settle_on(), test_a_label_naming_the_other_team_is_refused() (+42 more)

### Community 693 - "NHL props newest fetch shopping"
Cohesion: 0.21
Nodes (4): _Conn, TestOnlyTheNewestFetchIsShopped, latest_quotes(), fetchall()

### Community 696 - "NBA public splits archive tests"
Cohesion: 0.12
Nodes (6): _NoDB, _Store, _scoreboard(), test_a_late_game_still_in_play_after_midnight_is_archived_at_the_next_pass(), test_a_stored_game_is_not_written_again_and_a_splitless_game_is_retried(), _wire_archive()

### Community 699 - "NFL live leader moneyline odds feed"
Cohesion: 0.24
Nodes (4): LiveOddsFeed, Quote, _api_key(), parse_h2h()

### Community 7 - "Database connection and game feature builders"
Cohesion: 0.02
Nodes (116): DBConnection, today_et(), connection_lost(), _games_needing_synthesis(), _log_pipeline(), query_injuries_for_game(), _load_last_state(), record_credits() (+108 more)

### Community 70 - "tests/test_record_one_pick_per_event.py"
Cohesion: 0.04
Nodes (43): _CaptureConn, _RecordingConn, _code(), _copy_for_node(), _fn(), _node(), _read(), test_a_custom_model_counts_the_kept_copy_once() (+35 more)

### Community 701 - "NHL opening night early season"
Cohesion: 0.22
Nodes (4): TestOpeningNightIsEarlySeason, _blk_nhl_asof(), _t(), test_the_training_path_reads_nhl_odds_by_game_not_by_sport()

### Community 708 - "Weekly job catch-up tests"
Cohesion: 0.18
Nodes (3): _Conn, test_a_failing_savant_refresh_does_not_cost_the_calibration_its_catch_up(), test_ownership_is_checked_per_job()

### Community 718 - "Picks email rendering"
Cohesion: 0.46
Nodes (6): Pick, _fmt_edge(), _fmt_odds(), main(), _pick_card(), render_email()

### Community 73 - "nfl/live_model/tests: test_props + props"
Cohesion: 0.09
Nodes (33): PropProjection, PlayerState, _accrued(), _count(), detect_inactive(), price_over(), project(), _rate() (+25 more)

### Community 732 - "Mobile bankroll unit size hook"
Cohesion: 0.32
Nodes (7): BankrollSettings, useBankroll(), canStepUnitPct(), sanitizeUnitPct(), stepUnitPct(), store, BANKROLL_DEFAULTS

### Community 758 - "Deploy checks and job queue"
Cohesion: 0.07
Nodes (17): _Conn, test_a_declared_job_carries_its_run_after(), test_a_failing_check_raises_so_the_queue_announces_it(), test_a_job_can_only_name_a_registered_check(), test_enqueue_rejects_a_naive_run_after(), test_enqueue_stores_run_after(), test_every_check_is_read_only(), test_the_claim_waits_for_run_after() (+9 more)

### Community 76 - "ncaaf_live/tests/test_serve.py"
Cohesion: 0.05
Nodes (45): GameContext, _abbrev_fits(), _clock_seconds(), extract_live_states_cfbd(), _parse_situation(), _parse_yardline(), _cfbd_game(), test_cfbd_state_carries_the_yardline_and_the_raw_situation() (+37 more)

### Community 77 - "tests/test_wnba_prop_market.py"
Cohesion: 0.05
Nodes (29): _FakeConn, _QuoteConn, apply_price_floor(), norm_name(), pick_rows(), player_ids(), publish(), render() (+21 more)

### Community 78 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.12
Nodes (13): _Conn, _RaceConn, TestLockSurvivesNothing, TestNoneRowBesideABetIsCleared, TestPublishRace, TestPublishScored, _bet_row(), fetchall() (+5 more)

### Community 79 - "NHL derivative totals walk-forward model"
Cohesion: 0.07
Nodes (38): Market, build_p1_frame(), build_team_frame(), day_interval(), _ew(), fit(), game_means(), _implied_vec() (+30 more)

### Community 790 - "Prop no-bet rows survive tipoff"
Cohesion: 0.07
Nodes (9): _Board, _Clock, _PollConn, _fake_datetime_class(), _game(), _iso(), test_the_poller_keeps_prop_no_bet_rows_the_refresh_pass_still_clears(), test_the_poller_tells_the_scorer_to_leave_prop_rows_alone() (+1 more)

### Community 8 - "Mobile pick queries and stats odds"
Cohesion: 0.02
Nodes (120): FighterSide, Props, CustomBacktestPickRow, CustomBacktestSummary, DiscordPublish, LockPick, NcaafTeamRow, PropLineLike (+112 more)

### Community 80 - "Per-model EV floor card tests"
Cohesion: 0.08
Nodes (24): NhlTotalBet, _built(), floor_030(), identity_maps(), _nfl_fixtures(), open_pregame_cut(), _pregame(), shrink_map() (+16 more)

### Community 83 - "NHL prop card pick writing tests"
Cohesion: 0.17
Nodes (6): TestTheBacktestGradesTheRuleTheCardPlays, TestTheCard, implied(), pick_rows(), _mus(), _quotes()

### Community 84 - "NBA prop card runner tests"
Cohesion: 0.05
Nodes (47): _Conn, ev_percentile(), choose(), _detail(), games_with_a_prop_bet(), main(), one_per_game(), per_night() (+39 more)

### Community 848 - "Prop odds book update time"
Cohesion: 0.26
Nodes (6): _Conn, _parse(), test_a_row_built_without_the_key_still_inserts_as_null(), test_no_clock_anywhere_is_none_not_our_fetch_time(), test_the_column_is_added_only_when_the_catalog_lacks_it(), test_the_markets_own_clock_is_stored_else_the_books()

### Community 85 - "tests/test_recap_retries_a_skipped_day.py"
Cohesion: 0.06
Nodes (25): _LiteConn, World, _add_pick(), _grade(), _lite(), _schema(), test_a_day_with_nothing_counting_posts_nothing_and_logs_nothing(), test_a_failed_receipt_never_reposts_the_day() (+17 more)

### Community 854 - "Mixed pipeline and prop tests"
Cohesion: 0.07
Nodes (12): TestIngestEventsDoesNotShadowItsMarkets, test_the_halftime_distribution_refuses_a_choosing_season_without_enough_earlier_games(), rows(), fetchall(), test_live_prop_pull_asks_for_the_sharp_book(), fake_event_props(), fetchall(), fetchall() (+4 more)

### Community 861 - "NFL line snapshot publishing"
Cohesion: 0.15
Nodes (6): TestPublishLineSnapshots, TestSnapshotRowParams, snapshot_row_params(), _csv_row(), execute(), _write_snapshot_csv()

### Community 88 - "NBA prop market decision tests"
Cohesion: 0.04
Nodes (54): NbaPropBet, _PublishConn, _SettleConn, pick_label(), pick_rows(), _bet(), _decision(), fair_under() (+46 more)

### Community 895 - "Mobile subscription entitlement hook"
Cohesion: 0.60
Nodes (5): useAuth, useSubscription, SubscriptionRow, fetchSubscription(), isEntitled()

### Community 9 - "Publish keys and push free picks"
Cohesion: 0.02
Nodes (77): _Conn, _Conn, _KeyConn, paused_row_exclusion_sql(), test_a_real_pause_is_not_logged_as_stale(), execute(), test_empty_set_errors_when_a_stale_pause_flag_hides_bets(), execute() (+69 more)

### Community 90 - "Mobile contrast tones and range slider"
Cohesion: 0.05
Nodes (39): Pair, code(), lum(), noGreen(), over(), ratio(), read(), readUtf8() (+31 more)

### Community 92 - "tests/test_ncaaf_prop_odds.py"
Cohesion: 0.05
Nodes (27): _Conn, _Resp, _market_chunks(), _football_map(), resolver(), scope(), test_a_book_we_did_not_ask_for_is_never_written(), test_a_day_with_no_college_games_spends_nothing() (+19 more)

### Community 926 - "MLB prop feature engine"
Cohesion: 0.04
Nodes (39): _StubConn, _StubResult, _blk_nhl_loc_goals(), _all_batter_rows(), _all_pitcher_rows(), _batter_rate(), _batter_rolling_avg(), _batter_savant() (+31 more)

### Community 94 - "NCAAF in-play score distribution pricing"
Cohesion: 0.03
Nodes (57): ScoreDistribution, _cluster_bootstrap(), evaluate(), main(), report(), fit(), load_states(), main() (+49 more)

### Community 940 - "NFL prop player names and research cards"
Cohesion: 0.02
Nodes (89): TestLocalCacheGuards, TestMarketGrading, TestNormaliseName, norm_player_name(), activate(), available(), _manifest(), _path() (+81 more)

### Community 95 - "tests/test_ncaaf_pbp_store.py"
Cohesion: 0.09
Nodes (17): _Conn, load_season_from_db(), _report_ranges(), store_season(), _plays(), test_a_rerun_updates_rather_than_duplicating(), test_a_season_in_neither_place_is_an_error_not_a_short_corpus(), test_a_season_survives_the_round_trip_in_the_cfbd_spelling() (+9 more)

### Community 96 - "tests/test_heartbeat_watchdog.py"
Cohesion: 0.05
Nodes (35): _FakeConn, _FakeCursor, _break_db(), test_a_failed_post_does_not_start_the_throttle(), test_a_healthy_start_never_announces_a_recovery(), test_a_returning_outage_alerts_again_immediately(), test_a_silent_failure_alerter_is_caught_by_the_watchdog(), test_a_stalled_pipeline_outranks_a_silent_alerter() (+27 more)

### Community 97 - "Discord live signal embeds and prices"
Cohesion: 0.04
Nodes (42): _FakeConn, _sig(), test_a_strictly_better_book_becomes_the_headline(), test_an_equal_or_worse_price_never_replaces_draftkings(), test_draftkings_winning_its_own_shop_is_published_as_draftkings(), test_every_pre_game_producer_computes_good_to(), test_good_to_is_published_when_the_producer_supplies_it(), test_good_to_is_simply_absent_when_it_cannot_be_computed() (+34 more)

### Community 99 - "Record correction social posts"
Cohesion: 0.06
Nodes (28): Ledger, _Result, _pin(), _real_post(), _real_tweet(), x_posts(), _publish(), test_a_failed_discord_ledger_does_not_send_x() (+20 more)

### Community 100 - "NFL edge research shared helpers"
Cohesion: 0.03
Nodes (92): backfill_cost(), bets(), bh(), clean_2h(), fmt(), forward_2026(), hdr(), _line_models() (+84 more)

### Community 102 - "scripts/nfl_edge_live_rush_pace.py"
Cohesion: 0.18
Nodes (26): _asof(), boot_p(), build_state(), first(), grade(), initial_last(), load_pbp(), main() (+18 more)

### Community 103 - "NBA prop projection tests"
Cohesion: 0.05
Nodes (29): _art(), _proj(), _q(), _run(), _settle(), test_a_book_hanging_two_lines_for_one_player_is_refused(), test_a_decision_with_no_bet_is_still_a_decision(), test_a_past_game_never_projected_gets_the_newest_espn_pull_55_minutes_before_its_tip() (+21 more)

### Community 104 - "NFL preregistered 2026 edge study"
Cohesion: 0.09
Nodes (39): bar(), bets_frame(), bh(), binom_line(), _by_game(), cell(), fam(), first_last() (+31 more)

### Community 107 - "tests/test_prop_calibrated_decision.py"
Cohesion: 0.06
Nodes (30): apply_prop_daily_cap(), _claimed_ev(), dedupe_player_props(), _downgrade(), _is_paused_row(), _bet(), _identity_cal(), _prop() (+22 more)

### Community 109 - "NBA fourth search derivative markets"
Cohesion: 0.07
Nodes (32): team_total_dist(), calibrated_refs(), cell_specs(), choosing(), decision_quotes(), derivative_data(), emit_f1(), emit_f4() (+24 more)

### Community 110 - "tests/test_mobile_line_movement.py"
Cohesion: 0.08
Nodes (27): _fn(), _read(), _run(), test_a_cut_table_keeps_the_pick_and_says_what_it_covers(), test_a_cut_window_keeps_the_pick_row_on_the_8_row_table(), test_a_pick_made_after_the_cards_start_never_reads_since_your_pick(), test_after_the_start_the_verdict_is_not_graded(), test_an_old_snapshot_is_not_the_price_at_the_pick() (+19 more)

### Community 111 - "tests/test_live_calibration.py"
Cohesion: 0.06
Nodes (34): decide(), pick(), test_a_peak_with_no_plateau_anywhere_is_labelled_as_one(), test_a_prob_cut_and_an_ev_cut_select_different_picks(), test_calibration_also_scores_ev_against_realised_roi(), test_calibration_is_empty_rather_than_wrong_with_nothing_settled(), test_calibration_reports_the_gap_between_claim_and_reality(), test_expected_value_matches_the_hand_calculation() (+26 more)

### Community 112 - "NBA in-game luck study one"
Cohesion: 0.08
Nodes (28): attach_rates(), build(), close_totals(), decisions(), eligible(), fair_mu(), fit_w(), gate_passes() (+20 more)

### Community 117 - "NBA lineup stint derivation tests"
Cohesion: 0.08
Nodes (45): order_plays(), _blowout_q4(), derive(), dreb(), _dup_game(), end_period(), five_game(), make2() (+37 more)

### Community 118 - "NBA play-by-play parsing tests"
Cohesion: 0.06
Nodes (30): drop_duplicate_box_ids(), _last(), match_games(), match_names(), resolve_map(), _g(), _game_recs(), _rec() (+22 more)

### Community 119 - "tests/test_ncaaf_live_notify.py"
Cohesion: 0.05
Nodes (18): _load_write_picks(), _restore_stubbed_modules(), test_a_caller_supplied_connection_is_not_closed_by_the_write(), test_a_failing_notifier_never_breaks_pricing(), test_a_full_slate_announces_once(), test_a_live_bet_notifies_push_and_discord(), test_a_locked_lane_is_not_rewritten(), test_a_locked_lane_keeps_notifying_after_the_engine_stops_betting() (+10 more)

### Community 122 - "NCAAF quarterback team features"
Cohesion: 0.12
Nodes (24): build_qb_team_features(), load_qb_games(), merge_qb_features(), _feat(), _frame(), _games(), _qb_rows(), _qb_team() (+16 more)

### Community 124 - "NHL prop backtest and EV lab"
Cohesion: 0.08
Nodes (31): books(), build_frame(), card(), claimed_vs_realised(), day_interval(), line(), main(), namesakes() (+23 more)

### Community 126 - "Live monitor dashboard data store"
Cohesion: 0.09
Nodes (25): meta(), ops(), snapshot(), api_rollup(), call_timeline(), calls_since(), community(), scalar() (+17 more)

### Community 127 - "NFL prop book bettability check"
Cohesion: 0.25
Nodes (6): soft_verdict(), test_a_bettable_book_still_passes(), test_an_unbettable_book_is_excluded_however_good_its_numbers(), test_every_incumbent_soft_book_is_bettable(), test_the_clause_is_not_dead_code(), _verdict()

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
Cohesion: 0.10
Nodes (30): _american(), _complete(), _num(), parse_coupon(), poll_once(), _row_for(), _seen_key(), _stamp() (+22 more)

### Community 136 - "NCAAF cross-book opener tests"
Cohesion: 0.07
Nodes (25): _minutes_apart(), build_artifact(), build_band_artifact(), _branch(), test_absent_ceiling_means_unbounded(), test_artifact_shape(), test_band_ceiling_is_enforced_in_the_scorer(), test_band_volumes_sum_to_the_single_gate_backtest() (+17 more)

### Community 137 - "NFL 2024 in-play totals grading"
Cohesion: 0.11
Nodes (36): books_per_snapshot(), cell(), finalize_states(), h1(), h1_calibration(), h2(), h2_accuracy(), h3_accuracy() (+28 more)

### Community 139 - "NFL 2025 in-play edge research"
Cohesion: 0.10
Nodes (37): s(), h3(), attach_games(), attach_state(), bh(), cell(), cp_roi(), diagnostics() (+29 more)

### Community 141 - "MLB in-play odds history pull"
Cohesion: 0.18
Nodes (16): _get(), _iso(), main(), planned_calls(), pull_day(), rows_for(), _served_already(), shard_windows() (+8 more)

### Community 142 - "tests/test_health_pregame_prices_current.py"
Cohesion: 0.10
Nodes (30): _at(), _game(), _row(), _run(), test_a_broken_feed_read_is_an_error_and_rolls_back(), test_a_broken_query_is_an_error_and_rolls_back(), test_a_cancelled_fight_and_a_pulled_game_do_not_raise_the_alarm(), test_a_dead_feed_with_no_priced_game_is_a_crit() (+22 more)

### Community 144 - "NBA game line move study"
Cohesion: 0.07
Nodes (32): attach(), big_home_dog_signal(), consensus(), control_specs(), coverage_text(), fade_side(), favourite_sides(), first_fetch() (+24 more)

### Community 145 - "NBA stats and player log ingestion"
Cohesion: 0.08
Nodes (25): fill_missing_game_logs(), backfill_nba_stats(), _box_adds_up(), _build_game_id(), _build_game_rows(), _build_player_log_rows(), _build_team_stat_rows(), _fetch_league_game_log() (+17 more)

### Community 147 - "scripts/nfl_edge_extreme_props.py"
Cohesion: 0.16
Nodes (25): actuals(), add_modes(), bar(), candidates(), cell(), decision_boards(), devig(), fit_holdout() (+17 more)

### Community 148 - "scripts/nfl_edge_settlement.py"
Cohesion: 0.14
Nodes (30): add_test(), attach(), banner(), bh(), board(), boot_draws(), cell(), choose() (+22 more)

### Community 152 - "WNBA points prop rebuild and sweep"
Cohesion: 0.08
Nodes (25): build_bulk_wnba_prop_lookups(), build_wnba_prop_training_dataset(), _nb_dispersion(), _oof_predictions(), _poisson_objective(), train_prop_model(), build_dataset(), fetch_injury_out_map() (+17 more)

### Community 153 - "tests/test_agents_contract.py"
Cohesion: 0.05
Nodes (20): _labelled_retired(), test_blocked_items_are_marked_so_the_agent_skips_them(), test_every_backlog_item_is_a_checkbox(), test_neither_agent_may_change_a_model_threshold(), test_the_agents_are_findable_from_the_file_every_session_reads(), test_the_backlog_does_not_promise_an_agent_that_no_longer_runs(), test_the_backlog_exists_and_has_items(), test_the_contract_documents_every_agent_by_name() (+12 more)

### Community 157 - "Live model holdout comparison"
Cohesion: 0.31
Nodes (6): bias_table(), confident_share(), load_artifact(), main(), poisson_sf(), predict()

### Community 159 - "WNBA results ingestor"
Cohesion: 0.04
Nodes (56): build_log_row(), _core_athlete(), _deref(), _et_date(), _fetch_core_box_players(), _fetch_core_games(), _fetch_scoreboard(), _fetch_summary() (+48 more)

### Community 16 - "NBA public betting splits ingestor"
Cohesion: 0.11
Nodes (16): active_queries(), archive_ready(), ensure_table(), fetch_scoreboard(), keep_for_poll(), _known_abbrs(), load_games_index(), not_started() (+8 more)

### Community 161 - "NBA box score enrichment"
Cohesion: 0.07
Nodes (49): _blank(), box_rows(), _check_unmapped(), _create(), dnp_kind(), ensure_tables(), fetch_advanced(), _flt() (+41 more)

### Community 163 - "NBA derivative market lab"
Cohesion: 0.09
Nodes (35): add_team(), am_to_dec(), bars_for(), bet_list(), blind(), boot_ci(), build_line_rows(), build_outcomes() (+27 more)

### Community 167 - "scripts/nfl_preflight.py"
Cohesion: 0.19
Nodes (17): _load_postgres_schema(), check(), check_cards_run(), check_config_gates(), check_cost(), check_data(), data_check(), check_import_shadowing() (+9 more)

### Community 168 - "Mobile source logic tests via node"
Cohesion: 0.03
Nodes (62): node_exe(), node_strips_types(), test_app_errors_is_write_only_for_the_anon_key(), test_crash_log_is_free_of_app_imports(), test_kinds_agree_between_app_and_server(), test_the_crash_log_logic_holds(), test_the_fallback_never_renders_blank(), test_a_published_void_keeps_track_and_betslip() (+54 more)

### Community 169 - "NBA halftime in-game research"
Cohesion: 0.08
Nodes (24): add_features(), attach_close(), build_halves(), centre(), day_ci(), decision_games(), decision_quotes(), first_part() (+16 more)

### Community 172 - "MLB totals public fade under shopping"
Cohesion: 0.11
Nodes (14): diff(), pitcher_diff(), diff(), pitcher_diff(), numeric_feature_value(), _pct_pair(), _better_under(), _line_in_window() (+6 more)

### Community 173 - "tests/test_decide_on_calibrated.py"
Cohesion: 0.06
Nodes (19): _pick(), _pick_at(), test_a_calibrated_cut_is_paired_with_a_calibrated_decision(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(), test_a_genuinely_big_edge_still_fires_after_calibration(), test_a_hot_model_no_longer_fires_the_marginal_bet(), test_a_model_on_a_calibrated_cut_is_not_paused(), test_a_paused_model_never_fires_regardless() (+11 more)

### Community 176 - "NBA prop projection lab"
Cohesion: 0.10
Nodes (46): implied(), bars(), bh_read(), blind(), boot(), by(), cal_ab(), candidates() (+38 more)

### Community 180 - "Kalshi game and prop ladder ingestor"
Cohesion: 0.07
Nodes (21): event_code(), event_date(), kalshi_school(), _num(), probe(), record_game_markets(), resolve_events(), rows_for() (+13 more)

### Community 181 - "NBA in-game data staleness gate"
Cohesion: 0.04
Nodes (50): attach_pinnacle(), box_checks(), build(), drop_wild_wallclocks(), espn_map(), foul_flags(), is_heave(), keep_in_play() (+42 more)

### Community 182 - "tests/test_model_artifacts_load.py"
Cohesion: 0.09
Nodes (17): _git(), _gitignore_keep_pkls(), _ignored(), _manifest_keep_pkls(), _newest_per_model(), test_a_path_that_is_not_ignored_is_not_reported(), test_a_superseded_timestamped_pkl_is_ignored(), test_an_ignored_path_comes_back_byte_identical() (+9 more)

### Community 183 - "Mobile live, team and player screen tests"
Cohesion: 0.02
Nodes (72): _book_of(), part_a_card(), part_b(), _table(), test_every_revoke_names_the_roles_rather_than_public(), test_it_does_not_enable_rls_blind(), test_odds_keeps_select_for_the_app(), test_the_app_write_tables_are_not_touched() (+64 more)

### Community 185 - "scripts/game_line_market_sweep.py"
Cohesion: 0.08
Nodes (22): _by_month(), collect_picks(), devig(), _gap_seconds(), grade(), implied(), iter_months(), load() (+14 more)

### Community 186 - "Historical odds backfill and resume"
Cohesion: 0.06
Nodes (22): _ledger_entry_is_resumable(), relabel_in_play(), run_historical_odds_range(), test_the_in_play_relabel_uses_the_better_bound(), test_a_rerun_can_be_told_to_ignore_the_pull_ledger(), test_a_snapshot_after_first_pitch_is_marked_in_play(), test_a_snapshot_exactly_at_first_pitch_stays_pregame(), test_backfill_rows_are_stamped_with_the_historical_source() (+14 more)

### Community 187 - "Push notification deep link tests"
Cohesion: 0.08
Nodes (23): _code(), _py_version(), _read(), test_a_single_pick_deep_links_and_a_batch_does_not(), test_an_unreadable_payload_routes_nowhere_rather_than_guessing(), test_both_halves_pin_the_same_payload_version(), test_every_expo_message_carries_a_data_payload(), test_every_summary_producer_can_deep_link_a_single_pick() (+15 more)

### Community 188 - "tests/test_pass_instrumentation.py"
Cohesion: 0.06
Nodes (11): test_a_dead_database_does_not_fail_the_step(), test_a_raised_failure_still_records_the_exception(), test_a_step_that_raises_is_still_TIMED(), test_a_step_that_raises_still_raises(), boom(), test_a_step_that_returns_false_records_a_REASON(), test_a_successful_step_records_a_duration(), test_every_step_name_in_the_dispatch_table_is_reachable() (+3 more)

### Community 190 - "tests/test_db_adapt_sql.py"
Cohesion: 0.12
Nodes (21): _adapt_sql(), _named(), test_a_block_comment_is_skipped_too(), test_a_colon_word_inside_a_comment_is_not_a_placeholder(), test_a_dash_dash_inside_a_literal_is_data_not_a_comment(), test_a_line_comment_ends_at_the_newline(), test_a_real_param_after_a_literal_still_converts(), test_an_apostrophe_in_a_comment_does_not_swallow_a_later_literal() (+13 more)

### Community 195 - "tests/test_mobile_contrast_tokens.py"
Cohesion: 0.12
Nodes (30): _code_lines(), _ionicon_colors(), _lum(), _over(), _ratio(), _read(), _rgb(), test_badge_glyph_tracks_dynamic_type() (+22 more)

### Community 197 - "Daily pipeline runner and steps"
Cohesion: 0.02
Nodes (98): _compute_return_ramp(), fetch_mlb_transactions(), fetch_return_ramp_players(), run_injury_ingestor(), run_bullpen_ingestor(), run_nba_prop_odds_ingestor(), run_wnba_prop_odds_ingestor(), mirror_unchanged() (+90 more)

### Community 198 - "NBA game four part one tests"
Cohesion: 0.06
Nodes (32): _base(), _fair(), _ladder_quotes(), _offered(), _offers(), _period_games(), _rows(), _rung() (+24 more)

### Community 20 - "Calibration agent threshold sweep tests"
Cohesion: 0.04
Nodes (31): load_calibrations(), analyse(), split(), _basis(), _cut(), fetch(), main(), analyse() (+23 more)

### Community 201 - "NBA second game line move tests"
Cohesion: 0.06
Nodes (39): _priced_season(), _q(), _sched(), _season_games(), _signal(), _split(), _stub_main(), test_a_fetch_after_T_never_reaches_the_move() (+31 more)

### Community 204 - "NBA team total luck replay build"
Cohesion: 0.07
Nodes (20): load_artifact(), pricing_dist(), quote_frame(), uplift(), bucket_counts(), build(), cell_bets(), main() (+12 more)

### Community 207 - "NFL in-play prop flow anchoring tests"
Cohesion: 0.06
Nodes (23): apply_anchor(), grade_real(), naive_line(), _anchor_frame(), _long(), test_a_degenerate_line_is_dropped(), test_a_push_on_a_whole_number_line_is_not_a_loss(), test_accrual_is_as_of_the_mark_not_the_last_involvement() (+15 more)

### Community 208 - "WNBA prop context features"
Cohesion: 0.11
Nodes (18): _build_player_row(), build_wnba_prop_scoring_rows(), _context_features_for(), _opp_team_stat(), _recent_starter(), _rest_days(), _rolling_avg(), _season_avg() (+10 more)

### Community 212 - "NBA second game verdict"
Cohesion: 0.11
Nodes (19): axes_of(), bar9(), cell_key(), _floats(), house_bar4(), house_verdict(), load_cells(), main() (+11 more)

### Community 214 - "Probability calibration fitting and sweep"
Cohesion: 0.07
Nodes (29): apply_calibration(), demote(), ensure_schema(), _era_start(), fetch_graded(), fit_model(), fit_offset(), fit_platt() (+21 more)

### Community 219 - "tests/test_nfl_live_leader_state.py"
Cohesion: 0.15
Nodes (18): situation(), status(), test_a_conversion_try_is_skipped(), test_a_previous_quarters_play_is_not_the_state(), test_a_timeout_is_skipped_for_the_play_before_it(), test_after_a_scoring_play_nothing_is_evaluated(), test_after_the_kickoff_lands_the_receiver_has_the_ball(), test_an_ordinary_snap_is_evaluable_with_the_training_inputs() (+10 more)

### Community 221 - "tests/test_ncaaf_qb_ingestor.py"
Cohesion: 0.11
Nodes (24): _athlete_stats(), _comp_att(), parse_qb_game_stats(), _split_ratio(), test_split_ratio(), _parse(), _payload(), _team() (+16 more)

### Community 230 - "tests/test_local_cache_is_additive.py"
Cohesion: 0.15
Nodes (7): cached(), _frame(), test_a_first_ever_pull_still_works(), test_a_pull_that_lost_rows_keeps_them(), test_an_unreadable_cache_refuses_rather_than_overwrites(), test_rows_present_in_both_are_kept_once(), test_the_pull_ITSELF_is_additive()

### Community 232 - "First pitch guard for capture and delivery"
Cohesion: 0.11
Nodes (7): test_capture_compares_the_picks_own_clock_not_the_capture_clock(), test_capture_fails_open_on_a_missing_timestamp(), test_delivery_fails_open_too(), test_health_check_uses_the_same_first_pitch_bound_as_discord(), test_mixed_timestamp_shapes_are_parsed_not_string_compared(), test_the_dry_run_count_uses_the_same_predicate_as_the_insert(), test_the_restatement_path_is_deliberately_not_guarded()

### Community 237 - "House juice price floor tests"
Cohesion: 0.13
Nodes (9): _blocked_by_min_odds(), test_a_pick_with_no_price_is_never_blocked_by_the_floor(), test_an_explicit_floor_wins_in_BOTH_directions(), test_ordinary_prices_still_fire(), test_the_default_is_overridable_without_a_code_change(), test_the_measured_blast_radius_is_recorded(), test_the_mirror_never_writes_a_null_floor(), test_the_offending_pick_would_now_be_blocked() (+1 more)

### Community 240 - "tests/test_ncaaf_game_identity.py"
Cohesion: 0.12
Nodes (16): _add(), _conn(), _identity_sql(), _run(), test_a_clean_slate_reports_nothing(), test_a_non_fbs_fixture_is_not_reported(), test_a_phantom_opponent_is_detected_too(), test_a_real_doubleheader_is_not_a_duplicate() (+8 more)

### Community 241 - "NBA second game market tests"
Cohesion: 0.10
Nodes (27): _close_frames(), _data(), _f2_games(), _f6a_data(), _f6d_total_data(), _game(), _pe(), _q() (+19 more)

### Community 252 - "Count prop over-probability dispersion"
Cohesion: 0.09
Nodes (12): _count_over_prob(), _nb1_over_prob(), _poisson_over_prob(), _setup(), test_an_artifact_wanting_an_unmapped_column_is_never_scored(), test_an_unknown_family_refuses_to_price_rather_than_falling_back(), test_every_mapped_model_can_be_built_from_the_map(), test_nb1_has_the_mean_it_claims_and_a_wider_variance() (+4 more)

### Community 254 - "Kalshi ladder recorder tests"
Cohesion: 0.10
Nodes (5): test_a_kalshi_outage_cannot_break_the_pass(), test_a_run_is_idempotent_within_its_snapshot(), test_one_snapshot_timestamp_for_the_whole_run(), test_the_recorder_is_scheduled_on_the_pipeline_role(), test_the_recorder_keeps_raw_prices_not_a_filtered_ladder()

### Community 255 - "UFC results download caching"
Cohesion: 0.13
Nodes (10): _cached_etag(), _etag_cache_path(), _store_etag(), test_a_mounted_volume_is_preferred_over_tmp(), test_a_round_trip_actually_persists(), test_a_volume_path_that_does_not_exist_falls_back(), test_an_empty_etag_is_never_stored(), test_an_explicit_override_wins() (+2 more)

### Community 258 - "Prop market coverage board probe"
Cohesion: 0.33
Nodes (3): _board_markets(), table(), test_the_mlb_board_and_the_mlb_pull_are_one_set()

### Community 259 - "NBA total luck card publishing"
Cohesion: 0.11
Nodes (15): artifact(), decided_games(), ensure_decisions_table(), ledger_exists(), load_quote_rows(), load_season(), main(), newest_fetch() (+7 more)

### Community 260 - "tests/test_live_game_features.py"
Cohesion: 0.11
Nodes (19): compute_live_target(), half_innings_left(), parse_bases(), state_features(), test_build_live_state_row_merges_pregame_context(), test_build_live_state_row_unusable_state(), test_half_innings_left_bottom_ninth(), test_half_innings_left_extras_clamps_to_one() (+11 more)

### Community 262 - "UFC fight feature builder"
Cohesion: 0.09
Nodes (30): rounds_completed(), _age_years(), _assemble_ufc_features(), _blk_career_stats(), build_ufc_game_features(), career_stats(), compute_ufc_target(), _fight_minutes() (+22 more)

### Community 263 - "NFL halftime edge out-of-sample replay"
Cohesion: 0.12
Nodes (22): assert_same_as_earlier(), bh(), boot(), boot_coef(), build(), ci(), coverage(), fmt() (+14 more)

### Community 266 - "NBA quarter game model tests"
Cohesion: 0.11
Nodes (29): _data(), _game(), _ladder(), _no_real_load(), _point(), _pricing_world(), _q(), _row() (+21 more)

### Community 267 - "NBA second game luck studies"
Cohesion: 0.06
Nodes (32): timing(), as_of_ratings(), _before(), box_mismatches(), f4_projections(), f4_signal(), _known_team(), lead_minutes() (+24 more)

### Community 268 - "Signal deliverability window tests"
Cohesion: 0.11
Nodes (10): test_a_game_date_inside_the_window_counts(), test_a_lookahead_commence_counts_even_when_game_date_is_outside(), test_a_signal_locked_after_first_pitch_was_never_deliverable(), test_a_signal_locked_before_first_pitch_still_counts(), test_a_signal_locked_exactly_at_first_pitch_counts(), test_a_started_game_outside_the_window_does_not_count(), test_it_fails_toward_noticing(), test_mixed_timestamp_shapes_are_parsed_not_string_compared() (+2 more)

### Community 271 - "Line CLV sign and orientation tests"
Cohesion: 0.07
Nodes (8): test_runner_captures_stdout_from_the_script_main(), _load(), test_a_line_that_held_is_exactly_zero_not_none(), test_a_missing_close_is_not_a_zero(), test_a_side_that_cannot_be_oriented_returns_none_rather_than_guessing(), test_the_home_and_away_sides_are_exact_mirrors(), test_the_prop_market_flag_wins_over_the_market_string(), test_the_signs_are_the_negation_of_the_apps_entry_frame()

### Community 272 - "Mobile player stat group tests"
Cohesion: 0.15
Nodes (10): _set_literal(), _src(), test_a_group_is_filled_only_by_a_real_number(), test_a_tab_opens_on_the_stat_the_player_fills_most(), test_defensive_positions_get_only_the_defense_group(), test_every_logged_position_is_classified(), test_non_defensive_positions_get_no_defense_group(), test_offensive_positions_are_not_defensive() (+2 more)

### Community 275 - "NBA game harness tests"
Cohesion: 0.08
Nodes (28): test_a_period_moneyline_removes_the_tie_mass(), _cov_data(), _fetches(), _games(), _offers(), _q(), _stale_cache(), test_a_cell_reports_its_pooled_walk_forward_and_writes_its_bets() (+20 more)

### Community 276 - "UFC fight results scraper"
Cohesion: 0.10
Nodes (17): backfill_ufc_stats(), _build_ufc_game_id(), _fetch_event(), _fetch_event_list(), _fetch_fight(), _fetch_fighter(), _get(), _home_win_for_row() (+9 more)

### Community 280 - "NFL in-play flow slice backtest"
Cohesion: 0.13
Nodes (16): _clustered_ci(), _qcut(), _rows_for(), slice_table(), verdict(), _frame(), _table(), test_a_bias_living_in_one_quarter_reads_as_concentrated() (+8 more)

### Community 284 - "Discord price bound and voided picks"
Cohesion: 0.10
Nodes (16): _dec(), test_a_field_without_a_bound_renders_without_the_clause(), test_a_model_with_no_own_ev_floor_is_bound_by_the_global_one(), test_a_price_floor_can_be_the_binding_gate(), test_a_rounded_bound_still_clears_the_bound_it_came_from(), test_even_money_is_plus_one_hundred(), test_no_bound_from_junk_rather_than_a_guess(), test_no_bound_when_the_edge_floor_is_unreachable() (+8 more)

### Community 287 - "Model calibration check tests"
Cohesion: 0.11
Nodes (11): _calibration_sql(), test_a_flagged_model_is_named_eligible_or_not(), test_a_thin_model_is_still_excluded_rather_than_accused(), test_eligibility_notes_must_not_sink_the_gap_check(), test_it_grades_the_calibrated_probability_not_the_raw_one(), test_it_joins_picks_to_reach_the_calibrated_column(), test_the_check_has_a_skip_budget_that_survives_a_regime_change(), test_the_probability_floor_applies_to_the_decision_number_too() (+3 more)

### Community 29 - "NCAAF college data ingestor"
Cohesion: 0.06
Nodes (35): backfill_ncaaf_lines(), backfill_ncaaf_players(), backfill_ncaaf_qb(), _date_or_none(), _existing_ncaaf_ids(), _fold(), _get(), ingest_ncaaf_game_log() (+27 more)

### Community 290 - "MLB game market card and gate"
Cohesion: 0.09
Nodes (17): first_eligible_snapshot(), load_opening_odds(), _parse_ts(), persist(), load_latest_quotes(), _run(), _get_public_betting(), main() (+9 more)

### Community 291 - "Team stats games played invariants"
Cohesion: 0.08
Nodes (14): impossible_games_played(), _played_actual(), test_a_missing_count_is_reported_not_silently_passed(), test_an_honest_row_passes(), test_claiming_fewer_games_than_played_is_fine(), test_feb_gp_climbing_vs_zero_regular_season_still_fails(), test_mlb_twin_codes_do_not_false_crit(), test_mlb_twin_reverse_lookup_also_resolves() (+6 more)

### Community 293 - "Market coverage and firing guard tests"
Cohesion: 0.03
Nodes (44): test_the_artifact_table_revokes_at_its_own_creation(), test_a_run_that_writes_nothing_is_not_reported_as_success(), test_the_insert_rolls_back_per_row(), test_the_market_movement_loader_uses_the_better_bound(), test_the_nfl_prop_scorer_uses_the_better_bound(), test_the_prop_scorer_uses_the_better_bound(), test_the_wnba_prop_market_loader_coalesces_in_sql(), test_sport_and_market_are_bounded() (+36 more)

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
Nodes (20): pseudo_clv(), _bet(), _preds(), _quote(), _quotes(), synthetic(), test_a_far_away_kickoff_is_a_different_season(), test_a_quote_before_any_state_is_dropped() (+12 more)

### Community 315 - "NFL in-play remaining-yards engine training"
Cohesion: 0.13
Nodes (14): _cluster_bootstrap(), evaluate(), main(), report(), fit(), load_states(), main(), walk_forward_oos() (+6 more)

### Community 316 - "EV floor and honest cut replays"
Cohesion: 0.13
Nodes (19): _in_graded_matview(), _is_live_lane(), _era(), grade(), wilson(), _cell(), _decimal(), fetch_rows() (+11 more)

### Community 317 - "Scratch Postgres line state tests"
Cohesion: 0.06
Nodes (37): main(), can_scratch(), env_dsn(), _free_port(), pg_bin(), scratch_cluster(), sink(), as_app() (+29 more)

### Community 318 - "tests/test_live_record_start_views.py"
Cohesion: 0.09
Nodes (12): _body(), _code(), test_both_published_views_carry_the_live_date_gate(), test_it_runs_after_the_migration_that_used_to_own_the_daily_view(), test_migration_is_one_statement(), test_migration_is_registered_with_the_worker_runner(), test_neither_view_reads_the_sweep_universe(), test_no_ddl_outside_the_guarded_branches() (+4 more)

### Community 319 - "UFC historical CSV loader"
Cohesion: 0.11
Nodes (21): _aggregate_stats(), backfill_ufc_csv(), build_events(), build_fighter_index(), ingest_ufc_results_for_date_csv(), _kd_int(), load_fighter_profiles_from_csv(), _mirror_etag() (+13 more)

### Community 327 - "NHL prop odds fetch gate"
Cohesion: 0.07
Nodes (22): due(), _book(), test_a_200_on_both_calls_merges_the_alternate_lines(), fake_fetch(), test_a_game_first_priced_inside_the_final_window_gets_nothing_more(), test_a_game_first_priced_inside_the_window_gets_one_decision_snapshot(), test_a_game_with_nothing_stored_is_owed_its_open(), test_a_moved_featured_line_keeps_the_old_number_under_the_alternate_key() (+14 more)

### Community 328 - "NFL Kalshi edge search"
Cohesion: 0.17
Nodes (20): align_check(), bh(), bins(), boot(), cell(), coverage(), cp_roi(), fee() (+12 more)

### Community 329 - "nfl/models/opener_spread.py"
Cohesion: 0.13
Nodes (12): bettable_books(), age_tag(), american_to_prob(), _bettable_books(), clean_board(), edge_tier(), evaluate_board(), held_minutes() (+4 more)

### Community 332 - "MLB live slate midnight discovery tests"
Cohesion: 0.05
Nodes (26): live_slate_dates(), _slate_dates(), _discover_active_games(), _fetch_live_feed(), _game_id_from_statsapi(), _insert_state(), _insert_triggers(), poll_forever() (+18 more)

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
Cohesion: 0.04
Nodes (41): _identity_maps(), _platform_gates_off(), _declared(), test_an_explicit_run_date_must_be_a_real_iso_date(), test_declared_keys_are_unique(), test_every_declared_job_names_a_registered_type(), test_every_declared_job_validates(), test_no_run_date_means_the_module_resolves_it() (+33 more)

### Community 346 - "NFL research edge data cache"
Cohesion: 0.22
Nodes (14): _conn(), copy_main_local(), _df(), _games_2026(), log(), main(), nflverse_misc(), nflverse_pbp() (+6 more)

### Community 347 - "Mobile sport filter persistence tests"
Cohesion: 0.14
Nodes (10): _load_body(), _sports(), _src(), test_a_visit_scoped_sport_change_does_not_persist(), test_a_writer_landing_during_the_hydrate_is_not_overwritten(), test_every_sport_survives_a_cold_start(), test_no_retired_sport_is_a_selectable_chip(), test_no_second_hand_written_sport_list_in_the_hook() (+2 more)

### Community 35 - "NBA second game projection tests"
Cohesion: 0.07
Nodes (34): _box(), _dist(), _games(), _games_file(), _inj(), _rapm_inputs(), _segment_rows(), _segments() (+26 more)

### Community 351 - "Live game state poller triggers"
Cohesion: 0.12
Nodes (23): _bases_state(), _detect_triggers(), _extract_state(), _is_active_or_starting_soon(), test_active_in_progress_game_is_active(), test_bases_state_empty(), test_bases_state_loaded(), test_bases_state_single_runner() (+15 more)

### Community 353 - "NFL in-play flow snapshot validation"
Cohesion: 0.16
Nodes (14): bias_table(), main(), load_rows(), main(), attach_ids(), _game_marks(), load_snapshots(), main() (+6 more)

### Community 354 - "Bring your own model game facts"
Cohesion: 0.07
Nodes (42): assemble_game(), grade_ats(), grade_ml(), grade_total(), is_primetime(), lead_hours(), line_at_start(), _num() (+34 more)

### Community 358 - "NBA period map pricing tests"
Cohesion: 0.06
Nodes (32): _game(), _games3(), _gaps(), _ladder_quotes(), _luck_games(), _maps(), _odds_row(), _offered() (+24 more)

### Community 359 - "NCAAF model search runner"
Cohesion: 0.14
Nodes (16): _apply_calibration(), exponential_recency_weights(), _logit(), make_ensemble(), fit_predict(), make_lgbm(), fit_predict(), make_logreg() (+8 more)

### Community 36 - "NCAAF CFBD ingestor tests"
Cohesion: 0.03
Nodes (54): build_ncaaf_game_id(), _day_before(), eastern_game_date(), _local_aggregates(), ncaaf_slug(), parse_lines(), parse_teams(), shrink_to_prior() (+46 more)

### Community 360 - "Mobile screen source wiring tests"
Cohesion: 0.07
Nodes (20): _bn_body(), _sql_groups(), test_a_failed_position_read_is_said_not_hidden(), test_a_failed_read_is_not_held_on_the_spinner(), test_every_mlb_stat_chip_has_a_branch(), test_every_nfl_stat_chip_has_a_branch(), test_every_roster_sport_chip_has_a_branch(), test_mlb_lineup_buckets_agree_between_app_and_server() (+12 more)

### Community 366 - "Kalshi game market recorder"
Cohesion: 0.09
Nodes (8): run_kalshi_game_record(), test_a_kalshi_outage_cannot_break_the_pass(), test_event_code_is_shared_across_series(), test_event_date_is_searched_not_anchored(), test_kalshi_labels_expand_st_and_use_the_explicit_map(), test_resolution_runs_after_every_snapshot(), test_the_recorder_is_scheduled_on_the_pipeline_role(), test_the_recorder_keeps_raw_contracts()

### Community 367 - "Mobile team detail page tests"
Cohesion: 0.11
Nodes (15): _read(), test_every_team_page_read_names_its_relation_literally(), test_next_game_is_earliest_in_the_window_not_tonights_date(), test_no_paper_trading_copy(), test_public_betting_policy_migration_exists_and_is_select_only(), test_recent_games_are_scoped_by_sport(), test_results_are_units_never_dollars(), test_sharp_gap_is_no_vig_vs_no_vig() (+7 more)

### Community 369 - "CLV price taken app parity tests"
Cohesion: 0.13
Nodes (18): _app(), _clv_card(), _node_strips_types(), _server(), test_a_label_book_nfl_pick_compares_its_line_with_that_book(), test_a_recorded_book_differs_from_the_derived_one(), test_the_app_prefers_the_recorded_book_at_the_derived_price(), test_the_app_prices_every_row_as_the_server_grades_it() (+10 more)

### Community 371 - "NCAAF totals probability regression tests"
Cohesion: 0.10
Nodes (14): total_over_prob(), test_artifact_kind_is_routed_by_the_scorer(), test_asymmetry_is_real_and_would_have_bitten(), test_extremes_are_clamped_away_from_certainty(), test_model_above_the_line_favours_the_over(), test_model_below_the_line_favours_the_under(), test_no_dk_total_means_skip_not_prob_only(), test_no_residuals_returns_one_half_not_a_confident_bet() (+6 more)

### Community 373 - "Mobile live game status checks"
Cohesion: 0.07
Nodes (22): deadPoller, delayed, finalNoScore, future, golfDay2, live, live1, liveFinal (+14 more)

### Community 375 - "Refresh pass step ordering tests"
Cohesion: 0.10
Nodes (13): _order(), test_a_parallel_step_that_fails_is_still_recorded(), test_no_sequential_step_runs_while_a_parallel_group_is_open(), test_opening_signals_follows_every_scorer(), test_parlay_follows_opening_signals(), test_scoring_follows_every_ingest(), test_settle_follows_every_results_ingest(), test_sync_thresholds_follows_migrations_and_precedes_scoring() (+5 more)

### Community 379 - "NHL totals market model"
Cohesion: 0.12
Nodes (16): _coherent(), _fetch_ts(), find_bets(), load_fetch_quotes(), _ts(), _two_way(), _q(), test_a_different_number_is_not_the_same_bet() (+8 more)

### Community 381 - "NCAAF search feature leakage tests"
Cohesion: 0.11
Nodes (14): blended_rating(), features_for(), _synth(), test_blend_falls_back_when_one_side_missing(), test_blend_weights_move_from_prior_to_current(), test_confounded_home_assignment_plus_heavy_alpha_corrupts_hfa(), test_features_for_dedupes_and_preserves_order(), test_hfa_is_positive_and_neutral_site_excluded() (+6 more)

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

### Community 392 - "API call rollup and pruning tests"
Cohesion: 0.09
Nodes (10): test_a_fold_can_never_lower_a_stored_total(), test_a_new_process_does_not_prune_on_its_first_flush(), test_prune_rolls_up_before_it_deletes(), test_the_daily_table_is_created_and_locked_down(), test_the_daily_table_keys_on_day_api_and_source(), test_the_rollup_groups_by_eastern_day_not_utc(), test_the_rollup_reads_only_yesterday_and_today(), test_the_rollup_survives_a_failure_without_blocking_the_prune() (+2 more)

### Community 396 - "NCAAF steam lag study"
Cohesion: 0.27
Nodes (9): attach_scores(), build_events(), fmt(), grade(), lines_at_pulls(), load(), main(), summarise() (+1 more)

### Community 399 - "NFL live leader model tests"
Cohesion: 0.12
Nodes (13): art(), _d(), _raw(), test_600_seconds_and_both_lead_ends_are_inside(), test_a_flipped_spread_sign_changes_the_decision(), test_a_qualifying_state_bets_the_leader_at_its_price(), test_artifact_identity_training_and_rule(), test_band_matches_training_leader_view_on_nflverse_sign() (+5 more)

### Community 400 - "Mobile paused catalog tests"
Cohesion: 0.16
Nodes (11): _block(), _read(), test_paused_picks_reach_the_all_board_only_and_labelled(), test_stats_add_pick_refuses_a_paused_model(), test_the_behavioural_checks_pass(), test_the_bet_type_picker_filters_paused_models(), test_the_custom_model_picker_is_three_bet_types(), test_the_models_list_filters_paused_models() (+3 more)

### Community 402 - "NFL prop shape simulation"
Cohesion: 0.20
Nodes (12): anchor_scale(), calibration(), grade(), latest(), load_odds(), main(), placebo_sf(), player_gamma() (+4 more)

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

### Community 419 - "NCAAF in-play play-by-play state builder"
Cohesion: 0.16
Nodes (11): main(), _classify(), classify_report(), _detect_score_convention(), load_pbp(), load_platform_games(), pace_report(), _repair_day_offsets() (+3 more)

### Community 42 - "DataGolf ingestor and NHL SBR archive"
Cohesion: 0.05
Nodes (45): _american(), backfill_golf_rounds(), build_game_id(), _dg_get(), _earliest_commence_iso(), _event_meta_lookup(), event_slug(), ingest_golf_field() (+37 more)

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

### Community 427 - "NFL in-play prop flow model"
Cohesion: 0.09
Nodes (20): best_hit(), _boot_ci(), drop_degenerate(), evaluate(), fit_time_curve(), grade(), main(), report() (+12 more)

### Community 428 - "NFL 2026 opener and wind tracker"
Cohesion: 0.12
Nodes (20): classify(), fetch(), grade_rows(), is_void(), lead_days(), _load_nfl_model(), main(), opener_verdict() (+12 more)

### Community 429 - "NFL in-play prop line churn check"
Cohesion: 0.19
Nodes (13): churn_table(), main(), verdict(), _snaps(), test_a_line_moving_every_interval_reads_as_under_sampled(), test_a_missing_key_column_fails_loudly_rather_than_grouping_coarser(), test_a_single_snapshot_contributes_no_interval(), test_a_still_line_reads_as_still() (+5 more)

### Community 430 - "NFL in-play prop staleness reports"
Cohesion: 0.19
Nodes (11): american_b(), boot_roi(), first_per_player(), grade(), load(), main(), report(), main() (+3 more)

### Community 431 - "tests/test_pick_lock_is_on_picks.py"
Cohesion: 0.16
Nodes (9): _between(), _sql(), test_a_bet_is_still_never_re_scored(), test_only_a_bet_locks_a_pair(), test_the_cleanup_covers_the_whole_look_ahead_window(), test_the_cleanup_never_touches_a_started_game_or_a_live_row(), test_the_lock_is_no_longer_ncaaf_specific(), test_the_prop_and_live_locks_are_unchanged() (+1 more)

### Community 434 - "NFL in-play pick writer"
Cohesion: 0.13
Nodes (7): _is_market_opinion(), _lane_is_locked(), _norm_player(), resolve_game(), resolve_game_id(), test_normalised_player_key_is_the_join_the_prop_system_uses(), test_the_lane_lock_shares_the_scorers_meaning_of_locked()

### Community 437 - "Per-model threshold config tests"
Cohesion: 0.08
Nodes (8): test_an_own_floor_does_not_take_a_model_off_the_calibration_map(), test_every_model_carries_its_own_thresholds(), test_every_own_floor_names_a_live_model(), test_models_on_own_probability_is_not_derived_from_the_floor_dict(), test_no_own_floor_tightens_a_model_past_the_global_floor(), test_only_a_market_priced_model_carries_a_negative_floor(), test_own_ev_floor_and_model_min_ev_stay_disjoint(), test_the_nba_home_team_total_floor_does_not_move_with_the_platform_default()

### Community 438 - "NBA game two verdict grid tests"
Cohesion: 0.21
Nodes (20): _cell(), _grid(), _hgrid(), _house(), _mid(), test_a_cell_below_the_bet_count_enters_the_correction_at_p_one(), test_a_cell_clearing_every_bar_passes(), test_a_cell_with_no_dominant_side_is_not_held_to_a_blind_bet() (+12 more)

### Community 439 - "MLB runline retrain sweep job tests"
Cohesion: 0.10
Nodes (8): test_the_raised_timeout_is_restored_after_the_job(), test_the_restore_puts_back_a_pre_existing_value(), test_marker_file_is_in_tree_so_the_freeze_would_not_block_the_worker(), test_missing_artifact_path_refuses_to_sweep_live(), test_retrain_then_sweep_passes_the_new_path(), test_the_runner_retrains_then_sweeps_the_new_artifact(), _job_mlb_runline_retrain_sweep(), _job_retrain_model()

### Community 443 - "MLB retrain freeze guard"
Cohesion: 0.13
Nodes (9): assert_retrain_allowed(), test_import_time_flag_follows_marker_file(), test_marker_or_env_lifts_the_freeze(), test_mlb_prop_market_sweep_is_documented_exempt(), test_mlb_retrain_refused_while_incomplete(), test_mlb_threshold_sweeps_call_the_guard(), test_non_mlb_sports_are_not_gated(), test_repo_marker_file_is_present() (+1 more)

### Community 445 - "Live monitor server and feature matrix"
Cohesion: 0.08
Nodes (16): coerce_numeric_features(), feature_matrix(), configured(), guild_stats(), main(), build_server(), serve_in_thread(), _runline_row() (+8 more)

### Community 447 - "supabase/functions/discord-link/index.ts"
Cohesion: 0.24
Nodes (15): accessFor(), handleComplete(), handleStart(), handleStatus(), handleUnlink(), hmac(), issueState(), json() (+7 more)

### Community 449 - "tests/test_nfl_prop_clv.py"
Cohesion: 0.16
Nodes (9): _assign(), _book_from_label_fn(), _fn(), test_the_book_is_read_from_the_label_suffix(), test_the_closing_prop_lookup_defaults_to_draftkings_and_binds_the_book(), test_the_label_book_map_is_the_inverse_of_both_cards(), test_the_map_test_no_longer_excludes_nfl(), test_the_market_relative_rules_take_their_market_from_the_row() (+1 more)

### Community 451 - "Team stats rebuild and verify"
Cohesion: 0.15
Nodes (10): already_a_series(), _games(), live_season_snapshot_grace(), main(), _prior_season_rates(), rebuild_sport(), _team_games(), verify() (+2 more)

### Community 452 - "tests/test_scoring_methods.py"
Cohesion: 0.13
Nodes (7): _generic(), test_a_generic_model_is_never_declared_rule_or_engine(), test_accessor_defaults_to_artifact(), test_every_classified_model_carries_thresholds(), test_mlb_live_total_runs_is_artifact_backed(), test_rule_based_models_never_appear_in_a_feature_map(), test_the_map_covers_exactly_the_non_generic_models()

### Community 456 - "NFL weather edge fetch"
Cohesion: 0.15
Nodes (18): audit(), baseline(), bh(), boot(), classify(), era(), grade(), load() (+10 more)

### Community 457 - "Team stats as-of leak invariants"
Cohesion: 0.09
Nodes (19): build_rows(), seasons_with_too_few_snapshots(), _game(), test_a_real_series_passes(), test_a_row_never_includes_its_own_date(), test_a_single_snapshot_season_is_flagged(), test_a_two_snapshot_season_is_flagged(), test_counts_accumulate_across_dates() (+11 more)

### Community 458 - "NFL ESPN injury ingestion"
Cohesion: 0.06
Nodes (17): _espn_team_ids(), fetch_espn_injuries(), _fetch_espn_team_injuries(), _fetch_nba_espn_team_ids(), _fetch_nfl_espn_team_ids_core(), _fetch_wnba_espn_team_ids(), _nba_espn_team_to_abbrev(), _nfl_espn_team_to_abbrev() (+9 more)

### Community 46 - "Worker job queue runner"
Cohesion: 0.03
Nodes (32): derive_first_pitch(), test_the_worker_job_is_registered_and_defaults_to_dry_run(), test_the_discord_publish_job_calls_the_ordinary_producer(), test_the_discord_publish_job_takes_an_optional_date(), _announce(), _execute(), _job_byom_game_facts(), _job_derive_first_pitch() (+24 more)

### Community 460 - "Discord and X period recaps"
Cohesion: 0.03
Nodes (49): test_clv_line_is_empty_when_nothing_was_measured(), test_prob_only_picks_fall_back_to_the_settlement_price(), test_the_record_restatement_and_the_slate_restatement_are_separate(), test_units_convention_matches_the_stated_rule(), test_embeds_chunk_at_the_field_cap_and_the_size_cap(), bulky(), _at(), test_a_later_weekday_still_retries_that_week() (+41 more)

### Community 462 - "Anonymous read grant planning"
Cohesion: 0.03
Nodes (47): all_readable(), closed_tables(), lock_down_sql(), write_verbs_for(), _anon_can_read(), _function_plan(), _function_signature(), main() (+39 more)

### Community 465 - "nfl/scripts/backtest_opener.py"
Cohesion: 0.24
Nodes (9): boot(), by_season(), exp_win(), load(), main(), price(), report(), residuals() (+1 more)

### Community 467 - "NCAAF totals lead and consensus gate"
Cohesion: 0.17
Nodes (16): fmt(), grade(), load_closes(), main(), match(), build_lead_table(), first_cross(), fmt() (+8 more)

### Community 468 - "tests/test_latest_odds_views.py"
Cohesion: 0.25
Nodes (13): _app_columns(), _function(), test_every_log_table_has_its_insert_trigger_and_the_odds_tables_an_update_trigger(), test_every_view_reads_its_state_table_and_never_the_log(), test_no_pending_view_migration_re_creates_these_views_over_the_log(), test_the_dk_view_returns_the_apps_columns_in_order(), test_the_exclusions_survived_the_move(), test_the_game_view_returns_the_apps_columns_in_order() (+5 more)

### Community 472 - "NBA schedule ingestor"
Cohesion: 0.20
Nodes (11): ot_periods(), schedule_rows(), season_str(), _tv(), _row(), test_a_late_west_coast_tip_keeps_its_eastern_date(), test_an_undecided_playoff_slot_is_skipped(), test_game_type_is_read_from_the_first_three_digits() (+3 more)

### Community 475 - "NFL prop feature engine"
Cohesion: 0.18
Nodes (10): _add_features(), build_nfl_prop_scoring_rows(), derived_targets(), _load(), _nfl_season(), _pool_mask(), _read(), _roll() (+2 more)

### Community 476 - "tests/test_transaction_pooler.py"
Cohesion: 0.19
Nodes (8): _transaction_endpoint(), test_a_direct_connection_is_left_alone(), test_a_local_postgres_is_left_alone(), test_a_supabase_session_url_becomes_the_transaction_url(), test_it_is_idempotent(), test_only_the_port_changes(), test_the_escape_hatch_works(), test_the_job_queue_still_gets_session_mode()

### Community 477 - "Env file database URL fallback"
Cohesion: 0.16
Nodes (11): database_url(), _default_env_path(), env_value(), parse_env_file(), test_a_missing_env_file_is_empty_not_an_error(), test_a_value_containing_equals_survives(), test_env_file_is_read_when_the_environment_is_empty(), test_env_value_reads_other_keys_too() (+3 more)

### Community 478 - "MLB totals retrain sweep job tests"
Cohesion: 0.10
Nodes (10): _side_rows(), test_marker_file_is_in_tree_so_the_freeze_would_not_block_the_worker(), test_missing_artifact_path_refuses_to_sweep_live(), test_over_covers_when_combined_score_beats_the_total_line(), test_price_below_the_house_floor_is_not_a_gradable_side(), test_push_on_the_total_emits_no_sides(), test_retrain_then_sweep_passes_the_new_path(), test_the_runner_retrains_then_sweeps_the_new_artifact() (+2 more)

### Community 480 - "NCAAF in-play history backtest"
Cohesion: 0.15
Nodes (12): build_candidates(), _fmt(), load_snapshots(), main(), odds_from_rows(), report(), split_halves(), state_index_at() (+4 more)

### Community 482 - "Paused and no-signal pick rows tests"
Cohesion: 0.17
Nodes (10): _game_pick(), _prop_pick(), test_auto_paused_counts_as_paused(), test_no_signal_rows_persist_the_reason(), test_paused_game_model_avoid_stays_avoid_with_reason(), test_paused_game_model_bet_stays_bet_with_reason_and_stake(), test_paused_prop_model_avoid_stays_avoid_with_reason(), test_score_game_routes_no_signal_through_the_helper() (+2 more)

### Community 483 - "Trainer no-register mode tests"
Cohesion: 0.11
Nodes (11): _output_dir(), _register_model(), not_registering(), registering(), test_a_normal_run_DOES_register(), test_baseline_artifacts_are_not_committable(), test_baseline_runs_write_somewhere_else(), test_default_is_to_register() (+3 more)

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

### Community 493 - "UFC fighter name resolution"
Cohesion: 0.14
Nodes (12): _bulk_fighter_id(), resolve_slug(), _slug_tokens(), test_a_generational_suffix_resolves_either_way(), test_a_near_miss_is_not_a_match(), test_a_reversed_name_order_resolves(), test_a_shared_surname_alone_is_not_a_match(), test_an_ambiguous_token_set_resolves_to_nothing() (+4 more)

### Community 495 - "tests/test_worker_deps.py"
Cohesion: 0.22
Nodes (4): _requirements(), test_dashboard_packages_are_not_on_the_worker(), test_only_the_dashboard_imports_them(), test_the_worker_asks_for_the_cpu_build_of_xgboost()

### Community 50 - "scheduler.py"
Cohesion: 0.05
Nodes (55): _run_migrations(), abort_orphaned_refresh_runs(), build_scheduler(), _add_job(), _with_heartbeat(), _wrapped(), catch_up_daily_pipeline(), catch_up_refresh_pass() (+47 more)

### Community 501 - "Position defense ranks SQL checks"
Cohesion: 0.21
Nodes (10): _read(), _sql(), test_it_is_one_statement_and_each_piece_is_guarded(), test_the_app_calls_the_function_by_its_literal_name(), test_the_blend_cut_matches_the_app(), test_the_matchup_checks_pass(), test_the_matchup_header_fills_its_column_and_large_text_is_one_line(), test_the_role_and_stat_cuts_match_the_player_card() (+2 more)

### Community 502 - "NFL in-play leader win probability"
Cohesion: 0.21
Nodes (10): h1_frame(), async_check(), fit_wp(), h1(), leader_view(), logit_irls(), wp_design(), wp_lookup() (+2 more)

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
Nodes (94): bh_fdr(), binom_p(), eval_rule(), load(), main(), build(), fetch_issued_all_leads(), games() (+86 more)

### Community 512 - "tests/test_savant_freshness.py"
Cohesion: 0.14
Nodes (5): test_rows_are_stamped_with_a_capture_date(), test_savant_has_a_schedule(), test_the_insert_persists_the_stamp(), test_the_savant_job_belongs_to_the_pipeline_service(), test_the_stamp_defaults_rather_than_being_required_at_call_sites()

### Community 513 - "tests/test_scorer_nfl_prop_like_escape.py"
Cohesion: 0.23
Nodes (9): _between(), _broken_per_game_sql(), _first_sql(), _per_game_sql(), _sweep_sql(), test_escape_tripwire_is_on_the_pr_ci_subset(), test_live_per_game_clear_interpolates_with_one_game_id(), test_live_sweep_clear_interpolates_with_date_horizon_now() (+1 more)

### Community 514 - "NFL in-play prop model assessment"
Cohesion: 0.20
Nodes (13): american_b(), boot_ci(), build(), cluster_se_mean(), implied(), load(), main(), restore_archive() (+5 more)

### Community 516 - "NHL stats views tests"
Cohesion: 0.15
Nodes (14): _date_filter_runs_before_dedupe(), anywhere(), blob(), filter_wraps_unique(), has_unique(), pred(), pred_inside_unique(), _pg_bin() (+6 more)

### Community 518 - "Concurrent injury fetch speed tests"
Cohesion: 0.07
Nodes (11): _athlete_name(), _clear_cache(), test_a_dead_database_leaves_the_cache_empty_not_broken(), test_a_failed_lookup_is_not_cached(), test_a_known_athlete_costs_no_request(), test_a_SUCCESSFUL_response_with_no_name_is_not_cached(), test_an_unknown_athlete_is_fetched_and_then_remembered(), test_one_team_failing_does_not_lose_the_others() (+3 more)

### Community 519 - "Published record reconciliation checks"
Cohesion: 0.16
Nodes (8): test_a_pick_before_the_live_date_is_caught_in_either_view(), test_a_sport_missing_from_the_daily_view_is_caught(), test_an_empty_record_is_not_a_problem(), test_cent_level_agreement_is_required(), test_same_picks_but_different_money_is_caught(), test_the_fixed_production_numbers_reconcile(), test_the_real_production_drift_is_caught(), _published_record_problems()

### Community 520 - "Market movement feature builder"
Cohesion: 0.09
Nodes (23): american_to_prob(), build_market_features(), _is_full_game_snap(), _latest_two_sided(), _s(), test_a_game_with_no_decision_book_still_gets_features(), test_a_line_that_genuinely_did_not_move_is_zero_not_none(), test_a_one_way_sharp_quote_yields_nothing() (+15 more)

### Community 525 - "NFL live pick price ceiling tests"
Cohesion: 0.10
Nodes (9): _executor_min_price(), _probe_config(), test_the_ceiling_is_a_refusal_not_a_filter(), test_the_insert_tolerates_the_one_row_per_pick_index(), test_the_lane_can_actually_settle(), test_the_lane_refuses_a_quote_past_the_ceiling(), test_the_lock_is_scoped_by_player_not_just_by_game(), test_the_retired_model_carries_no_threshold_row() (+1 more)

### Community 527 - "NCAAF in-play odds history pull"
Cohesion: 0.24
Nodes (13): _blank_row(), _floor5(), _get(), _iso(), main(), planned_calls(), pull_day(), resolve_game_id() (+5 more)

### Community 529 - "tests/test_clear_unauthorized_auto_pauses_migration.py"
Cohesion: 0.19
Nodes (6): _stmts(), test_clearing_auto_pauses_did_not_park_batter_runs(), test_it_clears_the_whole_auto_pause_table(), test_it_does_not_touch_picks_thresholds_or_the_review_ledger(), test_it_no_ops_when_the_table_is_missing_or_already_empty(), test_migration_is_one_statement()

### Community 530 - "tests/test_ncaaf_se_louisiana_alias_migration.py"
Cohesion: 0.15
Nodes (4): test_a_pick_is_never_deleted_and_never_regraded(), test_it_guards_on_both_names_and_both_still_unscored(), test_migration_is_one_statement(), test_odds_move_only_when_canonical_has_none()

### Community 532 - "tests/test_overnight_polling.py"
Cohesion: 0.24
Nodes (7): _hours(), _jobs(), _match(), test_every_hour_of_the_day_is_covered(), test_the_overnight_pass_is_the_ordinary_one(), test_the_overnight_window_exists(), test_the_windows_do_not_overlap()

### Community 534 - "Mobile bankroll settings card"
Cohesion: 0.18
Nodes (20): fieldFlow(), inv(), bankrollDraft(), bankrollFieldText(), canonical(), checkBankroll(), commitBankrollText(), editBankrollInput() (+12 more)

### Community 535 - "NFL opener stake sizing and EV"
Cohesion: 0.09
Nodes (23): american_to_decimal(), cover_probs(), ev_per_unit(), fit_margin_pmf(), kelly_fraction(), margin_pmf_for(), add_model_mu(), load() (+15 more)

### Community 536 - "Mobile type-check baseline tests"
Cohesion: 0.29
Nodes (13): _entries(), _log(), _log_line(), _run(), test_a_clean_log_warns_for_every_baseline_entry(), test_a_compiler_crash_is_not_a_clean_run(), test_a_different_app_message_fails(), test_a_fixed_baseline_entry_warns_and_does_not_fail() (+5 more)

### Community 537 - "Model trainer and calibration metrics"
Cohesion: 0.06
Nodes (25): calibration_method(), _dispersion(), f(), _calibration_error_weighted(), calibration_metrics(), _count_cv_splits(), _gamma_shape(), _mean_calibration_error() (+17 more)

### Community 539 - "NFL prop lean concentration report"
Cohesion: 0.25
Nodes (7): add_context(), boot(), main(), profit(), report(), tercile_split(), under_profit()

### Community 541 - "Tracked performance verification script"
Cohesion: 0.10
Nodes (18): dup, empty, half, l50, loss, noAction, open1, open2 (+10 more)

### Community 543 - "Live monitor cache tests"
Cohesion: 0.15
Nodes (10): age(), cached(), clear(), test_cache_raises_when_it_has_nothing_to_fall_back_on(), test_cache_reports_age(), test_cache_serves_stale_rather_than_failing(), boom(), test_cache_serves_within_ttl_and_recomputes_after() (+2 more)

### Community 544 - "CLV no-vig close capture tests"
Cohesion: 0.20
Nodes (8): _fn(), test_a_missing_bet_book_close_is_not_filled_from_another_book(), test_backfill_revisits_anything_that_is_not_standard_v2(), test_capture_grades_raw_same_book_and_a_separate_pinnacle_edge(), test_capture_stamps_method_and_close_book(), test_game_close_never_falls_back_past_first_pitch(), test_pinnacle_is_a_second_lookup_not_the_headline_close(), test_prop_close_stays_bounded_at_first_pitch()

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

### Community 559 - "Odds prune protected sources tests"
Cohesion: 0.11
Nodes (10): ncaaf_line_bookmaker(), _unprotected(), test_prune_never_touches_cfbd_archive_lines(), test_the_prune_protects_every_ladder_source_by_its_writer_s_own_name(), test_the_two_prune_tiers_never_select_a_path_kept_sport(), test_cfbd_archive_prefix_is_protected(), test_historical_backfill_rows_are_protected_in_odds(), test_prop_table_has_no_source_column_so_no_source_clause() (+2 more)

### Community 561 - "NFL wind forecast validation"
Cohesion: 0.29
Nodes (10): build(), games(), hourly(), main(), _rate(), sec_coverage(), sec_error(), sec_rule() (+2 more)

### Community 563 - "Paused model profitability assessment"
Cohesion: 0.10
Nodes (15): _auto_paused_models(), active_era(), assess(), _half(), fetch(), grade(), main(), sweep() (+7 more)

### Community 565 - "NCAAF quarterback ablation study"
Cohesion: 0.28
Nodes (7): _fit(), main(), _report(), run(), summarise(), walk_forward(), wilson()

### Community 568 - "NFL opener cut sweep and calibration"
Cohesion: 0.16
Nodes (8): _load_backtest(), main(), selected_bets(), boot_ci(), candidate_rows(), _load_backtest(), main(), select()

### Community 569 - "NBA in-game study one tests"
Cohesion: 0.17
Nodes (15): _pin(), _q(), _rows(), _state(), test_every_fit_for_season_s_uses_earlier_seasons_only(), test_expected_rates_use_the_teams_earlier_dates_only(), test_ig1_bets_against_luck_and_the_control_with_it(), test_luck_counts_a_three_three_times_and_a_free_throw_once() (+7 more)

### Community 571 - "MLB backfill retry resilience tests"
Cohesion: 0.12
Nodes (6): test_a_failed_date_does_not_end_the_run_and_is_left_unmarked(), test_a_transient_network_error_is_retried(), test_an_http_error_is_NOT_retried(), test_it_gives_up_rather_than_looping_forever(), test_skip_existing_is_on_by_default(), test_the_resume_marker_distinguishes_historical_from_live_rows()

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

### Community 576 - "NCAAF situational spot evaluation"
Cohesion: 0.26
Nodes (5): build_spots(), evaluate(), load_team_games(), main(), wilson()

### Community 577 - "NBA period score ingestion"
Cohesion: 0.19
Nodes (13): ensure_table(), fetch_date(), _int(), main(), parse_period_rows(), run(), write(), _event() (+5 more)

### Community 580 - "scripts/render_brand_icons.py"
Cohesion: 0.24
Nodes (3): draw_mark(), main(), render()

### Community 582 - "Results recap NFL box score ordering"
Cohesion: 0.17
Nodes (8): _daily(), _job_body(), test_a_malformed_date_is_refused_before_anything_runs(), test_nfl_box_scores_are_ingested_before_settle(), test_nfl_finals_still_precede_the_box_scores(), test_the_job_does_not_read_rowcount_off_the_cursor(), test_the_job_only_clears_its_own_two_ledger_kinds(), test_the_job_posts_both_surfaces_through_the_ordinary_paths()

### Community 584 - "Mobile line ruler checks"
Cohesion: 0.32
Nodes (8): _read(), _slice(), test_a_bubble_tap_does_not_clear_the_tick_guard_in_the_same_turn(), test_blur_commits_and_the_clamp_is_announced_once(), test_cancel_scrolls_the_strip_back_and_does_not_change_the_board(), test_cancel_wins_when_blur_fires_before_the_click(), test_talkback_can_activate_the_bubble(), test_verify_line_ruler_script()

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

### Community 595 - "NFL model import checks"
Cohesion: 0.15
Nodes (6): _import_under_scheduler_env(), _scheduler_env(), test_no_nfl_script_uses_the_bare_models_import(), test_the_card_imports_under_the_schedulers_invocation(), test_the_exemption_is_the_loader_and_it_still_exists(), test_the_loader_reaches_nfls_models_not_the_platforms()

### Community 596 - "NBA ESPN box score parsing"
Cohesion: 0.08
Nodes (24): box_team_totals(), et_date(), nba_team(), _no_minutes(), parse_nba_box(), parse_nba_dnp(), parse_nba_postponed(), parse_nba_scoreboard() (+16 more)

### Community 60 - "tests: test_wnba_availability + wnba_availability"
Cohesion: 0.10
Nodes (33): absence_features(), absent_teammates(), build_context_features(), expected_rotation(), is_starter_tier(), _mean(), prior_rows(), recent_team_game_dates() (+25 more)

### Community 600 - "Mobile stat segment tabs tests"
Cohesion: 0.20
Nodes (10): _read(), test_one_shared_defensive_set(), test_position_is_never_inferred_from_stats(), test_runs_in_pr_ci(), test_search_and_position_review_fixes(), test_segment_labels_cap_only_on_fit(), test_tabs_speak_the_visible_label_not_the_key(), test_the_behavioural_checks_pass() (+2 more)

### Community 601 - "NBA injury report time slots"
Cohesion: 0.16
Nodes (10): _ampm(), new_slot(), old_slot(), pre_tip_slot(), slots_for_date(), test_format_switch_is_measured_and_both_are_probed_around_it(), test_hourly_dates_get_sixteen_hourly_slots(), test_pre_tip_slot_is_strictly_before_the_tip() (+2 more)

### Community 606 - "NCAAF play-by-play history puller"
Cohesion: 0.19
Nodes (7): _extremes(), fetch_season(), _get(), main(), observed_ranges(), pull_season(), test_the_scan_survives_nulls_and_non_numeric_cells()

### Community 608 - "supabase/functions/sharpsports-webhook: index + index"
Cohesion: 0.25
Nodes (5): internalIdFor(), pick(), admin, admin, cors

### Community 609 - "Mobile Lines board pin tests"
Cohesion: 0.22
Nodes (9): _read(), test_a_missing_draw_price_is_remembered(), test_lines_board_pins_are_on_the_pr_ci_subset(), test_lines_is_a_picks_view(), test_the_behavioural_checks_pass(), test_the_board_reloads_when_the_et_date_changes(), test_the_lines_read_names_the_view_and_pages(), test_the_lines_segment_is_unconditional_and_after_live() (+1 more)

### Community 61 - "X post publisher and database key checks"
Cohesion: 0.03
Nodes (54): main(), scram_stored_key(), discover(), fetch_all(), _get_image(), main(), _original_size(), store() (+46 more)

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
Nodes (60): assemble(), _assert_spread_sign(), attach_close(), bars(), bet_frame(), blind_bets(), blind_first_fetch(), boot_ci() (+52 more)

### Community 620 - "NHL totals research lab"
Cohesion: 0.26
Nodes (8): grade(), imp(), interval(), load(), main(), row(), show(), wpu()

### Community 622 - "UFC stats page parsing"
Cohesion: 0.10
Nodes (23): _height_to_inches(), _int_or_none(), _mmss_to_sec(), _of_pair(), _parse_dob(), _parse_event_date(), parse_event_list(), parse_event_page() (+15 more)

### Community 626 - "In-play honest cut sweep"
Cohesion: 0.33
Nodes (9): bets_split(), _fmt(), _grid(), main(), _print_grid(), run_mlb(), run_ncaaf(), _summ() (+1 more)

### Community 628 - "NCAAF weather totals study"
Cohesion: 0.23
Nodes (6): build_spots(), evaluate(), load_games(), main(), scoring_by_wind(), wilson()

### Community 629 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.47
Nodes (6): contentHeight(), evalExpr(), lineOf(), styleBlock(), styleProp(), visualHeight()

### Community 63 - "Football in-play game state"
Cohesion: 0.12
Nodes (18): _as_float(), _as_int(), _as_opt_float(), _as_opt_int(), from_espn(), from_extract(), from_pbp_row(), smooth_pass_rate() (+10 more)

### Community 631 - "Mobile team total tests"
Cohesion: 0.24
Nodes (6): _run(), test_a_move_off_the_deciding_book_s_number_is_against_the_bet(), test_the_line_movement_card_shows_the_team_total_line(), test_the_model_has_its_own_chip_and_no_picker_slot(), test_the_pick_reads_the_home_team_total_market_and_its_number(), test_the_team_page_leaves_the_team_total_out_of_every_tile()

### Community 632 - "NFL in-play prop dataset and calibration"
Cohesion: 0.09
Nodes (18): evaluate(), _infer_position(), main(), _pool_prior(), report(), _rows_for_market(), _to_states(), accrual_at() (+10 more)

### Community 634 - "Pipeline watch freshness findings"
Cohesion: 0.11
Nodes (11): test_a_clean_pass_produces_no_finding(), test_a_fresh_sweep_and_savant_produce_no_finding(), test_a_missing_sweeps_table_is_reported_not_swallowed(), test_a_pass_with_failed_steps_is_reported(), test_a_pass_with_no_finish_is_reported_without_over_reading_it(), test_a_stale_sweep_date_is_reported(), test_an_occasional_kind_is_not_flagged_for_being_quiet(), test_savant_with_only_one_player_type_is_stale_even_when_dated_today() (+3 more)

### Community 635 - "tests/test_demote_ncaaf_over_under_platt.py"
Cohesion: 0.32
Nodes (4): _stmts(), test_it_demotes_only_the_measured_promotion(), test_it_does_not_move_the_gate_the_floor_or_a_pause(), test_migration_is_one_statement()

### Community 636 - "Model quality degradation monitor"
Cohesion: 0.08
Nodes (22): record_exclusion_sql(), test_clv_clear_negative_vs_baseline_is_flagged(), test_raw_one_sided_clv_is_ignored(), test_roi_collapse_is_crit_when_hit_rate_dies(), test_roi_ignores_unpriced_profit_flat(), test_volume_spike_vs_median(), test_the_exclusion_sql_is_a_conjunction_of_negations(), _job_model_quality() (+14 more)

### Community 637 - "tests/test_discord_post_one_pick_migration.py"
Cohesion: 0.29
Nodes (3): _pairs(), test_it_names_each_measured_extra_and_the_row_kept(), test_the_update_does_not_rewrite_the_graded_outcome()

### Community 638 - "tests/test_game_scorer_spares_nfl_props.py"
Cohesion: 0.43
Nodes (5): _between(), _run_scorer_body(), test_an_nfl_game_never_enters_the_per_game_clear(), test_both_live_non_bet_clears_leave_nfl_rows(), test_the_left_out_ufc_clear_only_removes_unsettled_non_bets()

### Community 641 - "Mobile quiet update download tests"
Cohesion: 0.17
Nodes (8): _code_only(), _read(), test_a_downloaded_update_is_announced_quietly_once(), test_app_root_mounts_the_ota_updater(), test_every_trigger_only_downloads(), test_nothing_in_the_app_reloads_a_running_app(), test_the_pieces_exist(), test_the_updater_downloads_the_update()

### Community 642 - "NBA team total luck replay tests"
Cohesion: 0.18
Nodes (6): art(), ld(), results(), test_the_artifact_holds_the_lab_s_team_total_residuals_in_order(), test_the_live_code_reproduces_the_lab_game_for_game(), test_the_live_home_parts_are_the_independent_lab_copy_s()

### Community 645 - "NFL prop week one candidate pool"
Cohesion: 0.22
Nodes (5): partially_played_week_one(), _player_row(), _team_row(), test_a_clean_week_one_is_unchanged(), test_teams_still_to_play_keep_a_candidate_pool()

### Community 647 - "NFL Kalshi price history fetch"
Cohesion: 0.21
Nodes (6): candles(), get(), map_games(), paged(), parse_event(), probe()

### Community 649 - "MLB totals public fade card"
Cohesion: 0.10
Nodes (19): edge_floor(), max_per_slate(), publish_enabled(), rank_kind(), ticket_threshold(), under_odds_band(), main(), pick_rows() (+11 more)

### Community 65 - "NBA prop model research lab"
Cohesion: 0.07
Nodes (46): books(), p_over(), settle_value(), _agg(), apply_rule(), binary_baselines(), binary_indep(), blind_same() (+38 more)

### Community 650 - "Mobile stats filter UX verify"
Cohesion: 0.17
Nodes (10): board, chip, lineOnlyFn, playersDay, ROOT, sportReset, stats, teams (+2 more)

### Community 653 - "NFL prop pulled quote filter"
Cohesion: 0.32
Nodes (8): drop_pulled_quotes(), _ts(), _q(), test_a_book_on_its_own_cadence_is_not_penalised_inside_three_hours(), test_a_book_that_stopped_returning_the_game_is_dropped(), test_a_player_the_book_stopped_quoting_is_dropped(), test_a_whole_market_the_book_pulled_is_dropped(), test_rows_from_one_fetch_minutes_apart_are_kept_and_a_line_move_is_not_a_pull()

### Community 655 - "NBA injury report PDF layout parser"
Cohesion: 0.18
Nodes (7): _bands(), _column_of(), _columns(), _hrules(), _lines_of(), parse_page_layout(), _text()

### Community 656 - "Pipeline watch silence and regressions"
Cohesion: 0.29
Nodes (4): test_the_silence_finding_says_how_regular_the_kind_was(), _rows(), _silent_kinds(), _step_regressions()

### Community 658 - "NFL prop too-early kickoff ceiling"
Cohesion: 0.30
Nodes (8): _nfl_prop_too_early(), _iso(), test_a_kickoff_beyond_the_ceiling_is_too_early(), test_a_started_or_unknown_kickoff_is_not_too_early(), test_the_boundary_is_inclusive_at_the_ceiling(), test_the_scorer_and_the_card_read_ONE_constant(), test_the_scorer_loop_actually_applies_the_ceiling(), test_the_z_suffix_parses_like_the_offset_form()

### Community 660 - "NBA injury report player matching"
Cohesion: 0.17
Nodes (7): match_player(), _near_season(), remap_changes(), _surname_key(), test_a_name_printed_differently_matches_on_surname_and_initial_within_the_team(), test_player_ids_match_on_team_first_then_a_unique_season_name(), test_remap_rewrites_only_names_whose_id_changed()

### Community 662 - "NFL wind stake past calibration tests"
Cohesion: 0.22
Nodes (6): _probe(), test_an_uncalibrated_lead_is_sized_rather_than_zeroed_on_the_card(), test_at_the_default_gate_that_same_row_does_not_fire_at_all(), test_the_eval_board_agrees_with_the_card(), test_the_probability_was_already_clipping(), test_the_stake_clips_to_lead_seven_instead_of_returning_zero()

### Community 663 - "NFL kickoff-hour live wind readings"
Cohesion: 0.26
Nodes (5): attach_live_wind_reads(), _connect(), _current(), _utc(), _with_current()

### Community 665 - "Threshold sweep price floor tests"
Cohesion: 0.29
Nodes (7): _apply_price_floor(), _row(), test_a_model_with_no_floor_is_untouched(), test_every_prop_model_in_the_sweep_has_a_floor_to_apply(), test_plus_money_always_survives(), test_prices_juicier_than_the_floor_are_dropped(), test_the_boundary_matches_the_scorer()

### Community 667 - "NCAAF prop market rule sweep"
Cohesion: 0.26
Nodes (7): candidates(), dedupe(), grade(), load_board(), main(), norm(), profit()

### Community 668 - "NFL prop market stacking studies"
Cohesion: 0.08
Nodes (29): closing_prices(), devig(), ecdf_p_over(), main(), bets(), design(), main(), analyse() (+21 more)

### Community 669 - "NFL 2026 track policy pins"
Cohesion: 0.24
Nodes (8): _src(), test_config_comments_state_the_policy(), test_live_cuts_did_not_move(), test_max_fire_lead_stays_four_in_the_live_model(), test_paused_xgb_props_stay_paused(), test_the_script_does_not_write_thresholds_or_units(), test_tracking_doc_names_the_command_and_the_criteria(), test_units_stay_at_one_percent_on_both_cards()

### Community 670 - "NCAAF in-play model re-sweep"
Cohesion: 0.27
Nodes (6): attach(), first_signals(), load(), main(), summarise(), wilson()

### Community 673 - "Scorer keeps off-DraftKings priced bets tests"
Cohesion: 0.29
Nodes (6): _bet(), db(), _left(), _statement(), test_a_bet_priced_at_another_books_line_survives_and_a_bet_with_no_price_does_not(), test_the_statement_names_both_prices()

### Community 677 - "Historical odds file loader"
Cohesion: 0.25
Nodes (3): canonical_abbrev(), parse_csv_file(), test_sbr_abbreviations_are_canonicalised_for_mlb_only()

### Community 679 - "NCAAF structural spot scan"
Cohesion: 0.21
Nodes (3): load_data(), main(), scan_spot()

### Community 689 - "Live model grouped cross-validation"
Cohesion: 0.20
Nodes (5): _memorisable_plays(), test_game_ids_sort_chronologically(), test_groups_default_to_none_so_ungrouped_callers_are_unchanged(), test_the_live_trainer_passes_game_ids(), test_ungrouped_cv_scores_a_lookup()

### Community 692 - "NCAAF in-play history credit sharding"
Cohesion: 0.22
Nodes (6): budget_for(), calls_in(), parse_shard(), shard_windows(), test_a_bad_shard_spec_is_refused(), test_shard_parsing_and_splitting_is_round_robin_and_total()

### Community 694 - "Social post client tests"
Cohesion: 0.20
Nodes (5): _creds(), test_a_5xx_is_transport_and_not_a_tweet_id(), test_a_missing_table_is_a_no_op(), test_allow_link_is_off_on_the_pick_client(), _post()

### Community 695 - "Every named sportsbook is fetched"
Cohesion: 0.18
Nodes (5): _param_books(), test_a_sharp_reference_is_never_also_a_soft_book(), test_every_bettable_book_can_be_named_to_a_human(), test_every_named_book_is_in_the_pull_that_serves_it(), test_the_nfl_backfill_defaults_to_the_live_pull()

### Community 697 - "Duplicate pick copy exclusion"
Cohesion: 0.22
Nodes (6): duplicate_copy_exclusion_sql(), test_the_discord_recap_counts_each_event_once(), test_the_finder_skips_copies_already_marked(), test_the_marker_is_one_constant_and_one_predicate(), test_the_monitor_dashboard_box_score_arm_counts_each_event_once(), test_the_monitor_dashboard_picks_arm_counts_each_event_once()

### Community 700 - "NBA harness cell emission fakes"
Cohesion: 0.22
Nodes (6): _emit_world(), _spy_run_cells(), test_closing_value_is_priced_with_the_markets_empirical_distribution(), test_every_family_emits_exactly_its_cells_through_the_harness(), test_the_d_cells_are_gated_on_the_points_own_decision_times(), test_the_bootstrap_is_seeded_and_refines_small_p()

### Community 704 - "NFL prop local cache pull"
Cohesion: 0.33
Nodes (5): main(), _merge_with_cache(), _pull_odds(), _pull_seasoned(), _register_from_feature_engine()

### Community 71 - "MLB in-play inning gate replay"
Cohesion: 0.03
Nodes (93): should_fetch(), split_triggers(), under_credit_cap(), build_live_state_row(), apply_daily_cap(), classify_live_signal(), _ev_floor(), expected_value() (+85 more)

### Community 711 - "Mobile NHL look-ahead window tests"
Cohesion: 0.29
Nodes (5): _fn(), _read(), test_the_nhl_read_matches_the_other_look_aheads(), test_the_sport_chip_is_the_hook_not_an_allowlist(), test_use_today_picks_fetches_nhl_across_that_window()

### Community 712 - "NBA public betting splits ingestion"
Cohesion: 0.17
Nodes (9): an_pct(), parse_v1_sides(), v1_consensus_row(), test_a_one_percent_side_is_not_inflated_to_100(), test_out_of_range_or_junk_percentages_are_refused(), test_v1_flat_fields_map_to_market_side_and_metric(), test_v1_reads_only_the_consensus_book(), test_v1_rows_carry_the_inserted_stamp_and_its_lag() (+1 more)

### Community 713 - "NBA injury report name normalising"
Cohesion: 0.22
Nodes (7): name_first_last(), norm_name(), _row(), team_code(), test_name_key_drops_accents_punctuation_and_suffixes(), test_names_turn_round_with_their_suffix_on_the_surname(), test_team_names_map_to_our_codes()

### Community 714 - "NBA public splits quality flags"
Cohesion: 0.29
Nodes (4): quality_backfill_statements(), quality_flag(), test_the_quality_rule_puts_reversed_ahead_of_late(), test_the_stored_row_backfill_flags_exactly_what_the_rule_flags()

### Community 716 - "Parlay leg correlation estimates"
Cohesion: 0.36
Nodes (5): estimate(), estimate_basketball(), estimate_mlb(), main(), _median()

### Community 717 - "Eastern time game date tests"
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

### Community 74 - "Prop CLV and SQL escaping tests"
Cohesion: 0.05
Nodes (28): _is_main_guard(), _modules_with_guard(), test_at_least_one_entrypoint_is_scanned(), test_nothing_is_defined_after_the_main_guard(), test_the_backfill_queues_the_dates_of_those_picks(), _fn(), test_a_backfill_failure_never_breaks_settlement(), test_a_pick_is_only_stamped_captured_once_a_measure_resolved() (+20 more)

### Community 75 - "NCAAF margin and totals evaluation"
Cohesion: 0.08
Nodes (28): margin_cover_prob(), build_frames(), _fit(), fit_and_register(), fit_and_register_totals(), main(), _matrix(), _print_sweep() (+20 more)

### Community 82 - "Mobile error states and books tests"
Cohesion: 0.06
Nodes (35): tsx_cmd(), _load_state_dir(), _raw_error_lines(), _read(), _run_node(), test_aborts_are_silent_and_offline_slow_are_narrow(), test_aborts_render_nothing_and_every_catch_skips_them(), test_designer_review_fixes_behaviour() (+27 more)

### Community 849 - "NFL 2024 in-play replication tables"
Cohesion: 0.18
Nodes (13): families(), fit_models(), fmt(), main(), parse_2025_output(), pooled_table(), replication(), repro_check() (+5 more)

### Community 850 - "Shared database and config helpers"
Cohesion: 0.01
Nodes (162): _connect(), _convert_params(), _convert_params_outside_literals(), get_connection(), _open(), _session_options(), setup_database(), use_poller_session() (+154 more)

### Community 851 - "NHL derivative totals card"
Cohesion: 0.40
Nodes (3): main(), run(), test_card_writes_nothing_and_the_pipeline_does_not_call_it()

### Community 853 - "No record-only mode guard tests"
Cohesion: 0.43
Nodes (4): _allowed(), _hits(), _rel(), test_the_repo_has_no_record_only_or_paper_tracking_mode()

### Community 856 - "MLB public fade top-k backtest"
Cohesion: 0.12
Nodes (18): american_units(), bucket_win_rates(), build_candidates(), _fmt(), grade_under(), holdout_take(), load_db(), load_json() (+10 more)

### Community 86 - "NFL QB wind and NBA in-game tests"
Cohesion: 0.04
Nodes (98): test_baselines_never_see_the_game_they_price(), load_games(), main(), pivot_spreads(), pivot_totals(), load_games(), main(), wide_spreads() (+90 more)

### Community 867 - "Manual X posts runbook"
Cohesion: 0.29
Nodes (7): pin(), How to enqueue a post with an image, How to enqueue another post or thread, Manual posts to @SignalBasePicks, Pinning, What is already queued, What the drain will not do

### Community 868 - "NFL live pick game date resolution"
Cohesion: 0.25
Nodes (3): test_a_night_game_pick_carries_the_game_s_date_not_the_utc_clock(), test_nothing_written_means_nothing_announced(), test_resolution_refuses_rather_than_guesses()

### Community 87 - "NHL box score parsing"
Cohesion: 0.09
Nodes (25): _decision(), fill_missing(), _insert_absent(), _int(), _name(), parse_boxscore(), side_rows(), store_boxscore() (+17 more)

### Community 875 - "Calibration watch sweep queries"
Cohesion: 0.25
Nodes (4): auto_pause_caveat(), _sweep(), _sweep_dates(), query_rows()

### Community 876 - "NBA play-by-play clock parsing"
Cohesion: 0.40
Nodes (3): parse_clock(), test_field_goal_value(), test_parse_clock()

### Community 877 - "NBA public splits game dating"
Cohesion: 0.29
Nodes (5): et_game_date(), _game_meta(), team_abbr(), test_a_late_west_coast_tip_belongs_to_the_previous_et_date(), test_team_ids_come_from_the_abbr_then_the_full_name()

### Community 881 - "Rich market handicap feature builder"
Cohesion: 0.29
Nodes (4): build_rich_handicap(), _fav_signed_home_move(), _gated_flag(), _mul()

### Community 887 - "NFL in-play prop publish refusal"
Cohesion: 0.29
Nodes (4): refuse_publish_reason(), test_refuse_publish_allows_a_real_rush_under(), test_refuse_publish_blocks_pass_attempt_overs(), test_refuse_publish_blocks_the_constant_prob_fingerprint_even_on_rush()

### Community 89 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.03
Nodes (50): a11ySrc, allowHit, ALLOWLIST, app, badExempt, bar, bareClose, baselineLeft (+42 more)

### Community 892 - "Market coverage probe candidates"
Cohesion: 0.33
Nodes (5): candidate_markets(), _standard_markets(), test_it_asks_about_the_board_columns_that_are_permanently_blank(), test_no_market_is_asked_about_twice(), test_the_probe_asks_about_every_market_we_pull_and_its_alternate()

### Community 896 - "Opening versus closing strategy analysis"
Cohesion: 0.43
Nodes (4): _fmt(), _profit_sql(), _row(), strategy_analysis()

### Community 897 - "Pipeline credit burn findings"
Cohesion: 0.25
Nodes (4): test_burn_is_judged_against_the_cap_not_against_yesterday(), test_burn_survives_a_non_numeric_credits_column(), test_failed_api_calls_are_reported_even_when_burn_is_low(), findings_from_burn()

### Community 899 - "NBA game projection consensus gap tests"
Cohesion: 0.40
Nodes (6): _cons(), _neutral(), test_f1b_does_not_score_a_books_number_off_the_consensus(), test_f1b_strength_is_the_predicted_move_in_the_sides_favour(), test_the_f5_gap_is_measured_against_the_consensus_not_each_books_number(), test_the_f5_gap_reads_the_home_number()

### Community 900 - "Pipeline watch announce and escalation"
Cohesion: 0.29
Nodes (3): test_a_missing_webhook_escalates_rather_than_vanishing(), _announce(), _announce_and_ledger()

### Community 904 - "NBA team total feed test patching"
Cohesion: 0.40
Nodes (3): fn(), logged(), call()

### Community 907 - "NCAAF college stats payload parsing"
Cohesion: 0.08
Nodes (22): _int(), _num(), parse_advanced_stats(), parse_ratings(), parse_returning(), parse_season_stats(), parse_talent(), parse_team_game_stats() (+14 more)

### Community 909 - "NHL goalie save rate regression"
Cohesion: 0.83
Nodes (4): _goalie_line(), regressed(), saved_above(), tot()

### Community 91 - "NFL in-play backtest replay harness"
Cohesion: 0.05
Nodes (34): align_states(), build_team_map(), _game_index(), kill_verdict(), load_cached_snapshots(), main(), replay(), _settle() (+26 more)

### Community 912 - "NBA public splits row building tests"
Cohesion: 0.09
Nodes (26): build_rows(), clean_pair(), match_game(), parse_v2_sides(), _entry(), test_a_late_tip_matches_its_et_dated_game_id(), test_a_lone_side_is_kept_as_served(), test_a_pair_that_does_not_sum_to_100_is_dropped() (+18 more)

### Community 93 - "MLB totals public fade tests"
Cohesion: 0.11
Nodes (30): find_fade_bets(), is_pre_commence(), select_latest_pre_commence_over(), under_in_odds_band(), _dk_board(), _quote(), _quotes(), _slate() (+22 more)

### Community 98 - "NBA play-by-play ingestor"
Cohesion: 0.05
Nodes (51): active_queries(), alias_map_rows(), _bool(), box_context(), box_finals(), build_game(), build_gap_game(), build_map() (+43 more)

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

### Community 880 - "NBA play-by-play lineup stints doc"
Cohesion: 0.29
Nodes (6): Commands, How a stretch is built (each rule is pinned by a test that was watched to fail), NBA play-by-play and on-court lineup segments, Source, Things a reader should know, What was loaded, and the checks (re-measured 2026-10-17 on production, after the rebuild)

### Community 882 - "Mobile developer tooling dependencies"
Cohesion: 0.29
Nodes (7): devDependencies, @babel/core, babel-plugin-module-resolver, babel-preset-expo, tsx, @types/react, typescript

### Community 929 - "Opening signals shadow table"
Cohesion: 0.70
Nodes (4): idx_opening_signals_date, idx_opening_signals_model, idx_opening_signals_settle, opening_signals

### Community 930 - "In-app feedback thread tables"
Cohesion: 0.40
Nodes (5): feedback_messages, feedback_threads, idx_feedback_messages_thread, idx_feedback_threads_device, idx_feedback_threads_status

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

### Community 411 - "NFL prop over-lean research docs"
Cohesion: 0.11
Nodes (13): The live prop market leans over like the pre-game one, Publish backstop refuses pass-attempt overs, Accrued carries from ESPN core leaders, rush_attempt_pace model: one offset on the book's number, Pace ratio, In-play rushing-attempt UNDER on pace ratio >= 1.25, NFL prop lines lean over, NFL edge search 2026-10-11 (+5 more)

### Community 420 - "mobile/docs/UX_REVIEW.md"
Cohesion: 0.16
Nodes (13): dashboard.html renderRoster(), A pick is a pick (re-priced line never replaces the locked one), Copy: formatAmerican/formatPct/formatCurrency, model ids never raw, Decided at the best bettable price; read via lib/decisionPrice.ts, frontend-ux-designer agent contract, Mobbin MCP connector (one route: Matt's claude.ai connector), Product rules: a violation is a Blocker, Reuse before invention (EmptyState, StatTile, SignalBadge, ...) (+5 more)

### Community 432 - "Model quality monitor and MLB totals docs"
Cohesion: 0.04
Nodes (35): Hybrid Pin-agreement filter on mlb_over_under bets, mlb_runline and mlb_over_under (paused), mlb_total_public_fade card (paper UNDER), Slate concentration guard (insert-time), F5 odds coverage (DK carries F5 ML only), clv_degradation check, model_quality_checks table, Daily model-quality monitor (+27 more)

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

### Community 463 - "Probability calibration design notes"
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

### Community 558 - "Model artifact and health docs"
Cohesion: 0.24
Nodes (10): model_artifacts_load counts what it opened, model_artifacts table fallback restore, Three separate artifact questions, three separate failures, KNOWN_UNTRAINED — config models intentionally without artifacts, Pipeline-observability checks: refresh_pass_completion, refresh_pass_steps, signal_delivery, pick_label_integrity, pipeline_runs — the run ledger (tracking/run_ledger.py), Retrain Model workflow (retrain_model.yml), tracking/system_health.py — CRIT and WARN feed checks (Step 12) (+2 more)

### Community 560 - "docs/retrain_2026_plan.md"
Cohesion: 0.18
Nodes (13): scripts/paused_model_assessment, data.ingestors.baseball_savant_ingestor, models.trainer, anytime_td verdict: inert, not losing, F5 O/U and F5 RL paused: leak-mismatched, synthetic-line trained, NCAAF in-play season replay: -3.4% and -13.1%, No model has a cut that clears on the deployed artifact, batter_sb: opp_team_sb_allowed feature (+5 more)

### Community 594 - "Calibration and NFL wind opener tracking docs"
Cohesion: 0.16
Nodes (18): tracking.paper_tracker (_NFL_MODEL_MARKETS), scripts/nfl_rule_2026_track, tracking/opening_signals.capture_opening_signals, tracking.opening_report, tracking/opening_signals.settle_opening_signals, MAX_FIRE_LEAD = 4, nfl_opener_spread, nfl_wind_totals (+10 more)

### Community 603 - "docs/reviews/2026-09-07-nfl-props-deep-dive.md"
Cohesion: 0.33
Nodes (7): Twelve artifacts committed from a replica failed pickle.load unnoticed for two weeks, The eleven NFL projection prop models, unpaused on placeholder thresholds, nfl_prop_market: the de-vig rule (Pinnacle as truth, equal lines only), The scorer is pinned to today, the card looks ten days ahead, 112 bets on one Sunday from untuned models; 41-46% BET rates are placeholders, Eleven NFL distributional props paused 2026-09-14, NFL props deep dive — two lanes, one of them can't see the slate (2026-09-07)

### Community 627 - "docs/market_coverage.md"
Cohesion: 0.36
Nodes (7): ncaaf_prop_odds_ingestor and its probe, test_the_mlb_board_and_the_mlb_pull_are_one_set, MLB probe 2026-09-05 — served, unsupported and unpriced keys, NCAAF prune — FOOTBALL_MARKET_NOT_PRICED per league, scripts/probe_market_coverage.py — one market per call, writes nothing, Neither prop ingestor writes to api_call_log, Prop market coverage — what the feed actually serves

### Community 652 - "(root): pr-ci + requirements"
Cohesion: 0.33
Nodes (5): Mobile thresholds drift check (generate_mobile_thresholds --check), NFL preflight --ci, PR CI workflow — non-integration pytest subset, Render blueprint — betting-scheduler background worker, requirements.txt — >= pins for Python 3.14 wheels

### Community 66 - "NFL props sources and prediction market research"
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

### Community 755 - "Model research findings docs"
Cohesion: 0.04
Nodes (44): scripts/ncaaf_search/, Live inning gate replay, Live feature sensitivity (12.8pp median swing), mlb_live_total_runs (in-play total), Negative-binomial (NB1) tail, pregame_total_line feature (market anchor), ncaaf_live_total 2025 in-play backtest, ncaaf_live_win_prob 2025 in-play backtest (+36 more)

### Community 81 - "docs: nhl_market_lab + nhl_clv_ev_assessment"
Cohesion: 0.08
Nodes (39): nhl_research worker job, scripts/nhl_derivative_totals_backtest, data/ingestors/nhl_derivative_odds_history, models/nhl_props.py (Spec per market), Anytime goalscorer: not a candidate once names corrected, nhl_moneyline and nhl_moneyline_regulation: no cut clears, Game models: lock later? Refuted, nhl_over_under live as a market-anchored rule (models/nhl_totals_market.py) (+31 more)

### Community 890 - "docs/game_injury_gate.md"
Cohesion: 0.40
Nodes (5): ESPN core probables for the NHL starting goalie, A NONE from this gate is not locked — the reprice path, The gate rule — refuse a game-model BET on a confirmed Out starter/star/goalie, Fires in scorer.score_game and _score_nhl_3way, after best-price requalify, before insert, Game-model starter / star / goalie gate

## Ambiguous Edges - Review These
- `Claim: the app cannot write to the backend` → `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`  [AMBIGUOUS]
  docs/privacy.html · relation: conceptually_related_to

## Knowledge Gaps
- **105 isolated node(s):** `RFC-4122`, `expo/tsconfig.base`, `@babel/core`, `babel-plugin-module-resolver`, `babel-preset-expo` (+100 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 12209 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **210 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Table` connect `NBA public splits pipeline step` to `Mobile contrast tones and range slider`, `Scratch Postgres line state tests`?**
  _High betweenness centrality (0.200) - this node is a cross-community bridge._
- **What connects `RFC-4122`, `expo/tsconfig.base`, `@babel/core` to the rest of the system?**
  _105 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Mobile app screens and theme` be split into smaller, more focused modules?**
  _Cohesion score 0.01667634490254761 - nodes in this community are weakly interconnected._
- **Why does `over()` connect `Mobile contrast tones and range slider` to `Mobile bankroll math and copy`, `NBA public splits pipeline step`?**
  _High betweenness centrality (0.171) - this node is a cross-community bridge._
- **Should `Mobile picks home filters and sorting` be split into smaller, more focused modules?**
  _Cohesion score 0.022946268169198106 - nodes in this community are weakly interconnected._
- **Why does `inserted_minus_start_min()` connect `NBA public splits pipeline step` to `NBA public splits row building tests`, `NBA public betting splits ingestor`?**
  _High betweenness centrality (0.113) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Claim: the app cannot write to the backend` and `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._