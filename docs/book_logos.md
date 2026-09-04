# Sportsbook logos — how the marks get into the line pills

Matt, 2026-09-04: *"Can you scrape for the Sportsbook logos. We should have one
for all the Sportsbook betting lines we call. Fan duel, DK, MGM etc."*

The Stats tab's line pills are filled in each book's colour and carry that
book's mark (`mobile/src/components/BookMark.tsx`). Today the mark is the
book's short label — "DK", "FD", "MGM". This file is how it becomes the logo.

## Why the label ships first

**The sandbox cannot reach an image host, and the four routes in CLAUDE.md §1b
were all tried:**

| Route | Result |
|---|---|
| Direct fetch / `curl` | `CONNECT tunnel failed, 403` — the agent proxy denies `upload.wikimedia.org` and every CDN tried. The proxy's own status endpoint logs the rejection. |
| `WebFetch` | `EGRESS_BLOCKED` on the same host. SVG is text, so this route would otherwise have worked. |
| npm (reachable directly — it is in the proxy's `noProxy`) | No sportsbook icon set exists. `simple-icons` carries **3,457** marks and not one book; `npm search` for sportsbook/bookmaker/betting logos returns nothing relevant. |
| The Railway worker | Has open egress and would work, but a throwaway scraper is a deploy cycle for a 13pt decorative glyph. |

So there was no honest file to ship. A label is not a placeholder that lies —
it names the book correctly at the size the mark occupies.

## The right source is the affiliate kit, not a scrape

Every book's affiliate programme ships a brand kit — SVG and PNG, light and
dark, with the usage rules attached. That is the licensed source, it is what the
logos are *for*, and it is the version that will not go stale when a book
rebrands. DraftKings, FanDuel, BetMGM, Caesars, Fanatics, BetRivers, Hard Rock
Bet, Bally Bet, betPARX and Rebet all publish one.

**A scrape gives you the same pixels without the licence.** For a screen that
links members to those books it is the difference between a partner asset and a
borrowed one, and it costs nothing extra to do it properly.

## Dropping them in

Marks go in `mobile/assets/books/<bookKey>.svg`, keyed exactly as
`markets.ts::BookKey` spells them — note `williamhill_us` is Caesars:

```
draftkings  fanduel  betmgm  williamhill_us  fanatics
betrivers   hardrockbet  ballybet  betparx  rebet
```

Then register each one in `BOOK_GLYPHS` in
`mobile/src/components/BookMark.tsx`. That is the whole change — every pill on
every board reads through that one registry, so nothing else needs touching,
and `react-native-svg` is already a dependency (15.12.1), so it still ships
over the air.

Two constraints the component enforces, and a logo must respect:

- **It takes the pill's foreground colour.** The mark sits on DraftKings green
  or on the app tint; a mark with baked-in colour will fail contrast on one of
  them. Use `currentColor` / accept the `color` prop.
- **It is silent for VoiceOver.** The pill's own label already says
  "…, −262 at DraftKings", so the mark must not speak twice.

`mobile/scripts/verify_stats_pill.ts` pins both, plus the registry's existence.

## If you want them fetched rather than supplied

Say the word and it goes on the worker: a script that pulls each book's kit,
normalises the marks to a single viewBox, and commits them. That is the only
route from here with open egress — it needs a merge and a run, not a sandbox.
