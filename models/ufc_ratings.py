"""Fighter ratings and pre-fight inputs for the UFC opening-price model.

Every input is taken strictly before the fight: an Elo rating, UFC
experience, layoff, win / finish / decision rates, strike, takedown,
knockdown and submission rates per 15 minutes, average fight length, the
last result, and age, reach and height from the fighter's profile. The model
uses the A-minus-B difference of each (A = the fighter with the smaller
slug), plus a debut flag.

This is the production copy of the research builder
(scripts/ufc_study/fights.py, docs/ufc_market_audit.md section 3b), and it
must give the same numbers: tests/test_ufc_open_moneyline.py replays every
2026 fight against the research table.

    states = replay(fight_log_rows, profiles)       # every logged fight, in order
    z = pair_diffs(states, a_id, b_id, profiles, on_date)
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

K0 = 64.0
DIFFS = ("elo", "n", "days_off", "win_rate", "fin_rate", "ko_win", "sub_win", "ko_loss",
         "dec_rate", "slpm", "sapm", "td15", "kd15", "sub15", "avg_mins", "age", "reach",
         "height", "streak")
FEATURES = tuple(f"d_{f}" for f in DIFFS) + ("d_debut",)
FINISHES = ("ko_tko", "submission")


def slugify(name: str) -> str:
    n = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return math.nan
    return f


def _nansum(vals) -> float:
    """pandas' sum: NaN skipped, 0 when nothing is left."""
    return float(sum(v for v in vals if not math.isnan(v)))


def _nanmean(vals) -> float:
    """pandas' mean: NaN skipped, NaN when nothing is left."""
    v = [x for x in vals if not math.isnan(x)]
    return sum(v) / len(v) if v else math.nan


def _day(v) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


@dataclass
class Fighter:
    elo: float = 1500.0
    fights: int = 0                       # rated fights, for the K schedule
    hist: list = field(default_factory=list)


def _side(h: list, on: date) -> dict:
    """The fighter's inputs from his past fights `h` (each a dict)."""
    if not h:
        return {}
    n = len(h)
    wins = [x["result"] == "win" for x in h]
    mins = _nansum(x["mins"] for x in h)
    out = {
        "days_off": (on - h[-1]["date"]).days,
        "win_rate": sum(wins) / n,
        "fin_rate": sum(x["method"] in FINISHES for x in h) / n,
        "ko_win": sum(w and x["method"] == "ko_tko" for w, x in zip(wins, h)) / n,
        "sub_win": sum(w and x["method"] == "submission" for w, x in zip(wins, h)) / n,
        "ko_loss": sum(x["result"] == "loss" and x["method"] == "ko_tko" for x in h) / n,
        "dec_rate": sum(x["method"] == "decision" for x in h) / n,
        "avg_mins": _nanmean(x["mins"] for x in h),
        "streak": 1 if wins[-1] else -1,
    }
    if mins:
        out["slpm"] = _nansum(x["sig_strikes_landed"] for x in h) / mins
        out["sapm"] = _nansum(x["sig_strikes_absorbed"] for x in h) / mins
        out["td15"] = 15 * _nansum(x["takedowns_landed"] for x in h) / mins
        out["kd15"] = 15 * _nansum(x["knockdowns"] for x in h) / mins
        out["sub15"] = 15 * _nansum(x["sub_attempts"] for x in h) / mins
    else:
        out.update(slpm=math.nan, sapm=math.nan, td15=math.nan, kd15=math.nan, sub15=math.nan)
    return out


def _profile(p: dict | None, on: date) -> dict:
    if not p:
        return {}
    out = {"reach": _num(p.get("reach_in")), "height": _num(p.get("height_in"))}
    dob = p.get("dob")
    try:
        out["age"] = (on - _day(dob)).days / 365.25 if dob else math.nan
    except ValueError:
        out["age"] = math.nan
    return out


def fighter_inputs(st: Fighter, profile: dict | None, on: date) -> dict:
    out = {"elo": st.elo, "n": len(st.hist)}
    out.update(_side(st.hist, on))
    out.update(_profile(profile, on))
    return out


def diffs(a: dict, b: dict) -> dict:
    z = {f"d_{f}": _num(a.get(f)) - _num(b.get(f)) for f in DIFFS}
    z["d_debut"] = float((a.get("n", 0) == 0)) - float((b.get("n", 0) == 0))
    return z


def _mins(row) -> float:
    return ((_num(row["end_round"]) - 1) * 300 + _num(row["end_time_sec"])) / 60.0


def replay(rows: list[dict], profiles: dict[str, dict], until: date | None = None,
           on_fight=None) -> dict[str, Fighter]:
    """Every logged fight (two rows each, ufc_fight_log's columns) in date
    order, ratings updated after each. `until`: stop before fights on or
    after this date. `on_fight(game_id, a_row, b_row, z)` sees each fight's
    pre-fight differences, A being the smaller slug."""
    by_game: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_game[r["game_id"]].append(r)
    order = sorted(by_game, key=lambda g: (_day(by_game[g][0]["game_date"]), g,
                                            min(int(x["log_id"]) for x in by_game[g])))
    st: dict[str, Fighter] = defaultdict(Fighter)
    for gid in order:
        pair = sorted(by_game[gid], key=lambda x: int(x["log_id"]))
        if len(pair) != 2:
            continue
        a, b = pair
        if slugify(a["fighter_name"]) > slugify(b["fighter_name"]):
            a, b = b, a
        on = _day(a["game_date"])
        if until is not None and on >= until:
            break
        if on_fight is not None:
            za = fighter_inputs(st[a["fighter_id"]], profiles.get(a["fighter_id"]), on)
            zb = fighter_inputs(st[b["fighter_id"]], profiles.get(b["fighter_id"]), on)
            on_fight(gid, a, b, diffs(za, zb))
        fa, fb = st[a["fighter_id"]], st[b["fighter_id"]]
        pa = 1 / (1 + 10 ** ((fb.elo - fa.elo) / 400))
        sa = {"win": 1.0, "loss": 0.0, "draw": 0.5}.get(a["result"])
        if sa is not None:
            ka = K0 / math.sqrt(1 + fa.fights / 4)
            kb = K0 / math.sqrt(1 + fb.fights / 4)
            fa.elo, fb.elo = fa.elo + ka * (sa - pa), fb.elo - kb * (sa - pa)
        for f, r in ((fa, a), (fb, b)):
            f.fights += 1
            f.hist.append({"date": on, "result": r["result"], "method": r["method"],
                           "mins": _mins(r),
                           "sig_strikes_landed": _num(r["sig_strikes_landed"]),
                           "sig_strikes_absorbed": _num(r["sig_strikes_absorbed"]),
                           "takedowns_landed": _num(r["takedowns_landed"]),
                           "knockdowns": _num(r["knockdowns"]),
                           "sub_attempts": _num(r["sub_attempts"])})
    return st


def pair_diffs(states: dict[str, Fighter], a_id: str, b_id: str,
               profiles: dict[str, dict], on: date) -> dict:
    """A-minus-B inputs for a fight not yet in the log."""
    za = fighter_inputs(states.get(a_id) or Fighter(), profiles.get(a_id), on)
    zb = fighter_inputs(states.get(b_id) or Fighter(), profiles.get(b_id), on)
    return diffs(za, zb)


FIGHT_LOG_COLS = ("log_id", "fighter_id", "fighter_name", "game_id", "game_date", "result",
                  "method", "end_round", "end_time_sec", "sig_strikes_landed",
                  "sig_strikes_absorbed", "takedowns_landed", "knockdowns", "sub_attempts")


def load(conn) -> tuple[list[dict], dict[str, dict]]:
    """The whole fight log and every profile, as replay() takes them."""
    rows = [dict(zip(FIGHT_LOG_COLS, r)) for r in conn.execute(
        f"SELECT {', '.join(FIGHT_LOG_COLS)} FROM ufc_fight_log").fetchall()]
    profiles = {r[0]: {"reach_in": r[1], "height_in": r[2], "dob": r[3], "name": r[4]}
                for r in conn.execute(
                    "SELECT fighter_id, reach_in, height_in, dob, name FROM fighters").fetchall()}
    return rows, profiles
