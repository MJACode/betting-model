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
    Flatten the cached prop payloads into one row per QUOTE.

    A quote is two-sided, so over and under are kept on the SAME row. Emitting
    them separately double counts every proposition and, worse, lets a bet be
    graded at the price of the side it did not take.

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
                        "ts": ts,
                        "commence_time": data.get("commence_time"),
                        "home_team": data.get("home_team"),
                        "away_team": data.get("away_team"),
                        "book": bk.get("key"), "market": market,
                        "player_name": oc.get("description"),
                        "side": str(oc.get("name", "")).lower(),
                        "line": float(oc["point"]),
                        "price": float(oc["price"]),
                    })
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    key = ["ts", "commence_time", "home_team", "away_team", "book", "market",
           "player_name", "line"]
    df = df.drop_duplicates(subset=key + ["side"], keep="last")
    wide = (df.pivot_table(index=key, columns="side", values="price",
                           aggfunc="last").reset_index()
            .rename(columns={"over": "over_price", "under": "under_price"}))
    for col in ("over_price", "under_price"):
        if col not in wide.columns:
            wide[col] = np.nan
    # A one sided quote cannot be graded on the side the model wants half the
    # time, so require both prices rather than silently assuming a vig.
    return wide.dropna(subset=["over_price", "under_price"]).reset_index(drop=True)


def attach_ids(snaps: pd.DataFrame,
               era_ids: set | None = None) -> tuple[pd.DataFrame, int]:
    idx = name_index(era_ids)
    snaps = snaps.copy()
    snaps["player_id"] = snaps["player_name"].map(
        lambda n: idx.get(norm_name(n)))
    unresolved = int(snaps["player_id"].isna().sum())
    return snaps.dropna(subset=["player_id"]), unresolved


def _game_marks() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per game: the abbreviations in its id and when its first play was."""
    states = pd.read_parquet(ARTIFACT_DIR / "states_all.parquet",
                             columns=["game_id", "seconds_remaining", "wall_ts"])
    marks = (states.groupby("game_id")
             .agg(wall_start=("wall_ts", "min")).reset_index())
    parts = marks["game_id"].str.split("_", expand=True)
    marks["away_abbrev"] = parts[2]
    marks["home_abbrev"] = parts[3]
    return marks, states


def resolve_game_ids(snaps: pd.DataFrame, marks: pd.DataFrame) -> pd.DataFrame:
    """
    Put our game_id on every quote.

    A snapshot carries the book's team names and a kickoff time, not our id.
    Without this the join can only match on player, which lets a quote from one
    week be priced against a model state from another.
    """
    from data_ingest.parse import TEAM_MAP

    snaps = snaps.copy()
    snaps["home_abbrev"] = snaps["home_team"].map(TEAM_MAP)
    snaps["away_abbrev"] = snaps["away_team"].map(TEAM_MAP)
    snaps["commence_dt"] = pd.to_datetime(snaps["commence_time"], errors="coerce",
                                          utc=True, format="ISO8601")
    m = snaps.merge(marks, on=["home_abbrev", "away_abbrev"], how="inner")
    # One fixture per matchup per week; a kickoff more than half a day from the
    # first play is a different season's meeting of the same two teams.
    m = m[(m["commence_dt"] - m["wall_start"]).abs() <= pd.Timedelta(hours=12)]
    return m


def resolve_snaps(snaps: pd.DataFrame,
                  marks: pd.DataFrame | None = None) -> pd.DataFrame:
    """Attach game_id, a parsed timestamp and a stable id to every quote."""
    if marks is None:
        marks, _ = _game_marks()
    out = resolve_game_ids(snaps, marks)
    if out.empty:
        return out
    out["ts_dt"] = pd.to_datetime(out["ts"], errors="coerce", utc=True,
                                  format="ISO8601")
    out = out.dropna(subset=["ts_dt"]).reset_index(drop=True)
    out["quote_id"] = np.arange(len(out))
    return out


def pseudo_clv(graded: pd.DataFrame, snaps: pd.DataFrame) -> pd.DataFrame:
    """
    Compare every bet to the LAST quote the same book showed on it.

    These are full game props, so a later quote prices the identical
    proposition on a better informed view of it. Beating that number is the
    closest thing to closing line value this data allows, and the spec makes
    it the gate rather than ROI.

    "Pseudo" because the real close is the whistle and our last observation is
    600 seconds of game clock earlier, so this understates a late mover.
    """
    if graded.empty or snaps.empty:
        return pd.DataFrame()
    keys = ["game_id", "player_id", "market", "book"]
    last = (snaps.sort_values("ts_dt")
            .groupby(keys, as_index=False, sort=False).tail(1)
            [keys + ["ts_dt", "line", "over_price", "under_price"]]
            .rename(columns={"ts_dt": "close_ts", "line": "close_line",
                             "over_price": "close_over",
                             "under_price": "close_under"}))
    d = graded.merge(last, on=keys, how="inner")
    # A quote cannot be its own close.
    d = d[d["close_ts"] > d["ts_dt"]]
    if d.empty:
        return d

    # Line CLV, in units of the stat. Taking an over at a LOWER number than
    # the market later shows is value; taking an under at a higher one is.
    d["line_clv"] = np.where(d["bet_side"] == "over",
                             d["close_line"] - d["line"],
                             d["line"] - d["close_line"])

    # Price CLV, only where the number did not move. Devigged so the book's
    # margin is not counted as movement.
    def _imp(px):
        px = np.asarray(px, dtype=float)
        return np.where(px > 0, 100.0 / (px + 100.0), -px / (-px + 100.0))

    same = d["close_line"] == d["line"]
    io, iu = _imp(d["over_price"]), _imp(d["under_price"])
    co, cu = _imp(d["close_over"]), _imp(d["close_under"])
    bet_fair = np.where(d["bet_side"] == "over", io / (io + iu), iu / (io + iu))
    cls_fair = np.where(d["bet_side"] == "over", co / (co + cu), cu / (co + cu))
    d["price_clv_pp"] = np.where(same, 100.0 * (cls_fair - bet_fair), np.nan)
    return d


def match_to_flow(snaps: pd.DataFrame, flow: pd.DataFrame) -> pd.DataFrame:
    """
    Join a real line to the model state it should be priced against.

    Two things make this honest, and the previous version did neither:

    - The join is keyed on the GAME as well as the player, so a quote cannot be
      matched to a state from a different week.
    - The state must be at or BEFORE the moment the book published the quote.
      Pricing a Q2 line against a Q4 state hands the model three quarters of
      football the book did not have, which is look ahead, and it inflates the
      control arm just as much as the full one.
    """
    marks, states = _game_marks()
    if "quote_id" not in snaps.columns:
        snaps = resolve_snaps(snaps, marks)
    if snaps.empty:
        return snaps

    # Wall clock of each decision point: the first state at or before that many
    # seconds remained.
    # merge_asof refuses to join an int key to a float one, and the real flow
    # rows carry decision_point as an integer while states carry seconds as a
    # float. Pin both rather than relying on whatever the parquet happened to
    # store.
    dps = flow[["game_id", "decision_point"]].drop_duplicates().copy()
    dps["decision_point"] = dps["decision_point"].astype("float64")
    dps = dps.sort_values("decision_point")
    st = states.copy()
    st["seconds_remaining"] = st["seconds_remaining"].astype("float64")
    st = st.sort_values("seconds_remaining")
    dp_wall = pd.merge_asof(dps, st, left_on="decision_point",
                            right_on="seconds_remaining", by="game_id",
                            direction="forward")[
        ["game_id", "decision_point", "wall_ts"]]
    flow = flow.copy()
    flow["decision_point"] = flow["decision_point"].astype("float64")
    flow = flow.merge(dp_wall, on=["game_id", "decision_point"], how="inner")

    merged = flow.merge(snaps, on=["game_id", "player_id", "market"],
                        how="inner", suffixes=("", "_snap"))
    merged = merged[merged["wall_ts"] <= merged["ts_dt"]]
    if merged.empty:
        return merged
    # The freshest state the book's own clock allows.
    merged = (merged.sort_values("wall_ts")
              .groupby(["quote_id", "arm"], as_index=False, sort=False).tail(1))
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
    # Real prices, not an assumed -110, and the price of the side actually
    # taken. Books juice prop overs, so grading an under at the over's number
    # manufactures edge.
    price = np.where(g["bet_side"] == "over", g["over_price"], g["under_price"])
    dec = np.where(price > 0, 1 + price / 100.0, 1 + 100.0 / np.abs(price))
    g["price"] = price
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
    # Resolve once so the grading join and the close lookup share one frame.
    snaps = resolve_snaps(snaps)
    print(f"{len(snaps):,} quotes resolved to a game")

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

        # Is this a LIVE line or a stale one? A book that is repricing in play
        # cannot leave a number below what the player has already produced;
        # that would be free money and it would be taken. A large share of
        # such quotes means the market was not really being repriced, and any
        # edge measured against it is an artifact rather than a bet anyone
        # could have got down.
        one = graded[graded.arm == "full"]
        if len(one):
            below = float((one["line"] < one["accrued"]).mean())
            slack = (one["line"] - one["accrued"]).median()
            print(f"{market}   line vs accrued: median slack {slack:+.2f}, "
                  f"{100 * below:.1f}% of quotes already beaten")
            # A one sided book is a different claim than a working model. If
            # nearly every bet is an under and unders win, the finding is that
            # this market's live line is set too high, which needs neither the
            # flow features nor the anchor. Print the split so the two cannot
            # be confused.
            d10 = one[one.dev_frac.abs() >= 0.10].dropna(subset=["won"])
            for arm_label, arm_df in (("full", d10),):
                for sd in ("over", "under"):
                    sub = arm_df[arm_df.bet_side == sd]
                    if len(sub):
                        print(f"{market}     {arm_label} {sd:5s} n={len(sub):5d} "
                              f"win {100 * sub.won.mean():5.2f}%  "
                              f"roi {100 * sub.profit.mean():+6.2f}%")
            print(f"{market}   median line {one['line'].median():.1f}, "
                  f"median actual final {one['actual_final'].median():.1f}, "
                  f"median remaining truth "
                  f"{(one['actual_final'] - one['accrued']).median():.1f}")
            # The pre committed kill criterion is a lane holding across two
            # seasons. A one sided book bias that lives in a single season is
            # noise, or a market that has since been corrected.
            # Pseudo CLV is the spec's gate, not ROI. Report it before the
            # hit rates so a lane that fails it is not read past.
            clv = pseudo_clv(d10, snaps[snaps.market == market])
            if len(clv):
                beat = float((clv["line_clv"] > 0).mean())
                tied = float((clv["line_clv"] == 0).mean())
                pc = clv["price_clv_pp"].dropna()
                print(f"{market}   PSEUDO CLV n={len(clv):,}  "
                      f"mean line {clv['line_clv'].mean():+.3f}  "
                      f"beat {100 * beat:.1f}%  tied {100 * tied:.1f}%  "
                      f"price {pc.mean():+.2f}pp on n={len(pc):,} unmoved")
                for season, csub in clv.groupby("season"):
                    if len(csub) < 50:
                        continue
                    print(f"{market}     CLV {int(season)} n={len(csub):5d} "
                          f"mean line {csub['line_clv'].mean():+.3f}  "
                          f"beat {100 * (csub['line_clv'] > 0).mean():.1f}%")
            else:
                print(f"{market}   PSEUDO CLV: no later quote to compare")

            # Does the model actually forecast the final better than the book's
            # own number does? A +28% ROI requires it. Near identical error
            # would mean the ROI comes from somewhere other than skill, which
            # is what near zero CLV alongside a huge ROI already hints at.
            err_model = (d10["model_final"] - d10["actual_final"]).abs().mean()
            err_book = (d10["line"] - d10["actual_final"]).abs().mean()
            print(f"{market}   MAE vs final: model {err_model:.2f}  "
                  f"book {err_book:.2f}  "
                  f"model better by {err_book - err_model:+.2f}")

            for season, sub in d10.groupby("season"):
                if len(sub) < 50:
                    continue
                ov = sub[sub.bet_side == "over"]
                un = sub[sub.bet_side == "under"]
                print(f"{market}     {int(season)} n={len(sub):5d} "
                      f"win {100 * sub.won.mean():5.2f}% "
                      f"roi {100 * sub.profit.mean():+6.2f}%   "
                      f"over {len(ov):4d}/{100 * ov.won.mean() if len(ov) else float('nan'):5.2f}%  "
                      f"under {len(un):4d}/"
                      f"{100 * un.won.mean() if len(un) else float('nan'):5.2f}%")

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
