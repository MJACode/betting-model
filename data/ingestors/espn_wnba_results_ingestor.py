"""
espn_wnba_results_ingestor.py — WNBA final-score self-heal via ESPN's hidden API.

WHY THIS EXISTS:
Final scores + player box scores normally come from nba_api (wnba_stats_ingestor.py),
which requires stats.nba.com and only reliably works from Matt's local machine
("Basketball Daily Ingest" Task Scheduler job) — stats.nba.com blocks GitHub Actions
datacenter IPs. When that local job misses a day, WNBA `games` rows sit with NULL
home_score/away_score indefinitely: game-level picks (wnba_moneyline) never settle
and the daily system health check flags "final_scores" WARN for WNBA.

This module is a narrow, GitHub-Actions-reachable FALLBACK. It only fills
games.home_score / away_score / home_win for WNBA games that are still NULL, using
ESPN's public scoreboard endpoint (site.api.espn.com — the same host already used
for injuries and confirmed reachable from Actions; see injury_ingestor.py). It never
overwrites a row nba_api already populated (every write is WHERE home_score IS NULL).

IMPORTANT SCOPE LIMIT — this does NOT settle player props:
ESPN's athlete/player ids are a different id space from nba_api's numeric
PLAYER_ID, which `picks.player_id` and `_load_wnba_prop_actuals` are keyed to.
Inserting ESPN-sourced rows into wnba_player_game_log would either never match
existing picks, or (worse) create duplicate rows for the same real player once the
local job eventually lands the same game under nba_api's ids. So this ingestor
intentionally touches ONLY `games` — WNBA prop settlement still depends on the
local job catching up. Game-level (moneyline) picks settle automatically once
games.home_score is filled — no other code changes needed (paper_tracker's
trailing-window settle already reads games.home_score for every sport).

Endpoint shape is ESPN's standard "site.api" scoreboard contract (used across all
of their sports products) but has NOT been exercised against a live response from
this dev environment — ESPN is not reachable from the sandbox allowlist. Parsing is
defensive: any event/team that doesn't match the expected shape is logged and
skipped rather than raising, so a field-name surprise can't break the pipeline.
If the first live run logs shape warnings, fix the parsing here (isolated, one
function).

Usage:
    python -m data.ingestors.espn_wnba_results_ingestor                 # trailing 8-day window ending yesterday
    python -m data.ingestors.espn_wnba_results_ingestor --date 2026-07-05
    python -m data.ingestors.espn_wnba_results_ingestor --window 14
"""

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import WNBA_ODDS_API_MAP
from data.db import get_connection, DBConnection

# ── Constants ─────────────────────────────────────────────────────────────────

ESPN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

ESPN_WNBA_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard"

# Same convention as odds_ingestor / sbr_loader / wnba_stats_ingestor.
_GAME_ID_PREFIX = "WNBA"


def _normalize_team_name(name: str) -> str:
    return " ".join((name or "").lower().split())


# Full team name → our 3-letter abbrev, built from the odds-API map (covers all
# 15 franchises incl. expansion teams). Same pattern as injury_ingestor.py's
# ESPN team resolution — join on name, never hardcode ESPN's own abbrev scheme.
_WNBA_NAME_TO_ABBREV = {
    _normalize_team_name(full): abbrev for full, abbrev in WNBA_ODDS_API_MAP.items()
}


def _espn_team_to_abbrev(team: dict) -> str | None:
    """Resolve one ESPN competitor's team object to our 3-letter abbrev via name."""
    candidates = [
        team.get("displayName"),
        f"{team.get('location', '')} {team.get('name', '')}".strip(),
        team.get("shortDisplayName"),
        team.get("name"),
    ]
    for cand in candidates:
        abbrev = _WNBA_NAME_TO_ABBREV.get(_normalize_team_name(cand))
        if abbrev:
            return abbrev
    return None


def _build_game_id(game_date: str, away: str, home: str) -> str:
    """Same format as odds_ingestor / wnba_stats_ingestor: WNBA_{date}_{away}_{home}."""
    return f"{_GAME_ID_PREFIX}_{game_date}_{away}_{home}"


# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_scoreboard(game_date: str) -> dict:
    """game_date: YYYY-MM-DD. Returns parsed JSON, or {} on any failure."""
    espn_date = game_date.replace("-", "")
    try:
        resp = requests.get(
            ESPN_WNBA_SCOREBOARD_URL,
            params={"dates": espn_date},
            headers=ESPN_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning(f"ESPN WNBA scoreboard fetch failed for {game_date}: {exc}")
        return {}


# ── Parse ─────────────────────────────────────────────────────────────────────

def parse_scoreboard(data: dict, game_date: str) -> list[dict]:
    """
    Returns completed games as [{game_id, home_team, away_team, home_score,
    away_score, home_win}]. Any event that doesn't resolve cleanly (unknown
    team, missing score, unexpected shape) is skipped with a warning instead
    of raising — a single bad event must never take down the whole run.
    """
    out = []
    events = data.get("events", []) if isinstance(data, dict) else []
    for ev in events:
        try:
            comps = ev.get("competitions") or []
            if not comps:
                continue
            comp = comps[0]
            status_type = (comp.get("status") or {}).get("type") or {}
            if not status_type.get("completed"):
                continue  # in-progress / scheduled — nothing to settle yet

            home = away = None
            for c in comp.get("competitors") or []:
                abbrev = _espn_team_to_abbrev(c.get("team") or {})
                if not abbrev:
                    logger.warning(
                        f"ESPN WNBA {game_date}: unresolved team "
                        f"{(c.get('team') or {}).get('displayName')!r} — skipping event"
                    )
                    home = away = None
                    break
                try:
                    score = int(c.get("score"))
                except (TypeError, ValueError):
                    score = None
                if c.get("homeAway") == "home":
                    home = (abbrev, score)
                elif c.get("homeAway") == "away":
                    away = (abbrev, score)

            if not home or not away or home[1] is None or away[1] is None:
                continue

            home_abbrev, home_score = home
            away_abbrev, away_score = away
            out.append({
                "game_id":    _build_game_id(game_date, away_abbrev, home_abbrev),
                "home_team":  home_abbrev,
                "away_team":  away_abbrev,
                "home_score": home_score,
                "away_score": away_score,
                "home_win":   1 if home_score > away_score else 0,
            })
        except Exception as exc:
            logger.warning(f"ESPN WNBA {game_date}: skipping malformed event ({exc})")
            continue
    return out


# ── DB writer ─────────────────────────────────────────────────────────────────

def _fill_missing_scores(conn: DBConnection, game_date: str, rows: list[dict]) -> int:
    """
    Fills games.home_score/away_score/home_win ONLY where they are currently
    NULL — this must never overwrite nba_api's data. Matches on game_id alone;
    a game_id with no existing row is left alone (ESPN doesn't carry enough
    fields to safely construct a whole games row — commence_time, venue, etc.
    come from odds_ingestor / wnba_stats_ingestor).

    Returns the number of rows actually filled, measured via a before/after
    COUNT rather than cursor.rowcount — the DBConnection wrapper doesn't
    reliably expose rowcount (see CLAUDE.md session 11).
    """
    if not rows:
        return 0

    def _missing_count() -> int:
        row = conn.execute(
            "SELECT COUNT(*) FROM games WHERE sport = 'WNBA' AND game_date = %s AND home_score IS NULL",
            (game_date,),
        ).fetchone()
        return row[0] if row else 0

    before = _missing_count()
    for row in rows:
        conn.execute(
            """
            UPDATE games SET
                home_score = %(home_score)s,
                away_score = %(away_score)s,
                home_win   = %(home_win)s,
                updated_at = NOW()::TEXT
            WHERE game_id = %(game_id)s
              AND sport = 'WNBA'
              AND home_score IS NULL
            """,
            row,
        )
    after = _missing_count()
    return max(before - after, 0)


# ── Main entry point ─────────────────────────────────────────────────────────

def ingest_espn_wnba_results_for_date(game_date: str, window_days: int = 8) -> int:
    """
    Self-heal any WNBA games in the trailing `window_days` (ending game_date,
    inclusive) still missing a final score. Safe to call unconditionally —
    days nba_api already filled just update 0 rows. Returns total rows filled.
    """
    conn = get_connection()
    total = 0
    try:
        base = datetime.strptime(game_date, "%Y-%m-%d")
        for offset in range(window_days):
            d = (base - timedelta(days=offset)).strftime("%Y-%m-%d")
            data = fetch_scoreboard(d)
            rows = parse_scoreboard(data, d)
            n = _fill_missing_scores(conn, d, rows)
            total += n
            if n:
                logger.info(f"ESPN WNBA results {d}: filled {n} missing score(s)")
        conn.commit()
        if total:
            logger.success(
                f"ESPN WNBA results: {total} final score(s) filled "
                f"(window {window_days}d back from {game_date})"
            )
        else:
            logger.info("ESPN WNBA results: no missing scores in window (or no games)")
    except Exception as exc:
        conn.rollback()
        logger.error(f"ESPN WNBA results ingest failed: {exc}")
    finally:
        conn.close()
    return total


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ESPN WNBA final-score self-heal")
    parser.add_argument("--date", help="Anchor date YYYY-MM-DD (default: today)")
    parser.add_argument("--window", type=int, default=8,
                        help="Trailing window in days, ending at --date (default 8)")
    args = parser.parse_args()

    anchor = args.date or date.today().isoformat()
    result = ingest_espn_wnba_results_for_date(anchor, window_days=args.window)
    logger.info(f"Done: {result} score(s) filled")
