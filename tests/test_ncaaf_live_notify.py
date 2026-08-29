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


def _load_write_picks(calls: list, fail: bool = False):
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

    for name, mod in (("tracking.push_notifier", pn),
                      ("tracking.discord_notifier", dn),
                      ("data.db", ddb), ("models.scorer", sc)):
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
