# nfl/data/odds_cache — IRREPLACEABLE

~45,000 The Odds API credits of historical snapshots. **Never delete. Never
gitignore.** Losing this tree cannot be rebuilt without re-spending credits.

## Restore paths

1. **Git history** — the directory remains tracked on `master`.
2. **External tarball** — `nfl-model-odds-cache.tar.gz` (keep a copy outside
   any single machine). Unpack into `nfl/data/odds_cache/` if a checkout is
   sparse or damaged.

Git LFS migration is intentionally **not** applied in this change set: moving
already-committed blobs to LFS requires a history rewrite or `git lfs migrate`
on a full clone, which is out of scope for a contents-API patch.
