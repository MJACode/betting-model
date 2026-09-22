"""Reconstruct the game state that existed at the moment of every archived live quote.

WHY THIS EXISTS. The deployed rule prices a live prop from the book's line and
nothing else -- `over_prob(q.line, None, seconds_remaining)` in
`nfl/live_model/workers/gameday.py`. It therefore cannot tell a line the player
has already almost reached from one he would have to double his pace to clear.
Grading the archive needs the same state the worker could have read, so this
module rebuilds it from nflverse play-by-play and attaches it to each quote.

THE JOIN IS POINT-IN-TIME. Every quote carries a wall-clock `ts`; every play
carries `time_of_day`. A backwards `merge_asof` on that clock takes the most
recent play that had ALREADY HAPPENED when the quote was posted, so nothing
downstream can see the future. Plays with no `time_of_day` are dropped rather
than interpolated -- a guessed clock would be a look-ahead with no way to spot
it later.

THE ACCRUED COUNT IS VERIFIED, NOT ASSUMED. Counting "attempts" from
play-by-play is a definition, not a fact: sacks, two-point conversions and
penalty-nullified snaps each move the number. So `verify()` compares the
FULL-GAME cumulative count against the official per-player final already stored
in `nfl_player_game_log` and reports exact agreement per market. A definition
that does not reproduce the final is wrong, and the count it feeds is wrong in
the same direction all season.
"""
from __future__ import annotations

import glob

import numpy as np
import pandas as pd

PBP_GLOB = "nfl/data/pbp/play_by_play_{season}.parquet"
QUOTES = "nfl/data/live_model/_quotes_graded.parquet"
STATE = "nfl/data/live_model/_quotes_state.parquet"

PBP_COLS = [
    "game_id", "time_of_day", "game_seconds_remaining", "qtr", "posteam",
    "total_home_score", "total_away_score", "home_team", "away_team",
    "pass_attempt", "complete_pass", "rush_attempt", "sack", "two_point_attempt",
    "passer_player_name", "receiver_player_name", "rusher_player_name",
]


def _key(name: pd.Series) -> pd.Series:
    """`P.Mahomes` and `Patrick Mahomes` both collapse to `p|mahomes`.

    Play-by-play abbreviates the first name to an initial, the odds feed does
    not, so the only field both spell the same way is the initial plus the
    surname. Collisions inside one game and one market are possible in
    principle; `verify()` is what shows whether any actually bit.

    Every intermediate keeps the input's own index. `np.where` returns a bare
    array, and rebuilding a Series from one silently renumbers it 0..n-1 --
    assigning that back onto a filtered frame aligns on the wrong rows and
    produces a key that matches almost nothing.
    """
    s = name.fillna("").astype(str).str.strip()
    idx = s.index
    abbrev = s.str.contains(r"^[A-Za-z]\.", regex=True)
    first = pd.Series(
        np.where(abbrev, s.str.slice(0, 1), s.str.split().str[0].str.slice(0, 1)),
        index=idx)
    last = pd.Series(
        np.where(abbrev, s.str.split(".").str[-1], s.str.split().str[-1]),
        index=idx)
    last = last.astype(str).str.lower().str.replace(r"[^a-z]", "", regex=True)
    return first.astype(str).str.lower() + "|" + last


def load_pbp(seasons=(2023, 2024, 2025)) -> pd.DataFrame:
    frames = []
    for s in seasons:
        for f in sorted(glob.glob(PBP_GLOB.format(season=s))):
            frames.append(pd.read_parquet(f, columns=PBP_COLS))
    if not frames:
        raise FileNotFoundError(
            "no play-by-play on disk. Run:\n"
            "  python -m nfl.live_model.backtest.pull_pbp --seasons 2023 2024 2025")
    pbp = pd.concat(frames, ignore_index=True)
    raw = pd.to_datetime(pbp["time_of_day"], utc=True, errors="coerce")

    # 15.6% of plays carry no wall clock at all, and 3.30% of pass attempts do
    # -- and DROPPING those was a 3.3% systematic UNDERCOUNT of every accrued
    # total, which `verify()` caught as a mean error of -1.08 attempts per
    # quarterback. An attempt with no timestamp still happened and still counts
    # toward the final, so it has to be placed in time rather than discarded.
    #
    # Placed by INTERPOLATION between the surrounding clocked plays, on play
    # order within the game. That keeps the join point-in-time: an interpolated
    # play lands strictly between the play before it and the play after it, so
    # it can never be counted before something that genuinely preceded it.
    # Forward-filling would instead stamp it with an EARLIER play's time and
    # count it too soon, which is a look-ahead the size of a drive.
    # Microseconds throughout, stated once and never inferred. `.astype(int64)`
    # returns the count in the dtype's OWN unit, so reading it back with a
    # different unit silently rescales every timestamp by a factor of 1000 --
    # which moved all 147,914 plays to January 1970 while the accrued counts
    # still verified perfectly, because a cumulative count within a game does
    # not depend on the clock being right.
    us = raw.astype("datetime64[us, UTC]")
    epoch = us.astype("int64").where(us.notna()).astype(float)
    filled = epoch.groupby(pbp["game_id"]).transform(
        lambda s: s.interpolate(method="linear", limit_direction="both"))
    pbp["tod"] = pd.to_datetime(filled, unit="us", utc=True).astype(
        "datetime64[us, UTC]")

    # The guard the count-based check cannot give: a play's reconstructed wall
    # clock must sit inside its game's own broadcast window.
    span = pbp.groupby("game_id")["tod"].agg(["min", "max"])
    hours = (span["max"] - span["min"]).dt.total_seconds() / 3600.0
    bad = hours[(hours < 1.5) | (hours > 7.0)]
    if len(bad):
        raise ValueError(
            f"{len(bad)} games have an implausible wall-clock span "
            f"(min {hours.min():.2f}h, max {hours.max():.2f}h). The clock "
            f"reconstruction is wrong, and every point-in-time join built on "
            f"it would be too.")
    return pbp.dropna(subset=["tod", "game_seconds_remaining"]).sort_values("tod")


def events(pbp: pd.DataFrame) -> pd.DataFrame:
    """One row per counting event, with the player's running total after it.

    Each market's definition is the OFFICIAL one, which is why each carries its
    own exclusions rather than sharing a single `pass_attempt` flag:

      attempts     a pass that was not a sack and not a two-point try. nflverse
                   flags a sack as `pass_attempt == 1`; the NFL does not count
                   it, and including sacks inflates every quarterback by two to
                   four a game -- the same order as the bias this model was
                   built on.
      completions  a completed pass, credited to the passer.
      receptions   the same play, credited to the receiver.
      carries      a rush that was not a two-point try.
    """
    two = pbp["two_point_attempt"].fillna(0) == 1
    specs = {
        "attempts": ((pbp["pass_attempt"].fillna(0) == 1)
                     & (pbp["sack"].fillna(0) == 0) & ~two, "passer_player_name"),
        "completions": ((pbp["complete_pass"].fillna(0) == 1) & ~two,
                        "passer_player_name"),
        "receptions": ((pbp["complete_pass"].fillna(0) == 1) & ~two,
                       "receiver_player_name"),
        "carries": ((pbp["rush_attempt"].fillna(0) == 1) & ~two,
                    "rusher_player_name"),
    }
    out = []
    for stat, (mask, col) in specs.items():
        e = pbp.loc[mask & pbp[col].notna(), ["game_id", "tod", col]].copy()
        e["stat"] = stat
        e["pk"] = _key(e[col])
        out.append(e[["game_id", "tod", "stat", "pk"]])
    ev = pd.concat(out, ignore_index=True).sort_values("tod")
    ev["k"] = (ev["game_id"].astype(str) + "|" + ev["stat"].astype(str)
               + "|" + ev["pk"].astype(str))
    ev["accrued"] = ev.groupby("k").cumcount() + 1
    return ev


def verify(ev: pd.DataFrame, quotes: pd.DataFrame) -> pd.DataFrame:
    """Does the full-game count reproduce the official final?

    The archive already carries `final` from `nfl_player_game_log`, so the
    counting definitions above are checkable without a second source. Anything
    short of near-total exact agreement means a definition is wrong, and every
    accrued count it produces is biased the same way.
    """
    tot = ev.groupby("k")["accrued"].max().rename("counted")
    q = quotes.drop_duplicates(["game_id", "stat", "join_name"]).copy()
    q["k"] = (q["game_id"].str.replace("^NFL_", "", regex=True) + "|" + q["stat"]
              + "|" + _key(q["player_name"]))
    j = q.merge(tot, left_on="k", right_index=True, how="left")
    rows = []
    for stat, g in j.groupby("stat"):
        matched = g["counted"].notna()
        exact = (g["counted"] == g["final"]) & matched
        rows.append({
            "stat": stat, "players": len(g),
            "joined": int(matched.sum()),
            "exact": int(exact.sum()),
            "exact_pct": 100.0 * exact.sum() / max(matched.sum(), 1),
            "mean_err": float((g.loc[matched, "counted"]
                               - g.loc[matched, "final"]).mean()),
        })
    return pd.DataFrame(rows)


def build(seasons=(2023, 2024, 2025)) -> pd.DataFrame:
    """Attach point-in-time state to every graded quote."""
    quotes = pd.read_parquet(QUOTES)
    quotes["ts"] = pd.to_datetime(quotes["ts"], utc=True)
    quotes["pbp_game"] = quotes["game_id"].str.replace("^NFL_", "", regex=True)
    quotes["pk"] = _key(quotes["player_name"])

    pbp = load_pbp(seasons)
    ev = events(pbp)
    print(verify(ev, quotes).to_string(index=False))

    # --- accrued: the player's running total as of the quote's wall clock
    q = quotes.copy()
    q["k"] = (q["pbp_game"].astype(str) + "|" + q["stat"].astype(str)
              + "|" + q["pk"].astype(str))
    q = q.sort_values("ts")
    acc = pd.merge_asof(
        q[["ts", "k"]].reset_index(), ev[["tod", "k", "accrued"]],
        left_on="ts", right_on="tod", by="k", direction="backward")
    # No event before the quote is a genuine zero, not a missing value: the
    # player had not yet recorded one. A player who never joins at all is
    # dropped later by the `secs` gate, not silently zeroed.
    q["accrued"] = acc.set_index("index")["accrued"].reindex(q.index).fillna(0.0)

    # --- clock and score: the last play that had happened when the quote posted
    gs = pbp[["game_id", "tod", "game_seconds_remaining", "qtr", "total_home_score",
              "total_away_score", "home_team", "away_team"]].copy()
    gs = gs.rename(columns={"home_team": "pbp_home", "away_team": "pbp_away"})
    gs["gk"] = gs["game_id"].astype(str)
    gs = gs.sort_values("tod")
    st = pd.merge_asof(
        q[["ts", "pbp_game"]].reset_index().rename(columns={"pbp_game": "gk"}),
        gs.drop(columns=["game_id"]),
        left_on="ts", right_on="tod", by="gk", direction="backward")
    st = st.set_index("index")
    for c in ("game_seconds_remaining", "qtr", "total_home_score",
              "total_away_score", "pbp_home", "pbp_away"):
        q[c] = st[c].reindex(q.index)

    # --- which side is the player on? the team he recorded his events for
    side = ev.merge(pbp[["game_id", "tod", "posteam"]], on=["game_id", "tod"],
                    how="left")
    team = (side.dropna(subset=["posteam"]).groupby("k")["posteam"]
            .agg(lambda s: s.value_counts().idxmax()))
    q["team"] = q["k"].map(team)
    home = q["team"] == q["pbp_home"]
    own = np.where(home, q["total_home_score"], q["total_away_score"])
    opp = np.where(home, q["total_away_score"], q["total_home_score"])
    q["trail"] = opp - own                      # positive = the player is behind

    # --- the quantities the deployed rule never sees
    q["secs"] = q["game_seconds_remaining"].astype(float)
    q["min_left"] = q["secs"] / 60.0
    q["elapsed_min"] = ((3600.0 - q["secs"]) / 60.0).clip(lower=1.0)
    q["slack"] = q["line"] - q["accrued"]        # what the over still needs
    q["remaining"] = q["final"] - q["accrued"]   # what it actually got
    q["pace_so_far"] = q["accrued"] / q["elapsed_min"]
    q["pace_needed"] = q["slack"] / q["min_left"].clip(lower=1e-9)
    q["pace_ratio"] = q["pace_needed"] / q["pace_so_far"].replace(0.0, np.nan)
    q["trail_x_sqrt_t"] = q["trail"] * np.sqrt(q["secs"].clip(lower=0.0))

    # A running total can never exceed the final it is running toward. This is
    # the one check that fails loudly if the point-in-time join drifts forward
    # in time, which the per-game count check cannot see.
    live = q[q["secs"].notna()]
    ahead = live[live["accrued"] > live["final"]]
    if len(ahead) > 0.005 * max(len(live), 1):
        raise ValueError(
            f"{len(ahead):,} of {len(live):,} quotes show more accrued than the "
            f"player's final. The state join is reading the future.")
    print(f"accrued-exceeds-final: {len(ahead):,} / {len(live):,} "
          f"({100.0 * len(ahead) / max(len(live), 1):.3f}%)")

    q.to_parquet(STATE, index=False)
    return q


if __name__ == "__main__":
    d = build()
    live = d[d["secs"].notna() & (d["secs"] > 0)]
    print(f"\n{len(d):,} quotes, {len(live):,} with a live game state "
          f"({d['game_id'].nunique():,} games)")
    print(f"written: {STATE}")
