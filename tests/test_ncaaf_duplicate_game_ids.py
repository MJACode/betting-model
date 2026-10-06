"""NCAAF ingest must not mint a second games row for a game that already exists.

Measured 2026-10-06 (clusters2026): 112 games had 2-3 rows, 117 extra rows.
59 are an ET date against the UTC date CFBD preloaded on 2026-08-29. A 10:30pm
ET kickoff is the next calendar day in UTC. 3 are home/away swapped at a
neutral site (Army/Navy, Kansas/Arizona State, Virginia/West Virginia).

These tests use those rows. They do not touch the database.
"""

from datetime import date, timedelta

import pytest
from loguru import logger

import data.ingestors.cfbd_ingestor as cf
import data.ingestors.odds_ingestor as oi
from data.ingestors.cfbd_ingestor import parse_games, retain_existing_cfbd_ids
from data.ingestors.odds_ingestor import resolve_ncaaf_game_id

# Memphis @ UNLV, commence 2026-08-30T02:19Z = 10:19pm ET on the 29th.
# The UTC twin is the CFBD preload; the ET id is what the odds ingestor mints.
MEMPHIS_UTC = "NCAAF_2026-08-30_memphis_unlv"
MEMPHIS_ET = "NCAAF_2026-08-29_memphis_unlv"
# Fresno State @ USC, 2026-09-05T01:00Z = 9:00pm ET on the 4th.
FRESNO_ET_DATE = "2026-09-04"
# Army @ Navy on the odds feed; CFBD has Navy @ Army. Same calendar day.
ARMY_NAVY_ODDS = "NCAAF_2026-12-12_army_navy"
ARMY_NAVY_CFBD = "NCAAF_2026-12-12_navy_army"


def _schools(monkeypatch):
    monkeypatch.setattr(cf, "_SCHOOL_CACHE", [
        {"school": "UNLV", "mascot": "Rebels", "alt": []},
        {"school": "Memphis", "mascot": "Tigers", "alt": []},
        {"school": "Army", "mascot": "Black Knights", "alt": []},
        {"school": "Navy", "mascot": "Midshipmen", "alt": []},
        {"school": "USC", "mascot": "Trojans", "alt": []},
        {"school": "Fresno State", "mascot": "Bulldogs", "alt": []},
    ])


def _event(home, away, commence):
    return {
        "id": "e1",
        "commence_time": commence,
        "home_team": home,
        "away_team": away,
        "bookmakers": [{
            "key": "draftkings",
            "markets": [{"key": "h2h", "last_update": commence, "outcomes": [
                {"name": home, "price": -150},
                {"name": away, "price": 130},
            ]}],
        }],
    }


def _row(game_id, game_date, home, away):
    return {"game_id": game_id, "game_date": game_date,
            "home_team": home, "away_team": away}


class _Conn:
    def __init__(self, rows, boom=False):
        self.rows = rows
        self.boom = boom
        self.sql = ""
        self.params = None

    def execute(self, sql, params=None):
        if self.boom:
            raise RuntimeError("no database")
        self.sql = sql
        self.params = params
        rows = self.rows

        class _Cur:
            def fetchall(_self):
                return rows

        return _Cur()


def _memphis_parsed():
    return parse_games([{
        "id": 99, "season": 2026, "week": 1,
        "startDate": "2026-08-30T02:19:00.000Z",
        "homeTeam": "UNLV", "awayTeam": "Memphis",
        "homeClassification": "fbs", "awayClassification": "fbs",
    }])


# ── both ingestors, one id ────────────────────────────────────────────────────

@pytest.mark.parametrize("commence", [
    "2026-08-30T02:19:00Z",   # measured Memphis @ UNLV, 10:19pm ET
    "2026-08-30T02:30:00Z",   # 10:30pm ET = next-day UTC
])
def test_late_kickoff_reuses_the_utc_row_both_ingestors_share(commence, monkeypatch):
    """The UTC row is the only one stored and it has team logs. CFBD keeps
    it; the odds path looks it up instead of minting the ET id."""
    _schools(monkeypatch)
    rows = _memphis_parsed()
    retain_existing_cfbd_ids(rows, {MEMPHIS_UTC})

    existing = [_row(MEMPHIS_UTC, "2026-08-30", "UNLV", "Memphis")]
    conn = _Conn([(MEMPHIS_UTC, date(2026, 8, 30), "UNLV", "Memphis")])
    reuse = oi._ncaaf_resolver(conn, "2026-08-29")
    games, odds = oi._process_events(
        [_event("UNLV Rebels", "Memphis Tigers", commence)],
        "NCAAF", "open", "2026-08-29T12:00:00-04:00",
        reuse_game_id=reuse,
    )
    assert rows[0]["game_id"] == MEMPHIS_UTC
    assert games[0]["game_id"] == MEMPHIS_UTC
    assert {o["game_id"] for o in odds} == {MEMPHIS_UTC}
    assert resolve_ncaaf_game_id(existing, "UNLV", "Memphis", "2026-08-29") == MEMPHIS_UTC
    # A game row is still emitted. NCAAF is not the NFL: this ingestor writes
    # the schedule when it has to, and the upsert does not overwrite a score.
    assert len(games) == 1


def test_a_fresh_late_kickoff_is_the_et_id_from_both_ingestors(monkeypatch):
    """Nothing stored. Both sides date the 10:19pm ET kick on the 29th."""
    _schools(monkeypatch)
    rows = _memphis_parsed()
    retain_existing_cfbd_ids(rows, set())
    games, odds = oi._process_events(
        [_event("UNLV Rebels", "Memphis Tigers", "2026-08-30T02:19:00Z")],
        "NCAAF", "open", "2026-08-29T12:00:00-04:00",
        reuse_game_id=lambda *_a: None,
    )
    assert rows[0]["game_id"] == MEMPHIS_ET
    assert rows[0]["game_date"] == "2026-08-29"
    assert games[0]["game_id"] == MEMPHIS_ET
    assert games[0]["game_date"] == "2026-08-29"
    assert {o["game_id"] for o in odds} == {MEMPHIS_ET}


def test_a_failed_lookup_returns_none_and_does_not_skip_the_sport():
    """Unlike the NFL resolver, a lookup we could not build is permission to
    mint, not to drop the slate."""
    assert oi._ncaaf_resolver(_Conn([], boom=True), "2026-09-01") is None


# ── swapped neutral site ──────────────────────────────────────────────────────

def test_swapped_home_away_at_a_neutral_site_matches_the_existing_row(monkeypatch):
    """Army/Navy 2026-12-12. Odds lists Army @ Navy. CFBD preloaded Navy @ Army.
    One row, the one that already exists."""
    _schools(monkeypatch)
    conn = _Conn([(ARMY_NAVY_CFBD, "2026-12-12", "Army", "Navy")])
    reuse = oi._ncaaf_resolver(conn, "2026-09-01")
    games, odds = oi._process_events(
        [_event("Navy Midshipmen", "Army Black Knights", "2026-12-12T20:00:00Z")],
        "NCAAF", "open", "2026-09-01T12:00:00-04:00",
        reuse_game_id=reuse,
    )
    assert games[0]["game_id"] == ARMY_NAVY_CFBD
    assert {o["game_id"] for o in odds} == {ARMY_NAVY_CFBD}
    # The load window from the day Army-Navy first appeared on the board
    # (2026-09-01) has to reach the kickoff. The NFL's +10 days does not.
    assert "NCAAF" in conn.sql
    assert conn.params[1] >= "2026-12-12"
    anchor = date(2026, 9, 1)
    assert conn.params == (
        (anchor - timedelta(days=oi._NCAAF_REUSE_LOOKBACK_DAYS)).isoformat(),
        (anchor + timedelta(days=oi._NCAAF_REUSE_LOOKAHEAD_DAYS)).isoformat(),
    )


def test_when_both_orientations_exist_the_exact_order_wins():
    """Both Army/Navy rows are already stored. The odds event matches
    army_navy exactly and navy_army swapped. Exact order wins, and the
    ambiguity is logged."""
    games = [
        _row(ARMY_NAVY_CFBD, "2026-12-12", "Army", "Navy"),
        _row(ARMY_NAVY_ODDS, "2026-12-12", "Navy", "Army"),
    ]
    seen = []
    sink = logger.add(lambda m: seen.append(m.record["message"]),
                      level="WARNING", format="{message}")
    try:
        chosen = resolve_ncaaf_game_id(games, "Navy", "Army", "2026-12-12")
    finally:
        logger.remove(sink)
    assert chosen == ARMY_NAVY_ODDS
    assert seen and ARMY_NAVY_CFBD in seen[0] and ARMY_NAVY_ODDS in seen[0]


def test_exact_orientation_beats_a_nearer_swapped_row():
    """Sort is (exact order, then nearest date). A swapped row on the ET
    date loses to an exact-order row one day away."""
    games = [
        _row(ARMY_NAVY_CFBD, "2026-12-12", "Army", "Navy"),
        _row("NCAAF_2026-12-11_army_navy", "2026-12-11", "Navy", "Army"),
    ]
    assert resolve_ncaaf_game_id(games, "Navy", "Army", "2026-12-12") == \
        "NCAAF_2026-12-11_army_navy"


# ── +/- 1 day window ──────────────────────────────────────────────────────────

def _fresno(game_date):
    return _row(f"NCAAF_{game_date}_fresno-state_usc", game_date, "USC", "Fresno State")


@pytest.mark.parametrize("game_date,expected", [
    ("2026-09-02", None),                                          # 2 days before
    ("2026-09-03", "NCAAF_2026-09-03_fresno-state_usc"),          # 1 day before
    ("2026-09-04", "NCAAF_2026-09-04_fresno-state_usc"),          # the ET date
    ("2026-09-05", "NCAAF_2026-09-05_fresno-state_usc"),          # the UTC twin
    ("2026-09-06", None),                                          # 2 days after
])
def test_match_window_is_one_day_either_side_of_the_et_date(game_date, expected):
    """Fresno State @ USC kicks 2026-09-05T01:00Z, which is 2026-09-04 in ET.
    The boundary is the day, not 'about a day'."""
    assert resolve_ncaaf_game_id(
        [_fresno(game_date)], "USC", "Fresno State", FRESNO_ET_DATE,
    ) == expected


def test_a_different_opponent_inside_the_window_does_not_match():
    ucla = _row("NCAAF_2026-09-04_ucla_california", "2026-09-04",
                "California", "UCLA")
    assert resolve_ncaaf_game_id(
        [ucla], "USC", "Fresno State", FRESNO_ET_DATE,
    ) is None


def test_two_exact_rows_prefer_the_nearest_date_and_log_it():
    """Both Memphis rows. ET kickoff date is the 29th. The 29th wins over
    the 30th, and the warning names both."""
    games = [
        _row(MEMPHIS_UTC, "2026-08-30", "UNLV", "Memphis"),
        _row(MEMPHIS_ET, "2026-08-29", "UNLV", "Memphis"),
    ]
    seen = []
    sink = logger.add(lambda m: seen.append(m.record["message"]),
                      level="WARNING", format="{message}")
    try:
        chosen = resolve_ncaaf_game_id(games, "UNLV", "Memphis", "2026-08-29")
    finally:
        logger.remove(sink)
    assert chosen == MEMPHIS_ET
    assert len(seen) == 1
    assert MEMPHIS_UTC in seen[0] and MEMPHIS_ET in seen[0]


def test_a_single_match_is_not_logged_as_ambiguous():
    seen = []
    sink = logger.add(lambda m: seen.append(m.record["message"]),
                      level="WARNING", format="{message}")
    try:
        chosen = resolve_ncaaf_game_id(
            [_row(MEMPHIS_UTC, "2026-08-30", "UNLV", "Memphis")],
            "UNLV", "Memphis", "2026-08-29",
        )
    finally:
        logger.remove(sink)
    assert chosen == MEMPHIS_UTC
    assert seen == []
