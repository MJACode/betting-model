"""
Where in the week does the sharp-vs-soft prop edge actually live?

Every number in docs/nfl_props_model.md §5c is measured at ONE snapshot, ~3h
before kickoff, because that is how the backfill was built. That says nothing
about T-2 days or T-1 hour, and the answer decides the polling cadence — which
for props is a real cost question, not a free one: a prop pull is ~61 credits
per event, roughly 20x a game-line tick, so the §28 opener's hourly-from-T-10-
days cadence would cost ~1.26M credits a season.

The two things worth knowing are different, and only one needs volume:

  AVAILABILITY — how many qualifying edges exist at each offset. This is the
  cadence question and a few hundred quotes answer it.
  PROFITABILITY at each offset — needs far more bets than a sampled experiment
  provides, so it is reported with its bet count and should not be read as a
  verdict on any single offset.

Run after an `odds-timing` backfill has populated the t48/t24/t6/t1 series:
    python -m scripts.nfl_prop_timing
"""
from __future__ import annotations

import pandas as pd

from data import local_store
from data.ingestors.nfl_props_data_ingestor import norm_player_name
import models.nfl_prop_market as mk

# snapshot_type -> hours before the 17:00 UTC anchor
SERIES = {"t48": 48, "t24": 24, "open": 3, "t6": 6, "t1": 1}


def _actuals(log: pd.DataFrame) -> dict:
    log = log.copy()
    log["k"] = log.player_name.map(norm_player_name)
    log["ANY_TD"] = ((log.rushing_tds.fillna(0) + log.receiving_tds.fillna(0)) >= 1).astype(float)
    out = {}
    for r in log.itertuples(index=False):
        for m, c in mk.MARKET_STAT.items():
            v = getattr(r, c, None)
            if v is not None and not pd.isna(v):
                out[(r.game_id, r.k, m)] = float(v)
    return out


def main(min_edge: float = 0.05) -> None:
    local_store.activate()
    odds = local_store.read_table("nfl_prop_odds")
    if odds is None or "snapshot_type" not in odds.columns:
        raise SystemExit("cache has no snapshot_type — re-run scripts.pull_local_cache")
    act = _actuals(local_store.read_table("nfl_player_game_log"))
    ko = {r.game_id: r.commence_time for r in
          local_store.read_table("nfl_team_game_stats",
                                 columns=["game_id", "commence_time"])
          .dropna(subset=["commence_time"]).itertuples(index=False)}

    odds = odds[odds.market.isin(mk.SHARP_MARKETS)].copy()
    odds["k"] = odds.player_name.map(norm_player_name)

    # Only the games the experiment actually sampled, or the comparison is
    # between a full season at T-3h and eight dates everywhere else.
    sampled = set(odds[odds.snapshot_type.isin([s for s in SERIES if s != "open"])].game_id)
    if not sampled:
        raise SystemExit("no timing series in the cache yet")
    odds = odds[odds.game_id.isin(sampled)]

    print(f"{len(sampled)} sampled games | min_edge {min_edge:.0%}\n")
    print(f"{'offset':<9}{'quotes':>8}{'compared':>10}{'edges':>7}{'bets':>6}"
          f"{'win%':>8}{'ROI%':>9}   note")
    for stype, hrs in sorted(SERIES.items(), key=lambda kv: -kv[1]):
        d = odds[odds.snapshot_type == stype]
        if d.empty:
            continue
        d = d.sort_values("snapshot_at", kind="stable")
        q, snap = {}, {}
        for r in d.itertuples(index=False):
            key = (r.game_id, r.k, r.market, r.bookmaker)
            q[key] = {"line": r.line, "over_price": r.over_price,
                      "under_price": r.under_price}
            snap[key] = r.snapshot_at
        bets, diag = mk.find_bets(q, min_edge=min_edge)
        graded = mk.grade(bets, act, snap, ko, dedupe=True)
        s = mk.summarise(graded) if graded else {"bets": 0, "win_pct": 0, "roi_pct": 0}
        note = "" if s["bets"] >= 100 else f"only {s['bets']} bets — availability only"
        print(f"T-{hrs:<7}{len(q):>8,}{diag['compared']:>10,}{diag['bets']:>7,}"
              f"{s['bets']:>6}{s['win_pct']:>8.1f}{s['roi_pct']:>+9.2f}   {note}")


if __name__ == "__main__":
    main()
