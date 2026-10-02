"""The NHL prop models in models/nhl_props.py, backtested the way production runs them.

Walk-forward on the three priced seasons: each season is scored by a model
fitted only on earlier seasons, through the SAME module the card scores with,
and graded in units at the price that was on offer (one pre-game snapshot a
game, `player_prop_odds`, every book quoted at the same instant). One bet per
player per game: the book, line and side with the best expected value.

What is applied that a lab table would not:

  * the books the card shops (models.nhl_props.books()), with DraftKings alone
    shown beside it;
  * the sides the Spec may bet (unders), with the other side shown beside it;
  * the price floor (config.min_odds_for, -200 by default);
  * the coherent-quote filter the card applies (two-way implied sum 1.00-1.15);
  * the probability both ways: the model's OWN, and the borrowed correction a
    model with no record is handed (config.MODELS_ON_OWN_PROBABILITY decides);
  * for saves, the void: a priced goalie who did not start is no bet.

Reported per market: the EV cut as a neighbourhood, per season with each
season's early / late halves, an interval resampled by GAME DAY (bets on one
night share a slate, so they are not independent draws), claimed against
realised, bets a day, and which book the bets land at.

    python -m scripts.nhl_prop_backtest                      # all three markets
    python -m scripts.nhl_prop_backtest --model nhl_prop_saves
    python -m scripts.nhl_prop_backtest --cache DIR          # read a local copy, not the database
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config  # noqa: E402
import models.nhl_props as np_  # noqa: E402
from models.probability_calibration import apply_calibration  # noqa: E402

pd.set_option("display.width", 280)
pd.set_option("display.max_columns", 40)
SEASONS = [2024, 2025, 2026]
EV_CUTS = (0.0, 0.03, 0.05, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20)
BORROWED = {"method": "platt", "a": 1.0, "b": -0.259947}     # what a no-record model is given
COHERENT_SUM = (1.00, 1.15)
FLOOR = -200


# ── data ─────────────────────────────────────────────────────────────────────

def load(cache: str | None) -> dict:
    """Players, teams, games and prices -- from the database, or from a folder of pickles."""
    markets = [s.market for s in np_.SPECS.values()]
    if cache:
        c = Path(cache)
        sk, go = pd.read_pickle(c / "skaters.pkl"), pd.read_pickle(c / "goalies.pkl")
        px = pd.read_pickle(c / "props.pkl")
        return {"skater": sk[sk.game_type == 2][list(np_.SKATER_COLS)],
                "goalie": go[(go.game_type == 2) & go.player_id.notna()][list(np_.GOALIE_COLS)],
                "teams": pd.read_pickle(c / "teams.pkl")[list(np_.TEAM_COLS)],
                "games": pd.read_pickle(c / "games.pkl"), "prices": px[px.market.isin(markets)]}
    from data.db import get_connection
    conn = get_connection()
    try:
        games = pd.DataFrame(conn.execute(
            "SELECT game_id, season, commence_time FROM games WHERE sport = 'NHL'").fetchall(),
            columns=["game_id", "season", "commence_time"])
        ids = sorted(games[games.season.isin(SEASONS)].game_id)
        rows = []
        for i in range(0, len(ids), 300):
            rows += conn.execute(
                "SELECT game_id, player_name, market, bookmaker, line, over_price, under_price, snapshot_at "
                "FROM player_prop_odds WHERE game_id = ANY(%s) AND market = ANY(%s) AND snapshot_type = 'open'",
                (ids[i:i + 300], markets)).fetchall()
        px = pd.DataFrame(rows, columns=["game_id", "player", "market", "book", "line", "over", "under", "snap"])
        return {"skater": np_.load_players(conn, "skater"), "goalie": np_.load_players(conn, "goalie"),
                "teams": np_.load_teams(conn), "games": games, "prices": px}
    finally:
        conn.close()


def prices(data: dict, spec: np_.Spec) -> pd.DataFrame:
    """Coherent pre-game quotes for one market, every book, with the season."""
    px = data["prices"][data["prices"].market == spec.market].copy()
    for c in ("line", "over", "under"):
        px[c] = pd.to_numeric(px[c], errors="coerce")
    px = px.merge(data["games"][["game_id", "season", "commence_time"]], on="game_id")
    late = pd.to_datetime(px.snap, utc=True) > pd.to_datetime(px.commence_time, utc=True)
    two = px.over.notna() & px.under.notna()
    total = px.over.map(np_.implied, na_action="ignore") + px.under.map(np_.implied, na_action="ignore")
    bad = two & ~total.between(*COHERENT_SUM)
    print(f"{spec.market}: {len(px):,} quotes; dropped {int(late.sum()):,} taken after puck drop and "
          f"{int((bad & ~late).sum()):,} incoherent "
          f"({px[bad & ~late].book.value_counts().head(4).to_dict()})")
    px = px[~late & ~bad & px.line.notna()]
    px["pkey"] = px.player.map(np_.name_key)
    return px.drop_duplicates(["game_id", "pkey", "book", "line"])


# ── bets ─────────────────────────────────────────────────────────────────────

def predictions(spec: np_.Spec, frame: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for season in SEASONS:
        fitted = np_.fit(spec, frame, season - 1)
        te = np_.usable(spec, frame[(frame.season == season) & ~frame.upcoming]).dropna(subset=[spec.stat]).copy()
        te["mu"] = np_.predict_mean(spec, fitted, te)
        te["alpha"] = fitted["dispersion"]
        print(f"  {season - 1}-{str(season)[2:]}: fit on {fitted['n_train']:,} rows, excess variance "
              f"{fitted['dispersion']:.4f}; {len(te):,} rows to score; mean predicted {te.mu.mean():.2f} "
              f"vs actual {te[spec.stat].mean():.2f}")
        parts.append(te[["game_id", "pkey", "game_date", "season", "mu", "alpha", spec.stat]])
    return pd.concat(parts, ignore_index=True).rename(columns={spec.stat: "actual"})


def sides(df: pd.DataFrame) -> pd.DataFrame:
    """One row per priced SIDE with the model's probability, EV both ways, and the result."""
    po = np.array([float(np_.p_over(m, ln, a)) for m, ln, a in zip(df.mu, df.line, df.alpha)])
    out = []
    for side, col, p in (("over", "over", po), ("under", "under", 1 - po)):
        has = df[col].notna().values
        s = df[has].copy()
        s["side"], s["price"], s["p"] = side, s[col], p[has]
        won = (s.actual > s.line) if side == "over" else (s.actual < s.line)
        s["won"] = won.astype(int)
        s["profit"] = np.where(s.actual == s.line, 0.0, np.where(won, s.price.map(np_.win_per_unit), -1.0))
        out.append(s)
    s = pd.concat(out, ignore_index=True)
    w = s.price.map(np_.win_per_unit)
    s["p_borrowed"] = s.p.map(lambda v: apply_calibration(float(v), BORROWED))
    s["ev"] = s.p * (1 + w) - 1
    s["ev_borrowed"] = s.p_borrowed * (1 + w) - 1
    return s


def card(s: pd.DataFrame, cut: float, which: tuple[str, ...] = ("over", "under"),
         ev_col: str = "ev", floor: float | None = FLOOR, per_game: int | None = None) -> pd.DataFrame:
    """The bets a rule places: one per player per game, the best EV among the sides it may take,
    and (`per_game`) at most that many a game, best EV first -- as the card's limit_per_game."""
    b = s[(s[ev_col] >= cut) & s.side.isin(which)]
    if floor is not None:
        b = b[b.price >= floor]
    rank = {bk: i for i, bk in enumerate(np_.books())}          # a tie goes to the earlier book, as the card's does
    b = b.assign(_rank=b.book.map(rank).fillna(len(rank)) if "book" in b.columns else 0)
    b = (b.sort_values([ev_col, "_rank"], ascending=[False, True], kind="mergesort")
         .drop_duplicates(["game_id", "pkey"]).drop(columns="_rank"))
    if per_game is not None:
        b = b.groupby("game_id", sort=False).head(per_game)
    return b.sort_values(["game_date", "game_id", "pkey"])


def day_interval(b: pd.DataFrame, n: int = 5000) -> str:
    """95% interval on the return, resampling whole game days.

    Seeded per call, so the same bets always print the same interval whatever
    was computed before them.
    """
    g = b.groupby("game_date").profit.agg(["sum", "count"])
    tot, cnt = g["sum"].values, g["count"].values
    idx = np.random.default_rng(7).integers(0, len(g), size=(n, len(g)))
    lo, hi = np.percentile(tot[idx].sum(axis=1) / cnt[idx].sum(axis=1), [2.5, 97.5]) * 100
    return f"{lo:+.1f}..{hi:+.1f}"


def line(label: dict, b: pd.DataFrame) -> dict:
    if len(b) < 30:
        return {**label, "bets": len(b)}
    p = b.profit.values
    r = {**label, "bets": len(b), "units": round(float(p.sum()), 1), "roi%": round(float(p.mean()) * 100, 2),
         "95% by day": day_interval(b), "win%": round(float((p > 0).mean()) * 100, 1),
         "med price": int(b.price.median()), "claimed": round(float(b.p.mean()), 3),
         "won": round(float(b.won.mean()), 3)}
    for season in SEASONS:
        q = b[b.season == season].profit.values
        if len(q) < 30:
            r[f"{season - 1}-{str(season)[2:]}"] = f"({len(q)})"
            continue
        h = len(q) // 2
        r[f"{season - 1}-{str(season)[2:]}"] = (f"{q.mean() * 100:+.1f}% ({len(q)}) "
                                                f"[{q[:h].mean() * 100:+.0f}/{q[h:].mean() * 100:+.0f}]")
    return r


def show(title: str, rows: list[dict]) -> None:
    print(f"\n### {title}\n")
    print(pd.DataFrame(rows).to_string(index=False))


def claimed_vs_realised(b: pd.DataFrame) -> list[dict]:
    rows = []
    for lo, hi in ((0.3, 0.4), (0.4, 0.5), (0.5, 0.55), (0.55, 0.6), (0.6, 0.65), (0.65, 0.7), (0.7, 0.8), (0.8, 1.01)):
        q = b[(b.p >= lo) & (b.p < hi)]
        if len(q) >= 30:
            rows.append({"model says": f"{lo:.2f}-{min(hi, 1.0):.2f}", "sides": len(q),
                         "claimed": round(float(q.p.mean()), 3),
                         "borrowed says": round(float(q.p_borrowed.mean()), 3),
                         "happened": round(float(q.won.mean()), 3),
                         "price implies": round(float(q.price.map(np_.implied).mean()), 3)})
    return rows


def report(spec: np_.Spec, data: dict, frame: pd.DataFrame, dump: str | None) -> None:
    print(f"\n{'=' * 100}\n{spec.model_id}  ({spec.market}, settles on {spec.stat}; "
          f"{'LIVE' if spec in np_.LIVE else 'NOT live'})\n{'=' * 100}")
    px = prices(data, spec)
    pred = predictions(spec, frame)
    m = px.merge(pred.drop(columns=["season"]), on=["game_id", "pkey"], how="inner")
    books = list(np_.books())
    m = m[m.book.isin(books)]
    print(f"books shopped: {books}")
    print(f"priced player-games by season {m.drop_duplicates(['game_id', 'pkey']).groupby('season').size().to_dict()} "
          f"matched to a prediction (unmatched = under {np_.MIN_GAMES} games, a name the log does not hold"
          + ("; or a goalie who did not start: void" if spec.kind == "goalie" else "") + "); "
          f"quotes by book {m.book.value_counts().to_dict()}")
    s = sides(m)
    dk = s[s.book == np_.BOOK]
    print(f"DraftKings lines: {m[m.book == np_.BOOK].line.value_counts().head(8).to_dict()}")
    for side in ("over", "under"):
        print(f"blind always {side} at DraftKings: "
              f"{line({}, dk[dk.side == side].sort_values(['game_date', 'game_id', 'pkey']))}")

    rule = "/".join(spec.sides)
    other = tuple(x for x in ("over", "under") if x not in spec.sides)
    cap = spec.max_per_game
    show(f"THE RULE: {rule} only, the best price among the books shopped, the model's OWN probability, "
         f"floor {FLOOR}, {'no limit' if cap is None else f'at most {cap} a game'}; "
         f"per season as return (bets) [first half / second half]",
         [line({"EV>=": c}, card(s, c, spec.sides, per_game=cap)) for c in EV_CUTS])
    if cap is not None:
        show("The rule by bets allowed per game (best EV first)",
             [line({"EV>=": c, "per game": n}, card(s, c, spec.sides, per_game=n))
              for c in (0.08, 0.10, 0.12) for n in (1, 2, 3, 4, 5, None)])
    show("The same rule at DraftKings alone",
         [line({"EV>=": c}, card(dk, c, spec.sides)) for c in EV_CUTS])
    if other:
        show(f"The side the rule does not bet ({'/'.join(other)}), best price",
             [line({"EV>=": c}, card(s, c, other)) for c in EV_CUTS])
    show(f"The rule under the BORROWED correction instead ({rule}, best price, floor {FLOOR})",
         [line({"EV>=": c}, card(s, c, spec.sides, "ev_borrowed")) for c in EV_CUTS])
    show("Claimed against realised, every priced side at DraftKings", claimed_vs_realised(dk))
    show("The rule by price floor",
         [line({"EV>=": c, "floor": f}, card(s, c, spec.sides, floor=f)) for c in (0.06, 0.10) for f in (None, -250, -200, -150)])
    floor = config.MODEL_OWN_EV_FLOOR.get(spec.model_id, 0.10)
    b = card(s, floor, spec.sides, per_game=spec.max_per_game)
    days = s.game_date.nunique()
    if len(b):
        show(f"Where the bets land at EV >= {floor:.2f}",
             [line({"book": bk}, b[b.book == bk]) for bk in b.book.value_counts().index])
        print(f"\nat EV >= {floor:.2f}: {len(b):,} bets over {days:,} priced game days ({len(b) / max(days, 1):.1f} a day; "
              f"most on one day {int(b.groupby('game_date').size().max())})")
    if dump:
        s.assign(model_id=spec.model_id).to_pickle(Path(dump) / f"sides_{spec.model_id}.pkl")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", default=None, choices=sorted(np_.SPECS))
    ap.add_argument("--cache", default=None, help="a folder of pickles to read instead of the database")
    ap.add_argument("--dump", default=None, help="write the bet-level rows to this folder")
    a = ap.parse_args()
    data = load(a.cache)
    frames: dict[str, pd.DataFrame] = {}
    for spec in ([np_.SPECS[a.model]] if a.model else np_.SPECS.values()):
        if spec.kind not in frames:
            frames[spec.kind] = np_.build_frame(spec, data[spec.kind], data["teams"])
        report(spec, data, frames[spec.kind], a.dump)


if __name__ == "__main__":
    main()
