// Types and helpers for the Model Health tab. Every figure comes from the
// database views v_model_health_bets / v_model_health_windows /
// v_model_health_summary; this file only formats them and computes the
// rolling series.

export type Num = string | number | null

export type ClvStatus = 'price' | 'line_for' | 'line_against' | 'in_play' | 'no_close' | 'not_measured' | 'old_method'
export type ClvVerdict = 'beat' | 'push' | 'miss' | null

export type SummaryRow = {
  model_id: string
  sport: string
  bets: Num
  first_date: string
  last_date: string
  wins: Num
  losses: Num
  pushes: Num
  units: Num
  risked: Num
  price_n: Num
  price_beat: Num
  price_push: Num
  price_miss: Num
  line_for: Num
  line_against: Num
  in_play: Num
  unmeasured: Num
  market_n: Num
  avg_market_clv_pct: Num
  avg_clv_pct: Num
  se_clv_pct: Num
  price_beat_rate: Num
  beat_rate_with_line: Num
  last25_price_n: Num
  last25_avg_clv_pct: Num
  last25_se_clv_pct: Num
  last25_beat_rate_with_line: Num
  last50_price_n: Num
  last50_avg_clv_pct: Num
  last50_se_clv_pct: Num
  last50_beat_rate_with_line: Num
  last100_price_n: Num
  last100_avg_clv_pct: Num
  last100_se_clv_pct: Num
  last100_beat_rate_with_line: Num
}

export type WindowRow = {
  model_id: string
  sport: string
  block_size: Num
  block_no: Num
  bets: Num
  newest_seq: Num
  oldest_seq: Num
  first_date: string
  last_date: string
  wins: Num
  losses: Num
  pushes: Num
  units: Num
  risked: Num
  price_n: Num
  avg_clv_pct: Num
  sd_clv_pct: Num
  se_clv_pct: Num
  price_beat: Num
  price_push: Num
  price_miss: Num
  line_for: Num
  line_against: Num
  avg_line_pts: Num
  in_play: Num
  unmeasured: Num
  market_n: Num
  avg_market_clv_pct: Num
  full_block: boolean
  price_beat_rate: Num
  beat_rate_with_line: Num
  roi_pct: Num
}

export type BetRow = {
  pick_id: Num
  model_id: string
  sport: string
  game_date: string
  created_at: string
  pick_label: string
  result: string
  status: ClvStatus
  verdict: ClvVerdict
  clv_pct: Num
  market_clv_pct: Num
  line_clv_pts: Num
  units: Num
  seq: Num
}

export const BLOCK_SIZES = [25, 50, 100] as const
export type BlockSize = typeof BLOCK_SIZES[number]

export function num(v: unknown): number | null {
  if (v == null || v === '') return null
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

export function int(v: unknown): number {
  return num(v) ?? 0
}

export function fmtSignedPct(v: number | null, dp = 2): string {
  if (v == null) return '—'
  return (v >= 0 ? '+' : '') + v.toFixed(dp) + '%'
}

export function fmtRate(v: number | null): string {
  return v == null ? '—' : (v * 100).toFixed(0) + '%'
}

export function fmtSignedUnits(v: number | null): string {
  return v == null ? '—' : (v >= 0 ? '+' : '') + v.toFixed(2) + 'u'
}

/** Multiplier for a 95% margin from a standard error. */
export const Z95 = 1.96
/** Below this many bets with a closing price, no verdict is given. */
export const MIN_MEASURED = 10

export type Verdict = 'beats' | 'trails' | 'unclear' | 'few' | 'inplay'

export const VERDICT: Record<Verdict, { label: string; tone: 'good' | 'critical' | 'neutral' | 'outline' | 'info'; help: string }> = {
  beats: { label: 'Beats the close', tone: 'good', help: 'Average CLV is above zero by more than its 95% margin.' },
  trails: { label: 'Trails the close', tone: 'critical', help: 'Average CLV is below zero by more than its 95% margin.' },
  unclear: { label: 'Not clear yet', tone: 'neutral', help: 'The 95% range of the average CLV includes zero.' },
  few: { label: 'Too few measured', tone: 'outline', help: `Fewer than ${MIN_MEASURED} bets with a closing price on our number.` },
  inplay: { label: 'In-play: not measured', tone: 'info', help: 'In-play bets are not measured for closing-line value, by design: there is no pre-game close to compare against.' },
}

export function verdictOf(avg: number | null, se: number | null, measured: number, inPlayOnly: boolean): Verdict {
  if (inPlayOnly) return 'inplay'
  if (measured < MIN_MEASURED || avg == null || se == null) return 'few'
  if (avg - Z95 * se > 0) return 'beats'
  if (avg + Z95 * se < 0) return 'trails'
  return 'unclear'
}

export type Trend = 'improving' | 'fading' | 'steady' | 'none'
export const TREND_LABEL: Record<Trend, string> = { improving: 'Improving', fading: 'Fading', steady: 'Steady', none: '—' }

/**
 * The newest full block against the one before it, same size. A change counts
 * only when it is outside the two blocks' combined 95% margin.
 */
export function trendOf(newer: WindowRow | undefined, older: WindowRow | undefined): { trend: Trend; delta: number | null } {
  if (!newer || !older || !newer.full_block || !older.full_block) return { trend: 'none', delta: null }
  const a = num(newer.avg_clv_pct)
  const b = num(older.avg_clv_pct)
  const sa = num(newer.se_clv_pct)
  const sb = num(older.se_clv_pct)
  if (a == null || b == null || sa == null || sb == null) return { trend: 'none', delta: null }
  const delta = a - b
  if (int(newer.price_n) < MIN_MEASURED || int(older.price_n) < MIN_MEASURED) return { trend: 'none', delta }
  const margin = Z95 * Math.sqrt(sa * sa + sb * sb)
  if (delta > margin) return { trend: 'improving', delta }
  if (delta < -margin) return { trend: 'fading', delta }
  return { trend: 'steady', delta }
}

export const STATUS_LABEL: Record<ClvStatus, string> = {
  price: 'Closing price on our number',
  line_for: 'Line moved our way',
  line_against: 'Line moved against us',
  in_play: 'In-play (not measured, by design)',
  no_close: 'No closing price found',
  not_measured: 'Not measured yet',
  old_method: 'Old method (not counted)',
}

export type RollingPoint = {
  x: number
  seq: number
  date: string
  avg: number | null
  band: [number, number] | null
  measured: number
  beatRate: number | null
  judged: number
}

/**
 * A rolling window over the model's last `size` BETS (not the last `size`
 * measured ones), oldest first. A point appears once a full window exists.
 * avg is the mean CLV of the window's bets that have a closing price on our
 * number; beatRate counts those plus line moves (a line that moved our way is
 * a beat, against us a miss); a bet that closed at our exact price is left out
 * of the rate, as in the published record.
 */
export function rollingSeries(bets: BetRow[], size: number): RollingPoint[] {
  const ordered = [...bets].sort((a, b) => int(b.seq) - int(a.seq))
  const out: RollingPoint[] = []
  for (let i = size - 1; i < ordered.length; i++) {
    const win = ordered.slice(i - size + 1, i + 1)
    const vals: number[] = []
    for (const b of win) {
      if (b.status !== 'price') continue
      const v = num(b.clv_pct)
      if (v != null) vals.push(v)
    }
    let avg: number | null = null
    let band: [number, number] | null = null
    if (vals.length > 0) {
      const mean = vals.reduce((s, v) => s + v, 0) / vals.length
      avg = mean
      if (vals.length > 1) {
        const sd = Math.sqrt(vals.reduce((s, v) => s + (v - mean) ** 2, 0) / (vals.length - 1))
        const h = (Z95 * sd) / Math.sqrt(vals.length)
        band = [mean - h, mean + h]
      }
    }
    const beats = win.filter(b => b.verdict === 'beat').length
    const misses = win.filter(b => b.verdict === 'miss').length
    const last = ordered[i]!
    out.push({
      x: i + 1,
      seq: int(last.seq),
      date: last.game_date,
      avg,
      band,
      measured: vals.length,
      beatRate: beats + misses > 0 ? beats / (beats + misses) : null,
      judged: beats + misses,
    })
  }
  return out
}
