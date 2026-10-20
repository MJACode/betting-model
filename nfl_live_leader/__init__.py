"""NFL in-play leader moneyline model (`nfl_live_leader_ml`).

Late in the fourth quarter, bet the team that leads by 4-16 points on
DraftKings' live moneyline when an empirical win-probability model says the
price is at least two points too long. The model and the rule are the backtest
in scripts/nfl_edge_inplay_2024.py / nfl_edge_inplay_2025.py (cell "H1 leader
ref=pbp secs<=600 edge>=0.02", venue DraftKings), ported unchanged.

Runs from the REPO ROOT (`python -m nfl_live_leader.gameday`), like
ncaaf_live/. It is deliberately not under nfl/: that package runs with
cwd=nfl/ and carries its own `models/` and `data_ingest/`, so a platform import
from inside it resolves to the wrong module (data/live_quote_guard.py explains
the trap).

  model.py    the artifact, wp(), decide()          pure, no I/O
  state.py    ESPN sports.core -> the model's inputs
  odds.py     one bulk DraftKings h2h call per evaluation, credit-capped
  gameday.py  the loop: state every 20 s, evaluate each in-window game every 5 min
"""
