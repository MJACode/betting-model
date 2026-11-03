"""Build the first-post moneyline model's frozen numbers
(models/ncaab_moneyline_first_post.py) and replay its card's decision path over
2021-2026 on the stored history.

Writes models/saved/ncaab_moneyline_first_post_2027.json: the books, the cut,
the price floor, the other-books minimum, WHICH final-margin table the card
prices with (the spread model's, pinned by its SHA-256, as the 15:00 UTC
moneyline model's artifact pins it), the replay's numbers and the game-by-game
check against the research.

THE REPLAY. The history is the round-5 research's copy of `odds`
(rows.parquet: every pre-game h2h and spreads row of the 2021-2026 games, the
lines purchase plus the half-hourly opener grid) and the fetch ledger of the
instants it bought (ledger.parquet). A row is first SEEN at the first bought
instant at or after its own stamp, as the research read it: that instant is
the moment a capture poll would have shown it. A book's first post is its
first complete moneyline row; it is decided at the instant that first showed
it, when that instant is at least five minutes before tip and the book's
standing quote then is still that first row (a number already changed again
inside the half hour was never seen). At each such moment the card's own
functions run on every book's standing quotes (newest row stamped at or
before the moment): models.ncaab_moneyline_first_post.read -> decide_posts,
with the margin table fitted on the seasons before each one
(scripts/ncaab_spread_market_build.table_for, checked against the research's
tables). A game is bet at the first moment one of its posts bets.

It then grades every bet (a moneyline, overtime included), prints bets, units
and ROI by season and at the neighbouring cuts, compares the bets game by game
with the research's (--check-bets: the research's q3_bets.parquet), and
combines them with the 15:00 UTC model's bets (--live-bets, the same file's
S15Lpre cell at 0.01, which the 15:00 UTC model's own build matched 914 of
914), one bet a game, the earlier first, this model first on a tie.

    python -m scripts.ncaab_moneyline_first_post_build --rows R5/cache/rows.parquet
        --instants R5/cache/ledger.parquet --games R5/cache/games.parquet
        --table-cache NCAAB_CACHE [--check-tables PKL] [--check-bets PARQUET]
        [--live-bets PARQUET] [--last-season 2026] [--out PATH] [--bets-out PATH]

Reads nothing else and writes only the JSON (and --bets-out). Every row it
reads is in Supabase (`odds`, `odds_history_fetches`, `odds_history_pulls`).
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

import models.ncaab_book_quotes as bq  # noqa: E402
import models.ncaab_margin_dist as md  # noqa: E402
import models.ncaab_moneyline_first_post as fp  # noqa: E402
import models.ncaab_moneyline_own_spread as om  # noqa: E402
import scripts.ncaab_spread_market_build as sb  # noqa: E402

PAID_FIRST = sb.PAID_FIRST
BOOTSTRAP = 2000
NS_MIN = 60 * 10 ** 9
NEIGHBOURS = (0.01, 0.02)
COLS = {"spreads": ("spread_home", "home_price", "away_price"),
        "h2h": (None, "home_price", "away_price")}


# ── loading (the research's lib5.load_rows, unchanged in effect) ──────────────

def bought_instants(path: Path) -> np.ndarray:
    led = pd.read_parquet(path, columns=["instant"])
    return np.unique(led["instant"].values.astype("datetime64[ns]").astype("int64"))


def load_rows(path: Path, market: str, books, instants: np.ndarray) -> pd.DataFrame:
    """Every stored pre-game row of the market at `books`: line / p1 / p2, the
    stamp tsn, obs (the first bought instant at or after the stamp), first
    (the book's first complete row on the game). A row missing a price (or
    its line) is dropped first; two rows of one book with one stamp keep the
    one stored last."""
    lc, c1, c2 = COLS[market]
    cols = ["game_id", "market", "bookmaker", "ts", "stored", "tip", c1, c2] + ([lc] if lc else [])
    d = pd.read_parquet(path, columns=cols, filters=[("market", "==", market)])
    d["bookmaker"] = d["bookmaker"].astype(str)
    d = d[d["bookmaker"].isin(books)].copy()
    d = d.rename(columns={c1: "p1", c2: "p2"})
    if lc:
        d["line"] = d[lc].astype(float)
        d = d.drop(columns=[lc])
        d = d[d["line"].notna()]
    else:
        d["line"] = np.nan
    d = d[d["p1"].notna() & d["p2"].notna()]
    d = d.sort_values(["game_id", "bookmaker", "ts", "stored"], kind="mergesort")
    d = d.drop_duplicates(["game_id", "bookmaker", "ts"], keep="last")
    d["tsn"] = d["ts"].values.astype("datetime64[ns]").astype("int64")
    d["tipn"] = d["tip"].values.astype("datetime64[ns]").astype("int64")
    k = np.minimum(np.searchsorted(instants, d["tsn"].values, side="left"), len(instants) - 1)
    d["obs"] = instants[k]
    d = d.drop(columns=["market", "stored", "ts", "tip"]).reset_index(drop=True)
    d["rid"] = np.arange(len(d))
    d["first"] = ~d.duplicated(["game_id", "bookmaker"], keep="first")
    for c in ("p1", "p2"):
        d[c] = d[c].astype(float)
    return d


def standing(rows: pd.DataFrame, events: pd.DataFrame, books) -> pd.DataFrame:
    """Each book's newest row stamped at or before each event's moment
    (game_id, e): one row per (event, book) that has one, with rid."""
    left = events[["game_id", "e", "key"]].merge(pd.DataFrame({"bookmaker": list(books)}), how="cross")
    left = left.sort_values("e", kind="mergesort")
    r = rows[["game_id", "bookmaker", "tsn", "rid"]].sort_values("tsn", kind="mergesort")
    m = pd.merge_asof(left, r, left_on="e", right_on="tsn", by=["game_id", "bookmaker"],
                      direction="backward")
    m = m[m["rid"].notna()].copy()
    m["rid"] = m["rid"].astype("int64")
    return m


def as_card_rows(m: pd.DataFrame, rows: pd.DataFrame, tips: pd.Series) -> pd.DataFrame:
    """The standing rows in the shape the card's functions read, keyed on the
    event (`key` = game_id@moment, so one game decided at several moments is
    several keys)."""
    src = rows.iloc[m["rid"].values]
    return pd.DataFrame({
        "game_id": m["key"].values, "bookmaker": m["bookmaker"].values,
        "ts": pd.to_datetime(src["tsn"].values, utc=True),
        "line": src["line"].values, "p1": src["p1"].values, "p2": src["p2"].values,
        "order": m["rid"].values,
        "instant": pd.to_datetime(m["e"].values, utc=True),
        "tip": pd.to_datetime(m["game_id"].map(tips).values, utc=True),
    })


# ── grading ───────────────────────────────────────────────────────────────────

def grade(b: pd.DataFrame) -> pd.DataFrame:
    """A moneyline: the side wins when its team's final margin (overtime
    included) is positive. A game with no margin, or a 0 margin, is not graded."""
    b = b[b["margin"].notna() & (b["margin"] != 0)].copy()
    dd = fp.dec(b["price"])
    win = np.where(b["side"] == "home", b["margin"] > 0, b["margin"] < 0)
    b["risk"] = np.minimum(1 / (dd - 1), 3.0)
    b["units"] = np.where(win, b["risk"] * (dd - 1), -b["risk"])
    b["result"] = np.where(win, "W", "L")
    return b


def summarize(b: pd.DataFrame) -> dict:
    if not len(b):
        return {"bets": 0}
    rng = np.random.default_rng(7)
    dd = b.groupby("game_date").agg(u=("units", "sum"), r=("risk", "sum"))
    j = rng.integers(0, len(dd), size=(BOOTSTRAP, len(dd)))
    lo, hi = np.percentile(dd["u"].values[j].sum(1) / dd["r"].values[j].sum(1) * 100, [2.5, 97.5])
    du = b.groupby("game_date")["units"].sum().sort_values(ascending=False)
    out = {"bets": int(len(b)),
           "record": f"{int((b.result == 'W').sum())}-{int((b.result == 'L').sum())}",
           "units": round(float(b["units"].sum()), 2),
           "roi_pct": round(float(b["units"].sum() / b["risk"].sum() * 100), 2),
           "ci95_dates": [round(float(lo), 2), round(float(hi), 2)],
           "price_min": float(b["price"].min()), "price_median": float(b["price"].median()),
           "price_max": float(b["price"].max()),
           "units_without_10_best_dates": round(float(du.iloc[10:].sum()), 2)}
    if "prob" in b.columns and b["prob"].notna().all():
        ev = fp.ev_of(b["prob"], b["price"])
        out["ev_min"] = round(float(ev.min()), 4)
        out["ev_median"] = round(float(np.median(ev)), 4)
    if "lead_h" in b.columns:
        out["lead_h_median"] = round(float(b["lead_h"].median()), 2)
    return out


def by_season(b: pd.DataFrame, last: int) -> dict:
    per = {str(int(s)): summarize(b[b["season"] == s]) for s in sorted(b["season"].unique())}
    per[f"{PAID_FIRST}-{last - 1}"] = summarize(b[b["season"] <= last - 1])
    per[str(last)] = summarize(b[b["season"] == last])
    return per


# ── the checks ────────────────────────────────────────────────────────────────

def research_bets(path: Path, cell: str, cut: float) -> pd.DataFrame:
    r = pd.read_parquet(path, columns=["cell", "cut", "game_id", "side", "bookmaker", "price",
                                       "edge", "t", "season", "game_date", "units", "risk", "result", "prob"])
    r = r[(r["cell"] == cell) & np.isclose(r["cut"], cut)].copy()
    r["side"] = np.where(r["side"] == 1, "home", "away")
    return r


def check_bets(bets: pd.DataFrame, r: pd.DataFrame) -> dict:
    m = bets.merge(r[["game_id", "side", "bookmaker", "price", "edge", "t"]], on="game_id",
                   how="outer", suffixes=("", "_res"), indicator=True)
    both = m[m["_merge"] == "both"]
    same = both[(both["side"] == both["side_res"]) & np.isclose(both["price"], both["price_res"])]
    out = {"replay_bets": int(len(bets)), "research_bets": int(len(r)), "both": int(len(both)),
           "replay_only": m.loc[m["_merge"] == "left_only", "game_id"].tolist()[:20],
           "research_only": m.loc[m["_merge"] == "right_only", "game_id"].tolist()[:20],
           "same_game_side_price": int(len(same)),
           "same_book_too": int((same["bookmaker"] == same["bookmaker_res"]).sum()),
           "same_moment_too": int((same["t"] == same["t_res"]).sum()),
           "max_abs_edge_diff": float((same["edge"] - same["edge_res"]).abs().max()) if len(same) else None}
    for per, msk in (("2021-2025", bets["season"] <= 2025), ("2026", bets["season"] == 2026)):
        out[f"replay_bets_{per}"] = int(msk.sum())
    return out


def combined(first: pd.DataFrame, live: pd.DataFrame) -> pd.DataFrame:
    """One bet a game across the two moneyline models: the earlier first, this
    model first when both decide at the same moment (the research's q7)."""
    keep = ["game_id", "season", "game_date", "side", "price", "units", "risk", "result", "t"]
    u = pd.concat([first[keep].assign(src="cand"), live[keep].assign(src="live")], ignore_index=True)
    u = u.sort_values(["game_id", "t", "src"], kind="mergesort")
    return u.drop_duplicates("game_id", keep="first")


# ── the run ───────────────────────────────────────────────────────────────────

def replay(h2h: pd.DataFrame, spr: pd.DataFrame, games: pd.DataFrame, tables: dict,
           seasons, cut: float, t0: float) -> pd.DataFrame:
    """Every first post the card would have seen, decided by the card's own
    functions; -> one row per decided post (status, the post's best side)."""
    g = games.set_index("game_id")
    tips = g["tip"]
    # A moment at least five minutes before tip (the row's own tip, as the
    # research filtered its moments).
    firsts = h2h[h2h["first"] & h2h["bookmaker"].isin(bq.BOOKS)
                 & (h2h["obs"] <= h2h["tipn"] - 5 * NS_MIN)]
    ev = firsts[["game_id", "obs"]].drop_duplicates().rename(columns={"obs": "e"})
    ev = ev[ev["game_id"].isin(g.index)]
    ev["season"] = ev["game_id"].map(g["season"]).astype(int)
    ev = ev[ev["season"].isin(seasons)].reset_index(drop=True)
    ev["key"] = ev["game_id"] + "@" + ev["e"].astype(str)
    print(f"first-post moments {len(ev)} over {ev['game_id'].nunique()} games "
          f"({time.time() - t0:.0f}s)", flush=True)
    out = []
    n_drops = 0
    for s in sorted(ev["season"].unique()):
        es = ev[ev["season"] == s]
        mh = standing(h2h, es, fp.REF_BOOKS)
        ms = standing(spr, es, bq.BOOKS)
        # The posting books: the standing row IS the book's first row, and the
        # moment is the one that first showed it.
        hr = h2h.iloc[mh["rid"].values]
        post = mh[hr["first"].values & (hr["obs"].values == mh["e"].values)
                  & mh["bookmaker"].isin(bq.BOOKS).values]
        posting = pd.DataFrame({"game_id": post["key"].values, "bookmaker": post["bookmaker"].values})
        ml_rows, sp_rows = as_card_rows(mh, h2h, tips), as_card_rows(ms, spr, tips)
        # Feed typos out first, as the card does (models/ncaab_quote_bounds).
        drops = pd.concat([bq.dropped_quotes(ml_rows, window_min=None, books=fp.REF_BOOKS,
                                             need_line=False),
                           bq.dropped_quotes(sp_rows, window_min=None)], ignore_index=True)
        n_drops += len(drops)
        ml, sp = fp.read(ml_rows, sp_rows, tables[int(s)])
        ds = fp.decide_posts(posting, ml, sp, cut, with_quotes=False, dropped=drops)
        for d in ds:
            b = d.best or {}
            out.append({"key": d.game_id, "bookmaker": d.bookmaker, "status": d.status,
                        "n_books": d.n_books, "side": b.get("side"), "price": b.get("price"),
                        "edge": b.get("edge"), "prob": b.get("prob"), "own_line": b.get("own_line"),
                        "mu": b.get("mu")})
        print(f"  replayed {s}: {len(es)} moments, {len(posting)} posts "
              f"({time.time() - t0:.0f}s)", flush=True)
    d = pd.DataFrame(out).merge(ev[["key", "game_id", "e", "season"]], on="key", how="left")
    d.attrs["quotes_dropped"] = n_drops
    return d


def bets_at(d: pd.DataFrame, cut: float, games: pd.DataFrame) -> pd.DataFrame:
    """The bet of each game at `cut`, from a replay decided at a cut at or
    below it: the moment's winner must clear `cut`, and the game is bet at the
    first moment that has one."""
    w = d[d["status"].isin(["bets"]) & (d["edge"] > cut)]
    w = w.sort_values(["game_id", "e"], kind="mergesort").drop_duplicates("game_id")
    w = w.merge(games[["game_id", "game_date", "margin", "tip"]], on="game_id", how="left")
    w["t"] = w["e"]
    w["lead_h"] = (w["tip"].values.astype("datetime64[ns]").astype("int64") - w["e"].values) / 3.6e12
    return grade(w)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rows", required=True, type=Path)
    ap.add_argument("--instants", required=True, type=Path)
    ap.add_argument("--games", required=True, type=Path)
    ap.add_argument("--table-cache", required=True, type=Path)
    ap.add_argument("--check-tables", type=Path, default=None)
    ap.add_argument("--check-bets", type=Path, default=None)
    ap.add_argument("--live-bets", type=Path, default=None)
    ap.add_argument("--last-season", type=int, default=2026)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--bets-out", type=Path, default=None)
    a = ap.parse_args(argv)
    t0 = time.time()
    last = a.last_season
    seasons = list(range(PAID_FIRST, last + 1))

    # The margin tables, walk-forward, with the spread build's own functions.
    tg = sb.load_games(a.table_cache)
    arch = sb.archive_lines(a.table_cache)
    paid = tg[(tg["season"] >= PAID_FIRST) & (tg["season"] <= last)]
    sp_close = sb.load_spread_rows(a.table_cache, set(paid["game_id"]))
    h = sb.history(tg, arch, sb.close_consensus(sp_close, tg), last)
    tables, sizes = {}, {}
    for s in range(PAID_FIRST, last + 2):
        tables[s], sizes[s] = sb.table_for(h, s)
    print(f"margin tables fitted ({time.time() - t0:.0f}s): training games {sizes}", flush=True)
    tcheck = sb.check_tables(tables, a.check_tables) if a.check_tables else None
    if tcheck:
        print("table check against", a.check_tables, json.dumps(tcheck), flush=True)
    spread_art_rel = f"models/saved/ncaab_spread_market_{last + 1}.json"
    spread_art = json.loads((fp.ROOT / spread_art_rel).read_text(encoding="utf-8"))
    theirs = md.from_json(spread_art["margin_table"])
    diff = {k: float(np.abs(tables[last + 1][k] - theirs[k]).max()) for k in ("pmf", "ge")}
    print(f"table {last + 1} against {spread_art_rel}: largest difference {diff}", flush=True)
    if any(v != 0.0 for v in diff.values()) or int(spread_art["season"]) != last + 1:
        raise SystemExit(f"{spread_art_rel} does not hold the table this build fits; not written")

    games = pd.read_parquet(a.games, columns=["game_id", "season", "game_date", "margin", "tip"])
    games["game_date"] = games["game_date"].astype(str).str[:10]
    games["tip"] = pd.to_datetime(games["tip"], utc=True)
    games = games[games["tip"].notna()]
    inst = bought_instants(a.instants)
    h2h = load_rows(a.rows, "h2h", fp.REF_BOOKS, inst)
    spr = load_rows(a.rows, "spreads", bq.BOOKS, inst)
    print(f"rows: h2h {len(h2h)}, spreads {len(spr)}; bought instants {len(inst)} "
          f"({time.time() - t0:.0f}s)", flush=True)

    lo_cut = min((fp.CUT,) + NEIGHBOURS)
    d = replay(h2h, spr, games, tables, seasons, lo_cut, t0)
    status_counts = d["status"].value_counts().to_dict()
    bets = bets_at(d, fp.CUT, games)
    per = by_season(bets, last)
    neighbours = {str(c): {k: v for k, v in by_season(bets_at(d, c, games), last).items()
                           if k in (f"{PAID_FIRST}-{last - 1}", str(last))} for c in NEIGHBOURS}
    min_ev = float(fp.ev_of(bets["prob"], bets["price"]).min())
    summary = {"cut": fp.CUT, "min_price": fp.MIN_PRICE, "min_other_books": fp.MIN_OTHER_BOOKS,
               "rule": "a bettable book's first moneyline post, priced off its own spread at that "
                       "moment, flagged quotes out, sides shorter than -200 out before the pick, "
                       "3+ other bettable moneylines up, edge above the cut, one bet a game",
               "posts_decided": int(len(d)), "statuses_at_lowest_cut": status_counts,
               "quotes_dropped_as_data_errors": int(d.attrs.get("quotes_dropped", 0)),
               # The data-error cap (models/ncaab_quote_bounds.EDGE_CAP) must sit
               # above every real edge: the largest bet, and the largest edge of
               # any post priced with 3+ other books up.
               "max_edge_bets": round(float(bets["edge"].max()), 4),
               "max_edge_priced_posts": round(float(
                   d.loc[d["status"].isin(["bets", "below_cut", "not_best", "edge_cap"]), "edge"].max()), 4),
               "priced_posts_with_3_others": int(d["status"].isin(
                   ["bets", "below_cut", "not_best", "edge_cap"]).sum()),
               "by_season": per, "neighbour_cuts": neighbours,
               "min_ev": round(min_ev, 4), "min_prob": round(float(bets["prob"].min()), 4),
               "books": bets["bookmaker"].value_counts().to_dict()}
    print("replay:", json.dumps(summary, indent=1), flush=True)
    check = comb = None
    if a.check_bets:
        r = research_bets(a.check_bets, "FP", fp.CUT)
        check = check_bets(bets, r)
        print("bet check against", a.check_bets, json.dumps(check, indent=1), flush=True)
    if a.live_bets:
        lv = research_bets(a.live_bets, "S15Lpre", om.CUT)
        c = combined(bets, lv)
        comb = {"live_15z_bets": int(len(lv)),
                f"{PAID_FIRST}-{last - 1}": summarize(c[c["season"] <= last - 1]),
                str(last): summarize(c[c["season"] == last]),
                "games_taken_by_first_post": int((c["src"] == "cand").sum()),
                "first_post_games_the_15z_model_also_bet": int(bets["game_id"].isin(lv["game_id"]).sum())}
        print("combined with the 15:00 UTC model:", json.dumps(comb, indent=1), flush=True)
    if a.bets_out:
        bets.to_parquet(a.bets_out, index=False)
    out = a.out or (fp.ROOT / f"models/saved/ncaab_moneyline_first_post_{last + 1}.json")
    art = {
        "kind": fp.ARTIFACT_KIND, "model_id": fp.MODEL_ID,
        "season": last + 1, "prior_season": last,
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "command": "python -m scripts.ncaab_moneyline_first_post_build --rows <rows.parquet> "
                   "--instants <ledger.parquet> --games <games.parquet> --table-cache <cache> "
                   f"--last-season {last}",
        "books": list(bq.BOOKS), "ref_books": list(fp.REF_BOOKS),
        "min_lead_min": int(fp.MIN_LEAD.total_seconds() // 60),
        "cut": fp.CUT, "min_price": fp.MIN_PRICE, "min_other_books": fp.MIN_OTHER_BOOKS,
        "isum_range": [om.ISUM_LO, om.ISUM_HI], "disagree_line": om.DISAGREE_LINE,
        "window": "none: each book's newest stored row",
        "margin_table_from": spread_art_rel,
        "margin_table_sha256": om.table_digest(spread_art["margin_table"]),
        "table_train_seasons": [sb.TABLE_FIRST, last], "table_train_games": sizes[last + 1],
        "table_check": tcheck,
        "replay": summary, "research_check": check, "combined_with_15z": comb,
    }
    out.write_text(json.dumps(art, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes) in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
