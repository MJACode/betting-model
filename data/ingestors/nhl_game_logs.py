"""Per-game NHL logs — team, goalie and skater — from the NHL's free stats API.

Tables and the reason they exist: data/migrations/add_nhl_game_logs.sql.

WHAT IS PULLED. `api.nhle.com/stats/rest/en/<entity>/<report>?isGame=true`
returns one row per entity per game. Measured 2026-09-20 on season 2024-25:

    team/summary, realtime, percentages, powerplay, penaltykill   2,624 rows each
    goalie/summary                                                 2,764 rows
    skater/summary, realtime, timeonice                            CAPPED at 10,000

Team and goalie reports come back whole in one call per season. The skater
reports stop at 10,000 rows whatever `limit` says — a season is ~47,000 — so
they are pulled a WEEK at a time and the pull REFUSES any window that comes
back at the cap, because a capped window is a silently truncated one.

No key, no credits. Everything lands in Supabase, keyed on `source`
(`nhl_stats_api|season=<id>|type=<n>`), and a season whose rows are already
stored is skipped unless --force.

    python -m data.ingestors.nhl_game_logs --seasons 2019 2026            # dry run
    python -m data.ingestors.nhl_game_logs --seasons 2019 2026 --apply
    python -m data.ingestors.nhl_game_logs --recent 5 --apply            # daily top-up
"""
from __future__ import annotations

import argparse
import time
from datetime import date, timedelta

import requests
from loguru import logger

from data.db import DBConnection, get_connection
from data.ingestors.nhl_stats_ingestor import (NHL_HEADERS, NHL_STATS_BASE,
                                               _nhl_season_id, _norm_nhl)

ROW_CAP = 10_000            # the API's hard ceiling per call, measured
SKATER_WINDOW_DAYS = 7
GAME_TYPES = (2, 3)         # regular season, playoffs
PAUSE = 0.3
WRITE_BATCH = 2_000


# ── transport ────────────────────────────────────────────────────────────────

def _fetch(report: str, expr: str) -> list[dict]:
    """Every row of one per-game report. Raises rather than return a capped page."""
    resp = requests.get(
        f"{NHL_STATS_BASE}/{report}",
        params={"isGame": "true", "cayenneExp": expr, "limit": -1},
        headers=NHL_HEADERS, timeout=90)
    resp.raise_for_status()
    body = resp.json()
    rows = body.get("data", [])
    if len(rows) >= ROW_CAP or (body.get("total") or 0) >= ROW_CAP:
        raise RuntimeError(
            f"{report} [{expr}] came back at the {ROW_CAP:,}-row cap — the window "
            f"is truncated. Narrow it.")
    time.sleep(PAUSE)
    return rows


def _season_expr(season: int, game_type: int) -> str:
    return f"gameTypeId={game_type} and seasonId={_nhl_season_id(season)}"


def _windows(first: str, last: str, days: int = SKATER_WINDOW_DAYS):
    d, end = date.fromisoformat(first), date.fromisoformat(last)
    while d <= end:
        hi = min(d + timedelta(days=days - 1), end)
        yield d.isoformat(), hi.isoformat()
        d = hi + timedelta(days=1)


# ── row builders (pure: tested without a network or a database) ──────────────

def _game_key(row: dict) -> tuple[str, str, str, int]:
    """(our game_id, team, opponent, is_home) for any per-game API row."""
    team = _norm_nhl(row.get("teamAbbrev") or "")
    opp = _norm_nhl(row.get("opponentTeamAbbrev") or "")
    is_home = int((row.get("homeRoad") or "").upper() == "H")
    game_date = (row.get("gameDate") or "")[:10]
    home, away = (team, opp) if is_home else (opp, team)
    return f"NHL_{game_date}_{away}_{home}", team, opp, is_home


def _int(v):
    return None if v is None else int(round(float(v)))


def build_team_rows(summary: list[dict], realtime: list[dict], pct: list[dict],
                    powerplay: list[dict], penaltykill: list[dict],
                    team_abbrev: dict[int, str], season: int, game_type: int,
                    source: str, shooting: list[dict] | None = None) -> list[dict]:
    """One row per team-game. The team reports carry `teamId`, not an abbrev,
    and no opponent shot attempts — that is the OTHER team's row in the same
    game, so it is joined here rather than left to every reader."""
    def by_key(rows):
        return {(r["gameId"], r["teamId"]): r for r in rows}
    rt, pc, pp, pk = by_key(realtime), by_key(pct), by_key(powerplay), by_key(penaltykill)
    sh = by_key(shooting or [])

    out: dict[tuple[int, str], dict] = {}
    for s in summary:
        k = (s["gameId"], s["teamId"])
        team = _norm_nhl(team_abbrev.get(s["teamId"], ""))
        opp = _norm_nhl(s.get("opponentTeamAbbrev") or "")
        if not team or not opp:
            continue
        is_home = int((s.get("homeRoad") or "").upper() == "H")
        game_date = (s.get("gameDate") or "")[:10]
        home, away = (team, opp) if is_home else (opp, team)
        r, c, p, q = rt.get(k, {}), pc.get(k, {}), pp.get(k, {}), pk.get(k, {})
        out[(s["gameId"], team)] = {
            "nhl_game_id": s["gameId"], "team": team,
            "game_id": f"NHL_{game_date}_{away}_{home}",
            "season": season, "game_type": game_type, "game_date": game_date,
            "opponent": opp, "is_home": is_home,
            "goals_for": _int(s.get("goalsFor")), "goals_against": _int(s.get("goalsAgainst")),
            "shots_for": _int(s.get("shotsForPerGame")),
            "shots_against": _int(s.get("shotsAgainstPerGame")),
            "shot_attempts_for": _int(r.get("totalShotAttempts")),
            "shot_attempts_against": None,
            # `totalShotAttempts` is NULL before 2022-23 (measured); the 5v5
            # counts in team/summaryshooting go back the whole way.
            "sat_for_5v5": _int(sh.get(k, {}).get("satFor")),
            "sat_against_5v5": _int(sh.get(k, {}).get("satAgainst")),
            "sat_pct_5v5": c.get("satPct"),
            "pp_opportunities": _int(p.get("ppOpportunities")),
            "pp_goals": _int(p.get("powerPlayGoalsFor")),
            "times_shorthanded": _int(q.get("timesShorthanded")),
            "pp_goals_against": _int(q.get("ppGoalsAgainst")),
            "faceoff_win_pct": s.get("faceoffWinPct"),
            "hits": _int(r.get("hits")), "blocked_shots": _int(r.get("blockedShots")),
            "giveaways": _int(r.get("giveaways")), "takeaways": _int(r.get("takeaways")),
            "source": source,
        }
    for (gid, team), row in out.items():
        other = out.get((gid, row["opponent"]))
        if other:
            row["shot_attempts_against"] = other["shot_attempts_for"]
    return list(out.values())


def build_goalie_rows(summary: list[dict], season: int, game_type: int,
                      source: str) -> list[dict]:
    out = []
    for g in summary:
        game_id, team, opp, is_home = _game_key(g)
        if not team or not opp or not g.get("playerId"):
            continue
        decision = ("W" if g.get("wins") else "L" if g.get("losses")
                    else "OTL" if g.get("otLosses") else None)
        out.append({
            "nhl_game_id": g["gameId"], "player_id": g["playerId"],
            "player_name": g.get("goalieFullName") or "",
            "game_id": game_id, "season": season, "game_type": game_type,
            "game_date": (g.get("gameDate") or "")[:10],
            "team": team, "opponent": opp, "is_home": is_home,
            "started": int(bool(g.get("gamesStarted"))),
            "decision": decision,
            "toi_seconds": _int(g.get("timeOnIce")),
            "shots_against": _int(g.get("shotsAgainst")),
            "saves": _int(g.get("saves")),
            "goals_against": _int(g.get("goalsAgainst")),
            "source": source,
        })
    return out


def build_skater_rows(summary: list[dict], realtime: list[dict], toi: list[dict],
                      season: int, game_type: int, source: str) -> list[dict]:
    def by_key(rows):
        return {(r["gameId"], r["playerId"]): r for r in rows}
    rt, ti = by_key(realtime), by_key(toi)
    out = []
    for s in summary:
        game_id, team, opp, is_home = _game_key(s)
        if not team or not opp or not s.get("playerId"):
            continue
        k = (s["gameId"], s["playerId"])
        r, t = rt.get(k, {}), ti.get(k, {})
        out.append({
            "nhl_game_id": s["gameId"], "player_id": s["playerId"],
            "player_name": s.get("skaterFullName") or "",
            "position": s.get("positionCode"),
            "game_id": game_id, "season": season, "game_type": game_type,
            "game_date": (s.get("gameDate") or "")[:10],
            "team": team, "opponent": opp, "is_home": is_home,
            "goals": _int(s.get("goals")), "assists": _int(s.get("assists")),
            "points": _int(s.get("points")), "shots": _int(s.get("shots")),
            "shot_attempts": _int(r.get("totalShotAttempts")),
            "missed_shots": _int(r.get("missedShots")),
            "pp_goals": _int(s.get("ppGoals")), "pp_points": _int(s.get("ppPoints")),
            "plus_minus": _int(s.get("plusMinus")), "pim": _int(s.get("penaltyMinutes")),
            "hits": _int(r.get("hits")), "blocked_shots": _int(r.get("blockedShots")),
            "toi_seconds": _int(t.get("timeOnIce") if t else s.get("timeOnIcePerGame")),
            "ev_toi_seconds": _int(t.get("evTimeOnIce")),
            "pp_toi_seconds": _int(t.get("ppTimeOnIce")),
            "sh_toi_seconds": _int(t.get("shTimeOnIce")),
            "shifts": _int(t.get("shifts")),
            "source": source,
        })
    return out


# ── writers ──────────────────────────────────────────────────────────────────

def _upsert(conn: DBConnection, table: str, key: tuple[str, ...], rows: list[dict]) -> int:
    if not rows:
        return 0
    cols = list(rows[0])
    sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in key)
    sql = (f"INSERT INTO {table} ({', '.join(cols)}) "
           f"VALUES ({', '.join(f'%({c})s' for c in cols)}) "
           f"ON CONFLICT ({', '.join(key)}) DO UPDATE SET {sets}, fetched_at = NOW()")
    # COMMIT PER BATCH. One 47,000-row skater season in a single transaction
    # lost the connection mid-write on the first real run (2026-09-20) and the
    # whole season was discarded. A batch that loses its connection is retried
    # once on the reconnected handle; the upsert makes that safe.
    from data.db import ConnectionLost
    for i in range(0, len(rows), WRITE_BATCH):
        chunk = rows[i:i + WRITE_BATCH]
        try:
            conn.executemany(sql, chunk)
            conn.commit()
        except ConnectionLost:
            logger.warning(f"{table}: connection lost at row {i:,} — retrying the batch")
            conn.executemany(sql, chunk)
            conn.commit()
    return len(rows)


def _stored(conn: DBConnection, table: str, source: str) -> int:
    return conn.execute(f"SELECT count(*) FROM {table} WHERE source = ?",
                        (source,)).fetchone()[0]


def _team_abbrevs() -> dict[int, str]:
    """teamId -> triCode. The per-game TEAM reports name a team only by id."""
    resp = requests.get(f"{NHL_STATS_BASE}/team", headers=NHL_HEADERS, timeout=30)
    resp.raise_for_status()
    return {t["id"]: t.get("triCode") or "" for t in resp.json().get("data", [])}


# ── the pulls ────────────────────────────────────────────────────────────────

def load_window(conn: DBConnection | None, season: int, game_type: int,
                first: str | None, last: str | None, source: str,
                team_abbrev: dict[int, str], apply: bool,
                skaters_too: bool = True) -> dict:
    """Team, goalie and skater logs for one season+type, optionally one date range."""
    base = _season_expr(season, game_type)
    rng = (f' and gameDate>="{first}" and gameDate<="{last} 23:59:59"'
           if first and last else "")
    team = build_team_rows(
        _fetch("team/summary", base + rng), _fetch("team/realtime", base + rng),
        _fetch("team/percentages", base + rng), _fetch("team/powerplay", base + rng),
        _fetch("team/penaltykill", base + rng), team_abbrev, season, game_type, source,
        shooting=_fetch("team/summaryshooting", base + rng))
    goalies = build_goalie_rows(_fetch("goalie/summary", base + rng),
                                season, game_type, source)
    if not team:
        return {"team": 0, "goalie": 0, "skater": 0}

    lo = first or min(r["game_date"] for r in team)
    hi = last or max(r["game_date"] for r in team)
    skaters: list[dict] = []
    for a, b in (_windows(lo, hi) if skaters_too else ()):
        w = f' and gameDate>="{a}" and gameDate<="{b} 23:59:59"'
        skaters += build_skater_rows(
            _fetch("skater/summary", base + w), _fetch("skater/realtime", base + w),
            _fetch("skater/timeonice", base + w), season, game_type, source)

    if apply and conn is not None:
        # TEAM ROWS LAST: they are the completion marker `backfill` reads. Writes
        # are committed per batch, so a run that dies half-way leaves skaters
        # with no team rows, and the next run does that season again.
        _upsert(conn, "nhl_skater_game_log", ("nhl_game_id", "player_id"), skaters)
        _upsert(conn, "nhl_goalie_game_log", ("nhl_game_id", "player_id"), goalies)
        _upsert(conn, "nhl_team_game_log", ("nhl_game_id", "team"), team)
    return {"team": len(team), "goalie": len(goalies), "skater": len(skaters)}


def _complete(conn: DBConnection, source: str, skaters_too: bool) -> bool:
    """A season+type is done when its team rows exist and (if wanted) its
    skater log covers the same number of games."""
    games = conn.execute("SELECT count(DISTINCT nhl_game_id) FROM nhl_team_game_log "
                         "WHERE source = ?", (source,)).fetchone()[0]
    if not games:
        return False
    if not skaters_too:
        return True
    sk = conn.execute("SELECT count(DISTINCT nhl_game_id) FROM nhl_skater_game_log "
                      "WHERE source = ?", (source,)).fetchone()[0]
    return sk >= games


def backfill(seasons: list[int], apply: bool, force: bool = False,
             skaters_too: bool = True) -> None:
    conn = get_connection()
    try:
        team_abbrev = _team_abbrevs()
        for season in seasons:
            for gt in GAME_TYPES:
                source = f"nhl_stats_api|season={_nhl_season_id(season)}|type={gt}"
                if not force and _complete(conn, source, skaters_too):
                    logger.info(f"{source}: already stored — skipped")
                    continue
                n = load_window(conn, season, gt, None, None, source, team_abbrev,
                                apply, skaters_too)
                logger.success(f"{source}: {n}" + ("" if apply else "  (dry run)"))
    finally:
        conn.close()


def top_up(days: int, apply: bool, today: str | None = None) -> dict:
    """The daily job: re-pull the trailing `days` days of the current season."""
    from data.season_labels import nhl_season_label
    end = date.fromisoformat(today) if today else date.today()
    first, last = (end - timedelta(days=days)).isoformat(), end.isoformat()
    season = nhl_season_label(last)
    conn = get_connection()
    total = {"team": 0, "goalie": 0, "skater": 0}
    try:
        team_abbrev = _team_abbrevs()
        for gt in GAME_TYPES:
            source = f"nhl_stats_api|season={_nhl_season_id(season)}|type={gt}"
            n = load_window(conn, season, gt, first, last, source, team_abbrev, apply)
            for k in total:
                total[k] += n[k]
    finally:
        conn.close()
    logger.success(f"NHL game logs {first}..{last}: {total}")
    return total


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seasons", nargs=2, type=int, metavar=("START", "END"))
    ap.add_argument("--recent", type=int, metavar="DAYS")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-skaters", action="store_true",
                    help="team and goalie logs only (minutes, not an hour)")
    a = ap.parse_args()
    if a.seasons:
        backfill(list(range(a.seasons[0], a.seasons[1] + 1)), a.apply, a.force,
                 skaters_too=not a.no_skaters)
    elif a.recent:
        top_up(a.recent, a.apply)
    else:
        ap.error("give --seasons START END or --recent DAYS")
