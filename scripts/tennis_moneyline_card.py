"""Tennis match-winner card: write `atp_moneyline_shop` and `wta_moneyline_shop`
bets (models/tennis_moneyline_shop.py).

LIVE, real money (mike, 2026-11-13: "build professional tennis models"; men's
and women's as separate models and Discord channels). Runs every ten minutes
(scheduler.run_tennis_moneyline_card). RUN_TENNIS_MONEYLINE_CARD=0 stops it
before it reads or buys anything; the job keeps beating.

ONE RUN.
  1. The prices: one pass of the odds feed's live endpoint for every active
     tennis key, both book groups, stored change-only in tennis_odds_quotes
     (data/ingestors/tennis_odds_history.poll_live), the same table and the
     same rows the research replayed. The credit floor is 0 (mike,
     2026-11-14: "put the odds api floor to zero"); the job only stops when
     the account is empty.
  2. The schedule: ESPN's scoreboard for yesterday, today and tomorrow (UTC)
     for both tours, upserted into tennis_espn_matches. A match is decided
     only when ESPN lists it with the same two players and has not started it
     (the research graded linked matches only).
  3. The decision, once per match: at the first run at which the feed's listed
     start is 35 minutes or less away, and only before the listed start, from
     the quotes standing at that moment (each book's latest stored row) and
     Pinnacle's standing pair. The research replayed the same decision at the
     first hourly snapshot within 60 minutes of the listed start (30 minutes
     before it on average; this card, polling every ten minutes, decides 30
     on average too): scripts/tennis_moneyline_replay.py.
  4. The pick: a BET at the best decidable price both ways when its EV,
     retirement term included, is in [0.02, 0.05) at -500 or longer; a NONE
     row at the best quote otherwise, so the whole priced universe can be
     graded.

EACH MATCH DECIDED ONCE (CLAUDE.md 1c). The decision row
(tennis_moneyline_decisions, keyed on the feed's event id) and the pick are
written in one transaction under the model's advisory lock. A match with a
decision row is never decided again: a later poll, a moved line or a better
price writes nothing.

SETTLEMENT is tracking/paper_tracker._settle_tennis_picks: the ESPN match
stored on the decision row, graded at the deciding book's own retirement rule
(models/tennis_common.grade_moneyline). DraftKings voids a bet on the player
who retires after set one; FanDuel and BetMGM grade it a loss; Caesars and the
books whose rule is unread void every bet on a retirement.

    python -m scripts.tennis_moneyline_card              # print the card, write nothing
    python -m scripts.tennis_moneyline_card --publish    # buy the pass, write decisions and bets
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402,F401
from data.anon_readable import API_ROLES, lock_down  # noqa: E402
from data.db import get_connection  # noqa: E402
from data.ddl_guard import schema_is_current  # noqa: E402
from models import tennis_common as tc  # noqa: E402
from models import tennis_moneyline_shop as ms  # noqa: E402
from tracking.pick_integrity import pick_problems  # noqa: E402

_ET = ZoneInfo("America/New_York")
DECISION_LEAD = timedelta(minutes=35)
# Quotes for matches listed this far back are read: a listed start moves, so
# an event's latest row decides what its listed start is.
LOOK_BACK = timedelta(days=2)
ESPN_WINDOW = timedelta(hours=60)


def enabled() -> bool:
    """The kill switch: RUN_TENNIS_MONEYLINE_CARD=0 (or false/off/no). Default on."""
    return (os.environ.get("RUN_TENNIS_MONEYLINE_CARD", "1").strip().lower()
            not in ("0", "false", "off", "no"))


# ── the decisions ledger ─────────────────────────────────────────────────────
# One row per match the card has decided. Worker-only
# (data/anon_readable.WORKER_ONLY_TABLES): the app never reads it.
DECISIONS_TABLE = "tennis_moneyline_decisions"
DECISIONS_COLS = ("event_id", "decided_at", "sport_key", "game_id", "comp_id", "home_is_p1",
                  "quote_at", "listed_start", "book", "side", "price", "p_ref", "ev",
                  "ref_home", "ref_away", "signal", "detail")
DECISIONS_DDL = """
CREATE TABLE IF NOT EXISTS tennis_moneyline_decisions (
    event_id      TEXT PRIMARY KEY,
    decided_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sport_key     TEXT NOT NULL,
    game_id       TEXT NOT NULL,
    comp_id       TEXT,
    home_is_p1    BOOLEAN,
    quote_at      TEXT,
    listed_start  TEXT,
    book          TEXT,
    side          TEXT,
    price         INTEGER,
    p_ref         REAL,
    ev            REAL,
    ref_home      INTEGER,
    ref_away      INTEGER,
    signal        TEXT NOT NULL,
    detail        TEXT
)
"""
_INSERT_DECISION = (
    "INSERT INTO tennis_moneyline_decisions (event_id, sport_key, game_id, comp_id, home_is_p1, "
    "quote_at, listed_start, book, side, price, p_ref, ev, ref_home, ref_away, signal, detail) "
    "VALUES (%(event_id)s, %(sport_key)s, %(game_id)s, %(comp_id)s, %(home_is_p1)s, "
    "%(quote_at)s, %(listed_start)s, %(book)s, %(side)s, %(price)s, %(p_ref)s, %(ev)s, "
    "%(ref_home)s, %(ref_away)s, %(signal)s, %(detail)s) "
    "ON CONFLICT (event_id) DO NOTHING RETURNING event_id")


def ensure_decisions_table(conn) -> None:
    if schema_is_current(conn, DECISIONS_TABLE, columns=DECISIONS_COLS,
                         rls=True, revoked_from=API_ROLES):
        return
    conn.execute(DECISIONS_DDL)
    lock_down(conn, DECISIONS_TABLE)
    conn.commit()


def decided_events(conn, event_ids: list[str]) -> set[str]:
    if not event_ids or not conn.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' "
            "AND table_name = %s", (DECISIONS_TABLE,)).fetchone():
        return set()
    return {r[0] for r in conn.execute(
        "SELECT event_id FROM tennis_moneyline_decisions WHERE event_id = ANY(%s)",
        (list(event_ids),)).fetchall()}


# ── reads ─────────────────────────────────────────────────────────────────────

_QUOTE_COLS = ("sport_key", "event_id", "commence_time", "home_name", "away_name",
               "bookmaker", "snapshot_ts", "home_price", "away_price")


def load_standing(conn, keys: list[str], now: datetime) -> pd.DataFrame:
    """Each book's latest stored match-winner row, per event of `keys` listed
    from LOOK_BACK ago on, stored at or before `now`; and per event its latest
    row's listed start (`listed`). Read on the (sport_key, commence_time)
    index."""
    if not keys:
        return pd.DataFrame(columns=_QUOTE_COLS + ("listed",))
    rows = conn.execute(f"""
        SELECT {', '.join(_QUOTE_COLS)} FROM tennis_odds_quotes
        WHERE sport_key = ANY(%s) AND commence_time >= %s AND market = 'h2h'
          AND snapshot_ts <= %s AND home_price IS NOT NULL AND away_price IS NOT NULL
    """, (list(keys), now - LOOK_BACK, now)).fetchall()
    q = pd.DataFrame(rows, columns=list(_QUOTE_COLS))
    if q.empty:
        return q.assign(listed=pd.Series(dtype="datetime64[ns, UTC]"))
    for c in ("commence_time", "snapshot_ts"):
        q[c] = pd.to_datetime(q[c], utc=True)
    q = q.sort_values("snapshot_ts")
    listed = q.groupby("event_id").commence_time.last().rename("listed")
    stand = q.groupby(["event_id", "bookmaker"], as_index=False).tail(1)
    return stand.merge(listed, left_on="event_id", right_index=True)


def due_events(stand: pd.DataFrame, now: datetime) -> list[str]:
    """Events whose listed start is 35 minutes or less away and not passed."""
    if stand.empty:
        return []
    ev = stand.drop_duplicates("event_id")
    lead = ev.listed - pd.Timestamp(now)
    return sorted(ev[(lead > pd.Timedelta(0)) & (lead <= DECISION_LEAD)].event_id)


def load_espn(conn, now: datetime) -> pd.DataFrame:
    rows = conn.execute("""
        SELECT comp_id, start_time, status, p1_name, p2_name FROM tennis_espn_matches
        WHERE start_time BETWEEN %s AND %s
    """, (now - ESPN_WINDOW, now + ESPN_WINDOW)).fetchall()
    r = pd.DataFrame(rows, columns=["comp_id", "start_time", "status", "p1_name", "p2_name"])
    r["start_time"] = pd.to_datetime(r.start_time, utc=True)
    return r


def refresh_espn(conn, now: datetime) -> int:
    from data.ingestors import tennis_espn as te
    days = sorted({(now + timedelta(days=k)).date() for k in (-1, 0, 1)})
    n = 0
    for tour in ("ATP", "WTA"):
        n += te.store(conn, list(te.collect(tour, days).values()))
    return n


def buy_pass(conn) -> tuple[list[str], int]:
    from data.ingestors import tennis_odds_history as toh
    toh.ensure_tables(conn)
    keys = toh.active_keys()
    meter = toh.Meter(max_credits=10_000, floor=0)
    stored = toh.poll_live(conn, meter, keys)
    logger.info(f"tennis card: live pass over {len(keys)} keys, {stored} new quotes, "
                f"{meter.spent} credits, account {meter.remaining}")
    return keys, stored


# ── the decision ─────────────────────────────────────────────────────────────

def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", tc.fold(name).strip()).strip("-")


def game_id_for(tour: str, game_date: str, home: str, away: str) -> str:
    return f"{tour}_{game_date}_{_slug(away)}_{_slug(home)}"


def decide_event(g: pd.DataFrame, link: dict | None) -> dict:
    """One decision row (and the pick's fields) for one event's standing
    quotes `g`. Pure."""
    first = g.iloc[0]
    sk, tour = first.sport_key, ms.tour_of(first.sport_key)
    listed = first.listed
    game_date = listed.tz_convert(_ET).date().isoformat()
    out = {"event_id": first.event_id, "sport_key": sk, "tour": tour,
           "home": first.home_name, "away": first.away_name, "game_date": game_date,
           "game_id": game_id_for(tour, game_date, first.home_name, first.away_name),
           "listed_start": listed.isoformat(), "quote_at": g.snapshot_ts.max().isoformat(),
           "comp_id": None, "home_is_p1": None, "book": None, "side": None, "price": None,
           "p_ref": None, "ev": None, "ref_home": None, "ref_away": None, "dk_price": None}
    if link is None:
        return {**out, "signal": "SKIP", "detail": "no_espn_match"}
    out.update(comp_id=link["comp_id"], home_is_p1=link["home_is_p1"])
    if link["status"] != "STATUS_SCHEDULED":
        return {**out, "signal": "SKIP", "detail": f"espn_{link['status']}"}
    by = g.set_index("bookmaker")
    ref = None
    if ms.REFERENCE in by.index:
        r = by.loc[ms.REFERENCE]
        ref = ms.Quote(ms.REFERENCE, int(r.home_price), int(r.away_price))
        out.update(ref_home=ref.price_a, ref_away=ref.price_b)
    quotes = [ms.Quote(b, int(r.home_price), int(r.away_price)) for b, r in by.iterrows()]
    c = ms.decide(quotes, ref, sk)
    if c is None:
        return {**out, "signal": "SKIP", "detail": "no_pinnacle_price"}
    if not c.book:
        return {**out, "signal": "SKIP", "detail": c.reason}
    if "draftkings" in by.index:
        dk = by.loc["draftkings"]
        out["dk_price"] = int(dk.home_price if c.side == "a" else dk.away_price)
    out.update(book=c.book, side=c.side, price=c.price, p_ref=round(c.p_ref, 4),
               ev=round(c.ev, 4))
    return {**out, "signal": "BET" if c.bet else "NONE",
            "detail": "bet" if c.bet else c.reason}


def link_events(stand: pd.DataFrame, espn: pd.DataFrame, event_ids: list[str]) -> dict:
    from scripts.tennis_market_study import link
    if espn.empty or not event_ids:
        return {}
    ev = stand[stand.event_id.isin(event_ids)].drop_duplicates("event_id").copy()
    ev["commence_time"] = ev.listed
    lk = link(ev, espn, window=ESPN_WINDOW)
    status = espn.set_index("comp_id").status
    return {r.event_id: {"comp_id": r.comp_id, "home_is_p1": bool(r.home_is_p1),
                         "status": status.get(r.comp_id)}
            for r in lk.itertuples(index=False) if r.comp_id is not None}


# ── rows ──────────────────────────────────────────────────────────────────────

_COLS = ("game_id", "model_id", "sport", "game_date", "game_time", "pick_side", "pick_label",
         "model_probability", "model_probability_cal", "dk_implied_prob", "edge", "dk_odds",
         "scored_line", "kelly_fraction", "recommended_bet", "bankroll_at_pick", "signal_type",
         "confidence_tier", "decision_book", "decision_odds", "decision_implied_prob",
         "decision_edge", "best_book", "best_odds", "best_implied_prob", "best_edge",
         "downgrade_reason")
_INSERT = (f"INSERT INTO picks ({', '.join(_COLS)}) "
           f"VALUES ({', '.join('%(' + c + ')s' for c in _COLS)}) "
           f"ON CONFLICT DO NOTHING RETURNING pick_id")


def pick_row(d: dict, bankroll: float) -> tuple[dict | None, str | None]:
    """A decision -> its picks row (BET or NONE), or (None, why) when it is
    refused. The shared EV gate is applied to the probability-equivalent of
    the decision's EV, (1 + EV) / decimal, so the retirement term the rule
    priced is the one the gate checks."""
    if d["signal"] not in ("BET", "NONE"):
        return None, None
    from models.honest_ev import gate
    from models.scorer import _pause_note, quarter_kelly
    model_id = ms.MODEL_IDS[d["tour"]]
    is_bet = d["signal"] == "BET"
    price = d["price"]
    dec = tc.american_to_decimal(price)
    why = None
    floor = config.min_odds_for(model_id)
    if is_bet and floor is not None and price < floor:
        is_bet, why = False, f"below_price_floor:{price:+d}"
    if is_bet:
        g = gate(model_id, (1 + d["ev"]) / dec, price)
        if not g.clears:
            is_bet, why = False, g.reason or "below_ev_floor"
    side = "home" if d["side"] == "a" else "away"
    player = d["home"] if side == "home" else d["away"]
    label = f"{player} ML"
    problems = pick_problems(label, side, None, model_id, d["home"], d["away"])
    if problems:
        return None, "label_mismatch: " + "; ".join(problems)
    imp = tc.implied(price)
    edge = round(d["p_ref"] - imp, 4)
    kelly, rec = quarter_kelly(d["p_ref"], imp, bankroll) if is_bet else (0.0, 0.0)
    dk = d["dk_price"] if d["dk_price"] is not None else price
    return {
        "game_id": d["game_id"], "model_id": model_id, "sport": d["tour"],
        "game_date": d["game_date"], "game_time": d["listed_start"],
        "pick_side": side, "pick_label": label,
        # Pinnacle's power-de-vigged chance that the player advances.
        "model_probability": d["p_ref"], "model_probability_cal": d["p_ref"],
        "dk_odds": dk, "dk_implied_prob": round(tc.implied(dk), 4),
        "edge": round(d["p_ref"] - tc.implied(dk), 4), "scored_line": None,
        "kelly_fraction": kelly, "recommended_bet": rec, "bankroll_at_pick": bankroll,
        "signal_type": "BET" if is_bet else "NONE", "confidence_tier": "MED",
        "decision_book": d["book"], "decision_odds": price,
        "decision_implied_prob": round(imp, 4), "decision_edge": edge,
        "best_book": d["book"], "best_odds": price, "best_implied_prob": round(imp, 4),
        "best_edge": edge, "downgrade_reason": _pause_note(model_id),
    }, why


_GAME_UPSERT = """
INSERT INTO games (game_id, sport, season, game_date, home_team, away_team, commence_time,
                   data_source)
VALUES (%s, %s, %s, %s, %s, %s, %s, 'tennis_card')
ON CONFLICT (game_id) DO UPDATE SET commence_time = EXCLUDED.commence_time,
                                    updated_at = NOW()::TEXT
"""


def publish(conn, decisions: list[dict], bankroll: float) -> tuple[int, int]:
    """Each decided match once: its games row, its decision row and its pick
    in one transaction per model, under the model's lock. -> (bets, decided)."""
    from scripts.nfl_wind_publisher import _lock_model
    n_bets = n_decided = 0
    for tour in ("ATP", "WTA"):
        mine = [d for d in decisions if d["tour"] == tour]
        if not mine:
            continue
        _lock_model(conn, ms.MODEL_IDS[tour])
        done = decided_events(conn, [d["event_id"] for d in mine])
        for d in mine:
            # A SKIP (no ESPN match yet, no Pinnacle pair, no decidable quote,
            # or ESPN shows it started) is not a decision: the match is looked
            # at again next run, while its listed start is still ahead.
            if d["event_id"] in done or d["signal"] not in ("BET", "NONE"):
                continue
            row, why = pick_row(d, bankroll)
            detail = d["detail"] + (f"; refused {why}" if why else "")
            conn.execute(_GAME_UPSERT, (d["game_id"], tour, int(d["game_date"][:4]), d["game_date"],
                                        d["home"], d["away"], d["listed_start"]))
            got = conn.execute(_INSERT_DECISION, {
                **{k: d[k] for k in ("event_id", "sport_key", "game_id", "comp_id", "home_is_p1",
                                     "quote_at", "listed_start", "book", "side", "price",
                                     "p_ref", "ev", "ref_home", "ref_away")},
                "signal": row["signal_type"] if row else d["signal"], "detail": detail}).fetchone()
            if not got:
                continue
            n_decided += 1
            if row is not None and conn.execute(_INSERT, row).fetchone():
                n_bets += row["signal_type"] == "BET"
        conn.commit()
    return n_bets, n_decided


# ── the run ───────────────────────────────────────────────────────────────────

def render(decisions: list[dict]) -> str:
    lines = [f"tennis match-winner card: {len(decisions)} due"]
    for d in decisions:
        who = d["home"] if d["side"] == "a" else d["away"] if d["side"] else ""
        lines.append(f"  {d['tour']} {d['home']} v {d['away']} ({d['listed_start']}): {d['signal']} "
                     f"{d['detail']} {who} {d['book'] or ''} {d['price'] or ''} "
                     f"ev {d['ev'] if d['ev'] is not None else ''}")
    return "\n".join(lines)


def run_card(do_publish: bool = False, now: datetime | None = None, buy: bool = True) -> dict:
    now = now or datetime.now(timezone.utc)
    if not enabled():
        logger.info("tennis card: RUN_TENNIS_MONEYLINE_CARD is off; nothing read or bought")
        return {"due": 0, "bets": 0, "decided": 0, "off": True}
    conn = get_connection()
    try:
        if do_publish and buy:
            keys, _ = buy_pass(conn)
            refresh_espn(conn, now)
        else:
            from data.ingestors.tennis_odds_history import active_keys
            keys = active_keys()
        stand = load_standing(conn, keys, now)
        due = due_events(stand, now)
        done = decided_events(conn, due)
        due = [e for e in due if e not in done]
        links = link_events(stand, load_espn(conn, now), due)
        decisions = [decide_event(stand[stand.event_id == e], links.get(e)) for e in due]
        decisions = [d for d in decisions if d["tour"] in ms.MODEL_IDS]
        bets = decided = 0
        if do_publish and decisions:
            ensure_decisions_table(conn)
            from models.scorer import _get_current_bankroll
            bets, decided = publish(conn, decisions, _get_current_bankroll(conn))
        logger.info("\n" + render(decisions))
        return {"due": len(due), "bets": bets, "decided": decided,
                "signals": sum(d["signal"] == "BET" for d in decisions)}
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
        _install_api_probe("tennis-moneyline-card")
    except Exception:  # noqa: BLE001
        pass
    main()
