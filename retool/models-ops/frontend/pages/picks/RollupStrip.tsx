import { useMemo } from 'react'
import { AlertTriangle, Trophy, Coins, Percent, Ban, Target, Gauge } from 'lucide-react'
import { StatCard, signedClass } from '../../components/PanelUtils'
import { cn } from '../../lib/shadcn/utils'
import { computeRollup, type PickRow } from './picksUtils'

type Props = { rows: PickRow[]; total: number }

function signedU(n: number): string {
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}u`
}

export default function RollupStrip({ rows, total }: Props) {
  const s = useMemo(() => computeRollup(rows), [rows])

  const unitsDisplay = s.totalUnits != null ? signedU(s.totalUnits) : '—'
  const roiDisplay = s.roi != null ? (s.roi >= 0 ? '+' : '') + s.roi.toFixed(2) + '%' : '—'
  const beatRatePrice = s.beatRatePrice != null ? (s.beatRatePrice * 100).toFixed(1) + '%' : '—'
  const beatRateWithLine = s.beatRateWithLine != null ? (s.beatRateWithLine * 100).toFixed(1) + '%' : '—'
  const coveragePct = s.total > 0 ? ((s.measured / s.total) * 100).toFixed(0) + '%' : '—'

  const partial = s.partialUnits
    ? (
      <span className="mt-0.5 flex items-center gap-1 text-warn">
        <AlertTriangle className="h-3 w-3" aria-hidden />
        Partial price coverage
      </span>
    )
    : null

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
      <StatCard
        label="Record"
        icon={Trophy}
        value={`${s.wins}-${s.losses}-${s.pushes}`}
        caption={
          <span className="flex flex-col gap-0.5">
            <span>{s.settled.toLocaleString()} settled of {s.total.toLocaleString()} picks</span>
            {(s.noAction > 0 || s.unsettled > 0) && (
              <span>
                {[
                  s.noAction > 0 ? `${s.noAction} void` : null,
                  s.unsettled > 0 ? `${s.unsettled} unsettled` : null,
                ].filter(Boolean).join(' · ')} not counted
              </span>
            )}
          </span>
        }
      />

      <StatCard
        label="Units"
        icon={Coins}
        value={<span className={signedClass(s.totalUnits)}>{unitsDisplay}</span>}
        caption={
          <span className="flex flex-col gap-0.5">
            {(s.priced > 0 || s.unpriced > 0) && (
              <span>
                {s.priced.toLocaleString()} of {total.toLocaleString()} priced
                {s.unpriced > 0 && ` · ${s.unpriced} unpriced`}
              </span>
            )}
            <span className="flex flex-wrap gap-x-2">
              {s.laneUnits.pregame != null && (
                <span>Pre-game <span className={cn('font-medium', signedClass(s.laneUnits.pregame))}>{signedU(s.laneUnits.pregame)}</span></span>
              )}
              {s.laneUnits.live != null && (
                <span>In-play <span className={cn('font-medium', signedClass(s.laneUnits.live))}>{signedU(s.laneUnits.live)}</span></span>
              )}
            </span>
            {s.laneUnits.repairCount > 0 && <span>Re-priced props not counted ({s.laneUnits.repairCount})</span>}
            {partial}
          </span>
        }
      />

      <StatCard
        label="ROI"
        icon={Percent}
        value={<span className={signedClass(s.roi)}>{roiDisplay}</span>}
        caption={
          <span className="flex flex-col gap-0.5">
            {s.pricedNoPush > 0 && <span>over {s.pricedNoPush.toLocaleString()} settled, non-push</span>}
            {partial}
          </span>
        }
      />

      <StatCard
        label="Not in P&L"
        icon={Ban}
        value={<span className="text-muted-foreground">{(s.noAction + s.unsettled).toLocaleString()}</span>}
        caption={`${s.noAction} void · ${s.unsettled} unsettled; neither counts as a stake`}
        title="Void means the bet never stood. Unsettled means not yet graded. Both are left out of the record, units and the ROI denominator."
      />

      <StatCard
        label="CLV beat rate"
        icon={Target}
        value={beatRatePrice}
        caption={
          <span className="flex flex-col gap-0.5">
            <span>{`${s.beat} beat · ${s.worse} worse · ${s.flat} same price, of ${s.beat + s.worse + s.flat} closing prices`}</span>
            <span>{`With line moves ${beatRateWithLine}: ${s.lineFor} moved our way · ${s.lineAgainst} against`}</span>
          </span>
        }
        title="Beat rate = beat / (beat + worse) over bets whose book closed on our number; a close at our exact price is left out. Line moves (the book's line left our number before the start) are counted only in the 'with line moves' rate: our way is a beat, against is a miss."
      />

      <StatCard
        label="CLV coverage"
        icon={Gauge}
        value={`${s.measured.toLocaleString()} / ${s.total.toLocaleString()}`}
        caption={`${coveragePct} measured · ${s.notMeasured.toLocaleString()} not measured`}
        title="Measured means a closing price on our number or a line move. In-play bets have no pre-game close, so they are never measured; they show as not measured, not as losses. CLV is independent of result."
      />
    </div>
  )
}
