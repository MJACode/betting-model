"""Contrast and colour tokens — usability audit PR 1 (2026-09-25).

H7 darkens `textTertiary` to #6C6C70. H1 draws the signal badge word in an
ink with a ✓ / – / ✕ glyph. H2 / H8 add text-safe `betInk` / `avoidInk` /
`medInk` for P&L, ROI, EV, CLV, warnings and "Tracking", and keep the bright
`bet` / `avoid` / `med` for fills and icons. H6 takes white text off green.
Signed results always carry "+" or U+2212, and zero is unsigned.

The behavioural checks live in `mobile/scripts/verify_contrast_tokens.ts`.
This file re-measures every ratio in Python from theme.ts itself (so CI,
which has no node modules, still fails on a token drift), pins the wiring,
runs the pure formatters and tone map under node's type stripping, and runs
the tsx script when node modules are installed.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
SRC = MOBILE / "src"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _tokens() -> dict[str, str]:
    src = _read(SRC / "lib" / "theme.ts")
    brand = re.search(r"const BRAND_INK = '(#[0-9A-Fa-f]{6})'", src).group(1)
    block = re.search(r"export const colors = \{(.*?)\n\};", src, re.S).group(1)
    out = {}
    for m in re.finditer(r"^\s*(\w+):\s*(?:'(#[0-9A-Fa-f]{6,8})'|(BRAND_INK))", block, re.M):
        out[m.group(1)] = (m.group(2) or brand).upper()
    return out


def _rgb(h: str) -> tuple[float, float, float, float]:
    h = h.lstrip("#")
    a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a


def _over(fg: str, bg: str) -> str:
    r, g, b, a = _rgb(fg)
    R, G, B, _ = _rgb(bg)
    return "#" + "".join(f"{round(x * a + y * (1 - a)):02X}" for x, y in ((r, R), (g, G), (b, B)))


def _lum(h: str) -> float:
    r, g, b, _ = _rgb(h)

    def f(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _ratio(fg: str, bg: str) -> float:
    a, b = _lum(_over(fg, bg)), _lum(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def _code_lines(path: Path) -> list[str]:
    return [
        "" if re.match(r"^\s*(//|\*|/\*)", line) else line
        for line in _read(path).splitlines()
    ]


def test_token_values_and_fills_unchanged():
    t = _tokens()
    assert t["textTertiary"] == "#6C6C70"  # H7
    assert t["betInk"] == "#1A7F37"
    assert t["avoidInk"] == "#C4281C"
    assert t["medInk"] == "#9A5B00"
    # Fills keep the bright hues.
    assert t["bet"] == t["positive"] == "#34C759"
    assert t["avoid"] == t["negative"] == "#FF3B30"
    assert t["med"] == "#FF9500"
    assert _lum(t["textTertiary"]) > _lum(t["textSecondary"])  # hierarchy holds


# (text token, ground, minimum). The app is light-only: no dark palette exists.
PAIRS = [
    *[("textTertiary", g, 4.5) for g in ("bgCard", "bg", "noneSoft", "betSoft", "avoidSoft", "medSoft")],
    ("betInk", "bgCard", 4.5),
    ("betInk", "bg", 4.5),
    ("betInk", "betSoft", 4.5),
    ("avoidInk", "bgCard", 4.5),
    ("avoidInk", "bg", 4.5),
    ("avoidInk", "avoidSoft", 4.5),
    ("medInk", "bgCard", 4.5),
    ("medInk", "bg", 4.5),
    ("medInk", "medSoft", 4.5),
    ("textSecondary", "noneSoft", 4.5),
    ("textPrimary", "bet", 4.5),  # SportToggle count (H6)
    ("textPrimary", "med", 4.5),  # player hit-rate badge
    ("textPrimary", "avoid", 4.5),
    ("textPrimary", "none", 4.5),
    ("textInverse", "tint", 4.5),  # Apply (H6)
]


@pytest.mark.parametrize("fg,bg,minimum", PAIRS)
def test_every_changed_text_token_clears_aa_on_its_ground(fg, bg, minimum):
    t = _tokens()
    assert _ratio(t[fg], t[bg]) >= minimum, f"{fg} {t[fg]} on {bg} {t[bg]}: {_ratio(t[fg], t[bg]):.2f}"


@pytest.mark.parametrize("ink,hue", [("betInk", "bet"), ("avoidInk", "avoid"), ("medInk", "med")])
def test_parlay_grade_word_clears_aa_on_its_wash(ink, hue):
    t = _tokens()
    wash = _over(t[hue] + "22", t["bgCard"])
    assert _ratio(t[ink], wash) >= 4.5


def test_the_audit_ratios():
    t = _tokens()
    assert round(_ratio(t["textTertiary"], t["bgCard"]), 2) == 5.23
    assert round(_ratio(t["textTertiary"], t["bg"]), 2) == 4.69
    assert round(_ratio(t["betInk"], t["betSoft"]), 2) == 4.61
    assert round(_ratio(t["avoidInk"], t["avoidSoft"]), 2) == 5.01
    assert round(_ratio(t["medInk"], t["medSoft"]), 2) == 4.99
    assert round(_ratio(t["textPrimary"], t["bet"]), 2) == 9.46


def test_signal_badge_ink_and_glyph_mapping():
    tone = _read(SRC / "lib" / "tone.ts")
    for sig, glyph, ink, fill in (
        ("BET", "checkmark", "betInk", "betSoft"),
        ("NONE", "remove", "textSecondary", "noneSoft"),
        ("AVOID", "close", "avoidInk", "avoidSoft"),
    ):
        assert re.search(
            rf"{sig}: \{{ label: '{sig}', glyph: '{glyph}', ink: '{ink}', fill: '{fill}' \}}", tone
        ), sig
        t = _tokens()
        assert _ratio(t[ink], t[fill]) >= 4.5
    badge = _read(SRC / "components" / "SignalBadge.tsx")
    assert "SIGNAL_BADGE[signal]" in badge
    assert "name={spec.glyph}" in badge
    assert not re.search(r"colors\.(bet|avoid|none)\b(?!Soft|Ink)", badge)


def test_no_short_white_literal_and_h6_sites():
    hits = []
    for path in [*SRC.rglob("*.ts"), *SRC.rglob("*.tsx"), MOBILE / "App.tsx"]:
        if path.name == "theme.ts":
            continue
        for i, line in enumerate(_code_lines(path), 1):
            if re.search(r"(['\"])#fff\1|(['\"])white\2", line, re.I):
                hits.append(f"{path.relative_to(ROOT)}:{i}")
    assert not hits, hits
    sheet = _read(SRC / "components" / "SportsbookPickerSheet.tsx")
    apply_btn = re.search(r"applyBtn: \{.*?\}", sheet, re.S).group(0)
    apply_text = re.search(r"applyText: \{.*?\}", sheet, re.S).group(0)
    assert "backgroundColor: colors.tint" in apply_btn
    assert "color: colors.textInverse" in apply_text
    toggle = _read(SRC / "components" / "SportToggle.tsx")
    assert "color: colors.textPrimary" in re.search(r"badgeText: \{.*?\}", toggle, re.S).group(0)
    assert "opacity" not in re.search(r"labelMuted: \{.*?\}", toggle, re.S).group(0)  # M17


HUE_TEXT = re.compile(
    r"(?<![A-Za-z])(color:|tint:|tint=\{)[^,;\n}]*\bcolors\.(bet|avoid|med|positive|negative|high|none|low)\b(?!Soft|Ink)"
)


def test_no_bright_hue_left_as_a_text_colour():
    """Icons keep the bright hue (Ionicons `color={…}` is not matched); words
    use the inks. PickCard's movement summary carries `icon:` and routes its
    words through inkFor()."""
    hits = []
    for path in [*SRC.rglob("*.tsx"), MOBILE / "App.tsx"]:
        for i, line in enumerate(_code_lines(path), 1):
            if HUE_TEXT.search(line) and not re.search(r"\bicon:", line):
                hits.append(f"{path.relative_to(ROOT)}:{i}: {line.strip()}")
    assert not hits, "\n".join(hits)


def test_pnl_color_and_signed_formatter_are_wired():
    theme = _read(SRC / "lib" / "theme.ts")
    assert "return colors[pnlTone(value, digits, scale)]" in theme
    tone = _read(SRC / "lib" / "tone.ts")
    # The tone is the ROUNDED value's sign (Reviewer MEDIUM A), not an epsilon.
    assert "Number((n * scale).toFixed(digits))" in tone
    assert "epsilon" not in tone
    fmt = _read(SRC / "lib" / "format.ts")
    assert "export const MINUS = '\\u2212'" in fmt
    pct = fmt[fmt.index("export function formatPctSigned"):]
    assert "formatSigned(value * 100, digits, '%')" in pct[: pct.index("\n}")]
    # Hand-rolled "+" builders on the CLV sites are gone.
    for rel in ("components/PickCard.tsx", "screens/PickDetailScreen.tsx", "screens/BuiltInModelDetailScreen.tsx"):
        assert not re.search(r"> 0 \? '\+' : ''\}\$\{[^}]*toFixed", _read(SRC / rel)), rel


# Non-text (WCAG 1.4.11, 3:1). Warning icons are medInk on every ground;
# red icons keep the bright hue only where it already clears 3:1.
ICON_PAIRS = [
    ("medInk", "medSoft"), ("medInk", "bgCard"), ("medInk", "bg"),
    ("betInk", "bgCard"), ("avoidInk", "bgCard"),
    ("avoid", "avoidSoft"), ("avoid", "bgCard"),
]


@pytest.mark.parametrize("fg,bg", ICON_PAIRS)
def test_icons_clear_non_text_contrast(fg, bg):
    t = _tokens()
    assert _ratio(t[fg], t[bg]) >= 3.0, f"{fg} on {bg}: {_ratio(t[fg], t[bg]):.2f}"


def test_no_warning_icon_left_in_bright_med():
    t = _tokens()
    assert _ratio(t["med"], t["medSoft"]) < 3  # the failure being fixed
    hits = []
    for path in [*SRC.rglob("*.tsx"), MOBILE / "App.tsx"]:
        for i, line in enumerate(_code_lines(path), 1):
            if re.search(r"<Ionicons\b[^>]*color=\{colors\.med\}", line) or re.match(r"^\s*color=\{colors\.med\}", line):
                hits.append(f"{path.relative_to(ROOT)}:{i}")
    assert hits == []


# Reviewer Low 2: no Ionicons in bright green/amber, ternaries included. No
# allowlist: the green-as-selected checkmarks moved to tint (Designer verdict).
BRIGHT_ICON = re.compile(r"\bcolors\.(med|bet|positive|high)\b(?!Soft|Ink)")


def _ionicon_colors(src: str) -> list[tuple[int, str]]:
    out = []
    for m in re.finditer(r"<Ionicons\b", src):
        end = src.find("/>", m.start())
        tag = src[m.start(): end if end >= 0 else None]
        at = re.search(r"\bcolor=\{", tag)
        if not at:
            continue
        i = tag.index("{", at.start())
        start, depth = i, 0
        while i < len(tag):
            if tag[i] == "{":
                depth += 1
            elif tag[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        out.append((src[: m.start() + at.start()].count("\n") + 1, tag[start + 1: i]))
    return out


def test_bright_icon_scan_sees_ternaries():
    probe = "<Ionicons\n  name=\"x\"\n  color={on ? colors.bet : colors.textTertiary}\n/>\n<Ionicons color={colors.betInk} />"
    found = _ionicon_colors(probe)
    assert found[0][0] == 3 and BRIGHT_ICON.search(found[0][1])
    assert not BRIGHT_ICON.search(found[1][1])


def test_no_ionicon_in_bright_green_or_amber():
    hits = []
    for path in [*SRC.rglob("*.tsx"), *SRC.rglob("*.ts"), MOBILE / "App.tsx"]:
        src = "\n".join(_code_lines(path))
        for line, expr in _ionicon_colors(src):
            if not BRIGHT_ICON.search(expr):
                continue
            hits.append(f"{path.relative_to(MOBILE).as_posix()}:{line} {' '.join(expr.split())}")
    assert hits == []
    parlay = _read(SRC / "screens" / "ParlayScreen.tsx")
    # Designer: tint (overrides Reviewer MEDIUM B's betInk).
    assert 'name="pricetag-outline" size={13} color={colors.tint}' in parlay


@pytest.mark.parametrize(
    "rel",
    [
        "components/SportsbookPickerSheet.tsx",
        "components/StatGroupSheet.tsx",
        "components/HitModeSheet.tsx",
        "components/StatePickerSheet.tsx",
        "screens/PaywallScreen.tsx",
    ],
)
def test_selection_is_tint_not_green(rel):
    src = _read(SRC / rel)
    marks = re.findall(r'name="checkmark-circle" size=\{\d+\} color=\{colors\.(\w+)\}', src)
    assert marks and set(marks) == {"tint"}
    assert not re.search(r"rowActive:\s*\{\s*borderColor: colors\.bet\b", src)


def test_equity_total_share_text_and_no_picks_rows():
    eq = _read(SRC / "components" / "EquityCurve.tsx")
    assert "<Text style={[styles.units, { color: pnlColor(last, 1) }]}>{formatSignedUnits(last)}</Text>" in eq
    assert "toFixed(1)}u" not in eq
    share = _read(SRC / "lib" / "shareRecord.ts")
    assert "formatPctSigned(s.roiFlat)" in share and "formatSignedUnits(opts.endUnits)" in share
    assert "? '+' : ''" not in share
    daily = _read(SRC / "components" / "DailyResultsModal.tsx")
    assert "sportCardEmpty: { paddingVertical: spacing.sm }," in daily


def test_every_pnl_color_call_names_its_precision():
    bad, n = [], 0
    for path in [*SRC.rglob("*.tsx"), *SRC.rglob("*.ts"), MOBILE / "App.tsx"]:
        if path.name == "theme.ts":
            continue
        src = "\n".join(_code_lines(path))
        for m in re.finditer(r"pnlColor\(((?:[^()]|\([^()]*\))*)\)", src):
            n += 1
            if not re.search(r",\s*(1,\s*100|2|1)\s*$", m.group(1)):
                bad.append(f"{path.relative_to(ROOT)}: pnlColor({m.group(1)})")
    assert n >= 20 and bad == [], bad
    pick_detail = _read(SRC / "screens" / "PickDetailScreen.tsx")
    assert "const flat = !lineMoved && roundsToZero(pick.clv_pct, 1)" in pick_detail
    assert "evColor" not in _read(SRC / "components" / "PickCard.tsx")


def test_tracking_and_in_slip_on_state_is_tint_not_green():
    t = _tokens()
    assert _ratio(t["tint"], t["bgCard"]) >= 4.5
    track = "\n".join(_code_lines(SRC / "components" / "TrackButton.tsx"))
    add = "\n".join(_code_lines(SRC / "components" / "AddToPlayButton.tsx"))
    for src in (track, add):
        assert not re.search(r"colors\.(bet|betInk|betSoft|positive)\b", src)
    assert "tracked ? 'checkmark'" in track
    assert "inPlay ? 'checkmark'" in add
    # Reviewer Low 3: VoiceOver announces the ON state.
    assert "accessibilityState={{ selected: tracked }}" in track
    assert "accessibilityState={{ selected: inPlay }}" in add
    player = _read(SRC / "screens" / "PlayerStatsScreen.tsx")
    assert re.search(r"slipBtnIn: \{[^}]*borderColor: colors\.tint", player)
    assert "slipBtnTextIn: { color: colors.tint }" in player


def test_badge_glyph_tracks_dynamic_type():
    src = _read(SRC / "components" / "SignalBadge.tsx")
    assert "useWindowDimensions()" in src
    assert "badgeGlyphSize(size, fontScale)" in src
    assert "size={glyphSize}" in src
    tone = _read(SRC / "lib" / "tone.ts")
    assert "Math.round(fontSize * Math.min(scale, 2))" in tone


def _node_strips_types() -> bool:
    if shutil.which("node") is None:
        return False
    out = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip()
    m = re.match(r"v(\d+)\.(\d+)", out)
    return bool(m) and (int(m.group(1)), int(m.group(2))) >= (22, 6)


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_signed_formatter_and_tone_behaviour():
    script = """
import { formatCurrency, formatCurrencySigned, formatPctSigned, formatSigned, formatSignedUnits } from './mobile/src/lib/format.ts';
import { badgeGlyphSize, pnlTone } from './mobile/src/lib/tone.ts';
const M = '\\u2212';
const cases = [
  [formatSigned(1.23), '+1.2'], [formatSigned(-0.5, 2), M + '0.50'], [formatSigned(-0.04), '0.0'],
  [formatSigned(2.3, 1, 'pp'), '+2.3pp'], [formatSigned(null), '—'],
  [formatPctSigned(0.125), '+12.5%'], [formatPctSigned(-0.03), M + '3.0%'], [formatPctSigned(-0.0004), '0.0%'],
  [formatCurrencySigned(-25), M + '$25.00'], [formatCurrencySigned(0.004), '$0.00'],
  [formatSignedUnits(2.44), '+2.4u'], [formatSignedUnits(-0.5), M + '0.5u'], [formatSignedUnits(0.04), '0.0u'],
  [pnlTone(1, 1), 'betInk'], [pnlTone(-1, 1), 'avoidInk'], [pnlTone(0, 1), 'textSecondary'],
  [pnlTone(null, 1), 'textSecondary'], [pnlTone(Infinity, 1), 'textSecondary'],
  // Reviewer MEDIUM A pins: tone from the value as PRINTED.
  [formatPctSigned(-0.0004), '0.0%'], [pnlTone(-0.0004, 1, 100), 'textSecondary'],
  [formatCurrencySigned(1e-13), '$0.00'], [pnlTone(1e-13, 2), 'textSecondary'],
  [formatPctSigned(0.0008), '+0.1%'], [pnlTone(0.0008, 1, 100), 'betInk'],
  [formatSigned(-0.03, 1, 'pp'), '0.0pp'], [pnlTone(-0.03, 1), 'textSecondary'],
  // Reviewer Low 4.
  [formatSigned(Infinity), '—'], [formatSigned(NaN), '—'],
  [formatSignedUnits(0.25), '+0.3u'], [formatSignedUnits(-0.25), M + '0.3u'],
  [formatCurrency(-4), M + '$4.00'], [formatCurrency(-0.001), '$0.00'],
  [badgeGlyphSize(11, 1), 11], [badgeGlyphSize(11, 1.5), 17], [badgeGlyphSize(11, 3.1), 22], [badgeGlyphSize(11, NaN), 11],
];
for (const [got, want] of cases) if (got !== want) throw new Error(`${got} !== ${want}`);
"""
    proc = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_ux_scan_sees_short_hex_and_rgba():
    """L3: '#fff' on green shipped because the scan only matched 6/8 digits."""
    with tempfile.TemporaryDirectory() as d:
        probe = Path(d) / "Probe.tsx"
        probe.write_text(
            "const s = { a: { color: '#fff' }, b: { backgroundColor: 'rgba(255,255,255,0.5)' },\n"
            "  c: { shadowColor: '#000' }, d: { backgroundColor: 'rgba(0,0,0,0.4)' } };\n"
            "const copy = 'see PR #830';\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            ["node", "--experimental-strip-types", "mobile/scripts/ux_scan.mts", str(probe)],
            cwd=ROOT, capture_output=True, text=True,
        )
    assert proc.returncode == 0, proc.stderr
    assert "hard-coded colour #fff" in proc.stdout
    assert "rgba(255,255,255,0.5)" in proc.stdout
    assert "#000 " not in proc.stdout  # a black shadow is tolerated
    assert "rgba(0,0,0,0.4)" not in proc.stdout  # a black-alpha backdrop is tolerated
    assert "#830" not in proc.stdout  # copy is not a colour
    scan = _read(MOBILE / "scripts" / "ux_scan.mts")
    assert "APP_ROOT_FILE" in scan


def test_contrast_pins_are_on_the_pr_ci_subset():
    yml = _read(ROOT / ".github" / "workflows" / "pr-ci.yml")
    assert "tests/test_mobile_contrast_tokens.py" in yml


@pytest.mark.skipif(
    not (MOBILE / "node_modules" / ".bin").exists() or shutil.which("node") is None,
    reason="mobile node modules not installed",
)
def test_the_behavioural_checks_pass():
    tsx = MOBILE / "node_modules" / ".bin" / "tsx"
    proc = subprocess.run(
        [str(tsx), "scripts/verify_contrast_tokens.ts"],
        cwd=MOBILE, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
