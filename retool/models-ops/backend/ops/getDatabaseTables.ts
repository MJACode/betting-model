import { isMissingRelation, errorMessage } from './dbErrors'

/**
 * Every table's size at the newest per-table snapshot, beside the same table
 * at three earlier ones: the previous snapshot, the newest one at least 23
 * hours older, and the newest at least 6 days 20 hours older. Snapshots are
 * every six hours (tracking/db_health.py), so "a day" and "a week" land within
 * one snapshot of exact. A reference that does not exist yet is null.
 *
 * Row counts are Postgres's estimates (n_live_tup), never count(*).
 */

export type DbTableRow = {
  schema_name: string
  table_name: string
  kind: string
  total_bytes: number
  heap_bytes: number | null
  index_bytes: number | null
  toast_bytes: number | null
  live_rows_est: number | null
  dead_rows_est: number | null
  n_tup_ins: number | null
  n_tup_upd: number | null
  n_tup_del: number | null
  seq_scan: number | null
  idx_scan: number | null
  last_vacuum: string | null
  last_analyze: string | null
  prev_bytes: number | null
  prev_rows: number | null
  day_bytes: number | null
  day_rows: number | null
  week_bytes: number | null
  week_rows: number | null
}

type Refs = {
  latest_at: string | null
  prev_at: string | null
  day_at: string | null
  week_at: string | null
  first_at: string | null
  runs: number
}

type Result =
  | { ok: true; available: boolean; refs: Refs; tables: DbTableRow[] }
  | { ok: false; message: string }

const EMPTY_REFS: Refs = { latest_at: null, prev_at: null, day_at: null, week_at: null, first_at: null, runs: 0 }

const ISO = `'YYYY-MM-DD"T"HH24:MI:SS"Z"'`

export default async function (_req: { params: Record<string, never>; user: User }): Promise<Result> {
  try {
    const refsRes = await supabase.query<Refs & { latest_id: string | null; prev_id: string | null; day_id: string | null; week_id: string | null }>(
      `WITH runs AS (
         SELECT snapshot_id, taken_at FROM db_health_snapshots WHERE table_rows_taken
       ), latest AS (
         SELECT snapshot_id, taken_at FROM runs ORDER BY taken_at DESC LIMIT 1
       )
       SELECT
         (SELECT snapshot_id::text FROM latest) AS latest_id,
         to_char((SELECT taken_at FROM latest) AT TIME ZONE 'UTC', ${ISO}) AS latest_at,
         (SELECT r.snapshot_id::text FROM runs r, latest l WHERE r.taken_at < l.taken_at ORDER BY r.taken_at DESC LIMIT 1) AS prev_id,
         to_char((SELECT r.taken_at FROM runs r, latest l WHERE r.taken_at < l.taken_at ORDER BY r.taken_at DESC LIMIT 1) AT TIME ZONE 'UTC', ${ISO}) AS prev_at,
         (SELECT r.snapshot_id::text FROM runs r, latest l WHERE r.taken_at <= l.taken_at - interval '23 hours' ORDER BY r.taken_at DESC LIMIT 1) AS day_id,
         to_char((SELECT r.taken_at FROM runs r, latest l WHERE r.taken_at <= l.taken_at - interval '23 hours' ORDER BY r.taken_at DESC LIMIT 1) AT TIME ZONE 'UTC', ${ISO}) AS day_at,
         (SELECT r.snapshot_id::text FROM runs r, latest l WHERE r.taken_at <= l.taken_at - interval '6 days 20 hours' ORDER BY r.taken_at DESC LIMIT 1) AS week_id,
         to_char((SELECT r.taken_at FROM runs r, latest l WHERE r.taken_at <= l.taken_at - interval '6 days 20 hours' ORDER BY r.taken_at DESC LIMIT 1) AT TIME ZONE 'UTC', ${ISO}) AS week_at,
         to_char((SELECT min(taken_at) FROM runs) AT TIME ZONE 'UTC', ${ISO}) AS first_at,
         (SELECT count(*)::int FROM runs) AS runs`,
    )
    const r = refsRes.data[0]
    if (!r || !r.latest_id) return { ok: true, available: true, refs: EMPTY_REFS, tables: [] }

    const tablesRes = await supabase.query<DbTableRow>(
      `SELECT t.schema_name, t.table_name, t.kind,
              t.total_bytes::float8 AS total_bytes, t.heap_bytes::float8 AS heap_bytes,
              t.index_bytes::float8 AS index_bytes, t.toast_bytes::float8 AS toast_bytes,
              t.live_rows_est::float8 AS live_rows_est, t.dead_rows_est::float8 AS dead_rows_est,
              t.n_tup_ins::float8 AS n_tup_ins, t.n_tup_upd::float8 AS n_tup_upd, t.n_tup_del::float8 AS n_tup_del,
              t.seq_scan::float8 AS seq_scan, t.idx_scan::float8 AS idx_scan,
              to_char(t.last_vacuum AT TIME ZONE 'UTC', ${ISO}) AS last_vacuum,
              to_char(t.last_analyze AT TIME ZONE 'UTC', ${ISO}) AS last_analyze,
              p.total_bytes::float8 AS prev_bytes, p.live_rows_est::float8 AS prev_rows,
              d.total_bytes::float8 AS day_bytes, d.live_rows_est::float8 AS day_rows,
              w.total_bytes::float8 AS week_bytes, w.live_rows_est::float8 AS week_rows
         FROM db_table_snapshots t
         LEFT JOIN db_table_snapshots p
           ON p.snapshot_id = $1::bigint AND p.schema_name = t.schema_name AND p.table_name = t.table_name
         LEFT JOIN db_table_snapshots d
           ON d.snapshot_id = $2::bigint AND d.schema_name = t.schema_name AND d.table_name = t.table_name
         LEFT JOIN db_table_snapshots w
           ON w.snapshot_id = $3::bigint AND w.schema_name = t.schema_name AND w.table_name = t.table_name
        WHERE t.snapshot_id = $4::bigint
        ORDER BY t.total_bytes DESC`,
      // The driver binds $N in the order the placeholders first appear in the
      // text, so they are numbered top to bottom (Retool's own note on .query).
      [r.prev_id ?? '0', r.day_id ?? '0', r.week_id ?? '0', r.latest_id],
    )
    return {
      ok: true,
      available: true,
      refs: {
        latest_at: r.latest_at,
        prev_at: r.prev_at,
        day_at: r.day_at,
        week_at: r.week_at,
        first_at: r.first_at,
        runs: r.runs,
      },
      tables: tablesRes.data,
    }
  } catch (err) {
    if (isMissingRelation(err)) return { ok: true, available: false, refs: EMPTY_REFS, tables: [] }
    return { ok: false, message: errorMessage(err) }
  }
}
