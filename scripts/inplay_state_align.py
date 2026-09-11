"""Which game state was on the field when a historical quote was served.

The model is trained on the state BEFORE a plate appearance
(`features.live_game_features._PLAY_COLS`: outs_before, bases_before, the
score before). A completed play's after-state can carry three outs, which
training clips to two and the model has never seen, so the aligner never
returns an after-state. It returns the before-state of:

  * the plate appearance in progress at T (started, not yet ended), or
  * the NEXT plate appearance when T falls between two -- whose before-state
    is exactly the state after the last one, including a half-inning rollover
    to zero outs and empty bases.

None before the first pitch or after the last play has ended, so a quote on
a game that is over (or on game two of a doubleheader filed under game one's
id) is not priced against a dead state.
"""
from __future__ import annotations

from bisect import bisect_right
from datetime import datetime, timezone


def _t(v) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


class GameClock:
    """plays: dicts with play_index, inning, half_inning, outs_before,
    bases_before, score_home_before, score_away_before, start_time, end_time,
    in play order. Plays without a start_time are dropped."""

    def __init__(self, plays: list[dict]):
        ps = [p for p in plays if p.get("start_time")]
        ps.sort(key=lambda p: p["play_index"])
        self.plays = ps
        self.starts = [_t(p["start_time"]) for p in ps]
        self.ends = [_t(p["end_time"]) if p.get("end_time") else None for p in ps]

    @staticmethod
    def _before(p: dict) -> dict:
        return {"inning": p["inning"], "inning_half": p["half_inning"],
                "outs": p["outs_before"], "bases_state": p["bases_before"],
                "home_score": p["score_home_before"],
                "away_score": p["score_away_before"]}

    def state_at(self, when) -> dict | None:
        if not self.plays:
            return None
        T = _t(when)
        k = bisect_right(self.starts, T) - 1
        if k < 0:
            return None                      # before first pitch
        end = self.ends[k]
        if end is None or T <= end:
            return self._before(self.plays[k])   # PA in progress
        if k + 1 < len(self.plays):
            return self._before(self.plays[k + 1])   # between PAs: next one's before-state
        return None                          # after the last play: game over
