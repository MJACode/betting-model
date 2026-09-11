"""A quote between two plate appearances sees the NEXT one's before-state.

The trap: the last play that ENDED before the quote, read as its after-state,
carries outs=3 on a third out -- a state the live model was never trained on
(it clips outs to 2 and the bases would still show the stranded runners).
The aligner must roll over to the next half-inning: outs 0, bases empty.
"""
from scripts.inplay_state_align import GameClock


def _p(i, inning, half, outs, bases, h, a, start, end):
    return {"play_index": i, "inning": inning, "half_inning": half,
            "outs_before": outs, "bases_before": bases,
            "score_home_before": h, "score_away_before": a,
            "start_time": start, "end_time": end}


PLAYS = [
    _p(0, 1, "top", 0, "000", 0, 0, "2025-06-18T00:00:00Z", "2025-06-18T00:01:00Z"),
    _p(1, 1, "top", 1, "100", 0, 0, "2025-06-18T00:01:20Z", "2025-06-18T00:02:00Z"),
    # third out of the top half with a runner on: after-state would be outs=3, "100"
    _p(2, 1, "top", 2, "100", 0, 0, "2025-06-18T00:02:20Z", "2025-06-18T00:03:00Z"),
    _p(3, 1, "bottom", 0, "000", 0, 0, "2025-06-18T00:05:30Z", "2025-06-18T00:06:00Z"),
]


def test_mid_plate_appearance_is_that_pa_before_state():
    st = GameClock(PLAYS).state_at("2025-06-18T00:01:30Z")
    assert st == {"inning": 1, "inning_half": "top", "outs": 1, "bases_state": "100",
                  "home_score": 0, "away_score": 0}


def test_between_pas_across_third_out_rolls_over_to_next_half():
    # 00:04:00 is after play 2 ended and before play 3 started
    st = GameClock(PLAYS).state_at("2025-06-18T00:04:00Z")
    assert st["inning_half"] == "bottom"
    assert st["outs"] == 0
    assert st["bases_state"] == "000"


def test_before_first_pitch_and_after_last_play_are_not_priced():
    gc = GameClock(PLAYS)
    assert gc.state_at("2025-06-17T23:59:00Z") is None
    assert gc.state_at("2025-06-18T00:07:00Z") is None


def test_plays_without_times_are_ignored():
    untimed = [dict(p, start_time=None, end_time=None) for p in PLAYS]
    assert GameClock(untimed).state_at("2025-06-18T00:01:30Z") is None
