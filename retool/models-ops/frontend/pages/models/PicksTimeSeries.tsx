import { useState, useMemo } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  LineChart, Line,
} from 'recharts'
import { Search } from 'lucide-react'
import { Input } from '../../lib/shadcn/input'
import { PanelError, ChartSkeleton, EmptyState, Chip, Footnote } from '../../components/PanelUtils'
import {
  axisProps, gridProps, tooltipProps, legendProps, colorsByIdentity, assignStableSlots, slotColor, shortDate, PALETTE,
} from '../../components/chartTheme'
import { useModelNames, distinctLabels } from '../../components/models/modelNames'

type PickRow = {
  game_date: string
  model_id: string
  scored: string
  bets: string
}

type DayTotal = {
  game_date: string
  scored: number
  bets: number
  [key: string]: string | number
}

type Props = {
  data: unknown
  loading: boolean
  error: string | null
}

const MAX_SELECTED = PALETTE.length

// The combined view has two fixed series; colour follows their names.
const TOTALS = colorsByIdentity(['Bets', 'Scored'])

export default function PicksTimeSeries({ data, loading, error }: Props) {
  const names = useModelNames()
  const [selectedModels, setSelectedModels] = useState<string[]>([])
  const [slots, setSlots] = useState<Record<string, number>>({})
  const [search, setSearch] = useState('')

  const rows = useMemo<PickRow[]>(() => (data as PickRow[] | undefined) ?? [], [data])

  const allModels = useMemo(() => {
    const ids = Array.from(new Set(rows.map(r => r.model_id)))
    return ids.sort((a, b) => names.modelLabel(a).name.localeCompare(names.modelLabel(b).name) || a.localeCompare(b))
  }, [rows, names])

  const chipLabels = useMemo(() => distinctLabels(allModels, names, true), [allModels, names])
  const visibleChips = useMemo(
    () => allModels.filter(m => names.matchesModel(m, search)),
    [allModels, names, search],
  )

  const dailyData = useMemo<DayTotal[]>(() => {
    const map = new Map<string, DayTotal>()
    for (const row of rows) {
      const existing = map.get(row.game_date) ?? { game_date: row.game_date, scored: 0, bets: 0 }
      existing.scored += parseInt(row.scored, 10)
      existing.bets += parseInt(row.bets, 10)
      const keyScored = `${row.model_id}__scored`
      const keyBets = `${row.model_id}__bets`
      existing[keyScored] = ((existing[keyScored] as number | undefined) ?? 0) + parseInt(row.scored, 10)
      existing[keyBets] = ((existing[keyBets] as number | undefined) ?? 0) + parseInt(row.bets, 10)
      map.set(row.game_date, existing)
    }
    return Array.from(map.values()).sort((a, b) => a.game_date.localeCompare(b.game_date))
  }, [rows])

  const toggleModel = (m: string) => {
    const next = selectedModels.includes(m)
      ? selectedModels.filter(x => x !== m)
      : selectedModels.length >= MAX_SELECTED ? selectedModels : [...selectedModels, m]
    setSelectedModels(next)
    setSlots(s => assignStableSlots(s, next))
  }

  const clear = () => {
    setSelectedModels([])
    setSlots({})
  }

  if (loading) return <ChartSkeleton height={280} />
  if (error) return <PanelError message={error} />
  if (rows.length === 0) {
    return <EmptyState title="No picks in the last 14 days">Daily scored picks and bets per model will appear here.</EmptyState>
  }

  const showPerModel = selectedModels.length > 0
  const lineLabels = distinctLabels(selectedModels, names, true)
  // Legend order follows names, never selection order or volume.
  const orderedSelected = [...selectedModels].sort((a, b) => (lineLabels.get(a) ?? a).localeCompare(lineLabels.get(b) ?? b))

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative w-56">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input
              value={search}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearch(e.target.value)}
              placeholder="Find a model…"
              className="h-8 pl-8 text-xs"
              aria-label="Find a model"
            />
          </div>
          <span className="text-xs text-muted-foreground">
            {showPerModel
              ? `${selectedModels.length} of up to ${MAX_SELECTED} selected`
              : 'Pick models to compare them; otherwise all models are combined.'}
          </span>
          {showPerModel && (
            <button type="button" onClick={clear} className="text-xs font-medium text-muted-foreground underline-offset-2 hover:text-foreground hover:underline">
              Clear
            </button>
          )}
        </div>
        <div className="flex max-h-20 flex-wrap gap-1.5 overflow-y-auto">
          {visibleChips.length === 0 && <span className="text-xs text-muted-foreground">No model matches that search.</span>}
          {visibleChips.map(m => {
            const label = names.modelLabel(m)
            const paused = names.isPaused(m)
            return (
              <Chip
                key={m}
                active={selectedModels.includes(m)}
                onClick={() => toggleModel(m)}
                title={`${label.name}\n${m}${paused ? '\nPaused' : ''}`}
              >
                {chipLabels.get(m) ?? label.shortName}
              </Chip>
            )
          })}
        </div>
      </div>

      <div className="chart-fill">
        <ResponsiveContainer width="100%" height="100%">
          {showPerModel ? (
            <LineChart data={dailyData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid {...gridProps} vertical={false} />
              <XAxis dataKey="game_date" tickFormatter={shortDate} {...axisProps} />
              <YAxis {...axisProps} width={40} allowDecimals={false} />
              <Tooltip
                {...tooltipProps}
                labelFormatter={(label: unknown) => shortDate(String(label))}
                formatter={(value: unknown, name: unknown) => [`${String(value)} scored`, String(name)] as [string, string]}
              />
              {orderedSelected.length > 1 && <Legend {...legendProps} />}
              {orderedSelected.map(m => (
                <Line
                  key={m}
                  type="monotone"
                  dataKey={`${m}__scored`}
                  name={lineLabels.get(m) ?? m}
                  stroke={slotColor(slots[m])}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
              ))}
            </LineChart>
          ) : (
            <AreaChart data={dailyData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="scoredGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={TOTALS.colorOf('Scored')} stopOpacity={0.25} />
                  <stop offset="95%" stopColor={TOTALS.colorOf('Scored')} stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="betsGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={TOTALS.colorOf('Bets')} stopOpacity={0.25} />
                  <stop offset="95%" stopColor={TOTALS.colorOf('Bets')} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid {...gridProps} vertical={false} />
              <XAxis dataKey="game_date" tickFormatter={shortDate} {...axisProps} />
              <YAxis {...axisProps} width={44} allowDecimals={false} />
              <Tooltip {...tooltipProps} labelFormatter={(label: unknown) => shortDate(String(label))} />
              <Legend {...legendProps} />
              <Area type="monotone" dataKey="bets" name="Bets" stroke={TOTALS.colorOf('Bets')} fill="url(#betsGrad)" strokeWidth={2} />
              <Area type="monotone" dataKey="scored" name="Scored" stroke={TOTALS.colorOf('Scored')} fill="url(#scoredGrad)" strokeWidth={2} />
            </AreaChart>
          )}
        </ResponsiveContainer>
      </div>

      <Footnote>
        14-day window, pre-game picks only. Hover a model chip to see its full name and id.
      </Footnote>
    </div>
  )
}
