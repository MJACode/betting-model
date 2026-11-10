"""The Picks screen's day read is drained past the 1,000-row response cap.

The All board shows every scored pick, BET, AVOID and NONE (Matt,
2026-11-04: "The all tab should have all picks"). One day's pre-game rows
pass the cap Supabase puts on every PostgREST response (lib/paging.ts):
1,432 on 2026-09-19, 1,355 of them NONE (measured 2026-11-04, Supabase, read
only). With `.limit(5000)` the read silently returned the first 1,000, so the
rest of that day's NONE rows never reached All. The NCAAB cards now write a
NONE row for every game they price and do not bet, which adds to that day.

The read is two (UX review, 2026-11-04): the signals, which must load, and the
NONE rows, which are enrichment, so a timeout on a late NONE page reports a
partial board instead of blanking Signals.
"""
from __future__ import annotations

from tests.test_mobile_ncaab_in_app import QUERIES, _fn, _read


def _code(body: str) -> str:
    """Code only: comments may name the old `.limit(...)`."""
    return "\n".join(l for l in body.splitlines() if not l.strip().startswith("//"))


def test_the_days_picks_are_two_drained_reads_signals_required_none_enrichment():
    body = _code(_fn(_read(QUERIES), "fetchPicksForDate"))
    picks = body[body.index("const picksPage"): body.index(".from('games')")]
    assert ".limit(" not in picks
    assert ".range(from, to)" in picks
    # BET/AVOID first, then a unique key so range paging neither repeats nor
    # drops a row at a page seam.
    assert ".order('signal_type', { ascending: true })" in picks
    assert ".order('pick_id', { ascending: true })" in picks
    assert "q.eq('signal_type', 'NONE')" in picks and "q.neq('signal_type', 'NONE')" in picks
    assert picks.count("fetchAllPages<Pick>(picksPage(") == 2
    # A failed signals read fails the board; a failed NONE read is reported.
    assert "if (picksRes.error) throw picksRes.error;" in body
    assert "onEnrichmentError?.('the rest of today’s scored picks', noneRes.error)" in body
    # The line shop is built from the signals alone (it does not wait for NONE).
    assert body.index("const rawPicks = (picksRes.data") < body.index("const noneRes = await nonePicksRes")
    assert "const picks = [...rawPicks, ...((noneRes.data ?? []) as Pick[])];" in body


def test_the_ncaab_look_ahead_reads_lines_only_for_signal_games_and_reports_failures():
    # The read is shared with the women's sport from 2026-11-10: the men's
    # fetch passes 'NCAAB', and a failed line read names the sport it was for.
    body = _code(_fn(_read(QUERIES), "fetchUpcomingCollegeBasketballPicks"))
    assert "fetchUpcomingCollegeBasketballPicks('NCAAB'," in _fn(_read(QUERIES), "fetchUpcomingNcaabPicks")
    assert "picks.filter((p) => p.signal_type !== 'NONE')" in body
    assert body.count("eachChunk(lineGameIds,") == 2
    assert "eachChunk(gameIds," in body
    assert "onEnrichmentError?.(`the upcoming ${sport} lines`, e)" in body
    assert "onEnrichmentError?.(`the upcoming ${sport} line shop`, e)" in body
    assert ".catch(() =>" not in body
