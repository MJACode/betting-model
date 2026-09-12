"""Move the paid NFL odds history off this laptop and into Supabase.

mike, 2026-09-12: *"EVERYTHING SHOULD BE IN SUPABASE FOR THE MILLIONTH FUCKING
TIME. Need a global rule."*

WHAT WAS WRONG. `nfl/data/odds_cache` held 6,769 JSON files, 655 MB, of PAID
Odds API historical responses -- NFL 2020 through 2026, every book we have ever
requested, h2h / spreads / totals -- written by `nfl/data_ingest/odds_api.py`
and read by the opener and wind replays. `odds` held NFL rows for 2026 only.
That data existed on ONE laptop. CLAUDE.md section 1b has said extracted data
belongs in Supabase since 2026-08-30 and listed this directory as a known
exception "worth fixing when touched"; a tolerated exception is not a rule.

WHAT THIS WRITES. One `odds` row per (served snapshot, event, market, book):

    snapshot_at   = the timestamp the API SERVED (the file's `timestamp`)
    snapshot_type = 'in_play' when served >= commence_time, else 'open'
                    (the column is NOT NULL and 'open' is what every pre-game
                    row in the table carries)
    source        = 'nfl_odds_cache|served=<ts>|lu=<book last_update>'

`served` is what resume and dedupe key on, exactly as the in-play history
ingestors do: re-running imports nothing that is already stored. `lu` is the
BOOK's own last_update, kept because a quote whose last_update predates a score
is the score priced twice -- the replay's freshness split needs it and throwing
it away would make the stored copy worse than the files.

WHAT IT SKIPS, AND COUNTS RATHER THAN INVENTS.
  * `h2h_lay` -- an exchange lay price is not a bet we can place, and there is
    no column that means it.
  * An event whose teams or date do not resolve to a `games` row. NFL ids are
    `NFL_<season>_<week>_<away>_<home>`, so the id cannot be built from the
    payload; it is looked up by (date, away, home) with the full-name map the
    NFL ingest already carries, trying the ET date first and the UTC date
    second (a late kickoff crosses midnight UTC).

    python -m data.ingestors.nfl_odds_cache_import --dry-run
    python -m data.ingestors.nfl_odds_cache_import --apply
    python -m data.ingestors.nfl_odds_cache_import --apply --shard 0/4
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from loguru import logger

from data.db import DBConnection, get_connection
from data.ingestors.odds_ingestor import _insert_odds
from nfl.data_ingest.parse import TEAM_MAP

CACHE_DIR = Path(__file__).resolve().parents[2] / "nfl" / "data" / "odds_cache"
SOURCE_PREFIX = "nfl_odds_cache|"
SPORT = "NFL"
KEEP_MARKETS = ("h2h", "spreads", "totals")
_ET = ZoneInfo("America/New_York")
BATCH = 2000


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def game_index(conn: DBConnection) -> dict[tuple[str, str, str], str]:
    """(date, away, home) -> game_id, for both the ET and the UTC date of each
    game. A late kickoff is 'Sunday' in ET and 'Monday' in UTC, and the payload
    carries only the UTC commence_time."""
    idx: dict[tuple[str, str, str], str] = {}
    for gid, gd, home, away, ct in conn.execute(
            "SELECT game_id, game_date, home_team, away_team, commence_time "
            "FROM games WHERE sport = 'NFL'").fetchall():
        for d in {str(gd)[:10]}:
            idx[(d, str(away), str(home))] = gid
        if ct:
            try:
                u = _ts(str(ct))
            except Exception:                       # noqa: BLE001
                continue
            for d in {u.date().isoformat(), u.astimezone(_ET).date().isoformat()}:
                idx.setdefault((d, str(away), str(home)), gid)
    return idx


def resolve(idx: dict, ev: dict) -> str | None:
    home = TEAM_MAP.get(ev.get("home_team") or "")
    away = TEAM_MAP.get(ev.get("away_team") or "")
    ct = ev.get("commence_time")
    if not (home and away and ct):
        return None
    u = _ts(ct)
    # PLUS AND MINUS A DAY, not just minus. Minus covers the UTC roll on a late
    # kickoff; PLUS covers a POSTPONEMENT, and that is not a rare edge -- the
    # payload carries the originally scheduled kickoff while `games` carries
    # the date played. The 2024-01-14 Steelers-Bills wild card moved to the
    # 15th for a blizzard, and it was one of 956 events this dropped on the
    # first import, clustered in January and February: playoff weekends.
    for d in (u.astimezone(_ET).date().isoformat(), u.date().isoformat(),
              (u - timedelta(days=1)).date().isoformat(),
              (u + timedelta(days=1)).date().isoformat(),
              (u + timedelta(days=2)).date().isoformat()):
        gid = idx.get((d, away, home))
        if gid:
            return gid
    return None


def rows_from_file(payload: dict, idx: dict) -> tuple[list[dict], int]:
    """(`odds` rows, unresolved event count) for one cached response."""
    served = payload.get("timestamp")
    if not served:
        return [], 0
    served_dt = _ts(served)
    out, unresolved = [], 0
    for ev in payload.get("data") or []:
        gid = resolve(idx, ev)
        if not gid:
            unresolved += 1
            continue
        home_name = ev.get("home_team")
        in_play = served_dt >= _ts(ev["commence_time"])
        for bk in ev.get("bookmakers") or []:
            book = (bk.get("key") or "").strip().lower()
            if not book:
                continue
            for m in bk.get("markets") or []:
                key = m.get("key")
                if key not in KEEP_MARKETS:
                    continue
                row = {
                    "game_id": gid, "sport": SPORT, "market": key,
                    "bookmaker": book,
                    "snapshot_type": "in_play" if in_play else "open",
                    "snapshot_at": served,
                    "home_price": None, "away_price": None, "draw_price": None,
                    "spread_home": None, "total_line": None,
                    "over_price": None, "under_price": None,
                    "home_link": None, "away_link": None, "draw_link": None,
                    "over_link": None, "under_link": None,
                    "home_sid": None, "away_sid": None, "draw_sid": None,
                    "over_sid": None, "under_sid": None,
                    "source": (f"{SOURCE_PREFIX}served={served}"
                               f"|lu={m.get('last_update') or bk.get('last_update') or ''}"),
                }
                priced = False
                for o in m.get("outcomes") or []:
                    name, price, point = o.get("name"), o.get("price"), o.get("point")
                    if price is None:
                        continue
                    if key == "totals":
                        if name == "Over":
                            row["over_price"], row["total_line"] = price, point
                            priced = True
                        elif name == "Under":
                            row["under_price"] = price
                            priced = True
                    elif name == home_name:
                        row["home_price"] = price
                        if key == "spreads":
                            row["spread_home"] = point
                        priced = True
                    else:
                        row["away_price"] = price
                        priced = True
                if priced:
                    out.append(row)
    return out, unresolved


def stored_pairs(conn: DBConnection) -> set[tuple[str, str]]:
    """(game_id, served) already imported.

    The `--fill-gaps` key. The served-level resume below is right for the bulk
    import and wrong for a re-run after the RESOLVER improves: every file's
    snapshot is stored, so it would skip everything, while the events that now
    resolve have no rows at all. Keying on the pair adds exactly the newly
    resolved games and re-adds nothing."""
    return {(r[0], r[1]) for r in conn.execute(
        "SELECT DISTINCT game_id, snapshot_at FROM odds "
        "WHERE sport = %s AND source LIKE %s",
        (SPORT, SOURCE_PREFIX + "%")).fetchall()}


def stored_served(conn: DBConnection) -> set[str]:
    """Every served timestamp already imported. The resume key, so a re-run
    costs a scan and writes nothing rather than duplicating 2 million rows."""
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT split_part(split_part(source, '|served=', 2), '|', 1) "
        "FROM odds WHERE sport = %s AND source LIKE %s",
        (SPORT, SOURCE_PREFIX + "%")).fetchall() if r[0]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--shard", default=None, help="i/N, files split round-robin")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--fill-gaps", action="store_true",
                    help="ignore the served-level resume and add only the "
                         "(game_id, served) pairs missing -- for a re-run "
                         "after the resolver improves")
    a = ap.parse_args()
    if not (a.dry_run or a.apply):
        ap.error("choose --dry-run or --apply")

    files = sorted(CACHE_DIR.glob("*.json"))
    if a.shard:
        i, n = (int(x) for x in a.shard.split("/"))
        files = [f for k, f in enumerate(files) if k % n == i]
    if a.limit:
        files = files[:a.limit]
    logger.info(f"{len(files):,} cached response(s) in {CACHE_DIR}")

    conn = get_connection()
    try:
        idx = game_index(conn)
        logger.info(f"{len(idx):,} (date, away, home) keys from games")
        have = set() if a.fill_gaps else stored_served(conn)
        pairs = stored_pairs(conn) if a.fill_gaps else set()
        logger.info(f"{len(have):,} served snapshot(s) already in Supabase"
                    if not a.fill_gaps else
                    f"fill-gaps: {len(pairs):,} (game, snapshot) pair(s) stored")

        rows_total = unresolved_total = skipped = wrote = 0
        batch: list[dict] = []
        for k, f in enumerate(files, 1):
            try:
                payload = json.loads(f.read_text(encoding="utf-8"))
            except Exception as exc:                 # noqa: BLE001
                logger.warning(f"{f.name}: unreadable ({exc})")
                continue
            if (payload.get("timestamp") or "") in have:
                skipped += 1
                continue
            rows, unresolved = rows_from_file(payload, idx)
            if a.fill_gaps:
                rows = [r for r in rows
                        if (r["game_id"], r["snapshot_at"]) not in pairs]
                for r in rows:
                    pairs.add((r["game_id"], r["snapshot_at"]))
            rows_total += len(rows)
            unresolved_total += unresolved
            if a.apply and rows:
                batch.extend(rows)
                if len(batch) >= BATCH:
                    _insert_odds(conn, batch)
                    conn.commit()
                    wrote += len(batch)
                    batch = []
            have.add(payload.get("timestamp"))
            if k % 500 == 0:
                logger.info(f"  {k:,}/{len(files):,} files | rows {rows_total:,} "
                            f"| written {wrote:,} | skipped {skipped:,}")
        if a.apply and batch:
            _insert_odds(conn, batch)
            conn.commit()
            wrote += len(batch)

        logger.success(
            f"{'WROTE' if a.apply else 'WOULD WRITE'} {rows_total:,} odds rows "
            f"from {len(files) - skipped:,} file(s); {skipped:,} already stored; "
            f"{unresolved_total:,} event(s) did not resolve to a games row")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
