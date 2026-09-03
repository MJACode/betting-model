"""The prop scorer must price against a PRE-GAME quote, never an in-play one.

mike, 2026-09-03: ship the bound.

WHAT WENT WRONG. `_latest_dk_prop_row` took the newest DraftKings quote for a
player+market with no time bound and no snapshot_type filter. The prop
ingestor keeps snapshotting after first pitch and labels those rows 'open', so
a PRE-GAME model could be handed an IN-PLAY price. That is not a small error:
a pre-game probability read against a live number becomes a large FAKE EDGE,
and a high edge cut selects for it rather than protecting against it.

The worked case, pick 107657 -- "Nick Kurtz Over 0.5 Hits", 2026-05-26:

    01:41Z  first pitch
    ...     DK traded the prop at over -226 / -260 / -246 all day
    01:56Z  DK quotes over +135 -- IN-PLAY, Kurtz has already batted,
            written to player_prop_odds with snapshot_type='open'
    02:57Z  the pick is created and priced at +135

p(over) ~ 0.70 against an implied 0.4255 is a 27pp edge on a proposition that
had none. 46 of mlb_prop_batter_hits' 113 priced BETs fired this way between
2026-05-25 and 2026-06-20 (16-30, -11.18u), carrying +23.92pp of fabricated
CLV -- which is why that model showed the book's best CLV and its worst ROI at
the same time.

WHY THE CALL-SITE GUARD IS NOT ENOUGH. `_game_started()` already skips started
games, and that is what closed the exposure behaviourally in July. But it
returns False for an unknown or unparseable commence_time -- deliberately, so
the morning pipeline can still score games whose start has not been ingested --
and that is exactly the case this bound covers. The guard here is structural:
it holds even when the caller's does not.
"""

import ast
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import scorer
from models.scorer import _get_prop_dk_odds, _latest_dk_prop_row

SCORER_SRC = Path(__file__).parent.parent / "models" / "scorer.py"

# The real DK book for pick 107657. Only the first row is a pre-game quote at
# or before first pitch; the last is the in-play quote that poisoned the pick.
COMMENCE = "2026-05-27T01:41:00+00:00"
PREGAME_ROW = (0.5, -246, 181, None, None)
IN_PLAY_ROW = (0.5, 135, -175, None, None)


class _StubConn:
    """Captures the emitted SQL and params, and answers with whichever row the
    query's own WHERE clause would actually have reached."""

    def __init__(self):
        self.sql = ""
        self.params = ()

    def execute(self, sql, params=None):
        self.sql = " ".join(sql.split())
        self.params = tuple(params or ())
        bounded = "snapshot_at::timestamptz <=" in self.sql
        excludes_in_play = "in_play" in self.sql
        # The in-play row is the NEWEST, so an unbounded query returns it.
        row = PREGAME_ROW if (bounded or excludes_in_play) else IN_PLAY_ROW
        self._row = row
        return self

    def fetchone(self):
        return self._row

    def fetchall(self):
        return []


def test_the_pregame_price_is_returned_not_the_in_play_one():
    """The whole point. Nick Kurtz closes at -246, not +135."""
    conn = _StubConn()
    row = _latest_dk_prop_row(conn, "MLB_x", "Nick Kurtz", "batter_hits",
                              COMMENCE)
    assert row == PREGAME_ROW, (
        f"priced off an in-play quote: got over_price {row[1]}, expected -246"
    )


def test_the_query_is_bounded_on_commence_time_and_casts_both_sides():
    """Bounded, and CAST -- snapshot_at and commence_time are both TEXT in
    mixed shapes ('Z' suffix vs +-HH:MM offset), so a string compare silently
    keeps leaked rows (the §7 lesson)."""
    conn = _StubConn()
    _latest_dk_prop_row(conn, "MLB_x", "Nick Kurtz", "batter_hits", COMMENCE)
    assert "snapshot_at::timestamptz <= %s::timestamptz" in conn.sql, conn.sql
    assert COMMENCE in conn.params


def test_in_play_snapshots_are_excluded_unconditionally():
    conn = _StubConn()
    _latest_dk_prop_row(conn, "MLB_x", "Nick Kurtz", "batter_hits", COMMENCE)
    assert "in_play" in conn.sql, conn.sql


def test_it_fails_open_when_commence_time_is_missing():
    """No start time -> no time bound, so synthetic and SBR historical rows
    survive (§7: guards fail open on a missing timestamp). The in_play
    exclusion still applies, because that one never needs a timestamp."""
    conn = _StubConn()
    _latest_dk_prop_row(conn, "MLB_x", "Nick Kurtz", "batter_hits", None)
    assert "snapshot_at::timestamptz <=" not in conn.sql, conn.sql
    assert "in_play" in conn.sql, conn.sql
    assert conn.params == ("MLB_x", "Nick Kurtz", "batter_hits")


def test_get_prop_dk_odds_forwards_commence_time(monkeypatch):
    """The wrapper must thread it through -- both on the exact-name path and
    on the accented-spelling fallback."""
    seen = []

    def _spy(conn, game_id, player_name, market, commence_time=None):
        seen.append(commence_time)
        return PREGAME_ROW

    monkeypatch.setattr(scorer, "_latest_dk_prop_row", _spy)
    _get_prop_dk_odds(_StubConn(), "MLB_x", "Nick Kurtz", "batter_hits",
                      COMMENCE)
    assert seen == [COMMENCE], seen


def test_every_scorer_call_site_passes_a_start_time():
    """A source guard, so a new prop scorer cannot silently drop the argument
    and reopen this. Each call must pass 5 args, and the 5th must be a lookup
    of a start-time map that is assigned in the same function -- ct_map for the
    dated sports, kickoffs for NFL. Passing a literal None would type-check and
    quietly restore the old behaviour, so it is rejected too.
    """
    tree = ast.parse(io.open(SCORER_SRC, encoding="utf-8").read())
    checked = 0
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        assigned = {t.id for n in ast.walk(node) if isinstance(n, ast.Assign)
                    for t in n.targets if isinstance(t, ast.Name)}
        for call in ast.walk(node):
            if not (isinstance(call, ast.Call)
                    and getattr(call.func, "id", "") == "_get_prop_dk_odds"):
                continue
            assert len(call.args) >= 5, (
                f"{node.name}:{call.lineno} does not pass a start time")
            arg = ast.unparse(call.args[4])
            assert arg != "None", (
                f"{node.name}:{call.lineno} passes a literal None")
            base = arg.split(".")[0]
            assert base in assigned, (
                f"{node.name}:{call.lineno} passes {arg!r}, "
                f"but {base!r} is not assigned in that function")
            checked += 1
    assert checked >= 5, f"expected every prop scorer to be covered, saw {checked}"
