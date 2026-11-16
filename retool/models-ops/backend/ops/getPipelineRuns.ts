type PipelineRunRow = {
  run_id: string
  started_at: string
  finished_at: string | null
  run_kind: string
  ok: boolean | null
  steps_total: number | null
  steps_failed: number | null
  failed_steps: string | null
}

type PipelineResult = {
  runs: PipelineRunRow[]
  total: number
}

export default async function (_req: { params: Record<string, never>; user: User }): Promise<PipelineResult> {
  const [runsRes, countRes] = await Promise.all([
    supabase.query<PipelineRunRow>(`
      SELECT run_id, started_at, finished_at, run_kind, ok, steps_total, steps_failed, failed_steps
      FROM pipeline_runs ORDER BY started_at DESC LIMIT 12
    `),
    supabase.query<{ total: string }>(`SELECT COUNT(*) AS total FROM pipeline_runs`),
  ])
  return {
    runs: runsRes.data,
    total: parseInt(countRes.data[0]?.total ?? '0', 10),
  }
}
