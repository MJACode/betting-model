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
        <StatCard label="In-play (no pre-game close)" icon={Radio} value={t.inPlay.toLocaleString()} caption={share(t.inPlay)} />
        <StatCard label="Not measured" icon={HelpCircle} value={t.unmeasured.toLocaleString()} caption={share(t.unmeasured)} />
      </div>
      <Footnote>
        The same bets as the published record. Average CLV uses only bets whose book closed on the number we bet: the close is that book’s last pre-game price, and CLV is how much better our price was. When the book’s main line left our number before the start, there is no closing price for our exact bet, so the bet counts as a beat (line moved our way) or a miss (moved against us) in the beat rate “with line moves”, and is not in the average. In-play bets have no pre-game close. “Not measured” is mostly NCAAB first-half spreads, whose last line pull before tip is the one the bet was made on.
      </Footnote>
    </div>
  )
}
