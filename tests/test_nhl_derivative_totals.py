"""NHL derivative totals: the buyer stores every line, the grader pays the right side,
and nothing is registered while the walk-forward does not clear.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import config
from data.ingestors import nhl_derivative_odds_history as buyer
from models import nhl_derivative_totals as dt
from scripts import nhl_derivative_totals_card as card
from scripts import nhl_odds_history_backfill as game_lines

ROOT = Path(__file__).resolve().parents[1]


def _markets():
    return [
        {"key": "h2h", "outcomes": [{"name": "Boston Bruins", "price": -120}]},
        {"key": "team_totals", "outcomes": [
            {"name": "Over", "description": "Boston Bruins", "price": -115, "point": 3.5,
             "link": "o-bos", "sid": "s1"},
            {"name": "Under", "description": "Boston Bruins", "price": -105, "point": 3.5,
             "link": "u-bos", "sid": "s2"},
            {"name": "Over", "description": "Buffalo Sabres", "price": -110, "point": 2.5},
            {"name": "Under", "description": "Buffalo Sabres", "price": -110, "point": 2.5},
            {"name": "Over", "description": "Not A Real Team", "price": -110, "point": 4.5},
            {"name": "Under", "description": "Not A Real Team", "price": -110, "point": 4.5},
        ]},
        {"key": "alternate_totals", "outcomes": [
            {"name": "Over", "price": 120, "point": 5.5},
            {"name": "Under", "price": -140, "point": 5.5},
            {"name": "Over", "price": -150, "point": 6.5},
            {"name": "Under", "price": 130, "point": 6.5},
            {"name": "Over", "price": 180, "point": 7.5},
        ]},
        {"key": "totals_p1", "outcomes": [
            {"name": "Over", "price": -120, "point": 1.5},
            {"name": "Under", "price": 100, "point": 1.5},
        ]},
    ]


def test_parser_splits_team_totals_and_keeps_every_alternate_line():
    rows = buyer.parse_markets(_markets(), home="BUF", away="BOS")
    by_market = {}
    for r in rows:
        by_market.setdefault(r["market"], []).append(r)
    assert set(by_market) == {"team_totals_home", "team_totals_away", "alternate_totals", "totals_p1"}
    home = by_market["team_totals_home"]
    assert len(home) == 1 and home[0]["total_line"] == 2.5
    assert home[0]["over_price"] == -110 and home[0]["under_price"] == -110
    away = by_market["team_totals_away"][0]
    assert away["total_line"] == 3.5 and away["over_link"] == "o-bos"
    lines = sorted(r["total_line"] for r in by_market["alternate_totals"])
    assert lines == [5.5, 6.5, 7.5]
    one_sided = next(r for r in by_market["alternate_totals"] if r["total_line"] == 7.5)
    assert one_sided["over_price"] == 180 and one_sided["under_price"] is None
    assert by_market["totals_p1"][0]["total_line"] == 1.5
    assert all("Not A Real" not in str(r) for r in rows)


def test_snapshot_after_start_is_in_play():
    parsed = {"market": "totals_p1", "total_line": 1.5, "over_price": -110, "under_price": -110,
              "over_link": None, "under_link": None, "over_sid": None, "under_sid": None}
    start = datetime(2026, 1, 15, 23, 0, tzinfo=timezone.utc)
    late = buyer._blank_row("NHL_2026-01-15_BOS_BUF", "draftkings",
                            "2026-01-16T00:30:00Z", parsed, start)
    early = buyer._blank_row("NHL_2026-01-15_BOS_BUF", "draftkings",
                             "2026-01-15T22:00:00Z", parsed, start)
    assert late["snapshot_type"] == "in_play"
    assert early["snapshot_type"] == "open"
    assert late["source"] == "odds_api_nhl_totals_history"


def test_books_match_the_game_line_backfill():
    assert buyer.BOOKS == game_lines.BOOKS
    assert len(buyer.BOOKS) == 10
    assert buyer.MARKETS == ["team_totals", "alternate_totals", "totals_p1"]
    assert buyer.SOURCE == "odds_api_nhl_totals_history"
    assert not hasattr(buyer, "DEFAULT_CEILING")


def test_estimate_is_ten_credits_per_market_plus_the_event_list():
    assert buyer.estimate_credits(10, 2) == 10 * 30 + 2
    text = buyer.format_plan(2, 10, 4)
    assert "ESTIMATE (not measured)" in text
    assert "no credit ceiling" in text
    assert "150,000" not in text


class _Resp:
    def __init__(self, url):
        self.status_code = 200
        self._url = url

    def json(self):
        if self._url.endswith("/events"):
            return {"data": [{
                "id": "ev1", "away_team": "Boston Bruins", "home_team": "Buffalo Sabres",
            }]}
        return {"timestamp": "2026-01-15T22:00:00Z", "data": {"bookmakers": []}}


class _Meter:
    def __init__(self):
        self.spent = 0
        self.remaining = None
        self.calls = []

    def get(self, url, params):
        self.calls.append(url)
        self.spent += 1 if url.endswith("/events") else 30
        return _Resp(url)


def test_pull_buys_the_game_with_no_credit_stop():
    games = [{"game_id": "NHL_2026-01-15_BOS_BUF", "home": "BUF", "away": "BOS",
              "start": datetime(2026, 1, 15, 23, 7, tzinfo=timezone.utc)}]
    meter = _Meter()
    stats = buyer.pull_date(None, meter, "2026-01-15", games, apply=False)
    assert "stopped" not in stats
    assert stats["events"] == 1
    assert meter.calls[0] == f"{buyer.BASE}/events"
    assert any(u.endswith("/odds") for u in meter.calls)


def test_buyer_source_has_no_credit_ceiling():
    src = (ROOT / "data/ingestors/nhl_derivative_odds_history.py").read_text(encoding="utf-8")
    for banned in ("DEFAULT_CEILING", "max-credits", "room_for", "plan_credit_budget", "reserve-days"):
        assert banned not in src, banned


def test_apply_and_probe_without_a_key_return_before_any_call(monkeypatch, capsys):
    monkeypatch.setattr(buyer.config, "ODDS_API_KEY", "")

    def _no_conn(*_a, **_k):
        raise AssertionError("get_connection was called")

    def _no_http(*_a, **_k):
        raise AssertionError("requests.get was called")

    monkeypatch.setattr(buyer, "get_connection", _no_conn)
    monkeypatch.setattr(buyer.requests, "get", _no_http)
    for flag in ("--apply", "--probe"):
        argv = ["buyer", flag] if flag == "--apply" else ["buyer", "--probe", "2026-01-15"]
        monkeypatch.setattr(sys, "argv", argv)
        buyer.main()
        out = capsys.readouterr().out
        assert "ODDS_API_KEY is not set" in out
        assert "nothing spent" in out


def test_profit_pays_the_side_that_won():
    # 6 goals, line 5.5: the over wins, the under loses. -110 pays 100/110 units.
    over = dt.profit(6, 5.5, -110, "over")
    under = dt.profit(6, 5.5, -110, "under")
    assert over == pytest.approx(100 / 110)
    assert under == pytest.approx(-1.0)
    # The count under the line is the other way around.
    assert dt.profit(4, 5.5, -110, "under") == pytest.approx(100 / 110)
    assert dt.profit(4, 5.5, -110, "over") == pytest.approx(-1.0)
    # A landing on the line is a push, and a missing price is not a bet.
    assert dt.profit(5.5, 5.5, +100, "over") == 0
    assert dt.profit(5.5, 5.5, +100, "under") == 0
    assert np.isnan(dt.profit(6, 5.5, np.nan, "over"))


def test_a_whole_line_leaves_the_push_to_neither_side():
    """On a line of 3, exactly 3 goals wins for nobody. The under is P(count < 3)."""
    from scipy.stats import poisson
    mu = 3.1
    over = dt.p_over(mu, 3.0)
    under = dt.p_under(mu, 3.0)
    assert under == pytest.approx(poisson.cdf(2, mu))
    assert over + under == pytest.approx(1.0 - poisson.pmf(3, mu))
    assert over + under < 0.85                          # the push is about 22% here
    # Negative binomial: the same rule.
    assert dt.p_under(mu, 3.0, 0.2) + dt.p_over(mu, 3.0, 0.2) < 1.0
    # A half line has no push: the two are complements.
    assert dt.p_under(mu, 2.5) == pytest.approx(1.0 - dt.p_over(mu, 2.5))


def test_side_frame_returns_the_stake_on_a_push_in_the_expected_value():
    """EV = P(win) x payout - P(lose). The push is neither a win nor a loss."""
    from scipy.stats import poisson
    mu = 3.1
    q = pd.DataFrame({"game_id": ["G1", "G2"], "game_date": ["2026-01-01"] * 2, "season": [2026] * 2})
    # Line 3: over +105, under -125 (a coherent two-way quote). Line 2.5: -110 both ways.
    s = dt.side_frame(q, np.array([mu, mu]), np.array([3.0, 2.5]),
                      np.array([+105, -110]), np.array([-125, -110]), np.array([3.0, 3.0]))
    win_under, win_over = poisson.cdf(2, mu), poisson.sf(3, mu)
    whole_u = s[(s.side == "under") & (s.line == 3.0)].iloc[0]
    whole_o = s[(s.side == "over") & (s.line == 3.0)].iloc[0]
    assert whole_u.p == pytest.approx(win_under)
    assert whole_u.ev == pytest.approx(win_under * 0.8 - win_over)
    assert whole_o.ev == pytest.approx(win_over * 1.05 - win_under)
    assert whole_u.p_push == pytest.approx(poisson.pmf(3, mu))
    # The old rule (under = 1 - over, the push counted as a win) made this
    # under a +12% bet. Without the push it loses money.
    assert (1.0 - win_over) * 1.8 - 1.0 > 0.10
    assert whole_u.ev < 0
    # A half line is priced exactly as before.
    half_u = s[(s.side == "under") & (s.line == 2.5)].iloc[0]
    p = 1.0 - dt.p_over(mu, 2.5)
    assert half_u.ev == pytest.approx(p * (1 + 100 / 110) - 1.0)
    assert half_u.p_push == pytest.approx(0.0)
    # Graded, a landing on the whole line is a push for both sides.
    assert whole_u.profit == 0 and whole_o.profit == 0


def _clear_bets(n_per_season: int = 200, profit: float = 0.5) -> pd.DataFrame:
    rows = []
    for season, start in ((2024, "2023-10-10"), (2025, "2024-10-10")):
        for i in range(n_per_season):
            rows.append({
                "season": season,
                "game_date": (pd.Timestamp(start) + pd.Timedelta(days=i)).strftime("%Y-%m-%d"),
                "game_id": f"NHL_{season}_{i}",
                "profit": profit,
            })
    return pd.DataFrame(rows)


def test_publishable_accepts_a_record_clear_of_zero_and_rejects_the_flukes():
    good = _clear_bets()
    assert dt.publishable(good) is True

    one_season = good[good.season == 2024]
    assert len(one_season) >= 200
    assert dt.publishable(one_season) is False

    short = good.iloc[:100]
    assert dt.publishable(short) is False

    # Both seasons positive, both halves not: the first half loses.
    mixed = []
    for i in range(300):
        mixed.append({
            "season": 2024 if i % 2 == 0 else 2025,
            "game_date": (pd.Timestamp("2023-10-01") + pd.Timedelta(days=i)).strftime("%Y-%m-%d"),
            "game_id": f"m{i}",
            "profit": -1.0 if i < 150 else 2.0,
        })
    mixed = pd.DataFrame(mixed)
    assert mixed.groupby("season").profit.mean().gt(0).all()
    ordered = mixed.sort_values(["game_date", "game_id"])
    assert ordered.profit.iloc[:150].mean() < 0
    assert dt.publishable(mixed) is False


def test_publishable_rejects_an_interval_that_includes_zero():
    """36 winning days and 24 losing days. The mean is positive and both
    seasons and both halves are positive; the day bootstrap still reaches
    below zero, so the side is not publishable."""
    rows = []
    # Per season: 18 days at +10, 12 days at -9. Across 60 days the 2.5%
    # resample of a 60% win rate lands under zero (checked below, not assumed).
    day = 0
    for season, start in ((2024, "2023-10-01"), (2025, "2024-10-01")):
        for profit, n in ((10.0, 18), (-9.0, 12)):
            for _ in range(n):
                rows.append({
                    "season": season,
                    "game_date": (pd.Timestamp(start) + pd.Timedelta(days=day % 40)).strftime("%Y-%m-%d"),
                    "game_id": f"c{season}_{day}",
                    "profit": profit,
                })
                day += 1
    bets = pd.DataFrame(rows)
    # Spread the two seasons onto disjoint dates so a half split by row order
    # after sorting still contains both kinds of day. Rebuild dates in order.
    bets = bets.sort_values(["season", "profit"], ascending=[True, False]).reset_index(drop=True)
    bets["game_date"] = [(pd.Timestamp("2023-10-01") + pd.Timedelta(days=i)).strftime("%Y-%m-%d")
                         for i in range(len(bets))]
    bets["game_id"] = [f"c{i}" for i in range(len(bets))]
    assert bets.groupby("season").profit.mean().gt(0).all()
    ordered = bets.sort_values(["game_date", "game_id"])
    half = len(ordered) // 2
    assert ordered.profit.iloc[:half].mean() > 0
    assert ordered.profit.iloc[half:].mean() > 0
    lo, hi = dt.day_interval(ordered)
    assert lo < 0 < hi
    assert dt.publishable(ordered) is False


def test_neighbour_clears_fails_when_the_middle_cut_fails():
    good = _clear_bets()
    bad = good.iloc[:10]
    cuts = {
        0.08: good,
        0.10: bad,
        0.12: good,
    }
    assert dt.publishable(good) and not dt.publishable(bad)
    assert dt.neighbour_clears(cuts, 0.10) is False
    assert dt.neighbour_clears({0.08: good, 0.10: good, 0.12: good}, 0.10) is True


def test_a_teams_feature_does_not_include_that_games_goals():
    rows = []
    for i, gf in enumerate([2, 2, 2, 2, 2, 6]):
        date = f"2024-01-{i + 1:02d}"
        gid = f"NHL_{date}_BUF_BOS"
        rows.append({"nhl_game_id": gid, "game_id": gid, "team": "BOS", "opponent": "BUF",
                     "season": 2024, "game_date": date, "is_home": 1,
                     "goals_for": gf, "goals_against": 1, "shots_for": 30, "shots_against": 28})
        rows.append({"nhl_game_id": gid, "game_id": gid, "team": "BUF", "opponent": "BOS",
                     "season": 2024, "game_date": date, "is_home": 0,
                     "goals_for": 1, "goals_against": gf, "shots_for": 28, "shots_against": 30})
    frame = dt.build_team_frame(pd.DataFrame(rows))
    last = frame[(frame.team == "BOS") & (frame.goals_for == 6)].iloc[0]
    assert last.gf_l == pytest.approx(2.0)
    assert last.gf_l != 6


def test_card_writes_nothing_and_the_pipeline_does_not_call_it(capsys):
    assert dt.PUBLISHED == ()
    assert card.run() == 0
    assert "nothing cleared, not publishing" in capsys.readouterr().out
    pipeline = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    assert "nhl_derivative_totals" not in pipeline
    for model_id in ("nhl_team_total", "nhl_alternate_total", "nhl_p1_total"):
        assert model_id not in config.ACTION_THRESHOLDS
        assert model_id not in config.PAUSED_MODELS


def test_ledger_ddl_is_guarded():
    src = (ROOT / "data/ingestors/nhl_derivative_odds_history.py").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS nhl_derivative_odds_pulls" in src
    assert "lock_down(" in src


# ── the grader: what settles each market, and the Pinnacle table ─────────────

def _graded_game():
    """BOS at home beat TOR 3-2 in overtime: 2-2 after three, 1-0 in the first period."""
    from scripts import nhl_derivative_totals_backtest as bt
    games = pd.DataFrame([{"game_id": "NHL_2026-01-10_TOR_BOS", "season": 2026, "game_date": "2026-01-10",
                           "home_team": "BOS", "away_team": "TOR", "home_score": 3, "away_score": 2,
                           "commence_time": "2026-01-11T00:00:00Z"}])
    periods = pd.DataFrame([
        {"game_id": "NHL_2026-01-10_TOR_BOS", "season": 2026, "game_date": "2026-01-10", "home_p1": 1,
         "away_p1": 0, "home_p2": 0, "away_p2": 1, "home_p3": 1, "away_p3": 1, "source": "nhl_api_score"},
        # An older source for the same game, with a different first period, loses to the feed.
        {"game_id": "NHL_2026-01-10_TOR_BOS", "season": 2026, "game_date": "2026-01-10", "home_p1": 0,
         "away_p1": 0, "home_p2": 1, "away_p2": 1, "home_p3": 1, "away_p3": 1, "source": "sbr_archive_nhl"},
    ])
    return bt, bt.outcomes(periods, games)


def test_team_totals_settle_on_the_full_game_score_overtime_included():
    bt, games = _graded_game()
    assert "reg_home" not in games.columns and "reg_away" not in games.columns
    g = games.iloc[0]
    assert (g.total, g.p1_total) == (5, 1)
    px = pd.DataFrame({"market": ["team_totals_home", "team_totals_away", "totals_p1", "alternate_totals"]})
    for c in ("home_score", "away_score", "p1_total", "total"):
        px[c] = g[c]
    # BOS scored 2 in regulation and 3 in all. The book's 2.5 over on BOS wins.
    assert list(bt.settling_count(px)) == [3.0, 2.0, 1.0, 5.0]


def _quote(book, market, line, over, under, snap="2026-01-10T22:00:00Z"):
    return {"game_id": "NHL_2026-01-10_TOR_BOS", "market": market, "bookmaker": book, "total_line": line,
            "over_price": over, "under_price": under, "snapshot_at": snap}


def test_the_pinnacle_table_prices_a_bettable_book_off_pinnacle_at_the_same_number_and_snapshot():
    bt, games = _graded_game()
    prices = pd.DataFrame([
        _quote("pinnacle", "team_totals_home", 2.5, -120, +105),
        _quote("fanduel", "team_totals_home", 2.5, +110, -135),     # over at +110 against Pinnacle's ~0.53
        _quote("fanduel", "team_totals_home", 3.5, +200, -260),     # Pinnacle has no 3.5: not priced
        _quote("pinnacle", "totals_p1", 1.5, +120, -140, snap="2026-01-10T21:00:00Z"),
        _quote("draftkings", "totals_p1", 1.5, +130, -160),          # a different snapshot: not priced
        _quote("pinnacle", "alternate_totals", 6.5, +300, +300),     # implied sum 0.5: not a market
        _quote("draftkings", "alternate_totals", 6.5, +150, -180),
    ])
    px = bt.pregame(prices, games)
    s = bt.sharp_sides(px, ["fanduel", "draftkings"])
    assert set(zip(s.market, s.total_line)) == {("team_totals_home", 2.5)}
    over = s[s.side == "over"].iloc[0]
    io, iu = 120 / 220, 100 / 205
    assert over.pin == pytest.approx(io / (io + iu))
    assert over.ev == pytest.approx(over.pin * 2.10 - 1.0)
    assert over.ev > 0.02
    # Settled on the full game: BOS scored 3, so the over at 2.5 won 1.10 units.
    assert over.profit == pytest.approx(1.10)
    under = s[s.side == "under"].iloc[0]
    assert under.pin == pytest.approx(1.0 - over.pin) and under.profit == pytest.approx(-1.0)
    rows = bt.sharp_rows(s, ("over", "under"))
    assert [r["pin EV>="] for r in rows] == list(bt.SHARP_EV_CUTS)
    assert rows[0]["bets"] == 1                                 # one bet a game per market
