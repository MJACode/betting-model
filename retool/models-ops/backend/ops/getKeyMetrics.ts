// The Key Metrics tab: the published record, closing-line value, the models and
// the operations, in one call. Every figure is read from the views the record
// itself uses (v_public_track_record, v_public_track_record_daily and the
// v_model_health_* views, which read the record's own filter), so nothing here
// is a second definition of "published".

type DailyRow = { game_date: string; bets: number; units: number; risked: number }

type ClvRow = {
  measured: number
  beat: number
  matched: number
  trailed: number
  beat_price: number
  beat_line: number
  matched_price: number
  trailed_price: number
  trailed_line: number
  avg_clv_pct: number | null
  pin_n: number
  pin_beat: number
  pin_avg_pct: number | null
  in_play: number
  no_close: number
  bets: number
}

type ModelRow = {
  model_id: string
  sport: string
  bets: number
  wins: number
  losses: number
  pushes: number
  units: number
  risked: number
  in_play: number
  price_n: number
  avg_clv_pct: number | null
  se_clv_pct: number | null
}

type CountsRow = { live: number; paused: number; today_et: string }

type PipelineRow = { started_at: string; finished_at: string | null; ok: boolean | null; steps_failed: number | null; failed_steps: string | null }

type CheckRow = { run_date: string; ok: number; skipped: number; problems: number; problem_names: string | null }

type CreditsRow = { remaining: number | null; observed_at: string | null; median_burn: number | null; burn_days: number }

export type KeyMetrics = {
  daily: DailyRow[]
  clv: ClvRow | null
  models: ModelRow[]
  counts: CountsRow | null
  pipeline: PipelineRow | null
  checks: CheckRow | null
  credits: CreditsRow | null
}

export default async function (_req: { params: Record<string, never>; user: User }): Promise<KeyMetrics> {
  const [daily, clv, models, counts, pipeline, checks, credits] = await Promise.all([
    supabase.query<DailyRow>(`
      SELECT game_date::text AS game_date, sum(picks)::int AS bets,
             round(sum(units)::numeric, 4)::float8 AS units, round(sum(risked)::numeric, 4)::float8 AS risked
        FROM v_public_track_record_daily
       GROUP BY game_date ORDER BY game_date`),
    supabase.query<ClvRow>(`
      SELECT count(*) FILTER (WHERE status IN ('price', 'line_for', 'line_against'))::int AS measured,
             count(*) FILTER (WHERE verdict = 'beat')::int AS beat,
             count(*) FILTER (WHERE verdict = 'push')::int AS matched,
             count(*) FILTER (WHERE verdict = 'miss')::int AS trailed,
             count(*) FILTER (WHERE status = 'price' AND verdict = 'beat')::int AS beat_price,
             count(*) FILTER (WHERE status = 'line_for')::int AS beat_line,
             count(*) FILTER (WHERE status = 'price' AND verdict = 'push')::int AS matched_price,
             count(*) FILTER (WHERE status = 'price' AND verdict = 'miss')::int AS trailed_price,
             count(*) FILTER (WHERE status = 'line_against')::int AS trailed_line,
             round(avg(clv_pct)::numeric, 2)::float8 AS avg_clv_pct,
             count(market_clv_pct)::int AS pin_n,
             count(*) FILTER (WHERE market_clv_pct > 0)::int AS pin_beat,
             round(avg(market_clv_pct)::numeric, 2)::float8 AS pin_avg_pct,
             count(*) FILTER (WHERE status = 'in_play')::int AS in_play,
             count(*) FILTER (WHERE status = 'no_close')::int AS no_close,
             count(*)::int AS bets
        FROM v_model_health_bets`),
    // One row per model over the published record's bets. The record's totals
    // are the sum of these rows: the same bets and units as v_public_track_record
    // (1,636 bets, +71.11u on both, read 2026-11-19), one heavy read fewer.
    supabase.query<ModelRow>(`
      SELECT model_id, sport, bets::int AS bets, wins::int AS wins, losses::int AS losses,
             pushes::int AS pushes, units::float8 AS units, risked::float8 AS risked,
             in_play::int AS in_play, price_n::int AS price_n,
             avg_clv_pct::float8 AS avg_clv_pct, se_clv_pct::float8 AS se_clv_pct
        FROM v_model_health_summary`),
    supabase.query<CountsRow>(`
      SELECT count(*) FILTER (WHERE NOT paused)::int AS live, count(*) FILTER (WHERE paused)::int AS paused,
             (now() AT TIME ZONE 'America/New_York')::date::text AS today_et
        FROM model_action_thresholds`),
    supabase.query<PipelineRow>(`
      SELECT started_at::text AS started_at, finished_at::text AS finished_at, ok, steps_failed, failed_steps
        FROM pipeline_runs WHERE run_kind = 'daily' ORDER BY started_at DESC LIMIT 1`),
    supabase.query<CheckRow>(`
      SELECT max(run_date)::text AS run_date,
             count(*) FILTER (WHERE status = 'OK')::int AS ok,
             count(*) FILTER (WHERE status = 'SKIPPED')::int AS skipped,
             count(*) FILTER (WHERE status NOT IN ('OK', 'SKIPPED'))::int AS problems,
             string_agg(check_name || ' (' || lower(status) || ')', ', ' ORDER BY check_name)
               FILTER (WHERE status NOT IN ('OK', 'SKIPPED')) AS problem_names
        FROM system_health_checks
       WHERE run_date = (SELECT max(run_date) FROM system_health_checks)`),
    supabase.query<CreditsRow>(`
      WITH q AS (
        SELECT quota_date, requests_remaining, observed_at,
               requests_used - lag(requests_used) OVER (ORDER BY quota_date) AS burn
          FROM odds_api_quota ORDER BY quota_date DESC LIMIT 15)
      SELECT (SELECT requests_remaining FROM q ORDER BY quota_date DESC LIMIT 1)::float8 AS remaining,
             (SELECT observed_at FROM q ORDER BY quota_date DESC LIMIT 1)::text AS observed_at,
             (percentile_cont(0.5) WITHIN GROUP (ORDER BY burn) FILTER (WHERE burn > 0))::float8 AS median_burn,
             count(*) FILTER (WHERE burn > 0)::int AS burn_days
        FROM q`),
  ])
  return {
    daily: daily.data,
    clv: clv.data[0] ?? null,
    models: models.data,
    counts: counts.data[0] ?? null,
    pipeline: pipeline.data[0] ?? null,
    checks: checks.data[0] ?? null,
    credits: credits.data[0] ?? null,
  }
}
