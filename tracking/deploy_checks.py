"""
Named, read-only checks a worker job can run at a chosen time and announce.

WHY (session 280, 2026-09-11). mike: *"Schedule run to confirm these things
and alert me."* Two things the deploy of #645/#659 could only be judged on
hours later -- the 6am full-horizon pass replacing the pre-deploy AVOID rows,
and the worker's own hourly Kalshi snapshot landing -- and the only honest
way to report either is to run the query at that time on the machine that
does the work. So a check is a NAME in this registry, a job names the checks
it wants and the time it may run (`worker_jobs.run_after`), and the queue's
own announce posts the verdict to the ops Discord channel. A failed check
raises, so the queue's ❌ card is the alert.

Each check returns (ok, detail). Read-only by construction: the registry
holds SELECTs only, and a job cannot name a check that is not here.
"""
from __future__ import annotations

from datetime import datetime, timezone


def _ncaaf_paused_avoid_gone(conn) -> tuple[bool, str]:
    """After #645, no paused model may hold an AVOID on an unstarted game.

    The evening pass after the deploy re-scored only the near window, leaving
    43 pre-deploy `ncaaf_moneyline` AVOIDs on look-ahead games; the 6am
    full-horizon pass deletes and re-scores every unstarted non-BET row.
    """
    n, = conn.execute("""
        SELECT COUNT(*) FROM picks
        WHERE signal_type = 'AVOID' AND result IS NULL
          AND game_time::timestamptz > NOW()
          AND model_id IN (SELECT model_id FROM model_action_thresholds WHERE paused)
    """).fetchone()
    none_ok, = conn.execute("""
        SELECT COUNT(*) FROM picks
        WHERE model_id = 'ncaaf_moneyline' AND signal_type = 'NONE'
          AND downgrade_reason = 'model paused'
          AND game_time::timestamptz > NOW()
    """).fetchone()
    return (int(n) == 0,
            f"paused-model AVOID rows on unstarted games: {n} (expected 0); "
            f"ncaaf_moneyline NONE rows carrying 'model paused': {none_ok}")


def _kalshi_game_snapshot_fresh(conn) -> tuple[bool, str]:
    """The worker's own Kalshi NCAAF snapshot (job at :45) has landed and the
    event join was refreshed with it -- both within the last two hours."""
    row = conn.execute("""
        SELECT MAX(snapshot_at), COUNT(DISTINCT snapshot_at),
               (SELECT MAX(resolved_at) FROM kalshi_ncaaf_events),
               (SELECT COUNT(*) FROM kalshi_ncaaf_events WHERE game_id IS NOT NULL)
        FROM kalshi_game_markets
    """).fetchone()
    last_snap, n_snaps, last_res, n_resolved = row
    now = datetime.now(timezone.utc)

    def _age(t):
        if t is None:
            return None
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (now - t).total_seconds() / 3600

    a_snap, a_res = _age(last_snap), _age(last_res)
    ok = (a_snap is not None and a_snap <= 2.0 and a_res is not None and a_res <= 2.0
          and int(n_snaps) >= 2)
    return (ok,
            f"last kalshi_game_markets snapshot {last_snap} ({a_snap and round(a_snap, 2)}h ago), "
            f"{n_snaps} snapshots so far; kalshi_ncaaf_events last resolved {last_res} "
            f"({a_res and round(a_res, 2)}h ago), {n_resolved} events resolved")


CHECKS = {
    "ncaaf_paused_avoid_gone": _ncaaf_paused_avoid_gone,
    "kalshi_game_snapshot_fresh": _kalshi_game_snapshot_fresh,
}


def run_checks(conn, names: list[str]) -> dict:
    """Run the named checks. Raises if any fails, so the queue announces ❌."""
    results = {}
    failed = []
    for name in names:
        ok, detail = CHECKS[name](conn)
        results[name] = {"ok": ok, "detail": detail}
        if not ok:
            failed.append(name)
    out = {"verdict": "PASS" if not failed else "FAIL",
           "checked_at": datetime.now(timezone.utc).isoformat(),
           "checks": results}
    if failed:
        raise RuntimeError(
            "verification FAILED: " + "; ".join(f"{n}: {results[n]['detail']}" for n in failed))
    return out
