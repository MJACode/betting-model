import { useMemo } from 'react'
import {
  HardDrive, TrendingUp, Rows3, Zap, Gauge, Hourglass, Cable, Recycle, Timer, ListX, Archive,
} from 'lucide-react'
import { PanelError, StatsSkeleton, StatCard, EmptyState, Footnote } from '../../components/PanelUtils'
import {
  fmtBytes, fmtBytesSigned, fmtCount, fmtCountSigned, fmtPct, fmtSpan, fmtUtc, growthPerDay, intervals,
  type HealthPoint,
} from './dbUtils'

type Props = {
  points: HealthPoint[]
  total: number
  firstAt: string | null
  available: boolean
  loading: boolean
  error: string | null
}

function utcDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })
}

export default function DbOverview({ points, total, firstAt, available, loading, error }: Props) {
  const derived = useMemo(() => {
    const last = points[points.length - 1]
    const iv = intervals(points)
    const lastIv = iv[iv.length - 1]
    return {
      last,
      lastIv,
      size24: growthPerDay(points, 'db_bytes', 24),
      size7d: growthPerDay(points, 'db_bytes', 24 * 7, 24 * 3),
      rows24: growthPerDay(points, 'live_rows_est', 24),
    }
  }, [points])

  if (loading) return <StatsSkeleton count={10} />
  if (error) return <PanelError message={error} />
  if (!available) {
    return (
      <EmptyState icon={HardDrive} title="The snapshot tables are not in the database yet">
        They are created by data/migrations/db_health_snapshots_2026_11_15.sql, which the worker applies on its next pass.
      </EmptyState>
    )
  }
  const { last, lastIv, size24, size7d, rows24 } = derived
  if (!last) {
    return (
      <EmptyState icon={HardDrive} title="No snapshot yet">
        The worker writes one every hour at 50 minutes past, Eastern time.
      </EmptyState>
    )
  }

  const lifetimeHit = last.blks_hit != null && last.blks_read != null && last.blks_hit + last.blks_read > 0
    ? last.blks_hit / (last.blks_hit + last.blks_read) : null
  const hit = lastIv?.hitRatio ?? null
  const deadShare = last.dead_rows_est != null && last.live_rows_est ? last.dead_rows_est / last.live_rows_est : null
  const xidShare = last.xid_age != null && last.freeze_max_age ? last.xid_age / last.freeze_max_age : null
  const buckets = last.storage_buckets ?? []
  const nextHint = 'Shows after the next snapshot.'

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard
          icon={HardDrive}
          label="Database size"
          value={fmtBytes(last.db_bytes)}
          caption={`Tables ${fmtBytes(last.table_bytes)} · indexes ${fmtBytes(last.index_bytes)} · toast ${fmtBytes(last.toast_bytes)}`}
        />
        <StatCard
          icon={TrendingUp}
          label="Growth"
          value={size24 ? `${fmtBytesSigned(size24.perDay)}/day` : '—'}
          caption={size24
            ? `${size24.full ? 'Over the last 24 h' : `Over the ${fmtSpan(size24.hours)} recorded`}${size7d ? ` · 7-day ${fmtBytesSigned(size7d.perDay)}/day` : ''}`
            : points.length >= 2 ? 'Shows once the snapshots span an hour.' : nextHint}
        />
        <StatCard
          icon={Rows3}
          label="Rows (estimated)"
          value={fmtCount(last.live_rows_est)}
          caption={rows24 ? `${fmtCountSigned(rows24.perDay)} a day${rows24.full ? '' : ` (over ${fmtSpan(rows24.hours)})`}` : 'Postgres’s own estimate, not a count'}
        />
        <StatCard
          icon={Zap}
          label="Cache hit rate"
          value={fmtPct(hit ?? lifetimeHit, 1)}
          caption={hit != null
            ? 'Reads served from memory since the last snapshot'
            : `Running total since ${utcDate(last.stats_reset)}. ${nextHint}`}
        />
        <StatCard
          icon={Gauge}
          label="Load"
          value={lastIv?.load != null ? lastIv.load.toFixed(2) : '—'}
          caption={lastIv?.load != null ? 'Statements running at once, on average, since the last snapshot' : nextHint}
        />
        <StatCard
          icon={Hourglass}
          label="Idle in a transaction"
          value={lastIv?.idleInTx != null ? lastIv.idleInTx.toFixed(2) : '—'}
          caption={lastIv?.idleInTx != null
            ? 'Sessions holding a transaction open while doing nothing, on average'
            : nextHint}
        />
        <StatCard
          icon={Cable}
          label="Connections"
          value={last.connections != null ? `${last.connections} / ${last.max_connections ?? '—'}` : '—'}
          caption={`${last.connections_active ?? 0} active · ${last.connections_idle ?? 0} idle · ${last.connections_idle_in_tx ?? 0} idle in a transaction`}
        />
        <StatCard
          icon={Recycle}
          label="Dead rows"
          value={fmtCount(last.dead_rows_est)}
          caption={deadShare != null ? `${fmtPct(deadShare)} of live rows, waiting for vacuum` : 'Waiting for vacuum'}
        />
        <StatCard
          icon={Timer}
          label="Transaction ID age"
          value={fmtPct(xidShare)}
          caption={`${fmtCount(last.xid_age)} of ${fmtCount(last.freeze_max_age)}, when Postgres forces a vacuum`}
        />
        <StatCard
          icon={ListX}
          label="Unused indexes"
          value={last.unused_indexes != null ? String(last.unused_indexes) : '—'}
          caption={`${fmtBytes(last.unused_index_bytes)}, never scanned since ${utcDate(last.stats_reset)}`}
        />
      </div>
      <Footnote>
        <span className="inline-flex items-center gap-1"><Archive className="h-3 w-3" aria-hidden />File storage {fmtBytes(last.storage_bytes)} in {fmtCount(last.storage_objects)} files, {buckets.length} bucket{buckets.length === 1 ? '' : 's'}.</span>
        {' '}Newest snapshot {fmtUtc(last.taken_at)} ({last.source === 'manual' ? 'taken by hand' : 'hourly job'}).
        {' '}{total.toLocaleString('en-US')} snapshot{total === 1 ? '' : 's'} stored since {fmtUtc(firstAt)}; none is ever deleted.
        {' '}Sizes are in Postgres’s units (1 GB = 1,024³ bytes). Row counts are Postgres’s estimates.
      </Footnote>
    </div>
  )
}
