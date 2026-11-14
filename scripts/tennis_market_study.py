"""Tennis market study: every bought quote, linked to its result, graded at
each book's own settlement rule.

READS Supabase only (tennis_odds_quotes, tennis_espn_matches), once per run,
by sport key; caches nothing outside data/local_store. WRITES nothing.

THE DECISION TIMES are fixed here, before any result is read:
  first   each book's first quote on the match (its first post)
  t12     the latest quote at least 12 hours before the listed start
  close   the latest quote before the listed start
A quote counts only if both its snapshot and its last update are at least 10
minutes before the EARLIER of ESPN's start and the feed's last listed start
(pre_match). The feed's listed start is not the start: on the 2025-08-30
trial it was 10 to 60 minutes early for the day's later matches, a placeholder
up to 29 hours early for the next round's, revised on 13 of 16 matches, and
once 10 minutes after ESPN's start (Sinner v Shapovalov); when a match goes
live the feed stamps it to the second (15:03:57 against ESPN's 15:10). Bounding
on the listed start alone lets in-play prices in as the close.

THE REFERENCE is Pinnacle's own two prices at the same snapshot, de-vigged
multiplicatively; the Betfair exchange's back prices de-vigged the same way are
the second reference where Pinnacle is missing. Never a price from another
moment.

    python -m scripts.tennis_market_study --report baseline
    python -m scripts.tennis_market_study --report shop --min-ev 0.02
"""
from __future__ import annotations

import argparse
import math
from datetime import timedelta

import numpy as np
import pandas as pd

from models import tennis_common as tc

DECIDABLE = ("draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics",
             "betrivers", "hardrockbet")
REFERENCES = ("pinnacle", "betfair_ex_eu")
DECISIONS = ("first", "t12", "close")


# ── load ─────────────────────────────────────────────────────────────────────

def load_quotes(conn, keys: list[str] | None = None) -> pd.DataFrame:
    where, params = "", ()
    if keys:
        where, params = "WHERE sport_key = ANY(%s)", (list(keys),)
    rows = conn.execute(f"SELECT * FROM tennis_odds_quotes {where}", params).fetchall()
    cols = [c[0] for c in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = "
        "'tennis_odds_quotes' ORDER BY ordinal_position").fetchall()]
    q = pd.DataFrame(rows, columns=cols)
    for c in ("commence_time", "last_update", "snapshot_ts"):
        q[c] = pd.to_datetime(q[c], utc=True)
    return q


def load_results(conn) -> pd.DataFrame:
    rows = conn.execute(
        "SELECT comp_id, tour, season, event_name, is_major, round_name, start_time, status, "
        "best_of, p1_id, p1_name, p1_winner, p1_games, p1_tiebreaks, p2_id, p2_name, "
        "p2_winner, p2_games, p2_tiebreaks FROM tennis_espn_matches").fetchall()
    cols = ["comp_id", "tour", "season", "event_name", "is_major", "round_name", "start_time",
            "status", "best_of", "p1_id", "p1_name", "p1_winner", "p1_games", "p1_tb",
            "p2_id", "p2_name", "p2_winner", "p2_games", "p2_tb"]
    r = pd.DataFrame(rows, columns=cols)
    r["start_time"] = pd.to_datetime(r["start_time"], utc=True)
    return r


def espn_result(row, a_is_p1: bool) -> tc.Result | None:
    """An ESPN row as a Result from player A's side."""
    status = row.status
    g1, g2 = list(row.p1_games or []), list(row.p2_games or [])
    if status == "STATUS_WALKOVER":
        return tc.Result([], [], bool(row.p1_winner) == a_is_p1, "walkover", best_of=row.best_of)
    if status not in ("STATUS_FINAL", "STATUS_RETIRED") or not g1 or len(g1) != len(g2):
        return None
    done = sum(1 for a, b in zip(g1, g2) if a is not None and b is not None and tc._set_done(a, b))
    if status == "STATUS_RETIRED":
        retired = "p2" if row.p1_winner else "p1"
    else:
        retired = None
    a_g, b_g = (g1, g2) if a_is_p1 else (g2, g1)
    a_adv = bool(row.p1_winner) if a_is_p1 else bool(row.p2_winner)
    ret_side = None
    if retired:
        ret_side = "a" if (retired == "p1") == a_is_p1 else "b"
    return tc.Result([int(x or 0) for x in a_g], [int(x or 0) for x in b_g], a_adv,
                     "retired" if retired else "complete", retired_side=ret_side,
                     sets_complete=done, best_of=int(row.best_of or 3))


def link(quotes: pd.DataFrame, results: pd.DataFrame,
         window: timedelta = timedelta(hours=60)) -> pd.DataFrame:
    """One row per feed event: the ESPN match with the same two players (names
    as token sets) whose start is nearest the feed's, within `window`; and
    whether the feed's home player is ESPN's first. Unmatched events are kept
    with comp_id None, so the match rate is reported, not hidden."""
    ev = quotes.drop_duplicates("event_id")[["event_id", "sport_key", "commence_time",
                                             "home_name", "away_name"]].copy()
    results = results.copy()
    results["k1"] = results.p1_name.map(tc.name_key)
    results["k2"] = results.p2_name.map(tc.name_key)
    by_pair: dict = {}
    for i, r in enumerate(results.itertuples(index=False)):
        by_pair.setdefault(frozenset((r.k1, r.k2)), []).append(i)
    out = []
    for e in ev.itertuples(index=False):
        kh, ka = tc.name_key(e.home_name), tc.name_key(e.away_name)
        best, best_dt = None, None
        for i in by_pair.get(frozenset((kh, ka)), []):
            dt = abs(results.start_time.iloc[i] - e.commence_time)
            if dt <= window and (best_dt is None or dt < best_dt):
                best, best_dt = i, dt
        if best is None:
            out.append((e.event_id, None, None, None))
            continue
        r = results.iloc[best]
        out.append((e.event_id, r.comp_id, r.k1 == kh, best_dt.total_seconds() / 3600))
    return ev.merge(pd.DataFrame(out, columns=["event_id", "comp_id", "home_is_p1", "dt_hours"]),
                    on="event_id")


PRE_MATCH_MARGIN = pd.Timedelta(minutes=10)


def pre_match(q: pd.DataFrame, linked: pd.DataFrame, results: pd.DataFrame) -> pd.DataFrame:
    """The quotes of linked events that stood before the match: snapshot and
    last update both at least PRE_MATCH_MARGIN before the earlier of ESPN's
    start and the feed's last listed start. Unlinked events drop out."""
    last_listed = q.groupby("event_id").commence_time.max().rename("listed_last")
    starts = linked.dropna(subset=["comp_id"]).merge(
        results[["comp_id", "start_time"]], on="comp_id")[["event_id", "start_time"]]
    b = starts.merge(last_listed, left_on="event_id", right_index=True)
    b["bound"] = b[["start_time", "listed_last"]].min(axis=1) - PRE_MATCH_MARGIN
    x = q.merge(b[["event_id", "bound"]], on="event_id")
    ok = (x.snapshot_ts <= x.bound) & (x.last_update.isna() | (x.last_update <= x.bound))
    return x[ok].drop(columns="bound")


# ── prices at a decision time ────────────────────────────────────────────────

def decision_quotes(q: pd.DataFrame, decision: str) -> pd.DataFrame:
    """One quote per (event, book, market) at the decision time."""
    q = q.sort_values("snapshot_ts")
    if decision == "first":
        return q.groupby(["event_id", "bookmaker", "market"], as_index=False).head(1)
    if decision == "close":
        return q.groupby(["event_id", "bookmaker", "market"], as_index=False).tail(1)
    if decision == "t12":
        # 12 hours before the feed's last listed start: books first post a
        # median 17 to 19 hours before it (the 2025-08-30 trial, 16 matches).
        listed = q.groupby("event_id").commence_time.transform("max")
        cut = q[q.snapshot_ts <= listed - pd.Timedelta(hours=12)]
        return cut.groupby(["event_id", "bookmaker", "market"], as_index=False).tail(1)
    raise ValueError(decision)


def reference_at(q: pd.DataFrame, event_id: str, market: str, ts, book: str) -> pd.Series | None:
    """The reference book's quote on the same event and market at the snapshot
    `ts` itself (the change-only store keeps a quote until it changes, so the
    latest row at or before ts is the quote standing at ts)."""
    s = q[(q.event_id == event_id) & (q.bookmaker == book) & (q.market == market) & (q.snapshot_ts <= ts)]
    if s.empty:
        return None
    return s.iloc[-1]


def wilson_return_interval(units: np.ndarray, risked: np.ndarray, z: float = 1.645) -> tuple:
    """A normal-approximation 90% interval on return per unit risked."""
    if len(units) < 2 or risked.sum() == 0:
        return (math.nan, math.nan)
    r = units / np.where(risked == 0, 1, risked)
    m = units.sum() / risked.sum()
    se = r.std(ddof=1) / math.sqrt(len(r))
    return (m - z * se, m + z * se)


# ── the match-winner table: a decidable book against the sharp no-vig price ──

def moneyline_candidates(q: pd.DataFrame, linked: pd.DataFrame, results: pd.DataFrame,
                         decision: str, ref: str = "pinnacle") -> pd.DataFrame:
    """Every (event, decidable book, side) at the decision time, with the
    reference's no-vig probability at the same snapshot, the EV at the book's
    price, the retirement-adjusted EV for DraftKings, and the grade at the
    book's own rule. One row per side, so the table is the whole universe
    (every quote both ways), not only the bets."""
    pm = pre_match(q, linked, results)
    h2h = pm[pm.market == "h2h"]
    dq = decision_quotes(h2h, decision)
    dq = dq[dq.bookmaker.isin(DECIDABLE)]
    refq = h2h[h2h.bookmaker == ref].sort_values("snapshot_ts")
    res_by = results.set_index("comp_id")
    lk = linked.set_index("event_id")
    out = []
    for r in dq.itertuples(index=False):
        rq = refq[(refq.event_id == r.event_id) & (refq.snapshot_ts <= r.snapshot_ts)]
        if rq.empty or pd.isna(r.home_price) or pd.isna(r.away_price):
            continue
        ref_row = rq.iloc[-1]
        if pd.isna(ref_row.home_price) or pd.isna(ref_row.away_price):
            continue
        p_home, p_away = tc.no_vig_pair(ref_row.home_price, ref_row.away_price)
        link_row = lk.loc[r.event_id]
        espn = res_by.loc[link_row.comp_id]
        res = espn_result(espn, a_is_p1=bool(link_row.home_is_p1))
        if res is None:
            continue
        for side, price, p in (("a", r.home_price, p_home), ("b", r.away_price, p_away)):
            d = tc.american_to_decimal(price)
            grade = tc.grade_moneyline(res, side, r.bookmaker)
            out.append({"event_id": r.event_id, "book": r.bookmaker, "side": side,
                        "price": int(price), "ref_p": p, "ev": p * d - 1,
                        "snapshot_ts": r.snapshot_ts, "ref_age_min":
                        (r.snapshot_ts - ref_row.snapshot_ts).total_seconds() / 60,
                        "grade": grade, "units": tc.units(grade, price),
                        "risk": min(1 / (d - 1), 3.0)})
    return pd.DataFrame(out)
