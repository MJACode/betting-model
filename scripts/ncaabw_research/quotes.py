"""The fetched odds snapshots as research tables, parsed by the production
parser (odds_ingestor._process_events through the purchase's resolver), so the
research reads what production stores.

  cache/pregame_quotes.parquet  change-only pre-game quotes (the `odds` rows)
  cache/inplay_quotes.parquet   every in-play quote of every snapshot
  cache/boards.parquet          the whole pre-game board of each game at fixed
                                leads before ESPN's tip: the newest snapshot at
                                or before tip - lead (and no older than 10
                                minutes before that), every book's row as listed
  cache/snapshots.parquet       one row a snapshot

    python -m scripts.ncaabw_research.quotes            (no paid call)
"""
import gzip
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.ncaabw_research._paths import CACHE, SPOOL  # noqa: E402,F401

from data.ingestors import ncaabw_odds_history as H  # noqa: E402
from data.ingestors import ncaabw_teams as nt  # noqa: E402
from data.ingestors.odds_ingestor import _mark_in_play, _process_events  # noqa: E402

LEADS = (0, 10, 20, 30, 45, 60, 90, 120, 180, 240, 360)     # minutes before the tip
from loguru import logger  # noqa: E402
logger.remove()            # the parser warns once per unplaced event per snapshot; counted below instead
STALE = timedelta(minutes=10)

REG = CACHE / "registry.json"
if not REG.exists():
    from data.db import get_connection  # noqa: E402
    with get_connection() as conn:
        nt.reset_registry_cache()
        reg = nt.load_registry(conn)
    REG.write_text(json.dumps(reg), encoding="utf-8")
registry = json.loads(REG.read_text(encoding="utf-8"))

g = pd.read_parquet(CACHE / "games.parquet")
games = [{"game_id": r.game_id, "game_date": str(r.game_date)[:10], "commence_time": r.commence_time,
          "home_espn_id": int(r.home_espn_id), "away_espn_id": int(r.away_espn_id)}
         for r in g.itertuples(index=False)]
tips = {x["game_id"]: H._utc(x["commence_time"]) for x in games}
resolver = H.EventResolver(registry, games)
now = datetime.now(timezone.utc)
VAL = ("home_price", "away_price", "spread_home", "total_line", "over_price", "under_price")

pre, live, snaps = [], [], []
board: dict = {}          # (game_id, lead) -> (snapshot ts, [rows])
n_open = 0
for season, days in sorted(H.season_days(games, now).items()):
    if season < 2025:
        continue
    keeper = H.ChangeKeeper()
    listed = H.spool_snapshots(SPOOL, days)
    n_open += sum(1 for d in days if not H.read_state(SPOOL, d)["done"])
    for s in listed:
        with gzip.open(s["path"], "rt", encoding="utf-8") as fh:
            body = json.load(fh)
        ts = H._utc(body["timestamp"])
        events = body.get("data") or []
        _, rows = _process_events(events, H.SPORT, "open", H._stamp(ts), resolve_game_id=resolver)
        fed = {}
        for ev in events:
            hit = resolver(ev.get("home_team") or "", ev.get("away_team") or "",
                           ev.get("commence_time") or "")
            if hit:
                fed[hit[0]] = H._utc(ev.get("commence_time"))
            else:
                resolver.note_miss(ev)
        got = {r["game_id"] for r in rows}
        starts = [{"game_id": gid, "commence_time": (tips.get(gid) or fed.get(gid)).isoformat()
                   if (tips.get(gid) or fed.get(gid)) else None} for gid in got]
        _mark_in_play(starts, rows)
        n_pre = n_live = 0
        by_game: dict = {}
        for r in rows:
            vals = tuple(r.get(c) for c in VAL)
            if r.get("snapshot_type") == "in_play":
                live.append((ts, r["game_id"], r["bookmaker"], r["market"], r["snapshot_at"], *vals))
                n_live += 1
                continue
            by_game.setdefault(r["game_id"], []).append(
                (r["bookmaker"], r["market"], r["snapshot_at"], *vals))
            if keeper.wanted(r):
                pre.append((r["game_id"], r["bookmaker"], r["market"], r["snapshot_at"], ts, *vals))
                n_pre += 1
        for gid, brows in by_game.items():
            tip = tips.get(gid) or fed.get(gid)
            if tip is None or ts > tip:
                continue
            for lead in LEADS:
                at = tip - timedelta(minutes=lead)
                if at - STALE <= ts <= at:
                    board[(gid, lead)] = (ts, brows)        # ascending: the newest wins
        snaps.append((ts, season, len(events), n_pre, n_live, s["credits"]))
    print(f"season {season}: {len(listed):,} snapshots read", flush=True)

P = pd.DataFrame(pre, columns=["game_id", "bookmaker", "market", "last_update", "snapshot_ts", *VAL])
L = pd.DataFrame(live, columns=["snapshot_ts", "game_id", "bookmaker", "market", "last_update", *VAL])
B = pd.DataFrame([(gid, lead, ts, *row) for (gid, lead), (ts, brows) in board.items() for row in brows],
                 columns=["game_id", "lead", "snapshot_ts", "bookmaker", "market", "last_update", *VAL])
S = pd.DataFrame(snaps, columns=["snapshot_ts", "season", "events", "pregame_rows", "inplay_rows",
                                 "credits"])
for df in (P, L, B):
    df["last_update"] = pd.to_datetime(df["last_update"], utc=True)
    for c in VAL:
        df[c] = pd.to_numeric(df[c], errors="coerce")
P.to_parquet(CACHE / "pregame_quotes.parquet", index=False)
L.to_parquet(CACHE / "inplay_quotes.parquet", index=False)
B.to_parquet(CACHE / "boards.parquet", index=False)
S.to_parquet(CACHE / "snapshots.parquet", index=False)
print(f"snapshots {len(S):,} | credits {int(S['credits'].sum()):,} | days still open {n_open}")
print(f"pre-game rows {len(P):,} on {P['game_id'].nunique():,} games | "
      f"in-play rows {len(L):,} on {L['game_id'].nunique():,} games | board rows {len(B):,}")
print("games with a board, by lead:", B.groupby("lead")["game_id"].nunique().to_dict())
print("pre-game games by book and market:")
print(P.groupby(["bookmaker", "market"])["game_id"].nunique().unstack().fillna(0).astype(int).to_string())
print(resolver.report(top=40))
