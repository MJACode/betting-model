# UFC — models, data, pipeline

> Moved out of CLAUDE.md on 2026-08-30. Session-by-session history:
> `docs/sessions/`. The model search of 2026-11-13 and every number below:
> **`docs/ufc_market_audit.md`**.

## 20. UFC

### Models

mike, 2026-11-13: *"Use the model building skill to build models for UFC.
Ignore and delete any existing models in the repo."*

| Model | Market | What it does | Status |
|---|---|---|---|
| `ufc_open_moneyline` | fight winner | A fight a week or more out, on the noon-UTC run: fighter ratings move Pinnacle's no-vig price, and the best price at a book a pick may name is bet when its EV is 0.06 or more (-300 floor). The first pull that clears locks the fight. `models/ufc_open_moneyline.py`, `scripts/ufc_open_moneyline_card.py`, artifact `models/saved/ufc_open_moneyline.json` (built by `scripts/ufc_open_moneyline_build.py`) | **live on merge** (2026-11-13). Backtest 846 bets +12.85% [+8.0, +17.5], every year 2020-2026 positive, +2.2% against Pinnacle's close (`docs/ufc_market_audit.md` §3d) |

It holds a fight while either fighter has an earlier fight not yet logged,
and skips a fighter it cannot place on his ufcstats record (debutants, until
their first fight is logged). The card keys its decisions on the fight, not
the stored id, because the feed stores each fight under two ids. It skips the
feed's placeholder dates (December 31 and January 1). A bet on a fight that
is cancelled or moved settles NO_ACTION once its card is in the fight log
without either fighter (`tracking/paper_tracker._settle_unfought_ufc_picks`).

The three models of 2026-06-11 (`ufc_moneyline`, `ufc_total_rounds`,
`ufc_method_of_victory`) are in `config.RETIRED_MODELS`; their feature
engine, scorer and trainer branches and artifacts are gone. They had been
graded on probability alone at a synthetic -110, because no UFC price
history was ever stored, and method of victory was never given a market
price.
Their picks stay in `picks`, graded.

The grid below says where every other market stands.

### The market grid

| Market | Settles on | Inputs held | Prices | Baseline | Method tried | Result | Status |
|---|---|---|---|---|---|---|---|
| Fight winner | `games.home_win` (draw / no contest = push) | `ufc_fight_log` 2010-2026, `fighters`; ratings built strictly before each fight | Free archive: BestFightOdds open + closing range 2010-2026 (`ufc_price_archive`); feed history 2020-06+ (not bought); `odds` 2026-06+ every pull, 12 books | Blind favourite -0.8% to -3.9%, underdog -2.3% to -8.3% across the closing range, 7,541 fights | Market-anchored rating model at the close; at the first posted price; at each US book's first stored price; Pinnacle-anchored with US line shopping; five-round fights | At the close: nothing holds. At BestFightOdds' open: 1,531 bets +7.8% [+3.9, +11.8], positive against the close every year since 2018. At DraftKings' own first price, 2026: negative against Pinnacle's close (-2.1% to -2.5%); on the bought 2020-2026 history at the deciding books, Pinnacle-anchored: 846 bets +12.85%, 7/7 years | **Live**: `ufc_open_moneyline`, Pinnacle-anchored at a week out (audit §3d) |
| Total rounds (0.5-4.5) | rounds completed from `ufc_fight_log` end round and time; five-round fights from `scheduled_rounds` | same | `ufc_odds_history` (bought): Pinnacle 2020+ (2,421 fights, 2,384 at 1.5/2.5/4.5), DraftKings late 2023+ (1,072, 1,058 at those lines); `odds` 2026-06+; no free archive | Last pull: 2.5 over +0.1% at Pinnacle, -0.9% at DraftKings; 2.5 under -9.6% and -16.1%; 4.5 over +11.0% (127) and +8.5% (53). DraftKings' margin 6.2% against Pinnacle's 4.1% | Pinnacle-anchored finish model, walk-forward; four mechanisms of our own; the stuck ladder | Fighter inputs add nothing to Pinnacle's total (placebo equal); return falls as the cut rises; the card-day over (+6.9% on 228, interval below zero, 2025 negative) fails the bar and sits in the frontier | **Nothing clears** (audit §4) |
| Points spread | not known: DraftKings and Bovada list one (Holland +7.5) | | feed, live, 2 books | | | | **Parked**: what it settles on is unknown |
| Alternate round totals | as total rounds | | Pinnacle only on the feed | | | | **Parked**: no book a pick may name |
| Method of victory (by fighter) | `ufc_fight_log.method`; a DQ or could-not-continue end voided (graded as a TKO: -15.7% to -15.0%) | same | `ufc_prop_history` (BestFightOdds, stored 2026-11-14): last recorded price at DraftKings, FanDuel, BetMGM, Caesars, BetRivers, 2021-06 to 2026-11; DraftKings' own board live (audit §5a) | Best of five, 2021-2026: decision -2.1% (5,412), favourite by decision +2.4% [-2.1, +7.1], KO/TKO -15.7%, submission -19.3% | Three mechanisms (a book straying from the others, the anchored model, coherence with the fight winner), walk-forward by year | Decision anchored +9.7% on 1,112 but fails early/late and is a peak; KO/TKO and submission nothing | **Nothing clears** (audit §5f) |
| Goes the distance | `ufc_fight_log.method` = decision (a draw is a decision) | same | `ufc_prop_history`, as above | Best of five: yes +0.9% (2,712), no -9.2% | Same three | Anchored +10.0% on 791 at the last recorded price; **at the price an hour before: +6.8% on 745 [-0.9, +14.4], 2026 -3.6%**, the cut neighbourhood a hump; DraftKings alone -7.7% | **Nothing clears; lead on the frontier**, graded forward at FanDuel and Caesars (audit §5f) |
| Round betting, exact round, fight ends in round N | `ufc_fight_log` end round and method | same | `ufc_prop_history`, as above | Fighter wins in round N -19.7% (17,209); fight ends in round N -13.9% (8,506); by method in round N -22.6% (34,063) | Same three (no full set to de-vig for method in round N) | Nothing positive with an interval off zero | **Nothing clears** (audit §5f) |
| Inside the distance (by fighter) | KO/TKO or submission | same | `ufc_prop_history`: DraftKings and BetRivers only | Yes -14.1% (3,540), no -2.3% (3,524) | Same three | Anchored -2.9% (528) | **Nothing clears** (audit §5f) |
| In play | | | none stored | | | | **Parked** |
| Prediction markets | | | not checked for UFC | | | | **To do** |

### Conventions (load-bearing — don't break)

- **home/away mapping:** The Odds API's `home_team` fighter → our `home_team`. `games.home_team/away_team` store **display names**; `game_id = UFC_{date}_{away_slug}_{home_slug}` (slug = lowercase, accents stripped, hyphenated). Historical backfill rows (no pre-fight odds row) assign home = lexicographically smaller slug — **never winner-first** (label leakage).
- **Name matching:** Odds API names → `slugify_fighter()` → ufcstats fighters. Mismatches (nicknames, "Jr.", transliteration) go in `config.UFC_NAME_ALIASES` (Odds API name → ufcstats name). The results scraper matches games by slug pair ±1 day.
- **Scores convention:** `games.home_score/away_score` for UFC are 1/0 win indicators (0.5/0.5 + `home_win NULL` for draw/NC). The generic settle path therefore **excludes `ufc_%`** — `_settle_ufc_picks` in paper_tracker handles fight winner (draw/NC = PUSH), round totals (fractional rounds completed: O2.5 = fight passes 2:30 of R3), and method (DQ/overturned = NO_ACTION).
- **The feed carries every promotion** under one key. Our ingest keeps a fight only when one fighter is known to the UFC fight log, and stores a fight once DraftKings lists it, so every book's first stored row is DraftKings' (2026-11-13, all 345 stored fights).

### Pipeline

| Step | Runs where | Frequency | What it does |
|---|---|---|---|
| UFC odds (h2h bulk + per-event round totals) | the worker (`step_odds`) | 6am + every refresh pass | Every book's fight-winner lines; round totals per event (non-fatal when absent) |
| UFC results (`ufc-results`) | daily pipeline (step 0a, **before settle**) | 6am | Loads completed events **from the CSV mirror** over a **self-healing window** — everything since MAX(`ufc_fight_log.game_date`), capped 365 days; writes `games` scores (ALL duplicate rows) + `ufc_fight_log` + fighter profiles |
| Settlement | daily pipeline (`settle`) | 6am | `_settle_ufc_picks` settles any unsettled UFC BET pick whose fight has scores (incl. the slug-pair fallback for picks on duplicate/orientation-swapped games rows) |

| UFC opening-price card (`ufc_open_moneyline_card`) | the worker (scheduler) | hourly at :25 UTC | Bets only on the 12:25Z run; other runs close fights that reached a week out as NONE rows; publishes. `RUN_UFC_OPEN_MONEYLINE=0` stops it |

### The schedule gate (2026-10-20)

`data/schedule_context.py` holds a fight while either fighter has an earlier
fight on a card that is not in `ufc_fight_log` yet. A fight counts as done once
its CARD is in the log, whether or not this fighter is on it, because a
cancelled bout never reaches the log. Any new UFC card must go through it.

### Data sources

- **Results: the CSV mirror, not live scraping (2026-06-11).** ufcstats.com
  sits behind a browser-level Cloudflare challenge, so the primary path is
  `data/ingestors/ufc_csv_loader.py`, reading the
  [Greco1899/scrape_ufc_stats](https://github.com/Greco1899/scrape_ufc_stats)
  CSV mirror (updated weekly). The CSVs keep ufcstats' fight and fighter ids,
  so rows are identical to what the HTML scraper
  (`ufc_stats_ingestor.py`, kept as plan B) would produce. Config:
  `UFC_CSV_BASE_URL`, `UFC_CSV_DIR`. Refresh:
  `python -m data.ingestors.ufc_csv_loader --backfill 2010 2026`.
- **Price history, free (2026-11-13):** `data/ingestors/ufc_price_archive.py`
  stores two public archives in `ufc_price_archive`: fight-canon-db (MIT;
  BestFightOdds open and closing range, UFC 2007+) and the Ultimate UFC
  Dataset (CC BY 4.0; a fight price and three method prices per fighter,
  2010+). BestFightOdds' robots.txt allows everything but `/cnadm/`;
  OddsPortal disallows its dated archive; Tapology disallows Claude's
  crawlers by name.
- **Price history, the feed (bought 2026-11-13, 150,240 credits):**
  `data/ingestors/ufc_odds_history.py` stores fight winner and round totals
  for every book, noon UTC each day 2020-06-06 to 2026-06-13 and six pulls
  on each card day, in `ufc_odds_history` (552,576 rows, change-only, every
  promotion, UFC fights placed on our fight ids) and its ledger
  `ufc_odds_history_pulls`. The feed has nothing before 2020-06-06; the
  daily pull is the snapshot served at 11:55 UTC. Round totals come from
  Pinnacle from 2020 (2,421 fights at any line) and DraftKings from late
  2023 (1,072: 31 in 2023, 417 in 2024, 430 in 2025, 194 to June 2026); no
  other book a pick may name carries them.
- **Prop prices, BestFightOdds (stored 2026-11-14, free):**
  `data/ingestors/ufc_prop_history.py` crawls each UFC card's page (one
  request each, 3 s apart; robots.txt allows it) into `ufc_prop_history`
  (563,286 prices: every book's last recorded price on the fight winner and
  every prop, 2021-06-05 to 2026-11-07), `ufc_prop_history_fights` (3,146
  fights, 2,823 placed on our fight ids), `ufc_prop_history_ticks` (price
  histories, asked for per prop) and the ledger `ufc_prop_history_pulls`.
  DraftKings' columns are empty from late 2025. A last recorded price is
  the book's last change, not its price at any set time.

### Mobile

UFC is an option in the global sport toggle. UFC matchups render "A vs B" (not "A @ B"). Stats tab has a UFC fighter leaderboard (Wins/KO Wins/Sub Wins/Sig Strikes/Takedowns/Knockdowns/Sub Attempts) backed by `v_fighter_season_totals_ufc` + `fighter_window_totals_ufc(p_season, p_window)` — the window ranks each fighter's last N fights **career-wide**. UFC rows are display-only.
