import type { ReactNode } from 'react'
import { TabToolbar } from './TabToolbar'
import { TileGrid } from './TileGrid'
import { useTabLayouts } from './useTabLayouts'
import type { TabId, TileMeta, TileRender } from './layoutTypes'

/** A tab: layout bar, optional pinned content (not a tile), then the tile grid. */
export function TabShell({
  tab,
  metas,
  renderTile,
  pinned,
}: {
  tab: TabId
  metas: TileMeta[]
  renderTile: (id: string) => TileRender
  pinned?: ReactNode
}) {
  const layouts = useTabLayouts(tab, metas)
  return (
    <div className="space-y-4 px-4 py-5 sm:px-6">
      <TabToolbar layouts={layouts} />
      {pinned}
      <TileGrid layouts={layouts} renderTile={renderTile} />
    </div>
  )
}
