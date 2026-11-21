/**
 * Verify the Performance tab's Insights maths (lib/performanceInsights.ts).
 * Run by tests/test_mobile_performance_insights.py with node's type stripping;
 * by hand: npx tsx scripts/verify_performance_insights.ts
 */
import {
  clvOf,
  curveOf,
  groupBy,
  periodInsights,
  periodWindows,
  priceBand,
  recordOf,
  streakOf,
  versusModels,
} from '../src/lib/performanceInsights';
import type { InsightBet, ModelDayRecord } from '../src/lib/performanceInsights';

let failures = 0;
function check(name: string, cond: boolean, detail?: unknown) {
  if (cond) console.log(`[PASS] ${name}`);
  else {
    failures++;
    console.log(`[FAIL] ${name}${detail !== undefined ? ` -> ${JSON.stringify(detail)}` : ''}`);
  }
}

let n = 0;
function bet(o: Partial<InsightBet>): InsightBet {
  n++;
  return {
    key: `k${n}`,
    date: '2026-11-21',
    stamp: '',
    title: `Bet ${n}`,
    status: 'won',
    profit: 100,
    risked: 110,
    odds: -110,
    sport: 'NCAAB',
    betType: 'Spread',
    book: 'DraftKings',
    modelId: 'm1',
    clvPct: null,
    source: 'tracked',
    ...o,
  };
}

// ── Windows: Monday–Sunday weeks, calendar months and years ──────────────────
{
  const sat = periodWindows('week', '2026-11-21');
  check('week of a Saturday starts Monday', sat.current.from === '2026-11-16', sat.current);
  check('week of a Saturday ends Sunday', sat.current.to === '2026-11-22', sat.current);
  check('last week is the Monday–Sunday before', sat.previous?.from === '2026-11-09' && sat.previous?.to === '2026-11-15', sat.previous);
  const sun = periodWindows('week', '2026-11-22');
  check('a Sunday is the end of its week, not the start of the next', sun.current.from === '2026-11-16', sun.current);
  const mon = periodWindows('week', '2026-11-23');
  check('a Monday starts a new week', mon.current.from === '2026-11-23' && mon.current.to === '2026-11-29', mon.current);
  const leap = periodWindows('month', '2028-02-10');
  check('a leap February runs to the 29th', leap.current.from === '2028-02-01' && leap.current.to === '2028-02-29', leap.current);
  const jan = periodWindows('month', '2026-01-05');
  check('January compares with last December', jan.previous?.from === '2025-12-01' && jan.previous?.to === '2025-12-31', jan.previous);
  const yr = periodWindows('year', '2026-11-21');
  check('a year is the calendar year', yr.current.from === '2026-01-01' && yr.current.to === '2026-12-31', yr.current);
  const day = periodWindows('day', '2026-03-01');
  check('yesterday crosses a month end', day.previous?.from === '2026-02-28', day.previous);
  check('all time has no window and no previous', periodWindows('all', '2026-11-21').previous === null);
}

// ── Records ─────────────────────────────────────────────────────────────────
{
  const r = recordOf([
    bet({ status: 'won', profit: 100, risked: 110 }),
    bet({ status: 'lost', profit: -175, risked: 175 }),
    bet({ status: 'push', profit: 0, risked: 0 }),
    bet({ status: 'open', profit: 0, risked: 0 }),
  ]);
  check('record counts W-L-P and open', r.wins === 1 && r.losses === 1 && r.pushes === 1 && r.open === 1 && r.bets === 4, r);
  check('net is won less lost', r.net === -75, r.net);
  check('ROI is net over risked on decided bets', Math.abs((r.roi ?? 0) - -75 / 285) < 1e-9, r.roi);
  check('nothing decided has no ROI', recordOf([bet({ status: 'open', profit: 0, risked: 0 })]).roi === null);
}

// ── Period: only the window, best and toughest, the delta base ──────────────
{
  const bets = [
    bet({ date: '2026-11-16', status: 'won', profit: 250, title: 'Big dog' }),
    bet({ date: '2026-11-18', status: 'lost', profit: -300, risked: 300, title: 'Heavy fav' }),
    bet({ date: '2026-11-21', status: 'lost', profit: -100, risked: 100 }),
    bet({ date: '2026-11-15', status: 'won', profit: 500, title: 'Last week' }),
  ];
  const w = periodInsights(bets, 'week', '2026-11-21');
  check('the week counts only its own bets', w.record.bets === 3, w.record);
  check('best bet is the biggest win in the window', w.best?.title === 'Big dog', w.best);
  check('toughest loss is the biggest loss in the window', w.worst?.title === 'Heavy fav', w.worst);
  check('last week is the comparison', w.previous?.net === 500, w.previous);
  check('the units line runs by day', JSON.stringify(w.curve) === JSON.stringify([
    { date: '2026-11-16', cum: 250 },
    { date: '2026-11-18', cum: -50 },
    { date: '2026-11-21', cum: -150 },
  ]), w.curve);
  const all = periodInsights(bets, 'all', '2026-11-21');
  check('all time has every bet and no comparison', all.record.bets === 4 && all.previous === null, all);
}

// ── Groups: every group shown, best first; a bet with no value sits out ─────
{
  const g = groupBy(
    [
      bet({ sport: 'NBA', status: 'won', profit: 100 }),
      bet({ sport: 'NBA', status: 'lost', profit: -110 }),
      bet({ sport: 'NHL', status: 'won', profit: 90 }),
      bet({ sport: null, status: 'won', profit: 500, source: 'logged' }),
      bet({ sport: 'MLB', status: 'open', profit: 0 }),
    ],
    (b) => b.sport,
  );
  check('a logged bet with no sport is not put in a bucket', g.every((x) => x.label !== 'null') && g.length === 2, g);
  check('an open bet is not in a breakdown', !g.some((x) => x.label === 'MLB'), g);
  check('groups run best net first', g[0].label === 'NHL' && g[1].label === 'NBA', g);
  check('a one-bet group is still shown', g.some((x) => x.label === 'NHL' && x.wins === 1), g);
}

// ── Price bands ─────────────────────────────────────────────────────────────
{
  check('−200 is a heavy favorite', priceBand(-200)?.startsWith('Heavy') === true);
  check('−199 is a favorite', priceBand(-199)?.startsWith('Favorite') === true);
  check('−101 is a favorite', priceBand(-101)?.startsWith('Favorite') === true);
  check('−100 is even', priceBand(-100)?.startsWith('Even') === true);
  check('+150 is an underdog', priceBand(150)?.startsWith('Even') === true);
  check('no price has no band', priceBand(null) === null);
}

// ── Closing line ────────────────────────────────────────────────────────────
{
  const c = clvOf([
    bet({ clvPct: 2.5 }),
    bet({ clvPct: -1.5 }),
    bet({ clvPct: 0.004 }),
    bet({ clvPct: 3.0 }),
    bet({ clvPct: null }),
    bet({ clvPct: 9, status: 'open', profit: 0 }),
  ]);
  check('CLV counts beats, trails and matches', c.beats === 2 && c.losses === 1 && c.pushes === 1, c);
  check('beat rate leaves the matched close out', Math.abs((c.beatRate ?? 0) - 2 / 3) < 1e-9, c.beatRate);
  check('average CLV keeps the matched close in', Math.abs((c.avgPct ?? 0) - (2.5 - 1.5 + 0.004 + 3) / 4) < 1e-9, c.avgPct);
}

// ── Form ────────────────────────────────────────────────────────────────────
{
  const s = streakOf([
    bet({ date: '2026-11-18', status: 'lost', profit: -110 }),
    bet({ date: '2026-11-19', status: 'won' }),
    bet({ date: '2026-11-20', status: 'push', profit: 0 }),
    bet({ date: '2026-11-21', status: 'won' }),
    bet({ date: '2026-11-22', status: 'open', profit: 0 }),
  ]);
  check('a push does not break a streak', s.kind === 'W' && s.length === 2, s);
  check('last 10 counts only wins and losses', s.last10Wins === 2 && s.last10Losses === 1, s);
  check('no decided bet has no streak', streakOf([bet({ status: 'open', profit: 0 })]).kind === null);
  const order = streakOf([
    bet({ date: '2026-11-21', status: 'lost', profit: -110 }),
    bet({ date: '2026-11-20', status: 'won' }),
  ]);
  check('the streak reads by game date, not list order', order.kind === 'L' && order.length === 1, order);
}

// ── You vs the models ───────────────────────────────────────────────────────
{
  const daily: ModelDayRecord[] = [
    { game_date: '2026-11-17', model_id: 'm1', wins: 3, losses: 1, pushes: 0, units: 1.8, risked: 4.4 },
    { game_date: '2026-11-18', model_id: 'm2', wins: 9, losses: 0, pushes: 0, units: 9, risked: 9.9 },
    { game_date: '2026-11-10', model_id: 'm1', wins: 5, losses: 0, pushes: 0, units: 5, risked: 5.5 },
  ];
  const bets = [
    bet({ date: '2026-11-17', modelId: 'm1', status: 'won', profit: 100, risked: 110 }),
    bet({ date: '2026-11-17', modelId: null, source: 'logged', status: 'lost', profit: -100, risked: 100 }),
  ];
  const v = versusModels(bets, daily, { from: '2026-11-16', to: '2026-11-22' }, 100);
  check('compares only the models the member tracked', JSON.stringify(v?.models) === '["m1"]', v);
  check('the models side is the same window only', v?.models_record.wins === 3 && v?.models_record.losses === 1, v);
  check('model units read at the 100-is-1u scale', v?.models_record.net === 180, v?.models_record);
  check('logged bets sit out of your side', v?.you.wins === 1 && v?.you.losses === 0, v?.you);
  check('the view returns numerics as strings: still summed', versusModels(
    bets,
    [{ game_date: '2026-11-17', model_id: 'm1', wins: '2', losses: '1', pushes: '0', units: '0.9', risked: '3.3' } as unknown as ModelDayRecord],
    { from: null, to: null },
  )?.models_record.wins === 2);
  check('nothing tracked has no comparison', versusModels([bets[1]], daily, { from: null, to: null }) === null);
}

if (failures > 0) {
  console.log(`\n${failures} failure(s)`);
  process.exit(1);
}
console.log('\nAll performance insights checks passed');
