"""NHL moneyline, no model: a bettable book's price against Pinnacle's fair price.

`scripts/nhl_underdog_grid.py` found one positive grid in six seasons of NHL
moneylines: take the best price among the books a member can bet whenever it
beats Pinnacle's no-vig probability. This is the test a rule has to pass before
it is allowed to write a pick: the same rule at a different time of day, at one
book, with each book removed, with the two quotes forced to be simultaneous,
and graded against where Pinnacle CLOSED rather than against results alone.

THE RULE. For each side of a game: EV = Pinnacle's no-vig probability x the
decimal price at the best bettable book - 1. Bet the side with the larger EV
when it clears the cut. One bet a game, one unit.

PRICES. `odds.source = 'odds_api_historical'`, 2020-21 -> 2025-26: every book's
FIRST pre-game quote (the 16:00Z game-day snapshot, "open") and LAST (the
start-hour snapshot, "close"). A soft quote is used only when it was taken
within MAX_GAP_S of Pinnacle's.

    python -m scripts.nhl_moneyline_market_lab
"""
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config  # noqa: E402
from data.db import get_connection  # noqa: E402
from scripts.nhl_market_lab import novig, summarise, win_per_unit  # noqa: E402

pd.set_option("display.width", 260)
FEED = "odds_api_historical"
SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
SHARP = "pinnacle"
BETTABLE = [b for b in config.BEST_LINE_BOOKMAKERS if b != SHARP]
CUTS = (0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08)
MAX_GAP_S = 300.0


def _ts(v):
    return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(timezone.utc)


def load(conn) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(games, quotes): one row per game; one row per game x book x {open, close}."""
    games = conn.execute(
        "SELECT game_id, season, game_date, commence_time, home_score, away_score FROM games "
        "WHERE sport = 'NHL' AND season = ANY(%s) AND home_score IS NOT NULL AND commence_time IS NOT NULL",
        (SEASONS,)).fetchall()
    start = {g[0]: _ts(g[3]) for g in games}
    ids = sorted(start)
    rows = []
    for i in range(0, len(ids), 300):                    # by game id: the table is indexed on it
        rows += conn.execute(
            "SELECT game_id, bookmaker, snapshot_at, home_price, away_price FROM odds "
            "WHERE game_id = ANY(%s) AND source = %s AND snapshot_type = 'open' AND market = 'h2h'",
            (ids[i:i + 300], FEED)).fetchall()
    px = pd.DataFrame(rows, columns=["game_id", "book", "snap", "hp", "ap"])
    px["snap"] = px.snap.map(_ts)
    px["hp"], px["ap"] = pd.to_numeric(px.hp), pd.to_numeric(px.ap)
    px = px.dropna(subset=["hp", "ap"])
    px = px[[s <= start[g] for g, s in zip(px.game_id, px.snap)]].sort_values(["game_id", "book", "snap"])
    first = px.groupby(["game_id", "book"], sort=False).first().reset_index().assign(when="open")
    last = px.groupby(["game_id", "book"], sort=False).last().reset_index().assign(when="close")
    gm = pd.DataFrame(games, columns=["game_id", "season", "gdate", "commence", "hs", "as_"])
    gm["hs"], gm["as_"] = pd.to_numeric(gm.hs), pd.to_numeric(gm.as_)
    return gm.sort_values(["gdate", "game_id"]).reset_index(drop=True), pd.concat([first, last], ignore_index=True)


def candidates(gm: pd.DataFrame, q: pd.DataFrame, when: str, books: list[str],
               simultaneous: bool = True) -> pd.DataFrame:
    """One row per game: the better-EV side at the best price among `books`, decided at `when`."""
    t = q[q.when == when]
    pin = t[t.book == SHARP].set_index("game_id")
    pin_close = q[(q.when == "close") & (q.book == SHARP)].set_index("game_id")
    soft = t[t.book.isin(books)]
    out = []
    for gid, g in soft.groupby("game_id", sort=False):
        if gid not in pin.index:
            continue
        p = pin.loc[gid]
        if simultaneous:
            g = g[(g.snap - p.snap).abs().dt.total_seconds() <= MAX_GAP_S]
            if g.empty:
                continue
        fair_home = novig(float(p.hp), float(p.ap))
        best = None
        for side, col, fair in (("home", "hp", fair_home), ("away", "ap", 1 - fair_home)):
            i = g[col].idxmax()
            price = float(g.loc[i, col])
            ev = fair * (1 + win_per_unit(price)) - 1
            if best is None or ev > best["ev"]:
                best = {"game_id": gid, "side": side, "price": price, "book": g.loc[i, "book"],
                        "fair": fair, "ev": ev, "n_books": len(g)}
        if gid in pin_close.index:
            c = pin_close.loc[gid]
            fc = novig(float(c.hp), float(c.ap))
            fair_close = fc if best["side"] == "home" else 1 - fc
            best["ev_close"] = fair_close * (1 + win_per_unit(best["price"])) - 1
            best["clv"] = fair_close - best["fair"]
        out.append(best)
    b = pd.DataFrame(out).merge(gm, on="game_id")
    b["won"] = np.where(b.side == "home", b.hs > b.as_, b.as_ > b.hs)
    b["profit"] = np.where(b.won, b.price.map(win_per_unit), -1.0)
    b["dog"] = b.price > 0
    return b.sort_values(["gdate", "game_id"]).reset_index(drop=True)


def grid(name: str, b: pd.DataFrame, cuts=CUTS, seasons: bool = True) -> list[dict]:
    rows = []
    for cut in cuts:
        t = b[b.ev >= cut]
        if len(t) < 30:
            rows.append({"rule": name, "EV>=": cut, "bets": len(t)})
            continue
        p = t.profit.values
        half = len(t) // 2
        r = {"rule": name, "EV>=": cut, **summarise(p),
             "early": round(float(p[:half].mean()) * 100, 1), "late": round(float(p[half:].mean()) * 100, 1),
             "dogs": round(float(t.dog.mean()), 2),
             "EV at Pin close": round(float(t.ev_close.mean()) * 100, 2),
             "still +EV at close": round(float((t.ev_close > 0).mean()) * 100, 1)}
        if seasons:
            for s in SEASONS:
                m = (t.season == s).values
                r[f"{s - 1}-{str(s)[2:]}"] = (f"{p[m].mean() * 100:+.1f}% ({int(m.sum())})"
                                              if m.sum() >= 30 else f"({int(m.sum())})")
        rows.append(r)
    return rows


def show(title: str, rows: list[dict]) -> None:
    print(f"\n### {title}\n")
    print(pd.DataFrame(rows).to_string(index=False))


def main() -> None:
    conn = get_connection()
    try:
        gm, q = load(conn)
    finally:
        conn.close()
    print(f"{len(gm):,} games 2020-21 -> 2025-26; quotes: {len(q):,} (game, book, open/close) rows; "
          f"bettable books {BETTABLE}; sharp {SHARP}")
    o = candidates(gm, q, "open", BETTABLE)
    c = candidates(gm, q, "close", BETTABLE)
    print(f"games with a Pinnacle quote and a simultaneous bettable quote: open {len(o):,}, close {len(c):,}; "
          f"median bettable books per game at the open {o.n_books.median():.0f}")

    show("Decided at the OPEN, best bettable price", grid("open", o))
    show("Decided at the CLOSE, best bettable price", grid("close", c))
    show("Decided at the open, quotes NOT required to be simultaneous",
         grid("open, any gap", candidates(gm, q, "open", BETTABLE, simultaneous=False), seasons=False))
    show("DraftKings only, decided at the open", grid("draftkings", candidates(gm, q, "open", ["draftkings"])))

    rows = []
    for drop in BETTABLE:
        b = candidates(gm, q, "open", [x for x in BETTABLE if x != drop])
        rows += [{"without": drop, **{k: v for k, v in r.items() if k != "rule"}}
                 for r in grid("", b, cuts=(0.02, 0.03, 0.04), seasons=False)]
    show("Leave one book out, decided at the open", rows)

    rows = []
    for cut in (0.02, 0.03, 0.04):
        t = o[o.ev >= cut]
        for label, m in (("underdog", t.dog), ("favourite", ~t.dog)):
            s = t[m]
            rows.append({"EV>=": cut, "side": label,
                         **(summarise(s.profit.values) if len(s) >= 30 else {"bets": len(s)}),
                         "EV at Pin close": round(float(s.ev_close.mean()) * 100, 2) if len(s) else None})
        for label, m in (("price +100..+149", t.price.between(100, 149)), ("price +150 or longer", t.price >= 150),
                         ("price shorter than -150", t.price < -150)):
            s = t[m]
            rows.append({"EV>=": cut, "side": label,
                         **(summarise(s.profit.values) if len(s) >= 30 else {"bets": len(s)})})
    show("Who the bets are, decided at the open", rows)

    t = o[o.ev >= 0.03]
    by = t.groupby("book").agg(bets=("profit", "size"), units=("profit", "sum"), roi=("profit", "mean"))
    by["roi"] = (by.roi * 100).round(2)
    by["units"] = by.units.round(1)
    print("\n### The 0.03 cut, by the book whose price was taken\n")
    print(by.sort_values("bets", ascending=False).to_string())
    per_day = t.groupby("gdate").size()
    print(f"\nat 0.03: {len(t):,} bets over {gm.gdate.nunique():,} game days "
          f"({len(t) / gm.gdate.nunique():.2f} a game day; most on one day {int(per_day.max())})")


if __name__ == "__main__":
    main()
