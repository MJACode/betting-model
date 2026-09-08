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


def _conn(fbs=("Miami", "Troy", "Ole Miss", "TCU", "Georgia", "UTEP")):
    c = sqlite3.connect(":memory:")
    c.execute("""CREATE TABLE games (game_id TEXT PRIMARY KEY, sport TEXT,
                 game_date TEXT, home_team TEXT, away_team TEXT)""")
    c.execute("CREATE TABLE ncaaf_teams (school TEXT, classification TEXT)")
    for s in fbs:
        c.execute("INSERT INTO ncaaf_teams VALUES (?, 'fbs')", (s,))
    return c


def _add(c, gid, date, home, away):
    c.execute("INSERT INTO games VALUES (?,'NCAAF',?,?,?)", (gid, date, home, away))


def _identity_sql() -> str:
    """The check's ACTUAL query, lifted from the module.

    Reimplementing it here would be the §7 trap in its purest form: the test
    would pass while the code it guards was mutated out from under it. Both
    mutations (dropping the FBS bound, unbounding the window) went UNCAUGHT
    against a hand-copied query before this was changed to read the real one.

    The query uses `?` placeholders throughout, which is what makes it runnable
    against a sqlite fixture unaltered.
    """
    import io as _io
    text = _io.open(sh.__file__, encoding="utf-8").read()
    start = text.index("# ── One games row per NCAAF matchup")
    body = text[start:]
    sql = body[body.index('conn.execute("""') + len('conn.execute("""'):]
    return sql[:sql.index('""",')]


def _run(c, run_date="2026-09-10"):
    """Run the real query against the fixture."""
    from datetime import datetime, timedelta
    d = datetime.strptime(run_date, "%Y-%m-%d")
    end = (d + timedelta(days=9)).strftime("%Y-%m-%d")
    return c.execute(_identity_sql(), (run_date, end)).fetchall()


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


def test_a_non_fbs_fixture_is_not_reported():
    """The registry carries 683 schools across every classification, and the
    models score FBS. Bluffton's "Madonna" vs "Madonna University (Mich.)"
    survived the 2026-09-08 cleanup precisely because NEITHER name is in the
    registry -- there is no canonical id to merge onto, and nothing prices the
    game. Reporting it forever is the noise this exercise was about.
    """
    c = _conn()                                   # Bluffton is not in the fbs set
    _add(c, "NCAAF_2026-09-12_madonna_bluffton", "2026-09-12", "Bluffton", "Madonna")
    _add(c, "NCAAF_2026-09-12_madonna-u_bluffton", "2026-09-12", "Bluffton", "Madonna University (Mich.)")
    assert _run(c, "2026-09-08") == []


def test_an_fbs_split_is_still_reported_after_the_bound():
    """The bound must not swallow the cases it exists for."""
    c = _conn()
    _add(c, "NCAAF_2026-09-10_florida-a-m_miami", "2026-09-10", "Miami", "Florida A&M")
    _add(c, "NCAAF_2026-09-10_florida_miami", "2026-09-10", "Miami", "Florida")
    assert _run(c, "2026-09-08") == [("2026-09-10", "Miami", 2)]


# ── the resolver overrides that keep a matchup on one id ─────────────────────

def test_the_odds_api_map_bridges_names_no_rule_can():
    """Every entry here exists because a fold, a "school mascot" match and a
    longest-prefix all fail — the two sources use genuinely different names.

    "Southern Mississippi Golden Eagles" vs CFBD's "Southern Miss" was caught by
    ncaaf_game_identity on its first live run (2026-09-08): the resolver fell
    through to identity and wrote a second games row for Auburn's 09-12 game,
    splitting its odds from the id that will receive the final.
    """
    import config
    m = config.NCAAF_ODDS_API_MAP
    assert m.get("Southern Mississippi Golden Eagles") == "Southern Miss"
    assert m.get("Appalachian State Mountaineers") == "App State"
    assert m.get("UMass Minutemen") == "Massachusetts"


def test_every_override_target_is_a_canonical_school_shape():
    """A target that is itself a mascot-appended string would just move the
    split rather than close it."""
    import config
    for src, dst in config.NCAAF_ODDS_API_MAP.items():
        assert dst, f"{src!r} maps to an empty name"
        assert dst != src, f"{src!r} maps to itself"
        assert len(dst.split()) <= 4, (
            f"{src!r} -> {dst!r} looks like it still carries a mascot")
