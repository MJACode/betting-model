"""EuroLeague halftime spread: `euroleague_live_spread_ht`.

WHAT IT BETS. The full-game spread, home or away, at a book's in-play number
during the halftime break. One decision a game: the first five-minute price
read of the break that holds an eligible quote decides it, on the best quote
there, bet at EV >= the cut (0.05) and spent either way. Settled on the final
margin, overtime included, against the home number taken (CLAUDE.md 4).

THE MODEL (the women's college halftime method, ported; Pinnacle's close as
the pre-game number). The margin still to come (final margin minus the
current margin, home minus away, overtime included) is normal with mean X b
and variance s0 + s1 f + s2 f^2, f the share of regulation (2,400 seconds,
four 10-minute quarters) left. X has three terms: f x prior_m; f x sur;
f^2 x sur, where prior_m = -(Pinnacle's last pre-game home spread) and
sur = current margin - prior_m (1 - f). Fitted by weighted least squares in
three passes on the score every 30 seconds of regulation of every qualifying
game of the training seasons. At the break f = 0.5.

PRICING. For a home spread s at the half with the home side up cur_m:
k = -s - cur_m; P(home covers) = pw / (pw + pl) on a whole-number normal
(pushes removed); EV = p x decimal - 1 for each side; the side with the
higher EV is the one considered (home on a tie).

A QUOTE IS ELIGIBLE (each rule is the research's, scripts/euroleague_research/
r4_lib.py, unchanged) when: its book is one a pick may name (DraftKings,
FanDuel, BetMGM, BetRivers, Fanatics); it is in play (stamped at or after the
game's first shot); it is fresh (stamped after the half's last shot); both
prices are real (|price| >= 100) and the line is a number; the price of the
side taken is between -250 and +250; at least 2 other books quote the game's
spread in play in that read; its line is within 6 points of the median of
those books' lines; and |line| <= 70. The read must fall strictly more than a
minute after the half's last shot and more than a minute before the third
quarter's first shot.

ONE CODE PATH. `read_break` is the decision the build replays on the cache
(scripts/build_euroleague_live_ht_artifact.py, which must match the research
bet for bet before it writes an artifact) and the decision the loop makes
(models/euroleague_live_loop.py).

Evidence, prices, volume and what it missed: docs/sports/euroleague.md,
"Halftime spread".
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

MODEL_ID = "euroleague_live_spread_ht"
SPORT = "EUROLEAGUE"
MARKET = "spreads"
REG_S = 2400.0                    # four 10-minute quarters
HALF_S = 1200.0
GRID_STEP_S = 30.0
F_HALF = 0.5
PRICE_BAND = (-250.0, 250.0)      # the side taken, American
OUTLIER_PTS = 6.0                 # a line further than this from the read's median is not bet
MIN_OTHERS = 2                    # other in-play books quoting the game's spread in the read
SPREAD_MAX = 70.0
PRIOR_SPREAD_MAX = 70.0           # Pinnacle's pre-game spread beyond this is not a spread
PRIOR_TOTAL_RANGE = (90.0, 200.0)
ISUM_RANGE = (1.00, 1.15)         # a coherent two-way quote: implied chances summing to 1.00-1.15
BUFFER_S = 60.0                   # the read must sit a minute inside the break, each end
MAX_BREAK_MIN = 25.0              # the grade kept breaks of 10-25 minutes; a read later than this is past
MAX_RISK = 3.0                    # one unit to win, risk capped here (tracking.discord_notifier.stake_for)
# The purchase the rule was graded on: one in-play snapshot every five minutes
# (every ten in 2021-22), stamped 36-40 seconds after the mark (median 38 s in
# 2022-23 to 2025-26, 36 s in 2026-27; scripts/build_euroleague_live_ht_artifact.py
# prints the census).
CADENCE_MIN = 5
FETCH_AFTER_SEC = 37.0
# The books a pick may name, in the research's order (also the tie order).
DECIDABLE = ("draftkings", "fanduel", "betmgm", "betrivers", "fanatics")
# The ten books the history was bought at (config.EUROLEAGUE_HISTORY_BOOKMAKERS):
# the five above and five reference books that count toward a read's median
# and its count of other books but are never bet.
REFERENCE = ("pinnacle", "bovada", "marathonbet", "unibet", "paddypower")

ARTIFACT_KIND = "euroleague_live_ht"
ARTIFACT_PATH = "models/saved/euroleague_live_ht_2027.json"
SEASON = 2027                     # EuroLeague 2026-27 (ending-year label; EuroLeague's own code E2026)


# ── the game state from the shot chart ──────────────────────────────────────

def game_seconds(minute, console) -> np.ndarray:
    """Game seconds gone at a shot, from EuroLeague's MINUTE (1-40, then
    overtime minutes 41-45, 46-50 ...) and CONSOLE (the clock, 'MM:SS',
    counting down in the period). NaN when the clock cannot be read."""
    m = np.asarray(minute, float)
    cs = pd.Series(console).astype(str).str.split(":", expand=True)
    if cs.shape[1] < 2:
        return np.full(len(m), np.nan)
    clock = (pd.to_numeric(cs[0], errors="coerce") * 60 + pd.to_numeric(cs[1], errors="coerce")).clip(lower=0)
    clock = clock.to_numpy(float)
    reg = m <= 40
    qtr = np.where(reg, (m - 1) // 10 + 1, 5 + (m - 41) // 5)
    return np.where(reg, (qtr - 1) * 600 + 600 - clock, REG_S + (qtr - 5) * 300 + 300 - clock)


@dataclass
class States:
    """One game's shots in wall-clock order: game seconds gone and the score
    (home, away), each a running maximum (neither runs backwards)."""
    gs: np.ndarray
    h: np.ndarray
    a: np.ndarray


def states_from_shots(shots: pd.DataFrame) -> States | None:
    """Shot rows (num_anot, minute, console, points_home, points_away,
    shot_utc) -> States, sorted by shot_utc then num_anot (the research's
    reading). None when no shot carries a clock."""
    s = shots.assign(gs=game_seconds(shots["minute"], shots["console"])).dropna(subset=["gs"])
    if not len(s):
        return None
    s = s.sort_values(["shot_utc", "num_anot"], kind="mergesort")
    return States(np.maximum.accumulate(s["gs"].to_numpy(float)),
                  np.maximum.accumulate(s["points_home"].to_numpy(float)),
                  np.maximum.accumulate(s["points_away"].to_numpy(float)))


def training_rows(st: States, prior_m: float, final_margin: float) -> pd.DataFrame:
    """The score every GRID_STEP_S of regulation, and the margin that followed."""
    grid = np.arange(GRID_STEP_S, REG_S, GRID_STEP_S)
    idx = np.searchsorted(st.gs, grid, side="right") - 1
    ok = idx >= 0
    cur_m = (st.h - st.a)[idx[ok]]
    return pd.DataFrame({"f": 1 - grid[ok] / REG_S, "cur_m": cur_m, "prior_m": float(prior_m),
                         "rem_m": float(final_margin) - cur_m})


# ── the model ────────────────────────────────────────────────────────────────

def design(f, cur_m, prior_m) -> np.ndarray:
    f = np.atleast_1d(np.asarray(f, float))
    pm = np.asarray(prior_m, float)
    sur = np.asarray(cur_m, float) - pm * (1 - f)
    return np.column_stack([f * pm, f * sur, f * f * sur])


@dataclass(frozen=True)
class MarginModel:
    b: tuple                      # the three mean coefficients, in design()'s order
    s: tuple                      # the variance: s0 + s1 f + s2 f^2

    def predict(self, f, cur_m, prior_m):
        """(mean, sd) of the margin still to come, home minus away."""
        f = np.atleast_1d(np.asarray(f, float))
        mu = design(f, cur_m, prior_m) @ np.asarray(self.b, float)
        var = np.maximum(self.s[0] + self.s[1] * f + self.s[2] * f * f, 1.0)
        return mu, np.sqrt(var)

    def to_dict(self) -> dict:
        return {"b": [float(x) for x in self.b], "s": [float(x) for x in self.s]}

    @classmethod
    def from_dict(cls, d: dict) -> "MarginModel":
        b, s = tuple(float(x) for x in d["b"]), tuple(float(x) for x in d["s"])
        if len(b) != 3 or len(s) != 3 or not all(math.isfinite(x) for x in b + s):
            raise ValueError("a margin model is three mean and three variance numbers")
        return cls(b, s)


def fit(tr: pd.DataFrame) -> MarginModel:
    """Weighted least squares, the weights from the fitted variance, three passes."""
    X = design(tr["f"].values, tr["cur_m"].values, tr["prior_m"].values)
    y = tr["rem_m"].values
    f = tr["f"].values
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    V = np.column_stack([np.ones(len(tr)), f, f ** 2])
    s = None
    for _ in range(3):
        s = np.linalg.lstsq(V, (y - X @ b) ** 2, rcond=None)[0]
        w = 1.0 / np.sqrt(np.maximum(V @ s, 1.0))
        b = np.linalg.lstsq(X * w[:, None], y * w, rcond=None)[0]
    return MarginModel(tuple(float(x) for x in b), tuple(float(x) for x in s))


def p_over(mu, sd, k):
    """P(still to come > k), P(push); the margin still to come is a whole number."""
    k = np.asarray(k, float)
    whole = np.abs(k - np.round(k)) < 1e-9
    pw = np.where(whole, norm.sf((k + 0.5 - mu) / sd), norm.sf((k - mu) / sd))
    pp = np.where(whole, norm.cdf((k + 0.5 - mu) / sd) - norm.cdf((k - 0.5 - mu) / sd), 0.0)
    return pw, pp


def decimal(american) -> np.ndarray:
    a = np.asarray(american, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(a > 0, 1 + a / 100.0, 1 + 100.0 / np.abs(a))


def implied(american) -> np.ndarray:
    a = np.asarray(american, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(a > 0, 100 / (a + 100), -a / (-a + 100))


def covers(side: str, spread_home: float, final_margin: float) -> int:
    """+1 won, 0 push, -1 lost: home covers when margin + spread_home > 0."""
    r = int(np.sign(float(final_margin) + float(spread_home)))
    return r if side == "home" else -r


def units(side, spread_home, price, final_margin) -> tuple:
    """(units won, units risked) on the posted stake: one unit to win, risk
    capped at MAX_RISK, a push returns the stake (tracking.discord_notifier.stake_for)."""
    d = float(decimal(price))
    risk = min(1.0 / (d - 1.0), MAX_RISK)
    r = covers(side, spread_home, final_margin)
    return (risk * (d - 1.0) if r > 0 else (-risk if r < 0 else 0.0)), (risk if r else 0.0)


def research_units(side, spread_home, price, final_margin) -> tuple:
    """(units won, units risked) on the research's stake (scripts/euroleague_research/
    r1_lib.stake): a favourite risks |price|/100 (capped at 3) to win 1; an
    underdog risks 1 to win price/100. Used only to show the build matches."""
    p = float(price)
    risk = min(abs(p) / 100.0, MAX_RISK) if p < 0 else 1.0
    win = risk * 100.0 / abs(p) if p < 0 else p / 100.0
    r = covers(side, spread_home, final_margin)
    return (win if r > 0 else (-risk if r < 0 else 0.0)), (risk if r else 0.0)


# ── the break ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Half:
    """What the shot chart says about one game's halftime.
    first_shot     the game's first shot (UTC): a quote stamped earlier is pre-game
    last_q2_shot   the half's last shot (UTC): a quote stamped later is fresh
    ht_home/away   the score at the half, OUR orientation (EuroLeague's A is the home club)
    q3_at          the third quarter's first shot (UTC), or None while it has not come"""
    first_shot: pd.Timestamp
    last_q2_shot: pd.Timestamp
    ht_home: int
    ht_away: int
    q3_at: pd.Timestamp | None = None


OFFER_COLS = ("book", "stamp", "line", "side", "price", "ev", "prob", "p_push", "mean", "sd",
              "home_price", "away_price", "inplay", "fresh", "priced", "off", "others", "eligible")


@dataclass
class Read:
    """What one price read says about one game.
    status: 'early'    the read is not yet a minute past the half's last shot
            'past'     the read is within a minute of the third quarter (or it has begun)
            'none'     in the break, no eligible quote
            'decided'  in the break with an eligible quote: `best` is the decision
    """
    status: str
    offers: pd.DataFrame | None = None              # every quote in the read, priced
    best: dict | None = None


def _ts(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def in_window(fetch_at, half: Half) -> str:
    """'early', 'break' or 'past' for a read at fetch_at."""
    t = _ts(fetch_at)
    if t <= _ts(half.last_q2_shot) + pd.Timedelta(seconds=BUFFER_S):
        return "early"
    if half.q3_at is not None and t >= _ts(half.q3_at) - pd.Timedelta(seconds=BUFFER_S):
        return "past"
    if (t - _ts(half.last_q2_shot)).total_seconds() > MAX_BREAK_MIN * 60:
        return "past"
    return "break"


def read_break(quotes: pd.DataFrame, fetch_at, half: Half, prior_m: float, model: MarginModel,
               books: tuple = DECIDABLE) -> Read:
    """One game's spread quotes at one read -> Read.

    `quotes`: book, stamp (the book's own last update), spread_home (OUR home
    team's number), home_price, away_price; one row a book (the first is kept
    when the feed lists a book twice). Rows stamped after the read are
    dropped. Every book in the frame counts toward the read's median line and
    count of other books when it is in play and priced; only `books` are bet."""
    w = in_window(fetch_at, half)
    if w != "break":
        return Read(w)
    t = _ts(fetch_at)
    q = quotes.drop_duplicates("book", keep="first").copy()
    q["stamp"] = pd.to_datetime(q["stamp"], utc=True, errors="coerce")
    q = q[q["stamp"].notna() & (q["stamp"] <= t)]
    if not len(q):
        return Read("none", q.assign(eligible=[]))
    line = pd.to_numeric(q["spread_home"], errors="coerce").to_numpy(float)
    pa = pd.to_numeric(q["home_price"], errors="coerce").to_numpy(float)
    pb = pd.to_numeric(q["away_price"], errors="coerce").to_numpy(float)
    stamp = q["stamp"]
    inplay = (stamp >= _ts(half.first_shot)).to_numpy()
    fresh = inplay & (stamp > _ts(half.last_q2_shot)).to_numpy()
    with np.errstate(invalid="ignore"):
        priced = np.isfinite(pa) & np.isfinite(pb) & (np.abs(pa) >= 100) & (np.abs(pb) >= 100) & np.isfinite(line)
    counted = inplay & priced
    nbooks = int(counted.sum())
    med = float(np.median(line[counted])) if nbooks else np.nan
    others = nbooks - counted.astype(int)
    off = np.abs(line - med)

    cur_m = float(half.ht_home - half.ht_away)
    f = np.full(len(q), F_HALF)
    mu, sd = model.predict(f, np.full(len(q), cur_m), np.full(len(q), float(prior_m)))
    k = -line - cur_m
    pw, pp = p_over(mu, sd, np.nan_to_num(k))
    pl = 1 - pw - pp
    with np.errstate(divide="ignore", invalid="ignore"):
        p1 = pw / (pw + pl)
        ev1, ev2 = p1 * decimal(pa) - 1, (1 - p1) * decimal(pb) - 1
    first = ev1 >= ev2
    price = np.where(first, pa, pb)
    o = pd.DataFrame({
        "book": q["book"].to_numpy(), "stamp": stamp.to_numpy(), "line": line,
        "side": np.where(first, "home", "away"), "price": price, "ev": np.where(first, ev1, ev2),
        "prob": np.where(first, p1, 1 - p1), "p_push": pp, "mean": mu, "sd": sd,
        "home_price": pa, "away_price": pb, "inplay": inplay, "fresh": fresh, "priced": priced,
        "off": off, "others": others})
    with np.errstate(invalid="ignore"):
        o["eligible"] = (o["book"].isin(books) & o["inplay"] & o["priced"] & o["fresh"]
                         & (o["price"] >= PRICE_BAND[0]) & (o["price"] <= PRICE_BAND[1])
                         & (o["others"] >= MIN_OTHERS) & (o["off"] <= OUTLIER_PTS)
                         & (np.abs(o["line"]) <= SPREAD_MAX))
    el = o[o["eligible"]]
    if el.empty:
        return Read("none", o)
    rank = {b: i for i, b in enumerate(books)}
    el = el.assign(_r=el["book"].map(rank)).sort_values(["ev", "_r"], ascending=[False, True], kind="mergesort")
    return Read("decided", o, el.iloc[0].drop("_r").to_dict())


# ── the pre-game number: Pinnacle's close ───────────────────────────────────

# Pinnacle's pre-game spreads and totals for one game, oldest first. Bounded on
# the listed tip (pre-game and in-play prices never mix, CLAUDE.md 6); the loop
# also drops rows stamped at or after the game's first shot.
PRIOR_CLOSE_SQL = """
    SELECT o.market, o.snapshot_at, o.spread_home, o.total_line, o.home_price, o.away_price,
           o.over_price, o.under_price
      FROM odds o JOIN games g ON g.game_id = o.game_id
     WHERE o.game_id = %s AND o.bookmaker = 'pinnacle' AND o.market IN ('spreads', 'totals')
       AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
       AND o.snapshot_at::timestamptz <= g.commence_time::timestamptz
     ORDER BY o.snapshot_at::timestamptz, o.market
"""


def _f(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v if math.isfinite(v) else float("nan")


def coherent(p1, p2, line) -> bool:
    """Both prices real (|p| >= 100), a line, and implied chances summing to 1.00-1.15."""
    a, b, ln = _f(p1), _f(p2), _f(line)
    if not (math.isfinite(a) and math.isfinite(b) and math.isfinite(ln)) or abs(a) < 100 or abs(b) < 100:
        return False
    s = float(implied(a) + implied(b))
    return ISUM_RANGE[0] <= s <= ISUM_RANGE[1]


def prior_from_pinnacle(rows, before=None) -> tuple | None:
    """(prior_m, pre-game total) from Pinnacle's LAST coherent pre-game spread
    and total (rows as PRIOR_CLOSE_SQL returns them, any order; `before`
    drops rows stamped after it: the research bounded on min(tip, first shot)).
    prior_m = -(that spread). None when either is missing or out of range (the
    grade dropped such games): the last coherent quote decides, never an older one."""
    cut = None if before is None else _ts(before)
    last: dict = {}
    for market, at, sp, tot, hp, ap, op, up in rows:
        t = pd.to_datetime(at, utc=True, errors="coerce")
        if t is pd.NaT or pd.isna(t) or (cut is not None and t > cut):
            continue
        if market == "spreads" and coherent(hp, ap, sp):
            v = _f(sp)
        elif market == "totals" and coherent(op, up, tot):
            v = _f(tot)
        else:
            continue
        if market not in last or t >= last[market][0]:
            last[market] = (t, v)
    if "spreads" not in last or "totals" not in last:
        return None
    sp, tot = last["spreads"][1], last["totals"][1]
    if abs(sp) > PRIOR_SPREAD_MAX or not (PRIOR_TOTAL_RANGE[0] <= tot <= PRIOR_TOTAL_RANGE[1]):
        return None
    return -float(sp), float(tot)


# ── the artifact ─────────────────────────────────────────────────────────────

@dataclass
class Artifact:
    margin: MarginModel
    cut: float
    raw: dict = field(default_factory=dict)

    @property
    def version(self) -> str:
        return str(self.raw.get("version", ""))


def artifact_from_dict(d: dict, season: int = SEASON) -> Artifact:
    if d.get("kind") != ARTIFACT_KIND:
        raise ValueError(f"not an {ARTIFACT_KIND} artifact (kind={d.get('kind')!r})")
    if int(d.get("season", -1)) != int(season):
        raise ValueError(f"the artifact is for season {d.get('season')!r}, not {season}: "
                         f"rebuild it (scripts/build_euroleague_live_ht_artifact.py)")
    cut = float(d["cut"])
    if not 0.0 < cut < 1.0:
        raise ValueError("the cut is an expected value between 0 and 1")
    return Artifact(MarginModel.from_dict(d["margin"]), cut, d)


def load_artifact(path=None, season: int = SEASON) -> Artifact:
    p = Path(path) if path is not None else Path(__file__).resolve().parents[1] / ARTIFACT_PATH
    return artifact_from_dict(json.loads(p.read_text(encoding="utf-8")), season)


# ── the pick ─────────────────────────────────────────────────────────────────

def side_line(side: str, spread_home: float) -> float:
    """The number the side taken carries: the home number for home, its negative for away."""
    return float(spread_home) if side == "home" else -float(spread_home)


def pick_label(side: str, spread_home: float, home: str, away: str) -> str:
    """'PAN -3.5 (live)': the side's club and the number it carries, the shape
    of the NBA and NCAAB in-play spreads, so tracking.pick_integrity agrees.
    `spread_home` is always the HOME number (CLAUDE.md 4); an away pick names
    the away club with the sign turned over. No half is named: the bet is on
    the full game, and in this app "First Half" names a bet on that half alone."""
    team = home if side == "home" else away
    n = side_line(side, spread_home)
    num = "PK" if n == 0 else f"{n:+g}"
    return f"{team} {num} (live)"
