"""
The live lane decides on the calibrated probability, and the fit can SEE it.

WHY THIS EXISTS
---------------
Two halves of the same 2026-09-07 finding, at opposite ends of the same loop.

1. `DECIDE_ON_CALIBRATED_PROB` reached `classify_edge` on 2026-08-31 and
   `_make_prop_pick` on 2026-09-07. `classify_live_signal` was the third and
   last place it had to reach. It is a NO-OP as it lands — no live model has a
   promoted map — and that is the point: the props spent six days making bets on
   raw numbers while the map moved a display column, and this closes the same
   door before it opens.

2. The fit could not see a live model AT ALL. `fetch_graded` read
   `mv_scored_pick_outcomes`, which excludes `is_live` by construction, so every
   live lane reported "only 0 graded picks (need 150) — identity map, unfitted"
   on every weekly run. `mlb_live_total_runs` has 126 graded BETs and was
   reported as 0. That reads as "not enough data yet" and means "invisible" —
   the empty-board-versus-broken-pipeline failure, in the one place that decides
   whether a model's probabilities get corrected.

THE COHERENCE PROPERTY is the one worth naming. `classify_live_signal` applies a
probability floor, an edge floor AND an EV floor. All three must read the same
quantity: a prob floor on the calibrated number beside an EV floor on the raw
one is two cuts aimed at different things, and nobody would ever notice.
"""

from __future__ import annotations

import pytest

import config
from models import live_scorer as ls
from models import probability_calibration as pc

MODEL = "mlb_live_total_runs"
# A -250 price. Chosen so the whole grid sits under LIVE_MAX_EDGE_CAP (0.20):
# at -110 a 0.74 claim is already a +21.6pp edge and the cap voids it before
# any threshold is consulted, which would test the cap and nothing else.
IMPLIED = 0.714
ODDS = -250.0


@pytest.fixture(autouse=True)
def _cut(monkeypatch):
    monkeypatch.setitem(config.MODEL_EDGE_THRESHOLDS, MODEL, 0.14)
    monkeypatch.setitem(config.MODEL_PROB_THRESHOLDS, MODEL, 0.70)
    monkeypatch.setattr(ls, "MODEL_EDGE_THRESHOLDS", config.MODEL_EDGE_THRESHOLDS)
    monkeypatch.setattr(ls, "MODEL_PROB_THRESHOLDS", config.MODEL_PROB_THRESHOLDS)
    monkeypatch.setattr(ls, "PAUSED_MODELS", set())
    monkeypatch.setattr(ls, "MODEL_MIN_EV", {})


def _signal(monkeypatch, *, raw, calibrated_to, decide=True, odds=ODDS):
    monkeypatch.setattr(ls, "DECIDE_ON_CALIBRATED_PROB", decide)
    monkeypatch.setattr(ls, "_calibrated",
                        lambda mid, p: calibrated_to if mid == MODEL else p)
    return ls.classify_live_signal(MODEL, raw, raw - IMPLIED, odds)


# ── the decision ─────────────────────────────────────────────────────────────

def test_a_hot_live_model_no_longer_fires_the_marginal_bet(monkeypatch):
    """Claims 0.88 (+16.6pp edge, clears 0.70/0.14); worth 0.76 (+4.6pp), which
    does not. The map measured on this model maps a claimed 0.74 to 0.598, so
    this is the real shape rather than an invented one."""
    assert _signal(monkeypatch, raw=0.88, calibrated_to=0.76) is None


def test_the_same_signal_WOULD_have_fired_on_the_raw_number(monkeypatch):
    """The counterpart that makes the test above mean something. Watched to fail
    against the pre-2026-09-07 body."""
    assert _signal(monkeypatch, raw=0.88, calibrated_to=0.76, decide=False) == "BET"


def test_a_big_enough_claim_still_fires_after_calibration(monkeypatch):
    assert _signal(monkeypatch, raw=0.91, calibrated_to=0.86) == "BET"


def test_an_unmapped_live_model_is_completely_unaffected(monkeypatch):
    """The property that stops this silently re-cutting every live lane at
    once — and the reason this change is a no-op the day it ships."""
    monkeypatch.setattr(ls, "DECIDE_ON_CALIBRATED_PROB", True)
    monkeypatch.setattr(ls, "_calibrated", lambda mid, p: p)
    assert ls.classify_live_signal(MODEL, 0.88, 0.88 - IMPLIED, ODDS) == "BET"


def test_avoid_is_judged_on_the_calibrated_edge_too(monkeypatch):
    """A cold claim calibrates UP, out of the AVOID band."""
    assert _signal(monkeypatch, raw=0.55, calibrated_to=0.60) is None
    assert _signal(monkeypatch, raw=0.55, calibrated_to=0.60, decide=False) == "AVOID"


def test_the_EV_FLOOR_reads_the_same_number_the_prob_floor_does(monkeypatch):
    """THE COHERENCE PROPERTY. A prob floor on the calibrated number and an EV
    floor on the raw one are two cuts pointing at different quantities."""
    # At -250 the decimal payout is 1.4, so EV = p * 1.4 - 1: raw 0.91 is
    # +0.274 and its calibrated 0.86 is +0.204. Both clear a 0.20 floor.
    monkeypatch.setattr(ls, "MODEL_MIN_EV", {MODEL: 0.20})
    assert _signal(monkeypatch, raw=0.91, calibrated_to=0.86) == "BET"
    # Raise the floor between the two and the answer must follow the CALIBRATED
    # number, not the raw one.
    monkeypatch.setattr(ls, "MODEL_MIN_EV", {MODEL: 0.25})
    assert _signal(monkeypatch, raw=0.91, calibrated_to=0.86) == "NONE"
    assert _signal(monkeypatch, raw=0.91, calibrated_to=0.86,
                   decide=False) == "BET"


def test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(monkeypatch):
    monkeypatch.setattr(ls, "DECIDE_ON_CALIBRATED_PROB", True)
    monkeypatch.setattr(ls, "_calibrated", lambda mid, p: None)
    assert ls.classify_live_signal(MODEL, 0.88, 0.88 - IMPLIED, ODDS) == "BET"


# ── the fit can see a live lane at all ───────────────────────────────────────

class RecordingConn:
    def __init__(self, rows=()):
        self.rows = rows
        self.sql = []

    def execute(self, sql, params=None):
        self.sql.append(" ".join(sql.split()))
        return self

    def fetchall(self):
        return self.rows


def test_a_live_model_is_read_out_of_picks_not_the_matview():
    """THE REGRESSION. The matview excludes is_live, so this returned 0 rows for
    every live lane, forever, and said "need 150"."""
    conn = RecordingConn([(0.74, "WIN"), (0.71, "LOSS")])
    pairs = pc.fetch_graded(conn, "mlb_live_total_runs", "2026-06-14")
    assert pairs == [(0.74, 1), (0.71, 0)]
    assert "FROM picks" in conn.sql[0]
    assert "mv_scored_pick_outcomes" not in conn.sql[0]


def test_a_live_read_bounds_on_a_real_price():
    """CLAUDE.md 6: an unpriced row is not evidence about a bet."""
    conn = RecordingConn()
    pc.fetch_graded(conn, "mlb_live_total_runs", "2026-06-14")
    assert "dk_odds IS NOT NULL" in conn.sql[0]


def test_a_live_read_does_not_apply_the_dead_zone_windows():
    """CLEAN_WINDOWS marks where the NONE rows were deleted. A live lane never
    writes NONE, so its population is that shape in every window and excluding
    the gap corrects nothing while costing real bets."""
    conn = RecordingConn()
    pc.fetch_graded(conn, "mlb_live_total_runs", "2026-06-14")
    assert "2026-06-25" not in conn.sql[0]


def test_a_pre_game_model_still_reads_the_graded_matview():
    conn = RecordingConn()
    pc.fetch_graded(conn, "mlb_prop_pitcher_k", "2026-09-03")
    assert "mv_scored_pick_outcomes" in conn.sql[0]
    assert "2026-06-25" in conn.sql[0]


@pytest.mark.parametrize("model_id, live", [
    ("mlb_live_total_runs", True),
    ("ncaaf_live_total", True),
    # Written by nfl/live_model/pick_writer and absent from config.LIVE_MODELS —
    # the case a registry-only test would miss.
    ("nfl_live_prop", True),
    ("mlb_prop_pitcher_k", False),
    ("mlb_moneyline", False),
])
def test_every_live_lane_is_recognised_including_the_unregistered_one(model_id, live):
    assert pc._is_live_lane(model_id) is live
