# Graph Report - bm-nba-alt  (2026-10-24)

## Corpus Check
- Large corpus: 1714 files · ~2,857,656 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 34450 nodes · 82482 edges · 1079 communities (820 shown, 259 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 2182 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `46dc923a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Mobile app shell and feedback
- Mobile picks home filters and sorting
- Mobile stats board
- NFL poll fast silence tests
- NHL returning goalie name lookup
- Retired umpire features at retrain
- NHL opening night goalie lookup
- Umpire step on every refresh pass
- Line change push alerts
- Game schedule start context
- Unrated FBS opponent reporting
- NHL prop fetch staleness guards
- NHL early season as-of rule
- NFL live leader fake client
- Line shop pick qualification tests
- NHL stale teams schedule context
- NBA harness residual distribution
- Local database schema split
- NFL wind publisher lock tests
- Weather totals and NFL edge research
- Player news ingestor tests
- Prop scoring look-ahead dates
- NBA book numbers and game four search
- NBA injury report fake cursor
- College football in-play test connection
- Void tool refuses bare runs
- Best line price shopping tests
- Mobile stats odds and line legs
- tests/test_nfl_live_leader_gameday.py
- NFL live leader gameday cadence
- tests/test_calibration_promotion.py
- tests/test_score_off_any_book_line.py
- Alternate prop line fetching tests
- tests/test_backtester.py
- Mobile daily results summary
- NFL in-play gameday worker loop
- NBA prop market lab
- Discord pick notifier tests
- nfl/live_model/tests/test_backup_snaps.py
- mobile/scripts: verify_book_links + verify_betslip_combine
- Football gameday loops and push alerts
- NBA team total under model tests
- X post queue drain tests
- Kalshi prop ladder ingestion and bets
- tests/test_health_pregame_prices_current.py
- Pick lock survives settlement tests
- NBA game line move study
- MLB game market bet finder tests
- Discord full record correction posts
- X post publisher tests
- Threshold review and coverage probe
- UFC phantom fight filter
- NBA game model prop feature tests
- NFL prop market research scripts
- Mobile all-books lines board
- Discord void notice sender
- NFL prop odds loader tests
- NFL opener held minutes tests
- NHL stats, goalies and prop card
- Mobile crash logging
- NFL prop backtest and odds tests
- NBA game model luck feature tests
- Mobile preferred sportsbooks
- Discord publisher run lock
- tests/test_credit_budget.py
- Closing line value at price taken
- NHL goalie guards on prop cards
- Odds pruning keeps openers and closes tests
- NFL player and team stat parsing
- X profile update queue
- Odds pruning budget and sharp-book carve-out
- Market-relative prop bet finder tests
- tests/test_first_signal_repair.py
- Daily pipeline and stats ingestors
- Mobile markets and formatting
- Model calibration sweep tests
- Discord void notices and embeds
- NHL goalie as-of lookup
- NBA total luck replay studies
- NFL in-play game state feed
- Mobile color contrast checker
- Mobile record hero and equity curve
- Mobile paywall billing and account access
- Mobile bankroll tracker
- NCAAF live score distribution
- Idle database read transaction tests
- NHL market-anchored moneyline model
- In-play score change quote guard
- API call monitoring probe tests
- tests/test_db_reconnect.py
- Discord recap restatement
- In-play scorer locks and push alerts
- NHL blocked shots prop model
- tests/test_refresh_retry.py
- NBA results player name resolver
- NBA results ingestor tests
- NFL in-play odds history purchase
- NBA second game projection engine
- tests/test_local_cache_is_additive.py
- tests/test_calibration_check_coverage.py
- Live odds client and credits
- tests/test_team_board_cache.py
- nfl/live_model/tests/test_rush_attempt_pace.py
- NBA fifth search period shares
- MLB totals public fade model
- MLB weather forecast ingestor
- NHL team rates as of date
- tests/test_dk_freshness_parse.py
- models: slate_concentration + test_slate_concentration
- Sharp book retention during odds pruning
- View migration lock handling tests
- Discord pick notifier price fields
- Mobile tracked bets performance
- NHL goalie gate refresh tests
- NBA game four point estimates
- Best line threshold sweep
- Settlement CLV timeout retry tests
- NCAAF college data ingest tests
- Mobile bet slip and parlay legs
- NBA pregame scoring window
- tests/test_prop_odds_utc_stamp.py
- NHL derivative totals card
- Price prefilter rollback safety
- NCAAF walk forward validation
- tests/test_feature_artifact_agreement.py
- NFL prop market one side per line
- Closing line value math
- tests/test_cloud_retrain_artifacts.py
- NHL side models never bet against each other
- Schedule gate publishing tests
- System health and deliverability checks
- Walk-forward model evaluation harness
- Player news freshness and pruning
- Prop player name matching
- Mobile range slider filter
- MLB batter prop log scoring tests
- tests/test_nfl_wind_publisher.py
- Odds feed ingestion and quota logging
- NFL in-play prop polling tests
- tests/test_health_reason_and_cadence.py
- NBA odds history gap fetching
- tests/test_nfl_weather_supabase_readback.py
- Publish signals on write tests
- Pitcher stats as-of invariant tests
- NBA market-relative prop bet finder
- NFL in-play feed resilience tests
- Pipeline log reason tests
- NFL in-play score distribution training
- Marketing website build and legal pages
- NCAAF gameday school context
- NBA in-game study two
- NFL scored rows and lock keys
- NFL in-play prop settlement tests
- NBA prop fetch window planning
- NHL player prop model and backtest
- Settlement self-heal and postponed MLB voids
- tests/test_prop_missing_features.py
- Worker job queue run and lock tests
- NCAAF FBS registry health checks
- NFL in-play pick writer tests
- NFL in-play pick writer
- NCAAF live state recording tests
- tests/test_run_ledger_orphans.py
- NFL opener and NCAAF calibration tests
- NBA lineup stints from play-by-play
- NCAAF opponent-adjusted search features
- In-play calibrated decision tests
- Team total market decision tests
- Shared database connection and paper tracking
- NBA odds history and news window
- Any-book first five line scoring
- tests/test_repair_bogus_first_pitch_labels.py
- nfl/live_model/tests/test_executor.py
- tests/test_sbr_loader.py
- mobile/scripts/ux_scan.mts
- NBA schedule refresh
- Player prop box score backfill
- Mobile player stats and game log
- Database cursor and lock wrapper
- tests/test_live_quote_staleness.py
- NBA prop closing line purchase tests
- NBA prop settlement stats tests
- NFL pass attempt over bias
- In-play publish parity with pauses
- CLV backfill job tests
- NBA injury report fetch tests
- supabase/functions/_shared/discord.ts
- Worker job queue validation tests
- NCAAF in-play locked bet writes
- NFL wind publisher scored rows tests
- NHL goalie confirmation guards
- NFL line snapshot row writing
- NFL opener fire window tests
- NHL anchored moneyline input tests
- Schema change guard on startup
- tests/test_discord_channel_probe.py
- tests/test_nfl_prop_one_read_per_game.py
- Bounded prune failure handling
- Multi-book odds fetch tests
- System health check pass tests
- tests/test_model_game_savepoint.py
- Health check pick delivery tests
- NBA SBR odds archive importer
- Player news and name normalization
- Any-book first five innings lines
- tests/test_calibration_watch.py
- NCAAF in-play history backtest
- NFL weather edge research
- NBA schedule refresh fallback tests
- In-play pregame total anchor tests
- Pipeline failure alert rules
- Score when lines open tests
- Publish key identity checks
- tests/test_sbr_loader.py
- NHL totals market card
- Mobile app screens and theme
- Scratch Postgres migration test harness
- tests/test_nhl_three_way_lookahead.py
- NBA injury report ingestion
- Prop odds next day lookahead tests
- External threshold map promotion
- NHL goalie matchup assessment
- System health run ledger tests
- Social post publishing
- In-play best line price tests
- tests/test_sbr_loader.py
- Game feature engines across sports
- Mobile custom model builder client
- NCAAF college data refresh and backfill tests
- UFC fight stats ingest tests
- Mobile team detail and stats odds queries
- Honest EV and per model floors
- NBA team total odds fetch tests
- Discord stake sizing parity
- NFL opener bettable books tests
- tests/test_void_picks.py
- tests/test_sbr_loader.py
- MLB final score twin lookup
- NBA team total odds fake database
- Job heartbeat and stale jobs
- NHL stats pull row builders
- Failure alert delivery and recovery
- NBA ingestor shared imports
- NBA box score repair tests
- Health check daily feed freshness
- tests/test_sbr_loader.py
- NFL look-ahead and live bet keys
- tests/test_daily_retry.py
- UFC pregame price age tests
- Results recap message id tests
- Current injury status replacement
- NCAAF schedule rest context
- Odds repeat thinning keeps NBA rows
- NFL wind forecast cards
- tests/test_live_book_move_guard.py
- NHL player props card tests
- NCAAF research dataset building
- tests/test_sbr_loader.py
- Umpire ingestor backfill window
- Social post queue and drain
- Recap, line alert and X results tests
- NFL pick monitor
- In-play game clock alignment
- NHL expected goals model fit
- Ungraded model performance tests
- Prop odds missing game insert tests
- Threshold review schema setup
- NHL goalie confirmation timing tests
- NHL blocked shots prop settlement tests
- Pregame insert cutoff tests
- System health check test fixtures
- Mobile custom model filters and thresholds
- Team stats live season span checks
- Pregame price age clock tests
- supabase/functions/revenuecat-webhook/index.ts
- supabase/functions/whop-webhook/index.ts
- NFL pick evaluation and monitor
- tests/test_nfl_props.py
- NFL closing line backtest features
- NFL opener pick insert once
- WNBA injury team lookup fallback
- tests/test_sbr_loader.py
- NBA results store and windows
- Schedule events and odds pruning joins
- MLB prop market pregame sweep
- tests/test_nfl_props.py
- Injury adjustment feature tests
- NBA player prop model
- Mobile matchup and stats verify scripts
- Rule model card tests
- NFL prop settlement tests
- Game result target computation tests
- NBA official injury report PDF parser
- MLB doubleheader twin game merge
- NBA public splits archiving tests
- Scorer pick signal classification tests
- tests/test_game_market_gate.py
- NBA team total closing line tests
- NFL prop stat distribution tests
- NBA public splits quality backfill
- Pipeline watch findings and alerts
- NFL prop market card tests
- NBA research data cache
- NBA second game prop projections
- tests/test_score_when_lines_open.py
- Scorer injury flag tests
- Bounded odds pruning and thinning
- tests/test_pick_integrity.py
- NFL live leader model
- Schedule refresh fake database helpers
- NHL as-of blended team inputs
- NHL starter-out injury features
- Pre-game pick scorer core
- tests/test_record_one_pick_per_event.py
- WNBA returning player injury feature
- First signal repair tests
- Weekly job catch-up tests
- Model training and prop feature core
- Pipeline report rollback tests
- NFL pick monitor join key
- Paused bet bankroll capture tests
- Health check skip budget (group 716)
- Pregame price age bound tests
- nfl/live_model/tests: test_props + props
- One NHL prop bet per game
- NFL prop injury veto (group 731)
- NBA prop no-bet rows harness tests
- NFL prop market lead ceiling
- Deploy checks and job queue
- tests/test_wnba_prop_market.py
- tests/test_nfl_scored_rows.py
- NHL derivative totals pricing
- Eggz capper picks Discord recaps
- NBA prop cards across models
- Prop odds book update time
- tests/test_recap_retries_a_skipped_day.py
- Monitoring dashboard web server
- NFL prop pulls and recap error tests
- MLB bet record audit tally
- Live state poller dry-run connection
- Scorer feature value encoding
- Prop poller leaves rows alone
- Odds API credit budget
- Dead NHL API import removal
- NFL player stats and props data ingest
- NHL prop card nightly cap
- NBA prop market decision tests
- X tweet delivery attempt
- NBA injury report ingest tests
- Player news feed fetching
- Weather step date window tests
- Team total market pick tests
- Future game price gate tests
- Score when lines open window tests
- NBA game offset ridge fitting
- Schema SQL statement splitter
- NHL goalie confirmation window planner
- NBA totals luck decision tests
- Probability calibration and cut sweeps
- NHL goalie gate fake database
- NHL blocked shots prop settlement
- Savant freshness health check tests
- Odds poller creates missing games
- UFC fight resolution tests
- Weekly catch-up cursor stub
- tests/test_ncaaf_prop_odds.py
- MLB opposing starter feature tests
- NHL unknown goalie refusal rules
- College football alias score mirroring
- NFL opener card and model split tests
- DraftKings direct feed matching
- Silent job failure alerts
- NFL game line rules log tee
- Pregame price age fake board tests
- Multi-book odds fallback
- tests/test_ncaaf_pbp_store.py
- Sportsbook team to game resolver
- NFL prop game matching
- Team rest and back-to-back view
- tests/test_heartbeat_watchdog.py
- Sport injury index loader
- NCAAF gameday CFBD mode
- NFL DraftKings line snapshots
- NFL scoring preflight checks
- NBA results ingestor fake connection
- NCAAF in-play quote selection engine
- NCAAF feature engine test database
- Model quality run persistence tests
- Feature map per model tests
- Settlement self-heal tests
- Pregame line change poller
- Picks email rendering
- MLB public fade empty board test
- Record correction social posts
- Calibration watch announcements
- NBA prop rest days inputs tests
- NBA box score ingestion
- Pipeline credit burn watch
- NBA schedule refresh from feed
- NFL opener calibration
- NBA game probability harness
- Bet price and book taken
- Health check cadence from dates
- Model quality volume spikes
- NFL prop parameter artifact check
- Social posts dry run default
- NBA news and in-play research scripts
- NFL wide odds table builder
- Website record summary math
- NFL standings and division flags
- NFL prop alternate line grading
- Eggz picks recap timing
- NBA team total ladder quotes
- NBA prop projection tests
- Scorer housekeeping delete guards
- CFBD local aggregates
- NBA results ingestion check
- Health check lateness reporting
- Pipeline step failure reasons
- Player position cache
- NCAAF line bookmaker label
- NHL goalie save regression
- NCAAF monthly API call budget
- NFL spread board bet grading
- Discord stale pause flag check
- Health check skip budget (group 1050)
- NBA bought odds season coverage
- NBA prop near-tip posting
- NFL live leader call cap
- NFL kickoff schedule cache tests
- Pipeline step duration recording
- Pipeline watch announcement
- Pipeline watch recap findings
- NBA season opening date
- College football gameday cadence
- NBA per-season calibration test
- NBA harness season coverage choice
- NCAAF prop odds school resolver
- NCAAF odds cadence independence
- NCAAF kickoff timezone handling
- DraftKings feed per-row rollback
- tests/test_prop_calibrated_decision.py
- DraftKings direct feed switch
- DraftKings direct feed empty run
- Injury gate stays out of features
- Health check skip budget default
- NBA synthetic check safety
- NFL prop market veto reexport
- DailyFaceoff sample game fixture
- NHL shots on goal exemption
- NBA fourth search derivative markets
- tests/test_mobile_line_movement.py
- In-play calibration analysis
- NBA in-game luck study one
- NBA lineup stint derivation tests
- NBA play-by-play lineup builder
- tests/test_ncaaf_live_notify.py
- NFL in-play edge season research
- tests/test_ncaaf_alias_scores.py
- NCAAF quarterback team features
- Live monitor dashboard data store
- NBA fifth search grid tests
- tests/test_settled_record_is_immutable.py
- features/golf_feature_engine.py
- NCAAF in-play state building tests
- tests/test_bovada_feed.py
- NBA prop model research lab
- NCAAF cross-book opener tests
- tests/test_paused_keeps_real_verdict.py
- In-play edge research grading
- NBA prop projection research lab
- scripts/nfl_edge_extreme_props.py
- scripts/nfl_edge_settlement.py
- NBA prop projection card builder
- tests/test_agents_contract.py
- Pregame snapshot first pitch guard
- Kalshi NFL price history fetch
- WNBA results ingestor
- NBA box score enrichment
- NBA derivative market lab
- scripts/nfl_preflight.py
- Mobile screen source pattern tests
- NBA halftime in-game research
- NBA second game market search
- tests/test_decide_on_calibrated.py
- tests/test_dk_direct_feed.py
- Model artifact load and tracking tests
- NBA in-game data staleness gate
- NBA prop model verification script
- scripts/game_line_market_sweep.py
- NFL luck gap edge study
- Pipeline step timing instrumentation
- Mobile live board segment tests
- tests/test_db_adapt_sql.py
- NFL prop injury veto (group 194)
- tests/test_mobile_contrast_tokens.py
- NBA alternate line pricing study
- NBA game four part one tests
- Pregame cutoff on prop prices
- NBA second game line move tests
- NFL in-play prop flow anchoring tests
- NFL prop scoring rows and candidate pool
- NBA second game verdict
- NCAAF in-play pricing engine
- tests/test_nfl_live_leader_state.py
- tests/test_ncaaf_qb_ingestor.py
- tests/test_book_team_map.py
- NCAAF feature assembly tests
- Build your own model prop facts tests
- Postgres test harness and schedule refresh
- NFL wind board fast publishing tests
- tests/test_ncaaf_game_identity.py
- NBA second game market tests
- Monitoring dashboard cache
- MLB live inning gate replay
- NBA game model research harness
- Kalshi prop ladder recording
- UFC results ingestion
- Prop market coverage probe tests
- NFL luck gap and teaser research
- NBA schedule refresh planning tests
- UFC fight feature engine
- NFL schedule refresh tests
- NBA quarter game model tests
- NBA second game luck study
- Line CLV sign and orientation tests
- NBA game harness tests
- NFL in-play flow slice backtest
- NBA in-game staleness gate
- Model calibration check tests
- MLB live game state poller
- College football stats parsing
- NFL live rush pace edge study
- NCAAF player stats parser tests
- Discord and X results posting
- scripts/nfl_live_prop_feasibility.py
- tests/test_context_budget.py
- tests/test_player_h2h_stat_values_migration.py
- tests/test_retired_models.py
- NFL in-play flow pseudo CLV tests
- tests/test_live_record_start_views.py
- UFC fight CSV event builder
- NHL shot events parsing
- Discord price bound and risk math
- NHL prop odds fetch gate
- Prop box score cooled refill
- nfl/models/opener_spread.py
- nfl/live_model/feeds: test_feed_resilience + espn
- House juice minimum odds floor
- tests/test_nfl_wind_fire_window.py
- Custom model prop and game facts
- tests/test_public_betting_ingestor.py
- Basketball player positions ingestor
- tests/test_service_role_split.py
- SQL percent escaping tripwire
- Health check skip budget tests
- NHL goalie gate insert guards
- API call log daily rollup tests
- Model quality public fade detection
- MLB over under retrain sweep job
- Mobile sport filter persistence tests
- Custom model game facts tests
- NBA second game projection tests
- Live slate midnight date discovery
- NFL in-play flow bias validation
- Custom model facts refresh and load
- Intraday weather and news freshness
- NBA period map pricing tests
- X posting and brand avatar
- NCAAF CFBD ingestor tests
- NFL in-play 2025 edge study
- Kalshi game market recorder
- HTTP request timeout floor
- No-vig CLV capture and entrypoint checks
- UFC stats page parsing tests
- NCAAF totals probability regression tests
- Refresh pass step ordering tests
- NFL halftime out-of-sample study
- NHL period goals feed tests
- NCAAF in-play backtest game states
- Mobile bankroll screen checks
- Team rest and schedule context tests
- tests/test_mobile_threshold_parity.py
- NHL derivative odds job validation tests
- tests/test_track_record_views.py
- tests/test_weekly_catch_up.py
- NFL in-play prop assessment report
- X post image fetching
- NHL goalie gate core checks
- NFL live leader model tests
- Mobile paused catalog tests
- Free pick card and X results tests
- NCAAF opener board visibility tests
- tests/test_promote_calibration_job.py
- tests/test_cfbd_snapshot_leakage.py
- NFL wind forecast stability tests
- NFL edge research local cache
- Database URL diagnosis tool
- NFL prop threshold window tests
- tests/test_nhl_research_job.py
- tests/test_settlement_timing.py
- Push delivery ticket parsing tests
- DataGolf ingestor and NHL SBR archive
- Mobile pick button script tests
- NBA prop decisions ledger guard test
- NFL odds cache import to Supabase
- tests/test_health_check_observe.py
- NFL in-play prop flow model
- NFL 2026 opener and wind tracker
- NFL in-play prop line churn check
- tests/test_pick_lock_is_on_picks.py
- Mobile pick category checks
- NFL in-play prop rule and staleness reports
- X team hashtags
- Per-model threshold config tests
- NBA game two verdict grid tests
- scripts: build_nfl_live_leader_artifact + model
- Mobile player stat groups tests
- supabase/functions/discord-link/index.ts
- tests/test_nfl_prop_clv.py
- tests/test_scoring_methods.py
- Team stats impossible games played checks
- Injury fetch cache speed test
- Worker job queue runner
- NBA public betting splits ingestor
- Anonymous read access grants
- NCAAF gameday credit cap
- nfl/scripts/backtest_opener.py
- Paused model assessment grading tests
- Bounded database pruning
- tests/test_latest_odds_views.py
- scripts/nfl_edge_gameline_rules.py
- NBA schedule ingestor
- tests/test_transaction_pooler.py
- Database URL env fallback
- Game injury veto gate
- MLB play-by-play ingestor
- Team stats rebuild and as-of checks
- supabase/functions/sharpsports/index.ts
- NHL derivative totals backtest
- Rule model market reading tests
- NCAAF situational spot search
- NFL schedule read from database tests
- tests/test_worker_deps.py
- scheduler.py
- First pitch guard tests
- College football live ESPN feed
- Health check alert deliverability
- tests/test_mobile_stat_labels_match_the_server.py
- tests/test_ncaaf_fcs_visitor_names_migration.py
- NBA game model lab and rest features
- NBA totals luck card
- tests/test_scorer_nfl_prop_like_escape.py
- NHL stats views tests
- Trainer no-register mode tests
- MLB backfill retry resilience
- Market movement feature builder
- Team stats rebuild row tests
- ESPN NHL probable goalies
- tests/test_clear_unauthorized_auto_pauses_migration.py
- tests/test_ncaaf_se_louisiana_alias_migration.py
- tests/test_overnight_polling.py
- NFL stale daily card clearing
- NFL EV engine and stake sizing
- Mobile type-check baseline tests
- College football model search runner
- NFL overseas venue roof and wind tests
- Results recap backfill command
- tests/test_claude_rules_split.py
- tests/test_db_setup.py
- tests/test_dedupe_opening_signals.py
- Garbled NBA injury report detection
- tests/test_pbp_backfill_resilience.py
- ESPN injury team name mapping
- NBA public splits side parsing
- NBA injury report time slots
- NBA in-game study one tests
- Mobile accessibility and CLV card tests
- NFL model import path tests
- NBA public splits pipeline step
- tests/test_prompt_reads_thresholds.py
- NCAAF situational spot evaluation
- NBA period score ingestion
- scripts/render_brand_icons.py
- Line state and alias migration tests
- supabase/functions/stripe-webhook/index.ts
- tests/test_drop_voided_nfl_wind_opening_signals_migration.py
- tests/test_mobile_neutral_signal_label.py
- Discord period results recaps
- tests/test_scorer_commits_per_game.py
- NBA ESPN scoreboard parsing
- Declared worker job validation tests
- tests: test_wnba_availability + wnba_availability
- NFL prop market EV floor sweep
- NFL ESPN injury ingest tests
- supabase/functions/sharpsports-webhook: index + index
- Mobile Lines board pin tests
- Discord and X results posters
- supabase/functions/stripe-checkout/index.ts
- tests/test_book_list_budget.py
- Mobile type-check baseline checker
- NBA game market search lab
- Baseball Savant capture date stamping
- mobile/scripts/verify_a11y.ts
- Football in-play game state
- NCAAF in-play odds history pull
- NFL wind forecast validation
- NFL in-play prop dataset and calibration
- MLB totals public fade card runner
- tests/test_demote_ncaaf_over_under_platt.py
- NCAAF line move follow spots
- tests/test_discord_post_one_pick_migration.py
- tests/test_game_scorer_spares_nfl_props.py
- Injury athlete name caching
- NFL in-play score distribution pricing
- Mobile quiet update download tests
- NBA team total luck replay tests
- MLB in-play game state features
- NFL in-play edge studies 2024-25
- NFL prop shape simulation
- Build your own model data loading
- Monitoring probe call recording
- NFL wind stake past calibration tests
- NBA injury report player matching
- NCAAF scoreboard yardline parsing
- NFL prop kickoff lead ceiling tests
- NFL wind venue gate tests
- NHL prop EV lab fixtures
- Model quality CLV monitor
- Slate concentration and fade risk
- Published record reconciliation checks
- Pruning keeps openers and closes
- UFC fighter name resolution
- NFL opener cut sweep
- Every named sportsbook is fetched
- NCAAF opener strategy experiments
- NFL prop backtest universe summary
- NBA team total feed patching
- NHL regulation probability mapping
- Failure alerts and job heartbeats
- ESPN NHL goalie designations
- Database grant revocation
- NFL venue resolution for weather
- Mobile accessibility verify script
- Market handicap feature tests
- mobile/scripts/verify_a11y.ts
- mobile/scripts/verify_a11y.ts
- Prop CLV and SQL escaping tests
- mobile/scripts/verify_a11y.ts
- Historical odds backfill and first pitch tests
- NBA injury report name normalising
- ncaaf_live/tests/test_serve.py
- NCAAF starter out study
- Per-model EV floor card tests
- Mobile error states and books tests
- In-play trigger orchestrator and daily cap
- Custom model player prop facts
- Live feed freshness probes and MLB stats
- Steam lag line study
- No record-only mode guard tests
- MLB totals public fade ranking
- NFL quarterback wind edge study
- MLB retrain freeze guard
- NBA schedule refresh with fallback host
- NHL goalie designation changes
- NFL prop settlement name fallback
- NBA public splits quality flag
- NCAAF gameday loop cadence
- NHL box score ingest
- Team stats live season skip checks
- Team board commence cutoff tests
- NBA play-by-play clock parsing
- Team stats hist season boundary tests
- Team stats as-of date normalization
- MLB twin alias verification test
- College football in-play history backtest
- Team stats season label guard
- NCAAF quarterback ablation study
- Mobile stat segment label tests
- Opening versus closing strategy analysis
- Dashboard rule-based model display tests
- mobile/scripts/verify_a11y.ts
- NCAAF play-by-play column range scan
- Live slate midnight discovery
- NBA injury report page parser
- DailyFaceoff goalie designations parser
- Build your own model NFL docs
- CFBD school name orientation
- Weekly catch-up probe rollback test
- NFL in-play model backtest replay
- NBA public betting splits ingest
- Player news article conversion
- Mobile stats filter UX verify script
- ESPN injury feed fetch
- NBA public splits game matching
- NCAAF in-play state build file naming
- Worker service role split test
- Game injury star gate
- NFL in-play pick announcements
- MLB totals public fade tests
- Shared in-memory test database
- First signal repair comparison
- NCAAF venue travel and altitude features
- NFL prop sportsbook sweep
- NCAAF in-play score distribution pricing
- One pick per event record counting
- Monitoring server access control
- In-play column map scoring guard
- Pipeline watch recap tracking
- Odds snapshot pass ordering
- Restore first bet signals step
- NCAAF in-play history budget
- NCAAF prop odds markets
- MLB live bases state parsing
- Player news name matching
- ESPN player news ingestion
- NCAAF in-play odds cadence and outages
- Parlay correlation estimates
- MLB prop market sweep
- Rich market handicap features
- NBA shooting luck total gaps
- NBA play-by-play ingestor
- NHL goalie lock race guards
- Odds pruning keeps the close
- MLB game market steam overlay
- Betting bias rule scan
- College football model calibration fitting
- Account deletion endpoint tests
- Units won settlement convention
- ROI collapse detection
- NCAAF FBS registry fake database
- NHL goalie designations table migration
- Website hosting config
- Account deletion database functions
- Marketing site hosting readme
- Supabase schema tables
- Current injury status table
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
- App terms and conditions
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
- Social post queue migration
- Opening signals shadow table
- In-app feedback thread tables
- Capper picks tables migration
- NBA 2026-27 rebuild write-up
- Signal Base privacy policy
- One live bet row per pick index
- Social profile update migration
- NHL expected goals aggregates migration
- Saved custom models migration
- Mobile build and run scripts
- Mobile app development dependencies
- NBA in-game market search plan
- NBA lineup segments documentation
- NHL shot events migration
- Player news sheet docs
- docs/rules_evidence.md
- NFL game lines model write-up
- Market-relative prop rule evidence
- nfl/live_model/README.md
- docs: followups + clv
- docs: best_line + config_topology
- docs/history: learnings + build_state
- NCAAF in-play model notes
- monitoring/static/dashboard.html
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
- Monitoring and model research docs
- docs/sports: ufc + golf
- mobile/docs/BILLING.md
- NFL model environment and restore
- .claude/agents: frontend-ux-designer + CLAUDE
- .claude/rules/picks-and-publishing.md
- .claude/rules/model-updates.md
- NFL in-play prop assessments docs
- docs/signal_timing.md
- mobile/docs/DISCORD_LINKING.md
- Probability calibration design notes
- docs/live_betting.md
- College football model search findings
- docs/sports/wnba.md
- Odds sources and prop research
- mobile/docs/AUTHENTICATION.md
- .claude/rules/frontend.md
- Model artifact and health check docs
- docs/retrain_2026_plan.md
- Calibration and NFL wind opener tracking docs
- docs/reviews/2026-09-07-nfl-props-deep-dive.md
- NFL wind totals runbook
- docs/market_coverage.md
- NFL prop method research docs
- (root): pr-ci + requirements
- NFL props sources and prediction market research
- mobile/docs/BILLING.md
- docs/testing.md
- CLAUDE.md
- docs: nhl_market_lab + nhl_clv_ev_assessment
- docs/game_injury_gate.md
- Signal flip push notifications

## God Nodes (most connected - your core abstractions)
1. `get_connection()` - 677 edges
2. `DBConnection` - 332 edges
3. `StatsScreen()` - 164 edges
4. `react` - 154 edges
5. `react-native` - 109 edges
6. `colors` - 94 edges
7. `font` - 86 edges
8. `PickCard()` - 85 edges
9. `spacing` - 83 edges
10. `radii` - 82 edges

## Surprising Connections (you probably didn't know these)
- `8.1 P1, the market-anchored model: choices fixed before any P1 cell was graded (2026-10-18)` --references--> `choose_C()`  [INFERRED]
  docs/nba_models_2026.md → models/nhl_moneyline_anchored.py
- `IG-1: how the lab reads the row above (2026-10-17, written before any IG-1 number)` --references--> `run_cells()`  [INFERRED]
  docs/nba_models_2026.md → scripts/nba_game_harness.py
- `Things a reader should know` --references--> `shot_value()`  [INFERRED]
  docs/nba_pbp_stints.md → data/ingestors/nba_stints.py
- `Backtest` --references--> `statement_timeout()`  [INFERRED]
  docs/byom_nfl.md → data/db.py
- `9.8 Changes after the check, before any cell was graded (2026-10-20)` --references--> `derived()`  [INFERRED]
  docs/nba_models_2026.md → tests/test_mobile_pick_categories.py

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

## Communities (1079 total, 259 thin omitted)

### Community 272 - "Mobile app shell and feedback"
Cohesion: 0.02
Nodes (193): AppErrorBoundary, IoniconName, Calls, NavRef, PushState, PushStatus, FeedbackCategory, FeedbackMessage (+185 more)

### Community 0 - "Mobile picks home filters and sorting"
Cohesion: 0.02
Nodes (156): P, ActivePill, Props, Props, DateOption, DayRow, SelectableGame, modelCategory (+148 more)

### Community 1 - "Mobile stats board"
Cohesion: 0.01
Nodes (510): P, TouchSet, PlayerNextGame, Sport, NextGame, Section, AnytimeMatchupView, AnytimeSortRow (+502 more)

### Community 1019 - "NHL prop fetch staleness guards"
Cohesion: 0.29
Nodes (3): _QuoteConn, test_a_prop_fetch_older_than_the_confirmation_does_not_decide(), test_a_shots_on_goal_fetch_older_than_the_confirmation_still_decides()

### Community 1032 - "NHL stale teams schedule context"
Cohesion: 0.33
Nodes (3): _NhlConn, _stale_teams_before(), test_nhl_stale_teams_answers_exactly_as_before()

### Community 104 - "Weather totals and NFL edge research"
Cohesion: 0.04
Nodes (61): TestTheStoreReadsTheStartTime, _p(), backfill_weather(), fetch_and_store_weather_for_date(), _is_dome_game(), _wind_out_component(), _num(), step_nfl_prop_scoring() (+53 more)

### Community 105 - "NBA book numbers and game four search"
Cohesion: 0.05
Nodes (43): Point, even_gap(), ladder_mask(), main_rungs(), _one_rung(), split_main_rungs(), visible_numbers(), go_guard() (+35 more)

### Community 108 - "Best line price shopping tests"
Cohesion: 0.03
Nodes (48): FakeConn, TwoOrientationConn, FakeConn, _best_game_price(), _best_of(), _best_prop_price(), _fresh_quotes(), _same_line() (+40 more)

### Community 11 - "Mobile stats odds and line legs"
Cohesion: 0.02
Nodes (143): PlayerPropQuote, ResolvedSlip, BetslipPlayer, InjuryIndex, injuryTag, InjuryTone, GameLineLegSpec, GameLineMarket (+135 more)

### Community 113 - "tests/test_nfl_live_leader_gameday.py"
Cohesion: 0.06
Nodes (30): FakeClock, FakeConn, FakeFeed, _Rows, art(), live_state(), quote_payload(), _run_loop() (+22 more)

### Community 115 - "tests/test_calibration_promotion.py"
Cohesion: 0.06
Nodes (28): FakeConn, _SchemaRecordingConn, eligibility_clause(), maps_materially_differ(), promote(), _payload(), _row(), test_a_broken_table_is_identity_maps_not_an_exception() (+20 more)

### Community 116 - "tests/test_score_off_any_book_line.py"
Cohesion: 0.08
Nodes (33): _FakeConn, _fallback_line_quote(), _cut(), _on(), _pick(), _row(), _sql_const(), _src() (+25 more)

### Community 121 - "Alternate prop line fetching tests"
Cohesion: 0.06
Nodes (29): _Conn, _Resp, _market_chunks(), alt_markets_due(), _ou(), _parse(), test_a_422_retries_without_the_alternates_before_going_dk_only(), fake_get() (+21 more)

### Community 123 - "tests/test_backtester.py"
Cohesion: 0.07
Nodes (9): TestCalibrationError, TestComputeBacktestSummary, TestEvaluateResult, TestGoLiveGateConstants, TestIterSides, _calibration_error(), compute_backtest_summary(), _evaluate_result() (+1 more)

### Community 124 - "Mobile daily results summary"
Cohesion: 0.03
Nodes (86): Bucket, FixturePick, Acc, DayGameSummary, DayStakeStats, ModelDayStats, ScopedDailyResults, SportDayBreakdown (+78 more)

### Community 125 - "NFL in-play gameday worker loop"
Cohesion: 0.07
Nodes (14): _Q, GamedayWorker, GameTracker, test_the_worker_self_checks_once_and_alerts_on_a_broken_feed(), test_a_one_sided_quote_is_skipped_rather_than_priced_on_raw_juice(), test_anchor_does_not_match_a_different_game(), test_anchor_matches_on_the_matchup_not_the_event_id(), test_espn_abbreviations_that_differ_from_ours_still_match() (+6 more)

### Community 129 - "NBA prop market lab"
Cohesion: 0.09
Nodes (44): NBTable, add_units(), assemble(), best_per_key(), boot_ci(), build_quotes(), candidates_from(), choose_floor() (+36 more)

### Community 13 - "Discord pick notifier tests"
Cohesion: 0.01
Nodes (115): _FakeConn, _FakeResult, _Resp, _StampConn, _cand(), _et_now_iso(), _freeze_now(), _live_row() (+107 more)

### Community 131 - "nfl/live_model/tests/test_backup_snaps.py"
Cohesion: 0.09
Nodes (22): _FakeConn, _FakeCur, back_up(), digest(), _flush(), iter_files(), main(), _mb() (+14 more)

### Community 135 - "mobile/scripts: verify_book_links + verify_betslip_combine"
Cohesion: 0.06
Nodes (37): betslipCombineKind, combineBetMgm(), combineBetslipLinks(), combineCaesars(), combineDraftKings(), combineEspnBet(), combineFanDuel(), fanDuelPairs() (+29 more)

### Community 137 - "Football gameday loops and push alerts"
Cohesion: 0.02
Nodes (93): _Unset, LiveOddsFeed, GameContext, LiveOddsFeed, Quote, Puller, CreditBudgetExceeded, JsonlRecorder (+85 more)

### Community 14 - "NBA team total under model tests"
Cohesion: 0.04
Nodes (48): TeamTotalDecision, book_ages(), decide(), record(), home_part(), newest_season(), pricing_dist(), quote_frame() (+40 more)

### Community 140 - "X post queue drain tests"
Cohesion: 0.11
Nodes (39): _Fetcher, Poster, QueueConn, _Uploader, ImageFetch, MediaUpload, _blank(), _drain() (+31 more)

### Community 141 - "Kalshi prop ladder ingestion and bets"
Cohesion: 0.04
Nodes (36): Ladder, Rung, TestMarketRelative, find_bets(), _expit(), from_kalshi(), from_one_sided_overs(), _logit() (+28 more)

### Community 142 - "tests/test_health_pregame_prices_current.py"
Cohesion: 0.08
Nodes (31): _Conn, _at(), _game(), _row(), _run(), test_a_broken_feed_read_is_an_error_and_rolls_back(), test_a_broken_query_is_an_error_and_rolls_back(), test_a_cancelled_fight_and_a_pulled_game_do_not_raise_the_alarm() (+23 more)

### Community 143 - "Pick lock survives settlement tests"
Cohesion: 0.08
Nodes (22): _SqliteShim, conn(), _game(), _pick(), _survivors(), test_a_bet_is_never_dropped_for_an_earlier_no_signal(), test_a_dead_zone_prop_row_locks_too(), test_a_final_game_is_not_a_scoring_target() (+14 more)

### Community 144 - "NBA game line move study"
Cohesion: 0.07
Nodes (33): Data, attach(), big_home_dog_signal(), consensus(), control_specs(), coverage_text(), fade_side(), favourite_sides() (+25 more)

### Community 146 - "MLB game market bet finder tests"
Cohesion: 0.08
Nodes (25): GameMarketBet, _SlateConn, find_spread_bets(), find_total_bets(), _is_runline(), pick_rows(), test_mlb_market_cards_drop_a_bet_under_the_floor(), _game_rows() (+17 more)

### Community 149 - "Discord full record correction posts"
Cohesion: 0.07
Nodes (26): LedgerUnread, Conn, delete_custom_record_post(), _jump(), _place(), _publish(), publish_full_record(), publish_full_record_standard() (+18 more)

### Community 15 - "X post publisher tests"
Cohesion: 0.02
Nodes (80): _R, test_a_push_only_period_does_not_invent_an_roi(), test_the_period_tweet_uses_the_daily_tally_and_states_roi(), _afternoon(), _creds_on(), _fake_conn(), _slate(), _split() (+72 more)

### Community 150 - "Threshold review and coverage probe"
Cohesion: 0.05
Nodes (30): _Conn, _quiet(), rule_only(), _slate(), test_a_losing_model_with_enough_bets_is_flagged(), test_a_losing_model_with_too_few_bets_is_left_alone(), test_a_milestone_fires_only_once(), test_a_model_paused_in_config_is_not_reported_again() (+22 more)

### Community 154 - "UFC phantom fight filter"
Cohesion: 0.21
Nodes (6): TestFilterUfcPhantom, TestIsKnownUfcMatchup, _filter_ufc_phantom(), _is_known_ufc_matchup(), _game(), _odds()

### Community 156 - "NBA game model prop feature tests"
Cohesion: 0.06
Nodes (40): _Stop, _box(), _g(), _games(), _inj(), _model(), _props(), _run() (+32 more)

### Community 158 - "NFL prop market research scripts"
Cohesion: 0.01
Nodes (190): Plan, EggzSettleError, kalshi_school(), _num(), probe(), rows_for(), fetch_series(), ladders() (+182 more)

### Community 16 - "Mobile all-books lines board"
Cohesion: 0.03
Nodes (111): LinesMarket, LinesMarkPick, linesMarks, LinesMlMode, LinesOddsRow, LinesPickRef, LinesSheetRow, LinesSheetSide (+103 more)

### Community 160 - "Discord void notice sender"
Cohesion: 0.03
Nodes (51): Ledger, _posted_sql(), _sql_key(), test_a_game_level_key_has_no_tail(), test_a_published_void_keeps_track_and_betslip(), test_a_tracked_void_reads_not_graded_and_detail_closes_when_over(), test_an_opening_signal_is_live_only_when_discord_published_it(), test_discord_led_visibility() (+43 more)

### Community 162 - "NFL prop odds loader tests"
Cohesion: 0.07
Nodes (17): _Conn, _Cur, TestPropOddsLoader, _Conn, _Cur, _fetch_slice(), load_nfl_prop_odds(), statement_timeout_error() (+9 more)

### Community 164 - "NFL opener held minutes tests"
Cohesion: 0.20
Nodes (8): TestFreshNumberLabel, TestHeldMinutes, _giants_board(), _giants_prior_at_2129(), _giants_sched(), _obs(), _row(), _ts()

### Community 165 - "NHL stats, goalies and prop card"
Cohesion: 0.02
Nodes (103): _Resolver, TestNoHollowTeamRowBeforeTheFirstGame, fetch_espn_nhl_probables(), fill_missing(), backfill(), build_goalie_rows(), build_skater_rows(), build_team_rows() (+95 more)

### Community 166 - "Mobile crash logging"
Cohesion: 0.11
Nodes (34): CrashContext, CrashLogDeps, CrashReport, ErrorUtilsShape, KeyValueStore, LaunchMarker, LaunchStage, ReportKind (+26 more)

### Community 17 - "NFL prop backtest and odds tests"
Cohesion: 0.03
Nodes (39): TestLocalOddsCache, TestNormaliseName, TestPlaceboCannotSilentlyNotHappen, TestPriceMath, TestPushAdjustment, TestSnapRows, TestVerdict, TestYesNoMarkets (+31 more)

### Community 170 - "NBA game model luck feature tests"
Cohesion: 0.05
Nodes (39): _Stop, _against_bet(), _f6c_inputs(), _games_for_standings(), _gs(), _market_pricing(), _one_game_data(), _pair() (+31 more)

### Community 172 - "Mobile preferred sportsbooks"
Cohesion: 0.07
Nodes (45): IoniconName, Slide, State, BookKey, BookChecklist(), toggleBook(), OnboardingModal(), SportsbookIndicator() (+37 more)

### Community 174 - "Discord publisher run lock"
Cohesion: 0.07
Nodes (17): _Conn, _Result, _clear_locks(), _no_prod_threshold_sync(), _signal_row(), test_a_connection_that_cannot_lock_still_publishes(), test_an_exception_mid_publish_does_not_wedge_every_later_pass(), test_every_signal_publisher_takes_the_lock() (+9 more)

### Community 177 - "tests/test_credit_budget.py"
Cohesion: 0.09
Nodes (22): _Conn, daily_burn(), latest_remaining(), plan_credit_budget(), _burn_conn(), _plan(), test_a_billing_reset_is_not_a_refund(), test_a_call_is_billed_at_what_the_api_says_it_cost() (+14 more)

### Community 178 - "Closing line value at price taken"
Cohesion: 0.06
Nodes (25): _Conn, _Res, _fn(), _migration(), _pick(), test_a_draftkings_decided_row_is_unchanged(), test_a_legacy_row_that_cannot_be_re_measured_leaves_the_old_method(), test_a_legacy_stamped_row_is_re_measured_and_leaves_the_queue() (+17 more)

### Community 18 - "NHL goalie guards on prop cards"
Cohesion: 0.07
Nodes (33): _Clf, _FetchDB, GoalieDB, _refuse_unknown_nhl_bets(), publish(), publish(), _blocked_rows(), _both() (+25 more)

### Community 180 - "Odds pruning keeps openers and closes tests"
Cohesion: 0.09
Nodes (26): StandIn, build(), drain(), _lit(), old_prune(), old_thin(), render(), _rows_of() (+18 more)

### Community 182 - "NFL player and team stat parsing"
Cohesion: 0.06
Nodes (16): TestGamesRows, TestKickoff, TestParsePlayerRows, TestParseTeamRows, TestUpcomingRows, TestVenueAndScheduleOfRecord, games_rows(), _int_or_none() (+8 more)

### Community 186 - "X profile update queue"
Cohesion: 0.06
Nodes (35): ProfileConn, _Rows, Updater, ProfileUpdate, run_social_post_queue(), pin(), _code(), _creds() (+27 more)

### Community 189 - "Odds pruning budget and sharp-book carve-out"
Cohesion: 0.14
Nodes (8): Budget, BudgetSpent, _day(), prune_table(), mark(), settle(), test_a_one_row_budget_stops_after_one_deleting_statement(), test_the_time_budget_stops_the_run()

### Community 191 - "Market-relative prop bet finder tests"
Cohesion: 0.06
Nodes (25): TestNaNIsAbsent, devig(), find_bets(), card(), _bets_from_kalshi(), _zero_vig_american(), _q(), test_a_different_line_is_never_compared() (+17 more)

### Community 193 - "tests/test_first_signal_repair.py"
Cohesion: 0.13
Nodes (22): _VoidedConn, patch_conn(), _sql_of(), test_a_lane_already_holding_its_first_bet_is_untouched(), test_a_lane_with_no_sibling_still_restores(), test_a_lane_with_nothing_standing_is_restored(), test_a_pregame_model_is_not_marked_live(), test_a_price_move_alone_is_a_different_bet() (+14 more)

### Community 197 - "Daily pipeline and stats ingestors"
Cohesion: 0.01
Nodes (192): ViewMigrationResult, get_connection(), _run_migrations(), setup_database(), backfill_savant_stats(), run_savant_ingestor(), backfill_ncaaf(), backfill_ncaaf_lines() (+184 more)

### Community 2 - "Mobile markets and formatting"
Cohesion: 0.01
Nodes (325): Row, Props, Props, IoniconName, Props, Props, clvBetQuote, ClvBetRow (+317 more)

### Community 20 - "Model calibration sweep tests"
Cohesion: 0.05
Nodes (17): _ProbeConn, _rows(), test_a_prob_only_sweep_uses_only_the_probability_dimension(), test_column_migrations_run_every_pipeline_pass(), test_home_runs_are_no_longer_exempt_from_pausing(), test_plateau_is_computed_within_the_narrow_grid(), test_the_agent_changes_nothing_on_its_own(), test_the_agent_sweeps_every_registered_model_except_live_ones() (+9 more)

### Community 200 - "Discord void notices and embeds"
Cohesion: 0.06
Nodes (26): DiscordVoidRejected, test_a_malformed_timestamp_drops_the_stamp_rather_than_raising(), test_american_odds_formatting(), test_game_time_renders_in_eastern(), test_matchup_is_sport_aware(), test_a_known_channel_is_a_jump_link_and_an_unknown_one_is_omitted(), test_embeds_chunk_at_the_field_cap_and_the_size_cap(), bulky() (+18 more)

### Community 203 - "NHL goalie as-of lookup"
Cohesion: 0.17
Nodes (3): GoalieBook, TestGoalieAsOf, _g()

### Community 204 - "NBA total luck replay studies"
Cohesion: 0.05
Nodes (27): FrameConn, load_artifact(), load_artifact(), bucket_counts(), build(), cell_bets(), tt_residuals(), artifact() (+19 more)

### Community 205 - "NFL in-play game state feed"
Cohesion: 0.10
Nodes (20): CoreClient, EventMeta, LiveState, _abbr(), game_seconds(), https(), in_window(), _int() (+12 more)

### Community 206 - "Mobile color contrast checker"
Cohesion: 0.05
Nodes (39): Pair, code(), lum(), noGreen(), over(), ratio(), read(), readUtf8() (+31 more)

### Community 21 - "Mobile record hero and equity curve"
Cohesion: 0.03
Nodes (133): Slop, StatusForSpeech, EquityPoint, plotLayout, PlotPad, ParlaySummary, SportGroup, TrackRecordSummary (+125 more)

### Community 210 - "Mobile paywall billing and account access"
Cohesion: 0.02
Nodes (248): AccessState, useAccess, AuthState, AuthStatus, useAuth, useEntitlement, ConnectionMap, providerMeta (+240 more)

### Community 211 - "Mobile bankroll tracker"
Cohesion: 0.06
Nodes (69): BankrollCheck, BankrollCommit, BankrollPatch, BankrollRead, BankrollSettings, KeyValueStore, NumberSeparators, Part (+61 more)

### Community 214 - "NCAAF live score distribution"
Cohesion: 0.11
Nodes (10): ScoreDistribution, mu_bucket(), time_bucket(), _synth(), test_final_pmf_offsets_by_current_score(), test_marginals_are_normalised_under_both_smoothings(), test_no_support_cell_is_ever_exactly_zero(), test_shrink_moves_prior_mass_off_the_impossible_low_tail() (+2 more)

### Community 215 - "Idle database read transaction tests"
Cohesion: 0.08
Nodes (14): _Rec, _flat(), test_a_lock_timeout_fails_that_file_and_the_next_still_runs(), test_a_locked_bet_releases_the_lock_check(), test_a_quiet_tick_rolls_the_read_back(), test_a_tick_that_writes_does_not_roll_the_insert_back(), test_an_unresolved_game_releases_the_context_read(), test_is_locked_releases_the_read() (+6 more)

### Community 216 - "NHL market-anchored moneyline model"
Cohesion: 0.08
Nodes (17): OffsetLogit, games_between(), teams_missing_from_logs(), _add_rating(), build_inputs(), choose_C(), decision_window(), fit() (+9 more)

### Community 218 - "In-play score change quote guard"
Cohesion: 0.13
Nodes (12): _FakeConn, _book_move(), _get_live_dk_odds(), _score_changed_at(), _odds(), test_a_quote_published_before_the_score_is_declined(), test_a_quote_republished_after_the_score_is_kept(), test_the_age_bound_alone_would_have_allowed_it() (+4 more)

### Community 22 - "API call monitoring probe tests"
Cohesion: 0.04
Nodes (35): _Resp, configured(), guild_stats(), _credits_from(), _redact(), _scrub(), classify(), paid_apis() (+27 more)

### Community 220 - "tests/test_db_reconnect.py"
Cohesion: 0.09
Nodes (16): _Conn, _Cursor, _is_write(), _lost(), test_a_committed_transaction_is_clean_again(), test_a_lost_connection_with_uncommitted_writes_raises_connection_lost(), test_a_read_on_a_lost_connection_reconnects_and_retries(), test_a_statement_timeout_is_not_a_lost_connection() (+8 more)

### Community 222 - "Discord recap restatement"
Cohesion: 0.06
Nodes (18): _Conn, test_a_restated_recap_is_labelled_and_says_why(), _resp(), test_a_404_is_an_answer_not_a_retry(), test_a_persistent_403_still_raises_after_the_last_attempt(), test_a_recap_whose_count_merely_drifted_is_not_due(), test_a_recap_with_a_late_settlement_is_due(), test_a_restatement_waits_out_a_live_game_and_posts_the_next_morning() (+10 more)

### Community 223 - "In-play scorer locks and push alerts"
Cohesion: 0.07
Nodes (30): FakeConn, _Rows, FakeConn, _lane_signature(), _record_live_features(), _write_live_picks(), test_the_lane_signature_carries_the_deciding_price(), _log_lines() (+22 more)

### Community 224 - "NHL blocked shots prop model"
Cohesion: 0.07
Nodes (22): TestTonightsRowIsATrainingRow, TestWhoThePlayerIs, build_frame(), _ew(), expected_value(), fit(), load_skaters(), load_teams() (+14 more)

### Community 225 - "tests/test_refresh_retry.py"
Cohesion: 0.14
Nodes (23): Decision, RefreshRun, _decide(), _done(), _run(), test_a_failed_view_migration_fails_the_step(), test_a_pass_that_finished_with_failed_steps_ran_its_chain(), test_a_redeploy_between_passes_replaces_nothing() (+15 more)

### Community 226 - "NBA results player name resolver"
Cohesion: 0.14
Nodes (10): PlayerResolver, build_log_rows(), fallback_id(), _resolver(), test_a_rookie_keeps_one_id_across_games(), test_ambiguous_or_claimed_names_fall_back(), test_one_unresolved_player_does_not_drop_the_game(), test_resolution_order() (+2 more)

### Community 228 - "NBA results ingestor tests"
Cohesion: 0.09
Nodes (28): _ESPN, FakeStore, _FixedNow, ingest_nba_results(), match_game(), _new_totals(), _shift(), _game() (+20 more)

### Community 229 - "NFL in-play odds history purchase"
Cohesion: 0.16
Nodes (22): Budget, buy_halftime(), buy_inplay(), events_for(), _floor5(), _get(), halftime_requests(), halftime_windows() (+14 more)

### Community 23 - "NBA second game projection engine"
Cohesion: 0.03
Nodes (91): EW, Last, Model, PointInputs, State, World, actuals(), apply_models() (+83 more)

### Community 230 - "tests/test_local_cache_is_additive.py"
Cohesion: 0.11
Nodes (10): _FakeConn, _merge_with_cache(), _pull_odds(), cached(), _frame(), test_a_first_ever_pull_still_works(), test_a_pull_that_lost_rows_keeps_them(), test_an_unreadable_cache_refuses_rather_than_overwrites() (+2 more)

### Community 231 - "tests/test_calibration_check_coverage.py"
Cohesion: 0.10
Nodes (17): _Shim, _bet(), _calibration_results(), db(), _graded(), _make_db(), _only(), _promote() (+9 more)

### Community 232 - "Live odds client and credits"
Cohesion: 0.11
Nodes (12): CreditMeter, LiveOddsClient, Quote, best_price(), parse_events(), _parse_ts(), _side_of(), check_odds() (+4 more)

### Community 234 - "tests/test_team_board_cache.py"
Cohesion: 0.08
Nodes (10): _Conn, _Cursor, team_board_pairs(), team_board_seasons(), _cols(), test_every_team_sport_gets_last_this_and_next_year(), test_one_failing_pair_does_not_stop_the_rest(), test_the_cache_the_refresh_and_the_thin_function_name_the_same_columns() (+2 more)

### Community 238 - "nfl/live_model/tests/test_rush_attempt_pace.py"
Cohesion: 0.06
Nodes (23): Read, pace_ratio(), _sigmoid(), under_prob(), _price(), test_a_line_he_has_already_passed_is_not_a_live_proposition(), test_a_missing_accrued_count_is_refused_not_treated_as_zero(), test_a_reachable_over_is_declined_rather_than_faded() (+15 more)

### Community 24 - "NBA fifth search period shares"
Cohesion: 0.04
Nodes (43): LazyFrames, american(), band_bounds(), band_columns(), blended_ratings(), cell_specs(), control_shuffles(), _cum_before() (+35 more)

### Community 242 - "MLB totals public fade model"
Cohesion: 0.07
Nodes (31): PublicFadeBet, diff(), pitcher_diff(), diff(), pitcher_diff(), numeric_feature_value(), _better_under(), composite_score() (+23 more)

### Community 244 - "MLB weather forecast ingestor"
Cohesion: 0.09
Nodes (11): _Resp, TestTheHourIsTheGamesOwn, TestTheRequestCoversTheTargetHour, _celsius_to_f(), _fetch_open_meteo(), _game_hour_utc(), _target_hour_utc(), _utc_offset_from_lon() (+3 more)

### Community 247 - "tests/test_dk_freshness_parse.py"
Cohesion: 0.12
Nodes (17): _FakeConn, _FakeResult, _american(), parse_dk_payload(), _store(), _payload(), test_a_half_priced_market_is_dropped_rather_than_half_recorded(), test_an_event_with_no_markets_yields_nothing_rather_than_raising() (+9 more)

### Community 249 - "models: slate_concentration + test_slate_concentration"
Cohesion: 0.15
Nodes (15): SlateConcentration, apply_slate_guard(), apply_slate_concentration_guard(), _attr(), _edge_of(), _is_bet(), measure_side_concentration(), _side_of() (+7 more)

### Community 250 - "Sharp book retention during odds pruning"
Cohesion: 0.07
Nodes (14): _RecordingConn, _prop_reference_books(), protected_for(), _thin_book_filter(), test_the_bookmaker_these_rows_use_survives_the_daily_prune(), test_a_shopping_book_is_still_prunable(), test_every_prop_reference_book_is_protected(), test_every_sharp_book_is_protected_in_the_prop_table() (+6 more)

### Community 251 - "View migration lock handling tests"
Cohesion: 0.09
Nodes (23): _Conn, _Deadlock, _LockTimeout, _StatementTimeout, _Syntax, execute(), _before(), _code() (+15 more)

### Community 252 - "Discord pick notifier price fields"
Cohesion: 0.03
Nodes (61): _FakeConn, _sig(), test_a_strictly_better_book_becomes_the_headline(), test_an_equal_or_worse_price_never_replaces_draftkings(), test_best_odds_never_reaches_the_qualifying_gate(), test_draftkings_winning_its_own_shop_is_published_as_draftkings(), test_every_pre_game_producer_computes_good_to(), test_good_to_is_published_when_the_producer_supplies_it() (+53 more)

### Community 26 - "Mobile tracked bets performance"
Cohesion: 0.05
Nodes (60): Props, Props, StakeMode, StakeState, LiveTrackSnapshot, TrackedBetRow, trackedBetStatus, TrackedBetSummary (+52 more)

### Community 260 - "NHL goalie gate refresh tests"
Cohesion: 0.18
Nodes (20): _Fetch, _competitor(), _db(), _df_html(), _espn_docs(), _run(), test_a_back_and_forth_puts_the_first_goalie_back_without_a_key_clash(), test_a_changed_status_fetches_the_athlete_again() (+12 more)

### Community 261 - "NBA game four point estimates"
Cohesion: 0.07
Nodes (36): Point, base_inputs(), cell_specs(), check_cell_count(), derivative_data(), derivative_plan(), derivative_plumbing(), derivative_seasons() (+28 more)

### Community 265 - "Best line threshold sweep"
Cohesion: 0.09
Nodes (13): _Conn, american_to_decimal(), _basis(), units_at(), _row(), test_a_better_price_pays_more_than_the_dk_price(), test_a_loss_costs_one_unit_at_every_price(), test_a_push_is_flat() (+5 more)

### Community 268 - "Settlement CLV timeout retry tests"
Cohesion: 0.10
Nodes (13): _Conn, _fn(), _sql(), test_a_non_timeout_is_not_retried(), test_a_second_timeout_does_not_abort_the_next_statement(), test_a_timeout_is_rolled_back_and_retried_once(), test_one_date_timeout_does_not_drop_the_next_date(), test_query_canceled_with_sqlstate_is_a_timeout() (+5 more)

### Community 269 - "NCAAF college data ingest tests"
Cohesion: 0.07
Nodes (8): _GamesConn, _TeamsConn, test_ingest_games_retains_a_historical_utc_id_and_uses_et_for_a_new_row(), fake_get(), test_ingest_pulls_fbs_then_everyone_and_fbs_rows_win(), test_ingest_retries_everyone_without_a_year_if_the_season_filter_is_empty(), test_prior_context_tolerates_missing_talent_and_returning(), test_weekly_snapshot_build_aborts_on_failed_fetch()

### Community 27 - "Mobile bet slip and parlay legs"
Cohesion: 0.02
Nodes (109): MarketClass, BestBookPrice, BetslipBookQuote, Handoff, LineShop, ParlayMetrics, SavedParlay, SavedParlayLeg (+101 more)

### Community 270 - "NBA pregame scoring window"
Cohesion: 0.08
Nodes (23): PregamePlan, _db(), _decided_by(), _fires(), _job(), _slate(), test_a_close_alone_runs_only_the_close(), test_a_failed_team_total_step_is_an_error_after_publishing() (+15 more)

### Community 273 - "tests/test_prop_odds_utc_stamp.py"
Cohesion: 0.12
Nodes (13): _Conn, _assert_utc_stamp(), _frozen(), _run_mlb(), capture(), events(), _run_ncaaf(), test_an_eastern_row_then_a_later_utc_row_sorts_in_time_order() (+5 more)

### Community 274 - "NHL derivative totals card"
Cohesion: 0.06
Nodes (21): _Meter, _Resp, estimate_credits(), format_plan(), neighbour_clears(), publishable(), main(), run() (+13 more)

### Community 276 - "Price prefilter rollback safety"
Cohesion: 0.06
Nodes (13): _PoisonConn, _fmt_et_time(), get_conn(), query(), main(), _event_index(), _games(), _run() (+5 more)

### Community 277 - "NCAAF walk forward validation"
Cohesion: 0.15
Nodes (12): FoldResult, brier(), calibration_curve(), clv_report(), ece(), kelly_stake(), log_loss(), market_only_sanity() (+4 more)

### Community 278 - "tests/test_feature_artifact_agreement.py"
Cohesion: 0.11
Nodes (13): _Stub, _TolerantUnpickler, _load(), _newest_artifact(), test_artifact_width_matches_its_own_feature_cols(), test_config_list_matches_the_trained_artifact(), test_known_drift_only_names_real_models(), test_pending_features_are_not_live_without_a_retrain() (+5 more)

### Community 279 - "NFL prop market one side per line"
Cohesion: 0.06
Nodes (16): MarketBet, TestMarketCardPublisher, _Conn, best_per_prop(), select_prop(), test_nfl_prop_market_card_drops_a_bet_under_the_floor(), test_wnba_prop_market_card_drops_a_bet_under_the_floor(), test_publish_skips_games_with_no_games_row() (+8 more)

### Community 28 - "Closing line value math"
Cohesion: 0.06
Nodes (28): _Conn, _Res, test_a_one_way_close_is_not_de_vigged(), test_a_worse_close_is_negative_and_equal_prices_are_zero(), test_devigging_the_taken_price_is_not_what_primary_does(), test_kalshi_close_is_not_de_vigged(), test_market_edge_devigs_only_the_close(), test_other_side_prices_include_the_draw_on_a_three_way() (+20 more)

### Community 281 - "tests/test_cloud_retrain_artifacts.py"
Cohesion: 0.10
Nodes (12): _Conn, _restore_artifact(), test_a_failed_upload_does_not_lose_a_model_that_trained(), test_a_missing_artifact_table_is_not_an_error_on_restore(), test_a_no_register_run_stores_nothing(), test_load_model_actually_loads_from_the_store_when_the_file_is_gone(), fetchone(), test_load_model_returns_none_when_the_store_has_nothing_either() (+4 more)

### Community 282 - "NHL side models never bet against each other"
Cohesion: 0.08
Nodes (29): _Conn, _ThreeWay, _apply_side_conflicts(), bets(), _endings_won(), picks_cannot_both_win(), side_checked_models(), ml() (+21 more)

### Community 284 - "Schedule gate publishing tests"
Cohesion: 0.05
Nodes (50): _BoardConn, _Clf, _Clf3, _ClfOver, _PublishConn, _d(), _game(), _mlb() (+42 more)

### Community 285 - "System health and deliverability checks"
Cohesion: 0.05
Nodes (25): HealthReport, ncaaf_season_for_date(), conn(), test_dedupe_and_health_use_the_shared_tuple(), test_the_card_insert_tolerates_the_unique_index(), test_the_widen_migration_is_property_guarded(), test_unique_row_sql_is_key_parts_plus_date_and_side(), still_pre_game() (+17 more)

### Community 286 - "Walk-forward model evaluation harness"
Cohesion: 0.12
Nodes (10): _Cols, _Frame, _fake(), test_a_fold_with_too_little_history_is_skipped(), test_a_single_class_test_season_is_skipped(), _frame(), test_every_fold_trains_only_on_earlier_seasons(), _frame() (+2 more)

### Community 289 - "Player news freshness and pruning"
Cohesion: 0.15
Nodes (7): FakeConn, test_a_fresh_table_is_not_refetched(), test_an_empty_table_is_never_treated_as_fresh(), test_an_unknown_provider_is_refused_rather_than_defaulted(), test_pruning_uses_the_configured_window(), test_the_app_mirrors_the_python_name_fold(), test_timestamps_are_parsed_before_they_are_compared()

### Community 290 - "Prop player name matching"
Cohesion: 0.11
Nodes (13): FakeConn, resolve_feed_name(), test_accented_roster_name_matches_the_flat_feed_name(), test_ambiguity_is_a_miss_not_a_guess(), test_an_unlisted_player_is_still_a_miss(), test_every_prop_lane_keys_line_shopping_on_the_resolved_name(), test_exact_spelling_still_takes_the_fast_path(), test_normalize_folds_only_spelling() (+5 more)

### Community 293 - "Mobile range slider filter"
Cohesion: 0.14
Nodes (25): Props, GestureIntent, Scale, at(), RangeSlider(), applyBound(), grabTarget(), readIntent() (+17 more)

### Community 296 - "MLB batter prop log scoring tests"
Cohesion: 0.10
Nodes (9): _Rec, _ScoringConn, _log_sql(), test_batter_log_scan_is_pinned_to_the_lookback_not_the_catalog(), test_five_models_share_one_log_load(), test_no_lineup_does_not_scan_the_log(), test_starter_log_inside_the_batter_loader_uses_the_same_floor(), test_the_batter_loop_hands_one_cache_to_every_model() (+1 more)

### Community 298 - "tests/test_nfl_wind_publisher.py"
Cohesion: 0.13
Nodes (10): TestBuildRows, TestKickFields, TestParseMatchup, build_rows(), _fmt_line(), kick_fields(), parse_matchup(), test_nfl_wind_and_opener_rows_drop_a_bet_under_the_floor() (+2 more)

### Community 3 - "Odds feed ingestion and quota logging"
Cohesion: 0.01
Nodes (184): Meter, Meter, Meter, FakeResp, TestEveryOtherSportStillMintsItsOwn, TestNflResolvesOntoTheSchedule, TestTheResolverFailsClosed, TestOddsFeedTeamNames (+176 more)

### Community 30 - "NFL in-play prop polling tests"
Cohesion: 0.06
Nodes (26): _FakeOdds, _IdRecordingOdds, _core_worker(), test_a_deployed_bias_must_sit_inside_its_measured_interval(), test_a_matching_board_keeps_the_fast_cadence(), test_a_player_with_no_accrued_count_is_declined_end_to_end(), test_anchor_backs_off_when_the_book_does_not_carry_the_slate(), fetch_anchor() (+18 more)

### Community 300 - "tests/test_health_reason_and_cadence.py"
Cohesion: 0.19
Nodes (11): Report, _one(), test_a_24h_ts_check_reads_as_daily(), test_a_bare_add_still_fills_both_columns(), test_a_broken_query_is_its_own_reason(), test_a_passing_check_says_fresh(), test_a_skipped_check_says_the_gate_was_shut(), test_a_ts_check_reports_its_own_max_age() (+3 more)

### Community 301 - "NBA odds history gap fetching"
Cohesion: 0.08
Nodes (20): _Ledger, _Meter, _Resp, gap_instants(), line_snapshots(), parse_alternates(), _hourly(), _t() (+12 more)

### Community 302 - "tests/test_nfl_weather_supabase_readback.py"
Cohesion: 0.14
Nodes (13): FakeConn, _patch_conn(), _rows(), test_a_null_requested_lead_is_not_returned(), test_a_one_lead_response_is_not_stored(), test_a_partial_window_is_not_returned(), test_a_store_failure_is_a_warning_not_an_error(), test_a_subset_of_leads_reads_only_those_columns() (+5 more)

### Community 307 - "Publish signals on write tests"
Cohesion: 0.06
Nodes (18): _Conn, _body(), _row(), _surfaces(), _make(), test_a_broken_webhook_does_not_suppress_the_push(), test_a_failed_capture_still_delivers(), test_a_publish_failure_does_not_kill_the_tick() (+10 more)

### Community 308 - "Pitcher stats as-of invariant tests"
Cohesion: 0.05
Nodes (29): _FakeConn, last3_rates(), outs_from_ip(), per_nine(), whip(), build_rows(), constant_era_pitcher_seasons(), _row() (+21 more)

### Community 31 - "NBA market-relative prop bet finder"
Cohesion: 0.06
Nodes (33): Roster, ProjectionBet, coherent(), fair_under(), fetch_times(), find_bets(), in_window(), load_quotes() (+25 more)

### Community 312 - "NFL in-play feed resilience tests"
Cohesion: 0.08
Nodes (22): _ScriptedTick, _core_docs(), _core_event(), _fetch(), _run_scripted(), test_a_healthy_payload_raises_no_problems(), test_a_host_switch_is_alerted(), test_a_hunted_game_counts_as_busy() (+14 more)

### Community 314 - "Pipeline log reason tests"
Cohesion: 0.22
Nodes (6): _Conn, _capture(), test_a_false_step_records_the_last_error_it_logged(), test_a_false_step_that_logged_nothing_still_says_so(), test_a_raising_step_still_records_the_exception(), test_the_sink_is_removed_after_the_step()

### Community 315 - "NFL in-play score distribution training"
Cohesion: 0.07
Nodes (20): ScoreDistribution, _cluster_bootstrap(), evaluate(), main(), report(), fit(), load_states(), main() (+12 more)

### Community 316 - "Marketing website build and legal pages"
Cohesion: 0.11
Nodes (24): PlaceholderError, test_ncaaf_live_floors_come_from_the_platform_config(), test_ncaaf_live_floors_are_the_platform_accessor(), assert_public_anon(), _b64url_json(), _blocks(), build(), escape() (+16 more)

### Community 317 - "NCAAF gameday school context"
Cohesion: 0.12
Nodes (15): GameContext, _Conn, _Result, _choose_context(), _fold(), _has_pregame_lines(), load_context(), _night_twin() (+7 more)

### Community 32 - "NBA in-game study two"
Cohesion: 0.07
Nodes (35): StateModel, norm_cdf(), threshold(), apply_model(), benchmark_columns(), decision_quotes(), delta_ci(), _design() (+27 more)

### Community 320 - "NFL scored rows and lock keys"
Cohesion: 0.06
Nodes (14): _After, _LockConn, _Pg, _PgCursor, TestEvalRowsCarryTheLine, TestFlexedKickoffRefreshes, TestNoneRowNeverLocks, _model_lock_key() (+6 more)

### Community 321 - "NFL in-play prop settlement tests"
Cohesion: 0.15
Nodes (14): _SqliteShim, _box(), conn(), _game(), _live_bet(), raw(), _row(), test_a_final_with_no_box_score_yet_waits() (+6 more)

### Community 323 - "NBA prop fetch window planning"
Cohesion: 0.07
Nodes (25): _PlanConn, _fires(), _game(), _jobs(), _plan(), _t(), test_a_projection_too_old_to_price_does_not_block_the_retry(), test_a_tick_fetches_exactly_the_window_games_then_decides_closes_and_publishes() (+17 more)

### Community 331 - "NHL player prop model and backtest"
Cohesion: 0.03
Nodes (66): Spec, TestRegimeOrder, _Conn, TestOnlyTheNewestFetchIsShopped, TestWhoThePlayerIs, _attach_teams(), books(), build_frame() (+58 more)

### Community 332 - "Settlement self-heal and postponed MLB voids"
Cohesion: 0.11
Nodes (25): _FakeStatsapi, _game(), _pick(), test_a_doubleheader_row_with_a_final_keeps_its_picks_grading(), test_a_final_game_is_never_voided(), test_a_game_with_any_box_score_row_is_not_refetched(), test_a_postponed_game_voids_its_pending_bets(), test_a_recent_postponement_waits_for_a_same_day_resumption() (+17 more)

### Community 349 - "tests/test_prop_missing_features.py"
Cohesion: 0.14
Nodes (5): TestARowMissingAFeatureIsNotScored, TestEveryPropLoopGoesThroughTheHelper, TestTheUmpireIsTheDeclaredException, _frame(), helper()

### Community 350 - "Worker job queue run and lock tests"
Cohesion: 0.06
Nodes (24): _Conn, _DedupeConn, _fake(), test_a_busy_queue_claims_nothing(), fetchone(), test_a_declared_job_is_queued_once_however_often_it_is_read(), test_a_failing_job_is_requeued_until_the_attempt_cap(), _boom() (+16 more)

### Community 352 - "NCAAF FBS registry health checks"
Cohesion: 0.12
Nodes (10): TestRefusalLog, TestRegistryHealthCheck, _alarm_part(), _live_db(), _promoted(), _rating(), _registry_check(), _snapshot() (+2 more)

### Community 355 - "NFL in-play pick writer tests"
Cohesion: 0.03
Nodes (53): PicksRecorder, _AvoidConn, _Conn, _Decision, _OpenConn, build_pick(), refuse_publish_reason(), _executor_min_price() (+45 more)

### Community 357 - "NFL in-play pick writer"
Cohesion: 0.10
Nodes (9): TeeRecorder, _is_market_opinion(), _lane_is_locked(), _norm_player(), resolve_game(), resolve_game_id(), test_normalised_player_key_is_the_join_the_prop_system_uses(), test_the_lane_lock_shares_the_scorers_meaning_of_locked() (+1 more)

### Community 361 - "NCAAF live state recording tests"
Cohesion: 0.16
Nodes (13): _Conn, record_live_states(), state_change_row(), state_key(), _state(), test_a_failed_write_never_costs_the_pass(), test_a_score_a_period_or_a_possession_change_is_written(), test_first_sight_is_written() (+5 more)

### Community 363 - "tests/test_run_ledger_orphans.py"
Cohesion: 0.12
Nodes (18): _Conn, db(), _insert_open(), _ledger(), _open_rows(), _row(), test_a_genuine_current_hang_is_still_detectable(), test_a_second_sweep_does_not_abort_the_pass_this_process_started() (+10 more)

### Community 367 - "NFL opener and NCAAF calibration tests"
Cohesion: 0.09
Nodes (10): TestTickLatency, label(), test_the_tick_passes_a_days_that_covers_the_whole_window(), test_the_tick_returns_free_outside_the_window(), test_the_twelve_distributional_models_score_off_the_ticks_own_fetch(), test_a_game_is_decided_only_when_every_step_finished(), test_a_tick_polls_then_decides_the_newly_known_games(), test_a_tick_whose_game_odds_fetch_failed_decides_no_side_or_total() (+2 more)

### Community 37 - "NBA lineup stints from play-by-play"
Cohesion: 0.05
Nodes (48): Diagnostics, _Seg, alias_play_ids(), score_plays(), _accumulate(), _add_one(), _and_one_follows(), appearances() (+40 more)

### Community 373 - "NCAAF opponent-adjusted search features"
Cohesion: 0.09
Nodes (18): AdjRatings, blended_rating(), build_adjusted_ratings(), build_prior_season_ratings(), fit_opponent_adjustment(), rolling_variants(), _synth(), test_blend_falls_back_when_one_side_missing() (+10 more)

### Community 376 - "In-play calibrated decision tests"
Cohesion: 0.09
Nodes (16): RecordingConn, fetch_graded(), _cut(), _signal(), test_a_big_enough_claim_still_fires_after_calibration(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(), test_a_hot_live_model_no_longer_fires_the_marginal_bet(), test_a_live_model_is_read_out_of_picks_not_the_matview() (+8 more)

### Community 378 - "Team total market decision tests"
Cohesion: 0.11
Nodes (11): _SqliteShim, raw(), _result(), test_an_away_team_total_settles_on_the_away_team_s_points(), test_an_overtime_final_counts_and_a_full_game_total_would_not(), test_no_line_is_no_action_not_a_guess(), test_the_full_game_total_label_is_unchanged(), test_the_label_names_the_team_and_says_team_total() (+3 more)

### Community 38 - "Shared database connection and paper tracking"
Cohesion: 0.01
Nodes (250): ConnectionLost, DBConnection, BatchWriter, FetchFailed, GameMeta, FrontierUnreadable, live_slate_dates(), call_in_savepoint() (+242 more)

### Community 381 - "NBA odds history and news window"
Cohesion: 0.07
Nodes (26): _Resp, read_instants(), asof_mpg(), events(), load_cache(), player_minutes(), team_changes(), _asof() (+18 more)

### Community 385 - "Any-book first five line scoring"
Cohesion: 0.13
Nodes (16): _Clf, _cut(), _mlb_feat(), _on(), _spreads_row(), _src(), test_a_non_dk_f5_spread_pick_keeps_dk_columns_null(), test_a_non_dk_f5_total_pick_keeps_dk_columns_null() (+8 more)

### Community 387 - "tests/test_repair_bogus_first_pitch_labels.py"
Cohesion: 0.13
Nodes (8): _Conn, _run(), test_a_dry_run_writes_nothing_at_all(), test_a_short_backup_rolls_back_and_relabels_nothing(), test_the_backup_is_written_before_the_update(), test_the_backup_table_is_revoked_from_the_public_roles(), test_the_bogus_set_is_computed_never_listed(), test_the_query_is_scoped_to_the_scheduled_start_not_the_derived_one()

### Community 39 - "nfl/live_model/tests/test_executor.py"
Cohesion: 0.06
Nodes (45): Decision, Executor, derivative_lag(), ev_floor(), _mk(), expected_value(), honest_probability(), is_hunt_state() (+37 more)

### Community 393 - "tests/test_sbr_loader.py"
Cohesion: 0.12
Nodes (5): _SqliteConnShim, _SqliteCursorShim, canonical_abbrev(), loader_conn(), test_sbr_abbreviations_are_canonicalised_for_mlb_only()

### Community 397 - "mobile/scripts/ux_scan.mts"
Cohesion: 0.16
Nodes (18): Finding, Severity, changedFiles(), entitlementGate(), fontScaling(), fontSizeLiterals(), hexColors(), main() (+10 more)

### Community 398 - "NBA schedule refresh"
Cohesion: 0.10
Nodes (14): _HealthConn, event_rows(), _to_int(), _by_gid(), test_a_date_with_no_tip_yet_is_stored_without_one(), test_a_feed_that_has_not_moved_yet_never_moves_the_tip(), test_a_moved_tip_reaches_the_schedule_when_the_feed_lists_the_books_start(), test_a_postponed_game_is_read_as_postponed() (+6 more)

### Community 4 - "Player prop box score backfill"
Cohesion: 0.09
Nodes (18): GradeConn, ScriptConn, ensure_prop_box_scores(), missing_prop_games(), _pick(), test_a_logged_game_is_not_fetched_and_a_goalie_gap_is(), test_a_non_timeout_prop_error_rolls_back_and_raises(), test_a_probe_error_that_is_not_a_timeout_raises_after_rollback() (+10 more)

### Community 40 - "Mobile player stats and game log"
Cohesion: 0.02
Nodes (166): Section, Args, PlayerStatKey, BookQuote, H2HMeeting, playerHeadToHead, PlayerPickLine, playerPickRecord (+158 more)

### Community 403 - "Database cursor and lock wrapper"
Cohesion: 0.11
Nodes (5): _CursorResult, execute(), test_the_cursor_wrapper_rowcount_is_the_cursors(), test_a_dropped_connection_replays_the_migration_with_its_lock_timeout(), cursor()

### Community 41 - "tests/test_live_quote_staleness.py"
Cohesion: 0.04
Nodes (45): ScoreClock, _Conn, _Q, build_row(), quote_from_nfl_quotes(), rows_from_quote(), _abbrev(), rows_for_quotes() (+37 more)

### Community 410 - "NBA prop closing line purchase tests"
Cohesion: 0.09
Nodes (11): _Conn, _Resp, test_a_close_already_held_is_not_bought_again(), test_a_due_close_buys_one_call_of_the_bet_markets_and_reports_its_credits(), test_a_pass_outside_the_window_spends_nothing(), test_only_a_game_holding_a_bet_and_only_once(), test_only_twelve_to_twenty_five_minutes_before_tip(), test_the_ten_minute_evening_passes_always_land_one_inside() (+3 more)

### Community 412 - "NBA prop settlement stats tests"
Cohesion: 0.11
Nodes (9): _SelectConn, test_a_missing_stat_is_none_not_zero(), test_a_turnovers_bet_on_a_player_who_played_settles_win_not_no_action(), test_combo_markets_are_mapped_to_helpers_and_only_the_nba_rule_uses_them(), test_double_double_matches_the_rule_it_replaced(), test_the_loader_carries_every_stat_a_market_settles_on(), test_the_loader_selects_turnovers(), _load_nba_prop_actuals() (+1 more)

### Community 416 - "NFL pass attempt over bias"
Cohesion: 0.09
Nodes (11): Read, blind_over_prob(), over_prob(), _pass_attempt_bias_allowed(), test_blind_arm_no_longer_asserts_a_rate(), test_restoring_a_bias_is_one_constant(), test_the_gates_are_checked_before_the_no_bias_decline(), test_the_interval_spans_zero_so_the_lane_declines_to_price() (+3 more)

### Community 417 - "In-play publish parity with pauses"
Cohesion: 0.17
Nodes (12): _Conn, _db(), _labels(), _pick(), test_a_bet_written_while_paused_is_not_announced_after_an_unpause(), test_a_live_health_state_still_publishes(), test_a_paused_model_is_not_announced(), test_a_retired_model_is_not_announced() (+4 more)

### Community 419 - "CLV backfill job tests"
Cohesion: 0.15
Nodes (5): _Conn, _stub_backfill(), test_hard_cap_stops_a_nonempty_queue(), test_loops_until_a_pass_fills_nothing(), test_the_runner_opens_get_connection_and_calls_backfill_clv()

### Community 421 - "NBA injury report fetch tests"
Cohesion: 0.12
Nodes (12): _Conn, _PdfFetcher, _content_of_fixture(), test_a_changed_report_stores_its_rows(), __init__(), test_a_garbled_report_writes_its_ledger_row_and_no_rows(), test_a_repeat_of_a_repeat_points_at_the_report_that_holds_the_rows(), test_a_report_identical_to_its_predecessor_stores_no_rows_and_points_at_it() (+4 more)

### Community 424 - "supabase/functions/_shared/discord.ts"
Cohesion: 0.20
Nodes (15): DiscordApiError, DiscordUser, RoleSyncResult, addAppRole(), addGuildMember(), botFetch(), expectOk(), isGuildMember() (+7 more)

### Community 43 - "Worker job queue validation tests"
Cohesion: 0.03
Nodes (48): _VoidConn, _posted_row(), _quiet(), _run_void(), _run_void_job(), test_a_failed_job_needs_a_new_key_to_rerun(), test_a_graded_pick_is_refused_not_rewritten(), test_a_pick_that_does_not_exist_is_reported_as_missing() (+40 more)

### Community 430 - "NCAAF in-play locked bet writes"
Cohesion: 0.14
Nodes (12): FakeConn, _Rows, write_picks(), db(), test_both_lanes_locked_touches_nothing(), test_dry_run_never_touches_db(), test_first_bet_is_written_and_will_lock(), test_flag_off_restores_delete_and_replace() (+4 more)

### Community 434 - "NFL wind publisher scored rows tests"
Cohesion: 0.09
Nodes (8): TestBuildScoredRows, TestPickEmLabel, TestPreflightLockChecks, TestQualifyingRowIsNotANoneRow, _american_to_prob(), build_scored_rows(), _fmt_spread(), latest_eval_rows()

### Community 439 - "NHL goalie confirmation guards"
Cohesion: 0.08
Nodes (10): _CardDB, _HeartbeatDB, _NullIdDB, _Rows, test_a_goalie_row_with_no_nhl_id_is_not_bet_on_the_last_starters_form(), test_a_stopped_window_is_reported_within_half_an_hour_while_it_should_run(), test_shots_on_goal_writes_a_bet_on_an_unknown_game_at_its_opening_fetch(), score_market() (+2 more)

### Community 440 - "NFL line snapshot row writing"
Cohesion: 0.15
Nodes (6): TestPublishLineSnapshots, TestSnapshotRowParams, snapshot_row_params(), _csv_row(), execute(), _write_snapshot_csv()

### Community 443 - "NFL opener fire window tests"
Cohesion: 0.14
Nodes (5): TestFireWindow, _db_row(), _feed_schedule(), _evaluate(), _select()

### Community 445 - "NHL anchored moneyline input tests"
Cohesion: 0.09
Nodes (16): _Fixed, _GamesConn, _logs(), _served(), test_a_later_result_cannot_reach_an_earlier_game(), test_a_matinee_is_not_decided_once_it_has_started(), test_a_missing_input_skips_the_game(), test_a_scheduled_game_missing_from_the_logs_marks_both_teams_stale() (+8 more)

### Community 446 - "Schema change guard on startup"
Cohesion: 0.09
Nodes (9): GuardConn, _ddl(), _kickoff_wind(), test_ddl_still_runs_on_a_database_that_needs_it(), test_guard_rolls_back_a_failed_probe(), __init__(), test_kickoff_wind_reads_still_creates_then_reads_when_the_table_is_missing(), test_kickoff_wind_reads_still_writes_and_reads_when_ddl_is_skipped() (+1 more)

### Community 448 - "tests/test_discord_channel_probe.py"
Cohesion: 0.17
Nodes (7): _Resp, test_the_probe_covers_the_per_sport_live_channels(), test_the_probe_never_posts_and_never_returns_the_url(), test_the_probe_reports_the_channel_behind_each_sport(), _get(), test_two_sports_sharing_a_channel_are_flagged(), _job_discord_probe()

### Community 45 - "tests/test_nfl_prop_one_read_per_game.py"
Cohesion: 0.06
Nodes (25): _Conn, _Log, publish_hour_missed(), publishable_games(), _at(), _games(), test_a_game_is_publishable_on_exactly_one_pass_in_its_window(), test_a_game_with_no_kickoff_is_never_published() (+17 more)

### Community 450 - "Bounded prune failure handling"
Cohesion: 0.12
Nodes (6): _Counted, Timeout, test_a_failed_prune_is_reported_as_a_failed_step(), test_a_record_write_that_fails_for_a_bug_fails_the_table(), execute(), __init__()

### Community 469 - "Multi-book odds fetch tests"
Cohesion: 0.06
Nodes (20): _OddsConn, _odds_query(), _prop_markets(), _source(), test_a_game_with_no_commence_time_keeps_every_row(), test_closing_line_reads_name_the_book(), test_draftkings_is_always_first_line_shop_book(), test_feature_engines_whitelist_draftkings() (+12 more)

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

### Community 475 - "Player news and name normalization"
Cohesion: 0.04
Nodes (47): NewsItem, NewsPlayer, LazyConnection, season_fallback(), _athletes_in(), ingest_player_news(), main(), _minutes_since_last_ingest() (+39 more)

### Community 478 - "Any-book first five innings lines"
Cohesion: 0.15
Nodes (15): _GameOddsConn, _fallback_game_line_quote(), _get_scoring_odds(), _has_real_game_price(), test_a_quote_after_first_pitch_does_not_score(), test_draftkings_is_not_asked_twice(), test_fanduel_sets_the_f5_total_when_draftkings_has_none(), test_full_game_totals_do_not_use_the_f5_fallback() (+7 more)

### Community 48 - "tests/test_calibration_watch.py"
Cohesion: 0.06
Nodes (14): _Conn, _Res, TestDormantLiveModels, TestRosterChanges, TestTheRun, TestVerdictChanges, TestVolumeShifts, _row() (+6 more)

### Community 480 - "NCAAF in-play history backtest"
Cohesion: 0.11
Nodes (16): _StubEngine, first_signals(), grade(), _cand(), _event(), _no_db_school_lookup(), test_a_late_kickoff_falls_back_to_its_utc_dated_games_row(), test_a_market_filter_writes_only_that_market() (+8 more)

### Community 485 - "NFL weather edge research"
Cohesion: 0.08
Nodes (28): DailyLimit, Pacer, audit(), baseline(), bh(), boot(), classify(), era() (+20 more)

### Community 486 - "NBA schedule refresh fallback tests"
Cohesion: 0.13
Nodes (7): _Conn, _board(), test_a_dry_run_reads_and_writes_nothing(), test_a_run_stamps_every_row_espn_confirmed(), test_an_empty_answer_for_a_month_the_schedule_fills_is_a_failure_not_a_wipe(), test_one_failed_month_is_left_as_stored_and_the_rest_are_written(), get()

### Community 49 - "Pipeline failure alert rules"
Cohesion: 0.14
Nodes (5): FakeConn, TestHealthCheckOnlyIsNotADirtyPass, TestWhatCountsAsAFailure, _clean_rate(), _conditions()

### Community 497 - "Publish key identity checks"
Cohesion: 0.05
Nodes (22): _Conn, _KeyConn, _key(), _mobile(), _sql(), test_a_game_level_live_row_keeps_the_key_it_was_published_under(), test_a_game_level_row_keeps_the_key_it_was_published_under(), test_a_player_id_row_keeps_the_key_it_was_published_under() (+14 more)

### Community 498 - "tests/test_sbr_loader.py"
Cohesion: 0.22
Nodes (4): TestSafeFloat, parse_csv_file(), parse_sbr_file(), _safe_float()

### Community 499 - "NHL totals market card"
Cohesion: 0.05
Nodes (35): NhlTotalBet, _LockConn, _SlateConn, implied(), _coherent(), _fetch_ts(), find_bets(), load_fetch_quotes() (+27 more)

### Community 5 - "Mobile app screens and theme"
Cohesion: 0.02
Nodes (341): Props, Props, State, Nav, Props, Props, Props, FilterChipProps (+333 more)

### Community 504 - "Scratch Postgres migration test harness"
Cohesion: 0.03
Nodes (76): ScratchPostgres, _identity_maps(), _platform_gates_off(), pg_bin(), _code(), test_scratch_backtest_defaults_to_the_current_season_and_filters(), test_the_function_is_invoker_and_has_no_price_or_line_filter(), _code() (+68 more)

### Community 510 - "NBA injury report ingestion"
Cohesion: 0.08
Nodes (27): Fetcher, content_hash(), ensure_tables(), load_players(), load_schedule(), main(), norm_name(), previous_report() (+19 more)

### Community 512 - "External threshold map promotion"
Cohesion: 0.16
Nodes (5): _Conn, promote_external(), test_external_promotion_refuses_a_map_that_does_not_transfer(), test_external_promotion_writes_only_the_promoted_columns(), test_the_scorer_reads_the_external_map_like_any_promoted_one()

### Community 514 - "NHL goalie matchup assessment"
Cohesion: 0.13
Nodes (15): Matchup, assess(), matchup_states(), _select(), _latest(), test_a_confirmation_no_poll_has_read_lately_is_not_known(), test_a_dailyfaceoff_name_too_old_to_be_read_no_longer_vetoes(), test_a_goalie_row_that_names_someone_else_is_not_known() (+7 more)

### Community 519 - "Social post publishing"
Cohesion: 0.12
Nodes (6): _Rows, _creds(), test_a_5xx_is_transport_and_not_a_tweet_id(), test_a_missing_table_is_a_no_op(), test_allow_link_is_off_on_the_pick_client(), _post()

### Community 52 - "In-play best line price tests"
Cohesion: 0.04
Nodes (44): _FakeConn, _best_live_price(), _best_live_side(), _live_book_quotes(), _live_quote_is_on_offer(), best_takeable_quote(), _ev(), _live_pick() (+36 more)

### Community 524 - "Game feature engines across sports"
Cohesion: 0.01
Nodes (138): TestPregameSnapshotGuard, TestFbsGate, TestAmericanToDecimalScorer, trusted_first_pitch(), _blk_bullpen_ip(), _blk_injuries(), _blk_nhl_loc_goals(), _blk_nhl_rolling_goals() (+130 more)

### Community 525 - "Mobile custom model builder client"
Cohesion: 0.18
Nodes (23): ByomBacktestRow, ByomModel, ByomSnapshot, byomFilters, useByomBacktest(), useByomModels(), asRecord(), asRows() (+15 more)

### Community 526 - "NCAAF college data refresh and backfill tests"
Cohesion: 0.20
Nodes (6): _NullConn, test_backfill_returns_totals_when_every_season_succeeds(), test_backfill_survives_a_mid_run_season_failure(), test_refresh_games_happy_path_counts_games(), test_refresh_games_repairs_every_season_and_reports_failures(), test_refresh_stats_isolates_a_failing_season()

### Community 528 - "UFC fight stats ingest tests"
Cohesion: 0.11
Nodes (7): _IngestConn, _ingest(), _one_fight_event(), test_a_late_replacement_is_not_scored_on_the_original_booking(), test_a_misspelled_fighter_is_scored_for_the_side_they_fought_on(), test_a_row_naming_neither_fighter_is_left_unscored(), test_the_same_fight_stored_twice_is_scored_on_both_rows_each_way_round()

### Community 53 - "Mobile team detail and stats odds queries"
Cohesion: 0.02
Nodes (211): Props, FighterSide, Props, Props, LivePicksState, Args, PlayerNewsState, PropContext (+203 more)

### Community 531 - "Honest EV and per model floors"
Cohesion: 0.05
Nodes (21): Gate, TestTheCard, expected_value(), min_ev_for(), honest_probability(), test_ncaaf_live_ev_floor_is_wired_from_config(), pick_rows(), test_expected_value_is_on_the_quoted_price() (+13 more)

### Community 533 - "NBA team total odds fetch tests"
Cohesion: 0.05
Nodes (47): Clock, FakeFeed, closes_taken(), event_rows(), fetch_team_totals(), fetches(), _known_games(), ledger_exists() (+39 more)

### Community 537 - "Discord stake sizing parity"
Cohesion: 0.11
Nodes (12): UnitStake, test_flat_conviction_is_still_price_adjusted(), test_the_minus_110_example_matt_gave(), test_units_format_drops_the_trailing_zero(), test_units_format_keeps_the_second_decimal(), test_unpriced_picks_publish_conviction_and_claim_no_payout(), _doc(), _rows() (+4 more)

### Community 538 - "NFL opener bettable books tests"
Cohesion: 0.20
Nodes (5): TestBettableBooksOnly, TestSelectOpenerBets, _both_sides(), _frame(), _sched()

### Community 54 - "tests/test_void_picks.py"
Cohesion: 0.05
Nodes (18): _FakeConn, TestAPostedSignalIsLocked, TestAPostedVoidAnnouncesAfterCommit, TestTheGradedOptIn, TestVoidingAPostedPickIsAnExplicitOptIn, TestWhatMayBeVoided, TestWhatTheVoidWrites, announce_posted_voids() (+10 more)

### Community 541 - "MLB final score twin lookup"
Cohesion: 0.21
Nodes (9): _Conn, _Cur, _lookup_home_won(), mlb_game_final(), sbr_twin_id(), test_no_final_anywhere_is_none(), test_scored_canonical_row_wins_and_keeps_its_label(), test_twin_id_swaps_only_the_renamed_franchises() (+1 more)

### Community 544 - "NBA team total odds fake database"
Cohesion: 0.09
Nodes (9): TeamTotalBet, _Cur, FakeDB, pick_label(), pick_rows(), _bet(), test_a_label_that_disagrees_with_its_team_is_refused(), test_a_paused_model_s_rows_carry_the_paused_marker() (+1 more)

### Community 545 - "Job heartbeat and stale jobs"
Cohesion: 0.15
Nodes (8): Conn, _build(), test_a_job_marked_disabled_is_not_silent(), test_a_job_that_runs_here_is_not_marked(), test_a_service_leaves_alone_the_jobs_another_service_owns(), test_startup_marks_an_owned_job_that_is_switched_off(), allowed_silence(), stale_jobs()

### Community 550 - "Failure alert delivery and recovery"
Cohesion: 0.19
Nodes (5): TestDeliveryAndNoise, TestItCannotBreakTheWorker, _posts(), _state_dir(), run_failure_alerter()

### Community 551 - "NBA ingestor shared imports"
Cohesion: 0.01
Nodes (148): Plan, lock_down(), _fetchone(), schema_is_current(), et_date(), nba_team(), parse_nba_box(), parse_nba_dnp() (+140 more)

### Community 554 - "NBA box score repair tests"
Cohesion: 0.14
Nodes (7): _Conn, _logs(), _run(), test_a_box_that_does_not_add_up_is_never_written(), test_a_game_nba_com_does_not_list_is_refused(), test_only_the_named_game_is_replaced_delete_first(), test_the_season_repair_names_every_missing_or_wrong_box()

### Community 559 - "NFL look-ahead and live bet keys"
Cohesion: 0.03
Nodes (48): _Conn, test_the_restate_producer_keeps_the_first_bet_only(), _stmts(), test_it_deletes_exactly_the_three_measured_lock_keys(), test_it_does_not_touch_picks_or_discord(), test_it_still_skips_a_key_that_has_a_standing_bet(), test_migration_is_one_statement(), test_standing_pick_uses_lock_key_sql_not_player_id() (+40 more)

### Community 56 - "tests/test_daily_retry.py"
Cohesion: 0.06
Nodes (42): _Conn, _Cursor, _FrozenDatetime, DailyRun, _aborted(), _aborted_row(), _ok(), _ok_row() (+34 more)

### Community 561 - "UFC pregame price age tests"
Cohesion: 0.13
Nodes (8): _UfcBoardConn, _ago(), _score_card(), test_a_bet_on_either_id_locks_the_model_for_both(), test_a_never_priced_id_is_not_scored_beside_its_priced_twin(), test_the_chosen_id_still_borrows_a_market_only_its_twin_carries(), test_two_current_ids_of_one_fight_score_only_the_newer(), _ufc_game()

### Community 562 - "Results recap message id tests"
Cohesion: 0.05
Nodes (15): _Conn, _Ledger, _Resp, _silence_alert(), test_a_204_with_no_id_is_not_a_finished_recap(), test_a_failed_error_insert_rolls_back_before_the_read(), test_a_posted_recap_ledgers_the_id_wait_returned(), test_a_rejected_post_is_recorded_and_the_next_pass_sends() (+7 more)

### Community 564 - "Current injury status replacement"
Cohesion: 0.17
Nodes (13): FakeConn, current_status_rows(), _replace_current_status(), _row(), test_a_current_status_failure_cannot_cost_the_log(), test_a_degraded_pull_only_replaces_the_teams_that_answered(), test_a_healthy_pull_replaces_the_whole_sport(), test_a_player_listed_twice_keeps_the_worse_status() (+5 more)

### Community 565 - "NCAAF schedule rest context"
Cohesion: 0.17
Nodes (10): GameRow, Rules, _final(), _is_listing(), participants(), rest_days_as_of_kickoff(), _rows(), _same_series_game() (+2 more)

### Community 566 - "Odds repeat thinning keeps NBA rows"
Cohesion: 0.16
Nodes (9): _Conn, thin_repeats(), test_a_dry_run_counts_and_deletes_nothing(), test_an_unchanged_run_keeps_its_first_and_last_row(), test_every_move_survives_and_every_as_of_price_is_unchanged(), test_paid_history_todays_games_and_other_sports_are_untouched(), test_pre_game_and_in_play_are_separate_runs(), test_protected_books_keep_every_repeated_row() (+1 more)

### Community 568 - "NFL wind forecast cards"
Cohesion: 0.02
Nodes (98): OddsAPIClient, SnapshotResult, OpenMeteoError, game_index(), main(), resolve(), rows_from_file(), stored_pairs() (+90 more)

### Community 57 - "tests/test_live_book_move_guard.py"
Cohesion: 0.08
Nodes (34): BookMoveClock, _MlbConn, american_to_implied(), _at(), _delaware_ctx(), _dk(), _iso(), _mlb_odds() (+26 more)

### Community 570 - "NHL player props card tests"
Cohesion: 0.04
Nodes (24): _Shim, TestEveryLiveModelIsWiredEverywhere, TestInsertOnce, TestSettlement, TestTheBacktestGradesTheRuleTheCardPlays, TestTheCard, TestTheDistribution, TestTheGoalieFrame (+16 more)

### Community 575 - "NCAAF research dataset building"
Cohesion: 0.16
Nodes (8): LabelSet, build_label_set(), _fetch_lines(), _fetch_raw(), opener_coverage(), _pick_provider(), provider_continuity(), main()

### Community 58 - "Social post queue and drain"
Cohesion: 0.08
Nodes (40): QueueRejected, test_enqueue_inserts_a_thread_and_refuses_a_second_copy(), test_enqueue_refuses_a_url_unless_allow_link_is_set(), test_enqueue_stores_images_and_a_reply_target(), test_the_cli_can_enqueue_one_image_without_posting(), _actionable(), _as_utc(), _attach_media() (+32 more)

### Community 582 - "Recap, line alert and X results tests"
Cohesion: 0.06
Nodes (16): _Conn, test_a_malformed_date_is_refused_before_anything_runs(), test_the_job_does_not_bypass_the_day_is_over_guard(), test_the_job_does_not_read_rowcount_off_the_cursor(), test_the_job_only_clears_its_own_ledger_kind(), _daily(), _job_body(), test_a_malformed_date_is_refused_before_anything_runs() (+8 more)

### Community 583 - "NFL pick monitor"
Cohesion: 0.19
Nodes (6): TestClassify, TestImmutabilityContract, TestLatestPerPick, classify(), latest_per_pick(), _row()

### Community 584 - "In-play game clock alignment"
Cohesion: 0.24
Nodes (6): GameClock, _t(), test_before_first_pitch_and_after_last_play_are_not_priced(), test_between_pas_across_third_out_rolls_over_to_next_half(), test_mid_plate_appearance_is_that_pa_before_state(), test_plays_without_times_are_ignored()

### Community 585 - "NHL expected goals model fit"
Cohesion: 0.17
Nodes (10): BoostedXG, LogitXG, build_features(), fit_and_compare(), _lr_design(), model_mask(), _obj(), season_metrics() (+2 more)

### Community 588 - "Ungraded model performance tests"
Cohesion: 0.08
Nodes (12): FakeConn, test_perf_reads_the_matview_not_the_expensive_view(), test_roster_reports_a_registered_but_untrained_model(), _second_arm(), _sql(), test_a_fully_unpriced_recovered_model_reports_no_roi(), test_a_recovered_row_still_reports_roi_over_the_priced_bets(), test_both_arms_stay_inside_the_settled_bet_gate() (+4 more)

### Community 590 - "Prop odds missing game insert tests"
Cohesion: 0.11
Nodes (6): FakeConn, _is_missing_game_fk(), _run(), test_event_with_no_games_row_is_skipped_and_others_still_insert(), test_fk_on_insert_does_not_unwrite_the_events_that_already_landed(), test_is_missing_game_fk_matches_the_production_error()

### Community 591 - "Threshold review schema setup"
Cohesion: 0.10
Nodes (7): _DdlConn, _DdlRes, table(), test_a_failed_lock_down_does_not_lose_the_table(), test_ensure_schema_commits_the_tables_it_creates(), test_the_tables_are_locked_down_at_the_create_site(), ensure_schema()

### Community 592 - "NHL goalie confirmation timing tests"
Cohesion: 0.10
Nodes (11): _Fixed, _ThreeWay, _side(), test_a_listed_goalie_is_not_a_confirmed_one(), test_a_pass_does_not_hold_the_window_lock_while_it_runs(), test_a_side_model_decides_once_both_goalies_are_confirmed_whatever_the_clock(), test_a_tick_does_nothing_while_a_refresh_pass_or_the_daily_run_runs(), test_known_but_last_nights_logs_missing_still_waits() (+3 more)

### Community 595 - "NHL blocked shots prop settlement tests"
Cohesion: 0.27
Nodes (5): _Shim, TestSettlement, _bet(), _played(), _result()

### Community 597 - "Pregame insert cutoff tests"
Cohesion: 0.15
Nodes (11): _Conn, clock(), _rejected(), _row(), test_a_failed_cutoff_read_keeps_the_row(), test_a_live_row_is_inserted_and_not_looked_up(), test_a_live_row_stays_when_the_pregame_cutoff_has_passed(), test_a_row_at_or_after_the_cutoff_is_rejected_and_logged() (+3 more)

### Community 599 - "System health check test fixtures"
Cohesion: 0.12
Nodes (5): _FrozenDatetime, _Shim, db(), mlb_wired(), test_the_run_reports_whether_the_nba_schedule_is_being_refreshed()

### Community 6 - "Mobile custom model filters and thresholds"
Cohesion: 0.02
Nodes (229): Case, BacktestPickRow, CustomModelStats, ChipGroup, ChipKey, FilterablePick, BetTypeChoice, BetTypeOption (+221 more)

### Community 601 - "Team stats live season span checks"
Cohesion: 0.13
Nodes (6): _SeasonConn, test_verify_established_live_season_with_two_snapshots_stays_thin(), test_verify_five_day_span_with_one_snapshot_is_thin(), test_verify_four_day_opening_span_is_still_grace(), test_verify_opening_live_season_is_not_thin(), test_verify_short_historical_season_is_still_thin()

### Community 606 - "Pregame price age clock tests"
Cohesion: 0.12
Nodes (8): _TwoIdConn, _clock(), _h2h_row(), test_a_copy_that_was_never_priced_still_reads_the_other_orientation(), test_the_abandoned_copy_of_a_fight_does_not_borrow_the_live_copys_price(), test_the_app_applies_the_same_bound(), test_the_best_price_shop_follows_the_same_rule(), test_the_card_passes_its_clock_to_the_rule()

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

### Community 620 - "NFL closing line backtest features"
Cohesion: 0.14
Nodes (9): ShrunkEnsemble, add_form(), build(), feature_columns(), market_features(), team_game_stats(), fmt(), main() (+1 more)

### Community 621 - "NFL opener pick insert once"
Cohesion: 0.12
Nodes (8): TestBuildOpenerRows, TestPublishOpenerInsertOnce, build_opener_rows(), _opener_model(), _taken_at(), _card_row(), _row(), execute()

### Community 622 - "WNBA injury team lookup fallback"
Cohesion: 0.28
Nodes (4): TestCoreTeamsFallback, _fetch_wnba_espn_team_ids_core(), _fake_fetch(), _listing()

### Community 628 - "NBA results store and windows"
Cohesion: 0.13
Nodes (5): PgStore, _games(), _postponed(), _schedule(), end()

### Community 633 - "Schedule events and odds pruning joins"
Cohesion: 0.17
Nodes (8): Event, failed(), _before(), _clock(), _day(), _joins(), _log_check(), logged()

### Community 644 - "MLB prop market pregame sweep"
Cohesion: 0.12
Nodes (8): _Conn, load_quotes(), test_a_game_with_no_cutoff_fails_open(), test_both_market_relative_loaders_bound_on_the_cutoff(), test_it_compares_parsed_timestamps_not_strings(), test_it_joins_games_and_uses_the_shared_cutoff(), test_the_newest_qualifying_quote_still_wins(), test_the_post_first_pitch_quote_is_dropped_even_though_it_is_newest()

### Community 647 - "Injury adjustment feature tests"
Cohesion: 0.16
Nodes (4): TestComputeInjuryAdjustment, TestMarketForOdds, _compute_injury_adjustment(), _market_for_odds()

### Community 65 - "NBA player prop model"
Cohesion: 0.03
Nodes (84): Spec, asof_roster(), collapse_official(), compact_report(), minutes_cols(), predict_means(), rate_cols(), worker_data() (+76 more)

### Community 650 - "Mobile matchup and stats verify scripts"
Cohesion: 0.07
Nodes (47): MatchupInfo, TonightMatchupRow, check(), fakeServer(), main(), read(), check(), grade() (+39 more)

### Community 651 - "Rule model card tests"
Cohesion: 0.06
Nodes (20): TestTheCardFilters, TestTheListIsShared, _et(), _game(), _jobs(), test_a_fetch_that_stored_nothing_exits_non_zero(), test_a_schedule_placeholder_with_no_teams_is_never_planned(), test_a_tick_fetches_then_decides_then_publishes_each_step_bounded() (+12 more)

### Community 655 - "Game result target computation tests"
Cohesion: 0.17
Nodes (5): TestComputeTarget, _compute_target(), test_a_push_yields_no_target(), test_spread_target_uses_the_home_relative_line(), test_totals_and_moneyline_targets()

### Community 658 - "NBA official injury report PDF parser"
Cohesion: 0.18
Nodes (9): Report, finish_rows(), parse_pdf(), parse_title(), rows_from_pages(), season_of(), test_finish_rows_builds_our_game_id_and_season(), test_report_time_comes_from_the_header_and_is_stored_in_utc() (+1 more)

### Community 660 - "MLB doubleheader twin game merge"
Cohesion: 0.15
Nodes (9): _Conn, canonical(), counts(), test_a_canonical_id_maps_to_nothing(), test_a_non_mlb_or_malformed_id_is_left_alone(), test_an_empty_scope_counts_zero_rather_than_none(), test_both_teams_are_mapped_in_one_id(), test_only_the_four_renamed_franchises_map() (+1 more)

### Community 668 - "NBA public splits archiving tests"
Cohesion: 0.12
Nodes (6): _NoDB, _Store, _scoreboard(), test_a_late_game_still_in_play_after_midnight_is_archived_at_the_next_pass(), test_a_stored_game_is_not_written_again_and_a_splitless_game_is_retried(), _wire_archive()

### Community 67 - "tests/test_game_market_gate.py"
Cohesion: 0.06
Nodes (50): GateVerdict, MarketBookend, PublicSplits, apply_to_picks(), _as_float(), bookend_from_odds(), evaluate(), fair_prob() (+42 more)

### Community 670 - "NBA team total closing line tests"
Cohesion: 0.08
Nodes (15): _SnapConn, _book(), _capture(), _lateral(), _oc(), _quotes(), _team_total_pick(), test_a_close_at_the_same_number_is_graded_against_the_bet_book_s_close() (+7 more)

### Community 673 - "NFL prop stat distribution tests"
Cohesion: 0.12
Nodes (4): TestBinaryMarket, TestCountDistributions, TestYardageDistribution, _art()

### Community 674 - "NBA public splits quality backfill"
Cohesion: 0.18
Nodes (5): _CountingConn, backfill_quality(), test_an_existing_table_gets_the_quality_column(), test_the_backfill_adds_the_column_and_commits_once(), test_the_backfill_rolls_back_when_a_count_is_not_what_was_measured()

### Community 675 - "Pipeline watch findings and alerts"
Cohesion: 0.06
Nodes (30): _Conn, test_a_clean_pass_produces_no_finding(), test_a_clean_run_still_posts(), test_a_confirmed_post_is_ledgered_so_the_run_can_be_verified(), test_a_failed_ledger_does_not_lose_the_report(), execute(), test_a_failed_query_rolls_back_and_does_not_sink_the_run(), test_a_fresh_sweep_and_savant_produce_no_finding() (+22 more)

### Community 678 - "NFL prop market card tests"
Cohesion: 0.22
Nodes (3): TestMarketCard, execute(), fetchall()

### Community 679 - "NBA research data cache"
Cohesion: 0.24
Nodes (11): TestLocalCacheGuards, _write_manifest(), write_table(), _by_game_ids(), cache_box(), cache_games(), cache_lines(), cache_props() (+3 more)

### Community 68 - "NBA second game prop projections"
Cohesion: 0.06
Nodes (40): Shape, appearances(), box_tables(), build(), check_close_prior(), consensus_number(), empty_times(), fit_shape() (+32 more)

### Community 688 - "Bounded odds pruning and thinning"
Cohesion: 0.10
Nodes (14): _Ctx, main(), run_prune_odds(), test_prune_rejects_keep_days_below_one(), p(), _fails_on(), test_a_failed_thinning_statement_fails_the_step(), test_a_thinning_failure_still_prunes_both_tables_and_is_reported() (+6 more)

### Community 69 - "tests/test_pick_integrity.py"
Cohesion: 0.03
Nodes (45): _Conn, _Shim, _add_pick(), discord_sent(), _health(), health_db(), test_a_label_may_not_name_a_market_the_pick_does_not_settle_on(), test_a_label_naming_the_other_team_is_refused() (+37 more)

### Community 692 - "NFL live leader model"
Cohesion: 0.18
Nodes (9): Artifact, Decision, am_to_dec(), artifact_from_dict(), band_for(), decide(), leader_expected_margin(), load_artifact() (+1 more)

### Community 693 - "Schedule refresh fake database helpers"
Cohesion: 0.13
Nodes (4): _Lite, test_without_the_venue_columns_the_schedule_still_lands(), resolver(), fake_get()

### Community 694 - "NHL as-of blended team inputs"
Cohesion: 0.14
Nodes (4): TestBlendedTeamInputs, _r(), _t(), test_the_training_path_reads_nhl_odds_by_game_not_by_sport()

### Community 696 - "NHL starter-out injury features"
Cohesion: 0.18
Nodes (3): TestHasStarterOut, _build_nhl_features_from_bulk(), _has_starter_out()

### Community 7 - "Pre-game pick scorer core"
Cohesion: 0.01
Nodes (175): _Clock, _StubConn, _Conn, TestAmericanToImpliedProb, TestBuildPickLabel, TestConfidenceTier, TestMissingStarterGate, TestQuarterKelly (+167 more)

### Community 70 - "tests/test_record_one_pick_per_event.py"
Cohesion: 0.05
Nodes (42): _CaptureConn, _RecordingConn, _code(), _copy_for_node(), _fn(), _node(), _read(), test_a_custom_model_counts_the_kept_copy_once() (+34 more)

### Community 705 - "WNBA returning player injury feature"
Cohesion: 0.18
Nodes (3): TestHasReturnee, _has_returnee(), _assemble_wnba_features()

### Community 708 - "Weekly job catch-up tests"
Cohesion: 0.18
Nodes (3): _Conn, test_a_failing_savant_refresh_does_not_cost_the_calibration_its_catch_up(), test_ownership_is_checked_per_job()

### Community 71 - "Model training and prop feature core"
Cohesion: 0.01
Nodes (266): OffsetLogit, TestTrainingExcludesThemAndScoringDoesNot, assert_retrain_allowed(), calibration_method(), scoring_method(), build_training_dataset(), coerce_numeric_features(), build_live_training_dataset() (+258 more)

### Community 711 - "Pipeline report rollback tests"
Cohesion: 0.14
Nodes (6): _Conn, _rows(), test_a_failed_query_rolls_back(), test_every_section_is_still_present(), test_one_broken_section_does_not_break_the_rest(), test_the_health_check_query_does_not_compare_text_to_a_date()

### Community 712 - "NFL pick monitor join key"
Cohesion: 0.16
Nodes (3): TestTheJoinKeyMatchesPicks, eval_row(), _picks_game_id()

### Community 713 - "Paused bet bankroll capture tests"
Cohesion: 0.18
Nodes (3): _Capture, test_a_paused_settled_bet_never_moves_the_kelly_bankroll(), test_todays_standing_bets_ignore_a_paused_row()

### Community 716 - "Health check skip budget (group 716)"
Cohesion: 0.16
Nodes (6): FakeConn, test_a_check_never_seen_non_skipped_counts_its_whole_history(), test_a_check_skipped_only_today_is_not_counted_as_a_streak(), test_streak_counts_calendar_days_from_the_last_non_skipped_run(), test_the_streak_query_fails_open(), _skip_run_days()

### Community 718 - "Pregame price age bound tests"
Cohesion: 0.16
Nodes (7): _OddsConn, test_a_month_old_price_on_an_unstarted_game_is_no_price(), test_a_price_stored_this_pass_still_decides(), test_a_started_game_reads_its_last_pre_game_row_whatever_its_age(), test_just_inside_and_just_outside_the_bound(), test_the_feature_row_and_the_opener_read_the_same_bounded_price(), _totals_row()

### Community 73 - "nfl/live_model/tests: test_props + props"
Cohesion: 0.08
Nodes (35): PropProjection, GameState, PlayerState, _accrued(), _count(), detect_inactive(), price_over(), project() (+27 more)

### Community 731 - "NFL prop injury veto (group 731)"
Cohesion: 0.15
Nodes (4): _InjConn, _as_dt(), load_nfl_injury_index(), test_loader_keys_by_norm_name_and_skips_empty()

### Community 732 - "NBA prop no-bet rows harness tests"
Cohesion: 0.10
Nodes (7): _Board, _emit_world(), _spy_run_cells(), test_closing_value_is_priced_with_the_markets_empirical_distribution(), test_every_family_emits_exactly_its_cells_through_the_harness(), test_the_d_cells_are_gated_on_the_points_own_decision_times(), test_the_bootstrap_is_seeded_and_refines_small_p()

### Community 755 - "NFL prop market lead ceiling"
Cohesion: 0.05
Nodes (29): TestKickoffGate, TestMarketGrading, american_to_profit(), _as_dt(), drop_pulled_quotes(), grade(), season_of(), summarise() (+21 more)

### Community 758 - "Deploy checks and job queue"
Cohesion: 0.06
Nodes (19): _Conn, _job_queue(), test_a_declared_job_carries_its_run_after(), test_a_failing_check_raises_so_the_queue_announces_it(), test_a_job_can_only_name_a_registered_check(), test_enqueue_rejects_a_naive_run_after(), test_enqueue_stores_run_after(), test_every_check_is_read_only() (+11 more)

### Community 77 - "tests/test_wnba_prop_market.py"
Cohesion: 0.05
Nodes (30): _FakeConn, _QuoteConn, apply_price_floor(), norm_name(), pick_rows(), player_ids(), publish(), render() (+22 more)

### Community 78 - "tests/test_nfl_scored_rows.py"
Cohesion: 0.13
Nodes (12): _Conn, _RaceConn, TestLockSurvivesNothing, TestNoneRowBesideABetIsCleared, TestPublishRace, TestPublishScored, _bet_row(), fetchall() (+4 more)

### Community 79 - "NHL derivative totals pricing"
Cohesion: 0.13
Nodes (16): Market, build_p1_frame(), build_team_frame(), _ew(), fit(), game_means(), _implied_vec(), _payout() (+8 more)

### Community 8 - "Eggz capper picks Discord recaps"
Cohesion: 0.01
Nodes (126): _SlateConn, _Posted, _Rejected, name_resemblance(), _army_tulsa(), _grade_conn(), _recap_db(), _reg_conn() (+118 more)

### Community 84 - "NBA prop cards across models"
Cohesion: 0.07
Nodes (35): NbaPropDecision, _Conn, wp(), _patch_looks(), _proj_bet(), _proj_dec(), _proj_rows(), _rule_bet() (+27 more)

### Community 848 - "Prop odds book update time"
Cohesion: 0.26
Nodes (6): _Conn, _parse(), test_a_row_built_without_the_key_still_inserts_as_null(), test_no_clock_anywhere_is_none_not_our_fetch_time(), test_the_column_is_added_only_when_the_catalog_lacks_it(), test_the_markets_own_clock_is_stored_else_the_books()

### Community 85 - "tests/test_recap_retries_a_skipped_day.py"
Cohesion: 0.07
Nodes (23): _LiteConn, World, _add_pick(), _grade(), _lite(), _schema(), test_a_day_with_nothing_counting_posts_nothing_and_logs_nothing(), test_a_failed_receipt_never_reposts_the_day() (+15 more)

### Community 852 - "Monitoring dashboard web server"
Cohesion: 0.29
Nodes (4): Handler, _connect(), dumps(), _json_default()

### Community 854 - "NFL prop pulls and recap error tests"
Cohesion: 0.05
Nodes (17): TestIngestEventsDoesNotShadowItsMarkets, _write(), test_the_halftime_distribution_refuses_a_choosing_season_without_enough_earlier_games(), rows(), fetchall(), test_live_prop_pull_asks_for_the_sharp_book(), fake_event_props(), fetchall() (+9 more)

### Community 870 - "NFL player stats and props data ingest"
Cohesion: 0.03
Nodes (55): TestParseNflverseScores, _fetch_pitcher_gb_pct(), backfill_nfl_player_stats(), current_nfl_season(), _fetch_game_dates(), _fetch_season_csv(), ingest_nfl_player_stats(), parse_player_week_csv() (+47 more)

### Community 88 - "NBA prop market decision tests"
Cohesion: 0.04
Nodes (55): NbaPropBet, _PublishConn, _SettleConn, _SlateConn, pick_label(), pick_rows(), _bet(), _decision() (+47 more)

### Community 887 - "NBA injury report ingest tests"
Cohesion: 0.17
Nodes (11): _DatesConn, _Fetcher, _rows(), test_a_recent_403_is_not_written_so_a_later_run_can_still_fetch_it(), test_all_players_available_is_a_team_row_not_the_tail_of_a_reason(), test_current_layout_2026(), test_name_key_drops_accents_punctuation_and_suffixes(), test_nine_column_layout_2019() (+3 more)

### Community 892 - "Player news feed fetching"
Cohesion: 0.19
Nodes (9): FakeResponse, test_a_sport_with_no_team_id_map_still_gets_its_league_feed(), fake_fetch(), test_an_http_error_is_a_quiet_zero(), fake_fetch(), test_the_league_feed_runs_once_and_team_feeds_are_capped(), fake_fetch(), test_the_same_story_in_two_feeds_is_stored_once() (+1 more)

### Community 893 - "Weather step date window tests"
Cohesion: 0.13
Nodes (3): TestTheWeatherStepWalksTheWindow, _nhl_blended_features(), d()

### Community 894 - "Team total market pick tests"
Cohesion: 0.15
Nodes (5): _PickConn, _Rows, test_a_line_that_dropped_under_an_under_is_a_skip(), test_the_first_five_totals_are_not_newly_line_checked(), test_the_home_team_s_points_against_the_line()

### Community 898 - "NBA game offset ridge fitting"
Cohesion: 0.16
Nodes (5): OffsetRidge, choose_C_linear(), fit_one(), model_move(), _mse()

### Community 899 - "Schema SQL statement splitter"
Cohesion: 0.26
Nodes (3): TestRealSchema, TestSplitter, _split_sql_statements()

### Community 9 - "NHL goalie confirmation window planner"
Cohesion: 0.53
Nodes (4): Plan, has_games_today(), plan_tick(), today_slate()

### Community 90 - "NBA totals luck decision tests"
Cohesion: 0.03
Nodes (75): Decision, TotalLuckBet, _Conn, _Cur, decide(), lead_minutes(), newest_season(), pricing_dist() (+67 more)

### Community 903 - "Probability calibration and cut sweeps"
Cohesion: 0.02
Nodes (128): _FakeConn, build_live_state_row(), expected_value(), _score_live_model(), demote(), ensure_schema(), _era_start(), fit_model() (+120 more)

### Community 915 - "UFC fight resolution tests"
Cohesion: 0.09
Nodes (13): _FakeConn, _resolve(), test_confirmed_aliases_resolve_to_ufcstats_slug(), test_resolve_anchor_declines_when_opponent_changed(), test_resolve_anchor_matches_every_real_name_variant(), test_resolve_anchor_refuses_a_late_replacement(), test_resolve_anchor_refuses_every_real_stale_booking_on_its_own(), test_resolve_anchor_rescues_unmapped_variant() (+5 more)

### Community 92 - "tests/test_ncaaf_prop_odds.py"
Cohesion: 0.07
Nodes (19): _Conn, _Resp, _market_chunks(), scope(), test_a_book_we_did_not_ask_for_is_never_written(), test_a_day_with_no_college_games_spends_nothing(), test_a_rejected_chunk_costs_only_its_own_markets(), fake_get() (+11 more)

### Community 926 - "MLB opposing starter feature tests"
Cohesion: 0.09
Nodes (15): _StubConn, _StubResult, _opp_starter_savant(), _starter_gb_pct(), _batter_bulk(), test_batter_bulk_carries_everything_opp_starter_savant_reads(), test_it_reads_the_starters_savant_row(), test_live_mode_falls_back_to_prior_season() (+7 more)

### Community 931 - "NHL unknown goalie refusal rules"
Cohesion: 0.23
Nodes (8): _GateConn, matchup_reasons(), refuse_unknown(), _row(), test_a_shots_on_goal_bet_passes_an_unknown_game_without_a_read(), test_every_nhl_model_but_shots_on_goal_is_refused_on_an_unknown_game(), test_refuse_unknown_drops_or_downgrades_and_leaves_other_sports_unread(), test_the_gate_reads_and_fails_closed()

### Community 938 - "College football alias score mirroring"
Cohesion: 0.18
Nodes (5): _FakeConn, _FakeCursor, test_stored_finals_are_mirrored_without_a_cfbd_pull(), execute(), test_writer_never_touches_the_db_when_there_is_nothing_to_mirror()

### Community 943 - "DraftKings direct feed matching"
Cohesion: 0.24
Nodes (6): _Conn, _game_id_for(), test_a_unique_match_resolves(), test_an_ambiguous_event_name_writes_nothing(), test_an_event_name_with_no_at_sign_is_refused(), test_an_unmatched_event_name_writes_nothing()

### Community 949 - "Multi-book odds fallback"
Cohesion: 0.22
Nodes (6): _Resp, test_a_rejected_book_list_falls_back_to_the_decision_book(), _get(), test_the_fallback_does_not_recurse_forever(), _get(), _get()

### Community 95 - "tests/test_ncaaf_pbp_store.py"
Cohesion: 0.09
Nodes (18): _Conn, load_season_from_db(), _report_ranges(), store_season(), _plays(), test_a_rerun_updates_rather_than_duplicating(), test_a_season_in_neither_place_is_an_error_not_a_short_corpus(), test_a_season_survives_the_round_trip_in_the_cfbd_spelling() (+10 more)

### Community 953 - "Sportsbook team to game resolver"
Cohesion: 0.24
Nodes (5): _Conn, resolve_game_id(), test_a_non_mlb_sport_is_refused_rather_than_guessed(), test_a_unique_game_resolves(), test_an_ambiguous_game_resolves_to_none()

### Community 958 - "NFL prop game matching"
Cohesion: 0.29
Nodes (3): TestResolveGameId, resolve_nfl_game_id(), resolve()

### Community 96 - "tests/test_heartbeat_watchdog.py"
Cohesion: 0.05
Nodes (34): _FakeConn, _FakeCursor, _break_db(), sink(), test_a_failed_post_does_not_start_the_throttle(), test_a_healthy_start_never_announces_a_recovery(), test_a_returning_outage_alerts_again_immediately(), test_a_silent_failure_alerter_is_caught_by_the_watchdog() (+26 more)

### Community 960 - "Sport injury index loader"
Cohesion: 0.22
Nodes (5): _InjConn, load_sport_injury_index(), test_loader_fail_open_on_missing_column(), test_loader_keys_by_norm_name(), test_relevant_players_fail_open_without_conn()

### Community 963 - "NCAAF gameday CFBD mode"
Cohesion: 0.24
Nodes (6): _Ctx, _ev(), test_a_single_failed_summary_does_not_drop_the_other_games(), test_cfbd_mode_does_no_per_game_fetching(), test_espn_states_are_fetched_in_parallel_and_stay_aligned(), test_unknown_matchups_never_cost_a_fetch()

### Community 965 - "NFL DraftKings line snapshots"
Cohesion: 0.42
Nodes (3): TestDkLineRows, dk_line_rows(), _rec()

### Community 97 - "NCAAF in-play quote selection engine"
Cohesion: 0.07
Nodes (13): LiveEngine, american_to_prob(), devig_power(), expected_value(), _is_paused(), test_ev_floor_cannot_fire_without_a_price(), test_ev_floor_declines_a_qualifying_pick_that_is_priced_too_short(), test_ev_floor_only_tightens_and_never_touches_avoid() (+5 more)

### Community 976 - "Model quality run persistence tests"
Cohesion: 0.22
Nodes (3): _Shim, _insert_open_bet(), test_run_persists_all_unders_fade_slate_as_crit()

### Community 982 - "Settlement self-heal tests"
Cohesion: 0.22
Nodes (3): _SqliteShim, conn(), raw()

### Community 985 - "Pregame line change poller"
Cohesion: 0.04
Nodes (42): _PollConn, changed_rows(), _fingerprint(), _key(), _num(), over_credit_cap(), poll_once(), quoted_keys() (+34 more)

### Community 987 - "Picks email rendering"
Cohesion: 0.46
Nodes (6): Pick, _fmt_edge(), _fmt_odds(), main(), _pick_card(), render_email()

### Community 99 - "Record correction social posts"
Cohesion: 0.06
Nodes (28): Ledger, _Result, _pin(), _real_post(), _real_tweet(), x_posts(), _publish(), test_a_failed_discord_ledger_does_not_send_x() (+20 more)

### Community 993 - "Calibration watch announcements"
Cohesion: 0.25
Nodes (3): TestItNeverDecides, _announce(), _announce_and_ledger()

### Community 10 - "NBA prop rest days inputs tests"
Cohesion: 0.25
Nodes (11): box_from_log(), _bos(), _data(), _games(), _schedule(), test_a_cup_week_box_enters_the_players_history(), test_a_cup_week_game_the_schedule_does_not_list_still_counts_for_rest(), test_nothing_changes_when_the_schedule_lists_every_game() (+3 more)

### Community 100 - "NBA box score ingestion"
Cohesion: 0.05
Nodes (51): _blank(), _check_unmapped(), _create(), ensure_tables(), fetch_advanced(), fill_missing_game_logs(), _flt(), _game() (+43 more)

### Community 1005 - "Pipeline credit burn watch"
Cohesion: 0.25
Nodes (4): test_burn_is_judged_against_the_cap_not_against_yesterday(), test_burn_survives_a_non_numeric_credits_column(), test_failed_api_calls_are_reported_even_when_burn_is_low(), findings_from_burn()

### Community 101 - "NBA schedule refresh from feed"
Cohesion: 0.10
Nodes (13): _counts(), feed_shows(), _fits(), _known_team(), _month_bounds(), months(), read_games(), read_stored() (+5 more)

### Community 1012 - "NFL opener calibration"
Cohesion: 0.38
Nodes (3): _load_backtest(), main(), selected_bets()

### Community 1013 - "NBA game probability harness"
Cohesion: 0.29
Nodes (5): test_a_period_moneyline_removes_the_tie_mass(), test_a_past_average_miss_does_not_move_the_centre(), test_a_skewed_distribution_is_not_read_as_normal(), test_the_empirical_model_matches_the_normal_one_on_normal_residuals(), test_whole_lines_carry_push_mass_and_half_lines_none()

### Community 1014 - "Bet price and book taken"
Cohesion: 0.29
Nodes (4): test_the_bet_is_the_price_taken_at_the_book_it_was_taken(), test_the_line_check_passes_for_both_label_shapes(), _bet_price_and_book(), _book_from_label()

### Community 1015 - "Health check cadence from dates"
Cohesion: 0.29
Nodes (5): test_cadence_reads_a_daily_bar_off_the_dates(), test_cadence_reads_a_multi_day_window(), test_cadence_reads_a_same_day_bar(), test_cadence_survives_a_missing_or_unparseable_date(), _cadence_from_dates()

### Community 1016 - "Model quality volume spikes"
Cohesion: 0.29
Nodes (5): test_volume_spike_vs_median(), test_volume_without_history_is_skipped_not_flagged(), detect_volume_spike(), _median(), units_from_recommended_bet()

### Community 1017 - "NFL prop parameter artifact check"
Cohesion: 0.33
Nodes (3): _models(), _newest_artifact(), test_params_file_carries_the_newest_artifacts_hyperparameters()

### Community 102 - "NBA news and in-play research scripts"
Cohesion: 0.02
Nodes (129): snapshot_plan(), game_windows(), load_games(), main(), pivot_spreads(), pivot_totals(), devig_power(), games() (+121 more)

### Community 1023 - "NFL wide odds table builder"
Cohesion: 0.47
Nodes (4): load_games(), main(), wide_spreads(), wide_totals()

### Community 1025 - "NFL standings and division flags"
Cohesion: 0.33
Nodes (4): conference(), divisions(), f(), standings_flags()

### Community 1026 - "NFL prop alternate line grading"
Cohesion: 0.33
Nodes (4): base_market(), candidates(), _nn(), profit()

### Community 1028 - "NBA team total ladder quotes"
Cohesion: 0.33
Nodes (4): _ladder_quotes(), _offered(), _rung(), test_both_families_see_each_books_main_number_only()

### Community 103 - "NBA prop projection tests"
Cohesion: 0.06
Nodes (27): _art(), _proj(), _q(), _run(), _settle(), test_a_book_hanging_two_lines_for_one_player_is_refused(), test_a_decision_with_no_bet_is_still_a_decision(), test_a_past_game_never_projected_gets_the_newest_espn_pull_55_minutes_before_its_tip() (+19 more)

### Community 1030 - "Scorer housekeeping delete guards"
Cohesion: 0.33
Nodes (3): _run_scorer_body(), test_every_housekeeping_delete_in_run_scorer_is_scoped_to_the_subset(), test_the_subset_predicate_never_builds_an_empty_IN_list()

### Community 1033 - "CFBD local aggregates"
Cohesion: 0.40
Nodes (3): _local_aggregates(), test_local_aggregates_computes_season_to_date_form(), test_local_aggregates_does_no_date_filtering_of_its_own()

### Community 1034 - "NBA results ingestion check"
Cohesion: 0.50
Nodes (3): _is_team(), needs_work(), _parse_ts()

### Community 1038 - "Health check lateness reporting"
Cohesion: 0.40
Nodes (3): test_a_late_check_says_how_late(), test_days_late_falls_back_rather_than_lying(), _days_late()

### Community 1046 - "NHL goalie save regression"
Cohesion: 0.83
Nodes (4): _goalie_line(), regressed(), saved_above(), tot()

### Community 1051 - "NBA bought odds season coverage"
Cohesion: 0.67
Nodes (4): _games3(), _odds_row(), test_2024_25_and_2025_26_are_required_even_when_the_cache_lacks_one(), test_a_partly_bought_season_makes_the_graded_load_refuse()

### Community 107 - "tests/test_prop_calibrated_decision.py"
Cohesion: 0.07
Nodes (27): apply_prop_daily_cap(), dedupe_player_props(), _bet(), _identity_cal(), _prop(), test_a_genuinely_big_edge_still_fires_after_calibration(), test_a_hot_prop_model_no_longer_fires_the_marginal_bet(), test_a_model_outside_every_pool_is_untouched() (+19 more)

### Community 109 - "NBA fourth search derivative markets"
Cohesion: 0.07
Nodes (31): calibrated_refs(), cell_specs(), choosing(), decision_quotes(), derivative_data(), emit_f1(), emit_f4(), f1_fair() (+23 more)

### Community 110 - "tests/test_mobile_line_movement.py"
Cohesion: 0.08
Nodes (27): _fn(), _read(), _run(), test_a_cut_table_keeps_the_pick_and_says_what_it_covers(), test_a_cut_window_keeps_the_pick_row_on_the_8_row_table(), test_a_pick_made_after_the_cards_start_never_reads_since_your_pick(), test_after_the_start_the_verdict_is_not_graded(), test_an_old_snapshot_is_not_the_price_at_the_pick() (+19 more)

### Community 111 - "In-play calibration analysis"
Cohesion: 0.06
Nodes (33): decide(), pick(), test_a_peak_with_no_plateau_anywhere_is_labelled_as_one(), test_a_prob_cut_and_an_ev_cut_select_different_picks(), test_calibration_also_scores_ev_against_realised_roi(), test_calibration_is_empty_rather_than_wrong_with_nothing_settled(), test_calibration_reports_the_gap_between_claim_and_reality(), test_expected_value_matches_the_hand_calculation() (+25 more)

### Community 112 - "NBA in-game luck study one"
Cohesion: 0.08
Nodes (28): attach_rates(), build(), close_totals(), decisions(), eligible(), fair_mu(), fit_w(), gate_passes() (+20 more)

### Community 117 - "NBA lineup stint derivation tests"
Cohesion: 0.08
Nodes (45): order_plays(), _blowout_q4(), derive(), dreb(), _dup_game(), end_period(), five_game(), make2() (+37 more)

### Community 118 - "NBA play-by-play lineup builder"
Cohesion: 0.07
Nodes (25): active_queries(), build_map(), _dicts(), download(), ensure_tables(), idx(), make(), fill_gaps() (+17 more)

### Community 119 - "tests/test_ncaaf_live_notify.py"
Cohesion: 0.05
Nodes (18): _load_write_picks(), _restore_stubbed_modules(), test_a_caller_supplied_connection_is_not_closed_by_the_write(), test_a_failing_notifier_never_breaks_pricing(), test_a_full_slate_announces_once(), test_a_live_bet_notifies_push_and_discord(), test_a_locked_lane_is_not_rewritten(), test_a_locked_lane_keeps_notifying_after_the_engine_stops_betting() (+10 more)

### Community 12 - "NFL in-play edge season research"
Cohesion: 0.15
Nodes (26): books_per_snapshot(), families(), finalize_states(), fit_models(), fmt(), h2_accuracy(), h3_accuracy(), hold_table() (+18 more)

### Community 120 - "tests/test_ncaaf_alias_scores.py"
Cohesion: 0.13
Nodes (24): alias_score_updates(), _cfbd(), _row(), test_a_bare_substring_is_not_an_extension(), test_a_daytime_game_has_no_duplicate_and_is_untouched(), test_a_loose_match_swaps_scores_when_the_row_is_reversed(), test_a_merely_different_opponent_is_not_the_same_game(), test_a_row_that_already_has_a_final_is_never_overwritten() (+16 more)

### Community 122 - "NCAAF quarterback team features"
Cohesion: 0.13
Nodes (23): build_qb_team_features(), merge_qb_features(), _feat(), _frame(), _games(), _qb_rows(), _qb_team(), test_a_games_features_never_use_that_game() (+15 more)

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
Cohesion: 0.11
Nodes (18): assemble_player_features(), _avg_finish(), _event_finishes(), _made_cut_rate(), _mean(), _parse_date(), _rolling_sg(), _history() (+10 more)

### Community 132 - "NCAAF in-play state building tests"
Cohesion: 0.13
Nodes (22): build_states(), _platform(), _plays(), _post_convention_game(), _pre_convention_game(), test_a_scoring_plays_state_does_not_contain_its_own_points(), test_ambiguous_convention_refuses_to_build(), test_halftime_scores_carried_for_2h_settlement() (+14 more)

### Community 133 - "tests/test_bovada_feed.py"
Cohesion: 0.10
Nodes (31): _american(), _complete(), _num(), parse_coupon(), _row_for(), _seen_key(), _stamp(), _coupon() (+23 more)

### Community 134 - "NBA prop model research lab"
Cohesion: 0.07
Nodes (49): books(), decimal(), expected_value(), fit_alpha(), implied(), nb_logpmf(), p_over(), _agg() (+41 more)

### Community 136 - "NCAAF cross-book opener tests"
Cohesion: 0.07
Nodes (25): _minutes_apart(), build_artifact(), build_band_artifact(), _branch(), test_absent_ceiling_means_unbounded(), test_artifact_shape(), test_band_ceiling_is_enforced_in_the_scorer(), test_band_volumes_sum_to_the_single_gate_backtest() (+17 more)

### Community 138 - "tests/test_paused_keeps_real_verdict.py"
Cohesion: 0.07
Nodes (33): _bet(), _bodies(), _code(), _fn(), _pause(), _prop(), _rules(), _sql_of() (+25 more)

### Community 139 - "In-play edge research grading"
Cohesion: 0.12
Nodes (28): s(), cell(), h1(), h2(), h3(), h4(), h5(), h6() (+20 more)

### Community 145 - "NBA prop projection research lab"
Cohesion: 0.09
Nodes (47): apply_calibration(), _logit(), bars(), bh_read(), blind(), boot(), by(), cal_ab() (+39 more)

### Community 147 - "scripts/nfl_edge_extreme_props.py"
Cohesion: 0.16
Nodes (25): actuals(), add_modes(), bar(), candidates(), cell(), decision_boards(), devig(), fit_holdout() (+17 more)

### Community 148 - "scripts/nfl_edge_settlement.py"
Cohesion: 0.14
Nodes (30): add_test(), attach(), banner(), bh(), board(), boot_draws(), cell(), choose() (+22 more)

### Community 152 - "NBA prop projection card builder"
Cohesion: 0.09
Nodes (20): espn_compact(), espn_pulls(), espn_rows(), fill_espn_history(), _frame(), _game_teams(), history_decisions(), load_history() (+12 more)

### Community 153 - "tests/test_agents_contract.py"
Cohesion: 0.05
Nodes (20): _labelled_retired(), test_blocked_items_are_marked_so_the_agent_skips_them(), test_every_backlog_item_is_a_checkbox(), test_neither_agent_may_change_a_model_threshold(), test_the_agents_are_findable_from_the_file_every_session_reads(), test_the_backlog_does_not_promise_an_agent_that_no_longer_runs(), test_the_backlog_exists_and_has_items(), test_the_contract_documents_every_agent_by_name() (+12 more)

### Community 157 - "Kalshi NFL price history fetch"
Cohesion: 0.21
Nodes (6): candles(), get(), map_games(), paged(), parse_event(), probe()

### Community 159 - "WNBA results ingestor"
Cohesion: 0.06
Nodes (35): box_team_totals(), _no_minutes(), stat(), build_log_row(), _core_athlete(), _deref(), _et_date(), _fetch_core_box_players() (+27 more)

### Community 161 - "NBA box score enrichment"
Cohesion: 0.13
Nodes (22): box_rows(), dnp_kind(), minutes_to_float(), minutes_to_seconds(), starter_update_batches(), _box(), test_a_blank_minutes_string_is_null_not_zero(), test_a_dnp_row_has_null_minutes_and_its_reason_and_is_not_a_starter() (+14 more)

### Community 163 - "NBA derivative market lab"
Cohesion: 0.08
Nodes (36): add_team(), am_to_dec(), bars_for(), bet_list(), blind(), boot_ci(), build_line_rows(), build_outcomes() (+28 more)

### Community 167 - "scripts/nfl_preflight.py"
Cohesion: 0.19
Nodes (17): _load_postgres_schema(), check(), check_cards_run(), check_config_gates(), check_cost(), check_data(), data_check(), check_import_shadowing() (+9 more)

### Community 168 - "Mobile screen source pattern tests"
Cohesion: 0.02
Nodes (108): test_every_revoke_names_the_roles_rather_than_public(), test_odds_keeps_select_for_the_app(), test_the_two_rls_off_tables_lose_everything(), _app_rpcs(), test_every_rpc_the_app_calls_is_declared_or_known_absent(), test_the_dynamic_rpc_resolver_actually_finds_the_ternary_names(), test_the_function_revoke_names_public_as_well_as_the_roles(), test_app_errors_is_write_only_for_the_anon_key() (+100 more)

### Community 169 - "NBA halftime in-game research"
Cohesion: 0.08
Nodes (24): add_features(), attach_close(), build_halves(), centre(), day_ci(), decision_games(), decision_quotes(), first_part() (+16 more)

### Community 171 - "NBA second game market search"
Cohesion: 0.06
Nodes (34): cache_for(), check_cells(), combine_times(), f2_cells(), f2_point(), f6a_placebo(), f6a_point(), f6a_strength() (+26 more)

### Community 173 - "tests/test_decide_on_calibrated.py"
Cohesion: 0.06
Nodes (19): _pick(), _pick_at(), test_a_calibrated_cut_is_paired_with_a_calibrated_decision(), test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(), test_a_genuinely_big_edge_still_fires_after_calibration(), test_a_hot_model_no_longer_fires_the_marginal_bet(), test_a_model_on_a_calibrated_cut_is_not_paused(), test_a_paused_model_never_fires_regardless() (+11 more)

### Community 175 - "tests/test_dk_direct_feed.py"
Cohesion: 0.19
Nodes (13): _row_for(), _seen_key(), _rec(), test_a_line_move_is_a_new_quote(), test_a_market_we_do_not_understand_is_dropped_not_guessed(), test_a_price_move_is_a_new_quote(), test_a_priced_market_with_no_line_is_dropped(), test_every_row_is_tagged_dk_direct() (+5 more)

### Community 176 - "Model artifact load and tracking tests"
Cohesion: 0.07
Nodes (19): _git(), _gitignore_keep_pkls(), _ignored(), _manifest_keep_pkls(), _newest_per_model(), test_a_path_that_is_not_ignored_is_not_reported(), test_a_superseded_timestamped_pkl_is_ignored(), test_an_ignored_path_comes_back_byte_identical() (+11 more)

### Community 181 - "NBA in-game data staleness gate"
Cohesion: 0.06
Nodes (35): attach_pinnacle(), box_checks(), build(), drop_wild_wallclocks(), espn_map(), foul_flags(), is_heave(), keep_in_play() (+27 more)

### Community 183 - "NBA prop model verification script"
Cohesion: 0.13
Nodes (28): adv_from_log(), asof_roster(), blind_structured(), card_block(), collapse_report(), _compare(), log(), main() (+20 more)

### Community 185 - "scripts/game_line_market_sweep.py"
Cohesion: 0.08
Nodes (17): _by_month(), collect_picks(), devig(), grade(), implied(), iter_months(), load(), load_chunked() (+9 more)

### Community 187 - "NFL luck gap edge study"
Cohesion: 0.10
Nodes (30): add_windows(), add_windows_fast(), bh(), binom_p(), board(), boot(), cell(), fit_points() (+22 more)

### Community 188 - "Pipeline step timing instrumentation"
Cohesion: 0.13
Nodes (4): test_a_raised_failure_still_records_the_exception(), test_a_step_that_raises_is_still_TIMED(), test_a_step_that_raises_still_raises(), boom()

### Community 19 - "Mobile live board segment tests"
Cohesion: 0.06
Nodes (28): _read(), test_a_sport_switch_cannot_report_a_game_finishing(), test_all_three_segments_are_unconditional(), test_live_is_not_a_bottom_tab(), test_live_is_not_in_the_tab_param_list(), test_no_app_root_component_reaches_a_focus_aware_hook(), imports_of(), strip_comments() (+20 more)

### Community 190 - "tests/test_db_adapt_sql.py"
Cohesion: 0.09
Nodes (23): _adapt_sql(), _convert_params(), _convert_params_outside_literals(), _named(), test_a_block_comment_is_skipped_too(), test_a_colon_word_inside_a_comment_is_not_a_placeholder(), test_a_dash_dash_inside_a_literal_is_data_not_a_comment(), test_a_line_comment_ends_at_the_newline() (+15 more)

### Community 194 - "NFL prop injury veto (group 194)"
Cohesion: 0.18
Nodes (16): apply_injury_veto(), player_is_vetoed(), should_veto(), test_equal_timestamps_veto(), _bet(), _idx(), _quotes(), test_active_and_unknown_players_pass_through() (+8 more)

### Community 195 - "tests/test_mobile_contrast_tokens.py"
Cohesion: 0.13
Nodes (29): _code_lines(), _ionicon_colors(), _lum(), _over(), _ratio(), _read(), _rgb(), test_badge_glyph_tracks_dynamic_type() (+21 more)

### Community 196 - "NBA alternate line pricing study"
Cohesion: 0.08
Nodes (31): derivative_pricing(), _american(), band_cols(), blinds(), book_mains(), cache_alt(), clv_shaped(), eligible_offers() (+23 more)

### Community 198 - "NBA game four part one tests"
Cohesion: 0.06
Nodes (32): _base(), _fair(), _ladder_quotes(), _offered(), _offers(), _period_games(), _rows(), _rung() (+24 more)

### Community 199 - "Pregame cutoff on prop prices"
Cohesion: 0.20
Nodes (5): _assigned_from(), _prop_scorers(), test_every_scorer_call_site_passes_a_pregame_cutoff(), test_the_stamped_commence_time_is_still_the_schedule(), test_the_started_game_guard_uses_the_cutoff_too()

### Community 201 - "NBA second game line move tests"
Cohesion: 0.06
Nodes (39): _priced_season(), _q(), _sched(), _season_games(), _signal(), _split(), _stub_main(), test_a_fetch_after_T_never_reaches_the_move() (+31 more)

### Community 207 - "NFL in-play prop flow anchoring tests"
Cohesion: 0.07
Nodes (22): grade(), grade_real(), naive_line(), _anchor_frame(), _long(), test_a_degenerate_line_is_dropped(), test_a_push_on_a_whole_number_line_is_not_a_loss(), test_accrual_is_as_of_the_mark_not_the_last_involvement() (+14 more)

### Community 208 - "NFL prop scoring rows and candidate pool"
Cohesion: 0.08
Nodes (20): _add_features(), build_nfl_prop_scoring_rows(), derived_targets(), _load(), _nfl_season(), _pool_mask(), _read(), _roll() (+12 more)

### Community 212 - "NBA second game verdict"
Cohesion: 0.13
Nodes (15): axes_of(), band_slots(), bands_ok(), bar9(), cell_key(), _floats(), house_bar4(), house_verdict() (+7 more)

### Community 217 - "NCAAF in-play pricing engine"
Cohesion: 0.06
Nodes (22): correct_for_pregame(), _load_pregame_calibration(), pregame_dog_points(), _real_artifact(), test_a_big_dog_is_marked_down_hard(), test_a_corrupt_artifact_leaves_the_probability_alone(), test_a_favourite_is_marked_up(), test_a_missing_artifact_leaves_the_probability_alone() (+14 more)

### Community 219 - "tests/test_nfl_live_leader_state.py"
Cohesion: 0.12
Nodes (20): abbrev(), situation(), status(), test_a_conversion_try_is_skipped(), test_a_previous_quarters_play_is_not_the_state(), test_a_timeout_is_skipped_for_the_play_before_it(), test_after_a_scoring_play_nothing_is_evaluated(), test_after_the_kickoff_lands_the_receiver_has_the_ball() (+12 more)

### Community 221 - "tests/test_ncaaf_qb_ingestor.py"
Cohesion: 0.12
Nodes (23): _athlete_stats(), _comp_att(), parse_qb_game_stats(), _split_ratio(), _parse(), _payload(), _team(), test_athlete_stats_helper_is_category_scoped() (+15 more)

### Community 233 - "tests/test_book_team_map.py"
Cohesion: 0.15
Nodes (10): abbr_from_team_string(), split_matchup(), test_a_string_with_no_at_sign_is_refused(), test_an_unrecognised_club_is_refused_not_guessed(), test_draftkings_and_bovada_formats_resolve_the_same(), test_the_athletics_use_the_abbreviation_the_database_uses(), test_the_matchup_split_is_away_at_home(), test_the_two_chicago_clubs_do_not_collapse() (+2 more)

### Community 235 - "NCAAF feature assembly tests"
Cohesion: 0.08
Nodes (22): _assemble_ncaaf_features(), _game_tier(), shrink_hfa(), _assemble(), _stats(), test_assembly_carries_venue_context_and_hfa(), test_assembly_diffs_and_context(), test_backtester_and_scorer_dispatch_ncaaf_explicitly() (+14 more)

### Community 236 - "Build your own model prop facts tests"
Cohesion: 0.15
Nodes (25): backtest(), facts_for_game(), _game(), _log(), _one(), _q(), test_220_50_and_220_5_are_one_prop_key(), test_a_later_number_replaces_the_earlier_line() (+17 more)

### Community 237 - "Postgres test harness and schedule refresh"
Cohesion: 0.21
Nodes (10): _no_network(), _confirmed(), conn(), _game(), _row(), _sched(), test_a_month_read_from_the_fallback_host_keeps_a_stored_status_and_tv(), test_a_run_confirms_listed_rows_adds_the_missing_game_and_drops_a_replaced_espn_row() (+2 more)

### Community 239 - "NFL wind board fast publishing tests"
Cohesion: 0.19
Nodes (13): _append_board(), _body(), _row(), _sent(), _setup(), test_a_half_written_last_row_waits_for_the_next_tick(), test_a_killed_step_fails_the_run_loudly_after_publishing(), test_board_flush_looks_each_matchup_up_once() (+5 more)

### Community 240 - "tests/test_ncaaf_game_identity.py"
Cohesion: 0.12
Nodes (16): _add(), _conn(), _identity_sql(), _run(), test_a_clean_slate_reports_nothing(), test_a_non_fbs_fixture_is_not_reported(), test_a_phantom_opponent_is_detected_too(), test_a_real_doubleheader_is_not_a_duplicate() (+8 more)

### Community 241 - "NBA second game market tests"
Cohesion: 0.10
Nodes (27): _close_frames(), _data(), _f2_games(), _f6a_data(), _f6d_total_data(), _game(), _pe(), _q() (+19 more)

### Community 243 - "Monitoring dashboard cache"
Cohesion: 0.17
Nodes (9): age(), cached(), clear(), test_cache_raises_when_it_has_nothing_to_fall_back_on(), test_cache_reports_age(), test_cache_serves_stale_rather_than_failing(), boom(), test_cache_serves_within_ttl_and_recomputes_after() (+1 more)

### Community 248 - "MLB live inning gate replay"
Cohesion: 0.13
Nodes (27): _pair(), _refuse_tables(), _score_seen_at(), _game(), _price(), _scored(), _sig(), _state() (+19 more)

### Community 25 - "NBA game model research harness"
Cohesion: 0.04
Nodes (55): attach_fetch(), blind_by_real_side(), blind_pool(), blind_side(), boot(), cell_report(), cents(), check() (+47 more)

### Community 254 - "Kalshi prop ladder recording"
Cohesion: 0.05
Nodes (17): _event_date(), _player(), record_ladders(), run_kalshi_ladder_record(), test_a_kalshi_outage_cannot_break_the_pass(), test_a_run_is_idempotent_within_its_snapshot(), test_one_snapshot_timestamp_for_the_whole_run(), test_the_recorder_is_scheduled_on_the_pipeline_role() (+9 more)

### Community 255 - "UFC results ingestion"
Cohesion: 0.04
Nodes (44): _aggregate_stats(), backfill_ufc_csv(), _cached_etag(), _etag_cache_path(), ingest_ufc_results_for_date_csv(), load_fighter_profiles_from_csv(), _mirror_etag(), _read_csv() (+36 more)

### Community 256 - "Prop market coverage probe tests"
Cohesion: 0.06
Nodes (20): candidate_markets(), _standard_markets(), _board_markets(), test_a_two_sided_market_is_never_reported_one_sided(), test_an_all_line_leg_slip_does_not_claim_a_model(), test_it_asks_about_the_board_columns_that_are_permanently_blank(), test_it_reports_supported_but_empty_apart_from_unsupported(), test_no_market_is_asked_about_twice() (+12 more)

### Community 257 - "NFL luck gap and teaser research"
Cohesion: 0.06
Nodes (46): am_to_dec(), at_lead(), boot_ci(), devig2(), ev(), odds_2026(), pbp(), player_log() (+38 more)

### Community 259 - "NBA schedule refresh planning tests"
Cohesion: 0.21
Nodes (16): plan(), _espn(), _flex(), _stored(), test_a_game_the_schedule_lacks_is_added_and_given_a_games_row(), test_a_game_with_no_tip_yet_never_moves_a_stored_tip(), test_a_games_row_only_this_refresh_wrote_follows_espn(), test_a_listed_game_espn_does_not_show_is_named_not_dropped() (+8 more)

### Community 262 - "UFC fight feature engine"
Cohesion: 0.13
Nodes (20): _age_years(), _assemble_ufc_features(), career_stats(), compute_ufc_target(), infer_five_rounds(), synthetic_round_total(), _fight(), _stats_pair() (+12 more)

### Community 263 - "NFL schedule refresh tests"
Cohesion: 0.12
Nodes (13): upcoming_schedule_rows(), _game(), _jobs(), test_a_game_that_has_started_is_not_touched(), test_a_naive_now_is_read_as_utc(), test_a_new_game_is_inserted_whole_and_games_comes_first(), test_a_row_the_deploy_left_without_a_venue_gets_one(), test_a_wild_card_in_january_carries_last_years_season_label() (+5 more)

### Community 266 - "NBA quarter game model tests"
Cohesion: 0.11
Nodes (29): _data(), _game(), _ladder(), _no_real_load(), _point(), _pricing_world(), _q(), _row() (+21 more)

### Community 267 - "NBA second game luck study"
Cohesion: 0.06
Nodes (40): as_of_ratings(), _before(), box_mismatches(), f4_projections(), f4_signal(), _known_team(), pair_ratings(), project_ratings() (+32 more)

### Community 271 - "Line CLV sign and orientation tests"
Cohesion: 0.05
Nodes (12): _load(), test_a_line_that_held_is_exactly_zero_not_none(), test_a_missing_close_is_not_a_zero(), test_a_side_that_cannot_be_oriented_returns_none_rather_than_guessing(), test_the_home_and_away_sides_are_exact_mirrors(), test_the_prop_market_flag_wins_over_the_market_string(), test_the_signs_are_the_negation_of_the_apps_entry_frame(), test_marker_file_is_in_tree_so_the_freeze_would_not_block_the_worker() (+4 more)

### Community 275 - "NBA game harness tests"
Cohesion: 0.10
Nodes (21): _fetches(), _games(), _offers(), _q(), _stale_cache(), test_a_cell_reports_its_pooled_walk_forward_and_writes_its_bets(), test_a_graded_load_refuses_a_season_the_cache_does_not_price(), test_a_graded_load_refuses_rows_that_match_no_purchase() (+13 more)

### Community 280 - "NFL in-play flow slice backtest"
Cohesion: 0.13
Nodes (16): _clustered_ci(), _qcut(), _rows_for(), slice_table(), verdict(), _frame(), _table(), test_a_bias_living_in_one_quarter_reads_as_concentrated() (+8 more)

### Community 283 - "NBA in-game staleness gate"
Cohesion: 0.12
Nodes (15): coverage(), day_sums(), extra(), gate(), lag_profile(), logloss_gap(), main(), outcome() (+7 more)

### Community 287 - "Model calibration check tests"
Cohesion: 0.09
Nodes (12): _calibration_sql(), test_a_flagged_model_is_named_eligible_or_not(), test_a_thin_model_is_still_excluded_rather_than_accused(), test_eligibility_notes_must_not_sink_the_gap_check(), test_eligibility_notes_parse_the_payload_verdicts(), test_it_grades_the_calibrated_probability_not_the_raw_one(), test_it_joins_picks_to_reach_the_calibrated_column(), test_the_check_has_a_skip_budget_that_survives_a_regime_change() (+4 more)

### Community 288 - "MLB live game state poller"
Cohesion: 0.17
Nodes (16): _detect_triggers(), _is_active_or_starting_soon(), test_active_in_progress_game_is_active(), test_combined_changes_fire_all_relevant_triggers(), test_due_up_change_fires_due_up_change(), test_final_game_is_not_active(), test_identical_state_fires_no_triggers(), test_inning_half_change_fires_inning_change() (+8 more)

### Community 29 - "College football stats parsing"
Cohesion: 0.08
Nodes (23): _int(), _num(), parse_advanced_stats(), parse_ratings(), parse_returning(), parse_season_stats(), parse_talent(), parse_team_game_stats() (+15 more)

### Community 291 - "NFL live rush pace edge study"
Cohesion: 0.18
Nodes (26): _asof(), boot_p(), build_state(), first(), grade(), initial_last(), load_pbp(), main() (+18 more)

### Community 294 - "NCAAF player stats parser tests"
Cohesion: 0.18
Nodes (17): parse_player_game_stats(), _cat(), _parse(), _payload(), _team(), test_a_game_missing_from_the_id_map_is_skipped_not_guessed(), test_a_player_gets_one_row_across_every_category(), test_a_player_with_nothing_we_track_is_skipped() (+9 more)

### Community 295 - "Discord and X results posting"
Cohesion: 0.05
Nodes (41): _apply(), _assert_split(), _between(), _first_sql(), _per_game_sql(), _sweep_sql(), test_per_game_clear_keeps_nfl_prop_rows_on_a_game_the_loop_reaches(), test_sweep_keeps_unstarted_nfl_prop_nones_and_still_clears_game_nones() (+33 more)

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
Cohesion: 0.13
Nodes (20): pseudo_clv(), _bet(), _preds(), _quote(), _quotes(), synthetic(), test_a_far_away_kickoff_is_a_different_season(), test_a_quote_before_any_state_is_dropped() (+12 more)

### Community 318 - "tests/test_live_record_start_views.py"
Cohesion: 0.09
Nodes (12): _body(), _code(), test_both_published_views_carry_the_live_date_gate(), test_it_runs_after_the_migration_that_used_to_own_the_daily_view(), test_migration_is_one_statement(), test_migration_is_registered_with_the_worker_runner(), test_neither_view_reads_the_sweep_universe(), test_no_ddl_outside_the_guarded_branches() (+4 more)

### Community 319 - "UFC fight CSV event builder"
Cohesion: 0.18
Nodes (13): build_events(), build_fighter_index(), _kd_int(), _scheduled_rounds(), _split_bout(), _fixture(), test_build_events_draw_and_nc(), test_build_events_loser_first_outcome_is_swapped() (+5 more)

### Community 322 - "NHL shot events parsing"
Cohesion: 0.12
Nodes (27): _clock(), decode_situation(), _event_team_id(), parse_game(), _period(), period_sides(), _shooter(), shooter_view() (+19 more)

### Community 326 - "Discord price bound and risk math"
Cohesion: 0.09
Nodes (16): test_risk_and_win_always_agree_with_the_price(), _dec(), test_a_field_without_a_bound_renders_without_the_clause(), test_a_model_with_no_own_ev_floor_is_bound_by_the_global_one(), test_a_price_floor_can_be_the_binding_gate(), test_a_rounded_bound_still_clears_the_bound_it_came_from(), test_even_money_is_plus_one_hundred(), test_no_bound_from_junk_rather_than_a_guess() (+8 more)

### Community 327 - "NHL prop odds fetch gate"
Cohesion: 0.06
Nodes (25): due(), test_a_game_confirmed_after_its_newest_prop_fetch_owes_one_more_open(), test_an_unknown_game_with_no_prop_fetch_still_owes_its_opening_snapshot(), test_the_close_is_the_post_confirmation_snapshot_when_both_are_owed(), _book(), test_a_200_on_both_calls_merges_the_alternate_lines(), fake_fetch(), test_a_game_first_priced_inside_the_final_window_gets_nothing_more() (+17 more)

### Community 328 - "Prop box score cooled refill"
Cohesion: 0.11
Nodes (25): fill_missing(), _call_fill(), _cooled(), _day(), _default_mlb(), _default_nba(), _default_nfl(), _default_nhl() (+17 more)

### Community 329 - "nfl/models/opener_spread.py"
Cohesion: 0.14
Nodes (11): age_tag(), american_to_prob(), _bettable_books(), clean_board(), edge_tier(), evaluate_board(), held_minutes(), model_prob_for_dev() (+3 more)

### Community 33 - "nfl/live_model/feeds: test_feed_resilience + espn"
Cohesion: 0.07
Nodes (31): _competitors(), _deref(), fetch_live_events(), _https(), make_fetcher(), fetch(), parse_core_event(), _score() (+23 more)

### Community 330 - "House juice minimum odds floor"
Cohesion: 0.08
Nodes (19): min_odds_for(), _blocked_by_min_odds(), _apply_price_floor(), test_a_pick_with_no_price_is_never_blocked_by_the_floor(), test_an_explicit_floor_wins_in_BOTH_directions(), test_every_registered_model_has_an_effective_floor(), test_ordinary_prices_still_fire(), test_the_default_is_overridable_without_a_code_change() (+11 more)

### Community 333 - "tests/test_nfl_wind_fire_window.py"
Cohesion: 0.07
Nodes (18): _retractable_slate(), _slate(), test_a_blank_roof_at_a_NON_retractable_venue_is_unaffected(), test_a_closed_roof_is_still_indoor(), test_a_retractable_venue_with_an_unknown_roof_does_not_fire(), test_a_waiting_game_is_not_reported_as_a_collapsed_premise(), test_a_waiting_row_keeps_its_line_price_and_edge(), test_every_blank_roof_row_is_a_retractable_venue() (+10 more)

### Community 334 - "Custom model prop and game facts"
Cohesion: 0.13
Nodes (12): actual_from_log(), _capture_rank(), grade_ou(), in_backtest(), is_standard_market(), line_key(), _line_of(), _num() (+4 more)

### Community 335 - "tests/test_public_betting_ingestor.py"
Cohesion: 0.17
Nodes (17): parse_public_betting(), _pct(), _select_book(), _make_game(), test_parse_emits_six_rows(), test_parse_game_id_and_sides(), test_parse_marks_source_and_snapshot(), test_parse_missing_teams_returns_empty() (+9 more)

### Community 336 - "Basketball player positions ingestor"
Cohesion: 0.04
Nodes (44): _athlete_room(), _basketball(), basketball_group(), _cached_unmatched_ids(), _espn(), _fresh_source_ids(), _get_json(), ingest_player_positions() (+36 more)

### Community 339 - "tests/test_service_role_split.py"
Cohesion: 0.15
Nodes (11): _all_job_ids(), _sched(), test_an_unknown_role_runs_everything(), test_every_add_job_call_passes_an_id(), test_every_job_is_owned_by_exactly_one_role(), test_the_always_on_jobs_run_on_every_role(), test_the_default_preserves_the_single_container(), test_the_nfl_worker_stays_with_the_volume() (+3 more)

### Community 34 - "SQL percent escaping tripwire"
Cohesion: 0.21
Nodes (5): _adapt(), _parameterised_sql(), test_check_line_movement_query_interpolates(), test_parameterised_sql_escapes_literal_percents(), test_the_scanner_actually_catches_the_regression()

### Community 341 - "Health check skip budget tests"
Cohesion: 0.13
Nodes (11): test_a_stuck_gate_is_not_reported_as_stale_data(), _res(), test_a_non_skipped_result_is_never_touched(), test_a_stuck_gate_escalates_past_its_budget(), test_an_honest_offseason_skip_stays_skipped_but_shows_its_length(), test_applying_twice_does_not_double_annotate(), test_mlb_game_day_feeds_stay_skipped_through_the_longest_measured_offseason(), test_model_calibration_is_persisted() (+3 more)

### Community 342 - "NHL goalie gate insert guards"
Cohesion: 0.09
Nodes (14): _frozen(), _insert_constants(), _strings(), test_an_nhl_odds_fetch_that_stored_nothing_is_a_failed_step(), test_every_function_that_inserts_picks_is_behind_the_goalie_guard(), test_every_nhl_model_is_behind_a_goalie_guard(), test_every_picks_insert_is_behind_the_goalie_guard_or_named_with_a_reason(), test_no_writer_names_the_picks_table_through_a_variable() (+6 more)

### Community 343 - "API call log daily rollup tests"
Cohesion: 0.09
Nodes (10): test_a_fold_can_never_lower_a_stored_total(), test_a_new_process_does_not_prune_on_its_first_flush(), test_prune_rolls_up_before_it_deletes(), test_the_daily_table_is_created_and_locked_down(), test_the_daily_table_keys_on_day_api_and_source(), test_the_rollup_groups_by_eastern_day_not_utc(), test_the_rollup_reads_only_yesterday_and_today(), test_the_rollup_survives_a_failure_without_blocking_the_prune() (+2 more)

### Community 345 - "Model quality public fade detection"
Cohesion: 0.10
Nodes (9): _bet(), test_high_public_pct_on_a_fade_publisher_counts_as_a_fade(), test_low_public_pct_on_the_pick_side_counts_as_a_fade(), test_majority_share_warns_when_not_unanimous(), test_meta_steps_exclude_model_quality(), test_pipeline_step_never_fails_on_crit(), test_pipeline_step_never_fails_on_exception(), test_side_aliases_collapse_to_the_same_direction() (+1 more)

### Community 346 - "MLB over under retrain sweep job"
Cohesion: 0.08
Nodes (13): _side_rows(), test_the_raised_timeout_is_restored_after_the_job(), test_the_restore_puts_back_a_pre_existing_value(), test_marker_file_is_in_tree_so_the_freeze_would_not_block_the_worker(), test_missing_artifact_path_refuses_to_sweep_live(), test_over_covers_when_combined_score_beats_the_total_line(), test_price_below_the_house_floor_is_not_a_gradable_side(), test_push_on_the_total_emits_no_sides() (+5 more)

### Community 347 - "Mobile sport filter persistence tests"
Cohesion: 0.14
Nodes (10): _load_body(), _sports(), _src(), test_a_visit_scoped_sport_change_does_not_persist(), test_a_writer_landing_during_the_hydrate_is_not_overwritten(), test_every_sport_survives_a_cold_start(), test_no_retired_sport_is_a_selectable_chip(), test_no_second_hand_written_sport_list_in_the_hook() (+2 more)

### Community 348 - "Custom model game facts tests"
Cohesion: 0.09
Nodes (29): assemble_game(), grade_ats(), grade_ml(), grade_total(), is_primetime(), lead_hours(), line_at_start(), _num() (+21 more)

### Community 35 - "NBA second game projection tests"
Cohesion: 0.06
Nodes (41): _box(), _cons(), _dist(), _games(), _games_file(), _inj(), _neutral(), _rapm_inputs() (+33 more)

### Community 351 - "Live slate midnight date discovery"
Cohesion: 0.10
Nodes (10): _at(), test_both_live_loops_share_one_definition_of_the_slate(), test_by_daytime_yesterday_is_dropped(), test_just_after_midnight_still_asks_about_yesterday(), test_just_before_midnight_asks_about_today_only(), test_the_apps_live_hook_resolves_the_window_per_fetch(), test_the_apps_live_reads_take_a_LIST_of_dates(), test_the_ncaaf_live_loop_got_the_same_fix() (+2 more)

### Community 353 - "NFL in-play flow bias validation"
Cohesion: 0.14
Nodes (15): bias_table(), main(), apply_anchor(), load_rows(), main(), attach_ids(), _game_marks(), load_snapshots() (+7 more)

### Community 354 - "Custom model facts refresh and load"
Cohesion: 0.10
Nodes (22): parse_date(), _fetch(), _games(), _aware(), _buildable(), _clock(), due_games(), _fact_rows() (+14 more)

### Community 356 - "Intraday weather and news freshness"
Cohesion: 0.16
Nodes (9): _is_fresh(), _age(), test_an_unknown_age_refetches_rather_than_skipping(), test_fresh_data_is_skipped(), test_stale_data_is_refetched(), test_the_6am_pipeline_is_never_throttled(), test_the_boundary_refetches(), test_the_max_ages_are_sane_and_overridable() (+1 more)

### Community 358 - "NBA period map pricing tests"
Cohesion: 0.11
Nodes (16): _maps(), ran(), test_a_purchase_outside_45_to_75_minutes_is_never_a_decision(), test_a_season_with_too_few_earlier_games_gets_no_pricing_and_the_run_stops(), test_full_refuses_without_the_owners_go_before_reading_anything(), test_team_totals_take_f6ds_distribution(), test_the_market_pricing_reads_only_earlier_seasons(), test_the_period_map_and_its_error_read_only_seasons_before_the_one_they_price() (+8 more)

### Community 359 - "X posting and brand avatar"
Cohesion: 0.11
Nodes (15): discover(), fetch_all(), _get_image(), main(), _original_size(), store(), _x_api_profile(), test_form_params_are_in_the_signature_and_not_in_the_header() (+7 more)

### Community 36 - "NCAAF CFBD ingestor tests"
Cohesion: 0.03
Nodes (58): build_ncaaf_game_id(), _day_before(), eastern_game_date(), parse_games(), parse_lines(), parse_teams(), retain_existing_cfbd_ids(), shrink_to_prior() (+50 more)

### Community 360 - "NFL in-play 2025 edge study"
Cohesion: 0.14
Nodes (22): attach_games(), attach_state(), diagnostics(), dispersion(), fit_totals_margin(), h2_accuracy(), h3_accuracy(), h4() (+14 more)

### Community 366 - "Kalshi game market recorder"
Cohesion: 0.08
Nodes (9): event_code(), event_date(), test_a_kalshi_outage_cannot_break_the_pass(), test_event_code_is_shared_across_series(), test_event_date_is_searched_not_anchored(), test_kalshi_labels_expand_st_and_use_the_explicit_map(), test_resolution_runs_after_every_snapshot(), test_the_recorder_is_scheduled_on_the_pipeline_role() (+1 more)

### Community 368 - "HTTP request timeout floor"
Cohesion: 0.11
Nodes (11): install_timeout_floor(), _call(), clean_requests(), test_a_call_with_no_timeout_gets_one(), test_an_explicit_timeout_is_never_overridden(), test_installing_twice_is_a_no_op(), test_the_deadline_is_env_overridable(), test_the_deadline_survives_telemetry_being_turned_off() (+3 more)

### Community 369 - "No-vig CLV capture and entrypoint checks"
Cohesion: 0.11
Nodes (13): _is_main_guard(), _modules_with_guard(), test_at_least_one_entrypoint_is_scanned(), test_nothing_is_defined_after_the_main_guard(), _fn(), test_a_missing_bet_book_close_is_not_filled_from_another_book(), test_backfill_revisits_anything_that_is_not_standard_v2(), test_capture_grades_raw_same_book_and_a_separate_pinnacle_edge() (+5 more)

### Community 370 - "UFC stats page parsing tests"
Cohesion: 0.08
Nodes (27): _int_or_none(), _mmss_to_sec(), normalize_method(), parse_event_page(), _two_ints(), parse_fight_page(), rounds_completed(), _fight_minutes() (+19 more)

### Community 371 - "NCAAF totals probability regression tests"
Cohesion: 0.10
Nodes (14): total_over_prob(), test_artifact_kind_is_routed_by_the_scorer(), test_asymmetry_is_real_and_would_have_bitten(), test_extremes_are_clamped_away_from_certainty(), test_model_above_the_line_favours_the_over(), test_model_below_the_line_favours_the_under(), test_no_dk_total_means_skip_not_prob_only(), test_no_residuals_returns_one_half_not_a_confident_bet() (+6 more)

### Community 375 - "Refresh pass step ordering tests"
Cohesion: 0.10
Nodes (13): _order(), test_a_parallel_step_that_fails_is_still_recorded(), test_no_sequential_step_runs_while_a_parallel_group_is_open(), test_opening_signals_follows_every_scorer(), test_parlay_follows_opening_signals(), test_scoring_follows_every_ingest(), test_settle_follows_every_results_ingest(), test_sync_thresholds_follows_migrations_and_precedes_scoring() (+5 more)

### Community 377 - "NFL halftime out-of-sample study"
Cohesion: 0.09
Nodes (36): backfill_cost(), bets(), bh(), clean_2h(), fmt(), forward_2026(), hdr(), _line_models() (+28 more)

### Community 379 - "NHL period goals feed tests"
Cohesion: 0.13
Nodes (13): agrees(), period_goals(), _game(), _goal(), test_a_feed_game_becomes_the_same_game_id_the_games_table_uses(), test_a_game_still_in_play_or_a_goal_for_neither_side_is_not_a_result(), test_a_team_named_as_an_object_is_read_too(), test_goals_are_counted_into_the_period_they_were_scored_in() (+5 more)

### Community 380 - "NCAAF in-play backtest game states"
Cohesion: 0.16
Nodes (11): main(), _classify(), classify_report(), _detect_score_convention(), load_pbp(), load_platform_games(), pace_report(), _repair_day_offsets() (+3 more)

### Community 382 - "Mobile bankroll screen checks"
Cohesion: 0.23
Nodes (13): _read(), test_copy_is_word_for_word(), test_display_only_nothing_sized(), test_error_text_uses_the_text_safe_red(), test_explainer_no_longer_denies_a_bankroll(), test_exposure_card_hook_and_banner_stay_removed(), test_keyboard_never_covers_the_field(), test_locale_separators_decide_the_decimal() (+5 more)

### Community 383 - "Team rest and schedule context tests"
Cohesion: 0.18
Nodes (16): collapse(), team_view(), _rest_days(), _at(), _row(), test_a_game_still_to_be_played_is_pending_and_counts_for_rest(), test_a_past_game_that_never_got_a_result_stops_holding_after_the_lookback(), test_a_ufc_fight_is_done_once_its_card_is_in_the_fight_log() (+8 more)

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

### Community 392 - "NFL in-play prop assessment report"
Cohesion: 0.19
Nodes (14): _connect(), american_b(), boot_ci(), build(), cluster_se_mean(), implied(), load(), main() (+6 more)

### Community 394 - "X post image fetching"
Cohesion: 0.25
Nodes (3): test_fetch_https_image_sniffs_bytes_and_refuses_gif(), fetch_https_image(), _sniff_tweet_image()

### Community 396 - "NHL goalie gate core checks"
Cohesion: 0.20
Nodes (8): _first_names_agree(), same_goalie(), same_goalie_name(), _seen_at(), _stale(), team_problem(), _utc(), test_ids_decide_when_both_sides_have_one()

### Community 399 - "NFL live leader model tests"
Cohesion: 0.10
Nodes (19): fit_wp(), logit_irls(), wp_design(), wp_lookup(), art(), _d(), _raw(), test_600_seconds_and_both_lead_ends_are_inside() (+11 more)

### Community 400 - "Mobile paused catalog tests"
Cohesion: 0.17
Nodes (11): _block(), _read(), test_a_cached_row_without_a_paused_flag_stays_on_the_bundle_until_the_fetch(), test_paused_picks_reach_the_all_board_only_and_labelled(), test_stats_add_pick_refuses_a_paused_model(), test_the_bet_type_picker_filters_paused_models(), test_the_custom_model_picker_is_three_bet_types(), test_the_models_list_filters_paused_models() (+3 more)

### Community 401 - "Free pick card and X results tests"
Cohesion: 0.13
Nodes (11): _pick(), test_every_offerable_book_has_a_human_name_on_both_surfaces(), test_the_free_card_names_the_cheaper_book(), test_the_free_card_query_reads_the_columns_it_renders(), test_the_good_to_clause_is_dropped_not_truncated_when_it_will_not_fit(), test_the_tweet_names_the_cheaper_book(), test_the_tweet_never_publishes_a_worse_price_than_draftkings(), test_the_tweet_publishes_the_good_to_bound_when_it_fits() (+3 more)

### Community 402 - "NCAAF opener board visibility tests"
Cohesion: 0.07
Nodes (21): _days_until(), _line(), _patch(), test_a_declined_rule_can_never_leak_a_signal(), test_a_fired_pick_clears_its_own_probability_floor(), test_a_no_signal_row_does_not_lock_an_ncaaf_game_for_the_week(), test_books_agreeing_is_a_no_signal_row(), test_days_until_is_none_without_a_kickoff_time() (+13 more)

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

### Community 411 - "Database URL diagnosis tool"
Cohesion: 0.16
Nodes (17): diagnose(), bad(), _safe(), _fails(), _levels(), test_a_correct_url_reports_no_failures(), test_bare_postgres_on_a_DIRECT_host_is_fine(), test_bare_postgres_on_a_pooler_host_is_named() (+9 more)

### Community 413 - "NFL prop threshold window tests"
Cohesion: 0.11
Nodes (8): test_live_webhook_map_reads_the_per_sport_env_vars(), cfg(), test_no_nfl_prop_market_is_back_on_the_uniform_placeholder(), test_one_bad_date_does_not_cost_the_others(), test_the_prop_window_has_exactly_one_declaration(), test_the_scorer_step_covers_the_whole_window_not_one_date(), fake(), test_the_three_threshold_dicts_agree_for_every_nfl_prop_market()

### Community 414 - "tests/test_nhl_research_job.py"
Cohesion: 0.15
Nodes (11): test_a_dump_argument_is_refused(), test_a_model_must_be_a_real_spec(), test_a_season_must_be_a_priced_one(), test_an_unknown_script_is_refused(), test_an_unknown_top_level_key_is_refused(), test_every_runnable_module_has_a_main(), test_every_runnable_module_writes_no_database_row(), test_the_artifact_grade_names_the_rule_production_runs() (+3 more)

### Community 415 - "tests/test_settlement_timing.py"
Cohesion: 0.14
Nodes (9): test_capture_clv_requires_the_game_to_have_started(), test_future_kickoffs_are_not_treated_as_started(), test_game_log_skips_per_game_not_per_date(), test_mirror_unchanged_is_conservative_when_it_cannot_tell(), test_started_games_are_recognised_in_every_stored_format(), test_ufc_poll_uses_the_etag_gate_and_the_daily_run_does_not(), test_unparseable_timestamps_yield_none_rather_than_a_guess(), test_z_and_offset_forms_are_the_same_instant_but_not_the_same_string() (+1 more)

### Community 418 - "Push delivery ticket parsing tests"
Cohesion: 0.22
Nodes (10): _msgs(), test_a_credentials_failure_disables_nobody(), test_a_request_level_rejection_accepts_nothing(), test_a_retired_device_is_named_for_disabling(), test_a_single_message_reply_may_be_a_bare_object(), test_a_ticket_that_is_not_an_object_is_not_a_delivery(), test_an_error_ticket_is_not_counted_as_sent(), test_an_unpairable_reply_counts_nothing_and_disables_nothing() (+2 more)

### Community 42 - "DataGolf ingestor and NHL SBR archive"
Cohesion: 0.08
Nodes (29): _american(), build_game_id(), event_slug(), is_team_event(), normalize_dg_name(), _num(), parse_event_list(), parse_event_rounds() (+21 more)

### Community 422 - "Mobile pick button script tests"
Cohesion: 0.03
Nodes (64): tsx_cmd(), _node_strips_types(), test_a_stored_unknown_filter_key_does_not_drop_the_model_list(), test_byom_filters_reject_mixed_case_and_unknown_keys(), test_today_et_ignores_the_container_timezone(), test_the_board_checks_pass(), test_the_behavioural_checks_pass(), _read() (+56 more)

### Community 425 - "NFL odds cache import to Supabase"
Cohesion: 0.12
Nodes (9): _allowed(), _data_dirs(), test_a_rerun_after_the_resolver_improves_adds_only_the_gap(), test_every_buying_ingestor_keys_its_resume_on_a_source_marker(), test_no_undeclared_data_store_on_disk(), test_the_importer_resolves_a_postponed_game(), test_the_importer_still_refuses_an_event_with_no_game(), test_the_nfl_odds_cache_has_an_importer() (+1 more)

### Community 426 - "tests/test_health_check_observe.py"
Cohesion: 0.14
Nodes (10): _crit(), fake(), test_a_crit_does_not_fail_the_observe_path(), test_a_crit_still_fails_the_daily_step(), test_an_exception_does_not_fail_the_observe_path(), test_daily_syncs_thresholds_after_view_migrations(), test_it_still_runs_the_check_when_observing(), test_ok_is_identity_in_both_modes() (+2 more)

### Community 427 - "NFL in-play prop flow model"
Cohesion: 0.10
Nodes (20): best_hit(), _boot_ci(), drop_degenerate(), evaluate(), fit_time_curve(), main(), report(), sweep() (+12 more)

### Community 428 - "NFL 2026 opener and wind tracker"
Cohesion: 0.12
Nodes (16): lead_days(), opener_verdict(), _row(), _src(), test_a_wind_lock_past_four_days_is_flagged_not_resized(), test_config_comments_state_the_policy(), test_live_cuts_did_not_move(), test_max_fire_lead_stays_four_in_the_live_model() (+8 more)

### Community 429 - "NFL in-play prop line churn check"
Cohesion: 0.19
Nodes (13): churn_table(), main(), verdict(), _snaps(), test_a_line_moving_every_interval_reads_as_under_sampled(), test_a_missing_key_column_fails_loudly_rather_than_grouping_coarser(), test_a_single_snapshot_contributes_no_interval(), test_a_still_line_reads_as_still() (+5 more)

### Community 431 - "tests/test_pick_lock_is_on_picks.py"
Cohesion: 0.16
Nodes (9): _between(), _sql(), test_a_bet_is_still_never_re_scored(), test_only_a_bet_locks_a_pair(), test_the_cleanup_covers_the_whole_look_ahead_window(), test_the_cleanup_never_touches_a_started_game_or_a_live_row(), test_the_lock_is_no_longer_ncaaf_specific(), test_the_prop_and_live_locks_are_unchanged() (+1 more)

### Community 433 - "Mobile pick category checks"
Cohesion: 0.13
Nodes (13): _block(), _config_scorable_ids(), _meta_ids(), _meta_types(), _read(), test_every_model_id_derives_its_own_declared_category(), derived(), test_every_scorable_model_has_a_label_in_the_app() (+5 more)

### Community 435 - "NFL in-play prop rule and staleness reports"
Cohesion: 0.19
Nodes (11): american_b(), boot_roi(), first_per_player(), grade(), load(), main(), report(), main() (+3 more)

### Community 436 - "X team hashtags"
Cohesion: 0.12
Nodes (15): test_college_nicknames_and_a_shared_mascot_falls_back_to_the_school(), test_freepicks_in_the_pool_is_dropped(), test_team_hashtags_use_the_nickname(), pick_hashtags(), _add(), reach_pool(), _both_teams(), _from_full_names() (+7 more)

### Community 437 - "Per-model threshold config tests"
Cohesion: 0.07
Nodes (9): test_an_own_floor_does_not_take_a_model_off_the_calibration_map(), test_every_model_carries_its_own_thresholds(), test_every_own_floor_names_a_live_model(), test_models_on_own_probability_is_not_derived_from_the_floor_dict(), test_no_own_floor_tightens_a_model_past_the_global_floor(), test_only_a_market_priced_model_carries_a_negative_floor(), test_own_ev_floor_and_model_min_ev_stay_disjoint(), test_the_models_the_global_floor_silently_removed_can_bet_again() (+1 more)

### Community 438 - "NBA game two verdict grid tests"
Cohesion: 0.21
Nodes (20): _cell(), _grid(), _hgrid(), _house(), _mid(), test_a_cell_below_the_bet_count_enters_the_correction_at_p_one(), test_a_cell_clearing_every_bar_passes(), test_a_cell_with_no_dominant_side_is_not_held_to_a_blind_bet() (+12 more)

### Community 44 - "scripts: build_nfl_live_leader_artifact + model"
Cohesion: 0.06
Nodes (47): wp_design(), wp_lookup(), attach_games(), build_artifact(), check_possession(), _dk_pregame_spread(), _download(), _first_bets() (+39 more)

### Community 442 - "Mobile player stat groups tests"
Cohesion: 0.15
Nodes (10): _set_literal(), _src(), test_a_group_is_filled_only_by_a_real_number(), test_a_tab_opens_on_the_stat_the_player_fills_most(), test_defensive_positions_get_only_the_defense_group(), test_every_logged_position_is_classified(), test_non_defensive_positions_get_no_defense_group(), test_offensive_positions_are_not_defensive() (+2 more)

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
Cohesion: 0.08
Nodes (14): impossible_games_played(), _played_actual(), test_a_missing_count_is_reported_not_silently_passed(), test_an_honest_row_passes(), test_claiming_fewer_games_than_played_is_fine(), test_feb_gp_climbing_vs_zero_regular_season_still_fails(), test_mlb_twin_codes_do_not_false_crit(), test_mlb_twin_reverse_lookup_also_resolves() (+6 more)

### Community 46 - "Worker job queue runner"
Cohesion: 0.03
Nodes (35): derive_first_pitch(), test_the_worker_job_is_registered_and_defaults_to_dry_run(), test_runner_captures_stdout_from_the_script_main(), test_the_discord_publish_job_calls_the_ordinary_producer(), test_the_discord_publish_job_takes_an_optional_date(), test_the_job_defaults_to_probing_and_caps_its_sample(), _announce(), _execute() (+27 more)

### Community 460 - "NBA public betting splits ingestor"
Cohesion: 0.11
Nodes (14): clean_pair(), not_started(), test_a_late_west_coast_tip_belongs_to_the_previous_et_date(), test_a_lone_side_is_kept_as_served(), test_a_pair_that_does_not_sum_to_100_is_dropped(), test_a_v1_listing_rewritten_more_than_400_minutes_after_tip_is_late(), test_a_valid_pair_sums_to_100_within_rounding(), test_a_zero_zero_pair_is_missing_not_zero() (+6 more)

### Community 462 - "Anonymous read access grants"
Cohesion: 0.03
Nodes (49): all_readable(), closed_tables(), lock_down_sql(), write_verbs_for(), _anon_can_read(), _function_plan(), _function_signature(), main() (+41 more)

### Community 464 - "NCAAF gameday credit cap"
Cohesion: 0.12
Nodes (6): gameday_mod(), test_credit_cap_covers_a_full_saturday_at_the_configured_cadence(), test_idle_cadence_is_slower_than_the_live_cadence(), test_kickoffs_already_past_are_not_counted_as_upcoming(), test_state_cadence_is_fast_enough_to_react_to_a_drive(), test_the_effective_odds_cadence_is_bounded_by_the_pass()

### Community 465 - "nfl/scripts/backtest_opener.py"
Cohesion: 0.24
Nodes (9): boot(), by_season(), exp_win(), load(), main(), price(), report(), residuals() (+1 more)

### Community 466 - "Paused model assessment grading tests"
Cohesion: 0.11
Nodes (12): assess(), _half(), fetch(), grade(), sweep(), _units(), _rows(), test_a_cell_below_the_floor_is_not_a_result() (+4 more)

### Community 467 - "Bounded database pruning"
Cohesion: 0.11
Nodes (13): _after_nth_delete(), _expire_after_deletes(), execute(), _is_delete_sql(), nba_paths(), _one_market(), test_a_spent_budget_starts_no_statement_not_even_a_listing(), test_a_thinning_error_that_is_not_a_timeout_is_raised() (+5 more)

### Community 468 - "tests/test_latest_odds_views.py"
Cohesion: 0.25
Nodes (13): _app_columns(), _function(), test_every_log_table_has_its_insert_trigger_and_the_odds_tables_an_update_trigger(), test_every_view_reads_its_state_table_and_never_the_log(), test_no_pending_view_migration_re_creates_these_views_over_the_log(), test_the_dk_view_returns_the_apps_columns_in_order(), test_the_exclusions_survived_the_move(), test_the_game_view_returns_the_apps_columns_in_order() (+5 more)

### Community 47 - "scripts/nfl_edge_gameline_rules.py"
Cohesion: 0.12
Nodes (40): ats(), bh(), board_at(), board_open(), bstat(), cell(), dog_ats_frame(), dog_frame() (+32 more)

### Community 472 - "NBA schedule ingestor"
Cohesion: 0.20
Nodes (11): ot_periods(), schedule_rows(), season_str(), _tv(), _row(), test_a_late_west_coast_tip_keeps_its_eastern_date(), test_an_undecided_playoff_slot_is_skipped(), test_game_type_is_read_from_the_first_three_digits() (+3 more)

### Community 476 - "tests/test_transaction_pooler.py"
Cohesion: 0.19
Nodes (8): _transaction_endpoint(), test_a_direct_connection_is_left_alone(), test_a_local_postgres_is_left_alone(), test_a_supabase_session_url_becomes_the_transaction_url(), test_it_is_idempotent(), test_only_the_port_changes(), test_the_escape_hatch_works(), test_the_job_queue_still_gets_session_mode()

### Community 477 - "Database URL env fallback"
Cohesion: 0.09
Nodes (19): main(), scram_stored_key(), _classes(), main(), database_url(), _default_env_path(), env_value(), parse_env_file() (+11 more)

### Community 482 - "Game injury veto gate"
Cohesion: 0.24
Nodes (16): apply_to_picks(), player_matches_veto(), veto_reason(), _bet(), _idx(), _relevant(), test_avoid_and_none_are_not_downgraded(), test_missing_clocks_fail_open() (+8 more)

### Community 483 - "MLB play-by-play ingestor"
Cohesion: 0.16
Nodes (15): _bases_after_from_matchup(), parse_game_plays(), parse_play(), _split_event_type(), test_bases_empty_matchup(), test_bases_with_runners(), test_parse_game_plays_empty_feed(), test_parse_game_plays_walks_full_inning() (+7 more)

### Community 484 - "Team stats rebuild and as-of checks"
Cohesion: 0.15
Nodes (10): already_a_series(), _games(), live_season_snapshot_grace(), main(), _prior_season_rates(), rebuild_sport(), _team_games(), verify() (+2 more)

### Community 487 - "supabase/functions/sharpsports/index.ts"
Cohesion: 0.28
Nodes (14): americanFromBetSlip(), asArray(), createContext(), isSettled(), json(), pick(), pullAndUpsert(), readBets() (+6 more)

### Community 488 - "NHL derivative totals backtest"
Cohesion: 0.18
Nodes (15): day_interval(), select_bets(), blind_rows(), _csv(), even_money(), game_sides(), _line(), load() (+7 more)

### Community 491 - "Rule model market reading tests"
Cohesion: 0.15
Nodes (10): _case(), _clv_game_market(), _like(), _prompt_case(), _scorer_case(), test_the_case_reader_reads_the_name_patterns_as_postgres_does(), test_the_claude_mobile_prompt_reads_the_rule_card_s_market(), test_the_closing_line_functions_are_recreated_when_they_change() (+2 more)

### Community 492 - "NCAAF situational spot search"
Cohesion: 0.18
Nodes (7): is_bowl_game(), build_spots(), evaluate(), load_team_games(), main(), wilson(), test_is_bowl_game()

### Community 493 - "NFL schedule read from database tests"
Cohesion: 0.11
Nodes (19): _clock_file(), _et(), _feed(), _load_script(), _row(), _stale_file(), test_a_failed_read_keeps_the_last_list_and_none_without_one(), test_a_game_that_has_kicked_off_never_reaches_the_wind_card() (+11 more)

### Community 495 - "tests/test_worker_deps.py"
Cohesion: 0.16
Nodes (6): _requirements(), test_dashboard_packages_are_not_on_the_worker(), test_nothing_in_the_repo_actually_wants_a_gpu(), test_only_the_dashboard_imports_them(), test_the_dashboard_file_is_additive_not_a_replacement(), test_the_worker_asks_for_the_cpu_build_of_xgboost()

### Community 50 - "scheduler.py"
Cohesion: 0.04
Nodes (61): record_game_markets(), resolve_events(), abort_orphaned_refresh_runs(), build_scheduler(), _add_job(), _with_heartbeat(), _wrapped(), catch_up_daily_pipeline() (+53 more)

### Community 502 - "College football live ESPN feed"
Cohesion: 0.17
Nodes (16): check_feed_assumptions(), _competitors(), _count_plays(), _dig(), extract_live_events(), extract_summary_state(), _int(), _num() (+8 more)

### Community 503 - "Health check alert deliverability"
Cohesion: 0.12
Nodes (11): test_a_game_date_inside_the_window_counts(), test_a_lookahead_commence_counts_even_when_game_date_is_outside(), test_a_signal_locked_after_first_pitch_was_never_deliverable(), test_a_signal_locked_before_first_pitch_still_counts(), test_a_signal_locked_exactly_at_first_pitch_counts(), test_a_started_game_outside_the_window_does_not_count(), test_it_fails_toward_noticing(), test_mixed_timestamp_shapes_are_parsed_not_string_compared() (+3 more)

### Community 505 - "tests/test_mobile_stat_labels_match_the_server.py"
Cohesion: 0.21
Nodes (6): _meta_entries(), _server_stat_labels(), test_both_rushing_models_call_the_stat_the_same_thing(), test_the_live_model_names_the_market_it_actually_trades(), test_the_parser_actually_found_the_models(), test_the_unreconciled_models_are_named()

### Community 506 - "tests/test_ncaaf_fcs_visitor_names_migration.py"
Cohesion: 0.15
Nodes (5): _rows(), test_each_write_guards_on_its_own_property(), test_every_real_visitor_extends_the_wrong_one(), test_migration_is_one_statement(), test_the_nine_rows_and_their_finals_are_the_measured_ones()

### Community 508 - "NBA game model lab and rest features"
Cohesion: 0.04
Nodes (60): _counted_schedule(), from_cache(), game_schedule_features(), haversine_miles(), home_bases(), _offsets(), previous_game_load(), team_schedule_features() (+52 more)

### Community 51 - "NBA totals luck card"
Cohesion: 0.18
Nodes (5): load_quote_rows(), newest_fetch(), slate(), _snap_bound(), test_the_slate_prices_an_unlisted_quarterfinal_and_skips_the_cup_final()

### Community 513 - "tests/test_scorer_nfl_prop_like_escape.py"
Cohesion: 0.23
Nodes (9): _between(), _broken_per_game_sql(), _first_sql(), _per_game_sql(), _sweep_sql(), test_escape_tripwire_is_on_the_pr_ci_subset(), test_live_per_game_clear_interpolates_with_one_game_id(), test_live_sweep_clear_interpolates_with_date_horizon_now() (+1 more)

### Community 516 - "NHL stats views tests"
Cohesion: 0.15
Nodes (14): _date_filter_runs_before_dedupe(), anywhere(), blob(), filter_wraps_unique(), has_unique(), pred(), pred_inside_unique(), _pg_bin() (+6 more)

### Community 517 - "Trainer no-register mode tests"
Cohesion: 0.12
Nodes (9): not_registering(), registering(), test_a_normal_run_DOES_register(), test_baseline_artifacts_are_not_committable(), test_baseline_runs_write_somewhere_else(), test_default_is_to_register(), test_no_register_opens_no_database_connection(), _explode() (+1 more)

### Community 518 - "MLB backfill retry resilience"
Cohesion: 0.12
Nodes (6): test_a_failed_date_does_not_end_the_run_and_is_left_unmarked(), test_a_transient_network_error_is_retried(), test_an_http_error_is_NOT_retried(), test_it_gives_up_rather_than_looping_forever(), test_skip_existing_is_on_by_default(), test_the_resume_marker_distinguishes_historical_from_live_rows()

### Community 520 - "Market movement feature builder"
Cohesion: 0.07
Nodes (26): american_to_prob(), build_market_features(), _is_full_game_snap(), _latest_two_sided(), _snap_sort_key(), _snapshot_type_rank(), _unique_ordered(), _s() (+18 more)

### Community 522 - "Team stats rebuild row tests"
Cohesion: 0.09
Nodes (19): build_rows(), seasons_with_too_few_snapshots(), _game(), test_a_real_series_passes(), test_a_row_never_includes_its_own_date(), test_a_single_snapshot_season_is_flagged(), test_a_two_snapshot_season_is_flagged(), test_counts_accumulate_across_dates() (+11 more)

### Community 527 - "ESPN NHL probable goalies"
Cohesion: 0.18
Nodes (5): parse_probable(), test_fetch_fail_open(), test_fetch_uses_injected_fetch_and_keys_by_our_abbrev(), test_parse_probable_joins_display_name_to_our_abbrev(), test_parse_probable_skips_missing_name_or_slot()

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
Cohesion: 0.14
Nodes (9): card_path(), clear_card(), _load_script(), nfl_path(), test_a_dry_run_leaves_the_card_alone(), test_a_priced_wind_run_with_no_bets_removes_the_earlier_card(), test_clear_card_removes_todays_file_and_only_that(), test_the_path_cleared_is_the_path_the_publisher_reads() (+1 more)

### Community 535 - "NFL EV engine and stake sizing"
Cohesion: 0.09
Nodes (23): american_to_decimal(), cover_probs(), ev_per_unit(), fit_margin_pmf(), kelly_fraction(), margin_pmf_for(), add_model_mu(), load() (+15 more)

### Community 536 - "Mobile type-check baseline tests"
Cohesion: 0.29
Nodes (13): _entries(), _log(), _log_line(), _run(), test_a_clean_log_warns_for_every_baseline_entry(), test_a_compiler_crash_is_not_a_clean_run(), test_a_different_app_message_fails(), test_a_fixed_baseline_entry_warns_and_does_not_fail() (+5 more)

### Community 539 - "College football model search runner"
Cohesion: 0.17
Nodes (13): features_for(), exponential_recency_weights(), _logit(), make_ensemble(), fit_predict(), make_lgbm(), make_logreg(), fit_predict() (+5 more)

### Community 542 - "NFL overseas venue roof and wind tests"
Cohesion: 0.12
Nodes (15): _load(), nfl_path(), _paris_in_two_days(), _priced(), _reads(), _row(), test_a_home_game_keeps_its_rows_roof(), test_a_windy_paris_game_inside_the_window_is_bet() (+7 more)

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
Cohesion: 0.10
Nodes (9): test_a_graded_row_is_never_deleted(), test_a_row_with_computed_clv_is_never_deleted(), test_every_field_that_defines_the_bet_must_agree(), test_it_is_dry_run_by_default(), test_the_delete_selects_through_the_same_gates(), test_the_pair_must_be_an_old_shape_new_shape_pair(), test_the_report_and_the_delete_share_one_definition(), test_the_row_kept_is_the_one_locked_earlier() (+1 more)

### Community 552 - "tests/test_pbp_backfill_resilience.py"
Cohesion: 0.24
Nodes (6): _backfill_body(), test_a_failed_game_rolls_the_connection_back(), test_a_run_that_wrote_nothing_reports_an_error_not_a_success(), test_errors_are_counted_not_just_logged(), test_partial_failures_are_surfaced_too(), test_the_rollback_cannot_itself_raise()

### Community 553 - "ESPN injury team name mapping"
Cohesion: 0.15
Nodes (8): _espn_team_ids(), _fetch_nba_espn_team_ids(), _fetch_wnba_espn_team_ids(), _nba_espn_team_to_abbrev(), _nfl_espn_team_to_abbrev(), _normalize_team_name(), _wnba_espn_team_to_abbrev(), test_nfl_name_join_uses_our_abbrevs_not_espns()

### Community 563 - "NBA public splits side parsing"
Cohesion: 0.17
Nodes (9): an_pct(), parse_v1_sides(), v1_consensus_row(), test_a_one_percent_side_is_not_inflated_to_100(), test_out_of_range_or_junk_percentages_are_refused(), test_v1_flat_fields_map_to_market_side_and_metric(), test_v1_reads_only_the_consensus_book(), test_v1_rows_carry_the_inserted_stamp_and_its_lag() (+1 more)

### Community 567 - "NBA injury report time slots"
Cohesion: 0.16
Nodes (11): _all_slots(), _ampm(), new_slot(), old_slot(), pre_tip_slot(), slots_for_date(), test_format_switch_is_measured_and_both_are_probed_around_it(), test_hourly_dates_get_sixteen_hourly_slots() (+3 more)

### Community 569 - "NBA in-game study one tests"
Cohesion: 0.17
Nodes (15): _pin(), _q(), _rows(), _state(), test_every_fit_for_season_s_uses_earlier_seasons_only(), test_expected_rates_use_the_teams_earlier_dates_only(), test_ig1_bets_against_luck_and_the_control_with_it(), test_luck_counts_a_three_three_times_and_a_free_throw_once() (+7 more)

### Community 571 - "Mobile accessibility and CLV card tests"
Cohesion: 0.03
Nodes (52): node_exe(), node_strips_types(), _app(), _clv_card(), _node_strips_types(), _server(), test_a_label_book_nfl_pick_compares_its_line_with_that_book(), test_a_recorded_book_differs_from_the_derived_one() (+44 more)

### Community 572 - "NFL model import path tests"
Cohesion: 0.15
Nodes (6): _import_under_scheduler_env(), _scheduler_env(), test_no_nfl_script_uses_the_bare_models_import(), test_the_card_imports_under_the_schedulers_invocation(), test_the_exemption_is_the_loader_and_it_still_exists(), test_the_loader_reaches_nfls_models_not_the_platforms()

### Community 573 - "NBA public splits pipeline step"
Cohesion: 0.17
Nodes (11): inserted_minus_start_min(), side(), test_v1_inserted_lag_is_minutes_after_the_listed_start(), Coverage, Forward capture (2026-27), How to read it, NBA public betting splits (Action Network) — `nba_public_splits`, Rows to leave out (+3 more)

### Community 574 - "tests/test_prompt_reads_thresholds.py"
Cohesion: 0.18
Nodes (4): test_the_auto_pause_lookup_fails_open(), test_the_prompt_carries_no_per_model_cut(), test_the_prompt_still_says_it_is_pasted_once(), test_the_sync_mirrors_both_pause_registers()

### Community 576 - "NCAAF situational spot evaluation"
Cohesion: 0.22
Nodes (3): load_data(), main(), scan_spot()

### Community 577 - "NBA period score ingestion"
Cohesion: 0.32
Nodes (8): _int(), parse_period_rows(), _event(), test_espn_team_codes_map_to_ours(), test_one_row_per_period_under_our_game_id(), test_overtime_periods_follow_the_fourth(), test_quarters_that_do_not_sum_to_the_final_are_skipped(), test_unfinished_games_and_mismatched_period_counts_are_skipped()

### Community 580 - "scripts/render_brand_icons.py"
Cohesion: 0.24
Nodes (3): draw_mark(), main(), render()

### Community 581 - "Line state and alias migration tests"
Cohesion: 0.06
Nodes (36): main(), can_scratch(), env_dsn(), _free_port(), pg_bin(), scratch_cluster(), as_app(), db() (+28 more)

### Community 586 - "supabase/functions/stripe-webhook/index.ts"
Cohesion: 0.31
Nodes (9): applySubscription(), iso(), resolveUserId(), stripeGet(), timingSafeEqual(), toHex(), verifySignature(), admin (+1 more)

### Community 589 - "tests/test_mobile_neutral_signal_label.py"
Cohesion: 0.31
Nodes (7): _read(), test_explainer_names_neutral(), test_filters_and_card_speak_the_display_name(), test_model_screens_speak_the_display_name(), test_no_member_label_prints_a_raw_signal_type(), test_none_badge_reads_neutral(), test_withdrawn_pick_is_not_badged_neutral()

### Community 59 - "Discord period results recaps"
Cohesion: 0.07
Nodes (18): _at(), test_a_later_weekday_still_retries_that_week(), test_a_week_that_crosses_months_names_both(), test_an_evening_with_a_live_game_waits_for_the_next_morning(), test_discord_period_uses_the_results_webhook_and_ledgers_once(), test_monday_at_730_opens_the_prior_mon_sun_week(), test_monday_before_730_has_not_opened_the_new_week(), test_sunday_does_not_open_the_week_that_is_still_in_progress() (+10 more)

### Community 593 - "tests/test_scorer_commits_per_game.py"
Cohesion: 0.40
Nodes (8): _between(), _run_scorer_body(), test_a_lost_connection_re_runs_the_game_once_and_never_the_pass(), test_each_game_is_its_own_committed_unit(), test_no_bulk_delete_of_non_bet_rows_precedes_the_loop(), test_picks_are_only_counted_once_the_game_committed(), test_the_housekeeping_delete_is_a_sweep_after_the_loop(), test_the_outer_handler_still_records_the_failure()

### Community 596 - "NBA ESPN scoreboard parsing"
Cohesion: 0.19
Nodes (9): parse_nba_scoreboard(), _board(), _summary(), test_stats_are_read_by_label_and_a_dnp_is_omitted(), test_the_scoreboard_keeps_completed_games_only(), test_a_non_nba_opponent_is_dropped_not_invented(), test_espn_s_postponed_game_is_read_as_postponed(), test_overtime_comes_from_the_period_count() (+1 more)

### Community 598 - "Declared worker job validation tests"
Cohesion: 0.15
Nodes (7): _declared(), test_an_explicit_run_date_must_be_a_real_iso_date(), test_declared_keys_are_unique(), test_every_declared_job_names_a_registered_type(), test_every_declared_job_validates(), test_no_run_date_means_the_module_resolves_it(), test_the_validator_drops_unknown_args()

### Community 60 - "tests: test_wnba_availability + wnba_availability"
Cohesion: 0.07
Nodes (45): absence_features(), absent_teammates(), build_context_features(), expected_rotation(), is_starter_tier(), _mean(), prior_rows(), recent_team_game_dates() (+37 more)

### Community 600 - "NFL prop market EV floor sweep"
Cohesion: 0.09
Nodes (10): _book_of(), part_a_card(), part_b(), _table(), Nickname-aware settlement join, nfl_prop_market EV floor 0.20 -> 0.07, MODEL_OWN_EV_FLOOR per model, docs/followups.md (+2 more)

### Community 604 - "NFL ESPN injury ingest tests"
Cohesion: 0.13
Nodes (6): _fetch_nfl_espn_team_ids_core(), _fake_fetch(), test_core_nfl_listing_failure_returns_empty(), test_core_nfl_team_ids_resolve_lar_and_wsh_to_ours(), test_injury_fetch_raises_the_page_limit(), test_static_nfl_map_is_32_teams_on_our_abbrevs()

### Community 608 - "supabase/functions/sharpsports-webhook: index + index"
Cohesion: 0.25
Nodes (5): internalIdFor(), pick(), admin, admin, cors

### Community 609 - "Mobile Lines board pin tests"
Cohesion: 0.22
Nodes (9): _read(), test_a_missing_draw_price_is_remembered(), test_lines_board_pins_are_on_the_pr_ci_subset(), test_lines_is_a_picks_view(), test_the_behavioural_checks_pass(), test_the_board_reloads_when_the_et_date_changes(), test_the_lines_read_names_the_view_and_pages(), test_the_lines_segment_is_unconditional_and_after_live() (+1 more)

### Community 61 - "Discord and X results posters"
Cohesion: 0.02
Nodes (96): step_settle(), matchup(), _recap_row(), test_a_day_with_no_in_play_picks_says_nothing_about_it(), test_a_snapshot_with_no_clv_stores_null_not_zero(), test_an_in_play_pick_counts_toward_the_record(), test_clv_counts_only_picks_that_have_a_closing_price(), test_clv_ignores_in_play_picks_even_when_one_carries_a_value() (+88 more)

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

### Community 626 - "Baseball Savant capture date stamping"
Cohesion: 0.14
Nodes (5): test_rows_are_stamped_with_a_capture_date(), test_savant_has_a_schedule(), test_the_insert_persists_the_stamp(), test_the_savant_job_belongs_to_the_pipeline_service(), test_the_stamp_defaults_rather_than_being_required_at_call_sites()

### Community 629 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.47
Nodes (6): contentHeight(), evalExpr(), lineOf(), styleBlock(), styleProp(), visualHeight()

### Community 63 - "Football in-play game state"
Cohesion: 0.12
Nodes (17): _as_float(), _as_int(), _as_opt_float(), _as_opt_int(), from_espn(), from_extract(), from_pbp_row(), smooth_pass_rate() (+9 more)

### Community 630 - "NCAAF in-play odds history pull"
Cohesion: 0.24
Nodes (13): _blank_row(), _floor5(), _get(), _iso(), main(), planned_calls(), pull_day(), resolve_game_id() (+5 more)

### Community 631 - "NFL wind forecast validation"
Cohesion: 0.29
Nodes (10): build(), games(), hourly(), main(), _rate(), sec_coverage(), sec_error(), sec_rule() (+2 more)

### Community 632 - "NFL in-play prop dataset and calibration"
Cohesion: 0.09
Nodes (19): evaluate(), _infer_position(), main(), _pool_prior(), report(), _rows_for_market(), _to_states(), accrual_at() (+11 more)

### Community 634 - "MLB totals public fade card runner"
Cohesion: 0.18
Nodes (8): edge_floor(), max_per_slate(), publish_enabled(), rank_kind(), under_odds_band(), ranked_bets(), test_publish_defaults_off_and_xgboost_stays_paused(), test_publish_stays_off_and_xgboost_stays_paused_after_the_guard()

### Community 635 - "tests/test_demote_ncaaf_over_under_platt.py"
Cohesion: 0.32
Nodes (4): _stmts(), test_it_demotes_only_the_measured_promotion(), test_it_does_not_move_the_gate_the_floor_or_a_pause(), test_migration_is_one_statement()

### Community 636 - "NCAAF line move follow spots"
Cohesion: 0.29
Nodes (5): eval_follow_spread(), eval_follow_total(), load(), main(), _summ()

### Community 637 - "tests/test_discord_post_one_pick_migration.py"
Cohesion: 0.29
Nodes (3): _pairs(), test_it_names_each_measured_extra_and_the_row_kept(), test_the_update_does_not_rewrite_the_graded_outcome()

### Community 638 - "tests/test_game_scorer_spares_nfl_props.py"
Cohesion: 0.43
Nodes (5): _between(), _run_scorer_body(), test_an_nfl_game_never_enters_the_per_game_clear(), test_both_live_non_bet_clears_leave_nfl_rows(), test_the_left_out_ufc_clear_only_removes_unsettled_non_bets()

### Community 639 - "Injury athlete name caching"
Cohesion: 0.17
Nodes (5): _athlete_name(), test_a_failed_lookup_is_not_cached(), test_a_known_athlete_costs_no_request(), test_a_SUCCESSFUL_response_with_no_name_is_not_cached(), test_an_unknown_athlete_is_fetched_and_then_remembered()

### Community 64 - "NFL in-play score distribution pricing"
Cohesion: 0.07
Nodes (37): _model_price(), gaussian_copula_joint(), american_to_decimal(), american_to_prob(), anchor_to_market(), devig_power(), margin_pmf(), _over_under() (+29 more)

### Community 641 - "Mobile quiet update download tests"
Cohesion: 0.17
Nodes (8): _code_only(), _read(), test_a_downloaded_update_is_announced_quietly_once(), test_app_root_mounts_the_ota_updater(), test_every_trigger_only_downloads(), test_nothing_in_the_app_reloads_a_running_app(), test_the_pieces_exist(), test_the_updater_downloads_the_update()

### Community 642 - "NBA team total luck replay tests"
Cohesion: 0.18
Nodes (6): art(), ld(), results(), test_the_artifact_holds_the_lab_s_team_total_residuals_in_order(), test_the_live_code_reproduces_the_lab_game_for_game(), test_the_live_home_parts_are_the_independent_lab_copy_s()

### Community 643 - "MLB in-play game state features"
Cohesion: 0.11
Nodes (19): compute_live_target(), half_innings_left(), parse_bases(), state_features(), test_build_live_state_row_merges_pregame_context(), test_build_live_state_row_unusable_state(), test_half_innings_left_bottom_ninth(), test_half_innings_left_extras_clamps_to_one() (+11 more)

### Community 649 - "NFL in-play edge studies 2024-25"
Cohesion: 0.15
Nodes (15): h1_calibration(), h1_frame(), lagbook(), lagbook_catchup(), lagbook_groups(), summ(), async_check(), boot() (+7 more)

### Community 654 - "NFL prop shape simulation"
Cohesion: 0.20
Nodes (12): anchor_scale(), calibration(), grade(), latest(), load_odds(), main(), placebo_sf(), player_gamma() (+4 more)

### Community 656 - "Build your own model data loading"
Cohesion: 0.16
Nodes (12): parse_game_id(), _as_quotes(), build_season(), build_seasons(), _dk_quotes(), facts_for_season(), _ids_for(), _played() (+4 more)

### Community 659 - "Monitoring probe call recording"
Cohesion: 0.14
Nodes (14): _drain(), _enqueue(), instrumented(), _now(), _patch_curl_cffi(), instrumented(), record(), _with_params() (+6 more)

### Community 662 - "NFL wind stake past calibration tests"
Cohesion: 0.22
Nodes (6): _probe(), test_an_uncalibrated_lead_is_sized_rather_than_zeroed_on_the_card(), test_at_the_default_gate_that_same_row_does_not_fire_at_all(), test_the_eval_board_agrees_with_the_card(), test_the_probability_was_already_clipping(), test_the_stake_clips_to_lead_seven_instead_of_returning_zero()

### Community 663 - "NBA injury report player matching"
Cohesion: 0.20
Nodes (6): match_player(), _near_season(), remap_changes(), test_a_name_printed_differently_matches_on_surname_and_initial_within_the_team(), test_player_ids_match_on_team_first_then_a_unique_season_name(), test_remap_rewrites_only_names_whose_id_changed()

### Community 665 - "NCAAF scoreboard yardline parsing"
Cohesion: 0.21
Nodes (6): _abbrev_fits(), _parse_yardline(), _cfbd_game(), test_cfbd_state_carries_the_yardline_and_the_raw_situation(), test_cfbd_yardline_from_every_stored_situation(), test_cfbd_yardline_refuses_rather_than_guesses()

### Community 666 - "NFL prop kickoff lead ceiling tests"
Cohesion: 0.30
Nodes (8): _nfl_prop_too_early(), _iso(), test_a_kickoff_beyond_the_ceiling_is_too_early(), test_a_started_or_unknown_kickoff_is_not_too_early(), test_the_boundary_is_inclusive_at_the_ceiling(), test_the_scorer_and_the_card_read_ONE_constant(), test_the_scorer_loop_actually_applies_the_ceiling(), test_the_z_suffix_parses_like_the_offset_form()

### Community 667 - "NFL wind venue gate tests"
Cohesion: 0.14
Nodes (10): _covered_reads(), _slate(), test_a_locked_pick_with_no_venue_reads_degraded_never_gone(), test_a_placed_game_still_bets(), test_no_venue_no_bet(), test_stored_readings_cannot_carry_an_unplaced_game(), test_the_bernabeu_with_no_roof_state_is_held_back(), test_the_board_and_the_card_agree_on_a_placed_game() (+2 more)

### Community 671 - "NHL prop EV lab fixtures"
Cohesion: 0.14
Nodes (7): _load_fixture(), hist(), _league(), fake_load(), _loose_summary(), s(), _name()

### Community 677 - "Model quality CLV monitor"
Cohesion: 0.12
Nodes (12): record_exclusion_sql(), test_clv_clear_negative_vs_baseline_is_flagged(), test_raw_one_sided_clv_is_ignored(), test_the_exclusion_sql_is_a_conjunction_of_negations(), _job_model_quality(), detect_clv_degradation(), _group(), _result_row() (+4 more)

### Community 681 - "Slate concentration and fade risk"
Cohesion: 0.16
Nodes (12): _fade_slate(), test_a_mixed_slate_is_ok(), test_all_home_ncaaf_slate_is_flagged_without_mlb_hardcoding(), test_all_unders_public_fade_risk_is_crit(), test_all_unders_public_fade_slate_is_crit(), test_fade_in_the_model_id_is_sport_agnostic(), test_thin_slate_is_not_a_finding(), test_unanimous_but_small_slate_is_warn_not_crit() (+4 more)

### Community 683 - "Published record reconciliation checks"
Cohesion: 0.16
Nodes (8): test_a_pick_before_the_live_date_is_caught_in_either_view(), test_a_sport_missing_from_the_daily_view_is_caught(), test_an_empty_record_is_not_a_problem(), test_cent_level_agreement_is_required(), test_same_picks_but_different_money_is_caught(), test_the_fixed_production_numbers_reconcile(), test_the_real_production_drift_is_caught(), _published_record_problems()

### Community 689 - "Pruning keeps openers and closes"
Cohesion: 0.06
Nodes (19): _unprotected(), test_the_prune_protects_every_ladder_source_by_its_writer_s_own_name(), test_the_two_prune_tiers_never_select_a_path_kept_sport(), _prune(), _quotes(), test_both_delete_tiers_spare_the_keep_set(), test_the_close_is_never_an_in_play_price(), test_the_cost_is_recorded_as_a_measurement_not_a_guess() (+11 more)

### Community 690 - "UFC fighter name resolution"
Cohesion: 0.16
Nodes (11): resolve_slug(), _slug_tokens(), test_a_generational_suffix_resolves_either_way(), test_a_near_miss_is_not_a_match(), test_a_reversed_name_order_resolves(), test_a_shared_surname_alone_is_not_a_match(), test_an_ambiguous_token_set_resolves_to_nothing(), test_an_empty_or_tokenless_name_is_safe() (+3 more)

### Community 691 - "NFL opener cut sweep"
Cohesion: 0.23
Nodes (6): bettable_books(), boot_ci(), candidate_rows(), _load_backtest(), main(), select()

### Community 695 - "Every named sportsbook is fetched"
Cohesion: 0.18
Nodes (5): _param_books(), test_a_sharp_reference_is_never_also_a_soft_book(), test_every_bettable_book_can_be_named_to_a_human(), test_every_named_book_is_in_the_pull_that_serves_it(), test_the_nfl_backfill_defaults_to_the_live_pull()

### Community 697 - "NCAAF opener strategy experiments"
Cohesion: 0.20
Nodes (8): experiment_bands(), experiment_crossbook(), experiment_model(), _load_cross_book(), main(), _open_features(), _norm(), to_frame()

### Community 698 - "NFL prop backtest universe summary"
Cohesion: 0.29
Nodes (6): _universe_summary(), test_a_universe_without_the_model_sums_still_summarises(), test_mean_projection_and_mean_actual_separate_mean_bias_from_shape_bias(), test_model_over_rate_and_its_gap_are_reported(), _universe(), test_a_nonfinite_fair_price_cannot_switch_the_gate_off()

### Community 699 - "NBA team total feed patching"
Cohesion: 0.40
Nodes (3): fn(), logged(), call()

### Community 701 - "Failure alerts and job heartbeats"
Cohesion: 0.16
Nodes (7): _is_health_check_step(), _latest_health_rows(), _pass_is_clean(), _producer_failures(), _step_names(), failing_jobs(), should_notify()

### Community 704 - "ESPN NHL goalie designations"
Cohesion: 0.13
Nodes (10): fetch_espn_nhl_designations(), _short_name_teams(), _slot(), _team_abbrev(), test_dailyfaceoff_fails_open_with_one_warning(), blocked(), test_espn_fails_open(), boom() (+2 more)

### Community 714 - "Database grant revocation"
Cohesion: 0.14
Nodes (7): _strip_outer_tx(), test_it_asserts_the_app_write_surface_survives(), test_it_revokes_every_write_privilege(), test_select_is_never_revoked(), test_the_roles_are_named_never_public(), test_the_runners_transaction_stripping_leaves_the_do_block_intact(), test_the_set_is_computed_from_the_policy_rule_not_listed()

### Community 717 - "NFL venue resolution for weather"
Cohesion: 0.12
Nodes (10): resolve_venue(), _venue_key(), test_a_home_game_uses_its_stadium_id(), test_a_neutral_us_site_is_not_forecast(), test_a_row_without_venue_is_not_established(), test_an_unmapped_home_stadium_is_not_established(), test_every_2026_game_abroad_resolves_to_espns_venue(), test_names_are_matched_without_accents_or_case() (+2 more)

### Community 719 - "Mobile accessibility verify script"
Cohesion: 0.67
Nodes (3): read(), readUtf8(), verticalSlop()

### Community 72 - "Market handicap feature tests"
Cohesion: 0.05
Nodes (38): attach_market_handicap(), build_public_features(), empty_handicap(), favorite_side(), _pct_pair(), _rlm(), row_is_pregame(), select_latest_pregame_splits() (+30 more)

### Community 721 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.67
Nodes (3): closeOf(), openTag(), toggleUse()

### Community 74 - "Prop CLV and SQL escaping tests"
Cohesion: 0.09
Nodes (18): _fn(), test_a_backfill_failure_never_breaks_settlement(), test_a_pick_is_only_stamped_captured_once_a_measure_resolved(), test_a_pick_stamped_after_first_pitch_is_never_measured(), test_a_prop_pick_whose_label_has_no_name_is_skipped_not_guessed(), test_both_guards_agree(), test_clv_pct_never_compares_prices_across_a_moved_line(), test_every_prop_model_maps_to_a_dk_market() (+10 more)

### Community 75 - "Historical odds backfill and first pitch tests"
Cohesion: 0.02
Nodes (72): _ledger_entry_is_resumable(), relabel_in_play(), run_historical_odds_range(), main(), plan(), test_capture_compares_the_picks_own_clock_not_the_capture_clock(), test_capture_fails_open_on_a_missing_timestamp(), test_health_check_uses_the_same_first_pitch_bound_as_discord() (+64 more)

### Community 757 - "NBA injury report name normalising"
Cohesion: 0.33
Nodes (5): name_first_last(), _row(), team_code(), test_names_turn_round_with_their_suffix_on_the_surname(), test_team_names_map_to_our_codes()

### Community 76 - "ncaaf_live/tests/test_serve.py"
Cohesion: 0.07
Nodes (39): _clock_seconds(), extract_live_states_cfbd(), school(), _parse_situation(), _strip_mascot(), _cfbd_game(), _ctx(), _no_ev_floor() (+31 more)

### Community 790 - "NCAAF starter out study"
Cohesion: 0.27
Nodes (8): build_sample(), grade(), _line(), load_qb_log(), main(), report(), starter_status(), wilson()

### Community 80 - "Per-model EV floor card tests"
Cohesion: 0.10
Nodes (19): _built(), floor_030(), identity_maps(), _nfl_fixtures(), open_pregame_cut(), _pregame(), shrink_map(), test_a_floor_note_does_not_stop_the_best_price_recheck() (+11 more)

### Community 82 - "Mobile error states and books tests"
Cohesion: 0.11
Nodes (24): _load_state_dir(), _raw_error_lines(), _read(), _run_node(), test_aborts_are_silent_and_offline_slow_are_narrow(), test_aborts_render_nothing_and_every_catch_skips_them(), test_designer_review_fixes_behaviour(), test_error_state_component() (+16 more)

### Community 83 - "In-play trigger orchestrator and daily cap"
Cohesion: 0.04
Nodes (39): should_fetch(), split_triggers(), under_credit_cap(), apply_daily_cap(), classify_live_signal(), _ev_floor(), _consume_source(), _t() (+31 more)

### Community 849 - "Custom model player prop facts"
Cohesion: 0.18
Nodes (9): _as_quotes(), build_season(), build_seasons(), facts_for_season(), _fetch(), _games(), _log_for_game(), _quotes_for_game() (+1 more)

### Community 850 - "Live feed freshness probes and MLB stats"
Cohesion: 0.02
Nodes (84): _fetch_bat_hands(), _fetch_lineup(), backfill_bullpen_stats(), backfill_f5_scores(), backfill_mlb_stats(), backfill_pitcher_stats(), backfill_player_game_log(), backfill_player_handedness() (+76 more)

### Community 851 - "Steam lag line study"
Cohesion: 0.27
Nodes (9): attach_scores(), build_events(), fmt(), grade(), lines_at_pulls(), load(), main(), summarise() (+1 more)

### Community 853 - "No record-only mode guard tests"
Cohesion: 0.43
Nodes (4): _allowed(), _hits(), _rel(), test_the_repo_has_no_record_only_or_paper_tracking_mode()

### Community 856 - "MLB totals public fade ranking"
Cohesion: 0.12
Nodes (17): american_units(), bucket_win_rates(), build_candidates(), _fmt(), grade_under(), holdout_take(), load_db(), load_json() (+9 more)

### Community 86 - "NFL quarterback wind edge study"
Cohesion: 0.10
Nodes (43): band_table(), bh(), build_priced(), decisions_2026(), decisions_hist(), era5_hourly(), fc_at_decision(), fetch_2026() (+35 more)

### Community 860 - "MLB retrain freeze guard"
Cohesion: 0.12
Nodes (8): test_import_time_flag_follows_marker_file(), test_marker_or_env_lifts_the_freeze(), test_mlb_prop_market_sweep_is_documented_exempt(), test_mlb_retrain_refused_while_incomplete(), test_mlb_threshold_sweeps_call_the_guard(), test_non_mlb_sports_are_not_gated(), test_repo_marker_file_is_present(), test_trainer_calls_the_guard()

### Community 861 - "NBA schedule refresh with fallback host"
Cohesion: 0.18
Nodes (8): core_month(), _core(), fetch(), test_a_listing_of_more_than_one_page_fails_its_month(), test_a_month_the_fallback_host_breaks_on_is_failed_whole(), test_a_month_the_scoreboard_refuses_is_read_from_the_fallback_host(), test_each_team_is_fetched_once_a_run(), test_the_fallback_types_a_play_in_and_skips_a_slot_with_no_teams()

### Community 864 - "NHL goalie designation changes"
Cohesion: 0.17
Nodes (8): changes(), _latest(), run(), _stats_rows(), swaps_needed(), _unstarted_games(), _obs(), test_only_a_changed_name_or_status_is_stored()

### Community 865 - "NFL prop settlement name fallback"
Cohesion: 0.27
Nodes (10): _never(), _row(), test_a_first_name_the_stat_log_spells_differently_still_matches(), test_a_scratched_player_is_not_graded_on_a_teammate_with_his_initial(), test_a_spelling_the_log_already_knows_is_a_scratch_not_a_spelling(), test_another_game_and_another_initial_never_match(), test_first_name_rule(), test_two_candidates_is_a_miss_not_a_guess() (+2 more)

### Community 867 - "NBA public splits quality flag"
Cohesion: 0.29
Nodes (4): quality_backfill_statements(), quality_flag(), test_the_quality_rule_puts_reversed_ahead_of_late(), test_the_stored_row_backfill_flags_exactly_what_the_rule_flags()

### Community 868 - "NCAAF gameday loop cadence"
Cohesion: 0.15
Nodes (7): _main_source(), test_an_unanswered_state_feed_does_not_look_like_the_slate_ending(), test_loop_exits_early_when_no_kickoff_is_near(), test_loop_polls_at_the_idle_cadence_when_nothing_is_live(), test_loop_sleeps_the_remainder_not_a_flat_interval(), test_loop_warns_when_a_pass_overruns_its_interval(), test_odds_fetch_uses_the_odds_cadence_not_the_loop_cadence()

### Community 87 - "NHL box score ingest"
Cohesion: 0.12
Nodes (15): _decision(), _insert_absent(), _int(), _name(), parse_boxscore(), side_rows(), store_boxscore(), _write() (+7 more)

### Community 876 - "NBA play-by-play clock parsing"
Cohesion: 0.29
Nodes (4): classify_field_goal(), parse_clock(), test_field_goal_value(), test_parse_clock()

### Community 880 - "College football in-play history backtest"
Cohesion: 0.18
Nodes (6): build_candidates(), load_snapshots(), odds_from_rows(), state_index_at(), _ts(), test_odds_dict_has_the_shape_the_loop_reads()

### Community 883 - "NCAAF quarterback ablation study"
Cohesion: 0.28
Nodes (7): _fit(), main(), _report(), run(), summarise(), walk_forward(), wilson()

### Community 884 - "Mobile stat segment label tests"
Cohesion: 0.24
Nodes (9): _read(), test_one_shared_defensive_set(), test_position_is_never_inferred_from_stats(), test_runs_in_pr_ci(), test_search_and_position_review_fixes(), test_segment_labels_cap_only_on_fit(), test_tabs_speak_the_visible_label_not_the_key(), test_the_category_dropdown_is_gone() (+1 more)

### Community 885 - "Opening versus closing strategy analysis"
Cohesion: 0.43
Nodes (4): _fmt(), _profit_sql(), _row(), strategy_analysis()

### Community 888 - "Dashboard rule-based model display tests"
Cohesion: 0.14
Nodes (5): test_a_rule_carries_a_cut_but_is_in_no_training_registry(), test_a_rule_is_not_styled_as_a_warning(), test_a_rule_sorts_with_the_live_models_not_the_broken_ones(), test_the_roster_query_flags_rules(), test_the_summary_counts_rules_apart_from_outages()

### Community 89 - "mobile/scripts/verify_a11y.ts"
Cohesion: 0.03
Nodes (50): a11ySrc, allowHit, ALLOWLIST, app, badExempt, bar, bareClose, baselineLeft (+42 more)

### Community 897 - "NCAAF play-by-play column range scan"
Cohesion: 0.33
Nodes (3): _extremes(), observed_ranges(), test_the_scan_survives_nulls_and_non_numeric_cells()

### Community 901 - "Live slate midnight discovery"
Cohesion: 0.18
Nodes (7): _discover_active_games(), _game_id_from_statsapi(), test_a_game_seen_twice_is_polled_once(), test_discovery_asks_statsapi_about_every_date_it_is_given(), fake_schedule(), test_discovery_still_accepts_a_bare_string(), test_one_broken_date_does_not_lose_the_other()

### Community 902 - "NBA injury report page parser"
Cohesion: 0.18
Nodes (7): _bands(), _column_of(), _columns(), _hrules(), _lines_of(), parse_page_layout(), _text()

### Community 905 - "DailyFaceoff goalie designations parser"
Cohesion: 0.20
Nodes (7): fetch_dailyfaceoff(), normalize_status(), _observe_date(), parse_dailyfaceoff(), parse_dailyfaceoff_page(), test_a_page_with_no_data_blob_is_an_error_not_an_empty_slate(), test_dailyfaceoff_page_parses_to_our_teams_and_statuses()

### Community 906 - "Build your own model NFL docs"
Cohesion: 0.22
Nodes (8): log_status(), apply(), test_the_publish_key_backfill_is_registered_and_applies(), Backtest, Build Your Own Model — NFL facts, Prop facts, Refresh, Saved models

### Community 907 - "CFBD school name orientation"
Cohesion: 0.14
Nodes (8): _loose_orientation(), ncaaf_slug(), _slug_extends(), _slug_pair(), test_an_fcs_name_that_extends_an_fbs_school_passes_through_unresolved(), test_slug(), test_split_ratio(), test_with_the_visitor_in_the_registry_it_resolves_to_itself()

### Community 91 - "NFL in-play model backtest replay"
Cohesion: 0.05
Nodes (33): align_states(), build_team_map(), _game_index(), kill_verdict(), load_cached_snapshots(), main(), replay(), _settle() (+25 more)

### Community 912 - "NBA public betting splits ingest"
Cohesion: 0.13
Nodes (16): build_rows(), flip_side(), parse_v2_sides(), _entry(), test_a_late_tip_matches_its_et_dated_game_id(), test_a_swapped_listing_flips_team_sides_into_our_orientation(), test_an_unknown_team_is_reported_not_invented(), test_archive_rows_carry_no_observation_time() (+8 more)

### Community 914 - "Player news article conversion"
Cohesion: 0.23
Nodes (8): _article_url(), _to_item(), _article(), test_an_article_about_nobody_is_dropped(), test_an_article_becomes_an_item_with_its_players(), test_an_article_with_no_timestamp_is_dropped(), test_espn_carries_no_analysis_paragraph(), test_the_same_player_tagged_twice_appears_once()

### Community 917 - "Mobile stats filter UX verify script"
Cohesion: 0.17
Nodes (10): board, chip, lineOnlyFn, playersDay, ROOT, sportReset, stats, teams (+2 more)

### Community 918 - "ESPN injury feed fetch"
Cohesion: 0.40
Nodes (3): fetch_espn_injuries(), _fetch_espn_team_injuries(), test_nfl_active_rows_are_dropped_and_out_keeps_espn_date()

### Community 927 - "Game injury star gate"
Cohesion: 0.23
Nodes (7): _goalie_names(), _pitcher_names(), relevant_players(), _star_names(), stars_from_logs(), test_stars_from_logs_empty_when_no_history(), test_stars_from_logs_takes_top_two_not_the_bench()

### Community 93 - "MLB totals public fade tests"
Cohesion: 0.09
Nodes (36): find_fade_bets(), is_pre_commence(), select_latest_pre_commence_over(), under_in_odds_band(), pick_rows(), publish(), rows_for_insert(), _dk_board() (+28 more)

### Community 934 - "NCAAF venue travel and altitude features"
Cohesion: 0.11
Nodes (11): haversine_miles(), tz_offset_from_lon(), _venue_features(), trip(), test_altitude_climb_is_signed_from_each_teams_own_elevation(), test_both_teams_travel_at_a_neutral_site(), test_eastward_travel_is_positive_tz_shift(), test_haversine_matches_real_geography() (+3 more)

### Community 937 - "NFL prop sportsbook sweep"
Cohesion: 0.14
Nodes (12): _actuals(), _board(), p(), _line(), main(), _run(), soft_verdict(), test_a_bettable_book_still_passes() (+4 more)

### Community 94 - "NCAAF in-play score distribution pricing"
Cohesion: 0.02
Nodes (81): _seed_athlete_cache(), main(), rows_from_file(), source_for(), stadium_from_name(), stored_files(), _cluster_bootstrap(), evaluate() (+73 more)

### Community 942 - "One pick per event record counting"
Cohesion: 0.18
Nodes (7): duplicate_copy_exclusion_sql(), test_the_discord_recap_counts_each_event_once(), test_the_finder_skips_copies_already_marked(), test_the_marker_is_one_constant_and_one_predicate(), test_the_monitor_dashboard_box_score_arm_counts_each_event_once(), test_the_monitor_dashboard_picks_arm_counts_each_event_once(), test_the_predicate_keeps_rows_with_no_marker()

### Community 944 - "Monitoring server access control"
Cohesion: 0.20
Nodes (6): build_server(), serve_in_thread(), http_server(), live_server(), test_loopback_without_a_token_is_allowed(), test_refuses_a_public_bind_without_a_token()

### Community 947 - "In-play column map scoring guard"
Cohesion: 0.18
Nodes (3): _setup(), test_an_artifact_wanting_an_unmapped_column_is_never_scored(), test_the_same_fixture_does_reach_the_model_when_the_map_agrees()

### Community 950 - "Pipeline watch recap tracking"
Cohesion: 0.18
Nodes (4): test_a_stopped_recap_stays_in_the_watch_after_a_day(), _recap_ledger_rows(), _rows(), _step_regressions()

### Community 951 - "Odds snapshot pass ordering"
Cohesion: 0.25
Nodes (6): _between(), _code(), _pass(), test_a_second_pass_does_not_mix_posted_wins_with_all_bets_units(), test_published_rewrite_runs_once_and_uses_the_view_clv_rule(), test_recompute_rewrites_snapshots_only_while_the_old_column_exists()

### Community 956 - "NCAAF in-play history budget"
Cohesion: 0.22
Nodes (6): budget_for(), calls_in(), parse_shard(), shard_windows(), test_a_bad_shard_spec_is_refused(), test_shard_parsing_and_splitting_is_round_robin_and_total()

### Community 966 - "NCAAF prop odds markets"
Cohesion: 0.20
Nodes (5): _football_map(), test_the_half_credit_tackle_market_is_in_neither_list(), test_the_prune_is_per_league_and_the_nfl_keeps_both(), test_the_two_college_markets_no_book_prices_are_gone_from_both_lists(), test_what_we_pull_and_what_the_board_can_show_are_the_same_set()

### Community 969 - "MLB live bases state parsing"
Cohesion: 0.22
Nodes (7): _bases_state(), _extract_state(), test_bases_state_empty(), test_bases_state_loaded(), test_bases_state_single_runner(), test_extract_state_handles_empty_feed(), test_extract_state_pulls_fields_from_live_feed()

### Community 971 - "Player news name matching"
Cohesion: 0.22
Nodes (5): build_name_index(), test_a_sport_with_no_game_log_has_no_index(), test_an_accented_name_resolves_to_our_player_id(), test_an_unreadable_log_yields_an_empty_index_not_an_exception(), test_two_players_sharing_a_name_resolve_to_no_id()

### Community 972 - "ESPN player news ingestion"
Cohesion: 0.22
Nodes (5): _fetch_espn(), fetch_espn_news(), absorb(), test_a_dead_feed_is_a_quiet_zero(), test_a_sport_with_no_espn_path_is_skipped()

### Community 973 - "NCAAF in-play odds cadence and outages"
Cohesion: 0.22
Nodes (5): _feed_with_payload(), test_a_sustained_feed_outage_degrades_to_no_odds(), test_cached_odds_are_served_while_fresh(), test_credit_cap_reports_no_odds_rather_than_a_frozen_line(), test_credit_cap_still_serves_a_payload_that_is_still_fresh()

### Community 974 - "Parlay correlation estimates"
Cohesion: 0.36
Nodes (5): estimate(), estimate_basketball(), estimate_mlb(), main(), _median()

### Community 975 - "MLB prop market sweep"
Cohesion: 0.25
Nodes (5): actuals(), grade_day(), norm(), outs_from_ip(), profit()

### Community 977 - "Rich market handicap features"
Cohesion: 0.29
Nodes (4): build_rich_handicap(), _fav_signed_home_move(), _gated_flag(), _mul()

### Community 978 - "NBA shooting luck total gaps"
Cohesion: 0.28
Nodes (7): _game(), _gaps(), _luck_games(), _side(), test_a_teams_total_reads_only_the_luck_of_the_defence_it_scores_against(), test_the_first_half_total_reads_f4s_full_game_gap_unscaled(), test_the_team_total_gaps_add_up_to_f4s_total_gap_and_differ_by_its_margin_gap()

### Community 98 - "NBA play-by-play ingestor"
Cohesion: 0.04
Nodes (56): alias_map_rows(), _bool(), box_context(), box_finals(), build_game(), build_gap_game(), _date10(), derive_game() (+48 more)

### Community 981 - "NHL goalie lock race guards"
Cohesion: 0.22
Nodes (4): test_a_pass_that_starts_as_the_tick_takes_its_lock_still_wins(), release(), test_a_refresh_pass_waits_for_the_window_instead_of_skipping(), test_the_daily_run_waits_for_a_tick_in_progress()

### Community 983 - "Odds pruning keeps the close"
Cohesion: 0.29
Nodes (5): count_sql(), delete_sql(), doomed_sql(), _pk(), test_each_statement_reads_its_proposition_once_with_no_anti_join()

### Community 990 - "MLB game market steam overlay"
Cohesion: 0.25
Nodes (4): _run(), _apply_game_market_gate(), test_apply_game_market_gate_fail_open_without_conn(), test_scorer_live_default_downgrades_steamed_and_public_steam()

### Community 991 - "Betting bias rule scan"
Cohesion: 0.39
Nodes (5): bh_fdr(), binom_p(), eval_rule(), load(), main()

### Community 992 - "College football model calibration fitting"
Cohesion: 0.32
Nodes (4): _apply_calibration(), fit_predict(), fit_predict(), _split_internal()

### Community 995 - "Account deletion endpoint tests"
Cohesion: 0.39
Nodes (5): _body(), _code(), _deletes(), test_every_delete_is_the_caller_and_the_public_record_is_absent(), test_only_the_caller_and_only_a_fresh_session()

### Community 997 - "Units won settlement convention"
Cohesion: 0.29
Nodes (4): test_prob_only_picks_fall_back_to_the_settlement_price(), test_units_convention_matches_the_stated_rule(), _decimal_odds(), units_won()

### Community 998 - "ROI collapse detection"
Cohesion: 0.25
Nodes (5): test_roi_collapse_is_crit_when_hit_rate_dies(), test_roi_ignores_unpriced_profit_flat(), detect_roi_collapse(), _sample(), units_from_profit_flat()

### Community 1021 - "Website hosting config"
Cohesion: 0.29
Nodes (6): buildCommand, cleanUrls, headers, outputDirectory, $schema, trailingSlash

### Community 1044 - "Marketing site hosting readme"
Cohesion: 0.40
Nodes (4): DNS, Local preview, Signal Base marketing site, Vercel

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

### Community 623 - "App terms and conditions"
Cohesion: 0.10
Nodes (20): 10. Intellectual property, 11. Third-party services, 12. Termination, 13. Disclaimers, 14. Limitation of liability, 15. Indemnity, 16. Changes to these Terms, 17. Governing law and disputes (+12 more)

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
Cohesion: 0.05
Nodes (38): 10.1 Three free checks (2026-10-21; prices only, no game score read except where named), 10.2 The hypothesis, 10.3 Data (all into Supabase first), 10.4 Rules every cell is graded under, 10.5 The cells (30), 10.6 The bars, 10.7 Two changes after two checks, before any rung was graded (2026-10-21), 10. Sixth search: alternate lines (pre-registered 2026-10-21, before any alternate price was graded) (+30 more)

### Community 941 - "Signal Base privacy policy"
Cohesion: 0.17
Nodes (11): 10. Contact, 1. Information we collect, 2. How we use information, 3. How we share information, 4. Retention, 5. Your choices and rights, 6. Security, 7. Age requirement (+3 more)

### Community 961 - "NHL expected goals aggregates migration"
Cohesion: 0.43
Nodes (7): idx_nhl_goalie_game_xg_goalie_date, idx_nhl_goalie_game_xg_source, idx_nhl_goalie_game_xg_team_date, idx_nhl_team_game_xg_source, idx_nhl_team_game_xg_team_date, public.nhl_goalie_game_xg, public.nhl_team_game_xg

### Community 962 - "Saved custom models migration"
Cohesion: 0.36
Nodes (4): idx_byom_model_snapshots_model, idx_byom_models_user, public.byom_model_snapshots, public.byom_models

### Community 964 - "Mobile build and run scripts"
Cohesion: 0.25
Nodes (8): scripts, android, build:ios:preview, build:ios:production, ios, start, typecheck, web

### Community 979 - "Mobile app development dependencies"
Cohesion: 0.29
Nodes (7): devDependencies, @babel/core, babel-plugin-module-resolver, babel-preset-expo, tsx, @types/react, typescript

### Community 984 - "NBA in-game market search plan"
Cohesion: 0.25
Nodes (8): 7.1 Data rules, 7.2 Families (54 cells), 7.3 Gates and bars, 7.4 Purchases, only if a free test shows information, 7. Third search: in-game spread, moneyline and total (pre-registered 2026-10-17, before any grid), IG-1: how the lab reads the row above (2026-10-17, written before any IG-1 number), IG-1: the grid (2026-10-17) — closed for 2026-27, IG-1: the information test (2026-10-17)

### Community 986 - "NBA lineup segments documentation"
Cohesion: 0.25
Nodes (7): Commands, How a stretch is built (each rule is pinned by a test that was watched to fail), NBA play-by-play and on-court lineup segments, Source, Tables (all worker-only, locked down where they are created), Things a reader should know, What was loaded, and the checks (re-measured 2026-10-17 on production, after the rebuild)

### Community 994 - "NHL shot events migration"
Cohesion: 0.83
Nodes (3): idx_nhl_shot_events_season_date, idx_nhl_shot_events_source, public.nhl_shot_events

### Community 1010 - "Player news sheet docs"
Cohesion: 0.43
Nodes (5): PlayerNewsButton / PlayerNewsSheet / usePlayerNews / fetchPlayerNews, Name-key matching attached prices to both namesakes, player_news table: player_id plus player_key, Recent News sheet on prop player screens, Player news: Recent News sheet

### Community 151 - "docs/rules_evidence.md"
Cohesion: 0.07
Nodes (13): 'Decisions needed from you' is second person, never first, A model in config.MODELS with no FEATURE_MAP entry kills scoring for every sport, Every front-end change is reviewed by the UX designer agent before its PR opens, Gate the number that gets bet (cal_error_actionable), A health check must not gate on the thing that breaks, The settled live-prop record is zero bets, The Odds API returns x-requests-remaining on every response, including 401, How the pick rule was found: the NCAAF live loop delete-and-replaced every 45s (+5 more)

### Community 192 - "NFL game lines model write-up"
Cohesion: 0.12
Nodes (15): DataRegistry: source catalog with priority levels, Game totals model (consumes spread output as competitiveness), IngestOrchestrator: per-source fetch with no silent fallbacks, Middling does not clear vig, Moneyline derived from spread via fitted sigmoid, Opener: sharp-vs-soft deviation (bet Pinnacle's side at the soft book), Oracle ceiling: perfect closing-line knowledge, Power-method (Shin) de-vig (+7 more)

### Community 209 - "Market-relative prop rule evidence"
Cohesion: 0.09
Nodes (12): MLB prop market-relative rule (not wired), Live inning gate replay, ncaaf_live_total 2025 in-play backtest, ncaaf_live_win_prob 2025 in-play backtest, Cross-book opener signal (DK vs Bovada), prune_odds keeps the earliest snapshot per proposition, Late-game leader moneyline at DraftKings, Monotonicity bound on unequal lines (+4 more)

### Community 213 - "nfl/live_model/README.md"
Cohesion: 0.10
Nodes (19): Gate 1: win probability Brier 0.115 PASS vs 0.20, backtest/calibrate.py (the two gates), backtest/calibrate_props.py projection prop gate, check_feed_assumptions: automatic first-payload feed check, backtest/flow_eval.py flow test with control, Gate 1: win probability Brier 0.1654 PASS vs 0.20, Gate 2: total quantile coverage 1.26pp PASS vs 2.0pp, backtest/harness.py kill_verdict (+11 more)

### Community 227 - "docs: followups + clv"
Cohesion: 0.08
Nodes (26): Pruner keeps the opener AND the close per (proposition, book), clv_method = standard_v2 (PEDIGREE_CLV_METHODS), clv_standard_v2_2026_10_14.sql bulk rewrite, Secondary — market edge vs Pinnacle's fair close (market_clv_*), Power de-vig (bisection, 80 steps, k in [0.05, 12]), Primary CLV — same-book raw price (clv_pct, clv_pp, clv_beat_close), Same line, and the close bound, Which price is the bet — _bet_price_and_book and clv_bet_book (+18 more)

### Community 246 - "docs: best_line + config_topology"
Cohesion: 0.10
Nodes (21): Book roles: fetched (LINE_SHOP_BOOKMAKERS) vs offered (BEST_LINE_BOOKMAKERS), DECIDE_ON_BEST_PRICE=0 restores DraftKings as the deciding price, Stage 2: decide, size and settle at the best price (picks.decision_*), _get_event_odds fetched DraftKings-only (MLB F5, UFC round totals), The live models join best-price deciding (2026-09-10), PREGAME_PRICE_MAX_AGE_MIN (180 min) on game-market reads, Scoring off another book's line (picks.line_book), BEST_LINE_EXCLUDE_BOOKMAKERS — unbettable books out of shopping (+13 more)

### Community 253 - "docs/history: learnings + build_state"
Cohesion: 0.09
Nodes (25): Data sources table (Odds API, SBR, MLB Stats API, Savant, Open-Meteo, NHL API, nba_api, ESPN, UFC CSV mirror, DataGolf), FanGraphs / pybaseball removed (IP-blocked); replaced by MLB Stats API + Savant, MLB_Basic.csv datawarehouse (2009-2025, 40,996 games; runline derived as -1.5), What's built (package tree) and what's not, AlphaPy rejected (deprecated, team-level only, defunct connectors), Team stats need at least 10 games before they stabilize, The go-live gate prevents going live on lucky backtests, Historical team-stat backfill uses {season}-01-01 as as_of_date (+17 more)

### Community 258 - "NCAAF in-play model notes"
Cohesion: 0.15
Nodes (14): CFBD_MONTHLY_CALL_ALLOWANCE (Tier 4, 125k), Worker cannot reach site.api.espn.com (403); CFBD /scoreboard is the state source, ncaaf_live.gameday loop, Gate 2: total shape 2.60pp FAIL vs 2.0pp, Market licenses from the calibration gates, LIVE_ODDS_MAX_AGE_SEC (180s) odds age bound, ncaaf_live_loop scheduler job (*/10 supervisor), NCAAF live model (port of nfl/live_model) (+6 more)

### Community 264 - "monitoring/static/dashboard.html"
Cohesion: 0.16
Nodes (26): Signalbase pipeline monitor dashboard page, dashboard.html ageNote(), dashboard.html callRow(), dashboard.html connect(), dashboard.html drawSeries(), dashboard.html drawTimeline(), dashboard.html flush(), dashboard.html ingestCalls() (+18 more)

### Community 292 - "docs/sports/nhl.md"
Cohesion: 0.12
Nodes (22): NHL models code-complete, not yet trained (2026-06-13 snapshot), docs/nhl_clv_ev_assessment.md: the current CLV/EV grade of every NHL model, Per-game logs from the NHL stats API (team, goalie, skater) via data/ingestors/nhl_game_logs.py, Starting-goalie confirm via ESPN core probableStartingGoalie; game-model veto on Out/Doubtful, docs/nhl_market_research.md: six defects and the honest walk-forward, data/nhl_asof.py: one function rates goalies and teams as-of, strictly before the date, nhl_over_under is live as a rule: Pinnacle de-vigged vs the bettable books in the same fetch, NHL pipeline steps (results before settle, odds, stats, totals card, scoring, settlement) (+14 more)

### Community 309 - "NFL game lines model documentation"
Cohesion: 0.12
Nodes (24): Forecast validation (2026-08-15): rule holds at 57.09% under real day-3 error, The Odds API historical backfill (bet-time Tuesday 18:00 UTC; closing 10 min before kickoff clusters), Critical data defect: home/away sign flips in four books, Under rate falls ~0.41pp per day of forecast lead, The canonical write-up nfl_game_lines_model_system.md, data/odds_cache/ (~45,000 credits of snapshots), Open-Meteo (ERA5, issued forecasts, live forecasts) via data_ingest/weather.py, wind_speed_10m_previous_dayN is null before 2024-01-18 (+16 more)

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

### Community 432 - "Monitoring and model research docs"
Cohesion: 0.07
Nodes (28): Hybrid Pin-agreement filter on mlb_over_under bets, mlb_spread_market 1.8pp run-line rule, mlb_runline and mlb_over_under (paused), mlb_total_public_fade card (paper UNDER), Slate concentration guard (insert-time), F5 odds coverage (DK carries F5 ML only), clv_degradation check, model_quality_checks table (+20 more)

### Community 441 - "docs/sports: ufc + golf"
Cohesion: 0.17
Nodes (12): DataGolf Scratch Plus as the sole golf source (not The Odds API), Five golf models (outright, top10, top20, make_cut, matchup), One games row per tournament, per-player picks FK to it (the MLB-prop pattern), Golf settlement: ties settle at full price as a win (v1), WD-before-cut NO_ACTION, ufc_moneyline CalErr 5.99% above the 5% gate; a retrain will not move it, Primary UFC data path is the Greco1899 CSV mirror (ufcstats behind Cloudflare), UFC: moneyline, total_rounds, method_of_victory (3-class, prob-only), Fighter name matching via slugify_fighter and config.UFC_NAME_ALIASES (+4 more)

### Community 444 - "mobile/docs/BILLING.md"
Cohesion: 0.18
Nodes (10): BILLING_ENABLED kill switch, IAP entitlement flow (configure -> purchase -> webhook -> subscriptions), has_app_access() supersedes has_active_subscription(), isEntitled() checks status AND period end, PaywallScreen (localized prices, restore, redeem), RevenueCat SDK and entitlement 'signals', scripts/verify_billing.ts (83 assertions), has_app_access() server-side check (+2 more)

### Community 451 - "NFL model environment and restore"
Cohesion: 0.40
Nodes (3): nfl/requirements.txt dependency set (pandas, numpy, pyarrow, requests, scipy, scikit-learn, lightgbm), Multi-layered leakage detection, Restore pip set: lightgbm scikit-learn pyarrow requests pandas numpy scipy

### Community 453 - ".claude/agents: frontend-ux-designer + CLAUDE"
Cohesion: 0.20
Nodes (8): ux_scan.mts — the deterministic front-end scan, frontend-ux-designer agent, Mobbin MCP connector — the only reference route, Signalbase — the iOS app in mobile/, /ux-review command, Matt — product area leader, /graphify trigger — use the installed graphify skill, CLAUDE.md — Betting Model Project Context

### Community 454 - ".claude/rules/picks-and-publishing.md"
Cohesion: 0.24
Nodes (4): The pytest non-integration subset, The lock flags: LOCK_GAME_PICKS_AT_FIRST_RUN, LOCK_PROP_PICKS_AT_FIRST_SIGNAL, LOCK_LIVE_PICKS_AT_FIRST_SIGNAL, tests/test_context_budget.py polices CLAUDE.md size, picks-and-publishing.md — path-scoped rule file

### Community 456 - "NFL in-play prop assessments docs"
Cohesion: 0.11
Nodes (11): Halftime second-half lines, out of sample at real prices, The live prop market leans over like the pre-game one, Publish backstop refuses pass-attempt overs, Pace ratio, In-play rushing-attempt UNDER on pace ratio >= 1.25, NFL prop lines lean over, NFL edge search 2026-10-11, docs/nfl_live_prop_assessment.md (+3 more)

### Community 459 - "docs/signal_timing.md"
Cohesion: 0.18
Nodes (8): Does the daily pick lock cost us signals? (2026-08-23), MAX_EDGE_CAP blind spot: games with no row at all, A model re-run harness over stored snapshots (open item), Four NONE-row coverage traps, Prop NONE/AVOID rows are a survivor sample (poller clear), The pre-game line poller wipes a game's non-BET prop picks (known issue), The lock is signal-aware for NCAAF only (NONE rows refreshed, BETs lock at first cross), Signal-timing analysis — the pick lock (signal_timing.md)

### Community 461 - "mobile/docs/DISCORD_LINKING.md"
Cohesion: 0.23
Nodes (11): Migration add_discord_link_and_whop_memberships.sql, DISCORD_LINK_ENABLED flag, discord_links table, Connect Discord flow (start -> consent -> complete -> role sync), public.my_access() computes access on every read, useAccess access state hook, scripts/verify_discord_link.ts (44 assertions), whop_memberships table (+3 more)

### Community 463 - "Probability calibration design notes"
Cohesion: 0.19
Nodes (17): models/honest_ev.gate and honest_probability, tracking/system_health._report_model_calibration, Calibration tracks sample size, not market quality, Response families: NB, Poisson, ZI-Gamma, logistic, MODEL_OWN_EV_FLOOR and MODELS_ON_OWN_PROBABILITY for wind and opener, fetch_graded reads picks for NFL/NCAAF/UFC/rule models, GLOBAL_MIN_EV: 0.30 then 0.20, The go-live calibration gate never computed a real number (+9 more)

### Community 479 - "docs/live_betting.md"
Cohesion: 0.18
Nodes (13): The live calibration map: 126 of 150, and it does not close, BookMoveClock — the book has moved past a cap while our state has not changed, LOCK_LIVE_PICKS_AT_FIRST_SIGNAL — the first live BET per lane is the bet of record, The live staleness guards (data/live_quote_guard.py), Live cutoffs are re-derived every pass (tracking/live_calibration.py), LIVE_MAX_BETS_PER_WEEK is advisory, not a runtime cap, config.LIVE_MODELS — a separate registry from MODELS, live_pick_features — one row per lane, the first one, under its own SAVEPOINT (+5 more)

### Community 490 - "College football model search findings"
Cohesion: 0.07
Nodes (13): scripts/ncaaf_search/, mlb_live_total_runs (in-play total), Negative-binomial (NB1) tail, pregame_total_line feature (market anchor), Honest MLB signal is ~0.55-0.56 AUC, CollegeFootballData (CFBD) as primary source, ncaaf_spread / ncaaf_over_under / ncaaf_moneyline, Hourly-band curve inside 24h (2026) (+5 more)

### Community 500 - "docs/sports/wnba.md"
Cohesion: 0.21
Nodes (13): Double-double is logistic, over-only, prob-only (COMPUTE_DD sentinel), NBA: 10 models live (moneyline + 9 props), O/U and spread blocked, NBA pipeline steps (odds, prop odds, stats local, scoring, settlement), stats.nba.com blocks datacenter IPs; team stats run on the local Task Scheduler job, WNBA results from the ESPN hidden API with core-API fallback, The wnba_over_under / wnba_spread sweep was leaked (latest snapshot had no pre-tipoff cutoff), WNBA models (moneyline + assists live; points/rebounds/threes/PRA/O/U/spread paused), WNBA pipeline responsibilities (odds, props, scoring, ESPN results, local game log and stats) (+5 more)

### Community 507 - "Odds sources and prop research"
Cohesion: 0.16
Nodes (18): scripts/nfl_prop_ladder_grade, scripts/verify_kalshi, Alternate coverage effectively begins in 2024, Anchored ladder graded: fails every clause, Provider comparison: Odds API, Kalshi, SportsGameOdds, OddsJam, Unabated, OpticOdds, 1.48M alternate-market rows already stored and unread, Kalshi (CFTC-regulated event contracts), Status: deferred, no code (as of the memo) (+10 more)

### Community 523 - "mobile/docs/AUTHENTICATION.md"
Cohesion: 0.24
Nodes (12): App Store guideline 4.8: Google on iOS requires Apple, AUTH_ENABLED kill switch, signalbase://auth-callback redirect URL, billingReady() requires AUTH_ENABLED, discordLinkReady() requires AUTH_ENABLED, RLS pre-flight: authenticated keeps full read access, SignInScreen (SignIn route), useAuth session store (+4 more)

### Community 558 - "Model artifact and health check docs"
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

### Community 624 - "NFL wind totals runbook"
Cohesion: 0.14
Nodes (15): DOCUMENT STATUS block: superseded claims indexed, scripts/edge_hunt.py: moneyline calibration clean, ML-vs-spread gap dead, Under rate by forecast lead 1-7 (~0.41pp per day), Original staking: 25% Kelly capped at 3% (superseded), Kelly-proportional units with slate shading 1/sqrt(1+(k-1)rho), Live candidate: precip > 0.2mm AND wind < 11 -> under, Rejected candidates (backup QB lookahead artifact, home dogs, cold unders reversed, refs, rest...), Stops: 2 units per bet, 3 units per slate, review at -15 units (+7 more)

### Community 627 - "docs/market_coverage.md"
Cohesion: 0.36
Nodes (7): ncaaf_prop_odds_ingestor and its probe, test_the_mlb_board_and_the_mlb_pull_are_one_set, MLB probe 2026-09-05 — served, unsupported and unpriced keys, NCAAF prune — FOOTBALL_MARKET_NOT_PRICED per league, scripts/probe_market_coverage.py — one market per call, writes nothing, Neither prop ingestor writes to api_call_log, Prop market coverage — what the feed actually serves

### Community 645 - "NFL prop method research docs"
Cohesion: 0.15
Nodes (15): The eleven NFL distributional prop models, The information test: does the projection add to the line?, ESPN core injuries endpoint for NFL, NFL prop Out/Doubtful veto, DraftKings' alternate ladder over-prices every over, Market-anchored shape simulation, The eleven distributional models at their live cuts, docs/nfl_prop_method_search.md (+7 more)

### Community 652 - "(root): pr-ci + requirements"
Cohesion: 0.33
Nodes (5): Mobile thresholds drift check (generate_mobile_thresholds --check), NFL preflight --ci, PR CI workflow — non-integration pytest subset, Render blueprint — betting-scheduler background worker, requirements.txt — >= pins for Python 3.14 wheels

### Community 66 - "NFL props sources and prediction market research"
Cohesion: 0.08
Nodes (30): scripts/nfl_prop_market_card, scripts/nfl_prop_replay, data/ingestors/kalshi_prop_ingestor.py (SERIES_MARKET, record_ladders), DraftKings de-vigged price sits above realised over-rate, tackles_assists +21% is a measurement error (control), Walk-forward re-fit 2023-2025 (-4.32% over 1,554 bets), Traps specific to props, Anytime TD field de-vig: closed (+22 more)

### Community 710 - "mobile/docs/BILLING.md"
Cohesion: 1.00
Nodes (4): useEntitlement() access gate (subscription OR Discord), useSubscription() subscription-only state, useEntitlement(), not useSubscription(), Access is one gate: useEntitlement(), never useSubscription().entitled

### Community 720 - "docs/testing.md"
Cohesion: 0.67
Nodes (3): PR CI runs a non-integration pytest subset, Pure function tests, in-memory SQLite via conftest, Test suite (testing.md)

### Community 81 - "docs: nhl_market_lab + nhl_clv_ev_assessment"
Cohesion: 0.08
Nodes (38): nhl_research worker job, scripts/nhl_derivative_totals_backtest, data/ingestors/nhl_derivative_odds_history, models/nhl_props.py (Spec per market), Anytime goalscorer: not a candidate once names corrected, nhl_moneyline and nhl_moneyline_regulation: no cut clears, Game models: lock later? Refuted, The overnight pass takes the night's slots (+30 more)

### Community 890 - "docs/game_injury_gate.md"
Cohesion: 0.40
Nodes (5): ESPN core probables for the NHL starting goalie, A NONE from this gate is not locked — the reprice path, The gate rule — refuse a game-model BET on a confirmed Out starter/star/goalie, Fires in scorer.score_game and _score_nhl_3way, after best-price requalify, before insert, Game-model starter / star / goalie gate

### Community 996 - "Signal flip push notifications"
Cohesion: 0.23
Nodes (12): mobile usePushNotifications / NotificationsCard / pushDiagnosis, On-device storage: bankroll and placed-bet flags in AsyncStorage, Claim: the app cannot write to the backend, Signalbase privacy policy: nothing personal collected, APNs key / aps-environment entitlement is the blocker, device_push_tokens table (anon INSERT/UPDATE, no SELECT), No push has ever reached a phone (2026-09-12), push_sent ledger means considered, not delivered (+4 more)

## Ambiguous Edges - Review These
- `Claim: the app cannot write to the backend` → `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`  [AMBIGUOUS]
  docs/privacy.html · relation: conceptually_related_to

## Knowledge Gaps
- **105 isolated node(s):** `RFC-4122`, `@babel/core`, `babel-plugin-module-resolver`, `babel-preset-expo`, `expo-asset` (+100 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 13224 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **259 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Table` connect `NBA public splits pipeline step` to `Line state and alias migration tests`, `Mobile color contrast checker`?**
  _High betweenness centrality (0.147) - this node is a cross-community bridge._
- **What connects `RFC-4122`, `@babel/core`, `babel-plugin-module-resolver` to the rest of the system?**
  _105 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Mobile app shell and feedback` be split into smaller, more focused modules?**
  _Cohesion score 0.016464407281337873 - nodes in this community are weakly interconnected._
- **Why does `over()` connect `Mobile color contrast checker` to `Mobile bankroll tracker`, `NBA public splits pipeline step`?**
  _High betweenness centrality (0.130) - this node is a cross-community bridge._
- **Should `Mobile picks home filters and sorting` be split into smaller, more focused modules?**
  _Cohesion score 0.022967101179391682 - nodes in this community are weakly interconnected._
- **Why does `inserted_minus_start_min()` connect `NBA public splits pipeline step` to `NBA public betting splits ingest`, `NBA ingestor shared imports`?**
  _High betweenness centrality (0.083) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Claim: the app cannot write to the backend` and `device_push_tokens table (anon INSERT/UPDATE, no SELECT)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._