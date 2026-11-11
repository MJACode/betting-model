"""A synthetic women's college basketball game for the halftime model's tests:
ESPN scoreboard and summary JSON and an Odds API bulk payload, built so each
rule can be broken one at a time. Not collected (no test_ prefix).

The game: Drake @ Iowa, listed tip 2026-11-12T00:00Z (7pm ET on 2026-11-11),
ESPN event 401888888, Iowa (2294) at home, Drake (2181) away. Four 10-minute
quarters; a play every 30 s of wall time and 15 s of game time from 00:05:00Z,
40 plays a quarter. Iowa makes a two on every fourth play and Drake on three
plays in sixteen, so the half ends Iowa 40, Drake 30. Two minutes between the
first two quarters, a 15-minute halftime, then the third quarter."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

TIP = datetime(2026, 11, 12, 0, 0, tzinfo=timezone.utc)
FIRST = TIP + timedelta(minutes=5)
GAME_ID = "NCAABW_2026-11-11_drake_iowa"
GAME_DATE = "2026-11-11"
SEASON = 2027
EVENT_ID = 401888888
HOME_ID, AWAY_ID = 2294, 2181
HOME, AWAY = "Iowa", "Drake"
HOME_FEED, AWAY_FEED = "Iowa Hawkeyes", "Drake Bulldogs"
PLAY_GAP = timedelta(seconds=30)
QUARTER_BREAK = timedelta(minutes=2)
HALFTIME_BREAK = timedelta(minutes=15)
HALF_SCORE = (40, 30)                 # Iowa, Drake


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def at(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def clock_text(s: float) -> str:
    return f"{int(s // 60)}:{int(s % 60):02d}"


def build_plays(extra: list | None = None, quarters: int = 3, quiet_last: bool = False) -> list[dict]:
    """ESPN summary play dicts for the first `quarters` quarters, in ESPN's
    play order. Each play carries the running score of ITS moment in the game.
    `extra`: plays ESPN logged out of order, appended after the rest with their
    own wallclock, as ESPN does: dicts of period, clock_s, wallclock, and
    either points + team ('H'/'A', a play that scores when logged) or score
    (home, away: a late-entered play carrying an old running score).
    `quiet_last`: the half's last play is a rebound, not Iowa's basket, so the
    half ends 38-30 with no point in its last two minutes."""
    plays, seq = [], 0
    h = a = 0
    t = FIRST

    def add(period, clock_s, wall, ttext, team=None, pts=0, score=None):
        nonlocal seq, h, a
        seq += 1
        if pts and team == "H":
            h += pts
        elif pts and team == "A":
            a += pts
        hs, as_ = score if score is not None else (h, a)
        p = {"id": f"{EVENT_ID}{seq:04d}", "sequenceNumber": str(seq),
             "type": {"id": "558" if pts else "615", "text": "JumpShot" if pts else ttext},
             "text": ttext, "awayScore": as_, "homeScore": hs, "period": {"number": period},
             "clock": {"displayValue": clock_text(clock_s)}, "wallclock": iso(wall),
             "scoringPlay": bool(pts), "scoreValue": pts}
        if team is not None:
            p["team"] = {"id": str(HOME_ID if team == "H" else AWAY_ID)}
        plays.append(p)

    k = 0
    for period in range(1, quarters + 1):
        add(period, 600.0, t, "Start period")
        for i in range(40):
            clock_s = 600.0 - 15.0 * (i + 1)
            t = t + PLAY_GAP
            k += 1
            if k % 4 == 0 and not (quiet_last and k == 80):
                add(period, clock_s, t, "made two", "H", 2)
            elif k % 16 in (1, 5, 9):
                add(period, clock_s, t, "made two", "A", 2)
            else:
                add(period, clock_s, t, "Defensive Rebound", "H" if k % 2 else "A")
        t = t + timedelta(seconds=5)
        add(period, 0.0, t, "End Period")
        t = t + (HALFTIME_BREAK if period == 2 else QUARTER_BREAK)
    for e in extra or []:
        add(e["period"], e["clock_s"], e["wallclock"], e.get("text", "Substitution"), e.get("team"),
            e.get("points", 0), e.get("score"))
    return plays


def half_end(plays: list) -> datetime:
    """The wallclock of the second quarter's End Period play."""
    return next(at(p["wallclock"]) for p in plays
                if p["period"]["number"] == 2 and p["text"] == "End Period")


def third_start(plays: list) -> datetime:
    """The wallclock of the third quarter's first play off 10:00."""
    return next(at(p["wallclock"]) for p in plays
                if p["period"]["number"] == 3 and p["clock"]["displayValue"] != "10:00")


def summary(plays: list, known_until: datetime, period: int = 2, status: str = "STATUS_HALFTIME",
            header_score: tuple | None = None, swapped: bool = False) -> dict:
    """ESPN's summary as served at `known_until`: the plays logged by then, and
    a header carrying the highest score among them (or `header_score`)."""
    shown = [p for p in plays if at(p["wallclock"]) <= known_until]
    hs = max((p["homeScore"] for p in shown), default=0)
    as_ = max((p["awayScore"] for p in shown), default=0)
    if header_score is not None:
        hs, as_ = header_score
    home, away = (AWAY_ID, HOME_ID) if swapped else (HOME_ID, AWAY_ID)
    return {"header": {"season": {"type": 2}, "competitions": [{
        "competitors": [
            {"homeAway": "home", "team": {"id": str(home)}, "score": str(hs)},
            {"homeAway": "away", "team": {"id": str(away)}, "score": str(as_)}],
        "status": {"type": {"state": "in", "completed": False, "name": status}, "period": period,
                   "clock": 0.0}}]},
        "plays": shown}


def scoreboard(period: int = 2, state: str = "in", status: str = "STATUS_HALFTIME") -> dict:
    return {"events": [{"id": str(EVENT_ID), "date": iso(TIP), "season": {"type": 2},
                        "status": {"type": {"state": state, "name": status}, "period": period,
                                   "displayClock": "0:00"},
                        "competitions": [{"competitors": [
                            {"homeAway": "home", "team": {"id": str(HOME_ID)}},
                            {"homeAway": "away", "team": {"id": str(AWAY_ID)}}]}]}]}


def book(key: str, stamp: datetime, total=None, spread=None) -> dict:
    """One bookmaker's markets. total = (line, over price, under price);
    spread = (HOME number, home price, away price)."""
    mk = []
    if spread is not None:
        mk.append({"key": "spreads", "last_update": iso(stamp), "outcomes": [
            {"name": HOME_FEED, "price": spread[1], "point": spread[0]},
            {"name": AWAY_FEED, "price": spread[2], "point": -spread[0]}]})
    if total is not None:
        mk.append({"key": "totals", "last_update": iso(stamp), "outcomes": [
            {"name": "Over", "price": total[1], "point": total[0]},
            {"name": "Under", "price": total[2], "point": total[0]}]})
    return {"key": key, "markets": mk}


def events(books: list) -> list:
    return [{"id": "ev1", "commence_time": iso(TIP), "home_team": HOME_FEED, "away_team": AWAY_FEED,
             "bookmakers": books}]
