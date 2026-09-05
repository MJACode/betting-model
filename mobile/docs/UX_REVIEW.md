# Front-end UX review — the checklist

> The contract for the `frontend-ux-designer` agent (`.claude/agents/`), and
> for anyone reviewing a change under `mobile/src` by hand. The agent supplies
> judgement; this file says what it must look at, so two reviews of the same
> change find the same things. Invoke it with `/ux-review` or let it run
> proactively after a front-end change.
>
> Created 2026-09-02 (Matt). Companion scan: `mobile/scripts/ux_scan.mts`.

## What triggers a review

Any change that adds or edits a `.tsx` file under `mobile/src/components` or
`mobile/src/screens`, or a `.ts` under `mobile/src/lib` that shapes what users
see (`format.ts`, `theme.ts`, `modelMeta.ts`, `thresholds.ts`). Hooks and
queries are in scope only for the states they expose (loading / error / empty).

The Streamlit dashboard (`dashboard/app.py`) is an internal tool and is out of
scope unless asked.

## 0. Product rules — a violation is a Blocker

| Rule | Source | What to look for |
|---|---|---|
| A pick is a pick | CLAUDE.md §1c | A re-priced line shown where the locked line was. Movement belongs beside the pick (`LineMovementCard`, `PickTimingCard`), never in its place. |
| DK decides, best line displays | CLAUDE.md §6 | `best_*` fields feeding anything that reads as the decision: badge, edge, stake, P&L. Best price is for the card's book row and the betslip hand-off only. |
| LIVE, not paper trading | CLAUDE.md §2 | "paper", "simulated", "test mode" in copy. |
| Access is one gate | CLAUDE.md §6 | `useSubscription().entitled` deciding what renders. Must be `useEntitlement()`. |
| Today is ET | CLAUDE.md §7 | `toISOString().slice(0,10)` or a bare `new Date()` day. Must be `todayET()` / the `*ET` formatters in `src/lib/format.ts`. |
| Thresholds are mirrored, not authored | CLAUDE.md §6 | A component computing its own cut. `passesActionFilter` / `useActionThresholds` are the only sources. |
| Native module → TestFlight | `.github/workflows/mobile-ota.yml` | A new native dependency in `package.json` or `app.json`. Flag it in the summary; the OTA job will refuse the publish. |

## 1. Hierarchy and scanning

The board is read one-handed, several times a day, often during a game. The
question for every component: **can a user find the number they came for in
under a second?**

- One primary number per card, largest weight; everything else is secondary
  (`textSecondary`) or tertiary. Two equal-weight numbers side by side is the
  most common failure on this board.
- The signal (BET / AVOID / NONE) is the first thing the eye lands on. It uses
  `SignalBadge`, never an ad-hoc pill.
- Grouped-list iOS: cards on `bg`, `radii.md`, `spacing.lg` gutters, headers as
  uppercase footnote in `textSecondary`. A new screen that invents its own
  rhythm reads as a different app.
- Sort and filter controls live in the existing `FilterBar` / `FilterChip` /
  `FilterSheet` family. A new screen with its own chip style is a duplicate.
- Density: a list row taller than ~96pt on a scanning screen needs a reason.
  Detail screens can breathe; list screens cannot.

## 2. Tokens

Everything visual comes from `src/lib/theme.ts`. The reason is not taste: the
app is light-only today, and a hard-coded colour is the thing that breaks
first when that changes.

- No hex literals outside `theme.ts`. The scan reports these; the existing
  exceptions are modal backdrops (`#00000055`) and two `#FFF4E5` MED tints, and
  the right fix for a new one is a token, not another literal.
- `fontSize` from `font.size.*`, weights from `font.weight.*`, radii from
  `radii.*`, gaps from `spacing.*`. A literal `fontSize: 14` is a new type
  scale nobody agreed to.
- Semantic colours mean what they say: `bet` / `avoid` / `none` for signals,
  `positive` / `negative` for P&L, `high` / `med` / `low` for confidence.
  Green for anything that is not "good for the user" is a finding.
- **Brand (2026-09-03).** The `brand*` tokens are sampled from the real
  @signalbasepicks mark and banner (`assets/brand/`, hash-verified; icons are
  re-drawn by `scripts/render_brand_icons.py`). Amber (`brand`, #F2B01E) is
  **1.9:1 on white**, so it is never text or an icon on a light surface — it
  lives on the navy chrome (`brandNavy` tab bar, splash, `brandNavyRaised`
  betslip bar) and inside the mark. `tint` is `brandInk` (#0B1320, 18.6:1),
  the S itself; an amber tint would also collide with the orange `med`
  confidence semantic. Amber on a light card is a finding.

## 3. States — every screen has five

Loading, empty, error, offline/stale, and populated. A screen that only
handles the last one renders blank at 6:05am before the pipeline has run,
which is exactly when users open it.

- **Empty** uses `EmptyState` with a title that says *why* it is empty and,
  where possible, *when* that changes ("Picks post after the 6am run" beats
  "No picks"). CLAUDE.md §7: an empty board and a broken pipeline look
  identical; the copy should make them look different.
- **Loading** is an `ActivityIndicator` or a skeleton, not a flash of empty
  state. On a `FlatList`, `RefreshControl` is wired.
- **Error** shows the message from `src/lib/errors.ts` and a retry, and never
  the raw Supabase error text.
- **Stale / offline**: anything live (`LiveScreen`, `LiveGameBanner`,
  `GameStatusPill`) says how old the number is. `isLiveSnapshotUsable` exists
  for this.
- Preview / paywall: an unentitled user sees the `isUnlockedPreview` subset,
  and the paywall copy matches `PaywallScreen`, not a new sentence.

## 4. Touch and reach

- Every tappable has a hit area of at least 44×44pt. Icon buttons under that
  size carry `hitSlop`. The `*Button.tsx` components are the pattern.
- Primary actions sit in the bottom half of the screen or in a bar
  (`BetslipBar`), not the top-right corner.
- Sheets (`*Sheet.tsx`) dismiss on backdrop tap and on swipe; a sheet that
  only closes from an X is a finding.
- Destructive or money-moving actions (untrack, clear slip, change bankroll)
  confirm or are undoable via `showToast`.

## 5. Accessibility

- Every `Pressable` / `TouchableOpacity` has an `accessibilityRole` and, unless
  its only child is text, an `accessibilityLabel`. The scan reports the ones
  that do not.
- Colour is never the only carrier of meaning. A BET/AVOID distinction that is
  green-vs-red with no word or icon fails for ~8% of male users.
- Text scales: no `allowFontScaling={false}`, no fixed-height containers
  around body text. Numbers in tiles may cap with `maxFontSizeMultiplier`,
  and that is the one place it is fine.
- Contrast: `textTertiary` on `bg` is at the AA floor; do not put it on a
  coloured chip.

## 6. Layout and safe areas

- Screens wrap in `SafeAreaView` from `react-native-safe-area-context`
  (never the RN one). Bottom bars respect `useTabBarHeight`.
- Long team names, player names and event titles truncate with
  `numberOfLines`, and the number they sit beside does not wrap. Test the
  finding against "Louisiana-Monroe @ Northwestern State" and a golf event
  name, not "NYY @ BOS".
- No horizontal scroll on a phone width. Tables scroll inside their own
  container.

## 7. Copy

- Odds through `formatAmerican`, percentages through `formatPct`, money
  through `formatCurrency`, dates through the `*ET` helpers. A hand-rolled
  format is a finding.
- Model ids never appear raw; `modelShort` / `modelMeta` label them.
- Sentence case, no exclamation marks, no "Oops". Tooltips use `InfoTooltip`
  and explain the *number*, not the feature.
- Nothing describes the platform as paper trading.

## 8. Reuse before invention

Before a finding says "add a component", check whether one of these already
does it: `EmptyState`, `StatTile`, `SignalBadge`, `GameStatusPill`,
`SharpScorePill`, `InfoTooltip`, `Toast`/`showToast`, `TrendSparkline`,
`TrendStrip`, `CalendarGrid`, the `filters/` family, the `*Sheet` family,
the `*Card` family on `PickDetailScreen`. A change that adds a second version
of any of these is a Should-fix, with the existing one named.

## 9. References — how Mobbin is used

The agent pulls 2–4 real screens per new or materially changed pattern through
the `Mobbin` MCP connector and names them in the finding. The point is not to copy
a competitor; it is to stop designing from a blank prompt and to give Matt a
picture he can look at.

Comparators that match this app's problems:

| Pattern | Look at |
|---|---|
| Pick / bet card, betslip | DraftKings, FanDuel, Underdog, PrizePicks |
| Live score strip, in-game state | ESPN, theScore, Sleeper |
| Stat tiles, trend strips, heat maps | Robinhood, Apple Stocks, Apple Health |
| Empty states, onboarding, paywall | Copilot Money, Duolingo, Headspace |
| Segmented boards, filter chips | Apple App Store, Airbnb |

If Mobbin is not connected or not authenticated, the review says so in one
line and continues on Apple HIG and the app's own conventions. Setup is in
the section below; it is a paid Mobbin plan and an OAuth login that only Matt
can do.

## Connecting Mobbin

The official server is remote (`https://api.mobbin.com/mcp`, OAuth in the
browser) and exposes three tools: `search_screens`, `search_flows` and
`search_sections`. ONE route reaches it:

- **Matt's claude.ai connector**, named `Mobbin` — tools arrive as
  `mcp__Mobbin__*`. Connected 2026-09-02. Tested 2026-09-05: `search_screens`
  (`platform: ios`, standard mode) answered in one call with three real
  screens, so "connected" is a measured fact, not a setting.

There used to be a second route, a `mobbin` server declared in the repo's
`.mcp.json`. It only ever worked in a local session after `/mcp →
Authenticate`; in every remote session it sat unauthenticated, the harness
listed it as "requires authentication", and the reply said Mobbin needed
authorising while the connector was answering fine. Two names for one
service is how a working tool gets reported as down. Removed 2026-09-05
(Matt: "that is already properly set up"). If a local session ever wants its
own copy, add it back under a different name and keep the agent's tool list
pointing at the connector.

**It needs a paid Mobbin plan, on the account the connector is signed in as.**
Measured 2026-09-02 and again 2026-09-03: `search_screens` answered
`Mobbin MCP requires a paid plan. Upgrade at https://mobbin.com/pricing` while
the plan WAS paid — the connector was authorized as the wrong account. Matt
re-authorized it in claude.ai connector settings and the same call returned
real screens within two minutes, no session restart. So that error means
"check which account is connected", not "buy a plan". If it appears, the agent
says so in one line and reviews on Apple HIG and the app's own conventions;
that is a status line, not a conclusion.

**What is in the library, measured 2026-09-03 (14 searches).** The big US
sportsbooks — DraftKings, FanDuel, Underdog, PrizePicks, Sleeper, Hard Rock
Bet, Kalshi, Polymarket — returned nothing under their own names; the engine
substitutes other apps. The working comparators for this app are DAZN and
theScore (dark chrome, one accent), Apple Sports (its DraftKings odds module),
Phantom (a predictions market), Spotify (a bar floating over a dark tab bar),
and Tripadvisor / H&M / Airbnb / Copilot Money for sign-in and link affordance.

## Baseline

Measured 2026-09-02 across all of `mobile/src` with `ux_scan.mts --all`, so a
review can report a set diff rather than a count:

- see the table in the session entry for 2026-09-02 in
  `docs/sessions/2026-09.md`. The rule from CLAUDE.md §7 applies: a review
  reports "0 new in touched files", not a raw total.
