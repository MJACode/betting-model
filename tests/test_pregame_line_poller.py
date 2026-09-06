"""
The 30-second pre-game watcher: it must only write what moved, and it must
never empty the board.

Two properties carry this module, and they pull in opposite directions.

WRITE ONLY ON CHANGE is what makes 30 seconds affordable at all. Measured over
39,146 pre-game observations, 95% of polls find DK's number unchanged; writing
every poll would turn ~33k audit rows a day into ~2.25M and grow a 5 GB
database by ~634 MB every day. But an unseen quote must count as changed — a
brand-new game's opener is the most valuable number in the system, and treating
"unknown" as "unchanged" would silently skip every opener.

NEVER EMPTY THE BOARD is the trap a partial re-score sets. The scorer's
housekeeping DELETEs are scoped to the whole look-ahead WINDOW, while the
scoring loop only re-inserts for the games it was given. Run unscoped against a
subset, they clear every game's rows and refill a handful — and §7's rule is
that an empty board and a broken pipeline look identical.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402
from data.ingestors.pregame_line_poller import (  # noqa: E402
    PRICE_COLS, changed_rows, over_credit_cap,
)

_SCORER_SRC = (Path(__file__).parent.parent / "models" / "scorer.py").read_text(
    encoding="utf-8")


def _row(game_id="MLB_2026-08-30_NYY_BOS", market="h2h", **over):
    r = {"game_id": game_id, "market": market,
         "bookmaker": config.ODDS_API_BOOKMAKER, "snapshot_type": "open"}
    for c in PRICE_COLS:
        r[c] = None
    r.update(over)
    return r


# ── write only on change ──────────────────────────────────────────────────────

def test_an_unchanged_quote_is_not_written():
    row = _row(home_price=-150, away_price=130)
    known = {("MLB_2026-08-30_NYY_BOS", "h2h"): (-150.0, 130.0, None, None, None, None, None)}
    to_write, moved = changed_rows([row], known)
    assert to_write == [] and moved == set()


def test_a_moved_price_is_written_and_marks_its_game():
    row = _row(home_price=-165, away_price=140)
    known = {("MLB_2026-08-30_NYY_BOS", "h2h"): (-150.0, 130.0, None, None, None, None, None)}
    to_write, moved = changed_rows([row], known)
    assert len(to_write) == 1
    assert moved == {"MLB_2026-08-30_NYY_BOS"}


def test_a_quote_we_have_never_seen_counts_as_changed():
    """An opener is the most valuable number here — unknown is never unchanged."""
    to_write, moved = changed_rows([_row(home_price=-110)], {})
    assert len(to_write) == 1 and moved == {"MLB_2026-08-30_NYY_BOS"}


def test_text_and_float_forms_of_the_same_price_are_equal():
    """
    `odds` stores prices as TEXT in mixed shapes. A string compare would report
    a change on every single poll and defeat the entire diff — this is the bug
    that would quietly turn a 30s poller back into a full re-score.
    """
    row = _row(home_price="-110.0", total_line="8.5")
    known = {("MLB_2026-08-30_NYY_BOS", "h2h"): (-110.0, None, None, None, 8.5, None, None)}
    assert changed_rows([row], known) == ([], set())


def test_a_moved_total_counts_even_when_the_price_holds():
    row = _row(market="totals", total_line=9.5, over_price=-110, under_price=-110)
    known = {("MLB_2026-08-30_NYY_BOS", "totals"): (None, None, None, None, 8.5, -110.0, -110.0)}
    to_write, _ = changed_rows([row], known)
    assert len(to_write) == 1, "the LINE moving is a change even at the same juice"


def test_a_link_or_selection_id_churning_is_not_a_change():
    """
    Betslip links and DK selection ids rotate without the number moving. Counting
    them would re-score the whole board for nothing, which is the exact cost this
    module exists to avoid.
    """
    row = _row(home_price=-150, home_link="https://dk/new", home_sid="zzz")
    known = {("MLB_2026-08-30_NYY_BOS", "h2h"): (-150.0, None, None, None, None, None, None)}
    assert changed_rows([row], known) == ([], set())


def test_other_books_are_ignored():
    row = _row(home_price=-150)
    row["bookmaker"] = "fanduel"
    assert changed_rows([row], {}) == ([], set())


def test_in_play_rows_are_ignored():
    """The live loop owns that lane; the two must never write the same rows (§6)."""
    row = _row(home_price=-150)
    row["snapshot_type"] = "in_play"
    assert changed_rows([row], {}) == ([], set())


def test_one_moved_game_does_not_drag_in_the_quiet_ones():
    quiet = _row("MLB_2026-08-30_LAD_SF", home_price=-120)
    moved_row = _row("MLB_2026-08-30_NYY_BOS", home_price=-165)
    known = {
        ("MLB_2026-08-30_LAD_SF", "h2h"): (-120.0, None, None, None, None, None, None),
        ("MLB_2026-08-30_NYY_BOS", "h2h"): (-150.0, None, None, None, None, None, None),
    }
    to_write, moved = changed_rows([quiet, moved_row], known)
    assert moved == {"MLB_2026-08-30_NYY_BOS"}
    assert len(to_write) == 1


# ── the credit cap ────────────────────────────────────────────────────────────

def test_the_credit_cap_binds():
    assert over_credit_cap(config.PREGAME_POLL_DAILY_CREDIT_CAP + 1)
    assert not over_credit_cap(0)


def test_a_zero_cap_means_uncapped(monkeypatch):
    monkeypatch.setattr(config, "PREGAME_POLL_DAILY_CREDIT_CAP", 0)
    assert not over_credit_cap(10_000_000)


# The burn this cap has to clear, MEASURED rather than derived. On 2026-09-05
# the poller logged "daily credit cap reached (60000 >= 60000)" at 17:09 ET and
# repeated it on every 30-second tick until midnight; it had run since ~07:00,
# so 60,000 units in ~10 hours is ~6,000/hour and ~144,000 over a full day.
# Units are `api_call_log.credits`, which is what the cap is enforced in.
MEASURED_DAILY_BURN_UNITS = 144_000


def test_the_cap_covers_a_full_day_of_the_measured_burn():
    """
    The old assertion here was `cap > 2,880 sweeps x 13 credits` — a DERIVED
    number from when the poller swept fewer sports. It passed at 60,000 while
    the real loop was hitting that cap at 5pm and going dark for the whole
    evening, which is precisely when NFL, NCAAF and UFC lines cross. A capped
    poller fetches nothing, scores nothing and publishes nothing.

    So the bar is now the measured burn, not a model of it.
    """
    assert config.PREGAME_POLL_DAILY_CREDIT_CAP >= MEASURED_DAILY_BURN_UNITS, (
        "the cap binds before midnight — the poller will stop watching prices, "
        "and stop publishing, part-way through the day")


def test_the_cap_still_bounds_a_runaway_loop():
    """It is a runaway guard, not a budget. Raising it must not remove it."""
    assert 0 < config.PREGAME_POLL_DAILY_CREDIT_CAP <= 4 * MEASURED_DAILY_BURN_UNITS


# ── the board-wipe trap ───────────────────────────────────────────────────────

def _run_scorer_body() -> str:
    """Just run_scorer's source. The prop and golf scorers are separate entry
    points with their own per-model deletes, and the poller never calls them."""
    i = _SCORER_SRC.index("def run_scorer(")
    j = _SCORER_SRC.index("\ndef ", i + 10)
    return _SCORER_SRC[i:j]


def test_every_housekeeping_delete_in_run_scorer_is_scoped_to_the_subset():
    """
    The one that would empty a board. Every window-scoped DELETE in run_scorer
    must carry the subset predicate, or a partial re-score clears each game's
    rows and refills only the handful that moved.

    Counted inside run_scorer ONLY. The first version of this test counted
    `DELETE FROM picks` across the whole module and failed at 11 vs 4 — the
    other seven live in the prop and golf scorers, which take no subset and are
    never called by the poller. Counting them would have forced pointless
    changes to code this feature does not touch.
    """
    body = _run_scorer_body()
    deletes = body.count("DELETE FROM picks")
    # Count the predicate being APPENDED TO THE SQL, not merely assigned.
    # The first version counted the `_sc, _sp = _scope()` assignment and a
    # mutation that deleted only the `+ _sc` from one statement passed it
    # cleanly — the variable was still built, just never used. A guard that
    # can be satisfied by dead code is not a guard.
    applied = body.count('""" + _sc')
    # The postponed-game delete is keyed on a single game_id and needs no scope.
    assert deletes == 5, f"run_scorer gained a DELETE ({deletes}) — scope it too"
    assert applied == deletes - 1, (
        f"{deletes} DELETEs but only {applied} carry the subset predicate in "
        f"their SQL — an unscoped one will empty the board on a partial "
        f"re-score")
    # ...and the params must travel with it, or psycopg2 raises on the bind.
    assert body.count("+ _sp") == applied


def test_the_subset_predicate_never_builds_an_empty_IN_list():
    """`game_id IN ()` is a syntax error; the empty case must short-circuit."""
    body = _run_scorer_body()
    i = body.index("def _scope(")
    assert "AND FALSE" in body[i:i + 700]


def test_the_subset_is_applied_before_the_feature_build():
    """Narrowing after the expensive work would save nothing."""
    narrow = _SCORER_SRC.index("if only_games is not None:")
    assert narrow < _SCORER_SRC.index("ncaaf_unpriced: set = set()")
    assert narrow < _SCORER_SRC.index("# Build features once per game")


def test_an_empty_subset_scores_nothing_rather_than_everything():
    """
    `set()` means "nothing moved" — the common case at 95% no-change. Conflating
    it with None would turn every quiet poll into a full board re-score, which
    is the entire cost this parameter exists to avoid.
    """
    i = _SCORER_SRC.index("def run_scorer(")
    block = _SCORER_SRC[i:i + 2500]
    assert "if only_games is not None and not only_games:" in block
    assert block.index("if only_games is not None and not only_games:") < \
        block.index("conn = get_connection()"), "must return before any DB work"


def test_a_full_board_call_still_passes_no_subset():
    """The daily pipeline and refresh chain must be untouched by this."""
    src = (Path(__file__).parent.parent / "run_pipeline.py").read_text(encoding="utf-8")
    assert "only_games" not in src, (
        "the refresh chain must keep scoring the whole board")


# ── the loop's own safety ─────────────────────────────────────────────────────

def test_the_kill_switch_is_read_every_tick_not_once_at_start():
    """A switch only read at boot cannot stop a loop that is already running."""
    src = (Path(__file__).parent.parent / "data" / "ingestors"
           / "pregame_line_poller.py").read_text(encoding="utf-8")
    body = src[src.index("while True:"):]
    assert "config.RUN_PREGAME_POLLER" in body


def test_a_failed_tick_does_not_kill_the_loop():
    """A stopped poller and a quiet market look identical from the outside."""
    src = (Path(__file__).parent.parent / "data" / "ingestors"
           / "pregame_line_poller.py").read_text(encoding="utf-8")
    body = src[src.index("while True:"):]
    assert "except Exception as exc:" in body
    assert "raise" not in body


def test_the_interval_is_the_one_that_was_costed():
    """30s = ~1.1M credits/month of a 5M reset. Changing it is a spend decision."""
    assert config.PREGAME_POLL_INTERVAL_SEC == 30


def test_nhl_is_not_polled_while_out_of_season():
    """Its per-event 3-way pull 422s on every event — 32 wasted calls a pass."""
    assert "NHL" not in config.PREGAME_POLL_SPORTS


# ── the fingerprint map is seeded, not rebuilt every tick ─────────────────────
#
# last_known_prices() re-reads DK's whole pre-game history for every unstarted
# game -- ~1,525 games, ~142k heap fetches out of a 1.18 GB table. Rebuilding it
# once per 30-second tick made it the single most expensive statement in the
# database: 4,291 calls, 88,398 s total, 20,601 ms mean -- 24.6 HOURS of
# database time (pg_stat_statements, 2026-09-02). With a 20.6 s mean against a
# 30 s interval the loop spent ~69% of every cycle inside it, and at the >60 s
# tail it ran back to back and slept not at all.
#
# The poller already knows what it wrote, so the map only needs SEEDING.

class _PollConn:
    """Counts the fingerprint seeds and records the keys each one asked for.
    Everything else is a no-op."""

    def __init__(self):
        self.seeds = 0
        self.seed_keys: list[list[tuple]] = []

    def execute(self, sql, params=None):
        outer = self
        joined = " ".join(sql.split())
        if "FROM unnest(" in joined and "FROM odds o" in joined:
            outer.seeds += 1
            outer.seed_keys.append(list(zip(params[0], params[1])))

        class C:
            def fetchall(self_inner):
                return []

            def fetchone(self_inner):
                return (0,)
        return C()

    def commit(self):
        pass

    def rollback(self):
        pass


def _quiet_poll(monkeypatch, written=()):
    """poll_once with the network and the scorer stubbed out."""
    import data.ingestors.odds_ingestor as oi
    monkeypatch.setattr(oi, "fetch_pregame_rows", lambda sports: list(written),
                        raising=False)
    monkeypatch.setattr(oi, "_insert_odds", lambda conn, rows: None, raising=False)


def test_a_tick_given_a_map_does_not_rebuild_it(monkeypatch):
    """The whole point: 2,880 rebuilds a day become one per re-seed."""
    from data.ingestors.pregame_line_poller import poll_once
    _quiet_poll(monkeypatch)
    conn = _PollConn()
    known: dict = {}
    poll_once(conn, sports=["MLB"], score=False, known=known)
    poll_once(conn, sports=["MLB"], score=False, known=known)
    poll_once(conn, sports=["MLB"], score=False, known=known)
    assert conn.seeds == 0, (
        f"poll_once rebuilt the fingerprint map {conn.seeds} time(s) despite "
        "being handed one — this is the 24.6-hour query")


def test_a_tick_given_no_map_seeds_the_keys_it_was_quoted(monkeypatch):
    """A one-off call or a test must keep working unchanged -- and the seed it
    runs is for the quoted keys, not the whole table."""
    from data.ingestors.pregame_line_poller import poll_once
    _quiet_poll(monkeypatch, written=[_row(game_id="g1"), _row(game_id="g2", market="totals")])
    conn = _PollConn()
    poll_once(conn, sports=["MLB"], score=False)
    assert conn.seeds == 1
    assert sorted(conn.seed_keys[0]) == [("g1", "h2h"), ("g2", "totals")]


def test_a_tick_with_nothing_quoted_runs_no_seed(monkeypatch):
    """No quotes, nothing to diff, nothing to look up."""
    from data.ingestors.pregame_line_poller import poll_once
    _quiet_poll(monkeypatch)
    conn = _PollConn()
    poll_once(conn, sports=["MLB"], score=False)
    assert conn.seeds == 0


def test_the_seed_asks_only_for_keys_the_map_does_not_hold(monkeypatch):
    """The 24.6-hour query in miniature: a map that already carries a key must
    not send that key back to the database, however often it is quoted."""
    from data.ingestors.pregame_line_poller import poll_once, _key, _fingerprint
    held = _row(game_id="g1")
    new = _row(game_id="g2", market="totals")
    _quiet_poll(monkeypatch, written=[held, new])
    conn = _PollConn()
    known = {_key(held): _fingerprint(held)}
    poll_once(conn, sports=["MLB"], score=False, known=known)
    assert conn.seeds == 1
    assert conn.seed_keys[0] == [("g2", "totals")]
    # Now every quoted key is in the map: the next tick looks nothing up.
    poll_once(conn, sports=["MLB"], score=False, known=known)
    assert conn.seeds == 1


def test_the_seed_is_one_index_probe_per_key_not_a_table_scan():
    """The whole-table DISTINCT ON was a Parallel Seq Scan of the 842 MB odds
    table every re-seed (shared read=88,408 pages), and the app's views timed
    out underneath it 41 times in one minute. The seed must be driven by the
    caller's keys and bounded to one row per key."""
    from data.ingestors.pregame_line_poller import SEED_SQL
    sql = " ".join(SEED_SQL.split())
    assert "FROM unnest(%s::text[], %s::text[]) AS k(game_id, market)" in sql
    assert "DISTINCT ON" not in sql
    assert "ORDER BY o.snapshot_at DESC LIMIT 1" in sql, "not a top-1 probe"
    assert "o.game_id = k.game_id AND o.market = k.market" in sql, \
        "the probe must be keyed on the index's leading columns"
    assert "::timestamptz" not in sql, \
        "a cast defeats idx_odds_book_snap; text order was measured equal"
    assert "o.snapshot_type <> 'in_play'" in sql, "the live lane leaked in"


def test_other_books_and_in_play_quotes_are_never_looked_up():
    from data.ingestors.pregame_line_poller import quoted_keys
    rows = [_row(game_id="g1"), _row(game_id="g2", bookmaker="fanduel"),
            _row(game_id="g3", snapshot_type="in_play")]
    assert quoted_keys(rows) == {("g1", "h2h")}


def test_a_key_the_database_has_never_stored_is_written(monkeypatch):
    """A seed that returns nothing for a key means "never seen", and never
    seen counts as changed -- the opener is the most valuable number here."""
    from data.ingestors.pregame_line_poller import poll_once, _key
    opener = _row(game_id="g9")
    _quiet_poll(monkeypatch, written=[opener])
    conn = _PollConn()                      # its seed returns no rows
    known: dict = {}
    out = poll_once(conn, sports=["MLB"], score=False, known=known)
    assert out["written"] == 1
    assert _key(opener) in known


def test_what_a_tick_writes_lands_in_the_map(monkeypatch):
    """Without this the next tick re-writes the same move forever."""
    from data.ingestors.pregame_line_poller import poll_once, _key, _fingerprint
    moved = _row(home_price="-120")
    _quiet_poll(monkeypatch, written=[moved])
    conn = _PollConn()
    known: dict = {}

    first = poll_once(conn, sports=["MLB"], score=False, known=known)
    assert first["written"] == 1
    assert known[_key(moved)] == _fingerprint(moved)

    # Same quote again: now a no-op, because the map carries what we wrote.
    second = poll_once(conn, sports=["MLB"], score=False, known=known)
    assert second["written"] == 0, "a written price was not remembered"


def test_the_map_is_updated_only_after_the_commit():
    """A failed insert must not leave the map claiming a price the database
    never took — the next tick would see no change and never retry it."""
    src = (Path(__file__).parent.parent / "data" / "ingestors"
           / "pregame_line_poller.py").read_text(encoding="utf-8")
    body = src[src.index("if to_write:"):]
    commit_at = body.index("conn.commit()")
    fold_at = body.index("known[_key(row)]")
    assert commit_at < fold_at, "the map is folded before the commit"


def test_the_loop_reseeds_on_a_bounded_schedule():
    """Two drifts are self-correcting only at a seed: another writer moving a
    price we did not write, and started games left in the map as dead weight."""
    src = (Path(__file__).parent.parent / "data" / "ingestors"
           / "pregame_line_poller.py").read_text(encoding="utf-8")
    body = src[src.index("while True:"):]
    assert "PREGAME_POLL_RESEED_SEC" in body
    # A re-seed is an EMPTY map (the next tick looks its quoted keys up), never
    # a whole-table read.
    reseed = body[body.index("PREGAME_POLL_RESEED_SEC"):body.index("poll_once(conn, known=known)")]
    assert "known = {}" in reseed, "the loop never re-seeds the map at all"
    assert "last_known_prices" not in reseed, "the loop re-reads the whole table"


def test_a_failed_tick_throws_the_map_away():
    """A tick that died mid-write leaves a half-updated map; carrying that
    forward is carrying a guess."""
    src = (Path(__file__).parent.parent / "data" / "ingestors"
           / "pregame_line_poller.py").read_text(encoding="utf-8")
    body = src[src.index("except Exception as exc:"):]
    assert "known = None" in body


def test_the_reseed_interval_is_far_longer_than_the_tick():
    """A re-seed per tick is the bug this replaced."""
    assert config.PREGAME_POLL_RESEED_SEC >= 10 * config.PREGAME_POLL_INTERVAL_SEC
