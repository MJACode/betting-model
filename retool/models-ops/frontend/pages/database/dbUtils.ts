// Number helpers for the Database tab. Pure functions, unit-tested in dbUtils.test.ts.

export type HealthPoint = {
  taken_at: string
  source?: string
  db_bytes: number
  table_bytes?: number | null
  index_bytes?: number | null
  toast_bytes?: number | null
  relations?: number | null
  live_rows_est?: number | null
  dead_rows_est?: number | null
  connections?: number | null
  connections_active?: number | null
  connections_idle?: number | null
  connections_idle_in_tx?: number | null
  max_connections?: number | null
  longest_xact_s?: number | null
  waiting_locks?: number | null
  xid_age?: number | null
  freeze_max_age?: number | null
  blks_hit?: number | null
  blks_read?: number | null
  xact_commit?: number | null
  xact_rollback?: number | null
  temp_bytes?: number | null
  deadlocks?: number | null
  stats_reset?: string | null
  stmt_calls?: number | null
  stmt_exec_ms?: number | null
  stmt_reset?: string | null
  unused_indexes?: number | null
  unused_index_bytes?: number | null
  storage_objects?: number | null
  storage_bytes?: number | null
  storage_buckets?: Array<{ bucket: string; objects: number; bytes: number }> | null
}

const KB = 1024
const UNITS = ['B', 'KB', 'MB', 'GB', 'TB'] as const

/**
 * Bytes in 1024 steps with Postgres's own unit names, as pg_size_pretty
 * prints them ("102 GB" for 109,078,711,443 bytes): one decimal under 100.
 */
export function fmtBytes(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '—'
  const neg = n < 0
  let v = Math.abs(n)
  let i = 0
  while (v >= KB && i < UNITS.length - 1) {
    v /= KB
    i++
  }
  const dp = i === 0 || v >= 100 ? 0 : 1
  return `${neg ? '−' : ''}${v.toFixed(dp)} ${UNITS[i]}`
}

/** Signed bytes: "+3.1 GB", "−12 MB", "0 B". */
export function fmtBytesSigned(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '—'
  if (n === 0) return '0 B'
  return (n > 0 ? '+' : '') + fmtBytes(n)
}

/** Counts: 1,234 below ten thousand, then 12.3K, 4.56M, 1.2B. */
export function fmtCount(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '—'
  const a = Math.abs(n)
  const sign = n < 0 ? '−' : ''
  if (a < 10_000) return sign + Math.round(a).toLocaleString('en-US')
  if (a < 1_000_000) return `${sign}${(a / 1_000).toFixed(a < 100_000 ? 1 : 0)}K`
  if (a < 1_000_000_000) return `${sign}${(a / 1_000_000).toFixed(a < 100_000_000 ? 2 : 1)}M`
  return `${sign}${(a / 1_000_000_000).toFixed(2)}B`
}

export function fmtCountSigned(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '—'
  if (Math.round(n) === 0) return '0'
  return (n > 0 ? '+' : '') + fmtCount(n)
}

export function fmtPct(n: number | null | undefined, dp = 1): string {
  if (n == null || !Number.isFinite(n)) return '—'
  return `${(n * 100).toFixed(dp)}%`
}

/** Milliseconds as the largest sensible unit: 840 ms, 12.4 s, 3.2 min, 59.2 h. */
export function fmtDurationMs(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms)) return '—'
  const a = Math.abs(ms)
  if (a < 1_000) return `${a.toFixed(a < 10 ? 1 : 0)} ms`
  if (a < 60_000) return `${(a / 1_000).toFixed(1)} s`
  if (a < 3_600_000) return `${(a / 60_000).toFixed(1)} min`
  return `${(a / 3_600_000).toFixed(1)} h`
}

export function hoursBetween(a: string, b: string): number {
  return (Date.parse(b) - Date.parse(a)) / 3_600_000
}

/**
 * The change in a running counter between two snapshots, or null when it
 * cannot be read: a value missing, the counter's reset time changed, or the
 * counter went down (a reset the reset time did not show).
 */
export function counterDelta(
  a: HealthPoint,
  b: HealthPoint,
  key: keyof HealthPoint,
  resetKey: 'stats_reset' | 'stmt_reset' = 'stats_reset',
): number | null {
  const va = a[key]
  const vb = b[key]
  if (typeof va !== 'number' || typeof vb !== 'number') return null
  if ((a[resetKey] ?? null) !== (b[resetKey] ?? null)) return null
  const d = vb - va
  return d < 0 ? null : d
}

export type Interval = {
  at: string
  hours: number
  hitRatio: number | null
  load: number | null
  commitsPerSec: number | null
  rollbackShare: number | null
  tempBytesPerHour: number | null
  deadlocks: number | null
}

/** Rates for each pair of consecutive snapshots, stamped at the later one. */
export function intervals(points: HealthPoint[]): Interval[] {
  const out: Interval[] = []
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1]!
    const b = points[i]!
    const hours = hoursBetween(a.taken_at, b.taken_at)
    if (!(hours > 0)) continue
    const secs = hours * 3600
    const hit = counterDelta(a, b, 'blks_hit')
    const read = counterDelta(a, b, 'blks_read')
    const commits = counterDelta(a, b, 'xact_commit')
    const rollbacks = counterDelta(a, b, 'xact_rollback')
    const temp = counterDelta(a, b, 'temp_bytes')
    const stmtMs = counterDelta(a, b, 'stmt_exec_ms', 'stmt_reset')
    out.push({
      at: b.taken_at,
      hours,
      hitRatio: hit != null && read != null && hit + read > 0 ? hit / (hit + read) : null,
      // Statement time per second of wall time: the average number of
      // statements running at any moment between the two snapshots.
      load: stmtMs != null ? stmtMs / (secs * 1000) : null,
      commitsPerSec: commits != null ? commits / secs : null,
      rollbackShare: commits != null && rollbacks != null && commits + rollbacks > 0 ? rollbacks / (commits + rollbacks) : null,
      tempBytesPerHour: temp != null ? temp / hours : null,
      deadlocks: counterDelta(a, b, 'deadlocks'),
    })
  }
  return out
}

export type Growth = {
  /** Change per day, in the unit of the column. */
  perDay: number
  /** The change over the measured span. */
  change: number
  /** Hours between the two snapshots compared. */
  hours: number
  /** The earlier snapshot compared. */
  fromAt: string
  /** True when the span is the one asked for; false when history is shorter. */
  full: boolean
}

/**
 * Growth of a size column per day: the newest snapshot against the newest one
 * at least `targetHours` older. With less history than that, the oldest
 * snapshot is used, as long as it is at least `minHours` older (full = false).
 */
export function growthPerDay(
  points: HealthPoint[],
  key: 'db_bytes' | 'table_bytes' | 'index_bytes' | 'live_rows_est' | 'storage_bytes',
  targetHours = 24,
  minHours = 1,
): Growth | null {
  if (points.length < 2) return null
  const last = points[points.length - 1]!
  const lastV = last[key]
  if (typeof lastV !== 'number') return null
  const cutoff = Date.parse(last.taken_at) - targetHours * 3_600_000
  let ref: HealthPoint | undefined
  for (let i = points.length - 2; i >= 0; i--) {
    if (Date.parse(points[i]!.taken_at) <= cutoff) {
      ref = points[i]
      break
    }
  }
  const full = ref != null
  if (!ref) ref = points[0]
  if (!ref) return null
  const refV = ref[key]
  if (typeof refV !== 'number') return null
  const hours = hoursBetween(ref.taken_at, last.taken_at)
  if (!(hours >= minHours)) return null
  const change = lastV - refV
  return { perDay: (change / hours) * 24, change, hours, fromAt: ref.taken_at, full }
}

/** A short, readable span: "45 min", "6 h", "3.5 days". */
export function fmtSpan(hours: number): string {
  if (hours < 1) return `${Math.round(hours * 60)} min`
  if (hours < 48) return `${hours < 10 ? hours.toFixed(1).replace(/\.0$/, '') : Math.round(hours)} h`
  const days = hours / 24
  return `${days < 10 ? days.toFixed(1).replace(/\.0$/, '') : Math.round(days)} days`
}

/** "Nov 16, 03:41 UTC". Snapshots are stored in UTC; the label says so. */
export function fmtUtc(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const date = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })
  const time = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'UTC' })
  return `${date}, ${time} UTC`
}

/** How long ago, from a fixed "now" so tests can pin it. */
export function fmtAgo(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return 'never'
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return '—'
  const h = (now - t) / 3_600_000
  if (h < 0) return 'just now'
  if (h < 1) return `${Math.max(1, Math.round(h * 60))} min ago`
  if (h < 48) return `${Math.round(h)} h ago`
  return `${Math.round(h / 24)} days ago`
}

/** Bytes to GB (1024³), for chart axes. */
export function toGB(n: number | null | undefined): number | null {
  return n == null ? null : n / KB ** 3
}
