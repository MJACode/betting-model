/**
 * Yesterday's units equal Discord's posted stake on one fixture day.
 *
 * The expected file is written by tests/test_yesterday_discord_units.py
 * from tracking.discord_notifier._tally and tracking.published_units
 * (the SQL functions' Python twins). This script runs computeDailyResults
 * on the same picks, including the void and the unpublished win, and
 * requires the same wins, losses, units and risked.
 *
 *   node --experimental-strip-types verify_yesterday_units.ts fixture.json expected.json
 */
import { readFileSync } from 'node:fs';

import { computeDailyResults, dayRoiText, dayUnitsText, dayWinRateText } from '../src/lib/dailyResults';
import type { Pick, PickResult } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (!cond) failures++;
  console.log(`[${status}] ${name}${detail ? ` — ${detail}` : ''}`);
}
function near(a: number, b: number, eps = 1e-9): boolean {
  return Math.abs(a - b) <= eps;
}

interface FixturePick {
  id: string;
  sport: string;
  model_id: string;
  result: string;
  price: number | null;
  counts: boolean;
  condition_status?: string | null;
  discordPublish?: 'published' | 'unpublished' | 'unknown';
}

interface Bucket {
  wins: number;
  losses: number;
  pushes: number;
  units: number;
  risked: number;
  models?: Record<string, Bucket>;
}

const MINUS = '\u2212';

function appUnits(units: number): string {
  return dayUnitsText(units).replaceAll(MINUS, '-');
}

const fixturePath = process.argv[2];
const expectedPath = process.argv[3];
if (!fixturePath || !expectedPath) {
  console.error('usage: verify_yesterday_units.ts <fixture.json> <expected.json>');
  process.exit(2);
}

const fixture = JSON.parse(readFileSync(fixturePath, 'utf8')) as {
  date: string;
  picks: FixturePick[];
};
const expected = JSON.parse(readFileSync(expectedPath, 'utf8')) as {
  overall: Bucket;
  sports: Record<string, Bucket>;
  lines: { scope: string; units: string; roi: string | null }[];
};

function asResult(value: string): PickResult {
  if (value === 'WIN' || value === 'LOSS' || value === 'PUSH' || value === 'NO_ACTION') return value;
  return null;
}

let nextId = 1;
function mk(row: FixturePick): Pick {
  return {
    pick_id: nextId++,
    game_id: `g${row.id}`,
    model_id: row.model_id,
    sport: row.sport,
    game_date: fixture.date,
    game_time: `${fixture.date}T23:00:00Z`,
    pick_side: 'home',
    pick_label: row.id,
    model_probability: 0.75,
    dk_implied_prob: 0.5,
    edge: 0.15,
    dk_odds: row.price,
    scored_line: null,
    kelly_fraction: 0.5,
    recommended_bet: 30,
    bankroll_at_pick: 1000,
    injury_flag: null,
    injury_detail: null,
    signal_type: 'BET',
    confidence_tier: 'HIGH',
    condition_status: row.condition_status ?? null,
    result: asResult(row.result),
    profit_flat: row.result === 'WIN' ? 9999 : row.result === 'LOSS' ? -9999 : 0,
    profit_kelly: 0,
    settled_at: null,
    created_at: `${fixture.date}T12:00:00Z`,
    player_id: null,
    pitcher_throw_hand: null,
    public_bet_pct: null,
    public_money_pct: null,
    closing_dk_odds: null,
    closing_line: null,
    clv_pct: null,
    line_clv_pts: null,
    clv_beat_close: null,
    clv_captured_at: null,
    clv_method: null,
    clv_close_book: null,
    clv_bet_book: null,
    is_live: false,
    inning_at_pick: null,
    score_diff_at_pick: null,
    dk_bet_link: null,
    best_book: null,
    best_odds: null,
    best_implied_prob: null,
    best_edge: null,
    best_bet_link: null,
    line_book: null,
    decision_book: null,
    decision_odds: null,
    decision_implied_prob: null,
    decision_edge: null,
    discordPublish: row.discordPublish,
  };
}

const day = computeDailyResults(fixture.date, fixture.picks.map(mk));

function same(name: string, got: Bucket, want: Bucket) {
  check(`${name} record`,
    got.wins === want.wins && got.losses === want.losses && got.pushes === want.pushes,
    `got ${got.wins}-${got.losses}-${got.pushes}`);
  check(`${name} units`, near(got.units, want.units), `got ${got.units} want ${want.units}`);
  check(`${name} risked`, near(got.risked, want.risked), `got ${got.risked} want ${want.risked}`);
}

same('overall', day.overall, expected.overall);
check('void and unpublished are not in the graded list',
  day.gradedPicks.length === expected.overall.wins + expected.overall.losses + expected.overall.pushes
    && !day.gradedPicks.some((p) => p.pick_label === 'void' || p.pick_label === 'unpublished'),
  day.gradedPicks.map((p) => p.pick_label).join(','));
check('the unpublished win is counted as unpublished', day.unpublished === 1, `got ${day.unpublished}`);

for (const [sport, want] of Object.entries(expected.sports)) {
  const got = day.sports.find((s) => s.sport === sport);
  if (!got) {
    check(`${sport} section`, false, 'missing');
    continue;
  }
  same(sport, got.total, want);
  for (const [modelId, modelWant] of Object.entries(want.models ?? {})) {
    const model = got.models.find((m) => m.modelId === modelId);
    if (!model) {
      check(`${sport} ${modelId}`, false, 'missing');
      continue;
    }
    same(`${sport} ${modelId}`, model, modelWant);
  }
}

for (const line of expected.lines) {
  const stats = line.scope === 'overall'
    ? day.overall
    : day.sports.find((s) => s.sport === line.scope)?.total;
  if (!stats) {
    check(`${line.scope} line`, false, 'missing');
    continue;
  }
  const units = appUnits(stats.units);
  const roi = stats.risked > 0 ? dayRoiText(stats.risked, stats.roiFlat).replaceAll(MINUS, '-') : null;
  // Discord's :+ format keeps a plus on a value that rounds to zero.
  // formatSigned prints that zero unsigned, the same rule as the Record hero.
  const unitsOk = units === line.units || (line.units === '+0.00u' && units === '0.00u');
  const roiOk = roi === line.roi || (line.roi === '+0.0%' && roi === '0.0%');
  check(`${line.scope} units text`, unitsOk, `got ${units} want ${line.units}`);
  check(`${line.scope} roi text`, roiOk, `got ${roi} want ${line.roi}`);
}

// The 2026-10-17 book, as stored on results_snapshots (daily) and the
// posted-stake view. Two decimals, the same rounding Discord prints.
check('2026-10-17 overall is +7.31u', dayUnitsText(7.3111) === '+7.31u', dayUnitsText(7.3111));
check('2026-10-17 NCAAF is +6.45u', dayUnitsText(6.446666666666667) === '+6.45u', dayUnitsText(6.446666666666667));
check('2026-10-17 NHL is −0.14u', dayUnitsText(-0.13555555555555555) === `${MINUS}0.14u`, dayUnitsText(-0.13555555555555555));
check('2026-10-17 WNBA is +1.00u', dayUnitsText(1) === '+1.00u', dayUnitsText(1));
check('2026-10-17 overall ROI is +32.5%',
  dayRoiText(22.481, 7.3111 / 22.481) === '+32.5%', dayRoiText(22.481, 7.3111 / 22.481));
check('2026-10-17 NCAAF ROI is +48.8%',
  dayRoiText(13.205474432595023, 6.446666666666667 / 13.205474432595023) === '+48.8%',
  dayRoiText(13.205474432595023, 6.446666666666667 / 13.205474432595023));
check('2026-10-17 NHL ROI is −1.7%',
  dayRoiText(7.975569050832209, -0.13555555555555555 / 7.975569050832209) === `${MINUS}1.7%`,
  dayRoiText(7.975569050832209, -0.13555555555555555 / 7.975569050832209));
check('2026-10-17 WNBA ROI is +76.9%',
  dayRoiText(1.3, 1 / 1.3) === '+76.9%', dayRoiText(1.3, 1 / 1.3));
check('a push-only book prints 0.00u and no ROI',
  dayUnitsText(0) === '0.00u' && dayRoiText(0, 0) === '—',
  `${dayUnitsText(0)} ${dayRoiText(0, 0)}`);
check('a push-only book has no win rate', dayWinRateText(0, 0, 0) === '—', dayWinRateText(0, 0, 0));
check('an all-loss book prints 0.0%', dayWinRateText(0, 2, 0) === '0.0%', dayWinRateText(0, 2, 0));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
