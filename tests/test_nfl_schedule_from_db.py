"""NFL pre-game jobs read the schedule from the games table, not a frozen file.

WHY THIS FILE EXISTS

Until 2026-10-20 the wind card, the opener card, the DraftKings line dump and
the scheduler's NFL clock all read nfl/data/games.csv, committed once
(4ffdada1, 2026-08-15) and never refreshed. Measured that day:

  * no 2026 playoff game in it, so every NFL pre-game job would have found
    nothing ahead after week 18 (2027-01-10) and stood down;
  * CHI @ GB at 16:25 ET. Wind BET 3365283 carries that 20:25Z kickoff; the
    game kicked off at 17:00Z (games.commence_time, and ESPN);
  * the home team's US stadium for all nine 2026 games abroad, so wind BETs
    3465055 (PHI @ JAX, Tottenham) and 3583736 (HOU @ JAX, Wembley) were
    forecast at Jacksonville's coordinates.

Each test below fails on the code that read the file: the card and clock tests
put a stale file in the working directory and a correct database row beside
it, and assert the database won.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
NFL_ROOT = REPO / "nfl"
sys.path.insert(0, str(REPO))


@pytest.fixture()
def nfl_path():
    sys.path.insert(0, str(NFL_ROOT))
    try:
        yield
    finally:
        sys.path.remove(str(NFL_ROOT))


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(
        f"_nfl_sched_script_{name}", NFL_ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _row(gid, away, home, kick, *, location="Home", stadium_id=None, stadium=None,
         roof="outdoors", week=5):
    """One NFL games row joined to its home-team nfl_team_game_stats row."""
    kick = kick if isinstance(kick, str) else kick.isoformat()
    return {"game_id": f"NFL_{gid}", "season": 2026, "home_team": home,
            "away_team": away, "commence_time": kick, "week": week,
            "season_type": "REG", "roof": roof, "stadium_id": stadium_id,
            "stadium": stadium, "location": location}


def _feed(monkeypatch, rows):
    from data_ingest import schedule
    monkeypatch.setattr(schedule, "fetch_rows", lambda lo, hi: rows)


def _stale_file(tmp_path, rows):
    """A data/games.csv in nflverse's columns, as the frozen copy had them."""
    d = tmp_path / "data"
    d.mkdir(parents=True, exist_ok=True)
    head = "game_id,season,week,gameday,gametime,away_team,home_team,location,roof,stadium_id,stadium\n"
    (d / "games.csv").write_text(head + "".join(r + "\n" for r in rows), encoding="utf-8")


def _et(ts: datetime) -> tuple[str, str]:
    from zoneinfo import ZoneInfo
    k = ts.astimezone(ZoneInfo("America/New_York"))
    return f"{k:%Y-%m-%d}", f"{k:%H:%M}"


# ── The three affected wind BETs, read back through the new path ─────────────

# The games rows as production holds them, with the venue the nflverse ingest
# now stores (live nflverse games.csv, 2026-10-20).
AFFECTED = [
    # pick 3365283 "CHI @ GB Under 46": game_time 20:25Z on the pick
    _row("2026_05_CHI_GB", "CHI", "GB", "2026-10-11T17:00:00+00:00",
         stadium_id="GNB00", stadium="Lambeau Field"),
    # pick 3465055 "PHI @ JAX Under 42": Neutral, but nflverse still says JAX00
    _row("2026_05_PHI_JAX", "PHI", "JAX", "2026-10-11T13:30:00+00:00",
         location="Neutral", stadium_id="JAX00", stadium="Tottenham Hotspur Stadium"),
    # pick 3583736 "HOU @ JAX Under 42.5"
    _row("2026_06_HOU_JAX", "HOU", "JAX", "2026-10-18T13:30:00+00:00",
         location="Neutral", stadium_id="LON00", stadium="Wembley Stadium", week=6),
]


def test_the_three_affected_picks_read_back_with_the_right_kickoff_and_venue(nfl_path):
    from data_ingest.schedule import load_schedule
    from data_ingest.weather import STADIUM_COORDS
    g = load_schedule(0.0, 12.0, now="2026-10-07T00:00:00Z", rows=AFFECTED).set_index("game_id")

    assert g.loc["2026_05_CHI_GB", "kick_utc"] == pd.Timestamp("2026-10-11T17:00Z")
    assert g.loc["2026_05_CHI_GB", "stadium_id"] == "GNB00"

    assert g.loc["2026_05_PHI_JAX", "stadium_id"] == "LON02"      # Tottenham
    assert g.loc["2026_05_PHI_JAX", "nflverse_stadium_id"] == "JAX00"
    assert g.loc["2026_06_HOU_JAX", "stadium_id"] == "LON00"      # Wembley
    for gid in ("2026_05_PHI_JAX", "2026_06_HOU_JAX"):
        lat, lon = STADIUM_COORDS[g.loc[gid, "stadium_id"]]
        assert 51.4 < lat < 51.7 and -0.4 < lon < 0.0, (gid, lat, lon)   # London
    assert g.loc["2026_05_PHI_JAX", "matchup"] == "PHI @ JAX"


def test_the_frozen_files_venue_shapes_also_resolve_to_london(nfl_path):
    """The file had PHI @ JAX as 'Home' at JAX00 and HOU @ JAX at JAX00."""
    from data_ingest.weather import resolve_venue
    assert resolve_venue("JAX00", "Tottenham Hotspur Stadium", "Home")[0] == "LON02"
    assert resolve_venue("JAX00", "Wembley Stadium", "Neutral")[0] == "LON00"


# ── Venue resolution ─────────────────────────────────────────────────────────

# Every 2026 game abroad as nflverse publishes it on 2026-10-20, with ESPN's
# venue for the same game (site.api.espn.com scoreboard, fetched by hand the
# same day). The resolved venue must be ESPN's on every row.
ABROAD_2026 = [
    # (game, nflverse location, stadium_id, stadium) -> (resolved, ESPN venue)
    (("2026_01_SF_LA", "Neutral", "MEL00", "Melbourne Cricket Ground"), ("MEL00", "Melbourne Cricket Ground")),
    (("2026_03_BAL_DAL", "Neutral", "RIO00", "Maracana Stadium"), ("RIO00", "Maracanã Stadium")),
    (("2026_04_IND_WAS", "Neutral", "LON02", "Tottenham Hotspur Stadium"), ("LON02", "Tottenham Hotspur Stadium")),
    (("2026_05_PHI_JAX", "Neutral", "JAX00", "Tottenham Hotspur Stadium"), ("LON02", "Tottenham Hotspur Stadium")),
    (("2026_06_HOU_JAX", "Neutral", "LON00", "Wembley Stadium"), ("LON00", "Wembley Stadium")),
    (("2026_07_PIT_NO", "Neutral", "PAR00", "Stade de France"), ("PAR00", "Stade de France")),
    (("2026_09_CIN_ATL", "Neutral", "MAD01", "Bernabeu"), ("MAD01", "Santiago Bernabéu")),
    (("2026_10_NE_DET", "Neutral", "MUN01", "FC Bayern Munich Stadium"), ("MUN01", "FC Bayern Munich Stadium")),
    (("2026_11_MIN_SF", "Neutral", "MEX00", "Estadio Banorte"), ("MEX00", "Estadio Banorte")),
]


@pytest.mark.parametrize("src,want", ABROAD_2026, ids=[s[0] for s, _ in ABROAD_2026])
def test_every_2026_game_abroad_resolves_to_espns_venue(nfl_path, src, want):
    from data_ingest.weather import resolve_venue, STADIUM_COORDS
    _, loc, sid, name = src
    got, note = resolve_venue(sid, name, loc)
    assert got == want[0], note
    assert got in STADIUM_COORDS


def test_the_2025_pattern_home_teams_own_stadium_on_a_game_abroad_is_refused(nfl_path):
    """nflverse's 2025 rows: Dublin is 'Neutral, PIT00, Acrisure Stadium'.

    Both fields name Pittsburgh. A resolver that trusted either would forecast
    a game in Ireland at Pittsburgh's stadium.
    """
    from data_ingest.weather import resolve_venue
    got, note = resolve_venue("PIT00", "Acrisure Stadium", "Neutral")
    assert got is None and "not in the venue table" in note


def test_a_neutral_us_site_is_not_forecast(nfl_path):
    """A Super Bowl or relocated game: no US name may enter the venue table."""
    from data_ingest.weather import resolve_venue
    assert resolve_venue("SFO01", "Levi's Stadium", "Neutral")[0] is None


def test_a_home_game_uses_its_stadium_id(nfl_path):
    from data_ingest.weather import resolve_venue
    assert resolve_venue("GNB00", "Lambeau Field", "Home") == ("GNB00", "")


def test_a_row_without_venue_is_not_established(nfl_path):
    """The state of every row between the deploy and the first nflverse ingest."""
    from data_ingest.weather import resolve_venue
    got, note = resolve_venue(None, None, None)
    assert got is None and "no venue" in note


def test_an_unmapped_home_stadium_is_not_established(nfl_path):
    from data_ingest.weather import resolve_venue
    got, note = resolve_venue("NEW99", "Brand New Stadium", "Home")
    assert got is None and "no coordinates" in note


def test_the_venue_table_holds_only_venues_outside_the_us(nfl_path):
    """Structural guard for the rule in the NEUTRAL_VENUE_NAMES comment."""
    from data_ingest.weather import NEUTRAL_VENUE_NAMES, STADIUM_COORDS
    for name, sid in NEUTRAL_VENUE_NAMES.items():
        lat, lon = STADIUM_COORDS[sid]
        in_us = 24.0 < lat < 50.0 and -125.0 < lon < -66.0
        assert not in_us, f"{name} -> {sid} at ({lat}, {lon}) is inside the US"


def test_names_are_matched_without_accents_or_case(nfl_path):
    from data_ingest.weather import resolve_venue
    assert resolve_venue(None, "Maracanã Stadium", "Neutral")[0] == "RIO00"
    assert resolve_venue(None, "SANTIAGO BERNABÉU", "Neutral")[0] == "MAD01"


# ── The readers: the database row wins over a stale file beside it ──────────

def test_the_wind_card_reads_the_kickoff_from_the_games_table(
        nfl_path, tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    real = (now + timedelta(days=3)).replace(minute=0, second=0, microsecond=0)
    stale = real + timedelta(hours=3, minutes=25)      # the CHI @ GB error
    day, tod = _et(stale)
    _stale_file(tmp_path, [f"2026_05_CHI_GB,2026,5,{day},{tod},CHI,GB,Home,outdoors,GNB00,Lambeau Field"])
    monkeypatch.chdir(tmp_path)
    card = _load_script("weekly_wind_card")
    _feed(monkeypatch, [_row("2026_05_CHI_GB", "CHI", "GB", real,
                             stadium_id="GNB00", stadium="Lambeau Field")])

    g = card.load_schedule(10)
    assert list(g.game_id) == ["2026_05_CHI_GB"]
    assert g.kick_utc.iloc[0] == pd.Timestamp(real)
    assert g.stadium_id.iloc[0] == "GNB00"


def test_the_wind_card_reads_the_venue_from_the_games_table(
        nfl_path, tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    kick = (now + timedelta(days=2)).replace(minute=30, second=0, microsecond=0)
    day, tod = _et(kick)
    _stale_file(tmp_path, [f"2026_05_PHI_JAX,2026,5,{day},{tod},PHI,JAX,Home,outdoors,JAX00,Tottenham Hotspur Stadium"])
    monkeypatch.chdir(tmp_path)
    card = _load_script("weekly_wind_card")
    _feed(monkeypatch, [_row("2026_05_PHI_JAX", "PHI", "JAX", kick, location="Neutral",
                             stadium_id="JAX00", stadium="Tottenham Hotspur Stadium")])
    assert card.load_schedule(10).stadium_id.iloc[0] == "LON02"


def test_the_opener_card_reads_the_games_table(nfl_path, tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    real = (now + timedelta(days=4)).replace(minute=0, second=0, microsecond=0)
    day, tod = _et(real + timedelta(days=4))            # the file puts it out of window
    _stale_file(tmp_path, [f"2026_03_TEN_NYG,2026,3,{day},{tod},TEN,NYG,Home,outdoors,NYC01,MetLife Stadium"])
    monkeypatch.chdir(tmp_path)
    card = _load_script("daily_opener_card")
    _feed(monkeypatch, [_row("2026_03_TEN_NYG", "TEN", "NYG", real)])
    g = card.load_window_schedule(0.0, 7.0)
    assert list(g.game_id) == ["2026_03_TEN_NYG"]
    assert g.kick_utc.iloc[0] == pd.Timestamp(real)


def test_the_line_dump_reads_the_games_table(nfl_path, tmp_path, monkeypatch):
    from data_ingest import line_snapshots
    now = datetime.now(timezone.utc)
    real = (now + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)
    _stale_file(tmp_path, [])
    monkeypatch.chdir(tmp_path)
    _feed(monkeypatch, [_row("2026_07_KC_SEA", "KC", "SEA", real)])
    got = line_snapshots.snapshot_schedule(8.0)
    assert [r["game_id"] for r in got] == ["2026_07_KC_SEA"]
    assert pd.Timestamp(got[0]["kick_utc"]) == pd.Timestamp(real)


def test_no_database_means_no_games_never_the_file(nfl_path, tmp_path, monkeypatch, capsys):
    """THERE IS NO FALLBACK. A stale kickoff is worse than no card."""
    from data_ingest import schedule
    now = datetime.now(timezone.utc)
    day, tod = _et(now + timedelta(days=2))
    _stale_file(tmp_path, [f"2026_05_CHI_GB,2026,5,{day},{tod},CHI,GB,Home,outdoors,GNB00,Lambeau Field"])
    monkeypatch.chdir(tmp_path)

    def _down(lo, hi):
        raise ConnectionError("no route to the database")
    monkeypatch.setattr(schedule, "fetch_rows", _down)
    assert schedule.load_schedule(0.0, 10.0).empty
    assert "NFL schedule unavailable" in capsys.readouterr().err


def test_a_game_that_has_kicked_off_never_reaches_the_wind_card(nfl_path, monkeypatch):
    """The ONLY started-game guard on the wind model.

    `wind_totals.select_bets` bounds the lead from above only, the live odds
    pull carries in-play totals, and the publisher's BET insert does not ask
    whether the game has started. So the schedule's `kick_utc > now` is what
    keeps an in-play total off the card; a bound loosened by a day would put
    every game of the last 24 hours back on it.
    """
    card = _load_script("weekly_wind_card")
    now = pd.Timestamp.now(tz="UTC").floor("min")
    _feed(monkeypatch, [
        _row("2026_08_KC_DEN", "KC", "DEN", now - pd.Timedelta(hours=1),
             stadium_id="DEN00", stadium="Empower Field at Mile High"),
        _row("2026_08_CHI_SEA", "CHI", "SEA", now - pd.Timedelta(minutes=1),
             stadium_id="SEA00", stadium="Lumen Field"),
        _row("2026_08_BUF_NE", "BUF", "NE", now + pd.Timedelta(hours=1),
             stadium_id="BOS00", stadium="Gillette Stadium"),
    ])
    g = card.load_schedule(7)
    assert list(g.game_id) == ["2026_08_BUF_NE"]
    assert (g.lead_days > 0).all()


def test_a_playoff_game_reaches_the_cards(nfl_path):
    """The file had none. A wild-card row in the games table is just a game."""
    from data_ingest.schedule import load_schedule
    wc = _row("2026_19_GB_CHI", "GB", "CHI", "2027-01-16T21:30:00+00:00",
              stadium_id="CHI98", stadium="Soldier Field", week=19)
    g = load_schedule(0.0, 10.0, now="2027-01-11T12:00:00Z", rows=[wc])
    assert list(g.game_id) == ["2026_19_GB_CHI"]
    assert g.lead_days.iloc[0] == pytest.approx(5.396, abs=1e-3)


# ── The wind card skips a game it cannot place, and prices the rest ─────────

def test_an_unplaced_game_is_not_forecast_and_does_not_stop_the_slate(
        nfl_path, monkeypatch, capsys):
    """Before: an outdoor game with no coordinates was a FATAL for the whole
    card, and a None venue crashed the forecast loop. Now it is left with no
    forecast, said out loud, and every placed game is still forecast."""
    card = _load_script("weekly_wind_card")
    kick = pd.Timestamp.now(tz="UTC").floor("h") + pd.Timedelta(days=2)
    slate = pd.DataFrame([
        {"game_id": "2026_08_CHI_SEA", "matchup": "CHI @ SEA", "kick_utc": kick,
         "stadium_id": "SEA00", "roof": "outdoors", "lead_days": 2.0, "venue_note": ""},
        {"game_id": "2027_01_XX_YY", "matchup": "XX @ YY", "kick_utc": kick,
         "stadium_id": None, "roof": "outdoors", "lead_days": 2.0,
         "venue_note": "neutral site Somewhere Park (nflverse id YY00) is not in the venue table"},
    ])
    asked = []

    def _fc(sid, days=9):
        asked.append(sid)
        return pd.DataFrame({"stadium_id": sid, "ts": [kick], "wind": [15.0],
                             "gust": [22.0], "temp": [50.0]})
    monkeypatch.setattr(card, "fetch_live_forecast", _fc)
    out = card.attach_forecast(slate).set_index("game_id")
    assert asked == ["SEA00"]
    assert out.loc["2026_08_CHI_SEA", "forecast_wind"] == 15.0
    assert pd.isna(out.loc["2027_01_XX_YY", "forecast_wind"])
    assert "venue not established for XX @ YY" in capsys.readouterr().err


# ── The scheduler's NFL clock ────────────────────────────────────────────────

@pytest.fixture()
def clock(monkeypatch, tmp_path):
    """scheduler with an empty kickoff cache and a stale file under ROOT."""
    import scheduler
    monkeypatch.setattr(scheduler, "_nfl_kickoff_cache",
                        {"read_at": None, "kicks": None}, raising=False)
    monkeypatch.setattr(scheduler, "ROOT", tmp_path)
    return scheduler


def _clock_file(tmp_path, kicks):
    rows = []
    for i, k in enumerate(kicks):
        day, tod = _et(k)
        rows.append(f"2026_18_A{i}_B{i},2026,18,{day},{tod},A{i},B{i},Home,outdoors,GNB00,Lambeau Field")
    _stale_file(tmp_path / "nfl", rows)


def test_the_clock_reads_the_games_table_not_the_file(clock, tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    _clock_file(tmp_path, [now + timedelta(hours=5)])
    monkeypatch.setattr(clock, "_read_nfl_kickoffs",
                        lambda now: [now + timedelta(hours=2)], raising=False)
    assert clock._nfl_lead_hours() == pytest.approx(2.0, abs=0.01)


def test_the_clock_sees_the_playoffs_after_week_18(clock, tmp_path, monkeypatch):
    """The file's last game is in the past; the games table has a wild card."""
    now = datetime.now(timezone.utc)
    _clock_file(tmp_path, [now - timedelta(days=1)])
    monkeypatch.setattr(clock, "_read_nfl_kickoffs",
                        lambda now: [now - timedelta(days=1), now + timedelta(days=6)],
                        raising=False)
    assert clock._nfl_lead_hours() == pytest.approx(144.0, abs=0.01)


def test_the_clock_reads_the_database_at_most_once_per_cache_window(clock, monkeypatch):
    now = datetime.now(timezone.utc)
    reads = []
    monkeypatch.setattr(clock, "_read_nfl_kickoffs",
                        lambda now: reads.append(now) or [now + timedelta(hours=30)])
    for _ in range(5):
        assert clock._nfl_lead_hours() == pytest.approx(30.0, abs=0.05)
    assert len(reads) == 1
    clock._nfl_kickoff_cache["read_at"] = now - timedelta(seconds=clock.NFL_SCHEDULE_CACHE_S + 1)
    clock._nfl_lead_hours()
    assert len(reads) == 2


def test_a_failed_read_keeps_the_last_list_and_none_without_one(clock, monkeypatch):
    now = datetime.now(timezone.utc)

    def _down(now):
        raise ConnectionError("pool exhausted")
    monkeypatch.setattr(clock, "_read_nfl_kickoffs", _down)
    assert clock._nfl_lead_hours() is None            # nothing to fall back on

    clock._nfl_kickoff_cache.update(
        read_at=now - timedelta(hours=2), kicks=[now + timedelta(hours=10)])
    assert clock._nfl_lead_hours() == pytest.approx(10.0, abs=0.05)
