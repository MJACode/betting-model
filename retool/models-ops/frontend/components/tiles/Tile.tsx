import { useEffect, useRef, type ReactNode } from 'react'
import { GripVertical, MoreHorizontal, EyeOff } from 'lucide-react'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '../../lib/shadcn/dropdown-menu'
import { cn } from '../../lib/shadcn/utils'
import { SIZE_PRESETS, type TileMeta } from './layoutTypes'

export function Tile({
  meta,
  width,
  arranging,
  canDrag,
  actions,
  onHide,
  onSize,
  onMeasure,
  children,
}: {
  meta: TileMeta
  width: number
  arranging: boolean
  canDrag: boolean
  actions?: ReactNode
  onHide: () => void
  onSize: (w: number) => void
  /** Reports the tile's natural height in pixels (content-fitted tiles only). */
  onMeasure?: ((px: number) => void) | undefined
  children: ReactNode
}) {
  const dragging = arranging && canDrag
  const presetKey = SIZE_PRESETS.find(p => p.w === width)?.key ?? ''
  const headerRef = useRef<HTMLElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!onMeasure) return
    const header = headerRef.current
    const content = contentRef.current
    if (!header || !content) return
    // header + content + body bottom padding (20px) + top/bottom border (2px)
    const report = () => onMeasure(header.offsetHeight + content.offsetHeight + 22)
    report()
    const ro = new ResizeObserver(report)
    ro.observe(header)
    ro.observe(content)
    return () => ro.disconnect()
  }, [onMeasure])

  return (
    <section className="tile flex h-full min-h-0 flex-col" aria-label={meta.title}>
      <header ref={headerRef} className="flex items-start gap-2 px-5 pb-3 pt-4">
        {dragging && (
          <span className="tile-drag-handle -ml-1.5 mt-0.5 cursor-grab rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground active:cursor-grabbing" title="Drag to move">
            <GripVertical className="h-4 w-4" aria-hidden />
          </span>
        )}
        <div className={cn('min-w-0 flex-1', dragging && 'tile-drag-handle cursor-grab active:cursor-grabbing')}>
          <h2 className="truncate text-[15px] font-semibold leading-snug text-foreground">{meta.title}</h2>
          <p className="truncate text-xs text-muted-foreground" title={meta.description}>{meta.description}</p>
        </div>
        {actions && <div className="tile-no-drag flex shrink-0 items-center gap-1.5">{actions}</div>}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="tile-no-drag -mr-1.5 rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              aria-label={`${meta.title} options`}
            >
              <MoreHorizontal className="h-4 w-4" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-44">
            <DropdownMenuItem onSelect={onHide} className="gap-2 text-sm">
              <EyeOff className="h-3.5 w-3.5" />
              Hide tile
            </DropdownMenuItem>
            {dragging && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuLabel className="text-xs font-medium text-muted-foreground">Size</DropdownMenuLabel>
                <DropdownMenuRadioGroup
                  value={presetKey}
                  onValueChange={key => {
                    const p = SIZE_PRESETS.find(s => s.key === key)
                    if (p) onSize(p.w)
                  }}
                >
                  {SIZE_PRESETS.map(p => (
                    <DropdownMenuRadioItem key={p.key} value={p.key} className="text-sm">
                      {p.label}
                    </DropdownMenuRadioItem>
                  ))}
                </DropdownMenuRadioGroup>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </header>
      <div className="tile-body flex min-h-0 flex-1 flex-col gap-4 overflow-auto px-5 pb-5">
        {onMeasure ? (
          <div ref={contentRef} className="flex shrink-0 flex-col gap-4">{children}</div>
        ) : children}
      </div>
    </section>
  )
}
