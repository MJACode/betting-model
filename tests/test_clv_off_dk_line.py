"""A pick priced at a line DraftKings never hung still gets its closing line value.

The NHL prop card (scripts/nhl_props_card.py) and the scorer's
_fallback_line_quote write such a pick with dk_odds NULL BY DESIGN and the bet
in decision_odds at decision_book. _capture_clv and _backfill_clv both filtered
on `p.dk_odds IS NOT NULL`, so every one was skipped in silence: 30 NHL prop
BETs on 2026-10-01..08, all at Hard Rock (22 shots on goal, 6 saves, 2 assists).

The quotes below are Brock Nelson Under 2.5 Shots on Goal, 2026-10-03, as
stored in player_prop_odds.
"""
from __future__ import annotations

import ast
import re
from datetime import datetime
from pathlib import Path

from tracking import paper_tracker as pt
from tracking.clv_math import price_clv_pct

GAME = "NHL_2026-10-03_STL_COL"
LOCK_TS, CLOSE_TS = "2026-10-03T04:17:53+00:00", "2026-10-04T00:00:58+00:00"
QUOTES = [  # (book, snapshot_at, line, over, under)
    ("hardrockbet", LOCK_TS, 2.5, -115, -115),
    ("hardrockbet", CLOSE_TS, 2.5, -125, -135),
    ("draftkings", CLOSE_TS, 2.5, 125, -165),
    ("pinnacle", CLOSE_TS, 2.5, 125, -166),
    ("pinnacle", "2026-10-04T01:09:00+00:00", 2.5, 300, -500),   # after puck drop: never the close
]
PICK = dict(pick_id=1, game_id=GAME, model_id="nhl_prop_shots_on_goal", pick_side="under",
            dk_odds=None, commence_time="2026-10-04T01:00:00Z",
            pick_label="Brock Nelson Under 2.5 Shots on Goal", scored_line=2.5,
            created_at="2026-10-03 04:18:06.856386+00", prop_market="player_shots_on_goal",
            clv_method=None, decision_odds=-115.0, decision_book="hardrockbet",
            game_date="2026-10-03", signal_type="BET", is_live=False, clv_captured_at=None)


def _ts(v) -> datetime:
    s = str(v).replace("Z", "+00:00")
    return datetime.fromisoformat(s + ":00" if re.search(r"[+-]\d\d$", s) else s)


class _Res:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _Conn:
    """Answers the three statements _capture_clv issues, from the lists above."""

    def __init__(self, picks, quotes, player="Brock Nelson", market="player_shots_on_goal"):
        self.picks, self.quotes, self.player, self.market = picks, quotes, player, market
        self.updates: list[dict] = []

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if s.startswith("SELECT p.pick_id"):
            cols = [c.strip().split(".")[-1] for c in s[7:s.index(" FROM picks")].split(",")]
            if "COALESCE(p.dk_odds, p.decision_odds) IS NOT NULL" in s:
                priced = lambda p: p["dk_odds"] is not None or p["decision_odds"] is not None
            elif "p.dk_odds IS NOT NULL" in s:
                priced = lambda p: p["dk_odds"] is not None
            else:
                raise AssertionError("capture no longer filters on a price")
            return _Res([tuple(p[c] for c in cols) for p in self.picks
                         if p["game_date"] == params[0] and priced(p)])
        if "FROM player_prop_odds" in s:
            game_id, player, market, book, bound = params
            rows = sorted((q for q in self.quotes if q[0] == book and _ts(q[1]) <= _ts(bound)
                           and (game_id, player, market) == (GAME, self.player, self.market)),
                          key=lambda q: _ts(q[1]), reverse=True)
            return _Res([(q[3], q[4], q[2]) for q in rows[:1]])
        if s.startswith("UPDATE picks"):
            keys = ("closing_dk_odds", "closing_line", "clv_pct", "line_clv_pts", "clv_beat_close",
                    "clv_captured_at", "clv_method", "clv_close_book", "pick_id")
            self.updates.append(dict(zip(keys, params)))
            return _Res([])
        raise AssertionError(f"unexpected statement: {s[:80]}")


def test_a_pick_at_a_line_draftkings_never_hung_is_closed_at_pinnacle():
    conn = _Conn([PICK], QUOTES)
    assert pt._capture_clv(conn, "2026-10-03", "TS") == 1
    (u,) = conn.updates
    # The bet is -115 at Hard Rock, de-vigged against Hard Rock's own lock
    # two-way; the close is Pinnacle's last pre-game quote at the same line.
    want, _ = price_clv_pct(-115.0, -166, [125], book="pinnacle",
                            bet_other_prices=[-115], bet_book="hardrockbet")
    assert (u["clv_close_book"], u["closing_dk_odds"], u["clv_method"]) == ("pinnacle", -166, "no_vig")
    assert u["clv_pct"] == want == 8.41
    assert u["clv_beat_close"] is True


def test_without_pinnacle_the_close_is_the_deciding_book_not_draftkings():
    conn = _Conn([PICK], [q for q in QUOTES if q[0] != "pinnacle"])
    assert pt._capture_clv(conn, "2026-10-03", "TS") == 1
    (u,) = conn.updates
    want, _ = price_clv_pct(-115.0, -135, [-125], book="hardrockbet",
                            bet_other_prices=[-115], bet_book="hardrockbet")
    assert (u["clv_close_book"], u["closing_dk_odds"]) == ("hardrockbet", -135)
    assert u["clv_pct"] == want


def test_a_row_that_carries_dk_odds_keeps_its_book_and_price():
    """The market-relative cards put the SOFT book's price in dk_odds and the
    book in the label suffix, with decision_odds NULL (nfl_prop_market 90/90,
    wnba_prop_market 23/23 measured 2026-10-08). They must still close at the
    label book and grade dk_odds."""
    soft = {**PICK, "model_id": "nfl_prop_market", "dk_odds": -120.0, "decision_odds": None,
            "decision_book": None, "pick_label": "Brock Nelson Under 2.5 Shots on Goal (FD)"}
    quotes = [("fanduel", LOCK_TS, 2.5, 100, -120), ("fanduel", CLOSE_TS, 2.5, 110, -140),
              ("hardrockbet", CLOSE_TS, 2.5, -125, -135)]
    conn = _Conn([soft], quotes)
    assert pt._capture_clv(conn, "2026-10-03", "TS") == 1
    (u,) = conn.updates
    want, _ = price_clv_pct(-120.0, -140, [110], book="fanduel",
                            bet_other_prices=[100], bet_book="fanduel")
    assert (u["clv_close_book"], u["clv_pct"]) == ("fanduel", want)


def test_the_backfill_queues_the_dates_of_those_picks():
    """Without this the 30 already-settled picks are never revisited: the
    backfill's date scan carried the same dk_odds filter."""
    text = Path(pt.__file__).read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(text))
              if isinstance(n, ast.FunctionDef) and n.name == "_backfill_clv")
    src = "\n".join(text.splitlines()[fn.lineno - 1:fn.end_lineno])
    assert "COALESCE(p.dk_odds, p.decision_odds) IS NOT NULL" in src
    assert "AND p.dk_odds IS NOT NULL" not in src
