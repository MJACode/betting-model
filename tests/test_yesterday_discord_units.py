"""Yesterday's per-day units are Discord's posted stake.

The fixture mixes a priced win, a capped-risk win, a capped-risk loss, an
unpriced win, an unpriced loss, a push, a void, and an unpublished win.
``_tally`` adds ``unit_profit`` / ``unit_risked`` — the columns
``_SETTLED_SQL`` selects — and the app's ``computeDailyResults`` has to
land on the same wins, losses, units and risked. The printed units are
Discord's ``{units:+.2f}u`` (the app's U+2212 stands in for the ASCII
minus). A push-only total is the one exception: the app prints ``0.00u``.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from tests._node import NODE, node_strips_types
from tracking.discord_notifier import _tally
from tracking.published_units import unit_profit, unit_risked

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "yesterday_discord_units.json"
MOBILE = ROOT / "mobile"
LIB = MOBILE / "src" / "lib"

needs_node = pytest.mark.skipif(
    not node_strips_types(),
    reason="node >= 22.6 not available",
)

LIBS = (
    "dailyResults.ts",
    "thresholds.ts",
    "thresholds.generated.ts",
    "decisionPrice.ts",
    "discordPublish.ts",
    "format.ts",
    "recordStart.ts",
)


def _rewrite(text: str) -> str:
    text = re.sub(r"from '(?:\.\./)+src/lib/(\w+)';", r"from './\1.ts';", text)
    text = re.sub(r"from '(?:\.\./)+src/hooks/(\w+)';", r"from './\1.ts';", text)
    text = re.sub(r"from '@/lib/(\w+)';", r"from './\1.ts';", text)
    text = re.sub(r"from '@/hooks/(\w+)';", r"from './\1.ts';", text)

    def _rel(match: re.Match[str]) -> str:
        name = match.group(1)
        if name.endswith(".ts"):
            return match.group(0)
        return f"from './{name}.ts';"

    # Node ESM needs the extension. Metro does not, so the sources omit it.
    text = re.sub(r"from '\./([\w.]+)';", _rel, text)
    text = re.sub(r"^import type .*;\n", "", text, flags=re.M)
    return text


def _bucket(rows: list[tuple]) -> dict:
    t = _tally(rows)
    return {
        "wins": t["w"],
        "losses": t["l"],
        "pushes": t["p"],
        "units": t["units"],
        "risked": t["risked"],
    }


def _line(units: float, risked: float) -> dict:
    text = f"{units:+.2f}u"
    roi = None if risked <= 0 else f"{units / risked * 100:+.1f}%"
    return {"units": text, "roi": roi}


def _expected(fixture: dict) -> dict:
    countable = [p for p in fixture["picks"] if p["counts"]]
    def row(p):
        price = p["price"]
        return (
            p["sport"], p["model_id"], p["result"], None, price, None, False,
            unit_profit(price, p["result"]),
            unit_risked(price, p["result"]),
        )
    rows = [row(p) for p in countable]
    sports: dict[str, dict] = {}
    for p in countable:
        sport = sports.setdefault(p["sport"], {"rows": [], "models": {}})
        sport["rows"].append(row(p))
        sport["models"].setdefault(p["model_id"], []).append(row(p))
    sport_out = {}
    for sport, group in sports.items():
        bucket = _bucket(group["rows"])
        bucket["models"] = {
            model_id: _bucket(model_rows)
            for model_id, model_rows in group["models"].items()
        }
        sport_out[sport] = bucket
    overall = _bucket(rows)
    lines = [{"scope": "overall", **_line(overall["units"], overall["risked"])}]
    for sport, bucket in sport_out.items():
        lines.append({"scope": sport, **_line(bucket["units"], bucket["risked"])})
    return {"overall": overall, "sports": sport_out, "lines": lines}


def test_the_day_screen_reads_the_posted_stake_and_not_the_flat_book():
    daily = (LIB / "dailyResults.ts").read_text(encoding="utf-8")
    modal = (MOBILE / "src" / "components" / "DailyResultsModal.tsx").read_text(encoding="utf-8")
    hero = (LIB / "recordHero.ts").read_text(encoding="utf-8")
    assert "postedPickUnits" in daily
    assert "flatPnl" not in daily
    assert "postedPickUnits(pick)" in modal
    assert "dayUnitsText" in modal
    assert "dayRoiText" in modal
    assert "formatSigned(units, 2, 'u')" in daily
    assert "extends CustomModelStats" not in daily
    assert "profitFlat:" not in daily
    assert "stakedFlat:" not in daily
    assert "flat-bet ROI" not in modal
    assert "profitFlat / 100" not in modal
    assert "not in the money" not in modal
    assert "unpriced" not in modal
    assert " · no price" in modal
    assert "unitsSpeech(dayUnitsText(profit))" in modal
    assert "dayWinRateText" in modal
    assert "Return on bets unavailable" in modal
    copy = " ".join(modal.split())
    assert "Settled picks that Discord posted." in copy
    assert "Each pick risks the amount needed to win 1 unit." in copy
    assert "1.1 units to win 1." in copy
    assert "The Models tab uses a flat $100 bet" in copy
    assert "one\n              unit is one flat bet" not in modal
    assert "Models use a flat $100 bet" in hero
    assert "Yesterday and Models use a flat $100 bet" not in hero


@needs_node
def test_yesterday_matches_discord_on_the_fixture_day(tmp_path: Path):
    assert NODE is not None
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    expected = _expected(fixture)
    # The void and the unpublished win are in the fixture and out of the tally.
    assert expected["overall"]["wins"] == 3
    assert expected["overall"]["losses"] == 3
    assert expected["overall"]["pushes"] == 1
    (tmp_path / "expected.json").write_text(json.dumps(expected), encoding="utf-8")
    (tmp_path / "fixture.json").write_text(
        FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    script = _rewrite(
        (MOBILE / "scripts" / "verify_yesterday_units.ts").read_text(encoding="utf-8"))
    # node:fs stays. The alias rewrite does not touch it.
    (tmp_path / "verify_yesterday_units.ts").write_text(script, encoding="utf-8")
    for name in LIBS:
        (tmp_path / name).write_text(
            _rewrite((LIB / name).read_text(encoding="utf-8")), encoding="utf-8")
    (tmp_path / "package.json").write_text('{"type": "module"}\n', encoding="utf-8")
    proc = subprocess.run(
        [NODE, "--experimental-strip-types", "verify_yesterday_units.ts",
         "fixture.json", "expected.json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "\nALL PASS" in proc.stdout
    assert "[PASS] overall units" in proc.stdout
    assert "[PASS] overall units text" in proc.stdout
    assert "[PASS] format 7.3111 as +7.31u" in proc.stdout
    assert "[PASS] format 1 / 1.3 as +76.9%" in proc.stdout


@needs_node
def test_the_existing_daily_recap_verifier_passes(tmp_path: Path):
    assert NODE is not None
    script = _rewrite(
        (MOBILE / "scripts" / "verify_daily_results.ts").read_text(encoding="utf-8"))
    (tmp_path / "verify_daily_results.ts").write_text(script, encoding="utf-8")
    for name in LIBS:
        (tmp_path / name).write_text(
            _rewrite((LIB / name).read_text(encoding="utf-8")), encoding="utf-8")
    (tmp_path / "package.json").write_text('{"type": "module"}\n', encoding="utf-8")
    proc = subprocess.run(
        [NODE, "--experimental-strip-types", "verify_daily_results.ts"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "\nALL PASS" in proc.stdout


UNPRICED_LIBS = LIBS + (
    "customModelBacktest.ts",
    "customModelFilters.ts",
    "modelMeta.ts",
)


@needs_node
def test_the_unpriced_pnl_verifier_passes(tmp_path: Path):
    """Yesterday's block in verify_unpriced_pnl.ts is the posted stake.

    The Models checks in that script stay on the flat book. The day block
    is one unpriced win plus one win at -140: 2.00u on 2.40u risked.
    """
    assert NODE is not None
    script_src = (MOBILE / "scripts" / "verify_unpriced_pnl.ts").read_text(encoding="utf-8")
    recap = script_src.split("Yesterday's-results recap", 1)[1]
    assert "profitFlat" not in recap
    assert "stakedFlat" not in recap
    assert "2.4" in recap
    assert "contributes no\n * money to any record" not in script_src
    script = _rewrite(script_src)
    (tmp_path / "verify_unpriced_pnl.ts").write_text(script, encoding="utf-8")
    for name in UNPRICED_LIBS:
        (tmp_path / name).write_text(
            _rewrite((LIB / name).read_text(encoding="utf-8")), encoding="utf-8")
    (tmp_path / "package.json").write_text('{"type": "module"}\n', encoding="utf-8")
    proc = subprocess.run(
        [NODE, "--experimental-strip-types", "verify_unpriced_pnl.ts"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "\nAll checks passed." in proc.stdout
    assert "[PASS] Daily recap: both wins count (2-0) at the posted stake" in proc.stdout
