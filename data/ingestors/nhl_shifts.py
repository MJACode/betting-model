"""NHL shift charts. One row per shift, from the league's public API.

Personal, non-commercial. Not a pick input.

    https://api.nhle.com/stats/rest/en/shiftcharts?cayenneExp=gameId={id}

Measured 2026-11-26 on game 2026020386: one call returns every shift
(721 rows, `total` 721) when no limit is sent. A limit still pages with
`start`. A game already stored is not fetched again.

The chart has no strength and no situation (the row's keys are the shift
itself). Shared ice is derived from overlapping shifts in the same period.
Power-play units are not inferred from it; those come from Daily Faceoff.

    python -m data.ingestors.nhl_shifts --daily
    python -m data.ingestors.nhl_shifts --daily --apply
    python -m data.ingestors.nhl_shifts --backfill          # the season span
    python -m data.ingestors.nhl_shifts --backfill --apply  # 2023-24 through now
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
from data.ingestors.nhl_stats_ingestor import _norm_nhl

SOURCE = "nhl_api"
STATS = "https://api.nhle.com/stats/rest/en/shiftcharts"
PAUSE_S = 0.6
PAGE_LIMIT = 1000
# A minute of shared ice. Shorter overlaps are changes, not a pair.
MIN_SHARED_SECONDS = 60

SHIFT_COLS = (
    "shift_id", "nhl_game_id", "season_end", "game_type", "game_date", "our_game_id",
    "player_id", "player_name", "team_abbr", "period", "shift_number",
    "start_seconds", "end_seconds", "duration_seconds", "start_time", "end_time",
    "duration", "type_code", "detail_code", "event_number", "source",
)
SHIFT_PK = ("shift_id",)
MATE_COLS = (
    "nhl_game_id", "team_abbr", "player_id_lo", "player_id_hi",
    "player_name_lo", "player_name_hi", "shared_seconds",
    "season_end", "game_date", "our_game_id", "source",
)
MATE_PK = ("nhl_game_id", "player_id_lo", "player_id_hi")


def clock_seconds(value) -> int | None:
    """'MM:SS' or 'H:MM:SS' as published on the chart. None when it is not a clock."""
    if value is None:
        return None
    text = str(value).strip()
    parts = text.split(":")
    if not parts or any(not p.isdigit() for p in parts):
        return None
    nums = [int(p) for p in parts]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return None


def shift_url(gid: int, start: int, limit: int = PAGE_LIMIT) -> str:
    return f"{STATS}?cayenneExp=gameId={int(gid)}&start={int(start)}&limit={int(limit)}"


def fetch_shift_rows(gid: int, get=get_json, limit: int = PAGE_LIMIT) -> list[dict]:
    """Every shift for one game. Pages until `total` is in hand.

    `start` is an offset (measured: start=2 skips the first two rows). A
    page that adds nothing is the end, so a repeated page cannot loop.
    """
    found: dict[int, dict] = {}
    start = 0
    total = None
    while True:
        body = get(shift_url(gid, start, limit))
        page = body.get("data") or []
        total = int(body.get("total") or 0)
        added = 0
        for row in page:
            sid = row.get("id")
            if sid is None or int(sid) in found:
                continue
            found[int(sid)] = row
            added += 1
        if not page or added == 0 or (total and len(found) >= total):
            break
        start += len(page)
        if start > total + limit:
            break
    if total and len(found) < total:
        raise FetchFailed(f"game {gid}: {len(found)} shifts of {total}")
    return list(found.values())


def shift_record(row: dict, meta: dict) -> dict | None:
    if row.get("id") is None or row.get("playerId") is None:
        return None
    first = (row.get("firstName") or "").strip()
    last = (row.get("lastName") or "").strip()
    name = f"{first} {last}".strip() or None
    start = clock_seconds(row.get("startTime"))
    end = clock_seconds(row.get("endTime"))
    dur = clock_seconds(row.get("duration"))
    return {
        "shift_id": int(row["id"]),
        "nhl_game_id": int(meta["nhl_game_id"]),
        "season_end": int(meta["season_end"]),
        "game_type": int(meta["game_type"]),
        "game_date": meta.get("game_date"),
        "our_game_id": meta.get("our_game_id"),
        "player_id": int(row["playerId"]),
        "player_name": name,
        "team_abbr": _norm_nhl(row.get("teamAbbrev") or "") or None,
        "period": int(row["period"]) if row.get("period") is not None else None,
        "shift_number": int(row["shiftNumber"]) if row.get("shiftNumber") is not None else None,
        "start_seconds": start,
        "end_seconds": end,
        "duration_seconds": dur,
        "start_time": row.get("startTime"),
        "end_time": row.get("endTime"),
        "duration": row.get("duration"),
        "type_code": int(row["typeCode"]) if row.get("typeCode") is not None else None,
        "detail_code": int(row["detailCode"]) if row.get("detailCode") is not None else None,
        "event_number": int(row["eventNumber"]) if row.get("eventNumber") is not None else None,
        "source": SOURCE,
    }


def _overlap(a0: int, a1: int, b0: int, b1: int) -> int:
    return max(0, min(a1, b1) - max(a0, b0))


def linemate_pairs(records: list[dict], min_seconds: int = MIN_SHARED_SECONDS) -> list[dict]:
    """Pairs on one team whose shifts overlap in the same period.

    The chart does not say who was on the power play. This is shared ice
    only, and a pair under `min_seconds` is not stored.
    """
    by_team: dict[str, dict[int, dict]] = {}
    for row in records:
        team = row.get("team_abbr")
        start, end = row.get("start_seconds"), row.get("end_seconds")
        period = row.get("period")
        if not team or start is None or end is None or period is None or end <= start:
            continue
        players = by_team.setdefault(team, {})
        cur = players.setdefault(int(row["player_id"]), {
            "name": row.get("player_name"), "spans": [],
        })
        if row.get("player_name"):
            cur["name"] = row["player_name"]
        cur["spans"].append((int(period), int(start), int(end)))
    out = []
    meta = records[0] if records else {}
    for team, players in by_team.items():
        ids = sorted(players)
        for i, left in enumerate(ids):
            for right in ids[i + 1:]:
                shared = 0
                for p1, a0, a1 in players[left]["spans"]:
                    for p2, b0, b1 in players[right]["spans"]:
                        if p1 == p2:
                            shared += _overlap(a0, a1, b0, b1)
                if shared < min_seconds:
                    continue
                out.append({
                    "nhl_game_id": meta.get("nhl_game_id"),
                    "team_abbr": team,
                    "player_id_lo": left,
                    "player_id_hi": right,
                    "player_name_lo": players[left]["name"],
                    "player_name_hi": players[right]["name"],
                    "shared_seconds": shared,
                    "season_end": meta.get("season_end"),
                    "game_date": meta.get("game_date"),
                    "our_game_id": meta.get("our_game_id"),
                    "source": SOURCE,
                })
    return out


def _insert_sql(table: str, cols: tuple[str, ...], pk: tuple[str, ...]) -> str:
    sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in pk)
    return (
        f"INSERT INTO {table} ({', '.join(cols)}) "
        f"VALUES ({', '.join(f'%({c})s' for c in cols)}) "
        f"ON CONFLICT ({', '.join(pk)}) DO UPDATE SET {sets}, fetched_at = NOW()"
    )


_SHIFT_SQL = _insert_sql("nhl_shifts", SHIFT_COLS, SHIFT_PK)
_MATE_SQL = _insert_sql("nhl_shift_linemates", MATE_COLS, MATE_PK)


def _write_game(conn, shifts: list[dict], mates: list[dict]) -> None:
    def once():
        conn.executemany(_SHIFT_SQL, shifts)
        if mates:
            conn.executemany(_MATE_SQL, mates)
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
    written_shifts = written_mates = games_done = 0
    try:
        games, odd = completed_games(conn, first, last)
        have = stored_ids(conn, "nhl_shifts") if apply else set()
        todo = [g for g in games if g["nhl_game_id"] not in have]
        if limit:
            todo = todo[:limit]
        logger.info(
            f"NHL shifts {first}-{last}: {len(games):,} played, "
            f"{len(have):,} stored, {len(todo):,} to fetch, {len(odd)} odd log rows")
        if not apply:
            return {"ok": True, "games": len(todo), "rows": 0, "failed": {},
                    "seasons": (first, last), "downloaded": False}
        for i, meta in enumerate(todo, start=1):
            gid = meta["nhl_game_id"]
            try:
                raw = fetch_shift_rows(gid, get=get)
            except FetchFailed as exc:
                failed[gid] = str(exc)
                logger.warning(f"{gid}: {exc}")
                time.sleep(pause_s)
                continue
            records = [r for r in (shift_record(row, meta) for row in raw) if r]
            if not records:
                failed[gid] = "no shifts"
                logger.warning(f"{gid}: no shifts")
                time.sleep(pause_s)
                continue
            mates = linemate_pairs(records)
            _write_game(conn, records, mates)
            written_shifts += len(records)
            written_mates += len(mates)
            games_done += 1
            if games_done % 25 == 0:
                logger.info(f"{games_done:,} games, {written_shifts:,} shifts, "
                            f"{written_mates:,} pairs")
            time.sleep(pause_s)
            if i == len(todo):
                break
    finally:
        conn.close()
    ok = not failed
    if ok:
        logger.success(f"NHL shifts: {games_done:,} games, {written_shifts:,} shifts, "
                       f"{written_mates:,} pairs")
    else:
        logger.error(f"NHL shifts: {len(failed)} games not stored "
                     f"(first {list(failed)[:5]}); {games_done:,} games were written")
    return {"ok": ok, "games": games_done, "rows": written_shifts,
            "pairs": written_mates, "failed": failed, "seasons": (first, last)}


def daily(run_date: str, apply: bool) -> dict:
    return run(run_date, apply, backfill=False)


def backfill(run_date: str, apply: bool, limit: int | None = None) -> dict:
    first, last = season_span(run_date, True)
    logger.info(f"NHL shifts backfill, seasons {first} through {last} (ending year)")
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
    ap.add_argument("--limit", type=int, default=None, help="stop after this many games")
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
