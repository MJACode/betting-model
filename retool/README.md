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

**This folder is the copy you edit.** A change made directly in Retool's
editor must be copied back here the same day, or the next push from here will
overwrite it. Both Retool accounts are admins, and the admin group owns this
app in a way the sharing settings cannot change, so nothing on the Team plan
can lock the app against an edit in Retool.

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
4. If a file was **deleted** here, sends one thread message telling Retool's
   builder to delete it there too. The import only adds and overwrites.
5. Reads the app's files back out of Retool and runs
   `python -m scripts.retool_app_files check <dumps>`. It fails on any
   difference, missing file or extra file.
6. Publishes only when that check is clean. If Retool asks for approval of a
   function that writes to the database, Claude stops and asks you. Then it
   reads the published version back and checks it again.

**Read the right listing for the extra-file check.** The app's published
listing (no thread named) shows only the app's own files: 70 for the live app.
A thread's listing also shows Retool's hidden system files and the upload
folder (269 files on the test app). Those are not app source; compare only
the app's own files.

## What has been proved, and what has not

**The full path works on the live app** (2026-11-16, 01:46 UTC; a push with no
changes, at mike's request). The import used 0.0023 credits. Every file
read back from the draft matched. Publishing needed no function approval,
because the live app's functions were already approved and had not changed.
The published app was read back with no draft named: all 69 files
byte-for-byte identical to this folder, including `package.json`,
`backend/package.json` and `pnpm-workspace.yaml`. It loaded in the browser
with live data on the Models and Volume tabs and no console errors. Publish
tag `rr-publish-1794793612838-9275c64`.

Measured on 2026-11-15, on a throwaway copy of the app:

- **Upload and copy.** The upload was accepted (68 files, none dropped).
  Retool's builder reported placing 63 files with its file-copy tool, and its
  event log shows that tool in use. It wrote `frontend/package.json` by
  editing rather than copying, and that file came out identical too.
- **Byte check.** Reading the copy back, all 66 files that could be compared
  were byte-for-byte identical.
- **No database writes.** The builder ran no server function. The volume
  settings change log has no entry after 2026-11-11, and the layouts table is
  empty.
- **Cost.** The import used 0.002 Retool AI credits; the two follow-up test
  messages used about 5.9. The account has 1,000 a month; 992.07 were left
  afterwards (resets 2026-12-14).
- **Deleting a file works.** A thread message deleted an ordinary app file,
  and the file list confirmed it was gone.

What did **not** work, or is still unknown:

- **Four files Retool will not let an import overwrite:** `vitest.config.mjs`,
  `backend/package.json`, `frontend/vitest.config.ts`,
  `frontend/vitest.setup.ts`. Retool treats them as its own read-only files.
  **An edit to any of these here will not reach Retool.** They matched
  already.
- **Two files can't be read from a draft:** `backend/package.json` and
  `pnpm-workspace.yaml`. Retool's file-read tool reports both missing on a
  draft, on the test app and the live app alike. Read the published app to
  check them. After the live push, both matched.
- **Leftover files.** The import leaves `/plans/IMPORT_PLAN.md` and
  `/plans/import-build-plan.json` in the app, and Retool refuses to delete them
  ("Cannot delete protected file"). They are now in the published live app
  too (72 files listed instead of 70). The app never loads them, and `check`
  skips them.
- **A changed write function may need your approval.** Retool records each
  approval against a fingerprint of the function. The test app, being new, was
  blocked until its two layout functions (`saveDashboardLayout`,
  `deleteDashboardLayout`) were approved; that approval was not given there.
  On the live app, an unchanged push needed none. Expect Retool to ask again
  when one of those functions is edited (not yet seen). If it does, Claude
  stops and asks you.
- **Retool's check misses one write function.** Retool's "this function
  writes" check did not flag `setModelVolume`. That function writes through a
  database function call, which looks like a read.

**Routes that do not work**, measured the same day:

- Retool's builder cannot download anything. Its shell allows only a few
  `git` commands, `pnpm install` and `vitest`, and its `git` can only pull from
  Retool's own internal copy.
- Retool's GitHub link needs the Enterprise plan.

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
- Retool's own hidden files (`backend/user.d.ts`, the shared UI components,
  the generated hooks). Retool's ignore file lists them, and its published
  file list does not include them.

## What stays the same after the move

- The app reads the database through Retool's saved **supabase** connection,
  named by ID in `package.json`. No password or key is in these files.
- This repository is **public**, so the dashboard's queries are now public too.
  Every table and view they name is already named elsewhere in this repo.
