"""
Replay historical in-play odds snapshots against reconstructed game states.

    python -m live_model.backtest.harness --seasons 2023 2024

THIS IS THE GATE THE WHOLE PROJECT HANGS ON. Per the build spec's kill
criteria, a lane with pseudo-CLV of zero or below across two seasons is CUT
before it is ever deployed. That decision is made here, in advance, and it is
not renegotiable afterwards by rescoping until something passes.

PSEUDO-CLV IS THE PRIMARY METRIC, NOT ROI.
Realised ROI over a few hundred in-play bets is mostly variance. Pseudo-CLV,
the move in the devigged market number between our snapshot and the next one,
is a far lower variance read on whether we were on the right side of a market
that was about to move. It is also the metric that degrades most gracefully
under the known 5-minute granularity problem, because it is measured over the
same 5 minutes rather than assuming we could have acted instantly.

WHAT THE 5-MINUTE GRANULARITY DOES TO THESE NUMBERS
It flatters them, and there is no way to fix that with this data. Any edge that
lives inside a 5-minute window is invisible here, and any edge that persists
for 5 minutes is easier to capture in the backtest than it will be live, where
the market suspends at the snap and reprices in 1 to 3 seconds. So the reported
ROI is an UPPER BOUND, and the build spec's requirement of a larger margin than
a pregame model before going live is the correct response.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from data_ingest.odds_api import CACHE_DIR                      # noqa: E402
from ..config import ARTIFACT_DIR, EV_THRESHOLDS                # noqa: E402
from ..engine.distribution import ScoreDistribution             # noqa: E402
from ..engine.pricing import (                                  # noqa: E402
    american_to_decimal, devig_power, price_second_half, price_spread,
    price_team_total, price_total,
)
from ..engine.remaining import load_models, predict_remaining   # noqa: E402
from ..feeds.odds_live import parse_events                      # noqa: E402
from .train_engine import load_states                           # noqa: E402

# Lane assignment, so results are reported the way the kill criteria are stated.
LANE_OF_MARKET = {
    "totals": "anchor",
    "spreads": "anchor",
    "h2h": "anchor",
    "totals_h2": "halftime_2h",
    "spreads_h2": "halftime_2h",
    "h2h_h2": "halftime_2h",
    "team_totals": "derivative",
    "alternate_totals": "derivative",
    "alternate_spreads": "derivative",
    "player_pass_yds": "prop",
    "player_rush_yds": "prop",
}
# Anchor markets are priced for the anchor blend and reported for reference.
# They are NEVER counted as a bettable lane: constraint 4 says the live main
# line is truth, and a backtest that lets us bet it would be measuring our
# disagreement with the sharpest number on the board.
BETTABLE_LANES = ("halftime_2h", "derivative", "prop")


def load_cached_snapshots(min_ts: datetime | None = None,
                          cache_dir: Path | None = None) -> list[dict]:
    """
    Every historical payload already on disk, newest field intact.

    Reads the shared cache written by data_ingest.odds_api, so the harness runs
    for zero credits over whatever pull_snaps has already fetched.
    """
    out = []
    # `cache_dir` exists so tests can point at a fixture directory. The real
    # cache holds ~2,600 irreplaceable snapshots representing tens of thousands
    # of credits of spend; nothing in the test path may write to it.
    for path in sorted((cache_dir or CACHE_DIR).glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        ts_raw = payload.get("timestamp")
        if not ts_raw:
            continue
        try:
            ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        except ValueError:
            continue
        if min_ts and ts < min_ts:
            continue
        data = payload.get("data") or []
        if data:
            out.append({"ts": ts, "data": data, "path": path.name})
    out.sort(key=lambda d: d["ts"])
    return out


def align_states(states: pd.DataFrame) -> dict:
    """
    Index states by game so a snapshot can find the latest state at or before
    its timestamp.

    Alignment is one directional on purpose: the state must be at or BEFORE the
    quote. Taking the nearest state in either direction would let a snapshot be
    priced off a state that had not happened yet, which is the in-play version
    of look-ahead bias and would manufacture edge out of nothing.
    """
    idx = {}
    for gid, grp in states.groupby("game_id", sort=False):
        g = grp.sort_values("seconds_remaining", ascending=False)
        idx[gid] = g.reset_index(drop=True)
    return idx


# Odds API team names are full names ("Kansas City Chiefs"); nflverse game ids
# use abbreviations. Built from the pbp files themselves rather than hardcoded,
# so a relocation or rename cannot silently drop a team.
def build_team_map(states: pd.DataFrame) -> dict:
    """
    Map an Odds API full team name to the nflverse abbreviation.

    Matched on the LAST word of the full name (the nickname), which is unique
    across the league, with the two-word nicknames handled explicitly. A name
    that cannot be resolved is left out and its events are skipped and counted,
    never guessed onto a nearby team.
    """
    from data_ingest.parse import TEAM_MAP  # reuse the package own map
    return dict(TEAM_MAP)


def _game_index(states: pd.DataFrame) -> dict:
    """(home abbrev, away abbrev, date) -> game_id, for snapshot matching."""
    idx = {}
    first = states.groupby("game_id", sort=False).first().reset_index()
    for _, r in first.iterrows():
        d = pd.to_datetime(r["wall_ts"]).date()
        # A night game crosses midnight UTC, so index both the UTC date and the
        # day before. Matching on one of them only would drop every Sunday and
        # Monday night game from the backtest.
        for dd in (d, d - timedelta(days=1)):
            idx[(r["home_team"], r["away_team"], dd)] = r["game_id"]
    return idx


def _state_at(game_states: pd.DataFrame, ts: datetime):
    """
    The latest state at or BEFORE `ts`.

    One directional on purpose. Taking the nearest state in either direction
    would let a snapshot be priced off a state that had not happened yet, which
    is the in-play form of look-ahead bias and would manufacture edge from
    nothing.
    """
    prior = game_states[game_states["wall_ts"] <= ts]
    return None if prior.empty else prior.iloc[-1]


def _team_side(team, home, away) -> str | None:
    """Which side of the game a team-total quote belongs to."""
    if team is None:
        return None
    if team == home:
        return "home"
    if team == away:
        return "away"
    return None


def _model_price(dist, mu_h, mu_a, row, market: str, line: float,
                 side: str, team_side: str | None = None) -> float | None:
    """Model probability for one market and side. None if we do not price it."""
    out = dist.final_score_pmf(
        mu_h, mu_a, float(row["seconds_remaining"]),
        int(row["home_score_pre"]), int(row["away_score_pre"]),
    )
    if market == "totals":
        p = price_total(out, line)
        return p.get(side)
    if market.endswith("team_totals"):
        # Without a resolved team this is unpriceable: dropping it is the only
        # honest option, because guessing the team is a coin flip on which
        # offence the line refers to.
        if team_side is None:
            return None
        p = price_team_total(out, team_side, line)
        return p.get(side)
    if market in ("totals_h2", "spreads_h2", "h2h_h2"):
        # Second half markets need the halftime score. Priced only at or after
        # halftime, where it is known; before halftime the second half total is
        # a different quantity from remaining points and pricing it here would
        # be wrong rather than approximate.
        if float(row["qtr"]) < 3 and not (float(row["qtr"]) == 2 and
                                          float(row["quarter_seconds_remaining"]) <= 0):
            return None
        hh = int(row.get("half_home_score", row["home_score_pre"]))
        ha = int(row.get("half_away_score", row["away_score_pre"]))
        p = price_second_half(out, market, line, hh, ha)
        return p.get(side)
    if market == "spreads":
        return price_spread(out, line if side == "home" else -line).get(side)
    return None


def replay(seasons, sample_every: int = 1, verbose: bool = True,
           cache_dir: Path | None = None) -> pd.DataFrame:
    """
    Price every cached snapshot against the state that preceded it.

    One row per (snapshot, market, side) evaluated, carrying the model price,
    the quoted price, the devigged market price, the realised outcome and the
    NEXT snapshot's devigged price so pseudo-CLV can be measured over the same
    5 minutes the data actually resolves.
    """
    states = load_states()
    states = states[states.season.isin(seasons)]
    if states.empty:
        raise SystemExit(f"no reconstructed states for {seasons}")

    models = load_models(ARTIFACT_DIR)
    dist = ScoreDistribution.load(ARTIFACT_DIR / "score_distribution.npz")

    snaps = load_cached_snapshots(cache_dir=cache_dir)
    if not snaps:
        raise SystemExit(
            "no in-play snapshots on disk. Run live_model.backtest.pull_snaps "
            "first (it needs THE_ODDS_API_KEY and a credit budget)."
        )
    if verbose:
        print(f"{len(snaps):,} cached snapshots, "
              f"{snaps[0]['ts'].date()} to {snaps[-1]['ts'].date()}")

    team_map = build_team_map(states)
    gidx = _game_index(states)
    # DATA QUALITY GATE. A game whose wall clock runs backwards cannot be
    # aligned to a timestamped odds snapshot, so it is dropped rather than
    # silently mis-aligned. 78 of 3,028 games fail this after the day-offset
    # repair in backtest.states.
    from .states import monotonicity_report
    bad = set(monotonicity_report(states)["game_ids"])
    if bad and verbose:
        print(f"dropping {len(bad)} games with a non-monotone wall clock")
    states = states[~states.game_id.isin(bad)]

    # mergesort is STABLE. With quicksort, plays sharing a timestamp to the
    # second get reordered arbitrarily, and _state_at then returns whichever
    # one happened to land last, which near the end of a half means pricing a
    # snapshot off a state from the wrong side of halftime.
    by_game = {g: d.sort_values("wall_ts", kind="mergesort").reset_index(drop=True)
               for g, d in states.groupby("game_id", sort=False)}
    finals = states.groupby("game_id").first()[["home_score", "away_score"]]

    # Devigged market price per (game, market, line, side, ts), so the NEXT
    # snapshot can be looked up for pseudo-CLV after the whole pass.
    market_hist: dict = defaultdict(list)
    rows: list[dict] = []
    unmapped = 0

    for snap in snaps:
        ts = snap["ts"]
        for ev in snap["data"]:
            home = team_map.get(ev.get("home_team"))
            away = team_map.get(ev.get("away_team"))
            if not home or not away:
                unmapped += 1
                continue
            gid = gidx.get((home, away, ts.date()))
            if gid is None or gid not in by_game:
                unmapped += 1
                continue

            row = _state_at(by_game[gid], ts)
            if row is None:
                continue        # snapshot predates kickoff: not an in-play state

            feats = by_game[gid].loc[[row.name]]
            pred = predict_remaining(models, feats)
            mu_h = float(pred["home_remaining_hat"].iloc[0])
            mu_a = float(pred["away_remaining_hat"].iloc[0])

            quotes = parse_events([ev])
            # Group the two sides of each (market, line) so we can de-vig.
            # Team totals name the team in `description` and the direction in
            # `name`, so the grouping key must carry BOTH. Keying on the market
            # alone silently merges the home over with the away under and
            # prices a market that does not exist.
            pairs: dict = defaultdict(dict)
            for q in quotes:
                team = None
                if q.market.endswith("team_totals") and q.player:
                    team = team_map.get(q.player)
                    if team is None:
                        continue
                # A spread quotes its two sides at MIRRORED numbers (home -1.5,
                # away +1.5). Keying on the raw point puts them in separate
                # groups, each with one side, so the market can never be
                # de-vigged and the whole lane silently produces zero rows.
                # Normalise every spread to its HOME-relative line, which is
                # also the convention price_spread expects.
                key_line = q.line
                if key_line is not None and "spread" in q.market:
                    key_line = float(key_line) if q.side == "home" else -float(key_line)
                pairs[(q.market, q.bookmaker, key_line, team)][q.side] = q

            fh, fa = finals.loc[gid, "home_score"], finals.loc[gid, "away_score"]

            for (market, book, line, team), sides in pairs.items():
                lane = LANE_OF_MARKET.get(market)
                if lane is None or len(sides) < 2:
                    continue
                a_key, b_key = ("over", "under") if "over" in sides else ("home", "away")
                if a_key not in sides or b_key not in sides:
                    continue
                pa, _pb = devig_power(sides[a_key].price, sides[b_key].price)
                if not np.isfinite(pa):
                    continue

                for side in (a_key, b_key):
                    q = sides[side]
                    # `line` is already home relative for spreads, so both
                    # sides are priced off the same number.
                    mp = _model_price(dist, mu_h, mu_a, row, market,
                                      0.0 if line is None else float(line), side,
                                      team_side=_team_side(team, home, away))
                    if mp is None or not (0.0 < mp < 1.0):
                        continue
                    mkt_p = pa if side == a_key else 1.0 - pa
                    key = (gid, market, book, line, side)
                    rows.append({
                        "ts": ts, "game_id": gid, "season": int(row["season"]),
                        "lane": lane, "market": market, "bookmaker": book,
                        "side": side, "line": line, "team": team,
                        "price": q.price,
                        "decimal": american_to_decimal(q.price),
                        "model_prob": mp, "market_prob": mkt_p,
                        "ev": mp * american_to_decimal(q.price) - 1.0,
                        "seconds_remaining": float(row["seconds_remaining"]),
                        "won": _settle(market, side, line, row, fh, fa,
                                       team_side=_team_side(team, home, away)),
                        "_key": key,
                    })
                    market_hist[key].append((ts, mkt_p))

    df = pd.DataFrame(rows)
    if df.empty:
        if verbose:
            print(f"no priceable rows ({unmapped} unmapped events)")
        return df

    # Pseudo-CLV: how the devigged market moved toward our side over the next
    # snapshot. Lower variance than realised ROI and measured over exactly the
    # window the data resolves on, which is why the kill criteria read it.
    nxt = {}
    for key, hist in market_hist.items():
        hist.sort()
        for i, (ts, p) in enumerate(hist):
            nxt[(key, ts)] = hist[i + 1][1] - p if i + 1 < len(hist) else np.nan
    df["pseudo_clv"] = [nxt.get((k, t), np.nan)
                        for k, t in zip(df["_key"], df["ts"])]
    df = df.drop(columns=["_key"])

    if verbose:
        print(f"replay produced {len(df):,} rows over "
              f"{df.game_id.nunique()} games ({unmapped} unmapped events)")
    return df


def _settle(market: str, side: str, line, row, final_home, final_away,
            team_side: str | None = None):
    """Realised outcome. NaN for a push or anything we cannot adjudicate."""
    if line is None:
        return np.nan
    line = float(line)
    if market == "totals":
        total = float(final_home) + float(final_away)
        if total == line:
            return np.nan
        won = total > line
        return float(won if side == "over" else not won)
    if market.endswith("team_totals"):
        if team_side is None:
            return np.nan
        pts = float(final_home) if team_side == "home" else float(final_away)
        if pts == line:
            return np.nan
        won = pts > line
        return float(won if side == "over" else not won)
    if market == "totals_h2":
        hh = float(row.get("half_home_score", row["home_score_pre"]))
        ha = float(row.get("half_away_score", row["away_score_pre"]))
        second = (float(final_home) - hh) + (float(final_away) - ha)
        if second == line:
            return np.nan
        won = second > line
        return float(won if side == "over" else not won)
    if market in ("spreads", "spreads_h2"):
        margin = float(final_home) - float(final_away)
        if market == "spreads_h2":
            hh = float(row.get("half_home_score", row["home_score_pre"]))
            ha = float(row.get("half_away_score", row["away_score_pre"]))
            margin = (float(final_home) - hh) - (float(final_away) - ha)
        adj = margin + line if side == "home" else -(margin + line)
        if adj == 0:
            return np.nan
        return float(adj > 0)
    return np.nan


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    """
    Per lane per season: n, hit rate, ROI at the quoted price, pseudo-CLV and
    edge-bucket calibration. This table is what the kill criteria read.
    """
    if df.empty:
        return df
    out = []
    for (lane, season), g in df.groupby(["lane", "season"]):
        settled = g[g["won"].notna()]
        stake = len(settled)
        ret = float((settled["won"] * (settled["decimal"] - 1)
                     - (1 - settled["won"])).sum())
        out.append({
            "lane": lane, "season": int(season), "n": int(len(g)),
            "settled": stake,
            "hit_rate": float(settled["won"].mean()) if stake else float("nan"),
            "roi": ret / stake if stake else float("nan"),
            "pseudo_clv_pp": float(g["pseudo_clv"].mean() * 100)
            if g["pseudo_clv"].notna().any() else float("nan"),
            "clv_positive_rate": float((g["pseudo_clv"] > 0).mean())
            if g["pseudo_clv"].notna().any() else float("nan"),
        })
    return pd.DataFrame(out).sort_values(["lane", "season"])


def kill_verdict(summary: pd.DataFrame) -> dict:
    """
    Apply the build spec's kill criteria, without appeal.

    A lane with pseudo-CLV at or below zero across two seasons is CUT. Written
    as code so the decision cannot quietly be relitigated by looking at the
    numbers first and choosing a rule afterwards.
    """
    verdict = {}
    for lane in BETTABLE_LANES:
        g = summary[summary.lane == lane]
        if g.empty:
            verdict[lane] = {"status": "NO DATA", "detail": "no rows replayed"}
            continue
        seasons_pos = (g["pseudo_clv_pp"] > 0).sum()
        verdict[lane] = {
            "status": "KEEP" if seasons_pos >= 2 else "CUT",
            "seasons": int(len(g)),
            "seasons_positive_clv": int(seasons_pos),
            "mean_clv_pp": float(g["pseudo_clv_pp"].mean()),
            "detail": "positive pseudo-CLV in both seasons"
            if seasons_pos >= 2 else
            "fails the spec's kill criterion: pseudo-CLV not positive in two seasons",
        }
    return verdict


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", type=int, nargs="+", default=[2023, 2024])
    ap.add_argument("--sample-every", type=int, default=1)
    args = ap.parse_args()

    df = replay(args.seasons, args.sample_every)
    if df.empty:
        print("\nNo rows to summarise. The harness is wired but has no in-play "
              "snapshots to replay: pull them with live_model.backtest.pull_snaps.")
        return
    summary = summarise(df)
    print(summary.to_string(index=False))
    print("\nkill criteria:")
    for lane, v in kill_verdict(summary).items():
        print(f"  {lane:14s} {v['status']:8s} {v['detail']}")


if __name__ == "__main__":
    main()
