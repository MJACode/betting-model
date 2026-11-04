"""The Picks screen's day read is drained past the 1,000-row response cap.

The All board shows every scored pick, BET, AVOID and NONE (Matt,
2026-11-04: "The all tab should have all picks"). One day's pre-game rows
pass the cap Supabase puts on every PostgREST response (lib/paging.ts):
1,432 on 2026-09-19, 1,355 of them NONE (measured 2026-11-04, Supabase, read
only). With `.limit(5000)` the read silently returned the first 1,000, so the
rest of that day's NONE rows never reached All. The NCAAB cards now write a
NONE row for every game they price and do not bet, which adds to that day.
"""
from __future__ import annotations

from tests.test_mobile_ncaab_in_app import QUERIES, _fn, _read


def test_the_days_picks_read_is_drained_on_a_total_order():
    body = _fn(_read(QUERIES), "fetchPicksForDate")
    start = body.index("Promise.all([")
    picks = body[start: body.index(".from('games')")]
    # Code only: the comment above the read may name the old `.limit(...)`.
    picks = "\n".join(l for l in picks.splitlines() if not l.strip().startswith("//"))
    assert "fetchAllPages<Pick>" in picks
    assert ".range(from, to)" in picks
    # Signals first (a cap could never cost a BET), then a unique key so range
    # paging neither repeats nor drops a row at a page seam.
    assert ".order('signal_type', { ascending: true })" in picks
    assert ".order('pick_id', { ascending: true })" in picks
    assert ".limit(" not in picks
