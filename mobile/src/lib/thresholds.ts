/**
 * Mirror of config.py — ACTION_THRESHOLDS, PROB_ONLY_MODELS, KELLY constants.
 *
 * UPDATE THIS FILE whenever the Python config.py thresholds change.
 * Last synced: 2026-07-11 (adds min_odds price floors — config.MODEL_MIN_ODDS:
 * -140 on pitcher_k / batter_rbi / batter_walks / batter_runs).
 */

import type { Pick } from '@/types';

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
  mlb_live_win_prob: { min_prob: 0.65, min_edge: 0.10 },
  mlb_live_total_runs: { min_prob: 0.65, min_edge: 0.10 },
  mlb_live_runline: { min_prob: 0.65, min_edge: 0.10 },

  // Pitcher props (2026-06-20 sweep; hits/walks have no winning cut → retraining)
  // min_odds -140 (2026-07-11): price floor — these models' juice-heavy tail bled;
  // capped slices beat the uncapped record (pitcher_k +8.9%→+20.3%, rbi +2.2%→+7.3%,
  // batter_walks +2.5%→+37%, batter_runs +3.1%→+24.6%). See config.MODEL_MIN_ODDS.
  mlb_prop_pitcher_k: { min_prob: 0.71, min_edge: 0.06, min_odds: -140 },
  mlb_prop_pitcher_hits: { min_prob: 0.65, min_edge: 0.12 },
  mlb_prop_pitcher_er: { min_prob: 0.61, min_edge: 0.08 }, // 2026-06-21 ≥10% target: +11.1%/81
  mlb_prop_pitcher_outs: { min_prob: 0.50, min_edge: 0.12 },
  mlb_prop_pitcher_walks: { min_prob: 0.60, min_edge: 0.08 },

  // Batter props (2026-06-20 sweep; hr/sb have no winning cut)
  mlb_prop_batter_hits: { min_prob: 0.78, min_edge: 0.17 }, // 2026-06-28 full-outcome: 77 bets +8.3% (UNPAUSED)
  mlb_prop_batter_tb: { min_prob: 0.83, min_edge: 0.17 },
  mlb_prop_batter_hr: { min_prob: 0.225, min_edge: 0.0 }, // prob-only; 2026-06-26 stricter (best-record cut, ~66% fewer picks)
  mlb_prop_batter_rbi: { min_prob: 0.47, min_edge: 0.16, min_odds: -140 }, // 2026-06-21 cut + -140 floor: capped +7.3%/36
  mlb_prop_batter_runs: { min_prob: 0.47, min_edge: 0.16, min_odds: -140 }, // PAUSED; with the floor this cut grades +24.6%/40 (unpause candidate, declined)
  mlb_prop_batter_sb: { min_prob: 0.18, min_edge: 0.10 },
  mlb_prop_batter_walks: { min_prob: 0.45, min_edge: 0.14, min_odds: -140 }, // 2026-06-21 RE-SWEEP: +5.3%/65; -140 floor 2026-07-11

  // WNBA — placeholder thresholds; retune after the 2025 holdout backtest sweep.
  wnba_moneyline: { min_prob: 0.64, min_edge: 0.04 }, // 2026-07-02 sweep: 17 bets 14-3 +31.9% (old placeholder fired 3 bets)
  wnba_over_under: { min_prob: 0.60, min_edge: 0.06 }, // 2026-07-19 first real cut — 2026 OOS vs real DK lines: 23 bets 60.9% +14.5%
  wnba_spread: { min_prob: 0.60, min_edge: 0.10 }, // 2026-07-19 first real cut — 2026 OOS: 34 bets 64.7% +22.6%
  // WNBA props — re-optimized 2026-06-20 (thin 15-40 bet samples since June 1; will regress)
  wnba_prop_player_points: { min_prob: 0.58, min_edge: 0.17 }, // PAUSED 2026-07-11 — no positive cut on the 2x sample
  wnba_prop_player_rebounds: { min_prob: 0.69, min_edge: 0.08 }, // 2026-07-11 re-sweep: KEPT — grid ROI max (+5.6%/78)
  wnba_prop_player_assists: { min_prob: 0.69, min_edge: 0.08 }, // 2026-07-11 re-sweep: KEPT — ROI max (+19.3%/44)
  wnba_prop_player_threes: { min_prob: 0.64, min_edge: 0.12 }, // PAUSED 2026-07-11 — no winning cut
  wnba_prop_player_pra: { min_prob: 0.67, min_edge: 0.16 }, // PAUSED 2026-07-11 — no winning cut

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
  'mlb_prop_batter_runs', // with the -140 floor grades +24.6%/40 — unpause candidate, declined 2026-07-11 (no volume bets)
  // WNBA points/threes/PRA PAUSED 2026-07-11 — no positive cut at volume on the doubled
  // sample (-11.8u combined drag); rebounds + assists stay live.
  'wnba_prop_player_points',
  'wnba_prop_player_threes',
  'wnba_prop_player_pra',
  // mlb_over_under RE-PAUSED 2026-07-14 (Matt: "total runs model is 3-8"). The
  // under-skew watch item materialized — honest-era live record 3-8/-529u, and the
  // model's mean P(over) 0.454 vs a realized 0.500 / 9.32-run summer environment
  // (active model never trained on July data). Retraining w/ settled July games;
  // paused meanwhile. UNPAUSE after retrain + a fresh 2025 OOS threshold sweep.
  'mlb_over_under',
  // mlb_prop_batter_hr UNPAUSED 2026-06-20 — the -66.6% was a -110-settlement
  // artifact (DK HR odds weren't ingested; now sourced from batter_home_runs_alternate).
  // Kept live + +EV-filtered when priced.
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

export function passesActionFilter(p: Pick): boolean {
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

/** Bet size in dollars. */
export function recommendedBet(
  serverKellyFraction: number,
  bankroll: number,
  opts: KellySizingOpts,
): number {
  const f = effectiveKellyFraction(serverKellyFraction, opts);
  return Math.round(f * bankroll * 100) / 100;
}
