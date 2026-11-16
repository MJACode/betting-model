import AudienceTiles from './ops/AudienceTiles'
import PipelineRuns from './ops/PipelineRuns'
import HealthChecks from './ops/HealthChecks'
import WeatherBoard from './ops/WeatherBoard'
import OddsApiHealth from './ops/OddsApiHealth'
import ApiCallTrend from './ops/ApiCallTrend'
import ApiSources from './ops/ApiSources'
import {
  useGetAudienceTiles,
  useGetPipelineRuns,
  useGetHealthChecks,
  useGetWeatherBoard,
  useGetOddsApiHealth,
  useGetApiCallTrend,
  useGetApiSourceFrequency,
} from '../hooks/backend/ops'
import { TabShell } from '../components/tiles/TabShell'
import { useRefreshLoad } from '../hooks/useRefreshLoad'
import type { TileMeta, TileRender } from '../components/tiles/layoutTypes'

type Props = {
  refreshKey: number
}

const OPS_TILES: TileMeta[] = [
  { id: 'audience', title: 'Audience', description: 'Platform reach metrics', x: 0, y: 0, w: 6, h: 9, minW: 3, minH: 5, autoHeight: true },
  { id: 'oddsApi', title: 'Odds API', description: 'Credit burn on the only paid feed', x: 6, y: 0, w: 6, h: 9, minW: 3, minH: 5, autoHeight: true },
  { id: 'pipeline', title: 'Pipeline Runs', description: 'Most recent pipeline executions', x: 0, y: 9, w: 7, h: 11, minW: 4, minH: 6 },
  { id: 'apiSources', title: 'API Sources', description: 'Every feed, and how often it actually runs', x: 7, y: 9, w: 5, h: 11, minW: 3, minH: 6 },
  { id: 'health', title: 'Health Checks', description: 'Latest run, checks that are not OK', x: 0, y: 20, w: 12, h: 10, minW: 5, minH: 5 },
  { id: 'weather', title: 'Weather', description: 'Forecast coverage and conditions for upcoming MLB and NCAAF games', x: 0, y: 30, w: 12, h: 15, minW: 5, minH: 8 },
  { id: 'apiTrend', title: 'API Calls Over Time', description: 'Daily calls by source', x: 0, y: 45, w: 12, h: 11, minW: 4, minH: 7 },
]

const SWR = { cachePolicy: 'stale-while-revalidate' } as const

export default function OpsTab({ refreshKey }: Props) {
  const audience = useGetAudienceTiles(SWR)
  const pipeline = useGetPipelineRuns(SWR)
  const health = useGetHealthChecks(SWR)
  const weather = useGetWeatherBoard(SWR)
  const oddsApi = useGetOddsApiHealth(SWR)
  const apiTrend = useGetApiCallTrend(SWR)
  const apiSources = useGetApiSourceFrequency(SWR)

  useRefreshLoad('ops', refreshKey, skipCache => {
    const opts = { skipCache }
    for (const h of [audience, pipeline, health, weather, oddsApi, apiTrend, apiSources]) {
      h.trigger(undefined, opts).result.catch(() => {})
    }
  })

  const renderTile = (id: string): TileRender => {
    switch (id) {
      case 'audience':
        return { body: <AudienceTiles data={audience.data} loading={audience.loading} error={audience.error} /> }
      case 'oddsApi':
        return { body: <OddsApiHealth data={oddsApi.data} loading={oddsApi.loading} error={oddsApi.error} /> }
      case 'pipeline':
        return { body: <PipelineRuns data={pipeline.data} loading={pipeline.loading} error={pipeline.error} /> }
      case 'apiSources':
        return { body: <ApiSources data={apiSources.data} loading={apiSources.loading} error={apiSources.error} /> }
      case 'health':
        return { body: <HealthChecks data={health.data} loading={health.loading} error={health.error} /> }
      case 'weather':
        return { body: <WeatherBoard data={weather.data} loading={weather.loading} error={weather.error} /> }
      case 'apiTrend':
        return { body: <ApiCallTrend data={apiTrend.data} loading={apiTrend.loading} error={apiTrend.error} /> }
      default:
        return { body: null }
    }
  }

  return <TabShell tab="ops" metas={OPS_TILES} renderTile={renderTile} />
}
