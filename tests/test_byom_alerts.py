"""Alerts and open bets on members' own models (Matt, 2026-11-25, NFL first).

byom_alerts_2026_11_25.sql is hand applied. The scratch tests apply the
whole byom_legs chain, then this file twice, and drive byom/alerts.py
through the repo's DBConnection on that cluster. Nothing points at
DATABASE_URL.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SQL_NAME = "byom_alerts_2026_11_25.sql"
USER_A = "11111111-1111-1111-1111-111111111111"
USER_B = "22222222-2222-2222-2222-222222222222"

CHAIN = (
    "byom_facts_schema_2026_10_16.sql",
    "byom_dk_start_price_2026_10_23.sql",
    "byom_prop_facts_dk_prices_2026_10_28.sql",
    "byom_saved_models_2026_10_16.sql",
    "byom_prop_phase_a_filters_2026_10_29.sql",
    "byom_official_legs_2026_11_04.sql",
    "byom_official_lock_bands_2026_11_04.sql",
    "byom_official_legs_lock_read_idx_2026_11_04.sql",
    "byom_official_market_pushdown_2026_11_04.sql",
    "byom_prop_lookup_2026_11_04.sql",
    "byom_nhl_2026_11_05.sql",
    "byom_save_filters_2026_11_05.sql",
    "byom_units_inline_2026_11_05.sql",
    "byom_trend_filters_2026_11_05.sql",
    "byom_bets_actual_2026_11_17.sql",
    "byom_no_half_yards_2026_11_17.sql",
)


# ── static ───────────────────────────────────────────────────────────────────

def test_the_migration_is_hand_applied_and_never_touches_picks():
    from data.view_migrations import ACTIVE_MIGRATIONS
    from scripts.apply_anon_grants import MAY_BE_UNAPPLIED

    assert SQL_NAME not in ACTIVE_MIGRATIONS
    sql = (ROOT / "data/migrations" / SQL_NAME).read_text(encoding="utf-8")
    assert "HAND APPLIED" in sql
    assert "byom_open_bets_v1" in sql
    assert "auth.uid()" in sql
    assert "REVOKE ALL ON public.byom_alerts FROM PUBLIC, anon, authenticated" in sql
    assert "byom_alerts" not in MAY_BE_UNAPPLIED
    lowered = sql.lower()
    for banned in ("insert into picks", "discord", "update picks"):
        assert banned not in lowered
    code = (ROOT / "byom/alerts.py").read_text(encoding="utf-8").lower()
    for banned in ("insert into picks", "update picks", "from picks", "notify_discord"):
        assert banned not in code


def test_the_job_is_registered_nfl_and_ncaab():
    from tracking.job_queue import JOBS, _validate_byom_alerts

    assert "byom_alerts" in JOBS
    assert _validate_byom_alerts({}) == {"sport": "NFL", "rebuild": True}
    assert _validate_byom_alerts({"sport": " nfl ", "rebuild": False}) == {
        "sport": "NFL", "rebuild": False}
    assert _validate_byom_alerts({"sport": "ncaab"})["sport"] == "NCAAB"
    with pytest.raises(ValueError):
        _validate_byom_alerts({"sport": "NBA"})
    with pytest.raises(ValueError):
        _validate_byom_alerts({"rebuild": "yes"})


def test_every_refresh_pass_queues_the_alert_job():
    src = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    body = src[src.index("def run_refresh_pass"):src.index("def queue_byom_alerts")]
    assert "queue_byom_alerts(mode)" in body
    assert 'dedupe_key=f"byom-{sport.lower()}-alerts-{stamp}"' in src
    assert "for sport in ALERT_SPORTS" in src


def test_upcoming_games_are_today_through_two_days_and_not_started():
    from byom.alerts import upcoming_game_ids

    now = datetime(2026, 11, 26, 15, 0, tzinfo=timezone.utc)  # 10am ET Thursday
    games = [
        {"game_id": "early", "game_date": "2026-11-26",
         "commence_time": "2026-11-26T14:00:00+00:00"},          # started
        {"game_id": "late", "game_date": "2026-11-26",
         "commence_time": "2026-11-27T01:20:00+00:00"},
        {"game_id": "sun", "game_date": "2026-11-28", "commence_time": None},
        {"game_id": "far", "game_date": "2026-11-29",
         "commence_time": "2026-11-29T18:00:00+00:00"},          # 3 days out
        {"game_id": "past", "game_date": "2026-11-25",
         "commence_time": "2026-11-26T01:00:00+00:00"},
    ]
    assert upcoming_game_ids(games, today=now) == ["late", "sun"]


def test_the_push_body_is_the_stored_label_word_for_word():
    from byom.alerts import KIND, message_for
    from tracking.push_notifier import PUSH_ROUTE_VERSION

    one = {"model_id": "m1", "name": "Home favorites", "sport": "NFL",
           "bets": [{"alert_id": "a1", "label": "BUF +1"}]}
    title, body, data = message_for(one)
    assert title == "🔔 Home favorites: 1 new bet"
    assert body == "BUF +1"
    assert data == {"v": PUSH_ROUTE_VERSION, "type": KIND, "sport": "NFL",
                    "modelId": "m1", "alertId": "a1"}
    many = dict(one, bets=[{"alert_id": f"a{i}", "label": f"L{i}"} for i in range(5)])
    title, body, data = message_for(many)
    assert title == "🔔 Home favorites: 5 new bets"
    assert body == "L0 · L1 · L2 · +2 more"
    assert "alertId" not in data


def test_the_app_routes_the_alert_to_the_model():
    route = (ROOT / "mobile/src/lib/pushRoute.ts").read_text(encoding="utf-8")
    assert "byom_bet" in route
    assert "byomModel" in route


# ── scratch Postgres ─────────────────────────────────────────────────────────

@pytest.fixture
def scratch():
    psycopg2 = pytest.importorskip("psycopg2")
    from tests.byom_scratch import ScratchPostgres, pg_bin

    if pg_bin("initdb") is None:
        pytest.skip("initdb is not installed")
    cluster = ScratchPostgres()
    raw = None
    try:
        dsn = cluster.start()
        raw = psycopg2.connect(dsn)
        raw.autocommit = True
        cur = raw.cursor()
        cur.execute("""
            CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN;
            CREATE SCHEMA auth;
            CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
              SELECT NULLIF(current_setting('byom.uid', true), '')::uuid $$;
            GRANT USAGE ON SCHEMA auth TO anon, authenticated;
            CREATE TABLE device_push_tokens (
              token text, device_id text, user_id uuid, enabled boolean);
        """)
        for name in CHAIN:
            cur.execute((ROOT / "data/migrations" / name).read_text(encoding="utf-8"))
        sql = (ROOT / "data/migrations" / SQL_NAME).read_text(encoding="utf-8")
        cur.execute(sql)
        cur.execute(sql)  # the second run skips the patch and changes nothing
        cur.execute(f"""
            INSERT INTO byom_game_facts (
              canonical_key, sport, season, week, away_team, home_team,
              game_date, commence_time, line_basis, home_score, away_score,
              dk_spread_home, dk_total, home_rest_days, away_rest_days,
              home_role, away_role, is_primetime)
            VALUES
              ('2026_13_DET_BUF', 'NFL', 2026, 13, 'DET', 'BUF',
               (now() + interval '1 day')::date, now() + interval '1 day',
               'DraftKings line at game start', NULL, NULL,
               -1, 47.5, 7, 7, 'favorite', 'underdog', false),
              ('2026_13_NYJ_MIA', 'NFL', 2026, 13, 'NYJ', 'MIA',
               (now() - interval '1 hour')::date, now() - interval '1 hour',
               'DraftKings line at game start', NULL, NULL,
               -3, 41.5, 7, 7, 'favorite', 'underdog', false);
            INSERT INTO byom_official_legs (
              canonical_key, sport, season, market, leg_side, player_key,
              match_role, leg_role, team, locked_at, point, price, result)
            VALUES
              ('2026_13_DET_BUF', 'NFL', 2026, 'spreads', 'home', '', 'any',
               'favorite', 'BUF', now() - interval '2 hours', -1, -110, NULL),
              ('2026_13_DET_BUF', 'NFL', 2026, 'h2h', 'home', '', 'any',
               'favorite', 'BUF', now() - interval '2 hours', NULL, 1.91, NULL),
              ('2026_13_NYJ_MIA', 'NFL', 2026, 'spreads', 'home', '', 'any',
               'favorite', 'MIA', now() - interval '3 hours', -3, -110, NULL);
            INSERT INTO byom_models (model_id, user_id, name, sport, filters)
            VALUES
              ('aaaaaaaa-0000-0000-0000-000000000001', '{USER_A}', 'Home spreads',
               'NFL', '{{"markets":["spreads"],"side":"home"}}'),
              ('aaaaaaaa-0000-0000-0000-000000000002', '{USER_A}', 'Home ML',
               'NFL', '{{"markets":["h2h"],"side":"home"}}'),
              ('bbbbbbbb-0000-0000-0000-000000000001', '{USER_B}', 'B spreads',
               'NFL', '{{"markets":["spreads"],"side":"home"}}');
            INSERT INTO device_push_tokens VALUES
              ('ExponentPushToken[a]', 'dev-a', '{USER_A}', true);
        """)
        raw.autocommit = False
        from data.db import DBConnection
        yield psycopg2, raw, DBConnection(raw, url=dsn)
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()


def _open(cur, filters):
    cur.execute("SELECT canonical_key, market, leg_side, point, price, priced, result "
                "FROM byom_legs(2026, %s::jsonb, 'open') ORDER BY canonical_key, market",
                (filters,))
    return cur.fetchall()


def test_open_is_the_official_lock_on_games_not_started(scratch):
    _pg, raw, _conn = scratch
    cur = raw.cursor()
    rows = _open(cur, '{"markets":["spreads"],"side":"home"}')
    # BUF has not kicked off: its lock is open. MIA started an hour ago: gone.
    assert rows == [("2026_13_DET_BUF", "spreads", "home", -1, -110, True, None)]
    # The record timings are unchanged: an unplayed game is in neither.
    cur.execute("SELECT count(*) FROM byom_legs(2026, '{\"markets\":[\"spreads\"]}', 'official')")
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT count(*) FROM byom_legs(2026, '{\"markets\":[\"spreads\"]}', 'close')")
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT count(*) FROM byom_legs(2026, '{}', NULL) WHERE timing = 'open'")
    assert cur.fetchone()[0] == 0
    raw.rollback()
    with pytest.raises(Exception, match="official, close or open"):
        cur.execute("SELECT * FROM byom_legs(2026, '{}', 'later')")
    raw.rollback()


def test_a_bet_is_stored_once_and_a_moved_line_does_not_change_it(scratch, monkeypatch):
    _pg, raw, conn = scratch
    from byom import alerts

    sent = []
    monkeypatch.setattr("tracking.push_notifier._expo_send",
                        lambda messages, conn=None: sent.extend(messages) or len(messages))
    today = datetime.now(timezone.utc)
    report = alerts.run(conn, rebuild=False, today=today)
    assert report["status"] == "ok"
    assert report["announced"]["alerts"] == 2   # A's spread, B's spread; ML's 1.91 is not an American price
    cur = raw.cursor()
    cur.execute("SELECT user_id::text, label, price, notified_at IS NOT NULL "
                "FROM byom_alerts ORDER BY user_id")
    assert cur.fetchall() == [(USER_A, "BUF -1", -110, True), (USER_B, "BUF -1", -110, True)]
    # Only A has a device. The body is the label.
    assert [(m["to"], m["body"], m["data"]["type"]) for m in sent] == [
        ("ExponentPushToken[a]", "BUF -1", "byom_bet")]
    assert sent[0]["data"]["modelId"] == "aaaaaaaa-0000-0000-0000-000000000001"

    # The line moves: the next pass sees the same bet and stores nothing new.
    cur.execute("UPDATE byom_official_legs SET point = -2.5, price = -105 "
                "WHERE canonical_key = '2026_13_DET_BUF' AND market = 'spreads'")
    raw.commit()
    sent.clear()
    report = alerts.run(conn, rebuild=False, today=today)
    assert report["announced"]["alerts"] == 0
    assert sent == []
    cur.execute("SELECT count(*), min(price), min(label) FROM byom_alerts")
    assert cur.fetchone() == (2, -110, "BUF -1")


def test_alerts_off_finds_nothing(scratch, monkeypatch):
    _pg, raw, conn = scratch
    from byom import alerts

    monkeypatch.setattr("tracking.push_notifier._expo_send", lambda m, conn=None: 0)
    cur = raw.cursor()
    cur.execute("UPDATE byom_models SET alerts_enabled = false")
    raw.commit()
    report = alerts.run(conn, rebuild=False, today=datetime.now(timezone.utc))
    assert report["announced"]["alerts"] == 0


def test_member_rpcs_are_their_own_and_anon_has_none(scratch, monkeypatch):
    psycopg2, raw, conn = scratch
    from byom import alerts

    monkeypatch.setattr("tracking.push_notifier._expo_send", lambda m, conn=None: 0)
    alerts.run(conn, rebuild=False, today=datetime.now(timezone.utc))
    cur = raw.cursor()
    cur.execute("SET ROLE authenticated")
    cur.execute("SELECT set_config('byom.uid', %s, false)", (USER_A,))
    cur.execute("SELECT model_name, label, price, started FROM byom_my_open_bets()")
    assert cur.fetchall() == [("Home spreads", "BUF -1", -110, False)]
    cur.execute("SELECT model_id::text, alerts_enabled FROM byom_alert_settings() ORDER BY 1")
    assert [r[1] for r in cur.fetchall()] == [True, True]
    cur.execute("SELECT byom_set_alerts('aaaaaaaa-0000-0000-0000-000000000002', false)")
    assert cur.fetchone()[0] is False
    with pytest.raises(psycopg2.Error, match="model not found"):
        cur.execute("SELECT byom_set_alerts('bbbbbbbb-0000-0000-0000-000000000001', false)")
    raw.rollback()
    cur.execute("SET ROLE authenticated")
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        cur.execute("SELECT * FROM byom_alerts")
    raw.rollback()
    cur.execute("SET ROLE anon")
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        cur.execute("SELECT * FROM byom_my_open_bets()")
    raw.rollback()


def test_not_applied_does_nothing():
    from byom import alerts

    class Probe:
        def execute(self, *_a, **_k):
            raise RuntimeError("relation does not exist")

        def rollback(self):
            pass

    assert alerts.run(Probe(), today=date(2026, 11, 25)) == {
        "status": "not_applied", "sport": "NFL"}


# ── the app half ─────────────────────────────────────────────────────────────

MOBILE = ROOT / "mobile"


def test_the_app_checks_pass():
    import subprocess

    from tests._node import tsx_cmd

    cmd = tsx_cmd(MOBILE)
    if cmd is None:
        pytest.skip("mobile node modules not installed")
    run = subprocess.run([*cmd, "scripts/verify_byom_alerts.ts"], cwd=MOBILE,
                         capture_output=True, text=True, encoding="utf-8", timeout=180)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "all checks passed" in run.stdout


def test_cards_are_not_picks():
    """No track, betslip or Record path from an open-bet card."""
    for name in ("components/byom/ByomOpenBetCard.tsx", "components/byom/ByomOpenBetsSection.tsx",
                 "lib/byomAlerts.ts", "lib/byomAlertRows.ts"):
        text = (MOBILE / "src" / name).read_text(encoding="utf-8")
        for banned in ("useTrackedBets", "useParlaySlip", "PickDetail", "from('picks')"):
            assert banned not in text, (name, banned)
