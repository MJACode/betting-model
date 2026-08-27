-- Applied to Supabase as migration `add_ncaaf_qb_game`.
-- RLS on with no anon policy: pipeline-internal, written by the worker as
-- the table owner (which bypasses RLS) and never read by the mobile app.
-- NCAAF quarterback game log (CFBD /games/players, passing + rushing).
-- One row per passer per team-game. `is_primary` flags the QB who threw the
-- most passes for that team in that game -- our proxy for "the starter", since
-- CFBD's box score names participants, not the depth chart.
--
-- WHY THIS EXISTS: a backup QB moves a college line 4-7 points, and QB identity
-- was the one major CFB information channel never ingested. What this table
-- supports is QB CONTINUITY and QUALITY (who has been taking the snaps, how
-- well, and whether that changed) -- NOT "is the starter out this week", which
-- is unknowable pre-kickoff without an injury feed college football does not
-- reliably publish.
CREATE TABLE IF NOT EXISTS ncaaf_qb_game (
    qb_game_id   BIGSERIAL PRIMARY KEY,
    game_id      TEXT NOT NULL,
    team         TEXT NOT NULL,
    opponent     TEXT,
    season       INTEGER NOT NULL,
    week         INTEGER,
    season_type  TEXT,
    game_date    TEXT NOT NULL,
    player_id    TEXT NOT NULL,
    player_name  TEXT,
    is_primary   INTEGER,
    attempts     INTEGER, completions INTEGER,
    pass_yards   INTEGER, pass_td INTEGER, interceptions INTEGER,
    rush_att     INTEGER, rush_yards INTEGER, rush_td INTEGER,
    created_at   TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(game_id, team, player_id)
);
CREATE INDEX IF NOT EXISTS idx_ncaaf_qb_team ON ncaaf_qb_game(team, game_date);
CREATE INDEX IF NOT EXISTS idx_ncaaf_qb_game ON ncaaf_qb_game(game_id);
CREATE INDEX IF NOT EXISTS idx_ncaaf_qb_player ON ncaaf_qb_game(player_id, game_date);

ALTER TABLE public.ncaaf_qb_game ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.ncaaf_qb_game FROM anon, authenticated;
