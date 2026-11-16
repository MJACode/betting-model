type QuotaRow = {
  quota_date: string
  used: number
  remaining: number
  total: number
  pct_left: number | null
  burn_today: number | null
  days_left: number | null
  observed_at: string
  obs_age_h: number | null
}

type CheckRow = {
  check_name: string
  status: string
  severity: string
  detail: string
  checked_at: string
}

type OddsApiHealthResult = {
  quota: QuotaRow | null
  checks: CheckRow[]
}

export default async function (_req: { params: Record<string, never>; user: User }): Promise<OddsApiHealthResult> {
  const [quotaRes, checksRes] = await Promise.all([
    supabase.query<QuotaRow>(`
      WITH latest AS (
        SELECT quota_date, requests_used, requests_remaining, observed_at
        FROM odds_api_quota ORDER BY quota_date DESC LIMIT 1),
      prev AS (
        SELECT requests_used FROM odds_api_quota
        WHERE quota_date < (SELECT quota_date FROM latest)
        ORDER BY quota_date DESC LIMIT 1)
      SELECT l.quota_date::text AS quota_date,
             l.requests_used::bigint AS used, l.requests_remaining::bigint AS remaining,
             (l.requests_used + l.requests_remaining)::bigint AS total,
             round(l.requests_remaining / NULLIF(l.requests_used + l.requests_remaining, 0) * 100, 1)::float8 AS pct_left,
             (l.requests_used - p.requests_used)::bigint AS burn_today,
             CASE WHEN (l.requests_used - p.requests_used) > 0
                  THEN round(l.requests_remaining / (l.requests_used - p.requests_used), 1) END::float8 AS days_left,
             l.observed_at::text AS observed_at,
             round(EXTRACT(epoch FROM (NOW() - l.observed_at::timestamptz)) / 3600.0, 1)::float8 AS obs_age_h
      FROM latest l LEFT JOIN prev p ON TRUE
    `),
    supabase.query<CheckRow>(`
      SELECT check_name, status, severity, detail, checked_at
      FROM system_health_checks
      WHERE run_date = (SELECT MAX(run_date) FROM system_health_checks)
        AND check_name IN ('odds_api_credits', 'odds_dk_lines', 'player_prop_odds')
      ORDER BY check_name
    `),
  ])
  return {
    quota: quotaRes.data[0] ?? null,
    checks: checksRes.data,
  }
}
