"""A tapped notification lands on the thing it is about.

2026-09-06 (matt: "build it"). Until now `push_notifier` sent no `data` on any
message and the app installed no notification-response listener, so tapping a
push opened whatever screen the user had last been on. For a live pick — a
number the board itself labels as up to ~45s stale — that is the whole value of
the notification lost at the final step.

WHAT IS PINNED HERE

1. EVERY PRODUCER SENDS A PAYLOAD. A message without `data` is a tap with
   nowhere to go, and the failure is silent: the app opens, so it looks like it
   worked.

2. THE TWO HALVES AGREE ON A VERSION. The worker deploys on merge; the app
   reaches phones by OTA and an old build can sit on a phone for months, so the
   contract is versioned and the app ignores what it cannot read. If the two
   constants drift, every tap silently stops routing — the exact failure the
   version exists to make safe.

3. SPORT IS ONLY SENT WHEN IT IS UNAMBIGUOUS. The board shows ONE sport at a
   time, so switching sport on a push that spanned MLB and NCAAF would hide half
   of what it was announcing, with nothing on screen to say so.

4. THE APP HANDLES THE COLD-START TAP. A response that LAUNCHED the app is never
   delivered to a listener — it is only retrievable from
   getLastNotificationResponseAsync(). Handling only the listener works in every
   test (where the app is already open) and fails for the user tapping a
   notification on a locked phone, which is the normal case.

NOT PINNED, AND IT MATTERS: none of this can be proven end to end from here.
`device_push_tokens` was EMPTY when this was written, and the producers ledger
into `push_sent` whether or not any device exists ("Ledger regardless of token
count"), so the 1,158 new_bet and 578 live_signal rows are marks, not
deliveries. No push has ever reached a phone. See the PR.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NOTIFIER = ROOT / "tracking" / "push_notifier.py"
ROUTE_TS = ROOT / "mobile" / "src" / "lib" / "pushRoute.ts"
HOOK_TS = ROOT / "mobile" / "src" / "hooks" / "usePushDeepLink.ts"
APP_TSX = ROOT / "mobile" / "App.tsx"


def _read(p: Path) -> str:
    # Explicit encoding: cp1252 is the Windows default and this repo's source is
    # full of box-drawing characters (CLAUDE.md §7).
    return p.read_text(encoding="utf-8")


def _code(p: Path) -> str:
    """Source with comments blanked out.

    These files EXPLAIN the calls they must make, so a plain substring test is
    satisfied by the prose alone -- caught when deleting the cold-start call
    left the test green. CLAUDE.md: a guard dead code can satisfy is not a
    guard.
    """
    src = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"),
                 _read(p), flags=re.S)
    return "\n".join(
        "" if line.strip().startswith("//") else line for line in src.splitlines()
    )


# ── 1. the sender ─────────────────────────────────────────────────────────────


def test_every_expo_message_carries_a_data_payload():
    """No message may be built without `data` — a tap needs somewhere to go."""
    src = _read(NOTIFIER)
    # Every dict literal that names an Expo recipient is a message.
    messages = re.findall(r"\{[^{}]*\"to\":[^{}]*\}", src, re.S)
    assert messages, "no Expo message literals found — has the shape changed?"
    missing = [m for m in messages if '"data"' not in m]
    assert not missing, (
        f"{len(missing)} push message(s) carry no data payload, so a tap on them "
        f"cannot route: {missing}"
    )


def test_the_route_helper_only_sets_sport_when_it_is_unambiguous():
    from tracking.push_notifier import _route, _shared_sport

    assert _shared_sport([{"sport": "MLB"}, {"sport": "MLB"}]) == "MLB"
    assert _shared_sport([{"sport": "MLB"}, {"sport": "NCAAF"}]) is None
    assert _shared_sport([]) is None
    assert _shared_sport([{"sport": None}]) is None

    spanning = _route("new_bets", [{"sport": "MLB"}, {"sport": "NCAAF"}])
    assert "sport" not in spanning, (
        "a push spanning sports must not switch the board's sport — it would "
        "hide the half it did not choose"
    )


def test_every_summary_producer_can_deep_link_a_single_pick():
    """Two pushes of the same shape must not behave differently.

    _dropped_signals had no pick_id, so a one-pick "moved past the bet line"
    push dumped the reader on the whole Today board to find it while the
    identical new_bets push opened the pick (UX review, 2026-09-06).
    """
    src = _read(NOTIFIER)
    for fn in ("_new_bet_signals", "_dropped_signals", "_new_live_signals"):
        body = re.search(rf"def {fn}\(.*?\n\n\n", src, re.S)
        assert body, f"{fn} not found"
        assert '"pick_id"' in body.group(0), (
            f"{fn} does not carry pick_id, so its single-pick push cannot "
            "deep-link the way the other producers' do"
        )


def test_a_single_pick_deep_links_and_a_batch_does_not():
    from tracking.push_notifier import _route

    one = _route("live_signals", [{"sport": "NCAAF", "pick_id": 42}])
    assert one["pickId"] == 42
    assert one["sport"] == "NCAAF"

    many = _route("live_signals", [{"sport": "NCAAF", "pick_id": 42},
                                   {"sport": "NCAAF", "pick_id": 43}])
    assert "pickId" not in many, "a summary of several picks must open the board"
    assert many["sport"] == "NCAAF"

    # A pick with no id must not fabricate one.
    assert "pickId" not in _route("new_bets", [{"sport": "MLB", "pick_id": None}])


def test_the_line_change_glyph_matches_its_direction():
    """The glyph is read before the sentence on a lock screen.

    📈 on "moved against you" says the opposite of the alert, on the push with
    the shortest reaction window (UX review, 2026-09-06).
    """
    src = _read(NOTIFIER)
    assert "f\"{'📉' if a['against'] else '📈'} Line {arrow}\"" in src, (
        "the line-change title uses one glyph for both directions"
    )


def test_the_line_change_push_carries_the_pick_it_is_about():
    """It is always one tracked bet, so it can always open that bet."""
    src = _read(NOTIFIER)
    m = re.search(r"\"title\": f\"\{'📉'.*?\}\)", src, re.S)
    assert m, "the line-change message literal moved"
    assert '"pickId": a["pick_id"]' in m.group(0)
    # ...and the alert dict must actually carry it, or that is a KeyError in
    # production on a code path no test exercises.
    alert = re.search(r"alerts\.append\(\{(.*?)\}\)", src, re.S)
    assert alert and '"pick_id": pick_id' in alert.group(1), (
        "_line_change_alerts does not put pick_id on the alert it builds"
    )


def test_the_feedback_push_carries_a_thread_id_not_a_message_id():
    """The app routes on threadId; m.id is the MESSAGE and would 404 the screen."""
    src = _read(NOTIFIER)
    assert '"threadId": r["thread_id"]' in src
    rows = re.search(r"def _unpushed_feedback_replies.*?\} for r in rows\]", src, re.S)
    assert rows and '"thread_id": r[5]' in rows.group(0)
    assert "SELECT m.id, t.device_id, d.token, t.subject, m.body, t.id" in src


# ── 2. the contract between the two halves ────────────────────────────────────


def _py_version() -> int:
    m = re.search(r"^PUSH_ROUTE_VERSION = (\d+)", _read(NOTIFIER), re.M)
    assert m, "PUSH_ROUTE_VERSION missing from push_notifier.py"
    return int(m.group(1))


def _ts_version() -> int:
    m = re.search(r"export const PUSH_ROUTE_VERSION = (\d+)", _read(ROUTE_TS))
    assert m, "PUSH_ROUTE_VERSION missing from pushRoute.ts"
    return int(m.group(1))


def test_both_halves_pin_the_same_payload_version():
    """Drift here silently stops every tap routing, which is what `v` prevents."""
    assert _py_version() == _ts_version(), (
        f"push_notifier.py sends v={_py_version()} but the app only accepts "
        f"v={_ts_version()} — every tap would fall through to 'just open the app'"
    )


def test_every_type_the_sender_emits_is_one_the_app_can_route():
    sender_types = set(re.findall(r"_route\(\"(\w+)\"", _read(NOTIFIER)))
    sender_types |= set(re.findall(r"\"type\": \"(\w+)\"", _read(NOTIFIER)))
    app = _read(ROUTE_TS)
    app_types = set(re.findall(r"^\s{2}(\w+): '(?:today|signals|live)',", app, re.M))
    app_types |= set(re.findall(r"type === '(\w+)'", app))
    unroutable = sender_types - app_types
    assert not unroutable, (
        f"the sender emits push types the app cannot route: {sorted(unroutable)}"
    )


# ── 3. the app half ───────────────────────────────────────────────────────────


def test_the_app_handles_the_cold_start_tap():
    """A tap that LAUNCHES the app never reaches a listener."""
    src = _code(HOOK_TS)
    assert "getLastNotificationResponseAsync" in src, (
        "only the response LISTENER is handled, so a notification tapped while "
        "the app is closed opens the app and goes nowhere — and it works in "
        "every test, because there the app is already running"
    )
    assert "addNotificationResponseReceivedListener" in src

    # ...and the effect that fetches it must MOUNT ONCE. `ready` always goes
    # false -> true on launch (onReady fires after the first render), so an
    # effect that depends on it is guaranteed one teardown -- which used to
    # cancel the in-flight cold-start lookup while a once-guard stopped it
    # being retried. The launch tap was dropped on essentially every cold
    # start, and the warm path worked, so nothing on a dev phone showed it.
    m = re.search(r"getLastNotificationResponseAsync.*?\}, (\[[^\]]*\])\);", src, re.S)
    assert m, "the subscribe effect's dependency array moved"
    assert m.group(1).strip() == "[]", (
        f"the notification-response effect depends on {m.group(1)}; it must be "
        "[] or its teardown cancels the launch tap it exists to handle"
    )

    # The cold-start call belongs inside the same try as the listener: without a
    # native module the property access throws synchronously, past .catch.
    body = re.search(r"try \{(.*?)\} catch", src, re.S)
    assert body and "getLastNotificationResponseAsync" in body.group(1), (
        "the cold-start native call sits outside the try that guards the "
        "listener -- a launch crash on a build without expo-notifications"
    )


def test_the_router_is_mounted_at_the_app_root():
    src = _code(APP_TSX)
    assert "usePushDeepLink(navRef" in src, "the deep-link hook is not mounted"
    assert "onReady={onNavReady}" in src, (
        "the navigator's ready signal is not wired, so a cold-start route "
        "resolved before the container mounts is dropped"
    )


def test_the_deep_link_hook_avoids_use_focus_effect():
    """It is mounted outside NavigationContainer, where useNavigation() throws.

    Same rule that a crash in the Live-segment change put in
    .claude/rules/frontend.md. The comments in that file discuss the hook on
    purpose, so only CODE is checked -- and the transitive version of this lives
    in tests/test_mobile_live_segment.py, which walks the import graph from
    every app-root component.
    """
    assert "useFocusEffect" not in _code(HOOK_TS)


def test_an_unreadable_payload_routes_nowhere_rather_than_guessing():
    src = _code(ROUTE_TS)
    assert re.search(r"if \(d\.v !== PUSH_ROUTE_VERSION\) return null;", src), (
        "a payload from a newer sender must resolve to null (just open the "
        "app), never to a guessed destination"
    )
    for guard in ("data == null", "typeof data !== 'object'"):
        assert guard in src, f"missing guard: {guard}"


def test_the_board_route_switches_sport_before_navigating():
    """Navigating first shows the wrong sport's picks, then swaps under the reader."""
    src = _code(HOOK_TS)
    m = re.search(r"case 'board':(.*?)return;", src, re.S)
    assert m, "the board branch moved"
    body = m.group(1)
    set_at = body.index("setSportForVisit")
    nav_at = body.index("navRef.navigate")
    assert set_at < nav_at, "the sport switch must precede the navigate"


def test_the_sport_setter_is_callable_outside_react():
    """The router runs from a notification callback, with no component around it."""
    src = _read(ROOT / "mobile" / "src" / "hooks" / "useSportFilter.ts")
    assert re.search(r"export function setSportForVisit\(", src), (
        "setSportForVisit is gone — the push router cannot set the sport from a "
        "non-component callback without it"
    )
