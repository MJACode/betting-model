type ApiCallRow = {
  day: string
  api: string
  source: string
  calls: number
  errors: number
  credits: number
}

type WindowRow = {
  first_day: string | null
  last_day: string | null
  days: number
}

type ApiCallTrendResult = {
  rows: ApiCallRow[]
  window: WindowRow
}

export default async function (_req: { params: Record<string, never>; user: User }): Promise<ApiCallTrendResult> {
  const [rowsRes, windowRes] = await Promise.all([
    supabase.query<ApiCallRow>(`
      SELECT day::text AS day, api, source,
             calls::bigint AS calls, errors::bigint AS errors,
             COALESCE(credits, 0)::bigint AS credits
      FROM api_call_daily
      ORDER BY day, api, source
    `),
    supabase.query<WindowRow>(`
      SELECT min(day)::text AS first_day, max(day)::text AS last_day,
             count(DISTINCT day)::int AS days
      FROM api_call_daily
    `),
  ])
  return {
    rows: rowsRes.data,
    window: windowRes.data[0] ?? { first_day: null, last_day: null, days: 0 },
  }
}
