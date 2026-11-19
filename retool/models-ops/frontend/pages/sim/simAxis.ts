/** Axis ticks and domains for the simulation charts. */

const TINY = 1e-300

/** Positive floor so a log axis never receives 0 (only affects drawing). */
export function logSafe(v: number): number {
  return v > TINY ? v : TINY
}

export function niceStep(range: number, count: number): number {
  const raw = range / count
  if (!(raw > 0) || !Number.isFinite(raw)) return 1
  const mag = Math.pow(10, Math.floor(Math.log10(raw)))
  const n = raw / mag
  const m = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10
  return m * mag
}

function clean(v: number): number {
  return Number(v.toPrecision(12))
}

/** Linear axis from 0 to a round top. */
export function linearAxis(hi: number): { domain: [number, number]; ticks: number[] } {
  const step = niceStep(hi > 0 ? hi : 1, 5)
  const top = clean(Math.ceil((hi > 0 ? hi : 1) / step) * step)
  const ticks: number[] = []
  for (let v = 0; v <= top + step * 1e-9; v += step) ticks.push(clean(v))
  return { domain: [0, top], ticks }
}

/** Log axis: a padded domain around [lo, hi] with 1-2-5 ticks, or decades when that is too many. */
export function logAxis(loRaw: number, hiRaw: number): { domain: [number, number]; ticks: number[] } {
  const lo = logSafe(Math.min(loRaw, hiRaw)) / 1.15
  const hi = logSafe(Math.max(loRaw, hiRaw)) * 1.15
  const e0 = Math.floor(Math.log10(lo))
  const e1 = Math.ceil(Math.log10(hi))
  const all: number[] = []
  const decades: number[] = []
  for (let e = e0; e <= e1; e++) {
    const base = Math.pow(10, e)
    for (const m of [1, 2, 5]) {
      const v = clean(m * base)
      if (v >= lo && v <= hi) {
        all.push(v)
        if (m === 1) decades.push(v)
      }
    }
  }
  let ticks: number[]
  if (all.length >= 3 && all.length <= 8) ticks = all
  else if (all.length > 8) {
    const stride = Math.max(1, Math.ceil(decades.length / 8))
    ticks = decades.filter((_, i) => i % stride === 0)
  } else {
    // Narrow range: evenly spaced round values inside it.
    const step = niceStep(hi - lo, 4)
    ticks = []
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) if (v > 0) ticks.push(clean(v))
  }
  return { domain: [lo, hi], ticks }
}
