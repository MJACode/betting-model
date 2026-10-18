"""NFL Anytime TD defense ranks (Designer Option A, 2026-10-18).

The board asks position_defense_ranks_nfl once per position group. The same
role cut and stat CASE as position_vs_opponent_nfl, or the rank describes a
different population than the player card. Season and H2H gain `pos` in this
file because adding a column changes the row type.

Not applied here. The worker applies ACTIVE_MIGRATIONS; this test only reads
the file.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "data/migrations/position_defense_ranks_nfl_2026_10_18.sql"
SIBLING = ROOT / "data/migrations/add_position_vs_opponent_nfl.sql"
LIB = ROOT / "mobile/src/lib/anytimeMatchup.ts"
QUERIES = ROOT / "mobile/src/lib/queries.ts"
SCREEN = ROOT / "mobile/src/screens/StatsScreen.tsx"
CELL = ROOT / "mobile/src/components/AnytimeMatchupCell.tsx"
MOBILE = ROOT / "mobile"

from tests._node import tsx_cmd  # noqa: E402


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sql(path: Path) -> str:
    text = _read(path)
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("--"))


def _whens(text: str, needle: str) -> list[str]:
    """The WHEN arms of the CASE that contains `needle`, whitespace-collapsed."""
    start = text.find(needle)
    assert start != -1, needle
    body = text[start:text.find("END", start)]
    arms = re.findall(r"WHEN\b.*", body)
    return [re.sub(r"\s+", " ", a).strip() for a in arms]


def test_the_worker_list_and_the_anon_grant():
    # Read the lists as text. Importing view_migrations pulls the database
    # driver, and this pin is about the order of the names, not a connection.
    vm = _read(ROOT / "data/view_migrations.py")
    start = vm.find("ACTIVE_MIGRATIONS: list[str] = [")
    body = vm[start:vm.find("\n]\n", start)]
    names = re.findall(r'"([^"]+\.sql)"', body)
    name = MIG.name
    totals = "add_nhl_skater_window_totals_2026_10_17.sql"
    units_fn = "published_pick_units_2026_10_17.sql"
    units_view = "published_record_units_2026_10_16.sql"
    assert name in names
    assert names.index(totals) < names.index(name) < names.index(units_fn)
    assert names[-1] == units_view
    anon = _read(ROOT / "data/anon_readable.py")
    assert '"position_defense_ranks_nfl"' in anon
    code = _read(MIG)
    assert "v_public_track_record" not in code
    for fn in (
        "position_defense_ranks_nfl(integer[], text, text)",
        "player_season_stat_values_nfl(integer, text)",
        "player_h2h_stat_values_nfl(integer[], text, text[], text[])",
    ):
        assert f"REVOKE ALL ON FUNCTION public.{fn} FROM PUBLIC" in code
        assert f"GRANT EXECUTE ON FUNCTION public.{fn} TO anon, authenticated" in code


def test_it_is_one_statement_and_each_piece_is_guarded():
    sql = _sql(MIG).strip()
    assert sql.startswith("DO $mig$")
    assert sql.endswith("$mig$;")
    assert sql.count("DO $mig$") == 1
    assert "AS $$" not in sql
    code = _read(MIG)
    assert "p.proname = 'position_defense_ranks_nfl'" in code
    assert "pg_get_function_result(p.oid) ILIKE '%pos text%'" in code
    assert code.count("DROP FUNCTION IF EXISTS") == 2
    assert "SECURITY INVOKER" in code
    assert "SET search_path = public, pg_temp" in code


def test_the_blend_cut_matches_the_app():
    lib = _read(LIB)
    m = re.search(r"BLEND_UNTIL_TEAM_GAMES = (\d+)", lib)
    assert m, "BLEND_UNTIL_TEAM_GAMES missing"
    n = m.group(1)
    code = _read(MIG)
    assert f"< {n}" in code
    assert f">= {n}" in code
    assert "rank() OVER (ORDER BY d.avg_allowed DESC)" in code


def test_the_role_and_stat_cuts_match_the_player_card():
    new = _read(MIG)
    old = _read(SIBLING)
    assert _whens(new, "WHEN n.pos = 'QB'") == _whens(old, "WHEN n.pos = 'QB'")
    assert _whens(new, "WHEN 'QB' THEN COALESCE(g.attempts,0)") == _whens(
        old, "WHEN 'QB' THEN COALESCE(g.attempts,0)"
    )
    # The rank function and both stat reads use the same stat CASE.
    rank_stat = _whens(new, "WHEN 'passing_yards'")
    assert rank_stat == _whens(old, "WHEN 'passing_yards'")
    assert new.count("WHEN 'rush_rec_tds'") == 3
    assert "pos text" in new
    # Re-run skips the drop once pos is already on the result type.
    assert "already returns pos — skipping" in new
    assert "pg_get_function_identity_arguments" in new
    assert "position_defense_ranks_nfl already present — skipping" in new
    assert "per qualifying player-game" in new


def test_the_app_calls_the_function_by_its_literal_name():
    queries = _read(QUERIES)
    assert "supabase.rpc('position_defense_ranks_nfl'" in queries
    screen = _read(SCREEN)
    assert "fetchPositionDefenseRanks" in screen
    assert "isAnytimeTdBoard" in screen
    assert "AnytimeMatchupCell" in screen
    assert "ATD_COPY" in screen
    # Season and H2H rows keep the position the migration adds.
    assert "pos: r.pos ?? null" in screen
    assert "Promise.allSettled" in screen
    assert "groupsUsedByBoard" in screen
    assert "ATD_POS_GROUPS" not in screen


def test_the_matchup_header_fills_its_column_and_large_text_is_one_line():
    """MATCHUP was drawing in the 48pt header style, inside a 66pt column.
    Large text was a right-aligned tier over the rank."""
    screen = _read(SCREEN)
    cell = _read(CELL)
    sort_btn = screen.split("atdSortBtn: {", 1)[1].split("},", 1)[0]
    assert "minHeight: 44" in sort_btn
    assert "minWidth: 44" in sort_btn
    assert "width: '100%'" in sort_btn
    label = screen.split("atdMatchupLabel: {", 1)[1].split("},", 1)[0]
    assert "letterSpacing: 0" in label
    assert "width:" not in label
    word = screen.split("{ATD_COPY.header}", 1)[0].rsplit("<Text", 1)[1]
    assert "atdMatchupLabel" in word
    assert "colHeaderRight" not in word
    assert "numberOfLines={2}" in word
    assert "atdHitLabelWithArrow" in screen
    assert "flexWrap: 'wrap'" in screen
    line = cell.split("lineFull: {", 1)[1].split("},", 1)[0]
    assert "textAlign: 'left'" in line
    assert "width: '100%'" in line
    full = cell.split("wrapFull: {", 1)[1].split("},", 1)[0]
    assert "alignItems: 'flex-start'" in full
    assert "stackedMatchupLine(view.tier, view.line)" in cell
    # Scale 1 keeps the 66pt column. The first step above it stacks, because
    # MATCHUP plus the arrow fills 66pt and clips as soon as the type grows.
    assert "PixelRatio.getFontScale() > ATD_STACK_FONT_SCALE" in screen


@pytest.mark.skipif(tsx_cmd(MOBILE) is None, reason="mobile node modules not installed")
def test_the_matchup_checks_pass():
    proc = subprocess.run(
        [*tsx_cmd(MOBILE), "scripts/verify_anytime_matchup.ts"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
