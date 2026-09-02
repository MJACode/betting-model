"""The "good to" price: the model's gate, expressed as a number a reader can use.

Matt, 2026-08-30: "dont say 'Bet the number DraftKings is showing you, not this
one; if it has moved past your edge, skip it'. people wont know what the edge
is. use the model to give a range of odds the bet is good to ... For example,
live pick on X event at -110 on DK, good to -120 otherwise pass."

He is right that the old copy was useless: the edge is deliberately NOT
published (it is the model's IP), so it asked the reader to check a number they
cannot see. The bound is the same gate solved for price.

The property every test here defends: A PUBLISHED BOUND MUST ITSELF QUALIFY.
Rounding the friendly way by one cent of implied probability turns the number
into a lie, and it is a lie in the direction that costs money.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from tracking.discord_notifier import _decimal_to_american, price_bound


def _dec(american: float) -> float:
    return 1 + (american / 100.0 if american > 0
                else 100.0 / abs(american))


# ── the rounding ─────────────────────────────────────────────────────────────

def test_a_rounded_bound_still_clears_the_bound_it_came_from():
    """The one invariant. Swept across the whole realistic price range rather
    than spot-checked, because the two halves of the American scale round in
    OPPOSITE directions and a spot check can easily miss one."""
    d = 1.02
    while d < 5.0:
        a = _decimal_to_american(d)
        assert a != 0
        assert _dec(a) >= d - 1e-9, f"decimal {d}: {a} is below its own bound"
        d += 0.01


def test_the_two_halves_round_in_opposite_directions():
    # minus money: floor |A| (a bigger |A| would be a smaller decimal)
    assert _decimal_to_american(1.9412) == -106      # 106.25 -> 106, not 107
    # plus money: ceil A (a smaller A would likewise be under the bound)
    assert _decimal_to_american(2.057) == 106        # 105.7 -> 106, not 105


def test_even_money_is_plus_one_hundred():
    assert _decimal_to_american(2.0) == 100


# ── the bound ────────────────────────────────────────────────────────────────

def test_the_binding_gate_is_the_tightest_one():
    """Every gate is a lower bound on the decimal, so the largest wins.

    DERIVED from config rather than hard-coded. These assertions used to carry
    the literal answer for the EV floor of the day (-106 at 0.32), so moving the
    floor to 0.28 on 2026-08-30 "failed" a test that was only ever recording the
    old number. What must hold is the RULE: when the EV floor implies a tighter
    price than the edge floor, the EV floor is what gets published."""
    ev_floor = config.MODEL_MIN_EV["mlb_live_total_runs"]
    prob, edge_floor = 0.68, 0.14
    got = price_bound(prob, "mlb_live_total_runs", edge_floor, None, 150)

    from_ev = (1 + ev_floor) / prob          # p x dec - 1 >= floor
    from_edge = 1 / (prob - edge_floor)      # p - 1/dec >= floor
    assert from_ev > from_edge, "fixture no longer exercises an EV-bound case"
    # The published bound must clear the binding gate, and must not be looser.
    assert _dec(got) >= from_ev - 1e-9
    assert _dec(got) < from_ev + 0.02, got


def test_a_model_with_no_ev_floor_uses_its_edge_floor():
    """A model outside MODEL_MIN_EV is bounded by its edge floor alone.

    Picked dynamically: this test used to name ncaaf_live_total, which acquired
    an EV floor on 2026-08-30 and quietly stopped testing the thing it says."""
    model = next(m for m in ("mlb_moneyline", "nhl_moneyline", "ufc_moneyline")
                 if m not in config.MODEL_MIN_EV and m not in config.MODEL_MIN_ODDS)
    prob, edge_floor = 0.62, 0.08
    got = price_bound(prob, model, edge_floor, None, 200)
    assert _dec(got) >= 1.0 / (prob - edge_floor) - 1e-9
    assert _dec(got) < 1.0 / (prob - edge_floor) + 0.02, got


def test_a_price_floor_can_be_the_binding_gate():
    """MODEL_MIN_ODDS is a hard price floor and outranks a looser edge gate.

    Also pins the float case: -140 is decimal 1.714285714..., which comes back
    as 139.99999999999997. Without an epsilon this published -139 -- tighter
    than the model requires, i.e. suppressing bets that are actually fine."""
    got = price_bound(0.90, "mlb_prop_batter_rbi", 0.16, -140, -130)
    assert got == -140, got


def test_no_bound_when_the_posted_price_is_already_worse_than_it():
    """That would mean the pick never cleared its own gate. Publishing a range
    wider than the truth is worse than publishing none."""
    assert price_bound(0.68, "mlb_live_total_runs", 0.14, None, -200) is None


def test_no_bound_when_the_edge_floor_is_unreachable():
    """prob 0.10 with a 0.14 edge floor has no price that satisfies it -- the
    subtraction goes negative and there is no honest number to print."""
    assert price_bound(0.10, "ncaaf_live_total", 0.14, None, 500) is None


def test_no_bound_from_junk_rather_than_a_guess():
    for bad in (None, "", "abc", 0.0, 1.0, 1.5, -0.2):
        assert price_bound(bad, "ncaaf_live_total", 0.08, None, -110) is None
    # no gates at all -> nothing to solve for
    assert price_bound(0.70, "some_model_with_no_gates", None, None, -110) is None


# ── what actually reaches the channel ────────────────────────────────────────

def test_the_field_shows_the_bound_and_never_the_edge():
    from tracking.discord_notifier import _signal_field
    field = _signal_field({
        "label": "Over 8.5", "sport": "MLB", "home": "OAK", "away": "BAL",
        "dk_odds": -110, "kelly": 0.02, "model_id": "mlb_live_total_runs",
        "good_to": -106, "live": True,
    })
    assert "good to" in field["value"] and "-106" in field["value"]
    for leaked in ("edge", "0.14", "prob"):
        assert leaked not in field["value"].lower(), f"{leaked} must not be published"


def test_a_field_without_a_bound_renders_without_the_clause():
    """Pre-game producers do not compute one; their fields must be unchanged."""
    from tracking.discord_notifier import _signal_field
    field = _signal_field({
        "label": "NYM ML F5", "sport": "MLB", "home": "NYM", "away": "HOU",
        "dk_odds": -135, "kelly": 0.02, "model_id": "mlb_f5_moneyline",
    })
    assert "good to" not in field["value"]


def test_the_live_note_no_longer_asks_the_reader_about_an_edge():
    from tracking.discord_notifier import LIVE_STALENESS_NOTE
    assert "edge" not in LIVE_STALENESS_NOTE.lower()
    assert "good to" in LIVE_STALENESS_NOTE
