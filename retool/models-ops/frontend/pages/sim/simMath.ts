/**
 * Bankroll simulation math, ported line for line from the standalone simulator.
 * Every function is pure: the parameters (the original's `state`) and the
 * log-factorial table (the original's `lf`) are passed in.
 */

export const QS: readonly number[] = [0.05, 0.25, 0.5, 0.75, 0.95]

export type SimParams = {
  /** True win rate, 0..1. */
  p: number
  /** Starting bankroll in units. */
  B0: number
  /** Stake as a fraction of the current bankroll. */
  f: number
  /** American price. */
  odds: number
  /** Number of bets. */
  N: number
  /** Simulated paths. */
  paths: number
  seed: number
}

export const DEFAULT_PARAMS: SimParams = { p: 0.54, B0: 100, f: 0.01, odds: -110, N: 5000, paths: 2000, seed: 20261111 }

export type Logs = { b: number; lu: number; ld: number }

/** lf[k] = ln(k!) for k = 0..n (the original's ensureLf(n) table). */
export function logFactorials(n: number): Float64Array {
  const lf = new Float64Array(n + 1)
  lf[0] = 0
  for (let k = 1; k <= n; k++) lf[k] = lf[k - 1]! + Math.log(k)
  return lf
}

export function payout(odds: number): number {
  return odds < 0 ? 100 / Math.abs(odds) : odds / 100
}

export function logs(s: Pick<SimParams, 'odds' | 'f'>): Logs {
  const b = payout(s.odds)
  return { b, lu: Math.log(1 + s.f * b), ld: Math.log(1 - s.f) }
}

export function binomQuantiles(t: number, p: number, qs: readonly number[], lf: Float64Array): number[] {
  const out: number[] = []
  if (t === 0) {
    for (let z = 0; z < qs.length; z++) out.push(0)
    return out
  }
  const lp = Math.log(p), lq = Math.log(1 - p)
  const mu = t * p, sd = Math.sqrt(t * p * (1 - p))
  const k0 = Math.max(0, Math.floor(mu - 12 * sd - 2))
  let cdf = 0, qi = 0
  for (let k = k0; k <= t && qi < qs.length; k++) {
    cdf += Math.exp(lf[t]! - lf[k]! - lf[t - k]! + k * lp + (t - k) * lq)
    while (qi < qs.length && cdf >= qs[qi]!) { out.push(k); qi++ }
  }
  while (qi < qs.length) { out.push(t); qi++ }
  return out
}

export function binomCdf(t: number, p: number, kmax: number, lf: Float64Array): number {
  if (kmax < 0) return 0
  if (kmax >= t) return 1
  const lp = Math.log(p), lq = Math.log(1 - p)
  const mu = t * p, sd = Math.sqrt(t * p * (1 - p))
  const k0 = Math.max(0, Math.floor(mu - 14 * sd - 2))
  let s = 0
  for (let k = k0; k <= kmax; k++) s += Math.exp(lf[t]! - lf[k]! - lf[t - k]! + k * lp + (t - k) * lq)
  return Math.min(1, s)
}

export function pBelowStart(t: number, p: number, L: Logs, lf: Float64Array): number {
  const kStar = t * (-L.ld) / (L.lu - L.ld)
  const kmax = Math.ceil(kStar) - 1
  return binomCdf(t, p, kmax, lf)
}

export function bankAt(t: number, k: number, L: Logs, B0: number): number {
  return B0 * Math.exp(k * L.lu + (t - k) * L.ld)
}

export function mulberry32(seed: number): () => number {
  let a = seed
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export type SimResult = {
  L: Logs
  times: number[]
  /** One row per quantile in QS, bankroll in units at each time. */
  band: Float64Array[]
  /** Sample paths as log growth; bankroll = B0 * exp(sp). */
  sp: Float64Array[]
  final: number[]
  meanFinal: number
  pBelow: number
  medDD: number
  pDD30: number
  pHalf: number
  medStreak: number
}

export function compute(s: SimParams): SimResult {
  const p = s.p, N = s.N, L = logs(s)
  const lf = logFactorials(N + 1)
  const step = Math.max(1, Math.round(N / 250))
  const times: number[] = []
  for (let t = 0; t < N; t += step) times.push(t)
  times.push(N)
  const band = QS.map(() => new Float64Array(times.length))
  for (let i = 0; i < times.length; i++) {
    const ks = binomQuantiles(times[i]!, p, QS, lf)
    for (let q = 0; q < QS.length; q++) band[q]![i] = bankAt(times[i]!, ks[q]!, L, s.B0)
  }
  const S = 8, P = s.paths
  const sp: Float64Array[] = []
  for (let k = 0; k < S; k++) sp.push(new Float64Array(times.length))
  const mdd = new Float64Array(P)
  const halfLog = Math.log(0.5)
  let everHalf = 0, dd30 = 0
  const streaks = new Float64Array(P)
  const rnd = mulberry32(s.seed)
  const lu = L.lu, ld = L.ld
  for (let j = 0; j < P; j++) {
    let x = 0, peak = 0, dd = 0, minx = 0, ti = 1, run = 0, best = 0
    const row = j < S ? sp[j]! : null
    for (let n = 1; n <= N; n++) {
      if (rnd() < p) { x += lu; run = 0; if (x > peak) peak = x }
      else { x += ld; run += 1; if (run > best) best = run; if (peak - x > dd) dd = peak - x; if (x < minx) minx = x }
      if (row !== null && n === times[ti]) { row[ti] = x; ti += 1 }
    }
    const m = 1 - Math.exp(-dd)
    mdd[j] = m
    streaks[j] = best
    if (minx < halfLog) everHalf += 1
    if (m >= 0.3) dd30 += 1
  }
  mdd.sort(); streaks.sort()
  const finalKs = binomQuantiles(N, p, QS, lf)
  const meanFinal = s.B0 * Math.pow(1 + s.f * (p * L.b - (1 - p)), N)
  return {
    L, times, band, sp,
    final: finalKs.map(k => bankAt(N, k, L, s.B0)),
    meanFinal,
    pBelow: pBelowStart(N, p, L, lf),
    medDD: mdd[Math.floor(P / 2)]!,
    pDD30: dd30 / P,
    pHalf: everHalf / P,
    medStreak: streaks[Math.floor(P / 2)]!,
  }
}

export type SweepPoint = { p: number; med: number; below: number }

/** Median ending bankroll and chance below start at 97 win rates, 48%..60%. Depends only on N, f, odds, B0. */
export function computeSweep(s: Pick<SimParams, 'N' | 'f' | 'odds' | 'B0'>): SweepPoint[] {
  const L = logs(s)
  const lf = logFactorials(s.N + 1)
  const pts: SweepPoint[] = []
  for (let i = 0; i <= 96; i++) {
    const p = 0.48 + i * 0.00125
    const k = binomQuantiles(s.N, p, [0.5], lf)[0]!
    pts.push({ p, med: bankAt(s.N, k, L, s.B0), below: pBelowStart(s.N, p, L, lf) })
  }
  return pts
}

export type CheckpointRow = { bets: number; values: number[]; below: number }

/** The percentile table: 100, 250, ... below N, then N. */
export function checkpointRows(s: Pick<SimParams, 'p' | 'N' | 'f' | 'odds' | 'B0'>): CheckpointRow[] {
  const L = logs(s)
  const lf = logFactorials(s.N + 1)
  const cps = [100, 250, 500, 1000, 2500, 5000, 10000, 20000].filter(c => c < s.N)
  cps.push(s.N)
  return cps.map(c => ({
    bets: c,
    values: binomQuantiles(c, s.p, QS, lf).map(k => bankAt(c, k, L, s.B0)),
    below: pBelowStart(c, s.p, L, lf),
  }))
}

export type EdgeInfo = { be: number; gbe: number; ev: number; edge: number }

/** Break-even, the growth bar under percentage staking, EV per unit staked and the edge in points. */
export function edgeInfo(p: number, L: Logs): EdgeInfo {
  const be = 1 / (1 + L.b)
  const gbe = -L.ld / (L.lu - L.ld)
  const ev = p * L.b - (1 - p)
  const edge = (p - be) * 100
  return { be, gbe, ev, edge }
}

/** Stake percent for display, without float noise (0.07 * 100 = 7.000000000000001). */
export function stakePctText(f: number): string {
  return String(Number((f * 100).toPrecision(12)))
}

export function edgeLine(p: number, f: number, L: Logs): string {
  const { be, gbe, ev, edge } = edgeInfo(p, L)
  return (edge >= 0 ? '+' : '') + edge.toFixed(2) + ' pts vs break-even of ' + (be * 100).toFixed(2) + '%. EV ' +
    (ev >= 0 ? '+' : '') + (ev * 100).toFixed(1) + '% of stake per bet. Under ' + stakePctText(f) +
    '% compounding the median bankroll only grows above ' + (gbe * 100).toFixed(2) + '%.'
}

export function pct(x: number, d = 1): string {
  if (x > 0 && x < 0.001) return '<0.1%'
  if (x < 1 && x > 0.999) return '>99.9%'
  return (x * 100).toFixed(d) + '%'
}

/** The original's readAdv clamps. Returns null when the value cannot be used (keep the previous one). */
export const clampInput = {
  B0: (v: number): number | null => (Number.isFinite(v) && v > 0 ? v : null),
  fPct: (v: number): number | null => (Number.isFinite(v) ? Math.min(25, Math.max(0.1, v)) : null),
  odds: (v: number): number | null => (Number.isFinite(v) ? (Math.abs(v) >= 100 ? v : v < 0 ? -100 : 100) : null),
  N: (v: number): number | null => (Number.isFinite(v) ? Math.min(20000, Math.max(10, Math.round(v))) : null),
  paths: (v: number): number | null => (Number.isFinite(v) ? Math.min(10000, Math.max(100, Math.round(v))) : null),
}

export function newSeed(): number {
  return (Math.random() * 1e9) | 0
}

const BIG_SUFFIXES = ['K', 'M', 'B', 'T'] as const

/**
 * Units, never dollars. Below 10,000: one decimal with a thousands separator,
 * e.g. "1,234.5u". From 10,000: three significant figures with K/M/B/T, e.g.
 * "12.3K u", "4.56M u", "1.2B u". With `axis`, round values drop the decimal ("100u").
 */
export function fmtU(v: number, opts?: { axis?: boolean }): string {
  if (!Number.isFinite(v)) return '—'
  const a = Math.abs(v)
  if (a < 10000) {
    if (opts?.axis) {
      if (Number.isInteger(v)) return v.toLocaleString('en-US') + 'u'
      if (a < 1 && a > 0) return String(Number(v.toPrecision(2))) + 'u'
    }
    return v.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + 'u'
  }
  let scaled = v / 1000
  let i = 0
  while (i < BIG_SUFFIXES.length - 1 && Math.abs(Number(scaled.toPrecision(3))) >= 1000) {
    scaled /= 1000
    i++
  }
  if (Math.abs(Number(scaled.toPrecision(3))) >= 1000) return v.toExponential(2) + ' u'
  return String(Number(scaled.toPrecision(3))) + BIG_SUFFIXES[i]! + ' u'
}

/** The original simulator's dollar formats, verbatim (`money`, `axisMoney`). Only the Dollars display uses them. */
export function money(v: number): string {
  const a = Math.abs(v)
  if (a >= 1e9) return '$' + (v / 1e9).toFixed(a >= 1e10 ? 1 : 2) + 'B'
  if (a >= 1e6) return '$' + (v / 1e6).toFixed(a >= 1e7 ? 1 : 2) + 'M'
  if (a >= 1e4) return '$' + Math.round(v / 1e3) + 'K'
  if (a >= 1e3) return '$' + (v / 1e3).toFixed(1) + 'K'
  return '$' + Math.round(v)
}

export function axisMoney(v: number): string {
  const trim = (x: number) => String(parseFloat(x.toFixed(2)))
  if (v >= 1e9) return '$' + trim(v / 1e9) + 'B'
  if (v >= 1e6) return '$' + trim(v / 1e6) + 'M'
  if (v >= 1e3) return '$' + trim(v / 1e3) + 'K'
  return '$' + Math.round(v)
}

/** How bankroll figures are shown. The math always runs in units; Dollars multiplies for display only. */
export type Display = { mode: 'units' | 'dollars'; perUnit: number }

export const DEFAULT_DISPLAY: Display = { mode: 'units', perUnit: 100 }

export type Fmt = (v: number, opts?: { axis?: boolean }) => string

/** Display amount per bankroll unit: 1 in Units, the dollars per unit in Dollars. */
export function displayFactor(d: Display): number {
  return d.mode === 'dollars' ? d.perUnit : 1
}

/** The bankroll formatter for a display. Units is `fmtU` itself; Dollars is units x dollars per unit in the original's formats. */
export function makeFmt(d: Display): Fmt {
  if (d.mode === 'units') return fmtU
  const k = d.perUnit
  return (v, opts) => (!Number.isFinite(v) ? '—' : opts?.axis ? axisMoney(v * k) : money(v * k))
}

/** Dollars per unit: any positive amount up to 1,000,000; null keeps the previous value. */
export function clampPerUnit(v: number): number | null {
  return Number.isFinite(v) && v > 0 ? Math.min(1e6, v) : null
}
