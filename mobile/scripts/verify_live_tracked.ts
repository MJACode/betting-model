/**
 * Verify computeLiveTrackedResults (lib/liveTracked.ts).
 * Run: npx tsx scripts/verify_live_tracked.ts
 */
import { computeLiveTrackedResults } from '../src/lib/liveTracked';
import type { LiveTrackSnapshot } from '../src/hooks/useTrackedBets';
import type { Pick } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean) {
  if (cond) console.log(`  PASS  ${name}`);
  else {
    failures++;
    console.log(`  FAIL  ${name}`);
  }
}

function mkPick(overrides: Partial<Pick>): Pick {
  return {
    pick_id: 1,
    game_id: 'MLB_2026-07-22_NYY_BOS',
    model_id: 'mlb_live_win_prob',
    sport: 'MLB',
    game_date: '2026-07-22',
    pick_side: 'home',
    pick_label: 'BOS ML (live)',
    model_probability: 0.72,
    dk_implied_prob: 0.6,
    edge: 0.12,
    dk_odds: -150,
    scored_line: null,
    kelly_fraction: 0.03,
    recommended_bet: 30,
    bankroll_at_pick: 1000,
    injury_flag: null,
    injury_detail: null,
    signal_type: 'BET',
    confidence_tier: 'HIGH',
    result: null,
    profit_flat: null,
    profit_kelly: null,
    settled_at: null,
    created_at: '2026-07-22T20:00:00Z',
    player_id: null,
    pitcher_throw_hand: null,
    is_live: true,
    inning_at_pick: 5,
    score_diff_at_pick: 1,
    public_bet_pct: null,
    public_money_pct: null,
    closing_dk_odds: null,
    closing_line: null,
    clv_pct: null,
    clv_captured_at: null,
    dk_bet_link: null,
    ...overrides,
  } as Pick;
}

function snap(overrides: Partial<LiveTrackSnapshot>): LiveTrackSnapshot {
  const game_id = overrides.game_id ?? 'MLB_2026-07-22_NYY_BOS';
  const model_id = overrides.model_id ?? 'mlb_live_win_prob';
  const pick_side = overrides.pick_side ?? 'home';
  return {
    key: `${game_id}|${model_id}|${pick_side}`,
    game_id,
    model_id,
    pick_side,
    pick_label: 'BOS ML (live)',
    sport: 'MLB',
    game_date: '2026-07-22',
    dk_odds: -150,
    scored_line: null,
    tracked_at: '2026-07-22T20:30:00Z',
    ...overrides,
  };
}

const G = 'MLB_2026-07-22_NYY_BOS';

// 1. Settled WIN — graded at $100 flat, counts.
{
  const s = snap({});
  // churn: an old (deleted-in-reality) unsettled row + the settled final row.
  const settledWin = mkPick({ pick_id: 20, result: 'WIN', profit_flat: 66.67 });
  const { rows, summary } = computeLiveTrackedResults([s], [settledWin], () => true);
  check('settled WIN → won', rows[0].status === 'won');
  check('settled WIN profit = 66.67', Math.abs(rows[0].profit - 66.67) < 1e-9);
  check('settled WIN uses the settled pick_id', rows[0].pick.pick_id === 20);
  check('summary wins=1, net 66.67', summary.wins === 1 && Math.abs(summary.net - 66.67) < 1e-9);
}

// 2. Churn: prefers the SETTLED row over a stale unsettled one for the same key.
{
  const s = snap({});
  const stale = mkPick({ pick_id: 10, result: null });
  const settledLoss = mkPick({ pick_id: 30, result: 'LOSS', profit_flat: -100 });
  const { rows } = computeLiveTrackedResults([s], [stale, settledLoss], () => true);
  check('prefers settled over unsettled', rows[0].pick.pick_id === 30 && rows[0].status === 'lost');
}

// 3. Game in progress, unsettled pick exists → open (latest pick_id shown).
{
  const s = snap({});
  const older = mkPick({ pick_id: 40, result: null });
  const newer = mkPick({ pick_id: 41, result: null });
  const { rows, summary } = computeLiveTrackedResults([s], [older, newer], () => false);
  check('in-progress → open', rows[0].status === 'open');
  check('open uses latest pick_id', rows[0].pick.pick_id === 41);
  check('open not counted (profit 0)', rows[0].profit === 0 && summary.open === 1);
}

// 4. Model moved off the side, game FINAL, no matching pick → no_action (synthetic).
{
  const s = snap({ pick_side: 'over', model_id: 'mlb_live_total_runs', pick_label: 'Over 9.5 (live)' });
  const otherSide = mkPick({
    pick_id: 50,
    model_id: 'mlb_live_total_runs',
    pick_side: 'under',
    result: 'WIN',
    profit_flat: 90,
  });
  const { rows, summary } = computeLiveTrackedResults([s], [otherSide], () => true);
  check('flipped-off side, game final → no_action', rows[0].status === 'no_action');
  check('no_action synthetic pick_id is negative', rows[0].pick.pick_id < 0);
  check('no_action not counted', summary.settled === 0 && summary.net === 0);
  check('no_action row renders snapshot label', rows[0].pick.pick_label === 'Over 9.5 (live)');
}

// 5. No matching pick, game NOT final → open (synthetic, game still going).
{
  const s = snap({ pick_side: 'away' });
  const { rows } = computeLiveTrackedResults([s], [], () => false);
  check('no pick + not final → open', rows[0].status === 'open' && rows[0].pick.pick_id < 0);
}

// 6. Kelly stake scales profit; dedupe of duplicate snapshot keys.
{
  const s = snap({});
  const dup = snap({});
  const settledWin = mkPick({ pick_id: 60, result: 'WIN', profit_flat: 50, kelly_fraction: 0.04 });
  const { rows, summary } = computeLiveTrackedResults(
    [s, dup],
    [settledWin],
    () => true,
    () => 200,
  );
  check('duplicate snapshot keys deduped', rows.length === 1);
  check('stake 200 scales profit 50 → 100', Math.abs(rows[0].profit - 100) < 1e-9);
  check('staked=200', summary.staked === 200);
}

// 7. Only the tracked game's picks are considered (cross-game isolation is the
//    caller's job, but a non-matching key must not resolve to another game).
{
  const s = snap({ game_id: G });
  const otherGame = mkPick({ game_id: 'MLB_2026-07-22_LAD_SF', result: 'WIN', profit_flat: 80 });
  const { rows } = computeLiveTrackedResults([s], [otherGame], () => false);
  check('different game does not resolve the snapshot', rows[0].pick.pick_id < 0 && rows[0].status === 'open');
}

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
