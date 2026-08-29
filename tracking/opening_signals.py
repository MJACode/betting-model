"""
Opening-signal shadow track.

The live `picks` table is deleted and re-scored every hourly refresh, so a
game/market flips in and out of BET as the line moves. This module locks the
FIRST refresh a game/market crosses the BET threshold into `opening_signals`
and never overwrites it (lock_key UNIQUE), so we can measure two things the
churning table can't:

  1. "Lock the open" vs "chase the live line" — settle the locked opening
     signal independently and compare its record to the live/closing picks.
  2. How the line moved AFTER we locked — clv_pct vs our opening dk_odds
     (positive = the line moved toward us), bucketed as toward/against/flat,
     crossed with which side the public was on (with_public / contrarian).

This is a shadow track: it never touches the live `picks` flow or what
settle_picks reports, so the paper-trading go-live gate is unaffected. Game-level
markets are settled here (that's where line-move + public splits apply); props
are captured now so the data accrues and can be settled in a follow-up.
"""

from __future__ import annotations

from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

# Self-heal window: settle re-checks unsettled game-level signals this many days
# back so a day missed by the morning settle isn't stuck pending forever.
_OPENING_SETTLE_WINDOW_DAYS = 21

from loguru import logger

from config import UFC_SCORE_AHEAD_DAYS, NFL_LOCK_AHEAD_DAYS
from data.db import get_connection, DBConnection


# Model prefixes settled here (game-level markets only, Phase 1). Props, UFC,
# golf and live picks are captured but not settled in this pass.
_NON_GAME_PREFIXES = (
    "mlb_prop_", "wnba_prop_", "nba_prop_", "ufc_", "golf_", "mlb_live_",
)


def _is_game_level(model_id: str) -> bool:
    return not any(model_id.startswith(p) for p in _NON_GAME_PREFIXES)


# ── Capture ─────────────────────────────────────────────────────────────────

def capture_opening_signals(target_date: str | None = None,
                            dry_run: bool = False) -> int:
    """
    Lock the first BET cross for each game/market (per player for props) into
    opening_signals. Reads the live BET picks standing right now and inserts any
    lock_key not already present — so the first refresh a pick becomes a BET wins
    and later refreshes (incl. side flips) can't overwrite it.

    Live (in-play) picks are excluded — the opening-signal concept is about
    pre-game line/public movement. Idempotent; run as the last pipeline step.

    UFC look-ahead picks (scored up to UFC_SCORE_AHEAD_DAYS early, and re-scored
    every refresh until fight-day morning) are ALSO captured here at their FIRST
    BET cross — days before the fight — under a DISTINCT lock_key suffixed
    ':early'. The fight-day first cross still locks under the normal key, so each
    fight can carry BOTH rows: the ':early' snapshot (lock-at-first-signal shadow)
    and the day-of row (the bet of record that Discord/push post and that the
    live pick freezes to). Consumers that surface signals (discord_notifier,
    push_notifier) exclude ':early' rows — they are measurement, never display.
    Caveat for the comparison: an early totals signal may carry the synthetic 2.5
    line / no DK price (dk_odds NULL), which is exactly the information gap the
    comparison is meant to measure.

    Returns the number of NEW opening signals locked on this run.
    """
    if target_date is None:
        target_date = date.today().isoformat()

    # UFC fights are scored up to a week ahead — capture their first BET cross
    # early too (see docstring), under a ':early' key that never displays.
    ufc_horizon = (
        date.fromisoformat(target_date) + timedelta(days=UFC_SCORE_AHEAD_DAYS)
    ).isoformat()
    # NFL is the opposite case and gets a NORMAL key, so it posts on the day it
    # is written. Its two rules (nfl_wind_totals, nfl_opener_spread) are
    # INSERT-ONCE: the pick is immutable from the moment it lands and is never
    # re-priced (§28). So there is no "flicker vs bet of record" ambiguity to
    # wait out — it is already the bet of record. Waiting for game day would be
    # actively wrong for the opener, whose entire edge IS the stale soft-book
    # number: by kickoff the book has corrected and the bet no longer exists.
    # Contrast UFC/GOLF/NCAAF, which delete-and-rescore every pass until game
    # morning and therefore genuinely are not locked until then.
    nfl_horizon = (
        date.fromisoformat(target_date) + timedelta(days=NFL_LOCK_AHEAD_DAYS)
    ).isoformat()

    conn = get_connection()
    try:
        locked_at = datetime.now(ZoneInfo("America/New_York")).isoformat()

        date_pred = """(p.game_date = %s
                   OR (p.sport = 'UFC' AND p.game_date > %s AND p.game_date <= %s)
                   OR (p.sport = 'NFL' AND p.game_date > %s AND p.game_date <= %s))"""
        date_args = (target_date, target_date, ufc_horizon,
                     target_date, nfl_horizon)

        before = conn.execute(f"""
            SELECT COUNT(*) FROM opening_signals p WHERE {date_pred}
        """, date_args).fetchone()[0]

        candidates = conn.execute(f"""
            SELECT COUNT(*)
            FROM picks p
            WHERE {date_pred}
              AND p.signal_type = 'BET'
              AND (p.is_live IS NULL OR p.is_live = FALSE)
              AND p.model_id NOT LIKE 'mlb_live_%%'
        """, date_args).fetchone()[0]

        if dry_run:
            logger.info(
                f"[dry-run] {candidates} live BET picks for {target_date}; "
                f"{before} already locked"
            )
            return 0

        conn.execute(f"""
            INSERT INTO opening_signals (
                lock_key, game_id, model_id, sport, game_date, player_id,
                pick_side, pick_label, model_probability, dk_implied_prob, edge,
                dk_odds, scored_line, public_bet_pct, public_money_pct,
                confidence_tier, kelly_fraction, recommended_bet,
                bankroll_at_pick, locked_at
            )
            SELECT
                p.game_id || ':' || p.model_id || COALESCE(':' || p.player_id, '')
                    || CASE WHEN p.sport = 'UFC' AND p.game_date > %s
                            THEN ':early' ELSE '' END,
                p.game_id, p.model_id, p.sport, p.game_date, p.player_id,
                p.pick_side, p.pick_label, p.model_probability, p.dk_implied_prob,
                p.edge, p.dk_odds, p.scored_line, p.public_bet_pct,
                p.public_money_pct, p.confidence_tier, p.kelly_fraction,
                p.recommended_bet, p.bankroll_at_pick, %s
            FROM picks p
            WHERE {date_pred}
              AND p.signal_type = 'BET'
              AND (p.is_live IS NULL OR p.is_live = FALSE)
              AND p.model_id NOT LIKE 'mlb_live_%%'
            ON CONFLICT (lock_key) DO NOTHING
        """, (target_date, locked_at) + date_args)
        conn.commit()

        after = conn.execute(f"""
            SELECT COUNT(*) FROM opening_signals p WHERE {date_pred}
        """, date_args).fetchone()[0]

        new_locked = after - before
        logger.info(
            f"Opening signals: {new_locked} newly locked for {target_date} "
            f"({after} total locked, {candidates} live BET picks)"
        )
        return new_locked
    finally:
        conn.close()


# ── Settle ──────────────────────────────────────────────────────────────────

def settle_opening_signals(conn: DBConnection, game_date: str,
                           settled_at: str) -> tuple[int, int, int, int, float, float]:
    """
    Settle game-level opening signals for game_date and record the line story.

    Reuses paper_tracker's result + closing-line helpers. For each locked signal
    whose game is final, writes:
      - result / profit_flat / profit_kelly (vs our OPENING dk_odds + scored_line)
      - closing_dk_odds / closing_line / clv_pct (close vs our opening price)
      - line_move_dir (toward | against | flat) — how the line moved after lock
      - public_side  (with_public | contrarian | even) — from the locked split

    Shadow track: the caller must NOT fold these into the live settle totals.
    Returns (wins, losses, pushes, no_actions, profit_flat, profit_kelly).
    """
    # Lazy imports to avoid a circular import (paper_tracker imports this module).
    from tracking.paper_tracker import (
        _compute_result, _closing_dk_odds, _market_for_pick, _SIDE_PRICE_COL,
    )
    from models.scorer import american_to_implied_prob

    # Trailing window (self-heal) — not just `game_date`. A day the morning settle
    # missed (pipeline hiccup, games not final yet) would otherwise stay pending
    # forever, which also blocks that day's tracked parlay from settling.
    window_start = (datetime.strptime(game_date, "%Y-%m-%d")
                    - timedelta(days=_OPENING_SETTLE_WINDOW_DAYS)).strftime("%Y-%m-%d")

    rows = conn.execute("""
        SELECT os.id, os.game_id, os.model_id, os.pick_side, os.dk_odds,
               os.scored_line, os.recommended_bet, os.public_bet_pct,
               g.home_score, g.away_score,
               g.home_win, g.home_win_reg, g.went_to_ot, g.commence_time,
               g.home_score_f5, g.away_score_f5
        FROM opening_signals os
        JOIN games g ON os.game_id = g.game_id
        WHERE os.game_date >= %s
          AND os.result IS NULL
          AND os.model_id NOT LIKE 'mlb_prop_%%'
          AND os.model_id NOT LIKE 'wnba_prop_%%'
          AND os.model_id NOT LIKE 'nba_prop_%%'
          AND os.model_id NOT LIKE 'ufc_%%'
          AND os.model_id NOT LIKE 'golf_%%'
          AND os.model_id NOT LIKE 'mlb_live_%%'
          AND g.home_score IS NOT NULL
    """, (window_start,)).fetchall()

    wins = losses = pushes = no_actions = 0
    total_flat = total_kelly = 0.0

    for row in rows:
        (sig_id, game_id, model_id, pick_side, dk_odds, scored_line, rec_bet,
         public_bet_pct, home_score, away_score, home_win, home_win_reg,
         went_to_ot, commence_time, home_score_f5, away_score_f5) = row

        market = _market_for_pick(model_id)
        is_f5  = "1st_5_innings" in market

        if is_f5:
            if home_score_f5 is None or away_score_f5 is None:
                continue
            settle_home = home_score_f5
            settle_away = away_score_f5
            settle_home_win = (int(home_score_f5 > away_score_f5)
                               if home_score_f5 != away_score_f5 else None)
        else:
            settle_home = home_score
            settle_away = away_score
            settle_home_win = home_win

        spread_home = scored_line if "spreads" in market else None
        total_line  = scored_line if "totals"  in market else None
        odds_for_calc = dk_odds if dk_odds is not None else -110.0

        result, profit_flat, profit_kelly = _compute_result(
            pick_side, market,
            settle_home, settle_away,
            settle_home_win, home_win_reg, went_to_ot,
            odds_for_calc, spread_home, total_line,
            rec_bet or 0.0,
        )

        # Line story: how the price moved from our opening lock to the close.
        closing_dk = closing_line = clv_pct = line_move_dir = None
        if dk_odds is not None:
            closing = _closing_dk_odds(conn, game_id, market, commence_time)
            if closing:
                price_col = _SIDE_PRICE_COL.get(pick_side)
                close_price = closing.get(price_col) if price_col else None
                open_ip  = american_to_implied_prob(dk_odds)
                close_ip = (american_to_implied_prob(close_price)
                            if close_price is not None else None)
                if open_ip is not None and close_ip is not None:
                    clv_pct = round((close_ip - open_ip) * 100, 2)
                    line_move_dir = ("toward" if clv_pct > 0.5
                                     else "against" if clv_pct < -0.5 else "flat")
                    closing_dk = close_price
                    if "totals" in market:
                        closing_line = closing.get("total_line")
                    elif "spreads" in market:
                        closing_line = closing.get("spread_home")

        # Public side at lock (public_bet_pct is already on our pick side).
        public_side = None
        if public_bet_pct is not None:
            public_side = ("with_public" if public_bet_pct >= 55
                           else "contrarian" if public_bet_pct <= 45 else "even")

        conn.execute("""
            UPDATE opening_signals
            SET result          = %s,
                profit_flat     = %s,
                profit_kelly    = %s,
                closing_dk_odds = %s,
                closing_line    = %s,
                clv_pct         = %s,
                line_move_dir   = %s,
                public_side     = %s,
                settled_at      = %s
            WHERE id = %s
        """, (result, profit_flat, profit_kelly, closing_dk, closing_line,
              clv_pct, line_move_dir, public_side, settled_at, sig_id))

        if result == "WIN":
            wins += 1
            total_flat += profit_flat
            total_kelly += profit_kelly
        elif result == "LOSS":
            losses += 1
            total_flat += profit_flat
            total_kelly += profit_kelly
        elif result == "PUSH":
            pushes += 1
        else:
            no_actions += 1

    if wins + losses + pushes + no_actions:
        logger.info(
            f"Opening-signal shadow settle {game_date}: "
            f"{wins}W / {losses}L / {pushes}P / {no_actions}N "
            f"(flat ${total_flat:+,.2f})"
        )
    return wins, losses, pushes, no_actions, total_flat, total_kelly


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Capture opening signals")
    parser.add_argument("--date", help="game_date YYYY-MM-DD (default today)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    capture_opening_signals(args.date, dry_run=args.dry_run)
