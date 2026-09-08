"""A SKIPPED health check is a check that did not run, and it must say so.

`golf_odds` sat SKIPPED on 59 consecutive runs -- every run it has ever had,
zero verdicts since 2026-07-04 -- and read exactly like the honest offseason
skips beside it. The operations rule that a check must never gate on the thing
it detects fixed the CIRCULAR gates; it says nothing about a gate that is simply
stuck, and nothing in the report told the two apart.

These pin the three parts of the fix: the streak is counted in calendar days off
a table no feed can silence, a stuck gate escalates past its own budget, and the
persist happens after EVERY check so no result is computed and then dropped.
"""
import tracking.system_health as sh

SKIPPED, STALE, OK = sh.SKIPPED, sh.STALE, sh.OK


class FakeConn:
    """Just enough to answer the streak query, or to fail on demand."""

    def __init__(self, rows=(), raise_on_execute=False):
        self.rows = list(rows)
        self.raise_on_execute = raise_on_execute
        self.rolled_back = False

    def execute(self, sql, params=()):
        if self.raise_on_execute:
            raise RuntimeError("catalog read failed")
        return self

    def fetchall(self):
        return self.rows

    def rollback(self):
        self.rolled_back = True


def _res(check, status=SKIPPED, detail="no games in window"):
    return {"check_name": check, "status": status, "severity": "WARN",
            "detail": detail, "latest_seen": None}


# ── counting the streak ──────────────────────────────────────────────────────

def test_streak_counts_calendar_days_from_the_last_non_skipped_run():
    """Days, not rows: a day the pipeline never ran leaves no row at all, and
    counting rows would under-report exactly the outage that stopped it."""
    conn = FakeConn([("wnba_game_log", "2026-09-02", "2026-07-04")])
    assert sh._skip_run_days(conn, "2026-09-08") == {"wnba_game_log": 6}


def test_a_check_never_seen_non_skipped_counts_its_whole_history():
    """golf_odds has produced zero verdicts, so its streak is every row it has."""
    conn = FakeConn([("golf_odds", None, "2026-07-04")])
    assert sh._skip_run_days(conn, "2026-09-08") == {"golf_odds": 67}


def test_the_streak_query_fails_open():
    """A broken streak query may only lose the annotation, never invent a
    failure -- and it must roll back, or it poisons every later statement."""
    conn = FakeConn(raise_on_execute=True)
    assert sh._skip_run_days(conn, "2026-09-08") == {}
    assert conn.rolled_back


def test_a_check_skipped_only_today_is_not_counted_as_a_streak():
    conn = FakeConn([("umpires", "2026-09-07", "2026-07-04")])
    assert sh._skip_run_days(conn, "2026-09-08") == {"umpires": 1}


# ── acting on it ─────────────────────────────────────────────────────────────

def test_a_stuck_gate_escalates_past_its_budget():
    """67 days against golf_odds' 30-day budget: report the GATE, not the feed."""
    results = [_res("golf_odds", detail="no golf tournament in window")]
    sh._apply_skip_budgets(results, {"golf_odds": 67})
    assert results[0]["status"] == STALE
    assert "67 days" in results[0]["detail"]
    assert "suspect the GATE" in results[0]["detail"]


def test_an_honest_offseason_skip_stays_skipped_but_shows_its_length():
    """NBA in September is genuinely dark; the report should say how long."""
    results = [_res("nba_game_log", detail="no NBA games scheduled in last 3 days")]
    sh._apply_skip_budgets(results, {"nba_game_log": 67})
    assert results[0]["status"] == SKIPPED
    assert "skipped 67 days running" in results[0]["detail"]


def test_the_wnba_world_cup_break_does_not_trip_the_budget():
    """The 2026 season pauses for the FIBA World Cup (Sept 4-13) and resumes
    Sept 17. That is a real calendar gap, not a stuck gate."""
    results = [_res("wnba_game_log"), _res("espn_wnba_api")]
    sh._apply_skip_budgets(results, {"wnba_game_log": 17, "espn_wnba_api": 17})
    assert [x["status"] for x in results] == [SKIPPED, SKIPPED]


def test_a_non_skipped_result_is_never_touched():
    results = [_res("odds_dk_lines", status=OK, detail="last snapshot 0.0h ago")]
    sh._apply_skip_budgets(results, {"odds_dk_lines": 400})
    assert results[0] == _res("odds_dk_lines", status=OK, detail="last snapshot 0.0h ago")


def test_applying_twice_does_not_double_annotate():
    """The persist path may call this more than once; the detail must not grow."""
    results = [_res("nba_game_log")]
    sh._apply_skip_budgets(results, {"nba_game_log": 67})
    once = results[0]["detail"]
    sh._apply_skip_budgets(results, {"nba_game_log": 67})
    assert results[0]["detail"] == once


def _source_outside_the_budget_table() -> str:
    """The module source with the SKIP_BUDGET_DAYS declaration cut out.

    A plain grep of the whole file cannot verify a budget key: the key is a
    string literal INSIDE that declaration, so the search always finds itself
    and a typo'd or renamed check passes. Cutting the declaration out is what
    makes the search mean "this name is used somewhere that reports a check".

    Names are matched against the source rather than against r.add call sites
    alone because two checks are reported from a loop over a tuple of names
    (wnba_game_log, nba_game_log), where the literal is not at the call site.
    """
    import io as _io
    text = _io.open(sh.__file__, encoding="utf-8").read()
    start = text.index("SKIP_BUDGET_DAYS: dict = {")
    end = text.index("}", start) + 1
    return text[:start] + text[end:]


def test_every_budgeted_check_is_a_real_check_name():
    """A budget for a check that no longer exists is a budget that never fires."""
    rest = _source_outside_the_budget_table()
    assert "SKIP_BUDGET_DAYS: dict = {" not in rest, "the declaration was not cut out"
    unknown = sorted(c for c in sh.SKIP_BUDGET_DAYS if f'"{c}"' not in rest)
    assert not unknown, f"budgets for checks that are never reported: {unknown}"


def test_the_default_budget_is_short_enough_to_surface_a_stuck_gate():
    """An unbudgeted check must not be able to sit dark for a season."""
    assert sh.DEFAULT_SKIP_BUDGET_DAYS <= 31


# ── the persist ordering ─────────────────────────────────────────────────────

def test_model_calibration_is_persisted():
    """It was computed, logged, and then dropped: the INSERT loop ran BEFORE the
    calibration block, so system_health_checks held zero model_calibration rows,
    ever, while the surfaces that read that table were told nothing."""
    import io
    text = io.open(sh.__file__, encoding="utf-8").read()
    insert_at = text.index("INSERT INTO system_health_checks")
    calibration_at = text.index('r.add("model_calibration"')
    assert calibration_at < insert_at, (
        "the persist loop must run after every check is added, or the ones "
        "added later are silently discarded"
    )


def test_the_persist_applies_the_skip_budgets_first():
    import io
    text = io.open(sh.__file__, encoding="utf-8").read()
    apply_at = text.index("_apply_skip_budgets(r.results")
    insert_at = text.index("INSERT INTO system_health_checks")
    assert apply_at < insert_at
