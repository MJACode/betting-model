import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../lib/shadcn/table'
import { fmtU, pct, type CheckpointRow } from './simMath'

const HEADS = ['5th', '25th', 'Median', '75th', '95th']

export default function CheckpointTable({ rows }: { rows: CheckpointRow[] }) {
  return (
    <Table className="text-[13px]">
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="h-9 px-3">Bets</TableHead>
          {HEADS.map(h => (
            <TableHead key={h} className="h-9 px-3 text-right">{h}</TableHead>
          ))}
          <TableHead className="h-9 px-3 text-right">Below start</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map(r => (
          <TableRow key={r.bets}>
            <TableCell className="px-3 py-2 tabular-nums">{r.bets.toLocaleString('en-US')}</TableCell>
            {r.values.map((v, i) => (
              <TableCell key={i} className={`px-3 py-2 text-right tabular-nums ${i === 2 ? 'font-semibold' : ''}`}>
                {fmtU(v)}
              </TableCell>
            ))}
            <TableCell className="px-3 py-2 text-right tabular-nums">{pct(r.below)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
