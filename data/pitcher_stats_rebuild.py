"""Rebuild `mlb_pitcher_stats` as a real as-of-date series. Phase 2.

WHY. The table stored each pitcher's SEASON-FINAL ERA on every one of his
starts. Aaron Nola's 33 rows for 2024 all read 3.57 — his final 2024 ERA — and
`era_last3` was the same constant, so "his last three starts" was also a
season-final number. Across 2019-2025 a pitcher-season averages **1.0** distinct
ERA value; 2026, which is built correctly, averages 17.2.

This is the leak that carries `mlb_f5_moneyline`: `d_starter_era_last3` (0.213)
and `d_starter_era` (0.186) are its two most important features, 40% of total
importance between them. It is why rebuilding the team tables moved
`mlb_moneyline` (2026 AUC 0.529 -> 0.566) and left f5 untouched (0.560 -> 0.562).
`docs/team_stats_leak.md` has the evidence.

THE SOURCE. `player_game_log` — 481k rows, 2019-2026 — carries the raw
components per appearance, so era/whip/k9/bb9/hr9 and the last-3 variants are
computed rather than copied. The historical rows of `mlb_pitcher_stats` cannot
be re-aggregated in place: its own `innings_pitched`, `earned_runs`,
`strikeouts` and `walks` columns are NULL on every historical row (and on 2026's
too). Only the derived rates were ever written.

Validated against the leak itself, which for all its faults IS each pitcher's
true season-final ERA: rebuilding a full season from `player_game_log` and
comparing gives corr **0.957 / 0.920 / 0.720** for 2023 / 2024 / 2025 at a mean
bias of 0.002. The correlation degrades exactly in step with pgl's game coverage
(87% / 81% / 74%), which is what a faithful source with a coverage hole looks
like.

INNINGS ARE IN BASEBALL NOTATION. `innings_pitched` 5.2 means five and TWO
THIRDS, not 5.2. Only .0/.1/.2 fractions occur, across all 135,010 rows. Summing
the column directly is wrong arithmetic and biases every ERA upward — visible as
a mean bias of +0.025 that drops to +0.002 once converted. Everything here works
in OUTS and converts once, in `outs_from_ip`.

WHAT IS NOT REBUILT. `xfip`, `xfip_last3`, `swstr_pct` and `csw_pct` need
league-wide HR/FB and pitch-level data we do not hold, so they are left NULL.
Safe: they are computed into the feature dict but appear in no model's feature
list, and `build_training_data` filters to `feature_cols` BEFORE its `dropna`,
so a NULL there cannot delete the matrix.

THE COVERAGE COST, STATED PLAINLY. pgl holds no rows at all for any game
involving the White Sox or the Nationals before 2026 — not even the opponent's
starter — plus scattered games elsewhere. Rebuilt coverage is ~86% of completed
games for 2019-2023, 81% for 2024, 74% for 2025, 99% for 2026. The uncovered
games get no row and drop out of training. That is the honest cost: leaving the
old rows standing for exactly those games would produce a matrix that is honest
where pgl reaches and leaked where it does not, which is worse than missing.
Recovering them means backfilling pgl from the MLB StatsAPI — a Railway job,
named as a follow-up in `docs/team_stats_leak.md`, not done here.

THE ONE DETAIL THAT MATTERS MOST. A row stamped date D must be computed only
from appearances STRICTLY BEFORE D. `_get_mlb_pitcher_stats` matches
`game_date = D` exactly and hands the result to the model as the starter's form
ENTERING that start; a row that included D's own line would be handing over the
result of the game being predicted. `test_a_row_never_includes_its_own_start`
pins it.

    python -m data.pitcher_stats_rebuild --dry-run
    python -m data.pitcher_stats_rebuild --seasons 2019,2020
    python -m data.pitcher_stats_rebuild --verify-only
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.db import DBConnection, get_connection

TABLE = "mlb_pitcher_stats"

# 2026 is already a genuine daily series and must never be overwritten by this
# script. The separation is not subtle: 2019-2025 average 1.0 distinct ERA per
# pitcher-season, 2026 averages 17.2. Anything at or above this is a real
# series. Mirrors `team_stats_rebuild.already_a_series`.
MIN_DISTINCT_ERA_PER_PITCHER = 3.0

# A pitcher-season needs this many starts before "his ERA never moved" is
# evidence of a leak rather than a short sample.
MIN_STARTS_TO_JUDGE = 10

# `era_last3` averages the last N stored rows, matching the serving definition
# documented on `_last3` below.
LAST_N = 3


def outs_from_ip(ip: float) -> int:
    """Convert baseball innings notation to outs. 5.2 -> 17, not 15.6.

    The fractional part counts THIRDS of an inning and is only ever .0, .1 or
    .2. Anything else means the column's meaning changed and every rate built
    on it would be quietly wrong, so it raises rather than rounds.
    """
    whole = int(ip)
    thirds = round((ip - whole) * 10)
    if thirds not in (0, 1, 2):
        raise ValueError(
            f"innings_pitched {ip!r} has fractional part .{thirds} — baseball "
            f"notation only ever carries .0, .1 or .2 thirds of an inning")
    return whole * 3 + thirds


def _rate(numerator: float, outs: int, per: float = 27.0) -> float | None:
    """Per-nine rate from a total and a number of outs (27 outs = 9 innings)."""
    if not outs:
        return None
    return round(per * numerator / outs, 4)


def appearances(conn: DBConnection, seasons: list[int]) -> list[dict]:
    """Every pitching appearance, joined to `games` so the team label is the
    exact string the feature lookup will pass.

    RELIEF OUTINGS ARE INCLUDED. A season ERA counts every inning a pitcher
    threw, not only his starts. Rows are EMITTED only at his starts, because
    that is what the engine looks up, but the totals behind them are complete.

    Joining `games` also settles the team label without an alias map: measured
    across 2019-2026, `player_game_log.team` matches one of the game's two
    teams verbatim on all 30,798 starter rows and mismatches on zero. The
    CHW/WAS-vs-CWS/WSH split that looks like a label bug is really a coverage
    hole — those games are absent from pgl entirely.
    """
    marks = ",".join("?" for _ in seasons)
    rows = conn.execute(f"""
        SELECT p.player_id, p.player_name, p.team, p.season, p.game_date,
               p.game_id, p.is_starter, p.innings_pitched, p.p_earned_runs,
               p.p_strikeouts, p.p_walks, p.p_hits_allowed, p.p_home_runs
        FROM player_game_log p
        JOIN games g ON g.game_id = p.game_id
        WHERE p.player_type = 'pitcher'
          AND p.season IN ({marks})
          AND p.innings_pitched IS NOT NULL
          AND p.player_id IS NOT NULL
        ORDER BY p.player_id, p.season, p.game_date, p.game_id
    """, tuple(seasons)).fetchall()

    cols = ["player_id", "player_name", "team", "season", "game_date",
            "game_id", "is_starter", "ip", "er", "k", "bb", "h", "hr"]
    return [dict(zip(cols, r)) for r in rows]


def build_rows(apps: list[dict]) -> list[dict]:
    """One row per start, holding that pitcher's line ENTERING the start.

    The emit-then-accumulate order is the whole point: the current appearance
    is added to the running totals only AFTER its row has been built, so a row
    can never see its own game.
    """
    by_pitcher: dict = defaultdict(list)
    for a in apps:
        by_pitcher[(a["player_id"], a["season"])].append(a)

    rows: list[dict] = []
    for (player_id, season), group in by_pitcher.items():
        group.sort(key=lambda a: (a["game_date"], a["game_id"] or ""))
        cum = {"outs": 0, "er": 0, "k": 0, "bb": 0, "h": 0, "hr": 0}
        prior_rates: list[tuple] = []
        seen_dates: set = set()

        for a in group:
            if a["is_starter"] and a["game_date"] not in seen_dates:
                seen_dates.add(a["game_date"])
                row = _row(a, player_id, season, cum, prior_rates)
                rows.append(row)
                prior_rates.append((row["era"], row["k9"]))

            outs = outs_from_ip(a["ip"])
            cum["outs"] += outs
            for src, dst in (("er", "er"), ("k", "k"), ("bb", "bb"),
                             ("h", "h"), ("hr", "hr")):
                cum[dst] += a[src] or 0

    return rows


def _last3(prior_rates: list[tuple], idx: int) -> float | None:
    """`era_last3` / `k9_last3` AS THE SCORER ACTUALLY SEES THEM.

    This is deliberately NOT an ERA over the pitcher's last three starts. The
    daily ingest computes it as

        SELECT AVG(era) FROM (SELECT era FROM mlb_pitcher_stats
                              WHERE player_name = ? AND season = ?
                                AND game_date < ? ORDER BY game_date DESC LIMIT 3)

    — the MEAN OF THE LAST THREE STORED SEASON-TO-DATE RATES, a smoothed
    near-duplicate of `era`, and it will keep doing so tomorrow morning.
    Training on a true rolling last-three would measure a better system than
    the one deployed, and would silently redefine 40% of `mlb_f5_moneyline`'s
    importance — a model update under the repo's own rules, not a leak repair.

    Two details of the SQL that matter. `LIMIT 3` applies BEFORE the average,
    so a season's first start (NULL era) OCCUPIES A WINDOW SLOT and contributes
    nothing: at the fourth start the window is starts 1-3 and the mean is over
    two values, not three. And `AVG` returns NULL when every slot is NULL.

    The one thing not replicated is the ingestor keying on `player_name`, which
    collides — this session hit two pitchers named Nola. Grouping here is by
    `player_id`. That divergence is a bug fixed, not a definition changed, and
    it is flagged in `docs/team_stats_leak.md`.
    """
    window = [r[idx] for r in prior_rates[-LAST_N:]]
    present = [v for v in window if v is not None]
    return round(sum(present) / len(present), 4) if present else None


def _row(a: dict, player_id: str, season: int,
         cum: dict, prior_rates: list) -> dict:
    """Build one stored row from the totals accumulated BEFORE this start."""
    outs = cum["outs"]

    # The raw columns were NULL on every row this table has ever held, so
    # nothing reads them. Writing the cumulative sample the rates were computed
    # from makes each row self-describing and lets `verify` recompute the ERA
    # without going back to `player_game_log`. Stored as DECIMAL innings, not
    # baseball notation — era == 9 * earned_runs / innings_pitched exactly.
    row = {
        "player_id": player_id,
        "player_name": a["player_name"],
        "team": a["team"],
        "season": season,
        "game_date": a["game_date"],
        "game_id": a["game_id"],
        "innings_pitched": round(outs / 3.0, 6),
        "earned_runs": cum["er"],
        "strikeouts": cum["k"],
        "walks": cum["bb"],
        "hits_allowed": cum["h"],
        "home_runs_allowed": cum["hr"],
        "era": _rate(cum["er"], outs),
        "k9": _rate(cum["k"], outs),
        "bb9": _rate(cum["bb"], outs),
        "hr9": _rate(cum["hr"], outs),
        "whip": _rate(cum["bb"] + cum["h"], outs, per=3.0),
        "era_last3": _last3(prior_rates, 0),
        "k9_last3": _last3(prior_rates, 1),
    }
    return row


def already_a_series(conn: DBConnection, seasons: list[int]) -> list[int]:
    """Seasons already stored as a genuine per-start series — never overwrite.

    Without this the first careless `--seasons` argument replaces 2026's real
    daily data with a rebuild, and 2026 is the only season the models have ever
    been measured on honestly.
    """
    if not seasons:
        return []
    marks = ",".join("?" for _ in seasons)
    rows = conn.execute(f"""
        SELECT season, avg(n) FROM (
            SELECT season, player_id, count(DISTINCT era) AS n
            FROM {TABLE}
            WHERE season IN ({marks}) AND era IS NOT NULL
            GROUP BY season, player_id
            HAVING count(*) >= {MIN_STARTS_TO_JUDGE}
        ) t GROUP BY season
    """, tuple(seasons)).fetchall()
    return sorted(int(s) for s, avg_n in rows
                  if avg_n is not None and float(avg_n) >= MIN_DISTINCT_ERA_PER_PITCHER)


def rebuild(conn: DBConnection, seasons: list[int],
            dry_run: bool = False, force: bool = False) -> dict:
    protected = already_a_series(conn, seasons)
    if protected and not force:
        seasons = [s for s in seasons if s not in protected]
        logger.warning(f"skipping {protected} — already a real per-start "
                       f"series; rebuilding would replace measured data")
    if not seasons:
        return {"seasons": [], "appearances": 0, "rows": 0, "pitchers": 0,
                "protected": protected, "written": 0}

    apps = appearances(conn, seasons)
    rows = build_rows(apps)
    summary = {
        "seasons": seasons, "appearances": len(apps), "rows": len(rows),
        "pitchers": len({r["player_id"] for r in rows}),
        "teams": len({r["team"] for r in rows}),
        "protected": protected,
        "no_prior_line": sum(1 for r in rows if r["era"] is None),
    }
    if dry_run:
        summary["written"] = 0
        return summary

    marks = ",".join("?" for _ in seasons)
    conn.execute(f"DELETE FROM {TABLE} WHERE season IN ({marks})", tuple(seasons))
    cols = sorted({k for r in rows for k in r})
    placeholders = ",".join("?" for _ in cols)
    conn.executemany(
        f"INSERT INTO {TABLE} ({', '.join(cols)}) VALUES ({placeholders})",
        [tuple(r.get(c) for c in cols) for r in rows])
    conn.commit()
    summary["written"] = len(rows)
    return summary


def constant_era_pitcher_seasons(stored: list[dict]) -> list[tuple]:
    """The invariant that fails loudly on exactly the bug being fixed.

    A pitcher with ten or more starts whose stored ERA never moved is carrying
    one number across a whole season, which is what a season-final value looks
    like. Aaron Nola 2024 — 33 rows, all 3.57 — fails this instantly.
    """
    by_pitcher: dict = defaultdict(list)
    for r in stored:
        if r["era"] is not None:
            by_pitcher[(r["player_id"], r["season"])].append(r["era"])
    return sorted((pid, season, len(eras))
                  for (pid, season), eras in by_pitcher.items()
                  if len(eras) >= MIN_STARTS_TO_JUDGE and len(set(eras)) == 1)


def self_inconsistent_rows(stored: list[dict], tol: float = 0.01) -> list[dict]:
    """Every row must satisfy era == 9 * earned_runs / innings_pitched.

    Cheap, and it catches a whole class of arithmetic slip — most usefully the
    baseball-notation one, where summing `innings_pitched` naively leaves the
    stored rate disagreeing with the stored sample it was supposedly built from
    (an ~9% error).

    THE TOLERANCE IS RELATIVE, because the invariant is a ratio. `era` is
    computed from exact OUTS while `innings_pitched` is stored rounded, so a
    tiny sample amplifies that rounding: Kyle Gibson's 5 earned runs in a third
    of an inning is a true 135.00 ERA, and recomputing it from a stored 0.3333
    lands on 135.01. An absolute tolerance calls that a defect and says nothing
    about the 9% error it exists to catch.
    """
    bad = []
    for r in stored:
        if r["era"] is None or not r["innings_pitched"]:
            continue
        expected = 9.0 * r["earned_runs"] / r["innings_pitched"]
        if abs(expected - r["era"]) > tol * max(1.0, abs(r["era"])):
            bad.append(r)
    return bad


def verify(conn: DBConnection, seasons: list[int]) -> dict:
    marks = ",".join("?" for _ in seasons)
    cols = ["player_id", "player_name", "season", "game_date", "era",
            "earned_runs", "innings_pitched", "era_last3"]
    stored = [dict(zip(cols, r)) for r in conn.execute(
        f"SELECT {', '.join(cols)} FROM {TABLE} WHERE season IN ({marks})",
        tuple(seasons)).fetchall()]

    return {
        "rows": len(stored),
        "constant_era": constant_era_pitcher_seasons(stored),
        "self_inconsistent": self_inconsistent_rows(stored),
        "distinct_era_per_pitcher": _avg_distinct(stored),
    }


def _avg_distinct(stored: list[dict]) -> dict:
    by_season: dict = defaultdict(list)
    grouped: dict = defaultdict(set)
    for r in stored:
        if r["era"] is not None:
            grouped[(r["player_id"], r["season"])].add(r["era"])
    for (_, season), eras in grouped.items():
        by_season[season].append(len(eras))
    return {s: round(sum(v) / len(v), 1) for s, v in sorted(by_season.items())}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seasons", default="", help="comma-separated (default: all in player_game_log)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="rebuild even a season that is already a real series "
                         "(destroys measured data — almost never right)")
    args = ap.parse_args()

    conn = get_connection()
    try:
        if args.seasons:
            seasons = [int(s) for s in args.seasons.split(",")]
        else:
            seasons = [int(r[0]) for r in conn.execute(
                "SELECT DISTINCT season FROM player_game_log "
                "WHERE player_type = 'pitcher' ORDER BY season").fetchall()]

        if not args.verify_only:
            s = rebuild(conn, seasons, dry_run=args.dry_run, force=args.force)
            logger.info(
                f"{s['appearances']} appearances -> {s['rows']} start rows "
                f"across {s['pitchers']} pitchers, {len(s['seasons'])} seasons "
                f"({'DRY RUN' if args.dry_run else str(s['written']) + ' written'}); "
                f"{s.get('no_prior_line', 0)} rows are a season's first start "
                f"and carry no prior line")
            seasons = s["seasons"] or seasons

        if not args.dry_run and seasons:
            v = verify(conn, seasons)
            if v["constant_era"]:
                logger.error(f"{len(v['constant_era'])} pitcher-season(s) carry "
                             f"one ERA across every start, e.g. {v['constant_era'][0]}")
            if v["self_inconsistent"]:
                logger.error(f"{len(v['self_inconsistent'])} row(s) whose ERA "
                             f"disagrees with their own sample, e.g. "
                             f"{v['self_inconsistent'][0]}")
            if not v["constant_era"] and not v["self_inconsistent"]:
                logger.success(f"{v['rows']} rows pass both invariants; "
                               f"distinct ERAs per pitcher-season: "
                               f"{v['distinct_era_per_pitcher']}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
