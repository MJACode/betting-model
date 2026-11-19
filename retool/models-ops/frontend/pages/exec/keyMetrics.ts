// Types and the pure arithmetic for the Key Metrics tab. Every figure arrives
// from backend/ops/getKeyMetrics.ts, which reads the record's own views; this
// file only adds up, windows and formats them.

import { verdictOf, type Verdict } from '../health/healthUtils'

export type DailyRow = { game_date: string; bets: number; units: number; risked: number }

export type ClvRow = {
  measured: number
  beat: number
  matched: number
  trailed: number
  beat_price: number
  beat_line: number
  matched_price: number
  trailed_price: number
  trailed_line: number
  avg_clv_pct: number | null
  pin_n: number
  pin_beat: number
  pin_avg_pct: number | null
  in_play: number
  no_close: number
  bets: number
}

export type ModelRow = {
  model_id: string
  sport: string
  bets: number
  wins: number
  losses: number
  pushes: number
  units: number
  risked: number
  in_play: number
  price_n: number
  avg_clv_pct: number | null
  se_clv_pct: number | null
}

export type CountsRow = { live: number; paused: number; today_et: string }
export type PipelineRow = { started_at: string; finished_at: string | null; ok: boolean | null; steps_failed: number | null; failed_steps: string | null }
export type CheckRow = { run_date: string; ok: number; skipped: number; problems: number; problem_names: string | null }
export type CreditsRow = { remaining: number | null; observed_at: string | null; median_burn: number | null; burn_days: number }

export type KeyMetrics = {
  daily: DailyRow[]
  clv: ClvRow | null
  models: ModelRow[]
  counts: CountsRow | null
  pipeline: PipelineRow | null
  checks: CheckRow | null
  credits: CreditsRow | null
}

/** Days of credits the purchase script keeps in reserve (scripts/clv_close_history.py RESERVE_DAYS). */
export const CREDIT_RESERVE_DAYS = 3

export function n(v: unknown): number {
  const x = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(x) ? x : 0
}

export function nOrNull(v: unknown): number | null {
  if (v == null || v === '') return null
  const x = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(x) ? x : null
}

export function roiPct(units: number, risked: number): number | null {
  return risked > 0 ? (units / risked) * 100 : null
}

export type Totals = { bets: number; wins: number; losses: number; pushes: number; units: number; risked: number; roi: number | null; hitRate: number | null }

/** The published record's totals: the sum of the per-model rows. */
export function totalsOf(models: ModelRow[]): Totals {
  let bets = 0, wins = 0, losses = 0, pushes = 0, units = 0, risked = 0
  for (const m of models) {
    bets += n(m.bets); wins += n(m.wins); losses += n(m.losses); pushes += n(m.pushes)
    units += n(m.units); risked += n(m.risked)
  }
  const decided = wins + losses
  return { bets, wins, losses, pushes, units, risked, roi: roiPct(units, risked), hitRate: decided > 0 ? wins / decided : null }
}

/** YYYY-MM-DD, `days` before an ET date string. */
export function daysBefore(isoDate: string, days: number): string {
  const d = new Date(isoDate + 'T00:00:00Z')
  d.setUTCDate(d.getUTCDate() - days)
  return d.toISOString().slice(0, 10)
}

export type WindowTotals = { bets: number; units: number; risked: number; roi: number | null; days: number }

/** The `days` game dates ending today (ET): game_date > today - days. */
export function windowOf(daily: DailyRow[], todayEt: string, days: number): WindowTotals {
  const after = daysBefore(todayEt, days)
  let bets = 0, units = 0, risked = 0
  for (const d of daily) {
    if (d.game_date > after && d.game_date <= todayEt) {
      bets += n(d.bets); units += n(d.units); risked += n(d.risked)
    }
  }
  return { bets, units, risked, roi: roiPct(units, risked), days }
}

export type EquityPoint = { date: string; day: number; bets: number; cum: number; peak: number; below: number }

export type Equity = {
  points: EquityPoint[]
  maxDrop: number
  maxDropFrom: string | null
  maxDropTo: string | null
  belowNow: number
  peakDate: string | null
}

/**
 * Cumulative units by game date, with the deepest fall from a previous high.
 * By day, not by bet: a drop inside one day is not seen.
 */
export function equityOf(daily: DailyRow[]): Equity {
  const points: EquityPoint[] = []
  let cum = 0, peak = 0
  let peakDate: string | null = null
  let maxDrop = 0
  let maxDropFrom: string | null = null
  let maxDropTo: string | null = null
  for (const d of [...daily].sort((a, b) => a.game_date.localeCompare(b.game_date))) {
    cum += n(d.units)
    if (cum > peak) { peak = cum; peakDate = d.game_date }
    const below = peak - cum
    if (below > maxDrop) { maxDrop = below; maxDropFrom = peakDate; maxDropTo = d.game_date }
    points.push({ date: d.game_date, day: n(d.units), bets: n(d.bets), cum, peak, below })
  }
  const last = points[points.length - 1]
  return { points, maxDrop, maxDropFrom, maxDropTo, belowNow: last ? last.below : 0, peakDate }
}

export type ModelView = ModelRow & { verdict: Verdict; roi: number | null }

export function modelViews(models: ModelRow[]): ModelView[] {
  return models.map(m => {
    const inPlayOnly = n(m.in_play) === n(m.bets) && n(m.bets) > 0
    return {
      ...m,
      verdict: verdictOf(nOrNull(m.avg_clv_pct), nOrNull(m.se_clv_pct), n(m.price_n), inPlayOnly),
      roi: roiPct(n(m.units), n(m.risked)),
    }
  })
}

export type ModelBuckets = { withBets: number; up: number; down: number; fiftyPlus: number; fiftyUp: number; beats: number; trails: number }

export function bucketsOf(views: ModelView[]): ModelBuckets {
  const withBets = views.filter(m => n(m.bets) > 0)
  const fifty = withBets.filter(m => n(m.bets) >= 50)
  return {
    withBets: withBets.length,
    up: withBets.filter(m => n(m.units) > 0).length,
    down: withBets.filter(m => n(m.units) < 0).length,
    fiftyPlus: fifty.length,
    fiftyUp: fifty.filter(m => n(m.units) > 0).length,
    beats: withBets.filter(m => m.verdict === 'beats').length,
    trails: withBets.filter(m => m.verdict === 'trails').length,
  }
}

/** The models carrying (most units) or dragging (fewest) the record. */
export function byUnits(views: ModelView[], count: number, dir: 'top' | 'bottom'): ModelView[] {
  const sorted = [...views].filter(m => n(m.bets) > 0).sort((a, b) => n(b.units) - n(a.units))
  return dir === 'top' ? sorted.slice(0, count) : sorted.slice(-count).reverse()
}

export function fmtUnitsSigned(v: number | null, dp = 2): string {
  if (v == null) return '—'
  return (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(dp) + 'u'
}

export function fmtPctSigned(v: number | null, dp = 2): string {
  if (v == null) return '—'
  return (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(dp) + '%'
}

export function fmtShare(part: number, whole: number): string {
  return whole > 0 ? `${Math.round((part / whole) * 100)}%` : '—'
}

export function fmtInt(v: number): string {
  return Math.round(v).toLocaleString('en-US')
}
