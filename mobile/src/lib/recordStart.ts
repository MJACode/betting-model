/**
 * The official live date — the one place the app states when the record starts.
 *
 * Matt, 2026-09-04: "only start tracking bets as of 9/1 and on, that will be our
 * official live date."
 *
 * It was 2026-04-14 (the v8 retrain), spelled out in five separate files and in
 * four screens' copy, which is why moving it touched all of them. It lives here
 * now so the next move is one edit.
 *
 * This MUST match `config.PAPER_TRADING_START` on the backend and the
 * `game_date >= '2026-09-01'` gate inside `v_public_track_record` /
 * `v_public_track_record_daily` (data/migrations/live_record_start_2026_09_01.sql).
 * The server is what actually filters; this constant only decides how far back
 * the app asks and what the copy says. A mismatch shows up as the app asking for
 * rows the view will never return — wasteful, not wrong.
 *
 * Nothing before this date is deleted. Every earlier pick stays in `picks` and
 * stays the bet of record (CLAUDE.md §1c); it is simply outside the published
 * window. The threshold-sweep views deliberately keep their own, longer history
 * — a cut cannot be swept on a few days of data (CLAUDE.md §7).
 */

/** ISO date the published record starts at. */
export const LIVE_RECORD_START = '2026-09-01';

/** How the start reads in body copy — "since September 1, 2026". */
export const LIVE_RECORD_START_LABEL = 'September 1, 2026';

/** Compact form for a tile caption, matching the Record tab's "Since" tile. */
export const LIVE_RECORD_START_SHORT = 'Sep 1, 2026';

/**
 * The BACKTEST window — deliberately longer than the published one.
 *
 * A custom model is backtested by the `custom_model_backtest` RPC, which reads
 * `mv_scored_pick_outcomes`. That matview keeps its 2026-04-14 gate on purpose:
 * it is the threshold-sweep universe, and a filter cannot be judged on a few
 * days of picks (CLAUDE.md §7). So a backtest genuinely covers a longer window
 * than the published record, and the copy beside it MUST say the longer date —
 * labelling an April-onward number "since September 1" would overstate the
 * sample by five months.
 *
 * Two dates, two constants, both named. That is the honest shape; one date
 * pretending to cover both surfaces is what this file exists to prevent.
 */
export const BACKTEST_START = '2026-04-14';
export const BACKTEST_START_LABEL = 'April 14, 2026';

/**
 * The opening-signal shadow track's own start. Same reasoning as BACKTEST_START:
 * a comparison of "what the opener would have done" needs history to compare
 * against. Named here rather than left local to the screen so the next reader
 * finds all three windows in one place — and so it stops being called
 * PAPER_START, which the platform is not (CLAUDE.md §2).
 */
export const SHADOW_TRACK_START = '2026-04-14';

/**
 * EVERY SETTLED BET COUNTS, AND EVERY ROW SHOWS ITS RECORD IN FULL.
 *
 * Matt, 2026-11-21: "I don't care if they're not enough bets to tell if it's
 * successful. We're still keeping track of it regardless, so it counts ... stop
 * making those decisions without asking me."
 *
 * There used to be a 10-decided-bet floor here (MIN_PICKS_FOR_COLOURED_ROI)
 * under which a model's ROI and units were greyed and captioned "Too few to
 * judge yet". It was a display judgement nobody asked for, and it is gone: a
 * 1-bet model shows its ROI in the same colour as a 500-bet one. Do not bring
 * back a sample-size floor, caption or greying on any record surface without
 * Matt's approval in chat (CLAUDE.md §1b).
 */
