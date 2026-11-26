"""MoneyPuck NHL files into Supabase. Credit MoneyPuck.com.

Personal, non-commercial copy of the files listed on
https://moneypuck.com/data.htm. Nothing else on that site is fetched.
Not a pick input: no model, threshold, or record reads these tables.

Shots publish nightly around 3:40am ET and the other files around 6:45am ET,
so the daily job runs at 7:20am ET. One download of each file per day; a
retry the same day reuses the copy already on disk.

    python -m data.ingestors.moneypuck_nhl --daily --date 2026-11-26
    python -m data.ingestors.moneypuck_nhl --daily --apply
    python -m data.ingestors.moneypuck_nhl --backfill          # the file list
    python -m data.ingestors.moneypuck_nhl --backfill --apply  # download and write

What --backfill --apply stores, and why the rest stays out (sizes measured
2026-11-26 from Content-Length, and from the uncompressed 2026 files):

  * Shots, file years 2018-current (2018-19 through the current season).
    A full season is about 20 MB compressed. The 2026 file, partway through
    the season, is 5.3 MB compressed, 18.4 MB csv, 33,334 rows. Eight full
    seasons plus that file is on the order of 1.2-1.8 GB in Postgres.
    2007-2017 is another ~1.2 million shots and is not pulled.
  * Team game-by-game, the whole all_teams.csv: 129 MB csv, 236,210 rows,
    seasons 2008-2026. A few hundred MB in Postgres.
  * Lines and pairings, full history: lines/2008_to_2024.zip (101 MB) plus
    each later season. The 2026 file is 1.9 MB compressed, 13.2 MB csv,
    24,713 rows (5-on-5 lines and pairings). On the order of 1-1.6 GB.
  * Skaters, file years 2018-current, one zip a season (~20-24 MB
    compressed). The 2026 file is 7.0 MB compressed, 49.7 MB csv, 69,295
    rows. On the order of 1.5-2.5 GB. The 2008-2024 bundle is 366 MB
    compressed and is not pulled; it would add the years before 2018.
  * Goalies, full history: goalies/2008_to_2024.zip is 9 MB, and a season
    is about 0.5 MB. Tens of MB in Postgres.
  * Player bios, the one lookup file (names and positions).

The daily run pulls only the current season's shot, skater, goalie and line
files, the bios file, and all_teams.csv (the only team file; rows from
other seasons in it are not written).
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import tempfile
import time
import zipfile
from pathlib import Path

import requests
from loguru import logger

from data.db import ConnectionLost, get_connection
from data.ingestors.moneypuck_columns import SOURCE, TABLES, columns
from data.ingestors.nhl_stats_ingestor import _norm_nhl
from data.season_labels import nhl_season_label

# Credit MoneyPuck.com. The files are the ones named on their data page.
CREDIT = "MoneyPuck.com"
DATA_PAGE = "https://moneypuck.com/data.htm"
BASE = "https://peter-tanner.com/moneypuck/downloads"
SHOT_URL = BASE + "/shots_{year}.zip"
SKATER_URL = BASE + "/seasonPlayersSummary/skaters/{year}.zip"
GOALIE_URL = BASE + "/seasonPlayersSummary/goalies/{year}.zip"
LINE_URL = BASE + "/seasonPlayersSummary/lines/{year}.zip"
LINE_BUNDLE_URL = BASE + "/seasonPlayersSummary/lines/2008_to_2024.zip"
GOALIE_BUNDLE_URL = BASE + "/seasonPlayersSummary/goalies/2008_to_2024.zip"
TEAM_URL = "https://moneypuck.com/moneypuck/playerData/careers/gameByGame/all_teams.csv"
BIOS_URL = "https://moneypuck.com/moneypuck/playerData/playerBios/allPlayersLookup.csv"

# File year is the season's starting year. 2018 is 2018-19.
SHOTS_FROM_YEAR = 2018
SKATERS_FROM_YEAR = 2018
BUNDLE_THROUGH_YEAR = 2024

HEADERS = {
    "User-Agent": "BettingModel/1.0 (personal non-commercial research; credits MoneyPuck.com)",
    "Accept": "*/*",
}
PAUSE_S = 1.0
BATCH = 400
HTTP_TIMEOUT = 180

# MoneyPuck's older files spell a few clubs with a dot. Our id is the one
# nhl_team_game_log uses, including ARI folded into UTA.
DOTTED = {"L.A": "LAK", "N.J": "NJD", "S.J": "SJS", "T.B": "TBL"}

PLAYER_COLS = (
    "player_id", "name", "position", "team_code", "team_abbr", "birth_date",
    "weight", "height", "nationality", "shoots_catches", "primary_number",
    "primary_position", "source",
)

CACHE_DIR = Path(os.environ.get("MONEYPUCK_CACHE_DIR")
                 or Path(tempfile.gettempdir()) / "moneypuck")


def file_year(run_date: str) -> int:
    """MoneyPuck's season number: the starting year. Our label is the ending year."""
    return nhl_season_label(run_date) - 1


def team_abbr(code: str | None) -> str | None:
    if code is None:
        return None
    text = str(code).strip()
    if not text:
        return None
    return _norm_nhl(DOTTED.get(text, text))


def iso_date(value: str | None) -> str | None:
    """YYYYMMDD as published, stored YYYY-MM-DD like the rest of the logs."""
    if value is None:
        return None
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return text
    return None


def nhl_game_id_from_shot(season_start: int, mp_game_number: int) -> int:
    """shots_YYYY.csv numbers a game 20001. The league id is 2026020001.

    20001 zero-padded to six digits is 020001: game type 02, game 0001.
    """
    return int(f"{int(season_start)}{int(mp_game_number):06d}")


def _blank(value) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text.upper() in {"NA", "N/A", "NULL", "NONE", "NAN"}


def _measure(row: dict, table: dict) -> dict:
    out = {}
    for src, col, _sql, kind in table["measures"]:
        value = row.get(src, "")
        if _blank(value):
            out[col] = None
        elif kind == "text":
            out[col] = str(value)
        elif kind == "bigint":
            out[col] = int(value)
        else:
            out[col] = float(value)
    return out


def _season_pair(row: dict) -> tuple[int, int]:
    start = int(row["season"])
    return start, start + 1


def shot_record(row: dict) -> dict | None:
    start, end = _season_pair(row)
    number = int(row["game_id"])
    record = {
        "nhl_game_id": nhl_game_id_from_shot(start, number),
        "event_id": int(row["id"]),
        "season_start": start,
        "season_end": end,
        "mp_game_number": number,
        "game_date": None,
        "our_game_id": None,
        "team_abbr": team_abbr(row.get("teamCode")),
        "home_abbr": team_abbr(row.get("homeTeamCode")),
        "away_abbr": team_abbr(row.get("awayTeamCode")),
        "source": SOURCE,
    }
    record.update(_measure(row, TABLES["shots"]))
    return record


def _game_record(row: dict, table: dict, extra: dict) -> dict | None:
    start, end = _season_pair(row)
    team = team_abbr(row.get("playerTeam"))
    if not team or _blank(row.get("situation")) or _blank(row.get("gameId")):
        return None
    record = {
        "nhl_game_id": int(row["gameId"]),
        "season_start": start,
        "season_end": end,
        "game_date": iso_date(row.get("gameDate")),
        "our_game_id": None,
        "team_abbr": team,
        "opp_abbr": team_abbr(row.get("opposingTeam")),
        "situation": str(row["situation"]),
        "source": SOURCE,
    }
    record.update(extra)
    record.update(_measure(row, table))
    return record


def team_record(row: dict) -> dict | None:
    return _game_record(row, TABLES["teams"], {})


def line_record(row: dict) -> dict | None:
    if _blank(row.get("lineId")):
        return None
    return _game_record(row, TABLES["lines"], {"line_id": str(row["lineId"]).strip()})


def _player_record(row: dict, table: dict) -> dict | None:
    if _blank(row.get("playerId")):
        return None
    return _game_record(row, table, {"player_id": int(row["playerId"])})


def skater_record(row: dict) -> dict | None:
    return _player_record(row, TABLES["skaters"])


def goalie_record(row: dict) -> dict | None:
    return _player_record(row, TABLES["goalies"])


def player_record(row: dict) -> dict | None:
    if _blank(row.get("playerId")):
        return None
    weight = row.get("weight")
    return {
        "player_id": int(row["playerId"]),
        "name": row.get("name") or None,
        "position": row.get("position") or None,
        "team_code": row.get("team") or None,
        "team_abbr": team_abbr(row.get("team")),
        "birth_date": iso_date(row.get("birthDate")) or (row.get("birthDate") or None),
        "weight": float(weight) if not _blank(weight) else None,
        "height": row.get("height") or None,
        "nationality": row.get("nationality") or None,
        "shoots_catches": row.get("shootsCatches") or None,
        "primary_number": row.get("primaryNumber") or None,
        "primary_position": row.get("primaryPosition") or None,
        "source": SOURCE,
    }


BUILDERS = {
    "shots": shot_record,
    "teams": team_record,
    "lines": line_record,
    "skaters": skater_record,
    "goalies": goalie_record,
    "bios": player_record,
}


def _item(kind: str, url: str, season: int | None = None) -> dict:
    return {"kind": kind, "url": url, "season": season}


def daily_plan(run_date: str) -> list[dict]:
    """The files for one morning. One URL each. Current season only, plus
    the two files MoneyPuck publishes as a single all-years download."""
    year = file_year(run_date)
    return [
        _item("shots", SHOT_URL.format(year=year), year),
        _item("teams", TEAM_URL, year),
        _item("skaters", SKATER_URL.format(year=year), year),
        _item("goalies", GOALIE_URL.format(year=year), year),
        _item("lines", LINE_URL.format(year=year), year),
        _item("bios", BIOS_URL, None),
    ]


def backfill_plan(run_date: str) -> list[dict]:
    """History worth storing. See the module docstring for the sizes left out."""
    year = file_year(run_date)
    items = [_item("shots", SHOT_URL.format(year=y), y)
             for y in range(SHOTS_FROM_YEAR, year + 1)]
    items.append(_item("teams", TEAM_URL, None))
    items += [_item("skaters", SKATER_URL.format(year=y), y)
              for y in range(SKATERS_FROM_YEAR, year + 1)]
    items.append(_item("goalies", GOALIE_BUNDLE_URL, None))
    items += [_item("goalies", GOALIE_URL.format(year=y), y)
              for y in range(BUNDLE_THROUGH_YEAR + 1, year + 1)]
    items.append(_item("lines", LINE_BUNDLE_URL, None))
    items += [_item("lines", LINE_URL.format(year=y), y)
              for y in range(BUNDLE_THROUGH_YEAR + 1, year + 1)]
    items.append(_item("bios", BIOS_URL, None))
    return items


def _keep_season(season: int | None):
    if season is None:
        return None

    def pred(row: dict) -> bool:
        return int(row["season"]) == season

    return pred


def _cache_path(run_date: str, url: str) -> Path:
    name = url.rstrip("/").split("/")[-1]
    return CACHE_DIR / run_date / name


def download(url: str, dest: Path) -> bool:
    """Save one file. Returns True when this call hit the network.

    A file already saved for this date is reused, so a retry does not
    download it again.
    """
    if dest.exists() and dest.stat().st_size > 0:
        logger.info(f"reusing {dest.name} ({dest.stat().st_size:,} bytes)")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    logger.info(f"GET {url}")
    with requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT, stream=True) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in resp.iter_content(1 << 20):
                if chunk:
                    fh.write(chunk)
    os.replace(tmp, dest)
    logger.info(f"saved {dest.name} ({dest.stat().st_size:,} bytes)")
    return True


def iter_dicts(path: Path):
    if path.suffix.lower() == ".zip":
        archive = zipfile.ZipFile(path)
        names = [n for n in archive.namelist() if n.lower().endswith(".csv") and not n.endswith("/")]
        if len(names) != 1:
            archive.close()
            raise RuntimeError(f"{path.name} holds {names or 'no'} csv, expected one")
        raw = archive.open(names[0])
        text = io.TextIOWrapper(raw, encoding="utf-8", newline="")
        try:
            yield from csv.DictReader(text)
        finally:
            text.close()
            archive.close()
        return
    with path.open(encoding="utf-8", newline="") as fh:
        yield from csv.DictReader(fh)


def _insert_sql(table_name: str, cols: tuple[str, ...], pk: tuple[str, ...]) -> str:
    sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in pk)
    return (
        f"INSERT INTO {table_name} ({', '.join(cols)}) "
        f"VALUES ({', '.join(f'%({c})s' for c in cols)}) "
        f"ON CONFLICT ({', '.join(pk)}) DO UPDATE SET {sets}, fetched_at = NOW()"
    )


def _flush(conn, sql: str, rows: list[dict]) -> None:
    try:
        conn.executemany(sql, rows)
        conn.commit()
    except ConnectionLost:
        logger.warning("connection lost mid-batch — re-running it")
        conn.executemany(sql, rows)
        conn.commit()


def _dedupe(rows: list[dict], pk: tuple[str, ...]) -> list[dict]:
    keyed = {}
    for row in rows:
        keyed[tuple(row[c] for c in pk)] = row
    return list(keyed.values())


def load_file(path: Path, kind: str, season: int | None, apply: bool, conn) -> dict:
    if kind == "bios":
        table_name = "moneypuck_players"
        cols = PLAYER_COLS
        pk = ("player_id",)
        sql = _insert_sql(table_name, cols, pk)
    else:
        table = TABLES[kind]
        table_name = table["sql_name"]
        cols = columns(table) + ("source",)
        pk = table["pk"]
        sql = _insert_sql(table_name, cols, pk)
    build = BUILDERS[kind]
    pred = _keep_season(season)
    seen = kept = skipped = written = 0
    buf: list[dict] = []

    def flush() -> None:
        nonlocal written, buf
        if not buf:
            return
        rows = _dedupe(buf, pk)
        if apply:
            _flush(conn, sql, rows)
        written += len(rows)
        buf = []

    for raw in iter_dicts(path):
        seen += 1
        if pred is not None and not pred(raw):
            continue
        record = build(raw)
        if record is None:
            skipped += 1
            continue
        kept += 1
        buf.append(record)
        if len(buf) >= BATCH:
            flush()
    flush()
    logger.info(f"{table_name}: seen {seen:,}, kept {kept:,}, skipped {skipped:,}, "
                f"written {written:,}" + ("" if apply else " (dry run)"))
    return {"table": table_name, "seen": seen, "kept": kept,
            "skipped": skipped, "written": written}


def link_games(conn, tables: list[str]) -> None:
    """Fill our_game_id from nhl_team_game_log. Shots have no date of their own."""
    for name in tables:
        if name == "moneypuck_players":
            continue
        date_sql = ""
        if name == "moneypuck_shots":
            date_sql = ", game_date = COALESCE(s.game_date, g.game_date)"
        conn.execute(
            f"UPDATE {name} AS s SET our_game_id = g.game_id{date_sql} "
            "FROM (SELECT nhl_game_id, MIN(game_id) AS game_id, MIN(game_date) AS game_date "
            "FROM nhl_team_game_log GROUP BY nhl_game_id) g "
            "WHERE s.nhl_game_id = g.nhl_game_id "
            "AND (s.our_game_id IS DISTINCT FROM g.game_id"
            + (" OR s.game_date IS NULL" if name == "moneypuck_shots" else "")
            + ")",
        )
        conn.commit()


def run_plan(plan: list[dict], run_date: str, apply: bool) -> dict:
    """Download each file once and upsert. A file with zero kept rows fails
    the run: an empty current-season file is a broken download, not a quiet day.
    The team file is the exception on a daily run, where the season filter
    can match rows only when that season is in the file."""
    urls = [item["url"] for item in plan]
    if len(urls) != len(set(urls)):
        raise RuntimeError(f"plan downloads a file twice: {urls}")
    conn = get_connection() if apply else None
    results = []
    try:
        for item in plan:
            dest = _cache_path(run_date, item["url"])
            fetched = download(item["url"], dest)
            if fetched:
                time.sleep(PAUSE_S)
            stats = load_file(dest, item["kind"], item["season"], apply, conn)
            stats["url"] = item["url"]
            stats["kind"] = item["kind"]
            results.append(stats)
            if stats["kept"] == 0:
                raise RuntimeError(
                    f"{item['url']} kept 0 rows (seen {stats['seen']}). "
                    "Not a successful refresh.")
        if apply and conn is not None:
            link_games(conn, [r["table"] for r in results])
    finally:
        if conn is not None:
            conn.close()
    written = sum(r["written"] for r in results)
    logger.success(f"MoneyPuck.com: {len(results)} files, {written:,} rows"
                   + ("" if apply else " (dry run, nothing written)"))
    return {"ok": True, "files": results, "written": written, "credit": CREDIT}


def daily(run_date: str, apply: bool) -> dict:
    logger.info(f"MoneyPuck.com daily {run_date}, file year {file_year(run_date)}")
    return run_plan(daily_plan(run_date), run_date, apply)


def backfill(run_date: str, apply: bool) -> dict:
    plan = backfill_plan(run_date)
    logger.info(f"MoneyPuck.com backfill, {len(plan)} files, file year through {file_year(run_date)}")
    for item in plan:
        logger.info(f"  {item['kind']:8} {item['url']}")
    if not apply:
        return {"ok": True, "files": plan, "written": 0, "credit": CREDIT, "downloaded": False}
    return run_plan(plan, run_date, True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--daily", action="store_true",
                      help="current season only, one download per file")
    mode.add_argument("--backfill", action="store_true",
                      help="the history named in the module docstring")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD, default today ET")
    ap.add_argument("--apply", action="store_true", help="write to Supabase")
    args = ap.parse_args()
    if args.date:
        run_date = args.date
    else:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        run_date = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    if args.daily:
        daily(run_date, args.apply)
    else:
        backfill(run_date, args.apply)
