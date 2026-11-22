"""The Performance tab's Insights card (Matt, 2026-11-21).

Recaps for today, this week (Monday to Sunday), this month, this year and all
time; best and toughest bet; breakdowns by sport, bet type, book and price;
closing line; form; the units line; and the member against every posted pick
from the models they follow. Scored at "My stakes", logged bets folded in.

The behavioural half is mobile/scripts/verify_performance_insights.ts, run
here with node's type stripping (lib/performanceInsights.ts has no imports).
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
SRC = MOBILE / "src"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_the_insights_maths_passes():
    from tests._node import NODE, node_strips_types

    if not node_strips_types():
        pytest.skip("node >= 22.6 not available")
    assert NODE is not None
    script = _read(MOBILE / "scripts" / "verify_performance_insights.ts")
    script = re.sub(r"from '\.\./src/lib/(\w+)';", r"from './\1.ts';", script)
    script = re.sub(r"^import type [^;]*;\n", "", script, flags=re.M)
    lib = _read(SRC / "lib" / "performanceInsights.ts")
    assert not re.search(r"^import (?!type)", lib, flags=re.M), "the maths must stay import-free"
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "verify.ts").write_text(script, encoding="utf-8")
        (folder / "performanceInsights.ts").write_text(lib, encoding="utf-8")
        (folder / "package.json").write_text('{"type": "module"}\n', encoding="utf-8")
        proc = subprocess.run(
            [NODE, "--experimental-strip-types", "verify.ts"],
            cwd=folder, capture_output=True, text=True, timeout=60,
        )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "[FAIL]" not in proc.stdout
    assert "[PASS] week of a Saturday starts Monday" in proc.stdout


def test_the_card_is_scored_at_my_stakes_with_logged_bets_folded_in():
    screen = _read(SRC / "screens" / "PerformanceScreen.tsx")
    assert "buildInsightBets(tracked.myStakeRows, manual.bets)" in screen
    hook = _read(SRC / "hooks" / "useTrackedBetResults.ts")
    assert "trackedStakeFor('custom', stakes.customStakes)" in hook


def test_the_card_is_on_both_versions_of_the_screen():
    screen = _read(SRC / "screens" / "PerformanceScreen.tsx")
    assert screen.count("{insightsCard}") == 2


def test_the_models_read_is_paged_and_names_its_relation():
    q = _read(SRC / "lib" / "queries.ts")
    body = q.split("export async function fetchModelDailyRecordFull", 1)[1].split("\nexport ", 1)[0]
    assert "fetchAllPages" in body
    assert ".from('v_public_track_record_model_daily')" in body


def test_results_print_in_units_never_dollars():
    card = _read(SRC / "components" / "PerformanceInsightsCard.tsx")
    assert "$" not in re.sub(r"\$\{", "", card)
    assert "formatFlatUnits" in card


def test_the_hooks_on_this_path_do_not_use_focus_effect():
    for rel in ("hooks/useModelDailyRecordFull.ts", "components/PerformanceInsightsCard.tsx"):
        assert not re.search(r"import[^;]*\buseFocusEffect\b", _read(SRC / rel)), rel


def _run_stripped(script_name: str, lib_name: str) -> subprocess.CompletedProcess:
    from tests._node import NODE

    script = _read(MOBILE / "scripts" / script_name)
    script = re.sub(r"from '\.\./src/lib/(\w+)';", r"from './\1.ts';", script)
    script = re.sub(r"^import type [^;]*;\n", "", script, flags=re.M)
    lib = _read(SRC / "lib" / f"{lib_name}.ts")
    assert not re.search(r"^import (?!type)", lib, flags=re.M), f"{lib_name} must stay import-free"
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "verify.ts").write_text(script, encoding="utf-8")
        (folder / f"{lib_name}.ts").write_text(lib, encoding="utf-8")
        (folder / "package.json").write_text('{"type": "module"}\n', encoding="utf-8")
        return subprocess.run(
            [NODE, "--experimental-strip-types", "verify.ts"],
            cwd=folder, capture_output=True, text=True, timeout=60,
        )


def test_the_bet_lists_group_by_date_with_see_all():
    """Matt, 2026-11-21: the bet list collapsible by bet date, with a See all."""
    from tests._node import node_strips_types

    if not node_strips_types():
        pytest.skip("node >= 22.6 not available")
    proc = _run_stripped("verify_bet_date_groups.ts", "betDateGroups")
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "[FAIL]" not in proc.stdout
    assert "[PASS] dates run newest first" in proc.stdout


def test_both_bet_lists_use_the_date_groups_and_the_row_cap_is_gone():
    screen = _read(SRC / "screens" / "PerformanceScreen.tsx")
    assert screen.count("<DateGroupedList") == 2
    assert "TRACKED_ROW_CAP" not in screen
