import { useState, useMemo } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { PanelError, ChartSkeleton, EmptyState, Chip, Footnote } from '../../components/PanelUtils'
import {
  axisProps, gridProps, tooltipProps, legendProps, colorsByIdentity, shortDate,
  OTHER_KEY, OTHER_SERIES_COLOR,
} from '../../components/chartTheme'

type ApiCallRow = {
  day: string
  api: string
  source: string
  calls: number
  errors: number
  credits: number
}

type WindowRow = {
  first_day: string | null
  last_day: string | null
  days: number
}

type ApiCallTrendData = {
  rows: ApiCallRow[]
  window: WindowRow
}

type Props = {
  data: unknown
  loading: boolean
  error: string | null
}

type Metric = 'calls' | 'credits' | 'errors'

const MAX_SERIES = 7

export default function ApiCallTrend({ data, loading, error }: Props) {
  const [metric, setMetric] = useState<Metric>('calls')

  const { rows, window: win } = useMemo<ApiCallTrendData>(() => {
    const d = data as ApiCallTrendData | undefined
    return d ?? { rows: [], window: { first_day: null, last_day: null, days: 0 } }
  }, [data])

  // Coerce bigint-serialised strings to numbers
  const normRows = useMemo<ApiCallRow[]>(() => rows.map(r => ({
    ...r,
    calls: Number(r.calls),
    errors: Number(r.errors),
    credits: Number(r.credits),
  })), [rows])

  // Every source in the data, sorted by name. Colours come from this list, so
  // switching the metric never repaints a source. Sources past the eighth
  // palette slot fall back to the neutral, so an outgrown palette looks
  // wrong rather than looking like a real series.
  const allApis = useMemo(() => Array.from(new Set(normRows.map(r => r.api))).sort(), [normRows])
  const colorOf = useMemo(() => colorsByIdentity(allApis).colorOf, [allApis])

  // Which sources get their own series: the top 7 by the selected metric,
  // the rest in Other (ties keep name order, as before).
  const named = useMemo(() => {
    const totals = new Map<string, number>()
    for (const r of normRows) totals.set(r.api, (totals.get(r.api) ?? 0) + r[metric])
    const sorted = [...allApis].sort((a, b) => (totals.get(b) ?? 0) - (totals.get(a) ?? 0))
    return new Set(sorted.slice(0, MAX_SERIES))
  }, [allApis, normRows, metric])

  const hasOther = allApis.length > MAX_SERIES

  // Pivot to chart data: one row per day
  const chartData = useMemo(() => {
    const dayMap = new Map<string, Record<string, number>>()
    for (const r of normRows) {
      const seriesKey = named.has(r.api) ? r.api : OTHER_KEY
      const row = dayMap.get(r.day) ?? {}
      row[seriesKey] = (row[seriesKey] ?? 0) + r[metric]
      dayMap.set(r.day, row)
    }
    return Array.from(dayMap.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([day, vals]) => ({ day, ...vals }))
  }, [normRows, named, metric])

  const totals = useMemo(() => {
    let calls = 0, credits = 0, errors = 0
    for (const r of normRows) { calls += r.calls; credits += r.credits; errors += r.errors }
    return { calls, credits, errors }
  }, [normRows])

  // Series in name order; Other last.
  const seriesKeys = useMemo(
    () => [...Array.from(named).sort((a, b) => a.localeCompare(b)), ...(hasOther ? [OTHER_KEY] : [])],
    [named, hasOther],
  )

  if (loading) return <ChartSkeleton height={280} />
  if (error) return <PanelError message={error} />

  const isEmpty = normRows.length === 0

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="mr-1 text-xs font-medium text-muted-foreground">Metric</span>
        {(['calls', 'credits', 'errors'] as const).map(m => (
          <Chip key={m} active={metric === m} onClick={() => setMetric(m)}>
            {m.charAt(0).toUpperCase() + m.slice(1)}
          </Chip>
        ))}
        {!isEmpty && (
          <span className="ml-auto text-xs text-muted-foreground">
            {totals.calls.toLocaleString()} calls · {totals.credits.toLocaleString()} credits · {totals.errors.toLocaleString()} errors across {win.days} day{win.days !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {isEmpty ? (
        <EmptyState title="No daily totals yet">
          Daily calls by source appear here once the daily rollup has run.
        </EmptyState>
      ) : (
        <div className="chart-fill">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid {...gridProps} vertical={false} />
              <XAxis dataKey="day" tickFormatter={shortDate} {...axisProps} />
              <YAxis
                {...axisProps}
                width={50}
                tickFormatter={(v: number) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v))}
              />
              <Tooltip
                {...tooltipProps}
                labelFormatter={(label: unknown) => shortDate(String(label))}
                formatter={(value: unknown, name: unknown) => [Number(value).toLocaleString(), String(name)] as [string, string]}
              />
              {seriesKeys.length > 1 && <Legend {...legendProps} />}
              {seriesKeys.map(api => {
                const color = api === OTHER_KEY ? OTHER_SERIES_COLOR : colorOf(api)
                return (
                  <Area
                    key={api}
                    type="monotone"
                    dataKey={api}
                    stackId="1"
                    stroke={color}
                    fill={color}
                    fillOpacity={0.55}
                    strokeWidth={2}
                  />
                )
              })}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      <Footnote>
        The raw call log is pruned after 7 days, so this chart reads a per-day summary that is folded in before each prune. Anything before that summary started does not exist and never will;
        {win.first_day && win.last_day
          ? ` the window covers ${shortDate(win.first_day)} – ${shortDate(win.last_day)} (${win.days} day${win.days !== 1 ? 's' : ''}).`
          : ' the window above says what is actually covered.'}
        {' '}Credits are reported only by The Odds API; the other feeds are free and show zero, which is not the same as untracked.
      </Footnote>
    </div>
  )
}
