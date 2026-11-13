"""
NCAAB full-game moneylines at a book's FIRST moneyline post, priced off the
same book's own spread at that moment: the first-post moneyline model
(`ncaab_moneyline_first_post`).

LIVE, real money (mike, 2026-11-03: a new model when a new search beats what
is live; "-200 max" for NCAAB moneylines). The card that writes its picks is
scripts/ncaab_moneyline_first_post_card.py, run every minute; the frozen
numbers it reads are models/saved/ncaab_moneyline_first_post_2027.json,
written by scripts/ncaab_moneyline_first_post_build.py, whose replay of this
module over 2021-2026 matched the research's bets game by game.
docs/sports/ncaab.md has the evidence and its caveats (a secondary cell of the
round-5 search, not its pre-registered one; the half-hourly history cannot say
how long a first post stayed up).

THE RULE. The moment a bettable book (models/ncaab_book_quotes.BOOKS) first
posts its full-game moneyline for a game:
  1. QUOTES. Every bettable book's standing full-game moneyline and spread,
     and Pinnacle's and Bovada's moneylines for the favourite check, each
     book's NEWEST stored row however old (the capture stores a row only when
     a number moves, so an unchanged quote keeps its first stamp). No
     60-minute window: that is the 15:00 UTC model's read, not this one's.
  2. PRICE, FLAGS AND FLOOR exactly as the 15:00 UTC moneyline model
     (models/ncaab_moneyline_own_spread.py, steps 2-4): P(home win) from the
     posting book's OWN spread through the final-margin distribution; the
     three suspect-quote flags (implied sum outside 1.00-1.15, a favourite no
     other book shares, the book's own spread of 1.5 or more naming the other
     team); every side shorter than -200 removed BEFORE the pick.
  3. ONLY THE NEW POST IS PRICED: the book's newly posted moneyline, still at
     its first number. The other books' moneylines are read for the count and
     the flags, never bet here.
  4. THREE OTHERS UP. At least 3 OTHER bettable books must have a moneyline
     standing at that moment (both prices -100/+100 or longer; a flagged quote
     still counts, as the evidence counted it; a book posting in the same
     moment counts too).
  5. BET the posting book's better side when its edge, P(side wins) minus the
     side's own price's implied (vig included), is above 0.015. When two books
     post in the same moment, the larger edge wins and a tie goes to the
     book's name in alphabetical order (the research's order, not the 15:00
     UTC model's longer-price tie-break).
  6. FEED TYPOS OUT, FIRST (models/ncaab_quote_bounds.py), as on the 15:00 UTC
     card: a moneyline priced beyond +/-100000, and a spread beyond +/-60 or
     priced beyond +/-100000, is dropped before any flag, count or price reads
     it, and that book has no such quote at that moment. A moment whose
     largest edge is above the data-error cap
     (ncaab_quote_bounds.EDGE_CAP[MODEL_ID]) bets nothing: that post is
     written edge_cap and the card's run fails.
A moment less than five minutes before tip is not priced.

ONE BET A GAME, ACROSS BOTH MONEYLINE MODELS. A first post below the cut does
not close the game: a later book's first post can still bet it (the evidence's
bets came at DraftKings 157 times, Caesars 122). The first BET closes it, for
this model and for the 15:00 UTC model, whichever writes its bet first
(scripts/ncaab_moneyline_first_post_card.py and scripts/ncaab_moneyline_card.py
each read the other's BETs under both models' locks).

THE PROBABILITY (what model_probability holds): P(the bet side wins) from the
posting book's own spread, the number the 0.015 cut was measured on. The model
decides on its own number (config.MODELS_ON_OWN_PROBABILITY).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from models import ncaab_book_quotes as bq
from models import ncaab_margin_dist as md
from models import ncaab_moneyline_own_spread as om
from models import ncaab_quote_bounds as qb

MODEL_ID = "ncaab_moneyline_first_post"
SPORT = "NCAAB"
MARKET = "h2h"

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = "models/saved/ncaab_moneyline_first_post_2027.json"
ARTIFACT_KIND = "ncaab_moneyline_first_post"

# The other moneyline model: one bet a game across the two.
OTHER_MODEL_ID = om.MODEL_ID

REF_BOOKS = om.REF_BOOKS
CUT = 0.015
MIN_PRICE = om.MIN_PRICE        # -200, mike: "-200 max"
MIN_OTHER_BOOKS = 3
MIN_LEAD = om.MIN_LEAD          # five minutes before tip

dec = om.dec


def too_close(tip, instant) -> bool:
    """A moment less than five minutes before tip is never priced."""
    return pd.Timestamp(instant) > pd.Timestamp(tip) - MIN_LEAD


def read(ml_rows: pd.DataFrame, sp_rows: pd.DataFrame, table: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The read at the moment of a first post, from raw rows carrying instant
    and tip: om.read with no freshness window (each book's newest row)."""
    return om.read(ml_rows, sp_rows, table, window_min=None)


# ── the artifact ──────────────────────────────────────────────────────────────

def load_artifact(path: str | Path | None = None) -> dict:
    """The frozen numbers, with the margin table rebuilt (art["table"]).

    The table is the spread model's (one fit, three models), read from the file
    this artifact names and refused unless its digest matches the one recorded
    at build time, exactly as the 15:00 UTC moneyline model's artifact does."""
    p = Path(path) if path is not None else ROOT / ARTIFACT_PATH
    art = json.loads(p.read_text(encoding="utf-8"))
    if art.get("kind") != ARTIFACT_KIND:
        raise ValueError(f"{p}: not an {ARTIFACT_KIND} artifact")
    if tuple(art["books"]) != bq.BOOKS or tuple(art["ref_books"]) != REF_BOOKS:
        raise ValueError(f"{p}: built on books {art['books']} / {art['ref_books']}, the card reads "
                         f"{list(bq.BOOKS)} / {list(REF_BOOKS)}")
    src = ROOT / art["margin_table_from"]
    other = json.loads(src.read_text(encoding="utf-8"))
    if int(other.get("season", -1)) != int(art["season"]):
        raise ValueError(f"{src}: margin table for season {other.get('season')}, this model is "
                         f"for {art['season']}")
    if om.table_digest(other["margin_table"]) != art["margin_table_sha256"]:
        raise ValueError(f"{src}: its margin table is not the one {p.name} was built on "
                         f"(digest differs); rebuild with scripts/ncaab_moneyline_first_post_build.py")
    art["table"] = md.from_json(other["margin_table"])
    return art


# ── the decision ──────────────────────────────────────────────────────────────

# Every status a first post can be written with (the ledger's `status`).
STATUSES = ("bets", "below_cut", "too_few_books", "no_clean_quote", "not_best",
            "book_not_bettable", "edge_cap", "game_already_bet", "other_model_bet", "moved_before_seen",
            "tipped", "pre_model", "before_window", "missed")


@dataclass
class PostDecision:
    """One book's first moneyline post, decided. best is the priced better
    side of THIS book's quote (a row of om.price_sides), when it had one."""
    game_id: str
    bookmaker: str
    status: str
    detail: str
    best: dict | None = None
    quotes: list = field(default_factory=list)
    dk: dict | None = None
    n_books: int = 0                  # bettable books with a price-valid moneyline, this one included


_FLAGS = ("overround_bad", "fav_alone", "spread_disagree")


def _book_reason(mrow: dict | None, srow: dict | None, min_price: float) -> str:
    """Why a posted quote has no priced side, in the ledger's words."""
    if mrow is None:
        return "its moneyline is not price-valid (a price inside -100..+100)"
    flags = [n for n in _FLAGS if bool(mrow[n])]
    if flags:
        return "flagged: " + ", ".join(flags)
    if srow is None or not bool(srow["own_ok"]):
        return "no usable own spread"
    return f"both sides shorter than {min_price:+.0f}"


def decide_posts(posting: pd.DataFrame, ml: pd.DataFrame, sp: pd.DataFrame, cut: float = CUT,
                 bettable=bq.BOOKS, min_price: float = MIN_PRICE,
                 min_other: int = MIN_OTHER_BOOKS, with_quotes: bool = True,
                 dropped: pd.DataFrame | None = None) -> list[PostDecision]:
    """Decide every first post in `posting` (game_id, bookmaker), all at the
    same moment per game. Pure given its inputs.

    ml: om.flag_moneylines output and sp: om.spread_quotes output, both read
    at that moment (read()). bettable: the books a bet may be placed at now
    (config.BEST_LINE_BOOKMAKERS); the pick is made over the posting books
    first, as the evidence made it, and a pick at a book not bettable now is
    not replaced by the next one. with_quotes=False leaves out every book's
    quotes (the ledger's `quotes`), which the replay does not need. dropped:
    the moneylines and spreads the read dropped as data errors
    (models/ncaab_book_quotes.dropped_quotes, with `market`), listed in each
    post's quotes and detail; nothing is priced from them."""
    out: list[PostDecision] = []
    if not len(posting):
        return out
    drops = om._dropped_list(dropped)
    sides = om.price_sides(ml, sp, min_price)
    sides = sides[sides["edge"].notna()]
    # One side per quote: the larger edge (the research's order).
    sides = sides.sort_values(["game_id", "bookmaker", "edge"], ascending=[True, True, False],
                              kind="mergesort").drop_duplicates(["game_id", "bookmaker"], keep="first")
    best_by = {(r["game_id"], r["bookmaker"]): r for r in sides.to_dict("records")}
    keep = ["game_id", "bookmaker", "p1", "p2", "flag_any"] + list(_FLAGS) + \
        [c for c in ("link1", "link2") if c in ml.columns]
    ml_rec = {(r["game_id"], r["bookmaker"]): r for r in ml[keep].to_dict("records")} if len(ml) else {}
    sp_rec = {(r["game_id"], r["bookmaker"]): r
              for r in sp[["game_id", "bookmaker", "own_ok"]].to_dict("records")} if len(sp) else {}
    mb = ml[ml["bookmaker"].isin(bq.BOOKS)] if len(ml) else ml
    n_by = mb.groupby("game_id")["bookmaker"].nunique().to_dict() if len(mb) else {}
    if with_quotes:
        ml_by = {g: x for g, x in ml.groupby("game_id")} if len(ml) else {}
        sp_by = {g: x for g, x in sp.groupby("game_id")} if len(sp) else {}
    for gid, post in posting.groupby("game_id", sort=True):
        books = sorted(set(post["bookmaker"]))
        n_books = int(n_by.get(gid, 0))
        quotes = []
        if with_quotes and gid in ml_by:
            quotes = om._quote_list(ml_by[gid], sp_by.get(gid, sp.iloc[0:0]))
        dg = drops.get(gid, [])
        if with_quotes:
            quotes = quotes + dg
        note = ("; dropped as data errors: " + ", ".join(
            f"{x['book']} {x['market']} ({x['why']})" for x in dg)) if dg else ""
        r = ml_rec.get((gid, "draftkings"))
        dk = None
        if r is not None and not r["flag_any"]:
            dk = {"p1": float(r["p1"]), "p2": float(r["p2"]), "link1": r.get("link1"),
                  "link2": r.get("link2")}
        cands = []
        res: dict[str, PostDecision] = {}
        for b in books:
            bb = best_by.get((gid, b))
            base = dict(game_id=gid, bookmaker=b, quotes=quotes, dk=dk, n_books=n_books)
            if bb is None:
                own = [x for x in dg if x["book"] == b]
                why = ("its own " + ", ".join(f"{x['market']} is a data error ({x['why']})" for x in own)
                       if own else _book_reason(ml_rec.get((gid, b)), sp_rec.get((gid, b)), min_price))
                res[b] = PostDecision(status="no_clean_quote", detail=why + note, **base)
                continue
            bb = dict(bb)
            desc = (f"{b} {bb['side']} {bb['price']:+.0f} edge {bb['edge']:+.4f} p {bb['prob']:.4f} "
                    f"own spread {bb['own_line']:+g} mean {bb['mu']:+.2f} books {n_books}")
            if n_books - 1 < min_other:
                res[b] = PostDecision(status="too_few_books", best=bb,
                                      detail=f"{desc}; {n_books - 1} other bettable moneyline(s) up, "
                                             f"{min_other} needed", **base)
            elif not bb["edge"] > cut:
                res[b] = PostDecision(status="below_cut", best=bb, detail=desc, **base)
            else:
                res[b] = PostDecision(status="bets", best=bb, detail=desc, **base)
                cands.append(bb)
        if cands:
            cands.sort(key=lambda r: (-r["edge"], r["bookmaker"]))
            win = cands[0]["bookmaker"]
            for c in cands[1:]:
                d = res[c["bookmaker"]]
                d.status = "not_best"
                d.detail += f"; {win} posted in the same moment with the larger edge"
            capped = qb.edge_problem(cands[0]["edge"], MODEL_ID)
            if capped:
                # The moment's largest edge is a data error, not a bet
                # (models/ncaab_quote_bounds.py): nothing is bet at this
                # moment, and the game stays open for a later first post.
                d = res[win]
                d.status = "edge_cap"
                d.detail += f"; {capped}: a data error, not a bet"
            elif win not in bettable:
                d = res[win]
                d.status = "book_not_bettable"
                d.detail += "; that book is not in config.BEST_LINE_BOOKMAKERS"
        for b in books:
            res[b].detail += note
        out += [res[b] for b in books]
    return out


def the_bet(decisions: list[PostDecision]) -> dict[str, PostDecision]:
    """{game_id: the post that bets}; at most one a game by construction."""
    return {d.game_id: d for d in decisions if d.status == "bets"}


def ev_of(prob, price) -> np.ndarray:
    """EV per unit staked: P(side wins) x decimal - 1."""
    return np.asarray(prob, float) * dec(price) - 1
