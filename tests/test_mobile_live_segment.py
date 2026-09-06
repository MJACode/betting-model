"""Live is a conditional segment on Picks, not a bottom tab.

2026-09-06 (matt). The in-play board was its own tab from Phase 5 until now. It
was the same PickCard over the same sport filter in a lossy copy of the Picks
header -- the third state of one object holding a sixth of the tab bar. Measured
over the 30 days to 2026-09-06: 175 live BETs on 25 of 31 days, ~5.3h of board
occupancy per active day, so the board was empty ~81% of the clock; and because
it is sport-scoped, empty 100% of it for NBA, NHL, NFL, UFC and GOLF.

The app had already run this merge once -- `Today | Signals` replaced separate
Picks and Signals tabs for the same reason -- so Live became the third segment.

Three properties are pinned here, each of which has a silent failure mode:

1. THE SEGMENT IS CONDITIONAL. It renders only when the selected sport has live
   picks. An always-present segment that is empty 81% of the time reproduces
   exactly the thing the tab was removed for.

2. THE BETSLIP RESOLVER READS LIVE PICKS. Live picks became addable to the slip
   in the same change. fetchPicksForDate excludes is_live rows by construction,
   and useResolvedSlip PRUNES any key its board cannot resolve -- so a resolver
   that reads only today's picks would accept the add, tick the badge, then
   delete the leg a second later with no error anywhere. The add would simply
   not work.

3. THE DK-ONLY PRICING CAVEAT IS SCOPED TO THE LIVE VIEW. It is load-bearing
   (CLAUDE.md §6: the models decide on DraftKings, and the in-play feed is a
   ~45s cache) and it is wrong on the pre-game board, which is multi-book.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
APP = MOBILE / "App.tsx"
PICKS = MOBILE / "src" / "screens" / "PicksHomeScreen.tsx"
TYPES = MOBILE / "src" / "types" / "index.ts"
SLIP = MOBILE / "src" / "hooks" / "useResolvedSlip.ts"
SETTINGS = MOBILE / "src" / "screens" / "SettingsScreen.tsx"


def _read(p: Path) -> str:
    # Explicit encoding: this repo runs on Windows, where the platform default
    # (cp1252) dies on our box-drawing characters at COLLECTION time and takes
    # the whole suite with it (CLAUDE.md §7).
    return p.read_text(encoding="utf-8")


# ── 1. the tab is gone ────────────────────────────────────────────────────────


def test_live_is_not_a_bottom_tab():
    tabs = re.findall(r"<Tab\.Screen\s+name=\"(\w+)\"", _read(APP))
    assert "Live" not in tabs, "Live is registered as a bottom tab again"
    assert tabs == ["Picks", "TrackRecord", "Performance", "Models", "Stats"], tabs


def test_live_is_not_in_the_tab_param_list():
    m = re.search(r"export type TabParamList = \{(.*?)\n\};", _read(TYPES), re.S)
    assert m, "TabParamList not found"
    assert not re.search(r"^\s*Live:", m.group(1), re.M), "Live is still a tab route"


def test_the_live_screen_file_is_gone():
    assert not (MOBILE / "src" / "screens" / "LiveScreen.tsx").exists()
    # Its banner went with it -- it was already dead, and its comment described a
    # row removed in 2026-08-02.
    assert not (MOBILE / "src" / "components" / "LiveGameBanner.tsx").exists()


def test_nothing_navigates_to_a_live_route():
    """A stale navigate('Live') must be a type error, not a silent no-op."""
    src_dir = MOBILE / "src"
    offenders = []
    for path in list(src_dir.rglob("*.ts")) + list(src_dir.rglob("*.tsx")) + [APP]:
        for line in _read(path).splitlines():
            stripped = line.strip()
            # Comments discuss the retired route on purpose -- it is the code
            # that must not reach for it.
            if stripped.startswith(("//", "*", "/*")):
                continue
            if re.search(r"navigate\(\s*'Live'", line) or re.search(
                r"screen:\s*'Live'", line
            ):
                offenders.append(f"{path.relative_to(ROOT)}: {stripped}")
    assert not offenders, offenders


def test_settings_points_at_the_live_segment():
    src = _read(SETTINGS)
    assert "Live betting (beta)" in src, "the Settings entry point disappeared"
    assert re.search(
        r"screen:\s*'Picks',\s*params:\s*\{\s*view:\s*'live'\s*\}", src
    ), "Settings' live-betting row no longer opens the live segment"


# ── 2. the segment is conditional ─────────────────────────────────────────────


def test_picks_carries_a_live_view():
    src = _read(PICKS)
    m = re.search(r"export type PicksView = ([^;]+);", src)
    assert m, "PicksView not found"
    assert "'live'" in m.group(1), m.group(1)


def test_the_live_segment_renders_only_when_something_is_live():
    """No live picks in this sport, no segment -- no empty slot to learn to ignore."""
    src = _read(PICKS)
    m = re.search(r"(\{[^{}]*liveData\.length > 0[^{}]*\?\s*\(\s*<SubTabBtn)", src, re.S)
    assert m, (
        "the Live SubTabBtn is not guarded by liveData.length > 0. An "
        "always-present segment that is empty most of the time is the failure "
        "the Live TAB was removed for."
    )


def test_the_other_two_segments_are_unconditional():
    """Today and Signals must NOT pick up the live segment's guard."""
    src = _read(PICKS)
    for label in ("Today", "Signals"):
        m = re.search(rf'<SubTabBtn label="{label}"', src)
        assert m, f"the {label} segment disappeared"
        preceding = src[max(0, m.start() - 120) : m.start()]
        assert "length > 0 ?" not in preceding, (
            f"the {label} segment became conditional; only Live is"
        )


def test_leaving_a_sport_does_not_eject_you_from_a_live_game():
    """The sport-change reset keeps the view when the new sport is also live.

    A blanket setView('today') was correct while both views always existed; with
    a conditional third segment it would bounce a user out of a game they are
    watching every time they glanced at another sport.
    """
    src = _read(PICKS)
    assert re.search(
        r"setView\(\(v\) => \(v === 'live' && !liveSports\.has\(sport\) \? 'today' : v\)\)",
        src,
    ), "the sport-change effect resets the view unconditionally again"


def test_the_live_poll_is_slow_unless_you_are_watching_it():
    """A flat 30s poll would run for most of a session, since Picks is always open."""
    src = _read(PICKS)
    assert re.search(
        r"pollMs:\s*view === 'live' \? LIVE_POLL_MS : LIVE_IDLE_POLL_MS", src
    ), "the live poll is no longer gated on the live segment being open"


def test_the_empty_state_is_exhaustive_over_the_three_views():
    """A view without its own copy must fail the build, not inherit Signals'."""
    src = _read(PICKS)
    assert "const exhaustive: never = view;" in src, (
        "the exhaustiveness guard on EmptyForView is gone -- a fourth view would "
        "silently inherit another view's empty copy"
    )
    assert re.search(r"if \(view === 'live'\) \{", src), "no live empty state"


# ── 3. the betslip actually works on a live pick ──────────────────────────────


def test_the_slip_resolves_against_live_picks_too():
    src = _read(SLIP)
    assert "useLivePicks" in src, (
        "useResolvedSlip no longer reads live picks. fetchPicksForDate excludes "
        "is_live rows, and this hook prunes what it cannot resolve -- so adding a "
        "live pick to the betslip would silently delete itself."
    )
    assert re.search(r"\[\.\.\.data,\s*\.\.\.livePicks\.data\]", src), (
        "the resolution board is no longer the union of pre-game and live picks"
    )


def test_no_app_root_component_reaches_a_focus_aware_hook():
    """useFocusEffect calls useNavigation(), which THROWS outside the navigator.

    BetslipBar is mounted at the app root as a sibling of <NavigationContainer>
    so one bar covers the tabs and pushed screens alike, so every hook on its
    path is outside both NavigationContext and NavigationContainerRefContext.
    Wiring live picks into useResolvedSlip (which BetslipBar calls) put
    useFocusEffect on that path and crashed on render for any user with
    something in their betslip, on every screen (UX review, 2026-09-06).

    This is a class of bug ux_scan cannot see -- it has no cross-file
    reachability -- and it is the second time a hook has moved into an app-root
    component. So the property is pinned over the whole transitive import graph
    rather than on the one hook that broke.

    The walk is SYMBOL-level, not file-level: useLivePicks.ts legitimately holds
    both a focus-aware variant (for screens) and an unfocused one, so "this file
    mentions useFocusEffect" is not the question. The question is whether the
    functions actually reachable from the root call it.
    """
    src_dir = MOBILE / "src"
    root = src_dir / "components" / "BetslipBar.tsx"
    assert root.exists(), f"{root} moved -- re-point this test"

    def symbol_bodies(path: Path) -> dict[str, str]:
        """Top-level function declarations in a module, by name.

        Body = source from the declaration to the next top-level declaration,
        which is coarse but never UNDER-reports a call, so it cannot make this
        test pass by missing something.
        """
        src = _read(path)
        decls = [
            (m.start(), m.group(1))
            for m in re.finditer(r"^(?:export )?function (\w+)", src, re.M)
        ]
        out: dict[str, str] = {}
        for i, (pos, name) in enumerate(decls):
            end = decls[i + 1][0] if i + 1 < len(decls) else len(src)
            out[name] = src[pos:end]
        return out

    def imports_of(path: Path) -> dict[str, Path]:
        """Imported local symbol -> the module file it came from."""
        out: dict[str, Path] = {}
        for names, spec in re.findall(r"import \{([^}]+)\} from '@/([^']+)'", _read(path)):
            target = None
            for suffix in (".ts", ".tsx"):
                cand = src_dir / f"{spec}{suffix}"
                if cand.exists():
                    target = cand
                    break
            if target is None:
                continue
            for raw in names.split(","):
                name = raw.strip().removeprefix("type ").split(" as ")[-1].strip()
                if name:
                    out[name] = target
        return out

    offenders: list[str] = []
    seen: set[tuple[Path, str]] = set()
    # The root module's own top-level code counts, whatever it is named.
    stack = [(root, name) for name in symbol_bodies(root)]
    while stack:
        path, name = stack.pop()
        if (path, name) in seen:
            continue
        seen.add((path, name))
        body = symbol_bodies(path).get(name)
        if body is None:
            continue
        if "useFocusEffect" in body:
            offenders.append(f"{path.relative_to(ROOT)}::{name}")
            continue
        for sym, target in imports_of(path).items():
            if re.search(rf"\b{re.escape(sym)}\b", body):
                stack.append((target, sym))

    assert not offenders, (
        "these functions are reachable from an app-root component mounted "
        f"outside NavigationContainer and use useFocusEffect: {offenders}. "
        "useNavigation() throws there. Use a plain useEffect variant "
        "(see useLivePicksUnfocused) on that path."
    )


def test_the_slip_uses_the_unfocused_live_hook():
    src = _read(SLIP)
    assert "useLivePicksUnfocused" in src, (
        "useResolvedSlip must use the unfocused variant -- it is mounted by "
        "BetslipBar, outside NavigationContainer"
    )
    assert "useLivePicks(" not in src, "the focus-aware variant is back on the slip path"


def test_pruning_is_held_while_the_live_half_is_unknown():
    """A failed live read looks identical to 'your live leg is gone'."""
    src = _read(SLIP)
    m = re.search(r"canPruneSlip\(\{(.*?)\}\)", src, re.S)
    assert m, "canPruneSlip call not found"
    body = m.group(1)
    assert "livePicks.loading" in body, "a live fetch in flight can prune a live leg"
    assert "livePicks.error" in body, "a failed live fetch can prune a live leg"


# ── 4. the DK-only caveat stays where it is true ──────────────────────────────


def test_the_live_pricing_caveat_is_scoped_to_the_live_view():
    src = _read(PICKS)
    assert "priced and placed at DraftKings only" in src, (
        "the live DK-only / staleness caveat was lost in the merge (CLAUDE.md §6)"
    )
    m = re.search(
        r"\{view === 'live' \? \(\s*<View style=\{styles\.liveNoteWrap\}>(.*?)\)\s*:\s*null\}",
        src,
        re.S,
    )
    assert m, "the live caveat is not gated on view === 'live'"
    assert "DraftKings only" in m.group(1)


def test_the_caveat_does_not_reintroduce_the_your_sportsbook_contradiction():
    """One paragraph, not two: a prior UX review removed "bet your sportsbook's
    number" sitting beside "your sportsbook doesn't apply"."""
    src = _read(PICKS)
    m = re.search(r"styles\.liveNoteWrap\}>(.*?)</View>", src, re.S)
    assert m, "live caveat block not found"
    assert "your sportsbook" not in m.group(1).lower()
