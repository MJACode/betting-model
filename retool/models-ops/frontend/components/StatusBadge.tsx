import type { ReactNode } from 'react'
import {
  CheckCircle2, PauseCircle, AlertTriangle, XCircle, MinusCircle, Clock, Activity, Sparkles, Cpu, Radio,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '../lib/shadcn/utils'

/**
 * The one badge used across the dashboard: model states, Paused, In-play and
 * check statuses. Status tones (good / warning / critical) always carry an icon
 * and a text label, so colour is never the only signal.
 */
export type BadgeTone = 'neutral' | 'outline' | 'info' | 'good' | 'warning' | 'critical'

const toneClasses: Record<BadgeTone, string> = {
  neutral: 'bg-muted text-secondary-fg border-border',
  outline: 'bg-transparent text-muted-foreground border-border',
  info: 'bg-brand-soft text-brand border-brand',
  good: 'bg-good-soft text-good border-good',
  warning: 'bg-warn-soft text-warn border-warn',
  critical: 'bg-crit-soft text-crit border-crit',
}

export function Badge({
  tone = 'neutral',
  icon: Icon,
  children,
  title,
  className,
}: {
  tone?: BadgeTone
  icon?: LucideIcon | undefined
  children: ReactNode
  title?: string | undefined
  className?: string | undefined
}) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-[1px] text-[11px] font-medium leading-[18px]',
        toneClasses[tone],
        className,
      )}
    >
      {Icon && <Icon className="h-3 w-3 shrink-0" aria-hidden />}
      {children}
    </span>
  )
}

export function PausedBadge() {
  return <Badge tone="neutral" icon={PauseCircle}>Paused</Badge>
}

export function InPlayBadge() {
  return <Badge tone="info" icon={Radio}>In-play</Badge>
}

type Variant =
  | 'live' | 'paused' | 'no-artifact' | 'rules-based' | 'engine'
  | 'ok' | 'warn' | 'crit' | 'skipped' | 'stale' | 'error' | 'muted' | 'running'

const variantTone: Record<Variant, { tone: BadgeTone; icon?: LucideIcon }> = {
  live: { tone: 'good', icon: CheckCircle2 },
  paused: { tone: 'neutral', icon: PauseCircle },
  'no-artifact': { tone: 'critical', icon: AlertTriangle },
  'rules-based': { tone: 'info', icon: Sparkles },
  engine: { tone: 'info', icon: Cpu },
  ok: { tone: 'good', icon: CheckCircle2 },
  warn: { tone: 'warning', icon: AlertTriangle },
  crit: { tone: 'critical', icon: XCircle },
  skipped: { tone: 'outline', icon: MinusCircle },
  stale: { tone: 'warning', icon: Clock },
  error: { tone: 'critical', icon: XCircle },
  muted: { tone: 'neutral' },
  running: { tone: 'info', icon: Activity },
}

export function StatusBadge({ label, variant }: { label: string; variant: Variant }) {
  const v = variantTone[variant]
  return <Badge tone={v.tone} icon={v.icon}>{label}</Badge>
}

/** Model state as people read it: "Live", "Rules based", "No artifact"… */
export function stateLabel(state: string): string {
  const s = state.toLowerCase()
  return s.charAt(0).toUpperCase() + s.slice(1)
}

export function ModelStateBadge({ state }: { state: string }) {
  return <StatusBadge label={stateLabel(state)} variant={stateVariant(state)} />
}

export function stateVariant(state: string): Variant {
  if (state === 'LIVE') return 'live'
  if (state === 'PAUSED') return 'paused'
  if (state === 'NO ARTIFACT') return 'no-artifact'
  if (state === 'RULES BASED') return 'rules-based'
  if (state === 'ENGINE') return 'engine'
  return 'muted'
}

export function severityVariant(severity: string): Variant {
  if (severity === 'CRIT') return 'crit'
  if (severity === 'WARN') return 'warn'
  return 'muted'
}

export function statusVariant(status: string): Variant {
  if (status === 'OK') return 'ok'
  if (status === 'STALE') return 'stale'
  if (status === 'SKIPPED') return 'skipped'
  if (status === 'ERROR') return 'error'
  return 'muted'
}
