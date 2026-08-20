"""
config.py — Central configuration loader.

All other modules import from here. Never access os.environ directly elsewhere.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env ─────────────────────────────────────────────────────────────────
# Works from any working directory because we resolve relative to this file.
ROOT = Path(__file__).parent.resolve()
load_dotenv(ROOT / ".env")

# ── API Keys ──────────────────────────────────────────────────────────────────
ODDS_API_KEY: str = os.environ.get("ODDS_API_KEY", "")

# ── Database ──────────────────────────────────────────────────────────────────
# DATABASE_URL is the primary connection string used by all production code.
# Format: postgresql://user:password@host:5432/dbname
# Set in .env for local dev; set as Railway env var in production.
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

# DB_PATH is kept for backwards compat with tests (in-memory SQLite fixtures).
DB_PATH: Path = ROOT / os.environ.get("DB_PATH", "data/betting_model.db")

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY", "")

# ── Paper Trading ─────────────────────────────────────────────────────────────
BANKROLL: float = float(os.environ.get("BANKROLL", 1000))
# Evaluation start date — picks before this date are excluded from all P&L and
# go-live gate calculations. Set to when v8 models first ran live.
PAPER_TRADING_START: str = os.environ.get("PAPER_TRADING_START", "2026-04-14")

# ── Pick locking ──────────────────────────────────────────────────────────────
# When True (default), game-level picks (ML / runline / O-U / F5 / 3-way /
# method) LOCK at the first scoring run of the day (≈7am ET) and are NOT
# re-scored by later hourly refreshes — the morning pick is what you bet and what
# settles. Per-model: a model locks once it has written any pick for a same-day
# game; other models for that game can still fire on a later run when their odds
# post. Player props use a SEPARATE first-signal lock (LOCK_PROP_PICKS_AT_FIRST_
# SIGNAL below) since they can't lock at 7am. UFC/golf look-ahead (future-dated)
# games also keep re-scoring. Set to "0" to revert to the old delete-and-rescore-every-refresh
# behavior. Rationale: CLV is neutral (no edge in waiting for the closing line),
# so locking early is cleaner and stabilizes the board. See session 75.
LOCK_GAME_PICKS_AT_FIRST_RUN: bool = os.environ.get("LOCK_GAME_PICKS_AT_FIRST_RUN", "1") == "1"

# When True (default), PLAYER PROPS lock at their FIRST signal of the day. Props
# can't lock at 7am (they need evening confirmed lineups), so the lock triggers
# the first time a (game, model, player) prop crosses to a pick on a confirmed
# lineup — that signal becomes the bet of record and later refreshes don't
# overwrite it. Same first-signal philosophy as the game lock, just evening-
# triggered. Tradeoff: a late scratch after the lock stays put (rare; the bet
# simply settles as a no-action/void if the player doesn't play). Set to "0" to
# revert to delete-and-rescore-every-refresh for props. See session 78.
LOCK_PROP_PICKS_AT_FIRST_SIGNAL: bool = os.environ.get("LOCK_PROP_PICKS_AT_FIRST_SIGNAL", "1") == "1"

# Track-a-bet line-change alert: a tracked (game-level) bet pushes a notification
# when the DK price on its side moves at least this many implied-prob percentage
# points away from the price the user locked, in either direction. Re-notifies
# once per additional whole-multiple of this threshold (≈4pp, ≈8pp, …) so a
# steaming line escalates without spamming. See tracking/push_notifier.py.
LINE_CHANGE_NOTIFY_PP: float = float(os.environ.get("LINE_CHANGE_NOTIFY_PP", 4.0))

# ── Thresholds ────────────────────────────────────────────────────────────────
# Global fallback — used when a model has no specific override below.
BET_EDGE_THRESHOLD: float   = float(os.environ.get("BET_EDGE_THRESHOLD",   0.10))
AVOID_EDGE_THRESHOLD: float = float(os.environ.get("AVOID_EDGE_THRESHOLD", 0.10))

# Minimum model probability to generate a BET signal.
MIN_MODEL_PROB: float = float(os.environ.get("MIN_MODEL_PROB", 0.65))

# Per-model action filter — used by dashboard and Claude mobile for display filtering.
ACTION_THRESHOLDS: dict = {
    # MLB — re-optimized 2026-06-21 via the FULL-OUTCOME method: ALL scored picks
    # (not just BET signals), with outcomes recomputed from game scores +
    # player_game_log actuals — unbiased vs the earlier BET-only sweep. Still ~2
    # months of data; forward ROI will regress. over_under is edge-driven (prob bar
    # barely binds at 0.50/0.12). batter_hits/tb/sb + pitcher_hits have NO robust
    # winning cut on the full sample → retrain candidates (left at least-bad). HR's
    # -110 paper ROI is a settlement artifact (real-odds fix shipped 2026-06-20).
    "mlb_moneyline":      {"min_prob": 0.72, "min_edge": 0.11},  # 2026-07-04 (2nd decision): REVERTED to v20260413 model + tightened into its proven pocket — 2026 live full-outcome at this cut = 27 bets 21-6 +29.5% (whole 0.70-0.72 x 0.11-0.12 corner +10..+31%). The 07-04 retrain (v20260704_121659, CalErr 1.83%) stays registered INACTIVE — its 0.60/0.10 plateau (+25% on 2025 OOS) couldn't coexist with a green 2026 display (old-model picks grade -7.8% there). Re-evaluate the new model next spring. Old model scored all season with the frozen-bullpen bug — now fixed, so forward should be >= the banked record
    "mlb_over_under":     {"min_prob": 0.59, "min_edge": 0.07},  # 2026-07-11 TIGHTENED 0.57/0.05 -> 0.59/0.07 (Matt: fewer picks, better ROI). Fresh 2025 OOS all-sides sweep vs the live v20260704 model (reproduced the 366-bet count at the old cut exactly): 0.59/0.07 = 203 bets 60.4% +16.3% vs 366 bets +16.9% at the old cut — 45% fewer picks at plateau ROI, every month Apr-Sep positive (worst +3%), robust neighborhood (0.58-0.60 x 0.06-0.08 all +11..+16%). No cut robustly BEATS the plateau: the +18-21% cells are 39-53-bet noise stripes that collapse one grid step away (0.61/0.11 +17.8% -> 0.61/0.12 +3.5%)
    "mlb_runline":        {"min_prob": 0.68, "min_edge": 0.11},  # 2026-07-02 CORRECTION: the 2026-06-28 "broad plateau" (0.55/0.10 = 48-41 +14.9%) was computed on a SIGN BUG in v_model_full_outcome_record — away-side picks were graded with (away-home)+scored_line instead of (away-home)-scored_line, flipping every one-run game. Corrected (validated 30/31 vs stored settlements): 0.55/0.10 is 35-56 -20.6%; every prob floor below 0.68 is negative at volume. Corrected optimum: 0.68/0.11 = 19 bets 13-6 +20.0% (robust pocket 0.68-0.70 x 0.09-0.12 all +6..+20%; 9 away +1.5 / 10 away -1.5). Small sample. 2026-07-04: model swapped to v20260704_121650 (2019-2024+2026, holdout 2025, CalErr 2.95% vs v8 5.56%); cut CARRIED OVER UNVALIDATED (2025 has no runline prices; 2026 now in-sample — in-sample check at this cut: 5-0, all away +1.5). Expect very low volume (~1-2 picks/month)
    "mlb_f5_moneyline":   {"min_prob": 0.67, "min_edge": 0.07},  # 2026-06-26 full-outcome sweep (validated 104/104): 0.67/0.07 = 105 bets 59-31 65.6% +9.86% ROI — MORE picks AND higher ROI than 0.71/0.0 (70 bets +9.49%). Robust band 0.67-0.69/0.07 ≈ +9.3-9.9%
    # mlb_f5_over_under and mlb_f5_runline: DISABLED — DK does not carry these markets.
    "mlb_prop_batter_rbi":    {"min_prob": 0.47, "min_edge": 0.16},  # 2026-07-11: + DK >= -140 price floor — capped 36 bets +7.3% vs +2.2% uncapped. (A 0.45/0.12 volume cell = 142 bets +8.6% exists; Matt declined — no volume bets)
    "mlb_prop_batter_runs":   {"min_prob": 0.47, "min_edge": 0.16},  # UNPAUSED 2026-08-09 — with the -140 floor this cut grades 40 bets 21-19 +24.6% (robust edge>=0.16 band)
    "mlb_prop_batter_hits":   {"min_prob": 0.78, "min_edge": 0.17},  # 2026-06-28 full-outcome re-sweep: 0.78/0.17 = 77 bets 56-21 +8.3% (genuine combo found — UNPAUSED from the 2026-06-21 pause)
    "mlb_prop_batter_tb":     {"min_prob": 0.83, "min_edge": 0.17},  # 2026-06-21 RE-SWEEP: NO winning cut (best -4.2%) — least-bad, RETRAIN candidate
    "mlb_prop_batter_walks":  {"min_prob": 0.45, "min_edge": 0.14},  # 2026-06-21 full-outcome RE-SWEEP: 0.45/0.14 = 65 bets +5.3% (only positive pocket; high-edge/low-prob)
    "mlb_prop_pitcher_outs":  {"min_prob": 0.5, "min_edge": 0.12},  # 2026-06-21 full-outcome: +5.6%/102
    "mlb_prop_pitcher_k":     {"min_prob": 0.71, "min_edge": 0.06},  # 2026-06-20: 24 bets 71% +17.1%
    "mlb_prop_pitcher_er":    {"min_prob": 0.61, "min_edge": 0.08},  # 2026-06-21 ≥10% target: 0.61/0.08 = 81 bets +11.1% (CI [-8.3,+30.5])
    "mlb_prop_pitcher_hits":  {"min_prob": 0.65, "min_edge": 0.12},  # NO winning cut — retraining (already current-window; needs feature work)
    "mlb_prop_pitcher_walks": {"min_prob": 0.6, "min_edge": 0.08},  # 2026-06-21 full-outcome: +6.3%/66
    # Binary/rare-event models — prob scale differs from Poisson
    "mlb_prop_batter_hr":     {"min_prob": 0.225, "min_edge": 0.0},   # 2026-06-26 STRICTER: raised 0.20→0.225 (best-record cut). Full-outcome sweep of all decided HR picks since 4/14: hit-rate PEAKS at the 0.22-0.23 plateau (17.2% @ 0.225 vs 15.4% @ 0.20), flanked by dips at 0.205/0.235; the model's >0.21 picks would degrade further but 0.225 is the argmax. Cuts volume ~66% (253→87 decided bets). NOTE: HR overs are inherently low-hit (~17% even at the best cut) so the W-L record always looks ~1-in-6, and at REAL DK odds every cut is -EV (the +EV edge filter is anti-predictive vs DK's efficient longshot line) — this maximizes RECORD, not profit. Per session-60 directive HR is never paused.
    "mlb_prop_batter_sb":     {"min_prob": 0.18, "min_edge": 0.10},  # NO winning cut — already current-window v2; needs feature work, not retrain
    # WNBA — placeholder thresholds; retune from the 2025 holdout backtest sweep.
    "wnba_moneyline":            {"min_prob": 0.64, "min_edge": 0.04},  # 2026-07-02 full-outcome sweep (585/585 grading validated): the placeholder 0.66/0.12 only ever fired 3 bets. 0.64/0.04 = 17 bets 14-3 +31.9%; plateau 0.60-0.68 x 0.00-0.04 all +25..+32%. Tiny sample — re-sweep as season builds
    # 2026-07-19: first real cuts — models trained on synthetic 2019-2025 lines
    # (wnba_odds_synthesizer), cuts from the honest 2026 OOS sweep vs real DK
    # lines (118 games, not in training): O/U 0.60/0.06 = 23 bets 60.9% +14.5%;
    # spread 0.60/0.10 = 34 bets 64.7% +22.6% (edge>=0.06 positive at every prob
    # floor). Small OOS sample — provisional; re-sweep after 50 settled picks.
    "wnba_over_under":           {"min_prob": 0.60, "min_edge": 0.06},
    "wnba_spread":               {"min_prob": 0.60, "min_edge": 0.10},
    # WNBA props — re-optimized 2026-06-20 from settled BET picks since launch
    # (2026-06-01, real DK odds). VERY thin: 15-40 bet cuts over ~3 weeks — heavy
    # in-sample overfit, forward ROI will regress. Re-sweep as the season builds.
    "wnba_prop_player_points":   {"min_prob": 0.58, "min_edge": 0.17},  # PAUSED 2026-07-11 — full-outcome re-sweep on the 2x sample: NO positive cut at >=25 bets anywhere in the grid (current cut -4.1%/89). Cut kept for the unpause re-sweep
    "wnba_prop_player_rebounds": {"min_prob": 0.69, "min_edge": 0.08},  # 2026-07-11 re-sweep: KEPT — this is the ROI max of the whole grid (+5.6%/78); no cell reaches 8%. Volume alternative 0.53/0.02 = 292 bets +4.3%. Price floors HURT this model (it wins at heavy juice)
    "wnba_prop_player_assists":  {"min_prob": 0.69, "min_edge": 0.08},  # 2026-07-11 re-sweep: KEPT at the ROI max (+19.3%/44). The units-max 0.53/0.06 (103 bets +13.3%) was declined — no volume bets
    "wnba_prop_player_threes":   {"min_prob": 0.64, "min_edge": 0.12},  # PAUSED 2026-07-11 — re-sweep: best cell +0.6%/26, current cut -8.6%/46. No winning cut; price floors don't help either
    "wnba_prop_player_pra":      {"min_prob": 0.67, "min_edge": 0.16},  # PAUSED 2026-07-11 — re-sweep: NO positive cut at >=25 bets (current cut -6.3%/66)
    # NHL — placeholder thresholds; tune after 50+ settled picks. moneyline /
    # over_under / puckline score vs real DK lines. moneyline_regulation scores
    # vs DK's 3-way market — its per-side prob is lower (3 outcomes), hence the
    # 0.40 floor vs 0.55 for the binary markets.
    "nhl_moneyline":            {"min_prob": 0.55, "min_edge": 0.05},
    "nhl_moneyline_regulation": {"min_prob": 0.40, "min_edge": 0.05},
    "nhl_over_under":           {"min_prob": 0.55, "min_edge": 0.05},
    "nhl_puckline":             {"min_prob": 0.55, "min_edge": 0.05},
    # NFL — the standalone wind-totals card (§28), published into picks by
    # scripts/nfl_wind_publisher.py. The card itself is the real gate (raw
    # forecast wind >= 11 mph AND >= 3% edge after de-vig at the best book);
    # these floors just mirror it so the app's action filter can't hide a
    # card-qualified pick. 0.52 ~ the -110 breakeven; calibrated under-probs
    # run 0.56-0.60.
    "nfl_wind_totals":          {"min_prob": 0.52, "min_edge": 0.03},
    # NFL opener-spread (§28) — the sharp-vs-soft stale-line rule, published by
    # scripts/nfl_wind_publisher.py --opener. The card is the real gate
    # (|soft − Pinnacle| >= 1.0 in the T-7..T-2 window); model_prob is the
    # pooled validated ATS (0.5818), so 0.55 floors it and edge >= 0 filters
    # bets whose quoted juice already eats the whole edge.
    "nfl_opener_spread":        {"min_prob": 0.55, "min_edge": 0.00},
    # Live (in-play) — conservative placeholders; tune after 50+ settled live picks.
    "mlb_live_win_prob":   {"min_prob": 0.65, "min_edge": 0.10},
    "mlb_live_total_runs": {"min_prob": 0.65, "min_edge": 0.10},
    "mlb_live_runline":    {"min_prob": 0.65, "min_edge": 0.10},
    # NBA — placeholder thresholds; tune after 50+ settled picks. NBA mainlines
    # are the sharpest market we touch, so the game models run a higher edge gate
    # than props; double-double is prob-only (edge ignored, see PROB_ONLY_MODELS).
    "nba_moneyline":             {"min_prob": 0.66, "min_edge": 0.12},
    "nba_over_under":            {"min_prob": 0.66, "min_edge": 0.12},
    "nba_spread":                {"min_prob": 0.66, "min_edge": 0.12},
    "nba_prop_player_points":    {"min_prob": 0.60, "min_edge": 0.08},
    "nba_prop_player_rebounds":  {"min_prob": 0.60, "min_edge": 0.08},
    "nba_prop_player_assists":   {"min_prob": 0.60, "min_edge": 0.08},
    "nba_prop_player_threes":    {"min_prob": 0.60, "min_edge": 0.08},
    "nba_prop_player_pra":       {"min_prob": 0.60, "min_edge": 0.08},
    "nba_prop_player_blocks":    {"min_prob": 0.60, "min_edge": 0.08},
    "nba_prop_player_steals":    {"min_prob": 0.60, "min_edge": 0.08},
    "nba_prop_player_turnovers": {"min_prob": 0.60, "min_edge": 0.08},
    "nba_prop_player_dd":        {"min_prob": 0.55, "min_edge": 0.0},   # prob-only
    # UFC — placeholder thresholds; tune after 50+ settled picks.
    # ufc_moneyline scores vs real DK h2h odds. ufc_total_rounds uses real DK
    # round-total lines when the per-event endpoint carries them, else prob-only
    # vs a synthetic line. ufc_method_of_victory is prob-only (no DK odds via
    # The Odds API) — see PROB_ONLY_MODELS.
    "ufc_moneyline":         {"min_prob": 0.65, "min_edge": 0.08},
    "ufc_total_rounds":      {"min_prob": 0.62, "min_edge": 0.08},
    "ufc_method_of_victory": {"min_prob": 0.65, "min_edge": 0.0},
    # GOLF — placeholder thresholds; tune after 50+ settled picks per model.
    # NOTE: golf probabilities live on a MARKET-relative scale, NOT the 0.6+ scale
    # of two-sided sports. A win prob is ~3–15%, a top-10 prob ~10–30%. The min_prob
    # floors below reflect that — do not "fix" them up to 0.6+.
    "golf_outright":  {"min_prob": 0.03, "min_edge": 0.015},
    "golf_top10":     {"min_prob": 0.15, "min_edge": 0.05},
    "golf_top20":     {"min_prob": 0.25, "min_edge": 0.05},
    "golf_make_cut":  {"min_prob": 0.65, "min_edge": 0.05},
    "golf_matchup":   {"min_prob": 0.55, "min_edge": 0.05},
}

# Models where BET signal is decided by model probability alone (edge ignored).
# Use when the market is structurally illiquid/inefficient so DK prices don't
# anchor a meaningful edge — e.g. HR Over 0.5 where DK juices the over heavily
# and there is no real under market. Scorer skips the edge check; dashboard /
# Claude mobile SQL filters drop the edge clause for these models.
PROB_ONLY_MODELS: set = {
    "mlb_prop_batter_hr",
    # Method-of-victory odds are not carried by The Odds API — the model's
    # 3-class probability alone decides the BET signal.
    "ufc_method_of_victory",
    # NBA double-double is a Yes/No market DK juices heavily (and there is no
    # real "No" market to fade) — decide on model probability alone.
    "nba_prop_player_dd",
}
# Models temporarily PAUSED — never emit a BET signal. They are still scored and
# written as NONE rows (so the website can still show the game), but with no
# recommended bet, no settlement, and zero bankroll risk. A paused model is also
# excluded from the mobile action filter and the public track-record views.
# Reversible: remove the model_id here (and clear its `paused` flag in the
# model_action_thresholds table) to re-enable.
PAUSED_MODELS: set = {
    # 2026-06-21: PAUSED — no honest cut clears 10% ROI on the full-outcome sweep
    # (all scored picks since 2026-04-14). Per Matt, surface only models that can
    # clear 10%. These still SCORE (as NONE rows) so forward performance keeps
    # accruing for a later re-sweep; they just don't surface as BET picks.
    # Best achievable in-sample ROI shown per model. Unpause once a model earns a
    # real >=10% cut (esp. after the batter_runs/pitcher_outs retrains accrue live
    # picks, or after new features land for the others).
    # 2026-06-28 full-outcome re-sweep (v_model_full_outcome_record, ALL scored
    # picks since 4/14): these have NO positive cut at any real volume — genuinely
    # broken models that thresholds can't fix. Retrain with new features. 3 of the
    # 2026-06-21 pause (pitcher_walks +10.0%, batter_walks +5.3%, batter_hits +8.3%)
    # had real positive combos and were UNPAUSED; batter_runs was briefly unpaused
    # (+2.7%) then DROPPED again 2026-06-28 (too marginal — see below).
    "mlb_prop_pitcher_hits",   # best 60+ cut still -9.0% — retrain (needs batted-ball/contact features)
    "mlb_prop_pitcher_outs",   # best 60+ cut -2.6% — retrain (inherent IP variance)
    # 2026-07-11 PAUSED (Matt): pitcher ER + walks removed from display and
    # consideration for now. Both were running on the rolled-back May model
    # versions (session 94c) at marginal live cuts (er 0.61/0.08, walks
    # 0.60/0.08). Still score as NONE rows for forward tracking; thresholds kept
    # in the dicts below for the unpause.
    "mlb_prop_pitcher_er",
    "mlb_prop_pitcher_walks",
    "mlb_prop_batter_tb",      # best 60+ cut -1.7% — retrain (efficient market; needs contact-quality features)
    "mlb_prop_batter_sb",      # can't reach 60 bets at any cut — needs catcher CS%/pop-time (not ingested)
    # mlb_prop_batter_runs UNPAUSED 2026-08-09 (Matt: "unpause the run line one").
    # At 0.47/0.16 with the -140 floor it grades 40 bets 21-19 +24.6% — the pocket
    # is robust (the whole edge>=0.16 band is +15..+25% across prob 0.45-0.50, and
    # a second all-positive pocket sits at prob 0.66-0.72). Caveat: all of that
    # evidence is May-June — the July/Aug dead-zone universe was destroyed by the
    # started-game NONE cleanup (retired 2026-08-09), so re-sweep after ~40 clean
    # forward picks.

    # WNBA points / threes / PRA PAUSED 2026-07-11 (session 100b) and CONFIRMED
    # 2026-07-19: retrained with 2025 added (train 2019-2025, holdout 2026), then
    # swept the NEW models against the real stored 2026 DK prop lines at real
    # prices (1,366-2,218 side-rows each) — the ENTIRE prob x edge surface is
    # negative for all three (points -5..-10%, threes -2..-17%, pra -1..-7%;
    # tail cells included). DK's WNBA points/threes/PRA markets are efficient vs
    # rolling-average Poisson features — thresholds cannot fix these. A real fix
    # needs new FEATURES (opponent positional defense, usage-based minutes
    # projection), not retrains. Still score as NONE rows (fresh 20260719
    # artifacts); rebounds + assists stay LIVE (positive cuts exist).
    "wnba_prop_player_points",
    "wnba_prop_player_threes",
    "wnba_prop_player_pra",

    # wnba_prop_player_rebounds PAUSED 2026-07-29 — joins points/threes/PRA. It was
    # kept LIVE in the 2026-07-11 re-sweep as the last positive-ish WNBA prop (grid
    # ROI max +5.6%), but on the now-larger settled sample it has decayed to
    # -13.9% over 54 bets at the live 0.69/0.08 cut, and the full prob x edge sweep
    # (with the -140 floor) is negative in EVERY cell: -9.1% @ 0.69/0.16 (32 bets)
    # through -23.7% @ 0.65/0.12 (69 bets). The damage is side-structural, not a
    # threshold miss: OVER picks are -44%..-53% (34-43, -$1,505 over 79 bets) while
    # UNDER is roughly flat (82-64, -1.1% over 149 bets). The only non-negative cell
    # is under-only 0.73/0.14 = 17 bets +2.5%, which is inside noise and would need
    # side-restriction the scorer has no mechanism for — fitting that would be
    # textbook overfitting. Same verdict + same fix as the other three: this needs
    # opponent-positional-defense and minutes-projection FEATURES, not a re-cut.
    # Still scores as NONE rows so forward performance keeps accruing.
    "wnba_prop_player_rebounds",

    # wnba_over_under + wnba_spread PAUSED 2026-07-29 — their thresholds rest on a
    # LEAKED validation, so they are unvalidated rather than proven bad.
    #
    # Both launched 2026-07-19 on cuts taken from a "2026 OOS sweep vs real DK
    # lines" (O/U 0.60/0.06 = 23 bets 60.9% +14.5%; spread 0.60/0.10 = 34 bets
    # 64.7% +22.6%, then called "the most robust WNBA grid yet"). That sweep ran
    # through build_bulk_wnba_lookups, which took the LATEST odds snapshot per
    # (game_id, market) with no pre-tipoff cutoff. Because the evening refresh loop
    # runs to 11pm ET and writes post-start rows as snapshot_type='open', 89 of 133
    # completed 2026 games (67%) were featurized with a totals line that had already
    # drifted toward the final score — average leak 8.2 points, worst 47 — and 86/133
    # for spreads (avg 4.6, worst 41). total_line / spread_home is the top feature of
    # both models, so the sweep was partly reading the outcome it was predicting.
    # Fixed at the read side by _is_pregame_snapshot (features/feature_engine.py).
    #
    # The honest live records confirm the edge did not survive: with correct
    # pre-game lines the O/U model never reaches its own 0.60 prob bar (17 games
    # scored since 7/19, P(over) tops out at 0.599 -> ZERO BETs, which is the "not
    # producing" symptom), and the spread is 2-2 / -3.7% on its 4 settled bets.
    #
    # The MODELS are very likely fine: both trained on synthetic 2019-2025 lines
    # (one synthetic row per game, nothing to leak) with 2026 held out entirely, so
    # only the threshold calibration is invalid — no retrain implied. Cuts kept in
    # the dicts below. UNPAUSE only after scripts/wnba_line_sweep.py re-derives cuts
    # on pre-tipoff lines; if the clean grid has no positive cell, they stay paused
    # and need feature work instead. NOTE the O/U model also inherits the MLB O/U
    # lesson: it was trained on synthetic lines but serves on real DK lines, a
    # covariate shift on its top feature that likely explains the compressed
    # 0.42-0.60 output range. Worth checking in the same pass.
    "wnba_over_under",
    "wnba_spread",

    # mlb_over_under RE-PAUSED 2026-07-14 (Matt: "total runs model is 3-8, change
    # this poor record"). The under-skew watch item (flagged at the 2026-07-04
    # unpause and in sessions 92/95b/101) has MATERIALIZED. Honest-era live record
    # (>= 2026-07-05, current model + NaN-line fix) is 3-8 / -529u on 11 picks —
    # and it's NOT variance: across all 38 honest-era scored games the model's mean
    # P(over) is 0.454 while the realized over rate is 0.500 and games averaged 9.32
    # actual runs vs an 8.59 line. The active model v20260704_104508 was trained on
    # 2019-2024+2026 THROUGH JUNE ONLY — it has never seen a July 2026 game, so it's
    # anchored to a lower run environment than the summer actually is. NOT a
    # threshold problem (0.59/0.07 is on the flat plateau of the 203-bet 2025 OOS
    # sweep). Fix = the §27 retrain now including settled July data
    # (2019-2024+2026, holdout 2025). Paused meanwhile so we stop betting the
    # confirmed-mispriced model. UNPAUSE only after the retrain lands AND a fresh
    # 2025 OOS threshold sweep on the new model. Cut (0.59/0.07) kept in the dicts
    # below for the unpause.
    "mlb_over_under",

    # mlb_prop_batter_hr UNPAUSED 2026-06-20: the -66.6% that justified the pause
    # was a SETTLEMENT ARTIFACT — every HR pick settled at the -110 fallback because
    # DK's HR odds weren't being ingested (The Odds API serves them under
    # batter_home_runs_alternate, which we now request + remap). At the real
    # +250..+500 prices, HR's ~18% hit rate is break-even-to-positive, and the
    # scorer now applies a +EV edge filter when the line is priced (prob-only
    # fallback when DK omits it). HR stays LIVE by direction — re-pause only if it
    # still loses on REAL-odds settled picks.
}

# Fallback for models not listed above.
ACTION_MIN_PROB: float = float(os.environ.get("ACTION_MIN_PROB", 0.65))
ACTION_MIN_EDGE: float = float(os.environ.get("ACTION_MIN_EDGE", 0.14))
MAX_KELLY_FRACTION: float   = float(os.environ.get("MAX_KELLY_FRACTION",   0.05))
# Kelly multiplier: fraction of full Kelly to bet. Lowered from 0.25 → 0.10 (2026-05-04)
# because quarter-Kelly always exceeded the 5% cap (picks were all flat-bet at 5%).
# Tenth-Kelly keeps bets at 2-4% of bankroll, letting edge size drive differentiation.
KELLY_MULTIPLIER: float     = float(os.environ.get("KELLY_MULTIPLIER",      0.10))
# Edges above this magnitude are almost certainly model noise — filter them out
MAX_EDGE_CAP: float         = float(os.environ.get("MAX_EDGE_CAP",         0.20))

# Per-model stake multiplier applied AFTER Kelly sizing (and after the 5% cap).
# 1.0 = full Kelly-sized bet; <1.0 dials the stake down without touching the edge
# math. Use for high-variance / low-hit markets where a cold streak would otherwise
# dominate the bankroll. HR overs hit only ~17% of the time even at the best cut
# (they're longshots), so quarter-stake them. Models not listed bet at 1.0.
MODEL_BET_SIZE_MULTIPLIER: dict = {
    "mlb_prop_batter_hr": 0.25,   # 2026-06-28: hard, low-hit longshot — smaller bet (Matt)
}

# Per-model floor on the acceptable DK price (American odds). A pick whose DK
# odds are JUICIER than this floor (more negative, e.g. -165 < -140) never fires
# a BET — it scores as a NONE row instead, exactly like the dead-zone. Prob/edge
# math is untouched; this is a price-quality gate on top of it.
#
# 2026-07-11 (Matt: "implement this where it helps"): a -140 cap was first swept
# across a few models' full-outcome records and applied selectively (pitcher_k,
# batter_rbi, batter_walks, batter_runs) — those props' value lived at lighter
# prices and the heavy-juice tail bled.
#
# 2026-07-22 (Matt: "on any prop bets for MLB or WNBA, don't recommend model picks
# with a betting line over -140"): promoted to a BLANKET rule — EVERY MLB and WNBA
# player-prop model now carries the -140 floor, not just the swept few. A prop
# priced juicier than -140 (e.g. -150, -165) never fires a BET; it scores as a
# NONE row instead. Game markets (ML/totals/spreads/F5) and NBA/UFC/NHL/golf are
# unchanged — the rule is MLB + WNBA props only.
# Notes: mlb_prop_batter_hr is prob-only plus-money (over 0.5 HR at +250..+500), so
# the floor never blocks it — listed for completeness. NULL/absent DK price is
# never blocked (prob-only fallbacks keep firing). Models not listed have no floor.
MODEL_MIN_ODDS: dict = {
    # MLB pitcher props
    "mlb_prop_pitcher_k":     -140,
    "mlb_prop_pitcher_hits":  -140,
    "mlb_prop_pitcher_er":    -140,
    "mlb_prop_pitcher_outs":  -140,
    "mlb_prop_pitcher_walks": -140,
    # MLB batter props
    "mlb_prop_batter_hits":   -140,
    "mlb_prop_batter_tb":     -140,
    "mlb_prop_batter_hr":     -140,  # prob-only plus-money — floor never blocks
    "mlb_prop_batter_rbi":    -140,
    "mlb_prop_batter_runs":   -140,  # unpaused 2026-08-09 — floor is part of the +24.6%/40 cut
    "mlb_prop_batter_sb":     -140,
    "mlb_prop_batter_walks":  -140,
    # WNBA player props
    "wnba_prop_player_points":   -140,
    "wnba_prop_player_rebounds": -140,
    "wnba_prop_player_assists":  -140,
    "wnba_prop_player_threes":   -140,
    "wnba_prop_player_pra":      -140,
}

# Per-model BET edge thresholds (override the global default above).
# Derived from 2024 OOS backtest sweep: higher thresholds filter to higher-quality picks.
# Revisit after each retrain — edge distributions shift as features are added.
MODEL_EDGE_THRESHOLDS: dict = {
    "mlb_moneyline":            0.11,   # 2026-07-04: reverted to v20260413 model, 0.72/0.11 = 21-6 +29.5% live
    "mlb_over_under":           0.07,   # 2026-07-11 tightened (fewer picks): 0.59/0.07 = 203 bets 60.4% +16.3% on 2025 OOS
    "mlb_runline":              0.11,   # 2026-07-02 CORRECTION: the 06-28 0.55/0.10 "+14.9%" was a view sign bug (actually -20.6%). Corrected optimum 0.68/0.11 = 19 bets 13-6 +20.0%
    "mlb_f5_moneyline":         0.07,   # 2026-06-26 sweep: 0.67/0.07 = 105 bets +9.86% (more picks + higher ROI than 0.71/0.0)
    "mlb_f5_over_under":        0.15,   # DISABLED — DK does not carry totals_1st_5_innings
    "mlb_f5_runline":           0.15,   # DISABLED — DK does not carry spreads_1st_5_innings
    "nhl_moneyline":            0.05,   # placeholder — tune after 50+ settled picks
    "nhl_moneyline_regulation": 0.05,
    "nhl_over_under":           0.05,
    "nhl_puckline":             0.05,
    "nfl_wind_totals":          0.03,   # mirrors the wind card's own MIN_EDGE gate (§28)
    "nfl_opener_spread":        0.00,   # card gates on |dev| >= 1.0; edge >= 0 drops juice-eaten quotes
    # Prop models — re-optimized 2026-06-20 from settled-pick sweep (see ACTION_THRESHOLDS for per-model rationale + caveats)
    "mlb_prop_pitcher_k":        0.06,  # 2026-06-20: 71%/6% +17.1%
    "mlb_prop_pitcher_hits":     0.12,  # NO winning cut — retraining
    "mlb_prop_pitcher_er":       0.08,   # 2026-06-21 ≥10% target: 0.61/0.08 +11.1%/81
    "mlb_prop_pitcher_outs":     0.12,   # 2026-06-21 full-outcome
    "mlb_prop_pitcher_walks":    0.08,   # 2026-06-21 full-outcome
    "mlb_prop_batter_hits":      0.17,  # 2026-06-28 full-outcome: 0.78/0.17 = 77 bets +8.3% (UNPAUSED)
    "mlb_prop_batter_tb":        0.17,  # 2026-06-20: 83%/17% +3.2%
    "mlb_prop_batter_hr":        0.0,   # 2026-06-20: real DK HR odds now ingested (batter_home_runs_alternate) — +EV filter when priced (edge>=0), prob-only fallback when DK omits the line; keeps it live, removes -EV bets
    "mlb_prop_batter_rbi":       0.16,  # 2026-06-21 cut + -140 floor (2026-07-11): capped +7.3%/36
    "mlb_prop_batter_runs":      0.16,   # UNPAUSED 2026-08-09 — with -140 floor grades +24.6%/40
    "mlb_prop_batter_sb":        0.10,  # NO winning cut — needs feature work
    "mlb_prop_batter_walks":     0.14,   # 2026-06-21 RE-SWEEP: 0.45/0.14 = 65 bets +5.3%
    # WNBA — placeholder; retune from 2025 holdout backtest sweep.
    "wnba_moneyline":            0.04,  # 2026-07-02 sweep: 0.64/0.04 = 17 bets 14-3 +31.9% (old 0.66/0.12 placeholder fired 3 bets all season)
    "wnba_over_under":           0.06,   # 2026-07-19 OOS sweep (see ACTION_THRESHOLDS)
    "wnba_spread":               0.10,   # 2026-07-19 OOS sweep
    "wnba_prop_player_points":   0.17,  # PAUSED 2026-07-11 — no positive cut on the 2x sample
    "wnba_prop_player_rebounds": 0.08,  # 2026-07-11 re-sweep: KEPT — grid ROI max (+5.6%/78)
    "wnba_prop_player_assists":  0.08,  # 2026-07-11 re-sweep: KEPT — ROI max (+19.3%/44)
    "wnba_prop_player_threes":   0.12,  # PAUSED 2026-07-11 — no winning cut
    "wnba_prop_player_pra":      0.16,  # PAUSED 2026-07-11 — no winning cut
    # NBA — placeholder; tune after live odds accumulate.
    "nba_moneyline":             0.12,
    "nba_over_under":            0.12,
    "nba_spread":                0.12,
    "nba_prop_player_points":    0.08,
    "nba_prop_player_rebounds":  0.08,
    "nba_prop_player_assists":   0.08,
    "nba_prop_player_threes":    0.08,
    "nba_prop_player_pra":       0.08,
    "nba_prop_player_blocks":    0.08,
    "nba_prop_player_steals":    0.08,
    "nba_prop_player_turnovers": 0.08,
    "nba_prop_player_dd":        0.0,    # prob-only — edge ignored at runtime
    # UFC — placeholder; tune after 50+ settled picks.
    "ufc_moneyline":         0.08,
    "ufc_total_rounds":      0.08,
    "ufc_method_of_victory": 0.0,   # prob-only — edge ignored at runtime
    # GOLF — placeholder; tune after 50+ settled picks (market-relative scale).
    "golf_outright":  0.015,
    "golf_top10":     0.05,
    "golf_top20":     0.05,
    "golf_make_cut":  0.05,
    "golf_matchup":   0.05,
    # Live (in-play) — placeholder; in-play markets carry heavier vig, so the
    # edge floor starts higher than the pre-game equivalents.
    "mlb_live_win_prob":   0.10,
    "mlb_live_total_runs": 0.10,
    "mlb_live_runline":    0.10,
}

# Per-model minimum model probability to generate a BET signal.
# Moneyline markets run at a lower floor to surface more picks.
MODEL_PROB_THRESHOLDS: dict = {
    "mlb_moneyline":            0.72,   # 2026-07-04: reverted to v20260413 model, 0.72/0.11 = 21-6 +29.5% live
    "mlb_over_under":           0.59,   # 2026-07-11 tightened (fewer picks): 0.59/0.07 = 203 bets 60.4% +16.3% on 2025 OOS
    "mlb_runline":              0.68,   # 2026-07-02 CORRECTION: the 06-28 0.55/0.10 "+14.9%" was a view sign bug (actually -20.6%). Corrected optimum 0.68/0.11 = 19 bets 13-6 +20.0%
    "mlb_f5_moneyline":         0.67,   # 2026-06-26 sweep: 0.67/0.07 = 105 bets 65.6% +9.86% (more picks + higher ROI than 0.71/0.0)
    "mlb_f5_over_under":        0.65,   # DISABLED — DK does not carry these markets
    "mlb_f5_runline":           0.65,   # DISABLED — DK does not carry these markets
    "nhl_moneyline":            0.55,
    "nhl_moneyline_regulation": 0.40,   # 3-way market — lower per-side prob
    "nhl_over_under":           0.55,
    "nhl_puckline":             0.55,
    "nfl_wind_totals":          0.52,   # ~breakeven at -110; calibrated probs run 0.56-0.60 (§28)
    "nfl_opener_spread":        0.55,   # pooled validated ATS is 0.5818 flat (§28 opener)
    # Prop models — re-optimized 2026-06-20 from settled-pick sweep (see ACTION_THRESHOLDS for per-model rationale + caveats)
    "mlb_prop_pitcher_k":        0.71,  # 2026-06-20: 71%/6% +17.1%
    "mlb_prop_pitcher_hits":     0.65,  # NO winning cut — retraining
    "mlb_prop_pitcher_er":       0.61,   # 2026-06-21 ≥10% target: 0.61/0.08 +11.1%/81
    "mlb_prop_pitcher_outs":     0.5,   # 2026-06-21 full-outcome
    "mlb_prop_pitcher_walks":    0.6,   # 2026-06-21 full-outcome
    "mlb_prop_batter_hits":      0.78,  # 2026-06-28 full-outcome: 0.78/0.17 = 77 bets +8.3% (UNPAUSED)
    "mlb_prop_batter_tb":        0.83,  # 2026-06-20: 83%/17% +3.2%
    "mlb_prop_batter_hr":        0.225,  # 2026-06-26 STRICTER: 0.20→0.225 best-record cut (17.2% hit vs 15.4%, ~66% fewer picks). P(HR) caps ~0.29; model degrades above 0.23 (overfit top). See ACTION_THRESHOLDS note.
    "mlb_prop_batter_rbi":       0.47,  # 2026-06-21 cut + -140 floor (2026-07-11): capped +7.3%/36
    "mlb_prop_batter_runs":      0.47,   # UNPAUSED 2026-08-09 — with -140 floor grades +24.6%/40
    "mlb_prop_batter_sb":        0.18,  # NO winning cut — needs feature work
    "mlb_prop_batter_walks":     0.45,   # 2026-06-21 RE-SWEEP: 0.45/0.14 = 65 bets +5.3%
    # WNBA — placeholder; retune from 2025 holdout backtest sweep.
    "wnba_moneyline":            0.64,  # 2026-07-02 sweep: 0.64/0.04 = 17 bets 14-3 +31.9% (old 0.66/0.12 placeholder fired 3 bets all season)
    "wnba_over_under":           0.60,   # 2026-07-19 OOS sweep
    "wnba_spread":               0.60,   # 2026-07-19 OOS sweep
    "wnba_prop_player_points":   0.58,  # PAUSED 2026-07-11 — no positive cut on the 2x sample
    "wnba_prop_player_rebounds": 0.69,  # 2026-07-11 re-sweep: KEPT — grid ROI max (+5.6%/78)
    "wnba_prop_player_assists":  0.69,  # 2026-07-11 re-sweep: KEPT — ROI max (+19.3%/44)
    "wnba_prop_player_threes":   0.64,  # PAUSED 2026-07-11 — no winning cut
    "wnba_prop_player_pra":      0.67,  # PAUSED 2026-07-11 — no winning cut
    # NBA — placeholder; tune after live odds accumulate.
    "nba_moneyline":             0.66,
    "nba_over_under":            0.66,
    "nba_spread":                0.66,
    "nba_prop_player_points":    0.60,
    "nba_prop_player_rebounds":  0.60,
    "nba_prop_player_assists":   0.60,
    "nba_prop_player_threes":    0.60,
    "nba_prop_player_pra":       0.60,
    "nba_prop_player_blocks":    0.60,
    "nba_prop_player_steals":    0.60,
    "nba_prop_player_turnovers": 0.60,
    "nba_prop_player_dd":        0.55,   # prob-only — P(double-double) for stars ~0.4-0.7
    # UFC — placeholder; tune after 50+ settled picks.
    "ufc_moneyline":         0.65,
    "ufc_total_rounds":      0.62,
    "ufc_method_of_victory": 0.65,
    # GOLF — placeholder; tune after 50+ settled picks (market-relative scale).
    "golf_outright":  0.03,
    "golf_top10":     0.15,
    "golf_top20":     0.25,
    "golf_make_cut":  0.65,
    "golf_matchup":   0.55,
    # Live (in-play) — placeholder; tune after 50+ settled live picks.
    "mlb_live_win_prob":   0.65,
    "mlb_live_total_runs": 0.65,
    "mlb_live_runline":    0.65,
}

# ── Live (In-Play) Betting ────────────────────────────────────────────────────
# Phase 1: game-state poller polls MLB live feed for each in-progress game on
# this cadence. Free API — no Odds API credits consumed.
LIVE_POLL_INTERVAL_SEC: int  = int(os.environ.get("LIVE_POLL_INTERVAL_SEC", 15))
# Window in which we treat a game as "live": 15 min before scheduled first pitch
# (warmup updates can move lines) through final out.
LIVE_PREGAME_BUFFER_MIN: int = int(os.environ.get("LIVE_PREGAME_BUFFER_MIN", 15))
# Trigger orchestrator debounce — never more than one FG odds fetch per game
# inside this window (3-run innings still produce only one line-move opportunity).
LIVE_FG_DEBOUNCE_SEC: int    = int(os.environ.get("LIVE_FG_DEBOUNCE_SEC", 60))
# Hard kill switch — orchestrator stops dispatching Odds API calls if today's
# in-play burn would exceed this. Default 1000 (safe for the first live runs:
# ~3 credits/fetch, ~300-600 on a realistic evening). Set LIVE_DAILY_CREDIT_CAP=0
# in .env to run uncapped once you trust the burn, or raise it per your tier.
LIVE_DAILY_CREDIT_CAP: int   = int(os.environ.get("LIVE_DAILY_CREDIT_CAP", 1000))
# In-play odds older than this are stale — the live scorer skips rather than
# score against a line the book has since moved.
LIVE_ODDS_MAX_AGE_SEC: int   = int(os.environ.get("LIVE_ODDS_MAX_AGE_SEC", 300))
# Live game-state snapshots older than this mean the poller has stopped —
# don't score from a frozen state.
LIVE_STATE_MAX_AGE_SEC: int  = int(os.environ.get("LIVE_STATE_MAX_AGE_SEC", 300))

# Live (in-play) model registry — kept SEPARATE from MODELS so the pre-game
# scorer/trainer/backtester never pick these up. Each entry:
# model_id → (sport, market, model_type, description).
#   binary  → XGBClassifier + Platt; predict_proba[1] = P(outcome)
#   poisson → XGBRegressor count:poisson; predict = expected count REMAINING
LIVE_MODELS = {
    "mlb_live_win_prob":   ("MLB", "h2h",     "binary",
                            "P(home wins) from in-game state + pre-game context"),
    "mlb_live_total_runs": ("MLB", "totals",  "poisson",
                            "Expected runs in the REMAINDER of the game"),
    "mlb_live_runline":    ("MLB", "spreads", "binary",
                            "P(home wins by 2+) — only scored vs a live -1.5 line"),
}

# ── F5 (First 5 Innings) ──────────────────────────────────────────────────────
# Synthetic F5 total line = full_game_total * F5_TOTAL_FACTOR.
# Calibrated 2026-05-08 from 26,443 historical games:
#   avg F5 total = 5.344 runs / avg FG total = 8.623 → factor = 0.6197
# Overridable via env var if recalibration is needed after more data accumulates.
F5_TOTAL_FACTOR: float = float(os.environ.get("F5_TOTAL_FACTOR", 0.62))

# ── Early Season ──────────────────────────────────────────────────────────────
MIN_GAMES_BASELINE: int = int(os.environ.get("MIN_GAMES_BASELINE", 10))

# ── Return-from-Injury Ramp ───────────────────────────────────────────────────
RETURN_RAMP = {
    "early": float(os.environ.get("RETURN_RAMP_EARLY", 0.70)),  # games 1-2
    "mid":   float(os.environ.get("RETURN_RAMP_MID",   0.85)),  # games 3-5
    "full":  float(os.environ.get("RETURN_RAMP_FULL",  1.00)),  # games 6+
}

# ── Scheduling ────────────────────────────────────────────────────────────────
PIPELINE_RUN_TIME: str = os.environ.get("PIPELINE_RUN_TIME", "07:00")

# ── Sport Configuration ───────────────────────────────────────────────────────
SPORTS = {
    "MLB": {
        "odds_api_key":  "baseball_mlb",
        "seasons":       list(range(2019, 2026)),
        "train_seasons": list(range(2019, 2025)),  # 2019–2024 train (bumped 2026-06-06 — pre-clock 2019-23 window was stale; see docs/retrain_2026_plan.md)
        "test_season":   2025,                      # 2025 held out
        "sbr_dir":       ROOT / "data/raw/datawarehouse/mlb",
    },
    "NHL": {
        "odds_api_key":  "icehockey_nhl",
        "seasons":       list(range(2019, 2026)),
        "train_seasons": list(range(2019, 2025)),  # 2019–2024 train
        "test_season":   2025,                      # 2025 held out
        "sbr_dir":       ROOT / "data/raw/datawarehouse/nhl",
    },
    "WNBA": {
        "odds_api_key":  "basketball_wnba",
        # Season label = year of play (like MLB). WNBA runs May–Sept.
        "seasons":       list(range(2019, 2026)),
        "train_seasons": list(range(2019, 2025)),  # 2019–2024 train
        "test_season":   2025,                      # 2025 held out
        "sbr_dir":       ROOT / "data/raw/datawarehouse/wnba",
    },
    "NBA": {
        "odds_api_key":  "basketball_nba",
        # Season label = ENDING year (like NHL): season 2025 = the 2024-25 season,
        # which spans Oct 2024 – Jun 2025. The stats ingestor converts our int
        # season → the nba_api "YYYY-YY" string. Backfill team-stat snapshots are
        # stamped {season-1}-09-01 (before any Oct game) so the ASOF feature
        # lookup always finds an in-season row.
        "seasons":       list(range(2019, 2026)),
        "train_seasons": list(range(2019, 2025)),  # 2019–2024 train (=2018-19 .. 2023-24)
        "test_season":   2025,                      # 2025 (=2024-25) held out
        "sbr_dir":       ROOT / "data/raw/datawarehouse/nba",
    },
    "UFC": {
        "odds_api_key":  "mma_mixed_martial_arts",
        # Season label = calendar year of the event. Fight history scraped from
        # ufcstats.com back to 2010 so career rolling stats have depth; models
        # train on 2012+ (fighters need ≥3 prior UFC fights to produce a row).
        "seasons":       list(range(2010, 2027)),
        "train_seasons": list(range(2012, 2025)),  # 2012–2024 train
        "test_season":   2025,                      # 2025 held out
        "sbr_dir":       ROOT / "data/raw/datawarehouse/ufc",
    },
    "GOLF": {
        # odds_api_key is None on purpose — golf odds + stats come from DataGolf,
        # not The Odds API. The odds_ingestor's default sport list never includes
        # GOLF, so this key is never read for golf; it exists only to satisfy the
        # SPORTS schema (test_config.py requires the key to be present).
        "odds_api_key":  None,
        # Season label = calendar year. DataGolf round-level history + strokes
        # gained go back to ~2017; models train on 2017–2024, hold out 2025.
        "seasons":       list(range(2017, 2027)),
        "train_seasons": list(range(2017, 2025)),  # 2017–2024 train
        "test_season":   2025,                      # 2025 held out
        "sbr_dir":       ROOT / "data/raw/datawarehouse/golf",
    },
}

# ── Models Registry ───────────────────────────────────────────────────────────
# Each entry: model_id → (sport, market, description)
MODELS = {
    "mlb_moneyline":            ("MLB", "h2h",      "Home team wins (full game)"),
    "mlb_over_under":           ("MLB", "totals",   "Total runs over/under"),
    "mlb_runline":              ("MLB", "spreads",  "Favored team covers -1.5 run line"),
    "mlb_f5_moneyline":         ("MLB", "h2h_1st_5_innings",      "Home leads after 5 innings"),
    "mlb_f5_over_under":        ("MLB", "totals_1st_5_innings",   "Total runs over/under through 5 innings"),
    "mlb_f5_runline":           ("MLB", "spreads_1st_5_innings",  "Home covers F5 spread"),
    "nhl_moneyline":            ("NHL", "h2h",      "Home team wins incl. OT/SO"),
    "nhl_moneyline_regulation": ("NHL", "h2h_3way", "Regulation result: Home / Draw / Away"),
    "nhl_over_under":           ("NHL", "totals",   "Total goals over/under"),
    "nhl_puckline":             ("NHL", "spreads",  "Favored team covers -1.5 puck line"),
    "wnba_moneyline":           ("WNBA", "h2h",     "Home team wins"),
    "wnba_over_under":          ("WNBA", "totals",  "Total points over/under"),
    "wnba_spread":              ("WNBA", "spreads", "Home team covers the spread"),
    "nba_moneyline":            ("NBA",  "h2h",     "Home team wins"),
    "nba_over_under":           ("NBA",  "totals",  "Total points over/under"),
    "nba_spread":               ("NBA",  "spreads", "Home team covers the spread"),
    # UFC — fighter mapped to the Odds API "home_team" slot is our home side.
    "ufc_moneyline":            ("UFC", "h2h",    "Home-slot fighter wins the fight"),
    "ufc_total_rounds":         ("UFC", "totals", "Fight duration over/under the round line"),
    "ufc_method_of_victory":    ("UFC", "method", "Fight ends by Decision / KO-TKO / Submission (3-class)"),
    # GOLF — per-player markets on one tournament games row (picks carry player_id).
    # All four markets price against real DK odds via DataGolf's betting-tools feed.
    "golf_outright":            ("GOLF", "win",                "Player wins the tournament"),
    "golf_top10":               ("GOLF", "top_10",             "Player finishes in the top 10"),
    "golf_top20":               ("GOLF", "top_20",             "Player finishes in the top 20"),
    "golf_make_cut":            ("GOLF", "make_cut",           "Player makes the cut"),
    "golf_matchup":             ("GOLF", "matchup_tournament", "Player A beats Player B over the tournament"),
}

# ── The Odds API ──────────────────────────────────────────────────────────────
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
ODDS_API_REGIONS = "us"
ODDS_API_BOOKMAKER = "draftkings"   # the book the models SCORE against (unchanged)

# Line shopping: the top-5 US books fetched for GAME markets (h2h / spreads /
# totals / F5 ML) AND player props, so the app can show the price at whichever
# book the user actually bets. The model still scores against ODDS_API_BOOKMAKER
# — every other book here is DISPLAY-ONLY (see the scorer/feature-engine reads,
# which all hard-filter to draftkings).
#
# The Odds API counts the `bookmakers` param as ONE region, so adding books here
# does NOT increase credit cost — on either the bulk game call or the per-event
# prop calls. The cost is row volume, not credits.
#
# draftkings stays first so it's always present. If a key is ever rejected by the
# API, the ingestors fall back to draftkings-only rather than losing the fetch
# (see _books_param_with_fallback in odds_ingestor).
#
# Caesars is `williamhill_us` on The Odds API (NOT `caesars`) — verify against
#   curl ".../v4/sports/baseball_mlb/odds?apiKey=$ODDS_API_KEY&regions=us&markets=h2h" \
#     | jq -r '.[0].bookmakers[].key' | sort -u
# before changing this list.
LINE_SHOP_BOOKMAKERS = [
    b.strip().lower()
    for b in os.environ.get(
        "LINE_SHOP_BOOKMAKERS",
        "draftkings,fanduel,betmgm,williamhill_us,espnbet",
    ).split(",")
    if b.strip()
]
# Comma-joined for the Odds API `bookmakers` query param.
ODDS_API_BOOKMAKERS_PARAM = ",".join(dict.fromkeys(["draftkings", *LINE_SHOP_BOOKMAKERS]))

# Retention for line-shop (non-DraftKings) odds snapshots — see data/prune_odds.py.
# Both odds tables are append-only (~21 snapshots per proposition per day), but the
# ONLY readers of non-DK rows are the DISTINCT ON all-books views, which return just
# the newest row per book. So non-DK history is written once and never read, and at
# 5 books it would add ~2.7 GB/month. This bounds it to a flat working set.
# draftkings and sbr_consensus are NEVER pruned (CLV / line movement / training).
# Raise this before building any feature that needs non-DK history (e.g. "did the
# best book beat DK at close?") — pruned rows are gone permanently.
PRUNE_NON_DK_KEEP_DAYS = int(os.environ.get("PRUNE_NON_DK_KEEP_DAYS", "2"))

# ── Action Network (Public Betting Splits) ────────────────────────────────────
# Unofficial JSON scoreboard endpoint — the same data that powers
# actionnetwork.com/mlb/public-betting. No API key required. The ingestor is
# best-effort: any failure is logged and the pipeline continues (same resilient
# pattern as the ESPN hidden API and the F5 odds fetch). Override via env if the
# endpoint or book ids change.
ACTION_NETWORK_BASE: str = os.environ.get(
    "ACTION_NETWORK_BASE",
    "https://api.actionnetwork.com/web/v2/scoreboard",
)
# Book id(s) whose bet/money splits represent "the public". 15 is Action
# Network's consensus pseudo-book. Comma-separated — the first book that carries
# split data for a game wins.
ACTION_NETWORK_BOOK_IDS: str = os.environ.get("ACTION_NETWORK_BOOK_IDS", "15")

# ── ESPN Injury API ───────────────────────────────────────────────────────────
ESPN_INJURY_URLS = {
    "MLB": "https://sports.core.api.espn.com/v2/sports/baseball/leagues/mlb/teams/{team_id}/injuries",
    "NHL": "https://sports.core.api.espn.com/v2/sports/hockey/leagues/nhl/teams/{team_id}/injuries",
    "WNBA": "https://sports.core.api.espn.com/v2/sports/basketball/leagues/wnba/teams/{team_id}/injuries",
    "NBA": "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/teams/{team_id}/injuries",
}

# ESPN team ID maps — ESPN uses numeric IDs
ESPN_MLB_TEAM_IDS = {
    "ARI": 29, "ATL": 15, "BAL": 1,  "BOS": 2,  "CHC": 16, "CWS": 4,
    "CIN": 17, "CLE": 5,  "COL": 27, "DET": 6,  "HOU": 18, "KC":  7,
    "LAA": 3,  "LAD": 19, "MIA": 28, "MIL": 21, "MIN": 9,  "NYM": 21,
    "NYY": 10, "OAK": 11, "PHI": 22, "PIT": 23, "SD":  25, "SEA": 12,
    "SF":  26, "STL": 24, "TB":  30, "TEX": 13, "TOR": 14, "WSH": 20,
}

# NOTE: these ESPN NHL ids are unverified and have known duplicates — verify
# on a machine with ESPN access before relying on NHL injury resolution.
# `UTA` is the canonical relocated-franchise id (Arizona → Utah), matching the
# UTA convention used in the ingestor/odds/SBR maps. injury_adj degrades to
# neutral when a team id is wrong/missing, so a stale id is non-fatal.
ESPN_NHL_TEAM_IDS = {
    "ANA": 25, "UTA": 53, "BOS": 1,  "BUF": 2,  "CAR": 26, "CBJ": 29,
    "CGY": 20, "CHI": 16, "COL": 21, "DAL": 25, "DET": 17, "EDM": 22,
    "FLA": 13, "LAK": 26, "MIN": 30, "MTL": 8,  "NJD": 1,  "NSH": 18,
    "NYI": 2,  "NYR": 3,  "OTT": 9,  "PHI": 4,  "PIT": 5,  "SEA": 55,
    "SJS": 28, "STL": 19, "TBL": 14, "TOR": 10, "VAN": 23, "VGK": 54,
    "WSH": 15, "WPG": 52,
}

# WNBA canonical 3-letter abbreviations (used by odds + stats ingestors and the
# ESPN map below). 15 franchises as of 2026 (Portland Fire + Toronto Tempo expansion).
WNBA_TEAMS = [
    "ATL", "CHI", "CON", "DAL", "GSV", "IND", "LV",
    "LA", "MIN", "NY", "PDX", "PHX", "SEA", "TOR", "WAS",
]

# The Odds API returns full team names; normalise to WNBA_TEAMS abbrevs.
WNBA_ODDS_API_MAP = {
    "Atlanta Dream":          "ATL",
    "Chicago Sky":            "CHI",
    "Connecticut Sun":        "CON",
    "Dallas Wings":           "DAL",
    "Golden State Valkyries": "GSV",
    "Indiana Fever":          "IND",
    "Las Vegas Aces":         "LV",
    "Los Angeles Sparks":     "LA",
    "Minnesota Lynx":         "MIN",
    "New York Liberty":       "NY",
    "Portland Fire":          "PDX",
    "Phoenix Mercury":        "PHX",
    "Seattle Storm":          "SEA",
    "Toronto Tempo":          "TOR",
    "Washington Mystics":     "WAS",
}

# ESPN numeric team IDs for WNBA injuries — OFFLINE FALLBACK ONLY.
# The injury ingestor resolves ids LIVE from ESPN's WNBA teams endpoint at runtime
# (_fetch_wnba_espn_team_ids), joining on full team name via WNBA_ODDS_API_MAP, so
# all 15 franchises — including the 2025/2026 expansion teams (Golden State
# Valkyries, Portland Fire, Toronto Tempo) — resolve automatically with no
# hardcoded numeric ids. This static map is used only when that endpoint is
# unreachable (e.g. the sandbox allowlist blocks ESPN).
#
# These 12 long-established franchises use ESPN's standard WNBA team ids (ATL=20,
# LV=17, NY=9 independently verified; the rest are the stable ESPN ids for these
# clubs). GSV/PDX/TOR are intentionally omitted here — they're filled by the live
# resolver. The injuries endpoint is league-scoped (.../leagues/wnba/teams/{id}/
# injuries), so any unknown id just 404s and unmapped teams are skipped — both
# degrade gracefully (no wrong-team data is ever fetched).
ESPN_WNBA_TEAM_IDS = {
    "ATL": 20,   # Atlanta Dream
    "CHI": 19,   # Chicago Sky
    "CON": 18,   # Connecticut Sun
    "DAL": 3,    # Dallas Wings
    "IND": 5,    # Indiana Fever
    "LV":  17,   # Las Vegas Aces
    "LA":  6,    # Los Angeles Sparks
    "MIN": 8,    # Minnesota Lynx
    "NY":  9,    # New York Liberty
    "PHX": 11,   # Phoenix Mercury
    "SEA": 14,   # Seattle Storm
    "WAS": 16,   # Washington Mystics
}

# NBA canonical 3-letter abbreviations (used by odds + stats ingestors and the
# ESPN map below). 30 franchises. These match the stats.nba.com / ESPN scheme.
NBA_TEAMS = [
    "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
    "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
]

# The Odds API returns full team names; normalise to NBA_TEAMS abbrevs.
# (Note: The Odds API lists the Clippers as "LA Clippers", Lakers as
# "Los Angeles Lakers".)
NBA_ODDS_API_MAP = {
    "Atlanta Hawks":          "ATL",
    "Boston Celtics":         "BOS",
    "Brooklyn Nets":          "BKN",
    "Charlotte Hornets":      "CHA",
    "Chicago Bulls":          "CHI",
    "Cleveland Cavaliers":    "CLE",
    "Dallas Mavericks":       "DAL",
    "Denver Nuggets":         "DEN",
    "Detroit Pistons":        "DET",
    "Golden State Warriors":  "GSW",
    "Houston Rockets":        "HOU",
    "Indiana Pacers":         "IND",
    "LA Clippers":            "LAC",
    "Los Angeles Clippers":   "LAC",
    "Los Angeles Lakers":     "LAL",
    "Memphis Grizzlies":      "MEM",
    "Miami Heat":             "MIA",
    "Milwaukee Bucks":        "MIL",
    "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans":   "NOP",
    "New York Knicks":        "NYK",
    "Oklahoma City Thunder":  "OKC",
    "Orlando Magic":          "ORL",
    "Philadelphia 76ers":     "PHI",
    "Phoenix Suns":           "PHX",
    "Portland Trail Blazers": "POR",
    "Sacramento Kings":       "SAC",
    "San Antonio Spurs":      "SAS",
    "Toronto Raptors":        "TOR",
    "Utah Jazz":              "UTA",
    "Washington Wizards":     "WAS",
}

# ESPN numeric team IDs for NBA injuries. Unlike the WNBA list (which has
# expansion-team churn and is resolved live), the 30 NBA franchises are stable,
# so this static map is the primary source; the injury ingestor still overlays
# any ids it can resolve live from ESPN's NBA teams endpoint as a self-heal.
ESPN_NBA_TEAM_IDS = {
    "ATL": 1,  "BOS": 2,  "BKN": 17, "CHA": 30, "CHI": 4,  "CLE": 5,
    "DAL": 6,  "DEN": 7,  "DET": 8,  "GSW": 9,  "HOU": 10, "IND": 11,
    "LAC": 12, "LAL": 13, "MEM": 29, "MIA": 14, "MIL": 15, "MIN": 16,
    "NOP": 3,  "NYK": 18, "OKC": 25, "ORL": 19, "PHI": 20, "PHX": 21,
    "POR": 22, "SAC": 23, "SAS": 24, "TOR": 28, "UTA": 26, "WAS": 27,
}

# ── Player Props ─────────────────────────────────────────────────────────────
# All DK prop markets available via The Odds API event-level endpoint.
# Pitcher props use Poisson regression (count projection).
# Batter SB uses logistic (binary — rare event). HR switched to Poisson (v2).
PROP_MARKETS_PITCHER = [
    "pitcher_strikeouts",
    "pitcher_hits_allowed",
    "pitcher_earned_runs",
    "pitcher_outs",
    "pitcher_walks",
]
PROP_MARKETS_BATTER = [
    "batter_hits",
    "batter_total_bases",
    "batter_home_runs",      # poisson (v2 — pitcher HR/9, gb%, park factor, platoon)
    "batter_rbis",
    "batter_runs_scored",
    "batter_stolen_bases",   # logistic (binary)
    "batter_walks",
]
PROP_MARKETS_ALL = PROP_MARKETS_PITCHER + PROP_MARKETS_BATTER

# WNBA player prop markets (The Odds API basketball player-prop keys).
# All modelled as Poisson count projections.
PROP_MARKETS_WNBA = [
    "player_points",
    "player_rebounds",
    "player_assists",
    "player_threes",
    "player_points_rebounds_assists",   # PRA combo
]

# NBA player prop markets (The Odds API basketball player-prop keys).
# Counts are Poisson; player_double_double is a binary Yes/No market.
PROP_MARKETS_NBA = [
    "player_points",
    "player_rebounds",
    "player_assists",
    "player_threes",
    "player_points_rebounds_assists",   # PRA combo
    "player_blocks",
    "player_steals",
    "player_turnovers",
    "player_double_double",             # binary Yes/No (logistic, prob-only)
]

# Prop model IDs — one per market. Trained in Phase 2 after game-log backfill.
PROP_MODELS = {
    "mlb_prop_pitcher_k":    ("MLB", "pitcher_strikeouts",  "poisson",  "Priority 1"),
    "mlb_prop_pitcher_hits": ("MLB", "pitcher_hits_allowed","poisson",  ""),
    "mlb_prop_pitcher_er":   ("MLB", "pitcher_earned_runs", "poisson",  ""),
    "mlb_prop_pitcher_outs": ("MLB", "pitcher_outs",        "poisson",  ""),
    "mlb_prop_pitcher_walks":("MLB", "pitcher_walks",       "poisson",  ""),
    "mlb_prop_batter_hits":  ("MLB", "batter_hits",         "poisson",  ""),
    "mlb_prop_batter_tb":    ("MLB", "batter_total_bases",  "poisson",  ""),
    "mlb_prop_batter_hr":    ("MLB", "batter_home_runs",    "poisson",  "v2: pitcher HR/9, gb%, park factor, platoon"),
    "mlb_prop_batter_rbi":   ("MLB", "batter_rbis",         "poisson",  ""),
    "mlb_prop_batter_runs":  ("MLB", "batter_runs_scored",  "poisson",  ""),
    "mlb_prop_batter_sb":    ("MLB", "batter_stolen_bases", "logistic", "rare event"),
    "mlb_prop_batter_walks": ("MLB", "batter_walks",        "poisson",  ""),
    # WNBA player props — Poisson count projection (one model per market).
    "wnba_prop_player_points":   ("WNBA", "player_points",                   "poisson", ""),
    "wnba_prop_player_rebounds": ("WNBA", "player_rebounds",                 "poisson", ""),
    "wnba_prop_player_assists":  ("WNBA", "player_assists",                  "poisson", ""),
    "wnba_prop_player_threes":   ("WNBA", "player_threes",                   "poisson", ""),
    "wnba_prop_player_pra":      ("WNBA", "player_points_rebounds_assists",  "poisson", "P+R+A combo"),
    # NBA player props — 5 WNBA-equivalents (Poisson) + 4 NBA-specific markets.
    # Double-double is a binary Yes/No outcome (DK juices it heavily) → logistic +
    # prob-only, same treatment as the MLB HR prop. The rest are Poisson counts.
    "nba_prop_player_points":    ("NBA", "player_points",                   "poisson",  ""),
    "nba_prop_player_rebounds":  ("NBA", "player_rebounds",                 "poisson",  ""),
    "nba_prop_player_assists":   ("NBA", "player_assists",                  "poisson",  ""),
    "nba_prop_player_threes":    ("NBA", "player_threes",                   "poisson",  ""),
    "nba_prop_player_pra":       ("NBA", "player_points_rebounds_assists",  "poisson",  "P+R+A combo"),
    "nba_prop_player_blocks":    ("NBA", "player_blocks",                   "poisson",  ""),
    "nba_prop_player_steals":    ("NBA", "player_steals",                   "poisson",  ""),
    "nba_prop_player_turnovers": ("NBA", "player_turnovers",                "poisson",  ""),
    "nba_prop_player_dd":        ("NBA", "player_double_double",            "logistic", "double-double (binary, prob-only)"),
}

# Baseball Savant leaderboard CSV base URL
SAVANT_BASE_URL = "https://baseballsavant.mlb.com/leaderboard/custom"

# ── UFC ───────────────────────────────────────────────────────────────────────
# ufcstats.com is the historical + weekly results source (no official free API).
# Static site, no auth. The ingestor is polite (300ms between requests) and all
# parsers are isolated + fixture-tested so markup changes are a localized fix.
# NOTE (2026-06-11): ufcstats.com moved behind a browser-level Cloudflare
# challenge that even cloudscraper can't solve, so the PRIMARY data path is now
# the ufc_csv_loader (below). The HTML scraper is kept as a documented plan B.
UFCSTATS_BASE_URL: str = os.environ.get("UFCSTATS_BASE_URL", "http://ufcstats.com")

# Primary UFC data source: the Greco1899/scrape_ufc_stats GitHub mirror — a
# maintained repo whose own scheduled scraper keeps 1:1 CSV exports of
# ufcstats.com current (updated weekly after each card). The CSVs preserve the
# ufcstats fight/fighter ids in their URL columns, so rows are identical to
# what the HTML scraper would have produced. UFC_CSV_DIR (optional) points at a
# local directory of the same CSVs for offline/manual use.
UFC_CSV_BASE_URL: str = os.environ.get(
    "UFC_CSV_BASE_URL",
    "https://raw.githubusercontent.com/Greco1899/scrape_ufc_stats/main")
UFC_CSV_DIR: str = os.environ.get("UFC_CSV_DIR", "")

# ── NFL (standalone wind-totals card — §28) ──────────────────────────────────
# Canonical nflverse games.csv (Lee Sharpe's nfldata), updated nightly in
# season — the results source for settling nfl_wind_totals picks. Same
# raw.githubusercontent host the UFC CSV mirror already reaches from the
# Railway worker.
NFLVERSE_GAMES_URL: str = os.environ.get(
    "NFLVERSE_GAMES_URL",
    "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv")

# nflverse weekly per-player stats (one row per player per game) — feeds
# nfl_player_game_log for the mobile Stats tab NFL leaderboard. Served as
# GitHub release assets on the nflverse-data repo, tag `stats_player`,
# asset `stats_player_week_{season}.csv` (verified live 2026-08-19: 2024 and
# 2025 both 200; a not-yet-published season 404s, which the ingestor treats
# as a clean no-op — that is the off-season gate).
NFLVERSE_PLAYER_STATS_URL_TMPL: str = os.environ.get(
    "NFLVERSE_PLAYER_STATS_URL_TMPL",
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "stats_player/stats_player_week_{season}.csv")

# How many seasons back the self-healing NFL player-stats ingest keeps loaded
# (current season + this many prior). The first run after deploy backfills
# them all; later runs only refresh the current season.
NFL_PLAYER_STATS_BACKFILL_SEASONS: int = int(
    os.environ.get("NFL_PLAYER_STATS_BACKFILL_SEASONS", "3"))

# The Odds API fighter name → ufcstats.com fighter name overrides.
# Fighter identity is matched by slugified full name (lowercase, accents
# stripped, punctuation removed), which handles almost everyone. Add an entry
# here when the books and ufcstats disagree on a name (nicknames, "Jr.",
# transliteration differences). Keys are Odds API names, values ufcstats names.
UFC_NAME_ALIASES: dict = {
    # "Alexander Volkanovski": "Alex Volkanovski",   # (example — not real)
}

# Synthetic round-total lines used when DK round-total odds are absent
# (training, backtest, and prob-only live scoring). The most common DK lines:
# 2.5 rounds for 3-round bouts, 4.5 for 5-round bouts.
UFC_SYNTHETIC_TOTAL_3RD: float = 2.5
UFC_SYNTHETIC_TOTAL_5RD: float = 4.5

# UFC events are weekly, and DK prices fights days in advance — score fights up
# to this many days ahead so picks are visible before fight day (MLB/WNBA stay
# same-day only). Each scoring run re-deletes and re-scores unstarted UFC picks
# in this window, so signal flips are handled the same way as same-day picks.
UFC_SCORE_AHEAD_DAYS: int = int(os.environ.get("UFC_SCORE_AHEAD_DAYS", "7"))

# ── GOLF / DataGolf ───────────────────────────────────────────────────────────
# Golf data + odds come from the DataGolf "Scratch Plus" API (feeds.datagolf.com).
# A single API key unlocks: historical round-level scoring + strokes gained
# (/historical-raw-data/*), the current field (/field-updates), player ids
# (/get-player-list), skill rankings (/preds/get-dg-rankings) and — crucially —
# LIVE DraftKings odds for every weekly PGA event across all four markets via
# the betting-tools feed (/betting-tools/outrights, /betting-tools/matchups).
# The Odds API is NOT used for golf (it only carries the 4 majors, outrights only).
DATAGOLF_API_KEY: str  = os.environ.get("DATAGOLF_API_KEY", "")
DATAGOLF_BASE_URL: str = os.environ.get("DATAGOLF_BASE_URL", "https://feeds.datagolf.com")

# ── Kalshi (prediction markets — P3 evaluation, read-only spike only) ──────────
# CFTC-regulated event-contract exchange. Of interest because winners can't be
# "limited" the way sportsbooks limit sharp accounts. NOT wired into the pipeline
# — see docs/prediction_markets_eval.md and scripts/verify_kalshi.py. Public
# market-data reads (GET /events, /markets) generally need no key; a key is only
# required for trading/portfolio endpoints we don't use.
KALSHI_API_BASE: str = os.environ.get(
    "KALSHI_API_BASE", "https://api.elections.kalshi.com/trade-api/v2"
)
KALSHI_API_KEY: str = os.environ.get("KALSHI_API_KEY", "")

# A player must have at least this many measured rounds of history before the
# feature engine will produce a row (the MIN_UFC_FIGHTS / early-season analog —
# rolling strokes-gained is unstable below ~5 events / 20 rounds).
MIN_GOLF_ROUNDS: int = int(os.environ.get("MIN_GOLF_ROUNDS", "20"))

# Tournaments are weekly and DK prices the field days in advance — score picks
# up to this many days before the first round (same look-ahead pattern as UFC).
# Each scoring run re-deletes and re-scores picks for tournaments that have not
# yet teed off, so signal flips are handled like same-day picks.
GOLF_SCORE_AHEAD_DAYS: int = int(os.environ.get("GOLF_SCORE_AHEAD_DAYS", "7"))

# Number of historical player pairs sampled per event to build the matchup
# training set (deterministic — seeded by dg_event_id+season). Kept modest so a
# few dominant pairs can't swamp the binary target.
GOLF_MATCHUP_PAIRS_PER_EVENT: int = int(os.environ.get("GOLF_MATCHUP_PAIRS_PER_EVENT", "15"))

# Team events (alternate-shot / four-ball formats — e.g. the Zurich Classic) have
# no individual finishing positions and must be excluded from ingestion + scoring.
# Matched by DataGolf event name (case-insensitive substring).
GOLF_TEAM_EVENT_MARKERS = ("zurich classic",)

# ── Directories ───────────────────────────────────────────────────────────────
MODELS_DIR    = ROOT / "models" / "saved"
NOTEBOOKS_DIR = ROOT / "notebooks"
RAW_DATA_DIR  = ROOT / "data" / "raw"

# Ensure critical directories exist at import time
for _d in [
    MODELS_DIR,
    RAW_DATA_DIR / "datawarehouse/mlb",
    RAW_DATA_DIR / "datawarehouse/nhl",
    RAW_DATA_DIR / "datawarehouse/wnba",
    RAW_DATA_DIR / "datawarehouse/nba",
    RAW_DATA_DIR / "datawarehouse/ufc",
    RAW_DATA_DIR / "datawarehouse/golf",
]:
    _d.mkdir(parents=True, exist_ok=True)
