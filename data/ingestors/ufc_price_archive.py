"""Free historical UFC prices, stored in Supabase before anything models on them.

WHY. The UFC model search of 2026-11-13 (docs/ufc_market_audit.md) priced
every fight since 2010 off two free public archives. Both were read from
local downloads first; this importer is what puts them where every dataset
here has to live (CLAUDE.md section 1b: everything goes in Supabase).

THE TWO SOURCES (each row keeps its `source`, so a re-run imports nothing twice):

  * SOURCE_BFO, "bfo_fight_canon_db": the fight-canon-db SQLite release
    (github.com/Jadevit/fight-canon-db, MIT, rebuilt daily from
    BestFightOdds). One row per fighter per fight: the opening price (the
    first book to post), and the lowest and highest closing price across the
    books BestFightOdds lists. UFC from 2007; 8,138 UFC fights carry prices
    (measured 2026-11-13 on the 2026-11-12 release).
  * SOURCE_UUD, "ultimate_ufc_dataset": ufc-master.csv
    (github.com/shortlikeafox/ultimate_ufc_dataset, CC BY 4.0). One price per
    fighter for the fight and for each method of victory (decision, KO/TKO,
    submission), near the close. 7,177 fights 2010-2026; method prices from
    2012.

THE MATCH. Each fight is placed on our own ufc_fight_log game id by the
unordered pair of accent-folded fighter slugs within two days, the rule the
UFC settlement already uses (tracking/paper_tracker._settle_ufc_picks). An
archive fight that matches nothing is stored with game_id NULL rather than
dropped: it is still paid-for-in-time data, and a later alias fixes it.

    python -m data.ingestors.ufc_price_archive --canon PATH\\canon.db \\
        --uud PATH\\ufc-master.csv            # parse and report, write nothing
    ... --store                                # write to Supabase

The files are third-party downloads: they are opened read-only and parsed as
data, never imported or executed.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import unicodedata
from collections import defaultdict
from datetime import date, timedelta

from loguru import logger

from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current

SOURCE_BFO = "bfo_fight_canon_db"
SOURCE_UUD = "ultimate_ufc_dataset"
MATCH_DAYS = 2

TABLE = "ufc_price_archive"
COLS = ("source", "source_fight_id", "fight_date", "fighter_slug", "opponent_slug",
        "game_id", "market", "price_open", "close_low", "close_high", "price",
        "imported_at")
DDL = """
CREATE TABLE IF NOT EXISTS ufc_price_archive (
    source           TEXT NOT NULL,
    source_fight_id  TEXT NOT NULL,
    fight_date       DATE NOT NULL,
    fighter_slug     TEXT NOT NULL,
    opponent_slug    TEXT NOT NULL,
    game_id          TEXT,
    market           TEXT NOT NULL,
    price_open       INTEGER,
    close_low        INTEGER,
    close_high       INTEGER,
    price            INTEGER,
    imported_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source, source_fight_id, fighter_slug, market)
)
"""
INDEX = "ufc_price_archive_game_idx"
INDEX_DDL = f"CREATE INDEX IF NOT EXISTS {INDEX} ON ufc_price_archive (game_id)"

# market labels: the fight itself, and each method of victory BY this fighter
MARKETS_UUD = {"h2h": ("R_odds", "B_odds"),
               "method_decision": ("r_dec_odds", "b_dec_odds"),
               "method_ko_tko": ("r_ko_odds", "b_ko_odds"),
               "method_submission": ("r_sub_odds", "b_sub_odds")}


def slugify(name: str) -> str:
    """The fighter slug every UFC table here keys on (accents folded)."""
    n = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")


def american(value) -> int | None:
    """An American price as an int, or None for a blank, zero or junk cell."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v != v or abs(v) < 100:
        return None
    return int(round(v))


def ensure_tables(conn) -> None:
    if not schema_is_current(conn, TABLE, columns=COLS, indexes=(INDEX,), rls=True,
                             revoked_from=API_ROLES):
        conn.execute(DDL)
        conn.execute(INDEX_DDL)
        lock_down(conn, TABLE)
        conn.commit()


# ── parsing ──────────────────────────────────────────────────────────────────

def parse_canon(path: str) -> list[dict]:
    """UFC fights with a BestFightOdds row from the fight-canon-db SQLite file."""
    uri = "file:" + str(path).replace("\\", "/") + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        rows = con.execute("""
            SELECT f.fight_id, e.date, fr.name, o.open, o.close_low, o.close_high
              FROM fights f
              JOIN events e ON e.event_id = f.event_id
              JOIN fight_participants fp ON fp.fight_id = f.fight_id
              JOIN fighters fr ON fr.fighter_id = fp.fighter_id
              LEFT JOIN odds o ON o.fight_id = f.fight_id AND o.fighter_id = fp.fighter_id
                               AND o.book = 'all'
             WHERE e.promotion = 'UFC' AND e.date IS NOT NULL
        """).fetchall()
    finally:
        con.close()
    by_fight: dict = defaultdict(list)
    for fight_id, d, name, op, lo, hi in rows:
        by_fight[(fight_id, d)].append((slugify(name), american(op), american(lo), american(hi)))
    out = []
    for (fight_id, d), sides in by_fight.items():
        if len(sides) != 2:
            continue
        (sa, *pa), (sb, *pb) = sides
        if all(v is None for v in (*pa, *pb)):
            continue
        for me, opp, (op, lo, hi) in ((sa, sb, pa), (sb, sa, pb)):
            out.append(dict(source=SOURCE_BFO, source_fight_id=str(fight_id), fight_date=d,
                            fighter_slug=me, opponent_slug=opp, market="h2h",
                            price_open=op, close_low=lo, close_high=hi, price=None))
    return out


def parse_uud(path: str) -> list[dict]:
    """ufc-master.csv: a fight price and three method prices per fighter."""
    import csv
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            d = (row.get("date") or "").strip()[:10]
            r, b = slugify(row.get("R_fighter", "")), slugify(row.get("B_fighter", ""))
            if not d or not r or not b:
                continue
            fid = f"{d}|{min(r, b)}|{max(r, b)}"
            for market, (rc, bc) in MARKETS_UUD.items():
                for me, opp, col in ((r, b, rc), (b, r, bc)):
                    p = american(row.get(col))
                    if p is None:
                        continue
                    out.append(dict(source=SOURCE_UUD, source_fight_id=fid, fight_date=d,
                                    fighter_slug=me, opponent_slug=opp, market=market,
                                    price_open=None, close_low=None, close_high=None, price=p))
    return out


def attach_game_ids(rows: list[dict], fights: list[tuple[str, str, str, str]]) -> int:
    """Set game_id on each row from (game_id, date, slug, slug) of our fight log.
    Returns how many distinct archive fights matched."""
    idx: dict = defaultdict(list)
    for gid, d, s1, s2 in fights:
        idx[frozenset((s1, s2))].append((date.fromisoformat(str(d)[:10]), gid))
    matched = set()
    for r in rows:
        want = date.fromisoformat(str(r["fight_date"])[:10])
        r["game_id"] = None
        for d, gid in idx.get(frozenset((r["fighter_slug"], r["opponent_slug"])), []):
            if abs((d - want).days) <= MATCH_DAYS:
                r["game_id"] = gid
                matched.add((r["source"], r["source_fight_id"]))
                break
    return len(matched)


def _fight_log(conn) -> list[tuple[str, str, str, str]]:
    rows = conn.execute("""
        SELECT game_id, MIN(game_date), MIN(fighter_name), MAX(fighter_name)
          FROM ufc_fight_log GROUP BY game_id
    """).fetchall()
    return [(g, d, slugify(a), slugify(b)) for g, d, a, b in rows]


def store(conn, rows: list[dict]) -> int:
    ensure_tables(conn)
    cols = [c for c in COLS if c != "imported_at"]
    sql = (f"INSERT INTO {TABLE} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "
           "ON CONFLICT (source, source_fight_id, fighter_slug, market) DO NOTHING")
    before = conn.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0]
    for i in range(0, len(rows), 2000):
        conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows[i:i + 2000]])
        conn.commit()
    after = conn.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0]
    return after - before


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--canon", help="path to fight-canon-db canon.db")
    ap.add_argument("--uud", help="path to ultimate_ufc_dataset ufc-master.csv")
    ap.add_argument("--store", action="store_true", help="write to Supabase")
    a = ap.parse_args()
    rows: list[dict] = []
    if a.canon:
        rows += parse_canon(a.canon)
    if a.uud:
        rows += parse_uud(a.uud)
    from data.db import get_connection
    conn = get_connection()
    try:
        n = attach_game_ids(rows, _fight_log(conn))
        fights = len({(r["source"], r["source_fight_id"]) for r in rows})
        logger.info(f"{len(rows)} price rows over {fights} archive fights; {n} placed on our fight log")
        if a.store:
            logger.success(f"stored {store(conn, rows)} new rows in {TABLE}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
