import ModelRoster from './models/ModelRoster'
import SettledPerformance from './models/SettledPerformance'
import ThresholdWhatIf from './models/ThresholdWhatIf'
import PicksTimeSeries from './models/PicksTimeSeries'
import { useGetModelRoster, useGetSettledPerformance, useGetPicksTimeSeries } from '../hooks/backend/ops'
import { TabShell } from '../components/tiles/TabShell'
import { useRefreshLoad } from '../hooks/useRefreshLoad'
import type { TileMeta, TileRender } from '../components/tiles/layoutTypes'

type Props = {
  refreshKey: number
}

// Built-in Default layout: most-used first.
const MODELS_TILES: TileMeta[] = [
  { id: 'roster', title: 'Model Roster', description: 'Every model, its state and its live thresholds', x: 0, y: 0, w: 12, h: 20, minW: 6, minH: 8 },
  { id: 'performance', title: 'Settled Performance', description: 'Settled bets graded by the database view; covers only the markets it grades', x: 0, y: 20, w: 12, h: 13, minW: 5, minH: 6 },
  { id: 'whatif', title: 'Threshold What-If', description: 'Recompute a model at its live thresholds, or try your own', x: 0, y: 33, w: 12, h: 14, minW: 5, minH: 8 },
  { id: 'picks', title: 'Picks per Model (14 days)', description: 'Daily scored picks and bets, pre-game only', x: 0, y: 47, w: 12, h: 11, minW: 4, minH: 7 },
]

const SWR = { cachePolicy: 'stale-while-revalidate' } as const

export default function ModelsTab({ refreshKey }: Props) {
  const roster = useGetModelRoster(SWR)
  const perf = useGetSettledPerformance(SWR)
  const picks = useGetPicksTimeSeries(SWR)

  useRefreshLoad('models', refreshKey, skipCache => {
    const opts = { skipCache }
    roster.trigger(undefined, opts).result.catch(() => {})
    perf.trigger(undefined, opts).result.catch(() => {})
    picks.trigger(undefined, opts).result.catch(() => {})
  })

  const renderTile = (id: string): TileRender => {
    switch (id) {
      case 'roster':
        return { body: <ModelRoster data={roster.data} loading={roster.loading} error={roster.error} /> }
      case 'performance':
        return {
          body: (
            <SettledPerformance
              data={perf.data}
              loading={perf.loading}
              error={perf.error}
              rosterIds={Array.isArray(roster.data) ? (roster.data as Array<{ model_id: string }>).map(r => r.model_id) : undefined}
            />
          ),
        }
      case 'whatif':
        return { body: <ThresholdWhatIf rosterData={roster.data} perfData={perf.data} loading={roster.loading || perf.loading} /> }
      case 'picks':
        return { body: <PicksTimeSeries data={picks.data} loading={picks.loading} error={picks.error} /> }
      default:
        return { body: null }
    }
  }

  return <TabShell tab="models" metas={MODELS_TILES} renderTile={renderTile} />
}
