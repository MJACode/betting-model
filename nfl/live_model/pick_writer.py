"""
Write live BET decisions into Supabase `picks`, so they reach the app, Discord
and push like every other pick.

Matt, 2026-09-05: *"NFL should be live out of the gate, we should not do paper
trading and delay this being an available feature."*

WHAT THIS REPLACES. The worker recorded every decision to a JSONL file on the
Railway volume and alerted nobody. That is a complete audit log and it is not a
record the platform can read: nothing joined it to `games`, nothing settled it,
and no surface displayed it. The lane could run every Sunday of the season and
still show a settled record of zero.

SCOPE -- ONE LANE. `nfl_live_prop` (nfl/live_model/models/pass_attempt_bias.py)
is the only lane with an implementation. `nfl_live_halftime`, `nfl_live_deriv`
and `nfl_live_stale` exist as EV_THRESHOLDS keys with nothing assigning them, so
nothing can write them. That matters beyond tidiness: `DERIVATIVE_MARKETS` is
all half and quarter lines, and `games` stores full-game scores only (plus MLB's
F5) -- a pick on `totals_q3` could not be settled by anything in this repo. If
one of those lanes is ever implemented, it needs a scores source BEFORE it is
allowed to write here.

BETS ONLY. The executor records every PASS too, and those stay in the JSONL log
where they belong. Writing them to `picks` would be the "hundreds of dead rows a
day" that CLAUDE.md warns about for live lanes -- the pass record answers "was a
guard silently eating candidates", which is an audit question, not a board.

THE GAME ID IS THE WHOLE PROBLEM. A Decision carries ESPN's event id; `picks`
and `games` are keyed `NFL_{season}_{week}_{away}_{home}`. The book's event id
is a third unrelated string. The only thing the feeds share is who is playing,
which is why `Quote` carries the book's team names and why the executor now puts
them on every decision's context. Resolution is (both teams, kickoff day) against
`games` -- and it REFUSES rather than guesses: an unresolved decision is logged
and dropped, because a pick written under an id that joins to nothing can never
settle, and an unsettleable pick is worse than an absent one.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

MODEL_ID = "nfl_live_prop"

# The market this lane trades, as the platform spells it. Settlement reads
# picks.prop_market (tracking/paper_tracker._PROP_MARKET_STAT_BY_MODEL), the
# same shape nfl_prop_market uses for one model id spanning many markets.
LANE_MARKET = "player_pass_attempts"


def _norm_player(name: str | None) -> str | None:
    """Normalised player key.

    The odds feed and nflverse do not spell names the same way, and normalised
    name is the only bridge the whole NFL prop system has -- the same join the
    snap counts and tracking/paper_tracker's nfl_player settlement use. Keep
    this in step with that normaliser rather than inventing a second one.
    """
    if not name:
        return None
    return " ".join(str(name).replace(".", "").replace("'", "").split()).upper()


def resolve_game_id(conn, home_team: str | None, away_team: str | None,
                    kickoff: datetime | None) -> str | None:
    """The platform's NFL game_id for a book's (home, away) around `kickoff`.

    Returns None rather than guessing. Every caller treats None as "drop this
    decision", so a wrong answer here is strictly worse than no answer: it
    writes a real bet under an id that joins to no game and therefore settles
    never.

    The +/- 1 day window is deliberate. `games.game_date` is the ET calendar
    day; a Sunday-night or Monday-night kickoff is the next UTC day, and a
    London game is the same UTC day but can sit either side depending on how
    the feed stamps it. Matching both teams makes the window safe to widen --
    two NFL games with the same pair within a day of each other do not exist.
    """
    from data_ingest.parse import TEAM_MAP

    home = TEAM_MAP.get((home_team or "").strip())
    away = TEAM_MAP.get((away_team or "").strip())
    if not home or not away or kickoff is None:
        log.warning("cannot resolve game_id: home=%r->%r away=%r->%r kickoff=%r",
                    home_team, home, away_team, away, kickoff)
        return None

    day = kickoff.astimezone(timezone.utc).date()
    rows = conn.execute("""
        SELECT game_id FROM games
        WHERE sport = 'NFL' AND home_team = %s AND away_team = %s
          AND game_date BETWEEN %s AND %s
        ORDER BY game_date
        LIMIT 2
    """, (home, away, (day - timedelta(days=1)).isoformat(),
          (day + timedelta(days=1)).isoformat())).fetchall()
    if len(rows) != 1:
        # Zero is a schedule gap; two would mean the window caught a rematch,
        # which the NFL schedule does not produce. Either way: refuse.
        log.warning("game_id resolution found %d rows for %s @ %s around %s",
                    len(rows), away, home, day)
        return None
    return rows[0][0]


def build_pick(decision, game_id: str, bankroll: float) -> dict:
    """One `picks` row from one BET decision.

    `edge` is model_prob - market_prob, the platform's definition everywhere.
    It is NOT the executor's EV (`model_prob * decimal - 1`), which is the
    lane's own gate and a different quantity -- storing EV in the edge column
    would put this lane on a different scale from every other model in the
    table and quietly corrupt any cross-model threshold sweep.
    """
    ctx = decision.context or {}
    side = str(decision.side or "").lower()
    player = decision.player or ctx.get("player")
    line = decision.line
    label = (f"{player} {side.capitalize()} {line:g} Pass Attempts"
             if player and line is not None else
             f"{player or decision.market} {side}")
    return {
        # EXACTLY the columns _INSERT_SQL binds, and nothing else. A key here
        # that the statement does not name is silently dropped by psycopg2, so
        # an unused key is not tidy-up debt -- it is a column that looks written
        # and is not.
        "game_id": game_id,
        "model_id": decision.model_id,
        "sport": "NFL",
        "game_date": decision.ts.astimezone(timezone.utc).date().isoformat(),
        "game_time": None,
        "pick_side": side,
        "pick_label": label,
        "model_probability": float(decision.model_prob),
        "dk_implied_prob": float(decision.market_prob),
        "edge": float(decision.model_prob) - float(decision.market_prob),
        "dk_odds": float(decision.price),
        "scored_line": float(line) if line is not None else None,
        "kelly_fraction": float(decision.stake_fraction or 0.0),
        "recommended_bet": round(float(decision.stake_fraction or 0.0) * bankroll, 2),
        "bankroll_at_pick": bankroll,
        "signal_type": "BET",
        "confidence_tier": None,
        "prop_market": LANE_MARKET,
        "player_key": _norm_player(player),
        "player_id": _norm_player(player),
        "is_live": True,
        "score_diff_at_pick": ctx.get("score_diff"),
    }


# Its own INSERT rather than models.scorer._insert_picks, which does not carry
# `prop_market` or `player_key` -- the two columns settlement reads for a model
# id that spans markets. Passing them in the row dict would have silently done
# nothing, since psycopg2 named parameters ignore extra keys, and the lane would
# have written picks that never settle. Mirrors the column set
# scripts/nfl_prop_market_card.py uses, plus the live flag.
#
# ON CONFLICT DO NOTHING for the same reason _insert_picks has it: the
# uq_picks_one_row_per_pick index (migration picks_one_row_per_pick.sql) makes a
# duplicate an IntegrityError, which would abort the transaction and cost the
# tick its pick. The first-signal lock is what PREVENTS the duplicate; this only
# makes the losing side of a race harmless.
_INSERT_SQL = """
    INSERT INTO picks (game_id, model_id, sport, game_date, game_time,
                       pick_side, pick_label, model_probability, dk_implied_prob,
                       edge, dk_odds, scored_line, kelly_fraction,
                       recommended_bet, bankroll_at_pick, signal_type,
                       confidence_tier, prop_market, player_key, player_id,
                       is_live, score_diff_at_pick)
    VALUES (%(game_id)s, %(model_id)s, %(sport)s, %(game_date)s, %(game_time)s,
            %(pick_side)s, %(pick_label)s, %(model_probability)s,
            %(dk_implied_prob)s, %(edge)s, %(dk_odds)s, %(scored_line)s,
            %(kelly_fraction)s, %(recommended_bet)s, %(bankroll_at_pick)s,
            %(signal_type)s, %(confidence_tier)s, %(prop_market)s,
            %(player_key)s, %(player_id)s, %(is_live)s, %(score_diff_at_pick)s)
    ON CONFLICT DO NOTHING
"""


def _lane_is_locked(conn, game_id: str, model_id: str) -> bool:
    """Does this lane already hold an unsettled live BET for this game?

    The FIRST-SIGNAL LIVE LOCK (§1c, config.LOCK_LIVE_PICKS_AT_FIRST_SIGNAL):
    the first BET in a (game, model) lane is the bet of record at its line and
    price, and is never re-priced however far the edge later moves.

    The canonical implementation is models.scorer._locked_live_lanes, which the
    MLB and NCAAF live loops call. This package CANNOT import it: `from models.x
    import` under nfl/ resolves to whichever `models` package sys.path reaches
    first, and both roots are on the path on every scheduled run --
    tests/test_nfl_model_imports.py fails the build over exactly that. So the
    predicate is restated here, and tests/test_nfl_live_pick_writer.py asserts it
    still matches the scorer's, which is the drift guard the shared import would
    otherwise have given for free.
    """
    rows = conn.execute("""
        SELECT DISTINCT model_id FROM picks
        WHERE game_id = %s AND is_live = TRUE
          AND signal_type = 'BET' AND result IS NULL
    """, (game_id,)).fetchall()
    return model_id in {r[0] for r in rows}


class PicksRecorder:
    """Recorder that writes BET decisions to `picks`. Never raises.

    The executor calls recorders on the hot path and swallows their exceptions,
    but this one guards itself as well: a Postgres blip must cost one pick's
    visibility, not the loop's tick. The JSONL log is the durable audit trail
    either way, so a decision dropped here is still recoverable afterwards.
    """

    def __init__(self, bankroll: float | None = None, conn_factory=None):
        self._bankroll = bankroll
        self._conn_factory = conn_factory

    def _bankroll_value(self) -> float:
        if self._bankroll is not None:
            return self._bankroll
        import config
        return float(config.BANKROLL)

    def _connect(self):
        if self._conn_factory is not None:
            return self._conn_factory()
        from data.db import get_connection
        return get_connection()

    def __call__(self, decision) -> None:
        if not getattr(decision, "bet", False):
            return                      # passes live in the JSONL log only
        try:
            self._write(decision)
        except Exception:               # noqa: BLE001
            log.exception("live pick write failed; decision stands in the JSONL log")

    def _write(self, decision) -> None:
        from config import LOCK_LIVE_PICKS_AT_FIRST_SIGNAL

        ctx = decision.context or {}
        conn = self._connect()
        try:
            game_id = resolve_game_id(conn, ctx.get("home_team"),
                                      ctx.get("away_team"), decision.ts)
            if game_id is None:
                return                  # refuse, never guess -- see module docstring

            # FIRST-SIGNAL LIVE LOCK (§1c, config.LOCK_LIVE_PICKS_AT_FIRST_SIGNAL).
            # A lane holding an unsettled live BET for this game is the bet of
            # record and is never re-priced. Same helper the MLB and NCAAF live
            # loops use, so the three lanes cannot drift on what "locked" means.
            if LOCK_LIVE_PICKS_AT_FIRST_SIGNAL and _lane_is_locked(
                    conn, game_id, decision.model_id):
                log.info("lane %s locked for %s -- bet of record stands",
                         decision.model_id, game_id)
                return

            row = build_pick(decision, game_id, self._bankroll_value())
            conn.execute(_INSERT_SQL, row)
            conn.commit()
            log.info("WROTE live %s %s %s @ %s", row["model_id"],
                     row["pick_label"], row["pick_side"], row["dk_odds"])
        finally:
            try:
                conn.close()
            except Exception:           # noqa: BLE001
                pass


class TeeRecorder:
    """Fan one decision out to several recorders, independently.

    Order matters and is the executor's own rule: the durable audit log is
    written FIRST, so a decision that reaches Postgres but not the log cannot
    happen. One recorder raising must not stop the others -- a Postgres outage
    that also silenced the JSONL log would lose the record entirely.
    """

    def __init__(self, *recorders):
        self.recorders = [r for r in recorders if r is not None]

    def __call__(self, decision) -> None:
        for r in self.recorders:
            try:
                r(decision)
            except Exception:           # noqa: BLE001
                log.exception("recorder %r failed; continuing", r)
