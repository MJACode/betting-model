"""PR CI fails a mobile typecheck error that is not already baselined.

The OTA step ignores `scripts/` and `src/lib/queries.ts`. This gate does not.
`scripts/` is keyed by file and TS code, because those messages name the type
shape. App source keeps the message. Counts are not pinned: regenerating
`mobile/tsc-baseline.txt` must not require an edit here.

The machines that run this suite have no node, so the check is the filter,
not a live `tsc` run. `.github/workflows/pr-ci.yml` runs `tsc`.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "mobile" / "tsc-baseline.txt"
CHECKER = ROOT / "mobile" / "scripts" / "check_tsc_baseline.py"
PR_CI = ROOT / ".github" / "workflows" / "pr-ci.yml"

_SCRIPTS_KEY = re.compile(r"^scripts/\S+\.tsx? TS\d+$")
_APP_KEY = re.compile(r"^(?!scripts/)\S+\.tsx? TS\d+ .+$")

# The ten diagnostics #942 introduced. They are app source, so the message
# is part of the key, and they are not in the baseline.
_PR_942 = [
    "src/lib/customModelBacktest.ts TS2559 Type 'SettledPick' has no properties in common with type '{ discordPublish?: DiscordPublish | null | undefined; }'.",
    "src/lib/playerDetail.ts TS2339 Property 'discordPublish' does not exist on type 'SettledPick'.",
    "src/lib/playerDetail.ts TS2559 Type 'SettledPick' has no properties in common with type '{ discordPublish?: DiscordPublish | null | undefined; }'.",
    "src/lib/teamDetail.ts TS2339 Property 'discordPublish' does not exist on type 'SettledPick'.",
    "src/lib/teamDetail.ts TS2559 Type 'SettledPick' has no properties in common with type '{ discordPublish?: DiscordPublish | null | undefined; }'.",
    "src/screens/BuiltInModelDetailScreen.tsx TS2339 Property 'discordPublish' does not exist on type 'SettledPick'.",
    "src/screens/BuiltInModelDetailScreen.tsx TS2339 Property 'discordPublish' does not exist on type 'SettledPick'.",
    "src/screens/BuiltInModelDetailScreen.tsx TS2339 Property 'discordPublish' does not exist on type 'SettledPick'.",
    "src/screens/BuiltInModelDetailScreen.tsx TS2559 Type 'SettledPick' has no properties in common with type '{ discordPublish?: DiscordPublish | null | undefined; }'.",
    "src/screens/BuiltInModelDetailScreen.tsx TS2559 Type 'SettledPick' has no properties in common with type '{ discordPublish?: DiscordPublish | null | undefined; }'.",
]


def _entries() -> list[str]:
    return [
        line
        for line in BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def _log_line(entry: str, line_no: int, message: str | None = None) -> str:
    if _SCRIPTS_KEY.fullmatch(entry):
        path, code = entry.rsplit(" ", 1)
        text = message if message is not None else "placeholder message"
    else:
        match = _APP_KEY.fullmatch(entry)
        assert match, entry
        path, code, text = entry.split(" ", 2)
        if message is not None:
            text = message
    return f"{path}({line_no},1): error {code}: {text}"


def _log(entries: list[str], scripts_message: str | None = None) -> str:
    lines = []
    for i, entry in enumerate(entries, start=1):
        override = scripts_message if entry.startswith("scripts/") else None
        lines.append(_log_line(entry, i, override))
    return "\n".join(lines) + ("\n" if lines else "")


def _run(log: str, tmp_path: Path, baseline: Path | None = None) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "tsc.log"
    path.write_text(log, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(CHECKER), str(path), str(baseline or BASELINE)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_baseline_keys_do_not_pin_a_count() -> None:
    """Regenerating the file changes how many lines it has. The shape does not."""
    text = BASELINE.read_text(encoding="utf-8")
    entries = _entries()
    for entry in entries:
        assert _SCRIPTS_KEY.fullmatch(entry) or _APP_KEY.fullmatch(entry), entry
    assert all("discordPublish" not in entry for entry in entries)
    assert "file and TS code only" in text
    assert "mobile-ota.yml ignores" in text
    assert "mobile/ci/tsc-baseline.txt" in text
    assert "::warning::" in text


def test_pr_ci_documents_the_stricter_gate() -> None:
    yml = PR_CI.read_text(encoding="utf-8")
    checker = CHECKER.read_text(encoding="utf-8")
    assert "\n  mobile-tsc:" in yml
    mobile, pytest_job = yml.split("\n  mobile-tsc:", 1)[1].split("\n  pytest-subset:", 1)
    assert "npx tsc --noEmit" in mobile
    assert "scripts/check_tsc_baseline.py tsc.log tsc-baseline.txt" in mobile
    assert "cache: npm" in mobile
    assert "cache-dependency-path: mobile/package-lock.json" in mobile
    assert "Stricter than mobile-ota.yml" in mobile
    assert "file + TS code only" in mobile
    assert "mobile/ci/tsc-baseline.txt" in mobile
    assert "check_tsc_baseline.py" not in pytest_job
    assert "tests/test_mobile_tsc_baseline.py" in pytest_job
    assert "file and TS code only" in checker
    assert "mobile/ci/tsc-baseline.txt" in checker


def test_the_known_diagnostics_pass_at_any_line(tmp_path: Path) -> None:
    result = _run(_log(_entries()), tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "not in baseline: 0" in result.stdout
    assert "stale: 0" in result.stdout


def test_a_rewritten_scripts_message_stays_in_baseline(tmp_path: Path) -> None:
    result = _run(
        _log(_entries(), scripts_message="Type 'X' is missing clvGameSettled and 5 more."),
        tmp_path,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "not in baseline: 0" in result.stdout


def test_an_extra_copy_of_a_known_diagnostic_fails(tmp_path: Path) -> None:
    entries = _entries()
    assert entries, "baseline has no diagnostics to copy"
    result = _run(_log(entries + [entries[0]]), tmp_path)
    assert result.returncode == 1
    assert "not in baseline: 1" in result.stdout


def test_a_different_app_message_fails(tmp_path: Path) -> None:
    entries = _entries()
    app = next(entry for entry in entries if not entry.startswith("scripts/"))
    path, code, _message = app.split(" ", 2)
    changed = f"{path} {code} Conversion of type 'BrandNew' to type 'BrandNew'."
    result = _run(_log(entries + [changed]), tmp_path)
    assert result.returncode == 1
    assert "not in baseline: 1" in result.stdout
    assert "BrandNew" in result.stdout


def test_the_942_discord_publish_diagnostics_fail(tmp_path: Path) -> None:
    result = _run(_log(_entries() + _PR_942), tmp_path)
    assert result.returncode == 1
    assert "not in baseline: 10" in result.stdout
    assert "BuiltInModelDetailScreen.tsx" in result.stdout
    assert "playerDetail.ts" in result.stdout
    assert "teamDetail.ts" in result.stdout
    assert "customModelBacktest.ts" in result.stdout


def test_a_fixed_baseline_entry_warns_and_does_not_fail(tmp_path: Path) -> None:
    entries = _entries()
    assert len(entries) >= 1
    result = _run(_log(entries[:-1]), tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "stale: 1" in result.stdout
    assert "::warning::stale baseline entry no longer reported:" in result.stdout
    assert entries[-1] in result.stdout


def test_a_compiler_crash_is_not_a_clean_run(tmp_path: Path) -> None:
    result = _run("npm ERR! missing typescript\n", tmp_path)
    assert result.returncode == 1
    assert "did not run cleanly" in result.stdout


def test_a_clean_log_warns_for_every_baseline_entry(tmp_path: Path) -> None:
    result = _run("", tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"stale: {len(_entries())}" in result.stdout
