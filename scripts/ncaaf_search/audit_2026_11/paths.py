"""Where the 2026-11 NCAAF market audit reads and caches (docs/ncaaf_market_audit.md).

The audit reads the local copy of the database (docs/local_ops.md, "carbon copy"), never
production, apart from the two totals scripts that call the repo's own frame builder once.
Everything it writes is a regenerable cache OUTSIDE the repo.

    NCAAF_AUDIT_CACHE   the extracts (default C:\\Users\\micha\\ncaaf_research\\data)
    LOCAL_MIRROR_TABLES the mirror's tables directory

The props and in-play studies write beside the extracts, to WORK/props and WORK/inplay.
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
MIRROR = Path(os.environ.get(
    "LOCAL_MIRROR_TABLES", r"C:\Users\micha\Documents\betting_local_copies\supabase_mirror\tables"))
CACHE = Path(os.environ.get("NCAAF_AUDIT_CACHE", r"C:\Users\micha\ncaaf_research\data"))
CACHE.mkdir(parents=True, exist_ok=True)
WORK = CACHE.parent
TOTALS_ARTIFACT = REPO / "models" / "saved" / "ncaaf_over_under_20260825_204305.pkl"
