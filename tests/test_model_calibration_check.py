"""The calibration check must grade the number that DECIDED the bet.

mike, 2026-09-08: "fix the model calibration issue". The check was reporting
four models 8-14pp overconfident, and three of those four were artefacts of the
check rather than of the models.

Two faults, which compounded into a verdict that could never come good:

  * It averaged `o.model_probability`, the RAW number — while
    `DECIDE_ON_CALIBRATED_PROB` has been on since Phase 2 (2026-08-31), so the
    BET/AVOID call runs on the CALIBRATED probability. The raw column stays raw
    ON PURPOSE (docs/probability_calibration.md) so old sweeps stay readable.
    The check was grading a number the decision path no longer uses, and no
    amount of calibration work could ever have moved it.
  * Its window opened at the model VERSION's date, which predates every
    promoted map. Measured 2026-09-08: all seven promoted maps landed on 09-07
    and `graded_since_promotion` was ZERO for every model — 100% of the sample
    was written under the old regime.

Live consequence: two of the four accused were WNBA models whose last graded
pick was 2026-08-30. The season is over until May, so that population is frozen
— the check would have gone CRIT every morning for eight months about picks
nobody can change.

After the fix, against production: three models have enough in-regime evidence,
and exactly one is genuinely overconfident (`mlb_prop_pitcher_er`, +10.0pp over
397 picks) — the one model whose map mike deliberately did NOT promote because
it "helps but does not close".
"""
import io
import re

import tracking.system_health as sh


def _calibration_sql() -> str:
    """The check's ACTUAL query, lifted from the module.

    Read from source rather than restated here: a copy would keep passing while
    the query it guards was changed underneath it, which is the §7 blind spot
    that has already bitten this file twice today.
    """
    text = io.open(sh.__file__, encoding="utf-8").read()
    body = text[text.index("# ── Model calibration on the LIVE record"):]
    sql = body[body.index('conn.execute("""') + len('conn.execute("""'):]
    return sql[:sql.index('""")')]


def test_it_grades_the_calibrated_probability_not_the_raw_one():
    """COALESCE(model_probability_cal, model_probability) IS the decision
    number: the scorer stamps that column from the PROMOTED map, and it equals
    the raw probability when there is no promoted map."""
    sql = _calibration_sql()
    assert "COALESCE(p.model_probability_cal, o.model_probability)" in sql, (
        "the check must average the probability the bet was decided on"
    )
    # and the raw column must not be averaged on its own any more
    assert not re.search(r"AVG\(\s*o\.model_probability\s*\)", sql), (
        "AVG(o.model_probability) grades a number the decision path stopped "
        "using when DECIDE_ON_CALIBRATED_PROB shipped"
    )


def test_the_probability_floor_applies_to_the_decision_number_too():
    """Selecting "picks at the probabilities actually bet" on the raw column
    would pick a different population than the one that was bet."""
    sql = _calibration_sql()
    assert "COALESCE(p.model_probability_cal, o.model_probability) >= 0.60" in sql


def test_the_window_opens_at_the_later_of_version_and_promotion():
    """A pick from the previous regime says nothing about whether the current
    one is honest. Promoting a map is a regime change exactly like a retrain."""
    sql = _calibration_sql()
    assert "model_calibration" in sql and "promoted_at" in sql, (
        "the window must know when the map was promoted"
    )
    assert "c.promoted IS TRUE" in sql, (
        "only a PROMOTED map changes the decision, so only it moves the window"
    )
    assert "o.game_date > g.since" in sql


def test_it_joins_picks_to_reach_the_calibrated_column():
    """mv_scored_pick_outcomes does not carry model_probability_cal — verified
    against production, the column does not exist on the view."""
    sql = _calibration_sql()
    assert "JOIN picks p ON p.pick_id = o.pick_id" in sql


def test_a_thin_model_is_still_excluded_rather_than_accused():
    sql = _calibration_sql()
    assert "HAVING COUNT(*) >= 150" in sql


def test_the_skipped_state_does_not_claim_calibration():
    """SKIPPED here means "not enough evidence yet", and it un-skips on its own
    as picks accrue. It must never read as "calibrated"."""
    text = io.open(sh.__file__, encoding="utf-8").read()
    block = text[text.index('r.add("model_calibration", SKIPPED'):]
    block = block[:block.index(")\n")]
    assert "150+" in block
    assert "ok" not in block.lower().replace("promoted", "")


def test_the_check_has_a_skip_budget_that_survives_a_regime_change():
    """A retrain or a newly promoted map resets the sample to zero, and 150
    graded picks take weeks. The default 14-day budget would call that a stuck
    gate and go STALE for no reason."""
    budget = sh.SKIP_BUDGET_DAYS.get("model_calibration")
    assert budget is not None, "a regime change would trip the default budget"
    assert budget >= 30, f"{budget}d is shorter than a sample takes to rebuild"


def test_the_thresholds_are_still_the_documented_ones():
    """WARN at 5pp is the go-live criterion; CRIT at 8pp. Changing these is a
    model-policy decision, not a refactor."""
    text = io.open(sh.__file__, encoding="utf-8").read()
    block = text[text.index("gaps = sorted("):]
    block = block[:block.index('r.add("model_calibration", OK')]
    assert "g[0] >= 8.0" in block
    assert "5.0 <= g[0] < 8.0" in block
