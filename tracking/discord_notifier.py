"""
Discord webhook notifications — routes generated picks to per-sport channels.

Producers, each independently enabled by whether its webhook is configured:

  • notify_discord_signals — a pick posts to its SPORT's channel the first time
    it clears the action thresholds (the same cut the app's Signals tab and the
    §16 mobile query use). Reads `picks`, not `opening_signals`, so what posts is
    the same set the app shows.
  • notify_discord_live    — in-play BET signals from the live loops (MLB,
    NCAAF, and the NFL in-play worker), to the SPORT'S live channel
    (DISCORD_WEBHOOK_LIVE_{SPORT}; mike, 2026-09-09), else the shared live
    channel, else the sport's pre-game channel.
  • notify_discord_results — one morning recap after settlement: yesterday's
    record, P&L and ROI, overall and by sport. The same webhook also gets
    the Monday weekly recap and the first-Monday monthly recap.
  • notify_discord_void — one gray notice per sport for picks that are already
    VOID and already posted. Writes push_sent kind discord_void only after
    Discord accepts the message. Does not edit or delete the original post.

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

import json
import math
import os
import re
import time
import random
from typing import NamedTuple
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from loguru import logger

import config
from data.db import get_connection
from tracking.publish_lock import (
    DISCORD_LIVE_LOCK, DISCORD_SIGNALS_LOCK, publish_lock,
)
from tracking.publish_filters import captured_not_voided_sql, live_publishable_sql
from tracking.publish_keys import (
    SIGNAL_LEDGER_SQL, channel_lock_held_sql, live_lock_key_sql,
)
from tracking.publish_keys import key_partition_sql, lock_key_sql, posted_sql
from tracking.postable import still_pre_game as _still_pre_game
# Nothing is sent whose label disagrees with its side and line (2026-09-12).
from tracking.pick_integrity import refuse_mismatched

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
_COLOR_VOID = 0x95A5A6          # gray — a void notice is not a bet

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
    "NBA": "\U0001f3c0", "WNBA": "\U0001f3c0", "NCAAB": "\U0001f3c0", "NHL": "\U0001f3d2",
    "UFC": "\U0001f94a", "GOLF": "\u26f3",
}


# ── Delivery ─────────────────────────────────────────────────────────────────

def _message_url(url: str, message_id: str) -> str:
    """Webhook endpoint for one message it created."""
    return f"{url.split('?', 1)[0].rstrip('/')}/messages/{message_id}"


# urllib3 puts the request URL in timeout and connection errors. A webhook
# URL is the credential, so a delivery log must not keep it.
_WEBHOOK_IN_TEXT = re.compile(
    r"(?:https?://[^\s'\"<>]+)?/api/webhooks/\d+/[A-Za-z0-9._=\-]+",
    re.IGNORECASE,
)


def _redact_delivery_error(exc: BaseException, url: str) -> str:
    """Exception type plus message, with every webhook URL removed."""
    text = str(exc)
    bare = url.split("?", 1)[0]
    for secret in (url, bare):
        if secret:
            text = text.replace(secret, "[webhook]")
    text = _WEBHOOK_IN_TEXT.sub("[webhook]", text)
    return f"{type(exc).__name__}: {text}"


class _Posted(str):
    """One confirmed webhook result. status and detail belong to this call.

    A module dict of the last outcome is shared by every caller in the
    process, so two posts can record each other's HTTP status. This object
    is the outcome of the call that returned it.
    """

    status: int | None
    detail: str

    def __new__(cls, text: str, status, detail: str = ""):
        obj = str.__new__(cls, text)
        obj.status = status
        obj.detail = detail or ""
        return obj


class _Rejected:
    """A webhook answer that was not a delivery. Falsy, and not a message id."""

    def __init__(self, status, detail: str = ""):
        self.status = status
        self.detail = detail or ""

    def __bool__(self) -> bool:
        return False


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
                    mid = str(resp.json().get("id") or "")
                except Exception:  # noqa: BLE001 — 204, or a body we can't parse
                    mid = ""
                if mid:
                    return _Posted(mid, resp.status_code, "")
                return _Posted(_POST_OK_NO_ID, resp.status_code, "no message id")
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
            return _Rejected(resp.status_code, _WEBHOOK_IN_TEXT.sub(
                "[webhook]", resp.text[:180]))
        except Exception as exc:  # noqa: BLE001 — delivery must never break a run
            # A timeout (or a dropped connection) can mean Discord already
            # accepted this POST and the response never arrived. Retrying
            # then posts a second copy of the same message. Left as it is:
            # this retry predates the void notice, and changing it would
            # change every producer that calls _post.
            if attempt < _MAX_RETRIES:
                time.sleep(1.0 * (attempt + 1))
                continue
            logger.error(f"Discord webhook post failed: {_redact_delivery_error(exc, url)}")
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


def _honest(model_id, prob):
    """The promoted calibration map applied (models.honest_ev); the raw
    number when there is no map or the lookup fails. Never raises."""
    try:
        from models.honest_ev import honest_probability
        return honest_probability(str(model_id), float(prob))
    except Exception:  # noqa: BLE001 - a display bound must not stop a post
        return prob


def price_bound(prob, model_id: str, min_edge, min_odds, posted_odds,
                prop_market: str | None = None) -> int | None:
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
    # The platform's global EV floor or the model's own, whichever is higher
    # (config.min_ev_for, 2026-09-19). `prob` is the CALIBRATED probability
    # where the pick carries one -- the number the floor was applied to.
    # A model with a floor per market (config.MODEL_MARKET_EV_FLOOR) is bounded
    # at the pick's own market's floor, the cut it actually cleared.
    ev_floor = config.min_ev_for(model_id, prop_market)
    if ev_floor > 0:
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
    # GROUPED BY THE PICKS' OWN DATE, and `game_date` is only the fallback for
    # a row that has none. Before the look-ahead every pick in a pass was for
    # the day the pass ran, so one header date was always right; now a single
    # pass can carry today's slate and tomorrow's, and stamping both with the
    # run date announces tomorrow's pick under today's date. That is not a
    # cosmetic error -- the reader uses the header to know when to place it.
    #
    # Groups are emitted in date order, so today's slate always precedes
    # tomorrow's in the channel.
    groups: dict = {}
    for sig in signals:
        groups.setdefault(sig.get("game_date") or game_date, []).append(sig)

    out: list[tuple[list[dict], str]] = []
    first = True
    for date_key in sorted(groups):
        day = groups[date_key]
        for i in range(0, len(day), _FIELDS_PER_EMBED):
            chunk = day[i:i + _FIELDS_PER_EMBED]
            # The note belongs to the slate, and only on the first chunk of the
            # first day — repeating it above every 25-pick page would be noise.
            embed = _picks_embed(sport, chunk, date_key, live=live,
                                 note=note if first else None)
            first = False
            message_id = _post(url, {"embeds": [embed]})
            if not message_id:
                return out             # stop: later chunks would post out of order
            out.append((chunk, message_id))
            time.sleep(_INTER_POST_SLEEP)
    return out


def _webhook_for_sport(sport: str) -> str | None:
    return (config.DISCORD_WEBHOOKS.get(sport) or _channel_webhook(sport)
            or config.DISCORD_WEBHOOK_DEFAULT or None)


# A sport that names its channel (config.DISCORD_CHANNELS, a channel id) and no
# webhook: the bot token finds or makes the channel's webhook. Cached per
# process; the URL is a bearer credential, so it lives in memory only and no
# log line, error or job result ever carries it.
_DISCORD_API = "https://discord.com/api/v10"
_CHANNEL_HOOK_NAME = "Signalbase picks"
_CHANNEL_HOOKS: dict = {}


def _channel_webhook(sport: str) -> str | None:
    """The webhook URL for `sport`'s configured channel, or None.

    Reuses a webhook in that channel that the bot itself created (its `user`
    is the bot), else creates one. Needs DISCORD_BOT_TOKEN with Manage
    Webhooks on the channel. A failure is logged by status code and returns
    None, so the sport is skipped exactly as an unset webhook is (its picks
    stay unsent and post once the channel resolves)."""
    channel = config.DISCORD_CHANNELS.get(sport)
    if not channel:
        return None
    if sport in _CHANNEL_HOOKS:
        return _CHANNEL_HOOKS[sport]
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        return None
    headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
    try:
        me = requests.get(f"{_DISCORD_API}/users/@me", headers=headers, timeout=15)
        if me.status_code != 200:
            logger.error(f"Discord: bot identity read failed for {sport} ({me.status_code})")
            return None
        bot_id = str(me.json().get("id"))
        got = requests.get(f"{_DISCORD_API}/channels/{channel}/webhooks", headers=headers,
                           timeout=15)
        if got.status_code != 200:
            logger.error(f"Discord: listing webhooks of the {sport} channel failed "
                         f"({got.status_code}); the bot needs Manage Webhooks there")
            return None
        hook = next((h for h in (got.json() or [])
                     if str((h.get("user") or {}).get("id")) == bot_id and h.get("token")), None)
        if hook is None:
            made = requests.post(f"{_DISCORD_API}/channels/{channel}/webhooks", headers=headers,
                                 json={"name": _CHANNEL_HOOK_NAME}, timeout=15)
            if made.status_code not in (200, 201):
                logger.error(f"Discord: creating the {sport} channel's webhook failed "
                             f"({made.status_code})")
                return None
            hook = made.json()
            logger.info(f"Discord: created a webhook in the {sport} channel")
    except (requests.RequestException, ValueError) as exc:
        logger.error(f"Discord: resolving the {sport} channel's webhook failed: "
                     f"{type(exc).__name__}")
        return None
    url = f"https://discord.com/api/webhooks/{hook['id']}/{hook['token']}"
    _CHANNEL_HOOKS[sport] = url
    return url


def _live_webhook_for_sport(sport: str) -> str | None:
    """Where an IN-PLAY signal for `sport` posts.

    The sport's own live channel first (mike, 2026-09-09: live picks go to
    #nfl-live / #mlb-live / #ncaaf-live), then the shared live channel, then
    the sport's pre-game channel. The last fallback is deliberate: a sport that
    has a live loop and no live channel yet still posts SOMEWHERE its members
    read, and the ledger keeps it from re-posting once the channel is added.
    """
    return (config.DISCORD_WEBHOOKS_LIVE.get(sport)
            or config.DISCORD_WEBHOOK_LIVE
            or _webhook_for_sport(sport))


def _configured() -> bool:
    return bool(config.DISCORD_WEBHOOKS
                or config.discord_sports_wired()
                or config.DISCORD_WEBHOOKS_LIVE
                or config.DISCORD_WEBHOOK_DEFAULT
                or config.DISCORD_WEBHOOK_LIVE
                or config.DISCORD_WEBHOOK_RESULTS)


# ── New BET signals ──────────────────────────────────────────────────────────


def _sync_thresholds_before_post() -> None:
    """Mirror config.py into model_action_thresholds before the producer reads it.

    The scorer pauses from config.PAUSED_MODELS + model_auto_pauses. Discord
    and the app pause from the table. threshold_sync used to run at 6am ET
    only, so a deploy that cleared an auto-pause (or an unpause in config)
    left the table stale until the next daily run -- the producer logged
    "no new signals" while BETs sat unposted. Measured 2026-09-14: five MLB
    props (Lodolo Ks, Alcantara Ks, three SD@COL batter runs) written after
    #727 cleared model_auto_pauses, never posted, games finished, then the
    2026-09-15 10:02Z sync flipped paused=false and signal_delivery went CRIT.

    Best-effort: a sync failure must not skip the post. The query still runs
    against whatever the table currently holds.
    """
    try:
        from data.threshold_sync import sync_action_thresholds
        sync_action_thresholds()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Discord: threshold sync before post failed: {exc}")


def _log_stale_pause_hiding_bets(conn, target_date: str) -> None:
    """ERROR when the table's paused flag is hiding a BET config says is live.

    The empty-set log ("no new signals") is the silent miss: the five Sep 14
    MLB props matched today's cut, commence was hours away, and the only
    reason _new_signals returned [] was t.paused = TRUE on models that were
    not in PAUSED_MODELS. An ERROR naming the models is the thing that makes
    that diagnosable on the next pass rather than the next morning's CRIT.
    """
    try:
        from config import PAUSED_MODELS
        from tracking.threshold_review import auto_paused
        paused_ok = set(PAUSED_MODELS) | set(auto_paused(conn) or ())
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Discord: could not read pause registers: {exc}")
        return
    try:
        rows = conn.execute(f"""
            SELECT p.model_id, COUNT(*)
            FROM picks p
            JOIN model_action_thresholds t ON t.model_id = p.model_id
            LEFT JOIN games g ON g.game_id = p.game_id
            WHERE p.signal_type = 'BET'
              AND (p.is_live IS NULL OR p.is_live = FALSE)
              AND p.model_id NOT LIKE '%%_live_%%'
              AND (g.commence_time IS NULL
                   OR g.commence_time::timestamptz > NOW())
              AND (g.commence_time IS NOT NULL OR p.game_date >= %s)
              AND (p.condition_status IS NULL OR p.condition_status <> 'VOID')
              AND t.paused = TRUE
              -- A paused model's pick is NOT A SIGNAL (scorer._paused_signal,
              -- 2026-09-28): keyed on the row's own marker, so a pick written
              -- while paused is never announced, even after an unpause.
              {config.paused_row_exclusion_sql("p")}
              AND p.model_probability >= t.min_prob
              AND (t.prob_only = TRUE
                   OR COALESCE(p.decision_edge, p.edge) >= COALESCE(t.min_edge, 0))
              AND (t.min_odds IS NULL OR COALESCE(p.decision_odds, p.dk_odds) IS NULL
                   OR COALESCE(p.decision_odds, p.dk_odds) >= t.min_odds)
              AND NOT ({channel_lock_held_sql(lock_key_sql(), 'discord_signal')})
            GROUP BY p.model_id
            ORDER BY p.model_id
        """, (target_date,)).fetchall()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Discord: stale-pause probe failed: {exc}")
        return
    hidden = [(mid, n) for mid, n in rows if mid not in paused_ok]
    if not hidden:
        return
    detail = ", ".join(f"{mid} x{n}" for mid, n in hidden)
    logger.error(
        f"Discord: {sum(n for _, n in hidden)} unposted BET(s) hidden by "
        f"model_action_thresholds.paused=true on models config has live "
        f"({detail}). Sync thresholds and retry; do not wait for 6am."
    )


def _new_signals(conn, target_date: str, *,
                 include_already_posted: bool = False) -> list[dict]:
    """Bettable picks that have not been posted to Discord yet.

    READS `picks`, NOT `opening_signals` (2026-09-05, Matt: "the app and discord
    should always show the same picks. They should be identical").

    The app reads `picks` directly and gates on passesActionFilter. This reads
    the same table through the same model_action_thresholds row, so the two
    surfaces select the same set by construction rather than by keeping two
    windows in sync -- which is what they were doing, and it did not hold.

    WHY THE OLD SOURCE FAILED. Posting from `opening_signals` put the capture
    step between a pick and the channel, and capture is a second gate the app
    does not have: it can only ever LOSE rows relative to `picks`, never add
    one. Measured over every eligible BET since Discord signals went live
    (2026-08-23 22:42 ET) through 2026-09-05: 125 eligible, 119 posted, 6
    missed -- and all 6 were never captured, none were captured-then-unposted.
    Delivery was already perfect; capture was the entire leak.

    Two of those six were the Week 1 wind picks. `capture_opening_signals`
    reaches NFL_LOCK_AHEAD_DAYS forward, a pick written 2026-09-04 for a
    2026-09-13 kickoff is 9 days out, so it was never locked and could never
    post -- while the app showed it all along. That asymmetry is now gone: there
    is no date horizon here at all. A pick is postable when its game has not
    started, however far ahead it was written.

    `opening_signals` is untouched and still the opening-signal / CLV shadow
    track (docs/opening_signals.md). It simply is no longer the gate between a
    pick and the channel.

    THE BET OF RECORD IS THE FIRST ONE. `picks` can hold more than one BET per
    (game, model, player) from before #311 made the pick lock general, so the
    earliest `created_at` wins -- the same row capture would have locked, and
    the same one §1c calls the bet of record. The synthesised lock_key matches
    the key capture minted (`game:model[:player]`), so the push_sent ledger
    carries over and nothing already posted posts twice.

    `include_already_posted` drops only the Discord-ledger filter. X uses it
    so a pick Discord just posted in this same pass is still visible; X has
    its own ledger and must not treat "already on Discord" as "already tweeted".
    """
    rows = conn.execute(f"""
        WITH bet AS (
            SELECT DISTINCT ON ({key_partition_sql()})
                   {lock_key_sql()} AS lock_key,
                   p.pick_label, p.sport, p.model_id,
                   p.model_probability,
                   p.edge, p.dk_odds, p.kelly_fraction,
                   p.confidence_tier, g.home_team, g.away_team, g.commence_time,
                   p.dk_bet_link, p.created_at, p.best_book, p.best_odds,
                   t.min_edge, t.min_odds, p.game_date,
                   COALESCE(p.decision_odds, p.dk_odds) AS decision_odds,
                   p.pick_side, p.scored_line, p.prop_market,
                   p.decision_book, p.decision_odds AS decision_odds_raw
            FROM picks p
            JOIN model_action_thresholds t ON t.model_id = p.model_id
            LEFT JOIN games g ON g.game_id = p.game_id
            WHERE p.signal_type = 'BET'
              -- In-play picks have their own producer and their own channel.
              AND (p.is_live IS NULL OR p.is_live = FALSE)
              AND p.model_id NOT LIKE '%%_live_%%'
              -- NEVER DELIVER A PRE-GAME PICK FOR A GAME THAT HAS STARTED.
              -- The pick is a legitimate bet of record; announcing it once the
              -- game is under way is what is wrong, because the reader cannot
              -- take it. Anything with no commence_time (golf tournaments, a
              -- missing games row) is unaffected -- an unknown start time must
              -- not silently suppress a signal.
              AND (g.commence_time IS NULL
                   OR g.commence_time::timestamptz > NOW())
              -- With no date horizon, a game whose start time we never learned
              -- would stay postable forever. Bound THOSE to the run date; a
              -- game with a real commence_time in the future needs no bound.
              AND (g.commence_time IS NOT NULL OR p.game_date >= %s)
              -- The app's passesActionFilter, in SQL, off the same row.
              -- A VOIDED pick is not publishable (CLAUDE.md §1c): the row
              -- is kept as evidence of a model that fired where it should not
              -- have, and it stops counting. Mirrored by the app's
              -- passesActionFilter, which added the same exclusion the same
              -- day. Only 'VOID': scripts/nfl_pick_monitor.py writes
              -- 'OK' / 'DEGRADED' / 'GONE' here as health states on real,
              -- STANDING picks, which must keep publishing.
              AND (p.condition_status IS NULL OR p.condition_status <> 'VOID')
              AND t.paused = FALSE
              -- A paused model's pick is NOT A SIGNAL (scorer._paused_signal,
              -- 2026-09-28): keyed on the row's own marker, so a pick written
              -- while paused is never announced, even after an unpause.
              {config.paused_row_exclusion_sql("p")}
              AND p.model_probability >= t.min_prob
              -- The cut is applied at the price the pick was DECIDED at
              -- (2026-09-09): decision_* since the flip, DraftKings before.
              AND (t.prob_only = TRUE
                   OR COALESCE(p.decision_edge, p.edge) >= COALESCE(t.min_edge, 0))
              AND (t.min_odds IS NULL OR COALESCE(p.decision_odds, p.dk_odds) IS NULL
                   OR COALESCE(p.decision_odds, p.dk_odds) >= t.min_odds)
            ORDER BY {key_partition_sql()}, p.created_at
        )
        SELECT * FROM bet
        {"" if include_already_posted else "WHERE NOT (" + channel_lock_held_sql('bet.lock_key', 'discord_signal') + ")"}
        ORDER BY created_at
    """, (target_date,)).fetchall()
    return [{
        "lock_key": r[0], "label": r[1], "sport": r[2], "model_id": r[3],
        "prob": r[4], "edge": r[5], "dk_odds": r[6], "kelly": r[7],
        "tier": r[8], "home": r[9], "away": r[10], "commence": r[11],
        "bet_link": r[12], "posted_at": r[13],
        "best_book": r[14], "best_odds": r[15],
        # The worst price this pick would still have been generated at. Same
        # helper and same gates the live card uses, read from the same
        # model_action_thresholds row the scorer's cut comes from, so the
        # published range and the applied cut cannot drift apart. mike,
        # 2026-09-03: "for bonus, post a good to xx odds".
        # Bounded from the DECIDING price (r[19]), which is also the one
        # publish_price puts on the card.
        # On the HONEST probability (2026-09-19): the same promoted map the
        # EV floor was applied through, so the bound solves the gate the pick
        # actually cleared. The card still SHOWS model_probability, as the app.
        "good_to": price_bound(_honest(r[3], r[4]), r[3], r[16], r[17], r[19],
                               r[22] if len(r) > 22 else None),
        "decision_odds": r[19],
        # THE PICK'S OWN DATE, not the run date. Since the look-ahead
        # (2026-09-06) a pass can post picks for more than one day, and the
        # embed header used to say whatever day the pass ran -- so tomorrow's
        # pick was announced under today's date. mike caught it on the first
        # one: "the game is earlier, if you mean tomorrow, need to say
        # september 7th, the post to discord says september 6th".
        "game_date": r[18],
        # What tracking/pick_integrity checks the label against.
        "side": r[20], "line": r[21],
        "prop_market": r[22] if len(r) > 22 else None,
        # The book the price was taken at, and the raw decision price (not
        # the COALESCE above). book_for_pick names decision_book only when
        # that price is the number in dk_odds.
        "decision_book": r[23] if len(r) > 23 else None,
        "decision_odds_raw": r[24] if len(r) > 24 else None,
    } for r in rows
        # Never post a game that has already started -- see _still_pre_game.
        # Belt and braces with the SQL bound above, and the only guard that
        # holds for a caller whose cursor does not evaluate NOW().
        if _still_pre_game(r[11])]


def _locked_signals(conn, target_date: str) -> list[dict]:
    """Every BET on the date that clears the CURRENT thresholds -- ignoring the
    Discord ledger. Same rows _new_signals() draws from, minus the
    not-yet-posted filter, so a restatement covers the whole slate rather than
    whatever happens to be unposted.

    READS `picks`, NOT `opening_signals` (2026-09-05). #489 moved _new_signals
    onto `picks` and left this producer behind on the capture table, which put
    the abandoned gate back in front of the one path whose entire job is to
    REPAIR a channel. A restatement would have omitted exactly the picks that
    motivated #489 -- the uncaptured ones -- so the correction would have been
    as incomplete as the post it was correcting, and silently so. Measured on
    the two Week 1 nfl_wind_totals picks the same day: both in `picks`, neither
    in `opening_signals`, so a restate could not have reached either.

    The lock_key is SYNTHESISED here exactly as _new_signals synthesises it
    (`game:model[:player]`), which is the key capture minted, so the push_sent
    ledger still lines up across all three producers and across the rows
    capture wrote before the move.

    NO STARTED-GAME GUARD, deliberately, and this is the one producer where
    that is correct. _new_signals refuses a started game because ANNOUNCING a
    bet nobody can still take sends a member to a live number. A restatement is
    not an announcement: it corrects something already published, for a date
    that is normally over by the time anyone writes the correction. Adding the
    guard here would make restating a past slate a permanent no-op.

    THE FIRST BET WINS, as everywhere else (§1c): DISTINCT ON the pick's
    identity ordered by created_at, so a pre-#311 side flip collapses to the
    one bet of record rather than restating both halves of it.
    """
    rows = conn.execute(f"""
        WITH bet AS (
            SELECT DISTINCT ON ({key_partition_sql()})
                   {lock_key_sql()} AS lock_key,
                   p.pick_label, p.sport, p.model_id,
                   p.model_probability,
                   p.edge, p.dk_odds, p.kelly_fraction,
                   p.confidence_tier, g.home_team, g.away_team, g.commence_time,
                   p.dk_bet_link, p.created_at, p.best_book, p.best_odds,
                   t.min_edge, t.min_odds, p.game_date,
                   COALESCE(p.decision_odds, p.dk_odds) AS decision_odds,
                   p.pick_side, p.scored_line, p.prop_market,
                   p.decision_book, p.decision_odds AS decision_odds_raw
            FROM picks p
            JOIN model_action_thresholds t ON t.model_id = p.model_id
            LEFT JOIN games g ON g.game_id = p.game_id
            WHERE p.game_date = %s
              AND p.signal_type = 'BET'
              -- In-play picks have their own producer and their own channel.
              AND (p.is_live IS NULL OR p.is_live = FALSE)
              AND p.model_id NOT LIKE '%%_live_%%'
              -- The app's passesActionFilter, in SQL, off the same row --
              -- character for character the cut _new_signals applies, because
              -- a restatement that selected differently from the slate it
              -- corrects would be a third board.
              -- A VOIDED pick is not publishable (CLAUDE.md §1c): the row
              -- is kept as evidence of a model that fired where it should not
              -- have, and it stops counting. Mirrored by the app's
              -- passesActionFilter, which added the same exclusion the same
              -- day. Only 'VOID': scripts/nfl_pick_monitor.py writes
              -- 'OK' / 'DEGRADED' / 'GONE' here as health states on real,
              -- STANDING picks, which must keep publishing.
              AND (p.condition_status IS NULL OR p.condition_status <> 'VOID')
              AND t.paused = FALSE
              -- A paused model's pick is NOT A SIGNAL (scorer._paused_signal,
              -- 2026-09-28): keyed on the row's own marker, so a pick written
              -- while paused is never announced, even after an unpause.
              {config.paused_row_exclusion_sql("p")}
              AND p.model_probability >= t.min_prob
              -- The cut is applied at the price the pick was DECIDED at
              -- (2026-09-09): decision_* since the flip, DraftKings before.
              AND (t.prob_only = TRUE
                   OR COALESCE(p.decision_edge, p.edge) >= COALESCE(t.min_edge, 0))
              AND (t.min_odds IS NULL OR COALESCE(p.decision_odds, p.dk_odds) IS NULL
                   OR COALESCE(p.decision_odds, p.dk_odds) >= t.min_odds)
            ORDER BY {key_partition_sql()}, p.created_at
        )
        SELECT * FROM bet ORDER BY created_at
    """, (target_date,)).fetchall()
    return [{
        "lock_key": r[0], "label": r[1], "sport": r[2], "model_id": r[3],
        "prob": r[4], "edge": r[5], "dk_odds": r[6], "kelly": r[7],
        "tier": r[8], "home": r[9], "away": r[10], "commence": r[11],
        "bet_link": r[12], "posted_at": r[13],
        "best_book": r[14], "best_odds": r[15],
        # The worst price this pick would still have been generated at. Same
        # helper and same gates the live card uses, read from the same
        # model_action_thresholds row the scorer's cut comes from, so the
        # published range and the applied cut cannot drift apart. mike,
        # 2026-09-03: "for bonus, post a good to xx odds".
        # Bounded from the DECIDING price (r[19]), which is also the one
        # publish_price puts on the card.
        # On the HONEST probability (2026-09-19): the same promoted map the
        # EV floor was applied through, so the bound solves the gate the pick
        # actually cleared. The card still SHOWS model_probability, as the app.
        "good_to": price_bound(_honest(r[3], r[4]), r[3], r[16], r[17], r[19],
                               r[22] if len(r) > 22 else None),
        "decision_odds": r[19],
        # THE PICK'S OWN DATE, not the run date. Since the look-ahead
        # (2026-09-06) a pass can post picks for more than one day, and the
        # embed header used to say whatever day the pass ran -- so tomorrow's
        # pick was announced under today's date. mike caught it on the first
        # one: "the game is earlier, if you mean tomorrow, need to say
        # september 7th, the post to discord says september 6th".
        "game_date": r[18],
        "side": r[20], "line": r[21],
        "decision_book": r[23] if len(r) > 23 else None,
        "decision_odds_raw": r[24] if len(r) > 24 else None,
    } for r in rows]


# ── Which book the quoted price came from ────────────────────────────────────
# Matt, 2026-08-29: post the sportsbook the line was found at, with every pick.
#
# A price with no book attached is not checkable. "Over 44.5 -115" invites
# "-115 where?", and the honest answer differs by model: nearly everything here
# is priced against DraftKings (config.ODDS_API_BOOKMAKER is the scoring book
# and every scorer hard-filters to it). The line-shopped cards store the
# book on decision_book. Rows written before that still name it in
# pick_label, and those labels keep parsing.
_BOOK_NAMES = {
    "draftkings": "DraftKings", "dk": "DraftKings",
    "fanduel": "FanDuel", "fd": "FanDuel",
    "betmgm": "BetMGM", "mgm": "BetMGM",
    "williamhill_us": "Caesars", "caesars": "Caesars", "czr": "Caesars",
    "espnbet": "ESPN BET", "espn": "ESPN BET",
    "betrivers": "BetRivers", "br": "BetRivers",
    "bovada": "Bovada", "bov": "Bovada",
    "pinnacle": "Pinnacle", "pin": "Pinnacle",
    "fanatics": "Fanatics",
    # us2 books, added with the list on 2026-09-03. A key with no entry here
    # renders as its raw feed name ("hardrockbet"), which is not wrong but
    # reads like a bug in a channel members pay for.
    "hardrockbet": "Hard Rock Bet", "ballybet": "Bally Bet",
    "betparx": "betPARX", "rebet": "ReBet",
    # fliff joined the bettable set on 2026-09-07 with the nfl_prop_market
    # widening. Its own brand is lower-case.
    "fliff": "Fliff",
}

# Old labels, still in `picks` and not rewritten:
#   "... (Opener -1.5 vs Pinnacle, MGM) · 1.00u" / "... (Wind 14 mph, FD)"
#   "... (no bet, FD)"
# A trailing "(FD)" on a prop is not read. Those stored labels still show
# the book. A new row of the same card does not, so the price line has to.
_LABEL_BOOK_RE = re.compile(r"\((?:[^()]*,\s*)([A-Za-z_]+)\)")
# Cards that write the soft book's own price into dk_odds and the same
# number into decision_odds. When the two prices match, dk_odds is that
# book's number and the reader is sent there. MLB is not in this set:
# its price line stays DraftKings unless a best price is strictly better.
_DECISION_BOOK_MODELS = frozenset({
    "nfl_wind_totals", "nfl_opener_spread",
    "nfl_prop_market", "wnba_prop_market",
})


def _display_book(token: str) -> str:
    """Human name for a feed key or an old label abbreviation.

    An unknown token is returned as stored, not guessed into a known book.
    """
    text = (token or "").strip()
    return _BOOK_NAMES.get(text.lower(), text)


def _same_american(a, b) -> bool:
    """True when both prices are present and equal. A missing price does not
    match: decision_book is named only for the number it was taken at."""
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) <= 1e-6
    except (TypeError, ValueError):
        return False


def book_for_pick(s: dict) -> str | None:
    """Human name of the book whose price is being published.

    An explicit `book` wins. Then `decision_book`, for a soft-book card
    (`_DECISION_BOOK_MODELS`) when `decision_odds` is the same number as
    `dk_odds`: that column is the book the price came from, and the label
    no longer says it. Then the old comma annotation, for an NFL row
    written before the column. Then DraftKings, and only when the pick
    carries a price. A prop suffix, an MLB `decision_book`, "(F5)" and
    "(Regulation)" do not change the name.
    """
    raw = (s.get("book") or "").strip()
    if raw:
        return _display_book(raw)
    model = s.get("model_id") or ""
    decided = (s.get("decision_book") or "").strip()
    if (model in _DECISION_BOOK_MODELS and decided
            and _same_american(s.get("decision_odds_raw"), s.get("dk_odds"))):
        return _display_book(decided)
    if model.startswith("nfl_"):
        m = _LABEL_BOOK_RE.search(s.get("label") or "")
        if m:
            return _display_book(m.group(1))
    if s.get("dk_odds") is None:
        return None
    return "DraftKings"


def publish_price(s: dict) -> tuple[float | None, str | None]:
    """The price to PUBLISH and the book to publish it at.

    mike, 2026-09-03: *"it just needs to post the best book and price."*

    Until now the card led with the DraftKings price and appended
    "also `-120` @ BetMGM" as a footnote. That buried the number the reader is
    supposed to act on behind the number the MODEL happens to decide on, and on
    the 2026-09-02 slate it did that on half the card — Sugano was published at
    DK −139 with BetMGM's −120 in the tail, a 3.61pp better price shown as an
    aside.

    So the best BETTABLE price is the headline, and DraftKings appears only when
    it is the best. Falls back to DK whenever the alternative is absent, equal or
    worse: publishing a worse price as though it were an upgrade is the one
    failure mode worse than publishing DK's.

    THIS DOES NOT CHANGE WHAT QUALIFIES. `edge`, the BET/AVOID call and the cut
    are still measured on DraftKings (CLAUDE.md §6), because every threshold was
    swept there. It changes only where a reader is told to place the bet — and
    the mismatch it creates, that settled P&L is graded at DK while the reader
    got a better number, is exactly what Stage 2 closes (`docs/best_line.md`).

    The book set is filtered upstream: config.BEST_LINE_BOOKMAKERS excludes
    books that cannot be bet from the US, so this never sends anyone to
    Pinnacle.
    """
    dk_odds = s.get("dk_odds")
    best_odds = s.get("best_odds")
    book = (s.get("best_book") or "").strip().lower()
    if best_odds is None or not book:
        return dk_odds, book_for_pick(s)
    best_dec = _decimal_or_none(best_odds)
    if best_dec is None:
        return dk_odds, book_for_pick(s)
    dk_dec = _decimal_or_none(dk_odds)
    if dk_dec is not None and best_dec <= dk_dec + 1e-9:
        return dk_odds, book_for_pick(s)
    return best_odds, _BOOK_NAMES.get(book, book)


def _signal_field(s: dict) -> dict:
    """One pick as an embed field. Deliberately carries ONLY game, time, odds and
    unit stake — no model probability, no edge. Those are the model's IP and are
    not published to the channel."""
    # .get, not [] — context is decoration and MUST NOT be able to take a post
    # down. It could: the live producer built its dicts without a "commence"
    # key, so every notify_discord_live call since Discord shipped raised
    # KeyError into the caller's swallow-and-log, and not one live signal was
    # ever posted for any sport. The key is supplied now; this makes the class
    # of bug non-fatal rather than relying on three producers staying in sync.
    context = " · ".join(x for x in (
        _matchup(s.get("sport"), s.get("home"), s.get("away")),
        _game_time_et(s.get("commence")),
    ) if x)

    # The price the reader should actually take, at the book that has it.
    odds, book = publish_price(s)

    # The stake is grossed up by the price being PUBLISHED, not by DraftKings'.
    # Telling a reader to risk 1.39u at -139 while pointing them at BetMGM's
    # -120 would have them lay 16% more than the bet needs.
    stake = fmt_stake(stake_for(s.get("kelly"), odds))

    price = _american(odds)
    if book:
        price = f"{price} @ {book}"
    line = f"`{price}` · **{stake}**"

    # The price the bet survives to. Nobody outside this repo knows what an edge
    # of 0.14 means; everyone knows what -120 means, so the model's own gates are
    # re-expressed as the one number a reader can check at the book. Pre-game
    # picks carry it as of 2026-09-03 (mike: "for bonus, post a good to xx
    # odds") -- it was live-only before, on the reasoning that a stable price
    # makes it noise, but a signal locked at 6am and read at noon has had six
    # hours of movement.
    #
    # It is a bound on the PRICE THE MODEL WOULD STILL HAVE FIRED AT, so it is
    # book-agnostic: at or better than this number the bet holds, wherever you
    # are placing it. .get, so a producer that does not compute it just omits it.
    good_to = s.get("good_to")
    if good_to:
        line += f" · good to `{_american(good_to)}`"

    # WHEN we got it. Every pick here is a locked bet of record, so created_at
    # is the first moment the bet existed -- which is the reader's answer to
    # "how stale is this number?".
    posted = _posted_et(s.get("posted_at"), seconds=bool(s.get("live")))
    if posted:
        line += f" · posted {posted}"
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

    RESOLVES THE DATE AND SPORT THROUGH `picks`, not `opening_signals`
    (2026-09-05), for the same reason _locked_signals now does: this is the
    delete half of a restatement, and it has to reach every message the
    restatement replaces. Joined to the capture table it could only ever find
    the CAPTURED ones, so an uncaptured pick's stale post would survive the
    correction and the channel would end up showing both numbers -- the worst
    of the three outcomes, and the one nobody would look for. The join is on
    the synthesised lock_key, the same key push_sent was ledgered under.
    """
    url = _webhook_for_sport(sport)
    if not url:
        return 0
    try:
        rows = conn.execute(f"""
            SELECT DISTINCT ps.message_id
              FROM push_sent ps
              JOIN picks p
                ON ps.lock_key = {lock_key_sql()}
             WHERE ps.kind = %s
               AND ps.message_id IS NOT NULL
               AND p.game_date = %s
               AND p.sport = %s
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

# ── Restating a published recap ──────────────────────────────────────────────
#
# A recap can only count what has settled when it posts. A sport that settles
# LATER -- UFC results the next afternoon, an NCAAF score that lands two days
# on, the NFL props of 2026-09-09 that graded an hour after the 6am post --
# leaves a published number that is wrong and stays wrong, because the date is
# ledgered. Until 2026-09-10 the only remedy was a hand-run job (or, for
# 2026-08-29, a date hard-coded here).
#
# Now every settle pass asks: for each recap published in the last week, did
# any pick in its universe settle AFTER it was published? If so, both surfaces
# re-post the date labelled "restated", and the Discord post overwrites the
# snapshot (new published_at), so the same late batch never fires twice. The
# ledger key carries the published_at of the recap being corrected, so a
# SECOND late batch (new published_at) restates again, and a repeat pass over
# the same batch does not.
#
# THE TRIGGER IS LATE SETTLEMENT, NOT A COUNT DIFFERENCE. Measured 2026-09-10:
# every daily snapshot from 09-01 to 09-08 disagrees with the count the recap
# query returns today (09-01: 56 then, 33 now), because the query applies the
# CURRENT action cuts and those moved (the live cut re-sweep of 09-09, pauses).
# A count trigger would have restated eight days for nothing. settled_at >
# published_at is the only thing that means "this recap missed a pick".
#
# Recaps published before RESULTS_RESTATE_FROM are never restated
# automatically. Set to 2026-09-04 (mike, 2026-09-10: "ensure what's there is
# accurate"): the 09-04 and 09-05 recaps each carry picks that settled after
# they posted (2 NCAAF; 4 NCAAF + 2 UFC) and are corrected in place, labelled.
RESULTS_RESTATE_FROM = "2026-09-04"
RESULTS_RESTATE_LOOKBACK_DAYS = 7


def results_restate_note(late: int, prev_settled: int, now_settled: int) -> str:
    """The correction, stated: what settled late, and what the two counts are.

    When the two counts differ by more than the late picks, the rest is the
    action cuts having moved since the recap first posted (the recap query
    applies the CURRENT cuts) -- and the note says so, because "2 settled
    late, 56 then, 33 now" without that sentence reads as a contradiction."""
    picks = "pick" if late == 1 else "picks"
    note = (f"Restated. {late} {picks} settled after this recap was first "
            f"posted ({prev_settled} settled then, {now_settled} now).")
    if now_settled - prev_settled != late:
        note += (" The rest of the difference is the action cuts, which have "
                 "moved since; this is the day under the current cuts.")
    return note + (" Same picks, same results \u2014 this is the full day as "
                   "the record stands now.")


def recaps_needing_restatement(conn, through: str | None = None,
                               lookback_days: int = RESULTS_RESTATE_LOOKBACK_DAYS,
                               game_date: str | None = None) -> list[dict]:
    """Published recaps with a pick that settled after they were posted.

    One dict per date: game_date, published_at (of the snapshot being
    corrected -- the ledger key), settled (what it published), late (how many
    of the CURRENT universe settled after that). Dates < `through` (today ET)
    only, so a day still in play is never touched; bounded below by the
    lookback and by RESULTS_RESTATE_FROM."""
    if through is None:
        through = datetime.now(ET).date().isoformat()
    floor = max(RESULTS_RESTATE_FROM,
                (datetime.fromisoformat(through).date()
                 - timedelta(days=lookback_days)).isoformat())
    params: list = [through, floor]
    date_clause = ""
    if game_date is not None:
        date_clause = " AND game_date = %s"
        params.append(game_date)
    snaps = conn.execute(f"""
        SELECT game_date, published_at, settled
        FROM results_snapshots
        WHERE scope = 'daily' AND sport IS NULL
          AND game_date < %s AND game_date >= %s{date_clause}
        ORDER BY game_date
    """, tuple(params)).fetchall()
    out = []
    for d, published_at, settled in snaps:
        d = str(d)
        late = _execute_settled(
            conn,
            _SETTLED_SQL.format(window="= %s") + "\n          AND p.settled_at > %s",
            (d, published_at)).fetchall()
        if late:
            out.append({"game_date": d, "published_at": published_at,
                        "settled": int(settled or 0), "late": len(late)})
    return out


def restate_published_recaps(through: str | None = None,
                             dry_run: bool = False,
                             now: datetime | None = None) -> int:
    """Re-post every recap a late settlement has invalidated, both surfaces.

    Called at the end of every settle pass, and only from 6:00am through
    noon ET. A game of that sport in progress waits for a later pass.
    Discord first, then X, off the same scan result, so the two carry the
    same correction and the same key. Returns the number of posts made."""
    now = _as_et(now)
    if not in_daily_recap_window(now):
        return 0
    conn = get_connection()
    try:
        due = recaps_needing_restatement(conn, through)
    finally:
        conn.close()
    if not due:
        return 0
    from tracking.x_publisher import notify_x_results
    posted = 0
    for item in due:
        try:
            posted += notify_discord_results(item["game_date"], dry_run=dry_run,
                                             restate=item, now=now)
        except Exception as exc:                          # noqa: BLE001
            logger.error(f"Discord restate {item['game_date']} failed: {exc}")
            _record_restate_exception(item, exc)
        try:
            posted += notify_x_results(item["game_date"], dry_run=dry_run,
                                       restate=item, now=now)
        except Exception as exc:                          # noqa: BLE001
            logger.error(f"X restate {item['game_date']} failed: {exc}")
    return posted


# ── A recap the 6am run could not post ───────────────────────────────────────
# 2026-10-13: the recap for 2026-10-12 never posted, on either surface. The 6am
# run asked at 06:02 and the day's only counting bets -- two NHL props -- were
# not graded until the 07:17 refresh pass, at 07:24. The other six BETs that
# day were from paused models, which the recap rightly leaves out. Nothing
# asked again: a refresh pass settles TODAY, and both notifiers refuse a day
# that is not over. 2026-10-05 had the same shape (2 counting bets, first
# graded 10-06 07:26 ET) and was never recapped either.
#
# So a refresh pass from RECAP_RETRY_FROM_HOUR_ET through noon asks again for
# any day in the last DAILY_CATCHUP_DAYS that has not posted. Oldest first.
# The post names that date. After noon the next morning asks again. If a
# surface has no ledger row for the date and something counting has settled,
# it posts through the ordinary notifiers, Discord then X, exactly as the 6am
# run would have. Both are ledgered per date, so the day posts once, on the
# first pass that can, and every later pass is one cheap read. The hour gate
# is load-bearing: the overnight passes (00:17-05:17 ET)
# also settle today, and yesterday already passes the day-is-over guard at
# 00:17 -- before late games finish and before the 6am-only ingests (NCAAF
# finals, NFL box scores, yesterday's MLB box scores) have run. Without it
# almost every day would post a partial at 00:17. No refresh pass runs between
# the 6am run and 07:17, so 7 costs nothing on a normal day and keeps any pass
# from racing a 6am run that started late.
RECAP_RETRY_FROM_HOUR_ET = 7
# Daily posts from 6:00am ET. Weekly and monthly posts from 7:30am ET.
# Both stop at noon. An evening pass does not catch up; the next morning does.
RECAP_DAILY_HOUR_ET = 6
RECAP_MORNING_END_HOUR_ET = 12
# A missed day keeps trying each morning for this many days, the same span
# a week stays due.
DAILY_CATCHUP_DAYS = RESULTS_RESTATE_LOOKBACK_DAYS
# A started game with no final score is still in progress for this long.
# Past it, a missing score is not a game that is being played.
SPORT_LIVE_HOURS = 8


def _results_webhook() -> str | None:
    """Where the daily recap goes. One definition for the recap and its retry."""
    return config.DISCORD_WEBHOOK_RESULTS or config.DISCORD_WEBHOOK_DEFAULT


def _catchup_dates(now: datetime) -> list[str]:
    """Oldest first, through yesterday. A missed day stays in this list
    until it posts or DAILY_CATCHUP_DAYS mornings have passed."""
    today = now.date()
    return [(today - timedelta(days=back)).isoformat()
            for back in range(DAILY_CATCHUP_DAYS, 0, -1)]


def _missed_recap_dates_sql(n: int) -> str:
    """ONE statement for every catch-up date: ledgered on each surface, and
    whether the recap's own universe has anything settled that day."""
    unions = " UNION ALL ".join(["SELECT CAST(%s AS TEXT) AS game_date"] * n)
    settled = _SETTLED_SQL.format(window="= day.game_date")
    return (
        "SELECT day.game_date,\n"
        "       EXISTS (SELECT 1 FROM push_sent "
        "WHERE lock_key = 'discord_results:' || day.game_date "
        "AND kind = 'discord_results'),\n"
        "       (SELECT sent_at FROM push_sent "
        "WHERE lock_key = 'x_results:' || day.game_date "
        "AND kind = 'x_results'),\n"
        "       EXISTS (" + settled + ")\n"
        f"FROM ({unions}) day\n"
        "ORDER BY day.game_date")


def post_missed_recap(now: datetime | None = None,
                      dry_run: bool = False) -> int:
    """Post a day the morning window has not posted yet, on both surfaces.

    Called by step_settle on a refresh pass (one that settles TODAY), after
    the ordinary attempt and BEFORE restate_published_recaps. Yesterday is
    the usual date. A day that missed its morning stays eligible on later
    mornings, oldest first, for DAILY_CATCHUP_DAYS. The post names that
    date. After noon, nothing runs, and the next morning asks again.

    Cost: before RECAP_RETRY_FROM_HOUR_ET, and from noon ET on, nothing.
    Between them, one statement. When every surface is ledgered, or nothing
    counting has settled, it returns there, silently.
    """
    now = _as_et(now)
    if not in_daily_retry_window(now):
        return 0
    dates = _catchup_dates(now)

    from tracking.x_publisher import notify_x_results, results_can_post
    discord_on = bool(_results_webhook())
    x_on = results_can_post()
    if not (discord_on or x_on):
        return 0

    conn = get_connection()
    try:
        due = _execute_settled(
            conn, _missed_recap_dates_sql(len(dates)), tuple(dates)).fetchall()
    finally:
        conn.close()

    posted = 0
    for game_date, discord_done, x_sent_at, settled in due:
        game_date = str(game_date)
        missing = ((discord_on and not discord_done)
                   or (x_on and x_sent_at is None))
        if not missing or not settled:
            continue
        logger.info(f"Results recap for {game_date} did not post at 6am; "
                    f"posting it now that a counting pick has settled")
        discord_posted = 0
        try:
            discord_posted = notify_discord_results(
                game_date, dry_run=dry_run, now=now)
            posted += discord_posted
        except Exception as exc:                              # noqa: BLE001
            logger.error(f"Discord recap retry {game_date} failed: {exc}")
        try:
            posted += notify_x_results(game_date, dry_run=dry_run, now=now)
        except Exception as exc:                              # noqa: BLE001
            logger.error(f"X recap retry {game_date} failed: {exc}")
        if discord_posted and x_sent_at is not None:
            posted += _restate_x_if_behind(game_date, x_sent_at, dry_run, now)
    return posted


def _restate_x_if_behind(game_date: str, x_sent_at, dry_run: bool,
                         now: datetime | None = None) -> int:
    """Restate X for a date when a counting pick settled after its tweet."""
    from tracking.x_publisher import notify_x_results
    conn = get_connection()
    try:
        late = _execute_settled(
            conn,
            _SETTLED_SQL.format(window="= %s") + "\n          AND p.settled_at > %s",
            (game_date, x_sent_at)).fetchall()
    finally:
        conn.close()
    if not late:
        return 0
    try:
        return notify_x_results(game_date, dry_run=dry_run, restate={
            "game_date": game_date, "published_at": x_sent_at,
            "late": len(late)}, now=now)
    except Exception as exc:                              # noqa: BLE001
        logger.error(f"X restate {game_date} after the Discord retry "
                     f"failed: {exc}")
        return 0


def restate_lock_key(kind: str, game_date: str, published_at) -> str:
    """`{kind}:{date}:{published_at of the recap being corrected}` -- one key
    per correction generation, shared in shape by both surfaces."""
    stamp = published_at.isoformat() if hasattr(published_at, "isoformat") else str(published_at)
    return f"{kind}:{game_date}:{stamp}"


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
        signals = refuse_mismatched(_locked_signals(conn, target_date),
                                    "Discord(restate)")
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

    # BEFORE the lock and the SELECT: the table the producer joins must match
    # config, or a BET the scorer just wrote is invisible here. Own connection
    # inside sync_action_thresholds; fail-open on error.
    _sync_thresholds_before_post()

    conn = get_connection()
    try:
        # Serialize the read -> post -> ledger sequence across every process
        # that can publish. `pollers` and `worker` both call this now, and the
        # ledger cannot stop a duplicate on its own -- it only learns about a
        # post after it has happened. See tracking/publish_lock.py for the
        # 2026-09-06 double-posted Ole Miss card.
        with publish_lock(conn, DISCORD_SIGNALS_LOCK, "Discord") as owned:
            if not owned:
                return 0
            return _post_new_signals(conn, target_date, dry_run)
    finally:
        conn.close()


def _cap_for_run(group: list[dict], now: datetime | None = None) -> list[dict]:
    """The signals this run posts: every one whose game starts within
    config.DISCORD_UNCAPPED_WITHIN_MIN, then the rest up to
    config.DISCORD_MAX_EMBEDS_PER_RUN, in the order they came (oldest first).

    A held signal posts "next pass", and no pass can post a game that has
    started, so holding a pick close to its tip loses it from Discord and from
    the published record (CLAUDE.md 1c). Two NBA prop models decide every game
    55 minutes before tip, up to about 175 bets in one tip slot.
    """
    now = now or datetime.now(timezone.utc)
    soon = now + timedelta(minutes=config.DISCORD_UNCAPPED_WITHIN_MIN)
    due, later = [], []
    for s in group:
        t = _parse_commence(s.get("commence"))
        (due if t is not None and t <= soon else later).append(s)
    room = max(0, config.DISCORD_MAX_EMBEDS_PER_RUN - len(due))
    keep = {id(s) for s in due + later[:room]}
    return [s for s in group if id(s) in keep]


def _parse_commence(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        t = value
    else:
        try:
            t = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _post_new_signals(conn, target_date: str, dry_run: bool) -> int:
    """The body of notify_discord_signals, under the publisher lock."""
    # Refused picks are not ledgered, so they retry and keep logging until the
    # row is fixed; the pick_label_integrity health check turns that CRIT.
    signals = refuse_mismatched(_new_signals(conn, target_date), "Discord")
    if not signals:
        logger.info(f"Discord: no new signals for {target_date}")
        _log_stale_pause_hiding_bets(conn, target_date)
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

        capped = _cap_for_run(group)
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
                    SIGNAL_LEDGER_SQL,
                    (s["lock_key"], "discord_signal", sent_at, message_id),
                )
        posted_total += delivered

    if not dry_run:
        conn.commit()
        if posted_total:
            logger.success(f"✓ Discord: posted {posted_total} signal(s)")
    return posted_total


# ── Live (in-play) signals ───────────────────────────────────────────────────

def _new_live_signals(conn, target_date: str) -> list[dict]:
    """In-play BET picks not yet posted. Deduped on the live lock_key
    (tracking/publish_keys.live_lock_key_sql: game, model, side AND the player
    columns) so the live board — delete-and-rescored every pass — can't re-post
    the same signal, and two players' props in one game are two signals."""
    rows = conn.execute(f"""
        SELECT DISTINCT p.game_id, p.model_id, p.pick_side, p.pick_label, p.sport,
               p.model_probability, p.edge, p.dk_odds, p.kelly_fraction,
               p.inning_at_pick, p.dk_bet_link, g.home_team, g.away_team,
               g.commence_time, p.created_at, t.min_edge, t.min_odds,
               {live_lock_key_sql()} AS lock_key,
               -- The price the live pick was DECIDED at (2026-09-10): the
               -- best bettable in-play quote, DraftKings before the flip and
               -- for the NFL in-play lane (DK-only feed). Published as the
               -- headline through publish_price, like the pre-game cards.
               p.best_book, p.best_odds, p.best_bet_link,
               COALESCE(p.decision_odds, p.dk_odds) AS decision_odds,
               p.decision_book, p.scored_line, p.prop_market,
               p.decision_odds AS decision_odds_raw
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
          {live_publishable_sql()}
          AND NOT ({channel_lock_held_sql(live_lock_key_sql(), 'discord_live')})
        ORDER BY p.game_id
    """, (target_date,)).fetchall()
    return [{
        "lock_key": r[17],
        "label": r[3], "sport": r[4], "model_id": r[1],
        "prob": r[5], "edge": r[6], "dk_odds": r[7], "kelly": r[8],
        "inning": r[9], "bet_link": r[10], "home": r[11], "away": r[12],
        "commence": r[13], "posted_at": r[14], "live": True,
        "best_book": r[18], "best_odds": r[19], "best_bet_link": r[20],
        "decision_odds": r[21], "decision_book": r[22],
        "decision_odds_raw": r[25] if len(r) > 25 else None,
        "side": r[2], "line": r[23],
        # The market the pick settles against, so pick_integrity can check that
        # the label does not NAME a different one. Without this the stat check
        # is dead code, which is how "Blake Corum Under 11.5 Pass Attempts"
        # reached this channel on a rushing bet (CLAUDE.md section 1b: a guard
        # dead code can satisfy is not a guard).
        "prop_market": r[24],
        # "good to" from the deciding price, the same way the pre-game
        # producers bound theirs.
        "good_to": price_bound(_honest(r[1], r[5]), r[1], r[15], r[16], r[21]),
    } for r in rows]


def notify_discord_live(target_date: str | None = None, dry_run: bool = False) -> int:
    """Post new in-play BET signals to the sport's live channel (see
    _live_webhook_for_sport for the fallback chain). Called at the end of each
    MLB and NCAAF live pass, and by the NFL in-play worker after every live
    BET it writes. Returns the number posted."""
    if target_date is None:
        target_date = date.today().isoformat()
    if not _configured():
        return 0

    conn = get_connection()
    try:
        # Same race, same fix as the pre-game producer: the NCAAF live loop and
        # the MLB live scorer both end their passes here, and a pass that
        # overlaps another would post the same in-play card twice.
        with publish_lock(conn, DISCORD_LIVE_LOCK, "Discord(live)") as owned:
            if not owned:
                return 0
            return _post_new_live_signals(conn, target_date, dry_run)
    finally:
        conn.close()


def _post_new_live_signals(conn, target_date: str, dry_run: bool) -> int:
    """The body of notify_discord_live, under the publisher lock."""
    signals = refuse_mismatched(_new_live_signals(conn, target_date), "Discord(live)")
    if not signals:
        return 0

    by_url: dict[tuple[str, str], list[dict]] = {}
    for s in signals:
        url = _live_webhook_for_sport(s["sport"])
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
                    SIGNAL_LEDGER_SQL,
                    (s["lock_key"], "discord_live", sent_at, message_id),
                )
        posted_total += delivered

    if not dry_run:
        conn.commit()
        if posted_total:
            logger.success(f"✓ Discord(live): posted {posted_total} signal(s)")
    return posted_total


# ── Daily results recap ──────────────────────────────────────────────────────

# ── Free pick of the day ─────────────────────────────────────────────────────

def _free_pick_candidates(conn, target_date: str) -> list[dict]:
    """Every locked signal for the date that clears the CURRENT action cut.

    Deliberately does NOT exclude signals already posted to a sport channel: the
    free channel is a different audience, and the pick of the day is expected to
    also appear in the full feed.

    DOES exclude a signal whose pick was VOIDED (2026-10-09): the void writes
    only to `picks`, so the captured row stays, and without this the free
    channel and X could make a voided pick the pick of the day.
    """
    rows = conn.execute(f"""
        SELECT os.lock_key, os.pick_label, os.sport, os.dk_odds,
               os.kelly_fraction, g.home_team, g.away_team, g.commence_time,
               pk.created_at, pk.best_book, pk.best_odds,
               os.model_id, os.model_probability, t.min_edge, t.min_odds,
               os.pick_side, os.scored_line, pk.prop_market,
               pk.decision_book, pk.decision_odds
        FROM opening_signals os
        JOIN model_action_thresholds t ON t.model_id = os.model_id
        LEFT JOIN games g ON g.game_id = os.game_id
        LEFT JOIN LATERAL (
            -- The bet's own row, by the lock key the signal was captured
            -- under: it carries player AND market, so a player bet in two
            -- markets in one transaction (same created_at) cannot lend one
            -- bet the other's price and book.
            SELECT p.created_at, p.best_book, p.best_odds, p.prop_market,
                   p.decision_book, p.decision_odds
            FROM picks p
            WHERE p.game_id = os.game_id
              AND p.model_id = os.model_id
              AND p.pick_side = os.pick_side
              AND {lock_key_sql('p')} = os.lock_key
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
          {captured_not_voided_sql("os")}
        ORDER BY os.lock_key
    """, (target_date,)).fetchall()
    return refuse_mismatched([{
        "lock_key": r[0], "label": r[1], "sport": r[2], "dk_odds": r[3],
        "kelly": r[4], "home": r[5], "away": r[6], "commence": r[7],
        "posted_at": r[8], "best_book": r[9], "best_odds": r[10],
        "model_id": r[11], "side": r[15], "line": r[16],
        "decision_book": r[18] if len(r) > 18 else None,
        "decision_odds_raw": r[19] if len(r) > 19 else None,
        # Same "good to" the paid channels publish, from the same gates.
        "good_to": price_bound(r[12], r[11], r[13], r[14], r[3], r[17] if len(r) > 17 else None),
    } for r in rows], "Discord(free)")


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
    # The best BETTABLE price and the book that has it, exactly as the paid
    # channels publish it (mike, 2026-09-03: "it just needs to post the best
    # book and price"). The free card is the shop window; a shop window showing
    # a worse number than the shop is a strange thing to have built.
    odds, book = publish_price(pick)
    stake = fmt_stake(stake_for(pick.get("kelly"), odds))
    price = _american(odds)
    if book:
        price = f"{price} @ {book}"
    line = f"`{price}` · **{stake}**"
    good_to = pick.get("good_to")
    if good_to:
        line += f" · good to `{_american(good_to)}`"
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

        # The chosen pick's lock_key is recorded in message_id so the day's
        # free-channel choice is the one that was posted. X does not read it.
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
# The selected clv_pct is already NULL unless clv_method is standard_v2.
#
# Retired models need no clause: the JOIN drops them, because a retirement
# deletes the model_action_thresholds row.
# THE RECORD IS WHAT WAS BET, NOT WHAT WE WOULD BET TODAY.
#
# A pick is in here because `signal_type = 'BET'` — it cleared its model's cut
# on the day it was written, at the price that was available then. Nothing about
# the model's PRESENT state may take that back: not a pause, not a threshold
# change, not a retrain. This query therefore does not join
# model_action_thresholds at all.
#
# It used to. `AND t.paused = FALSE` plus a re-application of the current
# min_prob / min_edge / min_odds meant the published all-time figure was
# recomputed from scratch every morning under whatever config happened to be
# live. On 2026-09-12 that turned NCAAF's published record from 27-25 over 52
# settled picks into 0-3 over 3, because two NCAAF live lanes had been paused
# the evening before — 55 settled bets erased by a flag about the future.
# Threshold edits had been doing the quieter version of the same thing for a
# fortnight (-104 settled on 09-02, -22 on 09-09).
#
# mike, 2026-09-12: "Pausing a model should not erase settled record unless I
# explicitly say so ... Do not do it unless I explicitly say so." The two ways
# a settled pick DOES leave are both deliberate acts: a VOID, which sets
# result='NO_ACTION' and so fails the WIN/LOSS/PUSH filter below, and an entry
# in config.RECORD_EXCLUSIONS, appended here. See CLAUDE.md 1c.
#
# The open-pick publishers above are the opposite case and keep their paused and
# threshold checks: a paused model must not be offered as something to bet.
#
# A PICK WRITTEN WHILE ITS MODEL WAS PAUSED WAS NEVER BET (2026-09-28). Since
# scorer._paused_signal keeps a paused model's real verdict, such a row can be
# signal_type = 'BET' -- but it was never posted, never pushed and never
# staked, so it is not part of what was bet. It carries downgrade_reason =
# config.PAUSED_NOTE from the moment it is written, and that ROW marker (not
# the model's present state) is what keeps it out, so this is still a filter
# on what the pick WAS. A pick a live model wrote stays in after a pause.
#
# ONE EVENT IS ONE BET (mike, 2026-10-09, "Count each fight once"). When a
# model bet one event under two game ids, the second copy carries
# condition_status = config.DUPLICATE_STATUS and counts once, here and on
# every other record surface. Its result is never touched.
#
# POSTED TO DISCORD (owner, 2026-10-14). Daily, the 7-day restatement, and
# all-time all read this query, and X and the snapshot builder read it too.
# A settled BET Discord never carried is not in that record. The lock is
# posted_sql: push_sent discord_signal / discord_live, the same key
# v_discord_published joins, dropped when a newer discord_void notice holds.
# The row stays in picks. nfl_live_prop stays out through RECORD_EXCLUSIONS.
_SETTLED_SQL = r"""
        SELECT p.sport, p.model_id, p.result, p.kelly_fraction,
               COALESCE(p.decision_odds, p.dk_odds),
               CASE WHEN p.clv_method = 'standard_v2' THEN p.clv_pct END,
               p.is_live,
               published_pick_unit_profit(COALESCE(p.decision_odds, p.dk_odds), p.result),
               published_pick_unit_risked(COALESCE(p.decision_odds, p.dk_odds), p.result)
        FROM picks p
        WHERE p.game_date {window}
          AND p.signal_type = 'BET'
          AND (p.is_live IS NOT TRUE OR p.model_id LIKE '%%\_live\_%%')
          -- VOIDed picks are result='NO_ACTION' and drop out here.
          AND p.result IN ('WIN', 'LOSS', 'PUSH')""" \
    + config.record_exclusion_sql("p") \
    + config.paused_row_exclusion_sql("p") \
    + config.duplicate_copy_exclusion_sql("p") \
    + "\n          AND " + posted_sql("p") + "\n"


_UNIT_COLUMN_SQL = (
    ",\n               published_pick_unit_profit(COALESCE(p.decision_odds, p.dk_odds), p.result)"
    ",\n               published_pick_unit_risked(COALESCE(p.decision_odds, p.dk_odds), p.result)"
)


def _sql_without_unit_functions(sql: str) -> str:
    """The same query with the two function columns removed.

    A shorter tuple is what `_tally` already prices with `stake_for`.
    """
    if _UNIT_COLUMN_SQL not in sql:
        raise RuntimeError("settled sql has no posted-stake columns to drop")
    return sql.replace(_UNIT_COLUMN_SQL, "")


def _unit_functions_missing(exc: BaseException) -> bool:
    text = str(exc).lower()
    if "published_pick_unit_" not in text:
        return False
    return "does not exist" in text or "no such function" in text


def _execute_settled(conn, sql: str, params: tuple):
    """Run a query built on `_SETTLED_SQL`.

    The functions live in their own migration, and settle runs before that
    migration on the morning the code deploys. A missing function is not a
    failed settlement: drop the columns and let `_tally` use `stake_for`,
    which the function body is pinned equal to. Any other error propagates.
    """
    try:
        return conn.execute(sql, params)
    except Exception as exc:
        if not _unit_functions_missing(exc):
            raise
        # Postgres aborts the transaction on the error, so the retry needs a
        # rollback. That rollback is safe only because every caller reads
        # here and writes afterwards: notify_discord_results inserts
        # push_sent after both tallies return, and the scan, the missed
        # recap, and the X catch-up select and then close. An uncommitted
        # insert already on `conn` would be lost. sqlite3.rollback undoes
        # the test's open inserts instead, and the statement error did not
        # abort that connection.
        if type(exc).__module__.startswith("psycopg"):
            try:
                conn.rollback()
            except Exception:
                pass
        logger.warning(
            "published stake functions are not installed yet; "
            "tallying with stake_for"
        )
        return conn.execute(_sql_without_unit_functions(sql), params)


def _as_et(now: datetime | None) -> datetime:
    """America/New_York. A UTC instant is converted. A naive clock is labeled ET."""
    now = now or datetime.now(ET)
    if now.tzinfo is None:
        return now.replace(tzinfo=ET)
    return now.astimezone(ET)


def in_daily_recap_window(now: datetime | None = None) -> bool:
    """6:00am inclusive through noon exclusive, America/New_York."""
    now = _as_et(now)
    return RECAP_DAILY_HOUR_ET <= now.hour < RECAP_MORNING_END_HOUR_ET


def in_daily_retry_window(now: datetime | None = None) -> bool:
    """7:00am inclusive through noon exclusive.

    The 6:00am pipeline posts the day itself. The retry starts an hour
    later so it does not race that run, and it stops at noon.
    """
    now = _as_et(now)
    return RECAP_RETRY_FROM_HOUR_ET <= now.hour < RECAP_MORNING_END_HOUR_ET


def in_period_recap_window(now: datetime | None = None) -> bool:
    """7:30am inclusive through noon exclusive, America/New_York."""
    now = _as_et(now)
    if now.hour >= RECAP_MORNING_END_HOUR_ET:
        return False
    return (now.hour, now.minute) >= (PERIOD_RECAP_HOUR_ET, PERIOD_RECAP_MINUTE_ET)


def _parse_commence(value) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ET)
    return parsed.astimezone(ET)


def sport_in_progress(conn, sports: tuple[str, ...] | None = None,
                      now: datetime | None = None) -> bool:
    """A game of one of these sports has started and has no final score.

    The start has to be inside SPORT_LIVE_HOURS. A postponed game from an
    earlier day is not in progress. A connection with no execute is not live.
    """
    execute = getattr(conn, "execute", None)
    if execute is None:
        return False
    sports = tuple(dict.fromkeys(s for s in (sports or ()) if s))
    if not sports:
        return False
    now = _as_et(now)
    opened = now - timedelta(hours=SPORT_LIVE_HOURS)
    marks = ", ".join(["%s"] * len(sports))
    sql = (
        "SELECT g.commence_time FROM games g "
        f"WHERE g.sport IN ({marks}) "
        "AND g.game_date BETWEEN %s AND %s "
        "AND (g.home_score IS NULL OR g.away_score IS NULL) "
        "AND g.commence_time IS NOT NULL"
    )
    result = execute(
        sql, (*sports, opened.date().isoformat(), now.date().isoformat()))
    fetchall = getattr(result, "fetchall", None)
    rows = fetchall() if fetchall else []
    for row in rows or ():
        started = _parse_commence(row[0] if row else None)
        if started is not None and opened < started <= now:
            return True
    return False


def window_still_live(conn, start: str, end: str, sports: tuple[str, ...] | None = None) -> bool:
    """A game on a slate date in the window has no final score.

    Slate dates are dates that have a BET in the window. Every game of that
    sport on that date has to be final. An unfinished game in another sport
    does not hold the recap. A connection with no execute is not live, so a
    test double that only ledgers still posts.
    """
    execute = getattr(conn, "execute", None)
    if execute is None:
        return False
    sports = tuple(s for s in (sports or ()) if s)
    if not sports:
        return False
    marks = ", ".join(["%s"] * len(sports))
    sql = (
        "SELECT 1 FROM games g "
        f"WHERE g.game_date BETWEEN %s AND %s AND g.sport IN ({marks}) "
        "AND (g.home_score IS NULL OR g.away_score IS NULL) "
        "AND EXISTS (SELECT 1 FROM picks p "
        "WHERE p.game_date = g.game_date AND p.sport = g.sport "
        "AND p.signal_type = 'BET' "
        "AND p.game_date BETWEEN %s AND %s) "
        "LIMIT 1"
    )
    row = execute(sql, (start, end, *sports, start, end)).fetchone()
    return row is not None


def _settled_rows(conn, game_date: str) -> list[tuple]:
    """One settled day."""
    return _execute_settled(conn, _SETTLED_SQL.format(window="= %s"),
                            (game_date,)).fetchall()


def _settled_rows_since(conn, start_date: str, through: str) -> list[tuple]:
    """Every settled day in a window — the all-time block.

    Bounded ABOVE by the recapped date so the all-time figure is as of that
    recap and never quietly includes a later day: a number published on Monday
    must still reproduce on Friday."""
    return _execute_settled(
        conn,
        _SETTLED_SQL.format(window="BETWEEN %s AND %s"),
        (start_date, through)).fetchall()


# Fallback for a malformed/zero price inside _decimal_odds only. The recap
# tally does not use it: a pick with no taken price is staked at its bare
# conviction (stake_for), never at a -110 that was not on the board.
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
    """Win-loss and units over the same graded picks.

    The price column is the price the bet was taken at:
    COALESCE(decision_odds, dk_odds). Units use that price and the published
    stake (stake_for): conviction is 1u to win, the stake is grossed up by the
    price -- risk 1.1u at -110 to win 1u -- capped at MAX_RISK_UNITS. A loss
    costs the stake. A win pays stake.win, which is the conviction back unless
    the cap bound. A push returns the stake.

    A pick with no taken price is still in both totals. stake_for stakes it at
    the bare conviction. It is not dropped, and it is not given a -110 that
    was never on the board.
    """
    t = {"w": 0, "l": 0, "p": 0, "units": 0.0, "risked": 0.0,
         "clv_n": 0, "clv_beat": 0, "live": 0}
    for row in rows:
        _sport, _model_id, result, kelly, price, clv = row[:6]
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
        # Column 6 is already NULL unless clv_method is standard_v2. Columns
        # 8 and 9 are the posted-stake units and risked.
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
        # A row from _SETTLED_SQL carries the shared SQL functions in the
        # last two columns (published_pick_unit_profit, published_pick_unit_risked).
        # Those are the Record tab's units and risked. A shorter tuple is a
        # unit test of this formatter; it uses stake_for, which the function
        # body is pinned equal to.
        if len(row) >= 9:
            t["units"] += float(row[7] or 0)
            t["risked"] += float(row[8] or 0)
        else:
            stake = stake_for(kelly, price)
            if result == "WIN":
                t["units"] += stake.win
            elif result == "LOSS":
                t["units"] -= stake.risk
            # PUSH returns the stake: no unit change, and it was not risked.
            # WIN and LOSS only. A push, a void, and an ungraded row
            # laid nothing — the same rule as published_pick_unit_risked.
            if result in ("WIN", "LOSS"):
                t["risked"] += stake.risk
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
    # A push-only slate risked nothing, so there is no ROI to divide by.
    # The units are still the units: zero, stated, on the same picks as the record.
    if t["risked"] <= 0:
        base = f"{rec} · {t['units']:+.2f}u"
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
                    round(t["units"], 4),
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
    """Persist the published figures, in their own transaction. Non-fatal: an
    audit trail must never stop the recap being posted -- the post is the
    product, this is the receipt -- and must never take the post's ledger row
    down with it, which is why the caller commits that row first."""
    try:
        conn.executemany("""
            INSERT INTO results_snapshots (
                game_date, scope, sport, wins, losses, pushes, settled,
                units, risked, roi_pct, clv_graded, clv_beat,
                clv_pct, published_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (game_date, scope, COALESCE(sport, ''))
            DO UPDATE SET
                wins=EXCLUDED.wins, losses=EXCLUDED.losses,
                pushes=EXCLUDED.pushes, settled=EXCLUDED.settled,
                units=EXCLUDED.units,
                risked=EXCLUDED.risked, roi_pct=EXCLUDED.roi_pct,
                clv_graded=EXCLUDED.clv_graded, clv_beat=EXCLUDED.clv_beat,
                clv_pct=EXCLUDED.clv_pct, published_at=EXCLUDED.published_at
        """, rows)
        conn.commit()
    except Exception as exc:                         # noqa: BLE001
        logger.warning(f"results snapshot not stored (non-fatal): {exc}")
        try:
            conn.rollback()          # clear an aborted transaction
        except Exception:                            # noqa: BLE001
            pass


def _record_delivery_failure(conn, lock_key: str, kind: str, detail: str) -> None:
    """One row for the latest failed attempt. The success kind is untouched,
    so the next pass tries again. message_id holds the reason: this table has
    no other text column, and the reason is what a later read has to see."""
    fail_kind = f"{kind}_error"
    safe = _WEBHOOK_IN_TEXT.sub("[webhook]", (detail or "unconfirmed"))[:180]
    try:
        conn.execute(
            "INSERT INTO push_sent (lock_key, kind, sent_at, message_id) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (lock_key, kind) DO UPDATE SET "
            "sent_at = EXCLUDED.sent_at, message_id = EXCLUDED.message_id",
            (lock_key, fail_kind, datetime.now(ET).isoformat(), safe),
        )
        conn.commit()
    except Exception as exc:                              # noqa: BLE001
        logger.error(f"Discord delivery failure was not recorded "
                     f"({type(exc).__name__})")
        # The insert aborted the transaction. The no-id path reads the
        # row back next, and that read raises until this rolls back.
        try:
            conn.rollback()
        except Exception:                                 # noqa: BLE001
            pass


def _delivery_failure_reason(raw) -> str:
    """Why this call was not a message id. raw is the object _post returned."""
    status = getattr(raw, "status", None)
    detail = (getattr(raw, "detail", "") or "").strip()
    detail = _WEBHOOK_IN_TEXT.sub("[webhook]", detail)
    if isinstance(raw, str) and raw == _POST_OK_NO_ID:
        reason = "Discord returned no message id"
    else:
        reason = "Discord post was not confirmed"
    if status is not None:
        reason = f"HTTP {status}: {reason}"
    if detail and detail not in reason:
        reason = f"{reason}; {detail}"
    return reason[:180]


def _recap_missing_id_recorded(conn, lock_key: str, kind: str) -> bool:
    """True when this recap already has a no-message-id error row.

    That row means Discord answered success and did not give an id. Posting
    again can put another copy in the channel on every later pass. The row
    is the stop.
    """
    row = conn.execute(
        "SELECT message_id FROM push_sent WHERE lock_key = %s AND kind = %s",
        (lock_key, f"{kind}_error"),
    ).fetchone()
    if not row or row[0] is None:
        return False
    return "no message id" in str(row[0]).lower()


def _alert_recap_missing_id(game_date: str, kind: str, reason: str,
                            lock_key: str, *, recorded: bool) -> None:
    """One ops alert. The lock key is the row to delete, and a restatement's
    key includes the published_at of the recap it corrects.

    recorded means that row is in push_sent, so later passes do not post.
    An insert that failed leaves nothing to stop the next pass, and the
    alert says so.
    """
    from tracking.watch_util import post_ops_alert

    if recorded:
        tail = (
            "It will not be posted again automatically. "
            f"Delete the {kind}_error row for that lock to post it again."
        )
    else:
        tail = ("The error row was not recorded, so a later pass may post "
                "it again.")
    try:
        post_ops_alert(
            "Results recap has no message id",
            f"{kind} for {game_date} came back without a message id ({reason}). "
            f"Lock {lock_key}. {tail}",
        )
    except Exception as exc:                       # noqa: BLE001
        logger.error(f"recap no-message-id alert failed ({type(exc).__name__})")


def _record_restate_exception(item: dict, exc: BaseException) -> None:
    """A restatement that raised still leaves a row. The log line alone is
    gone when the container is."""
    conn = get_connection()
    try:
        key = restate_lock_key("discord_results_restate", item["game_date"],
                               item["published_at"])
        _record_delivery_failure(
            conn, key, "discord_results_restate",
            f"{type(exc).__name__}: {exc}")
    except Exception as inner:                            # noqa: BLE001
        logger.error(f"Discord restate failure was not recorded "
                     f"({type(inner).__name__})")
    finally:
        conn.close()


def render_all_time_fields(rows: list[tuple], since: str) -> list[dict]:
    """One overall field, then one per sport. The daily recap, the standalone
    full-record post, and the Eggz recap all render this."""
    overall = _tally(rows)
    by_sport: dict[str, list[tuple]] = {}
    for r in rows:
        by_sport.setdefault(r[0], []).append(r)
    fields = [{
        "name": f"\u200b\nAll-time  ·  since {since}",
        "value": f"**{_tally_line(overall, with_clv=True)}**  ·  "
                 f"{len(rows)} settled",
        "inline": False,
    }]
    for sport, group in sorted(by_sport.items()):
        fields.append({
            "name": f"{sport} (all-time)",
            "value": _tally_line(_tally(group), with_clv=True),
            "inline": False,
        })
    return fields


def all_time_fields(conn, through: str) -> tuple[list[dict], dict, int]:
    """The recap's all-time block: one overall field, then one per sport.
    The daily recap and the standalone full-record post both render this."""
    all_rows = _settled_rows_since(conn, config.PAPER_TRADING_START, through)
    return (render_all_time_fields(all_rows, config.PAPER_TRADING_START),
            _tally(all_rows), len(all_rows))


def all_time_embed(conn, through: str) -> dict:
    """The full record as its own recap-style embed (same builder, colours and
    lines as the daily recap's all-time block)."""
    fields, overall, _n = all_time_fields(conn, through)
    pretty = datetime.fromisoformat(through).strftime("%a %b %d").replace(" 0", " ")
    color = (_COLOR_RESULTS_UP if overall["units"] > 0
             else _COLOR_RESULTS_DOWN if overall["units"] < 0
             else _COLOR_RESULTS_FLAT)
    return {"title": f"\U0001F4CA Results — All-time through {pretty}",
            "color": color, "fields": fields}


def notify_discord_results(game_date: str | None = None, dry_run: bool = False,
                           restate=None, now: datetime | None = None) -> int:
    """Post one recap of a settled day: overall record / P&L / ROI plus a
    per-sport breakdown. Ledgered per date so re-running settle can't repost,
    and refuses any date that is not already over. Returns 1 if posted, else 0.

    `restate` re-posts a date whose published recap a later settlement has
    invalidated (recaps_needing_restatement): pass the scan's dict, or True
    to resolve it here. Its own ledger kind, keyed on the published_at of the
    recap being corrected, so one late batch fires exactly once and cannot
    collide with the original. The original is left in place: a channel that
    quietly loses a number people saw is worse than one carrying a visible
    correction. Renders through the SAME path as a normal recap, so a restated
    figure cannot drift from what tomorrow's recap would publish.
    """
    clock = _as_et(now)
    if game_date is None:
        game_date = (clock.date() - timedelta(days=1)).isoformat()

    url = _results_webhook()
    if not url:
        return 0

    # Only recap a day that is OVER, and only from 6:00am through noon ET.
    # `--step settle` (run on every refresh pass by scripts/refresh_pass.sh)
    # settles TODAY, grading games as they finish — recapping that would post
    # a partial record mid-slate and then ledger it, so the real end-of-day
    # recap could never post. The same window binds a restatement. A pass
    # after noon returns here, unledgered, and the next morning asks again.
    # The daily 6am pipeline settles yesterday, which is the run this is
    # meant to fire on; when it cannot (nothing counting settled yet, or the
    # post failed), later mornings ask again for that date (post_missed_recap).
    if game_date >= clock.date().isoformat():
        return 0
    if not in_daily_recap_window(clock):
        return 0

    conn = get_connection()
    try:
        if restate is True:
            found = recaps_needing_restatement(conn, game_date=game_date)
            restate = found[0] if found else None
            if restate is None:
                return 0                  # nothing settled late: no correction
        kind = "discord_results_restate" if restate else "discord_results"
        lock_key = (restate_lock_key(kind, game_date, restate["published_at"])
                    if restate else f"discord_results:{game_date}")
        if conn.execute(
            "SELECT 1 FROM push_sent WHERE lock_key = %s AND kind = %s",
            (lock_key, kind),
        ).fetchone():
            return 0
        # A success response with no message id is ledgered as {kind}_error.
        # The message may already be in the channel. Another pass would post
        # another copy. One such row stops this recap for good.
        if _recap_missing_id_recorded(conn, lock_key, kind):
            return 0

        rows = _settled_rows(conn, game_date)
        if not rows:
            logger.info(f"Discord(results): nothing settled for {game_date}")
            return 0
        sports = tuple({r[0] for r in rows if r[0]})
        if window_still_live(conn, game_date, game_date, sports):
            logger.info(f"Discord(results): {game_date} still has a game "
                        f"without a final score")
            return 0
        if sport_in_progress(conn, sports, now):
            logger.info(f"Discord(results): {game_date} waits, a game of "
                        f"that sport is in progress")
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
        fields.extend(all_time_fields(conn, game_date)[0])
        all_rows = _settled_rows_since(conn, config.PAPER_TRADING_START, game_date)
        all_overall = _tally(all_rows)
        all_by_sport: dict[str, list[tuple]] = {}
        for r in all_rows:
            all_by_sport.setdefault(r[0], []).append(r)

        color = (_COLOR_RESULTS_UP if overall["units"] > 0
                 else _COLOR_RESULTS_DOWN if overall["units"] < 0
                 else _COLOR_RESULTS_FLAT)

        pretty = datetime.fromisoformat(game_date).strftime("%a %b %d").replace(" 0", " ")
        embed = {
            "title": (f"\U0001F4CA Results — {pretty}"
                      + ("  ·  restated" if restate else "")),
            "description": (
                (results_restate_note(restate["late"], restate["settled"],
                                      len(rows)) + "\n\n") if restate else ""
            ) + f"**{_tally_line(overall, with_clv=True)}**  ·  "
                f"{len(rows)} settled",
            "color": color,
            "fields": fields,
        }

        if dry_run:
            logger.info(f"[dry-run] discord(results) {game_date} → {_tally_line(overall)}")
            return 0

        # _post appends ?wait=true and returns the message id. A 2xx with no
        # id used to be ledgered as a success. The row then
        # blocked every retry, and the message could not be opened. Measured
        # 2026-10-14: the Oct 13 restatement is that row (null message_id)
        # and it is not a message anyone can find. No id is not a delivery.
        # It is also not a miss we can safely repeat: the body may have
        # landed. One error row, one alert, and no later pass posts it.
        raw = _post(url, {"embeds": [embed]})
        message_id = raw if isinstance(raw, str) else None
        stored_id = (message_id if message_id
                     and message_id not in ("", _POST_OK_NO_ID) else None)
        if not stored_id:
            reason = _delivery_failure_reason(raw)
            logger.error(f"Discord(results) {game_date} "
                         f"{'restate ' if restate else ''}not confirmed ({reason})")
            _record_delivery_failure(conn, lock_key, kind, reason)
            if isinstance(raw, str) and raw == _POST_OK_NO_ID:
                try:
                    recorded = _recap_missing_id_recorded(conn, lock_key, kind)
                except Exception as exc:                  # noqa: BLE001
                    logger.error(f"Discord(results) {game_date} error row "
                                 f"could not be read back ({type(exc).__name__})")
                    recorded = False
                # A missing row does not stop the next pass. Alert either
                # way: once when the stop is stored, and on this pass when
                # the insert did not stick.
                _alert_recap_missing_id(
                    game_date, kind, reason, lock_key, recorded=recorded)
            return 0

        published_at = datetime.now(ET).isoformat()
        conn.execute(
            "INSERT INTO push_sent (lock_key, kind, sent_at, message_id) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (lock_key, kind) DO NOTHING",
            (lock_key, kind, published_at, stored_id),
        )
        # The post has gone out, so its ledger row commits NOW, on its own.
        # It used to share one transaction with the snapshot below, which
        # swallows its own failure: a pooler drop mid-snapshot (data.db
        # reconnects and raises ConnectionLost) or a failed snapshot statement
        # (PostgreSQL turns the COMMIT into a ROLLBACK and raises nothing)
        # silently took this row with it. With the refresh passes retrying a
        # missed recap (post_missed_recap) and restating late ones on every
        # pass, a lost row means the same post again on every pass until
        # midnight.
        conn.commit()
        # The snapshot is the published record for that date, so a restatement
        # OVERWRITES it rather than adding a second row: the corrected numbers
        # are the ones that should reproduce later, and two rows for one date
        # would leave which-is-authoritative to whoever reads them next.
        _store_snapshot(conn, snapshot_rows(
            game_date, published_at, overall, by_sport, all_overall,
            all_by_sport, len(rows), len(all_rows)))
        logger.success(
            f"✓ Discord(results): {'restated' if restate else 'posted'} "
            f"recap for {game_date}")
        return 1
    finally:
        conn.close()


# ── Weekly and monthly recaps ────────────────────────────────────────────────
# The daily recap above is yesterday, inside the 6:00am ET pipeline. These
# two use that same settled query and the same results webhook. They open
# Monday at 7:30am ET, after that daily post and after the 7:00am retry.
# A missed morning posts on the next morning, 7:30am through noon ET, until
# the next window opens. An evening pass does not post. The ledger posts once.

PERIOD_RECAP_HOUR_ET = 7
PERIOD_RECAP_MINUTE_ET = 30


def _at_et(day: date, hour: int, minute: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=ET)


def _first_monday(year: int, month: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(0 - first.weekday()) % 7)


def _previous_month(year: int, month: int) -> tuple[date, date]:
    if month == 1:
        start = date(year - 1, 12, 1)
    else:
        start = date(year, month - 1, 1)
    end = date(year, month, 1) - timedelta(days=1)
    return start, end


def _week_ending(sunday: date) -> tuple[date, date]:
    return sunday - timedelta(days=6), sunday


def recap_periods_due(now: datetime | None = None) -> list[dict]:
    """The week, and on its window the month, whose posting time has passed.

    The week that ended Sunday opens the following Monday at 7:30am ET and
    stays due until the next Monday at 7:30am. The previous calendar month
    opens on the first Monday of the new month at that same minute, and
    stays due until the next month's first Monday. Before 7:30am on the
    opening Monday, that window is not due yet.
    """
    now = now or datetime.now(ET)
    now = now.astimezone(ET) if now.tzinfo else now.replace(tzinfo=ET)
    today = now.date()
    due: list[dict] = []

    if today.weekday() == 6:
        sunday = today - timedelta(days=7)
    else:
        sunday = today - timedelta(days=today.weekday() + 1)
    week_opens = _at_et(sunday + timedelta(days=1),
                        PERIOD_RECAP_HOUR_ET, PERIOD_RECAP_MINUTE_ET)
    if now >= week_opens:
        start, end = _week_ending(sunday)
        due.append({
            "span": "week", "start": start, "end": end,
            "heading": period_heading("week", start, end),
        })

    opened: list[tuple[datetime, int, int]] = []
    for year, month in ((today.year, today.month),
                        *_shift_month(today.year, today.month, -1)):
        first = _first_monday(year, month)
        opens = _at_et(first, PERIOD_RECAP_HOUR_ET, PERIOD_RECAP_MINUTE_ET)
        if now >= opens:
            opened.append((opens, year, month))
    if opened:
        _opens, year, month = max(opened)
        start, end = _previous_month(year, month)
        due.append({
            "span": "month", "start": start, "end": end,
            "heading": period_heading("month", start, end),
        })
    return due


def _shift_month(year: int, month: int, delta: int) -> tuple[tuple[int, int]]:
    month += delta
    if month < 1:
        month += 12
        year -= 1
    elif month > 12:
        month -= 12
        year += 1
    return ((year, month),)


def period_heading(span: str, start: date, end: date) -> str:
    """The title both surfaces use, without the word 'results'."""
    if span == "month":
        return start.strftime("%B")
    left = f"{start.strftime('%b')} {start.day}"
    if start.month == end.month and start.year == end.year:
        right = str(end.day)
    else:
        right = f"{end.strftime('%b')} {end.day}"
    return f"Week of {left}-{right}"


def notify_discord_period(span: str, start: date, end: date,
                          heading: str, dry_run: bool = False,
                          now: datetime | None = None) -> int:
    """One weekly or monthly recap, on the daily recap's webhook.

    Same settled picks as the daily recap (`_settled_rows_since` is that
    query over a window). Ledgered on the window's start date, and only
    after Discord returns a message id.
    """
    url = _results_webhook()
    if not url:
        return 0
    if not in_period_recap_window(now):
        return 0
    kind = f"discord_results_{span}"
    lock_key = f"{kind}:{start.isoformat()}"
    conn = get_connection()
    try:
        if conn.execute(
            "SELECT 1 FROM push_sent WHERE lock_key = %s AND kind = %s",
            (lock_key, kind),
        ).fetchone():
            return 0
        rows = _settled_rows_since(conn, start.isoformat(), end.isoformat())
        if not rows:
            return 0
        sports = tuple({r[0] for r in rows if r[0]})
        if window_still_live(conn, start.isoformat(), end.isoformat(), sports):
            logger.info(f"Discord({span}): {heading} still has a game "
                        f"without a final score")
            return 0
        if sport_in_progress(conn, sports, now):
            logger.info(f"Discord({span}): {heading} waits, a game of "
                        f"that sport is in progress")
            return 0
        overall = _tally(rows)
        if (overall["w"] + overall["l"] + overall["p"]) == 0:
            return 0
        by_sport: dict[str, list] = {}
        for row in rows:
            by_sport.setdefault(row[0], []).append(row)
        fields = [{
            "name": sport,
            "value": _tally_line(_tally(group), with_clv=True),
            "inline": False,
        } for sport, group in sorted(by_sport.items())]
        color = (_COLOR_RESULTS_UP if overall["units"] > 0
                 else _COLOR_RESULTS_DOWN if overall["units"] < 0
                 else _COLOR_RESULTS_FLAT)
        embed = {
            "title": f"\U0001F4CA Results — {heading}",
            "description": (
                f"**{_tally_line(overall, with_clv=True)}**  ·  "
                f"{len(rows)} settled"),
            "color": color,
            "fields": fields,
        }
        if dry_run:
            logger.info(f"[dry-run] discord({span}) {heading} → "
                        f"{_tally_line(overall)}")
            return 0
        message_id = _post(url, {"embeds": [embed]})
        stored_id = (message_id if isinstance(message_id, str)
                     and message_id not in ("", _POST_OK_NO_ID) else None)
        if not stored_id:
            logger.error(f"Discord({span}) {heading} not confirmed")
            return 0
        conn.execute(
            "INSERT INTO push_sent (lock_key, kind, sent_at, message_id) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (lock_key, kind) DO NOTHING",
            (lock_key, kind, datetime.now(ET).isoformat(), stored_id),
        )
        conn.commit()
        logger.success(f"✓ Discord({span}): posted {heading}")
        return 1
    finally:
        conn.close()


def post_period_recaps(now: datetime | None = None, dry_run: bool = False) -> int:
    """Post each due week and month, Discord then X. A ledgered window is 0.

    Called by the Monday 7:30am job and again from later settle passes.
    Only 7:30am through noon ET. A miss rolls to the next morning. A
    successful post is not repeated.
    """
    now = _as_et(now)
    if not in_period_recap_window(now):
        return 0
    posted = 0
    for window in recap_periods_due(now):
        try:
            posted += notify_discord_period(
                window["span"], window["start"], window["end"],
                window["heading"], dry_run=dry_run, now=now)
        except Exception as exc:                              # noqa: BLE001
            logger.error(f"Discord {window['span']} recap failed: {exc}")
        try:
            from tracking.x_publisher import notify_x_period
            posted += notify_x_period(
                window["span"], window["start"], window["end"],
                window["heading"], dry_run=dry_run, now=now)
        except Exception as exc:                              # noqa: BLE001
            logger.error(f"X {window['span']} recap failed: {exc}")
    return posted


# ── Void notice ──────────────────────────────────────────────────────────────
# A one-off. Picks that were already posted, then VOIDED, stay on the app
# board because v_discord_published returns the discord_signal row. This
# posts a gray notice and, only after Discord accepts it, ledger
# kind discord_void. The view then drops the lock. The original message
# is left where it was: this path never edits or deletes.

VOID_NOTICE_REASON = (
    "Voided: priced off a stale sportsbook line after our odds feed dropped "
    "the game. These picks are void and do not count in the record. The "
    "original posts are left as they were."
)

_EMBED_TOTAL_MAX = 6000
_EMBED_DESCRIPTION_MAX = 4096
_FIELD_NAME_MAX = 256
_FIELD_VALUE_MAX = 1024


class DiscordVoidRejected(ValueError):
    """The list is not postable. Nothing was sent and nothing was written."""


def _void_title(sport: str) -> str:
    """Same emoji the slate embeds use. NCAAF is '🏈 NCAAF · Voided picks'."""
    emoji = _SPORT_EMOJI.get(sport, "\U0001f3af")
    return f"{emoji} {sport} \u00b7 Voided picks"


def _known_channel_ids(sport: str | None) -> tuple[str, str]:
    """Guild id and channel id for a jump link, when both are known.

    Config stores webhook URLs, which are credentials, not a guild id and a
    channel id. The ledger does not store either id. Nothing here calls
    Discord to look them up. Both empty means the notice omits the line.
    """
    del sport  # no per-sport channel id is configured
    return "", ""


def _discord_jump_line(message_id, guild_id: str | None,
                       channel_id: str | None) -> str | None:
    """https://discord.com/channels/<guild>/<channel>/<message>, or nothing.

    That URL has no webhook token. A missing id drops the line rather than
    printing the snowflake or the webhook address.
    """
    if message_id is None or str(message_id) in ("", _POST_OK_NO_ID):
        return None
    guild = (guild_id or "").strip()
    channel = (channel_id or "").strip()
    mid = str(message_id).strip()
    if not (guild.isdigit() and channel.isdigit() and mid.isdigit()):
        return None
    return f"https://discord.com/channels/{guild}/{channel}/{mid}"


def _void_field(pick: dict, webhook_url: str | None) -> dict:
    """One pick. The name is pick_label, word for word."""
    label = str(pick.get("label") or "")
    matchup = _matchup(pick.get("sport"), pick.get("home"), pick.get("away"))
    odds, book = publish_price(pick)
    price = _american(odds)
    if book:
        price = f"{price} @ {book}"
    game_date = pick.get("game_date") or ""
    if hasattr(game_date, "isoformat"):
        game_date = game_date.isoformat()
    posted = _posted_et(
        None if pick.get("posted_at") is None else str(pick.get("posted_at"))
    )
    bits = [x for x in (
        matchup,
        price,
        " \u00b7 ".join(x for x in (
            f"game {game_date}" if game_date else "",
            f"posted {posted}" if posted else "",
        ) if x),
    ) if x]
    guild_id, channel_id = _known_channel_ids(pick.get("sport"))
    original = _discord_jump_line(pick.get("message_id"), guild_id, channel_id)
    if original:
        bits.append(original)
    return {"name": label, "value": "\n".join(bits), "inline": False}


def _embed_size(title: str, description: str, fields: list[dict]) -> int:
    return (len(title) + len(description or "")
            + sum(len(f["name"]) + len(f["value"]) for f in fields))


def void_notice_embeds(sport: str, picks: list[dict], reason: str,
                       webhook_url: str | None) -> list[dict]:
    """Gray embeds for one sport, chunked at Discord's 25-field and 6000-char caps.

    The reason is the description of every embed, so a later page still says
    why. One embed per message is the caller's job.
    """
    if len(reason) > _EMBED_DESCRIPTION_MAX:
        raise DiscordVoidRejected(
            [f"reason is {len(reason)} characters; Discord's description cap "
             f"is {_EMBED_DESCRIPTION_MAX}"])
    title = _void_title(sport)
    fields = [_void_field(p, webhook_url) for p in picks]
    for field in fields:
        if len(field["name"]) > _FIELD_NAME_MAX or len(field["value"]) > _FIELD_VALUE_MAX:
            raise DiscordVoidRejected(
                [f"pick field exceeds Discord's size limit: {field['name'][:80]}"])
    chunks: list[list[dict]] = []
    cur: list[dict] = []
    for field in fields:
        trial = cur + [field]
        over = (len(trial) > _FIELDS_PER_EMBED
                or _embed_size(title, reason, trial) > _EMBED_TOTAL_MAX)
        if cur and over:
            chunks.append(cur)
            cur = [field]
        else:
            cur = trial
        if _embed_size(title, reason, cur) > _EMBED_TOTAL_MAX:
            raise DiscordVoidRejected(
                ["one pick does not fit in a Discord embed"])
    if cur:
        chunks.append(cur)
    return [{
        "title": title,
        "description": reason,
        "color": _COLOR_VOID,
        "fields": chunk,
    } for chunk in chunks]


def _normalize_void_ids(pick_ids) -> list[int]:
    if isinstance(pick_ids, (str, bytes)) or not isinstance(pick_ids, (list, tuple)):
        raise DiscordVoidRejected(
            ["pick_ids must be a non-empty list of pick ids"])
    if len(pick_ids) == 0:
        raise DiscordVoidRejected(
            ["pick_ids must be a non-empty list of pick ids"])
    ids: list[int] = []
    seen: set[int] = set()
    for raw in pick_ids:
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise DiscordVoidRejected(
                [f"pick id {raw!r} is not an integer"])
        if raw <= 0:
            raise DiscordVoidRejected([f"pick id {raw} is not a pick"])
        if raw not in seen:
            seen.add(raw)
            ids.append(raw)
    return ids


def _void_rows_sql() -> str:
    key = (f"CASE WHEN p.is_live THEN {live_lock_key_sql('p')} "
           f"ELSE {lock_key_sql('p')} END")
    return f"""
        SELECT p.pick_id, p.sport, p.model_id, p.game_id, p.game_date,
               p.pick_side, p.pick_label, p.condition_status,
               p.dk_odds, p.best_odds, p.best_book,
               p.is_live, p.player_id, p.player_key, p.prop_market,
               p.created_at, g.home_team, g.away_team,
               {key} AS lock_key,
               sig.message_id, sig.sent_at,
               (sig.kind IS NOT NULL) AS has_signal,
               (void.kind IS NOT NULL) AS already_voided
          FROM picks p
          LEFT JOIN games g ON g.game_id = p.game_id
          LEFT JOIN push_sent sig
            ON sig.lock_key = {key}
           AND sig.kind = CASE WHEN p.is_live THEN 'discord_live'
                               ELSE 'discord_signal' END
          LEFT JOIN push_sent void
            ON void.lock_key = {key}
           AND void.kind = 'discord_void'
         WHERE p.pick_id = ANY(%s)
    """


def _pick_from_row(row) -> dict:
    game_date = row[4]
    if hasattr(game_date, "isoformat"):
        game_date = game_date.isoformat()
    posted = row[20] if row[20] is not None else row[15]
    return {
        "pick_id": int(row[0]),
        "sport": row[1],
        "model_id": row[2],
        "game_id": row[3],
        "game_date": game_date,
        "side": row[5],
        "label": row[6],
        "condition_status": row[7],
        "dk_odds": row[8],
        "best_odds": row[9],
        "best_book": row[10],
        "is_live": bool(row[11]),
        "home": row[16],
        "away": row[17],
        "lock_key": row[18],
        "message_id": None if row[19] is None else str(row[19]),
        "posted_at": posted,
        "has_signal": bool(row[21]),
        "already_voided": bool(row[22]),
    }


def _reject_void_candidates(wanted: list[int], picks: list[dict]) -> None:
    """Every requested pick is VOID and already posted, or the call fails."""
    by_id = {p["pick_id"]: p for p in picks}
    problems: list[str] = []
    for pick_id in wanted:
        pick = by_id.get(pick_id)
        if pick is None:
            problems.append(f"pick {pick_id} was not found")
            continue
        if not pick["sport"]:
            problems.append(f"pick {pick_id} has no sport")
        if pick["condition_status"] != "VOID":
            problems.append(
                f"pick {pick_id} condition_status is "
                f"{pick['condition_status']!r}, not VOID")
        kind = "discord_live" if pick["is_live"] else "discord_signal"
        if not pick["has_signal"]:
            problems.append(f"pick {pick_id} has no {kind} row")
    if problems:
        raise DiscordVoidRejected(problems)


def posted_sibling_sql() -> str:
    """A pregame pick on this lock_key that a void notice would unpublish.

    The pregame key is game_id:model_id plus player parts, and it has no
    side. discord_void on that key releases every pick that shares it.
    A sibling that is still a published BET blocks the notice. Live keys
    include the side, so this query is not used for an in-play pick.
    """
    return f"""
        SELECT sib.pick_id
          FROM picks sib
         WHERE sib.pick_id <> %s
           AND sib.signal_type = 'BET'
           AND sib.condition_status IS DISTINCT FROM 'VOID'
           AND sib.condition_status IS DISTINCT FROM 'DUPLICATE'
           AND sib.result IS DISTINCT FROM 'NO_ACTION'
           AND COALESCE(sib.is_live, false) IS NOT TRUE
           AND {lock_key_sql('sib')} = %s
         LIMIT 1
    """


def _posted_sibling_id(conn, pick: dict):
    """The pick_id still holding this pregame lock, or None.

    Live locks carry the side. A notice on one does not release the other
    side, so an in-play void is not checked here.
    """
    if pick.get("is_live"):
        return None
    row = conn.execute(
        posted_sibling_sql(), (pick["pick_id"], pick["lock_key"])
    ).fetchone()
    if not row or row[0] is None:
        return None
    return int(row[0])


def _ledger_void(conn, picks: list[dict], sent_at: str, message_id: str) -> None:
    stored = None if message_id == _POST_OK_NO_ID else message_id
    for pick in picks:
        conn.execute(
            "INSERT INTO push_sent (lock_key, kind, sent_at, message_id) "
            "VALUES (%s, 'discord_void', %s, %s) "
            "ON CONFLICT (lock_key, kind) DO NOTHING",
            (pick["lock_key"], sent_at, stored),
        )
    conn.commit()


def notify_discord_void(pick_ids, reason: str | None = None,
                        dry_run: bool = True) -> dict:
    """Post one gray void notice per sport. dry_run is the default.

    Validates the whole list before any post. A pick that is not VOID, or
    that has no discord_signal (discord_live when the pick is in-play),
    fails the call and nothing is sent. Locks that already have discord_void
    are skipped; a rerun of a finished list is a no-op.

    A pregame lock has no side. Posting discord_void on it releases every
    pick on that key. When another pick on the key is still a published
    BET, this logs the refusal and skips that pick: no post, no ledger
    row. The void itself is already committed and is not undone.

    dry_run makes no HTTP call and no ledger write. It returns the exact
    POST bodies. A failed post writes nothing for that message. This never
    edits or deletes an existing Discord message.
    """
    ids = _normalize_void_ids(pick_ids)
    text = VOID_NOTICE_REASON if reason is None or not str(reason).strip() else str(reason).strip()
    if len(text) > _EMBED_DESCRIPTION_MAX:
        raise DiscordVoidRejected(
            [f"reason is {len(text)} characters; Discord's description cap "
             f"is {_EMBED_DESCRIPTION_MAX}"])

    conn = get_connection()
    try:
        rows = conn.execute(_void_rows_sql(), (ids,)).fetchall()
        picks = [_pick_from_row(r) for r in rows]
        _reject_void_candidates(ids, picks)
        by_id = {p["pick_id"]: p for p in picks}
        ordered = [by_id[i] for i in ids]
        skipped = [p["lock_key"] for p in ordered if p["already_voided"]]
        pending = [p for p in ordered if not p["already_voided"]]
        refused_siblings: list[str] = []
        safe: list[dict] = []
        for pick in pending:
            sibling = _posted_sibling_id(conn, pick)
            if sibling is None:
                safe.append(pick)
                continue
            logger.warning(
                f"Discord void: refusing pick {pick['pick_id']} on "
                f"{pick['lock_key']}; posted sibling {sibling} still "
                f"holds that lock")
            refused_siblings.append(pick["lock_key"])
        pending = safe
        if not pending:
            if refused_siblings:
                logger.info(
                    f"Discord void: nothing to post; {len(refused_siblings)} "
                    f"lock(s) kept, a posted sibling still holds them")
            else:
                logger.info(f"Discord void: nothing to post; {len(skipped)} lock(s) "
                            f"already noticed")
            return {"dry_run": dry_run, "posted": 0,
                    "skipped_lock_keys": skipped,
                    "refused_sibling_lock_keys": refused_siblings,
                    "payloads": []}

        by_sport: dict[str, list[dict]] = {}
        for pick in pending:
            by_sport.setdefault(pick["sport"] or "", []).append(pick)

        payloads: list[dict] = []
        for sport in sorted(by_sport):
            url = _webhook_for_sport(sport)
            embeds = void_notice_embeds(sport, by_sport[sport], text, url)
            for index, embed in enumerate(embeds):
                chunk = by_sport[sport][
                    sum(len(e["fields"]) for e in embeds[:index]):
                    sum(len(e["fields"]) for e in embeds[:index + 1])
                ]
                payloads.append({
                    "sport": sport,
                    "webhook_configured": bool(url),
                    "payload": {"embeds": [embed]},
                    "lock_keys": [p["lock_key"] for p in chunk],
                })

        if dry_run:
            for item in payloads:
                logger.info(f"[dry-run] discord void {item['sport']} "
                            f"{json.dumps(item['payload'], default=str)}")
            return {"dry_run": True, "posted": 0,
                    "skipped_lock_keys": skipped,
                    "refused_sibling_lock_keys": refused_siblings,
                    "payloads": payloads}

        missing = sorted({item["sport"] for item in payloads
                          if not item["webhook_configured"]})
        if missing:
            raise DiscordVoidRejected(
                [f"no webhook for {sport}" for sport in missing])

        sent_at = datetime.now(ET).isoformat()
        posted = 0
        message_ids: list[str] = []
        by_key = {p["lock_key"]: p for p in pending}
        for item in payloads:
            url = _webhook_for_sport(item["sport"])
            message_id = _post(url, item["payload"])
            if not message_id:
                raise DiscordVoidRejected(
                    [f"Discord rejected the {item['sport']} void notice; "
                     f"nothing was ledgered for that message"])
            chunk = [by_key[k] for k in item["lock_keys"]]
            _ledger_void(conn, chunk, sent_at, message_id)
            posted += len(chunk)
            message_ids.append(message_id)
        logger.success(f"✓ Discord void: posted {posted} pick(s)")
        return {"dry_run": False, "posted": posted,
                "skipped_lock_keys": skipped,
                "refused_sibling_lock_keys": refused_siblings,
                "message_ids": message_ids,
                "payloads": payloads}
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
