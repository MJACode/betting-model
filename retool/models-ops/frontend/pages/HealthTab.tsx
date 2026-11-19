import { useEffect, useMemo, useState } from 'react'
import { useGetModelHealthSummary, useGetModelHealthWindows, useGetModelHealthBets } from '../hooks/backend/ops'
import { TabShell } from '../components/tiles/TabShell'
import { useRefreshLoad } from '../hooks/useRefreshLoad'
import { Chip } from '../components/PanelUtils'
import type { TileMeta, TileRender } from '../components/tiles/layoutTypes'
import HealthCoverage from './health/HealthCoverage'
import HealthOverview from './health/HealthOverview'
import HealthBlocks from './health/HealthBlocks'
import HealthRolling from './health/HealthRolling'
import { BLOCK_SIZES, int, type BetRow, type BlockSize, type SummaryRow, type WindowRow } from './health/healthUtils'

type Props = { refreshKey: number }

const HEALTH_TILES: TileMeta[] = [
  { id: 'coverage', title: 'What each bet’s close is measured against', description: 'Every published bet since the live date, by whether a closing price exists for it', x: 0, y: 0, w: 12, h: 6, minW: 6, minH: 4, autoHeight: true },
  { id: 'overview', title: 'Every model', description: 'Closing-line value over each model’s bets and its newest 25, 50 and 100. Click a model to open it below', x: 0, y: 6, w: 12, h: 18, minW: 6, minH: 8 },
  { id: 'blocks', title: 'Blocks', description: 'The selected model’s newest 500 bets in blocks of 25, 50 or 100', x: 0, y: 24, w: 12, h: 19, minW: 6, minH: 8 },
  { id: 'rolling', title: 'Rolling CLV', description: 'The selected model’s average CLV over its last 25, 50 or 100 bets, one point per bet', x: 0, y: 43, w: 12, h: 16, minW: 5, minH: 8 },
]

const SWR = { cachePolicy: 'stale-while-revalidate' } as const

function asRows<T>(data: unknown): T[] {
  return Array.isArray(data) ? (data as T[]) : []
}

export default function HealthTab({ refreshKey }: Props) {
  const summary = useGetModelHealthSummary(SWR)
  const windows = useGetModelHealthWindows(SWR)
  const bets = useGetModelHealthBets(SWR)

  useRefreshLoad('health', refreshKey, skipCache => {
    const opts = { skipCache }
    summary.trigger(undefined, opts).result.catch(() => {})
    windows.trigger(undefined, opts).result.catch(() => {})
    bets.trigger(undefined, opts).result.catch(() => {})
  })

  const summaryRows = useMemo(() => asRows<SummaryRow>(summary.data), [summary.data])
  const windowRows = useMemo(() => asRows<WindowRow>(windows.data), [windows.data])
  const betRows = useMemo(() => asRows<BetRow>(bets.data), [bets.data])

  const [selected, setSelected] = useState<string | null>(null)
  const [blockSize, setBlockSize] = useState<BlockSize>(25)
  const [rollSize, setRollSize] = useState<BlockSize>(25)

  // First load: open the pre-game model with the most bets.
  useEffect(() => {
    if (selected != null || summaryRows.length === 0) return
    const pregame = summaryRows.filter(r => int(r.in_play) < int(r.bets))
    const pool = pregame.length > 0 ? pregame : summaryRows
    const top = [...pool].sort((a, b) => int(b.bets) - int(a.bets))[0]
    if (top) setSelected(top.model_id)
  }, [selected, summaryRows])

  const selectedBets = useMemo(() => betRows.filter(b => b.model_id === selected), [betRows, selected])
  const selectedSummary = useMemo(() => summaryRows.find(r => r.model_id === selected), [summaryRows, selected])

  const sizeChips = (value: BlockSize, set: (s: BlockSize) => void) => (
    <div className="flex items-center gap-1">
      {BLOCK_SIZES.map(s => (
        <Chip key={s} active={value === s} onClick={() => set(s)} title={`${s} bets`}>
          {s}
        </Chip>
      ))}
    </div>
  )

  const renderTile = (id: string): TileRender => {
    switch (id) {
      case 'coverage':
        return { body: <HealthCoverage rows={summaryRows} loading={summary.loading && summaryRows.length === 0} error={summary.error} /> }
      case 'overview':
        return {
          body: (
            <HealthOverview
              rows={summaryRows}
              windows={windowRows}
              loading={(summary.loading && summaryRows.length === 0) || (windows.loading && windowRows.length === 0)}
              error={summary.error ?? windows.error}
              selected={selected}
              onSelect={setSelected}
            />
          ),
        }
      case 'blocks':
        return {
          actions: sizeChips(blockSize, setBlockSize),
          body: (
            <HealthBlocks
              modelId={selected}
              summary={selectedSummary}
              windows={windowRows}
              size={blockSize}
              loading={windows.loading && windowRows.length === 0}
              error={windows.error}
            />
          ),
        }
      case 'rolling':
        return {
          actions: sizeChips(rollSize, setRollSize),
          body: (
            <HealthRolling
              modelId={selected}
              bets={selectedBets}
              size={rollSize}
              loading={bets.loading && betRows.length === 0}
              error={bets.error}
            />
          ),
        }
      default:
        return { body: null }
    }
  }

  return <TabShell tab="health" metas={HEALTH_TILES} renderTile={renderTile} />
}
