import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { TabShell } from '../../components/tiles/TabShell'
import type { TileMeta, TileRender } from '../../components/tiles/layoutTypes'
import {
  DEFAULT_DISPLAY,
  DEFAULT_PARAMS,
  checkpointRows,
  compute,
  computeSweep,
  displayFactor,
  edgeInfo,
  edgeLine,
  makeFmt,
  newSeed,
  type Display,
  type SimParams,
} from './simMath'
import SimAssumptions from './SimAssumptions'
import SimSummary from './SimSummary'
import FanChart, { type Scale } from './FanChart'
import SweepChart from './SweepChart'
import CheckpointTable from './CheckpointTable'
import SimNotes from './SimNotes'

const SIM_TILES: TileMeta[] = [
  { id: 'assumptions', title: 'Assumptions', description: 'True win rate, stake, price and the number of bets and paths', x: 0, y: 0, w: 12, h: 6, minW: 6, minH: 4, autoHeight: true },
  { id: 'summary', title: 'Summary', description: 'Where the bankroll ends up and how deep it dips on the way', x: 0, y: 6, w: 12, h: 4, minW: 4, minH: 3, autoHeight: true },
  { id: 'fan', title: 'Bankroll over time', description: 'Percentile bands of the bankroll by bets placed, with the median and 8 sample paths', x: 0, y: 10, w: 12, h: 12, minW: 6, minH: 8 },
  { id: 'sweep', title: 'Median ending bankroll by win rate', description: 'The same stake, price and number of bets at every win rate from 48% to 60%', x: 0, y: 22, w: 12, h: 10, minW: 5, minH: 7 },
  { id: 'table', title: 'Bankroll percentiles at checkpoints', description: 'Bankroll at the 5th, 25th, 50th, 75th and 95th percentile after a given number of bets', x: 0, y: 32, w: 12, h: 9, minW: 6, minH: 5 },
  { id: 'notes', title: 'How this works', description: 'What the figures assume and how they are computed', x: 0, y: 41, w: 12, h: 6, minW: 4, minH: 4 },
]

export default function SimTab() {
  const [params, setParams] = useState<SimParams>(DEFAULT_PARAMS)
  const [scale, setScale] = useState<Scale>('log')
  const [display, setDisplay] = useState<Display>(DEFAULT_DISPLAY)
  const fmt = useMemo(() => makeFmt(display), [display])
  const k = displayFactor(display)

  // Slider input is batched to one recompute per animation frame, as in the original.
  const pendingP = useRef<number | null>(null)
  const frame = useRef<number | null>(null)
  const onSlide = useCallback((p: number) => {
    pendingP.current = p
    if (frame.current != null) return
    frame.current = requestAnimationFrame(() => {
      frame.current = null
      const next = pendingP.current
      pendingP.current = null
      if (next != null) setParams(s => (s.p === next ? s : { ...s, p: next }))
    })
  }, [])
  useEffect(() => () => {
    if (frame.current != null) cancelAnimationFrame(frame.current)
  }, [])

  const onChange = useCallback((patch: Partial<SimParams>) => setParams(s => ({ ...s, ...patch })), [])
  const onRerun = useCallback(() => setParams(s => ({ ...s, seed: newSeed() })), [])

  const result = useMemo(() => compute(params), [params])
  const { N, f, odds, B0, p, paths } = params
  // The sweep does not depend on the win rate or the seed.
  const sweep = useMemo(() => computeSweep({ N, f, odds, B0 }), [N, f, odds, B0])
  const checkpoints = useMemo(() => checkpointRows({ p, N, f, odds, B0 }), [p, N, f, odds, B0])
  const edgeText = useMemo(() => edgeLine(p, f, result.L), [p, f, result.L])
  const breakEven = edgeInfo(p, result.L).be

  const renderTile = (id: string): TileRender => {
    switch (id) {
      case 'assumptions':
        return {
          body: (
            <SimAssumptions
              params={params}
              edgeText={edgeText}
              scale={scale}
              onScale={setScale}
              display={display}
              onDisplay={setDisplay}
              onSlide={onSlide}
              onRerun={onRerun}
              onChange={onChange}
            />
          ),
        }
      case 'summary':
        return { body: <SimSummary result={result} B0={B0} N={N} paths={paths} fmt={fmt} /> }
      case 'fan':
        return { body: <FanChart result={result} B0={B0} N={N} scale={scale} fmt={fmt} k={k} /> }
      case 'sweep':
        return { body: <SweepChart sweep={sweep} p={p} selectedMed={result.final[2]!} B0={B0} breakEven={breakEven} fmt={fmt} k={k} /> }
      case 'table':
        return { body: <CheckpointTable rows={checkpoints} fmt={fmt} /> }
      case 'notes':
        return { body: <SimNotes /> }
      default:
        return { body: null }
    }
  }

  return <TabShell tab="sim" metas={SIM_TILES} renderTile={renderTile} />
}
