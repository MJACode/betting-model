"""The tennis match-winner card (scripts/tennis_moneyline_card.py) and its
settlement (tracking/paper_tracker._settle_tennis_picks)."""
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

import config
from models import tennis_moneyline_shop as ms
from scripts import tennis_moneyline_card as card

NOW = datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc)
KEY = "tennis_atp_finals"


def _stand(listed, quotes):
    rows = [{"sport_key": KEY, "event_id": "e1", "commence_time": listed,
             "home_name": "Jannik Sinner", "away_name": "Carlos Alcaraz", "bookmaker": b,
             "snapshot_ts": pd.Timestamp(NOW) - pd.Timedelta(minutes=5),
             "home_price": h, "away_price": a, "listed": pd.Timestamp(listed)}
            for b, h, a in quotes]
    return pd.DataFrame(rows)


LINK = {"comp_id": "c1", "home_is_p1": True, "status": "STATUS_SCHEDULED"}


def test_a_match_is_due_from_35_minutes_before_its_listed_start_until_it():
    for minutes, due in ((36, False), (35, True), (5, True), (0, False), (-10, False)):
        s = _stand(pd.Timestamp(NOW) + pd.Timedelta(minutes=minutes), [("pinnacle", -150, 135)])
        assert (card.due_events(s, NOW) == ["e1"]) is due, minutes


def test_the_decision_is_the_models_and_names_the_book_and_side():
    s = _stand(pd.Timestamp(NOW) + pd.Timedelta(minutes=30),
               [("pinnacle", -150, 135), ("fanduel", -160, 150), ("bovada", -150, 170)])
    d = card.decide_event(s, LINK)
    c = ms.decide([ms.Quote("fanduel", -160, 150), ms.Quote("bovada", -150, 170)],
                  ms.Quote("pinnacle", -150, 135), KEY)
    assert (d["book"], d["side"], d["price"]) == (c.book, c.side, c.price) == ("fanduel", "b", 150)
    assert d["signal"] == ("BET" if c.bet else "NONE")
    assert d["game_id"] == "ATP_2026-11-14_carlos-alcaraz_jannik-sinner"


def test_no_espn_match_or_a_started_one_is_a_skip_and_not_a_decision():
    s = _stand(pd.Timestamp(NOW) + pd.Timedelta(minutes=30),
               [("pinnacle", -150, 135), ("fanduel", -160, 150)])
    assert card.decide_event(s, None)["signal"] == "SKIP"
    started = {**LINK, "status": "STATUS_IN_PROGRESS"}
    assert card.decide_event(s, started)["signal"] == "SKIP"
    assert card.decide_event(s.iloc[1:], LINK)["detail"] == "no_pinnacle_price"


def test_the_pick_row_is_labelled_for_its_player_and_gated_on_the_rules_ev():
    s = _stand(pd.Timestamp(NOW) + pd.Timedelta(minutes=30),
               [("pinnacle", -150, 135), ("draftkings", -160, 147)])
    d = card.decide_event(s, LINK)
    assert d["signal"] == "BET" and d["book"] == "draftkings"
    row, why = card.pick_row(d, 1000.0)
    assert why is None and row["signal_type"] == "BET"
    assert row["pick_label"] == "Carlos Alcaraz ML" and row["pick_side"] == "away"
    assert row["model_id"] == "atp_moneyline_shop" and row["sport"] == "ATP"
    assert row["decision_book"] == "draftkings" and row["decision_odds"] == 147
    # The retirement term carries this bet past the floor: the raw price alone
    # is under it, so a gate on Pinnacle's chance alone would refuse it.
    raw_ev = d["p_ref"] * 2.47 - 1
    assert raw_ev < config.min_ev_for("atp_moneyline_shop") <= d["ev"]


def test_a_price_below_the_floor_is_refused_as_a_bet():
    d = {"signal": "BET", "tour": "WTA", "price": -600, "ev": 0.03, "side": "a",
         "home": "Aryna Sabalenka", "away": "Elina Svitolina", "p_ref": 0.86, "dk_price": None,
         "game_id": "g", "game_date": "2026-11-14", "listed_start": "x", "book": "fanduel"}
    row, why = card.pick_row(d, 1000.0)
    assert row["signal_type"] == "NONE" and why.startswith("below_price_floor")


def test_the_card_is_scheduled_every_ten_minutes_and_its_heartbeat_is_bounded():
    import scheduler
    from tracking.job_heartbeat import MAX_SILENCE
    assert callable(scheduler.run_tennis_moneyline_card)
    assert MAX_SILENCE["tennis_moneyline_card"] == 40


def test_the_ledger_is_worker_only():
    from data.anon_readable import WORKER_ONLY_TABLES
    assert "tennis_moneyline_decisions" in WORKER_ONLY_TABLES


# ── settlement ────────────────────────────────────────────────────────────────

class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class _SettleConn:
    def __init__(self, picks):
        self.picks, self.updates = picks, []

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.startswith("SELECT 1 FROM information_schema.tables"):
            return _Rows([(1,)])
        if s.startswith("SELECT p.pick_id"):
            return _Rows(self.picks)
        if s.startswith("UPDATE picks"):
            self.updates.append(params)
        return _Rows([])


def _pick(book, side="away", status="STATUS_RETIRED", g1=(6, 2), g2=(3, 0), p1w=True):
    # ESPN p1 is the feed's home player; the away player (p2) retired at 3-6 0-2.
    return (11, side, "Carlos Alcaraz ML", book, -110, 10.0, True,
            status, 3, p1w, not p1w, list(g1), list(g2), "g1")


@pytest.mark.parametrize("book,result", [
    ("draftkings", "NO_ACTION"),     # a bet on the retiring player is void
    ("fanduel", "LOSS"),             # one set played: the retiring player loses
    ("betmgm", "LOSS"),
    ("williamhill_us", "NO_ACTION"),  # every bet void on a retirement
])
def test_a_bet_on_the_retiring_player_settles_at_its_books_rule(book, result):
    from tracking.paper_tracker import _settle_tennis_picks
    conn = _SettleConn([_pick(book)])
    _settle_tennis_picks(conn, "2026-11-14", "t")
    assert conn.updates[0][0] == result


@pytest.mark.parametrize("book,result", [
    ("draftkings", "WIN"),           # the player who advances is paid
    ("fanduel", "WIN"),
    ("williamhill_us", "NO_ACTION"),
])
def test_a_bet_on_the_player_who_advances_after_a_retirement(book, result):
    from tracking.paper_tracker import _settle_tennis_picks
    conn = _SettleConn([_pick(book, side="home")])
    _settle_tennis_picks(conn, "2026-11-14", "t")
    assert conn.updates[0][0] == result


def test_a_completed_match_and_a_walkover_and_a_cancellation():
    from tracking.paper_tracker import _settle_tennis_picks
    done = _pick("draftkings", side="home", status="STATUS_FINAL", g1=(6, 6), g2=(3, 4))
    conn = _SettleConn([done])
    _settle_tennis_picks(conn, "2026-11-14", "t")
    assert conn.updates[0][0] == "WIN" and conn.updates[0][1] == pytest.approx(100 * 100 / 110, abs=0.01)
    for status in ("STATUS_WALKOVER", "STATUS_CANCELED"):
        conn = _SettleConn([_pick("fanduel", status=status, g1=(), g2=())])
        _settle_tennis_picks(conn, "2026-11-14", "t")
        assert conn.updates[0][0] == "NO_ACTION", status


def test_a_retirement_before_the_first_set_is_complete_is_void_everywhere():
    from tracking.paper_tracker import _settle_tennis_picks
    for book in ("fanduel", "draftkings", "betmgm"):
        conn = _SettleConn([_pick(book, g1=(3,), g2=(2,))])
        _settle_tennis_picks(conn, "2026-11-14", "t")
        assert conn.updates[0][0] == "NO_ACTION", book
