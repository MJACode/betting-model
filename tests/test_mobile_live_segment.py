"""Live Signals is a segment on Picks, not a bottom tab — and it is always on.

2026-09-06 (matt). The in-play board was its own tab from Phase 5 until now. It
was the same PickCard over the same sport filter in a lossy copy of the Picks
header -- the third state of one object holding a sixth of the tab bar. Measured
over the 30 days to 2026-09-06: 175 live BETs on 25 of 31 days, ~5.3h of board
occupancy per active day, so the board was empty ~81% of the clock; and because
it is sport-scoped, empty 100% of it for NBA, NHL, NFL, UFC and GOLF.

The app had already run this merge once -- `Today | Signals` replaced separate
Picks and Signals tabs for the same reason -- so Live became the third segment.

IT WAS CONDITIONAL UNTIL 2026-09-12, when matt asked for the opposite and for
the name: "I want it to always show for each sport but only populates with live
signal bets". The measurement above is the accepted cost; what the conditional
version could not do is be FOUND when nothing was live, so "is anything live?"
had nowhere to be asked and its absence read as a missing feature.

Three properties are pinned here, each of which has a silent failure mode:

1. THE SEGMENT IS UNCONDITIONAL AND THE DOT IS NOT. An always-on board makes
   "is this the live board" and "is anything live" two different questions, and
   a red dot that is always lit answers neither. The count and the dot are now
   the whole live indicator on this control, so a guard creeping back onto the
   segment, or a dot wired to the wrong thing, silently removes it.

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
import sys
from pathlib import Path

# nfl/live_model is its own package root (see tests/test_nfl_live_pick_writer.py).
sys.path.insert(0, str(Path(__file__).parent.parent / "nfl"))

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
    # Renamed with the board, 2026-09-12, and its copy no longer says the segment
    # "appears while a game is in play" -- it is always there (UX review).
    assert "Live Signals (beta)" in src, "the Settings entry point disappeared"
    assert "which appears while a game is in play" not in src, (
        "Settings still describes the conditional segment"
    )
    assert re.search(
        r"screen:\s*'Picks',\s*params:\s*\{\s*view:\s*'live'\s*\}", src
    ), "Settings' live-betting row no longer opens the live segment"


# ── 2. the segment is always on, and so is its name ───────────────────────────


def test_picks_carries_a_live_view():
    """PicksView is declared once, in types, and includes 'live'.

    It used to be spelled out inline in three places -- the screen, the tab
    param list, and (after the push router landed) lib/pushRoute, which also had
    lib/ importing a type from screens/ and inverting the layering.
    """
    m = re.search(r"export type PicksView = ([^;]+);", _read(TYPES))
    assert m, "PicksView is not declared in types/index.ts"
    assert "'live'" in m.group(1), m.group(1)
    # and nothing re-spells it
    for path, label in ((PICKS, "PicksHomeScreen"), (MOBILE / "src" / "lib" / "pushRoute.ts", "pushRoute")):
        assert not re.search(r"type PicksView = '", _read(path)), (
            f"{label} re-declares PicksView instead of importing it"
        )


def test_the_live_segment_is_always_rendered():
    """Every sport gets the board, whether or not anything is in play (matt, 2026-09-12)."""
    src = _read(PICKS)
    m = re.search(r'<SubTabBtn\s+label="Live Signals"', src)
    assert m, "the Live Signals segment is gone, or was renamed"
    preceding = src[max(0, m.start() - 400) : m.start()]
    # A JSX conditional immediately ahead of it is the old behaviour returning.
    assert "liveData.length > 0 ?" not in preceding and "view === 'live' ?" not in preceding, (
        "the Live Signals segment is conditional again. matt asked for it on "
        "every sport: a board that only exists when it has something cannot be "
        "found when it has nothing."
    )


def test_the_live_dot_on_the_segment_is_conditional():
    """The segment is permanent, so the DOT is what has to carry 'something is live'."""
    src = _read(PICKS)
    m = re.search(r'<SubTabBtn\s+label="Live Signals"(.*?)/>', src, re.S)
    assert m, "the Live Signals segment is gone, or was renamed"
    assert re.search(r"dot=\{liveData\.length > 0\}", m.group(1)), (
        "the live dot is not gated on there being live picks -- a dot that is "
        "always lit has stopped meaning anything"
    )
    # and the dot the button draws must be the gated prop, not "this is the live
    # board" -- which `live` now is, on every render of the live segment.
    assert "{dot ? <LiveDot /> : null}" in src, "SubTabBtn no longer draws the gated dot"
    assert "{live ? <LiveDot" not in src, (
        "SubTabBtn draws its dot from `live` again, which is always true on the "
        "live board -- the dot would never go out"
    )


def test_the_live_board_says_which_sports_have_a_live_model():
    """Empty means two different things, and one of them is 'never' (lib/liveSports.ts)."""
    src = _read(PICKS)
    assert "hasLiveModel(sport)" in src, (
        "the live empty state no longer distinguishes a sport with no in-play "
        "model -- 'an in-play model finds an edge' is a promise NBA cannot keep"
    )
    assert "liveModelSportsSentence()" in src, (
        "nothing names the sports that do have a live lane, so a permanently "
        "empty board gives the reader nowhere to go"
    )


def test_the_live_sports_constant_matches_the_python_registry():
    """The app's live-lane list is pinned to config.py, like lib/thresholds.ts.

    Two sources, because the NFL in-play lane is its own worker: config.LIVE_MODELS
    carries the MLB and NCAAF lanes the generic live scorer runs, and
    nfl/live_model/config.MODEL_IDS carries the NFL one.
    """
    import config  # noqa: PLC0415
    from live_model import config as nfl_live_config  # noqa: PLC0415

    expected = {sport for sport, *_ in config.LIVE_MODELS.values()}
    if nfl_live_config.MODEL_IDS:
        expected.add("NFL")

    src = _read(MOBILE / "src" / "lib" / "liveSports.ts")
    m = re.search(r"LIVE_MODEL_SPORTS[^=]*=\s*new Set\(\[([^\]]*)\]\)", src)
    assert m, "LIVE_MODEL_SPORTS is not a literal Set in lib/liveSports.ts"
    actual = {s.strip().strip("'\"") for s in m.group(1).split(",") if s.strip()}
    assert actual == expected, (
        f"the app thinks {sorted(actual)} have in-play models; the Python "
        f"registry says {sorted(expected)}. A live lane shipped (or retired) and "
        "the app's Live Signals empty state is now lying about it."
    )


def test_all_three_segments_are_unconditional():
    """Since 2026-09-12 none of the three is allowed a render guard."""
    src = _read(PICKS)
    for label in ("Today", "Signals"):
        m = re.search(rf'<SubTabBtn label="{label}"', src)
        assert m, f"the {label} segment disappeared"
        preceding = src[max(0, m.start() - 120) : m.start()]
        assert "length > 0 ?" not in preceding, f"the {label} segment became conditional"


def test_nothing_moves_the_reader_off_the_live_board():
    """Neither a sport switch nor the last game ending may change the view.

    Both used to, and both had to while the segment was conditional: the board
    was about to disappear from under the reader. It does not disappear any more,
    so a setView() on either path is a screen that changes boards on its own --
    the thing 2026-09-06 removed the TAB for, inverted.
    """
    src = _read(PICKS)
    # The sport-change reset: filter and search only.
    m = re.search(r"useEffect\(\(\) => \{\s*setFilter\(freshFilter\(\)\);(.*?)\}, \[sport\]\);", src, re.S)
    assert m, "the sport-change reset effect is gone"
    assert "setView" not in m.group(1), (
        "the sport-change effect moves the reader's view again; Live Signals "
        "exists on every sport now, so there is nothing to eject them from"
    )
    # The board emptying out: a toast, not a redirect.
    m = re.search(r"const prevLiveCount = useRef<number \| null>\(null\);(.*?)\}, \[view, liveLoading, liveData\.length\]\);", src, re.S)
    assert m, "the live-board-emptied effect no longer tracks the previous count"
    assert "setView" not in m.group(1), (
        "the last game ending moves the reader back to Today again"
    )
    assert "showToast" in m.group(1), (
        "the board now empties in silence, which reads as a glitch -- say the "
        "games finished"
    )
    assert "prev !== null && prev > 0" in m.group(1), (
        "the toast is no longer gated on the something-to-zero transition: it "
        "will fire on arrival at an already-empty board, and again on every poll"
    )


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


def test_a_sport_switch_cannot_report_a_game_finishing():
    """`liveData` is sport-scoped; the toast's memory must be too.

    Found by the UX review on the 2026-09-12 change: the sport-change effect no
    longer resets the view, so a reader on 3 MLB live picks who taps NBA went
    3 -> 0 and was told "Last in-play game finished". With the board empty ~81% of
    the clock, and 100% of it on the sports with no live lane, that false report
    was the USUAL outcome of a sport tap from the live board.
    """
    src = _read(PICKS)
    m = re.search(
        r"useEffect\(\(\) => \{\s*setFilter\(freshFilter\(\)\);(.*?)\}, \[sport\]\);", src, re.S
    )
    assert m, "the sport-change reset effect is gone"
    assert "prevLiveCount.current = null" in m.group(1), (
        "a sport switch no longer forgets the previous sport's live count, so it "
        "will report a game finishing that did not finish"
    )


def test_the_empty_live_board_does_not_blink_to_a_spinner():
    """An empty live board is the ORDINARY state now, and it is polled every 30s.

    `refresh()` sets loading on every poll, so a reader parked on an empty board
    watched the empty state swap for an ActivityIndicator twice a minute. Invisible
    while the segment was conditional (it always had rows); the dominant experience
    the moment it became permanent (UX review, 2026-09-12).
    """
    src = _read(PICKS)
    assert re.search(
        r"const liveFirstLoad = liveLoading && prevLiveCount\.current === null;", src
    ), "the live spinner is not restricted to the first load"
    assert re.search(r"const busy = view === 'live' \? liveFirstLoad : loading;", src), (
        "the live board's busy flag is back on every poll"
    )
    # ... and pull-to-refresh must still spin, which it can no longer read off `busy`.
    assert "setPulling(true)" in src and "refreshing={view === 'live' ? pulling : busy}" in src, (
        "pull-to-refresh on the live board no longer shows the reader anything"
    )


def test_the_paywall_card_never_replaces_the_live_empty_state():
    """SignalLockCard is for picks that EXIST and are hidden, not for an empty board.

    At count 0 it says the models "haven't found a bet that clears the line yet
    today" -- on a sport with no in-play model that is a promise the app cannot
    keep, which is the sentence lib/liveSports.ts exists to prevent, and it pitches
    a trial on a board that is structurally empty there (UX review, 2026-09-12).
    """
    src = _read(PICKS)
    assert re.search(
        r"\{signalsLocked && !\(view === 'live' && liveData\.length === 0\) \?", src
    ), "an unentitled reader gets the paywall card instead of the live empty state"


def test_the_selected_segment_can_be_scrolled_into_view():
    """The row is longer than the screen at large text sizes, and a deep link can
    select a segment that is off it -- a control with nothing selected reads as a
    rendering bug (UX review, 2026-09-12)."""
    src = _read(PICKS)
    assert "subTabsScroll" in src, "the segment scroller lost its trailing gutter"
    assert "segmentsRef.current?.scrollTo(" in src, (
        "the selected segment is no longer scrolled into view"
    )
    # Measured, not assumed: the labels scale with Dynamic Type.
    assert "onSegmentLayout" in src, "segment offsets are not measured"


def test_the_two_signal_counts_are_not_presented_as_a_subset():
    """Signals and Live Signals are DISJOINT: fetchPicksForDate excludes is_live.

    So `Signals (3)` beside `Live Signals (2)` is five standing bets, not two of
    three, and the reader it misleads is the one adding up exposure.
    """
    src = _read(PICKS)
    assert "pre-game signals" in src, (
        "the Signals subtitle no longer says it is the pre-game board"
    )
    assert "the two boards never hold the same pick" in src, (
        "nothing tells the reader the two signal counts are disjoint"
    )


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
    # Every component App.tsx mounts OUTSIDE <NavigationContainer>. Add one here
    # when you mount one; that is the whole membership rule.
    roots = [
        src_dir / "components" / "BetslipBar.tsx",
        src_dir / "hooks" / "usePushDeepLink.ts",
    ]
    for root in roots:
        assert root.exists(), f"{root} moved -- re-point this test"

    def strip_comments(src: str) -> str:
        """Blank out comments, keeping line count so offsets stay meaningful.

        Only CODE can call a hook. Prose is where these rules get discussed --
        the files that obey this one explain why in their own headers -- so
        matching comments reports the compliant file as the offender.
        """
        src = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), src, flags=re.S)
        return "\n".join(
            "" if line.strip().startswith("//") else line for line in src.splitlines()
        )

    def symbol_bodies(path: Path) -> dict[str, str]:
        """Top-level function declarations in a module, by name.

        Body = source from the declaration to the next top-level declaration,
        which is coarse but never UNDER-reports a call, so it cannot make this
        test pass by missing something.
        """
        src = strip_comments(_read(path))
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
        for names, spec in re.findall(
            r"import (?:type )?\{([^}]+)\} from '@/([^']+)'", _read(path)
        ):
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
    stack = [(root, name) for root in roots for name in symbol_bodies(root)]
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
        r"\{view === 'live' && liveData\.length > 0 \? \(\s*<View style=\{styles\.liveNoteWrap\}>(.*?)\)\s*:\s*null\}",
        src,
        re.S,
    )
    assert m, (
        "the live caveat is not gated on BOTH the live view and there being live "
        "picks. It describes the staleness of prices on screen, so above an empty "
        "board it is a warning about prices that do not exist (UX review, "
        "2026-09-12) -- and on a sport with no live model it sits above an empty "
        "state saying exactly that."
    )
    assert "DraftKings only" in m.group(1)


def test_the_caveat_does_not_reintroduce_the_your_sportsbook_contradiction():
    """One paragraph, not two: a prior UX review removed "bet your sportsbook's
    number" sitting beside "your sportsbook doesn't apply"."""
    src = _read(PICKS)
    m = re.search(r"styles\.liveNoteWrap\}>(.*?)</View>", src, re.S)
    assert m, "live caveat block not found"
    assert "your sportsbook" not in m.group(1).lower()
