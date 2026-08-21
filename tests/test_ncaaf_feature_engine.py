"""
NCAAF feature-engine tests.

Covers the two load-bearing behaviours (the FBS gate and bowl detection), the
row assembly, and — via a small sqlite shim — the real bulk ASOF path against
the real schema, which is where a leak would actually hide.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402
from data.db_setup import SCHEMA_SQL  # noqa: E402
from features.feature_engine import _compute_target  # noqa: E402
from features.ncaaf_feature_engine import (  # noqa: E402
    _assemble_ncaaf_features, build_bulk_ncaaf_lookups,
    build_ncaaf_features_from_bulk, is_bowl_game,
)


# ── Bowl detection ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("week,stype,date,season,expected", [
    (5,    "regular",     "2025-09-27", 2025, 0),
    (14,   "regular",     "2025-11-29", 2025, 0),
    (1,    "postseason",  "2025-12-20", 2025, 1),   # explicit season type
    (17,   "regular",     "2025-12-20", 2025, 1),   # week past the floor
    (1,    None,          "2026-01-19", 2025, 1),   # January = postseason by convention
    (None, None,          "2025-10-04", 2025, 0),
])
def test_is_bowl_game(week, stype, date, season, expected):
    assert is_bowl_game(week, stype, date, season) == expected


# ── Row assembly ──────────────────────────────────────────────────────────────

def _stats(**over):
    base = dict(games_played=6, sp_overall=20.0, sp_offense=35.0, sp_defense=15.0,
                srs=10.0, talent=900.0, epa_per_play_off=0.20,
                epa_per_play_def=-0.05, success_rate_off=0.45,
                success_rate_def=0.38, explosiveness_off=1.30,
                plays_per_game=70.0, points_per_game=34.0,
                points_allowed_pg=18.0, points_last_3=36.0,
                point_differential=16.0, wins=5, losses=1, conference="SEC")
    base.update(over)
    return base


def _assemble(home=None, away=None, sched=None, odds=None):
    return _assemble_ncaaf_features(
        "NCAAF_2025-10-04_away_home", "2025-10-04", "Home U", "Away U", 2025,
        home if home is not None else _stats(),
        away if away is not None else _stats(sp_overall=10.0, talent=700.0,
                                             points_per_game=24.0, conference="MAC"),
        36.0, 22.0, 7, 14, sched or {"week": 6}, odds)


def test_fbs_gate_returns_none_when_a_team_has_no_stats_row():
    """
    An FCS opponent has no ncaaf_team_stats row by construction, so this is the
    whole FBS-vs-FCS exclusion. Returning None (not a row of nulls) makes the
    skip explicit at score time.
    """
    assert _assemble(away={}) is None
    assert _assemble(home={}) is None


def test_assembly_diffs_and_context():
    f = _assemble()
    assert f["d_sp_overall"] == pytest.approx(10.0)
    assert f["d_talent"] == pytest.approx(200.0)
    assert f["d_points_per_game"] == pytest.approx(10.0)
    assert f["d_points_last_3"] == pytest.approx(14.0)
    assert f["d_rest_days"] == pytest.approx(-7.0)     # home 7, away 14 (bye)
    assert f["home_win_pct"] == pytest.approx(5 / 6, abs=1e-3)
    assert f["week"] == 6
    assert f["is_bowl"] == 0


def test_game_tier_counts_power_four_sides():
    assert _assemble()["game_tier"] == 1                                   # SEC vs MAC
    assert _assemble(away=_stats(conference="Big Ten"))["game_tier"] == 2  # P4 vs P4
    assert _assemble(home=_stats(conference="MAC"),
                     away=_stats(conference="Sun Belt"))["game_tier"] == 0


def test_season_opener_gets_a_zero_rest_differential_not_a_null():
    """
    Both sides equally rested is the truth in week 1, not a fabricated fill —
    and a null here would drop every opener from the training matrix.
    """
    f = _assemble_ncaaf_features(
        "g", "2025-08-30", "Home U", "Away U", 2025, _stats(), _stats(),
        None, None, None, None, {"week": 1}, None)
    assert f["d_rest_days"] == 0.0


def test_market_number_attaches_from_the_odds_row():
    f = _assemble(odds={"spread_home": -7.5, "total_line": 55.5})
    assert f["spread_home"] == -7.5
    assert f["total_line"] == 55.5
    assert _assemble()["total_line"] is None


def test_early_season_is_flagged_not_gated():
    """A >=10-game gate (the MLB rule) would blank most of a 12-game season."""
    assert _assemble(home=_stats(games_played=1))["is_early_season"] == 1
    assert _assemble()["is_early_season"] == 0


# ── Bulk ASOF path, against the real schema ───────────────────────────────────

class _SqliteShim:
    """Minimal DBConnection stand-in: converts %s placeholders to sqlite's ?."""

    def __init__(self, conn):
        self._c = conn

    def execute(self, sql, params=None):
        return self._c.execute(sql.replace("%s", "?"), params or [])


@pytest.fixture
def ncaaf_db():
    raw = sqlite3.connect(":memory:")
    raw.executescript(SCHEMA_SQL)

    def game(gid, date, home, away, hs, aws, week, season=2025, neutral=0, conf=1):
        raw.execute("""INSERT INTO games (game_id, sport, season, game_date,
                       home_team, away_team, home_score, away_score, home_win,
                       week, neutral_site, conference_game)
                       VALUES (?,'NCAAF',?,?,?,?,?,?,?,?,?,?)""",
                    (gid, season, date, home, away, hs, aws,
                     None if hs is None else int(hs > aws), week, neutral, conf))

    def snap(team, as_of, gp, sp, ppg, pa, conf="SEC", season=2025):
        raw.execute("""INSERT INTO ncaaf_team_stats (team, season, as_of_date,
                       games_played, sp_overall, sp_offense, sp_defense, srs, talent,
                       epa_per_play_off, epa_per_play_def, success_rate_off,
                       success_rate_def, explosiveness_off, plays_per_game,
                       points_per_game, points_allowed_pg, points_last_3,
                       point_differential, wins, losses, conference)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (team, season, as_of, gp, sp, 35.0, 15.0, 10.0, 900.0,
                     0.2, -0.05, 0.45, 0.38, 1.3, 70.0, ppg, pa, ppg,
                     ppg - pa, gp, 0, conf))

    # Two completed games, then the game under test in week 4.
    game("g1", "2025-08-30", "Home U", "Cupcake FCS", 49, 3, 1)
    game("g2", "2025-09-13", "Home U", "Away U", 28, 24, 3)
    game("g3", "2025-09-27", "Home U", "Away U", None, None, 4, neutral=1)

    # Snapshots: a stale one, the correct one, and a FUTURE one that must be
    # ignored by the ASOF lookup — this is the leak the whole design guards.
    for team in ("Home U", "Away U"):
        snap(team, "2025-08-01", 0, 20.0, 30.0, 20.0)
        snap(team, "2025-09-26", 2, 22.0, 35.0, 18.0)
        snap(team, "2025-10-10", 5, 99.0, 99.0, 1.0)      # AFTER g3 — must not be used
    # Away U is weaker, and is a G5 team
    raw.execute("UPDATE ncaaf_team_stats SET sp_overall = 5.0, conference = 'MAC' "
                "WHERE team = 'Away U' AND as_of_date = '2025-09-26'")

    # Seed a LOWER-priority provider first, then the preferred one, so the
    # bulk loader's priority CASE has something to actually resolve.
    lo = config.NCAAF_LINE_BOOKMAKER_PRIORITY[-2]
    hi = config.NCAAF_LINE_BOOKMAKER_PRIORITY[0]
    for book, spread, total in ((lo, -3.0, 44.5), (hi, -7.5, 55.5)):
        for market, sp, tot in (("spreads", spread, None), ("totals", None, total)):
            raw.execute("""INSERT INTO odds (game_id, sport, market, bookmaker,
                           snapshot_type, snapshot_at, spread_home, total_line)
                           VALUES ('g3','NCAAF',?,?,'open','2025-09-27',?,?)""",
                        (market, book, sp, tot))
    raw.commit()
    yield _SqliteShim(raw)
    raw.close()


def test_bulk_asof_never_reads_a_future_snapshot(ncaaf_db):
    bulk = build_bulk_ncaaf_lookups(ncaaf_db, [2025])
    f = build_ncaaf_features_from_bulk(
        bulk, "g3", "2025-09-27", "Home U", "Away U", 2025,
        bulk["odds"].get(("g3", "spreads")))
    assert f is not None
    # The 2025-10-10 snapshot (sp_overall 99) must be invisible on 2025-09-27.
    assert f["home_sp_offense"] == 35.0
    assert f["d_sp_overall"] == pytest.approx(17.0)   # 22.0 home − 5.0 away
    assert f["game_tier"] == 1                        # SEC vs MAC


def test_bulk_attaches_schedule_context_and_line(ncaaf_db):
    bulk = build_bulk_ncaaf_lookups(ncaaf_db, [2025])
    f = build_ncaaf_features_from_bulk(
        bulk, "g3", "2025-09-27", "Home U", "Away U", 2025,
        bulk["odds"].get(("g3", "spreads")))
    assert f["is_neutral_site"] == 1
    assert f["week"] == 4
    assert f["spread_home"] == -7.5
    # Rolling form comes from completed games only
    assert f["d_points_last_3"] is not None


def test_bulk_returns_none_for_a_team_with_no_snapshot(ncaaf_db):
    bulk = build_bulk_ncaaf_lookups(ncaaf_db, [2025])
    assert build_ncaaf_features_from_bulk(
        bulk, "g1", "2025-08-30", "Home U", "Cupcake FCS", 2025, None) is None


def test_bulk_loads_both_markets_of_the_historical_line(ncaaf_db):
    bulk = build_bulk_ncaaf_lookups(ncaaf_db, [2025])
    assert bulk["odds"][("g3", "spreads")]["spread_home"] == -7.5
    assert bulk["odds"][("g3", "totals")]["total_line"] == 55.5


# ── Targets (generic path, exercised with NCAAF numbers) ──────────────────────

def test_spread_target_uses_the_home_relative_line():
    # Home wins by 4 but is laying 7.5 → does NOT cover.
    assert _compute_target("ncaaf_spread", "spreads", 28, 24, 1, None, 0, 0,
                           {"spread_home": -7.5}) == 0
    # Home wins by 10 laying 7.5 → covers.
    assert _compute_target("ncaaf_spread", "spreads", 34, 24, 1, None, 0, 0,
                           {"spread_home": -7.5}) == 1


def test_totals_and_moneyline_targets():
    assert _compute_target("ncaaf_over_under", "totals", 35, 24, 1, None, 0, 0,
                           {"total_line": 55.5}) == 1
    assert _compute_target("ncaaf_over_under", "totals", 20, 17, 1, None, 0, 0,
                           {"total_line": 55.5}) == 0
    assert _compute_target("ncaaf_moneyline", "h2h", 28, 24, 1, None, 0, 0, None) == 1


def test_a_push_yields_no_target():
    assert _compute_target("ncaaf_spread", "spreads", 31, 24, 1, None, 0, 0,
                           {"spread_home": -7.0}) is None
    assert _compute_target("ncaaf_over_under", "totals", 30, 25, 1, None, 0, 0,
                           {"total_line": 55.0}) is None


def test_bulk_resolves_the_preferred_provider_when_several_priced_the_game(ncaaf_db):
    """
    Several CFBD providers can price the same game. The loader must take the
    highest-priority one, not whichever the database happened to return first.
    """
    bulk = build_bulk_ncaaf_lookups(ncaaf_db, [2025])
    assert bulk["odds"][("g3", "spreads")]["spread_home"] == -7.5   # preferred
    assert bulk["odds"][("g3", "totals")]["total_line"] == 55.5


# ── FBS gate: row existence is NOT the test ───────────────────────────────────

def test_fbs_gate_rejects_an_fcs_team_that_has_a_snapshot_row():
    """
    CFBD's ratings/talent endpoints cover FCS, so the backfill writes snapshots
    for FCS programs too (162 of them in the loaded data). Those rows exist but
    carry no SP+, and pricing a game off them is exactly what the gate exists to
    prevent — dropna only protects TRAINING, not live scoring.
    """
    fcs = _stats(classification=None, sp_overall=None)
    assert _assemble(away=fcs) is None
    assert _assemble(home=fcs) is None


def test_fbs_gate_uses_sp_plus_as_evidence_when_classification_is_missing():
    """SP+ is FBS-only, so its presence is proof of membership."""
    unlabelled_fbs = _stats(classification=None, sp_overall=18.0)
    assert _assemble(away=unlabelled_fbs) is not None


def test_fbs_gate_rejects_an_explicitly_fcs_classification():
    assert _assemble(away=_stats(classification="fcs")) is None


# ── Sport dispatch: NCAAF must never fall through to another sport's engine ──

def test_backtester_and_scorer_dispatch_ncaaf_explicitly():
    """
    Regression guard for the session-34 bug class: a sport with no explicit
    branch falls into the NHL `else`, gets built with NHL features off a
    nhl_bulk of None, and produces numbers that look like model failure but are
    plumbing failure. Cheap source-level assertion, same style as the
    DraftKings-filter tripwires in tests/test_multi_book_odds.py.
    """
    root = Path(__file__).parent.parent
    bt = (root / "models" / "backtester.py").read_text(encoding="utf-8")
    sc = (root / "models" / "scorer.py").read_text(encoding="utf-8")
    assert 'sp == "NCAAF"' in bt, "backtester has no NCAAF feature branch"
    assert "build_ncaaf_features_from_bulk" in bt
    assert "build_bulk_ncaaf_lookups" in bt, "backtester never builds ncaaf_bulk"
    assert 'sport == "NCAAF"' in sc, "scorer has no NCAAF feature branch"
    assert "build_ncaaf_game_features" in sc
    # the NCAAF branch must come BEFORE the NHL else-fallthrough in both
    assert bt.index('sp == "NCAAF"') < bt.index("_build_nhl_features_from_bulk(\n")
