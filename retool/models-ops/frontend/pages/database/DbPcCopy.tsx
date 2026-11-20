import { useMemo } from 'react'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { Clock, ListChecks, Archive, HardDrive, GitBranch, Laptop, History, CalendarClock } from 'lucide-react'
import { PanelError, StatsSkeleton, StatCard, EmptyState, Footnote, type StatTone } from '../../components/PanelUtils'
import { axisProps, gridProps, tooltipProps, legendProps } from '../../components/chartTheme'
import { fmtBytes, fmtBytesSigned, fmtCount, fmtPct, fmtSpan, fmtUtc, fmtAgo, hoursBetween, toGB } from './dbUtils'

/** One report from mike's PC (backend/ops/getPcCopy.ts). */
export type PcCopyDiffering = {
  table: string
  local_rows: number
  supabase_rows: number
  ranges_differ: number | null
  ranges_not_counted: number | null
  checked_at: string | null
}

export type PcCopyTrigger = { type: string; enabled: boolean | null; at?: string; delay?: string }

/** The LocalMirror task as Task Scheduler held it when the row was written. */
export type PcCopySchedule = {
  task: string
  read_at: string
  diff?: string
  full?: string
  state?: string | null
  next_run_at?: string | null
  last_run_at?: string | null
  last_result?: number | null
  triggers?: PcCopyTrigger[]
  last_full: { run_id: string | null; run_started_at: string | null; run_finished_at: string | null; failed_tables: string[] | null } | null
  next_full_from: string | null
  error?: string
}

export type PcCopyPoint = {
  taken_at: string
  source: string
  pass_id: string
  pass_started_at: string | null
  copy_run_id: string | null
  copy_started_at: string | null
  copy_finished_at: string | null
  copy_tables: number | null
  copy_rows_pulled: number | null
  copy_this_pass: boolean | null
  failed_tables: string[] | null
  differing_tables: PcCopyDiffering[] | null
  github_exit: number | null
  supabase_exit: number | null
  duckdb_exit: number | null
  github_finished_at: string | null
  github_repos: number | null
  github_repos_failed: number | null
  local_tables: number | null
  local_rows: number | null
  tables_bytes: number | null
  schema_bytes: number | null
  storage_bytes: number | null
  github_bytes: number | null
  duckdb_bytes: number | null
  other_bytes: number | null
  total_bytes: number | null
  disk_total_bytes: number | null
  disk_free_bytes: number | null
  /** diff (nightly) or full (monthly); null before 2026-11-20. */
  copy_kind: string | null
  schedule: PcCopySchedule | null
}

type PcCopyResult =
  | { ok: true; available: boolean; points: PcCopyPoint[]; total: number; firstAt: string | null }
  | { ok: false; message: string }

type Props = {
  data: unknown
  loading: boolean
  error: string | null
  now?: number
}

/** A night with no report: the copy runs at 00:30 and takes up to about ten hours. */
const STALE_HOURS = 36
/** The GitHub copy runs at the start of each nightly pass and takes minutes, so
 *  a finish older than a day and six hours means a night went without one. */
const GITHUB_STALE_HOURS = 30
const DISK_WARN_SHARE = 0.15
const DISK_CRIT_SHARE = 0.05

const SIZE_SERIES = [
  { key: 'database', label: 'Database copy', color: 'var(--series-1)' },
  { key: 'github', label: 'GitHub copy', color: 'var(--series-7)' },
  { key: 'other', label: 'Everything else (older snapshots, logs)', color: 'var(--series-4)' },
] as const

function tickDay(iso: unknown): string {
  const d = new Date(String(iso))
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })
}

/** A whole number with its sign: +44, -3, 0. */
function fmtSigned(n: number): string {
  return `${n > 0 ? '+' : ''}${n.toLocaleString('en-US')}`
}

/** How long until a time: "in 5 h", "in 3 days". */
function fmtUntil(iso: string | null | undefined, now: number): string {
  if (!iso) return '—'
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return '—'
  const h = (t - now) / 3_600_000
  if (h <= 0) return 'due now'
  return `in ${fmtSpan(h)}`
}

/** The kind of a run, in words. Runs before 2026-11-20 re-copied every small table whole. */
function kindLabel(kind: string | null | undefined): string {
  if (kind === 'diff') return 'Nightly diff'
  if (kind === 'full') return 'Monthly full'
  return 'Nightly (before 11-20)'
}

/** "Mon, Dec 1" from a date string. */
function fmtDay(date: string): string {
  const d = new Date(`${date}T12:00:00Z`)
  if (Number.isNaN(d.getTime())) return date
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC' })
}

/** The task's triggers in words: "daily at 00:30 Eastern, and 2 min after sign-in". */
function triggerText(triggers: PcCopyTrigger[] | undefined): string {
  const on = (triggers ?? []).filter(t => t.enabled !== false)
  const parts = on.map(t => {
    if (t.type === 'daily') return `daily at ${t.at ?? '?'} Eastern`
    if (t.type === 'sign-in') {
      const m = /PT(\d+)M/.exec(t.delay ?? '')
      return m ? `${m[1]} min after sign-in` : 'at sign-in'
    }
    return t.type
  })
  return parts.length ? parts.join(', and ') : 'no trigger is on'
}

/** Everything under the copy's folder that is not the database copy or GitHub. */
function otherBytes(p: PcCopyPoint): number | null {
  const parts = [p.schema_bytes, p.storage_bytes, p.duckdb_bytes, p.other_bytes]
  return parts.every(v => v == null) ? null : parts.reduce<number>((a, v) => a + (v ?? 0), 0)
}

export default function DbPcCopy({ data, loading, error, now = Date.now() }: Props) {
  const d = data as PcCopyResult | undefined
  const points = useMemo(() => (d && d.ok ? d.points : []), [d])
  const derived = useMemo(() => {
    const latest = points[points.length - 1]
    const nightly = [...points].reverse().find(p => p.source === 'nightly')
    const firstWithSize = points.find(p => p.total_bytes != null)
    const schedule = [...points].reverse().find(p => p.schedule != null)?.schedule ?? null
    // One line per copy run, newest first. A run reported twice (by hand, then
    // by the pass) is listed once.
    const seen = new Set<string>()
    const runs: PcCopyPoint[] = []
    for (const p of [...points].reverse()) {
      // A pass whose copy did not finish carries the previous run's numbers:
      // list the pass itself, not that run again.
      if (p.copy_this_pass === false) {
        runs.push(p)
        if (runs.length >= 14) break
        continue
      }
      if (!p.copy_started_at) continue
      const key = p.copy_run_id ?? p.copy_started_at
      if (seen.has(key)) continue
      seen.add(key)
      runs.push(p)
      if (runs.length >= 14) break
    }
    return { latest, nightly, firstWithSize, schedule, runs }
  }, [points])

  if (loading && points.length === 0) return <StatsSkeleton count={5} />
  const message = error ?? (d && !d.ok ? d.message : null)
  if (message) return <PanelError message={message} />
  if (d && d.ok && !d.available) {
    return (
      <EmptyState icon={Laptop} title="The PC copy table is not in the database yet">
        It is created by data/migrations/pc_copy_snapshots_2026_11_16.sql, which the worker applies on its next pass.
      </EmptyState>
    )
  }
  const { latest, nightly, firstWithSize, schedule, runs } = derived
  if (!latest) {
    return (
      <EmptyState icon={Laptop} title="No report from the PC yet">
        The PC writes one when each nightly copy ends (the copy starts at 00:30 Eastern, and two minutes after mike signs in).
      </EmptyState>
    )
  }

  // 1. The last nightly copy
  const firstReport = points[0] ?? latest
  const firstReportAge = (now - Date.parse(firstReport.taken_at)) / 3_600_000
  let copyValue = '—'
  let copyCaption = 'No nightly report yet. The PC writes one when each nightly copy ends (it starts at 00:30 Eastern, and two minutes after mike signs in).'
  let copyTone: StatTone | undefined
  if (!nightly && firstReportAge > STALE_HOURS) {
    copyCaption = `No nightly report in the ${fmtSpan(firstReportAge)} since the first report. The PC's LocalMirror task may not be running.`
    copyTone = 'warning'
  }
  if (nightly) {
    const reportAge = (now - Date.parse(nightly.taken_at)) / 3_600_000
    // Written at the start of the next pass, for a pass whose runner stopped
    // before its last step (local_mirror_report.py --catch-up): no exit codes.
    const caughtUp = nightly.github_exit == null && nightly.supabase_exit == null && nightly.duckdb_exit == null
    const ofTables = nightly.copy_tables != null
      ? ` · ${fmtCount(nightly.copy_tables)}${nightly.local_tables != null ? ` of ${fmtCount(nightly.local_tables)}` : ''} tables`
      : ''
    if (nightly.copy_this_pass && nightly.copy_finished_at) {
      const took = nightly.copy_started_at ? hoursBetween(nightly.copy_started_at, nightly.copy_finished_at) : null
      copyValue = fmtAgo(nightly.copy_finished_at, now)
      copyCaption = `${kindLabel(nightly.copy_kind)} · finished ${fmtUtc(nightly.copy_finished_at)}${took != null ? ` · took ${fmtSpan(took)}` : ''}${ofTables}${nightly.copy_rows_pulled != null ? ` · ${fmtCount(nightly.copy_rows_pulled)} rows copied` : ''}.`
      copyTone = nightly.supabase_exit
        ? 'critical'
        : reportAge > STALE_HOURS || caughtUp || nightly.duckdb_exit ? 'warning' : 'good'
      if (caughtUp) copyCaption += ' That pass stopped before it could report; the next pass recorded it, so its exit codes are unknown.'
      if (nightly.duckdb_exit) copyCaption += ` The SQL views (DuckDB) did not rebuild: code ${nightly.duckdb_exit}.`
      if (reportAge > STALE_HOURS) copyCaption += ' No report since: the copy may have missed a night.'
    } else {
      copyValue = 'Did not finish'
      copyCaption = `The pass that started ${fmtUtc(nightly.pass_started_at)} ended${nightly.supabase_exit != null ? ` with code ${nightly.supabase_exit}` : ''}. The last run that finished: ${fmtUtc(nightly.copy_finished_at)}${ofTables}.`
      copyTone = 'critical'
    }
  }

  // 2. Tables that differ from Supabase, at each table's latest check
  const differing = latest.differing_tables ?? []
  const failed = (nightly ?? latest).failed_tables ?? []
  // A table that could not be copied is a failure. A count that differs is
  // usually rows that changed between the copy and its check (the next run
  // takes them), so it asks for a look rather than raising an alarm.
  const diffTone: StatTone = failed.length ? 'critical' : differing.length ? 'warning' : 'good'
  const diffCaption = differing.length
    ? `${differing.slice(0, 3).map(t => t.table.replace(/^public\./, '')).join(', ')}${differing.length > 3 ? ` and ${differing.length - 3} more` : ''}: row counts differ at the latest check`
    : `All ${fmtCount(latest.local_tables)} tables matched Supabase at their latest check`
  const failedCaption = failed.length
    ? ` · ${failed.length} could not be copied in the last run: ${failed.slice(0, 2).map(t => t.replace(/^public\./, '')).join(', ')}${failed.length > 2 ? '…' : ''}`
    : ''

  // 3. Size, and how fast it grows
  const span = firstWithSize && latest.total_bytes != null && firstWithSize !== latest
    ? hoursBetween(firstWithSize.taken_at, latest.taken_at) : 0
  const growth = span >= 20 && firstWithSize?.total_bytes != null && latest.total_bytes != null
    ? ((latest.total_bytes - firstWithSize.total_bytes) / span) * 24 : null

  // 4. Free disk
  const freeShare = latest.disk_free_bytes != null && latest.disk_total_bytes
    ? latest.disk_free_bytes / latest.disk_total_bytes : null
  const diskTone: StatTone | undefined = freeShare == null ? undefined
    : freeShare < DISK_CRIT_SHARE ? 'critical' : freeShare < DISK_WARN_SHARE ? 'warning' : undefined

  // 5. The GitHub copy
  const ghStale = nightly != null && nightly.pass_started_at != null && nightly.github_finished_at != null
    && Date.parse(nightly.github_finished_at) < Date.parse(nightly.pass_started_at)
  const ghFailed = (latest.github_repos_failed ?? 0) > 0 || (nightly?.github_exit ?? 0) !== 0 || ghStale
  const ghAge = latest.github_finished_at ? (now - Date.parse(latest.github_finished_at)) / 3_600_000 : null
  const ghLate = ghAge == null || ghAge > GITHUB_STALE_HOURS
  const ghTone: StatTone = ghFailed ? 'critical' : ghLate ? 'warning' : 'good'
  const ghRepos = `${fmtCount(latest.github_repos)} repositories${latest.github_repos_failed ? `, ${latest.github_repos_failed} failed` : ''} · ${fmtBytes(latest.github_bytes)}`
  const ghExit = nightly?.github_exit ?? null
  const ghCaption = ghStale
    ? `The last pass's GitHub copy did not finish${ghExit ? ` (code ${ghExit})` : ''}. The last one that did: ${fmtUtc(latest.github_finished_at)}.`
    : ghExit
      ? `The last pass's GitHub step ended with code ${ghExit}. ${ghRepos}`
      : ghLate
        ? `None has finished since ${fmtUtc(latest.github_finished_at)}, so a night went without one. ${ghRepos}`
        : ghRepos

  // 6. The schedule, as Task Scheduler held it at the latest report
  let schedValue = '—'
  let schedCaption = 'Not reported yet. Reports from 2026-11-20 on read the schedule from the PC.'
  let schedTone: StatTone | undefined
  if (schedule) {
    const nextFull = schedule.next_full_from
      ? `the first run on or after ${fmtDay(schedule.next_full_from)}`
      : 'the next run'
    const lastFull = schedule.last_full?.run_started_at ? ` (last: ${fmtUtc(schedule.last_full.run_started_at)})` : ''
    if (schedule.error) {
      schedValue = 'Not read'
      schedCaption = `The PC could not read its task: ${schedule.error}. Monthly full: ${nextFull}${lastFull}.`
      schedTone = 'warning'
    } else {
      const disabled = schedule.state === 'Disabled'
      const daily = (schedule.triggers ?? []).some(t => t.type === 'daily' && t.enabled !== false)
      schedValue = disabled ? 'Off' : fmtUntil(schedule.next_run_at, now)
      schedCaption = `Nightly diff ${triggerText(schedule.triggers)}. Next run ${fmtUtc(schedule.next_run_at)}. Monthly full: ${nextFull}${lastFull}.`
      if (disabled) schedCaption = `The task is switched off in Task Scheduler. ${schedCaption}`
      else if (!daily) schedCaption = `No nightly trigger is on. ${schedCaption}`
      schedTone = disabled || !daily ? 'critical' : undefined
    }
  }

  const rows = points
    .filter(p => p.total_bytes != null)
    .map(p => ({ at: p.taken_at, database: toGB(p.tables_bytes), github: toGB(p.github_bytes), other: toGB(otherBytes(p)) }))

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <StatCard icon={Clock} label="Last nightly copy" value={copyValue} caption={copyCaption} tone={copyTone} />
        <StatCard icon={CalendarClock} label="Next backup" value={schedValue} caption={schedCaption} tone={schedTone} />
        <StatCard
          icon={ListChecks}
          label="Tables that differ"
          value={differing.length ? String(differing.length) : 'None'}
          caption={diffCaption + failedCaption}
          tone={diffTone}
        />
        <StatCard
          icon={Archive}
          label="Size of the copy"
          value={fmtBytes(latest.total_bytes)}
          caption={`Database ${fmtBytes(latest.tables_bytes)} · GitHub ${fmtBytes(latest.github_bytes)} · other ${fmtBytes(otherBytes(latest))} (older snapshots, logs, other jobs’ files)${growth != null ? ` · ${fmtBytesSigned(growth)}/day` : ''}`}
        />
        <StatCard
          icon={HardDrive}
          label="Free disk"
          value={fmtBytes(latest.disk_free_bytes)}
          caption={freeShare != null ? `${fmtPct(freeShare, 0)} of ${fmtBytes(latest.disk_total_bytes)} free` : 'Not reported'}
          tone={diskTone}
        />
        <StatCard
          icon={GitBranch}
          label="GitHub copy"
          value={fmtAgo(latest.github_finished_at, now)}
          caption={ghCaption}
          tone={ghTone}
        />
      </div>

      {(differing.length > 0 || failed.length > 0) && (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-xs">
            <thead className="bg-muted/50 text-left text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Table</th>
                <th className="px-3 py-2 text-right font-medium">On the PC</th>
                <th className="px-3 py-2 text-right font-medium">In Supabase</th>
                <th className="px-3 py-2 text-right font-medium">Difference</th>
                <th className="px-3 py-2 font-medium">Checked</th>
              </tr>
            </thead>
            <tbody>
              {differing.map(t => (
                <tr key={t.table} className="border-t">
                  <td className="px-3 py-1.5 font-medium">{t.table}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{t.local_rows.toLocaleString('en-US')}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{t.supabase_rows.toLocaleString('en-US')}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{fmtSigned(t.local_rows - t.supabase_rows)}</td>
                  <td className="px-3 py-1.5 text-muted-foreground">{fmtUtc(t.checked_at)}</td>
                </tr>
              ))}
              {failed.map(name => (
                <tr key={`failed-${name}`} className="border-t">
                  <td className="px-3 py-1.5 font-medium">{name}</td>
                  <td className="px-3 py-1.5 text-muted-foreground" colSpan={4}>Could not be copied in the last run; the next run tries again.</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {runs.length > 0 && (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-xs">
            <caption className="px-3 py-2 text-left text-muted-foreground">
              Backup runs, newest first. A nightly diff copies only rows that are new or changed; the monthly full checks every row against Supabase and every file on the PC.
            </caption>
            <thead className="bg-muted/50 text-left text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Started</th>
                <th className="px-3 py-2 font-medium">Kind</th>
                <th className="px-3 py-2 text-right font-medium">Took</th>
                <th className="px-3 py-2 text-right font-medium">Rows copied</th>
                <th className="px-3 py-2 font-medium">Result</th>
              </tr>
            </thead>
            <tbody>
              {runs.map(r => {
                const unfinished = r.copy_this_pass === false
                const took = !unfinished && r.copy_started_at && r.copy_finished_at ? hoursBetween(r.copy_started_at, r.copy_finished_at) : null
                const code = r.supabase_exit
                const result = unfinished
                  ? `Did not finish${code ? ` (code ${code})` : ''}`
                  : code == null ? 'Finished (no exit code)' : code === 0 ? 'OK' : `Ended with code ${code}`
                return (
                  <tr key={unfinished ? `pass-${r.pass_id}` : r.copy_run_id ?? r.copy_started_at ?? r.pass_id} className="border-t">
                    <td className="px-3 py-1.5">{fmtUtc(unfinished ? r.pass_started_at : r.copy_started_at)}</td>
                    <td className="px-3 py-1.5">{unfinished ? '—' : kindLabel(r.copy_kind)}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{took != null ? fmtSpan(took) : '—'}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{unfinished ? '—' : fmtCount(r.copy_rows_pulled)}</td>
                    <td className="px-3 py-1.5 text-muted-foreground">{result}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {rows.length >= 2 ? (
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid {...gridProps} vertical={false} />
              <XAxis dataKey="at" tickFormatter={tickDay} minTickGap={28} {...axisProps} />
              <YAxis {...axisProps} width={48} tickFormatter={(v: number) => `${Math.round(v)} GB`} />
              <Tooltip
                {...tooltipProps}
                labelFormatter={(iso: unknown) => fmtUtc(String(iso))}
                formatter={(value: unknown, name: unknown) => [`${Number(value).toFixed(2)} GB`, String(name)] as [string, string]}
              />
              <Legend {...legendProps} />
              {SIZE_SERIES.map(s => (
                <Area
                  key={s.key}
                  type="monotone"
                  dataKey={s.key}
                  name={s.label}
                  stackId="size"
                  stroke={s.color}
                  fill={s.color}
                  fillOpacity={0.35}
                  strokeWidth={1.75}
                  isAnimationActive={false}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <EmptyState icon={History} title={`Size history starts ${fmtUtc(points[0]?.taken_at)}`}>
          Each report records the size of every copy, so the line appears with the next report.
        </EmptyState>
      )}

      <Footnote>
        Newest report {fmtUtc(latest.taken_at)} ({latest.source === 'nightly' ? 'after the nightly copy' : 'by hand'}).
        {' '}{(d && d.ok ? d.total : points.length).toLocaleString('en-US')} report{(d && d.ok ? d.total : points.length) === 1 ? '' : 's'} stored{d && d.ok && d.firstAt ? ` since ${fmtUtc(d.firstAt)}` : ''}; none is ever deleted.
        {' '}Copied tables: {fmtCount(latest.local_tables)}, {fmtCount(latest.local_rows)} rows. Sizes are bytes on the PC’s disk (1 GB = 1,024³ bytes).
      </Footnote>
    </div>
  )
}
