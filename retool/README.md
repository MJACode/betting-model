# Retool ops dashboard — source

`models-ops/` is the source of the Retool app **"Betting Model — Models & Ops"**:

- Live app: <https://signalbaseskinny--betting-model-models-ops.retool.app>
- Editor: <https://signalbaseskinny.retool.com/apps/ce1154be-a4e3-11f1-af11-a363289481d8>
- What each tab shows: `docs/monitoring.md`, "The Retool dashboard".

It was copied out of Retool on **2026-11-15**, from the app as last published
on 2026-11-13 15:24 UTC (69 of its 70 files; see "Not here" below). Every file
was checked against Retool's own size and line count, byte for byte.

## Which copy runs

**Retool runs what is published in Retool. Nothing here runs by itself.**

Retool's own GitHub link ("Source Control" and "Protect app") is an
**Enterprise-plan** feature. This Retool account is on the **Team** plan, and
the protect call answers "Source control is not configured for this
organization" (measured 2026-11-15). So there is no automatic sync in either
direction: a change merged here reaches the live dashboard only when it is
pushed to Retool, and a change made in Retool's own editor reaches this folder
only when it is copied back.

**This folder is the copy you edit.** Treat a change made directly in Retool's
editor as a change that must be copied back here the same day, or the next push
from here will overwrite it.

## Getting a change from here into Retool

Ask Claude to "push the dashboard". It:

1. Opens a thread on the app in Retool and tells Retool's builder to download
   `retool/models-ops/` at the merged commit straight from GitHub (this repo is
   public, so no key is needed) and replace the app's files with those bytes —
   copied by a command, not retyped.
2. Reads every file back out of Retool and runs
   `python -m scripts.retool_app_files check <dumps>`, which compares the two
   byte for byte and fails on any difference, missing file or extra file.
3. Publishes only when that check is clean, then reads the published version
   back and checks it again.

Retool's builder spends Retool AI credits on step 1 (the account has 1,000 a
month). Retool's builder is told never to run the functions that write
(`setModelVolume`, `saveDashboardLayout`, `deleteDashboardLayout`):
`setModelVolume` changes what gets posted.

## Getting a change made in Retool back here

Claude reads every file with Retool's file-read tool, then:

```bash
python -m scripts.retool_app_files write <dump.json> [<dump.json> ...]
```

The same command with `check` instead of `write` reports whether this folder
and Retool currently hold the same bytes.

## Not here

- `pnpm-lock.yaml` (201,834 bytes in Retool). Retool's file-read tool cuts any
  file off at 64 KB, so it cannot be copied whole, and a partial lockfile is
  worse than none. pnpm rebuilds it from the `package.json` files.
- `backend/user.d.ts` and the read-only system half of the theme are Retool's
  own files: `package.json` refers to the first, and Retool's file list does not
  include it.

## What stays the same after the move

- The app reads the database through Retool's saved **supabase** connection,
  named by ID in `package.json`. No password or key is in these files.
- This repository is **public**, so the dashboard's queries are now public too.
  They hold table and view names only, all of which are already in
  `data/migrations/`.
