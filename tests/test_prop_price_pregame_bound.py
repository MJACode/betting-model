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
returns False for an unknown or unparseable start time -- deliberately, so the
morning pipeline can still score games whose start has not been ingested --
and that is exactly the case this bound covers. The guard here is structural:
it holds even when the caller's does not.

AND THE BOUND IS NOT commence_time (2026-09-03, second pass). The scheduled
start is late: over 415 MLB games with live-state coverage the first `Live`
snapshot lands a mean 18.7 minutes BEFORE it, and only 8 games began after it.
So bounding on the schedule treats a quarter-hour of genuinely in-play quotes
as pre-game -- and on the 30 most recent MLB games with coverage, 1,926 of
3,919 player+market keys (49%) had their "pre-game" price taken from inside
that window. The lanes pass `_pregame_cutoff_map`'s
COALESCE(first_pitch_at, commence_time) instead, and the tests below fail if
any of them goes back to the schedule map.
"""

import ast
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import scorer
from data.first_pitch import pregame_cutoff_sql
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


def test_get_prop_dk_odds_forwards_the_cutoff(monkeypatch):
    """The wrapper must thread it through -- both on the exact-name path and
    on the accented-spelling fallback."""
    seen = []

    def _spy(conn, game_id, player_name, market, pregame_cutoff=None):
        seen.append(pregame_cutoff)
        return PREGAME_ROW

    monkeypatch.setattr(scorer, "_latest_dk_prop_row", _spy)
    _get_prop_dk_odds(_StubConn(), "MLB_x", "Nick Kurtz", "batter_hits",
                      COMMENCE)
    assert seen == [COMMENCE], seen


# The maps that hold a PRE-GAME CUTOFF, and the maps that hold the SCHEDULED
# start. The distinction is the whole point of this file's second pass: the
# schedule maps still exist and are still correct for what they do -- they
# supply the commence_time STAMPED on each pick -- so a call site that reaches
# for one is a plausible edit, not an obvious mistake.
CUTOFF_MAPS   = {"cut_map": "_pregame_cutoff_map",
                 "cutoffs": "_nfl_pregame_cutoff_map"}
SCHEDULE_MAPS = {"ct_map", "kickoffs"}


def _prop_scorers(tree):
    """Every function that prices a prop, with its assignments resolved."""
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        calls = [c for c in ast.walk(node)
                 if isinstance(c, ast.Call)
                 and getattr(c.func, "id", "") == "_get_prop_dk_odds"]
        if calls:
            yield node, calls


def _assigned_from(node):
    """{name: the function it was assigned from} for simple call assignments."""
    out = {}
    for n in ast.walk(node):
        if not isinstance(n, ast.Assign):
            continue
        for t in n.targets:
            if isinstance(t, ast.Name):
                out[t.id] = (getattr(n.value.func, "id", "")
                             if isinstance(n.value, ast.Call) else None)
    return out


def test_every_scorer_call_site_passes_a_pregame_cutoff():
    """A source guard, so a new prop scorer cannot silently drop the argument
    and reopen this. Each call must pass 5 args, and the 5th must be a lookup
    of a CUTOFF map assigned in the same function from _pregame_cutoff_map.

    Passing a literal None would type-check and quietly restore the unbounded
    read; passing ct_map or kickoffs would type-check, look right, and quietly
    restore the ~19-minute leak. Both are rejected by name.
    """
    tree = ast.parse(io.open(SCORER_SRC, encoding="utf-8").read())
    checked = 0
    for node, calls in _prop_scorers(tree):
        assigned = _assigned_from(node)
        for call in calls:
            assert len(call.args) >= 5, (
                f"{node.name}:{call.lineno} does not pass a pre-game cutoff")
            arg = ast.unparse(call.args[4])
            assert arg != "None", (
                f"{node.name}:{call.lineno} passes a literal None")
            base = arg.split(".")[0]
            assert base not in SCHEDULE_MAPS, (
                f"{node.name}:{call.lineno} bounds the price on {base!r}, the "
                f"SCHEDULED start. Use the cutoff map: the schedule runs a "
                f"mean 18.7 minutes late and 49% of keys price inside that "
                f"window.")
            assert base in CUTOFF_MAPS, (
                f"{node.name}:{call.lineno} passes {arg!r}, which is not one "
                f"of the known cutoff maps {sorted(CUTOFF_MAPS)}")
            assert assigned.get(base) == CUTOFF_MAPS[base], (
                f"{node.name}:{call.lineno} passes {base!r}, but it is not "
                f"assigned from {CUTOFF_MAPS[base]}() in that function")
            checked += 1
    assert checked >= 5, f"expected every prop scorer to be covered, saw {checked}"


def test_the_started_game_guard_uses_the_cutoff_too():
    """_game_started decides whether the lane runs at all. Left on the
    schedule it would keep scoring for the ~19 minutes after a game has
    actually begun -- the same leak, one step earlier."""
    tree = ast.parse(io.open(SCORER_SRC, encoding="utf-8").read())
    checked = 0
    for node, _ in _prop_scorers(tree):
        for call in ast.walk(node):
            if not (isinstance(call, ast.Call)
                    and getattr(call.func, "id", "") == "_game_started"):
                continue
            base = ast.unparse(call.args[0]).split(".")[0]
            assert base in CUTOFF_MAPS, (
                f"{node.name}:{call.lineno} guards on {base!r}, not a cutoff map")
            checked += 1
    assert checked >= 5, f"expected a guard in every prop lane, saw {checked}"


def test_the_stamped_commence_time_is_still_the_schedule():
    """The other half, and the one a careless fix breaks: `commence_time` on a
    pick is what the app shows and what the board sorts by, so it must stay
    the SCHEDULED start even though the price is bounded on the actual one."""
    tree = ast.parse(io.open(SCORER_SRC, encoding="utf-8").read())
    checked = 0
    for node, _ in _prop_scorers(tree):
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            for kw in call.keywords:
                if kw.arg != "commence_time":
                    continue
                base = ast.unparse(kw.value).split(".")[0]
                assert base in SCHEDULE_MAPS, (
                    f"{node.name}:{call.lineno} stamps commence_time from "
                    f"{base!r}; the pick must carry the scheduled start")
                checked += 1
    assert checked >= 5, f"expected stamped picks in every lane, saw {checked}"


def test_the_cutoff_map_coalesces_rather_than_swapping():
    """first_pitch_at is NULL for every game before 2026-07-22 and for every
    sport but MLB, so a plain swap would drop the bound (and with it seventeen
    seasons of history) everywhere it is not populated."""
    src = io.open(SCORER_SRC, encoding="utf-8").read()
    body = src[src.index("def _pregame_cutoff_map"):src.index("def _game_started")]
    assert "pregame_cutoff_sql(" in body, (
        "build the bound from data.first_pitch.pregame_cutoff_sql so the "
        "definition cannot drift from the other readers")
    sql = pregame_cutoff_sql("g")
    assert sql.startswith("COALESCE(CASE WHEN g.first_pitch_at"), sql
    assert sql.endswith("END, g.commence_time)"), sql


def test_the_nfl_cutoff_map_left_joins():
    """64 of 3,300 NFL slates have no `games` row at all. An INNER JOIN would
    drop them, and a game with no cutoff loses its started-game guard."""
    src = io.open(SCORER_SRC, encoding="utf-8").read()
    body = src[src.index("def _nfl_pregame_cutoff_map"):]
    body = body[:body.index("\ndef ", 10)]
    assert "LEFT JOIN games g" in body, body
    # The clamp, spelled out because the two timestamps span two tables and
    # pregame_cutoff_sql takes one alias. Same rule, same constant.
    assert "THEN g.first_pitch_at END" in body, body
    assert "SUSPICIOUS_EARLY_MINUTES" in body, body
    assert "s.commence_time) AS cutoff" in body, body
