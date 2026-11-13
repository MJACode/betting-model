"""A synthetic NCAAB game for the in-play loop tests: ESPN scoreboard and
summary JSON and an Odds API bulk payload, built so each rule can be broken one
at a time. Not collected (no test_ prefix).

The game: North Carolina @ Duke, listed tip 2026-11-08T00:00Z (7pm ET on
2026-11-07), ESPN event 401999999, Duke (150) at home, UNC (153) away. A play
every 30 s of wall time and 20 s of game time from the jump ball at 00:05:00Z,
60 plays a half. Every third play is a made two: Duke's twice, UNC's once in
each run of three, so Duke pulls away. A 15-minute halftime."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

TIP = datetime(2026, 11, 8, 0, 0, tzinfo=timezone.utc)
FIRST = TIP + timedelta(minutes=5)
GAME_ID = "NCAAB_2026-11-07_north-carolina_duke"
GAME_DATE = "2026-11-07"
EVENT_ID = 401999999
HOME_ID, AWAY_ID = 150, 153
HOME, AWAY = "Duke", "North Carolina"
HOME_FEED, AWAY_FEED = "Duke Blue Devils", "North Carolina Tar Heels"
PLAY_GAP = timedelta(seconds=30)
HALFTIME = timedelta(minutes=15)


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clock_text(s: float) -> str:
    return f"{int(s // 60)}:{int(s % 60):02d}"


def build_plays(extra: list | None = None) -> list[dict]:
    """ESPN summary play dicts for the game, in order. `extra`: plays to add
    (period, clock_s, wallclock, team 'H'/'A', points)."""
    plays, seq = [], 0
    h = a = 0
    t = FIRST

    def add(period, clock_s, wall, ttext, team=None, pts=0):
        nonlocal seq, h, a
        seq += 1
        if pts and team == "H":
            h += pts
        elif pts and team == "A":
            a += pts
        tid = HOME_ID if team == "H" else (AWAY_ID if team == "A" else None)
        p = {"id": f"{EVENT_ID}{seq:04d}", "sequenceNumber": str(seq),
             "type": {"id": "558" if pts else "615", "text": "JumpShot" if pts else ttext},
             "text": ttext, "awayScore": a, "homeScore": h, "period": {"number": period},
             "clock": {"displayValue": clock_text(clock_s)}, "wallclock": iso(wall),
             "scoringPlay": bool(pts), "scoreValue": pts}
        if tid is not None:
            p["team"] = {"id": str(tid)}
        plays.append(p)

    k = 0
    for period in (1, 2):
        add(period, 1200.0, t, "Start period")
        for i in range(60):
            clock_s = 1200.0 - 20.0 * (i + 1)
            t = t + PLAY_GAP
            k += 1
            if k % 3 == 0:
                team = "A" if (k // 3) % 3 == 0 else "H"
                add(period, clock_s, t, "made two", team, 2)
            else:
                add(period, clock_s, t, "Defensive Rebound", "H" if k % 2 else "A")
        t = t + timedelta(seconds=5)
        add(period, 0.0, t, "End Period")
        t = t + HALFTIME
    for e in extra or []:
        add(e["period"], e["clock_s"], e["wallclock"], "made two", e["team"], e["points"])
    plays.sort(key=lambda p: (p["wallclock"], int(p["sequenceNumber"])))
    hh = aa = 0
    for p in plays:                                   # the running score in wallclock order
        if p["scoringPlay"]:
            if p.get("team", {}).get("id") == str(HOME_ID):
                hh += p["scoreValue"]
            else:
                aa += p["scoreValue"]
        p["homeScore"], p["awayScore"] = hh, aa
    return plays


def wall_of(plays: list, period: int, clock_s: float) -> datetime:
    """The wallclock of the play at a period and clock."""
    for p in plays:
        if p["period"]["number"] == period and p["clock"]["displayValue"] == clock_text(clock_s):
            return datetime.fromisoformat(p["wallclock"].replace("Z", "+00:00"))
    raise KeyError((period, clock_s))


def summary(plays: list, known_until: datetime, period: int = 1, clock: float = 600.0) -> dict:
    """ESPN's summary as served at `known_until`: the plays logged by then."""
    shown = [p for p in plays if datetime.fromisoformat(p["wallclock"].replace("Z", "+00:00")) <= known_until]
    last = shown[-1] if shown else {"homeScore": 0, "awayScore": 0}
    return {"header": {"season": {"type": 2}, "competitions": [{
        "competitors": [
            {"homeAway": "home", "team": {"id": str(HOME_ID)}, "score": str(last["homeScore"])},
            {"homeAway": "away", "team": {"id": str(AWAY_ID)}, "score": str(last["awayScore"])}],
        "status": {"type": {"state": "in", "completed": False}, "period": period, "clock": clock}}]},
        "plays": shown}


def scoreboard(period: int = 1, state: str = "in") -> dict:
    return {"events": [{"id": str(EVENT_ID), "date": iso(TIP), "season": {"type": 2},
                        "status": {"type": {"state": state, "name": "STATUS_IN_PROGRESS"}, "period": period,
                                   "displayClock": "10:00"},
                        "competitions": [{"competitors": [
                            {"homeAway": "home", "team": {"id": str(HOME_ID)}},
                            {"homeAway": "away", "team": {"id": str(AWAY_ID)}}]}]}]}


def book(key: str, stamp: datetime, spread=None, total=None) -> dict:
    """One bookmaker's markets. spread = (HOME number, home price, away price);
    total = (line, over price, under price)."""
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
