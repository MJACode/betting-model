import { isMissingRelation, errorMessage } from './dbErrors'

/**
 * The statements that have used the most database time, from the newest
 * per-statement snapshot (pg_stat_statements, stored every six hours by
 * tracking/db_health.py), with the same statement at the newest snapshot at
 * least 23 hours older so the page can show the last day's time. A statement
 * absent from the older snapshot, or whose totals went down (a reset), has no
 * last-day figure.
 *
 * Statement text is Postgres's normalised form: constants are $1, $2, ...
 */

export type DbQueryRow = {
  queryid: string
  role_name: string
  toplevel: boolean
  calls: number
  total_exec_ms: number
  mean_exec_ms: number
  max_exec_ms: number | null
  rows: number | null
  shared_blks_read: number | null
  temp_blks_written: number | null
  query: string
  ref_calls: number | null
  ref_total_ms: number | null
}

type Meta = {
  latest_at: string | null
  ref_at: string | null
  stmt_exec_ms: number | null
  stmt_reset: string | null
  ref_stmt_exec_ms: number | null
  ref_stmt_reset: string | null
}

type Result =
  | { ok: true; available: boolean; meta: Meta; queries: DbQueryRow[] }
  | { ok: false; message: string }

const EMPTY_META: Meta = {
  latest_at: null, ref_at: null, stmt_exec_ms: null, stmt_reset: null, ref_stmt_exec_ms: null, ref_stmt_reset: null,
}

const ISO = `'YYYY-MM-DD"T"HH24:MI:SS"Z"'`

export default async function (_req: { params: Record<string, never>; user: User }): Promise<Result> {
  try {
    const metaRes = await supabase.query<Meta & { latest_id: string | null; ref_id: string | null }>(
      `WITH runs AS (
         SELECT snapshot_id, taken_at, stmt_exec_ms, stmt_reset FROM db_health_snapshots WHERE table_rows_taken
       ), latest AS (
         SELECT * FROM runs ORDER BY taken_at DESC LIMIT 1
       ), ref AS (
         SELECT r.* FROM runs r, latest l WHERE r.taken_at <= l.taken_at - interval '23 hours'
          ORDER BY r.taken_at DESC LIMIT 1
       )
       SELECT (SELECT snapshot_id::text FROM latest) AS latest_id,
              to_char((SELECT taken_at FROM latest) AT TIME ZONE 'UTC', ${ISO}) AS latest_at,
              (SELECT stmt_exec_ms FROM latest) AS stmt_exec_ms,
              to_char((SELECT stmt_reset FROM latest) AT TIME ZONE 'UTC', ${ISO}) AS stmt_reset,
              (SELECT snapshot_id::text FROM ref) AS ref_id,
              to_char((SELECT taken_at FROM ref) AT TIME ZONE 'UTC', ${ISO}) AS ref_at,
              (SELECT stmt_exec_ms FROM ref) AS ref_stmt_exec_ms,
              to_char((SELECT stmt_reset FROM ref) AT TIME ZONE 'UTC', ${ISO}) AS ref_stmt_reset`,
    )
    const m = metaRes.data[0]
    if (!m || !m.latest_id) return { ok: true, available: true, meta: EMPTY_META, queries: [] }

    const queriesRes = await supabase.query<DbQueryRow>(
      `SELECT q.queryid::text AS queryid, q.role_name, q.toplevel,
              q.calls::float8 AS calls, q.total_exec_ms, q.mean_exec_ms, q.max_exec_ms,
              q.rows::float8 AS rows, q.shared_blks_read::float8 AS shared_blks_read,
              q.temp_blks_written::float8 AS temp_blks_written,
              left(x.query, 1200) AS query,
              r.calls::float8 AS ref_calls, r.total_exec_ms AS ref_total_ms
         FROM db_query_snapshots q
         JOIN db_query_texts x ON x.queryid = q.queryid
         LEFT JOIN db_query_snapshots r
           ON r.snapshot_id = $1::bigint AND r.queryid = q.queryid
          AND r.role_name = q.role_name AND r.toplevel = q.toplevel
        WHERE q.snapshot_id = $2::bigint
        ORDER BY q.total_exec_ms DESC
        LIMIT 60`,
      // The driver binds $N in the order the placeholders first appear in the
      // text, so they are numbered top to bottom (Retool's own note on .query).
      [m.ref_id ?? '0', m.latest_id],
    )
    return {
      ok: true,
      available: true,
      meta: {
        latest_at: m.latest_at,
        ref_at: m.ref_at,
        stmt_exec_ms: m.stmt_exec_ms,
        stmt_reset: m.stmt_reset,
        ref_stmt_exec_ms: m.ref_stmt_exec_ms,
        ref_stmt_reset: m.ref_stmt_reset,
      },
      queries: queriesRes.data,
    }
  } catch (err) {
    if (isMissingRelation(err)) return { ok: true, available: false, meta: EMPTY_META, queries: [] }
    return { ok: false, message: errorMessage(err) }
  }
}
