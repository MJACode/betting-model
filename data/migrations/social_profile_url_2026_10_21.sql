-- Send the 100-character profile URL.
--
-- The first seed put the sheet URL in a dollar quote. data.db rewrites ?
-- to %s outside single quotes, so the stored URL was 101 characters and
-- X refused it (HTTP 403, code 120, maximum is 100). This file inserts
-- the URL in a single-quoted literal when no queued or done row already
-- has it. The failed row stays. A second pass returns.
--
-- to_regclass, not ::regclass. One DO block.

DO $mig$
BEGIN
  IF to_regclass('public.social_profile_update') IS NULL THEN
    RETURN;
  END IF;

  IF EXISTS (
    SELECT 1 FROM public.social_profile_update
     WHERE url = 'https://docs.google.com/spreadsheets/d/1FaUkZnjirMrh0G3Je3RpNoO6d9wq6CcKGZr9bbSovXo/edit?usp=sharing'
       AND status IN ('queued', 'done')
  ) THEN
    RETURN;
  END IF;

  INSERT INTO public.social_profile_update (name, description, url)
  SELECT $pname$SignalBase | Model Picks + CLV$pname$,
         $pdesc$Model-driven picks: NHL, NFL, CFB, NBA & more. Every posted pick graded, every closing line tracked. Full record below. Discord: discord.gg/Sge4Djj2xT · 21+$pdesc$,
         'https://docs.google.com/spreadsheets/d/1FaUkZnjirMrh0G3Je3RpNoO6d9wq6CcKGZr9bbSovXo/edit?usp=sharing'
   WHERE NOT EXISTS (
     SELECT 1 FROM public.social_profile_update
      WHERE url = 'https://docs.google.com/spreadsheets/d/1FaUkZnjirMrh0G3Je3RpNoO6d9wq6CcKGZr9bbSovXo/edit?usp=sharing'
   );
END
$mig$;
