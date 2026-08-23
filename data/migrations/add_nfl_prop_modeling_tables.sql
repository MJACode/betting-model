-- NFL player-prop modelling data (2026-08-23).
--
-- Three changes, all additive:
--   1. nfl_player_game_log gains the modelling columns the display ingest was
--      already downloading and discarding (usage shares, air yards, EPA, the
--      solo/assist tackle split, kicking splits). The mobile views and RPCs
--      select explicit column lists, so they are unaffected. The table's
--      docstring said "no model reads this table" — as of this migration the
--      NFL prop feature engine does.
--   2. nfl_team_game_stats — one row per team per game: offensive volume (the
--      denominator every usage share is taken against), plus the pre-game
--      market and environment context (spread, total, roof, wind, temp, rest).
--      Also the source of opponent-defence-allowed features, read from the
--      defending team's perspective.
--   3. nfl_snap_counts — snap share, the cleanest availability signal and the
--      main driver of the tackles+assists market. nflverse keys snaps on
--      pfr_player_id with no gsis id, so rows carry a normalised name key and
--      the feature engine joins on (norm_name, team, game_id) — verified 98-100%
--      coverage against the weekly stats on every pool that matters, with zero
--      duplicate keys.
--
-- No FK to games: only NFL games with a wind/opener pick ever get a games row,
-- while these tables cover the whole league (the nfl_player_game_log precedent).

ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS sacks_suffered      NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS passing_air_yards   NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS passing_epa         NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS rushing_first_downs INTEGER;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS receiving_air_yards NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS receiving_yac       NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS receiving_epa       NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS target_share        NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS air_yards_share     NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS wopr                NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS racr                NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS def_tackles_solo    NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS def_tackle_assists  NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS def_qb_hits         NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS fg_made             INTEGER;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS fg_att              INTEGER;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS pat_made            INTEGER;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS pat_att             INTEGER;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS norm_name           TEXT;

CREATE INDEX IF NOT EXISTS idx_nfl_plog_normname
    ON nfl_player_game_log(norm_name, team, game_id);

CREATE TABLE IF NOT EXISTS nfl_team_game_stats (
    row_id          BIGSERIAL PRIMARY KEY,
    game_id         TEXT NOT NULL,
    team            TEXT NOT NULL,
    opponent        TEXT NOT NULL,
    game_date       DATE NOT NULL,
    season          INTEGER NOT NULL,
    week            INTEGER,
    season_type     TEXT,
    is_home         INTEGER,
    -- offensive volume (the share denominator + the pace proxy)
    pass_attempts   INTEGER,
    carries         INTEGER,
    plays           INTEGER,
    pass_yards      NUMERIC,
    rush_yards      NUMERIC,
    completions     INTEGER,
    targets         INTEGER,
    -- pre-game market + environment context (nflverse games.csv)
    spread_line     NUMERIC,   -- home-relative, as nflverse publishes it
    total_line      NUMERIC,
    roof            TEXT,
    surface         TEXT,
    temp            NUMERIC,
    wind            NUMERIC,
    div_game        INTEGER,
    -- kickoff as a UTC ISO timestamp (gameday + gametime from the nflverse
    -- schedule). The scorer needs it to refuse to price a prop after the
    -- game has started — NFL games have no row in `games` unless they carry
    -- a wind/opener pick, so it cannot come from there.
    commence_time   TIMESTAMPTZ,
    points_for      INTEGER,
    points_against  INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(game_id, team)
);
CREATE INDEX IF NOT EXISTS idx_nfl_tgs_team   ON nfl_team_game_stats(team, game_date);
CREATE INDEX IF NOT EXISTS idx_nfl_tgs_season ON nfl_team_game_stats(season, week);
CREATE INDEX IF NOT EXISTS idx_nfl_tgs_opp    ON nfl_team_game_stats(opponent, game_date);

CREATE TABLE IF NOT EXISTS nfl_snap_counts (
    row_id          BIGSERIAL PRIMARY KEY,
    game_id         TEXT NOT NULL,
    team            TEXT NOT NULL,
    player_name     TEXT NOT NULL,
    norm_name       TEXT NOT NULL,
    pfr_player_id   TEXT,
    pos             TEXT,
    season          INTEGER NOT NULL,
    week            INTEGER,
    offense_snaps   INTEGER,
    offense_pct     NUMERIC,
    defense_snaps   INTEGER,
    defense_pct     NUMERIC,
    st_snaps        INTEGER,
    st_pct          NUMERIC,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(game_id, team, norm_name)
);
CREATE INDEX IF NOT EXISTS idx_nfl_snaps_join   ON nfl_snap_counts(norm_name, team, game_id);
CREATE INDEX IF NOT EXISTS idx_nfl_snaps_season ON nfl_snap_counts(season, week);

-- RLS on, no anon policy: modelling inputs, written by the pipeline via the
-- service-role DATABASE_URL. Matches nhl_team_stats / nba_team_stats /
-- ncaaf_team_stats. (nfl_player_game_log keeps its existing anon read policy —
-- the mobile Stats tab reads it.)
ALTER TABLE nfl_team_game_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE nfl_snap_counts     ENABLE ROW LEVEL SECURITY;
