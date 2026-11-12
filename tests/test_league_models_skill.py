"""The /league-models skill must not cite things that no longer exist.

The skill (.claude/skills/league-models/) tells every new-league build which
files to open, which settings to add and which tests to extend. Those names
move: a module is renamed, a config dict is split, a doc is retired. A skill
that still cites the old name sends the next build to the wrong place, and
nothing else in the suite would notice. This test is what corrects the skill
when nobody is using it: whoever moves a cited file or setting sees it fail
and updates the skill in the same change (SKILL.md, "How this skill learns,
corrects and evolves").

What it checks:
  * the frontmatter parses, and its name is the folder's name;
  * SKILL.md names every reference file, and every reference file it names
    exists;
  * every repo path in backticks exists (a file, a folder, a module, or a
    module plus a name defined in it);
  * every UPPER_CASE setting in backticks is defined somewhere in the code;
  * the learning log's entries are dated and newest first.

Placeholders (`<league>`, `<id>`, `*`) are skipped: they are templates, not
citations.
"""
from __future__ import annotations

import os
import re

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR = os.path.join(ROOT, ".claude", "skills", "league-models")
REF_DIR = os.path.join(SKILL_DIR, "references")

PATH_ROOTS = (
    "docs/", "models/", "scripts/", "data/", "tracking/", "tests/",
    "mobile/", "monitoring/", "features/", "nfl/", "jobs/", ".claude/",
    "config.py", "run_pipeline.py", "scheduler.py", "railway.json",
)
DOTTED_ROOTS = ("models.", "scripts.", "data.", "tracking.", "monitoring.")
CODE_EXTS = (".py", ".sql", ".ts", ".tsx", ".sh")
SKIP_DIRS = {".git", "node_modules", "graphify-out", "worktrees", "__pycache__",
             ".venv", "venv", "dist", "build", ".expo"}


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _skill_files() -> dict[str, str]:
    files = {"SKILL.md": _read(os.path.join(SKILL_DIR, "SKILL.md"))}
    for name in sorted(os.listdir(REF_DIR)):
        if name.endswith(".md"):
            files[f"references/{name}"] = _read(os.path.join(REF_DIR, name))
    return files


def _ticked(text: str) -> list[str]:
    return re.findall(r"`([^`\n]+)`", text)


def _is_template(token: str) -> bool:
    return any(ch in token for ch in "<>*{}|")


def _code_text() -> str:
    chunks = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(CODE_EXTS):
                try:
                    chunks.append(_read(os.path.join(dirpath, name)))
                except (UnicodeDecodeError, OSError):
                    continue
    return "\n".join(chunks)


def _resolves(token: str) -> bool:
    """A cited path resolves to a file, a folder, a module, or a name in one."""
    token = token.split("::", 1)[0].rstrip("/.,;:()")
    token = token.split(" ", 1)[0]
    if os.path.exists(os.path.join(ROOT, token)):
        return True
    if os.path.exists(os.path.join(ROOT, token + ".py")):
        return True
    if os.path.exists(os.path.join(ROOT, token.replace(".", "/") + ".py")):
        return True
    # module.name or path/module.name: the name must be defined in the module
    head, _, name = token.rpartition(".")
    if not head or not name:
        return False
    for cand in (head, head.replace(".", "/")):
        for path in (cand, cand + ".py"):
            full = os.path.join(ROOT, path)
            if os.path.isfile(full) and re.search(rf"\b{re.escape(name)}\b", _read(full)):
                return True
    return False


def _cited_paths(text: str) -> list[str]:
    out = []
    for tok in _ticked(text):
        tok = tok.strip()
        if _is_template(tok) or " " in tok.split("::", 1)[0].strip():
            continue
        if tok.startswith(PATH_ROOTS) or tok.startswith(DOTTED_ROOTS):
            out.append(tok)
    return out


def _cited_settings(text: str) -> list[str]:
    out = []
    for tok in _ticked(text):
        tok = tok.strip()
        if _is_template(tok):
            continue
        tok = re.sub(r"^config\.", "", tok)
        tok = re.sub(r"\[.*\]$", "", tok).strip()
        if re.fullmatch(r"_?[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+", tok):
            out.append(tok)
    return out


def test_the_frontmatter_parses_and_names_the_folder():
    text = _read(os.path.join(SKILL_DIR, "SKILL.md"))
    assert text.startswith("---\n"), "SKILL.md must open with YAML frontmatter"
    meta = yaml.safe_load(text.split("---", 2)[1])
    assert meta["name"] == os.path.basename(SKILL_DIR)
    assert len(meta["description"]) > 100


def test_skill_md_names_every_reference_file_and_each_exists():
    skill = _read(os.path.join(SKILL_DIR, "SKILL.md"))
    on_disk = {f"references/{n}" for n in os.listdir(REF_DIR) if n.endswith(".md")}
    named = set(re.findall(r"`(references/[a-z0-9-]+\.md)`", skill))
    assert on_disk - named == set(), f"reference files SKILL.md never names: {sorted(on_disk - named)}"
    assert named - on_disk == set(), f"SKILL.md names reference files that do not exist: {sorted(named - on_disk)}"


def test_every_cited_repo_path_still_exists():
    missing = []
    for fname, text in _skill_files().items():
        for tok in _cited_paths(text):
            if not _resolves(tok):
                missing.append(f"{fname}: `{tok}`")
    assert not missing, (
        "The league-models skill cites paths that no longer exist. Update the "
        "skill in the same change that moved them, and log it in "
        "references/learning-log.md:\n  " + "\n  ".join(missing)
    )


def test_every_cited_setting_is_still_defined():
    code = _code_text()
    missing = []
    for fname, text in _skill_files().items():
        for tok in sorted(set(_cited_settings(text))):
            if not re.search(rf"\b{re.escape(tok)}\b", code):
                missing.append(f"{fname}: `{tok}`")
    assert not missing, (
        "The league-models skill cites settings no code defines any more. "
        "Update the skill in the same change, and log it in "
        "references/learning-log.md:\n  " + "\n  ".join(missing)
    )


def test_the_learning_log_is_dated_and_newest_first():
    log = _read(os.path.join(REF_DIR, "learning-log.md"))
    dates = re.findall(r"^## (\d{4}-\d{2}-\d{2}) — ", log, flags=re.M)
    assert dates, "the learning log has no dated entries"
    assert dates == sorted(dates, reverse=True), f"entries out of order: {dates}"
