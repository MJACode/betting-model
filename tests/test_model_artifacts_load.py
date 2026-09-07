"""Every committed model artifact must actually deserialise.

WHY THIS EXISTS. All twelve `nfl_prop_*` artifacts committed in #215 on
2026-08-23 were unloadable: `pickle.load` raised
`XGBoostError: input stream corrupted` inside `XGBoosterUnserializeFromBuffer`.
They sat in master for two weeks and nothing noticed, because:

  * the family was in PAUSED_MODELS, so no scorer ever called load_model on
    them — a paused model is never opened; and
  * tracking/system_health's `model_registry` check asks only whether an ACTIVE
    REGISTRY ROW EXISTS. A row pointing at a corrupt file passes it. The check
    stats the registry, not the bytes.

It was found only when the models were unpaused (2026-09-06) and the scorer
tried to load one for real. This test is the missing tripwire: it opens the
bytes, which is the only thing that distinguishes a model from a file.

Not a version-skew guard. On the interpreter that found this, 31 other xgboost
artifacts — including five declaring the SAME xgboost 3.4.1 as the broken NFL
ones — loaded fine on the same run.
"""
from __future__ import annotations

import pickle
import warnings
from collections import defaultdict
from pathlib import Path

import pytest

SAVED = Path(__file__).resolve().parent.parent / "models" / "saved"


def _newest_per_model() -> list[Path]:
    """One artifact per model id — the newest, which is the one a fresh
    registry row points at. Loading all ~43 would spend most of the runtime
    re-proving superseded versions that nothing will ever open again."""
    by_stem: dict[str, list[Path]] = defaultdict(list)
    for p in SAVED.glob("*.pkl"):
        # "<model_id>_<YYYYmmdd>_<HHMMSS>.pkl" -> model_id
        parts = p.stem.rsplit("_", 2)
        if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
            by_stem[parts[0]].append(p)
    return [max(v, key=lambda q: q.stem) for v in by_stem.values()]


ARTIFACTS = sorted(_newest_per_model())


def test_there_are_artifacts_to_check():
    """A glob that silently matches nothing would make every case below pass."""
    assert len(ARTIFACTS) > 20, f"only found {len(ARTIFACTS)} artifacts in {SAVED}"


@pytest.mark.parametrize("path", ARTIFACTS, ids=lambda p: p.stem)
def test_artifact_deserialises(path: Path):
    """The bytes must round-trip into a real object.

    sklearn's InconsistentVersionWarning is expected and tolerated — it means
    the estimator loaded. An xgboost buffer that cannot be parsed RAISES, and
    that is what this catches.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with open(path, "rb") as fh:
            artifact = pickle.load(fh)
    assert artifact is not None
    if isinstance(artifact, dict):
        assert "model" in artifact, f"{path.name} has no 'model' key"
        # A NULL `model` is legitimate for a RULE. ncaaf_spread and
        # ncaaf_spread_premium are kind='cross_book_opener': there is no fitted
        # estimator, the artifact carries the rule's parameters (d_threshold,
        # model_prob) and that IS the model. Asserting a non-None estimator here
        # failed both of them on the first run of this file — a false positive
        # that would have blocked every merge while both artifacts were fine.
        #
        # So the property is "carries something usable", not "carries an
        # estimator": a rule must still bring the numbers that make it a rule.
        if artifact["model"] is None:
            assert artifact.get("kind"), (
                f"{path.name} has model=None and no `kind` — that is a broken "
                f"artifact, not a rule")
            assert any(artifact.get(k) is not None
                       for k in ("d_threshold", "model_prob", "prob_at_threshold")), (
                f"{path.name} is a {artifact['kind']} rule carrying no parameters")


@pytest.mark.parametrize(
    "model_id",
    ["nfl_prop_pass_yards", "nfl_prop_pass_attempts", "nfl_prop_pass_completions",
     "nfl_prop_pass_tds", "nfl_prop_rush_yards", "nfl_prop_rush_attempts",
     "nfl_prop_rec_yards", "nfl_prop_receptions", "nfl_prop_rush_rec_yards",
     "nfl_prop_anytime_td", "nfl_prop_tackles_assists", "nfl_prop_sacks"],
)
def test_every_unpaused_nfl_prop_model_has_a_loadable_artifact(model_id):
    """Named individually rather than globbed: these twelve went live on
    2026-09-06 off placeholder thresholds, so an unloadable one is a model
    that silently scores nothing on a slate someone is betting."""
    matches = [p for p in ARTIFACTS if p.stem.rsplit("_", 2)[0] == model_id]
    assert matches, f"no committed artifact for {model_id}"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with open(matches[0], "rb") as fh:
            artifact = pickle.load(fh)
    assert artifact["model"] is not None
    assert artifact["feature_cols"], f"{model_id} artifact carries no feature_cols"


def test_the_health_check_opens_the_artifact_not_just_the_registry_row():
    """The production-side twin of this file.

    tracking/system_health's `model_registry` check asks whether an ACTIVE ROW
    exists. A row pointing at a corrupt file passes it, which is precisely how
    twelve dead nfl_prop_* models reported healthy for two weeks — nothing else
    opens a paused model either. The `model_artifacts_load` check added
    2026-09-06 deserialises each active artifact; on the run that introduced it,
    against production, it reported:

        [WARN] model_registry:       OK    — 51 expected models all active
        [CRIT] model_artifacts_load: STALE — 10 active artifact(s) will not
               deserialise — the model is registered and DEAD: ...

    Two checks, same models, opposite verdicts. That gap is the thing.
    """
    import inspect

    from tracking import system_health

    src = inspect.getsource(system_health.run_system_health)
    assert "model_artifacts_load" in src, src
    assert "pickle.load" in src, "the check must OPEN the file, not stat it"
    # CRIT, not WARN: a registered model that cannot load is silently betting
    # nothing on a slate someone is watching.
    assert '"model_artifacts_load", STALE, "CRIT"' in src, src


# ---------------------------------------------------------------------------
# THE OTHER HALF: the file has to be IN GIT, not merely on somebody's disk.
#
# Everything above opens bytes that are sitting in `models/saved/`. That answers
# "is this a working model?" and cannot answer "will the worker have it?",
# because the worker deploys from git and has never seen this machine's disk.
#
# 2026-09-07, two days before Week 1: five model_registry rows were is_active=1
# and pointed at .pkl files that existed on one laptop and in no commit on any
# branch. Five of the eleven models unpaused in #536 would have scored nothing
# in production, silently, and every check we had said fine — the registry check
# saw an active row, and the loader test above happily opened the local file.
#
# The bug is only ever visible as a DIFFERENCE between disk and git, so the test
# for it has to ask git.
# ---------------------------------------------------------------------------

import subprocess

ROOT = Path(__file__).resolve().parent.parent


def _git(*args: str) -> str:
    return subprocess.run(("git", *args), cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", check=True).stdout


def _ignored(rel_paths: list[str]) -> set[str]:
    """Paths git is deliberately ignoring — derived from .gitignore, not guessed.

    `models/saved/_baseline/` is the real case: `--no-register` comparison runs
    land there and are meant to be thrown away. Asking git keeps this test from
    carrying its own stale copy of that rule.
    """
    if not rel_paths:
        return set()
    proc = subprocess.run(("git", "check-ignore", "--stdin"), cwd=ROOT,
                          input="\n".join(rel_paths), capture_output=True,
                          text=True, encoding="utf-8")
    # exit 0 = some ignored, 1 = none ignored, 128 = real error
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"git check-ignore failed: {proc.stderr}")
    return {line.strip().replace("\\", "/") for line in proc.stdout.splitlines() if line.strip()}


def test_every_model_artifact_on_disk_is_tracked_by_git():
    """A retrain that is never committed is a model that only exists here.

    This is the check that would have caught 2026-09-07 at the moment it
    happened, on the machine that had the files, instead of two days later by
    audit. It needs no database and no network: an untracked .pkl under
    models/saved/ IS the bug, whatever the registry currently says.

    If this fails, the fix is almost always `git add` the named file — see
    .claude/rules/operations.md, "a retrained model must have its .pkl
    COMMITTED". Deleting the file is also a valid fix if the retrain was a
    throwaway; leaving it untracked is not.
    """
    saved = ROOT / "models" / "saved"
    on_disk = sorted(p.relative_to(ROOT).as_posix() for p in saved.rglob("*.pkl"))
    if not on_disk:
        pytest.skip("no artifacts on disk")

    tracked = {line.strip() for line in _git("ls-files", "models/saved").splitlines()}
    ignored = _ignored(on_disk)

    untracked = [p for p in on_disk if p not in tracked and p not in ignored]
    assert not untracked, (
        f"{len(untracked)} model artifact(s) exist on disk but are NOT in git:\n  "
        + "\n  ".join(untracked)
        + "\n\nThe Railway worker deploys from git, so it will not have these. "
        "If a registry row points at one, that model is registered and DEAD in "
        "production while every other check reports healthy. `git add` them, or "
        "delete them if the retrain was a throwaway."
    )


def test_the_tripwire_can_actually_see_an_untracked_artifact():
    """Proves the check above is capable of failing.

    A guard that dead code can satisfy is not a guard (CLAUDE.md §1b). The real
    test passes on a clean tree, which looks identical to a test that inspects
    nothing — so this plants an untracked .pkl, asserts it is spotted, and
    removes it.
    """
    saved = ROOT / "models" / "saved"
    planted = saved / "_tripwire_probe_00000000_000000.pkl"
    planted.write_bytes(b"not a real model")
    try:
        rel = planted.relative_to(ROOT).as_posix()
        tracked = {ln.strip() for ln in _git("ls-files", "models/saved").splitlines()}
        assert rel not in tracked, "the probe file was somehow already tracked"
        assert rel not in _ignored([rel]), (
            "models/saved/*.pkl is gitignored, which would make the tripwire "
            "above silently vacuous for every real artifact too"
        )
    finally:
        planted.unlink(missing_ok=True)


def test_the_health_check_reports_what_it_opened_not_what_it_enumerated():
    """The 2026-09-07 false OK, in one line of production log:

        [CRIT] model_artifacts_load: OK — all 56 active artifacts deserialise

    It had opened 51. Five active artifacts were absent from the worker, hit a
    bare `continue`, and were counted as successes by `len(rows)` — a number
    that was never the number of files opened. Nothing was actually dead that
    day, because the artifact WAS restorable from Supabase and the restore ran
    ("Restored models/saved/nfl_prop_sacks_...pkl from Supabase (1,168,861
    bytes)"). But the check would have printed the identical OK with no blob to
    restore from, which is the case where the model really is dead.

    `.claude/rules/operations.md`: a health check must not gate on the thing
    that breaks, and an empty result must not look like a healthy one.
    """
    import inspect

    from tracking import system_health

    src = inspect.getsource(system_health.run_system_health)
    assert "opened" in src, "the check must track how many artifacts it OPENED"
    assert "f\"all {len(rows)} active artifacts deserialise\"" not in src, (
        "the summary still reports the ROW count rather than the opened count — "
        "that is the false OK this test exists for"
    )
    assert "missing_files" in src, "a missing artifact must be reported, not skipped"
    assert "NO BLOB" in src, (
        "missing-with-no-restorable-blob is the DEAD case and must be "
        "distinguished from missing-but-restorable"
    )
