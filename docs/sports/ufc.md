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
the stored id, because the feed stores each fight under two ids.

The three models of 2026-06-11 (`ufc_moneyline`, `ufc_total_rounds`,
`ufc_method_of_victory`) are in `config.RETIRED_MODELS`; their feature
engine, scorer and trainer branches and artifacts are gone. They had been
graded on probability alone at a synthetic -110, because no UFC price
history was ever stored, and method of victory never had a market price.
Their picks stay in `picks`, graded.

The grid below says where every other market stands.

### The market grid

| Market | Settles on | Inputs held | Prices | Baseline | Method tried | Result | Status |
|---|---|---|---|---|---|---|---|
| Fight winner | `games.home_win` (draw / no contest = push) | `ufc_fight_log` 2010-2026, `fighters`; ratings built strictly before each fight | Free archive: BestFightOdds open + closing range 2010-2026 (`ufc_price_archive`); feed history 2020-06+ (not bought); `odds` 2026-06+ every pull, 12 books | Blind favourite -0.8% to -3.9%, underdog -2.3% to -8.3% across the closing range, 7,541 fights | Market-anchored rating model at the close; at the first posted price; at each US book's first stored price; Pinnacle-anchored with US line shopping; five-round fights | At the close: nothing holds. At BestFightOdds' open: 1,531 bets +7.8% [+3.9, +11.8], positive against the close every year since 2018. At DraftKings' own first price, 2026: negative against Pinnacle's close (-2.1% to -2.5%); on the bought 2020-2026 history at the deciding books, Pinnacle-anchored: 846 bets +12.85%, 7/7 years | **Live**: `ufc_open_moneyline`, Pinnacle-anchored at a week out (audit §3d) |
| Total rounds (0.5-4.5) | rounds completed from `ufc_fight_log` end round and time; five-round fights from `scheduled_rounds` | same | `ufc_odds_history` (bought): Pinnacle 2021+, DraftKings 2025+; `odds` 2026-06+; no free archive | 2020-2026: blind under -10.8% (DraftKings, 1,066) and -6.8% (Pinnacle, 2,403); blind over -3.4% and -1.6% | Finish-time model (one logistic per line) | Log loss 0.684 against the price's 0.649: the model knows less than the line | **Nothing clears** (audit §4); next: a Pinnacle-anchored finish model |
| Points spread | not known: DraftKings and Bovada list one (Holland +7.5) | | feed, live, 2 books | | | | **Parked**: what it settles on is unknown |
| Alternate round totals | as total rounds | | Pinnacle only on the feed | | | | **Parked**: no book a pick may name |
| Method of victory (by fighter) | `ufc_fight_log.method` | same | **no live price**: the feed rejects every key (HTTP 422, 2026-11-13); free archive 2012-2026 near-close prices | Every blind method bet loses: favourite by decision -3.3% (5,821), finishes -20% to -41% | Blind by method and side | No profit anywhere | **Parked**: no live price |
| Goes the distance, round betting, exact round | `ufc_fight_log` | same | none: rejected by the feed, no free archive | | | | **Parked**: no price source |
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
  `ufc_odds_history_pulls`. The feed has nothing before 2020-06-06; round
  totals come from Pinnacle from 2021 and DraftKings by 2025.

### Mobile

UFC is an option in the global sport toggle. UFC matchups render "A vs B" (not "A @ B"). Stats tab has a UFC fighter leaderboard (Wins/KO Wins/Sub Wins/Sig Strikes/Takedowns/Knockdowns/Sub Attempts) backed by `v_fighter_season_totals_ufc` + `fighter_window_totals_ufc(p_season, p_window)` — the window ranks each fighter's last N fights **career-wide**. UFC rows are display-only.
