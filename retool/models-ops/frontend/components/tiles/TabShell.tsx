import type { ReactNode } from 'react'
import { TabToolbar, TabToolbarStatus } from './TabToolbar'
import { TileGrid } from './TileGrid'
import { useTabLayouts } from './useTabLayouts'
import { TAB_META, type TabId, type TileMeta, type TileRender } from './layoutTypes'

/** A tab: its heading with the layout controls, optional pinned content (not a tile), then the tile grid. */
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
  const meta = TAB_META[tab]
  return (
    <div className="space-y-4 px-4 pb-6 pt-6 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <h1 className="text-[22px] font-semibold leading-tight tracking-tight text-foreground">{meta.title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{meta.description}</p>
        </div>
        <TabToolbar layouts={layouts} />
      </div>
      <TabToolbarStatus layouts={layouts} />
      {pinned}
      <TileGrid layouts={layouts} renderTile={renderTile} />
    </div>
  )
}
