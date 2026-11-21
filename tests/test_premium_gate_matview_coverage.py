"""Every API object that reads mv_scored_pick_outcomes is on the pre-request hook.

premium_gate_matview_2026_11_20.sql refuses a fixed list of six endpoint
names. A view or RPC added later that reads the matview, directly or through
another view or function, would be open to a free account. This test applies
the migrations on a scratch cluster and discovers the readers from the
catalog, so the list in the migration is not what it trusts.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "data" / "migrations"
FREE = "22222222-2222-2222-2222-222222222222"

# The website record is anon on purpose. The view is a definer and the rows
# come from site_public_record_rows(), so a logged-out visitor can load the
# public record without a subscription. It does not read the scored-picks
# matview today. If a later migration points either object at that matview,
# it stays public: the page has no login.
PUBLIC_OBJECTS = frozenset({
    "site_public_record",
    "site_public_record_rows",
})

# Readers the worker migrations are supposed to leave behind. Missing any of
# these means the scratch catalog is not the one production's migrations
# build, and an empty discovery would pass without looking.
REQUIRED_PRESENT = (
    "mv_scored_pick_outcomes",
    "v_model_full_outcome_picks",
    "v_model_full_outcome_record",
    "custom_model_backtest",
    "custom_model_backtest_posted",
    "custom_model_picks",
    "premium_pre_request",
)

_READ = re.compile(
    r"\b(?:from|join)\s+(?:[a-z_][a-z0-9_]*\.)?([a-z_][a-z0-9_]*)\b",
    re.IGNORECASE,
)

# Enough of picks, games and the logs for decide_on_best_price to build the
# matview and the two views, and for the later record migrations to rewrite
# the views they own. Roles match the worker's GRANT targets.
_FIXTURE = r"""
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE ROLE authenticator NOINHERIT LOGIN;
GRANT anon, authenticated, service_role TO postgres;

CREATE SCHEMA IF NOT EXISTS auth;
CREATE TABLE auth.users (id uuid PRIMARY KEY);
CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT NULLIF(current_setting('request.jwt.claims', true)::json->>'sub','')::uuid
$$;
CREATE OR REPLACE FUNCTION auth.role() RETURNS text
LANGUAGE sql STABLE AS $$
  SELECT current_setting('request.jwt.claim.role', true)
$$;

CREATE TABLE public.subscriptions (
  user_id uuid PRIMARY KEY, status text, current_period_end timestamptz
);
CREATE TABLE public.access_grants (
  user_id uuid, access_source text, expires_at timestamptz
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

CREATE TABLE public.games (
  game_id text PRIMARY KEY,
  sport text, home_team text, away_team text, commence_time text, updated_at text,
  home_score numeric, away_score numeric,
  home_score_f5 numeric, away_score_f5 numeric,
  home_win integer, home_win_reg integer, went_to_ot integer
);
CREATE TABLE public.picks (
  pick_id bigserial PRIMARY KEY,
  game_id text, model_id text, sport text, game_date text, game_time text,
  pick_side text, pick_label text, model_probability numeric,
  dk_implied_prob numeric, edge numeric, dk_odds numeric, scored_line numeric,
  kelly_fraction numeric, recommended_bet numeric, bankroll_at_pick numeric,
  injury_flag text, injury_detail text, signal_type text, confidence_tier text,
  public_bet_pct numeric, player_id text, is_live boolean,
  result text, profit_flat numeric, profit_kelly numeric,
  settled_at text, created_at text, run_time text, clv_pct numeric,
  clv_method text, condition_status text, clv_bet_book text,
  market_clv_pct numeric, stake_units numeric
);
CREATE TABLE public.picks_log (pick_id bigint);
CREATE TABLE public.player_game_log (
  game_id text, player_id text, player_name text, season integer,
  p_strikeouts integer, p_walks integer, p_hits_allowed integer,
  p_earned_runs integer, innings_pitched numeric,
  hits integer, total_bases integer, rbi integer, runs integer,
  stolen_bases integer, walks integer, home_runs integer
);
CREATE TABLE public.wnba_player_game_log (
  game_id text, player_id text,
  points integer, rebounds integer, assists integer, fg3_made integer
);
CREATE TABLE public.model_action_thresholds (
  model_id text PRIMARY KEY,
  min_prob numeric, min_edge numeric,
  prob_only boolean, paused boolean, min_odds numeric
);
CREATE TABLE public.push_sent (
  lock_key text, kind text, sent_at timestamptz
);

-- Column list is the pre-decision shape. decide_on_best_price appends
-- decision_* with CREATE OR REPLACE, which refuses a different list.
CREATE VIEW public.v_model_full_outcome_picks AS
SELECT NULL::bigint AS pick_id, NULL::text AS model_id, NULL::text AS game_date,
       NULL::text AS game_id, NULL::text AS pick_label, NULL::text AS pick_side,
       NULL::numeric AS model_probability, NULL::numeric AS edge,
       NULL::numeric AS dk_odds, NULL::numeric AS scored_line,
       NULL::text AS result, NULL::numeric AS profit_units;
CREATE VIEW public.v_model_full_record AS
SELECT NULL::text AS model_id, NULL::bigint AS picks, NULL::bigint AS wins,
       NULL::bigint AS losses, NULL::bigint AS pushes, NULL::numeric AS profit_units;
CREATE VIEW public.v_public_track_record AS
SELECT NULL::text AS sport, NULL::text AS model_id,
       NULL::bigint AS picks, NULL::bigint AS wins, NULL::bigint AS losses,
       NULL::bigint AS pushes, NULL::numeric AS profit_flat,
       NULL::bigint AS staked_flat, NULL::bigint AS clv_settled,
       NULL::bigint AS clv_beat, NULL::numeric AS avg_clv_pct,
       NULL::text AS first_date, NULL::text AS last_date;
CREATE VIEW public.v_public_track_record_daily AS
SELECT NULL::text AS game_date, NULL::text AS sport,
       NULL::bigint AS picks, NULL::bigint AS wins, NULL::bigint AS losses,
       NULL::bigint AS pushes, NULL::numeric AS profit_flat,
       NULL::bigint AS staked_flat;
"""


class _Conn:
    """The slice of data.db's connection apply_view_migrations uses."""

    def __init__(self, raw):
        self.raw = raw

    def execute(self, query, params=None):
        cur = self.raw.cursor()
        cur.execute(query, params)
        return cur

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()


def _executable(sql: str) -> str:
    return "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--"))


def _reads_known(src: str, names: set[str]) -> bool:
    return any(match.group(1).lower() in names for match in _READ.finditer(src))


def _calls_known(src: str, names: set[str]) -> bool:
    return any(
        re.search(rf"\b{re.escape(name)}\s*\(", src, re.IGNORECASE)
        for name in names
    )


def _discover(cur) -> list[tuple[str, str, int]]:
    """Views and public SQL/plpgsql functions that read the matview.

    Views: pg_rewrite / pg_depend, walked until no new view appears, including
    a view that only calls a function already found. Functions: a pg_depend
    edge, a FROM/JOIN of a known relation in prosrc, or a call of a known
    function. premium_pre_request is the gate, not a reader.
    """
    cur.execute(
        "SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relname = 'mv_scored_pick_outcomes'")
    row = cur.fetchone()
    assert row, "mv_scored_pick_outcomes is not in the catalog after the migrations"
    matview = int(row[0])
    relations: dict[int, tuple[str, str]] = {matview: ("relation", "mv_scored_pick_outcomes")}
    functions: dict[int, str] = {}
    changed = True
    while changed:
        changed = False
        known = list(relations) + list(functions)
        cur.execute(
            """
            SELECT c.oid, c.relname
              FROM pg_depend d
              JOIN pg_rewrite w ON w.oid = d.objid
               AND d.classid = 'pg_rewrite'::regclass
              JOIN pg_class c ON c.oid = w.ev_class
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public'
               AND c.relkind IN ('v', 'm')
               AND d.refobjid = ANY(%s)
               AND NOT (c.oid = ANY(%s))
            """,
            (known, list(relations)))
        for oid, name in cur.fetchall():
            relations[int(oid)] = ("relation", name)
            changed = True
        cur.execute(
            """
            SELECT p.oid, p.proname, p.prosrc
              FROM pg_proc p
              JOIN pg_namespace n ON n.oid = p.pronamespace
              JOIN pg_language l ON l.oid = p.prolang
             WHERE n.nspname = 'public'
               AND l.lanname IN ('sql', 'plpgsql')
               AND p.proname <> 'premium_pre_request'
            """)
        rel_names = {name for _kind, name in relations.values()}
        fn_names = set(functions.values())
        for oid, name, src in cur.fetchall():
            oid = int(oid)
            if oid in functions:
                continue
            depends = False
            cur.execute(
                "SELECT 1 FROM pg_depend WHERE classid = 'pg_proc'::regclass "
                "AND objid = %s AND refobjid = ANY(%s) LIMIT 1",
                (oid, list(relations)))
            if cur.fetchone():
                depends = True
            if (depends or _reads_known(src or "", rel_names)
                    or _calls_known(src or "", fn_names)):
                functions[oid] = name
                changed = True
    found = [(kind, name, oid) for oid, (kind, name) in relations.items()]
    found += [("function", name, oid) for oid, name in functions.items()]
    return sorted(found, key=lambda item: (item[0], item[1], item[2]))


def _anon_can_read(cur, kind: str, oid: int) -> bool:
    if kind == "relation":
        cur.execute(
            """
            SELECT EXISTS (
              SELECT 1 FROM pg_attribute a
               WHERE a.attrelid = %s AND a.attnum > 0 AND NOT a.attisdropped
                 AND has_column_privilege('anon', a.attrelid, a.attnum, 'SELECT')
            )
            """,
            (oid,))
    else:
        cur.execute(
            "SELECT has_function_privilege('anon', %s, 'EXECUTE')", (oid,))
    return bool(cur.fetchone()[0])


def _hook_refuses(raw, path: str) -> tuple[bool, str]:
    """Free authenticated JWT, the path PostgREST would set, then the hook."""
    raw.rollback()
    cur = raw.cursor()
    try:
        cur.execute("BEGIN")
        cur.execute(
            "SELECT set_config('request.jwt.claims', %s, true)",
            ('{"sub": "%s"}' % FREE,))
        cur.execute("SELECT set_config('request.path', %s, true)", (path,))
        cur.execute("SET LOCAL ROLE authenticated")
        cur.execute("SELECT public.premium_pre_request()")
    except Exception as exc:
        raw.rollback()
        code = getattr(exc, "pgcode", None)
        return code == "42501", f"{code} {exc}".strip()
    raw.rollback()
    return False, "premium_pre_request returned"


def _path_for(kind: str, name: str) -> str:
    if kind == "function":
        return f"/rpc/{name}"
    return f"/{name}"


def _stand_in_for_lockdown(cur) -> None:
    """Step A revokes a fixed list. Relations it names that this scratch
    database never built get an empty stand-in so the file can commit.
    The scored-picks objects are already the ones the migrations created.

    v_model_full_outcome_picks keeps authenticated SELECT from
    add_model_full_outcome_picks_view.sql, which is not re-run by the worker.
    CREATE OR REPLACE keeps a grant and does not add one, so the stand-in
    restores the grant that file left in production.
    """
    from data.anon_lockdown_spec import (
        STEP_A_FUNCTIONS,
        STEP_A_HYGIENE,
        STEP_A_POLICIES,
        STEP_A_RELATIONS,
    )

    for name in list(STEP_A_RELATIONS) + list(STEP_A_HYGIENE):
        cur.execute("SELECT to_regclass(%s)", (f"public.{name}",))
        if cur.fetchone()[0] is not None:
            continue
        if name.startswith("v_"):
            cur.execute(f"CREATE VIEW public.{name} AS SELECT 1::int AS id")
        else:
            cur.execute(f"CREATE TABLE public.{name} (id int, lock_key text)")
    cur.execute(
        "GRANT SELECT ON public.v_model_full_outcome_picks TO authenticated")
    for name in list(STEP_A_RELATIONS) + list(STEP_A_HYGIENE):
        cur.execute(f"GRANT SELECT ON public.{name} TO authenticated")
    for policy, table, roles in STEP_A_POLICIES:
        cur.execute(
            "SELECT 1 FROM pg_policy p JOIN pg_class c ON c.oid = p.polrelid "
            "WHERE c.relname = %s AND p.polname = %s",
            (table, policy))
        if cur.fetchone():
            continue
        role_sql = "PUBLIC" if roles == "public" else "anon, authenticated"
        cur.execute(
            f'CREATE POLICY "{policy}" ON public.{table} '
            f"FOR SELECT TO {role_sql} USING (true)")
    for sig in STEP_A_FUNCTIONS:
        cur.execute("SELECT to_regprocedure(%s)", (sig,))
        if cur.fetchone()[0] is not None:
            continue
        cur.execute(
            f"CREATE FUNCTION {sig} RETURNS integer LANGUAGE sql AS $$ SELECT 1 $$")


def test_this_file_runs_in_pr_ci() -> None:
    workflow = (ROOT / ".github" / "workflows" / "pr-ci.yml").read_text(encoding="utf-8")
    assert "tests/test_premium_gate_matview_coverage.py" in workflow


def test_every_scored_picks_reader_is_on_the_pre_request_hook() -> None:
    psycopg2 = pytest.importorskip("psycopg2")
    from loguru import logger

    from data.view_migrations import apply_view_migrations
    from tests._pg import can_scratch, scratch_cluster

    if not can_scratch():
        if os.environ.get("GITHUB_ACTIONS"):
            pytest.fail("initdb is missing in CI — the scratch Postgres test would skip")
        pytest.skip("initdb is not installed")

    logger.disable("data.view_migrations")
    with scratch_cluster("matview-gate-") as dsn:
        raw = psycopg2.connect(dsn)
        try:
            raw.autocommit = True
            raw.cursor().execute(_FIXTURE)
            raw.autocommit = False
            result = apply_view_migrations(_Conn(raw))
            missed = []
            for name, err in result.failed:
                code = _executable((MIGRATIONS / name).read_text(encoding="utf-8"))
                if "mv_scored_pick_outcomes" in code:
                    missed.append(f"{name}: {err.splitlines()[0]}")
            assert not missed, (
                "a migration that reads mv_scored_pick_outcomes did not apply, "
                "so the catalog discovery would miss what it creates:\n"
                + "\n".join(missed))

            cur = raw.cursor()
            cur.execute((MIGRATIONS / "site_public_record_2026_11.sql").read_text(encoding="utf-8"))
            raw.commit()
            _stand_in_for_lockdown(cur)
            raw.commit()
            cur.execute((MIGRATIONS / "anon_lockdown_step_a_2026_11.sql").read_text(encoding="utf-8"))
            raw.commit()

            cur.execute(
                """
                SELECT c.relname FROM pg_class c
                  JOIN pg_namespace n ON n.oid = c.relnamespace
                 WHERE n.nspname = 'public'
                UNION ALL
                SELECT p.proname FROM pg_proc p
                  JOIN pg_namespace n ON n.oid = p.pronamespace
                 WHERE n.nspname = 'public'
                """)
            present = {row[0] for row in cur.fetchall()}
            absent = [name for name in REQUIRED_PRESENT if name not in present]
            assert not absent, (
                "migrations did not leave these scored-picks objects: "
                + ", ".join(absent))

            cur.execute(
                "SELECT has_table_privilege('anon', 'public.site_public_record', 'SELECT')")
            assert cur.fetchone()[0], (
                "anon cannot read site_public_record; the public record page must keep loading")
            refused, detail = _hook_refuses(raw, "/site_public_record")
            assert not refused, (
                "the hook refused /site_public_record for a free user: " + detail)

            found = _discover(cur)
            names = ", ".join(f"{kind} {name}" for kind, name, _oid in found)
            uncovered = []
            for kind, name, oid in found:
                label = f"{kind} {name}"
                if name in PUBLIC_OBJECTS:
                    if not _anon_can_read(cur, kind, oid):
                        uncovered.append(
                            f"{label}: allow-listed as public, but anon cannot read it")
                    continue
                path = _path_for(kind, name)
                refused, detail = _hook_refuses(raw, path)
                anon = _anon_can_read(cur, kind, oid)
                problems = []
                if not refused:
                    problems.append(
                        f"hook did not refuse {path} for a free authenticated user ({detail})")
                if anon:
                    problems.append(
                        "anon can read it, and the hook returns at once for anon")
                if problems:
                    uncovered.append(f"{label}: " + "; ".join(problems))
            assert not uncovered, (
                "scored-picks readers the pre-request hook does not cover "
                "(discovered: " + names + "):\n" + "\n".join(uncovered))
        finally:
            raw.close()
