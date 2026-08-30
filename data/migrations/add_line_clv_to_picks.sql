-- Line CLV: measure the CLOSE even when the number moved.
--
-- CLV has always been a PRICE comparison, and a price comparison is only valid
-- across the SAME proposition -- Over 44.5 at -110 and Over 46.5 at -110 are
-- different bets. So `_capture_clv` skipped any pick whose line had moved by
-- close, which is ~55% of settled pre-game bets. Two consequences:
--
--   1. The published beat-the-close rate spoke for under half the book.
--   2. `closing_line` was only ever written when it EQUALLED `scored_line`, so
--      the "Line 44.5 -> 46.5" row in the app's Closing Line Value card could
--      never render -- its own `scored_line !== closing_line` condition was
--      unreachable. The one thing a user most wants to see (the number we gave
--      them vs the number the market closed at) was structurally invisible.
--
-- This adds the measure that IS valid across a moved line: how far the NUMBER
-- moved toward our side, in points. It is the same idea the NFL card models use
-- (markets.ts isNflLineOnly / computeMovement lineOnly), generalised.
--
--   line_clv_pts    points the line moved in OUR favour between signal and
--                   close, signed from the pick's side. Over 44.5 closing 46.5
--                   is +2.0 (we needed less); Under 46.5 closing 44.5 is +2.0;
--                   home -3.5 closing -5.5 is +2.0. NULL for moneyline, which
--                   has no line to move.
--   clv_beat_close  the single verdict, whichever measure applies:
--                   the line moved  -> line_clv_pts > 0
--                   the line held   -> clv_pct > 0
--                   Stored rather than derived so a consumer cannot silently
--                   pick the wrong one of the two.
--
-- clv_pct KEEPS ITS EXACT MEANING and stays same-line-only. The number already
-- published does not move; this is strictly additive.
--
-- Idempotency note: `_capture_clv` / `_backfill_clv` now gate on
-- `clv_captured_at IS NULL` rather than `clv_pct IS NULL`, because a moved-line
-- pick is now captured WITHOUT a clv_pct and would otherwise be re-processed on
-- every settle forever. Verified before shipping: clv_pct and clv_captured_at
-- were 1:1 across all 1,795 captured picks, so the gate change is a no-op on
-- existing rows.

ALTER TABLE picks ADD COLUMN IF NOT EXISTS line_clv_pts   NUMERIC;
ALTER TABLE picks ADD COLUMN IF NOT EXISTS clv_beat_close BOOLEAN;

COMMENT ON COLUMN picks.line_clv_pts IS
  'Points the line moved toward the pick side between signal and close '
  '(positive = we beat the close on the number). NULL for moneyline.';
COMMENT ON COLUMN picks.clv_beat_close IS
  'Did this pick beat the close? line_clv_pts > 0 when the number moved, '
  'else clv_pct > 0. NULL until CLV is captured.';

-- Backfill the picks already captured. Every one of them cleared the same-line
-- guard by construction, so the number did not move: line CLV is exactly 0
-- wherever a line exists, and the verdict is the price verdict.
UPDATE picks
   SET line_clv_pts = 0
 WHERE clv_captured_at IS NOT NULL
   AND line_clv_pts IS NULL
   AND closing_line IS NOT NULL
   AND scored_line  IS NOT NULL;

UPDATE picks
   SET clv_beat_close = (clv_pct > 0)
 WHERE clv_captured_at IS NOT NULL
   AND clv_beat_close IS NULL
   AND clv_pct IS NOT NULL;

-- The ~55% that were skipped keep clv_captured_at NULL and are picked up by the
-- self-healing backfill on the next few settles (40 dates per run).
