-- Delete the signed-in account. Apple requires this once sign-in exists.
--
-- UNAPPLIED. This file is NOT in data/view_migrations.ACTIVE_MIGRATIONS.
-- The worker must not run it. Nothing here has been applied to production.
-- Matt applies it in the Supabase SQL editor (role postgres, which can
-- delete auth.users). Do not put it in ACTIVE_MIGRATIONS until that is done.
--
-- STALE SESSION. A call deletes nothing unless auth.uid() is set AND
-- auth.users.last_sign_in_at for that user is within the last 10 minutes.
-- Token refresh does not move last_sign_in_at, so a long-lived session is
-- stale on purpose. Both failures raise SQLSTATE 28000 with message
-- STALE_SESSION. The app maps that code, and a rejected JWT (PostgREST
-- PGRST301, which never reaches this function), to the re-auth sheet.
-- A fresh sign-in updates last_sign_in_at, and the app retries this call
-- without asking again.
--
-- OWN DATA ONLY. Every delete is filtered on auth.uid() (v_uid). There is
-- no user-id argument. The public model record is not touched: picks,
-- results, opening signals, the track record, games. whop_memberships is
-- not touched either — it is not keyed by auth.uid(), and deleting it
-- would not cancel the Whop charge. The member cancels where they bought
-- it. Deleting public.subscriptions removes OUR row only. It does not
-- call Apple, Google, Stripe, or Whop.
--
-- auth.users cascades identities, sessions, and refresh tokens. discord_links
-- and subscriptions also reference auth.users ON DELETE CASCADE; they are
-- deleted explicitly first so a later dropped foreign key cannot leave them.
--
-- Device-scoped rows (tracked_bets, linked_sportsbook_accounts, synced_bets,
-- device_push_tokens, app_errors, member_sportsbooks owner_key device:…)
-- are not deleted here. They are not keyed by auth.uid(). The app clears
-- this install's tracked_bets and asks the sharpsports function to unlink
-- this install. The device: sportsbooks row stays so the phone can keep
-- being used without an account.

CREATE OR REPLACE FUNCTION public.delete_my_account()
RETURNS void
LANGUAGE plpgsql
VOLATILE
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $fn$
DECLARE
  v_uid uuid := auth.uid();
  v_last timestamptz;
BEGIN
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'STALE_SESSION'
      USING ERRCODE = '28000',
            DETAIL = 'Sign in again before deleting this account.';
  END IF;

  SELECT u.last_sign_in_at
    INTO v_last
    FROM auth.users AS u
   WHERE u.id = v_uid;

  IF v_last IS NULL OR v_last < now() - interval '10 minutes' THEN
    RAISE EXCEPTION 'STALE_SESSION'
      USING ERRCODE = '28000',
            DETAIL = 'Sign in again before deleting this account.';
  END IF;

  DELETE FROM public.byom_model_snapshots WHERE user_id = v_uid;
  DELETE FROM public.byom_models WHERE user_id = v_uid;
  DELETE FROM public.feedback_messages WHERE thread_id IN (SELECT id FROM public.feedback_threads WHERE user_id = v_uid);
  DELETE FROM public.feedback_threads WHERE user_id = v_uid;
  DELETE FROM public.member_sportsbooks WHERE owner_key = 'user:' || v_uid::text;
  DELETE FROM public.discord_links WHERE user_id = v_uid;
  DELETE FROM public.subscriptions WHERE user_id = v_uid;
  DELETE FROM auth.users WHERE id = v_uid;
END;
$fn$;

REVOKE ALL ON FUNCTION public.delete_my_account() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.delete_my_account() FROM anon;
GRANT EXECUTE ON FUNCTION public.delete_my_account() TO authenticated;
