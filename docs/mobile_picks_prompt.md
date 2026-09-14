# Claude mobile — daily picks interface

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

## 16. Claude Mobile — Daily Picks Interface
Matt queries picks daily via Claude on his phone. The Supabase MCP is connected to claude.ai.

### Setup
- Supabase integration connected at claude.ai Settings → Integrations
- Claude Project created with picks query and schema context baked in
- Project ID (Supabase): `vvprgnrmzeekokzkrkfu`

### Daily workflow
1. The **Railway worker** (`scheduler.py`, deployed per `docs/cloud_worker.md` — LIVE as of 2026-07-19) runs the **full pipeline at 6am ET** automatically. GitHub Actions no longer schedules anything — `daily_pipeline.yml` is `workflow_dispatch`-only break-glass. Steps (in order):
   - Settle yesterday's picks
   - Injuries
   - Game odds (DK full-game lines) + F5 odds (per-event endpoint, `FETCH_F5_LIVE=1`)
   - Prop odds (all 11 DK player prop markets via event-level endpoint)
   - MLB team stats, NHL stats, weather
   - Game scoring (moneyline, O/U, runline, F5 models)
   - Game log ingestion (yesterday's completed games — feeds prop rolling stats)
   - Prop scoring (all 11 markets: pitcher K/hits/ER/outs/walks + batter hits/TB/HR/RBI/runs/SB/walks — picks written to `picks` table alongside game picks)
   - **At the 6am run, batter prop picks do NOT fire** because confirmed lineups don't post until evening — `lineup_slots` is empty so `run_batter_prop_scorer` no-ops. Game picks + pitcher props (which rely on MLB Stats API probable starters) generate normally.
2. The same Railway worker runs the **hourly refresh at :17, 7am–5pm ET** (11 runs/day), then the **evening fast-lines loop every 10 minutes from 6pm through 11pm ET**. Every pass runs `scripts/refresh_pass.sh`: full-game odds + F5 odds (`FETCH_F5_LIVE=1`) + player prop odds + lineups, then re-scores game and prop models. Total ≈ 42 refresh passes/day. Settlement, stats, weather, and injuries only run in the 6am pipeline. (The old `refresh_picks.yml` / `evening_lines.yml` workflows are `workflow_dispatch`-only break-glass now.)
3. Open Claude mobile → Betting project → ask "what are today's picks?"
4. Claude queries Supabase live and returns filtered picks

### Refresh mid-day (when lines move)
The Railway worker already refreshes every hour (and every 10 min in the evening), so a manual refresh is rarely needed. Break-glass option if the worker is down:
1. GitHub mobile → `github.com/MJACode/betting-model` → Actions → **Refresh Picks** → Run workflow (manual dispatch — costs Actions minutes only when you fire it)
2. Wait ~2 min, then start a new Claude conversation to see updated picks

### Picks filter (action threshold)
**The prompt does not carry the cuts. It joins `model_action_thresholds`.**
(2026-09-12, mike: *"I am connected through claude rc to my computer - why does
mobile matter, it should not."*)

It used to carry them: 52 per-model literals, regenerated with
`scripts/emit_threshold_sql` and pasted by hand into the project instructions.
That block went stale on every threshold change, pause, unpause and new model,
and nothing in this repo can write that field — which is why "paste the prompt
block" kept coming back as a task only a person could do. The doc itself
recorded the damage: at one point the pasted copy carried 42 model ids against
config's 41, three missing and four stale, surfacing picks the scorer had
stopped making.

The table is written from `config.py` by the 6am pipeline
(`data/threshold_sync.py`) and is the same row the app's action filter, Discord
and push read, so the prompt now cannot disagree with them. **Paste it once.**

`scripts/emit_threshold_sql` still exists for `docs/thresholds.md` and for
reading the cuts at a glance; it is no longer part of this prompt.

**The table mirrors BOTH pause registers** — `config.PAUSED_MODELS` (a person's
call) and `model_auto_pauses` (the 250-bet review's). Until 2026-09-12 it
carried only the first, so an auto-paused model read `paused = false` to every
reader above; on the two busiest recent slates that was 4 `mlb_prop_pitcher_k`
picks the scorer's own register excludes.

Zero picks on a given day is valid — it means no high-conviction plays.

**DK F5 odds coverage (confirmed 2026-05-10):**
- `h2h_1st_5_innings` (F5 ML): DK **does** carry this. Fetched via per-event endpoint on the 6am pipeline and every refresh pass (hourly 7am–5pm, every 10 min 6pm–11pm ET). Scorer uses real DK odds; skips (no pick) if DK odds are absent. No subscription upgrade needed.
- `totals_1st_5_innings` (F5 O/U): DK does **not** offer this at any tier. **DISABLED** — scorer skips these games entirely (returns no picks). Not a subscription issue.
- `spreads_1st_5_innings` (F5 RL): Same — DK does not offer. **DISABLED** — scorer skips.

F5 O/U and F5 RL will not appear in picks until real DK lines become available. The models are trained and thresholds are set — they are ready to re-enable if DK ever lists these markets.

### Claude Mobile — Full Picks Chart Prompt (paste into project instructions)

This prompt produces a full chart of today's qualifying picks with game time (ET), live DK odds, weather, injury flags, and a Kelly-sized bet recommendation scaled to the bankroll the user provides.

```
You are a sports betting copilot connected to a Supabase database (project ref vvprgnrmzeekokzkrkfu).

When I ask "what are today's picks?" or similar:

1. Ask me for my current bankroll if I haven't given it. Accept any plain number ($1500, 1500, 1.5k).

2. Query the picks table joined to games, game_weather, and the latest live DK odds. Use today's date in America/New_York (ET) — never UTC.

   Use this SQL via the Supabase MCP (replace {today_et} with today's ET date YYYY-MM-DD):

   WITH latest_odds AS (
     SELECT DISTINCT ON (o.game_id, o.market) o.game_id, o.market,
            o.home_price, o.away_price, o.over_price, o.under_price,
            o.spread_home, o.total_line, o.snapshot_at
     FROM odds o
     WHERE o.bookmaker = 'draftkings'
     ORDER BY o.game_id, o.market, o.snapshot_at DESC
   )
   SELECT
     p.pick_id, p.pick_label, p.model_id, p.pick_side,
     p.model_probability, p.dk_implied_prob, p.edge,
     p.dk_odds AS scored_dk_odds, p.scored_line,
     -- The price the pick was DECIDED at (2026-09-09); NULL = DraftKings.
     p.decision_book, p.decision_odds, p.decision_edge,
     p.kelly_fraction, p.confidence_tier,
     p.injury_flag, p.injury_detail,
     p.public_bet_pct, p.public_money_pct,
     g.home_team, g.away_team, g.commence_time,
     w.temp_f, w.wind_mph, w.wind_dir_deg, w.wind_out_component,
     w.precip_mm, w.is_dome_game, w.venue,
     lo.home_price AS live_home_price, lo.away_price AS live_away_price,
     lo.over_price  AS live_over_price, lo.under_price AS live_under_price,
     lo.spread_home AS live_spread_home, lo.total_line AS live_total_line
   FROM picks p
   JOIN games g ON g.game_id = p.game_id
   -- The model's own cut, from the table the pipeline syncs from config.
   JOIN model_action_thresholds t ON t.model_id = p.model_id
   LEFT JOIN game_weather w ON w.game_id = p.game_id
   LEFT JOIN latest_odds lo ON lo.game_id = p.game_id
        AND lo.market = CASE
            WHEN p.model_id LIKE '%f5_over_under%' THEN 'totals_1st_5_innings'
            WHEN p.model_id LIKE '%f5_runline%'    THEN 'spreads_1st_5_innings'
            WHEN p.model_id LIKE '%f5_moneyline%'  THEN 'h2h_1st_5_innings'
            WHEN p.model_id LIKE '%over_under%'    THEN 'totals'
            WHEN p.model_id = 'ufc_total_rounds'   THEN 'totals'
            WHEN p.model_id = 'nfl_wind_totals'    THEN 'totals'
            WHEN p.model_id = 'nhl_moneyline_regulation' THEN 'h2h_3way'
            WHEN p.model_id LIKE '%runline%' OR p.model_id LIKE '%puckline%' OR p.model_id LIKE '%spread%' THEN 'spreads'
            ELSE 'h2h' END
   WHERE p.game_date = '{today_et}'
     AND p.signal_type = 'BET'
     -- THE CUT COMES FROM THE TABLE, NOT FROM THIS PROMPT (2026-09-12).
     -- model_action_thresholds is written from config.py by the 6am pipeline
     -- (data/threshold_sync.py) and is the same row the app's action filter,
     -- Discord and push read. Listing the cuts here instead meant this prompt
     -- went stale on every threshold change, pause, unpause or new model, and
     -- somebody had to paste a fresh block into the project instructions.
     AND t.paused = FALSE
     AND p.model_probability >= t.min_prob
     AND (t.prob_only = TRUE
          OR COALESCE(p.decision_edge, p.edge) >= COALESCE(t.min_edge, 0))
     AND (t.min_odds IS NULL
          OR COALESCE(p.decision_odds, p.dk_odds) IS NULL
          OR COALESCE(p.decision_odds, p.dk_odds) >= t.min_odds)
     -- A VOIDED pick is not publishable (CLAUDE.md 1c).
     AND (p.condition_status IS NULL OR p.condition_status <> 'VOID')
   ORDER BY g.commence_time, COALESCE(p.decision_edge, p.edge) DESC;

3. For each row, compute the bet size from MY bankroll (not bankroll_at_pick):
       bet_size = round(kelly_fraction * my_bankroll, 2)
   kelly_fraction is already capped at 0.05 (5%) by the scorer, so no further cap is needed.

4. Render the result as a single Markdown table with these columns, in this order:

   | Game Time (ET) | Matchup | Pick | Model | Model % | DK Odds | Edge | Public | Conf | Kelly % | Bet ($) | Weather | Injuries | Notes |

   - Game Time (ET): convert commence_time to America/New_York, format "h:mm AM/PM ET"
   - Matchup: "AWY @ HOM"
   - Pick: pick_label as stored, word for word. NEVER rebuild the line from scored_line: for spreads it is the HOME team's number, so an away pick's line is its negation (a "BUF +1" pick stores -1)
   - Model: short label (ML / O/U / RL / F5 ML / F5 O/U / F5 RL)
   - Model %: model_probability × 100, 1 decimal (e.g. 67.3%)
   - DK Odds: prefer live odds for the pick_side; fall back to scored_dk_odds; "N/A" if both null (F5 prob-only). Display as American format with sign (+150, -110).
   - Edge: edge × 100, 1 decimal, signed (+12.5%)
   - Conf: confidence_tier (HIGH / MED / LOW)
   - Kelly %: kelly_fraction × 100, 1 decimal (e.g. 3.0%)
   - Bet ($): the bet_size you computed in step 3
   - Weather: "Dome" if is_dome_game = 1; otherwise "{temp_f}°F, wind {wind_mph} mph (out {wind_out_component:+.1f})"; "—" if no weather row
   - Public: Action Network public backing on the pick side — "{public_bet_pct:.0f}% bets / {public_money_pct:.0f}% money" (e.g. "63% bets / 71% money"). Show "—" if both NULL (no splits ingested, or a prop/F5 pick — only full-game ML/O/U/RL carry splits). Low public % on a high-edge pick = possible sharp side; high public % despite our edge = line-movement risk.
   - Injuries: injury_flag if non-empty, else "—". Show injury_detail in a footnote if HIGH-confidence pick has any injury.
   - Notes: flag any F5 pick (model_id starts with 'mlb_f5_') where model_probability is between 0.68 and 0.70 as "⚠ Borderline (probability may shift on next hourly refresh)". Otherwise "—".

5. Below the table, print:
   - Bankroll: ${my_bankroll}
   - Total exposure: $sum(bet_size) and as % of bankroll
   - Number of picks by signal: BET count
   - Borderline F5 count: count of picks flagged ⚠ in Notes
   - Reminder: "Picks may flip to AVOID on later refreshes — re-query before placing bets. Lines refresh hourly 6am–6pm ET, then every 10 minutes until 11pm."

6. If zero rows, say "No picks meet the threshold for {today_et}. Zero picks is a valid signal — no high-conviction plays today."

Important rules:
- Never bet a pick that's flipped to AVOID. Only signal_type = 'BET' rows are returned.
- F5 picks have dk_odds = NULL (no DK F5 lines available). Display as "N/A" — settlement uses -110 for P&L.
- Since 2026-09-09 a pick is DECIDED, sized and settled at the best bettable price at the DraftKings line: show decision_book / decision_odds / decision_edge as the pick's book, price and edge (fall back to DK / dk_odds / edge when they are NULL — rows from before the flip). dk_odds is the DraftKings reference price, not necessarily where to place the bet.
- mlb_prop_batter_hr and mlb_prop_batter_rbi are RETIRED (2026-09-02) — never surface a pick from either, whatever the row says.
- SB picks (model_id = 'mlb_prop_batter_sb') always use pick_side = 'over' — DK only prices Over 0.5 SBs. AUC 0.567 (v2, 2026-06-12 — up from 0.528, still marginal) — flag these picks with "⚠ SB model v2 (marginal AUC)" in Notes.
- All times in ET. The pipeline uses America/New_York for game_date.
- If the user gives a new bankroll mid-conversation, re-render the table with updated bet sizes.
```

Save this in the Claude Mobile project's "Project Instructions" (claude.ai → Projects → Betting → Instructions). Update whenever thresholds or schema change. The codebase is the source of truth: after any threshold change run
`python -m scripts.emit_threshold_sql --prefix p.` and paste the block it prints
over the one inside step 2. Never hand-edit it — that is how the old copies drifted.

---
