"""Tennis match history from a free archive, stored in Supabase before anything
reads it.

THE ARCHIVE. Jeff Sackmann's tennis_atp and tennis_wta datasets: every
tour-level match (and challengers, qualifying and ITF) with the score, the
round, the surface, both players' ranks, and serve and return counts (aces,
double faults, serve points, first serves in and won, second serves won,
service games, break points saved and faced) from 1991 on. The upstream
repositories answered HTTP 404 on 2026-11-13
(`gh api repos/JeffSackmann/tennis_atp`), so they are read from a public
archival mirror, github.com/Aneeshers/tennis-sackmann-archive, pinned at commit
83733587 (its README: an upstream snapshot taken June 2026).

LICENCE, as stated in the mirror's README: CC BY-NC-SA 4.0 (attribution to Jeff
Sackmann, non-commercial, share-alike). Recorded in docs/sports/tennis.md.

PRICES ARE NOT HERE. tennis-data.co.uk, the usual free source of one price per
match, answered a Cloudflare block ("Sorry, you have been blocked") from mike's
PC on 2026-11-13, and copies of its files are not used. Prices come from the
odds feed's own history (data/ingestors/tennis_odds_history.py).

EVERY ROW CARRIES ITS SOURCE (the repository and commit), so a re-run against
the same pin imports nothing new, and a later pin is a new source rather than a
silent overwrite. The table is worker-only (data/anon_readable).

THE SEASON is the tennis year the event belongs to: the first four characters
of the archive's tourney_id. Never derived from a match date (an event that
starts on 2023-12-31 is the 2024 season).

    python -m data.ingestors.tennis_archive --spool DIR --fetch       # download only
    python -m data.ingestors.tennis_archive --spool DIR --store       # write Supabase
"""
from __future__ import annotations

import argparse
import io
import json
import math
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from loguru import logger

from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current

SACKMANN_REPO = "Aneeshers/tennis-sackmann-archive"
SACKMANN_SHA = "83733587353df8a41f2fd4f516147d5aa83f5a8d"
SOURCE = f"{SACKMANN_REPO}@{SACKMANN_SHA[:8]}"
# Which files are imported. Tour level for both tours from 2000; challengers
# and qualifying (men) and qualifying and ITF (women) from 2010, because a
# qualifier at a Grand Slam has most of their matches there. The women's
# $10k, $15k and $25k ITF levels are left out (257,784 of the 650,915 rows
# parsed on 2026-11-13): no player in a draw the odds feed prices is rated off
# them.
MATCH_FILES = {
    ("ATP", "tour"): ("atp/atp_matches_{year}.csv", 2000, 2026),
    ("ATP", "qual_chall"): ("atp/atp_matches_qual_chall_{year}.csv", 2010, 2026),
    ("WTA", "tour"): ("wta/wta_matches_{year}.csv", 2000, 2026),
    ("WTA", "qual_itf"): ("wta/wta_matches_qual_itf_{year}.csv", 2010, 2026),
}

SKIP_LEVELS = {("WTA", "qual_itf"): {"10", "15", "25"}}

MATCHES = "tennis_archive_matches"
_STAT_COLS = ("w_ace", "w_df", "w_svpt", "w_1stIn", "w_1stWon", "w_2ndWon", "w_SvGms",
              "w_bpSaved", "w_bpFaced", "l_ace", "l_df", "l_svpt", "l_1stIn", "l_1stWon",
              "l_2ndWon", "l_SvGms", "l_bpSaved", "l_bpFaced")
MATCH_COLS = (
    "tour", "file_kind", "season", "tourney_id", "tourney_name", "surface", "draw_size",
    "tourney_level", "tourney_date", "match_num",
    "winner_id", "winner_seed", "winner_entry", "winner_name", "winner_hand", "winner_ht",
    "winner_ioc", "winner_age",
    "loser_id", "loser_seed", "loser_entry", "loser_name", "loser_hand", "loser_ht",
    "loser_ioc", "loser_age",
    "score", "best_of", "round", "minutes",
    *[c.lower() for c in _STAT_COLS],
    "winner_rank", "winner_rank_points", "loser_rank", "loser_rank_points",
    "source",
)
_KEY = tuple(MATCH_COLS.index(c) for c in ("tour", "tourney_id", "match_num", "winner_id", "loser_id"))
_INT_COLS = {"season", "draw_size", "match_num", "winner_id", "loser_id", "best_of"}
_TEXT_COLS = {"tour", "file_kind", "tourney_id", "tourney_name", "surface", "tourney_level",
              "tourney_date", "winner_seed", "winner_entry", "winner_name", "winner_hand",
              "winner_ioc", "loser_seed", "loser_entry", "loser_name", "loser_hand",
              "loser_ioc", "score", "round", "source"}


def _col_type(c: str) -> str:
    if c in _INT_COLS:
        return "INTEGER"
    if c in _TEXT_COLS:
        return "TEXT"
    return "DOUBLE PRECISION"


MATCHES_DDL = (
    f"CREATE TABLE IF NOT EXISTS {MATCHES} (\n"
    + ",\n".join(f"    {c} {_col_type(c)}" for c in MATCH_COLS)
    + ",\n    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),"
    + "\n    PRIMARY KEY (tour, tourney_id, match_num, winner_id, loser_id)\n)"
)
MATCHES_INDEX = "idx_tennis_archive_matches_date"
MATCHES_INDEX_DDL = (f"CREATE INDEX IF NOT EXISTS {MATCHES_INDEX} "
                     f"ON {MATCHES} (tour, tourney_date)")


def ensure_tables(conn) -> None:
    """The archive table, once, locked down (worker-only)."""
    if not schema_is_current(conn, MATCHES, columns=MATCH_COLS, indexes=(MATCHES_INDEX,),
                             rls=True, revoked_from=API_ROLES):
        conn.execute(MATCHES_DDL)
        conn.execute(MATCHES_INDEX_DDL)
        lock_down(conn, MATCHES)
        conn.commit()


# ── fetch ────────────────────────────────────────────────────────────────────

def _raw_url(path: str) -> str:
    return f"https://raw.githubusercontent.com/{SACKMANN_REPO}/{SACKMANN_SHA}/{path}"


def _spool_name(path: str) -> str:
    return "sackmann__" + path.replace("/", "__")


def _jobs():
    for (tour, kind), (tmpl, y0, y1) in MATCH_FILES.items():
        for y in range(y0, y1 + 1):
            yield tour, kind, y, tmpl.format(year=y)


def fetch_all(spool: Path) -> list[Path]:
    """Download every pinned file into `spool`, skipping ones already there."""
    spool.mkdir(parents=True, exist_ok=True)
    got = []
    for _tour, _kind, _y, path in _jobs():
        dest = spool / _spool_name(path)
        if dest.exists() and dest.stat().st_size > 0:
            got.append(dest)
            continue
        r = requests.get(_raw_url(path), timeout=120)
        if r.status_code != 200:
            logger.warning(f"{SOURCE} {path}: HTTP {r.status_code}, skipped")
            continue
        dest.write_bytes(r.content)
        got.append(dest)
    return got


# ── parse ────────────────────────────────────────────────────────────────────

def _clean(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, str) and not v.strip():
        return None
    return v


def _iso_date(s) -> str | None:
    s = _clean(s)
    if s is None:
        return None
    try:
        return datetime.strptime(str(s).strip(), "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def parse_match_file(text: str, tour: str, kind: str) -> list[tuple]:
    """Archive rows -> tuples in MATCH_COLS order, one per key. A row without
    both player ids or a match number cannot be keyed and is dropped."""
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    skip = SKIP_LEVELS.get((tour, kind))
    if skip and "tourney_level" in df.columns:
        df = df[~df["tourney_level"].isin(skip)]
    by_lower = {k.lower(): k for k in df.columns}
    out, seen = [], set()
    for rec in df.to_dict("records"):
        tid = _clean(rec.get("tourney_id"))
        if not tid or not _clean(rec.get("winner_id")) or not _clean(rec.get("loser_id")) \
                or _clean(rec.get("match_num")) is None:
            continue
        row = []
        for c in MATCH_COLS:
            if c == "tour":
                v = tour
            elif c == "file_kind":
                v = kind
            elif c == "season":
                v = int(str(tid)[:4])
            elif c == "source":
                v = SOURCE
            elif c == "tourney_date":
                v = _iso_date(rec.get("tourney_date"))
            else:
                v = _clean(rec.get(by_lower.get(c, c)))
                if v is not None and c not in _TEXT_COLS:
                    try:
                        v = int(float(v)) if c in _INT_COLS else float(v)
                    except ValueError:
                        v = None
            row.append(v)
        key = tuple(row[i] for i in _KEY)
        if None in key or key in seen:
            continue
        seen.add(key)
        out.append(tuple(row))
    return out


# ── store ────────────────────────────────────────────────────────────────────

_MATCH_INSERT = (f"INSERT INTO {MATCHES} ({', '.join(MATCH_COLS)}) VALUES "
                 f"({', '.join(['%s'] * len(MATCH_COLS))}) ON CONFLICT DO NOTHING")


def store_all(conn, spool: Path) -> dict:
    """Parse every spooled file and write it, one commit per 2,000 rows."""
    ensure_tables(conn)
    counts: dict = {}
    for tour, kind, y, path in _jobs():
        f = spool / _spool_name(path)
        if not f.exists():
            continue
        rows = parse_match_file(f.read_text(encoding="utf-8", errors="replace"), tour, kind)
        for i in range(0, len(rows), 2000):
            conn.executemany(_MATCH_INSERT, rows[i:i + 2000])
            conn.commit()
        counts[f"{tour}/{kind}/{y}"] = len(rows)
        logger.info(f"{MATCHES}: {tour} {kind} {y}: {len(rows)} rows")
    return counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Tennis match archive -> Supabase")
    ap.add_argument("--spool", required=True, type=Path)
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--store", action="store_true")
    a = ap.parse_args(argv)
    if a.fetch:
        got = fetch_all(a.spool)
        logger.info(f"{len(got)} files in {a.spool}")
    if a.store:
        from data.db import get_connection
        conn = get_connection()
        try:
            print(json.dumps(store_all(conn, a.spool), indent=1))
        finally:
            conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
