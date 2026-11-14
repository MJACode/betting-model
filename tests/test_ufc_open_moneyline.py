"""The UFC opening-price moneyline model (models/ufc_open_moneyline.py), its
ratings (models/ufc_ratings.py) and its card (scripts/ufc_open_moneyline_card.py).
No test here reaches a database or the odds feed."""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

import pytest

import config
from models import ufc_open_moneyline as om
from models import ufc_ratings as R
from scripts import ufc_open_moneyline_card as card

UTC = timezone.utc


# ── the decision at one pull ────────────────────────────────────────────────

def test_the_pick_is_the_best_ev_across_books_and_only_a_cleared_one_bets():
    # Pinnacle even; the model leans A (xb > 0); FanDuel has the better A price
    pick, best = om.decide_pull((-110, -110), {"draftkings": (+100, -120),
                                                "fanduel": (+115, -135)}, 0.30, 0.06, -300)
    assert pick is not None and pick.book == "fanduel" and pick.side == "a"
    p = 1 / (1 + math.exp(-(om.logit(0.5) + 0.30)))
    assert pick.prob == pytest.approx(p)
    assert pick.ev == pytest.approx(p * 2.15 - 1)
    nobet, best = om.decide_pull((-110, -110), {"draftkings": (+100, -120)}, 0.0, 0.06, -300)
    assert nobet is None and best is not None and best.ev < 0.06


def test_a_side_below_the_price_floor_is_dropped_before_the_best_is_chosen():
    # A heavy favourite whose only edge is at -400: nothing above the floor clears
    pick, best = om.decide_pull((-380, +300), {"draftkings": (-350, +280)}, 1.5, 0.06, -300)
    assert pick is None and best is None
    pick, _ = om.decide_pull((-380, +300), {"draftkings": (-350, +280)}, 1.5, 0.06, -400)
    assert pick is not None and pick.side == "a" and pick.price == -350


def test_a_missing_input_counts_as_the_training_mean():
    art = {"features": ["d_elo", "d_age"], "mu": [10.0, 1.0], "sd": [20.0, 4.0], "b": [0.5, -0.2]}
    assert om.opinion(art, {"d_elo": 30.0, "d_age": math.nan}) == pytest.approx(0.5)
    assert om.opinion(art, {"d_elo": 10.0}) == 0.0


def test_the_committed_artifact_is_the_ratings_feature_list():
    art = om.load_artifact()
    assert art["model_id"] == om.MODEL_ID
    assert art["features"] == list(R.FEATURES)
    assert len(art["b"]) == len(art["mu"]) == len(art["sd"]) == len(R.FEATURES)
    assert art["min_lead_h"] == om.MIN_LEAD_H and art["ridge"] == om.RIDGE
    assert art["n_fights"] > 7000


# ── the ratings ─────────────────────────────────────────────────────────────

def _row(log_id, gid, d, fid, name, result, method="decision", rnd=3, t=300, sig=30, absd=20):
    return {"log_id": log_id, "fighter_id": fid, "fighter_name": name, "game_id": gid,
            "game_date": d, "result": result, "method": method, "end_round": rnd,
            "end_time_sec": t, "sig_strikes_landed": sig, "sig_strikes_absorbed": absd,
            "takedowns_landed": 1, "knockdowns": 0, "sub_attempts": 0}


def _log():
    return [
        _row(1, "g1", "2024-01-01", "x", "Zed Zulu", "win"),
        _row(2, "g1", "2024-01-01", "y", "Abe Able", "loss"),
        _row(3, "g2", "2024-06-01", "x", "Zed Zulu", "win", "ko_tko", 1, 60, sig=float("nan")),
        _row(4, "g2", "2024-06-01", "z", "Moe Mid", "loss", "ko_tko", 1, 60),
    ]


def test_a_fight_sees_only_the_fights_before_it_with_a_the_smaller_slug():
    seen = {}
    R.replay(_log(), {"x": {"reach_in": 74, "height_in": 72, "dob": "1990-01-01"}},
             on_fight=lambda gid, a, b, z: seen.__setitem__(gid, (a["fighter_name"], z)))
    a_name, z1 = seen["g1"]
    assert a_name == "Abe Able"                     # abe-able < zed-zulu
    assert z1["d_elo"] == 0.0 and z1["d_n"] == 0.0 and z1["d_debut"] == 0.0
    a_name, z2 = seen["g2"]
    assert a_name == "Moe Mid"                      # moe-mid < zed-zulu
    # Zed won his first fight: B (Zed) has one fight and a higher rating
    assert z2["d_n"] == -1.0 and z2["d_elo"] < 0 and z2["d_debut"] == 1.0
    assert math.isnan(z2["d_reach"])                # Moe has no profile


def test_a_missing_stat_is_skipped_as_pandas_skips_it():
    st = R.replay(_log(), {})
    zed = R.fighter_inputs(st["x"], None, date(2024, 12, 1))
    # the second fight's strikes are NaN: 30 strikes over 15 + 1 minutes
    assert zed["slpm"] == pytest.approx(30 / 16)
    assert zed["n"] == 2 and zed["win_rate"] == 1.0 and zed["fin_rate"] == 0.5


def test_a_fight_with_no_recorded_length_is_left_out_of_the_minutes():
    log = _log() + [_row(5, "g3", "2024-09-01", "x", "Zed Zulu", "win", t=float("nan"), sig=10),
                    _row(6, "g3", "2024-09-01", "w", "Wes West", "loss", t=float("nan"))]
    zed = R.fighter_inputs(R.replay(log, {})["x"], None, date(2024, 12, 1))
    # minutes 15 + 1 (the third fight's length is unknown); strikes 30 + 10
    assert zed["avg_mins"] == pytest.approx(8.0)
    assert zed["slpm"] == pytest.approx(40 / 16)


def test_the_elo_update_is_symmetric_and_shrinks_with_experience():
    st = R.replay(_log()[:2], {})
    assert st["x"].elo - 1500 == pytest.approx(1500 - st["y"].elo)
    assert st["x"].elo == pytest.approx(1500 + 64 * 0.5)


# ── the card ────────────────────────────────────────────────────────────────

class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class _Conn:
    def __init__(self, rows):
        self.rows, self.params = rows, None

    def execute(self, sql, params=None):
        self.params = params
        return _Rows(self.rows)


NOW = datetime(2026, 11, 13, 12, 25, tzinfo=UTC)


def test_one_fight_stored_under_two_ids_is_one_slate_entry():
    start = "2026-11-28T03:00:00+00:00"
    conn = _Conn([
        ("UFC_2026-11-27_alex-pereira_jamahal-hill", "2026-11-27", "Jamahal Hill", "Alex Pereira", start),
        ("UFC_2026-11-28_jamahal-hill_alex-pereira", "2026-11-28", "Alex Pereira", "Jamahal Hill", start),
        ("UFC_2026-11-10_a-b_c-d", "2026-11-10", "C D", "A B", "2026-11-10T03:00:00+00:00"),  # started
    ])
    s = card.slate(conn, NOW)
    assert list(s) == ["alex-pereira|jamahal-hill|2026-11-27"]
    assert set(s["alex-pereira|jamahal-hill|2026-11-27"]["rows"]) == {
        "UFC_2026-11-27_alex-pereira_jamahal-hill", "UFC_2026-11-28_jamahal-hill_alex-pereira"}


def _fight(days_out):
    start = NOW + timedelta(days=days_out)
    return {"rows": {"G1": {"game_id": "G1", "game_date": start.date().isoformat(),
                            "home": "Home Guy", "away": "Away Guy", "start": start}},
            "start": start}


def test_the_pull_pairs_pinnacle_with_books_fetched_within_ten_minutes_oriented_to_a():
    t = NOW - timedelta(minutes=9)
    rows = [("G1", "pinnacle", card._z(t), -150, 130, None, None),
            ("G1", "draftkings", card._z(t + timedelta(minutes=8)), -145, 125, "dkh", "dka"),
            ("G1", "fanduel", card._z(t - timedelta(minutes=20)), -140, 120, None, None),
            ("G1", "pinnacle", card._z(t - timedelta(hours=1)), -170, 150, None, None)]
    pull = card.load_pull(_Conn(rows), _fight(10), NOW, {"G1": False})   # A is the away fighter
    assert pull["pin"] == (130.0, -150.0)            # the latest Pinnacle quote, A first
    assert set(pull["books"]) == {"draftkings"}      # FanDuel's is 20 minutes off
    assert pull["books"]["draftkings"][1:5] == (125.0, -145.0, "dka", "dkh")


def test_no_fresh_pinnacle_quote_is_no_pull():
    rows = [("G1", "draftkings", card._z(NOW - timedelta(minutes=5)), -145, 125, None, None)]
    assert card.load_pull(_Conn(rows), _fight(10), NOW, {"G1": True}) is None


def test_a_pull_below_the_cut_decides_nothing_until_the_week_out_mark():
    pull = {"at": NOW, "pin": (-110.0, -110.0), "books": {"draftkings": (NOW, -105.0, -115.0, None, None, "G1")}}
    early = card.decide_fight("k", _fight(10), pull, 0.0, 0.06, -300, NOW)
    late = card.decide_fight("k", _fight(5), pull, 0.0, 0.06, -300, NOW)
    assert early.status == "below_cut" and early.status not in card.FINAL
    assert late.status == "window_closed" and late.status in card.FINAL
    assert card.decide_fight("k", _fight(10), None, 0.0, 0.06, -300, NOW).status == "no_pull"
    assert card.decide_fight("k", _fight(5), None, 0.0, 0.06, -300, NOW).status == "no_window"
    assert "no_pull" not in card.FINAL and "no_window" in card.FINAL
    bet = card.decide_fight("k", _fight(10), pull, 0.5, 0.06, -300, NOW)
    assert bet.status == "bets" and bet.status in card.FINAL


def test_only_the_noon_utc_run_decides_bets():
    assert card.bets_decided_at(datetime(2026, 11, 13, 12, 25, tzinfo=UTC))
    assert not card.bets_decided_at(datetime(2026, 11, 13, 11, 25, tzinfo=UTC))
    assert not card.bets_decided_at(datetime(2026, 11, 13, 13, 25, tzinfo=UTC))


def test_the_pick_names_the_row_s_home_or_away_fighter(monkeypatch):
    import models.honest_ev as he
    monkeypatch.setattr(he, "gate", lambda *a, **k: type("G", (), {"clears": True, "reason": None})())
    import models.scorer as sc
    monkeypatch.setattr(sc, "_pause_note", lambda m: None)
    pull = {"at": NOW, "pin": (-110.0, -110.0),
            "books": {"fanduel": (NOW, 115.0, -135.0, "fa", "fb", "G1")}}
    d = card.decide_fight("k", _fight(10), pull, 0.30, 0.06, -300, NOW)
    # A is the away fighter on this row: an A pick is the away side
    row, refused = card.pick_row(d, _fight(10), "G1", False, 1000.0, pull)
    assert refused is None and row["signal_type"] == "BET"
    assert row["pick_side"] == "away" and row["pick_label"] == "Away Guy ML"
    assert row["decision_book"] == "fanduel" and row["decision_odds"] == 115.0
    assert row["best_bet_link"] == "fa" and row["dk_odds"] is None and row["scored_line"] is None
    row, _ = card.pick_row(d, _fight(10), "G1", True, 1000.0, pull)
    assert row["pick_side"] == "home" and row["pick_label"] == "Home Guy ML"


def test_the_model_carries_its_own_cut_floor_and_settles_as_a_moneyline():
    from tracking.paper_tracker import _market_for_pick
    assert config.min_ev_for(om.MODEL_ID) == 0.06
    assert config.min_odds_for(om.MODEL_ID) == -300
    assert om.MODEL_ID in config.MODELS_ON_OWN_PROBABILITY
    assert config.SCORING_METHODS[om.MODEL_ID] == "rule"
    assert _market_for_pick(om.MODEL_ID) == "h2h"
    assert om.MODEL_ID not in config.PAUSED_MODELS


def test_the_card_is_scheduled_hourly_and_its_heartbeat_is_bounded():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "scheduler.py").read_text(encoding="utf-8")
    assert 'id="ufc_open_moneyline_card"' in src
    assert '"scripts.ufc_open_moneyline_card", "--publish"' in src
    from tracking.job_heartbeat import MAX_SILENCE
    assert MAX_SILENCE["ufc_open_moneyline_card"] == 150


def test_the_feed_s_placeholder_date_is_not_a_fight_to_bet():
    conn = _Conn([("UFC_2026-12-31_ilia-topuria_justin-gaethje", "2026-12-31", "Justin Gaethje",
                   "Ilia Topuria", "2026-12-31T05:00:00+00:00"),
                  ("UFC_2027-01-01_khamzat-chimaev_sean-strickland", "2027-01-01", "Sean Strickland",
                   "Khamzat Chimaev", "2027-01-01T03:00:00+00:00"),
                  ("UFC_2026-12-12_diego-lopes_charles-oliveira", "2026-12-12", "Charles Oliveira",
                   "Diego Lopes", "2026-12-13T04:00:00+00:00")])
    assert list(card.slate(conn, NOW)) == ["charles-oliveira|diego-lopes|2026-12-12"]


# ── settlement of a fight that did not happen ───────────────────────────────

class _SettleConn:
    """Answers the two reads of _settle_unfought_ufc_picks; records the update."""

    def __init__(self, picks, card):
        self.picks, self.card, self.updates = picks, card, []

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.startswith("SELECT p.pick_id"):
            return _Rows(self.picks)
        if s.startswith("SELECT fighter_name FROM ufc_fight_log"):
            return _Rows([(n,) for n in self.card])
        if s.startswith("UPDATE picks SET result = 'NO_ACTION'"):
            self.updates.append(params)
        return _Rows([])


PICK = (7, "Ilia Topuria ML", "2026-11-14", "Justin Gaethje", "Ilia Topuria")


def test_a_bet_on_a_fight_missing_from_its_logged_card_settles_no_action():
    from tracking.paper_tracker import _settle_unfought_ufc_picks
    conn = _SettleConn([PICK], ["Alex Pereira", "Jamahal Hill"])
    assert _settle_unfought_ufc_picks(conn, "2026-11-17", "2026-11-17T11:00:00Z") == 1
    assert conn.updates == [("2026-11-17T11:00:00Z", 7)]


def test_a_card_not_logged_yet_or_a_fighter_on_it_settles_nothing():
    from tracking.paper_tracker import _settle_unfought_ufc_picks
    # the card is not in the fight log yet
    conn = _SettleConn([PICK], [])
    assert _settle_unfought_ufc_picks(conn, "2026-11-17", "x") == 0 and conn.updates == []
    # one fighter is on the card under the log's spelling: the same bout, left
    # to the normal path (the anchor rule)
    conn = _SettleConn([PICK], ["Gaethje Justin", "Max Holloway"])
    assert _settle_unfought_ufc_picks(conn, "2026-11-17", "x") == 0 and conn.updates == []


@pytest.mark.parametrize("feed, ufcstats", [
    ("Sergey Pavlovich", "Sergei Pavlovich"), ("Joseph Pyfer", "Joe Pyfer"),
    ("Daniel Hooker", "Dan Hooker"), ("Charlie Radtke", "Charles Radtke"),
    ("Heili Alateng", "Alatengheili")])
def test_the_feed_spellings_the_card_could_not_rate_build_the_ufcstats_fight(feed, ufcstats):
    """2026-11-14: the card skipped these five veterans' fights as unrated,
    because the odds feed spells them otherwise. The odds ingest stores the
    alias as the fighter's name and builds the fight id from it, so the card
    rates him and the results ingest scores the same row."""
    from data.ingestors.odds_ingestor import _normalize_team
    from models.ufc_ratings import slugify
    assert _normalize_team(feed, "UFC") == ufcstats
    assert slugify(_normalize_team(feed, "UFC")) == slugify(ufcstats)


def test_a_fight_listed_before_its_alias_and_after_it_is_one_slate_entry():
    """The feed's spelling built the first id; once the alias exists the ingest
    writes new pulls under the ufcstats spelling. One fight, one decision."""
    assert config.UFC_NAME_ALIASES["Daniel Hooker"] == "Dan Hooker"
    start = "2026-11-22T03:00:00+00:00"
    conn = _Conn([
        ("UFC_2026-11-21_brian-ortega_daniel-hooker", "2026-11-21", "Daniel Hooker", "Brian Ortega", start),
        ("UFC_2026-11-21_brian-ortega_dan-hooker", "2026-11-21", "Dan Hooker", "Brian Ortega", start),
    ])
    s = card.slate(conn, NOW)
    assert list(s) == ["brian-ortega|dan-hooker|2026-11-21"]
    assert set(s["brian-ortega|dan-hooker|2026-11-21"]["rows"]) == {
        "UFC_2026-11-21_brian-ortega_daniel-hooker", "UFC_2026-11-21_brian-ortega_dan-hooker"}
