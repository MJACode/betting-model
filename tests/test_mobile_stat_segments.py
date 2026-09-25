"""The Stats tab's position row (Designer Option A, Matt-approved 2026-09-25).

QB / RB / WR/TE / DEF / Teams on the football boards and Hitters / Pitchers /
Teams on MLB replace Players | Teams, and the category dropdown goes. A
segment only scopes which existing `group:key` chips show, so no stat or
market moves. The behavioural pins live in
`mobile/scripts/verify_stat_segments.ts`; this file runs it when the mobile
toolchain is installed and pins the source-level shape either way.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"


def _read(path: Path) -> str:
    # encoding is explicit: this repo runs on Windows (CLAUDE.md §7).
    return path.read_text(encoding="utf-8")


def test_the_category_dropdown_is_gone():
    stats = _read(MOBILE / "src/screens/StatsScreen.tsx")
    assert "StatGroupSheet" not in stats
    assert not (MOBILE / "src/components/StatGroupSheet.tsx").exists()
    assert 'accessibilityLabel="Stat group"' not in stats


def test_the_chip_row_is_scoped_by_the_segment_module():
    stats = _read(MOBILE / "src/screens/StatsScreen.tsx")
    assert "chipsForSegment(sport, segment).map" in stats
    assert "statForSegment(sport, next, stat)" in stats


def test_position_is_never_inferred_from_stats():
    # The only position source is the row's own `pos` column.
    seg = _read(MOBILE / "src/lib/statSegments.ts")
    assert "statValue" not in seg
    assert "sport !== 'NFL' || !readCarriesPosition" in seg


@pytest.mark.skipif(
    not (MOBILE / "node_modules" / ".bin").exists() or shutil.which("node") is None,
    reason="mobile node modules not installed",
)
def test_the_behavioural_checks_pass():
    tsx = MOBILE / "node_modules" / ".bin" / "tsx"
    proc = subprocess.run(
        [str(tsx), "scripts/verify_stat_segments.ts"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_search_and_position_review_fixes():
    # #830 review: a typed name bypasses the position cut, the cut runs last so
    # the empty state can blame the position (not the data), and a position
    # segment that cannot filter says so in one caption under the chips.
    stats = _read(MOBILE / "src/screens/StatsScreen.tsx")
    assert "const activePositions = query.trim() ? null : segmentPositions;" in stats
    assert "rankedAll.filter((r) => matchesPosition(r.row.pos, activePositions))" in stats
    assert "hitRateAll.filter((p) => matchesPosition(p.pos, activePositions))" in stats
    assert "return positionEmptyText(segment, stat.label, timeWindow);" in stats
    assert "positionFallbackNote(sport, segment, boardMode, segmentPositions)" in stats


def test_one_shared_defensive_set():
    # DEF and the player card read one set; statSegments must not redeclare it.
    seg = _read(MOBILE / "src/lib/statSegments.ts")
    log = _read(MOBILE / "src/lib/playerLog.ts")
    assert "import { NFL_DEFENSIVE_POSITIONS } from './playerLog'" in seg
    assert "def: NFL_DEFENSIVE_POSITIONS" in seg
    assert "export const NFL_DEFENSIVE_POSITIONS" in log


def test_segment_labels_cap_only_on_fit():
    tabs = _read(MOBILE / "src/components/GroupTabs.tsx")
    assert "maxFontSizeMultiplier={fit ? 2 : undefined}" in tabs
    assert "minimumFontScale={fit ? 0.75 : undefined}" in tabs
    assert tabs.count("maxFontSizeMultiplier") == 1


def test_runs_in_pr_ci():
    ci = _read(ROOT / ".github/workflows/pr-ci.yml")
    assert "tests/test_mobile_stat_segments.py" in ci
