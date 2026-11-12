"""Same-game parlay price estimate on the Betslip.

Matt, 2026-11-06: a 4-leg slip in two NBA games showed +5993 at DraftKings and
+6040 at FanDuel. FanDuel's own slip priced it +4254, as two same-game parlays.
The app multiplied every leg as if independent. Books price legs from one game
together, below the legs multiplied out, and no feed we buy publishes that
price, so the app now ESTIMATES it (mobile/src/lib/sgpPricing.ts), labels it
"est.", and lets a member enter the book's real price, which is stored and
refits each book's cut (data/migrations/add_sgp_price_observations_2026_11_06.sql).

The behavioural checks live in mobile/scripts/verify_sgp_pricing.ts. This file
pins the wiring so a surface that stops applying the estimate fails even when
node modules are not installed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
SRC = MOBILE / "src"

from tests._node import tsx_cmd  # noqa: E402


def _read(rel: str) -> str:
    return (SRC / rel).read_text(encoding="utf-8")


def test_every_pricing_surface_applies_the_same_game_estimate():
    parlay = _read("lib/parlay.ts")
    corr = _read("lib/parlayCorrelation.ts")
    # headline, bar, tiles, saved slip: one helper, four call sites.
    assert parlay.count("applySgpHaircut(") >= 2, "computeParlayMetrics and priceBooksForParlay"
    assert "applySgpHaircut(" in corr, "computeCorrelatedMetrics (the headline)"
    assert "sgpEstimated: m.sgpGroups > 0" in parlay, "betslipSummary (the bar)"


def test_bar_and_screen_read_the_same_fits():
    bar = _read("components/BetslipBar.tsx")
    screen = _read("screens/ParlayScreen.tsx")
    assert "betslipSummary(legs, count, sgpFits, typedDk)" in bar
    assert "useEnteredSgpPrices(" in bar and "useEnteredSgpPrices(" in screen
    assert "useSgpHaircuts()" in bar and "useSgpHaircuts()" in screen
    # BetslipBar is outside the NavigationContainer (.claude/rules/frontend.md).
    hook = _read("hooks/useSgpHaircuts.ts")
    code = "\n".join(l for l in hook.splitlines() if not l.strip().startswith(("*", "//")))
    assert "useFocusEffect" not in code


def test_an_estimate_is_labelled_as_one():
    screen = _read("screens/ParlayScreen.tsx")
    tiles = _read("components/BetslipBooksRow.tsx")
    assert "est." in screen and "metrics.sgpGroups > 0" in screen
    assert "· est." in tiles


def test_line_shop_is_withheld_on_a_same_game_slip():
    parlay = _read("lib/parlay.ts")
    body = parlay.split("export function lineShopParlay(")[1].split("\n}\n")[0]
    assert "if (sameGameGroupCount(legs) > 0) return null;" in body


def test_entered_prices_are_stored_through_the_insert_only_rpc():
    q = _read("lib/queries.ts")
    assert "supabase.rpc('log_sgp_price'" in q
    assert "supabase.rpc('sgp_haircuts')" in q
    from data.anon_readable import RPC_ANON_CALLABLE  # type: ignore

    assert "log_sgp_price" in RPC_ANON_CALLABLE and "sgp_haircuts" in RPC_ANON_CALLABLE
    mig = (ROOT / "data" / "migrations" / "add_sgp_price_observations_2026_11_06.sql").read_text(encoding="utf-8")
    assert "REVOKE ALL ON TABLE sgp_price_observations FROM anon, authenticated;" in mig
    assert "SECURITY DEFINER" in mig


@pytest.mark.skipif(tsx_cmd(MOBILE) is None, reason="mobile node modules not installed")
def test_the_behavioural_checks_pass():
    proc = subprocess.run(
        [*tsx_cmd(MOBILE), "scripts/verify_sgp_pricing.ts"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_nfl_correlations_bundled_in_the_app_match_the_stored_rows():
    """mobile/src/lib/propCorrelation.ts and the parlay_correlations rows in
    sgp_per_leg_cut_2026_11_12.sql are one table in two places (Matt,
    2026-11-12: the app priced NFL same-game legs as unrelated). They must not
    drift."""
    import re

    ts = _read("lib/propCorrelation.ts")
    app = {
        k: float(v)
        for k, v in re.findall(r"'(NFL\|[a-z_]+\|[a-z_]+\|[a-z_]+)':\s*(-?\d+\.\d+)", ts)
    }
    mig = (ROOT / "data" / "migrations" / "sgp_per_leg_cut_2026_11_12.sql").read_text(encoding="utf-8")
    db = {
        f"NFL|{a}|{b}|{rel}": float(rho)
        for a, b, rel, rho in re.findall(
            r"\('NFL','([a-z_]+)','([a-z_]+)','([a-z_]+)',(-?\d+\.\d+),'empirical',\d+\)", mig
        )
    }
    assert len(app) >= 100 and app == db
    # The pair behind the 2026-11-12 slip: a receiver's catches and his own TD.
    assert app["NFL|player_anytime_td|player_receptions|same_player"] > 0.25
    # Keys are ordered the way propPairKey orders them.
    for k in app:
        _, a, b, _ = k.split("|")
        assert a <= b, k


def test_the_same_game_estimate_is_per_extra_leg_after_the_correlation_lift():
    pricing = _read("lib/sgpPricing.ts")
    assert "const fair = multipliedDecimal / priceLift(shape.lift);" in pricing
    assert "return 1 + (fair - 1) * Math.pow(1 - haircutFor(book, fits), shape.extraLegs);" in pricing
    # A lift below 1 never raises the price above the legs multiplied out.
    assert "return lift > 1 && Number.isFinite(lift) ? lift : 1;" in pricing
    mig = (ROOT / "data" / "migrations" / "sgp_per_leg_cut_2026_11_12.sql").read_text(encoding="utf-8")
    assert "greatest(o.corr_lift, 1)" in mig, "the server fit uses the price's own formula"
    corr = _read("lib/parlayCorrelation.ts")
    # Every surface prices with the bundled table only, so they agree.
    assert "correlatedJointProb(priced, PARLAY_CORRELATION_PRIORS, undefined, SGP_LIFT_DRAWS)" in corr
    parlay = _read("lib/parlay.ts")
    assert parlay.count("sgpShapeFor(legs)") >= 2
