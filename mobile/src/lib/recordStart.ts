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
export const LIVE_RECORD_START_SHORT = '09-01';
