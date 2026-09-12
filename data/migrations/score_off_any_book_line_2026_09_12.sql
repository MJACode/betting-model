-- A proposition DraftKings does not list is still a proposition.
--
-- mike, 2026-09-12: "Yes, scoring of other books lines."
--
-- Until now a player prop with no DraftKings quote produced no pick at all,
-- however many bettable books priced it. Measured over the markets an ACTIVE
-- model prices, 2026-08-28 onward: DraftKings listed 11,780 player
-- propositions and the bettable books listed 1,357 more that it did not.
--
-- `picks.line_book` names the book whose LINE the pick was scored off; NULL
-- means DraftKings, which is every row written before today. The price such a
-- pick was decided at is already in decision_* (2026-09-09), and dk_odds /
-- dk_implied_prob / edge stay NULL / 0.0 on these rows because DraftKings
-- never quoted the proposition.
--
-- Two things this has to fix beyond the column:
--   1. the audit trigger must copy it, or a restored first signal forgets
--      which book set the number;
--   2. the PUBLISHED record gates its units on `p.dk_odds IS NOT NULL`
--      (require_price_for_published_units.sql, 2026-09-03, which exists
--      because settlement fabricates -110 for a pick with no price). That
--      gate now reads the DECIDING price: a pick scored off FanDuel's line
--      and settled at FanDuel's price has a real price and real units, and
--      leaving the gate on dk_odds would have bet it and never counted it.
--      The fabrication it guards against is unchanged -- COALESCE is NULL
--      only when no book priced the pick at all.
--
-- IDEMPOTENT: every step is guarded on the property it establishes, so the
-- view-migration runner can execute this on every pipeline pass.

DO $mig$
DECLARE
  d text;
  v text;
  dk_profit CONSTANT text :=
    'COALESCE(sum(p.profit_flat) FILTER (WHERE (p.result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])) AND p.dk_odds IS NOT NULL), 0::numeric)';
  new_profit CONSTANT text :=
    'COALESCE(sum(p.profit_flat) FILTER (WHERE (p.result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])) AND COALESCE(p.decision_odds, p.dk_odds) IS NOT NULL), 0::numeric)';
  dk_stake CONSTANT text :=
    '100 * count(*) FILTER (WHERE (p.result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])) AND p.dk_odds IS NOT NULL) AS staked_flat';
  new_stake CONSTANT text :=
    '100 * count(*) FILTER (WHERE (p.result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])) AND COALESCE(p.decision_odds, p.dk_odds) IS NOT NULL) AS staked_flat';
BEGIN
  -- ── 1. the column, on the table and its audit log ────────────────────────
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                  WHERE table_schema = 'public' AND table_name = 'picks'
                    AND column_name = 'line_book') THEN
    ALTER TABLE public.picks ADD COLUMN line_book TEXT;
    RAISE NOTICE 'picks: line_book added';
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                  WHERE table_schema = 'public' AND table_name = 'picks_log'
                    AND column_name = 'line_book') THEN
    ALTER TABLE public.picks_log ADD COLUMN line_book TEXT;
    RAISE NOTICE 'picks_log: line_book added';
  END IF;

  -- ── 2. the audit trigger copies it ───────────────────────────────────────
  SELECT p.prosrc INTO d FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'public' AND p.proname = 'log_picks_changes';
  IF d IS NULL OR position('line_book' in d) = 0 THEN
    EXECUTE $fn$
      CREATE OR REPLACE FUNCTION public.log_picks_changes()
       RETURNS trigger
       LANGUAGE plpgsql
       SET search_path TO 'public', 'pg_catalog'
      AS $body$
      DECLARE
        r picks%ROWTYPE;
      BEGIN
        IF TG_OP = 'DELETE' THEN
          r := OLD;
        ELSE
          r := NEW;
        END IF;

        INSERT INTO picks_log (
          logged_at, operation, pick_id, game_id, model_id, sport, game_date, game_time, run_time,
          pick_side, pick_label, model_probability, dk_implied_prob, edge, dk_odds, scored_line,
          kelly_fraction, recommended_bet, bankroll_at_pick, injury_flag, injury_detail,
          signal_type, confidence_tier, result, profit_flat, profit_kelly, settled_at, created_at,
          decision_book, decision_odds, decision_implied_prob, decision_edge, line_book
        ) VALUES (
          NOW(), TG_OP, r.pick_id, r.game_id, r.model_id, r.sport, r.game_date, r.game_time, r.run_time,
          r.pick_side, r.pick_label, r.model_probability, r.dk_implied_prob, r.edge, r.dk_odds, r.scored_line,
          r.kelly_fraction, r.recommended_bet, r.bankroll_at_pick, r.injury_flag, r.injury_detail,
          r.signal_type, r.confidence_tier, r.result, r.profit_flat, r.profit_kelly, r.settled_at, r.created_at,
          r.decision_book, r.decision_odds, r.decision_implied_prob, r.decision_edge, r.line_book
        );

        RETURN r;
      END;
      $body$
    $fn$;
    RAISE NOTICE 'log_picks_changes now copies line_book';
  END IF;

  -- ── 3. published units gate on the DECIDING price ────────────────────────
  FOREACH v IN ARRAY ARRAY['v_public_track_record', 'v_public_track_record_daily'] LOOP
    d := pg_get_viewdef(('public.' || v)::regclass, true);

    IF position(new_profit in d) > 0 THEN
      CONTINUE;                          -- already reading the deciding price
    END IF;

    IF position(dk_profit in d) = 0 THEN
      RAISE EXCEPTION '%: the DraftKings-only units gate is not present in the '
                      'shape require_price_for_published_units.sql leaves — '
                      're-derive both files together', v;
    END IF;

    d := replace(d, dk_profit, new_profit);
    d := replace(d, dk_stake,  new_stake);
    EXECUTE format('CREATE OR REPLACE VIEW public.%I AS %s', v, d);
    -- security_invoker survives CREATE OR REPLACE; re-asserted so a reviewer
    -- does not have to check.
    EXECUTE format('ALTER VIEW public.%I SET (security_invoker = on)', v);
    RAISE NOTICE '%: published units now gate on COALESCE(decision_odds, dk_odds)', v;
  END LOOP;
END $mig$;
