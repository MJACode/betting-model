"""Picks screen declutter (Matt, 2026-11-27).

One Bet all row, the sheet opens on the current sport, started and final
picks fold into a group, the Signals card drops the stats that moved to
Pick Detail, and search is an icon. Source checks: the behaviour lives in
the components, and these strings are the contract.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile" / "src"


def _read(rel: str) -> str:
    return (MOBILE / rel).read_text(encoding="utf-8")


def test_bet_all_row_follows_the_selected_sport():
    home = _read("screens/PicksHomeScreen.tsx")
    assert "`Bet all · ${betAllReady} ready in ${sportDisplayName(sport)}`" in home
    assert "Bet all sports ·" not in home
    assert "ready to bet as singles" not in home
    assert "ready across" not in home
    # A count of sports, when one is written, is 8. This row does not count sports.
    assert "all 6 sports" not in home and "all 7 sports" not in home


def test_sheet_opens_on_the_current_sport_and_the_toggle_counts_ready_picks():
    sheet = _read("components/BetAllSheet.tsx")
    home = _read("screens/PicksHomeScreen.tsx")
    assert "useState<'sport' | 'all'>('sport')" in sheet
    assert "setScope('sport')" in sheet
    assert "onPress={() => setBetAllOpen(true)}" in home
    assert "sportCandidates.picks.length" in sheet
    assert "allCandidates.picks.length" in sheet
    assert "All sports (${allReady})" in sheet
    assert "`Bet all · ${readyCount} ${readyCount === 1 ? 'pick' : 'picks'}`" in sheet
    # Unticked picks stay unticked across the toggle: selection is filtered
    # to the union, not replaced when the scope changes.
    assert "union.has(k)" in sheet
    assert "setScope('sport')" in sheet


def test_started_and_final_picks_leave_the_main_list():
    home = _read("screens/PicksHomeScreen.tsx")
    row = _read("components/StartedPickRow.tsx")
    kind = _read("lib/startedBoard.ts")
    assert "Started (${rows.length})" in home
    assert "Final results are in Record" in home
    assert "accessibilityLabel={`Started, ${rows.length}" in home
    assert "setStartedOpen(false)" in home
    assert "startedBoardKind(" in home
    assert "kind === 'final' ? 'final' : 'live'" in home
    assert "Record" in row and "Tracked" in row
    assert "if (st === 'final' || fed?.kind === 'final') return 'final'" in kind


def test_trimmed_card_moves_model_chance_and_posted_time_to_detail():
    card = _read("components/PickCard.tsx")
    detail = _read("screens/PickDetailScreen.tsx")
    home = _read("screens/PicksHomeScreen.tsx")
    assert "trimmed = false" in card
    assert "trimmed={item.pick.is_live !== true && (view === 'signals' || searchingAll)}" in home
    assert "styles.edgeStakeRow" in card
    assert "{signalsStakeShown ?? '—'}" in card
    # Live Signals keeps the full card, so the words stay in the file.
    assert "Model chance" in card and "Expected return" in card
    assert "modelChance: trimmed ? null" in card
    assert "About this pick" in detail
    assert "Model chance" in detail and "Expected return" in detail
    assert 'label="Model"' in detail
    assert "pickTimingInfo(pick)" in detail
    assert "postedTiming.label" in detail
    assert 'label="Game time"' in detail


def test_finals_count_on_the_chip_the_signals_tab_and_the_sport_sheet():
    home = _read("screens/PicksHomeScreen.tsx")
    assert "signalCountsBySport(allData)" in home
    assert "counts[s] = (counts[s] ?? 0) + 1" in home
    assert "const signalsOnBoard = live.length + finishedSignals.filter" in home
    assert "count={todayUnknown ? null : signalsOnBoard}" in home
    # Finished picks are not on the open board. The sport sheet adds them
    # as skips, and never as ready picks.
    assert "sportBetAllCandidates(unsearched, sportFinals," in home
    assert "unsearched.filter((d) => stateByItem.get(d) !== 'final')" not in home
    # The money line still ignores a finished game.
    assert "filtered.filter((d) => stateByItem.get(d) !== 'final')" in home


def test_started_group_subtitle_and_finals_sort_last():
    home = _read("screens/PicksHomeScreen.tsx")
    row = _read("components/StartedPickRow.tsx")
    assert "Betting is closed. Track still works." in home
    assert "=== 'final' ? 1 : 0" in home
    assert "numberOfLines={1}" not in row


def test_search_is_an_icon_beside_filters_and_covers_all_sports():
    home = _read("screens/PicksHomeScreen.tsx")
    assert "const SEARCH_ICON_PT = 36" in home
    assert "width: SEARCH_ICON_PT" in home
    assert 'accessibilityLabel="Search player or team"' in home
    assert "setSearchOpen(false)" in home
    assert "search covers every sport" in home.lower() or "Search covers every sport" in home
    assert "all sports" in home
    assert "· all sports" in home
