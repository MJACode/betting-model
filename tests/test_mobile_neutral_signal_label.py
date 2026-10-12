"""A dead-zone pick reads NEUTRAL to members, never NONE (Matt, 2026-10-12).

The stored ``signal_type`` stays ``'NONE'``; only the word on screen changes.
Every place the app prints a signal word goes through ``signalDisplayName``
(lib/tone.ts), so the badge, the filter chips, the filter pill and the card's
VoiceOver label cannot drift apart.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "mobile" / "src"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_none_badge_reads_neutral():
    tone = _read("lib/tone.ts")
    assert "NONE: { label: 'NEUTRAL'" in tone
    assert "label: 'NONE'" not in tone
    assert "export function signalDisplayName" in tone


def test_filters_and_card_speak_the_display_name():
    filters = _read("components/filters/PickFilters.tsx")
    assert "label={signalDisplayName(s)}" in filters
    assert "Array.from(state.signals).map(signalDisplayName)" in filters
    assert "label={s}" not in filters
    card = _read("components/PickCard.tsx")
    assert "signalDisplayName(pick.signal_type)" in card


def test_explainer_names_neutral():
    explainer = _read("screens/ExplainerScreen.tsx")
    assert "<Strong>NEUTRAL</Strong>" in explainer
    assert "<Strong>NONE</Strong>" not in explainer


def test_model_screens_speak_the_display_name():
    md = _read("screens/ModelDetailScreen.tsx")
    assert "signalDisplayName(ep.pick.signal_type)" in md
    assert "signalDisplayName(item.signal_type)" in md
    bim = _read("screens/BuiltInModelDetailScreen.tsx")
    assert "signalDisplayName(pick.signal_type)" in bim


def test_withdrawn_pick_is_not_badged_neutral():
    detail = _read("screens/PickDetailScreen.tsx")
    assert "voided ? 'NONE'" not in detail
    assert "'WITHDRAWN'" in detail


def test_no_member_label_prints_a_raw_signal_type():
    """accessibilityLabel arrays must not carry a bare `.signal_type` item."""
    import re
    for path in ROOT.rglob("*.tsx"):
        src = path.read_text(encoding="utf-8")
        for m in re.finditer(r"accessibilityLabel=\{\[(.*?)\]", src, re.S):
            assert not re.search(r"(?<!\()\b[\w.]*signal_type\b(?!\))", m.group(1)), path
