"""NBA opening and closing lines, 2018-19 and 2019-20, from the Sportsbook Reviews Online archive — free.

WHY. `odds` holds no NBA price on any game before 2020-10-01 (measured
2026-10-16: zero rows for the 2,289 games of seasons 2019 and 2020). The
game-market search wants a closing line on those seasons as SUPPORTING evidence
for its closing-line-only checks. These rows are never a bar: nothing in them
was bettable at a known price.

THE PAGE. One HTML table per season, two rows per game (visitor, then home;
both rows say `N` at a neutral site, e.g. the 2020 bubble):

    col 0 Date (MMDD, no year)  1 Rot  2 V/H/N  3 Team (no spaces: "GoldenState")
    4-7 quarter points  8 Final  9 Open  10 Close  11 ML  12 2H

Open and Close each hold TWO numbers per game, one per row: the FAVOURITE's row
carries the spread as a positive number ("pk" = 0), the other row carries the
total. Which row is which is decided per column, because the favourite can
change between the open and the close. So:

    spread on the HOME row     -> spread_home = -value   (home favourite)
    spread on the VISITOR row  -> spread_home = +value   (away favourite)

A column whose two numbers are not exactly one spread (0-40) and one total
(150-300) is refused for that game and counted, never guessed: two 2019-20
openers read "1105" and "1111".

ML is ONE moneyline per team with no open/close label. It is stored as `close`
because it agrees with the closing spread's favourite far more often than with
the opening one (measured by `validate`, reported as ml_follows_close /
ml_follows_open on the games where the favourite changed). The page carries no
price for a spread or a total, so those rows have NULL prices — nothing here
invents a -110.

STORED in `odds` the way the NHL archive is (data/ingestors/nhl_sbr_archive.py,
the same site): `bookmaker = 'sbr_consensus'` (protected from the daily prune by
data/prune_odds.PROTECTED_BOOKMAKERS), `source = 'sbr_archive_nba'`.
`snapshot_at` is SYNTHETIC because the page gives no time:

    open   -> the game date at 12:00Z          ("2019-01-15T12:00:00Z")
    close  -> games.commence_time minus 1 minute, in the `Z` form

A re-run writes nothing already stored: rows are keyed (game_id, market,
snapshot_type) within this source, and what is stored is read back by game_id
(indexed), never by scanning `odds` for the source.

AN UNMAPPED TEAM NAME IS A REFUSAL, never a guess.

    python -m data.ingestors.nba_sbr_archive                     # parse + validate, write nothing
    python -m data.ingestors.nba_sbr_archive --apply
    python -m data.ingestors.nba_sbr_archive --sign-sample 20    # stored rows against the page
    python -m data.ingestors.nba_sbr_archive --html-dir <dir>    # read <slug>.html instead of fetching
"""
from __future__ import annotations

import argparse
import io
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
from loguru import logger

BASE = "https://www.sportsbookreviewsonline.com/scoresoddsarchives/"
# slug -> the calendar year its first game falls in. `games` holds NBA seasons
# from 2019 (2018-19) on, and 2020-21 onward already has priced history
# (source odds_api_historical), so these two are the whole gap.
PAGES = {"nba-odds-2018-19": 2018, "nba-odds-2019-20": 2019}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
SOURCE = "sbr_archive_nba"
BOOK = "sbr_consensus"

SPREAD_MAX = 40.0
TOTAL_MIN, TOTAL_MAX = 150.0, 300.0

# The page's spellings (spaces removed by the site) -> the abbreviation `games` uses.
NBA_NAMES = {
    "Atlanta": "ATL", "Boston": "BOS", "Brooklyn": "BKN", "Charlotte": "CHA",
    "Chicago": "CHI", "Cleveland": "CLE", "Dallas": "DAL", "Denver": "DEN",
    "Detroit": "DET", "GoldenState": "GSW", "Houston": "HOU", "Indiana": "IND",
    "LAClippers": "LAC", "LALakers": "LAL", "Memphis": "MEM", "Miami": "MIA",
    "Milwaukee": "MIL", "Minnesota": "MIN", "NewOrleans": "NOP", "NewYork": "NYK",
    "OklahomaCity": "OKC", "Orlando": "ORL", "Philadelphia": "PHI", "Phoenix": "PHX",
    "Portland": "POR", "Sacramento": "SAC", "SanAntonio": "SAS", "Toronto": "TOR",
    "Utah": "UTA", "Washington": "WAS",
}


def _fold(name) -> str:
    return "".join(c for c in str(name or "").lower() if c.isalnum())


_NAMES = {_fold(k): v for k, v in NBA_NAMES.items()}


def team(name) -> str | None:
    return _NAMES.get(_fold(name))


def _num(v) -> float | None:
    s = str(v).strip()
    if s.lower() in ("pk", "pick", "pickem"):
        return 0.0
    try:
        f = float(s.replace("½", ".5"))
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def _price(v) -> int | None:
    f = _num(v)
    return None if f is None or abs(f) < 100 else int(f)


def classify(v_cell, h_cell) -> tuple[float | None, float | None]:
    """(spread_home, total) from one column's visitor and home cells.

    Exactly one cell must read as a spread (0-40, "pk" = 0) and the other as a
    total (150-300); anything else returns (None, None) and is counted by the
    caller. The spread sits on the favourite's row, so a spread on the home row
    is the home team laying points (negative), on the visitor row the home team
    getting them (positive)."""
    v, h = _num(v_cell), _num(h_cell)
    if v is None or h is None:
        return None, None
    v_spread, h_spread = 0 <= v <= SPREAD_MAX, 0 <= h <= SPREAD_MAX
    v_total, h_total = TOTAL_MIN <= v <= TOTAL_MAX, TOTAL_MIN <= h <= TOTAL_MAX
    if h_spread and v_total:
        return (-h if h else 0.0), v
    if v_spread and h_total:
        return v, h
    return None, None


def parse_season(html: str, first_year: int) -> tuple[list[dict], list[str], dict]:
    """(games, unmapped team names, counts of refused cells). Rows pair in page order."""
    table = max(pd.read_html(io.StringIO(html), header=None), key=len)
    rows = [r for r in table.values.tolist() if str(r[0]).strip().isdigit()]
    games, unknown = [], set()
    bad = {"pairing": 0, "open_refused": 0, "close_refused": 0, "ml_missing": 0}
    year, last_month = first_year, None
    season = first_year + 1
    for i in range(0, len(rows) - 1, 2):
        v, h = rows[i], rows[i + 1]
        vh = (str(v[2]).strip().upper(), str(h[2]).strip().upper())
        rot_ok = _num(h[1]) is not None and _num(v[1]) is not None and _num(h[1]) == _num(v[1]) + 1
        if vh not in (("V", "H"), ("N", "N")) or not rot_ok or str(v[0]).strip() != str(h[0]).strip():
            bad["pairing"] += 1
            continue
        mmdd = str(v[0]).strip().zfill(4)
        month, day = int(mmdd[:2]), int(mmdd[2:])
        if last_month is not None and month < last_month and last_month >= 10:
            year += 1                       # December -> January
        last_month = month
        away, home = team(v[3]), team(h[3])
        for raw, t in ((v[3], away), (h[3], home)):
            if t is None:
                unknown.add(str(raw))
        if away is None or home is None:
            continue
        sp_open, tot_open = classify(v[9], h[9])
        sp_close, tot_close = classify(v[10], h[10])
        bad["open_refused"] += sp_open is None
        bad["close_refused"] += sp_close is None
        ml_h, ml_a = _price(h[11]), _price(v[11])
        bad["ml_missing"] += ml_h is None or ml_a is None
        date = f"{year:04d}-{month:02d}-{day:02d}"
        games.append({
            "date": date, "season": season, "neutral": vh == ("N", "N"),
            "away": away, "home": home, "rot_away": int(_num(v[1])),
            "away_final": _num(v[8]), "home_final": _num(h[8]),
            "spread_open": sp_open, "total_open": tot_open,
            "spread_close": sp_close, "total_close": tot_close,
            "ml_home": ml_h, "ml_away": ml_a,
            "raw_away": [str(x) for x in v[:12]], "raw_home": [str(x) for x in h[:12]],
        })
    return games, sorted(unknown), bad


def fetch_all(html_dir: str | None = None) -> tuple[list[dict], list[str], dict]:
    games, unknown, bad = [], [], {}
    for slug, first_year in PAGES.items():
        if html_dir:
            html = (Path(html_dir) / f"{slug}.html").read_text(encoding="utf-8", errors="replace")
        else:
            r = requests.get(BASE + slug + "/", headers=UA, timeout=90)
            r.raise_for_status()
            html = r.text
        g, u, b = parse_season(html, first_year)
        logger.info(f"{slug}: {len(g):,} games parsed, refused {b}" + (f", unmapped {u}" if u else ""))
        games += g
        unknown += u
        for k, n in b.items():
            bad[k] = bad.get(k, 0) + n
    return games, sorted(set(unknown)), bad


def _swap(g: dict) -> dict:
    """The same game with the two rows' roles exchanged (a neutral-site pair the
    page lists in the other order from `games`)."""
    s = dict(g)
    s["away"], s["home"] = g["home"], g["away"]
    s["away_final"], s["home_final"] = g["home_final"], g["away_final"]
    for k in ("spread_open", "spread_close"):
        s[k] = -g[k] if g[k] else g[k]
    s["ml_home"], s["ml_away"] = g["ml_away"], g["ml_home"]
    s["raw_away"], s["raw_home"] = g["raw_home"], g["raw_away"]
    return s


def _gid(g: dict) -> str:
    return f"NBA_{g['date']}_{g['away']}_{g['home']}"


def match(games: list[dict], known: dict) -> tuple[list[dict], dict]:
    """Attach `game_id` + `commence_time` from `games`; keep only games whose
    final score agrees, which is what proves the home/away orientation.

    `known`: game_id -> (home_score, away_score, commence_time, season)."""
    out, n = [], {"direct": 0, "neutral_swapped": 0, "unmatched": 0,
                  "score_disagrees": 0, "labelled_but_swapped": 0}
    for g in games:
        cand = g
        if _gid(g) not in known:
            s = _swap(g)
            if _gid(s) in known:
                if not g["neutral"]:
                    n["labelled_but_swapped"] += 1
                    continue
                cand = s
                n["neutral_swapped"] += 1
            else:
                n["unmatched"] += 1
                continue
        else:
            n["direct"] += 1
        hs, as_, ct, _season = known[_gid(cand)]
        if hs is None or float(hs) != cand["home_final"] or float(as_) != cand["away_final"]:
            n["score_disagrees"] += 1
            continue
        out.append({**cand, "game_id": _gid(cand), "commence_time": ct})
    return out, n


def ml_timing(games: list[dict]) -> dict:
    """Does the single ML column follow the OPEN or the CLOSE favourite?
    Counted only where the two spreads name different favourites."""
    follows_open = follows_close = 0
    for g in games:
        so, sc, mh, ma = g["spread_open"], g["spread_close"], g["ml_home"], g["ml_away"]
        if not so or not sc or mh is None or ma is None or mh == ma or (so < 0) == (sc < 0):
            continue
        ml_home_fav = mh < ma
        follows_close += ml_home_fav == (sc < 0)
        follows_open += ml_home_fav == (so < 0)
    return {"favourite_changed": follows_open + follows_close,
            "ml_follows_close": follows_close, "ml_follows_open": follows_open}


def sign_agreement(games: list[dict]) -> dict:
    """Closing spread sign against the moneyline favourite (independent columns)."""
    agree = disagree = 0
    for g in games:
        sc, mh, ma = g["spread_close"], g["ml_home"], g["ml_away"]
        if not sc or mh is None or ma is None or mh == ma:
            continue
        if (sc < 0) == (mh < ma):
            agree += 1
        else:
            disagree += 1
    return {"agree": agree, "disagree": disagree}


def iso_z(ts: str) -> str:
    """Any ISO timestamp -> 'YYYY-MM-DDTHH:MM:SSZ' in UTC (the shape `odds` uses)."""
    d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def snapshot_times(game_date: str, commence_time: str) -> dict:
    """Synthetic times: the opener at noon UTC on the game date, the close one
    minute before the stored tip."""
    tip = datetime.fromisoformat(iso_z(commence_time).replace("Z", "+00:00"))
    return {"open": f"{game_date}T12:00:00Z",
            "close": (tip - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")}


def odds_rows(g: dict) -> list[tuple]:
    """(game_id, market, snapshot_type, snapshot_at, home_price, away_price,
    spread_home, total_line, over_price, under_price) for one matched game."""
    t = snapshot_times(g["date"], g["commence_time"])
    gid, rows = g["game_id"], []
    for snap in ("open", "close"):
        if g[f"spread_{snap}"] is not None:
            rows.append((gid, "spreads", snap, t[snap], None, None,
                         g[f"spread_{snap}"], None, None, None))
        if g[f"total_{snap}"] is not None:
            rows.append((gid, "totals", snap, t[snap], None, None,
                         None, g[f"total_{snap}"], None, None))
    if g["ml_home"] is not None and g["ml_away"] is not None:
        rows.append((gid, "h2h", "close", t["close"], g["ml_home"], g["ml_away"],
                     None, None, None, None))
    return rows


def load_known(conn) -> dict:
    return {r[0]: (r[1], r[2], r[3], r[4]) for r in conn.execute(
        "SELECT game_id, home_score, away_score, commence_time, season FROM games "
        "WHERE sport = 'NBA' AND season IN (2019, 2020)").fetchall()}


def stored_keys(conn, game_ids: list[str]) -> set[tuple]:
    """(game_id, market, snapshot_type) already written by THIS source, read by
    game_id (idx_odds_game) — `source` has no index of its own."""
    keys = set()
    for i in range(0, len(game_ids), 300):
        for gid, market, snap in conn.execute(
                "SELECT game_id, market, snapshot_type FROM odds "
                "WHERE game_id = ANY(%s) AND source = %s",
                (game_ids[i:i + 300], SOURCE)).fetchall():
            keys.add((gid, market, snap))
    return keys


def load(conn, matched: list[dict]) -> int:
    stored = stored_keys(conn, sorted({g["game_id"] for g in matched}))
    rows = [r for g in matched for r in odds_rows(g) if (r[0], r[1], r[2]) not in stored]
    sql = """INSERT INTO odds (game_id, sport, market, bookmaker, snapshot_type, snapshot_at,
                 home_price, away_price, spread_home, total_line, over_price, under_price, source)
             VALUES (%s, 'NBA', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
    payload = [(r[0], r[1], BOOK, r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], SOURCE)
               for r in rows]
    for i in range(0, len(payload), 2000):
        conn.executemany(sql, payload[i:i + 2000])
        conn.commit()
        logger.info(f"wrote {min(i + 2000, len(payload)):,}/{len(payload):,}")
    return len(payload)


def sign_sample(conn, matched: list[dict], n: int, seed: int = 20261016) -> list[dict]:
    """`n` random games: the page's two raw rows beside the spread READ BACK from `odds`."""
    pick = random.Random(seed).sample(matched, min(n, len(matched)))
    out = []
    for g in pick:
        stored = {r[0]: r[1] for r in conn.execute(
            "SELECT snapshot_type, spread_home FROM odds WHERE game_id = %s AND market = 'spreads' "
            "AND bookmaker = %s AND source = %s", (g["game_id"], BOOK, SOURCE)).fetchall()}
        out.append({"game_id": g["game_id"],
                    "page_visitor_row": g["raw_away"], "page_home_row": g["raw_home"],
                    "stored_close_spread_home": None if stored.get("close") is None
                    else float(stored["close"]),
                    "stored_open_spread_home": None if stored.get("open") is None
                    else float(stored["open"])})
    return out


if __name__ == "__main__":
    from data.db import get_connection

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--html-dir", default=None)
    ap.add_argument("--sign-sample", type=int, default=0)
    a = ap.parse_args()
    games, unknown, bad = fetch_all(a.html_dir)
    if unknown:
        raise SystemExit(f"REFUSED — team names with no mapping: {unknown}")
    c = get_connection()
    try:
        known = load_known(c)
        matched, n = match(games, known)
        by_season = {}
        for g in matched:
            by_season[g["season"]] = by_season.get(g["season"], 0) + 1
        in_games = {}
        for v in known.values():
            in_games[v[3]] = in_games.get(v[3], 0) + 1
        print({"parsed": len(games), "refused_cells": bad, "match": n,
               "matched_by_season": by_season, "games_by_season": in_games,
               "ml_timing": ml_timing(matched), "close_sign_vs_ml": sign_agreement(matched)})
        thin = {s: f"{by_season.get(s, 0)}/{t}" for s, t in in_games.items()
                if by_season.get(s, 0) / t < 0.95}
        if thin or n["score_disagrees"] > 0.01 * max(len(matched), 1) or n["labelled_but_swapped"]:
            raise SystemExit(f"REFUSED — the archive does not line up with `games` closely "
                             f"enough to trust the parse (thin seasons: {thin}, {n})")
        print("rows written:", load(c, matched) if a.apply else "dry run — nothing written")
        if a.sign_sample:
            for s in sign_sample(c, matched, a.sign_sample):
                print(s)
    finally:
        c.close()
