import { useMemo } from 'react'
import { ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ReferenceDot, ResponsiveContainer } from 'recharts'
import { PALETTE, AXIS_COLOR, TEXT_COLOR, axisProps, gridProps, ChartTooltipBox, Swatch } from '../../components/chartTheme'
import { fmtU, type SimResult } from './simMath'
import { linearAxis, logAxis, logSafe } from './simAxis'

export type Scale = 'log' | 'linear'

type FanRow = {
  t: number
  /** 5th..95th and 25th..75th as [low, high]; median; sample paths (drawing values). */
  outer: [number, number]
  inner: [number, number]
  med: number
  paths: number[]
  /** Exact percentiles [5th, 25th, median, 75th, 95th] for the tooltip. */
  q: number[]
}

const SAMPLE_COLOR = 'var(--series-other)'

function FanTip({ active, payload }: { active?: boolean; payload?: ReadonlyArray<{ payload?: FanRow }> }) {
  const row = active ? payload?.[0]?.payload : undefined
  if (!row) return null
  const [p5, p25, p50, p75, p95] = row.q
  const line = (label: string, v: number | undefined, strong = false) => (
    <div className="flex justify-between gap-4 tabular-nums">
      <span className={strong ? 'font-medium' : 'text-muted-foreground'}>{label}</span>
      <span className={strong ? 'font-semibold' : ''}>{v == null ? '—' : fmtU(v)}</span>
    </div>
  )
  return (
    <ChartTooltipBox title={`After ${row.t.toLocaleString('en-US')} bets`}>
      {line('95th', p95)}
      {line('75th', p75)}
      {line('Median', p50, true)}
      {line('25th', p25)}
      {line('5th', p5)}
    </ChartTooltipBox>
  )
}

export default function FanChart({ result, B0, N, scale }: { result: SimResult; B0: number; N: number; scale: Scale }) {
  const isLog = scale === 'log'

  const { rows, axis } = useMemo(() => {
    const draw = isLog ? logSafe : (v: number) => v
    let lo = B0, hi = B0
    const out: FanRow[] = result.times.map((t, i) => {
      const q = result.band.map(b => b[i]!)
      const paths = result.sp.map(s => B0 * Math.exp(s[i]!))
      for (const v of [q[0]!, q[4]!, ...paths]) {
        if (v < lo) lo = v
        if (v > hi) hi = v
      }
      return {
        t,
        outer: [draw(q[0]!), draw(q[4]!)],
        inner: [draw(q[1]!), draw(q[3]!)],
        med: draw(q[2]!),
        paths: paths.map(draw),
        q,
      }
    })
    return { rows: out, axis: isLog ? logAxis(lo, hi) : linearAxis(hi) }
  }, [result, B0, isLog])

  const finalMed = result.final[2]!

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="min-h-[240px] w-full flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 8, right: 72, bottom: 4, left: 0 }} accessibilityLayer>
            <CartesianGrid {...gridProps} vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              domain={[0, N]}
              {...axisProps}
              allowDecimals={false}
              tickFormatter={(v: number) => v.toLocaleString('en-US')}
              label={{ value: 'Bets placed', position: 'insideBottom', offset: -2, fontSize: 11, fill: AXIS_COLOR }}
              height={36}
            />
            <YAxis
              type="number"
              scale={isLog ? 'log' : 'linear'}
              domain={axis.domain}
              ticks={axis.ticks}
              allowDataOverflow
              {...axisProps}
              width={64}
              tickFormatter={(v: number) => fmtU(v, { axis: true })}
            />
            <Tooltip content={<FanTip />} cursor={{ stroke: AXIS_COLOR, strokeWidth: 1, strokeDasharray: '3 3' }} isAnimationActive={false} />
            <Area dataKey="outer" stroke="none" fill={PALETTE[0]} fillOpacity={0.12} isAnimationActive={false} activeDot={false} />
            <Area dataKey="inner" stroke="none" fill={PALETTE[0]} fillOpacity={0.24} isAnimationActive={false} activeDot={false} />
            {result.sp.map((_, j) => (
              <Line
                key={j}
                dataKey={(r: FanRow) => r.paths[j]}
                stroke={SAMPLE_COLOR}
                strokeOpacity={0.85}
                strokeWidth={1}
                dot={false}
                activeDot={false}
                isAnimationActive={false}
              />
            ))}
            <ReferenceLine
              y={isLog ? logSafe(B0) : B0}
              stroke={AXIS_COLOR}
              strokeDasharray="4 4"
              label={{ value: `Start ${fmtU(B0, { axis: true })}`, position: 'insideBottomLeft', fontSize: 11, fill: AXIS_COLOR }}
            />
            <Line dataKey="med" stroke={PALETTE[0]} strokeWidth={2} dot={false} activeDot={{ r: 3 }} isAnimationActive={false} />
            <ReferenceDot
              x={N}
              y={isLog ? logSafe(finalMed) : finalMed}
              r={4}
              fill={PALETTE[0]}
              stroke="hsl(var(--card))"
              strokeWidth={1.5}
              label={{ value: fmtU(finalMed), position: 'right', fontSize: 11, fontWeight: 600, fill: TEXT_COLOR }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span><span className="mr-1.5 inline-block h-2.5 w-4 rounded-sm align-middle" style={{ background: PALETTE[0], opacity: 0.18 }} />5th–95th</span>
        <span><span className="mr-1.5 inline-block h-2.5 w-4 rounded-sm align-middle" style={{ background: PALETTE[0], opacity: 0.4 }} />25th–75th</span>
        <span><Swatch color={PALETTE[0]} />Median</span>
        <span><Swatch color={SAMPLE_COLOR} />8 sample paths</span>
        <span className="ml-auto">Hover or focus the chart and use the arrow keys to step through it</span>
      </div>
    </div>
  )
}
