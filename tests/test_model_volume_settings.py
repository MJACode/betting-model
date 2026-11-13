"""A volume setting per pre-game model: fewer, stronger bets by one input.

mike, 2026-11-11: "give me bands or thresholds or easy ways to tune every model
for volume based on a simple input, maybe through the retool dash".

What is built (data/migrations/model_volume_settings_2026_11_11.sql, and the
volume part of data/threshold_sync.py):

  * `model_action_thresholds` keeps config.py's own cut in `base_min_*` beside
    the cut in force, `min_*`, which is what the app, Discord and push read.
  * `set_model_volume` is the one input. It can only tighten a pre-game model.
  * The sync writes config's cut and puts the settings back in the same
    transaction, so a setting outlives every pass.

WHAT THESE TESTS ARE, AND ARE NOT. They read the SQL as text and drive the sync
with a connection that records statements. No statement here is run by
Postgres. The check that does run them, on real picks, in a transaction that is
rolled back, is `python -m scripts.model_volume_rehearsal`; run it after any
edit to the migration or the sync. The last section pins that the rehearsal
cannot reach any real object the migration would change.
"""
from __future__ import annotations

import hashlib
import inspect
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import config                                              # noqa: E402
import data.threshold_sync as ts                           # noqa: E402
from data.view_migrations import ACTIVE_MIGRATIONS         # noqa: E402

NAME = "model_volume_settings_2026_11_11.sql"
MIG = ROOT / "data" / "migrations" / NAME
SQL = MIG.read_text(encoding="utf-8")
MARK = re.compile(r"model_volume [0-9a-f]{12}")
IN_PLAY = r"'%\_live\_%'"


def _code(sql: str) -> str:
    """The SQL with -- comments removed, so a clause in a comment proves nothing."""
    return "\n".join(line.split("--", 1)[0] for line in sql.splitlines())


CODE = _code(SQL)


def _between(start: str, end: str) -> str:
    i = CODE.index(start)
    return CODE[i:CODE.index(end, i)]


APPLY = _between("CREATE OR REPLACE FUNCTION public.apply_model_volume_settings()", "$fn$;")
VIEW = _between("CREATE OR REPLACE VIEW public.model_volume_bands", "$view$;")
SETTER = _between("CREATE OR REPLACE FUNCTION public.set_model_volume(", "$fn$;")


# ── the migration ────────────────────────────────────────────────────────────

def test_the_marker_is_the_hash_of_the_file():
    """The skip compares the view's comment to a marker. The marker is the hash
    of this file with the marker blanked, so an edit anywhere in it (a function
    as much as the view) without a new marker is a red test, and with one is
    applied on the next pass."""
    found = MARK.findall(SQL)
    assert len(found) == 2 and found[0] == found[1], found
    blank = MARK.sub("model_volume " + "0" * 12, SQL)
    want = "model_volume " + hashlib.sha256(blank.encode("utf-8")).hexdigest()[:12]
    assert found[0] == want, f"set the marker to '{want}' in both the skip and the COMMENT"


def test_it_is_one_statement_and_it_is_registered_before_the_posted_stake_pair():
    body = CODE.strip()
    assert body.startswith("DO $mig$") and body.endswith("END $mig$;")
    assert body.count("$mig$") == 2
    # The view calls the three-argument unit functions; on a fresh database it
    # waits for them with a NOTICE instead of failing the pass.
    assert "RAISE NOTICE 'model_volume_settings waits for" in CODE
    assert ACTIVE_MIGRATIONS.index(NAME) < ACTIVE_MIGRATIONS.index("published_pick_units_2026_10_17.sql")
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"


def test_a_setting_only_tightens():
    """The cut in force is the tighter of config's and the setting's, for the
    edge cut and the probability cut, and the input refuses a looser number."""
    assert APPLY.count("GREATEST(") == 2 and "LEAST(" not in CODE
    assert "GREATEST(COALESCE(t2.base_min_edge, t2.min_edge)," in APPLY
    assert "GREATEST(COALESCE(t2.base_min_prob, t2.min_prob)," in APPLY
    refusal = SETTER[SETTER.index("IF v < base THEN"):]
    assert refusal.split("END IF;")[0].count("RAISE EXCEPTION 'a volume setting only tightens") == 1
    # ... and it is measured against config's cut, not the cut in force
    assert "COALESCE(t.base_min_edge, t.min_edge, 0)" in SETTER
    assert "COALESCE(t.base_min_prob, t.min_prob, 0)" in SETTER


def test_in_play_models_are_never_moved_and_the_id_pattern_names_them_all():
    """An in-play model's posting does not read min_edge (tracking/
    publish_filters.live_publishable_sql), so raising it would hide in the app
    a bet Discord posted. The SQL knows an in-play model by its id; this pins
    that the id says so for every model config has."""
    for mid in config.ACTION_THRESHOLDS:
        assert ("_live_" in mid) == (mid in config.LIVE_MODELS), mid
    assert f"AND t2.model_id NOT LIKE {IN_PLAY}" in APPLY
    assert f"WHERE s.model_id NOT LIKE {IN_PLAY}" in APPLY
    assert f"(t.model_id LIKE {IN_PLAY}) AS in_play" in VIEW
    guard = SETTER[SETTER.index(f"IF p_model_id LIKE {IN_PLAY} THEN"):]
    assert "RAISE EXCEPTION '% is an in-play model" in guard.split("END IF;")[0]


def test_the_bands_are_cut_on_the_bets_the_producers_post():
    """A band's bet count is only a forecast of what a setting posts if the
    view filters picks the way the producers do. Both halves are pinned: the
    view's clauses, and that the producers still have the clauses they mirror."""
    for clause in (
        "p.signal_type = 'BET'",
        "p.condition_status NOT IN ('VOID', 'DUPLICATE')",
        f"p.downgrade_reason IS DISTINCT FROM '{config.PAUSED_NOTE}'",
        "(p.is_live IS TRUE) = c.in_play",
        "p.model_probability >= c.base_prob",
        "(c.prob_only OR COALESCE(p.decision_edge, p.edge) >= c.base_edge)",
        "COALESCE(p.decision_odds, p.dk_odds) >= c.min_odds",
    ):
        assert clause in VIEW, clause
    # config's own cut, so a setting in force does not move the bands under it
    assert "COALESCE(t.base_min_edge, t.min_edge, 0)::numeric AS base_edge" in VIEW
    assert "COALESCE(t.base_min_prob, t.min_prob, 0)::numeric AS base_prob" in VIEW
    producers = (ROOT / "tracking" / "discord_notifier.py").read_text(encoding="utf-8")
    for clause in (
        "AND p.model_probability >= t.min_prob",
        "OR COALESCE(p.decision_edge, p.edge) >= COALESCE(t.min_edge, 0))",
        "OR COALESCE(p.decision_odds, p.dk_odds) >= t.min_odds)",
    ):
        assert clause in producers, f"the producers' cut changed shape: {clause}"


def test_a_band_is_the_models_own_quartile_and_needs_twenty_bets():
    # trunc, not round: rounded up, a threshold could sit above the bet that
    # defines its band and drop it
    for arm in ("WHEN 'top_75' THEN (CASE WHEN q.n >= 20 THEN trunc(q.q25::numeric, 4) END)",
                "WHEN 'top_half' THEN (CASE WHEN q.n >= 20 THEN trunc(q.q50::numeric, 4) END)",
                "ELSE (CASE WHEN q.n >= 20 THEN trunc(q.q75::numeric, 4) END)"):
        assert arm in VIEW, arm
    for q, frac in (("q25", "0.25"), ("q50", "0.50"), ("q75", "0.75")):
        assert f"percentile_cont({frac}) WITHIN GROUP (ORDER BY x) AS {q}" in VIEW
    assert "FROM recent GROUP BY 1" in VIEW          # per model, never pooled
    assert "COALESCE(q.n, 0) >= 20 AS enough_bets" in VIEW
    # the window is the model's own last 120 days of betting
    assert "to_char(max(game_date)::date - 120, 'YYYY-MM-DD') AS first_day" in VIEW
    # the setter takes the band's threshold from the view, and refuses a NULL one
    assert "SELECT b.threshold INTO v FROM public.model_volume_bands b" in SETTER
    assert "IF v IS NULL THEN" in SETTER


def test_units_are_the_posted_stake_and_only_priced_graded_bets_count():
    assert "public.published_pick_unit_profit(b.price, b.result, b.stake_units)" in VIEW
    assert "public.published_pick_unit_risked(b.price, b.result, b.stake_units)" in VIEW
    assert "b.result IN ('WIN', 'LOSS', 'PUSH') AND b.price IS NOT NULL" in VIEW
    assert "profit_flat" not in CODE


def test_every_change_to_a_setting_is_logged_with_who_made_it():
    assert "AFTER INSERT OR UPDATE OR DELETE ON public.model_volume_settings" in CODE
    assert "FOR EACH ROW EXECUTE FUNCTION public.model_volume_settings_log_row()" in CODE
    assert "set_by    TEXT NOT NULL" in SQL and "CHECK (btrim(set_by) <> '')" in CODE
    # the setter refuses an empty name, and names the remover for the trigger
    assert "RAISE EXCEPTION 'a volume setting needs the name of who set it'" in SETTER
    assert "PERFORM set_config('model_volume.actor', who, true);" in SETTER
    assert "COALESCE(actor, 'direct SQL as ' || session_user)" in CODE
    # the setter applies what it wrote before it returns
    assert SETTER.index("PERFORM public.apply_model_volume_settings();") > SETTER.index(
        "INSERT INTO public.model_volume_settings")


def test_the_app_roles_get_nothing():
    """Default privileges in schema public hand anon and authenticated ALL on
    a new table and EXECUTE on a new function; REVOKE ... FROM PUBLIC alone
    does not take them back (.claude/rules/operations.md)."""
    for obj in ("public.model_volume_settings", "public.model_volume_settings_log",
                "SEQUENCE public.model_volume_settings_log_id_seq", "public.model_volume_bands"):
        assert f"REVOKE ALL ON {obj} FROM anon, authenticated;" in CODE, obj
    for fn in ("public.model_volume_settings_log_row()", "public.apply_model_volume_settings()",
               "public.set_model_volume(text, text, text, numeric, text)"):
        assert f"REVOKE ALL ON FUNCTION {fn} FROM PUBLIC, anon, authenticated;" in CODE, fn
    assert CODE.count("CREATE OR REPLACE FUNCTION") == 3
    for table in ("model_volume_settings", "model_volume_settings_log"):
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;" in CODE
    assert "WITH (security_invoker = on)" in VIEW
    assert "SECURITY DEFINER" not in CODE


# ── the sync ─────────────────────────────────────────────────────────────────

class _Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class _Conn:
    """Records what the sync does, in order."""

    def __init__(self, *, apply_fails=False, savepoint_lost=False, in_force=3):
        self.events: list[tuple] = []
        self.apply_fails, self.savepoint_lost, self.in_force = apply_fails, savepoint_lost, in_force

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        self.events.append(("execute", text, params))
        if "apply_model_volume_settings" in text:
            if self.apply_fails:
                raise RuntimeError("function apply_model_volume_settings() does not exist")
            return _Result([(self.in_force,)])
        if text.startswith("ROLLBACK TO SAVEPOINT") and self.savepoint_lost:
            raise RuntimeError("savepoint does not exist")
        return _Result([])

    def executemany(self, sql, rows):
        self.events.append(("executemany", " ".join(sql.split()), list(rows)))

    def commit(self):
        self.events.append(("commit",))

    def rollback(self):
        self.events.append(("rollback",))

    def close(self):
        self.events.append(("close",))

    def kinds(self) -> list[str]:
        out = []
        for e in self.events:
            if e[0] == "execute":
                out.append(e[1].split(" FROM ")[0] if e[1].startswith("DELETE") else e[1])
            else:
                out.append(e[0])
        return out


def _sync(monkeypatch, *, installed: bool, **conn_kw) -> _Conn:
    seen = []

    def schema_is_current(conn, table, *, columns=(), **kw):
        seen.append((table, tuple(columns)))
        return True if columns == ("scoring_method",) else installed

    monkeypatch.setattr(ts, "schema_is_current", schema_is_current)
    conn = _Conn(**conn_kw)
    conn.returned = ts.sync_action_thresholds(conn)
    conn.guard_reads = seen
    return conn


def _upsert(conn: _Conn) -> tuple[str, list[dict]]:
    (found,) = [e for e in conn.events if e[0] == "executemany"]
    return found[1], found[2]


def _column_values(sql: str) -> dict[str, str]:
    cols = re.search(r"INSERT INTO model_action_thresholds \((.*?)\) VALUES", sql).group(1)
    vals = re.search(r"VALUES \((.*?)\) ON CONFLICT", sql).group(1)
    cols, vals = [c.strip() for c in cols.split(",")], [v.strip() for v in vals.split(",")]
    assert len(cols) == len(vals), (cols, vals)
    return dict(zip(cols, vals))


def test_the_sync_writes_configs_cut_into_both_columns_then_reapplies_the_settings(monkeypatch):
    conn = _sync(monkeypatch, installed=True)
    sql, rows = _upsert(conn)
    wrote = _column_values(sql)
    # config's cut goes to the cut every surface reads AND to the base column
    assert wrote["min_prob"] == wrote["base_min_prob"] == "%(min_prob)s"
    assert wrote["min_edge"] == wrote["base_min_edge"] == "%(min_edge)s"
    update = sql.split("DO UPDATE SET")[1]
    assert "base_min_prob = EXCLUDED.base_min_prob" in update
    assert "base_min_edge = EXCLUDED.base_min_edge" in update
    assert {r["model_id"]: (r["min_prob"], r["min_edge"]) for r in rows} == {
        m: (t["min_prob"], t["min_edge"]) for m, t in config.ACTION_THRESHOLDS.items()}
    # the settings go back on AFTER every write of config's cut, BEFORE the commit
    assert conn.kinds() == [
        "SELECT model_id FROM model_auto_pauses",
        "executemany",
        "DELETE",
        "SAVEPOINT volume_settings",
        "SELECT apply_model_volume_settings()",
        "RELEASE SAVEPOINT volume_settings",
        "commit",
    ]
    assert conn.returned == len(config.ACTION_THRESHOLDS)
    assert ("model_action_thresholds", ("base_min_prob", "base_min_edge")) in conn.guard_reads


def test_the_sync_before_the_migration_is_the_statement_it_always_was(monkeypatch):
    conn = _sync(monkeypatch, installed=False)
    sql, _ = _upsert(conn)
    assert "base_min" not in sql
    assert set(_column_values(sql)) == {"model_id", "min_prob", "min_edge", "min_odds", "prob_only",
                                        "paused", "scoring_method", "updated_at"}
    assert conn.kinds() == ["SELECT model_id FROM model_auto_pauses", "executemany", "DELETE", "commit"]


def test_a_failed_apply_still_commits_configs_cuts(monkeypatch):
    """Failing the whole sync would hold back a pause as well. So the cuts
    land, the failed statement is rolled back to its savepoint (or the commit
    would be refused), and nothing after it is skipped."""
    conn = _sync(monkeypatch, installed=True, apply_fails=True)
    assert conn.kinds()[-4:] == [
        "SAVEPOINT volume_settings",
        "SELECT apply_model_volume_settings()",
        "ROLLBACK TO SAVEPOINT volume_settings",
        "commit",
    ]
    assert "rollback" not in conn.kinds()
    assert conn.returned == len(config.ACTION_THRESHOLDS)


def test_a_lost_savepoint_rolls_the_whole_sync_back(monkeypatch):
    """The one case that cannot fail open: with the savepoint gone the
    transaction cannot be saved, so nothing is committed and the table keeps
    its last good state, settings included."""
    monkeypatch.setattr(ts, "schema_is_current", lambda conn, table, *, columns=(), **kw: True)
    conn = _Conn(apply_fails=True, savepoint_lost=True)
    with pytest.raises(RuntimeError, match="savepoint does not exist"):
        ts.sync_action_thresholds(conn)
    assert "commit" not in conn.kinds() and conn.kinds()[-1] == "rollback"


def test_the_sync_never_runs_the_migrations_ddl():
    """One catalog read a pass, then nothing: DDL on every pass is the outage
    in .claude/rules/operations.md."""
    for fn in (ts._volume_settings_ready, ts._apply_volume_settings):
        src = "\n".join(line for line in inspect.getsource(fn).splitlines()
                        if not line.strip().startswith(("#", '"""')))
        body = src.split('"""')[-1]
        assert not re.search(r"\b(ALTER|CREATE|DROP)\b", body), fn.__name__
    assert "schema_is_current(conn" in inspect.getsource(ts._volume_settings_ready)


# ── the rehearsal ────────────────────────────────────────────────────────────

def test_the_rehearsal_can_only_read_the_real_database():
    """It runs the migration in a transaction it rolls back, with every object
    the migration creates or alters pointed at a scratch schema. If the
    migration gains an object the rehearsal does not redirect, the rehearsal
    would take a lock on the real one: this fails first."""
    from scripts import model_volume_rehearsal as rehearsal

    scratch = _code(rehearsal.scratch_sql())
    assert set(re.findall(r"\bpublic\.\w+", scratch)) == {
        "public.picks", "public.published_pick_unit_profit", "public.published_pick_unit_risked"}
    assert scratch.count(f"{rehearsal.SCRATCH}.model_action_thresholds") == \
        CODE.count("public.model_action_thresholds")
    src = inspect.getsource(rehearsal)
    assert "raw.commit" not in src and "autocommit = True" not in src
    assert "raw.autocommit = False" in src and "raw.rollback()" in src
