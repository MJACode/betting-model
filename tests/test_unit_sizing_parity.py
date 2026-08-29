"""
Cross-language parity for unit sizing.

The stake rule lives twice: tracking/discord_notifier.stake_for() drives the
Discord channels and the recap, mobile/src/lib/thresholds.stakeFor() drives the
app. Publishing in units is only meaningful if the two agree — a "2u" in the
channel and a "2u" on the card have to be the same bet.

tests/fixtures/unit_sizing_parity.json is the shared contract. This test
regenerates it from the Python side and asserts it matches; the TypeScript side
is checked against the same rows by mobile/scripts/verify_units_parity.ts. If
either implementation drifts, one of the two fails.

Regenerate after a deliberate rule change:
    python -m tests.test_unit_sizing_parity --write
"""
from __future__ import annotations

import json
from pathlib import Path

import tracking.discord_notifier as dn

FIXTURE = Path(__file__).parent / "fixtures" / "unit_sizing_parity.json"

# Deliberately spans every branch: below/at/above the Kelly cap, plus-money,
# the median live price, the price where the risk cap starts to bind, the worst
# price ever observed, and the unpriced (prob-only) case.
KELLYS = (0.001, 0.0167, 0.022, 0.025, 0.0328, 0.039, 0.05, 0.2)
ODDS = (-110, -135, -147, -200, -325, -1000, 100, 150, 600, None)


def _rows() -> list[dict]:
    out = []
    for k in KELLYS:
        for o in ODDS:
            s = dn.stake_for(k, o)
            out.append({
                "kelly": k, "odds": o,
                "conviction": s.conviction,
                "risk": round(s.risk, 9),
                "win": round(s.win, 9),
                "capped": s.capped,
                "priced": s.priced,
                "fmt": dn.fmt_stake(s),
            })
    return out


def _doc() -> dict:
    return {
        "_comment": (
            "GENERATED — do not hand-edit. Regenerate with "
            "`python -m tests.test_unit_sizing_parity --write`. Checked by this "
            "test (Python side) and mobile/scripts/verify_units_parity.ts "
            "(TypeScript side), so a drift in either fails."
        ),
        "cases": _rows(),
    }


def test_python_matches_the_parity_fixture():
    assert FIXTURE.exists(), (
        f"{FIXTURE} is missing — regenerate with "
        "`python -m tests.test_unit_sizing_parity --write`")
    stored = json.loads(FIXTURE.read_text())["cases"]
    assert _rows() == stored, (
        "Python unit sizing no longer matches the committed parity fixture. If "
        "the rule changed on purpose, regenerate the fixture AND re-run "
        "mobile/scripts/verify_units_parity.ts so the app stays in step.")


def test_the_fixture_actually_covers_the_interesting_branches():
    """A parity fixture that only exercises the happy path proves nothing."""
    cases = _rows()
    assert any(c["capped"] for c in cases), "no capped case"
    assert any(not c["priced"] for c in cases), "no unpriced case"
    # Conviction is FLAT while the tier scale is retired, so "reaches max
    # conviction" is no longer a branch to cover. What still matters is that
    # the fixture spans the price axis, which is what stake_for actually
    # varies on now.
    assert all(c["conviction"] == 1.0 for c in cases), "conviction is flat"
    assert any(c["risk"] > c["win"] for c in cases), "no favourite case"
    assert any(c["risk"] < c["win"] for c in cases), "no underdog case"
    assert any(c["conviction"] == 1.0 for c in cases), "never reaches min conviction"
    assert any(c["risk"] < c["conviction"] for c in cases), "no plus-money case"
    assert any(c["risk"] > c["conviction"] for c in cases), "no favourite case"


if __name__ == "__main__":
    import sys
    if "--write" in sys.argv:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(_doc(), indent=2) + "\n")
        print(f"wrote {FIXTURE} ({len(_rows())} cases)")
    else:
        test_python_matches_the_parity_fixture()
        test_the_fixture_actually_covers_the_interesting_branches()
        print("parity fixture OK")
