import { useMemo, useState } from 'react'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '../../lib/shadcn/table'
import { PanelError, TableSkeleton, NullCell, Chip, Footnote, fmtDateTime } from '../../components/PanelUtils'
import { StatusBadge } from '../../components/StatusBadge'
import { Switch } from '../../lib/shadcn/switch'
import { useModelNames } from '../../components/models/modelNames'

type CoverageRow = {
  sport: string
  game_date: string
  scheduled: number
  covered: number
  missing: number
}

type BoardRow = {
  game_id: string
  sport: string
  game_date: string
  home_team: string
  venue: string
  temp_f: number
  wind_mph: number
  wind_out: number
  precip_mm: number
  is_dome: number
  fetched_at: string
  lead_days: number
}

type FreshnessRow = {
  newest: string | null
  oldest: string | null
  upcoming_rows: number
}

type WeatherBoardData = {
  coverage: CoverageRow[]
  board: BoardRow[]
  freshness: FreshnessRow | null
}

type Props = {
  data: unknown
  loading: boolean
  error: string | null
}

type SportFilter = 'All' | 'MLB' | 'NCAAF'

/**
 * Every numeric column, null-guarded. All 28,623 rows written to date are
 * non-null, so this never fires today — it is here because a partial row from
 * the weather ingest would otherwise throw during render and take out the whole
 * Ops tab, not just this panel.
 */
function num(v: number | null | undefined, dp = 1, suffix = ''): string | null {
  if (v == null || Number.isNaN(v)) return null
  return v.toFixed(dp) + suffix
}

function isNotable(row: BoardRow): boolean {
  return row.is_dome === 0 && ((row.wind_mph ?? 0) >= 11 || (row.precip_mm ?? 0) > 0)
}

function CoverageCard({ sport, rows }: { sport: string; rows: CoverageRow[] }) {
  const totalScheduled = rows.reduce((s, r) => s + r.scheduled, 0)
  const totalCovered = rows.reduce((s, r) => s + r.covered, 0)
  const missingRows = rows.filter(r => r.missing > 0)
  const totalMissing = missingRows.reduce((s, r) => s + r.missing, 0)

  return (
    <div className="min-w-[180px] space-y-1.5 rounded-[10px] border bg-raised p-3 text-xs">
      <div className="text-sm font-semibold text-foreground">
        {sport === 'MLB' ? 'MLB · today' : 'NCAAF · next 7 days'}
      </div>
      <div className="text-muted-foreground">
        {totalCovered} / {totalScheduled} covered
      </div>
      {totalMissing > 0 ? (
        <>
          <StatusBadge label={`${totalMissing} missing`} variant="warn" />
          <div className="space-y-0.5 pt-0.5 text-[11px] text-muted-foreground">
            {missingRows.map(r => (
              <div key={r.game_date}>{r.game_date} ({r.missing})</div>
            ))}
          </div>
        </>
      ) : totalScheduled > 0 ? (
        <StatusBadge label="Complete" variant="ok" />
      ) : (
        <span className="text-muted-foreground">No games scheduled</span>
      )}
    </div>
  )
}

export default function WeatherBoard({ data, loading, error }: Props) {
  const { coverage, board, freshness } = useMemo<WeatherBoardData>(() => {
    const d = data as WeatherBoardData | undefined
    return d ?? { coverage: [], board: [], freshness: null }
  }, [data])

  const [sportFilter, setSportFilter] = useState<SportFilter>('All')
  const [notableOnly, setNotableOnly] = useState(true)
  const windModel = useModelNames().modelLabel('nfl_wind_totals').name

  const mlbRows = useMemo(() => coverage.filter(r => r.sport === 'MLB'), [coverage])
  const ncaafRows = useMemo(() => coverage.filter(r => r.sport === 'NCAAF'), [coverage])

  const staleFreshness = useMemo(() => {
    if (!freshness?.newest || !freshness?.oldest) return false
    const diff = Math.abs(new Date(freshness.newest).getTime() - new Date(freshness.oldest).getTime())
    return diff > 24 * 60 * 60 * 1000
  }, [freshness])

  const filtered = useMemo(() => {
    let rows = board
    if (sportFilter !== 'All') rows = rows.filter(r => r.sport === sportFilter)
    if (notableOnly) rows = rows.filter(isNotable)
    return rows
  }, [board, sportFilter, notableOnly])

  if (loading) return <TableSkeleton rows={6} />
  if (error) return <PanelError message={error} />

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      {/* Coverage strip */}
      <div className="space-y-2">
        <div className="flex flex-wrap gap-3">
          <CoverageCard sport="MLB" rows={mlbRows} />
          <CoverageCard sport="NCAAF" rows={ncaafRows} />
        </div>
        {freshness?.newest && (
          <div className="flex items-center gap-2 flex-wrap text-xs text-muted-foreground">
            <span>Forecasts fetched: <span className="font-semibold text-foreground tabular-nums">{fmtDateTime(freshness.newest)}</span></span>
            {staleFreshness && (
              <>
                <StatusBadge label="Stale" variant="stale" />
                <span>oldest: <span className="tabular-nums">{fmtDateTime(freshness.oldest)}</span></span>
              </>
            )}
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-1.5">
          {(['All', 'MLB', 'NCAAF'] as SportFilter[]).map(s => (
            <Chip key={s} active={sportFilter === s} onClick={() => setSportFilter(s)}>{s}</Chip>
          ))}
        </div>
        <label className="flex cursor-pointer select-none items-center gap-2 text-xs text-secondary-fg">
          <Switch checked={notableOnly} onCheckedChange={setNotableOnly} aria-label="Notable only" />
          Notable only (wind ≥ 11 mph or precip &gt; 0, outdoor)
        </label>
        <span className="ml-auto text-xs text-muted-foreground">
          Showing <span className="font-semibold text-foreground">{filtered.length}</span> of {board.length}
        </span>
      </div>

      {/* Table */}
      <div className="table-frame fill">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="px-3">Sport</TableHead>
              <TableHead className="px-3">Date</TableHead>
              <TableHead className="px-3">Home</TableHead>
              <TableHead className="px-3">Venue</TableHead>
              <TableHead className="px-3 text-right">Temp</TableHead>
              <TableHead className="px-3 text-right">Wind</TableHead>
              <TableHead className="px-3 text-right">Wind out</TableHead>
              <TableHead className="px-3 text-right">Precip</TableHead>
              <TableHead className="px-3">Dome</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} className="py-10 text-center text-sm text-muted-foreground">
                  No games match these filters. Turn off Notable only to see every forecast.
                </TableCell>
              </TableRow>
            ) : (
              filtered.map(row => {
                const windNotable = (row.wind_mph ?? 0) >= 11 && row.is_dome === 0
                const leadLabel = row.lead_days === 0 ? 'today' : `+${row.lead_days}d`
                return (
                  <TableRow key={row.game_id} className="align-middle">
                    <TableCell className="px-3 py-2">
                      <span className="text-xs font-medium">{row.sport}</span>
                    </TableCell>
                    <TableCell className="whitespace-nowrap px-3 py-2">
                      <span className="text-xs">{row.game_date}</span>
                      {' '}
                      <span className="text-[11px] text-muted-foreground">{leadLabel}</span>
                    </TableCell>
                    <TableCell className="max-w-[140px] px-3 py-2">
                      <span className="block truncate text-xs" title={row.home_team}>{row.home_team}</span>
                    </TableCell>
                    <TableCell className="max-w-[160px] px-3 py-2">
                      <span className="block truncate text-xs text-muted-foreground" title={row.venue}>{row.venue}</span>
                    </TableCell>
                    <TableCell className="px-3 py-2 text-right text-xs">
                      {num(row.temp_f, 1, '°F') ?? <NullCell />}
                    </TableCell>
                    <TableCell className="px-3 py-2 text-right text-xs">
                      <span className={windNotable ? 'font-semibold text-foreground underline decoration-dotted underline-offset-2' : ''} title={windNotable ? 'At or above 11 mph, outdoor' : undefined}>
                        {num(row.wind_mph, 1, ' mph') ?? <NullCell />}
                      </span>
                    </TableCell>
                    <TableCell className="px-3 py-2 text-right text-xs">
                      {row.sport === 'MLB' ? (num(row.wind_out, 1) ?? <NullCell />) : <NullCell />}
                    </TableCell>
                    <TableCell className="px-3 py-2 text-right text-xs">
                      {(row.precip_mm ?? 0) > 0 ? (num(row.precip_mm, 1, ' mm') ?? <NullCell />) : <NullCell />}
                    </TableCell>
                    <TableCell className="px-3 py-2">
                      {row.is_dome === 1
                        ? <StatusBadge label="Dome" variant="muted" />
                        : <NullCell />}
                    </TableCell>
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
      </div>

      {/* Footnotes */}
      <Footnote className="space-y-1.5">
        <p>
          <strong>MLB</strong> weather is fetched for <strong>game day only</strong> (<code>run_pipeline step_weather</code>), so tomorrow's MLB slate showing no rows is the normal cadence, not a gap.{' '}
          <strong>NCAAF</strong> is fetched for the <strong>next 7 days</strong> (<code>step_ncaaf_weather</code>).
        </p>
        <p>
          <strong>NFL and UFC are absent by design.</strong> UFC has no venue weather, and the NFL wind model runs on its own Open-Meteo pipeline with a file cache (<code>nfl/data_ingest/weather.py</code>), not this table — so nothing here reflects NFL.
        </p>
        <p>
          <strong>Wind out</strong> is MLB-only; a dash means not computed, not zero wind.
        </p>
        <p>
          <strong>11 mph</strong> is the cut the {windModel} model uses to take the under on outdoor NFL games — the only wind threshold in the repo with a measured record. It is shown here <strong>as a reference line only</strong>; these are MLB and NCAAF games, and no staked model keys off wind for them. Weather here feeds model features (temperature, wind and precipitation), it is not itself a signal.
        </p>
      </Footnote>
    </div>
  )
}
