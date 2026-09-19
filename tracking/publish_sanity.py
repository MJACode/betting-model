"""Pre-publish qualitative / common-sense sanity gate.

Before ANY pick is posted to Discord or push (pre-game AND live), the signal
list is filtered here. Live bypasses `publish_new_signals` and calls
`notify_discord_live` / `notify_live_signals` directly, so the gate lives on
those send paths — not only on the pre-game publisher.

WHY THIS IS NOT A SECOND BOARD. CLAUDE.md §1b: the app, Discord and push show
the same picks. An extra gate can only lose rows, and does it silently
(`opening_signals` did). This module is the same *shape* as
`tracking.pick_integrity.refuse_mismatched`: a send-time REFUSE of a row that
is unstakeable or absurd. It does not mutate `picks`, does not ledger a
refusal (retries until the row is fixed), and Discord and push apply the
identical function. The app still reads `picks`; a refused row is a bug that
stays visible in ERROR logs until someone fixes it.

COMPOSE, DO NOT DUPLICATE. Integrity is the first check. Stakeability
(paused / retired / VOID) matches `publish_filters.live_publishable_sql` and
the pre-game producers' `t.paused` / VOID clauses. The started-game /
first-pitch guard is `tracking.postable.still_pre_game`. Live dates use
`config.live_slate_dates()`. Public-split thresholds align with the MLB
handicap idea and `models.slate_concentration` / `tracking.model_quality`
(≥70% one side, n≥4). This is not the insert-time slate guard and not the
daily model-quality monitor: those report or suppress at write time; this
refuses at send time.

KILL SWITCH. `config.RUN_PUBLISH_SANITY` (env `RUN_PUBLISH_SANITY=0`)
disables the new checks only. Integrity still runs.

NO AUTO-PAUSE. NO UNIT BUMP. Optional in-process counters (`last_refusals`)
are a hook toward model_quality later; nothing is written to
`model_quality_checks` on the hot path.

LIVE HARD CAP. Deterministic, in-process, no LLM, no extra network. Missing
context for a fail-open check is skipped, not queried.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from loguru import logger

from tracking.pick_integrity import refuse_mismatched
from tracking.postable import still_pre_game

# Stable reason keys — report hook / tests. Not display copy.
REASON_INTEGRITY = "integrity"
REASON_STAKEABILITY = "stakeability"
REASON_STALE_CLOCK = "stale_clock"
REASON_ABSURD_PRICE = "absurd_price_line"
REASON_CONTRADICTION = "same_game_contradiction"
REASON_ONE_SIDED_PUBLIC = "one_sided_public"
REASON_DEAD_BET = "dead_bet"
REASON_MONEY_TICKET_SKEW = "money_ticket_skew"
REASON_PROP_LINEUP = "prop_lineup"
REASON_OUTDOOR_TOTAL = "outdoor_total_context"
REASON_TOO_GOOD_EDGE = "too_good_edge"
REASON_LOCK_REPRICE = "first_signal_lock"

# Align with models.slate_concentration / tracking.model_quality / the MLB
# handicap idea: ≥70% one side, n≥4.
PUBLIC_ONE_WAY_PCT = 70.0
PUBLIC_MIN_N = 4
# Violent money-vs-tickets disagreement, trap side = tickets without the money.
MONEY_TICKET_SKEW_PP = 25.0
TRAP_MONEY_MAX = 45.0

# Extreme juice / impossible numbers. Conservative: only the impossible.
MAX_ABS_AMERICAN = 10_000
# NFL wind card flags ~11–12 mph; 20+ is extreme conditions that card encodes.
EXTREME_WIND_MPH = 20.0
WIND_AWARE_MODELS = frozenset({"nfl_wind_totals"})
INACTIVE_PLAYER_STATUSES = frozenset({
    "out", "doubtful", "inactive", "ir", "suspended", "nfi", "pup",
})

# Spread |line| above this is not a real board number for that sport.
_SPREAD_ABS_MAX = {
    "MLB": 6.0, "NHL": 10.0, "NBA": 40.0, "WNBA": 40.0,
    "NFL": 45.0, "NCAAF": 50.0, "UFC": 20.0,
}
# Totals outside this range are not a real board number for that sport.
_TOTAL_RANGE = {
    "MLB": (1.0, 25.0), "NHL": (1.0, 20.0), "NBA": (120.0, 320.0),
    "WNBA": (80.0, 280.0), "NFL": (10.0, 90.0), "NCAAF": (10.0, 120.0),
    "UFC": (0.5, 15.0),
}
_PROP_LINE_RANGE = (0.0, 500.0)
_OUTLIER_Z = 4.0
_OUTLIER_MIN_N = 10

# Last filter_for_publish pass. In-process only; model_quality may read later.
_last_refusals: list[dict[str, Any]] = []


def last_refusals() -> list[dict[str, Any]]:
    """Copies of the refusals from the most recent `filter_for_publish` call."""
    return list(_last_refusals)


def _sanity_enabled() -> bool:
    try:
        import config
        return bool(config.RUN_PUBLISH_SANITY)
    except Exception:
        return True


def _paused_retired() -> tuple[set, frozenset]:
    try:
        import config
        return set(config.PAUSED_MODELS), frozenset(config.RETIRED_MODELS)
    except Exception:
        return set(), frozenset()


def _edge_cap(live: bool) -> float:
    try:
        import config
        cap = config.LIVE_MAX_EDGE_CAP if live else config.MAX_EDGE_CAP
        return float(cap)
    except Exception:
        return 0.20


def _live_slate() -> list[str]:
    try:
        import config
        return list(config.live_slate_dates())
    except Exception:
        return []


def _f(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _market_kind(model_id: str | None) -> str:
    """totals | spreads | h2h | prop | unknown. String first; registry fallback."""
    mid = (model_id or "").lower()
    if "_prop_" in mid or mid.endswith("_prop") or "prop_market" in mid:
        return "prop"
    if any(tok in mid for tok in ("total", "over_under", "wind_totals")):
        return "totals"
    if any(tok in mid for tok in ("spread", "runline", "puckline", "opener")):
        return "spreads"
    if any(tok in mid for tok in ("moneyline", "win_prob", "h2h", "method")):
        return "h2h"
    try:
        from tracking.paper_tracker import _market_for_pick
        market = _market_for_pick(model_id or "")
    except Exception:
        return "unknown"
    if market.startswith("total"):
        return "totals"
    if market.startswith("spread"):
        return "spreads"
    if market.startswith("h2h"):
        return "h2h"
    if "player" in market:
        return "prop"
    return "unknown"


def _is_prop(signal: dict) -> bool:
    if _market_kind(signal.get("model_id")) == "prop":
        return True
    return bool(signal.get("player_id") or signal.get("player_key")
                or signal.get("prop_market"))


def _valid_american(price: float) -> bool:
    if price == 0:
        return False
    if abs(price) > MAX_ABS_AMERICAN:
        return False
    # American odds are ≤ −100 or ≥ +100. −50 / +50 / 0 are not a book.
    return price <= -100.0 or price >= 100.0


def parse_identity(signal: dict) -> tuple[str, str, str]:
    """(game_id, model_id, player_tail) for list-level grouping.

    Prefer explicit fields. Fall back to the synthesised lock_key
    (`game:model[:player…]` or `live:game:model:side[:player…]`).
    """
    gid = str(signal.get("game_id") or "")
    mid = str(signal.get("model_id") or "")
    player = str(signal.get("player_id") or signal.get("player_key")
                 or signal.get("prop_market") or "")
    # Explicit identity wins. Do not treat a lock_key suffix as a player
    # when the producer already named the game and model — that suffix is
    # often just a uniqueness tail (`:o` / `:u`), not a player.
    if gid and mid:
        return gid, mid, player
    key = str(signal.get("lock_key") or "")
    if key.startswith("live:"):
        parts = key[5:].split(":")
        # live:game:model:side[:player…]
        if len(parts) >= 2:
            gid = gid or parts[0]
            mid = mid or parts[1]
            if not player and len(parts) > 3:
                player = ":".join(parts[3:])
    elif key:
        parts = key.split(":")
        if len(parts) >= 2:
            gid = gid or parts[0]
            mid = mid or parts[1]
            if not player and len(parts) > 2:
                player = ":".join(parts[2:])
    return gid, mid, player


def _created_ts(signal: dict):
    return signal.get("posted_at") or signal.get("created_at") or ""


# ── Per-pick checks ──────────────────────────────────────────────────────────

def _stakeability_problems(signal: dict) -> list[str]:
    mid = signal.get("model_id")
    paused, retired = _paused_retired()
    if mid in retired:
        return [f"model {mid} is retired"]
    if mid in paused:
        return [f"model {mid} is paused"]
    if signal.get("paused") is True:
        return [f"model {mid} is paused"]
    status = signal.get("condition_status")
    if status is not None and str(status) == "VOID":
        return ["the pick is VOID"]
    sig = signal.get("signal_type")
    if sig is not None and str(sig).upper() != "BET":
        return [f"signal_type is {sig}, not BET"]
    return []


def _stale_clock_problems(signal: dict, *, live: bool) -> list[str]:
    if not live:
        if "commence" not in signal:
            return []
        if still_pre_game(signal.get("commence")):
            return []
        return ["pre-game number after first pitch/kickoff"]
    game_date = signal.get("game_date")
    if not game_date:
        return []
    slate = _live_slate()
    if not slate:
        return []
    if str(game_date) in slate:
        return []
    return [f"live pick game_date {game_date} is outside the live slate {slate}"]


def _absurd_problems(signal: dict) -> list[str]:
    problems: list[str] = []
    if any(k in signal for k in ("decision_odds", "dk_odds", "best_odds")):
        raw = None
        for key in ("decision_odds", "dk_odds", "best_odds"):
            if key in signal:
                raw = signal.get(key)
                if raw is not None:
                    break
        price = _f(raw)
        if raw is None or price is None or not _valid_american(price):
            problems.append(f"odds {raw!r} are not a stakeable American price")

    kind = _market_kind(signal.get("model_id"))
    if kind in ("h2h", "unknown"):
        return problems
    if signal.get("line") is None:
        if kind in ("totals", "spreads", "prop"):
            problems.append(f"{kind} pick has a null line")
        return problems
    line = _f(signal.get("line"))
    if line is None:
        problems.append(f"line {signal.get('line')!r} is not a number")
        return problems

    sport = str(signal.get("sport") or "").upper()
    if kind == "spreads":
        cap = _SPREAD_ABS_MAX.get(sport)
        if cap is not None and abs(line) > cap:
            problems.append(f"spread {line:g} is outside a sane {sport} board")
    elif kind == "totals":
        bounds = _TOTAL_RANGE.get(sport)
        if bounds is not None and not (bounds[0] <= line <= bounds[1]):
            problems.append(f"total {line:g} is outside a sane {sport} board")
    elif kind == "prop":
        lo, hi = _PROP_LINE_RANGE
        if line < lo or line > hi:
            problems.append(f"prop line {line:g} is outside {lo:g}–{hi:g}")
    return problems


def _one_sided_public_problems(signal: dict) -> list[str]:
    """Refuse betting WITH an extreme public ticket pile. Missing data = open."""
    tickets = _f(signal.get("public_bet_pct")
                 if "public_bet_pct" in signal else None)
    if tickets is None:
        return []
    n = signal.get("public_n") or signal.get("ticket_n")
    n_val = _f(n)
    if n_val is not None and n_val < PUBLIC_MIN_N:
        return []
    # public_bet_pct is the public share ON THE PICK SIDE (scorer / opening_signals).
    if tickets >= PUBLIC_ONE_WAY_PCT:
        return [f"tickets are {tickets:g}% on this side (≥{PUBLIC_ONE_WAY_PCT:g}%, n≥{PUBLIC_MIN_N})"]
    return []


def _dead_bet_problems(signal: dict) -> list[str]:
    """Live only. Fail closed on a clear already-decided score; else open."""
    home = signal.get("home_score")
    away = signal.get("away_score")
    if home is None or away is None:
        return []
    try:
        current = int(home) + int(away)
    except (TypeError, ValueError):
        return []
    side = str(signal.get("side") or "").lower()
    kind = _market_kind(signal.get("model_id"))
    status = str(signal.get("game_status") or signal.get("abstract_game_state")
                 or "").lower()
    if status in ("final", "finalized", "game over"):
        return ["the game is already final"]
    if kind != "totals":
        return []
    line = _f(signal.get("line"))
    if line is None:
        return []
    if side == "under" and current > line:
        return [f"Under {line:g} is dead; score is already {current}"]
    return []


def _money_ticket_skew_problems(signal: dict) -> list[str]:
    """Pregame. Trap side = tickets piled here, money is not. Missing = open."""
    tickets = _f(signal.get("public_bet_pct")
                 if "public_bet_pct" in signal else None)
    money = _f(signal.get("public_money_pct")
               if "public_money_pct" in signal else None)
    if tickets is None or money is None:
        return []
    if tickets - money < MONEY_TICKET_SKEW_PP:
        return []
    if money > TRAP_MONEY_MAX:
        return []
    if tickets < PUBLIC_ONE_WAY_PCT:
        return []
    return [f"trap-side steam: tickets {tickets:g}% vs money {money:g}% on this side"]


def _prop_lineup_problems(signal: dict) -> list[str]:
    """Pregame props. Confirmed-out refuses; unknown confirmation = open."""
    if not _is_prop(signal):
        return []
    status = str(signal.get("player_status") or "").strip().lower()
    if status in INACTIVE_PLAYER_STATUSES:
        return [f"player status is {status}"]
    if "lineup_confirmed" in signal and signal.get("lineup_confirmed") is False:
        return ["player is not in a confirmed/trusted lineup"]
    return []


def _outdoor_total_problems(signal: dict) -> list[str]:
    """Pregame. Extreme wind already on the card + Over from a non-wind model."""
    if _market_kind(signal.get("model_id")) != "totals":
        return []
    if "wind_mph" not in signal:
        return []
    wind = _f(signal.get("wind_mph"))
    if wind is None:
        return []
    if signal.get("is_dome") is True:
        return []
    if wind < EXTREME_WIND_MPH:
        return []
    mid = signal.get("model_id")
    if mid in WIND_AWARE_MODELS:
        return []
    side = str(signal.get("side") or "").lower()
    if side != "over":
        return []
    return [f"Over ignores extreme outdoor wind ({wind:g} mph) already on the card"]


def _too_good_edge_problems(signal: dict, *, live: bool) -> list[str]:
    if "edge" not in signal:
        return []
    edge = _f(signal.get("edge"))
    if edge is None:
        return []
    cap = _edge_cap(live)
    if abs(edge) > cap:
        return [f"edge {edge:g} exceeds the {cap:g} cap (likely a bug)"]
    recent = signal.get("recent_edges")
    if not recent or not isinstance(recent, (list, tuple)):
        return []
    vals = [_f(x) for x in recent]
    vals = [v for v in vals if v is not None]
    if len(vals) < _OUTLIER_MIN_N:
        return []
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    std = var ** 0.5
    if std <= 0:
        return []
    if (edge - mean) / std > _OUTLIER_Z:
        return [f"edge {edge:g} is a {((edge - mean) / std):.1f}σ outlier vs recent posts"]
    return []


def pick_sanity_problems(signal: dict, *, live: bool = False) -> list[str]:
    """Every qualitative problem on this one pick. Empty = this check is OK.

    List-level checks (contradiction, first-signal lock) are not here.
    """
    problems: list[str] = []
    problems.extend(_stakeability_problems(signal))
    problems.extend(_stale_clock_problems(signal, live=live))
    problems.extend(_absurd_problems(signal))
    problems.extend(_one_sided_public_problems(signal))
    if live:
        problems.extend(_dead_bet_problems(signal))
    else:
        problems.extend(_money_ticket_skew_problems(signal))
        problems.extend(_prop_lineup_problems(signal))
        problems.extend(_outdoor_total_problems(signal))
    problems.extend(_too_good_edge_problems(signal, live=live))
    return problems


def _contradiction_keys(signals: list[dict]) -> set[int]:
    """Indexes that share a (game, model, player) lane with the opposite side."""
    groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for i, s in enumerate(signals):
        gid, mid, player = parse_identity(s)
        if not gid or not mid:
            continue
        groups[(gid, mid, player)].append(i)

    refuse: set[int] = set()
    opposites = ({"home", "away"}, {"over", "under"}, {"yes", "no"})
    for idxs in groups.values():
        sides = {str(signals[i].get("side") or "").lower() for i in idxs}
        sides.discard("")
        if any(pair <= sides for pair in opposites):
            refuse.update(idxs)
    return refuse


def _reprice_keys(signals: list[dict]) -> set[int]:
    """Later rows that re-price a locked BET in the same pass. Keep the first."""
    groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for i, s in enumerate(signals):
        gid, mid, player = parse_identity(s)
        if not gid or not mid:
            continue
        groups[(gid, mid, player)].append(i)

    refuse: set[int] = set()
    for idxs in groups.values():
        if len(idxs) < 2:
            continue
        # The standing bet is the earliest write (§1c). No timestamp → list order.
        ordered = sorted(idxs, key=lambda i: (_created_ts(signals[i]), i))
        first = ordered[0]
        first_sig = signals[first]
        first_line = first_sig.get("line")
        first_odds = None
        for key in ("decision_odds", "dk_odds", "best_odds"):
            if key in first_sig:
                first_odds = first_sig.get(key)
                break
        for i in ordered[1:]:
            other = signals[i]
            other_odds = None
            for key in ("decision_odds", "dk_odds", "best_odds"):
                if key in other:
                    other_odds = other.get(key)
                    break
            if other.get("line") != first_line or other_odds != first_odds:
                refuse.add(i)
    return refuse


def _reason_for(problem: str, *, live: bool) -> str:
    text = problem.lower()
    if "retired" in text or "paused" in text or "void" in text or "signal_type" in text:
        return REASON_STAKEABILITY
    if "first pitch" in text or "kickoff" in text or "live slate" in text:
        return REASON_STALE_CLOCK
    if "odds" in text or "spread" in text or "total" in text or "prop line" in text or "null line" in text:
        return REASON_ABSURD_PRICE
    if "tickets are" in text:
        return REASON_ONE_SIDED_PUBLIC
    if "dead" in text or "already final" in text:
        return REASON_DEAD_BET
    if "trap-side" in text:
        return REASON_MONEY_TICKET_SKEW
    if "lineup" in text or "player status" in text:
        return REASON_PROP_LINEUP
    if "wind" in text:
        return REASON_OUTDOOR_TOTAL
    if "edge" in text:
        return REASON_TOO_GOOD_EDGE
    if "both sides" in text or "over and under" in text:
        return REASON_CONTRADICTION
    if "locked bet" in text or "re-price" in text:
        return REASON_LOCK_REPRICE
    return REASON_ABSURD_PRICE if not live else REASON_DEAD_BET


def filter_for_publish(signals: list[dict], surface: str, *,
                       live: bool = False) -> list[dict]:
    """The signals that are safe to send. Refused ones are logged at ERROR.

    Integrity runs first and always. The qualitative checks run only when
    `config.RUN_PUBLISH_SANITY` is on. Nothing is ledgered here; the caller
    ledgers only what it actually delivers.
    """
    global _last_refusals
    _last_refusals = []

    after_integrity = refuse_mismatched(signals, surface)
    refused_keys = {id(s) for s in signals} - {id(s) for s in after_integrity}
    for s in signals:
        if id(s) in refused_keys:
            _last_refusals.append({
                "surface": surface, "live": live,
                "lock_key": s.get("lock_key"), "label": s.get("label"),
                "model_id": s.get("model_id"), "reason": REASON_INTEGRITY,
                "detail": "label disagrees with side/line, or side/line missing",
            })

    if not _sanity_enabled():
        return after_integrity

    contradicted = _contradiction_keys(after_integrity)
    repriced = _reprice_keys(after_integrity)

    kept: list[dict] = []
    for i, s in enumerate(after_integrity):
        problems = pick_sanity_problems(s, live=live)
        if i in contradicted:
            problems.append("same model/lane posts both sides (or Over and Under) on one game in this pass")
        if i in repriced:
            problems.append("re-prices a locked BET; sanity runs on the locked row only")
        if problems:
            logger.error(
                f"{surface}: SANITY REFUSED to publish {s.get('lock_key')} "
                f"{s.get('label')!r}: {'; '.join(problems)}"
            )
            _last_refusals.append({
                "surface": surface, "live": live,
                "lock_key": s.get("lock_key"), "label": s.get("label"),
                "model_id": s.get("model_id"),
                "reason": _reason_for(problems[0], live=live),
                "detail": "; ".join(problems),
            })
            continue
        kept.append(s)
    return kept
