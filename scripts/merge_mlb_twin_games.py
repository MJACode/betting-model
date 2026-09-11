"""Merge the four MLB franchises that `games` files twice.

THE SPLIT. The odds ingestor, the Stats API map and every `live` row say
ARI / CWS / OAK / WSH. The SBR CSV import (data/ingestors/sbr_loader.py)
files the same game as AZ / CHW / ATH / WAS -- and carries the final score,
while the live row stays unscored. Measured 2026-09-10: 1,716 SBR rows with a
canonical twin (2021-2025), 29,489 SBR rows with no twin (2009-2020, the
whole SBR-only era), 29,230 `odds` rows (all sbr_consensus) and 2,524
`game_weather` rows keyed to the SBR ids. Consequences already found: the PBP
ingestor skipped every one of those teams' games (no CWS or WSH game in the
2024 corpus), and the feature engine's sbr_consensus lookups miss them.

WHAT THIS DOES, per SBR row whose id carries a non-canonical token:
  twin exists   -> COALESCE the score / home_win onto the canonical row,
                   re-point odds and game_weather (a weather row already on
                   the canonical id wins; the SBR copy is dropped), delete
                   the SBR row.
  no twin       -> insert a canonical copy (team columns canonicalised too),
                   re-point odds and game_weather, delete the SBR row.
Every FK on games is NO ACTION, so nothing is renamed in place. The SBR rows
are snapshotted first into `games_sbr_twins_<date>` (the repo convention:
picks_dupes_removed_20260905, odds_pre_first_pitch_relabel_20260903).

DRY-RUN BY DEFAULT. `--apply` writes, in one transaction per season, and
prints the before/after counts the reply must show: zero non-canonical
tokens left in games / odds / game_weather; odds and weather row counts
unchanged; games count before = after + twins merged.

    python -m scripts.merge_mlb_twin_games            # counts only
    python -m scripts.merge_mlb_twin_games --apply
"""
from __future__ import annotations

import argparse
import re
from datetime import date

from loguru import logger

from data.db import get_connection

CANON = {"AZ": "ARI", "CHW": "CWS", "ATH": "OAK", "WAS": "WSH"}
TOKEN = re.compile(r"^(MLB_\d{4}-\d{2}-\d{2})_([A-Z]+)_([A-Z]+)$")
NONCANON_SQL = "game_id ~ '^MLB_.*_(AZ|CHW|WAS|ATH)(_|$)'"
DEPENDENTS = ("odds", "game_weather")


def canonical(game_id: str) -> str | None:
    m = TOKEN.match(game_id)
    if not m:
        return None
    pre, away, home = m.groups()
    c = f"{pre}_{CANON.get(away, away)}_{CANON.get(home, home)}"
    return c if c != game_id else None


def counts(conn) -> dict:
    out = {}
    out["games_total"] = conn.execute("SELECT count(*) FROM games WHERE sport='MLB'").fetchone()[0]
    out["games_noncanon"] = conn.execute(f"SELECT count(*) FROM games WHERE sport='MLB' AND {NONCANON_SQL}").fetchone()[0]
    for t in DEPENDENTS:
        out[f"{t}_total"] = conn.execute(f"SELECT count(*) FROM {t} WHERE game_id LIKE 'MLB_%%'").fetchone()[0]
        out[f"{t}_noncanon"] = conn.execute(f"SELECT count(*) FROM {t} WHERE {NONCANON_SQL}").fetchone()[0]
    return out


def plan(conn) -> list[dict]:
    rows = conn.execute(f"""
        SELECT game_id, sport, season, game_date, home_team, away_team,
               home_score, away_score, home_win, data_source, commence_time
        FROM games WHERE sport='MLB' AND {NONCANON_SQL} ORDER BY season, game_id""").fetchall()
    cols = ["game_id", "sport", "season", "game_date", "home_team", "away_team",
            "home_score", "away_score", "home_win", "data_source", "commence_time"]
    out = []
    for r in rows:
        g = dict(zip(cols, r))
        c = canonical(g["game_id"])
        if c is None:
            continue
        twin = conn.execute("SELECT home_score, away_score, home_win FROM games WHERE game_id=%s",
                            (c,)).fetchone()
        g["canonical"] = c
        g["twin"] = twin
        out.append(g)
    return out


def apply_one(conn, g: dict, backup: str) -> None:
    c = g["canonical"]
    conn.execute(f"INSERT INTO {backup} SELECT * FROM games WHERE game_id=%s", (g["game_id"],))
    if g["twin"] is None:
        conn.execute("""
            INSERT INTO games (game_id, sport, season, game_date, home_team, away_team,
                               home_score, away_score, home_win, data_source, commence_time)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                     (c, g["sport"], g["season"], g["game_date"],
                      CANON.get(g["home_team"], g["home_team"]),
                      CANON.get(g["away_team"], g["away_team"]),
                      g["home_score"], g["away_score"], g["home_win"],
                      g["data_source"], g["commence_time"]))
    else:
        conn.execute("""
            UPDATE games SET home_score = COALESCE(home_score, %s),
                             away_score = COALESCE(away_score, %s),
                             home_win   = COALESCE(home_win, %s)
            WHERE game_id = %s""", (g["home_score"], g["away_score"], g["home_win"], c))
    conn.execute("UPDATE odds SET game_id=%s WHERE game_id=%s", (c, g["game_id"]))
    has_weather = conn.execute("SELECT 1 FROM game_weather WHERE game_id=%s", (c,)).fetchone()
    if has_weather:
        conn.execute("DELETE FROM game_weather WHERE game_id=%s", (g["game_id"],))
    else:
        conn.execute("UPDATE game_weather SET game_id=%s WHERE game_id=%s", (c, g["game_id"]))
    conn.execute("DELETE FROM games WHERE game_id=%s", (g["game_id"],))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    conn = get_connection()
    try:
        before = counts(conn)
        todo = plan(conn)
        twins = sum(1 for g in todo if g["twin"] is not None)
        scored_twins = sum(1 for g in todo if g["twin"] is not None and g["twin"][0] is None
                           and g["home_score"] is not None)
        by_season: dict = {}
        for g in todo:
            by_season.setdefault(g["season"], [0, 0])[0 if g["twin"] is None else 1] += 1
        logger.info(f"before: {before}")
        logger.info(f"{len(todo)} SBR rows to merge: {twins} with a canonical twin "
                    f"({scored_twins} of them supply a score the twin lacks), "
                    f"{len(todo) - twins} without (canonical copy inserted)")
        logger.info("per season (orphans, twins): " + ", ".join(f"{s}: {v}" for s, v in sorted(by_season.items())))
        if not args.apply:
            logger.info("dry run -- nothing written")
            return
        backup = f"games_sbr_twins_{date.today().strftime('%Y%m%d')}"
        conn.execute(f"CREATE TABLE IF NOT EXISTS {backup} (LIKE games INCLUDING ALL)")
        conn.commit()
        for season in sorted(by_season):
            batch = [g for g in todo if g["season"] == season]
            for g in batch:
                apply_one(conn, g, backup)
            conn.commit()
            logger.info(f"  season {season}: {len(batch)} merged")
        after = counts(conn)
        logger.info(f"after: {after}")
        ok = (after["games_noncanon"] == 0
              and all(after[f"{t}_noncanon"] == 0 for t in DEPENDENTS)
              and after["odds_total"] == before["odds_total"]
              and after["games_total"] == before["games_total"] - twins)
        weather_dropped = before["game_weather_total"] - after["game_weather_total"]
        logger.info(f"weather rows dropped as duplicates of a canonical row: {weather_dropped}")
        (logger.success if ok else logger.error)(
            f"verification {'PASSED' if ok else 'FAILED'}: non-canonical left "
            f"games={after['games_noncanon']} odds={after['odds_noncanon']} "
            f"weather={after['game_weather_noncanon']}; odds {before['odds_total']}->{after['odds_total']}; "
            f"games {before['games_total']}->{after['games_total']} (twins {twins})")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
