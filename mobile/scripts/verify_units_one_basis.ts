/**
 * One unit basis everywhere (mike, 2026-11-03). CLAUDE.md §2: units are the
 * graded set sized by stake_for, 1u to WIN at COALESCE(decision_odds,
 * dk_odds), risk capped at 3u, a pick with no price at the bare 1u. The Record
 * tab, Yesterday and Discord book that (published_pick_unit_profit /
 * _risked). The model pages, the Models list and the custom-model backtest
 * used profit_flat / 100 (1u RISKED) instead, so a −200 loss was −1u on a
 * model page and −2u on the Record tab. These pin every one of them on the
 * Record's basis, through postedPickUnits and the view's units / risked.
 * Tracked picks on the Performance tab book the same stake by default
 * (#1138 Decision 1); the member's own stake is an explicit override.
 *
 *   npx tsx scripts/verify_units_one_basis.ts
 */
import {
  computeBuiltInModelStats,
  computeCustomModelStats,
  EMPTY_STATS,
  mergeStats,
  recordStatsFromPublished,
  summaryToStats,
} from '../src/lib/customModelBacktest';
import { postedPickUnits, setServerThresholds } from '../src/lib/thresholds';
import { playerPickRecord } from '../src/lib/playerDetail';
import { teamPickRecords } from '../src/lib/teamDetail';
import { computeTrackedResults } from '../src/lib/trackedPerformance';
import { computeLiveTrackedResults } from '../src/lib/liveTracked';
import { trackedStakeFor } from '../src/lib/trackedStake';
import type { LiveTrackSnapshot } from '../src/hooks/useTrackedBets';
import type { CustomModel, Pick, SettledPick } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (!cond) failures++;
  console.log(`[${status}] ${name}${detail ? ` — ${detail}` : ''}`);
}
const near = (a: number, b: number, eps = 1e-9) => Math.abs(a - b) <= eps;

let nextId = 1;
function mk(over: Partial<Pick>): SettledPick {
  const id = nextId++;
  return {
    pick_id: id, game_id: `g${id}`, model_id: 'nba_total_luck', sport: 'NBA',
    game_date: '2026-11-01', game_time: '2026-11-02T00:00:00+00:00',
    pick_side: 'under', pick_label: 'Test pick', model_probability: 0.6,
    dk_implied_prob: 0.5, edge: 0.1, dk_odds: -110, scored_line: 220.5,
    kelly_fraction: 0.02, recommended_bet: 20, bankroll_at_pick: 1000,
    injury_flag: null, injury_detail: null, signal_type: 'BET',
    confidence_tier: 'HIGH', condition_status: null, result: 'WIN',
    profit_flat: 90.91, profit_kelly: 18, settled_at: '2026-11-02T10:00:00Z',
    created_at: '2026-11-01T15:00:00Z', player_id: null, pitcher_throw_hand: null,
    public_bet_pct: null, public_money_pct: null, closing_dk_odds: null,
    closing_line: null, clv_pct: null, line_clv_pts: null, clv_beat_close: null,
    clv_captured_at: null, clv_method: null, clv_close_book: null, clv_bet_book: null,
    is_live: false, inning_at_pick: null, score_diff_at_pick: null,
    dk_bet_link: null, best_book: null, best_odds: null, best_implied_prob: null,
    best_edge: null, best_bet_link: null, line_book: null, decision_book: null,
    decision_odds: null, decision_implied_prob: null, decision_edge: null,
    ...over,
  } as unknown as SettledPick;
}

setServerThresholds({});

// A −200 win, a −200 loss, a win with no price, a −400 loss (cap binds), a push.
const SET: SettledPick[] = [
  mk({ dk_odds: -200, result: 'WIN', profit_flat: 50 }),
  mk({ dk_odds: -200, result: 'LOSS', profit_flat: -100 }),
  mk({ dk_odds: null, result: 'WIN', profit_flat: 90.91 }),
  mk({ dk_odds: -400, result: 'LOSS', profit_flat: -100 }),
  mk({ dk_odds: -110, result: 'PUSH', profit_flat: 0 }),
];
// Posted: +1 − 2 + 1 − 3 + 0 = −3u, on 2 + 2 + 1 + 3 = 8u risked.
const want = SET.reduce(
  (a, p) => { const u = postedPickUnits(p); return { units: a.units + u.units, risked: a.risked + u.risked }; },
  { units: 0, risked: 0 },
);
check('fixture: the published stake books −3u on 8u risked', near(want.units, -3) && near(want.risked, 8),
  `${want.units} on ${want.risked}`);

// ── Built-in model page / Models list (the fallback behind the view) ──────
const b = computeBuiltInModelStats('nba_total_luck', SET);
check('built-in stats: units are the published stake', near(b.units, -3), String(b.units));
check('built-in stats: risked is the published stake', near(b.risked, 8), String(b.risked));
check('built-in stats: return = units / risked', near(b.roi, -3 / 8), String(b.roi));
check('built-in stats: a −200 loss is −2u, not the 1u-risked −1u', b.units < -2.5);

// ── The published view's own columns ──────────────────────────────────────
const v = recordStatsFromPublished({
  model_id: 'nba_total_luck', paused: false, prob_only: false, bets: 5, wins: 2,
  losses: 2, pushes: 1, priced_bets: 4, units: -1.5, roi_pct: -37.5,
  posted_units: -3, posted_risked: 8,
});
check('view record: units / risked come from the posted columns',
  near(v.units, -3) && near(v.risked, 8) && near(v.roi, -0.375), `${v.units} ${v.risked} ${v.roi}`);
const vOld = recordStatsFromPublished({
  model_id: 'x', paused: false, prob_only: false, bets: 2, wins: 1, losses: 1,
  pushes: 0, priced_bets: 2, units: 0.5, roi_pct: 25,
});
check('view record without the posted columns: posted is unknown, not the flat figure',
  vOld.postedKnown === false, String(vOld.postedKnown));

// ── Custom models: the local half and the server summary ──────────────────
const model = {
  id: 'm', name: 'm', rules: [{ model_id: 'nba_total_luck', min_prob: 0, min_edge: -9 }],
  filters: {}, created_at: '', updated_at: '',
} as unknown as CustomModel;
const c = computeCustomModelStats(model, SET);
check('custom (phone-graded half): the published stake, never profit_flat',
  near(c.units, -3) && near(c.risked, 8), `${c.units} on ${c.risked}`);
const s = summaryToStats({ bets: 10, wins: 5, losses: 5, pushes: 0, priced: 10, units: -0.5,
  roi_pct: -5, posted_units: -1.2, posted_risked: 11 });
check('custom (server summary): the posted function\'s units and risked',
  near(s.units, -1.2) && near(s.risked, 11) && s.postedKnown === true, `${s.units} ${s.risked}`);
const sOld = summaryToStats({ bets: 10, wins: 5, losses: 5, pushes: 0, priced: 10, units: -0.5, roi_pct: -5 });
check('custom summary before the function exists: falls back to the 1u-risked figure, flagged',
  near(sOld.units, -0.5) && sOld.postedKnown === false, `${sOld.units} ${sOld.postedKnown}`);
const m = mergeStats(s, c);
check('merge: units and risked add, return recomputed',
  near(m.units, -4.2) && near(m.risked, 19) && near(m.roi, -4.2 / 19), `${m.units} ${m.risked}`);
check('merge with an unknown half stays unknown', mergeStats(sOld, c).postedKnown === false);
check('empty stats are known and zero', EMPTY_STATS.postedKnown === true && EMPTY_STATS.units === 0);

// ── A player's pick record ────────────────────────────────────────────────
const prop = (o: Partial<Pick>) => mk({ model_id: 'nba_prop_points', player_id: 'p1', ...o } as Partial<Pick>);
const pr = playerPickRecord([
  prop({ dk_odds: -200, result: 'LOSS', profit_flat: -100 }),
  prop({ dk_odds: null, result: 'WIN', profit_flat: 90.91 }),
] as SettledPick[]);
check('player record: the published stake (−2u + 1u = −1u), the unpriced win at 1u',
  pr.units != null && near(pr.units, -1), String(pr.units));

// ── A team's pick record ──────────────────────────────────────────────────
const tg = { game_id: 'tg1', home_team: 'BOS', away_team: 'NYK' } as unknown as Parameters<typeof teamPickRecords>[1][number];
const tr = teamPickRecords([
  mk({ game_id: 'tg1', model_id: 'nba_moneyline', pick_side: 'home', dk_odds: -200, result: 'LOSS', profit_flat: -100 }),
] as SettledPick[], [tg], 'BOS');
const teamUnits = [tr.on, tr.against, tr.over, tr.under].reduce((a, r) => a + (r.units ?? 0), 0);
check('team record: a −200 loss is −2u on the published stake', near(teamUnits, -2), String(teamUnits));

// ── Tracked picks on the Performance tab (#1138 Decision 1) ───────────────
// Stored at the 100-is-1u scale (lib/format FLAT_UNIT), so /100 is units.
// The tracked graders take full pick rows; the fixtures above are settled rows.
const asPick = (p: SettledPick): Pick => p as unknown as Pick;
const TP: Pick[] = SET.map(asPick);
const ids = TP.map((p) => p.pick_id);
const asPosted = trackedStakeFor('posted', {});
const tp = computeTrackedResults(ids, TP, asPosted);
check('tracked, as posted: net is the Record tab\'s −3u', near(tp.summary.net / 100, -3, 1e-6),
  String(tp.summary.net / 100));
check('tracked, as posted: staked is the Record tab\'s 8u risked', near(tp.summary.staked / 100, 8, 1e-6),
  String(tp.summary.staked / 100));
check('tracked, as posted: return = units / risked, as on the Record tab',
  tp.summary.roi != null && near(tp.summary.roi, -3 / 8, 1e-6), String(tp.summary.roi));
check('tracked, as posted: every row is postedPickUnits',
  tp.rows.every((r) => near(r.profit / 100, postedPickUnits(r.pick).units, 1e-6)));
check('tracked, as posted: no row is marked as the member\'s own stake', tp.rows.every((r) => !r.customStake));
const rowOf = (res: typeof tp, p: Pick) => res.rows.find((r) => r.pick.pick_id === p.pick_id)!;
check('tracked, as posted: a −200 win is +1.00u (1u risked read +0.50u)',
  near(rowOf(tp, TP[0]).profit, 100, 1e-6), String(rowOf(tp, TP[0]).profit));
check('tracked, as posted: a −200 loss is −2.00u', near(rowOf(tp, TP[1]).profit, -200, 1e-6));
check('tracked, as posted: a win with no price is +1.00u, never profit_flat\'s invented −110 (+0.91u)',
  near(rowOf(tp, TP[2]).profit, 100, 1e-6), String(rowOf(tp, TP[2]).profit));
check('tracked, as posted: the 3u cap binds on a −400 loss', near(rowOf(tp, TP[3]).profit, -300, 1e-6));
const dog = asPick(mk({ dk_odds: 150, result: 'LOSS', profit_flat: -100 }));
const tDog = computeTrackedResults([dog.pick_id], [dog], asPosted);
check('tracked, as posted: a +150 loss is −0.67u (1u risked read −1.00u)',
  near(tDog.summary.net / 100, -1 / 1.5, 1e-4), String(tDog.summary.net / 100));
const decided = asPick(mk({ dk_odds: -110, decision_odds: 120, result: 'WIN', profit_flat: 120 }));
const tDec = computeTrackedResults([decided.pick_id], [decided], asPosted);
check('tracked, as posted: staked at the decided price, not DraftKings (+120 risks 0.83u to win 1u)',
  near(tDec.summary.net, 100, 1e-6) && near(tDec.summary.staked / 100, 1 / 1.2, 1e-6),
  `${tDec.summary.net} on ${tDec.summary.staked}`);
const openPick = asPick(mk({ dk_odds: -150, result: null, profit_flat: null, settled_at: null }));
const tOpen = computeTrackedResults([openPick.pick_id], [openPick], asPosted);
check('tracked, as posted: an open pick shows the stake it lays (1.5u at −150) and counts nothing',
  near(tOpen.rows[0].stake, 150, 1e-6) && tOpen.summary.net === 0 && tOpen.summary.staked === 0,
  `${tOpen.rows[0].stake}`);

// The member's own stake: an override where one is set, the posted stake elsewhere.
const mine = trackedStakeFor('custom', { [String(TP[0].pick_id)]: 300, [String(TP[2].pick_id)]: 200 });
const tm = computeTrackedResults(ids, TP, mine);
check('my stakes: a 3u stake on a −200 win pays +1.50u at the decided price',
  near(rowOf(tm, TP[0]).profit, 150, 1e-6) && rowOf(tm, TP[0]).customStake,
  String(rowOf(tm, TP[0]).profit));
check('my stakes: a 2u stake on a win with no price is +2.00u at even money, as the posted stake counts it',
  near(rowOf(tm, TP[2]).profit, 200, 1e-6), String(rowOf(tm, TP[2]).profit));
check('my stakes: bets left alone stay as posted',
  [TP[1], TP[3], TP[4]].every((p) => near(rowOf(tm, p).profit, rowOf(tp, p).profit, 1e-6)
    && !rowOf(tm, p).customStake));
check('my stakes: a stake set to the posted risk gives the posted result',
  near(computeTrackedResults([TP[1].pick_id], TP, trackedStakeFor('custom', { [String(TP[1].pick_id)]: 200 })).summary.net,
    rowOf(tp, TP[1]).profit, 1e-6));
const ignored = computeTrackedResults(ids, TP, trackedStakeFor('posted', { [String(TP[0].pick_id)]: 300 }));
check('as posted ignores a stake the member saved under My stakes', near(ignored.summary.net / 100, -3, 1e-6));

// A tracked live (in-play) pick books the same stake.
const liveWin = asPick(mk({ is_live: true, dk_odds: -200, result: 'WIN', profit_flat: 50 }));
const snapshot: LiveTrackSnapshot = {
  key: `${liveWin.game_id}|${liveWin.model_id}|${liveWin.pick_side}`, game_id: liveWin.game_id,
  model_id: liveWin.model_id, pick_side: liveWin.pick_side, pick_label: liveWin.pick_label,
  sport: liveWin.sport, game_date: liveWin.game_date, dk_odds: -200, scored_line: null,
  tracked_at: '2026-11-01T20:00:00Z',
};
const lt = computeLiveTrackedResults([snapshot], [liveWin], () => true, asPosted);
check('tracked live, as posted: a −200 win is +1.00u on 2u risked',
  near(lt.summary.net, 100, 1e-6) && near(lt.summary.staked, 200, 1e-6), `${lt.summary.net} on ${lt.summary.staked}`);

console.log(failures === 0 ? '\nAll checks passed.' : `\n${failures} check(s) FAILED.`);
process.exit(failures === 0 ? 0 : 1);
