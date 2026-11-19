import { useMemo } from 'react'
import { ComposedChart, Area, Line, LineChart, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts'
import { PanelError, ChartSkeleton, EmptyState, Footnote } from '../../components/PanelUtils'
import { PALETTE, axisProps, gridProps, ChartTooltipBox, shortDate } from '../../components/chartTheme'
import { fmtRate, fmtSignedPct, rollingSeries, type BetRow, type RollingPoint } from './healthUtils'

type Props = {
  modelId: string | null
  bets: BetRow[]
  size: number
  loading: boolean
  error: string | null
}

function RollTip({ active, payload, size }: { active?: boolean; payload?: Array<{ payload: RollingPoint }>; size: number }) {
  if (!active || !payload?.length) return null
  const p = payload[0]!.payload
  return (
    <ChartTooltipBox title={`Bet ${p.x} · ${shortDate(p.date)}`}>
      <div>Avg CLV, last {size} bets: {fmtSignedPct(p.avg)}</div>
      {p.band && <div>95% range {fmtSignedPct(p.band[0])} to {fmtSignedPct(p.band[1])}</div>}
      <div>{p.measured} of {size} with a closing price</div>
      <div>Beat rate with line moves: {fmtRate(p.beatRate)} of {p.judged}</div>
    </ChartTooltipBox>
  )
}

export default function HealthRolling({ modelId, bets, size, loading, error }: Props) {
  const series = useMemo(() => rollingSeries(bets, size), [bets, size])

  if (loading) return <ChartSkeleton height={260} />
  if (error) return <PanelError message={error} />
  if (!modelId) return <EmptyState title="Pick a model">Click a model in the table above.</EmptyState>
  if (bets.length < size) {
    return (
      <EmptyState title={`Needs ${size} bets`}>
        This model has {bets.length} graded, published bet{bets.length !== 1 ? 's' : ''}. Pick a smaller window or another model.
      </EmptyState>
    )
  }
  if (series.every(p => p.avg == null)) {
    return (
      <EmptyState title="No closing prices">
        None of this model’s bets has a closing price on our number (in-play bets have no pre-game close).
      </EmptyState>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="h-[220px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={series} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid {...gridProps} vertical={false} />
            <XAxis dataKey="x" {...axisProps} type="number" domain={['dataMin', 'dataMax']} allowDecimals={false} />
            <YAxis {...axisProps} width={48} tickFormatter={v => `${v}%`} />
            <ReferenceLine y={0} stroke="var(--chart-axis)" />
            <Tooltip content={<RollTip size={size} />} />
            <Area dataKey="band" stroke="none" fill={PALETTE[0]} fillOpacity={0.15} isAnimationActive={false} connectNulls={false} />
            <Line dataKey="avg" stroke={PALETTE[0]} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="h-[120px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={series} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid {...gridProps} vertical={false} />
            <XAxis dataKey="x" {...axisProps} type="number" domain={['dataMin', 'dataMax']} allowDecimals={false} />
            <YAxis {...axisProps} width={48} domain={[0, 1]} tickFormatter={v => `${Math.round(v * 100)}%`} />
            <ReferenceLine y={0.5} stroke="var(--chart-axis)" strokeDasharray="3 3" />
            <Tooltip content={<RollTip size={size} />} />
            <Line dataKey="beatRate" stroke={PALETTE[1]} strokeWidth={1.5} dot={false} isAnimationActive={false} connectNulls={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <Footnote>
        Top: the average CLV of the bets in each rolling window of {size} bets that have a closing price on our number, with its 95% range shaded. Bottom: the beat rate over the same window, counting line moves (our way is a beat, against is a miss). Bet 1 is the oldest of the model’s newest 500 bets; a point appears once {size} bets exist.
      </Footnote>
    </div>
  )
}
