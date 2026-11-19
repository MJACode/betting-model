"""Model health: closing-line value per model, per bet and in blocks of 25/50/100.

mike, 2026-11-18: "rolling clv tracking per model in 25 bet increments for last
500 bets and 50 and 100 bet increments ... so we can truly assess health and
durability". data/migrations/model_health_2026_11_18.sql builds three views
the ops dashboard's Model Health tab reads.

The claim these tests hold it to: the views count exactly the published
record's bets, and their closing-line figures equal the record's own
(v_public_track_record) wherever the record has one. The record's filter is
read out of the record view itself, so the scratch database below carries a
copy of production's record view and the migration must find its filter there.

Runs data/view_migrations._apply_one, the worker's own path, on a scratch
database per test (LATEST_LINE_TEST_DSN or a throwaway cluster from
tests/_pg.py). Skips only where neither exists. Nothing here reaches
production.
"""
from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path

import pytest

from data.view_migrations import ACTIVE_MIGRATIONS

ROOT = Path(__file__).resolve().parents[1]
NAME = "model_health_2026_11_18.sql"
SQL = (ROOT / "data" / "migrations" / NAME).read_text(encoding="utf-8")
MARK = re.compile(r"model_health [0-9a-f]{12}")
VIEWS = ("v_model_health_bets", "v_model_health_windows", "v_model_health_summary")
ROLES = ("anon", "authenticated")


def _code(sql: str) -> str:
    """The SQL with -- comments removed, so a clause in a comment proves nothing."""
    return "\n".join(line.split("--", 1)[0] for line in sql.splitlines())


# ── the file itself ──────────────────────────────────────────────────────────

def test_the_mark_is_the_hash_of_the_file():
    found = MARK.findall(SQL)
    assert len(found) == 1, found
    blank = MARK.sub("model_health " + "0" * 12, SQL)
    want = "model_health " + hashlib.sha256(blank.encode("utf-8")).hexdigest()[:12]
    assert found[0] == want, f"set file_mark to '{want}'"


def test_it_is_one_statement_registered_before_the_posted_stake_pair():
    body = _code(SQL).strip()
    assert body.startswith("DO $mig$") and body.endswith("END $mig$;")
    assert body.count("$mig$") == 2
    assert ACTIVE_MIGRATIONS.count(NAME) == 1
    # After the three-argument unit functions it calls, before the pair.
    assert ACTIVE_MIGRATIONS.index("pick_stake_units_2026_11_06.sql") < ACTIVE_MIGRATIONS.index(NAME)
    assert ACTIVE_MIGRATIONS.index(NAME) < ACTIVE_MIGRATIONS.index("published_pick_units_2026_10_17.sql")
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"


def test_it_reads_the_record_view_and_never_rewrites_it():
    code = re.sub(r"\s+", " ", _code(SQL)).upper()
    assert "PG_GET_VIEWDEF('PUBLIC.V_PUBLIC_TRACK_RECORD'" in code
    for verb in ("VIEW PUBLIC.V_PUBLIC_TRACK_RECORD", "VIEW V_PUBLIC_TRACK_RECORD",
                 "ALTER VIEW", "DROP VIEW IF EXISTS PUBLIC.V_PUBLIC"):
        assert verb not in code, verb
    dropped = re.findall(r"DROP VIEW IF EXISTS PUBLIC\.([A-Z_]+)", code)
    assert dropped and all(v.startswith("V_MODEL_HEALTH_") for v in dropped), dropped


def test_it_does_not_write_a_pick():
    code = _code(SQL).upper()
    for verb in ("UPDATE PUBLIC.PICKS", "INSERT INTO", "DELETE FROM", "TRUNCATE"):
        assert verb not in code, verb


# ── on a real Postgres ───────────────────────────────────────────────────────

psycopg2 = pytest.importorskip("psycopg2")

from data.db import DBConnection  # noqa: E402
from data.view_migrations import _apply_one  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402


# Production's record view, as pg_get_viewdef printed it on 2026-11-18, with
# the select list cut to the columns these tests compare. The filter (WHERE)
# is verbatim: it is what the migration has to find and reuse.
RECORD_WHERE = r"""
  WHERE signal_type = 'BET'::text AND (is_live IS NOT TRUE OR model_id ~~ '%\_live\_%'::text) AND game_date >= '2026-09-01'::text AND NOT (model_id = 'mlb_over_under'::text AND game_date < '2026-07-05'::text) AND downgrade_reason IS DISTINCT FROM 'model paused'::text AND model_id <> 'nfl_live_prop'::text AND condition_status IS DISTINCT FROM 'DUPLICATE'::text AND (EXISTS ( SELECT 1
           FROM v_discord_published pub
          WHERE pub.lock_key =
                CASE
                    WHEN p.is_live THEN ((((((('live:'::text || p.game_id) || ':'::text) || p.model_id) || ':'::text) || p.pick_side) || COALESCE(':'::text || p.player_id, ''::text)) || COALESCE(':'::text || p.player_key, ''::text)) || COALESCE(':'::text || p.prop_market, ''::text)
                    ELSE ((((p.game_id || ':'::text) || p.model_id) || COALESCE(':'::text || p.player_id, ''::text)) || COALESCE(':'::text || p.player_key, ''::text)) || COALESCE(':'::text || p.prop_market, ''::text)
                END)) AND model_id <> 'ufc_moneyline'::text AND model_id <> 'ufc_total_rounds'::text AND model_id <> 'ufc_method_of_victory'::text
"""

RECORD_VIEW = r"""
CREATE OR REPLACE VIEW public.v_public_track_record AS
 SELECT sport, model_id,
    count(*) FILTER (WHERE result = ANY (ARRAY['WIN'::text, 'LOSS'::text, 'PUSH'::text])) AS picks,
    count(*) FILTER (WHERE (result = ANY (ARRAY['WIN'::text, 'LOSS'::text, 'PUSH'::text])) AND clv_pct IS NOT NULL AND clv_method = 'standard_v2'::text) AS clv_settled,
    count(*) FILTER (WHERE (result = ANY (ARRAY['WIN'::text, 'LOSS'::text, 'PUSH'::text])) AND clv_pct > 0::numeric AND clv_method = 'standard_v2'::text) AS clv_beat,
    avg(clv_pct) FILTER (WHERE (result = ANY (ARRAY['WIN'::text, 'LOSS'::text, 'PUSH'::text])) AND clv_pct IS NOT NULL AND clv_method = 'standard_v2'::text) AS avg_clv_pct,
    count(*) FILTER (WHERE (result = ANY (ARRAY['WIN'::text, 'LOSS'::text, 'PUSH'::text])) AND market_clv_pct IS NOT NULL AND clv_method = 'standard_v2'::text) AS market_clv_settled,
    avg(market_clv_pct) FILTER (WHERE (result = ANY (ARRAY['WIN'::text, 'LOSS'::text, 'PUSH'::text])) AND market_clv_pct IS NOT NULL AND clv_method = 'standard_v2'::text) AS avg_market_clv_pct,
    COALESCE(sum(published_pick_unit_profit(COALESCE(decision_odds, dk_odds), result, stake_units)) FILTER (WHERE result = ANY (ARRAY['WIN'::text, 'LOSS'::text, 'PUSH'::text])), 0::numeric) AS units,
    COALESCE(sum(published_pick_unit_risked(COALESCE(decision_odds, dk_odds), result, stake_units)) FILTER (WHERE result = ANY (ARRAY['WIN'::text, 'LOSS'::text, 'PUSH'::text])), 0::numeric) AS risked,
    count(*) FILTER (WHERE (result = ANY (ARRAY['WIN'::text, 'LOSS'::text, 'PUSH'::text])) AND clv_pct IS NOT NULL AND abs(clv_pct) < 0.005 AND clv_method = 'standard_v2'::text) AS clv_push
   FROM picks p
""" + RECORD_WHERE + """
  GROUP BY sport, model_id;
"""

SCHEMA = """
CREATE TABLE picks (
  pick_id bigint PRIMARY KEY, sport text, model_id text, game_id text, game_date text,
  created_at text, pick_label text, pick_side text, is_live boolean, result text,
  signal_type text, downgrade_reason text, condition_status text,
  player_id text, player_key text, prop_market text,
  decision_odds numeric, dk_odds numeric, stake_units numeric, profit_flat numeric,
  clv_bet_book text, closing_dk_odds numeric, scored_line numeric, closing_line numeric,
  clv_method text, clv_pct numeric, market_clv_pct numeric, line_clv_pts numeric);
CREATE TABLE push_sent (kind text, lock_key text);
CREATE VIEW v_discord_published AS SELECT lock_key, kind FROM push_sent;
CREATE FUNCTION published_pick_unit_profit(odds numeric, result text, stake numeric)
  RETURNS numeric LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE WHEN odds IS NULL THEN NULL
              WHEN result = 'WIN' THEN CASE WHEN odds > 0 THEN odds / 100 ELSE 1 END * COALESCE(stake, 1)
              WHEN result = 'LOSS' THEN -CASE WHEN odds > 0 THEN 1 ELSE -odds / 100 END * COALESCE(stake, 1)
              ELSE 0 END $$;
CREATE FUNCTION published_pick_unit_risked(odds numeric, result text, stake numeric)
  RETURNS numeric LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE WHEN odds IS NULL OR result = 'PUSH' THEN 0
              WHEN odds > 0 THEN 1 ELSE -odds / 100 END * COALESCE(stake, 1) $$;
"""


@pytest.fixture(scope="module")
def cluster():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("model-health-pg-") as d:
        yield d


_COUNTER = {"n": 0}


@pytest.fixture()
def db(cluster):
    _COUNTER["n"] += 1
    name = f"model_health_t{_COUNTER['n']}_{int(time.time() * 1000) % 10_000_000}"
    admin = psycopg2.connect(cluster)
    admin.autocommit = True
    with admin.cursor() as cur:
        for role in ROLES:
            cur.execute(f"DO $$ BEGIN CREATE ROLE {role} NOLOGIN; "
                        "EXCEPTION WHEN duplicate_object THEN NULL; END $$")
        cur.execute(f"CREATE DATABASE {name}")
    dsn = cluster.replace("dbname=postgres", f"dbname={name}")
    raw = psycopg2.connect(dsn)
    with raw.cursor() as cur:
        cur.execute(SCHEMA)
        cur.execute(RECORD_VIEW)
        # Supabase's default privileges hand new objects to the app roles;
        # the migration has to take them back.
        cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO anon, authenticated")
        cur.execute("CREATE TABLE ddl_seen (n integer NOT NULL)")
        cur.execute("INSERT INTO ddl_seen VALUES (0)")
        cur.execute("""CREATE FUNCTION count_ddl() RETURNS event_trigger LANGUAGE plpgsql AS
                       $$ BEGIN UPDATE ddl_seen SET n = n + 1; END $$""")
        cur.execute("CREATE EVENT TRIGGER count_ddl ON ddl_command_start EXECUTE FUNCTION count_ddl()")
    raw.commit()
    conn = DBConnection(raw, url=dsn)
    try:
        yield conn
    finally:
        try:
            raw.close()
        finally:
            with admin.cursor() as cur:
                cur.execute(f"DROP DATABASE IF EXISTS {name}")
            admin.close()


def _apply(conn, sql: str = SQL) -> None:
    err = _apply_one(conn, NAME, sql)
    assert err is None, err


def _ddl_seen(conn) -> int:
    n = conn.execute("SELECT n FROM ddl_seen").fetchone()[0]
    conn.commit()
    return int(n)


def _rows(conn, sql: str, params=None) -> list[dict]:
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur._cur.description]
    out = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.commit()
    return out


_ID = {"n": 0}


def _bet(conn, model: str, *, minute: int, result: str = "WIN", live: bool = False,
         posted: bool = True, method: str | None = "standard_v2", clv: float | None = None,
         line_pts: float | None = None, market: float | None = None, odds: float = -110,
         signal: str = "BET", game_date: str = "2026-11-10", **extra) -> int:
    _ID["n"] += 1
    pid = _ID["n"]
    game = f"G{pid}"
    side = extra.pop("side", "over")
    row = dict(pick_id=pid, sport=model.split("_")[0].upper(), model_id=model, game_id=game,
               game_date=game_date, created_at=f"2026-11-10 {minute // 60:02d}:{minute % 60:02d}:00+00",
               pick_label=f"label {pid}", pick_side=side, is_live=live, result=result,
               signal_type=signal, decision_odds=odds, dk_odds=odds, clv_bet_book="draftkings",
               clv_method=method, clv_pct=clv, line_clv_pts=line_pts, market_clv_pct=market)
    row.update(extra)
    cols = ", ".join(row)
    marks = ", ".join(["%s"] * len(row))
    conn.execute(f"INSERT INTO picks ({cols}) VALUES ({marks})", tuple(row.values()))
    if posted:
        tail = "".join(f":{row[k]}" for k in ("player_id", "player_key", "prop_market") if row.get(k))
        key = (f"live:{game}:{model}:{side}" if live else f"{game}:{model}") + tail
        conn.execute("INSERT INTO push_sent (kind, lock_key) VALUES ('discord_signal', %s)", (key,))
    conn.commit()
    return pid


def _seed(conn) -> None:
    """Every status, plus rows the record leaves out."""
    m = "nhl_moneyline"
    _bet(conn, m, minute=1, clv=2.50, market=1.10)            # price beat
    _bet(conn, m, minute=2, clv=0.00, market=-0.40)           # price push
    _bet(conn, m, minute=3, clv=-1.20, result="LOSS")         # price miss
    _bet(conn, m, minute=4, line_pts=1.0)                     # line moved our way
    _bet(conn, m, minute=5, line_pts=-0.5, result="LOSS")     # line moved against
    _bet(conn, m, minute=6, method="standard_v2")             # stamped, no close
    _bet(conn, m, minute=7, method=None)                      # never measured
    _bet(conn, m, minute=8, method="no_vig", clv=3.0)         # retired stamp
    _bet(conn, m, minute=9, clv=4.0, result="PUSH")
    _bet(conn, m, minute=10, clv=1.0, posted=False)           # never posted
    _bet(conn, m, minute=11, clv=1.0, result=None)            # not graded yet
    _bet(conn, m, minute=12, clv=1.0, signal="AVOID")         # not a bet
    _bet(conn, m, minute=13, clv=1.0, game_date="2026-08-20") # before the live date
    _bet(conn, m, minute=14, clv=1.0, condition_status="DUPLICATE")
    _bet(conn, m, minute=15, clv=1.0, downgrade_reason="model paused")
    _bet(conn, "mlb_live_total_runs", minute=16, live=True, method=None)  # in-play
    _bet(conn, "nba_prop_points", minute=17, live=True, clv=1.0)          # pre-game prop fired in-play
    _bet(conn, "ufc_total_rounds", minute=18, clv=5.0)                    # struck from the record
    _bet(conn, "nhl_prop_shots_on_goal", minute=19, clv=8.5, market=1.5, prop_market="player_shots_on_goal")
    _bet(conn, "nhl_prop_shots_on_goal", minute=20, clv=-2.0, result="LOSS", prop_market="player_shots_on_goal")


def test_every_count_and_average_equals_the_published_record(db):
    _seed(db)
    _apply(db)
    record = {r["model_id"]: r for r in _rows(db, "SELECT * FROM v_public_track_record")}
    summary = {r["model_id"]: r for r in _rows(db, "SELECT * FROM v_model_health_summary")}
    assert set(summary) == set(record) == {"nhl_moneyline", "mlb_live_total_runs", "nhl_prop_shots_on_goal"}
    for model, rec in record.items():
        s = summary[model]
        assert s["bets"] == rec["picks"], model
        assert s["price_n"] == rec["clv_settled"], model
        assert s["price_beat"] == rec["clv_beat"], model
        assert s["price_push"] == rec["clv_push"], model
        assert s["market_n"] == rec["market_clv_settled"], model
        assert s["units"] == rec["units"] and s["risked"] == rec["risked"], model
        for mine, theirs in (("avg_clv_pct", "avg_clv_pct"), ("avg_market_clv_pct", "avg_market_clv_pct")):
            if rec[theirs] is None:
                assert s[mine] is None, (model, mine)
            else:
                assert float(s[mine]) == pytest.approx(float(rec[theirs])), (model, mine)


def test_each_bet_gets_one_status_and_the_verdict_it_earned(db):
    _seed(db)
    _apply(db)
    rows = _rows(db, "SELECT model_id, status, verdict, clv_pct, line_clv_pts, seq FROM v_model_health_bets "
                     "WHERE model_id = 'nhl_moneyline' ORDER BY seq DESC")
    got = [(r["status"], r["verdict"]) for r in rows]
    assert got == [("price", "beat"), ("price", "push"), ("price", "miss"), ("line_for", "beat"),
                   ("line_against", "miss"), ("no_close", None), ("not_measured", None),
                   ("old_method", None), ("price", "beat")]
    # The retired stamp's number is not carried, as the record does not average it.
    assert [r["clv_pct"] for r in rows if r["status"] == "old_method"] == [None]
    assert [r["seq"] for r in rows] == list(range(9, 0, -1))
    live = _rows(db, "SELECT status, verdict FROM v_model_health_bets WHERE model_id = 'mlb_live_total_runs'")
    assert live == [{"status": "in_play", "verdict": None}]
    summary = _rows(db, "SELECT line_for, line_against, unmeasured, beat_rate_with_line, price_beat_rate "
                        "FROM v_model_health_summary WHERE model_id = 'nhl_moneyline'")[0]
    assert (summary["line_for"], summary["line_against"], summary["unmeasured"]) == (1, 1, 3)
    assert float(summary["price_beat_rate"]) == pytest.approx(2 / 3)
    assert float(summary["beat_rate_with_line"]) == pytest.approx(3 / 5)


def test_blocks_of_25_50_and_100_newest_first_over_the_last_500(db):
    for i in range(530):
        _bet(db, "nhl_prop_saves", minute=i, clv=float(i % 7) - 3.0, result="WIN" if i % 2 else "LOSS")
    _apply(db)
    w = _rows(db, "SELECT block_size, block_no, bets, newest_seq, oldest_seq, full_block, price_n "
                  "FROM v_model_health_windows WHERE model_id = 'nhl_prop_saves' "
                  "ORDER BY block_size, block_no")
    by = {}
    for r in w:
        by.setdefault(r["block_size"], []).append(r)
    assert [len(by[k]) for k in (25, 50, 100)] == [20, 10, 5]
    for size in (25, 50, 100):
        assert all(r["bets"] == size and r["full_block"] for r in by[size])
        assert by[size][0]["newest_seq"] == 1 and by[size][-1]["oldest_seq"] == 500
    # Newest block = the newest bets (largest created_at).
    newest = _rows(db, "SELECT max(created_at) AS t FROM v_model_health_bets WHERE model_id = 'nhl_prop_saves' AND seq <= 25")[0]["t"]
    overall = _rows(db, "SELECT max(created_at::timestamptz) AS t FROM picks WHERE model_id = 'nhl_prop_saves'")[0]["t"]
    assert newest == overall
    s = _rows(db, "SELECT bets, last25_price_n, last50_price_n, last100_price_n FROM v_model_health_summary "
                  "WHERE model_id = 'nhl_prop_saves'")[0]
    assert (s["bets"], s["last25_price_n"], s["last50_price_n"], s["last100_price_n"]) == (530, 25, 50, 100)


def test_a_short_history_has_one_short_block(db):
    for i in range(30):
        _bet(db, "nba_total_luck", minute=i, clv=1.0)
    _apply(db)
    w = _rows(db, "SELECT block_size, block_no, bets, full_block FROM v_model_health_windows "
                  "WHERE model_id = 'nba_total_luck' ORDER BY block_size, block_no")
    assert [(r["block_size"], r["block_no"], r["bets"], r["full_block"]) for r in w] == [
        (25, 1, 25, True), (25, 2, 5, False), (50, 1, 30, False), (100, 1, 30, False)]


def test_a_change_to_the_records_filter_reaches_these_views_on_the_next_pass(db):
    _seed(db)
    _apply(db)
    before = _ddl_seen(db)
    _apply(db)
    assert _ddl_seen(db) == before, "a second pass with nothing changed must not rebuild"
    db.execute(RECORD_VIEW.replace("AND model_id <> 'nfl_live_prop'::text",
                                   "AND model_id <> 'nfl_live_prop'::text AND model_id <> 'nhl_moneyline'::text"))
    db.commit()
    _apply(db)
    models = {r["model_id"] for r in _rows(db, "SELECT DISTINCT model_id FROM v_model_health_bets")}
    assert "nhl_moneyline" not in models
    assert models == {r["model_id"] for r in _rows(db, "SELECT model_id FROM v_public_track_record")}


def test_a_record_view_it_cannot_read_fails_loudly(db):
    db.execute("DROP VIEW public.v_public_track_record")
    db.execute("CREATE VIEW public.v_public_track_record AS "
               "SELECT sport, model_id, count(*) AS picks FROM (SELECT * FROM picks) q GROUP BY 1, 2")
    db.commit()
    err = _apply_one(db, NAME, SQL)
    assert err and "could not read the published record" in err


def test_the_app_roles_can_read_none_of_it(db):
    _apply(db)
    for view in VIEWS:
        for role in ROLES:
            got = _rows(db, "SELECT has_table_privilege(%s, %s, 'SELECT') AS ok", (role, f"public.{view}"))
            assert got == [{"ok": False}], (role, view)


def test_a_bet_placed_after_its_first_play_is_in_play(db):
    """mike, 2026-11-19: three NCAAF totals bet after kickoff "should be moved to
    live bets". Once game_first_play exists the views rebuild and read them as
    in-play; the record's own rows are untouched."""
    _apply(db)
    early = _bet(db, "ncaaf_over_under", minute=10, clv=1.0)
    late = _bet(db, "ncaaf_over_under", minute=20, clv=0.38)
    db.execute("""CREATE TABLE game_first_play (game_id text PRIMARY KEY, first_play_at timestamptz,
                  listed_start timestamptz, source text, source_id text, fetched_at timestamptz)""")
    for pid in (early, late):
        db.execute("INSERT INTO game_first_play (game_id, first_play_at, source) VALUES (%s, '2026-11-10 00:15:00+00', 'espn_wallclock')",
                   (f"G{pid}",))
    db.commit()
    before = {r["pick_id"]: r["status"] for r in _rows(db, "SELECT pick_id, status FROM v_model_health_bets")}
    assert before[late] == "price"                    # the views have not rebuilt yet
    _apply(db)
    after = {r["pick_id"]: r for r in _rows(db, "SELECT pick_id, status, clv_pct FROM v_model_health_bets")}
    assert after[early]["status"] == "price"
    assert after[late]["status"] == "in_play" and after[late]["clv_pct"] is None
