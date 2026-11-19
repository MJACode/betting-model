import { useMemo } from 'react'
import { ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ReferenceDot, ResponsiveContainer } from 'recharts'
import { PALETTE, AXIS_COLOR, TEXT_COLOR, axisProps, gridProps, ChartTooltipBox } from '../../components/chartTheme'
import { pct, type Fmt, type SweepPoint } from './simMath'
import { logAxis, logSafe, scaledAxis } from './simAxis'

type SweepRow = { x: number; med: number; draw: number; below: number }

const X_TICKS = [48, 50, 52, 54, 56, 58, 60]

function SweepTip({ active, payload, fmt }: { active?: boolean; payload?: ReadonlyArray<{ payload?: SweepRow }>; fmt: Fmt }) {
  const row = active ? payload?.[0]?.payload : undefined
  if (!row) return null
  return (
    <ChartTooltipBox title={`Win rate ${row.x.toFixed(2)}%`}>
      <div className="flex justify-between gap-4 tabular-nums">
        <span className="text-muted-foreground">Median ending</span>
        <span className="font-semibold">{fmt(row.med)}</span>
      </div>
      <div className="flex justify-between gap-4 tabular-nums">
        <span className="text-muted-foreground">Chance below start</span>
        <span>{pct(row.below)}</span>
      </div>
    </ChartTooltipBox>
  )
}

export default function SweepChart({
  sweep,
  p,
  selectedMed,
  B0,
  breakEven,
  fmt,
  k,
}: {
  sweep: SweepPoint[]
  p: number
  selectedMed: number
  B0: number
  /** Simple break-even win rate, 0..1. */
  breakEven: number
  fmt: Fmt
  /** Display amount per unit (1 in Units): the axis ticks are chosen in display amounts. */
  k: number
}) {
  const { rows, axis } = useMemo(() => {
    let lo = B0, hi = B0
    const out: SweepRow[] = sweep.map(pt => {
      if (pt.med < lo) lo = pt.med
      if (pt.med > hi) hi = pt.med
      return { x: pt.p * 100, med: pt.med, draw: logSafe(pt.med), below: pt.below }
    })
    if (selectedMed < lo) lo = selectedMed
    if (selectedMed > hi) hi = selectedMed
    return { rows: out, axis: scaledAxis(logAxis, lo, hi, k) }
  }, [sweep, B0, selectedMed, k])

  const beX = breakEven * 100

  return (
    <div className="min-h-[220px] w-full flex-1">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 22, right: 24, bottom: 4, left: 0 }} accessibilityLayer>
          <CartesianGrid {...gridProps} vertical={false} />
          <XAxis
            dataKey="x"
            type="number"
            domain={[48, 60]}
            ticks={X_TICKS}
            {...axisProps}
            tickFormatter={(v: number) => `${v}%`}
            label={{ value: 'True win rate', position: 'insideBottom', offset: -2, fontSize: 11, fill: AXIS_COLOR }}
            height={36}
          />
          <YAxis
            type="number"
            scale="log"
            domain={axis.domain}
            ticks={axis.ticks}
            allowDataOverflow
            {...axisProps}
            width={64}
            tickFormatter={(v: number) => fmt(v, { axis: true })}
          />
          <Tooltip content={<SweepTip fmt={fmt} />} cursor={{ stroke: AXIS_COLOR, strokeWidth: 1, strokeDasharray: '3 3' }} isAnimationActive={false} />
          <ReferenceLine
            y={logSafe(B0)}
            stroke={AXIS_COLOR}
            strokeDasharray="4 4"
            label={{ value: `Start ${fmt(B0, { axis: true })}`, position: 'insideBottomLeft', fontSize: 11, fill: AXIS_COLOR }}
          />
          {beX >= 48 && beX <= 60 && (
            <ReferenceLine
              x={beX}
              stroke={AXIS_COLOR}
              strokeDasharray="4 4"
              label={{ value: `Break-even ${beX.toFixed(2)}%`, position: 'top', fontSize: 11, fill: AXIS_COLOR }}
            />
          )}
          <Line dataKey="draw" stroke={PALETTE[0]} strokeWidth={2} dot={false} activeDot={{ r: 3 }} isAnimationActive={false} />
          <ReferenceDot
            x={p * 100}
            y={logSafe(selectedMed)}
            r={5}
            fill={PALETTE[0]}
            stroke="hsl(var(--card))"
            strokeWidth={1.5}
            label={{ value: `${(p * 100).toFixed(1)}%: ${fmt(selectedMed)}`, position: 'left', fontSize: 11, fontWeight: 600, fill: TEXT_COLOR }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
