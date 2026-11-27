"""Dunks & Threes' free game pages: its pre-game predictions for every NBA game, into Supabase.

WHY (mike, 2026-11-27: "I don't want to buy without testing", then "just test it with the free
data"). The API needs a paid key. The game pages do not: a page's data
(`/games/<id>/__data.json`, measured 2026-11-27 with `has_access` 0) carries

  game level   p_home_score, p_away_score, win_prob, both teams' EPM rank, the final score
  per player   p_stl, p_fg2m, p_fg2a, p_epm / p_oepm / p_depm, p_t_poss_48, p_pct_start, p_play
               (p_mp, p_pts, p_reb, p_ast, p_fg3m, p_blk and p_tov are null without a
               subscription)

for past games back to 2023-24 at least. Every row carries `epm_source` v2 on the API, so a
past game's numbers are TODAY's model run on the data before that date: a test on them is
optimistic (a null result ends it; a positive one needs forward confirmation). An unplayed
game's numbers are a true pre-game prediction.

Their terms prohibit automated copying of large portions of the site; mike's call
(2026-11-26: "We don't need any permission to use data just do it"). One request at a time,
PACE_S apart.

WHAT IS STORED. `dnt_game_predictions` (one row a game, `game_info` kept whole) and
`dnt_player_predictions` (one row a player and game, the free prediction fields and the
player's actual minutes, steals, points, rebounds, assists, threes and blocks), both under
source SOURCE, matched to our `games.game_id` by ET date and teams where one exists. The
ledger `dnt_game_page_fetches` holds one row per id read; a re-run reads nothing twice. A game
not yet final is not ledgered, so a later run reads it again once it is. Worker-only tables
(RLS on, anon revoked).

    python -m data.ingestors.dnt_game_pages --apply                    # 2023-24 to today
    python -m data.ingestors.dnt_game_pages --apply --seasons 2026 --limit 20
    python -m data.ingestors.dnt_game_pages                            # dry run: counts only
"""
from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from datetime import datetime, timezone

import requests
from loguru import logger

BASE = "https://dunksandthrees.com"
SOURCE = "dnt_free_game_page"
PACE_S = 1.2
UA = {"User-Agent": "Mozilla/5.0 (research; betting-model)", "Accept": "application/json"}
# Their ids: 2, the season's starting year's last two digits, then the game number (5 digits).
# A regular season is 1,230 games; ids past the last one answer 404 and are ledgered as such.
GAMES_PER_SEASON = 1230
SEASONS = (2024, 2025, 2026, 2027)          # our labels: the season's ENDING year (CLAUDE.md §4)

GAME_TABLE = "dnt_game_predictions"
PLAYER_TABLE = "dnt_player_predictions"
LEDGER = "dnt_game_page_fetches"
GAME_DDL = f"""
CREATE TABLE IF NOT EXISTS {GAME_TABLE} (
    dnt_game_id      BIGINT PRIMARY KEY,
    source           TEXT NOT NULL,
    season           INTEGER,
    seasontype       INTEGER,
    game_dt          DATE,
    game_dttm_et     TEXT,
    status_id        INTEGER,
    home_alias       TEXT,
    away_alias       TEXT,
    game_id          TEXT,
    p_home_score     DOUBLE PRECISION,
    p_away_score     DOUBLE PRECISION,
    win_prob         DOUBLE PRECISION,
    home_score       INTEGER,
    away_score       INTEGER,
    home_team_epm_rk INTEGER,
    away_team_epm_rk INTEGER,
    has_access       INTEGER,
    game_info        JSONB,
    fetched_at       TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""
PLAYER_COLS = ("p_play", "p_pct_start", "p_t_poss_48", "p_stl", "p_fg2m", "p_fg2a", "p_epm",
               "p_oepm", "p_depm", "mp", "stl", "pts", "reb", "ast", "fg3m", "blk")
PLAYER_DDL = f"""
CREATE TABLE IF NOT EXISTS {PLAYER_TABLE} (
    dnt_game_id   BIGINT NOT NULL,
    player_id     BIGINT NOT NULL,
    source        TEXT NOT NULL,
    team_id       BIGINT,
    player_name   TEXT,
    status        TEXT,
    starter       INTEGER,
    {", ".join(f"{c} DOUBLE PRECISION" for c in PLAYER_COLS)},
    PRIMARY KEY (dnt_game_id, player_id)
)
"""
LEDGER_DDL = f"""
CREATE TABLE IF NOT EXISTS {LEDGER} (
    dnt_game_id  BIGINT PRIMARY KEY,
    source       TEXT NOT NULL,
    http_status  INTEGER NOT NULL,
    status_id    INTEGER,
    n_players    INTEGER NOT NULL,
    game_id      TEXT,
    note         TEXT,
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""
# Standard alternate NBA codes, applied only to a code that is not one of ours.
CODE_ALIAS = {"GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS", "PHO": "PHX", "BRK": "BKN",
              "WSH": "WAS", "CHO": "CHA", "UTAH": "UTA", "NJ": "BKN"}


# ── pure pieces (tested) ─────────────────────────────────────────────────────

def dnt_ids(season: int, upto: int = GAMES_PER_SEASON) -> list[int]:
    """Our season label (ending year) -> their regular-season game ids. 2024 -> 22300001.."""
    return [int(f"2{(season - 2001) % 100:02d}{n:05d}") for n in range(1, upto + 1)]


def hydrate(data: list, i: int):
    """SvelteKit's __data.json is devalue-encoded: every value is an index into one flat array."""
    if not isinstance(i, int) or i < 0:
        return None                               # -1 undefined, -3 NaN, -4/-5 infinities, -6 -0
    v = data[i]
    if isinstance(v, dict):
        return {k: hydrate(data, j) for k, j in v.items()}
    if isinstance(v, list):
        if v and isinstance(v[0], str) and v[0] in ("Date", "Set", "Map", "BigInt", "RegExp"):
            return v[1] if len(v) > 1 else None
        return [hydrate(data, j) for j in v]
    return v


def page_node(body: dict) -> dict | None:
    """The node that carries `game_info` and `box`, decoded."""
    for node in body.get("nodes") or []:
        if isinstance(node, dict) and node.get("type") == "data" and node.get("data"):
            got = hydrate(node["data"], 0)
            if isinstance(got, dict) and "game_info" in got:
                return got
    return None


def our_code(code: str | None, ours: set[str]) -> str | None:
    c = (code or "").upper()
    if c in ours:
        return c
    a = CODE_ALIAS.get(c)
    return a if a in ours else None


def match_game(info: dict, games_by_date: dict, ours: set[str]) -> str | None:
    """Our games.game_id for their game: same ET date, same home and away team."""
    home, away = our_code(info.get("home_alias"), ours), our_code(info.get("away_alias"), ours)
    for g in games_by_date.get(str(info.get("game_dt")), []):
        if g["home"] == home and g["away"] == away:
            return g["game_id"]
    return None


def _num(x):
    try:
        return None if x is None or x == "" else float(x)
    except (TypeError, ValueError):
        return None


def rows_for(dnt_id: int, node: dict, our_game_id: str | None) -> tuple[dict, list[dict]]:
    info = node.get("game_info") or {}
    game = {
        "dnt_game_id": dnt_id, "source": SOURCE, "season": info.get("season"),
        "seasontype": info.get("seasontype"), "game_dt": info.get("game_dt"),
        "game_dttm_et": info.get("game_dttm"), "status_id": info.get("status_id"),
        "home_alias": info.get("home_alias"), "away_alias": info.get("away_alias"),
        "game_id": our_game_id, "p_home_score": _num(info.get("p_home_score")),
        "p_away_score": _num(info.get("p_away_score")), "win_prob": _num(info.get("win_prob")),
        "home_score": info.get("home_score"), "away_score": info.get("away_score"),
        "home_team_epm_rk": info.get("home_team_epm_rk"), "away_team_epm_rk": info.get("away_team_epm_rk"),
        "has_access": node.get("has_access"), "game_info": json.dumps(info, default=str),
    }
    players = []
    for b in node.get("box") or []:
        if not isinstance(b, dict) or b.get("player_id") is None:
            continue
        r = {"dnt_game_id": dnt_id, "player_id": int(b["player_id"]), "source": SOURCE,
             "team_id": b.get("team_id"), "player_name": b.get("player_name"),
             "status": b.get("status"), "starter": b.get("starter")}
        r.update({c: _num(b.get(c)) for c in PLAYER_COLS})
        players.append(r)
    return game, players


# ── database ─────────────────────────────────────────────────────────────────

def _games_by_date(conn) -> tuple[dict, set[str]]:
    rows = conn.execute(
        "SELECT game_id, game_date::text, home_team, away_team FROM games "
        "WHERE sport = 'NBA' AND season >= 2024 AND home_team <> 'NaN'").fetchall()
    by: dict[str, list] = defaultdict(list)
    ours: set[str] = set()
    for gid, d, h, a in rows:
        by[d].append({"game_id": gid, "home": h, "away": a})
        ours |= {h, a}
    return by, ours


def _ensure(conn) -> None:
    from data.anon_readable import lock_down
    from data.ddl_guard import schema_is_current
    for table, ddl in ((GAME_TABLE, GAME_DDL), (PLAYER_TABLE, PLAYER_DDL), (LEDGER, LEDGER_DDL)):
        if not schema_is_current(conn, table):
            conn.execute(ddl)
        lock_down(conn, table)
    conn.commit()


def _store(conn, game: dict, players: list[dict], ledger: dict) -> None:
    gcols = list(game)
    cast = {"game_info": "::jsonb", "game_dt": "::date"}
    conn.execute(f"INSERT INTO {GAME_TABLE} ({', '.join(gcols)}) VALUES "
                 f"({', '.join(f'%({c})s' + cast.get(c, '') for c in gcols)}) ON CONFLICT DO NOTHING",
                 game)
    if players:
        pcols = list(players[0])
        conn.executemany(f"INSERT INTO {PLAYER_TABLE} ({', '.join(pcols)}) VALUES "
                         f"({', '.join(f'%({c})s' for c in pcols)}) ON CONFLICT DO NOTHING", players)
    _ledger(conn, ledger)


def _ledger(conn, row: dict) -> None:
    conn.execute(f"""INSERT INTO {LEDGER} (dnt_game_id, source, http_status, status_id, n_players,
                         game_id, note)
                     VALUES (%(dnt_game_id)s, %(source)s, %(http_status)s, %(status_id)s,
                         %(n_players)s, %(game_id)s, %(note)s)
                     ON CONFLICT DO NOTHING""", row)
    conn.commit()


def run(seasons: tuple[int, ...], apply: bool, limit: int | None) -> dict:
    from data.db import get_connection
    conn = get_connection()
    stats: dict[str, int] = defaultdict(int)
    try:
        if apply:
            _ensure(conn)
            done = {r[0] for r in conn.execute(f"SELECT dnt_game_id FROM {LEDGER}").fetchall()}
        else:
            done = set()
        by_date, ours = _games_by_date(conn)
        todo = [i for s in seasons for i in dnt_ids(s) if i not in done]
        if limit:
            todo = todo[:limit]
        logger.info(f"D&T game pages: {len(todo)} to read ({len(done)} already ledgered)")
        if not apply:
            return {"to_read": len(todo), "ledgered": len(done)}
        s = requests.Session()
        misses_in_a_row = 0
        last_season = None
        for n, dnt_id in enumerate(todo, 1):
            season_key = str(dnt_id)[:3]
            if season_key != last_season:
                last_season, misses_in_a_row = season_key, 0
            elif misses_in_a_row >= 15:
                continue                          # past this season's last game: stop asking
            time.sleep(PACE_S)
            try:
                r = s.get(f"{BASE}/games/{dnt_id}/__data.json", headers=UA, timeout=40)
            except Exception as exc:  # noqa: BLE001 - not ledgered: the next run tries again
                stats["network_error"] += 1
                logger.warning(f"D&T {dnt_id}: {exc!r}")
                continue
            base = {"dnt_game_id": dnt_id, "source": SOURCE, "http_status": r.status_code,
                    "status_id": None, "n_players": 0, "game_id": None, "note": None}
            if r.status_code == 404:
                misses_in_a_row += 1          # past the season's last game
                stats["404"] += 1
                _ledger(conn, {**base, "note": "no such game"})
                continue
            if r.status_code != 200:
                stats[f"http_{r.status_code}"] += 1      # not ledgered: tried again next run
                continue
            node = page_node(r.json())
            if not node or not node.get("game_info"):
                misses_in_a_row += 1
                stats["no_game_info"] += 1
                _ledger(conn, {**base, "note": "no game_info in the page"})
                continue
            info = node["game_info"]
            if info.get("status_id") != 3:
                # Not ledgered: read again once it is final. Ids run in date order, so a run of
                # unplayed games is this season's future: the miss count stops the season.
                misses_in_a_row += 1
                stats["not_final"] += 1
                continue
            misses_in_a_row = 0
            gid = match_game(info, by_date, ours)
            game, players = rows_for(dnt_id, node, gid)
            _store(conn, game, players, {**base, "status_id": info.get("status_id"),
                                         "n_players": len(players), "game_id": gid,
                                         "note": None if gid else "no games row matched"})
            stats["stored"] += 1
            stats["matched"] += bool(gid)
            stats["players"] += len(players)
            if n % 100 == 0:
                logger.info(f"D&T game pages: {n}/{len(todo)} {dict(stats)}")
        return dict(stats)
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--seasons", type=int, nargs="+", default=list(SEASONS))
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    out = run(tuple(a.seasons), a.apply, a.limit)
    logger.info(f"D&T game pages: done {out}")
    print("DNT|import|done|" + json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
