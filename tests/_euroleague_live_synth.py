"""Shared pieces for the EuroLeague halftime tests: one real game's three
answers from EuroLeague's live API, and states of it at the break.

The fixtures are game 110 of 2026-27 (Panathinaikos 74, Barcelona 76,
2026-11-13), fetched after it ended from live.euroleague.net/api/Header,
PlayByPlay and Points (tests/fixtures/euroleague_live/). Read off them: the
half's last shot 20:09:38Z (MINUTE <= 20 on the shot chart), the half 33-32,
the third quarter's first shot 20:26:52Z, and the third quarter's
substitutions numbered before its 'BP' (logged during the break).
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

FIX = Path(__file__).resolve().parent / "fixtures" / "euroleague_live"
GAME_ID = "EUROLEAGUE_E2026_110"
GAME_DATE = "2026-11-13"
SEASON = 2027
SEASON_CODE = "E2026"
GAME_CODE = 110
HOME, AWAY = "PAN", "BAR"
HOME_FEED, AWAY_FEED = "Panathinaikos", "FC Barcelona Bàsquet"
TIP = pd.Timestamp("2026-11-13T19:15:00Z")
FIRST_SHOT = pd.Timestamp("2026-11-13T19:15:57Z")
LAST_Q2 = pd.Timestamp("2026-11-13T20:09:38Z")
FIRST_Q3 = pd.Timestamp("2026-11-13T20:26:52Z")
HALF = (33, 32)


def answers() -> dict:
    """The finished game's three answers, as the API served them."""
    def rd(n):
        return json.loads((FIX / f"{n}_E2026_110.json").read_text(encoding="utf-8"))
    return {"header": rd("header"), "pbp": rd("playbyplay"), "points": rd("points")}


def at_break(base: dict | None = None) -> dict:
    """The answers as they stood during the break: shots of the first two
    quarters only, the third quarter holding only the substitutions logged in
    the break (no 'BP'), nothing after it, the header live."""
    a = copy.deepcopy(base or answers())
    a["points"]["Rows"] = [r for r in a["points"]["Rows"] if int(r["MINUTE"]) <= 20]
    q3 = a["pbp"]["ThirdQuarter"]
    bp = min(p["NUMBEROFPLAY"] for p in q3 if str(p.get("PLAYTYPE")).strip() == "BP")
    a["pbp"]["ThirdQuarter"] = [p for p in q3 if str(p.get("PLAYTYPE")).strip() in ("IN", "OUT")
                                and p["NUMBEROFPLAY"] < bp]
    a["pbp"]["ForthQuarter"] = []
    a["pbp"]["ExtraTime"] = []
    a["pbp"]["Live"] = True
    a["header"]["Live"] = True
    for k in ("ScoreQuarter3A", "ScoreQuarter3B", "ScoreQuarter4A", "ScoreQuarter4B"):
        a["header"][k] = 0
    return a


def third_begun(with_shot: bool = True) -> dict:
    """The third quarter under way: its 'BP' logged, and its first shot too when asked."""
    a = at_break()
    full = answers()
    bp = [p for p in full["pbp"]["ThirdQuarter"] if str(p.get("PLAYTYPE")).strip() == "BP"]
    a["pbp"]["ThirdQuarter"] = bp + a["pbp"]["ThirdQuarter"]
    if with_shot:
        q3 = sorted((r for r in full["points"]["Rows"] if int(r["MINUTE"]) >= 21), key=lambda r: r["UTC"])
        a["points"]["Rows"].append(q3[0])
    return a


def first_half() -> dict:
    """Still in the second quarter: no 'End Period' in it yet, no shot after minute 18."""
    a = at_break()
    a["pbp"]["SecondQuarter"] = [p for p in a["pbp"]["SecondQuarter"] if str(p.get("PLAYTYPE")).strip() != "EP"]
    a["points"]["Rows"] = [r for r in a["points"]["Rows"] if int(r["MINUTE"]) <= 18]
    a["pbp"]["ThirdQuarter"] = []
    return a


def iso(t) -> str:
    return pd.Timestamp(t).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def book(key: str, stamp, spread=None, total=None) -> dict:
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


def events(books: list, commence=TIP) -> list:
    return [{"id": "el110", "commence_time": iso(commence), "home_team": HOME_FEED, "away_team": AWAY_FEED,
             "bookmakers": books}]


def utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
