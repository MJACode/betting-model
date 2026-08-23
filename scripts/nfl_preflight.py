#!/usr/bin/env python3
"""
NFL preflight — is the wind/opener stack actually wired correctly?

    python -m scripts.nfl_preflight

Read-only and offline. Spends no Odds API credits and needs no database: every
check is against code, config and schedule. Checks that genuinely need the live
DB are reported as such rather than silently skipped.

Run this after any change to the NFL models, the publisher, or the scheduler,
and before the first game of the season.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NFL = ROOT / "nfl"
sys.path.insert(0, str(ROOT))

PASS, FAIL, WARN, INFO = "PASS", "FAIL", "WARN", "INFO"
results: list[tuple[str, str, str]] = []


def check(section: str, name: str, ok, detail: str = "") -> None:
    status = ok if isinstance(ok, str) else (PASS if ok else FAIL)
    results.append((section, status, f"{name}{'  — ' + detail if detail else ''}"))


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    # Register BEFORE exec. A module using @dataclass under
    # `from __future__ import annotations` resolves its string annotations via
    # sys.modules[cls.__module__]; if it is not there yet, dataclasses raises
    # "'NoneType' object has no attribute '__dict__'" — which is what
    # wind_totals (it has a @dataclass Bet) did on the first run of this script.
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #

def check_models() -> None:
    s = "MODELS"
    try:
        opener = _load(NFL / "models" / "opener_spread.py", "pf_opener")
        check(s, "opener_spread imports", True)
        p1, p3 = opener.model_prob_for_dev(1.0), opener.model_prob_for_dev(3.0)
        check(s, "per-bet probability scales with deviation", p1 < p3,
              f"1pt={p1:.4f} < 3pt={p3:.4f}")
        check(s, "minimum modelled probability clears the config gate",
              p1 > 0.55, f"{p1:.4f} > 0.55")
        check(s, "edge tiers", opener.edge_tier(0.01) == "SMALL"
              and opener.edge_tier(0.04) == "MEDIUM"
              and opener.edge_tier(0.07) == "LARGE")
        check(s, "defective books excluded", len(opener.DEFECTIVE_BOOKS) == 4,
              ", ".join(sorted(opener.DEFECTIVE_BOOKS)))
    except Exception as exc:                                   # noqa: BLE001
        check(s, "opener_spread", False, repr(exc))

    try:
        # Load by PATH, not `from models.wind_totals import ...`. The platform
        # has its own top-level `models` package with an __init__.py, so from
        # the repo root the bare import resolves there and raises. This script
        # fell into exactly that trap on its first run; the production cards do
        # not, because the scheduler runs them with cwd=nfl/.
        sys.path.insert(0, str(NFL))       # so wind_totals can reach data_ingest
        w = _load(NFL / "models" / "wind_totals.py", "pf_wind")
        MAX_CALIBRATED_LEAD = w.MAX_CALIBRATED_LEAD
        MIN_LIVE_LEAD = w.MIN_LIVE_LEAD
        UNIT_PCT = w.UNIT_PCT
        model_under_prob, stake_units = w.model_under_prob, w.stake_units
        check(s, "wind_totals imports", True)
        check(s, "lead calibration measured to day 7", MAX_CALIBRATED_LEAD == 7)
        check(s, "live probability floors at lead 1 (never the ERA5 truth row)",
              MIN_LIVE_LEAD == 1 and model_under_prob(0) == model_under_prob(1))
        check(s, "uncalibrated lead sizes to ZERO",
              stake_units(model_under_prob(8), -110, 8) == 0.0)
        check(s, "calibrated lead sizes above zero",
              stake_units(model_under_prob(3), -110, 3) > 0)
        check(s, "1 unit = 1% of bankroll", UNIT_PCT == 0.01)
    except Exception as exc:                                   # noqa: BLE001
        check(s, "wind_totals", False, repr(exc))


def check_import_shadowing() -> None:
    """The platform's `models` package shadows nfl/models. Prove it still does,
    because the card's path-loading only looks like paranoia until it isn't."""
    s = "IMPORT SAFETY"
    import models as platform_models
    where = Path(platform_models.__file__).parent
    check(s, "platform `models` package wins from the repo root",
          where == ROOT / "models", str(where))
    check(s, "nfl models are NOT reachable as models.*",
          not hasattr(platform_models, "wind_totals")
          and not hasattr(platform_models, "opener_spread"))
    card = (NFL / "scripts" / "daily_opener_card.py").read_text(encoding="utf-8")
    # Anchored to the start of a line: the card's docstring legitimately quotes
    # the unsafe import while explaining why not to use it, and matching that
    # prose is how this check failed the first time it ran.
    bare = re.search(r"^\s*from\s+models\.", card, re.MULTILINE)
    check(s, "opener card loads its model by path, not by bare import",
          "_load_nfl_model" in card and bare is None,
          f"found: {bare.group(0).strip()!r}" if bare else "")


def check_lock_semantics() -> None:
    s = "THE LOCK"
    pub = (ROOT / "scripts" / "nfl_wind_publisher.py").read_text(encoding="utf-8")
    wind = pub[pub.index("def publish("):pub.index("def publish_opener(")]
    opener = pub[pub.index("def publish_opener("):]
    check(s, "wind never deletes unstarted picks",
          "DELETE FROM PICKS" not in wind.upper())
    check(s, "wind skips already-locked games",
          "SELECT DISTINCT game_id FROM picks" in wind)
    check(s, "opener insert-once lock intact",
          "INSERT-ONCE LOCK" in opener and "DELETE FROM PICKS" not in opener.upper())

    mon = (ROOT / "scripts" / "nfl_pick_monitor.py").read_text(encoding="utf-8")
    upd = mon[mon.index("UPDATE picks"):mon.index("WHERE pick_id = %s")]
    forbidden = [c for c in ("scored_line", "dk_odds", "model_probability", "edge",
                             "recommended_bet", "kelly_fraction", "pick_side",
                             "pick_label", "signal_type") if c in upd]
    check(s, "monitor writes no column describing the BET", not forbidden,
          f"would touch {forbidden}" if forbidden else "condition_* only")
    check(s, "monitor contains no SQL delete", "DELETE FROM" not in mon.upper())


def check_schedule() -> None:
    s = "POLLING"
    sch = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    check(s, "hourly poll job registered", 'id="nfl_poll_hourly"' in sch)
    check(s, "fast poll job registered", 'id="nfl_poll_fast"' in sch)
    check(s, "fast poll cron is every 10 min", 'CronTrigger(minute="*/10"' in sch)
    m = re.search(r"NFL_POLL_HORIZON_DAYS\s*=\s*([\d.]+)", sch)
    check(s, "horizon is 10 days", bool(m) and float(m.group(1)) == 10.0,
          f"{m.group(1) if m else '?'} days")
    m2 = re.search(r"NFL_FAST_WINDOW_HOURS\s*=\s*([\d.]+)", sch)
    check(s, "fast window is 3 hours", bool(m2) and float(m2.group(1)) == 3.0,
          f"{m2.group(1) if m2 else '?'} h")
    check(s, "old fixed wind-card slots removed",
          "nfl_wind_card_" not in sch and 'id="nfl_opener_card"' not in sch)
    check(s, "monitor runs on every tick", "scripts.nfl_pick_monitor" in sch)
    check(s, "both cards run with cwd=nfl/", sch.count('cwd=ROOT / "nfl"') >= 2)


def check_cards_run() -> None:
    s = "ENTRYPOINTS"
    for script in ("scripts/daily_opener_card.py", "scripts/weekly_wind_card.py"):
        r = subprocess.run([sys.executable, script, "--help"], cwd=NFL,
                           capture_output=True, text=True, timeout=180)
        check(s, f"{script} runs from nfl/", r.returncode == 0,
              (r.stderr or "").strip().splitlines()[-1:] and
              (r.stderr or "").strip().splitlines()[-1] if r.returncode else "")
    check(s, "opener watches wider than it fires",
          "--watch-days" in (NFL / "scripts" / "daily_opener_card.py").read_text(
              encoding="utf-8"))


def check_schema() -> None:
    s = "SCHEMA"
    import sqlite3
    from data.db_setup import SCHEMA_SQL, _load_postgres_schema, _split_sql_statements
    stmts = _split_sql_statements(_load_postgres_schema())
    kw = ("CREATE", "ALTER", "DROP", "INSERT", "UPDATE", "GRANT", "REVOKE",
          "COMMENT", "DO", "SELECT", "SET", "WITH", "BEGIN", "COMMIT")
    bad = [x for x in stmts if not x.upper().lstrip("( \n").startswith(kw)]
    check(s, "postgres schema splits into pure SQL", not bad,
          f"{len(stmts)} statements, {len(bad)} bad")
    c = sqlite3.connect(":memory:")
    c.executescript(SCHEMA_SQL)
    picks = {r[1] for r in c.execute("PRAGMA table_info(picks)")}
    inj = {r[1] for r in c.execute("PRAGMA table_info(injuries)")}
    hist = {r[1] for r in c.execute("PRAGMA table_info(nfl_pick_status_history)")}
    cond = {"condition_status", "condition_note", "condition_checked_at"}
    check(s, "picks has the condition columns", cond <= picks)
    check(s, "injuries does NOT have them", not (cond & inj))
    check(s, "history table defined", {"still_qualifies", "status", "reason"} <= hist)
    check(s, "live Postgres migration", INFO,
          "applied via the DB Migrate workflow; re-run it after any schema change")


def check_config_gates() -> None:
    s = "GATES"
    cfg = (ROOT / "config.py").read_text(encoding="utf-8")
    check(s, "nfl_opener_spread registered", "nfl_opener_spread" in cfg)
    check(s, "nfl_wind_totals registered", "nfl_wind_totals" in cfg)
    m = re.search(r'"nfl_opener_spread":\s*\{"min_prob":\s*([\d.]+)', cfg)
    if m:
        opener = _load(NFL / "models" / "opener_spread.py", "pf_opener2")
        lo = opener.model_prob_for_dev(1.0)
        check(s, "no bet is gated out by min_prob", lo > float(m.group(1)),
              f"min modelled {lo:.4f} vs gate {m.group(1)}")


def check_data() -> None:
    s = "DATA"
    import csv as _csv
    g = NFL / "data" / "games.csv"
    check(s, "games.csv present", g.exists())
    if g.exists():
        now = datetime.now(timezone.utc).date().isoformat()
        with g.open(newline="", encoding="utf-8") as fh:
            rows = list(_csv.DictReader(fh))
        future = [r for r in rows if (r.get("gameday") or "") >= now]
        seasons = sorted({r.get("season") for r in rows if r.get("season")})
        check(s, "schedule covers upcoming games", len(future) > 0,
              f"{len(future)} future games, seasons through {seasons[-1] if seasons else '?'}")
        if future:
            nxt = min(r["gameday"] for r in future)
            check(s, "next kickoff", INFO, nxt)
    cache = NFL / "data" / "odds_cache"
    check(s, "odds cache present", cache.exists() and len(list(cache.iterdir())) > 5000,
          f"{len(list(cache.iterdir())) if cache.exists() else 0} snapshots")


def check_secrets() -> None:
    s = "CREDENTIALS"
    check(s, "worker needs THE_ODDS_API_KEY or ODDS_API_KEY", INFO,
          "scheduler falls back to ODDS_API_KEY; without either the wind card "
          "runs --dry-run and the opener card no-ops")
    check(s, "worker needs DATABASE_URL", INFO,
          "publishers and the monitor need it; cards themselves do not")
    check(s, "RUN_NFL_WIND_CARD gates all NFL jobs", INFO,
          "set to 0 to disable NFL polling entirely")


def check_cost() -> None:
    s = "CREDIT COST"
    check(s, "per tick", INFO, "4 credits (2 markets x us,eu)")
    check(s, "hourly, in season", INFO, "~96/day")
    check(s, "fast window, per kickoff cluster", INFO, "~18 ticks x 4 = 72")
    check(s, "off-season / no game inside 10 days", INFO, "0 — driver returns early")


def main() -> int:
    for fn in (check_models, check_import_shadowing, check_lock_semantics, check_schedule, check_cards_run,
               check_schema, check_config_gates, check_data, check_secrets, check_cost):
        try:
            fn()
        except Exception as exc:                               # noqa: BLE001
            check(fn.__name__.replace("check_", "").upper(), "check crashed", False, repr(exc))

    width = max(len(r[2]) for r in results) + 2
    section = None
    for sec, status, text in results:
        if sec != section:
            print(f"\n=== {sec} ===")
            section = sec
        mark = {"PASS": "  ok  ", "FAIL": " FAIL ", "WARN": " warn ", "INFO": " note "}[status]
        print(f"[{mark}] {text:<{width}}")

    fails = [r for r in results if r[1] == FAIL]
    warns = [r for r in results if r[1] == WARN]
    print("\n" + "=" * 72)
    print(f"{len([r for r in results if r[1] == PASS])} passed, "
          f"{len(fails)} failed, {len(warns)} warning(s)")
    if fails:
        print("\nFAILURES:")
        for _, _, t in fails:
            print(f"  - {t}")
    print("=" * 72)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
