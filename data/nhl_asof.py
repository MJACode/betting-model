"""NHL goalie and team-rate features AS OF a date, from the per-game logs.

ONE FUNCTION FOR TRAINING AND FOR SCORING. Until 2026-09-20 the two paths read
different things and neither was right:

  * goalies — training read one row per team per season, dated `YYYY-10-01` and
    holding the season's FINAL line (the model was told in October how the
    goalie's year would end); scoring read the probable starter's live
    season-to-date. "GSAA" was a copy of GAA in both.
  * team shot share / power play / penalty kill — training read the PRIOR
    season's final, constant all year; scoring read the live season-to-date.

Both now come from `nhl_goalie_game_log` / `nhl_team_game_log` through the
functions here, strictly BEFORE the date asked about. The historical rebuild
(`python -m data.nhl_asof`) and the daily ingestor call the same code, so a
number means the same thing in a 2022 training row and on tonight's slate.

EARLY SEASON (CLAUDE.md §3: "season-to-date rates are noise early — blend
toward the prior season by games played"):

  * a goalie's rates are taken over THIS season and LAST, then regressed to
    the league rate with a fixed weight of league-average shots / minutes, so
    a goalie with no history reads as league average rather than as nothing;
  * a team rate is `(n*current + K*prior) / (n + K)` on games played, where
    `prior` is the team's own final rate last season (the league's, for an
    expansion team).

`gsaa` is the real thing at last: goals a league-average goalie would have
allowed on the same shots, minus goals allowed — THIS season only, so it is 0
on opening night and carries workload as well as quality.
"""
from __future__ import annotations

import argparse
import bisect
from collections import defaultdict

from loguru import logger

from data.db import DBConnection, get_connection

GOALIE_PRIOR_SHOTS = 500        # league-average shots mixed into save%
GOALIE_PRIOR_MINUTES = 600      # league-average minutes mixed into GAA
LAST5_PRIOR_SHOTS = 100
LAST5_PRIOR_MINUTES = 120
TEAM_PRIOR_GAMES = 25

TEAM_RATE_COLUMNS = ("corsi_for_pct", "power_play_pct", "penalty_kill_pct",
                     "shots_per_game", "shots_against_pg")


# ── goalies ──────────────────────────────────────────────────────────────────

class GoalieBook:
    """Every goalie game, indexed so 'strictly before d' is a bisect, not a scan."""

    def __init__(self, rows: list[dict]):
        self.by_player: dict[int, list[dict]] = defaultdict(list)
        self.by_team_game: dict[tuple[str, str], list[dict]] = defaultdict(list)
        league: dict[int, list[dict]] = defaultdict(list)
        for r in sorted(rows, key=lambda x: (x["game_date"], x["nhl_game_id"])):
            if not r.get("shots_against") and not r.get("toi_seconds"):
                continue
            self.by_player[int(r["player_id"])].append(r)
            self.by_team_game[(r["team"], r["game_id"])].append(r)
            league[r["season"]].append(r)
        # Per season: dates, and running league totals up to and including each row.
        self._lg: dict[int, tuple[list[str], list[tuple[int, int, int]]]] = {}
        for season, rs in league.items():
            dates, run, sa, ga, toi = [], [], 0, 0, 0
            for r in rs:
                sa += r.get("shots_against") or 0
                ga += r.get("goals_against") or 0
                toi += r.get("toi_seconds") or 0
                dates.append(r["game_date"])
                run.append((sa, ga, toi))
            self._lg[season] = (dates, run)

    def _league_totals(self, season: int, before: str | None) -> tuple[int, int, int]:
        dates, run = self._lg.get(season, ([], []))
        if not dates:
            return 0, 0, 0
        i = len(dates) if before is None else bisect.bisect_left(dates, before)
        return run[i - 1] if i else (0, 0, 0)

    def league(self, season: int, as_of: str) -> dict | None:
        """League save% and GAA over last season plus this one before `as_of`."""
        a, b = self._league_totals(season - 1, None), self._league_totals(season, as_of)
        sa, ga, toi = a[0] + b[0], a[1] + b[1], a[2] + b[2]
        if not sa or not toi:
            return None
        return {"sv": 1 - ga / sa, "gaa": ga * 3600 / toi}

    def starter(self, team: str, game_id: str) -> dict | None:
        rows = self.by_team_game.get((team, game_id), [])
        started = [r for r in rows if r.get("started")]
        if started:
            return started[0]
        return max(rows, key=lambda r: r.get("toi_seconds") or 0) if rows else None

    def busiest(self, team: str, season: int, as_of: str) -> int | None:
        """The team's most-used goalie over the window — the live fallback when
        no probable starter is named."""
        toi: dict[int, int] = defaultdict(int)
        for pid, rows in self.by_player.items():
            for r in rows:
                if (r["team"] == team and r["season"] in (season, season - 1)
                        and r["game_date"] < as_of):
                    toi[pid] += (r.get("toi_seconds") or 0) * (2 if r["season"] == season else 1)
        return max(toi, key=toi.get) if toi else None

    def asof(self, player_id: int | None, season: int, as_of: str) -> dict:
        """The six goalie columns for `player_id` strictly before `as_of`.
        Empty when the league baseline itself is missing (no data loaded)."""
        lg = self.league(season, as_of)
        if lg is None:
            return {}
        hist = [r for r in self.by_player.get(int(player_id), [])
                if r["game_date"] < as_of and r["season"] in (season, season - 1)
                ] if player_id else []
        return _goalie_line(hist, season, lg)


def _goalie_line(hist: list[dict], season: int, lg: dict) -> dict:
    def tot(rows):
        return (sum(r.get("shots_against") or 0 for r in rows),
                sum(r.get("goals_against") or 0 for r in rows),
                sum(r.get("toi_seconds") or 0 for r in rows) / 60.0)

    def regressed(rows, k_shots, k_min):
        sa, ga, mins = tot(rows)
        sv = ((sa - ga) + k_shots * lg["sv"]) / (sa + k_shots)
        gaa = (ga + lg["gaa"] * k_min / 60.0) / ((mins + k_min) / 60.0)
        return round(sv, 4), round(gaa, 4)

    def saved_above(rows):
        sa, ga, _ = tot(rows)
        return round(sa * (1 - lg["sv"]) - ga, 3)

    sv, gaa = regressed(hist, GOALIE_PRIOR_SHOTS, GOALIE_PRIOR_MINUTES)
    last5 = [r for r in hist if r.get("started")][-5:]
    sv5, gaa5 = regressed(last5, LAST5_PRIOR_SHOTS, LAST5_PRIOR_MINUTES)
    return {
        "save_pct": sv, "gaa": gaa,
        "gsaa": saved_above([r for r in hist if r["season"] == season]),
        "save_pct_last5": sv5, "gaa_last5": gaa5, "gsaa_last5": saved_above(last5),
    }


# ── team rates ───────────────────────────────────────────────────────────────

class TeamBook:
    def __init__(self, rows: list[dict]):
        self.by_team: dict[tuple[str, int], list[dict]] = defaultdict(list)
        for r in sorted(rows, key=lambda x: (x["game_date"], x["nhl_game_id"])):
            self.by_team[(r["team"], r["season"])].append(r)
        self._dates = {k: [r["game_date"] for r in v] for k, v in self.by_team.items()}
        self._final: dict[tuple[str, int], dict] = {}
        self._league_final: dict[int, dict] = {}

    @staticmethod
    def _rates(rows: list[dict]) -> dict:
        def s(key):
            return sum(r.get(key) or 0 for r in rows)
        n = len(rows)
        if not n:
            return {}
        saf, saa = s("sat_for_5v5"), s("sat_against_5v5")      # 5v5: every season
        ppo, tsh = s("pp_opportunities"), s("times_shorthanded")
        return {
            "corsi_for_pct": 100.0 * saf / (saf + saa) if saf + saa else None,
            "power_play_pct": s("pp_goals") / ppo if ppo else None,
            "penalty_kill_pct": 1 - s("pp_goals_against") / tsh if tsh else None,
            "shots_per_game": s("shots_for") / n,
            "shots_against_pg": s("shots_against") / n,
        }

    def final(self, team: str, season: int) -> dict:
        k = (team, season)
        if k not in self._final:
            self._final[k] = self._rates(self.by_team.get(k, []))
        return self._final[k]

    def league_final(self, season: int) -> dict:
        if season not in self._league_final:
            rows = [r for (t, s), v in self.by_team.items() if s == season for r in v]
            self._league_final[season] = self._rates(rows)
        return self._league_final[season]

    def asof(self, team: str, season: int, as_of: str) -> dict:
        """The five rate columns for `team`, strictly before `as_of`."""
        k = (team, season)
        rows = self.by_team.get(k, [])
        n = bisect.bisect_left(self._dates.get(k, []), as_of)
        cur = self._rates(rows[:n])
        prior = self.final(team, season - 1) or self.league_final(season - 1)
        out = {}
        for col in TEAM_RATE_COLUMNS:
            c, p = cur.get(col), prior.get(col)
            if c is None and p is None:
                out[col] = None
            elif p is None:
                out[col] = round(c, 4)
            elif c is None:
                out[col] = round(p, 4)
            else:
                out[col] = round((n * c + TEAM_PRIOR_GAMES * p) / (n + TEAM_PRIOR_GAMES), 4)
        return out


# ── loading ──────────────────────────────────────────────────────────────────

def _load(conn: DBConnection, table: str, cols: tuple[str, ...], seasons: list[int]) -> list[dict]:
    marks = ",".join("?" for _ in seasons)
    rows = conn.execute(
        f"SELECT {', '.join(cols)} FROM {table} WHERE season IN ({marks})",
        tuple(seasons)).fetchall()
    return [dict(zip(cols, r)) for r in rows]


_GOALIE_COLS = ("nhl_game_id", "player_id", "player_name", "game_id", "season",
                "game_date", "team", "started", "toi_seconds", "shots_against",
                "goals_against")
_TEAM_COLS = ("nhl_game_id", "team", "season", "game_date", "shots_for",
              "shots_against", "sat_for_5v5", "sat_against_5v5",
              "pp_opportunities", "pp_goals", "times_shorthanded", "pp_goals_against")


def goalie_book(conn: DBConnection, seasons: list[int]) -> GoalieBook:
    want = sorted({s for x in seasons for s in (x - 1, x)})
    return GoalieBook(_load(conn, "nhl_goalie_game_log", _GOALIE_COLS, want))


def team_book(conn: DBConnection, seasons: list[int]) -> TeamBook:
    want = sorted({s for x in seasons for s in (x - 1, x)})
    return TeamBook(_load(conn, "nhl_team_game_log", _TEAM_COLS, want))


# ── the historical rebuild ───────────────────────────────────────────────────

WRITE_BATCH = 2_000


def _in_batches(conn: DBConnection, sql: str, rows: list[dict]) -> None:
    """Commit per batch: tens of thousands of statements in one transaction is
    how the first log backfill lost its connection and its work. Every write
    here is idempotent, so a re-run after a failure is the recovery."""
    for i in range(0, len(rows), WRITE_BATCH):
        conn.executemany(sql, rows[i:i + WRITE_BATCH])
        conn.commit()


def rebuild_goalie_rows(conn: DBConnection, seasons: list[int], apply: bool) -> int:
    """One `nhl_goalie_stats` row per team per game: the STARTER's line before
    that game. Replaces the season-final snapshots for `seasons`."""
    book = goalie_book(conn, seasons)
    marks = ",".join("?" for _ in seasons)
    games = conn.execute(f"""
        SELECT game_id, game_date, season, home_team, away_team FROM games
        WHERE sport = 'NHL' AND season IN ({marks}) AND home_score IS NOT NULL
    """, tuple(seasons)).fetchall()
    rows, missing = [], 0
    for game_id, game_date, season, home, away in games:
        for team in (home, away):
            st = book.starter(team, game_id)
            if st is None:
                missing += 1
                continue
            line = book.asof(st["player_id"], season, game_date[:10])
            if not line:
                continue
            rows.append({"player_name": st["player_name"], "player_id": str(st["player_id"]),
                         "team": team, "season": season, "game_date": game_date[:10],
                         "game_id": game_id, **line})
    logger.info(f"goalie as-of rows: {len(rows):,} built, {missing:,} team-games "
                f"with no goalie in the log")
    if not apply:
        return len(rows)
    conn.execute(f"DELETE FROM nhl_goalie_stats WHERE season IN ({marks})", tuple(seasons))
    conn.commit()
    _in_batches(conn, """
        INSERT INTO nhl_goalie_stats (player_name, player_id, team, season, game_date,
            game_id, save_pct, gaa, gsaa, save_pct_last5, gaa_last5, gsaa_last5)
        VALUES (%(player_name)s, %(player_id)s, %(team)s, %(season)s, %(game_date)s,
            %(game_id)s, %(save_pct)s, %(gaa)s, %(gsaa)s, %(save_pct_last5)s,
            %(gaa_last5)s, %(gsaa_last5)s)
        ON CONFLICT (player_id, game_date) DO UPDATE SET
            team = EXCLUDED.team, game_id = EXCLUDED.game_id,
            save_pct = EXCLUDED.save_pct, gaa = EXCLUDED.gaa, gsaa = EXCLUDED.gsaa,
            save_pct_last5 = EXCLUDED.save_pct_last5, gaa_last5 = EXCLUDED.gaa_last5,
            gsaa_last5 = EXCLUDED.gsaa_last5
    """, rows)
    return len(rows)


def rebuild_team_rates(conn: DBConnection, seasons: list[int], apply: bool) -> int:
    """Overwrite the five rate columns on every `nhl_team_stats` row."""
    book = team_book(conn, seasons)
    marks = ",".join("?" for _ in seasons)
    keys = conn.execute(f"""
        SELECT team, season, as_of_date FROM nhl_team_stats WHERE season IN ({marks})
    """, tuple(seasons)).fetchall()
    updates = []
    for team, season, as_of in keys:
        r = book.asof(team, season, as_of[:10])
        updates.append({**r, "team": team, "season": season, "as_of_date": as_of})
    if apply and updates:
        _in_batches(conn, """
            UPDATE nhl_team_stats SET
                corsi_for_pct = %(corsi_for_pct)s, power_play_pct = %(power_play_pct)s,
                penalty_kill_pct = %(penalty_kill_pct)s, shots_per_game = %(shots_per_game)s,
                shots_against_pg = %(shots_against_pg)s
            WHERE team = %(team)s AND season = %(season)s AND as_of_date = %(as_of_date)s
        """, updates)
    return len(updates)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seasons", nargs=2, type=int, required=True, metavar=("START", "END"))
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    seasons = list(range(a.seasons[0], a.seasons[1] + 1))
    c = get_connection()
    try:
        print("goalie rows:", rebuild_goalie_rows(c, seasons, a.apply))
        print("team-stat rows re-rated:", rebuild_team_rates(c, seasons, a.apply))
        print("applied" if a.apply else "dry run — nothing written")
    finally:
        c.close()
