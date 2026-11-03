"""One unit basis in the app (mike, 2026-11-03).

CLAUDE.md §2: units are the graded set sized by stake_for, 1u to win at
COALESCE(decision_odds, dk_odds), risk capped at 3u, a pick with no price at
1u, the stake the Record tab, Yesterday and Discord book. The model pages, the
Models list, the custom-model backtest and the player and team pages used
profit_flat / 100 (1u risked per pick) instead, so the same model showed two
unit totals and a "1u risked per bet" label explained the difference. These
pin every one of them on the Record's basis. The behavioural half is
mobile/scripts/verify_units_one_basis.ts.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from tests._node import tsx_cmd

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
SRC = MOBILE / "src"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _code(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(
        re.sub(r"\s//\s.*$", "", line)
        for line in text.splitlines()
        if not line.lstrip().startswith("//")
    )


SCREENS = [
    "screens/BuiltInModelDetailScreen.tsx",
    "screens/ModelDetailScreen.tsx",
    "screens/ModelsScreen.tsx",
    "screens/ModelEditScreen.tsx",
]


def test_no_screen_carries_a_second_unit_basis_label():
    bad = re.compile(r"risked per bet|Flat units|Flat ROI|1u/bet|Models risk a flat|won’t match|won\\u2019t match")
    offenders = [
        f"{p.relative_to(SRC).as_posix()}: {m.group(0)}"
        for p in sorted(SRC.rglob("*.ts*"))
        for m in bad.finditer(_code(_read(p)))
    ]
    assert offenders == [], offenders


@pytest.mark.parametrize("rel", SCREENS)
def test_a_record_screen_prints_the_published_units(rel):
    code = _code(_read(SRC / rel))
    for flat in ("stats.profitFlat", "stats.roiFlat", "backtest?.roiFlat", "formatFlatUnits("):
        assert flat not in code, f"{rel} still prints {flat}"


def test_the_model_page_rows_are_the_published_stake():
    screen = _code(_read(SRC / "screens/BuiltInModelDetailScreen.tsx"))
    row = screen[screen.index("function HistoryPickRow"):]
    row = row[: row.index("\n}\n")]
    assert "postedPickUnits(pick).units" in row
    assert "profit_flat" not in row


def test_the_published_view_is_read_with_its_posted_columns():
    q = _read(SRC / "lib/queries.ts")
    assert "'model_id, picks, wins, losses, pushes, profit_flat, staked_flat, units, risked'" in q
    assert "posted_units: r.units == null ? null : Number(r.units)" in q
    # The custom backtest asks for the published stake beside its summary,
    # and stands on the 1u-risked summary only while the function is absent.
    assert "supabase.rpc('custom_model_backtest_posted', args)" in q
    assert "postedFunctionMissing(posted.error)" in q


def test_phone_graded_custom_rows_never_read_profit_flat():
    hook = _code(_read(SRC / "hooks/useCustomModelStats.ts"))
    assert "profit_flat:" not in hook
    assert "units: postedPickUnits(p).units" in hook


@pytest.mark.parametrize("rel", ["lib/playerDetail.ts", "lib/teamDetail.ts"])
def test_player_and_team_records_are_the_published_stake(rel):
    code = _code(_read(SRC / rel))
    assert "postedPickUnits(p).units" in code
    assert "pf / 100" not in code


@pytest.mark.skipif(tsx_cmd(MOBILE) is None, reason="mobile node modules not installed")
def test_the_behavioural_checks_pass():
    proc = subprocess.run(
        [*tsx_cmd(MOBILE), "scripts/verify_units_one_basis.ts"],
        cwd=MOBILE, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
