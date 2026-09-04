"""The read-surface manifest must stay ahead of the app, not behind it.

Once ALTER DEFAULT PRIVILEGES has revoked the default grant, a new table or view
the app reads arrives with NO SELECT -- and that fails silently: PostgREST
answers a permission error, the client folds it into `error`, and the screen
renders empty with nothing in any log near the cause.

This test is the tripwire. It parses every `.from('...')` in mobile/src and
fails if one names a relation the manifest does not, so "somebody forgot the
GRANT" is a red test before the PR opens rather than an empty screen after the
OTA ships.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.anon_readable import ANON_READABLE, AUTHENTICATED_ONLY, all_readable
from scripts.apply_anon_grants import REVOKE_DEFAULT, _plan

MOBILE_SRC = Path(__file__).parent.parent / "mobile" / "src"


def _app_relations() -> set[str]:
    """Every relation mobile/src reads through PostgREST."""
    found: set[str] = set()
    for path in MOBILE_SRC.rglob("*.ts*"):
        src = path.read_text(encoding="utf-8", errors="replace")
        found.update(re.findall(r"\.from\('([a-z_0-9]+)'\)", src))
    return found


def test_every_relation_the_app_reads_is_declared():
    app = _app_relations()
    assert app, "found no .from() calls at all -- the parser is broken, not the app"
    undeclared = sorted(app - set(all_readable()))
    assert not undeclared, (
        f"mobile/src reads {undeclared}, which data/anon_readable.py does not "
        f"declare. After ALTER DEFAULT PRIVILEGES a new relation arrives with "
        f"NO anon SELECT, so this would render an empty screen with no error "
        f"anywhere near the cause. Add it to the manifest and re-run "
        f"`python -m scripts.apply_anon_grants --apply`.")


def test_the_manifest_does_not_grow_stale_entries():
    """A relation nobody reads should not keep a grant. Not fatal -- a screen
    may be mid-build -- but it must be deliberate, so it is asserted."""
    app = _app_relations()
    unused = sorted(set(all_readable()) - app)
    assert not unused, (
        f"{unused} are granted but nothing in mobile/src reads them. Remove "
        f"them from data/anon_readable.py, or add the query that needs them.")


def test_subscriptions_stays_authenticated_only():
    """Billing state must not be readable before sign-in. anon has never held
    SELECT on it; that is the right shape, so it is pinned."""
    assert "subscriptions" in AUTHENTICATED_ONLY
    assert "subscriptions" not in ANON_READABLE


def test_the_default_privilege_revoke_names_the_api_roles_only():
    """service_role must keep its grant -- the edge functions, including every
    billing path, authenticate as it. And REVOKE ... FROM PUBLIC would not
    touch a named role at all."""
    assert "FROM anon, authenticated" in REVOKE_DEFAULT, REVOKE_DEFAULT
    assert "service_role" not in REVOKE_DEFAULT, REVOKE_DEFAULT
    assert "PUBLIC" not in REVOKE_DEFAULT.upper().replace("IN SCHEMA PUBLIC", "")
    assert "IN SCHEMA public" in REVOKE_DEFAULT, REVOKE_DEFAULT
    assert "ON TABLES" in REVOKE_DEFAULT, REVOKE_DEFAULT


def test_the_plan_revokes_before_it_grants():
    """Order matters only for readability, but a plan that granted first and
    revoked after would leave the window open in the same transaction."""
    plan = _plan()
    assert plan[0] == REVOKE_DEFAULT, plan[0]
    assert all(s.startswith("GRANT SELECT") for s in plan[1:]), plan[1:3]


def test_every_declared_relation_is_granted_exactly_once():
    plan = " | ".join(_plan())
    for rel in ANON_READABLE:
        assert f'ON public."{rel}" TO anon, authenticated' in plan, rel
    for rel in AUTHENTICATED_ONLY:
        assert f'ON public."{rel}" TO authenticated' in plan, rel
        assert f'ON public."{rel}" TO anon' not in plan, rel


# ── RPCs ─────────────────────────────────────────────────────────────────────

def _app_rpcs() -> set[str]:
    """Every RPC the app can call, INCLUDING the ones it names at runtime.

    A literal grep for `.rpc('x')` finds 17. Four call sites in queries.ts do

        const fn = sport === 'NFL' ? 'player_window_totals_nfl'
                                   : 'player_window_totals_ncaaf';
        await supabase.rpc(fn, {...})

    so the real surface is 24. Resolving only the literal form is how a sweep
    would silently revoke EXECUTE on the NBA/WNBA/NCAAF/NFL stats functions.
    """
    found: set[str] = set()
    for path in MOBILE_SRC.rglob("*.ts*"):
        src = path.read_text(encoding="utf-8", errors="replace")
        found.update(re.findall(r"\.rpc\('([a-z_0-9]+)'", src))
        # Indirect: rpc(<ident>) -- collect the string literals assigned to that
        # identifier anywhere in the same file.
        for ident in set(re.findall(r"\.rpc\(([A-Za-z_][A-Za-z_0-9]*)\s*,", src)):
            for assign in re.findall(
                    rf"\b{re.escape(ident)}\s*=\s*([^;]+);", src, re.S):
                found.update(re.findall(r"'([a-z_][a-z_0-9]*)'", assign))
    return found


def test_the_dynamic_rpc_resolver_actually_finds_the_ternary_names():
    """Guard the guard. If this regex stops resolving indirect calls it fails
    OPEN -- the surface looks smaller and the sweep gets more aggressive -- so
    the resolver is pinned against names known to be reachable only that way."""
    rpcs = _app_rpcs()
    for only_indirect in ("player_window_totals_ncaaf", "player_recent_games_nfl",
                          "player_season_stat_values_nba"):
        assert only_indirect in rpcs, (
            f"{only_indirect} is reached only through `const fn = ... ? ... : ...` "
            f"and the resolver missed it -- a sweep would now revoke it")


def test_every_rpc_the_app_calls_is_declared_or_known_absent():
    from data.anon_readable import RPC_ANON_CALLABLE, RPC_MISSING_IN_PROD

    known = set(RPC_ANON_CALLABLE) | set(RPC_MISSING_IN_PROD)
    undeclared = sorted(_app_rpcs() - known)
    assert not undeclared, (
        f"mobile/src calls {undeclared}, which data/anon_readable.py does not "
        f"declare. After ALTER DEFAULT PRIVILEGES ... ON FUNCTIONS a new RPC "
        f"404s through PostgREST. Add it to RPC_ANON_CALLABLE and re-run "
        f"`python -m scripts.apply_anon_grants --apply`.")


def test_the_transitive_helper_is_granted():
    """custom_model_picks and custom_model_backtest are SECURITY INVOKER and
    both call _jsonb_text_array, so the CALLER needs EXECUTE on it even though
    the app never names it. Measured in pg_proc, not assumed."""
    from data.anon_readable import RPC_ANON_CALLABLE

    assert "_jsonb_text_array" in RPC_ANON_CALLABLE


def test_the_trigger_function_is_not_swept():
    """log_picks_changes returns `trigger`: PostgREST will not expose it and
    Postgres does not check EXECUTE when a trigger fires. Revoking gains
    nothing and risks the picks_log audit trail."""
    from data.anon_readable import RPC_LEFT_ALONE, RPC_REVOKE

    assert "log_picks_changes" in RPC_LEFT_ALONE
    assert "log_picks_changes" not in RPC_REVOKE


def test_the_function_default_revoke_leaves_sequences_and_service_role_alone():
    from scripts.apply_anon_grants import REVOKE_DEFAULT_FUNCTIONS as R

    assert "ON FUNCTIONS" in R, R
    assert "FROM anon, authenticated" in R, R
    assert "service_role" not in R, R
    assert "SEQUENCES" not in R.upper(), (
        "sequences must not be revoked: tracked_bets.id defaults to nextval() "
        "and anon holds USAGE/UPDATE on that sequence")


def test_the_function_revoke_names_public_as_well_as_the_roles():
    """Postgres grants EXECUTE to PUBLIC by default and anon is a member of
    PUBLIC, so `REVOKE ... FROM anon, authenticated` leaves the function
    callable AND reports success.

    Measured 2026-09-04: the first run of this script revoked
    has_active_subscription from both named roles and anon could still execute
    it -- its ACL carried `=X/postgres`, the empty grantee being PUBLIC. 21 of
    28 public functions carry that grant.
    """
    import inspect as _inspect

    from scripts import apply_anon_grants

    src = _inspect.getsource(apply_anon_grants._function_plan)
    # There are two revokes in this function and they mean different things:
    # one strips PUBLIC from a callable before granting it to the named roles,
    # the other takes a function away entirely. This is about the second, so it
    # matches the full role list rather than the first REVOKE it finds.
    targets = re.findall(r'REVOKE ALL ON FUNCTION \{one\} FROM ([^"]+)"', src)
    assert targets, src
    full = [t for t in targets if "anon" in t]
    assert full, (
        f"no revoke targets anon at all; found {targets!r}. The RPC_REVOKE "
        f"path must remove the named roles as well as PUBLIC.")
    for roles in full:
        assert "PUBLIC" in roles, (
            f"revoke targets {roles!r} -- without PUBLIC the function stays "
            f"callable and the run still reports success")
        assert "authenticated" in roles, roles


def test_public_is_stripped_from_every_declared_callable_before_it_is_granted():
    """Postgres grants function EXECUTE to PUBLIC by default, so a function with
    an explicit anon grant is usually ALSO callable by every other role --
    including any role added later. The end state wanted is "PUBLIC holds
    nothing, anon and authenticated hold exactly EXECUTE".

    Order is load-bearing: the revoke must come BEFORE the grant, or it strips
    the grant it just made. Measured before shipping: all 20 functions carrying
    the PUBLIC grant already held explicit anon=X and authenticated=X, so PUBLIC
    was never the only source for any of them.
    """
    import inspect as _inspect

    from scripts import apply_anon_grants

    src = _inspect.getsource(apply_anon_grants._function_plan)
    rev = src.index('REVOKE ALL ON FUNCTION {one} FROM PUBLIC"')
    grant = src.index('GRANT EXECUTE ON FUNCTION {one} TO anon, authenticated"')
    assert rev < grant, (
        "the PUBLIC revoke must be emitted before the named grant, or it "
        "removes the grant it just made")
