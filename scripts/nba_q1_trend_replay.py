"""Replay the graded cell through the live model's own code (models/nba_q1_trend.decide).

The eighth NBA search graded 88 bets (docs/nba_models_2026.md section 12: Q1A, L5to10, the spread check, k >= 2).
This runs models.nba_q1_trend.decide on the same archive, season by season, with the same quotes, decision times,
numbers and first-quarter scores the lab read (scripts.nba_game5.load_real, as scripts/nba_game8_q1_trends.prepare),
and compares every bet with the artifact's copy of the graded ones: game, side, book, line and price. A difference
is printed and the run exits 1, so the live model cannot drift from the graded rule unnoticed.

Reads the research cache (NBA_RESEARCH_CACHE, a cache of Supabase) and the artifact; no database, no API.

    NBA_RESEARCH_CACHE=... PYTHONPATH=. python -m scripts.nba_q1_trend_replay
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import models.nba_q1_trend as q1  # noqa: E402
from scripts import nba_game5 as G5  # noqa: E402
from scripts import nba_game8_q1_trends as G8  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402

FLOOR = -200.0
# The deciding books the lab graded with (2026-10-28): betPARX was one of them and is not in
# config.BEST_LINE_BOOKMAKERS today. The exact check runs on these; the live books are reported beside it.
GRADED_BOOKS = ("draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics", "betrivers", "hardrockbet",
                "betparx")


def replay(cache: Path, books=GRADED_BOOKS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(the replay's bets, the graded bets), one row per game."""
    real = G5.load_real(cache, True)
    games_p, pe, graded = real["games_p"], real["pe"], real["graded"]
    art = q1.load_artifact()
    times = H.per_event_times(pe, q1.POINT)
    numbers = G8.game_numbers(q1.visible(pe, times))
    gp = games_p[games_p["season"].isin(graded)]
    tg = G8.team_games(gp, numbers)
    decided = gp[gp["game_id"].isin(set(times["game_id"]))]
    rows = []
    for s in graded:
        tgt = decided[decided["season"] == s][["game_id", "season", "game_date", "home_team", "away_team"]]
        bets, _, diag = q1.decide(tgt, pe[pe["season"] == s], tg, times, art, books=books, min_odds=FLOOR,
                                  bucket_uplift=0.0)
        print(f"season {s}: {diag}")
        rows += [{"game_id": b.game_id, "side": b.side, "book": b.book, "line": b.line, "price": b.price}
                 for b in bets]
    got = pd.DataFrame(rows, columns=["game_id", "side", "book", "line", "price"])
    want = pd.DataFrame(art["graded_bets"], columns=["game_id", "side", "book", "line", "price", "result"])
    return got, want


def compare(got: pd.DataFrame, want: pd.DataFrame) -> pd.DataFrame:
    m = got.merge(want, on="game_id", how="outer", suffixes=("_live", "_graded"), indicator=True)
    same = ((m["_merge"] == "both") & (m["side_live"] == m["side_graded"]) & (m["book_live"] == m["book_graded"])
            & np.isclose(m["line_live"].astype(float), m["line_graded"].astype(float))
            & np.isclose(m["price_live"].astype(float), m["price_graded"].astype(float)))
    return m.assign(same=same)


def main() -> None:
    import config
    got, want = replay(H.CACHE)
    m = compare(got, want)
    diff = m[~m["same"]]
    print(f"replay on the graded books {GRADED_BOOKS}: {len(got)} bets; graded: {len(want)}; "
          f"identical: {int(m['same'].sum())}")
    live_got, _ = replay(H.CACHE, tuple(config.BEST_LINE_BOOKMAKERS))
    lm = compare(live_got, want)
    print(f"on today's deciding books {tuple(config.BEST_LINE_BOOKMAKERS)}: {len(live_got)} bets, "
          f"{int(lm['same'].sum())} identical; the others:")
    print(lm[~lm["same"]].to_string(index=False))
    if len(diff):
        print(diff.to_string(index=False))
        raise SystemExit(1)
    print("every graded bet reproduced on the graded books: same game, side, book, line and price")


if __name__ == "__main__":
    main()
