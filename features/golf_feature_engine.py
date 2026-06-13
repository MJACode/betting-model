"""
Golf feature engine (PGA Tour).

The training unit is a player-tournament (one row per player per event), so golf
does NOT ride the per-game loop in feature_engine.build_training_dataset — it has
its own builder here (the prop-model precedent). Features are rolling
strokes-gained + recent form + course history computed ASOF strictly before the
tournament's start date (the look-ahead guard). A player needs ≥ MIN_GOLF_ROUNDS
prior measured rounds or the row is dropped (the early-season / MIN_UFC_FIGHTS
analog).

Public surface:
  • GOLF_PLAYER_FEATURES / GOLF_MATCHUP_FEATURES  — feature column lists
  • assemble_player_features(prior_rounds, event_dg_id, start_date)  — pure
  • compute_golf_target(model_id, finish_pos, made_cut)             — pure
  • matchup_diff_features(fa, fb) / sample_matchup_pairs(...)        — pure
  • renormalize_field_probs(probs)                                  — pure
  • build_bulk_golf_lookups(conn)                                   — DB
  • build_golf_training_dataset(model_id, seasons)                  — DB
  • build_golf_scoring_features(conn, dg_event_id, season, start_date, dg_ids) — DB (live scorer)
"""
from __future__ import annotations

import random
import sqlite3  # noqa: F401  (lazy-annotation parity on py3.12)
from datetime import datetime, timedelta

from loguru import logger

import config
from data.db import get_connection, DBConnection

MIN_GOLF_ROUNDS = config.MIN_GOLF_ROUNDS

# Finishing-position penalty assigned to a missed cut when averaging recent
# finishes (a missed cut is worse than nearly any made-cut finish).
MISSED_CUT_FINISH = 80.0


# ── Feature lists ─────────────────────────────────────────────────────────────

GOLF_PLAYER_FEATURES = [
    "sg_total_last8",
    "sg_total_last24",
    "sg_ott_last24",
    "sg_app_last24",
    "sg_arg_last24",
    "sg_putt_last24",
    "sg_total_form_delta",      # last8 − last24 (recent form vs baseline)
    "rounds_played_last_90d",
    "avg_finish_last5",
    "avg_finish_last10",
    "made_cut_rate_last10",
    "course_sg_total",          # mean SG total at this event in prior years
    "course_rounds_played",
    "days_since_last_event",
    "field_strength",           # mean sg_total_last24 across the field (injected)
]

# Per-player features that differ between the two players in a matchup. Field
# strength is identical for both (same field) so it is NOT differenced.
_MATCHUP_BASE = [f for f in GOLF_PLAYER_FEATURES if f != "field_strength"]
GOLF_MATCHUP_FEATURES = [f"d_{f}" for f in _MATCHUP_BASE]


# ── Pure helpers ──────────────────────────────────────────────────────────────

def _parse_date(d: str) -> datetime:
    return datetime.strptime(d[:10], "%Y-%m-%d")


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def _rolling_sg(prior_rounds: list[dict], n: int, key: str):
    """Mean of `key` over the player's last n measured rounds (most recent)."""
    vals = [r.get(key) for r in prior_rounds[-n:] if r.get(key) is not None]
    return sum(vals) / len(vals) if vals else None


def _event_finishes(prior_rounds: list[dict]) -> list[dict]:
    """Collapse prior rounds into one record per event, ordered oldest→newest:
    {date, dg_event_id, season, finish_pos, made_cut}."""
    by_event: dict[tuple, dict] = {}
    for r in prior_rounds:
        key = (r["season"], r["dg_event_id"])
        ev = by_event.setdefault(key, {
            "date": r["game_date"], "dg_event_id": r["dg_event_id"],
            "season": r["season"], "finish_pos": r.get("finish_pos"),
            "made_cut": r.get("made_cut"),
        })
        # carry the non-null finish/made_cut (duplicated across the player's rounds)
        if ev["finish_pos"] is None and r.get("finish_pos") is not None:
            ev["finish_pos"] = r["finish_pos"]
        if ev["made_cut"] is None and r.get("made_cut") is not None:
            ev["made_cut"] = r["made_cut"]
    return sorted(by_event.values(), key=lambda e: e["date"])


def _avg_finish(events: list[dict], k: int):
    """Average finishing position over the last k events; missed cut → penalty,
    withdrawals (made_cut None & finish None) skipped."""
    vals = []
    for ev in events[-k:]:
        if ev["finish_pos"] is not None:
            vals.append(float(ev["finish_pos"]))
        elif ev["made_cut"] == 0:
            vals.append(MISSED_CUT_FINISH)
        # else: WD / unknown — skip
    return sum(vals) / len(vals) if vals else None


def _made_cut_rate(events: list[dict], k: int):
    decided = [ev for ev in events[-k:] if ev["made_cut"] is not None]
    if not decided:
        return None
    return sum(1 for ev in decided if ev["made_cut"] == 1) / len(decided)


def assemble_player_features(prior_rounds: list[dict], event_dg_id: int,
                             start_date: str) -> dict | None:
    """
    Build one player's feature dict from their measured rounds BEFORE start_date.
    `prior_rounds` must be sorted ascending by (game_date, round_num) and already
    filtered to game_date < start_date. Returns None when the player has fewer
    than MIN_GOLF_ROUNDS prior rounds. `field_strength` is NOT set here — the
    caller injects it after building the whole field.
    """
    if len(prior_rounds) < MIN_GOLF_ROUNDS:
        return None

    start = _parse_date(start_date)
    cutoff_90 = start - timedelta(days=90)

    events = _event_finishes(prior_rounds)
    course_rounds = [r for r in prior_rounds if r["dg_event_id"] == event_dg_id]
    last_event_date = events[-1]["date"] if events else None

    sg_total_last8 = _rolling_sg(prior_rounds, 8, "sg_total")
    sg_total_last24 = _rolling_sg(prior_rounds, 24, "sg_total")
    form_delta = (sg_total_last8 - sg_total_last24
                  if sg_total_last8 is not None and sg_total_last24 is not None else None)

    return {
        "sg_total_last8":        sg_total_last8,
        "sg_total_last24":       sg_total_last24,
        "sg_ott_last24":         _rolling_sg(prior_rounds, 24, "sg_ott"),
        "sg_app_last24":         _rolling_sg(prior_rounds, 24, "sg_app"),
        "sg_arg_last24":         _rolling_sg(prior_rounds, 24, "sg_arg"),
        "sg_putt_last24":        _rolling_sg(prior_rounds, 24, "sg_putt"),
        "sg_total_form_delta":   form_delta,
        "rounds_played_last_90d": sum(1 for r in prior_rounds
                                      if _parse_date(r["game_date"]) >= cutoff_90),
        "avg_finish_last5":      _avg_finish(events, 5),
        "avg_finish_last10":     _avg_finish(events, 10),
        "made_cut_rate_last10":  _made_cut_rate(events, 10),
        "course_sg_total":       _mean([r.get("sg_total") for r in course_rounds]) if course_rounds else 0.0,
        "course_rounds_played":  len(course_rounds),
        "days_since_last_event": ((start - _parse_date(last_event_date)).days
                                  if last_event_date else None),
    }


def compute_golf_target(model_id: str, finish_pos, made_cut) -> int | None:
    """Per-player binary target. Returns None when the row should be dropped."""
    if model_id == "golf_outright":
        if finish_pos is None and made_cut is None:
            return None   # WD with unknown result
        return 1 if finish_pos == 1 else 0
    if model_id == "golf_top10":
        if finish_pos is None and made_cut is None:
            return None
        return 1 if (finish_pos is not None and finish_pos <= 10) else 0
    if model_id == "golf_top20":
        if finish_pos is None and made_cut is None:
            return None
        return 1 if (finish_pos is not None and finish_pos <= 20) else 0
    if model_id == "golf_make_cut":
        if made_cut is None:
            return None   # WD before the cut — DK voids
        return int(made_cut)
    raise ValueError(f"compute_golf_target: not a per-player golf model: {model_id}")


def matchup_diff_features(fa: dict, fb: dict) -> dict:
    """Difference of two players' per-player features (a − b)."""
    out = {}
    for base in _MATCHUP_BASE:
        va, vb = fa.get(base), fb.get(base)
        out[f"d_{base}"] = (va - vb) if (va is not None and vb is not None) else None
    return out


def compute_matchup_target(a_res: dict, b_res: dict) -> int | None:
    """
    1 if player A beats player B over the tournament, else 0. None when it's a
    tie or unsettleable (either WD).

    a_res / b_res: {finish_pos, made_cut, r12_total}.
    """
    af, bf = a_res.get("finish_pos"), b_res.get("finish_pos")
    amc, bmc = a_res.get("made_cut"), b_res.get("made_cut")
    # both have a numeric finish
    if af is not None and bf is not None:
        if af == bf:
            return None
        return 1 if af < bf else 0
    # one made the cut, the other missed
    a_made = af is not None or amc == 1
    b_made = bf is not None or bmc == 1
    if a_made and bmc == 0:
        return 1
    if b_made and amc == 0:
        return 0
    # both missed the cut → lower 36-hole total wins
    if amc == 0 and bmc == 0:
        at, bt = a_res.get("r12_total"), b_res.get("r12_total")
        if at is not None and bt is not None and at != bt:
            return 1 if at < bt else 0
        return None
    return None   # WD / ambiguous


def sample_matchup_pairs(dg_ids: list[int], n: int, seed: int) -> list[tuple[int, int]]:
    """Deterministically sample up to n unordered player pairs from a field."""
    ids = sorted(dg_ids)
    if len(ids) < 2:
        return []
    rng = random.Random(seed)
    all_pairs = [(ids[i], ids[j]) for i in range(len(ids)) for j in range(i + 1, len(ids))]
    rng.shuffle(all_pairs)
    return all_pairs[:n]


def renormalize_field_probs(probs: dict) -> dict:
    """Scale per-player win probabilities so the field sums to 1.0. Independent
    binary calibrators don't sum to 1 over a 150-man field; without this the
    edges vs DK win prices are systematically inflated."""
    total = sum(v for v in probs.values() if v is not None)
    if total <= 0:
        return dict(probs)
    return {k: (v / total if v is not None else None) for k, v in probs.items()}


# ── DB: bulk lookups ──────────────────────────────────────────────────────────

def _round_dict(row) -> dict:
    (dg_id, game_date, dg_event_id, season, round_num, score,
     sg_total, sg_ott, sg_app, sg_arg, sg_putt, finish_pos, made_cut) = row
    return {
        "dg_id": int(dg_id), "game_date": game_date, "dg_event_id": int(dg_event_id),
        "season": int(season), "round_num": int(round_num),
        "score": score, "sg_total": _f(sg_total), "sg_ott": _f(sg_ott),
        "sg_app": _f(sg_app), "sg_arg": _f(sg_arg), "sg_putt": _f(sg_putt),
        "finish_pos": int(finish_pos) if finish_pos is not None else None,
        "made_cut": int(made_cut) if made_cut is not None else None,
    }


def _f(v):
    return float(v) if v is not None else None


def build_bulk_golf_lookups(conn: DBConnection) -> dict:
    """
    Load all golf_rounds once, indexed by player (chronological), plus the
    tournament catalog and per-event player results. Loads ALL history (not just
    the requested seasons) so ASOF features for early events still see prior
    rounds.
    """
    rows = conn.execute("""
        SELECT dg_id, game_date, dg_event_id, season, round_num, score,
               sg_total, sg_ott, sg_app, sg_arg, sg_putt, finish_pos, made_cut
        FROM golf_rounds
        ORDER BY dg_id, game_date, round_num
    """).fetchall()

    rounds_by_player: dict[int, list[dict]] = {}
    # per-event results: {(dg_event_id, season): {dg_id: {finish_pos, made_cut, r12_total}}}
    event_results: dict[tuple, dict] = {}
    for row in rows:
        rd = _round_dict(row)
        rounds_by_player.setdefault(rd["dg_id"], []).append(rd)
        ekey = (rd["dg_event_id"], rd["season"])
        res = event_results.setdefault(ekey, {}).setdefault(
            rd["dg_id"], {"finish_pos": None, "made_cut": None, "r12_total": 0, "_r12n": 0})
        if rd["finish_pos"] is not None:
            res["finish_pos"] = rd["finish_pos"]
        if rd["made_cut"] is not None:
            res["made_cut"] = rd["made_cut"]
        if rd["round_num"] in (1, 2) and rd["score"] is not None:
            res["r12_total"] += rd["score"]
            res["_r12n"] += 1

    tourns = conn.execute("""
        SELECT dg_event_id, season, game_id, event_name, start_date, has_cut, tour
        FROM golf_tournaments
    """).fetchall()
    events = {}
    for (dg_event_id, season, game_id, event_name, start_date, has_cut, tour) in tourns:
        events[(int(dg_event_id), int(season))] = {
            "game_id": game_id, "event_name": event_name, "start_date": start_date,
            "has_cut": has_cut, "tour": tour,
        }

    return {"rounds_by_player": rounds_by_player,
            "event_results": event_results, "events": events}


def _prior_rounds(rounds_by_player: dict, dg_id: int, start_date: str) -> list[dict]:
    """That player's rounds strictly before start_date (already sorted)."""
    return [r for r in rounds_by_player.get(dg_id, []) if r["game_date"] < start_date]


def _field_features(rounds_by_player: dict, dg_ids, event_dg_id: int,
                    start_date: str) -> dict[int, dict]:
    """Build per-player features for a whole field, then inject field_strength
    (mean sg_total_last24 across players who have one)."""
    feats: dict[int, dict] = {}
    for dg_id in dg_ids:
        f = assemble_player_features(_prior_rounds(rounds_by_player, dg_id, start_date),
                                     event_dg_id, start_date)
        if f is not None:
            feats[dg_id] = f
    strengths = [f["sg_total_last24"] for f in feats.values()
                 if f.get("sg_total_last24") is not None]
    field_strength = sum(strengths) / len(strengths) if strengths else None
    for f in feats.values():
        f["field_strength"] = field_strength
    return feats


# ── DB: training dataset ──────────────────────────────────────────────────────

def build_golf_training_dataset(model_id: str, seasons: list[int]):
    """Per-player (or per-pair, for matchups) training matrix for the given
    seasons. Returns a DataFrame with feature cols + 'target' + metadata."""
    import pandas as pd
    from features.feature_engine import FEATURE_MAP

    is_matchup = (model_id == "golf_matchup")
    feature_cols = FEATURE_MAP[model_id]

    conn = get_connection()
    try:
        bulk = build_bulk_golf_lookups(conn)
    finally:
        conn.close()

    events = {k: v for k, v in bulk["events"].items() if k[1] in seasons}
    logger.info(f"Building {model_id} training set: {len(events)} events, seasons {seasons}")

    rows = []
    for (dg_event_id, season), ev in events.items():
        start_date = ev["start_date"]
        if not start_date:
            continue
        results = bulk["event_results"].get((dg_event_id, season), {})
        field_ids = list(results.keys())
        if not field_ids:
            continue
        feats = _field_features(bulk["rounds_by_player"], field_ids, dg_event_id, start_date)

        if not is_matchup:
            for dg_id, f in feats.items():
                res = results.get(dg_id, {})
                target = compute_golf_target(model_id, res.get("finish_pos"), res.get("made_cut"))
                if target is None:
                    continue
                rows.append({
                    "game_id": ev["game_id"], "game_date": start_date, "sport": "GOLF",
                    "season": season, "home_team": ev["event_name"], "away_team": str(dg_id),
                    "target": target, **f,
                })
        else:
            seed = dg_event_id * 100000 + season
            for a, b in sample_matchup_pairs(list(feats.keys()),
                                             config.GOLF_MATCHUP_PAIRS_PER_EVENT, seed):
                target = compute_matchup_target(results.get(a, {}), results.get(b, {}))
                if target is None:
                    continue
                diff = matchup_diff_features(feats[a], feats[b])
                rows.append({
                    "game_id": ev["game_id"], "game_date": start_date, "sport": "GOLF",
                    "season": season, "home_team": ev["event_name"], "away_team": f"{a}_{b}",
                    "target": target, **diff,
                })

    if not rows:
        logger.warning(f"No golf training rows for {model_id} seasons {seasons}")
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    meta_cols = ["game_id", "game_date", "sport", "season", "home_team", "away_team"]
    keep = meta_cols + [c for c in feature_cols if c in df.columns] + ["target"]
    df = df[[c for c in keep if c in df.columns]]
    num_cols = [c for c in df.columns if c not in meta_cols + ["target"]]
    before = len(df)
    df = df.dropna(subset=num_cols)
    if before - len(df):
        logger.info(f"  Dropped {before - len(df)} rows with null features "
                    f"({(before-len(df))/before:.1%})")
    logger.success(f"{model_id}: {len(df)} training rows, "
                   f"{df['target'].sum():.0f} positives ({df['target'].mean():.1%})")
    return df


# ── DB: live scoring features ─────────────────────────────────────────────────

def build_golf_scoring_features(conn: DBConnection, dg_event_id: int, season: int,
                                start_date: str, dg_ids: list[int]) -> dict[int, dict]:
    """
    Build per-player feature dicts (with field_strength) for the named players in
    an upcoming event, from golf_rounds history strictly before start_date.
    Players failing the MIN_GOLF_ROUNDS gate are omitted from the result.
    """
    if not dg_ids:
        return {}
    placeholders = ",".join(["%s"] * len(dg_ids))
    rows = conn.execute(f"""
        SELECT dg_id, game_date, dg_event_id, season, round_num, score,
               sg_total, sg_ott, sg_app, sg_arg, sg_putt, finish_pos, made_cut
        FROM golf_rounds
        WHERE dg_id IN ({placeholders}) AND game_date < %s
        ORDER BY dg_id, game_date, round_num
    """, list(dg_ids) + [start_date]).fetchall()

    rounds_by_player: dict[int, list[dict]] = {}
    for row in rows:
        rd = _round_dict(row)
        rounds_by_player.setdefault(rd["dg_id"], []).append(rd)

    feats = _field_features(rounds_by_player, dg_ids, dg_event_id, start_date)

    # Attach player names in one query so the scorer needn't look each up.
    if feats:
        ph = ",".join(["%s"] * len(feats))
        for dg_id, name in conn.execute(
                f"SELECT dg_id, player_name FROM golf_players WHERE dg_id IN ({ph})",
                list(feats.keys())).fetchall():
            if int(dg_id) in feats:
                feats[int(dg_id)]["player_name"] = name
    return feats
