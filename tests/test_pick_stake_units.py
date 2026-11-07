"""A pick's own stake: picks.stake_units (mike, 2026-11-06).

Every surface sizes a pick as stake_for: units TO WIN at the pick's price, risk
capped at 3u. A pick may now carry its own units to win (1..3); NULL is the flat
1u, so no settled record changes. The first writer is NCAAB's agreement rule
(models/ncaab_stake.py). These tests pin:

  * the three-argument SQL stake body to the Python stake_for, at every price
    and stake, including the cap and the out-of-range fallback;
  * the migration on a real Postgres: the columns, the functions, the views
    switched to pass stake_units, NULL rows graded exactly as before, a 2u row
    graded at 2u, and a second pass that changes nothing;
  * the order it runs in, and that the settled recap passes the stake.
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data import view_migrations as vm  # noqa: E402
from tracking.discord_notifier import _SETTLED_SQL, pick_conviction, stake_for  # noqa: E402
from tracking.published_units import unit_profit, unit_risked  # noqa: E402

MIG = ROOT / "data" / "migrations" / "pick_stake_units_2026_11_06.sql"
UNITS_MIG = ROOT / "data" / "migrations" / "published_record_units_2026_10_16.sql"
FN_MIG = ROOT / "data" / "migrations" / "published_pick_units_2026_10_17.sql"
PRICES = [None, 0, -110, -115, -150, -200, -301, -1000, 100, 150, 600]
UNITS = [None, 1, 1.5, 2, 3, 0.5, 4]


def _body(tag: str) -> str:
    text = MIG.read_text(encoding="utf-8")
    start = text.index(f"${tag}$") + len(tag) + 2
    return text[start:text.index(f"${tag}$", start)].strip()


def _stake_sql(price, units) -> tuple[float, float]:
    sql = _body("stake")
    sql = re.sub(r"\bprice\b", "NULL" if price is None else repr(float(price)), sql)
    sql = re.sub(r"\bunits\b", "NULL" if units is None else repr(float(units)), sql)
    risk, win = sqlite3.connect(":memory:").execute(sql).fetchone()
    return float(risk), float(win)


@pytest.mark.parametrize("units", UNITS)
def test_the_three_argument_stake_body_is_stake_for(units):
    for price in PRICES:
        want = stake_for(None, price, units)
        risk, win = _stake_sql(price, units)
        assert risk == pytest.approx(want.risk, abs=1e-9), (price, units)
        assert win == pytest.approx(want.win, abs=1e-9), (price, units)
        for result in ("WIN", "LOSS", "PUSH", "NO_ACTION", None):
            assert unit_profit(price, result, units) == pytest.approx(
                want.win if result == "WIN" else -want.risk if result == "LOSS" else 0.0, abs=1e-9)
            assert unit_risked(price, result, units) == pytest.approx(
                want.risk if result in ("WIN", "LOSS") else 0.0, abs=1e-9)


def test_a_stake_outside_one_to_three_is_the_flat_unit():
    for u in (None, 0, 0.5, 3.01, 4, "x", float("nan")):
        assert pick_conviction(0.03, u) == 1.0, u
    assert pick_conviction(0.03, 2) == 2.0 and pick_conviction(0.03, 3) == 3.0
    # 2u to win at -110 lays 2.2u; at -200 the 3u cap binds and the win drops to 1.5u
    assert (round(stake_for(None, -110, 2).risk, 6), stake_for(None, -110, 2).win) == (2.2, 2.0)
    s = stake_for(None, -200, 2)
    assert (s.risk, s.win, s.capped) == (3.0, 1.5, True)


def test_the_two_argument_functions_are_unchanged():
    """BYOM's backtest and anything without a pick row call the old pair."""
    assert "published_pick_unit_profit(numeric, text)" not in MIG.read_text(encoding="utf-8").split(
        "-- 2. the three-argument functions")[1].split("-- 3.")[0].replace(
        "published_pick_unit_profit(numeric, text, numeric)", "")
    assert FN_MIG.exists()


def test_it_runs_after_open_picks_and_before_the_posted_pair():
    names = list(vm.MIGRATION_FILES) if hasattr(vm, "MIGRATION_FILES") else None
    if names is None:
        names = [v for k, v in vars(vm).items() if isinstance(v, list) and "published_record_units_2026_10_16.sql" in v][0]
    # after open_picks' owner (it switches that view), before the posted pair
    # (whose view patch calls the three-argument functions it creates)
    assert names[-2:] == ["published_pick_units_2026_10_17.sql", "published_record_units_2026_10_16.sql"]
    assert names.index("open_picks_view_2026_11_04.sql") < names.index(MIG.name) < len(names) - 2


def test_the_settled_recap_passes_the_picks_stake():
    assert "published_pick_unit_profit(COALESCE(p.decision_odds, p.dk_odds), p.result, p.stake_units)" in _SETTLED_SQL
    assert "published_pick_unit_risked(COALESCE(p.decision_odds, p.dk_odds), p.result, p.stake_units)" in _SETTLED_SQL


def test_every_ddl_statement_sits_behind_a_catalog_read():
    """tests/test_ddl_guard.py: a second pass must fire no DDL."""
    text = MIG.read_text(encoding="utf-8")
    for stmt in ("ALTER TABLE public.picks ADD COLUMN stake_units",
                 "ALTER TABLE public.picks ADD COLUMN stake_reason",
                 "ALTER TABLE public.picks_log ADD COLUMN stake_units",
                 "CREATE FUNCTION public.published_pick_stake(price numeric, units numeric",
                 "CREATE FUNCTION public.published_pick_unit_profit(price numeric, result text, units numeric)",
                 "CREATE FUNCTION public.published_pick_unit_risked(price numeric, result text, units numeric)",
                 "CREATE OR REPLACE FUNCTION public.log_picks_changes()"):
        before = text[:text.index(stmt)]
        last_if = before.rfind("IF ")
        last_end = before.rfind("END IF;")
        assert last_if > last_end, f"{stmt} is not inside an IF"


# ── on a real Postgres ────────────────────────────────────────────────────────

psycopg2 = pytest.importorskip("psycopg2")
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402

RECORD_SQL = """
    SELECT count(*) AS n,
      COALESCE(sum(published_pick_unit_profit(COALESCE(decision_odds, dk_odds), result)) FILTER (WHERE result IN ('WIN', 'LOSS', 'PUSH')), 0) AS units,
      COALESCE(sum(published_pick_unit_risked(COALESCE(decision_odds, dk_odds), result)) FILTER (WHERE result IN ('WIN', 'LOSS', 'PUSH')), 0) AS risked
    FROM picks p
"""


@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("pick-stake-units-pg-") as d:
        yield d


@pytest.fixture()
def db(dsn):
    raw = psycopg2.connect(dsn)
    raw.autocommit = True
    cur = raw.cursor()
    for role in ("anon", "authenticated"):
        cur.execute(f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') "
                    f"THEN CREATE ROLE {role} NOLOGIN; END IF; END $$;")
    cur.execute("DROP VIEW IF EXISTS v_public_track_record, v_public_track_record_daily, open_picks")
    cur.execute("DROP TABLE IF EXISTS picks, picks_log, games CASCADE")
    for fn in ("published_pick_unit_profit(numeric, text)", "published_pick_unit_risked(numeric, text)",
               "published_pick_stake(numeric)", "published_pick_unit_profit(numeric, text, numeric)",
               "published_pick_unit_risked(numeric, text, numeric)", "published_pick_stake(numeric, numeric)"):
        cur.execute(f"DROP FUNCTION IF EXISTS public.{fn} CASCADE")
    cur.execute("CREATE TABLE picks (pick_id SERIAL PRIMARY KEY, game_id TEXT, game_date TEXT, "
                "decision_odds NUMERIC, dk_odds NUMERIC, result TEXT)")
    cur.execute("CREATE TABLE games (game_id TEXT PRIMARY KEY)")
    cur.execute(FN_MIG.read_text(encoding="utf-8"))
    cur.execute(f"CREATE VIEW v_public_track_record AS {RECORD_SQL}")
    cur.execute(f"CREATE VIEW v_public_track_record_daily AS {RECORD_SQL.replace('count(*) AS n', 'min(game_date) AS d, count(*) AS n')}")
    cur.execute("""CREATE VIEW open_picks AS SELECT p.pick_id, s.risk, s.win FROM picks p
                   LEFT JOIN games g ON g.game_id = p.game_id
                   CROSS JOIN LATERAL published_pick_stake(COALESCE(p.decision_odds, p.dk_odds)) s(risk, win)""")
    rows = [(-110, "WIN"), (-110, "LOSS"), (150, "LOSS"), (-200, "WIN"), (None, "WIN"), (-110, "PUSH"),
            (-110, "NO_ACTION"), (-110, None)]
    for price, res in rows:
        cur.execute("INSERT INTO picks (game_id, decision_odds, result) VALUES ('g', %s, %s)", (price, res))
    yield raw
    raw.close()


def _one(raw, sql):
    with raw.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()


def _apply(raw):
    """This file, then the record-units file that stays last (the list's order)."""
    with raw.cursor() as cur:
        cur.execute(MIG.read_text(encoding="utf-8"))
        cur.execute(UNITS_MIG.read_text(encoding="utf-8"))


def test_the_migration_switches_the_views_and_grades_null_rows_as_before(db):
    before = _one(db, "SELECT n, units, risked FROM v_public_track_record")
    before_open = _one(db, "SELECT sum(risk), sum(win) FROM open_picks")
    _apply(db)
    for v in ("v_public_track_record", "v_public_track_record_daily"):
        d = _one(db, f"SELECT pg_get_viewdef('public.{v}'::regclass, true)")[0]
        assert "result, stake_units)" in d and "dk_odds), result)" not in d, v
    assert "p.stake_units)" in _one(db, "SELECT pg_get_viewdef('public.open_picks'::regclass, true)")[0]
    # every row NULL: the record is exactly what it was
    assert _one(db, "SELECT n, units, risked FROM v_public_track_record") == before
    assert _one(db, "SELECT sum(risk), sum(win) FROM open_picks") == before_open

    # one 2u winner at -110 adds 1u of profit and 1.1u of risk over the 1u row
    with db.cursor() as cur:
        cur.execute("UPDATE picks SET stake_units = 2, stake_reason = 'test' WHERE pick_id = 1")
    n, units, risked = _one(db, "SELECT n, units, risked FROM v_public_track_record")
    assert float(units) == pytest.approx(float(before[1]) + 1.0)
    assert float(risked) == pytest.approx(float(before[2]) + 1.1)
    with pytest.raises(psycopg2.errors.CheckViolation):
        with db.cursor() as cur:
            cur.execute("UPDATE picks SET stake_units = 5 WHERE pick_id = 2")


def test_a_second_pass_changes_nothing(db):
    _apply(db)
    oid_defs = _one(db, "SELECT string_agg(pg_get_viewdef(c.oid, true), '|' ORDER BY c.relname) "
                        "FROM pg_class c WHERE relname IN ('v_public_track_record', 'open_picks')")
    xmin_before = _one(db, "SELECT xmin::text FROM pg_class WHERE relname = 'v_public_track_record'")
    _apply(db)
    assert _one(db, "SELECT string_agg(pg_get_viewdef(c.oid, true), '|' ORDER BY c.relname) "
                    "FROM pg_class c WHERE relname IN ('v_public_track_record', 'open_picks')") == oid_defs
    # no CREATE OR REPLACE ran: the view's catalog row was not rewritten
    assert _one(db, "SELECT xmin::text FROM pg_class WHERE relname = 'v_public_track_record'") == xmin_before

def test_a_record_view_its_owner_just_recreated_gets_the_three_argument_units(db):
    """An owner file rebuilds a record view with no units columns; the
    record-units file adds them with the pick's stake straight away."""
    with db.cursor() as cur:
        cur.execute("DROP VIEW v_public_track_record")
        cur.execute("CREATE VIEW v_public_track_record AS SELECT count(*) AS n FROM picks p")
    _apply(db)
    d = _one(db, "SELECT pg_get_viewdef('public.v_public_track_record'::regclass, true)")[0]
    assert d.count("result, stake_units)") == 2 and "dk_odds), result)" not in d


# production's log_picks_changes() before this migration (read 2026-11-06)
_LOG_COLS = ("pick_id", "game_id", "model_id", "sport", "game_date", "game_time", "run_time",
             "pick_side", "pick_label", "model_probability", "dk_implied_prob", "edge", "dk_odds",
             "scored_line", "kelly_fraction", "recommended_bet", "bankroll_at_pick", "injury_flag",
             "injury_detail", "signal_type", "confidence_tier", "result", "profit_flat",
             "profit_kelly", "settled_at", "created_at", "decision_book", "decision_odds",
             "decision_implied_prob", "decision_edge", "line_book")
_OLD_LOG_FN = """
CREATE OR REPLACE FUNCTION public.log_picks_changes() RETURNS trigger LANGUAGE plpgsql
SET search_path TO 'public', 'pg_catalog' AS $f$
  DECLARE r picks%%ROWTYPE;
  BEGIN
    IF TG_OP = 'DELETE' THEN r := OLD; ELSE r := NEW; END IF;
    INSERT INTO picks_log (logged_at, operation, %s) VALUES (NOW(), TG_OP, %s);
    RETURN r;
  END; $f$
""" % (", ".join(_LOG_COLS), ", ".join("r." + c for c in _LOG_COLS))


def test_the_audit_trigger_copies_the_stake_into_picks_log(dsn):
    raw = psycopg2.connect(dsn)
    raw.autocommit = True
    cur = raw.cursor()
    cur.execute("DROP VIEW IF EXISTS v_public_track_record, v_public_track_record_daily, open_picks")
    cur.execute("DROP TABLE IF EXISTS picks, picks_log CASCADE")
    typed = lambda c: f"{c} {'SERIAL PRIMARY KEY' if c == 'pick_id' else 'TEXT'}"
    cur.execute("CREATE TABLE picks (" + ", ".join(typed(c) for c in _LOG_COLS) + ")")
    cur.execute("CREATE TABLE picks_log (log_id SERIAL PRIMARY KEY, logged_at TIMESTAMPTZ, operation TEXT, "
                + ", ".join(f"{c} TEXT" for c in _LOG_COLS) + ")")
    cur.execute(_OLD_LOG_FN)
    cur.execute("CREATE TRIGGER picks_audit_trigger AFTER INSERT OR UPDATE OR DELETE ON picks "
                "FOR EACH ROW EXECUTE FUNCTION log_picks_changes()")
    cur.execute("INSERT INTO picks (game_id) VALUES ('before')")     # the old trigger works
    cur.execute(MIG.read_text(encoding="utf-8"))
    cur.execute("INSERT INTO picks (game_id, stake_units, stake_reason) VALUES ('after', 2, 'two agree')")
    cur.execute("SELECT game_id, stake_units, stake_reason FROM picks_log ORDER BY log_id")
    assert cur.fetchall() == [("before", None, None), ("after", 2, "two agree")]
    cur.execute(MIG.read_text(encoding="utf-8"))                      # a second pass is a no-op
    cur.execute("INSERT INTO picks (game_id) VALUES ('again')")
    cur.execute("SELECT count(*) FROM picks_log")
    assert cur.fetchone() == (3,)
    raw.close()


def test_a_two_unit_pick_posts_its_stake_and_why():
    from tracking.discord_notifier import _signal_field
    base = {"label": "Duke @ Kansas — First Half Under 69.5", "sport": "NCAAB", "kelly": 0.02,
            "dk_odds": -110, "decision_odds": -110, "decision_book": "fanduel",
            "decision_odds_raw": -110, "best_book": "fanduel", "best_odds": -110}
    two = _signal_field({**base, "stake_units": 2,
                         "stake_reason": "Two models agree: NCAAB Totals also bet Kansas vs Duke Under 140.5"})
    assert "**2.2u to win 2u**" in two["value"]
    assert two["value"].endswith("Two models agree: NCAAB Totals also bet Kansas vs Duke Under 140.5")
    one = _signal_field({**base, "stake_units": None, "stake_reason": None})
    assert "**1.1u to win 1u**" in one["value"] and "agree" not in one["value"]
