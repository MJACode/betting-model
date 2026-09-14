"""Game-model qualitative veto — starter/goalie/star Out before the quote.

NOT A FEATURE. `home_starter_out` / `injury_adj` in the feature engine are
trained averages (and `_has_starter_out` fires on any IL player with no
position). This gate lives at emit time, same clock as
`models.nfl_prop_injury_veto`: if the relevant starter/star is Out and
`status_ts <= quote snapshot_at`, refuse the BET. News after the quote is
ignored (look-ahead). Missing either clock fails OPEN.

Reprice is the next scoring pass: MLB already rebuilds features from
`mlb_pitcher_stats` when Stats API lists a new probable; NHL writes the
ESPN probable starting goalie into `nhl_goalie_stats` (`espn_probables`).
A NONE here is not locked (the game lock is BET-only), so a later pass
with the new starter can still fire.

Sports:
  MLB  — probable pitcher (mlb_pitcher_stats) Out / IL10 / IL15 / IL60
  NHL  — game-day goalie (nhl_goalie_stats) Out / Doubtful
  NBA / WNBA — top-2 by recent minutes (star DNP) Out

Not applied: NCAAF (injuries excluded by design), UFC, nfl_opener_spread /
nfl_wind_totals (opener IS a stale-number race; wind is the physical residual).
"""
from __future__ import annotations

from data.ingestors.nfl_props_data_ingestor import norm_player_name
from models.nfl_prop_injury_veto import should_veto

GATED_SPORTS = frozenset({"MLB", "NHL", "NBA", "WNBA"})

# Per-role statuses. Lowercased to match should_veto.
PITCHER_STATUSES = frozenset({"out", "il10", "il15", "il60"})
GOALIE_STATUSES = frozenset({"out", "doubtful"})
STAR_STATUSES = frozenset({"out"})

STAR_TIER = 2
STAR_MIN_MINUTES = 20.0
STAR_LOOKBACK_GAMES = 10
STAR_MIN_APPEARANCES = 5

_LOG_TABLE = {"NBA": "nba_player_game_log", "WNBA": "wnba_player_game_log"}


def stars_from_logs(rows: list[dict], team: str, game_date: str,
                    tier: int = STAR_TIER,
                    min_minutes: float = STAR_MIN_MINUTES,
                    lookback: int = STAR_LOOKBACK_GAMES,
                    min_appearances: int = STAR_MIN_APPEARANCES) -> list[str]:
    """Top-`tier` players on `team` by avg minutes over the last `lookback`
    team-games before `game_date`. Pure — the caller supplies log dicts.

    Measured 2026-09-14 on WNBA 2026 (players with ≥8 games): 198 rotation
    players, 64 at ≥24 mpg, 42 at ≥28. Top-2 per team at ≥20 mpg is the
    star tier, not the 6th man.
    """
    team_dates = sorted({
        r["game_date"] for r in rows
        if r.get("team") == team and r.get("game_date") and r["game_date"] < game_date
    })[-lookback:]
    window = set(team_dates)
    if not window:
        return []
    by_player: dict[str, list[float]] = {}
    names: dict[str, str] = {}
    for r in rows:
        if r.get("team") != team or r.get("game_date") not in window:
            continue
        mins = r.get("minutes") or 0
        if mins <= 0:
            continue
        key = r.get("player_id") or r.get("player_name")
        if not key:
            continue
        by_player.setdefault(key, []).append(float(mins))
        if r.get("player_name"):
            names[key] = r["player_name"]
    ranked = []
    for key, mins in by_player.items():
        if len(mins) < min_appearances:
            continue
        avg = sum(mins) / len(mins)
        if avg < min_minutes:
            continue
        name = names.get(key)
        if name:
            ranked.append((avg, name))
    ranked.sort(reverse=True)
    return [name for _, name in ranked[:tier]]


def player_matches_veto(player: str, quote_ts, injury_index: dict,
                        statuses: frozenset[str]) -> bool:
    if not player or not injury_index:
        return False
    rows = injury_index.get(norm_player_name(player)) or ()
    return any(
        should_veto(r.get("status"), r.get("status_ts"), quote_ts, statuses=statuses)
        for r in rows
    )


def veto_reason(quote_ts, relevant: list[dict], injury_index: dict) -> str | None:
    """Human reason if any relevant player is Out with status_ts ≤ quote.

    `relevant` is [{player_name, role, statuses}, ...]. Empty / missing
    clocks / unknown players return None (fail open).
    """
    if not relevant or not injury_index:
        return None
    hits = []
    for item in relevant:
        name = item.get("player_name") or ""
        statuses = item.get("statuses") or STAR_STATUSES
        if player_matches_veto(name, quote_ts, injury_index, statuses):
            hits.append(f"{item.get('role', 'player')} {name}")
    if not hits:
        return None
    return "injury gate: " + "; ".join(hits) + " Out before quote"


def load_sport_injury_index(conn, sport: str, as_of_date: str | None = None) -> dict:
    """Latest injury report on or before `as_of_date`, keyed by norm name.

    Fail-open: missing column / dead connection / no rows → {}.
    """
    if conn is None or sport not in GATED_SPORTS:
        return {}
    try:
        if as_of_date:
            latest = conn.execute(
                """
                SELECT MAX(report_date) FROM injuries
                WHERE sport = %s AND report_date <= %s
                """,
                (sport, as_of_date),
            ).fetchone()
        else:
            latest = conn.execute(
                "SELECT MAX(report_date) FROM injuries WHERE sport = %s",
                (sport,),
            ).fetchone()
        report_date = latest[0] if latest else None
        if not report_date:
            return {}
        rows = conn.execute(
            """
            SELECT player_name, status, status_ts, team
            FROM injuries
            WHERE sport = %s AND scenario = 'A' AND report_date = %s
            """,
            (sport, report_date),
        ).fetchall()
    except Exception:  # noqa: BLE001
        return {}

    out: dict[str, list] = {}
    for player_name, status, status_ts, team in rows or ():
        key = norm_player_name(player_name)
        if not key:
            continue
        out.setdefault(key, []).append({
            "status": status, "status_ts": status_ts,
            "player_name": player_name, "team": team,
        })
    return out


def _pitcher_names(conn, team: str, game_date: str) -> list[str]:
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT player_name FROM mlb_pitcher_stats
            WHERE team = %s AND game_date = %s AND player_name IS NOT NULL
            """,
            (team, game_date),
        ).fetchall()
    except Exception:  # noqa: BLE001
        return []
    return [r[0] for r in rows or () if r and r[0]]


def _goalie_names(conn, team: str, game_date: str) -> list[str]:
    """Game-day probable first; no ASOF fallback to the season snapshot.

    The season-start row is last year's #1. Matching that name against
    tonight's injury report would veto a backup start. Missing game-day
    row → no relevant player → fail open.
    """
    try:
        rows = conn.execute(
            """
            SELECT player_name FROM nhl_goalie_stats
            WHERE team = %s AND game_date = %s AND player_name IS NOT NULL
            ORDER BY created_at DESC
            """,
            (team, game_date),
        ).fetchall()
    except Exception:  # noqa: BLE001
        return []
    names = []
    seen = set()
    for r in rows or ():
        name = r[0] if r else None
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _star_names(conn, sport: str, team: str, game_date: str) -> list[str]:
    table = _LOG_TABLE.get(sport)
    if not table:
        return []
    try:
        rows = conn.execute(
            f"""
            SELECT player_id, player_name, team, game_date, minutes
            FROM {table}
            WHERE team = %s AND game_date < %s AND minutes IS NOT NULL
            """,
            (team, game_date),
        ).fetchall()
    except Exception:  # noqa: BLE001
        return []
    logs = [
        {"player_id": r[0], "player_name": r[1], "team": r[2],
         "game_date": r[3], "minutes": r[4]}
        for r in rows or ()
    ]
    return stars_from_logs(logs, team, game_date)


def relevant_players(conn, sport: str, game_date: str,
                     home_team: str, away_team: str) -> list[dict]:
    """Named players the gate watches for this game. Empty → fail open."""
    if conn is None or sport not in GATED_SPORTS:
        return []
    out: list[dict] = []
    if sport == "MLB":
        for team in (home_team, away_team):
            for name in _pitcher_names(conn, team, game_date):
                out.append({"player_name": name, "role": f"{team} starter",
                            "statuses": PITCHER_STATUSES})
    elif sport == "NHL":
        for team in (home_team, away_team):
            for name in _goalie_names(conn, team, game_date):
                out.append({"player_name": name, "role": f"{team} goalie",
                            "statuses": GOALIE_STATUSES})
    elif sport in ("NBA", "WNBA"):
        for team in (home_team, away_team):
            for name in _star_names(conn, sport, team, game_date):
                out.append({"player_name": name, "role": f"{team} star",
                            "statuses": STAR_STATUSES})
    return out


def apply_to_picks(picks: list[dict], quote_ts, relevant: list[dict],
                   injury_index: dict) -> dict:
    """Downgrade BET picks when a relevant player is Out before the quote.

    Per-pick `_quote_snapshot_at` wins when present (decision-book clock);
    otherwise `quote_ts`. Missing clock → that pick fails open.
    Mutates in place. Returns {"injury_gate": n_downgraded}.
    """
    n = 0
    if not picks or not relevant or not injury_index:
        return {"injury_gate": 0}
    for p in picks:
        if p.get("signal_type") != "BET":
            continue
        ts = p.get("_quote_snapshot_at", quote_ts)
        reason = veto_reason(ts, relevant, injury_index)
        if not reason:
            continue
        p["signal_type"] = "NONE"
        p["kelly_fraction"] = 0.0
        p["recommended_bet"] = 0.0
        p["downgrade_reason"] = reason
        n += 1
    return {"injury_gate": n}
