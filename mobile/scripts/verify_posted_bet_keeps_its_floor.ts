/**
 * A bet Discord already posted keeps the price floor it was written under.
 *
 *   npx tsx scripts/verify_posted_bet_keeps_its_floor.ts
 *
 * nfl_live_leader_ml's floor went from -5000 to -140 (mike, 2026-10-15 ET) the
 * night its first live bet laid -980. Re-cut at the new floor, that posted
 * bet fell out of the day's pending list and its edge lost its green. The
 * floor decides what the model may bet next, never what it already posted.
 */
import { passesActionFilter, setServerThresholds } from '../src/lib/thresholds';

let failed = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failed++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` - ${detail}` : ''}`);
}

const bet = {
  model_id: 'nfl_live_leader_ml',
  model_probability: 0.9683,
  edge: 0.0608,
  dk_odds: -980,
  decision_odds: -980,
  decision_edge: 0.0608,
  signal_type: 'BET' as const,
  condition_status: null,
};

for (const source of ['server', 'bundled'] as const) {
  setServerThresholds(
    source === 'server'
      ? { nfl_live_leader_ml: { min_prob: 0, min_edge: 0.02, min_odds: -140, prob_only: false, paused: false } }
      : null,
  );
  check(`${source}: the posted -980 bet still qualifies under the -140 floor`,
    passesActionFilter({ ...bet, discordPublish: 'published' }));
  check(`${source}: an unposted -980 bet does not`,
    !passesActionFilter({ ...bet, discordPublish: 'unpublished' }));
  check(`${source}: nor one whose ledger was not read`,
    !passesActionFilter({ ...bet }));
  check(`${source}: nor one whose ledger read failed ('unknown')`,
    !passesActionFilter({ ...bet, discordPublish: 'unknown' }));
  check(`${source}: a -130 bet qualifies either way`,
    passesActionFilter({ ...bet, dk_odds: -130, decision_odds: -130 }));
  check(`${source}: posting does not lift the edge cut`,
    !passesActionFilter({ ...bet, edge: 0.01, decision_edge: 0.01, discordPublish: 'published' }));
}
// Posting exempts the price floor only: a paused model's posted bet is still
// not an action.
setServerThresholds({
  nfl_live_leader_ml: { min_prob: 0, min_edge: 0.02, min_odds: -140, prob_only: false, paused: true },
});
check('server: a posted bet of a paused model is still refused',
  !passesActionFilter({ ...bet, dk_odds: -130, decision_odds: -130, discordPublish: 'published' }));
setServerThresholds(null);

if (failed) {
  console.log(`\n${failed} FAILURE(S)`);
  process.exit(1);
}
console.log('\nALL PASS');
