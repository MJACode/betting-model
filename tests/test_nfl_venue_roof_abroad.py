"""A game abroad is judged by its venue's roof, not the home team's (2026-10-21).

WHY THIS FILE EXISTS (mike, 2026-10-20: "The repo/models should look ahead
schedules for all markets and sports and models")

nflverse fills a future game's `roof` from the HOME team's US stadium, the
same way it fills the stadium id. Production's 2026 rows on 2026-10-21: PIT @
NO at the Stade de France is 'dome' (the Superdome), NE @ DET at the Allianz
Arena is 'dome' (Ford Field). The wind model drops every dome game before it
forecasts, so once the schedule placed these games in Paris and Munich it
still never looked at the weather there. ESPN's venue record for every game
abroad from 2022 to 2026 says all of these venues are open air except the
Bernabeu (`venue.indoor`, scoreboard API, fetched 2026-10-21; the table below).

The roof is replaced at the wind card's read only. The stored value is left as
nflverse wrote it, because the NFL prop models read it as a feature.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

NFL_ROOT = Path(__file__).resolve().parents[1] / "nfl"


@pytest.fixture()
def nfl_path():
    sys.path.insert(0, str(NFL_ROOT))
    try:
        yield
    finally:
        sys.path.remove(str(NFL_ROOT))


@pytest.fixture()
def wind(nfl_path):
    from _nfl_models import load_nfl_model
    return load_nfl_model("wind_totals")


NOW = "2026-10-21T13:00:00Z"


def _row(gid, away, home, kick, *, location="Neutral", stadium_id=None,
         stadium=None, roof="outdoors"):
    return {"game_id": f"NFL_{gid}", "season": 2026, "home_team": home,
            "away_team": away, "commence_time": kick, "week": 7,
            "season_type": "REG", "roof": roof, "stadium_id": stadium_id,
            "stadium": stadium, "location": location}


# The two upcoming games the dome copy blocked, as production holds them on
# 2026-10-21 (roof from nfl_team_game_stats, venue as the nflverse ingest
# writes it).
PARIS = _row("2026_07_PIT_NO", "PIT", "NO", "2026-10-25T13:30:00+00:00",
             stadium_id="PAR00", stadium="Stade de France", roof="dome")
MUNICH = _row("2026_10_NE_DET", "NE", "DET", "2026-11-15T14:30:00+00:00",
              stadium_id="MUN01", stadium="FC Bayern Munich Stadium", roof="dome")


def _load(rows, now=NOW, hi=30.0):
    from data_ingest.schedule import load_schedule
    return load_schedule(0.0, hi, now=now, rows=rows).set_index("game_id")


def test_paris_and_munich_are_open_air_games(nfl_path):
    from data_ingest.weather import open_air_mask
    g = _load([PARIS, MUNICH])
    assert list(g.roof) == ["outdoors", "outdoors"]
    assert list(g.nflverse_roof) == ["dome", "dome"]
    assert open_air_mask(g.reset_index()).all()
    assert "roof outdoors (nflverse row: dome)" in g.loc["2026_07_PIT_NO", "venue_note"]


def test_the_stored_roof_is_not_what_changes(nfl_path):
    """The row handed in is the database row; the loader must not edit it.
    nfl_team_game_stats.roof is an NFL prop model feature."""
    row = dict(PARIS)
    _load([row])
    assert row["roof"] == "dome"


@pytest.mark.parametrize("raw,want", [
    (None, None), ("", None), ("dome", None), ("outdoors", None),
    ("closed", "closed"), ("open", "open"),
])
def test_the_bernabeu_counts_only_an_observed_roof_state(nfl_path, raw, want):
    """Retractable, and ESPN lists both Madrid games indoor. A copied home
    roof ('dome' from a dome team, 'outdoors' from an open-air one) is not a
    state; only 'open' or 'closed' is."""
    from data_ingest.weather import open_air_mask
    madrid = _row("2026_09_CIN_ATL", "CIN", "ATL", "2026-11-08T14:30:00+00:00",
                  stadium_id="MAD01", stadium="Bernabeu", roof=raw)
    g = _load([madrid])
    got = g.roof.iloc[0]
    assert (got if isinstance(got, str) else None) == want
    assert bool(open_air_mask(g.reset_index()).iloc[0]) == (want == "open")


def test_a_home_game_keeps_its_rows_roof(nfl_path):
    """Only a venue abroad is overridden. Detroit at home is a dome."""
    det = _row("2026_08_MIN_DET", "MIN", "DET", "2026-11-01T18:00:00+00:00",
               location="Home", stadium_id="DET00", stadium="Ford Field", roof="dome")
    gb = _row("2026_08_CAR_GB", "CAR", "GB", "2026-10-30T00:15:00+00:00",
              location="Home", stadium_id="GNB00", stadium="Lambeau Field",
              roof="outdoors")
    g = _load([det, gb])
    assert g.loc["2026_08_MIN_DET", "roof"] == "dome"
    assert g.loc["2026_08_CAR_GB", "roof"] == "outdoors"
    assert "roof" not in g.loc["2026_08_CAR_GB", "venue_note"]


# Every NFL game abroad 2022-2026 with ESPN's venue.indoor for it (scoreboard
# API, site.api.espn.com, fetched by hand 2026-10-21), and the venue id the
# name resolves to.
ESPN_ABROAD = [
    ("2022-11-13", "Allianz Arena", False),
    ("2023-11-05", "Deutsche Bank Park", False),       # ESPN: "Frankfurt Stadium"
    ("2023-11-12", "Deutsche Bank Park", False),
    ("2024-09-07", "Arena Corinthians", False),
    ("2024-10-06", "Tottenham Hotspur Stadium", False),
    ("2024-10-13", "Tottenham Hotspur Stadium", False),
    ("2024-11-10", "Allianz Arena", False),
    ("2025-09-28", "Croke Park", False),
    ("2025-10-05", "Tottenham Hotspur Stadium", False),
    ("2025-10-12", "Tottenham Hotspur Stadium", False),
    ("2025-10-19", "Wembley Stadium", False),
    ("2025-11-09", "Olympiastadion", False),
    ("2025-11-16", "Bernabeu", True),
    ("2026-09-11", "Melbourne Cricket Ground", False),
    ("2026-09-27", "Maracana Stadium", False),
    ("2026-10-04", "Tottenham Hotspur Stadium", False),
    ("2026-10-11", "Tottenham Hotspur Stadium", False),
    ("2026-10-18", "Wembley Stadium", False),
    ("2026-10-25", "Stade de France", False),
    ("2026-11-08", "Bernabeu", True),
    ("2026-11-15", "FC Bayern Munich Stadium", False),
    ("2026-11-23", "Estadio Banorte", False),
]


@pytest.mark.parametrize("day,name,indoor", ESPN_ABROAD,
                         ids=[f"{d}-{n}" for d, n, _ in ESPN_ABROAD])
def test_every_venue_abroad_matches_espns_indoor_flag(nfl_path, day, name, indoor):
    from data_ingest.weather import RETRACTABLE_STADIUMS, resolve_venue, venue_roof
    sid, note = resolve_venue("XXX00", name, "Neutral")
    assert sid is not None, note
    if indoor:
        assert sid in RETRACTABLE_STADIUMS and venue_roof(sid, "dome") is None
    else:
        assert venue_roof(sid, "dome") == "outdoors", (sid, name)


def test_every_venue_the_name_table_can_reach_has_a_roof_entry(nfl_path):
    """A venue abroad with no entry would fall back to the home team's roof."""
    from data_ingest.weather import (NEUTRAL_VENUE_NAMES, RETRACTABLE_ABROAD,
                                     STADIUM_COORDS, VENUE_ROOF_ABROAD)
    assert set(NEUTRAL_VENUE_NAMES.values()) <= set(VENUE_ROOF_ABROAD)
    assert set(VENUE_ROOF_ABROAD) <= set(STADIUM_COORDS)
    assert {s for s, r in VENUE_ROOF_ABROAD.items() if r is None} == RETRACTABLE_ABROAD


# ── Through the model ────────────────────────────────────────────────────────

def _priced(g, mph=14.0):
    """Attach a windy forecast and a -105/-105 under at 42 (clears MIN_EDGE)."""
    g = g.reset_index().copy()
    g["forecast_wind"] = mph
    g["exp_true_wind"] = mph - 1.0
    g["best_book"], g["best_total"] = "draftkings", 42.0
    g["best_under_px"], g["best_over_px"] = -105, -105
    return g


def _paris_in_two_days():
    """The Paris row, kicking off two days from the real clock: the model
    measures lead against it, and this is inside its four-day window."""
    kick = (pd.Timestamp.now(tz="UTC").floor("min") + pd.Timedelta(days=2)).isoformat()
    return _load([dict(PARIS, commence_time=kick)], now=None)


def _reads(gid, mph=14.0):
    """A covered 12-hour window of readings stored under the game."""
    now = pd.Timestamp.now(tz="UTC")
    return {gid: [(now - pd.Timedelta(hours=h), mph) for h in (12, 8, 4, 0)]}


def test_a_windy_paris_game_inside_the_window_is_bet(wind):
    """Before: dropped as a dome, whatever the weather in Saint-Denis."""
    g = _priced(_paris_in_two_days())
    bets = wind.select_bets(g, wind_reads=_reads("2026_07_PIT_NO"))
    assert list(bets.game_id) == ["2026_07_PIT_NO"]


def test_the_board_no_longer_calls_paris_indoor(wind):
    g = _priced(_paris_in_two_days())
    row = wind.evaluate_board(g, wind_reads=_reads("2026_07_PIT_NO"))[0]
    assert row["reason"] != "indoor"
    assert int(row["qualifies"]), row["reason"]
