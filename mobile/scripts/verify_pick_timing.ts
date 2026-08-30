/**
 * Standalone verification for pick post-time display. Run with:
 *
 *   npx tsx scripts/verify_pick_timing.ts
 *
 * Pins: pickTimingInfo stamps only LOCKED bets (a locked row is never
 * rewritten, so created_at IS the post time) and refuses the two classes where
 * created_at is the latest re-score instead — non-BET rows (AVOID, the NCAAF
 * "watching" NONE rows) and unlocked look-ahead previews (future UFC/golf);
 * the live lock carries its period and reads as the bet of record; NFL keeps
 * its opener-vs-wind verbs; and formatStampET drops the date only when the
 * stamp is today in ET.
 */

import { formatStampET, todayET } from '../src/lib/format';
import { UNLOCKED_LOOKAHEAD_SPORTS } from '../src/lib/thresholds';
import { pickTimingInfo } from '../src/lib/markets';
import type { Pick, PickSide } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const NOW = new Date().toISOString();
const THREE_DAYS_AGO = new Date(Date.now() - 3 * 86400_000).toISOString();

function mkPick(over: Partial<Pick>): Pick {
  return {
    pick_id: 1,
    game_id: 'MLB_2026-08-30_NYY_BOS',
    model_id: 'mlb_moneyline',
    sport: 'MLB',
    game_date: '2026-08-30',
    game_time: '2026-08-30T23:05:00+00:00',
    pick_side: 'home' as PickSide,
    pick_label: 'NYY @ BOS — BOS ML',
    model_probability: 0.73,
    dk_implied_prob: 0.6,
    edge: 0.13,
    dk_odds: -150,
    scored_line: null,
    kelly_fraction: 0.02,
    recommended_bet: 100,
    bankroll_at_pick: 10000,
    injury_flag: null,
    injury_detail: null,
    signal_type: 'BET',
    confidence_tier: null,
    result: null,
    profit_flat: null,
    profit_kelly: null,
    settled_at: null,
    created_at: NOW,
    player_id: null,
    pitcher_throw_hand: null,
    is_live: null,
    inning_at_pick: null,
    score_diff_at_pick: null,
    public_bet_pct: null,
    public_money_pct: null,
    closing_dk_odds: null,
    closing_line: null,
    clv_pct: null,
    clv_captured_at: null,
    dk_bet_link: null,
    ...over,
  } as Pick;
}

// ── formatStampET ───────────────────────────────────────────────────────────
{
  const today = formatStampET(NOW);
  const older = formatStampET(THREE_DAYS_AGO);
  check('today stamp is time only', /^\d{1,2}:\d{2} (AM|PM) ET$/.test(today), today);
  check(
    'off-day stamp carries the day',
    /^[A-Z][a-z]{2},? \d{1,2}\/\d{1,2} · \d{1,2}:\d{2} (AM|PM) ET$/.test(older),
    older,
  );
  check('no stamp without a timestamp', formatStampET(null) === '');
}

// ── locked pre-game signals ─────────────────────────────────────────────────
{
  const game = pickTimingInfo(mkPick({}));
  check('game BET posts', game?.kind === 'posted' && game.verb === 'Posted');
  check('game label is "Posted <time>"', game?.label === `Posted ${formatStampET(NOW)}`, game?.label);
  check('game note names the daily lock', Boolean(game?.note.includes('first scoring run')));

  const prop = pickTimingInfo(
    mkPick({ model_id: 'mlb_prop_batter_hits', player_id: '660271', created_at: NOW }),
  );
  check('prop note names the lineup lock', Boolean(prop?.note.includes('lineup is confirmed')));

  const yesterday = pickTimingInfo(mkPick({ created_at: THREE_DAYS_AGO }));
  check(
    'an off-day post shows its date',
    Boolean(yesterday?.label.startsWith('Posted ') && yesterday.label.includes(' · ')),
    yesterday?.label,
  );
}

// ── live first-signal lock ──────────────────────────────────────────────────
{
  const mlb = pickTimingInfo(mkPick({ is_live: true, inning_at_pick: 3 }));
  check('live BET is the locked kind', mlb?.kind === 'live' && mlb.verb === 'Locked');
  check(
    'live label carries time, inning and bet-of-record',
    mlb?.label === `Locked ${formatStampET(NOW)} · inning 3 — bet of record`,
    mlb?.label,
  );
  check('live note says the price is not the current one', Boolean(mlb?.note.includes('not the current')));

  const ncaaf = pickTimingInfo(
    mkPick({ sport: 'NCAAF', model_id: 'ncaaf_over_under', is_live: true, inning_at_pick: 4 }),
  );
  check('NCAAF live shows a quarter, not an inning', Boolean(ncaaf?.label.includes('· Q4')), ncaaf?.label);

  const noPeriod = pickTimingInfo(mkPick({ is_live: true, inning_at_pick: null }));
  check(
    'live without a period still stamps the time',
    noPeriod?.label === `Locked ${formatStampET(NOW)} — bet of record`,
    noPeriod?.label,
  );
}

// ── NFL keeps its opener/wind distinction ───────────────────────────────────
{
  const opener = pickTimingInfo(
    mkPick({ sport: 'NFL', model_id: 'nfl_opener_spread', created_at: THREE_DAYS_AGO }),
  );
  check('opener is Locked', opener?.kind === 'nfl' && opener.verb === 'Locked');
  check('opener label carries the day it locked', Boolean(opener?.label.includes(' · ')), opener?.label);
  check('opener note still says never re-priced', Boolean(opener?.note.includes('never re-priced')));

  const wind = pickTimingInfo(mkPick({ sport: 'NFL', model_id: 'nfl_wind_totals' }));
  check('wind is Priced, not Locked', wind?.verb === 'Priced', wind?.label);
}

// ── what must NOT be stamped ────────────────────────────────────────────────
{
  check('AVOID has no post time', pickTimingInfo(mkPick({ signal_type: 'AVOID' })) === null);
  check(
    'a dead-zone/watching row has no post time',
    pickTimingInfo(mkPick({ signal_type: 'NONE', sport: 'NCAAF', model_id: 'ncaaf_spread' })) === null,
  );
  check('no timestamp, no stamp', pickTimingInfo(mkPick({ created_at: '' })) === null);

  // UNLOCKED_LOOKAHEAD_SPORTS is empty today (retired 2026-08-28: every fired
  // pick is a locked bet of record), so a future-dated UFC pick IS stamped.
  // The guard is a seam for a sport re-added there — a pick that re-prices
  // after posting has a created_at that no longer means "posted" — so pin both
  // sides of it rather than trusting an always-false branch.
  const future = new Date(Date.now() + 3 * 86400_000).toISOString().slice(0, 10);
  const ahead = mkPick({
    sport: 'UFC',
    model_id: 'ufc_moneyline',
    game_date: future,
    game_id: `UFC_${future}_a_b`,
  });
  check('no sport is an unlocked preview today', UNLOCKED_LOOKAHEAD_SPORTS.size === 0);
  check('a look-ahead UFC BET is stamped', pickTimingInfo(ahead)?.kind === 'posted');
  UNLOCKED_LOOKAHEAD_SPORTS.add('UFC');
  check('a re-added look-ahead sport is not stamped', pickTimingInfo(ahead) === null);
  check('and its same-day pick still is', pickTimingInfo({ ...ahead, game_date: todayET() })?.kind === 'posted');
  UNLOCKED_LOOKAHEAD_SPORTS.delete('UFC');
}

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
if (failures > 0) process.exit(1);
