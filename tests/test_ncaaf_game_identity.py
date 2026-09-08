"""One games row per NCAAF matchup — the check, and why it is CRIT.

NCAAF game_ids are built from RESOLVED school names, and two feeds build them:
CFBD writes its canonical school, the odds ingestor writes whatever
`resolve_odds_api_school` makes of The Odds API's mascot-appended string. When
those disagree the same real game gets two rows, and they do not split evenly --
the odds-side row collects every odds snapshot and every pick, the CFBD-side row
collects the FINAL. Six live BETs sat unsettled on 2026-09-04/05 for exactly
that reason (session 253); nothing was lost, the halves were on different ids.

Worse, the resolver's longest-prefix rule could substitute a DIFFERENT school --
"Florida A&M" -> "Florida", "Alabama State" -> "Alabama", "Texas Southern" ->
"Texas" -- writing a row for a matchup that never happens, which then gets
scored. On 2026-09-08 `NCAAF_2026-09-10_florida_miami` carried four NONE rows
for a game nobody will play.

Both faults have one signature: more than one games row for a (date, home team).
"""
import sqlite3

import pytest

import tracking.system_health as sh


def _conn():
    c = sqlite3.connect(":memory:")
    c.execute("""CREATE TABLE games (game_id TEXT PRIMARY KEY, sport TEXT,
                 game_date TEXT, home_team TEXT, away_team TEXT)""")
    return c


def _add(c, gid, date, home, away):
    c.execute("INSERT INTO games VALUES (?,'NCAAF',?,?,?)", (gid, date, home, away))


def _run(c, run_date="2026-09-10"):
    """Just the identity block, against a sqlite fixture."""
    from datetime import datetime, timedelta
    d = datetime.strptime(run_date, "%Y-%m-%d")
    rows = c.execute(
        "SELECT game_date, home_team, COUNT(*) FROM games "
        "WHERE sport='NCAAF' AND game_date >= ? AND game_date <= ? "
        "GROUP BY game_date, home_team HAVING COUNT(*) > 1",
        (run_date, (d + timedelta(days=9)).strftime("%Y-%m-%d"))).fetchall()
    return rows


def test_a_split_matchup_is_detected():
    """The real 2026-09-10 case: two ids for Florida A&M @ Miami."""
    c = _conn()
    _add(c, "NCAAF_2026-09-10_florida-a-m_miami", "2026-09-10", "Miami", "Florida A&M")
    _add(c, "NCAAF_2026-09-10_florida-a-m-rattlers_miami", "2026-09-10", "Miami", "Florida A&M Rattlers")
    assert _run(c) == [("2026-09-10", "Miami", 2)]


def test_a_phantom_opponent_is_detected_too():
    """"Florida A&M" resolved to "Florida" writes a matchup nobody will play.

    Same signature as the split, deliberately: one query catches both, so the
    check cannot be defeated by a new flavour of mis-resolution.
    """
    c = _conn()
    _add(c, "NCAAF_2026-09-10_florida-a-m_miami", "2026-09-10", "Miami", "Florida A&M")
    _add(c, "NCAAF_2026-09-10_florida_miami", "2026-09-10", "Miami", "Florida")
    assert _run(c) == [("2026-09-10", "Miami", 2)]


def test_a_clean_slate_reports_nothing():
    c = _conn()
    _add(c, "NCAAF_2026-09-12_wofford_ole-miss", "2026-09-12", "Ole Miss", "Wofford")
    _add(c, "NCAAF_2026-09-12_grambling_tcu", "2026-09-12", "TCU", "Grambling")
    assert _run(c) == []


def test_a_real_doubleheader_is_not_a_duplicate():
    """Two different home teams on one date is normal, not a split."""
    c = _conn()
    _add(c, "NCAAF_2026-09-12_a_troy", "2026-09-12", "Troy", "A")
    _add(c, "NCAAF_2026-09-12_b_tcu", "2026-09-12", "TCU", "B")
    assert _run(c) == []


def test_history_is_out_of_scope():
    """A duplicate on a played game is history; one on Saturday's card splits
    this week's odds. The window starts at run_date deliberately."""
    c = _conn()
    _add(c, "NCAAF_2026-09-05_x_georgia", "2026-09-05", "Georgia", "X")
    _add(c, "NCAAF_2026-09-05_x-y_georgia", "2026-09-05", "Georgia", "X Y")
    assert _run(c) == []


def test_the_check_is_crit_and_ungated():
    """CRIT so the run goes red, and gated on nothing that can be broken by the
    same outage -- a dead feed must not be able to silence it."""
    src = sh.__file__
    import io
    text = io.open(src, encoding="utf-8").read()
    block = text[text.index('r.add("ncaaf_game_identity"'):]
    block = block[:block.index("except Exception")]
    assert '"CRIT"' in block
    body = text[text.index("# ── One games row per NCAAF matchup"):]
    body = body[:body.index('r.add("ncaaf_game_identity", OK')]
    assert "gate_ok" not in body, "this check must not be gated"


def test_it_is_registered_under_a_skip_budget_or_never_skips():
    """It has no gate, so it can never report SKIPPED -- and therefore needs no
    skip budget. Pinned so adding a gate without a budget is caught."""
    import io
    text = io.open(sh.__file__, encoding="utf-8").read()
    block = text[text.index("# ── One games row per NCAAF matchup"):]
    block = block[:block.index("\n        # ") if "\n        # " in block[10:] else len(block)]
    assert "SKIPPED" not in block
