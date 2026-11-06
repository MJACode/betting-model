-- Migration: add_sgp_price_observations_2026_11_06
-- Apply via Supabase MCP apply_migration (project ref vvprgnrmzeekokzkrkfu) or
-- the SQL editor. Not in ACTIVE_MIGRATIONS, the same as add_app_timings.sql.
--
-- Same-game parlay (SGP) prices the books actually quoted (Matt, 2026-11-06:
-- the betslip showed +5993 / FD +6040 for a 4-leg slip FanDuel priced at
-- +4254). A book prices legs from one game together and pays less than the
-- legs multiplied out; no feed we buy publishes that price. The app estimates
-- it as  multiplied price x (1 - cut) per same-game group, and a member who
-- sees the book's real price can enter it. Every entry lands here, and
-- sgp_haircuts() fits each book's cut from them.
--
-- One row = one slip at one book:
--   multiplied_decimal  what the app showed at that book BEFORE the cut
--                       (every leg's price at that book, multiplied out)
--   book_decimal        the price the book quoted for the whole slip
--   sgp_groups          how many games on the slip had 2+ legs
--   cut = 1 - (book_decimal / multiplied_decimal) ^ (1 / sgp_groups)
--
-- Trust model as app_timings: RLS on, no policies, no grants on the table.
-- In through log_sgp_price() (insert-only, returns nothing), out through
-- sgp_haircuts() (aggregates only, no device ids).

CREATE TABLE IF NOT EXISTS sgp_price_observations (
    id                  BIGSERIAL PRIMARY KEY,
    received_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    device_id           TEXT NOT NULL,
    book                TEXT NOT NULL,
    book_american       INTEGER NOT NULL,
    book_decimal        NUMERIC NOT NULL,
    multiplied_decimal  NUMERIC NOT NULL,
    sgp_groups          INTEGER NOT NULL CHECK (sgp_groups BETWEEN 1 AND 10),
    leg_count           INTEGER NOT NULL CHECK (leg_count BETWEEN 2 AND 25),
    legs                JSONB,               -- labels + game ids, for audit
    source              TEXT NOT NULL DEFAULT 'app',
    app_version         TEXT
);

CREATE INDEX IF NOT EXISTS idx_sgp_obs_book_received
    ON sgp_price_observations (book, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_sgp_obs_device_received
    ON sgp_price_observations (device_id, received_at DESC);

ALTER TABLE sgp_price_observations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE sgp_price_observations FROM anon, authenticated;
REVOKE ALL ON SEQUENCE sgp_price_observations_id_seq FROM anon, authenticated;

CREATE OR REPLACE FUNCTION public.log_sgp_price(
    p_device_id          TEXT,
    p_book               TEXT,
    p_book_american      INTEGER,
    p_multiplied_decimal NUMERIC,
    p_sgp_groups         INTEGER,
    p_leg_count          INTEGER,
    p_legs               JSONB DEFAULT NULL,
    p_app_version        TEXT DEFAULT NULL
) RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_recent   INT;
    v_decimal  NUMERIC;
    v_ratio    NUMERIC;
BEGIN
    IF p_device_id IS NULL OR length(btrim(p_device_id)) < 8 OR length(p_device_id) > 64 THEN
        RAISE EXCEPTION 'invalid device';
    END IF;
    IF p_book IS NULL OR p_book !~ '^[a-z0-9_]{2,32}$' THEN
        RAISE EXCEPTION 'invalid book';
    END IF;
    IF p_book_american IS NULL OR (p_book_american > -100 AND p_book_american < 100) THEN
        RAISE EXCEPTION 'invalid odds';
    END IF;
    IF p_multiplied_decimal IS NULL OR p_multiplied_decimal <= 1 THEN
        RAISE EXCEPTION 'invalid multiplied price';
    END IF;

    v_decimal := CASE WHEN p_book_american > 0
                      THEN 1 + p_book_american / 100.0
                      ELSE 1 + 100.0 / abs(p_book_american) END;
    -- A typo (one digit short or long) is not a price. Books pay less than the
    -- legs multiplied out on a same-game slip; allow a little above 1 for a
    -- negatively-correlated slip, nothing near 10x either way.
    v_ratio := v_decimal / p_multiplied_decimal;
    IF v_ratio < 0.2 OR v_ratio > 1.2 THEN
        RAISE EXCEPTION 'price out of range';
    END IF;

    -- Unauthenticated: bound what one install can write.
    SELECT count(*) INTO v_recent
      FROM sgp_price_observations
     WHERE device_id = p_device_id
       AND received_at > now() - interval '1 day';
    IF v_recent >= 50 THEN
        RETURN;
    END IF;

    INSERT INTO sgp_price_observations
        (device_id, book, book_american, book_decimal, multiplied_decimal,
         sgp_groups, leg_count, legs, app_version)
    VALUES
        (p_device_id, p_book, p_book_american, v_decimal, p_multiplied_decimal,
         p_sgp_groups, p_leg_count, p_legs, p_app_version);
END;
$$;

-- Each book's fitted cut per same-game group, over the last 120 days.
-- ONE VOTE PER DEVICE (PR #1198 review M2): device_id is client-supplied on an
-- anonymous insert, so each install's entries collapse to that install's own
-- median first, and the book's cut is the median of those. n is the number of
-- DISTINCT devices, which is what the app's minimum counts — one install
-- entering 50 prices a day is one vote, not fifty.
CREATE OR REPLACE FUNCTION public.sgp_haircuts()
RETURNS TABLE (book TEXT, haircut NUMERIC, n BIGINT)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    WITH per_device AS (
        SELECT o.book,
               o.device_id,
               percentile_cont(0.5) WITHIN GROUP (
                   ORDER BY 1 - power(o.book_decimal / o.multiplied_decimal, 1.0 / o.sgp_groups)
               ) AS cut
          FROM sgp_price_observations o
         WHERE o.received_at > now() - interval '120 days'
         GROUP BY o.book, o.device_id
    )
    SELECT d.book,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY d.cut)::NUMERIC AS haircut,
           count(*) AS n
      FROM per_device d
     GROUP BY d.book;
$$;

REVOKE ALL ON FUNCTION public.log_sgp_price(TEXT, TEXT, INTEGER, NUMERIC, INTEGER, INTEGER, JSONB, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.sgp_haircuts() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.log_sgp_price(TEXT, TEXT, INTEGER, NUMERIC, INTEGER, INTEGER, JSONB, TEXT) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.sgp_haircuts() TO anon, authenticated;

-- The first observation: Matt's screenshots, 2026-11-06. The app's FanDuel
-- tile showed +6040 (legs multiplied, 61.40) for MIA@GSW Lendeborg O24.5 pts +
-- Klay O3.5 3PM and ORL@PHX Booker O29.5 pts + Carter O9.5 reb; FanDuel's own
-- slip priced the same four legs +4254 as two same-game parlays.
INSERT INTO sgp_price_observations
    (device_id, book, book_american, book_decimal, multiplied_decimal,
     sgp_groups, leg_count, legs, source)
SELECT 'seed-matt-2026-11-06', 'fanduel', 4254, 43.54, 61.40, 2, 4,
       '[{"label":"Yaxel Lendeborg Over 24.5 Points","game":"MIA@GSW"},
         {"label":"Klay Thompson Over 3.5 3PM","game":"MIA@GSW"},
         {"label":"Devin Booker Over 29.5 Points","game":"ORL@PHX"},
         {"label":"Wendell Carter Jr Over 9.5 Rebounds","game":"ORL@PHX"}]'::jsonb,
       'screenshot'
WHERE NOT EXISTS (
    SELECT 1 FROM sgp_price_observations WHERE device_id = 'seed-matt-2026-11-06'
);
