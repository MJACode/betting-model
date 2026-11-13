"""NBA builder parity with NFL (Matt, 2026-11-04: "do the same as what I
said for nfl"): the daily refresh, official candidates, and prop
candidates that change only with the prop's own line or price."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from byom.official import OFFICIAL_SPORTS, RoleClock, prop_lock_candidates

KICK = datetime(2026, 11, 2, 0, 30, tzinfo=timezone.utc)


def _spread(hours, home_point):
    return {"market": "spreads", "snapshot_at": KICK - timedelta(hours=hours),
            "lead_hours": float(hours), "point": Decimal(str(home_point)),
            "price_home": -110, "price_away": -110}


def _prop(hours, line, over, under):
    return {"snapshot_at": KICK - timedelta(hours=hours), "lead_hours": float(hours),
            "point": Decimal(str(line)), "over_price": over, "under_price": under,
            "captured_at": None, "prop_id": int(hours)}


FACT = {"canonical_key": "NBA_2026-11-01_BOS_NYK", "sport": "NBA", "season": 2027,
        "market": "player_points", "player_key": "jalen brunson", "team": "NYK",
        "actual": Decimal("31"), "log_status": "logged"}


def test_nba_writes_official_candidates():
    assert "NBA" in OFFICIAL_SPORTS and "NFL" in OFFICIAL_SPORTS


def test_a_prop_candidate_is_new_only_when_its_own_line_or_price_moves():
    # The game spread flips three times. The prop's line and price do not.
    clock = RoleClock([_spread(30, -2.5), _spread(20, 1.5), _spread(10, -1.5)])
    pool = [_prop(29, 28.5, -115, -105), _prop(19, 28.5, -115, -105),
            _prop(9, 28.5, -115, -105)]
    over = [r for r in prop_lock_candidates(FACT, pool, clock, "NYK", "BOS")
            if r["leg_side"] == "over"]
    assert len(over) == 1
    assert over[0]["point"] == Decimal("28.5") and over[0]["result"] == "win"
    # A price move is a new candidate.
    pool.append(_prop(5, 28.5, -125, 105))
    over = [r for r in prop_lock_candidates(FACT, pool, clock, "NYK", "BOS")
            if r["leg_side"] == "over"]
    assert [int(r["price"]) for r in over] == [-115, -125]


class _Conn:
    """Answers the three reads the refresh report makes."""

    def __init__(self, games, facts):
        self.games, self.facts, self.calls = games, facts, []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        rows = []
        if "FROM games" in sql:
            rows = [g for g in self.games if (g[8], g[1]) == (params[0], params[1])]
        elif "FROM byom_game_facts" in sql:
            rows = [f for f in self.facts if params == ("NBA", 2027)]

        class _R:
            def fetchall(self_inner):
                return rows
        return _R()


def test_nba_refresh_finds_this_seasons_unscored_and_window_games():
    from byom.refresh import due_games, freshness
    games = [
        # (game_id, season, game_date, home, away, hs, as, commence, sport, week)
        ("NBA_2026-10-28_BOS_NYK", 2027, "2026-10-28", "NYK", "BOS", 110, 104, None, "NBA", None),
        ("NBA_2026-11-03_LAL_GSW", 2027, "2026-11-03", "GSW", "LAL", 120, 117, None, "NBA", None),
        ("NBA_2026-10-01_OLD_ONE", 2027, "2026-10-01", "MIA", "ORL", 99, 98, None, "NBA", None),
        ("NBA_2026-04-01_LAST_YR", 2026, "2026-04-01", "MIA", "ORL", 99, 98, None, "NBA", None),
    ]
    stale = datetime(2026, 10, 24, tzinfo=timezone.utc)
    facts = [
        ("NBA_2026-10-28_BOS_NYK", None, None, stale, None),   # built before the score
        ("NBA_2026-10-01_OLD_ONE", 99, 98, stale, stale),      # complete, scanned
    ]
    conn = _Conn(games, facts)
    due = due_games(conn, today=date(2026, 11, 4), sport="NBA")
    reasons = {row["canonical_key"]: row["reason"] for row in due}
    assert reasons == {
        "NBA_2026-10-28_BOS_NYK": "incomplete",
        "NBA_2026-11-03_LAL_GSW": "window",
    }
    report = freshness(conn, today=date(2026, 11, 4), sport="NBA")
    assert report["sport"] == "NBA" and report["season"] == 2027


def test_the_refresh_refuses_another_sport():
    import pytest

    from byom.refresh import refresh
    with pytest.raises(ValueError):
        refresh(None, sport="MLB")
