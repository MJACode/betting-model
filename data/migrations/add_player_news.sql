-- Recent player news, one row per (source item, player).
--
-- Powers the "Recent News" sheet the prop screens open from their top-right
-- newspaper icon: a prop is a bet on ONE player, so "is he hurt / did he just
-- get skipped in the rotation / is he on a pitch count" is the single most
-- decision-relevant thing we were not showing next to the number.
--
-- Provider-agnostic by construction. `source` names who wrote the item ('espn'
-- today; a licensed fantasy-notes feed such as RotoWire/RotoBaller/SportsDataIO
-- drops in behind the same table), and `analysis` is the fantasy-note "ANALYSIS"
-- paragraph those feeds carry and ESPN does not -- nullable, and the sheet just
-- omits the block when it is absent.
--
-- Keyed twice on purpose. `player_id` is OUR id (the one on picks and the game
-- logs) and is NULL when the feed names a player we have never logged;
-- `player_key` is the normalized name (data/name_match.normalize_player_name)
-- and is always present, so the app can resolve a player the id join misses --
-- the accented-name gap that cost ~9% of every MLB slate is exactly this.
--
-- Retention: the ingestor prunes past config.PLAYER_NEWS_RETENTION_DAYS. A note
-- older than that is history, not news, and this table is a cache of a feed we
-- can always re-read -- nothing here is irreplaceable paid data.
DO $$
BEGIN
  IF to_regclass('public.player_news') IS NULL THEN
    CREATE TABLE public.player_news (
      news_id        BIGSERIAL PRIMARY KEY,
      sport          TEXT NOT NULL,
      -- Our player id when the name resolved against the sport's game log.
      player_id      TEXT,
      player_name    TEXT NOT NULL,
      -- normalize_player_name(player_name) -- the join the app falls back to.
      player_key     TEXT NOT NULL,
      team           TEXT,
      source         TEXT NOT NULL,
      -- The provider's own id for the item, so a re-read updates in place
      -- instead of duplicating.
      source_item_id TEXT NOT NULL,
      published_at   TIMESTAMPTZ NOT NULL,
      headline       TEXT NOT NULL,
      body           TEXT,
      -- Fantasy-note "ANALYSIS" paragraph. NULL for feeds that have none.
      analysis       TEXT,
      url            TEXT,
      ingested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    -- One item can name several players (a game recap mentions six), so the
    -- item id alone is not unique -- the player is part of the key.
    CREATE UNIQUE INDEX player_news_item_player
      ON public.player_news (source, source_item_id, player_key);
    CREATE INDEX player_news_by_id
      ON public.player_news (sport, player_id, published_at DESC);
    CREATE INDEX player_news_by_key
      ON public.player_news (sport, player_key, published_at DESC);
    CREATE INDEX player_news_published
      ON public.player_news (published_at DESC);

    -- Written by the pipeline as the table owner; read by the app's anon key.
    -- REVOKE names anon/authenticated rather than PUBLIC: Supabase's default
    -- privileges grant them BY NAME, so a PUBLIC-only revoke is a no-op.
    ALTER TABLE public.player_news ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.player_news FROM anon, authenticated;
    REVOKE ALL ON SEQUENCE public.player_news_news_id_seq FROM anon, authenticated;
    GRANT SELECT ON public.player_news TO anon, authenticated;
    CREATE POLICY "anon read player_news"
      ON public.player_news FOR SELECT TO anon, authenticated USING (true);
  END IF;
END $$;
