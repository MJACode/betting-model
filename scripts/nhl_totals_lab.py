"""NHL total goals: is there anything in the full-game number? Four tests that need no model.

Three earlier rounds (docs/nhl_market_lab.md) fitted models to the total and
found nothing: log loss and AUC at the market's own, every cut losing 1-4%.
This asks the questions a model cannot hide behind, on six priced seasons
(2020-21 to 2025-26, DraftKings and Pinnacle in the same API snapshot):

  BLIND          every over, every under, at DraftKings' first and last
                 pre-game number; by line and by price band. The props are
                 beatable because the book's margin sits on one side. Does the
                 total's?
  SHARP-VS-SOFT  bet DraftKings (or the best soft book) the first time
                 Pinnacle's no-vig probability AT THE SAME LINE, IN THE SAME
                 SNAPSHOT, makes the soft price positive.
  OTHER NUMBER   the soft book hangs a different total from Pinnacle in the
                 same snapshot: bet toward Pinnacle's number.
  HINDSIGHT      the ceiling: bet DraftKings' first number in exactly the games
                 where the number later moved that way. No rule can know this in
                 advance; it bounds what predicting line movement could earn.

Quotes are simultaneous by construction: one API snapshot returns every book
at one instant, and rows of one snapshot share `created_at`. Comparing prices
from different snapshots manufactured the moneyline "edge" of 2026-10-01.

    python -m scripts.nhl_totals_lab
    python -m scripts.nhl_totals_lab --cache DIR     # games.pkl + odds.pkl, read once
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config  # noqa: E402

pd.set_option("display.width", 260)
pd.set_option("display.max_rows", 300)
SOFT = ["draftkings", "fanduel", "betmgm", "williamhill_us", "betrivers", "hardrockbet", "fanatics", "bovada"]
BETTABLE = [b for b in SOFT if b in config.BEST_LINE_BOOKMAKERS]
SOURCE = "odds_api_historical"


def imp(a):
    a = np.asarray(a, float)
    return np.where(a > 0, 100 / (a + 100), -a / (-a + 100))


def wpu(a):
    a = np.asarray(a, float)
    return np.where(a > 0, a / 100, 100 / -a)


def load(cache: str | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    if cache:
        c = Path(cache)
        od = pd.read_pickle(c / "odds.pkl")
        return pd.read_pickle(c / "games.pkl"), od[(od.market == "totals") & (od.source == SOURCE)]
    from data.db import get_connection
    conn = get_connection()
    try:
        games = pd.DataFrame(conn.execute(
            "SELECT game_id, season, game_date, commence_time, home_score, away_score FROM games "
            "WHERE sport = 'NHL'").fetchall(),
            columns=["game_id", "season", "game_date", "commence_time", "home_score", "away_score"])
        ids, rows = sorted(games[games.season.between(2021, 2026)].game_id), []
        for i in range(0, len(ids), 150):                    # by game id: the odds table is 10 GB
            rows += conn.execute(
                "SELECT game_id, bookmaker, snapshot_type, snapshot_at, created_at, total_line, over_price, "
                "under_price FROM odds WHERE game_id = ANY(%s) AND source = %s AND market = 'totals'",
                (ids[i:i + 150], SOURCE)).fetchall()
        return games, pd.DataFrame(rows, columns=["game_id", "book", "snapshot_type", "snap", "created_at",
                                                  "total_line", "over", "under"])
    finally:
        conn.close()


def interval(b: pd.DataFrame) -> str:
    """95% on the return, resampling whole game days (seeded per call: same bets, same interval)."""
    g = b.groupby("game_date").profit.agg(["sum", "count"])
    tot, cnt = g["sum"].values, g["count"].values
    idx = np.random.default_rng(11).integers(0, len(g), size=(2000, len(g)))
    lo, hi = np.percentile(tot[idx].sum(1) / cnt[idx].sum(1), [2.5, 97.5]) * 100
    return f"{lo:+.1f}..{hi:+.1f}"


def row(label: dict, b: pd.DataFrame, seasons: list) -> dict:
    if len(b) < 30:
        return {**label, "bets": len(b)}
    r = {**label, "bets": len(b), "units": round(float(b.profit.sum()), 1),
         "roi%": round(float(b.profit.mean()) * 100, 2), "95% by day": interval(b)}
    for s in seasons:
        q = b[b.season == s]
        r[f"{s - 1}-{str(s)[2:]}"] = f"{q.profit.mean() * 100:+.1f}% ({len(q)})" if len(q) >= 30 else f"({len(q)})"
    return r


def grade(b: pd.DataFrame, side: str) -> np.ndarray:
    won = (b.total > b.total_line) if side == "over" else (b.total < b.total_line)
    return np.where(b.total == b.total_line, 0.0, np.where(won, wpu(b.over if side == "over" else b.under), -1.0))


def show(title: str, rows: list[dict]) -> None:
    print(f"\n### {title}\n")
    print(pd.DataFrame(rows).to_string(index=False))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", default=None)
    a = ap.parse_args()
    games, od = load(a.cache)
    games = games[games.home_score.notna() & games.away_score.notna()].copy()
    games["total"] = pd.to_numeric(games.home_score) + pd.to_numeric(games.away_score)
    t = od[od.snapshot_type == "open"].copy()
    for c in ("total_line", "over", "under"):
        t[c] = pd.to_numeric(t[c], errors="coerce")
    t = t.dropna(subset=["total_line", "over", "under"]).merge(
        games[["game_id", "season", "game_date", "commence_time", "total"]], on="game_id")
    t["snap_t"] = pd.to_datetime(t.snap, utc=True)
    t = t[t.snap_t <= pd.to_datetime(t.commence_time, utc=True)]              # pre-game only
    t["hours_out"] = (pd.to_datetime(t.commence_time, utc=True) - t.snap_t).dt.total_seconds() / 3600
    io_, iu = imp(t.over), imp(t.under)
    t = t[(io_ + iu > 1.0) & (io_ + iu < 1.15)].copy()
    t["nv_over"] = imp(t.over) / (imp(t.over) + imp(t.under))
    seasons = sorted(int(s) for s in t.season.unique())
    print(f"{len(t):,} pre-game totals quotes, {t.game_id.nunique():,} games, seasons {seasons}; "
          f"{t.groupby('game_id').created_at.nunique().mean():.1f} API snapshots a game")

    dk = t[t.book == "draftkings"].sort_values(["game_id", "snap_t"])
    for name, keep in (("FIRST", "first"), ("LAST", "last")):
        q = dk.drop_duplicates("game_id", keep=keep)
        rows, bands = [], []
        for side in ("over", "under"):
            b = q.assign(profit=grade(q, side), price=q[side])
            rows.append(row({"side": side, "line": "all"}, b, seasons))
            rows += [row({"side": side, "line": ln}, b[b.total_line == ln], seasons) for ln in (5.5, 6.0, 6.5)]
            bands += [row({"side": side, "price": f"{lo}..{hi}"}, b[(b.price >= lo) & (b.price <= hi)], seasons)
                      for lo, hi in ((-200, -131), (-130, -116), (-115, -106), (-105, 104), (105, 200))]
        show(f"BLIND at DraftKings' {name} pre-game number (median {q.hours_out.median():.1f}h before puck drop)", rows)
        show(f"BLIND by price band, {name} number", bands)

    pin = (t[t.book == "pinnacle"][["game_id", "created_at", "total_line", "nv_over"]]
           .rename(columns={"total_line": "pin_line", "nv_over": "pin_over"})
           .drop_duplicates(["game_id", "created_at"]))
    s = t[t.book.isin(SOFT)].merge(pin, on=["game_id", "created_at"])
    print(f"\nsoft-book quotes with Pinnacle in the SAME snapshot: {len(s):,}; "
          f"same number {(s.total_line == s.pin_line).mean():.1%}")
    same = s[s.total_line == s.pin_line]
    long = []
    for side in ("over", "under"):
        p = same.pin_over if side == "over" else 1 - same.pin_over
        long.append(same.assign(side=side, price=same[side], ev=p * (1 + wpu(same[side])) - 1,
                                profit=grade(same, side)))
    long = pd.concat(long)
    long = long[long.price >= -200]

    def first_hit(q: pd.DataFrame, cut: float) -> pd.DataFrame:
        b = q[q.ev >= cut].sort_values(["game_id", "snap_t", "ev"], ascending=[True, True, False])
        return b.drop_duplicates("game_id").sort_values(["game_date", "game_id"])

    # BETTABLE is the SOFT list without the books a member cannot bet (Bovada).
    # It is the set nhl_over_under's 0.01 cut was graded on (config.py,
    # MODEL_OWN_EV_FLOOR); the live model also bets betparx, which the history
    # purchase never asked for.
    for books, label in ((["draftkings"], "DraftKings"), (SOFT, "the best soft book"),
                         (BETTABLE, "the best bettable book")):
        q = long[long.book.isin(books)]
        show(f"SHARP-VS-SOFT: the first snapshot Pinnacle's no-vig makes {label}'s price +EV (same number)",
             [row({"pin EV>=": c}, first_hit(q, c), seasons) for c in (0.0, 0.01, 0.02, 0.03, 0.04)])

    diff = s[s.total_line != s.pin_line].copy()
    diff["side"] = np.where(diff.total_line > diff.pin_line, "under", "over")
    diff["price"] = np.where(diff.side == "under", diff.under, diff.over)
    diff["profit"] = np.where(diff.side == "under", grade(diff, "under"), grade(diff, "over"))
    diff = diff[diff.price >= -200]
    for books, label in ((["draftkings"], "DraftKings"), (SOFT, "any soft book")):
        q = (diff[diff.book.isin(books)].sort_values(["game_id", "snap_t", "price"], ascending=[True, True, False])
             .drop_duplicates("game_id").sort_values(["game_date", "game_id"]))
        show(f"OTHER NUMBER: {label} hangs a different total from Pinnacle; bet toward Pinnacle's",
             [row({"side": sd}, q if sd == "both" else q[q.side == sd], seasons) for sd in ("both", "over", "under")])

    first, last = dk.drop_duplicates("game_id", keep="first"), dk.drop_duplicates("game_id", keep="last")
    mv = first.merge(last[["game_id", "total_line"]].rename(columns={"total_line": "close_line"}), on="game_id")
    print(f"\nDraftKings' number moved between its first and last pre-game snapshot in "
          f"{(mv.total_line != mv.close_line).mean():.1%} of games")
    show("HINDSIGHT (not a rule): the first number, bet only where it later moved that way",
         [row({"bet": side}, mv[cond].assign(profit=grade(mv[cond], side)), seasons)
          for side, cond in (("over", mv.close_line > mv.total_line), ("under", mv.close_line < mv.total_line))])


if __name__ == "__main__":
    main()
