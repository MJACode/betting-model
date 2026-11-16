type HealthCheckRow = {
  check_name: string
  status: string
  severity: string
  detail: string
  checked_at: string
  reason: string
  cadence: string
}

type HealthResult = {
  runDate: string
  checks: HealthCheckRow[]
}

export default async function (_req: { params: Record<string, never>; user: User }): Promise<HealthResult> {
  const [checksRes, runDateRes] = await Promise.all([
    supabase.query<HealthCheckRow>(`
      SELECT check_name, status, severity, detail, checked_at, reason, cadence
      FROM system_health_checks
      WHERE run_date = (SELECT MAX(run_date) FROM system_health_checks)
        AND status <> 'OK'
      ORDER BY severity DESC, check_name
    `),
    supabase.query<{ run_date: string }>(`SELECT MAX(run_date) AS run_date FROM system_health_checks`),
  ])
  return {
    runDate: runDateRes.data[0]?.run_date ?? '',
    checks: checksRes.data,
  }
}
