"""Every sport in SPORTS survives a cold start.

`useSportFilter` is the app's global sport selector and it persists the
selection to AsyncStorage. Reading it back validated the stored string against a
HAND-WRITTEN list of six sports -- 'WNBA', 'MLB', 'NBA', 'UFC', 'GOLF', 'NHL' --
while `SPORTS` has held all eight since NFL and NCAAF shipped. Anything not on
the hand-written list fell through to DEFAULT_SPORT, so a user who selected NFL
or NCAAF, closed the app and reopened it was silently returned to MLB. Found
2026-09-06, in September, when those are the two sports in season.

The rule this pins is not "NFL and NCAAF are on the list" -- adding two more
literals would satisfy that and drift again at the next sport. It is that the
validation is DERIVED from SPORTS, so a sport cannot be added to the selector
without being added to what survives a restart.

The same property in its cross-file form: SPORTS is the one place the sport set
is written down, and every other list of sports in the hook agrees with it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "mobile" / "src" / "hooks" / "useSportFilter.ts"


def _src() -> str:
    # encoding is explicit: this repo runs on Windows, where read_text() with no
    # encoding uses cp1252 and dies on the box-drawing characters in our source
    # at COLLECTION time, taking the whole suite with it (CLAUDE.md §7).
    return HOOK.read_text(encoding="utf-8")


def _sports() -> list[str]:
    """The SPORTS array literal, in declaration order."""
    m = re.search(r"export const SPORTS:\s*Sport\[\]\s*=\s*\[(.*?)\]", _src(), re.S)
    assert m, "SPORTS array not found in useSportFilter.ts"
    return re.findall(r"'([A-Z]+)'", m.group(1))


def _load_body() -> str:
    """The body of load() -- the function that reads the persisted value back."""
    m = re.search(r"async function load\(\).*?\n\}", _src(), re.S)
    assert m, "load() not found in useSportFilter.ts"
    return m.group(0)


def test_sports_holds_all_eight():
    assert set(_sports()) == {
        "MLB",
        "WNBA",
        "NBA",
        "NFL",
        "NCAAF",
        "UFC",
        "GOLF",
        "NHL",
    }


def test_every_sport_survives_a_cold_start():
    """No sport in SPORTS is silently reverted to the default on restart.

    Satisfied by deriving the check from SPORTS. A hand-written list also passes
    while it happens to be complete -- which is exactly how this broke -- so
    test_the_persisted_value_is_validated_against_sports pins the derivation
    itself.
    """
    body = _load_body()
    if "SPORTS.includes" in body:
        return
    missing = [s for s in _sports() if f"'{s}'" not in body]
    assert not missing, (
        f"load() drops {missing} back to DEFAULT_SPORT on cold start: they are in "
        "SPORTS but not in the validation. Validate against SPORTS instead of a "
        "hand-written list."
    )


def test_the_persisted_value_is_validated_against_sports():
    """The validation is derived from SPORTS, not re-typed beside it."""
    body = _load_body()
    assert "SPORTS.includes" in body, (
        "load() validates the persisted sport against a hand-written list. Use "
        "SPORTS.includes(raw as Sport) so adding a sport to the selector cannot "
        "leave it unable to survive a restart."
    )


def test_no_second_hand_written_sport_list_in_the_hook():
    """SPORTS is the only place the sport set is enumerated in this file."""
    src = _src()
    # The Sport union type is the one legitimate second enumeration -- it is what
    # SPORTS is typed against, and TypeScript makes the two disagree loudly.
    src_without_union = re.sub(r"export type Sport =.*?;", "", src, flags=re.S)
    src_without_sports = re.sub(
        r"export const SPORTS:\s*Sport\[\]\s*=\s*\[.*?\];", "", src_without_union, flags=re.S
    )
    # A lone reference (DEFAULT_SPORT = 'MLB') is fine; a RUN of three or more
    # sport literals on one line is a list being re-typed.
    runs = re.findall(
        r"(?:'(?:MLB|WNBA|NBA|NFL|NCAAF|UFC|GOLF|NHL)'[^\n]{0,40}){3,}", src_without_sports
    )
    assert not runs, (
        f"a second sport list appears in useSportFilter.ts: {runs}. SPORTS is the "
        "single source of truth for the sport set."
    )
