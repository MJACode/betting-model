#!/usr/bin/env python3
"""
Daily opener-spread bet card — the LIVE deployment of `models/opener_spread.py`.

This module is plumbing: fetch the board, hand it to the model, print the card
and write the CSV the platform publisher reads. THE RULE, the evidence, the
per-bet win probability and the selection all live in `models/opener_spread.py`
— change them there, not here.

    python scripts/daily_opener_card.py            # scan the T-2..T-7 window
    python scripts/daily_opener_card.py --threshold 1.5

Cost: 2 credits per run (regions=us,eu x markets=spreads — eu is required,
that's where Pinnacle lives). Zero cost when no games are in the window.
Output: printed card + data/cards/opener_card_YYYY-MM-DD.csv.

EVIDENCE, RESTATED 2026-08-23 ON SIX SEASONS
--------------------------------------------
A 27,300-credit scan added 2020-2022 at the same 6-hourly resolution the
2023-2025 result was built on. The edge did not survive it:

  |dev| >= 1.0 : n=1,178, ATS 56.88% vs 54.60% expected from the number bought,
  +2.27pp excess [95% CI -0.6, +5.1]; ROI +1.34% [-3.9, +6.4]. Both span zero.
  Season ROI 2020..2025: -2.62 / -1.78 / -2.80 / +4.72 / +10.86 / +0.32. The
  three seasons added are all negative and the profit is nearly all 2024. The
  DraftKings placebo returns +0.95pp against the model's +2.27pp.

  Previously published as +6.82% on 2023-2025 alone. Two corrections rather
  than new information: backtest_opener had never excluded EXCHANGES though
  this card always has (that alone takes 2023-2025 to +5.37%), plus three
  worse seasons.

LIVE by explicit decision (2026-08-23), and sized to survive being wrong: the
six-season probabilities are ~2.8pp below the three-season table, and the
publisher stakes Kelly-proportionally per bet rather than 1u flat. Over
2020-2025 that is +5.45% on units staked against +1.28% flat, because 89% of
picks carry ~+1.6pp of edge and return -0.30% while the rare big deviations
carry +3.7 to +11pp. A quote whose juice has eaten the edge is staked at ZERO.

Retire it on a 2026 season at or below flat.

Each pick carries `edge_pp` and an `edge_tier` of SMALL / MEDIUM / LARGE, so
the size of the predicted edge is visible rather than implied. The tier moves
with the juice as well as the deviation, which is the useful part: a 2-point
deviation at -140 is a smaller edge than a 1-pointer at -110.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_nfl_model(name: str):
    """
    Import a sibling module from nfl/models/ by absolute path.

    A bare `from models.opener_spread import ...` is NOT safe here. The
    platform repo has its own top-level `models` package with an __init__.py,
    so whenever both roots are on sys.path — running from the repo root, or
    under pytest — that package wins and this one becomes invisible; the import
    does not fall back, it raises. Loading by path is unambiguous regardless of
    sys.path order, and is what tests/test_nfl_opener.py already does.
    """
    import importlib.util
    path = Path(__file__).resolve().parents[1] / "models" / f"{name}.py"
    mod_name = f"nfl_model_{name}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec: a module using @dataclass under
    # `from __future__ import annotations` resolves annotations through
    # sys.modules[cls.__module__] and raises without this.
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


opener_spread = _load_nfl_model("opener_spread")

# Re-exported so this module stays the single entry point for callers and
# tests. The definitions live in models/opener_spread.py.
american_to_prob = opener_spread.american_to_prob
model_prob_for_dev = opener_spread.model_prob_for_dev
edge_tier = opener_spread.edge_tier
select_opener_bets = opener_spread.select_opener_bets

DEFECTIVE_BOOKS = opener_spread.DEFECTIVE_BOOKS
EXCHANGES = opener_spread.EXCHANGES
REFERENCE = opener_spread.REFERENCE
DEPLOY_THRESHOLD = opener_spread.DEPLOY_THRESHOLD
LEAD_LO_DAYS = opener_spread.LEAD_LO_DAYS
LEAD_HI_DAYS = opener_spread.LEAD_HI_DAYS
POOLED_MODEL_PROB = opener_spread.POOLED_MODEL_PROB
DEV_WIN_PROB = opener_spread.DEV_WIN_PROB
EDGE_TIERS = opener_spread.EDGE_TIERS


def load_window_schedule(lo_days: float = LEAD_LO_DAYS,
                         hi_days: float = LEAD_HI_DAYS) -> pd.DataFrame:
    g = pd.read_csv("data/games.csv")
    dt = pd.to_datetime(g.gameday + " " + g.gametime, errors="coerce")
    g["kick_utc"] = (dt.dt.tz_localize(ZoneInfo("America/New_York"), ambiguous=True,
                                       nonexistent="shift_forward").dt.tz_convert("UTC"))
    now = pd.Timestamp.now(tz="UTC")
    g = g[(g.kick_utc > now + pd.Timedelta(days=lo_days))
          & (g.kick_utc <= now + pd.Timedelta(days=hi_days))].copy()
    g["matchup"] = g.away_team + " @ " + g.home_team
    g["lead_days"] = (g.kick_utc - now).dt.total_seconds() / 86400
    return g


# How far back the number-age label looks. A day is enough to tell "NEW" from
# "up 5h" from "up 1d"; the Supabase side is compressed to change points, so
# the window's cost is a server-side scan, not rows over the wire.
PRIOR_HOURS = 24.0

PRIOR_COLS = ["observed_at", "home", "away", "book", "point"]


def load_prior_observations(sched: pd.DataFrame, now=None,
                            hours: float = PRIOR_HOURS) -> pd.DataFrame:
    """
    Every spread quote seen on the watched games in the last `hours`, for the
    number-age label on each pick (models/opener_spread.FRESH_MINUTES).

    Two sources, unioned, because neither is complete on its own:

      1. This worker's own board dumps (`data/cards/board_<date>.csv`, today
         and yesterday) -- minute resolution, free, but on the worker's
         ephemeral disk, so a redeploy starts them from empty (seven deploys on
         2026-09-22 alone).
      2. Supabase: `nfl_odds_history` (the archive those dumps are flushed
         into, hourly at best and with gaps) and `odds` (the platform's own
         refresh passes, every bettable book, roughly hourly). Survives a
         redeploy.

    An EMPTY frame is a valid answer and means every pick this tick reads
    "age unknown"; the caller says so loudly. A failing source is a warning,
    never a crash, and never a reason not to bet. `odds.snapshot_at` is TEXT in two
    ISO shapes ('...Z' and '...+00:00'); both share the 'YYYY-MM-DDTHH:MM:SS'
    prefix, so the bound is compared as text and cast in the query.

    Only the books the label can ever be asked about are loaded (the bettable
    set plus Pinnacle), and the Supabase side returns CHANGE POINTS -- each
    (game, book)'s first row, every row whose number differs from the one
    before, and its latest row -- which is all `held_minutes` needs. The first
    version pulled every archived quote and came back with 508,217 rows for
    one tick; this comes back with a few hundred.
    """
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    since = now - pd.Timedelta(hours=hours)
    books = sorted(opener_spread._bettable_books() | {opener_spread.REFERENCE})
    parts: list[pd.DataFrame] = []
    counts: dict[str, object] = {}

    n_local = 0
    for day in (now, now - pd.Timedelta(days=1)):
        p = Path("data/cards") / f"board_{day:%Y-%m-%d}.csv"
        if not p.exists():
            continue
        try:
            b = pd.read_csv(p, usecols=["snapshot_at", "home", "away", "bookmaker",
                                        "market", "point"])
        except Exception as exc:                               # noqa: BLE001
            print(f"WARNING: could not read {p}: {exc}", file=sys.stderr)
            continue
        b = b[(b.market == "spreads") & b.bookmaker.isin(books)]
        parts.append(pd.DataFrame({
            "observed_at": pd.to_datetime(b.snapshot_at, utc=True, format="mixed",
                                          errors="coerce"),
            "home": b.home, "away": b.away, "book": b.bookmaker,
            "point": pd.to_numeric(b.point, errors="coerce")}))
        n_local += len(b)
    counts["local"] = n_local

    if len(sched):
        by_id = {f"NFL_{g.game_id}": (g.home_team, g.away_team)
                 for g in sched.itertuples()}
        try:
            from data.db import get_connection
            conn = get_connection()
            try:
                rows = conn.execute("""
                    WITH u AS (
                        SELECT snapshot_at, game_id, bookmaker, point::float AS point
                        FROM nfl_odds_history
                        WHERE market = 'spreads' AND game_id = ANY(%s)
                          AND bookmaker = ANY(%s) AND snapshot_at >= %s
                        UNION ALL
                        SELECT snapshot_at::timestamptz, game_id, bookmaker,
                               spread_home::float
                        FROM odds
                        WHERE sport = 'NFL' AND market = 'spreads' AND game_id = ANY(%s)
                          AND bookmaker = ANY(%s) AND spread_home IS NOT NULL
                          AND snapshot_at >= %s
                    ), s AS (
                        SELECT snapshot_at, game_id, bookmaker, point,
                               lag(point) OVER w AS prev,
                               row_number() OVER (PARTITION BY game_id, bookmaker
                                                  ORDER BY snapshot_at DESC) AS rn
                        FROM u
                        WINDOW w AS (PARTITION BY game_id, bookmaker ORDER BY snapshot_at)
                    )
                    SELECT snapshot_at::text, game_id, bookmaker, point
                    FROM s
                    WHERE prev IS NULL OR prev <> point OR rn = 1
                    ORDER BY game_id, bookmaker, snapshot_at
                """, (list(by_id), books, since.to_pydatetime(),
                      list(by_id), books, since.strftime("%Y-%m-%dT%H:%M:%S"))).fetchall()
            finally:
                conn.close()
            if rows:
                db = pd.DataFrame(rows, columns=["observed_at", "game_id", "book", "point"])
                ha = db.game_id.map(by_id)
                db["home"] = ha.map(lambda t: t[0] if isinstance(t, tuple) else None)
                db["away"] = ha.map(lambda t: t[1] if isinstance(t, tuple) else None)
                # format="mixed": the archive stamps microseconds and the
                # refresh pass does not, and pandas otherwise infers the format
                # from the first row and coerces every other shape to NaT --
                # measured: the loader silently dropped every archive row.
                db["observed_at"] = pd.to_datetime(db.observed_at, utc=True,
                                                   format="mixed", errors="coerce")
                parts.append(db[PRIOR_COLS])
            counts["db"] = len(rows)
        except Exception as exc:                               # noqa: BLE001
            print(f"WARNING: prior observations from Supabase unavailable: {exc}",
                  file=sys.stderr)
            counts["db"] = "unavailable"

    print(f"prior spread observations for the number-age label: {counts}",
          file=sys.stderr)
    if not parts:
        return pd.DataFrame(columns=PRIOR_COLS)
    out = pd.concat(parts, ignore_index=True).dropna(subset=["observed_at", "point"])
    out = out[(out.observed_at >= since) & (out.observed_at <= now)]
    return out[PRIOR_COLS].reset_index(drop=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=DEPLOY_THRESHOLD)
    ap.add_argument("--regions", default="us,eu",
                    help="must include eu — that's where Pinnacle lives")
    ap.add_argument("--watch-days", type=float, default=10.0,
                    help="observe games this far out (firing stays in T-7..T-2)")
    ap.add_argument("--bankroll", type=float, default=1000.0,
                    help="only for showing the stake in money on the printed card")
    a = ap.parse_args()

    # Two windows, and since 2026-09-06 they share an early bound.
    #
    # WATCH from 10 days out: every observation of every game is recorded, so a
    # locked pick's history is continuous rather than starting when it fires.
    #
    # FIRE from the same horizon down to T-2. This used to stop at T-7, which
    # sounds conservative and was not: Pinnacle had posted for the whole Week-1
    # board on 2026-09-06 with seven qualifying deviations, and the card sat on
    # them because the Sunday games were 7.19 days out. Waiting is not free
    # here — the edge IS the soft book's staleness, and every hour of it is an
    # hour the soft book might correct. See opener_spread.LEAD_HI_DAYS for what
    # this costs in evidence: pre-T-7 bets are outside the backtested span.
    #
    # The LATE bound is untouched at T-2.
    watch = load_window_schedule(lo_days=0.0, hi_days=a.watch_days)
    sched = load_window_schedule(hi_days=a.watch_days)
    if watch.empty:
        print(f"No games inside the {a.watch_days:.0f}-day watch horizon.")
        return 0

    key = os.environ.get("THE_ODDS_API_KEY")
    if not key:
        # Scheduled runs must not go red weekly on a missing key: the opener
        # has no weather-only dry-run side — without odds there is no card.
        print("THE_ODDS_API_KEY not set — opener card needs live odds; skipping.")
        return 0

    from data_ingest.odds_api import OddsAPIClient, ledger_status
    from data_ingest.parse import snapshot_to_frame

    client = OddsAPIClient(key, quota_guard=200)
    res = client.live_odds(regions=a.regions, markets="spreads")
    print(f"odds pulled, cost {res.cost} credit(s), ledger now {ledger_status()}",
          file=sys.stderr)
    frame = snapshot_to_frame(res.payload, "live")

    # Dump DraftKings' spreads for every upcoming game (wider than the card's
    # own T-2..T-7 window — this daily dump is what carries snapshot coverage
    # through game day for already-locked opener picks, so the app can show
    # how far the market has moved off the locked number). Enrichment only —
    # never sink the card. Runs BEFORE the no-qualifying-bets early exit.
    try:
        from data_ingest.line_snapshots import dump_dk_lines
        dump_dk_lines(frame, "spreads")
        from data_ingest.pick_eval import dump_board
        dump_board(frame)
    except Exception as exc:
        print(f"WARNING: line snapshot dump failed: {exc}", file=sys.stderr)

    # The history the number-age label reads. Loaded AFTER the board dump above
    # so this tick is in it too, and passed to BOTH the evaluation and the
    # selection so the audit trail and the card say the same age. Empty means
    # every pick this tick reads "age unknown" -- said out loud.
    now = pd.Timestamp.now(tz="UTC")
    prior = load_prior_observations(watch, now)
    if prior.empty:
        print("WARNING: no prior spread observations for the watched games -- "
              "any pick this tick will carry 'age unknown'", file=sys.stderr)

    # Record the model's view of EVERY game on the board, qualifying or not.
    # This is what lets a locked pick be told "the deviation is gone" without
    # anything being able to retract the bet. Enrichment only, never fatal.
    try:
        from data_ingest.pick_eval import dump_eval_rows
        dump_eval_rows(opener_spread.evaluate_board(frame, watch, a.threshold,
                                                    prior=prior, now=now))
    except Exception as exc:                                   # noqa: BLE001
        print(f"WARNING: opener pick-eval dump failed: {exc}", file=sys.stderr)

    bets = select_opener_bets(frame, sched, threshold=a.threshold,
                              prior=prior, now=now)
    if bets is None or len(bets) == 0:
        print(f"No qualifying opener bets at |dev| >= {a.threshold} "
              f"({len(watch)} game(s) watched, {len(sched)} inside T-7..T-2).")
        # An earlier run's card must not outlive it: data_ingest/cards.py.
        from data_ingest.cards import clear_card
        clear_card("opener_card")
        return 0

    print(f"\n=== OPENER SPREAD CARD  {datetime.now(timezone.utc):%Y-%m-%d %H:%MZ} ===")
    bets = bets.copy()
    bets["stake_amt"] = (bets.stake_pct / 100 * a.bankroll).round(2)
    bets["line_age"] = [opener_spread.age_tag(h) for h in bets.held_min]
    cols = ["matchup", "kick_utc", "bet_team", "side_line", "book", "price",
            "dev", "line_age", "model_prob", "edge_pp", "edge_tier", "units",
            "stake_amt"]
    print(bets[cols].to_string(index=False))
    tiers = bets.edge_tier.value_counts().to_dict()
    print("edge size: " + ", ".join(f"{tiers.get(t, 0)} {t}"
                                    for _, t in EDGE_TIERS) +
          "  (SMALL <3pp, MEDIUM 3-5.5pp, LARGE 5.5pp+ over the quoted price)")
    print(f"total {bets.units.sum():.2f} units. 1 unit = "
          f"{opener_spread.UNIT_PCT*100:.2f}% of bankroll = "
          f"{opener_spread.UNIT_PCT*a.bankroll:,.2f} at {a.bankroll:,.0f}. "
          f"Bets under {opener_spread.MIN_UNITS}u are skipped, not shrunk.")
    print(f"\n{len(bets)} bet(s). NOTE: already-taken games are locked by the "
          "publisher — a game reappearing here does NOT re-price its bet.")

    out = Path("data/cards"); out.mkdir(parents=True, exist_ok=True)
    p = out / f"opener_card_{datetime.now(timezone.utc):%Y-%m-%d}.csv"
    bets.to_csv(p, index=False)
    print(f"\nwritten: {p}")
    return 0


if __name__ == "__main__":
    # API telemetry for the live monitor (monitoring/). Guarded: this package is
    # standalone, and the repo root only reaches sys.path when the scheduler
    # supplies PYTHONPATH — run on its own it simply records nothing.
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("nfl-opener-card")
    except Exception:  # noqa: BLE001
        pass

    raise SystemExit(main())
