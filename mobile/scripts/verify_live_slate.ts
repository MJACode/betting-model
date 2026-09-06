/**
 * Standalone verification for the app's live-slate window
 * (src/lib/format.ts: liveSlateDatesET).
 *
 *   npx tsx scripts/verify_live_slate.ts
 *
 * This is the app half of tests/test_live_slate_midnight.py, and it exists for
 * the same reason that file does: THE FAILURE IS SILENT. An empty live board
 * and a missed live board render identically, so the only way to see it is to
 * stand at the boundary on purpose.
 *
 * A game carries the game_date of its KICKOFF. UCLA @ California kicked off at
 * 10:37pm ET on 2026-09-05 under game_date 2026-09-05; the live moneyline
 * crossed at 1:07am ET on 2026-09-06 and went to #ncaaf, because every backend
 * surface resolves its window through config.live_slate_dates(). The app asked
 * for a single todayET() — '2026-09-06' — and showed nothing, for the rest of
 * the game. CLAUDE.md §1b: the app, Discord and push show the same picks.
 *
 * Pinned here as PROPERTIES of the window, not as one fixture: a test that only
 * checked "00:30 works" would pass against a lookback of one hour and fail
 * again at 5am.
 */

import { liveSlateDatesET, LIVE_SLATE_LOOKBACK_UNTIL_HOUR_ET, todayET } from '../src/lib/format';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

/** A Date at a given ET wall-clock time. EDT (UTC-4) through the football season. */
function atET(y: number, m: number, d: number, hh: number, mm = 0): Date {
  return new Date(Date.UTC(y, m - 1, d, hh + 4, mm));
}

// ── the boundary ─────────────────────────────────────────────────────────────

check(
  'just after midnight still asks about yesterday',
  JSON.stringify(liveSlateDatesET(atET(2026, 9, 6, 0, 30))) ===
    JSON.stringify(['2026-09-06', '2026-09-05']),
  'the exact moment the live board went dark',
);

check(
  'the UCLA signal is inside the window it was posted in',
  // Discord posted UCLA ML at 1:07:06am ET on 2026-09-06, game_date 2026-09-05.
  liveSlateDatesET(atET(2026, 9, 6, 1, 7)).includes('2026-09-05'),
);

check(
  'just before midnight asks about today only',
  JSON.stringify(liveSlateDatesET(atET(2026, 9, 5, 23, 50))) === JSON.stringify(['2026-09-05']),
);

check(
  'by daytime yesterday is dropped',
  JSON.stringify(liveSlateDatesET(atET(2026, 9, 6, 12))) === JSON.stringify(['2026-09-06']),
  'nothing is still being played at noon, and an extra slate is an extra scan',
);

check(
  'the lookback ends before the next slate opens',
  LIVE_SLATE_LOOKBACK_UNTIL_HOUR_ET > 0 && LIVE_SLATE_LOOKBACK_UNTIL_HOUR_ET <= 10,
  `is ${LIVE_SLATE_LOOKBACK_UNTIL_HOUR_ET}`,
);

// ── properties that must hold at every hour ──────────────────────────────────

let todayFirst = true;
let sizeOk = true;
let lookbackExact = true;
for (let hour = 0; hour < 24; hour++) {
  const dates = liveSlateDatesET(atET(2026, 9, 6, hour));
  if (dates[0] !== '2026-09-06') todayFirst = false;
  if (dates.length < 1 || dates.length > 2) sizeOk = false;
  const wantsYesterday = hour < LIVE_SLATE_LOOKBACK_UNTIL_HOUR_ET;
  if (dates.includes('2026-09-05') !== wantsYesterday) lookbackExact = false;
}
check('today is always first', todayFirst, 'a caller that collapses to one date must still get today');
check('the window is never more than two dates', sizeOk);
check('yesterday is carried exactly while the lookback is open', lookbackExact);

check(
  'the window agrees with todayET on the same clock',
  liveSlateDatesET()[0] === todayET(),
  'the pre-game board and the live board must not disagree about what day it is',
);

// The mirror of config.live_slate_dates. If these drift, the app and the
// backend disagree about which games are live and the disagreement is silent.
check(
  'the lookback hour still mirrors config.LIVE_SLATE_LOOKBACK_UNTIL_HOUR_ET',
  LIVE_SLATE_LOOKBACK_UNTIL_HOUR_ET === 6,
  'change config.py and this together, or the surfaces diverge',
);

console.log(failures === 0 ? '\nAll live-slate checks passed.' : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
