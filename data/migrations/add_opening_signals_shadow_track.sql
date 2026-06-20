-- Migration: add_opening_signals_shadow_track
-- Apply via Supabase MCP apply_migration (project ref vvprgnrmzeekokzkrkfu) or
-- the SQL editor. Mirrors the opening_signals block in supabase_schema.sql.
--
-- Opening-signal shadow track: locks the FIRST refresh a game/market crosses the
-- BET threshold so it stops churning, runs beside the live `picks` table, and
-- records how the line moved after lock (clv_pct vs our opening dk_odds) and
-- which side the public was on.

CREATE TABLE IF NOT EXISTS opening_signals (
    id                 BIGSERIAL PRIMARY KEY,
    lock_key           TEXT NOT NULL,
    game_id            TEXT REFERENCES games(game_id),
    model_id           TEXT NOT NULL,
    sport              TEXT NOT NULL,
    game_date          TEXT NOT NULL,
    player_id          TEXT,
    pick_side          TEXT NOT NULL,
    pick_label         TEXT NOT NULL,
    model_probability  NUMERIC NOT NULL,
    dk_implied_prob    NUMERIC,
    edge               NUMERIC,
    dk_odds            NUMERIC,
    scored_line        NUMERIC,
    public_bet_pct     NUMERIC,
    public_money_pct   NUMERIC,
    confidence_tier    TEXT,
    kelly_fraction     NUMERIC,
    recommended_bet    NUMERIC,
    bankroll_at_pick   NUMERIC,
    locked_at          TEXT NOT NULL,
    closing_dk_odds    NUMERIC,
    closing_line       NUMERIC,
    clv_pct            NUMERIC,
    line_move_dir      TEXT,
    public_side        TEXT,
    result             TEXT,
    profit_flat        NUMERIC,
    profit_kelly       NUMERIC,
    settled_at         TEXT,
    created_at         TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(lock_key)
);

CREATE INDEX IF NOT EXISTS idx_opening_signals_date   ON opening_signals(game_date);
CREATE INDEX IF NOT EXISTS idx_opening_signals_model  ON opening_signals(model_id);
CREATE INDEX IF NOT EXISTS idx_opening_signals_settle ON opening_signals(result, line_move_dir, public_side);

ALTER TABLE opening_signals ENABLE ROW LEVEL SECURITY;

-- Pipeline writes via service-role DATABASE_URL (bypasses RLS). Anon read so the
-- mobile/website comparison report can surface the opening-vs-live record.
CREATE POLICY "anon read opening_signals" ON opening_signals
    FOR SELECT TO anon, authenticated USING (true);
