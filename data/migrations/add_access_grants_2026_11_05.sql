-- Non-IAP premium. Ops/SQL only. Not in ACTIVE_MIGRATIONS: it references
-- auth.users, and the worker's SQLite adapter must not replay it.
--
-- Apply once, by hand, in the Supabase SQL editor for project
-- vvprgnrmzeekokzkrkfu (Betting Model), after review. Then run
-- scripts/grant_founder_comped_2026_11_05.sql. This file grants nobody.
--
-- App premium (my_access.entitled / has_app_access):
--   RevenueCat subscriptions row, status trialing or active, period open
--   OR an active access_grants row whose access_source is comped or app_review.
-- Whop stays discord_access and is not an input to entitled.
-- Discord invite (source 'comped', or an active subscription — not a trial):
--   discord_grant_access_for is comped only. app_review unlocks the app and
--   does not unlock Discord.

CREATE TABLE IF NOT EXISTS public.access_grants (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    access_source TEXT NOT NULL CHECK (access_source IN ('comped', 'app_review')),
    granted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at    TIMESTAMPTZ,
    notes         TEXT
);

CREATE INDEX IF NOT EXISTS access_grants_user_source_idx
    ON public.access_grants (user_id, access_source);

ALTER TABLE public.access_grants ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.access_grants FROM PUBLIC, anon, authenticated;
GRANT ALL ON TABLE public.access_grants TO service_role;

COMMENT ON TABLE public.access_grants IS
    'Non-IAP app access. comped and app_review unlock the app. comped also unlocks the subscriber Discord invite. Whop does not. Written by ops SQL, never by the app.';

-- Active comped or app_review grant. Indefinite when expires_at is null.
CREATE OR REPLACE FUNCTION public.app_grant_access_for(p_user_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.access_grants g
        WHERE g.user_id = p_user_id
          AND g.access_source IN ('comped', 'app_review')
          AND (g.expires_at IS NULL OR g.expires_at > NOW())
    );
$$;

-- Discord invite grant. comped only. A trial and app_review do not pass.
CREATE OR REPLACE FUNCTION public.discord_grant_access_for(p_user_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.access_grants g
        WHERE g.user_id = p_user_id
          AND g.access_source = 'comped'
          AND (g.expires_at IS NULL OR g.expires_at > NOW())
    );
$$;

-- Same return shape as add_discord_link_and_whop_memberships.sql so the app
-- and discord-link keep reading the row. source gains 'comped' and 'app_review'.
CREATE OR REPLACE FUNCTION public.my_access_for(p_user_id UUID)
RETURNS TABLE (
    entitled          BOOLEAN,
    source            TEXT,
    app_access        BOOLEAN,
    discord_access    BOOLEAN,
    discord_linked    BOOLEAN,
    discord_username  TEXT,
    guild_member      BOOLEAN,
    app_role_granted  BOOLEAN
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    rc BOOLEAN;
    comped BOOLEAN;
    whop BOOLEAN;
    app_ok BOOLEAN;
BEGIN
    IF p_user_id IS NULL THEN
        RETURN QUERY SELECT FALSE, 'none'::TEXT, FALSE, FALSE, FALSE,
                            NULL::TEXT, FALSE, FALSE;
        RETURN;
    END IF;

    rc := public.app_subscription_access_for(p_user_id);
    comped := public.discord_grant_access_for(p_user_id);
    whop := public.discord_access_for(p_user_id);
    app_ok := rc OR public.app_grant_access_for(p_user_id);

    -- entitled / app_access: RevenueCat subscription OR an active grant.
    -- whop is discord_access only. It is not an input to entitled.
    -- source 'comped' wins so a comped member gets the Discord invite even
    -- when a trial row is also present. 'app_review' unlocks the app only.
    RETURN QUERY
    SELECT app_ok,
           CASE WHEN comped THEN 'comped'
                WHEN rc AND whop THEN 'both'
                WHEN rc THEN 'app'
                WHEN app_ok THEN 'app_review'
                WHEN whop THEN 'discord'
                ELSE 'none' END,
           app_ok,
           whop,
           dl.user_id IS NOT NULL,
           dl.discord_username,
           COALESCE(dl.guild_member, FALSE),
           COALESCE(dl.app_role_granted, FALSE)
    FROM (SELECT p_user_id AS u) me
    LEFT JOIN discord_links dl ON dl.user_id = me.u;
END;
$$;

CREATE OR REPLACE FUNCTION public.has_app_access()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT auth.uid() IS NOT NULL
       AND (
            public.app_subscription_access_for(auth.uid())
         OR public.app_grant_access_for(auth.uid())
       );
$$;

REVOKE ALL ON FUNCTION public.app_grant_access_for(UUID)     FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.discord_grant_access_for(UUID) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.app_grant_access_for(UUID)     TO service_role;
GRANT EXECUTE ON FUNCTION public.discord_grant_access_for(UUID) TO service_role;

COMMENT ON FUNCTION public.my_access() IS
    'Caller access. entitled/app_access: RevenueCat subscription (trialing/active, period open) OR an active comped/app_review grant. discord_access: matched Whop membership, does not unlock the app. source comped also unlocks the Discord invite.';
COMMENT ON FUNCTION public.has_app_access() IS
    'App gate. RevenueCat subscription OR an active comped/app_review grant. A Whop membership does not pass.';
