import { isMissingRelation, errorMessage } from './dbErrors'

/**
 * The Database tab's history: one point per stored snapshot of Supabase
 * (tracking/db_health.py writes them hourly). Counters are Postgres's running
 * totals as stored; the page turns the change between two points into a rate
 * and leaves a gap where a counter went down (a reset).
 *
 * Reads only db_health_snapshots. Older than 14 days, one point per six hours.
 */

type Params = { days?: number }

export type DbHealthPoint = {
  taken_at: string
  source: string
  db_bytes: number
  table_bytes: number | null
  index_bytes: number | null
  toast_bytes: number | null
  relations: number | null
  live_rows_est: number | null
  dead_rows_est: number | null
  connections: number | null
  connections_active: number | null
  connections_idle: number | null
  connections_idle_in_tx: number | null
  max_connections: number | null
  longest_xact_s: number | null
  waiting_locks: number | null
  xid_age: number | null
  freeze_max_age: number | null
  blks_hit: number | null
  blks_read: number | null
  xact_commit: number | null
  xact_rollback: number | null
  temp_bytes: number | null
  deadlocks: number | null
  stats_reset: string | null
  active_time_ms: number | null
  idle_in_tx_time_ms: number | null
  sessions: number | null
  stmt_calls: number | null
  stmt_exec_ms: number | null
  stmt_reset: string | null
  stmt_dealloc: number | null
  unused_indexes: number | null
  unused_index_bytes: number | null
  storage_objects: number | null
  storage_bytes: number | null
  storage_buckets: Array<{ bucket: string; objects: number; bytes: number }> | null
}

type Result =
  | { ok: true; available: boolean; days: number; points: DbHealthPoint[]; total: number; firstAt: string | null }
  | { ok: false; message: string }

const ALLOWED_DAYS = [7, 30, 90] as const

export default async function (req: { params: Params; user: User }): Promise<Result> {
  const asked = Number(req.params?.days)
  const days = (ALLOWED_DAYS as readonly number[]).includes(asked) ? asked : 30

  try {
    const [pointsRes, metaRes] = await Promise.all([
      supabase.query<DbHealthPoint>(
        `SELECT DISTINCT ON (bucket)
                to_char(taken_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS taken_at,
                source,
                db_bytes::float8 AS db_bytes, table_bytes::float8 AS table_bytes,
                index_bytes::float8 AS index_bytes, toast_bytes::float8 AS toast_bytes,
                relations, live_rows_est::float8 AS live_rows_est, dead_rows_est::float8 AS dead_rows_est,
                connections, connections_active, connections_idle, connections_idle_in_tx, max_connections,
                longest_xact_s, waiting_locks, xid_age::float8 AS xid_age, freeze_max_age::float8 AS freeze_max_age,
                blks_hit::float8 AS blks_hit, blks_read::float8 AS blks_read,
                xact_commit::float8 AS xact_commit, xact_rollback::float8 AS xact_rollback,
                temp_bytes::float8 AS temp_bytes, deadlocks::float8 AS deadlocks,
                to_char(stats_reset AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS stats_reset,
                active_time_ms, idle_in_tx_time_ms, sessions::float8 AS sessions,
                stmt_calls::float8 AS stmt_calls, stmt_exec_ms,
                to_char(stmt_reset AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS stmt_reset,
                stmt_dealloc::float8 AS stmt_dealloc,
                unused_indexes, unused_index_bytes::float8 AS unused_index_bytes,
                storage_objects::float8 AS storage_objects, storage_bytes::float8 AS storage_bytes,
                storage_buckets
           FROM (
             SELECT *,
                    CASE WHEN taken_at >= now() - interval '14 days'
                         THEN snapshot_id::text
                         ELSE to_char(date_trunc('day', taken_at) + floor(extract(hour FROM taken_at) / 6) * interval '6 hours', 'YYYY-MM-DD HH24')
                    END AS bucket
               FROM db_health_snapshots
              WHERE taken_at >= now() - make_interval(days => $1::int)
           ) s
          ORDER BY bucket, taken_at DESC`,
        [days],
      ),
      supabase.query<{ total: number; first_at: string | null }>(
        `SELECT count(*)::int AS total,
                to_char(min(taken_at) AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS first_at
           FROM db_health_snapshots`,
      ),
    ])
    const points = [...pointsRes.data].sort((a, b) => a.taken_at.localeCompare(b.taken_at))
    return {
      ok: true,
      available: true,
      days,
      points,
      total: metaRes.data[0]?.total ?? 0,
      firstAt: metaRes.data[0]?.first_at ?? null,
    }
  } catch (err) {
    if (isMissingRelation(err)) return { ok: true, available: false, days, points: [], total: 0, firstAt: null }
    return { ok: false, message: errorMessage(err) }
  }
}
