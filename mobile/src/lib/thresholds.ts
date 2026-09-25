/**
 * Mirror of config.py — ACTION_THRESHOLDS, PAUSED_MODELS, PROB_ONLY_MODELS, KELLY.
 *
 * DATA is generated from config.py into `./thresholds.generated` by
 * `python -m scripts.generate_mobile_thresholds`. Do not hand-edit the
 * numbers: change config.py, regenerate, and let
 * tests/test_mobile_threshold_parity.py + CI `--check` catch drift.
 *
 * WHY IT MATTERS even though the server store wins: `thresholdFor` and
 * `isModelPaused` consult `model_action_thresholds` PER MODEL ID and fall
 * through to these constants whenever it has not been fetched yet or has no
 * row for that id — so every cold start renders its first board from here.
 */

import { decisionEdge, decisionOdds } from './decisionPrice';
import { discordLedVisible, type DiscordPublish } from './discordPublish';
import { todayET } from './format';
import type { Pick as PickRow } from '@/types';

import {
  ACTION_THRESHOLDS,
  PAUSED_MODELS,
  PROB_ONLY_MODELS,
  RETIRED_PROB_ONLY_MODELS,
  RETIRED_MODELS,
  KELLY_MULTIPLIER,
  MAX_KELLY_FRACTION,
} from './thresholds.generated';
export type { ModelThreshold } from './thresholds.generated';
// `export { X } from` re-exports without binding X in this module, so
// isProbOnlyModel / thresholdFor / etc. cannot see the names (TS2304).
export {
  ACTION_THRESHOLDS,
  PAUSED_MODELS,
  PROB_ONLY_MODELS,
  RETIRED_PROB_ONLY_MODELS,
  RETIRED_MODELS,
  KELLY_MULTIPLIER,
  MAX_KELLY_FRACTION,
};

/**
 * The columns the action filter reads. Typed as a subset so it accepts both a
 * full Pick and the slimmer SettledPick the model screens cache.
 */
export type ActionFilterable = Pick<
  PickRow,
  'model_id' | 'model_probability' | 'edge' | 'dk_odds' | 'signal_type'
  | 'condition_status'
> & {
  decision_odds?: number | null;
  decision_edge?: number | null;
  /** Set by attachDiscordPublish. Omitted means the ledger was not read. */
  discordPublish?: DiscordPublish;
};

export function isProbOnlyModel(modelId: string): boolean {
  return PROB_ONLY_MODELS.has(modelId) || RETIRED_PROB_ONLY_MODELS.has(modelId);
}


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
// pick.kelly_fraction reflects tenth-Kelly. It is the RANKING signal only —
// nothing in the app turns it into a stake any more. Sizing is flat units
// (see convictionFor / stakeFor below), identical for every viewer, which is
// why there is no bankroll and no per-user aggressiveness knob to thread.

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
  // DISPLAY FOLLOWS DISCORD (Matt, 2026-09-23). A VOID the channel still has
  // stays a bet — the post is not retracted. A bet the channel does not have
  // is not an active Discord-led bet. Publishers still refuse to ANNOUNCE a
  // VOID; this is only what the board draws. The settled record is
  // passesRecordFilter, which still excludes every VOID.
  //
  // ONLY 'VOID' is special. The NFL pick monitor writes 'OK' / 'DEGRADED' /
  // 'GONE' as health states on real, standing picks. NCAAF does not write
  // this column; a downgraded NCAAF row carries `downgrade_reason`.
  //
  // discordPublish omitted (`unknown`) keeps a non-VOID bet visible, so a
  // ledger read that has not landed yet cannot blank the board. A VOID with
  // no evidence it is on Discord stays hidden.
  if (!discordLedVisible(p.condition_status, p.discordPublish)) return false;
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

/**
 * THE RECORD FILTER — what a model HAS bet, as opposed to what it may bet next.
 *
 * A settled pick belongs to the record because it was written as a BET: it
 * cleared its model's cut on the day, at the price available then. Nothing
 * about the model's present state may take that back — not a pause, not a
 * threshold change, not a retrain.
 *
 * mike, 2026-09-12: "Pausing a model should not erase settled record unless I
 * explicitly say so ... Do not do it unless I explicitly say so." On the
 * morning of 2026-09-12 the published NCAAF record went from 27-25 over 52
 * settled picks to 0-3 over 3, because two NCAAF live lanes had been paused the
 * evening before and every record surface re-applied `paused` to settled rows.
 *
 * A settled pick leaves the record by exactly two deliberate acts: a VOID,
 * checked here, and an entry in config.RECORD_EXCLUSIONS, which is enforced
 * SERVER-SIDE in v_public_track_record and is unreachable from the app (its
 * only entry predates the published window). Model state is checked nowhere.
 *
 * Use passesActionFilter instead for anything the reader could still BET —
 * there a paused model must not be offered. The two filters answering two
 * questions is the point; one filter answering both is the bug.
 */
export type RecordFilterable = Pick<
  PickRow,
  'model_id' | 'signal_type' | 'condition_status' | 'is_live'
>;

export function passesRecordFilter(p: RecordFilterable): boolean {
  if (p.signal_type !== 'BET') return false;
  // A VOIDed pick is not a bet of record (CLAUDE.md 1c). Server-side the same
  // exclusion happens via result='NO_ACTION'.
  if (p.condition_status === 'VOID') return false;
  // A pre-game model's in-play pick does not count; a dedicated live lane does.
  // Pre-game and in-play prices never mix (CLAUDE.md 6). Same helper the rest
  // of the record path uses, so this cannot drift from the DB views.
  if (isContaminatedPregamePick(p)) return false;
  return true;
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
 * Mirrors stake_for()/conviction_for() in tracking/discord_notifier.py — the
 * app and the Discord channel show the SAME numbers, which is the point of
 * publishing in units at all. Nothing here is per-user, so they cannot drift.
 *
 * Deliberately derived from kelly, never from bankroll: the compounded paper
 * bankroll has decayed to ~$107, so a dollar stake off it says nothing about
 * conviction. The app holds no bankroll at all now (2026-09-20) — results are
 * always in units (CLAUDE.md §4).
 */
export const UNIT_KELLY_FRACTION = 0.01;  // legacy: 1u == 1% of roll
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
 * There is no per-user scaling: the app, Discord and push publish the SAME
 * stake, so a knob that moved one of them would break that parity silently.
 */
export function convictionFor(
  _serverKellyFraction: number | null | undefined,
): number {
  return FLAT_CONVICTION;
}

/** Conviction plus the price-aware risk/win pair. See the block comment above. */
export function stakeFor(
  serverKellyFraction: number | null | undefined,
  dkOdds: number | null | undefined,
): UnitStake {
  const conviction = convictionFor(serverKellyFraction);
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
  dkOdds: number | null | undefined = null,
): number {
  return stakeFor(serverKellyFraction, dkOdds).risk;
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
