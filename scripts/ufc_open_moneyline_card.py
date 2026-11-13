"""The UFC opening-price moneyline card (models/ufc_open_moneyline.py).

Once a day, on the noon-UTC run: each upcoming UFC fight still at least a
week out is priced at the latest stored pull where Pinnacle and a deciding
book both quote it, fetched within ten minutes of each other. The card runs
hourly; the other hours only close fights that reached the week-out mark. The first pull that clears the
model's EV floor is the bet, and the fight is decided: the bet is never
re-decided (CLAUDE.md section 1c). A fight that reaches a week out without
clearing is decided then as a NONE row at its last pull before that mark, so
every priced fight sits in the graded universe.

One fight, one decision. The feed stores a fight under two ids (the fighters
in either order, and an Eastern and a UTC date), so the card keys its ledger
on the fight (both slugs and the card date), writes the pick on the id whose
odds were fetched last, and treats a pick on either id as the decision.

A fight is held while either fighter has an earlier fight not yet in the
fight log (data/schedule_context), and while either fighter cannot be
placed on his ufcstats record (data/ufc_identity): the ratings would be
another man's, or out of date.

    python -m scripts.ufc_open_moneyline_card            # decide and print, write nothing
    python -m scripts.ufc_open_moneyline_card --publish
RUN_UFC_OPEN_MONEYLINE=0 turns the card off.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from loguru import logger

import config
from data.anon_readable import API_ROLES, lock_down
from data.db import get_connection
from data.ddl_guard import schema_is_current
from models import ufc_open_moneyline as om
from models import ufc_ratings as R
from tracking.pick_integrity import pick_problems

MODEL_ID = om.MODEL_ID
SPORT = om.SPORT
FRESH_H = 3.0            # a pull older than this is not a pull
# The feed dates an unscheduled fight December 31 or January 1 (2026-11-13:
# Topuria-Gaethje, Masvidal-McGregor, Chimaev-Strickland and others). None of
# the 2,457 UFC fights of the bought 2020-2026 history was listed on either
# day, so the backtest never bet one; the card does not either.
PLACEHOLDER_DAYS = ("12-31", "01-01")
HORIZON_DAYS = 120       # fights further out than this are not read
SHARP = "pinnacle"


def enabled() -> bool:
    return os.environ.get("RUN_UFC_OPEN_MONEYLINE", "1").strip() not in ("0", "false", "no")


DECISIONS_TABLE = "ufc_open_moneyline_decisions"
DECISIONS_COLS = ("fight_key", "game_id", "decided_at", "quote_at", "status", "side", "book",
                  "price", "prob", "ev", "opinion", "n_books", "quotes", "detail")
DECISIONS_DDL = """
CREATE TABLE IF NOT EXISTS ufc_open_moneyline_decisions (
    fight_key   TEXT PRIMARY KEY,
    game_id     TEXT NOT NULL,
    decided_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    quote_at    TIMESTAMPTZ,
    status      TEXT NOT NULL,
    side        TEXT,
    book        TEXT,
    price       REAL,
    prob        REAL,
    ev          REAL,
    opinion     REAL,
    n_books     INTEGER,
    quotes      TEXT,
    detail      TEXT
)
"""
_INSERT_DECISION = (
    f"INSERT INTO {DECISIONS_TABLE} ({', '.join(c for c in DECISIONS_COLS if c != 'decided_at')}) "
    f"VALUES ({', '.join('%(' + c + ')s' for c in DECISIONS_COLS if c != 'decided_at')}) "
    "ON CONFLICT (fight_key) DO NOTHING RETURNING fight_key")
# A pull below the cut decides nothing: the next day's pull may clear. A fight
# is decided by a bet, or at the week-out mark (its last pull before it, or
# none).
FINAL = ("bets", "window_closed", "no_window")
# The hour (UTC) whose run decides bets: the backtest bought one pull a day,
# at noon UTC, and a first-clearing lock checked hourly would fire earlier
# and more often than the record it was graded on.
DECIDE_HOUR_UTC = 12


def bets_decided_at(now: datetime) -> bool:
    """Only the noon-UTC run decides bets (DECIDE_HOUR_UTC)."""
    return now.astimezone(timezone.utc).hour == DECIDE_HOUR_UTC


def ensure_decisions_table(conn) -> None:
    if not schema_is_current(conn, DECISIONS_TABLE, columns=DECISIONS_COLS, rls=True,
                             revoked_from=API_ROLES):
        conn.execute(DECISIONS_DDL)
        lock_down(conn, DECISIONS_TABLE)
        conn.commit()


def _z(t: datetime) -> str:
    """odds.snapshot_at's own text shape (every UFC row, 2026-11-13: 20
    characters ending Z), so a text comparison orders by time."""
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc(v) -> datetime | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    s = str(v).replace("Z", "+00:00")
    t = datetime.fromisoformat(s)
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


# ── the slate: one entry per fight ───────────────────────────────────────────

def fight_key(game_id: str) -> tuple[frozenset, date] | None:
    from data.schedule_context import ufc_slugs
    s = ufc_slugs(game_id)
    if not s:
        return None
    return frozenset(s), date.fromisoformat(game_id.split("_")[1])


def slate(conn, now: datetime) -> dict[str, dict]:
    """{fight key: {"ids": [...], "rows": {id: game row}}} for fights after now."""
    rows = conn.execute("""
        SELECT game_id, game_date, home_team, away_team, commence_time
          FROM games
         WHERE sport = 'UFC' AND home_score IS NULL
           AND game_date >= %s AND game_date <= %s
    """, ((now - timedelta(days=2)).date().isoformat(),
          (now + timedelta(days=HORIZON_DAYS)).date().isoformat())).fetchall()
    groups: dict[frozenset, list[dict]] = defaultdict(list)
    for gid, gd, home, away, ct in rows:
        k = fight_key(gid)
        start = _utc(ct)
        if k is None or start is None or start <= now:
            continue
        if start.strftime("%m-%d") in PLACEHOLDER_DAYS:
            continue
        groups[k[0]].append({"game_id": gid, "day": k[1], "game_date": str(gd)[:10],
                             "home": home, "away": away, "start": start})
    out = {}
    for pair, rs in groups.items():
        rs.sort(key=lambda r: r["day"])
        cluster: list[dict] = []
        for r in rs + [None]:
            if r is not None and (not cluster or (r["day"] - cluster[-1]["day"]).days <= 2):
                cluster.append(r)
                continue
            if cluster:
                key = "|".join(sorted(pair)) + "|" + cluster[0]["day"].isoformat()
                out[key] = {"rows": {c["game_id"]: c for c in cluster},
                            "start": max(c["start"] for c in cluster)}
            cluster = [r] if r is not None else []
    return out


def decided_fights(conn, keys: list[str]) -> set[str]:
    if not keys:
        return set()
    ph = ",".join(["%s"] * len(keys))
    try:
        done = {r[0] for r in conn.execute(
            f"SELECT fight_key FROM {DECISIONS_TABLE} WHERE fight_key IN ({ph})", keys).fetchall()}
    except Exception:                                   # noqa: BLE001 -- no ledger yet
        conn.rollback()
        done = set()
    return done


def picked_ids(conn, ids: list[str]) -> set[str]:
    """Ids this model already wrote a row on (a bet locks the fight)."""
    if not ids:
        return set()
    ph = ",".join(["%s"] * len(ids))
    return {r[0] for r in conn.execute(
        f"SELECT game_id FROM picks WHERE model_id = %s AND signal_type = 'BET' AND game_id IN ({ph})",
        [MODEL_ID, *ids]).fetchall()}


# ── identity, orientation, ratings ───────────────────────────────────────────

class Ratings:
    def __init__(self, conn):
        self.rows, self.profiles = R.load(conn)
        self.states = R.replay(self.rows, self.profiles)
        self._conn = conn
        self._ids: dict[str, str | None] = {}

    def fighter(self, display: str) -> str | None:
        if display not in self._ids:
            from data.ufc_identity import resolve_fighter_id
            self._ids[display] = resolve_fighter_id(self._conn, display)
        return self._ids[display]

    def orient(self, home: str, away: str) -> tuple[str, str, bool] | None:
        """(A id, B id, A is the row's home fighter), A the smaller ufcstats slug."""
        h, a = self.fighter(home), self.fighter(away)
        if not h or not a:
            return None
        sh = R.slugify(self.profiles.get(h, {}).get("name") or home)
        sa = R.slugify(self.profiles.get(a, {}).get("name") or away)
        return (h, a, True) if sh <= sa else (a, h, False)

    def opinion(self, art: dict, a_id: str, b_id: str, on: date) -> float:
        return om.opinion(art, R.pair_diffs(self.states, a_id, b_id, self.profiles, on))


# ── the pull ─────────────────────────────────────────────────────────────────

def load_pull(conn, fight: dict, at: datetime, a_home_by_id: dict[str, bool]) -> dict | None:
    """The fight's latest quotes at or before `at` (no older than FRESH_H):
    Pinnacle's, and each deciding book's fetched within MAX_GAP_MIN of it,
    oriented to A. None when Pinnacle has no fresh quote."""
    ids = list(fight["rows"])
    books = [SHARP, *config.BEST_LINE_BOOKMAKERS]
    ph_i, ph_b = ",".join(["%s"] * len(ids)), ",".join(["%s"] * len(books))
    rows = conn.execute(f"""
        SELECT game_id, bookmaker, snapshot_at, home_price, away_price, home_link, away_link
          FROM odds
         WHERE game_id IN ({ph_i}) AND market = 'h2h' AND bookmaker IN ({ph_b})
           AND COALESCE(snapshot_type, 'open') <> 'in_play'
           AND snapshot_at <= %s AND snapshot_at >= %s
           AND home_price IS NOT NULL AND away_price IS NOT NULL
    """, [*ids, *books, _z(at), _z(at - timedelta(hours=FRESH_H))]).fetchall()
    latest: dict[str, tuple] = {}
    for gid, book, snap, hp, ap, hl, al in rows:
        t = _utc(snap)
        if gid not in a_home_by_id or t is None:
            continue
        a_home = a_home_by_id[gid]
        q = (t, float(hp if a_home else ap), float(ap if a_home else hp),
             hl if a_home else al, al if a_home else hl, gid)
        if book not in latest or t > latest[book][0]:
            latest[book] = q
    pin = latest.pop(SHARP, None)
    if pin is None:
        return None
    gap = timedelta(minutes=om.MAX_GAP_MIN)
    usable = {b: q for b, q in latest.items() if abs(q[0] - pin[0]) <= gap}
    return {"at": pin[0], "pin": (pin[1], pin[2]), "books": usable,
            "newest_id": max([pin, *usable.values()], key=lambda q: q[0])[5]}


# ── the run ──────────────────────────────────────────────────────────────────

def decide_fight(key: str, fight: dict, pull: dict | None, xb: float, cut: float,
                 floor: float | None, now: datetime) -> om.Decision:
    lead_h = (fight["start"] - now).total_seconds() / 3600
    if pull is None or not pull["books"]:
        status = "no_pull" if lead_h >= om.MIN_LEAD_H else "no_window"
        return om.Decision(key, status, "no fresh Pinnacle quote with a deciding book beside it")
    pick, best = om.decide_pull(pull["pin"], {b: (q[1], q[2]) for b, q in pull["books"].items()},
                                xb, cut, floor)
    quotes = {"pinnacle": list(pull["pin"]), **{b: [q[1], q[2]] for b, q in pull["books"].items()}}
    if pick is not None:
        return om.Decision(key, "bets", f"EV {pick.ev:+.3f} at {pick.book} {pick.price:+.0f}, "
                           f"{lead_h / 24:.1f} days out", pick, quotes)
    why = "below_cut" if lead_h >= om.MIN_LEAD_H else "window_closed"
    ev = f"best EV {best.ev:+.3f}" if best is not None else "no candidate above the price floor"
    return om.Decision(key, why, ev, best, quotes)


def pick_row(d: om.Decision, fight: dict, game_id: str, a_home: bool, bankroll: float,
             pull: dict) -> tuple[dict | None, str | None]:
    """The picks row for a decision (BET or NONE), and why a bet was refused."""
    from models.honest_ev import gate
    from models.scorer import _build_pick_label, _pause_note, american_to_implied_prob, quarter_kelly
    if d.pick is None:
        return None, None
    g = fight["rows"][game_id]
    side = "home" if (d.pick.side == "a") == a_home else "away"
    is_bet, refused = d.status == "bets", None
    if is_bet:
        ev = gate(MODEL_ID, d.pick.prob, d.pick.price)
        if not ev.clears:
            is_bet, refused = False, ev.reason or "below_ev_floor"
    label = _build_pick_label(side, g["home"], g["away"], om.MARKET, None)
    problems = pick_problems(label, side, None, MODEL_ID, g["home"], g["away"])
    if problems:
        logger.error(f"{MODEL_ID}: refusing {game_id} {label!r}: {'; '.join(problems)}")
        return None, "label_mismatch"
    imp = american_to_implied_prob(d.pick.price)
    edge = round(d.pick.prob - imp, 4)
    kf, rec = quarter_kelly(d.pick.prob, imp, bankroll) if is_bet else (0.0, 0.0)
    q = pull["books"].get(d.pick.book)
    link = None if q is None else (q[3] if d.pick.side == "a" else q[4])
    dk = pull["books"].get("draftkings")
    dk_price = None if dk is None else (dk[1] if d.pick.side == "a" else dk[2])
    dk_imp = american_to_implied_prob(dk_price) if dk_price is not None else 0.0
    return {
        "game_id": game_id, "model_id": MODEL_ID, "sport": SPORT,
        "game_date": g["game_date"], "game_time": fight["start"].isoformat(),
        "pick_side": side, "pick_label": label,
        "model_probability": round(d.pick.prob, 4), "model_probability_cal": round(d.pick.prob, 4),
        "dk_odds": dk_price, "dk_implied_prob": round(dk_imp, 4),
        "edge": round(d.pick.prob - dk_imp, 4) if dk_price is not None else 0.0,
        "dk_bet_link": None if dk is None else (dk[3] if d.pick.side == "a" else dk[4]),
        "scored_line": None, "kelly_fraction": kf, "recommended_bet": rec,
        "bankroll_at_pick": bankroll, "signal_type": "BET" if is_bet else "NONE",
        "confidence_tier": "MED", "line_book": None,
        "decision_book": d.pick.book, "decision_odds": d.pick.price,
        "decision_implied_prob": round(imp, 4), "decision_edge": edge,
        "best_book": d.pick.book, "best_odds": d.pick.price, "best_implied_prob": round(imp, 4),
        "best_edge": edge, "best_bet_link": link, "downgrade_reason": _pause_note(MODEL_ID),
    }, refused


_COLS = ("game_id", "model_id", "sport", "game_date", "game_time", "pick_side", "pick_label",
         "model_probability", "model_probability_cal", "dk_implied_prob", "edge", "dk_odds",
         "scored_line", "kelly_fraction", "recommended_bet", "bankroll_at_pick", "signal_type",
         "confidence_tier", "dk_bet_link", "line_book",
         "decision_book", "decision_odds", "decision_implied_prob", "decision_edge",
         "best_book", "best_odds", "best_implied_prob", "best_edge", "best_bet_link",
         "downgrade_reason")
_INSERT = (f"INSERT INTO picks ({', '.join(_COLS)}) "
           f"VALUES ({', '.join('%(' + c + ')s' for c in _COLS)}) "
           f"ON CONFLICT DO NOTHING RETURNING pick_id")


def run_card(do_publish: bool = False, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    stats = defaultdict(int)
    if not enabled():
        logger.info("UFC opening-price card: RUN_UFC_OPEN_MONEYLINE is off; nothing read")
        return {"off": True}
    art = om.load_artifact()
    cut = config.min_ev_for(MODEL_ID)
    floor = config.min_odds_for(MODEL_ID)
    conn = get_connection()
    try:
        fights = slate(conn, now)
        stats["fights"] = len(fights)
        done = decided_fights(conn, sorted(fights))
        bet_ids = picked_ids(conn, sorted({i for f in fights.values() for i in f["rows"]}))
        todo = {k: f for k, f in fights.items()
                if k not in done and not (set(f["rows"]) & bet_ids)}
        stats["already_decided"] = len(fights) - len(todo)
        if not todo:
            logger.info(f"UFC opening-price card: {dict(stats)}")
            return dict(stats)
        if do_publish:
            ensure_decisions_table(conn)
        from data.schedule_context import ScheduleBook
        book = ScheduleBook.load(conn, "UFC", [(i, r["game_date"]) for f in todo.values()
                                               for i, r in f["rows"].items()])
        ratings = Ratings(conn)
        from models.scorer import _get_current_bankroll
        bankroll = _get_current_bankroll(conn) if do_publish else 0.0
        out = []
        for key, f in sorted(todo.items()):
            lead_h = (f["start"] - now).total_seconds() / 3600
            first = next(iter(f["rows"].values()))
            orient = {i: ratings.orient(r["home"], r["away"]) for i, r in f["rows"].items()}
            if any(o is None for o in orient.values()):
                stats["unplaced_fighter"] += 1
                continue
            hold = book.pending_reason(first["game_id"], first["game_date"], first["home"],
                                       first["away"], f["start"], now)
            if hold:
                stats["schedule_hold"] += 1
                logger.info(f"  {key}: held, {hold}")
                continue
            a_id, b_id, _ = orient[first["game_id"]]
            xb = ratings.opinion(art, a_id, b_id, f["start"].date())
            a_home = {i: o[2] for i, o in orient.items()}
            if lead_h >= om.MIN_LEAD_H and not bets_decided_at(now):
                stats["waits_for_noon"] += 1
                continue
            at = now if lead_h >= om.MIN_LEAD_H else f["start"] - timedelta(hours=om.MIN_LEAD_H)
            pull = load_pull(conn, f, at, a_home)
            d = decide_fight(key, f, pull, xb, cut, floor, now)
            stats[d.status] += 1
            if d.status not in FINAL:
                continue
            if pull is None:
                out.append((d, first["game_id"], None, None, None, xb))
                continue
            gid = pull["newest_id"]
            row, refused = pick_row(d, f, gid, a_home[gid], bankroll, pull)
            out.append((d, gid, row, refused, pull, xb))
        written = 0
        if do_publish and out:
            from scripts.nfl_wind_publisher import _lock_model
            _lock_model(conn, MODEL_ID)
            again = decided_fights(conn, [d.fight for d, *_ in out])
            for d, gid, row, refused, pull, xb in out:
                if d.fight in again:
                    continue
                p = d.pick
                got = conn.execute(_INSERT_DECISION, {
                    "fight_key": d.fight, "game_id": gid,
                    "quote_at": pull["at"].isoformat() if pull else None,
                    "status": d.status, "side": p.side if p else None, "book": p.book if p else None,
                    "price": p.price if p else None, "prob": round(p.prob, 4) if p else None,
                    "ev": round(p.ev, 4) if p else None, "opinion": round(xb, 4),
                    "n_books": len(pull["books"]) if pull else 0, "quotes": json.dumps(d.quotes),
                    "detail": (d.detail + (f"; refused {refused}" if refused else ""))[:2000],
                }).fetchone()
                if got and row is not None and conn.execute(_INSERT, row).fetchone():
                    written += row["signal_type"] == "BET"
            conn.commit()
        stats["written_bets"] = written
        for d, gid, row, refused, pull, xb in out:
            logger.info(f"  {d.fight}: {d.status} -- {d.detail}"
                        + (f" -> {row['pick_label']} {row['decision_odds']:+.0f} at {row['decision_book']}"
                           if row else ""))
        logger.info(f"UFC opening-price card: {dict(stats)}")
        return dict(stats)
    finally:
        conn.close()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args(argv)
    print(run_card(do_publish=a.publish))


if __name__ == "__main__":
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("ufc-open-moneyline-card")
    except Exception:  # noqa: BLE001
        pass
    main()
