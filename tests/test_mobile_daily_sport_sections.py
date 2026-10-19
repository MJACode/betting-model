"""Daily results: sports with picks stay above quiet sports, in order.

Chief Engineer review 5570490212 (post-merge on #1000). The modal lists
sports with picks first and keeps quiet sports on the lines underneath.
``partitionDailySportSections`` is that split. Switching a sport chip
clears any card the previous chip had opened.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests._node import NODE, node_strips_types

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
HELPER = MOBILE / "src" / "lib" / "dailySportSections.ts"
MODAL = MOBILE / "src" / "components" / "DailyResultsModal.tsx"

needs_node = pytest.mark.skipif(
    not node_strips_types(),
    reason="node >= 22.6 not available",
)


def _read(path: Path) -> str:
    # encoding is explicit: this repo runs on Windows (CLAUDE.md §7).
    return path.read_text(encoding="utf-8")


def test_the_modal_uses_the_partition_and_resets_on_a_chip_change():
    modal = _read(MODAL)
    helper = _read(HELPER)
    assert "import { partitionDailySportSections } from '@/lib/dailySportSections';" in modal
    assert "partitionDailySportSections(visibleSections)" in modal
    # Canonical order is still built here, then partitioned. The helper
    # keeps that order; it does not sort.
    assert "...ALL_SPORTS.map(" in modal
    assert "function sportHasActivity" not in modal
    assert "section.total.picks > 0 || section.pending > 0 || section.models.length > 0" in helper
    # Opening the modal and changing the day still collapse. Switching
    # chips does too, in the same press as the filter change.
    assert "setSportFilter('ALL')" in modal
    assert "useEffect(() => setExpanded(new Set()), [date])" in modal
    assert (
        "onPress={() => {\n"
        "                      if (s === sportFilter) return;\n"
        "                      setSportFilter(s);\n"
        "                      setExpanded(new Set());\n"
        "                    }}"
    ) in modal
    # The quiet lines keep the copy they already had.
    assert "No picks  " in modal
    assert "Not posted  " in modal


def test_runs_in_pr_ci():
    ci = _read(ROOT / ".github" / "workflows" / "pr-ci.yml")
    assert "tests/test_mobile_daily_sport_sections.py" in ci


_RUNNER = r"""
import { partitionDailySportSections } from './dailySportSections.ts';

function section(sport, picks, pending, unpublished, models) {
  return {
    sport,
    total: { picks },
    pending,
    unpublished,
    models: Array(models),
  };
}

function same(name, got, expected) {
  const a = JSON.stringify(got);
  const b = JSON.stringify(expected);
  if (a !== b) {
    console.error(name + ' got ' + a + ' expected ' + b);
    process.exitCode = 1;
  } else {
    console.log('[PASS] ' + name);
  }
}

// The modal passes sections in canonical sport order. Activity is picks,
// a pending pick, or a model row. Quiet rows stay in that order, and an
// unpublished count only matters once a row is quiet.
const day = [
  section('MLB', 0, 0, 0, 0),
  section('WNBA', 2, 1, 0, 1),
  section('NBA', 0, 0, 4, 0),
  section('NFL', 0, 2, 0, 0),
  section('NCAAF', 0, 0, 5, 1),
  section('UFC', 0, 0, 0, 0),
  section('NHL', 1, 0, 3, 0),
];
const split = partitionDailySportSections(day);
same('active sports', split.active.map((s) => s.sport), ['WNBA', 'NFL', 'NCAAF', 'NHL']);
same('no picks', split.noPicks, ['MLB', 'UFC']);
same('not posted', split.notPosted, ['NBA']);

// Input order is kept inside each group. The helper does not re-sort.
const shuffled = partitionDailySportSections([
  section('NHL', 1, 0, 0, 0),
  section('MLB', 0, 1, 9, 0),
  section('WNBA', 0, 0, 0, 0),
  section('NBA', 0, 0, 1, 0),
]);
same('active keeps input order', shuffled.active.map((s) => s.sport), ['NHL', 'MLB']);
same('quiet keeps input order', shuffled.noPicks.concat(shuffled.notPosted), ['WNBA', 'NBA']);

const allActive = partitionDailySportSections([
  section('NFL', 1, 0, 0, 0),
  section('NHL', 0, 0, 0, 2),
]);
same('no quiet sports', allActive.noPicks.concat(allActive.notPosted), []);
same('all active', allActive.active.map((s) => s.sport), ['NFL', 'NHL']);

const allQuiet = partitionDailySportSections([
  section('UFC', 0, 0, 0, 0),
  section('MLB', 0, 0, 2, 0),
]);
same('all quiet active', allQuiet.active, []);
same('all quiet no picks', allQuiet.noPicks, ['UFC']);
same('all quiet not posted', allQuiet.notPosted, ['MLB']);

const empty = partitionDailySportSections([]);
same('empty active', empty.active, []);
same('empty no picks', empty.noPicks, []);
same('empty not posted', empty.notPosted, []);

if (process.exitCode) process.exit(process.exitCode);
console.log('ALL PASS');
"""


@needs_node
def test_sports_with_picks_lead_quiet_sports_and_keep_order(tmp_path: Path):
    assert NODE is not None
    (tmp_path / "dailySportSections.ts").write_text(_read(HELPER), encoding="utf-8")
    (tmp_path / "run.ts").write_text(_RUNNER, encoding="utf-8")
    (tmp_path / "package.json").write_text('{"type": "module"}\n', encoding="utf-8")
    proc = subprocess.run(
        [NODE, "--experimental-strip-types", "run.ts"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "\nALL PASS" in proc.stdout
    assert "[PASS] active sports" in proc.stdout
    assert "[PASS] no picks" in proc.stdout
    assert "[PASS] not posted" in proc.stdout
    assert "[PASS] active keeps input order" in proc.stdout
    assert "[PASS] quiet keeps input order" in proc.stdout
