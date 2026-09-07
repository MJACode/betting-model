"""A fighter's name must resolve to HIS record, or to nothing at all.

Measured 2026-09-07 over the 916 distinct fighter names on 2026 UFC cards:
315 did not match a `fighters` slug exactly, and every one of those costs a
whole bout — `_resolve_fighter_id` returning None skips the fight, which is a
third of the reason the UFC board is nearly empty.

Two of those classes are safe to resolve and one is not, which is the whole
content of this module:

    token-order variants   'Weili Zhang'      -> 'Zhang Weili'        SAFE
    suffix variants        'Khalil Rountree'  -> 'Khalil Rountree Jr' SAFE
    edit-distance "near"   'Usman Nurmagomedov' ~ 'Umar Nurmagomedov' NEVER

The last one is the reason there is no fuzzy matching here. A wrong history is
worse than no history: it produces a confident pick built from another man's
record, and nothing downstream can tell.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from features.ufc_feature_engine import resolve_slug, _slug_tokens  # noqa: E402

KNOWN = [
    "zhang-weili", "xiong-jingnan", "khalil-rountree-jr", "michael-aswell-jr",
    "umar-nurmagomedov", "abus-magomedov", "islam-makhachev", "jose-aldo",
]


# ── the two safe classes ─────────────────────────────────────────────────────

def test_a_reversed_name_order_resolves():
    """Chinese and Japanese names arrive in either order depending on the feed."""
    assert resolve_slug("weili-zhang", KNOWN) == "zhang-weili"
    assert resolve_slug("jingnan-xiong", KNOWN) == "xiong-jingnan"


def test_a_generational_suffix_resolves_either_way():
    assert resolve_slug("khalil-rountree", KNOWN) == "khalil-rountree-jr"
    assert resolve_slug("michael-aswell-jr", KNOWN) == "michael-aswell-jr"


def test_an_exact_slug_still_wins_untouched():
    assert resolve_slug("islam-makhachev", KNOWN) == "islam-makhachev"


# ── the class that must NEVER resolve ────────────────────────────────────────

def test_a_near_miss_is_not_a_match():
    """`Usman Nurmagomedov` and `Umar Nurmagomedov` are different fighters, and
    an edit-distance matcher at cutoff 0.84 maps one to the other. Resolving it
    would price a fight off the wrong man's record."""
    assert resolve_slug("usman-nurmagomedov", KNOWN) is None
    assert resolve_slug("amru-magomedov", KNOWN) is None


def test_a_shared_surname_alone_is_not_a_match():
    assert resolve_slug("khabib-nurmagomedov", KNOWN) is None


def test_an_ambiguous_token_set_resolves_to_nothing():
    """Two known fighters with the same token set: refuse, never pick one."""
    ambiguous = ["jose-aldo", "aldo-jose"]
    assert resolve_slug("aldo-jose-jr", ambiguous) is None


def test_an_empty_or_tokenless_name_is_safe():
    assert resolve_slug("", KNOWN) is None
    assert resolve_slug("jr", KNOWN) is None


# ── the tokeniser ────────────────────────────────────────────────────────────

def test_suffixes_and_order_are_dropped_from_the_token_set():
    assert _slug_tokens("khalil-rountree-jr") == _slug_tokens("rountree-khalil")
    assert _slug_tokens("john-doe-iii") == {"john", "doe"}


def test_the_module_ships_no_fuzzy_matcher():
    """A regression guard with teeth: the fix for a missed name is an alias or
    a new safe RULE, never a similarity cutoff."""
    src = (Path(__file__).parent.parent / "features"
           / "ufc_feature_engine.py").read_text(encoding="utf-8")
    for banned in ("get_close_matches", "SequenceMatcher", "levenshtein",
                   "difflib", "rapidfuzz", "fuzzywuzzy"):
        assert banned not in src, f"{banned} would resolve Usman -> Umar"
