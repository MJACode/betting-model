# Environment and config topology

> Moved out of CLAUDE.md on 2026-08-30. The parts a session actually needs
> every time (the three config homes, the DraftKings-only invariant, the
> pre-game/in-play split) are summarised in CLAUDE.md §6; this is the full text.

## 13. Environment
- **Python:** Matt has **Python 3.14** (`C:\Python314\python.exe`) — very new as of 2025
- **Key packages:** xgboost, scikit-learn, optuna, pybaseball, streamlit, plotly,
  loguru, requests, python-dotenv, statsapi, nhl-api-py
- **Project path (Matt's machine):** `C:\Users\Matth\.claude\Bet Repos\betting-model`
- **DB:** Supabase (Postgres) — project ref `vvprgnrmzeekokzkrkfu`. Connection string in `.env` as `DATABASE_URL`. Use the **Session pooler** connection string (port 5432, `aws-1-us-west-2.pooler.supabase.com`) for GitHub Actions — direct connection (port 5432, `db.vvprgnrmzeekokzkrkfu.supabase.co`) only works locally.
- **Models saved to:** `models/saved/` (auto-created by trainer)
- **Network note:** The Cowork sandbox blocks outbound pip/npm. All installs must run
  on Matt's local machine.
- **IMPORTANT — always use `python -m pip install` not `pip install`** on Matt's
  machine. Windows has multiple Python versions; `python -m pip` guarantees pip and
  python point to the same installation. `pip install` alone may install to the wrong one.

### Where API keys + thresholds are stored (config topology)

Since the pipeline moved to the always-on Railway worker (session 102), it's worth being precise about where each kind of config actually lives — there are three homes and they play different roles.

**API keys / secrets — stored in Railway Variables (the live copy the worker reads):**
The Railway worker (`scheduler.py`, the service that runs the 6am daily pipeline + intraday refreshes + the live loop) reads its secrets from the **Railway → Variables** tab. These are the authoritative runtime copy:
- `DATABASE_URL` (Supabase **session pooler** string), `ODDS_API_KEY`, `DATAGOLF_API_KEY`
- `FETCH_F5_LIVE=1`, `TZ=America/New_York`
- live-loop controls: `RUN_LIVE_LOOP` (set `0` to kill the in-play loop), `LIVE_DAILY_CREDIT_CAP` (default 1000/day)

The **same** keys also live in two other places, each for a different purpose:
- **GitHub Actions secrets** — break-glass only. Manual `workflow_dispatch` runs (Retrain Model, break-glass pipeline, mobile OTA) still read these, but nothing is scheduled on Actions anymore (session 102/103).
- **Local `.env`** (Matt's machine) — for manual CLI runs. `docs/cloud_worker.md` is the source of truth for the Railway variable list; keep the three in sync when a key rotates.

**Thresholds — canonical in the repo, mirrored to Supabase (NOT stored in Railway):**
Model prob/edge cuts + `MODEL_MIN_ODDS` price floors + `PAUSED_MODELS`/`PROB_ONLY_MODELS` are **canonical in `config.py`** (version-controlled). They are NOT a Railway variable. The flow (session 65):
- The **scorer reads `config.py` directly** — so the server-side BET decision is always config-canonical wherever the code runs (Railway, Actions, local).
- `data.threshold_sync` mirrors `config.py` → the Supabase **`model_action_thresholds`** table, which the app's action filter + the track-record views read. This sync runs as **Step 0c of the daily pipeline on the Railway worker** (and can be run manually: `python -m data.threshold_sync`).
- So "thresholds are stored in Railway" is really: **config.py (repo) → Supabase table, and Railway is just the host that runs the daily sync.** A table edit made by hand is temporary — the next Railway daily run overwrites it from `config.py` on master. To change a threshold permanently, edit `config.py` and merge.

**Sportsbooks — canonical in `config.py`, env-overridable:**
`LINE_SHOP_BOOKMAKERS` (default `draftkings,fanduel,betmgm,williamhill_us,espnbet`) drives
`ODDS_API_BOOKMAKERS_PARAM`, which both `odds_ingestor` (game markets) and
`prop_odds_ingestor` (player props) send as the Odds API `bookmakers` param. Override with a
`LINE_SHOP_BOOKMAKERS` env var to add/drop a book without a code change.

**Best line — `BEST_LINE_BOOKMAKERS` (added 2026-08-28):** every scored pick now records the
best price across all seven ingested books plus which book had it, in
`picks.best_book / best_odds / best_implied_prob / best_edge / best_bet_link`. That is the
number to BET and what the app shows. It is deliberately NOT what decides the bet: `edge`, the
BET/AVOID call, the Kelly stake, settled P&L and CLV all still measure against DraftKings,
because every `docs/thresholds.md` threshold was swept on DK-implied edge and best-of-N pricing runs **~2pp
cheaper in implied probability** (measured over 92 MLB games on 2026-08-28; best beat DK on ~⅓ of
sides, avg 2.5 books priced per game) — adopting it as the qualifying price would loosen every
cut by that much with nobody deciding to. Only quotes at the SAME line count (a better price on
Over 9.0 is not a better price on Over 8.5), and in-play snapshots are excluded. Once ~a month of
`best_edge` history has accrued on the picks table, the thresholds can be re-swept at best price
and qualification flipped over deliberately, in one change.

Two invariants that must not be broken:
- **The models only ever DECIDE on DraftKings.** `ODDS_API_BOOKMAKER` is the scoring book;
  `scorer._get_dk_odds` / `_get_prop_dk_odds`, `paper_tracker._closing_dk_odds`, and all four
  feature engines hard-filter to it (feature engines whitelist `('draftkings','sbr_consensus')`
  so extra books can't multiply training rows). `tests/test_multi_book_odds.py` asserts each of
  these — if you refactor one of those queries, that test is the tripwire. The scorer's
  best-line helpers DO read other books, but only to fill the `best_*` columns after the pick is
  decided; `tests/test_best_line.py` asserts `_make_pick` / `_make_prop_pick` never see them.
- **A bad book key must never cost us a fetch.** Both ingestors retry with DraftKings alone on a
  422 (the `h2h_3way` failure mode: one unsupported param value 422s the whole request). Adding a
  book is therefore safe to try; worst case it silently no-ops.

**Retention — line-shop rows are pruned, DraftKings history is not.**
Both odds tables are append-only (~21 snapshots per proposition per day), but the ONLY readers
of non-DK rows are the two `DISTINCT ON` all-books views, which return just the newest row per
book. So non-DK history is written once and never read — at 5 books that was ~2.7 GB/month
against a ~2 GB database. `data/prune_odds.py` (`--step prune-odds`, Step 11b, after settle)
bounds it:
- **Never pruned:** `draftkings` (CLV / line movement / opening signals) and `sbr_consensus`
  (synthetic training lines the feature engines whitelist).
- **Tier 1** — games older than `PRUNE_NON_DK_KEEP_DAYS` (default 2): all non-DK rows.
- **Tier 2** — games before today, inside the window: every non-DK row except the newest per
  proposition per book (the only one the views can return).
- Today's and future rows are untouched, so it can't race an ingest or blank the live board.
- Retention is keyed on the **game's** date, not the snapshot's — `odds` has no date column, so
  it joins `games` (the view's convention). Dating by snapshot would prune a future UFC/golf
  event's only line-shop row, since those are priced up to 7 days ahead.
- **Pruned history is gone permanently.** Raise `PRUNE_NON_DK_KEEP_DAYS` before building
  anything that needs non-DK history (e.g. "did the best book beat DK at close?").

Caesars is `williamhill_us` on The Odds API, not `caesars` — **confirmed live 2026-08-01**, along
with `espnbet`; all 5 books are ingesting. Confirm keys against the live API before changing the
list — the mobile `bookLabel` map handles both spellings, but the ingestor only stores what the
API returns:
```bash
curl -s "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds?apiKey=$ODDS_API_KEY&regions=us&markets=h2h&oddsFormat=american" \
  | jq -r '.[0].bookmakers[].key' | sort -u
```

---