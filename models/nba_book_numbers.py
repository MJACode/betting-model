"""Which quote is a book's number: ONE copy of the main-number rule.

Some books hang a whole ladder of lines for one market in one fetch (betrivers
and betparx 5-7 team-total rungs, betmgm up to 21), and a few list a single
first-half or first-quarter rung 2+ points off every other book at a lopsided
price. A bettor reading "the book's number" means the main rung, so every
reader of these markets goes through the rule below. It moved here from the
fourth search's lab (scripts/nba_game4_p2.py) so that the lab's three families
(P1, P2, P3) and the live model nba_team_total_luck read the SAME code; the lab
imports it from here.

  main rung     per (game, market, book, fetch): the rung whose two prices are
                closest to even (the first search's `main`), coherent rungs
                first, ties to the lower number (main_rungs).
  ladder rule   a deciding book's first-half, first-quarter or team-total
                spread or total more than OFF_MED_PTS (1 point,
                scripts/nba_derivative_lab.py) from the median of the deciding
                books' main numbers at T is an alternate rung and is never an
                offer or the market's fair line. Pinnacle is never dropped and
                is not part of that median (ladder_mask). Full-game quotes are
                not ladders.

The live fetch applies the main rung once more, at WRITE time
(split_main_rungs): it stores each book's main rung under team_totals_home /
team_totals_away / totals_h1 and the rest under the _alternate names, so every
reader of one row per (game, market, book) lands on the main number.
The replay of the lab (scripts/nba_team_total_luck_replay.py) passes the
archived ladders through the same splitter before deciding.

The harness (scripts/nba_game_harness.py) is imported inside each function, as
models/nba_total_luck.py does, so the live fetch can import the splitter
without loading the research harness at import time.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

RUNG_KEY = ["game_id", "market", "book", "fetch_at"]


def even_gap(q: pd.DataFrame) -> np.ndarray:
    """How far a quote's two implied probabilities are apart (0 = even)."""
    from scripts import nba_game_harness as H
    return np.abs(H.imp(q["price_a"]) - H.imp(q["price_b"]))


def _one_rung(x: pd.DataFrame, first: list[str]) -> pd.DataFrame:
    x = x.assign(_inc=~x["coherent"].astype(bool), _eg=even_gap(x), _ln=x["line"].fillna(0.0))
    x = x.sort_values(RUNG_KEY + first + ["_inc", "_eg", "_ln"], kind="mergesort")
    drop = ["_inc", "_eg", "_ln"] + first
    return x.drop_duplicates(RUNG_KEY).drop(columns=drop).reset_index(drop=True)


def main_rungs(q: pd.DataFrame) -> pd.DataFrame:
    """One quote per (game, market, book, fetch): the rung whose two prices are
    closest to even (the first search's `main`), coherent first, ties to the
    lower number."""
    return _one_rung(q, [])


def ladder_mask(vis: pd.DataFrame, vis_main: pd.DataFrame, books=None) -> np.ndarray:
    """True for a deciding book's first-half, first-quarter or team-total spread
    or total more than OFF_MED_PTS from the median of the deciding books' main
    numbers at T (vis_main): an alternate rung, not the number it hangs.

    `books`: the deciding books, the harness's BETTABLE (config.BEST_LINE_BOOKMAKERS
    at its import) unless given. Only they are masked and only they make the
    median; a live model passes its own list."""
    from scripts import nba_game_harness as H
    from scripts.nba_derivative_lab import OFF_MED_PTS
    books = tuple(H.BETTABLE) if books is None else tuple(books)

    def deriv(v):
        return (H.scope(v["market"]) != "game") & (H.kind(v["market"]) != "ml")
    if vis.empty:
        return np.zeros(0, bool)
    m = vis_main[deriv(vis_main) & vis_main["book"].isin(books).to_numpy()
                 & vis_main["coherent"].to_numpy(bool)]
    med = m.groupby(["game_id", "market"])["line"].median().rename("_med").reset_index()
    x = vis[["game_id", "market", "book", "line"]].merge(med, on=["game_id", "market"], how="left")
    far = (x["line"] - x["_med"]).abs().to_numpy() > OFF_MED_PTS
    return deriv(vis) & vis["book"].isin(books).to_numpy() & far


def visible_numbers(q: pd.DataFrame, times: pd.DataFrame, books=None) -> pd.DataFrame:
    """What a bettor sees at each game's T, one number per book: its main rung
    in each fetch (main_rungs), the harness's newest fresh quote (H.visible),
    and no deciding book's first-half, first-quarter or team-total alternate
    (ladder_mask, `books` as there). P1 and P3 read their offers and the
    market's fair line through this, so the three families price the same
    quotes (docs/nba_models_2026.md sections 8.1 and 8.3, 2026-10-18), and so
    does the live nba_team_total_luck. H.visible alone keeps whichever rung of
    a ladder is last in the file."""
    from scripts import nba_game_harness as H
    vm = H.visible(main_rungs(q), times)
    return vm[~ladder_mask(vm, vm, books)].reset_index(drop=True)


# ── the write-time split: the main rung under the market's own name ─────────

# The market a stored row is filed under when it is NOT the book's main rung in
# that fetch. The prop ladders are named the same way
# (data/migrations/latest_line_state_tables.sql: *_alternate).
ALTERNATE_MARKET = {"team_totals_home": "team_totals_home_alternate",
                    "team_totals_away": "team_totals_away_alternate",
                    "totals_h1": "totals_h1_alternate"}


def split_main_rungs(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """One fetch's per-event total rows, team totals or the first half
    (odds-table dicts: game_id, bookmaker, market, total_line, over_price,
    under_price, ...) -> (main, alternates).

    For each (game, book, market) the main rung (main_rungs: coherent first,
    closest to even, ties to the lower number) keeps its market name; every
    other rung is returned with market renamed by ALTERNATE_MARKET. Only a rung
    with BOTH prices can be the main one, as in the lab, whose loader drops a
    one-sided quote before choosing (scripts/nba_game_harness.load_per_event):
    a one-sided rung is always an alternate, and a book with no two-sided rung
    keeps nothing under the main name. Rows keep their order and every other
    key; the dicts passed in are not modified.

    `rows` is ONE fetch: the rule picks one rung per (game, book, market), so
    rows from two fetches would lose the older fetch's main rung."""
    from scripts import nba_game_harness as H
    if not rows:
        return [], []
    bad = sorted({str(r.get("market")) for r in rows} - set(ALTERNATE_MARKET))
    if bad:
        raise ValueError(f"split_main_rungs: not a per-event total market: {bad}")

    def num(v):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return np.nan
        return f if np.isfinite(f) else np.nan

    q = pd.DataFrame({
        "_row": range(len(rows)),
        "game_id": [r.get("game_id") for r in rows],
        "market": [r["market"] for r in rows],
        "book": [r.get("bookmaker") for r in rows],
        "fetch_at": 0,
        "line": [num(r.get("total_line")) for r in rows],
        "price_a": [num(r.get("over_price")) for r in rows],
        "price_b": [num(r.get("under_price")) for r in rows],
    })
    q = q[q["price_a"].notna() & q["price_b"].notna()]
    s = H.imp(q["price_a"]) + H.imp(q["price_b"])
    q = q.assign(coherent=(s >= H.COHERENT[0]) & (s <= H.COHERENT[1]),
                 game_id=q["game_id"].fillna(""), book=q["book"].fillna(""))
    keep = set(main_rungs(q)["_row"]) if len(q) else set()
    main, alt = [], []
    for i, r in enumerate(rows):
        if i in keep:
            main.append(dict(r))
        else:
            alt.append({**r, "market": ALTERNATE_MARKET[r["market"]]})
    return main, alt
