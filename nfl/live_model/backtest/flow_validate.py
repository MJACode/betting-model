"""
Grade the flow model against REAL historical prop lines.

    python -m live_model.backtest.flow_validate

This is the test that settles the question. Everything measured so far is
against a RECONSTRUCTED anchor: our own guess at what a book's live number
would have been. That guess is fair by construction (it goes over about half
the time) and it blends in today's pace, but it is still our guess, and the
control in flow_eval shows that a meaningful slice of the apparent edge is just
our anchor having a worse functional form than a real book's.

Here the line is the book's actual number. There is nothing left to argue about
except whether the bets won.

THE SAME DECOMPOSITION IS REPORTED. The full model and the anchor-only control
are both graded against the real line, because the interesting quantity is
still how much GAME FLOW adds, not the headline. If the control also beats real
lines then books are lazier than assumed, which would be a finding in itself;
if only the full model does, the flow thesis is what is carrying it.

NAME MATCHING. Prop payloads name players; nflverse uses gsis ids. The join
goes through the nflverse players file, normalised, and anything that does not
resolve is DROPPED and counted rather than guessed onto a similar name. A prop
matched to the wrong player is worse than a prop dropped.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import ARTIFACT_DIR, PBP_DIR
from ..engine.prop_flow import FLOW_MARKETS, predict_flow, train_flow
from .flow_eval import (
    ANCHOR_ONLY_FEATURES, BREAKEVEN, GATES, apply_anchor, fit_time_curve,
    load_rows,
)

SNAP_DIR = ARTIFACT_DIR / "prop_snaps"
PLAYERS = PBP_DIR / "players.parquet"

# Odds API market key -> our market key. Identical today, kept explicit so a
# rename upstream fails loudly instead of silently dropping a market.
MARKET_MAP = {m: m for m in FLOW_MARKETS}


def norm_name(name: str) -> str:
    """Accent, punctuation and suffix insensitive. Same shape as the platform's
    UFC and WNBA name resolvers."""
    if not isinstance(name, str):
        return ""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace(".", " ").replace("'", "").replace("-", " ")
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def name_index(era_ids: set | None = None) -> dict:
    """
    normalised name -> gsis id.

    Suffix stripping makes fathers and sons collide: "Marvin Harrison Jr."
    normalises onto "marvin harrison", who also played from 1996. Rather than
    guessing, ambiguous names are resolved by asking which candidate actually
    appears in the play-by-play era we are grading. If exactly one does, that
    is the player; if none or several do, the name resolves to NOTHING and its
    lines are dropped and counted. A prop matched to the wrong player is worse
    than a prop dropped.
    """
    if not PLAYERS.exists():
        raise SystemExit(
            f"{PLAYERS} missing. Fetch it from the nflverse players release.")
    p = pd.read_parquet(PLAYERS, columns=["gsis_id", "display_name"])
    p = p.dropna(subset=["gsis_id", "display_name"])
    p["norm"] = p["display_name"].map(norm_name)

    idx = {}
    for norm, grp in p.groupby("norm"):
        ids = list(dict.fromkeys(grp["gsis_id"]))
        if len(ids) == 1:
            idx[norm] = ids[0]
            continue
        if era_ids:
            live = [i for i in ids if i in era_ids]
            if len(live) == 1:
                idx[norm] = live[0]
    return idx


def load_snapshots() -> pd.DataFrame:
    """
    Flatten the cached prop payloads into one row per (event, market, player,
    side).

    Only DraftKings and FanDuel are kept: those are the books a bet actually
    gets down at, and averaging a price across books that would not take the
    wager inflates the measured edge.
    """
    if not SNAP_DIR.exists():
        raise SystemExit(
            f"{SNAP_DIR} missing. Pull snapshots with "
            f"live_model.backtest.pull_prop_snaps --run first.")
    keep_books = {"draftkings", "fanduel"}
    rows = []
    for path in sorted(SNAP_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict) or "_error" in payload:
            continue
        ts = payload.get("timestamp")
        data = payload.get("data")
        if not isinstance(data, dict):
            continue
        for bk in data.get("bookmakers") or []:
            if bk.get("key") not in keep_books:
                continue
            for mk in bk.get("markets") or []:
                market = MARKET_MAP.get(mk.get("key"))
                if market is None:
                    continue
                for oc in mk.get("outcomes") or []:
                    if oc.get("point") is None or oc.get("price") is None:
                        continue
                    rows.append({
                        "ts": ts, "event_id": str(data.get("id") or ""),
                        "commence_time": data.get("commence_time"),
                        "book": bk.get("key"), "market": market,
                        "player_name": oc.get("description"),
                        "side": str(oc.get("name", "")).lower(),
                        "line": float(oc["point"]),
                        "price": float(oc["price"]),
                    })
    return pd.DataFrame(rows)


def attach_ids(snaps: pd.DataFrame,
               era_ids: set | None = None) -> tuple[pd.DataFrame, int]:
    idx = name_index(era_ids)
    snaps = snaps.copy()
    snaps["player_id"] = snaps["player_name"].map(
        lambda n: idx.get(norm_name(n)))
    unresolved = int(snaps["player_id"].isna().sum())
    return snaps.dropna(subset=["player_id"]), unresolved


def match_to_flow(snaps: pd.DataFrame, flow: pd.DataFrame) -> pd.DataFrame:
    """
    Join a real line to the model state it should be priced against.

    Matched on (player, market) within the game, then to the decision point
    whose wall clock is closest to the snapshot. A snapshot is only usable if a
    state exists at or before it, so the model never sees the future.
    """
    states = pd.read_parquet(ARTIFACT_DIR / "states_all.parquet")
    marks = (states.sort_values(["game_id", "seconds_remaining"],
                                ascending=[True, False], kind="mergesort")
             .groupby("game_id").agg(wall_start=("wall_ts", "first")).reset_index())
    flow = flow.merge(marks, on="game_id", how="left")
    snaps["ts_dt"] = pd.to_datetime(snaps["ts"], errors="coerce", utc=True,
                                    format="ISO8601")
    merged = flow.merge(
        snaps, on=["player_id", "market"], how="inner", suffixes=("", "_snap"))
    # The snapshot must fall inside the game it is being matched to.
    merged = merged[
        (merged["ts_dt"] >= merged["wall_start"])
        & (merged["ts_dt"] <= merged["wall_start"] + pd.Timedelta(hours=4))]
    return merged


def grade_real(d: pd.DataFrame) -> pd.DataFrame:
    """Bet the side the model disagrees with the REAL line on."""
    g = d.copy()
    g["deviation"] = g["model_final"] - g["line"]
    g["dev_frac"] = g["deviation"] / g["line"].clip(lower=0.5)
    g["bet_side"] = np.where(g["deviation"] > 0, "over", "under")
    over_hit = g["actual_final"] > g["line"]
    g["won"] = np.where(g["bet_side"] == "over", over_hit, ~over_hit).astype(float)
    g.loc[g["actual_final"] == g["line"], "won"] = np.nan
    # Real prices, not an assumed -110. Books juice prop overs, so an edge
    # measured at a flat vig can vanish once the actual number is used.
    dec = np.where(g["price"] > 0, 1 + g["price"] / 100.0,
                   1 + 100.0 / g["price"].abs())
    g["profit"] = np.where(g["won"] == 1.0, dec - 1.0, -1.0)
    g.loc[g["won"].isna(), "profit"] = 0.0
    return g


def run(rounds: int = 400) -> None:
    flow = load_rows()
    snaps = load_snapshots()
    if snaps.empty:
        raise SystemExit("no prop snapshots parsed; nothing to validate")
    era_ids = set(flow["player_id"].unique())
    snaps, unresolved = attach_ids(snaps, era_ids)
    print(f"{len(snaps):,} priced prop sides, {unresolved:,} names unresolved "
          f"and dropped")

    print("\n=== flow model vs REAL prop lines ===")
    print(f"breakeven at the quoted price; ROI is on the actual number, not "
          f"an assumed -110\n")

    for market in FLOW_MARKETS:
        d = flow[flow.market == market]
        s = snaps[snaps.market == market]
        if d.empty or s.empty:
            print(f"{market:26s} no matched lines")
            continue

        out = []
        for season in sorted(x for x in d.season.unique() if x >= 2018):
            prior, cur = d[d.season < season], d[d.season == season]
            if len(prior) < 2000 or cur.empty:
                continue
            print(f"  training {market} through {season}", flush=True)
            curve = fit_time_curve(prior)
            pa, ca = apply_anchor(prior, curve), apply_anchor(cur, curve)
            for label, feats in (("full", None), ("control", ANCHOR_ONLY_FEATURES)):
                m = train_flow(pa, None, rounds=rounds, features=feats)
                c = ca.copy()
                c["model_final"] = c["accrued"] + predict_flow(m, ca, features=feats)
                c["arm"] = label
                out.append(c)
        if not out:
            continue
        preds = pd.concat(out, ignore_index=True)
        matched = match_to_flow(s, preds)
        if matched.empty:
            print(f"{market:26s} no snapshots matched a model state")
            continue
        graded = grade_real(matched)

        print(f"{market}   matched bets {len(graded):,}  "
              f"games {graded.game_id.nunique():,}")
        for gate in (0.05, 0.10, 0.20):
            line = f"    gate {gate:.2f}  "
            for arm in ("full", "control"):
                a = graded[(graded.arm == arm)
                           & (graded.dev_frac.abs() >= gate)].dropna(subset=["won"])
                if len(a) < 50:
                    line += f"{arm}: thin  "
                    continue
                line += (f"{arm}: {100*a.won.mean():5.2f}% n={len(a):5d} "
                         f"roi {100*a.profit.mean():+5.2f}%  ")
            print(line)
        print()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=400)
    args = ap.parse_args()
    run(rounds=args.rounds)


if __name__ == "__main__":
    main()
