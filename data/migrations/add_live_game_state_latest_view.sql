-- add_live_game_state_latest_view (applied 2026-07-29)
--
-- Surface live (in-play) score + inning on the mobile pick cards.
--
-- live_game_state is an append-only snapshot table written every ~15s by the
-- live poller (data/ingestors/live_game_state_poller.py). The app only ever
-- needs the FRESHEST row per game, so expose that through a view rather than
-- letting the client pull thousands of snapshots.
--
-- security_invoker (project convention — see v_latest_dk_odds) means the view
-- respects caller RLS, so anon also needs a SELECT policy on the base table.
-- The data is public game state (score, inning, outs) — nothing sensitive.

CREATE POLICY "anon read live_game_state"
  ON live_game_state FOR SELECT TO anon, authenticated USING (true);

CREATE OR REPLACE VIEW v_live_game_state_latest
WITH (security_invoker = on) AS
SELECT DISTINCT ON (s.game_id)
    s.game_id,
    g.game_date,
    s.snapshot_at,
    s.inning,
    s.inning_half,
    s.outs,
    s.bases_state,
    s.home_score,
    s.away_score,
    s.abstract_game_state
FROM live_game_state s
JOIN games g ON g.game_id = s.game_id
ORDER BY s.game_id, s.snapshot_at DESC, s.state_id DESC;

GRANT SELECT ON v_live_game_state_latest TO anon, authenticated;
