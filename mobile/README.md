# Signalbase — iOS app (Expo / React Native)

A native iOS app that reads picks live from the same Supabase database the
Python pipeline writes to. Read-only. No Mac required to develop. No Mac
required to ship to TestFlight or the App Store either — EAS Build does the
Mac compile in the cloud.

## What you can do on Windows

| Goal                                 | Tool                          | Mac needed? |
|--------------------------------------|-------------------------------|-------------|
| Live preview on your iPhone          | `npx expo start` + Expo Go    | No          |
| Type-check + lint                    | `npm run typecheck`           | No          |
| Build a TestFlight `.ipa`            | `eas build --platform ios`    | No (cloud Mac) |
| Submit to TestFlight / App Store     | `eas submit --platform ios`   | No          |

## One-time setup (Windows)

1. Install **Node.js 20 LTS** from <https://nodejs.org/>.
2. Install the **Expo Go** app on your iPhone from the App Store.
3. From this folder (`mobile/`):
   ```
   npm install
   ```
4. Copy the env example and fill in the Supabase anon key:
   ```
   copy .env.example .env
   ```
   Open `.env` in a text editor. Get the anon public key from:
   <https://supabase.com/dashboard/project/vvprgnrmzeekokzkrkfu/settings/api>
   → look for "Project API keys → anon public". Paste it after
   `EXPO_PUBLIC_SUPABASE_ANON_KEY=`.

## Daily dev loop

```
npm start
```

Expo will print a QR code in the terminal. Open the Camera app on your
iPhone (or the Expo Go app's scanner) and scan it. The app loads with hot
reload — edit a `.tsx` file on Windows and the iPhone refreshes
automatically.

If you ever get stuck, run:
```
npx expo start --clear
```
to clear the Metro bundler cache.

## How the app is organized

```
App.tsx                  Navigation root (5 tabs + 2 stack screens)
src/lib/
  supabase.ts            createClient (anon key)
  thresholds.ts          MIRROR of config.py ACTION_THRESHOLDS — keep in sync
  format.ts              American odds, percent, currency, ET dates
  modelMeta.ts           Friendly labels per model_id + stat keys for trends
  theme.ts               iOS-style design tokens (light mode)
  queries.ts             All Supabase reads in one file
src/types/index.ts       All shared TypeScript interfaces
src/hooks/
  useBankroll            AsyncStorage-backed bankroll, default $1000
  usePlacedPicks         AsyncStorage map<pick_id, override>
  useTodayPicks          Today's picks joined with games + weather
  usePerformance         Settled picks × placed-flags rolled up by day
  useTeamTrends          Last 25 games per team, bucketed L3/5/10/20/season
  usePlayerTrends        Last 25 player_game_log rows for one player
src/screens/
  PicksScreen            Tab 1: ALL picks today
  SignalsScreen          Tab 2: BET-filtered by ACTION_THRESHOLDS
  PerformanceScreen      Tab 3: ROI tile + calendar + stat tiles
  PickDetailScreen       Stack: reasoning + team/player trends + weather
  DayDetailScreen        Stack: drill-in from a calendar cell
  ExplainerScreen        Tab 4: how the model works (plain language)
  SettingsScreen         Tab 5: bankroll, reset placed flags, about
src/components/
  PickCard               Row used on Picks + Signals lists
  SignalBadge            BET / AVOID / NONE pill
  PlacedToggle           Switch on PickDetail
  ReasoningCard          "Why this bet?" math breakdown
  TrendStrip             L3 / L5 / L10 / L20 / Season cells
  TrendSparkline         SVG line chart of last 20 player game values
  PerformanceCalendar    Month grid with red/green daily heat
  StatTile               Big-number tile (ROI, win %, streak, etc.)
  EmptyState             Headline + subtitle empty placeholder
```

## Keeping thresholds synced with `config.py`

`src/lib/thresholds.ts` mirrors `config.MODEL_PROB_THRESHOLDS`,
`MODEL_EDGE_THRESHOLDS`, `ACTION_THRESHOLDS`, and `PROB_ONLY_MODELS`. When
those change on the Python side, update the TS file by hand. Each entry has
a short comment matching the rationale in `CLAUDE.md`. The Signals tab
filter (`passesActionFilter`) must produce the same picks as the Section 16
SQL in `CLAUDE.md` — if they diverge, you'll bet on the wrong things.

## Supabase RLS / permissions

The pipeline already enabled anon SELECT policies on `picks`, `games`,
`game_weather`, `odds`, and `player_prop_odds` in session 18b for the
Lovable website. The app reuses those.

If team or player trends come back empty on the Pick Detail screen, the
anon role probably doesn't have SELECT on `mlb_team_stats` and/or
`player_game_log`. Run this in the Supabase SQL editor:

```sql
ALTER TABLE player_game_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon read player_game_log" ON player_game_log
  FOR SELECT TO anon, authenticated USING (true);
```

The `games` table is already readable so team trends already work.

## Branch previews (run one command)

GitHub Actions was removed from this repo on 2026-08-24, so the automatic
per-PR preview is gone. Publish one yourself from `mobile/`:

```bash
eas update --branch <branch-name> --message "what changed"
```

That prints a QR code and a shareable link — open it in Expo Go on any iPhone
and the latest commit loads instantly. No build, no TestFlight, no Mac.

### One-time setup (10 min)

1. Install EAS CLI: `npm install -g eas-cli`
2. Log in: `eas login` (creates a free expo.dev account if needed)
3. Initialize the project (writes the project ID into `app.json`):
   ```
   cd mobile
   eas init
   eas update:configure
   ```
4. Commit the resulting changes to `mobile/app.json`.
5. Create an access token at <https://expo.dev/settings/access-tokens>.
6. Add it as `EXPO_TOKEN` in GitHub: **Settings → Secrets and variables →
   Actions → New repository secret**.

Until that's done, the workflow posts a friendly "setup needed" comment on
your PRs instead of failing silently.

### Day-to-day

- Push a commit on a PR branch that touches `mobile/`
- ~2 minutes later, a comment appears on the PR with QR code + URL
- Open the URL on iPhone (or scan the QR with Expo Go) — latest code loads
- Each new commit updates the same preview

## TestFlight / App Store path (when ready)

1. Sign up for an Apple Developer account ($99/yr) at
   <https://developer.apple.com/programs/>.
2. Install EAS CLI: `npm install -g eas-cli`
3. Log in to Expo: `eas login`
4. Initialize a project once: `eas init` — paste the `projectId` it gives
   you into `app.json` → `extra.eas.projectId`.
5. Configure credentials: `eas credentials` (cloud-managed is easiest).
6. Run a preview build: `npm run build:ios:preview`. EAS spins up a Mac
   builder in the cloud and emails you a download link.
7. To submit: `eas submit --platform ios`.

The entire flow happens from Windows. You never touch a Mac.

## Troubleshooting

- **"Network request failed" on the picks screen** — the anon key in
  `.env` is wrong, or RLS is denying SELECT. Open the same Supabase URL +
  key in a curl request to confirm.
- **Black screen / red box on launch** — `npx expo start --clear` and
  reload.
- **TypeScript path alias `@/...` not resolving** — make sure
  `babel.config.js` is the one in this folder and you ran `npm install`.
  The `@/*` alias is declared in `tsconfig.json`.
- **Bankroll won't persist** — AsyncStorage requires native module linking,
  which happens automatically in Expo managed workflow. If you ejected, you'll
  need to re-add the native module manually.

## What this app deliberately does NOT do

- Place bets for you. Picks are informational; you place them at your book.
- Write to Supabase. Placed-bet flags live on the device only.
- Push notifications. Could be added later via Expo Push.
- Run a backend. The Python pipeline owns scoring + settlement entirely.
