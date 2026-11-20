import { isMissingRelation, errorMessage } from './dbErrors'

/**
 * The Database tab's PC copy section: the copy of the database, its storage
 * and GitHub on mike's PC. One row per report, written by
 * scripts/local_mirror_report.py last in each pass of the PC's LocalMirror
 * task (nightly at 00:30, and two minutes after mike signs in), or by hand.
 * Every number was read on the PC, from the copy's own files.
 *
 * Reads only pc_copy_snapshots: the last 120 days, oldest first.
 *
 * copy_kind is diff (the nightly catch-up) or full (monthly), NULL before
 * 2026-11-20. schedule is the LocalMirror task as Task Scheduler held it when
 * the row was written, with the last monthly full and when the next is due
 * (local_mirror_report.py read_schedule); NULL on rows before 2026-11-20.
 */

export type PcCopyTrigger = { type: string; enabled: boolean | null; at?: string; delay?: string }

export type PcCopySchedule = {
  task: string
  read_at: string
  diff?: string
  full?: string
  state?: string | null
  next_run_at?: string | null
  last_run_at?: string | null
  last_result?: number | null
  triggers?: PcCopyTrigger[]
  last_full: { run_id: string | null; run_started_at: string | null; run_finished_at: string | null; failed_tables: string[] | null } | null
  next_full_from: string | null
  error?: string
}

export type PcCopyDiffering = {
  table: string
  local_rows: number
  supabase_rows: number
  ranges_differ: number | null
  ranges_not_counted: number | null
  checked_at: string | null
}

export type PcCopyPoint = {
  taken_at: string
  source: string
  pass_id: string
  pass_started_at: string | null
  copy_run_id: string | null
  copy_started_at: string | null
  copy_finished_at: string | null
  copy_tables: number | null
  copy_rows_pulled: number | null
  copy_this_pass: boolean | null
  failed_tables: string[] | null
  differing_tables: PcCopyDiffering[] | null
  github_exit: number | null
  supabase_exit: number | null
  duckdb_exit: number | null
  github_finished_at: string | null
  github_repos: number | null
  github_repos_failed: number | null
  local_tables: number | null
  local_rows: number | null
  tables_bytes: number | null
  schema_bytes: number | null
  storage_bytes: number | null
  github_bytes: number | null
  duckdb_bytes: number | null
  other_bytes: number | null
  total_bytes: number | null
  disk_total_bytes: number | null
  disk_free_bytes: number | null
  copy_kind: string | null
  schedule: PcCopySchedule | null
}

type Result =
  | { ok: true; available: boolean; points: PcCopyPoint[]; total: number; firstAt: string | null }
  | { ok: false; message: string }

const ISO = `'YYYY-MM-DD"T"HH24:MI:SS"Z"'`

export default async function (_req: { params: Record<string, never>; user: User }): Promise<Result> {
  try {
    const [pointsRes, metaRes] = await Promise.all([
      supabase.query<PcCopyPoint>(
        `SELECT to_char(taken_at AT TIME ZONE 'UTC', ${ISO}) AS taken_at,
                source, pass_id,
                to_char(pass_started_at AT TIME ZONE 'UTC', ${ISO}) AS pass_started_at,
                copy_run_id,
                to_char(copy_started_at AT TIME ZONE 'UTC', ${ISO}) AS copy_started_at,
                to_char(copy_finished_at AT TIME ZONE 'UTC', ${ISO}) AS copy_finished_at,
                copy_tables, copy_rows_pulled::float8 AS copy_rows_pulled, copy_this_pass,
                failed_tables, differing_tables,
                github_exit, supabase_exit, duckdb_exit,
                to_char(github_finished_at AT TIME ZONE 'UTC', ${ISO}) AS github_finished_at,
                github_repos, github_repos_failed,
                local_tables, local_rows::float8 AS local_rows,
                tables_bytes::float8 AS tables_bytes, schema_bytes::float8 AS schema_bytes,
                storage_bytes::float8 AS storage_bytes, github_bytes::float8 AS github_bytes,
                duckdb_bytes::float8 AS duckdb_bytes, other_bytes::float8 AS other_bytes,
                total_bytes::float8 AS total_bytes,
                disk_total_bytes::float8 AS disk_total_bytes, disk_free_bytes::float8 AS disk_free_bytes,
                copy_kind, schedule
           FROM pc_copy_snapshots
          WHERE taken_at >= now() - interval '120 days'
          ORDER BY taken_at, snapshot_id`,
      ),
      supabase.query<{ total: number; first_at: string | null }>(
        `SELECT count(*)::int AS total,
                to_char(min(taken_at) AT TIME ZONE 'UTC', ${ISO}) AS first_at
           FROM pc_copy_snapshots`,
      ),
    ])
    return {
      ok: true,
      available: true,
      points: pointsRes.data,
      total: metaRes.data[0]?.total ?? 0,
      firstAt: metaRes.data[0]?.first_at ?? null,
    }
  } catch (err) {
    if (isMissingRelation(err)) return { ok: true, available: false, points: [], total: 0, firstAt: null }
    return { ok: false, message: errorMessage(err) }
  }
}
