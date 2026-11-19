import { useEffect, useState, type KeyboardEvent } from 'react'
import { ChevronDown, Shuffle } from 'lucide-react'
import { Slider } from '../../lib/shadcn/slider'
import { Button } from '../../lib/shadcn/button'
import { Input } from '../../lib/shadcn/input'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../../lib/shadcn/collapsible'
import { Chip } from '../../components/PanelUtils'
import { clampInput, clampPerUnit, stakePctText, type Display, type SimParams } from './simMath'
import type { Scale } from './FanChart'

type Field = 'B0' | 'fPct' | 'odds' | 'N' | 'paths'

const FIELDS: ReadonlyArray<{ key: Field; label: string; step: string }> = [
  { key: 'B0', label: 'Starting bankroll', step: '1' },
  { key: 'fPct', label: 'Stake (% of current bankroll)', step: '0.1' },
  { key: 'odds', label: 'Price (American)', step: '1' },
  { key: 'N', label: 'Number of bets', step: '100' },
  { key: 'paths', label: 'Simulated paths', step: '100' },
]

/** Trims float noise from a display amount (100 x 0.07 = 7.000000000000001). */
function numText(v: number): string {
  return String(Number(v.toPrecision(12)))
}

function fieldLabel(key: Field, label: string, display: Display): string {
  if (key !== 'B0') return label
  return display.mode === 'dollars' ? `${label} ($)` : `${label} (units)`
}

function fieldValue(params: SimParams, key: Field, display: Display): string {
  switch (key) {
    case 'B0': return display.mode === 'dollars' ? numText(params.B0 * display.perUnit) : String(params.B0)
    case 'fPct': return stakePctText(params.f)
    case 'odds': return String(params.odds)
    case 'N': return String(params.N)
    case 'paths': return String(params.paths)
  }
}

/** A number input that applies its value (clamped) on blur or Enter, then shows what was applied. */
function AdvInput({ label, step, value, onCommit, inline = false }: { label: string; step: string; value: string; onCommit: (raw: string) => void; inline?: boolean }) {
  const [draft, setDraft] = useState(value)
  useEffect(() => setDraft(value), [value])
  const commit = () => {
    onCommit(draft)
    setDraft(value)
  }
  return (
    <label className={inline ? 'flex items-center gap-1.5' : 'flex min-w-0 flex-col gap-1'}>
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <Input
        type="number"
        inputMode="decimal"
        step={step}
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => {
          if (e.key === 'Enter') commit()
        }}
        className={inline ? 'h-8 w-24 tabular-nums' : 'h-9 tabular-nums'}
      />
    </label>
  )
}

export default function SimAssumptions({
  params,
  edgeText,
  scale,
  onScale,
  display,
  onDisplay,
  onSlide,
  onRerun,
  onChange,
}: {
  params: SimParams
  edgeText: string
  scale: Scale
  onScale: (s: Scale) => void
  display: Display
  onDisplay: (d: Display) => void
  /** Raw slider value (0..1); the parent batches it to one recompute per frame. */
  onSlide: (p: number) => void
  onRerun: () => void
  onChange: (patch: Partial<SimParams>) => void
}) {
  // The readout and thumb follow the pointer at once; the charts follow on the next frame.
  const [slider, setSlider] = useState(params.p * 100)
  const [open, setOpen] = useState(false)

  const commit = (key: Field, raw: string) => {
    const v = raw.trim() === '' ? NaN : Number(raw)
    switch (key) {
      case 'B0': {
        // In Dollars the field is in dollars; the bankroll stays in units.
        const c = clampInput.B0(display.mode === 'dollars' ? v / display.perUnit : v)
        if (c != null) onChange({ B0: c })
        break
      }
      case 'fPct': { const c = clampInput.fPct(v); if (c != null) onChange({ f: c / 100 }); break }
      case 'odds': { const c = clampInput.odds(v); if (c != null) onChange({ odds: c }); break }
      case 'N': { const c = clampInput.N(v); if (c != null) onChange({ N: c }); break }
      case 'paths': { const c = clampInput.paths(v); if (c != null) onChange({ paths: c }); break }
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-x-8 gap-y-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-3">
          <div className="flex items-end justify-between gap-3">
            <span className="text-sm font-medium text-foreground">True win rate</span>
            <span className="sb-figure text-[32px] font-semibold leading-none tracking-tight text-foreground tabular-nums">
              {slider.toFixed(1)}%
            </span>
          </div>
          <Slider
            min={48}
            max={60}
            step={0.1}
            value={[slider]}
            onValueChange={v => {
              const next = v[0]
              if (next == null) return
              setSlider(next)
              onSlide(next / 100)
            }}
            aria-label="True win rate"
          />
          <div className="flex justify-between text-[11px] text-muted-foreground tabular-nums">
            <span>48%</span>
            <span>60%</span>
          </div>
        </div>
        <div className="flex flex-col justify-between gap-3">
          <p className="text-sm leading-relaxed text-secondary-fg">{edgeText}</p>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" size="sm" variant="outline" onClick={onRerun} className="h-8 gap-1.5 text-xs">
              <Shuffle className="h-3.5 w-3.5" aria-hidden />
              Re-run simulation
            </Button>
            <div className="flex items-center gap-1" role="group" aria-label="Y axis scale">
              <Chip active={scale === 'log'} onClick={() => onScale('log')} title="Log scale">Log scale</Chip>
              <Chip active={scale === 'linear'} onClick={() => onScale('linear')} title="Linear scale">Linear</Chip>
            </div>
            <div className="flex items-center gap-1" role="group" aria-label="Show amounts in">
              <Chip active={display.mode === 'units'} onClick={() => onDisplay({ ...display, mode: 'units' })} title="Show amounts in units">Units</Chip>
              <Chip active={display.mode === 'dollars'} onClick={() => onDisplay({ ...display, mode: 'dollars' })} title="Show amounts in dollars">Dollars</Chip>
            </div>
            {display.mode === 'dollars' && (
              <AdvInput
                inline
                label="$ per unit"
                step="1"
                value={numText(display.perUnit)}
                onCommit={raw => {
                  const c = clampPerUnit(raw.trim() === '' ? NaN : Number(raw))
                  if (c != null) onDisplay({ ...display, perUnit: c })
                }}
              />
            )}
            <span className="ml-auto text-xs text-muted-foreground tabular-nums">
              {params.paths.toLocaleString('en-US')} paths · seed {params.seed}
            </span>
          </div>
        </div>
      </div>

      <Collapsible open={open} onOpenChange={setOpen}>
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden />
            Change assumptions
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
            {FIELDS.map(f => (
              <AdvInput
                key={f.key}
                label={fieldLabel(f.key, f.label, display)}
                step={f.step}
                value={fieldValue(params, f.key, display)}
                onCommit={raw => commit(f.key, raw)}
              />
            ))}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Applied when you leave a field or press Enter. Stake 0.1% to 25%; price at least ±100; 10 to 20,000 bets; 100 to 10,000 paths.
          </p>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}
