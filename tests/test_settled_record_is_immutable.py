"""A settled pick's membership in the published record is fixed when it is written.

WHY. On 2026-09-12 the 06:02 Discord recap published NCAAF all-time as 0-3 over
3 settled picks. The morning before it had published 27-25 over 52. Nothing was
deleted and no pick changed: both NCAAF live lanes were paused the previous
evening, `model_action_thresholds.paused` went TRUE at the 6am sync, and the
recap's query carried `AND t.paused = FALSE` — applied not to what the models
may bet NEXT, but to what they had ALREADY bet and settled. 55 settled bets
stopped counting overnight. Measured from results_snapshots:

    published 2026-09-11 06:02 ET (through 09-10)   NCAAF  27-25,  52 settled
    published 2026-09-12 06:02 ET (through 09-11)   NCAAF   0-3,    3 settled

The same query re-applies the CURRENT min_prob / min_edge / min_odds to settled
rows, so a threshold edit moved the published all-time figure too: -22 settled
on 09-09, -104 on 09-02, -13 on 09-03, -10 on 09-01 (each measured as that
morning's all-time minus the previous morning's plus that day's daily).

mike, 2026-09-12: "Pausing a model should not erase settled record unless I
explicitly say so ... If I didn't explicitly say to remove a settled record, and
I have in the past for some others, then you need to keep the record. I did not
say this explicitly for NCAA football. Do not do it unless I explicitly say so."

So a settled pick leaves the published record by exactly two routes, both of
which someone had to ask for: a VOID (result='NO_ACTION') or an entry in
config.RECORD_EXCLUSIONS. The model's PRESENT state is not one of them.

NOT IN SCOPE, deliberately: mv_scored_pick_outcomes and v_model_full_outcome_*.
Those are the threshold-sweep universe and MUST re-cut under today's numbers —
CLAUDE.md 7's EVALUATION RULE. Publishing and sweeping are different questions.
test_the_sweep_views_are_left_alone pins that distinction.

Each test below was watched failing against the pre-fix code: the two SQL tests
against the `t.paused = FALSE` recap query and the un-migrated views, and the
app test against passesActionFilter being used for settled rows.
"""
from __future__ import annotations

import re
from pathlib import Path

import config
from tracking.discord_notifier import _SETTLED_SQL

ROOT = Path(__file__).parent.parent
MIG = ROOT / "data" / "migrations" / "settled_record_survives_a_pause_2026_09_12.sql"


def _code(sql: str) -> str:
    """SQL minus its comment lines — so a rule stated in prose in a comment
    cannot make a test pass that the executable text would fail."""
    return "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))


# ── the Discord recap ────────────────────────────────────────────────────────

def test_the_recap_does_not_re_apply_the_paused_flag_to_settled_picks():
    """The bug itself. `paused` says what a model may bet NEXT."""
    assert "paused" not in _code(_SETTLED_SQL).lower()


def test_the_recap_does_not_re_cut_settled_picks_at_todays_thresholds():
    """A pick was written as a BET because it cleared the cut THAT DAY. Re-cutting
    it at today's numbers is the same bug wearing a different flag — it is what
    moved the published all-time figure by -104 on 09-02 and -22 on 09-09."""
    code = _code(_SETTLED_SQL).lower()
    for column in ("min_prob", "min_edge", "min_odds", "prob_only"):
        assert column not in code, f"{column} is still re-cutting settled picks"


def test_the_recap_still_counts_only_settled_bets():
    code = _code(_SETTLED_SQL)
    assert "p.signal_type = 'BET'" in code
    assert "'WIN', 'LOSS', 'PUSH'" in code.replace('"', "'")


def test_a_voided_pick_is_still_out_of_the_record():
    """VOID sets result='NO_ACTION' (scripts/void_picks.py), so the WIN/LOSS/PUSH
    filter is what removes it. That is the mechanism carrying every removal mike
    HAS asked for — the MLB phantom-game rows, the re-cut nfl_opener_spread
    picks — and it must not depend on the paused flag we just stopped trusting."""
    code = _code(_SETTLED_SQL)
    assert "NO_ACTION" not in code, "a VOID must drop out via result, not a special case"
    assert re.search(r"result\s+IN\s*\(\s*'WIN',\s*'LOSS',\s*'PUSH'\s*\)", code)


def test_the_recap_applies_the_explicit_exclusions():
    """Whatever is in RECORD_EXCLUSIONS reaches the published query."""
    code = _code(_SETTLED_SQL)
    for ex in config.RECORD_EXCLUSIONS:
        assert ex["model_id"] in code, f"{ex['model_id']} exclusion never reaches the recap"


def test_a_dedicated_live_lane_still_counts_and_a_pre_game_in_play_pick_does_not():
    assert r"is_live IS NOT TRUE OR p.model_id LIKE" in _code(_SETTLED_SQL)


# ── the two published views the app reads ────────────────────────────────────

def test_the_migration_exists_and_is_registered_with_the_worker_runner():
    """An unregistered view migration is reverted on the next pass — the exact
    failure documented in tests/test_live_record_start_views.py."""
    assert MIG.exists(), "the migration is missing"
    active = (ROOT / "data" / "view_migrations.py").read_text(encoding="utf-8")
    assert MIG.name in active


def test_it_runs_after_the_migration_that_currently_owns_those_views():
    active = (ROOT / "data" / "view_migrations.py").read_text(encoding="utf-8")
    assert (active.index(MIG.name)
            > active.index("live_record_start_views_2026_09_01.sql")), \
        "ordered before the migration that defines the views: it would be overwritten"


def _view_bodies() -> list[str]:
    """The definitions the migration EXECUTEs, without the guards around them.

    The guards legitimately mention `paused` and `min_prob` — they are how the
    migration detects an unfixed view — so a naive search over the whole file
    tests the wrong text."""
    bodies = re.findall(r"EXECUTE \$v\$(.*?)\$v\$",
                        _code(MIG.read_text(encoding="utf-8")), re.S)
    assert len(bodies) == 2, f"expected both views to be redefined, found {len(bodies)}"
    return bodies


def test_neither_published_view_re_filters_settled_picks_on_model_state():
    for body in _view_bodies():
        low = body.lower()
        for column in ("paused", "min_prob", "min_edge", "min_odds", "prob_only"):
            assert column not in low, f"{column} still re-filters the published record"
        assert "model_action_thresholds" not in low, \
            "the record still joins the live threshold table"


def test_both_views_are_redefined_by_name():
    code = _code(MIG.read_text(encoding="utf-8"))
    for view in ("v_public_track_record", "v_public_track_record_daily"):
        assert f"CREATE OR REPLACE VIEW public.{view} " in code


def test_both_published_views_keep_the_live_date_gate():
    """The 2026-09-01 start is matt's explicit window and survives this change."""
    code = _code(MIG.read_text(encoding="utf-8"))
    assert code.count(f"'{config.PAPER_TRADING_START}'") >= 2


def test_the_views_and_the_recap_select_the_same_population():
    """A surface with an extra gate loses rows silently (CLAUDE.md 1b)."""
    view_code = _code(MIG.read_text(encoding="utf-8"))
    recap = _code(_SETTLED_SQL)
    for clause in ("signal_type = 'BET'", "is_live IS NOT TRUE"):
        assert clause in view_code and clause in recap


def test_the_sweep_views_are_left_alone():
    """CLAUDE.md 7: a cut is swept over every scored pick at TODAY's numbers.
    Those views re-cut by design and this migration must not touch them."""
    code = _code(MIG.read_text(encoding="utf-8"))
    for view in ("mv_scored_pick_outcomes", "v_model_full_outcome_record",
                 "v_model_full_outcome_picks"):
        assert f"VIEW public.{view}" not in code and f"VIEW {view}" not in code


# ── the explicit-removal list itself ─────────────────────────────────────────

def test_every_explicit_exclusion_names_who_asked_for_it():
    """An unattributed exclusion puts a decision in somebody's mouth — which is
    how the 2026-09-11 NCAAF pause came to carry `Updated-By: mike`."""
    for ex in config.RECORD_EXCLUSIONS:
        assert ex.get("asked_by"), f"{ex['model_id']} exclusion has no requester"
        assert ex.get("reason")


def test_no_ncaaf_model_was_quietly_added_to_the_exclusions():
    """mike, 2026-09-12: "I did not say this explicitly for NCAA football." """
    assert not [e for e in config.RECORD_EXCLUSIONS
                if e["model_id"].startswith("ncaaf")]


def test_a_paused_model_is_not_an_excluded_model():
    """The whole point: these two sets are unrelated."""
    excluded = {e["model_id"] for e in config.RECORD_EXCLUSIONS if not e.get("before")}
    assert not (excluded & set(config.PAUSED_MODELS))


def test_the_exclusion_sql_is_a_conjunction_of_negations():
    sql = config.record_exclusion_sql("p")
    for ex in config.RECORD_EXCLUSIONS:
        assert ex["model_id"] in sql
    assert sql == "" or sql.lstrip().startswith("AND")


# ── the app, which must agree with both ──────────────────────────────────────

def test_the_app_has_a_record_filter_that_ignores_model_state():
    src = (ROOT / "mobile" / "src" / "lib" / "thresholds.ts").read_text(encoding="utf-8")
    assert "passesRecordFilter" in src, "the app has no settled-record filter"
    body = src[src.index("export function passesRecordFilter"):]
    body = body[:body.index("\n}")]
    for token in ("paused", "min_prob", "min_edge", "min_odds"):
        assert token not in body, f"passesRecordFilter still re-filters on {token}"


def test_the_app_record_screens_do_not_use_the_action_filter():
    """BuiltInModelDetailScreen shows a model's SETTLED record and CLV history;
    filtering those with passesActionFilter is the same bug in TypeScript."""
    src = (ROOT / "mobile" / "src" / "screens"
           / "BuiltInModelDetailScreen.tsx").read_text(encoding="utf-8")
    assert "passesRecordFilter" in src
    assert "passesActionFilter" not in src


def test_the_app_still_filters_todays_pickable_board_on_model_state():
    """Open picks are a different question: a paused model must not be offered
    as something to bet. passesActionFilter keeps the paused check."""
    src = (ROOT / "mobile" / "src" / "lib" / "thresholds.ts").read_text(encoding="utf-8")
    body = src[src.index("export function passesActionFilter"):]
    assert "paused" in body[:body.index("\n}")]
