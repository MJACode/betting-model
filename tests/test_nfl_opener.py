"""
Tests for the NFL opener-spread deployment (session 119b).

Covers the opener MODEL (nfl/models/opener_spread.py — the rule, the per-bet
win probability and the selection), the live card that deploys it
(nfl/scripts/daily_opener_card.py), and the publisher's opener row mapping +
insert-once lock.
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

# The model itself, loaded independently of the card, so the split is covered
# on both sides rather than only through the card's re-exports.
_mspec = importlib.util.spec_from_file_location(
    "nfl_opener_spread_model", ROOT / "nfl" / "models" / "opener_spread.py")
opener_model = importlib.util.module_from_spec(_mspec)
_mspec.loader.exec_module(opener_model)


class TestModelCardSplit:
    """The card is plumbing; the rule lives in the model. Keep them agreeing."""

    def test_card_delegates_to_the_model_file(self):
        # Identity comparison would be wrong: the test execs the model a second
        # time, so the objects differ even when the source is shared. What
        # matters is that the card's functions are DEFINED IN the model file
        # rather than copied back into the card.
        model_file = str((ROOT / "nfl" / "models" / "opener_spread.py").resolve())
        for fn in (card.select_opener_bets, card.model_prob_for_dev,
                   card.edge_tier, card.american_to_prob):
            assert Path(fn.__code__.co_filename).resolve() == Path(model_file), fn
        assert card.DEV_WIN_PROB == opener_model.DEV_WIN_PROB
        assert card.DEPLOY_THRESHOLD == opener_model.DEPLOY_THRESHOLD
        assert card.EDGE_TIERS == opener_model.EDGE_TIERS

    def test_model_stands_alone(self):
        # Importable and usable without the card, which is the point of the split.
        assert opener_model.model_prob_for_dev(1.0) == 0.5470
        assert opener_model.edge_tier(0.06) == "LARGE"
        assert "pinnacle" == opener_model.REFERENCE

    def test_model_loads_with_the_platform_models_package_shadowing_it(self):
        # The failure this guards: `from models.opener_spread import ...` picks
        # up the platform's models package and raises. If someone "tidies" the
        # card's path loader into a bare import, this is what breaks.
        import models as platform_models
        assert "betting-model" in str(Path(platform_models.__file__).parent)
        assert not hasattr(platform_models, "opener_spread")
        assert opener_model.model_prob_for_dev(2.0) == 0.5557


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
        # Per-bet probability now scales with the deviation (was a flat
        # card.MODEL_PROB for every bet until 2026-08-22).
        assert b.model_prob == round(card.model_prob_for_dev(1.5), 4)
        assert b.edge_tier in ("SMALL", "MEDIUM", "LARGE")

    def test_model_prob_scales_with_deviation(self):
        # The whole point of the 2026-08-22 change: a bigger deviation is worth
        # more. A flat probability cannot express this.
        small = card.model_prob_for_dev(1.0)
        big = card.model_prob_for_dev(3.0)
        assert small < big, (small, big)
        # Monotone non-decreasing across the tabulated range.
        seq = [card.model_prob_for_dev(d / 4) for d in range(4, 33)]
        assert all(a <= b for a, b in zip(seq, seq[1:])), seq
        # Clamped outside the fitted range rather than extrapolated.
        assert card.model_prob_for_dev(0.25) == card.model_prob_for_dev(1.0)
        assert card.model_prob_for_dev(50.0) == card.model_prob_for_dev(8.0)
        # Raw |dev| must NOT be used directly: the shrink to Pinnacle's close
        # is what keeps the pooled probability at the validated rate.
        assert card.model_prob_for_dev(1.0) < card.POOLED_MODEL_PROB
        # Six-season calibration: still above the -110 breakeven floor the
        # platform gates on (0.52), but well below the old flat 0.5818.
        assert 0.52 < card.model_prob_for_dev(1.0) < card.POOLED_MODEL_PROB

    def test_edge_tier_boundaries(self):
        assert card.edge_tier(0.029) == "SMALL"
        assert card.edge_tier(0.030) == "MEDIUM"
        assert card.edge_tier(0.054) == "MEDIUM"
        assert card.edge_tier(0.055) == "LARGE"
        assert card.edge_tier(-0.01) == "SMALL"

    def test_juice_can_flip_the_tier_without_the_deviation_moving(self):
        # Same 2.0-point deviation, different price: the tier has to move,
        # because the edge is measured against what the book actually quotes.
        cheap = _both_sides("pinnacle", -3.0, -110, -110) +                 _both_sides("betmgm", -1.0, -105, -115)
        dear = _both_sides("pinnacle", -3.0, -110, -110) +                _both_sides("betmgm", -1.0, -140, -110)
        b_cheap = card.select_opener_bets(_frame(cheap), _sched()).iloc[0]
        b_dear = card.select_opener_bets(_frame(dear), _sched()).iloc[0]
        assert b_cheap.dev == b_dear.dev == 2.0
        assert b_cheap.model_prob == b_dear.model_prob
        assert b_cheap.edge > b_dear.edge
        assert b_cheap.edge_tier != b_dear.edge_tier

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
        # Kelly-proportional since 2026-08-23 (was a flat 1u). This row is a
        # strong bet — 0.5818 at -105 — so it stakes ABOVE one unit.
        assert p["kelly_fraction"] > 0.01
        assert p["recommended_bet"] == round(p["kelly_fraction"] * 1000, 2)
        assert p["pick_label"] == "NYJ @ MIA — NYJ +5 (Opener -1.5 vs Pinnacle, MGM)"

    def test_stake_scales_with_the_bet_and_floors_at_zero(self):
        # The whole point of leaving flat staking: 89% of opener picks carry
        # ~+1.6pp of edge and return -0.30%, while the rare big deviations
        # return +10 to +17%. A flat stake cannot tell them apart.
        def _row(dev, price, model_prob):
            return _card_row(dev=str(dev), price=str(price),
                             model_prob=str(model_prob))

        _, small = build_opener_rows([_row(1.0, -110, 0.5470)], bankroll=1000.0)
        _, large = build_opener_rows([_row(4.5, -110, 0.6408)], bankroll=1000.0)
        assert small[0]["kelly_fraction"] < large[0]["kelly_fraction"]

        # Capped at 2 units however good it looks.
        assert large[0]["kelly_fraction"] <= 0.02 + 1e-9

        # And a quote whose juice has eaten the edge stakes NOTHING, where the
        # old flat rule would still have put a full unit down.
        _, dead = build_opener_rows([_row(1.0, -160, 0.5470)], bankroll=1000.0)
        assert dead[0]["kelly_fraction"] == 0.0
        assert dead[0]["recommended_bet"] == 0.0

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
