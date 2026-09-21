"""Tapping a player opens THAT stat -- the one the reader was already reading.

Matt, 2026-09-20: "if I click on Rashee Rice any time TD and click on the
player I should be brought to any time TD stats, instead when I click on the
player it defaults to the receptions stat."

Nothing was broken in the sense of a wrong number. The player screen chose the
stat that player FILLS MOST (`openingChip`, added 2026-09-19 so a receiver
would not open on a Rushing tab holding one touchdown), and for a wide receiver
that is Receptions every time. The question the reader asked on the way in --
the board's selected stat, or the prop a pick is written on -- was simply not
carried across the navigation, so the screen had nothing to answer with.

What is pinned here is the HANDOVER, end to end, because each half is useless
alone: every caller states the stat, the route carries it, and the screen
opens on it.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "mobile" / "src" / "lib" / "playerLog.ts"
TYPES = ROOT / "mobile" / "src" / "types" / "index.ts"
SCREEN = ROOT / "mobile" / "src" / "screens" / "PlayerStatsScreen.tsx"
HIT_MODE = ROOT / "mobile" / "src" / "lib" / "hitMode.ts"
CALLERS = (
    ROOT / "mobile" / "src" / "screens" / "StatsScreen.tsx",
    ROOT / "mobile" / "src" / "screens" / "PickDetailScreen.tsx",
)


def _src(path: Path) -> str:
    # Explicit encoding: this repo runs on Windows, where read_text() with no
    # encoding uses cp1252 and dies on our box-drawing characters at COLLECTION
    # time, taking the whole suite with it (CLAUDE.md §7).
    return path.read_text(encoding="utf-8")


def _navigate_blocks(src: str) -> list[str]:
    """Every `navigation.navigate('PlayerStats', { ... })` argument object."""
    blocks: list[str] = []
    for m in re.finditer(r"navigate\(\s*'PlayerStats'\s*,\s*\{", src):
        i = m.end() - 1
        depth = 0
        for j in range(i, len(src)):
            if src[j] == "{":
                depth += 1
            elif src[j] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(src[i : j + 1])
                    break
    return blocks


def test_route_carries_the_stat():
    """The PlayerStats route has somewhere to put the question."""
    params = re.search(r"\n  PlayerStats: \{(.*?)\n  \};", _src(TYPES), re.S)
    assert params, "PlayerStats route params not found"
    body = params.group(1)
    assert "statKey?: string;" in body
    assert "statGroup?: string;" in body


def test_every_caller_states_the_stat():
    """A caller that stays silent is a caller that lands on Receptions."""
    seen = 0
    for path in CALLERS:
        for block in _navigate_blocks(_src(path)):
            seen += 1
            assert "statKey:" in block, f"{path.name}: navigate('PlayerStats') sends no statKey"
            assert "statGroup:" in block, f"{path.name}: navigate('PlayerStats') sends no statGroup"
    # Both known entry points -- the Stats board row and a prop pick's "View
    # all stats" button. A third one appearing is exactly what this should
    # catch, since it will not have been written with the handover in mind.
    assert seen == 2, f"expected 2 PlayerStats call sites, found {seen}"


def test_screen_opens_on_the_requested_stat():
    src = _src(SCREEN)
    assert "requestedChip(allChips, route.params.statKey, route.params.statGroup)" in src
    # Seeded at mount...
    assert re.search(
        r"useState<StatDef \| null>\(\s*\(\) => requested \?\? defaultChipForPlayer", src
    ), "initial stat is not seeded from the requested stat"
    # ...and again when the screen is reused for another player, which is the
    # path a second tap off the board takes.
    assert "setPicked(requested ?? defaultChipForPlayer(sport, playerType));" in src
    reset = re.search(
        r"setPicked\(requested \?\? defaultChipForPlayer\(sport, playerType\)\);.*?\}, \[(.*?)\]\)",
        src,
        re.S,
    )
    assert reset and "requested" in reset.group(1), "reset effect ignores the requested stat"


def test_the_requested_stat_survives_the_loaded_player_filter():
    """A receiver with no touchdown still opens on Anytime TD when asked.

    `chipsForLoadedPlayer` drops a group the player has never filled -- right
    for a tab row nobody asked for, wrong for the stat they just tapped, whose
    honest answer is "0 of 10". Without the exemption the screen falls back to
    `openingChip` and the bug returns for exactly the players it hurt most.

    ONE CHIP, never its group (UX review, 2026-09-20). Readmitting the group
    hands that receiver Rush Yards, Rush TDs and Carries as well, all flat
    zero -- the controls 2026-09-19 removed, coming back through the exemption
    meant to answer a question he was actually asked.
    """
    screen = _src(SCREEN)
    assert "chipsWithRequested(allChips, chipsForLoadedPlayer(allChips, games), requested)" in screen

    lib = _src(LIB)
    fn = re.search(r"export function chipsWithRequested\((.*?)\n\}", lib, re.S)
    assert fn, "chipsWithRequested not found in playerLog.ts"
    body = fn.group(1)
    # No request -> the filter stands untouched, so 2026-09-19's rule holds
    # everywhere it held before.
    assert "if (!requested) return kept;" in body
    # The chip, by its full identity...
    assert "chipKey(c) === key" in body
    # ...and NOT its group-mates, which is the regression this guards.
    assert "c.group === requested.group" not in body, (
        "the exemption readmits the whole group -- the 2026-09-19 zero tabs are back"
    )


def test_the_side_travels_with_the_stat():
    """"Under 1.5 · 7 of 10" must not land on "2+ · 3 of 10".

    The board renders every row in the active idiom, so without this the
    complementary bet on the same ten games is one tap away and nothing on
    either screen connects the two numbers (UX review, 2026-09-20). Averages
    rows carry no side and must send none.
    """
    assert "hitMode?: string;" in _src(TYPES)

    board = _src(CALLERS[0])
    assert "hitMode: effectiveMode === 'hitRate' ? hitMode : undefined," in board, (
        "the board must send its side, and only where the row has one"
    )

    # Pick Detail is the other caller, and #807 left it sending the stat
    # without the side. An Under prop then opened PlayerStats on atLeast —
    # complementary hits on the same games (Reviewer Medium on #807).
    detail = _src(CALLERS[1])
    detail_navs = _navigate_blocks(detail)
    assert detail_navs, "PickDetail has no PlayerStats navigate"
    assert any("hitMode:" in b for b in detail_navs), (
        "PickDetail navigate('PlayerStats') sends no hitMode"
    )
    assert "hitModeFromPickSide(pick.pick_side)" in detail, (
        "PickDetail must seed hitMode from the pick's own side"
    )

    screen = _src(SCREEN)
    assert "asHitMode(route.params.hitMode) ?? 'atLeast'" in screen
    assert "useState<HitMode>(requestedMode)" in screen, "the side is not seeded at mount"
    assert "setMode(requestedMode);" in screen, "the side is not re-seeded for the next player"

    # Validated, not cast: navigation state is serialised and restored, so a
    # value this build does not know has to fall back rather than reach HitMode.
    fn = re.search(r"export function asHitMode\((.*?)\n\}", _src(HIT_MODE), re.S)
    assert fn, "asHitMode not found in hitMode.ts"
    assert "'atLeast'" in fn.group(1) and "'under'" in fn.group(1)

    # The pick-side mapping is the producer half of the same handshake.
    mapped = re.search(r"export function hitModeFromPickSide\((.*?)\n\}", _src(HIT_MODE), re.S)
    assert mapped, "hitModeFromPickSide not found in hitMode.ts"
    body = mapped.group(1)
    assert "side === 'under' ? 'under'" in body
    assert "side === 'over' ? 'over'" in body
    assert "'atLeast'" in body


def test_innings_resolves_to_the_outs_chip():
    """MLB's one stat that is named differently on the two screens.

    The board sums innings (5.2 IP is a notation, not a number); the detail
    screen charts outs. A pitcher tapped off the Innings board must not fall
    through to the default chip because the key did not match.
    """
    fn = re.search(r"export function requestedChip\((.*?)\n\}", _src(LIB), re.S)
    assert fn, "requestedChip not found in playerLog.ts"
    assert "innings_pitched" in fn.group(1)
    assert "OUTS_STAT.key" in fn.group(1)
