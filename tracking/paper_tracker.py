"""
paper_tracker.py — Morning result settler for paper trading picks.

Runs each morning after games complete to:
  1. Find picks from the previous day that have no result yet
  2. Look up final scores from the games table
  3. Compute WIN / LOSS / PUSH for each pick
  4. Update profit_flat, profit_kelly, result, settled_at in the picks table
  5. Log performance summary

Usage:
    python -m tracking.paper_tracker              # settle yesterday's picks
    python -m tracking.paper_tracker --date 2025-04-15
    python -m tracking.paper_tracker --summary    # print running P&L
"""

import argparse
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import sys

import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MODELS
from data.db import get_connection, DBConnection
from models.scorer import american_to_decimal, american_to_implied_prob

try:
    import statsapi
    STATSAPI_AVAILABLE = True
except ImportError:
    STATSAPI_AVAILABLE = False

# MLB Stats API team ID → our abbreviation (same map as mlb_stats_ingestor)
_STATSAPI_TEAM_IDS = {
    109: "ARI", 144: "ATL", 110: "BAL", 111: "BOS", 112: "CHC",
    145: "CWS", 113: "CIN", 114: "CLE", 115: "COL", 116: "DET",
    117: "HOU", 118: "KC",  108: "LAA", 119: "LAD", 146: "MIA",
    158: "MIL", 142: "MIN", 121: "NYM", 147: "NYY", 133: "OAK",
    143: "PHI", 134: "PIT", 135: "SD",  136: "SEA", 137: "SF",
    138: "STL", 139: "TB",  140: "TEX", 141: "TOR", 120: "WSH",
}


def _fetch_and_store_scores(conn: DBConnection, game_date: str) -> int:
    """
    Pull final scores from MLB Stats API for game_date and write them into
    the games table.  Only updates rows where home_score is still NULL.
    Returns the number of rows updated.
    """
    if not STATSAPI_AVAILABLE:
        logger.warning("statsapi not available — cannot fetch scores for settlement")
        return 0

    try:
        schedule = statsapi.schedule(date=game_date, sportId=1)
    except Exception as exc:
        logger.error(f"statsapi.schedule({game_date}) failed: {exc}")
        return 0

    updated = 0
    for game in schedule:
        status = game.get("status", "")
        if status not in ("Final", "Game Over", "Completed Early"):
            continue

        home_id   = game.get("home_id")
        away_id   = game.get("away_id")
        home_abbr = _STATSAPI_TEAM_IDS.get(home_id)
        away_abbr = _STATSAPI_TEAM_IDS.get(away_id)
        if not home_abbr or not away_abbr:
            continue

        home_score = game.get("home_score")
        away_score = game.get("away_score")
        if home_score is None or away_score is None:
            continue

        home_score = int(home_score)
        away_score = int(away_score)
        home_win   = 1 if home_score > away_score else 0

        conn.execute("""
            UPDATE games
            SET home_score = %s,
                away_score = %s,
                home_win   = %s,
                updated_at = NOW()::TEXT
            WHERE sport     = 'MLB'
              AND game_date = %s
              AND home_team = %s
              AND away_team = %s
              AND home_score IS NULL
        """, (home_score, away_score, home_win,
              game_date, home_abbr, away_abbr))

        updated += 1

    if updated:
        logger.info(f"Scores fetched: {updated} MLB games updated for {game_date}")
    else:
        logger.debug(f"No new scores written for {game_date} (already populated or no finals)")

    # Fetch F5 (first 5 innings) scores via linescore API for games missing them
    f5_updated = _fetch_and_store_f5_scores(conn, game_date)
    if f5_updated:
        logger.info(f"F5 scores fetched: {f5_updated} games updated for {game_date}")

    return updated + f5_updated


def _fetch_and_store_f5_scores(conn: DBConnection, game_date: str) -> int:
    """
    Fetch inning-by-inning linescore from MLB Stats API and populate
    home_score_f5/away_score_f5 for games that are missing them.
    """
    # Only update games that have final scores but no F5 scores
    games = conn.execute("""
        SELECT game_id, home_team, away_team
        FROM games
        WHERE sport = 'MLB'
          AND game_date = %s
          AND home_score IS NOT NULL
          AND home_score_f5 IS NULL
    """, (game_date,)).fetchall()

    if not games:
        return 0

    try:
        url = (
            f"https://statsapi.mlb.com/api/v1/schedule"
            f"?sportId=1&date={game_date}&hydrate=linescore"
        )
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning(f"F5 linescore fetch failed for {game_date}: {exc}")
        return 0

    api_games = []
    for d in data.get("dates", []):
        api_games.extend(d.get("games", []))

    updated = 0
    for api_game in api_games:
        home_id = api_game.get("teams", {}).get("home", {}).get("team", {}).get("id")
        away_id = api_game.get("teams", {}).get("away", {}).get("team", {}).get("id")
        home_abbrev = _STATSAPI_TEAM_IDS.get(home_id, "")
        away_abbrev = _STATSAPI_TEAM_IDS.get(away_id, "")

        if not home_abbrev or not away_abbrev:
            continue

        linescore = api_game.get("linescore", {})
        innings = linescore.get("innings", [])

        if len(innings) < 5:
            continue

        home_f5 = 0
        away_f5 = 0
        valid = True
        for inn in innings[:5]:
            h_runs = inn.get("home", {}).get("runs")
            a_runs = inn.get("away", {}).get("runs")
            if h_runs is None or a_runs is None:
                valid = False
                break
            home_f5 += h_runs
            away_f5 += a_runs

        if not valid:
            continue

        game_id = f"MLB_{game_date}_{away_abbrev}_{home_abbrev}"
        conn.execute("""
            UPDATE games
            SET home_score_f5 = %s, away_score_f5 = %s
            WHERE game_id = %s AND home_score_f5 IS NULL
        """, (home_f5, away_f5, game_id))
        updated += 1

    return updated


# ── Prop Settlement Helpers ───────────────────────────────────────────────────

# Maps model_id → (player_type, stat_col)
# stat_col is a column in player_game_log, or 'COMPUTE_OUTS' for the special
# innings_pitched → outs conversion needed for mlb_prop_pitcher_outs.
_PROP_STAT_MAP: dict[str, tuple[str, str]] = {
    "mlb_prop_pitcher_k":           ("pitcher", "p_strikeouts"),
    "mlb_prop_pitcher_hits":        ("pitcher", "p_hits_allowed"),
    "mlb_prop_pitcher_er":          ("pitcher", "p_earned_runs"),
    "mlb_prop_pitcher_outs":        ("pitcher", "COMPUTE_OUTS"),
    "mlb_prop_pitcher_walks":       ("pitcher", "p_walks"),
    "mlb_prop_batter_hits":         ("batter",  "hits"),
    "mlb_prop_batter_tb":           ("batter",  "total_bases"),
    "mlb_prop_batter_hr":           ("batter",  "home_runs"),
    "mlb_prop_batter_rbi":          ("batter",  "rbi"),
    "mlb_prop_batter_runs":         ("batter",  "runs"),
    "mlb_prop_batter_sb":           ("batter",  "stolen_bases"),
    "mlb_prop_batter_walks":        ("batter",  "walks"),
    # WNBA props — resolved from wnba_player_game_log
    "wnba_prop_player_points":      ("wnba_player", "points"),
    "wnba_prop_player_rebounds":    ("wnba_player", "rebounds"),
    "wnba_prop_player_assists":     ("wnba_player", "assists"),
    "wnba_prop_player_threes":      ("wnba_player", "fg3_made"),
    "wnba_prop_player_pra":         ("wnba_player", "COMPUTE_PRA"),
}

# Extracts player name from pick_label like "Blake Snell Over 5.5 Ks"
_PICK_LABEL_RE = re.compile(r'^(.+?)\s+(?:Over|Under)\s+', re.IGNORECASE)


def _ip_to_outs(ip: float | None) -> int | None:
    """Convert baseball innings_pitched notation to integer outs.

    5.2 means 5 full innings + 2 outs (2/3 of an inning), so 5*3 + 2 = 17 outs.
    """
    if ip is None:
        return None
    whole = int(ip)
    thirds = round((ip % 1) * 10)
    return whole * 3 + thirds


def _load_prop_actuals(conn: DBConnection, game_date: str) -> tuple[dict, dict, dict]:
    """
    Bulk-load player_game_log rows for game_date.

    Returns:
        pitcher_by_id:   {(player_id,   game_id): row_dict}   ← primary pitcher lookup
        pitcher_by_name: {(player_name, game_id): row_dict}   ← fallback for legacy picks
        batter_actuals:  {(player_id,   game_id): row_dict}
    """
    rows = conn.execute("""
        SELECT player_id, player_name, game_id, player_type,
               innings_pitched,
               p_strikeouts, p_walks, p_hits_allowed, p_earned_runs,
               hits, total_bases, home_runs, rbi, runs, stolen_bases, walks
        FROM player_game_log
        WHERE game_date = %s
    """, (game_date,)).fetchall()

    _cols = [
        "player_id", "player_name", "game_id", "player_type",
        "innings_pitched",
        "p_strikeouts", "p_walks", "p_hits_allowed", "p_earned_runs",
        "hits", "total_bases", "home_runs", "rbi", "runs", "stolen_bases", "walks",
    ]

    pitcher_by_id:   dict = {}
    pitcher_by_name: dict = {}
    batter_actuals:  dict = {}

    for row in rows:
        d = dict(zip(_cols, row))
        if d["player_type"] == "pitcher":
            pitcher_by_id[(d["player_id"], d["game_id"])]   = d
            pitcher_by_name[(d["player_name"], d["game_id"])] = d
        else:
            batter_actuals[(d["player_id"], d["game_id"])] = d

    logger.debug(
        f"Prop actuals: {len(pitcher_by_id)} pitcher rows, "
        f"{len(batter_actuals)} batter rows for {game_date}"
    )
    return pitcher_by_id, pitcher_by_name, batter_actuals


def _load_wnba_prop_actuals(conn: DBConnection, game_date: str) -> dict:
    """
    Bulk-load wnba_player_game_log rows for game_date.

    Returns:
        wnba_actuals: {(player_id, game_id): row_dict}
    """
    rows = conn.execute("""
        SELECT player_id, player_name, game_id,
               points, rebounds, assists, fg3_made
        FROM wnba_player_game_log
        WHERE game_date = %s
    """, (game_date,)).fetchall()

    _cols = ["player_id", "player_name", "game_id", "points", "rebounds", "assists", "fg3_made"]
    wnba_actuals: dict = {}

    for row in rows:
        d = dict(zip(_cols, row))
        wnba_actuals[(d["player_id"], d["game_id"])] = d

    logger.debug(
        f"WNBA prop actuals: {len(wnba_actuals)} player rows for {game_date}"
    )
    return wnba_actuals


# Prop game logs can land after the morning settle (WNBA box scores are
# ingested on Matt's machine, which may run after the Actions settle), and
# settle_picks only runs for game_date = yesterday — a trailing window lets
# late-arriving logs settle on subsequent mornings instead of lingering
# unsettled forever. Mirrors _UFC_SETTLE_WINDOW_DAYS.
_PROP_SETTLE_WINDOW_DAYS = 14


def _settle_prop_picks_window(
    conn: DBConnection,
    game_date: str,
    settled_at: str,
) -> tuple[int, int, int, int, float, float]:
    """
    Settle unsettled BET prop picks for game_date and the trailing window
    before it. Per-date loops reuse _settle_prop_picks unchanged; dates with
    no unsettled prop picks return immediately.
    """
    totals = [0, 0, 0, 0, 0.0, 0.0]
    end = datetime.strptime(game_date, "%Y-%m-%d")
    for offset in range(_PROP_SETTLE_WINDOW_DAYS):
        d = (end - timedelta(days=offset)).strftime("%Y-%m-%d")
        day_results = _settle_prop_picks(conn, d, settled_at)
        for i, v in enumerate(day_results):
            totals[i] += v
    return tuple(totals)


def _settle_prop_picks(
    conn: DBConnection,
    game_date: str,
    settled_at: str,
) -> tuple[int, int, int, int, float, float]:
    """
    Settle all unsettled BET prop picks for game_date where the game is final.

    Returns (wins, losses, pushes, no_actions, total_flat, total_kelly).
    """
    prop_picks = conn.execute("""
        SELECT p.pick_id, p.game_id, p.model_id, p.pick_side,
               p.dk_odds, p.recommended_bet, p.scored_line,
               p.player_id, p.pick_label
        FROM picks p
        JOIN games g ON p.game_id = g.game_id
        WHERE p.game_date = %s
          AND p.result IS NULL
          AND p.signal_type = 'BET'
          AND (p.model_id LIKE 'mlb_prop_%%' OR p.model_id LIKE 'wnba_prop_%%')
          AND g.home_score IS NOT NULL
    """, (game_date,)).fetchall()

    if not prop_picks:
        return 0, 0, 0, 0, 0.0, 0.0

    logger.info(f"Found {len(prop_picks)} unsettled prop picks for {game_date}")

    pitcher_by_id, pitcher_by_name, batter_actuals = _load_prop_actuals(conn, game_date)
    wnba_actuals = _load_wnba_prop_actuals(conn, game_date)

    wins = losses = pushes = no_actions = 0
    total_flat = total_kelly = 0.0

    for row in prop_picks:
        (pick_id, game_id, model_id, pick_side,
         dk_odds, rec_bet, scored_line, player_id, pick_label) = row

        mapping = _PROP_STAT_MAP.get(model_id)
        if mapping is None:
            logger.warning(f"No stat mapping for {model_id}, skipping pick {pick_id}")
            no_actions += 1
            continue

        player_type, stat_col = mapping

        # ── Look up actual stat ───────────────────────────────────────────
        actual_stat = None

        if player_type == "pitcher":
            # Primary: look up by player_id (stored in picks since scorer fix).
            # Fallback: parse player_name from pick_label for legacy picks written
            # before the scorer stored player_id for pitcher props.
            row_data = pitcher_by_id.get((player_id, game_id)) if player_id else None
            if row_data is None:
                m = _PICK_LABEL_RE.match(pick_label or "")
                parsed_name = m.group(1).strip() if m else None
                if parsed_name:
                    row_data = pitcher_by_name.get((parsed_name, game_id))
            if row_data:
                if stat_col == "COMPUTE_OUTS":
                    actual_stat = _ip_to_outs(row_data.get("innings_pitched"))
                else:
                    actual_stat = row_data.get(stat_col)

        elif player_type == "wnba_player":
            if player_id:
                row_data = wnba_actuals.get((player_id, game_id))
                if row_data:
                    if stat_col == "COMPUTE_PRA":
                        pts = row_data.get("points") or 0
                        reb = row_data.get("rebounds") or 0
                        ast = row_data.get("assists") or 0
                        actual_stat = pts + reb + ast
                    else:
                        actual_stat = row_data.get(stat_col)

        else:  # batter
            if player_id:
                row_data = batter_actuals.get((player_id, game_id))
                if row_data:
                    actual_stat = row_data.get(stat_col)

        if actual_stat is None or scored_line is None:
            logger.debug(
                f"  Cannot settle pick {pick_id} ({model_id}, {pick_label}): "
                f"actual={actual_stat}, line={scored_line}"
            )
            no_actions += 1
            continue

        # ── Compare actual vs line ────────────────────────────────────────
        profit_flat  = 0.0
        profit_kelly = 0.0

        if float(actual_stat) == float(scored_line):
            result = "PUSH"
            pushes += 1

        else:
            over_hit   = float(actual_stat) > float(scored_line)
            picked_over = (pick_side == "over")
            won = (over_hit == picked_over)

            decimal = american_to_decimal(dk_odds if dk_odds is not None else -110)
            if decimal is None:
                no_actions += 1
                continue

            if won:
                result        = "WIN"
                profit_flat   = round(100.0 * (decimal - 1), 2)
                profit_kelly  = round((rec_bet or 0.0) * (decimal - 1), 2)
                wins += 1
            else:
                result        = "LOSS"
                profit_flat   = -100.0
                profit_kelly  = round(-(rec_bet or 0.0), 2)
                losses += 1

            total_flat  += profit_flat
            total_kelly += profit_kelly

        conn.execute("""
            UPDATE picks
            SET result       = %s,
                profit_flat  = %s,
                profit_kelly = %s,
                settled_at   = %s
            WHERE pick_id = %s
        """, (result, profit_flat, profit_kelly, settled_at, pick_id))

        logger.debug(
            f"  {pick_label}: actual={actual_stat} vs line={scored_line} "
            f"({pick_side}) → {result}"
        )

    return wins, losses, pushes, no_actions, total_flat, total_kelly


# ── UFC Settlement ────────────────────────────────────────────────────────────

# ufcstats results can post hours after a card ends, and settle_picks only runs
# for game_date = yesterday — a trailing window lets late posts settle on
# subsequent mornings instead of lingering unsettled forever.
_UFC_SETTLE_WINDOW_DAYS = 14

_UFC_METHOD_CLASSES = ("decision", "ko_tko", "submission")


def _settle_ufc_picks(
    conn: DBConnection,
    game_date: str,
    settled_at: str,
) -> tuple[int, int, int, int, float, float]:
    """
    Settle unsettled BET UFC picks (moneyline / round totals / method) whose
    fight is final, for game_date and the trailing window before it.

    Conventions:
      • games.home_score/away_score for UFC are 1/0 win indicators
        (0.5/0.5 for draw/NC); home_win is NULL for draw/NC.
      • Round totals settle on fractional rounds completed (Over 2.5 = the
        fight passes 2:30 of round 3), from ufc_fight_log end_round/time.
      • Method picks compare pick_side to the fight's method class; DQ/other
        results settle as NO_ACTION (no class to match).
      • Prob-only picks (totals/method) have dk_odds NULL → −110 flat P&L.

    Returns (wins, losses, pushes, no_actions, total_flat, total_kelly).
    """
    from data.ingestors.ufc_stats_ingestor import rounds_completed

    lo = (datetime.strptime(game_date, "%Y-%m-%d")
          - timedelta(days=_UFC_SETTLE_WINDOW_DAYS - 1)).strftime("%Y-%m-%d")

    picks = conn.execute("""
        SELECT p.pick_id, p.game_id, p.model_id, p.pick_side, p.pick_label,
               p.dk_odds, p.recommended_bet, p.scored_line,
               g.home_win
        FROM picks p
        JOIN games g ON p.game_id = g.game_id
        WHERE p.game_date BETWEEN %s AND %s
          AND p.result IS NULL
          AND p.signal_type = 'BET'
          AND p.model_id LIKE 'ufc_%%'
          AND g.home_score IS NOT NULL
    """, (lo, game_date)).fetchall()

    if not picks:
        return 0, 0, 0, 0, 0.0, 0.0

    logger.info(f"Found {len(picks)} unsettled UFC picks ({lo}..{game_date})")

    # Fight results for the picked games (either fighter's row carries the
    # shared method/round/time fields)
    game_ids = sorted({p[1] for p in picks})
    ph = ",".join(["%s"] * len(game_ids))
    res_rows = conn.execute(f"""
        SELECT game_id, method, end_round, end_time_sec, scheduled_rounds
        FROM ufc_fight_log
        WHERE game_id IN ({ph})
    """, game_ids).fetchall()
    results = {r[0]: dict(zip(["game_id", "method", "end_round",
                               "end_time_sec", "scheduled_rounds"], r))
               for r in res_rows}

    wins = losses = pushes = no_actions = 0
    total_flat = total_kelly = 0.0

    for (pick_id, game_id, model_id, pick_side, pick_label,
         dk_odds, rec_bet, scored_line, home_win) in picks:

        market = _market_for_pick(model_id)
        res = results.get(game_id)
        result = None
        won = None

        if market == "h2h":
            if home_win is None:
                result = "PUSH"     # draw / no contest — ML stake refunded
            else:
                won = (home_win == 1) if pick_side == "home" else (home_win == 0)

        elif market == "totals":
            if res is None or scored_line is None:
                logger.debug(f"  Cannot settle UFC pick {pick_id} ({pick_label}): "
                             f"no fight result row yet")
                no_actions += 1
                continue   # leave unsettled — retried while in the window
            rc = rounds_completed(res.get("end_round"), res.get("end_time_sec"),
                                  res.get("scheduled_rounds"))
            if rc is None:
                no_actions += 1
                continue
            if float(rc) == float(scored_line):
                result = "PUSH"
            else:
                over_hit = float(rc) > float(scored_line)
                won = over_hit if pick_side == "over" else not over_hit

        elif market == "method":
            if res is None:
                no_actions += 1
                continue   # leave unsettled — retried while in the window
            actual = res.get("method")
            if actual not in _UFC_METHOD_CLASSES:
                result = "NO_ACTION"   # DQ / overturned — final, no class to match
            else:
                won = (pick_side == actual)

        else:
            logger.warning(f"  Unknown UFC market '{market}' for pick {pick_id}")
            no_actions += 1
            continue

        profit_flat = profit_kelly = 0.0
        if result is None:
            # Prob-only picks have dk_odds NULL — settle at −110 flat
            decimal = american_to_decimal(dk_odds if dk_odds is not None else -110)
            if won:
                result = "WIN"
                profit_flat  = round(100.0 * (decimal - 1), 2)
                profit_kelly = round((rec_bet or 0.0) * (decimal - 1), 2)
                wins += 1
            else:
                result = "LOSS"
                profit_flat  = -100.0
                profit_kelly = round(-(rec_bet or 0.0), 2)
                losses += 1
            total_flat  += profit_flat
            total_kelly += profit_kelly
        elif result == "PUSH":
            pushes += 1
        else:   # NO_ACTION (written — final state)
            no_actions += 1

        conn.execute("""
            UPDATE picks
            SET result       = %s,
                profit_flat  = %s,
                profit_kelly = %s,
                settled_at   = %s
            WHERE pick_id = %s
        """, (result, profit_flat, profit_kelly, settled_at, pick_id))

        logger.debug(f"  {pick_label}: {result}")

    return wins, losses, pushes, no_actions, total_flat, total_kelly


# ── Golf settlement ───────────────────────────────────────────────────────────

_GOLF_SETTLE_WINDOW_DAYS = 14


def _settle_golf_picks(
    conn: DBConnection,
    game_date: str,
    settled_at: str,
) -> tuple[int, int, int, int, float, float]:
    """
    Settle unsettled BET golf picks (outright / top-10 / top-20 / make-cut /
    matchup) for tournaments marked completed, over a trailing window
    (DataGolf results post a day or two after Sunday's finish).

    Conventions:
      • Player results come from golf_rounds (finish_pos / made_cut / 36-hole
        total). A player with no rounds (WD before teeing off) → NO_ACTION.
      • Top-N ties settle at FULL price as a win when finish_pos ≤ N (v1 — no
        dead-heat reduction; documented caveat).
      • make_cut with made_cut NULL (WD before the cut) → NO_ACTION (DK voids).
      • Matchup: the picked player vs the opponent (recovered from golf_odds);
        better finish wins, tie/void → PUSH.
      • Golf carries real DK odds for every market (dk_odds always present).

    Returns (wins, losses, pushes, no_actions, total_flat, total_kelly).
    """
    from features.golf_feature_engine import compute_golf_target, compute_matchup_target

    lo = (datetime.strptime(game_date, "%Y-%m-%d")
          - timedelta(days=_GOLF_SETTLE_WINDOW_DAYS - 1)).strftime("%Y-%m-%d")

    picks = conn.execute("""
        SELECT p.pick_id, p.game_id, p.model_id, p.pick_side, p.pick_label,
               p.player_id, p.dk_odds, p.recommended_bet
        FROM picks p
        JOIN golf_tournaments t ON t.game_id = p.game_id
        WHERE p.game_date BETWEEN %s AND %s
          AND p.result IS NULL
          AND p.signal_type = 'BET'
          AND p.model_id LIKE 'golf_%%'
          AND t.status = 'completed'
    """, (lo, game_date)).fetchall()

    if not picks:
        return 0, 0, 0, 0, 0.0, 0.0

    logger.info(f"Found {len(picks)} unsettled golf picks ({lo}..{game_date})")

    # Per-(game_id, dg_id) results from golf_rounds (finish_pos / made_cut dup'd
    # across rounds; r12_total = sum of the first two rounds' scores).
    game_ids = sorted({p[1] for p in picks})
    ph = ",".join(["%s"] * len(game_ids))
    res_rows = conn.execute(f"""
        SELECT game_id, dg_id,
               MAX(finish_pos) AS finish_pos,
               MAX(made_cut)   AS made_cut,
               SUM(CASE WHEN round_num <= 2 THEN score END) AS r12_total
        FROM golf_rounds
        WHERE game_id IN ({ph})
        GROUP BY game_id, dg_id
    """, game_ids).fetchall()
    results: dict[tuple, dict] = {}
    for game_id, dg_id, finish_pos, made_cut, r12_total in res_rows:
        results[(game_id, int(dg_id))] = {
            "finish_pos": int(finish_pos) if finish_pos is not None else None,
            "made_cut": int(made_cut) if made_cut is not None else None,
            "r12_total": float(r12_total) if r12_total is not None else None,
        }

    wins = losses = pushes = no_actions = 0
    total_flat = total_kelly = 0.0

    for (pick_id, game_id, model_id, pick_side, pick_label,
         player_id, dk_odds, rec_bet) in picks:
        try:
            dg_id = int(player_id)
        except (TypeError, ValueError):
            no_actions += 1
            continue

        result = None
        won = None
        res = results.get((game_id, dg_id))

        if model_id == "golf_matchup":
            opp = _golf_matchup_opponent(conn, game_id, dg_id)
            opp_res = results.get((game_id, opp)) if opp is not None else None
            if res is None or opp_res is None:
                no_actions += 1
                continue
            t = compute_matchup_target(res, opp_res)
            if t is None:
                result = "PUSH"
            else:
                won = (t == 1)
        else:
            if res is None:
                no_actions += 1
                continue
            t = compute_golf_target(model_id, res["finish_pos"], res["made_cut"])
            if t is None:
                result = "NO_ACTION"   # WD before the cut — DK voids
            else:
                won = (t == 1)

        profit_flat = profit_kelly = 0.0
        if result is None:
            decimal = american_to_decimal(dk_odds if dk_odds is not None else -110)
            if won:
                result = "WIN"
                profit_flat  = round(100.0 * (decimal - 1), 2)
                profit_kelly = round((rec_bet or 0.0) * (decimal - 1), 2)
                wins += 1
            else:
                result = "LOSS"
                profit_flat  = -100.0
                profit_kelly = round(-(rec_bet or 0.0), 2)
                losses += 1
            total_flat  += profit_flat
            total_kelly += profit_kelly
        elif result == "PUSH":
            pushes += 1
        else:
            no_actions += 1

        conn.execute("""
            UPDATE picks
            SET result = %s, profit_flat = %s, profit_kelly = %s, settled_at = %s
            WHERE pick_id = %s
        """, (result, profit_flat, profit_kelly, settled_at, pick_id))
        logger.debug(f"  {pick_label}: {result}")

    return wins, losses, pushes, no_actions, total_flat, total_kelly


def _golf_matchup_opponent(conn: DBConnection, game_id: str, dg_id: int) -> int | None:
    """Recover the opponent dg_id for a settled matchup pick from golf_odds."""
    row = conn.execute("""
        SELECT dg_id, opp_dg_id FROM golf_odds
        WHERE game_id = %s AND market = 'matchup_tournament'
          AND (dg_id = %s OR opp_dg_id = %s)
        ORDER BY snapshot_at DESC LIMIT 1
    """, (game_id, dg_id, dg_id)).fetchone()
    if not row:
        return None
    a, b = int(row[0]), int(row[1]) if row[1] is not None else None
    return b if a == dg_id else a


# ── Closing Line Value (CLV) ──────────────────────────────────────────────────

# pick_side → the matching price column in the odds row
_SIDE_PRICE_COL = {
    "home":  "home_price",
    "away":  "away_price",
    "draw":  "draw_price",
    "over":  "over_price",
    "under": "under_price",
}


def _closing_dk_odds(conn: DBConnection, game_id: str, market: str,
                     commence_time: str | None) -> dict | None:
    """
    Closing DraftKings odds snapshot for a game+market.

    The hourly pipeline labels every snapshot 'open', so the last DK snapshot at
    or before first pitch is effectively the closing line. Falls back to the
    freshest DK snapshot if commence_time is missing or every snapshot landed
    after the listed start.

    Returns a dict of the price columns, or None if no DK snapshot exists.
    """
    cols = ["home_price", "away_price", "draw_price",
            "spread_home", "total_line", "over_price", "under_price"]
    # Standard runline only (±1.5) — avoid alternate spread lines. F5 spreads
    # use -0.5 and are prob-only (no dk_odds), so they never reach this path.
    spread_filter = "AND ABS(spread_home) = 1.5" if market == "spreads" else ""

    if commence_time:
        row = conn.execute(f"""
            SELECT home_price, away_price, draw_price,
                   spread_home, total_line, over_price, under_price
            FROM odds
            WHERE game_id   = %s
              AND market    = %s
              AND bookmaker = 'draftkings'
              {spread_filter}
              AND snapshot_at <= %s
            ORDER BY snapshot_at DESC
            LIMIT 1
        """, (game_id, market, commence_time)).fetchone()
        if row:
            return dict(zip(cols, row))

    row = conn.execute(f"""
        SELECT home_price, away_price, draw_price,
               spread_home, total_line, over_price, under_price
        FROM odds
        WHERE game_id   = %s
          AND market    = %s
          AND bookmaker = 'draftkings'
          {spread_filter}
        ORDER BY snapshot_at DESC
        LIMIT 1
    """, (game_id, market)).fetchone()
    return dict(zip(cols, row)) if row else None


def _capture_clv(conn: DBConnection, game_date: str, captured_at: str) -> int:
    """
    Record closing line value for each official (BET) game-level pick on game_date.

    For every BET pick that has a scored DK price but no CLV yet, find the closing
    DK price on the pick side (last pre-game snapshot) and store:
      - closing_dk_odds : closing American price on our side
      - closing_line    : closing total/spread on our side (NULL for moneyline)
      - clv_pct         : closing_implied_prob - bet_implied_prob, in pp
                          (positive = we beat the close — the line moved toward us)

    Player props are skipped — their prices live in player_prop_odds, not odds.
    Idempotent: only fills picks where clv_pct IS NULL. Returns picks updated.
    """
    rows = conn.execute("""
        SELECT p.pick_id, p.game_id, p.model_id, p.pick_side, p.dk_odds,
               g.commence_time
        FROM picks p
        JOIN games g ON p.game_id = g.game_id
        WHERE p.game_date = %s
          AND p.signal_type = 'BET'
          AND p.dk_odds IS NOT NULL
          AND p.clv_pct IS NULL
          AND p.model_id NOT LIKE 'mlb_prop_%%'
          AND p.model_id NOT LIKE 'wnba_prop_%%'
          AND p.model_id NOT LIKE 'golf_%%'
    """, (game_date,)).fetchall()

    if not rows:
        return 0

    updated = 0
    for pick_id, game_id, model_id, pick_side, dk_odds, commence_time in rows:
        market  = _market_for_pick(model_id)
        closing = _closing_dk_odds(conn, game_id, market, commence_time)
        if not closing:
            continue

        price_col     = _SIDE_PRICE_COL.get(pick_side)
        closing_price = closing.get(price_col) if price_col else None
        if closing_price is None:
            continue

        bet_ip   = american_to_implied_prob(dk_odds)
        close_ip = american_to_implied_prob(closing_price)
        if bet_ip is None or close_ip is None:
            continue

        clv_pct = round((close_ip - bet_ip) * 100, 2)

        if "totals" in market:
            closing_line = closing.get("total_line")
        elif "spreads" in market:
            closing_line = closing.get("spread_home")
        else:
            closing_line = None

        conn.execute("""
            UPDATE picks
            SET closing_dk_odds = %s,
                closing_line    = %s,
                clv_pct         = %s,
                clv_captured_at = %s
            WHERE pick_id = %s
        """, (closing_price, closing_line, clv_pct, captured_at, pick_id))
        updated += 1

    if updated:
        logger.info(f"CLV captured for {updated} picks on {game_date}")
    return updated


# ── Result Computation ────────────────────────────────────────────────────────

def _compute_result(pick_side: str, market: str,
                     home_score: float, away_score: float,
                     home_win: int, home_win_reg: int,
                     went_to_ot: int,
                     dk_odds: float, spread_home: float,
                     total_line: float,
                     rec_bet: float) -> tuple[str, float, float]:
    """
    Determine final result for one pick.

    Returns:
        (result: str, profit_flat: float, profit_kelly: float)
        result is 'WIN' | 'LOSS' | 'PUSH' | 'NO_ACTION'
    """
    if home_score is None or away_score is None:
        return "NO_ACTION", 0.0, 0.0

    total  = home_score + away_score
    margin = home_score - away_score

    won = None

    if market in ("h2h", "h2h_1st_5_innings"):
        if home_win is None:
            return "NO_ACTION", 0.0, 0.0
        if pick_side == "home":
            won = (home_win == 1)
        elif pick_side == "away":
            won = (home_win == 0)

    elif market == "h2h_3way":
        # Regulation only
        if pick_side == "home":
            won = (home_win_reg == 1)
        elif pick_side == "away":
            won = (home_win_reg == 0 and not went_to_ot)
        elif pick_side == "draw":
            won = (went_to_ot == 1)

    elif market in ("totals", "totals_1st_5_innings"):
        if total_line is None:
            return "NO_ACTION", 0.0, 0.0
        if total == total_line:
            return "PUSH", 0.0, 0.0
        if pick_side == "over":
            won = (total > total_line)
        elif pick_side == "under":
            won = (total < total_line)

    elif market in ("spreads", "spreads_1st_5_innings"):
        if spread_home is None:
            return "NO_ACTION", 0.0, 0.0
        covered_margin = margin + spread_home
        if covered_margin == 0:
            return "PUSH", 0.0, 0.0
        if pick_side == "home":
            won = (covered_margin > 0)
        elif pick_side == "away":
            won = (covered_margin < 0)

    if won is None:
        return "NO_ACTION", 0.0, 0.0

    # Compute P&L
    # F5 prob-only picks have dk_odds=NULL — use -110 (standard juice) for flat P&L
    decimal = american_to_decimal(dk_odds if dk_odds is not None else -110)
    if decimal is None:
        return "NO_ACTION", 0.0, 0.0

    if won:
        profit_flat   = round(100.0 * (decimal - 1), 2)
        profit_kelly  = round(rec_bet * (decimal - 1), 2)
        return "WIN", profit_flat, profit_kelly
    else:
        return "LOSS", -100.0, round(-rec_bet, 2)


def _market_for_pick(model_id: str) -> str:
    """Map model_id to its odds market key."""
    return MODELS[model_id][1] if model_id in MODELS else "h2h"


# ── Settler ───────────────────────────────────────────────────────────────────

def settle_picks(game_date: str = None) -> dict:
    """
    Settle all unsettled picks from game_date (default: yesterday).

    Returns:
        Summary dict with wins, losses, pushes, and P&L.
    """
    if game_date is None:
        game_date = (datetime.now(ZoneInfo("America/New_York")).date() - timedelta(days=1)).isoformat()

    logger.info(f"Settling picks for {game_date}...")

    conn = get_connection()

    try:
        # Fetch and store final scores before querying picks
        _fetch_and_store_scores(conn, game_date)
        conn.commit()

        # Record closing line value now that all pre-game odds snapshots have
        # accumulated. Independent of settlement — runs even for picks whose
        # game can't be settled yet (e.g. postponed) and is idempotent.
        clv_at = datetime.now(ZoneInfo("America/New_York")).isoformat()
        _capture_clv(conn, game_date, clv_at)
        conn.commit()

        wins = losses = pushes = no_actions = 0
        total_profit_flat  = 0.0
        total_profit_kelly = 0.0
        settled_at = datetime.now(ZoneInfo("America/New_York")).isoformat()

        # ── Game-level picks (moneyline, O/U, runline, F5 ML) ─────────────
        # Prop picks (mlb_prop_% / wnba_prop_%) are settled separately below —
        # _market_for_pick falls back to 'h2h' for unknown model_ids, which
        # stamps over/under prop picks as NO_ACTION and permanently blocks
        # _settle_prop_picks (it only touches result IS NULL rows).
        # UFC picks are also settled separately — under the UFC score
        # convention (home_score = 1/0 win indicator) the generic totals math
        # (home_score + away_score vs line) would be meaningless, and 'method'
        # picks need the fight result from ufc_fight_log.
        # Uses p.scored_line which stores the spread or total at scoring time,
        # correct for both full-game and F5 picks.
        picks = conn.execute("""
            SELECT p.pick_id, p.game_id, p.model_id, p.pick_side,
                   p.dk_odds, p.recommended_bet,
                   g.home_score, g.away_score,
                   g.home_win, g.home_win_reg, g.went_to_ot,
                   p.scored_line,
                   g.home_score_f5, g.away_score_f5
            FROM picks p
            LEFT JOIN games g ON p.game_id = g.game_id
            WHERE p.game_date = %s
              AND p.result IS NULL
              AND p.signal_type = 'BET'
              AND p.model_id NOT LIKE 'mlb_prop_%%'
              AND p.model_id NOT LIKE 'wnba_prop_%%'
              AND p.model_id NOT LIKE 'ufc_%%'
              AND p.model_id NOT LIKE 'golf_%%'
              AND g.home_score IS NOT NULL
        """, (game_date,)).fetchall()

        if picks:
            logger.info(f"Found {len(picks)} unsettled game picks")

        for row in picks:
            (pick_id, game_id, model_id, pick_side,
             dk_odds, rec_bet,
             home_score, away_score,
             home_win, home_win_reg, went_to_ot,
             scored_line,
             home_score_f5, away_score_f5) = row

            market = _market_for_pick(model_id)
            is_f5 = "1st_5_innings" in market

            # For F5 models, use F5 scores and derive F5 home_win
            if is_f5:
                if home_score_f5 is None or away_score_f5 is None:
                    continue  # can't settle without F5 scores
                settle_home = home_score_f5
                settle_away = away_score_f5
                settle_home_win = int(home_score_f5 > away_score_f5) if home_score_f5 != away_score_f5 else None
            else:
                settle_home = home_score
                settle_away = away_score
                settle_home_win = home_win

            # scored_line is the spread for spread models, total for totals models
            spread_home = scored_line if "spreads" in market else None
            total_line = scored_line if "totals" in market else None

            result, profit_flat, profit_kelly = _compute_result(
                pick_side, market,
                settle_home, settle_away,
                settle_home_win, home_win_reg, went_to_ot,
                dk_odds, spread_home, total_line,
                rec_bet or 0.0,
            )

            conn.execute("""
                UPDATE picks
                SET result       = %s,
                    profit_flat  = %s,
                    profit_kelly = %s,
                    settled_at   = %s
                WHERE pick_id = %s
            """, (result, profit_flat, profit_kelly, settled_at, pick_id))

            if result == "WIN":
                wins += 1
                total_profit_flat  += profit_flat
                total_profit_kelly += profit_kelly
            elif result == "LOSS":
                losses += 1
                total_profit_flat  += profit_flat
                total_profit_kelly += profit_kelly
            elif result == "PUSH":
                pushes += 1
            else:
                no_actions += 1

        # ── Prop picks (player props: mlb_prop_* / wnba_prop_* models) ────
        # Trailing window so game logs that arrive after a morning settle
        # (e.g. WNBA box scores from Matt's machine) still settle later.
        p_wins, p_losses, p_pushes, p_no_actions, p_flat, p_kelly = (
            _settle_prop_picks_window(conn, game_date, settled_at)
        )
        wins       += p_wins
        losses     += p_losses
        pushes     += p_pushes
        no_actions += p_no_actions
        total_profit_flat  += p_flat
        total_profit_kelly += p_kelly

        # ── UFC picks (moneyline / round totals / method) ─────────────────
        u_wins, u_losses, u_pushes, u_no_actions, u_flat, u_kelly = (
            _settle_ufc_picks(conn, game_date, settled_at)
        )
        wins       += u_wins
        losses     += u_losses
        pushes     += u_pushes
        no_actions += u_no_actions
        total_profit_flat  += u_flat
        total_profit_kelly += u_kelly

        # ── Golf picks (outright / top-N / make-cut / matchup) ────────────
        # Trailing window — DataGolf results post a day or two after Sunday.
        g_wins, g_losses, g_pushes, g_no_actions, g_flat, g_kelly = (
            _settle_golf_picks(conn, game_date, settled_at)
        )
        wins       += g_wins
        losses     += g_losses
        pushes     += g_pushes
        no_actions += g_no_actions
        total_profit_flat  += g_flat
        total_profit_kelly += g_kelly

        conn.commit()

        n_settled = wins + losses + pushes
        if n_settled == 0 and no_actions == 0:
            logger.info(f"No unsettled picks found for {game_date}")
            return {"game_date": game_date, "settled": 0}

        win_rate = wins / max(wins + losses, 1)
        flat_roi = total_profit_flat / max((wins + losses) * 100, 1)

        logger.success(
            f"\n{'═'*50}\n"
            f"  Settled: {game_date}\n"
            f"  Results: {wins}W / {losses}L / {pushes}P / {no_actions}N\n"
            f"  Win Rate: {win_rate:.1%}\n"
            f"  Flat P&L: ${total_profit_flat:+,.2f} (ROI: {flat_roi:.1%})\n"
            f"  Kelly P&L: ${total_profit_kelly:+,.2f}\n"
            f"{'═'*50}"
        )

        return {
            "game_date":     game_date,
            "settled":       n_settled,
            "wins":          wins,
            "losses":        losses,
            "pushes":        pushes,
            "no_actions":    no_actions,
            "profit_flat":   round(total_profit_flat, 2),
            "profit_kelly":  round(total_profit_kelly, 2),
            "win_rate":      round(win_rate, 4),
            "flat_roi":      round(flat_roi, 4),
        }

    except Exception as exc:
        conn.rollback()
        logger.error(f"Settlement failed: {exc}")
        raise
    finally:
        conn.close()


# ── Performance Summary ───────────────────────────────────────────────────────

def print_performance_summary(days: int = 30) -> dict:
    """
    Print running P&L and performance metrics for the last N days.
    """
    cutoff = (datetime.now(ZoneInfo("America/New_York")).date() - timedelta(days=days)).isoformat()

    conn = get_connection()
    try:
        # Overall stats
        overall = conn.execute("""
            SELECT
                COUNT(*) as total_picks,
                SUM(CASE WHEN result = 'WIN'  THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN result = 'PUSH' THEN 1 ELSE 0 END) as pushes,
                SUM(profit_flat)  as total_flat_pnl,
                SUM(profit_kelly) as total_kelly_pnl,
                AVG(edge)         as avg_edge,
                MAX(bankroll_at_pick) as bankroll_at_pick
            FROM picks
            WHERE game_date >= ?
              AND result IS NOT NULL
              AND signal_type = 'BET'
        """, (cutoff,)).fetchone()

        # Per-model breakdown
        by_model = conn.execute("""
            SELECT model_id,
                   COUNT(*) as picks,
                   SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins,
                   SUM(profit_flat) as flat_pnl,
                   SUM(profit_kelly) as kelly_pnl,
                   AVG(edge) as avg_edge
            FROM picks
            WHERE game_date >= ?
              AND result IS NOT NULL
              AND signal_type = 'BET'
            GROUP BY model_id
            ORDER BY flat_pnl DESC
        """, (cutoff,)).fetchall()

        # Current bankroll
        current_bankroll = conn.execute("""
            SELECT bankroll_at_pick + COALESCE(profit_kelly, 0)
            FROM picks
            WHERE result IS NOT NULL
            ORDER BY settled_at DESC
            LIMIT 1
        """).fetchone()

        # Running bankroll history (for chart)
        bankroll_history = conn.execute("""
            SELECT game_date,
                   SUM(profit_kelly) OVER (ORDER BY settled_at) as cumulative_kelly
            FROM picks
            WHERE game_date >= ?
              AND result IS NOT NULL
              AND signal_type = 'BET'
            ORDER BY settled_at
        """, (cutoff,)).fetchall()

    finally:
        conn.close()

    # Print
    logger.info(f"\n{'═'*60}")
    logger.info(f"  PAPER TRADING SUMMARY (last {days} days)")
    logger.info(f"{'═'*60}")

    if overall and overall[0]:
        total, wins, losses, pushes, flat_pnl, kelly_pnl, avg_edge, _ = overall
        decided = max(wins + losses, 1)
        logger.info(f"  Total Picks:  {total}")
        logger.info(f"  Record:       {wins}W / {losses}L / {pushes}P")
        logger.info(f"  Win Rate:     {wins/decided:.1%}")
        logger.info(f"  Flat P&L:     ${flat_pnl:+,.2f} (ROI: {flat_pnl/(decided*100):.1%})")
        logger.info(f"  Kelly P&L:    ${kelly_pnl:+,.2f}")
        logger.info(f"  Avg Edge:     {avg_edge:.2%}" if avg_edge else "")
        if current_bankroll and current_bankroll[0]:
            logger.info(f"  Bankroll:     ${current_bankroll[0]:,.2f}")

    if by_model:
        logger.info(f"\n  {'Model':<30} {'Picks':>5} {'W/L':>7} {'Flat P&L':>10} {'Avg Edge':>9}")
        logger.info(f"  {'-'*63}")
        for row in by_model:
            mid, picks, wins, flat_pnl, kelly_pnl, avg_edge = row
            losses = picks - wins if wins else picks
            wl = f"{wins}/{losses}" if wins is not None else "–"
            logger.info(f"  {mid:<30} {picks:>5} {wl:>7} "
                         f"${flat_pnl or 0:>9,.2f} {avg_edge or 0:>8.2%}")

    logger.info(f"{'═'*60}\n")

    return {
        "total_picks":    overall[0] if overall else 0,
        "wins":           overall[1] if overall else 0,
        "losses":         overall[2] if overall else 0,
        "flat_pnl":       overall[4] if overall else 0.0,
        "kelly_pnl":      overall[5] if overall else 0.0,
        "by_model":       [dict(zip(
            ["model_id","picks","wins","flat_pnl","kelly_pnl","avg_edge"], r
        )) for r in (by_model or [])],
        "bankroll_history": [{"date": r[0], "cumulative_kelly": r[1]}
                              for r in (bankroll_history or [])],
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Paper trader result settler")
    parser.add_argument("--date",    help="Game date to settle YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--summary", action="store_true", help="Print P&L summary")
    parser.add_argument("--days",    type=int, default=30, help="Days for summary")
    args = parser.parse_args()

    if args.summary:
        print_performance_summary(days=args.days)
    else:
        result = settle_picks(game_date=args.date)
        logger.info(f"Done: {result}")
