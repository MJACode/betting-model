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
        cheap = (_both_sides("pinnacle", -3.0, -110, -110)
                 + _both_sides("betmgm", -1.0, -105, -115))
        dear = (_both_sides("pinnacle", -3.0, -110, -110)
                + _both_sides("betmgm", -1.0, -115, -110))
        b_cheap = card.select_opener_bets(_frame(cheap), _sched()).iloc[0]
        b_dear = card.select_opener_bets(_frame(dear), _sched()).iloc[0]
        assert b_cheap.dev == b_dear.dev == 2.0
        assert b_cheap.model_prob == b_dear.model_prob
        assert b_cheap.edge > b_dear.edge
        assert b_cheap.edge_tier != b_dear.edge_tier
        # and the worse price is staked smaller, on the identical deviation
        assert b_cheap.units > b_dear.units

    def test_heavy_juice_removes_the_bet_entirely(self):
        # Beyond a point the juice does not just shrink the stake, it deletes
        # the bet. The old flat rule would still have put a full unit down.
        rows = (_both_sides("pinnacle", -3.0, -110, -110)
                + _both_sides("betmgm", -1.0, -160, -110))
        assert card.select_opener_bets(_frame(rows), _sched()).empty

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
        assert p["pick_label"].startswith(
            "NYJ @ MIA — NYJ +5 (Opener -1.5 vs Pinnacle, MGM)")
        assert p["pick_label"].endswith("u")

    def test_stake_scales_with_the_bet(self):
        # 89% of opener picks carry ~+1.6pp of edge and return -0.30%, while
        # the rare big deviations return +10 to +17%. A flat stake cannot tell
        # them apart. Validated out-of-sample: +9.68% sized vs +3.94% flat.
        def _row(dev, price, model_prob):
            return _card_row(dev=str(dev), price=str(price),
                             model_prob=str(model_prob))

        _, small = build_opener_rows([_row(1.0, -110, 0.5470)], bankroll=1000.0)
        _, large = build_opener_rows([_row(3.0, -110, 0.5987)], bankroll=1000.0)
        assert small[0]["kelly_fraction"] < large[0]["kelly_fraction"]

    def test_cap_scales_with_the_stake_scale(self):
        # The cap MUST rise with the scale. Left at 2u while the scale went to
        # x2.7, out-of-sample ROI fell from +9.52% to +7.58%, because the cap
        # flattens exactly the big-edge bets the sizing exists to find.
        from scripts.nfl_wind_publisher import (OPENER_MAX_UNITS,
                                                OPENER_STAKE_SCALE)
        assert OPENER_MAX_UNITS >= 2.0 * OPENER_STAKE_SCALE, (
            "cap must scale with OPENER_STAKE_SCALE or it strangles the sizing")
        _, huge = build_opener_rows(
            [_card_row(dev="9.0", price="-110", model_prob="0.7641")],
            bankroll=1000.0)
        assert huge[0]["kelly_fraction"] <= OPENER_MAX_UNITS * 0.01 + 1e-9

    def test_tiny_bets_are_skipped_not_floored(self):
        # A 0.5u FLOOR was considered and the data rejected it: out-of-sample
        # it added 132u of risk for -0.34u of profit (-0.26% on the marginal
        # money), because the bets that size tiny are the ones in the -0.30%
        # bucket. Skipping them instead gave MORE profit for LESS risk.
        _, dead = build_opener_rows(
            [_card_row(dev="1.0", price="-125", model_prob="0.5470")],
            bankroll=1000.0)
        assert dead == [], "a bet too small to want must be skipped, not floored"

    def test_publisher_uses_the_cards_stake_not_its_own(self):
        # One definition of the stake: models/opener_spread.stake_units. The
        # card computes it, prints it, and writes it to the CSV; the publisher
        # reads it. If the publisher ever recomputes and drifts, the number the
        # user was shown stops matching the number that was staked.
        row = _card_row(stake_pct="1.750")
        _, picks = build_opener_rows([row], bankroll=1000.0)
        assert picks[0]["kelly_fraction"] == 0.0175
        assert picks[0]["recommended_bet"] == 17.5

    def test_publisher_skips_a_zero_stake_from_the_card(self):
        # The card writes 0 for a bet too small to want. That must mean "no
        # bet", never "bet nothing" — a 0-stake row in the picks table would
        # show the user a pick they are not supposed to place.
        _, picks = build_opener_rows([_card_row(stake_pct="0.0")], bankroll=1000.0)
        assert picks == []

    def test_unit_appears_on_the_pick_label(self):
        # The stake has to be visible wherever the pick is read, not only in a
        # column somebody has to go looking for.
        _, picks = build_opener_rows([_card_row(stake_pct="1.470")], bankroll=1000.0)
        assert picks[0]["pick_label"].endswith("1.47u")

    def test_card_emits_the_stake_columns(self):
        rows = _both_sides("pinnacle", -3.5, -110, -110) +                _both_sides("betmgm", -1.0, -108, -112)
        bets = card.select_opener_bets(_frame(rows), _sched())
        assert "units" in bets.columns and "stake_pct" in bets.columns
        b = bets.iloc[0]
        assert b.units > 0
        assert abs(b.stake_pct - b.units * opener_model.UNIT_PCT * 100) < 1e-9

    def test_card_drops_bets_too_small_to_want(self):
        # dev 1.0 at -125: qualifies on the rule, but the juice leaves nothing.
        rows = _both_sides("pinnacle", -2.0, -110, -110) +                _both_sides("betmgm", -1.0, -125, -125)
        bets = card.select_opener_bets(_frame(rows), _sched())
        assert bets.empty

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


class TestBettableBooksOnly:
    """A pick must name a book the reader can actually walk up to.

    The rule used to take the largest deviation at any clean book, and the feed
    carries plenty of books nobody here holds. Measured on the live Week-1
    board (2026-09-06), the two biggest edges of the seven that qualified were
    at onexbet (+7.32pp) and betus (+5.92pp). mike: "no can't bet on these
    remove them". §1c makes such a pick permanent, so this filter is the only
    thing standing between an unbettable quote and the track record.
    """

    def test_unbettable_book_is_not_selected(self):
        # onexbet at |dev| 2.5 would win the "largest deviation" contest
        # outright. It must not appear at all.
        rows = _both_sides("pinnacle", -3.5, -110, -110) + \
               _both_sides("onexbet", -1.0, -105, -115)
        assert len(card.select_opener_bets(_frame(rows), _sched())) == 0

    def test_falls_through_to_the_best_BETTABLE_book(self):
        # THE ORDERING TRAP, and the reason the filter runs before the
        # deviation is computed rather than after. onexbet carries the biggest
        # deviation; a filter applied to the RESULT would pick onexbet, reject
        # it, and return nothing — silently losing the fanduel bet that was
        # always there.
        rows = _both_sides("pinnacle", -3.5, -110, -110) + \
               _both_sides("onexbet", -1.0, -105, -115) + \
               _both_sides("fanduel", -2.0, -108, -112)
        bets = card.select_opener_bets(_frame(rows), _sched())
        assert len(bets) == 1
        assert bets.iloc[0].book == "fanduel" and bets.iloc[0].dev == 1.5

    def test_pinnacle_survives_the_filter_as_the_reference(self):
        # Pinnacle is NOT bettable, but removing it would leave nothing to
        # measure against and the card would return empty for the wrong
        # reason — a silent failure that looks exactly like a quiet market.
        assert "pinnacle" not in opener_model._bettable_books()
        rows = _both_sides("pinnacle", -3.5, -110, -110) + \
               _both_sides("betmgm", -2.0, -108, -112)
        bets = card.select_opener_bets(_frame(rows), _sched())
        assert len(bets) == 1 and bets.iloc[0].pin_home_line == -3.5

    def test_evaluate_board_sees_the_same_books_as_the_selection(self):
        # If the audit trail counted a book the selection cannot take, the
        # history would read "qualifies" for bets that never appear.
        rows = _both_sides("pinnacle", -3.5, -110, -110) + \
               _both_sides("onexbet", -1.0, -105, -115)
        evals = opener_model.evaluate_board(_frame(rows), _sched())
        # Matched on the suffix: eval_row normalises to the platform's
        # `NFL_<season>_<week>_<away>_<home>` form, and pinning the exact
        # string here would make this test about the id format rather than
        # about which books the board is allowed to see.
        mia = [e for e in evals if str(e["game_id"]).endswith("2026_02_NYJ_MIA")][0]
        assert int(mia["qualifies"]) == 0
        assert "onexbet" not in str(mia.get("current_book") or "")
        # The soft side is empty because the only soft quote was unbettable —
        # that is a different state from "Pinnacle has not posted", and the
        # audit trail has to say which.
        assert mia["reason"] == "no clean soft book quoting"

    def test_env_override_is_read_at_call_time(self, monkeypatch):
        # Narrowed to ONE book while a WIDER deviation sits at another, so the
        # env var is the only thing that can produce this answer. Asserting
        # merely that an override ALLOWS a book would pass against the old
        # unfiltered code too, and prove nothing.
        monkeypatch.setenv("BETTABLE_BOOKS", "fanduel")
        rows = _both_sides("pinnacle", -3.5, -110, -110) + \
               _both_sides("onexbet", -1.0, -105, -115) + \
               _both_sides("fanduel", -2.0, -108, -112)
        bets = card.select_opener_bets(_frame(rows), _sched())
        assert len(bets) == 1
        assert bets.iloc[0].book == "fanduel" and bets.iloc[0].dev == 1.5

    def test_standalone_fallback_matches_the_platform_config(self):
        # The model carries a literal copy of the list for standalone runs
        # (backtests, one-off scripts) where the repo root is not on sys.path.
        # A copy that drifts is a copy that lies, so pin them together.
        import config as platform_config
        import importlib.util as _ilu
        _bspec = _ilu.spec_from_file_location(
            "nfl_books", ROOT / "nfl" / "data_ingest" / "books.py")
        books_mod = _ilu.module_from_spec(_bspec)
        _bspec.loader.exec_module(books_mod)
        fallback = {b.strip() for b in books_mod.BETTABLE_FALLBACK.split(",")}
        assert fallback == set(platform_config.BETTABLE_BOOKS)

    def test_no_unlicensed_book_hides_in_the_default(self):
        # The named offenders from the 2026-09-06 board, plus the rest of the
        # offshore group that was one qualifying deviation away from the same
        # problem.
        books = opener_model._bettable_books()
        for bad in ("onexbet", "betus", "coolbet", "gtbets", "lowvig",
                    "bovada", "matchbook"):
            assert bad not in books, bad


class TestFireWindow:
    """T-7 is gone; T-2 is not."""

    def test_game_beyond_T7_is_inside_the_fire_window(self, tmp_path, monkeypatch):
        # THE MEASURED CASE, tested where the window actually lives.
        # select_opener_bets never sees a lead time — load_window_schedule is
        # what decides which games reach it — so a test written against the
        # selection would have passed on the OLD code and proved nothing.
        #
        # On 2026-09-06 the Week-1 Sunday slate sat 172.5h out (7.19 days) with
        # Pinnacle posted and seven qualifying deviations, and the old bound
        # (LEAD_HI_DAYS = 7.0) watched them and fired nothing.
        from datetime import datetime, timedelta, timezone
        from zoneinfo import ZoneInfo
        et = ZoneInfo("America/New_York")
        now = datetime.now(timezone.utc)

        def _kick(delta_days):
            k = (now + timedelta(days=delta_days)).astimezone(et)
            return f"{k:%Y-%m-%d},{k:%H:%M}"

        d = tmp_path / "data"
        d.mkdir()
        (d / "games.csv").write_text(
            "season,week,gameday,gametime,away_team,home_team\n"
            f"2026,1,{_kick(7.19)},BUF,HOU\n"    # was excluded by T-7
            f"2026,1,{_kick(1.0)},NYJ,TEN\n"     # excluded by T-2, must STAY out
            f"2026,1,{_kick(4.0)},SF,LA\n",      # inside either way
            encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        # No hi_days argument on purpose: the DEFAULT is the thing that
        # changed. Passing 10.0 explicitly would have driven the old code to
        # the right answer too.
        teams = set(card.load_window_schedule().home_team)
        assert "HOU" in teams, "the 7.19-day game must now be fireable"
        assert "LA" in teams
        assert "TEN" not in teams, "the T-2 late bound must still exclude it"

    def test_early_bound_is_the_watch_horizon_and_late_bound_is_unchanged(self):
        # mike asked for the T-7 rule to go, not the T-2 one. Dropping both
        # would be a different model: inside two days the soft books have
        # corrected and the backtest says nothing about that region.
        assert opener_model.LEAD_LO_DAYS == 2.0
        assert opener_model.LEAD_HI_DAYS >= 10.0
