"""
wnba_availability.py — availability, rotation role, and usage derivations for
WNBA player-prop models.

WHY THIS EXISTS
---------------
Every WNBA prop model scores on 16 backward-looking columns and has no input
describing TONIGHT: who is playing, how many minutes they project for, or how
much shot volume a teammate's absence frees up. DraftKings reprices on exactly
that news. Measured on our own game log (2019-2026, 16,820 non-regular
player-games), each rotation regular who sits is worth to the players who
remain:

    regulars out :  0        1        2        3+
    avg minutes  : 13.17    15.14    17.56    20.13
    avg FGA      :  3.86     4.50     5.36     6.10
    avg points   :  4.44     5.09     6.01     7.07

Monotone, and ~+0.9 points per absence — several times the ~2pp edge deficit
the points model needs to close. This module turns that into features.

TWO DESIGN DECISIONS THAT ARE LOAD-BEARING
------------------------------------------
1. AVAILABILITY IS DERIVED FROM THE BOX SCORE, NOT THE `injuries` TABLE.
   The brief called for injury-table features, but `injuries` holds WNBA rows
   only from 2026-06-07. With train=2019-2025 / holdout=2026 that column is
   NULL for 100% of training rows and present in the holdout — a feature the
   model cannot learn from and that dropna would use to delete the entire
   matrix. Presence/absence in `wnba_player_game_log` reconstructs the same
   fact for all eight seasons. It is legitimately knowable pre-tip in
   production (lineups post ~30 min before), so it is not look-ahead — see
   the caveat on `expected_rotation` about DNP-coach's-decision.

2. ROLE IS DERIVED FROM MINUTES RANK, NOT `is_starter`.
   `is_starter` is 100% NULL for 2019-2025 and only 38% populated in 2026.
   The existing `_recent_starter()` helper turns that into a constant 0 for
   every historical row, so the models' one role feature is dead in training
   and then partially live at serve time — a train/serve skew. Ranking a
   player by their own recent minutes reproduces the intent with full
   coverage across every season.

Everything here is a pure function over already-loaded rows so it can be unit
tested without a database. The caller supplies rows shaped like
`wnba_player_game_log` dicts.
"""

from __future__ import annotations

# A player counts as part of the expected rotation if, over the team's recent
# games, they appeared at least this often and averaged at least this many
# minutes. Tuned to sit just under a bench-rotation workload: WNBA teams play
# 9-10, so 15 minutes separates rotation from garbage time.
ROTATION_LOOKBACK_GAMES = 10
ROTATION_MIN_APPEARANCE_SHARE = 0.5
ROTATION_MIN_MINUTES = 15.0

# A "starter-tier" player is one of the top N by recent minutes on their team.
STARTER_TIER_SIZE = 5

# Free-throw weight in the standard possession estimate.
FT_POSSESSION_WEIGHT = 0.44


# ── small helpers ─────────────────────────────────────────────────────────────

def _mean(values) -> float | None:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _safe_div(numerator, denominator) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def prior_rows(rows: list[dict], game_date: str) -> list[dict]:
    """Rows strictly before game_date. Rows must be date-ascending."""
    return [r for r in rows if r["game_date"] < game_date]


# ── rotation role ─────────────────────────────────────────────────────────────

def recent_team_game_dates(team_rows: list[dict], game_date: str,
                           lookback: int = ROTATION_LOOKBACK_GAMES) -> list[str]:
    """The team's last `lookback` distinct game dates before game_date."""
    dates = sorted({r["game_date"] for r in team_rows if r["game_date"] < game_date})
    return dates[-lookback:]


def expected_rotation(team_rows: list[dict], game_date: str,
                      lookback: int = ROTATION_LOOKBACK_GAMES,
                      min_share: float = ROTATION_MIN_APPEARANCE_SHARE,
                      min_minutes: float = ROTATION_MIN_MINUTES) -> dict[str, dict]:
    """
    Who we expect to be available for this team tonight, judged only on games
    BEFORE game_date.

    Returns {player_id: {"avg_minutes", "avg_fga", "avg_points", "appearances"}}.

    Caveat, stated rather than hidden: a player who is active but gets a DNP
    for coaching reasons is indistinguishable here from one who was ruled out,
    and that IS a small optimism, since a DNP is not knowable pre-tip. It is
    rare among players clearing the 15-minute bar, and the alternative (using
    minutes actually played) would leak in-game injury information.
    """
    window = set(recent_team_game_dates(team_rows, game_date, lookback))
    if not window:
        return {}

    by_player: dict[str, list[dict]] = {}
    for r in team_rows:
        if r["game_date"] in window and (r.get("minutes") or 0) > 0:
            by_player.setdefault(r["player_id"], []).append(r)

    rotation: dict[str, dict] = {}
    for pid, prows in by_player.items():
        share = len(prows) / len(window)
        avg_min = _mean(r.get("minutes") for r in prows)
        if share >= min_share and (avg_min or 0) >= min_minutes:
            rotation[pid] = {
                "avg_minutes":  round(avg_min, 3),
                "avg_fga":      round(_mean(r.get("fg_att") for r in prows) or 0.0, 3),
                "avg_points":   round(_mean(r.get("points") for r in prows) or 0.0, 3),
                "appearances":  len(prows),
            }
    return rotation


def rotation_rank(rotation: dict[str, dict], player_id: str) -> int | None:
    """1 = most minutes on the team. None if the player is not in the rotation."""
    if player_id not in rotation:
        return None
    order = sorted(rotation.items(), key=lambda kv: kv[1]["avg_minutes"], reverse=True)
    for i, (pid, _) in enumerate(order, start=1):
        if pid == player_id:
            return i
    return None


def is_starter_tier(rotation: dict[str, dict], player_id: str,
                    tier: int = STARTER_TIER_SIZE) -> int:
    """Minutes-rank replacement for the dead `is_starter` column."""
    rank = rotation_rank(rotation, player_id)
    return int(rank is not None and rank <= tier)


# ── availability / absence ────────────────────────────────────────────────────

def absent_teammates(rotation: dict[str, dict], present_ids: set[str],
                     exclude_player_id: str | None = None) -> list[str]:
    """Expected-rotation players with no box-score row for this game."""
    return [pid for pid in rotation
            if pid not in present_ids and pid != exclude_player_id]


def absence_features(rotation: dict[str, dict], present_ids: set[str],
                     player_id: str) -> dict:
    """
    How much opportunity tonight's absences free up for this player.

    A count of bodies is the weak version; what actually redistributes is the
    minutes and shot volume those bodies would have taken, so the headline
    features are sums of the absentees' recent workload. `teammate_fga_out` is
    the one that should matter most for a points line, since attempts track
    minutes at r=0.79 while makes carry shooting noise on top.
    """
    absentees = absent_teammates(rotation, present_ids, exclude_player_id=player_id)
    return {
        "teammates_out":        len(absentees),
        "teammate_minutes_out": round(sum(rotation[p]["avg_minutes"] for p in absentees), 3),
        "teammate_fga_out":     round(sum(rotation[p]["avg_fga"] for p in absentees), 3),
        "teammate_points_out":  round(sum(rotation[p]["avg_points"] for p in absentees), 3),
        "top_teammate_out":     int(any(
            rotation[p]["avg_points"] >= max(
                (rotation[q]["avg_points"] for q in rotation if q != player_id),
                default=0.0)
            for p in absentees
        )) if absentees else 0,
    }


# ── usage / shot volume ───────────────────────────────────────────────────────

def usage_features(player_prior: list[dict], windows=(3, 5, 10)) -> dict:
    """
    Shot-volume and efficiency features from columns already in the game log.

    `fg_att`, `fg3_att` and `ft_att` are populated for 100% of rows in all eight
    seasons and no prop model reads any of them; the models use made counts
    only. Attempts are the minutes-driven quantity (r=0.79 vs minutes, against
    0.73 for points), so modelling attempts and converting is a shorter path to
    a points projection than modelling points directly.
    """
    out: dict = {}
    for n in windows:
        window = player_prior[-n:] if len(player_prior) >= n else []
        out[f"fga_last{n}_avg"] = (round(_mean(r.get("fg_att") for r in window) or 0.0, 3)
                                   if window else None)
        out[f"min_last{n}_avg_avail"] = (round(_mean(r.get("minutes") for r in window) or 0.0, 3)
                                         if window else None)

    recent = player_prior[-10:]
    if not recent:
        return out | {
            "fta_last10_avg": None, "usage_per_min": None,
            "ts_pct": None, "pts_per_min": None, "fga_per_min": None,
        }

    fga = _mean(r.get("fg_att") for r in recent)
    fta = _mean(r.get("ft_att") for r in recent)
    pts = _mean(r.get("points") for r in recent)
    mins = _mean(r.get("minutes") for r in recent)

    # Possession-weighted shot volume, the standard usage numerator.
    shot_possessions = None
    if fga is not None and fta is not None:
        shot_possessions = fga + FT_POSSESSION_WEIGHT * fta

    ts = None
    if pts is not None and shot_possessions:
        ts = pts / (2.0 * shot_possessions)

    out["fta_last10_avg"] = round(fta, 3) if fta is not None else None
    out["usage_per_min"]  = (round(v, 4) if (v := _safe_div(shot_possessions, mins)) is not None else None)
    out["ts_pct"]         = round(ts, 4) if ts is not None else None
    out["pts_per_min"]    = (round(v, 4) if (v := _safe_div(pts, mins)) is not None else None)
    out["fga_per_min"]    = (round(v, 4) if (v := _safe_div(fga, mins)) is not None else None)
    return out


# ── assembled feature block ───────────────────────────────────────────────────

# Everything this module contributes, in one list, so the prop feature map and
# the minutes model can both reference it without drifting.
AVAILABILITY_FEATURES = [
    "rotation_rank",
    "is_starter_tier",
    "teammates_out",
    "teammate_minutes_out",
    "teammate_fga_out",
    "teammate_points_out",
    "top_teammate_out",
]

USAGE_FEATURES = [
    "fga_last3_avg",
    "fga_last5_avg",
    "fga_last10_avg",
    "fta_last10_avg",
    "usage_per_min",
    "ts_pct",
    "pts_per_min",
    "fga_per_min",
]


def build_context_features(team_rows: list[dict], player_rows: list[dict],
                           player_id: str, game_date: str,
                           present_ids: set[str]) -> dict:
    """
    The full availability + role + usage block for one player-game.

    `present_ids` is who actually appeared in this game for this team. In
    training that comes from the box score; at serve time it comes from the
    announced lineup and the injury report, which is why the two must define
    "present" the same way — a player listed OUT pre-tip and a player with no
    box-score row are the same event.
    """
    rotation = expected_rotation(team_rows, game_date)
    prior = prior_rows(player_rows, game_date)

    feats: dict = {
        "rotation_rank":   rotation_rank(rotation, player_id),
        "is_starter_tier": is_starter_tier(rotation, player_id),
    }
    feats.update(absence_features(rotation, present_ids, player_id))
    feats.update(usage_features(prior))

    # A player outside the recent rotation has no meaningful rank; rank is used
    # as an ordinal so a sentinel beyond the roster is the honest encoding.
    if feats["rotation_rank"] is None:
        feats["rotation_rank"] = 99
    return feats
