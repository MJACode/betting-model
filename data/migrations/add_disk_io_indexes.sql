-- Disk IO remediation (2026-08-30) — applied to Supabase as migration
-- `add_disk_io_indexes`. This file is the recoverable repo copy.
--
-- Context: Supabase emailed a "project is depleting its Disk IO Budget"
-- alert. pg_stat_statements traced ~95% of disk reads to five hot queries
-- doing full-table scans, each missing an index. GB figures below are
-- cumulative disk reads measured at diagnosis time.
--
-- Effect measured after applying (EXPLAIN ANALYZE on production):
--   _lookup_player_id  96 ms/call -> 2.4 ms   (was ~10 MB of reads per call)
--   _book_opener     2,111 ms/call -> 1.1 ms  (was ~90 MB of reads per call)

-- 1. scorer._lookup_player_id: LOWER(player_name) made every name resolution
--    a seq scan of the 479k-row table. 68k calls, 638 GB read — the #1 driver.
CREATE INDEX IF NOT EXISTS idx_player_game_log_name
  ON public.player_game_log (lower(player_name), player_type);

-- 2. scorer._book_opener (NCAAF cross-book opener rule) and the latest-odds
--    lookup family filter (game_id, market, bookmaker) with ORDER BY
--    snapshot_at LIMIT 1. Without bookmaker+snapshot_at in an index the
--    planner walked idx_odds_date across the whole 1.5M-row table.
--    2.1 s/call opener + 33 ms/call latest = 425 GB read combined.
CREATE INDEX IF NOT EXISTS idx_odds_book_snap
  ON public.odds (game_id, market, bookmaker, snapshot_at);

-- 3. Freshness probes (SELECT MAX(snapshot_at)) full-scanned the 1.5 GB
--    player_prop_odds table: 7.2 s/call, 131 GB read.
CREATE INDEX IF NOT EXISTS idx_prop_odds_snapshot
  ON public.player_prop_odds (snapshot_at);

-- 4. The live loops' _locked_live_lanes (WHERE game_id = X AND result IS NULL
--    AND is_live = Y) and per-game pick deletes had no game_id index on picks
--    — a seq scan every 5-second live pass (1.78B tuples read via seq scans).
CREATE INDEX IF NOT EXISTS idx_picks_game
  ON public.picks (game_id);

-- 5. Latest-live-state reads filter snapshot_at >= cutoff; only
--    (game_id, snapshot_at) existed.
CREATE INDEX IF NOT EXISTS idx_live_state_snapshot
  ON public.live_game_state (snapshot_at);
