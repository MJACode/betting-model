"""NBA in-play loop for the game-state models (models/nba_live_ingame.py).

    python -m nba_live.gameday              # the real thing (scheduler job nba_live_ingame)
    python -m nba_live.gameday --dry-run    # decide and log; write nothing, post nothing
    python -m nba_live.gameday --once       # one pass, then exit

espn.py   ESPN's NBA scoreboard and game summary (free), parsed into the
          play-by-play rows the lab was built from
state.py  the game state at each quote's stamp, by the lab's own functions
odds.py   the one live odds call per tick, its credits measured and capped
gameday.py the loop: the hourly tick, the decision, the lock, the picks
"""
