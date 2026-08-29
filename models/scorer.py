"""
scorer.py — Daily scoring: generate BET/AVOID signals for today's games.

For each game scheduled today:
  1. Build feature vector
  2. Get model probability
  3. Compute edge vs. DraftKings implied probability
  4. Apply injury flags and early season filter
  5. Classify as BET (edge ≥ +3%), AVOID (edge ≤ −3%), or no signal
  6. Size bets with Quarter-Kelly formula
  7. Log picks to the picks table

Usage:
    python -m models.scorer                    # score today
    python -m models.scorer --date 2025-04-15  # score a specific date
    python -m models.scorer --dry-run          # preview without writing to DB
"""

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
import os
import sys
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np
from loguru import logger

try:
    import statsapi
    STATSAPI_AVAILABLE = True
except ImportError:
    STATSAPI_AVAILABLE = False

sys.path.insert(0, str(Path(__file__).parent.parent))
from scipy import stats as scipy_stats

from config import (
    BANKROLL,
    BEST_LINE_BOOKMAKERS,
    BET_EDGE_THRESHOLD,
    AVOID_EDGE_THRESHOLD,
    MIN_MODEL_PROB,
    MODEL_EDGE_THRESHOLDS,
    MODEL_PROB_THRESHOLDS,
    MAX_EDGE_CAP,
    MAX_KELLY_FRACTION,
    KELLY_MULTIPLIER,
    MIN_GAMES_BASELINE,
    F5_TOTAL_FACTOR,
    MODELS,
    MODEL_BET_SIZE_MULTIPLIER,
    ODDS_API_BOOKMAKER,
    MODEL_MIN_ODDS,
    REQUIRE_DK_PRICE,
    PAUSED_MODELS,
    LOCK_GAME_PICKS_AT_FIRST_RUN,
    LOCK_PROP_PICKS_AT_FIRST_SIGNAL,
    PROB_ONLY_MODELS,
    PROP_MODELS,
    SPORTS,
    UFC_SCORE_AHEAD_DAYS,
    GOLF_SCORE_AHEAD_DAYS,
    NCAAF_SCORE_AHEAD_DAYS,
    NCAAF_TOTALS_MAX_LEAD_DAYS,
    PROP_MARKETS_NFL,
)
from data.db import get_connection, DBConnection

# Max minutes two books' opening snapshots may be apart and still count as
# "simultaneous" for the NCAAF cross-book opener rule. A refresh pass is ~60
# min, so 90 tolerates one book appearing a pass late without admitting the
# multi-day skew that would turn plain line drift into a fake edge.
OPENER_MAX_SKEW_MIN = float(os.environ.get("NCAAF_OPENER_MAX_SKEW_MIN", "90"))
from features.feature_engine import (
    FEATURE_MAP,
    build_mlb_game_features,
    build_nhl_game_features,
)
from features.prop_feature_engine import (
    PROP_FEATURE_MAP,
    build_pitcher_scoring_rows,
    build_batter_scoring_rows,
)
from models.trainer import load_model

# ── Odds Conversion ────────────────────────────────────────────────────────────

def american_to_implied_prob(american_odds: float) -> float:
    """
    Convert American moneyline odds to implied probability.
    Accounts for the vig: we use the raw implied (not vig-stripped) for edge calc.
    """
    if american_odds is None:
        return None
    if american_odds > 0:
        return 100 / (american_odds + 100)
    else:
        return abs(american_odds) / (abs(american_odds) + 100)


def american_to_decimal(american_odds: float) -> float:
    """Convert American odds to decimal (returns per unit bet including stake)."""
    if american_odds is None:
        return None
    if american_odds > 0:
        return (american_odds / 100) + 1
    else:
        return (100 / abs(american_odds)) + 1


# ── Kelly Sizing ──────────────────────────────────────────────────────────────

def quarter_kelly(model_prob: float, implied_prob: float,
                  bankroll: float) -> tuple[float, float]:
    """
    Quarter-Kelly bet sizing formula:
        f_q = KELLY_MULTIPLIER × (P - IP) / (1 - IP)

    Capped at MAX_KELLY_FRACTION × bankroll.

    Args:
        model_prob:   our model's estimated win probability
        implied_prob: bookmaker's implied win probability
        bankroll:     current paper trading bankroll

    Returns:
        (kelly_fraction, recommended_bet_dollars)
    """
    edge = model_prob - implied_prob
    if edge <= 0:
        return 0.0, 0.0

    denominator = 1.0 - implied_prob
    if denominator <= 0:
        return 0.0, 0.0

    f_raw = KELLY_MULTIPLIER * edge / denominator
    f_capped = min(f_raw, MAX_KELLY_FRACTION)
    bet_dollars = round(f_capped * bankroll, 2)

    return round(f_capped, 6), bet_dollars


# ── Injury Flag Builder ────────────────────────────────────────────────────────

def _build_injury_flag(features: dict, sport: str, pick_side: str) -> tuple[str, str]:
    """
    Derive an injury flag and detail string from the feature vector.
    Returns (flag_code, human_readable_detail).
    """
    side = "home" if pick_side == "home" else "away"
    opp  = "away" if pick_side == "home" else "home"

    flags = []
    details = []

    our_adj = features.get(f"{side}_injury_adj", 0)
    opp_adj = features.get(f"{opp}_injury_adj", 0)
    our_returnee = features.get(f"{side}_has_returnee", 0)

    # starter_out is intentionally excluded from the display flag:
    # _has_starter_out() fires for any IL10/IL15/IL60 player (no position data),
    # so it triggers on every team and is meaningless as a warning signal.
    # The feature is still used by the model (training consistency preserved).

    if our_returnee:
        flags.append("returning")
        details.append("Player returning from IL (ramp factor applied)")

    if opp_adj >= 0.7 and our_adj < 0.3:
        flags.append("opponent_edge")
        details.append(f"Opponent injury burden: {opp_adj:.2f}")

    if not flags:
        return None, None

    flag_code = "combined" if len(flags) > 1 else flags[0]
    return flag_code, " | ".join(details)


# ── Confidence Tier ───────────────────────────────────────────────────────────

def _confidence_tier(edge: float) -> str:
    abs_edge = abs(edge)
    if abs_edge >= 0.08:
        return "HIGH"
    elif abs_edge >= 0.05:
        return "MED"
    else:
        return "LOW"


# ── Pick Label Builder ────────────────────────────────────────────────────────

def _build_pick_label(pick_side: str, home_team: str, away_team: str,
                       market: str, line: float | None = None) -> str:
    """Human-readable pick label including line where applicable."""
    # Determine if this is a first-5-innings market
    f5_tag = " F5" if "1st_5_innings" in market else ""

    if market in ("h2h", "h2h_3way", "h2h_1st_5_innings"):
        team = home_team if pick_side == "home" else away_team
        return f"{team} ML{f5_tag}"
    elif market in ("totals", "totals_1st_5_innings"):
        direction = "Over" if pick_side == "over" else "Under"
        line_str = f" {line}" if line is not None else ""
        return f"{home_team} vs {away_team} {direction}{line_str}{f5_tag}"
    elif market in ("spreads", "spreads_1st_5_innings"):
        team = home_team if pick_side == "home" else away_team
        if line is not None:
            spread = line if pick_side == "home" else -line
            sign = "+" if spread > 0 else ""
            return f"{team} {sign}{spread:.1f}{f5_tag}"
        return f"{team} {pick_side.title()} Spread{f5_tag}"
    return f"{pick_side.upper()}"


# ── Core Scorer ───────────────────────────────────────────────────────────────

def _feature_value(v):
    """Serve-time feature encoding: missing (None) → NaN, real values kept as
    float (so a legitimate 0 like is_dome_game=0 / wind=0 is preserved). Never
    0-fill a missing value — an impossible 0.00 rate stat (ERA/WHIP/K9) is
    out-of-distribution and skews XGBoost, which handles NaN natively."""
    return np.nan if v is None else float(v)


def score_game(conn: DBConnection,
               game_id: str,
               model_id: str,
               features: dict,
               bankroll: float,
               dry_run: bool = False,
               commence_time: str | None = None) -> list[dict]:
    """
    Score one game with one model. Generates 0, 1, or 2 pick rows
    (BET and/or AVOID signals).

    Returns list of pick dicts ready for DB insert.
    """
    sport, market, _ = MODELS[model_id]
    feature_cols = FEATURE_MAP[model_id]

    # Guard: MLB game models lean most heavily on the probable starter's ERA
    # (the top feature for O/U, ML and RL). The day's probable starters don't
    # land in mlb_pitcher_stats until mid-morning, and the live feature vector
    # 0-fills anything missing (see below) — a 0.00 ERA is an impossible/elite
    # value that sends the model out-of-distribution and fires spurious (almost
    # always "under") BETs which then correct the moment real ERAs load. Skip
    # rather than emit a pick off absent starter data. MLB-only: home_starter_era
    # is an MLB feature key, so this never trips for other sports. Genuine
    # TBD/bullpen-game starters stay unscored all day (correct — don't bet on
    # missing data). Mirrors the backtester's null-feature skip.
    if sport == "MLB" and (
        features.get("home_starter_era") is None
        or features.get("away_starter_era") is None
    ):
        logger.debug(
            f"  {game_id}/{model_id}: probable starter not loaded — skipping"
        )
        return []

    # Load model artifact
    artifact = load_model(model_id)
    if artifact is None:
        logger.warning(f"Skipping {game_id}/{model_id} — no trained model")
        return []

    clf          = artifact["model"]
    feat_cols    = artifact.get("feature_cols", feature_cols)

    # Overlay the market-specific line into the feature vector. The caller
    # builds features ONCE per game from the h2h odds row (which has no
    # total_line/spread_home), so without this override every totals model
    # predicts with total_line = NaN and every spreads model with
    # spread_home = NaN — while training always has them populated (top-6
    # feature for O/U). That train/serve skew shifted live O/U probabilities
    # ~5pp under vs the validated backtest path (found 2026-07-05). Applies
    # to full-game totals/spreads AND the F5 variants; UFC totals has its own
    # override below (it also derives is_five_rounds from the line).
    feat = features
    if (market in ("totals", "spreads") and sport != "UFC") or "1st_5_innings" in market:
        mkt_odds = _get_dk_odds(conn, game_id, market)
        if mkt_odds:
            feat = dict(features)  # shallow copy to avoid mutating shared dict
            if mkt_odds.get("total_line") is not None:
                feat["total_line"] = mkt_odds["total_line"]
            if mkt_odds.get("spread_home") is not None:
                feat["spread_home"] = mkt_odds["spread_home"]

    # For UFC totals/method, the round-total line (when DK carries it) also
    # tells us the bout length: a line ≥ 3.5 only exists for 5-round fights.
    if sport == "UFC" and market in ("totals", "method"):
        ufc_t_odds = _get_dk_odds(conn, game_id, "totals")
        if ufc_t_odds and ufc_t_odds.get("total_line") is not None:
            feat = dict(features)
            feat["total_line"] = ufc_t_odds["total_line"]
            feat["is_five_rounds"] = int(float(ufc_t_odds["total_line"]) >= 3.5)

    # Build feature vector. Pass genuinely-missing features as NaN (XGBoost
    # handles NaN natively, and training drops null-feature rows so NaN is the
    # intended serve-time encoding) — NOT 0.0. A 0-fill turns a missing rate
    # stat into an impossible value (ERA/WHIP/K9 of 0.0) that is out-of-
    # distribution and skews the prediction. Real zeros (is_dome_game=0, wind=0)
    # are preserved.
    x = np.array([_feature_value(feat.get(c)) for c in feat_cols],
                  dtype=float).reshape(1, -1)

    home_team = features.get("home_team", "")
    away_team = features.get("away_team", "")
    game_date = features.get("game_date", "")

    # UFC method of victory — 3-class, prob-only (no DK odds via The Odds API).
    # Handled before the binary predict below (probs has 3 entries).
    if market == "method":
        return _score_ufc_method(conn, game_id, model_id, sport, game_date,
                                 home_team, away_team, clf, x, features,
                                 bankroll, dry_run, commence_time)

    # NHL regulation 3-way — 3-class (away reg win / draw / home reg win),
    # priced against DK's h2h_3way market. Also handled before the binary
    # predict (probs has 3 entries). Skips when DK doesn't list the market.
    if market == "h2h_3way":
        return _score_nhl_3way(conn, game_id, model_id, sport, game_date,
                               home_team, away_team, clf, x, features,
                               bankroll, dry_run, commence_time)

    # A model can decline to BET a game and still have something worth
    # showing. When a rule's gate/preconditions fail we set a reason here and
    # fall through to the stock side-evaluation: the row is written, carries
    # DK's live number, and is forced to NONE below. An empty board and a
    # broken pipeline look identical to a user, and on 2026-08-29 they were.
    no_signal: str | None = None

    # Get model probability
    if artifact.get("kind") == "margin_regression":
        # NCAAF spread margin artifact (scripts/ncaaf_margin_eval --fit): the
        # model predicts the MARGIN from fundamentals — the market number is
        # deliberately not in its feature list — and the probability is the
        # OOS residual ECDF evaluated at the disagreement with DK's live
        # spread. No DK spread → nothing to disagree with → skip (never
        # prob-only). Falls through to the stock spreads side-evaluation, so
        # labels, thresholds, Kelly and NONE rows are unchanged machinery.
        m_odds = _get_dk_odds(conn, game_id, market)
        if not m_odds or m_odds.get("spread_home") is None:
            logger.debug(f"  {game_id}/{model_id}: no DK spread — margin model skipped")
            return []
        try:
            pred_margin = float(clf.predict(x)[0])
        except Exception as exc:
            logger.error(f"  Prediction error for {game_id}/{model_id}: {exc}")
            return []
        from features.ncaaf_feature_engine import margin_cover_prob
        disagreement = pred_margin + float(m_odds["spread_home"])
        home_prob = margin_cover_prob(artifact.get("residuals"), disagreement)
        away_prob = 1.0 - home_prob
    elif artifact.get("kind") == "cross_book_opener":
        home_prob, away_prob, no_signal = _opener_rule(
            conn, game_id, model_id, market, artifact)
        if home_prob is None:
            return []
    elif artifact.get("kind") == "total_regression":
        # NCAAF totals regression (scripts/ncaaf_margin_eval --fit-totals).
        # Same shape as the margin artifact above: predict the TOTAL from
        # fundamentals (the market number is deliberately not a feature), then
        # take the probability from the OOS residual ECDF at the disagreement
        # with DK's live total. No DK total -> nothing to disagree with ->
        # skip, never prob-only.
        #
        # SIGN CONVENTION (differs from spreads, and getting it backwards
        # inverts every pick): spreads are stored home-relative and a cover is
        # margin + spread_home > 0, so disagreement ADDS the line. Totals are
        # absolute and the over wins on actual > line, so disagreement
        # SUBTRACTS it. Unit-tested in tests/test_ncaaf_totals_regression.py.
        t_odds = _get_dk_odds(conn, game_id, market)
        if not t_odds or t_odds.get("total_line") is None:
            logger.debug(f"  {game_id}/{model_id}: no DK total — totals model skipped")
            return []
        try:
            pred_total = float(clf.predict(x)[0])
        except Exception as exc:
            logger.error(f"  Prediction error for {game_id}/{model_id}: {exc}")
            return []
        from features.ncaaf_feature_engine import total_over_prob
        disagreement = pred_total - float(t_odds["total_line"])

        # `home_prob` is repurposed as P(over) by the stock totals path below.
        home_prob = total_over_prob(artifact.get("residuals"), disagreement)
        away_prob = 1.0 - home_prob

        # Lead guard — see config.NCAAF_TOTALS_MAX_LEAD_DAYS. The look-ahead
        # window exists so the BOARD is populated all week; this rule was only
        # ever validated against the archive's stored line, so it still fires
        # on game day and merely watches before it.
        lead = _days_until(commence_time)
        if lead is not None and lead > NCAAF_TOTALS_MAX_LEAD_DAYS:
            no_signal = f"watching — prices on game day ({lead:.0f}d out)"

        # Enforce the VALIDATED SYMMETRIC gate here rather than relying on a
        # single probability floor to imply it.
        #
        # The OOS residuals are not centred (mean -0.62), so the ECDF is
        # asymmetric: +8 of disagreement gives P(over)=0.650 while -8 gives
        # P(over)=0.290, i.e. P(under)=0.710. A lone prob threshold of 0.650
        # would therefore fire OVER picks at >= +8.0 (what the walk-forward
        # validated) but UNDER picks at about -5 (what it did NOT -- the
        # +/-5.5 gate was only +3.7%). That ships a looser, untested rule on
        # one side while looking correct in config. It is also why an
        # inside-the-gate game is forced to NONE below rather than left to the
        # thresholds: the under side can clear 0.65 on its own.
        gate = float(artifact.get("d_threshold") or 0.0)
        if not no_signal and gate and abs(disagreement) < gate:
            logger.debug(f"  {game_id}/{model_id}: |disagreement| "
                         f"{abs(disagreement):.1f} < gate {gate} — no signal")
            no_signal = (f"model {pred_total:.0f} vs line "
                         f"{float(t_odds['total_line']):.0f} — inside the "
                         f"{gate:g}-pt gate")
    else:
        try:
            probs = clf.predict_proba(x)[0]
            home_prob = float(probs[1])
            away_prob = 1.0 - home_prob
        except Exception as exc:
            logger.error(f"  Prediction error for {game_id}/{model_id}: {exc}")
            return []

    # Get DK odds
    odds = _get_dk_odds(conn, game_id, market)

    # F5 models — only score against real DK odds.
    # h2h_1st_5_innings: DK carries this, fetched at 11am. Score normally when present.
    # totals/spreads_1st_5_innings: DK does not carry these at any tier. Disabled until
    # real lines are available. Do not use prob-only fallback for any F5 market.
    if not odds and "1st_5_innings" in market:
        logger.debug(f"  {game_id}/{model_id}: no real DK F5 odds — skipping")
        return []

    # UFC round totals without DK lines — prob-only vs the synthetic line the
    # feature row carries (2.5 / 4.5). Same convention as the old F5 prob-only
    # path: edge = model_prob − 0.50, dk_odds NULL, settled at −110 flat.
    if not odds and sport == "UFC" and market == "totals":
        return _score_ufc_totals_prob_only(
            conn, game_id, model_id, sport, game_date, home_team, away_team,
            home_prob, away_prob, feat, features, bankroll, dry_run, commence_time)

    if not odds:
        logger.debug(f"  No DK odds for {game_id}/{model_id}")
        return []

    picks = []

    spread_home = odds.get("spread_home")
    total_line  = odds.get("total_line")

    if market in ("h2h", "spreads",
                  "h2h_1st_5_innings", "spreads_1st_5_innings"):
        # ── Evaluate home side ────────────────────────────────────────────────
        home_dk_odds = odds.get("home_price")
        if home_dk_odds is not None:
            home_ip = american_to_implied_prob(home_dk_odds)
            if home_ip:
                home_edge = home_prob - home_ip
                pick = _make_pick(
                    game_id, model_id, sport, game_date,
                    pick_side="home",
                    pick_label=_build_pick_label("home", home_team, away_team, market, spread_home),
                    model_prob=home_prob,
                    dk_implied_prob=home_ip,
                    edge=home_edge,
                    dk_odds=home_dk_odds,
                    scored_line=spread_home,
                    bankroll=bankroll,
                    features=features,
                    commence_time=commence_time,
                )
                if pick:
                    picks.append(pick)

        # ── Evaluate away side ─────────────────────────────────────────────────
        away_dk_odds = odds.get("away_price")
        if away_dk_odds is not None:
            away_ip = american_to_implied_prob(away_dk_odds)
            if away_ip:
                away_edge = away_prob - away_ip
                pick = _make_pick(
                    game_id, model_id, sport, game_date,
                    pick_side="away",
                    pick_label=_build_pick_label("away", home_team, away_team, market, spread_home),
                    model_prob=away_prob,
                    dk_implied_prob=away_ip,
                    edge=away_edge,
                    dk_odds=away_dk_odds,
                    scored_line=spread_home,
                    bankroll=bankroll,
                    features=features,
                    commence_time=commence_time,
                )
                if pick:
                    picks.append(pick)

    elif market in ("totals", "totals_1st_5_innings"):
        over_odds  = odds.get("over_price")
        under_odds = odds.get("under_price")

        # Model prob for "home_win" is repurposed as "over" in totals model
        over_prob  = home_prob
        under_prob = away_prob

        for side, model_p, dk_odds_val in [
            ("over",  over_prob,  over_odds),
            ("under", under_prob, under_odds),
        ]:
            if dk_odds_val is None:
                continue
            ip   = american_to_implied_prob(dk_odds_val)
            edge = model_p - ip
            pick = _make_pick(
                game_id, model_id, sport, game_date,
                pick_side=side,
                pick_label=_build_pick_label(side, home_team, away_team, market, total_line),
                model_prob=model_p,
                dk_implied_prob=ip,
                edge=edge,
                dk_odds=dk_odds_val,
                scored_line=total_line,
                bankroll=bankroll,
                features=features,
                commence_time=commence_time,
            )
            if pick:
                picks.append(pick)

    # Attach public betting coverage (% of bets / % of money) per side, so the
    # daily picks output can surface it alongside model probability and edge.
    # Also stamp the DK betslip deep link for the picked selection.
    for p in picks:
        p.update(_get_public_betting(conn, game_id, market, p["pick_side"]))
        p["dk_bet_link"] = _link_for_side(odds, p["pick_side"])
    # The price the bettor should actually take, and where. Stamped after the
    # pick is decided so it can never influence the BET/AVOID call.
    _stamp_best_game_prices(conn, picks, market)

    # A declined rule must not leak a signal. Forcing NONE here rather than
    # leaning on the prob/edge thresholds is deliberate: the totals ECDF is
    # asymmetric (OOS residual mean -0.62), so an inside-the-gate game can
    # still hand the UNDER side a probability above the 0.65 floor and would
    # otherwise fire a BET the walk-forward never validated.
    if no_signal:
        for p in picks:
            p["signal_type"]     = "NONE"
            p["kelly_fraction"]  = 0.0
            p["recommended_bet"] = 0.0

    # Write to DB
    if picks and not dry_run:
        _insert_picks(conn, picks)

    return picks


def _get_synthetic_f5_line(conn, game_id: str) -> float | None:
    """
    Derive a synthetic F5 total line from the full-game totals odds row.
    Returns None if no full-game totals row exists for the game.
    """
    row = conn.execute("""
        SELECT total_line FROM odds
        WHERE game_id   = %s
          AND market    = 'totals'
          AND bookmaker IN ('draftkings', 'sbr_consensus')
          AND total_line IS NOT NULL
        ORDER BY CASE bookmaker WHEN 'draftkings' THEN 0 ELSE 1 END,
                 snapshot_at DESC
        LIMIT 1
    """, (game_id,)).fetchone()
    if row is None:
        return None
    # Round to nearest 0.5 to match typical bookmaker line granularity
    raw = float(row[0]) * F5_TOTAL_FACTOR
    return round(raw * 2) / 2


def _score_f5_prob_only(
    game_id: str, model_id: str, sport: str, game_date: str, market: str,
    home_team: str, away_team: str, home_prob: float, away_prob: float,
    features: dict, bankroll: float, dry_run: bool, conn,
    commence_time: str | None = None,
) -> list[dict]:
    """
    Probability-only scoring for F5 models when no DK F5 odds exist.
    Uses model probability threshold only (no edge computation).
    Edge is stored as model_prob - 0.50 for record-keeping.
    Kelly sizing uses implied_prob=0.5 (fair line) — same formula as full-game models.
    """
    # F5 markets DK does not carry. Same rule: no market price, no bet.
    if REQUIRE_DK_PRICE:
        logger.debug(f"  {game_id}/{model_id}: no DK F5 line — skipped "
                     f"(REQUIRE_DK_PRICE)")
        return []

    prob_thresh = MODEL_PROB_THRESHOLDS.get(model_id, MIN_MODEL_PROB)
    edge_thresh = MODEL_EDGE_THRESHOLDS.get(model_id, BET_EDGE_THRESHOLD)
    picks = []

    if market == "h2h_1st_5_innings":
        sides = [
            ("home", home_prob, home_team),
            ("away", away_prob, away_team),
        ]
        for pick_side, model_prob, team in sides:
            if model_prob < prob_thresh:
                continue

            synthetic_edge = model_prob - 0.50
            if synthetic_edge < edge_thresh:
                continue

            pick_label = _build_pick_label(pick_side, home_team, away_team, market)
            inj_flag, inj_detail = _build_injury_flag(features, sport, pick_side)
            kelly_frac, rec_bet = quarter_kelly(model_prob, 0.5, bankroll)

            pick = {
                "game_id":           game_id,
                "model_id":          model_id,
                "sport":             sport,
                "game_date":         game_date,
                "pick_side":         pick_side,
                "pick_label":        pick_label,
                "model_probability": round(model_prob, 4),
                "dk_implied_prob":   0.5,
                "edge":              round(synthetic_edge, 4),
                "dk_odds":           None,
                "scored_line":       None,
                "kelly_fraction":    kelly_frac,
                "recommended_bet":   rec_bet,
                "bankroll_at_pick":  bankroll,
                "injury_flag":       inj_flag,
                "injury_detail":     inj_detail,
                "signal_type":       "BET",
                "confidence_tier":   _confidence_tier(synthetic_edge),
                "game_time":         commence_time,
            }
            picks.append(pick)
            logger.info(
                f"  [BET] {pick_label} | "
                f"DK=N/A (prob-only) | "
                f"model={model_prob:.3f} | "
                f"edge={synthetic_edge*100:+.1f}% (vs fair) | "
                f"bet=${pick['recommended_bet']:.0f} | "
                f"[{pick['confidence_tier']}]"
            )

    elif market == "totals_1st_5_innings":
        # home_prob = P(over), away_prob = P(under)
        # Derive synthetic F5 line from full-game totals
        f5_line = _get_synthetic_f5_line(conn, game_id)
        if f5_line is None:
            logger.debug(f"  {game_id}: no full-game totals row — skipping F5 O/U prob-only")
            return picks

        sides = [
            ("over",  home_prob),
            ("under", away_prob),
        ]
        for pick_side, model_prob in sides:
            if model_prob < prob_thresh:
                continue

            synthetic_edge = model_prob - 0.50
            if synthetic_edge < edge_thresh:
                continue

            pick_label = _build_pick_label(pick_side, home_team, away_team, market, line=f5_line)
            inj_flag, inj_detail = _build_injury_flag(features, sport, "home")
            kelly_frac, rec_bet = quarter_kelly(model_prob, 0.5, bankroll)

            pick = {
                "game_id":           game_id,
                "model_id":          model_id,
                "sport":             sport,
                "game_date":         game_date,
                "pick_side":         pick_side,
                "pick_label":        pick_label,
                "model_probability": round(model_prob, 4),
                "dk_implied_prob":   0.5,
                "edge":              round(synthetic_edge, 4),
                "dk_odds":           None,
                "scored_line":       f5_line,
                "kelly_fraction":    kelly_frac,
                "recommended_bet":   rec_bet,
                "bankroll_at_pick":  bankroll,
                "injury_flag":       inj_flag,
                "injury_detail":     inj_detail,
                "signal_type":       "BET",
                "confidence_tier":   _confidence_tier(synthetic_edge),
                "game_time":         commence_time,
            }
            picks.append(pick)
            logger.info(
                f"  [BET] {pick_label} | "
                f"DK=N/A (prob-only) | "
                f"model={model_prob:.3f} | "
                f"edge={synthetic_edge*100:+.1f}% (vs fair) | "
                f"F5 line={f5_line} | "
                f"bet=${pick['recommended_bet']:.0f} | "
                f"[{pick['confidence_tier']}]"
            )

    elif market == "spreads_1st_5_innings":
        # F5 RL is fixed at -0.5 (home must win F5 outright to cover)
        # home_prob = P(home covers -0.5) = P(home wins F5)
        # away_prob = P(away covers +0.5) = P(away wins or ties F5)
        # scored_line stores the home spread (-0.5) — same convention as full-game RL.
        # _build_pick_label negates it for the away side automatically.
        f5_spread = -0.5
        sides = [
            ("home", home_prob),
            ("away", away_prob),
        ]
        for pick_side, model_prob in sides:
            if model_prob < prob_thresh:
                continue

            synthetic_edge = model_prob - 0.50
            if synthetic_edge < edge_thresh:
                continue

            # Always pass f5_spread (home spread) as line — label builder negates for away
            pick_label = _build_pick_label(pick_side, home_team, away_team, market, line=f5_spread)
            inj_flag, inj_detail = _build_injury_flag(features, sport, pick_side)
            kelly_frac, rec_bet = quarter_kelly(model_prob, 0.5, bankroll)

            pick = {
                "game_id":           game_id,
                "model_id":          model_id,
                "sport":             sport,
                "game_date":         game_date,
                "pick_side":         pick_side,
                "pick_label":        pick_label,
                "model_probability": round(model_prob, 4),
                "dk_implied_prob":   0.5,
                "edge":              round(synthetic_edge, 4),
                "dk_odds":           None,
                "scored_line":       f5_spread,
                "kelly_fraction":    kelly_frac,
                "recommended_bet":   rec_bet,
                "bankroll_at_pick":  bankroll,
                "injury_flag":       inj_flag,
                "injury_detail":     inj_detail,
                "signal_type":       "BET",
                "confidence_tier":   _confidence_tier(synthetic_edge),
                "game_time":         commence_time,
            }
            picks.append(pick)
            logger.info(
                f"  [BET] {pick_label} | "
                f"DK=N/A (prob-only) | "
                f"model={model_prob:.3f} | "
                f"edge={synthetic_edge*100:+.1f}% (vs fair) | "
                f"bet=${pick['recommended_bet']:.0f} | "
                f"[{pick['confidence_tier']}]"
            )

    if picks and not dry_run:
        _insert_picks(conn, picks)

    return picks


_UFC_METHOD_LABELS = {"decision": "Decision", "ko_tko": "KO/TKO", "submission": "Submission"}


# Class index → pick_side for the NHL regulation 3-way model. Must match the
# target encoding in feature_engine._compute_target (0=away, 1=draw, 2=home).
NHL_3WAY_CLASSES = ["away", "draw", "home"]


def _score_nhl_3way(conn, game_id: str, model_id: str, sport: str,
                    game_date: str, home_team: str, away_team: str,
                    clf, x, features: dict, bankroll: float,
                    dry_run: bool, commence_time: str | None) -> list[dict]:
    """
    NHL regulation-result scoring — 3-class (away reg win / draw / home reg
    win) priced against DraftKings' 3-way regulation market. Each side with a
    DK price is evaluated independently through the standard _make_pick
    edge/threshold logic, including the Draw. Skips entirely (no prob-only
    fallback) when DK doesn't list the market — regulation value only exists
    relative to real 3-way prices.
    """
    odds = _get_dk_odds(conn, game_id, "h2h_3way")
    if not odds:
        logger.debug(f"  {game_id}/{model_id}: no DK 3-way regulation odds — skipping")
        return []

    try:
        probs = clf.predict_proba(x)[0]
    except Exception as exc:
        logger.error(f"  Prediction error for {game_id}/{model_id}: {exc}")
        return []
    if len(probs) < 3:
        logger.error(f"  {game_id}/{model_id}: expected 3-class probs, got {len(probs)}")
        return []

    side_prices = {
        "away": odds.get("away_price"),
        "draw": odds.get("draw_price"),
        "home": odds.get("home_price"),
    }
    side_labels = {
        "away": f"{away_team} (Regulation)",
        "draw": f"{away_team} @ {home_team} Draw (Regulation)",
        "home": f"{home_team} (Regulation)",
    }

    picks = []
    for idx, side in enumerate(NHL_3WAY_CLASSES):
        price = side_prices[side]
        if price is None:
            continue
        ip = american_to_implied_prob(price)
        if not ip:
            continue
        model_p = float(probs[idx])
        pick = _make_pick(
            game_id, model_id, sport, game_date,
            pick_side=side,
            pick_label=side_labels[side],
            model_prob=model_p,
            dk_implied_prob=ip,
            edge=model_p - ip,
            dk_odds=price,
            scored_line=None,
            bankroll=bankroll,
            features=features,
            commence_time=commence_time,
        )
        if pick:
            picks.append(pick)

    for p in picks:
        p.update(_get_public_betting(conn, game_id, "h2h_3way", p["pick_side"]))
        p["dk_bet_link"] = _link_for_side(odds, p["pick_side"])
        if p["signal_type"] == "BET":
            logger.info(
                f"  [BET] {p['pick_label']} | DK={p['dk_odds']:+.0f} | "
                f"model={p['model_probability']:.3f} | edge={p['edge']*100:+.1f}% | "
                f"bet=${p['recommended_bet']:.0f} | [{p['confidence_tier']}]"
            )

    if picks and not dry_run:
        _insert_picks(conn, picks)
    return picks


def _score_ufc_method(conn, game_id: str, model_id: str, sport: str,
                      game_date: str, home_team: str, away_team: str,
                      clf, x, features: dict, bankroll: float,
                      dry_run: bool, commence_time: str | None) -> list[dict]:
    """
    UFC method-of-victory scoring — 3-class (decision / ko_tko / submission),
    prob-only (model_id is in PROB_ONLY_MODELS; The Odds API carries no method
    odds). Emits one pick for the argmax class: BET when its calibrated prob
    clears the threshold, NONE otherwise (no AVOID — there is no priced side
    to fade). Fair prob for record-keeping edge = 1/3.
    """
    from features.ufc_feature_engine import METHOD_CLASSES

    try:
        probs = clf.predict_proba(x)[0]
    except Exception as exc:
        logger.error(f"  Prediction error for {game_id}/{model_id}: {exc}")
        return []
    if len(probs) < 3:
        logger.error(f"  {game_id}/{model_id}: expected 3-class probs, got {len(probs)}")
        return []

    idx = int(np.argmax(probs))
    model_prob = float(probs[idx])
    pick_side = METHOD_CLASSES[idx]
    fair = 1.0 / 3.0
    edge = model_prob - fair

    prob_thresh = MODEL_PROB_THRESHOLDS.get(model_id, MIN_MODEL_PROB)
    # VERIFIED 2026-08-28 (scripts/probe_ufc_markets.py, run against the live
    # feed with the production key): The Odds API returns HTTP 422 "unsupported
    # market" for every method/round key — method_of_victory, win_method,
    # method, fight_outcome, outcome_method, to_win_by_ko/submission/decision,
    # round_betting, exact_rounds, winning_round, go_the_distance. Only h2h,
    # totals, spreads and h2h_3_way are valid keys for MMA.
    #
    # A 422 rejects the KEY NAME, so this is independent of which fight is
    # queried. DraftKings does price method of victory on its own product; our
    # data provider simply does not expose it. Re-run the probe if the provider
    # ever adds it, then put the key in UFC_EVENT_MARKETS and this model prices
    # against a real line instead of a prior.
    #
    # Until then config.REQUIRE_DK_PRICE keeps it from firing, and the row is
    # written as NONE so the model keeps a tracked record. NOTE the `edge` here
    # is model_prob - 1/3 (a uniform prior over the three classes), NOT an edge
    # over a market — it is not comparable to the edge on a priced pick and must
    # never be presented as if it were.
    signal_type = ("NONE" if REQUIRE_DK_PRICE
                   else ("BET" if model_prob >= prob_thresh else "NONE"))
    # Paused models never fire a BET — downgrade to NONE (no bet, no settlement).
    if model_id in PAUSED_MODELS and signal_type == "BET":
        signal_type = "NONE"

    if signal_type == "BET":
        kelly_frac, rec_bet = quarter_kelly(model_prob, fair, bankroll)
    else:
        kelly_frac, rec_bet = 0.0, 0.0

    pick = {
        "game_id":           game_id,
        "model_id":          model_id,
        "sport":             sport,
        "game_date":         game_date,
        "pick_side":         pick_side,
        "pick_label":        f"{away_team} vs {home_team} — {_UFC_METHOD_LABELS[pick_side]}",
        "model_probability": round(model_prob, 4),
        "dk_implied_prob":   round(fair, 4),
        "edge":              round(edge, 4),
        "dk_odds":           None,
        "scored_line":       None,
        "kelly_fraction":    kelly_frac,
        "recommended_bet":   rec_bet,
        "bankroll_at_pick":  bankroll,
        "injury_flag":       None,
        "injury_detail":     None,
        "signal_type":       signal_type,
        "confidence_tier":   _confidence_tier(edge),
        "game_time":         commence_time,
    }

    if signal_type == "BET":
        logger.info(
            f"  [BET] {pick['pick_label']} | DK=N/A (prob-only) | "
            f"model={model_prob:.3f} | edge={edge*100:+.1f}% (vs fair 1/3) | "
            f"bet=${rec_bet:.0f} | [{pick['confidence_tier']}]"
        )
    if not dry_run:
        _insert_picks(conn, [pick])
    return [pick]


def _score_ufc_totals_prob_only(conn, game_id: str, model_id: str, sport: str,
                                game_date: str, home_team: str, away_team: str,
                                over_prob: float, under_prob: float,
                                feat: dict, features: dict, bankroll: float,
                                dry_run: bool, commence_time: str | None) -> list[dict]:
    """
    UFC round totals without DK lines: prob-only against the synthetic line
    carried by the feature row (2.5 for 3-round bouts, 4.5 for 5-round).
    Same convention as the F5 prob-only path — BET rows only, dk_odds NULL,
    edge = model_prob − 0.50, settled at −110 flat.
    """
    # A synthetic 2.5/4.5 line is not a market. With config.REQUIRE_DK_PRICE on
    # there is nothing placeable here, so skip rather than emit an unbettable
    # BET — the same "no line, no pick" convention NCAAF and NFL already use.
    # Since the sibling-orientation fallback in _get_dk_odds landed, reaching
    # this path at all means no book has posted the fight's round total yet.
    if REQUIRE_DK_PRICE:
        logger.debug(f"  {game_id}/{model_id}: no DK round-total line — skipped "
                     f"(REQUIRE_DK_PRICE)")
        return []

    prob_thresh = MODEL_PROB_THRESHOLDS.get(model_id, MIN_MODEL_PROB)
    edge_thresh = MODEL_EDGE_THRESHOLDS.get(model_id, BET_EDGE_THRESHOLD)
    line = feat.get("total_line")
    if line is None:
        return []

    picks = []
    for pick_side, model_prob in (("over", over_prob), ("under", under_prob)):
        if model_prob < prob_thresh:
            continue
        synthetic_edge = model_prob - 0.50
        if synthetic_edge < edge_thresh:
            continue

        kelly_frac, rec_bet = quarter_kelly(model_prob, 0.5, bankroll)
        pick = {
            "game_id":           game_id,
            "model_id":          model_id,
            "sport":             sport,
            "game_date":         game_date,
            "pick_side":         pick_side,
            "pick_label":        f"{away_team} vs {home_team} "
                                 f"{pick_side.title()} {line} Rounds",
            "model_probability": round(model_prob, 4),
            "dk_implied_prob":   0.5,
            "edge":              round(synthetic_edge, 4),
            "dk_odds":           None,
            "scored_line":       line,
            "kelly_fraction":    kelly_frac,
            "recommended_bet":   rec_bet,
            "bankroll_at_pick":  bankroll,
            "injury_flag":       None,
            "injury_detail":     None,
            "signal_type":       "BET",
            "confidence_tier":   _confidence_tier(synthetic_edge),
            "game_time":         commence_time,
        }
        picks.append(pick)
        logger.info(
            f"  [BET] {pick['pick_label']} | DK=N/A (prob-only) | "
            f"model={model_prob:.3f} | edge={synthetic_edge*100:+.1f}% (vs fair) | "
            f"bet=${rec_bet:.0f} | [{pick['confidence_tier']}]"
        )

    if picks and not dry_run:
        _insert_picks(conn, picks)
    return picks


def _blocked_by_min_odds(model_id: str, dk_odds: float | None) -> bool:
    """Price-quality gate (config.MODEL_MIN_ODDS): True when the model has a
    floor on acceptable American odds and the DK price is juicier than it
    (more negative, e.g. -165 with a -140 floor). A blocked pick is downgraded
    BET → NONE — same treatment as the dead-zone. NULL dk_odds never blocks
    (prob-only fallbacks keep firing)."""
    floor = MODEL_MIN_ODDS.get(model_id)
    return floor is not None and dk_odds is not None and dk_odds < floor


def _missing_price(dk_odds: float | None) -> bool:
    """True when config.REQUIRE_DK_PRICE is on and the pick carries no book
    price. Such a pick cannot be placed, so it is downgraded BET -> NONE."""
    return REQUIRE_DK_PRICE and dk_odds is None


def _make_pick(game_id: str, model_id: str, sport: str, game_date: str,
               pick_side: str, pick_label: str,
               model_prob: float, dk_implied_prob: float, edge: float,
               dk_odds: float, bankroll: float,
               features: dict, scored_line: float | None = None,
               commence_time: str | None = None) -> dict | None:
    """
    Classify edge and build pick dict. Returns None only if edge exceeds noise cap.
    BET/AVOID/NONE rows are all written to DB so the website can display every game.
    """
    if abs(edge) > MAX_EDGE_CAP:
        logger.debug(f"  Edge {edge*100:+.1f}% exceeds cap — skipping (likely model noise)")
        return None

    bet_thresh   = MODEL_EDGE_THRESHOLDS.get(model_id, BET_EDGE_THRESHOLD)
    avoid_thresh = MODEL_EDGE_THRESHOLDS.get(model_id, AVOID_EDGE_THRESHOLD)

    prob_thresh = MODEL_PROB_THRESHOLDS.get(model_id, MIN_MODEL_PROB)
    if edge >= bet_thresh and model_prob >= prob_thresh:
        signal_type = "BET"
    elif edge <= -avoid_thresh:
        signal_type = "AVOID"
    else:
        signal_type = "NONE"

    # Price too juicy for this model (config.MODEL_MIN_ODDS) — no bet.
    if signal_type == "BET" and _blocked_by_min_odds(model_id, dk_odds):
        logger.debug(f"  {pick_label}: DK {dk_odds:+.0f} below the "
                     f"{MODEL_MIN_ODDS[model_id]} price floor — BET → NONE")
        signal_type = "NONE"

    # No price, no bet. A BET must be placeable somewhere.
    if signal_type == "BET" and _missing_price(dk_odds):
        logger.debug(f"  {pick_label}: no book price — BET → NONE")
        signal_type = "NONE"

    # Paused models never fire a BET — downgrade to NONE (no bet, no settlement).
    if model_id in PAUSED_MODELS and signal_type == "BET":
        signal_type = "NONE"

    sport_from_model = MODELS[model_id][0]
    if signal_type == "NONE":
        kelly_frac, rec_bet = 0.0, 0.0
    else:
        kelly_frac, rec_bet = quarter_kelly(model_prob, dk_implied_prob, bankroll)

    inj_flag, inj_detail = _build_injury_flag(features, sport_from_model, pick_side)
    conf_tier = _confidence_tier(edge)

    return {
        "game_id":           game_id,
        "model_id":          model_id,
        "sport":             sport,
        "game_date":         game_date,
        "pick_side":         pick_side,
        "pick_label":        pick_label,
        "model_probability": round(model_prob, 4),
        "dk_implied_prob":   round(dk_implied_prob, 4),
        "edge":              round(edge, 4),
        "dk_odds":           dk_odds,
        "scored_line":       scored_line,
        "kelly_fraction":    kelly_frac,
        "recommended_bet":   rec_bet,
        "bankroll_at_pick":  bankroll,
        "injury_flag":       inj_flag,
        "injury_detail":     inj_detail,
        "signal_type":       signal_type,
        "confidence_tier":   conf_tier,
        "game_time":         commence_time,
    }


def _days_until(commence_time: str | None) -> float | None:
    """
    Days from now until kickoff. None when the time is absent or unparseable —
    callers must treat that as "no lead information", never as zero.
    """
    if not commence_time:
        return None
    t = str(commence_time).strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(t)
    except ValueError:
        return None
    now = datetime.now(ZoneInfo("UTC"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=ZoneInfo("UTC"))
    return (d - now).total_seconds() / 86400.0


def _opener_rule(conn: DBConnection, game_id: str, model_id: str, market: str,
                 artifact: dict) -> tuple:
    """
    NCAAF cross-book opener rule. Not a fitted model: where a SHARP book's
    opening spread disagrees with a SOFT book's, back the side the sharp book
    favours, at the soft book's stale number. The soft book here is
    DraftKings, which is also the book we price against, so the DK-only
    invariant is untouched.

    Backtest (CFBD archive, 2023-2025): 1,050 bets / 58.1% / +10.9%, positive
    in all three seasons, CLV 0.694, and the reversed book assignment is null.
    Both placebos pass -- the edge vanishes at the sharp book's open and at
    DK's close.

    Returns (home_prob, away_prob, no_signal):
      • (p, 1-p, None)      the rule fires
      • (0.5, 0.5, reason)  the rule DECLINES but the game is still shown --
                            a "no signal" row carrying DK's live number
      • (None, None, None)  nothing to show at all (no current DK line, or the
                            game belongs to the sibling tier)

    THREE PRECONDITIONS, all enforced here rather than assumed, because the
    whole strategy rests on the stale number being *gettable*:

     1. SIMULTANEITY. Both openers must be captured within
        OPENER_MAX_SKEW_MIN of each other. If the sharp book's number is
        simply recorded later, `dev` measures elapsed line movement, not book
        disagreement, and the edge is an artefact. Every NCAAF game already in
        our odds table on 2026-08-22 was first polled before Bovada was
        ingested at all -- so those games can never satisfy this, and the rule
        correctly declines to bet them.
     2. STILL GETTABLE. DK's CURRENT spread must equal its opening spread. If
        DK has already moved, the number the backtest bet no longer exists and
        neither does the edge.
     3. The disagreement must clear the gate.

    Failing any of them yields NO BET. It no longer yields no ROW: the game
    and DK's line still surface, flagged "no signal", because an empty board
    is indistinguishable from a broken pipeline (2026-08-29).
    """
    sharp_book = artifact.get("sharp_book") or "bovada"
    gate = float(artifact.get("d_threshold") or 1.0)
    max_skew = float(artifact.get("max_skew_min") or OPENER_MAX_SKEW_MIN)

    # No current DK line means there is nothing to price OR display.
    cur = _get_dk_odds(conn, game_id, market)
    if not cur or cur.get("spread_home") is None:
        return None, None, None

    soft_open = _opening_line(conn, game_id, market, ODDS_API_BOOKMAKER)
    sharp_open = _opening_line(conn, game_id, market, sharp_book)
    if (not soft_open or not sharp_open
            or soft_open.get("spread_home") is None
            or sharp_open.get("spread_home") is None):
        logger.debug(f"  {game_id}/{model_id}: missing an opener "
                     f"({ODDS_API_BOOKMAKER}/{sharp_book}) — no signal")
        return 0.5, 0.5, f"no opener recorded at {sharp_book}"

    skew = _minutes_apart(soft_open["snapshot_at"], sharp_open["snapshot_at"])
    if skew is None or skew > max_skew:
        logger.debug(f"  {game_id}/{model_id}: openers {skew} min apart "
                     f"(max {max_skew}) — not simultaneous, no signal")
        return 0.5, 0.5, "openers not captured simultaneously"

    if float(cur["spread_home"]) != float(soft_open["spread_home"]):
        logger.debug(f"  {game_id}/{model_id}: DK moved "
                     f"{soft_open['spread_home']} -> {cur['spread_home']}; "
                     "the stale number is gone — no signal")
        return 0.5, 0.5, "DK has moved off its opening number"

    dev = float(soft_open["spread_home"]) - float(sharp_open["spread_home"])

    # BAND CEILING (optional, exclusive). A tighter gate is a strict SUBSET of
    # a looser one, so two opener models sharing a floor would fire two picks
    # on the SAME side of the SAME game -- double staking, and two rows in the
    # app for one bet. `d_threshold_max` carves the range into DISJOINT bands
    # so a qualifying game produces exactly one pick, which is what lets a
    # high-conviction tier be ADDED rather than just re-slicing the existing
    # one. Absent -> unbounded (the original rule).
    #
    # This is the one decline that writes NO ROW: the sibling tier is pricing
    # this exact side of this exact game, and a "no signal" row beside its BET
    # would read as the two tiers contradicting each other.
    gate_max = artifact.get("d_threshold_max")
    if gate_max is not None and abs(dev) >= float(gate_max):
        logger.debug(f"  {game_id}/{model_id}: |dev| {abs(dev):.1f} >= band "
                     f"ceiling {gate_max} - belongs to the tier above")
        return None, None, None

    if abs(dev) < gate:
        logger.debug(f"  {game_id}/{model_id}: |dev| {abs(dev):.1f} < gate {gate}")
        return 0.5, 0.5, f"books agree within {gate:g} pts"

    # dev > 0 : soft's HOME number is higher (more generous to home) than
    # sharp's, so the sharp book implicitly favours HOME.
    p = float(artifact.get("model_prob") or 0.5)
    home_prob = p if dev > 0 else (1.0 - p)
    logger.info(f"  {game_id}/{model_id}: opener dev {dev:+.1f} "
                f"({sharp_book} {sharp_open['spread_home']} vs DK "
                f"{soft_open['spread_home']}), skew {skew:.0f}min")
    return home_prob, 1.0 - home_prob, None


def _opening_line(conn: DBConnection, game_id: str, market: str,
                  bookmaker: str) -> dict | None:
    """
    A book's EARLIEST stored snapshot for a game+market — its opener as we
    observed it.

    `data/prune_odds.py` preserves the first snapshot per (proposition, book)
    forever precisely so this stays available; without that the opener is
    deleted within PRUNE_NON_DK_KEEP_DAYS.
    """
    row = conn.execute("""
        SELECT spread_home, total_line, home_price, away_price, snapshot_at
        FROM odds
        WHERE game_id = ? AND market = ? AND bookmaker = ?
          AND snapshot_type != 'in_play'
        ORDER BY snapshot_at ASC
        LIMIT 1
    """, (game_id, market, bookmaker)).fetchone()
    if not row:
        return None
    return {"spread_home": row[0], "total_line": row[1],
            "home_price": row[2], "away_price": row[3], "snapshot_at": row[4]}


def _minutes_apart(a: str, b: str) -> float | None:
    """Absolute minutes between two ISO timestamps; None if unparseable."""
    from datetime import datetime
    def _p(v):
        if v is None:
            return None
        t = str(v).strip().replace("Z", "+00:00")
        try:
            d = datetime.fromisoformat(t)
        except ValueError:
            return None
        return d.replace(tzinfo=None) if d.tzinfo is None else d.astimezone().replace(tzinfo=None)
    pa, pb = _p(a), _p(b)
    if pa is None or pb is None:
        return None
    return abs((pa - pb).total_seconds()) / 60.0


# ── Best line across books (display + bet; never qualification) ───────────────
#
# Every scored pick records the best price we could find on its side across
# config.BEST_LINE_BOOKMAKERS, and which book had it. This is what the bettor
# should actually take, and what the app shows.
#
# It is deliberately NOT what decides the bet. `edge`, the BET/AVOID call, the
# Kelly stake, settlement and CLV all still measure against DraftKings, because
# every threshold in section 17 was swept on DK-implied edge and best-of-N
# pricing runs ~2pp cheaper in implied probability — adopting it as the
# qualifying price would loosen every cut by that much, silently. best_edge is
# recorded alongside so the true EV of the bet placed is visible, and so there
# is real best-price history on the picks table to re-sweep against later.

# Which column of an `odds` row carries the price for a pick side.
_SIDE_PRICE_COLUMN = {
    "home": "home_price", "away": "away_price", "draw": "draw_price",
    "over": "over_price", "under": "under_price",
}
_SIDE_LINK_COLUMN = {
    "home": "home_link", "away": "away_link", "draw": "draw_link",
    "over": "over_link", "under": "under_link",
}


def _same_line(a, b) -> bool:
    """Two propositions are the same bet only at the same number. A better price
    on Over 9.0 is not a better price on Over 8.5 — it is a different bet."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) < 1e-6


def _best_of(quotes: list[dict]) -> dict | None:
    """Highest decimal payout wins; ties keep the first (book order = config
    order, so DraftKings wins a tie and the quote stays on the modelled book)."""
    best = None
    for q in quotes:
        if q.get("odds") is None:
            continue
        try:
            payout = american_to_decimal(float(q["odds"]))
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if best is None or payout > best[0]:
            best = (payout, q)
    return best[1] if best else None


def _best_game_price(conn: DBConnection, game_id: str, market: str,
                     pick_side: str, scored_line: float | None) -> dict | None:
    """
    Best price on one side of a game market across BEST_LINE_BOOKMAKERS.

    Only quotes at the SAME line count (totals/spreads), and only pre-game
    snapshots — an in-play price is a different proposition entirely.
    """
    price_col = _SIDE_PRICE_COLUMN.get(pick_side)
    if not price_col or not BEST_LINE_BOOKMAKERS:
        return None
    link_col = _SIDE_LINK_COLUMN[pick_side]
    line_col = "total_line" if market.startswith("totals") else (
        "spread_home" if market.startswith("spreads") else None)

    placeholders = ",".join("?" for _ in BEST_LINE_BOOKMAKERS)
    rows = conn.execute(f"""
        SELECT bookmaker, {price_col}, {link_col}, total_line, spread_home, snapshot_at
        FROM odds
        WHERE game_id = ? AND market = ?
          AND snapshot_type != 'in_play'
          AND bookmaker IN ({placeholders})
        ORDER BY snapshot_at DESC
    """, (game_id, market, *BEST_LINE_BOOKMAKERS)).fetchall()

    # Latest snapshot per book (rows already newest-first).
    latest: dict[str, tuple] = {}
    for r in rows:
        latest.setdefault(r[0], r)

    quotes = []
    for book in BEST_LINE_BOOKMAKERS:          # config order breaks ties
        r = latest.get(book)
        if r is None:
            continue
        if line_col is not None:
            book_line = r[3] if line_col == "total_line" else r[4]
            if not _same_line(book_line, scored_line):
                continue
        quotes.append({"book": book, "odds": r[1], "link": r[2]})
    return _best_of(quotes)


def _best_prop_price(conn: DBConnection, game_id: str, player_name: str,
                     market: str, pick_side: str,
                     line: float | None) -> dict | None:
    """Best price on one side of a player prop, at the same line."""
    if pick_side not in ("over", "under") or not BEST_LINE_BOOKMAKERS:
        return None
    price_col = "over_price" if pick_side == "over" else "under_price"
    link_col  = "over_link"  if pick_side == "over" else "under_link"

    placeholders = ",".join("?" for _ in BEST_LINE_BOOKMAKERS)
    rows = conn.execute(f"""
        SELECT bookmaker, {price_col}, {link_col}, line
        FROM player_prop_odds
        WHERE game_id = ? AND player_name = ? AND market = ?
          AND bookmaker IN ({placeholders})
        ORDER BY snapshot_at DESC
    """, (game_id, player_name, market, *BEST_LINE_BOOKMAKERS)).fetchall()

    latest: dict[str, tuple] = {}
    for r in rows:
        latest.setdefault(r[0], r)

    quotes = []
    for book in BEST_LINE_BOOKMAKERS:
        r = latest.get(book)
        if r is None or not _same_line(r[3], line):
            continue
        quotes.append({"book": book, "odds": r[1], "link": r[2]})
    return _best_of(quotes)


def _best_fields(best: dict | None, model_prob: float) -> dict:
    """The five columns a pick carries about the best available price."""
    if not best or best.get("odds") is None:
        return {"best_book": None, "best_odds": None, "best_implied_prob": None,
                "best_edge": None, "best_bet_link": None}
    odds = float(best["odds"])
    implied = american_to_implied_prob(odds)
    return {
        "best_book":         best["book"],
        "best_odds":         odds,
        "best_implied_prob": round(implied, 4),
        "best_edge":         round(model_prob - implied, 4),
        "best_bet_link":     best.get("link"),
    }


def _stamp_best_game_prices(conn: DBConnection, picks: list[dict],
                            market: str) -> None:
    """Add the best-price columns to game-market picks, in place."""
    for p in picks:
        try:
            best = _best_game_price(conn, p["game_id"], market,
                                    p["pick_side"], p.get("scored_line"))
        except Exception as exc:               # never let line shopping kill scoring
            logger.debug(f"  best-price lookup failed for {p.get('pick_label')}: {exc}")
            best = None
        p.update(_best_fields(best, float(p["model_probability"])))


def _tag_prop(pick: dict, ctx: tuple) -> dict:
    """Carry (game_id, player_name, market) on a prop pick so _insert_picks can
    look up its best price. Private key — stripped before the INSERT."""
    if pick is not None:
        pick["_best_ctx"] = ctx
    return pick


def _get_dk_odds(conn: DBConnection, game_id: str, market: str) -> dict | None:
    """
    Get most recent odds snapshot for a game+market.
    Tries DraftKings first; falls back to sbr_consensus for historical games.
    """
    cols = ["home_price", "away_price", "draw_price",
            "spread_home", "total_line", "over_price", "under_price",
            "home_link", "away_link", "draw_link", "over_link", "under_link"]

    # For MLB runline / NHL puckline, filter to the standard ±1.5 to avoid
    # alternate spread lines returned by the Odds API. Basketball spreads
    # (WNBA/NBA) are game-specific numbers (-1.5 .. -15.5) — the ±1.5 filter
    # would discard nearly every row, so it only applies to MLB/NHL game ids.
    spread_filter = ""
    if market == "spreads" and game_id.split("_", 1)[0] in ("MLB", "NHL"):
        spread_filter = "AND ABS(spread_home) = 1.5"

    for bookmaker in ("draftkings", "sbr_consensus"):
        row = conn.execute(f"""
            SELECT home_price, away_price, draw_price,
                   spread_home, total_line, over_price, under_price,
                   home_link, away_link, draw_link, over_link, under_link
            FROM odds
            WHERE game_id   = ?
              AND market    = ?
              AND bookmaker = ?
              AND snapshot_type != 'in_play'
              {spread_filter}
            ORDER BY snapshot_at DESC
            LIMIT 1
        """, (game_id, market, bookmaker)).fetchone()

        if row:
            return dict(zip(cols, row))

    # UFC only: the same fight can exist as TWO games rows with home/away
    # swapped, because game_id is built from The Odds API's home_team and that
    # assignment is not stable between fetches. Odds land on whichever row the
    # feed used at ingest time, so the sibling can hold the real DK line while
    # this row holds none -- which silently pushed round-totals picks onto the
    # prob-only fallback even though DK had priced the fight. Verified on the
    # 2026-08-29 card: three fights had 195 DK totals rows on one orientation
    # and zero on the other, and all three picks landed on the empty one.
    sibling = _sibling_ufc_game_id(game_id)
    if sibling:
        row = conn.execute(f"""
            SELECT home_price, away_price, draw_price,
                   spread_home, total_line, over_price, under_price,
                   home_link, away_link, draw_link, over_link, under_link
            FROM odds
            WHERE game_id   = ?
              AND market    = ?
              AND bookmaker = 'draftkings'
              AND snapshot_type != 'in_play'
              {spread_filter}
            ORDER BY snapshot_at DESC
            LIMIT 1
        """, (sibling, market)).fetchone()
        if row:
            odds = dict(zip(cols, row))
            # totals are orientation-independent (over/under/line); h2h is NOT,
            # so home/away must be swapped to match THIS row's orientation.
            if market != "totals":
                odds = _swap_home_away(odds)
            logger.debug(f"  {game_id}/{market}: no odds on this row — "
                         f"resolved from sibling orientation {sibling}")
            return odds

    return None


def _sibling_ufc_game_id(game_id: str) -> str | None:
    """UFC_{date}_{away}_{home} -> UFC_{date}_{home}_{away}, or None when the id
    is not a UFC id of that shape. Fighter slugs contain hyphens but never
    underscores, so the 4-part split is unambiguous."""
    parts = game_id.split("_")
    if len(parts) != 4 or parts[0] != "UFC":
        return None
    return f"{parts[0]}_{parts[1]}_{parts[3]}_{parts[2]}"


def _swap_home_away(odds: dict) -> dict:
    """Mirror an odds dict read from the opposite home/away orientation."""
    out = dict(odds)
    for a, b in (("home_price", "away_price"), ("home_link", "away_link")):
        out[a], out[b] = odds.get(b), odds.get(a)
    if odds.get("spread_home") is not None:
        out["spread_home"] = -odds["spread_home"]
    return out


# pick_side → odds-dict link column. Used to stamp each pick with the DK
# betslip deep link for the exact selection (The Odds API includeLinks).
_PICK_SIDE_LINK_COL = {
    "home": "home_link", "away": "away_link", "draw": "draw_link",
    "over": "over_link", "under": "under_link",
}


def _link_for_side(odds: dict | None, pick_side: str) -> str | None:
    """DK betslip deep link matching a pick's side, or None if absent."""
    if not odds:
        return None
    return odds.get(_PICK_SIDE_LINK_COL.get(pick_side, ""))


# Model market → public_betting market. Only full-game markets carry public
# splits from Action Network; F5 / 3-way / prop markets resolve to None.
_PUBLIC_BETTING_MARKETS = {"h2h": "h2h", "spreads": "spreads", "totals": "totals"}


def _get_public_betting(conn: DBConnection, game_id: str,
                        market: str, side: str) -> dict:
    """
    Latest public betting split for a game's market+side, or NULLs if absent.
    Returns {'public_bet_pct', 'public_money_pct'} so callers can splat it onto
    a pick dict regardless of whether splits exist.
    """
    base = _PUBLIC_BETTING_MARKETS.get(market)
    if base is None:
        return {"public_bet_pct": None, "public_money_pct": None}

    row = conn.execute("""
        SELECT public_bet_pct, public_money_pct
        FROM public_betting
        WHERE game_id = ? AND market = ? AND side = ?
        ORDER BY snapshot_at DESC
        LIMIT 1
    """, (game_id, base, side)).fetchone()

    if row:
        return {"public_bet_pct": row[0], "public_money_pct": row[1]}
    return {"public_bet_pct": None, "public_money_pct": None}


def _commence_time_map(conn: DBConnection, game_date: str, sport: str) -> dict:
    """
    {game_id: commence_time} for a sport+date, so prop scorers can stamp each
    pick with the game's scheduled start (single source of truth = games table).
    commence_time may be None for games without a known start time.
    """
    rows = conn.execute(
        "SELECT game_id, commence_time FROM games WHERE game_date = ? AND sport = ?",
        (game_date, sport),
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def _game_started(commence_time: str | None) -> bool:
    """
    True if a game's scheduled first pitch/tip is in the past — i.e. any DK
    snapshot taken now is an IN-PLAY price.

    Prop scorers use this to skip started games entirely. Without the guard,
    the evening refresh loop kept scoring props DURING games: a player whose
    pre-game row was NONE lost it to the started-game NONE cleanup, fell out
    of the first-signal lock set, and was re-scored against DK's in-play prop
    prices (the ingestor keeps snapshotting after first pitch). From 2026-06-27
    to 2026-08-08 that wrote hundreds of in-play "pre-game" picks — e.g. 65 of
    batter_rbi's 67 settled BETs in that window were created after first pitch.

    commence_time formats vary ('Z' suffix, ±HH:MM offset, naive) — parse in
    Python, never string-compare (session-93 lesson). Unknown/unparseable
    start time → False (don't skip; the morning pipeline must still score
    games whose commence_time hasn't been ingested yet).
    """
    if not commence_time:
        return False
    ts = str(commence_time).strip()
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt <= datetime.now(ZoneInfo("UTC"))


def _insert_picks(conn: DBConnection, picks: list[dict]) -> None:
    sql = """
        INSERT INTO picks (
            game_id, model_id, sport, game_date, pick_side, pick_label,
            model_probability, dk_implied_prob, edge, dk_odds, scored_line,
            kelly_fraction, recommended_bet, bankroll_at_pick,
            injury_flag, injury_detail, signal_type, confidence_tier,
            game_time, player_id, pitcher_throw_hand,
            public_bet_pct, public_money_pct, dk_bet_link,
            best_book, best_odds, best_implied_prob, best_edge, best_bet_link,
            is_live, inning_at_pick, score_diff_at_pick
        ) VALUES (
            %(game_id)s, %(model_id)s, %(sport)s, %(game_date)s, %(pick_side)s, %(pick_label)s,
            %(model_probability)s, %(dk_implied_prob)s, %(edge)s, %(dk_odds)s, %(scored_line)s,
            %(kelly_fraction)s, %(recommended_bet)s, %(bankroll_at_pick)s,
            %(injury_flag)s, %(injury_detail)s, %(signal_type)s, %(confidence_tier)s,
            %(game_time)s, %(player_id)s, %(pitcher_throw_hand)s,
            %(public_bet_pct)s, %(public_money_pct)s, %(dk_bet_link)s,
            %(best_book)s, %(best_odds)s, %(best_implied_prob)s, %(best_edge)s,
            %(best_bet_link)s,
            %(is_live)s, %(inning_at_pick)s, %(score_diff_at_pick)s
        )
    """
    # Prop picks arrive tagged with (game_id, player_name, market) instead of
    # pre-stamped, because their best price is a per-player lookup and the five
    # prop scorers build picks in eleven places. Resolve it once here.
    for p in picks:
        ctx = p.pop("_best_ctx", None)
        if ctx is None or "best_book" in p:
            continue
        game_id, player_name, market = ctx
        try:
            best = _best_prop_price(conn, game_id, player_name, market,
                                    p["pick_side"], p.get("scored_line"))
        except Exception as exc:               # line shopping never blocks a pick
            logger.debug(f"  best-price lookup failed for {p.get('pick_label')}: {exc}")
            best = None
        p.update(_best_fields(best, float(p["model_probability"])))

    # Ensure new optional columns are present; game-level picks omit player_id /
    # pitcher_throw_hand, prop picks omit the public betting fields, and only
    # the live scorer sets the is_live trio.
    normalized = [
        {
            **p,
            "player_id":          p.get("player_id"),
            "pitcher_throw_hand": p.get("pitcher_throw_hand"),
            "public_bet_pct":     p.get("public_bet_pct"),
            "public_money_pct":   p.get("public_money_pct"),
            "dk_bet_link":        p.get("dk_bet_link"),
            # Best available price across books — display/bet only, absent on
            # paths with no multi-book feed (golf, live, prob-only fallbacks).
            "best_book":          p.get("best_book"),
            "best_odds":          p.get("best_odds"),
            "best_implied_prob":  p.get("best_implied_prob"),
            "best_edge":          p.get("best_edge"),
            "best_bet_link":      p.get("best_bet_link"),
            "is_live":            p.get("is_live", False),
            "inning_at_pick":     p.get("inning_at_pick"),
            "score_diff_at_pick": p.get("score_diff_at_pick"),
        }
        for p in picks
    ]
    conn.executemany(sql, normalized)


def check_line_movement(conn: DBConnection, game_date: str) -> list[dict]:
    """
    Compare scored odds against current (latest) odds for today's BET picks.
    Returns list of warning dicts for picks where the line has moved significantly.

    Thresholds:
      - Totals:  line moves 0.5+ against the bet → SKIP
      - Any bet: price moves 10+ cents against us (implied prob shift ≥ 3%) → CAUTION
    """
    picks = conn.execute("""
        SELECT p.pick_id, p.pick_label, p.pick_side, p.model_id,
               p.game_id, p.dk_odds AS scored_price, p.scored_line,
               o.market
        FROM picks p
        JOIN odds o ON o.game_id = p.game_id
            AND o.bookmaker = 'draftkings'
        WHERE p.game_date = ?
          AND p.signal_type = 'BET'
          AND o.market = CASE
              -- %% is a LITERAL percent. psycopg2 interpolates the whole SQL
              -- string against the params, so a single percent is read as a
              -- format spec and the query raises "not enough arguments for
              -- format string" -- exactly how opening-signal capture died
              -- silently for three days (see data/db.py). Doubled on purpose.
              WHEN p.model_id LIKE '%%f5_over_under%%' THEN 'totals_1st_5_innings'
              WHEN p.model_id LIKE '%%f5_runline%%' THEN 'spreads_1st_5_innings'
              WHEN p.model_id LIKE '%%f5_moneyline%%' THEN 'h2h_1st_5_innings'
              WHEN p.model_id LIKE '%%over_under%%' THEN 'totals'
              WHEN p.model_id LIKE '%%runline%%' OR p.model_id LIKE '%%puckline%%' THEN 'spreads'
              ELSE 'h2h' END
        ORDER BY o.snapshot_at DESC
    """, (game_date,)).fetchall()

    seen = set()
    warnings = []
    for row in picks:
        pick_id, label, side, model_id, game_id, scored_price, scored_line, market = row
        if pick_id in seen:
            continue
        seen.add(pick_id)

        # Get latest odds snapshot
        current = _get_dk_odds(conn, game_id, market)
        if not current:
            continue

        warning = {"pick_label": label, "status": None, "detail": ""}

        if market == "totals":
            cur_line = current.get("total_line")
            if cur_line is not None and scored_line is not None:
                delta = cur_line - scored_line
                # Under: line going DOWN hurts us; Over: line going UP hurts us
                if side == "under" and delta < -0.4:
                    warning["status"] = "SKIP"
                    warning["detail"] = f"Line moved from {scored_line} → {cur_line} (worse for Under)"
                elif side == "over" and delta > 0.4:
                    warning["status"] = "SKIP"
                    warning["detail"] = f"Line moved from {scored_line} → {cur_line} (worse for Over)"

        # Price movement check (all markets)
        cur_price = (
            current.get("over_price") if side == "over" else
            current.get("under_price") if side == "under" else
            current.get("home_price") if side == "home" else
            current.get("away_price")
        )
        if cur_price is not None and scored_price is not None:
            scored_ip = american_to_implied_prob(scored_price) or 0
            cur_ip    = american_to_implied_prob(cur_price) or 0
            ip_shift  = cur_ip - scored_ip   # positive = got more expensive (worse for bettor)
            if ip_shift >= 0.03 and warning["status"] != "SKIP":
                scored_str = f"+{int(scored_price)}" if scored_price > 0 else str(int(scored_price))
                cur_str    = f"+{int(cur_price)}"    if cur_price > 0    else str(int(cur_price))
                warning["status"] = "CAUTION"
                warning["detail"] = f"Price moved {scored_str} → {cur_str} (line steamed {ip_shift*100:.1f}pp against you)"

        if warning["status"]:
            warnings.append(warning)

    return warnings


# ── MLB Stats API team ID → abbreviation (for postponement check) ────────────

_STATSAPI_TEAM_IDS = {
    109: "ARI", 144: "ATL", 110: "BAL", 111: "BOS", 112: "CHC",
    145: "CWS", 113: "CIN", 114: "CLE", 115: "COL", 116: "DET",
    117: "HOU", 118: "KC",  108: "LAA", 119: "LAD", 146: "MIA",
    158: "MIL", 142: "MIN", 121: "NYM", 147: "NYY", 133: "OAK",
    143: "PHI", 134: "PIT", 135: "SD",  136: "SEA", 137: "SF",
    138: "STL", 139: "TB",  140: "TEX", 141: "TOR", 120: "WSH",
}


def _get_postponed_games(target_date: str) -> set[str]:
    """
    Query MLB Stats API for today's schedule and return a set of game_id
    strings for any games that are postponed or suspended.

    Returns an empty set if the API is unavailable or the call fails,
    so scoring proceeds normally (safe fallback).
    """
    if not STATSAPI_AVAILABLE:
        return set()

    try:
        schedule = statsapi.schedule(date=target_date, sportId=1)
    except Exception as exc:
        logger.warning(f"Could not check postponements via MLB Stats API: {exc}")
        return set()

    postponed_ids = set()
    for game in schedule:
        status = game.get("status", "")
        if status in ("Postponed", "Suspended", "Cancelled"):
            home_id = game.get("home_id")
            away_id = game.get("away_id")
            home_abbr = _STATSAPI_TEAM_IDS.get(home_id, "")
            away_abbr = _STATSAPI_TEAM_IDS.get(away_id, "")
            if home_abbr and away_abbr:
                game_id = f"MLB_{target_date}_{away_abbr}_{home_abbr}"
                postponed_ids.add(game_id)
                logger.info(f"  Postponed: {away_abbr} @ {home_abbr} ({status})")

    return postponed_ids


def _log_pipeline(conn, run_date, status, records_in, records_out,
                  duration_s, error_msg=None):
    conn.execute("""
        INSERT INTO pipeline_log
            (run_date, step, status, records_in, records_out, duration_s, error_msg)
        VALUES (?, 'scoring', ?, ?, ?, ?, ?)
    """, (run_date, status, records_in, records_out, duration_s, error_msg))


# ── Main Daily Run ────────────────────────────────────────────────────────────

def run_scorer(target_date: str = None, dry_run: bool = False) -> dict:
    """
    Score all games scheduled for target_date across all models.

    Args:
        target_date: ISO date string (default: today)
        dry_run:     If True, print picks but don't write to DB

    Returns:
        Summary dict with total picks and breakdown.
    """
    if target_date is None:
        target_date = date.today().isoformat()

    logger.info(f"\n{'═'*60}")
    logger.info(f"Daily Scorer — {target_date}")
    logger.info(f"{'═'*60}")

    start = datetime.now()
    conn = get_connection()

    try:
        # Get current bankroll from last settled pick or default
        bankroll = _get_current_bankroll(conn)
        logger.info(f"Current bankroll: ${bankroll:,.2f}")

        # Fetch today's games — plus upcoming UFC fights. UFC events are weekly
        # and DK prices them days ahead, so same-day-only scoring would leave
        # the UFC surface empty until fight day.
        ufc_horizon = (
            date.fromisoformat(target_date) + timedelta(days=UFC_SCORE_AHEAD_DAYS)
        ).isoformat()
        ncaaf_horizon = (
            date.fromisoformat(target_date) + timedelta(days=NCAAF_SCORE_AHEAD_DAYS)
        ).isoformat()
        games = conn.execute("""
            SELECT game_id, sport, season, game_date, home_team, away_team, commence_time
            FROM games
            WHERE home_score IS NULL
              AND (game_date = ?
                   OR (sport = 'UFC' AND game_date > ? AND game_date <= ?)
                   OR (sport = 'NCAAF' AND game_date > ? AND game_date <= ?))
            ORDER BY sport, game_date
        """, (target_date, target_date, ufc_horizon,
              target_date, ncaaf_horizon)).fetchall()

        if not games:
            logger.info(f"No games found for {target_date}")
            return {"target_date": target_date, "total_picks": 0}

        logger.info(f"Found {len(games)} games for {target_date}")

        # NCAAF look-ahead is a WEEK of games, and most of them cannot produce a
        # row. On 2026-08-29 the window held 155 look-ahead games; DK priced 73.
        # EVERY NCAAF model needs a DK line — both opener tiers return early
        # without a current DK spread, and the totals rule without a DK total —
        # so an unpriced game costs a feature build plus ~4 models' worth of
        # round trips to produce nothing at all. Skip those before the feature
        # build. This is a COST filter, not a behaviour one: the set of games
        # that can produce a row is identical.
        #
        # The FBS gate would cut it further (39 of the 155 are both-FBS AND
        # priced) but is deliberately NOT hoisted here: _is_fbs reads the team's
        # ASOF stats snapshot, so a pre-filter on ncaaf_teams could be STRICTER
        # than the real gate and silently drop a game the scorer would price.
        ncaaf_unpriced: set = set()
        if any(g[1] == "NCAAF" for g in games):
            try:
                priced = {r[0] for r in conn.execute("""
                    SELECT DISTINCT o.game_id FROM odds o
                    WHERE o.bookmaker = ?
                      AND o.game_id IN (
                          SELECT game_id FROM games
                          WHERE sport = 'NCAAF' AND home_score IS NULL
                            AND game_date >= ? AND game_date <= ?
                      )
                """, (ODDS_API_BOOKMAKER, target_date, ncaaf_horizon)).fetchall()}
                ncaaf_unpriced = {g[0] for g in games
                                  if g[1] == "NCAAF" and g[0] not in priced}
                if ncaaf_unpriced:
                    logger.info(f"NCAAF: skipping {len(ncaaf_unpriced)} game(s) "
                                f"{ODDS_API_BOOKMAKER} does not price")
            except Exception as exc:
                # Fail OPEN — a filter that can't be built must never be able to
                # empty the board. Worst case we pay the old cost.
                logger.warning(f"NCAAF price pre-filter failed ({exc}); scoring all")
                ncaaf_unpriced = set()

        # Check for postponed MLB games via the official schedule API
        postponed_ids = _get_postponed_games(target_date)
        if postponed_ids:
            logger.info(f"Found {len(postponed_ids)} postponed game(s) — will skip scoring")
            if not dry_run:
                for ppd_id in postponed_ids:
                    conn.execute(
                        "DELETE FROM picks WHERE game_id = %s AND result IS NULL",
                        (ppd_id,),
                    )
                logger.info("Deleted stale picks for postponed games")

        now_utc = datetime.now(ZoneInfo("UTC")).isoformat()

        # Pick locking (config.LOCK_GAME_PICKS_AT_FIRST_RUN): game-level picks
        # lock at the first run of the day. A (game_id, model_id) that already
        # has an unsettled pick for target_date is frozen — later refreshes skip
        # it instead of deleting + re-scoring. We therefore DON'T run the broad
        # same-day delete below; the per-model skip in the loop does the work,
        # so partially-scored games (e.g. totals odds posted late) can still fill
        # in their missing markets without disturbing the locked ones.
        # game_date >= target_date, NOT = target_date: UFC and golf are scored
        # days ahead, and a pick that first crossed on Tuesday is the bet of
        # record for Saturday's card. Scoping the lock to today would leave
        # those future-dated picks re-scored on every pass, which is what let a
        # UFC pick appear and disappear before its lock day.
        # Release picks the lock should never have protected.
        #
        # The lock and the price rule shipped together, and they interact badly
        # on picks written BEFORE the price rule existed: the lock stops those
        # rows being re-scored, and REQUIRE_DK_PRICE only governs NEW picks, so
        # an unplaceable BET created by the old code stays live forever. That is
        # exactly what happened to the 2026-08-29 UFC card -- six BETs with no
        # price, two of them -EV against a DK line that did exist, frozen by the
        # lock minutes after it shipped.
        #
        # This is NOT the withdrawal the lock exists to prevent. That rule is
        # "never drop a pick because the ODDS MOVED" -- the whole CLV thesis. A
        # BET with no price at all was never placeable and is not a bet whose
        # number moved; it is a bug's output. Deleting it here un-locks it, so
        # the pass below re-scores it under the current rules and it comes back
        # correctly priced, or not at all.
        #
        # Scoped to games that have not started, so nothing settleable is ever
        # touched.
        if not dry_run:
            conn.execute("""
                DELETE FROM picks
                 WHERE result IS NULL
                   AND signal_type = 'BET'
                   AND dk_odds IS NULL
                   AND game_date >= %s
                   AND game_id IN (
                       SELECT game_id FROM games
                        WHERE commence_time IS NULL OR commence_time > %s
                   )
            """, (target_date, now_utc))

        locked_pairs: set[tuple] = set()
        if LOCK_GAME_PICKS_AT_FIRST_RUN and not dry_run:
            # NCAAF is scored across a WEEK, not a day, so the lock has to
            # mean "a signal is locked", not "this game has been looked at".
            # A NONE row is not a bet — freezing one would mean a model that
            # forms a view on Thursday could never fire it, which for the
            # totals rule (game-day by design, see NCAAF_TOTALS_MAX_LEAD_DAYS)
            # is every single game. Signals still lock at first cross, which is
            # exactly the opener rule's thesis.
            for gid, mid in conn.execute("""
                SELECT p.game_id, p.model_id
                FROM picks p JOIN games g ON g.game_id = p.game_id
                WHERE p.game_date >= %s AND p.result IS NULL
                  AND (g.sport != 'NCAAF' OR p.signal_type != 'NONE')
            """, (target_date,)).fetchall():
                locked_pairs.add((gid, mid))
            if locked_pairs:
                logger.info(f"Pick lock: {len(locked_pairs)} game-model pick(s) "
                            f"already locked for {target_date} — preserving")

        # Only delete unsettled picks for games that haven't started yet.
        # This preserves picks for games already in progress or completed so
        # they still get settled. Picks for upcoming games are re-scored with
        # the latest odds. SKIPPED when locking is on (picks are frozen instead).
        if not dry_run:
            # Broad same-day delete — only when locking is OFF (old behavior:
            # wipe and re-score every refresh). When locking is ON it's skipped
            # so the morning picks stay frozen.
            if not LOCK_GAME_PICKS_AT_FIRST_RUN:
                conn.execute("""
                    DELETE FROM picks
                    WHERE game_date = %s
                      AND result IS NULL
                      AND game_id IN (
                          SELECT game_id FROM games
                          WHERE game_date = %s
                            AND (commence_time IS NULL OR commence_time > %s)
                      )
                """, (target_date, target_date, now_utc))
            # UFC look-ahead. This used to ALWAYS re-score, on the theory that
            # early-week lines are soft. That contradicted the pick lock: the
            # first cross IS the bet of record, and a pick must never be
            # withdrawn because the price later moved out of range — that is the
            # CLV thesis, and a pick that vanishes cannot demonstrate it.
            # Now it is deleted only when locking is OFF; with locking ON the
            # per-model skip below freezes these exactly like same-day picks.
            if not LOCK_GAME_PICKS_AT_FIRST_RUN:
                conn.execute("""
                    DELETE FROM picks
                    WHERE result IS NULL
                      AND game_id IN (
                          SELECT game_id FROM games
                          WHERE sport = 'UFC'
                            AND game_date > %s AND game_date <= %s
                            AND (commence_time IS NULL OR commence_time > %s)
                      )
                """, (target_date, ufc_horizon, now_utc))
            # NCAAF look-ahead housekeeping. Its "no signal" rows are NOT in
            # locked_pairs (above), so without this they would be re-inserted
            # on every pass. Delete + rescore keeps exactly one current row per
            # side while a game has no signal; the moment a rule fires, that
            # row is a BET/AVOID, joins locked_pairs, and is never touched
            # again. Scoped to unstarted games, so nothing settleable is hit.
            conn.execute("""
                DELETE FROM picks
                WHERE result IS NULL
                  AND signal_type = 'NONE'
                  AND game_id IN (
                      SELECT game_id FROM games
                      WHERE sport = 'NCAAF'
                        AND game_date >= %s AND game_date <= %s
                        AND (commence_time IS NULL OR commence_time > %s)
                  )
            """, (target_date, ncaaf_horizon, now_utc))

            logger.info(f"Cleared unsettled picks for games not yet started")

        all_picks = []
        model_failures: list[str] = []
        skipped_started = 0
        skipped_postponed = 0
        skipped_locked = 0
        for game in games:
            game_id, sport, season, game_date, home_team, away_team, commence_time = game

            if game_id in ncaaf_unpriced:
                continue

            # Skip postponed games
            if game_id in postponed_ids:
                skipped_postponed += 1
                continue

            # Skip games that have already started — their picks are locked in
            if commence_time and commence_time <= now_utc:
                skipped_started += 1
                continue

            # Build features once per game, reuse across all models for that sport
            odds_mlb_h2h  = _get_dk_odds(conn, game_id, "h2h")

            # UFC: only score fights DK actually prices. The Odds API sometimes
            # lists speculative/rumored matchups from other books (e.g. the same
            # fighter against three different opponents on one date) and the
            # odds ingestor creates games rows for them. Moneyline already skips
            # without odds, but round totals and method are prob-only and would
            # fire picks on fights that don't exist. A DK h2h row is the
            # "this fight is real" signal — DK prices every real UFC bout.
            if sport == "UFC" and not odds_mlb_h2h:
                logger.info(f"  [SKIP] {away_team} vs {home_team} — no DK h2h "
                            f"odds (unconfirmed/speculative bout)")
                continue

            if sport == "MLB":
                features = build_mlb_game_features(
                    conn, game_id, game_date, home_team, away_team, season,
                    odds_row=odds_mlb_h2h
                )
            elif sport == "WNBA":
                from features.wnba_feature_engine import build_wnba_game_features
                features = build_wnba_game_features(
                    conn, game_id, game_date, home_team, away_team, season,
                    odds_row=odds_mlb_h2h
                )
            elif sport == "NBA":
                from features.nba_feature_engine import build_nba_game_features
                features = build_nba_game_features(
                    conn, game_id, game_date, home_team, away_team, season,
                    odds_row=odds_mlb_h2h
                )
            elif sport == "UFC":
                from features.ufc_feature_engine import build_ufc_game_features
                features = build_ufc_game_features(
                    conn, game_id, game_date, home_team, away_team, season,
                    odds_row=odds_mlb_h2h
                )
            elif sport == "NCAAF":
                from features.ncaaf_feature_engine import build_ncaaf_game_features
                features = build_ncaaf_game_features(
                    conn, game_id, game_date, home_team, away_team, season,
                    odds_row=odds_mlb_h2h
                )
            else:  # NHL
                features = build_nhl_game_features(
                    conn, game_id, game_date, home_team, away_team, season,
                    odds_row=odds_mlb_h2h
                )

            if not features:
                continue

            # Run all models for this sport
            relevant_models = [mid for mid, (sp, _, _) in MODELS.items()
                               if sp == sport]

            for model_id in relevant_models:
                # Pick lock: a same-day game-model pick written on an earlier run
                # today is frozen — skip re-scoring it (config.LOCK_GAME_PICKS_AT_
                # FIRST_RUN). Other models for this game still fire when their odds
                # post. Future-dated UFC/golf look-ahead IS in locked_pairs now
                # (the set spans game_date >= target_date), so it freezes too.
                if (game_id, model_id) in locked_pairs:
                    skipped_locked += 1
                    continue
                # One model must never be able to take down the scoring
                # step for every sport. On 2026-08-29 a missing FEATURE_MAP
                # entry for ncaaf_spread_premium raised KeyError out of here,
                # and MLB, WNBA, NHL and UFC game picks stopped for the whole
                # day — while the only visible symptom was an empty NCAAF
                # board. Contain the blast radius, but stay LOUD: the failure
                # is re-raised after the surviving picks are committed, so the
                # step is still marked failed and refresh_pass_steps still
                # CRITs. Swallowing it here would be worse than the crash.
                try:
                    picks = score_game(conn, game_id, model_id, features,
                                        bankroll, dry_run=dry_run,
                                        commence_time=commence_time)
                except Exception as exc:
                    model_failures.append(f"{model_id}: {exc!r}")
                    logger.error(f"  {game_id}/{model_id} FAILED: {exc!r}")
                    continue
                all_picks.extend(picks)

                for p in picks:
                    signal = p["signal_type"]
                    tier   = p["confidence_tier"]
                    edge_pct = p["edge"] * 100
                    if p['dk_odds'] is None:
                        dk_odds_str = "N/A"
                    elif p['dk_odds'] > 0:
                        dk_odds_str = f"+{int(p['dk_odds'])}"
                    else:
                        dk_odds_str = str(int(p['dk_odds']))
                    logger.info(
                        f"  [{signal}] {p['pick_label']} | "
                        f"DK={dk_odds_str} | "
                        f"model={p['model_probability']:.3f} | "
                        f"edge={edge_pct:+.1f}% | "
                        f"bet=${p['recommended_bet']:.0f} | "
                        f"[{tier}]"
                    )

        if skipped_postponed:
            logger.info(f"Skipped {skipped_postponed} postponed game(s)")
        if skipped_started:
            logger.info(f"Skipped {skipped_started} games already started (picks locked)")
        if skipped_locked:
            logger.info(f"Skipped {skipped_locked} game-model pick(s) locked from an earlier run today")

        if not dry_run:
            conn.commit()

        # Committed first: the picks that DID score are real and should land.
        # Only then fail the step, so the outer handler's rollback has nothing
        # to undo and the run is still reported as broken.
        if model_failures:
            uniq = sorted(set(model_failures))
            raise RuntimeError(
                f"{len(model_failures)} model-game scoring failure(s); "
                f"distinct: {'; '.join(uniq[:5])}"
            )

        bets   = [p for p in all_picks if p["signal_type"] == "BET"]
        avoids = [p for p in all_picks if p["signal_type"] == "AVOID"]

        duration = (datetime.now() - start).total_seconds()
        if not dry_run:
            _log_pipeline(conn, target_date, "success",
                          records_in=len(games),
                          records_out=len(all_picks),
                          duration_s=duration)
            conn.commit()

        logger.success(
            f"\nScoring complete: {len(bets)} BETs | "
            f"{len(avoids)} AVOIDs | {duration:.1f}s"
        )

        return {
            "target_date": target_date,
            "games":       len(games),
            "total_picks": len(all_picks),
            "bets":        len(bets),
            "avoids":      len(avoids),
            "dry_run":     dry_run,
            "duration_s":  duration,
        }

    except Exception as exc:
        conn.rollback()
        duration = (datetime.now() - start).total_seconds()
        _log_pipeline(conn, target_date, "error", 0, 0, duration, str(exc))
        conn.commit()
        logger.error(f"Scorer failed: {exc}")
        raise
    finally:
        conn.close()


def _get_current_bankroll(conn: DBConnection) -> float:
    """Get current bankroll from last pick or fall back to config default."""
    row = conn.execute("""
        SELECT bankroll_at_pick, profit_kelly
        FROM picks
        WHERE result IS NOT NULL
        ORDER BY settled_at DESC
        LIMIT 1
    """).fetchone()

    if row and row[0] is not None and row[1] is not None:
        return row[0] + row[1]

    return BANKROLL


# ── Prop Scorer ───────────────────────────────────────────────────────────────

# MLB team name → abbreviation map for statsapi schedule results
_MLB_TEAM_ABBR = {
    "Arizona Diamondbacks": "ARI", "Atlanta Braves": "ATL", "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS", "Chicago Cubs": "CHC", "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN", "Cleveland Guardians": "CLE", "Colorado Rockies": "COL",
    "Detroit Tigers": "DET", "Houston Astros": "HOU", "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA", "Los Angeles Dodgers": "LAD", "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL", "Minnesota Twins": "MIN", "New York Mets": "NYM",
    "New York Yankees": "NYY", "Oakland Athletics": "OAK", "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT", "San Diego Padres": "SD", "Seattle Mariners": "SEA",
    "San Francisco Giants": "SF", "St. Louis Cardinals": "STL", "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX", "Toronto Blue Jays": "TOR", "Washington Nationals": "WSH",
    "Athletics": "OAK",
}


def _poisson_over_prob(lam: float, line: float) -> float:
    """
    P(actual strikeouts > line) using a Poisson distribution with mean=lam.
    DK K props use half-point lines (e.g. 5.5), so P(K > 5.5) = P(K >= 6).
    """
    return float(1.0 - scipy_stats.poisson.cdf(int(np.floor(line)), lam))


def _get_prop_dk_odds(conn: DBConnection, game_id: str,
                      player_name: str, market: str) -> dict | None:
    """
    Fetch the latest DraftKings prop odds for a player+game+market from
    player_prop_odds. Matches on exact player_name — both sources (statsapi
    and prop_odds_ingestor) use the MLB API's canonical full name.
    """
    row = conn.execute("""
        SELECT line, over_price, under_price, over_link, under_link
        FROM player_prop_odds
        WHERE game_id     = %s
          AND player_name = %s
          AND market      = %s
          AND bookmaker   = 'draftkings'
        ORDER BY snapshot_at DESC
        LIMIT 1
    """, (game_id, player_name, market)).fetchone()

    if row:
        return {"line": row[0], "over_price": row[1], "under_price": row[2],
                "over_link": row[3], "under_link": row[4]}
    return None


def _lookup_player_id(conn: DBConnection, player_name: str, season: int) -> str | None:
    """
    Resolve player_name → player_id from historical player_game_log rows.
    Prefers entries from the current or most recent season.
    """
    row = conn.execute("""
        SELECT player_id FROM player_game_log
        WHERE LOWER(player_name) = LOWER(%s)
          AND player_type = 'pitcher'
        ORDER BY ABS(season - %s), game_date DESC
        LIMIT 1
    """, (player_name, season)).fetchone()
    return str(row[0]) if row else None


def _get_probable_pitchers(target_date: str, conn: DBConnection) -> list[dict]:
    """
    Fetch today's probable starters from the MLB Stats API.
    Returns a list of dicts: {player_id, player_name, team, game_id}.
    Skips pitchers whose player_id cannot be resolved from player_game_log.
    """
    if not STATSAPI_AVAILABLE:
        logger.warning("statsapi not available — cannot fetch probable pitchers")
        return []

    season = int(target_date[:4])
    try:
        schedule = statsapi.schedule(date=target_date, sportId=1)
    except Exception as exc:
        logger.error(f"statsapi.schedule failed: {exc}")
        return []

    pitchers = []
    for game in schedule:
        status = game.get("status", "")
        if status in ("Postponed", "Suspended", "Cancelled"):
            continue

        home_name = _MLB_TEAM_ABBR.get(game.get("home_name", ""), "")
        away_name = _MLB_TEAM_ABBR.get(game.get("away_name", ""), "")
        if not home_name or not away_name:
            continue

        game_id = f"MLB_{target_date}_{away_name}_{home_name}"

        for side, team_abbr in [("home_probable_pitcher", home_name),
                                  ("away_probable_pitcher", away_name)]:
            pitcher_name = game.get(side, "")
            if not pitcher_name:
                continue

            player_id = _lookup_player_id(conn, pitcher_name, season)
            if not player_id:
                logger.debug(f"  No player_id for '{pitcher_name}' — skipping")
                continue

            pitchers.append({
                "player_id":   player_id,
                "player_name": pitcher_name,
                "team":        team_abbr,
                "game_id":     game_id,
            })

    logger.info(f"Found {len(pitchers)} probable starters for {target_date}")
    return pitchers


def _make_prop_pick(game_id: str, model_id: str, game_date: str,
                    player_name: str, pick_side: str,
                    model_prob: float,
                    dk_implied_prob: float | None,
                    edge: float | None,
                    dk_odds: float | None, line: float,
                    bankroll: float,
                    stat_label: str = "Ks",
                    player_id: str = None,
                    pitcher_throw_hand: str = None,
                    sport: str = "MLB",
                    dk_bet_link: str = None,
                    commence_time: str | None = None) -> dict | None:
    """
    Build a prop pick dict. Returns None only if edge exceeds noise cap.
    BET/AVOID/NONE rows are all written to DB so the website can display every starter.

    stat_label: human-readable stat name shown in pick_label (e.g. "Ks", "Hits", "TB", "HR")

    dk_implied_prob / edge / dk_odds may be None for prob-only models when DK
    does not list the market — the pick is then decided on model_prob alone
    and stored with 0.0 placeholders for the NOT NULL implied/edge columns.
    """
    no_dk_price = dk_implied_prob is None
    if not no_dk_price and abs(edge) > MAX_EDGE_CAP:
        return None

    bet_thresh  = MODEL_EDGE_THRESHOLDS.get(model_id, BET_EDGE_THRESHOLD)
    prob_thresh = MODEL_PROB_THRESHOLDS.get(model_id, MIN_MODEL_PROB)

    if model_id in PROB_ONLY_MODELS and no_dk_price:
        # No real DK price. Historically these still fired on model_prob alone;
        # under config.REQUIRE_DK_PRICE they no longer can — an unplaceable bet
        # is not a bet. The row is still written as NONE so the model keeps
        # accruing a tracked record. AVOID is meaningless for these over-only
        # markets, so we never emit AVOID.
        signal_type = ("NONE" if REQUIRE_DK_PRICE
                       else ("BET" if model_prob >= prob_thresh else "NONE"))
    elif model_id in PROB_ONLY_MODELS:
        # A real DK price IS available — apply the +EV edge filter to maximize
        # ROI (e.g. HR overs at +250..+500: only bet when the model beats DK's
        # implied price). Over-only, so never AVOID.
        signal_type = "BET" if (edge >= bet_thresh and model_prob >= prob_thresh) else "NONE"
    elif edge >= bet_thresh and model_prob >= prob_thresh:
        signal_type = "BET"
    elif edge <= -bet_thresh:
        signal_type = "AVOID"
    else:
        signal_type = "NONE"

    # No price, no bet. A BET must be placeable somewhere.
    if signal_type == "BET" and _missing_price(dk_odds):
        logger.debug(f"  {player_name}: no book price — BET → NONE")
        signal_type = "NONE"

    # Price too juicy for this model (config.MODEL_MIN_ODDS) — no bet. NULL
    # dk_odds (prob-only fallback) is never blocked.
    if signal_type == "BET" and _blocked_by_min_odds(model_id, dk_odds):
        logger.debug(f"  {player_name}: DK {dk_odds:+.0f} below the "
                     f"{MODEL_MIN_ODDS[model_id]} price floor — BET → NONE")
        signal_type = "NONE"

    # Paused models never fire a BET — downgrade to NONE (no bet, no settlement).
    if model_id in PAUSED_MODELS and signal_type == "BET":
        signal_type = "NONE"

    direction = "Over" if pick_side == "over" else "Under"
    pick_label = f"{player_name} {direction} {line} {stat_label}"
    if signal_type == "NONE" or no_dk_price:
        # Kelly needs a real DK implied prob to size; without it, surface as $0.
        kelly_frac, rec_bet = 0.0, 0.0
    else:
        kelly_frac, rec_bet = quarter_kelly(model_prob, dk_implied_prob, bankroll)
        # Per-model stake dial-down for high-variance markets (e.g. HR longshots).
        _mult = MODEL_BET_SIZE_MULTIPLIER.get(model_id, 1.0)
        if _mult != 1.0:
            kelly_frac *= _mult
            rec_bet    *= _mult

    if dk_odds is not None and dk_odds > 0:
        dk_odds_str = f"+{int(dk_odds)}"
    elif dk_odds is not None:
        dk_odds_str = str(int(dk_odds))
    else:
        dk_odds_str = "N/A"

    edge_for_display = 0.0 if edge is None else edge
    logger.info(
        f"  [{signal_type}] {pick_label} | "
        f"DK={dk_odds_str} | "
        f"model={model_prob:.3f} | "
        f"edge={edge_for_display*100:+.1f}% | "
        f"bet=${rec_bet:.0f} | "
        f"[{_confidence_tier(edge_for_display)}]"
    )

    return {
        "game_id":             game_id,
        "model_id":            model_id,
        "sport":               sport,
        "game_date":           game_date,
        "pick_side":           pick_side,
        "pick_label":          pick_label,
        "model_probability":   round(model_prob, 4),
        "dk_implied_prob":     round(dk_implied_prob, 4) if dk_implied_prob is not None else 0.0,
        "edge":                round(edge, 4) if edge is not None else 0.0,
        "dk_odds":             dk_odds,
        "scored_line":         line,
        "player_id":           player_id,
        "pitcher_throw_hand":  pitcher_throw_hand,
        "kelly_fraction":    kelly_frac,
        "recommended_bet":   rec_bet,
        "bankroll_at_pick":  bankroll,
        "injury_flag":       None,
        "injury_detail":     None,
        "signal_type":       signal_type,
        "confidence_tier":   _confidence_tier(edge_for_display),
        "game_time":         commence_time,
        "dk_bet_link":       dk_bet_link,
    }


# ── Pitcher Prop Config ───────────────────────────────────────────────────────

# Per-model: DK market name and stat label for pick label generation.
# All pitcher props use Poisson regression — same scoring loop for every entry.
_PITCHER_PROP_CONFIG: dict[str, dict] = {
    "mlb_prop_pitcher_k": {
        "market":     "pitcher_strikeouts",
        "stat_label": "Ks",
    },
    "mlb_prop_pitcher_hits": {
        "market":     "pitcher_hits_allowed",
        "stat_label": "Hits",
    },
    "mlb_prop_pitcher_er": {
        "market":     "pitcher_earned_runs",
        "stat_label": "ER",
    },
    "mlb_prop_pitcher_outs": {
        "market":     "pitcher_outs",
        "stat_label": "Outs",
    },
    "mlb_prop_pitcher_walks": {
        "market":     "pitcher_walks",
        "stat_label": "Walks",
    },
}


# ── Batter Prop Config ────────────────────────────────────────────────────────

# Per-model: DK market name and stat label for pick label generation.
_BATTER_PROP_CONFIG: dict[str, dict] = {
    "mlb_prop_batter_hits": {
        "market":     "batter_hits",
        "stat_label": "Hits",
    },
    "mlb_prop_batter_tb": {
        "market":     "batter_total_bases",
        "stat_label": "TB",
    },
    "mlb_prop_batter_hr": {
        "market":     "batter_home_runs",
        "stat_label": "HR",
        "over_only":  True,    # DK only prices the Yes/Over 0.5 side meaningfully
    },
    "mlb_prop_batter_rbi": {
        "market":     "batter_rbis",
        "stat_label": "RBI",
    },
    "mlb_prop_batter_runs": {
        "market":     "batter_runs_scored",
        "stat_label": "Runs",
    },
    "mlb_prop_batter_sb": {
        "market":     "batter_stolen_bases",
        "stat_label": "SB",
        "over_only":  True,    # DK only prices Over 0.5 SBs meaningfully
    },
    "mlb_prop_batter_walks": {
        "market":     "batter_walks",
        "stat_label": "Walks",
    },
}


def _locked_prop_keys(conn: DBConnection, target_date: str, model_ids) -> set:
    """First-signal prop lock (config.LOCK_PROP_PICKS_AT_FIRST_SIGNAL): the set of
    (game_id, model_id, player_id) tuples that already have an unsettled pick for
    target_date among the given models. The prop scorers skip these so the first
    confirmed-lineup signal of the day stays put and later refreshes don't
    overwrite it. Returns an empty set when locking is off (old delete+rescore)."""
    if not LOCK_PROP_PICKS_AT_FIRST_SIGNAL:
        return set()
    mids = set(model_ids)
    rows = conn.execute("""
        SELECT game_id, model_id, player_id FROM picks
        WHERE game_date = %s AND result IS NULL
    """, (target_date,)).fetchall()
    keys = {(g, m, p) for g, m, p in rows if m in mids}
    if keys:
        logger.info(f"Prop lock: preserving {len(keys)} prop pick(s) locked from "
                    f"an earlier run today")
    return keys


def run_batter_prop_scorer(target_date: str = None, dry_run: bool = False) -> dict:
    """
    Score batter prop markets (hits, TB, HR, RBI, runs, SB, walks) for today's
    confirmed lineup.

    Runs each model sequentially. Requires confirmed lineups in lineup_slots —
    returns 0 picks if no lineups are posted yet (expected in the morning).

    For Poisson models (hits, TB, RBI, runs, walks): predict lambda → P(over line)
    via Poisson CDF. For logistic models (HR, SB): predict_proba → P(outcome >= 1).

    Idempotent: deletes unsettled batter prop picks for target_date before inserting.
    """
    if target_date is None:
        target_date = date.today().isoformat()

    logger.info(f"Batter Prop Scorer — {target_date}")

    conn = get_connection()
    bankroll = _get_current_bankroll(conn)
    ct_map = _commence_time_map(conn, target_date, "MLB")

    total_picks = 0
    total_bets  = 0

    try:
        # First-signal prop lock: preserve picks locked on an earlier run today.
        locked_prop_keys = _locked_prop_keys(conn, target_date, _BATTER_PROP_CONFIG.keys())
        # Delete + rescore only when locking is OFF (old behavior).
        if not dry_run and not LOCK_PROP_PICKS_AT_FIRST_SIGNAL:
            for mid in _BATTER_PROP_CONFIG.keys():
                conn.execute("""
                    DELETE FROM picks
                    WHERE game_date = %s
                      AND model_id  = %s
                      AND result IS NULL
                """, (target_date, mid))
            conn.commit()

        for model_id, cfg in _BATTER_PROP_CONFIG.items():
            market     = cfg["market"]
            stat_label = cfg["stat_label"]
            max_line   = cfg.get("max_line")         # None = no cap
            over_only  = cfg.get("over_only", False) # skip under-side scoring

            # ── Load model ────────────────────────────────────────────────────
            artifact = load_model(model_id)
            if artifact is None:
                logger.debug(f"  No trained model for {model_id} — skipping")
                continue

            model_type   = artifact.get("model_type", "poisson")
            feature_cols = artifact["feature_cols"]
            model_obj    = artifact["model"]

            # ── Build scoring rows from today's confirmed lineups ─────────────
            df = build_batter_scoring_rows(target_date, model_id)
            if df.empty:
                logger.info(f"  {model_id}: no lineup rows — lineups not posted yet")
                continue

            # ── Predict ───────────────────────────────────────────────────────
            missing_cols = [c for c in feature_cols if c not in df.columns]
            for c in missing_cols:
                df[c] = np.nan

            X_raw = df[feature_cols].values.astype(float)
            X     = np.nan_to_num(X_raw, nan=0.0)

            had_nulls = np.isnan(X_raw).any(axis=1)
            if had_nulls.any():
                null_players = df.loc[had_nulls, "player_name"].tolist()
                logger.debug(f"  {model_id}: filled nulls for {null_players}")

            if model_type == "logistic":
                # CalibratedClassifierCV → predict_proba → P(outcome >= 1)
                probs_over = model_obj.predict_proba(X)[:, 1]
            else:
                # XGBRegressor → lambda → Poisson CDF
                lambdas    = np.clip(model_obj.predict(X), 1e-6, None)
                probs_over = None   # computed per-row below

            is_prob_only = model_id in PROB_ONLY_MODELS

            model_picks = []
            for i, row in df.iterrows():
                player_name        = row["player_name"]
                game_id            = row["game_id"]
                player_id          = row.get("player_id")
                if (game_id, model_id, player_id) in locked_prop_keys:
                    continue  # first-signal prop lock — already locked today
                if _game_started(ct_map.get(game_id)):
                    continue  # game underway — current DK prop prices are in-play
                pitcher_throw_hand = row.get("pitcher_throw_hand")

                # ── Fetch DK prop odds ────────────────────────────────────────
                prop_odds = _get_prop_dk_odds(conn, game_id, player_name, market)
                _best_ctx = (game_id, player_name, market)
                if prop_odds is None or prop_odds.get("line") is None:
                    if not is_prob_only:
                        logger.debug(f"    No DK odds for {player_name} {stat_label} — skipping")
                        continue
                    # PROB_ONLY models (e.g. HR): DK frequently doesn't list the market,
                    # but the model produces a meaningful probability on its own.
                    # Use the standard binary line (0.5) and write the pick with NULL pricing.
                    line        = 0.5
                    over_price  = None
                    under_price = None
                    over_link   = None
                    under_link  = None
                else:
                    line        = float(prop_odds["line"])
                    over_price  = prop_odds.get("over_price")
                    under_price = prop_odds.get("under_price")
                    over_link   = prop_odds.get("over_link")
                    under_link  = prop_odds.get("under_link")

                # Logistic HR model is only calibrated for 0.5 lines
                if max_line is not None and line > max_line:
                    logger.debug(
                        f"    {player_name}: line {line} > max {max_line} for {model_id} — skipping"
                    )
                    continue

                # ── Compute probabilities ─────────────────────────────────────
                if model_type == "logistic":
                    p_over  = float(probs_over[i])
                else:
                    lam     = float(lambdas[i])
                    p_over  = _poisson_over_prob(lam, line)

                p_under = 1.0 - p_over

                logger.debug(
                    f"    {player_name}: line={line} "
                    f"P(over)={p_over:.3f} P(under)={p_under:.3f}"
                )

                # ── Score over ────────────────────────────────────────────────
                if over_price is not None:
                    dk_ip_over = american_to_implied_prob(over_price)
                    if dk_ip_over:
                        pick = _make_prop_pick(
                            game_id=game_id, model_id=model_id,
                            game_date=target_date,
                            player_name=player_name, pick_side="over",
                            model_prob=p_over, dk_implied_prob=dk_ip_over,
                            edge=p_over - dk_ip_over,
                            dk_odds=over_price, line=line,
                            bankroll=bankroll, stat_label=stat_label,
                            player_id=player_id,
                            pitcher_throw_hand=pitcher_throw_hand,
                            dk_bet_link=over_link,
                            commence_time=ct_map.get(game_id),
                        )
                        if pick:
                            model_picks.append(_tag_prop(pick, _best_ctx))
                elif is_prob_only:
                    # No DK price — still emit a prob-only over pick so the
                    # model's HR favorites surface in the picks table.
                    pick = _make_prop_pick(
                        game_id=game_id, model_id=model_id,
                        game_date=target_date,
                        player_name=player_name, pick_side="over",
                        model_prob=p_over, dk_implied_prob=None,
                        edge=None, dk_odds=None, line=line,
                        bankroll=bankroll, stat_label=stat_label,
                        player_id=player_id,
                        pitcher_throw_hand=pitcher_throw_hand,
                        dk_bet_link=over_link,
                        commence_time=ct_map.get(game_id),
                    )
                    if pick:
                        model_picks.append(_tag_prop(pick, _best_ctx))

                # ── Score under ───────────────────────────────────────────────
                if under_price is not None and not over_only:
                    dk_ip_under = american_to_implied_prob(under_price)
                    if dk_ip_under:
                        pick = _make_prop_pick(
                            game_id=game_id, model_id=model_id,
                            game_date=target_date,
                            player_name=player_name, pick_side="under",
                            model_prob=p_under, dk_implied_prob=dk_ip_under,
                            edge=p_under - dk_ip_under,
                            dk_odds=under_price, line=line,
                            bankroll=bankroll, stat_label=stat_label,
                            player_id=player_id,
                            pitcher_throw_hand=pitcher_throw_hand,
                            dk_bet_link=under_link,
                            commence_time=ct_map.get(game_id),
                        )
                        if pick:
                            model_picks.append(_tag_prop(pick, _best_ctx))

            bets = [p for p in model_picks if p["signal_type"] == "BET"]
            logger.info(
                f"  {model_id}: {len(bets)} BETs / "
                f"{len(model_picks) - len(bets)} non-BET "
                f"({len(df)} batters evaluated)"
            )

            if model_picks and not dry_run:
                _insert_picks(conn, model_picks)
                conn.commit()

            total_picks += len(model_picks)
            total_bets  += len(bets)

    except Exception as exc:
        conn.rollback()
        logger.error(f"Batter prop scorer failed: {exc}")
        raise
    finally:
        conn.close()

    logger.success(
        f"Batter prop scoring complete: {total_bets} BETs / {total_picks} total picks"
    )
    return {
        "target_date": target_date,
        "prop_picks":  total_picks,
        "bets":        total_bets,
        "dry_run":     dry_run,
    }


# ── WNBA Prop Config ──────────────────────────────────────────────────────────

# Per-model: DK market name + stat label. All WNBA props are Poisson over/under.
_WNBA_PROP_CONFIG: dict[str, dict] = {
    "wnba_prop_player_points":   {"market": "player_points",                  "stat_label": "Pts"},
    "wnba_prop_player_rebounds": {"market": "player_rebounds",                "stat_label": "Reb"},
    "wnba_prop_player_assists":  {"market": "player_assists",                 "stat_label": "Ast"},
    "wnba_prop_player_threes":   {"market": "player_threes",                  "stat_label": "3PM"},
    "wnba_prop_player_pra":      {"market": "player_points_rebounds_assists", "stat_label": "PRA"},
}


def run_wnba_prop_scorer(target_date: str = None, dry_run: bool = False) -> dict:
    """
    Score WNBA player prop markets (points, rebounds, assists, threes, PRA).

    All Poisson: predict lambda → P(over line) via Poisson CDF → edge vs DK
    implied. Candidate players come from build_wnba_prop_scoring_rows, which
    prefers confirmed lineups but falls back to recent rotation players (WNBA
    rotations are stable), so picks fire even before lineups post.

    Idempotent: deletes unsettled WNBA prop picks for target_date before insert.
    """
    from features.wnba_prop_feature_engine import build_wnba_prop_scoring_rows

    if target_date is None:
        target_date = date.today().isoformat()

    logger.info(f"WNBA Prop Scorer — {target_date}")

    conn = get_connection()
    bankroll = _get_current_bankroll(conn)
    ct_map = _commence_time_map(conn, target_date, "WNBA")
    total_picks = 0
    total_bets  = 0

    try:
        locked_prop_keys = _locked_prop_keys(conn, target_date, _WNBA_PROP_CONFIG.keys())
        if not dry_run and not LOCK_PROP_PICKS_AT_FIRST_SIGNAL:
            for mid in _WNBA_PROP_CONFIG:
                conn.execute("""
                    DELETE FROM picks
                    WHERE game_date = %s AND model_id = %s AND result IS NULL
                """, (target_date, mid))
            conn.commit()

        for model_id, cfg in _WNBA_PROP_CONFIG.items():
            market     = cfg["market"]
            stat_label = cfg["stat_label"]

            artifact = load_model(model_id)
            if artifact is None:
                logger.debug(f"  No trained model for {model_id} — skipping")
                continue

            feature_cols = artifact["feature_cols"]
            model_obj    = artifact["model"]

            df = build_wnba_prop_scoring_rows(target_date, model_id)
            if df.empty:
                logger.info(f"  {model_id}: no scoring rows for {target_date}")
                continue

            for c in [c for c in feature_cols if c not in df.columns]:
                df[c] = np.nan
            X = np.nan_to_num(df[feature_cols].values.astype(float), nan=0.0)
            lambdas = np.clip(model_obj.predict(X), 1e-6, None)

            model_picks = []
            for i, row in df.iterrows():
                player_name = row["player_name"]
                game_id     = row["game_id"]
                player_id   = row.get("player_id")
                if (game_id, model_id, player_id) in locked_prop_keys:
                    continue  # first-signal prop lock — already locked today
                if _game_started(ct_map.get(game_id)):
                    continue  # game underway — current DK prop prices are in-play

                prop_odds = _get_prop_dk_odds(conn, game_id, player_name, market)
                _best_ctx = (game_id, player_name, market)
                if prop_odds is None or prop_odds.get("line") is None:
                    continue
                line        = float(prop_odds["line"])
                over_price  = prop_odds.get("over_price")
                under_price = prop_odds.get("under_price")
                over_link   = prop_odds.get("over_link")
                under_link  = prop_odds.get("under_link")

                lam     = float(lambdas[i])
                p_over  = _poisson_over_prob(lam, line)
                p_under = 1.0 - p_over

                if over_price is not None:
                    dk_ip_over = american_to_implied_prob(over_price)
                    if dk_ip_over:
                        pick = _make_prop_pick(
                            game_id=game_id, model_id=model_id,
                            game_date=target_date,
                            player_name=player_name, pick_side="over",
                            model_prob=p_over, dk_implied_prob=dk_ip_over,
                            edge=p_over - dk_ip_over,
                            dk_odds=over_price, line=line,
                            bankroll=bankroll, stat_label=stat_label,
                            player_id=player_id, sport="WNBA",
                            dk_bet_link=over_link,
                            commence_time=ct_map.get(game_id),
                        )
                        if pick:
                            model_picks.append(_tag_prop(pick, _best_ctx))
                if under_price is not None:
                    dk_ip_under = american_to_implied_prob(under_price)
                    if dk_ip_under:
                        pick = _make_prop_pick(
                            game_id=game_id, model_id=model_id,
                            game_date=target_date,
                            player_name=player_name, pick_side="under",
                            model_prob=p_under, dk_implied_prob=dk_ip_under,
                            edge=p_under - dk_ip_under,
                            dk_odds=under_price, line=line,
                            bankroll=bankroll, stat_label=stat_label,
                            player_id=player_id, sport="WNBA",
                            dk_bet_link=under_link,
                            commence_time=ct_map.get(game_id),
                        )
                        if pick:
                            model_picks.append(_tag_prop(pick, _best_ctx))

            bets = [p for p in model_picks if p["signal_type"] == "BET"]
            logger.info(
                f"  {model_id}: {len(bets)} BETs / {len(model_picks) - len(bets)} non-BET "
                f"({len(df)} players evaluated)"
            )
            if model_picks and not dry_run:
                _insert_picks(conn, model_picks)
                conn.commit()
            total_picks += len(model_picks)
            total_bets  += len(bets)

    except Exception as exc:
        conn.rollback()
        logger.error(f"WNBA prop scorer failed: {exc}")
        raise
    finally:
        conn.close()

    logger.success(
        f"WNBA prop scoring complete: {total_bets} BETs / {total_picks} total picks"
    )
    return {
        "target_date": target_date,
        "prop_picks":  total_picks,
        "bets":        total_bets,
        "dry_run":     dry_run,
    }


# ── NBA Prop Config ───────────────────────────────────────────────────────────

# Per-model: DK market name + stat label. Counts are Poisson over/under; the
# double-double model is logistic + over-only (Yes/No, 0.5 line) and prob-only
# (decided on model probability — DK juices DD heavily; see PROB_ONLY_MODELS).
_NBA_PROP_CONFIG: dict[str, dict] = {
    "nba_prop_player_points":    {"market": "player_points",                  "stat_label": "Pts"},
    "nba_prop_player_rebounds":  {"market": "player_rebounds",                "stat_label": "Reb"},
    "nba_prop_player_assists":   {"market": "player_assists",                 "stat_label": "Ast"},
    "nba_prop_player_threes":    {"market": "player_threes",                  "stat_label": "3PM"},
    "nba_prop_player_pra":       {"market": "player_points_rebounds_assists", "stat_label": "PRA"},
    "nba_prop_player_blocks":    {"market": "player_blocks",                  "stat_label": "Blk"},
    "nba_prop_player_steals":    {"market": "player_steals",                  "stat_label": "Stl"},
    "nba_prop_player_turnovers": {"market": "player_turnovers",               "stat_label": "TO"},
    "nba_prop_player_dd":        {"market": "player_double_double",           "stat_label": "DD",
                                  "over_only": True},
}


def run_nba_prop_scorer(target_date: str = None, dry_run: bool = False) -> dict:
    """
    Score NBA player prop markets (points/reb/ast/threes/PRA/blocks/steals/
    turnovers + double-double).

    Poisson models: predict lambda → P(over line) via Poisson CDF → edge vs DK.
    Logistic model (double-double): predict_proba → P(Yes), prob-only signal.
    Candidate players come from build_nba_prop_scoring_rows (recent rotation).

    Idempotent: deletes unsettled NBA prop picks for target_date before insert.
    """
    from features.nba_prop_feature_engine import build_nba_prop_scoring_rows

    if target_date is None:
        target_date = date.today().isoformat()

    logger.info(f"NBA Prop Scorer — {target_date}")

    conn = get_connection()
    bankroll = _get_current_bankroll(conn)
    ct_map = _commence_time_map(conn, target_date, "NBA")
    total_picks = 0
    total_bets  = 0

    try:
        locked_prop_keys = _locked_prop_keys(conn, target_date, _NBA_PROP_CONFIG.keys())
        if not dry_run and not LOCK_PROP_PICKS_AT_FIRST_SIGNAL:
            for mid in _NBA_PROP_CONFIG:
                conn.execute("""
                    DELETE FROM picks
                    WHERE game_date = %s AND model_id = %s AND result IS NULL
                """, (target_date, mid))
            conn.commit()

        for model_id, cfg in _NBA_PROP_CONFIG.items():
            market     = cfg["market"]
            stat_label = cfg["stat_label"]
            over_only  = cfg.get("over_only", False)

            artifact = load_model(model_id)
            if artifact is None:
                logger.debug(f"  No trained model for {model_id} — skipping")
                continue

            model_type   = artifact.get("model_type", "poisson")
            feature_cols = artifact["feature_cols"]
            model_obj    = artifact["model"]

            df = build_nba_prop_scoring_rows(target_date, model_id)
            if df.empty:
                logger.info(f"  {model_id}: no scoring rows for {target_date}")
                continue

            for c in [c for c in feature_cols if c not in df.columns]:
                df[c] = np.nan
            X = np.nan_to_num(df[feature_cols].values.astype(float), nan=0.0)
            if model_type == "logistic":
                probs_over = model_obj.predict_proba(X)[:, 1]
                lambdas    = None
            else:
                lambdas    = np.clip(model_obj.predict(X), 1e-6, None)
                probs_over = None

            is_prob_only = model_id in PROB_ONLY_MODELS

            model_picks = []
            for i, row in df.iterrows():
                player_name = row["player_name"]
                game_id     = row["game_id"]
                player_id   = row.get("player_id")
                if (game_id, model_id, player_id) in locked_prop_keys:
                    continue  # first-signal prop lock — already locked today
                if _game_started(ct_map.get(game_id)):
                    continue  # game underway — current DK prop prices are in-play

                prop_odds = _get_prop_dk_odds(conn, game_id, player_name, market)
                _best_ctx = (game_id, player_name, market)
                if prop_odds is None or prop_odds.get("line") is None:
                    if not is_prob_only:
                        continue
                    # prob-only (double-double): DK may not list it — still emit
                    # the model's pick with NULL pricing on the 0.5 over side.
                    line        = 0.5
                    over_price  = None
                    under_price = None
                    over_link   = None
                    under_link  = None
                else:
                    line        = float(prop_odds["line"])
                    over_price  = prop_odds.get("over_price")
                    under_price = prop_odds.get("under_price")
                    over_link   = prop_odds.get("over_link")
                    under_link  = prop_odds.get("under_link")

                if model_type == "logistic":
                    p_over = float(probs_over[i])
                else:
                    p_over = _poisson_over_prob(float(lambdas[i]), line)
                p_under = 1.0 - p_over

                # ── Score over ────────────────────────────────────────────────
                if over_price is not None:
                    dk_ip_over = american_to_implied_prob(over_price)
                    if dk_ip_over:
                        pick = _make_prop_pick(
                            game_id=game_id, model_id=model_id,
                            game_date=target_date,
                            player_name=player_name, pick_side="over",
                            model_prob=p_over, dk_implied_prob=dk_ip_over,
                            edge=p_over - dk_ip_over,
                            dk_odds=over_price, line=line,
                            bankroll=bankroll, stat_label=stat_label,
                            player_id=player_id, sport="NBA",
                            dk_bet_link=over_link,
                            commence_time=ct_map.get(game_id),
                        )
                        if pick:
                            model_picks.append(_tag_prop(pick, _best_ctx))
                elif is_prob_only:
                    pick = _make_prop_pick(
                        game_id=game_id, model_id=model_id,
                        game_date=target_date,
                        player_name=player_name, pick_side="over",
                        model_prob=p_over, dk_implied_prob=None,
                        edge=None, dk_odds=None, line=line,
                        bankroll=bankroll, stat_label=stat_label,
                        player_id=player_id, sport="NBA",
                        dk_bet_link=over_link,
                        commence_time=ct_map.get(game_id),
                    )
                    if pick:
                        model_picks.append(_tag_prop(pick, _best_ctx))

                # ── Score under ───────────────────────────────────────────────
                if under_price is not None and not over_only:
                    dk_ip_under = american_to_implied_prob(under_price)
                    if dk_ip_under:
                        pick = _make_prop_pick(
                            game_id=game_id, model_id=model_id,
                            game_date=target_date,
                            player_name=player_name, pick_side="under",
                            model_prob=p_under, dk_implied_prob=dk_ip_under,
                            edge=p_under - dk_ip_under,
                            dk_odds=under_price, line=line,
                            bankroll=bankroll, stat_label=stat_label,
                            player_id=player_id, sport="NBA",
                            dk_bet_link=under_link,
                            commence_time=ct_map.get(game_id),
                        )
                        if pick:
                            model_picks.append(_tag_prop(pick, _best_ctx))

            bets = [p for p in model_picks if p["signal_type"] == "BET"]
            logger.info(
                f"  {model_id}: {len(bets)} BETs / {len(model_picks) - len(bets)} non-BET "
                f"({len(df)} players evaluated)"
            )
            if model_picks and not dry_run:
                _insert_picks(conn, model_picks)
                conn.commit()
            total_picks += len(model_picks)
            total_bets  += len(bets)

    except Exception as exc:
        conn.rollback()
        logger.error(f"NBA prop scorer failed: {exc}")
        raise
    finally:
        conn.close()

    logger.success(
        f"NBA prop scoring complete: {total_bets} BETs / {total_picks} total picks"
    )
    return {
        "target_date": target_date,
        "prop_picks":  total_picks,
        "bets":        total_bets,
        "dry_run":     dry_run,
    }


# ── NFL Player Props ──────────────────────────────────────────────────────────

_NFL_PROP_CONFIG: dict[str, dict] = {
    "nfl_prop_pass_yards":       {"market": "player_pass_yds",           "stat_label": "Pass Yds"},
    "nfl_prop_pass_attempts":    {"market": "player_pass_attempts",      "stat_label": "Pass Att"},
    "nfl_prop_pass_completions": {"market": "player_pass_completions",   "stat_label": "Comp"},
    "nfl_prop_pass_tds":         {"market": "player_pass_tds",           "stat_label": "Pass TD"},
    "nfl_prop_rush_yards":       {"market": "player_rush_yds",           "stat_label": "Rush Yds"},
    "nfl_prop_rush_attempts":    {"market": "player_rush_attempts",      "stat_label": "Carries"},
    "nfl_prop_rec_yards":        {"market": "player_reception_yds",      "stat_label": "Rec Yds"},
    "nfl_prop_receptions":       {"market": "player_receptions",         "stat_label": "Rec"},
    "nfl_prop_rush_rec_yards":   {"market": "player_rush_reception_yds", "stat_label": "Ru+Re Yds"},
    "nfl_prop_anytime_td":       {"market": "player_anytime_td",         "stat_label": "Anytime TD",
                                  "over_only": True},
    "nfl_prop_tackles_assists":  {"market": "player_tackles_assists",    "stat_label": "Tkl+Ast"},
    "nfl_prop_sacks":            {"market": "player_sacks",              "stat_label": "Sacks"},
}


def _nfl_prop_probs(artifact: dict, pred: float, line: float) -> tuple[float, float, float]:
    """
    (P(over), P(under), P(push)) from the model's own response distribution.

    The family is per-market and is stored on the artifact, because NFL markets
    do not share one: yardage is a zero-inflated Gamma (variance-to-mean 27-36),
    volume counts are negative binomial, TD counts are genuinely Poisson, and
    anytime-TD is a calibrated binary. Reading P(over) off a Poisson for all of
    them — which is what the platform's other prop scorers do — would
    miscalibrate pass attempts by 8.3 percentage points.

    Push is real and is returned separately rather than folded into `under`.
    NFL count lines are frequently whole numbers (4 receptions, 30 attempts),
    and a bet that pushes returns the stake — treating it as a loss understates
    every under and misprices every count market.
    """
    model_type = artifact.get("model_type", "poisson")

    if model_type == "logistic":
        p_over = float(pred)
        return p_over, 1.0 - p_over, 0.0

    if model_type == "gamma":
        # Continuous: a push has probability zero. The Gamma is re-scaled by
        # 1/(1-p0) so the zero-inflated MIXTURE mean equals the fitted mean.
        p0 = float(artifact.get("zero_inflation") or 0.0)
        k = float(artifact.get("gamma_shape") or 1.0)
        if line <= 0:
            return 1.0 - p0, p0, 0.0
        m = max(float(pred), 1e-6) / max(1.0 - p0, 1e-6)
        p_over = float((1.0 - p0) * scipy_stats.gamma.sf(line, a=k, scale=m / k))
        return p_over, 1.0 - p_over, 0.0

    mu = max(float(pred), 1e-6)
    nb_r = artifact.get("nb_r")
    if nb_r:
        r = float(nb_r)
        sf = lambda x: float(scipy_stats.nbinom.sf(x, r, r / (r + mu)))
        pmf = lambda x: float(scipy_stats.nbinom.pmf(x, r, r / (r + mu)))
    else:
        sf = lambda x: float(scipy_stats.poisson.sf(x, mu))
        pmf = lambda x: float(scipy_stats.poisson.pmf(x, mu))

    if float(line).is_integer():
        n = int(line)
        p_push = pmf(n)
        p_over = sf(n)                       # X > line
        return p_over, max(1.0 - p_over - p_push, 0.0), p_push
    p_over = sf(int(np.floor(line)))
    return p_over, 1.0 - p_over, 0.0


def _push_adjusted(p_side: float, p_push: float) -> float:
    """
    Probability of winning GIVEN the bet resolves — the quantity a price is
    quoted against. A push returns the stake, so the book's implied probability
    already excludes it; comparing a raw P(over) to that price would understate
    the model on every push-able line.
    """
    denom = 1.0 - p_push
    return float(p_side / denom) if denom > 1e-9 else 0.0


def _nfl_kickoff_map(conn: DBConnection, game_date: str) -> dict[str, str]:
    """{game_id: kickoff ISO} for a slate, from nfl_team_game_stats.

    NFL games only get a row in `games` when they carry a wind/opener pick, so
    the generic _commence_time_map cannot see a normal slate — and without a
    kickoff the started-game guard silently never fires.
    """
    rows = conn.execute("""
        SELECT DISTINCT game_id, commence_time
        FROM nfl_team_game_stats
        WHERE game_date = %s AND commence_time IS NOT NULL
    """, (game_date,)).fetchall()
    return {r[0]: (r[1].isoformat() if hasattr(r[1], "isoformat") else str(r[1]))
            for r in rows}


def run_nfl_prop_scorer(target_date: str = None, dry_run: bool = False) -> dict:
    """
    Score the NFL player-prop markets.

    Every model prices against a REAL DraftKings line — none is prob-only. A
    player with no quoted price is skipped, never priced at a synthetic number:
    an NFL prop's whole question is whether we beat the quote.
    """
    from features.nfl_prop_feature_engine import build_nfl_prop_scoring_rows
    from data.ingestors.nfl_prop_odds_ingestor import load_nfl_prop_odds
    from data.ingestors.nfl_props_data_ingestor import norm_player_name

    if target_date is None:
        target_date = date.today().isoformat()

    logger.info(f"NFL Prop Scorer — {target_date}")

    conn = get_connection()
    bankroll = _get_current_bankroll(conn)
    kickoffs = _nfl_kickoff_map(conn, target_date)
    # One prefetch for the whole slate, keyed on the NORMALISED player name.
    # The platform's _get_prop_dk_odds matches the name exactly, which is right
    # for MLB (one canonical spelling on both sides) and wrong for NFL, where
    # the odds feed and nflverse disagree on suffixes and accents.
    prop_odds_by_key = load_nfl_prop_odds(conn, list(kickoffs.keys()),
                                          list(PROP_MARKETS_NFL))
    total_picks = total_bets = 0

    try:
        locked = _locked_prop_keys(conn, target_date, _NFL_PROP_CONFIG.keys())
        if not dry_run and not LOCK_PROP_PICKS_AT_FIRST_SIGNAL:
            for mid in _NFL_PROP_CONFIG:
                conn.execute("""
                    DELETE FROM picks
                    WHERE game_date = %s AND model_id = %s AND result IS NULL
                """, (target_date, mid))
            conn.commit()

        for model_id, cfg in _NFL_PROP_CONFIG.items():
            market     = cfg["market"]
            stat_label = cfg["stat_label"]
            over_only  = cfg.get("over_only", False)

            artifact = load_model(model_id)
            if artifact is None:
                logger.debug(f"  No trained model for {model_id} — skipping")
                continue
            feature_cols = artifact["feature_cols"]
            model_obj    = artifact["model"]
            model_type   = artifact.get("model_type", "poisson")

            df = build_nfl_prop_scoring_rows(target_date, model_id)
            if df.empty:
                logger.info(f"  {model_id}: no scoring rows for {target_date}")
                continue

            for c in [c for c in feature_cols if c not in df.columns]:
                df[c] = np.nan
            X = df[feature_cols].values.astype(float)
            preds = (model_obj.predict_proba(X)[:, 1] if model_type == "logistic"
                     else np.clip(model_obj.predict(X), 1e-6, None))

            model_picks = []
            for i, row in df.iterrows():
                player_name = row["player_name"]
                game_id     = row["game_id"]
                player_id   = row.get("player_id")
                if (game_id, model_id, player_id) in locked:
                    continue
                if _game_started(kickoffs.get(game_id)):
                    continue   # kicked off — any quote now is an in-play price

                prop_odds = _get_prop_dk_odds(conn, game_id, player_name, market)
                _best_ctx = (game_id, player_name, market)
                if prop_odds is None or prop_odds.get("line") is None:
                    continue

                line = float(prop_odds["line"])
                p_over, p_under, p_push = _nfl_prop_probs(artifact, float(preds[i]), line)

                for side, raw_p, price, link in (
                    ("over",  p_over,  prop_odds.get("over_price"),  prop_odds.get("over_link")),
                    ("under", p_under, prop_odds.get("under_price"), prop_odds.get("under_link")),
                ):
                    if side == "under" and over_only:
                        continue
                    if price is None:
                        continue
                    dk_ip = american_to_implied_prob(price)
                    if not dk_ip:
                        continue
                    p_cond = _push_adjusted(raw_p, p_push)
                    pick = _make_prop_pick(
                        game_id=game_id, model_id=model_id, game_date=target_date,
                        player_name=player_name, pick_side=side,
                        model_prob=p_cond, dk_implied_prob=dk_ip,
                        edge=p_cond - dk_ip, dk_odds=price, line=line,
                        bankroll=bankroll, stat_label=stat_label,
                        player_id=player_id, sport="NFL", dk_bet_link=link,
                        commence_time=kickoffs.get(game_id),
                    )
                    if pick:
                        model_picks.append(_tag_prop(pick, _best_ctx))

            bets = [p for p in model_picks if p["signal_type"] == "BET"]
            logger.info(f"  {model_id}: {len(bets)} BETs / {len(model_picks) - len(bets)} "
                        f"non-BET ({len(df)} players evaluated)")
            if model_picks and not dry_run:
                _insert_picks(conn, model_picks)
                conn.commit()
            total_picks += len(model_picks)
            total_bets  += len(bets)

        logger.success(f"NFL props: {total_bets} BETs / {total_picks} picks")
        return {"picks": total_picks, "bets": total_bets}
    finally:
        conn.close()



# ── Golf Scoring ──────────────────────────────────────────────────────────────

# Per-player one-sided markets. Each player gets a single "yes" bet (to win /
# top-N / make the cut) priced against the DataGolf-sourced DK line in golf_odds.
_GOLF_OUTRIGHT_CONFIG: dict[str, dict] = {
    "golf_outright": {"market": "win",       "label": "to Win",          "renorm": True},
    "golf_top10":    {"market": "top_10",    "label": "Top 10",          "renorm": False},
    "golf_top20":    {"market": "top_20",    "label": "Top 20",          "renorm": False},
    "golf_make_cut": {"market": "make_cut",  "label": "to Make the Cut", "renorm": False},
}


def _make_golf_pick(game_id: str, model_id: str, game_date: str,
                    player_name: str, model_prob: float,
                    dk_implied_prob: float, edge: float, dk_odds: float,
                    bankroll: float, label: str, player_id: str,
                    pick_side: str = "yes",
                    commence_time: str = None) -> dict | None:
    """
    Build one golf pick dict (per-player or matchup). Mirrors _make_prop_pick's
    signal/Kelly/confidence logic but with golf labels. dk_implied_prob/edge are
    always real (DataGolf carries DK prices for every golf market). Returns None
    only when the edge exceeds the noise cap.
    """
    if abs(edge) > MAX_EDGE_CAP:
        return None

    bet_thresh  = MODEL_EDGE_THRESHOLDS.get(model_id, BET_EDGE_THRESHOLD)
    prob_thresh = MODEL_PROB_THRESHOLDS.get(model_id, MIN_MODEL_PROB)

    if edge >= bet_thresh and model_prob >= prob_thresh:
        signal_type = "BET"
    elif edge <= -bet_thresh:
        signal_type = "AVOID"
    else:
        signal_type = "NONE"

    if signal_type == "NONE":
        kelly_frac, rec_bet = 0.0, 0.0
    else:
        kelly_frac, rec_bet = quarter_kelly(model_prob, dk_implied_prob, bankroll)

    dk_str = (f"+{int(dk_odds)}" if dk_odds is not None and dk_odds > 0
              else str(int(dk_odds)) if dk_odds is not None else "N/A")
    logger.info(f"  [{signal_type}] {label} | DK={dk_str} | model={model_prob:.3f} | "
                f"edge={edge*100:+.1f}% | bet=${rec_bet:.0f}")

    return {
        "game_id":           game_id,
        "model_id":          model_id,
        "sport":             "GOLF",
        "game_date":         game_date,
        "pick_side":         pick_side,
        "pick_label":        label,
        "model_probability": round(model_prob, 4),
        "dk_implied_prob":   round(dk_implied_prob, 4),
        "edge":              round(edge, 4),
        "dk_odds":           dk_odds,
        "scored_line":       None,
        "player_id":         player_id,
        "pitcher_throw_hand": None,
        "kelly_fraction":    kelly_frac,
        "recommended_bet":   rec_bet,
        "bankroll_at_pick":  bankroll,
        "injury_flag":       None,
        "injury_detail":     None,
        "signal_type":       signal_type,
        "confidence_tier":   _confidence_tier(edge),
        "game_time":         commence_time,
        "dk_bet_link":       None,
    }


def _latest_golf_odds(conn: DBConnection, game_id: str) -> dict:
    """Latest DK snapshot per (market, dg_id) for a tournament.
    Returns {(market, dg_id): {price, datagolf_prob, opp_dg_id, opp_price}}."""
    rows = conn.execute("""
        SELECT DISTINCT ON (market, dg_id)
               market, dg_id, price, datagolf_prob, opp_dg_id, opp_player_name, opp_price
        FROM golf_odds
        WHERE game_id = %s AND bookmaker = 'draftkings'
        ORDER BY market, dg_id, snapshot_at DESC
    """, (game_id,)).fetchall()
    out = {}
    for market, dg_id, price, dg_prob, opp_dg_id, opp_name, opp_price in rows:
        out[(market, int(dg_id))] = {
            "price": float(price) if price is not None else None,
            "datagolf_prob": float(dg_prob) if dg_prob is not None else None,
            "opp_dg_id": int(opp_dg_id) if opp_dg_id is not None else None,
            "opp_player_name": opp_name,
            "opp_price": float(opp_price) if opp_price is not None else None,
        }
    return out


def run_golf_scorer(target_date: str = None, dry_run: bool = False) -> dict:
    """
    Score golf markets (outright win, top-10, top-20, make-cut, matchups) for any
    tournament starting within GOLF_SCORE_AHEAD_DAYS. Picks price against real DK
    odds sourced from DataGolf (golf_odds). Win probabilities are renormalized
    across the field before pricing. Idempotent: deletes unsettled golf picks for
    in-window tournaments each run (UFC look-ahead flip-handling).
    """
    from features.golf_feature_engine import (
        build_golf_scoring_features, renormalize_field_probs, matchup_diff_features,
    )
    from features.feature_engine import GOLF_MATCHUP_FEATURES

    if target_date is None:
        target_date = date.today().isoformat()
    horizon = (date.fromisoformat(target_date) + timedelta(days=GOLF_SCORE_AHEAD_DAYS)).isoformat()

    logger.info(f"Golf Scorer — {target_date} (horizon {horizon})")
    conn = get_connection()
    bankroll = _get_current_bankroll(conn)
    total_picks = total_bets = 0

    try:
        tourns = conn.execute("""
            SELECT t.game_id, t.dg_event_id, t.season, t.start_date, t.has_cut,
                   t.event_name, g.commence_time
            FROM golf_tournaments t
            JOIN games g ON g.game_id = t.game_id
            WHERE COALESCE(t.status,'') <> 'completed'
              AND t.start_date >= %s AND t.start_date <= %s
            ORDER BY t.start_date
        """, (target_date, horizon)).fetchall()

        if not tourns:
            logger.info("Golf: no tournaments in scoring window")
            return {"target_date": target_date, "total_picks": 0, "bets": 0}

        # Load the per-player and matchup models once.
        artifacts = {mid: load_model(mid) for mid in
                     list(_GOLF_OUTRIGHT_CONFIG) + ["golf_matchup"]}

        for (game_id, dg_event_id, season, start_date, has_cut,
             event_name, commence_time) in tourns:
            # First-cross lock (config.LOCK_GAME_PICKS_AT_FIRST_RUN). Golf is
            # scored up to a week before the tournament, and this used to delete
            # and re-score the whole field on every pass — so a player who
            # crossed on Monday silently disappeared when his price moved on
            # Wednesday. The first cross is the bet of record; later passes may
            # only ADD players/markets that have not fired yet.
            locked_golf: set[tuple] = set()
            if not dry_run:
                if LOCK_GAME_PICKS_AT_FIRST_RUN:
                    for mid, pid in conn.execute("""
                        SELECT model_id, player_id FROM picks
                        WHERE game_id = %s AND result IS NULL
                    """, (game_id,)).fetchall():
                        locked_golf.add((mid, pid))
                    if locked_golf:
                        logger.info(f"  {event_name}: {len(locked_golf)} pick(s) "
                                    f"already locked — preserving")
                else:
                    conn.execute(
                        "DELETE FROM picks WHERE game_id = %s AND result IS NULL",
                        (game_id,))

            odds = _latest_golf_odds(conn, game_id)
            if not odds:
                logger.info(f"  {event_name}: no DK odds yet")
                continue
            field_ids = sorted({dg_id for (_m, dg_id) in odds})
            feats = build_golf_scoring_features(conn, dg_event_id, season, start_date, field_ids)
            if not feats:
                logger.info(f"  {event_name}: no players cleared the history gate")
                continue

            picks = []

            # ── Per-player markets ────────────────────────────────────────────
            for model_id, cfg in _GOLF_OUTRIGHT_CONFIG.items():
                art = artifacts.get(model_id)
                if art is None:
                    continue
                if cfg["market"] == "make_cut" and not has_cut:
                    continue
                fcols = art["feature_cols"]
                scored = [d for d in field_ids if d in feats]
                if not scored:
                    continue
                X = np.array([[feats[d].get(c) for c in fcols] for d in scored], dtype=float)
                X = np.nan_to_num(X, nan=0.0)
                probs = art["model"].predict_proba(X)[:, 1]
                prob_by_id = {d: float(p) for d, p in zip(scored, probs)}
                if cfg["renorm"]:
                    prob_by_id = renormalize_field_probs(prob_by_id)

                for d in scored:
                    if (model_id, str(d)) in locked_golf:
                        continue          # already fired earlier this week
                    o = odds.get((cfg["market"], d))
                    if not o or o["price"] is None:
                        continue
                    p = prob_by_id[d]
                    if p is None:
                        continue
                    dk_ip = american_to_implied_prob(o["price"])
                    if not dk_ip:
                        continue
                    name = feats[d].get("player_name") or _golf_name(conn, d)
                    label = f"{name} {cfg['label']}"
                    pick = _make_golf_pick(
                        game_id=game_id, model_id=model_id, game_date=start_date,
                        player_name=name, model_prob=p, dk_implied_prob=dk_ip,
                        edge=p - dk_ip, dk_odds=o["price"], bankroll=bankroll,
                        label=label, player_id=str(d), commence_time=commence_time)
                    if pick:
                        picks.append(pick)

            # ── Matchups ──────────────────────────────────────────────────────
            art = artifacts.get("golf_matchup")
            if art is not None:
                for (market, p1), o in odds.items():
                    if market != "matchup_tournament":
                        continue
                    p2 = o.get("opp_dg_id")
                    if p2 is None or p1 not in feats or p2 not in feats:
                        continue
                    # Lock on the PAIR, not the player: the matchup fires for
                    # whichever side has the larger edge, so keying on one
                    # player alone could re-fire the same matchup on the other
                    # side later in the week — i.e. bet both sides of it.
                    if (("golf_matchup", str(p1)) in locked_golf
                            or ("golf_matchup", str(p2)) in locked_golf):
                        continue
                    if o["price"] is None or o.get("opp_price") is None:
                        continue
                    diff = matchup_diff_features(feats[p1], feats[p2])
                    X = np.nan_to_num(
                        np.array([[diff.get(c) for c in GOLF_MATCHUP_FEATURES]], dtype=float), nan=0.0)
                    prob_p1 = float(art["model"].predict_proba(X)[0, 1])
                    ip1 = american_to_implied_prob(o["price"])
                    ip2 = american_to_implied_prob(o["opp_price"])
                    if not ip1 or not ip2:
                        continue
                    edge1, edge2 = prob_p1 - ip1, (1 - prob_p1) - ip2
                    n1 = feats[p1].get("player_name") or _golf_name(conn, p1)
                    n2 = feats[p2].get("player_name") or _golf_name(conn, p2)
                    # Score the side with the larger edge.
                    if edge1 >= edge2:
                        pick = _make_golf_pick(
                            game_id=game_id, model_id="golf_matchup", game_date=start_date,
                            player_name=n1, model_prob=prob_p1, dk_implied_prob=ip1,
                            edge=edge1, dk_odds=o["price"], bankroll=bankroll,
                            label=f"{n1} over {n2} (matchup)", player_id=str(p1),
                            pick_side=str(p1), commence_time=commence_time)
                    else:
                        pick = _make_golf_pick(
                            game_id=game_id, model_id="golf_matchup", game_date=start_date,
                            player_name=n2, model_prob=1 - prob_p1, dk_implied_prob=ip2,
                            edge=edge2, dk_odds=o["opp_price"], bankroll=bankroll,
                            label=f"{n2} over {n1} (matchup)", player_id=str(p2),
                            pick_side=str(p2), commence_time=commence_time)
                    if pick:
                        picks.append(pick)

            bets = [p for p in picks if p["signal_type"] == "BET"]
            logger.info(f"  {event_name}: {len(bets)} BETs / {len(picks)} picks")
            if picks and not dry_run:
                _insert_picks(conn, picks)
            total_picks += len(picks)
            total_bets += len(bets)

        if not dry_run:
            conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error(f"Golf scorer failed: {exc}")
        raise
    finally:
        conn.close()

    logger.success(f"Golf scoring complete: {total_bets} BETs / {total_picks} picks")
    return {"target_date": target_date, "total_picks": total_picks,
            "bets": total_bets, "dry_run": dry_run}


def _golf_name(conn: DBConnection, dg_id: int) -> str:
    row = conn.execute(
        "SELECT player_name FROM golf_players WHERE dg_id = %s", (dg_id,)).fetchone()
    return row[0] if row else str(dg_id)


def run_prop_scorer(target_date: str = None, dry_run: bool = False) -> dict:
    """
    Score all pitcher prop markets then batter props.

    Pitcher flow (loops over _PITCHER_PROP_CONFIG):
      1. Fetch probable starters once (shared across all pitcher models)
      2. Delete existing unsettled pitcher prop picks for target_date
      3. For each model: build feature rows → load model → predict lambda
         → P(over/under) via Poisson CDF → edge vs DK implied → write picks

    Returns summary dict.
    """
    if target_date is None:
        target_date = date.today().isoformat()

    logger.info(f"\n{'─'*60}")
    logger.info(f"Prop Scorer — {target_date}")
    logger.info(f"{'─'*60}")

    conn = get_connection()
    bankroll = _get_current_bankroll(conn)
    ct_map = _commence_time_map(conn, target_date, "MLB")

    total_pitcher_picks = 0
    total_pitcher_bets  = 0

    try:
        # ── 1. Probable starters (shared across all pitcher prop models) ──────
        pitchers = _get_probable_pitchers(target_date, conn)
        if not pitchers:
            logger.info("No probable starters found — skipping pitcher prop scoring")
            conn.close()
            batter_result = run_batter_prop_scorer(target_date=target_date, dry_run=dry_run)
            return {
                "target_date":   target_date,
                "prop_picks":    0,
                "batter_picks":  batter_result["prop_picks"],
                "batter_bets":   batter_result["bets"],
            }

        # ── 2. First-signal prop lock + (locking-off) delete ──────────────────
        locked_prop_keys = _locked_prop_keys(conn, target_date, _PITCHER_PROP_CONFIG.keys())
        if not dry_run and not LOCK_PROP_PICKS_AT_FIRST_SIGNAL:
            for mid in _PITCHER_PROP_CONFIG:
                conn.execute("""
                    DELETE FROM picks
                    WHERE game_date = %s AND model_id = %s AND result IS NULL
                """, (target_date, mid))
            conn.commit()

        # ── 3. Score each pitcher prop model ──────────────────────────────────
        for model_id, cfg in _PITCHER_PROP_CONFIG.items():
            market     = cfg["market"]
            stat_label = cfg["stat_label"]

            artifact = load_model(model_id)
            if artifact is None:
                logger.debug(f"  No trained model for {model_id} — skipping")
                continue

            regressor    = artifact["model"]
            feature_cols = artifact["feature_cols"]

            df = build_pitcher_scoring_rows(model_id, target_date, pitchers)
            if df.empty:
                logger.info(f"  {model_id}: no scoring rows built")
                continue

            missing_cols = [c for c in feature_cols if c not in df.columns]
            for c in missing_cols:
                df[c] = np.nan

            X_raw = df[feature_cols].values.astype(float)
            X     = np.nan_to_num(X_raw, nan=0.0)

            had_nulls = np.isnan(X_raw).any(axis=1)
            if had_nulls.any():
                null_pitchers = df.loc[had_nulls, 'player_name'].tolist()
                logger.debug(f"  {model_id}: filled nulls for {null_pitchers}")

            lambdas = np.clip(regressor.predict(X), 1e-6, None)

            model_picks = []
            for i, row in df.iterrows():
                lam         = float(lambdas[i])
                player_name = row["player_name"]
                game_id     = row["game_id"]
                player_id   = row.get("player_id")
                if (game_id, model_id, player_id) in locked_prop_keys:
                    continue  # first-signal prop lock — already locked today
                if _game_started(ct_map.get(game_id)):
                    continue  # game underway — current DK prop prices are in-play

                prop_odds = _get_prop_dk_odds(conn, game_id, player_name, market)
                _best_ctx = (game_id, player_name, market)
                if prop_odds is None or prop_odds.get("line") is None:
                    logger.debug(f"    No DK odds for {player_name} {stat_label} — skipping")
                    continue

                line        = float(prop_odds["line"])
                over_price  = prop_odds.get("over_price")
                under_price = prop_odds.get("under_price")
                over_link   = prop_odds.get("over_link")
                under_link  = prop_odds.get("under_link")

                p_over  = _poisson_over_prob(lam, line)
                p_under = 1.0 - p_over

                logger.debug(
                    f"    {player_name}: lam={lam:.2f} line={line} "
                    f"P(over)={p_over:.3f} P(under)={p_under:.3f}"
                )

                if over_price is not None:
                    dk_ip_over = american_to_implied_prob(over_price)
                    if dk_ip_over:
                        pick = _make_prop_pick(
                            game_id=game_id, model_id=model_id,
                            game_date=target_date,
                            player_name=player_name, pick_side="over",
                            model_prob=p_over, dk_implied_prob=dk_ip_over,
                            edge=p_over - dk_ip_over,
                            dk_odds=over_price, line=line,
                            bankroll=bankroll, stat_label=stat_label,
                            player_id=player_id,
                            dk_bet_link=over_link,
                            commence_time=ct_map.get(game_id),
                        )
                        if pick:
                            model_picks.append(_tag_prop(pick, _best_ctx))

                if under_price is not None:
                    dk_ip_under = american_to_implied_prob(under_price)
                    if dk_ip_under:
                        pick = _make_prop_pick(
                            game_id=game_id, model_id=model_id,
                            game_date=target_date,
                            player_name=player_name, pick_side="under",
                            model_prob=p_under, dk_implied_prob=dk_ip_under,
                            edge=p_under - dk_ip_under,
                            dk_odds=under_price, line=line,
                            bankroll=bankroll, stat_label=stat_label,
                            player_id=player_id,
                            dk_bet_link=under_link,
                            commence_time=ct_map.get(game_id),
                        )
                        if pick:
                            model_picks.append(_tag_prop(pick, _best_ctx))

            bets = [p for p in model_picks if p["signal_type"] == "BET"]
            logger.info(
                f"  {model_id}: {len(bets)} BETs / {len(model_picks) - len(bets)} non-BET "
                f"({len(pitchers)} starters evaluated)"
            )

            if model_picks and not dry_run:
                _insert_picks(conn, model_picks)
                conn.commit()

            total_pitcher_picks += len(model_picks)
            total_pitcher_bets  += len(bets)

        logger.success(
            f"Pitcher prop scoring complete: {total_pitcher_bets} BETs / "
            f"{total_pitcher_picks} total picks ({len(pitchers)} starters)"
        )

        pitcher_result = {
            "target_date": target_date,
            "starters":    len(pitchers),
            "prop_picks":  total_pitcher_picks,
            "bets":        total_pitcher_bets,
            "dry_run":     dry_run,
        }

    except Exception as exc:
        conn.rollback()
        logger.error(f"Pitcher prop scorer failed: {exc}")
        raise
    finally:
        conn.close()

    # ── Batter props (hits, TB, HR) ───────────────────────────────────────────
    batter_result = run_batter_prop_scorer(target_date=target_date, dry_run=dry_run)

    return {
        **pitcher_result,
        "batter_picks": batter_result["prop_picks"],
        "batter_bets":  batter_result["bets"],
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run daily scorer")
    parser.add_argument("--date",    dest="target_date",
                        help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview picks without writing to DB")
    parser.add_argument("--props",   action="store_true",
                        help="Score prop markets (pitcher K) instead of game markets")
    args = parser.parse_args()

    if args.props:
        result = run_prop_scorer(target_date=args.target_date, dry_run=args.dry_run)
    else:
        result = run_scorer(target_date=args.target_date, dry_run=args.dry_run)
    logger.info(f"\nDone: {result}")
