"""Every new player-prop row is stamped in UTC.

mike, 2026-10-09: "fix the prop writers to stamp UTC too". The MLB/WNBA/NBA
writer and the college football writer stamped Eastern time
(`datetime.now(_ET).isoformat()`, "-04:00"); the NFL and NHL writers stamp UTC.
For games on 2026-10-05 to 10-10, 1,990,335 of 2,542,384 player_prop_odds rows
were Eastern (measured 2026-10-09). Several readers order
the stamp as text inside one prop (the trigger that keeps the latest price, the
odds pruner, the app's prop history), and on 2026-11-01 an Eastern writer would
switch to "-05:00" and the repeated 1am hour would sort backwards.

Pinned here through the real run functions, with a frozen clock:
  1. The stamp is the pass's instant in UTC, written "+00:00".
  2. It never ends in "Z". backfilled_dates() reads a trailing "Z" from
     Pinnacle as a bought historical row, so a "Z" live stamp would make a paid
     backfill re-run skip dates it should buy.
  3. The slate date stays Eastern: at 11:30pm Eastern the pass still asks for
     tonight's games, not tomorrow's.
  4. Two passes either side of the 2026-11-01 clock change sort in time order
     as text.
Old rows are not rewritten, so readers keep parsing or casting; item 5
records, without calling the writers, why a switch-day series still sorts in
time order as text.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import data.ingestors.ncaaf_prop_odds_ingestor as ncaaf
import data.ingestors.prop_odds_ingestor as ing

ET = ZoneInfo("America/New_York")

# 11:30pm Eastern on 2026-10-09 is already 2026-10-10 in UTC.
LATE_EVENING = datetime(2026, 10, 10, 3, 30, 0, 123456, tzinfo=timezone.utc)

_PROPS = [("draftkings", [{
    "key": "batter_hits",
    "outcomes": [
        {"name": "Over", "description": "Aaron Judge", "price": -110, "point": 1.5},
        {"name": "Under", "description": "Aaron Judge", "price": -110, "point": 1.5},
    ],
}])]

_NCAAF_PROPS = [("draftkings", [{
    "key": "player_pass_yds",
    "outcomes": [
        {"name": "Over", "description": "Jalon Daniels", "price": -115, "point": 224.5},
        {"name": "Under", "description": "Jalon Daniels", "price": -105, "point": 224.5},
    ],
}])]


def _frozen(instant_utc: datetime) -> type:
    """A datetime whose now() is `instant_utc`, in whatever zone is asked for."""
    class _Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return instant_utc.replace(tzinfo=None)
            return instant_utc.astimezone(tz)
    return _Clock


class _Conn:
    def execute(self, sql, params=None):
        return type("R", (), {"fetchall": lambda s: [], "fetchone": lambda s: None})()

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def _run_mlb(monkeypatch, instant_utc: datetime) -> tuple[list[dict], list[str], dict]:
    """One MLB pass at `instant_utc`. Returns (rows handed to the INSERT,
    the slate dates asked for, the run summary)."""
    rows: list[dict] = []
    asked: list[str] = []

    def events(target_date, sport_key, days_ahead):
        asked.append(target_date)
        return [{"id": "ev1", "home_team": "New York Yankees",
                 "away_team": "Boston Red Sox",
                 "commence_time": "2026-10-09T23:05:00Z",
                 "game_date": target_date}]

    def capture(conn, batch):
        rows.extend(batch)
        return len(batch)

    monkeypatch.setattr(ing, "datetime", _frozen(instant_utc))
    monkeypatch.setattr(ing, "get_connection", lambda: _Conn())
    monkeypatch.setattr(ing, "persist_quota", lambda c: None)
    monkeypatch.setattr(ing, "alt_markets_due", lambda *a, **k: False)
    monkeypatch.setattr(ing, "_get_events", events)
    monkeypatch.setattr(ing, "_existing_game_ids", lambda conn, ids: set(ids))
    monkeypatch.setattr(ing, "_get_event_props", lambda *a, **k: _PROPS)
    monkeypatch.setattr(ing, "_insert_prop_odds", capture)
    monkeypatch.setattr(ing, "_log_pipeline", lambda *a, **k: None)
    monkeypatch.setattr(ing.time, "sleep", lambda s: None)
    out = ing.run_prop_odds_ingestor(snapshot_type="open", sport="MLB", days_ahead=0)
    assert rows, "the fake pass must write rows, or the stamp checks prove nothing"
    return rows, asked, out


def _run_ncaaf(monkeypatch, instant_utc: datetime) -> tuple[list[dict], list[str], dict]:
    rows: list[dict] = []
    asked: list[str] = []
    gid = "NCAAF_2026-10-09_long-island-university_kansas"

    def events(target_date):
        asked.append(target_date)
        return [{"id": "ev1", "home_team": "Kansas Jayhawks",
                 "away_team": "Long Island University Sharks"}]

    def capture(conn, batch):
        rows.extend(batch)
        return len(batch)

    monkeypatch.setattr(ncaaf, "datetime", _frozen(instant_utc))
    monkeypatch.setattr(ncaaf, "get_connection", lambda: _Conn())
    monkeypatch.setattr(ncaaf, "persist_quota", lambda c: None)
    monkeypatch.setattr(ncaaf, "_get_events", events)
    monkeypatch.setattr(ncaaf, "scope_events",
                        lambda conn, evs, d: ([(evs[0], gid)], {}))
    monkeypatch.setattr(ncaaf, "_event_props", lambda ev, mk: (_NCAAF_PROPS, 10))
    monkeypatch.setattr(ncaaf, "_insert_prop_odds", capture)
    out = ncaaf.run_ncaaf_prop_odds_ingestor()
    assert rows, "the fake pass must write rows, or the stamp checks prove nothing"
    return rows, asked, out


def _assert_utc_stamp(rows: list[dict], instant_utc: datetime) -> None:
    stamps = {r["snapshot_at"] for r in rows}
    assert len(stamps) == 1, f"one stamp per pass, got {stamps}"
    stamp = stamps.pop()
    assert stamp == instant_utc.isoformat(), stamp
    assert stamp.endswith("+00:00"), stamp
    assert not stamp.endswith("Z"), \
        "a live 'Z' stamp reads as a bought backfill row to backfilled_dates()"
    assert datetime.fromisoformat(stamp).utcoffset() == timedelta(0), stamp


# ── 1-3: MLB, WNBA and NBA share one writer ─────────────────────────────────

def test_the_mlb_wnba_nba_writer_stamps_utc(monkeypatch):
    rows, _asked, _out = _run_mlb(monkeypatch, LATE_EVENING)
    _assert_utc_stamp(rows, LATE_EVENING)


def test_the_mlb_wnba_nba_slate_date_stays_eastern(monkeypatch):
    """11:30pm Eastern on the 9th: still the 9th's slate, even though the
    stamp's UTC date is the 10th. A UTC slate date would ask for tomorrow's
    games and the scorer would find no prop rows for tonight."""
    rows, asked, out = _run_mlb(monkeypatch, LATE_EVENING)
    assert asked == ["2026-10-09"]
    assert out["target_date"] == "2026-10-09"
    assert {r["game_date"] for r in rows} == {"2026-10-09"}
    assert rows[0]["snapshot_at"].startswith("2026-10-10T03:30:00")


# ── 1-3: college football ───────────────────────────────────────────────────

def test_the_college_football_writer_stamps_utc(monkeypatch):
    rows, _asked, _out = _run_ncaaf(monkeypatch, LATE_EVENING)
    _assert_utc_stamp(rows, LATE_EVENING)


def test_the_college_football_slate_date_stays_eastern(monkeypatch):
    rows, asked, out = _run_ncaaf(monkeypatch, LATE_EVENING)
    assert asked == ["2026-10-09"]
    assert out["target_date"] == "2026-10-09"
    assert {r["game_date"] for r in rows} == {"2026-10-09"}


# ── 4: the 2026-11-01 clock change ──────────────────────────────────────────

def test_passes_either_side_of_the_fall_back_sort_in_time_order(monkeypatch):
    """1:30am EDT, then 1:10am EST forty minutes later. Stamped Eastern these
    read '...T01:30:00-04:00' then '...T01:10:00-05:00', so the later pass
    sorts first as text and the latest-price trigger would keep the earlier
    price. Stamped UTC they read 05:30 then 06:10."""
    first = datetime(2026, 11, 1, 5, 30, tzinfo=timezone.utc)    # 01:30 EDT
    second = datetime(2026, 11, 1, 6, 10, tzinfo=timezone.utc)   # 01:10 EST
    assert first.astimezone(ET).hour == 1 and second.astimezone(ET).hour == 1

    stamps = []
    for when in (first, second):
        rows, _asked, _out = _run_mlb(monkeypatch, when)
        stamps.append(rows[0]["snapshot_at"])
    assert stamps[0] < stamps[1], stamps
    for when in (first, second):
        rows, _asked, _out = _run_ncaaf(monkeypatch, when)
        stamps.append(rows[0]["snapshot_at"])
    assert stamps[2] < stamps[3], stamps[2:]


# ── 5: switch day ───────────────────────────────────────────────────────────

def test_an_eastern_row_then_a_later_utc_row_sorts_in_time_order():
    """This checks a property of the two stamp formats, not the writers. Tests
    1-4 cover the writers, and only a run against the real trigger in
    tests/test_latest_line_state.py would check the database's own ordering.

    Rows written before this change stay Eastern. On switch day one prop's
    series is Eastern rows, then UTC rows. Readers that order inside one prop
    as text (the latest-price trigger, the pruner) need the UTC rows to sort
    after every earlier Eastern row. A UTC wall clock is always 4 or 5 hours
    ahead of the Eastern one for the same instant, so this holds at any time
    of day; checked every 7 minutes over the evening the date rolls over in
    UTC. (Python compares bytes; the same comparisons were checked under the
    production database's collation on 2026-10-09.)"""
    start = datetime(2026, 10, 9, 18, 0, tzinfo=timezone.utc)
    for i in range(0, 24 * 60, 7):
        old = start + timedelta(minutes=i, microseconds=999999)
        for gap in (timedelta(microseconds=1), timedelta(minutes=10), timedelta(hours=6)):
            new = old + gap
            eastern = old.astimezone(ET).isoformat()
            utc = new.astimezone(timezone.utc).isoformat()
            assert eastern < utc, (eastern, utc)
