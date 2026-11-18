"""Where the women's college basketball research keeps its two folders.

NCAABW_RESEARCH_DIR (default the main checkout's
data/local/research/ncaabw_research) holds:
  cache/   parquet copies of what Supabase holds (games, box scores, the quote
           tables), each built by a script here from the database or from the
           purchase's own spool, so the research never leans on production
  spool/   the odds history purchase's spool (data/ingestors/ncaabw_odds_history
           --spool): every fetched snapshot, the source the quote tables are
           built from. Override with NCAABW_RESEARCH_SPOOL.

Both are caches of Supabase (CLAUDE.md 1b). Neither is in the repo.
"""
import os
from pathlib import Path

# The main checkout's data/local/research/, not the home folder (moved there
# 2026-11-16 so everything on the PC sits under the project; CLAUDE.md §7).
ROOT = Path(os.environ.get("NCAABW_RESEARCH_DIR")
            or Path.home() / "Documents" / "betting-model" / "data" / "local" / "research" / "ncaabw_research")
CACHE = ROOT / "cache"
SPOOL = Path(os.environ.get("NCAABW_RESEARCH_SPOOL") or ROOT / "spool")
CACHE.mkdir(parents=True, exist_ok=True)
