import { useEffect, useMemo, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Input } from '../../lib/shadcn/input'
import { Button } from '../../lib/shadcn/button'
import { Switch } from '../../lib/shadcn/switch'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../lib/shadcn/select'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '../../lib/shadcn/table'
import { TableSkeleton, PanelError, NullCell, fmtUnits, fmtDate, signedClass, Chip, ChipGroup } from '../../components/PanelUtils'
import { ModelName } from '../../components/models/ModelName'
import { useModelNames } from '../../components/models/modelNames'
import { InPlayBadge } from '../../components/StatusBadge'
import { cn } from '../../lib/shadcn/utils'
import { useSetModelVolume } from '../../hooks/backend/ops'

type Band = 'all' | 'top_75' | 'top_half' | 'top_quarter'
type Level = Band | 'custom'

export type VolumeBandRow = {
  model_id: string
  sport: string
  paused: boolean
  in_play: boolean
  cut_on: 'edge' | 'probability'
  band: Band
  band_order: number
  threshold: string | null
  config_cut: string | null
  cut_in_force: string | null
  setting: 'top_75' | 'top_half' | 'top_quarter' | 'custom' | null
  setting_value: string | null
  setting_in_force: boolean | null
  setting_by: string | null
  setting_at: string | null
  first_bet_date: string | null
  last_bet_date: string | null
  enough_bets: boolean
  bets_per_day: string | null
  wins: string | null
  losses: string | null
  units: string | null
  roi_pct: string | null
}

type ModelGroup = {
  first: VolumeBandRow
  bands: Partial<Record<Band, VolumeBandRow>>
}

type SetResult = { ok: true } | { ok: false; message: string }

type Props = {
  data: unknown
  loading: boolean
  error: string | null
  /** Re-reads the bands (and the roster); resolves when the bands are back. */
  onChanged: () => Promise<void>
}

const BANDS: { key: Band; label: string }[] = [
  { key: 'all', label: 'All bets' },
  { key: 'top_75', label: 'Top 75%' },
  { key: 'top_half', label: 'Top half' },
  { key: 'top_quarter', label: 'Top quarter' },
]

const LEVEL_WORDS: Record<Level, string> = {
  all: 'All bets (no setting)',
  top_75: 'Top 75%',
  top_half: 'Top half',
  top_quarter: 'Top quarter',
  custom: 'Custom number…',
}

function num(v: string | null | undefined): number | null {
  if (v == null || v === '') return null
  const n = parseFloat(v)
  return isNaN(n) ? null : n
}

function fmtFixed(v: string | null | undefined, dp: number): string {
  const n = num(v)
  return n == null ? '—' : n.toFixed(dp)
}

function shortDate(v: string | null): string | null {
  if (!v || v.length < 10) return null
  return v.slice(5, 10)
}

function unitsColor(v: string | null): string {
  return signedClass(num(v))
}

function parseCustom(text: string): number | null {
  if (text.trim() === '') return null
  const n = Number(text)
  if (!Number.isFinite(n) || n < 0 || n >= 1) return null
  return n
}

function BandCell({ row }: { row: VolumeBandRow | undefined }) {
  if (!row || row.threshold == null) {
    return (
      <div className="text-xs leading-tight">
        <NullCell />
        <div className="text-[10px] text-muted-foreground">under 20 bets</div>
      </div>
    )
  }
  const bpd = num(row.bets_per_day)
  return (
    <div className="text-xs leading-tight tabular-nums space-y-0.5">
      <div className="font-mono text-[11px]">{fmtFixed(row.threshold, 4)}</div>
      <div className="text-muted-foreground">{bpd == null ? '—' : bpd.toFixed(1)} a day</div>
      <div>
        {row.wins ?? 0}-{row.losses ?? 0},{' '}
        <span className={cn('font-semibold', unitsColor(row.units))}>{fmtUnits(row.units)}</span>
      </div>
    </div>
  )
}

function SettingCell({ m }: { m: VolumeBandRow }) {
  if (!m.setting) return <span className="text-xs text-muted-foreground">none</span>
  const words = m.setting === 'custom'
    ? `Custom ${fmtFixed(m.setting_value, 4)}`
    : LEVEL_WORDS[m.setting]
  return (
    <div className="text-xs leading-tight">
      <div className="font-medium">{words}</div>
      <div className="text-[10px] text-muted-foreground">
        by {m.setting_by ?? '—'}, {fmtDate(m.setting_at)}
      </div>
    </div>
  )
}

const COL_COUNT = 12

function VolumeRow({
  group,
  apply,
}: {
  group: ModelGroup
  apply: (modelId: string, level: Level, value: number | null, note: string | null) => Promise<SetResult>
}) {
  const m = group.first
  const current: Level = m.setting ?? 'all'
  const currentValue = m.setting === 'custom' ? (m.setting_value ?? '') : ''

  const [choice, setChoice] = useState<Level>(current)
  const [customText, setCustomText] = useState(currentValue)
  const [note, setNote] = useState('')
  const [pending, setPending] = useState(false)
  const [rowError, setRowError] = useState<string | null>(null)

  // Follow the stored setting after a successful apply re-reads the bands
  useEffect(() => {
    setChoice(current)
    setCustomText(currentValue)
    setNote('')
  }, [current, currentValue])

  const customNum = parseCustom(customText)
  const canApply = choice === 'custom'
    ? customNum != null && !(current === 'custom' && num(currentValue) === customNum)
    : choice !== current

  async function onApply() {
    setPending(true)
    setRowError(null)
    try {
      const res = await apply(
        m.model_id,
        choice,
        choice === 'custom' ? customNum : null,
        choice === 'custom' && note.trim() !== '' ? note.trim() : null,
      )
      if (!res.ok) setRowError(res.message)
    } catch (e) {
      setRowError(e instanceof Error ? e.message : String(e))
    } finally {
      setPending(false)
    }
  }

  const inForceHighlighted = m.setting_in_force === true
  const days = shortDate(m.first_bet_date) && shortDate(m.last_bet_date)
    ? `${shortDate(m.first_bet_date)} to ${shortDate(m.last_bet_date)}`
    : null

  return (
    <>
      <TableRow className={cn('text-sm align-top', m.in_play && 'opacity-60')}>
        <TableCell className="py-2"><ModelName id={m.model_id} paused={m.paused} className="min-w-[170px] max-w-[240px]" /></TableCell>
        <TableCell className="py-2">
          <div className="flex flex-col items-start gap-1">
            <span className="text-xs font-medium">{m.sport}</span>
            {m.in_play && <InPlayBadge />}
          </div>
        </TableCell>
        <TableCell className="py-1.5">
          {days ? <span className="text-xs tabular-nums whitespace-nowrap">{days}</span> : <NullCell />}
        </TableCell>
        <TableCell className="py-1.5"><span className="text-xs">{m.cut_on}</span></TableCell>
        <TableCell className="py-1.5">
          <span className="text-xs font-mono tabular-nums">{fmtFixed(m.config_cut, 4)}</span>
        </TableCell>
        <TableCell className="py-1.5">
          <span className={cn(
            'text-xs font-mono tabular-nums',
            inForceHighlighted && 'font-bold px-1 py-0.5 rounded bg-brand-soft text-brand'
          )}>
            {fmtFixed(m.cut_in_force, 4)}
          </span>
        </TableCell>
        {BANDS.map(b => (
          <TableCell key={b.key} className="py-1.5"><BandCell row={group.bands[b.key]} /></TableCell>
        ))}
        <TableCell className="py-1.5"><SettingCell m={m} /></TableCell>
        <TableCell className="py-1.5">
          {m.in_play ? (
            <span className="text-xs text-muted-foreground whitespace-nowrap">in-play: not adjustable yet</span>
          ) : (
            <div className="flex flex-col gap-1.5 min-w-[190px]">
              <div className="flex items-center gap-1.5">
                <Select value={choice} onValueChange={v => setChoice(v as Level)} disabled={pending}>
                  <SelectTrigger className="h-8 text-xs w-[170px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all" className="text-xs">{LEVEL_WORDS.all}</SelectItem>
                    {BANDS.filter(b => b.key !== 'all').map(b => (
                      <SelectItem
                        key={b.key}
                        value={b.key}
                        className="text-xs"
                        disabled={group.bands[b.key]?.threshold == null}
                      >
                        {LEVEL_WORDS[b.key]}
                      </SelectItem>
                    ))}
                    <SelectItem value="custom" className="text-xs">{LEVEL_WORDS.custom}</SelectItem>
                  </SelectContent>
                </Select>
                <Button size="sm" className="h-8 text-xs" disabled={!canApply || pending} onClick={() => void onApply()}>
                  Apply
                </Button>
                {pending && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />}
              </div>
              {choice === 'custom' && (
                <div className="flex items-center gap-1.5">
                  <Input
                    type="number"
                    inputMode="decimal"
                    step="0.0001"
                    min={0}
                    max={0.9999}
                    placeholder="0.05"
                    value={customText}
                    disabled={pending}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCustomText(e.target.value)}
                    className="h-8 text-xs w-[80px] font-mono"
                    aria-label="Custom number"
                  />
                  <Input
                    placeholder="Note (optional)"
                    value={note}
                    disabled={pending}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNote(e.target.value)}
                    className="h-8 text-xs w-[150px]"
                    aria-label="Note"
                  />
                </div>
              )}
            </div>
          )}
        </TableCell>
      </TableRow>
      {rowError && (
        <TableRow className="hover:bg-transparent">
          <TableCell colSpan={COL_COUNT} className="py-1.5">
            <PanelError message={rowError} />
          </TableCell>
        </TableRow>
      )}
    </>
  )
}

export default function ModelVolume({ data, loading, error, onChanged }: Props) {
  const [sportFilter, setSportFilter] = useState<string>('All')
  const [hidePaused, setHidePaused] = useState(true)
  const setVolume = useSetModelVolume()
  const { reportPaused } = useModelNames()

  const groups = useMemo<ModelGroup[]>(() => {
    const rows = (data as VolumeBandRow[] | null | undefined) ?? []
    const byModel = new Map<string, ModelGroup>()
    for (const r of rows) {
      let g = byModel.get(r.model_id)
      if (!g) {
        g = { first: r, bands: {} }
        byModel.set(r.model_id, g)
      }
      g.bands[r.band] = r
    }
    const allBpd = (g: ModelGroup) => num(g.bands.all?.bets_per_day) ?? 0
    return Array.from(byModel.values()).sort((a, b) => {
      if (a.first.in_play !== b.first.in_play) return a.first.in_play ? 1 : -1
      const d = allBpd(b) - allBpd(a)
      if (d !== 0) return d
      return a.first.model_id.localeCompare(b.first.model_id)
    })
  }, [data])

  const allSports = useMemo(
    () => Array.from(new Set(groups.map(g => g.first.sport))).sort(),
    [groups],
  )

  // Share paused state so other panels can badge paused models.
  useEffect(() => {
    if (groups.length > 0) reportPaused(groups.map(g => ({ model_id: g.first.model_id, paused: g.first.paused })))
  }, [groups, reportPaused])

  const visible = useMemo(() => groups.filter(g =>
    (sportFilter === 'All' || g.first.sport === sportFilter) &&
    (!hidePaused || !g.first.paused)
  ), [groups, sportFilter, hidePaused])

  async function apply(modelId: string, level: Level, value: number | null, note: string | null): Promise<SetResult> {
    const res = (await setVolume.trigger({ modelId, level, value, note }).result) as SetResult
    if (res.ok) await onChanged()
    return res
  }

  // Keep the table on screen while an apply re-reads the bands
  if (loading && data == null) return <TableSkeleton rows={8} />
  if (error) return <PanelError message={error} />

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <div className="space-y-2">
        <ChipGroup label="Sport">
          <Chip active={sportFilter === 'All'} onClick={() => setSportFilter('All')}>All</Chip>
          {allSports.map(s => (
            <Chip key={s} active={sportFilter === s} onClick={() => setSportFilter(s)}>{s}</Chip>
          ))}
        </ChipGroup>
        <div className="flex items-center gap-2">
          <Switch id="volume-hide-paused" checked={hidePaused} onCheckedChange={setHidePaused} />
          <label htmlFor="volume-hide-paused" className="cursor-pointer text-xs font-medium text-secondary-fg">Hide paused</label>
          <span className="ml-2 text-xs text-muted-foreground">Showing {visible.length} of {groups.length}</span>
        </div>
      </div>

      <div className="table-frame fill">
        <Table>
          <TableHeader>
            <TableRow>
              {['Model', 'Sport', 'Days', 'Cut on', "Model's cut", 'In force', ...BANDS.map(b => b.label), 'Setting', ''].map((h, i) => (
                <TableHead key={i} className="select-none px-3">{h}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {visible.length === 0 ? (
              <TableRow>
                <TableCell colSpan={COL_COUNT} className="py-10 text-center text-sm text-muted-foreground">
                  No models match these filters. Turn off Hide paused or pick another sport.
                </TableCell>
              </TableRow>
            ) : (
              visible.map(g => <VolumeRow key={g.first.model_id} group={g} apply={apply} />)
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
