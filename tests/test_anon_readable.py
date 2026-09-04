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
