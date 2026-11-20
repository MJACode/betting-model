"""Steps A and B of the anon lockdown, on a scratch Postgres.

Authenticated keeps SELECT. Anon keeps site_public_record and the two
logging functions. tracked_bets rows belong to auth.uid(). The eight
personas differ only on has_app_access(); the tables do not.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.anon_lockdown_spec import (  # noqa: E402
    ANON_KEEP_FUNCTIONS,
    ANON_KEEP_RELATIONS,
    EXPECTED_ANON_EXECUTABLE,
    EXPECTED_ANON_GRANT_ONLY,
    EXPECTED_ANON_READABLE,
    EXPECTED_ANON_SEQUENCES,
    STEP_A_FUNCTIONS,
    STEP_A_HYGIENE,
    STEP_A_POLICIES,
    STEP_A_RELATIONS,
    STEP_B_DEVICE_FUNCTIONS,
    STEP_B_HYGIENE,
    STEP_B_POLICIES,
    STEP_B_RELATIONS,
    STEP_B_STATS_FUNCTIONS,
)
from data.view_migrations import ACTIVE_MIGRATIONS  # noqa: E402
from tests._pg import pg_bin, scratch_cluster  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "data" / "migrations"

X = "11111111-1111-1111-1111-111111111111"
Y = "22222222-2222-2222-2222-222222222222"


def _sql_files():
    return {
        "site": MIGRATIONS / "site_public_record_2026_11.sql",
        "a": MIGRATIONS / "anon_lockdown_step_a_2026_11.sql",
        "b": MIGRATIONS / "anon_lockdown_step_b_2026_11.sql",
        "undo_a": MIGRATIONS / "anon_lockdown_step_a_2026_11_undo.sql",
        "undo_b": MIGRATIONS / "anon_lockdown_step_b_2026_11_undo.sql",
    }


def _psql(dsn: str, sql: str) -> str:
    psql = pg_bin("psql")
    if not psql:
        pytest.skip("psql is not installed")
    proc = subprocess.run(
        [psql, dsn, "-v", "ON_ERROR_STOP=1", "-X", "-q", "-t", "-A"],
        input=sql, text=True, capture_output=True)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return proc.stdout


def _psql_file(dsn: str, path: Path) -> None:
    psql = pg_bin("psql")
    if not psql:
        pytest.skip("psql is not installed")
    proc = subprocess.run(
        [psql, dsn, "-v", "ON_ERROR_STOP=1", "-X", "-q", "-f", str(path)],
        text=True, capture_output=True)
    if proc.returncode != 0:
        raise AssertionError(f"{path.name}\n{proc.stderr}\n{proc.stdout}")


def _fixture_sql() -> str:
    rels = []
    views = []
    for name in (STEP_A_RELATIONS + STEP_A_HYGIENE
                 + STEP_B_RELATIONS + STEP_B_HYGIENE):
        if name in ("v_public_track_record", "v_public_track_record_daily",
                    "tracked_bets", "push_sent"):
            continue
        if name.startswith("v_") or name in (
                "open_picks", "confirmed_picks", "mv_scored_pick_outcomes"):
            views.append(name)
        else:
            rels.append(name)
    lines = [
        "CREATE ROLE anon NOLOGIN;",
        "CREATE ROLE authenticated NOLOGIN;",
        "CREATE ROLE service_role NOLOGIN BYPASSRLS;",
        "GRANT anon, authenticated, service_role TO postgres;",
        "CREATE SCHEMA IF NOT EXISTS auth;",
        """CREATE TABLE auth.users (id uuid PRIMARY KEY);""",
        f"INSERT INTO auth.users (id) VALUES ('{X}'), ('{Y}');",
        """
        CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
        LANGUAGE sql STABLE AS $$
          SELECT NULLIF(current_setting('request.jwt.claims', true)::json->>'sub','')::uuid
        $$;
        CREATE OR REPLACE FUNCTION auth.role() RETURNS text
        LANGUAGE sql STABLE AS $$
          SELECT current_setting('request.jwt.claim.role', true)
        $$;
        """,
        """
        CREATE TABLE public.subscriptions (
          user_id uuid PRIMARY KEY,
          status text,
          current_period_end timestamptz
        );
        CREATE TABLE public.access_grants (
          user_id uuid,
          access_source text,
          expires_at timestamptz
        );
        CREATE OR REPLACE FUNCTION public.has_app_access() RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
          SELECT auth.uid() IS NOT NULL AND (
            EXISTS (
              SELECT 1 FROM subscriptions s
               WHERE s.user_id = auth.uid()
                 AND s.status IN ('trialing', 'active')
                 AND (s.current_period_end IS NULL OR s.current_period_end > now())
            ) OR EXISTS (
              SELECT 1 FROM access_grants g
               WHERE g.user_id = auth.uid()
                 AND g.access_source IN ('comped', 'app_review')
                 AND (g.expires_at IS NULL OR g.expires_at > now())
            )
          );
        $$;
        REVOKE ALL ON FUNCTION public.has_app_access() FROM PUBLIC, anon;
        GRANT EXECUTE ON FUNCTION public.has_app_access() TO authenticated;
        """,
        """
        CREATE TABLE public.push_sent (
          lock_key text, kind text, sent_at timestamptz
        );
        ALTER TABLE public.push_sent ENABLE ROW LEVEL SECURITY;
        GRANT SELECT (lock_key, kind, sent_at) ON public.push_sent TO anon, authenticated;
        CREATE POLICY anon_read_discord_publish ON public.push_sent
          FOR SELECT TO anon, authenticated USING (true);
        -- Production's record view is security_invoker and reads push_sent
        -- (through v_discord_published), which step A takes from anon. A
        -- fixture without both let a site view that anon cannot read pass
        -- (2026-11-19: the website lost its record for minutes after step A).
        CREATE VIEW public.v_public_track_record WITH (security_invoker = on) AS
        SELECT t.* FROM (VALUES
          ('NBA', 'nba_live_total', 2::bigint, 1::bigint, 1::bigint, 0::bigint,
           1.25::numeric, 2::numeric, '2026-09-01', '2026-09-02'),
          ('NBA', 'nba_moneyline', 4::bigint, 4::bigint, 0::bigint, 0::bigint,
           9::numeric, 4::numeric, '2026-09-01', '2026-09-03'),
          ('NFL', 'nfl_spread', 1::bigint, 1::bigint, 0::bigint, 0::bigint,
           0.50::numeric, 1::numeric, '2026-10-01', '2026-10-01')
        ) AS t(sport, model_id, picks, wins, losses, pushes, units, risked,
               first_date, last_date)
        WHERE NOT EXISTS (SELECT 1 FROM public.push_sent p
                           WHERE p.lock_key = t.model_id AND p.kind = 'discord_void');
        CREATE VIEW public.v_public_track_record_daily AS
        SELECT '2026-09-01'::text AS game_date, 'NBA'::text AS sport, 1::bigint AS picks;
        """,
        """
        CREATE TABLE public.tracked_bets (
          id bigserial PRIMARY KEY,
          device_id text NOT NULL,
          pick_id bigint NOT NULL,
          game_id text,
          model_id text,
          pick_side text,
          player_id text,
          pick_label text,
          locked_odds numeric,
          locked_line numeric,
          game_date text,
          created_at text
        );
        ALTER TABLE public.tracked_bets ENABLE ROW LEVEL SECURITY;
        CREATE POLICY "anon insert tracked_bets" ON public.tracked_bets
          FOR INSERT TO anon, authenticated WITH CHECK (true);
        CREATE POLICY "anon delete tracked_bets" ON public.tracked_bets
          FOR DELETE TO anon, authenticated USING (true);
        """,
        "CREATE SEQUENCE public.picks_pick_id_seq;",
    ]
    for name in rels:
        lines.append(
            f"CREATE TABLE public.{name} (id int);"
            f"ALTER TABLE public.{name} ENABLE ROW LEVEL SECURITY;")
    for name in views:
        if name == "mv_scored_pick_outcomes":
            lines.append(
                "CREATE MATERIALIZED VIEW public.mv_scored_pick_outcomes AS "
                "SELECT 1 AS id;")
        else:
            lines.append(f"CREATE VIEW public.{name} AS SELECT 1 AS id;")
    for policy, table, _roles in STEP_A_POLICIES + STEP_B_POLICIES:
        if table in ("push_sent",):
            continue
        roles = "PUBLIC" if _roles == "public" else "anon, authenticated"
        qual = "true"
        if policy == "service_role_all":
            lines.append(
                "CREATE POLICY service_role_all ON public.game_weather "
                "FOR ALL TO PUBLIC USING (auth.role() = 'service_role');")
            continue
        lines.append(
            f'CREATE POLICY "{policy}" ON public.{table} '
            f"FOR SELECT TO {roles} USING ({qual});")
    lines.append(
        "GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon, authenticated, service_role;")
    lines.append(
        "REVOKE ALL ON public.push_sent FROM anon;"
        "GRANT SELECT (lock_key, kind, sent_at) ON public.push_sent "
        "TO anon, authenticated;"
        "REVOKE ALL ON public.subscriptions FROM anon;"
        "REVOKE ALL ON public.access_grants FROM anon;")
    fns = (STEP_A_FUNCTIONS + STEP_B_STATS_FUNCTIONS + STEP_B_DEVICE_FUNCTIONS)
    for sig in fns:
        if sig.endswith("()"):
            if "log_picks_changes" in sig:
                lines.append(
                    "CREATE FUNCTION public.log_picks_changes() RETURNS trigger "
                    "LANGUAGE plpgsql AS $$ BEGIN RETURN NULL; END $$;")
            else:
                lines.append(
                    f"CREATE FUNCTION {sig} RETURNS integer "
                    "LANGUAGE sql AS $$ SELECT 1 $$;")
        else:
            lines.append(
                f"CREATE FUNCTION {sig} RETURNS integer "
                "LANGUAGE sql AS $$ SELECT 1 $$;")
    lines.append(
        """
        CREATE FUNCTION public.log_app_error(
          text, text, text, text, text, text, text, text, text, text, text,
          timestamp with time zone, jsonb) RETURNS void
        LANGUAGE sql AS $$ SELECT NULL::void $$;
        CREATE FUNCTION public.log_app_timings(text, jsonb, text, text, text)
        RETURNS void LANGUAGE sql AS $$ SELECT NULL::void $$;
        GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO PUBLIC, anon, authenticated;
        REVOKE ALL ON FUNCTION public.has_app_access() FROM PUBLIC, anon;
        GRANT EXECUTE ON FUNCTION public.has_app_access() TO authenticated;
        """)
    return "\n".join(lines)


def _can(dsn: str, role: str, statement: str, claims: str | None = None,
         commit: bool = False) -> tuple[bool, str]:
    claim = ""
    if claims:
        claim = (
            "SELECT set_config('request.jwt.claims', "
            f"'{claims}', true);\n")
    end = "COMMIT;" if commit else "ROLLBACK;"
    sql = f"""
    \\set VERBOSITY verbose
    BEGIN;
    {claim}
    SET LOCAL ROLE {role};
    {statement}
    {end}
    """
    psql = pg_bin("psql")
    proc = subprocess.run(
        [psql, dsn, "-v", "ON_ERROR_STOP=1", "-X", "-q", "-t", "-A"],
        input=sql, text=True, capture_output=True)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout)
    return True, proc.stdout


def test_the_lockdown_files_are_not_auto_applied():
    banned = {
        "site_public_record_2026_11.sql",
        "anon_lockdown_step_a_2026_11.sql",
        "anon_lockdown_step_b_2026_11.sql",
        "anon_lockdown_step_a_2026_11_undo.sql",
        "anon_lockdown_step_b_2026_11_undo.sql",
    }
    assert banned.isdisjoint(ACTIVE_MIGRATIONS)


def test_discord_and_edge_functions_do_not_read_as_anon():
    """Discord and the worker use DATABASE_URL. Edge functions use the service
    role for table work, or the anon key only for Auth API calls."""
    discord = (ROOT / "tracking" / "discord_notifier.py").read_text(encoding="utf-8")
    assert "get_connection" in discord
    functions = ROOT / "supabase" / "functions"
    for name in (
        "app-review-sign-in", "discord-link", "sharpsports",
        "sharpsports-webhook", "revenuecat-webhook", "stripe-webhook",
        "stripe-checkout", "stripe-portal", "whop-webhook",
    ):
        src = (functions / name / "index.ts").read_text(encoding="utf-8")
        assert "SERVICE_ROLE" in src, name
    review = (functions / "app-review-sign-in" / "index.ts").read_text(encoding="utf-8")
    assert "verifyOtp" in review
    link = (functions / "discord-link" / "index.ts").read_text(encoding="utf-8")
    assert "getUser" in link


def test_spec_counts_match_the_baseline():
    assert EXPECTED_ANON_READABLE == 97
    assert EXPECTED_ANON_GRANT_ONLY == 20
    assert EXPECTED_ANON_EXECUTABLE == 82
    assert EXPECTED_ANON_SEQUENCES == 67
    assert ANON_KEEP_FUNCTIONS == {
        "log_app_error", "log_app_timings", "save_device_push_token",
        "site_public_record_rows"}


def test_steps_a_and_b_on_scratch_postgres():
    files = _sql_files()
    with scratch_cluster("lockdown-pg-") as dsn:
        _psql(dsn, _fixture_sql())
        _psql_file(dsn, files["site"])
        # Retired nba_moneyline is out. NBA keeps the live model only.
        rows = _psql(dsn, "SELECT sport, picks, wins FROM site_public_record ORDER BY sport;")
        assert "NBA|2|1" in rows.replace(" ", "")
        assert "NFL|1|1" in rows.replace(" ", "")
        cols = _psql(
            dsn,
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'site_public_record' "
            "ORDER BY 1;")
        for banned in ("model_id", "edge", "model_probability", "kelly_fraction"):
            assert banned not in cols.split()
        explain = _psql(dsn, "EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM site_public_record;")
        times = re.findall(r"Execution Time: ([0-9.]+) ms", explain)
        assert times, explain
        assert float(times[-1]) < 300

        _psql_file(dsn, files["a"])
        _psql_file(dsn, files["a"])  # re-run
        ok, err = _can(dsn, "anon", "SELECT 1 FROM picks;")
        assert not ok and "42501" in err
        ok, err = _can(dsn, "anon", "SELECT 1 FROM mv_scored_pick_outcomes;")
        assert not ok and "42501" in err
        ok, _ = _can(dsn, "anon", "SELECT 1 FROM games;")
        assert ok, "after A, anon still reads scoreboard tables"
        _psql(dsn, "INSERT INTO picks (id) VALUES (1);")
        ok, _ = _can(dsn, "authenticated", "SELECT 1 FROM picks;")
        assert ok
        ok, err = _can(dsn, "anon", "SELECT sport, picks FROM site_public_record;")
        assert ok, f"after A, anon lost the website record: {err}"
        ok, err = _can(dsn, "anon", "SELECT public.byom_record(1, '{}'::jsonb);")
        assert not ok and "42501" in err
        ok, _ = _can(dsn, "authenticated", "SELECT public.byom_record(1, '{}'::jsonb);")
        assert ok
        ok, _ = _can(dsn, "anon", "SELECT public.team_stats_board('nba', 2026);")
        assert ok, "stats RPCs stay anon-callable until step B"

        _psql(dsn, "CREATE SCHEMA lockdown_other;")
        _psql_file(dsn, files["b"])
        _psql_file(dsn, files["b"])
        ok, err = _can(dsn, "anon", "SELECT 1 FROM games;")
        assert not ok and "42501" in err
        ok, err = _can(dsn, "anon", "SELECT 1 FROM golf_tournaments;")
        assert not ok
        ok, _ = _can(dsn, "anon", "SELECT sport, picks FROM site_public_record;")
        assert ok
        ok, _ = _can(dsn, "anon", "SELECT public.log_app_error("
                    "'d','k','m',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,now(),'{}'::jsonb);")
        assert ok
        ok, err = _can(dsn, "anon", "SELECT public.team_stats_board('nba', 2026);")
        assert not ok and "42501" in err
        ok, err = _can(dsn, "anon", "SELECT public.feedback_unread_count('d');")
        assert not ok
        # A function created after step B must not be executable by anon.
        # The per-schema PUBLIC revoke does not do this. The global one does.
        _psql(dsn, "CREATE FUNCTION public.fresh_after_b() RETURNS int "
                  "LANGUAGE sql AS $$ SELECT 1 $$;")
        ok, err = _can(dsn, "anon", "SELECT public.fresh_after_b();")
        assert not ok and "42501" in err
        _psql(dsn, "GRANT USAGE ON SCHEMA lockdown_other TO anon; "
                  "CREATE FUNCTION lockdown_other.fresh() RETURNS int "
                  "LANGUAGE sql AS $$ SELECT 1 $$;")
        ok, err = _can(dsn, "anon", "SELECT lockdown_other.fresh();")
        assert ok, err
        ok, err = _can(
            dsn, "anon",
            "SELECT public.save_device_push_token('t','device-1','ios',false,'n');")
        assert ok, err
        ok, _ = _can(dsn, "authenticated", "SELECT 1 FROM picks;")
        assert ok
        ok, _ = _can(dsn, "authenticated", "SELECT 1 FROM nba_player_game_log;")
        assert ok
        ok, _ = _can(dsn, "authenticated", "SELECT public.player_window_totals_nba(2026, 10);")
        assert ok
        # service role and the owner (worker / Discord) still read.
        ok, _ = _can(dsn, "service_role", "SELECT 1 FROM picks;")
        assert ok
        assert "1" in _psql(dsn, "SELECT count(*) FROM picks;")

        # Personas. The tables do not care. has_app_access does.
        _psql(dsn, f"""
          INSERT INTO subscriptions (user_id, status, current_period_end)
          VALUES ('{Y}', 'trialing', now() + interval '3 days');
        """)
        for label, uid, expected in (
            ("free", X, "f"),
            ("trial", Y, "t"),
        ):
            ok, out = _can(
                dsn, "authenticated", "SELECT public.has_app_access();",
                claims='{"sub": "%s"}' % uid)
            assert ok, out
            assert expected in out.replace(" ", ""), label
        _psql(dsn, f"DELETE FROM subscriptions WHERE user_id = '{Y}';")
        _psql(dsn, f"""
          INSERT INTO subscriptions (user_id, status, current_period_end)
          VALUES ('{Y}', 'active', now() + interval '30 days');
        """)
        ok, out = _can(dsn, "authenticated", "SELECT public.has_app_access();",
                       claims='{"sub": "%s"}' % Y)
        assert ok and "t" in out
        _psql(dsn, f"UPDATE subscriptions SET current_period_end = now() - interval '1 day' WHERE user_id = '{Y}';")
        ok, out = _can(dsn, "authenticated", "SELECT public.has_app_access();",
                       claims='{"sub": "%s"}' % Y)
        assert ok and "f" in out
        _psql(dsn, f"DELETE FROM subscriptions WHERE user_id = '{Y}';")
        _psql(dsn, f"INSERT INTO access_grants (user_id, access_source) VALUES ('{Y}', 'comped');")
        ok, out = _can(dsn, "authenticated", "SELECT public.has_app_access();",
                       claims='{"sub": "%s"}' % Y)
        assert ok and "t" in out
        _psql(dsn, f"UPDATE access_grants SET access_source = 'app_review' WHERE user_id = '{Y}';")
        ok, out = _can(dsn, "authenticated", "SELECT public.has_app_access();",
                       claims='{"sub": "%s"}' % Y)
        assert ok and "t" in out
        _psql(dsn, f"UPDATE access_grants SET expires_at = now() - interval '1 day' WHERE user_id = '{Y}';")
        ok, out = _can(dsn, "authenticated", "SELECT public.has_app_access();",
                       claims='{"sub": "%s"}' % Y)
        assert ok and "f" in out
        # Expired still reads picks. That split is step C/D, not this PR.
        ok, _ = _can(dsn, "authenticated", "SELECT 1 FROM picks;",
                     claims='{"sub": "%s"}' % Y)
        assert ok

        # tracked_bets cross-user.
        ok, err = _can(
            dsn, "authenticated",
            "INSERT INTO tracked_bets (device_id, pick_id) VALUES ('d1', 7);",
            claims='{"sub": "%s"}' % X, commit=True)
        assert ok, err
        owner = _psql(dsn, "SELECT user_id::text FROM tracked_bets WHERE device_id = 'd1';")
        assert X in owner
        ok, err = _can(
            dsn, "authenticated",
            f"INSERT INTO tracked_bets (device_id, pick_id, user_id) "
            f"VALUES ('d2', 8, '{Y}');",
            claims='{"sub": "%s"}' % X)
        assert not ok and ("42501" in err or "row-level security" in err)
        deleted = _psql(dsn, f"""
          BEGIN;
          SELECT set_config('request.jwt.claims', '{{"sub": "{Y}"}}', true);
          SET LOCAL ROLE authenticated;
          WITH gone AS (
            DELETE FROM tracked_bets WHERE device_id = 'd1' RETURNING 1
          )
          SELECT count(*) FROM gone;
          ROLLBACK;
        """)
        assert deleted.strip().endswith("0")
        assert "1" in _psql(dsn, "SELECT count(*) FROM tracked_bets WHERE device_id = 'd1';")
        seen = _psql(dsn, f"""
          BEGIN;
          SELECT set_config('request.jwt.claims', '{{"sub": "{Y}"}}', true);
          SET LOCAL ROLE authenticated;
          SELECT count(*) FROM tracked_bets;
          ROLLBACK;
        """)
        assert seen.strip().endswith("0")
        ok, err = _can(dsn, "anon",
                       "INSERT INTO tracked_bets (device_id, pick_id) VALUES ('z', 1);")
        assert not ok
        ok, err = _can(dsn, "anon", "DELETE FROM tracked_bets;")
        assert not ok
        # Legacy null owner: the worker still sees it, the API select does not.
        # untrack_tracked_bet deletes it when no other account used the device.
        _psql(dsn, "INSERT INTO tracked_bets (device_id, pick_id, user_id) "
                  "VALUES ('legacy-device', 9, NULL);")
        assert "legacy-device" in _psql(
            dsn, "SELECT device_id FROM tracked_bets WHERE device_id = 'legacy-device';")
        hidden = _psql(dsn, f"""
          BEGIN;
          SELECT set_config('request.jwt.claims', '{{"sub": "{X}"}}', true);
          SET LOCAL ROLE authenticated;
          SELECT count(*) FROM tracked_bets WHERE device_id = 'legacy-device';
          ROLLBACK;
        """)
        assert hidden.strip().endswith("0")
        ok, err = _can(
            dsn, "authenticated",
            "SELECT public.untrack_tracked_bet('legacy-device', 9);",
            claims='{"sub": "%s"}' % X, commit=True)
        assert ok, err
        assert "0" in _psql(
            dsn, "SELECT count(*) FROM tracked_bets WHERE device_id = 'legacy-device';")
        _psql(dsn, """
          CREATE TABLE public.app_timings (device_id text, user_id uuid);
          INSERT INTO public.app_timings (device_id, user_id)
          VALUES ('other-device', '%s');
          INSERT INTO public.tracked_bets (device_id, pick_id, user_id)
          VALUES ('other-device', 11, NULL);
        """ % Y)
        ok, err = _can(
            dsn, "authenticated",
            "SELECT public.untrack_tracked_bet('other-device', 11);",
            claims='{"sub": "%s"}' % X, commit=True)
        assert ok, err
        assert "1" in _psql(
            dsn, "SELECT count(*) FROM tracked_bets WHERE device_id = 'other-device';")
        _psql(dsn, "INSERT INTO tracked_bets (device_id, pick_id, user_id) "
                  "VALUES ('legacy-device', 12, NULL);")
        ok, err = _can(
            dsn, "authenticated",
            "SELECT public.clear_my_tracked_bets('legacy-device');",
            claims='{"sub": "%s"}' % X, commit=True)
        assert ok, err
        assert _psql(
            dsn, "SELECT count(*) FROM tracked_bets WHERE device_id = 'legacy-device';"
        ).strip() == "0"
        assert _psql(
            dsn, "SELECT count(*) FROM tracked_bets WHERE device_id = 'other-device';"
        ).strip() == "1"
        # Same device, another account has used it. The caller's row goes.
        # The legacy NULL row stays: it has no owner who can remove it.
        _psql(dsn, f"""
          INSERT INTO public.app_timings (device_id, user_id)
          VALUES ('shared-device1', '{Y}');
          INSERT INTO public.tracked_bets (device_id, pick_id, user_id) VALUES
            ('shared-device1', 20, NULL),
            ('shared-device1', 21, '{X}');
        """)
        ok, err = _can(
            dsn, "authenticated",
            "SELECT public.clear_my_tracked_bets('shared-device1');",
            claims='{"sub": "%s"}' % X, commit=True)
        assert ok, err
        assert _psql(dsn, """
          SELECT count(*) FROM tracked_bets
           WHERE device_id = 'shared-device1' AND user_id IS NULL
        """).strip() == "1"
        assert _psql(dsn, f"""
          SELECT count(*) FROM tracked_bets
           WHERE device_id = 'shared-device1' AND user_id = '{X}'
        """).strip() == "0"
        _psql(dsn, f"DELETE FROM auth.users WHERE id = '{X}';")
        assert "0" in _psql(
            dsn, f"SELECT count(*) FROM tracked_bets WHERE user_id = '{X}';")

        ok, err = _can(dsn, "anon", "SELECT nextval('public.picks_pick_id_seq');")
        assert not ok
        ok, _ = _can(dsn, "authenticated", "SELECT nextval('public.tracked_bets_id_seq');")
        assert ok

        # Undo B, then A.
        _psql_file(dsn, files["undo_b"])
        _psql(dsn, "CREATE FUNCTION public.fresh_after_undo() RETURNS int "
                  "LANGUAGE sql AS $$ SELECT 1 $$;")
        ok, err = _can(dsn, "anon", "SELECT public.fresh_after_undo();")
        assert ok, err
        ok, _ = _can(dsn, "anon", "SELECT 1 FROM games;")
        assert ok
        ok, err = _can(dsn, "anon", "SELECT 1 FROM picks;")
        assert not ok
        _psql_file(dsn, files["undo_a"])
        ok, _ = _can(dsn, "anon", "SELECT 1 FROM picks;")
        assert ok
        assert "user_id" in _psql(
            dsn,
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'tracked_bets' AND column_name = 'user_id';")


def test_worker_migrations_do_not_reopen_anon():
    """A refresh pass re-runs every ACTIVE_MIGRATIONS file. After step A
    those files must not GRANT anon again, or step B's guard aborts."""
    combined = re.compile(r"\bGRANT\b[^;]*\bTO\s+anon\s*,\s*authenticated\b", re.I)
    for name in ACTIVE_MIGRATIONS:
        lines = (MIGRATIONS / name).read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines, 1):
            if line.strip().startswith("--"):
                continue
            assert combined.search(line) is None, f"{name}:{i}"
            if re.search(r"\bTO\s+anon\b", line) and "authenticated" not in line:
                window = "\n".join(lines[max(0, i - 8):i])
                if not re.search(r"\bGRANT\b", line) and not re.search(r"\bGRANT\b", window):
                    continue
                assert "public.picks" in window or "public.picks" in line, (
                    f"{name}:{i} {line.strip()}")

    if not pg_bin("psql"):
        pytest.skip("psql is not installed")
    import psycopg2
    with scratch_cluster("lockdown-mig-") as dsn:
        _psql(dsn, """
          CREATE ROLE anon NOLOGIN;
          CREATE TABLE public.picks (id int);
          CREATE TABLE public.games (id int);
          REVOKE ALL ON public.picks FROM PUBLIC, anon;
          REVOKE ALL ON public.games FROM PUBLIC, anon;
        """)
        _psql(dsn, """
          DO $t$
          BEGIN
            IF to_regclass('public.picks') IS NULL
               OR has_table_privilege('anon', 'public.picks', 'SELECT') THEN
              GRANT SELECT ON public.games TO anon;
            END IF;
          END $t$;
        """)
        ok, err = _can(dsn, "anon", "SELECT 1 FROM public.games;")
        assert not ok and "42501" in err
        conn = psycopg2.connect(dsn)
        try:
            for name in ACTIVE_MIGRATIONS:
                sql = (MIGRATIONS / name).read_text(encoding="utf-8")
                try:
                    with conn.cursor() as cur:
                        cur.execute("SET LOCAL lock_timeout = '3s'")
                        cur.execute(sql)
                    conn.commit()
                except Exception:
                    conn.rollback()
        finally:
            conn.close()
        ok, err = _can(dsn, "anon", "SELECT 1 FROM public.picks;")
        assert not ok and "42501" in err
        ok, err = _can(dsn, "anon", "SELECT 1 FROM public.games;")
        assert not ok and "42501" in err
        # A new public table that arrives with anon is the supabase_admin
        # gap. The stray check flags it. Revoking works when we own it.
        _psql(dsn, "CREATE TABLE public.arrived_open (id int); "
                  "GRANT SELECT ON public.arrived_open TO anon;")
        try:
            _psql_file(dsn, ROOT / "scripts" / "lockdown_anon_stray_check.sql")
        except AssertionError as exc:
            assert "arrived_open" in str(exc)
        else:
            raise AssertionError("stray check did not raise")
        _psql(dsn, "REVOKE ALL ON public.arrived_open FROM anon;")


def test_supabase_admin_defaults_are_out_of_postgres_reach():
    """Measured: a non-member cannot change that role's defaults or revoke
    on a table it owns. storage and graphql are not named as targets."""
    sql = (MIGRATIONS / "anon_lockdown_step_b_2026_11.sql").read_text(encoding="utf-8")
    undo = (MIGRATIONS / "anon_lockdown_step_b_2026_11_undo.sql").read_text(encoding="utf-8")
    assert "pg_has_role('supabase_admin', 'MEMBER')" in sql
    assert "IN SCHEMA storage" not in sql
    assert "IN SCHEMA graphql" not in sql
    assert "IN SCHEMA storage" not in undo
    assert "IN SCHEMA graphql" not in undo
    if not pg_bin("psql"):
        pytest.skip("psql is not installed")
    with scratch_cluster("admin-acl-") as dsn:
        _psql(dsn, """
          CREATE ROLE supabase_admin NOLOGIN;
          CREATE ROLE worker NOLOGIN;
          CREATE ROLE anon NOLOGIN;
          GRANT CREATE, USAGE ON SCHEMA public TO supabase_admin, worker;
          GRANT supabase_admin TO postgres;
        """)
        _psql(dsn, """
          SET ROLE supabase_admin;
          ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public
            GRANT SELECT ON TABLES TO anon;
          CREATE TABLE public.opened_by_admin (id int);
          RESET ROLE;
          REVOKE supabase_admin FROM postgres;
        """)
        proc_sql = """
          GRANT worker TO postgres;
          SET ROLE worker;
          ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public
            REVOKE SELECT ON TABLES FROM anon;
        """
        psql = pg_bin("psql")
        proc = subprocess.run(
            [psql, dsn, "-v", "ON_ERROR_STOP=1", "-X", "-q", "-f", "-"],
            input=proc_sql, text=True, capture_output=True)
        assert proc.returncode != 0
        assert "permission denied to change default privileges" in proc.stderr
        assert _psql(
            dsn,
            "SELECT has_table_privilege('anon', 'public.opened_by_admin', 'SELECT');"
        ).strip() == "t"
        _psql(dsn, "REVOKE ALL ON TABLE public.opened_by_admin FROM anon;")
        _psql_file(dsn, ROOT / "scripts" / "lockdown_anon_stray_check.sql")


def test_lockdown_runbook_sql_runs_on_scratch_postgres():
    """The snapshot and the pre-apply check are executed, not only read.

    Postgres can evaluate has_sequence_privilege on a table before the
    relkind filter, and text || defaclobjtype is an ambiguous operator.
    Both failed on production 17.6. Step A's own post-apply check runs
    with the migration. Undo A runs after it.
    """
    if not pg_bin("psql"):
        pytest.skip("psql is not installed")
    from scripts.restore_acl_from_snapshot import _split_defacl

    files = _sql_files()
    with scratch_cluster("runbook-sql-") as dsn:
        _psql(dsn, _fixture_sql())
        _psql(dsn, """
          CREATE INDEX one_time_tokens_link_token_hash_hash_idx
            ON public.games (id);
          ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT SELECT ON TABLES TO anon;
          ALTER DEFAULT PRIVILEGES
            REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
        """)
        _psql_file(dsn, ROOT / "scripts" / "lockdown_acl_snapshot.sql")
        rows = _psql(
            dsn,
            "SELECT object FROM ops.acl_snapshot WHERE kind = 'defacl' ORDER BY 1;")
        objects = [line.strip() for line in rows.splitlines() if line.strip()]
        assert objects
        saw_global = False
        saw_schema = False
        for obj in objects:
            role, typ, global_scope = _split_defacl(obj)
            assert role
            assert len(typ) == 1 and typ.isalpha()
            assert obj == (f"{role}:{typ}:global" if global_scope else f"{role}:{typ}")
            saw_global = saw_global or global_scope
            saw_schema = saw_schema or not global_scope
        assert saw_global and saw_schema
        try:
            _psql_file(dsn, ROOT / "scripts" / "lockdown_preapply_check.sql")
        except AssertionError as exc:
            text = str(exc)
            assert "not a sequence" not in text
            assert "operator is not unique" not in text
            assert "42809" not in text
            assert "42725" not in text
            assert "baseline drifted" in text
        else:
            raise AssertionError("preapply check did not raise on the scratch counts")
        _psql_file(dsn, files["site"])
        _psql_file(dsn, files["a"])
        ok, err = _can(dsn, "anon", "SELECT 1 FROM picks;")
        assert not ok and "42501" in err
        _psql_file(dsn, files["undo_a"])
        ok, _ = _can(dsn, "anon", "SELECT 1 FROM picks;")
        assert ok


def test_stray_check_keep_names_match_the_spec():
    from data.anon_readable import ANON_READABLE, RPC_ANON_CALLABLE
    import inspect
    from scripts.apply_anon_grants import _revoke_lockdown_strays

    text = (ROOT / "scripts" / "lockdown_anon_stray_check.sql").read_text(
        encoding="utf-8")
    rel = re.search(r"c\.relname <> '([^']+)'", text)
    fn = re.search(r"p\.proname NOT IN \(([^)]+)\)", text)
    assert rel is not None and fn is not None
    names = re.findall(r"'([^']+)'", fn.group(1))
    assert frozenset({rel.group(1)}) == ANON_KEEP_RELATIONS
    assert frozenset(names) == ANON_KEEP_FUNCTIONS
    assert ANON_KEEP_RELATIONS == frozenset(ANON_READABLE)
    assert ANON_KEEP_FUNCTIONS == frozenset(RPC_ANON_CALLABLE)
    src = inspect.getsource(_revoke_lockdown_strays)
    assert "'p'" in src and "'f'" in src


class _Pg:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=None):
        cur = self.raw.cursor()
        cur.execute(sql, params)
        return cur


def test_lockdown_sweep_fails_closed_when_revoke_only_warns():
    """A non-owner who holds SELECT without grant option gets a warning
    and a successful REVOKE. The anon grant stays. The sweep must not
    record that as revoked. A partitioned table this role owns is
    revoked in the same pass, then restored when the caller rolls back.
    """
    psycopg2 = pytest.importorskip("psycopg2")
    if not pg_bin("psql"):
        pytest.skip("psql is not installed")
    from loguru import logger
    from scripts.apply_anon_grants import _revoke_lockdown_strays

    with scratch_cluster("stray-warn-") as dsn:
        _psql(dsn, """
          CREATE ROLE supabase_admin NOLOGIN;
          CREATE ROLE worker NOLOGIN;
          CREATE ROLE anon NOLOGIN;
          GRANT CREATE, USAGE ON SCHEMA public TO supabase_admin, worker;
          GRANT supabase_admin TO postgres;
          SET ROLE supabase_admin;
          CREATE TABLE public.opened_by_admin (id int);
          GRANT SELECT ON public.opened_by_admin TO anon;
          GRANT SELECT ON public.opened_by_admin TO worker;
          RESET ROLE;
          REVOKE supabase_admin FROM postgres;
          GRANT worker TO postgres;
          SET ROLE worker;
          CREATE TABLE public.opened_parts (id int, k int) PARTITION BY LIST (k);
          GRANT SELECT ON public.opened_parts TO anon;
          RESET ROLE;
        """)
        raw = psycopg2.connect(dsn)
        raw.autocommit = False
        lines: list[str] = []
        sink = logger.add(lambda msg: lines.append(str(msg)), format="{message}")
        try:
            raw.cursor().execute("SET ROLE worker")
            left = _revoke_lockdown_strays(_Pg(raw))
        finally:
            logger.remove(sink)
        assert any(
            "opened_by_admin" in item and "supabase_admin" in item for item in left)
        assert not any("opened_parts" in item for item in left)
        text = "\n".join(lines)
        assert "opened_by_admin: anon grant remains (owner supabase_admin)" in text
        assert "opened_by_admin: revoked" not in text
        assert "opened_parts: revoked anon grant" in text
        cur = raw.cursor()
        cur.execute(
            "SELECT has_table_privilege('anon', 'public.opened_by_admin', 'SELECT')")
        assert cur.fetchone()[0] is True
        cur.execute(
            "SELECT has_table_privilege('anon', 'public.opened_parts', 'SELECT')")
        assert cur.fetchone()[0] is False
        raw.rollback()
        cur = raw.cursor()
        cur.execute(
            "SELECT has_table_privilege('anon', 'public.opened_parts', 'SELECT')")
        assert cur.fetchone()[0] is True
        cur.execute(
            "SELECT has_table_privilege('anon', 'public.opened_by_admin', 'SELECT')")
        assert cur.fetchone()[0] is True
        raw.close()


def test_retired_sync_writes_config_retired_models():
    from config import RETIRED_MODELS
    from data.threshold_sync import _sync_retired_models

    class Conn:
        def __init__(self):
            self.rows = []

        def execute(self, sql, params=None):
            self.sql = sql
            return self

        def executemany(self, sql, rows):
            self.rows = list(rows)

        def fetchone(self):
            return ("site_retired_models",)

    conn = Conn()
    _sync_retired_models(conn)
    assert "DELETE FROM public.site_retired_models" in conn.sql
    assert {row[0] for row in conn.rows} == set(RETIRED_MODELS)


def test_signed_in_hooks_refetch_when_auth_changes():
    root = ROOT / "mobile" / "src" / "hooks"
    for name in ("useActionThresholds.ts", "useModelClvPedigree.ts",
                 "usePreferredBooks.ts"):
        src = (root / name).read_text(encoding="utf-8")
        assert "signedIn" in src, name
        assert "[authReady, signedIn]" in src, name
