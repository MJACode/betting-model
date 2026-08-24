/**
 * Standalone verification for the multi-sport player detail layer
 * (src/lib/playerLog.ts). Run with:
 *
 *   npx tsx scripts/verify_player_log.ts
 *
 * Pins the behaviours that let one player detail screen serve every sport:
 *  - which sports have a player log at all (UFC/NHL/Golf must stay out);
 *  - derived stats the raw log tables do not store (basketball threes/PRA, NFL
 *    rush+rec TDs, MLB outs) are computed the same way the leaderboard views
 *    compute them in SQL, and a missing input stays missing rather than zero;
 *  - the line stepper moves in increments the sport's numbers actually use, and
 *    the auto line lands on that grid;
 *  - MLB keeps its batter/pitcher split and swaps Innings for Outs, because
 *    5.2 IP means five and two THIRDS and cannot be compared against a line.
 */

import {
  chipGroupsFor,
  chipsForPlayer,
  defaultChipForPlayer,
  detailStatForPropModel,
  gameContextLine,
  ipToOuts,
  lineStepFor,
  logFetchLimit,
  logStatValue,
  normalizeLogRow,
  playerSubtitle,
  roundLineToStep,
  supportsPlayerDetail,
  windowOptionsFor,
  type PlayerLogEntry,
} from '../src/lib/playerLog';
import { statForPropModel, type StatDef } from '../src/lib/statCatalog';

let failures = 0;
function check(name: string, ok: boolean) {
  if (!ok) failures += 1;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}`);
}

const statOf = (sport: 'MLB' | 'WNBA' | 'NBA' | 'NFL', label: string, playerType?: 'batter' | 'pitcher'): StatDef =>
  chipsForPlayer(sport, playerType).find((s) => s.label === label)!;

// ── Which sports get a detail screen ────────────────────────────────────────
for (const s of ['MLB', 'WNBA', 'NBA', 'NFL'] as const) {
  check(`${s} has a player detail screen`, supportsPlayerDetail(s));
}
for (const s of ['UFC', 'NHL', 'GOLF'] as const) {
  check(`${s} has NO player detail screen (no per-game player log)`, !supportsPlayerDetail(s));
}

// ── Derived stats mirror the leaderboard views ──────────────────────────────
const wnbaRow = normalizeLogRow('WNBA', {
  player_id: '1', player_name: 'A Player', team: 'LV', game_id: 'g', game_date: '2026-08-01',
  season: 2026, minutes: 31.4, points: 20, rebounds: 8, assists: 5, fg3_made: 3,
});
check('WNBA threes come from fg3_made', wnbaRow.threes === 3);
check('WNBA PRA = points + rebounds + assists', wnbaRow.pra === 33);

const nbaRow = normalizeLogRow('NBA', { points: 10, rebounds: null, assists: 2, fg3_made: null });
check('NBA PRA ignores a missing component rather than zeroing it', nbaRow.pra === 12);
check('NBA threes stay null when fg3_made is null', nbaRow.threes === null);

const allNull = normalizeLogRow('NBA', { points: null, rebounds: null, assists: null });
check('an all-missing PRA is null, not 0 (a null game must not count as a zero game)',
  allNull.pra === null);

const nflRow = normalizeLogRow('NFL', {
  player_id: '2', player_name: 'A Back', team: 'SF', opponent: 'SEA', week: 4, pos: 'RB',
  game_id: 'g', game_date: '2026-09-28', season: 2026,
  rushing_yards: '84.0', rushing_tds: 1, receiving_tds: 1, receptions: 3,
});
check('NFL rush+rec TDs sum', nflRow.rush_rec_tds === 2);
check('NFL yardage arriving as a NUMERIC string still reads as a number',
  logStatValue(nflRow, statOf('NFL', 'Rush Yards')) === 84);

// ── MLB innings notation ────────────────────────────────────────────────────
check('5.2 IP is five and two thirds = 17 outs', ipToOuts(5.2) === 17);
check('6.0 IP = 18 outs', ipToOuts(6) === 18);
check('missing IP stays null', ipToOuts(null) === null);
const mlbPitch = normalizeLogRow('MLB', { innings_pitched: 5.2, p_strikeouts: 7, player_type: 'pitcher' });
check('MLB rows carry a derived outs column', mlbPitch.outs === 17);
check('MLB pitching offers Outs, never Innings (5.2 >= 5.5 would be false and wrong)',
  chipsForPlayer('MLB', 'pitcher').some((c) => c.label === 'Outs') &&
  !chipsForPlayer('MLB', 'pitcher').some((c) => c.label === 'Innings'));

// ── Chips ───────────────────────────────────────────────────────────────────
check('MLB batter chips exclude pitching stats',
  chipsForPlayer('MLB', 'batter').every((c) => c.group === 'Batting'));
check('MLB pitcher chips exclude batting stats',
  chipsForPlayer('MLB', 'pitcher').every((c) => c.group === 'Pitching'));
check('MLB batter opens on Hits (unchanged)', defaultChipForPlayer('MLB', 'batter')?.label === 'Hits');
check('WNBA opens on Points', defaultChipForPlayer('WNBA')?.label === 'Points');
check('NFL opens on Pass Yards', defaultChipForPlayer('NFL')?.label === 'Pass Yards');
check('NFL chips span four groups', chipGroupsFor('NFL').join() === 'Passing,Rushing,Receiving,Defense');
check('WNBA has a single group, so no group tab row', chipGroupsFor('WNBA').length === 1);
check('MLB has a single group per player type', chipGroupsFor('MLB', 'batter').length === 1);
check('every WNBA chip resolves against a WNBA log row',
  chipsForPlayer('WNBA').every((c) => logStatValue(wnbaRow, c) !== undefined));

// ── Line stepper ────────────────────────────────────────────────────────────
check('hits step by 1', lineStepFor(statOf('MLB', 'Hits', 'batter')) === 1);
check('points step by 1', lineStepFor(statOf('WNBA', 'Points')) === 1);
check('PRA steps by 1 (books hang 24.5, 25.5 — not 20/25/30)', lineStepFor(statOf('WNBA', 'PRA')) === 1);
check('rushing yards step by 5', lineStepFor(statOf('NFL', 'Rush Yards')) === 5);
check('passing yards step by 25', lineStepFor(statOf('NFL', 'Pass Yards')) === 25);
check('a null stat still yields a usable step', lineStepFor(null) === 1);

check('a median of 2 with step 1 gives a line of 2 (matches the MLB screen today)',
  roundLineToStep(2, 1) === 2);
check('a zero median never produces a line of 0', roundLineToStep(0, 1) === 1);
check('a 237-yard median snaps to 225 on a 25 grid', roundLineToStep(237, 25) === 225);
check('a tiny median never falls below one step', roundLineToStep(3, 25) === 25);

// ── Windows and fetch size ──────────────────────────────────────────────────
check('NFL windows start at L3 (a season is 17 games)',
  windowOptionsFor('NFL').map((w) => w.label).join() === 'L3,L5,L10,All');
check('MLB/basketball windows are L5/L10/L20/All',
  windowOptionsFor('MLB').map((w) => w.label).join() === 'L5,L10,L20,All');
check('the widest window is "All", not "Season" — it is the last N games loaded',
  windowOptionsFor('NBA').every((w) => w.label !== 'Season'));
check('NFL loads fewer games than daily sports', logFetchLimit('NFL') < logFetchLimit('MLB'));

// ── Display lines ───────────────────────────────────────────────────────────
check('NFL subtitle carries the position', playerSubtitle('NFL', 'SF', nflRow) === 'SF · RB');
check('MLB subtitle says Pitcher/Batter', playerSubtitle('MLB', 'BAL', undefined, 'batter') === 'BAL · Batter');
check('basketball subtitle is team only (no position column in the log)',
  playerSubtitle('WNBA', 'LV', wnbaRow) === 'LV');
check('a player with no games loaded still renders a subtitle',
  playerSubtitle('NBA', null, undefined) === '—');

check('NFL game line shows opponent and week',
  gameContextLine('NFL', nflRow) === 'SF · vs SEA · Wk 4');
check('basketball game line shows minutes', gameContextLine('WNBA', wnbaRow) === 'LV · 31 min');
check('MLB pitcher game line shows IP',
  gameContextLine('MLB', { ...mlbPitch, team: 'BAL' } as PlayerLogEntry) === 'BAL · 5.2 IP');
check('MLB batter game line shows AB',
  gameContextLine('MLB', { team: 'BAL', at_bats: 4, player_type: 'batter' } as PlayerLogEntry) ===
    'BAL · 4 AB');

// ── Prop pick → the stat its player detail opens on ─────────────────────────
check('an MLB batter prop opens on its own stat',
  detailStatForPropModel('mlb_prop_batter_hits')?.label === 'Hits');
check('a WNBA prop opens on its own stat',
  detailStatForPropModel('wnba_prop_player_rebounds')?.label === 'Rebounds');
check('an NBA prop opens on its own stat',
  detailStatForPropModel('nba_prop_player_threes')?.label === '3PM');
check('the MLB outs prop swaps Innings for Outs',
  statForPropModel('mlb_prop_pitcher_outs')?.key === 'innings_pitched' &&
  detailStatForPropModel('mlb_prop_pitcher_outs')?.label === 'Outs');
check('a game market has no player stat', detailStatForPropModel('mlb_moneyline') === null);
check('the NFL market-relative rule has no single stat (one id spans eight markets)',
  detailStatForPropModel('nfl_prop_market') === null);

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
