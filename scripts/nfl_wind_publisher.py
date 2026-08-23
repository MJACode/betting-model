"""
Publish the NFL wind-totals card into the platform's picks table.

The nfl/ package is standalone by design (CLAUDE.md Section 28) — its weekly
wind card prints to the Railway log and writes a CSV on the worker's ephemeral
disk. This publisher bridges that card into the app: after each scheduled LIVE
card run (scheduler.run_nfl_wind_card), it reads the day's card CSV and mirrors
the qualifying bets into `games` + `picks`, so they surface in the mobile app
like any other pick and settle through the standard game-level path.

Conventions (load-bearing):
- game_id = "NFL_" + the nflverse game id (e.g. NFL_2026_01_NE_SEA). The
  nflverse id is stable across flex-schedule date changes and is the join key
  the results ingestor uses — settlement can never miss on a date mismatch.
- model_id = "nfl_wind_totals"; picks are ALWAYS the under (the rule is
  under-only — it is not a spread or over play, see nfl/models/wind_totals.py).
- dk_odds stores the card's BEST-BOOK price. The wind card line-shops across
  books by design; the platform's DraftKings-only invariant applies to models
  that score against DK lines, which this standalone model never does. The
  book is named in pick_label so the price is never mistaken for a DK quote.
- Delete + replace for FUTURE kickoffs only: each card run re-prices whatever
  is still in its window (runbook: later is better — the edge is vs the close
  and forecast skill improves), so unstarted NFL wind picks that are NOT on
  the latest live card are cleared (wind dropped / line moved past the edge
  gate). Started games are never touched — the UFC/golf look-ahead precedent;
  NFL picks are future-dated and exempt from the first-run lock.
- NEVER run after a --dry-run card: a dry run has no prices and writes no CSV,
  and clearing picks off it would wipe a valid board. The scheduler only
  invokes this after a live run (THE_ODDS_API_KEY/ODDS_API_KEY present).

OPENER MODE (--opener): publishes the daily opener-spread card
(nfl/scripts/daily_opener_card.py) as model `nfl_opener_spread`. The locking
is the OPPOSITE of wind: an opener bet locks at the FIRST qualifying moment
(~T-6..T-2 days out) and is NEVER re-priced or removed — the edge IS the
staleness of the number taken; waiting or refreshing destroys it. So opener
publishing is insert-once per (game, model): a game that already has an
opener pick (settled or not) is skipped, and no-card days clear nothing.

LINE SNAPSHOTS: every publish also flushes the day's DraftKings line-snapshot
CSV (dumped by the card scripts from the odds payload they already fetched —
zero extra credits) into the odds table, so the app's movement chip and Line
Movement card show how the market has moved since an NFL pick was locked.
See publish_line_snapshots().

Run (from repo root, after a LIVE card run only):
    python -m scripts.nfl_wind_publisher                    # today's wind card (UTC date)
    python -m scripts.nfl_wind_publisher --opener           # today's opener card
    python -m scripts.nfl_wind_publisher --snapshots        # flush line snapshots only
    python -m scripts.nfl_wind_publisher --date 2026-09-10
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

NFL_WIND_MODEL_ID = "nfl_wind_totals"
NFL_OPENER_MODEL_ID = "nfl_opener_spread"

# Opener staking. Same unit as the wind model so one bankroll covers both.
#
# SCALE AND CAP WERE VALIDATED OUT-OF-SAMPLE (2026-08-23), walk-forward:
# calibrate on prior seasons only, bet the next, never letting the sizing see
# its own outcomes. Pooled over five held-out seasons:
#
#   flat 1u (the old rule)      601 bets  601u staked  +23.66u   +3.94%
#   Kelly x1, cap 2, no skip    601 bets  220u staked  +20.98u   +9.52%
#   Kelly x2, cap 4, skip 0.25  463 bets  424u staked  +41.08u   +9.68%  <- this
#
# So the sizing is real: +9.52% out-of-sample against flat's +3.94%, positive
# in 5/5 held-out seasons. But at x1/cap2 it was leaving money on the table —
# it risked only 220u where flat risked 601u. Scaling to x2 with the cap raised
# to 4 nearly DOUBLES flat's profit while still risking less than flat, at the
# best ROI of any configuration tested. Max drawdown -14.5u across the five
# seasons, comfortably inside the drawdown budget in nfl/scripts/stake_sizing.py.
#
# The cap has to rise with the scale. At x2.7 with the cap left at 2 the ROI
# fell to +7.58%, because the cap flattens exactly the big-edge bets the sizing
# exists to find. Scale and cap move together or not at all.
#
# More aggressive alternative, if the drawdown is acceptable: x2.5 / cap 5 /
# skip 0.25 returns +51.34u at +9.59% with a -18.1u max drawdown.
OPENER_UNIT_PCT = 0.01       # 1 unit = 1% of bankroll
OPENER_REF_KELLY = 0.0911    # wind's reference bet: lead 3, threshold 11, -110
OPENER_STAKE_SCALE = 2.0     # validated out-of-sample; see the table above
OPENER_MAX_UNITS = 4.0       # must scale with OPENER_STAKE_SCALE, not stay at 2

# Bets below this are SKIPPED, not floored.
#
# A floor was considered and the data rejected it. Out-of-sample, forcing a
# 0.5u minimum on the small bets added 132u of risk for -0.34u of profit: that
# marginal money returns -0.26%. It is not that tiny bets are unprofitable to
# place, it is that the bets which SIZE tiny are the ones carrying ~+1.6pp of
# edge, and that bucket returns -0.30%. Flooring them bets more on the worst
# bucket in the book.
#
# Skipping them instead does what a floor was reaching for — no trivial bets to
# place — and improves everything: skip <0.25u took the out-of-sample return
# from +20.98u on 220u staked to +23.10u on 185u, i.e. MORE profit for LESS
# risk (+12.47%). Skipping is the correct treatment of a bet too small to want.
OPENER_MIN_UNITS = 0.25
CARDS_DIR = Path(__file__).resolve().parent.parent / "nfl" / "data" / "cards"

_ET = ZoneInfo("America/New_York")

# Short labels for the best-price book named in pick_label. Unknown keys fall
# back to the raw key so a new book can never crash the publisher.
BOOK_ABBREV = {
    "draftkings": "DK",
    "fanduel": "FD",
    "betmgm": "MGM",
    "williamhill_us": "CZR",   # Caesars on The Odds API
    "caesars": "CZR",
    "espnbet": "ESPN",
    "betrivers": "BR",
    "bovada": "BOV",
    "pinnacle": "PIN",
    "matchbook": "MB (exch.)",  # exchange — price gross of commission
}


def parse_matchup(matchup: str) -> tuple[str, str]:
    """'NYJ @ MIA' -> ('NYJ', 'MIA'). Raises on any other shape."""
    away, sep, home = matchup.partition(" @ ")
    if not sep or not away.strip() or not home.strip():
        raise ValueError(f"unparseable NFL matchup: {matchup!r}")
    return away.strip(), home.strip()


def kick_fields(kick_utc: str) -> tuple[str, str]:
    """
    The card's kick_utc ('2026-09-13 17:00:00+00:00') -> (game_date, game_time).

    game_date is the EASTERN date (platform convention — a Sunday-night 8:20pm
    ET kickoff is 00:20 UTC Monday and must not land on Monday's board).
    game_time is the ISO commence_time in UTC (T separator), matching
    games.commence_time everywhere else.
    """
    dt = datetime.fromisoformat(kick_utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.astimezone(_ET).date().isoformat(), dt.isoformat()


def _fmt_line(total_line: float) -> str:
    """44.0 -> '44', 43.5 -> '43.5'."""
    return f"{total_line:g}"


def build_rows(card_rows: list[dict], bankroll: float) -> tuple[list[dict], list[dict]]:
    """
    Pure transform: card CSV rows -> (games rows, picks rows).

    Card columns (nfl/models/wind_totals.Bet): game_id, matchup, kick_utc,
    stadium_id, lead_days, forecast_wind, exp_true_wind, total_line, book,
    price, model_prob, market_prob, edge, stake_pct, ev_pct (+ stake_units).
    Rows that fail to parse are skipped with a message rather than sinking the
    whole card.
    """
    games: list[dict] = []
    picks: list[dict] = []
    for r in card_rows:
        try:
            nflverse_id = r["game_id"].strip()
            season = int(nflverse_id.split("_")[0])
            away, home = parse_matchup(r["matchup"])
            game_date, commence_iso = kick_fields(r["kick_utc"])
            total_line = float(r["total_line"])
            price = float(r["price"])
            model_prob = float(r["model_prob"])
            market_prob = float(r["market_prob"])
            edge = float(r["edge"])
            stake_pct = float(r["stake_pct"])
            wind = float(r["forecast_wind"])
            book = (r.get("book") or "").strip()
        except (KeyError, ValueError, IndexError) as exc:
            print(f"skipping unparseable card row ({exc}): {r}", file=sys.stderr)
            continue

        game_id = f"NFL_{nflverse_id}"
        kelly_fraction = round(stake_pct / 100.0, 6)
        games.append({
            "game_id": game_id,
            "sport": "NFL",
            "season": season,
            "game_date": game_date,
            "home_team": home,
            "away_team": away,
            "commence_time": commence_iso,
        })
        picks.append({
            "game_id": game_id,
            "model_id": NFL_WIND_MODEL_ID,
            "sport": "NFL",
            "game_date": game_date,
            "game_time": commence_iso,
            "pick_side": "under",
            "pick_label": (
                f"{away} @ {home} Under {_fmt_line(total_line)} "
                f"(Wind {wind:.0f} mph, {BOOK_ABBREV.get(book, book or '?')}) "
                f"· {stake_pct:.2f}u"
            ),
            "model_probability": model_prob,
            "dk_implied_prob": market_prob,   # de-vigged best-book prob
            "edge": edge,
            "dk_odds": price,                 # best-book price; book in label
            "scored_line": total_line,
            "kelly_fraction": kelly_fraction,
            "recommended_bet": round(kelly_fraction * bankroll, 2),
            "bankroll_at_pick": bankroll,
            "signal_type": "BET",
        })
    return games, picks


def build_opener_rows(card_rows: list[dict], bankroll: float) -> tuple[list[dict], list[dict]]:
    """
    Pure transform: opener card CSV rows -> (games rows, picks rows).

    Card columns (daily_opener_card.select_opener_bets): game_id, matchup,
    kick_utc, lead_days, side, bet_team, book, price, side_line,
    soft_home_line, pin_home_line, dev, model_prob, market_prob, edge.

    scored_line stores the SOFT book's HOME spread — the platform's spreads
    settle convention (covered = margin + spread_home; home wins >0, away <0),
    which grades both sides correctly from the one home-relative number.
    """
    games: list[dict] = []
    picks: list[dict] = []
    for r in card_rows:
        try:
            nflverse_id = r["game_id"].strip()
            season = int(nflverse_id.split("_")[0])
            away, home = parse_matchup(r["matchup"])
            game_date, commence_iso = kick_fields(r["kick_utc"])
            side = r["side"].strip()
            assert side in ("home", "away"), side
            bet_team = r["bet_team"].strip()
            side_line = float(r["side_line"])
            soft_home_line = float(r["soft_home_line"])
            price = float(r["price"])
            model_prob = float(r["model_prob"])
            market_prob = float(r["market_prob"])
            edge = float(r["edge"])
            dev = float(r["dev"])
            book = (r.get("book") or "").strip()
        except (KeyError, ValueError, IndexError, AssertionError) as exc:
            print(f"skipping unparseable opener row ({exc}): {r}", file=sys.stderr)
            continue

        game_id = f"NFL_{nflverse_id}"
        # Kelly-proportional stake (2026-08-23; was a flat 1u).
        #
        # Flat made sense while the model used one probability for every bet.
        # It no longer does: the card prices each bet by its deviation, and on
        # six seasons those bets are wildly unequal. Measured over 2020-2025 at
        # the deployed gate, sorted by the edge each bet actually carries:
        #
        #   SMALL  (n=726, 89% of picks)  mean edge +1.59pp   ROI  -0.30%
        #   MEDIUM (n= 58)                mean edge +3.73pp   ROI +17.13%
        #   LARGE  (n= 26)                mean edge +11.36pp  ROI +10.23%
        #
        # A flat stake bets the -0.30% bucket as hard as the +17% one. Sizing
        # by each bet's own Kelly fraction against the same reference the wind
        # model uses (so one bankroll covers both) takes the six-season return
        # from +1.28% flat to +5.45% on units staked, while risking 366u where
        # flat risked 810u. Capped at 2 units, floored at zero — a quote whose
        # juice has eaten the edge is staked at nothing rather than 1u.
        #
        # CAVEAT: the tier boundaries were drawn from this same sample, so the
        # +5.45% is partly in-sample. The DIRECTION is not in doubt — bet more
        # when the edge is bigger — but do not treat that figure as validated.
        # Prefer the stake the CARD computed — models/opener_spread.stake_units
        # is the single definition, exactly as wind's card owns its own stake.
        # The recompute below is a fallback for a CSV written before the card
        # carried the column, and it must stay in step with the model.
        if r.get("stake_pct") not in (None, ""):
            kelly_fraction = round(float(r["stake_pct"]) / 100.0, 6)
            if kelly_fraction <= 0:
                continue
        else:
            b_dec = (price / 100.0) if price > 0 else (100.0 / -price)
            kelly_full = max(0.0, (b_dec * model_prob - (1 - model_prob)) / b_dec)
            units = min(kelly_full / OPENER_REF_KELLY * OPENER_STAKE_SCALE,
                        OPENER_MAX_UNITS)
            if units < OPENER_MIN_UNITS:
                continue
            kelly_fraction = round(units * OPENER_UNIT_PCT, 6)
        games.append({
            "game_id": game_id,
            "sport": "NFL",
            "season": season,
            "game_date": game_date,
            "home_team": home,
            "away_team": away,
            "commence_time": commence_iso,
        })
        picks.append({
            "game_id": game_id,
            "model_id": NFL_OPENER_MODEL_ID,
            "sport": "NFL",
            "game_date": game_date,
            "game_time": commence_iso,
            "pick_side": side,
            "pick_label": (
                f"{away} @ {home} — {bet_team} {side_line:+g} "
                f"(Opener {dev:+g} vs Pinnacle, {BOOK_ABBREV.get(book, book or '?')}) "
                f"· {kelly_fraction / OPENER_UNIT_PCT:.2f}u"
            ),
            "model_probability": model_prob,
            "dk_implied_prob": market_prob,
            "edge": edge,
            "dk_odds": price,                 # soft-book price; book in label
            "scored_line": soft_home_line,    # HOME spread — settle convention
            "kelly_fraction": kelly_fraction,
            "recommended_bet": round(kelly_fraction * bankroll, 2),
            "bankroll_at_pick": bankroll,
            "signal_type": "BET",
        })
    return games, picks


def read_card(path: Path) -> list[dict]:
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def snapshot_row_params(r: dict) -> dict | None:
    """
    Pure transform: one line_snapshots CSV row (data_ingest/line_snapshots.py
    in the nfl/ package) -> odds-table insert params. None on a garbage row —
    skipped with a message rather than sinking the whole flush.
    """
    def num(key: str):
        v = r.get(key)
        if v is None:
            return None
        v = v.strip() if isinstance(v, str) else v
        if v == "":
            return None
        return float(v)

    try:
        nflverse_id = r["game_id"].strip()
        market = r["market"].strip()
        snapshot_at = r["snapshot_at"].strip()
        if market not in ("totals", "spreads") or not nflverse_id or not snapshot_at:
            raise ValueError(f"market={market!r} id={nflverse_id!r}")
        return {
            "game_id": f"NFL_{nflverse_id}",
            "market": market,
            "snapshot_at": snapshot_at,
            "home_price": num("home_price"),
            "away_price": num("away_price"),
            "spread_home": num("spread_home"),
            "total_line": num("total_line"),
            "over_price": num("over_price"),
            "under_price": num("under_price"),
        }
    except (KeyError, ValueError, AttributeError) as exc:
        print(f"skipping unparseable snapshot row ({exc}): {r}", file=sys.stderr)
        return None


def publish_board(run_date: str | None = None) -> int:
    """
    Flush the tick's full board CSV into `nfl_odds_history`.

    Every poll tick pays for a whole-sport pull and then keeps only the
    qualifying bets. `publish_line_snapshots` skims DraftKings off it for the
    app's movement chip; this keeps EVERYTHING — all books, all markets — so
    the odds archive keeps growing at zero extra credit cost.

    Deliberately NOT the `odds` table: that one is capped by prune_odds.py,
    which deletes non-DraftKings rows once a game ages out. This is the
    append-only research archive the models and backtests read.

    Idempotent: ON CONFLICT DO NOTHING on (snapshot_at, game_id, bookmaker,
    market). Never raises — an archive write must not sink a bet card.
    """
    if run_date is None:
        run_date = datetime.now(timezone.utc).date().isoformat()
    path = CARDS_DIR / f"board_{run_date}.csv"
    if not path.exists():
        return 0
    try:
        rows = read_card(path)
        if not rows:
            return 0
        from data.db import get_connection
        conn = get_connection()
        written = 0
        try:
            for r in rows:
                away, home = (r.get("away") or "").strip(), (r.get("home") or "").strip()
                if not away or not home:
                    continue
                # Match the nflverse id the rest of the NFL tables use.
                g = conn.execute("""
                    SELECT game_id, season, week FROM games
                    WHERE sport = 'NFL' AND home_team = %s AND away_team = %s
                      AND commence_time IS NOT NULL
                    ORDER BY commence_time DESC LIMIT 1
                """, (home, away)).fetchone()
                if not g:
                    continue          # game not published yet; nothing to hang it on
                conn.execute("""
                    INSERT INTO nfl_odds_history
                        (snapshot_at, game_id, season, week, commence_time,
                         bookmaker, market, point, price_home, price_away)
                    VALUES (%(snapshot_at)s, %(game_id)s, %(season)s, %(week)s,
                            %(commence_time)s, %(bookmaker)s, %(market)s,
                            %(point)s, %(price_home)s, %(price_away)s)
                    ON CONFLICT (snapshot_at, game_id, bookmaker, market) DO NOTHING
                """, {
                    "snapshot_at": r.get("snapshot_at"), "game_id": g[0],
                    "season": g[1], "week": g[2],
                    "commence_time": r.get("commence_time") or None,
                    "bookmaker": r.get("bookmaker"), "market": r.get("market"),
                    "point": _num(r.get("point")),
                    "price_home": _num(r.get("price_home")),
                    "price_away": _num(r.get("price_away")),
                })
                written += 1
            conn.commit()
        finally:
            conn.close()
        print(f"NFL board archive {run_date}: {written} quote(s) into nfl_odds_history")
        return written
    except Exception as exc:                                   # noqa: BLE001
        print(f"WARNING: board archive failed: {exc}", file=sys.stderr)
        return 0


def _num(v):
    try:
        return float(v) if v not in (None, "", "nan") else None
    except (TypeError, ValueError):
        return None


def publish_line_snapshots(run_date: str | None = None) -> int:
    """
    Flush the day's DraftKings line-snapshot CSV (written by the card scripts
    on every LIVE run, zero extra credits) into the odds table, so the app's
    movement chip / Line Movement card work for NFL picks — the "where is the
    market now vs the number this pick locked at" view.

    Rows are only inserted for games that already exist in `games` (i.e. games
    a card has published a pick for — movement history starts at the game's
    first card appearance), and re-flushing the same CSV is a no-op (the
    NOT EXISTS guard on game/market/snapshot_at). bookmaker='draftkings' so
    the existing DK-only mobile readers (v_latest_dk_odds, fetchOddsHistory)
    pick the rows up with no view changes; DK rows are never pruned by
    data/prune_odds.py.
    """
    if run_date is None:
        run_date = datetime.now(timezone.utc).date().isoformat()
    path = CARDS_DIR / f"line_snapshots_{run_date}.csv"
    if not path.exists():
        return 0
    rows = [p for p in (snapshot_row_params(r) for r in read_card(path)) if p]
    if not rows:
        return 0

    from data.db import get_connection

    conn = get_connection()
    try:
        for p in rows:
            conn.execute("""
                INSERT INTO odds (game_id, sport, market, bookmaker, snapshot_type,
                                  snapshot_at, home_price, away_price, spread_home,
                                  total_line, over_price, under_price)
                SELECT %(game_id)s, 'NFL', %(market)s, 'draftkings', 'open',
                       %(snapshot_at)s, %(home_price)s, %(away_price)s,
                       %(spread_home)s, %(total_line)s, %(over_price)s, %(under_price)s
                WHERE EXISTS (SELECT 1 FROM games WHERE game_id = %(game_id)s)
                  AND NOT EXISTS (
                      SELECT 1 FROM odds
                      WHERE game_id = %(game_id)s AND market = %(market)s
                        AND bookmaker = 'draftkings'
                        AND snapshot_at = %(snapshot_at)s
                  )
            """, p)
        conn.commit()
    finally:
        conn.close()

    print(f"NFL line snapshots {run_date}: flushed {len(rows)} row(s) into odds")
    return len(rows)


def _flush_board_safe(run_date):
    try:
        publish_board(run_date)
    except Exception as exc:      # noqa: BLE001
        print(f"WARNING: board archive failed: {exc}", file=sys.stderr)


def _flush_snapshots_safe(run_date: str | None) -> None:
    """Snapshot flush must never fail a publish — picks are the deliverable."""
    try:
        publish_line_snapshots(run_date)
    except Exception as exc:
        print(f"WARNING: line snapshot publish failed: {exc}", file=sys.stderr)


def publish(run_date: str | None = None) -> int:
    """
    Mirror the day's card into games + picks. Returns picks written.

    INSERT-ONCE LOCK: a game with an existing nfl_wind_totals pick is skipped.
    The first qualifying card locks the bet and later cards can only ADD games,
    never re-price or remove one — the bet is down at the locked number.

    A pick whose wind later drops below threshold does NOT leave the board. It
    is flagged by scripts/nfl_pick_monitor.py (condition_status GONE) and its
    whole post-lock history is kept in nfl_pick_status_history.
    """
    from data.db import get_connection

    if run_date is None:
        run_date = datetime.now(timezone.utc).date().isoformat()

    card_path = CARDS_DIR / f"wind_card_{run_date}.csv"
    card_rows = read_card(card_path) if card_path.exists() else []
    game_rows, pick_rows = build_rows(card_rows, config.BANKROLL)

    now_iso = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        for g in game_rows:
            conn.execute("""
                INSERT INTO games (game_id, sport, season, game_date,
                                   home_team, away_team, commence_time, data_source)
                VALUES (%(game_id)s, %(sport)s, %(season)s, %(game_date)s,
                        %(home_team)s, %(away_team)s, %(commence_time)s, 'nfl_wind_card')
                ON CONFLICT (game_id) DO UPDATE
                SET commence_time = EXCLUDED.commence_time,
                    game_date     = EXCLUDED.game_date
            """, g)

        # INSERT-ONCE LOCK (changed 2026-08-22; was delete-and-replace).
        #
        # A game with ANY existing nfl_wind_totals pick is skipped: the first
        # qualifying card locks that bet at that total, that price and that
        # book, forever. The bet is placed the moment it fires — nothing later
        # can retract it, so the board must not pretend otherwise.
        #
        # This is a deliberate departure from the wind rule's own runbook,
        # which says later is better because forecast skill improves. That
        # reasoning is about WHEN TO FIRE, and firing early is now the chosen
        # trade (see the lead-decay table: ~0.41pp of win rate per day). Once
        # fired, the bet is real. A forecast that later collapses is recorded
        # by scripts/nfl_pick_monitor.py as condition_status='GONE' and shown
        # loudly, instead of the pick vanishing as though it never happened.
        locked = {
            r[0] for r in conn.execute("""
                SELECT DISTINCT game_id FROM picks WHERE model_id = %s
            """, (NFL_WIND_MODEL_ID,)).fetchall()
        }
        skipped = [p for p in pick_rows if p["game_id"] in locked]
        pick_rows = [p for p in pick_rows if p["game_id"] not in locked]
        if skipped:
            print(f"  {len(skipped)} game(s) already locked — not re-priced: "
                  + ", ".join(sorted({p["game_id"] for p in skipped})))

        for p in pick_rows:
            conn.execute("""
                INSERT INTO picks (game_id, model_id, sport, game_date, game_time,
                                   pick_side, pick_label, model_probability,
                                   dk_implied_prob, edge, dk_odds, scored_line,
                                   kelly_fraction, recommended_bet, bankroll_at_pick,
                                   signal_type)
                VALUES (%(game_id)s, %(model_id)s, %(sport)s, %(game_date)s,
                        %(game_time)s, %(pick_side)s, %(pick_label)s,
                        %(model_probability)s, %(dk_implied_prob)s, %(edge)s,
                        %(dk_odds)s, %(scored_line)s, %(kelly_fraction)s,
                        %(recommended_bet)s, %(bankroll_at_pick)s, %(signal_type)s)
            """, p)
        conn.commit()
    finally:
        conn.close()

    print(f"NFL wind publish {run_date}: {len(pick_rows)} pick(s) "
          f"from {card_path.name if card_path.exists() else 'no card (zero qualifying bets)'}")
    # After the games rows exist, flush the run's DK line snapshots so a
    # newly-published game gets its first snapshot the same run.
    _flush_snapshots_safe(run_date)
    _flush_board_safe(run_date)
    return len(pick_rows)


def publish_opener(run_date: str | None = None) -> int:
    """
    Mirror the day's opener card into games + picks. Returns picks written.

    INSERT-ONCE LOCK: a game with ANY existing nfl_opener_spread pick is
    skipped — the first qualifying card locks the bet forever (the edge is the
    stale number; re-pricing on a later card would trade it away). No-card
    days do nothing: opener picks are never cleared.
    """
    from data.db import get_connection

    if run_date is None:
        run_date = datetime.now(timezone.utc).date().isoformat()

    card_path = CARDS_DIR / f"opener_card_{run_date}.csv"
    if not card_path.exists():
        # Most days have no NEW opener bets, but the card script still dumped
        # DK spreads for every upcoming game — flush them so already-locked
        # opener picks keep accruing movement history through game day.
        print(f"NFL opener publish {run_date}: no card — nothing to do")
        _flush_snapshots_safe(run_date)
        return 0
    game_rows, pick_rows = build_opener_rows(read_card(card_path), config.BANKROLL)

    conn = get_connection()
    written = 0
    try:
        for g in game_rows:
            conn.execute("""
                INSERT INTO games (game_id, sport, season, game_date,
                                   home_team, away_team, commence_time, data_source)
                VALUES (%(game_id)s, %(sport)s, %(season)s, %(game_date)s,
                        %(home_team)s, %(away_team)s, %(commence_time)s, 'nfl_opener_card')
                ON CONFLICT (game_id) DO UPDATE
                SET commence_time = EXCLUDED.commence_time,
                    game_date     = EXCLUDED.game_date
            """, g)

        for p in pick_rows:
            existing = conn.execute("""
                SELECT 1 FROM picks WHERE game_id = %s AND model_id = %s LIMIT 1
            """, (p["game_id"], p["model_id"])).fetchone()
            if existing:
                continue  # locked at its first qualifying card
            conn.execute("""
                INSERT INTO picks (game_id, model_id, sport, game_date, game_time,
                                   pick_side, pick_label, model_probability,
                                   dk_implied_prob, edge, dk_odds, scored_line,
                                   kelly_fraction, recommended_bet, bankroll_at_pick,
                                   signal_type)
                VALUES (%(game_id)s, %(model_id)s, %(sport)s, %(game_date)s,
                        %(game_time)s, %(pick_side)s, %(pick_label)s,
                        %(model_probability)s, %(dk_implied_prob)s, %(edge)s,
                        %(dk_odds)s, %(scored_line)s, %(kelly_fraction)s,
                        %(recommended_bet)s, %(bankroll_at_pick)s, %(signal_type)s)
            """, p)
            written += 1
        conn.commit()
    finally:
        conn.close()

    print(f"NFL opener publish {run_date}: {written} new pick(s) locked, "
          f"{len(pick_rows) - written} already locked")
    _flush_snapshots_safe(run_date)
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="card date (UTC, YYYY-MM-DD); default today")
    ap.add_argument("--opener", action="store_true",
                    help="publish the opener-spread card instead of the wind card")
    ap.add_argument("--snapshots", action="store_true",
                    help="flush the day's DK line snapshots only (no pick publishing)")
    args = ap.parse_args()
    if args.snapshots:
        publish_line_snapshots(args.date)
    elif args.opener:
        publish_opener(args.date)
    else:
        publish(args.date)
