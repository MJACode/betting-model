import { useModelNames } from './modelNames'
import { PausedBadge } from '../StatusBadge'
import { cn } from '../../lib/shadcn/utils'

/**
 * A model as people should see it: the friendly name, with the raw id beneath
 * in small muted monospace. `compact` shows the short name only and moves the
 * full name and id into the hover tooltip, for chips and other tight spots.
 */
export function ModelName({
  id,
  compact = false,
  paused,
  className,
}: {
  id: string
  compact?: boolean
  /** Pass when the panel knows; otherwise any state shared by other panels is used. */
  paused?: boolean | undefined
  className?: string | undefined
}) {
  const ctx = useModelNames()
  const label = ctx.modelLabel(id)
  const isPaused = paused ?? ctx.isPaused(id) ?? false

  if (compact) {
    return (
      <span className={cn('truncate', className)} title={`${label.name}\n${id}${isPaused ? '\nPaused' : ''}`}>
        {label.shortName}
      </span>
    )
  }

  return (
    <div className={cn('min-w-0', className)}>
      <div className="flex min-w-0 items-center gap-1.5">
        <span className="truncate text-[13px] font-medium text-foreground" title={label.name}>{label.name}</span>
        {isPaused && <PausedBadge />}
      </div>
      <div className="truncate font-mono text-[11px] leading-4 text-muted-foreground" title={id}>{id}</div>
    </div>
  )
}
