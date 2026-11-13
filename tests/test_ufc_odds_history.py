"""The UFC odds history purchase: what it asks for, how it reads an answer,
and what it stores. No test here reaches the feed or a database."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from data.ingestors import ufc_odds_history as H

UTC = timezone.utc


def _t(s):
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


def test_the_daily_stage_asks_noon_utc_on_every_day_of_the_window():
    inst = H.daily_instants(date(2024, 2, 27), date(2024, 3, 1))
    assert inst == [_t("2024-02-27T12:00"), _t("2024-02-28T12:00"),
                    _t("2024-02-29T12:00"), _t("2024-03-01T12:00")]
    # the whole window is the 2,199 asks the purchase was quoted on
    assert len(H.daily_instants()) == 2199
    assert len(H.daily_instants()) * H.CALL_COST == 87_960


def test_a_card_gets_six_asks_timed_off_its_first_middle_and_last_fight():
    first, last = _t("2024-04-13T22:00"), _t("2024-04-14T03:00")
    got = H.card_instants({date(2024, 4, 13): [first, _t("2024-04-14T01:00"), last]})
    assert got == sorted([first - timedelta(hours=6), first - timedelta(hours=1),
                          first - timedelta(minutes=5), _t("2024-04-14T00:25"),
                          last - timedelta(hours=1), last - timedelta(minutes=5)])


def test_one_start_time_for_a_whole_card_collapses_to_three_asks():
    t = _t("2024-04-13T22:00")
    assert len(H.card_instants({date(2024, 4, 13): [t, t]})) == 3


def _index():
    return H.FightIndex([("UFC_2024-04-13_alex-pereira_jamahal-hill", "2024-04-13",
                          "Alex Pereira", "Jamahal Hill")])


def test_an_event_is_placed_on_our_fight_by_its_pair_within_two_days(monkeypatch):
    monkeypatch.setattr(H.config, "UFC_NAME_ALIASES", {"Jamahal Hill Jr.": "Jamahal Hill"})
    idx = _index()
    assert idx("Jamahal Hill", "Alex Pereira", _t("2024-04-14T03:00")) == \
        "UFC_2024-04-13_alex-pereira_jamahal-hill"
    assert idx("Jamahal Hill Jr.", "Alex Pereira", _t("2024-04-14T03:00")) == \
        "UFC_2024-04-13_alex-pereira_jamahal-hill"            # through the alias map
    assert idx("Jamahal Hill", "Alex Pereira", _t("2024-04-20T03:00")) is None   # a week off
    assert idx("Somebody Else", "Alex Pereira", _t("2024-04-14T03:00")) is None


def _body(ts, price_home=-150, line=2.5):
    return {"asked_at": ts, "timestamp": ts, "data": [
        {"id": "ev1", "commence_time": "2024-04-14T03:00:00Z",
         "home_team": "Alex Pereira", "away_team": "Jamahal Hill",
         "bookmakers": [
             {"key": "draftkings", "last_update": ts, "markets": [
                 {"key": "h2h", "last_update": ts, "outcomes": [
                     {"name": "Alex Pereira", "price": price_home},
                     {"name": "Jamahal Hill", "price": 125}]},
                 {"key": "totals", "last_update": ts, "outcomes": [
                     {"name": "Over", "price": -120, "point": line},
                     {"name": "Under", "price": 100, "point": line}]}]},
             {"key": "pinnacle", "markets": [
                 {"key": "h2h", "outcomes": [{"name": "Alex Pereira", "price": -140}]}]}]},
        {"id": "ev2", "commence_time": "2024-04-14T02:00:00Z",
         "home_team": "Pfl Guy", "away_team": "Other Guy",
         "bookmakers": [{"key": "fanduel", "markets": [
             {"key": "h2h", "outcomes": [{"name": "Pfl Guy", "price": -200},
                                         {"name": "Other Guy", "price": 160}]}]}]}]}


def test_a_snapshot_becomes_one_row_per_event_book_and_market():
    rows = H.quote_rows(_body("2024-04-10T11:55:00Z"), _index())
    got = {(r["event_id"], r["bookmaker"], r["market"]) for r in rows}
    # Pinnacle's one-sided h2h is dropped; the other promotion is kept, unplaced
    assert got == {("ev1", "draftkings", "h2h"), ("ev1", "draftkings", "totals"),
                   ("ev2", "fanduel", "h2h")}
    by = {(r["event_id"], r["market"]): r for r in rows}
    assert (by["ev1", "h2h"]["home_price"], by["ev1", "h2h"]["away_price"]) == (-150, 125)
    assert (by["ev1", "totals"]["total_line"], by["ev1", "totals"]["over_price"],
            by["ev1", "totals"]["under_price"]) == (2.5, -120, 100)
    assert by["ev1", "h2h"]["game_id"] == "UFC_2024-04-13_alex-pereira_jamahal-hill"
    assert by["ev2", "h2h"]["game_id"] is None
    assert all(r["source"] == H.SOURCE for r in rows)


def test_only_a_changed_price_or_line_is_kept():
    k, idx = H.ChangeKeeper(), _index()
    first = [r for r in H.quote_rows(_body("2024-04-10T11:55:00Z"), idx) if k.wanted(r)]
    same = [r for r in H.quote_rows(_body("2024-04-11T11:55:00Z"), idx) if k.wanted(r)]
    moved = [r for r in H.quote_rows(_body("2024-04-12T11:55:00Z", -170, 1.5), idx) if k.wanted(r)]
    assert len(first) == 3 and same == []
    assert {(r["market"]) for r in moved} == {"h2h", "totals"}


class _Conn:
    def __init__(self, held=()):
        self.held, self.many, self.pulls, self.commits = list(held), [], [], 0

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.startswith("SELECT asked_at"):
            return _Rows([(h,) for h in self.held])
        if s.startswith(f"INSERT INTO {H.PULLS}"):
            self.pulls.append(params)
        return _Rows([])

    def executemany(self, sql, rows):
        self.many.extend(rows)

    def commit(self):
        self.commits += 1


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


def test_store_writes_in_feed_time_order_and_skips_what_the_ledger_holds(tmp_path, monkeypatch):
    monkeypatch.setattr(H, "ensure_tables", lambda conn: None)
    for ts, stage, price in (("2024-04-12T11:55:00Z", "daily", -170),
                             ("2024-04-10T11:55:00Z", "daily", -150),
                             ("2024-04-11T11:55:00Z", "cards", -150)):
        H.write_spool(tmp_path, stage, H._utc(ts), {k: v for k, v in _body(ts, price).items()
                                                     if k != "asked_at"})
    # the 04-10 snapshot is already stored: it is not written again, but its
    # quotes still seed the change memory, so the unchanged 04-11 writes nothing
    # and 04-12 writes only DraftKings' moved moneyline
    conn = _Conn(held=[H._utc("2024-04-10T11:55:00Z")])
    stats = H.store(conn, tmp_path, _index())
    assert stats == {"snapshots": 3, "stored_snapshots": 2, "rows": 1, "already": 1}
    assert [p[0] for p in conn.pulls] == ["2024-04-11T11:55:00Z", "2024-04-12T11:55:00Z"]
    assert [(r[0], r[5], r[6], r[9]) for r in conn.many] == [("ev1", "draftkings", "h2h", -170)]


def test_the_tables_are_worker_only():
    from data.anon_readable import WORKER_ONLY_TABLES
    assert {H.TABLE, H.PULLS} <= set(WORKER_ONLY_TABLES)
