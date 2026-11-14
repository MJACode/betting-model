"""
ufc_identity.py — resolve a fighter's display name to his ufcstats record.

Moved here 2026-11-13 from features/ufc_feature_engine.py when the three UFC
models built on that engine were retired (config.RETIRED_MODELS). The name
rule is not part of any model: every UFC model needs it, so it outlives them.

The odds feed and ufcstats spell the same fighter differently, and every
mismatch costs a whole fight: `resolve_fighter_id` returning None skips the
bout entirely. Measured 2026-09-07 over the 916 distinct fighter names on
2026 UFC cards, 315 did not match a `fighters` slug exactly. Classified:

    genuinely absent (debutants, other promotions)   298
    edit-distance "near" matches                      12   <- NEVER accept
    token-order variants (Zhang Weili / Weili Zhang)   2
    suffix variants (Khalil Rountree / ... Jr.)        3

So the two SAFE classes are handled here and the dangerous one is not.
Fuzzy matching is deliberately absent: at cutoff 0.84 it maps 'Usman
Nurmagomedov' to 'Umar Nurmagomedov' and 'Amru Magomedov' to 'Abus
Magomedov' -- different fighters, and a wrong history is worse than no
history, because it produces a confident pick from another man's record.

Every fallback is UNIQUE-OR-NOTHING: more than one candidate returns None.
Pinned by tests/test_ufc_name_resolution.py, which also refuses any fuzzy
matcher in this file.
"""

from pathlib import Path
import sys

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.db import DBConnection
from data.ingestors.ufc_stats_ingestor import slugify_fighter

_NAME_SUFFIXES = frozenset({"jr", "sr", "ii", "iii", "iv"})


def _slug_tokens(slug: str) -> frozenset:
    """The slug's name tokens, order- and suffix-independent."""
    return frozenset(t for t in slug.split("-") if t and t not in _NAME_SUFFIXES)


def resolve_slug(slug: str, candidates) -> str | None:
    """Match `slug` against known slugs: exact, else a UNIQUE token-set match.

    `candidates` is any iterable of known slugs. Returns the matching known
    slug, or None when there is no match or more than one -- an ambiguous name
    must never silently pick a fighter.
    """
    if not slug:
        return None
    known = list(candidates)
    if slug in known:
        return slug
    want = _slug_tokens(slug)
    if not want:
        return None
    hits = [k for k in known if _slug_tokens(k) == want]
    return hits[0] if len(hits) == 1 else None


def resolve_fighter_id(conn: DBConnection, display_name: str) -> str | None:
    """Fighter id for a display name: exact slug, else a unique token-set match.

    The fallback query is bounded by the rarest-looking token rather than
    scanning `fighters`, and resolve_slug() then insists on a UNIQUE token-set
    match, so a shared surname resolves to nothing rather than to the wrong
    man. See the module docstring for what is deliberately not tried.
    """
    slug = slugify_fighter(display_name)
    row = conn.execute(
        "SELECT fighter_id FROM fighters WHERE slug = ? ORDER BY updated_at DESC LIMIT 1",
        (slug,)).fetchone()
    if row:
        return row[0]

    tokens = sorted(_slug_tokens(slug), key=len, reverse=True)
    if not tokens:
        return None
    rows = conn.execute(
        "SELECT slug, fighter_id FROM fighters WHERE slug LIKE ? ORDER BY updated_at DESC",
        (f"%{tokens[0]}%",)).fetchall()
    if not rows:
        return None
    by_slug = {}
    for s, fid in rows:
        by_slug.setdefault(s, fid)
    hit = resolve_slug(slug, by_slug)
    if hit is None:
        return None
    logger.info(f"  UFC name resolved by token match: '{display_name}' -> {hit}")
    return by_slug[hit]
