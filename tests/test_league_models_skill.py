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


# ── Every new model and every new sport teaches the skill ─────────────────────
#
# The skill learns only when a build writes back (SKILL.md, "How this skill
# learns"). The Stop hook (.claude/hooks/league_models_writeback.py) reminds a
# session that used the skill; this catches a build that never opened it. Any
# model in config.ACTION_THRESHOLDS, or any sport the odds feed or Discord
# knows, that is not in the frozen sets below must be named in the learning
# log before it can merge.
#
# FROZEN 2026-11-13 (82 models, 11 sports). Never add to these sets: a new id
# goes in a learning-log entry instead, which is the point.
MODELS_BEFORE_THE_LOG = frozenset("""
mlb_f5_moneyline mlb_f5_over_under mlb_f5_runline mlb_live_total_runs mlb_moneyline
mlb_over_under mlb_prop_batter_hits mlb_prop_batter_runs mlb_prop_batter_sb
mlb_prop_batter_tb mlb_prop_batter_walks mlb_prop_pitcher_er mlb_prop_pitcher_hits
mlb_prop_pitcher_k mlb_prop_pitcher_outs mlb_prop_pitcher_walks mlb_runline
mlb_spread_market mlb_total_market mlb_total_public_fade nba_first_half_total_luck
nba_live_spread_q12 nba_prop_market nba_prop_projection nba_q1_trend nba_q1_trend_ml
nba_team_total_luck nba_total_luck ncaab_first_half_spread ncaab_first_half_total
ncaab_live_spread_h1 ncaab_live_spread_h2 ncaab_live_total_h2 ncaab_moneyline_first_post
ncaab_moneyline_own_spread ncaab_spread_market ncaab_total_blend ncaabw_live_total_ht
ncaabw_total_blend ncaaf_live_total ncaaf_live_win_prob ncaaf_moneyline
ncaaf_moneyline_market ncaaf_over_under ncaaf_spread ncaaf_spread_premium
nfl_live_leader_ml nfl_opener_spread nfl_prop_anytime_td nfl_prop_market
nfl_prop_pass_attempts nfl_prop_pass_completions nfl_prop_pass_tds nfl_prop_pass_yards
nfl_prop_rec_yards nfl_prop_receptions nfl_prop_rush_attempts nfl_prop_rush_rec_yards
nfl_prop_rush_yards nfl_prop_sacks nfl_prop_tackles_assists nfl_wind_totals
nhl_moneyline nhl_moneyline_regulation nhl_over_under nhl_prop_assists
nhl_prop_blocked_shots nhl_prop_saves nhl_prop_shots_on_goal nhl_puckline
ufc_method_of_victory ufc_moneyline ufc_total_rounds wnba_moneyline wnba_over_under
wnba_prop_market wnba_prop_player_assists wnba_prop_player_points wnba_prop_player_pra
wnba_prop_player_rebounds wnba_prop_player_threes wnba_spread
""".split())
SPORTS_BEFORE_THE_LOG = frozenset(
    "EUROLEAGUE GOLF MLB NBA NCAAB NCAABW NCAAF NFL NHL UFC WNBA".split())


def _odds_feed_sports() -> set[str]:
    """SPORT_KEYS' keys, read from the source (importing the ingestor pulls in the database layer)."""
    text = _read(os.path.join(ROOT, "data", "ingestors", "odds_ingestor.py"))
    block = re.search(r"^SPORT_KEYS\s*(?::[^=]+)?=\s*\{(.*?)^\}", text, re.S | re.M)
    assert block, "SPORT_KEYS not found in data/ingestors/odds_ingestor.py: update this test"
    return set(re.findall(r'^\s*"([A-Z0-9_]+)"\s*:', block.group(1), re.M))


def _unlogged(names, frozen, log_text, *, ignore_case=False):
    hay = log_text.lower() if ignore_case else log_text
    return sorted(n for n in set(names) - set(frozen)
                  if not re.search(rf"\b{re.escape(n.lower() if ignore_case else n)}\b", hay))


def _log_text() -> str:
    return _read(os.path.join(REF_DIR, "learning-log.md"))


def test_every_new_model_is_named_in_the_learning_log():
    import config
    missing = _unlogged(config.ACTION_THRESHOLDS, MODELS_BEFORE_THE_LOG, _log_text())
    assert not missing, (
        f"New model(s) {missing} are not named in "
        ".claude/skills/league-models/references/learning-log.md. Every model "
        "build teaches the skill: add a dated entry (newest first) naming each "
        "id, with what was tried, what was new, what was corrected and what in "
        "the framework changed, and write each new method, trap or source into "
        "its reference file. See SKILL.md, step 9."
    )


def test_every_new_sport_is_named_in_the_learning_log():
    import config
    sports = _odds_feed_sports() | set(getattr(config, "DISCORD_SPORTS", ()))
    missing = _unlogged(sports, SPORTS_BEFORE_THE_LOG, _log_text(), ignore_case=True)
    assert not missing, (
        f"New sport(s) {missing} are not named in the league-models learning "
        "log. A new league is built with /league-models and logged there "
        "(SKILL.md, step 9)."
    )


def test_the_rule_catches_an_unlogged_model_and_passes_a_logged_one():
    log = "## 2026-12-01 — WNBA\n\n3. **New.** `wnba_total_pace` ..."
    assert _unlogged({"wnba_total_pace", "wnba_q1_spread"}, set(), log) == ["wnba_q1_spread"]
    assert _unlogged({"NCAAB_X"}, set(), "ncaab_x built", ignore_case=True) == []
    assert _unlogged({"mlb_moneyline"}, MODELS_BEFORE_THE_LOG, "") == []
