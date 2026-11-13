"""A synthetic NBA game for the in-play tests: ESPN summary JSON, an Odds API
bulk payload and a games frame, built so each freshness and clock rule can be
broken one at a time. Not collected (no test_ prefix).

The game: NYK @ BOS, listed tip 2026-11-05T00:00Z (7pm ET on 2026-11-04).
A play every 45 s of wall time and 30 s of game time from the jump ball at
00:05:00Z, 24 plays a period; every third play is a made two (home on even
multiples of three, away on odd). End Period after each period, then a 2-minute
break (15 after the half). ESPN logs the next period's 12:00 substitution the
moment a period ends."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

TIP = datetime(2026, 11, 5, 0, 0, tzinfo=timezone.utc)
FIRST = TIP + timedelta(minutes=5)
GAME_ID = "NBA_2026-11-04_NYK_BOS"
GAME_DATE = "2026-11-04"
EVENT_ID = 401909999
HOME_ID, AWAY_ID = 2, 18
HOME_NAME, AWAY_NAME = "Boston Celtics", "New York Knicks"
PLAY_GAP = timedelta(seconds=45)
BREAKS = {1: timedelta(minutes=2), 2: timedelta(minutes=15), 3: timedelta(minutes=2)}
HOME_STARTERS = [9001, 9002, 9003, 9004, 9005]
AWAY_STARTERS = [9101, 9102, 9103, 9104, 9105]


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clock_text(s: float) -> str:
    return f"{int(s // 60)}:{int(s % 60):02d}"


def build_plays(periods: int = 4, first: datetime = FIRST, extra: list[dict] | None = None,
                shift_after: tuple | None = None) -> list[dict]:
    """ESPN summary play dicts for the whole game, in order. `extra`: plays
    to add (dicts with period, clock_s, wallclock datetime, team 'H'/'A',
    points). `shift_after`: (play index, timedelta) moves every later play's
    wallclock by the delta (a clock jump)."""
    plays, seq = [], 0
    h = a = 0
    t = first
    k = 0

    def add(period, clock_s, wall, ttext, team=None, pts=0, shooting=False, pa=None):
        nonlocal seq, h, a
        seq += 1
        if pts and team == "H":
            h += pts
        elif pts and team == "A":
            a += pts
        plays.append({
            "id": f"{EVENT_ID}{seq}", "sequenceNumber": str(seq),
            "type": {"id": "1", "text": ttext}, "text": ttext,
            "awayScore": a, "homeScore": h, "period": {"number": period},
            "clock": {"displayValue": clock_text(clock_s)}, "scoringPlay": bool(pts),
            "scoreValue": pts, "team": {"id": str(HOME_ID if team == "H" else AWAY_ID)} if team else {},
            "participants": [], "wallclock": iso(wall), "shootingPlay": shooting,
            "coordinate": {"x": 25, "y": 5}, "pointsAttempted": pa or 0,
        })

    for per in range(1, periods + 1):
        if per == 1:
            add(1, 720.0, t, "Jumpball", team="H")
        for i in range(24):
            clk = 720.0 - 30.0 * (i + 1)
            t = t + PLAY_GAP
            if k % 3 == 0:
                team = "H" if (k // 3) % 2 == 0 else "A"
                add(per, clk, t, "Jump Shot", team=team, pts=2, shooting=True, pa=2)
            else:
                add(per, clk, t, "Defensive Rebound", team="H" if k % 2 else "A")
            k += 1
        t = t + timedelta(seconds=10)
        add(per, 0.0, t, "End Period")
        if per < periods:
            add(per + 1, 720.0, t + timedelta(seconds=2), "Substitution", team="H")
            t = t + BREAKS.get(per, timedelta(minutes=2))
    for e in extra or []:
        seq += 1
        # ESPN's running score at an inserted play: the plays logged before it, plus it
        w_e = e["wallclock"]
        before = [p for p in plays if datetime.fromisoformat(p["wallclock"].replace("Z", "+00:00")) <= w_e]
        bh = max((p["homeScore"] for p in before), default=0)
        ba = max((p["awayScore"] for p in before), default=0)
        pts = e.get("points", 0)
        if e.get("team", "H") == "H":
            bh += pts
        else:
            ba += pts
        plays.append({
            "id": f"{EVENT_ID}x{seq}", "sequenceNumber": str(seq),
            "type": {"id": "1", "text": "Jump Shot" if e.get("points") else "Defensive Rebound"},
            "text": "extra", "awayScore": ba, "homeScore": bh, "period": {"number": e["period"]},
            "clock": {"displayValue": clock_text(e["clock_s"])}, "scoringPlay": bool(e.get("points")),
            "scoreValue": e.get("points", 0),
            "team": {"id": str(HOME_ID if e.get("team", "H") == "H" else AWAY_ID)},
            "participants": [], "wallclock": iso(e["wallclock"]), "shootingPlay": bool(e.get("points")),
            "coordinate": {"x": 25, "y": 5}, "pointsAttempted": e.get("points", 0),
        })
    if shift_after is not None:
        idx, delta = shift_after
        for p in plays[idx:]:
            w = datetime.fromisoformat(p["wallclock"].replace("Z", "+00:00")) + delta
            p["wallclock"] = iso(w)
    return plays


def summary(plays: list[dict], known_until: datetime | None = None, final: bool = False,
            header_score: tuple | None = None) -> dict:
    """An ESPN summary carrying the plays logged up to `known_until`. The
    header's score and clock are the newest known play's, as a healthy feed's
    are; `header_score` (home, away) overrides the score (a play list behind
    its header)."""
    if known_until is not None:
        plays = [p for p in plays
                 if datetime.fromisoformat(p["wallclock"].replace("Z", "+00:00")) <= known_until]
    last = max(plays, key=lambda p: (p["period"]["number"], int(p["sequenceNumber"]))) if plays else None
    hs, as_ = header_score if header_score is not None else (
        (last["homeScore"], last["awayScore"]) if last else (0, 0))
    clk = last["clock"]["displayValue"] if last else "12:00"
    mm, ss = clk.split(":")
    status = {"type": {"completed": final, "state": "post" if final else "in"},
              "period": last["period"]["number"] if last else 1, "clock": float(int(mm) * 60 + int(ss))}
    athletes_h = [{"athlete": {"id": str(i), "displayName": f"H{i}"}, "starter": True, "stats": []}
                  for i in HOME_STARTERS]
    athletes_a = [{"athlete": {"id": str(i), "displayName": f"A{i}"}, "starter": True, "stats": []}
                  for i in AWAY_STARTERS]
    return {
        "header": {"competitions": [{
            "status": status,
            "competitors": [
                {"homeAway": "home", "score": str(hs),
                 "team": {"id": str(HOME_ID), "abbreviation": "BOS", "displayName": HOME_NAME}},
                {"homeAway": "away", "score": str(as_),
                 "team": {"id": str(AWAY_ID), "abbreviation": "NY", "displayName": AWAY_NAME}},
            ]}]},
        "plays": plays,
        "boxscore": {"players": [
            {"team": {"abbreviation": "BOS", "displayName": HOME_NAME},
             "statistics": [{"labels": ["MIN"], "athletes": athletes_h}]},
            {"team": {"abbreviation": "NY", "displayName": AWAY_NAME},
             "statistics": [{"labels": ["MIN"], "athletes": athletes_a}]},
        ]},
    }


def scoreboard_event(period: int = 2, state: str = "in") -> dict:
    return {"events": [{
        "id": str(EVENT_ID), "date": iso(TIP), "season": {"type": 2},
        "status": {"period": period, "displayClock": "5:00",
                   "type": {"state": state, "name": "STATUS_IN_PROGRESS"}},
        "competitions": [{"competitors": [
            {"homeAway": "home", "team": {"abbreviation": "BOS", "displayName": HOME_NAME}},
            {"homeAway": "away", "team": {"abbreviation": "NY", "displayName": AWAY_NAME}},
        ]}]}]}


def wall_of(plays: list[dict], period: int, clock_s: float) -> datetime:
    for p in plays:
        if p["period"]["number"] == period and p["clock"]["displayValue"] == clock_text(clock_s) \
                and p["type"]["text"] not in ("Substitution", "End Period"):
            return datetime.fromisoformat(p["wallclock"].replace("Z", "+00:00"))
    raise KeyError((period, clock_s))


def book(key: str, ts: datetime, h2h=None, spread=None) -> dict:
    """One bookmaker: h2h=(home price, away price); spread=(home number,
    home price, away price)."""
    markets = []
    if h2h is not None:
        markets.append({"key": "h2h", "last_update": iso(ts), "outcomes": [
            {"name": HOME_NAME, "price": h2h[0]}, {"name": AWAY_NAME, "price": h2h[1]}]})
    if spread is not None:
        markets.append({"key": "spreads", "last_update": iso(ts), "outcomes": [
            {"name": HOME_NAME, "price": spread[1], "point": spread[0]},
            {"name": AWAY_NAME, "price": spread[2], "point": -spread[0]}]})
    return {"key": key, "last_update": iso(ts), "markets": markets}


def events(books: list[dict]) -> list[dict]:
    return [{"id": "evt1", "home_team": HOME_NAME, "away_team": AWAY_NAME, "commence_time": iso(TIP),
             "bookmakers": books}]


def games_frame() -> pd.DataFrame:
    return pd.DataFrame([{"game_id": GAME_ID, "season": 2027, "game_date": GAME_DATE,
                          "tip": pd.Timestamp(TIP)}])


def starters() -> pd.DataFrame:
    rows = [{"espn_id": i, "side": "H", "starter": True} for i in HOME_STARTERS]
    rows += [{"espn_id": i, "side": "A", "starter": True} for i in AWAY_STARTERS]
    return pd.DataFrame(rows)
