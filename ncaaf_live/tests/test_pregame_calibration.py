"""Stage 3 of the live win-probability model: the pregame-status correction.

mike, 2026-09-12: *"if Oklahoma State is a 24 point dog, then they are up by
only a TD in the second quarter and you say bet them live at even money, that
is just retarded. Give me an actual statistical model."*

Measured on 27,088 graded 2025 states, the two-stage probability under-rates
favourites and over-rates underdogs while being well calibrated by current
lead. These pin the correction that fixes it, and the three ways it can be
silently wrong: the sign of `dog_points`, the direction of the adjustment, and
a missing artifact turning into a zero rather than into "no correction".
"""
from __future__ import annotations

import json
import math

import pytest

from ncaaf_live import serve
from ncaaf_live.serve import correct_for_pregame, pregame_dog_points


@pytest.fixture(autouse=True)
def _real_artifact():
    """Each test starts from the shipped artifact, not a neighbour's monkeypatch."""
    serve._PREGAME_CAL = None
    yield
    serve._PREGAME_CAL = None


# ── the sign convention, where an inversion would hide ───────────────────────

def test_home_dog_points_is_the_spread_itself():
    assert pregame_dog_points("home", 24.5) == 24.5


def test_away_dog_points_is_the_negation():
    """Home +24.5 means the AWAY team is LAYING 24.5, not getting it."""
    assert pregame_dog_points("away", 24.5) == -24.5


def test_no_spread_is_none_not_zero():
    """Zero would read as a pick'em and apply no correction while looking
    applied; None is the honest answer and leaves p untouched."""
    assert pregame_dog_points("home", None) is None
    assert correct_for_pregame(0.637, None) == 0.637


# ── the direction, which is the whole point ──────────────────────────────────

def test_a_big_dog_is_marked_down_hard():
    """The case that prompted this: 0.637 on a 24.5-point pregame dog."""
    assert correct_for_pregame(0.637, 24.5) == pytest.approx(0.302, abs=0.01)


def test_a_favourite_is_marked_up():
    """The same correction in the other direction -- a cap could never do this."""
    assert correct_for_pregame(0.781, -10.0) > 0.781


def test_a_pick_em_is_barely_touched():
    assert correct_for_pregame(0.653, 0.0) == pytest.approx(0.653, abs=0.02)


def test_the_correction_is_monotone_in_dog_points():
    """More points received can only lower the probability."""
    ps = [correct_for_pregame(0.60, d) for d in (-21, -14, -7, 0, 7, 14, 21)]
    assert ps == sorted(ps, reverse=True)


def test_it_stays_a_probability():
    for p in (0.001, 0.5, 0.999):
        for d in (-60.0, 0.0, 60.0):
            assert 0.0 < correct_for_pregame(p, d) < 1.0


# ── failure must be "no correction", never "wrong correction" ────────────────

def test_a_missing_artifact_leaves_the_probability_alone(monkeypatch, tmp_path):
    monkeypatch.setattr(serve, "ARTIFACT_DIR", tmp_path)
    serve._PREGAME_CAL = None
    assert correct_for_pregame(0.637, 24.5) == 0.637


def test_a_corrupt_artifact_leaves_the_probability_alone(monkeypatch, tmp_path):
    (tmp_path / "win_prob_pregame_calibration.json").write_text("{not json",
                                                                encoding="utf-8")
    monkeypatch.setattr(serve, "ARTIFACT_DIR", tmp_path)
    serve._PREGAME_CAL = None
    assert correct_for_pregame(0.637, 24.5) == 0.637


# ── the artifact itself ──────────────────────────────────────────────────────

def test_the_shipped_artifact_is_loadable_and_signed_correctly():
    path = serve.ARTIFACT_DIR / "win_prob_pregame_calibration.json"
    art = json.loads(path.read_text(encoding="utf-8"))
    assert art["model_id"] == "ncaaf_live_win_prob"
    # c < 0 is the measured defect's direction: more points received -> lower
    # probability. A positive c would invert the whole correction.
    assert art["c"] < 0
    assert abs(art["c"]) > 2 * art["c_stderr"], "coefficient must exclude zero"
    assert art["validation"]["brier"]["this"] < art["validation"]["brier"]["raw"]
    assert art["validation"]["brier"]["this"] < art["validation"]["brier"]["platt_only"], \
        "the pregame term must beat a recalibration that cannot see the spread"


# ── the wiring ───────────────────────────────────────────────────────────────

def test_the_artifact_is_TRACKED_by_git():
    """ncaaf_live/data/ is in .gitignore, so this file needs `git add -f` the
    way its sibling artifacts did. Miss it and the worker has no calibration:
    _load_pregame_calibration returns None, the lane prices UNCORRECTED, and
    the cut it prices against was swept on the corrected scale -- the worst
    combination, and silent. This is the .pkl-not-committed trap
    (.claude/rules/operations.md) in a different file extension."""
    import subprocess
    from pathlib import Path
    root = Path(serve.__file__).resolve().parents[1]
    rel = "ncaaf_live/data/artifacts/win_prob_pregame_calibration.json"
    out = subprocess.run(["git", "ls-files", "--error-unmatch", rel],
                         cwd=root, capture_output=True, text=True)
    assert out.returncode == 0, (
        f"{rel} is not tracked by git -- the worker will price UNCORRECTED. "
        f"Add it with `git add -f {rel}`.")


def test_candidates_applies_the_correction():
    """Source tripwire. The helper existing is not the same as it running, and
    a correction that is computed and dropped is the worst of both."""
    from pathlib import Path
    src = Path(serve.__file__).read_text(encoding="utf-8")
    body = src.split("def candidates(")[1].split("\n    def ")[0]
    assert "correct_for_pregame(" in body
    assert "pregame_dog_points(" in body


def test_the_stored_probability_is_the_corrected_one():
    """`model_probability` must be what the model believes -- storing the raw
    number would misreport every surface that reads it, and the app filters on
    exactly this column."""
    from pathlib import Path
    src = Path(serve.__file__).read_text(encoding="utf-8")
    body = src.split("def candidates(")[1].split("\n    def ")[0]
    assert '"model_probability": p,' in body
    assert '"model_probability_raw": p_raw,' in body


def test_the_superseded_cap_is_gone():
    """It refused to bet in the region; the correction prices the region. Both
    at once would double-count the same defect."""
    from pathlib import Path
    src = Path(serve.__file__).read_text(encoding="utf-8")
    assert "ML_MAX_PREGAME_DOG_POINTS" not in src
    assert "_unless_big_dog" not in src
