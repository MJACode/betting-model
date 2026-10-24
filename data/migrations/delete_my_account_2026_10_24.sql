-- Delete the signed-in account. Apple requires this once sign-in exists.
--
-- UNAPPLIED. This file is NOT in data/view_migrations.ACTIVE_MIGRATIONS.
-- The worker must not run it. Nothing here has been applied to production.
-- Matt applies it in the Supabase SQL editor (role postgres, which can
-- delete auth.users). Do not put it in ACTIVE_MIGRATIONS until that is done.
-- One file, two functions. Run the whole file.
--
-- ORDER. delete_my_account() removes the caller's saved rows and leaves the
-- login in place. The app then revokes Discord and SharpSports. Those calls
-- need the user row: Discord's unlink reads auth.getUser() and the
-- discord_links row, and drops the link only after the role comes off.
-- delete_my_login() then deletes auth.users. A failed unlink does not call
-- delete_my_login(), so the links stay and a retry can still revoke them.
-- The phone clock does not gate either call. A failed RPC or a cancelled
-- re-auth leaves every link intact, because unlink runs only after
-- delete_my_account() has committed.
--
-- STALE SESSION. Each function deletes nothing unless auth.uid() is set AND
-- auth.users.last_sign_in_at for that user is within the last 10 minutes.
-- Token refresh does not move last_sign_in_at, so a long-lived session is
-- stale on purpose. Both failures raise SQLSTATE 28000 with message
-- STALE_SESSION. The app maps that code, and a rejected JWT (PostgREST
-- PGRST301, which never reaches these functions), to the re-auth sheet.
-- A fresh sign-in updates last_sign_in_at, and the app retries.
--
-- OWN DATA ONLY. Every delete is filtered on auth.uid() (v_uid). There is
-- no user-id argument. The public model record is not touched: picks,
-- results, opening signals, the track record, games. whop_memberships is
-- not touched either — it is not keyed by auth.uid(), and deleting it
-- would not cancel the Whop charge. The member cancels where they bought
-- it. Deleting public.subscriptions removes OUR row only. It does not
-- call Apple, Google, Stripe, or Whop.
--
-- auth.users cascades identities, sessions, refresh tokens, and
-- discord_links. delete_my_login() is the only delete of auth.users.
-- discord_links is not deleted here: unlink drops it after the role is
-- gone, and the cascade is the backstop when Discord linking is off.
-- subscriptions is deleted in delete_my_account() so a later dropped
-- foreign key cannot leave OUR row.
--
-- Device-scoped rows (tracked_bets, linked_sportsbook_accounts, synced_bets,
-- device_push_tokens, app_errors, member_sportsbooks owner_key device:…)
-- are not deleted here. They are not keyed by auth.uid(). The app clears
-- this install's tracked_bets, unregisters its push token, and rewrites the
-- device sportsbooks row to every book after the local sign-out (so this
-- function's user: delete is not recreated).

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
  DELETE FROM public.subscriptions WHERE user_id = v_uid;
END;
$fn$;

REVOKE ALL ON FUNCTION public.delete_my_account() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.delete_my_account() FROM anon;
GRANT EXECUTE ON FUNCTION public.delete_my_account() TO authenticated;

-- The login only. Called after Discord and SharpSports have been unlinked.
-- Same 10-minute rule as delete_my_account(). Cascades discord_links when
-- unlink did not already delete that row.

CREATE OR REPLACE FUNCTION public.delete_my_login()
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

  DELETE FROM auth.users WHERE id = v_uid;
END;
$fn$;

REVOKE ALL ON FUNCTION public.delete_my_login() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.delete_my_login() FROM anon;
GRANT EXECUTE ON FUNCTION public.delete_my_login() TO authenticated;
