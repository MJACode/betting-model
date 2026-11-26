"""Alerts for the member's own models (Build Your Own Model).

Matt, 2026-11-25: alert the member when one of their saved models has a
bet, and show it as a card. NFL only to start ("Let's start with just NFL
to test this out"). Alert on every odds refresh, on by default with a
per-model switch, and never in the official record.

One pass, run by the worker job ``byom_alerts`` after each refresh pass:

1. Rebuild the facts and official candidates for NFL games that have not
   started and kick off within ``UPCOMING_DAYS`` ET days. The daily
   10:41am refresh rebuilds the whole week; this keeps the next games as
   fresh as the odds. It reads stored odds only: no API credits.
2. For each saved NFL model with alerts on, ``byom_legs(season, filters,
   'open')`` returns the official bets on games not yet started: the first
   DraftKings line and price that fit the rules, the same lock the
   model's record uses. A bet with no American price is not an alert.
3. Insert each one into ``byom_alerts`` once. A later pass where the line
   moved does not touch the row (CLAUDE.md 1c, applied to a member's
   model). Only rows inserted by this pass are announced.
4. One push per model per pass to that member's devices, and one inbox
   row, unless the member muted NFL. ``notified_at`` is set once.

Nothing here reads or writes ``picks``, posts to Discord or X, or changes
a live model. Until data/migrations/byom_alerts_2026_11_25.sql is applied,
``ready`` is false and the pass does nothing.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from loguru import logger

from byom.game_facts import parse_date
from byom.refresh import _aware, _clock, _season_for

# Matt, 2026-11-25: NFL first. NCAAB game lines 2026-11-26 ("Do NCAAB next").
ALERT_SPORTS = ("NFL", "NCAAB")

# Not a lock window. Games that kick off today through this many ET days
# ahead are rebuilt on every pass. A later game is rebuilt by the daily
# refresh (7 days ahead), so its bets are still found, at most a day late.
UPCOMING_DAYS = 2

KIND = "byom_bet"

_READY = """
SELECT to_regclass('public.byom_alerts') IS NOT NULL
   AND EXISTS (
     SELECT 1 FROM pg_proc p
      WHERE p.oid = to_regprocedure('public.byom_legs(integer, jsonb, text)')
        AND position('byom_open_bets_v1' in p.prosrc) > 0)
"""

_MODELS = """
SELECT model_id::text, user_id::text, name, filters
  FROM byom_models
 WHERE sport = %s AND alerts_enabled
 ORDER BY created_at
"""

# One statement per model. ON CONFLICT keeps the first row: a moved line on
# a later pass is the same bet, not a new one.
_INSERT = """
INSERT INTO byom_alerts (
  model_id, user_id, sport, season, canonical_key, market, leg_side,
  team, player_name, home_team, away_team, commence_time, point, price,
  label, locked_at)
SELECT %(model_id)s::uuid, %(user_id)s::uuid, %(sport)s, %(season)s,
       l.canonical_key, l.market, l.leg_side, l.team,
       COALESCE(l.player_name, ''), l.home_team, l.away_team,
       l.commence_time, l.point, l.price,
       byom_leg_label(l.market, l.leg_side, l.team, l.point, l.player_name),
       l.locked_at
  FROM byom_legs(%(season)s, %(filters)s::jsonb, 'open') AS l
 WHERE l.priced
ON CONFLICT ON CONSTRAINT byom_alerts_one_per_bet DO NOTHING
RETURNING alert_id::text, label, commence_time, canonical_key
"""

_MARK = "UPDATE byom_alerts SET notified_at = now() WHERE alert_id = ANY(%s::uuid[])"


def ready(conn) -> bool:
    """True once the hand migration is applied. A probe never raises."""
    try:
        row = conn.execute(_READY).fetchone()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"byom alerts probe failed: {exc}")
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        return False
    return bool(row and row[0])


def upcoming_game_ids(games: list[dict], today=None,
                      days: int = UPCOMING_DAYS) -> list[str]:
    """Games from today through ``days`` ET days ahead that have not started.

    A game with no commence time is kept: the builder bounds every quote
    on kickoff itself, and the open read drops a started game.
    """
    as_of, now = _clock(today)
    last = as_of + timedelta(days=days)
    out = []
    for game in games:
        day = parse_date(game.get("game_date"))
        if day is None or day < as_of or day > last:
            continue
        kick = _kick(game.get("commence_time"))
        if kick is not None and kick <= now:
            continue
        if game.get("game_id"):
            out.append(str(game["game_id"]))
    return out


def _kick(value) -> datetime | None:
    if isinstance(value, str) and value.strip():
        try:
            value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    return _aware(value)


def rebuild_upcoming(conn, sport: str = "NFL", today=None) -> dict:
    """Facts and official candidates for the next games. Commits."""
    from byom.load import _games, build_season
    from byom.prop_load import build_season as build_props
    from byom.refresh import PROP_SPORTS

    as_of, _now = _clock(today)
    season = _season_for(sport, as_of)
    ids = upcoming_game_ids(_games(conn, season, sport), today=today)
    out = {"season": season, "games": len(ids), "game_facts": 0, "prop_facts": 0}
    if not ids:
        return out
    game = build_season(conn, season, apply=True, game_ids=ids, sport=sport)
    out["game_facts"] = game.get("written", 0)
    if sport in PROP_SPORTS:
        prop = build_props(conn, season, apply=True, game_ids=ids, sport=sport)
        out["prop_facts"] = prop.get("written", 0)
    conn.commit()
    return out


def find_new_bets(conn, sport: str = "NFL", today=None) -> list[dict]:
    """Insert this pass's new open bets. One savepoint per model.

    A model whose filters the function refuses is logged and skipped; the
    other models still run. Returns one dict per model that found any.
    """
    as_of, _now = _clock(today)
    season = _season_for(sport, as_of)
    found = []
    for model_id, user_id, name, filters in conn.execute(_MODELS, (sport,)).fetchall():
        # byom_save_model keeps the sport in its own column and strips it
        # from filters, and byom_legs reads a missing sport as NFL. So the
        # model's sport goes back in here, or an NCAAB model is matched
        # against NFL games.
        stored = dict(filters) if isinstance(filters, dict) else {}
        stored["sport"] = sport
        params = {
            "model_id": model_id, "user_id": user_id, "sport": sport,
            "season": season,
            "filters": json.dumps(stored),
        }
        conn.execute("SAVEPOINT byom_alert_model")
        try:
            rows = conn.execute(_INSERT, params).fetchall()
            conn.execute("RELEASE SAVEPOINT byom_alert_model")
        except Exception as exc:  # noqa: BLE001 - one model must not sink the rest
            conn.execute("ROLLBACK TO SAVEPOINT byom_alert_model")
            logger.error(f"byom alerts: model {model_id} skipped: {exc}")
            continue
        if rows:
            found.append({
                "model_id": model_id, "user_id": user_id, "name": name,
                "sport": sport,
                "bets": [{"alert_id": r[0], "label": r[1]} for r in rows],
            })
    conn.commit()
    return found


def message_for(model: dict) -> tuple[str, str, dict]:
    """Title, body and route for one model's new bets.

    The body is the stored label word for word (byom_leg_label), never a
    line rebuilt here (CLAUDE.md 00).
    """
    from tracking.push_notifier import PUSH_ROUTE_VERSION, _summary_body

    bets = model["bets"]
    n = len(bets)
    title = f"🔔 {model['name']}: {n} new bet{'s' if n != 1 else ''}"
    body = _summary_body([b["label"] for b in bets])
    data = {"v": PUSH_ROUTE_VERSION, "type": KIND, "sport": model["sport"],
            "modelId": model["model_id"]}
    if n == 1:
        data["alertId"] = bets[0]["alert_id"]
    return title, body, data


def announce(conn, found: list[dict], dry_run: bool = False) -> dict:
    """One push and one inbox row per model with new bets.

    A muted sport sends nothing and writes no inbox row; the alert rows
    stay, so the card is still on the member's screens. ``notified_at`` is
    set for every announced alert, including one whose member has no
    device: the moment has passed, and a later pass must not replay it.
    """
    from tracking.notification_inbox import (
        bind_inbox_id, inbox_ready, insert_rows, load_devices, load_mutes,
        make_row, sport_is_muted, unread_counts,
    )
    from tracking.push_notifier import _expo_send

    out = {"models": len(found), "alerts": sum(len(m["bets"]) for m in found),
           "messages": 0, "sent": 0, "inbox": 0, "muted": 0}
    if not found:
        return out
    has_inbox = inbox_ready(conn)
    devices = load_devices(conn)
    mutes = load_mutes(conn) if has_inbox else {}
    unread = unread_counts(conn, mutes) if has_inbox else {}
    messages: list[dict] = []
    rows: list[dict] = []
    for model in found:
        user_id = model["user_id"]
        if sport_is_muted(user_id, model["sport"], mutes):
            out["muted"] += 1
            continue
        title, body, data = message_for(model)
        keys = [b["alert_id"] for b in model["bets"]]
        payload = bind_inbox_id(user_id, KIND, keys, data)
        if has_inbox:
            rows.append(make_row(user_id, KIND, title, body, payload))
        tokens = [d["token"] for d in devices
                  if d.get("user_id") == user_id and d.get("token")]
        badge = unread.get(user_id, 0) + sum(1 for r in rows if r["user_id"] == user_id)
        for token in tokens:
            messages.append({
                "to": token, "title": title, "body": body, "data": dict(payload),
                "sound": "default", "priority": "high", "badge": badge,
            })
    out["messages"] = len(messages)
    out["inbox"] = len(rows)
    if dry_run:
        return out
    if messages:
        out["sent"] = _expo_send(messages, conn=conn)
    insert_rows(conn, rows)
    ids = [b["alert_id"] for m in found for b in m["bets"]]
    conn.execute(_MARK, (ids,))
    conn.commit()
    return out


def run(conn, sport: str = "NFL", rebuild: bool = True, today=None,
        dry_run: bool = False) -> dict:
    """The whole pass. Returns a report; does nothing until the migration is in."""
    if sport not in ALERT_SPORTS:
        raise ValueError(f"byom alerts run for {ALERT_SPORTS}, got {sport!r}")
    if not ready(conn):
        return {"status": "not_applied", "sport": sport}
    report: dict = {"status": "ok", "sport": sport}
    if dry_run:
        # The rebuild and find_new_bets both write. A dry run is the probe.
        return report
    if rebuild:
        report["rebuilt"] = rebuild_upcoming(conn, sport, today=today)
    found = find_new_bets(conn, sport, today=today)
    report["announced"] = announce(conn, found)
    return report
