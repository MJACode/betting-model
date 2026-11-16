import { useMemo } from 'react'
import { ArrowUp, ArrowDown, Equal, Check, X, Minus, Clock, Ban, CircleDashed } from 'lucide-react'
import { Badge } from '../../components/StatusBadge'
import { Chip } from '../../components/PanelUtils'
import type { ClvOutcome } from './picksUtils'

export function ClvBadge({ outcome }: { outcome: ClvOutcome }) {
  switch (outcome) {
    case 'BEAT': return <Badge tone="info" icon={ArrowUp}>Beat</Badge>
    case 'WORSE': return <Badge tone="critical" icon={ArrowDown}>Worse</Badge>
    case 'FLAT': return <Badge tone="neutral" icon={Equal}>Flat</Badge>
    case 'NOT_MEASURED': return <Badge tone="outline">Not measured</Badge>
    case 'UNRESOLVED': return <Badge tone="outline">Unresolved</Badge>
  }
}

export function ResultBadge({ result, isUnpriced }: { result: string | null; isUnpriced?: boolean }) {
  if (!result) return <Badge tone="outline" icon={Clock}>Unsettled</Badge>
  if (isUnpriced) {
    return (
      <Badge
        tone="outline"
        icon={CircleDashed}
        title="No DraftKings price at pick time, so this pick has no units. Its P&L is deliberately not fabricated."
      >
        Unpriced
      </Badge>
    )
  }
  const r = result.toUpperCase()
  if (r === 'NO_ACTION') return <Badge tone="outline" icon={Ban}>Void</Badge>
  if (r === 'WIN') return <Badge tone="good" icon={Check}>Win</Badge>
  if (r === 'LOSS') return <Badge tone="critical" icon={X}>Loss</Badge>
  if (r === 'PUSH') return <Badge tone="neutral" icon={Minus}>Push</Badge>
  return <Badge tone="neutral">{r}</Badge>
}

// Multi-select toggle chip group
type ToggleOption<T extends string> = { value: T; label: string }

type MultiToggleProps<T extends string> = {
  options: ToggleOption<T>[]
  value: T[]
  onChange: (v: T[]) => void
  label?: string
}

export function MultiToggle<T extends string>({ options, value, onChange, label }: MultiToggleProps<T>) {
  const set = useMemo(() => new Set(value), [value])

  function toggle(v: T) {
    if (set.has(v)) onChange(value.filter(x => x !== v))
    else onChange([...value, v])
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {label && <span className="mr-0.5 text-xs font-medium text-muted-foreground">{label}</span>}
      {options.map(o => (
        <Chip key={o.value} active={set.has(o.value)} onClick={() => toggle(o.value)}>{o.label}</Chip>
      ))}
    </div>
  )
}
