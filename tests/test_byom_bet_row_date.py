"""The Build Your Own Model bet list shows the game's date.

Matt, 2026-11-11: an NFL builder model listed three bets played in October and
November as "Official Mon, 8/31", the time the line locked, and the game line
read only "Sun". The old row cut "Sun, 11/8, 1:00 PM ET" at its first comma, so
the date was dropped. The row now prints `formatGameDateET` ("Sun 11/8") and no
lock time.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LIB = ROOT / "mobile" / "src" / "lib"
SCREEN = ROOT / "mobile" / "src" / "screens" / "ByomBetsScreen.tsx"

from tests._node import NODE, node_strips_types  # noqa: E402


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.skipif(not node_strips_types(), reason="node >= 22.6 not available")
def test_game_date_keeps_the_date(tmp_path):
    (tmp_path / "format.ts").write_text(_read(LIB / "format.ts"), encoding="utf-8")
    script = r"""
import { formatGameDateET } from './format.ts';
const eq = (got, want, what) => {
  if (got !== want) throw new Error(`${what}: ${JSON.stringify(got)} !== ${JSON.stringify(want)}`);
};
const now = new Date('2026-11-11T15:00:00Z');
// The phone's day label carries a comma; the old split kept only the weekday.
const day = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York',
  weekday: 'short', month: 'numeric', day: 'numeric' }).format(new Date('2026-11-08T21:05:00Z'));
eq(day.split(',')[0], 'Sun', 'the old split');
// LV @ SF, 2026-11-08 4:05 PM ET.
eq(formatGameDateET('2026-11-08T21:05:00+00:00', now), 'Sun 11/8', 'LV @ SF');
// A Monday-night kickoff after midnight UTC is still Monday in ET.
eq(formatGameDateET('2026-10-20 00:15:00+00', now), 'Mon 10/19', 'ET, not UTC');
// Today is a date like any other.
eq(formatGameDateET('2026-11-11T23:00:00Z', now), 'Wed 11/11', 'today');
// Another calendar year carries the year (All seasons).
eq(formatGameDateET('2025-01-05T18:00:00Z', now), 'Sun 1/5/25', 'last year');
eq(formatGameDateET('', now), '', 'empty');
eq(formatGameDateET(null, now), '', 'null');
eq(formatGameDateET('not a date', now), '', 'garbage');
"""
    (tmp_path / "check.mts").write_text(script, encoding="utf-8")
    out = subprocess.run(
        [NODE, "--experimental-strip-types", "--no-warnings", str(tmp_path / "check.mts")],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert out.returncode == 0, out.stderr or out.stdout


def test_row_shows_the_game_date_not_the_lock():
    src = _read(SCREEN)
    assert "formatGameDateET(bet.commence_time)" in src
    assert "locked_at" not in src
    assert "Official {" not in src
    assert ".split(',')" not in src
