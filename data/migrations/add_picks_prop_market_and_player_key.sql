-- The market-relative NFL prop rule is ONE model id covering many markets
-- (docs/nfl_props_model.md §5c), so the market travels on the pick row rather
-- than being looked up from the model id the way every trained prop model does.
--
-- player_key is the normalised player name. NFL is the one sport whose odds feed
-- and stat feed disagree on spelling ("Marvin Harrison Jr." vs "Marvin
-- Harrison", accents, suffixes), so settlement joins on the normalised name —
-- and recovering it by regex out of pick_label made a display string
-- load-bearing. This makes the join structural.
--
-- Both nullable and additive: every existing pick keeps working untouched.
ALTER TABLE picks ADD COLUMN IF NOT EXISTS prop_market TEXT;
ALTER TABLE picks ADD COLUMN IF NOT EXISTS player_key  TEXT;
