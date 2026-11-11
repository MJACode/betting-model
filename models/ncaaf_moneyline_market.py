"""
NCAAF full-game moneylines against the books' consensus spread: the NCAAF
moneyline model (`ncaaf_moneyline_market`).

LIVE, real money (mike, 2026-11-10, asked after the market audit whether he
wanted a moneyline model live although nothing measured clears: "ML model
yes"). The card that writes its picks is scripts/ncaaf_moneyline_card.py; the
frozen numbers it reads are models/saved/ncaaf_moneyline_market_2026.json,
written by scripts/ncaaf_moneyline_market_build.py. docs/sports/ncaaf.md has
the evidence, and says plainly that the rule did NOT clear (its 2023-2025
interval reaches below zero), that its profit is one season, and that 294 of
its 311 replayed bets are road underdogs.

A straight port of the research rule (scripts/ncaaf_search/audit_2026_11/
lab.py: price_ml(x, tabs, "cons"), best(), and sweep()'s two filters). Nothing
here improves on it. The build replays 2023-2025 through decide() below and
matches the research's 311 bets game for game.

THE RULE, per game, at 14:00 UTC on its Eastern date:
  1. QUOTES. Each of the ten fetched books' (CONS_BOOKS) standing full-game
     moneyline (both prices) and full-game spread (home line, both prices):
     its newest pre-game row stamped in the 60 minutes up to 14:00 UTC.
  2. CONSENSUS. A spread counts when its line and both prices exist, the line
     is within +/-70 and the two implied chances sum to 1.00-1.15. The
     consensus is the median home line over those, and n_ok how many.
  3. MONEYLINES PRICED. A moneyline is priced when both prices exist and the
     implied chances sum to 1.00-1.15. It is dropped when its favourite
     differs from the favourite of every other priced book's moneyline (two
     or more others). Even prices count as the away side being favourite, as
     the research coded it.
  4. FAIR. Expected home margin = minus the consensus plus the fitted offset.
     P(home wins) = P(final margin > 0) at that mean, from the final-margin
     table (models/ncaab_margin_dist.py, unchanged; football has no ties, and
     the table's small weight on a 0 margin is left out of both sides).
  5. EDGE. For each deciding book (DECIDING_BOOKS) and each side priced -200
     or longer: fair chance minus the implied chance of that price, vig
     included. Sides shorter than -200 are removed before the pick. Each book
     offers its better side (home on an exact tie).
  6. BET the largest edge in the game (a tie goes to the longer price, then
     the book's name) when it is above 0.02 and at least three OTHER books are
     in the consensus (n_ok - 1 >= 3).
  A game kicking off less than five minutes after 14:00 UTC is not priced.

THE TABLE AND THE OFFSET for a season are fitted on every earlier season's
scored games and their CFBD closing spreads, in game-date then game-id order
(the build). The artifact holds one season's and the card refuses any other.

Each game is decided once (CLAUDE.md section 1c): bet or not, never looked at
again, and a moved price writes nothing.

THE PROBABILITY (what model_probability holds): the bet side's fair chance of
winning, the number the 0.02 cut was measured on. decision_edge is that minus
the bet price's implied, so the publishers' 0.02 edge filter agrees with the
card exactly. The model decides on its own number
(config.MODELS_ON_OWN_PROBABILITY): it has no record to fit a map on.

THE ID has no 'spread' in it on purpose: several places read a market off a
model id by substring, and this model bets MONEYLINES.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from models import ncaab_book_quotes as bq
from models import ncaab_margin_dist as md

MODEL_ID = "ncaaf_moneyline_market"
SPORT = "NCAAF"
MARKET = "h2h"

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = "models/saved/ncaaf_moneyline_market_2026.json"
ARTIFACT_KIND = "ncaaf_moneyline_market"

# The books the research placed a bet at, and the ten it took the consensus
# over. Pinned here, not read from config: an environment override of
# BEST_LINE_BOOKMAKERS or LINE_SHOP_BOOKMAKERS must not silently change who is
# in the consensus. tests/test_ncaaf_moneyline_market.py pins them to config's
# defaults, and the card refuses a best side at a book config no longer lists.
DECIDING_BOOKS = ("draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics",
                  "betrivers", "hardrockbet")
CONS_BOOKS = DECIDING_BOOKS + ("bovada", "pinnacle", "betparx")

CHECK_HOUR_UTC = 14
WINDOW_MIN = 60
CUT = 0.02
MIN_PRICE = -200          # sides shorter than this are removed before the pick
MIN_OTHER = 3             # other books in the consensus (n_ok - 1)
ISUM_LO, ISUM_HI = 1.0, 1.15
MAX_ABS_LINE = 70.0
MIN_LEAD = timedelta(minutes=5)
_ET = ZoneInfo("America/New_York")

# CFBD's stored closing spread, first provider that has one: what the table
# and the offset are fitted on (config.NCAAF_LINE_BOOKMAKER_PRIORITY).
CLOSE_PRIORITY = ("cfbd_draftkings", "cfbd_bovada", "cfbd_consensus", "cfbd_teamrankings")


def dec(american) -> np.ndarray:
    """Decimal odds, vectorised, the research's own arithmetic."""
    a = np.asarray(american, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(a > 0, 1 + a / 100.0, 1 + 100.0 / np.abs(a))


def _sane(d1, d2) -> np.ndarray:
    """The two implied chances sum to 1.00-1.15 (False where a price is missing)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        s = 1 / np.asarray(d1, float) + 1 / np.asarray(d2, float)
        return (s >= ISUM_LO) & (s <= ISUM_HI)


def eastern_date(kickoff) -> str:
    """The Eastern date a game kicks off on (the odds row's game_date)."""
    t = pd.Timestamp(kickoff)
    t = t.tz_localize("UTC") if t.tzinfo is None else t
    return t.tz_convert(_ET).strftime("%Y-%m-%d")


def check_instant(et_date) -> datetime:
    """14:00 UTC on the game's Eastern date."""
    d = pd.Timestamp(str(et_date)[:10])
    return datetime(d.year, d.month, d.day, CHECK_HOUR_UTC, tzinfo=timezone.utc)


def too_close(kickoff, instant) -> bool:
    """A game kicking off less than five minutes after its 14:00 UTC is never
    priced (the research's rule for every read it used)."""
    return pd.Timestamp(instant) > pd.Timestamp(kickoff) - MIN_LEAD


# ── the read ──────────────────────────────────────────────────────────────────

QUOTE_COLS = ["game_id", "bookmaker", "ml_home", "ml_away", "ml_ts", "link_home", "link_away",
              "spread_home", "sp_home", "sp_away", "sp_ts"]


def quotes_at(ml_rows: pd.DataFrame, sp_rows: pd.DataFrame,
              window_min: int | None = WINDOW_MIN) -> pd.DataFrame:
    """Each (game, book)'s standing moneyline and spread at its game's instant,
    one row per pair over the ten books.

    ml_rows / sp_rows: stored h2h / spreads odds rows as
    models/ncaab_book_quotes.load_rows returns them (game_id, bookmaker, ts
    the row's own stamp, line, p1 / p2 the home / away prices, order, instant,
    tip, and link1 / link2 when read from the database). A book's quote is its
    newest row stamped at or before the instant and at most window_min minutes
    older, complete (both prices; a spread also its line), for a game still to
    kick off. The selection is the NCAAB cards' own (the same function); their
    line and price bounds are NOT applied, because the research rule has its
    own (steps 2 and 3)."""
    m = bq._newest(ml_rows, window_min, CONS_BOOKS, False)
    s = bq._newest(sp_rows, window_min, CONS_BOOKS, True)
    ml = pd.DataFrame({
        "game_id": m["game_id"], "bookmaker": m["bookmaker"],
        "ml_home": pd.to_numeric(m["p1"], errors="coerce").astype(float),
        "ml_away": pd.to_numeric(m["p2"], errors="coerce").astype(float),
        "ml_ts": m["ts"],
        "link_home": m["link1"] if "link1" in m.columns else None,
        "link_away": m["link2"] if "link2" in m.columns else None,
    })
    sp = pd.DataFrame({
        "game_id": s["game_id"], "bookmaker": s["bookmaker"],
        "spread_home": pd.to_numeric(s["line"], errors="coerce").astype(float),
        "sp_home": pd.to_numeric(s["p1"], errors="coerce").astype(float),
        "sp_away": pd.to_numeric(s["p2"], errors="coerce").astype(float),
        "sp_ts": s["ts"],
    })
    q = ml.merge(sp, on=["game_id", "bookmaker"], how="outer")
    return q[QUOTE_COLS].sort_values(["game_id", "bookmaker"], kind="mergesort").reset_index(drop=True)


def mark(q: pd.DataFrame) -> pd.DataFrame:
    """Add, per (game, book): sp_ok (the spread counts toward the consensus),
    cons and n_ok (the game's consensus and how many spreads are in it), ml_ok
    (the moneyline is priced), fav_home, and fav_alone (its favourite differs
    from every other priced moneyline's, two or more others)."""
    x = q[q["bookmaker"].isin(CONS_BOOKS)].reset_index(drop=True)
    x["sp_ok"] = (x["spread_home"].notna() & x["sp_home"].notna() & x["sp_away"].notna()
                  & (x["spread_home"].abs() <= MAX_ABS_LINE)
                  & _sane(dec(x["sp_home"]), dec(x["sp_away"])))
    xs = x[x["sp_ok"]]
    cons = xs.groupby("game_id")["spread_home"].median()
    n_ok = xs.groupby("game_id")["spread_home"].size()
    x["cons"] = x["game_id"].map(cons)
    x["n_ok"] = x["game_id"].map(n_ok).fillna(0).astype(int)
    x["ml_ok"] = (x["ml_home"].notna() & x["ml_away"].notna()
                  & _sane(dec(x["ml_home"]), dec(x["ml_away"])))
    x["fav_home"] = dec(x["ml_home"]) < dec(x["ml_away"])
    x["fav_alone"] = False
    z = x[x["ml_ok"]]
    if len(z):
        fh = z.groupby("game_id")["fav_home"].transform("sum")
        nn = z.groupby("game_id")["fav_home"].transform("size")
        oth_home = fh - z["fav_home"].astype(int)
        oth = nn - 1
        alone = (oth >= 2) & ((z["fav_home"] & (oth_home == 0))
                              | (~z["fav_home"] & (oth_home == oth)))
        x.loc[z.index, "fav_alone"] = alone
    return x


PRICED_COLS = ["game_id", "bookmaker", "side", "price", "prob", "edge", "cons", "n_ok", "mu",
               "ph", "link"]


def price(marked: pd.DataFrame, table: dict, offset: float,
          min_price: float = MIN_PRICE) -> pd.DataFrame:
    """Every deciding book's priced moneyline at its better side.

    marked: mark() output. One row per (game, deciding book) whose moneyline
    is priced, not alone on its favourite, in a game with a consensus, and has
    a side at min_price or longer. side: 'home' | 'away'; prob the side's fair
    chance; edge prob minus the price's implied chance."""
    z = marked[marked["ml_ok"] & ~marked["fav_alone"] & marked["cons"].notna()].copy()
    if not len(z):
        return pd.DataFrame(columns=PRICED_COLS)
    mu = (-z["cons"] + offset).to_numpy(float)
    pw, pp, pl = md.probs(mu, np.zeros(len(z)), table)
    ph = pw / (pw + pl)
    dh, da = dec(z["ml_home"]), dec(z["ml_away"])
    floor = float(dec(min_price))
    e1 = np.where(dh >= floor, ph - 1 / dh, -9.0)
    e2 = np.where(da >= floor, (1 - ph) - 1 / da, -9.0)
    home = e1 >= e2
    z["mu"] = mu
    z["ph"] = ph
    z["side"] = np.where(home, "home", "away")
    z["edge"] = np.maximum(e1, e2)
    z["price"] = np.where(home, z["ml_home"], z["ml_away"])
    z["prob"] = np.where(home, ph, 1 - ph)
    z["link"] = np.where(home, z["link_home"], z["link_away"])
    z = z[z["edge"] > -5]
    return z[z["bookmaker"].isin(DECIDING_BOOKS)][PRICED_COLS].reset_index(drop=True)


def best_per_game(z: pd.DataFrame) -> pd.DataFrame:
    """The largest edge per game; a tie goes to the longer price, then the
    book's name."""
    z = z[z["edge"].notna()].copy()
    z["_d"] = dec(z["price"])
    z = z.sort_values(["game_id", "edge", "_d", "bookmaker"],
                      ascending=[True, False, False, True], kind="mergesort")
    return z.drop_duplicates("game_id", keep="first").drop(columns=["_d"])


# ── the artifact ──────────────────────────────────────────────────────────────

def load_artifact(path: str | Path | None = None) -> dict:
    """The frozen numbers, with the margin table rebuilt (art["table"])."""
    p = Path(path) if path is not None else ROOT / ARTIFACT_PATH
    art = json.loads(p.read_text(encoding="utf-8"))
    if art.get("kind") != ARTIFACT_KIND:
        raise ValueError(f"{p}: not an {ARTIFACT_KIND} artifact")
    if (tuple(art["deciding_books"]) != DECIDING_BOOKS
            or tuple(art["consensus_books"]) != CONS_BOOKS):
        raise ValueError(f"{p}: built on books {art['deciding_books']} / "
                         f"{art['consensus_books']}, the card reads {list(DECIDING_BOOKS)} / "
                         f"{list(CONS_BOOKS)}")
    art["table"] = md.from_json(art["margin_table"])
    art["offset"] = float(art["offset"])
    return art


# ── the decision ──────────────────────────────────────────────────────────────

DIAG_KEYS = ("games", "already_decided", "no_quotes", "no_consensus", "no_clean_quote",
             "too_few_books", "below_cut", "book_not_bettable", "bets", "missed", "kicked_off",
             "other_model_bet", "duplicate_game")


@dataclass
class Decision:
    game_id: str
    status: str                      # a DIAG key
    detail: str
    best: dict | None = None         # the priced best side (a row of price())
    quotes: list = field(default_factory=list)   # every book's moneyline and spread
    dk: dict | None = None           # DraftKings' own moneyline, when it was priced


def _f(v):
    return None if v is None or (isinstance(v, float) and v != v) else float(v)


def _stamp(v):
    return None if v is None or pd.isna(v) else pd.Timestamp(v).isoformat()


def _quote_list(m: pd.DataFrame) -> list[dict]:
    """Every book's quote as the decision row keeps it."""
    out = []
    for r in m.sort_values("bookmaker").itertuples(index=False):
        flags = []
        if r.ml_home != r.ml_home or r.ml_away != r.ml_away:
            flags.append("no_moneyline")
        elif not r.ml_ok:
            flags.append("moneyline_overround")
        elif r.fav_alone:
            flags.append("fav_alone")
        if r.spread_home != r.spread_home:
            flags.append("no_spread")
        elif not r.sp_ok:
            flags.append("spread_out")
        out.append({"book": r.bookmaker, "p1": _f(r.ml_home), "p2": _f(r.ml_away),
                    "ts": _stamp(r.ml_ts), "spread": _f(r.spread_home),
                    "spread_p1": _f(r.sp_home), "spread_p2": _f(r.sp_away),
                    "spread_ts": _stamp(r.sp_ts), "in_consensus": bool(r.sp_ok), "flags": flags})
    return out


def decide(game_ids, q: pd.DataFrame, table: dict, offset: float, cut: float = CUT,
           bettable=DECIDING_BOOKS, min_price: float = MIN_PRICE,
           min_other: int = MIN_OTHER) -> list[Decision]:
    """Decide each game at its 14:00 UTC read. Pure given its inputs.

    q: quotes_at output for these games. table / offset: the season's
    final-margin table and fitted offset. bettable: the books a bet may be
    placed at now (config.BEST_LINE_BOOKMAKERS); the best side is chosen over
    DECIDING_BOOKS first, as the research chose it, and a best side at a book
    not bettable now is not replaced by the next one."""
    out: list[Decision] = []
    marked = mark(q)
    by_game = {g: x for g, x in marked.groupby("game_id")} if len(marked) else {}
    priced = price(marked, table, offset, min_price)
    best = best_per_game(priced).set_index("game_id") if len(priced) else None
    for gid in game_ids:
        m = by_game.get(gid)
        mb = m[m["bookmaker"].isin(DECIDING_BOOKS) & m["ml_home"].notna()
               & m["ml_away"].notna()] if m is not None else None
        if mb is None or not len(mb):
            out.append(Decision(gid, "no_quotes", "no deciding book quoted a moneyline in the "
                                                  "hour before 14:00 UTC",
                                quotes=_quote_list(m) if m is not None else []))
            continue
        quotes = _quote_list(m)
        n_ok = int(m["n_ok"].iloc[0])
        dkq = mb[(mb["bookmaker"] == "draftkings") & mb["ml_ok"] & ~mb["fav_alone"]]
        dk = None
        if len(dkq):
            r = dkq.iloc[0]
            dk = {"p1": float(r["ml_home"]), "p2": float(r["ml_away"]),
                  "link1": r["link_home"], "link2": r["link_away"]}
        if n_ok == 0:
            out.append(Decision(gid, "no_consensus", "no book's spread counts toward a consensus",
                                quotes=quotes, dk=dk))
            continue
        if best is None or gid not in best.index:
            out.append(Decision(gid, "no_clean_quote",
                                f"no deciding book's moneyline is priced with a side at "
                                f"{min_price:+.0f} or longer; consensus "
                                f"{float(m['cons'].iloc[0]):+g} over {n_ok} books",
                                quotes=quotes, dk=dk))
            continue
        b = best.loc[gid].to_dict()
        b["game_id"] = gid
        desc = (f"{b['bookmaker']} {b['side']} {b['price']:+.0f} edge {b['edge']:+.4f} "
                f"p {b['prob']:.4f} consensus {b['cons']:+g} over {n_ok} books "
                f"mean {b['mu']:+.2f}")
        if n_ok - 1 < min_other:
            status = "too_few_books"
            desc += f"; fewer than {min_other} other books in the consensus"
        elif not b["edge"] > cut:
            status = "below_cut"
        elif b["bookmaker"] not in bettable:
            status = "book_not_bettable"
            desc += "; that book is not in config.BEST_LINE_BOOKMAKERS"
        else:
            status = "bets"
        out.append(Decision(gid, status, desc, best=b, quotes=quotes, dk=dk))
    return out
