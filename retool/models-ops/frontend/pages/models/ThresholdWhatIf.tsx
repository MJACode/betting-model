import { useState, useEffect, useMemo, useRef } from 'react'
import { RotateCcw, TrendingUp, TrendingDown, Minus, AlertTriangle } from 'lucide-react'
import { Button } from '../../lib/shadcn/button'
import { Input } from '../../lib/shadcn/input'
import { Checkbox } from '../../lib/shadcn/checkbox'
import { Skeleton } from '../../lib/shadcn/skeleton'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../lib/shadcn/select'
import { Badge, ModelStateBadge, PausedBadge } from '../../components/StatusBadge'
import { EmptyState, Footnote, fmtUnits, signedClass } from '../../components/PanelUtils'
import { useModelNames } from '../../components/models/modelNames'
import { cn } from '../../lib/shadcn/utils'
import { useGetThresholdPerformance } from '../../hooks/backend/ops'

type ModelRow = {
  model_id: string
  paused: boolean
  prob_only: boolean
  min_prob: string | null
  min_edge: string | null
  min_odds: string | null
  state: 'LIVE' | 'PAUSED' | 'NO ARTIFACT'
}

type PerfRow = {
  model_id: string
  sport: string
  settled: string
}

type ThresholdPerf = {
  modelId: string
  candidatePicks: number
  settled: number
  wins: number
  losses: number
  pushes: number
  priced: number
  units: number
  riskedCount: number
  roiPct: number | null
  partial: boolean
}

type Props = {
  rosterData: unknown
  perfData: unknown
  loading: boolean
}

const DEBOUNCE_MS = 300

function ResultCard({
  title, perf, loading, tone,
}: {
  title: string
  perf: ThresholdPerf | undefined
  loading: boolean
  tone: 'neutral' | 'highlight'
}) {
  return (
    <div className={cn(
      'min-w-[200px] flex-1 space-y-2 rounded-[10px] border p-4',
      tone === 'highlight' ? 'border-brand bg-brand-soft' : 'bg-card',
    )}>
      <h4 className="text-xs font-medium text-muted-foreground">{title}</h4>
      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-7 w-24" />
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-16" />
        </div>
      ) : !perf || perf.settled === 0 ? (
        <div className="flex h-16 items-center text-xs text-muted-foreground">No settled picks clear these thresholds.</div>
      ) : (
        <div className="space-y-1">
          <div className="flex items-baseline gap-2">
            <span className={cn('text-2xl font-semibold tracking-tight', signedClass(perf.roiPct))}>
              {perf.roiPct != null ? `${perf.roiPct >= 0 ? '+' : ''}${perf.roiPct.toFixed(2)}%` : '—'}
            </span>
            <span className="text-xs text-muted-foreground">ROI</span>
          </div>
          {perf.partial && (
            <p className="flex items-center gap-1 text-[11px] text-warn">
              <AlertTriangle className="h-3 w-3" aria-hidden />
              {perf.priced} of {perf.settled} priced
            </p>
          )}
          <p className="text-sm">
            {perf.wins}-{perf.losses}-{perf.pushes}
            <span className="ml-1 text-xs text-muted-foreground">({perf.settled} settled)</span>
          </p>
          <p className={cn('text-sm font-semibold', signedClass(perf.units))}>
            {fmtUnits(String(perf.units))}
          </p>
        </div>
      )}
    </div>
  )
}

function DeltaBadge({ current, whatIf }: { current: ThresholdPerf | undefined; whatIf: ThresholdPerf | undefined }) {
  if (!current || !whatIf || current.settled === 0 || whatIf.settled === 0) return null
  if (current.roiPct == null || whatIf.roiPct == null) return null
  const delta = whatIf.roiPct - current.roiPct
  const Icon = delta > 0.01 ? TrendingUp : delta < -0.01 ? TrendingDown : Minus
  const color = delta > 0.01 ? 'text-good' : delta < -0.01 ? 'text-crit' : 'text-muted-foreground'
  const pickDelta = whatIf.candidatePicks - current.candidatePicks
  return (
    <div className={cn('flex items-center gap-1 text-xs font-semibold', color)}>
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {delta >= 0 ? '+' : ''}{delta.toFixed(2)}pp ROI · {pickDelta >= 0 ? '+' : ''}{pickDelta} picks
    </div>
  )
}

function Slider({ label, value, display, min, max, step, onChange }: {
  label: string; value: number; display: string; min: number; max: number; step: number; onChange: (v: number) => void
}) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <label className="text-xs text-muted-foreground">{label}</label>
        <span className="font-mono text-xs">{display}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={e => onChange(parseFloat(e.target.value))}
        className="h-1.5 w-full cursor-pointer accent-primary"
        aria-label={label}
      />
    </div>
  )
}

export default function ThresholdWhatIf({ rosterData, perfData, loading }: Props) {
  const names = useModelNames()
  const roster = useMemo<ModelRow[]>(() => (rosterData as ModelRow[] | undefined) ?? [], [rosterData])
  const perfModels = useMemo<Set<string>>(() => {
    const rows = (perfData as PerfRow[] | undefined) ?? []
    return new Set(rows.map(r => r.model_id))
  }, [perfData])

  // Only models that have settled performance data are worth analyzing
  const eligibleModels = useMemo(
    () => roster
      .filter(m => perfModels.has(m.model_id) && m.min_prob != null)
      .sort((a, b) => names.modelLabel(a.model_id).name.localeCompare(names.modelLabel(b.model_id).name) || a.model_id.localeCompare(b.model_id)),
    [roster, perfModels, names],
  )

  const [selectedModelId, setSelectedModelId] = useState<string>('')

  useEffect(() => {
    if (!selectedModelId && eligibleModels.length > 0) {
      setSelectedModelId(eligibleModels[0]?.model_id ?? '')
    }
  }, [eligibleModels, selectedModelId])

  const selectedModel = useMemo(
    () => eligibleModels.find(m => m.model_id === selectedModelId),
    [eligibleModels, selectedModelId],
  )

  const currentThresholds = useMemo(() => ({
    minProb: selectedModel?.min_prob != null ? parseFloat(selectedModel.min_prob) : 0,
    minEdge: selectedModel?.min_edge != null ? parseFloat(selectedModel.min_edge) : 0,
    minOdds: selectedModel?.min_odds != null ? parseFloat(selectedModel.min_odds) : null,
  }), [selectedModel])

  const [whatIfProb, setWhatIfProb] = useState(0)
  const [whatIfEdge, setWhatIfEdge] = useState(0)
  const [whatIfOddsEnabled, setWhatIfOddsEnabled] = useState(false)
  const [whatIfOdds, setWhatIfOdds] = useState(0)

  // Reset what-if inputs whenever the selected model changes
  useEffect(() => {
    setWhatIfProb(currentThresholds.minProb)
    setWhatIfEdge(currentThresholds.minEdge)
    setWhatIfOddsEnabled(currentThresholds.minOdds != null)
    setWhatIfOdds(currentThresholds.minOdds ?? -140)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedModelId])

  const currentPerfHook = useGetThresholdPerformance({ cachePolicy: 'stale-while-revalidate' })
  const whatIfPerfHook = useGetThresholdPerformance({ cachePolicy: 'stale-while-revalidate' })
  const [currentPerf, setCurrentPerf] = useState<ThresholdPerf | undefined>(undefined)
  const [whatIfPerf, setWhatIfPerf] = useState<ThresholdPerf | undefined>(undefined)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  // Fetch "current thresholds" performance whenever the model changes
  useEffect(() => {
    if (!selectedModel) return
    let cancelled = false
    currentPerfHook.trigger({
      modelId: selectedModel.model_id,
      minProb: currentThresholds.minProb,
      minEdge: currentThresholds.minEdge,
      minOdds: currentThresholds.minOdds,
    }).result.then(res => {
      if (!cancelled) setCurrentPerf(res as ThresholdPerf)
    }).catch(() => { /* the hook keeps the error */ })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedModelId])

  // Fetch "what-if" performance whenever inputs change, debounced
  useEffect(() => {
    if (!selectedModel) return
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      whatIfPerfHook.trigger({
        modelId: selectedModel.model_id,
        minProb: whatIfProb,
        minEdge: whatIfEdge,
        minOdds: whatIfOddsEnabled ? whatIfOdds : null,
      }).result.then(res => {
        setWhatIfPerf(res as ThresholdPerf)
      }).catch(() => { /* the hook keeps the error */ })
    }, DEBOUNCE_MS)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedModelId, whatIfProb, whatIfEdge, whatIfOddsEnabled, whatIfOdds])

  const resetToCurrent = () => {
    setWhatIfProb(currentThresholds.minProb)
    setWhatIfEdge(currentThresholds.minEdge)
    setWhatIfOddsEnabled(currentThresholds.minOdds != null)
    setWhatIfOdds(currentThresholds.minOdds ?? -140)
  }

  const isDirty =
    Math.abs(whatIfProb - currentThresholds.minProb) > 1e-9 ||
    Math.abs(whatIfEdge - currentThresholds.minEdge) > 1e-9 ||
    whatIfOddsEnabled !== (currentThresholds.minOdds != null) ||
    (whatIfOddsEnabled && currentThresholds.minOdds != null && Math.abs(whatIfOdds - currentThresholds.minOdds) > 1e-9)

  if (loading && eligibleModels.length === 0) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-72" />
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Skeleton className="h-56 rounded-[10px]" />
          <Skeleton className="h-56 rounded-[10px]" />
        </div>
      </div>
    )
  }

  if (eligibleModels.length === 0) {
    return (
      <EmptyState title="Nothing to analyse yet">
        A model shows up here once it has both live thresholds and at least one settled bet.
      </EmptyState>
    )
  }

  const selectedLabel = selectedModel ? names.modelLabel(selectedModel.model_id) : null

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs font-medium text-muted-foreground">Model</span>
        <Select value={selectedModelId} onValueChange={setSelectedModelId}>
          <SelectTrigger className="h-auto min-h-9 w-80 py-1.5 text-left" aria-label="Model">
            <SelectValue>
              {selectedModel && selectedLabel && (
                <span className="flex min-w-0 flex-col">
                  <span className="truncate text-sm font-medium">{selectedLabel.name}</span>
                  <span className="truncate font-mono text-[11px] text-muted-foreground">{selectedModel.model_id}</span>
                </span>
              )}
            </SelectValue>
          </SelectTrigger>
          <SelectContent className="max-h-80">
            {eligibleModels.map(m => (
              <SelectItem key={m.model_id} value={m.model_id} className="py-1.5">
                <span className="flex flex-col">
                  <span className="flex items-center gap-1.5 text-sm">
                    {names.modelLabel(m.model_id).name}
                    {m.paused && <PausedBadge />}
                  </span>
                  <span className="font-mono text-[11px] text-muted-foreground">{m.model_id}</span>
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {selectedModel && <ModelStateBadge state={selectedModel.state} />}
        {selectedModel?.prob_only && (
          <Badge tone="outline">Probability only: the edge cut has little effect</Badge>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="space-y-3 rounded-[10px] border bg-raised p-4">
          <h3 className="text-sm font-semibold">Current live thresholds</h3>
          <div className="grid grid-cols-3 gap-3 text-sm">
            <div>
              <div className="text-xs text-muted-foreground">Min prob</div>
              <div className="font-mono font-semibold">{(currentThresholds.minProb * 100).toFixed(1)}%</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Min edge</div>
              <div className="font-mono font-semibold">{(currentThresholds.minEdge * 100).toFixed(1)}%</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Min odds</div>
              <div className="font-mono font-semibold">{currentThresholds.minOdds ?? '—'}</div>
            </div>
          </div>
          <ResultCard title="Performance at current thresholds" perf={currentPerf} loading={currentPerfHook.loading} tone="neutral" />
        </div>

        <div className="space-y-3 rounded-[10px] border bg-raised p-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">What-if thresholds</h3>
            <Button size="sm" variant="ghost" onClick={resetToCurrent} disabled={!isDirty} className="h-7 gap-1 px-2 text-xs">
              <RotateCcw className="h-3 w-3" />
              Reset
            </Button>
          </div>

          <div className="space-y-3">
            <Slider label="Min prob" value={whatIfProb} display={`${(whatIfProb * 100).toFixed(1)}%`} min={0} max={1} step={0.01} onChange={setWhatIfProb} />
            <Slider label="Min edge" value={whatIfEdge} display={`${(whatIfEdge * 100).toFixed(1)}%`} min={-0.1} max={0.4} step={0.01} onChange={setWhatIfEdge} />
            <div>
              <div className="mb-1 flex items-center gap-2">
                <Checkbox
                  id="odds-gate"
                  checked={whatIfOddsEnabled}
                  onCheckedChange={(checked: boolean) => setWhatIfOddsEnabled(checked === true)}
                />
                <label htmlFor="odds-gate" className="text-xs text-muted-foreground">Min odds cut</label>
                {whatIfOddsEnabled && (
                  <Input
                    type="number"
                    value={whatIfOdds}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setWhatIfOdds(parseFloat(e.target.value) || 0)}
                    className="ml-auto h-7 w-20 font-mono text-xs"
                    aria-label="Min odds"
                  />
                )}
              </div>
              {whatIfOddsEnabled && (
                <input
                  type="range"
                  min={-500}
                  max={500}
                  step={5}
                  value={whatIfOdds}
                  onChange={e => setWhatIfOdds(parseFloat(e.target.value))}
                  className="h-1.5 w-full cursor-pointer accent-primary"
                  aria-label="Min odds slider"
                />
              )}
            </div>
          </div>

          <ResultCard title="What-if result" perf={whatIfPerf} loading={whatIfPerfHook.loading} tone="highlight" />
          <DeltaBadge current={currentPerf} whatIf={whatIfPerf} />
        </div>
      </div>

      <Footnote>
        Recomputed live from each scored pick's own probability, edge and DraftKings price, not from whether it was flagged as a bet at the time, so this shows what today's thresholds (or yours) would have produced.
      </Footnote>
    </div>
  )
}
