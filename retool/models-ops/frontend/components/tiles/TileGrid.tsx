import { useMemo, type ReactNode } from 'react'
import RGL from 'react-grid-layout'
import 'react-grid-layout/css/styles.css'
import { LayoutGrid } from 'lucide-react'
import { useMediaQuery, DESKTOP_QUERY } from '../../hooks/useMediaQuery'
import { EmptyState } from '../PanelUtils'
import { cn } from '../../lib/shadcn/utils'
import { Tile } from './Tile'
import { GRID_COLS, GRID_GAP, ROW_HEIGHT, readingOrder, rowsForPixels, type TileMeta, type TileRender } from './layoutTypes'
import type { TabLayouts } from './useTabLayouts'

const Grid = RGL.WidthProvider(RGL)

export function TileGrid({
  layouts,
  renderTile,
}: {
  layouts: TabLayouts
  renderTile: (id: string) => TileRender
}) {
  const desktop = useMediaQuery(DESKTOP_QUERY)
  const { working, metas, arrange } = layouts
  const metaById = useMemo(() => new Map(metas.map(m => [m.id, m])), [metas])
  const visible = useMemo(() => working.filter(t => !t.hidden && metaById.has(t.id)), [working, metaById])
  const fitTileHeight = layouts.fitTileHeight
  // Stable per-tile callbacks so each measurer subscribes once.
  const measurers = useMemo(() => {
    const map = new Map<string, (px: number) => void>()
    for (const m of metas) {
      if (m.autoHeight) map.set(m.id, (px: number) => fitTileHeight(m.id, rowsForPixels(px)))
    }
    return map
  }, [metas, fitTileHeight])

  if (visible.length === 0) {
    return (
      <EmptyState icon={LayoutGrid} title="All tiles are hidden">
        Use the Tiles menu above to bring them back.
      </EmptyState>
    )
  }

  const frame = (meta: TileMeta, width: number, canDrag: boolean): ReactNode => {
    const r = renderTile(meta.id)
    return (
      <Tile
        meta={meta}
        width={width}
        arranging={arrange}
        canDrag={canDrag}
        actions={r.actions}
        onHide={() => layouts.hideTile(meta.id)}
        onSize={w => layouts.setTileWidth(meta.id, w)}
        onMeasure={canDrag ? measurers.get(meta.id) : undefined}
      >
        {r.body}
      </Tile>
    )
  }

  // Narrow screens: one column in layout order, no dragging.
  if (!desktop) {
    return (
      <div className="tiles-stacked flex flex-col gap-4">
        {readingOrder(visible).map(t => {
          const meta = metaById.get(t.id)
          return meta ? <div key={t.id}>{frame(meta, t.w, false)}</div> : null
        })}
      </div>
    )
  }

  const gridLayout = visible.map(t => {
    const meta = metaById.get(t.id)
    return {
      i: t.id,
      x: t.x,
      y: t.y,
      w: t.w,
      h: t.h,
      minW: meta?.minW ?? 2,
      minH: meta?.autoHeight ? 1 : (meta?.minH ?? 3),
      // Content-fitted tiles only resize sideways; their height follows the content.
      resizeHandles: meta?.autoHeight ? (['e'] as Array<'e'>) : (['se'] as Array<'se'>),
    }
  })

  return (
    <Grid
      className={cn('tiles-grid', arrange && 'tiles-arranging')}
      layout={gridLayout}
      cols={GRID_COLS}
      rowHeight={ROW_HEIGHT}
      margin={[GRID_GAP, GRID_GAP]}
      containerPadding={[0, 0]}
      isDraggable={arrange}
      isResizable={arrange}
      draggableHandle=".tile-drag-handle"
      draggableCancel=".tile-no-drag"
      resizeHandles={['se']}
      compactType="vertical"
      useCSSTransforms
      onLayoutChange={items => layouts.syncPositions(items)}
      onDragStop={() => layouts.markDirty()}
      onResizeStop={() => layouts.markDirty()}
    >
      {visible.map(t => {
        const meta = metaById.get(t.id)
        return <div key={t.id}>{meta ? frame(meta, t.w, true) : null}</div>
      })}
    </Grid>
  )
}
