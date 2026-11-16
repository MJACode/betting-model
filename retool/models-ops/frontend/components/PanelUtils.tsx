import type { ReactNode } from 'react'
import { AlertCircle, ChevronUp, ChevronDown, ChevronsUpDown, Inbox, type LucideIcon } from 'lucide-react'
import { Skeleton } from '../lib/shadcn/skeleton'
import { cn } from '../lib/shadcn/utils'

// ---------- States: error, loading, empty ----------

export function PanelError({ message }: { message: string }) {
  return (
    <div role="alert" className="flex items-start gap-2 rounded-lg border border-crit bg-crit-soft p-3 text-sm text-crit">
      <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden />
      <span className="break-all font-mono text-xs leading-relaxed">{message}</span>
    </div>
  )
}

/** Skeleton shaped like a table: a header bar and a few rows. */
export function TableSkeleton({ rows = 6, toolbar = true }: { rows?: number; toolbar?: boolean }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading">
      {toolbar && (
        <div className="flex gap-2">
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-8 w-24" />
        </div>
      )}
      <div className="overflow-hidden rounded-[10px] border">
        <Skeleton className="h-9 rounded-none" />
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 border-t px-3 py-3">
            <Skeleton className="h-3.5 w-1/4" />
            <Skeleton className="h-3.5 w-1/6" />
            <Skeleton className="h-3.5 w-1/5" />
            <Skeleton className="ml-auto h-3.5 w-12" />
          </div>
        ))}
      </div>
    </div>
  )
}

export function ChartSkeleton({ height = 260 }: { height?: number }) {
  return (
    <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-7 w-48" />
      <Skeleton className="w-full rounded-[10px]" style={{ height }} />
    </div>
  )
}

export function StatsSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6" aria-busy="true" aria-label="Loading">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="space-y-2 rounded-[10px] border bg-raised p-4">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-7 w-16" />
          <Skeleton className="h-3 w-24" />
        </div>
      ))}
    </div>
  )
}

/** Kept for callers that only need a generic loading block. */
export function PanelLoading({ label: _label }: { label?: string }) {
  return <TableSkeleton rows={4} />
}

export function EmptyState({
  title,
  children,
  icon: Icon = Inbox,
  className,
}: {
  title: string
  children?: ReactNode
  icon?: LucideIcon
  className?: string
}) {
  return (
    <div className={cn('flex flex-col items-center justify-center gap-1.5 rounded-[10px] border border-dashed px-6 py-10 text-center', className)}>
      <Icon className="h-5 w-5 text-muted-foreground" aria-hidden />
      <p className="text-sm font-medium text-foreground">{title}</p>
      {children && <p className="max-w-md text-xs text-muted-foreground">{children}</p>}
    </div>
  )
}

// ---------- Small building blocks ----------

export function NullCell() {
  return <span className="text-muted-foreground/60">—</span>
}

export function SortIcon({ sorted }: { sorted: false | 'asc' | 'desc' }) {
  if (!sorted) return <ChevronsUpDown className="h-3 w-3 text-muted-foreground/50" />
  if (sorted === 'asc') return <ChevronUp className="h-3 w-3" />
  return <ChevronDown className="h-3 w-3" />
}

/** Plain-words note under a panel. */
export function Footnote({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('text-xs leading-relaxed text-muted-foreground', className)}>
      {children}
    </div>
  )
}

/** Toggle chip used for filters (sport, timing, metric). */
export function Chip({
  active,
  onClick,
  children,
  title,
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
  title?: string | undefined
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-pressed={active}
      className={cn(
        'inline-flex h-7 items-center rounded-full border px-2.5 text-xs font-medium transition-colors',
        active
          ? 'border-primary bg-primary text-primary-foreground'
          : 'border-border bg-card text-secondary-fg hover:border-foreground/30 hover:bg-muted',
      )}
    >
      {children}
    </button>
  )
}

export function ChipGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="mr-1 w-16 shrink-0 text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </div>
  )
}

export type StatTone = 'good' | 'warning' | 'critical'

/**
 * Big number, label and caption. A tone is only for real status and is always
 * paired with the icon passed in, never colour alone.
 */
export function StatCard({
  label,
  value,
  caption,
  tone,
  icon: Icon,
  onClick,
  active,
  title,
  className,
}: {
  label: ReactNode
  value: ReactNode
  caption?: ReactNode
  tone?: StatTone | undefined
  icon?: LucideIcon | undefined
  onClick?: (() => void) | undefined
  active?: boolean | undefined
  title?: string | undefined
  className?: string | undefined
}) {
  const toneText = tone === 'good' ? 'text-good' : tone === 'warning' ? 'text-warn' : tone === 'critical' ? 'text-crit' : 'text-foreground'
  const toneBorder = tone === 'good' ? 'border-good' : tone === 'warning' ? 'border-warn' : tone === 'critical' ? 'border-crit' : ''
  const body = (
    <>
      <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        {Icon && <Icon className={cn('h-3.5 w-3.5', tone ? toneText : 'text-muted-foreground')} aria-hidden />}
        {label}
      </span>
      <span className={cn('mt-1 text-2xl font-semibold leading-tight tracking-tight', toneText)}>{value}</span>
      {caption && <span className="mt-0.5 text-xs text-muted-foreground">{caption}</span>}
    </>
  )
  const base = cn(
    'flex min-w-0 flex-col items-start rounded-[10px] border bg-raised px-4 py-3 text-left',
    toneBorder,
    className,
  )
  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        title={title}
        aria-pressed={active}
        className={cn(base, 'transition-all hover:border-foreground/25 hover:bg-muted/60', active && 'ring-2 ring-primary ring-offset-1 ring-offset-card')}
      >
        {body}
      </button>
    )
  }
  return <div className={base} title={title}>{body}</div>
}

// ---------- Formatting ----------

export function fmtPct(val: string | null | undefined, dp = 1): string {
  if (val == null || val === '') return '—'
  const n = parseFloat(val)
  if (isNaN(n)) return '—'
  return n.toFixed(dp) + '%'
}

export function fmtUnits(val: string | null | undefined): string {
  if (val == null || val === '') return '—'
  const n = parseFloat(val)
  if (isNaN(n)) return '—'
  return (n >= 0 ? '+' : '') + n.toFixed(2) + 'u'
}

/** Text colour for a signed units / ROI number (the sign is always shown too). */
export function signedClass(n: number | null | undefined): string {
  if (n == null || n === 0 || isNaN(n)) return 'text-foreground'
  return n > 0 ? 'text-good' : 'text-crit'
}

export function fmtDate(val: string | null | undefined): string {
  if (!val) return '—'
  // Handles both 'YYYY-MM-DD' and ISO timestamps
  const d = val.length === 10 ? new Date(val + 'T00:00:00Z') : new Date(val)
  if (isNaN(d.getTime())) return val
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })
}

export function fmtDateTime(val: string | null | undefined): string {
  if (!val) return '—'
  const d = new Date(val)
  if (isNaN(d.getTime())) return val
  return d.toLocaleString('en-US', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  })
}

export function fmtDuration(start: string | null, end: string | null): string {
  if (!start || !end) return '—'
  const ms = new Date(end).getTime() - new Date(start).getTime()
  if (isNaN(ms) || ms < 0) return '—'
  const secs = Math.floor(ms / 1000)
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}
