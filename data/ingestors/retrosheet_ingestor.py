"""
retrosheet_ingestor.py — DEPRECATED in favour of `mlb_pbp_ingestor.py`.

Phase 1 scaffolded this file expecting to ingest Retrosheet play-by-play.
Phase 2a chose the MLB Stats API live feed instead — same endpoint the Phase
1 live poller already calls, so training-time state vectors match
inference-time state vectors with zero parser drift. 2008+ coverage is plenty
for live win-probability training.

Retrosheet is still the ONLY viable source if we ever need pre-2008 PBP.
This stub is kept (rather than deleted) as a documented fallback plan.

Tradeoffs that drove the decision
---------------------------------
- MLB Stats API: JSON, structured, modern endpoint. Trivial parser.
  2008+ coverage. Same endpoint as live inference (no train/serve skew).
- Retrosheet: dense event notation (S8/G, K, IBB, etc.). Free since 1918.
  Requires cwgame/cwevent C tools OR pybaseball.retrosheet OR a custom
  parser. Adds external-binary dependency or scraping risk.

If we ever need 1918-2007 PBP (which we currently don't), come back here.
"""

# Plan B (not implemented): pybaseball.retrosheet.events(season) returns a
# DataFrame of events that maps onto the same `plays` schema.
