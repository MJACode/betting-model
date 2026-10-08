"""The four NHL prop models graded TOGETHER, in expected units a season: every cap the card could run.

WHY. The card (scripts/nhl_props_card.py) now writes at most one NHL prop bet a
game and two a night, at EV >= 0.18 (mike, 2026-10-02 and 10-03). Those were
graded on return per bet. Expected value is maximised on units a season, and a
cap that lifts the return per bet can still cost units, so this prints both,
for every floor x per-game cap x per-night cap, from the production backtest
code (scripts/nhl_prop_backtest.py), walk-forward on the three priced seasons.

WHAT ELSE IT PRINTS
  * FanDuel shopped or not (models.nhl_props.EXCLUDED_BOOKS). The bought
    history has mispaired FanDuel quotes; the coherent-quote filter drops the
    ones it can see, so the FanDuel rows carry that caveat and are shown apart.
  * assists on both sides (the lab found its edge was about half overs).
  * 2026-27 so far: every candidate the card's rule finds at a game's FIRST
    stored price (the open) and at its LAST (the close, inside 70 minutes of
    puck drop) -- whether deciding at the open beats the close on price, and
    what the same bets returned. One price a game in the history, so this part
    is the live season only.

READ-ONLY. Nothing is written anywhere; run it on the worker with the
`nhl_research` job (tracking/job_queue.py), which holds DATABASE_URL.

    python -m scripts.nhl_prop_ev_lab
"""
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config  # noqa: E402
import models.nhl_props as np_  # noqa: E402
import scripts.nhl_prop_backtest as bt  # noqa: E402

pd.set_option("display.width", 320)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 400)

N_SEASONS = len(bt.SEASONS)
FLOORS = (0.06, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25)
PER_GAME = (1, 2, 3, None)
PER_NIGHT = (2, 3, 4, 6, None)
PRICE_FLOOR = bt.FLOOR
LIVE_SEASON = 2027
KEEP = ["model_id", "game_id", "pkey", "game_date", "season", "side", "price", "p", "ev",
        "profit", "won", "book", "line"]


# ── the three priced seasons ─────────────────────────────────────────────────

def engine_sides(data: dict, frames: dict) -> dict[str, pd.DataFrame]:
    """Every priced side at every bettable book (FanDuel included), per Spec model."""
    out = {}
    for spec in np_.SPECS.values():
        if spec.kind not in frames:
            frames[spec.kind] = np_.build_frame(spec, data[spec.kind], data["teams"])
        px = bt.prices(data, spec)
        pred = bt.predictions(spec, frames[spec.kind])
        m = px.merge(pred.drop(columns=["season"]), on=["game_id", "pkey"], how="inner")
        m = m[m.book.isin(list(config.BEST_LINE_BOOKMAKERS))]
        s = bt.sides(m)
        s["model_id"] = spec.model_id
        out[spec.model_id] = s
    return out


def blocked_sides() -> pd.DataFrame:
    """The blocked-shots model, DraftKings only, as it runs live."""
    import models.nhl_prop_blocked_shots as bs
    import scripts.nhl_prop_blocked_shots_backtest as bsb
    from data.db import get_connection
    conn = get_connection()
    try:
        frame = bs.build_frame(bs.load_skaters(conn), bs.load_teams(conn))
        s = bsb.bets(frame, conn)
    finally:
        conn.close()
    return s.assign(model_id="nhl_prop_blocked_shots", book=bs.BOOK, won=(s.profit > 0).astype(int))


def best_per_player(s: pd.DataFrame, books, sides, floor=PRICE_FLOOR) -> pd.DataFrame:
    """One candidate per model per player-game: the best EV among the books and sides allowed."""
    b = s[s.book.isin(list(books)) & s.side.isin(list(sides)) & (s.price >= floor) & (s.ev >= min(FLOORS))]
    rank = {bk: i for i, bk in enumerate(books)}
    b = b.assign(_r=b.book.map(rank).fillna(len(rank)))
    b = (b.sort_values(["ev", "_r"], ascending=[False, True], kind="mergesort")
         .drop_duplicates(["game_id", "pkey"]).drop(columns="_r"))
    b = b.assign(game_date=pd.to_datetime(b.game_date))
    return b[KEEP]


def regime(c: pd.DataFrame, floor: float, per_game, per_night) -> pd.DataFrame:
    """The card's order: best EV first, one-per-game, then the nightly limit."""
    b = c[c.ev >= floor].sort_values(["ev", "model_id", "pkey"], ascending=[False, True, True],
                                     kind="mergesort")
    if per_game is not None:
        b = b.groupby("game_id", sort=False).head(per_game)
    if per_night is not None:
        b = b.groupby("game_date", sort=False).head(per_night)
    return b.sort_values(["game_date", "game_id", "pkey"])


def summary(label: dict, b: pd.DataFrame) -> dict:
    if len(b) < 30:
        return {**label, "bets": len(b)}
    p = b.profit.values
    nights = b.groupby("game_date").profit.sum().sort_index()
    cum = nights.cumsum()
    r = {**label, "bets": len(b), "bets/season": round(len(b) / N_SEASONS),
         "units": round(float(p.sum()), 1), "units/season": round(float(p.sum()) / N_SEASONS, 1),
         "roi%": round(float(p.mean()) * 100, 2), "95% by day": bt.day_interval(b),
         "bets/night": round(float(b.groupby("game_date").size().mean()), 1),
         "max/game": int(b.groupby("game_id").size().max()),
         "worst night": round(float(nights.min()), 1),
         "max drawdown": round(float((cum.cummax() - cum).max()), 1)}
    for season in bt.SEASONS:
        q = b[b.season == season].profit.values
        r[f"{season - 1}-{str(season)[2:]}"] = (f"{q.mean() * 100:+.1f}% ({len(q)})" if len(q) >= 30
                                                else f"({len(q)})")
    return r


def show(title: str, rows: list[dict]) -> None:
    print(f"\n### {title}\n")
    print(pd.DataFrame(rows).to_string(index=False))


def history() -> None:
    data = bt.load(None)
    frames: dict = {}
    sides = engine_sides(data, frames)
    blocked = blocked_sides()
    live_books = tuple(np_.books())
    with_fd = tuple(config.BEST_LINE_BOOKMAKERS)
    print(f"\nbooks the card shops: {list(live_books)}; FanDuel in the bettable set: {'fanduel' in with_fd}")

    def pool(books, assists_sides=("under",)) -> pd.DataFrame:
        parts = [best_per_player(blocked, ("draftkings",), ("under",))]
        for mid, s in sides.items():
            allowed = assists_sides if mid == "nhl_prop_assists" else np_.SPECS[mid].sides
            parts.append(best_per_player(s, books, allowed))
        return pd.concat(parts, ignore_index=True)

    live = pool(live_books)
    print(f"candidates at EV >= {min(FLOORS)}: {len(live):,} "
          f"({live.groupby('model_id').size().to_dict()}); priced game days {live.game_date.nunique():,}")

    show("TODAY'S RULE, reproduced: EV >= 0.18, one a game, two a night (live order)",
         [summary({"rule": "today"}, regime(live, 0.18, 1, 2)),
          summary({"rule": "one a game, no nightly limit"}, regime(live, 0.18, 1, None))])
    show("Floor x bets a game, no nightly limit (units/season is what expected value is maximised on)",
         [summary({"EV>=": f, "per game": g if g else "none"}, regime(live, f, g, None))
          for f in FLOORS for g in PER_GAME])
    show("Floor x bets a night, one a game",
         [summary({"EV>=": f, "per night": n if n else "none"}, regime(live, f, 1, n))
          for f in FLOORS for n in PER_NIGHT])
    show("Each model alone, no cap (its own neighbourhood)",
         [summary({"model": m, "EV>=": f}, regime(live[live.model_id == m], f, None, None))
          for m in sorted(live.model_id.unique()) for f in (0.06, 0.10, 0.15, 0.18, 0.25)])

    fd = pool(with_fd)
    rows = []
    for f, g, n in ((0.10, None, None), (0.18, None, None), (0.18, 1, None), (0.18, 1, 2)):
        a, b = regime(live, f, g, n), regime(fd, f, g, n)
        rows += [summary({"books": "FanDuel out (today)", "EV>=": f, "per game": g, "per night": n}, a),
                 summary({"books": "FanDuel in", "EV>=": f, "per game": g, "per night": n}, b),
                 summary({"books": "FanDuel in: bets decided AT FanDuel", "EV>=": f, "per game": g,
                          "per night": n}, b[b.book == "fanduel"])]
    show("FanDuel shopped or not (its history carries mispaired quotes the filter cannot see)", rows)

    both = pool(live_books, assists_sides=("over", "under"))
    a = both[both.model_id == "nhl_prop_assists"]
    show("Assists on both sides, best price, no cap",
         [summary({"side": sd, "EV>=": f}, regime(a[a.side.isin(sd.split("+"))], f, None, None))
          for sd in ("under", "over", "over+under") for f in (0.06, 0.10, 0.15, 0.18)])
    show("All four with assists on both sides",
         [summary({"EV>=": f, "per game": g, "per night": n}, regime(both, f, g, n))
          for f, g, n in ((0.18, 1, 2), (0.18, 1, None), (0.10, None, None))])


# ── 2026-27: deciding at the open against deciding at the close ──────────────

def live_season() -> None:
    from data.db import get_connection
    conn = get_connection()
    try:
        games = pd.DataFrame(conn.execute(
            "SELECT game_id, season, commence_time FROM games WHERE sport = 'NHL' AND season = %s",
            (LIVE_SEASON,)).fetchall(), columns=["game_id", "season", "commence_time"])
        now = datetime.now(timezone.utc)
        games = games[pd.to_datetime(games.commence_time, utc=True) < now]
        markets = [s.market for s in np_.SPECS.values()]
        rows = conn.execute(
            "SELECT game_id, player_name, market, bookmaker, line, over_price, under_price, snapshot_at "
            "FROM player_prop_odds WHERE game_id = ANY(%s) AND market = ANY(%s) AND snapshot_type = 'open'",
            (sorted(games.game_id), markets)).fetchall() if len(games) else []
        players = {k: np_.load_players(conn, k) for k in ("skater", "goalie")}
        teams = np_.load_teams(conn)
    finally:
        conn.close()
    px = pd.DataFrame(rows, columns=["game_id", "player", "market", "book", "line", "over", "under", "snap"])
    print(f"\n{'=' * 100}\n2026-27 SO FAR: {len(games)} games started, {len(px):,} prop quotes\n{'=' * 100}")
    if px.empty:
        return
    for c in ("line", "over", "under"):
        px[c] = pd.to_numeric(px[c], errors="coerce")
    px = px.merge(games, on="game_id")
    px["snap_t"] = pd.to_datetime(px.snap, utc=True)
    px = px[px.snap_t <= pd.to_datetime(px.commence_time, utc=True)]
    tot = px.over.map(np_.implied, na_action="ignore") + px.under.map(np_.implied, na_action="ignore")
    px = px[~(px.over.notna() & px.under.notna() & ~tot.between(*bt.COHERENT_SUM)) & px.line.notna()]
    px["pkey"] = px.player.map(np_.name_key)
    first = px.groupby("game_id").snap_t.transform("min")
    last = px.groupby("game_id").snap_t.transform("max")
    px["when"] = np.where(px.snap_t == first, "open", np.where(px.snap_t == last, "close", "middle"))
    px["hours_before"] = (pd.to_datetime(px.commence_time, utc=True) - px.snap_t).dt.total_seconds() / 3600
    print("hours before puck drop, median: " + str(px.groupby("when").hours_before.median().round(2).to_dict()))

    allc = []
    for spec in np_.SPECS.values():
        frame = np_.build_frame(spec, players[spec.kind], teams)
        fitted = np_.fit(spec, frame, LIVE_SEASON - 1)
        te = np_.usable(spec, frame[(frame.season == LIVE_SEASON) & ~frame.upcoming]).dropna(subset=[spec.stat]).copy()
        te = te[~bt.namesakes(te, frame, LIVE_SEASON)]
        if te.empty:
            print(f"{spec.model_id}: no scored 2026-27 rows yet")
            continue
        te["mu"] = np_.predict_mean(spec, fitted, te)
        te["alpha"] = fitted["dispersion"]
        pred = te[["game_id", "pkey", "game_date", "mu", "alpha", spec.stat]].rename(columns={spec.stat: "actual"})
        q = px[(px.market == spec.market) & px.book.isin(list(np_.books()))]
        m = q.merge(pred, on=["game_id", "pkey"], how="inner")
        if m.empty:
            continue
        s = bt.sides(m)
        s = s[s.side.isin(spec.sides) & (s.price >= PRICE_FLOOR)]
        s["model_id"] = spec.model_id
        # the same book's close at the same line and side, de-vigged where it is two-way
        cl = m[m.when == "close"][["game_id", "pkey", "book", "line", "over", "under"]].rename(
            columns={"over": "c_over", "under": "c_under"})
        s = s.merge(cl, on=["game_id", "pkey", "book", "line"], how="left")
        s["c_price"] = np.where(s.side == "under", s.c_under, s.c_over)
        imp = lambda col: s[col].map(np_.implied, na_action="ignore")  # noqa: E731
        fair_close = np.where(s.side == "under", imp("c_under"), imp("c_over")) / (imp("c_under") + imp("c_over"))
        s["clv_pp"] = (fair_close - s.price.map(np_.implied)) * 100
        s["profit_close"] = np.where(s.actual == s.line, 0.0,
                                     np.where(s.won == 1, s.c_price.map(np_.win_per_unit, na_action="ignore"), -1.0))
        allc.append(s)
    if not allc:
        return
    s = pd.concat(allc, ignore_index=True)
    rows = []
    for when in ("open", "close"):
        w = s[s.when == when]
        for cut in (0.06, 0.10, 0.18):
            b = (w[w.ev >= cut].sort_values("ev", ascending=False)
                 .drop_duplicates(["model_id", "game_id", "pkey"]))
            if b.empty:
                continue
            has_close = b.c_price.notna()
            has_clv = b.clv_pp.notna()
            rows.append({"decided at": when, "EV>=": cut, "candidates": len(b),
                         "units at its price": round(float(b.profit.sum()), 1),
                         "roi%": round(float(b.profit.mean()) * 100, 1),
                         "same book+line at close": int(has_close.sum()),
                         "two-way close": int(has_clv.sum()),
                         "mean CLV pp vs that close (no-vig)": round(float(b.clv_pp[has_clv].mean()), 2),
                         "share CLV > 0": round(float((b.clv_pp[has_clv] > 0).mean()), 2),
                         "units if taken at the close price": round(float(b.profit_close[has_close].sum()), 1),
                         "units at its own price, same bets": round(float(b.profit[has_close].sum()), 1)})
    show("Every candidate the card's rule finds, decided at the OPEN vs at the CLOSE (unders, live books, floor -200)",
         rows)
    for cut in (0.10, 0.18):
        o = s[(s.when == "open") & (s.ev >= cut)].drop_duplicates(["model_id", "game_id", "pkey"])
        c = s[(s.when == "close") & (s.ev >= cut)].drop_duplicates(["model_id", "game_id", "pkey"])
        ko, kc = set(zip(o.model_id, o.game_id, o.pkey)), set(zip(c.model_id, c.game_id, c.pkey))
        print(f"EV >= {cut}: {len(ko)} at the open, {len(kc)} at the close, {len(ko & kc)} at both; "
              f"{len(kc - ko)} qualify only at the close, {len(ko - kc)} only at the open")
    show("By model, EV >= 0.10, decided at the open",
         [{"model": mid, "candidates": len(g), "roi%": round(float(g.profit.mean()) * 100, 1),
           "mean CLV pp": round(float(g.clv_pp.mean()), 2) if g.clv_pp.notna().any() else None}
          for mid, g in s[(s.when == "open") & (s.ev >= 0.10)].sort_values("ev", ascending=False)
          .drop_duplicates(["model_id", "game_id", "pkey"]).groupby("model_id")])
    print("\nA bet decided AT the close shows minus half the margin against its own no-vig close by "
          "construction; the comparison that matters is the open rows' CLV and the 'units if taken at "
          "the close price' column beside 'units at its own price'.")


def main() -> None:
    history()
    live_season()


if __name__ == "__main__":
    main()
