"""One pick, one publishing key — and two picks are never one key.

THE BUG (2026-09-09, found auditing "do the NFL bets line up with Discord?").
The key every publishing surface identifies a pick by was
`game_id:model_id[:player_id]`. `push_sent(lock_key, kind)` is UNIQUE, so two
picks sharing a key are ONE pick to Discord, to push, and to the CLV shadow
track — and the second is not delayed, it is gone, because the first one's
ledger row answers "already announced" forever.

`nfl_prop_market` shares no identity with the rest of the repo: it writes
`player_key` (a name slug) and `prop_market`, and leaves `player_id` NULL. So
every prop it picked in one game collapsed onto `<game_id>:nfl_prop_market`.

Measured against production before the fix: 8 eligible BETs, 7 ledgered keys.
`Sam Darnold Under 19.5 Comp (MGM)` — written 2026-09-09 08:26 ET for that
night's NE @ SEA kickoff — was on the app's board and could never reach Discord
or a phone, because `Jadarian Price Over 1.5 Rec (FD)` had taken the key the
morning before. That is CLAUDE.md §1b broken in a new place: not an extra gate
this time, an identity too coarse to tell two bets apart.

WHAT THESE TESTS PIN, and why each one is separate:

  * two propositions -> two keys        (the bug itself)
  * player_id-only rows keep the OLD key BYTE FOR BYTE (nothing republishes;
    this is the property that let the fix ship without re-announcing 119 picks)
  * pick_side stays OUT of the key      (§1c: a side flip is ONE bet of record)
  * every producer mints it from the shared helper, and the DISTINCT ON matches
    the key it dedupes toward — a partition coarser than the key drops rows
    before the ledger is ever consulted, which is the same bug one layer up.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tracking import discord_notifier as dn
from tracking import opening_signals as osig
from tracking import push_notifier as pn
from tracking.publish_keys import (
    KEY_PARTS, key_partition_sql, live_lock_key, live_lock_key_sql, lock_key_sql,
)


# ── the key, evaluated as Python so the property is checked, not the string ──

def _key(row: dict) -> str:
    """`lock_key_sql` applied to one row, by the same rule Postgres applies:
    `COALESCE(':' || x, '')` is '' when x IS NULL, else ':' + x."""
    out = f"{row['game_id']}:{row['model_id']}"
    for part in KEY_PARTS:
        v = row.get(part)
        if v is not None:
            out += f":{v}"
    return out


_PRICE = {"game_id": "NFL_2026_01_NE_SEA", "model_id": "nfl_prop_market",
          "player_id": None, "player_key": "jadarianprice",
          "prop_market": "player_receptions", "pick_side": "over"}
_DARNOLD = {"game_id": "NFL_2026_01_NE_SEA", "model_id": "nfl_prop_market",
            "player_id": None, "player_key": "samdarnold",
            "prop_market": "player_pass_completions", "pick_side": "under"}
_DOWNS_REC = {"game_id": "NFL_2026_01_MIA_LV", "model_id": "nfl_prop_receptions",
              "player_id": "00-0038997", "player_key": None,
              "prop_market": None, "pick_side": "under"}


def test_two_propositions_in_one_game_are_two_keys():
    """The measured failure: these two shared a key, so only one ever posted."""
    assert _key(_PRICE) != _key(_DARNOLD), (
        "two nfl_prop_market picks in one game still collapse to one key — the "
        "second one can never reach Discord or a phone")


def test_the_same_player_on_two_markets_is_two_keys():
    """`nfl_prop_market` is ONE model covering EVERY market, unlike the eleven
    distributional models (one model per market, so player alone was enough).
    A quarterback with a completions pick and a pass-yards pick is two bets."""
    comp = dict(_DARNOLD)
    yards = dict(_DARNOLD, prop_market="player_pass_yards")
    assert _key(comp) != _key(yards)


def test_a_player_id_row_keeps_the_key_it_was_published_under():
    """THE PROPERTY THAT LET THIS SHIP.

    Every row ledgered before 2026-09-09 — every sport, every game-level model,
    every distributional prop model — carries player_id and neither of the new
    components. Its key must be byte-identical to the old expression, or the
    first pass after deploy re-announces the entire published history.

    Verified against production the same way before applying: of every ledgered
    key, `nfl_prop_market`'s were the only ones that moved.
    """
    old = (f"{_DOWNS_REC['game_id']}:{_DOWNS_REC['model_id']}"
           f":{_DOWNS_REC['player_id']}")
    assert _key(_DOWNS_REC) == old


def test_a_game_level_row_keeps_the_key_it_was_published_under():
    """Same property with every component NULL — the opener and wind cards."""
    row = {"game_id": "NFL_2026_01_CLE_JAX", "model_id": "nfl_opener_spread",
           "player_id": None, "player_key": None, "prop_market": None}
    assert _key(row) == "NFL_2026_01_CLE_JAX:nfl_opener_spread"


def test_pick_side_is_not_in_the_key():
    """§1c, and it must stay this way. The key is deliberately COARSER than the
    `picks` unique row: a pre-#311 side flip has to collapse to the one bet of
    record, not announce both halves of it. Adding pick_side here would look
    like more precision and would publish the same game twice."""
    assert "pick_side" not in KEY_PARTS
    flipped = dict(_PRICE, pick_side="under")
    assert _key(flipped) == _key(_PRICE)


# ── every producer mints it the same way ─────────────────────────────────────

class _Conn:
    def __init__(self):
        self.sql = None

    def execute(self, sql, params=None):
        self.sql = sql
        return self

    def fetchall(self):
        return []

    def fetchone(self):
        return (0,)

    def commit(self):
        pass


def _sql(producer, *args):
    conn = _Conn()
    producer(conn, *args)
    return conn.sql


def test_every_publisher_mints_the_key_from_the_shared_helper():
    """A hand-rolled copy is how the surfaces drifted in the first place."""
    for sql in (_sql(dn._new_signals, "2026-09-09"),
                _sql(dn._locked_signals, "2026-09-09"),
                _sql(pn._new_bet_signals, "2026-09-09"),
                _sql(pn._dropped_signals, "2026-09-09")):
        assert lock_key_sql() in sql


def test_the_restate_delete_path_resolves_the_same_key():
    """`_delete_posted` joins push_sent back to picks to find the message a
    restatement replaces. Joined on a key the poster no longer mints, it finds
    nothing and leaves the stale post standing next to its correction — the
    worst of the three outcomes, and the one nobody goes looking for.

    Read from the SOURCE, not by calling it: `_delete_posted` returns before it
    reaches the query when no webhook is configured, which is every test run.
    """
    import inspect
    src = inspect.getsource(dn._delete_posted)
    assert "{lock_key_sql()}" in src or lock_key_sql() in src


def test_capture_mints_the_same_key_as_the_publishers():
    """`opening_signals` has `ON CONFLICT (lock_key) DO NOTHING`, so a coarse
    key there silently drops the second proposition from the CLV track too —
    measured: 8 prop_market BETs, 7 shadow rows."""
    import inspect
    src = inspect.getsource(osig.capture_opening_signals)
    assert "{lock_key_sql()}" in src or lock_key_sql() in src, (
        "capture must build its key from tracking.publish_keys")


def test_the_distinct_on_is_never_coarser_than_the_key():
    """A partition coarser than the key drops the row before the ledger sees
    it, so the ledger backfill cannot save it. They must move together."""
    for sql in (_sql(dn._new_signals, "2026-09-09"),
                _sql(dn._locked_signals, "2026-09-09"),
                _sql(pn._new_bet_signals, "2026-09-09")):
        assert f"DISTINCT ON ({key_partition_sql()})" in sql
    for part in KEY_PARTS:
        assert f"COALESCE(p.{part}, '')" in key_partition_sql(), (
            f"{part} is in the key but not in the DISTINCT ON")


# ── a voided pick is not publishable ─────────────────────────────────────────

def test_no_publisher_announces_a_voided_pick():
    """CLAUDE.md §1c: a VOIDED row is a pick the model should never have
    produced, kept as evidence and stopped from counting. The six Week 1 wind
    picks were voided on 2026-09-07 and removed from Discord BY HAND, and
    nothing carried that to the app — so all six were still drawing as green
    BETs on the 09-13 board. Both halves of the fix are pinned: this one, and
    `passesActionFilter` in mobile/src/lib/thresholds.ts.

    Only 'VOID'. scripts/nfl_pick_monitor.py writes 'OK' / 'DEGRADED' / 'GONE'
    in the same column as health states on real, STANDING picks (NCAAF does not
    use it at all — a downgraded NCAAF row carries `downgrade_reason`), so
    filtering on anything but 'VOID' would withdraw live bets.
    """
    for sql in (_sql(dn._new_signals, "2026-09-09"),
                _sql(dn._locked_signals, "2026-09-09"),
                _sql(pn._new_bet_signals, "2026-09-09")):
        assert ("p.condition_status IS NULL OR p.condition_status <> 'VOID'"
                in sql)
        # Compared against, not merely mentioned — the comment above the clause
        # names both of NCAAF's states on purpose.
        for healthy in ("'GONE'", "'DEGRADED'", "'OK'"):
            assert f"condition_status <> {healthy}" not in sql
            assert f"condition_status = {healthy}" not in sql


def _mobile(path: str) -> str:
    src = __file__.rsplit("tests", 1)[0] + "mobile/src/" + path
    with open(src, encoding="utf-8") as fh:      # §7: explicit encoding
        return fh.read()


def test_the_app_refuses_a_voided_pick_too():
    """The app is the other half. A server-side exclusion alone would just
    reverse which surface shows the extra rows."""
    body = _mobile("lib/thresholds.ts")
    body = body[body.index("export function passesActionFilter"):]
    body = body[:body.index("\n}")]
    assert re.search(r"condition_status\s*===\s*'VOID'", body), (
        "passesActionFilter must refuse a VOIDED row, or the app shows picks "
        "Discord does not")


def test_the_app_excludes_a_voided_pick_AT_THE_SOURCE():
    """A SEPARATE test from the one above, and the one that matters.

    passesActionFilter is called by five of the app's surfaces and NOT by the
    others. Found by the UX review on this branch's first draft: with only the
    filter fixed, the Today segment, both model screens, the Stats odds pill and
    the betslip hand-off all still drew the six voided wind picks as green,
    stakeable BET cards, while the header count directly above them excluded
    them. That is the retired-model bug of 2026-09-02 exactly, and
    `useTodayPicks` already carries its fix and the comment explaining it.

    This is `.claude/rules/frontend.md`'s blind-spot rule in miniature: the
    filter-only test above passed the whole time the board was wrong. So pin the
    SOURCE filter — the one every consumer inherits — not just the helper.
    """
    hook = _mobile("hooks/useTodayPicks.ts")
    body = hook[hook.index("const all = ["):]
    body = body[:body.index(");")]
    assert "condition_status !== 'VOID'" in body, (
        "the VOID exclusion must sit beside isModelRetired in useTodayPicks, "
        "or every consumer that does not call passesActionFilter still renders "
        "a voided pick as a live BET")
    assert "isModelRetired" in body, "the retired guard must survive beside it"


def test_the_live_board_excludes_a_voided_pick_too():
    """`scripts/void_picks.py` takes any --model and the publishers' exclusion
    is unconditional across sports, so a voided LIVE pick would drop out of
    Discord and stay on the Live tab. The live read never calls
    passesActionFilter at all — it filters in SQL."""
    q = _mobile("lib/queries.ts")
    body = q[q.index("export async function fetchLivePicks("):]
    body = body[:body.index("\n}")]
    assert "condition_status.neq.VOID" in body


# ── The LIVE key (mike, 2026-09-09: "Fix it now") ────────────────────────────
# The in-play producers keyed on game:model:side with no player, so a second
# quarterback's pass-attempt over -- or a second batter's hits over -- in the
# same game could never announce. Same fix as the pre-game key, same
# guarantees, pinned the same way.

_OLD_LIVE_EXPR = "'live:' || p.game_id || ':' || p.model_id || ':' || p.pick_side"


class _KeyConn:
    def __init__(self, rows): self._rows = rows
    def execute(self, sql, params=None):
        self._sql = sql
        return self
    def fetchall(self): return self._rows


def test_two_players_in_one_live_game_are_two_live_keys():
    a = live_lock_key("NFL_2026_01_NE_SEA", "nfl_live_prop", "over",
                      "cj-stroud", "cj-stroud", "player_pass_attempts")
    b = live_lock_key("NFL_2026_01_NE_SEA", "nfl_live_prop", "over",
                      "sam-darnold", "sam-darnold", "player_pass_attempts")
    assert a != b
    assert a.startswith("live:NFL_2026_01_NE_SEA:nfl_live_prop:over:")


def test_a_game_level_live_row_keeps_the_key_it_was_published_under():
    """Every ledgered discord_live row belongs to a game-level model (measured
    2026-09-09: 172 of 172). Their key must not move by a byte, or every
    standing live bet republishes into a paid channel."""
    assert live_lock_key("NCAAF_2026-08-29_north-carolina_tcu",
                         "ncaaf_live_total", "over") == \
        "live:NCAAF_2026-08-29_north-carolina_tcu:ncaaf_live_total:over"


def test_the_live_sql_is_the_old_expression_plus_the_player_tail():
    """The SQL and the Python helper are two spellings of one key. The SQL
    must START with the exact old expression, so a NULL-player row COALESCEs
    to the old string, and carry every KEY_PARTS column after it."""
    sql = live_lock_key_sql()
    assert sql.startswith(_OLD_LIVE_EXPR)
    for c in KEY_PARTS:
        assert f"COALESCE(':' || p.{c}, '')" in sql
    assert sql.index("player_id") < sql.index("player_key") < sql.index("prop_market")


@pytest.mark.parametrize("producer", [dn._new_live_signals, pn._new_live_signals])
def test_both_live_producers_mint_and_check_the_shared_live_key(producer):
    """The NOT EXISTS lookup and the projected lock_key must be the SAME
    expression, in both producers -- a lookup on the old key with a projection
    of the new one would ledger under a key it never checks."""
    conn = _KeyConn([])
    producer(conn, "2026-09-09")
    assert conn._sql.count(live_lock_key_sql()) == 2, \
        "the live key must appear as the projection AND the ledger lookup"
    assert _OLD_LIVE_EXPR + "\n" not in conn._sql.replace(live_lock_key_sql(), ""), \
        "no bare old-key expression may survive beside the shared one"


def test_the_live_producers_return_the_projected_key_not_a_rebuilt_one():
    """A Python f-string rebuilding the key from three columns is how the
    player component got lost. The dict must carry the column the query
    projected."""
    key = "live:G:nfl_live_prop:over:cj-stroud:cj-stroud:player_pass_attempts"
    row = ("G", "nfl_live_prop", "over", "C.J. Stroud Over 32.5 Pass Attempts",
           None, "NFL", 42, key)
    assert pn._new_live_signals(_KeyConn([row]), "2026-09-09")[0]["lock_key"] == key
    drow = ("G", "nfl_live_prop", "over", "C.J. Stroud Over 32.5 Pass Attempts",
            "NFL", 0.6, 0.07, -115.0, 0.011, None, None, "SEA", "NE",
            "2026-09-10T00:20:00Z", "2026-09-10T01:00:00+00:00", 0.0, -140, key)
    assert dn._new_live_signals(_KeyConn([drow]), "2026-09-09")[0]["lock_key"] == key


def test_the_first_signal_repair_clears_the_shared_live_key():
    src = (Path(__file__).parent.parent / "tracking" / "first_signal_repair.py").read_text(encoding="utf-8")
    assert "live_lock_key(" in src
    assert 'f"live:{' not in src
