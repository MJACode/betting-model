"""The game state at each live quote's stamp, by the lab's own functions.

Nothing here re-derives the state. ESPN's summary is turned back into the
release rows the lab read (nba_live.espn.records_from_summary), and then
data/ingestors/nba_pbp.slim_plays, scripts/nba_ingame_data.plays_frame,
drop_wild_wallclocks, phase_bounds, top_players, timeline and attach_state
build the rows exactly as they built scripts/nba_ingame_data.py's table. The
only live-specific piece is the PHASE of a game that has not finished:

  The lab labels a stamp after the last period's end "postgame" because its
  games were over. Live, the last period seen is still being played unless
  ESPN has logged its End Period row; and a stamp after that row, before the
  next period's first play, is the break (halftime after period 2). So for a
  game ESPN does not report final, the open period's end is pushed past any
  stamp, or, when it has ended, an empty next period starting past any stamp
  is added. A finished game keeps the lab's labels.

QUOTES. A fetch's rows become the lab's quote frame (load_quotes's columns):
`stamp` is the book's own last_update for the market, `fetch_at` the tick,
`served_at` the moment the response arrived, `served_newest` the newest stamp
in the response. A quote stamped more than 90 minutes before the listed tip
cannot be in play and is dropped, as the lab dropped it. A (game, market,
book) quote whose stamp was already seen at an earlier tick is dropped too:
the lab kept a stamp only at the first purchase that returned it (54 of
791,527 rows in six seasons, scripts/nba_ingame_data.load_quotes).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from data.ingestors import nba_pbp as P
from scripts import nba_game_harness as H
from scripts import nba_ingame_data as D
from scripts.nba_game_market_lab import imp

FAR = pd.Timestamp("2200-01-01", tz="UTC")


def plays_from_records(records: list[dict], espn_game_id: int, game_id: str, season: int,
                       swapped: bool = False) -> pd.DataFrame:
    """Release-shaped rows -> the lab's per-play frame (scripts/nba_ingame_data.plays_frame)."""
    rows = P.slim_plays(records, espn_game_id=int(espn_game_id), game_id=game_id,
                        season=int(season), season_type=2, swapped=swapped)
    return D.plays_frame(rows)


def sides_swapped(records: list[dict], espn_game_id: int, home: str, away: str) -> bool | None:
    """False when ESPN's home is ours, True when it is our away (a neutral-site
    game listed the other way round), None when the teams are not this game's."""
    meta = P.espn_game_meta(int(espn_game_id), records) if records else None
    if not meta:
        return None
    if meta["home"] == home and meta["away"] == away:
        return False
    if meta["home"] == away and meta["away"] == home:
        return True
    return None


def live_bounds(plays: pd.DataFrame, final: bool) -> pd.DataFrame:
    """scripts/nba_ingame_data.phase_bounds, with the open period of a game in
    progress left open (module docstring)."""
    b = D.phase_bounds(plays)
    if final or b.empty:
        return b
    b = b.copy()
    t = plays["type_text"].fillna("")
    ended = set(zip(plays.loc[t == "End Period", "game_id"], plays.loc[t == "End Period", "period"]))
    extra = []
    for gid, g in b.groupby("game_id"):
        i = g["period"].idxmax()
        per = int(b.at[i, "period"])
        if (gid, per) in ended:
            extra.append({"game_id": gid, "period": per + 1, "start": FAR, "end": FAR})
        else:
            b.at[i, "end"] = FAR
    if extra:
        b = pd.concat([b, pd.DataFrame(extra)], ignore_index=True)
    return b


def top_players(game_id: str, espn_game_id: int, box: list[dict], side_of: dict,
                prior_min: dict) -> pd.DataFrame:
    """scripts/nba_ingame_data.top_players on the live box: each side's three
    starters with the most minutes per game in their earlier games this season
    (else last season's average, else 0), ties to the lower athlete id.
    box: espn.starters_from_summary rows; side_of: ESPN team abbreviation ->
    'H' / 'A' (ours); prior_min: athlete_id -> minutes per game."""
    rows = [{"game_id": game_id, "espn_game_id": int(espn_game_id), "athlete_id": int(r["athlete_id"]),
             "side": side_of.get(r["team_abbr"]), "starter": bool(r["starter"])}
            for r in box if side_of.get(r["team_abbr"]) in (D.HOME, D.AWAY)]
    bx = pd.DataFrame(rows, columns=["game_id", "espn_game_id", "athlete_id", "side", "starter"])
    pr = pd.DataFrame([{"espn_game_id": int(espn_game_id), "athlete_id": int(a), "prior_min": float(m)}
                       for a, m in prior_min.items()],
                      columns=["espn_game_id", "athlete_id", "prior_min"])
    if bx.empty:
        return pd.DataFrame(columns=["game_id", "side", "rank", "athlete_id"])
    return D.top_players(bx, pr)


def quote_frame(odds_rows: list[dict], games: dict, fetch_at: pd.Timestamp,
                served_at: pd.Timestamp, books, seen: set | None = None) -> pd.DataFrame:
    """Live odds rows (data/ingestors/odds_ingestor._process_events, h2h and
    spreads) -> the lab's quote frame (scripts/nba_ingame_data.load_quotes's
    columns). `games`: game_id -> {'season', 'game_date', 'tip'}. `seen`:
    (game, market, book, stamp) already returned at an earlier tick."""
    cols = ["game_id", "season", "game_date", "tip", "market", "book", "label", "stamp",
            "fetch_at", "served_at", "served_newest", "line", "price_a", "price_b",
            "implied_sum", "coherent", "fa"]
    if not odds_rows:
        return pd.DataFrame(columns=cols)
    o = pd.DataFrame(odds_rows)
    o = o[o["market"].isin(("h2h", "spreads")) & o["bookmaker"].isin(tuple(books))].copy()
    if o.empty:
        return pd.DataFrame(columns=cols)
    o["stamp"] = pd.to_datetime(o["snapshot_at"], utc=True, format="mixed", errors="coerce")
    newest = o["stamp"].max()
    o = o[o["game_id"].isin(set(games)) & o["stamp"].notna()].copy()
    if o.empty:
        return pd.DataFrame(columns=cols)
    o["season"] = o["game_id"].map(lambda g: games[g]["season"])
    o["game_date"] = o["game_id"].map(lambda g: games[g]["game_date"])
    o["tip"] = pd.to_datetime(o["game_id"].map(lambda g: games[g]["tip"]), utc=True)
    o = o[o["stamp"] >= o["tip"] - pd.Timedelta(minutes=D.PREFILTER_MIN)]
    o = o.rename(columns={"bookmaker": "book", "snapshot_type": "label"})
    o["fetch_at"], o["served_at"], o["served_newest"] = fetch_at, served_at, newest
    o = o.drop_duplicates(["game_id", "market", "book", "stamp"])
    if seen:
        o = o[[(g, m, b, s) not in seen for g, m, b, s in
               zip(o["game_id"], o["market"], o["book"], o["stamp"])]]
    for c in ("spread_home", "home_price", "away_price"):
        o[c] = pd.to_numeric(o[c], errors="coerce")
    o["line"] = np.where(o["market"] == "spreads", o["spread_home"], np.nan)
    o["price_a"], o["price_b"] = o["home_price"], o["away_price"]
    o = o[o["price_a"].notna() & o["price_b"].notna()].copy()
    if o.empty:
        return pd.DataFrame(columns=cols)
    ia, ib = imp(o["price_a"]), imp(o["price_b"])
    o["implied_sum"] = ia + ib
    o["coherent"] = (o["implied_sum"] >= H.COHERENT[0]) & (o["implied_sum"] <= H.COHERENT[1])
    o["fa"] = ia / (ia + ib)
    return o[cols].reset_index(drop=True)


def tick_rows(quotes: pd.DataFrame, plays: pd.DataFrame, top: pd.DataFrame,
              final: bool) -> tuple[pd.DataFrame, dict]:
    """One game's quotes at one tick -> the lab's in-play rows (the state at
    each stamp, the points since it, Pinnacle's paired quote), by
    scripts/nba_ingame_data.attach_state. `plays` is the game's play frame
    (plays_from_records) after drop_wild_wallclocks."""
    if quotes.empty or plays.empty:
        return quotes.iloc[0:0], {}
    tl = D.timeline(plays, top)
    bounds = live_bounds(plays, final)
    return D.attach_state(quotes, tl, bounds)
