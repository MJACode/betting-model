const NOTES = [
  'Every bet risks the stake percentage of the bankroll at that moment, in units. A win pays the stake times the payout at the set price (100/110 at -110); a loss forfeits the stake.',
  'Ending bankroll, the bands, the win rate chart and the table are computed exactly from the binomial distribution of wins. Drawdown figures come from the simulated paths (fixed seed; Re-run draws a new set).',
  'Under percentage staking the median grows only if the win rate clears a slightly higher bar than the simple break-even, because a loss costs more log value than a win adds. The mean is pulled up by a few huge runs, so the median is the typical outcome.',
  'Dollars shows every bankroll figure as units times the dollars per unit you set, in the same dollar format as the original simulator. The math runs in units either way, and the percentages and chances do not change.',
  'Assumes independent bets at one fixed, known win rate. Real edges are estimated with error and drift, and correlated bets (same game, same slate) add variance beyond what is shown.',
]

export default function SimNotes() {
  return (
    <ul className="list-disc space-y-2 pl-5 text-[13px] leading-relaxed text-muted-foreground">
      {NOTES.map(n => (
        <li key={n}>{n}</li>
      ))}
    </ul>
  )
}
