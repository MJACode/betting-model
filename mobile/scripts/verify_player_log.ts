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
  chipKey,
  chipsForLoadedPlayer,
  chipsForPlayer,
  defaultChipForPlayer,
  detailStatForPropModel,
  filledChipCounts,
  gameContextLine,
  groupsOfChips,
  ipToOuts,
  lineStepFor,
  logFetchLimit,
  logStatValue,
  normalizeLogRow,
  openingChip,
  playerSubtitle,
  positionGroups,
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

const statOf = (sport: 'MLB' | 'WNBA' | 'NBA' | 'NFL' | 'NCAAF', label: string, playerType?: 'batter' | 'pitcher'): StatDef =>
  chipsForPlayer(sport, playerType).find((s) => s.label === label)!;

// ── Which sports get a detail screen ────────────────────────────────────────
for (const s of ['MLB', 'WNBA', 'NBA', 'NFL', 'NCAAF'] as const) {
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

// NCAAF reads the same football shape off a different table — the derived
// rush+rec TDs and the NUMERIC-string coercion must behave identically, or the
// college board would quietly disagree with the NFL one on a shared stat.
const ncaafRow = normalizeLogRow('NCAAF', {
  player_id: '3', player_name: 'A Runner', team: 'Ohio State', opponent: 'Michigan',
  week: 13, game_id: 'g', game_date: '2026-11-28', season: 2026,
  rushing_yards: 112, rushing_tds: 2, receiving_tds: null, receptions: 1,
  def_sacks: '1.5',
});
check('NCAAF rush+rec TDs ignore a missing receiving component', ncaafRow.rush_rec_tds === 2);
check('NCAAF half-sacks arriving as a NUMERIC string read as a number',
  logStatValue(ncaafRow, statOf('NCAAF', 'Sacks')) === 1.5);

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
check('NFL chips span four groups', groupsOfChips(chipsForPlayer('NFL')).join() === 'Passing,Rushing,Receiving,Defense');
check('NCAAF opens on Pass Yards', defaultChipForPlayer('NCAAF')?.label === 'Pass Yards');
check('NCAAF chips span the same four groups',
  groupsOfChips(chipsForPlayer('NCAAF')).join() === 'Passing,Rushing,Receiving,Defense');
check('NCAAF offers no Targets chip (CFBD box scores do not report them)',
  !chipsForPlayer('NCAAF').some((c) => c.label === 'Targets'));
check('WNBA has a single group, so no group tab row', groupsOfChips(chipsForPlayer('WNBA')).length === 1);
check('MLB has a single group per player type', groupsOfChips(chipsForPlayer('MLB', 'batter')).length === 1);
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
check('NCAAF is weekly too, so it loads the same as the NFL',
  logFetchLimit('NCAAF') === logFetchLimit('NFL'));
check('NCAAF windows start at L3 (a season is 12-15 games)',
  windowOptionsFor('NCAAF').map((w) => w.label).join() === 'L3,L5,L10,All');

// ── Display lines ───────────────────────────────────────────────────────────
check('NFL subtitle carries the position', playerSubtitle('NFL', 'SF', nflRow) === 'SF · RB');
check('MLB subtitle says Pitcher/Batter', playerSubtitle('MLB', 'BAL', undefined, 'batter') === 'BAL · Batter');
check('basketball subtitle is team only (no position column in the log)',
  playerSubtitle('WNBA', 'LV', wnbaRow) === 'LV');
check('a player with no games loaded still renders a subtitle',
  playerSubtitle('NBA', null, undefined) === '—');

check('NFL game line shows opponent and week',
  gameContextLine('NFL', nflRow) === 'SF · vs SEA · Wk 4');
check('NCAAF game line shows opponent and week',
  gameContextLine('NCAAF', ncaafRow) === 'Ohio State · vs Michigan · Wk 13');
check('NCAAF subtitle is team only (CFBD names participants, not positions)',
  playerSubtitle('NCAAF', 'Ohio State', ncaafRow) === 'Ohio State');
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

// ── The tabs a player actually fills ────────────────────────────────────────
// Matt, 2026-09-19: a quarterback was offered a Defense tab of ten zeroes.
// nfl_player_game_log stores 0, never NULL, off-position, so only the numbers
// can say what a player does — and for NCAAF, where CFBD names no position,
// they are the ONLY evidence there is.
const nflGame = (over: Partial<PlayerLogEntry>): PlayerLogEntry => ({
  player_id: 'p', player_name: 'A Player', team: 'BAL', game_id: 'g', game_date: '2026-09-14',
  season: 2026, pos: 'QB', passing_yards: 0, passing_tds: 0, completions: 0, attempts: 0,
  interceptions: 0, rushing_yards: 0, rushing_tds: 0, carries: 0, receptions: 0, targets: 0,
  receiving_yards: 0, receiving_tds: 0, def_sacks: 0, def_interceptions: 0,
  ...over,
} as PlayerLogEntry);

const nflChips = chipsForPlayer('NFL');
const qbLog = [
  normalizeLogRow('NFL', nflGame({ passing_yards: 237, attempts: 30, completions: 21, passing_tds: 2, rushing_yards: 45, carries: 8 })),
  normalizeLogRow('NFL', nflGame({ passing_yards: 180, attempts: 26, completions: 15, rushing_yards: 12, carries: 4 })),
];
const qbGroups = groupsOfChips(chipsForLoadedPlayer(nflChips, qbLog));
check('a QB is offered no Defense tab (the reported bug)', !qbGroups.includes('Defense'));
check('a QB keeps Passing and Rushing', qbGroups.includes('Passing') && qbGroups.includes('Rushing'));
check('a QB with no catch is offered no Receiving tab', !qbGroups.includes('Receiving'));

const lbLog = [
  normalizeLogRow('NFL', nflGame({ pos: 'LB', def_sacks: 1.5 })),
  normalizeLogRow('NFL', nflGame({ pos: 'LB', def_interceptions: 1 })),
];
const lbGroups = groupsOfChips(chipsForLoadedPlayer(nflChips, lbLog));
check('a linebacker is offered Defense alone, not three empty offensive tabs',
  lbGroups.join() === 'Defense');

const teLog = [normalizeLogRow('NFL', nflGame({ pos: 'TE', receptions: 5, receiving_yards: 61, receiving_tds: 1, targets: 7 }))];
const teChips = chipsForLoadedPlayer(nflChips, teLog);
const teFilled = filledChipCounts(teChips, teLog);
check('a receiving TD holds the Rushing tab (Anytime TD lives there)',
  groupsOfChips(teChips).includes('Rushing'));
check('...but that tab opens on the TD, not on Rush Yards 0.0',
  openingChip(teChips, teFilled, 'Rushing')?.label === 'Anytime TD');
check('a tight end opens on the stat he fills most, not on catalog order',
  openingChip(teChips, teFilled)?.label === 'Receptions' ||
  openingChip(teChips, teFilled)?.group === 'Receiving');
check('a chip he has never filled is still offered inside a surviving tab',
  teChips.some((c) => c.label === 'Rush Yards') && !teFilled.has(chipKey(teChips.find((c) => c.label === 'Rush Yards')!)));

// A player with nothing on file at all: the position decides, and it never
// says Defense for an offensive position (19 of 138 DEs are the mirror case).
const benchedQb = [normalizeLogRow('NFL', nflGame({}))];
check('a QB with a blank game sheet still gets no Defense tab',
  !groupsOfChips(chipsForLoadedPlayer(nflChips, benchedQb)).includes('Defense'));
check('a DE with no sack and no interception gets Defense alone',
  groupsOfChips(chipsForLoadedPlayer(nflChips, [normalizeLogRow('NFL', nflGame({ pos: 'DE' }))])).join() === 'Defense');
check('an unclassified position hides nothing on its own', positionGroups('XYZ').length === 0);
check('every offensive position maps away from Defense',
  ['QB', 'RB', 'WR', 'TE', 'FB', 'K', 'P', 'LS', 'C', 'G', 'OT', 'OL']
    .every((p) => !positionGroups(p).includes('Defense')));
check('every defensive position maps to Defense alone',
  ['CB', 'DB', 'DE', 'DL', 'DT', 'FS', 'ILB', 'LB', 'MLB', 'NT', 'OLB', 'S', 'SAF']
    .every((p) => positionGroups(p).join() === 'Defense'));

// NCAAF: no position, and CFBD leaves a category NULL for a player who took
// no part in it — so the nulls alone must carry the filtering.
const ncaafChips = chipsForPlayer('NCAAF');
const ncaafDefender = [normalizeLogRow('NCAAF', {
  player_id: 'c', player_name: 'A Player', team: 'Georgia', game_id: 'g', game_date: '2026-09-13',
  season: 2026, def_tackles: 7, def_solo: 4, def_sacks: 1, def_tfl: 2, def_pd: 1, def_interceptions: 0,
} as unknown as Record<string, unknown>)];
check('an NCAAF defender is offered Defense alone, with no position to go on',
  groupsOfChips(chipsForLoadedPlayer(ncaafChips, ncaafDefender)).join() === 'Defense');

check('no games loaded yet leaves every chip in place',
  chipsForLoadedPlayer(nflChips, []).length === nflChips.length);
check('a log of nothing but zeroes and no position keeps every chip',
  chipsForLoadedPlayer(ncaafChips, [normalizeLogRow('NCAAF', {
    player_id: 'c', player_name: 'A Player', team: 'Georgia', game_id: 'g', game_date: '2026-09-13', season: 2026,
  } as unknown as Record<string, unknown>)]).length === ncaafChips.length);


console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
