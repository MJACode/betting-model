"""Tennis total games and games spreads, round 2: a serve-and-return game model
anchored to Pinnacle's match-winner price, against the decidable books' total
and games-spread prices. Reads the local cache (scripts/tennis_cache.py) and
the spooled match archive; writes nothing but its own report and, with --save,
every scored quote. No network, no database, no paid call.

THE HYPOTHESIS. Books set the total off the match price. The anchor fixes the
gap between the two players' serve-point chances to the market's match price;
what it leaves to the players' own statistics is their SUM (serve dominance).
Two strong servers (more tiebreaks, fewer breaks) should go over the line more
often than the line's own price says, and a games spread should carry the
same information about how lopsided the sets are.

FIXED BEFORE ANY RESULT WAS READ (none was changed after):

  population   feed events linked to their ESPN result (scripts/tennis_market_study
               .link), ESPN start before 2026-06-01 (the archive's statistics end
               2026-05-25), pre-match quotes only (tennis_market_study.pre_match).
               Both players matched by models/tennis_common.name_key from the
               feed's names to the archive's names of the same tour; a key held by
               several archive ids goes to the id with the most archive rows from
               2018 on; an event with a player not found is OUT (counted)
  best of      ESPN's best_of, except a "Qualifying" round at a men's Slam key,
               which is best of 3 (ESPN reads 5 there; measured on the cache: no
               men's Slam Q1 or Q2 match went past three sets), and the Wimbledon
               men's Qualifying Final, best of 5 (it went to five sets in 2026)
  surface      the match's own archive row's surface (both ids, tourney_date in
               [start - 20 days, start + 8 days], the nearest); else a fixed map by
               sport key (SURFACE below). Disagreements are counted
  statistics   every spool file (tour, qualifying, Challenger, ITF) from 2015; a
               row counts when its surface is known and both players' svpt > 0
               with 1stWon and 2ndWon present. Serve points won = 1stWon + 2ndWon;
               return points = the opponent's svpt; return won = opponent svpt -
               opponent serve won
  average      per tour x surface, serve points won / serve points, on the MAIN
               tour files only, tourney_date in 2015-2019, tour levels ATP {G, M, A,
               F} and WTA {G, PM, P, I, F} (the levels tennis_shop_study
               .retire_rates uses; the qualifying and Challenger levels serve about
               two points lower and would shift the sum the test rides on). Carpet
               uses the hard-court average. Return average = 1 - serve average
  window       E = the event's date: the match's own archive row's tourney_date,
               else the first ESPN start date of the sport key's edition (linked
               events, a gap of more than 10 days starts a new edition). Archive
               rows with tourney_date in [E - 365 days, min(E, ESPN start date) - 1
               day]: strictly earlier events, so the same event's earlier rounds
               (same tourney_date) are out
  relative     relSPW = sum(serve won - svpt * avg_row) / (sum svpt + 1000), relRPW
               = sum(return won - rpt * (1 - avg_row)) / (sum rpt + 1000), avg_row
               the average of that archive row's tour and surface. No row in the
               window: 0
  matchup      pA = avg(tour, surface) + relSPW_A - relRPW_B, pB = avg + relSPW_B
               - relRPW_A, each clipped to [0.40, 0.90]; A is the feed's home player
  game model   hold(p) = p^4 (1 + 4q + 10q^2) + 20 p^3 q^3 p^2 / (1 - 2pq); a
               7-point tiebreak at 6-6 in every set (points served A, B, B, A, A,
               ... by the set's first server; from 6-6 in points A wins with x/(x+y),
               x = pA(1-pB), y = (1-pA)pB); serve alternates by game across sets
               (the next set's first server is the other player when the set had an
               odd number of games); best of 3 or 5; the first server a coin toss
               (both averaged). The distributions of total games and of the games
               margin (A - B) are exact dynamic programmes, vectorised over matches.
               Known gap: advantage final sets (Roland Garros 2020-21, Wimbledon's
               12-12 rule in 2021) can run past 13 games; the model gives that zero
               mass (51 linked matches had such a set)
  anchor       Pinnacle's h2h pair, the latest pre-match row at or before the
               decidable quote's snapshot (no age cap; the age is reported),
               power de-vig (scripts/tennis_shop_checks.power_side) of the home
               price = the target. delta by 60 bisection steps on [-0.45, 0.45] so
               that P(A wins | pA + delta, pB - delta) = target, the shifted chances
               held inside [0.02, 0.98]; a quote whose anchored chance misses the
               target by more than 0.002 is dropped (counted); a shift that reaches
               the [0.02, 0.98] guard is counted. No Pinnacle h2h: no bet
  decisions    first, t12, close (tennis_market_study.decision_quotes); books
               BetMGM, Caesars, BetRivers only
  EV           P(win) (d - 1) - P(loss) from the model's distribution, a whole line
               landed exactly a push
  one bet      per event, market and decision: the best EV across the three books
               and both sides
  grade        completed matches only, a retirement or walkover VOID
               (tennis_games_study.sides); units at the published stake: risk
               min(1/(d-1), 3) to win risk (d-1)
  cuts         EV >= 0.00, 0.01, 0.02, 0.03, 0.05, 0.08; the BANDED table is the
               one-bet-per-event set binned by its EV, [k, k+0.01), k = -0.03 to 0.07

  information  one row per decidable quote (over for totals, home for spreads),
               completed, not a push: p_model = P(win) / (P(win) + P(loss)); p_book =
               the quote's own pair, multiplicative de-vig; Brier and log-loss; logit
               y ~ 1 + logit(p_book) + (logit(p_model) - logit(p_book)), standard
               errors naive and clustered by event. The same on the quotes where
               Pinnacle's standing quote in that market (latest pre-match row at or
               before the snapshot) has the same line, Pinnacle's pair de-vigged
               multiplicatively as the base
  kill tests   a POSITIVE cell is a market x decision x cut with units > 0. Each:
               by season; early and late halves (bets sorted by start, split at the
               middle bet); side (over / under; home / away and favourite = the side
               with a negative point / dog for spreads); book; best of 5 (the men's
               Slam main draws) and best of 3; price band (<= -130, -129 to -111,
               -110 to -101, +100 and up); the five best days' share of the units
  placebo      for the BEST cell of each market x decision (the positive cut with
               the most units): 200 shuffles, each event given the four statistics
               (relSPW and relRPW of both players) of a random other event of the
               same tour (a permutation within tour), everything else recomputed;
               the shuffled units' mean, sd, 5/50/95th percentiles and the share at
               or above the real units. Seed 20261114
  walk-forward per market x decision: for each season after the first, the cut with
               the most units on all earlier seasons (none positive: no bets that
               season), applied to that season; the applied seasons totalled

    python -m scripts.tennis_serve_study --cache C:/Users/micha/tennis_research/cache \\
        --spool C:/Users/micha/tennis_research/spool \\
        --save C:/Users/micha/tennis_research/cache/serve_candidates.parquet
    python -m scripts.tennis_serve_study --self-test
"""
from __future__ import annotations

import argparse
import glob
import math
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

from models import tennis_common as tc
from scripts import tennis_market_study as st
from scripts.tennis_games_study import GAMES_BOOKS, outcomes, sides
from scripts.tennis_shop_checks import power_side
from scripts.tennis_shop_study import CUTS, load, table

STATS_END = pd.Timestamp("2026-06-01", tz="UTC")
SHRINK = 1000.0
CLIP_LO, CLIP_HI = 0.40, 0.90
GUARD_LO, GUARD_HI = 0.02, 0.98
DELTA_LO, DELTA_HI = -0.45, 0.45
ANCHOR_TOL = 0.002
SEED = 20261114
N_SHUFFLE = 200
TOUR_LEVELS = {"ATP": {"G", "M", "A", "F"}, "WTA": {"G", "PM", "P", "I", "F"}}
BANDS = [round(k / 100, 2) for k in range(-3, 8)]
NT, NM, MOFF = 66, 71, 35        # total-games bins 0..65, margin bins -35..35

SURFACE = {
    "aus_open_singles": "Hard", "us_open": "Hard", "french_open": "Clay", "wimbledon": "Grass",
    "indian_wells": "Hard", "miami_open": "Hard", "monte_carlo_masters": "Clay",
    "madrid_open": "Clay", "italian_open": "Clay", "canadian_open": "Hard",
    "cincinnati_open": "Hard", "shanghai_masters": "Hard", "paris_masters": "Hard",
    "china_open": "Hard", "qatar_open": "Hard", "dubai": "Hard", "washington_open": "Hard",
    "hamburg_open": "Clay", "japan_open": "Hard", "halle_open": "Grass", "swiss_indoors": "Hard",
    "vienna_open": "Hard", "queens_club_champ": "Grass", "barcelona_open": "Clay",
    "munich": "Clay", "finals": "Hard", "wuhan_open": "Hard", "charleston_open": "Clay",
    "monterrey_open": "Hard", "ningbo_open": "Hard", "guadalajara_open": "Hard",
    "strasbourg": "Clay", "german_open": "Grass", "stuttgart_open": "Clay",
    "pan_pacific_open": "Hard", "bad_homburg_open": "Grass", "singapore_open": "Hard",
}
MEN_SLAMS = ("tennis_atp_aus_open_singles", "tennis_atp_french_open", "tennis_atp_us_open",
             "tennis_atp_wimbledon")


# ── the game, set and match model ────────────────────────────────────────────

def hold(p):
    """P(server holds) with point-on-serve chance p."""
    p = np.asarray(p, dtype=float)
    q = 1 - p
    return p ** 4 * (1 + 4 * q + 10 * q ** 2) + 20 * p ** 3 * q ** 3 * p ** 2 / (1 - 2 * p * q)


def _tb_server_is_first(n: int) -> bool:
    """Point n (0-based) of a tiebreak: served A, B, B, A, A, ... from the first server."""
    return n == 0 or ((n - 1) // 2) % 2 == 1


def tiebreak(pa, pb, a_first: bool):
    """P(A wins a 7-point tiebreak)."""
    pa, pb = np.asarray(pa, float), np.asarray(pb, float)
    T = {(0, 0): np.ones_like(pa)}
    win = np.zeros_like(pa)
    for n in range(12):
        a_serves = _tb_server_is_first(n) == a_first
        pw = pa if a_serves else 1 - pb
        for i in range(max(0, n - 6), min(n, 6) + 1):
            j = n - i
            m = T.pop((i, j), None)
            if m is None:
                continue
            if i + 1 == 7:
                win = win + m * pw
            else:
                T[(i + 1, j)] = T.get((i + 1, j), 0) + m * pw
            if j + 1 < 7:
                T[(i, j + 1)] = T.get((i, j + 1), 0) + m * (1 - pw)
    x, y = pa * (1 - pb), (1 - pa) * pb
    return win + T.get((6, 6), 0) * x / (x + y)


SET_SCORES = [(6, 0), (6, 1), (6, 2), (6, 3), (6, 4), (7, 5), (7, 6),
              (0, 6), (1, 6), (2, 6), (3, 6), (4, 6), (5, 7), (6, 7)]
_SET_IDX = {s: k for k, s in enumerate(SET_SCORES)}


def set_outcomes(pa, pb, a_first: bool) -> np.ndarray:
    """N x 14: the chance of each final set score (SET_SCORES), A's games first."""
    pa, pb = np.asarray(pa, float), np.asarray(pb, float)
    ha, hb = hold(pa), hold(pb)
    out = np.zeros((len(pa), 14))
    G = {(0, 0): np.ones_like(pa)}
    for n in range(12):
        a_serves = (n % 2 == 0) == a_first
        pw = ha if a_serves else 1 - hb
        for a in range(max(0, n - 6), min(n, 6) + 1):
            b = n - a
            m = G.pop((a, b), None)
            if m is None:
                continue
            for na, nb, pr in ((a + 1, b, pw), (a, b + 1, 1 - pw)):
                if (na, nb) in _SET_IDX:
                    out[:, _SET_IDX[(na, nb)]] += m * pr
                else:
                    G[(na, nb)] = G.get((na, nb), 0) + m * pr
    m66 = G.pop((6, 6))
    assert not G
    tb = tiebreak(pa, pb, a_first)     # game 13 is served by the set's first server
    out[:, _SET_IDX[(7, 6)]] += m66 * tb
    out[:, _SET_IDX[(6, 7)]] += m66 * (1 - tb)
    return out


_A_WINS = np.array([ga > gb for ga, gb in SET_SCORES])
_FLIP = np.array([(ga + gb) % 2 == 1 for ga, gb in SET_SCORES])
_TOT = np.array([ga + gb for ga, gb in SET_SCORES])
_MAR = np.array([ga - gb for ga, gb in SET_SCORES])


def _match(pa, pb, best_of: int, track: str | None):
    """The match DP for one best_of. track None: P(A wins); 'total' / 'margin':
    the N x K distribution; 'joint': N x 36 x 36 (A's games, B's games).
    Internally the distributions are bin-major (K x N), and each state's
    shift touches only the bins its sets can reach."""
    S = {True: set_outcomes(pa, pb, True), False: set_outcomes(pa, pb, False)}
    need = (best_of + 1) // 2
    n = len(pa)
    if track is None:
        shape = (n,)
    elif track == "total":
        shape = (NT, n)
    elif track == "margin":
        shape = (NM, n)
    else:
        shape = (n, 36, 36)
    init = np.zeros(shape)
    if track is None:
        init[:] = 0.5
    elif track == "total":
        init[0] = 0.5
    elif track == "margin":
        init[MOFF] = 0.5
    else:
        init[:, 0, 0] = 0.5
    states = {(0, 0, True): init, (0, 0, False): init.copy()}
    final = np.zeros(shape)
    a_win = np.zeros(n)
    PT = {f: np.ascontiguousarray(S[f].T) for f in S}       # 14 x N
    while states:
        nxt: dict = {}
        for (sa, sb, f), m in states.items():
            P = PT[f]
            ns = sa + sb
            if track == "total":
                lo, hi = 6 * ns, 13 * ns
            elif track == "margin":
                lo, hi = MOFF - 6 * ns, MOFF + 6 * ns
            for k, (ga, gb) in enumerate(SET_SCORES):
                pk = P[k]
                na, nb = sa + _A_WINS[k], sb + (not _A_WINS[k])
                nf = (not f) if _FLIP[k] else f
                done = na == need or nb == need
                if track is None:
                    if done:
                        if na == need:
                            a_win += m * pk
                    else:
                        key = (na, nb, nf)
                        nxt[key] = nxt[key] + m * pk if key in nxt else m * pk
                    continue
                tgt = final if done else nxt.setdefault((na, nb, nf), np.zeros(shape))
                if track in ("total", "margin"):
                    inc = _TOT[k] if track == "total" else _MAR[k]
                    tgt[lo + inc:hi + 1 + inc] += m[lo:hi + 1] * pk
                else:
                    tgt[:, ga:, gb:] += m[:, :36 - ga, :36 - gb] * pk[:, None, None]
        states = nxt
    if track is None:
        return a_win
    return final.T if track in ("total", "margin") else final


def _by_bo(fn, pa, pb, bo, **kw):
    pa, pb, bo = np.asarray(pa, float), np.asarray(pb, float), np.asarray(bo)
    out = None
    for b in (3, 5):
        idx = np.flatnonzero(bo == b)
        if len(idx) == 0:
            continue
        r = fn(pa[idx], pb[idx], b, **kw)
        if out is None:
            out = np.zeros((len(pa),) + r.shape[1:])
        out[idx] = r
    if out is None:
        raise ValueError("best_of must be 3 or 5")
    return out


def match_win(pa, pb, bo):
    return _by_bo(_match, pa, pb, bo, track=None)


def distributions(pa, pb, bo):
    """(total games N x 66, games margin A - B N x 71 with offset 35)."""
    return (_by_bo(_match, pa, pb, bo, track="total"), _by_bo(_match, pa, pb, bo, track="margin"))


def joint(pa, pb, bo):
    return _by_bo(_match, pa, pb, bo, track="joint")


def anchor(pa0, pb0, bo, target, steps: int = 60):
    """delta with P(A wins | pa0 + delta, pb0 - delta) = target, by bisection."""
    pa0, pb0, target = (np.asarray(x, float) for x in (pa0, pb0, target))
    lo, hi = np.full(len(pa0), DELTA_LO), np.full(len(pa0), DELTA_HI)
    for _ in range(steps):
        mid = (lo + hi) / 2
        w = match_win(np.clip(pa0 + mid, GUARD_LO, GUARD_HI), np.clip(pb0 - mid, GUARD_LO, GUARD_HI), bo)
        up = w < target
        lo, hi = np.where(up, mid, lo), np.where(up, hi, mid)
    d = (lo + hi) / 2
    pa, pb = np.clip(pa0 + d, GUARD_LO, GUARD_HI), np.clip(pb0 - d, GUARD_LO, GUARD_HI)
    miss = np.abs(match_win(pa, pb, bo) - target)
    guard = (pa0 + d <= GUARD_LO) | (pa0 + d >= GUARD_HI) | (pb0 - d <= GUARD_LO) | (pb0 - d >= GUARD_HI)
    return d, pa, pb, miss, guard


# ── the archive: per player, serve and return against the average ────────────

def _tour_of(path: str) -> str:
    return "ATP" if "__atp__" in path else "WTA"


def load_archive(spool: str) -> pd.DataFrame:
    fs = sorted(glob.glob(f"{spool}/sackmann__*__*_matches_*.csv"))
    parts = []
    for f in fs:
        yr = int(f[-8:-4])
        if yr < 2015:
            continue
        d = pd.read_csv(f, low_memory=False, dtype={"tourney_level": str, "winner_id": str,
                                                    "loser_id": str, "tourney_id": str})
        d["tour"] = _tour_of(f)
        d["main"] = "qual" not in Path(f).name
        parts.append(d)
    a = pd.concat(parts, ignore_index=True)
    a["date"] = pd.to_datetime(a.tourney_date.astype("Int64").astype(str), format="%Y%m%d", utc=True)
    return a


def averages(a: pd.DataFrame) -> dict:
    m = a[a.main & a.date.dt.year.between(2015, 2019)].copy()
    m = m[[lv in TOUR_LEVELS[t] for lv, t in zip(m.tourney_level.astype(str), m.tour)]]
    m = m[_has_stats(m) & m.surface.isin(["Hard", "Clay", "Grass"])]
    sp = m.w_svpt + m.l_svpt
    sw = m.w_1stWon + m.w_2ndWon + m.l_1stWon + m.l_2ndWon
    g = pd.DataFrame({"tour": m.tour, "surface": m.surface, "sp": sp, "sw": sw}).groupby(["tour", "surface"]).sum()
    out = {(t, s): float(r.sw / r.sp) for (t, s), r in g.iterrows()}
    for t in ("ATP", "WTA"):
        out[(t, "Carpet")] = out[(t, "Hard")]
    return out


def _has_stats(d: pd.DataFrame) -> pd.Series:
    cols = ["w_svpt", "l_svpt", "w_1stWon", "w_2ndWon", "l_1stWon", "l_2ndWon"]
    return d[cols].notna().all(axis=1) & (d.w_svpt > 0) & (d.l_svpt > 0)


def player_rows(a: pd.DataFrame, avg: dict) -> pd.DataFrame:
    """One row per player per archive match with statistics: the excess serve
    and return points won over the tour x surface average."""
    d = a[_has_stats(a) & a.surface.notna()].copy()
    d["avg"] = [avg.get((t, s), np.nan) for t, s in zip(d.tour, d.surface)]
    d = d.dropna(subset=["avg"])
    w_sw = d.w_1stWon + d.w_2ndWon
    l_sw = d.l_1stWon + d.l_2ndWon
    rows = []
    for pid, sp, sw, rp, rw in (("winner_id", d.w_svpt, w_sw, d.l_svpt, d.l_svpt - l_sw),
                                ("loser_id", d.l_svpt, l_sw, d.w_svpt, d.w_svpt - w_sw)):
        rows.append(pd.DataFrame({"pid": d.tour + ":" + d[pid].astype(str), "date": d.date,
                                  "sp": sp.values, "sx": (sw - sp * d.avg).values,
                                  "rp": rp.values, "rx": (rw - rp * (1 - d.avg)).values}))
    return pd.concat(rows, ignore_index=True)


class Windows:
    """Sums over a player's rows with date in [lo, hi], by prefix sums."""

    def __init__(self, pr: pd.DataFrame):
        codes, uniq = pd.factorize(pr.pid)
        self.code = {p: i for i, p in enumerate(uniq)}
        day = (pr.date - pd.Timestamp("1990-01-01", tz="UTC")).dt.days.values
        key = codes.astype(np.int64) * 100000 + day
        o = np.argsort(key, kind="stable")
        self.key = key[o]
        self.cs = {c: np.concatenate([[0.0], np.cumsum(pr[c].values[o])]) for c in ("sp", "sx", "rp", "rx")}

    def rel(self, pids: pd.Series, lo: pd.Series, hi: pd.Series):
        base = pd.Timestamp("1990-01-01", tz="UTC")
        c = pids.map(self.code)
        ok = c.notna().values
        c = c.fillna(0).astype(np.int64).values
        l_day = (lo - base).dt.days.values
        h_day = (hi - base).dt.days.values
        i0 = np.searchsorted(self.key, c * 100000 + l_day, "left")
        i1 = np.searchsorted(self.key, c * 100000 + h_day, "right")
        s = {k: np.where(ok, v[i1] - v[i0], 0.0) for k, v in self.cs.items()}
        n_rows = np.where(ok, i1 - i0, 0)
        return s["sx"] / (s["sp"] + SHRINK), s["rx"] / (s["rp"] + SHRINK), n_rows


def name_map(a: pd.DataFrame) -> tuple[dict, int]:
    """(tour, name key) -> archive id; ties go to the id with the most rows from 2018."""
    rows = pd.concat([a[["tour", "winner_id", "winner_name", "date"]].set_axis(["tour", "id", "name", "date"], axis=1),
                      a[["tour", "loser_id", "loser_name", "date"]].set_axis(["tour", "id", "name", "date"], axis=1)])
    rows = rows.dropna(subset=["id", "name"])
    rows["recent"] = (rows.date.dt.year >= 2018).astype(int)
    cnt = rows.groupby(["tour", "name", "id"]).recent.agg(["sum", "size"]).reset_index()
    cnt["key"] = cnt.name.map(tc.name_key)
    out, multi = {}, 0
    for (t, k), g in cnt.groupby(["tour", "key"]):
        ids = g.groupby("id")[["sum", "size"]].sum().sort_values(["sum", "size"], ascending=False)
        if len(ids) > 1:
            multi += 1
        out[(t, k)] = f"{t}:{ids.index[0]}"
    return out, multi


# ── the events: who, where, what format, the two players' statistics ─────────

def events_table(q, lk, res, oc, a, avg) -> tuple[pd.DataFrame, dict]:
    info = {}
    ev = lk.dropna(subset=["comp_id"]).merge(oc, on="event_id")
    ev = ev.merge(res[["comp_id", "round_name"]], on="comp_id")
    info["linked_with_result"] = len(ev)
    ev = ev[ev.start < STATS_END].copy()
    info["before_cutoff"] = len(ev)
    ev["tour"] = np.where(ev.sport_key.str.contains("_atp_"), "ATP", "WTA")
    nm, info["name_keys_with_several_ids"] = name_map(a)
    ev["h_id"] = [nm.get((t, tc.name_key(n))) for t, n in zip(ev.tour, ev.home_name)]
    ev["a_id"] = [nm.get((t, tc.name_key(n))) for t, n in zip(ev.tour, ev.away_name)]
    names = pd.concat([ev[["tour", "home_name", "h_id"]].set_axis(["tour", "name", "id"], axis=1),
                       ev[["tour", "away_name", "a_id"]].set_axis(["tour", "name", "id"], axis=1)]).drop_duplicates(["tour", "name"])
    info["feed_names"] = len(names)
    info["feed_names_matched"] = int(names.id.notna().sum())
    info["unmatched_examples"] = names[names.id.isna()].name.head(15).tolist()
    info["player_slots"] = 2 * len(ev)
    info["player_slots_matched"] = int(ev.h_id.notna().sum() + ev.a_id.notna().sum())
    ev = ev.dropna(subset=["h_id", "a_id"]).copy()
    info["both_matched"] = len(ev)

    # best of: ESPN's, corrected at the men's Slam qualifying rounds
    qual = ev.round_name.astype(str).str.startswith("Qualifying") & ev.sport_key.isin(MEN_SLAMS)
    wq = qual & (ev.sport_key == "tennis_atp_wimbledon") & (ev.round_name == "Qualifying Final")
    info["bo_corrected"] = int((qual & ~wq & (ev.best_of != 3)).sum())
    ev["bo"] = np.where(qual & ~wq, 3, np.where(wq, 5, ev.best_of)).astype(int)

    # own archive row: tourney_date and surface
    a2 = a.dropna(subset=["winner_id", "loser_id"])
    own: dict = {}
    for r in a2[["tour", "winner_id", "loser_id", "date", "surface"]].itertuples(index=False):
        own.setdefault(frozenset((f"{r.tour}:{r.winner_id}", f"{r.tour}:{r.loser_id}")), []).append((r.date, r.surface))
    o_date, o_surf = [], []
    for r in ev.itertuples(index=False):
        best = None
        for d, s in own.get(frozenset((r.h_id, r.a_id)), []):
            dd = (d - r.start.normalize()).days
            if -20 <= dd <= 8 and (best is None or abs(dd) < best[0]):
                best = (abs(dd), d, s)
        o_date.append(best[1] if best else pd.NaT)
        o_surf.append(best[2] if best else None)
    ev["own_date"] = pd.to_datetime(pd.Series(o_date, index=ev.index), utc=True)
    ev["own_surface"] = o_surf
    info["own_row_found"] = int(ev.own_date.notna().sum())
    ev["map_surface"] = ev.sport_key.str.replace(r"^tennis_(atp|wta)_", "", regex=True).map(SURFACE)
    info["surface_map_missing"] = int(ev.map_surface.isna().sum())
    both = ev.own_surface.notna() & ev.map_surface.notna()
    info["surface_disagree"] = int((both & (ev.own_surface != ev.map_surface)).sum())
    info["surface_compared"] = int(both.sum())
    ev["surface"] = ev.own_surface.fillna(ev.map_surface).replace({"Carpet": "Hard"})

    # edition start, the fallback event date
    ev = ev.sort_values(["sport_key", "start"])
    gap = ev.groupby("sport_key").start.diff() > pd.Timedelta(days=10)
    ev["edition"] = gap.groupby(ev.sport_key).cumsum()
    ev["ed_start"] = ev.groupby(["sport_key", "edition"]).start.transform("min").dt.normalize()
    ev["E"] = ev.own_date.fillna(ev.ed_start)
    ev["w_lo"] = ev.E - pd.Timedelta(days=365)
    ev["w_hi"] = pd.concat([ev.E, ev.start.dt.normalize()], axis=1).min(axis=1) - pd.Timedelta(days=1)
    pr = player_rows(a, avg)
    w = Windows(pr)
    ev["h_spw"], ev["h_rpw"], ev["h_rows"] = w.rel(ev.h_id, ev.w_lo, ev.w_hi)
    ev["a_spw"], ev["a_rpw"], ev["a_rows"] = w.rel(ev.a_id, ev.w_lo, ev.w_hi)
    info["players_with_no_window_rows"] = int((ev.h_rows == 0).sum() + (ev.a_rows == 0).sum())
    ev["avg"] = [avg[(t, s)] for t, s in zip(ev.tour, ev.surface)]
    return ev.reset_index(drop=True), info


def matchup(ev: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    pa = np.clip(ev.avg + ev.h_spw - ev.a_rpw, CLIP_LO, CLIP_HI).values
    pb = np.clip(ev.avg + ev.a_spw - ev.h_rpw, CLIP_LO, CLIP_HI).values
    return pa, pb


# ── scoring the decidable quotes ─────────────────────────────────────────────

def decidable(pm: pd.DataFrame, ev: pd.DataFrame, market: str, dec: str) -> pd.DataFrame:
    """The decidable books' quotes at the decision, with the Pinnacle h2h anchor
    and Pinnacle's standing quote in the same market."""
    pt_a, pr_a, pr_b = (("total_point", "over_price", "under_price") if market == "totals"
                        else ("home_point", "home_price", "away_price"))
    h = pm[pm.market == market].dropna(subset=[pt_a, pr_a, pr_b])
    dq = st.decision_quotes(h, dec)
    d = dq[dq.bookmaker.isin(GAMES_BOOKS) & dq.event_id.isin(ev.event_id)].sort_values("snapshot_ts")
    hh = (pm[(pm.market == "h2h") & (pm.bookmaker == "pinnacle")].dropna(subset=["home_price", "away_price"])
          .sort_values("snapshot_ts")[["event_id", "snapshot_ts", "home_price", "away_price"]]
          .rename(columns={"snapshot_ts": "a_ts", "home_price": "a_home", "away_price": "a_away"}))
    m = pd.merge_asof(d, hh, left_on="snapshot_ts", right_on="a_ts", by="event_id", direction="backward")
    pin = (h[h.bookmaker == "pinnacle"].sort_values("snapshot_ts")[["event_id", "snapshot_ts", pt_a, pr_a, pr_b]]
           .rename(columns={"snapshot_ts": "pin_ts", pt_a: "pin_point", pr_a: "pin_a", pr_b: "pin_b"}))
    m = pd.merge_asof(m, pin, left_on="snapshot_ts", right_on="pin_ts", by="event_id", direction="backward")
    m["market"], m["decision"] = market, dec
    return m


def score(dq: pd.DataFrame, ev: pd.DataFrame, market: str, stats: pd.DataFrame | None = None):
    """Both sides of each anchored quote with the model's P(win), P(push), EV,
    the book's own no-vig chance, Pinnacle's same-line no-vig chance and the
    grade. `stats` replaces the events' four statistics (the placebo)."""
    e = ev if stats is None else ev.drop(columns=["h_spw", "h_rpw", "a_spw", "a_rpw"]).merge(stats, on="event_id")
    pa0, pb0 = matchup(e)
    e = e.assign(pa0=pa0, pb0=pb0)
    x = dq.dropna(subset=["a_home", "a_away"]).copy()
    ia = 1 / x.a_home.map(tc.american_to_decimal).values
    ib = 1 / x.a_away.map(tc.american_to_decimal).values
    x["target"] = power_side(ia, ib)
    u = x[["event_id", "target"]].drop_duplicates().merge(
        e[["event_id", "pa0", "pb0", "bo", "status", "total", "margin", "start", "season", "best_of"]], on="event_id")
    d, pa, pb, miss, guard = anchor(u.pa0.values, u.pb0.values, u.bo.values, u.target.values)
    tot, mar = distributions(pa, pb, u.bo.values)
    u = u.assign(delta=d, pa=pa, pb=pb, miss=miss, guard=guard, uix=np.arange(len(u)))
    x = x.merge(u, on=["event_id", "target"])
    n_miss = int((x.miss > ANCHOR_TOL).sum())
    x = x[x.miss <= ANCHOR_TOL]
    s = sides(x.assign(r_a=np.nan, r_b=np.nan), market)
    ui = s.uix.values
    pt = s.point.values.astype(float)
    if market == "totals":
        cdf = np.cumsum(tot, axis=1)
        over = (s.side == "over").values
        fl = np.clip(np.floor(pt).astype(int), -1, NT - 1)
        p_le_fl = np.where(fl >= 0, cdf[ui, np.maximum(fl, 0)], 0.0)
        is_int = pt == np.floor(pt)
        p_eq = np.where(is_int & (fl >= 0), tot[ui, np.clip(fl, 0, NT - 1)], 0.0)
        p_win = np.where(over, 1 - p_le_fl, p_le_fl - p_eq)
        p_push = p_eq
        own_a, own_b = np.where(over, s.over_price, s.under_price), np.where(over, s.under_price, s.over_price)
        pin_a, pin_b = np.where(over, s.pin_a, s.pin_b), np.where(over, s.pin_b, s.pin_a)
        same = (s.pin_point.values == s.total_point.values)
    else:
        cdf = np.cumsum(mar, axis=1)
        home = (s.side == "home").values
        # home wins when margin > -point; away wins when margin < point
        thr = np.where(home, -pt, pt)
        fl = np.floor(thr).astype(int) + MOFF
        p_le = np.where(fl >= 0, cdf[ui, np.clip(fl, 0, NM - 1)], 0.0)
        is_int = thr == np.floor(thr)
        p_eq = np.where(is_int & (fl >= 0) & (fl < NM), mar[ui, np.clip(fl, 0, NM - 1)], 0.0)
        p_win = np.where(home, 1 - p_le, p_le - p_eq)
        p_push = p_eq
        own_a, own_b = np.where(home, s.home_price, s.away_price), np.where(home, s.away_price, s.home_price)
        pin_a, pin_b = np.where(home, s.pin_a, s.pin_b), np.where(home, s.pin_b, s.pin_a)
        same = (s.pin_point.values == s.home_point.values)
    dec_ = _dec(s.price.values)
    s["p_model"], s["p_push"] = p_win, p_push
    s["ev"] = p_win * (dec_ - 1) - (1 - p_win - p_push)
    oa, ob = 1 / _dec(own_a), 1 / _dec(own_b)
    s["p_book_novig"] = oa / (oa + ob)
    pa_, pb_ = (np.where(same, v.astype(float), np.nan) for v in (pin_a, pin_b))
    ia_, ib_ = 1 / _dec(pa_), 1 / _dec(pb_)
    s["p_pin_novig"] = ia_ / (ia_ + ib_)
    s["anchor_age_min"] = (s.snapshot_ts - s.a_ts).dt.total_seconds() / 60
    return s, n_miss


def _dec(p) -> np.ndarray:
    """American to decimal, vectorised; NaN stays NaN."""
    p = np.asarray(p, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(p > 0, 1 + p / 100, 1 + 100 / np.abs(p))


def best_per_event(s: pd.DataFrame, cut: float) -> pd.DataFrame:
    b = s[s.ev >= cut].sort_values(["ev", "bookmaker", "side"], ascending=[False, True, True])
    return b.drop_duplicates(["event_id"])


def line(t: dict) -> str:
    return (f"bets {t['bets']:5,} won {t['won']:5,} void {t['void']:3}  units {t['units']:+8.2f}  "
            f"roi {t['roi']:+.4f}  ci90 ({float(t['ci90'][0]):+.4f}, {float(t['ci90'][1]):+.4f})")


# ── the information test ─────────────────────────────────────────────────────

def _logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def info_test(s: pd.DataFrame, market: str, base_col: str, label: str) -> None:
    import statsmodels.api as sm
    first = "over" if market == "totals" else "home"
    g = s[(s.side == first) & s.grade.isin([tc.WIN, tc.LOSS])].dropna(subset=[base_col])
    if len(g) < 50:
        print(f"    {label}: {len(g)} rows, too few")
        return
    y = (g.grade == tc.WIN).astype(float).values
    pm_ = (g.p_model / (1 - g.p_push)).clip(1e-6, 1 - 1e-6).values
    pb_ = g[base_col].clip(1e-6, 1 - 1e-6).values
    out = []
    for nm_, p in (("base", pb_), ("model", pm_)):
        ll = -(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()
        out.append(f"{nm_} brier {((p - y) ** 2).mean():.5f} logloss {ll:.5f}")
    X = sm.add_constant(np.column_stack([_logit(pb_), _logit(pm_) - _logit(pb_)]))
    try:
        r0 = sm.Logit(y, X).fit(disp=0)
        r1 = sm.Logit(y, X).fit(disp=0, cov_type="cluster", cov_kwds={"groups": pd.factorize(g.event_id)[0]})
        reg = (f"b_diff {r0.params[2]:+.4f} se {r0.bse[2]:.4f} (clustered {r1.bse[2]:.4f}, z {r1.params[2] / r1.bse[2]:+.2f}); "
               f"b_base {r0.params[1]:+.4f}")
    except Exception as exc:          # a singular fit is reported, not hidden
        reg = f"fit failed: {exc}"
    print(f"    {label}: n {len(g):6,} events {g.event_id.nunique():5,}  mean y {y.mean():.4f} "
          f"mean base {pb_.mean():.4f} mean model {pm_.mean():.4f}")
    print(f"      {out[0]} | {out[1]}")
    print(f"      {reg}")


# ── kill tests ───────────────────────────────────────────────────────────────

def price_band(p):
    p = np.asarray(p, float)
    return np.select([p <= -130, p <= -111, p <= -101], ["<=-130", "-129..-111", "-110..-101"], "+100 up")


def splits(b: pd.DataFrame, market: str) -> None:
    b = b.sort_values("start").reset_index(drop=True)
    half = np.where(np.arange(len(b)) < len(b) // 2, "early", "late")
    groups = {"season": b.season, "half": pd.Series(half), "side": b.side, "book": b.bookmaker,
              "best_of": b.bo, "price": pd.Series(price_band(b.price))}
    if market == "spreads":
        groups["fav/dog"] = pd.Series(np.where(b.point < 0, "favourite", np.where(b.point > 0, "dog", "level")))
    for name, key in groups.items():
        parts = []
        for k, g in b.groupby(key.values):
            t = table(g)
            parts.append(f"{k}: {t['bets']} / {t['units']:+.2f}u / {t['roi']:+.3f}")
        print(f"      by {name:7s} " + " | ".join(parts))
    day = b.groupby(b.start.dt.date).units.sum().sort_values(ascending=False)
    print(f"      five best days {day.head(5).sum():+.2f}u of {b.units.sum():+.2f}u; without them "
          f"{b.units.sum() - day.head(5).sum():+.2f}u over {b.start.dt.date.nunique()} days")


def placebo(dq, ev, market, cut, real_units, rng) -> None:
    keep = ev[["event_id", "tour", "h_spw", "h_rpw", "a_spw", "a_rpw"]]
    res = []
    t0 = time.time()
    for _ in range(N_SHUFFLE):
        parts = []
        for _, g in keep.groupby("tour"):
            perm = rng.permutation(len(g))
            parts.append(pd.DataFrame({"event_id": g.event_id.values,
                                       **{c: g[c].values[perm] for c in ("h_spw", "h_rpw", "a_spw", "a_rpw")}}))
        s, _ = score(dq, ev, market, stats=pd.concat(parts))
        res.append(best_per_event(s, cut).units.sum())
    r = np.array(res)
    print(f"      placebo ({N_SHUFFLE} shuffles, {time.time() - t0:.0f}s): mean {r.mean():+.2f} sd {r.std(ddof=1):.2f} "
          f"p5 {np.percentile(r, 5):+.2f} p50 {np.percentile(r, 50):+.2f} p95 {np.percentile(r, 95):+.2f}; "
          f"real {real_units:+.2f}; share of shuffles >= real {np.mean(r >= real_units):.3f}")


def walk_forward(s: pd.DataFrame) -> None:
    seasons = sorted(s.season.unique())
    total_u, total_r, total_n, rows = 0.0, 0.0, 0, []
    for i, yr in enumerate(seasons[1:], start=1):
        past = s[s.season < yr]
        scores = {c: best_per_event(past, c).units.sum() for c in CUTS}
        c_best = max(scores, key=scores.get)
        if scores[c_best] <= 0:
            rows.append(f"{yr}: no cut positive before, no bets")
            continue
        b = best_per_event(s[s.season == yr], c_best)
        total_u += b.units.sum()
        total_r += b.risk.sum()
        total_n += len(b)
        rows.append(f"{yr}: cut {c_best:.2f} -> {len(b)} bets {b.units.sum():+.2f}u")
    roi = total_u / total_r if total_r else float("nan")
    print("      walk-forward: " + "; ".join(rows) + f"  TOTAL {total_n} bets {total_u:+.2f}u roi {roi:+.4f}")


# ── self-test ────────────────────────────────────────────────────────────────

def _simulate(pa: float, pb: float, best_of: int, n: int, rng) -> np.ndarray:
    """Point-by-point simulation, sharing no code with the DP: (A games, B games,
    1 if A won the match)."""
    out = np.zeros((n, 3), dtype=int)
    need = (best_of + 1) // 2
    for i in range(n):
        server = 0 if rng.random() < 0.5 else 1
        sets = [0, 0]
        games_total = [0, 0]
        while max(sets) < need:
            g = [0, 0]
            while True:
                if g[0] == 6 and g[1] == 6:
                    pts, k, first = [0, 0], 0, server
                    while True:
                        srv = first if (k == 0 or ((k - 1) // 2) % 2 == 1) else 1 - first
                        p = pa if srv == 0 else pb
                        win_srv = rng.random() < p
                        pts[srv if win_srv else 1 - srv] += 1
                        k += 1
                        if max(pts) >= 7 and abs(pts[0] - pts[1]) >= 2:
                            break
                    w = 0 if pts[0] > pts[1] else 1
                    g[w] += 1
                    server = 1 - server       # 13 games: the receiver of game 13 serves next
                    break
                p = pa if server == 0 else pb
                pts = [0, 0]
                while True:
                    pts[0 if rng.random() < p else 1] += 1
                    if max(pts) >= 4 and abs(pts[0] - pts[1]) >= 2:
                        break
                won = server if pts[0] > pts[1] else 1 - server
                g[won] += 1
                server = 1 - server
                if (max(g) == 6 and min(g) <= 4) or max(g) == 7:
                    break
            sets[0 if g[0] > g[1] else 1] += 1
            games_total[0] += g[0]
            games_total[1] += g[1]
        out[i] = (games_total[0], games_total[1], int(sets[0] > sets[1]))
    return out


def self_test() -> int:
    ok = True

    def check(name, cond):
        nonlocal ok
        ok &= bool(cond)
        print(f"  {'ok ' if cond else 'FAIL'} {name}")

    check("hold(0.5) = 0.5", abs(float(hold(0.5)) - 0.5) < 1e-12)
    check(f"hold(0.6) = {float(hold(0.6)):.6f} ~ 0.7357", abs(float(hold(0.6)) - 0.7357) < 5e-5)
    for bo in (3, 5):
        p = np.array([0.55, 0.62, 0.70])
        w = match_win(p, p, np.full(3, bo))
        check(f"symmetric players win 0.5 (best of {bo}): {np.round(w, 12)}", np.allclose(w, 0.5, atol=1e-12))
        pa, pb = np.array([0.66, 0.58, 0.72]), np.array([0.61, 0.64, 0.55])
        t, m = distributions(pa, pb, np.full(3, bo))
        j = joint(pa, pb, np.full(3, bo))
        check(f"distributions sum to 1 (best of {bo})", np.allclose(t.sum(1), 1) and np.allclose(m.sum(1), 1)
              and np.allclose(j.sum((1, 2)), 1))
        jt = np.array([[j[i][np.add.outer(np.arange(36), np.arange(36)) == k].sum() for k in range(NT)] for i in range(3)])
        jm = np.array([[j[i][np.subtract.outer(np.arange(36), np.arange(36)) == k - MOFF].sum() for k in range(NM)] for i in range(3)])
        check(f"joint's marginals equal the marginal DPs (best of {bo})", np.allclose(jt, t) and np.allclose(jm, m))
    d = np.linspace(-0.3, 0.3, 61)
    w = match_win(np.clip(0.63 + d, GUARD_LO, GUARD_HI), np.clip(0.63 - d, GUARD_LO, GUARD_HI), np.full(61, 3))
    check("P(A wins) rises with delta", np.all(np.diff(w) > 0))
    tgt = np.array([0.1, 0.35, 0.5, 0.8, 0.95])
    dd, pa, pb, miss, guard = anchor(np.full(5, 0.64), np.full(5, 0.60), np.full(5, 3), tgt)
    check(f"anchor reaches its targets (max miss {miss.max():.2e})", miss.max() < 1e-6)
    check("anchor keeps pA + pB", np.allclose(pa + pb, 1.24))
    rng = np.random.default_rng(1)
    for bo, pa_, pb_ in ((3, 0.66, 0.60), (5, 0.70, 0.64)):
        sim = _simulate(pa_, pb_, bo, 20000, rng)
        t, m = distributions(np.array([pa_]), np.array([pb_]), np.array([bo]))
        mt, mm = (t[0] * np.arange(NT)).sum(), (m[0] * (np.arange(NM) - MOFF)).sum()
        st_, sm_ = sim[:, 0] + sim[:, 1], sim[:, 0] - sim[:, 1]
        se_t, se_m = st_.std() / math.sqrt(len(sim)), sm_.std() / math.sqrt(len(sim))
        check(f"simulation agrees, best of {bo}: mean total DP {mt:.3f} sim {st_.mean():.3f} (se {se_t:.3f}); "
              f"mean margin DP {mm:.3f} sim {sm_.mean():.3f} (se {se_m:.3f})",
              abs(mt - st_.mean()) < 4 * se_t and abs(mm - sm_.mean()) < 4 * se_m)
        hist = np.bincount(st_, minlength=NT)[:NT] / len(sim)
        check(f"simulation total-games histogram within 0.01 of DP, best of {bo} (max gap {np.abs(hist - t[0]).max():.4f})",
              np.abs(hist - t[0]).max() < 0.01)
        w = match_win(np.array([pa_]), np.array([pb_]), np.array([bo]))[0]
        sw, se_w = sim[:, 2].mean(), math.sqrt(sim[:, 2].mean() * (1 - sim[:, 2].mean()) / len(sim))
        check(f"simulation agrees on P(A wins), best of {bo}: DP {w:.4f} sim {sw:.4f} (se {se_w:.4f})",
              abs(w - sw) < 4 * se_w)
    print("SELF-TEST", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


# ── diagnostics, added after the round's results (not part of the fixed design) ──

def _cond(s):
    return (s.p_model / (1 - s.p_push)).clip(1e-6, 1 - 1e-6)


def archive_check(arch: pd.DataFrame, avg: dict) -> None:
    """The game model on the archive's own 2015-2019 tour-level completed matches:
    fed each match's REALISED serve shares (outcome-contaminated: a bound on the
    programme's behaviour, not a validation; the simulation in --self-test is
    that), and fed two average players (no lopsidedness at all)."""
    a = arch[arch.main & arch.date.dt.year.between(2015, 2019)]
    a = a[np.array([lv in TOUR_LEVELS[t] for lv, t in zip(a.tourney_level.astype(str), a.tour)]) & _has_stats(a).values]
    r = a.score.astype(str).map(tc.from_archive_score)
    ok = np.array([x is not None and x.status == "complete" and not x.super_tb_last for x in r])
    a, r = a[ok], [x for x, k in zip(r, ok) if k]
    a = a.assign(total=[x.total_games for x in r])
    a = a[a.best_of.isin([3, 5])]
    pw = ((a.w_1stWon + a.w_2ndWon) / a.w_svpt).clip(GUARD_LO, GUARD_HI).values
    pl = ((a.l_1stWon + a.l_2ndWon) / a.l_svpt).clip(GUARD_LO, GUARD_HI).values
    t, _ = distributions(pw, pl, a.best_of.values)
    base = np.array([avg[(tt, sf if sf in ("Hard", "Clay", "Grass") else "Hard")] for tt, sf in zip(a.tour, a.surface)])
    t0, _ = distributions(base, base, a.best_of.values)
    a = a.assign(realised=(t * np.arange(NT)).sum(1), even=(t0 * np.arange(NT)).sum(1))
    print(a.groupby(["tour", "best_of"]).agg(matches=("total", "size"), actual_total=("total", "mean"),
                                              model_realised_shares=("realised", "mean"),
                                              model_two_average_players=("even", "mean")).round(3).to_string())


def nested(s0: pd.DataFrame, s1: pd.DataFrame, market: str, base_col: str, label: str) -> None:
    """y ~ logit(base) + dev_nostats + (dev_stats - dev_nostats): the last
    coefficient is what the players' statistics add to the stats-free model."""
    import statsmodels.api as sm
    first = "over" if market == "totals" else "home"
    k = ["event_id", "bookmaker", "side"]
    g = s1[(s1.side == first) & s1.grade.isin([tc.WIN, tc.LOSS])].assign(pm1=_cond).merge(
        s0[s0.side == first].assign(pm0=_cond)[k + ["pm0"]], on=k).dropna(subset=[base_col])
    y = (g.grade == tc.WIN).astype(float).values
    lb = _logit(g[base_col].values)
    d0, d1 = _logit(g.pm0.values) - lb, _logit(g.pm1.values) - lb
    grp = {"groups": pd.factorize(g.event_id)[0]}
    r = sm.Logit(y, sm.add_constant(np.column_stack([lb, d0, d1 - d0]))).fit(disp=0, cov_type="cluster", cov_kwds=grp)
    r0 = sm.Logit(y, sm.add_constant(np.column_stack([lb, d0]))).fit(disp=0, cov_type="cluster", cov_kwds=grp)
    print(f"    {label}: n {len(g):,}; stats-free model alone: b_dev0 {r0.params[2]:+.4f} se {r0.bse[2]:.4f} "
          f"(z {r0.params[2] / r0.bse[2]:+.2f}); nested: b_dev0 {r.params[2]:+.4f} se {r.bse[2]:.4f}, "
          f"b_stats {r.params[3]:+.4f} se {r.bse[3]:.4f} (z {r.params[3] / r.bse[3]:+.2f})  [clustered by event]")


def diagnose(arch, avg, q, ev, pm) -> int:
    print("\nDIAGNOSE (added after the round's results; not part of the fixed design)")
    print("\n1. RAW QUOTES BY YEAR OF THE LISTED START (every row in the cache, before any filter), the games markets")
    r = q[q.market.isin(["totals", "spreads"]) & q.bookmaker.isin(list(GAMES_BOOKS) + ["pinnacle"])]
    print(r.groupby([r.market, r.bookmaker, r.commence_time.dt.year]).size().unstack(fill_value=0).to_string())
    print("   feed events by year:", q.drop_duplicates("event_id").commence_time.dt.year.value_counts().sort_index().to_dict())
    pa_raw = ev.avg + ev.h_spw - ev.a_rpw
    pb_raw = ev.avg + ev.a_spw - ev.h_rpw
    print(f"   matchup clip [0.40, 0.90] reached: pA {int(((pa_raw < CLIP_LO) | (pa_raw > CLIP_HI)).sum())}, "
          f"pB {int(((pb_raw < CLIP_LO) | (pb_raw > CLIP_HI)).sum())} of {len(ev):,} events")
    print("\n2. THE GAME MODEL ON THE ARCHIVE (2015-2019 tour-level completed matches)")
    archive_check(arch, avg)
    zero = ev[["event_id"]].assign(h_spw=0.0, h_rpw=0.0, a_spw=0.0, a_rpw=0.0)
    for market in ("totals", "spreads"):
        print(f"\n===================== {market.upper()} =====================")
        for dec in st.DECISIONS:
            dq = decidable(pm, ev, market, dec)
            s1, _ = score(dq, ev, market)
            s0, _ = score(dq, ev, market, stats=zero)
            s1 = s1.merge(ev[["event_id", "tour"]], on="event_id")
            print(f"\n--- {market} {dec}")
            first = "over" if market == "totals" else "home"
            g = s1[(s1.side == first) & s1.grade.isin([tc.WIN, tc.LOSS])].copy()
            g["won"] = (g.grade == tc.WIN).astype(float)
            g["p_cond"] = _cond(g)
            u = g.drop_duplicates(["event_id", "target"])
            t, mg = distributions(u.pa.values, u.pb.values, u.bo.values)
            u = u.assign(m_tot=(t * np.arange(NT)).sum(1), m_mar=(mg * (np.arange(NM) - MOFF)).sum(1))
            g = g.merge(u[["event_id", "target", "m_tot", "m_mar"]], on=["event_id", "target"])
            if market == "totals":
                print("  a. the model's level against the line, by tour and best of (over side, completed, every decidable quote)")
                print(g.groupby(["tour", "bo"]).agg(quotes=("won", "size"), line=("point", "mean"), actual=("total", "mean"),
                                                   model_mean_total=("m_tot", "mean"), p_over_model=("p_cond", "mean"),
                                                   p_over_book=("p_book_novig", "mean"), over_rate=("won", "mean"))
                      .round(3).to_string())
            else:
                g["fav"] = np.where(g.point < 0, "home favourite", np.where(g.point > 0, "home dog", "level"))
                print("  a. orientation: the home side's cover chance, by whether home gives games (completed, every decidable quote)")
                print(g.groupby(["fav", "bo"]).agg(quotes=("won", "size"), home_point=("point", "mean"),
                                                  actual_margin=("margin", "mean"), model_mean_margin=("m_mar", "mean"),
                                                  p_cover_model=("p_cond", "mean"), p_cover_book=("p_book_novig", "mean"),
                                                  cover_rate=("won", "mean")).round(3).to_string())
            print("  b. the stats-free model (all four statistics 0) against the stats model")
            nested(s0, s1, market, "p_book_novig", "base = the book's own no-vig")
            nested(s0, s1, market, "p_pin_novig", "base = Pinnacle's same-line no-vig")
            print("  c. side composition of the bets, by cut")
            for cut in CUTS:
                b = best_per_event(s1, cut)
                comp = {k: int(v) for k, v in b.side.value_counts().items()}
                if market == "spreads":
                    comp.update({"favourite": int((b.point < 0).sum()), "dog": int((b.point > 0).sum())})
                print(f"    EV>={cut:.2f}  bets {len(b):5,}  {comp}")
            print("  d. bets above EV 0.08, in coarser bands")
            b = best_per_event(s1, 0.08)
            for lo, hi in ((0.08, 0.12), (0.12, 0.16), (0.16, 9.0)):
                x = b[(b.ev >= lo) & (b.ev < hi)]
                if len(x):
                    print(f"    EV [{lo:.2f}, {hi:.2f})  {line(table(x))}")
            print("  e. best of five (the men's Slam main draws) and best of three, every cut")
            for cut in CUTS:
                b = best_per_event(s1, cut)
                parts = [f"bo{k}: {line(table(x))}" for k, x in b.groupby("bo")]
                print(f"    EV>={cut:.2f}  " + "  ||  ".join(parts))
            print("  g. BLIND, no model: every decidable quote on each side, by best of (mechanism 5 for spreads: "
                  "does the favourite cover more at best of five?)")
            x = s1.assign(kind=s1.side if market == "totals" else
                          np.where(s1.point < 0, "favourite", np.where(s1.point > 0, "dog", "level")))
            for (bo, kind), gx in x.groupby(["bo", "kind"]):
                print(f"    bo{bo} {kind:9s} every quote: {line(table(gx))}")
            for (bo, kind), gx in x.groupby(["bo", "kind"]):
                bp = gx.sort_values(["price", "bookmaker"], ascending=[False, True]).drop_duplicates("event_id")
                print(f"    bo{bo} {kind:9s} one a match, best price of the three books: {line(table(bp))}")
            if market == "spreads":
                bp = x[(x.bo == 5) & (x.kind == "favourite")].sort_values(
                    ["price", "bookmaker"], ascending=[False, True]).drop_duplicates("event_id")
                print("  h. the best-of-five favourite, blind, one a match at the best price: the kill-test splits")
                splits(bp, market)
            b = best_per_event(s1, 0.0)
            print("  f. bets at EV>=0.00 by season:", {int(k): int(v) for k, v in b.season.value_counts().sort_index().items()},
                  "; by book:", {k: int(v) for k, v in b.bookmaker.value_counts().items()})
    return 0


# ── main ─────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path)
    ap.add_argument("--spool")
    ap.add_argument("--save", type=Path)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--no-placebo", action="store_true")
    ap.add_argument("--diagnose", action="store_true",
                    help="after the round: why the grid looks as it does (not part of the fixed design)")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    pd.set_option("display.width", 220)
    t0 = time.time()
    arch = load_archive(a.spool)
    avg = averages(arch)
    print("TOUR x SURFACE SERVE AVERAGE (main tour files, tour levels, 2015-2019):",
          {f"{k[0]} {k[1]}": round(v, 4) for k, v in sorted(avg.items())})
    q, res = load(a.cache)
    lk = st.link(q, res)
    oc = outcomes(lk, res)
    print(f"\nPOPULATION\n  feed events {q.event_id.nunique():,}; linked to ESPN {int(lk.comp_id.notna().sum()):,}")
    ev, info = events_table(q, lk, res, oc, arch, avg)
    for k, v in info.items():
        print(f"  {k}: {v}")
    print(f"  name match rate: feed names {info['feed_names_matched']}/{info['feed_names']} = "
          f"{info['feed_names_matched'] / info['feed_names']:.4f}; player slots {info['player_slots_matched']}/"
          f"{info['player_slots']} = {info['player_slots_matched'] / info['player_slots']:.4f}")
    pa0, pb0 = matchup(ev)
    print(f"  matchup pA+pB: mean {np.mean(pa0 + pb0):.4f} sd {np.std(pa0 + pb0):.4f}; clipped "
          f"{int(((ev.avg + ev.h_spw - ev.a_rpw) < CLIP_LO).sum() + ((ev.avg + ev.h_spw - ev.a_rpw) > CLIP_HI).sum())}")
    print(f"  best of in the test population: {ev.bo.value_counts().to_dict()}; seasons {ev.season.value_counts().sort_index().to_dict()}")
    pm = st.pre_match(q, lk, res)
    pin_h2h = set(pm[(pm.market == "h2h") & (pm.bookmaker == "pinnacle")].dropna(subset=["home_price", "away_price"]).event_id)
    print(f"  with a pre-match Pinnacle h2h quote: {int(ev.event_id.isin(pin_h2h).sum()):,} of {len(ev):,}")
    print(f"  [{time.time() - t0:.0f}s]")
    if a.diagnose:
        return diagnose(arch, avg, q, ev, pm)

    rng = np.random.default_rng(SEED)
    saved, cells = [], {}
    for market in ("totals", "spreads"):
        print(f"\n===================== {market.upper()} =====================")
        for dec in st.DECISIONS:
            dq = decidable(pm, ev, market, dec)
            n_q, n_ev = len(dq), dq.event_id.nunique()
            s, n_miss = score(dq, ev, market)
            n_anch = s.drop_duplicates(["event_id", "bookmaker"]).shape[0]
            print(f"\n--- {market} {dec}: decidable quotes {n_q:,} on {n_ev:,} events; with a Pinnacle h2h anchor "
                  f"{n_anch:,} quotes on {s.event_id.nunique():,} events; dropped for an anchor miss {n_miss}; "
                  f"guard reached {int(s.guard.sum() // 2)} quotes; anchor age min p50 {s.anchor_age_min.median():.0f} "
                  f"p90 {s.anchor_age_min.quantile(.9):.0f}")
            print(f"    median EV {s.ev.median():+.4f}; mean p_model (no push) {np.mean(s.p_model / (1 - s.p_push)):.4f}")
            saved.append(s)
            print("  INFORMATION TEST")
            info_test(s, market, "p_book_novig", "model vs the book's own no-vig")
            info_test(s, market, "p_pin_novig", "model vs Pinnacle's same-line no-vig")
            sub = s[s.p_pin_novig.notna()]
            info_test(sub, market, "p_book_novig", "  (the same rows, model vs the book's own)")
            print("  GRID (one bet per event: the best EV across books and sides)")
            for cut in CUTS:
                b = best_per_event(s, cut)
                if len(b):
                    t = table(b)
                    cells[(market, dec, cut)] = (t, b, s, dq)
                    print(f"    EV>={cut:.2f}  {line(t)}")
            print("  BANDED (the one-bet-per-event set by its EV)")
            b_all = best_per_event(s, -9.0)
            g = b_all[b_all.ev < BANDS[0]]
            if len(g):
                print(f"    EV < {BANDS[0]:+.2f}          {line(table(g))}")
            for k in BANDS:
                g = b_all[(b_all.ev >= k) & (b_all.ev < k + 0.01)]
                if len(g):
                    print(f"    EV [{k:+.2f}, {k + 0.01:+.2f})  {line(table(g))}")
            g = b_all[b_all.ev >= BANDS[-1] + 0.01]
            if len(g):
                print(f"    EV >= {BANDS[-1] + 0.01:+.2f}         {line(table(g))}")
            walk_forward(s)
    print("\n===================== KILL TESTS ON EVERY POSITIVE CELL =====================")
    best = {}
    for (market, dec, cut), (t, b, s, dq) in cells.items():
        if t["units"] > 0:
            print(f"\n  {market} {dec} EV>={cut:.2f}: {line(t)}")
            splits(b, market)
            if (market, dec) not in best or t["units"] > best[(market, dec)][1]["units"]:
                best[(market, dec)] = (cut, t, s, dq)
    if not best:
        print("  none")
    if not a.no_placebo:
        print("\n===================== PLACEBO ON THE BEST CELL OF EACH MARKET x DECISION =====================")
        for (market, dec), (cut, t, s, dq) in best.items():
            print(f"\n  {market} {dec} EV>={cut:.2f}: real {t['units']:+.2f}u on {t['bets']} bets")
            placebo(dq, ev, market, cut, t["units"], rng)
    if a.save and saved:
        # best_of is the format the model used (ESPN's, corrected at men's Slam qualifying); best_of_espn is ESPN's own
        x = pd.concat(saved, ignore_index=True).rename(columns={"best_of": "best_of_espn"})
        x["best_of"] = x.bo.astype(int)
        keep = ["decision", "market", "event_id", "sport_key", "bookmaker", "side", "price", "point", "p_model",
                "p_book_novig", "ev", "grade", "units", "risk", "start", "season", "best_of", "best_of_espn", "p_push",
                "p_pin_novig", "target", "pa", "pb", "delta", "snapshot_ts", "a_ts", "anchor_age_min"]
        x[keep].to_parquet(a.save, index=False)
        print(f"\nsaved {len(x):,} scored quotes to {a.save}")
    print(f"done [{time.time() - t0:.0f}s]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
