"""Nothing that cost money or time lives only on disk.

mike, 2026-09-12: *"EVERYTHING SHOULD BE IN SUPABASE FOR THE MILLIONTH FUCKING
TIME. Need a global rule."* CLAUDE.md section 1b carries it.

THE FAILURE THIS EXISTS FOR. The rule was already written -- since 2026-08-30 --
and was broken anyway, because it carried a list of known exceptions "worth
fixing when touched" and nobody touched them. `nfl/data/odds_cache` held 655 MB
across 6,769 files of PAID Odds API history (NFL 2020-2026, every book) while
`odds` held NFL rows for 2026 only. A rule with a standing exception is not a
rule; this is the mechanical half.

WHAT IT CHECKS. Every directory in the repo that holds a meaningful amount of
data-shaped file (json / jsonl / csv / parquet / pkl) must be either:

  * a DECLARED CACHE of Supabase -- gitignored, regenerable, every row already
    in the database (`data/local_store.py` is the sanctioned shape); or
  * model artifacts, which are versioned code, not data; or
  * a test fixture.

Anything else is a primary store outside the system of record. **When this
fails, the fix is an importer, not an entry in the allowlist** -- and an
allowlist entry that names an importer is only honest while that importer
exists and resumes, which the tests below check rather than trust.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA_SUFFIXES = {".json", ".jsonl", ".csv", ".parquet", ".pkl", ".npz", ".txt"}
# A directory has to hold at least this much before it counts as a store rather
# than a handful of config or fixture files.
MIN_FILES = 25

# Directories that may hold data files, each with the reason.
ALLOWED = {
    # A cache OF Supabase: opt-in, gitignored, regenerable in one command, and
    # every row of it already in the database (data/local_store.py).
    "data/local": "declared cache of Supabase",
    # Versioned code, not data: the scorer loads these and a retrain commits
    # the new .pkl (.claude/rules/operations.md).
    "models/saved": "model artifacts, versioned with the code",
    "ncaaf_live/data/artifacts": "engine artifacts, versioned with the code",
    "nfl/live_model/artifacts": "engine artifacts, versioned with the code",
    # Fixtures and schema, not acquired data.
    # The 655 MB that produced this rule. Every file is now in `odds` via
    # data/ingestors/nfl_odds_cache_import.py (pinned by the test below), so
    # what remains on disk is a cache of Supabase -- the sanctioned shape --
    # rather than the only copy. Declared with the importer, never on its own.
    "nfl/data/odds_cache": "imported to Supabase by nfl_odds_cache_import.py",
    "tests": "test fixtures",
    "tests/fixtures": "test fixtures",
    "data/migrations": "schema",
    "jobs": "declared job manifests",
    "docs": "documentation",
    "mobile": "app source",
    ".github": "workflows",
}

SKIP_PARTS = {".git", "node_modules", "__pycache__", ".venv", "venv",
              ".pytest_cache", ".expo", "build", "dist", ".claude"}


def _data_dirs() -> dict[str, int]:
    counts: dict[str, int] = {}
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in DATA_SUFFIXES:
            continue
        rel = p.relative_to(ROOT)
        if SKIP_PARTS & set(rel.parts):
            continue
        d = str(rel.parent).replace("\\", "/")
        counts[d] = counts.get(d, 0) + 1
    return counts


def _allowed(d: str) -> bool:
    return any(d == a or d.startswith(a + "/") for a in ALLOWED)


def test_no_undeclared_data_store_on_disk():
    offenders = {d: n for d, n in _data_dirs().items()
                 if n >= MIN_FILES and not _allowed(d)}
    assert not offenders, (
        "these directories hold data outside Supabase:\n  "
        + "\n  ".join(f"{d}: {n} files" for d, n in sorted(offenders.items()))
        + "\n\nThe fix is an importer that writes them to Supabase keyed for "
          "resume (data/ingestors/nfl_odds_cache_import.py is the shape), NOT "
          "an entry in ALLOWED. A local file is a cache of Supabase or it is a "
          "bug (CLAUDE.md section 1b)."
    )


def test_the_nfl_odds_cache_has_an_importer():
    """The 655 MB that produced this rule. The directory may still exist as a
    working cache; what must exist is the path INTO Supabase."""
    imp = ROOT / "data" / "ingestors" / "nfl_odds_cache_import.py"
    assert imp.exists()
    src = imp.read_text(encoding="utf-8")
    assert "_insert_odds" in src, "it must write to the odds table"
    assert "stored_served" in src and "already in Supabase" in src, (
        "a buy-once importer must resume rather than re-import")


def test_the_rule_is_loaded_on_every_session_and_has_no_exceptions():
    """It has to be in CLAUDE.md, not in a path-scoped rules file.

    `.claude/rules/*.md` load only when a file matching their `paths:`
    frontmatter is opened. That is right for rules about one area and WRONG for
    this one: a session that never opens `data/` can still buy a season and
    drop it on disk. So the text must be in the file every session reads, and
    this asserts where it lives, not merely that it exists somewhere."""
    always_loaded = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "EVERYTHING GOES IN SUPABASE" in always_loaded, (
        "the rule must be in CLAUDE.md; a path-scoped rules file would leave "
        "it unloaded for exactly the sessions that break it")
    assert "THERE ARE NO EXCEPTIONS" in always_loaded
    # The old wording listed two directories as tolerated exceptions, and that
    # is how 655 MB of paid history sat on a laptop for a fortnight. If the
    # phrasing returns, the rule has been softened back into a suggestion.
    scoped = "".join(p.read_text(encoding="utf-8")
                     for p in (ROOT / ".claude" / "rules").glob("*.md"))         if (ROOT / ".claude" / "rules").is_dir() else ""
    assert "worth fixing when touched" not in always_loaded + scoped


@pytest.mark.parametrize("shape", ["_history", "_import"])
def test_every_buying_ingestor_keys_its_resume_on_a_source_marker(shape):
    """An ingestor that spends money must be re-runnable for free."""
    for p in (ROOT / "data" / "ingestors").glob(f"*{shape}*.py"):
        src = p.read_text(encoding="utf-8")
        if "requests.get" not in src and "_insert_odds" not in src:
            continue
        assert "SOURCE_PREFIX" in src, f"{p.name}: no source marker to resume on"
        assert "source LIKE" in src or "source like" in src, (
            f"{p.name}: nothing reads the marker back, so a re-run re-buys")


def test_the_importer_resolves_a_postponed_game():
    """The payload carries the SCHEDULED kickoff; `games` carries the date
    played. The 2024-01-14 Steelers-Bills wild card moved to the 15th for a
    blizzard, and matching only backwards in time dropped it -- one of 956
    events lost on the first import, clustered on playoff weekends."""
    from data.ingestors.nfl_odds_cache_import import resolve
    idx = {("2024-01-15", "PIT", "BUF"): "NFL_2023_19_PIT_BUF"}
    ev = {"home_team": "Buffalo Bills", "away_team": "Pittsburgh Steelers",
          "commence_time": "2024-01-14T18:00:00Z"}
    assert resolve(idx, ev) == "NFL_2023_19_PIT_BUF"


def test_the_importer_still_refuses_an_event_with_no_game():
    """Counted and skipped, never invented: a Super-Bowl-week placeholder
    matchup has no `games` row and must not acquire one."""
    from data.ingestors.nfl_odds_cache_import import resolve
    ev = {"home_team": "Baltimore Ravens", "away_team": "Detroit Lions",
          "commence_time": "2024-02-11T23:31:00Z"}
    assert resolve({}, ev) is None


def test_a_rerun_after_the_resolver_improves_adds_only_the_gap():
    """The served-level resume is right for the bulk import and wrong after
    the resolver changes -- every snapshot is stored, so it would skip
    everything while the newly resolved games have no rows. --fill-gaps keys
    on (game_id, served) instead."""
    src = (ROOT / "data" / "ingestors" / "nfl_odds_cache_import.py").read_text(
        encoding="utf-8")
    assert "def stored_pairs(" in src and "--fill-gaps" in src
    body = src[src.index("def main("):]
    assert 'if a.fill_gaps' in body and '(r["game_id"], r["snapshot_at"]) not in pairs' in body
