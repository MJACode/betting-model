"""
live_scorer.py — Phase 4 of the live (in-play) betting build.

In-play counterpart to models/scorer.py. The pre-game scorer skips games whose
commence_time has passed; this module scores ONLY games that are currently in
progress (latest live_game_state snapshot is abstract_game_state='Live').

Per live game it runs the LIVE_MODELS registry, which for MLB is one model
since 2026-08-30 (mlb_live_win_prob and mlb_live_runline were retired — see
config.LIVE_MODELS):
    mlb_live_total_runs  vs the in-play DK total: the model predicts runs in
                         the REMAINDER, so P(over L) = P(rest > L − current)
                         via the Poisson CDF

Pick rows are written with is_live=true plus inning_at_pick and
score_diff_at_pick. Only BET/AVOID signals are written (no NONE rows — a live
game would otherwise generate hundreds of dead rows per day). Writes go through
the first-signal lock (config.LOCK_LIVE_PICKS_AT_FIRST_SIGNAL): a lane's first
live BET is the bet of record and is never re-priced or deleted; unlocked lanes
are delete-and-replaced each pass (the live analog of the signal-flip rule). Settlement flows
through the standard game-level path in paper_tracker (market resolved via
LIVE_MODELS); CLV capture skips live picks (an in-play price has no meaningful
"closing line" comparison).

Staleness guards: scoring is skipped when the newest game-state snapshot is
older than LIVE_STATE_MAX_AGE_SEC (poller died) or the newest in-play odds
snapshot is older than LIVE_ODDS_MAX_AGE_SEC (line has moved since).
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    LIVE_MODELS,
    LIVE_ODDS_MAX_AGE_SEC,
    LIVE_STATE_MAX_AGE_SEC,
    LIVE_MAX_EDGE_CAP,
    MODEL_EDGE_THRESHOLDS,
    LIVE_MAX_SIGNALS_PER_DAY,
    MODEL_MIN_EV,
    PAUSED_MODELS,
    MODEL_PROB_THRESHOLDS,
)
from data.db import get_connection, DBConnection
from features.live_game_features import build_live_state_row
from models.scorer import (
    _build_pick_label,
    _confidence_tier,
    _get_current_bankroll,
    _insert_picks,
    _locked_live_lanes,
    _link_for_side,
    _poisson_over_prob,
    american_to_implied_prob,
    quarter_kelly,
)
from models.trainer import load_model


# ── Helpers ───────────────────────────────────────────────────────────────────

def _age_seconds(iso_ts: Optional[str]) -> Optional[float]:
    """Seconds since an ISO timestamp (assumed UTC when naive). None on parse error."""
    if not iso_ts:
        return None
    try:
        ts = datetime.fromisoformat(str(iso_ts).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds()
    except Exception:
        return None


def _latest_live_state(conn: DBConnection, game_id: str) -> Optional[dict]:
    cols = ["inning", "inning_half", "outs", "bases_state",
            "home_score", "away_score", "abstract_game_state", "snapshot_at"]
    row = conn.execute(f"""
        SELECT {', '.join(cols)}
        FROM live_game_state
        WHERE game_id = %s
        ORDER BY snapshot_at DESC
        LIMIT 1
    """, (game_id,)).fetchone()
    return dict(zip(cols, row)) if row else None


def _get_live_dk_odds(conn: DBConnection, game_id: str,
                      market: str) -> Optional[dict]:
    """
    Latest in-play DK snapshot for a game+market, or None when absent/stale.
    Unlike the pre-game `_get_dk_odds`, this REQUIRES snapshot_type='in_play'
    and never falls back to sbr_consensus.
    """
    cols = ["home_price", "away_price", "spread_home", "total_line",
            "over_price", "under_price", "snapshot_at",
            "home_link", "away_link", "over_link", "under_link"]
    row = conn.execute(f"""
        SELECT {', '.join(cols)}
        FROM odds
        WHERE game_id = %s
          AND market = %s
          AND bookmaker = 'draftkings'
          AND snapshot_type = 'in_play'
        ORDER BY snapshot_at DESC
        LIMIT 1
    """, (game_id, market)).fetchone()
    if not row:
        return None
    odds = dict(zip(cols, row))
    age = _age_seconds(odds.get("snapshot_at"))
    if age is None or age > LIVE_ODDS_MAX_AGE_SEC:
        logger.debug(f"  {game_id}/{market}: in-play odds stale "
                     f"({age and int(age)}s old) — skipping")
        return None
    return odds


def expected_value(model_prob: float, dk_odds) -> Optional[float]:
    """EV per unit staked: model_prob x decimal_odds - 1.

    Edge (prob minus implied) ignores the PAYOUT, so two picks with equal edge
    are not equal bets -- at -200 you risk twice as much for the same return.
    None when there is no price to compute against; a floor then cannot apply,
    which is the honest outcome rather than assuming -110."""
    if dk_odds is None:
        return None
    try:
        a = float(dk_odds)
    except (TypeError, ValueError):
        return None
    if a == 0:
        return None
    decimal = 1.0 + (a / 100.0 if a > 0 else 100.0 / abs(a))
    return model_prob * decimal - 1.0


def classify_live_signal(model_id: str, model_prob: float,
                         edge: float, dk_odds=None) -> Optional[str]:
    """
    BET / AVOID / None for live picks. NONE-zone picks return None (not
    written) — pure so it can be unit-tested.
    """
    # The LIVE cap, not the pre-game one. A live price is at most ~45s old by
    # construction (The Odds API's in-play cache), so an implausible edge here
    # usually means our snapshot is behind the book rather than that we found
    # value. See config.LIVE_MAX_EDGE_CAP for why the two are separate.
    if abs(edge) > LIVE_MAX_EDGE_CAP:
        return None
    bet_thresh  = MODEL_EDGE_THRESHOLDS.get(model_id, 0.10)
    prob_thresh = MODEL_PROB_THRESHOLDS.get(model_id, 0.65)
    if edge >= bet_thresh and model_prob >= prob_thresh:
        # A PAUSED live model still scores, it just never produces an
        # actionable bet. Written as NONE (the pre-game convention) rather than
        # dropped, so the forward record keeps accruing for the unpause
        # decision -- with nothing written there would be nothing to
        # re-evaluate on. The "live picks are BET/AVOID only, no NONE rows"
        # rule exists to stop a live game writing hundreds of dead rows a day;
        # a paused model's would-be BETs are ~1-2 a day, so it does not apply.
        # Every actionable surface (Live tab, Discord, the record views) filters
        # signal_type='BET', so a NONE row surfaces nowhere.
        if model_id in PAUSED_MODELS:
            return "NONE"
        # EV floor. Applied AFTER prob/edge so it only ever tightens, and only
        # when a price exists -- a prob-only pick has no EV and is judged on the
        # thresholds alone.
        floor = MODEL_MIN_EV.get(model_id)
        if floor is not None:
            ev = expected_value(model_prob, dk_odds)
            if ev is not None and ev < floor:
                return "NONE"
        return "BET"
    if edge <= -bet_thresh:
        return "AVOID"
    return None


def _make_live_pick(game_id: str, model_id: str, game_date: str,
                    pick_side: str, pick_label: str,
                    model_prob: float, dk_odds: float,
                    scored_line: Optional[float],
                    bankroll: float, state: dict,
                    commence_time: Optional[str],
                    dk_bet_link: Optional[str]) -> Optional[dict]:
    """Build a live pick dict, or None when the signal is in the dead zone."""
    implied = american_to_implied_prob(dk_odds)
    if implied is None:
        return None
    edge = model_prob - implied

    signal = classify_live_signal(model_id, model_prob, edge, dk_odds)
    if signal is None:
        return None

    kelly_frac, rec_bet = (quarter_kelly(model_prob, implied, bankroll)
                           if signal == "BET" else (0.0, 0.0))

    score_diff = None
    if state.get("home_score") is not None and state.get("away_score") is not None:
        score_diff = int(state["home_score"]) - int(state["away_score"])

    return {
        "game_id":            game_id,
        "model_id":           model_id,
        "sport":              LIVE_MODELS[model_id][0],
        "game_date":          game_date,
        "pick_side":          pick_side,
        "pick_label":         pick_label,
        "model_probability":  round(model_prob, 4),
        "dk_implied_prob":    round(implied, 4),
        "edge":               round(edge, 4),
        "dk_odds":            dk_odds,
        "scored_line":        scored_line,
        "kelly_fraction":     kelly_frac,
        "recommended_bet":    rec_bet,
        "bankroll_at_pick":   bankroll,
        "injury_flag":        None,
        "injury_detail":      None,
        "signal_type":        signal,
        "confidence_tier":    _confidence_tier(edge),
        "game_time":          commence_time,
        "dk_bet_link":        dk_bet_link,
        "is_live":            True,
        "inning_at_pick":     state.get("inning"),
        "score_diff_at_pick": score_diff,
    }


# ── Per-model scoring ─────────────────────────────────────────────────────────

def _score_live_model(conn: DBConnection, model_id: str, artifact: dict,
                      game: dict, state: dict, pregame: dict,
                      bankroll: float) -> list[dict]:
    """Score one live model for one in-progress game. Returns 0..2 pick dicts."""
    sport, market, model_type, _ = LIVE_MODELS[model_id]
    game_id   = game["game_id"]
    home_team = game["home_team"]
    away_team = game["away_team"]

    odds = _get_live_dk_odds(conn, game_id, market)
    if not odds:
        return []

    row = build_live_state_row(state, pregame, model_id)
    if row is None:
        return []

    feat_cols = artifact["feature_cols"]
    x = np.array([[np.nan if row.get(c) is None else float(row[c])
                   for c in feat_cols]], dtype=float)

    clf = artifact["model"]
    picks: list[dict] = []
    label_suffix = " (live)"

    if model_type == "binary":
        try:
            p_home = float(clf.predict_proba(x)[0][1])
        except Exception as exc:
            logger.error(f"  {game_id}/{model_id}: prediction error: {exc}")
            return []

        if market == "spreads":
            # The model's fixed target is "home wins by 2+" — only meaningful
            # against a live home −1.5 line. DK in-play run lines move; skip
            # any other number rather than score the wrong proposition.
            if odds.get("spread_home") is None or float(odds["spread_home"]) != -1.5:
                return []

        for side, prob, price in [("home", p_home, odds.get("home_price")),
                                  ("away", 1.0 - p_home, odds.get("away_price"))]:
            if price is None:
                continue
            label = _build_pick_label(side, home_team, away_team, market,
                                      odds.get("spread_home")) + label_suffix
            pick = _make_live_pick(
                game_id, model_id, game["game_date"], side, label,
                prob, price, odds.get("spread_home"), bankroll, state,
                game.get("commence_time"), _link_for_side(odds, side))
            if pick:
                picks.append(pick)

    else:  # poisson — expected runs in the remainder of the game
        line = odds.get("total_line")
        if line is None:
            return []
        try:
            lam = float(np.clip(clf.predict(x)[0], 1e-6, None))
        except Exception as exc:
            logger.error(f"  {game_id}/{model_id}: prediction error: {exc}")
            return []

        current_total = row["total_runs"]
        rest_line = float(line) - current_total
        if rest_line < 0:
            # Over already clinched — no bettable proposition.
            return []
        p_over = _poisson_over_prob(lam, rest_line)

        for side, prob, price in [("over", p_over, odds.get("over_price")),
                                  ("under", 1.0 - p_over, odds.get("under_price"))]:
            if price is None:
                continue
            label = _build_pick_label(side, home_team, away_team, market,
                                      line) + label_suffix
            pick = _make_live_pick(
                game_id, model_id, game["game_date"], side, label,
                prob, price, line, bankroll, state,
                game.get("commence_time"), _link_for_side(odds, side))
            if pick:
                picks.append(pick)

    return picks


# ── Entry point ───────────────────────────────────────────────────────────────

# Pre-game context, cached for the life of the process.
#
# build_mlb_game_features runs ~10 per-game queries, and at the 5s cadence that
# is 12 games x 10 queries every pass -- for a row that CANNOT change during the
# game. Every input is as-of first pitch: season team stats, the starters,
# weather, and the pre-game DK line (_get_dk_odds excludes in_play, so it stops
# moving at first pitch by construction). Only the STATE changes pitch to pitch,
# and that is read fresh every pass.
#
# Keyed by date as well as game so a long-running process cannot serve one
# night's context to the next; entries for other dates are dropped on sight.
_PREGAME_CACHE: dict[tuple[str, str], dict] = {}


def _pregame_features(conn: DBConnection, game: dict, build, get_dk_odds):
    key = (game["game_date"], game["game_id"])
    hit = _PREGAME_CACHE.get(key)
    if hit is not None:
        return hit
    for stale in [k for k in _PREGAME_CACHE if k[0] != game["game_date"]]:
        _PREGAME_CACHE.pop(stale, None)
    row = build(conn, game["game_id"], game["game_date"],
                game["home_team"], game["away_team"], game["season"],
                odds_row=get_dk_odds(conn, game["game_id"], "h2h"))
    if row:
        _PREGAME_CACHE[key] = row
    return row


def _lane_signature(picks: list[dict]) -> tuple:
    """What a lane's rows currently ARE: side, signal, line and price per row.

    Deliberately NOT model_probability: it drifts fractionally on every pitch
    while the bet on offer is unchanged, and rewriting a row for that is churn
    with no reader. Rounded because a float round-trip through NUMERIC must not
    read as a change."""
    return tuple(sorted(
        (p["pick_side"], p["signal_type"],
         None if p.get("scored_line") is None else round(float(p["scored_line"]), 2),
         None if p.get("dk_odds") is None else round(float(p["dk_odds"]), 2))
        for p in picks))


def _existing_live_lanes(conn: DBConnection, game_id: str) -> dict[str, tuple]:
    """Signature of the unsettled live rows already stored, per model."""
    rows = conn.execute("""
        SELECT model_id, pick_side, signal_type, scored_line, dk_odds
        FROM picks
        WHERE game_id = %s AND result IS NULL AND is_live = TRUE
    """, (game_id,)).fetchall()
    by_model: dict[str, list[dict]] = {}
    for model_id, side, signal, line, odds in rows:
        by_model.setdefault(model_id, []).append({
            "pick_side": side, "signal_type": signal,
            "scored_line": line, "dk_odds": odds})
    return {m: _lane_signature(v) for m, v in by_model.items()}


def _live_bets_today(conn: DBConnection, game_date: str) -> dict[str, int]:
    """Live BETs already standing today, per model — the daily cap's counter.

    Counts across every game, because the cap is "N live signals a day from this
    model", not per game. Unsettled and settled both count: a bet placed at 2pm
    is still one of the day's signals at 9pm."""
    rows = conn.execute("""
        SELECT model_id, count(DISTINCT game_id)
        FROM picks
        WHERE game_date = %s AND is_live = TRUE AND signal_type = 'BET'
        GROUP BY model_id
    """, (game_date,)).fetchall()
    return {r[0]: int(r[1]) for r in rows}


def apply_daily_cap(picks: list[dict], counts: dict[str, int],
                    caps: dict[str, int]) -> list[dict]:
    """Downgrade a BET to NONE once its model has used up the day's allowance.

    A THRESHOLD is a hope about volume — it depends on where the model's
    distribution happens to sit that night, which is how a cut measured at ~1
    signal a day produced six on a heavy slate. A cap is a guarantee. Taken in
    the order signals cross, so it composes with the first-signal lock rather
    than fighting it: the first qualifying bet of the day is the one that
    stands, and it is already locked by the time the cap turns the rest away.

    Mutates nothing — returns a new list. NONE rows still get written, so the
    turned-away signals remain visible for the next sweep."""
    if not caps:
        return picks
    used = dict(counts)
    out = []
    for p in picks:
        m = p["model_id"]
        cap = caps.get(m)
        if p.get("signal_type") == "BET" and cap is not None:
            if used.get(m, 0) >= cap:
                p = {**p, "signal_type": "NONE", "kelly_fraction": 0.0,
                     "recommended_bet": 0.0}
            else:
                used[m] = used.get(m, 0) + 1
        out.append(p)
    return out


def _write_live_picks(conn: DBConnection, game_id: str,
                      game_picks: list[dict]) -> list[dict]:
    """Write one game's fresh live picks under the first-signal lock
    (config.LOCK_LIVE_PICKS_AT_FIRST_SIGNAL).

    A lane (model_id) with an unsettled live BET is LOCKED: its rows are never
    deleted and no new rows are written for it — the first BET is the bet of
    record at its line and price. Unlocked lanes keep the delete-and-replace
    churn (the live analog of the pre-game signal-flip rule). Returns the picks
    actually written."""
    locked = _locked_live_lanes(conn, game_id, LIVE_MODELS.keys())
    kept = [p for p in game_picks if p["model_id"] not in locked]

    # Rewrite a lane only when the PROPOSITION changed.
    #
    # Unlocked lanes are delete-and-replaced, which was fine at a 60s cadence
    # and is not at 5s: 12 live games x 3 models x 2 sides rewritten every pass
    # is ~52k picks rows an hour and twice that in picks_log (the audit trigger
    # fires on both the delete and the insert). Almost all of it is identical
    # rows. Comparing side/signal/line/price -- the fields that define what the
    # bet IS and what it costs -- makes the write proportional to actual line
    # movement instead of to poll frequency, which is what we actually wanted
    # from a faster loop.
    existing = _existing_live_lanes(conn, game_id)
    changed = {m for m in LIVE_MODELS if m not in locked
               and existing.get(m) != _lane_signature(
                   [p for p in kept if p["model_id"] == m])}
    kept = [p for p in kept if p["model_id"] in changed]
    for model_id in LIVE_MODELS:
        if model_id in locked or model_id not in changed:
            continue
        conn.execute("""
            DELETE FROM picks
            WHERE game_id = %s AND result IS NULL AND is_live = TRUE
              AND model_id = %s
        """, (game_id, model_id))
    if kept:
        _insert_picks(conn, kept)
    if len(kept) < len(game_picks):
        logger.info(f"  {game_id}: {len(game_picks) - len(kept)} live pick(s) "
                    f"skipped — lane locked at first BET signal "
                    f"({', '.join(sorted(locked))})")
    return kept


def run_live_scorer(target_date: Optional[str] = None,
                    game_ids: Optional[set[str]] = None,
                    dry_run: bool = False) -> dict:
    """
    Score every in-progress game (or just `game_ids`) with all live models.
    Safe to call repeatedly — each pass replaces the game's unsettled live picks.
    """
    if target_date is None:
        target_date = date.today().isoformat()

    conn = get_connection()
    summary = {"target_date": target_date, "games_scored": 0,
               "picks": 0, "bets": 0, "avoids": 0}
    try:
        artifacts = {}
        for model_id, spec in LIVE_MODELS.items():
            # 'engine' models are not platform artifacts. The NCAAF live pair is
            # served by ncaaf_live/ from its own LightGBM boosters, and this
            # scorer only prices MLB anyway (see the sport filter below) -- so
            # asking the registry for them logged "No active model found" on
            # every pass, for models nothing here was going to use. Harmless,
            # but this is exactly the shape of noise that hid a real five-day
            # outage today, so it does not get to keep crying wolf.
            if spec[2] == "engine":
                continue
            art = load_model(model_id)
            if art:
                artifacts[model_id] = art
        if not artifacts:
            logger.warning("Live scorer: no trained live models registered — "
                           "run `python -m models.trainer --all-live` first")
            return summary

        bankroll = _get_current_bankroll(conn)

        now_utc = datetime.now(timezone.utc).isoformat()
        rows = conn.execute("""
            SELECT game_id, game_date, season, home_team, away_team, commence_time
            FROM games
            WHERE sport = 'MLB'
              AND game_date = %s
              AND home_score IS NULL
              AND commence_time IS NOT NULL
              AND commence_time <= %s
        """, (target_date, now_utc)).fetchall()
        games = [dict(zip(["game_id", "game_date", "season", "home_team",
                           "away_team", "commence_time"], r)) for r in rows]
        if game_ids is not None:
            games = [g for g in games if g["game_id"] in game_ids]

        if not games:
            logger.info(f"Live scorer: no started games for {target_date}")
            return summary

        from features.feature_engine import build_mlb_game_features
        from models.scorer import _get_dk_odds

        # Counted once per pass, then incremented in-pass: a later game on the
        # same pass must see the signals the earlier ones just produced.
        bets_today = _live_bets_today(conn, target_date)

        all_picks: list[dict] = []
        for game in games:
            state = _latest_live_state(conn, game["game_id"])
            if not state or state.get("abstract_game_state") != "Live":
                continue
            age = _age_seconds(state.get("snapshot_at"))
            if age is None or age > LIVE_STATE_MAX_AGE_SEC:
                logger.debug(f"  {game['game_id']}: state snapshot stale — skipping")
                continue

            pregame = _pregame_features(conn, game, build_mlb_game_features,
                                        _get_dk_odds)
            if not pregame:
                continue

            game_picks: list[dict] = []
            for model_id, artifact in artifacts.items():
                game_picks.extend(_score_live_model(
                    conn, model_id, artifact, game, state, pregame, bankroll))
            game_picks = apply_daily_cap(game_picks, bets_today,
                                         LIVE_MAX_SIGNALS_PER_DAY)
            for p in game_picks:
                if p.get("signal_type") == "BET":
                    bets_today[p["model_id"]] = bets_today.get(
                        p["model_id"], 0) + 1

            if not dry_run:
                # First-signal live lock: locked lanes keep their bet of record;
                # unlocked lanes are delete-and-replaced with the fresh set.
                game_picks = _write_live_picks(conn, game["game_id"], game_picks)
            summary["games_scored"] += 1

            for p in game_picks:
                logger.info(
                    f"  [LIVE {p['signal_type']}] {p['pick_label']} | "
                    f"inning {p['inning_at_pick']} | DK={p['dk_odds']:+.0f} | "
                    f"model={p['model_probability']:.3f} | "
                    f"edge={p['edge']*100:+.1f}% | bet=${p['recommended_bet']:.0f}")
            all_picks.extend(game_picks)

        if not dry_run:
            conn.commit()

        summary["picks"]  = len(all_picks)
        summary["bets"]   = sum(1 for p in all_picks if p["signal_type"] == "BET")
        summary["avoids"] = sum(1 for p in all_picks if p["signal_type"] == "AVOID")
        logger.success(f"Live scorer: {summary['games_scored']} game(s), "
                       f"{summary['bets']} BET / {summary['avoids']} AVOID")

        # Push new in-play BET signals (deduped per game:model:side). Never let a
        # push failure break the live loop. Lazy import avoids a startup cycle.
        if not dry_run and summary["bets"]:
            try:
                from tracking.push_notifier import notify_live_signals
                notify_live_signals(target_date=target_date, dry_run=False)
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Live signal push failed (non-fatal): {exc}")
            # Separate channel, separate try: a broken Discord webhook must not
            # suppress the mobile push, or vice versa.
            try:
                from tracking.discord_notifier import notify_discord_live
                notify_discord_live(target_date=target_date, dry_run=False)
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Live signal Discord post failed (non-fatal): {exc}")

        return summary
    finally:
        conn.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Score in-progress games with live models")
    parser.add_argument("--date",    default=None, help="Date to score (YYYY-MM-DD)")
    parser.add_argument("--game-id", default=None, help="Restrict to one game_id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ids = {args.game_id} if args.game_id else None
    run_live_scorer(target_date=args.date, game_ids=ids, dry_run=args.dry_run)
