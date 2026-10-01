"""NHL moneyline underdogs against favourites, in units, on six seasons of stored prices.

mike, 2026-10-01: "Underdog +money bets are more important than favorites.
This has been proven." The published record stops in January 2022 (see
docs/nhl_market_lab.md), so the seasons since have to be measured here.

No model. Every game 2020-21 -> 2025-26 with a DraftKings pre-game moneyline in
the bought history (`odds.source = 'odds_api_historical'`), one unit on a side:

  OPEN   each book's FIRST pre-game quote (the 16:00Z game-day snapshot)
  CLOSE  each book's LAST pre-game quote (the start-hour snapshot)
  BEST   the best OPEN price among the books a member can bet
         (config.BEST_LINE_BOOKMAKERS)

"Underdog" is the side DraftKings prices longer at the open; a game priced the
same both ways has none and is left out. Closing-line value is Pinnacle's last
pre-game no-vig probability minus its first, on the side taken.

    python -m scripts.nhl_underdog_grid
"""
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config  # noqa: E402
from data.db import get_connection  # noqa: E402
from scripts.nhl_market_lab import implied, novig, summarise, win_per_unit  # noqa: E402

pd.set_option("display.width", 250)
FEED = "odds_api_historical"
SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
BETTABLE = list(config.BEST_LINE_BOOKMAKERS)
BANDS = [(100, 119), (120, 149), (150, 199), (200, 10_000)]


def _ts(v):
    return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(timezone.utc)


def load(conn) -> pd.DataFrame:
    """One row per game: DraftKings open and close, the best bettable open, Pinnacle open and close."""
    games = conn.execute(
        "SELECT game_id, season, game_date, commence_time, home_score, away_score FROM games "
        "WHERE sport = 'NHL' AND season = ANY(%s) AND home_score IS NOT NULL AND commence_time IS NOT NULL",
        (SEASONS,)).fetchall()
    start = {g[0]: _ts(g[3]) for g in games}
    ids = list(start)
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
    first = px.groupby(["game_id", "book"], sort=False).first().reset_index()
    last = px.groupby(["game_id", "book"], sort=False).last().reset_index()
    out: dict[str, dict] = {}
    for gid, g in first.groupby("game_id"):
        d = out.setdefault(gid, {"game_id": gid})
        dk, pin, soft = g[g.book == "draftkings"], g[g.book == "pinnacle"], g[g.book.isin(BETTABLE)]
        if len(dk):
            d["dk_home"], d["dk_away"] = float(dk.hp.iloc[0]), float(dk.ap.iloc[0])
        if len(pin):
            d["pin_open_home"] = novig(float(pin.hp.iloc[0]), float(pin.ap.iloc[0]))
        if len(soft):
            ih, ia = soft.hp.idxmax(), soft.ap.idxmax()
            d["best_home"], d["best_away"] = float(soft.hp.loc[ih]), float(soft.ap.loc[ia])
            d["best_home_book"], d["best_away_book"] = soft.book.loc[ih], soft.book.loc[ia]
            d["n_books"] = len(soft)
    for gid, g in last.groupby("game_id"):
        d = out.setdefault(gid, {"game_id": gid})
        dk, pin = g[g.book == "draftkings"], g[g.book == "pinnacle"]
        if len(dk):
            d["dkc_home"], d["dkc_away"] = float(dk.hp.iloc[0]), float(dk.ap.iloc[0])
        if len(pin):
            d["pin_close_home"] = novig(float(pin.hp.iloc[0]), float(pin.ap.iloc[0]))
    gm = pd.DataFrame(games, columns=["game_id", "season", "gdate", "commence", "hs", "as_"])
    gm["hs"], gm["as_"] = pd.to_numeric(gm.hs), pd.to_numeric(gm.as_)
    df = gm.merge(pd.DataFrame(out.values()), on="game_id", how="inner").dropna(subset=["dk_home", "dk_away"])
    return df[df.dk_home != df.dk_away].copy()


def sides(df: pd.DataFrame) -> pd.DataFrame:
    """Two rows per game — the underdog and the favourite — with every price the side could be bet at."""
    dog_home = df.dk_home > df.dk_away
    parts = []
    for role, home in (("underdog", dog_home), ("favourite", ~dog_home)):
        s = pd.DataFrame({
            "game_id": df.game_id, "season": df.season, "gdate": df.gdate, "role": role,
            "where": np.where(home, "home", "road"),
            "won": np.where(home, df.hs > df.as_, df.as_ > df.hs),
            "open": np.where(home, df.dk_home, df.dk_away),
            "close": np.where(home, df.dkc_home, df.dkc_away),
            "best": np.where(home, df.best_home, df.best_away),
            "best_book": np.where(home, df.best_home_book, df.best_away_book),
            "pin_open": np.where(home, df.pin_open_home, 1 - df.pin_open_home),
            "pin_close": np.where(home, df.pin_close_home, 1 - df.pin_close_home),
        })
        parts.append(s)
    s = pd.concat(parts, ignore_index=True)
    s["clv"] = s.pin_close - s.pin_open
    return s


def profit(s: pd.DataFrame, at: str) -> np.ndarray:
    return np.where(s.won, s[at].map(win_per_unit), -1.0)


def row(label: dict, s: pd.DataFrame, at: str) -> dict:
    s = s.dropna(subset=[at])
    if len(s) < 30:
        return {**label, "priced at": at, "bets": len(s)}
    return {**label, "priced at": at, **summarise(profit(s, at), s.clv.values),
            "win%": round(float(s.won.mean()) * 100, 1)}


def show(title: str, rows: list[dict]) -> None:
    print(f"\n### {title}\n")
    print(pd.DataFrame(rows).to_string(index=False))


def main() -> None:
    conn = get_connection()
    try:
        df = load(conn)
    finally:
        conn.close()
    s = sides(df)
    print(f"{len(df):,} games with a DraftKings pre-game moneyline and a favourite, seasons "
          f"{SEASONS[0] - 1}-{str(SEASONS[0])[2:]} -> {SEASONS[-1] - 1}-{str(SEASONS[-1])[2:]}; "
          f"per season {df.groupby('season').size().to_dict()}; bettable books {BETTABLE}")

    show("All six seasons, blind", [row({"side": r}, s[s.role == r], at)
                                    for r in ("underdog", "favourite") for at in ("open", "close", "best")])

    rows = []
    for season in SEASONS:
        for r in ("underdog", "favourite"):
            rows.append(row({"season": f"{season - 1}-{str(season)[2:]}", "side": r},
                            s[(s.role == r) & (s.season == season)], "open"))
    show("By season, DraftKings open", rows)

    rows = []
    for season in SEASONS:
        for r in ("underdog", "favourite"):
            rows.append(row({"season": f"{season - 1}-{str(season)[2:]}", "side": r},
                            s[(s.role == r) & (s.season == season)], "best"))
    show("By season, best bettable open price", rows)

    dogs = s[s.role == "underdog"]
    rows = []
    for lo, hi in BANDS:
        b = dogs[dogs.open.between(lo, hi)]
        name = f"+{lo} to +{hi}" if hi < 10_000 else f"+{lo} or longer"
        r = row({"underdog priced": name}, b, "open")
        for season in SEASONS:
            q = b[b.season == season]
            r[f"{season - 1}-{str(season)[2:]}"] = (f"{profit(q, 'open').mean() * 100:+.1f}% ({len(q)})"
                                                    if len(q) >= 30 else f"({len(q)})")
        rows.append(r)
    show("Underdogs by DraftKings opening price, with each season's return (bets)", rows)

    rows = []
    for wh in ("home", "road"):
        for r in ("underdog", "favourite"):
            rows.append(row({"side": f"{wh} {r}"}, s[(s.role == r) & (s["where"] == wh)], "open"))
    show("Home and road, DraftKings open", rows)

    # line shopping: is the best bettable price better than the sharp book's fair price, and does it pay?
    rows = []
    for r in ("underdog", "favourite"):
        q = s[(s.role == r)].dropna(subset=["best", "pin_open"]).copy()
        q["ev"] = q.pin_open * (1 + q.best.map(win_per_unit)) - 1
        rows.append({"side": r, "games": len(q), "share where best price beats Pinnacle's fair price":
                     round(float((q.ev > 0).mean()) * 100, 1), "mean EV at best price, %": round(float(q.ev.mean()) * 100, 2)})
        for cut in (0.0, 0.02, 0.04):
            t = q[q.ev >= cut]
            rows.append({"side": f"{r}, bet when EV vs Pinnacle >= {cut:.2f}",
                         **(summarise(profit(t, "best"), t.clv.values) if len(t) >= 30 else {"bets": len(t)})})
    show("Line shopping: the best bettable open price against Pinnacle's no-vig open", rows)

    # the same rule with no side chosen, as a neighbourhood and season by season
    q = s.dropna(subset=["best", "pin_open"]).copy()
    q["ev"] = q.pin_open * (1 + q.best.map(win_per_unit)) - 1
    rows = []
    for cut in (0.0, 0.01, 0.02, 0.03, 0.04, 0.06):
        t = q[q.ev >= cut].sort_values("gdate")
        if len(t) < 30:
            rows.append({"EV vs Pinnacle >=": cut, "bets": len(t)})
            continue
        p = profit(t, "best")
        half = len(t) // 2
        r = {"EV vs Pinnacle >=": cut, **summarise(p, t.clv.values),
             "dog share": round(float((t.role == "underdog").mean()), 2),
             "early": round(float(p[:half].mean()) * 100, 1), "late": round(float(p[half:].mean()) * 100, 1)}
        for season in SEASONS:
            m = (t.season == season).values
            r[f"{season - 1}-{str(season)[2:]}"] = (f"{p[m].mean() * 100:+.1f}% ({int(m.sum())})"
                                                    if m.sum() >= 30 else f"({int(m.sum())})")
        rows.append(r)
    show("Either side, bet at the best bettable open price when it beats Pinnacle's no-vig open by the cut", rows)

    # whose price is it? one book hanging stale numbers would look exactly like an edge
    t = q[q.ev >= 0.02]
    rows = []
    for book, g in sorted(t.groupby("best_book"), key=lambda kv: -len(kv[1])):
        rows.append({"book with the best price": book,
                     **(summarise(profit(g, "best"), g.clv.values) if len(g) >= 30 else {"bets": len(g)})})
    show("The 0.02 cut, by the book whose price was taken", rows)

    hold = (df.dk_home.map(implied) + df.dk_away.map(implied) - 1).mean() * 100
    print(f"\nDraftKings' moneyline hold at the open on these games: {hold:.2f}%")


if __name__ == "__main__":
    main()
