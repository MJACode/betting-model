"""
paper_tracker.py — Morning result settler. Grades yesterday's picks and
writes P&L. (Module name is historical; the record it settles is the live one.)

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
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import sys

import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import LIVE_MODELS, MODELS
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
    # NBA props — resolved from nba_player_game_log
    "nba_prop_player_points":       ("nba_player", "points"),
    "nba_prop_player_rebounds":     ("nba_player", "rebounds"),
    "nba_prop_player_assists":      ("nba_player", "assists"),
    "nba_prop_player_threes":       ("nba_player", "fg3_made"),
    "nba_prop_player_pra":          ("nba_player", "COMPUTE_PRA"),
    "nba_prop_player_blocks":       ("nba_player", "blocks"),
    "nba_prop_player_steals":       ("nba_player", "steals"),
    "nba_prop_player_turnovers":    ("nba_player", "turnovers"),
    "nba_prop_player_dd":           ("nba_player", "COMPUTE_DD"),
    # NFL props — resolved from nfl_player_game_log. Keyed on the NORMALISED
    # player name rather than an id: the odds feed and nflverse do not spell
    # names the same way, and normalised name is the only bridge the whole NFL
    # prop system has (the same join the snap counts use).
    "nfl_prop_pass_yards":          ("nfl_player", "passing_yards"),
    "nfl_prop_pass_attempts":       ("nfl_player", "attempts"),
    "nfl_prop_pass_completions":    ("nfl_player", "completions"),
    "nfl_prop_pass_tds":            ("nfl_player", "passing_tds"),
    "nfl_prop_rush_yards":          ("nfl_player", "rushing_yards"),
    "nfl_prop_rush_attempts":       ("nfl_player", "carries"),
    "nfl_prop_rec_yards":           ("nfl_player", "receiving_yards"),
    "nfl_prop_receptions":          ("nfl_player", "receptions"),
    "nfl_prop_rush_rec_yards":      ("nfl_player", "COMPUTE_RUSH_REC_YDS"),
    "nfl_prop_anytime_td":          ("nfl_player", "COMPUTE_ANY_TD"),
    "nfl_prop_tackles_assists":     ("nfl_player", "COMPUTE_TACKLES"),
    "nfl_prop_sacks":               ("nfl_player", "def_sacks"),
    # The market-relative rule is ONE model id spanning many markets, so its
    # stat cannot come from the model id — it is resolved per pick from
    # picks.prop_market via _NFL_MARKET_STAT below.
    "nfl_prop_market":              ("nfl_player", "FROM_PROP_MARKET"),
}

# Odds API market key -> the column (or sentinel) that settles it. Mirrors
# models.nfl_prop_market.MARKET_STAT, which is what the backtest grades with;
# two different opinions about what a market means is how a backtest and a
# settler end up disagreeing.
_NFL_MARKET_STAT = {
    "player_pass_yds": "passing_yards", "player_pass_attempts": "attempts",
    "player_pass_completions": "completions", "player_pass_tds": "passing_tds",
    "player_rush_yds": "rushing_yards", "player_rush_attempts": "carries",
    "player_reception_yds": "receiving_yards", "player_receptions": "receptions",
    "player_rush_reception_yds": "COMPUTE_RUSH_REC_YDS",
    "player_anytime_td": "COMPUTE_ANY_TD",
    "player_tackles_assists": "COMPUTE_TACKLES",
    "player_sacks": "def_sacks",
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


def _load_nba_prop_actuals(conn: DBConnection, game_date: str) -> dict:
    """
    Bulk-load nba_player_game_log rows for game_date.

    Returns:
        nba_actuals: {(player_id, game_id): row_dict}
    Includes steals/blocks so the double-double model (COMPUTE_DD) can settle.
    """
    rows = conn.execute("""
        SELECT player_id, player_name, game_id,
               points, rebounds, assists, fg3_made, steals, blocks
        FROM nba_player_game_log
        WHERE game_date = %s
    """, (game_date,)).fetchall()

    _cols = ["player_id", "player_name", "game_id",
             "points", "rebounds", "assists", "fg3_made", "steals", "blocks"]
    nba_actuals: dict = {}

    for row in rows:
        d = dict(zip(_cols, row))
        nba_actuals[(d["player_id"], d["game_id"])] = d

    logger.debug(
        f"NBA prop actuals: {len(nba_actuals)} player rows for {game_date}"
    )
    return nba_actuals


def _load_nfl_prop_actuals(conn: DBConnection, game_date: str) -> dict:
    """
    {(norm_player_name, game_id): row_dict} from nfl_player_game_log.

    Keyed on the NORMALISED name, not player_id. Every other sport keys on an
    id because the odds feed and the stat feed agree on one; NFL is the sport
    where they do not ("Marvin Harrison Jr." vs "Marvin Harrison", accents,
    suffixes), so the id is frequently unknown at pick time and the normalised
    name is the bridge the rest of the NFL prop system already runs on.
    """
    from data.ingestors.nfl_props_data_ingestor import norm_player_name

    cols = ["player_id", "player_name", "game_id",
            "passing_yards", "attempts", "completions", "passing_tds",
            "rushing_yards", "carries", "rushing_tds",
            "receiving_yards", "receptions", "receiving_tds",
            "def_sacks", "def_tackles_solo", "def_tackle_assists"]
    rows = conn.execute(
        f"SELECT {', '.join(cols)} FROM nfl_player_game_log WHERE game_date = %s",
        (game_date,)).fetchall()

    out: dict = {}
    for row in rows:
        d = dict(zip(cols, row))
        out[(norm_player_name(d["player_name"]), d["game_id"])] = d
    logger.debug(f"NFL prop actuals: {len(out)} player rows for {game_date}")
    return out


def _nfl_prop_actual(row: dict, stat_col: str):
    """Resolve one NFL prop's actual, including the three derived targets."""
    def n(c):
        v = row.get(c)
        return 0.0 if v is None else float(v)

    if stat_col == "COMPUTE_RUSH_REC_YDS":
        return n("rushing_yards") + n("receiving_yards")
    if stat_col == "COMPUTE_ANY_TD":
        # Over 0.5 on a 0/1 indicator. Return TDs are not in the weekly file,
        # so a kick-return score settles as a loss — a known undercount, and
        # the alternative is inventing a number we do not have.
        return float((n("rushing_tds") + n("receiving_tds")) >= 1)
    if stat_col == "COMPUTE_TACKLES":
        # Solo + assists. NOTE §5b: our count runs ~9pp under the number the
        # books grade, which is why nfl_prop_tackles_assists stays paused. This
        # settles what we can measure; it does not claim to match the book.
        return n("def_tackles_solo") + n("def_tackle_assists")
    v = row.get(stat_col)
    return None if v is None else float(v)


# Prop game logs can land after the morning settle (WNBA box scores are
# ingested on Matt's machine, which may run after the Actions settle), and
# settle_picks only runs for game_date = yesterday — a trailing window lets
# late-arriving logs settle on subsequent mornings instead of lingering
# unsettled forever. (UFC settlement has no window — it settles any unsettled
# BET pick whose fight has scores, since UFC pick volume is tiny.)
_PROP_SETTLE_WINDOW_DAYS = 14
# Cap on the self-healing reach below. Bounds the work when something has been
# broken for a long time, and stops a single bad row dragging the loop back to
# the start of the season forever.
_PROP_SETTLE_MAX_HEAL_DAYS = 365


def _prop_settle_window_days(conn: DBConnection, game_date: str) -> int:
    """
    How many days back to settle. Normally _PROP_SETTLE_WINDOW_DAYS, but
    EXTENDED to reach any BET prop pick that is still unsettled on a game that
    already has a final score.

    A fixed trailing window silently abandons picks: if settlement is broken or
    delayed for longer than the window, those picks age out and can NEVER be
    graded, even though their actuals sit in player_game_log the whole time.
    That is not hypothetical -- 752 BET prop picks from 2026-05-09..06-16 were
    stranded exactly this way (99% of them WITH their game-log row) when the
    settle-before-game-log ordering bug was fixed only after they had aged past
    14 days. They are missing from the published record permanently.

    Anchoring the lower bound to the oldest still-settleable pick is the same
    self-healing shape ufc_csv_loader._heal_window_lo uses for a mirror that
    lags. Dates with nothing to do return immediately from _settle_prop_picks,
    so a wide window costs one cheap query per empty day.
    """
    try:
        row = conn.execute("""
            SELECT MIN(p.game_date)
              FROM picks p
              JOIN games g ON g.game_id = p.game_id
             WHERE p.signal_type = 'BET'
               AND p.result IS NULL
               AND p.model_id LIKE '%%_prop_%%'
               AND g.home_score IS NOT NULL
        """).fetchone()
    except Exception as exc:
        logger.warning(f"Prop settle window: heal probe failed ({exc}) — "
                       f"using the fixed {_PROP_SETTLE_WINDOW_DAYS}-day window")
        return _PROP_SETTLE_WINDOW_DAYS

    oldest = row[0] if row else None
    if not oldest:
        return _PROP_SETTLE_WINDOW_DAYS

    try:
        span = (datetime.strptime(game_date, "%Y-%m-%d")
                - datetime.strptime(str(oldest), "%Y-%m-%d")).days + 1
    except ValueError:
        return _PROP_SETTLE_WINDOW_DAYS

    days = max(_PROP_SETTLE_WINDOW_DAYS, min(span, _PROP_SETTLE_MAX_HEAL_DAYS))
    if days > _PROP_SETTLE_WINDOW_DAYS:
        logger.info(f"Prop settle: extending window to {days} days — oldest "
                    f"unsettled prop BET on a scored game is {oldest}")
    return days


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
    for offset in range(_prop_settle_window_days(conn, game_date)):
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
               p.player_id, p.pick_label, p.prop_market, p.player_key
        FROM picks p
        JOIN games g ON p.game_id = g.game_id
        WHERE p.game_date = %s
          AND p.result IS NULL
          AND p.signal_type = 'BET'
          AND (p.model_id LIKE 'mlb_prop_%%' OR p.model_id LIKE 'wnba_prop_%%'
               OR p.model_id LIKE 'nba_prop_%%' OR p.model_id LIKE 'nfl_prop_%%')
          AND g.home_score IS NOT NULL
    """, (game_date,)).fetchall()

    if not prop_picks:
        return 0, 0, 0, 0, 0.0, 0.0

    logger.info(f"Found {len(prop_picks)} unsettled prop picks for {game_date}")

    pitcher_by_id, pitcher_by_name, batter_actuals = _load_prop_actuals(conn, game_date)
    wnba_actuals = _load_wnba_prop_actuals(conn, game_date)
    nba_actuals = _load_nba_prop_actuals(conn, game_date)
    nfl_actuals = _load_nfl_prop_actuals(conn, game_date)

    # Games whose box scores have been ingested (any player row). Used to tell
    # "log not ingested yet" (leave unsettled, retry tomorrow) apart from
    # "player did not play" (game logged, player absent → DNP → NO_ACTION).
    mlb_logged_games = ({gid for (_pid, gid) in pitcher_by_id}
                        | {gid for (_pid, gid) in batter_actuals})
    wnba_logged_games = {gid for (_pid, gid) in wnba_actuals}
    nba_logged_games = {gid for (_pid, gid) in nba_actuals}
    nfl_logged_games = {gid for (_name, gid) in nfl_actuals}
    logged_games_by_type = {
        "pitcher":     mlb_logged_games,
        "batter":      mlb_logged_games,
        "wnba_player": wnba_logged_games,
        "nba_player":  nba_logged_games,
        "nfl_player":  nfl_logged_games,
    }

    wins = losses = pushes = no_actions = 0
    total_flat = total_kelly = 0.0

    for row in prop_picks:
        (pick_id, game_id, model_id, pick_side,
         dk_odds, rec_bet, scored_line, player_id, pick_label,
         prop_market, player_key) = row

        mapping = _PROP_STAT_MAP.get(model_id)
        if mapping is None:
            logger.warning(f"No stat mapping for {model_id}, skipping pick {pick_id}")
            no_actions += 1
            continue

        player_type, stat_col = mapping
        if stat_col == "FROM_PROP_MARKET":
            stat_col = _NFL_MARKET_STAT.get(prop_market or "")
            if stat_col is None:
                # A pick written without its market cannot be graded, and
                # guessing one would silently settle the wrong stat.
                logger.warning(f"pick {pick_id}: model {model_id} has "
                               f"prop_market={prop_market!r} — cannot resolve a stat")
                no_actions += 1
                continue

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

        elif player_type == "nba_player":
            if player_id:
                row_data = nba_actuals.get((player_id, game_id))
                if row_data:
                    if stat_col == "COMPUTE_PRA":
                        pts = row_data.get("points") or 0
                        reb = row_data.get("rebounds") or 0
                        ast = row_data.get("assists") or 0
                        actual_stat = pts + reb + ast
                    elif stat_col == "COMPUTE_DD":
                        # Double-double: ≥10 in ≥2 of pts/reb/ast/stl/blk → 1 else 0.
                        # scored_line is 0.5, so over (Yes) wins when actual == 1.
                        cats = [row_data.get("points"), row_data.get("rebounds"),
                                row_data.get("assists"), row_data.get("steals"),
                                row_data.get("blocks")]
                        actual_stat = int(sum(1 for c in cats if (c or 0) >= 10) >= 2)
                    else:
                        actual_stat = row_data.get(stat_col)

        elif player_type == "nfl_player":
            from data.ingestors.nfl_props_data_ingestor import norm_player_name
            # player_key is the structural join. The pick_label regex is the
            # fallback for rows written before that column existed — it works,
            # but it makes a display string load-bearing, which is why the
            # column exists.
            key = player_key
            if not key:
                m = _PICK_LABEL_RE.match(pick_label or "")
                key = norm_player_name(m.group(1).strip()) if m else None
            row_data = nfl_actuals.get((key, game_id)) if key else None
            if row_data:
                actual_stat = _nfl_prop_actual(row_data, stat_col)

        else:  # batter
            if player_id:
                row_data = batter_actuals.get((player_id, game_id))
                if row_data:
                    actual_stat = row_data.get(stat_col)

        if actual_stat is None or scored_line is None:
            # Player DNP: the game's box scores ARE ingested but this player has
            # no row — rest / late scratch / injury. DK voids the prop, so
            # settle NO_ACTION ($0) instead of retrying forever. Requires a
            # stored player_id so a legacy name-parse miss can't be mistaken
            # for a DNP. Games with no log rows at all stay unsettled (the
            # ingest simply hasn't landed yet — retried within the window).
            # The player_id requirement exists so a legacy NAME-parse miss is
            # not mistaken for a DNP. NFL has no id at pick time by design —
            # normalised name IS its primary key — so for NFL the equivalent
            # evidence is that a name was parsed at all.
            _identified = bool(player_id) or (
                player_type == "nfl_player"
                and (player_key or _PICK_LABEL_RE.match(pick_label or "")))
            if (actual_stat is None and _identified
                    and game_id in logged_games_by_type.get(player_type, set())):
                conn.execute("""
                    UPDATE picks
                    SET result       = 'NO_ACTION',
                        profit_flat  = 0,
                        profit_kelly = 0,
                        settled_at   = %s
                    WHERE pick_id = %s
                """, (settled_at, pick_id))
                logger.info(f"  {pick_label}: player did not play → NO_ACTION")
            else:
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

_UFC_METHOD_CLASSES = ("decision", "ko_tko", "submission")


def _settle_ufc_picks(
    conn: DBConnection,
    game_date: str,
    settled_at: str,
) -> tuple[int, int, int, int, float, float]:
    """
    Settle unsettled BET UFC picks (moneyline / round totals / method) whose
    fight is final, for game_date and any earlier date. No trailing-window
    lower bound: the CSV mirror can publish a card's results weeks late (the
    old 14-day window left the whole of June 2026 permanently unsettled), and
    unsettled UFC BET volume is tiny, so `result IS NULL` bounds the query.

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
    from data.ingestors.ufc_stats_ingestor import rounds_completed, slugify_fighter

    picks = conn.execute("""
        SELECT p.pick_id, p.game_id, p.model_id, p.pick_side, p.pick_label,
               p.dk_odds, p.recommended_bet, p.scored_line,
               g.home_win, g.home_team, g.away_team, p.game_date
        FROM picks p
        JOIN games g ON p.game_id = g.game_id
        WHERE p.game_date <= %s
          AND p.result IS NULL
          AND p.signal_type = 'BET'
          AND p.model_id LIKE 'ufc_%%'
          AND g.home_score IS NOT NULL
    """, (game_date,)).fetchall()

    if not picks:
        return 0, 0, 0, 0, 0.0, 0.0

    logger.info(f"Found {len(picks)} unsettled UFC picks (through {game_date})")

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

    # Fallback keyed by fighter slug-pair: fight_log rows live only on the
    # canonical games row, but picks can sit on duplicate rows for the same
    # fight (home/away swapped between odds fetches, or ±1-day date drift).
    pick_dates = sorted({str(p[11])[:10] for p in picks})
    fl_lo = (datetime.strptime(pick_dates[0], "%Y-%m-%d")
             - timedelta(days=1)).strftime("%Y-%m-%d")
    fl_hi = (datetime.strptime(pick_dates[-1], "%Y-%m-%d")
             + timedelta(days=1)).strftime("%Y-%m-%d")
    pair_results: dict[frozenset, list[dict]] = {}
    for (fname, oname, fl_date, method, end_round,
         end_time_sec, scheduled_rounds) in conn.execute("""
        SELECT fighter_name, opponent_name, game_date, method, end_round,
               end_time_sec, scheduled_rounds
        FROM ufc_fight_log
        WHERE game_date BETWEEN %s AND %s
    """, (fl_lo, fl_hi)).fetchall():
        key = frozenset((slugify_fighter(fname), slugify_fighter(oname)))
        pair_results.setdefault(key, []).append({
            "game_date": str(fl_date)[:10], "method": method,
            "end_round": end_round, "end_time_sec": end_time_sec,
            "scheduled_rounds": scheduled_rounds,
        })

    def _in_window(cand, want):
        got = datetime.strptime(cand["game_date"], "%Y-%m-%d")
        return abs((got - want).days) <= 1

    def _pair_fallback(home_team, away_team, pick_date):
        if not home_team or not away_team:
            return None
        slugs = {slugify_fighter(home_team), slugify_fighter(away_team)}
        want = datetime.strptime(str(pick_date)[:10], "%Y-%m-%d")
        for cand in pair_results.get(frozenset(slugs), []):
            if _in_window(cand, want):
                return cand
        # Unmapped name variant (Odds API vs ufcstats spelling). Mirrors the
        # anchor rule in ufc_stats_ingestor._resolve_game_rows: a fight sharing
        # exactly ONE fighter on the same date is the same bout, but only when
        # it is unambiguous — several matches mean the opponent changed, which
        # is a different proposition and must not be settled as this one.
        anchored = [cand for key, cands in pair_results.items()
                    if len(key & slugs) == 1
                    for cand in cands if _in_window(cand, want)]
        if len(anchored) == 1:
            logger.warning(
                f"UFC settle: name variant resolved by anchor for "
                f"{away_team} vs {home_team} — add the pair to "
                f"config.UFC_NAME_ALIASES."
            )
            return anchored[0]
        return None

    wins = losses = pushes = no_actions = 0
    total_flat = total_kelly = 0.0

    for (pick_id, game_id, model_id, pick_side, pick_label,
         dk_odds, rec_bet, scored_line, home_win,
         home_team, away_team, pick_game_date) in picks:

        market = _market_for_pick(model_id)
        res = (results.get(game_id)
               or _pair_fallback(home_team, away_team, pick_game_date))
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
    # Standard runline only (±1.5) for MLB/NHL — avoid alternate spread lines.
    # Basketball spreads (WNBA/NBA) are game-specific numbers, so no filter
    # there. F5 spreads use -0.5 and are prob-only (no dk_odds), so they never
    # reach this path.
    spread_filter = ("AND ABS(spread_home) = 1.5"
                     if market == "spreads"
                     and game_id.split("_", 1)[0] in ("MLB", "NHL") else "")

    if commence_time:
        row = conn.execute(f"""
            SELECT home_price, away_price, draw_price,
                   spread_home, total_line, over_price, under_price
            FROM odds
            WHERE game_id   = %s
              AND market    = %s
              AND bookmaker = 'draftkings'
              AND snapshot_type != 'in_play'
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
          AND snapshot_type != 'in_play'
          {spread_filter}
        ORDER BY snapshot_at DESC
        LIMIT 1
    """, (game_id, market)).fetchone()
    return dict(zip(cols, row)) if row else None


def _as_utc(value) -> "datetime | None":
    """Parse a stored timestamp to an aware UTC datetime, or None.

    games.commence_time is TEXT and appears as both '...Z' and '...+00:00'.
    Those two do not string-compare correctly against each other, so anything
    deciding "has this started?" must parse first.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


_PROP_MARKET_FOR_MODEL = {
    "mlb_prop_pitcher_k": "pitcher_strikeouts",
    "mlb_prop_pitcher_hits": "pitcher_hits_allowed",
    "mlb_prop_pitcher_er": "pitcher_earned_runs",
    "mlb_prop_pitcher_outs": "pitcher_outs",
    "mlb_prop_pitcher_walks": "pitcher_walks",
    "mlb_prop_batter_hits": "batter_hits",
    "mlb_prop_batter_tb": "batter_total_bases",
    "mlb_prop_batter_hr": "batter_home_runs",
    "mlb_prop_batter_rbi": "batter_rbis",
    "mlb_prop_batter_runs": "batter_runs_scored",
    "mlb_prop_batter_sb": "batter_stolen_bases",
    "mlb_prop_batter_walks": "batter_walks",
    "wnba_prop_player_points": "player_points",
    "wnba_prop_player_rebounds": "player_rebounds",
    "wnba_prop_player_assists": "player_assists",
    "wnba_prop_player_threes": "player_threes",
    "wnba_prop_player_pra": "player_points_rebounds_assists",
    "nba_prop_player_points": "player_points",
    "nba_prop_player_rebounds": "player_rebounds",
    "nba_prop_player_assists": "player_assists",
    "nba_prop_player_threes": "player_threes",
    "nba_prop_player_pra": "player_points_rebounds_assists",
    "nba_prop_player_blocks": "player_blocks",
    "nba_prop_player_steals": "player_steals",
    "nba_prop_player_turnovers": "player_turnovers",
    "nba_prop_player_dd": "player_double_double",
}


def _closing_prop_odds(conn: DBConnection, game_id: str, player_id: str,
                       market: str, commence_time: str) -> dict | None:
    """Closing DK price for one player prop: the newest pre-game snapshot.

    The prop analog of _closing_dk_odds. Bounded at commence_time for the same
    reason and using the same convention -- the evening refresh writes
    post-first-pitch snapshots as snapshot_type='open' (that is the §106 leak),
    so an unbounded "latest" would take an in-play number as the close."""
    row = conn.execute("""
        SELECT over_price, under_price, line
        FROM player_prop_odds
        WHERE game_id = %s AND player_id = %s AND market = %s
          AND bookmaker = 'draftkings'
          AND snapshot_at::timestamptz <= %s::timestamptz
        ORDER BY snapshot_at::timestamptz DESC
        LIMIT 1
    """, (game_id, player_id, market, commence_time)).fetchone()
    if not row:
        return None
    return {"over_price": row[0], "under_price": row[1], "line": row[2]}


def _capture_clv(conn: DBConnection, game_date: str, captured_at: str) -> int:
    """
    Record closing line value for each official (BET) game-level pick on game_date.

    For every BET pick that has a scored DK price but no CLV yet, find the closing
    DK price on the pick side (last pre-game snapshot) and store:
      - closing_dk_odds : closing American price on our side
      - closing_line    : closing total/spread on our side (NULL for moneyline)
      - clv_pct         : closing_implied_prob - bet_implied_prob, in pp
                          (positive = we beat the close — the line moved toward us)

    PLAYER PROPS ARE INCLUDED (2026-08-29, mike). They were skipped because
    their prices live in player_prop_odds rather than odds -- but props are the
    bulk of the settled record, so skipping them left CLV measured on 240 of
    3,422 bets (7%), and a beat-the-close rate on 7% of the book says very
    little about the book. _closing_prop_odds is the prop-side lookup.

    LIVE PICKS ARE STILL EXCLUDED, and always will be: an in-play price has no
    meaningful close to compare against. Golf too -- its prices live in
    golf_odds and a tournament has no single closing moment.

    Idempotent: only fills picks where clv_pct IS NULL. Returns picks updated.
    """
    rows = conn.execute("""
        SELECT p.pick_id, p.game_id, p.model_id, p.pick_side, p.dk_odds,
               g.commence_time, p.player_id
        FROM picks p
        JOIN games g ON p.game_id = g.game_id
        WHERE p.game_date = %s
          AND p.signal_type = 'BET'
          AND p.dk_odds IS NOT NULL
          AND p.clv_pct IS NULL
          AND p.is_live IS NOT TRUE
          AND p.model_id NOT LIKE 'golf_%%'
    """, (game_date,)).fetchall()

    if not rows:
        return 0

    now_utc = datetime.now(timezone.utc)
    updated = 0
    for (pick_id, game_id, model_id, pick_side, dk_odds, commence_time,
         player_id) in rows:
        # The game must have STARTED. _closing_dk_odds takes the newest snapshot
        # at or before kickoff, so capturing while a game is still hours away
        # records that hour's price as "the close" — and since the fill is
        # idempotent on clv_pct IS NULL, the wrong number is permanent. Harmless
        # when settlement ran once a day after midnight; load-bearing the moment
        # it runs hourly. Parsed rather than string-compared: commence_time is
        # TEXT in mixed 'Z' and '+00:00' forms, which do not sort consistently
        # against each other. Unparseable or absent -> leave for a later pass.
        ct = _as_utc(commence_time)
        if ct is None or ct > now_utc:
            continue
        prop_market = _PROP_MARKET_FOR_MODEL.get(model_id)
        if prop_market:
            if not player_id:
                continue                 # can't find the prop without the player
            market = prop_market
            closing = _closing_prop_odds(conn, game_id, player_id, prop_market,
                                         commence_time)
            closing_price = (closing or {}).get(
                "over_price" if pick_side == "over" else "under_price")
        else:
            market  = _market_for_pick(model_id)
            closing = _closing_dk_odds(conn, game_id, market, commence_time)
            price_col     = _SIDE_PRICE_COL.get(pick_side)
            closing_price = (closing or {}).get(price_col) if price_col else None
        if not closing or closing_price is None:
            continue

        bet_ip   = american_to_implied_prob(dk_odds)
        close_ip = american_to_implied_prob(closing_price)
        if bet_ip is None or close_ip is None:
            continue

        clv_pct = round((close_ip - bet_ip) * 100, 2)

        if prop_market:
            closing_line = closing.get("line")
        elif "totals" in market:
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
        # Regulation only. Undetermined regulation outcome → NO_ACTION rather
        # than a fabricated loss (a draw still settles off went_to_ot).
        if home_win_reg is None and pick_side != "draw":
            return "NO_ACTION", 0.0, 0.0
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


_NFL_MODEL_MARKETS = {
    "nfl_wind_totals": "totals",       # under vs scored_line (the card's total)
    "nfl_opener_spread": "spreads",    # scored_line = soft book's HOME spread
}

# Models removed from the registries but whose picks still live in the picks
# table. A pick that existed is the bet of record and must keep grading on the
# math it was made under (§1c) -- and grading is the ONLY thing a retired model
# still needs, which is why this is a settlement map rather than a registry
# entry. Without it these fall through to the 'h2h' default: mlb_live_runline
# picks would be graded as moneylines, silently turning a -1.5 cover into a
# win. Retired 2026-08-30, see config.LIVE_MODELS.
_RETIRED_MODEL_MARKETS = {
    "mlb_live_win_prob": "h2h",
    "mlb_live_runline":  "spreads",
}


def _market_for_pick(model_id: str) -> str:
    """Map model_id to its odds market key (pre-game and live registries)."""
    if model_id in _RETIRED_MODEL_MARKETS:
        return _RETIRED_MODEL_MARKETS[model_id]
    if model_id in _NFL_MODEL_MARKETS:
        # The standalone NFL card models (§28) — not in MODELS (never trained
        # by the platform), but their picks settle on the standard totals/
        # spreads math: games scores vs the pick's scored_line. Without this
        # they would fall to 'h2h' and stamp NO_ACTION.
        return _NFL_MODEL_MARKETS[model_id]
    if model_id in MODELS:
        return MODELS[model_id][1]
    if model_id in LIVE_MODELS:
        # Live picks settle on the same final-score math as their pre-game
        # counterparts: h2h vs home_win, totals vs scored_line (the in-play
        # line at pick time), spreads vs the -1.5 runline.
        return LIVE_MODELS[model_id][1]
    return "h2h"


# ── Settler ───────────────────────────────────────────────────────────────────

# Game finals can land after the morning settle (WNBA/NBA scores come from the
# local Basketball Daily Ingest, which may run late or catch up after days
# off), and settle_picks only runs for game_date = yesterday — a trailing
# window lets late-arriving finals settle game-level picks on subsequent
# mornings instead of lingering unsettled forever. Mirrors
# _PROP_SETTLE_WINDOW_DAYS.
_GAME_SETTLE_WINDOW_DAYS = 14


def _settle_game_picks(
    conn: DBConnection,
    game_date: str,
    settled_at: str,
) -> tuple[int, int, int, int, float, float]:
    """
    Settle all unsettled game-level BET picks (moneyline, O/U, runline, F5,
    3-way) for game_date where the game has a final score.

    Prop picks (mlb_prop_% / wnba_prop_% / nba_prop_%) are settled separately —
    _market_for_pick falls back to 'h2h' for unknown model_ids, which would
    stamp over/under prop picks as NO_ACTION and permanently block
    _settle_prop_picks (it only touches result IS NULL rows).
    UFC picks are also settled separately — under the UFC score convention
    (home_score = 1/0 win indicator) the generic totals math would be
    meaningless. Golf picks settle from golf_rounds.

    Returns (wins, losses, pushes, no_actions, total_flat, total_kelly).
    """
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
          AND p.model_id NOT LIKE 'nba_prop_%%'
          AND p.model_id NOT LIKE 'ufc_%%'
          AND p.model_id NOT LIKE 'golf_%%'
          AND g.home_score IS NOT NULL
    """, (game_date,)).fetchall()

    if not picks:
        return 0, 0, 0, 0, 0.0, 0.0

    logger.info(f"Found {len(picks)} unsettled game picks for {game_date}")

    wins = losses = pushes = no_actions = 0
    total_profit_flat  = 0.0
    total_profit_kelly = 0.0

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

    return wins, losses, pushes, no_actions, total_profit_flat, total_profit_kelly


def _settle_game_picks_window(
    conn: DBConnection,
    game_date: str,
    settled_at: str,
) -> tuple[int, int, int, int, float, float]:
    """
    Settle unsettled game-level BET picks for game_date and the trailing
    window before it. Dates with no unsettled game picks return immediately.
    """
    totals = [0, 0, 0, 0, 0.0, 0.0]
    end = datetime.strptime(game_date, "%Y-%m-%d")
    for offset in range(_GAME_SETTLE_WINDOW_DAYS):
        d = (end - timedelta(days=offset)).strftime("%Y-%m-%d")
        day_results = _settle_game_picks(conn, d, settled_at)
        for i, v in enumerate(day_results):
            totals[i] += v
    return tuple(totals)


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
        # Fetch + store final scores over a TRAILING WINDOW (not just game_date) so
        # a day the settle missed (pipeline hiccup, late finals) still gets scored
        # and self-heals — otherwise its picks / opening signals / parlays stay
        # pending forever for lack of a score.
        _base = datetime.strptime(game_date, "%Y-%m-%d")
        for _i in range(5):
            _d = (_base - timedelta(days=_i)).strftime("%Y-%m-%d")
            try:
                _fetch_and_store_scores(conn, _d)
            except Exception as _exc:
                logger.warning(f"score fetch {_d} failed: {_exc}")
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

        # ── Game-level picks (moneyline, O/U, runline, F5 ML, 3-way) ──────
        # Trailing window so finals that land after a morning settle (WNBA/NBA
        # scores arrive via the local Basketball Daily Ingest, which can run
        # late or catch up after days off) still settle on subsequent mornings.
        gm_wins, gm_losses, gm_pushes, gm_no_actions, gm_flat, gm_kelly = (
            _settle_game_picks_window(conn, game_date, settled_at)
        )
        wins       += gm_wins
        losses     += gm_losses
        pushes     += gm_pushes
        no_actions += gm_no_actions
        total_profit_flat  += gm_flat
        total_profit_kelly += gm_kelly

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

        # ── Opening-signal shadow track (game-level) ──────────────────────
        # Settled independently and NOT folded into the live totals above —
        # this is a parallel record for comparing "lock the open" vs "chase
        # the live line", so the published live record stays untouched.
        from tracking.opening_signals import settle_opening_signals
        settle_opening_signals(conn, game_date, settled_at)

        # ── Public parlay track record (game-level, built on opening signals) ──
        # Settle AFTER opening signals so the parlay legs already have results.
        # Also a shadow record — not folded into the live totals.
        from tracking.parlay_track_record import settle_parlay_track_record
        settle_parlay_track_record(conn, game_date, settled_at)

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
    logger.info(f"  RESULTS SUMMARY (last {days} days)")
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
    parser = argparse.ArgumentParser(description="Result settler")
    parser.add_argument("--date",    help="Game date to settle YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--summary", action="store_true", help="Print P&L summary")
    parser.add_argument("--days",    type=int, default=30, help="Days for summary")
    args = parser.parse_args()

    if args.summary:
        print_performance_summary(days=args.days)
    else:
        result = settle_picks(game_date=args.date)
        logger.info(f"Done: {result}")
