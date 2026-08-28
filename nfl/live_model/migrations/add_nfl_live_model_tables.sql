/* NFL live (in-play) model: raw captures and the decision trail.
 *
 * Two append-only capture tables plus reuse of `picks` for decisions.
 *
 * RLS is ENABLED WITH NO POLICY on both tables, which is this repo's
 * established shape for pipeline-internal data (nhl_team_stats,
 * nfl_team_game_stats, ncaaf_team_stats and about two dozen others). The
 * worker writes as the table owner via DATABASE_URL and owners bypass RLS;
 * the anon key, which ships inside the mobile bundle and is publicly
 * extractable, gets nothing. Grants are revoked from anon and authenticated
 * BY NAME rather than from PUBLIC, because Supabase default privileges grant
 * on new public objects by role name and a PUBLIC-only revoke is a no-op.
 * That exact hole was found live in session 126c and again in session 127.
 */

CREATE TABLE IF NOT EXISTS public.live_game_states (
  game_id   text        NOT NULL,
  ts        timestamptz NOT NULL,
  state     jsonb       NOT NULL,
  PRIMARY KEY (game_id, ts)
);

CREATE TABLE IF NOT EXISTS public.live_odds_snapshots (
  game_id    text        NOT NULL,
  ts         timestamptz NOT NULL,
  bookmaker  text        NOT NULL,
  market     text        NOT NULL,
  payload    jsonb       NOT NULL,
  PRIMARY KEY (game_id, ts, bookmaker, market)
);

CREATE INDEX IF NOT EXISTS live_game_states_ts_idx
  ON public.live_game_states (ts DESC);
CREATE INDEX IF NOT EXISTS live_odds_snapshots_game_ts_idx
  ON public.live_odds_snapshots (game_id, ts DESC);

ALTER TABLE public.live_game_states     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.live_odds_snapshots  ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.live_game_states    FROM anon, authenticated;
REVOKE ALL ON public.live_odds_snapshots FROM anon, authenticated;

/* Decisions reuse `picks`. Every live NFL pick carries is_live = TRUE and a
 * model_id in the four lanes, and thresholds live in model_action_thresholds
 * exactly like every other model, so the app's action filter and the
 * track-record views need no special case. The daily picks query already
 * excludes is_live rows by design.
 *
 * state_ref and quote_ref point back at the two capture tables so any decision
 * can be fully reconstructed afterwards: which state we saw, and which quote
 * we saw it against. Without them a post mortem on a bad bet is guesswork. */
ALTER TABLE public.picks
  ADD COLUMN IF NOT EXISTS state_ref timestamptz,
  ADD COLUMN IF NOT EXISTS quote_ref timestamptz;

COMMENT ON COLUMN public.picks.state_ref IS
  'live models: timestamp of the live_game_states row this pick was priced from';
COMMENT ON COLUMN public.picks.quote_ref IS
  'live models: timestamp of the live_odds_snapshots row this pick was priced against';
