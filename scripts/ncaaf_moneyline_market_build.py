"""Build the NCAAF moneyline model's frozen numbers
(models/ncaaf_moneyline_market.py) and replay its card walk-forward.

Writes models/saved/ncaaf_moneyline_market_<season>.json: the books, the check
hour and window, the cut, the price floor, the consensus limits, the fitted
offset and the final-margin table the card prices with, fitted on every scored
game before <season> that has a CFBD closing spread.

It then REPLAYS the card's own decision path
(models.ncaaf_moneyline_market.quotes_at -> decide) on the three seasons
before <season>, at 14:00 UTC on each game's Eastern date, on the quotes of
the stored game-day morning pull (13:55 UTC), with the table and offset fitted
on the seasons before each one. It grades every bet (a moneyline, overtime
included), prints bets, units and return by season, the price and EV ranges,
and compares the bets game by game with the research's.

    python -m scripts.ncaaf_moneyline_market_build --cache DIR [--last-season 2025]
        [--out PATH] [--check-bets PKL] [--bets-out PATH]

DIR holds two files, each every NCAAF row of one table, taken from the local
copy of the database (docs/local_ops.md) by
scripts/ncaaf_search/audit_2026_11/extract_ncaaf.py: ncaaf_games.parquet
(`games`) and ncaaf_odds.parquet (`odds`). Every row is in Supabase. Nothing
else is read, no database and no network.

--check-bets is the research's bets (a pickle, {"keep": {cut: frame}}, written
by scripts/ncaaf_search/audit_2026_11/lab.py as bets_D0_AM_C.pkl): the replay
must hold the same game, side, book and price for every one.

WHAT THE REPLAY READS, the research's own read (audit_2026_11/prep.py and
lab.load, ported here so the build needs neither):
  * Games. A game counts when it has a final score, its own or its twin's: an
    odds row with no score takes the score of the one scored row for the same
    two teams, in the same season, dated within a day (orientation corrected).
    Where two odds rows are one real game, the one with more stored quotes is
    kept.
  * The morning pull. The stored historical pulls of the game's Eastern date
    taken before 18:00 UTC and at least five minutes before kickoff; a book's
    quotes are those of the latest such pull that holds any row for it.
  * The card's read then runs unchanged: each book's newest complete row in
    the 60 minutes up to 14:00 UTC. Measured on these pulls (2026-11-10):
    every quote's own stamp is 4 to 19 minutes before 14:00 UTC.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.ncaab_margin_dist as md  # noqa: E402
import models.ncaaf_moneyline_market as mm  # noqa: E402

BOOTSTRAP = 2000
REPLAY_SEASONS = 3
PULL_SOURCE = "odds_api_historical"
PM_HOUR_UTC = 18          # a pull stamped before this hour is the morning one


# ── the two reads ─────────────────────────────────────────────────────────────

def load_games(cache: Path) -> pd.DataFrame:
    g = pd.read_parquet(cache / "ncaaf_games.parquet",
                        columns=["game_id", "season", "game_date", "home_team", "away_team",
                                 "home_score", "away_score", "commence_time"])
    for c in ("home_score", "away_score"):
        g[c] = pd.to_numeric(g[c], errors="coerce")
    g["season"] = g["season"].astype(int)
    g["kick"] = pd.to_datetime(g["commence_time"], utc=True, errors="coerce", format="mixed")
    g["margin"] = g["home_score"] - g["away_score"]
    g["et_date"] = g["kick"].dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
    return g


def load_odds(cache: Path) -> pd.DataFrame:
    """Every stored NCAAF odds row, file order kept in `order` (it breaks a tie
    between two rows of one book with the same stamp)."""
    o = pd.read_parquet(cache / "ncaaf_odds.parquet",
                        columns=["game_id", "market", "bookmaker", "snapshot_type", "snapshot_at",
                                 "created_at", "source", "home_price", "away_price", "spread_home"])
    o["order"] = np.arange(len(o), dtype="int64")
    return o


def closing_spreads(o: pd.DataFrame) -> pd.Series:
    """game_id -> CFBD's stored closing spread (the home number), from the
    first provider in mm.CLOSE_PRIORITY that has one. CFBD's lines are stored
    one row a game and provider, under the cfbd_* bookmakers."""
    c = o[o["bookmaker"].isin(mm.CLOSE_PRIORITY) & (o["market"] == "spreads")].copy()
    c["spread_home"] = pd.to_numeric(c["spread_home"], errors="coerce")
    c = c[c["spread_home"].notna()]
    c["rank"] = c["bookmaker"].map({b: i for i, b in enumerate(mm.CLOSE_PRIORITY)})
    c = c.sort_values(["game_id", "rank", "order"], kind="mergesort").drop_duplicates("game_id")
    return c.set_index("game_id")["spread_home"]


def with_twins(g: pd.DataFrame, has_odds: set) -> pd.DataFrame:
    """Give an unscored row that has odds its scored twin's result.

    The twin is the ONE scored row with the same two teams, in the same
    season, dated within a day (a night game is stored twice: the odds feed's
    Eastern-dated row carries the prices, CFBD's UTC-dated row the score). No
    twin, or two, and the row stays unscored. A flipped twin (home and away
    swapped) gives the margin and the closing spread their signs back. Adds
    twin_of."""
    g = g.copy()
    g["d"] = pd.to_datetime(g["game_date"])
    g["twin_of"] = None
    idx: dict = {}
    for r in g[g["margin"].notna()].itertuples(index=False):
        idx.setdefault((r.season, frozenset((r.home_team, r.away_team))), []).append(r)
    for r in g[g["margin"].isna() & g["game_id"].isin(has_odds)].itertuples():
        cands = [c for c in idx.get((r.season, frozenset((r.home_team, r.away_team))), [])
                 if abs((c.d - r.d).days) <= 1]
        if len(cands) != 1:
            continue
        c = cands[0]
        sgn = -1 if c.home_team != r.home_team else 1
        g.at[r.Index, "margin"] = sgn * c.margin
        g.at[r.Index, "twin_of"] = c.game_id
        g.at[r.Index, "close_spread"] = (sgn * c.close_spread if pd.notna(c.close_spread)
                                         else np.nan)
    return g.drop(columns="d")


def history(cache: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(games with margin, close_spread and twin_of; the odds rows)."""
    g = load_games(cache)
    o = load_odds(cache)
    g["close_spread"] = g["game_id"].map(closing_spreads(o))
    return with_twins(g, set(o["game_id"].unique())), o


def train_rows(g: pd.DataFrame, season: int) -> pd.DataFrame:
    """The games a season's table and offset are fitted on: every game of an
    earlier season that has its own final score (not a twin's) and a CFBD
    closing spread, in game-date then game-id order (the fit adds in it)."""
    base = g[g["twin_of"].isna() & g["margin"].notna()].sort_values(
        ["game_date", "game_id"], kind="mergesort")
    return base[(base["season"] < season) & base["close_spread"].notna()]


def table_for(g: pd.DataFrame, season: int) -> tuple[dict, float, int]:
    """(final-margin table, offset, games) for `season`. The table's mean is
    minus the closing spread; the offset is the mean of final margin plus
    closing spread."""
    tr = train_rows(g, season)
    table = md.fit(tr["margin"].astype(int).to_numpy(), (-tr["close_spread"]).to_numpy())
    return table, float((tr["margin"] + tr["close_spread"]).mean()), int(len(tr))


def morning_rows(g: pd.DataFrame, o: pd.DataFrame, seasons) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(h2h rows, spreads rows, games) of the stored game-day morning pull for
    the scored games of `seasons`, as the card's read takes them: one row per
    stored odds row with ts, line, p1, p2, order, instant (14:00 UTC on the
    game's Eastern date) and tip."""
    h = o[(o["source"].fillna("").str.split("|").str[0] == PULL_SOURCE)
          & (o["snapshot_type"] == "open")].copy()
    h["ts"] = pd.to_datetime(h["snapshot_at"], utc=True, errors="coerce", format="mixed")
    # A pull is one stored batch; its stamp is the newest quote in it.
    h["pull_ts"] = h["created_at"].map(h.groupby("created_at")["ts"].max())
    h = h[h["bookmaker"].isin(mm.CONS_BOOKS) & h["market"].isin(["spreads", "totals", "h2h"])]
    gg = g[g["margin"].notna() & g["season"].isin(list(seasons)) & g["kick"].notna()]
    h = h.merge(gg[["game_id", "kick", "et_date", "season", "twin_of"]], on="game_id", how="inner")
    h = h[h["pull_ts"] < h["kick"] - mm.MIN_LEAD]
    # One odds id per real game: the one with more stored quotes (a quote is a
    # book at a pull).
    per = h.drop_duplicates(["game_id", "pull_ts", "bookmaker"])
    n = per.assign(canon=per["twin_of"].fillna(per["game_id"])).groupby(
        ["canon", "game_id"]).size().reset_index(name="n")
    n = n.sort_values(["canon", "n", "game_id"], ascending=[True, False, True], kind="mergesort")
    h = h[h["game_id"].isin(set(n.drop_duplicates("canon")["game_id"]))]
    # The game-day morning pull, and each book's latest one.
    pull_et = h["pull_ts"].dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
    h = h[(pull_et == h["et_date"]) & (h["pull_ts"].dt.hour < PM_HOUR_UTC)]
    h = h[h["pull_ts"] == h.groupby(["game_id", "bookmaker"])["pull_ts"].transform("max")]
    h["instant"] = [pd.Timestamp(mm.check_instant(d)) for d in h["et_date"]]
    h["tip"] = h["kick"]
    for c in ("home_price", "away_price", "spread_home"):
        h[c] = pd.to_numeric(h[c], errors="coerce").astype(float)
    h = h.rename(columns={"home_price": "p1", "away_price": "p2", "spread_home": "line"})
    cols = ["game_id", "bookmaker", "ts", "line", "p1", "p2", "order", "instant", "tip"]
    games = h.drop_duplicates("game_id")[["game_id", "season", "et_date", "kick", "instant"]]
    return (h[h["market"] == "h2h"][cols].reset_index(drop=True),
            h[h["market"] == "spreads"][cols].reset_index(drop=True),
            games.reset_index(drop=True))


# ── the replay ────────────────────────────────────────────────────────────────

def replay_season(ml_rows: pd.DataFrame, sp_rows: pd.DataFrame, games: pd.DataFrame,
                  table: dict, offset: float, cut: float) -> list[mm.Decision]:
    """The card's decision path over one season's games at their 14:00 UTC
    instants: read, then decide. A game kicking off less than five minutes
    after 14:00 UTC is not priced (as on the card)."""
    g = games[[not mm.too_close(k, i) for k, i in zip(games["kick"], games["instant"])]]
    ids = set(g["game_id"])
    q = mm.quotes_at(ml_rows[ml_rows["game_id"].isin(ids)], sp_rows[sp_rows["game_id"].isin(ids)])
    return mm.decide(sorted(ids), q, table, offset, cut)


def replay(g: pd.DataFrame, rows: tuple, seasons, tables: dict, cut: float,
           offset: float | None = None) -> pd.DataFrame:
    """Every priced game's best side over `seasons`, with its status, margin
    and Eastern date. rows: morning_rows output. offset: use this one for
    every season (a control)."""
    ml_rows, sp_rows, games = rows
    out = []
    for s in seasons:
        table, c, _ = tables[s]
        gs = games[games["season"] == s]
        for d in replay_season(ml_rows, sp_rows, gs, table, c if offset is None else offset, cut):
            if d.best is not None:
                out.append({"game_id": d.game_id, "season": s, "status": d.status,
                            **{k: d.best.get(k) for k in ("bookmaker", "side", "price", "edge",
                                                          "prob", "cons", "n_ok", "mu")}})
    return pd.DataFrame(out).merge(g[["game_id", "margin", "et_date"]], on="game_id", how="left")


def road_teams_in_range(g: pd.DataFrame, rows: tuple, lo: float, hi: float) -> pd.DataFrame:
    """A control, not the model: every game whose road team's longest
    moneyline among the deciding books, at the same read, is priced lo to hi,
    bet at that price. No table, no consensus, no cut."""
    ml_rows, sp_rows, games = rows
    ids = {gid for gid, k, i in zip(games["game_id"], games["kick"], games["instant"])
           if not mm.too_close(k, i)}
    q = mm.quotes_at(ml_rows[ml_rows["game_id"].isin(ids)], sp_rows[sp_rows["game_id"].isin(ids)])
    z = q[q["bookmaker"].isin(mm.DECIDING_BOOKS) & q["ml_home"].notna() & q["ml_away"].notna()].copy()
    z["_d"] = mm.dec(z["ml_away"])
    z = z.sort_values(["game_id", "_d", "bookmaker"], ascending=[True, False, True],
                      kind="mergesort").drop_duplicates("game_id")
    z = z[(z["ml_away"] >= lo) & (z["ml_away"] <= hi)]
    out = pd.DataFrame({"game_id": z["game_id"], "bookmaker": z["bookmaker"], "side": "away",
                        "price": z["ml_away"], "prob": np.nan, "edge": np.nan})
    return out.merge(g[["game_id", "season", "margin", "et_date"]], on="game_id", how="left")


def grade(b: pd.DataFrame) -> pd.DataFrame:
    """A moneyline: the side wins when its team's final margin (overtime
    included) is positive. 1 unit to win, risk capped at 3."""
    b = b[b["margin"].notna() & (b["margin"] != 0)].copy()
    dd = mm.dec(b["price"])
    win = np.where(b["side"] == "home", b["margin"] > 0, b["margin"] < 0)
    b["risk"] = np.minimum(1 / (dd - 1), 3.0)
    b["units"] = np.where(win, b["risk"] * (dd - 1), -b["risk"])
    b["result"] = np.where(win, "W", "L")
    b["ev"] = b["prob"] * dd - 1
    return b


def record(b: pd.DataFrame) -> dict:
    """Bets, record, units and return: the short summary the controls print."""
    if not len(b):
        return {"bets": 0}
    return {"bets": int(len(b)),
            "record": f"{int((b.result == 'W').sum())}-{int((b.result == 'L').sum())}",
            "units": round(float(b["units"].sum()), 2),
            "units_risked": round(float(b["risk"].sum()), 2),
            "roi_pct": round(float(b["units"].sum() / b["risk"].sum() * 100), 2),
            "road_teams": int((b["side"] == "away").sum())}


def halves(b: pd.DataFrame) -> dict:
    """Each season split at its median bet date: the early bets and the late
    ones (the research's split, lab.halves)."""
    early, late = [], []
    for _, x in b.groupby("season"):
        mid = x["et_date"].sort_values().iloc[len(x) // 2]
        early.append(x[x["et_date"] < mid])
        late.append(x[x["et_date"] >= mid])
    return {"early": record(pd.concat(early)) if early else {"bets": 0},
            "late": record(pd.concat(late)) if late else {"bets": 0}}


def summarize(b: pd.DataFrame) -> dict:
    if not len(b):
        return {"bets": 0}
    rng = np.random.default_rng(7)
    dd = b.groupby("et_date").agg(u=("units", "sum"), r=("risk", "sum"))
    j = rng.integers(0, len(dd), size=(BOOTSTRAP, len(dd)))
    lo, hi = np.percentile(dd["u"].values[j].sum(1) / dd["r"].values[j].sum(1) * 100, [2.5, 97.5])
    best10 = dd["u"].sort_values(ascending=False).head(10).sum()
    return {"bets": int(len(b)),
            "record": f"{int((b.result == 'W').sum())}-{int((b.result == 'L').sum())}",
            "units": round(float(b["units"].sum()), 2),
            "units_risked": round(float(b["risk"].sum()), 2),
            "roi_pct": round(float(b["units"].sum() / b["risk"].sum() * 100), 2),
            "ci95_dates": [round(float(lo), 1), round(float(hi), 1)],
            "price_min": float(b["price"].min()), "price_median": float(b["price"].median()),
            "price_max": float(b["price"].max()),
            "favourites": int((b["price"] < 0).sum()),
            "road_teams": int((b["side"] == "away").sum()),
            "ev_min": round(float(b["ev"].min()), 4), "ev_median": round(float(b["ev"].median()), 4),
            "ev_max": round(float(b["ev"].max()), 4),
            "edge_max": round(float(b["edge"].max()), 4),
            "units_without_10_best_dates": round(float(b["units"].sum() - best10), 2)}


def check_bets(bets: pd.DataFrame, path: Path, cut: float) -> dict:
    """The replay's bets against the research's, game by game."""
    r = pd.read_pickle(path)["keep"][cut][["game_id", "bookmaker", "side", "price", "edge"]].copy()
    r["side"] = np.where(r["side"] == 1, "home", "away")
    m = bets.merge(r, on="game_id", how="outer", suffixes=("", "_res"), indicator=True)
    both = m[m["_merge"] == "both"]
    same = both[(both["side"] == both["side_res"]) & (both["bookmaker"] == both["bookmaker_res"])
                & np.isclose(both["price"], both["price_res"], rtol=0, atol=1e-9)]
    differ = both[~both["game_id"].isin(same["game_id"])]
    return {"replay_bets": int(len(bets)), "research_bets": int(len(r)),
            "same_game": int(len(both)),
            "same_game_side_book_price": int(len(same)),
            "same_game_other_side_book_or_price": differ["game_id"].tolist()[:20],
            "replay_only": m.loc[m["_merge"] == "left_only", "game_id"].tolist()[:20],
            "research_only": m.loc[m["_merge"] == "right_only", "game_id"].tolist()[:20],
            "max_abs_edge_diff": (float((same["edge"] - same["edge_res"]).abs().max())
                                  if len(same) else None)}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", required=True, type=Path)
    ap.add_argument("--last-season", type=int, default=2025)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--check-bets", type=Path, default=None)
    ap.add_argument("--bets-out", type=Path, default=None)
    a = ap.parse_args(argv)
    t0 = time.time()
    last = a.last_season
    seasons = list(range(last - REPLAY_SEASONS + 1, last + 1))
    g, o = history(a.cache)
    print(f"games {len(g)} ({int(g['margin'].notna().sum())} with a final score, "
          f"{int(g['twin_of'].notna().sum())} of them from a twin row); odds rows {len(o)} "
          f"({time.time() - t0:.0f}s)", flush=True)
    tables = {s: table_for(g, s) for s in seasons + [last + 1]}
    for s, (_, c, n) in tables.items():
        print(f"season {s}: margin table on {n} games, offset {c:+.3f}", flush=True)

    rows = morning_rows(g, o, seasons)
    age = pd.concat([rows[0]["instant"] - rows[0]["ts"],
                     rows[1]["instant"] - rows[1]["ts"]]).dt.total_seconds() / 60
    quote_age = {"moneyline_rows": int(len(rows[0])), "spread_rows": int(len(rows[1])),
                 "games": int(len(rows[2])),
                 "minutes_before_14z": [round(float(age.min()), 1), round(float(age.max()), 1)],
                 "older_than_the_window": int((age > mm.WINDOW_MIN).sum()),
                 "after_14z": int((age < 0).sum())}
    print(f"the morning pull: {quote_age['games']} games, {quote_age['moneyline_rows']} moneyline and "
          f"{quote_age['spread_rows']} spread rows, each stamped {quote_age['minutes_before_14z'][0]} to "
          f"{quote_age['minutes_before_14z'][1]} minutes before 14:00 UTC; "
          f"{quote_age['older_than_the_window']} older than the card's {mm.WINDOW_MIN}-minute window, "
          f"{quote_age['after_14z']} after 14:00 UTC", flush=True)
    dz = replay(g, rows, seasons, tables, mm.CUT)
    bets = grade(dz[dz["status"] == "bets"].copy())
    print(f"replayed {seasons[0]}-{last}: {len(dz)} games priced, {len(bets)} bets "
          f"({time.time() - t0:.0f}s)", flush=True)
    per = {str(s): summarize(bets[bets["season"] == s]) for s in seasons}
    per[f"{seasons[0]}-{last}"] = summarize(bets)
    neighbours = {}
    for c in (0.01, 0.03, 0.04, 0.05):
        x = dz[(dz["n_ok"] - 1 >= mm.MIN_OTHER) & (dz["edge"] > c)
               & dz["bookmaker"].isin(mm.DECIDING_BOOKS)]
        neighbours[str(c)] = summarize(grade(x.copy()))
    # Two controls, neither the model. The same rule with the fitted offset
    # set to zero; and every road team priced inside the range the rule's own
    # bets were priced in, with no rule at all.
    zero = replay(g, rows, seasons, tables, mm.CUT, offset=0.0)
    no_offset = record(grade(zero[zero["status"] == "bets"].copy()))
    lo, hi = float(bets["price"].min()), float(bets["price"].max())
    road = record(grade(road_teams_in_range(g, rows, lo, hi)))
    road["rule"] = (f"every road team whose longest deciding-book moneyline at the same read is "
                    f"{lo:+.0f} to {hi:+.0f}, at that price")
    summary = {"cut": mm.CUT, "min_price": mm.MIN_PRICE, "min_other_books": mm.MIN_OTHER,
               "rule": "14:00 UTC on the game's Eastern date, the best deciding-book moneyline "
                       "against the win chance the ten books' median spread implies, sides shorter "
                       "than -200 out before the pick, 3+ other books in the consensus",
               "read": "the stored game-day morning pull (13:55 UTC)", "read_quotes": quote_age,
               "priced_games": int(len(dz)), "by_season": per, "halves": halves(bets),
               "neighbour_cuts": neighbours,
               "control_offset_zero": no_offset, "control_road_teams_in_price_range": road}
    print("replay:", json.dumps(summary, indent=1))
    all_ = per[f"{seasons[0]}-{last}"]
    print(f"prices laid: {all_['price_min']:+.0f} to {all_['price_max']:+.0f} "
          f"(median {all_['price_median']:+.0f}), {all_['favourites']} favourites, "
          f"{all_['road_teams']} of {all_['bets']} road teams; EV {all_['ev_min']:+.4f} to "
          f"{all_['ev_max']:+.4f} (median {all_['ev_median']:+.4f})")
    check = None
    if a.check_bets:
        check = check_bets(bets, a.check_bets, mm.CUT)
        print("bet check against", a.check_bets.name, json.dumps(check, indent=1))
        ok = (check["same_game_side_book_price"] == check["research_bets"] == check["replay_bets"])
        print("MATCH: every research bet replayed, same game, side, book and price" if ok else
              "MISMATCH: the replay and the research differ (above)")
    if a.bets_out:
        bets.to_parquet(a.bets_out, index=False)
    table, offset, n = tables[last + 1]
    out = a.out or (mm.ROOT / f"models/saved/ncaaf_moneyline_market_{last + 1}.json")
    art = {
        "kind": mm.ARTIFACT_KIND, "model_id": mm.MODEL_ID,
        "season": last + 1, "prior_season": last,
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "command": f"python -m scripts.ncaaf_moneyline_market_build --cache <the two extracts> "
                   f"--last-season {last}",
        "deciding_books": list(mm.DECIDING_BOOKS), "consensus_books": list(mm.CONS_BOOKS),
        "check_hour_utc": mm.CHECK_HOUR_UTC, "window_min": mm.WINDOW_MIN,
        "min_lead_min": int(mm.MIN_LEAD.total_seconds() // 60),
        "cut": mm.CUT, "min_price": mm.MIN_PRICE, "min_other_books": mm.MIN_OTHER,
        "isum_range": [mm.ISUM_LO, mm.ISUM_HI], "max_abs_line": mm.MAX_ABS_LINE,
        "close_priority": list(mm.CLOSE_PRIORITY),
        "offset": offset,
        "offset_note": "mean(final margin + CFBD closing spread) over the table's games",
        "table_train_seasons": [int(train_rows(g, last + 1)["season"].min()), last],
        "table_train_games": n,
        "replay": summary, "research_check": check,
        "margin_table": md.to_json(table),
    }
    out.write_text(json.dumps(art, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes) in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
