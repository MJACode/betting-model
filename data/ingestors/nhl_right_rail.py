"""Officials and healthy scratches from the league's game right rail.

Personal, non-commercial. Not a pick input.

    https://api-web.nhle.com/v1/gamecenter/{id}/right-rail

Measured 2026-11-26 on game 2026020386: `gameInfo.referees` and
`gameInfo.linesmen` are names and sweater numbers, and each side's
`scratches` are player id and name. The side does not carry its own
abbrev; home and away come from nhl_team_game_log.

A game that already has an official row is not fetched again. A final
with no officials is left unstored so the next run tries it.

    python -m data.ingestors.nhl_right_rail --daily --apply
    python -m data.ingestors.nhl_right_rail --backfill --apply
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from loguru import logger

from data.db import ConnectionLost, get_connection
from data.ingestors.nhl_completed_games import completed_games, season_span, stored_ids
from data.ingestors.nhl_polite_http import FetchFailed, get_json
from data.ingestors.nhl_stats_ingestor import NHL_API_BASE

SOURCE = "nhl_api"
PAUSE_S = 0.6

OFFICIAL_COLS = (
    "nhl_game_id", "role", "slot", "full_name", "sweater_number",
    "season_end", "game_type", "game_date", "our_game_id",
    "home_abbr", "away_abbr", "source",
)
OFFICIAL_PK = ("nhl_game_id", "role", "slot")
SCRATCH_COLS = (
    "nhl_game_id", "player_id", "team_abbr", "side", "player_name",
    "season_end", "game_type", "game_date", "our_game_id", "source",
)
SCRATCH_PK = ("nhl_game_id", "player_id")


def rail_url(gid: int) -> str:
    return f"{NHL_API_BASE}/gamecenter/{int(gid)}/right-rail"


def _name(node) -> str | None:
    if isinstance(node, dict):
        default = node.get("default")
        if isinstance(default, str) and default.strip():
            return default.strip()
    if isinstance(node, str) and node.strip():
        return node.strip()
    return None


def _person(node) -> str | None:
    if not isinstance(node, dict):
        return None
    full = _name(node.get("fullName"))
    if full:
        return full
    first = _name(node.get("firstName")) or ""
    last = _name(node.get("lastName")) or ""
    name = f"{first} {last}".strip()
    return name or None


def parse_right_rail(body: dict, meta: dict) -> tuple[list[dict], list[dict]]:
    """(officials, scratches). Officials are empty when the feed has none."""
    info = (body or {}).get("gameInfo") or {}
    base = {
        "nhl_game_id": int(meta["nhl_game_id"]),
        "season_end": int(meta["season_end"]),
        "game_type": int(meta["game_type"]),
        "game_date": meta.get("game_date"),
        "our_game_id": meta.get("our_game_id"),
        "home_abbr": meta.get("home_abbr"),
        "away_abbr": meta.get("away_abbr"),
        "source": SOURCE,
    }
    officials = []
    for role, key in (("referee", "referees"), ("linesman", "linesmen")):
        for slot, node in enumerate(info.get(key) or [], start=1):
            name = _person(node)
            if not name:
                continue
            sweater = node.get("sweaterNumber") if isinstance(node, dict) else None
            officials.append({
                **base,
                "role": role,
                "slot": slot,
                "full_name": name,
                "sweater_number": int(sweater) if sweater is not None else None,
            })
    scratches = []
    seen = set()
    for side, key, team_key in (
        ("away", "awayTeam", "away_abbr"),
        ("home", "homeTeam", "home_abbr"),
    ):
        block = info.get(key) or {}
        for node in block.get("scratches") or []:
            if not isinstance(node, dict) or node.get("id") is None:
                continue
            pid = int(node["id"])
            if pid in seen:
                continue
            seen.add(pid)
            scratches.append({
                "nhl_game_id": base["nhl_game_id"],
                "player_id": pid,
                "team_abbr": meta.get(team_key),
                "side": side,
                "player_name": _person(node),
                "season_end": base["season_end"],
                "game_type": base["game_type"],
                "game_date": base["game_date"],
                "our_game_id": base["our_game_id"],
                "source": SOURCE,
            })
    return officials, scratches


def _insert_sql(table: str, cols: tuple[str, ...], pk: tuple[str, ...]) -> str:
    sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in pk)
    return (
        f"INSERT INTO {table} ({', '.join(cols)}) "
        f"VALUES ({', '.join(f'%({c})s' for c in cols)}) "
        f"ON CONFLICT ({', '.join(pk)}) DO UPDATE SET {sets}, fetched_at = NOW()"
    )


_OFF_SQL = _insert_sql("nhl_game_officials", OFFICIAL_COLS, OFFICIAL_PK)
_SCR_SQL = _insert_sql("nhl_healthy_scratches", SCRATCH_COLS, SCRATCH_PK)


def _write_game(conn, officials: list[dict], scratches: list[dict]) -> None:
    def once():
        conn.executemany(_OFF_SQL, officials)
        if scratches:
            conn.executemany(_SCR_SQL, scratches)
        conn.commit()

    try:
        once()
    except ConnectionLost:
        logger.warning("connection lost mid-game — re-running it")
        once()


def run(run_date: str, apply: bool, backfill: bool = False,
        limit: int | None = None, pause_s: float = PAUSE_S, get=get_json) -> dict:
    first, last = season_span(run_date, backfill)
    conn = get_connection()
    failed: dict[int, str] = {}
    games_done = scratches = 0
    try:
        games, odd = completed_games(conn, first, last)
        have = stored_ids(conn, "nhl_game_officials") if apply else set()
        todo = [g for g in games if g["nhl_game_id"] not in have]
        if limit:
            todo = todo[:limit]
        logger.info(
            f"NHL right rail {first}-{last}: {len(games):,} played, "
            f"{len(have):,} stored, {len(todo):,} to fetch, {len(odd)} odd log rows")
        if not apply:
            return {"ok": True, "games": len(todo), "rows": 0, "failed": {},
                    "seasons": (first, last), "downloaded": False}
        for meta in todo:
            gid = meta["nhl_game_id"]
            try:
                body = get(rail_url(gid))
            except FetchFailed as exc:
                failed[gid] = str(exc)
                logger.warning(f"{gid}: {exc}")
                time.sleep(pause_s)
                continue
            officials, scratch_rows = parse_right_rail(body, meta)
            if not officials:
                failed[gid] = "no officials"
                logger.warning(f"{gid}: no officials")
                time.sleep(pause_s)
                continue
            _write_game(conn, officials, scratch_rows)
            games_done += 1
            scratches += len(scratch_rows)
            if games_done % 25 == 0:
                logger.info(f"{games_done:,} games, {scratches:,} scratches")
            time.sleep(pause_s)
    finally:
        conn.close()
    ok = not failed
    if ok:
        logger.success(f"NHL right rail: {games_done:,} games, {scratches:,} scratches")
    else:
        logger.error(f"NHL right rail: {len(failed)} games not stored "
                     f"(first {list(failed)[:5]}); {games_done:,} games were written")
    return {"ok": ok, "games": games_done, "rows": games_done,
            "scratches": scratches, "failed": failed, "seasons": (first, last)}


def daily(run_date: str, apply: bool) -> dict:
    return run(run_date, apply, backfill=False)


def backfill(run_date: str, apply: bool, limit: int | None = None) -> dict:
    first, last = season_span(run_date, True)
    logger.info(f"NHL right rail backfill, seasons {first} through {last} (ending year)")
    if not apply:
        return {"ok": True, "seasons": (first, last), "downloaded": False, "rows": 0}
    return run(run_date, True, backfill=True, limit=limit)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--daily", action="store_true")
    mode.add_argument("--backfill", action="store_true")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD, default today ET")
    ap.add_argument("--apply", action="store_true", help="write to Supabase")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    if args.date:
        run_date = args.date
    else:
        run_date = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    if args.daily:
        if args.limit:
            result = run(run_date, args.apply, backfill=False, limit=args.limit)
        else:
            result = daily(run_date, args.apply)
    else:
        result = backfill(run_date, args.apply, limit=args.limit)
    if result.get("failed"):
        raise SystemExit(1)
