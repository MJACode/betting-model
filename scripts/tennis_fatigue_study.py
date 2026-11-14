"""Tennis match winner: does FATIGUE or RETIREMENT RISK carry information the
market's own price lacks, and would a bet on it have made money at the books
we can bet?

READS the local research cache and the spooled match archive only:
  shop_candidates.parquet (scripts/tennis_shop_study.py --save), Pinnacle rows
  tennis_odds_quotes.parquet (who is side a / side b), tennis_espn_matches.parquet
  the Sackmann archive CSVs (2014-2026, every level spooled)
WRITES nothing but a regenerable feature cache (--features, outside the repo)
and its own report. No database, no network, no paid call.

    python -m scripts.tennis_fatigue_study --cache C:/Users/micha/tennis_research/cache \\
        --spool C:/Users/micha/tennis_research/spool

EVERYTHING BELOW WAS FIXED BEFORE ANY RESULT WAS READ.

POPULATION
  A priced match is a feed event in the candidates with a Pinnacle-referenced
  close row, starting (ESPN start) before 2026-06-01 (the archive's last
  tourney_date is 2026-05-25). Outcome y = side a (the feed's home player)
  advances, from ESPN (scripts/tennis_market_study.espn_result: the retiring
  player loses once a set is complete, Pinnacle's own grading); events whose
  ESPN row has both winner flags false are dropped (espn_result would call
  them a loss for side a). Walkovers are already out of the candidates.

LINKS (all names through models.tennis_common.name_key)
  archive <-> ESPN   same tour, same two name keys, ESPN start - tourney_date in
                     [-11, +16] days; cost |dd - median dd of the round| (the
                     medians measured on a first pass with cost |dd - 2|, by
                     Grand Slam or not and round); each row used once, lowest
                     cost first. A linked archive row takes ESPN's exact start.
  feed -> archive    the feed's home and away names against the archive's
                     winner and loser, same tour, ESPN start - tourney_date in
                     [-11, +16] days, nearest by the archive row's date (exact
                     where linked, else estimated). Second pass for the rest:
                     each feed name key a subset or superset of one archive
                     name key, and exactly one archive row in the window.
                     The archive winner is checked against ESPN's outcome.
  timeline           keyed on the archive's own player ids (tour, id), never
                     names. Walkovers are not matches and are left out.
  match date         ESPN's exact start where the archive row is linked; else
                     tourney_date + the round's median offset (above).

FEATURES, per player, from the player's archive matches strictly before this
one (ordered by tourney_date, tourney_id, round order Q1<Q2<Q3<Q4<R128<R64<
R32<R16<RR<QF<SF<BR<F, match_num); each enters as the difference a - b:
  prev_minutes   minutes of the previous match if it was in the SAME event
                 (same tourney_id), in hours; NaN when there is none or the
                 archive has no minutes (minutes <= 0 or > 420 read as missing)
  prev_sets      sets played in that same-event previous match; NaN if none
  prev_distance  1 if that match went the distance (sets played = its best-of)
  days_since     log(1 + min(days since the previous match in any event, 365));
                 NaN when the archive holds no earlier match
  matches14      matches played in the 14 days before this one (by date)
  ret30          1 if the player lost a match by 'RET' in the 30 days before
  age            archive age at this event, years
  MISSING VALUES: a row missing a feature for either player is left out of
  that feature's test; joint fits are complete-case; nothing is imputed.

TEST 2, THE INFORMATION TEST (one row per event: side a, never both sides)
  p_market = power de-vig (scripts/tennis_shop_checks.power_side) of the
  Pinnacle pair standing at the close: per event, the close row with the
  latest ref_ts. L = logit(p_market). Three models on the same rows:
    raw     p_market itself (slope 1, no fit)
    market  y ~ 1 + L            (recalibrated market)
    feature y ~ 1 + L + x        (x = the a - b difference)
  Rows: F1..F7 one at a time; F8 = prev_minutes on men's best-of-five only
  (the scout's own population); J1 = F1..F7 jointly, complete-case; J2 =
  days_since, matches14, ret30, age jointly, complete-case.
  Coefficients and standard errors from one fit on every season. Out of
  sample: fit on seasons < S, score S, S = 2022..2026; report the change in
  log-loss feature - market, per season and pooled with a paired standard
  error over matches.
  A FEATURE IMPROVES only if the pooled change is below zero AND it is below
  zero in at least 4 of the 5 held-out seasons.
  (Added after the first run, as a reported column and NOT a pass criterion:
  the pooled change feature - raw with its paired standard error, because the
  first run showed the recalibrated market scoring worse out of sample than
  the raw power price itself.)

TEST 3, THE BET RULE (run for, and only for, a model that improves)
  Per decision (first, t12, close): the same two fits walk-forward on that
  decision's Pinnacle pair (per event, the row with the latest ref_ts), seasons
  2022..2026 scored. Every decidable quote both ways at that decision gets
  p_model (side b = 1 - side a's), EV = p_model x decimal - 1 + the book's
  retirement term (DraftKings +r; Caesars and the unread books +r - r(d-1);
  FanDuel, BetMGM 0; r the study's flat per-side rate, as the current best
  candidate). One bet per event and decision: the best EV across books and
  sides. Cuts EV >= 0.00, 0.01, 0.02, 0.03, 0.05, no price floor; a banded EV
  table. The identical rule on the market-only recalibrated fit and on the
  raw power price, same rows, isolates what the feature adds. Kill tests at
  EV >= 0.02, each decision: by season, early/late half, favourite/underdog,
  price band, book; placebo: the event-level feature shuffled across events
  within season 200 times, every walk-forward fit redone.

TEST 4, RETIREMENT RISK AT DRAFTKINGS
  A logistic for a player retiring after set one (the archive's score read by
  tc.from_archive_score, retired and first set complete, the player the
  loser), fit on the archive's 2015-2019 tour-level matches (men G, M, A, F;
  women G, PM, P, I, F; walkovers out) on: prev_minutes in hours (0 with an
  indicator when there is no same-event previous match with minutes), ret30,
  age, best-of-five, surface (clay, grass, carpet against hard) and tour (the
  flat rate's own split). Rows without an age are dropped from the fit and get
  the flat rate when applied. Scored on the 2020-2026 priced matches against
  ESPN (the side retired after a completed set): calibration by decile, Brier
  and log-loss against the flat rate (scripts/tennis_shop_study.retire_rates),
  the same on DraftKings-priced sides. Then the current best candidate (close,
  best decidable price both ways, EV = p_power x d - 1 + the book's term,
  0.02 <= EV < 0.05, price >= -500, one bet per event) with the flat rate
  replaced by the modelled per-side chances (DraftKings +r_own; full-match
  books +r_own - r_opp(d-1)), nothing else changed.

TEST 5, DESCRIPTIVE
  At the close, side a: realised advance rate minus p_market, binned by the
  prev_minutes difference a - b in minutes (<= -90, -90..-45, -45..-15,
  -15..15, 15..45, 45..90, >= 90), men's best-of-five and everything else.

THE BAR: positive in units at real prices with an interval; a plateau across
cuts; positive in both halves and across seasons; no one side or price band
carrying the total; the placebo clearly below; 25+ bets per cell.
"""
from __future__ import annotations

import argparse
import glob
import math
from pathlib import Path

import numpy as np
import pandas as pd

from models import tennis_common as tc
from scripts import tennis_market_study as st
from scripts.tennis_shop_checks import power_side
from scripts.tennis_shop_study import retire_rates, table

ARCHIVE_FIRST_YEAR = 2014
END = pd.Timestamp("2026-06-01", tz="UTC")
WINDOW = (-11.0, 16.0)
ROUND_ORDER = {"Q1": 0, "Q2": 1, "Q3": 2, "Q4": 3, "R128": 10, "R64": 11, "R32": 12, "R16": 13,
               "RR": 13.5, "QF": 14, "SF": 15, "BR": 16, "F": 17, "f": 17}
TOUR_LEVELS = {"ATP": {"G", "M", "A", "F"}, "WTA": {"G", "PM", "P", "I", "F"}}
FEATURES = ["prev_minutes", "prev_sets", "prev_distance", "days_since", "matches14", "ret30", "age"]
CUTS = (0.0, 0.01, 0.02, 0.03, 0.05)
OOS_SEASONS = (2022, 2023, 2024, 2025, 2026)
DECISIONS = ("first", "t12", "close")
KILL_CUT = 0.02


# ── the archive ──────────────────────────────────────────────────────────────

def load_archive(spool: str) -> pd.DataFrame:
    frames = []
    for tour, pre in (("ATP", "atp"), ("WTA", "wta")):
        for f in sorted(glob.glob(f"{spool}/sackmann__{pre}__{pre}_matches_*.csv")):
            if int(f[-8:-4]) < ARCHIVE_FIRST_YEAR:
                continue
            d = pd.read_csv(f, dtype={"tourney_level": str, "winner_id": str, "loser_id": str,
                                      "tourney_id": str}, low_memory=False)
            frames.append(d.assign(tour=tour))
    a = pd.concat(frames, ignore_index=True)
    a = a.dropna(subset=["winner_id", "loser_id"]).reset_index(drop=True)
    a["tdate"] = pd.to_datetime(a.tourney_date.astype(int).astype(str), format="%Y%m%d")
    a["rord"] = a["round"].map(ROUND_ORDER).fillna(12.0)
    a["is_g"] = a.tourney_level == "G"
    a["minutes"] = pd.to_numeric(a.minutes, errors="coerce")
    a.loc[(a.minutes <= 0) | (a.minutes > 420), "minutes"] = np.nan
    res = [tc.from_archive_score(s, int(b) if pd.notna(b) else 3) for s, b in zip(a.score.astype(str), a.best_of)]
    a["walkover"] = [r is None or r.status == "walkover" for r in res]
    a["sets"] = [np.nan if r is None else float(len(r.a_games)) for r in res]
    a["ret_after1"] = [r is not None and r.status == "retired" and r.first_set_complete for r in res]
    a["ret_token"] = a.score.astype(str).str.upper().str.contains("RET")
    a["kw"] = a.winner_name.map(tc.name_key)
    a["kl"] = a.loser_name.map(tc.name_key)
    a["k"] = [frozenset((w, l)) for w, l in zip(a.kw, a.kl)]
    return a


def link_archive_espn(a: pd.DataFrame, e: pd.DataFrame) -> tuple:
    """Exact ESPN start for each archive row that matches one (see docstring)."""
    ek = e[["comp_id", "tour", "start_time", "p1_name", "p2_name"]].copy()
    ek["k"] = [frozenset((tc.name_key(x), tc.name_key(y))) for x, y in zip(ek.p1_name, ek.p2_name)]
    ek["start"] = ek.start_time.dt.tz_convert("UTC").dt.tz_localize(None)
    m = a[["tour", "k", "tdate", "is_g", "round"]].reset_index().rename(columns={"index": "arow"}).merge(
        ek[["comp_id", "tour", "k", "start"]], on=["tour", "k"])
    m["dd"] = (m.start - m.tdate).dt.total_seconds() / 86400
    m = m[m.dd.between(*WINDOW)]

    def assign(mm: pd.DataFrame, cost: pd.Series) -> pd.DataFrame:
        mm = mm.assign(cost=cost).sort_values("cost")
        used_a, used_e, keep = set(), set(), []
        for i, ar, cid in zip(mm.index, mm.arow, mm.comp_id):
            if ar in used_a or cid in used_e:
                continue
            used_a.add(ar)
            used_e.add(cid)
            keep.append(i)
        return mm.loc[keep]

    first = assign(m, (m.dd - 2).abs())
    med = first.groupby(["is_g", "round"]).dd.median().to_dict()
    med_round = first.groupby("round").dd.median().to_dict()
    exp = [med.get((g, r), med_round.get(r, 2.0)) for g, r in zip(m.is_g, m["round"])]
    final = assign(m, (m.dd - np.array(exp)).abs())
    exact = pd.Series(pd.NaT, index=a.index, dtype="datetime64[ns]")
    exact.loc[final.arow.values] = final.start.values.astype("datetime64[ns]")
    comp = pd.Series(None, index=a.index, dtype=object)
    comp.loc[final.arow.values] = final.comp_id.values
    return exact, comp, med, med_round


def timeline(a: pd.DataFrame) -> pd.DataFrame:
    """One row per (archive match, role) with the features known before it."""
    x = a[~a.walkover]
    rows = []
    for role in ("winner", "loser"):
        rows.append(pd.DataFrame({
            "arow": x.index, "role": role, "tour": x.tour.values, "pid": x[f"{role}_id"].values,
            "tdate": x.tdate.values, "tid": x.tourney_id.values, "rord": x.rord.values,
            "match_num": pd.to_numeric(x.match_num, errors="coerce").fillna(0).values,
            "date": x.date.values, "exact": x.exact.notna().values, "minutes": x.minutes.values,
            "sets": x.sets.values, "best_of": x.best_of.values, "age": x[f"{role}_age"].values,
            "ret_loser": (x.ret_token & (role == "loser")).values}))
    t = pd.concat(rows, ignore_index=True)
    t = t.sort_values(["tour", "pid", "tdate", "tid", "rord", "match_num"]).reset_index(drop=True)
    g = t.groupby(["tour", "pid"], sort=False)
    same = (g.tid.shift(1) == t.tid)
    t["prev_exact"] = g.exact.shift(1).fillna(False).astype(bool) & t.exact
    t["prev_minutes"] = (g.minutes.shift(1) / 60).where(same)
    t["prev_sets"] = g.sets.shift(1).where(same)
    t["prev_distance"] = (g.sets.shift(1) == g.best_of.shift(1)).astype(float).where(same & g.sets.shift(1).notna())
    t["has_prev_same"] = same
    days = (t.date - g.date.shift(1)).dt.total_seconds() / 86400
    t["days_raw"] = days.clip(lower=0)
    t["days_since"] = np.log1p(t.days_raw.clip(upper=365))
    # windows by date: rows before this one by date within the player
    t["gid"] = g.ngroup()
    day = (t.date - pd.Timestamp("2000-01-01")).dt.total_seconds().values / 86400
    order = np.lexsort((t.rord.values, day, t.gid.values))
    key = t.gid.values[order] * 100000.0 + day[order]
    pos = np.arange(len(key))
    lo14 = np.searchsorted(key, key - 14.0, side="left")
    m14 = np.empty(len(key))
    m14[order] = pos - lo14
    t["matches14"] = m14
    # last retirement strictly before, by date order
    td = t.iloc[order][["gid", "date", "ret_loser"]].copy()
    td["rd"] = td.date.where(td.ret_loser)
    td["rd_prev"] = td.groupby("gid").rd.shift(1)
    td["last_ret"] = td.groupby("gid").rd_prev.ffill()
    t["last_ret"] = td.last_ret.reindex(t.index)
    t["ret30"] = ((t.date - t.last_ret).dt.total_seconds() / 86400 <= 30).astype(float)
    return t


# ── the priced matches ───────────────────────────────────────────────────────

def priced_events(cache: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    c = pd.read_parquet(cache / "shop_candidates.parquet")
    c = c[c.ref == "pinnacle"].copy()
    ia, ib = c.r_side.map(tc.implied).values, c.r_other.map(tc.implied).values
    c["p_pow"] = power_side(ia, ib)
    c["dec"] = c.price.map(tc.american_to_decimal)
    q = pd.read_parquet(cache / "tennis_odds_quotes.parquet",
                        columns=["event_id", "sport_key", "commence_time", "home_name", "away_name"])
    q["commence_time"] = pd.to_datetime(q.commence_time, utc=True)
    res = pd.read_parquet(cache / "tennis_espn_matches.parquet")
    res["start_time"] = pd.to_datetime(res.start_time, utc=True)
    res = res.rename(columns={"p1_tiebreaks": "p1_tb", "p2_tiebreaks": "p2_tb"})
    lk = st.link(q[q.event_id.isin(c.event_id.unique())], res)
    resi = res.set_index("comp_id")
    ev = c.drop_duplicates("event_id")[["event_id", "tour", "start", "season"]].merge(
        lk[["event_id", "home_name", "away_name", "comp_id", "home_is_p1"]], on="event_id", how="left")
    out = []
    for r in ev.itertuples(index=False):
        d = {"event_id": r.event_id, "y": np.nan, "both_false": False, "best_of": np.nan,
             "ret_side": None, "sets_complete": np.nan, "espn_status": None}
        if isinstance(r.comp_id, str) and r.comp_id in resi.index:
            row = resi.loc[r.comp_id]
            d["best_of"] = row.best_of
            d["espn_status"] = row.status
            if row.status in ("STATUS_FINAL", "STATUS_RETIRED") and not row.p1_winner and not row.p2_winner:
                d["both_false"] = True
            else:
                rs = st.espn_result(row, a_is_p1=bool(r.home_is_p1))
                if rs is not None and rs.status != "walkover":
                    d["y"] = float(rs.a_advanced)
                    d["ret_side"] = rs.retired_side
                    d["sets_complete"] = rs.sets_complete
        out.append(d)
    ev = ev.merge(pd.DataFrame(out), on="event_id")
    return c, ev, res


def link_feed_archive(ev: pd.DataFrame, a: pd.DataFrame) -> pd.DataFrame:
    """event_id -> archive row, whether the feed's home is the archive winner,
    and which pass linked it."""
    ak = a[~a.walkover].reset_index().rename(columns={"index": "arow"})
    by = {}
    for i, (tour, k) in enumerate(zip(ak.tour, ak.k)):
        by.setdefault((tour, k), []).append(i)
    tdate = ak.tdate.values.astype("datetime64[ns]")
    adate = ak.date.values.astype("datetime64[ns]")
    sort_t = {tour: ak.index[ak.tour == tour].values[np.argsort(tdate[ak.tour == tour], kind="stable")]
              for tour in ("ATP", "WTA")}
    kw_l, kl_l, arow_l = ak.kw.tolist(), ak.kl.tolist(), ak.arow.tolist()
    out = []
    for r in ev.itertuples(index=False):
        if not isinstance(r.home_name, str):
            out.append((r.event_id, np.nan, None, "no feed names"))
            continue
        T = np.datetime64(r.start.tz_convert("UTC").tz_localize(None), "ns")
        kh, ka = tc.name_key(r.home_name), tc.name_key(r.away_name)
        best, bc = None, None
        for i in by.get((r.tour, frozenset((kh, ka))), []):
            dd = (T - tdate[i]) / np.timedelta64(1, "D")
            if WINDOW[0] <= dd <= WINDOW[1]:
                cst = abs((T - adate[i]) / np.timedelta64(1, "D"))
                if bc is None or cst < bc:
                    best, bc = i, cst
        if best is not None:
            out.append((r.event_id, arow_l[best], kw_l[best] == kh, "exact"))
            continue
        idx = sort_t[r.tour]
        lo = np.searchsorted(tdate[idx], T - np.timedelta64(int(WINDOW[1] * 24), "h"), side="left")
        hi = np.searchsorted(tdate[idx], T - np.timedelta64(int(WINDOW[0] * 24), "h"), side="right")
        cands = []

        def rel(x, y):
            return bool(x) and bool(y) and (x <= y or y <= x)
        for i in idx[lo:hi]:
            kw, kl = kw_l[i], kl_l[i]
            if rel(kh, kw) and rel(ka, kl) and not rel(kh, kl):
                cands.append((i, True))
            elif rel(kh, kl) and rel(ka, kw) and not rel(kh, kw):
                cands.append((i, False))
        if len(cands) == 1:
            out.append((r.event_id, arow_l[cands[0][0]], cands[0][1], "subset"))
        else:
            out.append((r.event_id, np.nan, None, "unlinked" if not cands else "ambiguous"))
    return pd.DataFrame(out, columns=["event_id", "arow", "home_is_winner", "link"])


def build(cache: Path, spool: str) -> tuple:
    a = load_archive(spool)
    c, ev, res = priced_events(cache)
    exact, comp, med, med_round = link_archive_espn(a, res)
    a["exact"] = exact
    a["espn_comp"] = comp
    off = [med.get((g, r), med_round.get(r, 2.0)) for g, r in zip(a.is_g, a["round"])]
    a["date"] = a.exact.fillna(a.tdate + pd.to_timedelta(off, unit="D"))
    t = timeline(a)
    lk = link_feed_archive(ev, a)
    ev = ev.merge(lk, on="event_id", how="left")
    feat = ["prev_minutes", "prev_sets", "prev_distance", "days_since", "days_raw", "matches14",
            "ret30", "age", "has_prev_same", "exact", "prev_exact"]
    tw = t[t.role == "winner"].set_index("arow")[feat]
    tl = t[t.role == "loser"].set_index("arow")[feat]
    rows = []
    for r in ev.itertuples(index=False):
        if pd.isna(r.arow):
            rows.append({})
            continue
        w, l = tw.loc[int(r.arow)], tl.loc[int(r.arow)]
        A, B = (w, l) if r.home_is_winner else (l, w)
        d = {f"{f}_a": A[f] for f in feat}
        d.update({f"{f}_b": B[f] for f in feat})
        rows.append(d)
    ev = pd.concat([ev.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    ar = a.loc[ev.arow.dropna().astype(int)]
    ev.loc[ev.arow.notna(), "arch_surface"] = ar.surface.values
    ev.loc[ev.arow.notna(), "arch_level"] = ar.tourney_level.values
    ev.loc[ev.arow.notna(), "arch_best_of"] = ar.best_of.values
    return a, t, c, ev, med


# ── logistic ─────────────────────────────────────────────────────────────────

def logit_fit(X: np.ndarray, y: np.ndarray, iters: int = 50) -> tuple[np.ndarray, np.ndarray]:
    """Newton-Raphson logistic; returns coefficients and standard errors."""
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        z = np.clip(X @ b, -30, 30)
        p = 1 / (1 + np.exp(-z))
        w = p * (1 - p)
        H = X.T @ (X * w[:, None]) + 1e-9 * np.eye(X.shape[1])
        step = np.linalg.solve(H, X.T @ (y - p))
        b = b + step
        if np.abs(step).max() < 1e-10:
            break
    z = np.clip(X @ b, -30, 30)
    p = 1 / (1 + np.exp(-z))
    H = X.T @ (X * (p * (1 - p))[:, None])
    se = np.sqrt(np.diag(np.linalg.pinv(H)))
    return b, se


def sig(z):
    return 1 / (1 + np.exp(-np.clip(z, -30, 30)))


def ll(y, p):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def lgt(p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return np.log(p / (1 - p))


# ── test 2 ───────────────────────────────────────────────────────────────────

def decision_frame(c: pd.DataFrame, ev: pd.DataFrame, decision: str) -> pd.DataFrame:
    """Per event: side a's power-de-vigged Pinnacle price standing at the
    decision (the row with the latest ref_ts), with the outcome and features."""
    x = c[(c.decision == decision) & (c.side == "a")].sort_values("ref_ts").drop_duplicates("event_id", keep="last")
    x = x[["event_id", "p_pow"]].merge(ev, on="event_id")
    x = x[(x.start < END) & x.y.notna()].copy()
    x["L"] = lgt(x.p_pow.values)
    for f in FEATURES:
        x[f] = x[f"{f}_a"].astype(float) - x[f"{f}_b"].astype(float)
    x["men_bo5"] = (x.tour == "ATP") & (x.best_of == 5)
    return x


MODELS = {
    "F1 prev_minutes (h)": (["prev_minutes"], None),
    "F2 prev_sets": (["prev_sets"], None),
    "F3 prev_distance": (["prev_distance"], None),
    "F4 days_since (log)": (["days_since"], None),
    "F5 matches14": (["matches14"], None),
    "F6 ret30": (["ret30"], None),
    "F7 age (y)": (["age"], None),
    "F8 prev_minutes, men bo5": (["prev_minutes"], "men_bo5"),
    "J1 all seven": (FEATURES, None),
    "J2 days/m14/ret30/age": (["days_since", "matches14", "ret30", "age"], None),
}


def model_rows(x: pd.DataFrame, cols: list, subset) -> pd.DataFrame:
    m = x.dropna(subset=cols)
    if subset:
        m = m[m[subset]]
    return m


def info_test(x: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    out, passed = [], {}
    for name, (cols, subset) in MODELS.items():
        m = model_rows(x, cols, subset)
        y = m.y.values
        Xm = np.column_stack([np.ones(len(m)), m.L.values])
        Xf = np.column_stack([Xm, m[cols].values])
        bf, sef = logit_fit(Xf, y)
        rec = {"model": name, "n": len(m)}
        for j, col in enumerate(cols):
            rec[f"coef {col}"] = f"{bf[2 + j]:+.4f} ({sef[2 + j]:.4f})"
        rec["slope L"] = round(bf[1], 4)
        d_all, by_season, d_raw, d_fr = [], {}, [], []
        for S in OOS_SEASONS:
            tr, te = m[m.season < S], m[m.season == S]
            if len(te) == 0 or len(tr) < 50:
                continue
            bm, _ = logit_fit(np.column_stack([np.ones(len(tr)), tr.L.values]), tr.y.values)
            bff, _ = logit_fit(np.column_stack([np.ones(len(tr)), tr.L.values, tr[cols].values]), tr.y.values)
            pm = sig(bm[0] + bm[1] * te.L.values)
            pf = sig(np.column_stack([np.ones(len(te)), te.L.values, te[cols].values]) @ bff)
            dlt = ll(te.y.values, pf) - ll(te.y.values, pm)
            d_all.append(dlt)
            d_raw.append(ll(te.y.values, te.p_pow.values) - ll(te.y.values, pm))
            d_fr.append(ll(te.y.values, pf) - ll(te.y.values, te.p_pow.values))
            by_season[S] = (len(tr), len(te), dlt.mean())
        d = np.concatenate(d_all) if d_all else np.array([np.nan])
        rec["oos n"] = len(d)
        rec["d logloss pooled"] = f"{d.mean():+.5f}"
        rec["paired se"] = f"{d.std(ddof=1) / math.sqrt(len(d)):.5f}" if len(d) > 1 else "nan"
        rec["z"] = round(d.mean() / (d.std(ddof=1) / math.sqrt(len(d))), 2) if len(d) > 1 else math.nan
        rec["raw - market"] = f"{np.concatenate(d_raw).mean():+.5f}" if d_raw else "nan"
        fr_ = np.concatenate(d_fr) if d_fr else np.array([np.nan])
        rec["feature - raw"] = (f"{fr_.mean():+.5f} (se {fr_.std(ddof=1) / math.sqrt(len(fr_)):.5f})"
                                if len(fr_) > 1 else "nan")
        neg = sum(1 for v in by_season.values() if v[2] < 0)
        rec["seasons < 0"] = f"{neg}/{len(by_season)}"
        for S, (ntr, nte, v) in by_season.items():
            rec[str(S)] = f"{v:+.5f} [{ntr}/{nte}]"
        passed[name] = bool(d.mean() < 0 and neg >= 4)
        rec["IMPROVES"] = passed[name]
        out.append(rec)
    return pd.DataFrame(out), passed


# ── the books' retirement term ───────────────────────────────────────────────

def book_term(book: pd.Series, d: np.ndarray, r_own: np.ndarray, r_opp: np.ndarray) -> np.ndarray:
    rule = book.map(lambda b: tc.MONEYLINE_RULE.get(b, tc.DEFAULT_MONEYLINE_RULE)).values
    return np.where(rule == tc.RULE_RETIREE_VOID, r_own,
                    np.where(rule == tc.RULE_FULL_MATCH, r_own - r_opp * (d - 1), 0.0))


def flat_rate(c: pd.DataFrame) -> pd.Series:
    """The study's flat per-side rate per event, read back from the DraftKings
    rows' opt (0 where no DraftKings row): exactly the current best candidate."""
    return c.event_id.map(c.groupby("event_id").opt.max()).fillna(0.0)


# ── test 3 ───────────────────────────────────────────────────────────────────

def best_rows(ev_idx: np.ndarray, ev: np.ndarray) -> np.ndarray:
    o = np.lexsort((-ev, ev_idx))
    _, first = np.unique(ev_idx[o], return_index=True)
    return o[first]


def walk_coefs(fr: pd.DataFrame, cols: list, xvals: np.ndarray | None) -> dict:
    """Per held-out season S: (market-only coefs, feature coefs) fit on < S."""
    out = {}
    L, y, s = fr.L.values, fr.y.values, fr.season.values
    for S in OOS_SEASONS:
        tr = s < S
        if tr.sum() < 50:
            continue
        bm, _ = logit_fit(np.column_stack([np.ones(tr.sum()), L[tr]]), y[tr])
        bf = None
        if xvals is not None:
            bf, _ = logit_fit(np.column_stack([np.ones(tr.sum()), L[tr], xvals[tr]]), y[tr])
        out[S] = (bm, bf)
    return out


def bet_inputs(c: pd.DataFrame, fr: pd.DataFrame, decision: str) -> pd.DataFrame:
    b = c[(c.decision == decision) & c.event_id.isin(fr.event_id) & c.season.isin(OOS_SEASONS)].copy()
    b["Lside"] = lgt(b.p_pow.values)
    b["sgn"] = np.where(b.side == "a", 1.0, -1.0)
    r = flat_rate(c).loc[b.index].values
    b["term"] = book_term(b.book, b.dec.values, r, r)
    b["eidx"] = b.event_id.map({e: i for i, e in enumerate(fr.event_id)}).values
    return b


def model_p(b: pd.DataFrame, coefs: dict, which: int, xev: np.ndarray | None) -> np.ndarray:
    """Side a's model probability from the season's coefficients; side b = 1 - it."""
    p = np.full(len(b), np.nan)
    La = b.Lside.values * b.sgn.values
    for S, cf in coefs.items():
        m = (b.season.values == S)
        if not m.any():
            continue
        beta = cf[which]
        z = beta[0] + beta[1] * La[m]
        if which == 1:
            z = z + xev[b.eidx.values[m]] @ beta[2:]
        pa = sig(z)
        p[m] = np.where(b.sgn.values[m] > 0, pa, 1 - pa)
    return p


def pick(b: pd.DataFrame, p: np.ndarray, cut: float) -> pd.DataFrame:
    ok = ~np.isnan(p)
    bb = b[ok]
    ev = p[ok] * bb.dec.values - 1 + bb.term.values
    i = best_rows(bb.eidx.values, ev)
    sel = bb.iloc[i].assign(ev=ev[i], p_model=p[ok][i])
    return sel[sel.ev >= cut]


def fmt(t: dict) -> str:
    return (f"bets {t['bets']:5,} won {t['won']:5,} void {t['void']:3}  units {t['units']:+8.2f}  "
            f"roi {t['roi']:+.4f}  ci90 {t['ci90']}")


def kill(sel: pd.DataFrame) -> None:
    sel = sel.sort_values("start")
    sel = sel.assign(half=np.where(np.arange(len(sel)) < len(sel) / 2, "early", "late"),
                     fav=np.where(sel.price < 0, "favourite", "underdog"),
                     band=pd.cut(sel.price, [-100000, -300, -150, 100, 200, 100000],
                                 labels=["<-300", "-300..-150", "-150..+100", "+100..+200", ">+200"]))
    for col in ("season", "half", "fav", "band", "book", "tour"):
        parts = []
        for k, g in sel.groupby(col, observed=True):
            t = table(g)
            parts.append(f"{k}: {t['bets']} {t['units']:+.2f}u {t['roi']:+.3f}")
        print(f"      by {col}: " + " | ".join(parts))


def bet_rule(c: pd.DataFrame, ev: pd.DataFrame, name: str, cols: list, subset, n_placebo: int, seed: int) -> None:
    print(f"\n=== TEST 3, BET RULE: {name} ===")
    rng = np.random.default_rng(seed)
    for decision in DECISIONS:
        fr = model_rows(decision_frame(c, ev, decision), cols, subset).reset_index(drop=True)
        xev = fr[cols].values.astype(float)
        coefs = walk_coefs(fr, cols, xev)
        b = bet_inputs(c, fr, decision)
        p_feat = model_p(b, coefs, 1, xev)
        p_mkt = model_p(b, coefs, 0, None)
        print(f"\n  {decision}: events {len(fr):,} (bet seasons {sum(fr.season.isin(OOS_SEASONS)):,}), quotes {len(b):,}")
        for label, p in (("feature model", p_feat), ("market-only fit", p_mkt), ("raw power price", b.p_pow.values)):
            for cut in CUTS:
                print(f"    {label:16s} EV>={cut:.2f}  {fmt(table(pick(b, p, cut)))}")
        sel = pick(b, p_feat, 0.0)
        sel["eb"] = pd.cut(sel.ev, [0, .01, .02, .03, .05, .08, 10], right=False)
        print("    EV bands (feature model, best per event):")
        for k, g in sel.groupby("eb", observed=True):
            print(f"      {k!s:14s} {fmt(table(g))}")
        real = pick(b, p_feat, KILL_CUT)
        print(f"    kill tests, feature model, EV>={KILL_CUT:.2f}: {fmt(table(real))}")
        kill(real)
        if n_placebo:
            ru = table(real)["units"]
            pu = []
            for _ in range(n_placebo):
                xs = xev.copy()
                for S in np.unique(fr.season.values):
                    idx = np.where(fr.season.values == S)[0]
                    xs[idx] = xev[rng.permutation(idx)]
                cf = walk_coefs(fr, cols, xs)
                pu.append(table(pick(b, model_p(b, cf, 1, xs), KILL_CUT))["units"])
            pu = np.array(pu)
            print(f"    placebo ({n_placebo} shuffles within season), EV>={KILL_CUT:.2f}: real {ru:+.2f}u; "
                  f"placebo mean {pu.mean():+.2f}u, median {np.median(pu):+.2f}u, 95th pct {np.percentile(pu, 95):+.2f}u, "
                  f"share >= real {np.mean(pu >= ru):.3f}")


# ── test 4 ───────────────────────────────────────────────────────────────────

def ret_design(df: pd.DataFrame) -> np.ndarray:
    pm = df.prev_minutes.astype(float)
    surf = df.surface.fillna("Hard")
    return np.column_stack([
        np.ones(len(df)), pm.fillna(0).values, pm.isna().astype(float).values,
        df.ret30.astype(float).values, df.age.astype(float).values,
        (df.best_of == 5).astype(float).values,
        (surf == "Clay").astype(float).values, (surf == "Grass").astype(float).values,
        (surf == "Carpet").astype(float).values, (df.tour == "WTA").astype(float).values])


RET_COLS = ["const", "prev_minutes_h", "no_prev", "ret30", "age", "best_of_5", "clay", "grass", "carpet", "wta"]


def retirement_test(a: pd.DataFrame, t: pd.DataFrame, c: pd.DataFrame, ev: pd.DataFrame, rr: dict) -> None:
    print("\n=== TEST 4, RETIREMENT RISK AT DRAFTKINGS ===")
    tt = t.merge(a[["tourney_level", "surface", "ret_after1"]], left_on="arow", right_index=True)
    tt["season"] = tt.tid.str[:4].astype(int)
    lvl_ok = np.array([lv in TOUR_LEVELS[tr] for tr, lv in zip(tt.tour, tt.tourney_level)])
    fit = tt[lvl_ok & tt.season.between(2015, 2019) & tt.age.notna()]
    yfit = (fit.ret_after1 & (fit.role == "loser")).astype(float).values
    beta, se = logit_fit(ret_design(fit), yfit)
    print(f"  fit: 2015-2019 tour-level player-matches {len(fit):,}, retired after set one {int(yfit.sum()):,} "
          f"({yfit.mean():.4f} per side)")
    for n, b_, s_ in zip(RET_COLS, beta, se):
        print(f"    {n:15s} {b_:+.4f} ({s_:.4f})")
    # the priced matches, both sides
    rows = []
    for side in ("a", "b"):
        other = "b" if side == "a" else "a"
        x = ev[ev.arow.notna() & ev.y.notna() & (ev.start < END)].copy()
        df = pd.DataFrame({"event_id": x.event_id.values, "side": side, "tour": x.tour.values,
                           "best_of": x.best_of.values, "surface": x.arch_surface.values,
                           "prev_minutes": x[f"prev_minutes_{side}"].values,
                           "ret30": x[f"ret30_{side}"].values, "age": x[f"age_{side}"].values,
                           "season": x.season.values,
                           "retired": ((x.ret_side == side) & (x.sets_complete >= 1)).astype(float).values})
        df["flat"] = [rr.get((tr, int(bo) if pd.notna(bo) else 3), 0.0) for tr, bo in zip(df.tour, df.best_of)]
        rows.append(df)
    pr = pd.concat(rows, ignore_index=True)
    ok = pr.age.notna() & pr.ret30.notna()
    pr["model"] = pr.flat
    pr.loc[ok, "model"] = sig(ret_design(pr[ok]) @ beta)
    pr["modelled"] = ok
    print(f"  scored: 2020-2026 priced sides {len(pr):,} ({int(ok.sum()):,} with a modelled chance), "
          f"retired after a set {int(pr.retired.sum()):,} ({pr.retired.mean():.4f})")

    def score(df, label):
        yv = df.retired.values
        from sklearn.metrics import roc_auc_score
        for col in ("flat", "model"):
            pv = df[col].values
            auc = roc_auc_score(yv, pv) if 0 < yv.sum() < len(yv) else math.nan
            print(f"    {label:28s} {col:5s} n {len(df):6,} mean p {pv.mean():.4f} realised {yv.mean():.4f}  "
                  f"brier {((pv - yv) ** 2).mean():.6f}  logloss {ll(yv, pv).mean():.5f}  auc {auc:.4f}")
    m = pr[pr.modelled]
    score(m, "all priced sides (modelled)")
    dk_ev = set(c[(c.book == "draftkings") & (c.decision == "close")].event_id)
    score(m[m.event_id.isin(dk_ev)], "DraftKings-priced sides")
    score(m[(m.tour == "ATP") & (m.best_of == 5)], "men's best-of-five")
    m = m.assign(dec=pd.qcut(m.model, 10, duplicates="drop"))
    print("  calibration by decile of the modelled chance (all priced sides):")
    for k, g in m.groupby("dec", observed=True):
        print(f"    {k!s:22s} n {len(g):5,}  model {g.model.mean():.4f}  flat {g.flat.mean():.4f}  "
              f"realised {g.retired.mean():.4f}  ({int(g.retired.sum())})")

    # the current best candidate with the rate swapped
    cl = c[c.decision == "close"].copy()
    r = flat_rate(c).loc[cl.index].values
    cl["ev_flat"] = cl.p_pow.values * cl.dec.values - 1 + book_term(cl.book, cl.dec.values, r, r)
    mm = pr[pr.modelled].set_index(["event_id", "side"]).model
    own = pd.MultiIndex.from_arrays([cl.event_id, cl.side])
    opp = pd.MultiIndex.from_arrays([cl.event_id, np.where(cl.side == "a", "b", "a")])
    r_own = mm.reindex(own).values
    r_opp = mm.reindex(opp).values
    has = ~np.isnan(r_own) & ~np.isnan(r_opp)
    cl["has_model"] = has
    ro, rp = np.where(has, r_own, r), np.where(has, r_opp, r)
    cl["ev_mod"] = cl.p_pow.values * cl.dec.values - 1 + book_term(cl.book, cl.dec.values, ro, rp)

    def rule(df, col):
        x = df[(df.price >= -500) & (df[col] < 0.05)].assign(ev=df[col])
        return st_best(x, 0.02)
    print("  the current best candidate (close, 0.02 <= EV < 0.05, price >= -500, one bet per event):")
    full_flat = rule(cl, "ev_flat")
    print(f"    every event, flat rate (the reproduction)            {fmt(table(full_flat))}")
    print(f"    every event, modelled where linked, flat elsewhere   {fmt(table(rule(cl, 'ev_mod')))}")
    lk = cl[cl.event_id.isin(set(pr[pr.modelled].event_id)) & cl.has_model]
    for col, lab in (("ev_flat", "flat"), ("ev_mod", "modelled")):
        sel = rule(lk, col)
        print(f"    modelled events only (pre-June 2026), {lab:8s}       {fmt(table(sel))}")
        print(f"      by book: " + " | ".join(f"{k}: {table(g)['bets']} {table(g)['units']:+.2f}u"
                                            for k, g in sel.groupby("book")))
    a_f, a_m = rule(lk, "ev_flat"), rule(lk, "ev_mod")
    sf, sm = set(a_f.event_id + a_f.book + a_f.side), set(a_m.event_id + a_m.book + a_m.side)
    print(f"    same bet in both {len(sf & sm)}, flat only {len(sf - sm)}, modelled only {len(sm - sf)}")


def st_best(x: pd.DataFrame, cut: float) -> pd.DataFrame:
    x = x[x.ev >= cut].sort_values("ev", ascending=False)
    return x.drop_duplicates(["decision", "ref", "event_id"])


# ── test 5 ───────────────────────────────────────────────────────────────────

def descriptive(x: pd.DataFrame) -> None:
    print("\n=== TEST 5, REALISED MINUS MARKET BY prev_minutes DIFFERENCE (a - b), close, side a ===")
    m = x.dropna(subset=["prev_minutes"]).copy()
    m["dm"] = m.prev_minutes * 60
    m["bin"] = pd.cut(m.dm, [-1e9, -90, -45, -15, 15, 45, 90, 1e9], right=False,
                      labels=["<= -90", "-90..-45", "-45..-15", "-15..15", "15..45", "45..90", ">= 90"])
    for grp, g0 in (("men's best-of-five", m[m.men_bo5]), ("everything else", m[~m.men_bo5])):
        print(f"  {grp}: matches {len(g0):,}")
        for k, g in g0.groupby("bin", observed=True):
            se = math.sqrt((g.p_pow * (1 - g.p_pow)).sum()) / len(g)
            print(f"    {k!s:9s} n {len(g):5,}  market {g.p_pow.mean():.4f}  realised {g.y.mean():.4f}  "
                  f"gap {g.y.mean() - g.p_pow.mean():+.4f} (se {se:.4f})")


# ── main ─────────────────────────────────────────────────────────────────────

def population(c: pd.DataFrame, ev: pd.DataFrame, a: pd.DataFrame, med: dict) -> None:
    print("=== TEST 1, POPULATION ===")
    print(f"  archive rows {ARCHIVE_FIRST_YEAR}-2026 {len(a):,} (walkovers {int(a.walkover.sum()):,}), "
          f"last tourney_date {a.tdate.max().date()}; with an exact ESPN start {int(a.exact.notna().sum()):,}")
    print("  round offsets used for unlinked archive rows (median ESPN start - tourney_date, days):")
    print("    " + ", ".join(f"{'G' if g else 'other'} {r} {v:+.2f}" for (g, r), v in sorted(med.items(), key=lambda kv: (kv[0][0], ROUND_ORDER.get(kv[0][1], 12)))))
    close_ev = set(c[c.decision == "close"].event_id)
    e = ev[ev.event_id.isin(close_ev)]
    pre = e[e.start < END]
    print(f"  candidate events (Pinnacle reference) {ev.event_id.nunique():,}; with a close row {len(e):,}; "
          f"starting before 2026-06-01 {len(pre):,}")
    print(f"    ESPN both winner flags false {int(pre.both_false.sum())}, no outcome otherwise "
          f"{int((pre.y.isna() & ~pre.both_false).sum())}; with an outcome {int(pre.y.notna().sum()):,}")
    p = pre[pre.y.notna()]
    lc = p.link.value_counts()
    print(f"  feed names -> archive names (name_key): exact {lc.get('exact', 0):,}, subset pass {lc.get('subset', 0):,}, "
          f"ambiguous {lc.get('ambiguous', 0):,}, unlinked {lc.get('unlinked', 0):,}, no feed names {lc.get('no feed names', 0):,}; "
          f"rate {p.arow.notna().mean():.4f}")
    for tour, g in p.groupby("tour"):
        print(f"    {tour}: {g.arow.notna().mean():.4f} of {len(g):,}")
    for s, g in p.groupby("season"):
        print(f"    season {s}: {g.arow.notna().mean():.4f} of {len(g):,}")
    lkd = p[p.arow.notna()]
    arch_y = lkd.home_is_winner.astype(float)
    print(f"  archive winner agrees with ESPN's outcome: {(arch_y == lkd.y).sum():,} of {len(lkd):,}")
    print(f"  exact ESPN time for this match and the previous one (both players): "
          f"{(lkd.prev_exact_a.astype(bool) & lkd.prev_exact_b.astype(bool)).mean():.4f}")
    lkd = lkd.assign(grp=np.where((lkd.tour == "ATP") & (lkd.best_of == 5), "ATP bo5",
                                  np.where(lkd.tour == "ATP", "ATP bo3", "WTA bo3")))
    print("  feature present for both players (share of linked matches):")
    for grp, g in lkd.groupby("grp"):
        parts = [f"{f} {(g[f'{f}_a'].notna() & g[f'{f}_b'].notna()).mean():.3f}" for f in FEATURES]
        print(f"    {grp} ({len(g):,}): " + ", ".join(parts))
    g = lkd
    print(f"    all ({len(g):,}): " + ", ".join(
        f"{f} {int((g[f'{f}_a'].notna() & g[f'{f}_b'].notna()).sum()):,}" for f in FEATURES))
    print(f"    a same-event previous match for both: {int((g.has_prev_same_a.astype(bool) & g.has_prev_same_b.astype(bool)).sum()):,}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--spool", required=True)
    ap.add_argument("--features", type=Path, default=None,
                    help="write the per-event feature table here (a regenerable cache)")
    ap.add_argument("--placebo", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20261114)
    args = ap.parse_args(argv)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    a, t, c, ev, med = build(args.cache, args.spool)
    if args.features:
        out = ev.copy()
        for col in out.columns:
            if out[col].dtype == object and col not in ("event_id", "tour", "home_name", "away_name", "comp_id",
                                                        "espn_status", "ret_side", "link", "arch_surface",
                                                        "arch_level"):
                out[col] = out[col].astype(float)
        out.to_parquet(args.features, index=False)
        print(f"feature table written: {args.features} ({len(out):,} events)")
    population(c, ev, a, med)

    print("\n=== TEST 2, INFORMATION TEST (close, side a, one row per event) ===")
    x = decision_frame(c, ev, "close")
    x = x[x.arow.notna()]
    print(f"  events {len(x):,}; by season " + ", ".join(f"{s} {n}" for s, n in x.season.value_counts().sort_index().items()))
    yv = x.y.values
    print(f"  raw power price log-loss {ll(yv, x.p_pow.values).mean():.5f}, brier {((x.p_pow - yv) ** 2).mean():.5f}")
    res, passed = info_test(x)
    for rec in res.to_dict("records"):
        print("  " + "  ".join(f"{k}: {v}" for k, v in rec.items() if not (isinstance(v, float) and math.isnan(v))))

    any_pass = [k for k, v in passed.items() if v]
    print(f"\n  models that improve out-of-sample log-loss (pooled < 0 and < 0 in >= 4 of 5 seasons): {any_pass or 'none'}")
    for name in any_pass:
        cols, subset = MODELS[name]
        bet_rule(c, ev[ev.arow.notna()], name, cols, subset, args.placebo, args.seed)
    if not any_pass:
        print("  TEST 3 not run: no feature improves the out-of-sample log-loss.")

    retirement_test(a, t, c, ev, retire_rates(args.spool))
    descriptive(x)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
