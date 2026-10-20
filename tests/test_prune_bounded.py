"""data/prune_odds: one proposition per statement, same rows kept and deleted.

The whole-table prune stopped completing: every daily run died on the 120 s
statement_timeout (a COUNT over all 31M `odds` rows, then a window over every
prunable row of every past game), and from 2026-09-03 nothing was thinned in
either table. It now runs one proposition per statement, a run at a time,
with progress stored in Supabase.

These run the real SQL on SQLite, the OLD whole-table statements beside the
new ones, and compare what survives. They also pin the bound: no statement the
prune sends can read a table without naming the game it is about.
"""
from __future__ import annotations

import json
import random
import re
import sqlite3

import pytest

from data import prune_odds as po

TODAY = "2026-10-20"
KEEP = 2                                   # cutoff 2026-10-18
ODDS_COLS = ("odds_id", "game_id", "sport", "market", "bookmaker", "snapshot_type",
             "snapshot_at", "home_price", "away_price", "draw_price", "spread_home",
             "total_line", "over_price", "under_price", "source")
PROP_COLS = ("prop_id", "game_id", "game_date", "player_name", "market", "bookmaker",
             "snapshot_type", "snapshot_at", "line", "over_price")


# ── the SQLite stand-in ──────────────────────────────────────────────────────

def _lit(v):
    if isinstance(v, (tuple, list)):
        return "(" + ", ".join(_lit(x) for x in v) + ")"
    if v is None:
        return "NULL"
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return str(v)


def render(sql: str, params) -> str:
    """psycopg2's interpolation, done by hand: every parameter as a literal."""
    if isinstance(params, dict):
        for k in sorted(params, key=len, reverse=True):
            sql = sql.replace(f"%({k})s", _lit(params[k]))
    elif params:
        parts = sql.split("%s")
        assert len(parts) == len(params) + 1, "placeholder count"
        sql = parts[0] + "".join(_lit(p) + rest for p, rest in zip(params, parts[1:]))
    return sql


class Timeout(Exception):
    pgcode = "57014"


class StandIn:
    """sqlite3 behind the DBConnection surface the prune uses, recording every
    statement and every commit in order."""

    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute(f"CREATE TABLE odds ({', '.join(ODDS_COLS)})")
        self.db.execute(f"CREATE TABLE player_prop_odds ({', '.join(PROP_COLS)})")
        self.db.execute("CREATE TABLE games (game_id PRIMARY KEY, sport, game_date)")
        self.db.execute("CREATE TABLE job_heartbeats (job_id TEXT PRIMARY KEY, "
                        "last_run_at TEXT NOT NULL, last_status TEXT, detail TEXT)")
        self.log: list[tuple[str, str]] = []      # ("sql", text) / ("commit", "")
        self.deleted: list[int] = []              # rows per DELETE, in order
        self.fail = None                          # (sql, params) -> bool

    def execute(self, sql, params=None):
        if self.fail and self.fail(sql, params):
            raise Timeout("canceling statement due to statement timeout")
        text = render(sql, params)
        self.log.append(("sql", text))
        cur = self.db.execute(text)
        if text.lstrip().upper().startswith("DELETE"):
            self.deleted.append(cur.rowcount)
        return cur

    def commit(self):
        self.log.append(("commit", ""))
        self.db.commit()

    def rollback(self):
        self.log.append(("rollback", ""))
        self.db.rollback()

    # helpers
    def ids(self, table):
        pk = "odds_id" if table == "odds" else "prop_id"
        return {r[0] for r in self.db.execute(f"SELECT {pk} FROM {table}")}

    def frontier(self, table):
        row = self.db.execute("SELECT detail FROM job_heartbeats WHERE job_id = ?",
                              (po.FRONTIER_JOB_PREFIX + table,)).fetchone()
        return json.loads(row[0]) if row else None


def build(conn: StandIn, seed: int = 7) -> None:
    """Games across every tier, every protected book, prefix and source, NBA,
    in-play, NULL snapshot types, an orphan, a dateless game, a prop row dated
    apart from its game, and TIES: a pass that writes several rows for one
    book at one snapshot_at (a ladder market does), so which tied row is the
    opener, the close or the newest is decided by the primary key alone."""
    rnd = random.Random(seed)
    games = [  # (game_id, sport, game_date)
        ("MLB_A", "MLB", "2026-10-10"), ("MLB_B", "MLB", "2026-10-15"),
        ("NFL_C", "NFL", "2026-10-17"), ("MLB_D", "MLB", "2026-10-18"),
        ("NFL_E", "NFL", "2026-10-19"), ("MLB_F", "MLB", TODAY),
        ("NFL_G", "NFL", "2026-10-21"), ("NBA_H", "NBA", "2026-10-15"),
        ("NHL_I", "NHL", "2026-10-12"), ("UFC_J", "UFC", None),
    ]
    conn.db.executemany("INSERT INTO games VALUES (?, ?, ?)", games)
    books = ["fanduel", "betmgm", "pinnacle", "draftkings", "sbr_consensus",
             "cfbd_bovada", "bovada"]
    sources = [None, None, None, None, "bovada_direct", *po.PROTECTED_SOURCES]
    types = ["open", "open", "open", "close", "in_play", "in_play", None]
    oid = 0
    for gid, sport, _ in games + [("ORPHAN", "MLB", None)]:
        for market in ("h2h", "totals"):
            for book in books:
                n = rnd.randint(1, 9)
                for i in range(n):
                    at = f"2026-10-01T{i:02d}:{rnd.randint(0, 59):02d}:00Z"
                    for _ in range(rnd.choice((1, 1, 2, 3))):    # a tie group
                        oid += 1
                        conn.db.execute(
                            f"INSERT INTO odds ({', '.join(ODDS_COLS)}) VALUES "
                            f"({', '.join('?' * len(ODDS_COLS))})",
                            (oid, gid, sport, market, book, rnd.choice(types), at,
                             -110 + rnd.randint(-5, 5), 100, None, None, None, None,
                             None, rnd.choice(sources)))
    pid = 0
    moved = [("NFL_POST", "NFL", "2026-10-19"), ("NFL_SWAP", "NFL", "2026-10-19")]
    prop_games = [(g, s, d) for g, s, d in games if d] + moved
    conn.db.executemany("INSERT INTO games VALUES (?, ?, ?)", moved)
    for gid, _, gdate in prop_games:
        for market in ("player_points", "player_rec_yds_alternate"):
            for player in ("Ann", "Bo"):
                for book in ("fanduel", "pinnacle", "betonlineag", "draftkings", "betmgm"):
                    for i in range(rnd.randint(1, 8)):
                        # Prop rows dated apart from their game, both ways
                        # round: NFL_POST's first rows carry an earlier date,
                        # NFL_SWAP's LAST rows do, so its newest row overall is
                        # a Tier 1 row and Tier 2's newest must be ranked
                        # among the Tier 2 rows alone.
                        row_date = gdate
                        if (gid == "NFL_POST" and i < 3) or (gid == "NFL_SWAP" and i >= 4):
                            row_date = "2026-10-16"
                        at = f"2026-10-01T{i:02d}:{rnd.randint(0, 59):02d}:00Z"
                        for _ in range(rnd.choice((1, 1, 2, 3))):    # a tie group
                            pid += 1
                            conn.db.execute(
                                f"INSERT INTO player_prop_odds ({', '.join(PROP_COLS)}) "
                                f"VALUES ({', '.join('?' * len(PROP_COLS))})",
                                (pid, gid, row_date, player, market, book,
                                 rnd.choice(["open", "t24", "close", "in_play", None]),
                                 at, rnd.choice([20.5, 21.5]), -110))
    conn.db.commit()


# ── the old statements, frozen ───────────────────────────────────────────────
# The two DELETEs prune_table sent until 2026-10-20, verbatim but for being
# assembled here and for one addition: every window breaks ties on snapshot_at
# by the primary key, as the new statement does. The old ones ordered by
# snapshot_at alone, so on a tie they kept whichever row the scan returned
# first, and there is no fixed answer to compare against. `tie` flips that
# tie-break, to show the fixture's ties change which rows survive.
# `_unprotected` is shared: this compares the batching, and the protected set
# is whatever it is today for both.

_OLD_DATE = {
    "odds": "game_id IN (SELECT game_id FROM games WHERE game_date {op} %({param})s)",
    "player_prop_odds": "game_date {op} %({param})s",
}
_OLD_IDENTITY = {"odds": ("game_id", "market"),
                 "player_prop_odds": ("game_id", "market", "player_name")}


def old_prune(conn: StandIn, table: str, keep_days: int, today: str,
              tie: str = "ASC") -> None:
    from datetime import date, timedelta
    cutoff = (date.fromisoformat(today) - timedelta(days=keep_days)).isoformat()
    pk = "odds_id" if table == "odds" else "prop_id"
    first = f"snapshot_at ASC, {pk} {tie}"
    last = f"snapshot_at DESC, {pk} {'DESC' if tie == 'ASC' else 'ASC'}"
    part_by = ", ".join(_OLD_IDENTITY[table]) + ", bookmaker"
    params = {"protected": po.PROTECTED_BOOKMAKERS, "cutoff": cutoff, "today": today}
    prunable = po._unprotected(params, table)
    d = _OLD_DATE[table]
    before_cutoff = d.format(op="<", param="cutoff")
    before_today = d.format(op="<", param="today")
    at_or_after_cutoff = d.format(op=">=", param="cutoff")
    is_pre = "(snapshot_type IS NULL OR snapshot_type <> 'in_play')"
    select_keepers = f"""
        SELECT {pk} FROM (
            SELECT {pk},
                   ROW_NUMBER() OVER (
                       PARTITION BY {part_by} ORDER BY {first}
                   ) AS rn_first,
                   ROW_NUMBER() OVER (
                       PARTITION BY {part_by}, {is_pre} ORDER BY {last}
                   ) AS rn_last,
                   {is_pre} AS is_pre
            FROM {table}
            WHERE {prunable}
              AND {before_today}
        ) k WHERE rn_first = 1 OR (is_pre AND rn_last = 1)
    """
    where_old = f"""
        WHERE {prunable}
          AND {before_cutoff}
          AND {pk} NOT IN ({select_keepers})
    """
    select_superseded = f"""
        SELECT {pk} FROM (
            SELECT {pk}, ROW_NUMBER() OVER (
                       PARTITION BY {part_by} ORDER BY {last}
                   ) AS rn
            FROM {table}
            WHERE {prunable}
              AND {at_or_after_cutoff}
              AND {before_today}
        ) t WHERE rn > 1
          AND {pk} NOT IN ({select_keepers})
    """
    conn.execute(f"DELETE FROM {table} {where_old}", params)
    conn.execute(f"DELETE FROM {table} WHERE {pk} IN ({select_superseded})", params)
    conn.commit()


def drain(conn: StandIn, table: str, *, rows=1, floor="2026-10-01", today=TODAY,
          max_runs=2000) -> list[dict]:
    """Run the new prune with a tiny budget until a run deletes nothing and
    the backlog is done. Returns every run's summary."""
    _, identity, row_date = next(t for t in po._TABLES if t[0] == table)
    runs = []
    for _ in range(max_runs):
        res = po.prune_table(conn, table, identity, row_date, KEEP, today,
                             budget=po.Budget(seconds=3600, rows=rows), floor=floor)
        runs.append(res)
        if res["deleted"] == 0 and res["backlog_done"] and not res["budget_spent"]:
            return runs
    raise AssertionError("the prune never converged")


# ── equivalence ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", [7, 11, 23])
@pytest.mark.parametrize("table", ["odds", "player_prop_odds"])
def test_a_proposition_at_a_time_keeps_exactly_what_the_whole_table_prune_kept(table, seed):
    """RULE: identical keep/delete semantics. The old two statements run once;
    the new code runs one row of budget at a time until it is done. The rows
    that survive are the same rows."""
    old, new, flipped = StandIn(), StandIn(), StandIn()
    build(old, seed)
    build(new, seed)
    build(flipped, seed)
    before = old.ids(table)
    old_prune(old, table, KEEP, TODAY)
    old_prune(flipped, table, KEEP, TODAY, tie="DESC")
    runs = drain(new, table)
    assert old.ids(table) < before, "the fixture deletes nothing; it proves nothing"
    assert flipped.ids(table) != old.ids(table), (
        "no tie in the fixture decides which row survives; it proves nothing about ties")
    assert new.ids(table) == old.ids(table)
    assert len(runs) > 3, "a one-row budget should take several runs"


def test_dates_below_the_floor_are_left_alone():
    """RULE: the backlog walk stops at BACKLOG_FLOOR. Rows on older games are
    kept, which is where paid imports with unnamed sources sit."""
    conn = StandIn()
    build(conn)
    old_games = {r[0] for r in conn.db.execute(
        "SELECT odds_id FROM odds o JOIN games g USING (game_id) "
        "WHERE g.game_date < '2026-10-16'")}
    drain(conn, "odds", rows=10**9, floor="2026-10-16")
    assert old_games <= conn.ids("odds")


def test_a_prop_row_on_a_game_moved_past_today_waits_for_the_game():
    """Visited through `games`: a prop row whose game was moved to a future
    date waits until that date passes, then is pruned by its own date."""
    conn = StandIn()
    build(conn)
    conn.db.execute("UPDATE games SET game_date = '2026-10-25' WHERE game_id = 'NFL_POST'")
    waiting = {r[0] for r in conn.db.execute(
        "SELECT prop_id FROM player_prop_odds WHERE game_id = 'NFL_POST'")}
    drain(conn, "player_prop_odds", rows=10**9)
    assert waiting <= conn.ids("player_prop_odds")


def test_ties_keep_the_lowest_id_as_the_opener():
    """A ladder writes many rows per book per pass. Which tied row is the
    opener is fixed by the primary key, so a re-run cannot change its mind."""
    conn = StandIn()
    conn.db.execute("INSERT INTO games VALUES ('G', 'MLB', '2026-10-10')")
    for i in (1, 2, 3):
        conn.db.execute(
            f"INSERT INTO odds ({', '.join(ODDS_COLS)}) VALUES "
            f"(?, 'G', 'MLB', 'alternate_totals', 'fanduel', 'open', "
            f"'2026-10-10T01:00:00Z', NULL, NULL, NULL, NULL, ?, -110, -110, NULL)",
            (i, 8.5 + i))
    drain(conn, "odds", rows=10**9)
    assert conn.ids("odds") == {1, 3}         # opener = lowest id, close = highest


# ── the bound ────────────────────────────────────────────────────────────────

_TABLE_READ = re.compile(r"\b(?:FROM|DELETE FROM)\s+(odds|player_prop_odds)\b", re.I)


def unbounded(sql: str) -> list[str]:
    """Every read of an odds table in `sql` that does not name its game.

    A read is bounded when the WHERE that follows it pins game_id to one value
    or to a literal list. Anything else could touch the whole table."""
    bad = []
    for m in _TABLE_READ.finditer(sql):
        rest = sql[m.end():]
        nxt = _TABLE_READ.search(rest)
        clause = rest[: nxt.start()] if nxt else rest
        if not re.search(r"\bWHERE\b.*?\bgame_id\s*(=\s*'[^']*'|IN\s*\('[^)]*'\))",
                         clause, re.S | re.I):
            bad.append(" ".join(sql[m.start():m.start() + 120].split()))
    return bad


def test_every_statement_the_prune_sends_names_its_game(monkeypatch):
    """RULE: no statement may touch an unbounded set of an odds table. Runs the
    whole job (thinning, both tables, every phase) on the stand-in and checks
    every statement it sent."""
    conn = StandIn()
    build(conn)
    conn.db.execute("INSERT INTO games VALUES ('NBA_K', 'NBA', '2026-10-18')")
    for i in range(4):
        conn.db.execute(
            f"INSERT INTO odds ({', '.join(ODDS_COLS)}) VALUES "
            f"(?, 'NBA_K', 'NBA', 'h2h', 'fanduel', 'open', ?, -110, 100, "
            f"NULL, NULL, NULL, NULL, NULL, NULL)", (90000 + i, f"2026-10-18T0{i}:00:00Z"))
    monkeypatch.setattr(po, "get_connection", lambda: _Ctx(conn))
    po.run_prune_odds(run_date=TODAY, keep_days=KEEP, seconds=3600, rows=10**9)
    sent = [t for k, t in conn.log if k == "sql"]
    assert any(_TABLE_READ.search(s) for s in sent)
    assert any("NBA_K" in s and s.lstrip().upper().startswith("DELETE") for s in sent), (
        "the path thinning never ran, so its statements were never checked")
    offenders = [b for s in sent for b in unbounded(s)]
    assert not offenders, offenders


def test_the_bound_check_catches_a_whole_table_statement():
    """The check above, shown failing on the statement that timed out."""
    old = StandIn()
    build(old)
    old_prune(old, "odds", KEEP, TODAY)
    sent = [t for k, t in old.log if k == "sql"]
    assert any(unbounded(s) for s in sent)


class _Ctx:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, *a):
        return False


# ── the budget ───────────────────────────────────────────────────────────────

def test_a_one_row_budget_stops_after_one_deleting_statement():
    """RULE: a per-run cap. A run stops starting statements once its budget is
    spent: with one row of budget, the first statement that deletes anything
    is the last statement it sends."""
    conn = StandIn()
    build(conn)
    _, identity, row_date = po._TABLES[0]
    res = po.prune_table(conn, "odds", identity, row_date, KEEP, TODAY,
                         budget=po.Budget(seconds=3600, rows=1), floor="2026-10-01")
    assert res["budget_spent"] and res["deleted"] > 0
    assert conn.deleted and conn.deleted[-1] > 0
    assert [n for n in conn.deleted if n > 0] == [conn.deleted[-1]]


def test_the_time_budget_stops_the_run():
    conn = StandIn()
    build(conn)
    ticks = iter(range(0, 10**6))
    clock = lambda: next(ticks)                  # one second per call
    _, identity, row_date = po._TABLES[0]
    res = po.prune_table(conn, "odds", identity, row_date, KEEP, TODAY,
                         budget=po.Budget(seconds=5, rows=10**9, clock=clock),
                         floor="2026-10-01")
    assert res["budget_spent"] and res["statements"] <= 5


def _expire_after_deletes(conn: StandIn, n: int) -> po.Budget:
    """A budget whose clock runs out the moment the n-th DELETE has run."""
    seen = {"deletes": 0}
    run = conn.execute

    def execute(sql, params=None):
        cur = run(sql, params)
        if sql.lstrip().upper().startswith("DELETE"):
            seen["deletes"] += 1
        return cur
    conn.execute = execute
    return po.Budget(seconds=1, rows=10**9,
                     clock=lambda: 10**9 if seen["deletes"] >= n else 0)


def _after_nth_delete(conn: StandIn, n: int) -> list[str]:
    sent = [t for k, t in conn.log if k == "sql"]
    at = [i for i, t in enumerate(sent) if t.lstrip().upper().startswith("DELETE")][n - 1]
    return sent[at + 1:]


@pytest.mark.parametrize("table", ["odds", "player_prop_odds"])
def test_a_spent_budget_starts_no_statement_not_even_a_listing(table):
    """RULE: a run overshoots its budget by at most the one statement in
    flight. Until 2026-10-20 the budget was checked before each DELETE only,
    so once it ran out the next game's listing (about 23 statements for one
    NFL game's props) still went out. The clock here runs out on a game's last
    DELETE, where the next statement would be the next game's listing; after
    it, only the progress record may be written."""
    probe = StandIn()
    build(probe)
    _run(probe, table)
    sent = [t for k, t in probe.log if k == "sql"]
    k = next(i for i in range(len(sent) - 1)
             if sent[i].lstrip().startswith("DELETE") and "WITH RECURSIVE" in sent[i + 1])
    n = sum(1 for t in sent[:k + 1] if t.lstrip().startswith("DELETE"))
    conn = StandIn()
    build(conn)
    _, identity, row_date = next(t for t in po._TABLES if t[0] == table)
    res = po.prune_table(conn, table, identity, row_date, KEEP, TODAY,
                         budget=_expire_after_deletes(conn, n), floor="2026-10-01")
    assert res["budget_spent"]
    late = [t for t in _after_nth_delete(conn, n)
            if not t.lstrip().startswith("INSERT INTO job_heartbeats")]
    assert not late, late[:2]


def test_the_odds_prune_never_visits_a_path_kept_sport_s_games(monkeypatch):
    """RULE: NBA rows are never deleted by the two tiers (the row filter), so
    the `odds` prune does not list or visit NBA games at all: each one cost a
    statement per market, read every row of the market and deleted nothing.
    Same rows deleted, fewer statements."""
    new, ref = StandIn(), StandIn()
    build(new)
    build(ref)

    def every_game(conn, day, *a, **k):          # the listing before 2026-10-20
        return [r[0] for r in conn.execute(
            "SELECT game_id FROM games WHERE game_date = %(day)s ORDER BY game_id",
            {"day": day}).fetchall()]
    before = new.ids("odds")
    drain(new, "odds", rows=10**9)
    with monkeypatch.context() as m:
        m.setattr(po, "_games_on", every_game)
        drain(ref, "odds", rows=10**9)
    assert ref.ids("odds") < before, "the fixture deletes nothing; it proves nothing"
    assert new.ids("odds") == ref.ids("odds")

    def reads(conn):
        return [t for k, t in conn.log if k == "sql" and re.search(r"\bFROM odds\b", t)]
    assert any("'NBA_H'" in t for t in reads(ref)), "the fixture has no NBA game to skip"
    assert not [t for t in reads(new) if "'NBA_H'" in t]
    assert len(reads(new)) < len(reads(ref))


def test_every_delete_is_committed_on_its_own():
    """RULE: each statement is its own transaction, so a slow one can hold
    locks for one proposition, never the run."""
    conn = StandIn()
    build(conn)
    drain(conn, "odds", rows=10**9)
    log = conn.log
    for i, (kind, text) in enumerate(log):
        if kind == "sql" and text.lstrip().startswith("DELETE"):
            nxt = next(k for k, _ in log[i + 1:] if k in ("commit", "rollback")
                       or (k == "sql" and _.lstrip().startswith("DELETE")))
            assert nxt == "commit", "two DELETEs shared a transaction"


# ── the frontier ─────────────────────────────────────────────────────────────

def _run(conn, table="odds", today=TODAY, rows=10**9, floor="2026-10-01"):
    _, identity, row_date = next(t for t in po._TABLES if t[0] == table)
    return po.prune_table(conn, table, identity, row_date, KEEP, today,
                          budget=po.Budget(seconds=3600, rows=rows), floor=floor)


def test_a_first_run_settles_back_to_the_floor_and_records_it():
    conn = StandIn()
    build(conn)
    res = _run(conn)
    assert res["frontier_before"] is None
    assert conn.frontier("odds") == {"lo": "2026-10-01", "hi": "2026-10-18", "retry": []}
    assert res["backlog_done"]


def test_a_run_never_rereads_a_finished_date():
    """RULE: finished dates are recorded, so the next run reads only the
    window, not the whole backlog again."""
    conn = StandIn()
    build(conn)
    _run(conn)
    conn.log.clear()
    _run(conn)
    read_days = {m.group(1) for k, t in conn.log if k == "sql"
                 for m in [re.search(r"FROM games WHERE game_date = '([0-9-]+)'", t)] if m}
    assert read_days == {"2026-10-18", "2026-10-19"}, read_days


def test_a_missed_day_is_caught_up():
    """RULE: a date that left the window while the prune did not run is
    settled on the next run, not lost."""
    conn = StandIn()
    build(conn)
    _run(conn, today="2026-10-17")                # settles up to 10-14
    assert conn.frontier("odds")["hi"] == "2026-10-15"
    old = StandIn()
    build(old)
    _run(conn, today=TODAY)                       # the 10-18 and 10-19 runs were missed
    assert conn.frontier("odds")["hi"] == "2026-10-18"
    old_prune(old, "odds", KEEP, TODAY)
    assert conn.ids("odds") == old.ids("odds")


def _fails_on(game_id: str):
    """A stand-in failure: every DELETE of one game times out."""
    return lambda sql, p: (isinstance(p, dict) and p.get("game_id") == game_id
                           and sql.lstrip().startswith("DELETE"))


def test_a_date_with_a_failed_statement_goes_on_the_retry_list():
    """RULE: a date is recorded as settled only when every statement of it
    committed. One that had a timeout is rolled back, logged, and stored on
    the record's retry list; the walk carries on past it, and the next run
    retries it, after the newest dates (so units that keep timing out can
    never spend the budget those need). It leaves the list only when all of
    it succeeds."""
    conn, ref = StandIn(), StandIn()
    build(conn)
    build(ref)
    old_prune(ref, "odds", KEEP, TODAY)
    conn.fail = _fails_on("MLB_B")
    res = _run(conn)
    assert res["failed"] and all(f["day"] == "2026-10-15" for f in res["failed"])
    assert conn.frontier("odds") == {"lo": "2026-10-01", "hi": "2026-10-18",
                                     "retry": ["2026-10-15"]}
    conn.fail = None
    conn.log.clear()
    res = _run(conn)
    assert not res["failed"] and conn.frontier("odds")["retry"] == []
    assert conn.ids("odds") == ref.ids("odds")
    days = [m.group(1) for k, t in conn.log if k == "sql"
            for m in [re.search(r"FROM games WHERE game_date = '([0-9-]+)'", t)] if m]
    i = days.index("2026-10-15")
    assert i > 0 and all(d >= "2026-10-18" for d in days[:i]),         "the newest dates did not run before the retry"


def test_a_date_that_always_fails_does_not_stop_the_dates_after_it():
    """RULE: one unit that always fails costs its own date, not every date
    after it. Until 2026-10-20 the walk stopped at the first failed date and
    the record never moved again, so every later date kept the newest row the
    window keeps and was never settled. Four daily runs with one game's
    DELETEs always timing out: the record still advances, every other game
    ends exactly where the whole-table prune leaves it, and every run reports
    the failure."""
    conn, ref = StandIn(), StandIn()
    build(conn)
    build(ref)
    old_prune(ref, "odds", KEEP, TODAY)
    stuck = {r[0] for r in conn.db.execute("SELECT odds_id FROM odds WHERE game_id = 'MLB_B'")}
    conn.fail = _fails_on("MLB_B")
    for today in ("2026-10-17", "2026-10-18", "2026-10-19", TODAY):
        res = _run(conn, today=today)
        assert res["failed"], f"the {today} run did not report the failed date"
    assert conn.frontier("odds") == {"lo": "2026-10-01", "hi": "2026-10-18",
                                     "retry": ["2026-10-15"]}
    assert conn.ids("odds") - stuck == ref.ids("odds") - stuck
    conn.fail = None
    _run(conn)
    assert conn.frontier("odds")["retry"] == []
    assert conn.ids("odds") == ref.ids("odds")


@pytest.mark.parametrize("listing", ["games", "propositions"])
def test_a_listing_timeout_costs_its_own_date_and_is_retried(listing):
    """RULE: listing a date's games, or a game's propositions, is a statement
    like any other. A timeout there is rolled back, logged, and leaves its date
    on the retry list; the other dates and games carry on. Until 2026-10-20 it
    escaped the timeout handling and ended the whole table for the run."""
    conn, ref = StandIn(), StandIn()
    build(conn)
    build(ref)
    old_prune(ref, "odds", KEEP, TODAY)
    if listing == "games":
        conn.fail = lambda sql, p: (isinstance(p, dict) and p.get("day") == "2026-10-15"
                                    and "FROM games" in sql)
    else:
        conn.fail = lambda sql, p: (isinstance(p, dict) and p.get("game_id") == "MLB_B"
                                    and "WITH RECURSIVE" in sql)
    res = _run(conn)
    assert [f["day"] for f in res["failed"]] == ["2026-10-15"]
    assert conn.frontier("odds") == {"lo": "2026-10-01", "hi": "2026-10-18",
                                     "retry": ["2026-10-15"]}
    stuck = {r[0] for r in conn.db.execute("SELECT odds_id FROM odds WHERE game_id = 'MLB_B'")}
    assert conn.ids("odds") - stuck == ref.ids("odds") - stuck
    conn.fail = None
    res = _run(conn)
    assert not res["failed"] and conn.frontier("odds")["retry"] == []
    assert conn.ids("odds") == ref.ids("odds")


def test_an_unreadable_record_skips_its_table_and_is_reported(monkeypatch):
    """RULE: a failed read of the progress record is not "no record". Treated
    as none, the run restarted the backlog and then overwrote the good record.
    The table is skipped for the run, the other table is pruned, and the run
    raises so the step is marked failed."""
    conn = StandIn()
    build(conn)
    good = json.dumps({"lo": "2026-10-05", "hi": "2026-10-18", "retry": []})
    conn.db.execute("INSERT INTO job_heartbeats VALUES (?, 'x', 'frontier', ?)",
                    (po.FRONTIER_JOB_PREFIX + "odds", good))
    conn.db.commit()
    before = conn.ids("odds")
    conn.fail = lambda sql, p: (isinstance(p, dict)
                                and p.get("job") == po.FRONTIER_JOB_PREFIX + "odds"
                                and sql.lstrip().upper().startswith("SELECT"))
    monkeypatch.setattr(po, "get_connection", lambda: _Ctx(conn))
    with pytest.raises(RuntimeError, match=r"(^|; )odds: .*progress record"):
        po.run_prune_odds(run_date=TODAY, keep_days=KEEP, seconds=3600, rows=10**9)
    assert conn.ids("odds") == before
    assert conn.frontier("odds") == json.loads(good)
    assert conn.frontier("player_prop_odds") is not None, "the other table was not pruned"


# ── failures fail the step ───────────────────────────────────────────────────

def test_failed_statements_fail_the_step(monkeypatch):
    """RULE: a statement that timed out is a failed step. Until 2026-10-20 the
    count went into the log line only, so a run whose every statement timed
    out returned success. The log line keeps the counts; the run raises once
    both tables have had their turn, and the pipeline step returns False."""
    import run_pipeline
    conn = StandIn()
    build(conn)
    conn.fail = _fails_on("MLB_B")
    monkeypatch.setattr(po, "get_connection", lambda: _Ctx(conn))
    with pytest.raises(RuntimeError, match=r"(^|; )odds: \d+ statements failed"):
        po.run_prune_odds(run_date=TODAY, keep_days=KEEP, seconds=3600, rows=10**9)
    assert conn.frontier("player_prop_odds") is not None, "the second table never ran"
    assert run_pipeline.step_prune_odds(TODAY) is False


def test_a_failed_thinning_statement_fails_the_step(monkeypatch):
    conn = StandIn()
    nba_paths(conn)
    conn.fail = lambda sql, p: (sql.lstrip().upper().startswith("DELETE")
                                and not isinstance(p, dict)
                                and tuple(p[:2]) == ("NBA_Q", "totals"))
    monkeypatch.setattr(po, "get_connection", lambda: _Ctx(conn))
    with pytest.raises(RuntimeError, match=r"path thinning: 1 statements failed"):
        po.run_prune_odds(run_date=TODAY, keep_days=KEEP, seconds=3600, rows=10**9)


def test_the_frontier_is_written_after_its_dates_last_commit():
    """RULE: a date is recorded as settled only after every statement of it
    has committed. No DELETE for a date inside a recorded range may come after
    the record, and the last DELETE before it must be committed."""
    conn = StandIn()
    build(conn)
    _run(conn)
    day_of = dict(conn.db.execute("SELECT game_id, game_date FROM games").fetchall())
    log = conn.log
    writes = 0
    for i, (kind, text) in enumerate(log):
        if not (kind == "sql" and text.lstrip().startswith("INSERT INTO job_heartbeats")):
            continue
        writes += 1
        rng = json.loads(re.search(r"'(\{[^']*\})'", text).group(1))
        for kind2, later in log[i + 1:]:
            if kind2 == "sql" and later.lstrip().startswith("DELETE"):
                gid = re.search(r"game_id = '([^']+)'", later).group(1)
                assert not (rng["lo"] <= day_of[gid] < rng["hi"]), (
                    f"{gid} ({day_of[gid]}) was pruned after its date was recorded settled")
        before = [k for k, t in log[:i] if k in ("commit", "rollback")
                  or (k == "sql" and t.lstrip().startswith("DELETE"))]
        assert not before or before[-1] == "commit"
    assert writes > 3


def test_a_dry_run_counts_and_changes_nothing():
    conn = StandIn()
    build(conn)
    before = conn.ids("odds")
    res = po.prune_table(conn, "odds", ("game_id", "market"), "%(game_day)s", KEEP, TODAY,
                         dry_run=True, budget=po.Budget(seconds=3600, rows=10**9),
                         floor="2026-10-01")
    assert res["would_delete"] > 0 and res["deleted"] == 0
    assert conn.ids("odds") == before
    assert conn.frontier("odds") is None


# ── the NBA path thinning ────────────────────────────────────────────────────
# It ran one statement per GAME DATE over every game of the date, outside any
# try, so one timeout (an 11-game night is ~0.5M rows) stopped both table
# prunes that day and every day after. It now runs one (game, market) per
# statement, each committed on its own, with the table prunes' timeout rule.

NBA_DAYS = {"NBA_P": "2026-10-18", "NBA_Q": "2026-10-18", "NBA_R": "2026-10-18",
            "NBA_S": "2026-10-19", "NBA_T": TODAY}
NBA_MARKETS = ("h2h", "spreads", "totals")


def nba_paths(conn: StandIn, seed: int = 5) -> None:
    """Price paths with long repeats for several NBA games on two settled
    dates and today: three markets, three books, pre-game and in-play rows,
    NULL snapshot types, and paid (non-NULL source) rows mixed in."""
    rnd = random.Random(seed)
    conn.db.executemany("INSERT INTO games VALUES (?, 'NBA', ?)", list(NBA_DAYS.items()))
    oid = 500000
    for gid in NBA_DAYS:
        for market in NBA_MARKETS:
            for book in ("fanduel", "betmgm", "draftkings"):
                price = -110
                for i in range(rnd.randint(8, 30)):
                    if rnd.random() < 0.2:
                        price = rnd.choice([-120, -115, -110, -105, 100])
                    oid += 1
                    conn.db.execute(
                        f"INSERT INTO odds ({', '.join(ODDS_COLS)}) VALUES "
                        f"({', '.join('?' * len(ODDS_COLS))})",
                        (oid, gid, "NBA", market, book,
                         rnd.choice(["open", "open", "in_play", None]),
                         f"2026-10-18T{i // 60:02d}:{i % 60:02d}:00Z",
                         price, -price, None, None, None, None, None,
                         "odds_api_nba_team_totals_live" if rnd.random() < 0.1 else None))
    conn.db.commit()


# The date-wide statement thin_repeats sent until this change, frozen here,
# with one addition: the protected books, which it deleted until 2026-10-20
# (test_prune_keeps_nba_path pins that). This compares the batching; the
# protected set is whatever it is today for both.
_KEEP_BOOKS = ("bookmaker NOT IN (" + ", ".join(f"'{b}'" for b in po.protected_for("odds"))
               + ")" + "".join(f" AND bookmaker NOT LIKE '{p}%'"
                               for p in po.PROTECTED_BOOKMAKER_PREFIXES))
_OLD_THIN = f"""
    SELECT odds_id FROM (
        SELECT odds_id, {po._QUOTE_KEY} AS q,
               LAG({po._QUOTE_KEY}) OVER w AS q_prev,
               LEAD({po._QUOTE_KEY}) OVER w AS q_next
          FROM odds
         WHERE game_id IN ({{ids}})
           AND source IS NULL
           AND {_KEEP_BOOKS}
        WINDOW w AS (PARTITION BY game_id, market, bookmaker,
                     (snapshot_type IS NULL OR snapshot_type <> 'in_play')
                     ORDER BY snapshot_at, odds_id)
    ) t
    WHERE q = q_prev AND q = q_next
"""


def old_thin(conn: StandIn, today: str = TODAY) -> None:
    days = sorted({d for d in NBA_DAYS.values() if d < today})
    for d in days:
        ids = [g for g, gd in NBA_DAYS.items() if gd == d]
        marks = ", ".join(["%s"] * len(ids))
        conn.execute(f"DELETE FROM odds WHERE game_id IN ({marks}) AND odds_id IN "
                     f"({_OLD_THIN.format(ids=marks)})", (*ids, *ids))
    conn.commit()


def _rows_of(conn: StandIn, gid: str, market: str) -> set[int]:
    return {r[0] for r in conn.db.execute(
        "SELECT odds_id FROM odds WHERE game_id = ? AND market = ?", (gid, market))}


@pytest.mark.parametrize("seed", [5, 9, 31])
def test_thinning_a_market_at_a_time_keeps_what_the_date_wide_statement_kept(seed):
    """RULE: identical rows survive. The window partitions by (game, market,
    book, pre-game or in-play), so a statement per (game, market) keeps and
    deletes exactly what one statement over the whole date did."""
    old, new = StandIn(), StandIn()
    nba_paths(old, seed)
    nba_paths(new, seed)
    before = old.ids("odds")
    old_thin(old)
    po.thin_repeats(new, today=TODAY)
    assert old.ids("odds") < before, "the fixture thins nothing; it proves nothing"
    assert new.ids("odds") == old.ids("odds")


_ONE_UNIT = re.compile(r"^DELETE FROM odds WHERE game_id = '[^']+' AND market = '[^']+' AND ")


def test_every_thinning_statement_covers_one_game_and_one_market():
    """RULE: the thinning's unit of work is one (game, market), about 26k rows
    for an NBA game's market on 2026-10-20, not a whole date (0.5M rows for
    10-21's eleven games before tip-off). Every DELETE names one game and one
    market, and nothing it sends lists several games."""
    conn = StandIn()
    nba_paths(conn)
    out = po.thin_repeats(conn, today=TODAY)
    sent = [t for k, t in conn.log if k == "sql"]
    deletes = [" ".join(s.split()) for s in sent if s.lstrip().upper().startswith("DELETE")]
    settled = [g for g, d in NBA_DAYS.items() if d < TODAY]
    assert len(deletes) == len(settled) * len(NBA_MARKETS) == out["statements"]
    assert all(_ONE_UNIT.match(d) for d in deletes), deletes[:2]
    assert not [s for s in sent if re.search(r"game_id\s+IN\s*\(", s, re.I)]


def test_a_thinning_timeout_spares_the_other_markets_and_is_retried():
    """RULE: one statement timing out costs that (game, market) only. It is
    rolled back and logged; every other market of every date is thinned, and
    the next run, whose 21-day look-back still covers the date, finishes it."""
    conn, ref = StandIn(), StandIn()
    nba_paths(conn)
    nba_paths(ref)
    old_thin(ref)
    stuck = _rows_of(conn, "NBA_Q", "totals")
    conn.fail = lambda sql, p: (sql.lstrip().upper().startswith("DELETE")
                                and tuple(p[:2]) == ("NBA_Q", "totals"))
    out = po.thin_repeats(conn, today=TODAY)
    assert [(f["game_id"], f["market"]) for f in out["failed"]] == [("NBA_Q", "totals")]
    assert _rows_of(conn, "NBA_Q", "totals") == stuck
    assert conn.ids("odds") - stuck == ref.ids("odds") - stuck
    # Dates run newest first, so the game after NBA_Q is NBA_R on its date.
    i = max(n for n, (k, _) in enumerate(conn.log) if k == "rollback")
    assert any(k == "sql" and "'NBA_R'" in t for k, t in conn.log[i:]), (
        "nothing ran after the timeout")
    conn.fail = None
    out = po.thin_repeats(conn, today=TODAY)
    assert not out["failed"] and conn.ids("odds") == ref.ids("odds")


def test_a_thinning_listing_timeout_costs_its_own_game():
    """RULE: listing a game's markets is a statement like any other. A timeout
    there is rolled back and logged as that game's failure; every other game is
    thinned, and the next run retries it."""
    conn, ref = StandIn(), StandIn()
    nba_paths(conn)
    nba_paths(ref)
    old_thin(ref)
    stuck = {r[0] for r in conn.db.execute("SELECT odds_id FROM odds WHERE game_id = 'NBA_Q'")}
    conn.fail = lambda sql, p: "WITH RECURSIVE" in sql and tuple(p)[0] == "NBA_Q"
    out = po.thin_repeats(conn, today=TODAY)
    assert [f["game_id"] for f in out["failed"]] == ["NBA_Q"]
    assert conn.ids("odds") - stuck == ref.ids("odds") - stuck
    conn.fail = None
    out = po.thin_repeats(conn, today=TODAY)
    assert not out["failed"] and conn.ids("odds") == ref.ids("odds")


def test_the_thinning_stops_when_its_budget_is_spent():
    """RULE: the thinning has a budget too, checked before every statement
    and at the top of every game, so it overshoots by at most the statement in
    flight. It had none until 2026-10-20 and re-read 21 days of NBA games every
    run. The clock runs out on the first DELETE; nothing after it reads odds."""
    conn = StandIn()
    nba_paths(conn)
    out = po.thin_repeats(conn, today=TODAY, budget=_expire_after_deletes(conn, 1))
    assert out["budget_spent"] and out["statements"] == 1
    assert not _after_nth_delete(conn, 1)


def test_the_thinning_starts_with_the_newest_date():
    """A spent budget leaves the OLDEST dates for the next run: they were
    thinned by earlier runs already, while the newest settled date holds a
    whole day of unthinned rows (77,278 for one NBA game on 2026-10-20)."""
    conn = StandIn()
    nba_paths(conn)
    po.thin_repeats(conn, today=TODAY, budget=_expire_after_deletes(conn, 1))
    first = next(t for k, t in conn.log
                 if k == "sql" and t.lstrip().upper().startswith("DELETE"))
    newest = max(d for d in NBA_DAYS.values() if d < TODAY)
    assert f"'{next(g for g, d in NBA_DAYS.items() if d == newest)}'" in first


def test_the_daily_run_gives_the_thinning_a_budget(monkeypatch):
    """The budget only bounds the run if run_prune_odds passes one."""
    seen = {}
    conn = StandIn()
    monkeypatch.setattr(po, "get_connection", lambda: _Ctx(conn))

    def thin(conn, today, **k):
        seen.update(k)
        return {"sports": ["NBA"], "rows": 0, "dates": 0, "statements": 0,
                "failed": [], "budget_spent": False}
    monkeypatch.setattr(po, "thin_repeats", thin)
    monkeypatch.setattr(po, "prune_table", lambda *a, **k: {
        "table": a[1], "deleted": 0, "would_delete": 0, "statements": 0,
        "seconds": 0.0, "frontier": {"lo": "x", "hi": "y"}, "retry": [],
        "backlog_done": True, "budget_spent": False, "failed": []})
    po.run_prune_odds(run_date=TODAY, keep_days=KEEP)
    assert isinstance(seen.get("budget"), po.Budget)


def test_a_thinning_error_that_is_not_a_timeout_is_raised():
    """RULE: only a timeout or a lost connection is absorbed. Any other error
    is a bug and stops the thinning loudly."""
    conn = StandIn()
    nba_paths(conn)

    def broken(sql, p):
        if sql.lstrip().upper().startswith("DELETE"):
            raise ValueError("column q does not exist")
        return False
    conn.fail = broken
    with pytest.raises(ValueError):
        po.thin_repeats(conn, today=TODAY)


@pytest.mark.parametrize("error", [Timeout("canceling statement due to statement timeout"),
                                   RuntimeError("thinning broke")])
def test_a_thinning_failure_still_prunes_both_tables_and_is_reported(monkeypatch, error):
    """RULE: the thinning cannot stop the table prunes. Whatever escapes it is
    logged, both tables still get their turn, and the run raises at the end so
    the failure is not silent."""
    pruned = []
    conn = StandIn()
    monkeypatch.setattr(po, "get_connection", lambda: _Ctx(conn))

    def thin(*a, **k):
        raise error

    def prune_table(conn, table, *a, **k):
        pruned.append(table)
        return {"table": table, "deleted": 0, "would_delete": 0, "statements": 0,
                "seconds": 0.0, "frontier": {"lo": "x", "hi": "y"},
                "backlog_done": True, "budget_spent": False, "failed": []}
    monkeypatch.setattr(po, "thin_repeats", thin)
    monkeypatch.setattr(po, "prune_table", prune_table)
    with pytest.raises(RuntimeError, match="thinning"):
        po.run_prune_odds(run_date=TODAY, keep_days=KEEP)
    assert pruned == ["odds", "player_prop_odds"]


def test_a_failed_prune_is_reported_as_a_failed_step(monkeypatch):
    """RULE: the prune is non-fatal (the run goes on) but never silent. It
    last finished around 2026-09-03 and timed out every day the logs reach
    while the step returned True, so the run's ledger never named it."""
    import run_pipeline
    import data.prune_odds as po

    def boom(run_date):
        raise RuntimeError("canceling statement due to statement timeout")
    monkeypatch.setattr(po, "run_prune_odds", boom)
    assert run_pipeline.step_prune_odds("2026-10-20") is False
    monkeypatch.setattr(po, "run_prune_odds",
                        lambda run_date: {"tables": [{"deleted": 3}, {"deleted": 4}]})
    assert run_pipeline.step_prune_odds("2026-10-20") is True


def test_a_record_write_that_fails_for_a_bug_fails_the_table():
    """RULE: a progress record that can never be written means every run
    re-walks the same dates with nothing to say so. A timeout on the write is
    retried by the next run's write; any other error is raised, so the table
    fails and the step is marked failed."""
    class Broken(StandIn):
        def __init__(self, exc):
            super().__init__()
            self.exc = exc

        def execute(self, sql, params=None):
            if "INSERT INTO job_heartbeats" in sql:
                raise self.exc
            return super().execute(sql, params)

    conn = Broken(ValueError("bad detail"))
    build(conn)
    with pytest.raises(ValueError):
        _run(conn)
    conn = Broken(Timeout("canceling statement due to statement timeout"))
    build(conn)
    res = _run(conn)
    assert res["frontier"]["lo"] == "2026-10-01"
