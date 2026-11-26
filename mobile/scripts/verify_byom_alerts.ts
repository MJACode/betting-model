/**
 * Alerts and open bets on the member's own models (Matt, 2026-11-25). Run:
 *
 *   npx tsx scripts/verify_byom_alerts.ts
 *
 * The push payload is a contract with byom/alerts.py (message_for): type
 * 'byom_bet' and a modelId opens that model. A row the card cannot draw
 * is dropped, never drawn with a made-up price.
 */

import { routeForPush, PUSH_ROUTE_VERSION } from '../src/lib/pushRoute';
import { isMissingFunction, matchupLabel, parseOpenBet } from '../src/lib/byomAlertRows';
import { asByomSport, byomHasProps, byomSeasonName, byomStartWord, byomUsesRest, seasonListFor } from '../src/lib/byomRecord';

let failed = 0;
function check(name: string, ok: boolean, detail?: unknown): void {
  if (ok) {
    console.log(`ok   ${name}`);
  } else {
    failed += 1;
    console.log(`FAIL ${name}`, detail ?? '');
  }
}

const MODEL = 'aaaaaaaa-0000-0000-0000-000000000001';

const route = routeForPush({ v: PUSH_ROUTE_VERSION, type: 'byom_bet', sport: 'NFL', modelId: MODEL, alertId: 'x' });
check('a byom_bet push opens its model', JSON.stringify(route) === JSON.stringify({ kind: 'byomModel', modelId: MODEL }), route);
check('no modelId opens only the app', routeForPush({ v: PUSH_ROUTE_VERSION, type: 'byom_bet' }) === null);
check('a non-uuid modelId opens only the app', routeForPush({ v: PUSH_ROUTE_VERSION, type: 'byom_bet', modelId: '1; drop' }) === null);
check('another version opens only the app', routeForPush({ v: PUSH_ROUTE_VERSION + 1, type: 'byom_bet', modelId: MODEL }) === null);

const row = {
  alert_id: 'a1', model_id: MODEL, model_name: 'Home favorites', sport: 'NFL',
  market: 'spreads', label: 'BUF +1', home_team: 'BUF', away_team: 'DET',
  commence_time: '2026-11-27T01:20:00+00:00', price: '-110',
  locked_at: '2026-11-25T14:00:00+00:00', detected_at: '2026-11-25T14:12:00+00:00', started: false,
};
const bet = parseOpenBet(row);
check('a row parses with its label word for word', bet != null && bet.label === 'BUF +1' && bet.price === -110, bet);
check('the matchup is away @ home', bet != null && matchupLabel(bet) === 'DET @ BUF');
check('a row with no price is dropped', parseOpenBet({ ...row, price: null }) === null);
check('a row with no label is dropped', parseOpenBet({ ...row, label: '' }) === null);
check('a missing RPC reads as not applied', isMissingFunction({ code: 'PGRST202' }) && !isMissingFunction({ code: '42501' }));

// NCAAB game lines on the builder (Matt, 2026-11-26).
const nov = new Date('2026-11-26T15:00:00Z');
const ncaab = seasonListFor('NCAAB', nov);
check('NCAAB seasons run 2021 to the ending year 2027', ncaab[0] === 2021 && ncaab[ncaab.length - 1] === 2027, ncaab);
check('NCAAB is game bets only', !byomHasProps('NCAAB') && byomHasProps('NFL') && byomHasProps('NBA') && !byomHasProps('NHL'));
check('NCAAB uses rest chips and tipoff', byomUsesRest('NCAAB') && byomStartWord('NCAAB') === 'tipoff');
check('an NCAAB season reads 2026-27', byomSeasonName('NCAAB', 2027) === '2026-27');
check('NCAAB round-trips as a sport', asByomSport('NCAAB') === 'NCAAB' && asByomSport('NCAAF') === 'NFL');

if (failed > 0) {
  console.log(`${failed} check(s) failed`);
  process.exit(1);
}
console.log('all checks passed');
