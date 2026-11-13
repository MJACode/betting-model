"""
NCAAB full-game spreads: the NCAAB spread model (`ncaab_spread_market`).

LIVE, real money (mike, 2026-11-02: "we need to build 1H and game lines ML and
Spread no matter what"; CLAUDE.md section 2). No games-played wait (mike, the
same day: "we do not need to wait 10 games ... I want these models live now").
The card that writes its picks is scripts/ncaab_spread_card.py; the frozen
numbers it reads are models/saved/ncaab_spread_market_2027.json, written by
scripts/ncaab_spread_market_build.py. docs/sports/ncaab.md has the evidence.

THE RULE, per game, at 15:00 UTC on its date (models/ncaab_book_quotes.py):
  1. QUOTES. Each of the eight bettable books' standing full-game spread (its
     newest pre-game row stamped in the hour up to 15:00 UTC): home line and
     both prices.
  2. ARTEFACTS OUT. A quote whose line or price is a feed typo (a spread
     beyond +/-60, a price beyond +/-100000: models/ncaab_quote_bounds.py) is
     dropped before anything reads it, and that book has no quote. A quote on
     the other side of zero from the median of the other books is a pick'em
     sign error and is dropped.
  3. CONSENSUS. The median of the remaining lines, the book being priced
     included.
  4. MEAN. Expected home margin = -consensus + c, with c = +0.2494 points in
     November and -0.0815 from December on: the mean of (final margin + the
     Prediction Tracker opener) over the 2012-2020 archive games. Fitted once,
     on the free archive, and used for every season the evidence graded; it was
     never refit on the paid seasons, so neither is it here.
  5. PRICE every quote with the final-margin distribution
     (models/ncaab_margin_dist.py, fitted on every season before the one
     priced): P(home covers | no push) at the quote's own line; the edge of a
     side is that chance (or one minus it for the away side) minus the
     implied probability of the side's own price, vig included. A quote's side
     is the one with the larger edge (home on a tie).
  6. BET the single best quote of the game when its edge is above 0.03 and at
     least MIN_OTHER_BOOKS other books are in the consensus. Best = largest
     edge; a tie goes to the better line for the side, then the better price,
     then a book a bet may be placed at, then the book's name in alphabetical
     order. A tie on line AND price is the same bet at two books, so those last
     two steps only name which (betPARX, fetch-only since 2026-11-06, never
     takes a tie from a bettable book).
  7. A best edge above the data-error cap (models/ncaab_quote_bounds.EDGE_CAP)
     is not a bet: the game is decided as edge_cap with none, and the card's
     run fails so the failure alerter says so.

Each game is decided once (CLAUDE.md section 1c): bet or not, never looked at
again, and a moved line writes nothing.

THE PROBABILITY (what model_probability holds): P(win | no push) on the bet
side at the bet book's line, the number the 0.03 cut was measured on.
decision_edge is that minus the bet price's implied probability, so the
publishers' 0.03 edge filter agrees with the card exactly. The model decides on
its own number (config.MODELS_ON_OWN_PROBABILITY): it has no record to fit a
map on.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from models import ncaab_book_quotes as bq
from models import ncaab_margin_dist as md
from models import ncaab_quote_bounds as qb

MODEL_ID = "ncaab_spread_market"
SPORT = "NCAAB"
MARKET = "spreads"

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = "models/saved/ncaab_spread_market_2027.json"
ARTIFACT_KIND = "ncaab_spread_market"

MIN_OTHER_BOOKS = 3
PHASES = ("Nov", "Dec+")


def phase_of(game_date) -> str:
    """'Nov' for a November game date, else 'Dec+'."""
    return "Nov" if pd.Timestamp(str(game_date)[:10]).month == 11 else "Dec+"


def dec(american) -> np.ndarray:
    """Decimal odds, vectorised, the research's own arithmetic."""
    a = np.asarray(american, dtype=float)
    return np.where(a > 0, 1 + a / 100.0, 1 + 100.0 / np.abs(a))


# ── pricing ───────────────────────────────────────────────────────────────────

def price_quotes(q: pd.DataFrame, c_by_phase: dict, table: dict) -> pd.DataFrame:
    """Price every 'ok' quote of a snapshot (models/ncaab_book_quotes.snapshot
    output, plus a `phase` column). Adds mu, ph (P home covers | no push), pp
    (P push), side (1 home / 2 away), edge, price and prob (P win | no push of
    the side). Quotes that are flagged, or whose game has no consensus, are
    left out."""
    z = q[(q["flag"] == "ok") & q["cons"].notna()].copy()
    if not len(z):
        for c in ("mu", "ph", "pp", "edge", "price", "prob"):
            z[c] = pd.Series(dtype=float)
        z["side"] = pd.Series(dtype=int)
        return z
    z["mu"] = -z["cons"] + z["phase"].map(c_by_phase)
    ph, pp = md.home_cover(z["mu"].to_numpy(float), z["line"].to_numpy(float), table)
    z["ph"] = ph
    z["pp"] = pp
    e1 = z["ph"] - 1 / dec(z["p1"])
    e2 = (1 - z["ph"]) - 1 / dec(z["p2"])
    z["side"] = np.where(e1 >= e2, 1, 2)
    z["edge"] = np.maximum(e1, e2)
    z["price"] = np.where(z["side"] == 1, z["p1"], z["p2"])
    z["prob"] = np.where(z["side"] == 1, z["ph"], 1 - z["ph"])
    return z


def best_per_game(z: pd.DataFrame, bettable=None) -> pd.DataFrame:
    """The single best priced quote per game: largest edge; a tie goes to the
    better line for the side, then the better price, then a book in `bettable`
    (None: every book is), then the book's name.

    A tie on line and price is the same bet at two books, so the bettable book
    takes it (mike, 2026-11-07, after betPARX left the deciding books: 74 of the
    89 replayed bets it held were exact ties, 70 with BetRivers alone). With
    every book bettable the order is the evidence's exactly."""
    z = z[z["edge"].notna()].copy()
    z["_line_for_side"] = np.where(z["side"] == 1, z["line"], -z["line"])
    z["_dprice"] = dec(z["price"])
    z["_unbettable"] = 0 if bettable is None else (~z["bookmaker"].isin(list(bettable))).astype(int)
    z = z.sort_values(["game_id", "edge", "_line_for_side", "_dprice", "_unbettable", "bookmaker"],
                      ascending=[True, False, False, False, True, True], kind="mergesort")
    return z.drop_duplicates("game_id", keep="first").drop(
        columns=["_line_for_side", "_dprice", "_unbettable"])


# ── the artifact ──────────────────────────────────────────────────────────────

def load_artifact(path: str | Path | None = None) -> dict:
    """The frozen numbers, with the margin table rebuilt (art["table"])."""
    p = Path(path) if path is not None else ROOT / ARTIFACT_PATH
    art = json.loads(p.read_text(encoding="utf-8"))
    if art.get("kind") != ARTIFACT_KIND:
        raise ValueError(f"{p}: not an {ARTIFACT_KIND} artifact")
    if tuple(art["books"]) != bq.BOOKS:
        raise ValueError(f"{p}: built on books {art['books']}, the card reads {list(bq.BOOKS)}")
    art["table"] = md.from_json(art["margin_table"])
    return art


# ── the decision ──────────────────────────────────────────────────────────────

DIAG_KEYS = ("games", "already_decided", "no_quotes", "no_clean_quote", "below_cut",
             "too_few_books", "book_not_bettable", "edge_cap", "bets", "missed", "tipped",
             "quotes_dropped")


@dataclass
class Decision:
    game_id: str
    status: str                      # a DIAG key
    detail: str
    best: dict | None = None         # the priced best quote (a row of price_quotes)
    quotes: list = field(default_factory=list)   # every book's quote at the instant
    dk: dict | None = None           # DraftKings' own quote, when it had one


def _quote_list(q: pd.DataFrame, dropped: pd.DataFrame | None = None) -> list[dict]:
    out = []
    for r in q.sort_values("bookmaker").itertuples(index=False):
        out.append({"book": r.bookmaker, "line": float(r.line), "p1": float(r.p1),
                    "p2": float(r.p2), "ts": pd.Timestamp(r.ts).isoformat(), "flag": r.flag})
    for r in ([] if dropped is None else dropped.sort_values("bookmaker").to_dict("records")):
        out.append({"book": r["bookmaker"], "line": float(r["line"]), "p1": float(r["p1"]),
                    "p2": float(r["p2"]), "ts": pd.Timestamp(r["ts"]).isoformat(),
                    "flag": "out_of_range", "why": r["why"]})
    return out


def _dropped_note(dropped: pd.DataFrame | None) -> str:
    if dropped is None or not len(dropped):
        return ""
    return "; dropped as data errors: " + ", ".join(
        f"{r['bookmaker']} {float(r['line']):+g} ({r['why']})" for r in dropped.to_dict("records"))


def decide(game_ids, snap: pd.DataFrame, c_by_phase: dict, table: dict, cut: float,
           min_other_books: int = MIN_OTHER_BOOKS, bettable=bq.BOOKS,
           dropped: pd.DataFrame | None = None) -> list[Decision]:
    """Decide each game at its 15:00 UTC snapshot. Pure given its inputs.

    game_ids: the games to decide. snap: models/ncaab_book_quotes.snapshot
    output for them, with a `phase` column. bettable: the books a bet may be
    placed at now (config.BEST_LINE_BOOKMAKERS); the best quote is chosen over
    every book first, as the evidence chose it, and a best quote at a book not
    bettable now is not replaced by the next one. An exact tie (same line and
    price) is the same bet, so it goes to the bettable book (best_per_game). dropped: the quotes the
    snapshot dropped as data errors (models/ncaab_book_quotes.dropped_quotes),
    listed in each game's decision; nothing is priced from them."""
    out: list[Decision] = []
    by_game = {g: x for g, x in snap.groupby("game_id")} if len(snap) else {}
    drops = ({g: x for g, x in dropped.groupby("game_id")}
             if dropped is not None and len(dropped) else {})
    priced = price_quotes(snap, c_by_phase, table) if len(snap) else snap
    best = best_per_game(priced, bettable).set_index("game_id") if len(priced) else None
    for gid in game_ids:
        q = by_game.get(gid)
        dg = drops.get(gid)
        note = _dropped_note(dg)
        if q is None or not len(q):
            out.append(Decision(gid, "no_quotes", "no bettable book quoted a spread in the hour "
                                                  "before 15:00 UTC" + note,
                                quotes=_quote_list(pd.DataFrame(columns=["bookmaker"]), dg)))
            continue
        quotes = _quote_list(q, dg)
        dkq = q[q["bookmaker"] == "draftkings"]
        dk = None
        if len(dkq):
            r = dkq.iloc[0]
            dk = {"line": float(r.line), "p1": float(r.p1), "p2": float(r.p2), "flag": r.flag,
                  "link1": r.get("link1"), "link2": r.get("link2")}
        if best is None or gid not in best.index:
            out.append(Decision(gid, "no_clean_quote", "every quote crossed zero against the "
                                                       "other books" + note, quotes=quotes, dk=dk))
            continue
        b = best.loc[gid].to_dict()
        b["game_id"] = gid
        side = "home" if int(b["side"]) == 1 else "away"
        others = int(b["n_ok"]) - 1
        desc = (f"{b['bookmaker']} {side} {b['line']:+g} {b['price']:+.0f} edge {b['edge']:+.4f} "
                f"p {b['prob']:.4f} consensus {b['cons']:+g} mean {b['mu']:+.2f} books {int(b['n_ok'])}")
        capped = qb.edge_problem(b["edge"], MODEL_ID)
        if capped:
            status = "edge_cap"
            desc += f"; {capped}: a data error, not a bet"
        elif not b["edge"] > cut:
            status = "below_cut"
        elif others < min_other_books:
            status = "too_few_books"
            desc += f"; {others} other book(s), needs {min_other_books}"
        elif b["bookmaker"] not in bettable:
            status = "book_not_bettable"
            desc += "; that book is not in config.BEST_LINE_BOOKMAKERS"
        else:
            status = "bets"
        out.append(Decision(gid, status, desc + note, best=b, quotes=quotes, dk=dk))
    return out


def snapshot_for(rows: pd.DataFrame, game_dates: dict[str, str]) -> pd.DataFrame:
    """The flagged snapshot with each game's phase, from raw rows carrying
    instant and tip (models/ncaab_book_quotes.load_rows output, or the
    replay's history)."""
    snap = bq.snapshot(rows)
    snap["phase"] = snap["game_id"].map({g: phase_of(d) for g, d in game_dates.items()})
    return snap
