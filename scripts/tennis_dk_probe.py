"""DraftKings' own tennis board, every level, every market it lists, stored in
Supabase: the bettable price below the odds feed's top tier.

WHY. The odds feed sells only its 53 top-tier tennis tournaments. DraftKings
lists every level: its tennis page of 2026-11-13 named 40 leagues (both Finals,
a 250, a WTA 125, seven Challengers, ten men's and eleven women's ITF events,
the four Grand Slams). A pick on any of them needs DraftKings' own price
(docs/sports/tennis.md, the market grid). mike, 2026-11-13: yes to reading it.

HOW. A browser-style session (the one data/ingestors/dk_live_board.dk_session
uses for the in-play feed) opens the tennis page, which names every tennis
league with its id (`"displayGroupId":6,"eventGroupId":<id>`). Each league's
board comes from the sportscontent API, one request a second: its events (both
players, start, status), its markets and every selection with its American
price. Every selection is stored, whatever its market, so every market
DraftKings offers is kept; a row is written only when a selection's price or
line differs from the last one stored (change-only). The first pass also writes
each raw answer to --out, so the stored rows can be checked against what
DraftKings sent. A refusal ends the pass; three refused passes in a row end the
run.

The permission check refused this read from a Claude session on 2026-11-13,
twice, the second time after mike's yes in chat. It runs from mike's own
terminal (or from a session once his settings allow
"Bash(python -m scripts.tennis_dk_probe:*)"):

    python C:/Users/micha/tennis_research/run_with_db.py scripts.tennis_dk_probe \\
        --out C:/Users/micha/tennis_research/dk_probe --log-until 2026-12-31T00:00:00
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

BOOT_URL = "https://sportsbook.draftkings.com/sports/tennis"
LEAGUE_URL = "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusoh/v1/leagues/{league}"
PAUSE_S = 1.0
SOURCE = "dk_site"
TENNIS_GROUP = "6"          # DraftKings' display group for tennis (its nav, 2026-11-13)

TABLE = "tennis_dk_selections"
COLS = ("selection_id", "seen_at", "league_id", "league_name", "dk_event_id", "event_name",
        "start_time", "event_status", "p1_name", "p2_name", "market_id", "market_name",
        "market_main", "outcome_type", "label", "points", "american", "source")
DDL = """
CREATE TABLE IF NOT EXISTS tennis_dk_selections (
    selection_id   TEXT NOT NULL,
    seen_at        TIMESTAMPTZ NOT NULL,
    league_id      TEXT,
    league_name    TEXT,
    dk_event_id    TEXT,
    event_name     TEXT,
    start_time     TIMESTAMPTZ,
    event_status   TEXT,
    p1_name        TEXT,
    p2_name        TEXT,
    market_id      TEXT,
    market_name    TEXT,
    market_main    BOOLEAN,
    outcome_type   TEXT,
    label          TEXT,
    points         DOUBLE PRECISION,
    american       INTEGER,
    source         TEXT NOT NULL,
    PRIMARY KEY (selection_id, seen_at)
)
"""
INDEX = "idx_tennis_dk_selections_event"
INDEX_DDL = f"CREATE INDEX IF NOT EXISTS {INDEX} ON {TABLE} (dk_event_id, seen_at)"

_NAV_A = re.compile(r'\{"displayGroupId":6,"eventGroupId":(\d+),"eventGroupName":"([^"]+)",'
                    r'"nameIdentifier":"([^"]+)"')
_NAV_B = re.compile(r'\{"name":"([^"]+)","displayGroupId":"6","eventGroupId":"(\d+)",'
                    r'"path":"/leagues/tennis/([a-z0-9%,-]+)"')


def ensure_tables(conn) -> None:
    from data.anon_readable import API_ROLES, lock_down
    from data.ddl_guard import schema_is_current
    if not schema_is_current(conn, TABLE, columns=COLS, indexes=(INDEX,), rls=True,
                             revoked_from=API_ROLES):
        conn.execute(DDL)
        conn.execute(INDEX_DDL)
        lock_down(conn, TABLE)
        conn.commit()


def session():
    from curl_cffi import requests as cr
    return cr.Session(impersonate="chrome124")


def league_ids(page: str) -> dict[str, str]:
    """{league id: league name} for every tennis league the page names, from
    both shapes its embedded state uses (read off the 2026-11-13 page)."""
    out: dict[str, str] = {}
    for lid, name, _slug in _NAV_A.findall(page):
        out[lid] = name
    for name, lid, _slug in _NAV_B.findall(page):
        out.setdefault(lid, name)
    # Singles only: 54 leagues on the 2026-11-13 page, 21 of them doubles.
    return {k: v for k, v in out.items() if "doubles" not in v.lower()}


def _american(sel: dict) -> int | None:
    """DraftKings writes American odds with a Unicode minus (U+2212)."""
    disp = (sel.get("displayOdds") or {}).get("american")
    if isinstance(disp, str):
        try:
            return int(disp.replace("\u2212", "-").replace("+", "").strip())
        except ValueError:
            return None
    return None


def selection_rows(body: dict, league_id: str, league_name: str, seen_at: str) -> list[tuple]:
    """Every selection on one league board, in COLS order. Players are listed
    in DraftKings' own order (sortOrder)."""
    events = {str(e.get("id")): e for e in body.get("events") or []}
    markets = {str(m.get("id")): m for m in body.get("markets") or []}
    out = []
    for s in body.get("selections") or []:
        m = markets.get(str(s.get("marketId")))
        if m is None:
            continue
        e = events.get(str(m.get("eventId"))) or {}
        parts = sorted(e.get("participants") or [], key=lambda p: p.get("sortOrder") or 99)
        p1 = parts[0].get("name") if len(parts) > 0 else None
        p2 = parts[1].get("name") if len(parts) > 1 else None
        pts = s.get("points")
        out.append((
            str(s.get("id")), seen_at, league_id, league_name, str(m.get("eventId")),
            e.get("name"), e.get("startEventDate"), e.get("status"), p1, p2,
            str(m.get("id")), m.get("name"), bool(m.get("main")),
            s.get("outcomeType"), s.get("label"),
            float(pts) if isinstance(pts, (int, float)) else None, _american(s), SOURCE))
    return out


_INSERT = (f"INSERT INTO {TABLE} ({', '.join(COLS)}) VALUES ({', '.join(['%s'] * len(COLS))}) "
           "ON CONFLICT DO NOTHING")


def last_values(conn) -> dict:
    rows = conn.execute(f"SELECT DISTINCT ON (selection_id) selection_id, points, american "
                        f"FROM {TABLE} ORDER BY selection_id, seen_at DESC").fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def one_pass(s, conn, last: dict, out_dir: Path | None) -> dict:
    seen_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    r = s.get(BOOT_URL, timeout=20)
    if out_dir:
        (out_dir / "tennis_page.html").write_text(r.text, encoding="utf-8")
    if r.status_code != 200:
        return {"refused": f"tennis page HTTP {r.status_code}"}
    leagues = league_ids(r.text)
    stored = seen = 0
    for lid, name in leagues.items():
        time.sleep(PAUSE_S)
        x = s.get(LEAGUE_URL.format(league=lid), timeout=20)
        if x.status_code != 200:
            return {"refused": f"league {lid} HTTP {x.status_code}", "leagues": len(leagues),
                    "seen": seen, "stored": stored}
        body = x.json()
        if out_dir:
            (out_dir / f"league_{lid}.json").write_text(json.dumps(body), encoding="utf-8")
        rows = selection_rows(body, lid, name, seen_at)
        seen += len(rows)
        fresh = []
        for row in rows:
            val = (row[15], row[16])
            if last.get(row[0]) != val:
                last[row[0]] = val
                fresh.append(row)
        if fresh and conn is not None:
            conn.executemany(_INSERT, fresh)
            conn.commit()
        stored += len(fresh)
    return {"seen_at": seen_at, "leagues": len(leagues), "seen": seen, "stored": stored}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="DraftKings tennis board -> Supabase")
    ap.add_argument("--out", type=Path, help="write the first pass's raw answers here")
    ap.add_argument("--log-until", help="repeat every --every-min until this UTC time")
    ap.add_argument("--every-min", type=float, default=30)
    ap.add_argument("--no-store", action="store_true", help="read and save raw only")
    a = ap.parse_args(argv)
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
    conn = None
    last: dict = {}
    if not a.no_store:
        from data.db import get_connection
        conn = get_connection()
        ensure_tables(conn)
        last = last_values(conn)
    s = session()
    until = (datetime.fromisoformat(a.log_until).replace(tzinfo=timezone.utc)
             if a.log_until else None)
    refused, first = 0, True
    while True:
        try:
            res = one_pass(s, conn, last, a.out if first else None)
        except Exception as exc:                                    # noqa: BLE001
            res = {"error": f"{type(exc).__name__}: {exc}"[:300]}
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:                                   # noqa: BLE001
                    from data.db import get_connection
                    conn = get_connection()
        print(json.dumps(res), flush=True)
        first = False
        refused = refused + 1 if "refused" in res else 0
        if refused >= 3:
            print("three refused passes in a row: stopping", flush=True)
            return 1
        if until is None or datetime.now(timezone.utc) >= until:
            return 0
        time.sleep(a.every_min * 60)
        s = session()


if __name__ == "__main__":
    raise SystemExit(main())
