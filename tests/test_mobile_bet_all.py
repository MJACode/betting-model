"""Bet all: every pre-game signal for a sport, sent as SINGLE bets.

Matt, 2026-11-14: "I like the option to bet one Sportsbook or go with best
line. They are all singles and should not be considered for a parlay."
Then: default to best line, ask if they placed the bet, and do not cover live
bets but call out that it doesn't.

The behavioural checks live in `mobile/scripts/verify_bet_all.ts`. This file
pins the parts that must hold even where node modules are not installed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"

from tests._node import tsx_cmd  # noqa: E402


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_bet_all_never_asks_a_book_for_a_parlay():
    src = _read(MOBILE / "src" / "lib" / "betslipLinks.ts")
    singles = src.split("export function combineSinglesLinks(")[1]
    assert "{ type: 'Single' }" in singles
    assert "combo" not in singles.split("function joinQueryList(")[0]
    sheet = _read(MOBILE / "src" / "components" / "BetAllSheet.tsx")
    assert "useParlaySlip" not in sheet
    assert "combineBetslipLinks" not in sheet


def test_bet_all_and_the_card_share_one_price_view():
    """Bet all offers a pick only when its card would offer the bet."""
    card = _read(MOBILE / "src" / "components" / "PickCard.tsx")
    lib = _read(MOBILE / "src" / "lib" / "betAll.ts")
    assert "pickPriceView(item, liveState, myBooks, myBooksReady)" in card
    assert "pickPriceView(item, liveState, myBooks, true)" in lib
    assert "heroAmericanForPick(" not in card


def test_signals_only_with_the_live_call_out():
    home = _read(MOBILE / "src" / "screens" / "PicksHomeScreen.tsx")
    assert "view === 'signals' && myBooksReady" in home
    assert "{BET_ALL_LIVE_NOTE}" in home
    lib = _read(MOBILE / "src" / "lib" / "betAll.ts")
    assert "if (pick.is_live === true) continue;" in lib


@pytest.mark.skipif(tsx_cmd(MOBILE) is None, reason="mobile node modules not installed")
def test_the_behavioural_checks_pass():
    proc = subprocess.run(
        [*tsx_cmd(MOBILE), "scripts/verify_bet_all.ts"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_tracking_reads_the_latest_list_not_a_render_copy():
    """Matt, 2026-11-14: three placed via Bet all, one showed tracked."""
    src = _read(MOBILE / "src" / "hooks" / "useTrackedBets.ts")
    track = src.split("export async function trackPicks(")[1].split("\n}\n")[0]
    assert "const ids = idCache ?? [];" in track
    sheet = _read(MOBILE / "src" / "components" / "BetAllSheet.tsx")
    assert "else onTrack([leg.pick]);" in sheet
    assert "if (rest.length > 0) onTrack(rest);" in sheet
    home = _read(MOBILE / "src" / "screens" / "PicksHomeScreen.tsx")
    assert "onTrack={tracked.trackMany}" in home


@pytest.mark.skipif(tsx_cmd(MOBILE) is None, reason="mobile node modules not installed")
def test_batch_tracking_keeps_every_pick():
    proc = subprocess.run(
        [*tsx_cmd(MOBILE), "scripts/verify_tracked_batch.ts"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr



def test_bet_all_lists_tracked_picks_like_the_board():
    """Matt, 2026-11-21: once the board gained its own Tracked filter, Bet
    all shows the picks already tracked too. The sheet's "Untracked only"
    switch is gone; tracked picks are listed and ticked, marked "Tracking",
    and the board's "Not tracked" filter is how to leave them out."""
    sheet = _read(MOBILE / "src" / "components" / "BetAllSheet.tsx")
    assert "const picks = allPicks;" in sheet
    assert "untrackedOnly" not in sheet
    assert 'accessibilityLabel="Untracked only"' not in sheet
    assert "!isTracked(p.pick)" not in sheet
    assert ">Tracking</Text>" in sheet
    # Every pick, tracked or not, starts ticked.
    assert "setSelected(new Set(allPicks.map((p) => p.key)));" in sheet
    # A ticked tracked pick is named above the button (UX review).
    assert "you’re already tracking ${trackedTicked === 1 ? 'is' : 'are'} included" in sheet
    # Send-step progress counts only legs placed in this run.
    assert "step.legs.filter((l) => !trackedAtStart.has(l.key))" in sheet
    # The re-tick machinery stays removed.
    assert "seenTracked" not in sheet
    assert "untrackedKeys" not in sheet
