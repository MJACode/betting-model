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
    python -m scripts.nhl_prop_backtest --moneypuck          # shots candidate features, not live
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
# three seasons the live artifacts were walked forward on. The shots candidate
# adds it when the log and the prices have it.
SHOT_SEASONS = [2024, 2025, 2026, 2027]
EV_CUTS = (0.0, 0.03, 0.05, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20)
BORROWED = {"method": "platt", "a": 1.0, "b": -0.259947}     # what a no-record model is given
COHERENT_SUM = (1.00, 1.15)
FLOOR = -200


# ── data ─────────────────────────────────────────────────────────────────────

def load(cache: str | None, seasons: list[int] | None = None) -> dict:
    """Players, teams, games and prices -- from the database, or from a folder of pickles.

    `seasons` limits which games' prices are read. The default is the three
    seasons the live report scores. A cache folder is read whole.
    """
    seasons = SEASONS if seasons is None else list(seasons)
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
    live_features = spec.features == np_.SPECS[spec.model_id].features
    print(f"\n{'=' * 100}\n{spec.model_id}  ({spec.market}, settles on {spec.stat}; "
          f"{'LIVE' if live_features else 'CANDIDATE FEATURES, not live'})\n{'=' * 100}")
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
    floor = config.MODEL_OWN_EV_FLOOR.get(spec.model_id, 0.10)
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
    """One quote per player-game on this side: the best EV, no cut and no price floor.

    Not the three-a-game cap. This is the scored set a cut is drawn from.
    """
    return card(s, -9.0, (side,), floor=None)


def _metric_row(label: str, b: pd.DataFrame) -> dict:
    d = _decisive(b)
    row = {
        "set": label,
        "rows": len(b),
        "decisive": len(d),
        "pushes": int((b.actual == b.line).sum()) if len(b) else 0,
        "log_loss": None if not len(d) else round(log_loss(b), 4),
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
        rows.append(row)
    return rows


# Candidate groups, removed one at a time. Linemate quality is built from the
# mate's prior MoneyPuck xG, so dropping the individual columns does not take
# that xG out of lm_q / pp_unit.
SHOT_GROUPS = (
    ("without individual xG / attempts / high-danger",
     ("mp_xg_l", "mp_xg_s", "mp_att_l", "mp_att_s", "mp_hd_l", "mp_hd_s")),
    ("without TOI and PP TOI trends", ("toi_trend", "pp_toi_trend")),
    ("without linemates and PP deployment",
     ("lm_q_l", "lm_q_s", "pp_share_l", "pp_share_s", "pp_unit_l", "pp_unit_s")),
    ("without opponent shot suppression", ("opp_mp_sa", "opp_mp_xga")),
)


def compare_shots(base: pd.DataFrame, mp: pd.DataFrame, floor: float,
                  seasons: list[int], ablations: list[tuple[str, pd.DataFrame]] | None = None) -> str:
    """Current shots features against the candidate features, on one price set.

    The live rule is unders only, at most three a game, price floor -200, the
    model's own probability. Overs are scored beside that because the question
    was whether the live model takes both sides. It does not.
    """
    cap = np_.SHOTS.max_per_game
    base_bets = card(base, floor, np_.SHOTS.sides, per_game=cap)
    mp_bets = card(mp, floor, np_.SHOTS.sides, per_game=cap)
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
        _metric_row(f"current overs at EV>={floor:.2f}, no cap",
                    card(base, floor, ("over",))),
        _metric_row(f"candidate overs at EV>={floor:.2f}, no cap",
                    card(mp, floor, ("over",))),
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
        for name, s in (("current", base), ("candidate", mp)):
            b = card(s, cut, np_.SHOTS.sides, per_game=cap)
            neigh.append({"model": name, "EV>=": cut,
                          **{k: v for k, v in _metric_row(name, b).items() if k != "set"}})
    ablate_rows = []
    for name, sides in ablations or []:
        b = card(sides, floor, np_.SHOTS.sides, per_game=cap)
        ablate_rows.append(_metric_row(f"{name}, EV>={floor:.2f}", b))
        ablate_rows.append(_metric_row(f"{name}, every under", _population(sides, "under")))
    lines = [
        f"live rule: unders only, at most {cap} a game, best EV, floor {FLOOR}, "
        f"own probability, EV>={floor:.2f}",
        "overs are not a live side; the over rows are the side the rule does not bet",
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
        lines += ["", "Each candidate group removed, same prices, live rule at the live cut "
                  "and every best-EV under.",
                  pd.DataFrame(ablate_rows).to_string(index=False)]
    return "\n".join(lines)


def load_shots_inputs(cache: str | None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """MoneyPuck skater and team rows, and regular-season shift-chart pairs.

    Prior-game features are built later, from these. Playoff pairs are left
    out: the skater log the model trains on is regular season, and a playoff
    chart is not a regular-season input.
    """
    if cache:
        c = Path(cache)
        return (pd.read_pickle(c / "moneypuck_skaters.pkl"),
                pd.read_pickle(c / "moneypuck_teams.pkl"),
                pd.read_pickle(c / "shift_linemates.pkl"))
    from data.db import get_connection
    conn = get_connection()
    try:
        skaters = pd.DataFrame(conn.execute(
            "SELECT player_id, nhl_game_id, i_f_x_goals, i_f_shot_attempts, i_f_high_danger_shots "
            "FROM moneypuck_skater_games WHERE situation = %s",
            (np_.MONEYPUCK_SITUATION,)).fetchall(),
            columns=["player_id", "nhl_game_id", "i_f_x_goals", "i_f_shot_attempts", "i_f_high_danger_shots"])
        teams = pd.DataFrame(conn.execute(
            "SELECT nhl_game_id, team_abbr, game_date, shots_on_goal_against, x_goals_against "
            "FROM moneypuck_team_games WHERE situation = %s",
            (np_.MONEYPUCK_SITUATION,)).fetchall(),
            columns=["nhl_game_id", "team", "game_date", "shots_on_goal_against", "x_goals_against"])
        mates = pd.DataFrame(conn.execute(
            "SELECT nhl_game_id, team_abbr, player_id_lo, player_id_hi, shared_seconds "
            "FROM nhl_shift_linemates WHERE (nhl_game_id / 10000) % 100 = 2").fetchall(),
            columns=["nhl_game_id", "team", "player_id_lo", "player_id_hi", "shared_seconds"])
        return skaters, teams, mates
    finally:
        conn.close()


def _shots_seasons(games: pd.DataFrame) -> list[int]:
    """Priced seasons the candidate walk-forward can score, including the one in progress."""
    have = set(int(s) for s in games.season.dropna().unique())
    seasons = [s for s in SHOT_SEASONS if s in have]
    return seasons or list(SEASONS)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", default=None, choices=sorted(np_.SPECS))
    ap.add_argument("--cache", default=None, help="a folder of pickles to read instead of the database")
    ap.add_argument("--dump", default=None, help="write the bet-level rows to this folder")
    ap.add_argument("--moneypuck", action="store_true",
                    help="walk-forward nhl_prop_shots_on_goal with the candidate features and compare it to the live features")
    ap.add_argument("--results", default=None, help="write the shots comparison here")
    a = ap.parse_args()
    if a.moneypuck and a.model not in (None, "nhl_prop_shots_on_goal"):
        raise SystemExit("--moneypuck is the shots-on-goal model only")
    if a.moneypuck:
        data = load(a.cache, SHOT_SEASONS)
        seasons = _shots_seasons(data["games"])
        spec = np_.shots_spec(True)
        skaters, mp_teams, mates = load_shots_inputs(a.cache)
        base = np_.build_frame(np_.SHOTS, data["skater"], data["teams"])
        framed = np_.add_moneypuck_skater_features(base, skaters, mp_teams, mates)
        required = [f for f in np_.MONEYPUCK_SHOT_FEATURES if f not in np_.SHIFT_OPTIONAL_FEATURES]
        print(f"candidate features on {int(framed[required].notna().all(axis=1).sum()):,} "
              f"of {len(framed):,} skater-games "
              f"(shift-chart features on {int(framed[list(np_.SHIFT_OPTIONAL_FEATURES)].notna().all(axis=1).sum()):,}); "
              f"linemate pairs {len(mates):,}; seasons {[_season_name(s) for s in seasons]}")
        current = report(np_.SHOTS, data, base, a.dump, seasons)
        enhanced = report(spec, data, framed, a.dump, seasons)
        ablations = []
        for name, drop in SHOT_GROUPS:
            held = np_.shots_spec(True, drop)
            ablations.append((name, report(held, data, framed, None, seasons, quiet=True)))
        floor = float(config.MODEL_OWN_EV_FLOOR["nhl_prop_shots_on_goal"])
        text = compare_shots(current, enhanced, floor, seasons, ablations)
        print(f"\n{'=' * 100}\nCOMPARISON\n{'=' * 100}\n{text}")
        if a.results:
            Path(a.results).write_text(text + "\n", encoding="utf-8")
        return
    data = load(a.cache)
    frames: dict[str, pd.DataFrame] = {}
    for spec in ([np_.SPECS[a.model]] if a.model else np_.SPECS.values()):
        if spec.kind not in frames:
            frames[spec.kind] = np_.build_frame(spec, data[spec.kind], data["teams"])
        report(spec, data, frames[spec.kind], a.dump)


if __name__ == "__main__":
    main()
