import { useMemo, useState } from 'react'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine, Cell, LabelList,
} from 'recharts'
import { type PickRow } from './picksUtils'
import { EmptyState, Chip } from '../../components/PanelUtils'
import {
  axisProps, gridProps, legendProps, colorsByIdentity, ChartTooltipBox, Swatch, AXIS_COLOR,
} from '../../components/chartTheme'
import { useModelNames, distinctLabels } from '../../components/models/modelNames'

// CLV outcome colours (palette slots 1 and 8 plus a neutral), defined per theme in appTheme.css.
const BEAT = 'var(--clv-beat)'
const WORSE = 'var(--clv-worse)'
const FLAT = 'var(--clv-flat)'
const ZERO_LINE = 'var(--clv-muted)'

function signedU(n: number): string {
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}u`
}

function NoData({ children }: { children: string }) {
  return <EmptyState title="Nothing to chart">{children}</EmptyState>
}

/** Settled (WIN/LOSS/PUSH) with units — the same universe as units and ROI. */
function pricedRows(rows: PickRow[]): PickRow[] {
  return rows.filter(r => {
    const res = r.result?.toUpperCase()
    return (res === 'WIN' || res === 'LOSS' || res === 'PUSH') && r.profit_units != null
  })
}

// Recharts passes these as render props; typed loosely to avoid version skew
type TooltipRenderProps = {
  active?: boolean
  payload?: ReadonlyArray<{ name?: unknown; value?: unknown; color?: unknown; payload?: unknown }>
  label?: unknown
}

// ---- 1. Equity curve ----
type CombinedDay = { date: string; dayUnits: number; cumulative: number }
type SportDay = { date: string } & Record<string, number>

export function EquityCurve({ rows, sportUniverse }: { rows: PickRow[]; sportUniverse: string[] }) {
  const [splitBySport, setSplitBySport] = useState(false)
  const priced = useMemo(() => pricedRows(rows), [rows])
  // Sports are coloured from the unfiltered set so a filter never repaints them.
  const sportColors = useMemo(() => colorsByIdentity(sportUniverse), [sportUniverse])

  const { combined, bySport, sports } = useMemo(() => {
    const sorted = [...priced].sort((a, b) => (a.game_date < b.game_date ? -1 : a.game_date > b.game_date ? 1 : 0))

    const dateMap = new Map<string, number>()
    for (const r of sorted) {
      const u = r.profit_units != null ? parseFloat(r.profit_units) : 0
      dateMap.set(r.game_date, (dateMap.get(r.game_date) ?? 0) + u)
    }
    let running = 0
    const combined: CombinedDay[] = Array.from(dateMap.entries())
      .sort(([a], [b]) => (a < b ? -1 : 1))
      .map(([date, dayUnits]) => {
        running += dayUnits
        return { date, dayUnits: parseFloat(dayUnits.toFixed(3)), cumulative: parseFloat(running.toFixed(3)) }
      })

    const sportSet = Array.from(new Set(sorted.map(r => r.sport))).sort()
    const sportDateMap = new Map<string, Record<string, number>>()
    for (const r of sorted) {
      const u = r.profit_units != null ? parseFloat(r.profit_units) : 0
      if (!sportDateMap.has(r.game_date)) sportDateMap.set(r.game_date, {})
      const bucket = sportDateMap.get(r.game_date)!
      bucket[r.sport] = (bucket[r.sport] ?? 0) + u
    }
    const sportCumMap = new Map<string, number>(sportSet.map(s => [s, 0]))
    const bySport: SportDay[] = Array.from(sportDateMap.entries())
      .sort(([a], [b]) => (a < b ? -1 : 1))
      .map(([date, bucket]) => {
        const entry: Record<string, unknown> = { date }
        for (const s of sportSet) {
          sportCumMap.set(s, (sportCumMap.get(s) ?? 0) + (bucket[s] ?? 0))
          entry[s] = parseFloat((sportCumMap.get(s) ?? 0).toFixed(3))
        }
        return entry as SportDay
      })

    return { combined, bySport, sports: sportSet }
  }, [priced])

  if (combined.length === 0) return <NoData>The running units total appears here once the filter includes settled, priced picks.</NoData>

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Chip active={!splitBySport} onClick={() => setSplitBySport(false)}>Combined</Chip>
        <Chip active={splitBySport} onClick={() => setSplitBySport(true)}>By sport</Chip>
        <span className="ml-auto text-xs text-muted-foreground">{priced.length.toLocaleString()} settled, priced picks</span>
      </div>
      <div className="chart-fill">
        <ResponsiveContainer width="100%" height="100%">
          {splitBySport ? (
            <LineChart data={bySport} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid {...gridProps} vertical={false} />
              <XAxis dataKey="date" {...axisProps} minTickGap={24} />
              <YAxis {...axisProps} width={56} tickFormatter={(v: number) => `${v > 0 ? '+' : ''}${v}u`} />
              <ReferenceLine y={0} stroke={ZERO_LINE} strokeWidth={1} />
              <Tooltip
                content={({ active, payload, label }: TooltipRenderProps) => {
                  if (!active || !payload?.length) return null
                  return (
                    <ChartTooltipBox title={String(label ?? '')}>
                      {payload.map(p => (
                        <div key={String(p.name)}>
                          <Swatch color={String(p.color ?? '')} />
                          {String(p.name)}: <span className="tabular-nums">{signedU(Number(p.value))}</span>
                        </div>
                      ))}
                    </ChartTooltipBox>
                  )
                }}
              />
              {sports.length > 1 && <Legend {...legendProps} />}
              {sports.map(s => (
                <Line key={s} type="monotone" dataKey={s} name={s} stroke={sportColors.colorOf(s)} strokeWidth={2} dot={false} />
              ))}
            </LineChart>
          ) : (
            <LineChart data={combined} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid {...gridProps} vertical={false} />
              <XAxis dataKey="date" {...axisProps} minTickGap={24} />
              <YAxis {...axisProps} width={56} tickFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v}u`} />
              <ReferenceLine y={0} stroke={ZERO_LINE} strokeWidth={1} />
              <Tooltip
                content={({ active, payload, label }: TooltipRenderProps) => {
                  if (!active || !payload?.length) return null
                  const d = payload[0]?.payload as CombinedDay | undefined
                  if (!d) return null
                  return (
                    <ChartTooltipBox title={String(label ?? '')}>
                      <div>Day: <span className="tabular-nums">{signedU(d.dayUnits)}</span></div>
                      <div>Running: <span className="tabular-nums">{signedU(d.cumulative)}</span></div>
                    </ChartTooltipBox>
                  )
                }}
              />
              <Line type="monotone" dataKey="cumulative" name="Running units" stroke="var(--series-1)" strokeWidth={2} dot={false} />
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  )
}

/** Vertical list chart that grows with the number of models and scrolls inside its tile. */
function ScrollingChart({ count, perRow, children }: { count: number; perRow: number; children: React.ReactElement }) {
  return (
    <div className="chart-fill overflow-y-auto">
      <div style={{ height: count * perRow + 48, minHeight: '100%' }}>
        <ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer>
      </div>
    </div>
  )
}

// ---- 2. Units by model ----
type ModelUnit = { model_id: string; units: number }

export function UnitsByModel({ rows }: { rows: PickRow[] }) {
  const names = useModelNames()
  const priced = useMemo(() => pricedRows(rows), [rows])

  const data = useMemo<ModelUnit[]>(() => {
    const map = new Map<string, number>()
    for (const r of priced) {
      const u = r.profit_units != null ? parseFloat(r.profit_units) : 0
      map.set(r.model_id, (map.get(r.model_id) ?? 0) + u)
    }
    return Array.from(map.entries())
      .map(([model_id, units]) => ({ model_id, units: parseFloat(units.toFixed(2)) }))
      .sort((a, b) => a.units - b.units)
  }, [priced])

  const axisLabels = useMemo(() => distinctLabels(data.map(d => d.model_id), names, true), [data, names])

  if (data.length === 0) return <NoData>Units per model appear here once the filter includes settled, priced picks.</NoData>

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <span className="inline-flex items-center"><Swatch color={BEAT} />Up</span>
        <span className="inline-flex items-center"><Swatch color={WORSE} />Down</span>
        <span className="ml-auto">Sorted by units · hover a bar for the model id</span>
      </div>
      <ScrollingChart count={data.length} perRow={28}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 64, left: 4, bottom: 4 }}>
          <CartesianGrid {...gridProps} horizontal={false} />
          <XAxis type="number" {...axisProps} tickFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v}u`} />
          <YAxis
            type="category"
            dataKey="model_id"
            width={150}
            {...axisProps}
            tickFormatter={(id: string) => {
              const l = axisLabels.get(id) ?? id
              return l.length > 22 ? `${l.slice(0, 21)}…` : l
            }}
          />
          <ReferenceLine x={0} stroke={ZERO_LINE} strokeWidth={1} />
          <Tooltip
            cursor={{ fill: 'hsl(var(--muted) / 0.6)' }}
            content={({ active, payload }: TooltipRenderProps) => {
              if (!active || !payload?.length) return null
              const d = payload[0]?.payload as ModelUnit | undefined
              if (!d) return null
              return (
                <ChartTooltipBox title={names.modelLabel(d.model_id).name}>
                  <div className="font-mono text-[11px] text-muted-foreground">{d.model_id}</div>
                  <div className="mt-1">Units: <span className="tabular-nums">{signedU(d.units)}</span></div>
                </ChartTooltipBox>
              )
            }}
          />
          <Bar dataKey="units" name="Units" maxBarSize={20} radius={4}>
            {data.map(entry => (
              <Cell key={entry.model_id} fill={entry.units >= 0 ? BEAT : WORSE} />
            ))}
            <LabelList
              dataKey="units"
              position="right"
              style={{ fontSize: 11, fill: AXIS_COLOR }}
              formatter={(v: unknown) => signedU(Number(v))}
            />
          </Bar>
        </BarChart>
      </ScrollingChart>
    </div>
  )
}

// ---- 3. CLV outcome by model ----
type ModelClv = {
  model_id: string
  beat: number; flat: number; worse: number; total: number
  beatPct: number; flatPct: number; worsePct: number
}

export function ClvByModel({ rows }: { rows: PickRow[] }) {
  const names = useModelNames()

  const { data, excluded } = useMemo(() => {
    const map = new Map<string, ModelClv>()
    for (const r of rows) {
      if (r.clv_outcome === 'NOT_MEASURED' || r.clv_outcome === 'UNRESOLVED') continue
      if (!map.has(r.model_id)) {
        map.set(r.model_id, { model_id: r.model_id, beat: 0, flat: 0, worse: 0, total: 0, beatPct: 0, flatPct: 0, worsePct: 0 })
      }
      const m = map.get(r.model_id)!
      m.total++
      if (r.clv_outcome === 'BEAT') m.beat++
      else if (r.clv_outcome === 'FLAT') m.flat++
      else if (r.clv_outcome === 'WORSE') m.worse++
    }

    const allModels = Array.from(new Set(rows.map(r => r.model_id))).sort()
    const excluded = allModels.filter(m => !map.has(m))

    const data = Array.from(map.values())
      .sort((a, b) => b.beat / (b.total || 1) - a.beat / (a.total || 1))
      .map(m => ({
        ...m,
        beatPct: m.total > 0 ? parseFloat(((m.beat / m.total) * 100).toFixed(2)) : 0,
        flatPct: m.total > 0 ? parseFloat(((m.flat / m.total) * 100).toFixed(2)) : 0,
        worsePct: m.total > 0 ? parseFloat(((m.worse / m.total) * 100).toFixed(2)) : 0,
      }))

    return { data, excluded }
  }, [rows])

  const axisLabels = useMemo(() => distinctLabels(data.map(d => d.model_id), names, true), [data, names])

  if (data.length === 0) return <NoData>Beat, flat and worse shares per model appear here once the filter includes picks with a measured close.</NoData>

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <ScrollingChart count={data.length} perRow={30}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 56, left: 4, bottom: 4 }}>
          <CartesianGrid {...gridProps} horizontal={false} />
          <XAxis type="number" domain={[0, 100]} {...axisProps} tickFormatter={(v: number) => `${v}%`} />
          <YAxis
            type="category"
            dataKey="model_id"
            width={150}
            {...axisProps}
            tickFormatter={(id: string) => {
              const l = axisLabels.get(id) ?? id
              return l.length > 22 ? `${l.slice(0, 21)}…` : l
            }}
          />
          <Tooltip
            cursor={{ fill: 'hsl(var(--muted) / 0.6)' }}
            content={({ active, payload }: TooltipRenderProps) => {
              if (!active || !payload?.length) return null
              const d = payload[0]?.payload as ModelClv | undefined
              if (!d) return null
              return (
                <ChartTooltipBox title={names.modelLabel(d.model_id).name}>
                  <div className="mb-1 font-mono text-[11px] text-muted-foreground">{d.model_id}</div>
                  <div><Swatch color={BEAT} />Beat: <span className="tabular-nums">{d.beatPct.toFixed(1)}%</span> ({d.beat})</div>
                  <div><Swatch color={FLAT} />Flat: <span className="tabular-nums">{d.flatPct.toFixed(1)}%</span> ({d.flat})</div>
                  <div><Swatch color={WORSE} />Worse: <span className="tabular-nums">{d.worsePct.toFixed(1)}%</span> ({d.worse})</div>
                  <div className="mt-1 text-muted-foreground">{d.total} measured</div>
                </ChartTooltipBox>
              )
            }}
          />
          <Legend {...legendProps} verticalAlign="top" align="left" wrapperStyle={{ fontSize: 12, paddingBottom: 8 }} />
          <Bar dataKey="beatPct" name="Beat" stackId="a" fill={BEAT} maxBarSize={20} radius={[4, 0, 0, 4]} />
          <Bar dataKey="flatPct" name="Flat" stackId="a" fill={FLAT} maxBarSize={20} />
          <Bar dataKey="worsePct" name="Worse" stackId="a" fill={WORSE} maxBarSize={20} radius={[0, 4, 4, 0]}>
            <LabelList
              content={(props) => {
                const { x, y, width, height, index } = props as {
                  x?: number; y?: number; width?: number; height?: number; index?: number
                }
                if (index == null || !data[index]) return null
                const row = data[index]!
                return (
                  <text
                    x={(x ?? 0) + (width ?? 0) + 6}
                    y={(y ?? 0) + (height ?? 0) / 2}
                    dy="0.35em"
                    fontSize={11}
                    fill={AXIS_COLOR}
                  >
                    n={row.total}
                  </text>
                )
              }}
            />
          </Bar>
        </BarChart>
      </ScrollingChart>
      {excluded.length > 0 && (
        <p className="text-xs text-muted-foreground">
          No close measured (in-play only or never captured): {excluded.map(id => names.modelLabel(id).name).join(', ')}
        </p>
      )}
      <p className="text-xs text-muted-foreground">In-play picks and any pick without a captured close are left out of CLV, not counted as losses.</p>
    </div>
  )
}

// ---- 4. CLV distribution histogram ----
type HistBucket = { label: string; count: number; sign: 'pos' | 'neg' | 'zero' }

export function ClvDistribution({ rows }: { rows: PickRow[] }) {
  const BUCKET_SIZE = 0.5

  const { buckets, n } = useMemo(() => {
    const sameLine = rows.filter(r => r.clv_pct != null)
    const n = sameLine.length
    if (n === 0) return { buckets: [] as HistBucket[], n: 0 }

    const values = sameLine.map(r => parseFloat(r.clv_pct!))
    const minVal = Math.min(...values)
    const maxVal = Math.max(...values)

    const bucketMin = Math.floor(minVal / BUCKET_SIZE) * BUCKET_SIZE
    const bucketMax = Math.ceil(maxVal / BUCKET_SIZE) * BUCKET_SIZE

    const map = new Map<number, number>()
    for (const v of values) {
      const key = Math.round(Math.floor(v / BUCKET_SIZE) * BUCKET_SIZE * 10) / 10
      map.set(key, (map.get(key) ?? 0) + 1)
    }

    const buckets: HistBucket[] = []
    let cur = bucketMin
    while (cur <= bucketMax + 1e-9) {
      const key = Math.round(cur * 10) / 10
      const count = map.get(key) ?? 0
      const sign: HistBucket['sign'] = key === 0 ? 'zero' : key > 0 ? 'pos' : 'neg'
      buckets.push({
        label: key === 0 ? '0' : `${key >= 0 ? '+' : ''}${key.toFixed(1)}`,
        count,
        sign,
      })
      cur = Math.round((cur + BUCKET_SIZE) * 10) / 10
    }

    return { buckets, n }
  }, [rows])

  if (n === 0) return <NoData>The spread of price CLV appears here once the filter includes same-line picks with a measured close.</NoData>

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <span className="inline-flex items-center"><Swatch color={BEAT} />Beat the close</span>
        <span className="inline-flex items-center"><Swatch color={FLAT} />No change</span>
        <span className="inline-flex items-center"><Swatch color={WORSE} />Worse than close</span>
        <span className="ml-auto">{n.toLocaleString()} same-line picks · 0.5pp buckets</span>
      </div>
      <div className="chart-fill">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={buckets} margin={{ top: 16, right: 16, left: 0, bottom: 20 }}>
            <CartesianGrid {...gridProps} vertical={false} />
            <XAxis
              dataKey="label"
              {...axisProps}
              tick={{ fontSize: 10, fill: AXIS_COLOR }}
              label={{ value: 'CLV (pp)', position: 'insideBottom', offset: -12, fontSize: 11, fill: AXIS_COLOR }}
            />
            <YAxis {...axisProps} width={44} allowDecimals={false} />
            <Tooltip
              cursor={{ fill: 'hsl(var(--muted) / 0.6)' }}
              content={({ active, payload, label }: TooltipRenderProps) => {
                if (!active || !payload?.length) return null
                return (
                  <ChartTooltipBox title={`CLV bucket: ${String(label ?? '')}pp`}>
                    Picks: <span className="tabular-nums">{Number(payload[0]?.value).toLocaleString()}</span>
                  </ChartTooltipBox>
                )
              }}
            />
            <Bar dataKey="count" name="Picks" maxBarSize={28} radius={[3, 3, 0, 0]}>
              {buckets.map(b => (
                <Cell key={b.label} fill={b.sign === 'pos' ? BEAT : b.sign === 'neg' ? WORSE : FLAT} />
              ))}
              <LabelList
                content={(props) => {
                  const { x, y, width, index } = props as { x?: number; y?: number; width?: number; index?: number }
                  if (index == null || !buckets[index]) return null
                  const b = buckets[index]!
                  if (b.sign !== 'zero') return null
                  return (
                    <text x={(x ?? 0) + (width ?? 0) / 2} y={(y ?? 0) - 5} textAnchor="middle" fontSize={11} fill={AXIS_COLOR} fontWeight={600}>
                      {b.count.toLocaleString()}
                    </text>
                  )
                }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs text-muted-foreground">Picks whose line moved carry no price CLV by construction, so only same-line picks are counted.</p>
    </div>
  )
}
