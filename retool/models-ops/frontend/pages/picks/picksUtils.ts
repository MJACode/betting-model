// Shared types and helpers for the Picks & CLV tab

export type ClvOutcome = 'BEAT' | 'FLAT' | 'WORSE' | 'LINE_FOR' | 'LINE_AGAINST' | 'NOT_MEASURED' | 'UNRESOLVED'
export type Lane = 'pregame' | 'live' | 'repair'

export type PickRow = {
  pick_id: string
  sport: string
  model_id: string
  game_date: string
  game_id: string
  pick_label: string
  pick_side: string | null
  scored_line: string | null
  odds_at_pick: string | null
  odds_at_close: string | null
  closing_line: string | null
  clv_pct: string | null
  line_clv_pts: string | null
  clv_beat_close: boolean | null
  clv_captured_at: string | null
  is_live: boolean
  result: string | null
  dk_odds: string | null
  edge: string | null
  model_probability: string | null
  created_at: string
  game_time: string | null
  profit_units: string | null
  lane: Lane
  clv_outcome: ClvOutcome
}

// --- Aggregation helpers ---

export type LaneUnits = {
  pregame: number | null
  live: number | null
  repairCount: number  // total repair rows (excluded from P&L)
}

export type RollupStats = {
  total: number
  wins: number
  losses: number
  pushes: number
  settled: number
  noAction: number    // voided bets — excluded from record, units, ROI
  unsettled: number   // null result — excluded from record, units, ROI
  unpriced: number    // settled but dk_odds IS NULL — no units by design
  priced: number      // settled (WIN/LOSS/PUSH) + profit_units non-null
  pricedNoPush: number
  totalUnits: number | null
  roi: number | null
  partialUnits: boolean
  laneUnits: LaneUnits
  // CLV — from the published record's own classification (v_model_health_bets)
  notMeasured: number
  measured: number
  beat: number
  flat: number
  worse: number
  lineFor: number
  lineAgainst: number
  beatRatePrice: number | null     // beat / (beat + worse), the published headline (a same-price close is left out)
  beatRateWithLine: number | null  // (beat + lineFor) / (beat + worse + lineFor + lineAgainst)
}

export function computeRollup(rows: PickRow[]): RollupStats {
  let wins = 0, losses = 0, pushes = 0, noAction = 0, unsettled = 0, unpriced = 0
  let priced = 0, pricedNoPush = 0
  let totalUnits = 0
  let hasAnyUnits = false
  let notMeasured = 0, measured = 0, beat = 0, flat = 0, worse = 0, lineFor = 0, lineAgainst = 0

  // Per-lane unit tracking
  let pregameUnits = 0, hasPregame = false
  let liveUnits = 0, hasLive = false
  let repairCount = 0

  for (const r of rows) {
    const res = r.result?.toUpperCase()

    // Record: only WIN/LOSS/PUSH. NO_ACTION (voided) and null (unsettled) excluded.
    if (res === 'WIN') wins++
    else if (res === 'LOSS') losses++
    else if (res === 'PUSH') pushes++
    else if (res === 'NO_ACTION') noAction++
    else if (res == null) unsettled++
    // (unpriced counted below, after we know it's settled)

    // Track unpriced: settled but no DK odds
    if ((res === 'WIN' || res === 'LOSS' || res === 'PUSH') && r.dk_odds == null) unpriced++

    // Units/ROI: only settled (WIN/LOSS/PUSH) rows with profit_units non-null.
    // Repair rows have profit_units = NULL so they fall out automatically.
    if (res === 'WIN' || res === 'LOSS' || res === 'PUSH') {
      const u = r.profit_units != null ? parseFloat(r.profit_units) : null
      if (u != null) {
        hasAnyUnits = true
        totalUnits += u
        priced++
        if (res !== 'PUSH') pricedNoPush++

        // Per-lane breakdown
        if (r.lane === 'pregame') { hasPregame = true; pregameUnits += u }
        else if (r.lane === 'live') { hasLive = true; liveUnits += u }
      }
    }

    if (r.lane === 'repair') repairCount++

    // CLV: independent of result. Line moves are measured but are never a
    // price beat or a price worse.
    const co = r.clv_outcome
    if (co === 'NOT_MEASURED' || co === 'UNRESOLVED') notMeasured++
    else {
      measured++
      if (co === 'BEAT') beat++
      else if (co === 'FLAT') flat++
      else if (co === 'WORSE') worse++
      else if (co === 'LINE_FOR') lineFor++
      else if (co === 'LINE_AGAINST') lineAgainst++
    }
  }

  const settled = wins + losses + pushes
  const partialUnits = priced > 0 && priced < rows.length

  return {
    total: rows.length,
    wins,
    losses,
    pushes,
    settled,
    noAction,
    unsettled,
    unpriced,
    priced,
    pricedNoPush,
    totalUnits: hasAnyUnits ? totalUnits : null,
    roi: hasAnyUnits && pricedNoPush > 0 ? (totalUnits / pricedNoPush) * 100 : null,
    partialUnits,
    laneUnits: {
      pregame: hasPregame ? pregameUnits : null,
      live: hasLive ? liveUnits : null,
      repairCount,
    },
    notMeasured,
    measured,
    beat,
    flat,
    worse,
    lineFor,
    lineAgainst,
    beatRatePrice: beat + worse > 0 ? beat / (beat + worse) : null,
    beatRateWithLine: beat + worse + lineFor + lineAgainst > 0
      ? (beat + lineFor) / (beat + worse + lineFor + lineAgainst)
      : null,
  }
}

// --- Filter state ---

export type FilterState = {
  sports: string[]
  models: string[]
  dateFrom: string
  dateTo: string
  clvOutcomes: ClvOutcome[]
  results: string[]
  lanes: Lane[]  // empty = all lanes selected
}

export function defaultFilter(): FilterState {
  return {
    sports: [],
    models: [],
    dateFrom: '',
    dateTo: '',
    clvOutcomes: [],
    results: [],
    lanes: ['pregame', 'live'],  // Repair OFF by default
  }
}

export function applyFilter(rows: PickRow[], f: FilterState): PickRow[] {
  return rows.filter(r => {
    if (f.sports.length > 0 && !f.sports.includes(r.sport)) return false
    if (f.models.length > 0 && !f.models.includes(r.model_id)) return false
    if (f.dateFrom && r.game_date < f.dateFrom) return false
    if (f.dateTo && r.game_date > f.dateTo) return false
    if (f.clvOutcomes.length > 0 && !f.clvOutcomes.includes(r.clv_outcome)) return false
    if (f.results.length > 0) {
      let res: string
      if (r.result == null) {
        res = 'UNSETTLED'
      } else if (r.dk_odds == null && r.result.toUpperCase() !== 'NO_ACTION') {
        res = 'UNPRICED'
      } else {
        res = r.result.toUpperCase()
      }
      if (!f.results.includes(res)) return false
    }
    // Lane filter: if lanes array is non-empty, only include rows whose lane is in the set.
    // Empty lanes array means no lane filter (show all).
    if (f.lanes.length > 0 && !f.lanes.includes(r.lane)) return false
    return true
  })
}

// --- Formatting helpers ---

export function fmtOdds(v: string | null): string {
  if (v == null) return '—'
  const n = parseFloat(v)
  if (isNaN(n)) return '—'
  return n > 0 ? `+${Math.round(n)}` : `${Math.round(n)}`
}

export function fmtLine(v: string | null): string {
  if (v == null) return '—'
  const n = parseFloat(v)
  if (isNaN(n)) return '—'
  return n > 0 ? `+${n}` : `${n}`
}

export function fmtOddsMove(pick: string | null, close: string | null): string {
  if (pick == null) return '—'
  const p = fmtOdds(pick)
  if (close == null) return p
  const c = fmtOdds(close)
  if (p === c) return p
  return `${p} → ${c}`
}

export function fmtLineMove(pick: string | null, close: string | null): string {
  if (pick == null) return '—'
  const p = fmtLine(pick)
  if (close == null) return p
  const c = fmtLine(close)
  if (p === c) return p
  return `${p} → ${c}`
}

export function fmtClvPct(v: string | null): string {
  if (v == null) return '—'
  const n = parseFloat(v)
  if (isNaN(n)) return '—'
  return (n >= 0 ? '+' : '') + n.toFixed(2) + '%'
}

export function fmtClvPts(v: string | null): string {
  if (v == null) return '—'
  const n = parseFloat(v)
  if (isNaN(n)) return '—'
  return (n >= 0 ? '+' : '') + n.toFixed(2)
}
