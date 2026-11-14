"""EuroLeague pre-game rules: five rule cards, each the research's own rule.

LIVE, real money (mike, 2026-11-14: "I told you to build all the models"),
knowing each one MISSED part of the research bar; docs/sports/euroleague.md
says what each missed. The card is scripts/euroleague_pregame_card.py; the
build that replays the research bet for bet is
scripts/euroleague_pregame_build.py; the artifact is
models/saved/euroleague_pregame_<season>.json.

THE FIVE RULES (each decided once a game, at the research's decision time,
tip minus 10 minutes; the books a pick may name are DECIDABLE, less any
config.BEST_LINE_BOOKMAKERS no longer lists):

  euroleague_home_ml            the home moneyline at the close, when the home
                                price is -200 or longer (round 2, A1). Not at a
                                neutral site.
  euroleague_heavy_fav_ml       the moneyline favourite at the close, when its
                                price is -500 or shorter (full game round 1,
                                lead iii). Every game, neutral ones included.
  euroleague_home_dog_spread    the home underdog against the spread at the
                                close: the home number above 0 (full game round
                                1, H3). Own-country games only: not neutral, not
                                at a relocated venue (RELOCATED_VENUES).
  euroleague_h1_dog_ml          the first-half moneyline underdog at the close
                                (first half round 1, the best baseline). A tied
                                half pushes.
  euroleague_q1_club_share_total
                                the first-quarter total against each club's
                                prior-games first-quarter share of the full-game
                                total (round 2, Q1-i at margin 1.0).

WHAT EACH RULE READS. The full-game rules read the BOARD at the decision
instant: per (game, market, book), the newest coherent stored quote stamped at
or before it (r2_lib.board_at). The period rules read the quotes of ONE fetch:
the per-event call made ten minutes before tip
(data/ingestors/euroleague_period_odds.py), as the research read the purchase's
call made at that mark.

THE PRICE A PICK IS DECIDED AT (CLAUDE.md 6): the best price across the
deciding books, as every research rule's "best decidable" read. Run with
books=("draftkings",) the same code reproduces the research's DraftKings reads
(the build prints both).

THE PROBABILITY. A blind rule has no model probability of its own. Each pick
carries the market's no-vig chance of the bet side (power de-vig for the
full-game moneyline, multiplicative otherwise, as the research priced it) plus
the rule's walk-forward uplift: the realised win share minus that mean no-vig
chance over the replayed bets of the seasons before the live one (pushes out),
stored in the artifact. The EV floor and the edge cut (config) sit under every
replayed bet: the rule is the cut.

Pure: no database, no network. The card reads; this decides.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

SPORT = "EUROLEAGUE"
HOME_ML = "euroleague_home_ml"
HEAVY_FAV_ML = "euroleague_heavy_fav_ml"
HOME_DOG_SPREAD = "euroleague_home_dog_spread"
H1_DOG_ML = "euroleague_h1_dog_ml"
Q1_SHARE_TOTAL = "euroleague_q1_club_share_total"
MODELS = (HOME_ML, HEAVY_FAV_ML, HOME_DOG_SPREAD, H1_DOG_ML, Q1_SHARE_TOTAL)
FULL_GAME_MODELS = (HOME_ML, HEAVY_FAV_ML, HOME_DOG_SPREAD)
PERIOD_MODELS = (H1_DOG_ML, Q1_SHARE_TOTAL)
# The market each pick settles on (tracking/paper_tracker._RULE_MODEL_MARKETS).
MARKET = {HOME_ML: "h2h", HEAVY_FAV_ML: "h2h", HOME_DOG_SPREAD: "spreads",
          H1_DOG_ML: "h2h_h1", Q1_SHARE_TOTAL: "totals_q1"}
# The research's books a pick may name (r2_lib.DECIDABLE, r1_lib.DECIDABLE).
DECIDABLE = ("draftkings", "fanduel", "betmgm", "betrivers", "fanatics")
REFERENCE_BOOK = "draftkings"
SHARP = "pinnacle"

# The research's period markets: the main number of each (r1_lib.MARKETS).
PERIOD_MAIN_MARKETS = ("spreads_h1", "totals_h1", "h2h_h1", "spreads_q1", "totals_q1", "h2h_q1")
LADDER_MARKET = "alternate_totals"   # Pinnacle's full-game ladder (model 5's anchor)

# Full-game coherence (r2_lib): both prices finite American odds and the two
# implied chances summing to 1.00-1.15.
ISUM_LO, ISUM_HI = 1.00, 1.15
# A period spread/total "main" whose no-vig side chance is outside 0.35-0.65 is
# a rung, not the book's main number (r1_lib.OFFC); so is one 2+ points from
# every other book's main number in the same fetch (r3_lib.period_main).
OFFC = 0.15
FAR_POINTS = 2.0

ARTIFACT_DIR = Path(__file__).resolve().parent / "saved"


def artifact_path(season: int) -> Path:
    return ARTIFACT_DIR / f"euroleague_pregame_{int(season)}.json"


def load_artifact(season: int) -> dict:
    """The built artifact for `season` (scripts/euroleague_pregame_build.py).
    Raises FileNotFoundError when there is none: the card then decides nothing
    for that season and fails its run."""
    with open(artifact_path(season), encoding="utf-8") as fh:
        art = json.load(fh)
    if int(art["season"]) != int(season):
        raise ValueError(f"artifact {artifact_path(season)} is for season {art['season']}")
    return art


# ── prices ──────────────────────────────────────────────────────────────────

def imp(a):
    """American odds -> implied chance (vig in). NaN stays NaN."""
    a = np.asarray(a, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(a > 0, 100 / (a + 100), -a / (-a + 100))


def dec(a):
    a = np.asarray(a, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(a > 0, 1 + a / 100.0, 1 + 100.0 / np.abs(a))


def power_fair(p1, p2):
    """Power de-vig: the k with p1^k + p2^k = 1 (r2_lib.power_fair, verbatim)."""
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


def stake(price):
    """(risk, win) at the posted stake: 1 unit to win, risk capped at 3; an
    underdog risks 1 (r1_lib.stake; config's stake_for)."""
    p = np.asarray(price, float)
    neg = p < 0
    risk = np.where(neg, np.minimum(np.abs(p) / 100.0, 3.0), 1.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        win = np.where(neg, risk * 100.0 / np.abs(p), p / 100.0)
    return risk, win


# ── the full-game board ─────────────────────────────────────────────────────

FULL_GAME_MARKETS = ("h2h", "spreads", "totals")
_PREPARED_COLS = ["game_id", "market", "bookmaker", "snapshot_at", "home_price", "away_price",
                  "spread_home", "total_line", "over_price", "under_price", "line", "pa", "pb",
                  "isum", "pa_mult", "pa_pow", "tip"]


def prepare_fullgame(rows: pd.DataFrame, tips: pd.Series) -> pd.DataFrame:
    """Stored pre-game full-game rows -> coherent quotes (r2_lib.load_quotes).

    rows: game_id, market, bookmaker, snapshot_at, home_price, away_price,
    spread_home, total_line, over_price, under_price. tips: game_id -> tip.
    Adds line (the HOME spread / the total / NaN), pa (home or over), pb (away
    or under), isum, pa_mult (multiplicative no-vig side a), pa_pow (power
    no-vig side a). Keeps rows stamped at or before the tip, sorted by game,
    market, book and stamp; only coherent quotes."""
    if rows.empty or "market" not in rows:
        return pd.DataFrame(columns=_PREPARED_COLS)
    q = rows[rows["market"].isin(FULL_GAME_MARKETS)].copy()
    if q.empty:
        return pd.DataFrame(columns=_PREPARED_COLS)
    for c in ("home_price", "away_price", "spread_home", "total_line", "over_price", "under_price"):
        q[c] = pd.to_numeric(q[c], errors="coerce")
    q["snapshot_at"] = pd.to_datetime(q["snapshot_at"], utc=True, errors="coerce")
    tot = q.market == "totals"
    q["line"] = np.where(q.market == "spreads", q.spread_home, np.where(tot, q.total_line, np.nan))
    q["pa"] = np.where(tot, q.over_price, q.home_price)
    q["pb"] = np.where(tot, q.under_price, q.away_price)
    ok = np.isfinite(q.pa) & np.isfinite(q.pb) & (q.pa.abs() >= 100) & (q.pb.abs() >= 100)
    ok &= (q.market == "h2h") | np.isfinite(q.line)
    ia = np.where(ok, imp(np.where(ok, q.pa, 100)), np.nan)
    ib = np.where(ok, imp(np.where(ok, q.pb, 100)), np.nan)
    q["isum"] = ia + ib
    coherent = ok & (q.isum >= ISUM_LO) & (q.isum <= ISUM_HI)
    q["pa_mult"] = ia / q.isum
    pf = power_fair(np.where(ok, ia, 0.5), np.where(ok, ib, 0.5))[0]
    q["pa_pow"] = np.where(ok, pf, np.nan)
    q["tip"] = pd.to_datetime(q.game_id.map(tips), utc=True)
    q = q[coherent & (q.snapshot_at <= q.tip)]
    q = q.sort_values(["game_id", "market", "bookmaker", "snapshot_at"], kind="mergesort")
    return q.reset_index(drop=True)


def board_at(q: pd.DataFrame, T: pd.Series) -> pd.DataFrame:
    """Per (game, market, book) the newest prepared quote stamped at or before
    T[game] (r2_lib.board_at). T: game_id -> UTC instant."""
    tt = pd.to_datetime(T, utc=True).rename("T").rename_axis("game_id").reset_index()
    z = q.merge(tt, on="game_id", how="inner")
    z = z[z.snapshot_at <= z["T"]]
    return z.drop_duplicates(["game_id", "market", "bookmaker"], keep="last").reset_index(drop=True)


def sides_long(b: pd.DataFrame) -> pd.DataFrame:
    """Each quote as two sides (r2_lib.sides_long): side, price, fair."""
    a = b.copy()
    a["side"] = np.where(a.market == "totals", "over", "home")
    a["price"] = a.pa
    a["fair"] = a.pa_mult
    c = b.copy()
    c["side"] = np.where(c.market == "totals", "under", "away")
    c["price"] = c.pb
    c["fair"] = 1 - c.pa_mult
    z = pd.concat([a, c], ignore_index=True)
    z["fair_pow"] = np.where(z.side == "home", z.pa_pow,
                             np.where(z.side == "away", 1 - z.pa_pow, np.nan))
    return z


def _best_per_side(z: pd.DataFrame) -> pd.DataFrame:
    """The best (highest decimal) price per (game, side); a tie goes to the
    book first in name order (the research's order)."""
    z = z.assign(_dz=dec(z.price))
    z = z.sort_values(["game_id", "side", "_dz", "bookmaker"], ascending=[True, True, False, True],
                      kind="mergesort")
    return z.drop_duplicates(["game_id", "side"], keep="first").drop(columns="_dz")


def modal_line(lines: pd.Series) -> float:
    """The modal number; a tie goes to the one nearest the median, then the
    lower (the repo's same-line rule, r2_leads2.modal / r3_lib.modal_best)."""
    vc = lines.value_counts()
    top = sorted(vc[vc == vc.max()].index, key=lambda v: (abs(v - lines.median()), v))
    return float(top[0])


# ── decisions ───────────────────────────────────────────────────────────────

@dataclass
class Decision:
    """One model's decision on one game. status:
      bet          the rule bets: a BET row
      no_bet       priced, and the rule does not bet: a NONE row at the side
                   and price it would have taken (no stake)
      not_eligible the rule does not price this game (neutral site, relocated
                   venue): ledgered, no row
      no_quotes    no deciding book had the market: ledgered, no row
      no_anchor / no_shares / pick_em   model-specific, ledgered, no row
    """
    game_id: str
    model_id: str
    status: str
    detail: str = ""
    side: str | None = None
    book: str | None = None
    price: float | None = None
    line: float | None = None
    p_fair: float | None = None
    uplift: float | None = None
    p_model: float | None = None
    ev: float | None = None
    edge: float | None = None
    dk_price: float | None = None
    dk_line: float | None = None
    n_books: int | None = None
    extra: dict = field(default_factory=dict)

    @property
    def scored(self) -> bool:
        """Priced: a BET or a NONE row is written."""
        return self.status in ("bet", "no_bet")


def finish(d: Decision, uplift: float | None) -> Decision:
    """p_model, EV and edge from p_fair and the uplift. None uplift: the
    research's grading has no probability, so the three stay None."""
    if d.price is None or d.p_fair is None or uplift is None or not np.isfinite(d.p_fair):
        return d
    d.uplift = float(uplift)
    d.p_model = float(min(max(d.p_fair + uplift, 0.01), 0.99))
    d.ev = float(d.p_model * float(dec(d.price)) - 1.0)
    d.edge = float(d.p_model - float(imp(d.price)))
    return d


def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _dk_quote(rows: pd.DataFrame, side: str, line: float | None = None) -> tuple:
    """DraftKings' own price on `side` (and its number), the reference."""
    r = rows[rows.bookmaker == REFERENCE_BOOK]
    if line is not None and "line" in r:
        r = r[r.line == line]
    if r.empty:
        return None, None
    r = r.iloc[-1]
    price = r.pa if side in ("home", "over") else r.pb
    return _num(price), _num(r.get("line"))


def _by_game(df: pd.DataFrame) -> dict:
    """{game_id: its rows}, the rows' order kept."""
    if df.empty:
        return {}
    return {g: x for g, x in df.groupby("game_id", sort=False)}


_NONE = pd.DataFrame()


def _games(games: pd.DataFrame) -> pd.DataFrame:
    g = games.copy()
    if "neutral_site" not in g:
        g["neutral_site"] = False
    g["neutral_site"] = g["neutral_site"].fillna(False).astype(bool)
    return g


def decide_home_ml(board: pd.DataFrame, games: pd.DataFrame, art: dict,
                   books=DECIDABLE) -> list[Decision]:
    """Model 1 (r3_a_home.a1): the home side at the best deciding-book close,
    every quote shorter than the floor removed BEFORE the best is picked."""
    p = art["models"][HOME_ML]["params"]
    floor, min_season = float(p["min_price"]), int(p["min_season"])
    out = []
    g = _games(games)
    h2h = _by_game(board[(board.market == "h2h") & board.bookmaker.isin(books)])
    for row in g.itertuples(index=False):
        gid = row.game_id
        if bool(row.neutral_site):
            out.append(Decision(gid, HOME_ML, "not_eligible", "neutral site"))
            continue
        if int(row.season) < min_season:
            out.append(Decision(gid, HOME_ML, "not_eligible", f"season before {min_season}"))
            continue
        b = h2h.get(gid, _NONE)
        if b.empty:
            out.append(Decision(gid, HOME_ML, "no_quotes", "no deciding book has a moneyline"))
            continue
        z = sides_long(b)
        home = z[z.side == "home"]
        ok = home[home.price >= floor]
        dk_price, _ = _dk_quote(b, "home")
        fair = float(np.nanmean(home.fair_pow))
        if ok.empty:
            best = _best_per_side(home).iloc[0]
            out.append(Decision(gid, HOME_ML, "no_bet",
                                f"home {best.price:+.0f} at its best book, shorter than {floor:+.0f}",
                                side="home", book=best.bookmaker, price=float(best.price),
                                p_fair=fair, dk_price=dk_price, n_books=int(len(home))))
            continue
        best = _best_per_side(ok).iloc[0]
        out.append(Decision(gid, HOME_ML, "bet", f"home {best.price:+.0f} at {best.bookmaker}",
                            side="home", book=best.bookmaker, price=float(best.price),
                            p_fair=float(np.nanmean(ok.fair_pow)), dk_price=dk_price,
                            n_books=int(len(ok))))
    return out


def decide_heavy_fav(board: pd.DataFrame, games: pd.DataFrame, art: dict,
                     books=DECIDABLE) -> list[Decision]:
    """Model 2 (r2_kill section 2 at DraftKings; r2_baselines.best_decidable's
    <=-500 band at the best deciding book): the side whose best price is the
    cutoff or shorter. Neutral sites included, as the research's games were."""
    p = art["models"][HEAVY_FAV_ML]["params"]
    cutoff = float(p["max_price"])
    out = []
    h2h = _by_game(board[(board.market == "h2h") & board.bookmaker.isin(books)])
    for gid in games.game_id:
        b = h2h.get(gid, _NONE)
        if b.empty:
            out.append(Decision(gid, HEAVY_FAV_ML, "no_quotes", "no deciding book has a moneyline"))
            continue
        z = sides_long(b)
        best = _best_per_side(z).set_index("side")
        fair = {s: float(np.nanmean(z[z.side == s].fair_pow)) for s in ("home", "away")}
        hits = best[best.price <= cutoff]
        if len(hits):
            side = hits.index[0]
            r = hits.iloc[0]
            status, detail = "bet", f"{side} {r.price:+.0f} at {r.bookmaker}"
        else:
            # the favourite by its best price (the shorter one); level: home
            dz = {s: float(dec(best.loc[s, "price"])) for s in best.index}
            side = "home" if dz.get("home", math.inf) <= dz.get("away", math.inf) else "away"
            r = best.loc[side]
            status, detail = "no_bet", f"favourite {side} {r.price:+.0f}, longer than {cutoff:+.0f}"
        dk_price, _ = _dk_quote(b, side)
        out.append(Decision(gid, HEAVY_FAV_ML, status, detail, side=side, book=r.bookmaker,
                            price=float(r.price), p_fair=fair[side], dk_price=dk_price,
                            n_books=int((z.side == side).sum())))
    return out


def relocated(home_code: str, venue) -> str | None:
    """'R1', 'R2' or 'excluded' when this home club's venue is on the
    research's relocated lists (r2_leads R1/R2/EXCL), else None."""
    if venue is None or (isinstance(venue, float) and venue != venue):
        return None
    return None if home_code is None else _RELOCATED.get((str(home_code), str(venue).strip()))


# r2_leads.py's lists, unchanged (the research named them from the stored
# venue names). A relocation decided after 2026-11-12 is not on them: an open
# item in docs/sports/euroleague.md.
RELOCATED_VENUES = {
    "R1": [("TEL", "ALEKSANDAR NIKOLIC HALL"), ("TEL", "BELGRADE ARENA"),
           ("TEL", "SPYROS KYPRIANOU ATHLETIC CENTER"), ("HTA", "ARENA 8888 SOFIA"),
           ("HTA", "ARENA BOTEVGRAD"), ("DUB", "ZETRA ARENA"),
           ("DUB", "ARENA HUSEJIN SMAJLOVIC ZENICA")],
    "R2": [("IST", "MORACA"), ("IST", "ARENA RIGA"), ("ULK", "SAP GARDEN"),
           ("ULK", "KALNAPILIO ARENA"), ("ULK", "ZALGIRIO ARENA"), ("PAR", "BMW PARK")],
    "excluded": [("IST", "XIAOMI ARENA")],
}
_RELOCATED = {tuple(k): grp for grp, keys in RELOCATED_VENUES.items() for k in keys}


def decide_home_dog(board: pd.DataFrame, games: pd.DataFrame, art: dict,
                    books=DECIDABLE) -> list[Decision]:
    """Model 3 (r2_leads2 H3, home line > 0): the home side on the modal
    deciding-book number at its best price, when that number is above 0.
    Own-country games only."""
    p = art["models"][HOME_DOG_SPREAD]["params"]
    min_line = float(p["min_home_line"])
    out = []
    g = _games(games)
    sp = _by_game(board[(board.market == "spreads") & board.bookmaker.isin(books)])
    for row in g.itertuples(index=False):
        gid = row.game_id
        if bool(row.neutral_site):
            out.append(Decision(gid, HOME_DOG_SPREAD, "not_eligible", "neutral site"))
            continue
        grp = relocated(row.home_code, getattr(row, "venue_name", None))
        if grp:
            out.append(Decision(gid, HOME_DOG_SPREAD, "not_eligible",
                                f"relocated venue ({grp}): {getattr(row, 'venue_name', '')}"))
            continue
        b = sp.get(gid, _NONE)
        if b.empty:
            out.append(Decision(gid, HOME_DOG_SPREAD, "no_quotes", "no deciding book has a spread"))
            continue
        line = modal_line(b.line)
        on = b[b.line == line]
        z = sides_long(on)
        best = _best_per_side(z[z.side == "home"]).iloc[0]
        dk_price, dk_line = _dk_quote(b, "home")
        status = "bet" if line > min_line else "no_bet"
        detail = (f"home {line:+g} at {best.bookmaker} {best.price:+.0f}" if status == "bet"
                  else f"home {line:+g}: not an underdog")
        out.append(Decision(gid, HOME_DOG_SPREAD, status, detail, side="home", book=best.bookmaker,
                            price=float(best.price), line=line,
                            p_fair=float(np.nanmean(z[z.side == "home"].fair)),
                            dk_price=dk_price, dk_line=dk_line, n_books=int(len(on))))
    return out


# ── the period fetch ────────────────────────────────────────────────────────

def prepare_period(rows: pd.DataFrame) -> pd.DataFrame:
    """One fetch's stored period rows -> main quotes with the rung flags
    (r1_lib.load_main_quotes, r3_lib.period_main): line, pa, pb, pa_fair,
    offc, far, rung. Every book is kept: the 'far' rule compares each main
    number with every other book's, the reference books included."""
    q = rows[rows["market"].isin(PERIOD_MAIN_MARKETS)].copy().reset_index(drop=True)
    if q.empty:
        return q.assign(line=[], pa=[], pb=[], pa_fair=[], offc=[], far=[], rung=[])
    for c in ("home_price", "away_price", "spread_home", "total_line", "over_price", "under_price"):
        q[c] = pd.to_numeric(q[c], errors="coerce")
    tot = q.market.str.startswith("totals")
    q["line"] = np.where(q.market.str.startswith("spreads"), q.spread_home,
                         np.where(tot, q.total_line, np.nan))
    q["pa"] = np.where(tot, q.over_price, q.home_price)
    q["pb"] = np.where(tot, q.under_price, q.away_price)
    s = imp(q.pa) + imp(q.pb)
    q["pa_fair"] = imp(q.pa) / s
    q["offc"] = (~q.market.str.startswith("h2h")) & ((q.pa_fair - 0.5).abs() > OFFC)
    q["_rid"] = np.arange(len(q))
    st = q[~q.market.str.startswith("h2h")][["_rid", "game_id", "market", "bookmaker", "line"]]
    m = st.merge(st, on=["game_id", "market"], suffixes=("", "_o"))
    m = m[m._rid != m._rid_o]
    m["d"] = (m.line - m.line_o).abs()
    mind = m.groupby("_rid").d.min()
    q["far"] = q._rid.map(mind).fillna(0.0).to_numpy() >= FAR_POINTS
    q["rung"] = q.offc | q.far
    return q.drop(columns="_rid")


def decide_h1_dog(period: pd.DataFrame, games: pd.DataFrame, art: dict,
                  books=DECIDABLE) -> list[Decision]:
    """Model 4 (r1_baselines.best_decidable, side 'dog'): the first-half
    moneyline side whose mean deciding-book no-vig chance is under one half,
    at its best deciding-book price. A level mean is a pick'em: no bet.
    `period`: prepare_period() of the decision fetch."""
    out = []
    x = _by_game(period[(period.market == "h2h_h1") & period.bookmaker.isin(books) & ~period.offc])
    for gid in games.game_id:
        y = x.get(gid, _NONE)
        if y.empty:
            out.append(Decision(gid, H1_DOG_ML, "no_quotes",
                                "no deciding book has a first-half moneyline in the fetch"))
            continue
        fair = float(y.pa_fair.mean())
        if not np.isfinite(fair) or np.isclose(fair, 0.5):
            out.append(Decision(gid, H1_DOG_ML, "pick_em", f"mean no-vig home chance {fair:.4f}"))
            continue
        fav_home = fair > 0.5
        side = "away" if fav_home else "home"
        col = "pb" if side == "away" else "pa"
        i = y[col].idxmax()
        price, book = float(y.loc[i, col]), str(y.loc[i, "bookmaker"])
        dk = y[y.bookmaker == REFERENCE_BOOK]
        dk_price = _num(dk[col].iloc[0]) if len(dk) else None
        out.append(Decision(gid, H1_DOG_ML, "bet", f"{side} {price:+.0f} at {book}", side=side,
                            book=book, price=price, p_fair=(1 - fair) if fav_home else fair,
                            dk_price=dk_price, n_books=int(y[col].notna().sum()),
                            extra={"mean_home_fair": round(fair, 6)}))
    return out


# ── model 5: the club first-quarter share ───────────────────────────────────

def ladder_fair(rows: pd.DataFrame) -> float | None:
    """Pinnacle's full-game ladder: where the no-vig over chance crosses one
    half, linear between the two bracketing numbers, the first crossing
    (r3_lib.pin_ladder). rows: one fetch's alternate_totals at Pinnacle."""
    x = rows[["total_line", "over_price", "under_price"]].copy()
    for c in x.columns:
        x[c] = pd.to_numeric(x[c], errors="coerce")
    x["pa"] = imp(x.over_price) / (imp(x.over_price) + imp(x.under_price))
    x = x.sort_values("total_line", kind="mergesort").reset_index(drop=True)
    v, p = x.total_line.to_numpy(float), x.pa.to_numpy(float)
    for i in range(len(v) - 1):
        lo, hi = p[i], p[i + 1]
        if (lo - 0.5) * (hi - 0.5) <= 0 and lo != hi:
            return float(v[i] + (0.5 - lo) * (v[i + 1] - v[i]) / (hi - lo))
    return None


def anchor(fetch_rows: pd.DataFrame, fg_board: pd.DataFrame, game_id: str) -> tuple:
    """(full-game total, its source) for model 5 (r3_d_periods.anchors):
    Pinnacle's ladder fair in the same fetch, else Pinnacle's main total on the
    full-game board at the fetch, else DraftKings'."""
    lad = fetch_rows
    if len(lad):
        lad = lad[(lad.game_id == game_id) & (lad.market == LADDER_MARKET) & (lad.bookmaker == SHARP)]
    if len(lad):
        f = ladder_fair(lad)
        if f is not None and np.isfinite(f):
            return f, "pinnacle ladder"
    tb = fg_board
    if not len(tb):
        return None, "none"
    tb = tb[(tb.game_id == game_id) & (tb.market == "totals")]
    for book, src in ((SHARP, "pinnacle main"), (REFERENCE_BOOK, "draftkings main")):
        r = tb[tb.bookmaker == book]
        if len(r) and np.isfinite(r.line.iloc[-1]):
            return float(r.line.iloc[-1]), src
    return None, "none"


def share_history(games: pd.DataFrame, periods: pd.DataFrame) -> pd.DataFrame:
    """Played games with a first-quarter total and a final (r1_lib.load_games
    + r3_d_periods.club_shares' filter): game_id, tip, home_code, away_code,
    share = first-quarter points / final points (overtime in), sorted by tip."""
    p1 = periods[periods["period"] == 1][["game_id", "home_points", "away_points"]]
    g = games.merge(p1, on="game_id", how="left")
    g["q1_total"] = pd.to_numeric(g.home_points, errors="coerce") + pd.to_numeric(g.away_points, errors="coerce")
    g["fg_total"] = pd.to_numeric(g.home_score, errors="coerce") + pd.to_numeric(g.away_score, errors="coerce")
    g["tip"] = pd.to_datetime(g.commence_time, utc=True)
    played = g["played"].fillna(False).astype(bool) if "played" in g else g.home_score.notna()
    g = g[played & g.q1_total.notna() & (g.fg_total > 0)].copy()
    g["share"] = g.q1_total / g.fg_total
    return g.sort_values("tip", kind="mergesort")[["game_id", "tip", "home_code", "away_code", "share"]] \
        .reset_index(drop=True)


def pair_share(history: pd.DataFrame, tip, home: str, away: str, k: float,
               gap_hours: float) -> dict | None:
    """The league's mean share over every game tipping at least `gap_hours`
    before `tip`, plus each club's shrunk deviation over its own earlier games
    (sum(share - league) / (n + k)); None with no earlier game. Summed in tip
    order, as r3_d_periods.club_shares accumulates."""
    t = pd.Timestamp(tip)
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    prior = history[history.tip <= t - pd.Timedelta(hours=gap_hours)]
    if prior.empty:
        return None
    lsum = 0.0
    csum: dict[str, float] = {}
    cn: dict[str, int] = {}
    for s, h, a in zip(prior.share.to_numpy(float), prior.home_code, prior.away_code):
        lsum += float(s)
        for c in (h, a):
            csum[c] = csum.get(c, 0.0) + float(s)
            cn[c] = cn.get(c, 0) + 1
    ln = len(prior)
    lm = lsum / ln
    dev = {}
    for c in (home, away):
        n = cn.get(c, 0)
        dev[c] = (csum.get(c, 0.0) - n * lm) / (n + k)
    return {"league": lm, "dev_home": dev[home], "dev_away": dev[away],
            "pair": lm + dev[home] + dev[away], "n_home": cn.get(home, 0),
            "n_away": cn.get(away, 0), "n_league": ln}


def modal_best(y: pd.DataFrame) -> dict:
    """The modal number over the quotes given and the best price on it per
    side (r3_lib.modal_best; a tie in price goes to the first row given)."""
    ln = modal_line(y.line)
    z = y[y.line == ln]
    ia = int(np.argmax(dec(z.pa.to_numpy())))
    ib = int(np.argmax(dec(z.pb.to_numpy())))
    return {"line": ln, "best_pa": float(z.pa.iloc[ia]), "book_a": str(z.bookmaker.iloc[ia]),
            "best_pb": float(z.pb.iloc[ib]), "book_b": str(z.bookmaker.iloc[ib]),
            "nbooks": int(len(z)), "fair_a": float(np.nanmean(z.pa_fair))}


def decide_q1_share(period: pd.DataFrame, fetch_rows: pd.DataFrame, fg_board: pd.DataFrame,
                    history: pd.DataFrame, games: pd.DataFrame, art: dict,
                    books=DECIDABLE) -> list[Decision]:
    """Model 5 (r3_d_periods.share_bets at m 1.0): the club-pair share times
    the full-game anchor against the modal deciding-book first-quarter total
    (rungs set aside); over when it is the margin or more above the number,
    under when the margin or more below. `period`: prepare_period() of the
    decision fetch; `fetch_rows`: the same fetch's raw rows (Pinnacle's ladder);
    `fg_board`: the full-game board at the fetch; `history`: share_history()."""
    p = art["models"][Q1_SHARE_TOTAL]["params"]
    margin, k, gap = float(p["margin"]), float(p["k_share"]), float(p["prior_gap_hours"])
    out = []
    x = _by_game(period[(period.market == "totals_q1") & period.bookmaker.isin(books) & ~period.rung])
    ladders = _by_game(fetch_rows[(fetch_rows.market == LADDER_MARKET) & (fetch_rows.bookmaker == SHARP)])
    totals = _by_game(fg_board[fg_board.market == "totals"]) if len(fg_board) else {}
    for row in games.itertuples(index=False):
        gid = row.game_id
        y = x.get(gid, _NONE)
        if y.empty:
            out.append(Decision(gid, Q1_SHARE_TOTAL, "no_quotes",
                                "no deciding book has a first-quarter main total in the fetch"))
            continue
        a, src = anchor(ladders.get(gid, _NONE), totals.get(gid, _NONE), gid)
        if a is None:
            out.append(Decision(gid, Q1_SHARE_TOTAL, "no_anchor", "no full-game total to anchor on"))
            continue
        sh = pair_share(history, row.tip, row.home_code, row.away_code, k, gap)
        if sh is None:
            out.append(Decision(gid, Q1_SHARE_TOTAL, "no_shares", "no earlier game to take a share from"))
            continue
        mb = modal_best(y)
        implied = sh["pair"] * a
        edge_pts = implied - mb["line"]
        side = "over" if edge_pts >= 0 else "under"
        price = mb["best_pa"] if side == "over" else mb["best_pb"]
        book = mb["book_a"] if side == "over" else mb["book_b"]
        status = "bet" if (edge_pts >= margin or edge_pts <= -margin) else "no_bet"
        dk_price, _ = _dk_quote(y, side, mb["line"])
        out.append(Decision(
            gid, Q1_SHARE_TOTAL, status,
            f"{side} {mb['line']:g}: share {sh['pair']:.4f} x total {a:.2f} = {implied:.2f}, "
            f"{edge_pts:+.2f} points ({src})",
            side=side, book=book, price=float(price), line=mb["line"],
            p_fair=mb["fair_a"] if side == "over" else 1 - mb["fair_a"],
            dk_price=dk_price, n_books=mb["nbooks"],
            extra={"anchor": round(a, 4), "anchor_src": src, "pair_share": round(sh["pair"], 6),
                   "league_share": round(sh["league"], 6), "implied": round(implied, 4),
                   "edge_pts": round(edge_pts, 4), "n_prior": sh["n_league"]}))
    return out


# ── one game never carries two bets that cannot both win ────────────────────

def winning_margins(side: str, home_line: float) -> tuple:
    """The integer final home margins a full-game bet wins on, inclusive. A
    moneyline is the spread at -0.5 (home) / +0.5 (away): a full game cannot
    end level (every regulation tie goes to overtime)."""
    x = -float(home_line)
    if side == "home":
        return (math.floor(x) + 1.0, math.inf)
    return (-math.inf, math.ceil(x) - 1.0)


def full_game_margins(market: str, side: str, line: float | None) -> tuple | None:
    if market == "h2h":
        return winning_margins(side, -0.5 if side == "home" else 0.5)
    if market == "spreads" and line is not None:
        return winning_margins(side, float(line))
    return None


def cannot_both_win(a: dict, b: dict) -> bool:
    """Two full-game moneyline/spread bets no final margin wins together
    (mike, 2026-10-17: "It can't be both"). dicts: market, side, line (the HOME
    number for a spread, None for a moneyline). Other markets never conflict
    here: a first-half or first-quarter bet and a full-game bet can both win."""
    ma = full_game_margins(a["market"], a["side"], a.get("line"))
    mb = full_game_margins(b["market"], b["side"], b.get("line"))
    if ma is None or mb is None:
        return False
    return max(ma[0], mb[0]) > min(ma[1], mb[1])


def resolve_conflicts(decisions: list[Decision], standing: list[dict]) -> list[Decision]:
    """Turn each BET that cannot win alongside a standing BET on its game, or
    alongside another BET decided in this pass, into a NONE row (status
    no_bet) with the reason. A standing BET keeps the game; two from one pass
    both go NONE (.claude/rules/picks-and-publishing.md). Mutates and returns."""
    def mine(d: Decision) -> dict:
        return {"market": MARKET[d.model_id], "side": d.side, "line": d.line, "label": d.model_id}

    bets = [d for d in decisions if d.status == "bet" and MARKET[d.model_id] in ("h2h", "spreads")]
    notes: dict[int, str] = {}
    for d in bets:
        held = next((s for s in standing if s["game_id"] == d.game_id and cannot_both_win(mine(d), s)), None)
        if held is not None:
            notes[id(d)] = f"cannot both win with {held.get('label') or held.get('model_id')}, already bet"
    rest = [d for d in bets if id(d) not in notes]
    for i, a in enumerate(rest):
        for b in rest[i + 1:]:
            if a.game_id == b.game_id and cannot_both_win(mine(a), mine(b)):
                notes.setdefault(id(a), f"cannot both win with {b.model_id} {b.side}, decided in the "
                                        f"same pass; neither is bet")
                notes.setdefault(id(b), f"cannot both win with {a.model_id} {a.side}, decided in the "
                                        f"same pass; neither is bet")
    for d in bets:
        if id(d) in notes:
            d.status = "no_bet"
            d.detail = f"{d.detail}; {notes[id(d)]}"
            d.extra["conflict"] = notes[id(d)]
    return decisions


# ── the replayed-bet bookkeeping the build and the card share ───────────────

def uplift_from(bets: pd.DataFrame, before_season: int) -> tuple[float | None, int]:
    """(win share minus mean p_fair, bets counted) over graded bets of the
    seasons before `before_season`, pushes out. bets: season, res (+1/0/-1),
    p_fair."""
    x = bets[(bets.season < before_season) & (bets.res != 0) & bets.p_fair.notna()]
    if x.empty:
        return None, 0
    return float((x.res > 0).mean() - x.p_fair.mean()), int(len(x))
