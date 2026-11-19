import { Coins, MoveHorizontal, TrendingDown, ArrowDownRight, AlertTriangle, Divide } from 'lucide-react'
import { StatCard } from '../../components/PanelUtils'
import { pct, type Fmt, type SimResult } from './simMath'

export default function SimSummary({ result, B0, N, paths, fmt }: { result: SimResult; B0: number; N: number; paths: number; fmt: Fmt }) {
  const med = result.final[2]!
  const mult = med / B0
  const multText = mult >= 10 ? mult.toFixed(0) : mult.toFixed(2)
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
      <StatCard
        label="Median ending bankroll"
        icon={Coins}
        value={fmt(med)}
        caption={`${multText}× start · mean ${fmt(result.meanFinal)}`}
      />
      <StatCard
        label="Middle 90% of endings"
        icon={MoveHorizontal}
        value={<span className="text-[18px]">{fmt(result.final[0]!)} to {fmt(result.final[4]!)}</span>}
        caption="5th to 95th percentile"
      />
      <StatCard
        label="Chance of finishing below start"
        icon={TrendingDown}
        value={pct(result.pBelow)}
        caption={`after ${N.toLocaleString('en-US')} bets`}
      />
      <StatCard
        label="Median worst drawdown"
        icon={ArrowDownRight}
        value={pct(result.medDD, 0)}
        caption="peak to trough, typical path"
      />
      <StatCard
        label="Chance of a 30%+ drawdown"
        icon={AlertTriangle}
        value={pct(result.pDD30, 0)}
        caption={`of ${paths.toLocaleString('en-US')} simulated paths · typical longest losing run ${result.medStreak} bets`}
      />
      <StatCard
        label="Chance bankroll ever halves"
        icon={Divide}
        value={pct(result.pHalf, 0)}
        caption="dips below half the start at any point"
      />
    </div>
  )
}
