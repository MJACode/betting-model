"""A player's detail screen only offers the stat groups that player can fill.

Lamar Jackson's screen shipped a "Defense" tab (Matt, 2026-09-19, screenshot):
Sacks 0.00 across L3/L5/L10/L20/Season, "Hit 0 of 10 games", a 0% badge in
alarm red. Nothing was broken -- `nfl_player_game_log` stores 0, never NULL,
for the stats a position does not produce, so the tab charted ten real zeroes.
It is still a control that leads nowhere, and the screen offered it on a
quarterback.

The rule pinned here is NOT "hide Defense for QBs" -- a list of positions would
drift at the next roster string. It is:

  * every `pos` value the log actually stores is classified as defensive or
    not, so no position falls through to "unknown"; and
  * a non-defensive position's groups never include Defense; and
  * the detail screen derives its tabs from the FILTERED chip list, so the
    filter cannot be bypassed by reading the raw catalog.

The symmetric half comes free: a linebacker no longer gets Passing, Rushing and
Receiving tabs full of the same zeroes.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "mobile" / "src" / "lib" / "playerLog.ts"
SCREEN = ROOT / "mobile" / "src" / "screens" / "PlayerStatsScreen.tsx"

# Every distinct `pos` in nfl_player_game_log, measured against production
# 2026-09-19: `select distinct pos from nfl_player_game_log` -> 25 rows, and
# `count(pos) = count(*) = 175,542`, i.e. the column is never NULL.
LOG_POSITIONS = {
    "C", "CB", "DB", "DE", "DL", "DT", "FB", "FS", "G", "ILB", "K", "LB",
    "LS", "MLB", "NT", "OL", "OLB", "OT", "P", "QB", "RB", "S", "SAF", "TE",
    "WR",
}


def _src(path: Path) -> str:
    # Explicit encoding: this repo runs on Windows, where read_text() with no
    # encoding uses cp1252 and dies on our box-drawing characters at COLLECTION
    # time, taking the whole suite with it (CLAUDE.md §7).
    return path.read_text(encoding="utf-8")


def _set_literal(name: str) -> set[str]:
    """The string members of a `const <name> = new Set([...])` declaration."""
    src = _src(LIB)
    m = re.search(rf"const {name}[^=]*=\s*new Set[^(]*\(\s*\[(.*?)\]", src, re.S)
    assert m, f"{name} not found in playerLog.ts"
    return set(re.findall(r"'([A-Za-z]+)'", m.group(1)))


def test_every_logged_position_is_classified():
    """No position falls through to "unknown" -- that is how Defense came back."""
    defensive = _set_literal("NFL_DEFENSIVE_POSITIONS")
    other = _set_literal("NFL_NON_DEFENSIVE_POSITIONS")
    assert not defensive & other, "a position cannot be on both sides of the ball"
    missing = LOG_POSITIONS - (defensive | other)
    assert not missing, f"unclassified positions in the log: {sorted(missing)}"


def test_offensive_positions_are_not_defensive():
    defensive = _set_literal("NFL_DEFENSIVE_POSITIONS")
    for pos in ("QB", "RB", "WR", "TE", "FB", "K", "P", "LS", "C", "G", "OT", "OL"):
        assert pos not in defensive, f"{pos} would still be offered a Defense tab"


def test_non_defensive_positions_get_no_defense_group():
    """The groups a non-defensive position may show, as a literal."""
    m = re.search(
        r"const NON_DEFENSIVE_GROUPS:\s*StatGroup\[\]\s*=\s*\[(.*?)\]", _src(LIB), re.S
    )
    assert m, "NON_DEFENSIVE_GROUPS not found in playerLog.ts"
    groups = set(re.findall(r"'([A-Za-z]+)'", m.group(1)))
    assert "Defense" not in groups
    assert groups == {"Passing", "Rushing", "Receiving"}


def test_defensive_positions_get_only_the_defense_group():
    m = re.search(
        r"const DEFENSIVE_GROUPS:\s*StatGroup\[\]\s*=\s*\[(.*?)\]", _src(LIB), re.S
    )
    assert m, "DEFENSIVE_GROUPS not found in playerLog.ts"
    assert set(re.findall(r"'([A-Za-z]+)'", m.group(1))) == {"Defense"}


def test_the_filter_exists_and_falls_back_to_the_full_list():
    """An empty result must never leave the screen with no tabs at all."""
    src = _src(LIB)
    m = re.search(r"export function chipsForLoadedPlayer\((.*?)\n\}", src, re.S)
    assert m, "chipsForLoadedPlayer not found in playerLog.ts"
    body = m.group(0)
    assert "games.length === 0" in body, "no data loaded yet must keep every chip"
    assert "played.size > 0 ? played" in body, "the log decides; position is only the net"
    assert "positionGroups(positionOf(games))" in body, "position must catch the empty case"
    assert "kept.length > 0 ? kept : chips" in body, "must fall back to the full chip list"


def test_a_group_is_filled_only_by_a_real_number():
    """0 and NULL both mean "did not do this" — the NFL log stores one, NCAAF the other."""
    m = re.search(r"export function filledChipCounts\((.*?)\n\}", _src(LIB), re.S)
    assert m, "filledChipCounts not found in playerLog.ts"
    assert "v != null && v !== 0" in m.group(0), "a column of zeroes is not a group the player fills"


def test_a_tab_opens_on_the_stat_the_player_fills_most():
    """Otherwise a tight end's Rushing tab opens on Rush Yards, flat zero."""
    m = re.search(r"export function openingChip\((.*?)\n\}", _src(LIB), re.S)
    assert m, "openingChip not found in playerLog.ts"
    body = m.group(0)
    assert "w > bestGroupWeight" in body, "the group's own weight must break catalog order"
    assert "n > bestScore" in body, "within a group, the most-filled chip wins"
    assert "best ?? inGroup[0] ?? null" in body, "a player who fills none still gets a chip"

    screen = _src(SCREEN)
    assert re.search(
        r"onChange=\{\(g\) => \{\s*const first = openingChip\(chips, filled, g\);", screen
    ), "a group tab must open on the stat the player fills"


def test_the_screen_derives_its_tabs_from_the_filtered_chips():
    """The raw catalog must not reach GroupTabs -- that is the bypass.

    `chipsWithRequested` wraps the filter (2026-09-20) so the ONE group the
    reader explicitly tapped through on survives it -- an Anytime TD row has to
    open on Anytime TD even for a receiver who has not scored. That is the only
    sanctioned way past this filter, and it still runs `chipsForLoadedPlayer`
    over everything else, so the pattern below allows that wrapper and nothing
    wider: `allChips` reaching `chips` on its own is still the bypass.
    """
    src = _src(SCREEN)
    assert "chipsForLoadedPlayer" in src, "PlayerStatsScreen does not filter its chips"
    assert re.search(
        r"const chips = useMemo\(\s*\(\)\s*=>\s*"
        r"(chipsWithRequested\(allChips,\s*)?chipsForLoadedPlayer\(",
        src,
    ), "`chips` must be the filtered list"
    assert re.search(
        r"const groups = useMemo\(\s*\(\)\s*=>\s*groupsOfChips\(chips\)", src
    ), "group tabs must be derived from the filtered chips"
