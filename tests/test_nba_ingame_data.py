"""The in-play quote / game-state join (scripts/nba_ingame_data.py,
docs/nba_models_2026.md section 7.1), on synthetic plays and quotes.

What each test pins:
  - a quote stamped after the listed tip but before the first play is NOT in
    play, and a quote stamped after the first play is, whatever its label;
  - the state at a stamp counts only plays ESPN logged at or before it, by
    wallclock (a play one second later is not counted; a correction logged
    later is not counted even when its play number is earlier);
  - a quote stamped between the End Period row of period 2 and the first play
    of period 3 is labelled halftime; the gap after period 1 is a break;
  - Pinnacle is attached within 60 seconds in the same fetch, not at 61;
  - the foul rule (charges logged only as turnovers count once; offensive and
    technical fouls are not team fouls).
"""
from __future__ import annotations

import pandas as pd
import pytest

from scripts import nba_ingame_data as D

T0 = pd.Timestamp("2025-01-10T00:10:00Z")


def ts(sec: float) -> pd.Timestamp:
    return T0 + pd.Timedelta(seconds=sec)


def play(n, sec, period, clock, type_text="Jump Shot", side=None, points=0, athlete=None,
         fg3a=0, fg3m=0, fta=0, ftm=0):
    return {"game_id": "G", "play_no": n, "wc": ts(sec), "period": period, "clock_s": clock,
            "game_s": D_elapsed(period, clock), "type_text": type_text, "team_side": side,
            "points": points, "fg3a": fg3a, "fg3m": fg3m, "fta": fta, "ftm": ftm,
            "athlete_id_1": athlete}


def D_elapsed(period, clock):
    return 720 * (period - 1) + 720 - clock


@pytest.fixture
def plays():
    rows = [
        play(1, 0, 1, 720, "Jumpball"),
        play(2, 30, 1, 700, "Jump Shot", "H", 2, 11.0),
        play(3, 60, 1, 680, "Jump Shot", "A", 3, 21.0, fg3a=1, fg3m=1),
        play(4, 600, 1, 0, "End Period"),
        play(5, 700, 2, 720, "Substitution"),
        play(6, 720, 2, 700, "Jump Shot", "H", 2, 11.0),
        play(7, 1500, 2, 0, "End Period"),
        play(8, 2400, 3, 720, "Jump Shot", "A", 2, 21.0),
        play(9, 3000, 3, 0, "End Period"),
        play(10, 3100, 4, 720, "Jump Shot", "H", 2, 11.0),
        play(11, 4000, 4, 0, "End Period"),
        play(12, 4005, 4, 0, "End Game"),
    ]
    df = pd.DataFrame(rows)
    return D.foul_flags(df)


def quotes(stamps, label="in_play", **extra):
    q = pd.DataFrame({"game_id": "G", "stamp": [ts(s) for s in stamps], "label": label})
    for k, v in extra.items():
        q[k] = v
    return q


def test_a_quote_before_the_first_play_is_excluded(plays):
    b = D.phase_bounds(plays)
    # stamped after the listed tip (T0 - 10 min) but 5 s before the first play
    q = quotes([-5, 0, 45])
    q.loc[2, "label"] = "open"            # a pre-game label does not keep a live quote out
    kept, counts = D.keep_in_play(q, b)
    assert list(kept["stamp"]) == [ts(0), ts(45)]
    assert counts["phase_counts_all"]["pregame"] == 1


def test_after_the_final_period_is_postgame(plays):
    b = D.phase_bounds(plays)
    kept, _ = D.keep_in_play(quotes([3999, 4000, 4500]), b)
    assert list(kept["stamp"]) == [ts(3999)]


def test_the_state_counts_only_plays_logged_at_or_before_the_stamp(plays):
    tl = D.timeline(plays)
    q = quotes([29, 30, 59, 61])
    s = D.state_at(q, tl, "stamp", ["h_pts", "a_pts", "a_fg3a", "period", "clock_s"])
    assert list(s["h_pts"]) == [0, 2, 2, 2]          # the basket at +30 s counts from +30 s
    assert list(s["a_pts"]) == [0, 0, 0, 3]          # the three at +60 s is not in at +59 s
    assert list(s["a_fg3a"]) == [0, 0, 0, 1]
    assert list(s["clock_s"]) == [720, 700, 700, 680]


def test_a_correction_logged_later_is_not_known_earlier(plays):
    # play 13 belongs early in period 1 by play order but ESPN logged it at +900 s
    late = pd.DataFrame([play(2.5, 900, 1, 690, "Jump Shot", "A", 2, 21.0)])
    p = D.foul_flags(pd.concat([plays, late], ignore_index=True))
    tl = D.timeline(p)
    s = D.state_at(quotes([650, 950]), tl, "stamp", ["a_pts"])
    assert list(s["a_pts"]) == [3, 5]


def test_halftime_and_breaks_are_labelled_from_the_play_clock(plays):
    b = D.phase_bounds(plays)
    q = quotes([1499, 1500, 2000, 2399, 2400, 650, 3050])
    ph = D.label_phase(q, b)
    assert list(ph) == ["live", "halftime", "halftime", "halftime", "live", "break", "break"]


def test_pinnacle_within_60_seconds_in_the_same_fetch():
    f1, f2 = pd.Timestamp("2025-01-10T01:00:00Z"), pd.Timestamp("2025-01-10T02:00:00Z")
    rows = [
        # book, stamp offset, fetch
        ("pinnacle", 0, f1),
        ("draftkings", 59, f1),
        ("fanduel", -61, f1),
        ("betmgm", 10, f2),         # a different fetch: no Pinnacle there
    ]
    q = pd.DataFrame({"game_id": "G", "market": "h2h", "book": [r[0] for r in rows],
                      "stamp": [ts(r[1]) for r in rows], "fetch_at": [r[2] for r in rows],
                      "line": float("nan"), "price_a": -150.0, "price_b": 130.0,
                      "coherent": True, "fa": 0.58})
    out = D.attach_pinnacle(q)
    got = dict(zip(out["book"], out["pin_dt_s"]))
    assert got["pinnacle"] == 0
    assert got["draftkings"] == 59
    assert pd.isna(got["fanduel"])
    assert pd.isna(got["betmgm"])
    assert out.loc[out["book"] == "draftkings", "pin_fa"].iloc[0] == pytest.approx(0.58)


def test_the_foul_rule():
    rows = [
        play(1, 0, 1, 600, "Offensive Foul", "H", athlete=11.0),
        play(2, 1, 1, 600, "Offensive Foul Turnover", "H", athlete=11.0),   # same charge: not twice
        play(3, 5, 1, 500, "Offensive Foul Turnover", "A", athlete=21.0),   # lone: a charge
        play(4, 9, 1, 400, "Shooting Foul", "A", athlete=22.0),
        play(5, 12, 1, 300, "Technical Foul", "H", athlete=12.0),
        play(6, 15, 1, 200, "Defensive 3-Seconds Technical", "A", athlete=23.0),
        play(7, 18, 1, 100, "Loose Ball Foul", "H", athlete=13.0),
    ]
    f = D.foul_flags(pd.DataFrame(rows))
    assert list(f["pf"]) == [1, 0, 1, 1, 0, 0, 1]
    assert list(f["tf"]) == [0, 0, 0, 1, 0, 0, 1]
