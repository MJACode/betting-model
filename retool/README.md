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

Merge the change to `master`, then ask Claude to "push the dashboard". It:

1. Builds the upload: `python -m scripts.retool_app_files zip <out.zip>`
   (every file here except `package.json`, which Retool writes itself).
2. Calls Retool's import tool (`retool_start_prepared_import`) with this app as
   the target. The import plan tells Retool's builder to copy every file
   unchanged and never to run the functions that write (`setModelVolume`,
   `saveDashboardLayout`, `deleteDashboardLayout`). `setModelVolume` changes
   what gets posted.
3. Uploads the zip to the address the tool returns (`curl -X PUT`; Python's
   default client is refused by Retool's firewall with error 1010).
4. Waits for the import, then deletes the two planning files it leaves behind
   (`/plans/IMPORT_PLAN.md`, `/plans/import-build-plan.json`).
5. Reads every file back out of Retool and runs
   `python -m scripts.retool_app_files check <dumps>`. It fails on any
   difference, missing file or extra file.
6. Publishes only when that check is clean, then reads the published version
   back and checks it again.

**What was proved on 2026-11-15, on a throwaway copy of the app:** the upload
was accepted (68 files, none dropped), Retool's builder placed them with a
file-copy step (not by retyping), ran no server function, and used 0.002 of
the month's 1,000 Retool AI credits. Reading the copy back, all 66 files that
could be compared were byte-for-byte identical. Two small files,
`backend/package.json` and `pnpm-workspace.yaml`, could not be read back from
that copy. Retool calls them its own read-only files, and both are Retool's
defaults. A publish to the live app has not been done this way yet; step 6
is what checks it the first time.

**Routes that do not work**, measured the same day: Retool's builder cannot
download anything (its shell allows only a few `git` commands, `pnpm install`
and `vitest`, and its `git` can only pull from Retool's own internal copy);
and Retool's GitHub link needs the Enterprise plan.

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
