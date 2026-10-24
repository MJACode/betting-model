/**
 * Injury tags on the Stats board (Matt, 2026-10-23: Doubs ranked #3 on IR).
 *
 *   npx tsx scripts/verify_injury_status.ts
 *
 * Pins the tag per status, who greys and sinks, the team-first lookup, the
 * freshness window, and the stable sink.
 */
import {
  INJURY_FRESH_HOURS,
  buildInjuryIndex,
  injuryTag,
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

console.log(failures === 0 ? '\nAll injury-status checks passed.' : `\n${failures} check(s) failed.`);
process.exit(failures === 0 ? 0 : 1);
