"""
Take a BET that has just been written and get it onto every surface — from ANY
writer, not just the refresh pass.

WHY THIS EXISTS (2026-09-05, mike: "when there is a bet from the model, post
the pick")

Publishing used to live only at the end of `scripts/refresh_pass.sh`: the
`opening-signals` step locked the day's new crosses and `push-notifications`
delivered them. Every other writer in the system just wrote picks and waited.

The pre-game line poller (`data/ingestors/pregame_line_poller.py`) is one of
those writers, and it runs every 30 seconds. So a BET it wrote could sit
unpublished for up to an hour — until the next `:17` pass captured and posted
it. Measured cost on the 2026-09-05 UFC card:

    18:27:16Z  poller writes  mario-pinto/ryan-spann  ufc_moneyline  -195  BET
    18:40:00Z  the fight starts
    19:17:00Z  the next refresh pass -- the first thing that would have posted
               it -- runs, and the poster's "never post a started fight" guard
               drops it, correctly and permanently.

That pick existed 13 minutes before the fight and was publishable for every one
of them. MLB never noticed the gap because first pitches are hours apart; a UFC
card starts a fight every 20-30 minutes, and NFL/NCAAF crosses inside the hour
before kickoff have exactly the same shape. Of the three UFC signals ever
locked since Discord posting shipped on 2026-08-23, ONE reached Discord.

WHAT THIS IS
The three steps that turn a written BET into a published one, in the order they
have to happen, callable from anywhere:

    capture_opening_signals   stamp the cross into the CLV shadow track
      -> notify_signal_changes  push it to opted-in devices
      -> notify_discord_signals post it to the sport's channel

Both notifiers read `picks` directly (2026-09-05), so this adds no gate the
app does not already apply -- it only decides WHEN they are asked.

CLAUDE.md §1b: a change to how one model operates is assessed against all of
them, and the shared helper is preferred over a per-sport implementation. This
is that helper. It is sport-agnostic on purpose — nothing in it names UFC.

WHAT IT IS NOT
  * Not a second delivery rule. It calls the same three functions the refresh
    pass calls, so the thresholds, the first-pitch guard, the started-game
    guard and the `push_sent` ledger all apply exactly as they already do.
    Publishing sooner cannot publish anything MORE than the pass would have.
  * Not a way to re-price a pick. It publishes what was already written (§1c);
    it never scores.
  * Not the whole of the pass's notification step. The daily free pick, the
    restatement path, track-a-bet line changes and feedback replies belong to
    a scheduled pass and stay there — a price-watching loop must not be able
    to fire them.

IDEMPOTENT, AND SAFE TO CALL OFTEN. Every step below is ledgered or
ON CONFLICT DO NOTHING, so calling this on a tick that locked nothing is three
cheap reads and no side effects.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def publish_new_signals(target_date: str | None = None,
                        dry_run: bool = False) -> dict:
    """Lock and deliver newly-crossed BET signals. Returns per-surface counts.

    NEVER RAISES, and each surface gets its OWN try block. Two reasons, both
    load-bearing:

      * The caller is a loop whose whole job is watching prices. An exception
        here must not be able to stop it — a stopped poller and a quiet market
        look identical from the outside.
      * A broken Discord webhook must not suppress the push, and a failed
        capture must not skip delivery at all: the notifiers read `picks`, not
        this call's own output, so the pick is postable whether or not the
        shadow track took it.
    """
    import config

    if target_date is None:
        target_date = config.today_et()

    out = {"locked": 0, "pushed": 0, "discord": 0}

    # 1. Lock the cross into the opening-signal / CLV shadow track.
    #
    # NOT a gate on delivery: since 2026-09-05 both notifiers read `picks`
    # directly (Matt: "the app and discord should always show the same picks"),
    # so capture can only inform the shadow track, never decide what posts.
    # It runs FIRST anyway, because its whole value is a `locked_at` that says
    # when the cross happened -- and its own first-pitch guard drops a capture
    # that arrives after the game started, which is exactly what waiting for
    # the next pass produced.
    try:
        from tracking.opening_signals import capture_opening_signals
        out["locked"] = capture_opening_signals(
            target_date=target_date, dry_run=dry_run) or 0
    except Exception as exc:                                  # noqa: BLE001
        logger.error(f"publish: opening-signal capture failed: {exc}",
                     exc_info=True)

    # 2. Push to devices.
    try:
        from tracking.push_notifier import notify_signal_changes
        out["pushed"] = notify_signal_changes(
            target_date=target_date, dry_run=dry_run) or 0
    except Exception as exc:                                  # noqa: BLE001
        logger.error(f"publish: push notification failed: {exc}", exc_info=True)

    # 3. Post to the sport's Discord channel. Last and independently guarded —
    # the push has already gone out by here, so a webhook problem costs the
    # Discord copy and nothing else.
    try:
        from tracking.discord_notifier import notify_discord_signals
        out["discord"] = notify_discord_signals(
            target_date=target_date, dry_run=dry_run) or 0
    except Exception as exc:                                  # noqa: BLE001
        logger.error(f"publish: Discord post failed: {exc}", exc_info=True)

    if any(out.values()):
        logger.info(f"publish [{target_date}]: {out['locked']} locked, "
                    f"{out['pushed']} pushed, {out['discord']} to Discord")
    return out
