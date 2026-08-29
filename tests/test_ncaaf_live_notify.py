"""
The NCAAF live worker must notify, not just write.

ncaaf_live/gameday.py is a SEPARATE live loop from models/live_scorer.py (the
MLB in-play loop). The MLB one calls notify_live_signals + notify_discord_live
after writing; this one never got that hook, so from the day it shipped every
NCAAF live BET reached the app and NOTHING else -- push_sent had zero
'discord_live' rows, ever. Reported 2026-08-29: "I am seeing them in the app"
but not in Discord.

These pin the hook, and the four properties that keep it from doing harm.
"""
from __future__ import annotations

import ast
import logging
import sys
import types

import pytest


# _load_write_picks() swaps four real modules out of sys.modules and cannot put
# them back itself — it returns a function the caller goes on using, so the
# stubs have to outlive it. Left in place they leak into every LATER test in the
# session: the data.db stub's get_connection() hands back a connection whose
# fetchone() is always None, which silently defeated the existing-pick lock in
# test_nfl_opener.py::test_existing_pick_locks_out_reinsert and the guarded
# insert in test_nfl_line_snapshots.py. Both pass in isolation and failed only
# in a full-suite run, which is the worst shape of test pollution — it makes the
# suite order-dependent and quietly weakens every test that comes after.
_STUBBED_MODULES = ("tracking.push_notifier", "tracking.discord_notifier",
                    "data.db", "models.scorer", "config")


@pytest.fixture(autouse=True)
def _restore_stubbed_modules():
    saved = {n: sys.modules.get(n) for n in _STUBBED_MODULES}
    try:
        yield
    finally:
        for name, mod in saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod


def _load_write_picks(calls: list, fail: bool = False, locked_lanes=()):
    """Exec write_picks() out of gameday.py against stubbed collaborators.

    The module imports the live engine and CFBD clients at import time, so the
    function is lifted out rather than importing the module.
    """
    def _push(target_date, dry_run):
        if fail:
            raise RuntimeError("push down")
        calls.append(("push", target_date))

    def _discord(target_date, dry_run):
        if fail:
            raise RuntimeError("webhook down")
        calls.append(("discord", target_date))

    pn = types.ModuleType("tracking.push_notifier")
    pn.notify_live_signals = _push
    dn = types.ModuleType("tracking.discord_notifier")
    dn.notify_discord_live = _discord

    class _Conn:
        def execute(self, *a, **k):
            return types.SimpleNamespace(fetchone=lambda: None, fetchall=lambda: [])
        def commit(self): pass
        def close(self): pass

    ddb = types.ModuleType("data.db")
    ddb.get_connection = lambda: _Conn()
    sc = types.ModuleType("models.scorer")
    sc._insert_picks = lambda conn, picks: None
    # #265 made write_picks import the first-signal lock. Without these the
    # whole file fails at ImportError, which is how it sat broken in isolation.
    sc._locked_live_lanes = lambda conn, game_id, model_ids: set(locked_lanes)
    cfg = types.ModuleType("config")
    cfg.LOCK_LIVE_PICKS_AT_FIRST_SIGNAL = True

    for name, mod in (("tracking.push_notifier", pn),
                      ("tracking.discord_notifier", dn),
                      ("data.db", ddb), ("models.scorer", sc),
                      ("config", cfg)):
        sys.modules[name] = mod

    tree = ast.parse(open("ncaaf_live/gameday.py").read())
    fn = [n for n in tree.body
          if isinstance(n, ast.FunctionDef) and n.name == "write_picks"]
    assert fn, "write_picks not found in ncaaf_live/gameday.py"
    ns = {"log": logging.getLogger("test"),
          "LIVE_MODEL_IDS": ("ncaaf_live_win_prob", "ncaaf_live_total")}
    exec(compile(ast.Module(body=fn, type_ignores=[]), "<gd>", "exec"), ns)
    return ns["write_picks"]


BET = {"signal_type": "BET", "model_id": "ncaaf_live_total",
       "game_date": "2026-08-29", "pick_label": "NC @ TCU Over 46.5 (live)",
       "model_probability": 0.663, "edge": 0.139, "dk_odds": -110.0}
AVOID = {**BET, "signal_type": "AVOID", "pick_label": "NC @ TCU Under 46.5 (live)"}


def test_a_live_bet_notifies_push_and_discord():
    """The bug: this worker wrote picks and told nobody."""
    calls: list = []
    _load_write_picks(calls)([BET, AVOID], "NCAAF_x", dry_run=False)
    assert calls == [("push", "2026-08-29"), ("discord", "2026-08-29")]


def test_the_slate_date_comes_from_the_picks():
    """Both notifiers query `picks WHERE game_date = target_date`, so a wrong
    date is a silent no-op rather than an error."""
    calls: list = []
    _load_write_picks(calls)([{**BET, "game_date": "2026-09-05"}], "g", dry_run=False)
    assert [d for _, d in calls] == ["2026-09-05", "2026-09-05"]


def test_avoid_only_notifies_nothing():
    """A fade is not an actionable bet; the live board is BET-only."""
    calls: list = []
    _load_write_picks(calls)([AVOID], "NCAAF_x", dry_run=False)
    assert calls == []


def test_dry_run_notifies_nothing():
    calls: list = []
    _load_write_picks(calls)([BET], "NCAAF_x", dry_run=True)
    assert calls == []


def test_a_failing_notifier_never_breaks_pricing():
    """Separate try blocks, and neither may take down the loop -- a broken
    webhook must not stop NCAAF from being priced."""
    calls: list = []
    write_picks = _load_write_picks(calls, fail=True)
    write_picks([BET], "NCAAF_x", dry_run=False)   # must not raise
    assert calls == []


def test_restore_fixture_covers_every_stubbed_module():
    """
    The loader and the restore fixture must name the SAME modules. A fifth stub
    added to one and not the other silently reintroduces the leak, and the
    symptom would again land in an unrelated test file.
    """
    import inspect
    import re
    src = inspect.getsource(_load_write_picks)
    stubbed = set(re.findall(r'types\.ModuleType\("([\w.]+)"\)', src))
    assert stubbed, "could not find the stubbed module names"
    assert stubbed <= set(_STUBBED_MODULES), (
        f"not restored after the test: {sorted(stubbed - set(_STUBBED_MODULES))}")


# ── The first-signal lock changed what "there is a bet" means ────────────────
#
# #265 locks a lane at its first live BET: later passes neither delete nor
# re-insert it. The engine still re-prices from scratch every ~45s, so it can
# stop emitting a BET on that side while a LOCKED bet of record is standing.
# Gating notification on "this pass produced a BET" was right before the lock
# and became a hole after it — a signal not yet delivered (webhook added
# mid-game, a 5xx, or the KeyError that meant delivery had never once worked)
# would never be retried for the rest of the game.

def test_a_locked_lane_keeps_notifying_after_the_engine_stops_betting():
    """THE hole. Lane locked, this pass prices only an AVOID -> still notify."""
    calls: list = []
    write_picks = _load_write_picks(calls, locked_lanes=("ncaaf_live_total",))
    write_picks([AVOID], "NCAAF_x", dry_run=False)
    assert calls == [("push", "2026-08-29"), ("discord", "2026-08-29")]


def test_a_locked_lane_is_not_rewritten():
    """The lock's own contract: a locked lane is excluded from the insert."""
    written: list = []
    calls: list = []
    write_picks = _load_write_picks(calls, locked_lanes=("ncaaf_live_total",))
    sys.modules["models.scorer"]._insert_picks = lambda c, p: written.extend(p)
    write_picks([BET], "NCAAF_x", dry_run=False)
    assert written == []


def test_no_picks_at_all_notifies_nothing():
    """An empty pass must not index picks[0] — and has no date to pass anyway."""
    calls: list = []
    _load_write_picks(calls, locked_lanes=("ncaaf_live_total",))([], "g", False)
    assert calls == []


def test_dry_run_still_notifies_nothing_when_a_lane_is_locked():
    calls: list = []
    _load_write_picks(calls, locked_lanes=("ncaaf_live_total",))([BET], "g", True)
    assert calls == []
