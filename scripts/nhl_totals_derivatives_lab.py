"""NHL team totals, alternate totals and first-period totals: is the margin one-sided, and can it be beaten?

The full-game total has nothing in it (scripts/nhl_totals_lab.py: the book's
margin sits on both sides). The prop models work because the margin sits on
ONE side and a model says which bets on the cheap side. This asks the same
two questions of the three total-goals markets bought on 2026-10-01
(data/ingestors/nhl_totals_odds_history.py; one pre-game snapshot a game,
every book at the same instant, 2023-24 to 2025-26):

  BLIND          every over and every under, per market, by number and by
                 price band, at DraftKings and at the best bettable price.
                 Where does the margin sit?
  SHARP-VS-SOFT  Pinnacle quotes all three. Bet a bettable book when
                 Pinnacle's no-vig probability at the SAME number in the SAME
                 snapshot makes its price positive.
  MODEL          no hockey inputs: the MAIN total and moneyline already say
                 how many goals the market expects and from whom. A logistic
                 fit on earlier seasons maps (main number, no-vig over, no-vig
                 home win) to the chance of each derivative outcome; each
                 priced season is scored by a fit on seasons before it. Bet
                 when that probability makes a bettable price positive.

Graded in units on final scores (`games`; a team total and the game total
include overtime, a shootout counting one goal) and on first-period goals
(`nhl_period_scores`). One bet per game per market per side-of-the-question:
the best expected value on offer.

    python -m scripts.nhl_totals_derivatives_lab
    python -m scripts.nhl_totals_derivatives_lab --cache DIR      # games.pkl, odds.pkl; writes/reads deriv.pkl, periods.pkl
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

import config  # noqa: E402
from data.ingestors.nhl_totals_odds_history import SOURCE  # noqa: E402

pd.set_option("display.width", 280)
pd.set_option("display.max_rows", 400)
SEASONS = [2024, 2025, 2026]
BETTABLE = list(config.BEST_LINE_BOOKMAKERS)
SHARP = "pinnacle"
EV_CUTS = (0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.15)
FLOOR = -200
MARKETS = ("team_totals", "alternate_totals", "totals_p1")


def imp(a):
    a = np.asarray(a, float)
    return np.where(a > 0, 100 / (a + 100), -a / (-a + 100))


def wpu(a):
    a = np.asarray(a, float)
    return np.where(a > 0, a / 100, 100 / -a)


# ── data ─────────────────────────────────────────────────────────────────────

def _db_read(sql: str, ids: list[str], cols: list[str], extra: tuple = (), size: int = 150) -> pd.DataFrame:
    from data.db import get_connection
    conn = get_connection()
    try:
        rows = []
        for i in range(0, len(ids), size):                   # by game id: `odds` is 10 GB
            rows += conn.execute(sql, (ids[i:i + size], *extra)).fetchall()
        return pd.DataFrame(rows, columns=cols)
    finally:
        conn.close()


def load(cache: str | None) -> dict:
    """Games, the bought derivative quotes, the main lines, and goals by period."""
    c = Path(cache) if cache else None
    if c and (c / "games.pkl").exists():
        games = pd.read_pickle(c / "games.pkl")
    else:
        from data.db import get_connection
        conn = get_connection()
        try:
            games = pd.DataFrame(conn.execute(
                "SELECT game_id, season, game_date, commence_time, home_team, away_team, home_score, away_score "
                "FROM games WHERE sport = 'NHL'").fetchall(),
                columns=["game_id", "season", "game_date", "commence_time", "home_team", "away_team",
                         "home_score", "away_score"])
        finally:
            conn.close()
    ids_all = sorted(games[games.season.between(2019, 2026)].game_id)
    ids = sorted(games[games.season.isin(SEASONS)].game_id)

    def cached(name: str, build):
        if c and (c / name).exists():
            return pd.read_pickle(c / name)
        df = build()
        if c:
            df.to_pickle(c / name)
        return df

    deriv = cached("deriv.pkl", lambda: _db_read(
        "SELECT game_id, market, bookmaker, snapshot_at, total_line, over_price, under_price FROM odds "
        "WHERE game_id = ANY(%s) AND source = %s", ids,
        ["game_id", "market", "book", "snap", "line", "over", "under"], (SOURCE,)))
    if c and (c / "odds.pkl").exists():
        od = pd.read_pickle(c / "odds.pkl")
        main = od[(od.source == "odds_api_historical") & (od.snapshot_type == "open")][
            ["game_id", "market", "book", "snap", "hp", "ap", "total_line", "over", "under"]]
    else:
        main = _db_read(
            "SELECT game_id, market, bookmaker, snapshot_at, home_price, away_price, total_line, over_price, "
            "under_price FROM odds WHERE game_id = ANY(%s) AND source = %s AND snapshot_type = 'open' "
            "AND market IN ('totals', 'h2h')", ids_all,
            ["game_id", "market", "book", "snap", "hp", "ap", "total_line", "over", "under"],
            ("odds_api_historical",))

    def periods():
        from data.db import get_connection
        conn = get_connection()
        try:
            return pd.DataFrame(conn.execute(
                "SELECT DISTINCT ON (game_id) game_id, home_p1, away_p1 FROM nhl_period_scores "
                "ORDER BY game_id, source").fetchall(), columns=["game_id", "home_p1", "away_p1"])
        finally:
            conn.close()
    return {"games": games, "deriv": deriv, "main": main, "periods": cached("periods.pkl", periods)}


def results(data: dict) -> pd.DataFrame:
    g = data["games"]
    g = g[g.home_score.notna() & g.away_score.notna()].copy()
    g["home_goals"], g["away_goals"] = pd.to_numeric(g.home_score), pd.to_numeric(g.away_score)
    g["total"] = g.home_goals + g.away_goals
    g = g.merge(data["periods"], on="game_id", how="left")
    g["p1"] = pd.to_numeric(g.home_p1, errors="coerce") + pd.to_numeric(g.away_p1, errors="coerce")
    g["start"] = pd.to_datetime(g.commence_time, utc=True)
    return g[["game_id", "season", "game_date", "start", "home_goals", "away_goals", "total", "p1"]]


def main_lines(data: dict, res: pd.DataFrame, at: pd.DataFrame | None = None) -> pd.DataFrame:
    """The market's own view of each game: main total, no-vig over, no-vig home win.

    Pinnacle when it has one, else DraftKings. `at` (game_id, as_of) bounds the
    quote to the newest one at or before that instant -- the derivative
    snapshot -- so nothing later than the price being bet is used. Without it
    (the training seasons) the last pre-game quote is taken.
    """
    m = data["main"].copy()
    m["snap_t"] = pd.to_datetime(m.snap, utc=True)
    m = m.merge(res[["game_id", "start"]], on="game_id")
    m = m[m.snap_t <= m.start]
    if at is not None:
        m = m.merge(at, on="game_id")
        m = m[m.snap_t <= m["as_of"] + pd.Timedelta(minutes=2)]
    m["pref"] = m.book.map({SHARP: 0, "draftkings": 1}).fillna(9)
    m = m[m.pref < 9]
    for c in ("hp", "ap", "total_line", "over", "under"):
        m[c] = pd.to_numeric(m[c], errors="coerce")
    t = m[(m.market == "totals") & m.over.notna() & m.under.notna() & m.total_line.notna()]
    t = t.sort_values(["game_id", "pref", "snap_t"]).groupby(["game_id", "pref"]).tail(1)
    t = t.sort_values(["game_id", "pref"]).drop_duplicates("game_id")
    t = t.assign(p_over=imp(t.over) / (imp(t.over) + imp(t.under)))[["game_id", "total_line", "p_over", "snap_t"]]
    h = m[(m.market == "h2h") & m.hp.notna() & m.ap.notna()]
    h = h.sort_values(["game_id", "pref", "snap_t"]).groupby(["game_id", "pref"]).tail(1)
    h = h.sort_values(["game_id", "pref"]).drop_duplicates("game_id")
    h = h.assign(p_home=imp(h.hp) / (imp(h.hp) + imp(h.ap)))[["game_id", "p_home"]]
    out = t.rename(columns={"total_line": "main", "snap_t": "main_snap"}).merge(h, on="game_id")
    return out


def quotes(data: dict, res: pd.DataFrame) -> pd.DataFrame:
    """Every bought quote as one row per SIDE, with the result. Team totals carry the team's own goals."""
    d = data["deriv"].copy()
    for c in ("line", "over", "under"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.merge(res, on="game_id")
    d["snap_t"] = pd.to_datetime(d.snap, utc=True)
    d = d[d.snap_t <= d.start]
    d["actual"] = np.select([d.market == "team_totals_home", d.market == "team_totals_away", d.market == "totals_p1"],
                            [d.home_goals, d.away_goals, d.p1], default=d.total)
    d["family"] = d.market.str.replace("_home", "", regex=False).str.replace("_away", "", regex=False)
    d = d[d.actual.notna()]
    two = d.over.notna() & d.under.notna()
    tot = imp(d.over.fillna(100)) + imp(d.under.fillna(100))
    d = d[~(two & ((tot < 1.0) | (tot > 1.25)))]             # alternates carry a wider margin than a main line
    out = []
    for side in ("over", "under"):
        s = d[d[side].notna()].copy()
        s["side"], s["price"] = side, s[side]
        other = s["under" if side == "over" else "over"]
        s["nv"] = np.where(other.notna(), imp(s.price) / (imp(s.price) + imp(other.fillna(100))), np.nan)
        won = (s.actual > s.line) if side == "over" else (s.actual < s.line)
        s["won"] = won.astype(int)
        s["profit"] = np.where(s.actual == s.line, 0.0, np.where(won, wpu(s.price), -1.0))
        out.append(s)
    return pd.concat(out, ignore_index=True)


# ── tables ───────────────────────────────────────────────────────────────────

def interval(b: pd.DataFrame, n: int = 3000) -> str:
    g = b.groupby("game_date").profit.agg(["sum", "count"])
    tot, cnt = g["sum"].values, g["count"].values
    idx = np.random.default_rng(7).integers(0, len(g), size=(n, len(g)))
    lo, hi = np.percentile(tot[idx].sum(1) / cnt[idx].sum(1), [2.5, 97.5]) * 100
    return f"{lo:+.1f}..{hi:+.1f}"


def row(label: dict, b: pd.DataFrame) -> dict:
    if len(b) < 40:
        return {**label, "bets": len(b)}
    p = b.profit.values
    r = {**label, "bets": len(b), "units": round(float(p.sum()), 1), "roi%": round(float(p.mean()) * 100, 2),
         "95% by day": interval(b), "win%": round(float((p > 0).mean()) * 100, 1), "med price": int(b.price.median())}
    for s in SEASONS:
        q = b[b.season == s].sort_values("game_date").profit.values
        if len(q) < 30:
            r[f"{s - 1}-{str(s)[2:]}"] = f"({len(q)})"
            continue
        h = len(q) // 2
        r[f"{s - 1}-{str(s)[2:]}"] = f"{q.mean() * 100:+.1f}% ({len(q)}) [{q[:h].mean() * 100:+.0f}/{q[h:].mean() * 100:+.0f}]"
    return r


def show(title: str, rows: list[dict]) -> None:
    print(f"\n### {title}\n")
    print(pd.DataFrame(rows).to_string(index=False), flush=True)


def one_per_game(b: pd.DataFrame, by: list[str], ev: str) -> pd.DataFrame:
    """The best expected value per game (and per `by`), ties to the earlier book in the bettable order."""
    rank = {bk: i for i, bk in enumerate(BETTABLE)}
    b = b.assign(_r=b.book.map(rank).fillna(len(rank)))
    return (b.sort_values([ev, "_r"], ascending=[False, True], kind="mergesort")
            .drop_duplicates(["game_id"] + by).drop(columns="_r").sort_values(["game_date", "game_id"]))


def blind(q: pd.DataFrame) -> None:
    for fam in MARKETS:
        f = q[(q.family == fam) & (q.price >= FLOOR)]
        if f.empty:
            print(f"{fam}: no priced side with a result yet")
            continue
        dk = f[f.book == "draftkings"]
        ref = dk if len(dk) else f[f.book == f.book.value_counts().index[0]]
        name = "DraftKings" if len(dk) else f"{ref.book.iloc[0]} (DraftKings does not list it)"
        rows = [row({"book": name, "side": sd, "number": "all"}, ref[ref.side == sd]) for sd in ("over", "under")]
        for ln in sorted(ref.line.unique()):
            for sd in ("over", "under"):
                b = ref[(ref.side == sd) & (ref.line == ln)]
                if len(b) >= 150:
                    rows.append(row({"book": name, "side": sd, "number": ln}, b))
        show(f"BLIND, {fam}: every over and every under at {name}, price floor {FLOOR}", rows)
        rows = []
        for sd in ("over", "under"):
            for lo, hi in ((-200, -151), (-150, -121), (-120, -101), (100, 130), (131, 200), (201, 400), (401, 5000)):
                rows.append(row({"side": sd, "price": f"{lo}..{hi}"},
                                ref[(ref.side == sd) & (ref.price >= lo) & (ref.price <= hi)]))
        show(f"BLIND, {fam}: by price band at {name}", rows)
        print(f"books quoting {fam}: {f.groupby('book').game_id.nunique().sort_values(ascending=False).to_dict()}")


def sharp_vs_soft(q: pd.DataFrame) -> None:
    pin = q[(q.book == SHARP) & q.nv.notna()][["game_id", "market", "line", "side", "nv"]].rename(columns={"nv": "pin"})
    s = q[q.book.isin(BETTABLE) & (q.price >= FLOOR)].merge(pin, on=["game_id", "market", "line", "side"])
    s["ev"] = s.pin * (1 + wpu(s.price)) - 1
    for fam in MARKETS:
        f = s[s.family == fam]
        print(f"\n{fam}: bettable quotes with Pinnacle at the same number in the same snapshot: {len(f):,} "
              f"({f.game_id.nunique():,} games)")
        for sides, label in ((("over", "under"), "either side"), (("under",), "unders"), (("over",), "overs")):
            show(f"SHARP-VS-SOFT, {fam}, {label}: best bettable price, one bet a game per market",
                 [row({"pin EV>=": c}, one_per_game(f[(f.ev >= c) & f.side.isin(sides)], ["market"], "ev"))
                  for c in EV_CUTS])
        b = one_per_game(f[f.ev >= 0.04], ["market"], "ev")
        if len(b):
            print("where the 4% bets land:", b.book.value_counts().to_dict())


def model(q: pd.DataFrame, data: dict, res: pd.DataFrame) -> None:
    """P(outcome) from the main total and moneyline alone, fitted on earlier seasons."""
    hist = main_lines(data, res).merge(res, on="game_id")
    asof = (q.groupby("game_id").snap_t.max().rename("as_of").reset_index())
    now = main_lines(data, res, asof)
    print(f"\nmain lines for the model: {len(hist):,} games to fit on "
          f"({hist.groupby('season').size().to_dict()}); {len(now):,} priced games have a main line no later "
          f"than their derivative snapshot (median gap "
          f"{(asof.merge(now, on='game_id').pipe(lambda d: (d["as_of"] - d.main_snap).dt.total_seconds() / 60)).median():.0f} min)")

    def X(d: pd.DataFrame, p_team=None) -> np.ndarray:
        lo = np.log(d.p_over / (1 - d.p_over))
        cols = [d.main.values, lo.values]
        if p_team is not None:
            cols.append(np.log(p_team / (1 - p_team)).values)
        return np.column_stack(cols)

    scored = []
    for season in SEASONS:
        tr = hist[hist.season < season]
        te = q[q.season == season].merge(now, on="game_id")
        for fam in MARKETS:
            f = te[te.family == fam]
            for (market, line), grp in f.groupby(["market", "line"]):
                if fam == "team_totals":
                    home = market.endswith("_home")
                    goals = tr.home_goals if home else tr.away_goals
                    xt, xg = X(tr, tr.p_home if home else 1 - tr.p_home), X(grp, grp.p_home if home else 1 - grp.p_home)
                    ok = np.ones(len(tr), bool)
                elif fam == "totals_p1":
                    ok = tr.p1.notna().values
                    goals = tr.p1
                    xt, xg = X(tr), X(grp)
                else:
                    ok = np.ones(len(tr), bool)
                    goals = tr.total
                    xt, xg = X(tr), X(grp)

                def chance(y) -> np.ndarray | None:
                    y = y[ok].astype(int)
                    if y.sum() < 40 or (1 - y).sum() < 40:
                        return None                           # a number that almost never lands that way
                    return LogisticRegression(C=10.0, max_iter=500).fit(xt[ok], y).predict_proba(xg)[:, 1]

                # A whole number can PUSH, so "under" is not "not over": each side
                # gets its own fit there. On a half number the two are complements.
                p_over = chance(goals > line)
                p_under = chance(goals < line) if float(line).is_integer() else (None if p_over is None else 1 - p_over)
                if p_over is None or p_under is None:
                    continue
                g = grp.copy()
                g["p"] = np.where(g.side == "over", p_over, p_under)
                g["p_lose"] = np.where(g.side == "over", p_under, p_over)
                scored.append(g)
    s = pd.concat(scored, ignore_index=True)
    s["ev"] = s.p * wpu(s.price) - s.p_lose                  # a push returns the stake
    for fam in MARKETS:
        f = s[s.family == fam]
        if f.empty:
            continue
        cal = []
        for lo, hi in ((0.05, 0.2), (0.2, 0.35), (0.35, 0.45), (0.45, 0.55), (0.55, 0.65), (0.65, 0.8), (0.8, 0.95)):
            c = f[(f.p >= lo) & (f.p < hi) & (f.book == f.book.value_counts().index[0])]
            if len(c) >= 100:
                cal.append({"model says": f"{lo:.2f}-{hi:.2f}", "sides": len(c), "claimed": round(float(c.p.mean()), 3),
                            "happened": round(float(c.won.mean()), 3), "price implies": round(float(imp(c.price).mean()), 3)})
        show(f"MODEL, {fam}: claimed against realised (the most-quoted book's sides)", cal)
        b = f[f.book.isin(BETTABLE) & (f.price >= FLOOR)]
        for sides, label in ((("over", "under"), "either side"), (("under",), "unders"), (("over",), "overs")):
            show(f"MODEL, {fam}, {label}: best bettable price, one bet a game per market, floor {FLOOR}",
                 [row({"EV>=": c}, one_per_game(b[(b.ev >= c) & b.side.isin(sides)], ["market"], "ev"))
                  for c in EV_CUTS])
        dk = f[(f.book == "draftkings") & (f.price >= FLOOR)]
        if len(dk):
            show(f"MODEL, {fam}, either side: DraftKings alone",
                 [row({"EV>=": c}, one_per_game(dk[dk.ev >= c], ["market"], "ev")) for c in EV_CUTS])
        top = one_per_game(b[b.ev >= 0.06], ["market"], "ev")
        if len(top):
            print("at EV >= 0.06 the bets land at:", top.book.value_counts().to_dict(),
                  "| by side:", top.side.value_counts().to_dict(),
                  "| by number:", top.line.value_counts().head(8).to_dict())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", default=None)
    a = ap.parse_args()
    data = load(a.cache)
    res = results(data)
    q = quotes(data, res)
    print(f"{len(data['deriv']):,} bought quotes; {len(q):,} priced sides with a result, "
          f"{q.game_id.nunique():,} games, by season {q.drop_duplicates('game_id').groupby('season').size().to_dict()}; "
          f"first-period goals known for {int(res[res.season.isin(SEASONS)].p1.notna().sum()):,} of "
          f"{int(res.season.isin(SEASONS).sum()):,} games")
    blind(q)
    sharp_vs_soft(q)
    model(q, data, res)


if __name__ == "__main__":
    main()
