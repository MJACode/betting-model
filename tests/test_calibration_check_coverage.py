"""The calibration health check must see every model, and judge only live ones.

Two faults, measured against production on 2026-10-12:

  * It WARNed every morning about `wnba_prop_player_threes` (+6.9pp over 159
    graded picks, last graded 2026-09-27) -- a model PAUSED since 2026-08-31
    that bets nothing, so the warning could never be acted on.
  * It read `mv_scored_pick_outcomes` alone, which grades MLB and WNBA pre-game
    models only. Every NBA, NHL, NFL, NCAAF and UFC model, every in-play model
    and every market rule (wnba_prop_market included: its id matches the view's
    `wnba_prop_%` filter, but no grading branch exists for it) could never be
    measured. The weekly fitter fixed the same blind spot on 2026-09-19 by
    reading settled bets from `picks`; the check was never moved with it.

All but the last two tests drive the real check end to end --
`run_system_health()` over a SQLite database -- so they fail on the code before
the fix on the verdict itself (STALE where it should be OK, SKIPPED where it
should be STALE, two results where there should be one). The last two pin the
settled-bet source directly: that its failure is reported, and which models it
covers. They fail before the fix because that source did not exist.
"""

import glob
import io
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import tracking.system_health as sh
from data.db_setup import SCHEMA_SQL, _MIGRATIONS
from models import probability_calibration as pc

REPO = Path(__file__).resolve().parent.parent


class _Shim:
    """sqlite3 behind the DBConnection surface the health check uses."""

    def __init__(self, path):
        self._c = sqlite3.connect(path)

    def execute(self, sql, params=()):
        return self._c.execute(sql, tuple(params))

    def commit(self):
        self._c.commit()

    def close(self):
        self._c.close()


def _make_db(with_view: bool = True):
    path = tempfile.mktemp(suffix=".db")
    c = sqlite3.connect(path)
    c.executescript(SCHEMA_SQL)
    for tbl, col, defn in _MIGRATIONS:
        try:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {defn}")
        except sqlite3.OperationalError:
            pass
    c.execute("""
        CREATE TABLE model_action_thresholds (
            model_id TEXT PRIMARY KEY, min_prob REAL NOT NULL,
            min_edge REAL NOT NULL DEFAULT 0, prob_only BOOLEAN NOT NULL DEFAULT 0,
            paused BOOLEAN NOT NULL DEFAULT 0, min_odds REAL)
    """)
    c.execute(pc.DDL)
    if with_view:
        # Only the columns the check reads. A table stands in for the view.
        c.execute("""
            CREATE TABLE mv_scored_pick_outcomes (
                pick_id INTEGER PRIMARY KEY, model_id TEXT, game_date TEXT,
                model_probability REAL, result TEXT)
        """)
    c.commit()
    return path, c


@pytest.fixture
def db(monkeypatch):
    path, c = _make_db()
    monkeypatch.setattr(sh, "get_connection", lambda: _Shim(path))
    yield c
    c.close()


def _register(c, model_id, created="2026-07-19 00:00:00"):
    c.execute("INSERT INTO model_registry (model_id, version, trained_on, "
              "train_seasons, is_active, created_at) VALUES (?,?,?,?,1,?)",
              (model_id, "v1", "2026-07-19", "2019-2025", created))


def _promote(c, model_id, promoted_at):
    c.execute("INSERT INTO model_calibration (model_id, fitted_at, promoted, "
              "promoted_at, payload) VALUES (?, ?, 1, ?, '{}')",
              (model_id, promoted_at, promoted_at))


_VIEW_ID = [1_000_000]


def _graded(c, model_id, n, wins, prob=0.70, first_day=1, last="2026-09-27"):
    """n rows in the graded view, `wins` of them won; the last on `last`."""
    for i in range(n):
        _VIEW_ID[0] += 1
        day = last if i == n - 1 else f"2026-08-{first_day + i % 27:02d}"
        c.execute("INSERT INTO mv_scored_pick_outcomes VALUES (?,?,?,?,?)",
                  (_VIEW_ID[0], model_id, day, prob,
                   "WIN" if i < wins else "LOSS"))


_GAME = [0]


def _bet(c, model_id, *, day, result, cal, raw=0.80, signal="BET", odds=-110,
         decision_odds=None, status=None, is_live=False):
    _GAME[0] += 1
    c.execute(
        "INSERT INTO picks (game_id, model_id, sport, game_date, pick_side, "
        "pick_label, model_probability, model_probability_cal, dk_implied_prob, "
        "edge, dk_odds, decision_odds, kelly_fraction, recommended_bet, "
        "bankroll_at_pick, signal_type, result, condition_status, is_live) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (f"g{_GAME[0]}", model_id, "X", day, "home", "HOME", raw, cal, 0.5,
         0.1, odds, decision_odds, 0.01, 1.0, 100.0, signal, result, status,
         is_live))


def _settled_bets(c, model_id, n, wins, cal, day="2026-10-05", is_live=False):
    for i in range(n):
        _bet(c, model_id, day=day, result="WIN" if i < wins else "LOSS",
             cal=cal, is_live=is_live)


def _calibration_results():
    out = [r for r in sh.run_system_health()["results"]
           if r["check_name"] == "model_calibration"]
    return out


def _only(results):
    assert len(results) == 1, (
        f"model_calibration must produce exactly one result, got {results}")
    return results[0]


# ── a paused model is reported, not judged ──────────────────────────────────

def test_a_paused_models_gap_is_informational_and_re_arms_when_unpaused(db, monkeypatch):
    """159 graded picks claiming 70%, hitting 59.7%: +10.3pp. Before the fix this
    turned the check STALE every morning for a model that bets nothing."""
    _register(db, "wnba_prop_player_threes")
    _register(db, "mlb_prop_batter_walks")
    _graded(db, "wnba_prop_player_threes", 159, 95, last="2026-09-27")
    _graded(db, "mlb_prop_batter_walks", 200, 140, last="2026-10-10")   # 70% / 70%
    db.commit()
    monkeypatch.setattr(config, "PAUSED_MODELS",
                        set(config.PAUSED_MODELS) | {"wnba_prop_player_threes"})

    res = _only(_calibration_results())
    assert res["status"] == sh.OK, res
    detail = res["detail"]
    # still visible: gap, row count and last graded date
    assert "wnba_prop_player_threes +10.3pp/159" in detail, detail
    assert "last graded 2026-09-27" in detail, detail
    assert "informational" in detail, detail
    # and the unpaused model is the one being judged
    assert "1 model(s) measured" in detail, detail

    # Unpausing re-arms it with no other change.
    monkeypatch.setattr(config, "PAUSED_MODELS",
                        set(config.PAUSED_MODELS) - {"wnba_prop_player_threes"})
    res = _only(_calibration_results())
    assert res["status"] == sh.STALE, res
    assert "wnba_prop_player_threes +10.3pp/159" in res["detail"]


# ── a model the graded view cannot see is measured from settled bets ────────

@pytest.mark.parametrize("model_id,cal,wins,registered,promoted,is_live", [
    # a market rule with NO registry row, whose id matches the view's
    # wnba_prop_% filter -- the exact case the weekly fitter still reads as n=0
    ("wnba_prop_market", 0.70, 75, False, "2026-09-19", False),
    # an in-play model: the view drops is_live rows; no registry row either
    ("ncaaf_live_total", 0.70, 75, False, None, True),
    # a three-way market claiming under 50%: a 0.60 floor would hide it
    ("nhl_moneyline_regulation", 0.47, 45, True, None, False),
])
def test_a_model_absent_from_the_graded_view_is_measured_from_settled_bets(
        db, model_id, cal, wins, registered, promoted, is_live):
    if registered:
        _register(db, model_id, created="2026-09-20 00:00:00")
    if promoted:
        _promote(db, model_id, f"{promoted}T12:00:00+00:00")
    _settled_bets(db, model_id, 150, wins, cal, is_live=is_live)
    # Rows that are NOT evidence, every one a WIN so counting any of them
    # would move both the count and the gap:
    _bet(db, model_id, day="2026-10-05", result="WIN", cal=cal, signal="NONE")
    _bet(db, model_id, day="2026-10-05", result="WIN", cal=cal, signal="AVOID")
    _bet(db, model_id, day="2026-10-05", result="WIN", cal=cal, status="VOID")
    _bet(db, model_id, day="2026-10-05", result="WIN", cal=cal,
         status=config.DUPLICATE_STATUS)
    _bet(db, model_id, day="2026-10-05", result="WIN", cal=cal, odds=None)
    _bet(db, model_id, day="2026-10-05", result="PUSH", cal=cal)
    if registered or promoted:
        # before the current version / promoted map: a different regime
        _bet(db, model_id, day="2026-09-15", result="WIN", cal=cal)
    db.commit()

    res = _only(_calibration_results())
    gap = 100 * cal - 100 * wins / 150
    assert res["status"] == sh.STALE, res
    # It grades the DECISION number (cal), not the raw 0.80 -- which would
    # read 10-33pp larger.
    assert f"{model_id} +{gap:.1f}pp/150 bet-only" in res["detail"], res["detail"]
    assert "settled bets alone" in res["detail"], res["detail"]


def test_a_price_taken_at_another_book_counts_as_a_real_price(db):
    """decision_odds is the price the bet was decided at; dk_odds may be NULL
    when DraftKings did not list it (CLAUDE.md section 6)."""
    _promote(db, "nfl_prop_market", "2026-09-19T12:00:00+00:00")
    for i in range(150):
        _bet(db, "nfl_prop_market", day="2026-10-05",
             result="WIN" if i < 60 else "LOSS", cal=0.55, odds=None,
             decision_odds=-105)
    db.commit()
    res = _only(_calibration_results())
    assert "nfl_prop_market +15.0pp/150 bet-only" in res["detail"], res


# ── the 150 gate still holds, on both sides of the line ─────────────────────

def test_the_150_gate_holds_for_both_sources(db):
    """149 is not enough to accuse; 150 is enough to measure. Before the fix the
    settled-bet side could not be measured at any count."""
    _register(db, "mlb_prop_batter_walks")
    _graded(db, "mlb_prop_batter_walks", 149, 90)            # +9.6pp, thin
    _promote(db, "nfl_prop_market", "2026-09-19T12:00:00+00:00")
    _settled_bets(db, "nfl_prop_market", 149, 50, 0.70)      # +36pp, thin
    _settled_bets(db, "nhl_over_under", 150, 84, 0.56)       # +0.0pp, measured
    db.commit()

    res = _only(_calibration_results())
    assert res["status"] == sh.OK, res
    assert "1 model(s) measured" in res["detail"], res["detail"]
    assert "nhl_over_under bet-only" in res["detail"], res["detail"]
    assert "nfl_prop_market" not in res["detail"]
    assert "mlb_prop_batter_walks" not in res["detail"]


def test_only_paused_models_measurable_is_skipped_and_still_names_them(db, monkeypatch):
    """Nothing the check judges reached 150, so it has no verdict: SKIPPED, not
    OK and not STALE. The paused reading still rides along in the detail."""
    _register(db, "wnba_prop_player_threes")
    _graded(db, "wnba_prop_player_threes", 159, 95, last="2026-09-27")
    _settled_bets(db, "nhl_over_under", 149, 84, 0.56)
    db.commit()
    monkeypatch.setattr(config, "PAUSED_MODELS",
                        set(config.PAUSED_MODELS) | {"wnba_prop_player_threes"})
    res = _only(_calibration_results())
    assert res["status"] == sh.SKIPPED, res
    assert "150+" in res["detail"]
    assert "wnba_prop_player_threes +10.3pp/159" in res["detail"], res["detail"]
    assert "last graded 2026-09-27" in res["detail"], res["detail"]


# ── a failed query is the only result, and it is what gets stored ───────────

def test_a_failed_query_is_stored_as_an_error_not_overwritten_by_skipped(monkeypatch):
    """The persist upserts on (run_date, check_name). Before the fix a failed
    query added ERROR and then SKIPPED, and the SKIPPED is what was stored."""
    path, c = _make_db(with_view=False)          # the graded view is missing
    monkeypatch.setattr(sh, "get_connection", lambda: _Shim(path))
    try:
        results = _calibration_results()
        res = _only(results)
        assert res["status"] == sh.ERROR, res
        stored = c.execute(
            "SELECT status FROM system_health_checks "
            "WHERE check_name = 'model_calibration'").fetchall()
        assert stored == [(sh.ERROR,)], stored
    finally:
        c.close()


def test_a_failed_settled_bet_query_is_an_error_too(db, monkeypatch):
    """The settled-bet source covers 53 models. If it fails, the check must not
    quietly fall back to the graded view alone and hide them again."""
    def _boom(conn, model_ids):
        raise RuntimeError("relation picks is unreachable")
    monkeypatch.setattr(sh, "_calibration_bet_only_rows", _boom)
    res = _only(_calibration_results())
    assert res["status"] == sh.ERROR, res
    assert "settled-bet" in res["detail"], res


# ── which models go to which source ─────────────────────────────────────────

def _view_graded_models() -> set:
    """The models the graded view can actually grade: the explicit game-model
    branches plus the per-stat lateral mappings, read from every migration that
    defines the view (they must agree, or this test needs the live one)."""
    sets = []
    for path in glob.glob(str(REPO / "data" / "migrations" / "*.sql")):
        text = io.open(path, encoding="utf-8").read()
        at = text.find("MATERIALIZED VIEW public.mv_scored_pick_outcomes AS")
        if at < 0:
            continue
        block = text[at:]
        names = set(re.findall(r"WHEN p\.model_id = '(\w+)' THEN CASE", block))
        names |= set(re.findall(r"WHEN '((?:mlb|wnba)_prop_\w+)'\s+THEN ", block))
        sets.append(names)
    assert sets, "no migration defines mv_scored_pick_outcomes"
    assert all(s == sets[0] for s in sets), "the view definitions disagree"
    return sets[0]


def test_every_model_is_visible_to_exactly_one_source():
    """A registered model the graded view cannot grade must be read from
    settled bets -- otherwise it is invisible, which is the bug."""
    graded = _view_graded_models()
    assert "wnba_prop_market" not in graded      # matches the filter, no branch
    expected = sorted(m for m in config.ACTION_THRESHOLDS if m not in graded
                      or pc._is_live_lane(m))
    assert sh._calibration_bet_only_models() == expected
