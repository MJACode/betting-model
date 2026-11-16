export type ApiSourceRow = {
  api: string
  source: string
  calls_2d: number
  calls_per_day: number
  med_min_between_runs: number | null
  runs_2d: number
}

export default async function getApiSourceFrequency(_req: { params: Record<string, never>; user: User }) {
  const result = await supabase.query<ApiSourceRow>(`
    WITH g AS (
      SELECT api, source,
             EXTRACT(epoch FROM ts::timestamptz
                     - lag(ts::timestamptz) OVER (PARTITION BY api, source ORDER BY ts::timestamptz)) AS gap_s
      FROM api_call_log WHERE ts::timestamptz >= now() - interval '2 days')
    SELECT api, source,
           count(*)::int AS calls_2d,
           round(count(*)/2.0)::int AS calls_per_day,
           round((percentile_cont(0.5) WITHIN GROUP (ORDER BY gap_s)
                  FILTER (WHERE gap_s > 120)/60.0)::numeric, 1)::float8 AS med_min_between_runs,
           count(*) FILTER (WHERE gap_s > 120)::int AS runs_2d
    FROM g GROUP BY 1, 2 ORDER BY calls_2d DESC
  `)
  return { rows: result.data }
}
