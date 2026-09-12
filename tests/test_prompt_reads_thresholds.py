"""The Claude-mobile prompt reads the cut from the table, not from itself.

mike, 2026-09-12: *"I am connected through claude rc to my computer - why does
mobile matter, it should not."*

It should not, and the reason it did was self-inflicted. The prompt embedded 52
per-model cuts as SQL literals, so it went stale on every threshold change,
pause, unpause or new model, and the only way to refresh it was for a person to
paste a freshly generated block into the project instructions. Nothing in this
repo can write that field, which is why "paste the prompt block" kept coming
back as a task only mike could do.

`model_action_thresholds` is written from `config.py` by the 6am pipeline and
is already what the app's action filter, Discord and push read. The prompt now
joins it. It is pasted once and never again.

AND THE TABLE HAS TO TELL THE WHOLE TRUTH, which it did not: `threshold_sync`
wrote `paused` from `config.PAUSED_MODELS` alone, so a model auto-paused by the
250-bet review read `paused = false` to every one of those readers. Measured
2026-09-12 on the two busiest recent slates: the table-driven cut returned 4
`mlb_prop_pitcher_k` picks that the scorer's own pause register excludes.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT = (ROOT / "docs" / "mobile_picks_prompt.md").read_text(encoding="utf-8")
SYNC = (ROOT / "data" / "threshold_sync.py").read_text(encoding="utf-8")


def test_the_prompt_carries_no_per_model_cut():
    """A literal cut in the prompt is a copy that goes stale silently."""
    literals = re.findall(r"p\.model_id = '[a-z0-9_]+'\s+AND p\.model_probability >=", PROMPT)
    assert not literals, (
        f"{len(literals)} per-model cut(s) hardcoded in the prompt; they go "
        "stale on every threshold change and can only be refreshed by hand")


def test_the_prompt_joins_the_thresholds_table_and_applies_every_gate():
    assert "JOIN model_action_thresholds t ON t.model_id = p.model_id" in PROMPT
    for gate in ("t.paused = FALSE",
                 "p.model_probability >= t.min_prob",
                 "COALESCE(p.decision_edge, p.edge) >= COALESCE(t.min_edge, 0)",
                 "COALESCE(p.decision_odds, p.dk_odds) >= t.min_odds",
                 "p.condition_status IS NULL OR p.condition_status <> 'VOID'"):
        assert gate in PROMPT, f"the prompt lost the gate: {gate}"


def test_the_sync_mirrors_both_pause_registers():
    """config.PAUSED_MODELS is what a person chose; model_auto_pauses is what
    the review decided. A table that carries only the first tells the app,
    Discord, push and the prompt that a paused model is live."""
    assert "mid in PAUSED_MODELS or mid in auto_paused_set" in SYNC
    assert "from tracking.threshold_review import auto_paused" in SYNC


def test_the_auto_pause_lookup_fails_open():
    """An unreadable table must pause nothing, not everything -- the same
    contract models.scorer._auto_paused_models keeps."""
    body = SYNC[SYNC.index("auto_paused_set"):]
    assert "except Exception" in body and "auto_paused_set = set()" in body


def test_the_prompt_still_says_it_is_pasted_once():
    """If the doc goes back to telling a human to regenerate and paste a block
    on every change, the recurring task is back."""
    assert "python -m scripts.emit_threshold_sql --prefix p." not in PROMPT.split(
        "## ")[0] + PROMPT[:PROMPT.index("```") if "```" in PROMPT else 0]
