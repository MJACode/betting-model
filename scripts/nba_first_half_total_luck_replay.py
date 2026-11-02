"""Replay the LIVE `nba_first_half_total_luck` code on the research cache, against the lab.

The live model (models/nba_first_half_total_luck.decide) is run on 2023-24,
2024-25 and 2025-26 at the lab's own decision instants (decision point D: each
game's per-game purchase 45-75 minutes before tip, scripts.nba_game_harness
.per_event_times on the lab's own load), with:

  quotes   the archived per-game purchase rows of totals_h1, their created_at set
           to snapshot_at (the purchase's feed time IS its fetch instant; the
           archive's created_at is the day the rows were bought), passed through
           the LIVE write-time split (models.nba_book_numbers.split_main_rungs:
           one fetch at a time) and the LIVE shaping
           (models.nba_first_half_total_luck.quote_frame).
  games    the season's final games, box scores and owed games read by the
           totals card's own load (scripts.nba_total_luck_card.load_season, its
           SQL answered from the cache by scripts.nba_total_luck_replay.FrameConn)
  pricing  the committed artifact (models.nba_first_half_total_luck.ARTIFACT_PATH)

and compared, game by game, with what the lab graded:

  gaps     the lab's own (scripts.nba_game4_p3.f4_signal on
           scripts.nba_game2_luck's projection over every graded season). On this
           branch nba_game2_luck's projection IS models/nba_total_luck's, so this
           checks the inputs, not the ratings code; the sibling replay pins the
           ratings against the fourth search's own copy
           (tests/test_nba_team_total_luck_replay.py, LAB_HOME_PARTS_SHA256).
  bets     the lab's bet file for the shipped cell (P3_F4, D, totals_h1, over, cut
           2.0): game, book, line, price, T and the market-fair probability
  pricing  the lab's own period_market_pricing for each season (same probabilities)

It also states, on the matched bets, the decision lead (each must be a 'decide'
under the live timing) and the EV floor at the 2026-27 uplift (models.honest_ev
.gate, as the card applies it), grades the live bets on Q1 + Q2 points
(scripts.nba_game_harness.grade), and settles them through the LIVE settlement
(tracking.paper_tracker._first_half_points and _compute_result) from the cache's
nba_period_scores, against the lab's result on each bet.

WHAT THE MATCH DOES NOT PROVE. The purchase kept ONE listed pair per book
(odds_ingestor._parse_total_outcomes keeps the last pair a book lists), so every
archived fetch holds one number per book, the split has nothing to choose among,
and it sets nothing aside (rungs_listed, which this replay reports). So the replay
proves the live code decides as the lab did on the lab's quotes. It says nothing
about whether those quotes were each book's main number, and at BetRivers, betPARX
and probably Hard Rock they were not (quote_census). Live takes the real main
number, so it will not be offered the quotes behind some graded bets. --quote-bounds
re-grades without them (quote_bounds); models/nba_first_half_total_luck.py states
the numbers.

    NBA_RESEARCH_CACHE=... python -m scripts.nba_first_half_total_luck_replay [--seasons 2026 ...]
    NBA_RESEARCH_CACHE=... python -m scripts.nba_first_half_total_luck_replay --quote-bounds
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import models.nba_first_half_total_luck as fh  # noqa: E402
from models import nba_book_numbers as NB  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402
from scripts.nba_first_half_total_luck_build import BETS, cell_bets  # noqa: E402
from scripts.nba_total_luck_replay import FrameConn  # noqa: E402

LAB_SEASONS = (H.REGIME, *H.CHOOSE, H.CONFIRM)        # the lab's full-game load (P3 --full)
REPLAY_SEASONS = (2024, 2025, 2026)
# The books whose stored first-half pair mostly sits off the market's number, and
# how far apart a row's two prices must be, in points of probability, to read as
# an off-main rung (the re-grades of quote_bounds).
OFF_MAIN_BOOKS = ("betrivers", "betparx", "hardrockbet")
LOPSIDED_GAP = 0.06


def lab_bets(path: Path = BETS) -> pd.DataFrame:
    return cell_bets(path)


def split_archive(rows: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """The archived rows through the live write-time split, one fetch (one
    purchase instant) at a time. -> (rows as stored live, counts)."""
    main, alt = [], []
    for _, grp in rows.groupby("created_at", sort=True):
        m, a = NB.split_main_rungs(grp.to_dict("records"))
        main += m
        alt += a
    out = pd.DataFrame(main + alt, columns=rows.columns)
    counts = {"rows": int(len(rows)), "main": len(main), "alternate": len(alt),
              "by_market": out["market"].value_counts().to_dict()}
    return out, counts


def load(cache: Path = H.CACHE) -> dict:
    """Everything the replay reads, loaded once."""
    from scripts import nba_game4_p3 as P3
    data = H.load(cache, seasons=LAB_SEASONS, require_seasons=LAB_SEASONS)   # the lab's own load
    games_p = H.with_periods(data.games, cache)
    pe, graded = P3.load_derivatives(games_p, cache)
    times = H.per_event_times(pe, P3.POINT)
    o = pd.read_parquet(cache / "nba_odds.parquet", filters=[("market", "==", fh.MARKET)])
    o = o[(o["source"] == H.PER_EVENT_SOURCE) & (o["snapshot_type"] != "in_play")
          & o["game_id"].isin(set(data.games["game_id"]))].copy()
    o["created_at"] = o["snapshot_at"]                     # the live table's meaning
    for c in ("over_link", "under_link"):
        o[c] = None                                       # the purchase kept no links
    rows, split = split_archive(o[list(fh.QUOTE_ROW_COLS)])
    box = pd.read_parquet(cache / "nba_player_game_log.parquet",
                          columns=["game_id", "team", *fh.BOX_COLS])
    periods = pd.read_parquet(cache / "nba_period_scores.parquet",
                              columns=["game_id", "period", "home_points", "away_points"])
    sched = pd.read_parquet(cache / "nba_schedule.parquet",
                            columns=["game_id", "season", "game_type", "game_date",
                                     "home_team", "away_team", "status_text"])
    games = pd.read_parquet(cache / "nba_games.parquet",
                            columns=["game_id", "season", "game_date", "home_team", "away_team",
                                     "home_score", "away_score"])
    return {"data": data, "games_p": games_p, "pe": pe, "graded": graded, "times": times,
            "rows": rows, "split": split, "box": box, "schedule": sched, "games": games,
            "periods": periods}


def lab_gaps(ld: dict) -> pd.Series:
    """The lab's gap per game, computed the lab's way: one projection over
    every graded season (scripts.nba_game4_p3.full)."""
    from scripts import nba_game2_luck as L
    from scripts import nba_game4_p3 as P3
    data = ld["data"]
    graded_games = data.games[data.games["season"].isin(ld["graded"])]
    proj = L.f4_projections(graded_games, L.team_box(ld["box"], data.games))
    s = P3.f4_signal(proj)
    return s[s["market"] == fh.MARKET].set_index("game_id")["strength"]


def pricing_matches(ld: dict, art: dict, seasons) -> dict:
    """The artifact's distribution against the lab's own period_market_pricing."""
    from scripts import nba_game4_p3 as P3
    lab = P3.period_market_pricing(H.pinnacle_close(ld["data"]), ld["games_p"],
                                   tuple(int(s) for s in seasons))
    out = {}
    for s in seasons:
        a, b = fh.pricing_dist(art, s), lab[(int(s), fh.MARKET)]
        out[int(s)] = bool(a.n == b.n and np.array_equal(a.win_whole, b.win_whole)
                           and np.array_equal(a.push_whole, b.push_whole)
                           and np.array_equal(a.win_half, b.win_half))
    return out


def rungs_listed(rows: pd.DataFrame) -> dict:
    """How many numbers the stored rows hold per (game, book, fetch). One
    everywhere means the main-number rule had nothing to choose among, so a match
    against it is true of any file and is evidence of nothing."""
    n = rows.groupby(["game_id", "bookmaker", "created_at"]).size()
    most = int(n.max()) if len(n) else 0
    return {"most_per_book_and_fetch": most, "fetches_with_a_choice": int((n > 1).sum()),
            "the_main_rule_chose_anything": most > 1}


def quote_census(rows: pd.DataFrame) -> pd.DataFrame:
    """Per book, the stored first-half rows against Pinnacle's number in the same
    game (Pinnacle's latest row): the share at least 1.5 points off it and the
    share exactly on it. A row stored from a ladder cut to one rung shows here."""
    main = rows[rows["market"] == fh.MARKET]
    pin = (main[main["bookmaker"] == "pinnacle"].sort_values("snapshot_at")
           .drop_duplicates("game_id", keep="last").set_index("game_id")["total_line"])
    x = main[main["bookmaker"] != "pinnacle"].assign(_pin=lambda d: d["game_id"].map(pin))
    x = x[x["_pin"].notna()]
    off = (x["total_line"] - x["_pin"]).abs()
    return (x.assign(_far=off >= 1.5, _on=off == 0).groupby("bookmaker")
            .agg(rows=("_far", "size"), far=("_far", "mean"), on=("_on", "mean"))
            .assign(far=lambda d: (100.0 * d["far"]).round(1),
                    on=lambda d: (100.0 * d["on"]).round(1))
            .sort_values("far", ascending=False))


def _graded_bets(ld: dict, art: dict, rows: pd.DataFrame, seasons=REPLAY_SEASONS) -> pd.DataFrame:
    """The live rule on `rows`, graded on Q1 + Q2 points, without the EV floor."""
    from scripts.nba_total_luck_card import load_season
    out = []
    for season in seasons:
        games = ld["data"].games[ld["data"].games["season"] == season]
        times = ld["times"][ld["times"]["game_id"].isin(set(games["game_id"]))]
        targets = games[games["game_id"].isin(set(times["game_id"]))][
            ["game_id", "season", "game_date", "home_team", "away_team"]]
        final, box, sched = load_season(FrameConn(ld["games"], ld["schedule"], ld["box"]),
                                        season, "9999-12-31")
        prior = [s for s in art["bucket"] if int(s) < season]
        bets = fh.decide(targets, fh.quote_frame(rows, games), box, final, times, art,
                         scheduled=sched, bucket_uplift=None if prior else 0.0)[0]
        out += [{"game_id": b.game_id, "season": season, "market": fh.MARKET, "side": fh.SIDE,
                 "line": b.line, "price": b.price, "book": b.book} for b in bets]
    bets = pd.DataFrame(out).merge(ld["data"].games[["game_id", "game_date"]], on="game_id")
    return H.grade(bets, ld["games_p"])


def _bound(graded: pd.DataFrame, base: pd.DataFrame) -> dict:
    lo, hi = H.ci95(graded)
    m = graded.merge(base, on="game_id", how="outer", suffixes=("", "_b"), indicator=True)
    both = m[m["_merge"] == "both"]
    return {"bets": int(len(graded)), "units": round(float(graded["units"].sum()), 2),
            "roi": round(100.0 * float(graded["units"].sum() / graded["risk"].sum()), 2),
            "interval": (round(100.0 * lo, 2), round(100.0 * hi, 2)),
            "offers_changed": int(((both["book"] != both["book_b"])
                                   | (both["line"] != both["line_b"])
                                   | (both["price"] != both["price_b"])).sum()),
            "results_flipped": int((both["result"] != both["result_b"]).sum()),
            "games_gained": int((m["_merge"] == "left_only").sum()),
            "games_lost": int((m["_merge"] == "right_only").sum()),
            "price_range": (float(graded["price"].min()), float(graded["price"].max()))}


def quote_bounds(ld: dict, art: dict) -> dict:
    """What the lab's off-main quotes are worth: the live rule re-graded without
    them, three ways. The rule is unchanged in each, so the same games are bet."""
    rows = ld["rows"]
    lopsided = np.abs(H.imp(rows["over_price"]) - H.imp(rows["under_price"])) > LOPSIDED_GAP
    book = rows["bookmaker"]
    base = _graded_bets(ld, art, rows)
    return {
        "base": _bound(base, base),
        "betrivers_betparx_lopsided_removed": _bound(_graded_bets(
            ld, art, rows[~(book.isin(OFF_MAIN_BOOKS[:2]) & lopsided)]), base),
        "and_hard_rock_lopsided_removed": _bound(_graded_bets(
            ld, art, rows[~(book.isin(OFF_MAIN_BOOKS) & lopsided)]), base),
        "all_three_removed": _bound(_graded_bets(ld, art, rows[~book.isin(OFF_MAIN_BOOKS)]), base),
    }


def lab_prices() -> dict:
    """The price range the lab's bets lay, across all books and at the books whose
    rows look like main numbers."""
    lb = lab_bets()
    four = lb[~lb["book"].isin(OFF_MAIN_BOOKS)]
    return {"all": (float(lb["price"].min()), float(lb["price"].max()), int(len(lb))),
            "main_number_books": (float(four["price"].min()), float(four["price"].max()),
                                  int(len(four))),
            "at_the_three_books": lb[lb["book"].isin(OFF_MAIN_BOOKS)]["book"].value_counts().to_dict(),
            "above_plus_105_by_book": lb[lb["price"] > 105]["book"].value_counts().to_dict(),
            "minus_125_or_worse_by_book": lb[lb["price"] <= -125]["book"].value_counts().to_dict()}


def split_keeps_the_labs_rows(ld: dict, season: int) -> bool:
    """The rows the live split stores under totals_h1 are the lab's own
    (models.nba_book_numbers.main_rungs on its load). True of any file with one
    number per book, so this is NOT evidence that the rows are main numbers
    (rungs_listed)."""
    games = ld["data"].games[ld["data"].games["season"] == season]
    pe = ld["pe"]
    lab = NB.main_rungs(pe[(pe["market"] == fh.MARKET) & pe["game_id"].isin(set(games["game_id"]))])
    live = fh.quote_frame(ld["rows"], games)
    key = ["game_id", "book", "fetch_at", "line", "price_a", "price_b", "coherent"]
    a = lab[key].sort_values(key).reset_index(drop=True)
    b = live[key].sort_values(key).reset_index(drop=True)
    return bool(len(a) == len(b) and a.equals(b))


class _PeriodConn:
    """Answers tracking.paper_tracker._first_half_points' one read from the cache."""

    def __init__(self, periods: pd.DataFrame):
        self._by = {g: list(zip(x["period"], x["home_points"], x["away_points"]))
                    for g, x in periods.groupby("game_id")}

    def execute(self, sql, params):
        assert "FROM nba_period_scores WHERE game_id" in sql, sql
        rows = self._by.get(params[0], [])

        class _Rows:
            @staticmethod
            def fetchall():
                return rows
        return _Rows


def settled_live(ld: dict, bets, games: pd.DataFrame) -> dict[str, str | None]:
    """{game_id: W | L | P, or None when the live settlement leaves it pending}."""
    from tracking.paper_tracker import _compute_result, _first_half_points
    conn = ld.get("period_conn")
    if conn is None:
        conn = ld["period_conn"] = _PeriodConn(ld["periods"])
    finals = games.set_index("game_id")[["home_score", "away_score"]]
    out: dict[str, str | None] = {}
    for b in bets:
        home, away = finals.loc[b.game_id]
        points = _first_half_points(conn, b.game_id, home, away)
        if points is None:
            out[b.game_id] = None
            continue
        result = _compute_result(fh.SIDE, fh.MARKET, points[0], points[1], None, None, 0,
                                 b.price, None, b.line, 0.0)[0]
        out[b.game_id] = {"WIN": "W", "LOSS": "L", "PUSH": "P"}.get(result, result)
    return out


def replay(ld: dict, season: int, art: dict | None = None) -> dict:
    data, box = ld["data"], ld["box"]
    art = art or fh.load_artifact()
    games = data.games[data.games["season"] == season]
    times = ld["times"][ld["times"]["game_id"].isin(set(games["game_id"]))]
    quotes = fh.quote_frame(ld["rows"], games)
    targets = games[games["game_id"].isin(set(times["game_id"]))][
        ["game_id", "season", "game_date", "home_team", "away_team"]]
    # The card's own load of the season, every game before the season's end.
    from scripts.nba_total_luck_card import load_season
    final, season_box, sched = load_season(FrameConn(ld["games"], ld["schedule"], box),
                                           season, "9999-12-31")
    lab_final = games[["game_id", "home_score", "away_score"]].sort_values("game_id")
    live_final = final[["game_id", "home_score", "away_score"]].sort_values("game_id")
    same_population = (lab_final["game_id"].tolist() == live_final["game_id"].tolist()
                       and np.allclose(lab_final[["home_score", "away_score"]].to_numpy(float),
                                       live_final[["home_score", "away_score"]].to_numpy(float)))
    # 2023-24 has no graded season before it to fit an uplift on; it moves only
    # the written probability, never the bet, so 0 is used there.
    prior = [s for s in art["bucket"] if int(s) < season]
    bets, decisions, diag = fh.decide(targets, quotes, season_box, final, times, art,
                                      scheduled=sched,
                                      bucket_uplift=None if prior else 0.0)

    lab_gap = ld.get("lab_gaps")
    if lab_gap is None:
        lab_gap = ld["lab_gaps"] = lab_gaps(ld)
    live_gap = {d.game_id: d.gap_total for d in decisions if d.gap_total is not None}
    in_t = lab_gap[lab_gap.index.isin(targets["game_id"])]
    common = sorted(set(live_gap) & set(in_t.index))
    diff = np.array([abs(live_gap[g] - in_t[g]) for g in common])
    only_lab = sorted(set(in_t.index) - set(live_gap))
    only_live = sorted(set(live_gap) - set(lab_gap.index))

    lb = lab_bets()
    lb = lb[lb["season"] == season]
    key = ["game_id", "book", "line", "price"]
    live = pd.DataFrame([{"game_id": b.game_id, "book": b.book, "line": b.line, "price": b.price,
                          "T": b.fetch_at, "p_fair": b.p_fair, "gap_total": b.gap_total}
                         for b in bets], columns=key + ["T", "p_fair", "gap_total"])
    m = lb[key + ["T", "p_win"]].merge(live, on=key, how="outer", indicator=True)
    both = m[m["_merge"] == "both"]
    t_ok = bool((pd.to_datetime(both["T_x"], utc=True)
                 == pd.to_datetime(both["T_y"], utc=True)).all())
    p_ok = bool(np.allclose(both["p_win"], both["p_fair"], atol=1e-9)) if len(both) else True

    tips = games.set_index("game_id")["tip"]
    leads = [fh.lead_minutes(tips[b.game_id], b.fetch_at) for b in bets]
    timing = [fh.timing(tips[b.game_id], b.fetch_at, b.fetch_at) for b in bets]
    # The card's EV floor (models.honest_ev.gate) on each bet's probability at
    # the 2026-27 uplift.
    from models.honest_ev import gate
    u27 = fh.uplift(art, 2027)
    gates = [(b, gate(fh.MODEL_ID, b.p_fair + u27, b.price)) for b in bets]
    below = [{"game_id": b.game_id, "book": b.book, "line": b.line, "price": b.price,
              "ev": round(g.ev, 4), "floor": g.floor} for b, g in gates if not g.clears]
    graded = H.grade(pd.DataFrame([{"game_id": b.game_id, "season": season,
                                    "market": fh.MARKET, "side": fh.SIDE, "line": b.line,
                                    "price": b.price, "book": b.book} for b in bets],
                                  columns=["game_id", "season", "market", "side", "line",
                                           "price", "book"]),
                     ld["games_p"][ld["games_p"]["season"] == season])
    settled = settled_live(ld, bets, games)
    lab_result = lb.set_index("game_id")["result"].to_dict()
    return {
        "season": season, "games_decided": int(diag["games"]), "diag": diag,
        "decisions": len(decisions),
        "decisions_with_an_offer": sum(1 for d in decisions if d.book is not None),
        "load_season_is_the_lab_population": bool(same_population),
        "load_season_games": int(len(final)), "lab_games": int(len(lab_final)),
        "gap_compared": len(common),
        "gap_max_abs_diff": float(diff.max()) if len(diff) else 0.0,
        "gap_only_lab": only_lab, "gap_only_live": only_live,
        "lab_bets": int(len(lb)), "live_bets": int(len(live)),
        "bets_matched": int((m["_merge"] == "both").sum()),
        "lab_only": m[m["_merge"] == "left_only"][key].to_dict("records"),
        "live_only": m[m["_merge"] == "right_only"][key].to_dict("records"),
        "decision_time_identical": t_ok, "fair_probability_identical": p_ok,
        "lead_min": (round(min(leads), 1), round(float(np.median(leads)), 1),
                     round(max(leads), 1)) if leads else None,
        "every_bet_decides_under_live_timing": all(x == "decide" for x in timing),
        "below_ev_floor_at_2026_27_uplift": below,
        "record": graded["result"].value_counts().to_dict(),
        "units": round(float(graded["units"].sum()), 2),
        "risk": round(float(graded["risk"].sum()), 2),
        "split_keeps_the_labs_rows": split_keeps_the_labs_rows(ld, season),
        "settled_pending": sorted(g for g, r in settled.items() if r is None),
        "settled_differently": sorted(g for g, r in settled.items()
                                      if r is not None and r != lab_result.get(g)),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seasons", type=int, nargs="+", default=list(REPLAY_SEASONS))
    ap.add_argument("--quote-bounds", action="store_true",
                    help="the stored rows by book, and the re-grades without the off-main quotes")
    a = ap.parse_args()
    ld = load()
    art = fh.load_artifact()
    print("split:", ld["split"])
    print("rungs listed:", rungs_listed(ld["rows"]))
    if a.quote_bounds:
        print(quote_census(ld["rows"]).to_string())
        print("prices:", lab_prices())
        for name, bound in quote_bounds(ld, art).items():
            print(name, bound, flush=True)
        return
    print("pricing equals the lab's period_market_pricing:", pricing_matches(ld, art, a.seasons))
    tot = {"lab_bets": 0, "live_bets": 0, "bets_matched": 0, "units": 0.0, "risk": 0.0}
    below = []
    for s in a.seasons:
        r = replay(ld, s, art)
        print(r)
        for k in tot:
            tot[k] += r[k]
        below += r["below_ev_floor_at_2026_27_uplift"]
    tot["units"], tot["risk"] = round(tot["units"], 2), round(tot["risk"], 2)
    roi = 100.0 * tot["units"] / tot["risk"] if tot["risk"] else float("nan")
    print(f"pooled: {tot} ({roi:+.1f}%) | below the EV floor at the 2026-27 uplift: {below}")


if __name__ == "__main__":
    main()
