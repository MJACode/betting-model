"""Rehearse the volume-setting migration and the threshold sync on real data.

    python -m scripts.model_volume_rehearsal [--out DIR]

Run it after any edit to data/migrations/model_volume_settings_2026_11_11.sql
or to the volume part of data/threshold_sync.py, BEFORE the edit merges. The
pytest file (tests/test_model_volume_settings.py) reads the SQL as text and
drives the sync with a recording connection; neither runs a statement. This
does: Postgres parses every function, the bands are computed from the real
picks, and the sync's own SQL is executed.

IT WRITES NOTHING. Everything runs in one transaction that is rolled back,
and the last check reads the catalog on a new connection to prove it. The
real model_action_thresholds is never altered or locked: the migration's
table, functions and view are pointed at a scratch schema that holds a copy
of it. `picks` and the posted-unit functions are the real ones, read only.

What that leaves unrehearsed, and is checked after the real apply instead:
the privileges anon and authenticated hold (default privileges are granted
in schema public only), and data.threshold_sync's own "has the migration
run?" read, which looks at schema public (replaced here by a constant).

--out DIR also writes the bands as DIR/bands.csv.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg2                                        # noqa: E402
import psycopg2.extras                                 # noqa: E402

import config                                          # noqa: E402
import data.threshold_sync as ts                       # noqa: E402
from data.db import _adapt_sql                         # noqa: E402

MIGRATION = ROOT / "data" / "migrations" / "model_volume_settings_2026_11_11.sql"
SCRATCH = "mvtest"

# Every object the migration creates or alters, pointed at the scratch schema.
SUBS = [
    ("table_schema = 'public' AND table_name = 'model_action_thresholds'",
     f"table_schema = '{SCRATCH}' AND table_name = 'model_action_thresholds'"),
    ("public.model_action_thresholds", f"{SCRATCH}.model_action_thresholds"),
    ("public.model_volume_", f"{SCRATCH}.model_volume_"),
    ("public.apply_model_volume_settings", f"{SCRATCH}.apply_model_volume_settings"),
    ("public.set_model_volume", f"{SCRATCH}.set_model_volume"),
]

# The cut the pre-game producers apply (tracking/discord_notifier._new_signals)
# and the record's one-bet-per-event rule (no DUPLICATE copy), per model over
# the days the view uses for it: %s is two arrays, model ids and first days.
PRODUCERS_COUNT = f"""
    SELECT p.model_id, count(*) FROM public.picks p
      JOIN {SCRATCH}.model_action_thresholds t ON t.model_id = p.model_id
      JOIN unnest(%s::text[], %s::text[]) AS w(model_id, first_day) ON w.model_id = p.model_id
     WHERE p.signal_type = 'BET'
       AND (p.is_live IS NULL OR p.is_live = FALSE)
       AND (p.condition_status IS NULL OR p.condition_status NOT IN ('VOID', 'DUPLICATE'))
       AND p.downgrade_reason IS DISTINCT FROM '{config.PAUSED_NOTE}'
       AND p.model_probability >= t.min_prob
       AND (t.prob_only = TRUE OR COALESCE(p.decision_edge, p.edge) >= COALESCE(t.min_edge, 0))
       AND (t.min_odds IS NULL OR COALESCE(p.decision_odds, p.dk_odds) IS NULL
            OR COALESCE(p.decision_odds, p.dk_odds) >= t.min_odds)
       AND p.game_date >= w.first_day
     GROUP BY 1
"""


def scratch_sql() -> str:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert _adapt_sql(sql) == sql.strip(), "data.db's adapter rewrites this migration"
    for a, b in SUBS:
        assert a in sql, a
        sql = sql.replace(a, b)
    for left in ("public.model_", "public.apply", "public.set_"):
        assert left not in sql, f"{left} still points at schema public"
    return sql


class Rehearsal:
    def __init__(self, raw):
        self.raw = raw
        self.checks: list[tuple[str, bool, str]] = []

    def ok(self, name: str, cond, detail="") -> None:
        self.checks.append((name, bool(cond), str(detail)))
        print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail != "" else ""),
              flush=True)

    def q(self, sql: str, params=None) -> list:
        cur = self.raw.cursor()
        cur.execute(sql, params)
        return cur.fetchall() if cur.description else []

    def one(self, sql: str, params=None):
        rows = self.q(sql, params)
        return rows[0] if rows else None

    def refused(self, label: str, sql: str, params, needle: str) -> None:
        """The statement must raise, with `needle` in the message."""
        self.q("SAVEPOINT refused")
        try:
            self.q(sql, params)
            self.q("RELEASE SAVEPOINT refused")
            self.ok(label, False, "did not raise")
        except psycopg2.Error as exc:
            self.q("ROLLBACK TO SAVEPOINT refused")
            msg = str(exc).splitlines()[0]
            self.ok(label, needle in msg, msg)


class NoCommit:
    """What sync_action_thresholds is handed: its own statements, no commit."""

    def __init__(self, raw):
        self.raw = raw
        self.commits = 0

    def execute(self, sql, params=None):
        cur = self.raw.cursor()
        adapted = _adapt_sql(sql)
        if params is not None:
            cur.execute(adapted, params)
        else:
            cur.execute(adapted)
        return cur

    def executemany(self, sql, rows):
        psycopg2.extras.execute_batch(self.raw.cursor(), _adapt_sql(sql), rows)

    def commit(self):
        self.commits += 1

    def rollback(self):
        raise RuntimeError("the sync asked for a rollback")

    def close(self):
        pass


def rehearse(r: Rehearsal, out: Path | None) -> None:
    q, one, ok, refused = r.q, r.one, r.ok, r.refused
    T = f"{SCRATCH}.model_action_thresholds"

    q("SET LOCAL lock_timeout = '3s'")
    q("SET LOCAL statement_timeout = '90s'")
    q(f"CREATE SCHEMA {SCRATCH}")
    q(f"CREATE TABLE {T} (LIKE public.model_action_thresholds INCLUDING ALL)")
    q(f"INSERT INTO {T} SELECT * FROM public.model_action_thresholds")
    q(f"SET LOCAL search_path = {SCRATCH}, public")
    n_models = one(f"SELECT count(*) FROM {T}")[0]
    ok("the copy holds every model config has", n_models == len(config.ACTION_THRESHOLDS),
       f"{n_models} rows, {len(config.ACTION_THRESHOLDS)} in config")

    # 1. the migration applies, and a second pass returns on the catalog read
    sql = scratch_sql()
    q(sql)
    ok("base cuts start equal to the cuts in the table",
       one(f"SELECT count(*) FROM {T} WHERE base_min_edge IS DISTINCT FROM min_edge "
           "OR base_min_prob IS DISTINCT FROM min_prob")[0] == 0)
    trg = one("SELECT oid FROM pg_trigger WHERE tgname = 'model_volume_settings_log_trg'")[0]
    q(sql)
    ok("a second pass changes nothing (the trigger is not rebuilt)",
       one("SELECT oid FROM pg_trigger WHERE tgname = 'model_volume_settings_log_trg'")[0] == trg)

    # 2. the bands, on the real picks
    cur = r.raw.cursor()
    cur.execute(f"SELECT * FROM {SCRATCH}.model_volume_bands ORDER BY sport, model_id, band_order")
    cols = [d[0] for d in cur.description]
    bands = [dict(zip(cols, row)) for row in cur.fetchall()]
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        with (out / "bands.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(bands)
    ok("four bands for every model", len(bands) == 4 * n_models, len(bands))
    by: dict[str, dict[str, dict]] = {}
    for b in bands:
        by.setdefault(b["model_id"], {})[b["band"]] = b
    tight = ("top_75", "top_half", "top_quarter")
    enough = sorted(m for m, bs in by.items() if bs["all"]["enough_bets"])
    pre = [m for m in enough if not by[m]["all"]["in_play"]]
    ok("some pre-game models have bands", len(pre) > 0,
       f"{len(pre)} pre-game and {len(enough) - len(pre)} in-play of {n_models} models")
    ok("a tighter band never has a lower threshold or more bets",
       all(by[m]["all"]["threshold"] <= by[m]["top_75"]["threshold"]
           <= by[m]["top_half"]["threshold"] <= by[m]["top_quarter"]["threshold"]
           and by[m]["all"]["recent_bets"] >= by[m]["top_75"]["recent_bets"]
           >= by[m]["top_half"]["recent_bets"] >= by[m]["top_quarter"]["recent_bets"] > 0
           for m in enough))
    ok("a model with too few bets has no band thresholds",
       all(bs[b]["threshold"] is None and bs[b]["recent_bets"] == 0
           for m, bs in by.items() if not bs["all"]["enough_bets"] for b in tight))
    ok("the 'all' band is config's own cut for every model",
       all(float(bs["all"]["threshold"]) == float(
               config.ACTION_THRESHOLDS[m]["min_prob"] if m in config.PROB_ONLY_MODELS
               else config.ACTION_THRESHOLDS[m]["min_edge"])
           for m, bs in by.items()))
    ok("the id pattern and the rows agree on which models are in-play",
       all(bs["all"]["in_play"] == (m in config.LIVE_MODELS) for m, bs in by.items()))

    ok("each band keeps at least its share of the bets",
       all(by[m][b]["recent_bets"] >= share * by[m]["all"]["recent_bets"] - 1
           for m in enough for b, share in zip(tight, (0.75, 0.5, 0.25))))

    # every pre-game model that has bet: the view's count is the producers' own
    betting = sorted(k for k, bs in by.items()
                     if not bs["all"]["in_play"] and bs["all"]["first_bet_date"])
    days = [by[k]["all"]["first_bet_date"] for k in betting]

    def producers() -> dict[str, int]:
        return dict(q(PRODUCERS_COUNT, (betting, days)))

    posted = producers()
    wrong = {k: (posted.get(k, 0), by[k]["all"]["recent_bets"]) for k in betting
             if posted.get(k, 0) != by[k]["all"]["recent_bets"]}
    ok("'all' counts the bets the producers' cut passes, for every pre-game model",
       not wrong, f"{len(betting)} models, {sum(posted.values())} bets" if not wrong else wrong)

    edge_models = [m for m in pre if m not in config.PROB_ONLY_MODELS]
    m = max(edge_models, key=lambda k: by[k]["all"]["recent_bets"])
    before = posted[m]

    # 3. one input
    half, base = by[m]["top_half"]["threshold"], by[m]["all"]["config_cut"]
    got = one(f"SELECT * FROM {SCRATCH}.set_model_volume(%s, 'top_half', 'rehearsal')", (m,))
    ok("top_half puts that band's threshold in force",
       got[1] == "top_half" and got[4] == half and got[3] == base,
       f"{m}: config {base}, in force {got[4]}")
    row = one(f"SELECT min_edge, base_min_edge, min_prob, base_min_prob FROM {T} WHERE model_id = %s", (m,))
    ok("the table's cut is the setting, config's cut is kept beside it",
       row[0] == half and row[1] == base and row[2] == row[3], row)
    now = producers()
    ok(f"the producers' cut now passes the band's bets, no more ({m})",
       now[m] == by[m]["top_half"]["recent_bets"],
       f"{before} before, {now[m]} after, the band says {by[m]['top_half']['recent_bets']}")
    ok("and every other model posts what it did",
       {k: v for k, v in now.items() if k != m} == {k: v for k, v in posted.items() if k != m})
    ok("no other model moved",
       one(f"SELECT count(*) FROM {T} WHERE model_id <> %s AND (min_edge IS DISTINCT FROM base_min_edge "
           "OR min_prob IS DISTINCT FROM base_min_prob)", (m,))[0] == 0)
    v = one(f"SELECT setting, setting_value, setting_in_force, setting_by, cut_in_force "
            f"FROM {SCRATCH}.model_volume_bands WHERE model_id = %s AND band = 'all'", (m,))
    ok("the view shows the setting and that it is in force",
       v == ("top_half", half, True, "rehearsal", half), v)
    still = one(f"SELECT threshold, recent_bets FROM {SCRATCH}.model_volume_bands "
                "WHERE model_id = %s AND band = 'top_half'", (m,))
    ok("a setting does not move the bands (they are cut at config's)",
       still == (half, by[m]["top_half"]["recent_bets"]), still)

    call = f"SELECT * FROM {SCRATCH}.set_model_volume"
    refused("a number under config's cut is refused", call + "(%s, 'custom', 'rehearsal', %s)",
            (m, float(base) - 0.005 if float(base) > 0.005 else -0.001), "only tightens")
    live = sorted(k for k in by if by[k]["all"]["in_play"])[0]
    refused("an in-play model is refused", call + "(%s, 'custom', 'rehearsal', 0.2)", (live,), "in-play")
    thin = sorted(k for k, bs in by.items() if not bs["all"]["enough_bets"] and not bs["all"]["in_play"])[0]
    refused("a band is refused for a model with too few bets",
            call + "(%s, 'top_half', 'rehearsal')", (thin,), "under 20 bets")
    refused("an unknown model is refused", call + "('no_such_model', 'top_half', 'rehearsal')", None, "no model")
    refused("a setting with no name is refused", call + "(%s, 'top_half', '  ')", (m,), "who set it")
    refused("an unknown level is refused", call + "(%s, 'most', 'rehearsal')", (m,), "unknown level")
    refused("a number of 1 or more is refused", call + "(%s, 'custom', 'rehearsal', 5)", (m,), "decimal under 1")
    refused("a custom setting with no number is refused", call + "(%s, 'custom', 'rehearsal')", (m,),
            "needs a number")
    ok("a refusal leaves the setting as it was",
       one(f"SELECT level, min_edge FROM {SCRATCH}.model_volume_settings WHERE model_id = %s", (m,))
       == ("top_half", half))

    po = sorted(config.PROB_ONLY_MODELS & set(by))[0]
    got = one(call + "(%s, 'custom', 'rehearsal', %s)",
              (po, round(float(by[po]["all"]["config_cut"]) + 0.03, 4)))
    row = one(f"SELECT min_prob - base_min_prob, min_edge - base_min_edge FROM {T} WHERE model_id = %s", (po,))
    ok("a probability-cut model moves its probability cut only",
       got[2] == "probability" and abs(row[0] - 0.03) < 1e-9 and row[1] == 0, (po, row))

    q(f"INSERT INTO {SCRATCH}.model_volume_settings (model_id, level, min_edge, set_by) "
      "VALUES (%s, 'custom', 0.5, 'rehearsal')", (live,))
    n_in_force = one(f"SELECT {SCRATCH}.apply_model_volume_settings()")[0]
    row = one(f"SELECT min_edge, base_min_edge FROM {T} WHERE model_id = %s", (live,))
    ok("a setting written straight in for an in-play model is never applied",
       row[0] == row[1] and n_in_force == 2, (row, n_in_force))
    v = one(f"SELECT setting, setting_in_force FROM {SCRATCH}.model_volume_bands "
            "WHERE model_id = %s AND band = 'all'", (live,))
    ok("and the view says it is not in force", v == ("custom", False), v)

    # 4. the sync keeps the settings
    def differs() -> list[str]:
        return sorted(x[0] for x in q(
            f"SELECT model_id FROM {T} WHERE min_edge IS DISTINCT FROM base_min_edge "
            "OR min_prob IS DISTINCT FROM base_min_prob"))

    ready = ts._volume_settings_ready
    try:
        ts._volume_settings_ready = lambda conn: True      # the real read looks at schema public
        conn = NoCommit(r.raw)
        n = ts.sync_action_thresholds(conn)
        ok("the sync wrote every model and committed once", (n, conn.commits) == (n_models, 1),
           (n, conn.commits))
        ok("after the sync, base cuts are config.py's for every model",
           all(float(e) == float(config.ACTION_THRESHOLDS[k]["min_edge"])
               and float(p) == float(config.ACTION_THRESHOLDS[k]["min_prob"])
               for k, e, p in q(f"SELECT model_id, base_min_edge, base_min_prob FROM {T}")))
        ok("after the sync, only the two models with a setting differ from config",
           differs() == sorted([m, po]), differs())
        ok("after the sync, the setting is still the cut in force",
           one(f"SELECT min_edge FROM {T} WHERE model_id = %s", (m,))[0] == half)

        q(f"ALTER FUNCTION {SCRATCH}.apply_model_volume_settings() RENAME TO apply_model_volume_settings_gone")
        conn = NoCommit(r.raw)
        n = ts.sync_action_thresholds(conn)
        ok("a broken apply step still syncs config's cuts",
           (n, conn.commits, differs()) == (n_models, 1, []), (n, conn.commits, differs()))
        q(f"ALTER FUNCTION {SCRATCH}.apply_model_volume_settings_gone() RENAME TO apply_model_volume_settings")

        ts._volume_settings_ready = lambda conn: False     # a database the migration has not reached
        q(f"UPDATE {T} SET base_min_edge = 0.77 WHERE model_id = %s", (m,))
        conn = NoCommit(r.raw)
        ts.sync_action_thresholds(conn)
        ok("the sync before the migration touches neither the new columns nor the function",
           one(f"SELECT base_min_edge FROM {T} WHERE model_id = %s", (m,))[0] == 0.77 and conn.commits == 1)

        ts._volume_settings_ready = lambda conn: True
        ts.sync_action_thresholds(NoCommit(r.raw))
        ok("the next full sync puts the setting back",
           one(f"SELECT min_edge, base_min_edge FROM {T} WHERE model_id = %s", (m,)) == (half, base))
    finally:
        ts._volume_settings_ready = ready

    # 5. removing it, and the log
    got = one(call + "(%s, 'all', 'rehearsal two')", (m,))
    row = one(f"SELECT min_edge, base_min_edge FROM {T} WHERE model_id = %s", (m,))
    ok("'all' removes the setting and config's cut is back in force",
       got[1] is None and got[4] == base and row == (base, base), (got, row))
    log = q(f"SELECT action, model_id, level, set_by FROM {SCRATCH}.model_volume_settings_log ORDER BY id")
    ok("the log holds each set and the removal, with who did it",
       log == [("set", m, "top_half", "rehearsal"), ("set", po, "custom", "rehearsal"),
               ("set", live, "custom", "rehearsal"), ("removed", m, "top_half", "rehearsal two")], log)
    q("SELECT set_config('model_volume.actor', '', true)")
    q(f"DELETE FROM {SCRATCH}.model_volume_settings WHERE model_id = %s", (po,))
    last = one(f"SELECT action, set_by FROM {SCRATCH}.model_volume_settings_log ORDER BY id DESC LIMIT 1")
    ok("a removal made in plain SQL is logged with the database role",
       last[0] == "removed" and last[1].startswith("direct SQL as "), last)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=None, help="also write the bands to DIR/bands.csv")
    args = ap.parse_args(argv)
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set")
        return 2

    raw = psycopg2.connect(url)
    raw.autocommit = False
    r = Rehearsal(raw)
    try:
        rehearse(r, args.out)
    finally:
        raw.rollback()
        raw.close()

    check = psycopg2.connect(url)
    try:
        cur = check.cursor()
        cur.execute("""SELECT to_regnamespace(%s) IS NULL,
                              (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                                WHERE n.nspname = %s)""", (SCRATCH, SCRATCH))
        gone = cur.fetchone()
    finally:
        check.close()
    r.ok("rolled back: the scratch schema and everything in it are gone", gone == (True, 0), gone)

    bad = [c for c in r.checks if not c[1]]
    print(f"\n{len(r.checks) - len(bad)} of {len(r.checks)} checks passed")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
