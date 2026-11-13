"""The pruner keeps the CLOSING non-DK snapshot, not just the opener.

mike, 2026-09-03: "keep one non-dk snapshot per day." Until then a settled
game's only surviving line-shop row was the OPENER, and an opener cannot answer
either question the retained history exists for — the best price available at
DECISION time (Stage 2's re-sweep, for propositions that never got a scored
row) or "did the best book beat DK at close?".

Pruned rows are gone permanently, so these assert the SQL keeps what it claims
before it is ever run against production. Source-level: prune_table builds one
statement per tier and the keep-set is the part that must not regress.

The close is bounded on the game's start (2026-10-26, mike approved: "2)
yes"). It was the last row TYPED pre-game, and the evening refresh writes
`open` rows after the start, so on the 44 NCAAF games of 2026-10-24 FanDuel
kept a post-start "close" on every game and a price from the last hour before
kickoff on none. The behavioural cases below run the real statement on the
SQLite stand-in.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data import prune_odds as po  # noqa: E402
from tests.test_prune_bounded import GAME_COLS, ODDS_COLS, PROP_COLS, StandIn  # noqa: E402

SRC = (Path(__file__).parent.parent / "data" / "prune_odds.py").read_text(
    encoding="utf-8")

# The statement prune_table sends, with the protected predicate left as a
# marker so the tests can see where it lands.
DOOMED = po.doomed_sql("odds", ("game_id", "market"), "%(game_day)s", "<<PRUNABLE>>")


def _game(conn: StandIn, game: str, day: str, commence: str | None = None,
          first_pitch: str | None = None) -> None:
    conn.db.execute(f"INSERT INTO games ({', '.join(GAME_COLS)}) VALUES (?, 'MLB', ?, ?, ?)",
                    (game, day, commence, first_pitch))


def _quotes(conn: StandIn, game: str, day: str, rows, commence: str | None = None,
            first_pitch: str | None = None) -> None:
    """rows: (odds_id, snapshot_type, hour). No commence: the close falls open
    to the pre-game-typed rule."""
    _game(conn, game, day, commence, first_pitch)
    for oid, stype, hour in rows:
        conn.db.execute(
            f"INSERT INTO odds ({', '.join(ODDS_COLS)}) VALUES "
            f"(?, ?, 'MLB', 'h2h', 'fanduel', ?, ?, -110, 100, NULL, NULL, NULL, "
            f"NULL, NULL, NULL)", (oid, game, stype, f"{day}T{hour:02d}:00:00Z"))


def _prune(conn: StandIn, today: str = "2026-10-20") -> None:
    po.prune_table(conn, "odds", ("game_id", "market"), "%(game_day)s", 2, today,
                   budget=po.Budget(seconds=60, rows=10**9), floor="2026-10-01")


def test_the_close_is_selected_by_the_newest_snapshot():
    assert "ORDER BY snapshot_at DESC" in DOOMED
    assert "rn_last = 1" in DOOMED


def test_the_opener_is_still_selected_by_the_oldest():
    """The 2026-08-25 rule this is layered on top of, not a replacement for."""
    assert "ORDER BY snapshot_at ASC" in DOOMED
    assert "rn_first = 1" in DOOMED


def test_the_close_is_never_an_in_play_price():
    """An in-play row is a different proposition (CLAUDE.md §6). Keeping one as
    'the close' hands every later analysis a price from the third inning.

    The DESC ranking is partitioned BY the close flag (pre-game typed, and
    since 2026-10-26 at or before the start), so rn_last = 1 AND is_close is
    the newest CANDIDATE row — not the newest row that happens to be one,
    which is what an unpartitioned ranking would give.
    """
    assert f"PARTITION BY game_id, market, bookmaker, {po._IS_CLOSE}" in DOOMED, (
        "the DESC ranking is not scoped to close candidates, so a proposition "
        "whose newest row is in-play keeps nothing pre-game at all")
    assert po._IS_PRE in po._IS_CLOSE, "a close candidate must be pre-game typed"
    assert "is_close AND rn_last = 1" in DOOMED
    assert "snapshot_type IS NULL" in po._IS_PRE, (
        "NULL snapshot_type must count as pre-game — every reader treats it "
        "that way, and excluding it would keep nothing for older rows")
    conn = StandIn()
    _quotes(conn, "G", "2026-10-10", [(1, "open", 1), (2, "open", 2), (3, "open", 3),
                                      (4, "in_play", 4), (5, "in_play", 5)])
    _prune(conn)
    assert conn.ids("odds") == {1, 3}, "the close must be the newest PRE-GAME row"


def test_both_delete_tiers_spare_the_keep_set():
    """Tier 1 (settled games past the window) and tier 2 (superseded rows
    inside it) both delete, so both must spare the opener and the close.
    Sparing it in one tier only means the other deletes it a day later."""
    assert "WHERE NOT (rn_first = 1 OR (is_close AND rn_last = 1))" in DOOMED
    conn = StandIn()
    _quotes(conn, "OLD", "2026-10-10", [(1, "open", 1), (2, "open", 2), (3, "open", 3),
                                        (4, "in_play", 4)])
    _quotes(conn, "WIN", "2026-10-19", [(11, "open", 1), (12, "open", 2), (13, "open", 3),
                                        (14, "in_play", 4)])
    _prune(conn)
    assert {1, 3} <= conn.ids("odds"), "tier 1 deleted the opener or the close"
    assert {11, 13} <= conn.ids("odds"), "tier 2 deleted the opener or the close"


def test_each_statement_reads_its_proposition_once_with_no_anti_join():
    """PERFORMANCE IS CORRECTNESS HERE. A version that added a SECOND `NOT IN`
    beside the opener's stopped completing (`canceling statement due to
    statement timeout`), and the whole-table version later timed out every
    day. A pruner that times out prunes nothing, and the growth it exists to
    bound is silent. Every keep rule rides on ONE read of one proposition.
    """
    assert DOOMED.count("FROM odds") == 1
    assert "NOT IN (" not in DOOMED
    delete = po.delete_sql("odds", ("game_id", "market"), "%(game_day)s", "<<PRUNABLE>>")
    assert delete.count("FROM odds") == 2          # the DELETE and its one read
    # The window is computed once and the DELETE looks those ids up by primary
    # key. A proposition predicate on the DELETE makes Postgres re-run the
    # scan once per doomed id (2026-10-21: 4,819 ids, 8.5 s, and the form
    # with the window inside that loop was cancelled at statement_timeout).
    assert "AS MATERIALIZED" in delete
    tail = delete.split("DELETE FROM", 1)[1]
    assert "game_id" not in tail
    assert tail.strip().startswith("odds WHERE odds_id IN (SELECT odds_id FROM doomed)")


def test_the_protected_books_are_untouched_by_this_change():
    """draftkings and sbr_consensus were never prunable and must stay that way;
    the close is an addition to what SURVIVES, never a widening of what is
    deleted."""
    assert 'PROTECTED_BOOKMAKERS = (ODDS_API_BOOKMAKER, "sbr_consensus")' in SRC
    assert "AND <<PRUNABLE>>" in DOOMED, (
        "the statement lost the protected-bookmaker predicate")


def test_the_cost_is_recorded_as_a_measurement_not_a_guess():
    """§1b: never estimate what you can measure. The retention decision was
    made on a real row count, and the next person changing it needs the same
    number rather than the old ~2.7 GB/month comment that counted one table."""
    assert "297,975" in SRC and "105,105" in SRC, (
        "the measured daily row counts behind this decision are gone")
    assert "+6 MB/day" in SRC


# ── the close is bounded on the game's start (2026-10-26) ────────────────────
# Every game below is on 2026-10-10 (Tier 1 for a 2026-10-20 run) unless it
# says otherwise. Rows are stamped `{day}T{hour}:00:00Z`; the start times use
# '+00:00', the shape 44 of 2026-10-24's NCAAF commence_times carry, so a
# text comparison would get the row exactly at the start wrong.

def test_the_close_is_bounded_on_the_game_s_cutoff_in_the_sql():
    """One join, one read: the cutoff comes from data.first_pitch (the one
    definition every pre-game read shares), keyed on the statement's own game,
    and the comparison is cast, never text."""
    from data.first_pitch import pregame_cutoff_sql
    assert pregame_cutoff_sql("g") in DOOMED
    assert "FROM games g WHERE g.game_id = %(game_id)s" in DOOMED
    assert "b.close_by IS NULL OR snapshot_at::timestamptz <= b.close_by" in po._IS_CLOSE
    assert DOOMED.count("LEFT JOIN") == 1


def test_open_rows_after_the_start_are_not_the_close():
    """The bug: `open` rows written after the start won the DESC ranking. The
    close is now the last pre-game row at or before the start."""
    conn = StandIn()
    _quotes(conn, "G", "2026-10-10", [(i, "open", i) for i in range(1, 7)],
            commence="2026-10-10T03:30:00+00:00")
    _prune(conn)
    assert conn.ids("odds") == {1, 3}


def test_a_row_exactly_at_the_start_is_the_close():
    """`<=`, and cast: '2026-10-10T03:00:00Z' sorts after
    '2026-10-10T03:00:00+00:00' as text, though they are the same instant."""
    conn = StandIn()
    _quotes(conn, "G", "2026-10-10", [(i, "open", i) for i in range(1, 7)],
            commence="2026-10-10T03:00:00+00:00")
    _prune(conn)
    assert conn.ids("odds") == {1, 3}


def test_no_start_time_keeps_the_pre_game_typed_rule():
    """A NULL commence_time fails open to the rule before this change: the
    newest pre-game-typed row, wherever it sits."""
    conn = StandIn()
    _quotes(conn, "G", "2026-10-10", [(1, "open", 1), (2, "open", 2), (3, "open", 5),
                                      (4, "in_play", 6)])
    _prune(conn)
    assert conn.ids("odds") == {1, 3}


def test_a_game_quoted_only_after_its_start_keeps_its_opener_and_no_close():
    """Every pre-game-typed row is after the start, so none is a close. The
    opener still ranks every row and survives."""
    conn = StandIn()
    _quotes(conn, "G", "2026-10-10", [(1, "open", 2), (2, "open", 3), (3, "open", 4),
                                      (4, "in_play", 5)],
            commence="2026-10-10T01:00:00+00:00")
    _prune(conn)
    assert conn.ids("odds") == {1}


def test_a_trusted_first_pitch_bounds_the_close():
    """data.first_pitch: a derived first pitch up to an hour before the
    scheduled start is believed, and then it, not the schedule, is the start."""
    conn = StandIn()
    _quotes(conn, "G", "2026-10-10", [(i, "open", i) for i in range(1, 7)],
            commence="2026-10-10T04:00:00+00:00",
            first_pitch="2026-10-10T03:00:00+00:00")       # exactly 60 min early
    _prune(conn)
    assert conn.ids("odds") == {1, 3}


def test_a_first_pitch_more_than_an_hour_early_is_ignored():
    """More than 60 minutes before the schedule is a wrong match (the
    doubleheader case in data.first_pitch), so the schedule bounds the close."""
    conn = StandIn()
    _quotes(conn, "G", "2026-10-10", [(i, "open", i) for i in range(1, 7)],
            commence="2026-10-10T04:00:00+00:00",
            first_pitch="2026-10-10T02:59:00+00:00")       # 61 min early
    _prune(conn)
    assert conn.ids("odds") == {1, 4}


def test_tier_2_keeps_the_newest_row_even_after_the_start():
    """The live all-books views return the newest row, so Tier 2 keeps it
    wherever it sits; only the close is bounded. Inside the window the
    survivors are exactly the opener, the last row at or before the start, and
    the newest."""
    conn = StandIn()
    _quotes(conn, "WIN", "2026-10-19", [(i, "open", i) for i in range(1, 7)],
            commence="2026-10-19T03:00:00+00:00")
    _prune(conn)
    assert conn.ids("odds") == {1, 3, 6}


def _props(conn: StandIn, game: str, day: str, rows, commence: str | None = None,
           first_pitch: str | None = None) -> None:
    """rows: (prop_id, snapshot_type, hour), one proposition at fanduel."""
    _game(conn, game, day, commence, first_pitch)
    for pid, stype, hour in rows:
        conn.db.execute(
            f"INSERT INTO player_prop_odds ({', '.join(PROP_COLS)}) VALUES "
            f"(?, ?, ?, 'Ann', 'player_points', 'fanduel', ?, ?, 20.5, -110)",
            (pid, game, day, stype, f"{day}T{hour:02d}:00:00Z"))


def _prune_props(conn: StandIn, today: str = "2026-10-20") -> None:
    po.prune_table(conn, "player_prop_odds", ("game_id", "market", "player_name"),
                   "game_date", 2, today, budget=po.Budget(seconds=60, rows=10**9),
                   floor="2026-10-01")


def test_the_prop_table_s_close_is_bounded_the_same_way():
    """player_prop_odds goes through the same statement: post-start `open`
    rows are not the close, a trusted first pitch bounds it, and with no start
    time the old rule holds."""
    conn = StandIn()
    rows = [(i, "open", i) for i in range(1, 7)]
    _props(conn, "P1", "2026-10-10", rows, commence="2026-10-10T03:30:00+00:00")
    _props(conn, "P2", "2026-10-11", [(10 + i, t, h) for i, t, h in rows],
           commence="2026-10-11T05:00:00+00:00", first_pitch="2026-10-11T04:15:00+00:00")
    _props(conn, "P3", "2026-10-12", [(20 + i, t, h) for i, t, h in rows])
    _props(conn, "P4", "2026-10-19", [(30 + i, t, h) for i, t, h in rows],
           commence="2026-10-19T02:00:00+00:00")
    _prune_props(conn)
    assert conn.ids("player_prop_odds") == {1, 3, 11, 14, 21, 26, 31, 32, 36}


def test_no_literal_percent_sign_reaches_psycopg2():
    """psycopg2 %-interpolates every prune statement, so a literal percent
    sign in the SQL (a LIKE pattern, a modulo) raises before Postgres sees it,
    and the SQLite stand-in, which renders parameters by hand, would never
    notice. Python's % formatting reads the string the same way."""
    class Any(dict):
        def __missing__(self, key):
            return "x"
    for table, identity, row_date in po._TABLES:
        for build in (po.doomed_sql, po.delete_sql, po.count_sql):
            sql = build(table, identity, row_date, po._unprotected({}, table))
            sql % Any()                      # raises on a stray percent sign
