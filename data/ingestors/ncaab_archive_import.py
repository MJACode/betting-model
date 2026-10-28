"""
Free historical college basketball lines, imported into Supabase and matched
onto ESPN's games.

TWO SOURCES
-----------
* The Prediction Tracker (thepredictiontracker.com/ncaabb{yy}.csv, yy = the
  season's FALL year): every lined D-I game since 2003-04 with the opening line
  (from 2004-05), the "updated line" (its last scrape before tip, not a
  verified book close) and about fifteen public rating systems' predicted
  margins. Its sign is the REVERSE of ours: +3 means the HOME team is favoured
  by 3. Stored here in our convention (CLAUDE.md §4: the HOME number, negative
  when home is favoured): spread_home = -line. The systems' numbers are
  predicted HOME margins and are stored as given, under their own names.
* SBRO (sportsbookreviewsonline.com, "will not be updated"): opening and
  closing spreads and totals, moneylines, second-half lines and half scores,
  2007-08 to 2020-21, one xlsx per season. Two rows per game (visitor, home;
  N/N on a neutral court). In each row's Open/Close cell the SMALLER number is
  that side's spread when favoured and the LARGER is the total; "pk" is 0.
  Its 2nd-half score column is REGULATION ONLY (overtime missing), so a
  second-half total graded on it shows a phantom under edge (46.25% overs vs
  50.04% with overtime, SBRO 2015-19); never grade on home_h2/away_h2 alone.

MATCHING ONTO ESPN
------------------
Names differ by source ("Michigan St." vs "Michigan State"), so rows are
matched on what cannot differ: the ET date (within a day) and the two final
scores. The orientation is read off the scores: when the archive's home score
is ESPN's away score, `flipped` is TRUE and oriented() turns the lines round.
Two games on one date with the same two scores fall back to folded team names;
anything still ambiguous stays unmatched (counted, never guessed).

    python -m data.ingestors.ncaab_archive_import --pt 2015 2026 --sbro 2008 2021
    python -m data.ingestors.ncaab_archive_import --match
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import unicodedata
from datetime import date, timedelta

import pandas as pd
import requests
from loguru import logger

from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current

SOURCE = "prediction_tracker"          # the default marker; SBRO rows carry SBRO_SOURCE
PT_SOURCE = SOURCE
SBRO_SOURCE = "sbro"
PT_URL = "https://www.thepredictiontracker.com/ncaabb{yy:02d}.csv"
SBRO_URL = ("https://www.sportsbookreviewsonline.com/wp-content/uploads/"
            "sportsbookreviewsonline_com_737/ncaa-basketball-{a}-{b:02d}.xlsx")
_UA = {"User-Agent": "Mozilla/5.0 (betting-model archive import)"}

TABLE = "ncaab_archive_lines"
COLS = ("row_key", "source", "season", "game_date", "home_name", "away_name", "neutral",
        "home_score", "away_score", "home_h1", "away_h1", "home_h2", "away_h2",
        "open_spread_home", "close_spread_home", "open_total", "close_total",
        "home_ml", "away_ml", "h2_spread_home", "h2_total", "systems",
        "game_id", "flipped", "match_method", "loaded_at")
DDL = """
CREATE TABLE IF NOT EXISTS ncaab_archive_lines (
    row_key            TEXT PRIMARY KEY,
    source             TEXT NOT NULL,
    season             INTEGER NOT NULL,
    game_date          TEXT NOT NULL,
    home_name          TEXT,
    away_name          TEXT,
    neutral            BOOLEAN,
    home_score         INTEGER,
    away_score         INTEGER,
    home_h1            INTEGER,
    away_h1            INTEGER,
    home_h2            INTEGER,
    away_h2            INTEGER,
    open_spread_home   REAL,
    close_spread_home  REAL,
    open_total         REAL,
    close_total        REAL,
    home_ml            INTEGER,
    away_ml            INTEGER,
    h2_spread_home     REAL,
    h2_total           REAL,
    systems            JSONB,
    game_id            TEXT,
    flipped            BOOLEAN,
    match_method       TEXT,
    loaded_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""
INDEX = "CREATE INDEX IF NOT EXISTS idx_ncaab_archive_game ON ncaab_archive_lines (game_id)"

# PT columns that are not systems.
_PT_FIXED = {"date", "home", "hscore", "road", "rscore", "line", "lineopen", "neutral", "std"}


def ensure_table(conn) -> None:
    if schema_is_current(conn, TABLE, columns=COLS, indexes=("idx_ncaab_archive_game",),
                         rls=True, revoked_from=API_ROLES):
        return
    conn.execute(DDL)
    conn.execute(INDEX)
    lock_down(conn, TABLE)
    conn.commit()


def _f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(x) else x


def _i(v):
    x = _f(v)
    return None if x is None else int(round(x))


def _key(*parts) -> str:
    return "|".join(str(p) for p in parts)


# ── The Prediction Tracker ───────────────────────────────────────────────────

def pt_rows(df: pd.DataFrame, season: int) -> list[dict]:
    """Rows in our sign convention. A line further than 60 points from zero is
    a corrupt scrape (2021-22 holds one at -489) and is dropped to NULL."""
    out = []
    for rec in df.to_dict("records"):
        raw_date = str(rec.get("date") or "").strip()
        try:
            m, d, y = raw_date.split("/")
            gd = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
        except ValueError:
            continue
        line, lopen = _f(rec.get("line")), _f(rec.get("lineopen"))
        line = None if (line is None or abs(line) > 60) else line
        lopen = None if (lopen is None or abs(lopen) > 60) else lopen
        systems = {k: _f(v) for k, v in rec.items()
                   if k not in _PT_FIXED and _f(v) is not None}
        home, away = str(rec.get("home") or "").strip(), str(rec.get("road") or "").strip()
        out.append({
            "row_key": _key(PT_SOURCE, gd, home, away), "source": PT_SOURCE, "season": season,
            "game_date": gd, "home_name": home, "away_name": away,
            "neutral": bool(_i(rec.get("neutral")) or 0),
            "home_score": _i(rec.get("hscore")), "away_score": _i(rec.get("rscore")),
            "home_h1": None, "away_h1": None, "home_h2": None, "away_h2": None,
            "open_spread_home": None if lopen is None else -lopen,
            "close_spread_home": None if line is None else -line,
            "open_total": None, "close_total": None, "home_ml": None, "away_ml": None,
            "h2_spread_home": None, "h2_total": None,
            "systems": json.dumps(systems) if systems else None,
        })
    return _dedupe(out)


def fetch_pt(season: int) -> pd.DataFrame | None:
    """season is the ENDING year; the file is named by the fall year."""
    r = requests.get(PT_URL.format(yy=(season - 1) % 100), headers=_UA, timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text))


# ── SBRO ─────────────────────────────────────────────────────────────────────

def _sbro_num(v):
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("pk", "pick", "p"):
            return 0.0
        if s in ("", "nl", "-", "x"):
            return None
    return _f(v)


def _split_spread_total(v_cell, h_cell):
    """(spread_home, total) from the visitor and home Open/Close cells."""
    cv, ch = _sbro_num(v_cell), _sbro_num(h_cell)
    if cv is None or ch is None:
        return None, None
    if ch < cv:
        spread_home, total = -ch, cv      # home favoured by ch
    else:
        spread_home, total = cv, ch       # visitor favoured by cv -> home +cv
    if total < 90 or abs(spread_home) > 60:
        return None, None
    return spread_home, total


def sbro_rows(df: pd.DataFrame, season: int) -> list[dict]:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    out = []
    recs = df.to_dict("records")
    for i in range(0, len(recs) - 1, 2):
        v, h = recs[i], recs[i + 1]
        vh_v, vh_h = str(v.get("VH", "")).strip(), str(h.get("VH", "")).strip()
        if vh_v not in ("V", "N") or vh_h not in ("H", "N"):
            continue
        try:
            mmdd = int(float(v.get("Date")))
        except (TypeError, ValueError):
            continue
        m, d = divmod(mmdd, 100)
        y = season - 1 if m >= 8 else season
        try:
            gd = date(y, m, d).isoformat()
        except ValueError:
            continue
        o_sp, o_tot = _split_spread_total(v.get("Open"), h.get("Open"))
        c_sp, c_tot = _split_spread_total(v.get("Close"), h.get("Close"))
        h2_sp, h2_tot = _split_spread_total(v.get("2H"), h.get("2H"))
        home, away = str(h.get("Team") or "").strip(), str(v.get("Team") or "").strip()
        out.append({
            "row_key": _key(SBRO_SOURCE, gd, home, away), "source": SBRO_SOURCE,
            "season": season, "game_date": gd, "home_name": home, "away_name": away,
            "neutral": vh_h == "N",
            "home_score": _i(h.get("Final")), "away_score": _i(v.get("Final")),
            "home_h1": _i(h.get("1st")), "away_h1": _i(v.get("1st")),
            "home_h2": _i(h.get("2nd")), "away_h2": _i(v.get("2nd")),
            "open_spread_home": o_sp, "close_spread_home": c_sp,
            "open_total": o_tot, "close_total": c_tot,
            "home_ml": _i(_sbro_num(h.get("ML"))), "away_ml": _i(_sbro_num(v.get("ML"))),
            "h2_spread_home": h2_sp, "h2_total": h2_tot, "systems": None,
        })
    return _dedupe(out)


def fetch_sbro(season: int) -> pd.DataFrame | None:
    r = requests.get(SBRO_URL.format(a=season - 1, b=season % 100), headers=_UA, timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return pd.read_excel(io.BytesIO(r.content))


def _dedupe(rows: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        if r["row_key"] not in seen:
            seen.add(r["row_key"])
            out.append(r)
    return out


# ── writes ───────────────────────────────────────────────────────────────────

_WRITE_COLS = [c for c in COLS if c not in ("game_id", "flipped", "match_method", "loaded_at")]
_UPSERT = (
    f"INSERT INTO {TABLE} (" + ", ".join(_WRITE_COLS) + ") VALUES ("
    + ", ".join(f"%({c})s" for c in _WRITE_COLS) + ") ON CONFLICT (row_key) DO UPDATE SET "
    + ", ".join(f"{c} = EXCLUDED.{c}" for c in _WRITE_COLS if c != "row_key")
    + ", loaded_at = NOW()")


def stored_seasons(conn, source: str) -> set[int]:
    """Seasons already imported under `source` (the resume key)."""
    return {int(r[0]) for r in conn.execute(
        f"SELECT DISTINCT season FROM {TABLE} WHERE source = %s", (source,)).fetchall()}


def write_rows(conn, rows: list[dict]) -> int:
    for i in range(0, len(rows), 2000):
        conn.executemany(_UPSERT, rows[i:i + 2000])
    conn.commit()
    return len(rows)


# ── matching ─────────────────────────────────────────────────────────────────

def _fold(v: str) -> str:
    v = unicodedata.normalize("NFKD", (v or "").lower())
    v = "".join(c for c in v if not unicodedata.combining(c))
    v = re.sub(r"\bst\b\.?", "state", v)
    v = re.sub(r"[^a-z0-9]+", "", v)
    return v


def _name_score(a: str, b: str) -> int:
    fa, fb = _fold(a), _fold(b)
    if not fa or not fb:
        return 0
    if fa == fb:
        return 3
    if fa.startswith(fb) or fb.startswith(fa):
        return 2
    return 1 if (fa[:4] == fb[:4]) else 0


def match_rows(archive: list[dict], games: list[dict]) -> list[tuple]:
    """[(row_key, game_id, flipped, method)] for each archive row that matches.

    archive dicts: row_key, game_date, home_name, away_name, home_score,
    away_score. games dicts: game_id, game_date, home_team, away_team,
    home_score, away_score (scored NCAAB games).
    """
    by_day: dict[str, list[dict]] = {}
    for g in games:
        if g["home_score"] is None or g["away_score"] is None:
            continue
        by_day.setdefault(g["game_date"], []).append(g)
    out = []
    for a in archive:
        if a["home_score"] is None or a["away_score"] is None:
            continue
        try:
            day = date.fromisoformat(a["game_date"])
        except ValueError:
            continue
        cands = []
        for off in (0, -1, 1):
            for g in by_day.get((day + timedelta(days=off)).isoformat(), []):
                hs, as_ = int(g["home_score"]), int(g["away_score"])
                if (hs, as_) == (a["home_score"], a["away_score"]):
                    cands.append((g, False, off))
                elif (as_, hs) == (a["home_score"], a["away_score"]):
                    cands.append((g, True, off))
        if not cands:
            continue
        if len(cands) == 1:
            g, flipped, off = cands[0]
            out.append((a["row_key"], g["game_id"], flipped, "scores" if off == 0 else "scores_pm1"))
            continue

        def score(c):
            g, flipped, off = c
            h, aw = (g["away_team"], g["home_team"]) if flipped else (g["home_team"], g["away_team"])
            return (_name_score(a["home_name"], h) + _name_score(a["away_name"], aw), -abs(off))
        cands.sort(key=score, reverse=True)
        if score(cands[0]) > score(cands[1]) and score(cands[0])[0] >= 2:
            g, flipped, _ = cands[0]
            out.append((a["row_key"], g["game_id"], flipped, "scores_names"))
    return out


def oriented(row: dict) -> dict:
    """An archive row's lines in ESPN's orientation (the stored game's home)."""
    if not row.get("flipped"):
        return dict(row)
    r = dict(row)
    for k in ("open_spread_home", "close_spread_home", "h2_spread_home"):
        if r.get(k) is not None:
            r[k] = -r[k]
    for a, b in (("home_ml", "away_ml"), ("home_score", "away_score"),
                 ("home_h1", "away_h1"), ("home_h2", "away_h2"),
                 ("home_name", "away_name")):
        r[a], r[b] = row.get(b), row.get(a)
    return r


def run_match(conn, seasons: tuple[int, int] | None = None) -> dict:
    where, params = "", ()
    if seasons:
        where, params = " AND season BETWEEN %s AND %s", tuple(seasons)
    archive = [dict(zip(("row_key", "game_date", "home_name", "away_name",
                         "home_score", "away_score", "season"), r))
               for r in conn.execute(
                   f"SELECT row_key, game_date, home_name, away_name, home_score, away_score, "
                   f"season FROM {TABLE} WHERE game_id IS NULL{where}", params).fetchall()]
    if not archive:
        return {"unmatched_before": 0, "matched": 0}
    lo = min(a["season"] for a in archive)
    hi = max(a["season"] for a in archive)
    games = [dict(zip(("game_id", "game_date", "home_team", "away_team",
                       "home_score", "away_score"), r))
             for r in conn.execute(
                 "SELECT game_id, game_date, home_team, away_team, home_score, away_score "
                 "FROM games WHERE sport = 'NCAAB' AND season BETWEEN %s AND %s "
                 "AND home_score IS NOT NULL", (lo, hi)).fetchall()]
    hits = match_rows(archive, games)
    conn.executemany(
        f"UPDATE {TABLE} SET game_id = %s, flipped = %s, match_method = %s WHERE row_key = %s",
        [(gid, fl, m, k) for k, gid, fl, m in hits])
    conn.commit()
    return {"unmatched_before": len(archive), "matched": len(hits),
            "still_unmatched": len(archive) - len(hits), "games_considered": len(games)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Import free NCAAB line archives into Supabase")
    ap.add_argument("--pt", nargs=2, type=int, metavar=("FIRST", "LAST"),
                    help="Prediction Tracker, ending-year seasons (2026 = 2025-26)")
    ap.add_argument("--sbro", nargs=2, type=int, metavar=("FIRST", "LAST"),
                    help="SBRO, ending-year seasons (2008 = 2007-08 .. 2021 = 2020-21)")
    ap.add_argument("--match", action="store_true", help="match unmatched rows onto games")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    from data.db import get_connection
    conn = get_connection()
    try:
        ensure_table(conn)
        for flag, src, fetch, parse in (("pt", PT_SOURCE, fetch_pt, pt_rows),
                                        ("sbro", SBRO_SOURCE, fetch_sbro, sbro_rows)):
            span = getattr(args, flag)
            if not span:
                continue
            have = stored_seasons(conn, src)
            for s in range(span[0], span[1] + 1):
                if s in have and not args.force:
                    print(f"{src} {s}: already stored")
                    continue
                df = fetch(s)
                if df is None:
                    print(f"{src} {s}: not published")
                    continue
                n = write_rows(conn, parse(df, s))
                print(f"{src} {s}: {n} rows")
                logger.info(f"ncaab_archive_import {src} {s}: {n} rows")
        if args.match:
            print(f"match: {run_match(conn)}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
