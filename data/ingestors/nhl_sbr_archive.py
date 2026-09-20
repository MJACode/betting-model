"""NHL opening and closing lines from the Sportsbook Reviews Online archive — free.

WHY. Until 2026-09-20 `odds` held no NHL price before 2026-07-19, so no NHL
market could be backtested in units, `nhl_over_under` and `nhl_puckline` had
never trained ("no historical total_line / spread_home"), and the one backtest
on record assumed -110 on every game. This archive has, for every game
2017-18 -> 2022-11-27: opening and closing moneyline, a puck line with a price,
opening and closing total with prices, and the score of each period.

It was found by the morning's research and filed as a "fallback" while a
159,900-credit purchase was scheduled for the same information
(docs/rules_evidence.md, "The analysis protocol"). One GET parses a season.

THE PAGE. One HTML table per season, two rows per game (visitor, then home):

    col 0 Date (MMDD, no year)   1 Rot   2 V/H/N   3 Team   4-6 period goals
    7 Final   8 ML open   9 ML close   10 puck line   11 puck-line price
    12 open total   13 its price   14 close total   15 its price

The header names 13 columns and the table has 16, so columns are read BY
POSITION. The visitor row's total price is the OVER, the home row's the UNDER
(checked on load: the side priced shorter must win more often than not).

STORED the way every other archive row is (`sbr_loader.load_to_db`):
`odds.bookmaker = 'sbr_consensus'`, `snapshot_type` open / close,
`snapshot_at` = the game date, so the feature engine and the trainers find the
lines with no new code. `source = 'sbr_archive_nhl'` keys the re-run: a
(game, market, open|close) already stored is skipped. The book behind the
consensus is NOT named by the site.

AN UNMAPPED TEAM NAME IS A REFUSAL, never a three-letter guess — that guess is
how Montreal became `CAN` on 2026-09-20.

    python -m data.ingestors.nhl_sbr_archive                 # parse + validate, write nothing
    python -m data.ingestors.nhl_sbr_archive --apply
"""
from __future__ import annotations

import argparse
import io
import unicodedata

import pandas as pd
import requests
from loguru import logger

from data.db import get_connection
from data.ingestors.sbr_loader import NHL_NAME_MAP
from data.season_labels import nhl_season_label

BASE = "https://www.sportsbookreviewsonline.com/scoresoddsarchives/"
# slug -> the calendar year its first game falls in
# 2017-18 and earlier exist on the site; `games` starts at 2018-19, so there is
# nothing to join them to.
PAGES = {"nhl-odds-2018-19": 2018, "nhl-odds-2019-20": 2019,
         "nhl-odds-2021": 2021, "nhl-odds-2021-22": 2021, "nhl-odds-2022-23": 2022}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
SOURCE = "sbr_archive_nhl"
BOOK = "sbr_consensus"

# The page's own spellings that the shared map does not carry.
EXTRA_NAMES = {"Arizona": "UTA", "Arizonas": "UTA", "Phoenix": "UTA",   # "Arizonas": the page's typo, 2019-20
               "Los Angeles": "LAK",
               "St.Louis": "STL", "St Louis": "STL", "NY Rangers": "NYR",
               "NY Islanders": "NYI", "Tampa": "TBL"}


def _fold(name: str) -> str:
    flat = unicodedata.normalize("NFKD", str(name or ""))
    return "".join(c for c in flat.lower() if c.isalnum())


_NAMES = {_fold(k): v for k, v in {**NHL_NAME_MAP, **EXTRA_NAMES}.items()}


def team(name: str) -> str | None:
    t = _NAMES.get(_fold(name))
    return "UTA" if t == "ARI" else t


def _num(v) -> float | None:
    try:
        f = float(str(v).replace("½", ".5"))
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def _price(v) -> int | None:
    f = _num(v)
    return None if f is None or abs(f) < 100 else int(f)


def parse_season(html: str, first_year: int) -> tuple[list[dict], list[str]]:
    """(games, unmapped team names). Rows are paired in page order."""
    table = max(pd.read_html(io.StringIO(html), header=None), key=len)
    rows = [r for r in table.values.tolist() if str(r[0]).strip().isdigit()]
    games, unknown = [], set()
    year, last_month = first_year, None
    for i in range(0, len(rows) - 1, 2):
        v, h = rows[i], rows[i + 1]
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
        date = f"{year:04d}-{month:02d}-{day:02d}"
        a_per = [_num(v[c]) for c in (4, 5, 6)]
        h_per = [_num(h[c]) for c in (4, 5, 6)]
        games.append({
            "game_id": f"NHL_{date}_{away}_{home}", "game_date": date,
            "season": nhl_season_label(date), "home": home, "away": away,
            "home_final": _num(h[7]), "away_final": _num(v[7]),
            "home_periods": h_per, "away_periods": a_per,
            "ml_home_open": _price(h[8]), "ml_away_open": _price(v[8]),
            "ml_home_close": _price(h[9]), "ml_away_close": _price(v[9]),
            "spread_home": _num(h[10]),
            "pl_home_price": _price(h[11]), "pl_away_price": _price(v[11]),
            "total_open": _num(v[12]), "over_open": _price(v[13]), "under_open": _price(h[13]),
            "total_close": _num(v[14]), "over_close": _price(v[15]), "under_close": _price(h[15]),
        })
    return games, sorted(unknown)


def fetch_all() -> tuple[list[dict], list[str]]:
    games, unknown = [], []
    for slug, first_year in PAGES.items():
        r = requests.get(BASE + slug, headers=UA, timeout=90)
        r.raise_for_status()
        g, u = parse_season(r.text, first_year)
        logger.info(f"{slug}: {len(g):,} games parsed" + (f", unmapped {u}" if u else ""))
        games += g
        unknown += u
    return games, sorted(set(unknown))


def validate(conn, games: list[dict]) -> dict:
    """Match rate to `games`, agreement on the score and on overtime, and the
    over/under price orientation."""
    ids = [g["game_id"] for g in games]
    have = {}
    for i in range(0, len(ids), 2000):
        chunk = ids[i:i + 2000]
        marks = ",".join("?" for _ in chunk)
        for gid, hs, as_, ot in conn.execute(
                f"SELECT game_id, home_score, away_score, went_to_ot FROM games "
                f"WHERE game_id IN ({marks})", tuple(chunk)).fetchall():
            have[gid] = (hs, as_, ot)
    out = {"parsed": len(games), "matched": 0, "score_disagrees": 0,
           "ot_disagrees": 0, "ot_checked": 0, "by_season": {}}
    short_over = short_over_won = 0
    for g in games:
        s = out["by_season"].setdefault(g["season"], [0, 0])
        s[0] += 1
        if g["game_id"] not in have:
            continue
        s[1] += 1
        out["matched"] += 1
        hs, as_, ot = have[g["game_id"]]
        if hs is not None and (hs != g["home_final"] or as_ != g["away_final"]):
            out["score_disagrees"] += 1
        if None not in g["home_periods"] + g["away_periods"] and ot is not None:
            out["ot_checked"] += 1
            tied = sum(g["home_periods"]) == sum(g["away_periods"])
            out["ot_disagrees"] += int(tied != bool(ot))
        if (g["over_close"] and g["under_close"] and g["total_close"] and hs is not None
                and g["over_close"] < g["under_close"] and hs + as_ != g["total_close"]):
            short_over += 1
            short_over_won += int(hs + as_ > g["total_close"])
    out["over_shorter_n"] = short_over
    out["over_shorter_went_over"] = round(short_over_won / short_over, 4) if short_over else None
    return out


def _odds_rows(g: dict) -> list[tuple]:
    d, gid = g["game_date"], g["game_id"]
    rows = []
    for snap in ("open", "close"):
        hp, ap = g[f"ml_home_{snap}"], g[f"ml_away_{snap}"]
        if hp is not None and ap is not None:
            rows.append((gid, "h2h", snap, d, hp, ap, None, None, None, None))
        tl, op, up = g[f"total_{snap}"], g[f"over_{snap}"], g[f"under_{snap}"]
        if tl is not None and op is not None and up is not None:
            rows.append((gid, "totals", snap, d, None, None, None, tl, op, up))
    # One puck line per game and the page does not say when it was taken. Filed
    # as `close`: it agrees with the closing favourite far more often than not.
    if g["spread_home"] is not None and g["pl_home_price"] and g["pl_away_price"]:
        rows.append((gid, "spreads", "close", d, g["pl_home_price"], g["pl_away_price"],
                     g["spread_home"], None, None, None))
    return rows


def load(conn, games: list[dict]) -> int:
    ids = {g["game_id"] for g in games}
    known = {r[0] for r in conn.execute(
        "SELECT game_id FROM games WHERE sport = 'NHL' AND season BETWEEN 2018 AND 2023"
    ).fetchall()}
    stored = {(r[0], r[1], r[2]) for r in conn.execute(
        "SELECT game_id, market, snapshot_type FROM odds WHERE source = ?", (SOURCE,)).fetchall()}
    rows = [r for g in games if g["game_id"] in known & ids for r in _odds_rows(g)
            if (r[0], r[1], r[2]) not in stored]
    sql = """INSERT INTO odds (game_id, sport, market, bookmaker, snapshot_type, snapshot_at,
                 home_price, away_price, spread_home, total_line, over_price, under_price, source)
             VALUES (%s, 'NHL', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
    payload = [(r[0], r[1], BOOK, r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], SOURCE)
               for r in rows]
    for i in range(0, len(payload), 2000):
        conn.executemany(sql, payload[i:i + 2000])
        conn.commit()
    return len(payload)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    games, unknown = fetch_all()
    if unknown:
        raise SystemExit(f"REFUSED — team names with no mapping: {unknown}")
    c = get_connection()
    try:
        v = validate(c, games)
        print(v)
        # Per season, because one season is SUPPOSED to fall short: `games` has no
        # 2020 bubble playoffs (130 games), so 2019-20 matches 1,082 of 1,212.
        thin = {s: f"{m}/{n}" for s, (n, m) in v["by_season"].items() if m / n < 0.85}
        bad = (bool(thin)
               or v["score_disagrees"] / max(v["matched"], 1) > 0.01
               or v["ot_disagrees"] / max(v["ot_checked"], 1) > 0.01)
        if bad:
            raise SystemExit(f"REFUSED — the archive does not line up with `games` closely "
                             f"enough to trust the parse (thin seasons: {thin})")
        print("rows written:", load(c, games) if a.apply else "dry run — nothing written")
    finally:
        c.close()
