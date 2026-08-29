/**
 * Mirror of config.py — ACTION_THRESHOLDS, PROB_ONLY_MODELS, KELLY constants.
 *
 * UPDATE THIS FILE whenever the Python config.py thresholds change.
 * Last synced: 2026-07-22 (-140 price floor now on EVERY MLB + WNBA player prop —
 * config.MODEL_MIN_ODDS. Prior: only pitcher_k / batter_rbi / batter_walks / runs).
 */

import { todayET } from './format';
import type { Pick as PickRow } from '@/types';

/**
 * The columns the action filter reads. Typed as a subset so it accepts both a
 * full Pick and the slimmer SettledPick the model screens cache.
 */
export type ActionFilterable = Pick<
  PickRow,
  'model_id' | 'model_probability' | 'edge' | 'dk_odds' | 'signal_type'
>;

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
  mlb_moneyline: { min_prob: 0.72, min_edge: 0.11 }, // 2026-07-04: reverted to v20260413 model; 21-6 +29.5% live at this cut
  mlb_over_under: { min_prob: 0.59, min_edge: 0.07 }, // 2026-07-11 tightened (fewer picks): 203 bets 60.4% +16.3% on 2025 OOS
  mlb_runline: { min_prob: 0.68, min_edge: 0.11 }, // 2026-07-02 CORRECTION: 06-28 "+14.9%" was a view sign bug (actually -20.6%); corrected optimum 13-6 +20.0%
  mlb_f5_moneyline: { min_prob: 0.67, min_edge: 0.07 }, // 2026-06-26 sweep: 0.67/0.07 = 105 bets 65.6% +9.86% (more picks + higher ROI)

  // Live (in-play) models — conservative placeholders; tune after 50+ settled live picks.
  // LIVE MLB, re-cut 2026-08-29 from the settled live record: total_runs is the
  // only profitable live model (0.68/0.14 = 17 bets 12-5 +27.9%); the two binary
  // models are negative at every cut and are PAUSED below.
  mlb_live_win_prob: { min_prob: 0.65, min_edge: 0.10 },   // PAUSED
  mlb_live_total_runs: { min_prob: 0.68, min_edge: 0.14 },
  mlb_live_runline: { min_prob: 0.65, min_edge: 0.10 },    // PAUSED

  // Pitcher props (2026-06-20 sweep; hits/walks have no winning cut → retraining)
  // min_odds -140: every MLB + WNBA prop now carries a -140 price floor (2026-07-22,
  // Matt: "don't recommend prop picks with a betting line over -140"). A prop priced
  // juicier than -140 scores NONE, not BET. See config.MODEL_MIN_ODDS.
  mlb_prop_pitcher_k: { min_prob: 0.71, min_edge: 0.06, min_odds: -140 },
  mlb_prop_pitcher_hits: { min_prob: 0.65, min_edge: 0.12, min_odds: -140 },
  mlb_prop_pitcher_er: { min_prob: 0.61, min_edge: 0.08, min_odds: -140 }, // 2026-06-21 ≥10% target: +11.1%/81
  mlb_prop_pitcher_outs: { min_prob: 0.50, min_edge: 0.12, min_odds: -140 },
  mlb_prop_pitcher_walks: { min_prob: 0.60, min_edge: 0.08, min_odds: -140 },

  // Batter props (2026-06-20 sweep; hr/sb have no winning cut)
  mlb_prop_batter_hits: { min_prob: 0.78, min_edge: 0.17, min_odds: -140 }, // 2026-06-28 full-outcome: 77 bets +8.3% (UNPAUSED)
  mlb_prop_batter_tb: { min_prob: 0.83, min_edge: 0.17, min_odds: -140 },
  mlb_prop_batter_hr: { min_prob: 0.225, min_edge: 0.0, min_odds: -140 }, // prob-only plus-money — floor never blocks; 2026-06-26 stricter cut
  mlb_prop_batter_rbi: { min_prob: 0.47, min_edge: 0.16, min_odds: -140 }, // 2026-06-21 cut + -140 floor: capped +7.3%/36
  mlb_prop_batter_runs: { min_prob: 0.47, min_edge: 0.16, min_odds: -140 }, // UNPAUSED 2026-08-09; with the floor this cut grades +24.6%/40
  mlb_prop_batter_sb: { min_prob: 0.18, min_edge: 0.10, min_odds: -140 },
  mlb_prop_batter_walks: { min_prob: 0.45, min_edge: 0.14, min_odds: -140 }, // 2026-06-21 RE-SWEEP: +5.3%/65

  // WNBA — placeholder thresholds; retune after the 2025 holdout backtest sweep.
  wnba_moneyline: { min_prob: 0.64, min_edge: 0.04 }, // 2026-07-02 sweep: 17 bets 14-3 +31.9% (old placeholder fired 3 bets)
  wnba_over_under: { min_prob: 0.60, min_edge: 0.06 }, // 2026-07-19 first real cut — 2026 OOS vs real DK lines: 23 bets 60.9% +14.5%
  wnba_spread: { min_prob: 0.60, min_edge: 0.10 }, // 2026-07-19 first real cut — 2026 OOS: 34 bets 64.7% +22.6%
  // WNBA props — re-optimized 2026-06-20 (thin 15-40 bet samples since June 1; will regress); -140 floor 2026-07-22
  wnba_prop_player_points: { min_prob: 0.58, min_edge: 0.17, min_odds: -140 }, // PAUSED 2026-07-11 — no positive cut on the 2x sample
  wnba_prop_player_rebounds: { min_prob: 0.69, min_edge: 0.08, min_odds: -140 }, // 2026-07-11 re-sweep: KEPT — grid ROI max (+5.6%/78)
  wnba_prop_player_assists: { min_prob: 0.69, min_edge: 0.08, min_odds: -140 }, // 2026-07-11 re-sweep: KEPT — ROI max (+19.3%/44)
  wnba_prop_player_threes: { min_prob: 0.64, min_edge: 0.12, min_odds: -140 }, // PAUSED 2026-07-11 — no winning cut
  wnba_prop_player_pra: { min_prob: 0.67, min_edge: 0.16, min_odds: -140 }, // PAUSED 2026-07-11 — no winning cut

  // NBA — placeholder thresholds; tune after live odds accumulate.
  // nba_prop_player_dd is prob-only (DK juices double-double Yes/No).
  nba_moneyline: { min_prob: 0.66, min_edge: 0.12 },
  nba_over_under: { min_prob: 0.66, min_edge: 0.12 },
  nba_spread: { min_prob: 0.66, min_edge: 0.12 },
  nba_prop_player_points: { min_prob: 0.60, min_edge: 0.08 },
  nba_prop_player_rebounds: { min_prob: 0.60, min_edge: 0.08 },
  nba_prop_player_assists: { min_prob: 0.60, min_edge: 0.08 },
  nba_prop_player_threes: { min_prob: 0.60, min_edge: 0.08 },
  nba_prop_player_pra: { min_prob: 0.60, min_edge: 0.08 },
  nba_prop_player_blocks: { min_prob: 0.60, min_edge: 0.08 },
  nba_prop_player_steals: { min_prob: 0.60, min_edge: 0.08 },
  nba_prop_player_turnovers: { min_prob: 0.60, min_edge: 0.08 },
  nba_prop_player_dd: { min_prob: 0.55, min_edge: 0.0 }, // prob-only

  // UFC — placeholder thresholds; tune after 50+ settled picks.
  // ufc_method_of_victory is prob-only (no DK method odds via The Odds API).
  ufc_moneyline: { min_prob: 0.65, min_edge: 0.08 },
  ufc_total_rounds: { min_prob: 0.62, min_edge: 0.08 },
  ufc_method_of_victory: { min_prob: 0.65, min_edge: 0.0 }, // prob-only

  // NHL — placeholder thresholds; tune after 50+ settled picks.
  // moneyline_regulation is a 3-way market (lower per-side prob).
  nhl_moneyline: { min_prob: 0.55, min_edge: 0.05 },
  nhl_moneyline_regulation: { min_prob: 0.40, min_edge: 0.05 },
  nhl_over_under: { min_prob: 0.55, min_edge: 0.05 },
  nhl_puckline: { min_prob: 0.55, min_edge: 0.05 },

  // NCAAF — ncaaf_spread is a MARGIN-REGRESSION model. min_prob is the
  // out-of-sample residual-ECDF probability at the validated +/-5.5-point
  // disagreement gate, so the prob floor IS the gate; edge floor is 0.0 on
  // purpose (the validated rule is the disagreement, not a price filter).
  // PAPER ONLY until 50+ settled picks clear the go-live gate.
  // 0.55 floors the opener rule's flat validated prob (0.5810); the real
  // filter is the |dev| >= 1.0 gate enforced server-side.
  ncaaf_spread: { min_prob: 0.55, min_edge: 0.0 },
  // Premium opener band [2.5, inf): 344 bets, 60.5%, +15.4% (2023-25,
  // positive every season). Disjoint from ncaaf_spread by construction.
  ncaaf_spread_premium: { min_prob: 0.58, min_edge: 0.0 },
  // NCAAF live lanes (calibration set — no in-play edge measured yet)
  ncaaf_live_win_prob: { min_prob: 0.58, min_edge: 0.1 },
  ncaaf_live_total: { min_prob: 0.62, min_edge: 0.08 },
  // Paused (see PAUSED_MODELS) — cuts kept so unpausing is one edit.
  ncaaf_moneyline: { min_prob: 0.62, min_edge: 0.08 },
  // 0.65 = P(over) at the validated +/-8.0 gate; the server enforces the
  // symmetric gate itself, so this floor is a backstop rather than the rule.
  ncaaf_over_under: { min_prob: 0.65, min_edge: 0.0 },

  // NFL — the standalone wind-totals card (§28). The card itself is the real
  // gate (forecast wind >= 11mph + >= 3% edge after de-vig); these floors just
  // mirror it so a card-qualified pick can never be hidden by the filter.
  nfl_wind_totals: { min_prob: 0.52, min_edge: 0.03 },
  // Opener: model_prob is the pooled validated ATS (0.5818) — 0.52 floors it;
  // edge >= 0 drops bets whose quoted juice eats the whole edge.
  nfl_opener_spread: { min_prob: 0.52, min_edge: 0.0 },

  // NFL props — trained 2026-08-23, ALL PAUSED (see PAUSED_MODELS below).
  // Listed anyway so the offline / first-launch fallback knows their cuts.
  // A model ABSENT from this map is invisible to passesActionFilter, so if
  // one were unpaused server-side it would stay hidden in the app until
  // model_action_thresholds had been fetched.
  nfl_prop_anytime_td: { min_prob: 0.3, min_edge: 0.05 },
  nfl_prop_pass_attempts: { min_prob: 0.55, min_edge: 0.05 },
  nfl_prop_pass_completions: { min_prob: 0.55, min_edge: 0.05 },
  nfl_prop_pass_tds: { min_prob: 0.55, min_edge: 0.05 },
  nfl_prop_pass_yards: { min_prob: 0.55, min_edge: 0.05 },
  nfl_prop_rec_yards: { min_prob: 0.55, min_edge: 0.05 },
  nfl_prop_receptions: { min_prob: 0.55, min_edge: 0.05 },
  nfl_prop_rush_attempts: { min_prob: 0.55, min_edge: 0.05 },
  nfl_prop_rush_rec_yards: { min_prob: 0.55, min_edge: 0.05 },
  nfl_prop_rush_yards: { min_prob: 0.55, min_edge: 0.05 },
  nfl_prop_sacks: { min_prob: 0.55, min_edge: 0.05 },
  nfl_prop_tackles_assists: { min_prob: 0.55, min_edge: 0.05 },
  // Market-relative props: model_prob is Pinnacle's DE-VIGGED number, which is
  // near 0.5 by construction, so a probability floor would cut the rule's core.
  // The edge is the whole signal, and 5pp is pre-committed (6pp wins in
  // training and returns -0.46% blind). See docs/nfl_props_model.md §5c.
  nfl_prop_market: { min_prob: 0.0, min_edge: 0.05 },

  // GOLF — placeholder thresholds on a market-relative prob scale (win ~3%,
  // top-N ~15-25%, make-cut ~65%). Tune after 50+ settled picks per model.
  golf_outright: { min_prob: 0.03, min_edge: 0.015 },
  golf_top10: { min_prob: 0.15, min_edge: 0.05 },
  golf_top20: { min_prob: 0.25, min_edge: 0.05 },
  golf_make_cut: { min_prob: 0.65, min_edge: 0.05 },
  golf_matchup: { min_prob: 0.55, min_edge: 0.05 },
};

export const PROB_ONLY_MODELS = new Set<string>([
  'mlb_prop_batter_hr',
  'ufc_method_of_victory',
  'nba_prop_player_dd',
]);

// Mirror of config.py PAUSED_MODELS — models that never fire a BET (paused for
// poor performance). Excluded from the action filter so they don't appear as
// actionable picks anywhere in the app.
export const PAUSED_MODELS = new Set<string>([
  // Live MLB binary models — no profitable cut at any volume (2026-08-29).
  'mlb_live_win_prob',
  'mlb_live_runline',
  // 2026-06-28 full-outcome re-sweep: only these 4 have NO positive cut at real
  // volume (retrain candidates). The other 4 (pitcher_walks/batter_walks/
  // batter_hits/batter_runs) had genuine positive combos and were UNPAUSED.
  // Server store (model_action_thresholds.paused) is authoritative; this bundled
  // list is the offline fallback. Still score as NONE for forward tracking.
  'mlb_prop_pitcher_hits',
  'mlb_prop_pitcher_outs',
  // 2026-07-11 PAUSED (Matt) — pitcher ER + walks removed from display/consideration for now.
  'mlb_prop_pitcher_er',
  'mlb_prop_pitcher_walks',
  'mlb_prop_batter_tb',
  'mlb_prop_batter_sb',
  // mlb_prop_batter_runs UNPAUSED 2026-08-09 — 0.47/0.16 + -140 floor grades +24.6%/40
  // WNBA points/threes/PRA PAUSED 2026-07-11 — no positive cut at volume on the doubled
  // sample (-11.8u combined drag).
  // NCAAF 2026-08-24: the binary classifiers held out at AUC ~0.49-0.50 on a
  // healthy 6,000+-row matrix, and the margin-regression harness also FAILED
  // for totals. Their registry rows may still carry active classifier
  // artifacts, so pause both — only ncaaf_spread (margin regression) is live.
  'ncaaf_moneyline',
  // ncaaf_over_under UNPAUSED 2026-08-25 — now a total-regression rule
  // (>= 8.0 pts of disagreement with DK's total), walk-forward 295/528 55.9%
  // +6.7% with that gate best in all four test seasons. CI does not clear
  // breakeven; sized small deliberately.
  // ncaaf_spread UNPAUSED 2026-08-26 — replaced with a CROSS-BOOK OPENER rule
  // (back the side Bovada's opener favours, at DK's stale number). Backtest
  // 1,050 bets 58.1% +10.9%, CLV 0.694. The server enforces simultaneity of
  // the two openers and that DK is still on its opening number, so the rule
  // self-disables when it would be untradeable.
  'wnba_prop_player_points',
  'wnba_prop_player_threes',
  'wnba_prop_player_pra',
  // wnba_prop_player_rebounds PAUSED 2026-07-29 — decayed to -13.9%/54 bets at the
  // live 0.69/0.08 cut and EVERY cell of the prob x edge sweep is negative
  // (-9.1% to -23.7%). Side-structural: overs -44%..-53%, unders ~flat. Needs
  // opponent-defense / minutes features, not a re-cut. Assists stays live.
  'wnba_prop_player_rebounds',
  // wnba_over_under + wnba_spread PAUSED 2026-07-29 — UNVALIDATED, not proven bad.
  // Their launch cuts came from a 2026 sweep whose bulk odds loader took the latest
  // snapshot with no pre-tipoff cutoff, so 67% of games were featurized with a line
  // that had already drifted toward the final score (avg leak 8.2 pts on totals).
  // With honest pre-game lines the O/U model never reaches its own 0.60 bar (0 BETs
  // in 17 games) and the spread is 2-2/-3.7%. Leak fixed in feature_engine; unpause
  // only after scripts/wnba_line_sweep.py re-derives cuts on clean lines.
  'wnba_over_under',
  'wnba_spread',
  // mlb_over_under RE-PAUSED 2026-07-14 (Matt: "total runs model is 3-8"). The
  // under-skew watch item materialized — honest-era live record 3-8/-529u, and the
  // model's mean P(over) 0.454 vs a realized 0.500 / 9.32-run summer environment
  // (active model never trained on July data). Retraining w/ settled July games;
  // paused meanwhile. UNPAUSE after retrain + a fresh 2025 OOS threshold sweep.
  'mlb_over_under',
  // mlb_prop_batter_hr UNPAUSED 2026-06-20 — the -66.6% was a -110-settlement
  // artifact (DK HR odds weren't ingested; now sourced from batter_home_runs_alternate).
  // Kept live + +EV-filtered when priced.

  // NFL props: trained 2026-08-23, none live.
  'nfl_prop_anytime_td',
  'nfl_prop_pass_attempts',
  'nfl_prop_pass_completions',
  'nfl_prop_pass_tds',
  'nfl_prop_pass_yards',
  'nfl_prop_rec_yards',
  'nfl_prop_receptions',
  'nfl_prop_rush_attempts',
  'nfl_prop_rush_rec_yards',
  'nfl_prop_rush_yards',
  'nfl_prop_sacks',
  'nfl_prop_tackles_assists',
]);

// Record-only models — their picks still grade and their W-L record is shown,
// but they NEVER count toward any displayed record, P&L, or ROI total. Mirrors
// the DB views: v_public_track_record excludes HR entirely (2026-07-04) and
// v_model_full_outcome_record forces units=0 / roi NULL for HR (2026-07-05).
// Rationale: most HR picks carry no real DK price, so counting them adds pure
// W-L drag with a fabricated -110 P&L.
export const RECORD_ONLY_MODELS = new Set<string>(['mlb_prop_batter_hr']);

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

  // Prefer the server-fed thresholds (model_action_thresholds, synced from
  // config.py); fall back to the bundled constants when not yet loaded / offline.
  const sv = serverThresholds?.[p.model_id];
  if (sv) {
    if (sv.paused) return false;
    if (p.model_probability < sv.min_prob) return false;
    if (!passesMinOdds(p.dk_odds, sv.min_odds)) return false;
    if (sv.prob_only) return true;
    return p.edge >= sv.min_edge;
  }

  if (PAUSED_MODELS.has(p.model_id)) return false;
  const t = ACTION_THRESHOLDS[p.model_id];
  if (!t) return false;
  if (p.model_probability < t.min_prob) return false;
  if (!passesMinOdds(p.dk_odds, t.min_odds)) return false;
  if (PROB_ONLY_MODELS.has(p.model_id)) return true;
  return p.edge >= t.min_edge;
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
 * 2 -> "2u", 3.5 -> "3.5u", 1.1 -> "1.1u".
 *
 * Rounds HALF-UP at one decimal, explicitly. Neither language's default is safe:
 * Python's %.1f is half-to-EVEN while JS toFixed is half-up (0.25 renders "0.2"
 * there and "0.3" here), and a float like 2.0250000000000004 is not an integer,
 * so a naive isInteger check gives "2.0" on one side and "2" on the other. The
 * Python mirror uses the identical expression; the parity fixture pins that they
 * agree — it caught exactly these two divergences.
 */
export function formatUnits(u: number): string {
  const n = Math.floor(u * 10 + 0.5) / 10;
  return `${Number.isInteger(n) ? String(n) : n.toFixed(1)}u`;
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
