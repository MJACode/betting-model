# Model artifacts: is the file there, and is it the one the worker will open?

> Written 2026-09-07 after `system_health` reported `OK — all 56 active
> artifacts deserialise` while it had opened 51. Rules it serves:
> `.claude/rules/operations.md` ("a retrained model must have its `.pkl`
> COMMITTED"; "a health check must not gate on the thing that breaks").

## Three separate questions, three separate failures

A registered model is only usable if all three hold. Each has failed at least
once, and each failure looked healthy from the other two angles.

| Question | Failure | Caught by |
|---|---|---|
| Does a registry row exist? | — | `model_registry` check |
| Do the bytes deserialise? | #215 — twelve `nfl_prop_*` artifacts raised `XGBoostError` and sat in master two weeks | `tests/test_model_artifacts_load.py`, `model_artifacts_load` check |
| **Is the file where the worker will look?** | **2026-09-07 — five active artifacts in no commit on any branch** | **`test_every_model_artifact_on_disk_is_tracked_by_git`** (new) |

The third is the one this doc is about, because it is invisible from the machine
that has the file. It is only ever a **difference between disk and git**, so a
test that reads the disk cannot see it.

## What actually happened on 2026-09-07

Five `model_registry` rows were `is_active=1` pointing at `.pkl` files that
existed on one laptop and in no commit. The worker deploys from git.

**It did not break.** `models/trainer.py` falls back to the `model_artifacts`
table when a path is missing, and it ran:

```
14:26:42 SUCCESS | Restored models/saved/nfl_prop_sacks_20260907_052908.pkl
                   from Supabase (1,168,861 bytes)
14:26:43 INFO    |   nfl_prop_sacks: no scoring rows for 2026-09-07
```

All five blobs were present, byte-for-byte. So committing the files (#540) was
**hygiene, not an incident** — the "five models score nothing, silently"
framing that went with it was never established and the logs contradict it.

**The defect was the check.** Twice that afternoon it printed:

```
[CRIT] model_artifacts_load: OK — all 56 active artifacts deserialise
```

having opened 51. A missing file hit a bare `continue` while the summary
reported `len(rows)` — a count of rows enumerated, never of files opened.

The restore happened to save it. **The check would have printed the identical
`OK` with no blob to restore from**, which is precisely when the model is dead.

## What guards it now

**At merge time** — `tests/test_model_artifacts_load.py`:

- `test_every_model_artifact_on_disk_is_tracked_by_git` — any `.pkl` under
  `models/saved/` that git is neither tracking nor ignoring fails the suite, on
  the machine that has it. Ignore rules come from `git check-ignore`, so
  `models/saved/_baseline/` (throwaway `--no-register` comparison runs) stays
  excluded by `.gitignore` rather than by this test's memory of it.
- `test_the_tripwire_can_actually_see_an_untracked_artifact` — plants a probe
  and asserts it is spotted. The real test passes on a clean tree, which looks
  identical to a test that inspects nothing.

**At runtime** — `tracking/system_health.model_artifacts_load` now counts what
it opened and separates:

| state | verdict |
|---|---|
| present, will not deserialise | `CRIT` — registered and dead |
| absent, **no blob** to restore from | `CRIT` — registered and dead |
| absent, restorable from Supabase | `WARN` — repo and registry disagree, commit it |
| present and loads | `OK`, reporting the **opened** count |

## If the tripwire fails on you

Almost always `git add` the file it names — that is
`.claude/rules/operations.md`'s first rule. Deleting it is equally valid if the
retrain was a throwaway. Leaving it untracked is the one option that is not:
the registry may already point at it, and then the repo and production disagree
about what the model is.
