"""The restore of the NCAAB NONE rows the scorer's sweep deleted.

Runs the module's real SQL on a scratch Postgres (tests/_pg.py). What it must
do: put back a card's deleted NONE row with its own pick_id and created_at
(CLAUDE.md 1c: timing is data), rebuild the columns picks_log does not keep
by each card's rule, and touch nothing else -- not a started game, not a game
that has a row now, not a BET, not another model, not a delete from before
the cards wrote NONE rows. Repeating it restores nothing twice.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tracking import restore_swept_ncaab_none_rows as r  # noqa: E402

NOW = datetime(2026, 11, 6, 16, 0, tzinfo=timezone.utc)
LATER = (NOW + timedelta(hours=5)).isoformat().replace("+00:00", "Z")
EARLIER = (NOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z")

_TYPES = {"pick_id": "bigint", "model_probability": "numeric",
          "dk_implied_prob": "numeric", "edge": "numeric", "dk_odds": "numeric",
          "scored_line": "numeric", "kelly_fraction": "numeric",
          "recommended_bet": "numeric", "bankroll_at_pick": "numeric",
          "decision_odds": "numeric", "decision_implied_prob": "numeric",
          "decision_edge": "numeric", "model_probability_cal": "numeric",
          "best_odds": "numeric", "best_implied_prob": "numeric",
          "best_edge": "numeric"}


def _col(c):
    return f"{c} {_TYPES.get(c, 'text')}"


class _Conn:
    """The two calls the module makes: execute(...).fetchall() and commit()."""

    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=None):
        cur = self.raw.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self.raw.commit()


@pytest.fixture(scope="module")
def dsn():
    from tests._pg import can_scratch, scratch_cluster
    if not can_scratch():
        pytest.skip("no Postgres binaries (tests/_pg.py)")
    with scratch_cluster("restore-ncaab-none-") as d:
        yield d


@pytest.fixture
def conn(dsn):
    import psycopg2
    raw = psycopg2.connect(dsn)
    cur = raw.cursor()
    cur.execute("DROP TABLE IF EXISTS picks, picks_log, games")
    cur.execute("CREATE TABLE games (game_id text, sport text, commence_time text)")
    other = [c for c in r.LOG_COLS + r.REBUILT_COLS if c != "pick_id"]
    cur.execute(f"""CREATE TABLE picks (
        pick_id bigserial PRIMARY KEY, {', '.join(_col(c) for c in other)},
        result text, dk_bet_link text, best_bet_link text,
        downgrade_reason text, is_live boolean DEFAULT false)""")
    # The identity uq_picks_one_row_per_pick keys a card's row on.
    cur.execute("CREATE UNIQUE INDEX uq ON picks (game_id, model_id, game_date, pick_side)")
    cur.execute(f"""CREATE TABLE picks_log (
        log_id bigserial PRIMARY KEY, logged_at timestamptz, operation text,
        {', '.join(_col(c) for c in r.LOG_COLS)}, result text)""")
    raw.commit()
    yield _Conn(raw)
    raw.close()


def _logged(conn, pick_id, game_id, model_id, *, op="DELETE", signal="NONE",
            book="fanduel", logged_at="2026-11-05T15:24:31+00:00",
            created_at="2026-11-05 15:05:00.765169+00", side="home"):
    row = {c: None for c in r.LOG_COLS}
    row.update(pick_id=pick_id, game_id=game_id, model_id=model_id,
               sport="NCAAB", game_date="2026-11-06", game_time=LATER,
               pick_side=side, pick_label=f"{game_id} {model_id}",
               model_probability=0.5205, dk_implied_prob=0.0, edge=0.0,
               scored_line=-7.0, kelly_fraction=0.0, recommended_bet=0.0,
               bankroll_at_pick=631.33, signal_type=signal,
               confidence_tier="MED", created_at=created_at,
               decision_book=book, decision_odds=-110,
               decision_implied_prob=0.5238, decision_edge=-0.0033,
               line_book=book)
    cols = ["logged_at", "operation"] + list(r.LOG_COLS)
    conn.execute(
        f"INSERT INTO picks_log ({', '.join(cols)}) "
        f"VALUES ({', '.join('%(' + c + ')s' for c in cols)})",
        {**row, "logged_at": logged_at, "operation": op})
    return row


def _game(conn, game_id, commence):
    conn.execute("INSERT INTO games VALUES (%s, 'NCAAB', %s)", (game_id, commence))


def _picks(conn):
    # Numbers as float8: data.db registers numeric -> float for the process.
    cur = conn.execute(
        "SELECT pick_id, game_id, model_id, created_at, signal_type, "
        "model_probability_cal::float8, best_book, best_odds::float8, "
        "best_implied_prob::float8, best_edge::float8 FROM picks ORDER BY pick_id")
    return {row[0]: row[1:] for row in cur.fetchall()}


def test_restores_each_card_with_its_own_rebuilt_columns(conn):
    for gid in ("G1", "G2", "G3", "G4"):
        _game(conn, gid, LATER)
    _logged(conn, 11, "G1", "ncaab_moneyline_own_spread")
    _logged(conn, 12, "G2", "ncaab_total_blend", book="draftkings")
    _logged(conn, 13, "G3", "ncaab_first_half_spread", book="draftkings")
    _logged(conn, 14, "G4", "ncaab_first_half_total", book="betmgm")
    conn.commit()

    dry = r.restore(conn, apply=False, now=NOW)
    assert dry["n_found"] == 4 and dry["n_restored"] == 0
    assert _picks(conn) == {}, "a count-only run wrote rows"

    out = r.restore(conn, apply=True, now=NOW)
    assert out["n_restored"] == 4
    got = _picks(conn)
    cal = 0.5205
    best = ("fanduel", -110.0, 0.5238, -0.0033)
    assert got[11] == ("G1", "ncaab_moneyline_own_spread",
                       "2026-11-05 15:05:00.765169+00", "NONE", cal, *best)
    assert got[12][4:] == (cal, None, None, None, None), "total_blend: no best"
    assert got[13][4:] == (cal, None, None, None, None), "first half at DK: no best"
    assert got[14][4:] == (cal, "betmgm", -110.0, 0.5238, -0.0033)

    again = r.restore(conn, apply=True, now=NOW)
    assert again["n_found"] == 0 and again["n_restored"] == 0


def test_leaves_everything_it_must_not_touch(conn):
    for gid in ("TIPPED", "HASROW", "BETROW", "OTHER", "OLD", "KEEP"):
        _game(conn, gid, EARLIER if gid == "TIPPED" else LATER)
    _logged(conn, 21, "TIPPED", "ncaab_spread_market")
    _logged(conn, 22, "HASROW", "ncaab_spread_market")
    conn.execute("INSERT INTO picks (game_id, model_id, game_date, pick_side, "
                 "signal_type, created_at) VALUES ('HASROW', "
                 "'ncaab_spread_market', '2026-11-06', 'away', 'BET', 'later')")
    _logged(conn, 23, "BETROW", "ncaab_spread_market", signal="BET")
    _logged(conn, 24, "OTHER", "nfl_opener_spread")
    _logged(conn, 25, "OLD", "ncaab_spread_market",
            logged_at="2026-11-03T15:00:00+00:00")
    _logged(conn, 26, "KEEP", "ncaab_spread_market", op="INSERT")
    conn.commit()

    out = r.restore(conn, apply=True, now=NOW)

    assert out["n_found"] == 0 and out["n_restored"] == 0
    assert set(_picks(conn)) == {1}, "only the pre-existing BET stands"


# ── the worker job that runs it once, after the fix deploys ─────────────────

def test_the_declared_job_restores_after_the_old_container_drains():
    import json

    from tracking import job_queue as q
    root = Path(__file__).resolve().parents[1]
    entries = json.loads((root / "jobs" / "declared_jobs.json").read_text(encoding="utf-8"))
    [entry] = [e for e in entries
               if e.get("key") == "restore-swept-ncaab-none-rows-2026-11-06"]
    assert entry["job_type"] == "restore_swept_ncaab_none_rows"
    assert entry.get("enabled", True) is True
    _, validate = q.JOBS[entry["job_type"]]
    cleaned = validate(entry["args"])
    assert cleaned["apply"] is True
    # Longer than the drain of the container the deploy replaces, whose
    # in-flight scoring step would sweep the rows again.
    drain = json.loads((root / "railway.json").read_text(encoding="utf-8"))
    assert cleaned["wait_s"] > drain["deploy"]["drainingSeconds"]


@pytest.mark.parametrize("args", [{"apply": "yes"}, {"apply": 1},
                                  {"apply": True, "wait_s": -1},
                                  {"apply": True, "wait_s": True},
                                  {"apply": True, "wait_s": 5000}])
def test_the_job_refuses_loose_arguments(args):
    from tracking import job_queue as q
    _, validate = q.JOBS["restore_swept_ncaab_none_rows"]
    with pytest.raises(ValueError):
        validate(args)


def test_the_job_counts_only_by_default():
    from tracking import job_queue as q
    _, validate = q.JOBS["restore_swept_ncaab_none_rows"]
    assert validate({}) == {"apply": False, "wait_s": 660}
