import { useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts'
import {
  Coins, Percent, Trophy, CalendarDays, CalendarClock, TrendingDown, TrendingUp, Minus,
  Layers, Scale, Award, CheckCircle2, XCircle, AlertTriangle, Gauge, Target,
} from 'lucide-react'
import { StatCard, StatsSkeleton, ChartSkeleton, PanelError, EmptyState, Footnote, signedClass } from '../../components/PanelUtils'
import { PALETTE, axisProps, gridProps, ChartTooltipBox, shortDate } from '../../components/chartTheme'
import { ModelName } from '../../components/models/ModelName'
import { Badge } from '../../components/StatusBadge'
import { cn } from '../../lib/shadcn/utils'
import { VERDICT } from '../health/healthUtils'
import {
  CREDIT_RESERVE_DAYS, fmtInt, fmtPctSigned, fmtShare, fmtUnitsSigned, n, nOrNull,
  type ClvRow, type CountsRow, type CheckRow, type CreditsRow, type Equity, type EquityPoint,
  type ModelBuckets, type ModelView, type PipelineRow, type Totals, type WindowTotals,
} from './keyMetrics'

function Signed({ v, text }: { v: number | null; text: string }) {
  return <span className={signedClass(v)}>{text}</span>
}

// ── Results ──────────────────────────────────────────────────────────────────

export function ResultsStrip({ totals, last30, last7, equity, firstDate, lastDate, loading, error }: {
  totals: Totals; last30: WindowTotals; last7: WindowTotals; equity: Equity
  firstDate: string | null; lastDate: string | null; loading: boolean; error: string | null
}) {
  if (loading) return <StatsSkeleton count={6} />
  if (error) return <PanelError message={error} />
  const perDay = last30.bets / last30.days
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        <StatCard label="Units won" icon={Coins}
          value={<Signed v={totals.units} text={fmtUnitsSigned(totals.units)} />}
          caption={`on ${totals.risked.toFixed(1)}u risked, ${fmtInt(totals.bets)} bets`} />
        <StatCard label="Return on risk" icon={Percent}
          value={<Signed v={totals.roi} text={fmtPctSigned(totals.roi)} />}
          caption="units won ÷ units risked" />
        <StatCard label="Record" icon={Trophy}
          value={`${fmtInt(totals.wins)}-${fmtInt(totals.losses)}-${fmtInt(totals.pushes)}`}
          caption={totals.hitRate != null ? `${(totals.hitRate * 100).toFixed(1)}% of decided bets won` : '—'} />
        <StatCard label="Last 30 days" icon={CalendarDays}
          value={<Signed v={last30.units} text={fmtUnitsSigned(last30.units)} />}
          caption={`${fmtPctSigned(last30.roi)} return, ${fmtInt(last30.bets)} bets (${perDay.toFixed(1)} a day)`} />
        <StatCard label="Last 7 days" icon={CalendarClock}
          value={<Signed v={last7.units} text={fmtUnitsSigned(last7.units)} />}
          caption={`${fmtPctSigned(last7.roi)} return, ${fmtInt(last7.bets)} bets`} />
        <StatCard label="Deepest drop from a high" icon={TrendingDown}
          value={equity.maxDrop > 0 ? `−${equity.maxDrop.toFixed(2)}u` : '0.00u'}
          caption={equity.maxDropFrom && equity.maxDropTo
            ? `${shortDate(equity.maxDropFrom)} to ${shortDate(equity.maxDropTo)}; now ${equity.belowNow > 0 ? `${equity.belowNow.toFixed(2)}u below the high` : 'at the high'}`
            : 'no drop yet'} />
      </div>
      <Footnote>
        The published record: every graded bet the app, Discord and the record pages count, from {firstDate ? shortDate(firstDate) : '—'} to {lastDate ? shortDate(lastDate) : '—'}, in units at the posted stake. "Last 30 days" and "Last 7 days" are game dates ending today (Eastern). The deepest drop is measured day by day on the running total.
      </Footnote>
    </div>
  )
}

function EquityTip({ active, payload }: { active?: boolean; payload?: Array<{ payload: EquityPoint }> }) {
  if (!active || !payload?.length) return null
  const p = payload[0]!.payload
  return (
    <ChartTooltipBox title={shortDate(p.date)}>
      <div>Running total: {fmtUnitsSigned(p.cum)}</div>
      <div>That day: {fmtUnitsSigned(p.day)} over {p.bets} bet{p.bets === 1 ? '' : 's'}</div>
      {p.below > 0 && <div>{p.below.toFixed(2)}u below the high</div>}
    </ChartTooltipBox>
  )
}

export function EquityChart({ equity, loading, error }: { equity: Equity; loading: boolean; error: string | null }) {
  if (loading) return <ChartSkeleton height={260} />
  if (error) return <PanelError message={error} />
  if (equity.points.length === 0) return <EmptyState title="No graded bets yet">The running total starts with the first graded bet.</EmptyState>
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="h-[260px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={equity.points} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid {...gridProps} vertical={false} />
            <XAxis dataKey="date" {...axisProps} tickFormatter={shortDate} minTickGap={32} />
            <YAxis {...axisProps} width={52} tickFormatter={v => `${v}u`} />
            <ReferenceLine y={0} stroke="var(--chart-axis)" />
            <Tooltip content={<EquityTip />} cursor={{ stroke: 'var(--chart-axis)', strokeWidth: 1 }} />
            <Line dataKey="cum" stroke={PALETTE[0]} strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: 'hsl(var(--card))' }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <Footnote>Units won to date, by game date. Hover a day for its result.</Footnote>
    </div>
  )
}

// ── Beating the close ────────────────────────────────────────────────────────

export function ClvSplit({ clv, loading, error }: { clv: ClvRow | null; loading: boolean; error: string | null }) {
  if (loading) return <ChartSkeleton height={260} />
  if (error) return <PanelError message={error} />
  if (!clv || n(clv.measured) === 0) return <EmptyState title="Nothing measured yet">No pre-game bet has a closing price yet.</EmptyState>
  const total = n(clv.measured)
  const parts = [
    { key: 'beat', label: 'Beat the close', count: n(clv.beat), color: 'var(--clv-beat)', icon: TrendingUp,
      detail: `${fmtInt(n(clv.beat_price))} on price, ${fmtInt(n(clv.beat_line))} on the number` },
    { key: 'matched', label: 'Matched it', count: n(clv.matched), color: 'var(--clv-flat)', icon: Minus,
      detail: 'closed at the price we took' },
    { key: 'trailed', label: 'Trailed it', count: n(clv.trailed), color: 'var(--clv-worse)', icon: TrendingDown,
      detail: `${fmtInt(n(clv.trailed_price))} on price, ${fmtInt(n(clv.trailed_line))} on the number` },
  ]
  const pinRate = n(clv.pin_n) > 0 ? n(clv.pin_beat) / n(clv.pin_n) : null
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <div>
        <div className="sb-figure text-[28px] font-semibold leading-tight tracking-tight text-foreground">
          {fmtShare(n(clv.beat), total)} <span className="text-base font-medium text-muted-foreground">beat the closing line</span>
        </div>
        <div className="mt-1 text-xs text-muted-foreground">
          of the {fmtInt(total)} pre-game bets with a closing price or a line move
        </div>
      </div>
      <div className="flex h-4 w-full gap-[2px] overflow-hidden rounded-full" role="img"
        aria-label={parts.map(p => `${p.label} ${p.count}`).join(', ')}>
        {parts.filter(p => p.count > 0).map(p => (
          <div key={p.key} title={`${p.label}: ${fmtInt(p.count)} (${fmtShare(p.count, total)})`}
            style={{ flexGrow: p.count, background: p.color }} className="h-full first:rounded-l-full last:rounded-r-full" />
        ))}
      </div>
      <ul className="space-y-2">
        {parts.map(p => {
          const Icon = p.icon
          return (
            <li key={p.key} className="flex items-start gap-2 text-sm">
              <span className="mt-1.5 inline-block h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: p.color }} aria-hidden />
              <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
              <div className="min-w-0">
                <div className="font-medium text-foreground">
                  {p.label}: <span className="tabular-nums">{fmtInt(p.count)}</span>{' '}
                  <span className="text-muted-foreground tabular-nums">({fmtShare(p.count, total)})</span>
                </div>
                <div className="text-xs text-muted-foreground">{p.detail}</div>
              </div>
            </li>
          )
        })}
      </ul>
      <div className="grid grid-cols-2 gap-3 border-t pt-3 text-sm">
        <div>
          <div className="text-xs text-muted-foreground">Average price gain at the close</div>
          <div className="sb-figure text-lg font-semibold"><Signed v={nOrNull(clv.avg_clv_pct)} text={fmtPctSigned(nOrNull(clv.avg_clv_pct))} /></div>
          <div className="text-xs text-muted-foreground">bets that closed at our number</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Against Pinnacle’s fair price</div>
          <div className="sb-figure text-lg font-semibold">
            {pinRate != null ? `${Math.round(pinRate * 100)}% beat` : '—'}{' '}
            <span className="text-sm"><Signed v={nOrNull(clv.pin_avg_pct)} text={fmtPctSigned(nOrNull(clv.pin_avg_pct))} /></span>
          </div>
          <div className="text-xs text-muted-foreground">{fmtInt(n(clv.pin_n))} bets, the stricter test</div>
        </div>
      </div>
      <Footnote>
        Each bet is compared with its own book’s last price before the start, at the exact number we bet. When the book still offered our number, the price decides it; when the book had moved the number, the move decides it. Not counted: {fmtInt(n(clv.in_play))} in-play bets (no pre-game close, by design) and {fmtInt(n(clv.no_close))} with no closing price. Pinnacle’s figure still uses the earlier timing rule (#1482).
      </Footnote>
    </div>
  )
}

// ── Models ───────────────────────────────────────────────────────────────────

export function ModelsStrip({ counts, buckets, loading, error }: {
  counts: CountsRow | null; buckets: ModelBuckets; loading: boolean; error: string | null
}) {
  if (loading) return <StatsSkeleton count={5} />
  if (error) return <PanelError message={error} />
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
      <StatCard label="Live models" icon={Layers} value={counts ? fmtInt(n(counts.live)) : '—'}
        caption={counts ? `${fmtInt(n(counts.paused))} paused` : undefined} />
      <StatCard label="Models in profit" icon={Scale} value={`${buckets.up} of ${buckets.withBets}`}
        caption={`${buckets.down} down, over their published bets`} />
      <StatCard label="50+ bets and in profit" icon={Award} value={`${buckets.fiftyUp} of ${buckets.fiftyPlus}`}
        caption="models with at least 50 graded bets" />
      <StatCard label="Beating the close" icon={Target} value={fmtInt(buckets.beats)}
        caption="models whose average CLV is above zero by more than its 95% margin" />
      <StatCard label="Trailing the close" icon={TrendingDown} value={fmtInt(buckets.trails)}
        caption="models whose average CLV is below zero by more than its 95% margin" />
    </div>
  )
}

export function ModelList({ rows, loading, error, empty }: { rows: ModelView[]; loading: boolean; error: string | null; empty: string }) {
  if (loading) return <StatsSkeleton count={3} />
  if (error) return <PanelError message={error} />
  if (rows.length === 0) return <EmptyState title="No models yet">{empty}</EmptyState>
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b text-xs text-muted-foreground">
          <th className="py-2 pr-2 text-left font-medium">Model</th>
          <th className="py-2 px-2 text-right font-medium">Bets</th>
          <th className="py-2 px-2 text-right font-medium">Units</th>
          <th className="py-2 px-2 text-right font-medium">Return</th>
          <th className="py-2 pl-2 text-right font-medium">Against the close</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(m => {
          const v = VERDICT[m.verdict]
          return (
            <tr key={m.model_id} className="border-b last:border-0">
              <td className="py-2 pr-2"><ModelName id={m.model_id} className="max-w-[240px]" /></td>
              <td className="py-2 px-2 text-right tabular-nums">{fmtInt(n(m.bets))}</td>
              <td className={cn('py-2 px-2 text-right font-medium tabular-nums', signedClass(n(m.units)))}>{fmtUnitsSigned(n(m.units))}</td>
              <td className={cn('py-2 px-2 text-right tabular-nums', signedClass(m.roi))}>{fmtPctSigned(m.roi, 1)}</td>
              <td className="py-2 pl-2 text-right"><Badge tone={v.tone} title={v.help}>{v.label}</Badge></td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

// ── Operations ───────────────────────────────────────────────────────────────

function ago(iso: string | null | undefined): string {
  if (!iso) return '—'
  const t = new Date(iso).getTime()
  if (!Number.isFinite(t)) return '—'
  const h = (Date.now() - t) / 3_600_000
  return h < 1 ? `${Math.max(1, Math.round(h * 60))} min ago` : h < 48 ? `${h.toFixed(1)} h ago` : `${(h / 24).toFixed(1)} days ago`
}

export function OpsStrip({ pipeline, checks, credits, clv, loading, error }: {
  pipeline: PipelineRow | null; checks: CheckRow | null; credits: CreditsRow | null; clv: ClvRow | null
  loading: boolean; error: string | null
}) {
  const coverage = useMemo(() => {
    if (!clv) return null
    const pre = n(clv.measured) + n(clv.no_close)
    return pre > 0 ? n(clv.measured) / pre : null
  }, [clv])
  if (loading) return <StatsSkeleton count={4} />
  if (error) return <PanelError message={error} />

  const pipeOk = pipeline?.ok === true && n(pipeline.steps_failed) === 0
  const remaining = nOrNull(credits?.remaining)
  const burn = nOrNull(credits?.median_burn)
  const runway = remaining != null && burn != null && burn > 0 ? remaining / burn : null
  const lowCredits = runway != null && runway < CREDIT_RESERVE_DAYS
  const problems = n(checks?.problems)

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard label="Daily pipeline" icon={pipeOk ? CheckCircle2 : XCircle} tone={pipeline ? (pipeOk ? 'good' : 'critical') : undefined}
        value={pipeline ? (pipeOk ? 'Ran clean' : `${n(pipeline.steps_failed)} step${n(pipeline.steps_failed) === 1 ? '' : 's'} failed`) : '—'}
        caption={pipeline ? `started ${ago(pipeline.started_at)}${pipeline.failed_steps ? `: ${pipeline.failed_steps}` : ''}` : 'no run recorded'} />
      <StatCard label="Health checks" icon={problems > 0 ? AlertTriangle : CheckCircle2} tone={checks ? (problems > 0 ? 'warning' : 'good') : undefined}
        value={checks ? (problems > 0 ? `${problems} need a look` : 'All passing') : '—'}
        caption={checks ? `${n(checks.ok)} passing, ${n(checks.skipped)} skipped${checks.problem_names ? `; ${checks.problem_names}` : ''}` : undefined} />
      <StatCard label="Odds feed credits" icon={Gauge} tone={lowCredits ? 'critical' : undefined}
        value={remaining != null ? fmtInt(remaining) : '—'}
        caption={runway != null && burn != null
          ? `about ${Math.floor(runway)} days at the median ${fmtInt(burn)} a day (last ${n(credits?.burn_days)} days); read ${ago(credits?.observed_at)}`
          : 'no daily use measured'} />
      <StatCard label="Pre-game bets with a close" icon={Target}
        value={coverage != null ? `${(coverage * 100).toFixed(1)}%` : '—'}
        caption={clv ? `${fmtInt(n(clv.measured))} measured, ${fmtInt(n(clv.no_close))} with no closing price` : undefined} />
    </div>
  )
}
