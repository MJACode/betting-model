-- Undo for premium_gate_matview_2026_11_20.sql. HAND APPLIED. Not in
-- ACTIVE_MIGRATIONS. Remove premium_gate_matview_2026_11_20.sql from
-- ACTIVE_MIGRATIONS first, or the worker sets the hook again on its next pass.
-- PostgREST stops calling the pre-request function; the function is left in
-- place (harmless when nothing calls it).
ALTER ROLE authenticator RESET pgrst.db_pre_request;
NOTIFY pgrst, 'reload config';
