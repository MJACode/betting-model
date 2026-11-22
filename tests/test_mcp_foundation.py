"""AI assistant (MCP) connector: the database gate (mcp_foundation_2026_11_21.sql).

Every rule Matt set on 2026-11-20/21, run on a scratch cluster through the
worker's own apply path: paid and comped only (not trial), terms first,
10 questions a day where a burst of lookups is one question, 30 lookups a day,
5 a minute, founders unlimited, suspension, and nothing in mcp_meter readable
by anon, authenticated or the read role. Since 2026-11-22 (Matt): up to three
assistants per member, one shared daily pool, a reconnect is the same
assistant, and disconnect is per assistant (mcp_multi_assistant_2026_11_22.sql).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.view_migrations import ACTIVE_MIGRATIONS, _apply_one, _without_combined_anon_grants  # noqa: E402
from tests._pg import pg_bin, scratch_cluster  # noqa: E402
from tests.test_anon_lockdown import (  # noqa: E402
    MIGRATIONS, X, Y, _can, _fixture_sql, _psql, _psql_file, _sql_files)

PAID = X
TRIAL = Y
COMPED = "33333333-3333-3333-3333-333333333333"
NOBODY = "44444444-4444-4444-4444-444444444444"
REVIEW = "88888888-8888-8888-8888-888888888888"
MATT = "33f61a85-b7ee-4a00-9641-73600e410305"
T0 = "2026-11-21 15:00:00+00"  # 10:00 ET
# OAuth clients as Supabase Auth registers them: every reconnect is a new id.
CLAUDE_1 = "c1a0de00-0000-4000-8000-000000000001"
CLAUDE_2 = "c1a0de00-0000-4000-8000-000000000002"
CHATGPT = "c1a0de00-0000-4000-8000-000000000003"
GROK = "c1a0de00-0000-4000-8000-000000000004"
OTHER_APP = "c1a0de00-0000-4000-8000-000000000005"


def _now_utc() -> str:
    """mcp_my_status() reads TODAY in ET, so a call it should count is made now."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00")


def _member(dsn: str, who: str) -> None:
    _psql(dsn, f"""
      INSERT INTO auth.users (id) VALUES ('{who}');
      INSERT INTO public.access_grants (user_id, access_source) VALUES ('{who}', 'comped');
      INSERT INTO mcp_meter.terms_acceptances (user_id, terms_version) VALUES ('{who}', '2026-11-21');""")


def _status(dsn: str, who: str) -> dict:
    ok, out = _can(dsn, "authenticated", "SELECT public.mcp_my_status()::text;",
                   claims='{"sub": "%s"}' % who)
    assert ok, out
    return json.loads([ln for ln in out.splitlines() if ln.startswith("{")][-1])


class _Conn:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, q, params=None):
        cur = self.raw.cursor()
        cur.execute(q, params)
        return cur

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()


def _apply(dsn: str, name: str) -> None:
    import psycopg2
    sql = _without_combined_anon_grants(
        (MIGRATIONS / name).read_text(encoding="utf-8"))
    raw = psycopg2.connect(dsn)
    try:
        assert _apply_one(_Conn(raw), name, sql) is None
    finally:
        raw.close()


def _call(dsn: str, user: str, at: str, client: str = "claude", tool: str = "get_player_hit_rates") -> dict:
    out = _psql(dsn, f"""
      BEGIN;
      SET LOCAL ROLE mcp_meter_role;
      SELECT mcp_meter.begin_call('{user}'::uuid, '{client}', '{tool}', '{{}}'::jsonb, '{at}'::timestamptz)::text;
      COMMIT;""")
    line = [ln for ln in out.splitlines() if ln.startswith("{")][-1]
    return json.loads(line)


@pytest.fixture(scope="module")
def dsn():
    if not pg_bin("psql"):
        pytest.skip("psql is not installed")
    with scratch_cluster("mcp-foundation-") as d:
        _psql(d, _fixture_sql())
        _psql_file(d, _sql_files()["site"])
        _psql_file(d, _sql_files()["a"])
        _psql(d, f"""
          INSERT INTO auth.users (id) VALUES ('{COMPED}'), ('{NOBODY}'), ('{MATT}'), ('{REVIEW}'),
            ('a2f697f8-02e1-4006-b7b2-6f7a0999f62c');
          ALTER TABLE public.subscriptions ADD COLUMN IF NOT EXISTS trial_end timestamptz;
          INSERT INTO public.subscriptions (user_id, status, current_period_end, trial_end) VALUES
            ('{PAID}', 'active', now() + interval '20 days', NULL),
            ('{TRIAL}', 'trialing', now() + interval '5 days', now() + interval '5 days');
          INSERT INTO public.access_grants (user_id, access_source) VALUES
            ('{COMPED}', 'comped'), ('{REVIEW}', 'app_review');
        """)
        _apply(d, "app_founders_2026_11_20.sql")
        _apply(d, "mcp_foundation_2026_11_21.sql")
        _apply(d, "mcp_foundation_2026_11_21.sql")  # second pass: no-op
        _psql(d, f"""
          CREATE TABLE IF NOT EXISTS auth.oauth_clients (
            id uuid PRIMARY KEY, client_name text, redirect_uris text);
          INSERT INTO auth.oauth_clients VALUES
            ('c1a0de00-0000-4000-8000-000000000001', 'Claude',
             'https://claude.ai/api/mcp/auth_callback,https://claude.com/api/mcp/auth_callback'),
            ('{CLAUDE_2}', 'Claude', 'https://claude.ai/api/mcp/auth_callback'),
            ('{CHATGPT}', 'ChatGPT', 'https://chatgpt.com/connector_platform_oauth_redirect'),
            ('{GROK}', 'Grok', 'https://grok.com/connectors-oauth-exchange-code/'),
            ('{OTHER_APP}', 'Claude', 'https://evil.example/cb');
        """)
        _apply(d, "mcp_status_client_2026_11_21.sql")
        _apply(d, "mcp_status_client_2026_11_21.sql")  # second pass: no-op
        _apply(d, "mcp_session_revoke_2026_11_21.sql")
        _apply(d, "mcp_session_revoke_2026_11_21.sql")  # second pass: no-op
        _apply(d, "mcp_multi_assistant_2026_11_22.sql")
        _apply(d, "mcp_multi_assistant_2026_11_22.sql")  # second pass: no-op
        _psql(d, f"""
          INSERT INTO mcp_meter.terms_acceptances (user_id, terms_version) VALUES
            ('{PAID}', '2026-11-21'), ('{COMPED}', '2026-11-21'), ('{MATT}', '2026-11-21'),
            ('{TRIAL}', '2026-11-21'), ('{REVIEW}', '2026-11-21');
        """)
        yield d


def test_listed_after_the_founders_table():
    assert "mcp_foundation_2026_11_21.sql" in ACTIVE_MIGRATIONS
    assert (ACTIVE_MIGRATIONS.index("app_founders_2026_11_20.sql")
            < ACTIVE_MIGRATIONS.index("mcp_foundation_2026_11_21.sql"))


def test_entitlement(dsn):
    rows = _psql(dsn, f"""
      SELECT mcp_meter.entitlement('{PAID}'), mcp_meter.entitlement('{TRIAL}'),
             mcp_meter.entitlement('{COMPED}'), mcp_meter.entitlement('{NOBODY}'),
             mcp_meter.entitlement('{MATT}'), mcp_meter.entitlement('{REVIEW}');""").strip()
    assert rows == "paid|trial|comped|none|founder|app_review"


def test_trial_and_no_access_are_refused(dsn):
    assert _call(dsn, TRIAL, T0)["reason"] == "not_entitled"
    assert _call(dsn, NOBODY, T0)["reason"] == "not_entitled"


def test_terms_are_required_first(dsn):
    other = "55555555-5555-5555-5555-555555555555"
    _psql(dsn, f"""
      INSERT INTO auth.users (id) VALUES ('{other}');
      INSERT INTO public.access_grants (user_id, access_source) VALUES ('{other}', 'comped');""")
    assert _call(dsn, other, T0)["reason"] == "terms_required"


def test_a_burst_is_one_question_and_ten_is_the_cap(dsn):
    # Three lookups 20 s apart: one question.
    r1 = _call(dsn, PAID, "2026-11-21 15:00:00+00")
    r2 = _call(dsn, PAID, "2026-11-21 15:00:20+00")
    r3 = _call(dsn, PAID, "2026-11-21 15:00:40+00")
    assert [r1["questions_used"], r2["questions_used"], r3["questions_used"]] == [1, 1, 1]
    assert r3["questions_left"] == 9
    assert r3["resets_at"] == "2026-11-22T05:00:00+00:00"  # midnight ET
    # A gap over 2 minutes starts question 2.
    assert _call(dsn, PAID, "2026-11-21 15:03:00+00")["questions_used"] == 2
    # Questions 3..10, one lookup each, 3 minutes apart.
    used = []
    for i in range(8):
        minute = 6 + 3 * i
        used.append(_call(dsn, PAID, f"2026-11-21 15:{minute:02d}:00+00")["questions_used"])
    assert used == list(range(3, 11))
    eleventh = _call(dsn, PAID, "2026-11-21 16:00:00+00")
    assert eleventh["allowed"] is False and eleventh["reason"] == "limit_reached"
    assert eleventh["questions_left"] == 0
    # The next ET day starts over.
    assert _call(dsn, PAID, "2026-11-22 15:00:00+00")["questions_used"] == 1


def test_five_a_minute_and_thirty_a_day(dsn):
    out = [_call(dsn, COMPED, f"2026-11-21 15:00:{s:02d}+00")["reason"] for s in range(0, 60, 10)]
    assert out[:5] == ["ok"] * 5 and out[5] == "rate_limited"
    # Fill to 30 lookups in 5-lookup bursts that each stay one question:
    # 25 more, at 1 a minute so the per-minute cap never trips.
    reasons = []
    for i in range(25):
        reasons.append(_call(dsn, COMPED, f"2026-11-21 {16 + i // 60}:{i % 60:02d}:00+00")["reason"])
    total_ok = 5 + reasons.count("ok")
    assert total_ok <= 30
    after = _call(dsn, COMPED, "2026-11-21 18:00:00+00")
    assert after["allowed"] is False and after["reason"] == "limit_reached"


def test_founders_are_unlimited(dsn):
    for i in range(40):
        r = _call(dsn, MATT, f"2026-11-21 {15 + i // 50}:{i % 50:02d}:00+00")
        assert r["allowed"] is True, r
    assert r["unlimited"] is True and r["questions_left"] is None


def test_several_assistants_share_one_pool(dsn):
    """Matt, 2026-11-22: connect more than one assistant; the 10 are shared."""
    who = "66666666-6666-6666-6666-666666666666"
    _member(dsn, who)
    assert _call(dsn, who, T0, client=CLAUDE_1)["questions_used"] == 1
    # Another assistant 10 s later is its own question, from the same pool.
    r = _call(dsn, who, "2026-11-21 15:00:10+00", client=GROK)
    assert r["allowed"] is True and r["assistant"] == "grok"
    assert r["questions_used"] == 2 and r["questions_left"] == 8
    # Claude's follow-up lookup stays Claude's question; the pool does not go back.
    r = _call(dsn, who, "2026-11-21 15:00:20+00", client=CLAUDE_1)
    assert r["questions_used"] == 2 and r["questions_left"] == 8
    assert _call(dsn, who, "2026-11-21 15:00:30+00", client=CHATGPT)["questions_used"] == 3
    # Fill the pool from all three, 3 minutes apart (no burst, no rate limit).
    clients = [CLAUDE_1, GROK, CHATGPT]
    for i in range(7):
        r = _call(dsn, who, f"2026-11-21 15:{3 + 3 * i:02d}:00+00", client=clients[i % 3])
        assert r["allowed"] is True, r
    assert r["questions_used"] == 10 and r["questions_left"] == 0
    for c in clients:
        out = _call(dsn, who, "2026-11-21 16:00:00+00", client=c)
        assert out["allowed"] is False and out["reason"] == "limit_reached", (c, out)
        assert out["questions_left"] == 0
    # Midnight ET resets the pool for everyone.
    assert _call(dsn, who, "2026-11-22 15:00:00+00", client=GROK)["questions_used"] == 1


def test_a_reconnect_is_the_same_assistant_and_three_is_the_cap(dsn):
    """2026-11-22: a reconnected Claude registers a new client id and was refused."""
    who = "66666666-6666-6666-6666-666666666667"
    _member(dsn, who)
    for c in (CLAUDE_1, CHATGPT, GROK):
        assert _call(dsn, who, T0, client=c, tool="get_slate")["allowed"] is True, c
    # Claude reconnected: new client id, same assistant, let in at the cap.
    r = _call(dsn, who, "2026-11-21 15:05:00+00", client=CLAUDE_2)
    assert r["allowed"] is True and r["assistant"] == "claude"
    # A fourth DIFFERENT assistant is refused; a name it chose does not make it Claude.
    r = _call(dsn, who, "2026-11-21 15:06:00+00", client=OTHER_APP)
    assert r["allowed"] is False and r["reason"] == "app_limit" and r["assistant"] == "evil.example"
    assert r["max_assistants"] == 3
    # Nothing is replaced or deleted: four active client rows, three assistants.
    rows = _psql(dsn, f"""SELECT count(*), count(DISTINCT assistant) FROM mcp_meter.connections
                          WHERE user_id = '{who}' AND revoked_at IS NULL;""").strip()
    assert rows == "4|3"
    # Disconnecting one assistant frees a place.
    ok, err = _can(dsn, "authenticated", "SELECT public.mcp_disconnect_assistant('grok');",
                   claims='{"sub": "%s"}' % who, commit=True)
    assert ok, err
    assert _call(dsn, who, "2026-11-21 15:07:00+00", client=OTHER_APP)["allowed"] is True


def test_disconnect_is_per_assistant(dsn):
    who = "66666666-6666-6666-6666-666666666668"
    _member(dsn, who)
    assert _scall(dsn, who, "claude-s", T0, client=CLAUDE_1)["allowed"] is True
    assert _scall(dsn, who, "grok-s", "2026-11-21 15:01:00+00", client=GROK)["allowed"] is True
    ok, err = _can(dsn, "authenticated", "SELECT public.mcp_disconnect_assistant('grok');",
                   claims='{"sub": "%s"}' % who, commit=True)
    assert ok, err
    r = _scall(dsn, who, "grok-s", "2026-11-21 15:05:00+00", client=GROK)
    assert r["allowed"] is False and r["reason"] == "disconnected"
    assert _scall(dsn, who, "claude-s", "2026-11-21 15:05:00+00", client=CLAUDE_1)["allowed"] is True
    # The old no-argument Disconnect (older app builds) still ends every assistant.
    ok, err = _can(dsn, "authenticated", "SELECT public.mcp_disconnect();",
                   claims='{"sub": "%s"}' % who, commit=True)
    assert ok, err
    r = _scall(dsn, who, "claude-s", "2026-11-21 15:09:00+00", client=CLAUDE_1)
    assert r["allowed"] is False and r["reason"] == "disconnected"
    kept = _psql(dsn, f"SELECT count(*) FROM mcp_meter.connections WHERE user_id = '{who}';")
    assert kept.strip() == "2"  # kept, with revoked_at
    for role in ("anon",):
        ok, err = _can(dsn, role, "SELECT public.mcp_disconnect_assistant('claude');")
        assert not ok and "42501" in err


def test_status_lists_each_assistant(dsn):
    who = "66666666-6666-6666-6666-666666666669"
    _member(dsn, who)
    before = _status(dsn, who)
    assert before["assistants"] == [] and before["max_assistants"] == 3
    _call(dsn, who, _now_utc(), client=CLAUDE_1)
    _call(dsn, who, _now_utc(), client=GROK)
    _call(dsn, who, _now_utc(), client=CLAUDE_2)  # Claude reconnected
    st = _status(dsn, who)
    by = {a["assistant"]: a for a in st["assistants"]}
    assert set(by) == {"claude", "grok"}
    assert by["claude"]["client_host"] == "claude.ai" and by["grok"]["client_host"] == "grok.com"
    assert by["grok"]["questions_today"] == 1
    assert st["questions_used"] >= 2 and st["questions_left"] == 10 - st["questions_used"]
    assert st["connected_client"] is not None  # older builds still see a connected app
    # A call logged before the migration has no assistant column; it still
    # counts toward its assistant (review L1, 2026-11-22).
    _psql(dsn, f"""UPDATE mcp_meter.calls SET assistant = NULL
                    WHERE user_id = '{who}' AND client_id = '{GROK}';""")
    assert {a["assistant"]: a for a in _status(dsn, who)["assistants"]}["grok"]["questions_today"] == 1


def test_later_passes_never_restore_one_app(dsn):
    """Every MCP migration runs on every worker pass; none may undo v3."""
    for name in ("mcp_foundation_2026_11_21.sql", "mcp_status_client_2026_11_21.sql",
                 "mcp_session_revoke_2026_11_21.sql", "mcp_multi_assistant_2026_11_22.sql"):
        _apply(dsn, name)
    src = _psql(dsn, """
      SELECT position('mcp_meter v3' IN (SELECT prosrc FROM pg_proc
               WHERE oid = 'mcp_meter.begin_call(uuid,text,text,jsonb,timestamptz)'::regprocedure)) > 0,
             position('mcp_my_status v3' IN (SELECT prosrc FROM pg_proc
               WHERE oid = 'public.mcp_my_status()'::regprocedure)) > 0,
             to_regclass('mcp_meter.mcp_connections_one_active') IS NULL;""").strip()
    assert src == "t|t|t"
    assert (ACTIVE_MIGRATIONS.index("mcp_session_revoke_2026_11_21.sql")
            < ACTIVE_MIGRATIONS.index("mcp_multi_assistant_2026_11_22.sql"))


def test_suspension(dsn):
    who = "77777777-7777-7777-7777-777777777777"
    _psql(dsn, f"""
      INSERT INTO auth.users (id) VALUES ('{who}');
      INSERT INTO public.access_grants (user_id, access_source) VALUES ('{who}', 'comped');
      INSERT INTO mcp_meter.terms_acceptances (user_id, terms_version) VALUES ('{who}', '2026-11-21');
      INSERT INTO mcp_meter.suspensions (user_id, reason) VALUES ('{who}', 'test');""")
    assert _call(dsn, who, T0)["reason"] == "suspended"


def test_member_functions(dsn):
    ok, out = _can(dsn, "authenticated", "SELECT public.mcp_my_status()::text;",
                   claims='{"sub": "%s"}' % TRIAL)
    assert ok, out
    status = json.loads([ln for ln in out.splitlines() if ln.startswith("{")][-1])
    assert status["entitlement"] == "trial" and status["eligible"] is False
    assert status["trial_converts_at"] is not None
    ok, err = _can(dsn, "authenticated", "SELECT public.mcp_accept_terms('2026-11-21', 'claude');",
                   claims='{"sub": "%s"}' % NOBODY, commit=True)
    assert ok, err
    ok, err = _can(dsn, "authenticated", "SELECT public.mcp_accept_terms('1999-01-01');",
                   claims='{"sub": "%s"}' % NOBODY)
    assert not ok and "22023" in err
    for fn in ("public.mcp_my_status()", "public.mcp_disconnect()",
               "public.mcp_accept_terms('2026-11-21')"):
        ok, err = _can(dsn, "anon", f"SELECT {fn};")
        assert not ok and "42501" in err, fn


def test_nothing_in_the_meter_is_readable_outside_the_gate(dsn):
    for role in ("anon", "authenticated", "mcp_reader", "mcp_meter_role"):
        ok, err = _can(dsn, role, "SELECT 1 FROM mcp_meter.calls;")
        assert not ok and "42501" in err, role
    for role in ("anon", "authenticated", "mcp_reader"):
        ok, err = _can(dsn, role,
                       f"SELECT mcp_meter.begin_call('{PAID}', 'x', 'y', '{{}}'::jsonb, now());")
        assert not ok and "42501" in err, role
    # PostgREST logs in as authenticator and switches to anon/authenticated.
    # SET ROLE is checked against the LOGIN role, so the guarantee is that
    # none of those three can become the connector's roles.
    _psql(dsn, "DO $r$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
               "'authenticator') THEN CREATE ROLE authenticator NOINHERIT LOGIN; END IF; END $r$;"
               "GRANT anon, authenticated TO authenticator;")
    member = _psql(dsn, """
      SELECT bool_or(pg_has_role(r, m, 'MEMBER'))
        FROM unnest(ARRAY['authenticator', 'anon', 'authenticated']) r,
             unnest(ARRAY['mcp_reader', 'mcp_meter_role']) m;""")
    assert member.strip() == "f"


def test_app_review_sees_it_but_cannot_connect(dsn):
    """Matt, 2026-11-21: the reviewer can see the AI Assistant, not connect."""
    assert _call(dsn, REVIEW, T0)["reason"] == "not_entitled"
    ok, out = _can(dsn, "authenticated", "SELECT public.mcp_my_status()::text;",
                   claims='{"sub": "%s"}' % REVIEW)
    assert ok, out
    status = json.loads([ln for ln in out.splitlines() if ln.startswith("{")][-1])
    assert status["can_view"] is True and status["preview_only"] is True
    assert status["eligible"] is False


def test_status_names_the_connected_app(dsn):
    who = "99999999-9999-4999-8999-999999999999"
    client = "c1a0de00-0000-4000-8000-000000000001"
    _psql(dsn, f"""
      INSERT INTO auth.users (id) VALUES ('{who}');
      INSERT INTO public.access_grants (user_id, access_source) VALUES ('{who}', 'comped');
      INSERT INTO mcp_meter.terms_acceptances (user_id, terms_version) VALUES ('{who}', '2026-11-21');""")
    claims = '{"sub": "%s"}' % who
    ok, out = _can(dsn, "authenticated", "SELECT public.mcp_my_status()::text;", claims=claims)
    assert ok, out
    before = json.loads([ln for ln in out.splitlines() if ln.startswith("{")][-1])
    assert before["connected_client_name"] is None and before["connected_client_host"] is None
    assert _call(dsn, who, _now_utc(), client=client)["allowed"] is True
    ok, out = _can(dsn, "authenticated", "SELECT public.mcp_my_status()::text;", claims=claims)
    assert ok, out
    after = json.loads([ln for ln in out.splitlines() if ln.startswith("{")][-1])
    assert after["connected_client"] == client
    assert after["connected_client_name"] == "Claude"
    assert after["connected_client_host"] == "claude.ai"
    assert after["questions_used"] == 1 and after["questions_left"] == 9
    ok, err = _can(dsn, "anon", "SELECT public.mcp_my_status();")
    assert not ok and "42501" in err


def _scall(dsn: str, user: str, session: str, at: str, client: str = "claude") -> dict:  # noqa: E302
    out = _psql(dsn, f"""
      BEGIN;
      SET LOCAL ROLE mcp_meter_role;
      SELECT mcp_meter.begin_call_session('{user}'::uuid, '{client}', '{session}', 'get_slate',
                                          '{{}}'::jsonb, '{at}'::timestamptz)::text;
      COMMIT;""")
    return json.loads([ln for ln in out.splitlines() if ln.startswith("{")][-1])


def test_disconnect_cuts_the_app_off(dsn):
    """Disconnect must stop the app's existing sign-in, not just free the slot."""
    who = "aaaaaaaa-0000-4000-8000-00000000000a"
    _psql(dsn, f"""
      INSERT INTO auth.users (id) VALUES ('{who}');
      INSERT INTO public.access_grants (user_id, access_source) VALUES ('{who}', 'comped');
      INSERT INTO mcp_meter.terms_acceptances (user_id, terms_version) VALUES ('{who}', '2026-11-21');""")
    assert _scall(dsn, who, "s1", T0)["allowed"] is True
    assert _scall(dsn, who, "s2", "2026-11-21 15:01:00+00")["allowed"] is True  # second approval, same app
    ok, err = _can(dsn, "authenticated", "SELECT public.mcp_disconnect();",
                   claims='{"sub": "%s"}' % who, commit=True)
    assert ok, err
    for s in ("s1", "s2"):
        r = _scall(dsn, who, s, "2026-11-21 15:05:00+00")
        assert r["allowed"] is False and r["reason"] == "disconnected", (s, r)
    logged = _psql(dsn, f"SELECT count(*) FROM mcp_meter.calls WHERE user_id = '{who}' AND outcome = 'disconnected';")
    assert logged.strip() == "2"
    # A fresh approval is a new session, and works (the other app may take the slot too).
    assert _scall(dsn, who, "s3", "2026-11-21 15:06:00+00", client="chatgpt")["allowed"] is True
    ok, err = _can(dsn, "authenticated",
                   f"SELECT mcp_meter.begin_call_session('{who}', 'x', 's9', 'y', '{{}}'::jsonb, now());")
    assert not ok and "42501" in err
    for role in ("anon", "authenticated", "mcp_reader", "mcp_meter_role"):
        ok, err = _can(dsn, role, "SELECT 1 FROM mcp_meter.connection_sessions;")
        assert not ok and "42501" in err, role


def test_status_client_listed_after_the_views():
    i = ACTIVE_MIGRATIONS.index
    assert (i("mcp_stats_views_2026_11_21.sql") < i("mcp_status_client_2026_11_21.sql")
            < i("mcp_session_revoke_2026_11_21.sql"))


def test_stats_views_file_shape():
    """mcp_stats_views: listed after the foundation, one DO block, read role only.

    2026-11-21: its first draft skipped on obj_description('x'::regclass), which
    raises 42P01 before the view exists, so the first worker pass would have
    failed. The skip must go through to_regclass.
    """
    name = "mcp_stats_views_2026_11_21.sql"
    assert name in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS.index("mcp_foundation_2026_11_21.sql") < ACTIVE_MIGRATIONS.index(name)
    sql = (MIGRATIONS / name).read_text(encoding="utf-8")
    body = "\n".join(ln for ln in sql.splitlines() if not ln.strip().startswith("--"))
    assert body.strip().startswith("DO $views$") and body.strip().endswith("$views$;")
    assert "'mcp_stats.player_games'::regclass" not in body
    assert "obj_description(to_regclass('mcp_stats.player_games')" in body
    assert "GRANT SELECT ON ALL TABLES IN SCHEMA mcp_stats TO mcp_reader" in body
    import re
    assert not re.search(r"GRANT[^;]*\b(anon|authenticated)\b", body)
    for forbidden in ("source", "data_source", "bookmaker AS", "pick", "model"):
        assert not re.search(r"\b" + forbidden + r"\b\s*(,|$| AS)", body.split("CREATE OR REPLACE VIEW mcp_stats.books")[1], re.M), forbidden
