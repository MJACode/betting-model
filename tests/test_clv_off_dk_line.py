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
from tracking.clv_math import market_edge_clv, same_book_clv

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
            game_time="2026-10-04T01:00:00Z",
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
            set_part = s[s.index(" SET ") + 5:s.index(" WHERE ")]
            keys = [a.split("=")[0].strip() for a in set_part.split(",")] + ["pick_id"]
            assert len(keys) == len(params), s
            self.updates.append(dict(zip(keys, params)))
            return _Res([])
        raise AssertionError(f"unexpected statement: {s[:80]}")


def test_a_pick_draftkings_never_hung_closes_at_the_bet_book():
    """Primary CLV is Hard Rock's own raw close. Pinnacle is the market-edge
    column and is not written into closing_dk_odds."""
    conn = _Conn([PICK], QUOTES)
    assert pt._capture_clv(conn, "2026-10-03", "TS") == 1
    (u,) = conn.updates
    pct, pp = same_book_clv(-115.0, -135)
    m_pct, m_pp, method = market_edge_clv(-115.0, -166, [125], book="pinnacle")
    assert (u["clv_close_book"], u["closing_dk_odds"], u["clv_method"],
            u["clv_bet_book"]) == ("hardrockbet", -135, "standard_v2", "hardrockbet")
    assert (u["clv_pct"], u["clv_pp"]) == (pct, pp)
    assert pct > 0
    assert u["clv_beat_close"] is True
    assert u["pinnacle_close_odds"] == -166
    assert (u["market_clv_pct"], u["market_clv_pp"], u["market_clv_method"]) == (
        m_pct, m_pp, method)


def test_without_pinnacle_the_primary_is_still_the_bet_book():
    conn = _Conn([PICK], [q for q in QUOTES if q[0] != "pinnacle"])
    assert pt._capture_clv(conn, "2026-10-03", "TS") == 1
    (u,) = conn.updates
    pct, _ = same_book_clv(-115.0, -135)
    assert (u["clv_close_book"], u["closing_dk_odds"], u["clv_pct"],
            u["clv_bet_book"]) == ("hardrockbet", -135, pct, "hardrockbet")
    assert u["market_clv_pct"] is None
    assert u["pinnacle_close_odds"] is None


def test_a_row_that_carries_dk_odds_keeps_its_book_and_price():
    """The market-relative cards put the SOFT book's price in dk_odds and the
    book in the label suffix, with decision_odds NULL (nfl_prop_market 90/90,
    wnba_prop_market 23/23 measured 2026-10-08). They must still close at the
    label book and grade dk_odds, raw against that book's own close."""
    soft = {**PICK, "model_id": "nfl_prop_market", "dk_odds": -120.0, "decision_odds": None,
            "decision_book": None, "pick_label": "Brock Nelson Under 2.5 Shots on Goal (FD)"}
    quotes = [("fanduel", LOCK_TS, 2.5, 100, -120), ("fanduel", CLOSE_TS, 2.5, 110, -140),
              ("hardrockbet", CLOSE_TS, 2.5, -125, -135)]
    conn = _Conn([soft], quotes)
    assert pt._capture_clv(conn, "2026-10-03", "TS") == 1
    (u,) = conn.updates
    pct, _ = same_book_clv(-120.0, -140)
    assert (u["clv_close_book"], u["clv_bet_book"], u["clv_pct"],
            u["closing_dk_odds"]) == ("fanduel", "fanduel", pct, -140)
    assert u["pinnacle_close_odds"] is None


def test_the_backfill_queues_the_dates_of_those_picks():
    """Without this the 30 already-settled picks are never revisited: the
    backfill's date scan carried the same dk_odds filter."""
    text = Path(pt.__file__).read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(text))
              if isinstance(n, ast.FunctionDef) and n.name == "_backfill_clv")
    src = "\n".join(text.splitlines()[fn.lineno - 1:fn.end_lineno])
    assert "COALESCE(p.dk_odds, p.decision_odds) IS NOT NULL" in src
    assert "AND p.dk_odds IS NOT NULL" not in src
