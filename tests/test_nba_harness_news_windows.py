"""The seventh search's 5-minute injury-news purchase stays out of every other grade.

docs/nba_models_2026.md section 11: those fetches buy the whole slate at times no other
search planned on, so left in they would become many games' close and decision fetch and a
grade would depend on when the cache was refreshed. scripts.nba_game_harness.load leaves
them out unless asked (include_news_windows=True, which the seventh search's lab passes).
"""
from __future__ import annotations

import pandas as pd

from scripts import nba_game_harness as H


def _cache(tmp_path):
    tip = "2025-01-16T00:10:00+00:00"
    pd.DataFrame([{"game_id": "G1", "season": 2025, "game_date": "2025-01-15", "home_team": "PHI",
                   "away_team": "NYK", "home_score": 110.0, "away_score": 100.0,
                   "commence_time": tip}]).to_parquet(tmp_path / "nba_games.parquet")
    hourly_pull, news_pull = "2026-10-15 22:00:00+00", "2026-10-25 01:00:00+00"
    rows = []
    for created, snap, line in ((hourly_pull, "2025-01-15T22:58:00Z", -6.5),
                                (news_pull, "2025-01-15T23:35:30Z", -8.5)):
        rows.append({"game_id": "G1", "market": "spreads", "bookmaker": "pinnacle", "snapshot_type": "open",
                     "snapshot_at": snap, "source": "odds_api_historical", "created_at": created,
                     "home_price": -105.0, "away_price": -105.0, "spread_home": line, "total_line": None,
                     "over_price": None, "under_price": None})
    pd.DataFrame(rows).to_parquet(tmp_path / "nba_odds.parquet")
    pd.DataFrame([
        {"requested_at": pd.Timestamp("2025-01-15T23:00:00Z"), "pulled_at": pd.Timestamp(hourly_pull),
         "rows": 1, "why": "hourly"},
        {"requested_at": pd.Timestamp("2025-01-15T23:36:00Z"), "pulled_at": pd.Timestamp(news_pull),
         "rows": 1, "why": H.NEWS_WINDOW_WHY},
    ]).to_parquet(tmp_path / "nba_fetch_ledger.parquet")


def test_news_window_fetches_and_their_quotes_are_left_out_by_default(tmp_path):
    _cache(tmp_path)
    d = H.load(tmp_path)
    assert list(d.quotes["line"]) == [-6.5]                     # the news quote is not placed anywhere
    assert set(d.fetches["fetch_at"]) == {pd.Timestamp("2025-01-15T23:00:00Z")}
    close = H.pinnacle_close(d)
    assert list(close["close_line"]) == [-6.5]                  # the close is the hourly archive's


def test_the_seventh_search_reads_them_when_it_asks(tmp_path):
    _cache(tmp_path)
    d = H.load(tmp_path, include_news_windows=True)
    assert sorted(d.quotes["line"]) == [-8.5, -6.5]
    assert pd.Timestamp("2025-01-15T23:36:00Z") in set(d.fetches["fetch_at"])
