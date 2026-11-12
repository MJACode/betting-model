"""What the ops dashboard reads: the app's model names, and saved tile layouts.

mike, 2026-11-12: "change the front end names of the models to something more
friendly ... allow savable layouts, like the different sections are tiles that
can be moved".

data/migrations/dashboard_support_2026_11_12.sql builds the view
`model_display_names` (every model's name exactly as the mobile app shows it)
and the worker-only table `dashboard_layouts`. These tests read the SQL as
text; none of it is run by Postgres here.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import config                                              # noqa: E402
from data.view_migrations import ACTIVE_MIGRATIONS         # noqa: E402
from scripts import model_display_names as names           # noqa: E402

NAME = "dashboard_support_2026_11_12.sql"
SQL = (ROOT / "data" / "migrations" / NAME).read_text(encoding="utf-8")
META = (ROOT / "mobile" / "src" / "lib" / "modelMeta.ts").read_text(encoding="utf-8")
MARK = re.compile(r"dashboard_support [0-9a-f]{12}")


def _code(sql: str) -> str:
    """The SQL with -- comments removed, so a clause in a comment proves nothing."""
    return "\n".join(line.split("--", 1)[0] for line in sql.splitlines())


CODE = _code(SQL)


def _rows() -> dict[str, tuple[str, str]]:
    body = SQL[SQL.index(names.BEGIN):SQL.index(names.END)]
    out = {}
    for mid, name, short in re.findall(r"\('([a-z0-9_]+)', '((?:[^']|'')*)', '((?:[^']|'')*)'\)", body):
        assert mid not in out, f"{mid} is listed twice"
        out[mid] = (name.replace("''", "'"), short.replace("''", "'"))
    return out


def test_the_names_are_the_apps_names_and_in_step_with_it():
    """The fix for a failure here is one command, never a hand edit."""
    pairs = names.model_meta(META)
    assert names.render(SQL, pairs) == SQL, (
        "model_display_names is out of step with mobile/src/lib/modelMeta.ts: "
        "run python -m scripts.model_display_names")
    assert _rows() == {mid: (long_, short) for mid, long_, short in pairs}


def test_every_model_with_a_cut_has_a_name():
    missing = sorted(set(config.ACTION_THRESHOLDS) - set(_rows()))
    assert not missing, f"give these models a name in modelMeta.ts, then regenerate: {missing}"


def test_the_marker_is_the_hash_of_the_file():
    found = MARK.findall(SQL)
    assert len(found) == 2 and found[0] == found[1], found
    blank = MARK.sub("dashboard_support " + "0" * 12, SQL)
    want = "dashboard_support " + hashlib.sha256(blank.encode("utf-8")).hexdigest()[:12]
    assert found[0] == want, f"set the marker to '{want}' (python -m scripts.model_display_names does it)"


def test_it_is_one_statement_registered_before_the_posted_stake_pair():
    body = CODE.strip()
    assert body.startswith("DO $mig$") and body.endswith("END $mig$;")
    assert body.count("$mig$") == 2
    assert ACTIVE_MIGRATIONS.count(NAME) == 1
    assert ACTIVE_MIGRATIONS.index(NAME) < ACTIVE_MIGRATIONS.index("published_pick_units_2026_10_17.sql")
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"


def test_it_writes_nothing_but_its_own_two_objects():
    """No pick, cut, record or app table is touched."""
    for verb in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "DROP", "ALTER TABLE public.picks",
                 "model_action_thresholds", "CREATE OR REPLACE FUNCTION", "SECURITY DEFINER", "GRANT"):
        assert verb not in CODE, verb
    created = set(re.findall(r"CREATE (?:TABLE IF NOT EXISTS|OR REPLACE VIEW) (public\.\w+)", CODE))
    assert created == {"public.dashboard_layouts", "public.model_display_names"}


def test_the_app_roles_get_nothing_and_the_view_runs_as_the_caller():
    assert "REVOKE ALL ON public.dashboard_layouts FROM anon, authenticated;" in CODE
    assert "REVOKE ALL ON public.model_display_names FROM anon, authenticated;" in CODE
    assert "ALTER TABLE public.dashboard_layouts ENABLE ROW LEVEL SECURITY;" in CODE
    assert "WITH (security_invoker = on)" in CODE
    # the skip needs the revokes to hold too, so a re-grant is undone on the next pass
    skip = CODE[:CODE.index("RETURN;")]
    for role in ("anon", "authenticated"):
        for obj in ("public.dashboard_layouts", "public.model_display_names"):
            assert f"NOT has_table_privilege('{role}', '{obj}', 'SELECT')" in skip, (role, obj)


def test_a_layout_belongs_to_a_named_person_and_one_of_the_four_tabs():
    assert "PRIMARY KEY (owner, tab, name)" in CODE
    assert "CHECK (btrim(owner) <> '')" in CODE
    assert "CHECK (tab IN ('models', 'volume', 'ops', 'picks'))" in CODE
    assert "CHECK (btrim(name) <> '' AND length(name) <= 60)" in CODE
    assert "CHECK (jsonb_typeof(layout) IN ('array', 'object'))" in CODE


def test_in_play_is_known_by_the_same_id_rule_everywhere():
    assert r"(n.model_id LIKE '%\_live\_%') AS in_play" in CODE
    for mid in _rows():
        if mid in config.ACTION_THRESHOLDS:
            assert ("_live_" in mid) == (mid in config.LIVE_MODELS), mid
