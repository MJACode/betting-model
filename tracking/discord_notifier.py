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
import re
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


def _posted_et(ts_raw: str | None, *, seconds: bool = False) -> str:
    """When the pick was WRITTEN TO THE DATABASE, in ET.

    Matt, 2026-08-30: "the time it writes to the database, to know the first
    minute we get it." That is picks.created_at, and it is the earliest moment
    the bet existed anywhere — deliberately NOT opening_signals.locked_at (the
    capture step runs later in the pass, and on 2026-08-29 captured 3:18pm
    picks at 4:31pm) and not the book's own publish clock.

    Seconds only where they change a decision: a live total moves a full run on
    one scoring play, so the age of an in-play number matters to the second. A
    pre-game price is stable for hours, so the minute is the honest resolution.

    The ET DATE is prefixed whenever it isn't today's, because an NFL opener
    posts days before kickoff and a bare "9:31 AM ET" on a Saturday board would
    read as this morning.
    """
    if not ts_raw:
        return ""
    try:
        ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return ""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    local = ts.astimezone(ET)
    # %I/%m (not glibc's %-I/%-m): the dash form raises ValueError on Windows,
    # where the tests run. lstrip + explicit ints drop leading zeros portably.
    stamp = local.strftime("%I:%M:%S %p ET" if seconds else "%I:%M %p ET").lstrip("0")
    if local.date() != datetime.now(ET).date():
        # Comma, not the middle dot the field uses as its own separator --
        # "... \u00b7 posted Wed 8/26 \u00b7 10:02 PM ET" reads as two segments.
        stamp = f"{local.strftime('%a')} {local.month}/{local.day}, {stamp}"
    return stamp


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
#   CONVICTION  units to win -- currently FLAT 1u (see below). This is the
#               handicapper convention: a "1 unit play" means you are trying
#               to WIN one unit, not risk one.
#   RISK        what you actually lay to win that, derived from the price:
#               risk = conviction / (decimal - 1). At -110 that is 1.1u to win
#               1u; at +150 it is 0.67u to win 1u. Without this the same "2u"
#               label meant wildly different money at -300 and at +200.
#
# CONVICTION IS FLAT AT 1u (Matt, 2026-08-29, after seeing the record). It used
# to be Kelly rescaled so the 5% cap landed on 3u. Measured over 387 settled
# picks, that scale sized UP into the only losing bucket:
#
#     edge tier (within model)     n     win%      ROI
#     lowest                      129   69.0%   +16.8%
#     middle                      129   62.8%   +11.1%
#     HIGHEST                     129   50.4%    -7.2%
#
# The same decline appears on raw edge, on Kelly and on price, so it is not an
# artifact of one parameterisation: a large claimed edge over the book usually
# means the model is miscalibrated, not that the book is wrong. Inverting was
# rejected as well -- on a time split the top tier is +8.1% (Apr-Jun) then
# -32.3% (Jul-Aug), unstable rather than reliably backwards, and fitting a
# scale to 387 picks is the noise-fitting this repo has been burned by twice.
# Flat until a tier signal survives a time split. See conviction_for().
#
# RISK IS STILL HARD-CAPPED AT 3u ON A SINGLE EVENT, though at 1u to win the cap
# now needs a price below about -300 to bind. When it does, `win` is RECOMPUTED
# from the capped risk so the pair stays internally consistent: at -400 the pick
# publishes "risk 3u to win 0.75u", never a 1u win it would not actually pay.
#
# Unpriced picks (prob-only markets — HR, UFC method, F5 O/U/RL) cannot be
# grossed up, so they publish the bare conviction and `priced` is False. Their
# P&L still grades at the -110 fallback settlement uses; that is a GRADING
# convention and deliberately not asserted as a price on the card.
UNIT_KELLY_FRACTION = 0.01   # legacy: 1u == 1% of roll. Kept for the old callers.
MAX_KELLY_FRACTION = 0.05    # mirrors config.MAX_KELLY_FRACTION (the server cap)
MAX_CONVICTION = 3.0         # ceiling of the (currently unused) tier scale
FLAT_CONVICTION = 1.0        # every pick, until a tier survives a time split
MIN_CONVICTION = 1.0         # lowest
MAX_RISK_UNITS = 3.0         # never lay more than this on one event
_DEFAULT_UNITS = 1.0         # kelly absent/zero (prob-only picks)


class UnitStake(NamedTuple):
    conviction: float   # units to win, before the risk cap
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
    """Conviction in UNITS TO WIN. Currently FLAT 1u for every pick.

    FLAT, and this is an evidence decision, not a placeholder (Matt, 2026-08-29,
    after seeing the numbers). The scale used to be Kelly rescaled so the 5% cap
    landed on 3u. Measured over 387 settled picks since the record start, that
    scale sized UP into the only losing bucket:

        edge tier (within model)     n     win%      ROI
        lowest                      129   69.0%   +16.8%
        middle                      129   62.8%   +11.1%
        HIGHEST                     129   50.4%    -7.2%

    The same monotone decline shows on raw edge, on Kelly, and on price, so it
    is not an artifact of one parameterisation: when a model claims a large edge
    over the book it is usually the model that is miscalibrated, not the book.
    Sizing 3u on "highest EV" would have put the most money on the worst third.

    Inverting it was rejected as well. On a time split the top tier is +8.1%
    (Apr-Jun) and -32.3% (Jul-Aug) -- unstable, not reliably backwards -- and
    fitting a scale to 387 picks is the noise-fitting this repo has already been
    burned by twice (sessions 74 and 87). Only the bottom two tiers are positive
    in BOTH halves, and nothing separates them.

    So: flat, until a tier signal survives a time split. Re-open with a
    pre-specified signal, per-half records and a Wilson CI, per the §31 house
    rules. `kelly_fraction` is untouched on the pick and still carries the
    model's own conviction for whenever that day comes.
    """
    return FLAT_CONVICTION


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
    """2.0 -> '2u', 3.5 -> '3.5u', 1.15 -> '1.15u'.

    TWO decimals, trailing zeros trimmed. One decimal used to round the -115
    stake (1.15 laid to win 1) to '1.2u', which is a different bet from the one
    the model asked for; every negative price divides out exactly at two
    decimals, so this is the precision the number actually has.

    Rounds HALF-UP, explicitly. Neither language's default is safe here:
    Python's %.2f and round() are half-to-EVEN, JS toFixed is half-up, and a
    float like 2.0250000000000004 is not an integer so a naive isInteger check
    renders '2.00' on one side and '2' on the other. Trimming splits on the
    decimal point rather than rstrip('0'), which would turn '20.00' into '2'.
    The mobile mirror uses the identical expression;
    tests/fixtures/unit_sizing_parity.json pins that they agree (it caught
    exactly these divergences)."""
    n = math.floor(u * 100 + 0.5) / 100
    whole, frac = f"{n:.2f}".split(".")
    frac = frac.rstrip("0")
    return (f"{whole}.{frac}" if frac else whole) + "u"


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


# Every live post carries this. It is not a disclaimer, it is the measured
# property of the feed: The Odds API serves ONE cached in-play snapshot for
# ~44-46 seconds, and both its bulk and per-event endpoints return that same
# cache (36/36 paired reads on 2026-08-29 -- identical last_update, line and
# price). So our number can be up to ~45s behind the book's app at the instant
# we post, and no amount of polling changes that. A reader who opens DraftKings
# and sees a different total is seeing the feed's floor, not a bug, and the post
# should say so rather than let them discover it.
def _decimal_to_american(dec: float) -> int:
    """Decimal odds -> the American price, rounded to a price that STILL clears.

    The bound is a floor on the decimal: anything at or above it qualifies. So
    the rounding has to land on a number that is itself at or above it, which
    is the opposite direction for the two halves of the scale.

        minus money  |A| = 100/(dec-1), FLOOR it   (a larger |A| is a smaller
                     decimal, i.e. below the bound -- it would not qualify)
        plus money   A = (dec-1)*100,   CEIL it    (a smaller A is likewise
                     below the bound)

    Rounding the other way in either half publishes a price the model does not
    actually endorse, which is the whole thing this number exists to prevent.
    """
    if dec <= 1.0:
        return 0
    # The epsilon is not cosmetic. A bound that IS a round price -- a -140
    # MODEL_MIN_ODDS floor is decimal 1.714285714... -- comes back as
    # 139.99999999999997, and a bare floor would publish -139: a tighter number
    # than the model actually requires. 1e-9 of an American price is ~1e-11 of
    # implied probability, far below any distinction that exists at a book.
    if dec >= 2.0:
        return int(math.ceil((dec - 1.0) * 100.0 - 1e-9))
    return -int(math.floor(100.0 / (dec - 1.0) + 1e-9))


def price_bound(prob, model_id: str, min_edge, min_odds, posted_odds) -> int | None:
    """The WORST price at which this pick would still have been generated.

    Matt, 2026-08-30: "use the model to give a range of odds the bet is good
    to ... For example, live pick on X at -110 on DK, good to -120 otherwise
    pass." Nobody outside this repo knows what an edge of 0.14 means; everyone
    knows what -120 means. So the model's own gates are re-expressed as the one
    number a reader can act on at the book.

    Every price-dependent gate the scorer applies, solved for the price:

        edge floor   p - implied >= min_edge   ->  dec >= 1 / (p - min_edge)
        EV floor     p * dec - 1 >= min_ev     ->  dec >= (1 + min_ev) / p
        price floor  min_odds                  ->  dec >= decimal(min_odds)

    All three are lower bounds on the decimal, so the binding one is the
    LARGEST, and any price at or above it still qualifies. MAX_EDGE_CAP is
    deliberately not considered: it bounds prices that are too GOOD, which can
    never be the worse end of a range.

    Returns None rather than a guess when the inputs cannot support a bound, or
    when the bound comes out better than the price we actually posted -- that
    would mean the pick did not clear its own gate, and printing a range wider
    than the truth is worse than printing none.
    """
    try:
        p = float(prob)
    except (TypeError, ValueError):
        return None
    if not 0.0 < p < 1.0:
        return None

    required: list[float] = []
    try:
        if min_edge is not None and p - float(min_edge) > 0:
            required.append(1.0 / (p - float(min_edge)))
    except (TypeError, ValueError):
        pass
    ev_floor = config.MODEL_MIN_EV.get(model_id)
    if ev_floor is not None:
        required.append((1.0 + float(ev_floor)) / p)
    floor_dec = _decimal_or_none(min_odds)
    if floor_dec:
        required.append(floor_dec)
    if not required:
        return None

    bound = _decimal_to_american(max(required))
    if not bound:
        return None
    posted_dec = _decimal_or_none(posted_odds)
    if posted_dec is not None and posted_dec < max(required) - 1e-9:
        # The posted price is already worse than the bound: the pick cannot
        # have cleared its own gate, so say nothing rather than invent a range.
        return None
    return bound


LIVE_STALENESS_NOTE = (
    "\u26a0\ufe0f Live line \u2014 our odds feed refreshes about every 45s, so the "
    "book may already have moved. **Check DraftKings' current price against the "
    "\u201cgood to\u201d number on each pick**: at or better than it, the bet still "
    "holds; past it, pass."
)


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


def _lookahead_horizon(target_date: str) -> str:
    """Furthest-out game_date whose locked look-ahead signal may post today.

    Kept in step with tracking/opening_signals.capture_opening_signals: capture
    reaches forward this far, so the poster must too or the row it locks sits
    unposted until kickoff.

    One horizon for both look-ahead sports, deliberately: NFL_LOCK_AHEAD_DAYS
    and NCAAF_SCORE_AHEAD_DAYS are both 7, and taking the max means a change to
    either one can only ever widen this window, never orphan the other sport's
    rows. Two separate horizons here would be two things to keep in sync, and
    §1b's whole complaint is that per-sport copies drift.
    """
    return (date.fromisoformat(target_date)
            + timedelta(days=max(config.NFL_LOCK_AHEAD_DAYS,
                                 config.NCAAF_SCORE_AHEAD_DAYS))).isoformat()


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
               pk.dk_bet_link, pk.created_at, pk.best_book, pk.best_odds
        FROM opening_signals os
        JOIN model_action_thresholds t ON t.model_id = os.model_id
        LEFT JOIN games g ON g.game_id = os.game_id
        -- The pick row itself, for its betslip link and for WHEN IT WAS
        -- WRITTEN. os.locked_at is the capture step's clock, which runs later
        -- in the pass (3:18pm picks were captured at 4:31pm on 2026-08-29), so
        -- it would overstate how fresh a signal is. No fallback on purpose: a
        -- missing pick row publishes no stamp rather than a wrong one.
        LEFT JOIN LATERAL (
            -- best_book/best_odds ride along on the join that already reads
            -- this pick. DISPLAY ONLY: the BET decision stays on DraftKings
            -- (§6) because every threshold was swept on DK-implied edge, and a
            -- best-of-N price is ~2pp cheaper in implied probability.
            SELECT p.dk_bet_link, p.created_at, p.best_book, p.best_odds
            FROM picks p
            WHERE p.game_id = os.game_id
              AND p.model_id = os.model_id
              AND p.pick_side = os.pick_side
              AND COALESCE(p.player_id, '') = COALESCE(os.player_id, '')
              AND p.game_date = os.game_date
            ORDER BY p.created_at
            LIMIT 1
        ) pk ON TRUE
        WHERE (os.game_date = %s
               -- NFL and NCAAF picks are written days ahead and are the bet of
               -- record the moment they land, so waiting for game day would
               -- post them AFTER the number that justified them is gone. For
               -- the NFL opener rule that is fatal by construction: its entire
               -- edge IS the stale soft-book number, and by kickoff the book
               -- has corrected. Mirrors the capture window in
               -- tracking/opening_signals.py. The push_sent NOT EXISTS below
               -- still makes each signal post exactly once, so widening the
               -- date window cannot duplicate.
               --
               -- NCAAF was added 2026-08-30. It was omitted because look-ahead
               -- picks used to delete-and-rescore until game morning and so
               -- were genuinely unlocked -- but #311 made the pick lock general
               -- that same morning, and a locked NCAAF BET is now exactly as
               -- immutable as an NFL one. The visible cost of the gap: a
               -- Florida Atlantic +27.5 (-115) BET locked 2026-08-29 for a
               -- 2026-09-05 kickoff was never postable, and would not have
               -- become postable for seven days.
               OR (os.sport IN ('NFL', 'NCAAF', 'UFC')
                   AND os.game_date > %s AND os.game_date <= %s))
          -- The ':early' exclusion that used to sit here is retired with the
          -- suffix itself (2026-08-30, mike: "UFC: publish"). Historical rows
          -- carrying the old suffix are still filtered, so a shadow row locked
          -- before the change can never surface as a bet nobody was given.
          AND os.lock_key NOT LIKE '%%:early'
          -- NEVER DELIVER A PRE-GAME PICK FOR A GAME THAT HAS STARTED.
          --
          -- The pick was created pre-game and is a legitimate bet of record;
          -- what is wrong is POSTING it once the game is under way, because the
          -- reader cannot take it. On 2026-08-29 three F5 picks locked at 3:18pm
          -- ET, the 3:17pm refresh pass ABORTED before reaching the capture
          -- step, and the 4:17pm pass captured them at 4:31pm -- 20 minutes
          -- after two of those games had first pitch. Discord posted all three.
          --
          -- Deliberately at DELIVERY, not at capture: the pick still locks and
          -- still settles into the model record (it was a real signal at a real
          -- number), it simply is not announced as something to go and bet.
          -- Anything with no commence_time (golf tournaments, a missing games
          -- row) is unaffected -- an unknown start time must not silently
          -- suppress a signal.
          AND (g.commence_time IS NULL
               OR g.commence_time::timestamptz > NOW())
          AND t.paused = FALSE
          AND os.model_probability >= t.min_prob
          AND (t.prob_only = TRUE OR os.edge >= COALESCE(t.min_edge, 0))
          AND (t.min_odds IS NULL OR os.dk_odds IS NULL OR os.dk_odds >= t.min_odds)
          AND NOT EXISTS (
              SELECT 1 FROM push_sent s
              WHERE s.lock_key = os.lock_key AND s.kind = 'discord_signal'
          )
        ORDER BY os.locked_at
    """, (target_date, target_date, _lookahead_horizon(target_date))).fetchall()
    return [{
        "lock_key": r[0], "label": r[1], "sport": r[2], "model_id": r[3],
        "prob": r[4], "edge": r[5], "dk_odds": r[6], "kelly": r[7],
        "tier": r[8], "home": r[9], "away": r[10], "commence": r[11],
        "bet_link": r[12], "posted_at": r[13],
        "best_book": r[14], "best_odds": r[15],
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
               pk.dk_bet_link, pk.created_at
        FROM opening_signals os
        JOIN model_action_thresholds t ON t.model_id = os.model_id
        LEFT JOIN games g ON g.game_id = os.game_id
        -- The pick row itself, for its betslip link and for WHEN IT WAS
        -- WRITTEN. os.locked_at is the capture step's clock, which runs later
        -- in the pass (3:18pm picks were captured at 4:31pm on 2026-08-29), so
        -- it would overstate how fresh a signal is. No fallback on purpose: a
        -- missing pick row publishes no stamp rather than a wrong one.
        LEFT JOIN LATERAL (
            SELECT p.dk_bet_link, p.created_at
            FROM picks p
            WHERE p.game_id = os.game_id
              AND p.model_id = os.model_id
              AND p.pick_side = os.pick_side
              AND COALESCE(p.player_id, '') = COALESCE(os.player_id, '')
              AND p.game_date = os.game_date
            ORDER BY p.created_at
            LIMIT 1
        ) pk ON TRUE
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
        "bet_link": r[12], "posted_at": r[13],
    } for r in rows]


# ── Which book the quoted price came from ────────────────────────────────────
# Matt, 2026-08-29: post the sportsbook the line was found at, with every pick.
#
# A price with no book attached is not checkable. "Over 44.5 -115" invites
# "-115 where?", and the honest answer differs by model: nearly everything here
# is priced against DraftKings (config.ODDS_API_BOOKMAKER is the scoring book
# and every scorer hard-filters to it), but the standalone NFL rules
# deliberately line-shop and put the winning book in pick_label.
_BOOK_NAMES = {
    "draftkings": "DraftKings", "dk": "DraftKings",
    "fanduel": "FanDuel", "fd": "FanDuel",
    "betmgm": "BetMGM", "mgm": "BetMGM",
    "williamhill_us": "Caesars", "caesars": "Caesars", "czr": "Caesars",
    "espnbet": "ESPN BET", "espn": "ESPN BET",
    "betrivers": "BetRivers", "br": "BetRivers",
    "bovada": "Bovada", "bov": "Bovada",
    "pinnacle": "Pinnacle", "pin": "Pinnacle",
}

# "... (Opener -1.5 vs Pinnacle, MGM) · 1.00u" / "... (Wind 14 mph, FD)"
_LABEL_BOOK_RE = re.compile(r"\((?:[^()]*,\s*)([A-Za-z_]+)\)")


def book_for_pick(s: dict) -> str | None:
    """Human name of the book whose price is being published.

    Order matters. An explicitly recorded book wins; then the NFL label, which
    is the only place a line-shopped book is stored; then the platform default,
    but ONLY for a pick that actually carries a price -- a prob-only pick has no
    book because it has no quote, and naming one would assert a price that did
    not exist.
    """
    raw = (s.get("book") or "").strip().lower()
    if raw:
        return _BOOK_NAMES.get(raw, raw)
    label = s.get("label") or ""
    if (s.get("model_id") or "").startswith("nfl_"):
        m = _LABEL_BOOK_RE.search(label)
        if m:
            key = m.group(1).strip().lower()
            # Unknown abbrev is reported as-is rather than guessed into a
            # known book -- a label that names the wrong book is worse than
            # one that names an unfamiliar one.
            return _BOOK_NAMES.get(key, m.group(1).strip())
    if s.get("dk_odds") is None:
        return None
    return "DraftKings"


def better_price_note(s: dict) -> str | None:
    """"also -105 @ FanDuel" when another book beats the price we decided on.

    mike, 2026-08-30: "the bet should pick the best line for the bettor, across
    the main books, not just DK."

    DISPLAY ONLY, and the distinction is load-bearing. The models DECIDE on
    DraftKings (§6) because every threshold was swept on DK-implied edge, and a
    best-of-N price is systematically ~2pp cheaper in implied probability --
    adopting it as the qualifying price would loosen every cut by that much
    with nobody deciding to. So this changes where a reader should PLACE the
    bet, never whether the bet exists.

    Silent unless the other book is STRICTLY better and is a different book.
    Publishing "also -110 @ DraftKings" beside "-110" is noise, and publishing a
    worse price as an alternative is actively misleading.

    Where the money is: measured 2026-08-30 across 1,569 same-line prop
    comparisons, DK is the best price at the median, but one prop in three has
    1-30 cents available elsewhere and one in sixteen has 30+.
    """
    best = s.get("best_odds")
    book = (s.get("best_book") or "").strip().lower()
    if best is None or not book or book == config.ODDS_API_BOOKMAKER:
        return None
    posted = _decimal_or_none(s.get("dk_odds"))
    better = _decimal_or_none(best)
    if posted is None or better is None or better <= posted + 1e-9:
        return None
    return f"also `{_american(best)}` @ {_BOOK_NAMES.get(book, book)}"


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
    # A record-only model's money is zeroed in every record view and in the
    # recap, so publishing a stake for it invites a bet we do not count. Say so
    # instead. mlb_prop_batter_hr is the case: 103 settled picks, 19.4% win at
    # +393 average odds -- a longshot ledger, not a staking plan.
    if s.get("model_id") in _RECORD_ONLY_MODELS:
        stake = "record only"
    else:
        stake = fmt_stake(stake_for(s.get("kelly"), s.get("dk_odds")))
    book = book_for_pick(s)
    price = _american(s["dk_odds"])
    if book:
        price = f"{price} @ {book}"
    line = f"`{price}`\u2003\u00b7\u2003**{stake}**"
    # The price the bet survives to. On a live pick the book has very likely
    # moved by the time this is read, and "if it has moved past your edge" is
    # useless advice to someone who has never seen the edge -- it is not
    # published, deliberately. This is the same gate expressed as the one thing
    # a reader can check at the book. .get, so a producer that does not compute
    # it simply omits the clause.
    good_to = s.get("good_to")
    if good_to:
        line += f"\u2003\u00b7\u2003good to `{_american(good_to)}`"
    # Where the same bet is cheaper. Appended after the gate, so the reader sees
    # the decision price first and the shopping tip second.
    better = better_price_note(s)
    if better:
        line += f"\u2003\u00b7\u2003{better}"
    # WHEN we got it. Every pick here is a locked bet of record, so created_at
    # is the first moment the bet existed -- which is the reader's answer to
    # "how stale is this number?".
    #
    # It matters most in-play: a live MLB total moves a full run on one scoring
    # play, so a post that reads as "available now" sends someone to a book that
    # has already moved (CWS@MIN: published DK's real Over 9.5 -124; minutes
    # later DK was on 10.5). Pre-game picks carried no stamp until 2026-08-30 on
    # the grounds that a stable price makes it noise; Matt asked for it there
    # too, and it is the same question with a slower clock -- a signal locked at
    # the 6am run and read at noon has had six hours of line movement.
    posted = _posted_et(s.get("posted_at"), seconds=bool(s.get("live")))
    if posted:
        line += f"\u2003\u00b7\u2003posted {posted}"
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

# Dates whose RESULTS recap was published over an incomplete pick universe and
# should be posted again, corrected. Separate from DISCORD_RESTATE_DATES above:
# that one restates a SLATE (what to bet), this one restates a RECORD (what
# happened). A date restates once -- its own ledger kind blocks the rest.
DISCORD_RESULTS_RESTATE_DATES: frozenset[str] = frozenset({"2026-08-29"})

_RESULTS_RESTATE_NOTE = (
    "Restated. The original recap counted PRE-GAME picks only \u2014 in-play "
    "picks were excluded from the record while the live board still re-priced "
    "every pass. They lock at first signal now, so they are the bet of record "
    "and they count. Same picks, same results; this is the full day.\n"
    "Closing-line value stays pre-game only: an in-play price has no "
    "meaningful close to be measured against."
)

_RESTATE_NOTE = (
    "Unit sizing was updated after this slate first posted. Same picks, same "
    "prices \u2014 restated with the corrected stakes.\n"
    "Stakes are **units to win**, grossed up by the price: at -110 you risk "
    "1.1u to win 1u. Every pick is 1u to win \u2014 the tiered 1u-3u scale was "
    "retired because, measured over the settled record, the picks it sized up "
    "were the ones that lost."
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
               g.commence_time, p.created_at, t.min_edge, t.min_odds
        FROM picks p
        LEFT JOIN games g ON g.game_id = p.game_id
        -- The model's own gates, from the same table the app's action filter
        -- reads, so the "good to" price in the channel and the cut the scorer
        -- applied cannot drift apart.
        LEFT JOIN model_action_thresholds t ON t.model_id = p.model_id
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
        "commence": r[13], "posted_at": r[14], "live": True,
        "good_to": price_bound(r[5], r[1], r[15], r[16], r[7]),
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

            chunks = _post_picks(url, sport, capped, target_date, live=True,
                                 note=LIVE_STALENESS_NOTE)
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
               os.kelly_fraction, g.home_team, g.away_team, g.commence_time,
               pk.created_at
        FROM opening_signals os
        JOIN model_action_thresholds t ON t.model_id = os.model_id
        LEFT JOIN games g ON g.game_id = os.game_id
        LEFT JOIN LATERAL (
            SELECT p.created_at
            FROM picks p
            WHERE p.game_id = os.game_id
              AND p.model_id = os.model_id
              AND p.pick_side = os.pick_side
              AND COALESCE(p.player_id, '') = COALESCE(os.player_id, '')
              AND p.game_date = os.game_date
            ORDER BY p.created_at
            LIMIT 1
        ) pk ON TRUE
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
        "posted_at": r[8],
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
    line = f"`{_american(pick['dk_odds'])}`\u2003·\u2003**{stake}**"
    posted = _posted_et(pick.get("posted_at"))
    if posted:
        line += f"\u2003·\u2003posted {posted}"
    return {
        "title": (f"{_SPORT_EMOJI.get(pick['sport'], chr(0x1F3AF))} "
                  f"Free Pick of the Day — {pretty}"),
        "color": _COLOR_SIGNAL,
        "fields": [{
            "name": pick["label"],
            "value": (f"{context}\n" if context else "") + line,
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

        # The chosen pick's lock_key is recorded in message_id (empty on this
        # kind, and this is what it is for now): X's free pick reads it back and
        # publishes THE SAME PICK. Two independent random.choice calls over a
        # 22-candidate pool agreed about 4% of the time, so the free pick tweeted
        # publicly was almost never the free pick the free channel was given —
        # against this module's own charter that X gets exactly what the free
        # Discord channel gets. See tracking/x_publisher.notify_x_free_pick.
        conn.execute(
            "INSERT INTO push_sent (lock_key, kind, sent_at, message_id) "
            "VALUES (%s, 'discord_free_pick', %s, %s) "
            "ON CONFLICT (lock_key, kind) DO NOTHING",
            (lock_key, datetime.now(ET).isoformat(), pick["lock_key"]),
        )
        conn.commit()
        logger.success(f"Discord(free): posted {pick['label']} ({pick['sport']})")
        return 1
    finally:
        conn.close()


# The pick universe every published number is computed over: settled BETs that
# cleared the action thresholds. One query, two windows, so the daily and
# all-time figures can never be computed on different populations.
#
# IN-PLAY PICKS COUNT. They were excluded while the live board delete-and-
# rescored every pass, when a live row was a moving quote rather than a bet
# anyone was given. Since the first-signal lock they are the bet of record --
# locked at their line and price, settled through the same path -- and dropping
# them understated 2026-08-29 by 23 of its 31 BET picks.
#
# But `is_live` alone does NOT mean "in-play bet". The column carries a second
# population: the session-114 repair rows -- ~14k PRE-GAME prop picks flagged
# is_live because they were scored against an in-play price after first pitch.
# 65 of those are settled and clear current thresholds (20-45, -$1,493), so
# without the model_id clause below the recap publishes fabricated losses that
# session 114 removed from every record. Only model_id separates the two:
# `%%\_live\_%%` matches all 5 live models and none of the 17 repaired prop
# models. The doubled %% are psycopg2 placeholder escaping, not part of the
# pattern, and the string is RAW so the LIKE-escaped \_ survives verbatim (an
# unescaped \_ is also an invalid Python escape on 3.12+).
#
# CLV is the one figure in-play picks stay out of, and p.is_live is selected so
# that exclusion is EXPLICIT rather than resting on clv_pct happening to be
# NULL. An in-play price has no meaningful closing line to be measured against.
#
# Retired models need no clause: the JOIN drops them, because a retirement
# deletes the model_action_thresholds row.
_SETTLED_SQL = r"""
        SELECT p.sport, p.model_id, p.result, p.kelly_fraction, p.dk_odds,
               p.clv_pct, p.is_live
        FROM picks p
        JOIN model_action_thresholds t ON t.model_id = p.model_id
        WHERE p.game_date {window}
          AND p.signal_type = 'BET'
          AND (p.is_live IS NOT TRUE OR p.model_id LIKE '%%\_live\_%%')
          AND p.result IN ('WIN', 'LOSS', 'PUSH')
          AND t.paused = FALSE
          AND p.model_probability >= t.min_prob
          AND (t.prob_only = TRUE OR p.edge >= COALESCE(t.min_edge, 0))
          AND (t.min_odds IS NULL OR p.dk_odds IS NULL OR p.dk_odds >= t.min_odds)
"""


def _settled_rows(conn, game_date: str) -> list[tuple]:
    """One settled day."""
    return conn.execute(_SETTLED_SQL.format(window="= %s"),
                        (game_date,)).fetchall()


def _settled_rows_since(conn, start_date: str, through: str) -> list[tuple]:
    """Every settled day in a window — the all-time block.

    Bounded ABOVE by the recapped date so the all-time figure is as of that
    recap and never quietly includes a later day: a number published on Monday
    must still reproduce on Friday."""
    return conn.execute(
        _SETTLED_SQL.format(window="BETWEEN %s AND %s"),
        (start_date, through)).fetchall()


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
    t = {"w": 0, "l": 0, "p": 0, "units": 0.0, "risked": 0.0, "record_only": 0,
         "clv_n": 0, "clv_beat": 0, "live": 0}
    for row in rows:
        _sport, model_id, result, kelly, dk_odds, clv = row[:6]
        # is_live is optional so a caller passing the older 6-tuple still works.
        is_live = bool(row[6]) if len(row) > 6 else False
        if is_live:
            t["live"] += 1
        # CLV: did the price move TOWARD us after we bet? Positive clv_pct means
        # we beat the close. IN-PLAY PICKS ARE EXCLUDED -- mike, 2026-08-30,
        # "CLV does not apply to those picks", and he is right: an in-play price
        # has no meaningful close to be measured against. _capture_clv already
        # skips them at source, so this is belt-and-braces rather than the only
        # guard -- but a figure this easy to misread deserves both.
        if clv is not None and not is_live:
            t["clv_n"] += 1
            if float(clv) > 0:
                t["clv_beat"] += 1
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


def clv_line(t: dict) -> str:
    """Share of graded bets that beat the closing line, with its DENOMINATOR.

    The denominator is not decoration: CLV is only captured for game-level picks
    that have a closing DK price, which today is a minority of settled bets
    (props price in a different table). Publishing a bare percentage would imply
    it covers every bet in the record beside it."""
    if not t.get("clv_n"):
        return ""
    pct = t["clv_beat"] / t["clv_n"] * 100
    return f"{pct:.0f}% beat close ({t['clv_beat']}/{t['clv_n']})"


def _tally_line(t: dict, with_clv: bool = False) -> str:
    rec = f"{t['w']}-{t['l']}" + (f"-{t['p']}" if t["p"] else "")
    if t["risked"] <= 0:
        base = f"{rec} · record only"
    else:
        roi = t["units"] / t["risked"] * 100
        base = f"{rec} · {t['units']:+.2f}u · {roi:+.1f}% ROI"
    # How the day split. Both halves count identically, but a record carried by
    # in-play bets reads very differently from one carried by the morning board,
    # and the number means little without saying which.
    if t.get("live"):
        base += f" · {t['live']} in-play"
    clv = clv_line(t) if with_clv else ""
    return f"{base} · {clv}" if clv else base


def snapshot_rows(game_date: str, published_at: str,
                  daily_overall: dict, daily_by_sport: dict,
                  all_overall: dict, all_by_sport: dict,
                  daily_settled: int, all_settled: int) -> list[tuple]:
    """The recap's numbers, flattened for storage — one row per
    (scope, sport), sport NULL for the overall line."""
    out = []

    def add(scope, sport, t, settled):
        roi = (t["units"] / t["risked"] * 100) if t["risked"] > 0 else None
        clv = (t["clv_beat"] / t["clv_n"] * 100) if t.get("clv_n") else None
        out.append((game_date, scope, sport, t["w"], t["l"], t["p"], settled,
                    t["record_only"], round(t["units"], 4),
                    round(t["risked"], 4), None if roi is None else round(roi, 4),
                    t.get("clv_n", 0), t.get("clv_beat", 0),
                    None if clv is None else round(clv, 4), published_at))

    add("daily", None, daily_overall, daily_settled)
    for sport, group in sorted(daily_by_sport.items()):
        add("daily", sport, _tally(group), len(group))
    add("all_time", None, all_overall, all_settled)
    for sport, group in sorted(all_by_sport.items()):
        add("all_time", sport, _tally(group), len(group))
    return out


def _store_snapshot(conn, rows: list[tuple]) -> None:
    """Persist the published figures. Non-fatal: an audit trail must never stop
    the recap being posted -- the post is the product, this is the receipt."""
    try:
        conn.executemany("""
            INSERT INTO results_snapshots (
                game_date, scope, sport, wins, losses, pushes, settled,
                record_only, units, risked, roi_pct, clv_graded, clv_beat,
                clv_pct, published_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (game_date, scope, COALESCE(sport, ''))
            DO UPDATE SET
                wins=EXCLUDED.wins, losses=EXCLUDED.losses,
                pushes=EXCLUDED.pushes, settled=EXCLUDED.settled,
                record_only=EXCLUDED.record_only, units=EXCLUDED.units,
                risked=EXCLUDED.risked, roi_pct=EXCLUDED.roi_pct,
                clv_graded=EXCLUDED.clv_graded, clv_beat=EXCLUDED.clv_beat,
                clv_pct=EXCLUDED.clv_pct, published_at=EXCLUDED.published_at
        """, rows)
    except Exception as exc:                         # noqa: BLE001
        logger.warning(f"results snapshot not stored (non-fatal): {exc}")


def notify_discord_results(game_date: str | None = None, dry_run: bool = False,
                           restate: bool = False) -> int:
    """Post one recap of a settled day: overall record / P&L / ROI plus a
    per-sport breakdown. Ledgered per date so re-running settle can't repost,
    and refuses any date that is not already over. Returns 1 if posted, else 0.

    `restate` re-posts a date whose original recap was computed over an
    incomplete pick universe, under its own ledger kind so it fires exactly
    once and cannot collide with the original. The original is left in place:
    a channel that quietly loses a number people saw is worse than one carrying
    a visible correction. Renders through the SAME path as a normal recap, so a
    restated figure cannot drift from what tomorrow's recap would publish.
    """
    if game_date is None:
        game_date = (datetime.now(ET).date() - timedelta(days=1)).isoformat()
    if restate and game_date not in DISCORD_RESULTS_RESTATE_DATES:
        return 0

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
        kind = "discord_results_restate" if restate else "discord_results"
        lock_key = f"{kind}:{game_date}" if restate else f"discord_results:{game_date}"
        if conn.execute(
            "SELECT 1 FROM push_sent WHERE lock_key = %s AND kind = %s",
            (lock_key, kind),
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
            "value": _tally_line(_tally(group), with_clv=True),
            "inline": False,
        } for sport, group in sorted(by_sport.items())]

        # ALL-TIME, as of this recap. A day on its own says nothing about
        # whether the thing works -- 4-3 is noise either way -- so the running
        # record travels with it, broken out by sport for the same reason the
        # day is.
        all_rows = _settled_rows_since(conn, config.PAPER_TRADING_START, game_date)
        all_overall = _tally(all_rows)
        all_by_sport: dict[str, list[tuple]] = {}
        for r in all_rows:
            all_by_sport.setdefault(r[0], []).append(r)
        fields.append({
            "name": f"\u200b\nAll-time  ·  since {config.PAPER_TRADING_START}",
            "value": f"**{_tally_line(all_overall, with_clv=True)}**  ·  "
                     f"{len(all_rows)} settled",
            "inline": False,
        })
        for sport, group in sorted(all_by_sport.items()):
            fields.append({
                "name": f"{sport} (all-time)",
                "value": _tally_line(_tally(group), with_clv=True),
                "inline": False,
            })

        color = (_COLOR_RESULTS_UP if overall["units"] > 0
                 else _COLOR_RESULTS_DOWN if overall["units"] < 0
                 else _COLOR_RESULTS_FLAT)

        pretty = datetime.fromisoformat(game_date).strftime("%a %b %d").replace(" 0", " ")
        embed = {
            "title": (f"\U0001F4CA Results — {pretty}"
                      + ("  ·  restated" if restate else "")),
            "description": (
                (_RESULTS_RESTATE_NOTE + "\n\n") if restate else ""
            ) + f"**{_tally_line(overall, with_clv=True)}**  ·  "
                f"{len(rows)} settled",
            "color": color,
            "fields": fields,
        }

        if dry_run:
            logger.info(f"[dry-run] discord(results) {game_date} → {_tally_line(overall)}")
            return 0

        if not _post(url, {"embeds": [embed]}):
            return 0                      # un-ledgered: retried on the next pass

        published_at = datetime.now(ET).isoformat()
        conn.execute(
            "INSERT INTO push_sent (lock_key, kind, sent_at) "
            "VALUES (%s, %s, %s) ON CONFLICT (lock_key, kind) DO NOTHING",
            (lock_key, kind, published_at),
        )
        # The snapshot is the published record for that date, so a restatement
        # OVERWRITES it rather than adding a second row: the corrected numbers
        # are the ones that should reproduce later, and two rows for one date
        # would leave which-is-authoritative to whoever reads them next.
        _store_snapshot(conn, snapshot_rows(
            game_date, published_at, overall, by_sport, all_overall,
            all_by_sport, len(rows), len(all_rows)))
        conn.commit()
        logger.success(
            f"✓ Discord(results): {'restated' if restate else 'posted'} "
            f"recap for {game_date}")
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
