"""The two checks that would have caught the team-stats leak on day one.

`docs/team_stats_leak.md`: `mlb_team_stats`, `nba_team_stats`, `nhl_team_stats`
and `wnba_team_stats` each stored ONE OR TWO rows per historical season, and
each row held that season's FINAL numbers stamped before the season began. NBA
BOS season 2023 carried 82 games played and 57 wins at `as_of_date
2022-09-01` -- a month before the season started.

Neither of these is clever. Both are cheap, both are permanent, and either one
alone fails instantly on that row. They exist because the rebuild has to be
verified by something other than the person who wrote it.

Pure functions over a fake table -- no database. The production sweep lives in
`data/team_stats_rebuild.verify`, which applies exactly these rules against the
real tables.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.team_stats_rebuild import (MIN_SNAPSHOTS_PER_SEASON,
                                     impossible_games_played,
                                     seasons_with_too_few_snapshots)


# ── 1. a row cannot know about games that have not been played ───────────────

def test_the_leak_row_is_caught():
    """The exact row: 82 games played, stamped before the season began."""
    rows = [{"team": "BOS", "season": 2023, "as_of_date": "2022-09-01",
             "games_played": 82}]
    played = {("BOS", 2023, "2022-09-01"): 0}
    bad = impossible_games_played(rows, played)
    assert len(bad) == 1
    assert bad[0]["claimed"] == 82 and bad[0]["actual"] == 0


def test_an_honest_row_passes():
    rows = [{"team": "BOS", "season": 2023, "as_of_date": "2023-01-15",
             "games_played": 40}]
    assert impossible_games_played(rows, {("BOS", 2023, "2023-01-15"): 40}) == []


def test_claiming_fewer_games_than_played_is_fine():
    """A snapshot may lag — a team that has played 41 and is recorded at 40 is
    stale, not leaked. Only claiming MORE than happened is impossible."""
    rows = [{"team": "BOS", "season": 2023, "as_of_date": "2023-01-15",
             "games_played": 40}]
    assert impossible_games_played(rows, {("BOS", 2023, "2023-01-15"): 41}) == []


def test_one_game_date_boundary_mismatch_is_tolerated():
    """Rebuild vs live ingest can disagree by one game on the date boundary
    (TEXT as_of_date / strict `<`). claimed == actual + 1 is noise, not a leak."""
    rows = [{"team": "LAD", "season": 2025, "as_of_date": "2025-09-28",
             "games_played": 162}]
    assert impossible_games_played(rows, {("LAD", 2025, "2025-09-28"): 161}) == []


def test_two_games_of_lookahead_is_still_caught():
    """Beyond the 1-game boundary tolerance, extra GP is still impossible —
    and the original leak (162 in April vs ~0 played) fails by a mile."""
    rows = [{"team": "BOS", "season": 2023, "as_of_date": "2023-01-15",
             "games_played": 42}]
    bad = impossible_games_played(rows, {("BOS", 2023, "2023-01-15"): 40})
    assert len(bad) == 1


def test_season_final_in_april_is_still_caught():
    """The original leak shape: games_played=162 stamped before the season."""
    rows = [{"team": "NYY", "season": 2024, "as_of_date": "2024-04-01",
             "games_played": 162}]
    bad = impossible_games_played(rows, {("NYY", 2024, "2024-04-01"): 0})
    assert len(bad) == 1 and bad[0]["claimed"] == 162


def test_a_missing_count_is_reported_not_silently_passed():
    """No games data for that key means the row cannot be verified. Unverifiable
    is not the same as fine, and a check that treats it as fine is how the
    original leak survived."""
    rows = [{"team": "XXX", "season": 2023, "as_of_date": "2023-01-15",
             "games_played": 40}]
    bad = impossible_games_played(rows, {})
    assert len(bad) == 1 and bad[0]["actual"] is None


# ── 1b. MLB SBR / Stats-API twin codes ───────────────────────────────────────
# Job 90952 (2026-09-14): 2967 "impossible" MLB rows, all actual is None.
# Hist mlb_team_stats stores WAS/CHW/AZ/ATH; games stores WSH/CWS/ARI/OAK.
# WAS 2019-02-24 GP=1 failed because the played key was missing, not because
# 1 > 0+1. After aliasing, that row is claimed=1 / actual=1 (measured).

_MLB_TWINS = (("WAS", "WSH"), ("CHW", "CWS"), ("AZ", "ARI"), ("ATH", "OAK"))


def test_mlb_twin_alias_map_matches_sbr_canon():
    """Drift here re-opens the 2967-row false CRIT; the four pairs are the
    same ones sbr_loader / merge_mlb_twin_games already canonicalise."""
    from data.team_stats_rebuild import MLB_TEAM_CODE_ALIASES
    from scripts.merge_mlb_twin_games import CANON
    assert MLB_TEAM_CODE_ALIASES == CANON
    sbr = (Path(__file__).parent.parent / "data" / "ingestors"
           / "sbr_loader.py").read_text(encoding="utf-8")
    assert 'SBR_ABBREV_CANON = {"AZ": "ARI", "CHW": "CWS", "ATH": "OAK", "WAS": "WSH"}' in sbr


@pytest.mark.parametrize("stats_team,games_team", _MLB_TWINS)
def test_mlb_twin_codes_do_not_false_crit(stats_team, games_team):
    """A hist stats row under the SBR twin must resolve to the games count."""
    rows = [{"team": stats_team, "season": 2019, "as_of_date": "2019-02-24",
             "games_played": 1}]
    played = {(games_team, 2019, "2019-02-24"): 1}
    assert impossible_games_played(rows, played) == []


@pytest.mark.parametrize("stats_team,games_team", _MLB_TWINS)
def test_mlb_twin_reverse_lookup_also_resolves(stats_team, games_team):
    """Games-side code in stats, SBR code in played — either direction."""
    rows = [{"team": games_team, "season": 2019, "as_of_date": "2019-06-15",
             "games_played": 40}]
    played = {(stats_team, 2019, "2019-06-15"): 40}
    assert impossible_games_played(rows, played) == []


@pytest.mark.parametrize("stats_team,games_team", _MLB_TWINS)
def test_season_final_in_april_still_caught_on_twin_code(stats_team, games_team):
    """Aliasing must not hide the original leak: 162 GP stamped in April."""
    rows = [{"team": stats_team, "season": 2019, "as_of_date": "2019-04-01",
             "games_played": 162}]
    played = {(games_team, 2019, "2019-04-01"): 0}
    bad = impossible_games_played(rows, played)
    assert len(bad) == 1 and bad[0]["claimed"] == 162 and bad[0]["actual"] == 0


def test_unmatched_team_with_no_alias_still_fails():
    """A missing team that is not one of the four twins stays unverifiable."""
    rows = [{"team": "XXX", "season": 2019, "as_of_date": "2019-02-24",
             "games_played": 1}]
    played = {("WSH", 2019, "2019-02-24"): 1}
    bad = impossible_games_played(rows, played)
    assert len(bad) == 1 and bad[0]["actual"] is None


def test_feb_gp_climbing_vs_zero_regular_season_still_fails():
    """Spring-training-shaped dates are not a skip. Measured 2026-09-14: after
    alias, every WAS/CHW/AZ/ATH hist row and every MLB Feb–Mar snapshot is
    within +1 of aliased actual (1845 Feb–Mar, n_over_tol=0) because 2019–20
    `games` include those dates. If claimed GP climbed 3 vs 0 scored, that is
    still the leak shape and must CRIT — do not special-case February."""
    rows = [{"team": "WAS", "season": 2021, "as_of_date": "2021-02-24",
             "games_played": 3}]
    played = {("WSH", 2021, "2021-02-24"): 0}
    bad = impossible_games_played(rows, played)
    assert len(bad) == 1 and bad[0]["actual"] == 0


# ── 2. a season is not a season if it has two snapshots ──────────────────────

def test_a_single_snapshot_season_is_flagged():
    rows = [{"season": 2023, "as_of_date": "2022-09-01"},
            {"season": 2023, "as_of_date": "2022-09-01"}]
    assert seasons_with_too_few_snapshots(rows) == [(2023, 1)]


def test_a_two_snapshot_season_is_flagged():
    """MLB's shape: `YYYY-01-01` and `YYYY-10-01`, and both were season-final."""
    rows = [{"season": 2024, "as_of_date": "2024-01-01"},
            {"season": 2024, "as_of_date": "2024-10-01"}]
    assert seasons_with_too_few_snapshots(rows) == [(2024, 2)]


def test_a_real_series_passes():
    rows = [{"season": 2026, "as_of_date": f"2026-04-{d:02d}"}
            for d in range(1, MIN_SNAPSHOTS_PER_SEASON + 2)]
    assert seasons_with_too_few_snapshots(rows) == []


def test_ncaaf_shaped_weekly_snapshots_pass():
    """NCAAF was built correctly — 14-16 weekly snapshots per season — and is
    the template. The threshold must not flag the one table that is right."""
    rows = [{"season": 2024, "as_of_date": f"2024-09-{d:02d}"}
            for d in range(1, 15)]
    assert seasons_with_too_few_snapshots(rows) == []


# ── 3. the detail that matters most: strictly BEFORE ─────────────────────────
# `_team_stats_before` selects `as_of_date <= game_date`, so a row dated D that
# included D's own game would hand the model that game's result -- the same leak
# one day narrower and far harder to see than the original.

from data.team_stats_rebuild import build_rows  # noqa: E402


def _game(date, home, away, hs, as_, season=2024, ot=None):
    return {"date": date, "season": season, "home": home, "away": away,
            "hs": float(hs), "as_": float(as_),
            "home_win": 1 if hs > as_ else 0, "ot": ot, "home_win_reg": None}


GAMES = [
    _game("2024-04-01", "AAA", "BBB", 5, 3),
    _game("2024-04-02", "AAA", "BBB", 1, 7),
    _game("2024-04-03", "BBB", "AAA", 2, 6),
]


def test_a_row_never_includes_its_own_date():
    """The row for AAA on 04-02 must know only about 04-01."""
    rows = {(r["team"], r["as_of_date"]): r for r in build_rows("MLB", GAMES)}
    r = rows[("AAA", "2024-04-02")]
    assert r["games_played"] == 1, "the row swallowed its own game"
    assert r["wins"] == 1 and r["losses"] == 0
    assert r["runs_per_game"] == 5.0
    assert r["run_differential"] == 2


def test_the_first_date_of_a_season_produces_no_row():
    """Before any game there is nothing to know, and a zero row would read as a
    team with a 0-0 record rather than as absent."""
    rows = build_rows("MLB", GAMES)
    assert not [r for r in rows if r["as_of_date"] == "2024-04-01"]


def test_counts_accumulate_across_dates():
    rows = {(r["team"], r["as_of_date"]): r for r in build_rows("MLB", GAMES)}
    r = rows[("AAA", "2024-04-03")]
    assert r["games_played"] == 2
    assert r["wins"] == 1 and r["losses"] == 1
    assert r["run_differential"] == (5 + 1) - (3 + 7)


def test_last_n_is_a_rolling_window_not_a_season_constant():
    """The whole point: `runs_last_5` currently holds a season-final number, so
    `d_runs_last_5` -- a top-10 feature -- is a leaked constant per team.

    The fixture runs SEVEN games on purpose. With fewer games than the window,
    the rolling mean and the season mean are the same number, and the first
    version of this test passed happily against a mutation that replaced the
    window with a season average.
    """
    scores = [10, 10, 10, 10, 0, 0, 0]
    games = [_game(f"2024-04-{i + 1:02d}", "AAA", "BBB", s, 1)
             for i, s in enumerate(scores)]
    games.append(_game("2024-04-08", "AAA", "BBB", 1, 1))   # a date to read at
    rows = {(r["team"], r["as_of_date"]): r for r in build_rows("MLB", games)}
    r = rows[("AAA", "2024-04-08")]
    assert r["games_played"] == 7
    assert r["runs_per_game"] == round(40 / 7, 4)      # season mean
    assert r["runs_last_5"] == 4.0                     # (10+10+0+0+0) / 5
    assert r["runs_last_5"] != r["runs_per_game"], (
        "the fixture cannot tell a rolling window from a season average")


def test_home_and_away_splits_use_only_the_relevant_games():
    rows = {(r["team"], r["as_of_date"]): r for r in build_rows("MLB", GAMES)}
    r = rows[("AAA", "2024-04-03")]
    assert r["runs_per_game_home"] == 3.0   # 5 and 1, both at home
    assert r["runs_per_game_away"] is None  # AAA has not played away yet


def test_nhl_splits_regulation_losses_from_ot_losses():
    games = [_game("2024-10-10", "AAA", "BBB", 2, 3, ot=1),
             _game("2024-10-12", "AAA", "BBB", 1, 4, ot=None)]
    rows = {(r["team"], r["as_of_date"]): r for r in build_rows("NHL", games)}
    r = rows[("AAA", "2024-10-12")]
    assert r["games_played"] == 1 and r["wins"] == 0
    assert r["ot_losses"] == 1 and r["losses"] == 0


def test_every_sport_uses_its_own_scoring_noun():
    """A column name copied from MLB into the NBA table writes nothing and
    raises nothing — the row simply lacks the feature."""
    from data.team_stats_rebuild import SPORTS
    for sport, cfg in SPORTS.items():
        g = [_game("2024-04-01", "AAA", "BBB", 5, 3),
             _game("2024-04-02", "AAA", "BBB", 1, 7)]
        rows = build_rows(sport, g)
        assert rows, sport
        assert f"{cfg['noun']}_per_game" in rows[0], sport
        assert cfg["diff"] in rows[0], sport


# ── 4. never overwrite a season that is already correct ──────────────────────

def test_a_season_that_is_already_a_series_is_refused():
    """2026 is stored correctly in all four tables — daily snapshots with REAL
    rate stats, the only honest rate data we have. The first dry run of the
    rebuild was scoped to all 18 seasons and would have deleted it, replacing
    measured OPS with last season's carried-forward values.

    The refusal belongs in the code, not in the operator's memory.
    """
    from data.team_stats_rebuild import already_a_series

    class _Conn:
        def execute(self, sql, params=None):
            self._n = len(params) - 0
            return self
        def fetchall(self):
            # 2025 leaked (2 snapshots), 2026 a real series (141)
            return [(2025, 2), (2026, 141)]

    assert already_a_series(_Conn(), "mlb_team_stats", [2025, 2026]) == [2026]


def test_the_guard_is_wired_so_protected_seasons_are_REMOVED():
    """Testing `already_a_series` alone is not enough: it returns the seasons to
    protect, and the caller has to drop them. Inverting that condition
    (`if protected and force`) left the helper's own test passing while the
    rebuild happily overwrote 2026 — so the wiring gets its own assertion."""
    src = (Path(__file__).parent.parent / "data"
           / "team_stats_rebuild.py").read_text(encoding="utf-8")
    i = src.index("def rebuild_sport(")
    body = src[i:src.index(chr(10) + "def ", i + 10)]
    assert "if protected and not force:" in body, (
        "protected seasons are not being excluded when force is off")
    guard_at = body.index("already_a_series")
    delete_at = body.index("DELETE FROM")
    assert guard_at < delete_at, "the guard runs after the DELETE"


def test_the_guard_uses_the_same_threshold_as_the_invariant():
    """Two thresholds that can drift apart would let a season be both 'too thin
    to trust' and 'thick enough to overwrite'."""
    src = (Path(__file__).parent.parent / "data"
           / "team_stats_rebuild.py").read_text(encoding="utf-8")
    i = src.index("def already_a_series(")
    body = src[i:src.index("\ndef ", i + 10)]
    assert "MIN_SNAPSHOTS_PER_SEASON" in body


# ── 5. the columns we write must exist ───────────────────────────────────────

def test_every_emitted_column_exists_in_the_real_table():
    """The check that would have saved a failed production write.

    `runs_home` was derived from the sport's scoring noun. Tidy, and wrong: MLB
    spells it `runs_per_game_home`. The INSERT failed against the real table
    AFTER the DELETE had already run in the same transaction. It rolled back
    cleanly, but only because Postgres aborts the whole transaction on error —
    the design was one autocommit away from emptying seven seasons.

    Schemas are parsed from `data/db_setup.py`, so this needs no database.
    """
    import re

    from data.team_stats_rebuild import RATE_COLUMNS, SPORTS, build_rows

    setup = (Path(__file__).parent.parent / "data"
             / "db_setup.py").read_text(encoding="utf-8")

    def columns_of(table: str) -> set:
        pattern = r"CREATE TABLE IF NOT EXISTS " + table + r" \((.*?)\n\)"
        m = re.search(pattern, setup, re.S)
        assert m, table + " is not declared in db_setup.py"
        cols = set()
        # Several columns per line is normal here -- "ops REAL, wrc_plus REAL,
        # woba REAL" -- so split on commas, not just on newlines. Reading only
        # the first token per LINE saw 5 of mlb_team_stats' 26 columns and
        # reported the other 21 as missing.
        flat = m.group(1).replace(chr(10), " ")
        for frag in flat.split(","):
            frag = frag.strip()
            if not frag or frag.startswith(("--", "PRIMARY", "UNIQUE", "FOREIGN",
                                            "CONSTRAINT", "CHECK")):
                continue
            name = frag.split()[0]
            if name.isidentifier():
                cols.add(name)
        return cols

    games = [_game("2024-04-01", "AAA", "BBB", 5, 3),
             _game("2024-04-02", "BBB", "AAA", 2, 6),
             _game("2024-04-03", "AAA", "BBB", 1, 7)]

    for sport, cfg in SPORTS.items():
        real = columns_of(cfg["table"])
        emitted = set()
        for r in build_rows(sport, games):
            emitted |= set(r)
        emitted |= set(RATE_COLUMNS[cfg["table"]])
        missing = sorted(emitted - real)
        assert not missing, (
            sport + " writes columns " + cfg["table"] + " lacks: " + str(missing))


# ── 6. verify() skips live season + normalizes TEXT dates ────────────────────

def test_verify_skips_live_season_for_impossible_but_keeps_thin_check():
    """Current max season is live ingest; comparing GP to scored games alone
    false-CRITs (stats ahead of games). Thin snapshots still cover every season
    so a 1–2 row leak in the live year would still fail."""
    from data.team_stats_rebuild import verify

    class _Conn:
        def __init__(self):
            self._q = None

        def execute(self, sql, params=None):
            self._q = (sql, params)
            return self

        def fetchall(self):
            sql, params = self._q
            if "FROM mlb_team_stats" in sql and "games_played" in sql:
                return [
                    # Live: would be false CRIT (35 claimed, 0 scored in fixtures).
                    ("MIN", 2026, "2026-05-05", 35),
                    # Honest hist: claimed == scored-before.
                    ("LAD", 2025, "2025-09-28", 10),
                    # Thin leak shape (2 snapshots) — still must CRIT via thin.
                    ("NYY", 2024, "2024-01-01", 0),
                    ("NYY", 2024, "2024-10-01", 0),
                ]
            if "FROM games" in sql:
                # Hist seasons only (live skipped for impossible).
                # 10 LAD games strictly before 2025-09-28; one late NYY game so
                # the 2024 thin rows resolve actual=0 (claimed 0) and are not
                # "unverifiable".
                return [
                    (f"2025-04-{i:02d}", 2025, "LAD", "SF", 5, 3, 1, None, None)
                    for i in range(1, 11)
                ] + [
                    ("2024-11-01", 2024, "NYY", "BOS", 1, 0, 1, None, None),
                ]
            return []

    v = verify(_Conn(), "MLB", [2024, 2025, 2026])
    assert v["skipped_live_season"] == 2026
    assert not any(r["season"] == 2026 for r in v["impossible"])
    assert (2024, 2) in v["thin_seasons"]
    assert v["impossible"] == []


def test_verify_tolerates_one_game_boundary_on_hist_season():
    """2025 LAD-style: claimed == actual_scored + 1 must not CRIT."""
    from data.team_stats_rebuild import verify

    class _Conn:
        def __init__(self):
            self._q = None

        def execute(self, sql, params=None):
            self._q = (sql, params)
            return self

        def fetchall(self):
            sql, _ = self._q
            if "FROM mlb_team_stats" in sql:
                return [("LAD", 2025, "2025-09-28", 11)]
            if "FROM games" in sql:
                return [
                    (f"2025-04-{i:02d}", 2025, "LAD", "SF", 5, 3, 1, None, None)
                    for i in range(1, 11)
                ]
            return []

    v = verify(_Conn(), "MLB", [2025, 2026])
    assert v["impossible"] == []
    assert v["skipped_live_season"] == 2026


def test_verify_normalizes_as_of_date_to_yyyy_mm_dd():
    """as_of_date and game_date are TEXT; timestamps must not break `<`."""
    from data.team_stats_rebuild import verify

    class _Conn:
        def __init__(self):
            self._q = None

        def execute(self, sql, params=None):
            self._q = (sql, params)
            return self

        def fetchall(self):
            sql, _ = self._q
            if "FROM mlb_team_stats" in sql:
                return [("LAD", 2025, "2025-06-15 00:00:00", 10)]
            if "FROM games" in sql:
                games = [
                    (f"2025-04-{i:02d}", 2025, "LAD", "SF", 4, 2, 1, None, None)
                    for i in range(1, 11)
                ]
                # Same-calendar-day game must NOT count (strictly before).
                games.append(("2025-06-15", 2025, "LAD", "SF", 1, 0, 1, None, None))
                return games
            return []

    v = verify(_Conn(), "MLB", [2025, 2026])
    assert v["impossible"] == []
    assert v["skipped_live_season"] == 2026


def test_verify_aliases_mlb_twins_and_still_catches_april_leak():
    """Job 90952: WAS hist row, WSH games. Alias must clear the None actual
    without skipping a 162-in-April leak on the same twin."""
    from data.team_stats_rebuild import verify

    class _Conn:
        def __init__(self):
            self._q = None

        def execute(self, sql, params=None):
            self._q = (sql, params)
            return self

        def fetchall(self):
            sql, _ = self._q
            if "FROM mlb_team_stats" in sql:
                return [
                    # Production false CRIT shape: SBR code, spring date, GP=1.
                    ("WAS", 2019, "2019-02-24", 1),
                    # Original leak on the same twin: season-final in April.
                    ("CHW", 2019, "2019-04-01", 162),
                ]
            if "FROM games" in sql:
                return [
                    ("2019-02-23", 2019, "WSH", "NYM", 3, 2, 1, None, None),
                    ("2019-04-15", 2019, "CWS", "KC", 4, 1, 1, None, None),
                ]
            return []

    v = verify(_Conn(), "MLB", [2019, 2026])
    assert v["skipped_live_season"] == 2026
    was = [r for r in v["impossible"] if r["team"] == "WAS"]
    chw = [r for r in v["impossible"] if r["team"] == "CHW"]
    assert was == [], was
    assert len(chw) == 1 and chw[0]["claimed"] == 162 and chw[0]["actual"] == 0
    assert (2019, 2) in v["thin_seasons"]
