type CoverageRow = {
  sport: string
  game_date: string
  scheduled: number
  covered: number
  missing: number
}

type BoardRow = {
  game_id: string
  sport: string
  game_date: string
  home_team: string
  venue: string
  temp_f: number
  wind_mph: number
  wind_out: number
  precip_mm: number
  is_dome: number
  fetched_at: string
  lead_days: number
}

type FreshnessRow = {
  newest: string | null
  oldest: string | null
  upcoming_rows: number
}

type WeatherBoardResult = {
  coverage: CoverageRow[]
  board: BoardRow[]
  freshness: FreshnessRow | null
}

export default async function (_req: { params: Record<string, never>; user: User }): Promise<WeatherBoardResult> {
  const [coverageRes, boardRes, freshnessRes] = await Promise.all([
    supabase.query<CoverageRow>(`
      WITH expected AS (
        SELECT g.game_id, g.sport, g.game_date
        FROM games g
        WHERE (g.sport = 'MLB'   AND g.game_date =  CURRENT_DATE::text)
           OR (g.sport = 'NCAAF' AND g.game_date >= CURRENT_DATE::text
                               AND g.game_date <= (CURRENT_DATE + 7)::text)
      )
      SELECT e.sport, e.game_date,
             count(*)::int              AS scheduled,
             count(w.game_id)::int      AS covered,
             (count(*) - count(w.game_id))::int AS missing
      FROM expected e
      LEFT JOIN game_weather w ON w.game_id = e.game_id
      GROUP BY 1, 2 ORDER BY 2, 1
    `),
    supabase.query<BoardRow>(`
      SELECT w.game_id, g.sport, w.game_date, w.home_team, w.venue,
             w.temp_f::float8 AS temp_f, w.wind_mph::float8 AS wind_mph,
             w.wind_out_component::float8 AS wind_out, w.precip_mm::float8 AS precip_mm,
             w.is_dome_game::int AS is_dome, w.fetched_at,
             (w.game_date::date - CURRENT_DATE)::int AS lead_days
      FROM game_weather w
      JOIN games g ON g.game_id = w.game_id
      WHERE w.game_date >= CURRENT_DATE::text
      ORDER BY w.is_dome_game, w.wind_mph DESC NULLS LAST
    `),
    supabase.query<FreshnessRow>(`
      SELECT max(fetched_at) AS newest, min(fetched_at) AS oldest, count(*)::int AS upcoming_rows
      FROM game_weather WHERE game_date >= CURRENT_DATE::text
    `),
  ])

  return {
    coverage: coverageRes.data,
    board: boardRes.data,
    freshness: freshnessRes.data[0] ?? null,
  }
}
