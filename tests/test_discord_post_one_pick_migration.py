"""The 2026-10-14 Discord-lock extras are named, and only those rows move.

Measured read-only that day: 34 posts (23 discord_live, 11 discord_signal)
have more than one picks row on the exact publish lock, 35 extras. None of
the extras is a graded WIN, LOSS or PUSH. The kept row is the BET the
publisher would post (earliest BET, then created_at, then pick_id).
"""
from __future__ import annotations

import re
from pathlib import Path

MIG = (Path(__file__).parent.parent
       / "data/migrations/discord_post_one_pick_2026_10_14.sql")
CODE = MIG.read_text(encoding="utf-8")

# mark_id, kept_id. The kept ids include graded bets; the mark ids must not.
PAIRS = {
    2131279: 2131569, 2131460: 2131570, 2478678: 2476480,
    2558040: 2559202, 2558709: 2559049, 2559044: 2559045,
    2559046: 2559047, 2559145: 2559211, 2559326: 2559327,
    2559340: 2559341, 2562773: 2562774, 2562775: 2562776,
    2562833: 2562834, 2563081: 2563082, 2563083: 2563084,
    2563085: 2563086, 2563894: 2563895, 2565688: 2567487,
    2567188: 2567189, 2577062: 2577063, 2626444: 2628978,
    2838267: 2838310, 3208387: 3208455, 1387924: 1387923,
    1391561: 1391560, 1404777: 1404778, 1404793: 1404792,
    1410045: 1410044, 1410056: 1410057, 1410071: 1410070,
    1631577: 1584585, 1631579: 1603849, 2068718: 2068714,
    3585550: 3585552, 3585551: 3585552,
}

# Graded copies that must stay the kept row.
KEPT_GRADED = {2068714, 2131569, 2559202, 1387923, 3585552}


def _pairs() -> list[tuple[int, int, str, str]]:
    return [(int(a), int(b), model, game) for a, b, model, game in re.findall(
        r"\((\d+)::bigint, (\d+)::bigint, '([^']+)', '([^']+)'\)", CODE)]


def test_migration_is_registered_and_one_statement():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS
    assert CODE.count("$mig$") == 2
    assert CODE.split("$mig$")[-1].strip() == ";"


def test_it_names_each_measured_extra_and_the_row_kept():
    found = {mark: kept for mark, kept, _model, _game in _pairs()}
    assert found == PAIRS
    assert len(found) == 35
    assert 2068718 in found and found[2068718] == 2068714
    assert 2478678 in found and found[2478678] == 2476480
    assert found[3585550] == 3585552 and found[3585551] == 3585552
    for kept in KEPT_GRADED:
        assert kept not in found


def test_the_update_does_not_rewrite_the_graded_outcome():
    """Result, profit, line, price and created_at are not assigned."""
    body = CODE.split("UPDATE public.picks", 1)[1]
    assignment = body.split("FROM", 1)[0]
    for column in ("result ", "profit_flat", "profit_kelly", "scored_line",
                   "dk_odds", "decision_odds", "created_at", "settled_at"):
        assert column not in assignment
    assert "condition_status = 'DUPLICATE'" in assignment
    assert "IS DISTINCT FROM 'DUPLICATE'" in CODE
    assert "x.result IS NULL OR x.result = 'NO_ACTION'" in CODE
    assert "SET result" not in CODE.lower()


def test_a_second_standing_bet_and_a_second_live_row_are_blocked():
    assert "CREATE UNIQUE INDEX uq_picks_one_bet_per_publish_lock" in CODE
    assert "CREATE UNIQUE INDEX uq_picks_one_live_row" in CODE
    assert "signal_type = 'BET'" in CODE
    assert "condition_status IS DISTINCT FROM 'VOID'" in CODE
    assert "result IS DISTINCT FROM 'NO_ACTION'" in CODE
    assert "is_live IS TRUE" in CODE
    assert "RAISE NOTICE" in CODE
    assert "RAISE EXCEPTION" not in CODE
    # A duplicate left behind skips the create; it must not abort the marks.
    assert CODE.index("UPDATE public.picks") < CODE.index(
        "CREATE UNIQUE INDEX uq_picks_one_bet_per_publish_lock")
    assert "is_live IS NOT TRUE" not in CODE.split(
        "uq_picks_one_live_row", 1)[1].split("CREATE UNIQUE INDEX", 1)[0]
