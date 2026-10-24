/**
 * Injury tags on the Stats board (Matt, 2026-10-23: Doubs ranked #3 on IR).
 *
 *   npx tsx scripts/verify_injury_status.ts
 *
 * Pins the tag per status, who greys and sinks, the team-first lookup, the
 * freshness window, the stable sink, the disabled price pill, and the
 * betslip add guard.
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { lineLegsAfterAdd, slipKeysAfterAdd } from '../src/lib/betslipGuard';
import type { GameLineLegSpec, PropLineLegSpec } from '../src/lib/lineLegs';
import {
  INJURY_FRESH_HOURS,
  buildInjuryIndex,
  injuryTag,
  pricePillActivation,
  sinkSidelined,
} from '../src/lib/injuryStatus';
import type { InjuryStatusRow } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const tag = (s: string, t?: string | null) => injuryTag(s, t);

// ── The tag per status ─────────────────────────────────────────────────────
check('NFL injured reserve reads IR and sits out', tag('Out', 'Injured Reserve')?.label === 'IR' && tag('Out', 'Injured Reserve')!.sidelined);
check('plain Out reads O and sits out', tag('Out', 'out')?.label === 'O' && tag('Out', null)!.sidelined);
check('a suspension reads SUSP and sits out', tag('Out', 'Suspension')?.label === 'SUSP' && tag('Out', 'Suspension')!.sidelined);
check('MLB IL keeps its length', tag('IL10')?.label === 'IL10' && tag('IL15')?.label === 'IL15' && tag('IL60')?.label === 'IL60');
check('every IL sits out', ['IL10', 'IL15', 'IL60'].every((s) => tag(s)!.sidelined));
check('Doubtful is red D but stays in the ranking', tag('Doubtful')?.label === 'D' && tag('Doubtful')?.tone === 'out' && !tag('Doubtful')!.sidelined);
check('Questionable is amber Q, playing', tag('Questionable')?.label === 'Q' && tag('Questionable')?.tone === 'warn' && !tag('Questionable')!.sidelined);
check('Day-To-Day is amber DTD, playing', tag('Day-To-Day')?.label === 'DTD' && tag('Day-To-Day')?.tone === 'warn' && !tag('Day-To-Day')!.sidelined);
check('an unknown status shows nothing', tag('Active') === null && tag('Returning') === null && tag('') === null);

// ── The index ───────────────────────────────────────────────────────────────
const NOW = Date.parse('2026-10-23T03:00:00Z');
const row = (o: Partial<InjuryStatusRow>): InjuryStatusRow => ({
  sport: 'NFL',
  team: 'NE',
  player_key: '',
  player_name: '',
  player_id: null,
  status: 'Out',
  injury_type: null,
  status_ts: null,
  as_of: '2026-10-23T02:50:22Z',
  ...o,
});
// Doubs as production stored him on 2026-10-23.
const doubs = row({ player_key: 'romeo doubs', player_name: 'Romeo Doubs', status: 'Out', injury_type: 'Injured Reserve' });
const idx = buildInjuryIndex(
  [
    doubs,
    row({ team: 'BUF', player_key: 'josh allen', player_name: 'Josh Allen', status: 'Questionable', injury_type: 'questionable' }),
    row({ team: 'JAX', player_key: 'josh allen', player_name: 'Josh Allen', status: 'Out', injury_type: 'out' }),
    row({ team: 'CHI', player_key: 'old news', player_name: 'Old News', as_of: '2026-10-21T00:00:00Z' }),
    row({ team: 'MIA', player_key: 'odell beckham', player_name: 'Odell Beckham Jr.', status: 'Doubtful' }),
  ],
  NOW,
);
check('Doubs on NE reads IR', idx.lookup('Romeo Doubs', 'NE')?.label === 'IR');
check('Doubs with no team on the row still reads IR', idx.lookup('Romeo Doubs', null)?.label === 'IR');
check('a teammate is not tagged', idx.lookup('Hunter Henry', 'NE') === null);
check('Doubs on another team is not tagged', idx.lookup('Romeo Doubs', 'GB') === null);
check('two Josh Allens: each team gets its own', idx.lookup('Josh Allen', 'BUF')?.label === 'Q' && idx.lookup('Josh Allen', 'JAX')?.label === 'O');
check('two Josh Allens and no team: say nothing', idx.lookup('Josh Allen', null) === null);
check('suffix and punctuation fold', idx.lookup('Odell Beckham', 'MIA')?.label === 'D' && idx.lookup('ODELL BECKHAM JR', 'MIA')?.label === 'D');
check(`a row older than ${INJURY_FRESH_HOURS}h is ignored`, idx.lookup('Old News', 'CHI') === null);
check('an empty feed tags nobody', buildInjuryIndex([], NOW).lookup('Romeo Doubs', 'NE') === null);

// ── The sink ────────────────────────────────────────────────────────────────
// The screenshot's board: Walker, Henry, Doubs, Douglas, Williams.
const board = ['Jahdae Walker', 'Hunter Henry', 'Romeo Doubs', 'DeMario Douglas', 'Kyle Williams'];
const sunk = sinkSidelined(board, (n) => !!idx.lookup(n, n === 'Jahdae Walker' ? 'CHI' : 'NE')?.sidelined);
check(
  'Doubs drops from #3 to last; the rest keep their order',
  sunk.join('|') === 'Jahdae Walker|Hunter Henry|DeMario Douglas|Kyle Williams|Romeo Doubs',
  sunk.join(', '),
);
const sameRef = sinkSidelined(board, () => false);
check('nobody out: the list is returned as is', sameRef === board);
const two = sinkSidelined([1, 2, 3, 4, 5], (n) => n === 1 || n === 3);
check('several out keep their own order at the bottom', two.join(',') === '2,4,5,1,3');

// ── The price pill does not press for a player who is not playing ──────────
const pill = (status: string, type?: string | null) => pricePillActivation(injuryTag(status, type)!.sidelined, true);
check('Out price pill has no press and is disabled', !pill('Out').pressable && pill('Out').disabled);
check('IR price pill has no press and is disabled', !pill('Out', 'Injured Reserve').pressable && pill('Out', 'Injured Reserve').disabled);
check(
  'SUSP and every IL pill are disabled the same way',
  !pill('Out', 'Suspension').pressable && ['IL10', 'IL15', 'IL60'].every((s) => !pill(s).pressable && pill(s).disabled),
);
check('Questionable price pill still presses', pill('Questionable').pressable && !pill('Questionable').disabled);
check('Doubtful price pill still presses', pill('Doubtful').pressable && !pill('Doubtful').disabled);
check('Day-to-day price pill still presses', pill('Day-To-Day').pressable && !pill('Day-To-Day').disabled);
check('a playing pill with no handler stays disabled', !pricePillActivation(false, false).pressable && pricePillActivation(false, false).disabled);

const statsSrc = readFileSync(join(import.meta.dirname, '../src/screens/StatsScreen.tsx'), 'utf8');
check('OddsCell asks pricePillActivation', statsSrc.includes('pricePillActivation(muted, onPress != null)'));
check('OddsCell omits onPress when the pill is not pressable', statsSrc.includes('onPress: pill.pressable ? onPress : undefined'));
check('OddsCell disables the pill when the activation says so', statsSrc.includes('disabled: pill.disabled'));
check(
  'a muted pill sets accessibilityState disabled and keeps the not-playing label',
  statsSrc.includes('accessibilityState: muted ? { disabled: true } : undefined') &&
    statsSrc.includes("${playerName}${muted ? ', not playing' : ''}"),
);

// ── The betslip add itself rejects a sidelined player ──────────────────────
const prop = (name: string, team: string | null): PropLineLegSpec => ({
  kind: 'prop',
  game_id: 'NFL_2026-10-23_NE_CHI',
  sport: 'NFL',
  market: 'player_anytime_td',
  player_name: name,
  team,
  line: 0.5,
  side: 'over',
  statLabel: 'Anytime TD',
});
check('betslip add rejects Doubs on IR', lineLegsAfterAdd([], prop('Romeo Doubs', 'NE'), idx) === null);
check('betslip add rejects Doubs with no team, one listing', lineLegsAfterAdd([], prop('Romeo Doubs', null), idx) === null);
check('betslip add rejects the Out Josh Allen', lineLegsAfterAdd([], prop('Josh Allen', 'JAX'), idx) === null);
check('betslip add accepts the Questionable Josh Allen', lineLegsAfterAdd([], prop('Josh Allen', 'BUF'), idx)?.length === 1);
check('betslip add does not guess between two Josh Allens', lineLegsAfterAdd([], prop('Josh Allen', null), idx)?.length === 1);
check('betslip add accepts Doubtful', lineLegsAfterAdd([], prop('Odell Beckham Jr.', 'MIA'), idx)?.length === 1);
check('betslip add accepts a player who is not on a report', lineLegsAfterAdd([], prop('Hunter Henry', 'NE'), idx)?.length === 1);
const gameLeg: GameLineLegSpec = {
  kind: 'game',
  game_id: 'NFL_2026-10-23_NE_CHI',
  sport: 'NFL',
  market: 'h2h',
  team: 'NE',
  opponent: 'CHI',
  isHome: false,
  line: null,
  side: null,
};
check('a game line is not rejected as an injured player', lineLegsAfterAdd([], gameLeg, idx)?.length === 1);
check(
  'pick-slip add rejects a sidelined name',
  slipKeysAfterAdd([], 'g|nfl_prop_market|doubs', { name: 'Romeo Doubs', team: 'NE' }, idx) === null,
);
check(
  'pick-slip add accepts Questionable',
  slipKeysAfterAdd([], 'g|nfl_prop_market|allen', { name: 'Josh Allen', team: 'BUF' }, idx)?.[0] === 'g|nfl_prop_market|allen',
);
check('pick-slip add with no player is kept', slipKeysAfterAdd([], 'g|nfl_moneyline|', null, idx)?.length === 1);
check(
  'a duplicate key is not added twice',
  slipKeysAfterAdd(['already'], 'already', { name: 'Hunter Henry', team: 'NE' }, idx) === null,
);

const lineHook = readFileSync(join(import.meta.dirname, '../src/hooks/useLineLegs.ts'), 'utf8');
const slipHook = readFileSync(join(import.meta.dirname, '../src/hooks/useParlaySlip.ts'), 'utf8');
check(
  'the line-leg store loads the injury index and admits through the guard',
  lineHook.includes('injuryIndexForSport(') && lineHook.includes('lineLegsAfterAdd('),
);
check(
  'the pick store loads the injury index and admits through the guard',
  slipHook.includes('injuryIndexForSport(') && slipHook.includes('slipKeysAfterAdd('),
);
const sheet = readFileSync(join(import.meta.dirname, '../src/components/AddLineSheet.tsx'), 'utf8');
const addedAt = sheet.indexOf('const added = await legs.add(spec)');
const toastAt = sheet.indexOf("showToast('Added to betslip')");
check('the sheet does not toast an add the guard rejected', addedAt >= 0 && toastAt > addedAt && sheet.includes('if (!added) return'));
const readSrc = (p: string) => readFileSync(join(import.meta.dirname, p), 'utf8');
check('pick detail names the player on the slip toggle', readSrc('../src/screens/PickDetailScreen.tsx').includes('betslipPlayerFromPick(pick)'));
check('the picks board names the player on the slip toggle', readSrc('../src/screens/PicksHomeScreen.tsx').includes('betslipPlayerFromPick(item.pick)'));
check(
  'the player page names the player on the slip toggle',
  readSrc('../src/screens/PlayerStatsScreen.tsx').includes('name: playerName'),
);
check(
  'a restored slip names the player when the pick is on the board',
  readSrc('../src/screens/ParlayScreen.tsx').includes('betslipPlayerFromPick(ep.pick)') &&
    readSrc('../src/screens/ParlayScreen.tsx').includes('if (boardLoading) return') &&
    readSrc('../src/screens/ParlayScreen.tsx').includes('slipKeysAfterAdd(') &&
    readSrc('../src/screens/ParlayScreen.tsx').includes('slip.replace(kept)'),
);
check(
  'a disabled price pill claims the touch so the row does not open',
  statsSrc.includes('onStartShouldSetResponder={() => true}'),
);

console.log(failures === 0 ? '\nAll injury-status checks passed.' : `\n${failures} check(s) failed.`);
process.exit(failures === 0 ? 0 : 1);
