"""
Tests for the NFL opener-spread deployment (session 119b).

Covers the live card's pure selection (nfl/scripts/daily_opener_card.py — the
deployment of the corrected backtest_opener rule) and the publisher's opener
row mapping + insert-once lock.
"""

import importlib.util
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.nfl_wind_publisher import NFL_OPENER_MODEL_ID, build_opener_rows

# Load the card module directly by path — `import scripts...`/`import models...`
# would collide between the platform packages and the nfl/ package's same-named
# directories.
_spec = importlib.util.spec_from_file_location(
    "nfl_daily_opener_card", ROOT / "nfl" / "scripts" / "daily_opener_card.py")
card = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(card)


def _sched():
    return pd.DataFrame([
        {"game_id": "2026_02_NYJ_MIA", "home_team": "MIA", "away_team": "NYJ",
         "matchup": "NYJ @ MIA", "kick_utc": "2026-09-20 17:00:00+00:00",
         "lead_days": 4.2},
        {"game_id": "2026_02_DEN_KC", "home_team": "KC", "away_team": "DEN",
         "matchup": "DEN @ KC", "kick_utc": "2026-09-20 20:25:00+00:00",
         "lead_days": 4.3},
    ])


def _row(book, side, point, price, home="MIA", away="NYJ", event="ev1"):
    return {"event_id": event, "home": home, "away": away, "book": book,
            "market": "spreads", "side": side, "price": price, "point": point}


def _frame(rows):
    return pd.DataFrame(rows)


def _both_sides(book, home_point, px_home, px_away, **kw):
    return [_row(book, "home", home_point, px_home, **kw),
            _row(book, "away", -home_point, px_away, **kw)]


class TestSelectOpenerBets:
    def test_positive_dev_bets_home_at_soft_number(self):
        # Pinnacle: MIA -3.5. Soft book hangs MIA -2.0 → dev(home) = +1.5 →
        # home is getting 1.5 more points than sharp → bet HOME at the soft line.
        rows = _both_sides("pinnacle", -3.5, -110, -110) + \
               _both_sides("betmgm", -2.0, -108, -112)
        bets = card.select_opener_bets(_frame(rows), _sched())
        assert len(bets) == 1
        b = bets.iloc[0]
        assert b.side == "home" and b.bet_team == "MIA"
        assert b.book == "betmgm" and b.price == -108
        assert b.side_line == -2.0 and b.soft_home_line == -2.0
        assert b.pin_home_line == -3.5 and b.dev == 1.5
        assert b.game_id == "2026_02_NYJ_MIA"
        assert b.model_prob == card.MODEL_PROB

    def test_negative_dev_bets_away_at_away_price(self):
        # Soft book hangs MIA -5.0 vs Pinnacle -3.5 → dev = -1.5 → away (NYJ)
        # is getting more points at the soft book → bet AWAY at +5.0.
        rows = _both_sides("pinnacle", -3.5, -110, -110) + \
               _both_sides("betmgm", -5.0, -115, -105)
        bets = card.select_opener_bets(_frame(rows), _sched())
        b = bets.iloc[0]
        assert b.side == "away" and b.bet_team == "NYJ"
        assert b.price == -105 and b.side_line == 5.0
        assert b.soft_home_line == -5.0

    def test_below_threshold_no_bet(self):
        rows = _both_sides("pinnacle", -3.5, -110, -110) + \
               _both_sides("betmgm", -3.0, -110, -110)   # |dev| = 0.5
        assert len(card.select_opener_bets(_frame(rows), _sched())) == 0

    def test_no_pinnacle_no_bets(self):
        rows = _both_sides("betmgm", -2.0, -110, -110) + \
               _both_sides("fanduel", -6.0, -110, -110)
        assert len(card.select_opener_bets(_frame(rows), _sched())) == 0

    def test_defective_and_exchange_books_excluded(self):
        rows = _both_sides("pinnacle", -3.5, -110, -110) + \
               _both_sides("betsson", -1.0, -110, -110) + \
               _both_sides("matchbook", -6.5, -102, -102)
        assert len(card.select_opener_bets(_frame(rows), _sched())) == 0

    def test_one_bet_per_game_largest_dev_wins(self):
        rows = _both_sides("pinnacle", -3.5, -110, -110) + \
               _both_sides("betmgm", -2.0, -110, -110) + \
               _both_sides("fanduel", -1.0, -105, -115)   # |dev| 2.5 > 1.5
        bets = card.select_opener_bets(_frame(rows), _sched())
        assert len(bets) == 1
        assert bets.iloc[0].book == "fanduel" and bets.iloc[0].dev == 2.5

    def test_game_not_in_window_schedule_skipped(self):
        rows = _both_sides("pinnacle", -3.5, -110, -110,
                           home="GB", away="DET", event="ev9") + \
               _both_sides("betmgm", -1.5, -110, -110,
                           home="GB", away="DET", event="ev9")
        assert len(card.select_opener_bets(_frame(rows), _sched())) == 0


def _card_row(**over):
    row = {
        "game_id": "2026_02_NYJ_MIA", "matchup": "NYJ @ MIA",
        "kick_utc": "2026-09-20 17:00:00+00:00", "lead_days": "4.2",
        "side": "away", "bet_team": "NYJ", "book": "betmgm", "price": "-105",
        "side_line": "5.0", "soft_home_line": "-5.0", "pin_home_line": "-3.5",
        "dev": "-1.5", "model_prob": "0.5818", "market_prob": "0.5122",
        "edge": "0.0696",
    }
    row.update(over)
    return row


class TestBuildOpenerRows:
    def test_maps_row_with_home_relative_scored_line(self):
        games, picks = build_opener_rows([_card_row()], bankroll=1000.0)
        assert len(games) == 1 and len(picks) == 1
        p = picks[0]
        assert p["model_id"] == NFL_OPENER_MODEL_ID
        assert p["game_id"] == "NFL_2026_02_NYJ_MIA"
        assert p["pick_side"] == "away"
        # scored_line is the HOME spread even on an away bet — the generic
        # spreads settle (margin + spread_home) grades both sides off it.
        assert p["scored_line"] == -5.0
        assert p["dk_odds"] == -105.0
        assert p["model_probability"] == 0.5818
        assert p["signal_type"] == "BET"
        assert p["kelly_fraction"] == 0.01 and p["recommended_bet"] == 10.0
        assert p["pick_label"] == "NYJ @ MIA — NYJ +5 (Opener -1.5 vs Pinnacle, MGM)"

    def test_bad_side_skipped(self):
        games, picks = build_opener_rows(
            [_card_row(side="over"), _card_row()], bankroll=1000.0)
        assert len(picks) == 1


class TestPublishOpenerInsertOnce:
    def test_existing_pick_locks_out_reinsert(self, monkeypatch, tmp_path):
        import csv as _csv
        import data.db as db
        from scripts import nfl_wind_publisher as pub

        executed = []
        class FakeConn:
            def execute(self, sql, params=None):
                executed.append((" ".join(sql.split()), params))
                class R:
                    def fetchone(self_r):
                        # Report an existing pick for every game → all locked.
                        return (1,) if "SELECT 1 FROM picks" in sql else None
                    def fetchall(self_r):
                        return []
                return R()
            def commit(self): executed.append(("COMMIT", None))
            def close(self): pass

        monkeypatch.setattr(db, "get_connection", lambda: FakeConn())
        monkeypatch.setattr(pub, "CARDS_DIR", tmp_path)
        row = _card_row()
        with open(tmp_path / "opener_card_2026-09-16.csv", "w", newline="") as fh:
            w = _csv.DictWriter(fh, fieldnames=list(row))
            w.writeheader(); w.writerow(row)

        written = pub.publish_opener("2026-09-16")
        assert written == 0
        sqls = [s for s, _ in executed]
        assert not any(s.startswith("INSERT INTO picks") for s in sqls)
        assert not any(s.startswith("DELETE") for s in sqls)  # opener never clears
        assert any(s.startswith("INSERT INTO games") for s in sqls)

    def test_no_card_is_a_noop(self, monkeypatch, tmp_path):
        import data.db as db
        from scripts import nfl_wind_publisher as pub
        monkeypatch.setattr(db, "get_connection",
                            lambda: (_ for _ in ()).throw(AssertionError("no DB touch")))
        monkeypatch.setattr(pub, "CARDS_DIR", tmp_path)
        assert pub.publish_opener("2026-09-16") == 0
