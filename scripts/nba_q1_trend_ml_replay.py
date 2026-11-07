"""Replay the graded cell through the live model's own code (models/nba_q1_trend_ml.decide).

The first-quarter moneyline search graded 87 bets (docs/nba_search_q1mt.md: Q1M, the spread check, k >= 2). This runs
models.nba_q1_trend_ml.decide on the same archive, season by season, with the same quotes, decision times, numbers and
first-quarter scores the lab read (scripts.nba_game5.load_real, as scripts/nba_game8_q1_trends.prepare), and compares
every bet with the artifact's copy of the graded ones: game, side, book and price. A difference is printed and the run
exits 1, so the live model cannot drift from the graded rule unnoticed.

Reads the research cache (NBA_RESEARCH_CACHE, a cache of Supabase) and the artifact; no database, no API.

    NBA_RESEARCH_CACHE=... PYTHONPATH=. python -m scripts.nba_q1_trend_ml_replay
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import models.nba_q1_trend_ml as ml  # noqa: E402
from scripts import nba_game5 as G5  # noqa: E402
from scripts import nba_game8_q1_trends as G8  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402
from scripts.nba_q1_trend_replay import FLOOR  # noqa: E402
from scripts.nba_q1_trend_replay import GRADED_BOOKS as SPREAD_GRADED_BOOKS  # noqa: E402

COLS = ["game_id", "side", "book", "price"]
# The deciding books the search graded with (2026-11-07, config.BEST_LINE_BOOKMAKERS that day): betPARX had left them
# on 2026-11-06 (#1203), so unlike the spread model's eighth-search grade it is not one of them. The exact check runs
# on these; the spread model's graded books (with betPARX) are reported beside it.
GRADED_BOOKS = ("draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics", "betrivers", "hardrockbet")


def replay(cache: Path, books=GRADED_BOOKS, real: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(the replay's bets, the graded bets), one row per game."""
    real = real or G5.load_real(cache, True)
    games_p, pe, graded = real["games_p"], real["pe"], real["graded"]
    art = ml.load_artifact()
    times = H.per_event_times(pe, ml.POINT)
    numbers = G8.game_numbers(ml.q1.visible(pe, times))
    gp = games_p[games_p["season"].isin(graded)]
    tg = G8.team_games(gp, numbers)
    decided = gp[gp["game_id"].isin(set(times["game_id"]))]
    rows = []
    for s in graded:
        tgt = decided[decided["season"] == s][["game_id", "season", "game_date", "home_team", "away_team"]]
        bets, _, diag = ml.decide(tgt, pe[pe["season"] == s], tg, times, art, books=books, min_odds=FLOOR,
                                  bucket_uplift=0.0)
        print(f"season {s}: {diag}")
        rows += [{"game_id": b.game_id, "side": b.side, "book": b.book, "price": b.price} for b in bets]
    got = pd.DataFrame(rows, columns=COLS)
    want = pd.DataFrame(art["graded_bets"], columns=COLS + ["result"])
    return got, want


def compare(got: pd.DataFrame, want: pd.DataFrame) -> pd.DataFrame:
    m = got.merge(want, on="game_id", how="outer", suffixes=("_live", "_graded"), indicator=True)
    same = ((m["_merge"] == "both") & (m["side_live"] == m["side_graded"]) & (m["book_live"] == m["book_graded"])
            & np.isclose(m["price_live"].astype(float), m["price_graded"].astype(float)))
    return m.assign(same=same)


def main() -> None:
    import config
    real = G5.load_real(H.CACHE, True)
    got, want = replay(H.CACHE, real=real)
    m = compare(got, want)
    diff = m[~m["same"]]
    print(f"replay on the graded books {GRADED_BOOKS}: {len(got)} bets; graded: {len(want)}; "
          f"identical: {int(m['same'].sum())}")
    for name, books in (("today's deciding books", tuple(config.BEST_LINE_BOOKMAKERS)),
                        ("the spread model's graded books, with betPARX", SPREAD_GRADED_BOOKS)):
        other, _ = replay(H.CACHE, books, real=real)
        om = compare(other, want)
        print(f"on {name} {books}: {len(other)} bets, {int(om['same'].sum())} identical; the others:")
        print(om[~om["same"]].to_string(index=False))
    if len(diff):
        print(diff.to_string(index=False))
        raise SystemExit(1)
    print("every graded bet reproduced on the graded books: same game, side, book and price")


if __name__ == "__main__":
    main()
