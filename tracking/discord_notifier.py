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

import math
import time
import random
from typing import NamedTuple
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
# Longest we will wait out a 429 in one attempt. Discord's per-route limits
# are sub-second; anything larger is a channel- or global-level limit that a
# retry loop should not try to sit through -- the next pass is minutes away
# and nothing is ledgered, so giving up is free. Bounded so delivery can
# never stall a pipeline step.
_MAX_429_WAIT = 30.0
# Truthy stand-in when a post succeeded but Discord returned no id (a bare
# 204). Keeps _post's boolean contract without pretending we can address
# the message later -- the delete path ignores it.
_POST_OK_NO_ID = "ok"
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
    # %I (not glibc's %-I): the dash form raises ValueError on Windows,
    # where the tests run. lstrip drops the leading zero portably.
    return local.strftime("%I:%M %p ET").lstrip("0")


# ── Units ────────────────────────────────────────────────────────────────────
# Stake is published in UNITS, never dollars. `kelly_fraction` is already stored
# on every pick/signal, so this needs no bankroll — which matters, because the
# compounded bankroll is a decaying number nobody should be reading a stake off.
#
# TWO NUMBERS, and the distinction is the whole point (Matt, 2026-08-28):
#
#   CONVICTION  1u..3u, "units to win". 3 is the highest-conviction play, 1 the
#               lowest. This is the handicapper convention: a "1 unit play" means
#               you are trying to WIN one unit, not risk one.
#   RISK        what you actually lay to win that, derived from the price:
#               risk = conviction / (decimal - 1). At -110 that is 1.1u to win
#               1u; at +150 it is 0.67u to win 1u. Without this the same "2u"
#               label meant wildly different money at -300 and at +200.
#
# The conviction scale is Kelly rescaled so the server's MAX_KELLY_FRACTION (5%)
# cap lands exactly on 3u — Kelly stays the ranking signal, it is only the
# denominator that changed. On the 431 qualifying picks since paper-trading
# started this spreads 38 / 124 / 138 / 106 / 25 across 1 / 1.5 / 2 / 2.5 / 3u,
# which is a real spread rather than everything piling on the cap.
#
# RISK IS HARD-CAPPED AT 3u ON A SINGLE EVENT. Un-capped "3 units to win" at the
# median -135 price would lay 4.05u, and 30% of the book would risk more than 3u
# (worst observed 6.5u) — which contradicts "never more than 3 units on 1 event".
# When the cap binds, `win` is RECOMPUTED from the capped risk so the pair is
# always internally consistent: a 3u-conviction play at -147 publishes as
# "risk 3u to win 2.04u", never as a 3u win it would not actually pay.
#
# Unpriced picks (prob-only markets — HR, UFC method, F5 O/U/RL) cannot be
# grossed up, so they publish the bare conviction and `priced` is False. Their
# P&L still grades at the -110 fallback settlement uses; that is a GRADING
# convention and deliberately not asserted as a price on the card.
UNIT_KELLY_FRACTION = 0.01   # legacy: 1u == 1% of roll. Kept for the old callers.
MAX_KELLY_FRACTION = 0.05    # mirrors config.MAX_KELLY_FRACTION (the server cap)
MAX_CONVICTION = 3.0         # highest-conviction play, in units to win
MIN_CONVICTION = 1.0         # lowest
MAX_RISK_UNITS = 3.0         # never lay more than this on one event
_DEFAULT_UNITS = 1.0         # kelly absent/zero (prob-only picks)


class UnitStake(NamedTuple):
    conviction: float   # 1..3, units to win before the risk cap
    risk: float         # units laid
    win: float          # units returned on a win (recomputed if the cap bound)
    capped: bool        # True when the 3u risk cap bound
    priced: bool        # False when no book price was available


def _decimal_or_none(american) -> float | None:
    """American -> decimal, or None when there is no usable price.

    Deliberately NOT the same function as _decimal_odds() further down. That one
    falls back to -110 because SETTLEMENT grades an unpriced pick at -110; this
    one refuses, because DISPLAY must never assert a price that did not exist.
    Same name for both is how the display path silently started quoting a
    fabricated -110 stake on prob-only picks — caught by a test, not review."""
    try:
        a = float(american)
    except (TypeError, ValueError):
        return None
    if a == 0:
        return None
    return 1.0 + (a / 100.0 if a > 0 else 100.0 / abs(a))


def conviction_for(kelly_fraction) -> float:
    """Kelly fraction -> conviction in UNITS TO WIN, 1u..3u to the nearest 0.5u."""
    try:
        k = float(kelly_fraction)
    except (TypeError, ValueError):
        return _DEFAULT_UNITS
    if k <= 0:
        return _DEFAULT_UNITS
    scaled = k / MAX_KELLY_FRACTION * MAX_CONVICTION
    return min(MAX_CONVICTION, max(MIN_CONVICTION, round(scaled * 2) / 2))


def stake_for(kelly_fraction, dk_odds=None) -> UnitStake:
    """Conviction + the price-aware risk/win pair. See the block comment above."""
    conviction = conviction_for(kelly_fraction)
    dec = _decimal_or_none(dk_odds)
    if dec is None or dec <= 1.0:
        # No price to gross up against — publish the bare conviction.
        return UnitStake(conviction, conviction, conviction, False, False)

    risk = conviction / (dec - 1.0)
    if risk > MAX_RISK_UNITS:
        risk = MAX_RISK_UNITS
        # Recompute the payout from the capped risk so the two never disagree.
        return UnitStake(conviction, risk, risk * (dec - 1.0), True, True)
    return UnitStake(conviction, risk, conviction, False, True)


def units_for(kelly_fraction, dk_odds=None) -> float:
    """
    Units LAID on a pick — what exposure sums and the recap tally should add up.
    Price-aware: at -110 a 1u-conviction play returns 1.1.
    """
    return stake_for(kelly_fraction, dk_odds).risk


def fmt_stake(stake: UnitStake) -> str:
    """'1.1u to win 1u'; just '1u' when the pick carries no price."""
    if not stake.priced:
        return fmt_units(stake.conviction)
    return f"{fmt_units(stake.risk)} to win {fmt_units(stake.win)}"


def fmt_units(u: float) -> str:
    """2.0 -> '2u', 3.5 -> '3.5u', 1.1 -> '1.1u'.

    Rounds HALF-UP at one decimal, explicitly. Neither language's default is
    safe here: Python's %.1f and round() are half-to-EVEN, JS toFixed is
    half-up, and a float like 2.0250000000000004 is not an integer so a naive
    isInteger check renders '2.0' on one side and '2' on the other. The mobile
    mirror uses the identical expression; tests/fixtures/unit_sizing_parity.json
    pins that they agree (it caught exactly these two divergences)."""
    n = math.floor(u * 10 + 0.5) / 10
    return (f"{n:.0f}" if n == int(n) else f"{n:.1f}") + "u"


_SPORT_EMOJI = {
    "MLB": "\u26be", "NFL": "\U0001f3c8", "NCAAF": "\U0001f3c8",
    "NBA": "\U0001f3c0", "WNBA": "\U0001f3c0", "NHL": "\U0001f3d2",
    "UFC": "\U0001f94a", "GOLF": "\u26f3",
}


# ── Delivery ─────────────────────────────────────────────────────────────────

def _message_url(url: str, message_id: str) -> str:
    """Webhook endpoint for one message it created."""
    return f"{url.split('?', 1)[0].rstrip('/')}/messages/{message_id}"


def _post(url: str, payload: dict) -> str | None:
    """POST one webhook message. Returns the MESSAGE ID on a confirmed success
    and None on failure, so the caller knows both whether it is safe to ledger
    and how to reach the message later. Retries a 429 for the duration Discord
    asks for; never raises.

    ?wait=true is what makes the id available: without it Discord answers 204
    with no body, the id is lost, and a posted message can never afterwards be
    edited or deleted (there is no endpoint to list a webhook's messages). That
    is exactly how the 2026-08-28 slate became uncorrectable in place.

    Callers still use this as a boolean -- a real id is always truthy, and None
    is falsy -- so `if not _post(...)` reads the same as before. Returning
    _POST_OK_NO_ID keeps that contract on the 204 path if ?wait= is ever
    stripped by a proxy.
    """
    sep = "&" if "?" in url else "?"
    wait_url = f"{url}{sep}wait=true"
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = requests.post(wait_url, json=payload, timeout=_POST_TIMEOUT)
            if resp.status_code in (200, 204):
                try:
                    return str(resp.json().get("id") or _POST_OK_NO_ID)
                except Exception:  # noqa: BLE001 — 204, or a body we can't parse
                    return _POST_OK_NO_ID
            if resp.status_code == 429:
                try:
                    wait = float(resp.json().get("retry_after", 1.0))
                except Exception:  # noqa: BLE001 — malformed 429 body
                    wait = 1.0
                # retry_after is seconds on the webhook API. Clamp so a bad or
                # very large value can't stall the pipeline step -- but LOG the
                # number Discord actually asked for. Without it "still
                # rate-limited after retries" is undiagnosable: you cannot tell
                # a 1-second burst limit from a multi-minute ban, and the fix
                # is different for each.
                logger.warning(f"Discord 429; Discord asked for {wait:.1f}s, "
                               f"waiting {min(max(wait, 0.5), _MAX_429_WAIT):.1f}s "
                               f"(attempt {attempt + 1}/{_MAX_RETRIES + 1})")
                time.sleep(min(max(wait, 0.5), _MAX_429_WAIT))
                continue
            if 500 <= resp.status_code < 600 and attempt < _MAX_RETRIES:
                time.sleep(1.0 * (attempt + 1))
                continue
            logger.error(f"Discord webhook rejected ({resp.status_code}): {resp.text[:200]}")
            return None
        except Exception as exc:  # noqa: BLE001 — delivery must never break a run
            if attempt < _MAX_RETRIES:
                time.sleep(1.0 * (attempt + 1))
                continue
            logger.error(f"Discord webhook post failed: {exc}")
            return False
    logger.error("Discord webhook still rate-limited after retries; will retry next pass")
    return None


def _post_picks(url: str, sport: str, signals: list[dict], game_date: str,
                live: bool = False,
                note: str | None = None) -> list[tuple[list[dict], str]]:
    """Post a slate as one embed per message (chunked at Discord's 25-field cap).

    Returns one (signals, message_id) pair per chunk that was CONFIRMED
    delivered — a partial failure reports only the chunks that landed, so the
    rest stay un-ledgered and retry. The message id travels with the signals so
    the ledger can record where each one went and a later correction can delete
    or edit it; len(sum of chunks) is the old integer return.
    """
    out: list[tuple[list[dict], str]] = []
    for i in range(0, len(signals), _FIELDS_PER_EMBED):
        chunk = signals[i:i + _FIELDS_PER_EMBED]
        # The note belongs to the slate, and only on the first chunk — repeating
        # it above every 25-pick page would be noise.
        embed = _picks_embed(sport, chunk, game_date, live=live,
                             note=note if i == 0 else None)
        message_id = _post(url, {"embeds": [embed]})
        if not message_id:
            break                      # stop: later chunks would post out of order
        out.append((chunk, message_id))
        time.sleep(_INTER_POST_SLEEP)
    return out


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


def _locked_signals(conn, target_date: str) -> list[dict]:
    """Every locked signal for the date that clears the CURRENT thresholds --
    ignoring the Discord ledger. Same rows _new_signals() draws from, minus the
    not-yet-posted filter, so a restatement covers the whole slate rather than
    whatever happens to be unposted."""
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
          AND os.lock_key NOT LIKE '%%:early'
          AND t.paused = FALSE
          AND os.model_probability >= t.min_prob
          AND (t.prob_only = TRUE OR os.edge >= COALESCE(t.min_edge, 0))
          AND (t.min_odds IS NULL OR os.dk_odds IS NULL OR os.dk_odds >= t.min_odds)
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
    # .get, not [] — context is decoration and MUST NOT be able to take a post
    # down. It could: the live producer built its dicts without a "commence"
    # key, so every notify_discord_live call since Discord shipped raised
    # KeyError into the caller's swallow-and-log, and not one live signal was
    # ever posted for any sport. The key is supplied now; this makes the class
    # of bug non-fatal rather than relying on three producers staying in sync.
    context = " \u00b7 ".join(x for x in (
        _matchup(s.get("sport"), s.get("home"), s.get("away")),
        _game_time_et(s.get("commence")),
    ) if x)
    stake = fmt_stake(stake_for(s.get("kelly"), s.get("dk_odds")))
    line = f"`{_american(s['dk_odds'])}`\u2003\u00b7\u2003**{stake}**"
    return {
        "name": s["label"],
        "value": f"{context}\n{line}" if context else line,
        "inline": False,
    }


def _picks_embed(sport: str, signals: list[dict], game_date: str,
                 live: bool = False, note: str | None = None) -> dict:
    """One embed per message holding the whole slate — far tidier in-channel than
    a stack of one-pick embeds.

    `note` renders above the picks as the embed description. It exists so a
    correction ships as ONE message: posting a "corrected stakes" header and the
    corrected slate separately means a failure between them leaves a header with
    nothing under it, and the retry posts a second header. One post is atomic.
    """
    emoji = _SPORT_EMOJI.get(sport, "\U0001f3af")
    try:
        pretty = datetime.fromisoformat(game_date).strftime("%a %b %d").replace(" 0", " ")
    except ValueError:
        pretty = game_date
    title = (f"\U0001f534 {emoji} {sport} LIVE" if live
             else f"{emoji} {sport} Picks \u00b7 {pretty}")
    embed = {
        "title": title,
        "color": _COLOR_LIVE if live else _COLOR_SIGNAL,
        "fields": [_signal_field(s) for s in signals],
    }
    if note:
        embed["description"] = note
    return embed


def _delete_message(url: str, message_id: str) -> bool:
    """Delete one message this webhook created. Best effort: a message already
    gone (404) counts as success, since the goal is only that it is not in the
    channel. Never raises."""
    if not message_id or message_id == _POST_OK_NO_ID:
        return False
    try:
        resp = requests.delete(_message_url(url, message_id), timeout=_POST_TIMEOUT)
        if resp.status_code in (200, 204, 404):
            return True
        logger.warning(f"Discord delete rejected ({resp.status_code}): "
                       f"{resp.text[:160]}")
    except Exception as exc:  # noqa: BLE001 — cleanup must never break a run
        logger.warning(f"Discord delete failed: {exc}")
    return False


def _delete_posted(conn, target_date: str, sport: str, kind: str) -> int:
    """Remove the messages a date's signals were posted in, for one sport.

    Only reaches messages whose id was CAPTURED at post time. Anything posted
    before message_id existed keeps NULL and is left alone rather than guessed
    at — which is exactly why the 2026-08-28 slate has to be cleared by hand.
    """
    url = _webhook_for_sport(sport)
    if not url:
        return 0
    try:
        rows = conn.execute("""
            SELECT DISTINCT ps.message_id
              FROM push_sent ps
              JOIN opening_signals os ON os.lock_key = ps.lock_key
             WHERE ps.kind = %s
               AND ps.message_id IS NOT NULL
               AND os.game_date = %s
               AND os.sport = %s
        """, (kind, target_date, sport)).fetchall()
    except Exception as exc:  # noqa: BLE001 — the column may not exist yet
        logger.warning(f"Discord: cannot read message ids ({exc}); "
                       f"leaving the original post in place")
        return 0
    removed = 0
    for (message_id,) in rows:
        if _delete_message(url, message_id):
            removed += 1
            time.sleep(_INTER_POST_SLEEP)
    return removed


# ── Restatement ──────────────────────────────────────────────────────────────
# Dates whose already-posted slate must be RE-POSTED once, corrected.
#
# Needed because a slate is fire-and-forget: _post() does not pass ?wait=true, so
# Discord never returns a message id and there is nothing to PATCH. Even with ids
# stored, editing would be the wrong call here -- silently rewriting a stake that
# people may already have bet off rereads history. A visibly labelled correction
# is the honest artifact for a betting channel.
#
# 2026-08-28: the morning slate published the OLD stake (kelly/1%, up to 5u,
# ignoring the price). The rule changed mid-day to a 1u-3u conviction in units TO
# WIN, grossed up by the odds and capped at 3u risk. Six signals were affected.
#
# This is deliberately an explicit date list, not a heuristic. It expires by
# itself: once the date is restated the ledger blocks it, and an empty set is a
# permanent no-op. Add a date here only for a change that alters what was already
# published.
DISCORD_RESTATE_DATES: frozenset[str] = frozenset({"2026-08-28"})

_RESTATE_NOTE = (
    "Unit sizing was updated after this slate first posted. Same picks, same "
    "prices \u2014 restated with the corrected stakes.\n"
    "Stakes are now **units to win**, grossed up by the price: at -110 you risk "
    "1.1u to win 1u. Conviction runs 1u-3u, and no single bet ever risks more "
    "than 3u."
)


def notify_discord_restate(target_date: str | None = None,
                           dry_run: bool = False) -> int:
    """Re-post a date's slate once, corrected and labelled as a restatement.

    Only fires for a date in DISCORD_RESTATE_DATES, and only once per sport --
    ledgered under kind 'discord_restate' so a later pass is a clean no-op. The
    original post is left in place; a channel that quietly loses a number people
    bet off is worse than one carrying a visible correction.

    Renders through the SAME _post_picks/_signal_field path as a normal slate, so
    a restated stake cannot drift from what the next slate would publish.
    """
    if target_date is None:
        target_date = date.today().isoformat()
    if target_date not in DISCORD_RESTATE_DATES or not _configured():
        return 0

    conn = get_connection()
    try:
        signals = _locked_signals(conn, target_date)
        if not signals:
            return 0

        by_sport: dict[str, list[dict]] = {}
        for sig in signals:
            by_sport.setdefault(sig["sport"], []).append(sig)

        posted = 0
        sent_at = datetime.now(ET).isoformat()
        for sport, group in sorted(by_sport.items()):
            lock_key = f"restate:{target_date}:{sport}"
            already = conn.execute(
                "SELECT 1 FROM push_sent WHERE lock_key = %s AND kind = 'discord_restate'",
                (lock_key,)).fetchone()
            if already:
                continue
            url = _webhook_for_sport(sport)
            if not url:
                continue

            if dry_run:
                logger.info(f"[dry-run] discord restate[{sport}] "
                            f"\u2192 {len(group)} signal(s)")
                posted += len(group)
                continue

            # Clear the stale post when we can reach it, so the channel ends
            # up showing the corrected slate ONLY. Messages posted before ids
            # were captured are unreachable; those fall through to the note,
            # which is why it explains itself rather than assuming the original
            # is gone.
            removed = _delete_posted(conn, target_date, sport, "discord_signal")
            if removed:
                logger.info(f"Discord restate[{sport}]: removed {removed} "
                            f"stale message(s)")

            # ONE message: the note rides on the slate embed. Posting them
            # separately meant a failure in between left a "corrected stakes"
            # header with nothing under it, and the retry added a second header
            # -- observed live on the first attempt, 2026-08-28 13:19.
            chunks = _post_picks(url, sport, group, target_date,
                                 note=_RESTATE_NOTE)
            delivered = sum(len(c) for c, _ in chunks)
            if delivered < len(group):
                logger.error(f"Discord restate[{sport}]: delivered "
                             f"{delivered}/{len(group)}; not ledgered, retries next pass")
                continue

            # Ledger only a COMPLETE restatement. A half-posted correction that
            # could never finish would be worse than the stale numbers.
            conn.execute(
                "INSERT INTO push_sent (lock_key, kind, sent_at) "
                "VALUES (%s, 'discord_restate', %s) "
                "ON CONFLICT (lock_key, kind) DO NOTHING",
                (lock_key, sent_at))
            posted += delivered

        # The free-pick channel carried the same stale stake. Its own ledger key
        # so a failure on either side doesn't consume the other.
        free_key = f"restate-free:{target_date}"
        free_url = config.DISCORD_WEBHOOK_FREE
        if free_url and not conn.execute(
            "SELECT 1 FROM push_sent WHERE lock_key = %s AND kind = 'discord_restate'",
            (free_key,)).fetchone():
            pick = _pick_free(_free_pick_candidates(conn, target_date))
            if pick is not None:
                if dry_run:
                    logger.info(f"[dry-run] discord restate(free) "
                                f"\u2192 {pick['label']}")
                else:
                    embed = _free_pick_embed(pick, target_date)
                    embed["description"] = _RESTATE_NOTE      # one atomic message
                if not dry_run and _post(free_url, {"embeds": [embed]}):
                    conn.execute(
                        "INSERT INTO push_sent (lock_key, kind, sent_at) "
                        "VALUES (%s, 'discord_restate', %s) "
                        "ON CONFLICT (lock_key, kind) DO NOTHING",
                        (free_key, sent_at))
                    posted += 1

        if not dry_run:
            conn.commit()
            if posted:
                logger.success(f"\u2713 Discord: restated {posted} signal(s) "
                               f"for {target_date}")
        return posted
    finally:
        conn.close()


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

            chunks = _post_picks(url, sport, capped, target_date)
            delivered = sum(len(c) for c, _ in chunks)
            if delivered < len(capped):
                logger.error(f"Discord[{sport}]: delivered {delivered}/{len(capped)}; "
                             f"undelivered signals retry next pass")

            # Ledger ONLY what actually landed, WITH the message it went out in
            # so a later correction can delete or edit that message.
            for chunk, message_id in chunks:
                for s in chunk:
                    conn.execute(
                        "INSERT INTO push_sent (lock_key, kind, sent_at, message_id) "
                        "VALUES (%s, 'discord_signal', %s, %s) "
                        "ON CONFLICT (lock_key, kind) DO NOTHING",
                        (s["lock_key"], sent_at, message_id),
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
               p.inning_at_pick, p.dk_bet_link, g.home_team, g.away_team,
               g.commence_time
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
        "commence": r[13],
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

            chunks = _post_picks(url, sport, capped, target_date, live=True)
            delivered = sum(len(c) for c, _ in chunks)
            for chunk, message_id in chunks:
                for s in chunk:
                    conn.execute(
                        "INSERT INTO push_sent (lock_key, kind, sent_at, message_id) "
                        "VALUES (%s, 'discord_live', %s, %s) "
                        "ON CONFLICT (lock_key, kind) DO NOTHING",
                        (s["lock_key"], sent_at, message_id),
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


def _free_pick_embed(pick: dict, target_date: str) -> dict:
    """The free pick as one embed. Extracted so notify_discord_restate() can
    re-render it through the exact same path — a correction that formats its own
    stake differently from the original would be its own bug."""
    pretty = datetime.fromisoformat(target_date).strftime("%a %b %d").replace(" 0", " ")
    context = " · ".join(x for x in (
        _matchup(pick["sport"], pick["home"], pick["away"]),
        _game_time_et(pick["commence"]),
    ) if x)
    stake = fmt_stake(stake_for(pick.get("kelly"), pick.get("dk_odds")))
    return {
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

        embed = _free_pick_embed(pick, target_date)

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


# Fallback for a malformed/zero price on a pick that DOES carry one. Picks with
# NO price at all are now excluded from the units math entirely (see _tally) --
# grading them at a -110 that was never available fabricates P&L.
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

    Units convention (Matt, 2026-08-28): a pick's CONVICTION is 1u-3u of units
    TO WIN, and the stake is grossed up by the price -- risk 1.1u at -110 to win
    1u -- capped so no single event ever lays more than MAX_RISK_UNITS. `stake`
    below is therefore the units RISKED: a loss costs it in full and a win pays
    stake x (decimal - 1), which is the conviction back (or the capped payout).
    Record-only models (HR) contribute W-L but never units -- mirrors the app.
    """
    t = {"w": 0, "l": 0, "p": 0, "units": 0.0, "risked": 0.0, "record_only": 0}
    for _sport, model_id, result, kelly, dk_odds in rows:
        if result == "WIN":
            t["w"] += 1
        elif result == "LOSS":
            t["l"] += 1
        else:
            t["p"] += 1
        # Record-only: counts toward W-L, never toward units.
        #   - _RECORD_ONLY_MODELS (HR): most picks have no real price, so units
        #     would be fabricated.
        #   - ANY pick with no book price: settlement grades it at -110, but
        #     that price never existed, so reporting units on it invents P&L.
        #     config.REQUIRE_DK_PRICE stops NEW ones being created; this keeps
        #     the historical ones out of the published numbers.
        if model_id in _RECORD_ONLY_MODELS or dk_odds is None:
            t["record_only"] += 1
            continue
        stake = units_for(kelly, dk_odds)
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

        pretty = datetime.fromisoformat(game_date).strftime("%a %b %d").replace(" 0", " ")
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
