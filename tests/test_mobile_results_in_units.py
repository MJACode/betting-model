"""Every result in the app is in units, never dollars (mike, 2026-11-03:
"everything must be units"; CLAUDE.md §4).

A unit is the posted stake (CLAUDE.md §2): 1u to win at the decided price,
risk capped at 3u. `profit_flat` / 100 is the 1u-risked figure and no screen
prints it (tests/test_mobile_units_one_basis.py). Stakes are units too. The only
dollar amounts left in the app are real money that is not a betting result:
the subscription prices on the paywall, and the optional bankroll a member
types into Settings to see what one of their units is worth.

Also pinned here: the record is kept at the price the pick was decided at.
"The best price across all books" was false for at least one model
(ncaab_moneyline_own_spread bets the book with the largest edge: 269 of its
914 replayed bets had a better price at another book), so no screen says it.

The behavioural half is `mobile/scripts/verify_results_in_units.ts`; this file
runs it when node is available and scans the source either way.
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

# Real money that is not a betting result. Each one is a price a member pays
# or the member's own optional bankroll, never a pick's or a model's result.
DOLLARS_ALLOWED = {
    "lib/billingHelpers.ts",   # subscription prices ("$24.99")
    "lib/billingConfig.ts",    # the same prices, configured
    "lib/iapHelpers.ts",       # the store's localized price string
    "lib/bankroll.ts",         # the optional bankroll, display-only (#831)
}
# Settings carries exactly one "$": the bankroll field's prefix. Any other
# dollar sign there is a finding like anywhere else.
SETTINGS_BANKROLL_PREFIX = "screens/SettingsScreen.tsx: $"


def _read(p: Path) -> str:
    # Explicit encoding: this repo runs on Windows (CLAUDE.md §7).
    return p.read_text(encoding="utf-8")


def _sources():
    for p in sorted(SRC.rglob("*")):
        if p.suffix in (".ts", ".tsx"):
            yield p.relative_to(SRC).as_posix(), _read(p)


def _code_only(text: str) -> str:
    """The source with comments removed, so a docstring that explains the
    stored $100 convention does not count as a screen showing dollars."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"\{\s*/\*.*?\*/\s*\}", "", text, flags=re.S)
    lines = []
    for line in text.splitlines():
        if line.lstrip().startswith("//"):
            continue
        # A trailing "  // note" on a code line ("https://" has no space before it).
        lines.append(re.sub(r"\s//\s.*$", "", line))
    return "\n".join(lines)


def test_no_dollar_formatter_survives():
    """formatCurrency / formatCurrencySigned printed "$90.91" on the model
    page's history rows, the Models list, the custom-model page and the
    Performance tab. They are gone, so nothing can reach for them again."""
    offenders = [
        rel for rel, text in _sources()
        if re.search(r"\bformatCurrency(Signed)?\b", text)
    ]
    assert offenders == [], offenders


def test_no_screen_prints_a_dollar_amount():
    """No "$100 flat", "$10 pays", "per $1", "Stake ($)" or "$${x}" outside the
    real-money files. Template-literal "${" is code, not a dollar sign."""
    offenders = []
    for rel, text in _sources():
        if rel in DOLLARS_ALLOWED:
            continue
        code = _code_only(text)
        # A literal "$" that is not the start of a template substitution, and
        # not a regex anchor or replacement ("$1", "$/", "\\$").
        for m in re.finditer(r"(?<![\\$])\$(?!\{)", code):
            line = code[: m.start()].count("\n")
            src_line = code.splitlines()[line]
            # "$1" inside a .replace() call is a regex backreference, not money.
            if ".replace(" in src_line and re.match(r"\$[1-9](?!\d)", code[m.start():]):
                continue
            # Regex literals: "...$/", "$')", "$`)" are anchors, not money.
            tail = code[m.start() + 1 : m.start() + 3]
            if tail[:1] in ("/", ")", "'", '"', "`", "|", "]") or src_line.strip().startswith("*"):
                continue
            offenders.append(f"{rel}: {src_line.strip()}")
    settings = [o for o in offenders if o.startswith("screens/SettingsScreen.tsx: ")]
    assert settings == [SETTINGS_BANKROLL_PREFIX], settings
    offenders = [o for o in offenders if o not in settings]
    assert offenders == [], "\n".join(offenders)


def test_no_copy_says_dollars_for_a_result():
    words = re.compile(r"in dollars|\$100|\$10 pays|per \$1\b|Stake \(\$\)", re.I)
    offenders = [
        f"{rel}: {line.strip()}"
        for rel, text in _sources()
        if rel not in DOLLARS_ALLOWED
        for line in _code_only(text).splitlines()
        if words.search(line)
        # The Settings bankroll field (#831) is the one place a member types
        # dollars: its label and hint say so, and say nothing about a result.
        and not (rel == "screens/SettingsScreen.tsx" and re.search(
            r'"Your bankroll in dollars, optional"|"Only used to show your units in dollars', line))
    ]
    assert offenders == [], offenders


def test_the_model_page_history_rows_are_units():
    """The case the 2026-11-02 UX review found: each settled pick under a
    model's record showed "+$90.91"."""
    screen = _read(SRC / "screens/BuiltInModelDetailScreen.tsx")
    row = screen[screen.index("function HistoryPickRow"):]
    row = row[: row.index("\n}\n")]
    # The published stake since 2026-11-03 (tests/test_mobile_units_one_basis.py):
    # never settlement's profit_flat, which invents -110 with no price.
    assert "formatSigned(postedPickUnits(pick).units, 2, 'u')" in row
    assert "profit_flat" not in _code_only(row)
    assert 'label="Units"' in screen


@pytest.mark.parametrize("rel", [
    "screens/BuiltInModelDetailScreen.tsx",
    "screens/ModelDetailScreen.tsx",
    "screens/ModelsScreen.tsx",
])
def test_each_record_surface_tones_from_the_units_it_prints(rel):
    """Colour comes from the number as printed (lib/tone.ts). Units print at
    two decimals ("+0.91u"), so the tone is pnlColor(units, 2)."""
    text = _read(SRC / rel)
    assert "formatSigned(" in text and ", 2, 'u')" in text
    assert re.search(r"pnlColor\((stats|item)\.units, 2\)", text), rel
    assert re.search(r"pnlColor\([^)]*profit[^)]*, 2\)", text, re.I) is None, rel


def test_the_performance_tab_is_units():
    screen = _read(SRC / "screens/PerformanceScreen.tsx")
    # Tracked picks default to the posted stake (#1138 Decision 1); the
    # member's own stake is typed in units.
    assert "label: 'As posted'" in screen
    assert "Use posted stake" in screen
    assert 'accessibilityLabel="Stake in units"' in screen
    # Synced bets (not live yet) read at the tab's one scale until the unit for
    # them is decided; the bankroll stays a Settings-only display (#831).
    assert "{formatFlatUnits(summary.net_profit)}" in screen
    assert "useBankroll" not in screen
    modal = _read(SRC / "components/ManualBetModal.tsx")
    assert 'label="Stake (units)"' in modal
    assert "Stake in dollars" not in modal


def test_the_record_is_kept_at_the_decided_price_for_every_model():
    """One true statement for every model, not a best-price claim with one
    exception carved out."""
    books = _read(SRC / "lib/myBooks.ts")
    assert "RECORD_AT_EDGE_BOOK_MODELS" not in books
    assert "RECORD_AT_BEST_BOOK_NOTE" not in books
    false_claims = re.compile(
        r"best price across (all|every)|graded at the best price|record uses best price"
        r"|taken at the best price",
        re.I,
    )
    offenders = [
        f"{rel}: {m.group(0)}"
        for rel, text in _sources()
        for m in false_claims.finditer(_code_only(text))
    ]
    assert offenders == [], offenders


@pytest.mark.skipif(tsx_cmd(MOBILE) is None, reason="mobile node modules not installed")
def test_the_behavioural_checks_pass():
    proc = subprocess.run(
        [*tsx_cmd(MOBILE), "scripts/verify_results_in_units.ts"],
        cwd=MOBILE, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
