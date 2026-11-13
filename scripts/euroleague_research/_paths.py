"""Where the EuroLeague research keeps its two folders.

EUROLEAGUE_RESEARCH_DIR (default ~/euroleague_research) holds:
  cache/   parquet copies of what Supabase holds (games, quarter scores,
           venues, the period quotes with the time before tip each was bought
           at), read once by game id so the research never leans on production
  spool/   the full-game purchase's spool (data/ingestors/euroleague_odds_history
           --spool): every fetched snapshot. Override with
           EUROLEAGUE_RESEARCH_SPOOL; the purchase of 2026-11-13 used
           C:\\Users\\micha\\el_spool.

Both are caches of Supabase (CLAUDE.md 1b). Neither is in the repo.
"""
import os
from pathlib import Path

ROOT = Path(os.environ.get("EUROLEAGUE_RESEARCH_DIR") or Path.home() / "euroleague_research")
CACHE = ROOT / "cache"
SPOOL = Path(os.environ.get("EUROLEAGUE_RESEARCH_SPOOL") or Path.home() / "el_spool")
CACHE.mkdir(parents=True, exist_ok=True)
