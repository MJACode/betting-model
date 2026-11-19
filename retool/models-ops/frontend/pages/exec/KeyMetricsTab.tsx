import { useMemo } from 'react'
import { useGetKeyMetrics } from '../../hooks/backend/ops'
import { TabShell } from '../../components/tiles/TabShell'
import { useRefreshLoad } from '../../hooks/useRefreshLoad'
import type { TileMeta, TileRender } from '../../components/tiles/layoutTypes'
import { ResultsStrip, EquityChart, ClvSplit, ModelsStrip, ModelList, OpsStrip } from './ExecParts'
import { bucketsOf, byUnits, equityOf, modelViews, totalsOf, windowOf, type KeyMetrics } from './keyMetrics'

type Props = { refreshKey: number }

const EXEC_TILES: TileMeta[] = [
  { id: 'results', title: 'Results', description: 'The published record in units: all-time, the last 30 and 7 days, and the deepest drop', x: 0, y: 0, w: 12, h: 5, minW: 6, minH: 4, autoHeight: true },
  { id: 'equity', title: 'Units won over time', description: 'The running total of the published record, by game date', x: 0, y: 5, w: 8, h: 10, minW: 5, minH: 8 },
  { id: 'clv', title: 'Beating the closing line', description: 'Every measured pre-game bet against its book’s last price before the start', x: 8, y: 5, w: 4, h: 10, minW: 4, minH: 8 },
  { id: 'models', title: 'Models', description: 'How many are live, in profit, and beating the close', x: 0, y: 15, w: 12, h: 4, minW: 6, minH: 3, autoHeight: true },
  { id: 'leaders', title: 'Carrying the record', description: 'The five models with the most units won', x: 0, y: 19, w: 6, h: 8, minW: 4, minH: 6 },
  { id: 'laggards', title: 'Dragging the record', description: 'The five models with the fewest units won', x: 6, y: 19, w: 6, h: 8, minW: 4, minH: 6 },
  { id: 'ops', title: 'Operations', description: 'Is the system running: the daily pipeline, health checks, the odds feed and closing prices', x: 0, y: 27, w: 12, h: 4, minW: 6, minH: 3, autoHeight: true },
]

const SWR = { cachePolicy: 'stale-while-revalidate' } as const

const EMPTY: KeyMetrics = { daily: [], clv: null, models: [], counts: null, pipeline: null, checks: null, credits: null }

export default function KeyMetricsTab({ refreshKey }: Props) {
  const q = useGetKeyMetrics(SWR)

  useRefreshLoad('exec', refreshKey, skipCache => {
    q.trigger(undefined, { skipCache }).result.catch(() => {})
  })

  const data = (q.data as KeyMetrics | undefined) ?? EMPTY
  const loading = q.loading && !q.data
  const error = q.error ?? null

  const d = useMemo(() => {
    const today = data.counts?.today_et ?? new Date().toISOString().slice(0, 10)
    const views = modelViews(data.models)
    const dates = data.daily.map(r => r.game_date).sort()
    return {
      totals: totalsOf(data.models),
      last30: windowOf(data.daily, today, 30),
      last7: windowOf(data.daily, today, 7),
      equity: equityOf(data.daily),
      buckets: bucketsOf(views),
      top: byUnits(views, 5, 'top'),
      bottom: byUnits(views, 5, 'bottom'),
      firstDate: dates[0] ?? null,
      lastDate: dates[dates.length - 1] ?? null,
    }
  }, [data])

  const renderTile = (id: string): TileRender => {
    switch (id) {
      case 'results':
        return { body: <ResultsStrip totals={d.totals} last30={d.last30} last7={d.last7} equity={d.equity} firstDate={d.firstDate} lastDate={d.lastDate} loading={loading} error={error} /> }
      case 'equity':
        return { body: <EquityChart equity={d.equity} loading={loading} error={error} /> }
      case 'clv':
        return { body: <ClvSplit clv={data.clv} loading={loading} error={error} /> }
      case 'models':
        return { body: <ModelsStrip counts={data.counts} buckets={d.buckets} loading={loading} error={error} /> }
      case 'leaders':
        return { body: <ModelList rows={d.top} loading={loading} error={error} empty="No model has a graded bet yet." /> }
      case 'laggards':
        return { body: <ModelList rows={d.bottom} loading={loading} error={error} empty="No model has a graded bet yet." /> }
      case 'ops':
        return { body: <OpsStrip pipeline={data.pipeline} checks={data.checks} credits={data.credits} clv={data.clv} loading={loading} error={error} /> }
      default:
        return { body: null }
    }
  }

  return <TabShell tab="exec" metas={EXEC_TILES} renderTile={renderTile} />
}
