"""Build the EuroLeague pre-game artifact and replay the research bet for bet.

For each of the five rules (models/euroleague_pregame.py) this:
  1. decides every game of the research's cache again through the CARD'S OWN
     decision code, at the research's decision time (tip minus 10 minutes:
     the last snapshot of the full-game purchase at or before it; the period
     purchase's call made at that mark), at the best deciding-book price and,
     for the three full-game rules, at DraftKings alone;
  2. runs the research's own code (scripts/euroleague_research r1_/r2_/r3_)
     on the same cache;
  3. compares the two bet for bet (game, side, number, price, book) and
     prints every difference, in either direction;
  4. writes the walk-forward uplift (THE PROBABILITY in the rules module), the
     price range, the volume and the replay's smallest EV and edge into
     models/saved/euroleague_pregame_<season>.json.

The research read the cache as it stood on 2026-11-13 (games through
2026-11-12, RESEARCH_LAST_DATE). The cache has gained games since; those are
replayed separately and reported, never mixed into the comparison.

Reads the local research cache only (EUROLEAGUE_RESEARCH_DIR, default
~/euroleague_research; scripts/euroleague_research/_paths.py): no database, no
network, no key.

    python -m scripts.euroleague_pregame_build              # replay and print
    python -m scripts.euroleague_pregame_build --write      # and write the artifact
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
RESEARCH = ROOT / "scripts" / "euroleague_research"

import models.euroleague_pregame as R  # noqa: E402

SEASON = 2027
RESEARCH_LAST_DATE = "2026-11-12"
CLOSE_LEAD_MIN = 10
PERIOD_MARK = "T-10"

PARAMS = {
    # r3_a_home.a1: home price -200 or longer, 2021-22 on, not neutral.
    R.HOME_ML: {"min_price": -200.0, "min_season": 2022},
    # r2_kill section 2 / r2_baselines' "<=-500" band.
    R.HEAVY_FAV_ML: {"max_price": -500.0},
    # r2_leads2 H3: the home number above 0.
    R.HOME_DOG_SPREAD: {"min_home_line": 0.0,
                        "relocated_venues": R.RELOCATED_VENUES},
    # r1_baselines: the blind first-half underdog.
    R.H1_DOG_ML: {},
    # r3_d_periods Q1-i at m 1.0 (the grid's top cell; the pre-registered 0.5
    # lost): K 40, earlier = tipped 3+ hours before.
    R.Q1_SHARE_TOTAL: {"margin": 1.0, "k_share": 40.0, "prior_gap_hours": 3.0},
}
FIRST_READ_SEASON = {R.HOME_ML: 2022, R.HEAVY_FAV_ML: 2022, R.HOME_DOG_SPREAD: 2022,
                     R.H1_DOG_ML: 2026, R.Q1_SHARE_TOTAL: 2026}


def cache_dir() -> Path:
    sys.path.insert(0, str(RESEARCH))
    from scripts.euroleague_research._paths import CACHE
    return CACHE


# ── the cache, as the card would read it ─────────────────────────────────────

def load(cache: Path) -> dict:
    g = pd.read_parquet(cache / "games.parquet")
    per = pd.read_parquet(cache / "periods.parquet")
    fq = pd.read_parquet(cache / "fullgame_quotes.parquet")
    pq = pd.read_parquet(cache / "period_quotes.parquet")
    led = pd.read_parquet(cache / "snapshots.parquet").snapshot_ts
    g["tip"] = pd.to_datetime(g.commence_time, utc=True)
    pv = per[per.period <= 2].pivot_table(index="game_id", columns="period",
                                           values=["home_points", "away_points"], aggfunc="sum")
    sc = pd.DataFrame({"q1h": pv[("home_points", 1)], "q1a": pv[("away_points", 1)],
                       "q2h": pv[("home_points", 2)], "q2a": pv[("away_points", 2)]}).reset_index()
    g = g.merge(sc, on="game_id", how="left")
    g["margin"] = g.home_score - g.away_score
    g["h1_margin"] = (g.q1h + g.q2h) - (g.q1a + g.q2a)
    g["q1_total"] = g.q1h + g.q1a
    return {"games": g, "periods": per, "fq": fq, "pq": pq,
            "ledger": np.sort(pd.to_datetime(led, utc=True).values.astype("datetime64[us]").astype(np.int64))}


def close_times(g: pd.DataFrame, ledger: np.ndarray) -> pd.Series:
    """The last purchase snapshot at or before tip minus 10 minutes
    (r2_lib.decision_times 'close'), per game id."""
    t = g.set_index("game_id").tip - pd.Timedelta(minutes=CLOSE_LEAD_MIN)
    us = t.dt.tz_convert("UTC").dt.tz_localize(None).values.astype("datetime64[us]").astype(np.int64)
    i = np.searchsorted(ledger, us, side="right") - 1
    ok = i >= 0
    when = pd.to_datetime(ledger[i[ok]].astype("datetime64[us]")).tz_localize("UTC")
    return pd.Series(when, index=t.index[ok])


def replay(data: dict, played: pd.DataFrame, books=R.DECIDABLE) -> dict[str, list]:
    """Every rule's decisions on `played` through the card's own code."""
    art = {"models": {m: {"params": PARAMS[m]} for m in R.MODELS}}
    tips = data["games"].set_index("game_id").tip
    fq = data["fq"][data["fq"].game_id.isin(played.game_id)]
    prepared = R.prepare_fullgame(fq, tips)
    close = close_times(played, data["ledger"])
    board = R.board_at(prepared, close)
    out = {R.HOME_ML: R.decide_home_ml(board, played, art, books),
           R.HEAVY_FAV_ML: R.decide_heavy_fav(board, played, art, books),
           R.HOME_DOG_SPREAD: R.decide_home_dog(board, played, art, books)}
    if tuple(books) == tuple(R.DECIDABLE):
        rows = data["pq"][(data["pq"].mark == PERIOD_MARK) & data["pq"].game_id.isin(played.game_id)]
        if rows.empty:
            out[R.H1_DOG_ML], out[R.Q1_SHARE_TOTAL] = [], []
            return out
        per = R.prepare_period(rows)
        out[R.H1_DOG_ML] = R.decide_h1_dog(per, played, art, books)
        asked = pd.to_datetime(per[~per.rung].groupby("game_id").asked_at.min(), utc=True)
        fgb = R.board_at(prepared, asked)
        hist = R.share_history(data["games"], data["periods"])
        out[R.Q1_SHARE_TOTAL] = R.decide_q1_share(per, rows, fgb, hist, played, art, books)
    return out


def graded(decisions: list, g: pd.DataFrame, model: str) -> pd.DataFrame:
    """The BETs as a frame, graded at the posted stake."""
    rows = [d.__dict__ | {"extra": None} for d in decisions if d.status == "bet"]
    x = pd.DataFrame(rows, columns=["game_id", "model_id", "status", "detail", "side", "book", "price",
                                    "line", "p_fair", "uplift", "p_model", "ev", "edge", "dk_price",
                                    "dk_line", "n_books", "extra"])
    x = x.merge(g[["game_id", "season", "game_date", "margin", "h1_margin", "q1_total"]], on="game_id")
    market = R.MARKET[model]
    sgn = np.where(x.side.isin(["home", "over"]), 1, -1)
    if market == "h2h":
        r = np.sign(x.margin)
    elif market == "spreads":
        r = np.sign(x.margin + x.line)
    elif market == "h2h_h1":
        r = np.sign(x.h1_margin)
    else:
        r = np.sign(x.q1_total - x.line)
    x["res"] = (sgn * r).astype(int)
    risk, win = R.stake(x.price.to_numpy())
    x["risk"] = np.where(x.res == 0, 0.0, risk)
    x["units"] = np.where(x.res > 0, win, np.where(x.res < 0, -risk, 0.0))
    return x


# ── the research's own code ──────────────────────────────────────────────────

def research_bets() -> dict:
    """{model: {"best": frame, "dk": frame}} from the research scripts, each
    frame game_id, side, line, price, book, units, game_date."""
    sys.path.insert(0, str(RESEARCH))
    with contextlib.redirect_stdout(io.StringIO()):
        import r1_lib as L1
        import r2_lib as L2
        import r3_lib as RR
        import r2_baselines as RB
        import r2_leads2 as LD2
        import r1_baselines as B1
        import r3_d_periods as D
    out: dict = {}

    def keep(x, line=None):
        y = x.copy()
        y["book"] = y["bookmaker"] if "bookmaker" in y else y.get("book")
        if line is not None:
            y["line"] = line
        return y[["game_id", "side", "line", "price", "book", "units", "game_date"]]

    g, q, dt, cb, fp = RR.fullgame()
    gg = g[~g.neutral_site & (g.season >= 2022)]
    b = cb[(cb.market == "h2h") & cb.game_id.isin(set(gg.game_id))]
    z = RR.ml_sides(b)
    home = z[(z.side == "home") & (z.price >= -200)]
    out[R.HOME_ML] = {"dk": keep(L2.grade(home[home.bookmaker == "draftkings"]), np.nan),
                      "best": keep(L2.grade(RR.best_price(home[home.bookmaker.isin(RR.DECIDABLE)])), np.nan)}
    zd = L2.grade(L2.sides_long(cb[(cb.market == "h2h") & (cb.bookmaker == "draftkings")]))
    zb = L2.grade(RB.best_decidable(RB.close, "h2h"))
    out[R.HEAVY_FAV_ML] = {"dk": keep(zd[zd.price <= -500], np.nan), "best": keep(zb[zb.price <= -500], np.nan)}
    out[R.HOME_DOG_SPREAD] = {}
    for key, name in (("DraftKings close", "dk"), ("best decidable close", "best")):
        v = LD2.SETS[key]
        out[R.HOME_DOG_SPREAD][name] = keep(L2.grade(v[(v.side == "home") & (v.line > 0)]))
    xm = B1.Q[B1.Q.market == "h2h_h1"]
    bd = pd.concat([B1.best_decidable(xm[xm.season == s], "h2h_h1", "T-10")
                    for s in sorted(xm[xm.decidable].season.unique())])
    a = B1.assign(bd, "h2h_h1", "dog", fav_home=bd.fav_home.astype(bool))
    a["book"] = np.where(a.side == "home", a.book_a, a.book_b)
    out[R.H1_DOG_ML] = {"best": keep(L1.grade_rows(a, "h2h_h1").assign(bookmaker=a.book.values), np.nan)}
    qq = RR.period_main()
    g1 = RR.period_games()
    A = D.anchors(qq, "T-10")
    S = D.club_shares(g1, "q1")
    qt = qq[(qq.market == "totals_q1") & (qq.mark == "T-10")]
    dec_q = qt[qt.season.isin([2026, 2027]) & qt.bookmaker.isin(D.DEC_PERIOD)]
    mb = RR.modal_best(dec_q, "over", "under")
    zz = D.share_bets(mb, A, S, g1, "q1", PARAMS[R.Q1_SHARE_TOTAL]["margin"])
    out[R.Q1_SHARE_TOTAL] = {"best": keep(zz)}
    return out


def compare(mine: pd.DataFrame, ref: pd.DataFrame) -> dict:
    """Bet-for-bet: the same games, and on each the same side, number and
    price; a different book at the same price is a tie, counted apart."""
    def key(x):
        return x.assign(line=x.line.astype(float).round(3).fillna(-9999.0),
                        price=x.price.astype(float).round(3))
    a, b = key(mine), key(ref)
    m = a.merge(b, on="game_id", how="outer", suffixes=("_card", "_research"), indicator=True)
    only_card = m[m._merge == "left_only"]
    only_res = m[m._merge == "right_only"]
    both = m[m._merge == "both"]
    diff = both[(both.side_card != both.side_research) | (both.line_card != both.line_research)
                | (both.price_card != both.price_research)]
    book_ties = both[(both.book_card != both.book_research) & both.index.isin(both.index.difference(diff.index))]
    return {"card": len(a), "research": len(b), "only_card": only_card.game_id.tolist(),
            "only_research": only_res.game_id.tolist(), "different": diff.game_id.tolist(),
            "book_ties": book_ties.game_id.tolist(),
            "units_card": round(float(mine.units.sum()), 2), "units_research": round(float(ref.units.sum()), 2)}


# ── summaries ────────────────────────────────────────────────────────────────

def summary(x: pd.DataFrame) -> dict:
    sys.path.insert(0, str(RESEARCH))
    import r1_lib as L1
    s = L1.summary(x) if len(x) else L1.summary(x.iloc[0:0])
    return {k: s[k] for k in ("bets", "W", "L", "P", "units", "risked", "ret%", "lo%", "hi%")}


def price_range(x: pd.DataFrame) -> dict:
    if not len(x):
        return {}
    p = x.price.to_numpy(float)
    return {"median": float(np.median(p)), "shortest": float(p.min()), "longest": float(p.max()),
            "share_shorter_than_-300": round(float(np.mean(p < -300)), 4),
            "share_shorter_than_-500": round(float(np.mean(p < -500)), 4),
            "risked": round(float(x.risk.sum()), 2)}


def md(rows: list[dict]) -> str:
    if not rows:
        return "(none)"
    cols = list(rows[0])
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if r.get(c) is None else str(r.get(c)) for c in cols) + " |")
    return "\n".join(out)


def build(write: bool = False) -> dict:
    data = load(cache_dir())
    g = data["games"]
    played = g[g.played & g.margin.notna()].copy()
    research_games = played[played.game_date <= RESEARCH_LAST_DATE]
    later_games = played[played.game_date > RESEARCH_LAST_DATE]
    report: list[str] = [f"# EuroLeague pre-game build, season {SEASON} (research state: games through "
                         f"{RESEARCH_LAST_DATE})\n"]
    best = replay(data, research_games)
    dk = replay(data, research_games, books=("draftkings",))
    ref = research_bets()
    art = {"season": SEASON, "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "research_last_date": RESEARCH_LAST_DATE, "decision_lead_min": CLOSE_LEAD_MIN,
           "deciding_books": list(R.DECIDABLE), "models": {}}
    all_ok = True
    rows = []
    graded_best: dict[str, pd.DataFrame] = {}
    for m in R.MODELS:
        gb = graded(best[m], played, m)
        graded_best[m] = gb
        c = compare(gb, ref[m]["best"][ref[m]["best"].game_date <= RESEARCH_LAST_DATE])
        ok = not (c["only_card"] or c["only_research"] or c["different"])
        all_ok &= ok
        line = {"model": m, "read": "best deciding book", **{k: c[k] for k in ("card", "research")},
                "units card": c["units_card"], "units research": c["units_research"],
                "only card": len(c["only_card"]), "only research": len(c["only_research"]),
                "different": len(c["different"]), "same price, other book": len(c["book_ties"])}
        rows.append(line)
        if not ok:
            report.append(f"DIFFERENCE {m} (best): {json.dumps({k: c[k][:20] for k in ('only_card', 'only_research', 'different')})}")
        if m in dk:
            gd = graded(dk[m], played, m)
            cd = compare(gd, ref[m]["dk"][ref[m]["dk"].game_date <= RESEARCH_LAST_DATE])
            okd = not (cd["only_card"] or cd["only_research"] or cd["different"])
            all_ok &= okd
            rows.append({"model": m, "read": "DraftKings alone", "card": cd["card"], "research": cd["research"],
                         "units card": cd["units_card"], "units research": cd["units_research"],
                         "only card": len(cd["only_card"]), "only research": len(cd["only_research"]),
                         "different": len(cd["different"]), "same price, other book": len(cd["book_ties"])})
            if not okd:
                report.append(f"DIFFERENCE {m} (DraftKings): {json.dumps({k: cd[k][:20] for k in ('only_card', 'only_research', 'different')})}")
    report.append("## The replay against the research's own code\n")
    report.append(md(rows))
    print("\n".join(report), flush=True)
    report = []

    # one game never carries two bets that cannot both win
    every = [d for m in R.MODELS for d in best[m]]
    before = {id(d): d.status for d in every}
    R.resolve_conflicts(every, standing=[])
    flipped = [d for d in every if before[id(d)] == "bet" and d.status != "bet"]
    report.append(f"\n## Conflicts in one pass: {len(flipped)} bet(s) written NONE instead\n")
    crow = []
    for m in R.MODELS:
        lost = [d.game_id for d in flipped if d.model_id == m]
        gb = graded_best[m]
        kept = gb[~gb.game_id.isin(lost)]
        crow.append({"model": m, "lost to a conflict": len(lost),
                     "units of those": round(float(gb[gb.game_id.isin(lost)].units.sum()), 2),
                     **{f"after: {k}": v for k, v in summary(kept).items() if k in ("bets", "units", "ret%")}})
    report.append(md(crow))

    # the probability: the walk-forward uplift, then EV and edge on every replayed bet
    srow = []
    later_dec = replay(data, later_games) if len(later_games) else {}
    for m in R.MODELS:
        gb = graded_best[m]
        lost = {d.game_id for d in flipped if d.model_id == m}
        live = gb[~gb.game_id.isin(lost)].copy()
        by_season = {}
        for s in sorted(set(live.season) | {SEASON}):
            u, n = R.uplift_from(live, int(s))
            if u is not None:
                by_season[str(int(s))] = {"uplift": round(u, 6), "bets": n}
        up, n_up = R.uplift_from(live, SEASON)
        if up is None:
            raise SystemExit(f"{m}: no graded bet before {SEASON} to take an uplift from")
        pm = np.clip(live.p_fair + up, 0.01, 0.99)
        live["ev"] = pm * R.dec(live.price) - 1
        live["edge"] = pm - R.imp(live.price)
        s_all = summary(live)
        seasons = {str(int(s)): summary(x) for s, x in live.groupby("season")}
        full = [x for s, x in live.groupby("season") if int(s) < SEASON and int(s) >= FIRST_READ_SEASON[m]]
        per_season = float(np.mean([len(x) for x in full])) if full else None
        per_week = ([len(x) / ((pd.to_datetime(x.game_date).max() - pd.to_datetime(x.game_date).min()).days / 7 + 1)
                     for x in full])
        later = graded(later_dec.get(m, []), played, m) if len(later_games) else live.iloc[0:0]
        art["models"][m] = {
            "params": PARAMS[m], "market": R.MARKET[m],
            "uplift": round(up, 6), "uplift_bets": n_up, "uplift_by_season": by_season,
            "ev_min": round(float(live.ev.min()), 6), "edge_min": round(float(live.edge.min()), 6),
            "ev_median": round(float(live.ev.median()), 6),
            "replay": {"all": s_all, "by_season": seasons,
                       "lost_to_conflicts": sorted(lost)},
            "price_range": price_range(live),
            "volume": {"per_full_season": per_season,
                       "per_week": round(float(np.mean(per_week)), 2) if per_week else None},
            "after_research_state": {"games": int(len(later_games)), **summary(later)} if len(later) else
                                    {"games": int(len(later_games)), "bets": 0},
        }
        srow.append({"model": m, **{k: s_all[k] for k in ("bets", "W", "L", "P", "units", "ret%", "lo%", "hi%")},
                     "uplift": round(up, 4), "EV min": round(float(live.ev.min()), 4),
                     "edge min": round(float(live.edge.min()), 4),
                     "price median": price_range(live).get("median"),
                     "shortest": price_range(live).get("shortest"), "longest": price_range(live).get("longest"),
                     "per season": per_season})
    report.append("\n## The live rules (best deciding book, after the conflict rule), and the probability\n")
    report.append(md(srow))
    report.append(f"\nGames after the research's state ({len(later_games)}): " + ", ".join(
        f"{m}: {art['models'][m]['after_research_state'].get('bets', 0)} bet(s)" for m in R.MODELS))
    art["replay_matches_research"] = bool(all_ok)
    text = "\n".join(report)
    print(text)
    if write:
        if not all_ok:
            raise SystemExit("the replay differs from the research: nothing written")
        path = R.artifact_path(SEASON)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(art, fh, indent=1, sort_keys=True)
            fh.write("\n")
        print(f"\nwrote {path}")
    return art


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help="write the artifact (only when the replay matches)")
    a = ap.parse_args(argv)
    build(write=a.write)


if __name__ == "__main__":
    main()
