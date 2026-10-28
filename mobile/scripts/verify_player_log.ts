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

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import {
  commitTypedLineOnce,
  measureStepperRow,
  parseTypedLine,
  stepLineFrom,
  stepperRowLayout,
  CHIP_ROW_LEAD,
  chipKey,
  chipRowScrollX,
  chipsForLoadedPlayer,
  chipsForPlayer,
  defaultChipForPlayer,
  detailStatForPick,
  detailStatForPropModel,
  filledChipCounts,
  gameContextLine,
  attachGameSides,
  opponentLabel,
  shortGameDate,
  chartGames,
  groupsOfChips,
  ipToOuts,
  lineStepFor,
  logFetchLimit,
  logStatValue,
  normalizeLogRow,
  openingChip,
  pagePlayerId,
  playerSubtitle,
  positionGroups,
  requestedChip,
  roundLineToStep,
  supportsPlayerDetail,
  windowOptionsFor,
  type PlayerLogEntry,
} from '../src/lib/playerLog';
import {
  isLogDerivedStat,
  propMarketForStat,
  propModelForStat,
  statForPropMarket,
  statForPropModel,
  statsForSport,
  type StatDef,
} from '../src/lib/statCatalog';
import { playerLineNote, playerPickRecord } from '../src/lib/playerDetail';
import { modelLong } from '../src/lib/modelMeta';
import type { SettledPick } from '../src/types';

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

// Blocks+Steals and Reb+Ast: the two combined markets the NBA projection model
// bets. No leaderboard view carries them, so the log row is the only place
// they are summed (statCatalog.LOG_DERIVED_STATS).
const nbaCombo = normalizeLogRow('NBA', { blocks: 2, steals: 1, rebounds: 9, assists: 4 });
check('NBA Blocks+Steals = blocks + steals', nbaCombo.blocks_steals === 3);
check('NBA Reb+Ast = rebounds + assists', nbaCombo.rebounds_assists === 13);
const nbaComboGap = normalizeLogRow('NBA', { blocks: null, steals: 2, rebounds: null, assists: null });
check('Blocks+Steals ignores a missing component rather than zeroing it', nbaComboGap.blocks_steals === 2);
check('an all-missing Reb+Ast is null, not 0', nbaComboGap.rebounds_assists === null);
check('Blocks+Steals reads through logStatValue on its chip',
  logStatValue(nbaCombo, statOf('NBA', 'Blocks+Steals')) === 3 &&
  logStatValue(nbaCombo, statOf('NBA', 'Reb+Ast')) === 13);
check('the NBA player page offers Blocks+Steals and Reb+Ast after the leaderboard chips',
  chipsForPlayer('NBA').slice(-2).map((c) => c.label).join() === 'Blocks+Steals,Reb+Ast');
check('the NBA leaderboard does not carry them (no view column, no server branch)',
  !statsForSport('NBA').some((c) => c.label === 'Blocks+Steals' || c.label === 'Reb+Ast'));
check('WNBA offers neither (no WNBA model bets them)',
  !chipsForPlayer('WNBA').some((c) => isLogDerivedStat(c)));
check('the NBA player page still opens on Points', defaultChipForPlayer('NBA')?.label === 'Points');
check('a pick handed over as blocks_steals opens on that chip',
  requestedChip(chipsForPlayer('NBA'), 'blocks_steals', 'NBA')?.label === 'Blocks+Steals');
check('the two are log-derived; a leaderboard stat is not',
  isLogDerivedStat(statOf('NBA', 'Reb+Ast')) && !isLogDerivedStat(statOf('NBA', 'PRA')));
check('their markets resolve with no per-stat model behind them',
  propMarketForStat(statOf('NBA', 'Blocks+Steals')) === 'player_blocks_steals' &&
  propMarketForStat(statOf('NBA', 'Reb+Ast')) === 'player_rebounds_assists' &&
  propModelForStat(statOf('NBA', 'Blocks+Steals')) === null);
// The head-to-head and same-position cards read server functions keyed on the
// stat, which have no branch for either key and return nothing: the card would
// say "No meetings with X" about a player who has met them. The hook skips
// both reads, and both cards, for a log-derived stat.
{
  const hook = readFileSync(join(import.meta.dirname, '..', 'src/hooks/usePlayerDetail.ts'), 'utf-8');
  check('the player page knows which stats the server cannot read',
    hook.includes('const serverStat = !isLogDerivedStat(stat);'));
  check('its head-to-head read and card are skipped for them',
    hook.includes('team && opponent && stat && serverStat') &&
    hook.includes('if (!opponent || threshold == null || !serverStat) return null;'));
  check('its same-position read and card are skipped for them',
    hook.includes('opponent && stat && serverStat && posGroup && pvoSeason != null') &&
    hook.includes('opponent && serverStat && posGroup && pvoSeason != null') &&
    hook.includes('serverStat && isRosterSport && opponent && stat && !posGroup'));
  // …and the page says so where the cards were, instead of dropping them
  // without a word (UX review, 2026-10-16).
  check('the hook says when those reads were skipped and there was an opponent to read',
    hook.includes('serverReadsSkipped: !serverStat && stat != null && opponent != null,'));
  const screenSrc = readFileSync(join(import.meta.dirname, '..', 'src/screens/PlayerStatsScreen.tsx'), 'utf-8');
  check('the player page puts one muted line in a card where the two cards were',
    /\{detail\.serverReadsSkipped && detail\.nextGame \? \(\s*<>\s*<SectionTitle title=\{`vs \$\{detail\.nextGame\.entry\.opponent\}`\} \/>\s*<View style=\{styles\.card\}>\s*<Text style=\{styles\.muted\}>\s*No head-to-head or same-position numbers for combined stats yet\. Pick a single stat to see them\.\s*<\/Text>\s*<\/View>\s*<\/>\s*\) : null\}/
      .test(screenSrc));
  check('that line sits after the same-position card, before the MLB context',
    screenSrc.indexOf('{detail.serverReadsSkipped && detail.nextGame ? (') > screenSrc.indexOf('<PositionVsOpponentPending') &&
    screenSrc.indexOf('{detail.serverReadsSkipped && detail.nextGame ? (') < screenSrc.indexOf('<StatcastCard'));
}

// ── The selected stat chip is scrolled into view ────────────────────────────
// NBA has 11 chips; a projection pick on Blocks+Steals or Reb+Ast opens on the
// 10th or 11th, past the right edge on every iPhone, so nothing visible said
// which stat the chart was (UX review, 2026-10-16). SportToggle's pattern:
// offsets from each chip's onLayout, scroll when the active chip lays out.
check('NBA Blocks+Steals and Reb+Ast are the 10th and 11th chips (why this matters)',
  chipsForPlayer('NBA').findIndex((c) => c.label === 'Blocks+Steals') === 9 &&
  chipsForPlayer('NBA').findIndex((c) => c.label === 'Reb+Ast') === 10 &&
  chipsForPlayer('NBA').length === 11);
check('the row scrolls to 40pt before the chip, as SportToggle does',
  CHIP_ROW_LEAD === 40 && chipRowScrollX(600) === 560);
check('a chip near the start scrolls the row back to 0, never negative',
  chipRowScrollX(30) === 0 && chipRowScrollX(0) === 0);
check('a chip that has not laid out yet does not scroll the row',
  chipRowScrollX(undefined) === null && chipRowScrollX(null) === null && chipRowScrollX(NaN) === null);
{
  const screenSrc = readFileSync(join(import.meta.dirname, '..', 'src/screens/PlayerStatsScreen.tsx'), 'utf-8');
  check('the stat chip row carries a ref',
    /<ScrollView\s+ref=\{statRowRef\}\s+horizontal/.test(screenSrc));
  check('each stat chip records its x under its chip key, and the active one scrolls when it lays out',
    /onLayout=\{\(e\) => \{\s*statChipX\.current\[chipKey\(c\)\] = e\.nativeEvent\.layout\.x;\s*if \(active\) scrollToActiveChip\(\);\s*\}\}/
      .test(screenSrc));
  check('the scroll is keyed on the resolved stat and goes through chipRowScrollX, not animated',
    screenSrc.includes('const activeChipKey = stat ? chipKey(stat) : null;') &&
    screenSrc.includes('chipRowScrollX(statChipX.current[activeChipKey])') &&
    screenSrc.includes('statRowRef.current?.scrollTo({ x, animated: false });') &&
    screenSrc.includes('}, [activeChipKey]);'));
  check('it scrolls on layout only, never on a tap (a tapped chip is already on screen)',
    screenSrc.split('scrollToActiveChip').length - 1 === 2);
}

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

// ── A multi-market rule's pick → the stat its row's prop_market is ──────────
// nba_prop_market, wnba_prop_market and nfl_prop_market are one model id across
// several markets, so the pick's own prop_market names the stat its chart and
// "View stats" link open on. The NBA markets resolve through the retired
// per-stat models' rows, which is why those rows stay in PROP_MARKET_BY_MODEL.
check('an NBA rule pick on points opens Points',
  detailStatForPick({ model_id: 'nba_prop_market', prop_market: 'player_points' })?.label === 'Points');
check('an NBA rule pick on PRA opens PRA',
  detailStatForPick({ model_id: 'nba_prop_market', prop_market: 'player_points_rebounds_assists' })?.label === 'PRA');
check('an NBA rule pick resolves on the NBA board, not the WNBA one',
  detailStatForPick({ model_id: 'nba_prop_market', prop_market: 'player_threes' })?.sport === 'NBA');
check('a WNBA rule pick on assists opens the WNBA Assists stat',
  (() => {
    const d = detailStatForPick({ model_id: 'wnba_prop_market', prop_market: 'player_assists' });
    return d?.label === 'Assists' && d.sport === 'WNBA';
  })());
check('an NFL rule pick on receptions opens Receptions',
  detailStatForPick({ model_id: 'nfl_prop_market', prop_market: 'player_receptions' })?.label === 'Receptions');
check('an NFL rule pick on receiving yards opens Rec Yards',
  detailStatForPick({ model_id: 'nfl_prop_market', prop_market: 'player_reception_yds' })?.label === 'Rec Yards');
check('a rule pick with no prop_market still has no single stat',
  detailStatForPick({ model_id: 'nba_prop_market', prop_market: null }) === null);
check('a market no stat is priced in has no stat',
  detailStatForPick({ model_id: 'nba_prop_market', prop_market: 'player_nonsense' }) === null);
check('a per-stat model ignores the row and keeps its own stat',
  detailStatForPick({ model_id: 'mlb_prop_batter_hits', prop_market: 'player_points' })?.label === 'Hits');
check('the outs swap holds on the pick path too',
  detailStatForPick({ model_id: 'mlb_prop_pitcher_outs' })?.label === 'Outs');
check('statForPropMarket needs the sport: no NCAAF stat is priced in an NBA market',
  statForPropMarket('NCAAF', 'player_points') === null);

// The NBA projection model: one id across six markets, like the rule. Two of
// them (Blocks+Steals, Reb+Ast) had no stat at all until the log-derived pair.
for (const [market, label] of [
  ['player_steals', 'Steals'],
  ['player_rebounds', 'Rebounds'],
  ['player_blocks_steals', 'Blocks+Steals'],
  ['player_blocks', 'Blocks'],
  ['player_rebounds_assists', 'Reb+Ast'],
  ['player_threes', '3PM'],
] as const) {
  const d = detailStatForPick({ model_id: 'nba_prop_projection', prop_market: market });
  check(`a projection pick on ${market} opens the NBA ${label} stat`, d?.label === label && d.sport === 'NBA');
}
check('statForPropMarket resolves the two combined NBA markets',
  String(statForPropMarket('NBA', 'player_blocks_steals')?.key) === 'blocks_steals' &&
  String(statForPropMarket('NBA', 'player_rebounds_assists')?.key) === 'rebounds_assists');
check('the combined markets are NBA-only: no WNBA stat is priced in them',
  statForPropMarket('WNBA', 'player_blocks_steals') === null &&
  statForPropMarket('WNBA', 'player_rebounds_assists') === null);
check('the projection model names no single stat of its own',
  detailStatForPropModel('nba_prop_projection') === null);

// ── "Our picks on <player>": a multi-market rule splits by market ───────────
{
  const settled = (over: Partial<SettledPick>): SettledPick => ({
    pick_id: 1, game_id: 'g', model_id: 'nba_prop_market', sport: 'NBA', game_date: '2026-10-20',
    game_time: null, pick_side: 'under', pick_label: 'A Player Under 24.5 Pts', model_probability: 0.55,
    edge: 0.05, dk_odds: -110, scored_line: 24.5, signal_type: 'BET', confidence_tier: null,
    condition_status: null, result: 'WIN', profit_flat: 90.91, player_id: '1', public_bet_pct: null,
    injury_flag: null, clv_pct: null, clv_method: null, decision_book: 'draftkings', decision_odds: -110,
    decision_edge: 0.05, is_live: false, prop_market: 'player_points',
    ...over,
  } as SettledPick);
  const rec = playerPickRecord([
    settled({ pick_id: 1, prop_market: 'player_points' }),
    settled({ pick_id: 2, prop_market: 'player_points', result: 'LOSS', profit_flat: -100 }),
    settled({ pick_id: 3, prop_market: 'player_rebounds', pick_label: 'A Player Under 8.5 Reb' }),
    settled({ pick_id: 4, model_id: 'mlb_prop_batter_runs', sport: 'MLB', prop_market: null, pick_side: 'over' }),
  ]);
  const labels = rec.lines.map((l) => l.label).sort().join(',');
  // The label is the stat. A second row with the same stat names its model
  // on the note (playerLineNote), not as "Assists (Props)".
  check('a multi-market rule gets one line per market, named for its stat',
    labels === 'Points,Rebounds,Runs');
  check('each line has its own key, so two lines of one model never share a React key',
    new Set(rec.lines.map((l) => l.key)).size === rec.lines.length);
  const pts = rec.lines.find((l) => l.label === 'Points');
  check('the points line carries both its bets', pts?.wins === 1 && pts.losses === 1 && pts.unders === 2);
  check('the total still counts every bet once', rec.settled === 4);

  // The same stat from a per-stat model and from the rule: two lines, two names.
  const both = playerPickRecord([
    settled({ pick_id: 5, model_id: 'wnba_prop_player_assists', sport: 'WNBA', prop_market: null }),
    settled({ pick_id: 6, model_id: 'wnba_prop_market', sport: 'WNBA', prop_market: 'player_assists', result: 'LOSS', profit_flat: -100 }),
  ]);
  const bothLabels = both.lines.map((l) => l.label).sort().join(',');
  // The prop-market rule has no parenthetical, so this pair shares the word
  // "Assists". The rows stay separate (different keys). "Assists (Props)" is
  // the reading the rename refused.
  check('a per-stat Assists line and the WNBA Props line both use the stat name',
    bothLabels === 'Assists,Assists');
  check('those two Assists lines are still two rows',
    new Set(both.lines.map((l) => l.key)).size === 2);
  check('a shared stat label names the model on the note, not in the label',
    both.lines.every((l) => !l.label.includes('Props') && playerLineNote(l, both.lines)?.startsWith(modelLong(l.modelId))) &&
      both.lines.map((l) => playerLineNote(l, both.lines)).sort().join(' | ') ===
        'WNBA Assists · 0 overs · 1 under | WNBA Props · 0 overs · 1 under');
  check('a stat that only one model priced does not prefix the model name',
    playerLineNote(pts!, rec.lines) === '0 overs · 2 unders');

  // The NBA projection model keeps "Projection" on its lines; the prop-market
  // rule does not. It bets overs as well as unders.
  const proj = playerPickRecord([
    settled({ pick_id: 7, model_id: 'nba_prop_projection', prop_market: 'player_steals', pick_side: 'over',
      pick_label: 'A Player Over 1.5 Steals' }),
    settled({ pick_id: 8, model_id: 'nba_prop_projection', prop_market: 'player_steals', pick_side: 'under',
      pick_label: 'A Player Under 1.5 Steals', result: 'LOSS', profit_flat: -100 }),
    settled({ pick_id: 9, model_id: 'nba_prop_projection', prop_market: 'player_blocks_steals', pick_side: 'over',
      pick_label: 'A Player Over 2.5 Blocks+Steals' }),
    settled({ pick_id: 10, model_id: 'nba_prop_projection', prop_market: 'player_rebounds_assists',
      pick_label: 'A Player Under 13.5 Reb+Ast' }),
    settled({ pick_id: 11, prop_market: 'player_rebounds', pick_label: 'A Player Under 8.5 Reb' }),
  ]);
  const projLabels = proj.lines.map((l) => l.label).sort().join(',');
  check('the projection model\'s lines are named "(Projection)", the rule\'s are the stat alone',
    projLabels === 'Blocks+Steals (Projection),Reb+Ast (Projection),Rebounds,Steals (Projection)');
  check('no projection line claims Pinnacle',
    proj.lines.filter((l) => l.modelId === 'nba_prop_projection').every((l) => !l.label.includes('Pinnacle')));
  const steals = proj.lines.find((l) => l.label === 'Steals (Projection)');
  check('a projection line counts its overs and its unders',
    steals?.overs === 1 && steals.unders === 1 && steals.wins === 1 && steals.losses === 1);
  check('the projection and the rule are separate lines even in one sport',
    new Set(proj.lines.map((l) => l.key)).size === proj.lines.length && proj.settled === 5);

  // The projection's labels use the rule's words for the shared markets:
  // rebounds is "Reb" and threes is "3PM" (models/nba_prop_projection.py
  // MARKET_LABEL). The line is named from the row's prop_market, not the
  // label's words, so both still land on their stat.
  const words = playerPickRecord([
    settled({ pick_id: 12, model_id: 'nba_prop_projection', prop_market: 'player_rebounds', pick_side: 'under',
      pick_label: 'Josh Hart Under 7.5 Reb' }),
    settled({ pick_id: 13, model_id: 'nba_prop_projection', prop_market: 'player_threes', pick_side: 'over',
      pick_label: 'Karl-Anthony Towns Over 1.5 3PM' }),
  ]);
  check('a projection "Reb" pick is a Rebounds line, a "3PM" pick a 3PM line',
    words.lines.map((l) => l.label).sort().join(',') === '3PM (Projection),Rebounds (Projection)');
  check('…on its own side',
    words.lines.find((l) => l.label === '3PM (Projection)')?.overs === 1 &&
    words.lines.find((l) => l.label === 'Rebounds (Projection)')?.unders === 1);
}

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

// ── The ± stepper and the typed line (Matt, 2026-10-08) ─────────────────────
// A 50.5 book line opens the ruler on 51+; stepping by 5 from there walked
// 46/51/56 and 50 was unreachable. Off-grid lines land on the grid first.
check('51 minus one step of 5 lands on 50', stepLineFrom(51, -1, 5) === 50);
check('51 plus one step of 5 lands on 55', stepLineFrom(51, 1, 5) === 55);
check('on the grid, steps move by the step', stepLineFrom(50, 1, 5) === 55 && stepLineFrom(50, -1, 5) === 45);
check('two steps from off-grid: 51 -> 60 / 45', stepLineFrom(51, 2, 5) === 60 && stepLineFrom(51, -2, 5) === 45);
check('step of 1 is unchanged', stepLineFrom(3, 1, 1) === 4 && stepLineFrom(3, -1, 1) === 2);
check('never below 0', stepLineFrom(3, -1, 5) === 0 && stepLineFrom(0, -1, 5) === 0);
check('step of 25 from 237 lands on 225 / 250', stepLineFrom(237, -1, 25) === 225 && stepLineFrom(237, 1, 25) === 250);
check('a typed line above the ceiling steps down once, not to the ceiling',
  stepLineFrom(300, -1, 5, 85) === 295);
check('stepping up stops at the ceiling', stepLineFrom(80, 2, 5, 85) === 85);
check('stepping up from above the ceiling does not drop to it', stepLineFrom(300, 1, 5, 85) === 300);
check('typed "50" in At Least is 50+', parseTypedLine('50') === 50);
check('typed "50+" in At Least is 50+', parseTypedLine('50+') === 50);
check('typed "50.5" in At Least clears the half-line: 51+', parseTypedLine('50.5') === 51);
check('typed "50.5" in Over is that line: 51+', parseTypedLine('50.5', 'over') === 51);
check('typed "50" in Under is Under 50.5: threshold 51', parseTypedLine('50', 'under') === 51);
check('junk is refused', parseTypedLine('') === null && parseTypedLine('abc') === null && parseTypedLine('-5') === null);

// Android delivers Done as onSubmitEditing and then blur as onEndEditing, in
// one turn, with the same draft. The first call commits; the second finds
// the latch and applies nothing. iOS commits from blur only, once.
let taken = false;
let typedLine: number | null = 51;
const firstCommit = commitTypedLineOnce('50', taken, 'atLeast', typedLine);
taken = firstCommit.taken;
if (firstCommit.line != null) typedLine = firstCommit.line;
const secondCommit = commitTypedLineOnce('50', taken, 'atLeast', typedLine);
check('a typed line commits once when Done and blur both fire',
  firstCommit.line === 50 && firstCommit.taken === true
  && secondCommit.line === null && secondCommit.taken === true
  && typedLine === 50);
check('a latched commit does not apply a second draft',
  commitTypedLineOnce('40', true, 'atLeast', 50).line === null);
check('an unopened field does not latch, so a later edit can commit',
  commitTypedLineOnce(null, false, 'atLeast', 51).taken === false
  && commitTypedLineOnce('40', false, 'atLeast', 51).line === 40);

// The stepper row at Dynamic Type. Measured (Inter, stand-in for SF): at
// fontScale 1, "At Least" + a 50.5 line + three-digit averages is 309pt of a
// 375pt card's 319 and fits. At fontScale 2 the one line is 472pt, so the +
// button leaves the screen; on its own line the stepper is 287pt and fits,
// including Accessibility Large (2.143, RCTAccessibilityManager). From
// Accessibility Extra Large (2.643) that line overflows too, and the mode
// control moves above − / field / +. At the largest size (3.571) that group
// is 221pt. The − / + stay 30pt with 8pt slop (46 ≥ 44). The field and the
// mode control stay minHeight 44. Nothing overlaps: the 8pt gap equals the
// slop, so a button's slop ends where the field begins.
const at1 = measureStepperRow(1);
const at2 = measureStepperRow(2);
const axLarge = measureStepperRow(2.143);
const axXL = measureStepperRow(2.643);
const axXXXL = measureStepperRow(3.571);
check('at default type the stepper row fits on one line',
  at1.layout === 'inline' && at1.single <= at1.inner && at1.single > 300 && stepperRowLayout(1) === 'inline');
check('at fontScale 2 the one-line row overflows and the stepper line still fits',
  at2.layout === 'stacked' && at2.single > at2.inner && at2.single > 450
  && at2.stacked <= at2.inner && at2.stacked > 250 && stepperRowLayout(2) === 'stacked');
check('Accessibility Large (2.143) still fits on the stepper line',
  axLarge.layout === 'stacked' && axLarge.stacked <= axLarge.inner);
check('from Accessibility Extra Large (2.643) the mode control has to leave that line',
  axXL.layout === 'split' && axXL.stacked > axXL.inner && axXL.controls <= axXL.inner && axXL.mode <= axXL.inner);
check('at the largest Dynamic Type (3.571) − / field / + and the mode label each fit',
  axXXXL.layout === 'split' && axXXXL.controls <= axXXXL.inner && axXXXL.mode <= axXXXL.inner
  && stepperRowLayout(3.571) === 'split');
check('the − / + stay a 44pt target (30 + 8 + 8) and do not overlap the field',
  30 + 8 + 8 >= 44);

const playerScreen = readFileSync(join(import.meta.dirname, '..', 'src/screens/PlayerStatsScreen.tsx'), 'utf-8');
check('Done and blur share one commit, and the field resets the latch on focus',
  /returnKeyType="done"/.test(playerScreen)
  && /onSubmitEditing=\{commitLineDraft\}/.test(playerScreen)
  && /onEndEditing=\{commitLineDraft\}/.test(playerScreen)
  && /commitTypedLineOnce\(lineDraft, lineCommitTaken\.current, mode, line\)/.test(playerScreen)
  && /lineCommitTaken\.current = false/.test(playerScreen)
  && /lineCommitTaken\.current = result\.taken/.test(playerScreen));
check('the card places the stepper from stepperRowLayout',
  /const \{ fontScale \} = useWindowDimensions\(\)/.test(playerScreen)
  && /const stepperLayout = stepperRowLayout\(fontScale\)/.test(playerScreen)
  && /stepperLayout === 'inline' \? styles\.stepper : styles\.stepperStacked/.test(playerScreen)
  && /stepperLayout !== 'inline' && styles\.statsRowStacked/.test(playerScreen)
  && /stepperLayout === 'split' && styles\.stepperSplit/.test(playerScreen)
  && /stepperLayout === 'split' && styles\.modeBtnSplit/.test(playerScreen)
  && /stepperLayout === 'split' && styles\.stepperControlsSplit/.test(playerScreen));
const stackedBlock = /stepperStacked: \{([\s\S]*?)\n  \},/.exec(playerScreen)?.[1] ?? '';
check('the stacked stepper takes the full line and does not keep flex: 1',
  /width: '100%'/.test(stackedBlock) && !/flex:\s*1/.test(stackedBlock));
check('the split puts the mode control and the ± line on their own full lines',
  /modeBtnSplit: \{[\s\S]*?width: '100%'/.test(playerScreen)
  && /stepperControlsSplit: \{[\s\S]*?width: '100%'/.test(playerScreen)
  && /stepperSplit: \{[\s\S]*?flexWrap: 'wrap'/.test(playerScreen));
check('the mode control and the field stay 44pt, and the − / + keep their slop',
  /modeBtn: \{[\s\S]*?minHeight: 44/.test(playerScreen)
  && /stepInput: \{[\s\S]*?minHeight: 44/.test(playerScreen)
  && /stepBtn: \{[\s\S]*?width: 30,\n\s*height: 30/.test(playerScreen)
  && (playerScreen.match(/hitSlop=\{8\}/g) ?? []).length >= 3);


// ── A page opened by name keys its reads on the log's player id ─────────────
// nfl_prop_market writes no player_id, so its pick opens the player page by
// name. The head-to-head card matched r.player_id === null and always said
// "no meetings"; today's-pick lookups found nothing (designer review,
// 2026-10-16). The loaded log carries the id.
check('a name-only page takes the id from the loaded log',
  pagePlayerId('', [{ player_id: '00-0036322' }]) === '00-0036322');
check('a route id wins over the log', pagePlayerId('660271', [{ player_id: '999' }]) === '660271');
check('nothing loaded and no route id is null, never an empty string', pagePlayerId('', []) === null);
check('the screen resolves the page id from the route id and the log',
  /const pageId = pagePlayerId\(playerId, games\);/.test(playerScreen));
check('usePlayerDetail keys on the resolved id',
  /usePlayerDetail\(\{[\s\S]*?playerId: pageId,/.test(playerScreen));
check('the betslip pick lookup keys on the resolved id',
  /slipPickFor\(\{ player_id: pageId \}/.test(playerScreen));
check('the pick-threshold lookup keys on the resolved id',
  /buildPickIndex\(todayPicks, propModelForStat\(stat\)\)\.get\(pageId\)/.test(playerScreen));
// The same-position card leaves the player himself out of "others at his
// position"; keyed on the empty route id, a name-only page counted his own
// games among them (NFL is the card's sport, and its rule picks have no id).
check('the same-position card excludes the player by the resolved id',
  /<PositionVsOpponentCard[\s\S]*?playerId=\{pageId\}/.test(playerScreen));

// ── Chart labels: opponent and date on every bar (Matt, 2026-10-28) ────────
{
  const base = { player_id: 'p', player_name: 'K', season: 2026 } as const;
  const log = [
    { ...base, team: 'NYK', game_id: 'g3', game_date: '2026-10-26', points: 27 },
    { ...base, team: 'NYK', game_id: 'g2', game_date: '2026-10-24', points: null },
    { ...base, team: 'NYK', game_id: 'g1', game_date: '2026-10-22', points: 22 },
    { ...base, team: 'NYK', game_id: 'gX', game_date: '2026-10-20', points: 19 },
  ];
  const sided = attachGameSides(log as never, [
    { game_id: 'g3', home_team: 'CHI', away_team: 'NYK' },
    { game_id: 'g2', home_team: 'NYK', away_team: 'BOS' },
    { game_id: 'g1', home_team: 'NYK', away_team: 'ORL' },
  ]);
  check('an away game reads @CHI, a home game vs ORL',
    opponentLabel(sided[0]!) === '@CHI' && opponentLabel(sided[2]!) === 'vs ORL'
      && opponentLabel(sided[2]!, true) === 'vs ORL');
  check('a game missing from games keeps no opponent and no venue',
    opponentLabel(sided[3]!) === null && sided[3]!.venue == null);
  check('a stored football opponent is kept, venue still added',
    attachGameSides([{ ...base, team: 'Ohio State', opponent: 'Michigan', game_id: 'f', game_date: '2026-11-28' }] as never,
      [{ game_id: 'f', home_team: 'Michigan', away_team: 'Ohio State' }])[0]!.venue === 'away');
  const abbr = new Map([['Michigan', 'MICH'], ['Michigan State', 'MSU']]);
  check('a school name uses its own abbreviation, so two Michigans stay two',
    opponentLabel({ opponent: 'Michigan State', venue: 'away' }, true, abbr) === '@MSU'
      && opponentLabel({ opponent: 'Michigan', venue: 'home' }, true, abbr) === 'vs MICH'
      && opponentLabel({ opponent: 'Michigan State', venue: 'away' }) === '@Michigan State');
  check('a school with no abbreviation falls back to four letters under a bar',
    opponentLabel({ opponent: 'Ohio State', venue: 'away' }, true) === '@OHIO');
  check('dates print as 10/26, junk as empty',
    shortGameDate('2026-10-26') === '10/26' && shortGameDate('2026-01-05') === '1/5' && shortGameDate(null) === '');
  // logValues DROPS a game with no value. The labels must drop the same game,
  // or every bar after the gap carries the previous game's opponent.
  const cg = chartGames(sided, (r) => (r.points == null ? null : Number(r.points)));
  check('chart labels skip the same games the values skip, in the same order',
    cg.length === 3 && cg[0]!.value === 27 && cg[0]!.opp === '@CHI' && cg[0]!.date === '10/26'
      && cg[1]!.value === 22 && cg[1]!.opp === 'vs ORL' && cg[2]!.value === 19 && cg[2]!.opp === null);
  check('the Recent games row names the opponent in basketball too',
    gameContextLine('NBA', { ...sided[0]!, minutes: 34 } as never) === 'NYK · @CHI · 34 min');
  check('the player chart is handed the labelled games',
    /<HitRateChart[\s\S]*?games=\{windowedGames\}/.test(playerScreen));
}

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
