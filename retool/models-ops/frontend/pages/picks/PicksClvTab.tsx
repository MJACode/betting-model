import { useState, useMemo } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Skeleton } from '../../lib/shadcn/skeleton'
import { PanelError, StatsSkeleton, TableSkeleton, ChartSkeleton } from '../../components/PanelUtils'
import { useGetPickLedger } from '../../hooks/backend/ops'
import { applyFilter, defaultFilter, type FilterState, type PickRow } from './picksUtils'
import PicksFilterBar from './PicksFilterBar'
import RollupStrip from './RollupStrip'
import PicksLedger from './PicksLedger'
import { EquityCurve, UnitsByModel, ClvByModel, ClvDistribution } from './PicksCharts'
import { TabShell } from '../../components/tiles/TabShell'
import { useRefreshLoad } from '../../hooks/useRefreshLoad'
import type { TileMeta, TileRender } from '../../components/tiles/layoutTypes'

type Props = { refreshKey: number }

const PICKS_TILES: TileMeta[] = [
  { id: 'rollup', title: 'Summary', description: 'Record, units, ROI and CLV for the picks in the filter', x: 0, y: 0, w: 12, h: 6, minW: 4, minH: 4, autoHeight: true },
  { id: 'ledger', title: 'Ledger', description: 'Every bet pick in the filter, with prices, CLV and result', x: 0, y: 8, w: 12, h: 18, minW: 6, minH: 8 },
  { id: 'equity', title: 'Equity curve', description: 'Running units over time, settled and priced picks only', x: 0, y: 26, w: 6, h: 10, minW: 4, minH: 7 },
  { id: 'unitsByModel', title: 'Units by model', description: 'Settled, priced picks only, sorted by units', x: 6, y: 26, w: 6, h: 10, minW: 4, minH: 7 },
  { id: 'clvByModel', title: 'CLV by model', description: 'Share of measured picks that beat, matched or missed the close, or whose line moved our way or against', x: 0, y: 36, w: 6, h: 12, minW: 4, minH: 7 },
  { id: 'clvDistribution', title: 'CLV distribution', description: 'How far same-line picks beat or missed the closing price', x: 6, y: 36, w: 6, h: 12, minW: 4, minH: 7 },
]

export default function PicksClvTab({ refreshKey }: Props) {
  const { data, loading, error, trigger } = useGetPickLedger({ cachePolicy: 'stale-while-revalidate' })
  const [filter, setFilter] = useState<FilterState>(defaultFilter())

  useRefreshLoad('picks', refreshKey, skipCache => {
    trigger(undefined, { skipCache }).result.catch(() => {})
  })

  const allRows = useMemo<PickRow[]>(() => (data as PickRow[] | undefined) ?? [], [data])
  const filteredRows = useMemo(() => applyFilter(allRows, filter), [allRows, filter])
  const sportUniverse = useMemo(() => Array.from(new Set(allRows.map(r => r.sport))).sort(), [allRows])

  // Data bounds come from the loaded rows
  const { dataMin, dataMax } = useMemo(() => {
    if (allRows.length === 0) return { dataMin: '', dataMax: '' }
    let mn = allRows[0]!.game_date
    let mx = allRows[0]!.game_date
    for (const r of allRows) {
      if (r.game_date < mn) mn = r.game_date
      if (r.game_date > mx) mx = r.game_date
    }
    return { dataMin: mn, dataMax: mx }
  }, [allRows])

  const repairSelected = filter.lanes.includes('repair')

  const pinned = (
    <div
      className="sticky z-20 -mx-4 space-y-3 bg-background/90 px-4 py-2 backdrop-blur sm:-mx-6 sm:px-6"
      style={{ top: 'var(--app-header-h, 0px)' }}
    >
      {loading ? (
        <Skeleton className="h-[104px] w-full rounded-xl" />
      ) : (
        <PicksFilterBar
          rows={allRows}
          filtered={filteredRows.length}
          filter={filter}
          onChange={setFilter}
          dataMin={dataMin}
          dataMax={dataMax}
        />
      )}
      {error && <PanelError message={error} />}
      {repairSelected && (
        <div className="flex items-start gap-3 rounded-lg border border-warn bg-warn-soft px-4 py-3 text-warn">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden />
          <p className="text-xs leading-relaxed">
            These are pre-game prop picks scored against an in-play price after first pitch, not in-play bets.
            They carry no units by design and are excluded from every record.
          </p>
        </div>
      )}
    </div>
  )

  const renderTile = (id: string): TileRender => {
    if (loading) {
      if (id === 'rollup') return { body: <StatsSkeleton count={6} /> }
      if (id === 'ledger') return { body: <TableSkeleton rows={8} /> }
      return { body: <ChartSkeleton height={220} /> }
    }
    if (error) return { body: <p className="text-sm text-muted-foreground">The pick ledger could not be loaded; see the message above.</p> }
    switch (id) {
      case 'rollup':
        return { body: <RollupStrip rows={filteredRows} total={allRows.length} /> }
      case 'ledger':
        return { body: <PicksLedger rows={filteredRows} /> }
      case 'equity':
        return { body: <EquityCurve rows={filteredRows} sportUniverse={sportUniverse} /> }
      case 'unitsByModel':
        return { body: <UnitsByModel rows={filteredRows} /> }
      case 'clvByModel':
        return { body: <ClvByModel rows={filteredRows} /> }
      case 'clvDistribution':
        return { body: <ClvDistribution rows={filteredRows} /> }
      default:
        return { body: null }
    }
  }

  return <TabShell tab="picks" metas={PICKS_TILES} renderTile={renderTile} pinned={pinned} />
}
