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


def _lane_is_locked(conn, game_id: str, model_id: str,
                    player_key: str | None) -> bool:
    """Does this PLAYER's lane already hold an unsettled live BET in this game?

    The FIRST-SIGNAL LIVE LOCK (§1c, config.LOCK_LIVE_PICKS_AT_FIRST_SIGNAL):
    the first BET in a lane is the bet of record at its line and price, and is
    never re-priced however far the edge later moves.

    SCOPED BY PLAYER, WHICH IS A DELIBERATE DIVERGENCE FROM
    models.scorer._locked_live_lanes. That one keys on (game, model) because
    every lane it serves is a GAME-level proposition -- one total, one
    moneyline, one runline per game -- so the lane and the game are the same
    thing. This lane is a PLAYER PROP: one game carries a proposition per
    quarterback, and locking on (game, model) meant the first QB's bet froze the
    lane for everyone else in the game. On a 13-game Sunday with two passers a
    side that silently blocks roughly half the eligible bets, and it looks
    exactly like "the model found nothing".

    Shipped that way in #489 and fixed here. The pre-game NFL prop models have
    the same shape and the same answer: the proposition is the player, not the
    game.
    """
    rows = conn.execute("""
        SELECT 1 FROM picks
        WHERE game_id = %s AND model_id = %s
          AND COALESCE(player_key, '') = COALESCE(%s, '')
          AND is_live = TRUE AND signal_type = 'BET' AND result IS NULL
        LIMIT 1
    """, (game_id, model_id, player_key)).fetchall()
    return bool(rows)


# Decline reasons that are a MARKET OPINION and belong in `picks` as AVOID, the
# way every other live lane records its declines (mlb_live_total_runs 95 BET /
# 73 AVOID, ncaaf_live_total 20/7 -- nfl_live_prop was the only lane whose
# declines lived in a JSONL file nobody could query).
#
# Everything else the executor refuses -- a stale quote, a degenerate state, no
# Kelly stake, the daily exposure cap -- is PLUMBING, not a view on the market.
# Those stay in the audit log only: they answer "is a guard eating candidates",
# which is an operations question, and writing them here would be the "hundreds
# of dead rows a day" CLAUDE.md warns about for live lanes.
_AVOID_REASONS = ("below_threshold", "price_past_ceiling")


def _is_market_opinion(reason: str | None) -> bool:
    return str(reason or "").split(":", 1)[0] in _AVOID_REASONS


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
        # (game, model, player, side) -> the (line, price) last written as AVOID.
        self._avoid_sigs: dict[tuple, tuple] = {}

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
        # THE BET PATH RUNS FIRST AND ALONE (Matt, 2026-09-05: recording
        # declines "shouldn't prevent bets from being live"). Nothing in the
        # AVOID path can delay, block or fail a bet: it is a separate branch,
        # separately guarded, and a decline that cannot be written costs a row
        # in a research table and nothing else.
        if getattr(decision, "bet", False):
            try:
                self._write(decision)
            except Exception:           # noqa: BLE001
                log.exception("live pick write failed; decision stands in the JSONL log")
            return
        if _is_market_opinion(getattr(decision, "reason", None)):
            try:
                self._write_avoid(decision)
            except Exception:           # noqa: BLE001
                log.exception("live AVOID write failed; decision stands in the JSONL log")

    def _write_avoid(self, decision) -> None:
        """Record a model-level decline as an AVOID row.

        WHY AT ALL. Every other live lane already does this -- mlb_live_total_runs
        carries 95 BET and 73 AVOID, ncaaf_live_total 20 and 7 -- and CLAUDE.md's
        evaluation rule says any analysis of thresholds or timing must see the
        whole population, not just what cleared the live bar. nfl_live_prop was
        the only lane whose declines lived in a JSONL file on a Railway volume,
        so its cut could never be swept against its own near-misses.

        WRITTEN ONLY WHEN THE PROPOSITION CHANGES, which is what keeps this from
        becoming churn. The executor evaluates every candidate on every poll --
        at a 5s cadence that is thousands of identical opinions an hour -- while
        the thing a reader cares about is the line and price on offer. Same rule
        and same reasoning as models.live_scorer._lane_signature: side, signal,
        line, price, and deliberately NOT model_probability, which drifts on
        every snap while the bet on offer is unchanged.

        The signature cache is per worker process. A restart re-writes one row
        per live lane, which is a handful, and the alternative (a DB read per
        candidate per poll) is the pool exhaustion CLAUDE.md documents for the
        NCAAF loop.
        """
        player_key = _norm_player(decision.player)
        side = str(decision.side or "").lower()
        key = (decision.game_id, decision.model_id, player_key or "", side)
        sig = (
            None if decision.line is None else round(float(decision.line), 2),
            None if decision.price is None else round(float(decision.price), 2),
        )
        if self._avoid_sigs.get(key) == sig:
            return                      # same proposition, already recorded

        ctx = decision.context or {}
        conn = self._connect()
        try:
            game_id = resolve_game_id(conn, ctx.get("home_team"),
                                      ctx.get("away_team"), decision.ts)
            if game_id is None:
                return

            # A lane holding the bet of record is not also "avoided". Same rule
            # the MLB loop applies by excluding locked lanes from its rewrite.
            from config import LOCK_LIVE_PICKS_AT_FIRST_SIGNAL
            if LOCK_LIVE_PICKS_AT_FIRST_SIGNAL and _lane_is_locked(
                    conn, game_id, decision.model_id, player_key):
                self._avoid_sigs[key] = sig
                return

            # Replace this lane's standing AVOID, never a BET (§1c). The
            # signal_type guard is what makes that structural rather than
            # incidental -- the same guard ncaaf_live.gameday.write_picks uses.
            conn.execute("""
                DELETE FROM picks
                WHERE game_id = %s AND model_id = %s
                  AND COALESCE(player_key, '') = COALESCE(%s, '')
                  AND pick_side = %s
                  AND is_live = TRUE AND result IS NULL
                  AND signal_type <> 'BET'
            """, (game_id, decision.model_id, player_key, side))
            row = build_pick(decision, game_id, self._bankroll_value())
            row["signal_type"] = "AVOID"
            row["kelly_fraction"] = 0.0
            row["recommended_bet"] = 0.0
            conn.execute(_INSERT_SQL, row)
            conn.commit()
            self._avoid_sigs[key] = sig
        finally:
            try:
                conn.close()
            except Exception:           # noqa: BLE001
                pass

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
                    conn, game_id, decision.model_id,
                    _norm_player(decision.player)):
                log.info("lane %s/%s locked for %s -- bet of record stands",
                         decision.model_id, decision.player, game_id)
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
