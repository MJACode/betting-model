import { useMemo, useState, useRef, useEffect } from 'react'
import { X, ChevronDown, Calendar, Search } from 'lucide-react'
import { Button } from '../../lib/shadcn/button'
import { cn } from '../../lib/shadcn/utils'
import { type FilterState, type ClvOutcome, type Lane, defaultFilter, type PickRow } from './picksUtils'
import { MultiToggle } from './PicksAtoms'
import { Chip } from '../../components/PanelUtils'
import { PausedBadge } from '../../components/StatusBadge'
import { useModelNames, distinctLabels } from '../../components/models/modelNames'

const CLV_OPTIONS: { value: ClvOutcome; label: string }[] = [
  { value: 'BEAT', label: 'Beat' },
  { value: 'FLAT', label: 'Flat' },
  { value: 'WORSE', label: 'Worse' },
  { value: 'LINE_FOR', label: 'Line moved our way' },
  { value: 'LINE_AGAINST', label: 'Line moved against' },
  { value: 'NOT_MEASURED', label: 'Not measured' },
]

const RESULT_OPTIONS = [
  { value: 'WIN', label: 'Win' },
  { value: 'LOSS', label: 'Loss' },
  { value: 'PUSH', label: 'Push' },
  { value: 'NO_ACTION', label: 'Void' },
  { value: 'UNPRICED', label: 'Unpriced' },
  { value: 'UNSETTLED', label: 'Unsettled' },
]

const PICK_TYPE_OPTIONS: { value: Lane; label: string }[] = [
  { value: 'pregame', label: 'Pre-game' },
  { value: 'live', label: 'In-play' },
  { value: 'repair', label: 'Re-priced props' },
]

// ET-based "today" — never UTC
function todayStr(): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date()) // en-CA yields YYYY-MM-DD
}

// Subtract N days using a noon-UTC anchor so DST never shifts the boundary
function subtractDays(dateStr: string, n: number): string {
  const d = new Date(dateStr + 'T12:00:00Z')
  d.setUTCDate(d.getUTCDate() - n)
  return d.toISOString().slice(0, 10)
}

// First day of current month (derived from ET today)
function thisMonthStart(): string {
  return todayStr().slice(0, 7) + '-01'
}

// YYYY-MM-DD validator
function isCompleteDate(s: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(s)
}

type Props = {
  rows: PickRow[]
  filtered: number
  filter: FilterState
  onChange: (f: FilterState) => void
  /** Derived from loaded row min(game_date) */
  dataMin: string
  /** Derived from loaded row max(game_date) */
  dataMax: string
}

type Option = { value: string; label: string; sub?: string; paused?: boolean }

// Searchable multi-select dropdown; search matches the label, the value and the sub line.
function MultiSelect({
  label,
  options,
  value,
  onChange,
  width = 260,
}: {
  label: string
  options: Option[]
  value: string[]
  onChange: (v: string[]) => void
  width?: number
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (q === '') return options
    return options.filter(o =>
      o.label.toLowerCase().includes(q) || o.value.toLowerCase().includes(q) || (o.sub ?? '').toLowerCase().includes(q),
    )
  }, [options, search])

  const set = useMemo(() => new Set(value), [value])

  function toggle(o: string) {
    if (set.has(o)) onChange(value.filter(x => x !== o))
    else onChange([...value, o])
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        className={cn(
          'flex h-8 items-center gap-1 rounded-md border px-2.5 text-xs font-medium transition-colors',
          value.length > 0
            ? 'border-brand bg-brand-soft text-brand'
            : 'border-border bg-card text-secondary-fg hover:bg-muted',
        )}
      >
        {value.length === 0 ? label : `${label} (${value.length})`}
        <ChevronDown className="ml-0.5 h-3 w-3" />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 rounded-lg border bg-popover shadow-retool-lg" style={{ width }}>
          <div className="border-b p-1.5">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground" aria-hidden />
              <input
                className="w-full rounded-md border bg-background py-1 pl-6 pr-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
                placeholder="Search by name or id…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                autoFocus
              />
            </div>
          </div>
          <div className="max-h-64 overflow-y-auto p-1">
            {filtered.length === 0 && (
              <div className="px-2 py-1.5 text-xs text-muted-foreground">Nothing matches that search.</div>
            )}
            {filtered.map(o => (
              <label key={o.value} className="flex cursor-pointer items-start gap-2 rounded-md px-2 py-1.5 text-xs hover:bg-muted">
                <input
                  type="checkbox"
                  checked={set.has(o.value)}
                  onChange={() => toggle(o.value)}
                  className="mt-0.5 h-3 w-3 accent-primary"
                />
                <span className="min-w-0">
                  <span className="flex items-center gap-1.5">
                    <span className="truncate font-medium text-foreground">{o.label}</span>
                    {o.paused && <PausedBadge />}
                  </span>
                  {o.sub && <span className="block truncate font-mono text-[11px] text-muted-foreground">{o.sub}</span>}
                </span>
              </label>
            ))}
          </div>
          {value.length > 0 && (
            <div className="border-t p-1">
              <button
                type="button"
                onClick={() => { onChange([]); setSearch('') }}
                className="w-full py-1 text-xs text-muted-foreground hover:text-foreground"
              >
                Clear selection
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Date range control: derived bounds, draft state committed on blur or a complete date.
// Takes a single onChangeRange so both keys are written atomically (no stale spread).
function DateRangeControl({
  dateFrom,
  dateTo,
  dataMin,
  dataMax,
  onChangeRange,
}: {
  dateFrom: string
  dateTo: string
  dataMin: string
  dataMax: string
  onChangeRange: (from: string, to: string) => void
}) {
  const [draftFrom, setDraftFrom] = useState(dateFrom)
  const [draftTo, setDraftTo] = useState(dateTo)

  // Sync drafts when parent resets or a preset fires
  useEffect(() => { setDraftFrom(dateFrom) }, [dateFrom])
  useEffect(() => { setDraftTo(dateTo) }, [dateTo])

  const hasRange = dateFrom !== '' || dateTo !== ''

  // Presets set open-ended to: '' so they stay correct as data grows
  // and the active-state comparison is stable
  const presets = useMemo(() => [
    { label: 'Last 7d', from: subtractDays(todayStr(), 7), to: '' },
    { label: 'Last 30d', from: subtractDays(todayStr(), 30), to: '' },
    { label: 'This month', from: thisMonthStart(), to: '' },
    { label: 'All time', from: '', to: '' },
  ], [])

  function commitFrom(val: string) {
    if (val === '' || isCompleteDate(val)) onChangeRange(val, dateTo)
  }
  function commitTo(val: string) {
    if (val === '' || isCompleteDate(val)) onChangeRange(dateFrom, val)
  }

  const inputCls = 'h-8 w-[130px] rounded-md border bg-card px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring'

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Calendar className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" aria-hidden />
      <div className="flex items-center gap-1.5">
        {presets.map(preset => (
          <Chip
            key={preset.label}
            active={preset.from === dateFrom && preset.to === dateTo}
            onClick={() => onChangeRange(preset.from, preset.to)}
          >
            {preset.label}
          </Chip>
        ))}
      </div>

      <div className="flex items-center gap-1.5">
        <input
          type="date"
          value={draftFrom}
          onChange={e => {
            setDraftFrom(e.target.value)
            if (isCompleteDate(e.target.value)) onChangeRange(e.target.value, dateTo)
            if (e.target.value === '') onChangeRange('', dateTo)
          }}
          onBlur={e => commitFrom(e.target.value)}
          className={inputCls}
          aria-label="From date"
        />
        <span className="text-xs text-muted-foreground">to</span>
        <input
          type="date"
          value={draftTo}
          onChange={e => {
            setDraftTo(e.target.value)
            if (isCompleteDate(e.target.value)) onChangeRange(dateFrom, e.target.value)
            if (e.target.value === '') onChangeRange(dateFrom, '')
          }}
          onBlur={e => commitTo(e.target.value)}
          className={inputCls}
          aria-label="To date"
        />
        {hasRange && (
          <button
            type="button"
            onClick={() => onChangeRange('', '')}
            className="flex h-8 w-8 items-center justify-center rounded-md border bg-card text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label="Clear date range"
          >
            <X className="h-3 w-3" />
          </button>
        )}
      </div>

      {(dataMin || dataMax) && (
        <span className="text-xs text-muted-foreground">Data covers {dataMin} – {dataMax}</span>
      )}
    </div>
  )
}

export default function PicksFilterBar({ rows, filtered, filter, onChange, dataMin, dataMax }: Props) {
  const names = useModelNames()
  const sports = useMemo<Option[]>(
    () => Array.from(new Set(rows.map(r => r.sport))).sort().map(s => ({ value: s, label: s })),
    [rows],
  )
  const modelIds = useMemo(() => Array.from(new Set(rows.map(r => r.model_id))), [rows])
  const models = useMemo<Option[]>(() => modelIds
    .map(id => ({ value: id, label: names.modelLabel(id).name, sub: id, paused: names.isPaused(id) === true }))
    .sort((a, b) => a.label.localeCompare(b.label) || a.value.localeCompare(b.value)),
  [modelIds, names])
  const chipLabels = useMemo(() => distinctLabels(filter.models, names, true), [filter.models, names])

  function update(partial: Partial<FilterState>) {
    onChange({ ...filter, ...partial })
  }

  const def = useMemo(() => defaultFilter(), [])

  const isDefault = useMemo(() => (
    filter.sports.length === 0 &&
    filter.models.length === 0 &&
    filter.dateFrom === def.dateFrom &&
    filter.dateTo === def.dateTo &&
    filter.clvOutcomes.length === 0 &&
    filter.results.length === 0 &&
    filter.lanes.length === def.lanes.length &&
    [...filter.lanes].sort().join(',') === [...def.lanes].sort().join(',')
  ), [filter, def])

  return (
    <div className="space-y-3 rounded-xl border bg-card p-3 shadow-retool-sm">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="flex items-center gap-2">
          <MultiSelect label="Sport" options={sports} value={filter.sports} onChange={v => update({ sports: v })} width={200} />
          <MultiSelect label="Model" options={models} value={filter.models} onChange={v => update({ models: v })} width={300} />
        </div>
        <MultiToggle options={PICK_TYPE_OPTIONS} value={filter.lanes} onChange={v => update({ lanes: v })} label="Pick type" />
        <MultiToggle options={CLV_OPTIONS} value={filter.clvOutcomes} onChange={v => update({ clvOutcomes: v })} label="CLV" />
        <MultiToggle options={RESULT_OPTIONS} value={filter.results} onChange={v => update({ results: v })} label="Result" />

        <div className="ml-auto flex items-center gap-2">
          <span className="whitespace-nowrap text-xs font-semibold text-foreground">
            {filtered.toLocaleString()} <span className="font-normal text-muted-foreground">of {rows.length.toLocaleString()} picks</span>
          </span>
          {!isDefault && (
            <Button size="sm" variant="ghost" onClick={() => onChange(defaultFilter())} className="h-8 gap-1 px-2 text-xs">
              <X className="h-3 w-3" />
              Reset
            </Button>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t pt-3">
        <DateRangeControl
          dateFrom={filter.dateFrom}
          dateTo={filter.dateTo}
          dataMin={dataMin}
          dataMax={dataMax}
          onChangeRange={(from, to) => onChange({ ...filter, dateFrom: from, dateTo: to })}
        />
        {filter.models.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs font-medium text-muted-foreground">Models</span>
            {filter.models.map(id => {
              const label = names.modelLabel(id)
              return (
                <span
                  key={id}
                  title={`${label.name}\n${id}`}
                  className="inline-flex h-7 items-center gap-1 rounded-full border border-brand bg-brand-soft pl-2.5 pr-1 text-xs font-medium text-brand"
                >
                  {chipLabels.get(id) ?? label.shortName}
                  <button
                    type="button"
                    onClick={() => update({ models: filter.models.filter(m => m !== id) })}
                    className="rounded-full p-0.5 hover:bg-background/60"
                    aria-label={`Remove ${label.name}`}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
