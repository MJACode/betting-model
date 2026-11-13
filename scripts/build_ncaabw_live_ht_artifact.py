"""Build and check the women's halftime total model's artifact
(models/saved/ncaabw_live_ht_2027.json, read by models/ncaabw_live_loop.py).

    PYTHONPATH=. python -m scripts.build_ncaabw_live_ht_artifact            # replay and report
    PYTHONPATH=. python -m scripts.build_ncaabw_live_ht_artifact --write    # and write the artifact

WHAT IT DOES. It replays the PRODUCTION decision (models.ncaabw_live_ht.
read_break, on plays parsed by data.ingestors.ncaabw_pbp) on every five-minute
snapshot of the two priced seasons:

  2025-26 with a model fitted on 2024-25            walk-forward
  2024-25 with a model fitted on 2025-26            a second look, NOT walk-forward
  2026-27 to date with a model fitted on 2024-26    walk-forward, the artifact's model

TWICE, on two readings of the play list (models.ncaabw_live_ht.states_from_rows):

  research    each play's own running score, the reading the research used.
              The first two folds must equal the research's numbers
              (scripts/ncaabw_research/inplay_checks.py, "halftime"): 689
              bets, 398-291, +66.59 units and 303 bets, 182-120, +44.96 units
              at EV >= 0.05. That shows this code is the research's rule.
  production  the score is the highest logged so far (the research's reading
              gave 54 of those 689 bets a wrong halftime score). This is what
              the loop does, so THIS replay is the model's evidence, and its
              numbers are pinned below so a change to the path is seen.

It REFUSES to write an artifact unless both hold.

WHAT IT READS. The research cache (scripts/ncaabw_research/README.md): the
schedule and finals, each book's last pre-game spread and total, the in-play
quotes of every snapshot, and sportsdataverse's play-by-play files. Every one
is a copy of what Supabase holds (games, odds, ncaabw_inplay_quotes,
ncaabw_pbp), read locally so a build costs production nothing.

ONE DIFFERENCE FROM THE LOOP, named: a snapshot stamped after the history's
last logged play of a game is not read (the grade left it out; a live play
list always ends at "now", so the loop has no such case).

Stake: one unit to win, risk capped at 3, at the quote's price. Intervals are
95%, resampled by date.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from data.ingestors import ncaabw_pbp  # noqa: E402
from models import ncaabw_live_ht as M  # noqa: E402
from scripts.ncaabw_research._paths import CACHE  # noqa: E402

CUT = 0.05
CUTS = (0.02, 0.03, 0.05, 0.08, 0.12)
VERSION = "ncaabw_live_ht_2027_v1"
FOLDS = (  # label, the seasons fitted on, the season replayed
    ("2025-26, model from 2024-25 (walk-forward)", (2025,), 2026),
    ("2024-25, model from 2025-26 (second look)", (2026,), 2025),
    ("2026-27 to date, model from 2024-26 (walk-forward)", (2025, 2026), 2027),
)
READINGS = ("research", "production")
# (bets, won, lost, units) at CUT, by reading and season replayed.
EXPECTED = {
    "research": {2026: (689, 398, 291, 66.59), 2025: (303, 182, 120, 44.96)},
    "production": {2026: (669, 398, 271, 89.96), 2025: (298, 178, 119, 42.10)},
}


def load_games() -> pd.DataFrame:
    g = pd.read_parquet(CACHE / "games.parquet")
    g = g[g["home_score"].notna()].copy()
    g["final_t"] = g["home_score"].astype(float) + g["away_score"].astype(float)
    g["game_date"] = g["game_date"].astype(str).str[:10]
    return g


def priors() -> pd.DataFrame:
    """Each book's last pre-game spread and total -> M.prior_from_closes, per game."""
    B = pd.read_parquet(CACHE / "boards.parquet")
    c = B[(B["lead"] == 0) & B["market"].isin(["spreads", "totals"])]
    out = {}
    for gid, x in c.groupby("game_id"):
        p = M.prior_from_closes(list(zip(x["market"], x["bookmaker"],
                                         x["spread_home"].where(x["spread_home"].notna(), None),
                                         x["total_line"].where(x["total_line"].notna(), None))))
        if p is not None:
            out[gid] = p
    return pd.DataFrame.from_dict(out, orient="index", columns=["prior_m", "prior_t"])


def load_states(g: pd.DataFrame, wanted: set) -> tuple[dict, dict]:
    """({reading: {game_id: M.States}}, {game_id: the play list's own halftime
    score}), through the production parser."""
    ev = g[g["game_id"].isin(wanted) & g["espn_event_id"].notna()]
    out = {r: {} for r in READINGS}
    half = {}
    for season in sorted({s for _l, tr, te in FOLDS for s in (*tr, te)}):
        frame = ncaabw_pbp.release_frame(season, from_dir=str(CACHE))
        if frame is None:
            continue
        es = ev[ev["season"] == season]
        events = {int(r.espn_event_id): {"game_id": r.game_id, "game_date": r.game_date,
                                         "home_espn_id": r.home_espn_id, "away_espn_id": r.away_espn_id,
                                         "home_score": r.home_score, "away_score": r.away_score}
                  for r in es.itertuples(index=False)}
        frame = frame[frame["game_id"].astype("int64").isin(set(events))]
        stats: dict = {}
        for e, _sw, rows in ncaabw_pbp.parsed_games(frame, events, season, stats):
            for reading in READINGS:
                st = M.states_from_rows(rows, as_logged=reading == "research")
                if st is not None:
                    out[reading][e["game_id"]] = st
            first = [r for r in rows if r["period"] is not None and r["period"] <= 2
                     and r["home_score"] is not None and r["away_score"] is not None]
            if first:
                half[e["game_id"]] = (max(r["home_score"] for r in first), max(r["away_score"] for r in first))
        print(f"  {season}: {stats.get('games_in_file', 0):,} wanted games in the play-by-play file, "
              f"{stats.get('team_mismatch', 0)} with other teams than ours", flush=True)
    return out, half


def training(states: dict, g: pd.DataFrame, pri: pd.DataFrame, seasons) -> pd.DataFrame:
    gi = g.set_index("game_id")
    rows = [M.training_rows(st, pri.at[gid, "prior_t"], gi.at[gid, "final_t"])
            for gid, st in states.items() if gid in pri.index and gi.at[gid, "season"] in seasons]
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def replay(Q: pd.DataFrame, states: dict, g: pd.DataFrame, pri: pd.DataFrame, model: M.TotalModel,
           season: int) -> tuple[pd.DataFrame, dict]:
    """The production decision on every snapshot of a season, in time order.
    Returns one row per decided game, and the counts of the rest."""
    books = tuple(config.BEST_LINE_BOOKMAKERS)
    gi = g.set_index("game_id")
    out, counts = [], {"games": 0, "decided": 0, "break_passed_undecided": 0, "never_in_break": 0}
    for gid, q in Q.groupby("game_id", sort=False):
        if gid not in states or gid not in pri.index or gid not in gi.index or gi.at[gid, "season"] != season:
            continue
        counts["games"] += 1
        st, prior_t = states[gid], float(pri.at[gid, "prior_t"])
        end = "never_in_break"
        for ts, x in q.groupby("snapshot_ts", sort=True):
            if pd.Timestamp(ts).as_unit("ns").value > st.wall[-1]:
                break                                   # after the history's last logged play
            r = M.read_break(x, st, ts, prior_t, model, books)
            if r.status == "early":
                continue
            if r.status == "past":
                break
            end = "break_passed_undecided"              # a read inside the break
            if r.status == "decided":
                b = r.best
                u, risk = M.units(b["side"], b["line"], b["price"], gi.at[gid, "final_t"])
                el = r.offers[r.offers["eligible"]]
                bo, bu = el.loc[el["over_price"].idxmax()], el.loc[el["under_price"].idxmax()]
                out.append({"game_id": gid, "game_date": gi.at[gid, "game_date"], "snapshot_ts": ts,
                            "book": b["book"], "side": b["side"], "line": float(b["line"]),
                            "price": float(b["price"]), "ev": float(b["ev"]), "prob": float(b["prob"]),
                            "h_pts": int(b["h_pts"]), "a_pts": int(b["a_pts"]), "units": u, "risk": risk,
                            "stamp": b["stamp"], "final_t": float(gi.at[gid, "final_t"]),
                            "other_price": float(b["under_price"] if b["side"] == "over" else b["over_price"]),
                            "blind_over_line": float(bo["line"]), "blind_over_price": float(bo["over_price"]),
                            "blind_under_line": float(bu["line"]), "blind_under_price": float(bu["under_price"]),
                            "eligible_quotes": int(len(el))})
                end = "decided"
                break
        counts[end] += 1
    return pd.DataFrame(out), counts


def line_of(b: pd.DataFrame, label: str) -> str:
    if not len(b):
        return f"  {label:40s}    0 bets"
    u, r = b["units"].values, b["risk"].values
    ud = pd.Series(u).groupby(b["game_date"].values).sum().values
    rd = pd.Series(r).groupby(b["game_date"].values).sum().values
    idx = np.random.default_rng(20261111).integers(0, len(ud), size=(3000, len(ud)))
    lo, hi = np.percentile(ud[idx].sum(axis=1) / rd[idx].sum(axis=1) * 100, [2.5, 97.5])
    return (f"  {label:40s} {len(b):5d} bets {int((u > 0).sum())}-{int((u < 0).sum())}  {u.sum():+8.2f}u "
            f"{u.sum() / r.sum() * 100:+6.2f}% [{lo:+5.1f}, {hi:+5.1f}]")


def summary(b: pd.DataFrame) -> dict:
    u = b["units"].values
    return {"bets": int(len(b)), "won": int((u > 0).sum()), "lost": int((u < 0).sum()),
            "units": round(float(u.sum()), 2),
            "roi_pct": round(float(u.sum() / b["risk"].sum() * 100), 2) if len(b) else None,
            "price_min": float(b["price"].min()) if len(b) else None,
            "price_max": float(b["price"].max()) if len(b) else None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--write", action="store_true", help="write the artifact when the replay matches")
    ap.add_argument("--keep", help="also save each fold's decisions as parquet in this folder")
    a = ap.parse_args(argv)

    g = load_games()
    pri = priors()
    Q = pd.read_parquet(CACHE / "inplay_quotes.parquet")
    Q = Q[Q["market"] == "totals"].rename(columns={"bookmaker": "book", "last_update": "stamp"})
    Q = Q[["snapshot_ts", "game_id", "book", "stamp", "total_line", "over_price", "under_price"]]
    print(f"games with a pre-game spread and total {len(pri):,}; with in-play total quotes {Q['game_id'].nunique():,}")
    all_states, half = load_states(g, set(pri.index) | set(Q["game_id"]))
    print(f"games with a play-by-play {len(all_states['production']):,}")

    season_of = dict(zip(g["game_id"], g["season"]))
    replays, fitted, ok = {r: {} for r in READINGS}, {}, True
    for reading in READINGS:
        states = all_states[reading]
        print(f"\n\n################ the {reading} reading of the play list ################")
        for label, tr_s, te_s in FOLDS:
            tr = training(states, g, pri, tr_s)
            if not len(tr):
                print(f"\n=== {label}: no games to fit on")
                ok = False
                continue
            model = M.fit(tr)
            fitted[(reading, tr_s)] = (model, len(tr), int(sum(1 for gid in states if gid in pri.index
                                                               and season_of[gid] in tr_s)))
            dec, counts = replay(Q, states, g, pri, model, te_s)
            print(f"\n=== {label}\n  fitted on {len(tr):,} states; mean {np.round(model.b, 4)} variance "
                  f"{np.round(model.s, 2)}\n  {counts}")
            if not len(dec):
                continue
            dec["half_h"] = dec["game_id"].map(lambda x: half.get(x, (np.nan, np.nan))[0])
            dec["half_a"] = dec["game_id"].map(lambda x: half.get(x, (np.nan, np.nan))[1])
            dec["state_is_half"] = (dec["h_pts"] == dec["half_h"]) & (dec["a_pts"] == dec["half_a"])
            for cut in CUTS:
                print(line_of(dec[dec["ev"] >= cut], f"EV >= {cut:.2f}"))
            bets = dec[dec["ev"] >= CUT]
            print(line_of(bets[bets["state_is_half"]], "at the cut, state = the list's half"))
            print(line_of(bets[~bets["state_is_half"]], "at the cut, state is another score"))
            if len(bets):
                days = bets.groupby("game_date").size()
                print(f"  at {CUT}: prices {bets['price'].min():.0f} to {bets['price'].max():.0f} (median "
                      f"{bets['price'].median():.0f}); shorter than -150: {int((bets['price'] < -150).sum())}; days "
                      f"with a bet {len(days)}, a day median {days.median():.0f}, 90% {days.quantile(0.9):.0f}, max "
                      f"{days.max()}")
                print("  claimed against won (every decided game, pushes out):")
                for lo, hi in ((0.0, 0.52), (0.52, 0.55), (0.55, 0.58), (0.58, 0.62), (0.62, 0.70), (0.70, 1.01)):
                    z = dec[(dec["prob"] >= lo) & (dec["prob"] < hi) & (dec["units"] != 0)]
                    if len(z):
                        zb = z[z["ev"] >= CUT]
                        print(f"    claimed {lo:.2f}-{hi:.2f}: n {len(z):4d}  claimed {z['prob'].mean():.3f}  won "
                              f"{(z['units'] > 0).mean():.3f}   bets {len(zb):4d} {zb['units'].sum():+7.2f}u")
            replays[reading][te_s] = {"label": label, "counts": counts, **summary(bets)}
            if a.keep:
                Path(a.keep).mkdir(parents=True, exist_ok=True)
                dec.to_parquet(Path(a.keep) / f"ht_decisions_{reading}_{te_s}.parquet", index=False)
            want = EXPECTED[reading].get(te_s)
            got = (len(bets), int((bets["units"] > 0).sum()), int((bets["units"] < 0).sum()),
                   round(float(bets["units"].sum()), 2))
            if want is None:
                print(f"  not pinned: this replay {got}")
                ok &= te_s not in EXPECTED["research"]         # the two graded seasons must be pinned
            else:
                ok &= got == want
                print(f"  against the pinned numbers: {'MATCHES' if got == want else 'DIFFERS'} "
                      f"(pinned {want}, this replay {got})")

    if not ok:
        print("\nA replay does not equal its pinned numbers. No artifact written.")
        return 1
    if not a.write:
        print("\nBoth replays equal their pinned numbers. Run with --write to write the artifact.")
        return 0
    model, n_states, n_games = fitted[("production", (2025, 2026))]
    art = {
        "kind": M.ARTIFACT_KIND, "version": VERSION, "model_id": M.MODEL_ID, "season": M.SEASON,
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cut": CUT, "total": model.to_dict(),
        "fitted_on": {"seasons": [2025, 2026], "games": n_games, "states": n_states,
                      "what": "the score every 30 seconds of regulation of every game with a pre-game "
                              "spread and total and a play-by-play"},
        "rule": {"price_band": list(M.PRICE_BAND), "outlier_pts": M.OUTLIER_PTS, "min_others": M.MIN_OTHERS,
                 "line_range": list(M.LINE_RANGE), "cadence_min": M.CADENCE_MIN,
                 "fetch_after_sec": M.FETCH_AFTER_SEC, "books": list(config.BEST_LINE_BOOKMAKERS)},
        "replay": {r: {str(k): v for k, v in by.items()} for r, by in replays.items()},
        "evidence": "docs/sports/ncaabw.md, 'In play'",
    }
    out = ROOT / M.ARTIFACT_PATH
    out.write_text(json.dumps(art, indent=1) + "\n", encoding="utf-8")
    M.load_artifact(out)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
