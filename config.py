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

# ── Bankroll & sizing ─────────────────────────────────────────────────────────
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

# When True (default), LIVE (in-play) picks lock at their FIRST BET signal per
# (game, model) lane. The live loops (models/live_scorer.py for MLB,
# ncaaf_live/gameday.py for NCAAF) delete-and-rescore each game's live rows
# every pass — which meant a live BET could be re-priced, flipped, or destroyed
# outright (the NCAAF totals lane closes in Q4, erasing any standing pick before
# it could settle). With the lock, the first BET a lane fires is the bet of
# record at its line and price: that lane is excluded from later passes' deletes
# and inserts, it survives lane closes/OT, and it is what settles into the model
# record. Unlocked lanes keep churning (the board can post freely — only
# signals lock). Complementary AVOID rows written in the same pass as the
# locking BET freeze with it (same proposition, other side). Set to "0" to
# revert to delete-and-rescore (the pick standing at game end settles).
LOCK_LIVE_PICKS_AT_FIRST_SIGNAL: bool = os.environ.get("LOCK_LIVE_PICKS_AT_FIRST_SIGNAL", "1") == "1"

# Track-a-bet line-change alert: a tracked (game-level) bet pushes a notification
# when the DK price on its side moves at least this many implied-prob percentage
# points away from the price the user locked, in either direction. Re-notifies
# once per additional whole-multiple of this threshold (≈4pp, ≈8pp, …) so a
# steaming line escalates without spamming. See tracking/push_notifier.py.
LINE_CHANGE_NOTIFY_PP: float = float(os.environ.get("LINE_CHANGE_NOTIFY_PP", 4.0))

# ── Discord ───────────────────────────────────────────────────────────────────
# Picks are pushed to a Discord server via incoming WEBHOOKS (no bot, no gateway
# connection, no hosting) — one channel per sport. Set only the sports you want:
#   DISCORD_WEBHOOK_MLB, DISCORD_WEBHOOK_NFL, DISCORD_WEBHOOK_NBA,
#   DISCORD_WEBHOOK_NHL, DISCORD_WEBHOOK_WNBA, DISCORD_WEBHOOK_UFC,
#   DISCORD_WEBHOOK_GOLF, DISCORD_WEBHOOK_NCAAF
# A sport with no webhook is SKIPPED and its signals are NOT marked as sent, so
# adding that channel later still delivers the rest of the day's picks.
# (Listed literally rather than derived from SPORTS — that registry is defined
# further down this file, and a webhook name is a stable, user-facing env var.)
DISCORD_SPORTS: tuple = ("MLB", "NHL", "WNBA", "NBA", "UFC", "GOLF", "NCAAF", "NFL")
DISCORD_WEBHOOKS: dict = {
    sport: url for sport in DISCORD_SPORTS
    if (url := os.environ.get(f"DISCORD_WEBHOOK_{sport}", "").strip())
}

# Catch-all for any sport without its own channel. Leave unset to post nothing
# for unmapped sports rather than dumping every sport into one channel.
DISCORD_WEBHOOK_DEFAULT: str = os.environ.get("DISCORD_WEBHOOK_DEFAULT", "").strip()

# Dedicated in-play channel. The live board re-scores every ~10 minutes during a
# slate, so it is worth separating from the pre-game picks. Falls back to the
# sport's channel when unset.
DISCORD_WEBHOOK_LIVE: str = os.environ.get("DISCORD_WEBHOOK_LIVE", "").strip()

# Channel for the morning results recap (cross-sport, so it needs its own home).
# Falls back to DISCORD_WEBHOOK_DEFAULT.
DISCORD_WEBHOOK_RESULTS: str = os.environ.get("DISCORD_WEBHOOK_RESULTS", "").strip()

# Free-pick-of-the-day channel: ONE pick per day, picked at random from the
# day's qualifying signals (NFL preferred once the season starts, else any
# sport). Deliberately has NO fallback to DISCORD_WEBHOOK_DEFAULT — this is a
# distinct, more public audience than the full feed, so an unset variable must
# post nothing rather than leak the free pick into the catch-all channel.
DISCORD_WEBHOOK_FREE: str = os.environ.get("DISCORD_WEBHOOK_FREE", "").strip()

# Operations channel for the heartbeat watchdog (tracking/heartbeat_watchdog.py).
# Deliberately has NO fallback to any member-facing channel — RESULTS and the
# per-sport channels are read by subscribers, and an infrastructure alert dumped
# there is both noise to them and a leak of internal state. An unset variable
# means the watchdog can SEE a problem and cannot REPORT it, so it says so in
# its own return value and logs at CRITICAL rather than failing silently.
DISCORD_WEBHOOK_OPS: str = os.environ.get("DISCORD_WEBHOOK_OPS", "").strip()

# How stale the newest pipeline_runs row may get before the watchdog calls it a
# stall, in minutes. The tightest real cadence is the evening refresh at every
# 10 minutes; the loosest gap a HEALTHY system produces is the quiet stretch
# between the last evening pass (~11:50pm ET) and the overnight pass at 12:17am
# ET, plus the pass's own runtime. 90 minutes clears that comfortably while
# still catching an overnight break before the 6am pipeline would have.
WATCHDOG_STALE_MINUTES: int = int(os.environ.get("WATCHDOG_STALE_MINUTES", 90))

# How long the watchdog waits before REPEATING an alert for a condition that is
# still true. Without this a 9-hour outage posts ~36 identical messages at the
# 15-minute cadence and the channel becomes unreadable exactly when it matters.
WATCHDOG_RENOTIFY_MINUTES: int = int(os.environ.get("WATCHDOG_RENOTIFY_MINUTES", 360))

# Sports the free pick prefers, in order. NFL first so the free pick becomes an
# NFL pick automatically the moment the season produces signals; until then it
# falls through to whatever else qualified that day.
DISCORD_FREE_PICK_PRIORITY: tuple = ("NFL",)

# Max embeds posted to one channel in a single run. Bounds the blast radius when
# a webhook is added mid-day with a full slate already locked; anything over the
# cap is left un-ledgered and posts on the next refresh pass.
DISCORD_MAX_EMBEDS_PER_RUN: int = int(os.environ.get("DISCORD_MAX_EMBEDS_PER_RUN", 20))

# ── Price requirement ─────────────────────────────────────────────────────────
# A BET must be placeable: no real book price, no bet. When True, any pick whose
# dk_odds is NULL is downgraded BET -> NONE (dead-zone treatment: still written
# and tracked, never bet, never settled for P&L).
#
# This closes the "synthetic edge" hole. Some scoring paths score against an
# INVENTED baseline when no market exists -- ufc_method_of_victory against a 1/3
# uniform prior over its three classes, UFC round totals and the F5 markets
# against a 0.50 fair line. Those produce an `edge` that is not an edge over any
# market, yet lands in the same column, renders identically, and feeds
# confidence_tier -- so a method pick showed "+33.0% edge / HIGH" for a bet that
# could not be placed at any price.
#
# Set REQUIRE_DK_PRICE=0 to restore the old prob-only behaviour.
REQUIRE_DK_PRICE: bool = os.environ.get("REQUIRE_DK_PRICE", "1") not in ("0", "false", "False")

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
    "mlb_over_under":     {"min_prob": 0.5, "min_edge": 0.04},  # 2026-08-30 UNPAUSED (mike) — calibrated sweep + time split, scripts/calibrated_threshold_sweep
    "mlb_runline":        {"min_prob": 0.68, "min_edge": 0.11},  # 2026-07-02 CORRECTION: the 2026-06-28 "broad plateau" (0.55/0.10 = 48-41 +14.9%) was computed on a SIGN BUG in v_model_full_outcome_record — away-side picks were graded with (away-home)+scored_line instead of (away-home)-scored_line, flipping every one-run game. Corrected (validated 30/31 vs stored settlements): 0.55/0.10 is 35-56 -20.6%; every prob floor below 0.68 is negative at volume. Corrected optimum: 0.68/0.11 = 19 bets 13-6 +20.0% (robust pocket 0.68-0.70 x 0.09-0.12 all +6..+20%; 9 away +1.5 / 10 away -1.5). Small sample. 2026-07-04: model swapped to v20260704_121650 (2019-2024+2026, holdout 2025, CalErr 2.95% vs v8 5.56%); cut CARRIED OVER UNVALIDATED (2025 has no runline prices; 2026 now in-sample — in-sample check at this cut: 5-0, all away +1.5). Expect very low volume (~1-2 picks/month). 2026-08-21 DORMANT — NOT paused anywhere (config, model_action_thresholds and the mobile fallback all have it live), it simply cannot reach its own 0.68 prob floor any more: the model's max probability across ALL of August 2026 was 0.625, and the last BET fired 2026-07-19. Cause is the two live-input repairs, not threshold drift — weekly max_p goes 0.757 (wk 06-29) -> 0.554 (wk 07-06), a cliff exactly at the 2026-07-04 bullpen-freeze catch-up (bullpen_ip_last1/3 had been 0.0 = "fully rested" for every live-scored game since 4/14) and the 2026-07-05 NaN-line fix (spread_home was NaN at every live spreads prediction). So the pre-July probabilities that this 0.68 cut was chosen on were inflated by out-of-distribution inputs, and the +21.7%/20-bet record it shows was banked in that broken-input era. DO NOT simply loosen the floor to make picks reappear: on the honest era (>= 2026-07-05, 354 graded picks at real DK prices, matview grading validated 63/63 and the sign convention re-validated 138/138 vs stored settlements) the model is -6.93% overall and BOTH sides are negative (away +1.5 -6.5%/199, home -1.5 -7.5%/155 — so even the away-only pocket session 74 identified has stopped working). No cell in the 0.45-0.68 x 0.00-0.20 grid is a plateau: the best, 0.51/0.02 = 34 bets 17-17 +8.6%, is a coin flip whose neighbours flip negative one step away (0.52/0.02 = -4.6%) — shipping it would repeat the session-74/87 noise-fitting mistake. FIX = retrain on 2019-2025 with 2026 HELD OUT (2026 is the only season carrying real DK runline prices — 1,694 priced games vs zero for 2019-2025 — so it is the only honest OOS ROI basis this model has ever had; the current cut was itself "carried over UNVALIDATED"), then re-cut with scripts/mlb_runline_sweep.py (or the "Runline Threshold Sweep" Action). Cut left UNCHANGED meanwhile
    # 2026-09-03 (mike): 0.74/0.00 -> 0.58/0.02 on the retrained artifact
    # v20260903_163809 (mlb_pitcher_stats leak repair, docs/team_stats_leak.md).
    #
    # WHY THE OLD CUT COULD NOT STAY. It fired ZERO bets. Scored across 2026,
    # the retrained model's MAXIMUM probability is 0.734 -- not few sides over
    # 0.74, none. That is mlb_runline's failure mode: a model that cannot reach
    # its own floor publishes nothing while looking live here, in
    # model_action_thresholds and in the mobile fallback. And f5 is PAPER ONLY
    # (a retrain resets §2's gate), so a cut that fires nothing can never reach
    # the >=50 settled picks the gate needs -- 0.74 did not park f5, it
    # stranded it. It was also swept on CALIBRATED probabilities while the
    # scorer decides on RAW ones (models/scorer.py: "DISPLAY ONLY for now"),
    # so it was the wrong number on the wrong scale.
    #
    # WHAT THIS CUT IS. scripts/mlb_f5_sweep on 2026 -- the only season with DK
    # first-five prices AND the season held out of the retrain, scored on RAW
    # probabilities, the scale the scorer actually uses:
    #     0.58/0.02   76 bets   45-31   59.2%   +3.52%   halves +0.99 / +6.18
    # ~5.4 bets/week, average price -134, worst -200. Those are the numbers WITH
    # config.MODEL_MIN_ODDS applied inside the sweep, which is the only honest
    # way to quote them: a cell measured on bets below the floor is measured on
    # bets the scorer refuses. Unfloored it reads 77 bets / +4.09%; the floor
    # removes exactly one bet here, but the 2026-08-31 slate had a sweep that
    # skipped the floor recommend four cuts the corrected one withdrew.
    #
    # THE EVIDENCE IS WEAK, AND THAT IS ON THE RECORD RATHER THAN BURIED.
    # One of 50 non-thin cells in the grid is positive, which is what no edge
    # looks like against vig (average DK implied 53.2%). The cell FAILS the
    # plateau test 0 of 8 -- the isolated-peak shape sessions 74 and 87 had to
    # retract. It survives a time split, which is the only check it passes.
    # Claude recommended pausing f5 instead; mike chose to ship it, and the
    # reasoning is sound on its own terms: f5 is paper-only, paper picks risk
    # nothing, and the paper phase IS the validation mechanism -- a cut that
    # fires is the only way to generate the record that decides.
    #
    # KILL CRITERION, pre-committed so it is not re-argued later: review at 50
    # settled picks. If flat-bet ROI is negative there, PAUSE -- do not widen
    # the bar looking for a better cell, because the grid already says there
    # isn't one. Clearing §2 needs positive ROI and calibration <=5% as well.
    "mlb_f5_moneyline":   {"min_prob": 0.58, "min_edge": 0.02},
    # mlb_f5_over_under and mlb_f5_runline: DISABLED — DK does not carry these markets.
    # mlb_prop_batter_hr + mlb_prop_batter_rbi RETIRED 2026-09-02 (matt) -- see the RETIRED block above PROP_MODELS.
    "mlb_prop_batter_runs":   {"min_prob": 0.62, "min_edge": 0.10},  # 2026-08-31 (mike): 0.47/0.16 -> 0.62/0.10 on the floor-corrected calibrated sweep = 27 bets 18-9 +25.6%, and the halves are +25.6% / +25.6% -- the flattest split on the board. ~9.9/wk. Supersedes the 2026-08-09 unpause cut, which was chosen on raw probabilities.
    "mlb_prop_batter_hits":   {"min_prob": 0.78, "min_edge": 0.17},  # 2026-06-28 full-outcome re-sweep: 0.78/0.17 = 77 bets 56-21 +8.3% (genuine combo found — UNPAUSED from the 2026-06-21 pause)
    "mlb_prop_batter_tb":     {"min_prob": 0.83, "min_edge": 0.17},  # 2026-06-21 RE-SWEEP: NO winning cut (best -4.2%) — least-bad, RETRAIN candidate
    "mlb_prop_batter_walks":  {"min_prob": 0.45, "min_edge": 0.14},  # 2026-06-21 full-outcome RE-SWEEP: 0.45/0.14 = 65 bets +5.3% (only positive pocket; high-edge/low-prob)
    "mlb_prop_pitcher_outs":  {"min_prob": 0.5, "min_edge": 0.12},  # 2026-08-31 (mike) UNPAUSED at its EXISTING cut -- the floor correction is what changed, not the numbers. On the uncorrected sweep this failed the time split; with the -140 floor applied (26.1% of its rows) the same cell grades 79 bets 46-33 +20.7%, ~25.1/wk, the largest volume on the board. The halves are +0.7% then +40.2%: positive throughout, so it survives, but the first half is break-even and the verdict rests on the second. FIRST TO RE-CHECK.
    "mlb_prop_pitcher_k":     {"min_prob": 0.58, "min_edge": 0.08},  # 2026-08-31 (mike): 0.71/0.06 -> 0.58/0.08 on the floor-corrected calibrated sweep = 25 bets 15-10 +14.8%, +11.3% then +18.0% by half, ~5.4/wk.
    "mlb_prop_pitcher_er":    {"min_prob": 0.61, "min_edge": 0.08},  # 2026-06-21 ≥10% target: 0.61/0.08 = 81 bets +11.1% (CI [-8.3,+30.5])
    "mlb_prop_pitcher_hits":  {"min_prob": 0.54, "min_edge": 0.08},  # 2026-08-31 (mike) UNPAUSED. The clearest evidence in the repo that the defect was the probability, not the model: on raw numbers this is the worst model on the board (-27.9% ROI, claims 70.5% and delivers 38.5% over 65 bets), and on calibrated numbers at 0.54/0.08 it grades 95 bets 49-46 +11.0%, +13.2% then +8.7% by half, ~19.8/wk. Identical before and after the price-floor correction -- its floor blocks only 23.5% and none of them mattered.
    "mlb_prop_pitcher_walks": {"min_prob": 0.6, "min_edge": 0.08},  # 2026-06-21 full-outcome: +6.3%/66
    # Binary/rare-event models — prob scale differs from Poisson
    "mlb_prop_batter_sb":     {"min_prob": 0.18, "min_edge": 0.10},  # NO winning cut — already current-window v2; needs feature work, not retrain
    # WNBA — placeholder thresholds; retune from the 2025 holdout backtest sweep.
    "wnba_moneyline":            {"min_prob": 0.5, "min_edge": 0.06},  # 2026-08-31 (mike): 0.64/0.04 -> 0.50/0.06 on the calibrated sweep = 25 bets 18-7 +24.3%, halves +9.1% then +47.1%. AT THE 25-BET FLOOR -- the thinnest of the twelve shipped today, and the first to re-check. Supersedes the 2026-07-02 full-outcome sweep (0.64/0.04 = 17 bets 14-3 +31.9%), which was chosen on raw probabilities.
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
    "wnba_prop_player_rebounds": {"min_prob": 0.62, "min_edge": 0.0},  # 2026-08-31 (mike): 0.75/0.09 -> 0.62/0.00 on the floor-corrected calibrated sweep = 30 bets 19-11 +12.5%, ~7/wk. Yesterday's 0.75/0.09 unpause came from the SAME sweep before the price floor was applied, where this read 22-5 +33.2%; the corrected halves are +1.5% then +22.2%, so the first half is barely break-even. Watch this one.
    "wnba_prop_player_assists":  {"min_prob": 0.5, "min_edge": 0.10},  # 2026-08-31 (mike): 0.69/0.08 -> 0.50/0.10 on the floor-corrected calibrated sweep = 57 bets 35-22 +23.1%, +13.9% then +29.8% by half, ~14/wk. The 2026-07-11 note declined a volume cell on RAW probabilities; this one is chosen on corrected ones, which is a different question.
    "wnba_prop_player_threes":   {"min_prob": 0.706, "min_edge": 0.026},  # 2026-08-30 UNPAUSED (mike) — calibrated sweep + time split, scripts/calibrated_threshold_sweep
    "wnba_prop_player_pra":      {"min_prob": 0.68, "min_edge": 0.16},  # 2026-08-30 UNPAUSED (mike) — calibrated sweep + time split, scripts/calibrated_threshold_sweep
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
    "nfl_opener_spread":        {"min_prob": 0.52, "min_edge": 0.00},
    # Live (in-play) — conservative placeholders; tune after 50+ settled live picks.
    # LIVE MLB, re-cut 2026-08-29 (mike) from the settled live record (70 BETs).
    # Sweep over every settled live BET, real DK prices, flat $100:
    #   total_runs  0.65/0.10  41 bets 24-17  +8.2%
    #               0.68/0.14  17 bets 12-5  +27.9%  <- all 8 neighbours positive
    #   win_prob    NEGATIVE at every cut (0.65/0.15 = -78.9% on 8) -> PAUSED
    #   runline     NEGATIVE at every cut (best 0.70/0.15 = -0.4%)  -> PAUSED
    # Totals is the only live model whose ROI RISES with both prob and edge;
    # the two binary models are severely overconfident (avg model prob 0.73-0.76
    # against a 36-40% realised win rate), which is what their 5.3%/5.9% holdout
    # CalErr was already warning about. 17 bets is thin and in-sample -- re-sweep
    # at ~50 settled totals picks.
    #
    # win_prob and runline were RETIRED 2026-08-30 (see LIVE_MODELS) -- a paused
    # model keeps scoring so its forward record can earn an unpause, and neither
    # of these can: the failure is calibration, not a cut, so more NONE rows at
    # the same overconfidence buy nothing. No thresholds because there is no
    # model left to threshold.
    "mlb_live_total_runs": {"min_prob": 0.7, "min_edge": 0.14},  # 2026-08-30 mike: live volume cut — see MODEL_MIN_EV + docs/live_betting.md
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
    # NCAAF (FBS) — PLACEHOLDER cuts, deliberately tighter than our other launch
    # defaults. A Saturday slate is ~60-80 FBS games, so a loose cut would fire
    # 30+ picks in one afternoon. Tune from the 2025 holdout sweep (Phase 4),
    # sliced by game_tier (P4 vs G5) and week bucket.
    # 2026-08-24 margin-regression model (scripts/ncaaf_margin_eval --fit):
    # min_prob is the OOS-residual-ECDF probability at the validated ±5.5-point
    # disagreement gate (140/261 = 53.6% on the 2025 holdout; --fit prints the
    # exact mapping — update this number to match its output). Edge floor 0.0
    # ON PURPOSE: the validated rule is the disagreement gate, not a price
    # filter. REAL MONEY from Week 1 (Matt skipped the paper gate 2026-08-27
    # after the 4-season outcome/edge scan confirmed the rule: 464 bets ~55.6%
    # +6.4% at -110, direction-symmetric, both halves). Still review at 50
    # settled picks — live DK totals must behave like the archive lines.
    # 0.55 floors the rule's flat validated prob (0.5810). The real filter is
    # the |dev| >= 1.0 gate plus the simultaneity/still-gettable preconditions,
    # all enforced in the scorer. Edge floor 0.0 on purpose: the validated rule
    # is the disagreement, not a price filter.
    "ncaaf_spread":     {"min_prob": 0.55, "min_edge": 0.0},
    # Premium opener tier, band [2.5, inf). Floors its own flat validated
    # prob (0.6047); the band, not the prob, is the filter.
    "ncaaf_spread_premium": {"min_prob": 0.58, "min_edge": 0.0},
    # NCAAF live lanes — placeholders mirroring ncaaf_live/serve.py; the
    # week-1 output is a CALIBRATION SET (no in-play edge has been measured).
    "ncaaf_live_win_prob": {"min_prob": 0.66, "min_edge": 0.10},  # 2026-08-30 mike: live volume cut — see MODEL_MIN_EV + docs/live_betting.md
    "ncaaf_live_total":    {"min_prob": 0.66, "min_edge": 0.12},  # 2026-08-30 mike: live volume cut — see MODEL_MIN_EV + docs/live_betting.md
    # 0.65 = P(over) at the validated +/-8.0 gate (--fit-totals prints it).
    # The scorer enforces |disagreement| >= 8.0 directly because the OOS
    # residuals are not centred, so a prob floor ALONE would imply an
    # asymmetric gate (over at +8, under at ~-5) and ship a looser rule on the
    # under side than anything validated. Edge floor 0.0 on purpose: the
    # validated rule is the disagreement gate, not a price filter.
    "ncaaf_over_under": {"min_prob": 0.65, "min_edge": 0.0},
    # moneyline also carries a -250 MODEL_MIN_ODDS floor — most of a CFB slate
    # is priced -1000 or worse and is not bettable at any edge.
    "ncaaf_moneyline":  {"min_prob": 0.62, "min_edge": 0.08},
    # ── NFL player props (2026-08-23) ──────────────────────────────────────
    # PLACEHOLDERS. Not tuned, and they cannot be tuned until prop prices
    # exist to grade against — the whole NFL prop family is in
    # PAUSED_MODELS for exactly that reason. Do not read these as a
    # calibrated cut. anytime_td's prob floor is lower because its base
    # rate is 27%, not 50%.
    # The market-relative rule (models/nfl_prop_market). ONE id across every
    # market it trades, because the validated result is a POOLED number over 954
    # bets — per-market splits were reported but never validated at volume, and
    # eight ids would each show a thin record inviting per-market cuts the
    # evidence does not support. The market travels on picks.prop_market, so
    # per-market visibility is a GROUP BY rather than eight registry entries.
    #
    # min_prob is 0: the model probability here is Pinnacle's de-vigged number,
    # which is often near 0.5 by construction — the edge is the whole signal,
    # and a probability floor would silently cut the rule's core.
    #
    # 5pp is PRE-COMMITTED. Greedy selection on 2023-24 picks 6pp and 6pp
    # returns -0.46% blind on 2025; 5pp replicated (+10.22% train, +10.76%
    # blind). Not to be chased. See docs/nfl_props_model.md §5c.
    #
    # Deliberately absent from PROP_MODELS: that registry drives training and
    # the artifact-coverage health check, and this is a rule with no artifact.
    # The WNBA market-relative rule (models/wnba_prop_market) — the NFL rule
    # ported 2026-08-31 after the model-first path was closed: the points
    # rebuild STOPped in both availability modes and 4 of 5 prop grids sit at
    # or under the vig, while the market-relative construction is the repo's
    # best validated edge (NFL: +10.2% train / +10.8% blind, 954 bets). ONE id
    # over the three markets Pinnacle quotes for WNBA (points/rebounds/assists
    # — it declines threes, which is itself information); the market travels on
    # picks.prop_market. min_prob 0 on purpose: model_probability is Pinnacle's
    # de-vigged number, near 0.5 by construction — the edge is the whole
    # signal. 5pp is PRE-COMMITTED from the NFL derivation (6pp chosen greedily
    # went negative blind); not to be chased. PAPER-FIRST: kill if no positive
    # blind month at >= 50 flags.
    "wnba_prop_market":           {"min_prob": 0.0, "min_edge": 0.05},
    "nfl_prop_market":            {"min_prob": 0.0, "min_edge": 0.05},
    "nfl_prop_pass_yards":         {"min_prob": 0.55, "min_edge": 0.05},
    "nfl_prop_pass_attempts":      {"min_prob": 0.55, "min_edge": 0.05},
    "nfl_prop_pass_completions":   {"min_prob": 0.55, "min_edge": 0.05},
    "nfl_prop_pass_tds":           {"min_prob": 0.55, "min_edge": 0.05},
    "nfl_prop_rush_yards":         {"min_prob": 0.55, "min_edge": 0.05},
    "nfl_prop_rush_attempts":      {"min_prob": 0.55, "min_edge": 0.05},
    "nfl_prop_rec_yards":          {"min_prob": 0.55, "min_edge": 0.05},
    "nfl_prop_receptions":         {"min_prob": 0.55, "min_edge": 0.05},
    "nfl_prop_rush_rec_yards":     {"min_prob": 0.55, "min_edge": 0.05},
    "nfl_prop_anytime_td":         {"min_prob": 0.3, "min_edge": 0.05},
    "nfl_prop_tackles_assists":    {"min_prob": 0.55, "min_edge": 0.05},
    "nfl_prop_sacks":              {"min_prob": 0.55, "min_edge": 0.05},
}

# Models where BET signal is decided by model probability alone (edge ignored).
# Use when the market is structurally illiquid/inefficient so DK prices don't
# anchor a meaningful edge — e.g. HR Over 0.5 where DK juices the over heavily
# and there is no real under market. Scorer skips the edge check; dashboard /
# Claude mobile SQL filters drop the edge clause for these models.
PROB_ONLY_MODELS: set = {
    # mlb_prop_batter_hr was the founding member (HR Over 0.5, no real under
    # market) until it was RETIRED 2026-09-02 -- see the block above PROP_MODELS.
    # Method-of-victory odds are not carried by The Odds API — the model's
    # 3-class probability alone decides the BET signal.
    "ufc_method_of_victory",
    # NBA double-double is a Yes/No market DK juices heavily (and there is no
    # real "No" market to fade) — decide on model probability alone.
    "nba_prop_player_dd",
}

# Models RETIRED — removed from their registry (MODELS / PROP_MODELS /
# LIVE_MODELS) outright, so nothing scores, trains or syncs a threshold row for
# them. Their picks stay in the DB and stay graded (§1c), but they are EXCLUDED
# FROM EVERY PUBLISHED TOTAL: the track-record views drop them through the
# model_action_thresholds join, and every Python or app aggregation that reads
# raw picks consults this set. It mirrors mobile/src/lib/thresholds.ts
# RETIRED_MODELS; keep the two in sync (tests/test_retired_models.py pins it).
#
# This is NOT PAUSED_MODELS: a paused model still scores NONE rows and keeps
# its cut for the unpause; a retired model has nothing left to pause and is
# gone from the registry. The two sets are disjoint by construction.
RETIRED_MODELS: frozenset = frozenset({
    # 2026-08-30 (matt): the two binary MLB live models. See LIVE_MODELS.
    "mlb_live_win_prob",
    "mlb_live_runline",
    # 2026-09-02 (matt): batter home runs + batter RBIs. See PROP_MODELS.
    "mlb_prop_batter_hr",
    "mlb_prop_batter_rbi",
})
# Models temporarily PAUSED — never emit a BET signal. They are still scored and
# written as NONE rows (so the website can still show the game), but with no
# recommended bet, no settlement, and zero bankroll risk. A paused model is also
# excluded from the mobile action filter and the public track-record views.
# Reversible: remove the model_id here (and clear its `paused` flag in the
# model_action_thresholds table) to re-enable.
# ── Per-model EV floor (expected value, not edge) ────────────────────────────
# EV = model_prob x decimal_odds - 1. Edge is prob minus implied and ignores the
# PAYOUT, so two picks with the same edge are not the same bet: at -200 you risk
# twice as much for the same return. This is the number to cut on when the ask
# is "only the best EV".
#
# Deliberately a GENERIC per-model dict rather than a live-only knob -- the same
# question ("is this a big enough return to be worth the exposure?") applies to
# every market, so any model can be given a floor here without new code. Absent
# = no floor.
#
# mlb_live_total_runs 0.30 -> 0.32 (2026-08-29, mike): re-swept on the settled
# live record with the finer grid the first sweep did not have.
#   >=0.26  34 bets  +5.2%
#   >=0.28  30       +6.8%
#   >=0.30  20 12-8 +15.3%
#   >=0.32  17 10-7 +14.1%   <- the aggressive end OF THE PLATEAU
#   >=0.34   9  5-4  +7.9%   <- collapses, and it is worse than 0.30
#   >=0.36   6  4-2 +30.3%   <- six bets, and nothing at all clears 0.40
# 0.30 and 0.32 are one plateau; everything above it is the sample running out.
# 0.34 halving the ROI on nine bets is the tell, and the 0.36 spike is noise at
# the very edge of the observed distribution, so it is not a floor, it is a
# boundary artifact. 0.32 is as aggressive as the evidence supports.
# ── Live edge band: upper bound ──────────────────────────────────────────────
# The live analogue of MAX_EDGE_CAP, kept SEPARATE from it even though the two
# currently hold the same number.
#
# They must not share a constant, because they guard different things. A
# pre-game price is stable for hours, so a huge edge there is a model claim. A
# live price is at most ~45 seconds old BY CONSTRUCTION -- measured 2026-08-29,
# The Odds API serves one cached in-play snapshot for ~44-46s and both its bulk
# and per-event endpoints return that identical cache (36/36 paired reads, same
# last_update, same line, same price). So a huge edge against a live line is
# usually evidence that OUR snapshot is behind the book, not that we found
# value. Sharing one constant means a future live tightening silently moves the
# pre-game cut too.
#
# 0.20 for mlb_live_total_runs, i.e. UNCHANGED, and that is a measurement not an
# oversight. NCAAF was tightened to 0.18 because its two largest edges were its
# two worst immediate line moves; MLB shows no such pattern -- ROI by edge
# bucket on the settled record is 0.16-0.18 = +17.3% (16 bets) and 0.18-0.20 =
# +5.7% (9), with the WORST bucket at the BOTTOM (0.10-0.12 = -63.5% on 5). A
# live MLB total moves 0-2 runs in ten minutes against 2-8 points for NCAAF, so
# the sport is an order of magnitude less exposed to the cache floor. Tightening
# here would remove profitable bets to solve a problem MLB does not have.
LIVE_MAX_EDGE_CAP: float = float(os.environ.get("LIVE_MAX_EDGE_CAP", 0.20))

MODEL_MIN_EV: dict = {
    # 0.32, set 2026-08-29 and RESTORED 2026-08-30 (mike) after a brief 0.28.
    #
    # The 0.28 came off a sweep table that averaged 08-29 (pre-floor, EVs down to
    # 0.178) with 08-30 (post-floor, every EV >= 0.320), which understated where
    # the floor already sat and made a LOOSENING look like a tightening. Flagged
    # at the time, applied as asked, reverted the same day. The lesson is the
    # table's, not the number's: a threshold sweep run across a day on which the
    # threshold itself changed is measuring two different models.
    "mlb_live_total_runs": 0.32,
    # NCAAF live, 2026-08-30. LEAST-BAD, EXPLICITLY UNVALIDATED -- 10 settled
    # bets from ONE Saturday (2026-08-29), which is a slate, not a record. Every
    # EV cut on that sample is still negative overall; these are the cells that
    # lose least while keeping more than one bet. Re-sweep after ~3 more
    # Saturdays and expect these numbers to move.
    "ncaaf_live_total": 0.22,
    "ncaaf_live_win_prob": 0.22,
}

# ── Live volume ceiling (bets per week) ──────────────────────────────────────
# What mike is willing to be shown, in bets per week per live model. NOT a
# runtime cap — nothing enforces it at score time. It is the constraint the
# recalibration recommender optimises UNDER (tracking/live_calibration.py): a
# cut that earns more ROI by making more bets is not an improvement if the
# volume was the complaint.
#
# Set 2026-08-30 (mike: "still too many live bets on MLB"). MLB live had gone
# from ~35% of games producing a bet to 100% when the first-signal lock landed
# on 08-29 -- ~63 bets/week at an unchanged threshold. prob >= 0.70 + EV >= 0.28
# projects ~28/week, so the ceiling is set just above that.
LIVE_MAX_BETS_PER_WEEK: dict = {
    "mlb_live_total_runs": 30,
    # NCAAF plays one day a week, so a "week" here is one Saturday slate.
    "ncaaf_live_total": 20,
    "ncaaf_live_win_prob": 10,
}

# ── Live signals per model per day ───────────────────────────────────────────
# A hard ceiling on how many live BETs one model may surface in a day, taken in
# the order they cross (the first qualifying signal locks; see
# LOCK_LIVE_PICKS_AT_FIRST_SIGNAL). Absent = uncapped, which is the state every
# model is in.
#
# EMPTY ON PURPOSE (2026-08-29, mike). mlb_live_total_runs carried a 1/day cap
# for one day. The cap was reaching for the wrong lever: the six-signal night it
# was written for came from a loose threshold with no EV floor at all, not from
# a missing ceiling. With EV >= 0.32 the settled record averages 1.21 signals a
# day and its BUSIEST day is 3 -- so a cap of 1 was throwing away real bets to
# solve a problem the floor had already solved.
#
# The mechanism stays because a cap is a guarantee and a threshold is only a
# hope about volume. If a model ever needs one again, add it here.
LIVE_MAX_SIGNALS_PER_DAY: dict = {
}

PAUSED_MODELS: set = {
    # 2026-08-31 (mike). UNPAUSED the same day it was paused, and the round trip
    # is the useful part of the record. TB ML F5 fired at -195 under a cut that
    # was legitimate but no longer described a profitable model (197 settled
    # BETs, -0.37% lifetime, May +0.4% / Jun +1.3% / Jul +6.5% / Aug -9.3%).
    # The morning's fix raised min_edge 0.07 -> 0.15 and paused it. The
    # afternoon's calibrated sweep showed the edge bar was aimed at the wrong
    # quantity: at 0.74/0.00 on CALIBRATED probabilities the model grades 33
    # bets 23-10 +5.7%, +6.9% then +4.6% by half. The defect was never the juice
    # -- bets at -160 or worse grade +3.85%/51 against -1.84%/146 for everything
    # cheaper -- it was 10-12pp of overconfidence from 0.65 up, which is exactly
    # the band a heavy-priced bet must come from. Correct the probability and
    # the cut works; widen the edge bar and you only bet less of the same
    # mistake. mlb_f5_moneyline is therefore LIVE again at 0.74/0.00, and is
    # only meaningful once the calibration map is promoted.
    #
    # 2026-08-31 (mike): PAUSED. Dormant since 2026-07-19 rather than broken --
    # it cannot reach its own 0.68 prob floor any more (max live probability
    # across August was 0.625), so it has been publishing nothing while looking
    # live in config, model_action_thresholds and the mobile fallback. The
    # calibrated sweep now says there is no cut to fix that with: nothing in the
    # grid clears 25 settled bets profitably on the corrected numbers, and on
    # the honest era (>= 2026-07-05, 354 graded picks) the model is -6.93% with
    # BOTH sides negative. Pausing states out loud what has been true for six
    # weeks; a dormant model that nobody paused is indistinguishable from a
    # broken feed. Unpause path is the retrain in the ACTION_THRESHOLDS note
    # (2019-2025, 2026 held out) followed by scripts/mlb_runline_sweep.py.
    "mlb_runline",
    # 2026-09-03 (mike): PAUSED. The pitcher-stats leak repair
    # (docs/team_stats_leak.md) removed the only thing holding this model up.
    # Walk-forward across 2019-2026 on the rebuilt tables, fixed params:
    #   2021 0.514  2022 0.516  2023 0.505  2024 0.519  2025 0.502  2026 0.486
    # Mean AUC 0.507, and the ONE honestly-featurised season lands at 0.486 --
    # BELOW A COIN FLIP. Zero of six folds clear 0.55. Its pre-rebuild
    # 0.547/0.573/0.574/0.569 was the leak in its entirety: `mlb_pitcher_stats`
    # held each starter's season-final ERA on every start, and this model reads
    # home_starter_era/away_starter_era directly.
    #
    # Unpause path is a REBUILT MODEL, not a threshold. No cut rescues a
    # classifier that does not rank -- moving a bar on a 0.50 AUC only changes
    # how many coin flips get bet.
    "mlb_over_under",
    # mlb_live_win_prob + mlb_live_runline were paused here 2026-08-29 (mike) and
    # RETIRED 2026-08-30 -- they are gone from LIVE_MODELS entirely, so there is
    # nothing left to pause. See the RETIRED block above LIVE_MODELS.
    # 2026-08-24: NCAAF kill criterion — binary classifiers held out at AUC
    # ~0.49-0.50 on a healthy 6,000+-row matrix, and the margin-regression
    # harness (scripts/ncaaf_margin_eval) also FAILED for totals. Moneyline was
    # already parked (-12% ROI / 17% CalErr). Both registry rows may still be
    # active with stale classifier artifacts — paused so neither can ever
    # surface a pick. ncaaf_spread stays LIVE on the margin-regression model.
    "ncaaf_moneyline",
    # ncaaf_over_under UNPAUSED 2026-08-25: replaced the dead AUC-0.49
    # classifier with a TOTAL-REGRESSION artifact (kind="total_regression",
    # scripts/ncaaf_margin_eval --fit-totals). It predicts the total from
    # fundamentals and bets only a >= 8.0-point disagreement with DK's live
    # total. Basis: walk-forward on CORRECTED snapshots, 4 test seasons, with
    # +/-8.0 independently the best gate in EVERY one of them --
    #   2022 116/206 56.3% +7.5% (did not inform the gate choice)
    #   2023  81/143 56.6% +8.1%
    #   2024  51/ 90 56.7% +8.2%
    #   2025  47/ 89 52.8% +0.8%
    #   pooled 295/528 55.9% +6.7%
    # HONEST CAVEAT: the pooled 95% CI is [51.6%, 60.1%] and does NOT clear the
    # 52.38% breakeven, and 2025 is both the weakest and the most recent
    # season. Four-season gate stability is the reason to run it; the interval
    # is the reason to size it small. Live from 2026-08-29 per Matt.
    # 2026-08-25: ncaaf_spread PAUSED too. Three independent reasons, any one
    # of which is sufficient:
    #  1. Its honest multi-season record is BELOW breakeven. The single-holdout
    #     2025 pass (53.6%) that shipped it did not replicate: walk-forward
    #     (--walk-forward) is 52.1% pooled / -0.5% ROI over 806 bets vs the
    #     52.38% -110 breakeven, and the per-season "best" gates scatter
    #     (2023 none / 2024 +/-4.0 / 2025 +/-5.5), which the harness itself
    #     calls the signature of a gate fitted to one season.
    #  2. Its ACTIVE model_registry row points at a binary CLASSIFIER
    #     (kind=None, holdout AUC ~0.49), not the margin-regression artifact
    #     the scorer's margin branch expects. `--fit` was never run, so no
    #     margin artifact exists anywhere.
    #  3. Every feature it consumes was built from ncaaf_team_stats snapshots
    #     that leaked postseason results into in-season rows (32.7% of all
    #     snapshots, fixed 2026-08-25 in cfbd_ingestor). Anything trained
    #     before that fix was trained on future information.
    # 2026-08-26: ncaaf_spread UNPAUSED, but it is NO LONGER the classifier the
    # note above describes. The artifact was replaced with a CROSS-BOOK OPENER
    # rule (kind="cross_book_opener"): where Bovada's opening spread disagrees
    # with DraftKings' by >= 1.0, back the side Bovada favours at DK's stale
    # number. Backtest 2023-2025: 1,050 bets 58.1% +10.9%, positive in all
    # three seasons, CLV 0.694, reversed book assignment null, both placebos
    # pass. The dead AUC-0.49 classifier is deactivated in model_registry.
    #
    # The open question -- whether both openers are observable simultaneously --
    # is enforced by the SCORER, not assumed: it requires the two openers to be
    # captured within max_skew_min AND DK to still be on its opening number,
    # else no pick. So the rule self-disables exactly when it would be
    # untradeable, which is the "remove it later if Bovada comes after DK"
    # condition made automatic.
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
    # mlb_prop_pitcher_hits — UNPAUSED 2026-08-31 (mike) at 0.54/0.08. The
    # "best 60+ cut still -9.0%" that paused it was measured on RAW
    # probabilities, and this model is the most overconfident on the board:
    # it claims 70.5% where it delivers 38.5%. On calibrated numbers the same
    # picks grade 49-46 +11.0%, +13.2% then +8.7% by half. Nothing about the
    # model changed; the number it was being judged on did.
    # mlb_prop_pitcher_outs — UNPAUSED 2026-08-31 (mike) at its existing
    # 0.50/0.12. Here it was the PRICE FLOOR, not the calibration: the sweep
    # was grading 26.1% of rows the -140 floor refuses, and once they are
    # excluded the cell goes from failing the time split to 46-33 +20.7%.
    # Halves +0.7% then +40.2% -- positive throughout, but the first half is
    # break-even, so this is the first cut to re-check.
    # 2026-07-11 PAUSED (Matt): pitcher ER + walks removed from display and
    # consideration for now. Both were running on the rolled-back May model
    # versions (session 94c) at marginal live cuts (er 0.61/0.08, walks
    # 0.60/0.08). Still score as NONE rows for forward tracking; thresholds kept
    # in the dicts below for the unpause.
    "mlb_prop_pitcher_er",
    "mlb_prop_pitcher_walks",
    "mlb_prop_batter_tb",      # best 60+ cut -1.7% — retrain (efficient market; needs contact-quality features)
    "mlb_prop_batter_sb",      # can't reach 60 bets at any cut — needs catcher CS%/pop-time (not ingested)
    # 2026-09-03 PAUSED (mike). Dormant since 2026-07-23, not broken -- it scored
    # 460 rows on 1-2 Sept and player_game_log is continuous, so §7's "a dormant
    # model and a broken feed look identical" resolves to the dormant side.
    #
    # Its PREDICTIONS compressed on an UNCHANGED artifact. model_registry shows
    # one active version since 2026-06-21, never swapped. Two uncensored windows
    # either side, both with NONE rows present so like-for-like:
    #
    #   06-21..06-25  n=1,457  sd=0.1394  p99.9=0.944  max=0.950  >=0.78: 53 (3.64%)
    #   08-10..09-02  n=8,026  sd=0.1020  p99.9=0.774  max=0.795  >=0.78:  8 (0.10%)
    #
    # Same model file, 36x fewer rows clearing the 0.78 prob cut. The break is
    # sharp at 2026-07-23: daily max prob ran 0.87-0.99 with BETs every day to
    # 07-22 and never exceeded 0.795 after. The cut did not move (0.78/0.17 since
    # 2026-06-28), so this is the inputs losing discriminative power, not a
    # threshold change. WHICH feature is still open -- the repo's git history
    # starts 2026-08-27, so there is no code history for July.
    #
    # Do NOT chase the volume back. 521 settled BETs, flat $100 (profit_flat is
    # exactly -100 on every loss; dividing by recommended_bet mixes flat profit
    # with a Kelly stake and gives a nonsense -127%):
    #
    #   blocked by the -140 floor  401 bets  65.1% vs 67.9% breakeven   -3.89%
    #   passes the -140 floor      120 bets  40.0% vs 50.1% breakeven  -21.16%
    #   all                        521 bets  59.3% vs 63.8% breakeven   -7.87%
    #
    # THE -140 FLOOR KEEPS THE WORSE HALF FOR THIS MODEL. The slice it admits
    # lost -21.2%; the slice it blocks lost -3.9%. That inverts the floor's
    # purpose here (on mlb_prop_batter_rbi the same floor capped 36 bets at +7.3%
    # vs +2.2% uncapped), so it is a per-model fact, not a general one -- do not
    # generalise it to the other props.
    #
    # So the dormancy was PROTECTIVE, and that was the risk being carried: the
    # model was unpaused, and if its distribution ever un-compressed it would
    # resume betting the -21% slice with nobody having decided to. It has lost
    # $4,098 at flat $100 over 521 bets, and config's own note has called it a
    # retrain candidate since 2026-06-21.
    #
    # The sweep's "best" cell (29 bets, +19%) is NOT an unpause path -- its own
    # verdict was "FAILS THE TIME SPLIT (19.5% then None%)": the second half has
    # no bets at all, so it fits the pre-07-23 period that no longer exists.
    # Unpause path is a retrain, but find the 07-23 cause first: the features
    # (rolling form, prior-season Savant, batting order, opp team ERA) are the
    # same ones that stopped discriminating, so retraining blind may reproduce
    # it. Thresholds stay in the dicts below for the unpause.
    "mlb_prop_batter_hits",
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
    # RE-PAUSED 2026-08-31 (mike), one day after being unpaused, and the reason
    # is worth keeping: the 2026-08-30 unpause was decided on a sweep that
    # ignored config.MODEL_MIN_ODDS. 37.5% of the rows behind that "22-7
    # +15.6%" are bets the scorer refuses at -140. With the floor applied there
    # is NO cell in the grid that clears 25 settled bets profitably, and the
    # live record is -18.7% over 70 bets. A measurement bug that reaches a
    # threshold decision is worse than the same bug in a report, which is why
    # the floor is now applied in the sweep itself and pinned by
    # tests/test_sweep_price_floor.py.
    "wnba_prop_player_threes",
    # "wnba_prop_player_pra" — UNPAUSED 2026-08-30 (mike). Its edge
    # survived a time split on calibrated probabilities; the
    # pause predates that measurement.

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
    # "wnba_prop_player_rebounds" — UNPAUSED 2026-08-30 (mike). Its edge
    # survived a time split on calibrated probabilities; the
    # pause predates that measurement.

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
    # "mlb_over_under" — UNPAUSED 2026-08-30 (mike). Its edge
    # survived a time split on calibrated probabilities; the
    # pause predates that measurement.

    # mlb_prop_batter_hr: UNPAUSED 2026-06-20 (the -66.6% that justified the
    # pause was a settlement artifact), then RETIRED 2026-09-02 (matt) -- gone
    # from PROP_MODELS entirely, so there is nothing left to pause. Same for
    # mlb_prop_batter_rbi. See the RETIRED block above PROP_MODELS.
    # ── NFL player props — paused on arrival (2026-08-23) ─────────────────
    # Built and assessed on OUTCOMES, never validated against a PRICE:
    # no NFL prop odds exist in player_prop_odds yet. Their thresholds
    # are placeholders, so leaving them live would surface picks off an
    # untuned cut. Each unpauses individually once it clears the six
    # gates in docs/nfl_props_model.md §5 — not as a family.
    "nfl_prop_pass_yards",
    "nfl_prop_pass_attempts",
    "nfl_prop_pass_completions",
    "nfl_prop_pass_tds",
    "nfl_prop_rush_yards",
    "nfl_prop_rush_attempts",
    "nfl_prop_rec_yards",
    "nfl_prop_receptions",
    "nfl_prop_rush_rec_yards",
    "nfl_prop_anytime_td",
    "nfl_prop_tackles_assists",
    "nfl_prop_sacks",
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
    # mlb_prop_batter_hr carried 0.25 here (2026-06-28, Matt) until it was
    # RETIRED 2026-09-02. Nothing is currently scaled; the mechanism stays.
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
# Decide on the CALIBRATED probability, not the raw one (mike, 2026-08-31).
#
# Every model publishes a probability and, separately, a claimed-to-realised map
# (models/probability_calibration.py). Until now the map only moved a DISPLAY
# number: picks.model_probability_cal was stamped and nothing read it back, so
# `edge` and the BET call were computed on the raw probability.
#
# That gap is where mlb_f5_moneyline's -195 bets came from. Its raw
# probabilities are well calibrated to about 0.60 and then run 10-12pp hot:
# claimed 0.68 delivers 0.56, claimed 0.72 delivers 0.62, claimed 0.77 delivers
# 0.67, over 270 graded rows. A 7pp edge bar against a 66% implied price needs
# a ~74% claim, which lands squarely in the worst-calibrated band -- so the
# heavy juice was not the cause, it was the selector.
#
# With this on, edge = calibrated_prob - dk_implied_prob, and both the edge and
# probability floors are applied to the calibrated number. A model with no
# PROMOTED map calibrates to itself, so this is a no-op for it -- the change
# only bites where a map exists and the fit's own held-out half endorsed it.
#
# Env-overridable so it can be switched off without a deploy if the volume drop
# is worse than intended.
DECIDE_ON_CALIBRATED_PROB: bool = (
    os.environ.get("DECIDE_ON_CALIBRATED_PROB", "1").strip() not in ("0", "false", "False")
)

# THE HOUSE JUICE FLOOR. Applies to every model that does not name its own.
#
# mike, 2026-09-03, on seeing `LAD ML F5  -290 @ FanDuel  3u to win 0.91u` on
# the board: "Why is there a -295 pick?!?! I thought we had juice rules. this
# needs to be removed."
#
# We did have a juice rule and it reached 17 of 69 models: sixteen props at -140
# and ncaaf_moneyline at -250. `MODEL_MIN_ODDS.get(model_id)` returned None for
# everything else, and None means NO FLOOR -- so every MLB game-level model
# could bet any price at all. That pick was DK -330 with a model probability of
# 0.7729 against a 0.7674 break-even: an edge of 0.54%, on a model whose own
# Kelly fraction came out at 0.0023. mlb_f5_moneyline's cut is
# min_prob 0.74 / min_edge 0.0, and a zero edge floor accepts exactly that.
#
# BLAST RADIUS, measured on the clean window (BETs since 2026-08-09 that clear
# their CURRENT floor) rather than guessed:
#
#     mlb_f5_moneyline     38 bets,  3 fail at -200,  1 at -250, juiciest -330
#     ncaaf_live_win_prob   2 bets,  1 fail at -200,             juiciest -238
#     mlb_live_win_prob     9 bets,  1 fail at -200  (retired model)
#
# So roughly three picks a month, and every one of them a heavy favourite where
# the payout stops covering model error. (A naive count over ALL history says
# 29% of bets, but that is dominated by prop rows written before the -140 prop
# floors existed -- the prospective number is the one above.)
#
# WHY -200. At -200 a bet needs 66.7% to break even and lays 2u to win 1u,
# which is also where MAX_RISK_UNITS (3.0) stops binding. It is a house risk
# rule, not a swept cut: it is NOT derived from a per-model record and is not
# claimed to be optimal for any model. A model that wants a different floor
# names it below and the explicit value wins in either direction -- note
# ncaaf_moneyline's -250 is LOOSER than this default and stays looser.
DEFAULT_MIN_ODDS: float = float(os.environ.get("DEFAULT_MIN_ODDS", "-200"))

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
    "mlb_prop_batter_runs":   -140,  # unpaused 2026-08-09 — floor is part of the +24.6%/40 cut
    "mlb_prop_batter_sb":     -140,
    "mlb_prop_batter_walks":  -140,
    # WNBA player props
    "wnba_prop_player_points":   -140,
    "wnba_prop_player_rebounds": -140,
    "wnba_prop_player_assists":  -140,
    "wnba_prop_market":          -140,  # blanket WNBA-prop floor applies to the market rule too
    "wnba_prop_player_threes":   -140,
    "wnba_prop_player_pra":      -140,
    # NCAAF moneyline — CFB has enormous talent gaps, so most of a Saturday
    # slate is priced -1000 or worse where no realistic model edge survives
    # the juice. -250 keeps the model to games that are actually contested.
    "ncaaf_moneyline":           -250,
}


def min_odds_for(model_id: str) -> float:
    """The price floor this model actually bets under.

    ONE accessor, because the floor has to mean the same thing in all three
    places that consult it: the scorer's BET/NONE gate, the
    model_action_thresholds mirror the app filter and the Discord card read, and
    the sweeps. `MODEL_MIN_ODDS.get(mid)` returned None for 52 of 69 models and
    None meant "no floor at all" -- see the block comment above.
    """
    return MODEL_MIN_ODDS.get(model_id, DEFAULT_MIN_ODDS)

# Per-model BET edge thresholds (override the global default above).
# Derived from 2024 OOS backtest sweep: higher thresholds filter to higher-quality picks.
# Revisit after each retrain — edge distributions shift as features are added.
MODEL_EDGE_THRESHOLDS: dict = {
    "mlb_moneyline":            0.11,   # 2026-07-04: reverted to v20260413 model, 0.72/0.11 = 21-6 +29.5% live
    "mlb_over_under":           0.04,  # 2026-08-30 UNPAUSED (mike) — calibrated sweep + time split, scripts/calibrated_threshold_sweep
    "mlb_runline":              0.11,   # 2026-07-02 CORRECTION: the 06-28 0.55/0.10 "+14.9%" was a view sign bug (actually -20.6%). Corrected optimum 0.68/0.11 = 19 bets 13-6 +20.0%. 2026-08-21: DORMANT (model can no longer reach 0.68 — see ACTION_THRESHOLDS note); cut held pending the 2019-2025/holdout-2026 retrain + scripts/mlb_runline_sweep.py
    "mlb_f5_moneyline":         0.02,   # 2026-09-03 (mike): 0.00 -> 0.02 with the retrained artifact. See ACTION_THRESHOLDS for the sweep, the plateau failure, and the kill criterion.
    "mlb_f5_over_under":        0.15,   # DISABLED — DK does not carry totals_1st_5_innings
    "mlb_f5_runline":           0.15,   # DISABLED — DK does not carry spreads_1st_5_innings
    "nhl_moneyline":            0.05,   # placeholder — tune after 50+ settled picks
    "nhl_moneyline_regulation": 0.05,
    "nhl_over_under":           0.05,
    "nhl_puckline":             0.05,
    "nfl_wind_totals":          0.03,   # mirrors the wind card's own MIN_EDGE gate (§28)
    "nfl_opener_spread":        0.00,   # card gates on |dev| >= 1.0; edge >= 0 drops juice-eaten quotes
    # Prop models — re-optimized 2026-06-20 from settled-pick sweep (see ACTION_THRESHOLDS for per-model rationale + caveats)
    "mlb_prop_pitcher_k":        0.08,  # 2026-08-31 (mike): floor-corrected calibrated sweep, 0.58/0.08 = 15-10 +14.8%
    "mlb_prop_pitcher_hits":     0.08,  # 2026-08-31 (mike): UNPAUSED at 0.54/0.08 on the calibrated sweep = 49-46 +11.0%
    "mlb_prop_pitcher_er":       0.08,   # 2026-06-21 ≥10% target: 0.61/0.08 +11.1%/81
    "mlb_prop_pitcher_outs":     0.12,   # 2026-06-21 full-outcome
    "mlb_prop_pitcher_walks":    0.08,   # 2026-06-21 full-outcome
    "mlb_prop_batter_hits":      0.17,  # 2026-06-28 full-outcome: 0.78/0.17 = 77 bets +8.3% (UNPAUSED)
    "mlb_prop_batter_tb":        0.17,  # 2026-06-20: 83%/17% +3.2%
    "mlb_prop_batter_runs":      0.10,   # 2026-08-31 (mike): floor-corrected calibrated sweep, 0.62/0.10 = 18-9 +25.6% (halves +25.6/+25.6)
    "mlb_prop_batter_sb":        0.10,  # NO winning cut — needs feature work
    "mlb_prop_batter_walks":     0.14,   # 2026-06-21 RE-SWEEP: 0.45/0.14 = 65 bets +5.3%
    # WNBA — placeholder; retune from 2025 holdout backtest sweep.
    "wnba_moneyline":            0.06,  # 2026-08-31 (mike): calibrated sweep 0.50/0.06 = 18-7 +24.3% (was 0.64/0.04 on raw probabilities)
    "wnba_over_under":           0.06,   # 2026-07-19 OOS sweep (see ACTION_THRESHOLDS)
    "wnba_spread":               0.10,   # 2026-07-19 OOS sweep
    "wnba_prop_player_points":   0.17,  # PAUSED 2026-07-11 — no positive cut on the 2x sample
    "wnba_prop_player_rebounds": 0.0,   # 2026-08-31 (mike): floor-corrected calibrated sweep, 0.62/0.00 = 19-11 +12.5% (halves +1.5/+22.2 -- thin first half)
    "wnba_prop_player_assists":  0.10,  # 2026-08-31 (mike): floor-corrected calibrated sweep, 0.50/0.10 = 35-22 +23.1%
    "wnba_prop_player_threes":   0.026,  # 2026-08-30 UNPAUSED (mike) — calibrated sweep + time split, scripts/calibrated_threshold_sweep
    "wnba_prop_player_pra":      0.16,  # 2026-08-30 UNPAUSED (mike) — calibrated sweep + time split, scripts/calibrated_threshold_sweep
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
    # mlb_live_win_prob + mlb_live_runline RETIRED 2026-08-30 (see LIVE_MODELS).
    "mlb_live_total_runs": 0.14,
    # NCAAF (FBS) — PLACEHOLDER cuts, deliberately tighter than our other launch
    # defaults. A Saturday slate is ~60-80 FBS games, so a loose cut would fire
    # 30+ picks in one afternoon. Tune from the 2025 holdout sweep (Phase 4),
    # sliced by game_tier (P4 vs G5) and week bucket.
    "ncaaf_spread":     0.0,   # margin model: the ±5.5 disagreement gate IS the filter
    "ncaaf_spread_premium": 0.0,   # the [2.5, inf) band IS the filter
    "ncaaf_live_win_prob": 0.10,
    "ncaaf_live_total":    0.12,
    "ncaaf_over_under": 0.0,   # gate is the filter, not price
    "ncaaf_moneyline":  0.08,
    # ── NFL player props (2026-08-23) ──────────────────────────────────────
    # PLACEHOLDERS. Not tuned, and they cannot be tuned until prop prices
    # exist to grade against — the whole NFL prop family is in
    # PAUSED_MODELS for exactly that reason. Do not read these as a
    # calibrated cut. anytime_td's prob floor is lower because its base
    # rate is 27%, not 50%.
    "wnba_prop_market":            0.05,   # see ACTION_THRESHOLDS
    "nfl_prop_market":             0.05,   # see ACTION_THRESHOLDS
    "nfl_prop_pass_yards":         0.05,
    "nfl_prop_pass_attempts":      0.05,
    "nfl_prop_pass_completions":   0.05,
    "nfl_prop_pass_tds":           0.05,
    "nfl_prop_rush_yards":         0.05,
    "nfl_prop_rush_attempts":      0.05,
    "nfl_prop_rec_yards":          0.05,
    "nfl_prop_receptions":         0.05,
    "nfl_prop_rush_rec_yards":     0.05,
    "nfl_prop_anytime_td":         0.05,
    "nfl_prop_tackles_assists":    0.05,
    "nfl_prop_sacks":              0.05,
}

# Per-model minimum model probability to generate a BET signal.
# Moneyline markets run at a lower floor to surface more picks.
MODEL_PROB_THRESHOLDS: dict = {
    "mlb_moneyline":            0.72,   # 2026-07-04: reverted to v20260413 model, 0.72/0.11 = 21-6 +29.5% live
    "mlb_over_under":           0.5,  # 2026-08-30 UNPAUSED (mike) — calibrated sweep + time split, scripts/calibrated_threshold_sweep
    "mlb_runline":              0.68,   # 2026-07-02 CORRECTION: the 06-28 0.55/0.10 "+14.9%" was a view sign bug (actually -20.6%). Corrected optimum 0.68/0.11 = 19 bets 13-6 +20.0%. 2026-08-21: DORMANT — max live prob in Aug 2026 was 0.625, so this floor is unreachable; cut held pending the retrain + re-sweep (see ACTION_THRESHOLDS note)
    "mlb_f5_moneyline":         0.58,   # 2026-09-03 (mike): 0.74 -> 0.58. The old bar fired ZERO bets (max raw prob 0.734) and was swept on CALIBRATED probabilities while the scorer decides on RAW. See ACTION_THRESHOLDS.
    "mlb_f5_over_under":        0.65,   # DISABLED — DK does not carry these markets
    "mlb_f5_runline":           0.65,   # DISABLED — DK does not carry these markets
    "nhl_moneyline":            0.55,
    "nhl_moneyline_regulation": 0.40,   # 3-way market — lower per-side prob
    "nhl_over_under":           0.55,
    "nhl_puckline":             0.55,
    "nfl_wind_totals":          0.52,   # ~breakeven at -110; calibrated probs run 0.56-0.60 (§28)
    "nfl_opener_spread":        0.52,   # ~breakeven at -110, a sanity floor like wind's. Was 0.55, which
                                    # was set against a FLAT 0.5818 model prob; once the card began
                                    # pricing per deviation it silently became an edge filter (§28)
    # Prop models — re-optimized 2026-06-20 from settled-pick sweep (see ACTION_THRESHOLDS for per-model rationale + caveats)
    "mlb_prop_pitcher_k":        0.58,  # 2026-08-31 (mike): floor-corrected calibrated sweep, 0.58/0.08 = 15-10 +14.8%
    "mlb_prop_pitcher_hits":     0.54,  # 2026-08-31 (mike): UNPAUSED at 0.54/0.08 on the calibrated sweep = 49-46 +11.0%
    "mlb_prop_pitcher_er":       0.61,   # 2026-06-21 ≥10% target: 0.61/0.08 +11.1%/81
    "mlb_prop_pitcher_outs":     0.5,   # 2026-06-21 full-outcome
    "mlb_prop_pitcher_walks":    0.6,   # 2026-06-21 full-outcome
    "mlb_prop_batter_hits":      0.78,  # 2026-06-28 full-outcome: 0.78/0.17 = 77 bets +8.3% (UNPAUSED)
    "mlb_prop_batter_tb":        0.83,  # 2026-06-20: 83%/17% +3.2%
    "mlb_prop_batter_runs":      0.62,   # 2026-08-31 (mike): floor-corrected calibrated sweep, 0.62/0.10 = 18-9 +25.6% (halves +25.6/+25.6)
    "mlb_prop_batter_sb":        0.18,  # NO winning cut — needs feature work
    "mlb_prop_batter_walks":     0.45,   # 2026-06-21 RE-SWEEP: 0.45/0.14 = 65 bets +5.3%
    # WNBA — placeholder; retune from 2025 holdout backtest sweep.
    "wnba_moneyline":            0.5,   # 2026-08-31 (mike): calibrated sweep 0.50/0.06 = 18-7 +24.3% (was 0.64/0.04 on raw probabilities)
    "wnba_over_under":           0.60,   # 2026-07-19 OOS sweep
    "wnba_spread":               0.60,   # 2026-07-19 OOS sweep
    "wnba_prop_player_points":   0.58,  # PAUSED 2026-07-11 — no positive cut on the 2x sample
    "wnba_prop_player_rebounds": 0.62,  # 2026-08-31 (mike): floor-corrected calibrated sweep, 0.62/0.00 = 19-11 +12.5% (halves +1.5/+22.2 -- thin first half)
    "wnba_prop_player_assists":  0.5,   # 2026-08-31 (mike): floor-corrected calibrated sweep, 0.50/0.10 = 35-22 +23.1%
    "wnba_prop_player_threes":   0.706,  # 2026-08-30 UNPAUSED (mike) — calibrated sweep + time split, scripts/calibrated_threshold_sweep
    "wnba_prop_player_pra":      0.68,  # 2026-08-30 UNPAUSED (mike) — calibrated sweep + time split, scripts/calibrated_threshold_sweep
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
    # mlb_live_win_prob + mlb_live_runline RETIRED 2026-08-30 (see LIVE_MODELS).
    "mlb_live_total_runs": 0.7,  # 2026-08-30 mike: live volume cut — see MODEL_MIN_EV + docs/live_betting.md
    # NCAAF (FBS) — PLACEHOLDER cuts, deliberately tighter than our other launch
    # defaults. A Saturday slate is ~60-80 FBS games, so a loose cut would fire
    # 30+ picks in one afternoon. Tune from the 2025 holdout sweep (Phase 4),
    # sliced by game_tier (P4 vs G5) and week bucket.
    "ncaaf_spread":     0.55,  # floors the cross-book opener's flat 0.5810
    "ncaaf_spread_premium": 0.58,  # floors the premium band's flat 0.6047
    "ncaaf_live_win_prob": 0.66,  # 2026-08-30 mike: live volume cut — see MODEL_MIN_EV + docs/live_betting.md
    "ncaaf_live_total":    0.66,  # 2026-08-30 mike: live volume cut — see MODEL_MIN_EV + docs/live_betting.md
    "ncaaf_over_under": 0.65,  # = P(over) at the +/-8.0 gate
    "ncaaf_moneyline":  0.62,
    # ── NFL player props (2026-08-23) ──────────────────────────────────────
    # PLACEHOLDERS. Not tuned, and they cannot be tuned until prop prices
    # exist to grade against — the whole NFL prop family is in
    # PAUSED_MODELS for exactly that reason. Do not read these as a
    # calibrated cut. anytime_td's prob floor is lower because its base
    # rate is 27%, not 50%.
    "wnba_prop_market":            0.0,    # edge is the signal; see ACTION_THRESHOLDS
    "nfl_prop_market":             0.0,    # edge is the signal; see ACTION_THRESHOLDS
    "nfl_prop_pass_yards":         0.55,
    "nfl_prop_pass_attempts":      0.55,
    "nfl_prop_pass_completions":   0.55,
    "nfl_prop_pass_tds":           0.55,
    "nfl_prop_rush_yards":         0.55,
    "nfl_prop_rush_attempts":      0.55,
    "nfl_prop_rec_yards":          0.55,
    "nfl_prop_receptions":         0.55,
    "nfl_prop_rush_rec_yards":     0.55,
    "nfl_prop_anytime_td":         0.3,
    "nfl_prop_tackles_assists":    0.55,
    "nfl_prop_sacks":              0.55,
}

# ── Live (In-Play) Betting ────────────────────────────────────────────────────
# Phase 1: game-state poller polls MLB live feed for each in-progress game on
# this cadence. Free API — no Odds API credits consumed.
# 15 -> 5 (2026-08-29). The odds fetch runs INSIDE this loop, so the pass is the
# hard bound on how fresh a live price can ever be: no odds cadence below this
# number buys anything. MLB StatsAPI is free, so the only cost of 5s is the
# paid fetch it now permits, which is capped below.
LIVE_POLL_INTERVAL_SEC: int  = int(os.environ.get("LIVE_POLL_INTERVAL_SEC", 5))
# Window in which we treat a game as "live": 15 min before scheduled first pitch
# (warmup updates can move lines) through final out.
LIVE_PREGAME_BUFFER_MIN: int = int(os.environ.get("LIVE_PREGAME_BUFFER_MIN", 15))
# Minimum spacing between in-play odds fetches, and (since the floor fetch) the
# cadence itself: the orchestrator fetches every LIVE_FG_DEBOUNCE_SEC while any
# game is live, not only when a trigger fires.
#
# 60 -> 5 (2026-08-29). The old comment's premise -- "3-run innings still produce
# only one line-move opportunity" -- is the same mistake the trigger set made: a
# live total moves on every baserunner, not once an inning. At 60s the end-to-end
# lag was minutes; the measured feed gap that day averaged 269s. The bulk
# endpoint costs 3 credits however many games are live, so this is a flat
# ~21k credits on a 10-hour slate, not a per-game cost.
LIVE_FG_DEBOUNCE_SEC: int    = int(os.environ.get("LIVE_FG_DEBOUNCE_SEC", 5))
# Hard kill switch — orchestrator stops dispatching Odds API calls if today's
# in-play burn would exceed this. 1000 -> 10000 (2026-08-29): 1000 was sized for
# a TRIGGER-ONLY fetch ("~300-600 on a realistic evening"). The floor fetch
# added the same day is ~600 fetches x 3 credits = ~1,800 on a 10-hour slate, so
# the old cap would have bound by mid-afternoon and silently stopped refreshing
# the line — the exact failure the floor exists to prevent. 10k is ~5x headroom
# and ~0.2% of the account balance. Set =0 to run uncapped.
LIVE_DAILY_CREDIT_CAP: int   = int(os.environ.get("LIVE_DAILY_CREDIT_CAP", 50000))
# How old DRAFTKINGS' OWN publish of an in-play price may be before the live
# scorer declines. This is a BOOK-publish bound, not a fetch bound: in-play rows
# store `snapshot_at` from the market's `last_update`, so the age measured here
# is how long ago DK last moved the number — the only thing that says whether
# the price is still on offer.
#
# 300 -> 120 -> 30 -> 90 (2026-08-29, three revisions in a day; the third was
# wrong and this records why). The 30s value was set on the reasoning that "the
# bound must stay a small multiple of the FETCH cadence", which would be right
# if the column held our clock. It does not. Measured over 1,687 in-play
# publishes that evening, DK republishes a live total every 47s at the median
# and 106s at p90 — so a 30s bound sat BELOW the book's own refresh rate and
# declined roughly 60% of the time by construction. A bound tighter than the
# feed it guards is not a safety net, it is an outage.
#
# 90s is the NFL live model's proven MAX_QUOTE_AGE_SEC and fits the measured
# distribution: it accepts the normal rhythm and rejects a freeze (the NCAAF
# market that produced the bad Florida State pick had held one number for 275s).
#
# 90 -> 60 -> 30 (2026-08-30, mike). Measured against DraftKings' OWN feed for
# the first time -- 4,404 in-play rows compared with what DK was actually
# showing at that moment -- the price we would act on is on the WRONG LINE at a
# rate that climbs with this bound: 4.8% at 0-15s, 7.4% at 15-30s, 9.7% at
# 30-45s, 12.4% at 45-60s, 20.5% beyond 60s. Under the pick rule a different
# line is a different bet, not a stale price.
#
# 30 IS A DELIBERATE, REAFFIRMED CHOICE, NOT A REVERSION. The identical value
# was set and rolled back on 2026-08-29 because it sits BELOW DK's own 47s
# median republish and declined ~60% of passes by construction. That concern
# was put to mike twice, with the numbers, and he chose 30 anyway: the trade is
# fewer live bets in exchange for the ones we do take being priced at a line
# that is actually on the board. Do NOT quietly raise this back to 60/90 on the
# strength of the 2026-08-29 note -- that argument has been heard and decided.
#
# EXPECTED CONSEQUENCE, so a volume drop is not misread as an outage: a pass can
# only act during the fresh ~30s of each ~47-67s republish cycle, so roughly
# half of passes decline. tracking/live_calibration.py re-derives every live cut
# from the RECENT regime, so its bets/week projections move with this -- that is
# the mechanism working, not drift.
LIVE_ODDS_MAX_AGE_SEC: int   = int(os.environ.get("LIVE_ODDS_MAX_AGE_SEC", 30))

# ── Pre-game line poller (2026-08-30) ────────────────────────────────────────
# The pre-game board used to be re-read by the 28-job refresh pass, which takes
# ~12 minutes. Scheduled every 10 minutes in the evening, it could never keep
# up: 18 passes ran in a 5-hour window, one every 17 minutes, and the ticks in
# between were silently skipped. A line that opened and moved inside that gap
# was priced -- if at all -- long after it was takeable.
#
# mike, 2026-08-30: "why not run this like we do the live poller every few
# seconds for games not started ... and that should be the cadence 24x7".
#
# So this is the live loop's shape applied to unstarted games: fetch, diff,
# and act only on what moved. It is NOT the refresh pass run more often --
# that pass rebuilds features, settles bets, notifies and health-checks, none
# of which belongs on a price-watching cadence.
#
# 30s was chosen against two measurements, not a guess:
#   * COST. The bulk game-lines call is ~13 credits across all six sports, so
#     30s is ~37,440/day = ~1.1M/month against a 5M monthly reset (~22%).
#     5s would be ~225k/day = 6.8M/month, i.e. over plan, for no extra picks.
#   * BENEFIT. Over 39,146 pre-game observations in 48h, 95% found DK's number
#     unchanged; the median gap between real moves was ~50 minutes and even the
#     fastest decile was ~10 minutes. 30s is already ~20x faster than the
#     fastest-moving lines move, so it is the point past which spending more
#     buys nothing.
PREGAME_POLL_INTERVAL_SEC: int = int(os.environ.get("PREGAME_POLL_INTERVAL_SEC", 30))
# How often the poller rebuilds its fingerprint map from the database rather
# than from its own writes. The rebuild reads DK's whole pre-game history for
# every unstarted game and was costing 24.6 HOURS of database time a day at one
# rebuild per 30s tick (measured 2026-09-02); at 15 minutes it costs about 96
# reads a day instead of 2,880. Lower it only if another writer moving a
# pre-game price needs to be noticed sooner than that.
PREGAME_POLL_RESEED_SEC: int = int(os.environ.get("PREGAME_POLL_RESEED_SEC", 900))
# Kill switch, so the loop can be stopped from Railway without a deploy.
RUN_PREGAME_POLLER: bool = os.environ.get("RUN_PREGAME_POLLER", "1") == "1"
# Hard daily cap on this loop's Odds API burn, mirroring LIVE_DAILY_CREDIT_CAP.
# 30s x 24h x ~13 credits is ~37k, so 60k is ~1.6x headroom and still ~1.2% of
# a monthly plan. Set = 0 to run uncapped.
PREGAME_POLL_DAILY_CREDIT_CAP: int = int(
    os.environ.get("PREGAME_POLL_DAILY_CREDIT_CAP", 60000))
# Sports the poller watches. NHL is excluded while it is out of season -- its
# per-event 3-way pull returns 422 on every event and costs 32 wasted round
# trips a pass.
PREGAME_POLL_SPORTS: list = [
    s for s in os.environ.get(
        "PREGAME_POLL_SPORTS", "MLB,WNBA,NBA,NCAAF,UFC").split(",") if s.strip()
]
# Live game-state snapshots older than this mean the poller has stopped —
# don't score from a frozen state.
# 300 -> 60 (2026-08-29): 300 was 20 passes at the old 15s poll and is 60 at the
# new 5s one. A frozen state is how the engine ends up pricing an inning that
# finished minutes ago, so the bound tracks the poll cadence.
LIVE_STATE_MAX_AGE_SEC: int  = int(os.environ.get("LIVE_STATE_MAX_AGE_SEC", 60))

# Live (in-play) model registry — kept SEPARATE from MODELS so the pre-game
# scorer/trainer/backtester never pick these up. Each entry:
# model_id → (sport, market, model_type, description).
#   binary  → XGBClassifier + Platt; predict_proba[1] = P(outcome)
#   poisson → XGBRegressor count:poisson; predict = expected count REMAINING
#
# RETIRED 2026-08-30 (matt): mlb_live_win_prob (h2h) and mlb_live_runline
# (spreads), the two BINARY live models. Removing them from this registry is
# what stops them: the live scorer, the trainer (--all-live) and the live
# feature map are all driven off these keys, so a retired model cannot score,
# cannot be retrained, and writes no rows of any kind.
#
# Evidence (2026-08-29 sweep over every settled live BET at real DK prices,
# flat $100): win_prob 15 bets 6-9 -34.1%, runline 14 bets 5-9 -39.9%, and both
# get WORSE as the probability floor rises (win_prob 0.65/0.15 = -78.9% on 8).
# Avg model probability 0.73-0.76 against a 36-40% realised win rate: they are
# overconfident, which is a CALIBRATION failure, not a threshold one -- there is
# no cut to find and nothing a pause would learn. Their 5.3%/5.9% holdout CalErr
# (both above the 5% go-live gate) said so before either ever took a bet.
#
# Their picks stay in the DB and stay graded -- a pick that existed is the bet of
# record (§1c). paper_tracker._RETIRED_MODEL_MARKETS keeps mapping them to the
# right market so those rows settle on the right math forever; without it the
# runline picks would fall back to 'h2h' and grade as moneylines.
#
# Reviving one means retraining it (the artifacts are deleted, the registry rows
# deactivated) and clearing the calibration gate first -- not just re-adding a key.
LIVE_MODELS = {
    "mlb_live_total_runs": ("MLB", "totals",  "poisson",
                            "Expected runs in the REMAINDER of the game"),
    # NCAAF live (ncaaf_live/ package, runs on Matt's machine on gamedays).
    # WP gate PASSED (Brier 0.115); the totals lane is licensed only with
    # >= 900s of regulation left (the calibrated region) — enforced in
    # ncaaf_live/serve.py, not here. Settlement rides the generic game path
    # via this market mapping; totals settle vs scored_line (the live line
    # at pick time), the MLB-live convention.
    "ncaaf_live_win_prob": ("NCAAF", "h2h",    "engine",
                            "P(home wins) from the live two-stage engine"),
    "ncaaf_live_total":    ("NCAAF", "totals", "engine",
                            "Live main-total from the remaining-points distribution"),
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
    "NCAAF": {
        "odds_api_key":  "americanfootball_ncaaf",
        # Season label = calendar year of the FALL. The 2025 season includes
        # January 2026 bowl / playoff games — so season is NEVER derived from a
        # game's date (Jan/Feb games belong to the PRIOR year's season). CFBD
        # returns `season` explicitly on every game; the odds ingestor rolls
        # Jan/Feb back a year. Same footgun class as the NBA Oct-Dec rule.
        "seasons":       list(range(2015, 2027)),
        # Train window = the portal era only (Matt's call 2026-08-20). ~3,000
        # FBS games — thin for a 25-feature model, chosen for regime
        # consistency (transfer portal + NIL broke year-over-year continuity in
        # 2021). This is a ONE-LINE change: Phase 4 backtests 2021-24 against
        # 2015-24 and the data decides.
        "train_seasons": list(range(2021, 2025)),  # 2021-2024 train
        "test_season":   2025,                      # 2025 held out
        "sbr_dir":       ROOT / "data/raw/datawarehouse/ncaaf",
    },
    "NFL": {
        "odds_api_key":  "americanfootball_nfl",
        # Season label = the nflverse season, i.e. the calendar year the season
        # STARTS. January/February playoff games belong to the PRIOR year's
        # label and the season is always read from the source, never derived
        # from a date (same footgun as NCAAF and NBA).
        #
        # Train window starts 2015 — the earliest season with complete nflverse
        # usage shares AND snap counts. 2020 is deliberately kept in: it is an
        # anomalous season (no preseason, COVID absences) but excluding it would
        # cost 10% of the sample for a regime argument that never showed up in
        # the walk-forward season splits.
        "seasons":       list(range(2015, 2027)),
        "train_seasons": list(range(2015, 2025)),  # 2015-2024 train
        "test_season":   2025,                      # 2025 held out
        "sbr_dir":       ROOT / "data/raw/datawarehouse/nfl",
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
    # NCAAF (FBS) — all three game markets score against real DK lines AND
    # backtest against real historical lines (CFBD /lines). The first new sport
    # where totals/spreads are not blocked on missing line history.
    "ncaaf_spread":             ("NCAAF", "spreads",  "Home team covers the spread"),
    # Same rule as ncaaf_spread, DISJOINT band [2.5, inf). The scorer's
    # d_threshold_max keeps the two mutually exclusive, so a game fires
    # exactly one of them and the tiers never double-stake.
    "ncaaf_spread_premium":     ("NCAAF", "spreads",  "Home team covers the spread"),
    "ncaaf_over_under":         ("NCAAF", "totals",   "Total points over/under"),
    "ncaaf_moneyline":          ("NCAAF", "h2h",      "Home team wins"),
}

# ── The Odds API ──────────────────────────────────────────────────────────────
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
# Env-overridable so a probe can reach a region we do not normally pay for.
# Pinnacle — the market-making book whose de-vigged price is the benchmark the
# §28 opener model already trades against — is only served in "eu".
ODDS_API_REGIONS = os.environ.get("ODDS_API_REGIONS") or "us"
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
    for b in (os.environ.get("LINE_SHOP_BOOKMAKERS")
              # bovada + pinnacle added 2026-08-25 for the NCAAF cross-book
              # opener work. Pinnacle is the canonical sharp reference the
              # section-28 NFL opener rule already uses; Bovada is the book
              # whose OPENER carried the signal in the CFBD backtest. Both are
              # display/analysis only -- every model read is pinned to
              # DraftKings (asserted by tests/test_multi_book_odds.py). The
              # `bookmakers` param counts as ONE region, so extra books cost
              # zero extra Odds API credits.
              # fanatics added 2026-09-03 (mike). Verified against the live
              # endpoint first, per the curl above: `fanatics` is a real key
              # returning MLB/NCAAF/WNBA (no UFC). `caesars` and `wynnbet` are
              # NOT keys this API offers -- Caesars IS williamhill_us, and Wynn
              # left US online sportsbooks.
              # betrivers, hardrockbet, ballybet, betparx, rebet added
              # 2026-09-03 (mike: "do the extra books"). All five are real keys
              # covering MLB, NCAAF, WNBA and UFC -- the two sports where this
              # repo shopped fewest books.
              #
              # THEY ARE NOT FREE, AND THAT IS THE OPPOSITE OF WHAT THE COMMENT
              # ABOVE SAYS ABOUT `bookmakers` COUNTING AS ONE REGION. Measured
              # against the live endpoint 2026-09-03, one bulk MLB call for
              # h2h+spreads+totals:
              #
              #     the 8 books above          3 credits
              #     these 5 books alone        3 credits
              #     all 13 together            6 credits
              #
              # These five live in the `us2` region, so asking for them spans a
              # second region and the bill is markets x REGIONS. The same
              # doubling hits the per-event fetch (1 -> 2 credits on one market)
              # and the prop fetch, which uses this param too and is the larger
              # consumer. Recent burn is ~35k credits/day against a 5,000,000
              # monthly plan (August used 737,085), so the ceiling this moves
              # toward is ~2.1M/month -- affordable, but real, and mike was told
              # the number rather than left to find it.
              #
              # The marginal cost of books 2-5 is ZERO: once one us2 book is on
              # the list the second region is paid for. So this is all-or-
              # nothing, not a dial. Set LINE_SHOP_BOOKMAKERS to the first eight
              # to revert.
              or ("draftkings,fanduel,betmgm,williamhill_us,espnbet,"
                  "fanatics,bovada,pinnacle,"
                  "betrivers,hardrockbet,ballybet,betparx,rebet")).split(",")
    if b.strip()
]
# Comma-joined for the Odds API `bookmakers` query param.
# DraftKings is prepended because it is the book the models score against and
# must never be dropped by a config edit. The env override exists for ONE case:
# a targeted backfill that adds a book to history already collected. The
# inserter is append-only with no dedup, so re-requesting DK would duplicate
# every row it already holds — the override is how you ask for only what is
# missing.
ODDS_API_BOOKMAKERS_PARAM = (
    os.environ.get("ODDS_API_BOOKMAKERS_PARAM")
    or ",".join(dict.fromkeys(["draftkings", *LINE_SHOP_BOOKMAKERS]))
)

# Sharp reference books. These are MARKET-MAKING books whose de-vigged price is
# treated as an estimate of truth, not as a shopping option -- the construction
# models/nfl_prop_market.py validated at +10.76% blind over 954 bets, and the one
# approach in this repo with a blind-tested positive result.
#
# Listed separately from LINE_SHOP_BOOKMAKERS because the two roles have opposite
# retention needs. A line-shop book's history is genuinely disposable: only the
# newest row is ever read, to stamp a best price. A sharp book's history is the
# INPUT to a model, so pruning it destroys the evidence the model is built on.
# data/prune_odds.py protects everything named here.
#
# Added 2026-08-31 (mike) when MLB props moved toward a market-relative model.
# Pinnacle MLB prop capture began 2026-08-27, so the usable history is days old
# and every pruned day is validation that cannot be recovered later.
# Books requested when BACKFILLING history from The Odds API's /historical
# endpoint. Deliberately wider than the live pull's decision book.
#
# 2026-09-01 (mike: "Pinnacle data is in odds api. I have brought this up
# several times. why do you ignore it."). He was right, and the mechanism was
# this parameter. `_get_historical_odds` requested bookmakers=draftkings from
# the day it was written, so Supabase holds 40,488 MLB games of single-snapshot
# SBR consensus, 1,908 games of DK snapshots from 2026-04, and 73 games of
# Pinnacle from 2026-08-27 -- and I reported that as though Pinnacle history did
# not exist. It exists; we never asked for it.
#
# The `bookmakers` param counts as ONE region on this endpoint, so naming seven
# books costs exactly what naming one costs. The bill is 10 credits x markets x
# regions per call regardless.
ODDS_HISTORY_BOOKMAKERS = [
    b.strip().lower()
    for b in (os.environ.get("ODDS_HISTORY_BOOKMAKERS")
              or ",".join(dict.fromkeys([ODDS_API_BOOKMAKER,
                                         *LINE_SHOP_BOOKMAKERS]))).split(",")
    if b.strip()
]

SHARP_BOOKMAKERS = [
    b.strip().lower()
    for b in (os.environ.get("SHARP_BOOKMAKERS") or "pinnacle").split(",")
    if b.strip()
]

# Retention for line-shop (non-DraftKings) odds snapshots — see data/prune_odds.py.
# Both odds tables are append-only (~21 snapshots per proposition per day), but the
# ONLY readers of non-DK rows are the DISTINCT ON all-books views, which return just
# the newest row per book. So non-DK history is written once and never read, and at
# 5 books it would add ~2.7 GB/month. This bounds it to a flat working set.
# draftkings and sbr_consensus are NEVER pruned (CLV / line movement / training).
# Raise this before building any feature that needs non-DK history (e.g. "did the
# best book beat DK at close?") — pruned rows are gone permanently.
PRUNE_NON_DK_KEEP_DAYS = int(os.environ.get("PRUNE_NON_DK_KEEP_DAYS", "2"))

# ── Best-line shopping (what the bettor actually gets) ────────────────────────
# The books considered when stamping the BEST available price on a pick.
#
# This is DISPLAY + BET information, deliberately separate from scoring: a
# pick's `edge`, its BET/AVOID decision, its Kelly stake, its settled P&L and
# its CLV all still measure against DraftKings (ODDS_API_BOOKMAKER). That is
# not timidity — every threshold in section 17 was swept on DK-implied edge,
# and best-of-N pricing lowers the implied probability by ~2pp on average
# (measured 2026-08-28 over 92 MLB games), which would silently loosen every
# cut by that much. Keeping qualification on DK holds the pick set identical
# to the calibrated system while the bettor still takes the better number.
#
# Every scored pick now records best_book/best_odds/best_edge, so in a month
# there is real best-price history on the picks table itself to re-sweep the
# thresholds against — at which point qualification can flip over deliberately,
# with evidence, in one change.
# Books that are REFERENCE ONLY — never offered as a price to take.
#
# BEST_LINE_BOOKMAKERS answers one question: "where should the bettor actually
# place this?" A book that cannot be bet from the US is not an answer to it,
# however good its number is. Pinnacle does not accept US customers and Bovada
# is offshore; both are in LINE_SHOP_BOOKMAKERS deliberately (Pinnacle is the
# sharp de-vig reference SHARP_BOOKMAKERS is built on, Bovada carried the NCAAF
# opener signal), and both must stay there. They just must not be the price a
# member is told to take.
#
# Measured 2026-09-02, and this is why it is a hard default rather than a note:
# of 69 pre-game BETs since 08-31 carrying a best price, 35 named a book other
# than DraftKings and **18 of those 35 named Pinnacle or Bovada**. So over half
# of every "we found you a better number" claim, and 26% of all bets, pointed at
# a price the bettor could not take — while the column's own docstring says it
# is "what the bettor should actually take".
#
# espnbet joined the list on 2026-09-03: mike, "remove william hill and espn bet
# (shut down last year)". Recorded rather than silently applied, because the
# live feed disagrees -- measured the same day, espnbet returned 82 h2h quotes
# across MLB/NCAAF/WNBA with a MEDIAN AGE OF 0.7 MINUTES, which is a book that
# is very much still pricing. It is excluded anyway: which books a bettor will
# actually use is mike's call and not the feed's, and this is one env var to
# reverse. It stays in LINE_SHOP_BOOKMAKERS so the data keeps arriving.
#
# williamhill_us was NOT removed, and this is the one instruction that was not
# followed as written. On The Odds API `williamhill_us` IS Caesars -- the curl
# comment above LINE_SHOP_BOOKMAKERS says so, and `caesars` is not a key the
# endpoint returns. mike asked to ADD Caesars and REMOVE William Hill in the
# same breath; those are one book, so doing both literally would have deleted
# the book he asked for. Kept, flagged, his to overrule.
#
# `wynnbet` could not be added: the endpoint does not return that key at all
# (WynnBET exited US online sports betting).
#
# Override with BEST_LINE_EXCLUDE_BOOKMAKERS (comma-separated) to add or, with
# an empty value, to shop every book in LINE_SHOP_BOOKMAKERS.
_BEST_LINE_EXCLUDE_DEFAULT = "pinnacle,bovada,espnbet"
BEST_LINE_EXCLUDE_BOOKMAKERS = [
    b.strip().lower()
    for b in os.environ.get("BEST_LINE_EXCLUDE_BOOKMAKERS",
                            _BEST_LINE_EXCLUDE_DEFAULT).split(",")
    if b.strip()
]

BEST_LINE_BOOKMAKERS = [
    b for b in (
        b.strip().lower()
        for b in (os.environ.get("BEST_LINE_BOOKMAKERS")
                  or ",".join(LINE_SHOP_BOOKMAKERS)).split(",")
        if b.strip()
    )
    if b not in BEST_LINE_EXCLUDE_BOOKMAKERS
]

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

# NFL player prop markets (The Odds API americanfootball_nfl player-prop keys).
#
# PROVISIONAL KEY NAMES: these were not verified against a live API response —
# The Odds API is unreachable from the dev sandbox. NFL prop odds ingestion is
# owned by a separate workstream; if a key here disagrees with what that fetch
# actually returns, THIS list is the thing to correct (the DataGolf precedent).
# The market key is only ever used to look a price up — a wrong key means zero
# picks for that model, never a wrong pick.
#
# The list is deliberately a SUBSET of what DraftKings prices. Field goals,
# kicking points, passing interceptions, individual rush/rec TDs, longest
# rush/reception and first TD are all excluded — see docs/nfl_props_model.md §3
# for the measurement behind each exclusion (two of them have NEGATIVE
# out-of-sample R²: a tuned model is worse than the pooled mean).
PROP_MARKETS_NFL = [
    "player_pass_yds",
    "player_pass_attempts",
    "player_pass_completions",
    "player_pass_tds",
    "player_rush_yds",
    "player_rush_attempts",
    "player_reception_yds",
    "player_receptions",
    "player_rush_reception_yds",
    "player_anytime_td",
    "player_tackles_assists",
    "player_sacks",
]

# RETIRED 2026-09-02 (matt): mlb_prop_batter_hr (batter_home_runs) and
# mlb_prop_batter_rbi (batter_rbis). Removing them from this registry is what
# stops them: the prop scorer, the trainer, the calibration agent, the health
# checks and threshold_sync are all driven off these keys, so a retired model
# cannot score, cannot be retrained, carries no threshold row (threshold_sync
# prunes it, which is what drops it from every track-record view -- they all
# INNER JOIN model_action_thresholds) and writes no rows of any kind.
#
# Matt's call, 2026-09-02: remove both from the app and keep them out of every
# model total. The record at the time: HR 256 settled BETs 42-214 (a ~17%-hit
# longshot market whose +EV filter was anti-predictive against DK's efficient
# longshot line; already record-only, already excluded from the public
# record since 2026-07-04); RBI 293 settled BETs 214-79 lifetime, but only ONE
# of them clears the cut it was re-cut to on 2026-08-31, and its sweep was the
# most floor-distorted on the board (47.6% of the population refused by the
# -140 floor).
#
# Their picks stay in the DB and stay graded -- a pick that existed is the bet
# of record (S1c). paper_tracker._PROP_STAT_MAP and _PROP_MARKET_FOR_MODEL are
# keyed by model_id, NOT by this registry, and keep both entries so the 20
# unsettled BETs settle on the right stat and the closing line still resolves.
# The prop-odds INGEST (PROP_MARKETS_BATTER) is deliberately untouched: the
# markets keep flowing into prop_odds for the market-relative rule and any
# future model; retiring a model is not deleting its data.
#
# Reviving one means retraining it (the artifacts are deleted, the registry
# rows deactivated) and clearing the go-live gate first -- not just re-adding a
# key.
# Prop model IDs — one per market. Trained in Phase 2 after game-log backfill.
PROP_MODELS = {
    "mlb_prop_pitcher_k":    ("MLB", "pitcher_strikeouts",  "poisson",  "Priority 1"),
    "mlb_prop_pitcher_hits": ("MLB", "pitcher_hits_allowed","poisson",  ""),
    "mlb_prop_pitcher_er":   ("MLB", "pitcher_earned_runs", "poisson",  ""),
    "mlb_prop_pitcher_outs": ("MLB", "pitcher_outs",        "poisson",  ""),
    "mlb_prop_pitcher_walks":("MLB", "pitcher_walks",       "poisson",  ""),
    "mlb_prop_batter_hits":  ("MLB", "batter_hits",         "poisson",  ""),
    "mlb_prop_batter_tb":    ("MLB", "batter_total_bases",  "poisson",  ""),
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
    # NFL player props. The response family is per-market and is NOT the
    # platform's usual Poisson — NFL yardage has a variance-to-mean ratio of
    # 27-36 and even the count markets are overdispersed (pass attempts 3.7).
    # Under a Poisson head pass attempts miscalibrates by 8.3 percentage points;
    # negative binomial roughly halves calibration error on every overdispersed
    # market. TD counts really are Poisson (var/mean ~1.0) and are left there.
    # Evidence: docs/nfl_props_model.md §2.
    "nfl_prop_pass_yards":       ("NFL", "player_pass_yds",            "gamma",    "zero-inflated Gamma"),
    "nfl_prop_pass_attempts":    ("NFL", "player_pass_attempts",       "nbinom",   ""),
    "nfl_prop_pass_completions": ("NFL", "player_pass_completions",    "nbinom",   ""),
    "nfl_prop_pass_tds":         ("NFL", "player_pass_tds",            "poisson",  "var/mean ~1 — genuinely Poisson"),
    "nfl_prop_rush_yards":       ("NFL", "player_rush_yds",            "gamma",    "zero-inflated Gamma"),
    "nfl_prop_rush_attempts":    ("NFL", "player_rush_attempts",       "nbinom",   ""),
    "nfl_prop_rec_yards":        ("NFL", "player_reception_yds",       "gamma",    "zero-inflated Gamma"),
    "nfl_prop_receptions":       ("NFL", "player_receptions",          "nbinom",   ""),
    "nfl_prop_rush_rec_yards":   ("NFL", "player_rush_reception_yds",  "gamma",    "highest R2 of any NFL yardage market"),
    "nfl_prop_anytime_td":       ("NFL", "player_anytime_td",          "logistic", "binary, over-only, heavily juiced"),
    "nfl_prop_tackles_assists":  ("NFL", "player_tackles_assists",     "nbinom",   "most out-of-sample signal in the sport"),
    "nfl_prop_sacks":            ("NFL", "player_sacks",               "poisson",  "thin market — paper only"),
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

# The Odds API NFL team names → nflverse abbreviations. NFL prop odds arrive
# keyed by full team name and a kickoff timestamp; the modelling tables are
# keyed by the nflverse game id (NFL_2026_01_KC_BUF). This map is the bridge —
# the resolver looks the pair up in nfl_team_game_stats rather than
# constructing an id, so a wrong name yields a skipped event, never a wrong one.
# nflverse uses LA for the Rams and LAC for the Chargers; LV, JAX, WAS.
NFL_ODDS_API_MAP = {
    "Arizona Cardinals": "ARI",      "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",       "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",      "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",     "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",         "Denver Broncos": "DEN",
    "Detroit Lions": "DET",          "Green Bay Packers": "GB",
    "Houston Texans": "HOU",         "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",   "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV",       "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LA",        "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",      "New England Patriots": "NE",
    "New Orleans Saints": "NO",      "New York Giants": "NYG",
    "New York Jets": "NYJ",          "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",       "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN",       "Washington Commanders": "WAS",
    # historical names still present in older Odds API snapshots
    "Oakland Raiders": "LV",         "San Diego Chargers": "LAC",
    "St. Louis Rams": "LA",          "Washington Football Team": "WAS",
    "Washington Redskins": "WAS",
}

# nflverse snap counts (offensive/defensive/ST snap share, one row per player
# per game) — the availability signal behind the NFL prop models and the main
# driver of the tackles+assists market. Same release host as the weekly stats;
# published back to 2012. nflverse keys these on pfr_player_id with no gsis id,
# so the join to the weekly stats is on a normalised name + team + game id
# (see data/ingestors/nfl_props_data_ingestor.norm_player_name).
NFLVERSE_SNAP_COUNTS_URL_TMPL: str = os.environ.get(
    "NFLVERSE_SNAP_COUNTS_URL_TMPL",
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "snap_counts/snap_counts_{season}.csv")

# Earliest season the NFL prop modelling ingest keeps loaded. 2015 is the first
# year with complete usage shares and snap counts in nflverse.
NFL_MODEL_FIRST_SEASON: int = int(os.environ.get("NFL_MODEL_FIRST_SEASON", "2015"))

# How far ahead an NFL pick may be locked and published.
#
# Both §28 rules write picks with a FUTURE game_date and are INSERT-ONCE: an
# nfl_opener_spread pick locks in the T-7..T-2 window and is never re-priced
# (the edge IS the stale soft-book number), and nfl_wind_totals was switched to
# the same lock. So an NFL pick is the bet of record the moment it is written,
# and capture_opening_signals must reach forward to it — otherwise it would only
# be captured, and therefore only reach Discord and push, on GAME DAY, by which
# time the opener's number has been corrected and the bet no longer exists.
#
# 7 matches the opener's own LEAD_HI_DAYS (nfl/models/opener_spread.py); the
# wind card never reaches further than ~4 days out.
NFL_LOCK_AHEAD_DAYS: int = int(os.environ.get("NFL_LOCK_AHEAD_DAYS", "7"))

# How many seasons back the self-healing NFL player-stats ingest keeps loaded
# (current season + this many prior). The first run after deploy backfills
# them all; later runs only refresh the current season.
NFL_PLAYER_STATS_BACKFILL_SEASONS: int = int(
    os.environ.get("NFL_PLAYER_STATS_BACKFILL_SEASONS", "3"))


# ── NCAAF (college football, FBS) ─────────────────────────────────────────────
# CollegeFootballData.com is the SOLE history source: games, per-game team box
# scores, season + advanced stats (EPA / success rate / explosiveness / havoc),
# SP+/SRS/Elo ratings, 247 team talent composite, returning production — AND
# `/lines`, real historical spreads/totals/moneylines per provider. That last
# endpoint is why NCAAF totals and spreads are trainable at all: every other
# non-MLB totals/spread model in this repo is blocked on missing line history.
#
# Free tier: request a key at https://collegefootballdata.com/key (email only,
# no card). Rate-limited — the backfill is paced and resumable.
CFBD_API_KEY: str = os.environ.get("CFBD_API_KEY", "")
CFBD_BASE_URL: str = os.environ.get("CFBD_BASE_URL", "https://api.collegefootballdata.com")
# Seconds to sleep between CFBD calls during backfill (free-tier politeness).
CFBD_REQUEST_PAUSE: float = float(os.environ.get("CFBD_REQUEST_PAUSE", "0.6"))

# Which /lines providers to persist as historical training lines, in PREFERENCE
# ORDER. We ingest ALL of them rather than picking one, and the feature engine
# takes the first available per game — so no season is lost to a book that
# didn't exist yet, and DraftKings (the book we actually score against) is used
# wherever it exists.
#
# VERIFIED 2026-08-21 against a real key, seasons 2015-2025:
#     consensus      9 seasons   6,596 spreads
#     teamrankings   9 seasons   5,601 spreads
#     Bovada         7 seasons   4,883 spreads
#     DraftKings     3 seasons   2,255 spreads   (launched 2018, scaled 2019-21)
# No single provider covers the full window, which is why this is a list.
# Order matters: earlier entries win when several priced the same game.
CFBD_LINES_PROVIDERS: list = [
    p.strip() for p in os.environ.get(
        "CFBD_LINES_PROVIDERS",
        "DraftKings,Bovada,consensus,teamrankings").split(",") if p.strip()
]


def ncaaf_line_bookmaker(provider: str) -> str:
    """
    Bookmaker label for a backfilled CFBD line.

    Deliberately prefixed rather than bare: live DraftKings odds from The Odds
    API own the "draftkings" key and the scorer reads it, so an archive row
    must never be able to masquerade as a live price.
    """
    slug = "".join(c if c.isalnum() else "_" for c in str(provider).lower()).strip("_")
    return f"cfbd_{slug}"


# Ordered bookmaker labels the NCAAF feature engine will accept as a training
# line, best first. Live DraftKings rows come LAST: during the season a game
# has both, and the archive line is the one the historical target was built
# from, so preferring it keeps training and backtesting consistent.
NCAAF_LINE_BOOKMAKER_PRIORITY: list = (
    [ncaaf_line_bookmaker(p) for p in CFBD_LINES_PROVIDERS] + ["draftkings"]
)


# ── Calibration method override (per model) ───────────────────────────────────
# Default is Platt/sigmoid, which assumes a parametric logistic shape. That
# breaks down when a model is systematically overconfident rather than uniformly
# shifted — isotonic is non-parametric and fixes the tails, at the cost of
# needing more data (rule of thumb: >= ~1,000 rows) and a mild overfit risk.
#
# ncaaf_moneyline: holdout CalErr 17.2% on ~2,987 rows with a 63.75% home base
# rate. Its edge is model_prob - implied_prob, so a miscalibrated probability
# doesn't merely mis-size bets, it selects the WRONG GAMES — which is why this
# is worth one attempt before retiring the model.
MODEL_CALIBRATION_METHOD: dict = {
    "ncaaf_moneyline": os.environ.get("NCAAF_ML_CALIBRATION", "isotonic"),
}


def calibration_method(model_id: str) -> str:
    """Calibration method for a model — 'sigmoid' (Platt) unless overridden."""
    return MODEL_CALIBRATION_METHOD.get(model_id, "sigmoid")

# Prior-shrinkage strength for in-season NCAAF team stats. A CFB team plays
# 12-13 games a season, so a raw season-to-date average is noise for the first
# month. Every rate stat is blended with the team's PRIOR-season value:
#     blended = w * in_season + (1 - w) * prior,   w = games_played / (games_played + k)
# k = 4 means the prior still carries half the weight at 4 games played and
# ~24% at 13. This is the single most important modeling decision in the sport
# — a flat rolling average would make weeks 1-5 unusable.
NCAAF_PRIOR_SHRINKAGE_K: float = float(os.environ.get("NCAAF_PRIOR_SHRINKAGE_K", "4"))

# Below this many games played, the game is flagged is_early_season. Unlike MLB
# (which GATES picks on >= 10 games), NCAAF only FLAGS it — a 10-game gate
# would blank out three quarters of a 12-game season. The prior-shrinkage
# blender above is what actually makes early-season rows usable.
NCAAF_MIN_GAMES: int = int(os.environ.get("NCAAF_MIN_GAMES", "4"))

# Power-4 conferences (post-2024 realignment). Drives the `game_tier` feature:
# P4 primetime games are priced as sharply as the NFL, while midweek G5 games
# carry soft numbers and low limits — thresholds are expected to differ by tier.
NCAAF_POWER_CONFERENCES: set = {"SEC", "Big Ten", "ACC", "Big 12"}

# The Odds API team name → CFBD canonical school name.
#
# LOAD-BEARING CONVENTION: the canonical NCAAF team identifier is the CFBD
# SCHOOL NAME ("Ohio State", "Miami", "Miami (OH)"), NOT a 3-letter abbrev.
# 136 FBS programs collide badly in 3 letters, and CFBD is the source of truth
# for both the stats AND the historical lines, so joining on its school name is
# lossless. games.home_team/away_team store the school name; game_id uses a
# slug (see ncaaf_slug) — the same display-name/slug split UFC uses.
#
# The Odds API lists NCAAF teams with the mascot appended ("Ohio State
# Buckeyes"). data.ingestors.cfbd_ingestor.resolve_odds_api_school() strips it
# by matching against the ncaaf_teams table, so this dict only needs entries
# the automatic resolver gets WRONG. Populate it from the mismatch report that
# `python -m scripts.verify_cfbd` prints.
NCAAF_ODDS_API_MAP: dict = {
    # 2026-08-26: the resolver now folds case/accents/punctuation, which fixed
    # "San Jose State Spartans" -> "San José State" and "Hawaii Rainbow
    # Warriors" -> "Hawai'i" generically. Entries here are only for names the
    # fold cannot bridge (a genuinely different school name).
    "Appalachian State Mountaineers": "App State",
    "Appalachian State": "App State",
    "UMass Minutemen": "Massachusetts",
    "UMass": "Massachusetts",
}

# The Odds API fighter name → ufcstats.com fighter name overrides.
# Fighter identity is matched by slugified full name (lowercase, accents
# stripped, punctuation removed), which handles almost everyone. Add an entry
# here when the books and ufcstats disagree on a name (nicknames, "Jr.",
# transliteration differences). Keys are Odds API names, values ufcstats names.
UFC_NAME_ALIASES: dict = {
    # The Odds API and ufcstats spell a meaningful minority of fighters
    # differently — middle names, nicknames-as-first-names, transliterations,
    # generational suffixes. Left unmapped, the two sources slugify to
    # different keys, the odds feed creates its own `games` row, and that row
    # NEVER receives a score (its picks can never settle) while the results
    # ingest writes to a separate row. Every entry below was confirmed against
    # the `fighters` table; keys are the Odds API spelling, values the ufcstats
    # one. `_resolve_game_rows` also carries a fallback that catches unmapped
    # variants at settlement — but an alias is strictly better, because it
    # makes both sources build the SAME game_id and no duplicate row is ever
    # created. When the fallback logs "resolved by anchor", add the pair here.
    "Ian Garry": "Ian Machado Garry",
    "Sergey Spivak": "Serghei Spivac",
    "Billy Goff": "Billy Ray Goff",
    "Carlos Diego Ferreira": "Diego Ferreira",
    "Giovanna Canuto": "Gigi Canuto",
    "Yadier DelValle": "Yadier del Valle",
    "L'udovit Klein": "Ludovit Klein",
    "Seok Hyun Ko": "Seokhyeon Ko",
    "Asu Almabaev": "Asu Almabayev",
    "Abdulrakhman Yakhyaev": "Abdul Rakhman Yakhyaev",
    "Abusupyian Magomedov": "Abus Magomedov",
    "Beatriz Mesquita": "Bia Mesquita",
    "Nursultan Ruziboev": "Nursulton Ruziboev",
    "Javier Reyes Rugeles": "Javier Reyes",
    "Steve Garcia Jr.": "Steve Garcia",
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

# NCAAF plays one slate a week and DK prices it days ahead, so same-day-only
# scoring left the board empty for six days out of seven — and, worse, made the
# cross-book opener rule structurally dormant: it only fires while DK is STILL
# on its opening number, which is rarely true by kickoff. Score the whole week.
#
# The look-ahead interacts with the pick lock deliberately (see run_scorer): an
# NCAAF row carrying an actual signal locks at first cross — that IS the opener
# rule's thesis — while a "no signal" row is refreshed every pass, so a model
# that forms a view mid-week can still fire.
NCAAF_SCORE_AHEAD_DAYS: int = int(os.environ.get("NCAAF_SCORE_AHEAD_DAYS", "7"))

# ...but only the OPENER rule was validated at a long lead. The totals
# regression was walked forward against the archive's stored line per game, not
# against an opener a week out, so firing it at any lead the look-ahead happens
# to expose would ship an untested rule. It may well be better early (that is
# the usual CLV story) — it is simply not measured, so the default keeps the
# behaviour that was: fire on game day, watch (no signal) before it.
NCAAF_TOTALS_MAX_LEAD_DAYS: float = float(
    os.environ.get("NCAAF_TOTALS_MAX_LEAD_DAYS", "1")
)

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


# ── The one definition of "today" ─────────────────────────────────────────────
# Every game_date in this database is an EASTERN date (run_pipeline has always
# derived run_date this way). `date.today()` returns the CONTAINER's date, so on
# a UTC host it rolls over at 8pm ET and starts naming tomorrow -- which is how
# the live loop came to report "no active games" every night from 8pm ET while
# games were plainly in progress (2026-08-30). Nothing that resolves a game_date
# may use date.today(); use this.
#
# It does not depend on the TZ environment variable being set, deliberately: a
# correctness property this load-bearing should not be one dashboard edit away
# from silently reverting.
def today_et() -> str:
    """Today's date in America/New_York, ISO. The canonical `game_date` clock."""
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo as _Z
    return _dt.now(_Z("America/New_York")).strftime("%Y-%m-%d")


# ── Which dates a LIVE loop must ask about ───────────────────────────────────
# `today_et()` alone is the wrong question for anything polling games that are
# IN PROGRESS, and this is the other half of the bug #296 fixed.
#
# A game carries the game_date of its FIRST PITCH. A 10:08pm ET start in
# Anaheim is in the fourth inning at 00:30 ET the NEXT day -- and at midnight
# the loops stopped asking for it, because they asked for "today's games" and
# it is no longer today's game. #296 moved the blind spot from 8pm ET to
# midnight ET; it did not remove it.
#
# Measured 2026-08-30 against DraftKings' own feed: the last in-play row on
# 2026-08-29 landed at 23:50:35 ET, while DK went on quoting PHI@LAA, ARI@SF
# and BAL@ATH until 01:07 ET. Seventy-seven minutes of live baseball, three
# games, no prices, no picks -- and, exactly as in #296, no error, because "no
# games today" is also what an empty slate looks like.
#
# Yesterday is included only in the early-ET window where one of its games
# could still plausibly be running. Every caller already filters on live status
# (Final and not-yet-started are dropped), so a spare date costs one lookup and
# can never widen what actually gets scored.
LIVE_SLATE_LOOKBACK_UNTIL_HOUR_ET: int = int(
    os.environ.get("LIVE_SLATE_LOOKBACK_UNTIL_HOUR_ET", 6))


def live_slate_dates(now=None) -> list[str]:
    """Every ET game_date whose games could still be in progress right now.

    Newest first, so a caller that wants one date still gets today. Use this
    anywhere a LIVE loop resolves which games to poll, price or score; use
    today_et() for anything about the day's slate as a unit.

    `now` is injectable ONLY so the midnight boundary can be tested at the
    boundary. This failure is invisible at runtime -- an empty slate and a
    missed slate log the same line -- so it needs a test that can stand at
    00:30 ET on demand.
    """
    from datetime import datetime as _dt, timedelta as _td
    from zoneinfo import ZoneInfo as _Z
    now = now or _dt.now(_Z("America/New_York"))
    dates = [now.strftime("%Y-%m-%d")]
    if now.hour < LIVE_SLATE_LOOKBACK_UNTIL_HOUR_ET:
        dates.append((now - _td(days=1)).strftime("%Y-%m-%d"))
    return dates


# ── Intraday freshness for the model's own inputs ────────────────────────────
# The refresh pass re-reads the MARKET every 10-60 minutes (odds, prop odds,
# lineups, public splits) but until 2026-08-30 it re-read the MODEL'S INPUTS
# only at 6am. So the price moved all day against a view of who was hurt, and
# what the weather would be, that was frozen at breakfast.
#
# That gap is what makes a late-crossing pick dangerous: if a number drifts
# because a starter was scratched at 2pm, taking it at 6pm is betting against
# information we chose not to re-read. mike, 2026-08-30: "shouldnt we be
# modeling on datapoints like pitchers and injuries and the like?"
#
# Sized as a MAX AGE rather than a cadence, so the guard holds however often
# the pass runs -- 42 passes a day must not become 42 ESPN sweeps. ESPN has
# IP-blocked this worker twice (sessions 112, 115), so these are deliberately
# env-overridable: they can be dialled back without a deploy.
REFRESH_INJURY_MAX_AGE_MIN: int = int(
    os.environ.get("REFRESH_INJURY_MAX_AGE_MIN", 45))
REFRESH_WEATHER_MAX_AGE_MIN: int = int(
    os.environ.get("REFRESH_WEATHER_MAX_AGE_MIN", 60))


# ── Player news ───────────────────────────────────────────────────────────────
# The feed behind the "Recent News" sheet the prop screens open from their
# top-right icon. A prop is a bet on one player, so the note that he is on a
# pitch count, or was scratched, is the most decision-relevant thing there is
# next to the number -- and it is the one thing the pick card never showed.
#
# PROVIDER IS A SETTING, NOT A HARD-CODE. 'espn' is the default because it is
# free, needs no key, and reuses the hidden API this repo already reads for
# injuries. What it returns is ARTICLES (headline + summary), not the per-player
# fantasy notes with an ANALYSIS paragraph that RotoWire syndicates -- those are
# licensed, and `player_news.analysis` plus PLAYER_NEWS_PROVIDER exist so a paid
# feed drops in behind the same table and the same sheet without a rewrite.
PLAYER_NEWS_PROVIDER: str = os.environ.get("PLAYER_NEWS_PROVIDER", "espn")

# Sports the news ingest covers. Only sports with a player detail screen are
# worth fetching -- the sheet has nowhere to open from otherwise.
PLAYER_NEWS_SPORTS: list[str] = [
    s.strip().upper()
    for s in os.environ.get("PLAYER_NEWS_SPORTS", "MLB,NBA,WNBA,NFL").split(",")
    if s.strip()
]

# ESPN league paths for the news feed, keyed by our sport label.
ESPN_NEWS_PATHS: dict[str, str] = {
    "MLB":   "baseball/mlb",
    "NBA":   "basketball/nba",
    "WNBA":  "basketball/wnba",
    "NFL":   "football/nfl",
    "NHL":   "hockey/nhl",
    "NCAAF": "football/college-football",
}

# Same shape as REFRESH_INJURY_MAX_AGE_MIN, and for the same reason: sized as a
# MAX AGE rather than a cadence so ~42 refresh passes a day cannot become 42
# ESPN sweeps. ESPN has IP-blocked this worker twice (sessions 112, 115).
REFRESH_PLAYER_NEWS_MAX_AGE_MIN: int = int(
    os.environ.get("REFRESH_PLAYER_NEWS_MAX_AGE_MIN", 60))

# Per-run ceiling on team-scoped ESPN news calls. The league feed returns ~10
# items; a team feed adds ~10 more per team, which is the only way to reach a
# bench bat or a fifth starter. Capped, and spent on the teams that actually
# have a pick today, so coverage improves without a 30-team sweep.
PLAYER_NEWS_MAX_TEAM_FETCHES: int = int(
    os.environ.get("PLAYER_NEWS_MAX_TEAM_FETCHES", 12))

# How many days of notes to keep. Older than this is history, not news; the
# sheet shows the most recent few and the table is a cache we can always re-read.
PLAYER_NEWS_RETENTION_DAYS: int = int(
    os.environ.get("PLAYER_NEWS_RETENTION_DAYS", 21))
