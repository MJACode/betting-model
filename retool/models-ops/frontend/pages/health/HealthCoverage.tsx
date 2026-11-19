import { useMemo } from 'react'
import { CheckCircle2, TrendingUp, TrendingDown, Radio, HelpCircle, Layers } from 'lucide-react'
import { StatCard, StatsSkeleton, PanelError, Footnote } from '../../components/PanelUtils'
import { int, type SummaryRow } from './healthUtils'

type Props = { rows: SummaryRow[]; loading: boolean; error: string | null }

export default function HealthCoverage({ rows, loading, error }: Props) {
  const t = useMemo(() => {
    let bets = 0, price = 0, lineFor = 0, lineAgainst = 0, inPlay = 0, unmeasured = 0
    for (const r of rows) {
      bets += int(r.bets)
      price += int(r.price_n)
      lineFor += int(r.line_for)
      lineAgainst += int(r.line_against)
      inPlay += int(r.in_play)
      unmeasured += int(r.unmeasured)
    }
    return { bets, price, lineFor, lineAgainst, inPlay, unmeasured }
  }, [rows])

  if (loading) return <StatsSkeleton count={6} />
  if (error) return <PanelError message={error} />

  const share = (n: number) => (t.bets > 0 ? `${((n / t.bets) * 100).toFixed(0)}% of bets` : '—')

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        <StatCard label="Published bets" icon={Layers} value={t.bets.toLocaleString()} caption={`${rows.length} models, graded`} />
        <StatCard label="Closing price on our number" icon={CheckCircle2} value={t.price.toLocaleString()} caption={share(t.price)} />
        <StatCard label="Line moved our way" icon={TrendingUp} value={t.lineFor.toLocaleString()} caption={share(t.lineFor)} />
        <StatCard label="Line moved against us" icon={TrendingDown} value={t.lineAgainst.toLocaleString()} caption={share(t.lineAgainst)} />
        <StatCard label="In-play: not measured, by design" icon={Radio} value={t.inPlay.toLocaleString()} caption={share(t.inPlay)} />
        <StatCard label="No closing price" icon={HelpCircle} value={t.unmeasured.toLocaleString()} caption={share(t.unmeasured)} />
      </div>
      <Footnote>
        The same bets as the published record. In-play bets are not measured for closing-line value, by design: there is no pre-game close to compare against. Every pre-game bet is measured against its book's last price before the start, at the exact number we bet, from a pull made after the bet: the main line, or the book's alternate ladder when the main line had moved. "Line moved" counts are bets where the book no longer offered our number at the start; they count as a beat (moved our way) or a miss (against us) in the beat rate with line moves, and are not in the average. "No closing price" is a bet the book was not pulled again between the bet and the start.
      </Footnote>
    </div>
  )
}
