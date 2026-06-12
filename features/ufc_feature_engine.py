"""
ufc_feature_engine.py — UFC fight feature builder (moneyline / round totals /
method of victory).

Mirrors the WNBA builder pattern:
  • build_ufc_game_features      — live scoring (per-fight DB lookups)
  • build_bulk_ufc_lookups       — bulk-load tables for training/backtest
  • build_ufc_features_from_bulk — fast in-memory ASOF lookups
  • compute_ufc_target           — targets for all 3 UFC models (fight results
                                   live in ufc_fight_log, not the games row, so
                                   the generic _compute_target doesn't apply)

There are no teams and no season-to-date stats: every feature is a career /
rolling stat computed ASOF the fight date from ufc_fight_log, plus static
fighter attributes (age, height, reach, stance) from fighters.

Identity: games.home_team/away_team hold fighter display names (as the books
list them). They are resolved to ufcstats fighter_ids by slug. Fighters with
fewer than MIN_UFC_FIGHTS prior UFC fights produce no feature row — debuts and
near-debuts are unmodelable (the analog of the early-season gate).

Convention reminders:
  • "home" = the fighter The Odds API placed in home_team (live) or the
    lexicographically-smaller slug (historical backfill rows).
  • Round totals settle on fractional rounds completed: Over 2.5 means the
    fight passes 2:30 of round 3 (see ufc_stats_ingestor.rounds_completed).
"""

import bisect
from datetime import datetime
from pathlib import Path
import sys

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import UFC_SYNTHETIC_TOTAL_3RD, UFC_SYNTHETIC_TOTAL_5RD
from data.db import DBConnection
from data.ingestors.ufc_stats_ingestor import rounds_completed, slugify_fighter

# Minimum prior UFC fights for a fighter to be modelable.
MIN_UFC_FIGHTS = 3

# Method classes — index = the multiclass target value.
METHOD_CLASSES = ["decision", "ko_tko", "submission"]


# ── Per-fighter career stats (pure) ───────────────────────────────────────────

def _fight_minutes(row: dict) -> float | None:
    rc = rounds_completed(row.get("end_round"), row.get("end_time_sec"),
                          row.get("scheduled_rounds"))
    return rc * 5.0 if rc is not None else None


def _age_years(dob: str | None, as_of_date: str) -> float | None:
    if not dob:
        return None
    try:
        d0 = datetime.strptime(dob, "%Y-%m-%d")
        d1 = datetime.strptime(as_of_date, "%Y-%m-%d")
        return round((d1 - d0).days / 365.25, 2)
    except ValueError:
        return None


def career_stats(prior_rows: list[dict], opp_rows_by_game: dict,
                 as_of_date: str, profile: dict | None) -> dict | None:
    """
    Career stats for one fighter ASOF as_of_date from their prior fight rows
    (ordered oldest → newest, all dated strictly before as_of_date).

    opp_rows_by_game: {game_id: opponent's row} for defensive stats
    (striking defense and takedown defense need what opponents attempted).

    Returns None when the fighter has < MIN_UFC_FIGHTS prior fights.
    """
    n = len(prior_rows)
    if n < MIN_UFC_FIGHTS:
        return None

    wins = sum(1 for r in prior_rows if r.get("result") == "win")
    losses = sum(1 for r in prior_rows if r.get("result") == "loss")
    decided = wins + losses

    # Win streak (consecutive wins from the most recent fight backwards)
    streak = 0
    for r in reversed(prior_rows):
        if r.get("result") == "win":
            streak += 1
        elif r.get("result") == "loss":
            break
        # draw/nc: neither extends nor breaks the streak

    # Method mix over all prior fights (how this fighter's fights end —
    # both directions matter for totals/method)
    methods = [r.get("method") for r in prior_rows]
    ko_rate  = sum(1 for m in methods if m == "ko_tko") / n
    sub_rate = sum(1 for m in methods if m == "submission") / n
    dec_rate = sum(1 for m in methods if m == "decision") / n
    finish_rate = ko_rate + sub_rate

    # Volume rates per minute / per 15 minutes
    total_min = 0.0
    sig_landed = sig_att = sig_absorbed = 0
    opp_sig_att = 0
    td_landed = td_att = 0
    opp_td_landed = opp_td_att = 0
    sub_attempts = 0
    rounds_sum = 0.0
    rounds_n = 0

    for r in prior_rows:
        mins = _fight_minutes(r)
        if mins:
            total_min += mins
            rc = mins / 5.0
            rounds_sum += rc
            rounds_n += 1
        sig_landed   += r.get("sig_strikes_landed") or 0
        sig_att      += r.get("sig_strikes_attempted") or 0
        sig_absorbed += r.get("sig_strikes_absorbed") or 0
        td_landed    += r.get("takedowns_landed") or 0
        td_att       += r.get("takedowns_attempted") or 0
        sub_attempts += r.get("sub_attempts") or 0

        opp = opp_rows_by_game.get(r.get("game_id"))
        if opp:
            opp_sig_att   += opp.get("sig_strikes_attempted") or 0
            opp_td_landed += opp.get("takedowns_landed") or 0
            opp_td_att    += opp.get("takedowns_attempted") or 0

    slpm = round(sig_landed / total_min, 3) if total_min > 0 else None
    sapm = round(sig_absorbed / total_min, 3) if total_min > 0 else None
    str_acc = round(sig_landed / sig_att, 4) if sig_att > 0 else None
    str_def = round(1.0 - sig_absorbed / opp_sig_att, 4) if opp_sig_att > 0 else None
    td_avg = round(td_landed / total_min * 15.0, 3) if total_min > 0 else None
    td_acc = round(td_landed / td_att, 4) if td_att > 0 else None
    td_def = round(1.0 - opp_td_landed / opp_td_att, 4) if opp_td_att > 0 else None
    sub_att_rate = round(sub_attempts / total_min * 15.0, 3) if total_min > 0 else None
    avg_fight_rounds = round(rounds_sum / rounds_n, 3) if rounds_n else None

    # Layoff
    last_date = prior_rows[-1].get("game_date")
    layoff_days = None
    try:
        layoff_days = (datetime.strptime(as_of_date, "%Y-%m-%d")
                       - datetime.strptime(last_date, "%Y-%m-%d")).days
    except (ValueError, TypeError):
        pass

    profile = profile or {}
    return {
        "career_win_pct":   round(wins / decided, 4) if decided else None,
        "win_streak":       streak,
        "experience":       n,
        "finish_rate":      round(finish_rate, 4),
        "ko_rate":          round(ko_rate, 4),
        "sub_rate":         round(sub_rate, 4),
        "dec_rate":         round(dec_rate, 4),
        "slpm":             slpm,
        "sapm":             sapm,
        "str_acc":          str_acc,
        "str_def":          str_def,
        "td_avg":           td_avg,
        "td_acc":           td_acc,
        "td_def":           td_def,
        "sub_att_rate":     sub_att_rate,
        "avg_fight_rounds": avg_fight_rounds,
        "layoff_days":      layoff_days,
        "age":              _age_years(profile.get("dob"), as_of_date),
        "height_in":        float(profile["height_in"]) if profile.get("height_in") is not None else None,
        "reach_in":         float(profile["reach_in"]) if profile.get("reach_in") is not None else None,
        "stance":           profile.get("stance"),
    }


def synthetic_round_total(scheduled_rounds: int | None) -> float:
    """Default DK round-total line for a bout length (2.5 / 4.5)."""
    if scheduled_rounds and scheduled_rounds >= 5:
        return UFC_SYNTHETIC_TOTAL_5RD
    return UFC_SYNTHETIC_TOTAL_3RD


def infer_five_rounds(total_line: float | None,
                      scheduled_rounds: int | None = None) -> int:
    """
    1 if the bout is scheduled for 5 rounds. Training knows scheduled_rounds
    from ufcstats; live scoring infers it from the DK round-total line
    (≥ 3.5 only exists for 5-round fights) and otherwise assumes 3 rounds.
    """
    if scheduled_rounds is not None:
        return int(scheduled_rounds >= 5)
    if total_line is not None and total_line >= 3.5:
        return 1
    return 0


def _assemble_ufc_features(game_id: str, game_date: str,
                           home_team: str, away_team: str, season: int,
                           home: dict | None, away: dict | None,
                           odds_row: dict | None,
                           scheduled_rounds: int | None = None) -> dict | None:
    """Build the feature dict from two resolved career-stat dicts."""
    if home is None or away is None:
        return None

    def diff(key: str):
        h, a = home.get(key), away.get(key)
        if h is None or a is None:
            return None
        return round(float(h) - float(a), 4)

    h_stance = (home.get("stance") or "").lower()
    a_stance = (away.get("stance") or "").lower()
    stance_mismatch = int(
        ("orthodox" in h_stance and "southpaw" in a_stance)
        or ("southpaw" in h_stance and "orthodox" in a_stance)
    )

    total_line = odds_row.get("total_line") if odds_row else None
    is_five = infer_five_rounds(total_line, scheduled_rounds)
    if total_line is None:
        total_line = synthetic_round_total(5 if is_five else 3)

    features = {
        "game_id":   game_id,
        "game_date": game_date,
        "sport":     "UFC",
        "season":    season,
        "home_team": home_team,
        "away_team": away_team,
        "is_early_season": 0,   # no early-season concept for UFC

        # Differentials (home − away)
        "d_career_win_pct": diff("career_win_pct"),
        "d_win_streak":     diff("win_streak"),
        "d_experience":     diff("experience"),
        "d_finish_rate":    diff("finish_rate"),
        "d_ko_rate":        diff("ko_rate"),
        "d_sub_rate":       diff("sub_rate"),
        "d_slpm":           diff("slpm"),
        "d_sapm":           diff("sapm"),
        "d_str_acc":        diff("str_acc"),
        "d_str_def":        diff("str_def"),
        "d_td_avg":         diff("td_avg"),
        "d_td_acc":         diff("td_acc"),
        "d_td_def":         diff("td_def"),
        "d_sub_att_rate":   diff("sub_att_rate"),
        "d_layoff_days":    diff("layoff_days"),
        "d_age":            diff("age"),
        "d_height_in":      diff("height_in"),
        "d_reach_in":       diff("reach_in"),
        "stance_mismatch":  stance_mismatch,

        # Absolutes (totals / method models)
        "home_finish_rate":      home.get("finish_rate"),
        "away_finish_rate":      away.get("finish_rate"),
        "home_ko_rate":          home.get("ko_rate"),
        "away_ko_rate":          away.get("ko_rate"),
        "home_sub_rate":         home.get("sub_rate"),
        "away_sub_rate":         away.get("sub_rate"),
        "home_dec_rate":         home.get("dec_rate"),
        "away_dec_rate":         away.get("dec_rate"),
        "home_avg_fight_rounds": home.get("avg_fight_rounds"),
        "away_avg_fight_rounds": away.get("avg_fight_rounds"),
        "home_slpm":             home.get("slpm"),
        "away_slpm":             away.get("slpm"),
        "home_sapm":             home.get("sapm"),
        "away_sapm":             away.get("sapm"),
        "home_td_avg":           home.get("td_avg"),
        "away_td_avg":           away.get("td_avg"),
        "home_sub_att_rate":     home.get("sub_att_rate"),
        "away_sub_att_rate":     away.get("sub_att_rate"),

        # Bout context
        "is_five_rounds": is_five,
        "total_line":     total_line,
        "spread_home":    None,   # no spreads market for UFC
    }
    return features


# ── Target computation (training/backtest) ────────────────────────────────────

def compute_ufc_target(model_id: str, market: str,
                       result_row: dict | None,
                       home_win: int | None,
                       total_line: float | None) -> int | None:
    """
    Target for a UFC training row. result_row is the fight-level outcome dict
    from build_bulk_ufc_lookups()['results'][game_id]:
        {method, end_round, end_time_sec, scheduled_rounds}
    Returns None when the target can't be computed (draw/NC, DQ, push, missing
    result) — the row is dropped from training.
    """
    if market == "h2h":
        return int(home_win == 1) if home_win is not None else None

    if result_row is None:
        return None

    if market == "totals":
        rc = rounds_completed(result_row.get("end_round"),
                              result_row.get("end_time_sec"),
                              result_row.get("scheduled_rounds"))
        if rc is None:
            return None
        line = total_line
        if line is None:
            line = synthetic_round_total(result_row.get("scheduled_rounds"))
        if rc == line:
            return None   # push
        return int(rc > line)

    if market == "method":
        method = result_row.get("method")
        if method in METHOD_CLASSES:
            return METHOD_CLASSES.index(method)
        return None   # dq / other / missing

    return None


# ── Live scoring path (per-fight DB lookups) ──────────────────────────────────

_LOG_COLS = [
    "fighter_id", "game_id", "game_date", "result", "method",
    "end_round", "end_time_sec", "scheduled_rounds",
    "sig_strikes_landed", "sig_strikes_attempted", "sig_strikes_absorbed",
    "takedowns_landed", "takedowns_attempted", "sub_attempts",
]


def _resolve_fighter_id(conn: DBConnection, display_name: str) -> str | None:
    slug = slugify_fighter(display_name)
    row = conn.execute(
        "SELECT fighter_id FROM fighters WHERE slug = ? ORDER BY updated_at DESC LIMIT 1",
        (slug,)).fetchone()
    return row[0] if row else None


def _load_prior_fights_live(conn: DBConnection, fighter_id: str,
                            as_of_date: str) -> tuple[list[dict], dict]:
    sel = ", ".join(_LOG_COLS)
    rows = conn.execute(f"""
        SELECT {sel} FROM ufc_fight_log
        WHERE fighter_id = ? AND game_date < ?
        ORDER BY game_date
    """, (fighter_id, as_of_date)).fetchall()
    prior = [dict(zip(_LOG_COLS, r)) for r in rows]

    opp_by_game: dict = {}
    game_ids = [r["game_id"] for r in prior if r.get("game_id")]
    if game_ids:
        ph = ",".join(["?"] * len(game_ids))
        opp_rows = conn.execute(f"""
            SELECT {sel} FROM ufc_fight_log
            WHERE game_id IN ({ph}) AND fighter_id != ?
        """, game_ids + [fighter_id]).fetchall()
        for r in opp_rows:
            d = dict(zip(_LOG_COLS, r))
            opp_by_game[d["game_id"]] = d
    return prior, opp_by_game


def _load_profile_live(conn: DBConnection, fighter_id: str) -> dict:
    row = conn.execute("""
        SELECT height_in, reach_in, stance, dob FROM fighters WHERE fighter_id = ?
    """, (fighter_id,)).fetchone()
    if not row:
        return {}
    return dict(zip(["height_in", "reach_in", "stance", "dob"], row))


def build_ufc_game_features(conn: DBConnection, game_id: str, game_date: str,
                            home_team: str, away_team: str, season: int,
                            odds_row: dict = None) -> dict | None:
    """
    Build the full feature row for one UFC fight (live scoring path).
    Returns None when either fighter is unknown or has < MIN_UFC_FIGHTS prior
    UFC fights — no pick is generated for that fight.
    """
    stats = {}
    for side, name in (("home", home_team), ("away", away_team)):
        fighter_id = _resolve_fighter_id(conn, name)
        if fighter_id is None:
            logger.info(f"  {game_id}: fighter '{name}' not in fighters table — skipping "
                        f"(add a UFC_NAME_ALIASES entry if this is a name mismatch)")
            return None
        prior, opp_by_game = _load_prior_fights_live(conn, fighter_id, game_date)
        s = career_stats(prior, opp_by_game, game_date, _load_profile_live(conn, fighter_id))
        if s is None:
            logger.info(f"  {game_id}: '{name}' has < {MIN_UFC_FIGHTS} prior UFC fights — skipping")
            return None
        stats[side] = s

    return _assemble_ufc_features(game_id, game_date, home_team, away_team,
                                  season, stats["home"], stats["away"], odds_row)


# ── Bulk training/backtest path ───────────────────────────────────────────────

def build_bulk_ufc_lookups(conn: DBConnection, seasons: list[int]) -> dict:
    """
    Bulk-load every UFC table for fast in-memory ASOF lookups.
    Career stats need the FULL history (a 2024 fight's features draw on fights
    from 2015), so ufc_fight_log is loaded unfiltered — ~16K rows total.
    """
    sel = ", ".join(_LOG_COLS)
    rows = conn.execute(f"""
        SELECT {sel} FROM ufc_fight_log ORDER BY game_date
    """).fetchall()

    history: dict = {}        # fighter_id → (sorted dates, [row dicts])
    rows_by_game: dict = {}   # game_id → {fighter_id: row}
    for r in rows:
        d = dict(zip(_LOG_COLS, r))
        fid = d["fighter_id"]
        if fid not in history:
            history[fid] = ([], [])
        history[fid][0].append(d["game_date"])
        history[fid][1].append(d)
        if d.get("game_id"):
            rows_by_game.setdefault(d["game_id"], {})[fid] = d

    # Fight-level results (either fighter's row carries the shared fields)
    res_rows = conn.execute("""
        SELECT DISTINCT ON (game_id)
               game_id, method, end_round, end_time_sec, scheduled_rounds
        FROM ufc_fight_log
        WHERE game_id IS NOT NULL
        ORDER BY game_id
    """).fetchall()
    results = {r[0]: dict(zip(["game_id", "method", "end_round",
                               "end_time_sec", "scheduled_rounds"], r))
               for r in res_rows}

    # Fighter profiles + slug index
    f_rows = conn.execute("""
        SELECT fighter_id, slug, height_in, reach_in, stance, dob FROM fighters
    """).fetchall()
    profiles: dict = {}
    slug_to_id: dict = {}
    for fid, slug, height_in, reach_in, stance, dob in f_rows:
        profiles[fid] = {"height_in": height_in, "reach_in": reach_in,
                         "stance": stance, "dob": dob}
        slug_to_id[slug] = fid

    # Odds (live DK rows accumulate going forward; historical UFC odds absent)
    o_cols = ['game_id', 'market', 'home_price', 'away_price',
              'total_line', 'over_price', 'under_price']
    o_rows = conn.execute("""
        SELECT o.game_id, o.market, o.home_price, o.away_price,
               o.total_line, o.over_price, o.under_price
        FROM odds o
        JOIN games g ON g.game_id = o.game_id
        WHERE g.sport = 'UFC' AND o.bookmaker = 'draftkings'
        ORDER BY o.game_id, o.market, o.snapshot_at DESC
    """).fetchall()
    odds_lookup: dict = {}
    for r in o_rows:
        d = dict(zip(o_cols, r))
        k = (d['game_id'], d['market'])
        if k not in odds_lookup:
            odds_lookup[k] = d

    logger.debug(f"UFC bulk loads: {len(rows)} fight-log rows, "
                 f"{len(results)} fights, {len(f_rows)} fighters, "
                 f"{len(o_rows)} odds rows")

    return dict(history=history, rows_by_game=rows_by_game, results=results,
                profiles=profiles, slug_to_id=slug_to_id, odds=odds_lookup)


def _blk_career_stats(bulk: dict, fighter_id: str, as_of_date: str) -> dict | None:
    if fighter_id not in bulk['history']:
        return None
    dates, frows = bulk['history'][fighter_id]
    hi = bisect.bisect_left(dates, as_of_date)
    prior = frows[:hi]
    opp_by_game = {}
    for r in prior:
        gid = r.get("game_id")
        if gid and gid in bulk['rows_by_game']:
            for fid, row in bulk['rows_by_game'][gid].items():
                if fid != fighter_id:
                    opp_by_game[gid] = row
    return career_stats(prior, opp_by_game, as_of_date,
                        bulk['profiles'].get(fighter_id))


def build_ufc_features_from_bulk(bulk: dict, game_id: str, game_date: str,
                                 home_team: str, away_team: str, season: int,
                                 odds_row: dict | None) -> dict | None:
    """Build a UFC feature row from pre-loaded bulk data (training/backtest)."""
    home_id = bulk['slug_to_id'].get(slugify_fighter(home_team))
    away_id = bulk['slug_to_id'].get(slugify_fighter(away_team))
    if home_id is None or away_id is None:
        return None

    home = _blk_career_stats(bulk, home_id, game_date)
    away = _blk_career_stats(bulk, away_id, game_date)

    result = bulk['results'].get(game_id) or {}
    return _assemble_ufc_features(game_id, game_date, home_team, away_team,
                                  season, home, away, odds_row,
                                  scheduled_rounds=result.get("scheduled_rounds"))
