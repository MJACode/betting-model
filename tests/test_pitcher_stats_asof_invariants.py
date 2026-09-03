"""Invariants for the `mlb_pitcher_stats` rebuild (`data/pitcher_stats_rebuild`).

The bug being fixed: every historical row carried the pitcher's SEASON-FINAL
ERA, so `d_starter_era` and `d_starter_era_last3` — 40% of `mlb_f5_moneyline`'s
importance — told the model how the pitcher's whole season went before it
predicted a game inside it.

Every test here was watched failing with its fix removed. Where that is not
obvious from the assertion, the mutation that breaks it is named in the
docstring.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.pitcher_rates import LAST_N, last3_rates, outs_from_ip
from data.pitcher_stats_rebuild import (
    already_a_series,
    build_rows,
    constant_era_pitcher_seasons,
    self_inconsistent_rows,
)


def _app(date, ip, er=0, k=0, bb=0, h=0, hr=0, starter=True,
         pid="p1", season=2024, team="PHI"):
    return {"player_id": pid, "player_name": "Test Pitcher", "team": team,
            "season": season, "game_date": date, "game_id": "g" + date,
            "is_starter": starter, "ip": ip, "er": er, "k": k, "bb": bb,
            "h": h, "hr": hr}


# ── innings notation ─────────────────────────────────────────────────────────

def test_innings_are_thirds_not_decimals():
    """5.2 IP is five and TWO THIRDS — 17 outs, not 15.6.

    Mutation that must break this: `int(ip * 3)`, the obvious-looking
    conversion, which turns 5.2 into 15 and biases every ERA upward.
    """
    assert outs_from_ip(5.0) == 15
    assert outs_from_ip(5.1) == 16
    assert outs_from_ip(5.2) == 17
    assert outs_from_ip(6.0) == 18
    assert outs_from_ip(0.1) == 1


def test_a_fractional_part_that_is_not_thirds_raises():
    """If the column's meaning ever changes, every rate built on it is wrong.
    Failing loudly beats silently rounding .5 to .2 of an inning."""
    with pytest.raises(ValueError, match="baseball notation"):
        outs_from_ip(5.5)


def test_era_is_computed_from_outs_not_from_summed_notation():
    """Two 5.2-inning starts are 11.1 innings (34 outs), never 10.4.

    9 * 4 ER / (34/3) = 3.176. Naive summing gives 9*4/10.4 = 3.46 — a 9%
    overstatement that looks entirely plausible in a table.
    """
    rows = build_rows([_app("2024-04-01", 5.2, er=2),
                       _app("2024-04-07", 5.2, er=2),
                       _app("2024-04-13", 6.0, er=0)])
    third = rows[2]
    assert third["innings_pitched"] == pytest.approx(34 / 3, abs=1e-3)
    assert third["era"] == pytest.approx(3.176, abs=1e-3)


# ── the leak itself ──────────────────────────────────────────────────────────

def test_a_row_never_includes_its_own_start():
    """THE invariant. A row stamped date D holds the line ENTERING D.

    `_get_mlb_pitcher_stats` matches `game_date = D` exactly and hands the
    result over as the starter's form for that game, so a row that counted D's
    own line would be leaking the game being predicted.

    Mutation that must break this: accumulating before emitting in
    `build_rows`.
    """
    rows = build_rows([_app("2024-04-01", 9.0, er=0),    # shutout
                       _app("2024-04-07", 9.0, er=9)])   # blowup

    # First start: nothing came before it.
    assert rows[0]["era"] is None
    # Second start: 0 ER in 9 IP. If it counted its own 9 ER, this would be 4.50.
    assert rows[1]["era"] == pytest.approx(0.0)
    assert rows[1]["innings_pitched"] == pytest.approx(9.0)


def test_a_seasons_first_start_carries_no_prior_line():
    """No prior appearances means no rate, not a zero. A fabricated 0.00 ERA
    would be the most attractive number in the table."""
    rows = build_rows([_app("2024-04-01", 6.0, er=3)])
    assert len(rows) == 1
    for col in ("era", "k9", "bb9", "hr9", "whip", "era_last3", "k9_last3"):
        assert rows[0][col] is None, col
    assert rows[0]["innings_pitched"] == 0.0


def test_the_stored_era_actually_moves_across_a_season():
    """The shape of the bug, asserted directly: a real series varies.

    Aaron Nola's 33 rows for 2024 all read 3.57. Any rebuild that reproduces
    that shape has reproduced the leak.
    """
    apps = [_app(f"2024-04-{d:02d}", 6.0, er=d % 5) for d in range(1, 21)]
    eras = [r["era"] for r in build_rows(apps) if r["era"] is not None]
    assert len(set(eras)) > 5, "a genuine as-of-date series moves start to start"


# ── what counts toward the line ──────────────────────────────────────────────

def test_relief_outings_count_toward_the_season_line():
    """A season ERA counts every inning thrown, not only starts. Rows are
    emitted only at starts; the totals behind them include relief.

    Mutation that must break this: filtering the source query to
    `is_starter` only.
    """
    with_relief = build_rows([
        _app("2024-04-01", 6.0, er=0),
        _app("2024-04-04", 3.0, er=9, starter=False),   # disastrous relief
        _app("2024-04-07", 6.0, er=0)])
    without = build_rows([
        _app("2024-04-01", 6.0, er=0),
        _app("2024-04-07", 6.0, er=0)])

    assert without[-1]["era"] == pytest.approx(0.0)
    assert with_relief[-1]["era"] == pytest.approx(9.0)


def test_only_starts_get_a_row():
    """The engine looks up one row per (team, date) for the probable starter.
    A relief appearance must not create a row that could win that lookup."""
    rows = build_rows([_app("2024-04-01", 6.0), _app("2024-04-04", 1.0, starter=False)])
    assert [r["game_date"] for r in rows] == ["2024-04-01"]


def test_last3_is_a_true_rolling_window_over_the_raw_lines():
    """`era_last3` is 27 * ER / outs across the last three STARTS.

    It was `AVG(era)` over the last three stored rows until 2026-09-03 — the
    mean of three season-to-date rates, a smoothed restatement of `era` that
    carried almost nothing `era` did not. mike: *"yes on era_last3"*. The
    daily ingest was changed in the same commit and shares this arithmetic via
    `data/pitcher_rates.py`, so training and serving cannot drift.

    Mutation that must break this: dropping the `[-LAST_N:]` slice.
    """
    apps = [_app("2024-04-01", 9.0, er=9),    # blowup, then five shutouts
            _app("2024-04-07", 9.0, er=0),
            _app("2024-04-13", 9.0, er=0),
            _app("2024-04-19", 9.0, er=0),
            _app("2024-04-25", 9.0, er=0),
            _app("2024-05-01", 9.0, er=0)]
    rows = build_rows(apps)
    assert LAST_N == 3

    # Season-to-date ERA still carries the blowup.
    assert rows[-1]["era"] == pytest.approx(1.8)
    # The last three starts were all shutouts, so the rolling window is 0.00.
    assert rows[-1]["era_last3"] == pytest.approx(0.0)
    # Under the OLD smoothed definition this row read 3.25.
    assert rows[-1]["era_last3"] != pytest.approx(3.25)


def test_last3_weights_by_innings_not_by_start():
    """A one-inning disaster is one inning, not one third of the window.

    Averaging three ERAs would give (45.00 + 0 + 0) / 3 = 15.00. Pooling the
    raw lines gives 27 * 5 / 57 outs = 2.37, which is what actually happened.
    This is the information the smoothed definition threw away.
    """
    era_l3, _ = last3_rates([(1.0, 5, 0), (9.0, 0, 0), (9.0, 0, 0)])
    assert era_l3 == pytest.approx(2.368, abs=1e-3)


def test_a_seasons_first_start_has_no_rolling_window():
    """Nothing to average is None, never a fabricated 0.00."""
    assert last3_rates([]) == (None, None)
    assert last3_rates([(0.0, 0, 0)]) == (None, None)


def test_a_doubleheader_emits_one_row_per_date():
    """`mlb_pitcher_stats` is UNIQUE(player_id, game_date). Two starts on one
    date would abort the whole INSERT — after the DELETE has already run."""
    rows = build_rows([_app("2024-04-01", 5.0), _app("2024-04-01", 5.0)])
    assert len(rows) == 1


# ── the verify invariants ────────────────────────────────────────────────────

def test_constant_era_invariant_flags_the_leaked_shape():
    """Fed the real bug — 33 starts, one ERA — the check must catch it, and
    must not fire on a genuine series."""
    leaked = [{"player_id": "nola", "season": 2024, "era": 3.57} for _ in range(33)]
    assert constant_era_pitcher_seasons(leaked)

    real = [{"player_id": "nola", "season": 2026, "era": 3.5 + i / 100}
            for i in range(33)]
    assert not constant_era_pitcher_seasons(real)


def test_constant_era_invariant_ignores_a_short_sample():
    """Three starts at the same ERA is a coincidence, not a leak."""
    short = [{"player_id": "x", "season": 2024, "era": 3.00} for _ in range(3)]
    assert not constant_era_pitcher_seasons(short)


def test_self_inconsistency_catches_a_rate_that_disagrees_with_its_sample():
    """era must equal 9 * earned_runs / innings_pitched. This is what a
    naive-innings-summing bug looks like once it reaches the table."""
    good = [{"era": 3.0, "earned_runs": 10, "innings_pitched": 30.0}]
    bad = [{"era": 3.46, "earned_runs": 4, "innings_pitched": 34 / 3}]
    assert not self_inconsistent_rows(good)
    assert self_inconsistent_rows(bad)


def test_a_rounding_artifact_on_a_tiny_sample_is_not_a_defect():
    """5 earned runs in a third of an inning is a true 135.00 ERA. `era` comes
    from exact outs while `innings_pitched` is stored rounded, so recomputing
    gives 135.01 — an absolute tolerance calls that broken and drowns the 9%
    error the check exists to find.

    Mutation that must break this: an absolute tolerance.
    """
    artifact = [{"era": 135.0, "earned_runs": 5, "innings_pitched": 0.3333}]
    assert not self_inconsistent_rows(artifact)

    # The real error stays caught at the same magnitude of ERA.
    real = [{"era": 135.0, "earned_runs": 5, "innings_pitched": 0.30}]
    assert self_inconsistent_rows(real)


# ── the refusal that protects real data ──────────────────────────────────────

class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=()):
        self._sql = sql
        return self

    def fetchall(self):
        return self._rows


def test_a_season_already_stored_as_a_real_series_is_protected():
    """2026 averages 17.2 distinct ERAs per pitcher-season; 2019-2025 average
    1.0. Rebuilding 2026 would replace the only honestly-built season we have
    with a reconstruction."""
    conn = _FakeConn([(2024, 1.0), (2025, 1.0), (2026, 17.2)])
    assert already_a_series(conn, [2024, 2025, 2026]) == [2026]


def test_the_protection_is_wired_into_rebuild_not_just_available():
    """A helper nobody calls protects nothing — this exact gap shipped once in
    the team rebuild. Assert `rebuild` consults it."""
    src = (Path(__file__).parent.parent / "data"
           / "pitcher_stats_rebuild.py").read_text(encoding="utf-8")
    body = src.split("def rebuild(")[1].split("\ndef ")[0]
    assert "already_a_series(conn, seasons)" in body
    assert "if protected and not force" in body


# ── the columns we write must exist ──────────────────────────────────────────

def test_every_emitted_column_exists_in_the_real_table():
    """`runs_home` was invented from the sport's scoring noun in the team
    rebuild; MLB spells it `runs_per_game_home`, and the INSERT failed AFTER
    the DELETE had run in the same transaction. Schema is parsed from
    `db_setup.py`, so this needs no database.
    """
    setup = (Path(__file__).parent.parent / "data"
             / "db_setup.py").read_text(encoding="utf-8")
    m = re.search(r"CREATE TABLE IF NOT EXISTS mlb_pitcher_stats \((.*?)\n\);",
                  setup, re.S)
    assert m, "mlb_pitcher_stats is not declared in db_setup.py"

    # Split on commas that are not inside parentheses -- the DDL packs several
    # columns onto one line and ends with UNIQUE(player_id, game_date).
    body, depth, part, parts = m.group(1), 0, "", []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(part); part = ""
        else:
            part += ch
    parts.append(part)

    real = set()
    for p in parts:
        p = p.strip()
        if not p or p.startswith(("--", "PRIMARY", "UNIQUE", "FOREIGN",
                                  "CONSTRAINT", "CHECK")):
            continue
        real.add(p.split()[0])

    assert {"innings_pitched", "strikeouts", "era_last3"} <= real, \
        "the DDL parser is not finding packed columns"

    emitted = set()
    for r in build_rows([_app("2024-04-01", 6.0), _app("2024-04-07", 6.0)]):
        emitted |= set(r)
    missing = sorted(emitted - real)
    assert not missing, f"rebuild writes columns mlb_pitcher_stats lacks: {missing}"
