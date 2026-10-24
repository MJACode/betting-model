"""
Publish the NFL wind-totals card into the platform's picks table.

The nfl/ package is standalone by design (docs/sports/nfl.md) — its weekly
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
  book is `decision_book` (the feed key), with `decision_odds` equal to that
  same price, so the label does not have to carry it. Rows already stored
  still name the book inside the old parenthetical; readers keep parsing that.
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
import io
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from models.honest_ev import gate

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


def _opener_model():
    """The nfl/ opener model, loaded by path.

    `from models.opener_spread import ...` would resolve to the platform's own
    top-level `models` package from here (nfl/_nfl_models.py explains), so the
    file is loaded by absolute path, once, the way the tests and the card do.
    """
    import importlib.util
    name = "nfl_model_opener_spread"
    if name in sys.modules:
        return sys.modules[name]
    path = Path(__file__).resolve().parent.parent / "nfl" / "models" / "opener_spread.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

_ET = ZoneInfo("America/New_York")

# Short labels for the best-price book. Kept so an old parenthetical still
# maps ("FD" → fanduel) in the readers. New rows store the feed key in
# decision_book and do not write the abbreviation into pick_label.
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


def _taken_at(book: str, price: float, implied: float, edge: float) -> dict:
    """The sportsbook the quoted price was taken at, on the row.

    `decision_odds` is the same number stored in `dk_odds`. Stake, the
    action cut and the grade all read COALESCE(decision_odds, dk_odds), so
    copying the price does not move them. The key is the feed's book key
    (`fanduel`), not the old parenthetical abbreviation (`FD`). A blank
    book leaves the columns null; readers then fall back to the label,
    which is how every row written before this still names its book.
    """
    key = (book or "").strip().lower()
    if not key:
        return {
            "decision_book": None,
            "decision_odds": None,
            "decision_implied_prob": None,
            "decision_edge": None,
        }
    return {
        "decision_book": key,
        "decision_odds": price,
        "decision_implied_prob": implied,
        "decision_edge": edge,
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
            # A non-numeric forecast still skips the row. The mph stays off
            # the label (Matt, 2026-10-23).
            float(r["forecast_wind"])
            book = (r.get("book") or "").strip()
        except (KeyError, ValueError, IndexError) as exc:
            print(f"skipping unparseable card row ({exc}): {r}", file=sys.stderr)
            continue

        game_id = f"NFL_{nflverse_id}"
        # THE GLOBAL EV FLOOR on the honest probability at the bet price
        # (2026-09-19). The card has no decision function -- its row IS the
        # bet -- so the platform gate is applied here, before the row.
        ev = gate(NFL_WIND_MODEL_ID, model_prob, price)
        if not ev.clears:
            print(f"{NFL_WIND_MODEL_ID}: {ev.reason} — dropped {game_id}",
                  file=sys.stderr)
            continue
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
                f"· {stake_pct:.2f}u"
            ),
            "model_probability": model_prob,
            "model_probability_cal": round(ev.cal_prob, 4),
            "dk_implied_prob": market_prob,   # de-vigged best-book prob
            "edge": edge,
            "dk_odds": price,                 # best-book price; book in decision_book
            **_taken_at(book, price, market_prob, edge),
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
            # A non-numeric deviation still skips the row. The opener gap
            # and the Pinnacle comparison stay off the label (Matt, 2026-10-23).
            float(r["dev"])
            book = (r.get("book") or "").strip()
            held_raw = r.get("held_min")
            held_min = (None if held_raw in (None, "", "nan")
                        else float(held_raw))
        except (KeyError, ValueError, IndexError, AssertionError) as exc:
            print(f"skipping unparseable opener row ({exc}): {r}", file=sys.stderr)
            continue
        # The age of the soft book's number, on the pick itself (mike,
        # 2026-09-22: a fresh number is a possible book error -- move fast and
        # record whether it was placeable -- not a reason to skip). One
        # formatter, the model's, so the card, the audit trail and the label
        # agree. A card written before the column existed carries no tag.
        age = "" if "held_min" not in r else f" · {_opener_model().age_tag(held_min)}"

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
        # THE GLOBAL EV FLOOR on the honest probability at the bet price
        # (2026-09-19), same gate as the wind rows above.
        ev = gate(NFL_OPENER_MODEL_ID, model_prob, price)
        if not ev.clears:
            print(f"{NFL_OPENER_MODEL_ID}: {ev.reason} — dropped {game_id}",
                  file=sys.stderr)
            continue
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
                f"· {kelly_fraction / OPENER_UNIT_PCT:.2f}u{age}"
            ),
            "model_probability": model_prob,
            "model_probability_cal": round(ev.cal_prob, 4),
            "dk_implied_prob": market_prob,
            "edge": edge,
            "dk_odds": price,                 # soft-book price; book in decision_book
            **_taken_at(book, price, market_prob, edge),
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


BOARD_CHUNK = 5000            # rows per batch; each batch commits and moves the marker
BOARD_FLUSH_BUDGET_S = 120    # no new batch starts after this; the poll runs every 10 min


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

    INCREMENTAL AND BATCHED (2026-10-11). Since the opener went to a one-minute
    poll (2026-09-22) it appends the whole board here every minute, ~560 rows a
    minute on an NFL Sunday. This flush re-read the WHOLE day on every wind
    tick, with two round trips per row inside one transaction, so each run took
    longer than the last: 18, 27, 48, 71, 105, 151 and 232 minutes on
    2026-10-11. The fast NFL poll allows one run at a time, so the run that
    started at 12:20Z held it for ~5.7 hours and the wind model re-checked that
    Sunday's games twice before kickoff. Now the marker beside the CSV holds how
    many rows are already in, each matchup is looked up once, rows go in
    batches that each commit and advance the marker, and no new batch starts
    after BOARD_FLUSH_BUDGET_S, so the rest waits for the next tick instead of
    holding the poll. A lost marker (redeploy) costs one re-flush, which the
    ON CONFLICT makes harmless.
    """
    if run_date is None:
        run_date = datetime.now(timezone.utc).date().isoformat()
    path = CARDS_DIR / f"board_{run_date}.csv"
    if not path.exists():
        return 0
    try:
        marker = path.with_suffix(".flushed")
        try:
            done = int(marker.read_text(encoding="utf-8").strip() or 0)
        except (OSError, ValueError):
            done = 0
        # The opener may be appending while this reads. Fix the end FIRST -- the
        # last newline in the file as it stands now -- and read only up to it,
        # so a half-written row waits for the next tick instead of going in
        # past the marker, half-written for good.
        with open(path, "rb") as fh:
            data = fh.read()
        data = data[:data.rfind(b"\n") + 1]
        # Count past the rows already in rather than keeping the whole day
        # (~800k rows by midnight on an NFL Sunday) as dicts.
        total, pending = 0, []
        for total, r in enumerate(
                csv.DictReader(io.StringIO(data.decode("utf-8"), newline="")), 1):
            if total > done:
                pending.append(r)
        if done > total:                  # a rewritten file: start over
            done = 0
            pending = list(csv.DictReader(io.StringIO(data.decode("utf-8"), newline="")))
        if not pending:
            return 0

        def matchup(r):
            return ((r.get("home") or "").strip(), (r.get("away") or "").strip())

        from data.db import get_connection
        conn = get_connection()
        written, started = 0, time.monotonic()
        try:
            # Match the nflverse id the rest of the NFL tables use, once per
            # matchup rather than once per quote.
            games: dict = {}
            for key in {matchup(r) for r in pending}:
                if all(key):
                    games[key] = conn.execute("""
                        SELECT game_id, season, week FROM games
                        WHERE sport = 'NFL' AND home_team = %s AND away_team = %s
                          AND commence_time IS NOT NULL
                        ORDER BY commence_time DESC LIMIT 1
                    """, key).fetchone()
            for start in range(0, len(pending), BOARD_CHUNK):
                if start and time.monotonic() - started > BOARD_FLUSH_BUDGET_S:
                    break                 # the rest goes next tick, from the marker
                chunk = pending[start:start + BOARD_CHUNK]
                params = []
                for r in chunk:
                    g = games.get(matchup(r))
                    if not g:
                        continue          # game not published yet; nothing to hang it on
                    params.append({
                        "snapshot_at": r.get("snapshot_at"), "game_id": g[0],
                        "season": g[1], "week": g[2],
                        "commence_time": r.get("commence_time") or None,
                        "bookmaker": r.get("bookmaker"), "market": r.get("market"),
                        "point": _num(r.get("point")),
                        "price_home": _num(r.get("price_home")),
                        "price_away": _num(r.get("price_away")),
                    })
                conn.executemany("""
                    INSERT INTO nfl_odds_history
                        (snapshot_at, game_id, season, week, commence_time,
                         bookmaker, market, point, price_home, price_away)
                    VALUES (%(snapshot_at)s, %(game_id)s, %(season)s, %(week)s,
                            %(commence_time)s, %(bookmaker)s, %(market)s,
                            %(point)s, %(price_home)s, %(price_away)s)
                    ON CONFLICT (snapshot_at, game_id, bookmaker, market) DO NOTHING
                """, params)
                conn.commit()
                written += len(params)
                done += len(chunk)
                try:
                    marker.write_text(str(done), encoding="utf-8")
                except OSError as exc:
                    print(f"WARNING: could not write {marker}: {exc}", file=sys.stderr)
        finally:
            conn.close()
        left = total - done
        print(f"NFL board archive {run_date}: {written} quote(s) into nfl_odds_history"
              + (f", {left} row(s) left for the next tick" if left else ""))
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
    # INCREMENTAL (2026-09-22). The CSV is appended on every tick and this
    # flush re-read and re-inserted the WHOLE day every time it ran -- 3,024
    # rows at 21:30Z, each a round trip guarded by NOT EXISTS -- so the
    # opener's publish step took 75 s on a job scheduled every minute, and
    # the scheduler skipped every other tick ("maximum number of running
    # instances reached"). A one-minute poll that runs every two minutes is
    # what put the Discord post 75 s behind a number that lived four minutes.
    # The marker beside the CSV holds how many rows have already been flushed;
    # only the rows after it go to the database. The NOT EXISTS guard stays,
    # so a lost marker (redeploy) costs one full re-flush and nothing else.
    all_rows = read_card(path)
    marker = path.with_suffix(".flushed")
    try:
        done = int(marker.read_text(encoding="utf-8").strip() or 0)
    except (OSError, ValueError):
        done = 0
    if done > len(all_rows):          # a rewritten file: start over
        done = 0
    rows = [p for p in (snapshot_row_params(r) for r in all_rows[done:]) if p]
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
    try:
        marker.write_text(str(len(all_rows)), encoding="utf-8")
    except OSError as exc:
        print(f"WARNING: could not write {marker}: {exc}", file=sys.stderr)

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


def _clear_scored_row(conn, game_id: str, model_id: str) -> int:
    """Drop the unsettled NONE row a BET is about to replace.

    THE ONLY DELETE the NFL publishers are allowed, and it sits ABOVE the
    two BET writers on purpose. scripts/nfl_preflight.py (THE LOCK) slices
    this file per writer and requires every delete of a pick, here or in a
    writer, to be guarded by signal_type = 'NONE' AND result IS NULL. With
    the helper below the wind writer it landed inside the opener's slice and
    failed the insert-once check (Reviewer, #838 post-merge).

    Returns the rows actually deleted (0 when there was no NONE row).
    """
    cur = conn.execute("""
        DELETE FROM picks
        WHERE game_id = %s AND model_id = %s
          AND signal_type = 'NONE' AND result IS NULL
    """, (game_id, model_id))
    return getattr(cur, "rowcount", 0) or 0


# Namespace for the per-model publish lock. Any process writing NFL game-rule
# rows for a model (the BET writers and publish_scored) takes the SAME key,
# derived here and nowhere else, so a scored-rows pass and an opener/wind
# publish for one model can never interleave their read-then-write.
_PICKS_LOCK_NS = "nfl_game_rule_picks:"

# How long a writer waits for another's pass before giving up. The passes hold
# the lock for a few statements; a wait this long means something is stuck,
# and the pass fails (nothing committed, the next tick retries) rather than
# queueing behind it.
_PICKS_LOCK_TIMEOUT = "5s"


def _model_lock_key(model_id: str) -> int:
    """Stable signed 32-bit key for `model_id` (crc32; not Python's hash())."""
    import zlib
    k = zlib.crc32((_PICKS_LOCK_NS + model_id).encode("utf-8")) & 0xFFFFFFFF
    return k - (1 << 32) if k >= (1 << 31) else k


def _lock_model(conn, model_id: str) -> None:
    """Hold the model's publish lock until this transaction ends.

    pg_advisory_xact_lock, not the session form: the worker talks to the
    TRANSACTION pooler (data/db.get_connection), where only a
    transaction-scoped lock is guaranteed to stay on one backend. It blocks
    rather than skips -- both writers must run, just not interleaved.

    The race it closes (Reviewer, #838 post-merge): publish_scored read the
    BET set, an opener BET committed, then the scored writer inserted a NONE
    row. A home BET made that insert hit uq_picks_one_row_per_pick and roll
    back the whole scored pass; an away BET left a permanent NONE row beside
    the BET.

    lock_timeout bounds the wait. A timeout (SQLSTATE 55P03) aborts the
    transaction, so the pass raises with nothing written. data/db treats the
    lock as a write, so a connection lost after it raises ConnectionLost
    instead of re-running the pass on a new, unlocked backend.
    """
    conn.execute(f"SET LOCAL lock_timeout = '{_PICKS_LOCK_TIMEOUT}'")
    try:
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_model_lock_key(model_id),))
    except Exception as exc:                                   # noqa: BLE001
        if getattr(exc, "pgcode", None) == "55P03":            # lock_not_available
            raise RuntimeError(
                f"NFL publish lock for {model_id} not acquired within "
                f"{_PICKS_LOCK_TIMEOUT}; pass aborted, nothing written") from exc
        raise


def _fmt_spread(line: float) -> str:
    """-3.0 -> '-3', 6.5 -> '+6.5', 0 -> 'PK' (the app's pick'em convention,
    mobile/src/lib/teamDetail.ts; tracking/pick_integrity accepts it)."""
    return "PK" if float(line) == 0 else f"{line:+g}"


# ── The schedule gate (mike, 2026-10-20) ─────────────────────────────────────
#
# "The repo/models should look ahead schedules for all markets and sports and
# models." The opener fires from 10 days out and NFL games are 7 days apart, so
# a Thursday game can be decided before both teams' Sunday games: at
# 2026-10-20 20:00Z the opener evaluated CAR @ GB (10-29) while both teams
# still had to play on 10-25. Neither rule reads a team log, but the rule
# stands for every pre-game model: no decision while either team has an
# earlier game not played, being played, or without its result in `games`
# (data/schedule_context; nflverse fills the score, measured 4.2-20.5h after a
# Sunday kickoff in 2026 weeks 1-6).
#
# A held game's BET is not written. Its number is written as NONE with the
# reason, by publish_scored, so the board still shows it; NONE never locks, so
# the first tick after the games are scored decides it. Read from the
# DATABASE schedule (nflverse, daily), never the frozen nfl/data/games.csv.

def _schedule_holds(conn, games: dict[str, dict],
                    now: datetime | None = None) -> dict[str, str]:
    """{game_id: reason} for the games a pre-game NFL rule may not decide yet.

    `games` maps game_id -> {home_team, away_team, game_date, commence_time}.
    Fails CLOSED: a schedule that cannot be read holds every game this pass
    (the read runs before anything is written, so the rollback loses
    nothing)."""
    if not games:
        return {}
    from data.schedule_context import SCHEDULE_UNREADABLE, ScheduleBook
    now = now or datetime.now(timezone.utc)
    try:
        book = ScheduleBook.load(conn, "NFL", [(gid, g["game_date"])
                                                for gid, g in games.items()])
        out = {}
        for gid, g in games.items():
            why = book.pending_reason(gid, g["game_date"], g["home_team"],
                                      g["away_team"], g.get("commence_time"), now)
            if why:
                out[gid] = why
        return out
    except Exception as exc:                                   # noqa: BLE001
        print(f"WARNING: NFL schedule check failed ({exc!r}); holding "
              f"{len(games)} game(s) this pass", file=sys.stderr)
        try:
            conn.rollback()
        except Exception:                                      # noqa: BLE001
            pass
        return {gid: SCHEDULE_UNREADABLE for gid in games}


def _held_out(pick_rows: list[dict], holds: dict[str, str], label: str) -> list[dict]:
    """The pick rows still to write, after printing every held one."""
    for p in pick_rows:
        if p["game_id"] in holds:
            print(f"  {label} {p['game_id']}: not decided -- {holds[p['game_id']]}")
    return [p for p in pick_rows if p["game_id"] not in holds]


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
        # Before any write: a failed read rolls back nothing (_schedule_holds).
        holds = _schedule_holds(conn, {g["game_id"]: g for g in game_rows})
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
        #
        # BET rows only (2026-09-26). The same table now holds a NONE row per
        # evaluated game (publish_scored), and a NONE row is the model saying
        # "not yet" -- it must never lock a game out of the bet that fires
        # later. The NONE row is cleared as the BET lands (_clear_scored_row).
        # Serialise against publish_scored for this model before reading the
        # lock set (see _lock_model).
        _lock_model(conn, NFL_WIND_MODEL_ID)
        locked = {
            r[0] for r in conn.execute("""
                SELECT DISTINCT game_id FROM picks
                WHERE model_id = %s AND signal_type = 'BET'
            """, (NFL_WIND_MODEL_ID,)).fetchall()
        }
        skipped = [p for p in pick_rows if p["game_id"] in locked]
        pick_rows = [p for p in pick_rows if p["game_id"] not in locked]
        if skipped:
            print(f"  {len(skipped)} game(s) already locked — not re-priced: "
                  + ", ".join(sorted({p["game_id"] for p in skipped})))
        # A team's earlier game still to be played or scored: no BET yet.
        pick_rows = _held_out(pick_rows, holds, "wind")

        for p in pick_rows:
            _clear_scored_row(conn, p["game_id"], p["model_id"])
            conn.execute("""
                INSERT INTO picks (game_id, model_id, sport, game_date, game_time,
                                   pick_side, pick_label, model_probability,
                                   dk_implied_prob, edge, dk_odds, scored_line,
                                   kelly_fraction, recommended_bet, bankroll_at_pick,
                                   signal_type, model_probability_cal,
                                   decision_book, decision_odds,
                                   decision_implied_prob, decision_edge)
                VALUES (%(game_id)s, %(model_id)s, %(sport)s, %(game_date)s,
                        %(game_time)s, %(pick_side)s, %(pick_label)s,
                        %(model_probability)s, %(dk_implied_prob)s, %(edge)s,
                        %(dk_odds)s, %(scored_line)s, %(kelly_fraction)s,
                        %(recommended_bet)s, %(bankroll_at_pick)s, %(signal_type)s,
                        %(model_probability_cal)s, %(decision_book)s,
                        %(decision_odds)s, %(decision_implied_prob)s,
                        %(decision_edge)s)
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
        # Before any write: a failed read rolls back nothing (_schedule_holds).
        holds = _schedule_holds(conn, {g["game_id"]: g for g in game_rows})
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

        # A team's earlier game still to be played or scored: no BET yet. The
        # first qualifying tick AFTER that is the one that locks.
        pick_rows = _held_out(pick_rows, holds, "opener")

        # Serialise against publish_scored before the insert-once reads.
        _lock_model(conn, NFL_OPENER_MODEL_ID)
        for p in pick_rows:
            # BET rows only: a NONE row (publish_scored) is not a lock.
            existing = conn.execute("""
                SELECT 1 FROM picks
                WHERE game_id = %s AND model_id = %s AND signal_type = 'BET'
                LIMIT 1
            """, (p["game_id"], p["model_id"])).fetchone()
            if existing:
                continue  # locked at its first qualifying card
            _clear_scored_row(conn, p["game_id"], p["model_id"])
            conn.execute("""
                INSERT INTO picks (game_id, model_id, sport, game_date, game_time,
                                   pick_side, pick_label, model_probability,
                                   dk_implied_prob, edge, dk_odds, scored_line,
                                   kelly_fraction, recommended_bet, bankroll_at_pick,
                                   signal_type, model_probability_cal,
                                   decision_book, decision_odds,
                                   decision_implied_prob, decision_edge)
                VALUES (%(game_id)s, %(model_id)s, %(sport)s, %(game_date)s,
                        %(game_time)s, %(pick_side)s, %(pick_label)s,
                        %(model_probability)s, %(dk_implied_prob)s, %(edge)s,
                        %(dk_odds)s, %(scored_line)s, %(kelly_fraction)s,
                        %(recommended_bet)s, %(bankroll_at_pick)s, %(signal_type)s,
                        %(model_probability_cal)s, %(decision_book)s,
                        %(decision_odds)s, %(decision_implied_prob)s,
                        %(decision_edge)s)
            """, p)
            written += 1
        conn.commit()
    finally:
        conn.close()

    print(f"NFL opener publish {run_date}: {written} new pick(s) locked, "
          f"{len(pick_rows) - written} already locked")
    _flush_snapshots_safe(run_date)
    return written


# ── NONE rows: every game the two rules evaluated ───────────────────────────
#
# Matt, 2026-09-26: "There are only 7 bets showing under NFL. All bet lines
# should be showing on the today tab." The two NFL game rules only ever wrote
# BET rows, so a 14-game Sunday read as 7 cards on Today -- the rest of the
# slate had been evaluated (every tick dumps the model's view of every game to
# pick_eval_<date>.csv) and never reached `picks`. NCAAF has written a NONE row
# per scored game all along; this is the NFL half of the same shape.
#
# What a NONE row here is, and is not:
#   * NOT a pick. Discord, push, opening signals and every record query read
#     `signal_type = 'BET'`; none of them see these rows.
#   * NOT a lock. Both BET locks above are keyed on signal_type = 'BET', and a
#     BET that lands clears the game's NONE row first (_clear_scored_row) --
#     the dead-zone NONE on an unstarted game is the one row the pick rule
#     allows to go (.claude/rules/picks-and-publishing.md, corollaries).
#   * REFRESHED IN PLACE until kickoff, then frozen: the last pre-game view is
#     what the evaluation rule (CLAUDE.md §7) grades. Updated only when a
#     number or the reason changed, so the audit log sees changes, not ticks.
#   * NEVER PRICELESS. A game with no quote gets no row: profit_flat fabricates
#     -110 for a NULL price (CLAUDE.md §6).
#
# The numbers are the model's where it has them. Where it does not -- wind
# below threshold, an opener deviation too small to price -- the rule has no
# opinion, so the row says exactly that: model probability = the market's,
# edge 0. The opener's row is always the HOME side at the HOME price; the rule
# takes no side until a deviation fires. The model's own words go in
# `downgrade_reason`.

SCORED_MODEL_IDS = (NFL_WIND_MODEL_ID, NFL_OPENER_MODEL_ID)


def _american_to_prob(px: float) -> float:
    return 100.0 / (px + 100.0) if px > 0 else -px / (-px + 100.0)


def latest_eval_rows(rows: list[dict]) -> dict[tuple[str, str], dict]:
    """Newest observation per (game_id, model_id); ISO timestamps sort as text."""
    out: dict[tuple[str, str], dict] = {}
    for r in rows:
        key = ((r.get("game_id") or "").strip(), (r.get("model_id") or "").strip())
        if not all(key) or key[1] not in SCORED_MODEL_IDS:
            continue
        if key not in out or (r.get("observed_at") or "") >= (out[key].get("observed_at") or ""):
            out[key] = r
    return out


def build_scored_rows(latest: dict[tuple[str, str], dict],
                      games: dict[str, dict], bankroll: float,
                      holds: dict[str, str] | None = None) -> list[dict]:
    """
    Pure transform: newest eval row per (game, model) -> NONE pick rows.

    `games` maps game_id -> {home_team, away_team, game_date, commence_time}.
    A game the platform does not know (FK), or a row with no line or price,
    is skipped: a NONE row is only worth writing if it carries a real quote.

    `holds` maps game_id -> the schedule gate's reason (_schedule_holds). A
    held game's row carries that reason, and is written even when the model
    fired: the BET writers write no BET for it, so this row is the board's
    only view of the game until the earlier games are scored.
    """
    holds = holds or {}
    out: list[dict] = []
    for (game_id, model_id), r in sorted(latest.items()):
        held = holds.get(game_id)
        # The model FIRED on this tick. Its BET row is the publisher's to
        # write (publish / publish_opener); a pass row carrying the firing
        # edge would be a bet dressed as a pass. Write nothing and let the
        # BET land (Reviewer, #838 post-merge) -- unless the game is held,
        # in which case no BET will land this tick.
        if str(r.get("qualifies") or "").strip() == "1" and not held:
            continue
        g = games.get(game_id)
        line, price = _num(r.get("current_line")), _num(r.get("current_price"))
        if g is None or line is None or price is None or price == 0:
            continue
        book = (r.get("current_book") or "").strip()
        # The quote's book is decision_book (the feed key). The label is the
        # bet only. Rows already stored still name the book in "(no bet, FD)".
        home, away = g["home_team"], g["away_team"]
        market = _american_to_prob(price)
        m_prob, m_edge = _num(r.get("model_prob")), _num(r.get("edge"))
        if model_id == NFL_WIND_MODEL_ID:
            side = "under"
            label = f"{away} @ {home} Under {_fmt_line(line)}"
            if m_prob is not None and m_edge is not None:
                # The card de-vigs; its edge is against that market number.
                model_prob, implied, edge = m_prob, m_prob - m_edge, m_edge
            else:
                model_prob, implied, edge = market, market, 0.0
        else:
            side = "home"
            label = f"{away} @ {home} — {home} {_fmt_spread(line)}"
            model_prob, implied, edge = market, market, 0.0
        stored_prob = round(model_prob, 4)
        stored_implied = round(implied, 4)
        stored_edge = round(edge, 4)
        out.append({
            "game_id": game_id,
            "model_id": model_id,
            "sport": "NFL",
            "game_date": g["game_date"],
            "game_time": g["commence_time"],
            "pick_side": side,
            "pick_label": label,
            "model_probability": stored_prob,
            "dk_implied_prob": stored_implied,
            "edge": stored_edge,
            "dk_odds": price,
            **_taken_at(book, price, stored_implied, stored_edge),
            "scored_line": line,          # total (wind) / HOME spread (opener)
            "kelly_fraction": 0.0,
            "recommended_bet": 0.0,
            "bankroll_at_pick": bankroll,
            "signal_type": "NONE",
            "downgrade_reason": (held or r.get("reason") or "")[:500] or None,
        })
    return out


# game_date / game_time are compared too: a flexed kickoff changes nothing
# else on the row, and must still be refreshed (Reviewer, #838 post-merge).
_SCORED_FIELDS = ("pick_label", "pick_side", "model_probability",
                  "dk_implied_prob", "edge", "dk_odds", "scored_line",
                  "downgrade_reason", "game_date", "game_time",
                  "decision_book", "decision_odds",
                  "decision_implied_prob", "decision_edge")


def _field_moved(existing: dict, new: dict, key: str) -> bool:
    a, b = existing.get(key), new.get(key)
    if isinstance(a, (int, float)) or isinstance(b, (int, float)):
        try:
            return a is None or b is None or abs(float(a) - float(b)) > 1e-9
        except (TypeError, ValueError):
            return True
    return (a or None) != (b or None)


def _changed(existing: dict, new: dict) -> bool:
    return any(_field_moved(existing, new, k) for k in _SCORED_FIELDS)


# The observed number. A book stamp or a label edit is not one of these,
# so it does not move created_at.
_NUMBER_FIELDS = ("pick_side", "model_probability", "edge", "dk_odds",
                  "scored_line")


def _number_moved(existing: dict, new: dict) -> bool:
    return any(_field_moved(existing, new, k) for k in _NUMBER_FIELDS)


def publish_scored(run_date: str | None = None) -> int:
    """
    Write / refresh one NONE row per (game, model) the two rules evaluated.
    Returns rows inserted + updated. Never touches a BET, never touches a
    started game.
    """
    from data.db import get_connection

    if run_date is None:
        run_date = datetime.now(timezone.utc).date().isoformat()
    path = CARDS_DIR / f"pick_eval_{run_date}.csv"
    if not path.exists():
        print(f"NFL scored rows {run_date}: no evaluation dump — nothing to do")
        return 0
    latest = latest_eval_rows(read_card(path))
    if not latest:
        return 0

    now = datetime.now(timezone.utc)
    conn = get_connection()
    inserted = updated = 0
    try:
        ids = sorted({gid for gid, _ in latest})
        games: dict[str, dict] = {}
        for gid, home, away, gdate, kick in conn.execute("""
            SELECT game_id, home_team, away_team, game_date::text, commence_time::text
            FROM games WHERE sport = 'NFL' AND game_id = ANY(%s)
        """, (ids,)).fetchall():
            if not kick:
                continue
            try:
                kick_dt = datetime.fromisoformat(str(kick).replace(" ", "T"))
            except ValueError:
                continue
            if kick_dt.tzinfo is None:        # stored naive = UTC, as kick_fields writes
                kick_dt = kick_dt.replace(tzinfo=timezone.utc)
            started = kick_dt <= now
            if started:
                continue            # frozen at its last pre-game view
            games[gid] = {"home_team": home, "away_team": away,
                          "game_date": gdate, "commence_time": kick}
        # The same schedule answer the BET writers act on, read before any
        # write (_schedule_holds).
        holds = _schedule_holds(conn, games, now)

        # Same per-model lock the BET writers take, in a fixed order (no
        # deadlock), BEFORE the BET set is read: an opener/wind BET can no
        # longer commit between that read and the NONE insert below. Every
        # scored model, not just the ones in this dump: the cleanup below
        # deletes for any model the picks read returns.
        for mid in sorted(SCORED_MODEL_IDS):
            _lock_model(conn, mid)

        existing: dict[tuple[str, str], dict] = {}
        bet: set[tuple[str, str]] = set()
        for row in conn.execute("""
            SELECT pick_id, game_id, model_id, signal_type, pick_label, pick_side,
                   model_probability, dk_implied_prob, edge, dk_odds,
                   scored_line, downgrade_reason, game_date::text, game_time,
                   decision_book, decision_odds, decision_implied_prob,
                   decision_edge
            FROM picks
            WHERE model_id = ANY(%s) AND game_id = ANY(%s)
        """, (list(SCORED_MODEL_IDS), ids)).fetchall():
            key = (row[1], row[2])
            if row[3] == "BET":
                bet.add(key)
            elif row[3] == "NONE":
                existing[key] = dict(zip(
                    ("pick_id", "game_id", "model_id", "signal_type") + _SCORED_FIELDS,
                    row))

        # A NONE row left beside a BET (the pre-lock race, or any older
        # leftover) is cleared here: the pick of record stands alone. Same
        # delete, same guard, as a landing BET uses -- and unstarted games
        # only (`games` holds no started game), like every write here.
        cleared = 0
        for key in sorted(bet):
            if key in existing and key[0] in games:
                cleared += _clear_scored_row(conn, *key)

        for p in build_scored_rows(latest, games, config.BANKROLL, holds):
            key = (p["game_id"], p["model_id"])
            if key in bet:
                continue            # the pick of record stands; no NONE beside it
            old = existing.get(key)
            if old is None:
                conn.execute("""
                    INSERT INTO picks (game_id, model_id, sport, game_date, game_time,
                                       pick_side, pick_label, model_probability,
                                       dk_implied_prob, edge, dk_odds, scored_line,
                                       kelly_fraction, recommended_bet, bankroll_at_pick,
                                       signal_type, downgrade_reason,
                                       decision_book, decision_odds,
                                       decision_implied_prob, decision_edge)
                    VALUES (%(game_id)s, %(model_id)s, %(sport)s, %(game_date)s,
                            %(game_time)s, %(pick_side)s, %(pick_label)s,
                            %(model_probability)s, %(dk_implied_prob)s, %(edge)s,
                            %(dk_odds)s, %(scored_line)s, %(kelly_fraction)s,
                            %(recommended_bet)s, %(bankroll_at_pick)s, %(signal_type)s,
                            %(downgrade_reason)s, %(decision_book)s,
                            %(decision_odds)s, %(decision_implied_prob)s,
                            %(decision_edge)s)
                """, p)
                inserted += 1
            elif _changed(old, p):
                # created_at is when THIS number was observed. The line-movement
                # card on an open NONE row starts its window there. A refresh
                # that only stamps the book, or drops the label note, leaves it.
                conn.execute("""
                    UPDATE picks
                    SET pick_label = %(pick_label)s, pick_side = %(pick_side)s,
                        model_probability = %(model_probability)s,
                        dk_implied_prob = %(dk_implied_prob)s, edge = %(edge)s,
                        dk_odds = %(dk_odds)s, scored_line = %(scored_line)s,
                        downgrade_reason = %(downgrade_reason)s,
                        game_date = %(game_date)s, game_time = %(game_time)s,
                        decision_book = %(decision_book)s,
                        decision_odds = %(decision_odds)s,
                        decision_implied_prob = %(decision_implied_prob)s,
                        decision_edge = %(decision_edge)s,
                        created_at = CASE WHEN %(touch_created)s
                                          THEN now()::text ELSE created_at END
                    WHERE pick_id = %(pick_id)s
                      AND signal_type = 'NONE' AND result IS NULL
                """, {**p, "pick_id": old["pick_id"],
                      "touch_created": _number_moved(old, p)})
                updated += 1
        conn.commit()
    finally:
        conn.close()

    print(f"NFL scored rows {run_date}: {inserted} NONE row(s) written, "
          f"{updated} refreshed, {cleared} cleared beside a BET, "
          f"{len(latest)} (game, model) evaluated")
    return inserted + updated


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="card date (UTC, YYYY-MM-DD); default today")
    ap.add_argument("--opener", action="store_true",
                    help="publish the opener-spread card instead of the wind card")
    ap.add_argument("--snapshots", action="store_true",
                    help="flush the day's DK line snapshots only (no pick publishing)")
    ap.add_argument("--scored", action="store_true",
                    help="write/refresh a NONE row per evaluated game (both rules)")
    args = ap.parse_args()
    if args.scored:
        publish_scored(args.date)
    elif args.snapshots:
        publish_line_snapshots(args.date)
    elif args.opener:
        publish_opener(args.date)
    else:
        publish(args.date)
