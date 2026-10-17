/**
 * A bet Discord already posted keeps the cuts it was written under: the price
 * floor, the probability floor and the edge cut.
 *
 *   npx tsx scripts/verify_posted_bet_keeps_its_cuts.ts
 *
 * nfl_live_leader_ml's floor went from -5000 to -140 (mike, 2026-10-15 ET) the
 * night its first live bet laid -980. Re-cut at the new floor, that posted
 * bet would have fallen out of the day's pending list and lost its green
 * edge. Raising a model's edge or probability cut does the same; on mike's
 * "Yes" (2026-10-16 ET) all three are judged as posted. The cuts decide what a
 * model may bet next, never what it already posted.
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
  check(`${source}: a posted DUPLICATE copy is never an action`,
    !passesActionFilter({ ...bet, dk_odds: -130, decision_odds: -130, condition_status: 'DUPLICATE',
                          discordPublish: 'published' }));
  if (source === 'bundled') {
    // The offline fallback: the bundled cut is min_edge 0.02, so an edge of
    // 0.01 is below it. Posted, it keeps the cut it was written under.
    const thin = { ...bet, dk_odds: -130, decision_odds: -130, edge: 0.01, decision_edge: 0.01 };
    check('bundled: a posted bet below the edge cut still qualifies',
      passesActionFilter({ ...thin, discordPublish: 'published' }));
    check('bundled: the same bet unposted does not',
      !passesActionFilter({ ...thin, discordPublish: 'unpublished' }));
    check("bundled: nor with its ledger unread ('unknown')",
      !passesActionFilter({ ...thin, discordPublish: 'unknown' }));
  }
  // The edge cut raised above the bet's 0.061 (0.02 -> 0.07), and the
  // probability floor above its 0.968 (0 -> 0.99): posted, it still shows.
  const raised = { min_prob: 0.99, min_edge: 0.07, min_odds: -140, prob_only: false, paused: false };
  if (source === 'server') setServerThresholds({ nfl_live_leader_ml: raised });
  const rawEdge = { ...bet, dk_odds: -130, decision_odds: -130 };
  if (source === 'server') {
    check('server: a posted bet below a raised edge and probability cut still qualifies',
      passesActionFilter({ ...rawEdge, discordPublish: 'published' }));
    check('server: the same bet unposted does not',
      !passesActionFilter({ ...rawEdge, discordPublish: 'unpublished' }));
    check("server: nor with its ledger unread ('unknown')",
      !passesActionFilter({ ...rawEdge, discordPublish: 'unknown' }));
  }
}
// Posting keeps the cuts, not the model: a paused model's posted bet is still
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
