"""
Daily model-quality monitor — betting-quality failures ops health does not see.

Motivation: `tracking/system_health.py` catches stale feeds and pipeline
failures. It does not catch a model going one-sided on a slate (all unders /
all overs / same side), public-fade concentration, CLV/ROI collapse versus a
recent baseline, or a sudden spike in BET volume / unit exposure.

Runs on the Railway worker via the same machinery as health_check:

    python -m tracking.model_quality
    python run_pipeline.py --step model-quality
    a `model_quality` row in worker_jobs (declared or enqueued)

Observability must not break the thing it observes: the pipeline step always
returns True. A dedicated CLI / job writes CRIT to the table and the logs; it
does not raise. Nothing here pauses a model or changes a unit size.

Every result row is upserted into `model_quality_checks`
(UNIQUE(run_date, check_name, model_key) — re-runs overwrite):

    SELECT run_date, check_name, model_key, sport, status, severity, detail, metrics
    FROM model_quality_checks
    WHERE run_date = '{today}' AND status NOT IN ('OK', 'SKIPPED')
    ORDER BY CASE severity WHEN 'CRIT' THEN 0 ELSE 1 END, model_key, check_name;
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import record_exclusion_sql, today_et
from data.db import get_connection
from data.ddl_guard import schema_is_current

OK, FLAGGED, SKIPPED, ERROR = "OK", "FLAGGED", "SKIPPED", "ERROR"
WARN, CRIT = "WARN", "CRIT"

# Check names — stable keys in the table, not display copy.
SLATE_CONCENTRATION = "slate_concentration"
PUBLIC_FADE_RISK = "public_fade_risk"
CLV_DEGRADATION = "clv_degradation"
ROI_COLLAPSE = "roi_collapse"
VOLUME_SPIKE = "volume_spike"

# ── Slate concentration / one-sided books ────────────────────────────────────
# A 15-game MLB card with eight unders from one model is a correlated book,
# not eight independent opinions. Fade-style models (id contains "fade") are
# *designed* to pile one side; that is the risk this check exists to name.
MIN_CONCENTRATION_BETS = 5
MIN_CONCENTRATION_GAMES = 5
CONCENTRATION_WARN_SHARE = 0.85
CONCENTRATION_CRIT_BETS = 6

# Public % on the pick's own side. Scorer writes the split for that side
# (models/scorer.py::_get_public_betting). A fade therefore lands LOW
# (under at 30% when the public is 70% over). Some fade publishers stamp
# the *opposite* ticket pile (mlb_total_public_fade's over-ticket trigger),
# which lands HIGH. Both shapes are a public-side concentration.
FADE_PUBLIC_LOW = 40.0
FADE_PUBLIC_HIGH = 70.0
MIN_FADE_BETS = 5
FADE_WARN_SHARE = 0.85
FADE_CRIT_BETS = 6

# ── Settled windows ──────────────────────────────────────────────────────────
RECENT_DAYS = 14
BASELINE_DAYS = 28          # immediately preceding the recent window
MIN_CLV_N = 15
CLV_WARN_PP = -1.0
CLV_WARN_DROP_PP = 1.5
CLV_CRIT_PP = -2.0
CLV_CRIT_BEAT = 0.40
MIN_CLV_CRIT_N = 20

MIN_ROI_N = 20
ROI_WARN = -0.15
ROI_WARN_DROP = 0.10
ROI_CRIT = -0.25
HIT_CRIT = 0.40

# ── Volume / exposure ────────────────────────────────────────────────────────
VOLUME_LOOKBACK_DAYS = 14
MIN_VOLUME_HISTORY_DAYS = 5
VOLUME_WARN_MULT = 3.0
VOLUME_CRIT_MULT = 5.0
MIN_VOLUME_TODAY = 6

CLV_METHODS = ("no_vig", "zero_vig")

_SIDE_ALIASES = {
    "o": "over", "over": "over",
    "u": "under", "under": "under",
    "h": "home", "home": "home",
    "a": "away", "away": "away",
    "yes": "yes", "y": "yes",
    "no": "no", "n": "no",
    "draw": "draw",
}


# ── Pure detectors (no database) ─────────────────────────────────────────────

def normalize_side(pick_side: str | None) -> str:
    """Lower-case side, with the short aliases the board sometimes stores."""
    raw = (pick_side or "").strip().lower()
    return _SIDE_ALIASES.get(raw, raw)


def is_fade_style_model(model_id: str) -> bool:
    """Sport-agnostic: any model whose id names a fade is a fade-style model.

    Do not list MLB ids here. A new sport's `*_public_fade` must trip the
    same check without a code change.
    """
    return "fade" in (model_id or "").lower()


def is_public_fade_pick(pick: dict) -> bool:
    """True when this BET is fading a public pile, or the model is fade-style.

    `public_bet_pct` is the public share ON THE PICK SIDE when the scorer
    wrote it. Low = we are on the minority. High = a fade publisher stamped
    the opposite pile (the trigger, not the pick side). Either way the
    book's risk is the same: correlated public fades.
    """
    if is_fade_style_model(str(pick.get("model_id") or "")):
        return True
    pct = pick.get("public_bet_pct")
    if pct is None:
        pct = pick.get("public_money_pct")
    if pct is None:
        return False
    try:
        value = float(pct)
    except (TypeError, ValueError):
        return False
    return value <= FADE_PUBLIC_LOW or value >= FADE_PUBLIC_HIGH


def units_from_recommended_bet(recommended_bet) -> float:
    """recommended_bet is dollars-per-$100-unit, same scale as profit_flat."""
    try:
        return float(recommended_bet or 0.0) / 100.0
    except (TypeError, ValueError):
        return 0.0


def units_from_profit_flat(profit_flat, price) -> float | None:
    """profit_flat fabricates -110 when the price is missing (§6). Gate it."""
    if price is None or profit_flat is None:
        return None
    try:
        return float(profit_flat) / 100.0
    except (TypeError, ValueError):
        return None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def detect_slate_concentration(
    picks: list[dict],
    *,
    min_bets: int = MIN_CONCENTRATION_BETS,
    min_games: int = MIN_CONCENTRATION_GAMES,
    warn_share: float = CONCENTRATION_WARN_SHARE,
    crit_bets: int = CONCENTRATION_CRIT_BETS,
) -> dict[str, Any] | None:
    """One-sided book on one model's open BETs. None = not enough to judge.

    CRIT when every BET is the same side and the slate is large enough for
    that to be a correlated book (the all-unders public-fade case). WARN
    when the majority share clears `warn_share` but is not unanimous, or
    when the unanimous book is just at the minimum size.
    """
    if len(picks) < min_bets:
        return None
    sides: dict[str, int] = defaultdict(int)
    games: set[str] = set()
    for pick in picks:
        side = normalize_side(pick.get("pick_side"))
        if side:
            sides[side] += 1
        gid = pick.get("game_id")
        if gid:
            games.add(str(gid))
    if not sides:
        return None
    majority_side, majority_n = max(sides.items(), key=lambda kv: (kv[1], kv[0]))
    n = len(picks)
    share = majority_n / n
    n_games = len(games)
    metrics = {
        "n_bets": n,
        "n_games": n_games,
        "majority_side": majority_side,
        "majority_n": majority_n,
        "share": round(share, 4),
        "side_counts": dict(sides),
        "fade_style": any(is_fade_style_model(str(p.get("model_id") or ""))
                          for p in picks),
    }
    unanimous = share >= 1.0 - 1e-12
    large_enough = n_games >= min_games or n >= crit_bets + 2
    if unanimous and n >= crit_bets and large_enough:
        return {
            "status": FLAGGED, "severity": CRIT,
            "detail": (
                f"{majority_n}/{n} open BETs are {majority_side} "
                f"across {n_games} game(s) — one-sided book"
            ),
            "metrics": metrics,
        }
    if share >= warn_share and n >= min_bets and (n_games >= min_games or unanimous):
        return {
            "status": FLAGGED, "severity": WARN,
            "detail": (
                f"{majority_n}/{n} open BETs are {majority_side} "
                f"({share:.0%}) across {n_games} game(s)"
            ),
            "metrics": metrics,
        }
    return {
        "status": OK, "severity": WARN,
        "detail": (
            f"{n} open BET(s), majority {majority_side} "
            f"{majority_n}/{n} ({share:.0%})"
        ),
        "metrics": metrics,
    }


def detect_public_fade_risk(
    picks: list[dict],
    *,
    min_bets: int = MIN_FADE_BETS,
    warn_share: float = FADE_WARN_SHARE,
    crit_bets: int = FADE_CRIT_BETS,
) -> dict[str, Any] | None:
    """Correlated public-side fades on one model's slate. None = no fade signal.

    A fade-style model (id contains `fade`) treats every BET as a fade.
    Other models need a public split on the pick. Combined with a
    one-sided book this is the all-unders public-OVER-fade pattern.
    """
    fade_picks = [p for p in picks if is_public_fade_pick(p)]
    if len(picks) < min_bets:
        return None
    if not fade_picks:
        return {
            "status": OK, "severity": WARN,
            "detail": f"{len(picks)} open BET(s), none look like a public fade",
            "metrics": {"n_bets": len(picks), "n_fade": 0, "fade_share": 0.0},
        }
    n = len(picks)
    n_fade = len(fade_picks)
    fade_share = n_fade / n
    sides: dict[str, int] = defaultdict(int)
    games: set[str] = set()
    for pick in fade_picks:
        side = normalize_side(pick.get("pick_side"))
        if side:
            sides[side] += 1
        if pick.get("game_id"):
            games.add(str(pick["game_id"]))
    majority_side, majority_n = (
        max(sides.items(), key=lambda kv: (kv[1], kv[0])) if sides
        else ("", 0)
    )
    side_share = (majority_n / n_fade) if n_fade else 0.0
    fade_style = any(is_fade_style_model(str(p.get("model_id") or ""))
                     for p in picks)
    metrics = {
        "n_bets": n,
        "n_fade": n_fade,
        "fade_share": round(fade_share, 4),
        "majority_side": majority_side,
        "majority_n": majority_n,
        "side_share": round(side_share, 4),
        "n_games": len(games),
        "fade_style": fade_style,
    }
    unanimous_fade = (
        fade_share >= 1.0 - 1e-12 and side_share >= 1.0 - 1e-12
    )
    if unanimous_fade and n_fade >= crit_bets and (
            len(games) >= MIN_CONCENTRATION_GAMES or fade_style):
        return {
            "status": FLAGGED, "severity": CRIT,
            "detail": (
                f"{n_fade}/{n} open BETs fade the public, all {majority_side} "
                f"across {len(games)} game(s) — correlated fade book"
            ),
            "metrics": metrics,
        }
    if fade_share >= warn_share and n_fade >= min_bets and side_share >= warn_share:
        return {
            "status": FLAGGED, "severity": WARN,
            "detail": (
                f"{n_fade}/{n} open BETs fade the public "
                f"({majority_n}/{n_fade} {majority_side})"
            ),
            "metrics": metrics,
        }
    return {
        "status": OK, "severity": WARN,
        "detail": (
            f"{n_fade}/{n} open BET(s) look like a public fade, "
            f"majority {majority_side or 'n/a'}"
        ),
        "metrics": metrics,
    }


def detect_clv_degradation(
    recent: list[dict],
    baseline: list[dict],
    *,
    min_n: int = MIN_CLV_N,
) -> dict[str, Any] | None:
    """Rolling no-vig / zero-vig CLV vs the prior window. None = thin sample.

    Only `clv_method` in (`no_vig`, `zero_vig`) and a numeric `clv_pct`.
    Beat-rate uses `clv_beat_close` when present, else `clv_pct > 0`.
    """
    def _sample(rows: list[dict]) -> tuple[int, float | None, float | None]:
        clvs: list[float] = []
        beats = 0
        for row in rows:
            method = str(row.get("clv_method") or "")
            if method not in CLV_METHODS:
                continue
            raw = row.get("clv_pct")
            if raw is None:
                continue
            try:
                clv = float(raw)
            except (TypeError, ValueError):
                continue
            clvs.append(clv)
            beat = row.get("clv_beat_close")
            if beat is None:
                beat = clv > 0
            if beat:
                beats += 1
        if not clvs:
            return 0, None, None
        return len(clvs), sum(clvs) / len(clvs), beats / len(clvs)

    n_r, mean_r, beat_r = _sample(recent)
    n_b, mean_b, beat_b = _sample(baseline)
    if n_r < min_n:
        return None
    metrics = {
        "recent_n": n_r,
        "recent_mean_clv_pp": None if mean_r is None else round(mean_r, 3),
        "recent_beat_rate": None if beat_r is None else round(beat_r, 4),
        "baseline_n": n_b,
        "baseline_mean_clv_pp": None if mean_b is None else round(mean_b, 3),
        "baseline_beat_rate": None if beat_b is None else round(beat_b, 4),
        "drop_pp": (
            None if mean_r is None or mean_b is None
            else round(mean_b - mean_r, 3)
        ),
    }
    drop = metrics["drop_pp"]
    if (mean_r is not None and mean_r <= CLV_CRIT_PP
            and beat_r is not None and beat_r < CLV_CRIT_BEAT
            and n_r >= MIN_CLV_CRIT_N):
        return {
            "status": FLAGGED, "severity": CRIT,
            "detail": (
                f"recent no-vig CLV {mean_r:+.2f}pp / beat {beat_r:.0%} "
                f"on {n_r} settled BET(s)"
            ),
            "metrics": metrics,
        }
    if (mean_r is not None and mean_r <= CLV_WARN_PP
            and drop is not None and drop >= CLV_WARN_DROP_PP):
        return {
            "status": FLAGGED, "severity": WARN,
            "detail": (
                f"recent no-vig CLV {mean_r:+.2f}pp vs baseline "
                f"{mean_b:+.2f}pp (drop {drop:.2f}pp) on {n_r} settled BET(s)"
            ),
            "metrics": metrics,
        }
    return {
        "status": OK, "severity": WARN,
        "detail": (
            f"recent no-vig CLV {mean_r:+.2f}pp / beat {beat_r:.0%} "
            f"on {n_r} settled BET(s)"
        ),
        "metrics": metrics,
    }


def detect_roi_collapse(
    recent: list[dict],
    baseline: list[dict],
    *,
    min_n: int = MIN_ROI_N,
) -> dict[str, Any] | None:
    """Recent settled ROI / hit-rate vs the prior window. None = thin sample.

    Units come from profit_flat / 100, gated on a non-NULL price (§6).
    PUSH rows count in n but not as hits.
    """
    def _sample(rows: list[dict]) -> tuple[int, int, float, float | None, float | None]:
        n = 0
        wins = 0
        units = 0.0
        priced = 0
        for row in rows:
            result = str(row.get("result") or "").upper()
            if result not in ("WIN", "LOSS", "PUSH", "W", "L"):
                continue
            n += 1
            if result in ("WIN", "W"):
                wins += 1
            price = row.get("decision_odds")
            if price is None:
                price = row.get("dk_odds")
            u = units_from_profit_flat(row.get("profit_flat"), price)
            if u is not None:
                units += u
                priced += 1
        roi = (units / priced) if priced else None
        hit = (wins / n) if n else None
        return n, priced, units, roi, hit

    n_r, priced_r, units_r, roi_r, hit_r = _sample(recent)
    n_b, priced_b, units_b, roi_b, hit_b = _sample(baseline)
    if priced_r < min_n:
        return None
    drop = None if roi_r is None or roi_b is None else (roi_b - roi_r)
    metrics = {
        "recent_n": n_r,
        "recent_priced": priced_r,
        "recent_units": round(units_r, 3),
        "recent_roi": None if roi_r is None else round(roi_r, 4),
        "recent_hit_rate": None if hit_r is None else round(hit_r, 4),
        "baseline_n": n_b,
        "baseline_priced": priced_b,
        "baseline_units": round(units_b, 3),
        "baseline_roi": None if roi_b is None else round(roi_b, 4),
        "baseline_hit_rate": None if hit_b is None else round(hit_b, 4),
        "drop": None if drop is None else round(drop, 4),
    }
    if (roi_r is not None and roi_r <= ROI_CRIT
            and hit_r is not None and hit_r < HIT_CRIT):
        return {
            "status": FLAGGED, "severity": CRIT,
            "detail": (
                f"recent ROI {roi_r:+.1%} / hit {hit_r:.0%} "
                f"on {priced_r} priced BET(s) ({units_r:+.1f}u)"
            ),
            "metrics": metrics,
        }
    if (roi_r is not None and roi_r <= ROI_WARN
            and drop is not None and drop >= ROI_WARN_DROP):
        return {
            "status": FLAGGED, "severity": WARN,
            "detail": (
                f"recent ROI {roi_r:+.1%} vs baseline {roi_b:+.1%} "
                f"on {priced_r} priced BET(s)"
            ),
            "metrics": metrics,
        }
    return {
        "status": OK, "severity": WARN,
        "detail": (
            f"recent ROI {roi_r:+.1%} / hit {hit_r:.0%} "
            f"on {priced_r} priced BET(s)"
        ),
        "metrics": metrics,
    }


def detect_volume_spike(
    today_picks: list[dict],
    daily_history: list[tuple[int, float]],
    *,
    min_today: int = MIN_VOLUME_TODAY,
    min_history_days: int = MIN_VOLUME_HISTORY_DAYS,
    warn_mult: float = VOLUME_WARN_MULT,
    crit_mult: float = VOLUME_CRIT_MULT,
) -> dict[str, Any] | None:
    """Today's BET count / units vs that model's recent daily median.

    `daily_history` is (n_bets, units) per day, excluding today. Days with
    zero BETs are omitted so an off-day does not collapse the median.
    """
    n_today = len(today_picks)
    units_today = sum(units_from_recommended_bet(p.get("recommended_bet"))
                      for p in today_picks)
    if n_today == 0:
        return None
    counts = [float(n) for n, _u in daily_history]
    unit_days = [float(u) for _n, u in daily_history]
    med_n = _median(counts)
    med_u = _median(unit_days)
    metrics = {
        "n_today": n_today,
        "units_today": round(units_today, 3),
        "median_n": None if med_n is None else round(med_n, 3),
        "median_units": None if med_u is None else round(med_u, 3),
        "history_days": len(daily_history),
        "count_mult": (
            None if not med_n else round(n_today / med_n, 3)
        ),
        "units_mult": (
            None if not med_u else round(units_today / med_u, 3)
        ),
    }
    if len(daily_history) < min_history_days:
        return {
            "status": SKIPPED, "severity": WARN,
            "detail": (
                f"{n_today} BET(s) / {units_today:.1f}u today; "
                f"only {len(daily_history)} history day(s) — no median yet"
            ),
            "metrics": metrics,
        }
    count_mult = metrics["count_mult"] or 0.0
    units_mult = metrics["units_mult"] or 0.0
    spike = max(count_mult, units_mult)
    if n_today >= min_today and spike >= crit_mult:
        return {
            "status": FLAGGED, "severity": CRIT,
            "detail": (
                f"{n_today} BET(s) / {units_today:.1f}u today vs median "
                f"{med_n:.1f} / {med_u:.1f}u ({spike:.1f}×)"
            ),
            "metrics": metrics,
        }
    if n_today >= min_today and spike >= warn_mult:
        return {
            "status": FLAGGED, "severity": WARN,
            "detail": (
                f"{n_today} BET(s) / {units_today:.1f}u today vs median "
                f"{med_n:.1f} / {med_u:.1f}u ({spike:.1f}×)"
            ),
            "metrics": metrics,
        }
    return {
        "status": OK, "severity": WARN,
        "detail": (
            f"{n_today} BET(s) / {units_today:.1f}u today vs median "
            f"{med_n:.1f} / {med_u:.1f}u"
        ),
        "metrics": metrics,
    }


# ── Persistence ──────────────────────────────────────────────────────────────

_TABLE_COLUMNS = (
    "run_date", "check_name", "model_key", "sport",
    "status", "severity", "detail", "metrics", "created_at",
)
_INDEX_NAMES = ("idx_model_quality_run_date", "model_quality_checks_key")

_DDL = """
CREATE TABLE IF NOT EXISTS model_quality_checks (
    id          INTEGER PRIMARY KEY,
    run_date    TEXT NOT NULL,
    check_name  TEXT NOT NULL,
    model_key   TEXT NOT NULL,
    sport       TEXT,
    status      TEXT NOT NULL,
    severity    TEXT NOT NULL,
    detail      TEXT,
    metrics     TEXT,
    created_at  TEXT NOT NULL,
    UNIQUE(run_date, check_name, model_key)
)
"""


def ensure_schema(conn) -> None:
    """Create the ledger if a migration has not landed yet.

    Gated on `schema_is_current` — `CREATE INDEX IF NOT EXISTS` is real DDL
    and fires PostgREST's schema-cache reload (data/ddl_guard.py).
    """
    if schema_is_current(conn, "model_quality_checks",
                         columns=_TABLE_COLUMNS, indexes=_INDEX_NAMES):
        return
    try:
        conn.execute(_DDL)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_model_quality_run_date "
            "ON model_quality_checks(run_date)"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS model_quality_checks_key "
            "ON model_quality_checks(run_date, check_name, model_key)"
        )
    except Exception:                                       # noqa: BLE001
        getattr(conn, "rollback", lambda: None)()


def _result_row(run_date: str, check_name: str, model_key: str, sport: str,
                finding: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_date": run_date,
        "check_name": check_name,
        "model_key": model_key,
        "sport": sport or "",
        "status": finding["status"],
        "severity": finding["severity"],
        "detail": finding.get("detail") or "",
        "metrics": finding.get("metrics") or {},
    }


# ── Loaders ──────────────────────────────────────────────────────────────────

_OPEN_BET_SQL = """
    SELECT p.model_id, p.sport, p.game_id, p.pick_side,
           p.public_bet_pct, p.public_money_pct, p.recommended_bet,
           p.kelly_fraction
    FROM picks p
    WHERE p.signal_type = 'BET'
      AND p.game_date = ?
      AND (p.condition_status IS NULL OR p.condition_status <> 'VOID')
"""

_SETTLED_BET_SQL = """
    SELECT p.model_id, p.sport, p.game_date, p.pick_side,
           p.result, p.profit_flat, p.dk_odds, p.decision_odds,
           p.clv_pct, p.clv_beat_close, p.clv_method
    FROM picks p
    WHERE p.signal_type = 'BET'
      AND p.game_date >= ? AND p.game_date < ?
      AND p.result IN ('WIN', 'LOSS', 'PUSH', 'W', 'L')
      AND (p.condition_status IS NULL OR p.condition_status <> 'VOID')
      {excl}
"""

_VOLUME_HISTORY_SQL = """
    SELECT p.model_id, p.game_date,
           COUNT(*) AS n,
           SUM(COALESCE(p.recommended_bet, 0)) AS stake
    FROM picks p
    WHERE p.signal_type = 'BET'
      AND p.game_date >= ? AND p.game_date < ?
      AND (p.condition_status IS NULL OR p.condition_status <> 'VOID')
    GROUP BY p.model_id, p.game_date
"""


def _row_open(row) -> dict:
    return {
        "model_id": row[0],
        "sport": row[1],
        "game_id": row[2],
        "pick_side": row[3],
        "public_bet_pct": row[4],
        "public_money_pct": row[5],
        "recommended_bet": row[6],
        "kelly_fraction": row[7],
    }


def _row_settled(row) -> dict:
    return {
        "model_id": row[0],
        "sport": row[1],
        "game_date": row[2],
        "pick_side": row[3],
        "result": row[4],
        "profit_flat": row[5],
        "dk_odds": row[6],
        "decision_odds": row[7],
        "clv_pct": row[8],
        "clv_beat_close": row[9],
        "clv_method": row[10],
    }


def _group(rows: list[dict], key: str = "model_id") -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        out[str(row.get(key) or "")].append(row)
    out.pop("", None)
    return out


def _sport_for(rows: list[dict]) -> str:
    sports = {str(r.get("sport") or "") for r in rows if r.get("sport")}
    if len(sports) == 1:
        return next(iter(sports))
    if not sports:
        return ""
    return ",".join(sorted(sports))


# ── Run ──────────────────────────────────────────────────────────────────────

def run_model_quality(run_date: str | None = None) -> dict:
    """Run every check, upsert `model_quality_checks`, log a summary.

    Returns {"ok": bool, "crit": int, "warn": int, "results": [...]}.
    ok=False only when a CRIT finding is FLAGGED or a check ERRORs at CRIT
    — the pipeline step ignores this and still returns True.
    """
    if run_date is None:
        run_date = today_et()
    d = datetime.strptime(run_date, "%Y-%m-%d")
    recent_start = (d - timedelta(days=RECENT_DAYS)).strftime("%Y-%m-%d")
    baseline_start = (d - timedelta(days=RECENT_DAYS + BASELINE_DAYS)).strftime(
        "%Y-%m-%d")
    volume_start = (d - timedelta(days=VOLUME_LOOKBACK_DAYS)).strftime(
        "%Y-%m-%d")

    results: list[dict] = []
    conn = get_connection()
    try:
        ensure_schema(conn)
        try:
            open_rows = [_row_open(r) for r in conn.execute(
                _OPEN_BET_SQL, (run_date,)).fetchall()]
        except Exception as exc:                            # noqa: BLE001
            getattr(conn, "rollback", lambda: None)()
            logger.error(f"model_quality: open-BET query failed: {exc}")
            open_rows = []
            results.append(_result_row(
                run_date, SLATE_CONCENTRATION, "*", "",
                {"status": ERROR, "severity": WARN,
                 "detail": f"open-BET query failed: {exc}", "metrics": {}}))

        open_by_model = _group(open_rows)

        excl = record_exclusion_sql("p")
        try:
            settled_sql = _SETTLED_BET_SQL.format(excl=excl)
            recent_rows = [_row_settled(r) for r in conn.execute(
                settled_sql, (recent_start, run_date)).fetchall()]
            baseline_rows = [_row_settled(r) for r in conn.execute(
                settled_sql, (baseline_start, recent_start)).fetchall()]
        except Exception as exc:                            # noqa: BLE001
            getattr(conn, "rollback", lambda: None)()
            logger.error(f"model_quality: settled query failed: {exc}")
            recent_rows, baseline_rows = [], []
            results.append(_result_row(
                run_date, CLV_DEGRADATION, "*", "",
                {"status": ERROR, "severity": WARN,
                 "detail": f"settled query failed: {exc}", "metrics": {}}))

        recent_by_model = _group(recent_rows)
        baseline_by_model = _group(baseline_rows)

        try:
            hist_rows = conn.execute(
                _VOLUME_HISTORY_SQL, (volume_start, run_date)).fetchall()
        except Exception as exc:                            # noqa: BLE001
            getattr(conn, "rollback", lambda: None)()
            logger.error(f"model_quality: volume query failed: {exc}")
            hist_rows = []

        hist_by_model: dict[str, list[tuple[int, float]]] = defaultdict(list)
        for mid, _gd, n, stake in hist_rows:
            hist_by_model[str(mid)].append(
                (int(n or 0), float(stake or 0.0) / 100.0))

        model_keys = sorted(
            set(open_by_model)
            | set(recent_by_model)
            | set(baseline_by_model)
            | set(hist_by_model)
        )

        for mid in model_keys:
            today = open_by_model.get(mid, [])
            sport = _sport_for(today or recent_by_model.get(mid, [])
                               or baseline_by_model.get(mid, []))

            if today:
                conc = detect_slate_concentration(today)
                if conc is None:
                    conc = {
                        "status": SKIPPED, "severity": WARN,
                        "detail": (
                            f"{len(today)} open BET(s) — below the "
                            f"{MIN_CONCENTRATION_BETS}-bet concentration floor"
                        ),
                        "metrics": {"n_bets": len(today)},
                    }
                results.append(_result_row(
                    run_date, SLATE_CONCENTRATION, mid, sport, conc))

                fade = detect_public_fade_risk(today)
                if fade is None:
                    fade = {
                        "status": SKIPPED, "severity": WARN,
                        "detail": (
                            f"{len(today)} open BET(s) — below the "
                            f"{MIN_FADE_BETS}-bet fade floor"
                        ),
                        "metrics": {"n_bets": len(today)},
                    }
                results.append(_result_row(
                    run_date, PUBLIC_FADE_RISK, mid, sport, fade))

                vol = detect_volume_spike(today, hist_by_model.get(mid, []))
                if vol is not None:
                    results.append(_result_row(
                        run_date, VOLUME_SPIKE, mid, sport, vol))

            recent = recent_by_model.get(mid, [])
            baseline = baseline_by_model.get(mid, [])
            if recent or baseline:
                clv = detect_clv_degradation(recent, baseline)
                if clv is None:
                    clv = {
                        "status": SKIPPED, "severity": WARN,
                        "detail": (
                            f"{len(recent)} recent settled BET(s) — "
                            f"need {MIN_CLV_N} with no-vig/zero-vig CLV"
                        ),
                        "metrics": {"recent_n": len(recent)},
                    }
                results.append(_result_row(
                    run_date, CLV_DEGRADATION, mid, sport, clv))

                roi = detect_roi_collapse(recent, baseline)
                if roi is None:
                    roi = {
                        "status": SKIPPED, "severity": WARN,
                        "detail": (
                            f"{len(recent)} recent settled BET(s) — "
                            f"need {MIN_ROI_N} priced"
                        ),
                        "metrics": {"recent_n": len(recent)},
                    }
                results.append(_result_row(
                    run_date, ROI_COLLAPSE, mid, sport, roi))

        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for res in results:
            try:
                conn.execute("""
                    INSERT INTO model_quality_checks
                        (run_date, check_name, model_key, sport,
                         status, severity, detail, metrics, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (run_date, check_name, model_key) DO UPDATE SET
                        sport = EXCLUDED.sport,
                        status = EXCLUDED.status,
                        severity = EXCLUDED.severity,
                        detail = EXCLUDED.detail,
                        metrics = EXCLUDED.metrics,
                        created_at = EXCLUDED.created_at
                """, (res["run_date"], res["check_name"], res["model_key"],
                      res["sport"], res["status"], res["severity"],
                      res["detail"], json.dumps(res["metrics"], default=str),
                      created_at))
            except Exception as exc:                        # noqa: BLE001
                getattr(conn, "rollback", lambda: None)()
                logger.error(
                    f"model_quality: persist failed for "
                    f"{res['check_name']}/{res['model_key']}: {exc}")
        try:
            conn.commit()
        except Exception as exc:                            # noqa: BLE001
            logger.error(f"model_quality: commit failed: {exc}")
    finally:
        conn.close()

    bad = [x for x in results if x["status"] in (FLAGGED, ERROR)]
    crit = [x for x in bad if x["severity"] == CRIT]
    warn = [x for x in bad if x["severity"] != CRIT]
    for res in results:
        line = (f"[{res['severity']}] {res['check_name']} "
                f"{res['model_key']}: {res['status']} — {res['detail']}")
        if res["status"] in (FLAGGED, ERROR):
            (logger.error if res["severity"] == CRIT else logger.warning)(line)
        else:
            logger.info(line)
    if crit:
        logger.error(
            f"MODEL QUALITY: {len(crit)} CRITICAL finding(s), "
            f"{len(warn)} warning(s) — report only, no pause")
    elif warn:
        logger.warning(f"MODEL QUALITY: OK with {len(warn)} warning(s)")
    else:
        logger.success(
            f"MODEL QUALITY: no flagged findings ({len(results)} row(s))")

    return {
        "ok": not crit,
        "crit": len(crit),
        "warn": len(warn),
        "results": results,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Run the daily model-quality monitor")
    parser.add_argument("--date", help="Run date YYYY-MM-DD (default: today ET)")
    args = parser.parse_args()
    out = run_model_quality(args.date)
    # Dedicated CLI: CRIT is visible as a non-zero exit. The pipeline step
    # ignores this. The job runner never raises on ok=False.
    sys.exit(0 if out["ok"] else 1)
