"""Where the EuroLeague research keeps its two folders.

EUROLEAGUE_RESEARCH_DIR (default the main checkout's
data/local/research/euroleague_research) holds:
  cache/   parquet copies of what Supabase holds (games, quarter scores,
           venues, the period quotes with the time before tip each was bought
           at), read once by game id so the research never leans on production
  spool/   the full-game purchase's spool (data/ingestors/euroleague_odds_history
           --spool): every fetched snapshot. Override with
           EUROLEAGUE_RESEARCH_SPOOL; the purchase of 2026-11-13 used
           C:\\Users\\micha\\Documents\\betting-model\\data\\local\\research\\el_spool.

Both are caches of Supabase (CLAUDE.md 1b). Neither is in the repo.
"""
import os
from pathlib import Path

# The main checkout's data/local/research/, not the home folder (moved there
# 2026-11-16 so everything on the PC sits under the project; CLAUDE.md §7).
_RESEARCH = Path.home() / "Documents" / "betting-model" / "data" / "local" / "research"
ROOT = Path(os.environ.get("EUROLEAGUE_RESEARCH_DIR") or _RESEARCH / "euroleague_research")
CACHE = ROOT / "cache"
SPOOL = Path(os.environ.get("EUROLEAGUE_RESEARCH_SPOOL") or _RESEARCH / "el_spool")
CACHE.mkdir(parents=True, exist_ok=True)
