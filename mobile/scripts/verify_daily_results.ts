/**
 * Standalone verification for the daily-recap aggregator (src/lib/dailyResults.ts).
 * No JS test runner is configured for the app, so — like the other verify_*.ts
 * scripts — we assert the pure function here and run with tsx:
 *
 *   npx tsx scripts/verify_daily_results.ts
 *
 * Pins: overall + per-sport + per-model records and ROI are correct; that
 * off-date, NO_ACTION, sub-threshold, live, AVOID, and paused-model picks are
 * all excluded (they would otherwise inflate the counts); and that record-only
 * models (batter HR) are listed but never counted toward any total.
 */
import { ALL_SPORTS, computeDailyResults, scopeDailyResults } from '../src/lib/dailyResults';
import { isModelPaused } from '../src/lib/thresholds';
import type { GameRow, Pick } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (!cond) failures++;
  console.log(`[${status}] ${name}${detail ? ` — ${detail}` : ''}`);
}
function near(a: number, b: number, eps = 0.01): boolean {
  return Math.abs(a - b) <= eps;
}

const DATE = '2026-06-29';
const WIN_PROFIT = 90.91; // ~ -110 decimal payout on a $100 flat stake

let nextId = 1;
function mk(over: Partial<Pick>): Pick {
  return {
    pick_id: nextId++,
    game_id: `g${nextId}`,
    model_id: 'mlb_moneyline',
    sport: 'MLB',
    game_date: DATE,
    game_time: `${DATE}T23:10:00+00:00`,
    pick_side: 'home',
    pick_label: 'Test pick',
    model_probability: 0.75,
    dk_implied_prob: 0.5,
    edge: 0.15,
    dk_odds: -110,
    scored_line: null,
    kelly_fraction: 0.03,
    recommended_bet: 30,
    bankroll_at_pick: 1000,
    injury_flag: null,
    injury_detail: null,
    signal_type: 'BET',
    confidence_tier: 'HIGH',
    result: 'WIN',
    profit_flat: WIN_PROFIT,
    profit_kelly: 27,
    settled_at: '2026-06-30T12:00:00Z',
    created_at: '2026-06-29T11:00:00Z',
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
    is_live: false,
    inning_at_pick: null,
    score_diff_at_pick: null,
    dk_bet_link: null,
    best_book: null,
    best_odds: null,
    best_implied_prob: null,
    best_edge: null,
    best_bet_link: null,
    ...over,
  };
}

const picks: Pick[] = [
  // MLB moneyline: 1W / 1L
  mk({ model_id: 'mlb_moneyline', result: 'WIN', profit_flat: WIN_PROFIT }),
  mk({ model_id: 'mlb_moneyline', result: 'LOSS', profit_flat: -100 }),
  // MLB F5 moneyline: 2W (prob 0.72 / edge 0.12 both clear 0.67/0.07).
  // This slot used to be mlb_over_under, which was PAUSED on 2026-07-14 — the
  // fixture kept counting its two wins and 21 assertions went red on arithmetic
  // that was never wrong. See the pause guard above the assertions.
  mk({ model_id: 'mlb_f5_moneyline', model_probability: 0.72, edge: 0.12, result: 'WIN', profit_flat: WIN_PROFIT }),
  mk({ model_id: 'mlb_f5_moneyline', model_probability: 0.72, edge: 0.12, result: 'WIN', profit_flat: WIN_PROFIT }),
  // WNBA assists: 1L / 1P (prob 0.72 / edge 0.12 clear 0.69/0.08)
  mk({ model_id: 'wnba_prop_player_assists', sport: 'WNBA', model_probability: 0.72, edge: 0.12, result: 'LOSS', profit_flat: -100 }),
  mk({ model_id: 'wnba_prop_player_assists', sport: 'WNBA', model_probability: 0.72, edge: 0.12, result: 'PUSH', profit_flat: 0 }),

  // ── RECORD-ONLY: batter HR (prob 0.25 clears the 0.225 prob-only cut) —
  // graded and listed, but must never count toward any total.
  mk({ model_id: 'mlb_prop_batter_hr', model_probability: 0.25, edge: 0, dk_odds: null, result: 'LOSS', profit_flat: -100 }),

  // In-play. Counts exactly like a pre-game pick since the first-signal lock
  // (session 133) made it the bet of record. A REAL live model id: the pipeline
  // never writes is_live on a pre-game model, and a fixture that does would let
  // an id-parsing bug pass.
  mk({ model_id: 'mlb_live_total_runs', model_probability: 0.72, edge: 0.16,
       is_live: true, result: 'WIN', profit_flat: 90.91 }),

  // A RETIRED live model. Its picks are real history but the model can never
  // pick again, so it is excluded here exactly as the Models tab hides it.
  mk({ model_id: 'mlb_live_win_prob', model_probability: 0.8, edge: 0.2,
       is_live: true, result: 'WIN', profit_flat: 90.91 }),

  // ── Must all be EXCLUDED ──
  mk({ model_id: 'mlb_moneyline', result: 'NO_ACTION', profit_flat: null }), // not graded
  mk({ model_id: 'mlb_moneyline', game_date: '2026-06-28', result: 'WIN' }), // wrong date
  mk({ model_id: 'mlb_moneyline', model_probability: 0.6, result: 'WIN' }), // below the prob floor
  mk({ model_id: 'mlb_f5_moneyline', signal_type: 'AVOID', model_probability: 0.72, edge: 0.12, result: 'WIN' }), // not a BET
  mk({ model_id: 'mlb_prop_batter_tb', sport: 'MLB', model_probability: 0.9, edge: 0.2, result: 'WIN' }), // paused model

  // ── PENDING: BET, clears the cut, but not yet graded (result NULL) ──
  // Was mlb_prop_pitcher_walks until it was PAUSED on 2026-07-11. dk_odds stays
  // at the mk() default of -110 because every MLB/WNBA prop carries a -140 price
  // floor (§17) — a juicier price would silently drop this from "pending".
  mk({ model_id: 'mlb_prop_pitcher_k', sport: 'MLB', model_probability: 0.75, edge: 0.1, result: null, profit_flat: null, game_id: 'gMLB1' }),
  mk({ model_id: 'mlb_moneyline', signal_type: 'AVOID', result: null }), // AVOID null → NOT pending
  // WNBA moneyline BET whose game never got a final (the "WNBA signals not
  // showing" case) — must surface as WNBA pending, not vanish.
  mk({ model_id: 'wnba_moneyline', sport: 'WNBA', model_probability: 0.7, edge: 0.1, result: null, profit_flat: null, game_id: 'gWNBA1' }),
];

// ── Fixture health ───────────────────────────────────────────────────────────
// Every model the fixture EXPECTS to be counted must currently be live. Without
// this, pausing a model turns 21 assertions red with arithmetic mismatches that
// say nothing about the cause — which is exactly what happened when
// mlb_over_under (2026-07-14) and mlb_prop_pitcher_walks (2026-07-11) were
// paused. A named failure here points straight at the fixture instead.
const COUNTED_MODELS = [
  'mlb_moneyline', 'mlb_f5_moneyline', 'wnba_prop_player_assists',
  'mlb_prop_batter_hr', 'mlb_prop_pitcher_k', 'wnba_moneyline',
];
for (const m of COUNTED_MODELS) {
  check(`fixture model ${m} is still live (swap it if it gets paused)`,
    !isModelPaused(m));
}
// And the model used as the "paused picks are excluded" case must still be
// paused, or that assertion silently stops testing anything.
check('fixture pause case (mlb_prop_batter_tb) is still paused',
  isModelPaused('mlb_prop_batter_tb'));

let nextGame = 1;
function mkGame(over: Partial<GameRow>): GameRow {
  return {
    game_id: `game${nextGame++}`,
    sport: 'MLB',
    season: 2026,
    game_date: DATE,
    home_team: 'HOM',
    away_team: 'AWY',
    home_score: 5,
    away_score: 3,
    home_score_f5: null,
    away_score_f5: null,
    commence_time: '2026-06-29T23:00:00Z',
    home_win: 1,
    home_win_reg: null,
    went_to_ot: 0,
    ...over,
  };
}

// Give two picks a shared game so pickCount aggregates.
picks[0]!.game_id = 'gMLB1';
const games: GameRow[] = [
  mkGame({ game_id: 'gMLB1', home_team: 'STL', away_team: 'DET', commence_time: '2026-06-29T23:00:00Z' }),
  mkGame({
    game_id: 'gWNBA1', sport: 'WNBA', home_team: 'NY', away_team: 'LV',
    home_score: null, away_score: null, home_win: null, commence_time: '2026-06-29T22:00:00Z',
  }),
  mkGame({ game_id: 'gNOPICKS' }), // no pick rows → excluded from the games list
  mkGame({ game_id: 'gOFFDATE', game_date: '2026-06-28' }), // wrong date → excluded
];

const r = computeDailyResults(DATE, picks, games);

// Overall: 3W-2L-1P, picks 6, profit -9.09 + 181.82 - 100 = 72.73, staked 600.
// The HR LOSS grades but is record-only — it must NOT move any of these numbers.
check('overall picks = 7 (6 pre-game + 1 in-play, HR excluded)', r.overall.picks === 7, `got ${r.overall.picks}`);
check('overall record 4-2-1', r.overall.wins === 4 && r.overall.losses === 2 && r.overall.pushes === 1,
  `${r.overall.wins}-${r.overall.losses}-${r.overall.pushes}`);
check('overall profitFlat ≈ 163.64', near(r.overall.profitFlat, 163.64), `got ${r.overall.profitFlat}`);
check('overall roiFlat ≈ 0.2338', near(r.overall.roiFlat, 163.64 / 700), `got ${r.overall.roiFlat}`);
check('overall winRate ≈ 0.6667', near(r.overall.winRate, 0.6667, 0.001), `got ${r.overall.winRate}`);

// Pending: the two BET/null picks count; the AVOID/null and NO_ACTION do not.
check('pending = 2', r.pending === 2, `got ${r.pending}`);
check('pending excluded from graded picks', r.overall.picks === 7, `got ${r.overall.picks}`);
check('pendingPicks lists both, MLB before WNBA',
  r.pendingPicks.length === 2 && r.pendingPicks[0]?.sport === 'MLB' && r.pendingPicks[1]?.sport === 'WNBA',
  r.pendingPicks.map((p) => p.sport).join(','));

// Two sports, MLB first
check('two sports', r.sports.length === 2, `got ${r.sports.length}`);
check('MLB ordered before WNBA', r.sports[0]?.sport === 'MLB' && r.sports[1]?.sport === 'WNBA',
  r.sports.map((s) => s.sport).join(','));

const mlb = r.sports.find((s) => s.sport === 'MLB')!;
const wnba = r.sports.find((s) => s.sport === 'WNBA')!;

// MLB total: 3W-1L, picks 4, profit 172.73, staked 400
check('MLB total 4-1-0', mlb.total.wins === 4 && mlb.total.losses === 1 && mlb.total.pushes === 0,
  `${mlb.total.wins}-${mlb.total.losses}-${mlb.total.pushes}`);
check('MLB profitFlat ≈ 263.64', near(mlb.total.profitFlat, 263.64), `got ${mlb.total.profitFlat}`);
check('MLB roiFlat ≈ 0.5273', near(mlb.total.roiFlat, 263.64 / 500), `got ${mlb.total.roiFlat}`);

// MLB models: f5_moneyline (+181.82), HR (record-only, zeroed → 0), moneyline (-9.09)
check('MLB has 4 models (in-play row + record-only HR)', mlb.models.length === 4, `got ${mlb.models.length}`);
check('MLB models sorted by profit desc',
  mlb.models.every((m, i) => i === 0 || mlb.models[i - 1].profitFlat >= m.profitFlat),
  mlb.models.map((m) => `${m.modelId}:${m.profitFlat.toFixed(2)}`).join(','));
// Looked up by id, not by index. These were positional, and every one of them
// broke the moment a model joined the fixture -- which says nothing about the
// code under test.
const mlbModel = (id: string) => mlb.models.find((m) => m.modelId === id);
check('mlb_f5_moneyline 2-0-0',
  mlbModel('mlb_f5_moneyline')?.wins === 2 && mlbModel('mlb_f5_moneyline')?.losses === 0, '');
check('mlb_moneyline profit ≈ -9.09',
  near(mlbModel('mlb_moneyline')?.profitFlat ?? 0, -9.09),
  `got ${mlbModel('mlb_moneyline')?.profitFlat}`);
check('the in-play model row is flagged live',
  mlbModel('mlb_live_total_runs')?.live === true, '');
check('a pre-game model row is not flagged live',
  mlbModel('mlb_f5_moneyline')?.live === false, '');
check('a retired live model contributes nothing',
  mlbModel('mlb_live_win_prob') === undefined, '');
check('the day reports its pre-game / in-play split',
  r.live === 1 && mlb.live === 1, `overall ${r.live}, MLB ${mlb.live}`);
check('paused model excluded from MLB', !mlb.models.some((m) => m.modelId === 'mlb_prop_batter_tb'), '');

// Record-only HR row: real W-L kept, money zeroed, flagged recordOnly.
const hrRow = mlb.models.find((m) => m.modelId === 'mlb_prop_batter_hr');
check('HR model row is recordOnly with real W-L',
  hrRow?.recordOnly === true && hrRow?.wins === 0 && hrRow?.losses === 1 && hrRow?.picks === 1,
  JSON.stringify(hrRow));
check('HR model row money zeroed',
  hrRow?.profitFlat === 0 && hrRow?.stakedFlat === 0 && hrRow?.roiFlat === 0,
  JSON.stringify(hrRow));
check('non-record-only rows flagged false',
  mlb.models.filter((m) => m.modelId !== 'mlb_prop_batter_hr').every((m) => m.recordOnly === false), '');

// WNBA total: 0W-1L-1P, picks 2, profit -100, staked 200
check('WNBA total 0-1-1', wnba.total.wins === 0 && wnba.total.losses === 1 && wnba.total.pushes === 1,
  `${wnba.total.wins}-${wnba.total.losses}-${wnba.total.pushes}`);
check('WNBA roiFlat = -0.5', near(wnba.total.roiFlat, -0.5), `got ${wnba.total.roiFlat}`);

// Per-sport pending counts
check('MLB pending = 1', mlb.pending === 1, `got ${mlb.pending}`);
check('WNBA pending = 1', wnba.pending === 1, `got ${wnba.pending}`);

// A sport with ONLY pending picks (nothing graded) still gets a section.
const pendingOnly = computeDailyResults(DATE, [
  mk({ model_id: 'wnba_moneyline', sport: 'WNBA', model_probability: 0.7, edge: 0.1, result: null, profit_flat: null }),
]);
check('pending-only sport gets a section',
  pendingOnly.sports.length === 1 && pendingOnly.sports[0]?.sport === 'WNBA'
    && pendingOnly.sports[0]?.pending === 1 && pendingOnly.sports[0]?.total.picks === 0,
  JSON.stringify(pendingOnly.sports.map((s) => ({ sport: s.sport, pending: s.pending }))));

// Games list: only on-date games with ≥1 scored pick row, sport-ordered.
check('games has the 2 picked games', r.games.length === 2, `got ${r.games.length}`);
check('games MLB before WNBA', r.games[0]?.sport === 'MLB' && r.games[1]?.sport === 'WNBA',
  r.games.map((g) => g.sport).join(','));
check('MLB game aggregates pick rows', r.games[0]?.pickCount === 2 && r.games[0]?.final === true,
  `count ${r.games[0]?.pickCount}, final ${r.games[0]?.final}`);
check('MLB game matchup away @ home', r.games[0]?.matchup === 'DET @ STL', `got ${r.games[0]?.matchup}`);
check('WNBA game not final', r.games[1]?.final === false && r.games[1]?.matchup === 'LV @ NY',
  `final ${r.games[1]?.final}, ${r.games[1]?.matchup}`);
check('game with no picks + off-date game excluded',
  !r.games.some((g) => g.gameId === 'gNOPICKS' || g.gameId === 'gOFFDATE'), '');

// Sport scoping (the modal's chip filter)
const all = scopeDailyResults(r, 'ALL');
check('scope ALL passes everything through (record excludes HR, list includes it)',
  all.record.picks === 7 && all.pending === 2 && all.gradedPicks.length === 8
    && all.pendingPicks.length === 2 && all.games.length === 2 && all.models === null, '');
const wnbaScope = scopeDailyResults(r, 'WNBA');
check('scope WNBA record + pending',
  wnbaScope.record.picks === 2 && wnbaScope.pending === 1
    && wnbaScope.gradedPicks.length === 2 && wnbaScope.pendingPicks.length === 1
    && wnbaScope.games.length === 1 && (wnbaScope.models?.length ?? -1) === 1,
  JSON.stringify({ picks: wnbaScope.record.picks, pending: wnbaScope.pending }));
const nhlScope = scopeDailyResults(r, 'NHL');
check('scope NHL (nothing that day) is empty',
  nhlScope.record.picks === 0 && nhlScope.pending === 0 && nhlScope.gradedPicks.length === 0
    && nhlScope.games.length === 0 && (nhlScope.models?.length ?? -1) === 0, '');

// Graded picks list: the 6 counted picks PLUS the record-only HR pick, sorted
// sport-order then profit desc, with every excluded pick (off-date, live,
// AVOID, paused, sub-threshold, NO_ACTION, pending) absent.
check('gradedPicks has 8 picks (7 counted + record-only HR)',
  r.gradedPicks.length === 8, `got ${r.gradedPicks.length}`);
check('record-only HR pick is listed',
  r.gradedPicks.some((p) => p.model_id === 'mlb_prop_batter_hr'), '');
check('gradedPicks all on-date settled BETs',
  r.gradedPicks.every((p) => p.game_date === DATE && p.signal_type === 'BET'
    && (p.result === 'WIN' || p.result === 'LOSS' || p.result === 'PUSH')), '');
check('gradedPicks MLB before WNBA',
  r.gradedPicks.findIndex((p) => p.sport === 'WNBA') === 6,
  r.gradedPicks.map((p) => p.sport).join(','));
// The property, not two indices. The old form asserted list[0] and list[3] and
// went red the moment a pick joined the fixture -- which tests the fixture, not
// the sort.
check('gradedPicks profit desc within sport',
  r.gradedPicks.every((p, i) => i === 0
    || r.gradedPicks[i - 1].sport !== p.sport
    || Number(r.gradedPicks[i - 1].profit_flat ?? 0) >= Number(p.profit_flat ?? 0)),
  r.gradedPicks.map((p) => `${p.sport}:${p.profit_flat}`).join(','));
check('paused model absent from gradedPicks',
  !r.gradedPicks.some((p) => p.model_id === 'mlb_prop_batter_tb'), '');

// ALL_SPORTS drives the modal's always-show-every-sport sections. Pinned to the
// literal on purpose — the ORDER is the product decision — but it has to be
// updated when a sport is added, and was not when NCAAF shipped (2026-08-24).
check('ALL_SPORTS is the full canonical order',
  ALL_SPORTS.join(',') === 'MLB,WNBA,NBA,NFL,NCAAF,UFC,NHL,GOLF', ALL_SPORTS.join(','));

// A day where ONLY a record-only HR pick graded: totals stay zero, but MLB
// still gets a section carrying the record-only row and the pick is listed.
const hrOnly = computeDailyResults(DATE, [
  mk({ model_id: 'mlb_prop_batter_hr', model_probability: 0.25, edge: 0, dk_odds: null, result: 'LOSS', profit_flat: -100 }),
]);
check('HR-only day: overall stays zero',
  hrOnly.overall.picks === 0 && hrOnly.overall.profitFlat === 0, JSON.stringify(hrOnly.overall));
check('HR-only day: MLB section with record-only row + listed pick',
  hrOnly.sports.length === 1 && hrOnly.sports[0]?.sport === 'MLB'
    && hrOnly.sports[0]?.total.picks === 0 && hrOnly.sports[0]?.models.length === 1
    && hrOnly.sports[0]?.models[0]?.recordOnly === true && hrOnly.gradedPicks.length === 1,
  JSON.stringify(hrOnly.sports.map((s) => ({ sport: s.sport, models: s.models.length }))));

// Empty day → empty result
const empty = computeDailyResults(DATE, []);
check('empty day → 0 picks, no sports, 0 pending, no graded/pending/games lists',
  empty.overall.picks === 0 && empty.sports.length === 0 && empty.pending === 0
    && empty.gradedPicks.length === 0 && empty.pendingPicks.length === 0
    && empty.games.length === 0, '');

// ── Live (in-play) bets fold into their sport's totals (2026-08-30) ─────────
// The `is_live` column carries two populations and only model_id separates
// them: a real live bet counts, a session-114 repair row (pre-game model,
// flagged is_live because it was scored against an in-play price) never does.
const liveDay = computeDailyResults(DATE, [
  // Real in-play bets — must COUNT.
  mk({ model_id: 'ncaaf_live_total', sport: 'NCAAF', is_live: true,
       model_probability: 0.7, edge: 0.12, result: 'WIN', profit_flat: WIN_PROFIT }),
  mk({ model_id: 'mlb_live_total_runs', is_live: true,
       model_probability: 0.72, edge: 0.16, result: 'LOSS', profit_flat: -100 }),
  // Repair row — same flag, pre-game model — must NOT count.
  mk({ model_id: 'mlb_moneyline', is_live: true, result: 'WIN', profit_flat: WIN_PROFIT }),
]);
check('live day: both real live bets counted, repair row excluded',
  liveDay.overall.picks === 2 && liveDay.overall.wins === 1 && liveDay.overall.losses === 1,
  JSON.stringify(liveDay.overall));
check('live day: P&L is the live bets only (repair row would add a 3rd win)',
  near(liveDay.overall.profitFlat, WIN_PROFIT - 100),
  String(liveDay.overall.profitFlat));
check('live day: NCAAF gets its own sport section',
  liveDay.sports.some((s) => s.sport === 'NCAAF' && s.total.picks === 1 && s.total.wins === 1),
  liveDay.sports.map((s) => `${s.sport}:${s.total.picks}`).join(','));
check('live day: MLB total is the live model only, not the repair row',
  liveDay.sports.find((s) => s.sport === 'MLB')?.total.picks === 1,
  JSON.stringify(liveDay.sports.find((s) => s.sport === 'MLB')?.total));
check('live day: live models appear as their own model rows',
  liveDay.sports.flatMap((s) => s.models).map((m) => m.modelId).sort().join(',')
    === 'mlb_live_total_runs,ncaaf_live_total',
  liveDay.sports.flatMap((s) => s.models).map((m) => m.modelId).join(','));
check('live day: real live bets are listed in gradedPicks, repair row is not',
  liveDay.gradedPicks.length === 2
    && liveDay.gradedPicks.every((p) => p.model_id.includes('_live_')),
  liveDay.gradedPicks.map((p) => p.model_id).join(','));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
