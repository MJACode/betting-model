"""
NCAAB full-game moneylines priced off each book's own spread: the NCAAB
moneyline model (`ncaab_moneyline_own_spread`).

LIVE, real money (mike, 2026-11-02: "we need to build 1H and game lines ML and
Spread no matter what", "we do not need to wait 10 games", "I want it all done
and go live now"; and the cap, "-200 max"). The card that writes its picks is
scripts/ncaab_moneyline_card.py; the frozen numbers it reads are
models/saved/ncaab_moneyline_own_spread_2027.json, written by
scripts/ncaab_moneyline_build.py. docs/sports/ncaab.md has the evidence, and
says plainly that it did NOT clear the research bar (its 2021-2025 interval
reaches below zero) and that the rule was chosen after the fact.

THE RULE, per game, at 15:00 UTC on its date (models/ncaab_book_quotes.py, the
same instant and the same 60-minute freshness window as the spread model):
  1. QUOTES. Each bettable book's standing full-game moneyline, and the SAME
     book's standing full-game spread at the same instant. Pinnacle's and
     Bovada's moneylines are read too, only to check the favourite (step 3).
  2. FAIR. P(home win) from the book's OWN spread: its two prices power
     de-vigged to P(home covers | no push), the final-margin distribution
     (models/ncaab_margin_dist.py) inverted to the expected home margin that
     gives that cover chance at that line, then P(home win) = P(margin > 0) /
     (1 - P(margin = 0)) at that mean. No consensus, no offset: the book is
     priced against itself. A spread quote counts only when both prices are
     -100/+100 or longer, the two implied chances sum to 1.00-1.15, and its
     line is not on the other side of zero from the other books' median (the
     pick'em sign error, models/ncaab_book_quotes.flag_and_consensus).
  3. FLAGGED MONEYLINES OUT. A moneyline is not priced when its two implied
     chances sum outside 1.00-1.15; when its favourite differs from the
     favourite of every other book at the instant (2+ other books, Pinnacle
     and Bovada included); or when the same book's spread (price-valid, line
     1.5 or more) names the other team as favourite.
  4. PRICE FLOOR, BEFORE THE PICK. Every side priced shorter than -200 is
     removed first (mike: "-200 max"), so a game whose best side is -250 is
     bet at its next-best side if that one clears the cut.
  5. BET the single largest edge of the game, edge = P(side wins) minus the
     side's own price's implied probability (vig included), when it is above
     0.01. A tie on edge goes to the longer price, then the book's name in
     alphabetical order (the same bet at two books; the name only says which).
  A game that tips less than five minutes after 15:00 UTC is not priced.
  6. FEED TYPOS OUT, FIRST (models/ncaab_quote_bounds.py). A moneyline with a
     price beyond +/-100000 (-100000 itself is a real quote), and a spread
     beyond +/-60 or with a price beyond +/-100000, is dropped before any flag
     or count reads it; that book has no such quote at the instant. A best
     edge above the data-error cap is not a bet: the game is decided as
     edge_cap with none, and the card's run fails.

Each game is decided once (CLAUDE.md section 1c): bet or not, never looked at
again, and a moved price writes nothing.

THE PROBABILITY (what model_probability holds): P(the bet side wins) from the
bet book's own spread, the number the 0.01 cut was measured on. decision_edge
is that minus the bet price's implied, so the publishers' 0.01 edge filter
agrees with the card exactly. The model decides on its own number
(config.MODELS_ON_OWN_PROBABILITY): it has no record to fit a map on.

THE ID has 'spread' in it but the model bets MONEYLINES. Every place that reads
a market off a model id by substring names this id first (the app's
markets.ts, the Claude-mobile prompt); tests/test_ncaab_moneyline_own_spread.py
pins each one to the moneyline.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from models import ncaab_book_quotes as bq
from models import ncaab_margin_dist as md
from models import ncaab_quote_bounds as qb

MODEL_ID = "ncaab_moneyline_own_spread"
SPORT = "NCAAB"
MARKET = "h2h"

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = "models/saved/ncaab_moneyline_own_spread_2027.json"
ARTIFACT_KIND = "ncaab_moneyline_own_spread"

# The favourite check (step 3) counts these two as "other books" too, as the
# evidence did. They are never bet.
REF_BOOKS = bq.BOOKS + ("pinnacle", "bovada")
CUT = 0.01
MIN_PRICE = -200          # mike, 2026-11-02: "-200 max"
ISUM_LO, ISUM_HI = 1.0, 1.15
DISAGREE_LINE = 1.5       # a same-book spread this big or bigger must agree on the favourite
MIN_LEAD = timedelta(minutes=5)


def dec(american) -> np.ndarray:
    """Decimal odds, vectorised, the research's own arithmetic."""
    a = np.asarray(american, dtype=float)
    return np.where(a > 0, 1 + a / 100.0, 1 + 100.0 / np.abs(a))


def power_fair(p1, p2) -> tuple[np.ndarray, np.ndarray]:
    """Power de-vig of two implied probabilities: the k with p1^k + p2^k = 1,
    by 60 halvings of [0.5, 3.0]. The research's own routine, unchanged, so
    the replay reproduces its numbers to the bit."""
    p1 = np.asarray(p1, float)
    p2 = np.asarray(p2, float)
    lo = np.full(p1.shape, 0.5)
    hi = np.full(p1.shape, 3.0)
    for _ in range(60):
        k = (lo + hi) / 2
        s = p1 ** k + p2 ** k
        lo = np.where(s > 1, k, lo)
        hi = np.where(s > 1, hi, k)
    k = (lo + hi) / 2
    return p1 ** k, p2 ** k


def pair_ok(a, b) -> tuple[np.ndarray, np.ndarray]:
    """(both prices finite and -100/+100 or longer, the two implied chances'
    sum; NaN where not ok)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b) & (np.abs(a) >= 100) & (np.abs(b) >= 100)
    s = np.where(ok, 1 / dec(np.where(ok, a, 100)) + 1 / dec(np.where(ok, b, 100)), np.nan)
    return ok, s


def too_close(tip, instant) -> bool:
    """A game that tips less than five minutes after its 15:00 UTC is never
    priced (the evidence's rule for every instant it used)."""
    return pd.Timestamp(instant) > pd.Timestamp(tip) - MIN_LEAD


# ── the two reads ─────────────────────────────────────────────────────────────

def moneyline_quotes(rows: pd.DataFrame, window_min: int | None = bq.WINDOW_MIN) -> pd.DataFrame:
    """Every REF_BOOKS moneyline standing at its game's instant, with its flags.

    rows: stored h2h odds rows (models/ncaab_book_quotes.load_rows with
    market='h2h' and books=REF_BOOKS, or the replay's history), p1 / p2 the
    home / away prices. A quote with a price inside -100..+100 is dropped.
    Adds isum, pq (power de-vigged P(home)), fav (+1 home, -1 away, 0 even),
    overround_bad and fav_alone. spread_disagree and flag_any are added by
    flag_moneylines, which needs the spreads. window_min: the freshness window
    (models/ncaab_book_quotes.standing_quotes; None = the newest row however
    old, the first-post model's read)."""
    q = bq.standing_quotes(rows, window_min=window_min, books=REF_BOOKS, need_line=False)
    ok, s = pair_ok(q["p1"], q["p2"]) if len(q) else (np.zeros(0, bool), np.zeros(0))
    q = q[ok].copy()
    q["isum"] = s[ok]
    q["pq"] = power_fair(1 / dec(q["p1"]), 1 / dec(q["p2"]))[0] if len(q) else np.zeros(0)
    q["overround_bad"] = (q["isum"] < ISUM_LO) | (q["isum"] > ISUM_HI)
    q["fav"] = np.sign(q["pq"] - 0.5)
    # The favourite alone: 2+ other books at the instant (overround quotes
    # left out of the count), every one of them with the other favourite.
    good = ~q["overround_bad"]
    g = q.assign(_n=good.astype(int), _h=(good & (q["fav"] > 0)).astype(int),
                 _a=(good & (q["fav"] < 0)).astype(int))
    tot = g.groupby("game_id")[["_n", "_h", "_a"]].transform("sum")
    own = good.astype(int)
    oth = tot["_n"] - own
    oh = tot["_h"] - own * (q["fav"] > 0)
    oa = tot["_a"] - own * (q["fav"] < 0)
    q["fav_alone"] = (oth >= 2) & (((q["fav"] > 0) & (oa == oth)) | ((q["fav"] < 0) & (oh == oth)))
    return q.reset_index(drop=True)


def spread_quotes(rows: pd.DataFrame, table: dict,
                  window_min: int | None = bq.WINDOW_MIN) -> pd.DataFrame:
    """Every bettable book's spread standing at its game's instant
    (models/ncaab_book_quotes.snapshot: the sign-error flag over the eight
    books), with sp_valid (prices -100/+100 or longer, implied sum 1.00-1.15),
    own_ok (sp_valid and not flagged), and, where own_ok, pcov (P home covers
    | no push, power de-vigged), mu (the expected home margin that gives it at
    the book's line) and ph_own (P home wins at that mean). window_min as in
    moneyline_quotes."""
    q = bq.snapshot(rows, window_min)
    if not len(q):
        for c in ("sp_valid", "own_ok"):
            q[c] = pd.Series(dtype=bool)
        for c in ("pcov", "mu", "ph_own"):
            q[c] = pd.Series(dtype=float)
        return q
    ok, s = pair_ok(q["p1"], q["p2"])
    q["sp_valid"] = ok & (s >= ISUM_LO) & (s <= ISUM_HI)
    q["own_ok"] = q["sp_valid"] & (q["flag"] == "ok")
    v = q["own_ok"].to_numpy(bool)
    q["pcov"] = np.nan
    q["mu"] = np.nan
    q["ph_own"] = np.nan
    if v.any():
        pcov = power_fair(1 / dec(q["p1"].to_numpy(float)[v]), 1 / dec(q["p2"].to_numpy(float)[v]))[0]
        mu = md.mean_for_cover(pcov, -q["line"].to_numpy(float)[v], table)
        pw, pp, pl = md.probs(mu, np.zeros(int(v.sum())), table)
        q.loc[v, "pcov"] = pcov
        q.loc[v, "mu"] = mu
        q.loc[v, "ph_own"] = pw / (pw + pl)
    return q


def flag_moneylines(ml: pd.DataFrame, sp: pd.DataFrame) -> pd.DataFrame:
    """Add own_line (the same book's price-valid spread line, crossing or
    not), spread_disagree and flag_any."""
    same = sp[sp["sp_valid"]][["game_id", "bookmaker", "line"]].rename(columns={"line": "own_line"}) \
        if len(sp) else pd.DataFrame(columns=["game_id", "bookmaker", "own_line"])
    q = ml.merge(same, on=["game_id", "bookmaker"], how="left")
    ol = pd.to_numeric(q["own_line"], errors="coerce")
    q["spread_disagree"] = (ol.notna() & (ol.abs() >= DISAGREE_LINE)
                            & (-np.sign(ol) != q["fav"]) & (q["fav"] != 0))
    q["flag_any"] = q["overround_bad"] | q["fav_alone"] | q["spread_disagree"]
    return q


# ── pricing ───────────────────────────────────────────────────────────────────

SIDE_COLS = ["game_id", "bookmaker", "side", "price", "dec", "implied", "prob", "edge",
             "own_line", "mu", "ph_own", "link"]


def price_sides(ml: pd.DataFrame, sp: pd.DataFrame, min_price: float = MIN_PRICE) -> pd.DataFrame:
    """Both sides of every bettable book's unflagged moneyline whose own
    spread is usable, priced; sides shorter than min_price are removed HERE,
    before any pick. side: 'home' | 'away'."""
    h = ml[ml["bookmaker"].isin(bq.BOOKS) & ~ml["flag_any"]]
    f = sp[sp["own_ok"]][["game_id", "bookmaker", "mu", "ph_own"]] if len(sp) else \
        pd.DataFrame(columns=["game_id", "bookmaker", "mu", "ph_own"])
    h = h.merge(f, on=["game_id", "bookmaker"], how="inner")
    h = h[h["ph_own"].notna()]
    out = []
    for side, pc, lc in (("home", "p1", "link1"), ("away", "p2", "link2")):
        z = h[["game_id", "bookmaker", "own_line", "mu", "ph_own"]].copy()
        z["side"] = side
        z["price"] = h[pc].to_numpy(float)
        z["link"] = h[lc].to_numpy(object) if lc in h.columns else None
        z["dec"] = dec(z["price"])
        z["implied"] = 1 / z["dec"]
        z["prob"] = z["ph_own"] if side == "home" else 1 - z["ph_own"]
        z["edge"] = z["prob"] - z["implied"]
        out.append(z)
    if not out or not len(h):
        return pd.DataFrame(columns=SIDE_COLS)
    z = pd.concat(out, ignore_index=True)
    return z[z["price"] >= min_price][SIDE_COLS].reset_index(drop=True)


def best_per_game(z: pd.DataFrame, bettable=None) -> pd.DataFrame:
    """The single largest-edge side per game; a tie goes to the longer price,
    then a book in `bettable` (None: every book is), then the book's name.

    A tie on edge and price is the same bet at two books, so the bettable book
    takes it (mike, 2026-11-07: of the 38 replayed bets betPARX held, 36 were
    exact ties with a book that can still be bet). With every book bettable the
    order is the evidence's exactly."""
    z = z[z["edge"].notna()].copy()
    z["_unbettable"] = 0 if bettable is None else (~z["bookmaker"].isin(list(bettable))).astype(int)
    z = z.sort_values(["game_id", "edge", "dec", "_unbettable", "bookmaker"],
                      ascending=[True, False, False, True, True], kind="mergesort")
    return z.drop_duplicates("game_id", keep="first").drop(columns=["_unbettable"])


# ── the artifact ──────────────────────────────────────────────────────────────

def table_digest(margin_table_json: dict) -> str:
    """SHA-256 of a margin table's JSON (models/ncaab_margin_dist.to_json),
    keys sorted: the identity the artifact pins."""
    return hashlib.sha256(json.dumps(margin_table_json, sort_keys=True).encode("utf-8")).hexdigest()


def load_artifact(path: str | Path | None = None) -> dict:
    """The frozen numbers, with the margin table rebuilt (art["table"]).

    The table is not copied into this artifact: it is the spread model's
    (the same fit, 2012 through the last finished season, which the build
    checked equal), read from the file this artifact names and refused unless
    its digest matches the one recorded at build time."""
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
    if table_digest(other["margin_table"]) != art["margin_table_sha256"]:
        raise ValueError(f"{src}: its margin table is not the one {p.name} was built on "
                         f"(digest differs); rebuild with scripts/ncaab_moneyline_build.py")
    art["table"] = md.from_json(other["margin_table"])
    return art


# ── the decision ──────────────────────────────────────────────────────────────

DIAG_KEYS = ("games", "already_decided", "no_quotes", "no_clean_quote", "below_cut",
             "book_not_bettable", "edge_cap", "bets", "missed", "tipped", "quotes_dropped",
             "other_model_bet")


@dataclass
class Decision:
    game_id: str
    status: str                      # a DIAG key
    detail: str
    best: dict | None = None         # the priced best side (a row of price_sides)
    quotes: list = field(default_factory=list)   # every book's moneyline and own spread
    dk: dict | None = None           # DraftKings' own moneyline, when it had a clean one


def _f(v):
    return None if v is None or (isinstance(v, float) and v != v) else float(v)


def _quote_list(ml: pd.DataFrame, sp: pd.DataFrame) -> list[dict]:
    spd = {r.bookmaker: r for r in sp.itertuples(index=False)} if len(sp) else {}
    out = []
    for r in ml.sort_values("bookmaker").itertuples(index=False):
        s = spd.get(r.bookmaker)
        flags = [n for n in ("overround_bad", "fav_alone", "spread_disagree") if bool(getattr(r, n))]
        out.append({"book": r.bookmaker, "p1": float(r.p1), "p2": float(r.p2),
                    "ts": pd.Timestamp(r.ts).isoformat(), "flags": flags,
                    "spread": None if s is None else float(s.line),
                    "spread_p1": None if s is None else float(s.p1),
                    "spread_p2": None if s is None else float(s.p2),
                    "spread_ok": None if s is None else bool(s.own_ok),
                    "ph_own": None if s is None else _f(s.ph_own)})
    for b, s in sorted(spd.items()):
        if b not in set(ml["bookmaker"]):
            out.append({"book": b, "p1": None, "p2": None, "ts": None, "flags": ["no_moneyline"],
                        "spread": float(s.line), "spread_p1": float(s.p1), "spread_p2": float(s.p2),
                        "spread_ok": bool(s.own_ok), "ph_own": _f(s.ph_own)})
    return out


def _dropped_list(dropped: pd.DataFrame | None) -> dict[str, list[dict]]:
    """{game_id: [quote dropped as a data error, as the decision row lists it]}."""
    out: dict[str, list[dict]] = {}
    if dropped is None or not len(dropped):
        return out
    for r in dropped.sort_values(["game_id", "market", "bookmaker"]).to_dict("records"):
        line = r.get("line")
        out.setdefault(r["game_id"], []).append({
            "book": r["bookmaker"], "market": r["market"],
            "line": None if line is None or pd.isna(line) else float(line),
            "p1": _f(r.get("p1")), "p2": _f(r.get("p2")), "flags": ["out_of_range"],
            "why": r["why"]})
    return out


def decide(game_ids, ml: pd.DataFrame, sp: pd.DataFrame, cut: float,
           bettable=bq.BOOKS, min_price: float = MIN_PRICE,
           dropped: pd.DataFrame | None = None) -> list[Decision]:
    """Decide each game at its 15:00 UTC read. Pure given its inputs.

    ml: flag_moneylines output; sp: spread_quotes output, for these games.
    bettable: the books a bet may be placed at now
    (config.BEST_LINE_BOOKMAKERS); the best side is chosen over the eight
    books first, as the evidence chose it, and a best side at a book not
    bettable now is not replaced by the next one. An exact tie (same edge and
    price) is the same bet, so it goes to the bettable book (best_per_game). dropped: the moneylines and
    spreads the read dropped as data errors (models/ncaab_book_quotes
    .dropped_quotes, with `market`), listed in each game's decision; nothing
    is priced from them."""
    out: list[Decision] = []
    drops = _dropped_list(dropped)
    ml_by = {g: x for g, x in ml.groupby("game_id")} if len(ml) else {}
    sp_by = {g: x for g, x in sp.groupby("game_id")} if len(sp) else {}
    sides = price_sides(ml, sp, min_price)
    best = best_per_game(sides, bettable).set_index("game_id") if len(sides) else None
    for gid in game_ids:
        m = ml_by.get(gid)
        s = sp_by.get(gid, sp.iloc[0:0] if len(sp) else pd.DataFrame())
        mb = m[m["bookmaker"].isin(bq.BOOKS)] if m is not None else None
        dg = drops.get(gid, [])
        note = ("; dropped as data errors: " + ", ".join(
            f"{x['book']} {x['market']} ({x['why']})" for x in dg)) if dg else ""
        if mb is None or not len(mb):
            out.append(Decision(gid, "no_quotes", "no bettable book quoted a moneyline in the hour "
                                                  "before 15:00 UTC" + note,
                                quotes=(_quote_list(m, s) if m is not None else []) + dg))
            continue
        quotes = _quote_list(m, s) + dg
        dkq = mb[(mb["bookmaker"] == "draftkings") & ~mb["flag_any"]]
        dk = None
        if len(dkq):
            r = dkq.iloc[0]
            dk = {"p1": float(r.p1), "p2": float(r.p2), "link1": r.get("link1"), "link2": r.get("link2")}
        if best is None or gid not in best.index:
            out.append(Decision(gid, "no_clean_quote", "no unflagged moneyline with a usable spread "
                                                       f"at the same book and a price of {min_price:+.0f} "
                                                       "or longer" + note, quotes=quotes, dk=dk))
            continue
        b = best.loc[gid].to_dict()
        b["game_id"] = gid
        desc = (f"{b['bookmaker']} {b['side']} {b['price']:+.0f} edge {b['edge']:+.4f} "
                f"p {b['prob']:.4f} own spread {b['own_line']:+g} mean {b['mu']:+.2f} "
                f"books {int(mb['bookmaker'].nunique())}")
        capped = qb.edge_problem(b["edge"], MODEL_ID)
        if capped:
            status = "edge_cap"
            desc += f"; {capped}: a data error, not a bet"
        elif not b["edge"] > cut:
            status = "below_cut"
        elif b["bookmaker"] not in bettable:
            status = "book_not_bettable"
            desc += "; that book is not in config.BEST_LINE_BOOKMAKERS"
        else:
            status = "bets"
        out.append(Decision(gid, status, desc + note, best=b, quotes=quotes, dk=dk))
    return out


def read(ml_rows: pd.DataFrame, sp_rows: pd.DataFrame, table: dict,
         window_min: int | None = bq.WINDOW_MIN) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The whole 15:00 UTC read from raw rows carrying instant and tip:
    (flag_moneylines output, spread_quotes output). window_min=None is the
    first-post model's read (models/ncaab_moneyline_first_post.py): each
    book's newest row however old."""
    sp = spread_quotes(sp_rows, table, window_min)
    ml = flag_moneylines(moneyline_quotes(ml_rows, window_min), sp)
    return ml, sp
