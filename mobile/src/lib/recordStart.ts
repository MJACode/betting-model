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
 * Below this many settled picks, an ROI is not coloured as a result.
 *
 * The window is days old, so the board currently holds models at 1, 5 and 8
 * settled bets. `ncaaf_live_win_prob` is 0-1 and renders -100%;
 * `mlb_prop_pitcher_outs` is 6-2 and renders +60.6% in green. Neither number
 * means anything, and the green one is the one a member screenshots.
 *
 * The row is NEVER hidden — "nothing hidden, nothing cherry-picked" is the
 * promise on the same screen. What changes is only that the number stops
 * wearing the bet/avoid colour that says "this is a result", and the row says
 * that it is provisional. 10 is the floor for treating a percentage as signal
 * at all.
 *
 * It deliberately does NOT carry the platform's >= 50-settled go-live gate any
 * more. That number was exported here purely to be quoted at members, and
 * quoting it announced "not backed yet" about live models. The gate still
 * governs backing server-side; it is not app copy.
 */
export const MIN_PICKS_FOR_COLOURED_ROI = 10;

/**
 * The ONE sentence every surface uses for "this record is too thin to read".
 *
 * Two callers — the Models tab's built-in rows and the Record tab's model rows.
 * It lives here, beside the constant that triggers it, for the same reason
 * `RETIRED_RULE_CAPTION` exists in `lib/modelMeta`: this state had drifted into
 * four phrasings across those two screens before it was pulled together.
 *
 * It says NOTHING about a go-live gate, and it takes no count. It used to read
 * "N of 50 settled · too few to judge", quoting the >= 50-settled bar from
 * CLAUDE.md §2 — which announced "this model is not backed yet" on every row
 * that had not reached it (Matt, 2026-09-06: *"Remove all paper trading ... we
 * are not doing paper trading"*, first on `ncaaf_live_win_prob`, then on
 * `ncaaf_spread` showing the same line). The platform is live; a
 * progress bar toward being backed described something it does not do.
 *
 * What survives is arithmetic, not status: below MIN_PICKS_FOR_COLOURED_ROI
 * decided bets a percentage is noise — `ncaaf_live_win_prob` is 0-1 and renders
 * -100% — so the number stops wearing the bet/avoid colour and this line says
 * why. Never returns empty: grey on its own does not explain itself.
 *
 * The go-live gate itself is untouched and still real. It lives server-side
 * (`models/backtester.GO_LIVE_MIN_PICKS`) where it governs whether a model is
 * backed; it is simply no longer narrated to members row by row.
 */
export function thinSampleCaption(): string {
  return 'Too few to judge yet';
}
