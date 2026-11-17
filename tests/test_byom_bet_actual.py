"""The Build Your Own Model bet list shows what actually happened.

Matt, 2026-11-17: "we should definitely show actual on the win or loss".
A row read "Jordan Mason Over 0.5 · Won" with no number, so a 0.5
receiving-yards line looked like a bug. byom_bets now returns `actual`
(a prop's stat) and the final score, and the row prints one of them.
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
MIGRATION = ROOT / "data" / "migrations" / "byom_bets_actual_2026_11_17.sql"

from tests._node import NODE, node_strips_types  # noqa: E402


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.skipif(not node_strips_types(), reason="node >= 22.6 not available")
def test_actual_text(tmp_path):
    src = _read(LIB / "byomActual.ts").replace(
        "import type { ByomBet } from './byom';\n", "type ByomBet = any;\n")
    (tmp_path / "byomActual.ts").write_text(src, encoding="utf-8")
    script = r"""
import { byomActualText } from './byomActual.ts';
const eq = (got, want, what) => {
  if (got !== want) throw new Error(`${what}: ${JSON.stringify(got)} !== ${JSON.stringify(want)}`);
};
const prop = { market: 'player_reception_yds', player_name: 'Jordan Mason', home_team: 'MIN', away_team: 'BUF',
  home_score: 24, away_score: 20 };
// Production, 2026-11-17: BUF @ MIN, Mason 7 receiving yards on Over 0.5.
eq(byomActualText({ ...prop, actual: 7 }), 'Actual: 7', 'prop');
eq(byomActualText({ ...prop, actual: 0 }), 'Actual: 0', 'zero is a value');
eq(byomActualText({ ...prop, actual: -3 }), 'Actual: -3', 'negative yards');
// A prop with no stored stat says nothing; it does not fall back to the score.
eq(byomActualText({ ...prop, actual: null }), null, 'prop, no actual');
// Yes/no markets are stored as 1 or 0, so they never read "Actual: 0".
eq(byomActualText({ ...prop, market: 'player_double_double', actual: 1 }), 'Double-double: yes', 'DD yes');
eq(byomActualText({ ...prop, market: 'player_double_double', actual: 0 }), 'Double-double: no', 'DD no');
eq(byomActualText({ ...prop, market: 'player_triple_double', actual: 0 }), 'Triple-double: no', 'TD3 no');
eq(byomActualText({ ...prop, market: 'player_anytime_td', actual: 2 }), 'TDs: 2', 'anytime TD');
eq(byomActualText({ ...prop, market: 'player_anytime_td', actual: 0 }), 'No TD', 'no TD');
const game = { player_name: null, actual: null, home_team: 'DEN', away_team: 'KC',
  home_score: 24, away_score: 20 };
eq(byomActualText(game), 'Final: KC 20 @ DEN 24', 'game, away first');
eq(byomActualText({ ...game, home_score: null }), null, 'game, no score');
"""
    (tmp_path / "check.mts").write_text(script, encoding="utf-8")
    out = subprocess.run(
        [NODE, "--experimental-strip-types", "--no-warnings", str(tmp_path / "check.mts")],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert out.returncode == 0, out.stderr or out.stdout


def test_row_prints_the_actual():
    screen = _read(SCREEN)
    assert "byomActualText(bet)" in screen
    assert "{actual}" in screen


def test_parser_reads_the_new_columns():
    byom = _read(LIB / "byom.ts")
    for col in ("actual", "home_score", "away_score"):
        assert f"optionalNum(row, '{col}')" in byom


def test_migration_is_active_and_safe():
    from data.view_migrations import ACTIVE_MIGRATIONS
    names = list(ACTIVE_MIGRATIONS)
    assert MIGRATION.name in names
    # After the file that first created byom_bets.
    assert names.index(MIGRATION.name) > names.index("byom_official_legs_2026_11_04.sql")
    sql = _read(MIGRATION)
    # The older file skips only while five functions carry its marker.
    assert "-- byom_official_legs_v1" in sql
    assert "position('byom_bets_actual_v1' in p.prosrc)" in sql
    for col in ("actual numeric", "home_score numeric", "away_score numeric"):
        assert col in sql
    assert "FROM PUBLIC" in sql
    assert "TO anon, authenticated;" in sql
    assert "TO service_role;" in sql
    assert "picks" not in sql.lower().replace("does not write picks", "")


def test_yes_no_keys_match_the_record_constants():
    record = _read(LIB / "byomRecord.ts")
    actual = _read(LIB / "byomActual.ts")
    for name, key in (("ANYTIME_TD_MARKET", "player_anytime_td"),
                      ("DOUBLE_DOUBLE_MARKET", "player_double_double"),
                      ("TRIPLE_DOUBLE_MARKET", "player_triple_double")):
        assert f"{name}: ByomPropMarket = '{key}'" in record
        assert f"'{key}'" in actual
