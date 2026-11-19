import { useMemo } from 'react'
import { BarChart, Bar, Cell, ErrorBar, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../lib/shadcn/table'
import { PanelError, TableSkeleton, EmptyState, Footnote, signedClass, fmtDate } from '../../components/PanelUtils'
import { ModelName } from '../../components/models/ModelName'
import { PALETTE, axisProps, gridProps, ChartTooltipBox, shortDate } from '../../components/chartTheme'
import { cn } from '../../lib/shadcn/utils'
import { Z95, fmtRate, fmtSignedPct, fmtSignedUnits, int, num, type SummaryRow, type WindowRow } from './healthUtils'

type Props = {
  modelId: string | null
  summary: SummaryRow | undefined
  windows: WindowRow[]
  size: number
  loading: boolean
  error: string | null
}

type Point = {
  key: string
  label: string
  avg: number | null
  err: number
  full: boolean
  measured: number
  bets: number
  dates: string
}

function BlockTip({ active, payload }: { active?: boolean; payload?: Array<{ payload: Point }> }) {
  if (!active || !payload?.length) return null
  const p = payload[0]!.payload
  return (
    <ChartTooltipBox title={`Bets ${p.label}`}>
      <div>{p.dates}</div>
      <div>Avg CLV {fmtSignedPct(p.avg)}{p.err ? ` ± ${p.err.toFixed(2)}` : ''}</div>
      <div>{p.measured} of {p.bets} bets with a closing price{p.full ? '' : ' · partial block'}</div>
    </ChartTooltipBox>
  )
}

export default function HealthBlocks({ modelId, summary, windows, size, loading, error }: Props) {
  const rows = useMemo(
    () => windows
      .filter(w => w.model_id === modelId && int(w.block_size) === size)
      .sort((a, b) => int(a.block_no) - int(b.block_no)),
    [windows, modelId, size],
  )

  const points = useMemo<Point[]>(() => [...rows].reverse().map(r => {
    const se = num(r.se_clv_pct)
    return {
      key: String(r.block_no),
      label: `#${int(r.newest_seq)}–${int(r.oldest_seq)}`,
      avg: num(r.avg_clv_pct),
      err: se != null ? Z95 * se : 0,
      full: r.full_block,
      measured: int(r.price_n),
      bets: int(r.bets),
      dates: `${fmtDate(r.first_date)} – ${fmtDate(r.last_date)}`,
    }
  }), [rows])

  if (loading) return <TableSkeleton rows={6} />
  if (error) return <PanelError message={error} />
  if (!modelId) return <EmptyState title="Pick a model">Click a model in the table above.</EmptyState>

  const bets = int(summary?.bets)

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <ModelName id={modelId} />
        <span className="ml-auto text-xs text-muted-foreground">
          {bets} bet{bets !== 1 ? 's' : ''} · {rows.length} block{rows.length !== 1 ? 's' : ''} of {size}{bets > 500 ? ' (newest 500)' : ''}
        </span>
      </div>

      {rows.length === 0 ? (
        <EmptyState title="No bets yet">This model has no graded, published bet.</EmptyState>
      ) : (
        <>
          <div className="h-[200px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid {...gridProps} vertical={false} />
                <XAxis dataKey="label" {...axisProps} interval="preserveStartEnd" />
                <YAxis {...axisProps} width={48} tickFormatter={v => `${v}%`} />
                <ReferenceLine y={0} stroke="var(--chart-axis)" />
                <Tooltip content={<BlockTip />} cursor={{ fill: 'hsl(var(--muted) / 0.6)' }} />
                <Bar dataKey="avg" isAnimationActive={false} radius={[3, 3, 0, 0]}>
                  {points.map(p => (
                    <Cell key={p.key} fill={PALETTE[0]} fillOpacity={p.full ? 0.9 : 0.4} />
                  ))}
                  <ErrorBar dataKey="err" width={4} strokeWidth={1} stroke="hsl(var(--foreground))" />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="table-frame fill">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="px-3">Bets</TableHead>
                  <TableHead className="px-3">Dates</TableHead>
                  <TableHead className="px-3 text-right">Closing price</TableHead>
                  <TableHead className="px-3 text-right">Avg CLV</TableHead>
                  <TableHead className="px-3 text-right">Beat rate</TableHead>
                  <TableHead className="px-3 text-right">Line moves</TableHead>
                  <TableHead className="px-3 text-right">No close</TableHead>
                  <TableHead className="px-3 text-right">Vs Pinnacle</TableHead>
                  <TableHead className="px-3 text-right">W-L-P</TableHead>
                  <TableHead className="px-3 text-right">Units</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map(r => {
                  const avg = num(r.avg_clv_pct)
                  const se = num(r.se_clv_pct)
                  const mkt = num(r.avg_market_clv_pct)
                  const units = num(r.units)
                  const roi = num(r.roi_pct)
                  return (
                    <TableRow key={`${r.block_size}-${r.block_no}`}>
                      <TableCell className="px-3 py-2 text-xs tabular-nums">
                        #{int(r.newest_seq)}–{int(r.oldest_seq)}
                        {!r.full_block && <span className="ml-1 text-muted-foreground">(partial)</span>}
                      </TableCell>
                      <TableCell className="whitespace-nowrap px-3 py-2 text-xs">{shortDate(r.first_date)} – {shortDate(r.last_date)}</TableCell>
                      <TableCell className="px-3 py-2 text-right text-xs tabular-nums">{int(r.price_n)} of {int(r.bets)}</TableCell>
                      <TableCell className="px-3 py-2 text-right">
                        <span className={cn('text-xs font-semibold tabular-nums', signedClass(avg))}>{fmtSignedPct(avg)}</span>
                        {se != null && <div className="text-[11px] tabular-nums text-muted-foreground">±{(Z95 * se).toFixed(2)}</div>}
                      </TableCell>
                      <TableCell className="px-3 py-2 text-right">
                        <span className="text-xs font-semibold tabular-nums">{fmtRate(num(r.beat_rate_with_line))}</span>
                        <div className="text-[11px] tabular-nums text-muted-foreground">price only {fmtRate(num(r.price_beat_rate))}</div>
                      </TableCell>
                      <TableCell className="whitespace-nowrap px-3 py-2 text-right text-xs tabular-nums">{int(r.line_for)} our way · {int(r.line_against)} against</TableCell>
                      <TableCell className="whitespace-nowrap px-3 py-2 text-right text-xs tabular-nums" title="In-play bets, and bets with no closing quote">
                        {int(r.in_play) + int(r.unmeasured)}
                      </TableCell>
                      <TableCell className={cn('px-3 py-2 text-right text-xs tabular-nums', signedClass(mkt))}>
                        {fmtSignedPct(mkt)}{int(r.market_n) > 0 && <span className="text-muted-foreground"> ({int(r.market_n)})</span>}
                      </TableCell>
                      <TableCell className="px-3 py-2 text-right text-xs tabular-nums">{int(r.wins)}-{int(r.losses)}-{int(r.pushes)}</TableCell>
                      <TableCell className="px-3 py-2 text-right">
                        <span className={cn('text-xs font-semibold tabular-nums', signedClass(units))}>{fmtSignedUnits(units)}</span>
                        <div className="text-[11px] tabular-nums text-muted-foreground">{roi == null ? '—' : fmtSignedPct(roi, 1)} ROI</div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        </>
      )}

      <Footnote>
        Bet #1 is the model’s newest bet, so the top row is the newest block. The chart runs oldest to newest, left to right; the whisker is the 95% margin of the block’s average CLV and a faded bar is a block that is not full yet. Up to the newest 500 bets are shown.
      </Footnote>
    </div>
  )
}
