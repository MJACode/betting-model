"""
Discord webhook notifications — routes generated picks to per-sport channels.

Three producers, each independently enabled by whether its webhook is configured:

  • notify_discord_signals — a pick posts to its SPORT's channel the first time
    it clears the action thresholds (the same cut the app's Signals tab and the
    §16 mobile query use). Reads the LOCKED opening_signals row, so what posts is
    the bet of record, not a mid-refresh flicker.
  • notify_discord_live    — in-play BET signals from the live loop, to the
    dedicated live channel (or the sport's channel if none is set).
  • notify_discord_results — one morning recap after settlement: yesterday's
    record, P&L and ROI, overall and by sport.

Dedupe reuses the existing `push_sent` ledger (UNIQUE(lock_key, kind)) with
discord_* kinds, so a Discord post is independent of the mobile push for the
same signal and neither can double-fire across the ~42 refresh passes a day.

Two deliberate differences from tracking/push_notifier.py:

  • Nothing is ledgered unless the POST actually succeeded. The push notifier
    ledgers regardless (so a signal with zero devices online isn't re-detected
    forever). Here the analogous case — a webhook that isn't configured yet, or
    a transient 5xx — is one we WANT to retry: configure the channel at noon and
    the day's remaining signals still land, rather than being silently consumed.
  • Per-run volume is capped (DISCORD_MAX_EMBEDS_PER_RUN). Un-posted signals go
    out on the next pass instead of dumping 40 embeds into a channel at once.

Failures never propagate: a down webhook logs and returns, it does not fail the
pipeline step or the live loop.
"""

from __future__ import annotations

import time
import random
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from loguru import logger

import config
from data.db import get_connection

ET = ZoneInfo("America/New_York")

_FIELDS_PER_EMBED = 25          # Discord's per-embed field cap
_POST_TIMEOUT = 15
_MAX_RETRIES = 2                # on 429 / transient 5xx
_INTER_POST_SLEEP = 0.6         # webhooks allow ~5 req / 2s; stay well under

_COLOR_SIGNAL = 0x2ECC71        # green
_COLOR_LIVE = 0xE74C3C          # red
_COLOR_RESULTS_UP = 0x2ECC71
_COLOR_RESULTS_DOWN = 0xE74C3C
_COLOR_RESULTS_FLAT = 0x95A5A6

# Models whose record is tracked but whose money is not counted (mirrors the
# mobile RECORD_ONLY_MODELS and the v_model_full_outcome_record zeroing).
_RECORD_ONLY_MODELS = {"mlb_prop_batter_hr"}


# ── Formatting helpers ───────────────────────────────────────────────────────

def _american(odds) -> str:
    """DK price as a signed American string. Prob-only picks carry no price."""
    if odds is None:
        return "N/A"
    n = int(round(float(odds)))
    return f"+{n}" if n > 0 else str(n)


def _matchup(sport: str, home: str | None, away: str | None) -> str:
    """GOLF rows are one tournament (away_team is the literal 'FIELD'); UFC has
    no home team, so it reads 'A vs B' not 'A @ B'."""
    if not home and not away:
        return ""
    if sport == "GOLF":
        return home or ""
    if sport == "UFC":
        return f"{away} vs {home}"
    return f"{away} @ {home}"


def _game_time_et(commence_time: str | None) -> str:
    if not commence_time:
        return ""
    try:
        ts = datetime.fromisoformat(str(commence_time).replace("Z", "+00:00"))
    except ValueError:
        return ""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    local = ts.astimezone(ET)
    return local.strftime("%-I:%M %p ET").lstrip("0")


# ── Units ────────────────────────────────────────────────────────────────────
# Stake is published in UNITS, never dollars. `kelly_fraction` is already stored
# on every pick/signal, so this needs no bankroll — which matters, because the
# compounded bankroll is a decaying number nobody should be reading a stake off.
#
# 1 unit == UNIT_KELLY_FRACTION of the roll (1%), rounded to the nearest half
# unit. Kelly is capped at MAX_KELLY_FRACTION (5%), so units top out around 5u.
UNIT_KELLY_FRACTION = 0.01
_DEFAULT_UNITS = 1.0     # when kelly is absent/zero (prob-only picks)
_MIN_UNITS = 0.5         # a real pick never publishes as "0u"


def units_for(kelly_fraction) -> float:
    """Kelly fraction -> published unit stake, to the nearest 0.5u."""
    try:
        k = float(kelly_fraction)
    except (TypeError, ValueError):
        return _DEFAULT_UNITS
    if k <= 0:
        return _DEFAULT_UNITS
    return max(_MIN_UNITS, round(k / UNIT_KELLY_FRACTION * 2) / 2)


def fmt_units(u: float) -> str:
    """2.0 -> '2u', 3.5 -> '3.5u'."""
    return (f"{u:.1f}".rstrip("0").rstrip(".") or "0") + "u"


_SPORT_EMOJI = {
    "MLB": "\u26be", "NFL": "\U0001f3c8", "NCAAF": "\U0001f3c8",
    "NBA": "\U0001f3c0", "WNBA": "\U0001f3c0", "NHL": "\U0001f3d2",
    "UFC": "\U0001f94a", "GOLF": "\u26f3",
}


# ── Delivery ─────────────────────────────────────────────────────────────────

def _post(url: str, payload: dict) -> bool:
    """POST one webhook message. Returns True only on a confirmed success, so
    the caller knows whether it is safe to ledger. Retries a 429 for the
    duration Discord asks for; never raises."""
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = requests.post(url, json=payload, timeout=_POST_TIMEOUT)
            if resp.status_code in (200, 204):
                return True
            if resp.status_code == 429:
                try:
                    wait = float(resp.json().get("retry_after", 1.0))
                except Exception:  # noqa: BLE001 — malformed 429 body
                    wait = 1.0
                # retry_after is seconds on the webhook API; clamp so a bad
                # value can't stall the pipeline step.
                time.sleep(min(max(wait, 0.5), 10.0))
                continue
            if 500 <= resp.status_code < 600 and attempt < _MAX_RETRIES:
                time.sleep(1.0 * (attempt + 1))
                continue
            logger.error(f"Discord webhook rejected ({resp.status_code}): {resp.text[:200]}")
            return False
        except Exception as exc:  # noqa: BLE001 — delivery must never break a run
            if attempt < _MAX_RETRIES:
                time.sleep(1.0 * (attempt + 1))
                continue
            logger.error(f"Discord webhook post failed: {exc}")
            return False
    logger.error("Discord webhook still rate-limited after retries; will retry next pass")
    return False


def _post_picks(url: str, sport: str, signals: list[dict], game_date: str,
                live: bool = False) -> int:
    """Post a slate as one embed per message (chunked at Discord's 25-field cap).
    Returns how many SIGNALS were CONFIRMED delivered — a partial failure reports
    only the chunks that landed, so the rest stay un-ledgered and retry."""
    delivered = 0
    for i in range(0, len(signals), _FIELDS_PER_EMBED):
        chunk = signals[i:i + _FIELDS_PER_EMBED]
        embed = _picks_embed(sport, chunk, game_date, live=live)
        if not _post(url, {"embeds": [embed]}):
            break                      # stop: later chunks would post out of order
        delivered += len(chunk)
        time.sleep(_INTER_POST_SLEEP)
    return delivered


def _webhook_for_sport(sport: str) -> str | None:
    return config.DISCORD_WEBHOOKS.get(sport) or config.DISCORD_WEBHOOK_DEFAULT or None


def _configured() -> bool:
    return bool(config.DISCORD_WEBHOOKS
                or config.DISCORD_WEBHOOK_DEFAULT
                or config.DISCORD_WEBHOOK_LIVE
                or config.DISCORD_WEBHOOK_RESULTS)


# ── New BET signals ──────────────────────────────────────────────────────────

def _new_signals(conn, target_date: str) -> list[dict]:
    """Locked opening signals clearing the CURRENT action thresholds that haven't
    been posted to Discord yet. Joining model_action_thresholds applies the same
    prob / edge / price-floor / paused cut as the app's passesActionFilter, so we
    only ever post genuinely bettable signals."""
    rows = conn.execute("""
        SELECT os.lock_key, os.pick_label, os.sport, os.model_id,
               os.model_probability, os.edge, os.dk_odds, os.kelly_fraction,
               os.confidence_tier, g.home_team, g.away_team, g.commence_time,
               (SELECT p.dk_bet_link FROM picks p
                 WHERE p.game_id = os.game_id
                   AND p.model_id = os.model_id
                   AND p.pick_side = os.pick_side
                   AND COALESCE(p.player_id, '') = COALESCE(os.player_id, '')
                   AND p.game_date = os.game_date
                 LIMIT 1) AS dk_bet_link
        FROM opening_signals os
        JOIN model_action_thresholds t ON t.model_id = os.model_id
        LEFT JOIN games g ON g.game_id = os.game_id
        WHERE os.game_date = %s
          AND os.lock_key NOT LIKE '%%:early'   -- UFC first-signal shadow rows: measurement, never display
          AND t.paused = FALSE
          AND os.model_probability >= t.min_prob
          AND (t.prob_only = TRUE OR os.edge >= COALESCE(t.min_edge, 0))
          AND (t.min_odds IS NULL OR os.dk_odds IS NULL OR os.dk_odds >= t.min_odds)
          AND NOT EXISTS (
              SELECT 1 FROM push_sent s
              WHERE s.lock_key = os.lock_key AND s.kind = 'discord_signal'
          )
        ORDER BY os.locked_at
    """, (target_date,)).fetchall()
    return [{
        "lock_key": r[0], "label": r[1], "sport": r[2], "model_id": r[3],
        "prob": r[4], "edge": r[5], "dk_odds": r[6], "kelly": r[7],
        "tier": r[8], "home": r[9], "away": r[10], "commence": r[11],
        "bet_link": r[12],
    } for r in rows]


def _signal_field(s: dict) -> dict:
    """One pick as an embed field. Deliberately carries ONLY game, time, odds and
    unit stake — no model probability, no edge, no book name. Those are the
    model's IP and are not published to the channel."""
    context = " \u00b7 ".join(x for x in (
        _matchup(s["sport"], s["home"], s["away"]),
        _game_time_et(s["commence"]),
    ) if x)
    stake = fmt_units(units_for(s.get("kelly")))
    line = f"`{_american(s['dk_odds'])}`\u2003\u00b7\u2003**{stake}**"
    return {
        "name": s["label"],
        "value": f"{context}\n{line}" if context else line,
        "inline": False,
    }


def _picks_embed(sport: str, signals: list[dict], game_date: str,
                 live: bool = False) -> dict:
    """One embed per message holding the whole slate — far tidier in-channel than
    a stack of one-pick embeds."""
    emoji = _SPORT_EMOJI.get(sport, "\U0001f3af")
    try:
        pretty = datetime.fromisoformat(game_date).strftime("%a %b %-d")
    except ValueError:
        pretty = game_date
    title = (f"\U0001f534 {emoji} {sport} LIVE" if live
             else f"{emoji} {sport} Picks \u00b7 {pretty}")
    return {
        "title": title,
        "color": _COLOR_LIVE if live else _COLOR_SIGNAL,
        "fields": [_signal_field(s) for s in signals],
    }


def notify_discord_signals(target_date: str | None = None, dry_run: bool = False) -> int:
    """Post newly-locked BET signals to their sport's channel. Returns the number
    of signals posted. Idempotent; safe on every refresh pass."""
    if target_date is None:
        target_date = date.today().isoformat()
    if not _configured():
        return 0

    conn = get_connection()
    try:
        signals = _new_signals(conn, target_date)
        if not signals:
            logger.info(f"Discord: no new signals for {target_date}")
            return 0

        by_sport: dict[str, list[dict]] = {}
        for s in signals:
            by_sport.setdefault(s["sport"], []).append(s)

        posted_total = 0
        sent_at = datetime.now(ET).isoformat()

        for sport, group in sorted(by_sport.items()):
            url = _webhook_for_sport(sport)
            if not url:
                # No channel for this sport yet. Skip WITHOUT ledgering so these
                # still post if a webhook is added later today.
                logger.info(f"Discord: no webhook for {sport}; skipped {len(group)} signal(s)")
                continue

            capped = group[:config.DISCORD_MAX_EMBEDS_PER_RUN]
            held = len(group) - len(capped)
            if held:
                logger.info(f"Discord[{sport}]: capped at {len(capped)}; "
                            f"{held} will post next pass")

            if dry_run:
                for s in capped:
                    logger.info(f"[dry-run] discord[{sport}] → {s['label']}")
                posted_total += len(capped)
                continue

            delivered = _post_picks(url, sport, capped, target_date)
            if delivered < len(capped):
                logger.error(f"Discord[{sport}]: delivered {delivered}/{len(capped)}; "
                             f"undelivered signals retry next pass")

            # Ledger ONLY what actually landed.
            for s in capped[:delivered]:
                conn.execute(
                    "INSERT INTO push_sent (lock_key, kind, sent_at) "
                    "VALUES (%s, 'discord_signal', %s) "
                    "ON CONFLICT (lock_key, kind) DO NOTHING",
                    (s["lock_key"], sent_at),
                )
            posted_total += delivered

        if not dry_run:
            conn.commit()
            if posted_total:
                logger.success(f"✓ Discord: posted {posted_total} signal(s)")
        return posted_total
    finally:
        conn.close()


# ── Live (in-play) signals ───────────────────────────────────────────────────

def _new_live_signals(conn, target_date: str) -> list[dict]:
    """In-play BET picks not yet posted. Deduped per (game, model, side) so the
    live board — delete-and-rescored every pass — can't re-post the same signal."""
    rows = conn.execute("""
        SELECT DISTINCT p.game_id, p.model_id, p.pick_side, p.pick_label, p.sport,
               p.model_probability, p.edge, p.dk_odds, p.kelly_fraction,
               p.inning_at_pick, p.dk_bet_link, g.home_team, g.away_team
        FROM picks p
        LEFT JOIN games g ON g.game_id = p.game_id
        WHERE p.game_date = %s
          AND p.is_live = TRUE
          AND p.signal_type = 'BET'
          AND p.result IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM push_sent s
              WHERE s.lock_key = 'live:' || p.game_id || ':' || p.model_id || ':' || p.pick_side
                AND s.kind = 'discord_live'
          )
        ORDER BY p.game_id
    """, (target_date,)).fetchall()
    return [{
        "lock_key": f"live:{r[0]}:{r[1]}:{r[2]}",
        "label": r[3], "sport": r[4], "model_id": r[1],
        "prob": r[5], "edge": r[6], "dk_odds": r[7], "kelly": r[8],
        "inning": r[9], "bet_link": r[10], "home": r[11], "away": r[12],
    } for r in rows]


def notify_discord_live(target_date: str | None = None, dry_run: bool = False) -> int:
    """Post new in-play BET signals to the live channel (falling back to the
    sport's channel when DISCORD_WEBHOOK_LIVE isn't set). Called at the end of
    each live-scorer pass. Returns the number posted."""
    if target_date is None:
        target_date = date.today().isoformat()
    if not _configured():
        return 0

    conn = get_connection()
    try:
        signals = _new_live_signals(conn, target_date)
        if not signals:
            return 0

        by_url: dict[tuple[str, str], list[dict]] = {}
        for s in signals:
            url = config.DISCORD_WEBHOOK_LIVE or _webhook_for_sport(s["sport"])
            if url:
                by_url.setdefault((url, s["sport"]), []).append(s)
        if not by_url:
            logger.info(f"Discord(live): no webhook configured; skipped {len(signals)} signal(s)")
            return 0

        posted_total = 0
        sent_at = datetime.now(ET).isoformat()

        for (url, sport), group in by_url.items():
            capped = group[:config.DISCORD_MAX_EMBEDS_PER_RUN]

            if dry_run:
                for s in capped:
                    logger.info(f"[dry-run] discord(live) → {s['label']}")
                posted_total += len(capped)
                continue

            delivered = _post_picks(url, sport, capped, target_date, live=True)
            for s in capped[:delivered]:
                conn.execute(
                    "INSERT INTO push_sent (lock_key, kind, sent_at) "
                    "VALUES (%s, 'discord_live', %s) "
                    "ON CONFLICT (lock_key, kind) DO NOTHING",
                    (s["lock_key"], sent_at),
                )
            posted_total += delivered

        if not dry_run:
            conn.commit()
            if posted_total:
                logger.success(f"✓ Discord(live): posted {posted_total} signal(s)")
        return posted_total
    finally:
        conn.close()


# ── Daily results recap ──────────────────────────────────────────────────────

# ── Free pick of the day ─────────────────────────────────────────────────────

def _free_pick_candidates(conn, target_date: str) -> list[dict]:
    """Every locked signal for the date that clears the CURRENT action cut.

    Deliberately does NOT exclude signals already posted to a sport channel: the
    free channel is a different audience, and the pick of the day is expected to
    also appear in the full feed.
    """
    rows = conn.execute("""
        SELECT os.lock_key, os.pick_label, os.sport, os.dk_odds,
               os.kelly_fraction, g.home_team, g.away_team, g.commence_time
        FROM opening_signals os
        JOIN model_action_thresholds t ON t.model_id = os.model_id
        LEFT JOIN games g ON g.game_id = os.game_id
        WHERE os.game_date = %s
          AND os.lock_key NOT LIKE '%%:early'
          AND t.paused = FALSE
          AND os.model_probability >= t.min_prob
          AND (t.prob_only = TRUE OR os.edge >= COALESCE(t.min_edge, 0))
          AND (t.min_odds IS NULL OR os.dk_odds IS NULL OR os.dk_odds >= t.min_odds)
        ORDER BY os.lock_key
    """, (target_date,)).fetchall()
    return [{
        "lock_key": r[0], "label": r[1], "sport": r[2], "dk_odds": r[3],
        "kelly": r[4], "home": r[5], "away": r[6], "commence": r[7],
    } for r in rows]


def _pick_free(candidates: list[dict], priority=None) -> dict | None:
    """One pick at random, preferring the first priority sport that has any.

    NFL is first in the priority list, so the free pick becomes an NFL pick the
    moment the season starts producing signals — no date logic needed.
    """
    if not candidates:
        return None
    if priority is None:
        priority = config.DISCORD_FREE_PICK_PRIORITY
    for sport in priority:
        pool = [c for c in candidates if c["sport"] == sport]
        if pool:
            return random.choice(pool)
    return random.choice(candidates)


def notify_discord_free_pick(target_date: str | None = None,
                             dry_run: bool = False) -> int:
    """Post ONE random qualifying pick for the day to the free channel.

    Ledgered per date, so only the first pass of the day that finds a qualifying
    signal posts; the other ~41 passes are no-ops. Returns 1 if posted, else 0.
    """
    if target_date is None:
        target_date = datetime.now(ET).date().isoformat()

    url = config.DISCORD_WEBHOOK_FREE          # no DEFAULT fallback, by design
    if not url:
        return 0

    conn = get_connection()
    try:
        lock_key = f"discord_free:{target_date}"
        if conn.execute(
            "SELECT 1 FROM push_sent WHERE lock_key = %s AND kind = 'discord_free_pick'",
            (lock_key,),
        ).fetchone():
            return 0                       # already posted today

        pick = _pick_free(_free_pick_candidates(conn, target_date))
        if pick is None:
            logger.info(f"Discord(free): no qualifying signal for {target_date}")
            return 0

        pretty = datetime.fromisoformat(target_date).strftime("%a %b %-d").replace(" 0", " ")
        context = " · ".join(x for x in (
            _matchup(pick["sport"], pick["home"], pick["away"]),
            _game_time_et(pick["commence"]),
        ) if x)
        stake = fmt_units(units_for(pick.get("kelly")))
        embed = {
            "title": (f"{_SPORT_EMOJI.get(pick['sport'], chr(0x1F3AF))} "
                      f"Free Pick of the Day — {pretty}"),
            "color": _COLOR_SIGNAL,
            "fields": [{
                "name": pick["label"],
                "value": (f"{context}\n" if context else "")
                         + f"`{_american(pick['dk_odds'])}`\u2003·\u2003**{stake}**",
                "inline": False,
            }],
            "footer": {"text": f"{pick['sport']} · one free pick daily"},
        }

        if dry_run:
            logger.info(f"[dry-run] discord(free) {target_date} → {pick['label']}")
            return 0

        if not _post(url, {"embeds": [embed]}):
            return 0                       # un-ledgered: retried next pass

        conn.execute(
            "INSERT INTO push_sent (lock_key, kind, sent_at) "
            "VALUES (%s, 'discord_free_pick', %s) ON CONFLICT (lock_key, kind) DO NOTHING",
            (lock_key, datetime.now(ET).isoformat()),
        )
        conn.commit()
        logger.success(f"Discord(free): posted {pick['label']} ({pick['sport']})")
        return 1
    finally:
        conn.close()


def _settled_rows(conn, game_date: str) -> list[tuple]:
    """Settled BET picks for the date that cleared the action thresholds — the
    same universe the app's daily recap grades. Live picks are excluded (that
    board is tracked separately) as are NO_ACTION rows."""
    return conn.execute("""
        SELECT p.sport, p.model_id, p.result, p.kelly_fraction, p.dk_odds
        FROM picks p
        JOIN model_action_thresholds t ON t.model_id = p.model_id
        WHERE p.game_date = %s
          AND p.signal_type = 'BET'
          AND p.is_live IS NOT TRUE
          AND p.result IN ('WIN', 'LOSS', 'PUSH')
          AND t.paused = FALSE
          AND p.model_probability >= t.min_prob
          AND (t.prob_only = TRUE OR p.edge >= COALESCE(t.min_edge, 0))
          AND (t.min_odds IS NULL OR p.dk_odds IS NULL OR p.dk_odds >= t.min_odds)
    """, (game_date,)).fetchall()


# Prob-only picks (UFC method, some F5) carry no DK price. Settlement already
# grades those at -110, so the recap uses the same fallback rather than
# silently dropping them from the units math.
_NO_PRICE_FALLBACK = -110.0


def _decimal_odds(american) -> float:
    """American -> decimal. -110 -> 1.909, +150 -> 2.50."""
    try:
        a = float(american)
    except (TypeError, ValueError):
        a = _NO_PRICE_FALLBACK
    if a == 0:
        a = _NO_PRICE_FALLBACK
    return 1.0 + (a / 100.0 if a > 0 else 100.0 / abs(a))


def units_won(units_risked: float, american) -> float:
    """Units returned on a WIN. The wager is what you RISK; what you win depends
    on the price -- risk 1.1u at -110 to win 1.0u."""
    return units_risked * (_decimal_odds(american) - 1.0)


def _tally(rows: list[tuple]) -> dict:
    """Record over every graded pick; units over the ones that count.

    Units convention (Matt, 2026-08-27): the wager is the units RISKED, and the
    amount won depends on the odds -- risk 1.1u at -110 to win 1u. So a loss
    costs the full stake and a win pays stake x (decimal - 1). Record-only
    models (HR) contribute W-L but never units -- mirrors the app.
    """
    t = {"w": 0, "l": 0, "p": 0, "units": 0.0, "risked": 0.0, "record_only": 0}
    for _sport, model_id, result, kelly, dk_odds in rows:
        if result == "WIN":
            t["w"] += 1
        elif result == "LOSS":
            t["l"] += 1
        else:
            t["p"] += 1
        if model_id in _RECORD_ONLY_MODELS:
            t["record_only"] += 1
            continue
        stake = units_for(kelly)
        if result == "WIN":
            t["units"] += units_won(stake, dk_odds)
        elif result == "LOSS":
            t["units"] -= stake
        # PUSH returns the stake: no unit change.
        if result != "PUSH":
            t["risked"] += stake
    return t


def _tally_line(t: dict) -> str:
    rec = f"{t['w']}-{t['l']}" + (f"-{t['p']}" if t["p"] else "")
    if t["risked"] <= 0:
        return f"{rec} · record only"
    roi = t["units"] / t["risked"] * 100
    return f"{rec} · {t['units']:+.2f}u · {roi:+.1f}% ROI"


def notify_discord_results(game_date: str | None = None, dry_run: bool = False) -> int:
    """Post one recap of a settled day: overall record / P&L / ROI plus a
    per-sport breakdown. Ledgered per date so re-running settle can't repost,
    and refuses any date that is not already over. Returns 1 if posted, else 0."""
    if game_date is None:
        game_date = (datetime.now(ET).date() - timedelta(days=1)).isoformat()

    url = config.DISCORD_WEBHOOK_RESULTS or config.DISCORD_WEBHOOK_DEFAULT
    if not url:
        return 0

    # Only recap a day that is OVER. `--step settle` (run on every refresh pass
    # by scripts/refresh_pass.sh) settles TODAY, grading games as they finish —
    # recapping that would post a partial record mid-slate and then ledger it,
    # so the real end-of-day recap could never post. The daily 6am pipeline
    # settles yesterday, which is the run this is meant to fire on.
    if game_date >= datetime.now(ET).date().isoformat():
        return 0

    conn = get_connection()
    try:
        lock_key = f"discord_results:{game_date}"
        if conn.execute(
            "SELECT 1 FROM push_sent WHERE lock_key = %s AND kind = 'discord_results'",
            (lock_key,),
        ).fetchone():
            return 0

        rows = _settled_rows(conn, game_date)
        if not rows:
            logger.info(f"Discord(results): nothing settled for {game_date}")
            return 0

        overall = _tally(rows)
        by_sport: dict[str, list[tuple]] = {}
        for r in rows:
            by_sport.setdefault(r[0], []).append(r)

        fields = [{
            "name": sport,
            "value": _tally_line(_tally(group)),
            "inline": False,
        } for sport, group in sorted(by_sport.items())]

        color = (_COLOR_RESULTS_UP if overall["units"] > 0
                 else _COLOR_RESULTS_DOWN if overall["units"] < 0
                 else _COLOR_RESULTS_FLAT)

        pretty = datetime.fromisoformat(game_date).strftime("%a %b %-d").replace(" 0", " ")
        embed = {
            "title": f"📊 Results — {pretty}",
            "description": f"**{_tally_line(overall)}**  ·  {len(rows)} settled",
            "color": color,
            "fields": fields,
            "footer": {"text": "Paper trading · units risked per bet · 1u = 1% of roll"},
        }

        if dry_run:
            logger.info(f"[dry-run] discord(results) {game_date} → {_tally_line(overall)}")
            return 0

        if not _post(url, {"embeds": [embed]}):
            return 0                      # un-ledgered: retried on the next pass

        conn.execute(
            "INSERT INTO push_sent (lock_key, kind, sent_at) "
            "VALUES (%s, 'discord_results', %s) ON CONFLICT (lock_key, kind) DO NOTHING",
            (lock_key, datetime.now(ET).isoformat()),
        )
        conn.commit()
        logger.success(f"✓ Discord(results): posted recap for {game_date}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Discord webhook notifications")
    parser.add_argument("--date", default=None, help="game_date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print intended posts without sending or ledgering")
    parser.add_argument("--live", action="store_true", help="post in-play signals")
    parser.add_argument("--results", action="store_true",
                        help="post the daily recap (defaults to yesterday)")
    args = parser.parse_args()

    if args.live:
        n = notify_discord_live(target_date=args.date, dry_run=args.dry_run)
    elif args.results:
        n = notify_discord_results(game_date=args.date, dry_run=args.dry_run)
    else:
        n = notify_discord_signals(target_date=args.date, dry_run=args.dry_run)
    print(f"posted {n}")
