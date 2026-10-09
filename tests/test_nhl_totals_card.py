"""The NHL totals card: which games it prices, the row it writes, and that it
writes a game's bet once, under the model's own lock, and never again.

Rows follow the scorer's convention for a pick decided away from DraftKings
(scripts/nhl_props_card.py): the DraftKings columns hold DraftKings' own price
at the bet's number or NULL / 0.0, `decision_*` is the book the bet was taken
at, `line_book` names that book only when DraftKings did not hang the number,
and `best_*` is filled only when the bet is not at DraftKings.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import models.nhl_totals_market as mk
import scripts.nhl_totals_card as card
from models.market_relative import implied
from tracking.pick_integrity import pick_problems

NOW = datetime(2026, 10, 8, 18, 0, 0, tzinfo=timezone.utc)
GAME = "NHL_2026-10-08_PHI_OTT"
GAMES = {GAME: {"home": "OTT", "away": "PHI", "game_date": "2026-10-08",
                "commence_time": "2026-10-08T23:13:54Z"}}


class _SlateConn:
    def __init__(self, rows):
        self.rows = rows
        self.sql = []

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        return self

    def fetchall(self):
        return self.rows


def _iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


def test_started_games_are_not_on_the_slate():
    rows = [
        ("NHL_A", "OTT", "PHI", _iso(NOW - timedelta(seconds=1)), "2026-10-08"),
        ("NHL_B", "BOS", "UTA", _iso(NOW + timedelta(seconds=1)), "2026-10-08"),
        ("NHL_C", "VGK", "TOR", _iso(NOW + timedelta(hours=30)), "2026-10-09"),
    ]
    conn = _SlateConn(rows)
    games = card.slate(conn, NOW)
    assert set(games) == {"NHL_B", "NHL_C"}
    assert games["NHL_C"]["home"] == "VGK" and games["NHL_C"]["away"] == "TOR"
    sql = conn.sql[0][0]
    assert "sport = 'NHL'" in sql


def _bet(**kw):
    base = dict(
        game_id=GAME, side="under", book="betmgm", line=6.0, price=-105.0,
        fair=0.5257, ev=0.5257 * (1 + 100 / 105) - 1,
        sharp_over=104.0, sharp_under=-119.0,
        created_at="2026-10-08 01:00:07.2+00",
        soft_snapshot_at="2026-10-08T00:59:30Z",
        sharp_snapshot_at="2026-10-08T00:59:58Z",
        link="https://betmgm/under", dk_price=None, dk_link=None,
    )
    base.update(kw)
    return mk.NhlTotalBet(**base)


def test_row_when_draftkings_did_not_hang_the_number():
    rows = card.pick_rows([_bet()], GAMES, bankroll=10_000)
    assert len(rows) == 1
    r = rows[0]
    assert r["pick_label"] == "OTT vs PHI Under 6.0"
    assert r["model_id"] == "nhl_over_under" and r["sport"] == "NHL"
    assert r["pick_side"] == "under" and r["signal_type"] == "BET"
    assert r["dk_odds"] is None
    assert r["dk_implied_prob"] == 0.0
    assert r["edge"] == 0.0
    assert r["dk_bet_link"] is None
    assert r["line_book"] == "betmgm"
    assert r["decision_book"] == "betmgm"
    assert r["decision_odds"] == -105
    assert r["decision_implied_prob"] == pytest.approx(round(implied(-105), 4))
    assert r["decision_edge"] == pytest.approx(round(0.5257 - implied(-105), 4))
    assert r["best_book"] == "betmgm" and r["best_odds"] == -105
    assert r["best_bet_link"] == "https://betmgm/under"
    assert isinstance(r["scored_line"], float) and r["scored_line"] == 6.0
    assert r["model_probability"] == 0.5257
    assert r["game_date"] == "2026-10-08"
    assert r["game_time"] == "2026-10-08T23:13:54Z"
    assert r["kelly_fraction"] > 0
    assert pick_problems(r["pick_label"], r["pick_side"], r["scored_line"],
                         r["model_id"], "OTT", "PHI") == []


def _q(book, line, over, under, created="2026-10-08 01:00:07.2+00"):
    return {
        "game_id": GAME, "book": book, "created_at": created,
        "snapshot_at": "2026-10-08T00:59:58Z",
        "total_line": line, "over_price": over, "under_price": under,
        "over_link": f"https://{book}/over", "under_link": f"https://{book}/under",
    }


def test_row_when_draftkings_hung_the_number():
    # Pinnacle -125 / +108: no-vig over 0.5352. FanDuel -102 is EV +0.060.
    pin = _q("pinnacle", 6.5, -125, 108)
    dk = _q("draftkings", 6.5, -110, -110)
    fd = _q("fanduel", 6.5, -102, -118)
    bets, _ = mk.find_bets([pin, dk, fd])
    assert len(bets) == 1 and bets[0].book == "fanduel"
    assert bets[0].dk_price == -110.0
    r = card.pick_rows(bets, GAMES, bankroll=10_000)[0]
    assert r["dk_odds"] == -110
    assert r["dk_implied_prob"] == pytest.approx(round(implied(-110), 4))
    assert r["edge"] == pytest.approx(round(bets[0].fair - implied(-110), 4))
    assert r["dk_bet_link"] == "https://draftkings/over"
    assert r["line_book"] is None
    assert r["decision_book"] == "fanduel" and r["decision_odds"] == -102
    assert r["best_book"] == "fanduel" and r["best_odds"] == -102
    assert r["best_bet_link"] == "https://fanduel/over"
    assert r["pick_label"] == "OTT vs PHI Over 6.5"

    # DraftKings has the best price: the bet is at DraftKings, best_* empty.
    dk_best = _q("draftkings", 6.5, -102, -118)
    bets, _ = mk.find_bets([pin, dk_best, fd])
    assert len(bets) == 1 and bets[0].book == "draftkings"
    r = card.pick_rows(bets, GAMES, bankroll=10_000)[0]
    assert r["decision_book"] == "draftkings" and r["decision_odds"] == -102
    assert r["dk_odds"] == -102 and r["line_book"] is None
    for col in ("best_book", "best_odds", "best_implied_prob", "best_edge",
                "best_bet_link"):
        assert r[col] is None, col
    assert r["decision_odds"] is not None


def test_an_incoherent_draftkings_quote_is_not_the_reference_price():
    # DraftKings +105 / +100 sums to 0.988 implied: not a price (COHERENT). The
    # rule drops it as a candidate, so it must not fill dk_odds either. If it
    # did, Discord would headline DraftKings +105 while the bet, the app and
    # settlement are FanDuel +103.
    from tracking.discord_notifier import publish_price
    pin = _q("pinnacle", 6.5, -105, -105)       # no-vig 0.5 / 0.5
    dk = _q("draftkings", 6.5, 105, 100)
    fd = _q("fanduel", 6.5, 103, -125)          # over EV 0.5 x 2.03 - 1 = 0.015
    bets, diag = mk.find_bets([pin, dk, fd])
    assert diag["soft_incoherent"] == 1
    assert len(bets) == 1 and bets[0].book == "fanduel"
    assert bets[0].dk_price is None and bets[0].dk_link is None
    r = card.pick_rows(bets, GAMES, bankroll=10_000)[0]
    assert r["dk_odds"] is None and r["dk_bet_link"] is None
    assert r["line_book"] == "fanduel"
    assert r["decision_book"] == "fanduel" and r["decision_odds"] == 103
    assert publish_price(r)[0] == 103


def test_every_bet_is_med_however_large_the_edge():
    # Pinnacle 0.60 against BetMGM -105 is an edge of 8.8 points; the card
    # still writes MED, as the NHL prop cards do.
    r = card.pick_rows([_bet(fair=0.60, ev=0.60 * (1 + 100 / 105) - 1)],
                       GAMES, bankroll=10_000)
    assert len(r) == 1
    assert r[0]["decision_edge"] > 0.03
    assert r[0]["confidence_tier"] == "MED"
    assert card.pick_rows([_bet()], GAMES, bankroll=10_000)[0][
        "confidence_tier"] == "MED"


def test_the_step_is_a_choice_the_pipeline_accepts():
    # refresh_pass.sh and the 6am run call `run_pipeline.py --step
    # nhl-over-under`; without the choice, argparse rejects it and the model
    # writes nothing, with one WARN line in the worker log.
    from pathlib import Path
    rp = (Path(__file__).parent.parent / "run_pipeline.py").read_text(
        encoding="utf-8")
    choices = rp.split("choices=[", 1)[1].split("]", 1)[0]
    assert '"nhl-over-under"' in choices


def test_the_6am_run_prices_the_fetch_its_odds_step_just_stored():
    from pathlib import Path
    rp = (Path(__file__).parent.parent / "run_pipeline.py").read_text(
        encoding="utf-8")
    daily = rp.split("def run_daily_pipeline(", 1)[1].split("\ndef ", 1)[0]
    odds = daily.index('results["odds"] = step_odds(')
    card_at = daily.index("step_nhl_over_under(")
    props = daily.index("step_prop_odds(")
    assert odds < card_at < props


def test_a_mismatched_label_is_refused(monkeypatch):
    # The same bet is written with its own label, so the refusal below is the
    # label's doing, not the EV gate's.
    assert len(card.pick_rows([_bet()], GAMES, bankroll=10_000)) == 1
    monkeypatch.setattr(card, "_build_pick_label",
                        lambda *a, **k: "OTT vs PHI Over 6.0")
    assert card.pick_rows([_bet()], GAMES, bankroll=10_000) == []


class _LockConn:
    """Records every statement in order; a picks SELECT finds a BET when the
    game is in `existing`, and an INSERT adds it there."""

    def __init__(self, existing=()):
        self.existing = set(existing)
        self.statements = []
        self.inserted = []
        self.commits = 0
        self._found = None

    def execute(self, sql, params=None):
        self.statements.append((" ".join(sql.split()), params))
        if "FROM picks" in sql:
            self._found = (1,) if params[0] in self.existing else None
        return self

    def fetchone(self):
        return self._found

    def executemany(self, sql, rows):
        self.statements.append((" ".join(sql.split())[:20], None))
        for r in rows:
            self.inserted.append(r)
            self.existing.add(r["game_id"])

    def commit(self):
        self.commits += 1


def test_insert_once_under_the_model_lock():
    from scripts.nfl_wind_publisher import _model_lock_key

    rows = card.pick_rows([_bet()], GAMES, bankroll=10_000)
    conn = _LockConn()
    assert card.publish(conn, [dict(r) for r in rows]) == 1
    sqls = [s for s, _ in conn.statements]
    assert sqls[0].startswith("SET LOCAL lock_timeout")
    assert "pg_advisory_xact_lock" in sqls[1]
    assert conn.statements[1][1] == (_model_lock_key("nhl_over_under"),)
    assert sqls[2].startswith("SELECT 1 FROM picks")
    assert "signal_type = 'BET'" in sqls[2]
    # Any BET on the game counts: the other side, a VOIDed one, a settled one.
    assert "pick_side" not in sqls[2] and "condition_status" not in sqls[2]
    assert "result" not in sqls[2]
    assert sqls[3].startswith("INSERT INTO picks")
    assert conn.commits == 1
    # A second identical pass writes nothing.
    assert card.publish(conn, [dict(r) for r in rows]) == 0
    assert len(conn.inserted) == 1

    # An existing BET on the game, whatever its side, means no INSERT.
    other = _LockConn(existing={GAME})
    over = card.pick_rows([_bet(side="over", price=110.0, fair=0.4743 + 0.05,
                                 link="https://betmgm/over")],
                          GAMES, bankroll=10_000)
    assert card.publish(other, [dict(r) for r in over]) == 0
    assert other.inserted == []
    assert not any(s.startswith("INSERT") for s, _ in other.statements)
