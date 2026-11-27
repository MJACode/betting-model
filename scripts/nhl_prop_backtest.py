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
    python -m scripts.nhl_prop_backtest --moneypuck          # points and assists candidate, not live
    python -m scripts.nhl_prop_backtest --assists-no-team-pace  # assists without team pace, not live
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
# 2027 is the season in progress (ending year). The default report stays on the
# three seasons the live artifacts were walked forward on. The points and
# assists candidate adds it.
POINT_SEASONS = [2024, 2025, 2026, 2027]
EV_CUTS = (0.0, 0.03, 0.05, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20)
BORROWED = {"method": "platt", "a": 1.0, "b": -0.259947}     # what a no-record model is given
COHERENT_SUM = (1.00, 1.15)
FLOOR = -200


# ── data ─────────────────────────────────────────────────────────────────────

def load(cache: str | None, seasons: list[int] | None = None,
         markets: list[str] | None = None) -> dict:
    """Players, teams, games and prices -- from the database, or from a folder of pickles.

    `seasons` limits which games' prices are read. The default is the three
    seasons the live report scores. A cache folder is read whole. `markets`
    defaults to the live specs; the points backtest names the markets it scores.
    """
    seasons = SEASONS if seasons is None else list(seasons)
    markets = list(dict.fromkeys(markets or [s.market for s in np_.SPECS.values()]))
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
        ids = sorted(games[games.season.isin(seasons)].game_id)
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


def _utc(series: pd.Series) -> pd.Series:
    """Timestamps as UTC. Snapshot strings carry fractional seconds; pandas 3
    will not infer that mix unless the format is named."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, utc=True)
    return pd.to_datetime(series, utc=True, format="ISO8601")


def prices(data: dict, spec: np_.Spec) -> pd.DataFrame:
    """Coherent pre-game quotes for one market, every book, with the season."""
    px = data["prices"][data["prices"].market == spec.market].copy()
    for c in ("line", "over", "under"):
        px[c] = pd.to_numeric(px[c], errors="coerce")
    px = px.merge(data["games"][["game_id", "season", "commence_time"]], on="game_id")
    late = _utc(px.snap) > _utc(px.commence_time)
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

def namesakes(te: pd.DataFrame, frame: pd.DataFrame, season: int) -> pd.Series:
    """True for a row the live card could never bet: the name is shared.

    Prices find their player by NAME (`name_key`), so where two players share
    one, a price is attached to both and the backtest bets the one with the
    better EV -- grading, say, Elias Pettersson the forward's shots under on
    Elias Pettersson the defenceman's count. The card refuses such a name: it
    skips any price whose name matches more than one player who has played for
    either team this season or last (scripts/nhl_props_card.upcoming_rows). The
    same test here. Found 2026-10-08: 124 such bets, +89.8 units at a 90% win
    rate, 35% of the units the one-a-game, two-a-night rule was justified on.
    """
    seen = frame[frame.season.isin([season - 1, season]) & ~frame.upcoming]
    roster = seen.groupby(["team", "pkey"]).player_id.agg(lambda s: frozenset(s.dropna()))
    pairs = te[["team", "opponent", "pkey"]].drop_duplicates()
    shared = {(t, o, k) for t, o, k in pairs.itertuples(index=False)
              if len(roster.get((t, k), frozenset()) | roster.get((o, k), frozenset())) > 1}
    return pd.Series([(t, o, k) in shared for t, o, k in zip(te.team, te.opponent, te.pkey)], index=te.index)


def predictions(spec: np_.Spec, frame: pd.DataFrame, seasons: list[int] | None = None) -> pd.DataFrame:
    parts = []
    for season in (SEASONS if seasons is None else seasons):
        fitted = np_.fit(spec, frame, season - 1)
        te = np_.usable(spec, frame[(frame.season == season) & ~frame.upcoming]).dropna(subset=[spec.stat]).copy()
        shared = namesakes(te, frame, season)
        if shared.any():
            print(f"  {season - 1}-{str(season)[2:]}: {int(shared.sum()):,} player-games dropped, a name shared "
                  f"with another player on either team ({sorted(te[shared].pkey.unique())[:6]})")
        te = te[~shared]
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


def day_interval(b: pd.DataFrame, n: int = 5000, col: str = "profit") -> str:
    """95% interval on the return, resampling whole game days.

    Seeded per call, so the same bets always print the same interval whatever
    was computed before them. `col` is the per-bet profit. The default is the
    1-unit-risked profit this script has always reported.
    """
    g = b.groupby("game_date")[col].agg(["sum", "count"])
    tot, cnt = g["sum"].values, g["count"].values
    idx = np.random.default_rng(7).integers(0, len(g), size=(n, len(g)))
    lo, hi = np.percentile(tot[idx].sum(axis=1) / cnt[idx].sum(axis=1), [2.5, 97.5]) * 100
    return f"{lo:+.1f}..{hi:+.1f}"


def line(label: dict, b: pd.DataFrame, seasons: list[int] | None = None) -> dict:
    if len(b) < 30:
        return {**label, "bets": len(b)}
    p = b.profit.values
    r = {**label, "bets": len(b), "units": round(float(p.sum()), 1), "roi%": round(float(p.mean()) * 100, 2),
         "95% by day": day_interval(b), "win%": round(float((p > 0).mean()) * 100, 1),
         "med price": int(b.price.median()), "claimed": round(float(b.p.mean()), 3),
         "won": round(float(b.won.mean()), 3)}
    for season in (SEASONS if seasons is None else seasons):
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


def _season_name(season: int) -> str:
    return f"{season - 1}-{str(season)[2:]}"


def report(spec: np_.Spec, data: dict, frame: pd.DataFrame, dump: str | None,
           seasons: list[int] | None = None, quiet: bool = False) -> pd.DataFrame:
    seasons = SEASONS if seasons is None else list(seasons)
    base = np_.POINTS if spec.model_id == np_.POINTS.model_id else np_.SPECS.get(spec.model_id)
    live_features = base is not None and spec.features == base.features
    print(f"\n{'=' * 100}\n{spec.model_id}  ({spec.market}, settles on {spec.stat}; "
          f"{'LIVE' if spec in np_.LIVE and live_features else 'CANDIDATE, not live'})\n{'=' * 100}")
    px = prices(data, spec)
    pred = predictions(spec, frame, seasons)
    m = px.merge(pred.drop(columns=["season"]), on=["game_id", "pkey"], how="inner")
    books = list(np_.books())
    m = m[m.book.isin(books)]
    print(f"books shopped: {books}")
    print(f"priced player-games by season {m.drop_duplicates(['game_id', 'pkey']).groupby('season').size().to_dict()} "
          f"matched to a prediction (unmatched = under {np_.MIN_GAMES} games, a name the log does not hold"
          + ("; or a goalie who did not start: void" if spec.kind == "goalie" else "") + "); "
          f"quotes by book {m.book.value_counts().to_dict()}")
    s = sides(m)
    if quiet:
        return s
    dk = s[s.book == np_.BOOK]

    def _line(label: dict, b: pd.DataFrame) -> dict:
        return line(label, b, seasons)

    print(f"DraftKings lines: {m[m.book == np_.BOOK].line.value_counts().head(8).to_dict()}")
    for side in ("over", "under"):
        print(f"blind always {side} at DraftKings: "
              f"{_line({}, dk[dk.side == side].sort_values(['game_date', 'game_id', 'pkey']))}")

    rule = "/".join(spec.sides)
    other = tuple(x for x in ("over", "under") if x not in spec.sides)
    cap = spec.max_per_game
    show(f"THE RULE: {rule} only, the best price among the books shopped, the model's OWN probability, "
         f"floor {FLOOR}, {'no limit' if cap is None else f'at most {cap} a game'}; "
         f"per season as return (bets) [first half / second half]",
         [_line({"EV>=": c}, card(s, c, spec.sides, per_game=cap)) for c in EV_CUTS])
    if cap is not None:
        show("The rule by bets allowed per game (best EV first)",
             [_line({"EV>=": c, "per game": n}, card(s, c, spec.sides, per_game=n))
              for c in (0.08, 0.10, 0.12) for n in (1, 2, 3, 4, 5, None)])
    show("The same rule at DraftKings alone",
         [_line({"EV>=": c}, card(dk, c, spec.sides)) for c in EV_CUTS])
    if other:
        show(f"The side the rule does not bet ({'/'.join(other)}), best price",
             [_line({"EV>=": c}, card(s, c, other)) for c in EV_CUTS])
    show(f"The rule under the BORROWED correction instead ({rule}, best price, floor {FLOOR})",
         [_line({"EV>=": c}, card(s, c, spec.sides, "ev_borrowed")) for c in EV_CUTS])
    show("Claimed against realised, every priced side at DraftKings", claimed_vs_realised(dk))
    show("The rule by price floor",
         [_line({"EV>=": c, "floor": f}, card(s, c, spec.sides, floor=f)) for c in (0.06, 0.10) for f in (None, -250, -200, -150)])
    floor = config.MODEL_OWN_EV_FLOOR.get(spec.model_id, 0.18 if spec.model_id == np_.POINTS.model_id else 0.10)
    b = card(s, floor, spec.sides, per_game=spec.max_per_game)
    days = s.game_date.nunique()
    if len(b):
        show(f"Where the bets land at EV >= {floor:.2f}",
             [_line({"book": bk}, b[b.book == bk]) for bk in b.book.value_counts().index])
        print(f"\nat EV >= {floor:.2f}: {len(b):,} bets over {days:,} priced game days ({len(b) / max(days, 1):.1f} a day; "
              f"most on one day {int(b.groupby('game_date').size().max())})")
    if dump:
        tag = spec.model_id if live_features else spec.model_id + "_moneypuck"
        s.assign(model_id=tag).to_pickle(Path(dump) / f"sides_{tag}.pkl")
    return s


def _decisive(b: pd.DataFrame) -> pd.DataFrame:
    return b[b.actual != b.line]


def log_loss(b: pd.DataFrame) -> float:
    """Log loss of P(this side wins) on decisive rows. A push is not a win or a loss."""
    d = _decisive(b)
    if not len(d):
        return float("nan")
    y = d.won.to_numpy(dtype=float)
    p = np.clip(d.p.to_numpy(dtype=float), 1e-6, 1 - 1e-6)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def brier(b: pd.DataFrame) -> float:
    """Brier score of P(this side wins) on decisive rows. A push is left out."""
    d = _decisive(b)
    if not len(d):
        return float("nan")
    y = d.won.to_numpy(dtype=float)
    p = d.p.to_numpy(dtype=float)
    return float(np.mean((p - y) ** 2))


def calibration_error(b: pd.DataFrame, n_bins: int = 10) -> float:
    """Mean absolute gap between claimed P(side) and the hit rate, weighted by count."""
    d = _decisive(b)
    if not len(d):
        return float("nan")
    y = d.won.to_numpy(dtype=float)
    p = d.p.to_numpy(dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    err = 0.0
    n = 0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & (p <= hi if hi == 1 else p < hi)
        k = int(mask.sum())
        if not k:
            continue
        err += abs(float(y[mask].mean()) - float(p[mask].mean())) * k
        n += k
    return err / n if n else float("nan")


def profit_to_win(b: pd.DataFrame) -> np.ndarray:
    """1 unit to win, risk capped at 3. The published record's stake. A push is 0."""
    price = b.price.to_numpy(dtype=float)
    win_per = np.where(price > 0, price / 100.0, 100.0 / np.abs(price))
    risk = 1.0 / win_per
    capped = risk > 3
    risk = np.where(capped, 3.0, risk)
    win = np.where(capped, 3.0 * win_per, 1.0)
    push = b.actual.to_numpy() == b.line.to_numpy()
    won = b.won.to_numpy(dtype=bool) & ~push
    return np.where(push, 0.0, np.where(won, win, -risk))


def _population(s: pd.DataFrame, side: str) -> pd.DataFrame:
    """One quote per player-game on this side: the best EV, no cut and no price floor."""
    return card(s, -9.0, (side,), floor=None)


def _metric_row(label: str, b: pd.DataFrame) -> dict:
    d = _decisive(b)
    row = {
        "set": label,
        "rows": len(b),
        "decisive": len(d),
        "pushes": int((b.actual == b.line).sum()) if len(b) else 0,
        "log_loss": None if not len(d) else round(log_loss(b), 4),
        "brier": None if not len(d) else round(brier(b), 4),
        "cal_err": None if not len(d) else round(calibration_error(b), 4),
        "claimed": None if not len(d) else round(float(d.p.mean()), 3),
        "hit": None if not len(d) else round(float(d.won.mean()), 3),
    }
    if len(b):
        to_win = profit_to_win(b)
        stamped = b.assign(profit_to_win=to_win)
        row["units_risked"] = round(float(b.profit.sum()), 2)
        row["roi_risked"] = round(float(b.profit.mean()), 4)
        row["units_to_win"] = round(float(to_win.sum()), 2)
        row["roi_to_win"] = round(float(to_win.mean()), 4)
        if len(b) >= 30:
            row["95% risked"] = day_interval(b)
            row["95% to win"] = day_interval(stamped, col="profit_to_win")
    return row


def _by_season(label: str, b: pd.DataFrame, seasons: list[int]) -> list[dict]:
    rows = []
    ordered = b.sort_values(["game_date", "game_id", "pkey"]) if len(b) else b
    for season in seasons:
        q = ordered[ordered.season == season]
        row = _metric_row(f"{label} {_season_name(season)}", q)
        if len(q) >= 2:
            h = len(q) // 2
            early, late = q.iloc[:h], q.iloc[h:]
            row["early_roi_risked"] = round(float(early.profit.mean()), 4)
            row["late_roi_risked"] = round(float(late.profit.mean()), 4)
            row["early_n"] = len(early)
            row["late_n"] = len(late)
            if len(early) >= 30:
                row["early_95"] = day_interval(early)
            if len(late) >= 30:
                row["late_95"] = day_interval(late)
        rows.append(row)
    return rows


# Candidate groups, removed one at a time. Linemate expected goals is built from
# the mate's prior individual xG, so dropping the individual columns does not
# take that xG out of lm_xg / pp_unit_xg.
POINT_GROUPS = (
    ("without individual xG and primary assists",
     ("mp_onice_xg_l", "mp_onice_xg_s", "mp_xg_l", "mp_xg_s", "mp_pa_l", "mp_pa_s")),
    ("without power-play share and unit",
     ("pp_share_l", "pp_share_s", "pp_unit_pts_l", "pp_unit_pts_s", "pp_unit_xg_l", "pp_unit_xg_s")),
    ("without linemate quality",
     ("lm_pts_l", "lm_pts_s", "lm_xg_l", "lm_xg_s")),
    ("without team pace and xG for", np_.TEAM_PACE_FEATURES),
    ("without opponent xG against", ("opp_mp_xga_l",)),
    ("without goalie quality", ("opp_gsax_l",)),
    ("without referee power-play rate", ("ref_pp_l",)),
)


def compare_market(base_spec: np_.Spec, base: pd.DataFrame, mp: pd.DataFrame, floor: float,
                   seasons: list[int], ablations: list[tuple[str, pd.DataFrame]] | None = None) -> str:
    """Current features against the candidate, on one price set.

    The rule is the spec's sides, its per-game cap, price floor -200, the
    model's own probability. Overs are scored beside that.
    """
    cap = base_spec.max_per_game
    base_bets = card(base, floor, base_spec.sides, per_game=cap)
    mp_bets = card(mp, floor, base_spec.sides, per_game=cap)
    keys = ["game_id", "pkey", "book", "line", "side"]
    both = base_bets.merge(mp_bets[keys], on=keys, how="inner")
    mp_on_base = base_bets[keys].merge(mp, on=keys, how="inner")
    rows = [
        _metric_row("current, every best-EV under", _population(base, "under")),
        _metric_row("candidate, every best-EV under", _population(mp, "under")),
        _metric_row("current, every best-EV over", _population(base, "over")),
        _metric_row("candidate, every best-EV over", _population(mp, "over")),
        _metric_row(f"current bets, EV>={floor:.2f}", base_bets),
        _metric_row(f"candidate bets, EV>={floor:.2f}", mp_bets),
        _metric_row(f"current overs at EV>={floor:.2f}, no cap", card(base, floor, ("over",))),
        _metric_row(f"candidate overs at EV>={floor:.2f}, no cap", card(mp, floor, ("over",))),
        _metric_row(f"current bets scored by candidate p, EV>={floor:.2f}", mp_on_base),
        _metric_row(f"bets both take, current p, EV>={floor:.2f}", both),
    ]
    if len(both):
        mp_both = both[keys].merge(mp, on=keys, how="inner")
        rows.append(_metric_row(f"bets both take, candidate p, EV>={floor:.2f}", mp_both))
    season_rows = []
    season_rows += _by_season(f"current bets EV>={floor:.2f}", base_bets, seasons)
    season_rows += _by_season(f"candidate bets EV>={floor:.2f}", mp_bets, seasons)
    season_rows += _by_season("current, every under", _population(base, "under"), seasons)
    season_rows += _by_season("candidate, every under", _population(mp, "under"), seasons)
    cuts = tuple(sorted(set(EV_CUTS) | {round(floor, 2)}))
    neigh = []
    for cut in cuts:
        for name, sides_df in (("current", base), ("candidate", mp)):
            b = card(sides_df, cut, base_spec.sides, per_game=cap)
            neigh.append({"model": name, "EV>=": cut,
                          **{k: v for k, v in _metric_row(name, b).items() if k != "set"}})
    ablate_rows = []
    for name, held in ablations or []:
        b = card(held, floor, base_spec.sides, per_game=cap)
        ablate_rows.append(_metric_row(f"{name}, EV>={floor:.2f}", b))
        ablate_rows.append(_metric_row(f"{name}, every under", _population(held, "under")))
    cap_txt = "no per-game cap" if cap is None else f"at most {cap} a game"
    lines = [
        f"{base_spec.model_id}: {cap_txt}, sides {base_spec.sides}, best EV, floor {FLOOR}, "
        f"own probability, EV>={floor:.2f}",
        "overs are not the rule; the over rows are the other side",
        f"current bets {len(base_bets):,}; candidate bets {len(mp_bets):,}; "
        f"both {len(both):,}; current bets the candidate can score {len(mp_on_base):,}",
        "units_risked is 1 unit risked (a loss is -1). units_to_win is 1 unit to win, risk capped at 3.",
        "roi is the mean profit per bet. The day interval resamples whole game days.",
        "",
        pd.DataFrame(rows).to_string(index=False),
        "",
        pd.DataFrame(season_rows).to_string(index=False),
        "",
        pd.DataFrame(neigh).to_string(index=False),
    ]
    if ablate_rows:
        lines += ["", "Each candidate group removed, same prices, the rule at the cut "
                  "and every best-EV under.",
                  pd.DataFrame(ablate_rows).to_string(index=False)]
    return "\n".join(lines)


def load_points_inputs(cache: str | None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """MoneyPuck skater, team and goalie rows, shift-chart pairs, and referees.

    Prior-game features are built later. Playoff pairs and playoff referees are
    left out: the skater log the model trains on is regular season.
    """
    if cache:
        c = Path(cache)
        return (pd.read_pickle(c / "moneypuck_skaters.pkl"),
                pd.read_pickle(c / "moneypuck_teams.pkl"),
                pd.read_pickle(c / "moneypuck_goalies.pkl"),
                pd.read_pickle(c / "shift_linemates.pkl"),
                pd.read_pickle(c / "referees.pkl"))
    from data.db import get_connection
    conn = get_connection()
    try:
        skaters = pd.DataFrame(conn.execute(
            "SELECT player_id, nhl_game_id, on_ice_f_x_goals, i_f_x_goals, i_f_primary_assists "
            "FROM moneypuck_skater_games WHERE situation = %s",
            (np_.MONEYPUCK_SITUATION,)).fetchall(),
            columns=["player_id", "nhl_game_id", "on_ice_f_x_goals", "i_f_x_goals", "i_f_primary_assists"])
        teams = pd.DataFrame(conn.execute(
            "SELECT nhl_game_id, team_abbr, game_date, shots_on_goal_for, x_goals_for, x_goals_against "
            "FROM moneypuck_team_games WHERE situation = %s",
            (np_.MONEYPUCK_SITUATION,)).fetchall(),
            columns=["nhl_game_id", "team", "game_date", "shots_on_goal_for", "x_goals_for", "x_goals_against"])
        goalies = pd.DataFrame(conn.execute(
            "SELECT g.player_id, g.nhl_game_id, g.team, g.game_date, mp.x_goals, mp.goals "
            "FROM nhl_goalie_game_log g "
            "LEFT JOIN moneypuck_goalie_games mp "
            "ON mp.player_id = g.player_id AND mp.nhl_game_id = g.nhl_game_id AND mp.situation = %s "
            "WHERE g.game_type = 2 AND g.started = 1 AND g.player_id IS NOT NULL",
            (np_.MONEYPUCK_SITUATION,)).fetchall(),
            columns=["player_id", "nhl_game_id", "team", "game_date", "x_goals", "goals"])
        mates = pd.DataFrame(conn.execute(
            "SELECT nhl_game_id, player_id_lo, player_id_hi, shared_seconds "
            "FROM nhl_shift_linemates WHERE (nhl_game_id / 10000) % 100 = 2").fetchall(),
            columns=["nhl_game_id", "player_id_lo", "player_id_hi", "shared_seconds"])
        refs = pd.DataFrame(conn.execute(
            "SELECT nhl_game_id, full_name FROM nhl_game_officials "
            "WHERE role = 'referee' AND game_type = 2").fetchall(),
            columns=["nhl_game_id", "full_name"])
        return skaters, teams, goalies, mates, refs
    finally:
        conn.close()


# The cuts asked for on the no-pace assists candidate. 0.18 is the live floor.
PACE_EV_CUTS = (0.12, 0.15, 0.18, 0.22)
# Same buckets as claimed_vs_realised. A bucket with no decisive rows is omitted.
RELIABILITY_EDGES = (
    (0.0, 0.3), (0.3, 0.4), (0.4, 0.5), (0.5, 0.55), (0.55, 0.6),
    (0.6, 0.65), (0.65, 0.7), (0.7, 0.8), (0.8, 1.01),
)


def _point_seasons(games: pd.DataFrame) -> list[int]:
    """Priced seasons the candidate walk-forward can score, including the one in progress."""
    have = set(int(s) for s in games.season.dropna().unique())
    seasons = [s for s in POINT_SEASONS if s in have]
    return seasons or list(SEASONS)


def reliability(b: pd.DataFrame) -> list[dict]:
    """Claimed P(side) against the hit rate, by bucket, on decisive rows."""
    d = _decisive(b)
    rows = []
    for lo, hi in RELIABILITY_EDGES:
        q = d[(d.p >= lo) & (d.p < hi)]
        if not len(q):
            continue
        claimed = float(q.p.mean())
        hit = float(q.won.mean())
        rows.append({
            "bucket": f"{lo:.2f}-{min(hi, 1.0):.2f}",
            "n": len(q),
            "claimed": round(claimed, 3),
            "hit": round(hit, 3),
            "gap": round(hit - claimed, 3),
        })
    return rows


def restrict_slate(left: pd.DataFrame, right: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep the player-games both frames can score. The quotes on those games stay."""
    keys = ["game_id", "pkey"]
    both = left[keys].drop_duplicates().merge(right[keys].drop_duplicates(), on=keys)
    return left.merge(both, on=keys), right.merge(both, on=keys)


def _pace_bets(sides_df: pd.DataFrame, cut: float) -> pd.DataFrame:
    """Unders only, best price, the -200 floor, no per-game cap. Assists' rule."""
    return card(sides_df, cut, ("under",), per_game=None)


def _with_price(label: str, b: pd.DataFrame) -> dict:
    row = _metric_row(label, b)
    if len(b):
        price = b.price.astype(float)
        row["med_price"] = int(price.median())
        row["shortest"] = int(price.min())
        row["share_le_-300"] = round(float((price <= -300).mean()), 4)
        row["share_le_-500"] = round(float((price <= -500).mean()), 4)
    return row


def _halves(label: str, b: pd.DataFrame) -> list[dict]:
    if len(b) < 2:
        return []
    ordered = b.sort_values(["game_date", "game_id", "pkey"])
    h = len(ordered) // 2
    return [
        _with_price(f"{label} early", ordered.iloc[:h]),
        _with_price(f"{label} late", ordered.iloc[h:]),
    ]


def pace_report(live: pd.DataFrame, cand: pd.DataFrame, floor: float,
                seasons: list[int]) -> str:
    """Live assists against the no-pace candidate.

    Own bets are each model on every player-game it can score. The same slate
    is the player-games both can score. Units at 1 unit risked, and at 1 unit
    to win with the risk capped at 3. The day interval resamples whole game days.
    """
    live_same, cand_same = restrict_slate(live, cand)
    universes = (
        ("live own", live),
        ("no-pace own", cand),
        ("live same slate", live_same),
        ("no-pace same slate", cand_same),
    )
    headline = []
    for name, sides_df in universes:
        headline.append(_with_price(f"{name} bets EV>={floor:.2f}", _pace_bets(sides_df, floor)))
        headline.append(_with_price(f"{name} every under", _population(sides_df, "under")))
        headline.append(_with_price(f"{name} overs EV>={floor:.2f}", card(sides_df, floor, ("over",))))
    keys = ["game_id", "pkey", "book", "line", "side"]
    live_bets = _pace_bets(live_same, floor)
    cand_bets = _pace_bets(cand_same, floor)
    both_keys = live_bets.merge(cand_bets[keys], on=keys, how="inner")
    headline.append(_with_price(f"same-slate bets both take, live p, EV>={floor:.2f}", both_keys))
    if len(both_keys):
        cand_both = both_keys[keys].merge(cand_same, on=keys, how="inner")
        headline.append(_with_price(
            f"same-slate bets both take, no-pace p, EV>={floor:.2f}", cand_both))
    cuts = []
    for cut in PACE_EV_CUTS:
        for name, sides_df in universes:
            cuts.append(_with_price(f"{name} EV>={cut:.2f}", _pace_bets(sides_df, cut)))
    seasons_rows = []
    halves = []
    for name, sides_df in universes:
        taken = _pace_bets(sides_df, floor)
        seasons_rows += _by_season(f"{name} bets EV>={floor:.2f}", taken, seasons)
        halves += _halves(f"{name} bets EV>={floor:.2f}", taken)
    reliable_blocks = []
    for name, frame in (
        (f"live same-slate bets EV>={floor:.2f}", live_bets),
        (f"no-pace same-slate bets EV>={floor:.2f}", cand_bets),
        ("live same-slate every under", _population(live_same, "under")),
        ("no-pace same-slate every under", _population(cand_same, "under")),
    ):
        rows = reliability(frame)
        reliable_blocks.append(name + "\n" + (pd.DataFrame(rows).to_string(index=False) if rows else "(none)"))
    live_players = live[["game_id", "pkey"]].drop_duplicates()
    cand_players = cand[["game_id", "pkey"]].drop_duplicates()
    both_players = live_players.merge(cand_players, on=["game_id", "pkey"])
    lines = [
        f"nhl_prop_assists no-team-pace candidate. USE_ASSISTS_NO_TEAM_PACE="
        f"{np_.USE_ASSISTS_NO_TEAM_PACE}. The card scores ASSISTS. Nothing here is registered.",
        f"unders only, no per-game cap, best EV, floor {FLOOR}, own probability, live EV cut {floor:.2f}.",
        "units_risked is 1 unit risked (a loss is -1). units_to_win is 1 unit to win, risk capped at 3.",
        "roi is the mean profit per bet. The 95% columns resample whole game days, 5000 draws, seed 7.",
        "brier and log_loss are on decisive rows. Lines are x.5 in this market, so a push is rare.",
        f"priced player-games live can score {len(live_players):,}; no-pace {len(cand_players):,}; "
        f"both {len(both_players):,}.",
        f"same-slate bets live {len(live_bets):,}; no-pace {len(cand_bets):,}; both take {len(both_keys):,}.",
        "",
        "HEADLINE",
        pd.DataFrame(headline).to_string(index=False),
        "",
        "EV CUTS 0.12 / 0.15 / 0.18 / 0.22",
        pd.DataFrame(cuts).to_string(index=False),
        "",
        "BY SEASON",
        pd.DataFrame(seasons_rows).to_string(index=False),
        "",
        "EARLY / LATE, bets ordered by date",
        pd.DataFrame(halves).to_string(index=False) if halves else "(none)",
        "",
        "RELIABILITY",
        "\n\n".join(reliable_blocks),
        "",
        "COMPACT",
    ]
    for row in headline + cuts + seasons_rows + halves:
        lines.append(
            f"{row['set']}: rows={row['rows']} units_risked={row.get('units_risked')} "
            f"roi_risked={row.get('roi_risked')} ci_risked={row.get('95% risked')} "
            f"units_to_win={row.get('units_to_win')} roi_to_win={row.get('roi_to_win')} "
            f"ci_to_win={row.get('95% to win')} brier={row.get('brier')} "
            f"log_loss={row.get('log_loss')} cal_err={row.get('cal_err')} "
            f"claimed={row.get('claimed')} hit={row.get('hit')} "
            f"med_price={row.get('med_price')}"
        )
    return "\n".join(lines)


def _run_assists_no_team_pace(a) -> None:
    """Walk the no-pace assists spec forward and compare it with live assists.

    Each season is fit only on earlier seasons. The live spec is fit on the
    live feature list. The candidate is fit without team pace and team xG for.
    Neither fit is stored.
    """
    spec = np_.assists_no_team_pace_spec()
    if np_.USE_ASSISTS_NO_TEAM_PACE:
        print("USE_ASSISTS_NO_TEAM_PACE is true in this process. The card still scores ASSISTS. "
              "This run does not register an artifact and does not change the live spec.")
    if spec is np_.ASSISTS or spec in np_.LIVE or spec.features == np_.ASSISTS.features:
        raise SystemExit("the no-pace spec is the live spec")
    if any(f in spec.features for f in np_.TEAM_PACE_FEATURES):
        raise SystemExit("the no-pace spec still carries team pace")
    if set(np_.ASSISTS.features) - set(spec.features):
        raise SystemExit("the no-pace spec dropped a live feature")
    data = load(a.cache, POINT_SEASONS, markets=[np_.ASSISTS.market])
    seasons = _point_seasons(data["games"])
    skaters, mp_teams, goalies, mates, refs = load_points_inputs(a.cache)
    base = np_.build_frame(np_.ASSISTS, data["skater"], data["teams"])
    framed = np_.add_points_features(base, skaters, mp_teams, goalies, mates, refs, data["teams"])
    print(f"no-pace features: {', '.join(spec.features)}")
    print(f"dropped: {', '.join(np_.TEAM_PACE_FEATURES)}")
    print(f"seasons {[_season_name(s) for s in seasons]}; flag USE_ASSISTS_NO_TEAM_PACE="
          f"{np_.USE_ASSISTS_NO_TEAM_PACE}")
    live = report(np_.ASSISTS, data, base, None, seasons, quiet=True)
    cand = report(spec, data, framed, None, seasons, quiet=True)
    floor = float(config.MODEL_OWN_EV_FLOOR["nhl_prop_assists"])
    text = pace_report(live, cand, floor, seasons)
    print(f"\n{'=' * 100}\nNO-TEAM-PACE ASSISTS\n{'=' * 100}\n{text}")
    if a.dump:
        out = Path(a.dump)
        out.mkdir(parents=True, exist_ok=True)
        live.assign(model_id="nhl_prop_assists").to_pickle(out / "sides_nhl_prop_assists.pkl")
        cand.assign(model_id="nhl_prop_assists_no_team_pace").to_pickle(
            out / "sides_nhl_prop_assists_no_team_pace.pkl")
    if a.results:
        Path(a.results).write_text(text + "\n", encoding="utf-8")


def _run_moneypuck(a) -> None:
    targets = []
    if a.model in (None, "nhl_prop_points"):
        targets.append(np_.points_spec(False))
    if a.model in (None, "nhl_prop_assists"):
        targets.append(np_.ASSISTS)
    data = load(a.cache, POINT_SEASONS, markets=[s.market for s in targets])
    seasons = _point_seasons(data["games"])
    skaters, mp_teams, goalies, mates, refs = load_points_inputs(a.cache)
    base = np_.build_frame(np_.ASSISTS, data["skater"], data["teams"])
    framed = np_.add_points_features(base, skaters, mp_teams, goalies, mates, refs, data["teams"])
    required = [f for f in np_.MONEYPUCK_POINTS_FEATURES if f not in np_.POINTS_OPTIONAL_FEATURES]
    optional = list(np_.POINTS_OPTIONAL_FEATURES)
    print(f"candidate features on {int(framed[required].notna().all(axis=1).sum()):,} "
          f"of {len(framed):,} skater-games "
          f"(shift and referee features on {int(framed[optional].notna().all(axis=1).sum()):,}); "
          f"linemate pairs {len(mates):,}; referees {len(refs):,}; "
          f"seasons {[_season_name(s) for s in seasons]}")
    blocks = []
    for base_spec in targets:
        maker = np_.points_spec if base_spec.model_id == np_.POINTS.model_id else np_.assists_spec
        spec = maker(True)
        current = report(base_spec, data, base, a.dump, seasons)
        enhanced = report(spec, data, framed, a.dump, seasons)
        ablations = []
        for name, drop in POINT_GROUPS:
            held = maker(True, drop)
            ablations.append((name, report(held, data, framed, None, seasons, quiet=True)))
        floor = float(config.MODEL_OWN_EV_FLOOR.get(base_spec.model_id, 0.18))
        text = compare_market(base_spec, current, enhanced, floor, seasons, ablations)
        print(f"\n{'=' * 100}\nCOMPARISON {base_spec.model_id}\n{'=' * 100}\n{text}")
        blocks.append(text)
    if a.results:
        Path(a.results).write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", default=None,
                    choices=sorted(np_.SPECS) + [np_.POINTS.model_id])
    ap.add_argument("--cache", default=None, help="a folder of pickles to read instead of the database")
    ap.add_argument("--dump", default=None, help="write the bet-level rows to this folder")
    ap.add_argument("--moneypuck", action="store_true",
                    help="walk-forward points and assists with the candidate features and compare them to the current features")
    ap.add_argument("--assists-no-team-pace", action="store_true",
                    help="walk-forward the assists candidate without team pace and compare it to live assists")
    ap.add_argument("--results", default=None, help="write the comparison here")
    a = ap.parse_args()
    if a.moneypuck and a.assists_no_team_pace:
        raise SystemExit("run one backtest at a time")
    if a.moneypuck and a.model not in (None, "nhl_prop_assists", "nhl_prop_points"):
        raise SystemExit("--moneypuck is the points and assists models only")
    if a.assists_no_team_pace and a.model not in (None, "nhl_prop_assists"):
        raise SystemExit("--assists-no-team-pace is the assists model only")
    if a.assists_no_team_pace:
        _run_assists_no_team_pace(a)
        return
    if a.moneypuck:
        _run_moneypuck(a)
        return
    if a.model == np_.POINTS.model_id:
        raise SystemExit("nhl_prop_points is not a live model; run it with --moneypuck")
    data = load(a.cache)
    frames: dict[str, pd.DataFrame] = {}
    for spec in ([np_.SPECS[a.model]] if a.model else np_.SPECS.values()):
        if spec.kind not in frames:
            frames[spec.kind] = np_.build_frame(spec, data[spec.kind], data["teams"])
        report(spec, data, frames[spec.kind], a.dump)


if __name__ == "__main__":
    main()
