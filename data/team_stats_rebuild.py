"""Rebuild the team-stats tables as real as-of-date series. Phase 1.

WHY. `mlb_team_stats`, `nba_team_stats`, `nhl_team_stats` and `wnba_team_stats`
each stored ONE OR TWO rows per historical season, and each row held that
season's FINAL numbers stamped before the season began — NBA BOS season 2023
carried 82 games played and 57 wins at `as_of_date 2022-09-01`. Every historical
training game resolves `as_of_date <= game_date` to that row, so every MLB, NBA,
NHL and WNBA model has been trained knowing how the season turned out.
`docs/team_stats_leak.md` has the evidence; `docs/team_stats_rebuild_scope.md`
has the plan. NCAAF was built correctly and is untouched.

WHAT PHASE 1 REBUILDS. Everything derivable from final scores, exactly, from the
`games` table (87k rows, 2009-2026):

    games_played, wins, losses, run/point/goal differential,
    <scoring>_per_game, <scoring>_allowed, last-N form, home/away splits

That is more than the counting stats the scope promised. `runs_last_5`,
`runs_last_10`, `points_last_3`, `goals_last_5` and the home/away splits are all
exact from scores — and today they hold season-final constants, which is what
makes `d_runs_last_5` (the model's 10th-most-important feature) a leaked number
rather than a rolling one.

WHAT IT DOES NOT REBUILD. Rate stats — OPS, wRC+, ERA, off_rating, corsi and the
rest — need per-game player aggregation and are Phase 3. They are carried
forward from the PRIOR season's final row, which is a legitimate pre-season
prior rather than a leak: last season's numbers are genuinely known before this
season starts. Where no prior season exists (the earliest season in the table)
they are left NULL and those rows drop out of training, which is the honest
outcome rather than a convenient one.

THE ONE DETAIL THAT MATTERS MOST. A row stamped date D must contain only games
played STRICTLY BEFORE D. `_team_stats_before` selects `as_of_date <= game_date`,
so a row dated D that included D's own game would hand the model that game's
result — rebuilding the leak one day narrower and much harder to see.
`test_a_row_never_includes_its_own_date` pins it.

    python -m data.team_stats_rebuild --sport MLB --dry-run
    python -m data.team_stats_rebuild --sport MLB --seasons 2019,2020
    python -m data.team_stats_rebuild --verify-only
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.db import DBConnection, get_connection

# A season with fewer than this many distinct as_of_dates is not a series. The
# leaked tables had 1 or 2; NCAAF, which is correct, has 14-16 weekly snapshots
# and must not be flagged.
MIN_SNAPSHOTS_PER_SEASON = 5

# Per sport: the table, the scoring noun its columns use, the last-N windows it
# stores, and whether it carries NHL's regulation/OT split.
SPORTS: dict[str, dict] = {
    # `home`/`away` are spelled out per sport because MLB is the odd one out --
    # runs_per_game_home, not runs_home. Deriving them from `noun` looked tidy
    # and produced `runs_away`, which does not exist; the INSERT failed on the
    # real table after the DELETE had already run in the same transaction.
    "MLB":  {"table": "mlb_team_stats",  "noun": "runs",   "diff": "run_differential",
             "windows": (5, 10, 15), "allowed": None,      "ot": False,
             "home": "runs_per_game_home", "away": "runs_per_game_away"},
    "NBA":  {"table": "nba_team_stats",  "noun": "points", "diff": "point_differential",
             "windows": (3, 5),      "allowed": "points_allowed_pg", "ot": False,
             "home": "points_home", "away": "points_away"},
    "WNBA": {"table": "wnba_team_stats", "noun": "points", "diff": "point_differential",
             "windows": (3, 5),      "allowed": "points_allowed_pg", "ot": False,
             "home": "points_home", "away": "points_away"},
    "NHL":  {"table": "nhl_team_stats",  "noun": "goals",  "diff": "goal_differential",
             "windows": (5, 10),     "allowed": "goals_against_pg",  "ot": True,
             "home": "goals_home", "away": "goals_away"},
}

# Rate columns per table, carried forward from the prior season. Phase 3
# replaces these with real as-of-date aggregates.
RATE_COLUMNS: dict[str, tuple[str, ...]] = {
    "mlb_team_stats": ("ops", "wrc_plus", "woba", "k_pct", "bb_pct", "iso",
                       "babip", "team_era", "bullpen_era", "team_whip", "team_fip"),
    "nba_team_stats": ("pace", "off_rating", "def_rating", "efg_pct", "fg_pct",
                       "fg3_pct", "ft_pct", "reb_per_game", "ast_per_game", "tov_pct"),
    "wnba_team_stats": ("pace", "off_rating", "def_rating", "efg_pct", "fg_pct",
                        "fg3_pct", "ft_pct", "reb_per_game", "ast_per_game", "tov_pct"),
    "nhl_team_stats": ("shots_per_game", "corsi_for_pct", "xgf_pct",
                       "power_play_pct", "shots_against_pg", "penalty_kill_pct",
                       "xga_pct"),
}


# ── the two invariants ───────────────────────────────────────────────────────

def impossible_games_played(rows: list[dict], played: dict) -> list[dict]:
    """Rows claiming more games than the team had actually played by that date.

    `played` maps (team, season, as_of_date) -> games actually completed before
    that date, computed from `games`.

    A MISSING count is reported, not skipped. "I could not verify this" is not
    "this is fine", and a checker that quietly passes what it cannot check is
    how the original leak survived seven seasons.
    """
    bad = []
    for r in rows:
        key = (r["team"], r["season"], r["as_of_date"])
        actual = played.get(key)
        if actual is None or r["games_played"] > actual:
            bad.append({**r, "claimed": r["games_played"], "actual": actual})
    return bad


def seasons_with_too_few_snapshots(rows: list[dict]) -> list[tuple[int, int]]:
    """(season, n_distinct_as_of_dates) for seasons that are not a real series."""
    per: dict[int, set] = defaultdict(set)
    for r in rows:
        per[r["season"]].add(r["as_of_date"])
    return sorted((s, len(d)) for s, d in per.items()
                  if len(d) < MIN_SNAPSHOTS_PER_SEASON)


# ── building the series ──────────────────────────────────────────────────────


def already_a_series(conn: DBConnection, table: str, seasons: list[int]) -> list[int]:
    """Seasons that ALREADY have a real as-of-date series and must not be touched.

    2026 is stored correctly in all four tables -- daily snapshots with REAL
    rate stats, the only honest rate data in the database. A rebuild that
    deleted it would replace measured OPS and off_rating with last season's
    carried-forward values and destroy the one season worth trusting. The first
    dry run of this module was scoped to all 18 seasons and would have done
    exactly that.

    So the refusal is in the code, not in the operator's memory.
    """
    marks = ",".join("?" for _ in seasons)
    rows = conn.execute(
        f"SELECT season, COUNT(DISTINCT as_of_date) FROM {table} "
        f"WHERE season IN ({marks}) GROUP BY season", tuple(seasons)).fetchall()
    return sorted(int(s) for s, n in rows if n >= MIN_SNAPSHOTS_PER_SEASON)


def _games(conn: DBConnection, sport: str, seasons: list[int]) -> list[dict]:
    marks = ",".join("?" for _ in seasons)
    rows = conn.execute(f"""
        SELECT game_date, season, home_team, away_team,
               home_score, away_score, home_win, went_to_ot, home_win_reg
        FROM games
        WHERE sport = ? AND season IN ({marks})
          AND home_score IS NOT NULL AND away_score IS NOT NULL
        ORDER BY game_date
    """, (sport, *seasons)).fetchall()
    return [{"date": r[0][:10], "season": r[1], "home": r[2], "away": r[3],
             "hs": float(r[4]), "as_": float(r[5]),
             "home_win": r[6], "ot": r[7], "home_win_reg": r[8]} for r in rows]


def _team_games(games: list[dict]) -> dict[tuple[str, int], list[dict]]:
    """One chronological list of (date, scored, allowed, won, home) per team."""
    out: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for g in games:
        won_home = (g["home_win"] == 1) if g["home_win"] is not None else (g["hs"] > g["as_"])
        out[(g["home"], g["season"])].append(
            {"date": g["date"], "for": g["hs"], "against": g["as_"],
             "won": won_home, "home": True, "ot": g["ot"]})
        out[(g["away"], g["season"])].append(
            {"date": g["date"], "for": g["as_"], "against": g["hs"],
             "won": not won_home, "home": False, "ot": g["ot"]})
    for v in out.values():
        v.sort(key=lambda x: x["date"])
    return out


def build_rows(sport: str, games: list[dict]) -> list[dict]:
    """One row per team per date the team's league played, holding ONLY games
    played strictly before that date."""
    cfg = SPORTS[sport]
    noun, windows = cfg["noun"], cfg["windows"]
    per_team = _team_games(games)
    all_dates = sorted({g["date"] for g in games})
    rows: list[dict] = []

    for (team, season), tg in per_team.items():
        season_dates = [d for d in all_dates
                        if any(x["date"] == d for x in tg)
                        or (tg and tg[0]["date"] <= d <= tg[-1]["date"])]
        idx = 0
        for d in season_dates:
            # STRICTLY BEFORE: a row dated d must not contain d's own result.
            while idx < len(tg) and tg[idx]["date"] < d:
                idx += 1
            prior = tg[:idx]
            if not prior:
                continue
            gp = len(prior)
            wins = sum(1 for x in prior if x["won"])
            scored = [x["for"] for x in prior]
            allowed = [x["against"] for x in prior]
            home = [x["for"] for x in prior if x["home"]]
            away = [x["for"] for x in prior if not x["home"]]
            row = {
                "team": team, "season": season, "as_of_date": d,
                "games_played": gp,
                "wins": wins, "losses": gp - wins,
                cfg["diff"]: sum(scored) - sum(allowed),
                f"{noun}_per_game": round(sum(scored) / gp, 4),
                cfg["home"]: round(sum(home) / len(home), 4) if home else None,
                cfg["away"]: round(sum(away) / len(away), 4) if away else None,
            }
            if cfg["allowed"]:
                row[cfg["allowed"]] = round(sum(allowed) / gp, 4)
            for w in windows:
                last = scored[-w:]
                row[f"{noun}_last_{w}"] = round(sum(last) / len(last), 4) if last else None
            if cfg["ot"]:
                ot_losses = sum(1 for x in prior if not x["won"] and x["ot"] == 1)
                row["ot_losses"] = ot_losses
                row["losses"] = gp - wins - ot_losses
            rows.append(row)
    return rows


def _prior_season_rates(conn: DBConnection, table: str, season: int) -> dict:
    """The prior season's final rate stats per team — a legitimate pre-season
    prior, not a leak: last season's numbers are known before this one starts."""
    cols = RATE_COLUMNS[table]
    rows = conn.execute(f"""
        SELECT DISTINCT ON (team) team, {', '.join(cols)}
        FROM {table} WHERE season = ?
        ORDER BY team, as_of_date DESC
    """, (season - 1,)).fetchall()
    return {r[0]: dict(zip(cols, r[1:])) for r in rows}


def rebuild_sport(conn: DBConnection, sport: str, seasons: list[int],
                  dry_run: bool = False, force: bool = False) -> dict:
    cfg = SPORTS[sport]
    table = cfg["table"]

    # Never overwrite a season that is already right -- see already_a_series.
    protected = already_a_series(conn, table, seasons)
    if protected and not force:
        seasons = [s for s in seasons if s not in protected]
        logger.warning(f"{sport}: skipping {protected} — already a real "
                       f"as-of-date series, and rebuilding would replace "
                       f"measured rate stats with carried-forward ones")
    if not seasons:
        return {"sport": sport, "seasons": [], "games": 0, "rows": 0,
                "teams": 0, "no_prior_rates": 0, "protected": protected}

    games = _games(conn, sport, seasons)
    if not games:
        return {"sport": sport, "seasons": seasons, "games": 0, "rows": 0}

    rows = build_rows(sport, games)
    rates_cache: dict[int, dict] = {}
    for r in rows:
        s = r["season"]
        if s not in rates_cache:
            rates_cache[s] = _prior_season_rates(conn, table, s)
        r.update(rates_cache[s].get(r["team"], {}))

    summary = {"sport": sport, "seasons": seasons, "games": len(games),
               "rows": len(rows), "protected": protected,
               "teams": len({r["team"] for r in rows}),
               "no_prior_rates": sum(1 for r in rows
                                     if not rates_cache[r["season"]].get(r["team"]))}
    if dry_run:
        summary["written"] = 0
        return summary

    marks = ",".join("?" for _ in seasons)
    conn.execute(f"DELETE FROM {table} WHERE season IN ({marks})", tuple(seasons))
    cols = sorted({k for r in rows for k in r})
    placeholders = ",".join("?" for _ in cols)
    conn.executemany(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",
        [tuple(r.get(c) for c in cols) for r in rows])
    conn.commit()
    summary["written"] = len(rows)
    return summary


def verify(conn: DBConnection, sport: str, seasons: list[int]) -> dict:
    """Run both invariants against what is actually stored."""
    table = SPORTS[sport]["table"]
    marks = ",".join("?" for _ in seasons)
    stored = [{"team": r[0], "season": r[1], "as_of_date": r[2],
               "games_played": r[3]}
              for r in conn.execute(
                  f"SELECT team, season, as_of_date, games_played FROM {table} "
                  f"WHERE season IN ({marks})", tuple(seasons)).fetchall()]

    played: dict = defaultdict(int)
    per_team = _team_games(_games(conn, sport, seasons))
    dates = {r["as_of_date"] for r in stored}
    for (team, season), tg in per_team.items():
        for d in dates:
            played[(team, season, d)] = sum(1 for x in tg if x["date"] < d)

    return {"sport": sport, "rows": len(stored),
            "impossible": impossible_games_played(stored, played),
            "thin_seasons": seasons_with_too_few_snapshots(stored)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sport", default="", help="MLB|NBA|NHL|WNBA (default: all)")
    ap.add_argument("--seasons", default="", help="comma-separated (default: all present)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="rebuild even seasons that already have a real series "
                         "(destroys measured rate stats — almost never right)")
    args = ap.parse_args()

    sports = [args.sport] if args.sport else list(SPORTS)
    conn = get_connection()
    try:
        for sport in sports:
            if args.seasons:
                seasons = [int(s) for s in args.seasons.split(",")]
            else:
                seasons = [r[0] for r in conn.execute(
                    "SELECT DISTINCT season FROM games WHERE sport = ? "
                    "AND home_score IS NOT NULL ORDER BY season", (sport,)).fetchall()]
            if not seasons:
                logger.info(f"{sport}: no seasons with finals"); continue

            if not args.verify_only:
                s = rebuild_sport(conn, sport, seasons, dry_run=args.dry_run,
                                  force=args.force)
                logger.info(
                    f"{sport}: {s['games']} games -> {s['rows']} rows across "
                    f"{s['teams']} teams, {len(seasons)} seasons "
                    f"({'DRY RUN' if args.dry_run else str(s['written']) + ' written'}); "
                    f"{s['no_prior_rates']} rows have no prior-season rate stats")
            if not args.dry_run:
                v = verify(conn, sport, seasons)
                bad, thin = v["impossible"], v["thin_seasons"]
                if bad:
                    logger.error(f"{sport}: {len(bad)} row(s) claim games that had "
                                 f"not been played, e.g. {bad[0]}")
                if thin:
                    logger.error(f"{sport}: seasons with too few snapshots: {thin}")
                if not bad and not thin:
                    logger.success(f"{sport}: {v['rows']} rows pass both invariants")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
