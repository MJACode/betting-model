"""NHL total goals card: write `nhl_over_under` bets (models/nhl_totals_market.py).

Runs on every refresh pass right after the odds fetch, and in the 6am daily run
right after its odds step, so the fetch it reads is the one just stored. It
prices every NHL game that has not started, with no date or lead horizon:
Pinnacle's own listing sets the window (it first hangs a total about 24 hours
before puck drop), and the prior-day quotes carry most of the evidence.

LIVE, with no default-off write switch (mike, 2026-10-08: "This is live
model"). The MLB cards' switches flipped off on a redeploy and those models
went dark without a trace (config.py, MLB_*_PUBLISH).

INSERT ONCE (CLAUDE.md 1c). A game's first qualifying fetch is the bet of
record. A later better price, a moved number or the other side all write
nothing. The check-then-insert runs under the model's transaction-scoped
advisory lock, because the 6am run and a refresh pass can overlap and the
picks unique index includes the side, so it would not stop an over plus an
under.

BOTH STARTING GOALIES CONFIRMED FIRST (mike, 2026-10-20: "We should
absolutely always know the goalie matchup before making a bet as well."). A
game is priced only once models/nhl_goalie_gate.py says its matchup is known;
every other game is held back before its quotes are read, and the pass logs how
many and why. A known game whose newest Pinnacle fetch was taken before the
matchup became known waits too (`after_confirmation`): that price was set
without the goalie news, and the next fetch decides. The INSERT refuses an
unknown game again (refuse_unknown, then the scorer's own insert guard). THIS
MOVED THE MODEL'S DECISION MOMENT: until 2026-10-20 a game's first qualifying
fetch was often the day before (the prior-day quotes carry most of the
evidence, above); now it is the first qualifying fetch after both goalies are
confirmed on game day. That regime has not been graded on its own.

BET ROWS ONLY. The scorer deletes every model's unsettled non-BET rows on each
pass, so a "declined" row would not survive. The per-pass diagnostic line in
the worker log is how an empty card is told apart from a broken one.

ROW SHAPE: the scorer's convention for a pick decided away from DraftKings
(scripts/nhl_props_card.py). dk_odds / dk_implied_prob / edge are DraftKings'
own price at this number in this fetch, else NULL / 0.0 / 0.0; decision_* is
the book taken, always set; line_book names that book only when DraftKings did
not hang the number; best_* is set only when the bet is not at DraftKings.

    python -m scripts.nhl_totals_card              # print the card, write nothing
    python -m scripts.nhl_totals_card --publish    # write new bets
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import models.nhl_goalie_gate as goalie_gate
import models.nhl_totals_market as mk
from data.db import get_connection
from models.market_relative import implied
from models.scorer import (
    _build_pick_label,
    _get_current_bankroll,
    _insert_picks,
    quarter_kelly,
)
from tracking.pick_integrity import pick_problems

MODEL_ID = mk.MODEL_ID
SPORT = "NHL"
MARKET = "totals"
_ET = ZoneInfo("America/New_York")


def slate(conn, now: datetime) -> dict[str, dict]:
    """Every NHL game a book has listed whose start is after `now`. No horizon.

    The game_date bound only lets the query use the date: a game that starts
    after `now` cannot carry an ET date earlier than yesterday's. The started
    check is done on the parsed start time, because commence_time is TEXT in
    mixed shapes.
    """
    from features.feature_engine import _parse_iso_ts
    from data.ingestors.nhl_schedule_refresh import listed_by_a_book
    since = (now.astimezone(_ET).date() - timedelta(days=1)).isoformat()
    # A game no book has listed has no Pinnacle total either. Without this the
    # season the schedule refresh stores ahead (~1,200 games) would be read,
    # goalie-gated and logged as held on every pass.
    rows = conn.execute(f"""
        SELECT game_id, home_team, away_team, commence_time, game_date
        FROM games
        WHERE sport = 'NHL'
          AND commence_time IS NOT NULL
          AND game_date >= %s
          AND {listed_by_a_book()}
    """, (since,)).fetchall()
    out = {}
    # The stored start is the odds feed's, about ten minutes after the
    # scheduled puck drop: nothing is decided that close to it
    # (config.NHL_DECIDE_BEFORE_START_MIN).
    margin = timedelta(minutes=config.NHL_DECIDE_BEFORE_START_MIN)
    for gid, home, away, commence, gd in rows:
        start = _parse_iso_ts(commence)
        if start is None or start - margin <= now:
            continue
        out[gid] = {"home": home, "away": away,
                    "commence_time": commence, "game_date": str(gd)[:10]}
    return out


def after_confirmation(quotes: list[dict], known_at: dict) -> list[dict]:
    """The quotes of the games whose newest Pinnacle fetch (odds.created_at,
    the clock find_bets pairs on) was taken at or after the matchup became
    known. A game whose newest one predates it is dropped whole, and logged:
    its next fetch decides. A game with no recorded moment keeps its quotes
    (a stored designation always carries one; see the scorer's twin,
    models/scorer._nhl_price_reason)."""
    newest: dict = {}
    for q in quotes:
        if q.get("book") == mk.SHARP_BOOK:
            ts = mk._fetch_ts(q)
            if ts is not None and (q["game_id"] not in newest or ts > newest[q["game_id"]]):
                newest[q["game_id"]] = ts
    wait = sorted(g for g, at in known_at.items()
                  if at is not None and g in newest and newest[g] < at)
    if wait:
        logger.info(f"NHL totals card: {len(wait)} game(s) wait for a fetch taken after both "
                    f"goalies were confirmed: {', '.join(wait)}")
    return [q for q in quotes if q["game_id"] not in wait]


def pick_rows(bets, games: dict, bankroll: float) -> list[dict]:
    """Card bets -> picks rows. Pure given its inputs, so it is testable."""
    from models.honest_ev import gate
    rows = []
    for b in bets:
        # The platform's EV gate on the model's own probability at the price
        # taken. With own-probability membership it agrees with find_bets.
        ev = gate(MODEL_ID, b.fair, b.price)
        if not ev.clears:
            logger.info(f"{MODEL_ID}: {ev.reason} - dropped {b.game_id} "
                        f"{b.side} @{b.book}")
            continue
        g = games.get(b.game_id, {})
        home, away = g.get("home", ""), g.get("away", "")
        line = float(b.line)
        label = _build_pick_label(b.side, home, away, MARKET, line)
        problems = pick_problems(label, b.side, line, MODEL_ID, home, away)
        if problems:
            logger.error(f"{MODEL_ID}: refusing {b.game_id}: {'; '.join(problems)}")
            continue
        price = float(b.price)
        dec_implied = implied(price)
        dk = b.dk_price
        dk_implied = implied(dk) if dk is not None else None
        at_dk = b.book == mk.REFERENCE_BOOK
        kelly_frac, rec_bet = quarter_kelly(b.fair, dec_implied, bankroll)
        decision_edge = round(b.fair - dec_implied, 4)
        rows.append({
            "game_id": b.game_id, "model_id": MODEL_ID, "sport": SPORT,
            "game_date": g.get("game_date"),
            "game_time": g.get("commence_time"),
            "pick_side": b.side, "pick_label": label,
            # Pinnacle's no-vig probability of the side, in the same fetch.
            "model_probability": round(b.fair, 4),
            # DraftKings' own price at this number in this fetch, else the
            # NOT NULL placeholders.
            "dk_odds": dk,
            "dk_implied_prob": round(dk_implied, 4) if dk is not None else 0.0,
            "edge": round(b.fair - dk_implied, 4) if dk is not None else 0.0,
            "dk_bet_link": b.dk_link if dk is not None else None,
            "line_book": None if dk is not None else b.book,
            "scored_line": line,
            "kelly_fraction": kelly_frac,
            "recommended_bet": rec_bet,
            "bankroll_at_pick": bankroll,
            "signal_type": "BET",
            # MED on every bet, as the NHL prop cards write. The app draws HIGH
            # as a green chip, and the evidence gives no tier: the EV >= 0.02
            # cut, which holds every edge >= 3 points, returned +0.14% on 548
            # bets against +4.72% at the live 0.01 (UX review, 2026-10-08).
            "confidence_tier": "MED",
            "injury_flag": None,
            "injury_detail": None,
            # The price the bet was taken at. Always set: the scorer deletes an
            # unstarted BET with dk_odds and decision_odds both NULL.
            "decision_book": b.book,
            "decision_odds": price,
            "decision_implied_prob": round(dec_implied, 4),
            "decision_edge": decision_edge,
            "best_book": None if at_dk else b.book,
            "best_odds": None if at_dk else price,
            "best_implied_prob": None if at_dk else round(dec_implied, 4),
            "best_edge": None if at_dk else decision_edge,
            "best_bet_link": None if at_dk else b.link,
        })
    return rows


def publish(conn, rows: list[dict]) -> int:
    """Insert once per game, under the model's lock, in one transaction."""
    if not rows:
        return 0
    from scripts.nfl_wind_publisher import _lock_model
    _lock_model(conn, MODEL_ID)
    # The last line: no bet on a game whose goalie matchup is not known.
    rows = goalie_gate.refuse_unknown(conn, rows, mode="drop", label=MODEL_ID)
    written = 0
    for r in rows:
        # Any BET on the game counts: the other side, a VOIDed or settled one.
        got = conn.execute("""
            SELECT 1 FROM picks
            WHERE game_id = %s AND model_id = %s AND signal_type = 'BET'
            LIMIT 1
        """, (r["game_id"], MODEL_ID)).fetchone()
        if got:
            continue
        _insert_picks(conn, [r])
        written += 1
    conn.commit()
    return written


def render(bets, diag: dict) -> str:
    counts = " ".join(f"{k}={diag.get(k, 0)}" for k in mk.DIAG_KEYS)
    lines = [f"NHL totals card ({MODEL_ID}): {counts}"]
    for b in sorted(bets, key=lambda x: -x.ev):
        lines.append(
            f"  {b.game_id:28s} {b.side:5s} {b.line:4.1f} @{b.book} "
            f"{b.price:+.0f}  fair {b.fair:.4f}  EV {b.ev:+.4f}  "
            f"(PIN {b.sharp_over:+.0f}/{b.sharp_under:+.0f}, fetch {b.created_at})")
    return "\n".join(lines)


def run_card(do_publish: bool = False, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    conn = get_connection()
    try:
        games = slate(conn, now)
        if not games:
            logger.info("NHL totals card: no unstarted NHL games")
            return {"games": 0, "held": 0, "bets": 0, "published": 0}
        # Only a game whose goalie matchup is known may produce a bet
        # (nhl_over_under is not exempt; models/nhl_goalie_gate.is_exempt).
        held: dict = {}
        known_at: dict = {}
        if not goalie_gate.is_exempt(MODEL_ID):
            states = goalie_gate.matchup_states(conn, list(games), now=now)
            games, held = goalie_gate.split_known(games, {g: m.reason for g, m in states.items()})
            goalie_gate.log_held("NHL totals card", held)
            known_at = {g: states[g].known_at for g in games}
        if not games:
            return {"games": len(held), "held": len(held), "bets": 0, "published": 0}
        quotes = after_confirmation(mk.load_fetch_quotes(conn, games), known_at)
        # The card's clock goes to the rule, so a fetch older than
        # config.PREGAME_PRICE_MAX_AGE_MIN is refused (diag `stale_fetch`).
        bets, diag = mk.find_bets(quotes, now=now)
        logger.info("\n" + render(bets, diag))
        published = 0
        if do_publish and bets:
            bankroll = _get_current_bankroll(conn)
            rows = pick_rows(bets, games, bankroll)
            published = publish(conn, rows)
            logger.info(f"NHL totals card: {published} new bet(s) written "
                        f"of {len(bets)} on the card")
        return {"games": len(games) + len(held), "held": len(held), "bets": len(bets),
                "published": published}
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args()
    print(run_card(do_publish=a.publish))


if __name__ == "__main__":
    main()
