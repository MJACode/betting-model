"""PR CI must fail a mobile typecheck error that is not already baselined.

#942 read `discordPublish` on `SettledPick` without declaring it. `tsc` grew
ten diagnostics outside `queries.ts`, the OTA Typecheck step skipped Publish,
and every later mobile merge was blocked. The known 31 diagnostics are
`mobile/tsc-baseline.txt`. This pins the filter that would have rejected that
diff. The machines that run this suite have no node, so the check is the
filter, not a live `tsc` run; `.github/workflows/pr-ci.yml` runs `tsc`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "mobile" / "tsc-baseline.txt"
CHECKER = ROOT / "mobile" / "scripts" / "check_tsc_baseline.py"
PR_CI = ROOT / ".github" / "workflows" / "pr-ci.yml"

# The ten diagnostics #942 introduced, location stripped the way the baseline is.
_PR_942 = [
    "src/lib/customModelBacktest.ts: error TS2559: Type 'SettledPick' has no properties in common with type '{ discordPublish?: DiscordPublish | null | undefined; }'.",
    "src/lib/playerDetail.ts: error TS2339: Property 'discordPublish' does not exist on type 'SettledPick'.",
    "src/lib/playerDetail.ts: error TS2559: Type 'SettledPick' has no properties in common with type '{ discordPublish?: DiscordPublish | null | undefined; }'.",
    "src/lib/teamDetail.ts: error TS2339: Property 'discordPublish' does not exist on type 'SettledPick'.",
    "src/lib/teamDetail.ts: error TS2559: Type 'SettledPick' has no properties in common with type '{ discordPublish?: DiscordPublish | null | undefined; }'.",
    "src/screens/BuiltInModelDetailScreen.tsx: error TS2339: Property 'discordPublish' does not exist on type 'SettledPick'.",
    "src/screens/BuiltInModelDetailScreen.tsx: error TS2339: Property 'discordPublish' does not exist on type 'SettledPick'.",
    "src/screens/BuiltInModelDetailScreen.tsx: error TS2339: Property 'discordPublish' does not exist on type 'SettledPick'.",
    "src/screens/BuiltInModelDetailScreen.tsx: error TS2559: Type 'SettledPick' has no properties in common with type '{ discordPublish?: DiscordPublish | null | undefined; }'.",
    "src/screens/BuiltInModelDetailScreen.tsx: error TS2559: Type 'SettledPick' has no properties in common with type '{ discordPublish?: DiscordPublish | null | undefined; }'.",
]


def _entries() -> list[str]:
    return [
        line
        for line in BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def _log(entries: list[str]) -> str:
    lines = []
    for i, entry in enumerate(entries, start=1):
        path, rest = entry.split(": ", 1)
        lines.append(f"{path}({i},1): {rest}")
    return "\n".join(lines) + ("\n" if lines else "")


def _run(log: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "tsc.log"
    path.write_text(log, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(CHECKER), str(path), str(BASELINE)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_the_baseline_is_the_known_31() -> None:
    entries = _entries()
    assert len(entries) == 31
    assert all("discordPublish" not in line for line in entries)
    assert sum(line.startswith("src/lib/queries.ts:") for line in entries) == 22
    assert sum(line.startswith("scripts/") for line in entries) == 9


def test_pr_ci_runs_the_baseline_filter() -> None:
    yml = PR_CI.read_text(encoding="utf-8")
    assert "npx tsc --noEmit" in yml
    assert "scripts/check_tsc_baseline.py tsc.log tsc-baseline.txt" in yml
    assert "tests/test_mobile_tsc_baseline.py" in yml


def test_the_known_diagnostics_pass_at_any_line(tmp_path: Path) -> None:
    result = _run(_log(_entries()), tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_an_extra_copy_of_a_known_diagnostic_fails(tmp_path: Path) -> None:
    entries = _entries()
    result = _run(_log(entries + [entries[0]]), tmp_path)
    assert result.returncode == 1
    assert "not in baseline: 1" in result.stdout


def test_the_942_discord_publish_diagnostics_fail(tmp_path: Path) -> None:
    result = _run(_log(_entries() + _PR_942), tmp_path)
    assert result.returncode == 1
    assert "not in baseline: 10" in result.stdout
    assert "BuiltInModelDetailScreen.tsx" in result.stdout
    assert "playerDetail.ts" in result.stdout
    assert "teamDetail.ts" in result.stdout
    assert "customModelBacktest.ts" in result.stdout


def test_a_compiler_crash_is_not_a_clean_run(tmp_path: Path) -> None:
    result = _run("npm ERR! missing typescript\n", tmp_path)
    assert result.returncode == 1
    assert "did not run cleanly" in result.stdout


def test_a_clean_log_passes(tmp_path: Path) -> None:
    result = _run("", tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
