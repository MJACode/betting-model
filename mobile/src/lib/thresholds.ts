/**
 * Mirror of config.py — ACTION_THRESHOLDS, PAUSED_MODELS, PROB_ONLY_MODELS, KELLY.
 *
 * PINNED BY tests/test_mobile_threshold_parity.py, which fails until this file
 * equals config.py. "UPDATE THIS FILE whenever config.py changes" was the whole
 * mechanism until 2026-09-11 and it did not hold: nothing tested it, so by then
 * one live model was absent outright, 16 were paused here and live in config, 3
 * were live here and paused in config, 24 cuts disagreed, and 40 carried no
 * price floor where config resolves one. A comment is not a guard.
 *
 * WHY IT MATTERS even though the server store wins: `thresholdFor` and
 * `isModelPaused` consult `model_action_thresholds` PER MODEL ID and fall
 * through to these constants whenever it has not been fetched yet or has no row
 * for that id — so every cold start renders its first board from this file.
 *
 * `min_odds` is the RESOLVED floor (config.min_odds_for: the model's own, else
 * DEFAULT_MIN_ODDS −200), which is what threshold_sync writes to the server.
 * Last synced: 2026-09-11.
 */

import { decisionEdge, decisionOdds } from './decisionPrice';
import { todayET } from './format';
import type { Pick as PickRow } from '@/types';

/**
 * The columns the action filter reads. Typed as a subset so it accepts both a
 * full Pick and the slimmer SettledPick the model screens cache.
 */
export type ActionFilterable = Pick<
  PickRow,
  'model_id' | 'model_probability' | 'edge' | 'dk_odds' | 'signal_type'
  // REQUIRED, not optional (2026-09-09). The guard is only as good as the
  // SELECT that feeds it: a new query picking a column subset and forgetting
  // this one would compile, pass ux_scan (no cross-file reachability) and pass
  // the test that pins the line exists — the blind-spot shape
  // .claude/rules/frontend.md warns about. Both pick reads carry the column
  // now, so requiring it costs nothing and makes the omission a type error.
  | 'condition_status'
> & {
  // The price the pick was DECIDED at (2026-09-09). Optional so the slimmer
  // row shapes that predate the columns still type-check; absent = DraftKings.
  decision_odds?: number | null;
  decision_edge?: number | null;
};

export interface ModelThreshold {
  min_prob: number;
  min_edge: number;
  /** Floor on the acceptable DK price (American odds). A pick priced juicier
   *  than this (more negative, e.g. -165 < -140) is not actionable. Absent /
   *  null = no price floor. NULL dk_odds (prob-only) always passes. */
  min_odds?: number | null;
}

export const ACTION_THRESHOLDS: Record<string, ModelThreshold> = {
  // Game models — re-optimized 2026-06-20 from settled BET picks since 2026-04-14 (in-sample; will regress)
  mlb_moneyline: { min_prob: 0.72, min_edge: 0.11, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  mlb_over_under: { min_prob: 0.5, min_edge: 0.04, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  mlb_runline: { min_prob: 0.68, min_edge: 0.11, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  mlb_f5_moneyline: { min_prob: 0.58, min_edge: 0.02, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for

  // LIVE MLB, re-cut 2026-08-29 from the settled live record: total_runs is the
  // only profitable live model (0.68/0.14 = 17 bets 12-5 +27.9%). The two binary
  // models were negative at every cut and are RETIRED (see RETIRED_MODELS).
  mlb_live_total_runs: { min_prob: 0.72, min_edge: 0.14, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for

  // Pitcher props (2026-06-20 sweep; hits/walks have no winning cut → retraining)
  // min_odds -140: every MLB + WNBA prop now carries a -140 price floor (2026-07-22,
  // Matt: "don't recommend prop picks with a betting line over -140"). A prop priced
  // juicier than -140 scores NONE, not BET. See config.MODEL_MIN_ODDS.
  mlb_prop_pitcher_k: { min_prob: 0.58, min_edge: 0.08, min_odds: -140 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  mlb_prop_pitcher_hits: { min_prob: 0.54, min_edge: 0.08, min_odds: -140 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  mlb_prop_pitcher_er: { min_prob: 0.61, min_edge: 0.08, min_odds: -140 }, // 2026-06-21 ≥10% target: +11.1%/81
  mlb_prop_pitcher_outs: { min_prob: 0.50, min_edge: 0.12, min_odds: -140 },
  mlb_prop_pitcher_walks: { min_prob: 0.60, min_edge: 0.08, min_odds: -140 },

  // Batter props (2026-06-20 sweep; sb has no winning cut; hr + rbi RETIRED below)
  mlb_prop_batter_hits: { min_prob: 0.78, min_edge: 0.17, min_odds: -140 }, // 2026-06-28 full-outcome: 77 bets +8.3% (UNPAUSED)
  mlb_prop_batter_tb: { min_prob: 0.83, min_edge: 0.17, min_odds: -140 },
  // mlb_prop_batter_hr + mlb_prop_batter_rbi RETIRED 2026-09-02 — see RETIRED_MODELS.
  mlb_prop_batter_runs: { min_prob: 0.62, min_edge: 0.1, min_odds: -140 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  mlb_prop_batter_sb: { min_prob: 0.18, min_edge: 0.10, min_odds: -140 },
  mlb_prop_batter_walks: { min_prob: 0.45, min_edge: 0.14, min_odds: -140 }, // 2026-06-21 RE-SWEEP: +5.3%/65

  // WNBA — placeholder thresholds; retune after the 2025 holdout backtest sweep.
  wnba_moneyline: { min_prob: 0.5, min_edge: 0.06, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  wnba_over_under: { min_prob: 0.6, min_edge: 0.06, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  wnba_spread: { min_prob: 0.6, min_edge: 0.1, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  // WNBA props — re-optimized 2026-06-20 (thin 15-40 bet samples since June 1; will regress); -140 floor 2026-07-22
  wnba_prop_player_points: { min_prob: 0.58, min_edge: 0.17, min_odds: -140 }, // PAUSED 2026-07-11 — no positive cut on the 2x sample
  wnba_prop_player_rebounds: { min_prob: 0.62, min_edge: 0, min_odds: -140 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  wnba_prop_player_assists: { min_prob: 0.5, min_edge: 0.1, min_odds: -140 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  wnba_prop_market: { min_prob: 0.0, min_edge: 0.05, min_odds: -140 }, // market-relative rule (Pinnacle de-vig); edge IS the signal — NFL precedent
  wnba_prop_player_threes: { min_prob: 0.706, min_edge: 0.026, min_odds: -140 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  wnba_prop_player_pra: { min_prob: 0.68, min_edge: 0.16, min_odds: -140 }, // cut per config.ACTION_THRESHOLDS + min_odds_for

  // NBA — placeholder thresholds; tune after live odds accumulate.
  // nba_prop_player_dd is prob-only (DK juices double-double Yes/No).
  nba_moneyline: { min_prob: 0.66, min_edge: 0.12, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nba_over_under: { min_prob: 0.66, min_edge: 0.12, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nba_spread: { min_prob: 0.66, min_edge: 0.12, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nba_prop_player_points: { min_prob: 0.6, min_edge: 0.08, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nba_prop_player_rebounds: { min_prob: 0.6, min_edge: 0.08, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nba_prop_player_assists: { min_prob: 0.6, min_edge: 0.08, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nba_prop_player_threes: { min_prob: 0.6, min_edge: 0.08, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nba_prop_player_pra: { min_prob: 0.6, min_edge: 0.08, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nba_prop_player_blocks: { min_prob: 0.6, min_edge: 0.08, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nba_prop_player_steals: { min_prob: 0.6, min_edge: 0.08, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nba_prop_player_turnovers: { min_prob: 0.6, min_edge: 0.08, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nba_prop_player_dd: { min_prob: 0.55, min_edge: 0, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for

  // UFC — placeholder thresholds; tune after 50+ settled picks.
  // ufc_method_of_victory is prob-only (no DK method odds via The Odds API).
  ufc_moneyline: { min_prob: 0.65, min_edge: 0.08, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  ufc_total_rounds: { min_prob: 0.62, min_edge: 0.08, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  ufc_method_of_victory: { min_prob: 0.65, min_edge: 0, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for

  // NHL — placeholder thresholds; tune after 50+ settled picks.
  // moneyline_regulation is a 3-way market (lower per-side prob).
  nhl_moneyline: { min_prob: 0.55, min_edge: 0.05, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nhl_moneyline_regulation: { min_prob: 0.4, min_edge: 0.05, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nhl_over_under: { min_prob: 0.55, min_edge: 0.05, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nhl_puckline: { min_prob: 0.55, min_edge: 0.05, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for

  // NCAAF — ncaaf_spread is a MARGIN-REGRESSION model. min_prob is the
  // out-of-sample residual-ECDF probability at the validated +/-5.5-point
  // disagreement gate, so the prob floor IS the gate; edge floor is 0.0 on
  // purpose (the validated rule is the disagreement, not a price filter).
  // PAPER ONLY until 50+ settled picks clear the go-live gate.
  // 0.55 floors the opener rule's flat validated prob (0.5810); the real
  // filter is the |dev| >= 1.0 gate enforced server-side.
  ncaaf_spread: { min_prob: 0.55, min_edge: 0, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  // Premium opener band [2.5, inf): 344 bets, 60.5%, +15.4% (2023-25,
  // positive every season). Disjoint from ncaaf_spread by construction.
  ncaaf_spread_premium: { min_prob: 0.58, min_edge: 0, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  // NCAAF live lanes (calibration set — no in-play edge measured yet)
  ncaaf_live_win_prob: { min_prob: 0.66, min_edge: 0.1, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  ncaaf_live_total: { min_prob: 0.66, min_edge: 0.12, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  // Paused (see PAUSED_MODELS) — cuts kept so unpausing is one edit.
  ncaaf_moneyline: { min_prob: 0.62, min_edge: 0.08, min_odds: -250 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  // 0.65 = P(over) at the validated +/-8.0 gate; the server enforces the
  // symmetric gate itself, so this floor is a backstop rather than the rule.
  ncaaf_over_under: { min_prob: 0.65, min_edge: 0, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for

  // NFL — the standalone wind-totals card (§28). The card itself is the real
  // gate (forecast wind >= 11mph + >= 3% edge after de-vig); these floors just
  // mirror it so a card-qualified pick can never be hidden by the filter.
  nfl_wind_totals: { min_prob: 0.52, min_edge: 0.03, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  // Opener: model_prob is the pooled validated ATS (0.5818) — 0.52 floors it;
  // edge >= 0 drops bets whose quoted juice eats the whole edge.
  // 0.55 mirrors the card's |dev| >= 2.0 gate (#651, 2026-09-11, mike):
  // model_prob_for_dev(2.0) = 0.5557 clears it, the 0.5470 a 1-point
  // deviation carries does not. Raised from 0.52 with config in the same
  // breath -- test_mobile_threshold_parity caught the drift the day it
  // appeared, which is the whole point of it.
  nfl_opener_spread: { min_prob: 0.55, min_edge: 0.0, min_odds: -200 },

  // NFL props — trained 2026-08-23, ALL PAUSED (see PAUSED_MODELS below).
  // Listed anyway so the offline / first-launch fallback knows their cuts.
  // A model ABSENT from this map is invisible to passesActionFilter, so if
  // one were unpaused server-side it would stay hidden in the app until
  // model_action_thresholds had been fetched.
  nfl_prop_anytime_td: { min_prob: 0.37, min_edge: 0.16, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nfl_prop_pass_attempts: { min_prob: 0.73, min_edge: 0.19, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nfl_prop_pass_completions: { min_prob: 0.68, min_edge: 0.16, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nfl_prop_pass_tds: { min_prob: 0.78, min_edge: 0.17, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nfl_prop_pass_yards: { min_prob: 0.68, min_edge: 0.15, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nfl_prop_rec_yards: { min_prob: 0.69, min_edge: 0.16, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nfl_prop_receptions: { min_prob: 0.63, min_edge: 0.16, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nfl_prop_rush_attempts: { min_prob: 0.76, min_edge: 0.2, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nfl_prop_rush_rec_yards: { min_prob: 0.68, min_edge: 0.15, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nfl_prop_rush_yards: { min_prob: 0.71, min_edge: 0.19, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nfl_prop_sacks: { min_prob: 0.7, min_edge: 0.15, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  nfl_prop_tackles_assists: { min_prob: 0.7, min_edge: 0.15, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for
  // Market-relative props: model_prob is Pinnacle's DE-VIGGED number, which is
  // near 0.5 by construction, so a probability floor would cut the rule's core.
  // The edge is the whole signal, and 5pp is pre-committed (6pp wins in
  // training and returns -0.46% blind). See docs/nfl_props_model.md §5c.
  // The in-play NFL prop lane (nfl/live_model). LIVE since 2026-09-05 with
  // the §2 go-live gate deliberately not met (Matt's call), and announcing on
  // Discord since #629 -- but it had NO row here at all, so before the server
  // store is fetched `thresholdFor` returned null and passesActionFilter
  // refused every one of its BETs. The real cut is EV, in
  // nfl/live_model/config.EV_THRESHOLDS; 0/0 mirrors config.
  nfl_live_prop: { min_prob: 0, min_edge: 0, min_odds: -140 },
  nfl_prop_market: { min_prob: 0, min_edge: 0.05, min_odds: -200 }, // cut per config.ACTION_THRESHOLDS + min_odds_for

  // GOLF RETIRED 2026-09-08 — see RETIRED_MODELS below.
};

export const PROB_ONLY_MODELS = new Set<string>([
  // mlb_prop_batter_hr was here until it was RETIRED 2026-09-02 — see
  // RETIRED_PROB_ONLY_MODELS just below for why it still matters.
  'ufc_method_of_victory',
  'nba_prop_player_dd',
]);

// Models that WERE prob-only when they made their picks and have since been
// retired. PROB_ONLY_MODELS stays a strict mirror of config.py, so a retired id
// cannot live there — but a pick made by a prob-only model was explained as a
// probability call, not an edge call, and that explanation must not change
// after the fact (§1c: a pick's meaning is fixed when it is made). Anything
// that RENDERS a pick reads isProbOnlyModel(); passesActionFilter keeps reading
// PROB_ONLY_MODELS because a retired model never reaches that branch.
export const RETIRED_PROB_ONLY_MODELS = new Set<string>(['mlb_prop_batter_hr']);

export function isProbOnlyModel(modelId: string): boolean {
  return PROB_ONLY_MODELS.has(modelId) || RETIRED_PROB_ONLY_MODELS.has(modelId);
}

// A STRICT MIRROR of config.PAUSED_MODELS — models that never fire a BET —
// pinned by tests/test_mobile_threshold_parity.py. The server store
// (model_action_thresholds.paused) is authoritative once fetched; this list is
// what every COLD START renders its first board from, so a stale entry here
// either hides a live model's picks or draws a stakeable BET for one the
// platform has withdrawn.
//
// A PAUSED MODEL STILL SCORES NONE ROWS, so its cards keep drawing on the Today
// board and its market keeps a chip in the filter (useTodayPicks drops retired
// and VOID rows at the source, paused ones deliberately not). What it can never
// be is a BET.
//
// The per-model reasoning lives in config.py beside each id and is NOT copied
// here -- it had drifted out of agreement with this very list (the old comment
// said mlb_prop_batter_hits was unpaused while config had paused it), and a
// comment that contradicts its own data is worse than no comment. "Paused for
// poor performance" went with it and was not replaced: it is wrong for three of
// the thirteen — config calls wnba_over_under and wnba_spread "UNVALIDATED, not
// proven bad" and mlb_runline dormant rather than broken.
export const PAUSED_MODELS = new Set<string>([
  'mlb_over_under',
  'mlb_prop_batter_hits',
  'mlb_prop_batter_sb',
  'mlb_prop_batter_tb',
  'mlb_prop_pitcher_er',
  'mlb_prop_pitcher_walks',
  'mlb_runline',
  'ncaaf_moneyline',
  'ufc_total_rounds',
  'wnba_over_under',
  'wnba_prop_player_points',
  'wnba_prop_player_threes',
  'wnba_spread',
]);

// Retired models — removed from config.LIVE_MODELS / MODELS entirely, so they
// can never score another pick. Their EXISTING picks stay in the DB and keep
// their labels (a pick that existed is the bet of record), so MODEL_META keeps
// its entries and the market mapping keeps working for the Line Movement card;
// what retirement changes is that they are never actionable and never listed as
// a model you could follow.
//
// This is not the same thing as paused, and it does not reduce to a threshold
// lookup: the server's model_action_thresholds row survives until the next
// threshold_sync prune, and while it does it reports paused=false — so without
// this set an old live BET would read as actionable again the moment the retired
// model dropped out of the bundled PAUSED_MODELS list.
//
// 2026-08-30: the two binary MLB live models. Overconfident in production
// (win_prob 15 bets 6-9 -34.1%, runline 14 bets 5-9 -39.9%, both worse at
// higher probability floors), which is a calibration failure a cut cannot fix.
//
// 2026-09-02 (Matt): batter home runs and batter RBIs. Removed from the app and
// from every model total. HR was already record-only and already excluded from
// the public record (42-214 over 256 settled bets in a ~17%-hit longshot market
// whose +EV filter was anti-predictive); RBI had ONE settled bet clearing the
// cut it was re-cut to the day before, on the most floor-distorted sweep on the
// board. Mirrors config.RETIRED_MODELS; keep the two in sync.
export const RETIRED_MODELS = new Set<string>([
  'mlb_live_win_prob',
  'mlb_live_runline',
  'mlb_prop_batter_hr',
  'mlb_prop_batter_rbi',
  // 2026-09-08 (mike): golf retired outright. DATAGOLF_API_KEY was never set on
  // the worker, so every golf pipeline step no-opped and the sport produced no
  // games, no odds and no picks, ever.
  'golf_outright',
  'golf_top10',
  'golf_top20',
  'golf_make_cut',
  'golf_matchup',
]);

export function isModelRetired(modelId: string): boolean {
  return RETIRED_MODELS.has(modelId);
}

// Genuine in-play models, identified by their model_id rather than by the
// `is_live` column on a pick — because that COLUMN carries two different
// populations and only one of them is a live bet:
//   1. Real in-play picks written by the live scorers (mlb_live_*, ncaaf_live_*).
//   2. The session-114 repair rows: ~14k PRE-GAME prop picks retroactively
//      flagged is_live because they were scored against in-play prices after
//      first pitch. Those are contamination and must never reach a record.
// So "is this row a live bet?" is `is_live AND isLiveModel(model_id)`, and
// "should this row be excluded from a record?" is `is_live AND NOT
// isLiveModel(model_id)`. Mirrors the `model_id LIKE '%\_live\_%'` predicate in
// v_public_track_record / _daily (migration track_record_include_live_models),
// so the app and the DB views can never disagree about what counts.
export function isLiveModel(modelId: string): boolean {
  return modelId.includes('_live_');
}

// A pick that is flagged in-play but is NOT from a live model — i.e. a
// session-114 repair row. These are excluded from every record and total.
export function isContaminatedPregamePick(pick: {
  is_live?: boolean | null;
  model_id: string;
}): boolean {
  return pick.is_live === true && !isLiveModel(pick.model_id);
}

// Record-only models — their picks still grade and their W-L record is shown,
// but they NEVER count toward any displayed record, P&L, or ROI total. Mirrors
// the DB views: v_public_track_record excludes HR entirely (2026-07-04) and
// v_model_full_outcome_record forces units=0 / roi NULL for HR (2026-07-05).
// Rationale: most HR picks carry no real DK price, so counting them adds pure
// W-L drag with a fabricated -110 P&L.
// 2026-09-02: HR is RETIRED, and passesActionFilter refuses a retired model
// before this set is ever consulted — so no live model is record-only today.
// The mechanism stays for the next prob-only longshot market.
export const RECORD_ONLY_MODELS = new Set<string>(['mlb_prop_batter_hr']);

// A settled pick with NO book price contributes no money — no profit, no
// stake. Its W-L still counts. Settlement grades an unpriced pick at a -110
// that never existed (tracking/paper_tracker), so its profit_flat is
// fabricated: +$90.91 on a win nobody could have placed. The DB side already
// refuses that money — v_public_track_record / _daily keep the W-L and sum
// profit and stake over priced picks only (migration
// require_price_for_published_units, 2026-08-31) — and Discord's recap tallies
// it as record-only. Every app tally goes through here so the Models tab, the
// custom-model fallback and the daily recap can never price a pick the Record
// tab refuses to. Found on the UFC card, 2026-09-03: the Models tab summed 11
// unpriced picks and showed Total Rounds +13.0% on the same 8-5 the Record tab
// printed at -26.6%. config.REQUIRE_DK_PRICE stops new unpriced BETs; this
// covers the ones that already exist.
export function flatPnl(p: {
  dk_odds: number | null;
  profit_flat: number | null;
  decision_odds?: number | null;
}): {
  profit: number;
  staked: number;
} {
  // "Priced" means a price the pick was decided at; settlement fabricates
  // -110 only when there was none (decision_odds AND dk_odds both NULL).
  if (p.decision_odds == null && p.dk_odds == null) return { profit: 0, staked: 0 };
  return { profit: Number(p.profit_flat ?? 0), staked: 100 };
}

// Server-side Kelly fraction is computed as 0.10 × edge / (1 − implied), so
// pick.kelly_fraction reflects tenth-Kelly with the server's old 5% cap. The
// mobile client now lets the user scale this with a multiplier and apply an
// optional cap (see useKellySettings).
export const KELLY_MULTIPLIER = 0.10;

export interface KellySizingOpts {
  multiplier: number;     // 1.0 = tenth-Kelly (server default)
  cap: number | null;     // null = no cap; else max fraction of bankroll
}

// ── Server-driven thresholds ───────────────────────────────────────────────
// config.py is canonical; data/threshold_sync.py mirrors it into the
// model_action_thresholds table (run in the daily pipeline). The app fetches
// that table (useActionThresholds) into this module-level store, so threshold
// changes take effect on the next refresh with NO mobile rebuild. The bundled
// constants above (ACTION_THRESHOLDS / PAUSED_MODELS / PROB_ONLY_MODELS) are the
// OFFLINE FALLBACK used until the fetch succeeds.
export interface ServerThreshold {
  min_prob: number;
  min_edge: number;
  min_odds: number | null;
  prob_only: boolean;
  paused: boolean;
}

let serverThresholds: Record<string, ServerThreshold> | null = null;

/** Populate the server store (called by useActionThresholds). null = clear. */
export function setServerThresholds(map: Record<string, ServerThreshold> | null): void {
  serverThresholds = map;
}

/** True once server thresholds have loaded (else the bundled fallback is used). */
export function hasServerThresholds(): boolean {
  return serverThresholds != null;
}

/**
 * Whether a model is paused (never surfaced as an actionable pick, and hidden
 * from the Models list). Prefers the server flag (model_action_thresholds.paused),
 * falls back to the bundled PAUSED_MODELS set when not yet loaded / offline.
 */
export function isModelPaused(modelId: string): boolean {
  const sv = serverThresholds?.[modelId];
  if (sv) return sv.paused;
  return PAUSED_MODELS.has(modelId);
}

/** Resolved per-model action thresholds, preferring the server store; null for
 *  an unknown model. Used by the Sharp Score to normalize edge by the model's
 *  own bar. */
export interface ResolvedThreshold {
  min_prob: number;
  min_edge: number;
  min_odds: number | null;
  prob_only: boolean;
  paused: boolean;
}

export function thresholdFor(modelId: string): ResolvedThreshold | null {
  const sv = serverThresholds?.[modelId];
  if (sv) return { ...sv, min_odds: sv.min_odds ?? null };
  const t = ACTION_THRESHOLDS[modelId];
  if (!t) return null;
  return {
    min_prob: t.min_prob,
    min_edge: t.min_edge,
    min_odds: t.min_odds ?? null,
    prob_only: PROB_ONLY_MODELS.has(modelId),
    paused: PAUSED_MODELS.has(modelId),
  };
}

/** Price-floor gate (min_odds): a pick priced juicier than the model's floor
 *  (dk_odds more negative, e.g. -165 with a -140 floor) is not actionable.
 *  NULL dk_odds (prob-only fallback) always passes. */
function passesMinOdds(dkOdds: number | null | undefined, minOdds: number | null | undefined): boolean {
  if (minOdds == null || dkOdds == null) return true;
  return dkOdds >= minOdds;
}

// ── Unlocked look-ahead previews ─────────────────────────────────────────────
// UFC fights and GOLF tournaments are scored up to a week ahead, and those
// RETIRED 2026-08-28 — deliberately empty, so isUnlockedPreview() is always false.
//
// This encoded a misreading of the lock rule. It assumed UFC/golf look-ahead
// picks delete+rescore until a day-of lock, so a future-dated one was a
// "preview" rather than a signal. The rule is the opposite: the FIRST time the
// model crosses into a pick, that IS the bet of record — locked at that price,
// and never withdrawn if the line later moves out of range. A pick that can
// vanish cannot demonstrate closing-line value, which is the whole point of
// betting early.
//
// The scorer now locks UFC and golf at first cross like every other market
// (config.LOCK_GAME_PICKS_AT_FIRST_RUN), so no pick is ever an unlocked
// preview and every fired pick is a real signal.
//
// Left as an empty SEAM rather than ripped out, deliberately. Every call site
// (PickCard, PickDetailScreen, ReasoningCard, parlay.ts, lineMovementBoard.ts,
// PicksHomeScreen, BuiltInModelDetailScreen) reduces to a provable no-op while
// the set is empty, so the dead PREVIEW markup costs nothing but a re-added
// sport costs one line. verify_signal_counts.ts asserts the set is empty, so
// repopulating it fails the check and forces a revisit of those branches.
export const UNLOCKED_LOOKAHEAD_SPORTS = new Set<string>();

export function isUnlockedPreview(
  p: { sport: string; game_date: string },
  today: string = todayET(),
): boolean {
  return UNLOCKED_LOOKAHEAD_SPORTS.has(p.sport) && p.game_date > today;
}

export function passesActionFilter(p: ActionFilterable): boolean {
  if (p.signal_type !== 'BET') return false;
  // A VOIDED pick is not an action either (CLAUDE.md §1c). It is a row the
  // model should never have produced — fired outside its validated window, or
  // on a game that was never eligible — kept deliberately, because deleting it
  // would destroy the evidence of the bug that is usually how it was found.
  //
  // WHY THIS IS A PARITY FIX, not a display tweak (2026-09-09). The six Week 1
  // `nfl_wind_totals` picks were voided on 09-07 and REMOVED FROM DISCORD by
  // hand ("I deleted older wind picks from the discord and they should not be
  // stored as official picks"). Nothing carried that to the app, which has no
  // concept of condition_status at all, so all six were still drawing as green,
  // stakeable BETs for the 09-13 slate — the app and Discord showing different
  // picks, which is the one thing §1b says they must never do. The publishers
  // now apply the same exclusion in SQL.
  //
  // ONLY 'VOID'. The NFL pick monitor (scripts/nfl_pick_monitor.py) writes
  // 'OK' / 'DEGRADED' / 'GONE' in this column — health states on real, standing
  // picks, which stay bettable and stay counted. NCAAF does not write this
  // column at all; a downgraded NCAAF row carries `downgrade_reason`.
  if (p.condition_status === 'VOID') return false;
  // A retired model's old BETs are history, never an action. Checked before the
  // server store, whose row for a retired model outlives the model itself.
  if (RETIRED_MODELS.has(p.model_id)) return false;

  // Prefer the server-fed thresholds (model_action_thresholds, synced from
  // config.py); fall back to the bundled constants when not yet loaded / offline.
  // The cut is applied at the price the pick was DECIDED at (2026-09-09):
  // decision_* since the flip, DraftKings before it. Same clause the scorer,
  // the Discord and push producers and the record views apply.
  const odds = decisionOdds(p);
  const edge = decisionEdge(p);
  const sv = serverThresholds?.[p.model_id];
  if (sv) {
    if (sv.paused) return false;
    if (p.model_probability < sv.min_prob) return false;
    if (!passesMinOdds(odds, sv.min_odds)) return false;
    if (sv.prob_only) return true;
    return edge >= sv.min_edge;
  }

  if (PAUSED_MODELS.has(p.model_id)) return false;
  const t = ACTION_THRESHOLDS[p.model_id];
  if (!t) return false;
  if (p.model_probability < t.min_prob) return false;
  if (!passesMinOdds(odds, t.min_odds)) return false;
  if (PROB_ONLY_MODELS.has(p.model_id)) return true;
  return edge >= t.min_edge;
}

/** Effective fraction of bankroll after applying multiplier + user cap. */
export function effectiveKellyFraction(
  serverKellyFraction: number,
  opts: KellySizingOpts,
): number {
  const scaled = Math.max(0, serverKellyFraction * opts.multiplier);
  if (opts.cap != null) return Math.min(scaled, opts.cap);
  return scaled;
}

/**
 * Stake is expressed in UNITS, not dollars — and in TWO numbers, because one
 * cannot carry both conviction and price (Matt, 2026-08-28):
 *
 *   CONVICTION  1u..3u, "units to WIN". 3 is the highest-conviction play, 1 the
 *               lowest. The handicapper convention: a "1 unit play" means you
 *               are trying to win one unit, not risk one.
 *   RISK        what you lay to win that, from the price:
 *               risk = conviction / (decimal - 1). At -110 that is 1.1u to win
 *               1u; at +150, 0.67u to win 1u. Without this the same "2u" label
 *               meant wildly different money at -300 and at +200.
 *
 * The conviction scale is Kelly rescaled so the server's 5% Kelly cap lands on
 * exactly 3u — Kelly is still the ranking signal, only the denominator moved.
 *
 * RISK IS HARD-CAPPED AT MAX_RISK_UNITS ON ONE EVENT. Un-capped, "3 units to
 * win" at the median -135 lays 4.05u and 30% of the book would risk over 3u
 * (worst 6.5u), contradicting "never more than 3 units on 1 event". When the cap
 * binds, `win` is RECOMPUTED from the capped risk so the pair never disagrees:
 * a 3u play at -147 reads "risk 3u to win 2u", not a 3u win it would not pay.
 *
 * Unpriced picks (prob-only markets) cannot be grossed up: they carry the bare
 * conviction and `priced` is false. Their P&L still grades at the -110 fallback
 * settlement uses, but that is a GRADING convention and is deliberately not
 * asserted as a price on the card.
 *
 * Mirrors stake_for()/conviction_for() in tracking/discord_notifier.py — at the
 * default 1.00x aggressiveness the app and the Discord channel show the SAME
 * numbers, which is the point of publishing in units at all.
 *
 * Deliberately derived from kelly, never from bankroll: the compounded paper
 * bankroll has decayed to ~$107, so a dollar stake off it says nothing about
 * conviction.
 */
export const UNIT_KELLY_FRACTION = 0.01;  // legacy: 1u == 1% of roll
export const MAX_KELLY_FRACTION = 0.05;   // mirrors config.MAX_KELLY_FRACTION
export const MAX_CONVICTION = 3;          // ceiling of the (currently unused) tier scale
export const FLAT_CONVICTION = 1;        // every pick, until a tier survives a time split
export const MIN_CONVICTION = 1;          // lowest
export const MAX_RISK_UNITS = 3;          // never lay more than this on one event
const DEFAULT_UNITS = 1;                  // kelly absent/zero (prob-only picks)

export type UnitStake = {
  conviction: number;   // 1..3, units to win before the risk cap
  risk: number;         // units laid
  win: number;          // units returned on a win (recomputed if the cap bound)
  capped: boolean;      // the risk cap bound
  priced: boolean;      // a real book price was available
};

/** American -> decimal. null when there is no usable price. */
export function decimalOdds(american: number | null | undefined): number | null {
  const a = Number(american);
  if (!Number.isFinite(a) || a === 0) return null;
  return 1 + (a > 0 ? a / 100 : 100 / Math.abs(a));
}

/**
 * Conviction in UNITS TO WIN. Currently FLAT 1u for every pick.
 *
 * Mirrors tracking/discord_notifier.conviction_for -- the app and the channel
 * must publish the same number, and scripts/verify_units_parity.ts pins that.
 *
 * FLAT is an evidence decision, not a placeholder. The scale used to be Kelly
 * rescaled so the 5% cap landed on 3u; over 387 settled picks that sized UP
 * into the only losing bucket (highest-edge third: 50.4% win, -7.2% ROI, vs
 * +16.8% for the lowest). Inverting was rejected too -- on a time split the top
 * tier is +8.1% then -32.3%, i.e. unstable rather than reliably backwards, and
 * fitting a scale to 387 picks is the noise-fitting this repo has been burned
 * by before. Flat until a tier signal survives a time split.
 *
 * The user's aggressiveness multiplier still applies downstream in stakeFor,
 * so a bettor who wants to scale everything up or down still can.
 */
export function convictionFor(
  _serverKellyFraction: number | null | undefined,
  _opts: KellySizingOpts = { multiplier: 1, cap: null },
): number {
  return FLAT_CONVICTION;
}

/** Conviction plus the price-aware risk/win pair. See the block comment above. */
export function stakeFor(
  serverKellyFraction: number | null | undefined,
  dkOdds: number | null | undefined,
  opts: KellySizingOpts = { multiplier: 1, cap: null },
): UnitStake {
  const conviction = convictionFor(serverKellyFraction, opts);
  const dec = decimalOdds(dkOdds);
  if (dec == null || dec <= 1) {
    // No price to gross up against — publish the bare conviction.
    return { conviction, risk: conviction, win: conviction, capped: false, priced: false };
  }
  const risk = conviction / (dec - 1);
  if (risk > MAX_RISK_UNITS) {
    // Recompute the payout from the capped risk so the two never disagree.
    return {
      conviction,
      risk: MAX_RISK_UNITS,
      win: MAX_RISK_UNITS * (dec - 1),
      capped: true,
      priced: true,
    };
  }
  return { conviction, risk, win: conviction, capped: false, priced: true };
}

/**
 * Units LAID on a pick — what exposure sums should add up. Price-aware, so at
 * -110 a 1u-conviction play returns 1.1.
 */
export function unitsFor(
  serverKellyFraction: number | null | undefined,
  opts: KellySizingOpts = { multiplier: 1, cap: null },
  dkOdds: number | null | undefined = null,
): number {
  return stakeFor(serverKellyFraction, dkOdds, opts).risk;
}

/** "1.1u to win 1u"; just "1u" when the pick carries no price. */
export function formatStake(stake: UnitStake): string {
  if (!stake.priced) return formatUnits(stake.conviction);
  return `${formatUnits(stake.risk)} to win ${formatUnits(stake.win)}`;
}

/**
 * 2 -> "2u", 3.5 -> "3.5u", 1.15 -> "1.15u".
 *
 * TWO decimals, trailing zeros trimmed. One decimal used to round the -115
 * stake (1.15 laid to win 1) to "1.2u", which is a different bet from the one
 * the model asked for; every negative price divides out exactly at two
 * decimals, so this is the precision the number actually has.
 *
 * Rounds HALF-UP, explicitly. Neither language's default is safe: Python's %.2f
 * is half-to-EVEN while JS toFixed is half-up (0.125 renders "0.12" there and
 * "0.13" here), and a float like 2.0250000000000004 is not an integer, so a
 * naive isInteger check gives "2.00" on one side and "2" on the other. Trimming
 * splits on the decimal point rather than stripping trailing zeros off the whole
 * string, which would turn "20.00" into "2". The Python mirror uses the
 * identical expression; the parity fixture pins that they agree — it caught
 * exactly these divergences.
 */
export function formatUnits(u: number): string {
  const n = Math.floor(u * 100 + 0.5) / 100;
  const [whole, frac] = n.toFixed(2).split('.');
  const trimmed = frac.replace(/0+$/, '');
  return `${trimmed ? `${whole}.${trimmed}` : whole}u`;
}

/** Bet size in dollars. */
export function recommendedBet(
  serverKellyFraction: number,
  bankroll: number,
  opts: KellySizingOpts,
): number {
  const f = effectiveKellyFraction(serverKellyFraction, opts);
  return Math.round(f * bankroll * 100) / 100;
}
