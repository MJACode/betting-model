"""The clauses a LIVE (in-play) pick has to clear before any surface shows it.

WHY THIS MODULE EXISTS. CLAUDE.md section 1b: *the app, Discord and push show
the same picks — they are identical*. The PRE-GAME producers have satisfied that
since 2026-09-05 by selecting `picks` through `model_action_thresholds`, the
same table and the same cut the app's `passesActionFilter` applies. The LIVE
producers never did: `discord_notifier._new_live_signals` and
`push_notifier._new_live_signals` took **every** `is_live` BET row with
`result IS NULL` and no gate at all — no paused check, no retired check, no
VOID check — while the app's Live board (`PicksHomeScreen.liveInProgress`)
applies `!isModelPaused && !isModelRetired`, and `queries.fetchLivePicks`
excludes `condition_status = 'VOID'` in its own SQL.

So the live channel could announce a bet the app refuses to show, and the two
had no shared definition to drift from. This module is that definition.

WHAT IS **NOT** HERE, AND ON PURPOSE. `min_prob` / `min_edge` / `min_odds` are
deliberately absent. The app's Live board does not apply them either, and its
comment says why: `nfl_live_prop`'s cut is EV, applied server-side in
`nfl/live_model/config.EV_THRESHOLDS`, so filtering the board on the bundled
prob/edge row would hide BETs that lane legitimately wrote. Adding them here
would create the mismatch in the other direction — Discord losing picks the app
shows — which is the same fault wearing the opposite sign. The in-play engines
decide; these clauses only remove what is not stakeable at all.

RETIREMENT NEEDS NO LIST. `data.threshold_sync` prunes `model_action_thresholds`
down to `config.ACTION_THRESHOLDS`, and a retired model is out of that dict — so
a retired model has NO ROW, and requiring one is exactly the app's
`isModelRetired`. Measured 2026-09-12: all four retired models with live BETs
(`mlb_live_win_prob`, `mlb_live_runline`, `mlb_prop_batter_hr`,
`mlb_prop_batter_rbi`) carry zero threshold rows, so `EXISTS` is the whole test.
The pre-game producers get this free from their INNER JOIN; the live ones
LEFT JOIN (Discord, for the price bound) or do not join at all (push).
"""
from __future__ import annotations


def live_publishable_sql(alias: str = "p") -> str:
    """The WHERE-clause fragment (leading ``AND``) a live pick must clear.

    Written as EXISTS rather than a join so the two callers can share one
    string: Discord already LEFT JOINs `model_action_thresholds` for the
    "good to" price bound and must keep that row available even when a clause
    would have dropped it, and push joins nothing at all.
    """
    return f"""
          -- PARITY WITH THE APP'S LIVE BOARD (CLAUDE.md section 1b).
          -- A PAUSED or RETIRED model's live BET is not stakeable, and the
          -- app stopped drawing it -- so it must not be announced either.
          -- A paused model keeps its row (paused = TRUE); a retired one has
          -- none at all, pruned by data.threshold_sync. Both fail this.
          AND EXISTS (
              SELECT 1 FROM model_action_thresholds mat_pub
              WHERE mat_pub.model_id = {alias}.model_id
                AND mat_pub.paused = FALSE
          )
          -- A VOIDED pick is not publishable and not displayable (section 1c):
          -- the row stays as evidence of a model that fired where it should
          -- not have, and it stops counting. fetchLivePicks excludes it in the
          -- app's own SQL; scripts/void_picks.py takes any --model, so this is
          -- not an NFL-shaped concern.
          AND ({alias}.condition_status IS NULL
               OR {alias}.condition_status <> 'VOID')"""
