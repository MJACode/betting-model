import { useCallback } from 'react'
import ModelVolume from './models/ModelVolume'
import { useGetModelVolumeBands } from '../hooks/backend/ops'
import { TabShell } from '../components/tiles/TabShell'
import { useRefreshLoad } from '../hooks/useRefreshLoad'
import { Footnote } from '../components/PanelUtils'
import type { TileMeta, TileRender } from '../components/tiles/layoutTypes'

type Props = {
  refreshKey: number
}

const VOLUME_TILES: TileMeta[] = [
  { id: 'volume', title: 'Volume', description: 'Post fewer, stronger bets from a pre-game model', x: 0, y: 0, w: 12, h: 22, minW: 8, minH: 10 },
]

export default function VolumeTab({ refreshKey }: Props) {
  const bands = useGetModelVolumeBands({ cachePolicy: 'stale-while-revalidate' })

  useRefreshLoad('volume', refreshKey, skipCache => {
    bands.trigger(undefined, { skipCache }).result.catch(() => {})
  })

  // After a volume change: re-read the bands, always from the database
  const bandsTrigger = bands.trigger
  const onVolumeChanged = useCallback(async () => {
    try {
      await bandsTrigger(undefined, { skipCache: true }).result
    } catch {
      // the bands hook surfaces its own error in the panel
    }
  }, [bandsTrigger])

  const renderTile = (id: string): TileRender => {
    if (id !== 'volume') return { body: null }
    return {
      body: (
        <>
          <Footnote>
            Pre-game models: choose how many of a model's bets get posted. In-play models are listed but cannot be adjusted yet.
            A setting never loosens a model's own cut and does not change what the model records. Bets a day are over each model's last 120 days of betting; the record is every bet at or above the band.
          </Footnote>
          <ModelVolume data={bands.data} loading={bands.loading} error={bands.error} onChanged={onVolumeChanged} />
        </>
      ),
    }
  }

  return <TabShell tab="volume" metas={VOLUME_TILES} renderTile={renderTile} />
}
