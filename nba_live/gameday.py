"""
NBA in-play loop: the game-state models (models/nba_live_ingame.py).

    python -m nba_live.gameday              # the real thing
    python -m nba_live.gameday --dry-run    # decide and log; no writes, no posts
    python -m nba_live.gameday --once       # one pass, then exit

Run from the REPO ROOT. scheduler.run_nba_live_ingame relaunches it every 10
minutes through the NBA evening (max_instances=1); it exits by itself after a
few passes with no regular-season NBA game in progress, so an idle launch
costs a few free ESPN reads and no Odds API credit.

DECISION TIMING MIRRORS THE GRADED SAMPLING. The lab decided at the archive's
purchases. During games those are the top of each UTC hour (and, on some
dates only, the half hour), and each purchase returned the feed's snapshot
from 264 s earlier: the lab's state, its "served" instant, is hh:55:36
(scripts/nba_ingame_data.py, SERVED). So the loop has ONE tick an hour, at
hh:55:36 UTC (NBA_LIVE_INGAME_TICK_SECOND, default 3336), and fetches the odds
once inside the 4 minutes after it (NBA_LIVE_INGAME_TICK_WINDOW_SEC) -- never
between ticks. Hourly only, no half-hour tick: replaying the shipped rule on
the archive's top-of-hour purchases alone keeps every cell positive in every
graded season (docs/thresholds.md has the numbers).

ONE TICK
  1. Games ESPN shows in progress (scoreboard, free) that are regular-season
     games in `games`, with a pre-game prior, and with at least one of the
     three models still undecided.
  2. One odds call (nba_live/odds.py) for every such game.
  3. NBA_LIVE_INGAME_SETTLE_SEC later (default 30), each game's ESPN summary:
     the plays logged so far. The lab counted every play ESPN logged at or
     before a stamp, from the finished game; reading the summary after the
     odds have landed gives ESPN that long to post the plays that happened
     before the quotes were served.
  4. The lab's rows (nba_live/state.py): the state at each quote's own stamp,
     the points since it, Pinnacle's paired quote.
  5. models.nba_live_ingame.decide: every model whose phase holds an
     eligible quote is decided ONCE -- a bet, or a no-bet decision -- and
     written to the ledger (nba_live_ingame_decisions) with its bet in one
     transaction. A model with no eligible quote this tick waits for the
     next tick while its phase lasts.
  6. Every quote of the fetch is stored in `odds` as in_play (source
     'nba_live_ingame'), and the notifiers are asked to post the slate's bets.

THE LOCK (CLAUDE.md section 1c). A (game, model) is decided once: its ledger
row, read at every launch, and any BET the model holds on the game stop it
being decided again. A bet of record is never deleted or re-priced.

WHAT IS NOT HERE, ON PURPOSE. No book-move guard (data/live_quote_guard.
BookMoveClock): the lab had none, and with one read an hour every quote is a
first sight, so the clock could only ever report nothing. The event-relative
guard the rule DOES have is stronger than quote_predates_score: a quote is
eligible only when no point was scored between its own stamp and the moment
it was served, measured on ESPN's play wallclock, for the deciding quote and
its Pinnacle quote alike. No quote-age cap and no edge cap: the lab had none.
The -200 floor is config.min_odds_for. Each decision logs the deciding quote's
age and the points its side scored in the 2 minutes before the stamp, so the
books' own lag (docs/nba_models_2026.md 7.3) is visible pick by pick.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402
import models.nba_live_ingame as M  # noqa: E402
from nba_live import espn as E  # noqa: E402
from nba_live import odds as O  # noqa: E402
from nba_live import state as S  # noqa: E402
from scripts import nba_ingame_data as D  # noqa: E402

log = logging.getLogger("nba_live.gameday")

SPORT = "NBA"
_ET = ZoneInfo("America/New_York")
POLL_SEC = float(os.environ.get("NBA_LIVE_INGAME_POLL_SEC", "30"))
TICK_SECOND = int(os.environ.get("NBA_LIVE_INGAME_TICK_SECOND", "3336"))     # hh:55:36 UTC
TICK_WINDOW_SEC = float(os.environ.get("NBA_LIVE_INGAME_TICK_WINDOW_SEC", "240"))
SETTLE_SEC = float(os.environ.get("NBA_LIVE_INGAME_SETTLE_SEC", "30"))
IDLE_EXIT_PASSES = int(os.environ.get("NBA_LIVE_INGAME_IDLE_EXIT_PASSES", "3"))
FEED_FAIL_EXIT_PASSES = int(os.environ.get("NBA_LIVE_INGAME_FEED_FAIL_EXIT_PASSES", "60"))

DECISIONS_TABLE = "nba_live_ingame_decisions"
DECISIONS_COLS = ("game_id", "model_id", "market", "phase", "season", "tick_at", "served_at",
                  "decided_at", "bet", "reason", "side", "book", "line", "price", "stamp", "ev",
                  "p_win", "p_push", "mean", "sd", "p_home", "mu_pre", "period", "clock_s",
                  "h_pts", "a_pts", "offers", "best_ev", "dk_price", "detail")
DECISIONS_DDL = """
CREATE TABLE IF NOT EXISTS nba_live_ingame_decisions (
    game_id     TEXT NOT NULL,
    model_id    TEXT NOT NULL,
    market      TEXT NOT NULL,
    phase       TEXT NOT NULL,
    season      INTEGER,
    tick_at     TIMESTAMPTZ,
    served_at   TIMESTAMPTZ,
    decided_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    bet         BOOLEAN NOT NULL,
    reason      TEXT NOT NULL,
    side        TEXT,
    book        TEXT,
    line        REAL,
    price       REAL,
    stamp       TIMESTAMPTZ,
    ev          REAL,
    p_win       REAL,
    p_push      REAL,
    mean        REAL,
    sd          REAL,
    p_home      REAL,
    mu_pre      REAL,
    period      SMALLINT,
    clock_s     REAL,
    h_pts       INTEGER,
    a_pts       INTEGER,
    offers      INTEGER,
    best_ev     REAL,
    dk_price    REAL,
    detail      TEXT,
    PRIMARY KEY (game_id, model_id)
)
"""
_INSERT_DECISION = (
    f"INSERT INTO {DECISIONS_TABLE} ({', '.join(c for c in DECISIONS_COLS if c != 'decided_at')}) "
    f"VALUES ({', '.join('%(' + c + ')s' for c in DECISIONS_COLS if c != 'decided_at')}) "
    "ON CONFLICT (game_id, model_id) DO NOTHING RETURNING game_id")

PICK_COLS = ("game_id", "model_id", "sport", "game_date", "game_time", "pick_side", "pick_label",
             "model_probability", "model_probability_cal", "dk_implied_prob", "edge", "dk_odds",
             "scored_line", "kelly_fraction", "recommended_bet", "bankroll_at_pick", "signal_type",
             "confidence_tier", "dk_bet_link", "line_book", "is_live", "inning_at_pick",
             "score_diff_at_pick", "decision_book", "decision_odds", "decision_implied_prob",
             "decision_edge", "best_book", "best_odds", "best_implied_prob", "best_edge",
             "best_bet_link", "downgrade_reason")
# Its own column list, not models.scorer._insert_picks: that one stamps
# model_probability_cal from the promoted map, and these models decide on their
# own number (config.MODELS_ON_OWN_PROBABILITY).
_INSERT_PICK = (f"INSERT INTO picks ({', '.join(PICK_COLS)}) "
                f"VALUES ({', '.join('%(' + c + ')s' for c in PICK_COLS)}) "
                "ON CONFLICT DO NOTHING RETURNING pick_id")


def implied(price) -> float:
    a = float(price)
    return 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)


# ── the tick ─────────────────────────────────────────────────────────────────

class TickClock:
    """One tick an hour, at `second` seconds past each UTC hour, open for
    `window` seconds. A tick is consumed once (mark), whether it decided,
    found nothing to decide or was refused; an odds call that failed leaves
    it open for the next pass inside the window."""

    def __init__(self, second: int = TICK_SECOND, window: float = TICK_WINDOW_SEC):
        self.second, self.window = int(second), float(window)
        self._done: set = set()

    def instant(self, now: datetime) -> pd.Timestamp:
        t = pd.Timestamp(now).tz_convert("UTC") if pd.Timestamp(now).tzinfo else pd.Timestamp(now, tz="UTC")
        base = (t - pd.Timedelta(seconds=self.second)).floor("h")
        return base + pd.Timedelta(seconds=self.second)

    def due(self, now: datetime) -> pd.Timestamp | None:
        T = self.instant(now)
        age = (pd.Timestamp(now) - T).total_seconds()
        if 0 <= age < self.window and T not in self._done:
            return T
        return None

    def mark(self, T) -> None:
        self._done.add(pd.Timestamp(T))


# ── a game ───────────────────────────────────────────────────────────────────

@dataclass
class Game:
    game_id: str
    espn_id: int
    home: str
    away: str
    season: int
    game_date: str
    tip: datetime
    mu_pre: float | None = None
    prior_note: str = ""
    decided: set = field(default_factory=set)
    top: pd.DataFrame | None = None
    swapped: bool | None = None
    abbr_sides: dict = field(default_factory=dict)   # ESPN abbreviation -> 'H' / 'A' (ours)

    @property
    def open_models(self) -> list[str]:
        return [m for m in M.MODEL_IDS if m not in self.decided]

    @property
    def meta(self) -> dict:
        return {"season": self.season, "game_date": self.game_date, "tip": self.tip}


# ── the database, behind one seam ────────────────────────────────────────────

class Store:
    """Every read and write the loop makes. DryRunStore keeps the reads and
    turns every write into a log line; the tests use an in-memory one."""

    def __init__(self, conn_factory=None):
        self._factory = conn_factory
        self._conn = None
        self._resolver = None

    def conn(self):
        if self._conn is None:
            if self._factory is None:
                from data.db import get_connection, use_poller_session
                use_poller_session()
                self._factory = get_connection
            self._conn = self._factory()
        return self._conn

    def _release(self):
        from data.db import release_read
        try:
            release_read(self.conn())
        except Exception:                             # noqa: BLE001
            pass

    def recycle(self):
        c, self._conn = self._conn, None
        if c is not None:
            try:
                c.rollback()
                self._conn = c
            except Exception:                         # noqa: BLE001
                try:
                    c.close()
                except Exception:                     # noqa: BLE001
                    pass

    # reads
    def resolve_game(self, home: str, away: str, et_date: str) -> dict | None:
        """The one `games` row for ESPN's teams on the ET date (either way
        round, +/- 1 day), with its schedule type and tip, or None."""
        d = datetime.fromisoformat(et_date).date()
        try:
            rows = self.conn().execute("""
                SELECT g.game_id, g.home_team, g.away_team, g.game_date, g.season,
                       g.commence_time, s.commence_time, s.game_type
                FROM games g LEFT JOIN nba_schedule s ON s.game_id = g.game_id
                WHERE g.sport = 'NBA' AND g.game_date BETWEEN %s AND %s
                  AND ((g.home_team = %s AND g.away_team = %s) OR (g.home_team = %s AND g.away_team = %s))
            """, ((d - timedelta(days=1)).isoformat(), (d + timedelta(days=1)).isoformat(),
                  home, away, away, home)).fetchall()
            if len(rows) != 1:
                if rows:
                    log.warning("%s @ %s on %s: %d games rows - refusing", away, home, et_date, len(rows))
                return None
            gid, h, a, gd, season, g_ct, s_ct, game_type = rows[0]
            days = self.conn().execute(
                "SELECT DISTINCT season, game_date, game_type FROM nba_schedule WHERE season = %s",
                (int(season),)).fetchall()
            return {"game_id": gid, "home": h, "away": a, "game_date": str(gd)[:10],
                    "season": int(season), "g_ct": g_ct, "s_ct": s_ct, "game_type": game_type,
                    "days": days}
        finally:
            self._release()

    def pinnacle_spread_rows(self, game_id: str, tip: datetime) -> list:
        """Pinnacle's pre-game spread rows for the game, stored by the refresh
        passes, in the 36 hours before tip (snapshot_at is TEXT; the bound
        lets idx_odds_book_snap do the work)."""
        lo = (tip - timedelta(hours=36)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        try:
            return self.conn().execute("""
                SELECT game_id, bookmaker, market, snapshot_type, snapshot_at, created_at,
                       spread_home, home_price, away_price
                FROM odds
                WHERE game_id = %s AND market = 'spreads' AND bookmaker = 'pinnacle'
                  AND snapshot_type = 'open' AND snapshot_at >= %s
            """, (game_id, lo)).fetchall()
        finally:
            self._release()

    def decided_models(self, game_id: str) -> set[str]:
        """Models with a ledger row for the game, or with any BET on it."""
        try:
            out = set()
            if self.ledger_exists():
                out |= {r[0] for r in self.conn().execute(
                    f"SELECT model_id FROM {DECISIONS_TABLE} WHERE game_id = %s", (game_id,)).fetchall()}
            out |= {r[0] for r in self.conn().execute("""
                SELECT DISTINCT model_id FROM picks
                WHERE game_id = %s AND model_id = ANY(%s) AND signal_type = 'BET'
            """, (game_id, list(M.MODEL_IDS))).fetchall()}
            return out
        finally:
            self._release()

    def ledger_exists(self) -> bool:
        return bool(self.conn().execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' "
            "AND table_name = %s", (DECISIONS_TABLE,)).fetchone())

    def prior_minutes(self, box: list[dict], season: int, before: str) -> dict:
        """athlete_id -> minutes per game in his earlier games this season
        (else last season's average, else 0), from nba_player_game_log, his
        ESPN id resolved as the results step resolves it."""
        from data.ingestors.nba_results_ingestor import PlayerResolver
        try:
            if self._resolver is None:
                xwalk = self.conn().execute("""
                    SELECT source_athlete_id, player_id FROM player_positions
                    WHERE sport = 'NBA' AND source_athlete_id IS NOT NULL
                """).fetchall()
                since = (datetime.fromisoformat(before) - timedelta(days=400)).date().isoformat()
                names = self.conn().execute("""
                    SELECT DISTINCT player_id, player_name, team FROM nba_player_game_log
                    WHERE game_date >= %s
                """, (since,)).fetchall()
                self._resolver = PlayerResolver({str(e): str(p) for e, p in xwalk}, names)
            ids = {}
            for r in box:
                if r.get("starter"):
                    pid, _ = self._resolver.resolve(str(r["athlete_id"]), r.get("name"), r.get("team"))
                    ids[int(r["athlete_id"])] = pid
            if not ids:
                return {}
            rows = self.conn().execute("""
                SELECT player_id, season, AVG(minutes) FILTER (WHERE minutes > 0)
                FROM nba_player_game_log
                WHERE player_id = ANY(%s) AND season IN (%s, %s) AND game_date < %s
                GROUP BY player_id, season
            """, (list(set(ids.values())), int(season), int(season) - 1, before)).fetchall()
            by = {(str(p), int(s)): (None if m is None else float(m)) for p, s, m in rows}
            out = {}
            for aid, pid in ids.items():
                cur, last = by.get((str(pid), int(season))), by.get((str(pid), int(season) - 1))
                out[aid] = cur if cur is not None else (last if last is not None else 0.0)
            return out
        finally:
            self._release()

    def bankroll(self) -> float:
        from models.scorer import _get_current_bankroll
        try:
            return float(_get_current_bankroll(self.conn()))
        finally:
            self._release()

    def used_today(self) -> int:
        try:
            return O.used_today(self.conn())
        except Exception:                             # noqa: BLE001
            self.recycle()
            return 0

    def latest_remaining(self):
        try:
            return O.latest_remaining(self.conn())
        finally:
            self._release()

    def unsettled_bet_dates(self) -> set[str]:
        since = (datetime.now(timezone.utc) - timedelta(days=4)).date().isoformat()
        try:
            rows = self.conn().execute("""
                SELECT DISTINCT game_date FROM picks
                WHERE model_id = ANY(%s) AND is_live = TRUE AND signal_type = 'BET'
                  AND result IS NULL AND game_date >= %s
            """, (list(M.MODEL_IDS), since)).fetchall()
            return {str(r[0])[:10] for r in rows}
        finally:
            self._release()

    # writes
    def ensure_ledger(self) -> None:
        from data.ddl_guard import API_ROLES, lock_down, schema_is_current
        c = self.conn()
        if schema_is_current(c, DECISIONS_TABLE, columns=DECISIONS_COLS, rls=True, revoked_from=API_ROLES):
            return
        c.execute(DECISIONS_DDL)
        lock_down(c, DECISIONS_TABLE)
        c.commit()

    def write_decision(self, row: dict, pick: dict | None) -> tuple[bool, bool]:
        """The ledger row and its bet in ONE transaction, under the model's
        lock, re-checked inside it. -> (decision written, bet written)."""
        from scripts.nfl_wind_publisher import _lock_model
        c = self.conn()
        try:
            _lock_model(c, row["model_id"])
            held = c.execute("""
                SELECT 1 FROM picks WHERE game_id = %s AND model_id = %s AND signal_type = 'BET' LIMIT 1
            """, (row["game_id"], row["model_id"])).fetchone()
            if held:
                c.rollback()
                return False, False
            if not c.execute(_INSERT_DECISION, row).fetchone():
                c.rollback()
                return False, False
            wrote = bool(pick is not None and c.execute(_INSERT_PICK, pick).fetchone())
            c.commit()
            return True, wrote
        except Exception:
            try:
                c.rollback()
            except Exception:                         # noqa: BLE001
                pass
            raise

    def record_prices(self, rows: list[dict], known: set[str]) -> int:
        from data.ingestors.live_price_log import record_live_prices
        return record_live_prices(self.conn(), rows, known_game_ids=known)

    def record_fetch(self, credits: int, fired_at: datetime) -> None:
        from data.ingestors.odds_quota import persist_quota
        c = self.conn()
        try:
            O.record_fetch(c, credits, fired_at)
            c.commit()
        except Exception as exc:                      # noqa: BLE001
            log.warning("credit telemetry failed (non-fatal): %s", exc)
            self.recycle()
        try:
            persist_quota(self.conn())
        except Exception:                             # noqa: BLE001
            pass

    def notify(self, target_date: str) -> None:
        """Push, then Discord live: both dedupe on their ledgers, neither may
        break the loop."""
        try:
            from tracking.push_notifier import notify_live_signals
            notify_live_signals(target_date=target_date, dry_run=False)
        except Exception as exc:                      # noqa: BLE001
            log.error("live push failed (non-fatal): %s", exc)
        try:
            from tracking.discord_notifier import notify_discord_live
            notify_discord_live(target_date=target_date, dry_run=False)
        except Exception as exc:                      # noqa: BLE001
            log.error("live Discord post failed (non-fatal): %s", exc)

    def close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:                         # noqa: BLE001
                pass


class DryRunStore(Store):
    """Reads as the real store does; writes nothing and posts nothing."""

    def ensure_ledger(self) -> None:
        log.info("[dry-run] would ensure %s", DECISIONS_TABLE)

    def write_decision(self, row, pick):
        log.info("[dry-run] would write decision %s %s %s%s", row["game_id"], row["model_id"],
                 row["reason"], f" and BET {pick['pick_label']} {pick['decision_odds']:+.0f}" if pick else "")
        return True, pick is not None

    def record_prices(self, rows, known) -> int:
        log.info("[dry-run] would store %d in-play quotes", len(rows))
        return 0

    def record_fetch(self, credits, fired_at) -> None:
        log.info("[dry-run] would record %s credits", credits)

    def notify(self, target_date) -> None:
        log.info("[dry-run] would announce %s", target_date)


# ── the prior and the pick ───────────────────────────────────────────────────

def pregame_prior(rows: list, game: Game, art: dict) -> tuple[float | None, str]:
    """mu_pre from Pinnacle's last pre-tip coherent spread (the harness's
    pinnacle_close on the live odds rows, fetch instant = created_at), solved
    through the artifact's distribution for the game's season."""
    from scripts import nba_game_harness as H
    if not rows:
        return None, "no Pinnacle pre-game spread stored"
    o = pd.DataFrame(rows, columns=["game_id", "bookmaker", "market", "snapshot_type", "snapshot_at",
                                    "created_at", "spread_home", "home_price", "away_price"])
    o["snapshot_at"] = pd.to_datetime(o["snapshot_at"], utc=True, format="mixed", errors="coerce")
    o["fetch_at"] = pd.to_datetime(o["created_at"], utc=True, format="mixed", errors="coerce")
    for c in ("spread_home", "home_price", "away_price"):
        o[c] = pd.to_numeric(o[c], errors="coerce")
    o["total_line"] = o["over_price"] = o["under_price"] = np.nan
    o = o.assign(season=game.season, game_date=game.game_date, tip=pd.Timestamp(game.tip))
    q = H.frame_quotes(o.dropna(subset=["snapshot_at", "fetch_at"]))
    close = H.pinnacle_close(H.Data(games=pd.DataFrame(), quotes=q, fetches=pd.DataFrame()))
    close = close[close["market"] == "spreads"]
    if close.empty:
        return None, "no coherent Pinnacle pre-game spread before tip"
    mu = M.solve_prior(close, lambda s: M.artifact_prior_dist(art, s))
    r = close.iloc[0]
    return float(mu["mu_pre"].iloc[0]), (f"Pinnacle close {float(r['close_line']):+g} "
                                         f"(no-vig home {float(r['close_fa']):.3f}) at {r['close_at']}")


def decision_row(d: M.Decision, tick_at, detail: dict) -> dict:
    def ts(v):
        return None if v is None or (isinstance(v, float) and np.isnan(v)) else pd.Timestamp(v).isoformat()
    return {"game_id": d.game_id, "model_id": d.model_id, "market": d.market, "phase": d.phase,
            "season": d.season, "tick_at": ts(tick_at), "served_at": ts(d.served_at),
            "bet": bool(d.bet), "reason": d.reason, "side": d.side, "book": d.book, "line": d.line,
            "price": d.price, "stamp": ts(d.stamp), "ev": d.ev, "p_win": d.p_win, "p_push": d.p_push,
            "mean": d.mean, "sd": d.sd, "p_home": d.p_home, "mu_pre": d.mu_pre, "period": d.period,
            "clock_s": d.clock_s, "h_pts": d.h_pts, "a_pts": d.a_pts, "offers": d.offers,
            "best_ev": d.best_ev, "dk_price": d.dk_price, "detail": json.dumps(detail, default=str)}


def build_pick(d: M.Decision, game: Game, bankroll: float, links: dict) -> dict:
    """One `picks` row from one BET decision. The label quotes the SIDE's own
    number (models.nba_live_ingame.pick_label); scored_line is the HOME
    number (CLAUDE.md section 4)."""
    from models.scorer import _pause_note, quarter_kelly
    price = float(d.price)
    dec_imp = implied(price)
    edge = round(d.p_win - dec_imp, 4)
    dk = d.dk_price
    dk_imp = implied(dk) if dk is not None else None
    at_dk = d.book == "draftkings"
    kf, rec = quarter_kelly(d.p_win, dec_imp, bankroll)
    link = links.get((d.game_id, d.market, d.book, d.side))
    dk_link = links.get((d.game_id, d.market, "draftkings", d.side))
    return {
        "game_id": d.game_id, "model_id": d.model_id, "sport": SPORT,
        "game_date": game.game_date,
        "game_time": pd.Timestamp(game.tip).isoformat() if game.tip is not None else None,
        "pick_side": d.side, "pick_label": M.pick_label(d, game.home, game.away),
        "model_probability": round(d.p_win, 4), "model_probability_cal": round(d.p_win, 4),
        "dk_implied_prob": round(dk_imp, 4) if dk is not None else 0.0,
        "edge": round(d.p_win - dk_imp, 4) if dk is not None else 0.0,
        "dk_odds": dk, "scored_line": d.line,
        "kelly_fraction": kf, "recommended_bet": rec, "bankroll_at_pick": bankroll,
        "signal_type": "BET", "confidence_tier": "MED",
        "dk_bet_link": dk_link if dk is not None else None,
        "line_book": None if dk is not None else d.book,
        "is_live": True, "inning_at_pick": d.period,
        "score_diff_at_pick": (None if d.h_pts is None or d.a_pts is None else int(d.h_pts - d.a_pts)),
        "decision_book": d.book, "decision_odds": price,
        "decision_implied_prob": round(dec_imp, 4), "decision_edge": edge,
        "best_book": None if at_dk else d.book, "best_odds": None if at_dk else price,
        "best_implied_prob": None if at_dk else round(dec_imp, 4),
        "best_edge": None if at_dk else edge, "best_bet_link": None if at_dk else link,
        "downgrade_reason": _pause_note(d.model_id),
    }


def pick_refusal(pick: dict, d: M.Decision, game: Game) -> str | None:
    """Why this bet may not be written, or None: the platform's own gates,
    read at call time, and the label read back against its fields."""
    from tracking.pick_integrity import pick_problems
    if d.model_id in getattr(config, "PAUSED_MODELS", ()):
        return "model is paused (config.PAUSED_MODELS)"
    if d.model_id in getattr(config, "RETIRED_MODELS", ()):
        return "model is retired"
    floor = config.min_odds_for(d.model_id)
    if floor is not None and d.price < floor:
        return f"price {d.price:+.0f} under the floor {floor:+.0f}"
    problems = pick_problems(pick["pick_label"], pick["pick_side"], pick["scored_line"], d.model_id,
                             game.home, game.away)
    if problems:
        return "label mismatch: " + "; ".join(problems)
    return None


# ── the loop ─────────────────────────────────────────────────────────────────

class Loop:
    def __init__(self, store: Store, espn: E.EspnClient, feed: O.LiveOddsFeed, art: dict, *,
                 now=None, sleep=None, clock: TickClock | None = None, settle: float = SETTLE_SEC,
                 dry_run: bool = False):
        self.store, self.espn, self.feed, self.art = store, espn, feed, art
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.sleep = sleep or time.sleep
        self.clock = clock or TickClock()
        self.settle = float(settle)
        self.dry_run = dry_run
        self.games: dict[int, Game | None] = {}       # ESPN id -> our game (None: not ours)
        self.seen: set = set()
        self.models: dict[int, M.StateModel] = {}
        self.bets_written = 0
        self.decisions_written = 0
        self.bet_dates: set[str] = set()
        self.log: list[dict] = []                     # every decision this process made

    # -- context
    def model_for(self, season: int) -> M.StateModel | None:
        if season not in self.models:
            try:
                self.models[season] = M.live_model(self.art, season)
            except ValueError as exc:
                log.error("%s", exc)
                self.models[season] = None
        return self.models[season]

    def game_for(self, ev: E.EspnEvent) -> Game | None:
        if ev.event_id in self.games:
            return self.games[ev.event_id]
        from data.ingestors.nba_espn_box import et_date, nba_team
        from models.nba_prop_market import tip_of
        from models.nba_total_luck import regular_season
        g = None
        home, away = nba_team(ev.home_abbr, ev.home_name), nba_team(ev.away_abbr, ev.away_name)
        day = et_date(ev.date)
        if ev.season_type != E.REGULAR_SEASON:
            log.info("ESPN %s %s @ %s: season type %s is not the regular season - not priced",
                     ev.event_id, ev.away_abbr, ev.home_abbr, ev.season_type)
        elif home and away and day:
            row = self.store.resolve_game(home, away, day)
            if row is not None:
                frame = pd.DataFrame([{"game_id": row["game_id"], "season": row["season"],
                                       "game_date": row["game_date"], "game_type": row["game_type"]}])
                days = pd.DataFrame(row["days"], columns=["season", "game_date", "game_type"])
                if regular_season(frame, days).empty:
                    log.info("%s is not a regular-season game (%s) - not priced", row["game_id"],
                             row["game_type"])
                else:
                    tip = tip_of(row["s_ct"], row["g_ct"])
                    g = Game(row["game_id"], int(ev.event_id), row["home"], row["away"], row["season"],
                             row["game_date"], tip)
                    g.abbr_sides = _abbr_sides_for(ev, g)
                    g.decided = self.store.decided_models(g.game_id)
                    mu, note = pregame_prior(self.store.pinnacle_spread_rows(g.game_id, tip), g, self.art)
                    g.mu_pre, g.prior_note = mu, note
                    log.info("%s: prior %s (%s); already decided: %s", g.game_id,
                             "none" if mu is None else f"{mu:+.2f}", note, sorted(g.decided) or "none")
        self.games[ev.event_id] = g
        return g

    # -- one pass
    def live_events(self) -> list[E.EspnEvent] | None:
        now = self.now()
        et = now.astimezone(_ET)
        days = [et.date()] + ([et.date() - timedelta(days=1)] if et.hour < 6 else [])
        out, answered = [], False
        for d in days:
            evs = self.espn.scoreboard(d.strftime("%Y%m%d"))
            if evs is None:
                continue
            answered = True
            out += [e for e in evs if e.state == "in"]
        return out if answered else None

    def pass_once(self) -> dict:
        """One pass: who is in play, and the tick if it is due."""
        evs = self.live_events()
        if evs is None:
            return {"live": None}
        live = []
        for ev in evs:
            try:
                g = self.game_for(ev)
            except Exception as exc:                  # noqa: BLE001
                log.error("context for ESPN %s failed: %s", ev.event_id, exc)
                self.store.recycle()
                self.games.pop(ev.event_id, None)
                continue
            if g is not None:
                live.append(g)
        out = {"live": len(evs), "ours": len(live), "tick": None}
        T = self.clock.due(self.now())
        if T is not None:
            out["tick"] = self.tick(T, live)
        return out

    def tick(self, T, live: list[Game]) -> dict:
        res = {"T": str(T), "fetched": False, "decisions": 0, "bets": 0}
        due = [g for g in live if g.open_models and g.mu_pre is not None
               and self.model_for(g.season) is not None]
        for g in live:
            if g.mu_pre is None and g.open_models:
                log.info("%s: no pre-game prior (%s) - not priced", g.game_id, g.prior_note)
        if not due:
            self.clock.mark(T)
            res["reason"] = "nothing to decide"
            return res
        why = self.feed.refusal(self.store.used_today())
        if why:
            log.error("tick %s: not fetching - %s", T, why)
            self.clock.mark(T)
            res["reason"] = why
            return res
        events, served_at = self.feed.fetch()
        if events is None:
            res["reason"] = "odds fetch failed"
            return res                                # the window stays open: next pass retries
        self.clock.mark(T)
        res["fetched"] = True
        self.store.record_fetch(self.feed.last_credits or 0, served_at)
        known = {g.game_id for g in live}
        odds_rows = O.parse_events(events, served_at, known)
        # Never earlier than the newest stamp the response carries, as the lab
        # set served_at (scripts/nba_ingame_data.py, SERVED).
        newest = pd.to_datetime([r["snapshot_at"] for r in odds_rows], utc=True, format="mixed",
                                errors="coerce").max() if odds_rows else None
        if newest is not None and not pd.isna(newest) and newest > pd.Timestamp(served_at):
            served_at = newest.to_pydatetime()
        links = {}
        for r in odds_rows:
            for side in ("home", "away"):
                if r.get(f"{side}_link"):
                    links[(r["game_id"], r["market"], r["bookmaker"], side)] = r[f"{side}_link"]
        if self.settle > 0:
            self.sleep(self.settle)
        frames = []
        for g in due:
            rows = self.rows_for(g, odds_rows, T, served_at)
            if rows is not None and len(rows):
                frames.append(rows)
        try:
            self.store.record_prices(odds_rows, known)
        except Exception as exc:                      # noqa: BLE001
            log.warning("in-play quote log failed (non-fatal): %s", exc)
            self.store.recycle()
        if not frames:
            res["reason"] = "no in-play quotes"
            return res
        rows = pd.concat(frames, ignore_index=True)
        prior = pd.DataFrame([{"game_id": g.game_id, "mu_pre": g.mu_pre} for g in due])
        decided = {(g.game_id, m) for g in due for m in g.decided}
        by_game = {g.game_id: g for g in due}
        for season, part in rows.groupby("season"):
            model = self.model_for(int(season))
            ds = M.decide(part, prior, model, decided=decided)
            for d in ds:
                self.record(d, by_game[d.game_id], T, served_at, links, part)
                res["decisions"] += 1
                res["bets"] += int(d.bet)
        return res

    def rows_for(self, g: Game, odds_rows: list[dict], T, served_at) -> pd.DataFrame | None:
        """One game's rows at this tick, from its summary read now."""
        j = self.espn.summary(g.espn_id)
        if j is None:
            log.warning("%s: no ESPN summary this tick - not decided", g.game_id)
            return None
        status = E.summary_status(j)
        records = E.records_from_summary(j)
        if g.swapped is None:
            g.swapped = S.sides_swapped(records, g.espn_id, g.home, g.away)
            if g.swapped is None:
                log.error("%s: ESPN's teams are not this game's - not priced", g.game_id)
                return None
        plays = S.plays_from_records(records, g.espn_id, g.game_id, g.season, swapped=g.swapped)
        plays, wild = D.drop_wild_wallclocks(plays)
        if wild:
            log.error("%s: a play is logged more than %.0f h from the rest - the lab left such games "
                      "out; not decided", g.game_id, D.WILD_HOURS)
            return None
        if g.top is None or g.top.empty:
            box = E.starters_from_summary(j)
            side_of = g.abbr_sides
            starters = [dict(r, team=self._team(r, side_of, g)) for r in box if r["starter"]]
            if len(starters) >= 6:
                pm = self.store.prior_minutes(starters, g.season, g.game_date)
                g.top = S.top_players(g.game_id, g.espn_id, starters, side_of, pm)
        quotes = S.quote_frame([r for r in odds_rows if r["game_id"] == g.game_id],
                               {g.game_id: g.meta}, T, pd.Timestamp(served_at), O.BOOKS, self.seen)
        self.seen |= set(zip(quotes["game_id"], quotes["market"], quotes["book"], quotes["stamp"]))
        if quotes.empty:
            return None
        rows, _ = S.tick_rows(quotes, plays, g.top if g.top is not None else pd.DataFrame(),
                              final=bool(status.get("completed")))
        return rows

    @staticmethod
    def _team(r, side_of, g) -> str:
        return g.home if side_of.get(r["team_abbr"]) == D.HOME else g.away

    def record(self, d: M.Decision, g: Game, T, served_at, links: dict, part: pd.DataFrame) -> None:
        detail = {"prior": g.prior_note, "offers": d.offers, "best_ev": d.best_ev,
                  "quote_age_s": (None if d.stamp is None else
                                  (pd.Timestamp(served_at) - pd.Timestamp(d.stamp)).total_seconds()),
                  "pts_side_last_120s": d.pts120_side, "tick_at": str(T)}
        pick = None
        if d.bet:
            bankroll = 0.0 if self.dry_run else self.store.bankroll()
            pick = build_pick(d, g, bankroll, links)
            why = pick_refusal(pick, d, g)
            if why:
                log.warning("BET %s on %s not written: %s", d.model_id, d.game_id, why)
                detail["refused"] = why
                pick = None
        row = decision_row(d, T, detail)
        try:
            wrote_d, wrote_b = self.store.write_decision(row, pick)
        except Exception as exc:                      # noqa: BLE001
            log.error("write failed for %s %s (non-fatal): %s", d.game_id, d.model_id, exc)
            self.store.recycle()
            return
        if wrote_d:
            g.decided.add(d.model_id)
            self.decisions_written += 1
            self.log.append({**row, "pick_label": pick["pick_label"] if pick else None})
        if wrote_b:
            self.bets_written += 1
            self.bet_dates.add(g.game_date)
        log.info("DECIDED %s %s %s at %s: %s%s", d.model_id, d.game_id, d.phase, T, d.reason,
                 f" -> {pick['pick_label']} {d.price:+.0f} @{d.book} ev {d.ev:.3f}" if pick else "")


def _abbr_sides_for(ev: E.EspnEvent, g: Game) -> dict:
    """ESPN abbreviation -> our side, from the event's own home/away and the
    swap (a neutral-site game ESPN lists the other way round)."""
    from data.ingestors.nba_espn_box import nba_team
    out = {}
    for abbr, name in ((ev.home_abbr, ev.home_name), (ev.away_abbr, ev.away_name)):
        t = nba_team(abbr, name)
        if t == g.home:
            out[abbr] = D.HOME
        elif t == g.away:
            out[abbr] = D.AWAY
    return out


def main(argv=None) -> int:
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("nba-live-ingame")
    except Exception:                                 # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="NBA in-play game-state loop")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=float, default=POLL_SEC)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    art = M.load_artifact()
    log.info("artifact %s: season %s, %s training states, built %s; models %s", M.ARTIFACT_PATH,
             art["model"]["S"], art["model"]["n_train"], art.get("built_at"), ", ".join(M.MODEL_IDS))
    store = DryRunStore() if a.dry_run else Store()
    if not a.dry_run:
        store.ensure_ledger()
    feed = O.LiveOddsFeed(remaining=store.latest_remaining())
    loop = Loop(store, E.EspnClient(), feed, art, dry_run=a.dry_run)
    if not a.dry_run:
        try:
            loop.bet_dates |= store.unsettled_bet_dates()
        except Exception as exc:                      # noqa: BLE001
            log.warning("could not read standing BETs (non-fatal): %s", exc)
            store.recycle()
    idle = fails = 0
    last_notify = None
    try:
        while True:
            started = time.monotonic()
            out = loop.pass_once()
            if out["live"] is None:
                fails += 1
                if fails >= FEED_FAIL_EXIT_PASSES:
                    log.error("ESPN unreachable for %d passes - exiting", fails)
                    return 1
            else:
                fails = 0
                idle = idle + 1 if not out["ours"] else 0
            if out.get("tick"):
                log.info("tick %s", out["tick"])
            wrote = bool(out.get("tick") and out["tick"].get("bets"))
            if not a.dry_run and loop.bet_dates and (wrote or last_notify is None
                                                     or time.monotonic() - last_notify >= 300):
                for d_ in sorted(loop.bet_dates):
                    store.notify(d_)
                last_notify = time.monotonic()
            if a.once or idle >= IDLE_EXIT_PASSES:
                log.info("exiting: %s; %d decisions, %d BETs written; ESPN calls %d, odds credits %d",
                         "--once" if a.once else f"no NBA game in progress for {idle} passes",
                         loop.decisions_written, loop.bets_written, loop.espn.calls,
                         loop.feed.credits_used)
                return 0
            time.sleep(max(0.0, a.interval - (time.monotonic() - started)))
    finally:
        store.close()


if __name__ == "__main__":
    sys.exit(main())
