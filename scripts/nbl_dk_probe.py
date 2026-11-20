"""Does DraftKings' own board price the NBL, and which markets? Read-only, one
pass, every answer stored raw in Supabase (nbl_dk_raw) and printed.

WHY. The odds feed carries no DraftKings NBL price in any snapshot read
(2024-12 to 2026-11, docs/sports/nbl.md), so BetRivers is the only book a pick
may name there. The scout of 2026-11-14 found search-index copies of
DraftKings NBL pages (quarters, winning margin, alternate spreads, an in-play
fourth-quarter line), FanDuel ones (team props, player threes) and BetMGM's
NBL page, all undated. A feed that does not resell a book's league is not a
book that does not price it (the league-models skill, market-grid route 4).
This pass answers it for DraftKings: whether the NBL is on its basketball
navigation, its league id, the games on its board, and every category and
sub-page it lists, with one sub-page answer each.

HOW. The client the repo's in-play reader uses (curl_cffi as Chrome,
data/ingestors/dk_live_board.py): the basketball page, which names each league
with its id, then the sportscontent API for every league whose name says NBL
or Australia, one request a second. DraftKings lists a league only while it has
offers (EuroLeague, 2026-11-13), so run it on a day with NBL games on the board.

The permission check refused DraftKings site reads from a Claude session
(2026-11-13). It runs from mike's own terminal, from the repo folder:

    python C:/Users/micha/nbl_research/run_with_db.py scripts.nbl_dk_probe

(or `python -m scripts.nbl_dk_probe` with DATABASE_URL set). --no-store prints
without writing.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone

BOOT_URL = "https://sportsbook.draftkings.com/sports/basketball"
LEAGUE_URL = "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusoh/v1/leagues/{league}"
SUB_URL = LEAGUE_URL + "/categories/{cat}/subcategories/{sub}"
PAUSE_S = 1.0
TABLE = "nbl_dk_raw"
COLS = ("fetched_at", "url", "status", "payload")
DDL = """
CREATE TABLE IF NOT EXISTS nbl_dk_raw (
    fetched_at  TIMESTAMPTZ NOT NULL,
    url         TEXT NOT NULL,
    status      INTEGER NOT NULL,
    payload     JSONB,
    PRIMARY KEY (fetched_at, url)
)
"""
# Every league entry on a sports page carries its id and name in one of these
# shapes (read off the tennis page, scripts/tennis_dk_probe.py); the display
# group is not pinned, so any sport's entries are read and filtered by name.
_NAV_A = re.compile(r'"eventGroupId":"?(\d+)"?,"eventGroupName":"([^"]+)"')
_NAV_B = re.compile(r'\{"name":"([^"]+)","displayGroupId":"?\d+"?,"eventGroupId":"?(\d+)"?')
_WANTED = re.compile(r"\bnbl\b|austral", re.I)


def league_ids(page: str) -> dict[str, str]:
    """{league id: name} for every league on the page whose name says NBL or
    Australia. Pure."""
    out: dict[str, str] = {}
    for lid, name in _NAV_A.findall(page):
        out[lid] = name
    for name, lid in _NAV_B.findall(page):
        out.setdefault(lid, name)
    return {k: v for k, v in out.items() if _WANTED.search(v)}


def _store(conn, rows: list[tuple]) -> None:
    from data.anon_readable import API_ROLES, lock_down
    from data.ddl_guard import schema_is_current
    if not schema_is_current(conn, TABLE, columns=COLS, rls=True, revoked_from=API_ROLES):
        conn.execute(DDL)
        lock_down(conn, TABLE)
    conn.executemany(f"INSERT INTO {TABLE} (fetched_at, url, status, payload) "
                     f"VALUES (%s, %s, %s, %s::jsonb) ON CONFLICT DO NOTHING", rows)
    conn.commit()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Does DraftKings price the NBL?")
    ap.add_argument("--no-store", action="store_true", help="print only")
    ap.add_argument("--league", action="append", default=[],
                    help="also read this DraftKings league id")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    from curl_cffi import requests as cr
    s = cr.Session(impersonate="chrome124")
    rows: list[tuple] = []

    def get(url: str):
        r = s.get(url, timeout=20)
        now = datetime.now(timezone.utc)
        body = None
        try:
            body = r.json()
        except Exception:                                       # noqa: BLE001
            pass
        rows.append((now, url, r.status_code, json.dumps(body) if body is not None else None))
        print(f"  HTTP {r.status_code}, {len(r.content):,} bytes  {url}")
        time.sleep(PAUSE_S)
        return r, body

    r, _ = get(BOOT_URL)
    leagues = league_ids(r.text) if r.status_code == 200 else {}
    for lid in a.league:
        leagues.setdefault(lid, "(asked by id)")
    print(f"basketball navigation: {len(leagues)} NBL/Australia league(s): {leagues or 'none'}")
    for lid, name in leagues.items():
        _, body = get(LEAGUE_URL.format(league=lid))
        if not body:
            continue
        events = body.get("events") or []
        print(f"\n{name} (league {lid}): {len(events)} events")
        for e in events[:12]:
            print("   ", e.get("startEventDate"), e.get("name"), e.get("status"))
        cats = {str(c.get("id")): c.get("name") for c in body.get("categories") or []}
        print("  categories:", cats)
        subs = [(str(sc.get("categoryId")), str(sc.get("id")), sc.get("name"))
                for sc in body.get("subcategories") or []]
        print(f"  {len(subs)} sub-pages:", [f"{cats.get(c)}/{n}" for c, _, n in subs])
        for cat, sub, sname in subs:
            _, sb = get(SUB_URL.format(league=lid, cat=cat, sub=sub))
            if sb:
                print(f"    {cats.get(cat)}/{sname}: {len(sb.get('events') or [])} events, "
                      f"{len(sb.get('markets') or [])} markets, "
                      f"{len(sb.get('selections') or [])} prices")
    if not a.no_store and rows:
        from data.db import get_connection
        with get_connection() as conn:
            _store(conn, rows)
        print(f"\nstored {len(rows)} answers in {TABLE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
