-- ─────────────────────────────────────────────────────────────────────────────
-- Discord account linking + Whop membership mirror + unified access resolution
--
-- Ships the two-way membership rule:
--   * pay in the app (App Store / RevenueCat)  -> get the Discord subscriber role
--   * pay via Discord (Whop)                   -> get the app at no extra cost
--   * lose access on either side               -> lose it on the other
--
-- THE ROLE IS THE ENTITLEMENT CARRIER ON THE DISCORD SIDE, and each side only
-- ever revokes the role IT granted. Whop assigns its own role
-- (DISCORD_WHOP_ROLE_ID); we assign ours (DISCORD_APP_ROLE_ID). A lapsed app
-- subscription therefore cannot strip a member who is still paying Whop, and
-- vice versa. `discord_links.app_role_granted` records that OUR role is on, so
-- revocation never guesses.
--
-- Nothing here is reachable while the mobile flags are dark
-- (AUTH_ENABLED / BILLING_ENABLED / DISCORD_LINK_ENABLED) — the tables are
-- written only by the Edge Functions running as service role.
--
-- Apply once:  psql "$DATABASE_URL" -f data/migrations/add_discord_link_and_whop_memberships.sql
-- Runbook:     mobile/docs/DISCORD_LINKING.md
-- ─────────────────────────────────────────────────────────────────────────────

-- ── 1. Identity: app account <-> Discord account ─────────────────────────────
-- One row per app user, and one Discord account can back at most one app
-- account (the UNIQUE constraint is the anti-sharing rule: without it a single
-- paying Discord member could hand free access to unlimited app accounts).
CREATE TABLE IF NOT EXISTS discord_links (
    user_id                UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    discord_user_id        TEXT NOT NULL UNIQUE,
    discord_username       TEXT,
    discord_avatar         TEXT,
    -- Email as Discord reports it, plus Discord's own verification flag. Only
    -- a VERIFIED email is ever used to auto-match a Whop membership — an
    -- unverified one is attacker-chosen and would be a free-access exploit.
    discord_email          TEXT,
    discord_email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    -- Did the guilds.join call succeed (or were they already in the server)?
    guild_member           BOOLEAN NOT NULL DEFAULT FALSE,
    -- TRUE only while WE hold the app-subscriber role on this member. The
    -- revocation guard described above.
    app_role_granted       BOOLEAN NOT NULL DEFAULT FALSE,
    last_synced_at         TIMESTAMPTZ,
    last_sync_error        TEXT,
    linked_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_discord_links_discord_user
    ON discord_links (discord_user_id);
CREATE INDEX IF NOT EXISTS idx_discord_links_email
    ON discord_links (lower(discord_email))
    WHERE discord_email IS NOT NULL AND discord_email_verified;

-- ── 2. Whop membership mirror ────────────────────────────────────────────────
-- Keyed on the Whop membership id, NOT on a Discord id: a membership exists
-- from the moment it is paid for, which is before the buyer has connected
-- Discord (or ever signs into the app). Both `discord_user_id` and `email` are
-- nullable and both are match keys, so a member resolves by whichever identity
-- we learn first.
CREATE TABLE IF NOT EXISTS whop_memberships (
    membership_id      TEXT PRIMARY KEY,
    whop_user_id       TEXT,
    discord_user_id    TEXT,
    email              TEXT,
    product_id         TEXT,
    plan_id            TEXT,
    -- Whop's own vocabulary, stored verbatim for debuggability.
    status             TEXT NOT NULL,
    -- Whop's `valid` boolean is the authoritative "does this grant access"
    -- flag — it already accounts for trials, grace periods and cancellations
    -- that run to period end. We do NOT re-derive it from `status`.
    valid              BOOLEAN NOT NULL DEFAULT FALSE,
    renewal_period_end TIMESTAMPTZ,
    -- Whole payload of the last event, so a field rename upstream is a
    -- localized fix rather than lost history.
    raw                JSONB,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_whop_memberships_discord
    ON whop_memberships (discord_user_id) WHERE discord_user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_whop_memberships_email
    ON whop_memberships (lower(email)) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_whop_memberships_valid
    ON whop_memberships (valid) WHERE valid;

-- ── 3. RLS ───────────────────────────────────────────────────────────────────
-- Users may read their OWN link row (the Settings card shows which Discord
-- account is connected). Nobody reads whop_memberships directly — it carries
-- other people's emails, so the app only ever sees the boolean that falls out
-- of my_access() below.
ALTER TABLE discord_links     ENABLE ROW LEVEL SECURITY;
ALTER TABLE whop_memberships  ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users read own discord link" ON discord_links;
CREATE POLICY "users read own discord link" ON discord_links
    FOR SELECT TO authenticated USING (auth.uid() = user_id);

-- Supabase's default privileges over-grant anon/authenticated on every new
-- public table, and `REVOKE ... FROM PUBLIC` does not undo it. Revoke BY NAME
-- (the session-113 lesson, promoted into CLAUDE.md §7).
REVOKE ALL ON TABLE discord_links    FROM anon, authenticated;
REVOKE ALL ON TABLE whop_memberships FROM anon, authenticated;
GRANT SELECT ON TABLE discord_links TO authenticated;

-- ── 4. Access resolution ─────────────────────────────────────────────────────
-- The one place the two-way rule is expressed. Everything else (the app, the
-- Edge Functions, any future server-side gating) calls these.

-- Is there a valid Whop membership behind this app user?
--
-- Two match keys, both of which must be evidence the user actually controls:
--   1. The linked Discord account id — explicit, consented, and unique per app
--      account.
--   2. Their VERIFIED email, on both sides. Supabase only populates
--      auth.users.email_confirmed_at after the OTP round trip, and Whop bills
--      the address it holds, so a match means the same mailbox paid.
-- An unverified address on either side matches nothing.
CREATE OR REPLACE FUNCTION public.discord_access_for(p_user_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, auth
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM whop_memberships w
        WHERE w.valid
          AND (
                -- (1) the Discord account this app user explicitly linked
                (w.discord_user_id IS NOT NULL
                 AND w.discord_user_id = (
                     SELECT dl.discord_user_id FROM discord_links dl
                     WHERE dl.user_id = p_user_id
                 ))
                -- (2) the app account's own confirmed email
             OR (w.email IS NOT NULL
                 AND lower(w.email) = (
                     SELECT lower(u.email) FROM auth.users u
                     WHERE u.id = p_user_id AND u.email_confirmed_at IS NOT NULL
                 ))
                -- (3) the linked Discord account's Discord-verified email
             OR (w.email IS NOT NULL
                 AND lower(w.email) = (
                     SELECT lower(dl.discord_email) FROM discord_links dl
                     WHERE dl.user_id = p_user_id AND dl.discord_email_verified
                 ))
          )
    );
$$;

-- Does the app-side subscription entitle right now?
-- Mirrors mobile/src/lib/billingHelpers.ts::isEntitled — status AND period end,
-- because an `active` row whose period lapsed (missed webhook) must not grant
-- access forever. NULL period end entitles: that is a row written before the
-- webhook filled it in, and locking out a just-paid user is the worse failure.
CREATE OR REPLACE FUNCTION public.app_subscription_access_for(p_user_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1 FROM subscriptions s
        WHERE s.user_id = p_user_id
          AND s.status IN ('trialing', 'active')
          AND (s.current_period_end IS NULL OR s.current_period_end > NOW())
    );
$$;

-- The whole access picture for ONE user. Takes a user id, so it is
-- service-role only — the Edge Functions call it after a link or a webhook,
-- where there is no auth.uid() to read. The app never gets EXECUTE on it;
-- my_access() below is the auth.uid()-pinned wrapper it does get, which is
-- what stops it being used to enumerate who is subscribed.
DROP FUNCTION IF EXISTS public.my_access_for(UUID);
CREATE FUNCTION public.my_access_for(p_user_id UUID)
RETURNS TABLE (
    entitled          BOOLEAN,
    source            TEXT,     -- 'app' | 'discord' | 'both' | 'none'
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
    a BOOLEAN;
    d BOOLEAN;
BEGIN
    IF p_user_id IS NULL THEN
        RETURN QUERY SELECT FALSE, 'none'::TEXT, FALSE, FALSE, FALSE,
                            NULL::TEXT, FALSE, FALSE;
        RETURN;
    END IF;

    a := public.app_subscription_access_for(p_user_id);
    d := public.discord_access_for(p_user_id);

    RETURN QUERY
    SELECT (a OR d),
           CASE WHEN a AND d THEN 'both'
                WHEN a THEN 'app'
                WHEN d THEN 'discord'
                ELSE 'none' END,
           a,
           d,
           dl.user_id IS NOT NULL,
           dl.discord_username,
           COALESCE(dl.guild_member, FALSE),
           COALESCE(dl.app_role_granted, FALSE)
    FROM (SELECT p_user_id AS u) me
    LEFT JOIN discord_links dl ON dl.user_id = me.u;
END;
$$;

-- The single read the app makes: my_access_for(), pinned to the caller. It
-- cannot be pointed at anyone else's account.
DROP FUNCTION IF EXISTS public.my_access();
CREATE FUNCTION public.my_access()
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
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT * FROM public.my_access_for(auth.uid());
$$;

-- Replaces has_active_subscription() as the honest gate for any future
-- server-side signal gating: a Whop member is entitled without a
-- `subscriptions` row, so a check that reads only that table would lock out
-- everybody who paid through Discord.
CREATE OR REPLACE FUNCTION public.has_app_access()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT auth.uid() IS NOT NULL
       AND (public.app_subscription_access_for(auth.uid())
            OR public.discord_access_for(auth.uid()));
$$;

-- SECURITY DEFINER + default EXECUTE-to-PUBLIC is the combination that leaked
-- before. Revoke by name, then grant only what the app needs.
REVOKE ALL ON FUNCTION public.discord_access_for(UUID)         FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.app_subscription_access_for(UUID) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.my_access()                      FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.my_access_for(UUID)              FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.has_app_access()                 FROM PUBLIC, anon, authenticated;

-- Every *_for(uuid) function takes an arbitrary user id, so all three stay
-- service-role only. The app calls the two zero-argument functions, which are
-- pinned to auth.uid().
GRANT EXECUTE ON FUNCTION public.my_access()      TO authenticated;
GRANT EXECUTE ON FUNCTION public.has_app_access() TO authenticated;

-- The Edge Functions run as service_role and call my_access_for() directly:
-- there is no auth.uid() in a webhook, so the auth.uid()-pinned wrapper is no
-- use to them. Granted explicitly rather than relying on the default
-- privileges the REVOKEs above just stripped.
GRANT EXECUTE ON FUNCTION public.my_access_for(UUID)             TO service_role;
GRANT EXECUTE ON FUNCTION public.discord_access_for(UUID)        TO service_role;
GRANT EXECUTE ON FUNCTION public.app_subscription_access_for(UUID) TO service_role;
GRANT EXECUTE ON FUNCTION public.my_access()                     TO service_role;
GRANT EXECUTE ON FUNCTION public.has_app_access()                TO service_role;
GRANT ALL ON TABLE discord_links    TO service_role;
GRANT ALL ON TABLE whop_memberships TO service_role;

COMMENT ON TABLE discord_links IS
    'App account <-> Discord account. Written only by the discord-link Edge Function (service role).';
COMMENT ON TABLE whop_memberships IS
    'Mirror of Whop membership state, written only by the whop-webhook Edge Function (service role).';
COMMENT ON FUNCTION public.my_access() IS
    'The caller''s full access picture: app subscription OR Discord (Whop) membership.';
