# The UFC market study, 2026-11-13

Every table in `docs/ufc_market_audit.md` is printed by one script here. They
read no database and make no paid call except `feed_probe.py`.

**Run from the cache folder** (`%TEMP%\ufc_research` by default, or
`UFC_STUDY_DIR`): every script reads and writes its parquet files relative to
the working directory, and imports its siblings from this folder.

1. `build_cache.py` and `odds_census.py` copy the UFC rows of `games`,
   `ufc_fight_log`, `fighters`, `picks` and `odds` out of mike's local mirror
   (`docs/local_ops.md`; override with `LOCAL_MIRROR_TABLES`).
2. The two free archives go in `dl_canon\canon.db` (fight-canon-db release)
   and `dl_uud\ufc-master.csv` (Ultimate UFC Dataset). Both are also stored in
   Supabase by `data/ingestors/ufc_price_archive.py`.
3. `fights.py` builds `fights.parquet` (one row per fight, every input taken
   strictly before the fight); `ml_hist.py` joins the archive prices to it.
4. Then any study script: `ml_base.py` (baselines), `ml_blind_open.py`,
   `ml_anchor.py` (the market-anchored model, walk-forward), `ml_open_clv.py`,
   `ml_open_placebo.py`, `ml_steam.py`,
   `ml_open_2026.py` and `ml_shop_2026.py` (DraftKings' and the US books'
   first quotes, 2026), `ml_five_rounds.py` and `ml_five_dog.py`,
   `pilot_2026.py` and `totals_model.py` (round totals), `method_study.py`.

5. On the bought history (the spool of `data/ingestors/ufc_odds_history.py`):
   `feed_quotes.py <spool>` builds `feed_quotes.parquet`; then `feed_open.py`
   (each book's first price, the Pinnacle-anchored rule, round totals),
   `feed_kill.py <min lead hours>` (the shipped rule's kill tests),
   `totals_search.py` (round totals: the anchored model, market structure,
   the mechanisms and the stuck ladder; audit §4),
   `feed_debut.py`, `expected_value.py` (the shipped rule's units and return
   by year, against its own EV and Pinnacle's close), `example_bets.py` (its
   2026 backtest bets, as picks), and `card_replay.py` (the card's own code against the
   research, bet for bet; needs DATABASE_URL). `live_replay.py` replays the
   rule on our own 2026 store; `non_ufc_events.py <spool>` counts the fights
   listed but not fought on their card.

6. Price routes for the method, distance and round props (audit §5):
   `dk_props_probe.py` reads DraftKings' own UFC board (run on mike's PC;
   saves to `dk_probe\`), `bfo_probe.py` reads BestFightOdds' event pages,
   price charts and event sitemap (saves to `bfo\`). Both read only, and
   both re-read their saved answers with `--offline`.

7. The prop markets graded (audit §5f). `data/ingestors/ufc_prop_history.py`
   stores BestFightOdds' pages (and any price histories asked for) in
   Supabase; mirror its four tables first (`local_mirror.py run --only
   "public.ufc_prop_history*"`). Then `prop_load.py` builds `props.parquet`
   (every price, settled; split fights folded), `prop_grade.py blind` and
   `prop_grade.py models` (three mechanisms per market, walk-forward, kill
   tests), `prop_leads.py tables` (the two leads taken apart; writes
   `prop_lead_jobs.txt`, the price histories they need) and, once those are
   stored and mirrored, `prop_leads.py retime` and `prop_staleness.py` (how
   old a last recorded price is).

`feed_probe.py` is PAID (2 credits a market live, 20 in history) and logs every
call to `api_call_log` through `config`.
