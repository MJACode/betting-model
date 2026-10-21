"""Pinnacle market edge for game spreads and totals is the latest main line.

The same-line filter kept the last quote that still showed our number. When
Pinnacle had moved, that quote was hours before the close. The close is the
latest pre-start main line (MLB and NHL spreads stay on ±1.5). A different
number is NULL.

The historical rows are already standard_v2, so the Python capture will not
revisit them. data/migrations/clv_pinnacle_mainline_2026_10_14.sql copies
those rows and nulls the moved ones, once.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from tracking import paper_tracker as pt

ROOT = Path(__file__).parent.parent
V2 = ROOT / "data" / "migrations" / "clv_standard_v2_2026_10_14.sql"
MAIN = ROOT / "data" / "migrations" / "clv_pinnacle_mainline_2026_10_14.sql"

_GAME_COLS = ("home_price", "away_price", "draw_price", "spread_home",
              "total_line", "over_price", "under_price")


def _ts(v) -> datetime:
    s = str(v).replace("Z", "+00:00")
    return datetime.fromisoformat(s)


class _Res:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _Conn:
    """Answers the statements _capture_clv issues, and keeps the quote it chose."""

    def __init__(self, picks, quotes):
        self.picks, self.quotes = picks, quotes
        self.updates: list[dict] = []

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if s.startswith("SELECT p.pick_id"):
            cols = [c.strip().split(".")[-1] for c in s[7:s.index(" FROM picks")].split(",")]
            return _Res([tuple(p[c] for c in cols) for p in self.picks
                         if p["game_date"] == params[0]])
        if "FROM odds" in s:
            if "spread_home = %s" in s or "total_line = %s" in s:
                game_id, market, book, bound, line = params
            else:
                game_id, market, book, bound = params
                line = None
            rows = [q for q in self.quotes
                    if q[0] == book and q[1] == market and q[2] == game_id
                    and _ts(q[3]) <= _ts(bound)]
            if "snapshot_type != 'in_play'" in s or "snapshot_type <> 'in_play'" in s:
                rows = [q for q in rows if q[5] != "in_play"]
            rows.sort(key=lambda q: _ts(q[3]), reverse=True)
            if line is not None and "spreads" in market:
                rows = [q for q in rows if q[4].get("spread_home") == line]
            elif line is not None:
                rows = [q for q in rows if q[4].get("total_line") == line]
            elif "ABS(spread_home) = 1.5" in s:
                rows = [q for q in rows if abs(q[4].get("spread_home") or 0) == 1.5]
            return _Res([tuple(q[4].get(c) for c in _GAME_COLS) for q in rows[:1]])
        if s.startswith("UPDATE picks"):
            set_part = s[s.index(" SET ") + 5:s.index(" WHERE ")]
            keys, values, pi = [], [], 0
            params = list(params)
            for assign in set_part.split(","):
                key, expr = assign.split("=", 1)
                keys.append(key.strip())
                if "%s" in expr:
                    values.append(params[pi])
                    pi += 1
                elif expr.strip().upper() == "NULL":
                    values.append(None)
                else:
                    raise AssertionError(expr)
            keys.append("pick_id")
            values.append(params[pi])
            assert pi + 1 == len(params), s
            self.updates.append(dict(zip(keys, values)))
            return _Res([])
        raise AssertionError(f"unexpected statement: {s[:120]}")


def _pick(**kw):
    base = dict(
        pick_id=1, game_id="MLB_2026-09-20_NYY_BOS", model_id="mlb_over_under",
        pick_side="over", dk_odds=-110.0, commence_time="2026-09-20T23:05:00Z",
        pick_label="BOS vs NYY Over 8.5", scored_line=8.5,
        created_at="2026-09-20 15:00:00+00", prop_market=None, clv_method=None,
        decision_odds=None, decision_book=None, game_date="2026-09-20",
        game_time="2026-09-20T23:05:00Z",
    )
    base.update(kw)
    return base


def _q(game_id, book, market, at, cols, snapshot_type="open"):
    return (book, market, game_id, at, cols, snapshot_type)


def _dk_total(game_id, at, line=8.5, over=-120, under=100):
    return _q(game_id, "draftkings", "totals", at,
              dict(total_line=line, over_price=over, under_price=under))


def _pin_total(game_id, at, line, over, under, snapshot_type="open"):
    return _q(game_id, "pinnacle", "totals", at,
              dict(total_line=line, over_price=over, under_price=under),
              snapshot_type)


def _one(conn):
    assert len(conn.updates) == 1
    return conn.updates[0]


def test_market_edge_uses_the_latest_main_line_not_an_older_same_number():
    """The close is 8.5 at −130. An older 8.5 at −105 is not the close."""
    game = "MLB_2026-09-20_NYY_BOS"
    quotes = [
        _dk_total(game, "2026-09-20T22:50:00Z"),
        _pin_total(game, "2026-09-20T01:00:00Z", 8.5, -105, -115),
        _pin_total(game, "2026-09-20T22:40:00Z", 8.5, -130, 110),
    ]
    conn = _Conn([_pick()], quotes)
    assert pt._capture_clv(conn, "2026-09-20", "TS") == 1
    u = _one(conn)
    assert u["pinnacle_close_odds"] == -130
    assert u["market_clv_pct"] is not None
    assert u["clv_pct"] is not None


def test_a_moved_pinnacle_main_line_is_null_and_the_primary_stays():
    """Pinnacle's latest main total is 9.5. The 8.5 quote from 01:00 is not
    the close. DraftKings is still on 8.5, so the same-book primary stands."""
    game = "MLB_2026-09-20_NYY_BOS"
    quotes = [
        _dk_total(game, "2026-09-20T22:50:00Z", over=-120),
        _pin_total(game, "2026-09-20T01:00:00Z", 8.5, -105, -115),
        _pin_total(game, "2026-09-20T22:40:00Z", 9.5, -115, -105),
        # An in-play 8.5 after that must not put the number back.
        _pin_total(game, "2026-09-20T22:58:00Z", 8.5, -101, -119, "in_play"),
    ]
    conn = _Conn([_pick()], quotes)
    assert pt._capture_clv(conn, "2026-09-20", "TS") == 1
    u = _one(conn)
    assert u["pinnacle_close_odds"] is None
    assert u["market_clv_pct"] is None
    assert u["market_clv_pp"] is None
    assert u["market_clv_method"] is None
    assert u["clv_pct"] is not None
    assert u["closing_dk_odds"] == -120


def test_an_mlb_alternate_does_not_hide_the_main_run_line():
    """±1.5 is the main line. A later +2.5 is an alternate. The latest ±1.5
    is still +1.5, so that price is the market edge."""
    game = "MLB_2026-09-20_NYY_BOS"
    pick = _pick(model_id="mlb_runline", pick_side="away", scored_line=1.5,
                 pick_label="NYY +1.5", dk_odds=130.0)
    quotes = [
        _q(game, "draftkings", "spreads", "2026-09-20T22:50:00Z",
           dict(spread_home=1.5, home_price=-155, away_price=130)),
        _q(game, "pinnacle", "spreads", "2026-09-20T01:00:00Z",
           dict(spread_home=1.5, home_price=-150, away_price=100)),
        _q(game, "pinnacle", "spreads", "2026-09-20T22:20:00Z",
           dict(spread_home=1.5, home_price=-148, away_price=136)),
        _q(game, "pinnacle", "spreads", "2026-09-20T22:50:00Z",
           dict(spread_home=2.5, home_price=-200, away_price=180)),
    ]
    conn = _Conn([pick], quotes)
    assert pt._capture_clv(conn, "2026-09-20", "TS") == 1
    u = _one(conn)
    assert u["pinnacle_close_odds"] == 136
    assert u["market_clv_pct"] is not None


def test_an_mlb_main_line_that_flipped_sign_is_null():
    """The latest ±1.5 is −1.5. The old +1.5, and a later +2.5 alternate,
    are not the close."""
    game = "MLB_2026-09-20_NYY_BOS"
    pick = _pick(model_id="mlb_runline", pick_side="away", scored_line=1.5,
                 pick_label="NYY +1.5", dk_odds=130.0)
    quotes = [
        _q(game, "draftkings", "spreads", "2026-09-20T22:50:00Z",
           dict(spread_home=1.5, home_price=-155, away_price=130)),
        _q(game, "pinnacle", "spreads", "2026-09-20T01:00:00Z",
           dict(spread_home=1.5, home_price=-150, away_price=100)),
        _q(game, "pinnacle", "spreads", "2026-09-20T22:20:00Z",
           dict(spread_home=-1.5, home_price=-140, away_price=120)),
        _q(game, "pinnacle", "spreads", "2026-09-20T22:50:00Z",
           dict(spread_home=2.5, home_price=-200, away_price=180)),
    ]
    conn = _Conn([pick], quotes)
    assert pt._capture_clv(conn, "2026-09-20", "TS") == 1
    u = _one(conn)
    assert u["pinnacle_close_odds"] is None
    assert u["market_clv_pct"] is None
    assert u["closing_dk_odds"] == 130


# ── the migration, against a local Postgres ──────────────────────────────────

def _scratch():
    psycopg2 = pytest.importorskip("psycopg2")
    from tests.byom_scratch import ScratchPostgres, pg_bin

    if pg_bin("initdb") is None:
        if __import__("os").environ.get("GITHUB_ACTIONS"):
            pytest.fail("initdb is missing in CI — the migration test would skip")
        pytest.skip("initdb is not installed")
    cluster = ScratchPostgres()
    try:
        dsn = cluster.start()
    except Exception as exc:  # noqa: BLE001
        cluster.stop()
        pytest.skip(f"scratch cluster did not start: {exc}")
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    return cluster, conn


@pytest.fixture
def pg():
    cluster, conn = _scratch()
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()
        cluster.stop()


def _exec(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)


def _one_sql(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def _base_schema(conn):
    _exec(conn, """
        CREATE TABLE public.games (
          game_id text PRIMARY KEY,
          commence_time text
        );
        CREATE TABLE public.picks (
          pick_id bigint PRIMARY KEY,
          game_id text,
          model_id text,
          pick_side text,
          pick_label text,
          scored_line numeric,
          signal_type text,
          is_live boolean,
          dk_odds numeric,
          decision_odds numeric,
          decision_book text,
          prop_market text,
          created_at text,
          game_time text,
          closing_dk_odds numeric,
          closing_line numeric,
          clv_pct numeric,
          clv_pp numeric,
          line_clv_pts numeric,
          clv_beat_close boolean,
          clv_captured_at text,
          clv_method text,
          clv_close_book text,
          clv_bet_book text,
          market_clv_pct numeric,
          market_clv_pp numeric,
          market_clv_method text,
          pinnacle_close_odds numeric,
          result text
        );
        CREATE TABLE public.odds (
          game_id text,
          market text,
          bookmaker text,
          snapshot_type text,
          snapshot_at text,
          home_price numeric,
          away_price numeric,
          draw_price numeric,
          spread_home numeric,
          total_line numeric,
          over_price numeric,
          under_price numeric
        );
        CREATE TABLE public.player_prop_odds (
          game_id text,
          player_name text,
          market text,
          bookmaker text,
          snapshot_at text,
          over_price numeric,
          under_price numeric,
          line numeric
        );
        CREATE VIEW public.v_public_track_record AS
          SELECT 1::bigint AS clv_game_settled, 1 AS last_date;
    """)


def _market_fns(conn):
    _exec(conn, """
        CREATE FUNCTION public.clv_game_market(model_id text)
        RETURNS text LANGUAGE sql IMMUTABLE AS $fn$
          SELECT CASE model_id
            WHEN 'mlb_over_under' THEN 'totals'
            WHEN 'mlb_runline' THEN 'spreads'
            WHEN 'mlb_moneyline' THEN 'h2h'
            ELSE NULL
          END
        $fn$;
        CREATE FUNCTION public.clv_prop_key(model_id text)
        RETURNS text LANGUAGE sql IMMUTABLE AS $fn$
          SELECT CASE WHEN model_id LIKE '%prop%' THEN 'prop' ELSE NULL END
        $fn$;
    """)


def _run_file(conn, path: Path):
    _exec(conn, path.read_text(encoding="utf-8"))


def _game(conn, game_id, commence="2026-09-20T23:05:00Z"):
    _exec(conn,
          "INSERT INTO public.games (game_id, commence_time) VALUES (%s, %s)",
          (game_id, commence))


def _bet(conn, pick_id, game_id, model_id, scored_line, market_pct,
         pinnacle, clv_pct=1.25, method="standard_v2", signal="BET"):
    _exec(conn, """
        INSERT INTO public.picks (
          pick_id, game_id, model_id, pick_side, pick_label, scored_line,
          signal_type, is_live, dk_odds, created_at, game_time,
          clv_pct, clv_method, market_clv_pct, market_clv_pp,
          market_clv_method, pinnacle_close_odds, result
        ) VALUES (
          %s, %s, %s, 'over', 'label', %s,
          %s, false, -110, '2026-09-20T15:00:00Z', '2026-09-20T23:05:00Z',
          %s, %s, %s, 0.50, 'power', %s, 'WIN'
        )
    """, (pick_id, game_id, model_id, scored_line, signal, clv_pct, method,
          market_pct, pinnacle))


def _odds(conn, game_id, market, at, **cols):
    _exec(conn, """
        INSERT INTO public.odds (
          game_id, market, bookmaker, snapshot_type, snapshot_at,
          spread_home, total_line, over_price, under_price
        ) VALUES (%s, %s, 'pinnacle', %s, %s, %s, %s, %s, %s)
    """, (game_id, market, cols.get("snapshot_type", "open"), at,
          cols.get("spread_home"), cols.get("total_line"),
          cols.get("over_price"), cols.get("under_price")))


def _watch_rewrites(conn):
    _exec(conn, """
        CREATE TABLE public._rewrite_log (pick_id bigint);
        CREATE FUNCTION public._assert_backup_before_rewrite()
        RETURNS trigger LANGUAGE plpgsql AS $fn$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM public.clv_pinnacle_mainline_backup_2026_10_14 b
            WHERE b.pick_id = NEW.pick_id
          ) THEN
            RAISE EXCEPTION 'rewrite of % happened before its backup row', NEW.pick_id;
          END IF;
          INSERT INTO public._rewrite_log VALUES (NEW.pick_id);
          RETURN NEW;
        END
        $fn$;
        CREATE TRIGGER picks_backup_first
          BEFORE UPDATE ON public.picks
          FOR EACH ROW EXECUTE FUNCTION public._assert_backup_before_rewrite();
    """)


def test_backup_is_written_before_the_null_and_a_moved_line_becomes_null(pg):
    _base_schema(pg)
    _market_fns(pg)
    _watch_rewrites(pg)
    moved = "MLB_2026-09-20_NYY_BOS"
    held = "MLB_2026-09-20_LAD_SF"
    alt = "MLB_2026-09-20_CHC_STL"
    _game(pg, moved)
    _game(pg, held)
    _game(pg, alt)
    _game(pg, "MLB_2026-09-20_ATL_MIA")
    _bet(pg, 1, moved, "mlb_over_under", 8.5, 3.25, -105)
    _bet(pg, 2, held, "mlb_over_under", 8.5, 1.10, -120)
    _bet(pg, 3, alt, "mlb_runline", 1.5, 2.20, 100)
    _bet(pg, 2899429, moved, "mlb_over_under", 8.5, 9.99, -105)
    _bet(pg, 4, "MLB_2026-09-20_ATL_MIA", "mlb_moneyline", None, 4.00, -130)
    # Moved total. A later in-play quote back on 8.5 is not the close.
    _odds(pg, moved, "totals", "2026-09-20T01:00:00Z", total_line=8.5, over_price=-105)
    _odds(pg, moved, "totals", "2026-09-20T22:40:00Z", total_line=9.5, over_price=-115)
    _odds(pg, moved, "totals", "2026-09-20T22:58:00Z", total_line=8.5,
          over_price=-101, snapshot_type="in_play")
    # Latest main line is still 8.5. The older 8.5 is not the close.
    _odds(pg, held, "totals", "2026-09-20T01:00:00Z", total_line=8.5, over_price=-150)
    _odds(pg, held, "totals", "2026-09-20T22:40:00Z", total_line=8.5, over_price=-120)
    # Latest ±1.5 flipped. A later +2.5 alternate is not the main line.
    _odds(pg, alt, "spreads", "2026-09-20T01:00:00Z", spread_home=1.5, away_price=100)
    _odds(pg, alt, "spreads", "2026-09-20T22:20:00Z", spread_home=-1.5, away_price=120)
    _odds(pg, alt, "spreads", "2026-09-20T22:50:00Z", spread_home=2.5, away_price=180)

    _run_file(pg, MAIN)

    nulled = _one_sql(pg, """
        SELECT market_clv_pct, pinnacle_close_odds, clv_pct, signal_type, result
        FROM public.picks WHERE pick_id = 1
    """)
    assert nulled == (None, None, 1.25, "BET", "WIN")
    backed = _one_sql(pg, """
        SELECT market_clv_pct, pinnacle_close_odds
        FROM public.clv_pinnacle_mainline_backup_2026_10_14 WHERE pick_id = 1
    """)
    assert backed == (3.25, -105)
    held_row = _one_sql(pg,
        "SELECT market_clv_pct, pinnacle_close_odds FROM public.picks WHERE pick_id = 2")
    assert held_row == (1.10, -120)
    assert _one_sql(pg, """
        SELECT 1 FROM public.clv_pinnacle_mainline_backup_2026_10_14 WHERE pick_id = 2
    """) is None
    flipped = _one_sql(pg,
        "SELECT market_clv_pct FROM public.picks WHERE pick_id = 3")
    assert flipped == (None,)
    forbidden = _one_sql(pg,
        "SELECT market_clv_pct FROM public.picks WHERE pick_id = 2899429")
    assert forbidden == (9.99,)
    money = _one_sql(pg,
        "SELECT market_clv_pct FROM public.picks WHERE pick_id = 4")
    assert money == (4.00,)
    n_backup = _one_sql(pg, """
        SELECT count(*) FROM public.clv_pinnacle_mainline_backup_2026_10_14
    """)[0]
    assert n_backup == 2  # the moved total and the flipped run line
    n_rewrites = _one_sql(pg, "SELECT count(*) FROM public._rewrite_log")[0]
    assert n_rewrites == 2


def test_an_existing_backup_row_is_not_replaced(pg):
    _base_schema(pg)
    _market_fns(pg)
    _watch_rewrites(pg)
    game = "MLB_2026-09-20_NYY_BOS"
    _game(pg, game)
    _bet(pg, 1, game, "mlb_over_under", 8.5, 3.25, -105)
    _odds(pg, game, "totals", "2026-09-20T22:40:00Z", total_line=9.5, over_price=-115)
    _exec(pg, """
        CREATE TABLE public.clv_pinnacle_mainline_backup_2026_10_14
          (LIKE public.picks INCLUDING DEFAULTS);
        ALTER TABLE public.clv_pinnacle_mainline_backup_2026_10_14
          ADD COLUMN backed_up_at timestamptz NOT NULL DEFAULT now();
        ALTER TABLE public.clv_pinnacle_mainline_backup_2026_10_14
          ADD PRIMARY KEY (pick_id);
        INSERT INTO public.clv_pinnacle_mainline_backup_2026_10_14
          (pick_id, market_clv_pct, pinnacle_close_odds)
        VALUES (1, 50, -999);
    """)
    _run_file(pg, MAIN)
    assert _one_sql(pg, """
        SELECT market_clv_pct, pinnacle_close_odds
        FROM public.clv_pinnacle_mainline_backup_2026_10_14 WHERE pick_id = 1
    """) == (50, -999)
    assert _one_sql(pg, """
        SELECT market_clv_pct FROM public.picks WHERE pick_id = 1
    """) == (None,)


def test_a_second_pass_does_not_write(pg):
    _base_schema(pg)
    _market_fns(pg)
    _watch_rewrites(pg)
    game = "MLB_2026-09-20_NYY_BOS"
    _game(pg, game)
    _bet(pg, 1, game, "mlb_over_under", 8.5, 3.25, -105)
    _odds(pg, game, "totals", "2026-09-20T22:40:00Z", total_line=9.5, over_price=-115)
    _run_file(pg, MAIN)
    assert _one_sql(pg, "SELECT count(*) FROM public._rewrite_log")[0] == 1
    _game(pg, "MLB_2026-09-21_SEA_HOU")
    _bet(pg, 8, "MLB_2026-09-21_SEA_HOU", "mlb_over_under", 7.5, 6.00, -110,
         clv_pct=2.0)
    # Before this row's close bound, on a different number. A second pass
    # that still rewrote would null it.
    _odds(pg, "MLB_2026-09-21_SEA_HOU", "totals", "2026-09-20T22:00:00Z",
          total_line=8.5, over_price=-120)
    _run_file(pg, MAIN)
    assert _one_sql(pg, """
        SELECT market_clv_pct, pinnacle_close_odds FROM public.picks WHERE pick_id = 8
    """) == (6.00, -110)
    assert _one_sql(pg, "SELECT count(*) FROM public._rewrite_log")[0] == 1
    assert _one_sql(pg, """
        SELECT count(*) FROM public.clv_pinnacle_mainline_backup_2026_10_14
    """)[0] == 1
    assert _one_sql(pg, """
        SELECT count(*) FROM public.clv_pinnacle_mainline_once_2026_10_14
    """)[0] == 1


def test_the_applied_standard_v2_file_is_not_edited():
    """clv_standard_v2 has already run in production. The data fix is the
    new file, not a second edit of that migration."""
    text = V2.read_text(encoding="utf-8")
    assert "clv_standard_v2_once" not in text
    assert "clv_pinnacle_mainline" not in text


def test_both_migrations_are_on_the_worker_list_in_order():
    from data.view_migrations import ACTIVE_MIGRATIONS
    pick_units = "published_pick_units_2026_10_17.sql"
    units = "published_record_units_2026_10_16.sql"
    assert V2.name in ACTIVE_MIGRATIONS
    assert MAIN.name in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS.index(V2.name) < ACTIVE_MIGRATIONS.index(MAIN.name)
    assert ACTIVE_MIGRATIONS[-1] == units
    # The posted-stake functions and the view that reads them stay adjacent,
    # with the view last. This file is the entry immediately before that pair.
    assert ACTIVE_MIGRATIONS.index(pick_units) == ACTIVE_MIGRATIONS.index(units) - 1
    assert ACTIVE_MIGRATIONS.index(MAIN.name) == ACTIVE_MIGRATIONS.index(pick_units) - 1
    body = MAIN.read_text(encoding="utf-8")
    assert "v_public_track_record" not in body
    assert "profit_flat" not in body
    assert "SET result" not in body
    assert body.index("INSERT INTO public.clv_pinnacle_mainline_backup_2026_10_14") < body.index(
        "UPDATE public.picks")
    assert "2899429" in body and "2911172" in body
    assignment = body.split("UPDATE public.picks", 1)[1].split("FROM", 1)[0]
    columns = []
    for line in assignment.splitlines():
        if "=" not in line:
            continue
        name = line.split("=", 1)[0].strip()
        if name.startswith("SET "):
            name = name[4:].strip()
        columns.append(name)
    assert columns == [
        "market_clv_pct", "market_clv_pp", "market_clv_method", "pinnacle_close_odds",
    ]
