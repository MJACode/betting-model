import { describe, expect, it } from 'vitest'
import {
  counterDelta, fmtBytes, fmtCount, fmtDurationMs, growthPerDay, intervals, type HealthPoint,
} from './dbUtils'

const P = (taken_at: string, extra: Partial<HealthPoint> = {}): HealthPoint => ({
  taken_at,
  db_bytes: 100,
  stats_reset: '2026-03-30T19:02:21Z',
  stmt_reset: '2026-04-04T15:19:21Z',
  ...extra,
})

describe('fmtBytes', () => {
  it('prints what pg_size_pretty prints for the first snapshot', () => {
    // 109,078,711,443 bytes is 101.59 GB in 1024 steps; pg_size_pretty says "102 GB".
    expect(fmtBytes(109_078_711_443)).toBe('101.6 GB')
    expect(fmtBytes(6_701_672)).toBe('6.4 MB')
    expect(fmtBytes(512)).toBe('512 B')
    expect(fmtBytes(null)).toBe('—')
  })
})

describe('fmtCount and fmtDurationMs', () => {
  it('shortens big numbers', () => {
    expect(fmtCount(260_486_212)).toBe('260.5M')
    expect(fmtCount(8_947_115)).toBe('8.95M')
    expect(fmtCount(4_991)).toBe('4,991')
    expect(fmtDurationMs(213_298_775)).toBe('59.2 h')
    expect(fmtDurationMs(840)).toBe('840 ms')
  })
})

describe('counterDelta', () => {
  it('is the change between two snapshots', () => {
    expect(counterDelta(P('2026-11-16T03:00:00Z', { blks_hit: 10 }), P('2026-11-16T04:00:00Z', { blks_hit: 25 }), 'blks_hit')).toBe(15)
  })
  it('is null across a reset, whether or not the reset time moved', () => {
    const a = P('2026-11-16T03:00:00Z', { blks_hit: 10 })
    expect(counterDelta(a, P('2026-11-16T04:00:00Z', { blks_hit: 25, stats_reset: '2026-11-16T03:30:00Z' }), 'blks_hit')).toBeNull()
    expect(counterDelta(a, P('2026-11-16T04:00:00Z', { blks_hit: 4 }), 'blks_hit')).toBeNull()
  })
})

describe('intervals', () => {
  it('turns two snapshots an hour apart into rates', () => {
    const a = P('2026-11-16T03:00:00Z', { blks_hit: 900, blks_read: 100, xact_commit: 0, xact_rollback: 0, stmt_exec_ms: 0, temp_bytes: 0 })
    const b = P('2026-11-16T04:00:00Z', { blks_hit: 1890, blks_read: 110, xact_commit: 3600, xact_rollback: 400, stmt_exec_ms: 7_200_000, temp_bytes: 50 })
    const [r] = intervals([a, b])
    expect(r!.hitRatio).toBeCloseTo(990 / 1000)
    expect(r!.commitsPerSec).toBeCloseTo(1)
    expect(r!.rollbackShare).toBeCloseTo(0.1)
    // 7,200,000 ms of statements in 3,600 s: two running on average.
    expect(r!.load).toBeCloseTo(2)
    expect(r!.tempBytesPerHour).toBeCloseTo(50)
  })
  it('leaves a gap after a statement-stats reset', () => {
    const a = P('2026-11-16T03:00:00Z', { stmt_exec_ms: 9_000 })
    const b = P('2026-11-16T04:00:00Z', { stmt_exec_ms: 10, stmt_reset: '2026-11-16T03:30:00Z' })
    expect(intervals([a, b])[0]!.load).toBeNull()
  })
})

describe('growthPerDay', () => {
  const pts = [
    P('2026-11-15T00:00:00Z', { db_bytes: 1_000 }),
    P('2026-11-15T12:00:00Z', { db_bytes: 1_500 }),
    P('2026-11-16T00:00:00Z', { db_bytes: 2_000 }),
    P('2026-11-16T06:00:00Z', { db_bytes: 2_600 }),
  ]
  it('compares with the newest snapshot at least a day older', () => {
    const g = growthPerDay(pts, 'db_bytes', 24)!
    expect(g.full).toBe(true)
    expect(g.fromAt).toBe('2026-11-15T00:00:00Z')
    expect(g.hours).toBe(30)
    expect(g.perDay).toBeCloseTo((1_600 / 30) * 24)
  })
  it('uses the oldest snapshot when history is shorter, and says so', () => {
    const g = growthPerDay(pts.slice(2), 'db_bytes', 24)!
    expect(g.full).toBe(false)
    expect(g.hours).toBe(6)
    expect(g.perDay).toBeCloseTo(600 * 4)
  })
  it('has nothing to say from one snapshot', () => {
    expect(growthPerDay(pts.slice(3), 'db_bytes')).toBeNull()
  })
})
