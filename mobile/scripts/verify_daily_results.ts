/**
 * Standalone verification for the daily-recap aggregator (src/lib/dailyResults.ts).
 * No JS test runner is configured for the app, so — like the other verify_*.ts
 * scripts — we assert the pure function here and run with tsx:
 *
 *   npx tsx scripts/verify_daily_results.ts
 *
 * Pins: overall + per-sport + per-model records and the posted-stake units
 * and ROI (the same stake Discord #results books) are correct; that
 * off-date, NO_ACTION, AVOID, retired, and ungraded-below-the-cut picks are
 * excluded. A graded pick stays if its model is paused now or if it would
 * miss today's cut — that is the record filter. A retired
 * model contributes nothing to any total.
 */
import { ALL_SPORTS, computeDailyResults, scopeDailyResults } from '../src/lib/dailyResults';
import { isModelPaused, postedPickUnits } from '../src/lib/thresholds';
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
    condition_status: null,
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
    clv_captured_at: null, clv_method: null, clv_close_book: null, clv_bet_book: null,
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

  // ── RETIRED pre-game model (2026-09-02): batter HR. It must contribute NOTHING —
  // no row, no listing, no total — exactly like the retired live model below.
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

  // Graded, and below today's prob floor. It still counts: the floor decides
  // the next bet, not a bet already settled.
  mk({ model_id: 'mlb_moneyline', model_probability: 0.6, result: 'WIN' }),
  // Graded while the model is paused now. A pause does not take the bet back.
  mk({ model_id: 'mlb_prop_batter_tb', sport: 'MLB', model_probability: 0.9, edge: 0.2, result: 'WIN' }),

  // ── Must all be EXCLUDED ──
  mk({ model_id: 'mlb_moneyline', result: 'NO_ACTION', profit_flat: null }), // not graded
  mk({ model_id: 'mlb_moneyline', game_date: '2026-06-28', result: 'WIN' }), // wrong date
  mk({ model_id: 'mlb_f5_moneyline', signal_type: 'AVOID', model_probability: 0.72, edge: 0.12, result: 'WIN' }), // not a BET

  // ── PENDING: BET, clears the cut, but not yet graded (result NULL) ──
  // A live model. A paused model's ungraded row is not "still placed".
  mk({ model_id: 'mlb_f5_moneyline', sport: 'MLB', model_probability: 0.75, edge: 0.1, result: null, profit_flat: null, game_id: 'gMLB1' }),
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
  'wnba_moneyline',
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

// 6W-2L-1P. The two extra wins are a graded pick under today's prob floor
// and a graded pick whose model is paused now. Both were bets, so both
// count. Every price is -110: a win is +1u on 1.1 risked, a loss is -1.1u,
// and the push risks nothing. The retired HR loss stays out.
check('overall picks = 9', r.overall.picks === 9, `got ${r.overall.picks}`);
check('overall record 6-2-1', r.overall.wins === 6 && r.overall.losses === 2 && r.overall.pushes === 1,
  `${r.overall.wins}-${r.overall.losses}-${r.overall.pushes}`);
check('overall units = 3.8', near(r.overall.units, 3.8), `got ${r.overall.units}`);
check('overall risked = 8.8', near(r.overall.risked, 8.8), `got ${r.overall.risked}`);
check('overall roi = 3.8/8.8', near(r.overall.roi, 3.8 / 8.8), `got ${r.overall.roi}`);
check('overall winRate = 0.75', near(r.overall.winRate, 0.75, 0.001), `got ${r.overall.winRate}`);

// Pending: the two BET/null picks count; the AVOID/null and NO_ACTION do not.
check('pending = 2', r.pending === 2, `got ${r.pending}`);
check('pending excluded from graded picks', r.overall.picks === 9, `got ${r.overall.picks}`);
check('pendingPicks lists both, MLB before WNBA',
  r.pendingPicks.length === 2 && r.pendingPicks[0]?.sport === 'MLB' && r.pendingPicks[1]?.sport === 'WNBA',
  r.pendingPicks.map((p) => p.sport).join(','));

// Two sports, MLB first
check('two sports', r.sports.length === 2, `got ${r.sports.length}`);
check('MLB ordered before WNBA', r.sports[0]?.sport === 'MLB' && r.sports[1]?.sport === 'WNBA',
  r.sports.map((s) => s.sport).join(','));

const mlb = r.sports.find((s) => s.sport === 'MLB')!;
const wnba = r.sports.find((s) => s.sport === 'WNBA')!;

// MLB total: 6W-1L. Four of the original wins, plus the sub-threshold win
// and the paused model's win.
check('MLB total 6-1-0', mlb.total.wins === 6 && mlb.total.losses === 1 && mlb.total.pushes === 0,
  `${mlb.total.wins}-${mlb.total.losses}-${mlb.total.pushes}`);
check('MLB units = 4.9', near(mlb.total.units, 4.9), `got ${mlb.total.units}`);
check('MLB roi = 4.9/7.7', near(mlb.total.roi, 4.9 / 7.7), `got ${mlb.total.roi}`);

// MLB models: f5, the in-play win, the paused model's win, moneyline. No HR.
check('MLB has 4 models (paused graded row included, retired HR absent)', mlb.models.length === 4, `got ${mlb.models.length}`);
check('MLB models sorted by units desc',
  mlb.models.every((m, i) => i === 0 || mlb.models[i - 1].units >= m.units),
  mlb.models.map((m) => `${m.modelId}:${m.units.toFixed(2)}`).join(','));
// Looked up by id, not by index. These were positional, and every one of them
// broke the moment a model joined the fixture -- which says nothing about the
// code under test.
const mlbModel = (id: string) => mlb.models.find((m) => m.modelId === id);
check('mlb_f5_moneyline 2-0-0',
  mlbModel('mlb_f5_moneyline')?.wins === 2 && mlbModel('mlb_f5_moneyline')?.losses === 0, '');
check('mlb_moneyline units = 0.9 (the sub-threshold win still counts)',
  near(mlbModel('mlb_moneyline')?.units ?? 0, 0.9),
  `got ${mlbModel('mlb_moneyline')?.units}`);
check('the in-play model row is flagged live',
  mlbModel('mlb_live_total_runs')?.live === true, '');
check('a pre-game model row is not flagged live',
  mlbModel('mlb_f5_moneyline')?.live === false, '');
check('a retired live model contributes nothing',
  mlbModel('mlb_live_win_prob') === undefined, '');
check('the day reports its pre-game / in-play split',
  r.live === 1 && mlb.live === 1, `overall ${r.live}, MLB ${mlb.live}`);
check('a graded pick from a paused model still counts',
  mlbModel('mlb_prop_batter_tb')?.wins === 1, '');

// A retired pre-game model contributes nothing.
check('a retired pre-game model contributes no row',
  mlb.models.find((m) => m.modelId === 'mlb_prop_batter_hr') === undefined, '');

// WNBA total: 0W-1L-1P. The push risks nothing, so the loss is the whole book.
check('WNBA total 0-1-1', wnba.total.wins === 0 && wnba.total.losses === 1 && wnba.total.pushes === 1,
  `${wnba.total.wins}-${wnba.total.losses}-${wnba.total.pushes}`);
check('WNBA units = -1.1 and the push is not risked',
  near(wnba.total.units, -1.1) && near(wnba.total.risked, 1.1) && near(wnba.total.roi, -1),
  `units ${wnba.total.units} risked ${wnba.total.risked} roi ${wnba.total.roi}`);

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
check('scope ALL passes everything through (the retired HR pick in neither)',
  all.record.picks === 9 && all.pending === 2 && all.gradedPicks.length === 9
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

// Graded picks list: exactly the 7 counted picks, sorted sport-order then
// profit desc, with every excluded pick (off-date, retired, AVOID, paused,
// sub-threshold, NO_ACTION, pending) absent.
check('gradedPicks has 9 picks (the counted ones, nothing else)',
  r.gradedPicks.length === 9, `got ${r.gradedPicks.length}`);
check('the retired HR pick is not listed',
  !r.gradedPicks.some((p) => p.model_id === 'mlb_prop_batter_hr'), '');
check('gradedPicks all on-date settled BETs',
  r.gradedPicks.every((p) => p.game_date === DATE && p.signal_type === 'BET'
    && (p.result === 'WIN' || p.result === 'LOSS' || p.result === 'PUSH')), '');
check('gradedPicks MLB before WNBA',
  r.gradedPicks.findIndex((p) => p.sport === 'WNBA') === 7,
  r.gradedPicks.map((p) => p.sport).join(','));
// The property, not two indices. The old form asserted list[0] and list[3] and
// went red the moment a pick joined the fixture -- which tests the fixture, not
// the sort.
check('gradedPicks units desc within sport',
  r.gradedPicks.every((p, i) => i === 0
    || r.gradedPicks[i - 1].sport !== p.sport
    || postedPickUnits(r.gradedPicks[i - 1]).units >= postedPickUnits(p).units),
  r.gradedPicks.map((p) => `${p.sport}:${postedPickUnits(p).units}`).join(','));
check('the paused model\'s graded win is listed',
  r.gradedPicks.some((p) => p.model_id === 'mlb_prop_batter_tb'), '');

// ALL_SPORTS drives the modal's always-show-every-sport sections. Pinned to the
// literal on purpose — the ORDER is the product decision — but it has to be
// updated when a sport is added, and was not when NCAAF shipped (2026-08-24).
// NCAAB joined beside NCAAF on 2026-10-30.
check('ALL_SPORTS is the full canonical order',
  ALL_SPORTS.join(',') === 'MLB,WNBA,NBA,NFL,NCAAF,NCAAB,UFC,NHL', ALL_SPORTS.join(','));

// A day where ONLY a retired model's pick graded is an EMPTY day: no totals,
// no sport section, nothing listed.
const hrOnly = computeDailyResults(DATE, [
  mk({ model_id: 'mlb_prop_batter_hr', model_probability: 0.25, edge: 0, dk_odds: null, result: 'LOSS', profit_flat: -100 }),
]);
check('retired-only day: overall stays zero',
  hrOnly.overall.picks === 0 && hrOnly.overall.units === 0 && hrOnly.overall.risked === 0,
  JSON.stringify(hrOnly.overall));
check('retired-only day: no sport section, nothing listed',
  hrOnly.sports.length === 0 && hrOnly.gradedPicks.length === 0,
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
check('live day: units are the live bets only (repair row would add a 3rd win)',
  near(liveDay.overall.units, 1 - 1.1) && near(liveDay.overall.risked, 2.2),
  `units ${liveDay.overall.units} risked ${liveDay.overall.risked}`);
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

const unpublished = computeDailyResults(DATE, [
  mk({ result: 'WIN', profit_flat: WIN_PROFIT, discordPublish: 'unpublished' }),
  mk({ result: 'LOSS', profit_flat: -100, discordPublish: 'published' }),
]);
check('an unpublished graded bet is left out of the day',
  unpublished.overall.picks === 1 && unpublished.overall.losses === 1
    && unpublished.gradedPicks.length === 1 && unpublished.unpublished === 1
    && unpublished.sports.find((s) => s.sport === 'MLB')?.unpublished === 1,
  JSON.stringify(unpublished.overall));
const unpostedDay = computeDailyResults(DATE, [
  mk({ result: 'WIN', profit_flat: WIN_PROFIT, discordPublish: 'unpublished' }),
]);
check('a day of only unpublished bets reports that count and an empty record',
  unpostedDay.overall.picks === 0 && unpostedDay.unpublished === 1
    && unpostedDay.gradedPicks.length === 0,
  JSON.stringify({ picks: unpostedDay.overall.picks, unpublished: unpostedDay.unpublished }));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
