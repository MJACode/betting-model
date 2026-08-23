"""
Does the LIVE card select what the validated backtest graded?

The +10.33% in docs/nfl_props_model.md §5c is measured by feeding quotes
straight into models.nfl_prop_market. The thing that will actually run on
Sunday is scripts/nfl_prop_market_card, which reaches those quotes through a
slate query, a started-game guard, a soft-book filter and a dedupe. Every one of
those is a chance for the live board to differ from the record it is sold on,
and none of them would raise if it did — the symptom is a different set of bets,
not an error.

So this replays past slates THROUGH THE CARD, grades what the card chose, and
compares it to the backtest path on the same data. They should agree exactly.

Reads the committed local cache, so it costs nothing and needs no database.

    python -m scripts.nfl_prop_replay
    python -m scripts.nfl_prop_replay --season 2025 --lead-hours 3
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

import pandas as pd

from data import local_store
from data.ingestors.nfl_props_data_ingestor import norm_player_name
import models.nfl_prop_market as mk
import scripts.nfl_prop_market_card as card_mod


def _actuals(log: pd.DataFrame) -> dict:
    log = log.copy()
    log["k"] = log.player_name.map(norm_player_name)
    log["ANY_TD"] = ((log.rushing_tds.fillna(0) + log.receiving_tds.fillna(0)) >= 1).astype(float)
    log[mk.DERIVED_RUSH_REC] = (log.rushing_yards.fillna(0)
                                + log.receiving_yards.fillna(0))
    out = {}
    for r in log.itertuples(index=False):
        for m, c in mk.MARKET_STAT.items():
            v = getattr(r, c, None)
            if v is not None and not pd.isna(v):
                out[(r.game_id, r.k, m)] = float(v)
    return out


def _cadence(odds, act, ko, dates, min_edge: float) -> None:
    """
    What the scheduled cadence actually yields, run through the card.

    Production polls each game at ~T-24h and ~T-3h and the publisher locks
    insert-once, so the second tick can only ADD. Historically those two moments
    live in different snapshot series ('t24' and 'open'), which is why this
    needs to point the card at each in turn — live there is only one series and
    the card just takes the latest quote before now.

    Restricted to the games that have BOTH series, or the comparison is one
    offset over a full season against the other over eight dates.
    """
    from datetime import timedelta
    import models.nfl_prop_market as _mk

    have = {}
    for st in ("t24", "open"):
        have[st] = set(odds[odds.snapshot_type == st].game_id)
    both = have["t24"] & have["open"]
    if not both:
        print("no games carry both series — run an odds-timing backfill first")
        return

    snaps = {}
    o = odds[odds.market.isin(_mk.SHARP_MARKETS)].copy()
    o["k"] = o.player_name.map(norm_player_name)
    for r in o.sort_values("snapshot_at", kind="stable").itertuples(index=False):
        snaps[(r.game_id, r.k, r.market, r.bookmaker)] = r.snapshot_at

    results = {}
    for label, st, lead in (("T-24h", "t24", 24.0), ("T-3h", "open", 3.0)):
        bets, seen = [], set()
        for d in dates:
            games = {g: v for g, v in card_mod.slate(None, d, d).items() if g in both}
            if not games:
                continue
            for kick in sorted({card_mod._as_dt(ko[g]) for g in games if ko.get(g)}):
                if kick is None:
                    continue
                got, _diag, _ = card_mod.card(
                    None, d, d, min_edge, games=games,
                    now=kick - timedelta(hours=lead),
                    snapshot_types=(st,))
                for b in got:
                    key = (b.game_id, b.player, b.market, b.side)
                    if key in seen:
                        continue
                    seen.add(key)
                    bets.append(b)
        results[label] = bets

    print(f"{len(both)} games carry both series\n")
    print(f"{'':<14}{'bets':>6}{'win%':>7}{'ROI%':>8}{'  CI':>14}")
    for label, bets in results.items():
        s = _mk.summarise(_mk.grade(bets, act, snaps, ko), draws=5000)
        if s.get("bets"):
            print(f"{label:<14}{s['bets']:>6}{s['win_pct']:>6.1f}%{s['roi_pct']:>+8.2f}%"
                  f"  ({s['roi_ci'][0]:+.1f},{s['roi_ci'][1]:+.1f})")
        else:
            print(f"{label:<14}{'0':>6}")

    # Both polls, insert-once — which is what the scheduler will do.
    merged, seen = [], set()
    for label in ("T-24h", "T-3h"):
        for b in results[label]:
            key = (b.game_id, b.player, b.market, b.side)
            if key in seen:
                continue
            seen.add(key)
            merged.append(b)
    s = _mk.summarise(_mk.grade(merged, act, snaps, ko), draws=5000)
    if s.get("bets"):
        print(f"{'BOTH polls':<14}{s['bets']:>6}{s['win_pct']:>6.1f}%{s['roi_pct']:>+8.2f}%"
              f"  ({s['roi_ci'][0]:+.1f},{s['roi_ci'][1]:+.1f})")
    print("\nThe second poll can only ADD — the publisher locks insert-once. "
          "More bets at a similar return is the case for polling twice; a lower "
          "return means the extra offset is buying noise.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=None)
    ap.add_argument("--lead-hours", type=float, default=3.0,
                    help="replay each slate this many hours before its kickoff")
    ap.add_argument("--min-edge", type=float, default=card_mod.MIN_EDGE)
    ap.add_argument("--cadence", action="store_true",
                    help="replay the SCHEDULED two-poll cadence (T-24h then "
                         "T-3h, insert-once) over the games that have both "
                         "series — the first end-to-end number for it")
    a = ap.parse_args()

    local_store.activate()
    odds = local_store.read_table("nfl_prop_odds")
    act = _actuals(local_store.read_table("nfl_player_game_log"))
    tg = local_store.read_table(
        "nfl_team_game_stats",
        columns=["game_id", "commence_time", "team", "opponent", "is_home", "game_date"]
    ).dropna(subset=["commence_time"])
    ko = {r.game_id: r.commence_time for r in tg.itertuples(index=False)}

    dates = sorted({str(d)[:10] for d in tg.game_date})
    if a.season:
        dates = [d for d in dates if f"NFL_{a.season}_" in "".join(
            g for g in ko if str(ko[g])[:10] == d) or d.startswith(str(a.season))]
    # Only dates that actually have quotes — the rest replay to an empty card.
    priced = {str(d)[:10] for d in odds.game_date.unique()}
    dates = [d for d in dates if d in priced]

    # Replay each date as production runs it: SEVERAL ticks, not one, with
    # insert-once dedupe. One clock per date is wrong and it is not a small
    # wrongness — a 9:30am ET London game pulls the whole day's clock back
    # before the afternoon slate is even priced, and every quote stamped later
    # is then invisible. Measured on 2025-10-05 that silently dropped all 3,650
    # quotes and every bet on the card.
    if a.cadence:
        _cadence(odds, act, ko, dates, a.min_edge)
        return

    all_bets, seen, slates, ticks = [], set(), 0, 0
    for d in dates:
        kicks = sorted(k for k in
                       (card_mod._as_dt(v) for g, v in ko.items() if str(v)[:10] == d)
                       if k)
        if not kicks:
            continue
        games = card_mod.slate(None, d, d)
        if not games:
            continue
        slates += 1
        # One tick per distinct kickoff, at that game's own lead — the coarse
        # equivalent of the hourly cadence, and enough for every game to be
        # priced while it is still pre-game.
        for kick in sorted({k for k in kicks}):
            now = kick - timedelta(hours=a.lead_hours)
            bets, _diag, _ = card_mod.card(None, d, d, a.min_edge,
                                           games=games, now=now)
            ticks += 1
            for b in bets:
                key = (b.game_id, b.player, b.market, b.side)
                if key in seen:      # the publisher's insert-once lock
                    continue
                seen.add(key)
                all_bets.append(b)

    # Grade what the CARD chose, with the same grader the backtest uses.
    snaps = {}
    o = odds[odds.market.isin(mk.SHARP_MARKETS)].copy()
    o["k"] = o.player_name.map(norm_player_name)
    for r in o.sort_values("snapshot_at", kind="stable").itertuples(index=False):
        snaps[(r.game_id, r.k, r.market, r.bookmaker)] = r.snapshot_at
    graded = mk.grade(all_bets, act, snaps, ko)
    s = mk.summarise(graded, draws=5000)

    print(f"replayed {slates} slates ({ticks} card runs) at T-{a.lead_hours:g}h "
          f"per game, min edge {a.min_edge:.0%}")
    print(f"card selected {len(all_bets)} bets, {s.get('bets', 0)} graded")
    if s.get("bets"):
        print(f"  win {s['win_pct']:.1f}%  ROI {s['roi_pct']:+.2f}%  "
              f"CI ({s['roi_ci'][0]:+.1f},{s['roi_ci'][1]:+.1f})  units {s['units']:+.1f}")
        print("  " + "  ".join(f"{k}:{v['roi_pct']:+.1f}%({v['bets']})"
                               for k, v in sorted(s["per_season"].items())))
    print("\nCompare against docs/nfl_props_model.md §5c. The card reaches the "
          "same quotes through a slate query, a started-game guard, a soft-book "
          "filter and a dedupe; a materially different bet count means one of "
          "those is silently changing the strategy.")


if __name__ == "__main__":
    main()
