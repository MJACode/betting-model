import { useEffect, useMemo, useState } from 'react'
import DbOverview from './database/DbOverview'
import { DbSizeChart, DbActivityChart, type RangeDays } from './database/DbCharts'
import DbTables from './database/DbTables'
import DbQueries from './database/DbQueries'
import { Chip } from '../components/PanelUtils'
import { useGetDatabaseHealth, useGetDatabaseTables, useGetDatabaseQueries } from '../hooks/backend/ops'
import { TabShell } from '../components/tiles/TabShell'
import { useRefreshLoad } from '../hooks/useRefreshLoad'
import type { TileMeta, TileRender } from '../components/tiles/layoutTypes'
import type { HealthPoint } from './database/dbUtils'

type Props = {
  refreshKey: number
}

const DATABASE_TILES: TileMeta[] = [
  { id: 'overview', title: 'At a glance', description: 'The newest snapshot of the Supabase database, and how it is changing', x: 0, y: 0, w: 12, h: 9, minW: 6, minH: 5, autoHeight: true },
  { id: 'size', title: 'Size over time', description: 'Table data, indexes and toast, one point an hour', x: 0, y: 9, w: 7, h: 12, minW: 4, minH: 8 },
  { id: 'activity', title: 'Activity', description: 'Load, cache, commits, temp files and connections between snapshots', x: 7, y: 9, w: 5, h: 12, minW: 4, minH: 8 },
  { id: 'tables', title: 'Largest tables', description: 'Size, rows and growth of every table, every six hours', x: 0, y: 21, w: 12, h: 17, minW: 6, minH: 8 },
  { id: 'queries', title: 'Heaviest statements', description: 'What has used the most database time, from Postgres’s own statement statistics', x: 0, y: 38, w: 12, h: 16, minW: 6, minH: 8 },
]

const SWR = { cachePolicy: 'stale-while-revalidate' } as const

type HealthResult =
  | { ok: true; available: boolean; days: number; points: HealthPoint[]; total: number; firstAt: string | null }
  | { ok: false; message: string }

function healthOf(data: unknown): { points: HealthPoint[]; total: number; firstAt: string | null; available: boolean; message: string | null } {
  const d = data as HealthResult | undefined
  if (!d) return { points: [], total: 0, firstAt: null, available: true, message: null }
  if (!d.ok) return { points: [], total: 0, firstAt: null, available: true, message: d.message }
  return { points: d.points ?? [], total: d.total ?? 0, firstAt: d.firstAt ?? null, available: d.available, message: null }
}

export default function DatabaseTab({ refreshKey }: Props) {
  const health = useGetDatabaseHealth(SWR)
  const tables = useGetDatabaseTables(SWR)
  const queries = useGetDatabaseQueries(SWR)
  const [days, setDays] = useState<RangeDays>(30)

  useRefreshLoad('database', refreshKey, skipCache => {
    const opts = { skipCache }
    health.trigger({ days }, opts).result.catch(() => {})
    tables.trigger(undefined, opts).result.catch(() => {})
    queries.trigger(undefined, opts).result.catch(() => {})
  })

  // A new range re-reads the history only.
  const healthTrigger = health.trigger
  const [rangeTouched, setRangeTouched] = useState(false)
  useEffect(() => {
    if (!rangeTouched) return
    healthTrigger({ days }).result.catch(() => {})
  }, [days, rangeTouched, healthTrigger])

  const h = useMemo(() => healthOf(health.data), [health.data])
  const healthError = health.error ?? h.message

  const rangeChips = (
    <div className="flex items-center gap-1">
      {([7, 30, 90] as const).map(d => (
        <Chip key={d} active={days === d} onClick={() => { setRangeTouched(true); setDays(d) }} title={`Last ${d} days`}>
          {d}d
        </Chip>
      ))}
    </div>
  )

  const renderTile = (id: string): TileRender => {
    switch (id) {
      case 'overview':
        return {
          body: (
            <DbOverview
              points={h.points}
              total={h.total}
              firstAt={h.firstAt}
              available={h.available}
              loading={health.loading && h.points.length === 0}
              error={healthError}
            />
          ),
        }
      case 'size':
        return {
          actions: rangeChips,
          body: <DbSizeChart points={h.points} firstAt={h.firstAt} loading={health.loading && h.points.length === 0} error={healthError} days={days} />,
        }
      case 'activity':
        return {
          body: <DbActivityChart points={h.points} firstAt={h.firstAt} loading={health.loading && h.points.length === 0} error={healthError} />,
        }
      case 'tables':
        return { body: <DbTables data={tables.data} loading={tables.loading} error={tables.error} /> }
      case 'queries':
        return { body: <DbQueries data={queries.data} loading={queries.loading} error={queries.error} /> }
      default:
        return { body: null }
    }
  }

  return <TabShell tab="database" metas={DATABASE_TILES} renderTile={renderTile} />
}
