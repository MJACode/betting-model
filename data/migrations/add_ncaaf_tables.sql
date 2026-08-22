-- Migration: add_ncaaf_tables
-- NCAAF (FBS) model support — see docs/ncaaf_model_plan.md.
-- Three new tables plus three nullable schedule columns on the shared games
-- table. Additive only; nothing existing is altered or dropped.

-- ── NCAAF (college football, FBS) ────────────────────────────────────────────
-- Source: CollegeFootballData.com (free API key). The canonical team id is the
-- CFBD SCHOOL NAME ("Ohio State", "Miami (OH)"), not a 3-letter abbrev — 136
-- FBS programs collide badly in 3 letters, and CFBD is the source of truth for
-- both the stats and the historical lines. games.home_team/away_team store the
-- school name; game_id uses a slug. Season = calendar year of the FALL (a
-- January bowl belongs to the PRIOR season) and is always threaded explicitly.

-- School registry — also powers Odds API name -> CFBD school resolution
-- (The Odds API lists NCAAF teams with the mascot appended).
CREATE TABLE IF NOT EXISTS ncaaf_teams (
    school          TEXT PRIMARY KEY,
    abbreviation    TEXT,
    mascot          TEXT,
    conference      TEXT,
    division        TEXT,
    classification  TEXT,
    alt_names       TEXT,
    updated_at      TEXT DEFAULT (NOW()::TEXT)
);
CREATE INDEX IF NOT EXISTS idx_ncaaf_teams_conf ON ncaaf_teams(conference);

-- ASOF season-to-date team snapshot. The feature engine reads the newest row
-- with as_of_date <= game_date, then SHRINKS each rate toward the prior
-- season's value by games played (config.NCAAF_PRIOR_SHRINKAGE_K) — a raw
-- season-to-date average is noise for the first month of a 12-game season.
CREATE TABLE IF NOT EXISTS ncaaf_team_stats (
    stat_id                 BIGSERIAL PRIMARY KEY,
    team                    TEXT NOT NULL,
    season                  INTEGER NOT NULL,
    as_of_date              TEXT NOT NULL,
    games_played            INTEGER,
    -- Ratings (CFBD /ratings/*) — the backbone in a 12-game sport
    sp_overall              NUMERIC, sp_offense NUMERIC, sp_defense NUMERIC, sp_special_teams NUMERIC,
    srs                     NUMERIC, elo NUMERIC,
    -- Program strength (recruiting + continuity), the priors that carry weeks 1-5
    talent                  NUMERIC, returning_ppa NUMERIC,
    -- Efficiency (CFBD /stats/season/advanced)
    epa_per_play_off        NUMERIC, epa_per_play_def NUMERIC,
    success_rate_off        NUMERIC, success_rate_def NUMERIC,
    explosiveness_off       NUMERIC, explosiveness_def NUMERIC,
    havoc_rate              NUMERIC, havoc_rate_allowed NUMERIC,
    finishing_drives_off    NUMERIC, finishing_drives_def NUMERIC,
    avg_field_position_off  NUMERIC,
    third_down_rate_off     NUMERIC, third_down_rate_def NUMERIC,
    turnover_margin_pg      NUMERIC,
    -- Tempo — the dominant totals signal in CFB
    plays_per_game          NUMERIC, seconds_per_play NUMERIC,
    -- Scoring / record
    points_per_game         NUMERIC, points_allowed_pg NUMERIC,
    points_last_3           NUMERIC, point_differential NUMERIC,
    wins                    INTEGER, losses INTEGER,
    -- Context
    conference              TEXT, classification TEXT,
    created_at              TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(team, season, as_of_date)
);
CREATE INDEX IF NOT EXISTS idx_ncaaf_team ON ncaaf_team_stats(team, as_of_date);

-- Per-team per-game box score. Feeds rolling form + the ASOF stat rebuild.
-- No FK on game_id (the NFL precedent): the log covers every game a tracked
-- team plays, including FCS opponents that may never get a games row.
CREATE TABLE IF NOT EXISTS ncaaf_team_game_log (
    log_id             BIGSERIAL PRIMARY KEY,
    game_id            TEXT NOT NULL,
    team               TEXT NOT NULL,
    opponent           TEXT,
    season             INTEGER NOT NULL,
    week               INTEGER,
    season_type        TEXT,
    game_date          TEXT NOT NULL,
    is_home            INTEGER,
    is_neutral_site    INTEGER,
    is_conference_game INTEGER,
    points             INTEGER, points_allowed INTEGER,
    total_yards        INTEGER, rushing_yards INTEGER, passing_yards INTEGER,
    plays              INTEGER, possession_seconds INTEGER,
    first_downs        INTEGER,
    third_down_conv    INTEGER, third_down_att INTEGER,
    turnovers          INTEGER, penalties INTEGER, penalty_yards INTEGER,
    sacks              NUMERIC, tackles_for_loss NUMERIC,
    created_at         TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(team, game_id)
);
CREATE INDEX IF NOT EXISTS idx_ncaaf_glog_team ON ncaaf_team_game_log(team, game_date);
CREATE INDEX IF NOT EXISTS idx_ncaaf_glog_game ON ncaaf_team_game_log(game_id);

ALTER TABLE games ADD COLUMN IF NOT EXISTS week            INTEGER;
ALTER TABLE games ADD COLUMN IF NOT EXISTS neutral_site    INTEGER;
ALTER TABLE games ADD COLUMN IF NOT EXISTS conference_game INTEGER;

ALTER TABLE ncaaf_teams          ENABLE ROW LEVEL SECURITY;
ALTER TABLE ncaaf_team_stats     ENABLE ROW LEVEL SECURITY;
ALTER TABLE ncaaf_team_game_log  ENABLE ROW LEVEL SECURITY;
