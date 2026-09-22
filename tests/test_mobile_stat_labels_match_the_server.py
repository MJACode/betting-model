"""The app calls a stat what the server calls it.

THE BUG THIS EXISTS FOR, 2026-09-21. The live NFL prop model changed market from
pass attempts to rushing attempts. Four things were updated -- the model, the
market the worker buys, the market written to `picks.prop_market`, and the
column settlement reads -- and two display strings were left behind. The first
rushing pick published to Discord as "Blake Corum Under 11.5 Pass Attempts": a
running back, on a passing line, with an entirely correct bet underneath it.

A wrong bet is visible. A wrong SENTENCE describing a right bet is not -- the
reader is told a proposition that does not exist and has no way to see the
fields that say otherwise. `tracking/pick_integrity.refuse_mismatched` did not
catch it because it validates the label's SIDE and LINE, not the stat it names.

The Python side is now pinned to itself (tests/test_nfl_live_pick_writer.py ties
`pick_writer` to `models/scorer._NFL_PROP_CONFIG`). That guard stops at the
language boundary, so the app could still drift on the next market switch in
exactly the same way. This is the other half: `mobile/src/lib/modelMeta.ts` is
read as text -- there is no node on this machine to import it -- and the stat
names it declares are checked against the ones the server publishes.

SCOPE. The two RUSHING models, which are the pair that actually bit, plus the
live model's own market. The remaining NFL prop models disagree in smaller ways
that predate this, each an abbreviation of the same stat rather than a
different one. They are not silently exempted: `UNRECONCILED` names all
three, so the set can only shrink deliberately.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
META = ROOT / "mobile" / "src" / "lib" / "modelMeta.ts"

# Known to differ, all three predating the 2026-09-21 switch, and all three a
# shorter ABBREVIATION of the same stat rather than a different stat -- which is
# what separates them from the failure this file exists for:
#
#     nfl_prop_anytime_td        app 'TD'        server 'Anytime TD'
#     nfl_prop_pass_completions  app 'Pass Comp' server 'Comp'
#     nfl_prop_receptions        app 'Recs'      server 'Rec'
#
# Listed rather than skipped: an exception nobody can see is how the rule above
# got broken in the first place (CLAUDE.md section 1b). Reconciling them is a
# one-line-each sweep that needs a decision about which spelling wins, not a
# correctness fix, so it is not bundled with a live mislabel.
UNRECONCILED = {
    "nfl_prop_anytime_td",
    "nfl_prop_pass_completions",
    "nfl_prop_receptions",
}


def _meta_entries() -> dict[str, dict[str, str]]:
    """model id -> its declared string fields, parsed out of the TypeScript.

    Read as TEXT with an explicit encoding: node is not installed on this
    machine (CLAUDE.md section 1b), so the module cannot be imported, and this
    repo's source is full of box-drawing characters.
    """
    src = META.read_text(encoding="utf-8")
    out: dict[str, dict[str, str]] = {}
    for m in re.finditer(r"^\s{2}(\w+):\s*\{(.*?)^\s{2}\},", src,
                         re.DOTALL | re.MULTILINE):
        fields = dict(re.findall(r"(\w+):\s*'([^']*)'", m.group(2)))
        if fields:
            out[m.group(1)] = fields
    return out


def _server_stat_labels() -> dict[str, str]:
    from models.scorer import _NFL_PROP_CONFIG
    return {mid: c["stat_label"] for mid, c in _NFL_PROP_CONFIG.items()}


def test_the_parser_actually_found_the_models():
    """A regex that silently matches nothing turns every assertion below into a
    guard dead code can satisfy."""
    entries = _meta_entries()
    assert len(entries) > 30, f"only parsed {len(entries)} entries"
    assert "nfl_live_prop" in entries
    assert "nfl_prop_rush_attempts" in entries


def test_the_live_model_names_the_market_it_actually_trades():
    """The exact failure: three strings describing a market the model left."""
    from nfl.live_model.models import rush_attempt_pace as rap

    e = _meta_entries()["nfl_live_prop"]
    assert e["statLabel"] == rap.STAT_LABEL, (
        f"the app calls the live model's stat {e['statLabel']!r}; the model "
        f"calls it {rap.STAT_LABEL!r}")
    for field in ("shortLabel", "longLabel", "statLabel"):
        assert "Pass" not in e[field], (
            f"{field} still says {e[field]!r}, and this model stopped trading "
            f"passing attempts on 2026-09-21")


@pytest.mark.parametrize("model_id", ["nfl_prop_rush_attempts", "nfl_live_prop"])
def test_both_rushing_models_call_the_stat_the_same_thing(model_id):
    """One stat, one name. Track Record and the daily recap can show a pre-game
    and a live rushing pick on the same screen."""
    from nfl.live_model.models import rush_attempt_pace as rap

    server = _server_stat_labels()
    expected = server.get(model_id, rap.STAT_LABEL)
    assert _meta_entries()[model_id]["statLabel"] == expected


def test_the_unreconciled_models_are_named():
    """Every NFL prop model whose app label disagrees with the server's is in
    UNRECONCILED, and nothing else is.

    This is deliberately not a skip list. CLAUDE.md section 1b: a rule with a
    standing exception is not a rule, so the divergences are enumerated and the
    set can only shrink -- a NEW one fails here.
    """
    entries, server = _meta_entries(), _server_stat_labels()
    drift = {mid for mid, label in server.items()
             if mid in entries and entries[mid].get("statLabel") != label}
    assert drift == UNRECONCILED, (
        f"newly diverged: {sorted(drift - UNRECONCILED)}; "
        f"now reconciled, remove from UNRECONCILED: "
        f"{sorted(UNRECONCILED - drift)}")
