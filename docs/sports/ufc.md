# UFC — pipeline operations

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

## 20. UFC — Pipeline Operations
### Models (registered, NOT yet trained — session 49)

| Model ID | Type | Market | Odds source | Status |
|---|---|---|---|---|
| `ufc_moneyline` | binary XGBoost + Platt | h2h | real DK h2h (bulk feed) | **LIVE** — holdout acc 66.2% / AUC 0.714 / CalErr 5.99% (above gate; provisional) |
| `ufc_total_rounds` | binary XGBoost + Platt | totals | per-event DK round totals when present; else prob-only vs synthetic 2.5/4.5 line | **LIVE** — acc 63.9% / AUC 0.669 / CalErr 3.84% |
| `ufc_method_of_victory` | **3-class** XGBoost (`multi:softprob`) + calibrated | method | **prob-only** (in `PROB_ONLY_MODELS` — The Odds API has no method odds) | **LIVE** — acc 56.5% / OvR-AUC 0.673 / CalErr 3.23% |

Thresholds (placeholder — tune after 50+ settled picks): ML 65%/8%, rounds 62%/8%, method 65% prob-only.

### Conventions (load-bearing — don't break)

- **home/away mapping:** The Odds API's `home_team` fighter → our `home_team`. `games.home_team/away_team` store **display names**; `game_id = UFC_{date}_{away_slug}_{home_slug}` (slug = lowercase, accents stripped, hyphenated). Historical backfill rows (no pre-fight odds row) assign home = lexicographically smaller slug — **never winner-first** (label leakage).
- **Name matching:** Odds API names → `slugify_fighter()` → ufcstats fighters. Mismatches (nicknames, "Jr.", transliteration) go in `config.UFC_NAME_ALIASES` (Odds API name → ufcstats name). The results scraper matches games by slug pair ±1 day. Unknown fighter at score time → fight skipped with a log line naming the fighter.
- **Scores convention:** `games.home_score/away_score` for UFC are 1/0 win indicators (0.5/0.5 + `home_win NULL` for draw/NC). The generic settle path therefore **excludes `ufc_%`** — `_settle_ufc_picks` in paper_tracker handles ML (draw/NC = PUSH), round totals (fractional rounds completed: O2.5 = fight passes 2:30 of R3), and method (DQ/overturned = NO_ACTION), over a **trailing 14-day window** so late-posted ufcstats results still settle.
- **Five-round bouts:** unknowable pre-fight from our data; inferred from the DK round-total line (≥3.5 → 5 rounds) else assumed 3. Training uses the true `scheduled_rounds` from ufcstats — known mismatch for main events without DK totals lines (documented, acceptable v1).
- **Min-history gate:** fighters need ≥3 prior UFC fights (`MIN_UFC_FIGHTS`) or the fight is skipped — debuts are unmodelable (the early-season analog).

### Pipeline

| Step | Runs where | Frequency | What it does |
|---|---|---|---|
| UFC odds (h2h bulk + per-event round totals) | GitHub Actions (`step_odds`) | 6am + hourly to 5pm + every 10 min 6pm–11pm | DK fight-winner lines; round totals attempted per-event (non-fatal when DK doesn't list them) |
| UFC scoring | GitHub Actions (`step_scoring`) | 6am + every refresh pass | `run_scorer` UFC branch → picks |
| UFC results (`ufc-results`) | daily pipeline (step 0a, **before settle**) | 6am | Loads completed events **from the CSV mirror** over a **self-healing window** — everything since MAX(`ufc_fight_log.game_date`), capped 365 days (the mirror can lag a card by weeks; a fixed 8-day window missed every 2026 card — see session 103); writes `games` scores (ALL duplicate rows) + `ufc_fight_log` + fighter profiles |
| Settlement | daily pipeline (`settle`) | 6am | `_settle_ufc_picks` — **no trailing window**: settles any unsettled UFC BET pick whose fight has scores (incl. slug-pair fallback for picks on duplicate/orientation-swapped games rows) |

UFC events are ~weekly (Saturdays) — most days all UFC steps no-op cleanly.

### Data source — CSV mirror, not live scraping (2026-06-11)

ufcstats.com moved behind a **browser-level Cloudflare challenge** that plain
`requests` and `cloudscraper` both fail (HTTPS refused; HTTP returns the
"Checking your browser..." interstitial → empty HTML → 0 events). Solving it
live would need a headless browser, which still gets blocked from GitHub
Actions' datacenter IPs.

So the **primary UFC data path is `data/ingestors/ufc_csv_loader.py`**, which
reads the [Greco1899/scrape_ufc_stats](https://github.com/Greco1899/scrape_ufc_stats)
GitHub CSV mirror — a maintained repo whose own scheduled scraper keeps 1:1 CSV
exports of ufcstats.com current (updated weekly after each card). The CSVs
preserve ufcstats' fight/fighter ids in their URL columns, so rows are
**identical** to what the HTML scraper would have produced. The loader reshapes
CSV rows into the exact dict shapes the pure parsers emit and feeds the shared
`ufc_stats_ingestor._ingest_event(ev=…, detail_lookup=…)` writer — so
home/away assignment, idempotency, and the settlement contract are unchanged.
`ufc_stats_ingestor.py` (the HTML scraper) is kept as a documented plan B.

Config: `UFC_CSV_BASE_URL` (the raw-GitHub base, env-overridable) and
`UFC_CSV_DIR` (point at a local folder of the same CSVs for offline use).
Coverage check (2026-06-11): 617 events 2010–2025, 7,231 fights, 99.7% with
both fighter ids resolved (debut fighters absent from the profile CSV are
skipped — they fail the 3-fight gate anyway).

### First-time setup — DONE (backfilled + trained 2026-06-11, retrained 2026-06-19)

The 3 models are trained, committed, and active in `model_registry`. To refresh
(e.g. after new fight cards land in the CSV mirror):

```bash
# 1. Refresh fight data from the CSV mirror (idempotent — skips already-ingested
#    fights). Bump the end year for newer events: --backfill 2010 2026
python -m data.ingestors.ufc_csv_loader --backfill 2010 2025

# 2. Retrain (multiclass branch handles ufc_method_of_victory automatically),
#    then re-commit the new active artifacts (the prior versions deactivate):
python -m models.trainer --model ufc_moneyline
python -m models.trainer --model ufc_total_rounds
python -m models.trainer --model ufc_method_of_victory
git add -f models/saved/ufc_*.pkl && git commit -m "Retrain UFC models"
```

**Open flag:** `ufc_moneyline` holdout CalErr is **5.99%, above the 5% gate** — a
retrain on the same fight data won't move it (confirmed 2026-06-19). Improving it
needs feature work (e.g. opponent-adjusted striking/grappling, layoff/age
interactions) or a real historical-odds backtest, not another retrain. Treat the
65%/8% ML threshold as provisional and re-check after 50 settled live picks.

**Backtest caveat:** no historical UFC odds exist in our DB, so all UFC backtests are prob-only at synthetic −110 (Kaggle UFC datasets carry real historical odds — a future enhancement for a truer moneyline backtest). Live `ufc_moneyline` scores vs real DK prices from day one.

### Mobile

UFC is the third option in the global sport toggle (MLB | WNBA | UFC). UFC matchups render "A vs B" (not "A @ B"). Stats tab has a UFC fighter leaderboard (Wins/KO Wins/Sub Wins/Sig Strikes/Takedowns/Knockdowns/Sub Attempts) backed by `v_fighter_season_totals_ufc` + `fighter_window_totals_ufc(p_season, p_window)` — the window ranks each fighter's last N fights **career-wide** (fighters fight ~3×/year). UFC rows are display-only (no fighter detail screen yet — WNBA precedent).

---
