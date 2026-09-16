"""
Market-relative gate for GAME picks (model vs posted market, not sharp-vs-soft).

WHY THIS EXISTS
---------------
`models/market_relative.py` de-vigs a sharp book and bets a soft book's
outlier. That construction is for PLAYER PROPS. MLB (and every other)
pre-game GAME model never calls it. Those models still:

  * predict a probability from starter / team / bullpen / weather diffs
  * compute edge as model_prob minus vig-INCLUDED implied of the posted price
  * fire BET when that edge and min_prob both clear (`scorer._decide`)

They do not look at opening vs current structure, do not pass when the
market has already steamed through the model's number, and do not use the
Action Network ticket/handle splits that `public_betting` already stores.
`features/market_movement.py` computes the movement features. `mlb_runline`
and `mlb_over_under` now list them on the train matrix
(`docs/mlb_market_handicap_features.md`); this module is still the DECISION
layer, not a substitute for that retrain. Pre-2026 SBR rows stay NaN
(`SPARSE_OK`). A live artifact has not been retrained.

This module is the DECISION layer, not a retrain. It answers three questions
at pick time from odds already in the pipeline:

  1. What is the no-vig market probability of our side at the CURRENT quote
     (the quote `_get_dk_odds` already bounded at first pitch)?
  2. Has that market moved through the model's number since the first
     pre-game snapshot we actually had (open), so a BET now is chasing?
  3. When ticket splits exist, is this public steam (tickets heavy on our
     side AND the market moving with them)? Reverse line movement is
     recorded, not required — we do not invent PCG percentages.

It never reads a snapshot after `as_of` and never reads one after first
pitch. The close is not an input. A missing two-way is fail-open, not a
manufactured fair.

WHAT THE CALLER OWNS: loading the current quote (already leak-bounded) and
the opening bookend, attaching public splits if the table has them, and
honouring `config.GAME_MARKET_GATE_MODE`. What this module owns: the
arithmetic and the PASS reasons.

SHADOW vs LIVE. No live-artifact-era cut cleared the section-7 standards
for these models (n too small or the grid is negative). mike, 2026-09-15:
default mode is live anyway — new BETs that PASS_STEAMED or
PASS_PUBLIC_STEAM become NONE. PASS_EDGE only fires if
`GAME_MARKET_GATE_MIN_NO_VIG_EDGE` is set (it is not). Fail-open; never
upgrades NONE. Env `GAME_MARKET_GATE_MODE=shadow` restores persist-only.

PCG / extra split sources: pass them through `PublicSplits.source`. This
file never synthesises a percentage.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from models.market_relative import devig


# Stable verdict tokens. Query `game_market_gate.verdict` with these.
CLEAR = "CLEAR"
PASS_EDGE = "PASS_EDGE"
PASS_STEAMED = "PASS_STEAMED"
PASS_PUBLIC_STEAM = "PASS_PUBLIC_STEAM"
NO_TWO_WAY = "NO_TWO_WAY"

LIVE_PASS = {PASS_EDGE, PASS_STEAMED, PASS_PUBLIC_STEAM}

# Markets whose "line" is a total; spreads use spread_home; h2h has none.
_TOTALS_MARKETS = {"totals", "totals_1st_5_innings"}
_SPREAD_MARKETS = {"spreads", "spreads_1st_5_innings"}


@dataclass(frozen=True)
class PublicSplits:
    """Ticket/handle share on OUR side, 0-100. None = unknown — do not invent."""
    ticket_pct: float | None = None
    money_pct: float | None = None
    source: str | None = None  # "action_network" | "pcg" | None


@dataclass(frozen=True)
class MarketBookend:
    """One pre-game quote, already bounded at as_of / first pitch by the loader."""
    our_price: float | None
    opp_price: float | None
    line: float | None          # total_line or home spread; None for h2h
    snapshot_at: str | None = None


@dataclass(frozen=True)
class GateVerdict:
    verdict: str
    reason: str
    market_fair_prob: float | None
    open_fair_prob: float | None
    no_vig_edge: float | None
    steamed: bool
    public_steam: bool
    rlm: bool                   # informational: line moved against ticket-heavy public
    applied: bool = False       # True only when live mode actually changed a BET


def fair_prob(our_price, opp_price) -> float | None:
    """No-vig probability of OUR side. None if the market is one-way."""
    ours, _opp = devig(our_price, opp_price)
    return ours


def bookend_from_odds(odds: dict | None, side: str, market: str) -> MarketBookend | None:
    """The scorer's current quote, mapped onto our side. None if odds is missing."""
    if not odds:
        return None
    our, opp = _side_prices(odds, side)
    return MarketBookend(
        our_price=our, opp_price=opp,
        line=_line_for_market(odds, market),
        snapshot_at=odds.get("snapshot_at"),
    )


def splits_from_pick(pick: dict) -> PublicSplits | None:
    """Action Network shares already stamped on the pick, or None if both empty."""
    t, m = pick.get("public_bet_pct"), pick.get("public_money_pct")
    if t is None and m is None:
        return None
    return PublicSplits(ticket_pct=_as_float(t), money_pct=_as_float(m),
                        source="action_network")


def evaluate(
    *,
    model_prob: float,
    side: str,
    market: str,
    current: MarketBookend | None,
    opening: MarketBookend | None = None,
    splits: PublicSplits | None = None,
    min_no_vig_edge: float | None = None,
    steam_through: bool = True,
    public_steam_pass: bool = True,
    public_heavy: float = 55.0,
    line_steam_pts: float = 0.5,
) -> GateVerdict:
    """Decide CLEAR vs PASS_* from current/open quotes. Never looks at a close.

    `min_no_vig_edge` is opt-in. None means "do not add a floor on top of
    `_decide`". Tests pass an explicit floor. Production default is None
    because no live-artifact cut cleared (see docs/mlb_game_market_gate.md).
    """
    if current is None:
        return GateVerdict(NO_TWO_WAY, "no current quote", None, None, None,
                           False, False, False)

    current_fair = fair_prob(current.our_price, current.opp_price)
    open_fair = (fair_prob(opening.our_price, opening.opp_price)
                 if opening is not None else None)
    edge = (None if current_fair is None
            else round(float(model_prob) - current_fair, 6))

    steamed = False
    if steam_through:
        steamed = _steamed_through(
            model_prob=float(model_prob), side=side, market=market,
            current=current, opening=opening,
            current_fair=current_fair, open_fair=open_fair,
            line_steam_pts=line_steam_pts,
        )

    toward_us = _moved_toward_us(
        side=side, market=market, current=current, opening=opening,
        current_fair=current_fair, open_fair=open_fair,
        line_steam_pts=line_steam_pts,
    )
    public_steam = False
    rlm = False
    if splits is not None and splits.ticket_pct is not None:
        heavy_us = splits.ticket_pct >= public_heavy
        heavy_them = splits.ticket_pct <= (100.0 - public_heavy)
        if public_steam_pass and heavy_us and toward_us:
            public_steam = True
        if heavy_them and toward_us:
            rlm = True

    if steamed:
        return GateVerdict(
            PASS_STEAMED,
            "market steamed through the model — no chase",
            current_fair, open_fair, edge, True, public_steam, rlm,
        )
    if public_steam:
        return GateVerdict(
            PASS_PUBLIC_STEAM,
            "tickets heavy on our side and the market moved with them",
            current_fair, open_fair, edge, False, True, rlm,
        )
    if current_fair is None:
        return GateVerdict(
            NO_TWO_WAY, "one-way quote — no no-vig fair",
            None, open_fair, None, False, False, rlm,
        )
    if min_no_vig_edge is not None and edge is not None and edge < min_no_vig_edge:
        return GateVerdict(
            PASS_EDGE,
            f"no-vig edge {edge:.4f} below floor {min_no_vig_edge}",
            current_fair, open_fair, edge, False, False, rlm,
        )
    return GateVerdict(
        CLEAR, "clears market-relative gate",
        current_fair, open_fair, edge, False, False, rlm,
    )


def apply_to_picks(
    picks: list[dict],
    *,
    market: str,
    current_odds: dict | None,
    opening_odds: dict | None,
    mode: str,
    min_no_vig_edge: float | None,
    steam_through: bool = True,
    public_steam_pass: bool = True,
    public_heavy: float = 55.0,
    line_steam_pts: float = 0.5,
    enabled_models: set | None = None,
) -> list[GateVerdict]:
    """Stamp each pick with `_market_gate`. Live mode may BET → NONE.

    Never upgrades a NONE/AVOID into a BET. Never overwrites an existing
    `downgrade_reason`. Mutates in place. Returns the verdicts in pick order.
    """
    out: list[GateVerdict] = []
    live = (mode or "shadow").strip().lower() == "live"
    for p in picks:
        model_id = p.get("model_id")
        if enabled_models is not None and model_id not in enabled_models:
            continue
        side = p.get("pick_side") or ""
        current = bookend_from_odds(current_odds, side, market)
        opening = bookend_from_odds(opening_odds, side, market)
        v = evaluate(
            model_prob=float(p["model_probability"]),
            side=side, market=market,
            current=current, opening=opening,
            splits=splits_from_pick(p),
            min_no_vig_edge=min_no_vig_edge,
            steam_through=steam_through,
            public_steam_pass=public_steam_pass,
            public_heavy=public_heavy,
            line_steam_pts=line_steam_pts,
        )
        applied = False
        if (live and v.verdict in LIVE_PASS and p.get("signal_type") == "BET"
                and not p.get("downgrade_reason")):
            p["signal_type"] = "NONE"
            p["kelly_fraction"] = 0.0
            p["recommended_bet"] = 0.0
            p["downgrade_reason"] = f"market: {v.reason}"
            applied = True
        v = GateVerdict(**{**v.__dict__, "applied": applied})
        p["_market_gate"] = v
        p["_market_as_of"] = current.snapshot_at if current else None
        out.append(v)
    return out


def first_eligible_snapshot(
    snaps: list[dict],
    *,
    as_of,
    commence=None,
    book: str = "draftkings",
) -> dict | None:
    """First pre-game snapshot at or before as_of (and first pitch).

    Snapshots AFTER as_of or AFTER commence are dropped. That is the leak
    guard: a close, or any later tick, cannot become the opener and cannot
    become "current" here — current is supplied separately from the scorer's
    already-bounded quote.
    """
    as_of_dt = _parse_ts(as_of)
    if as_of_dt is None:
        return None
    commence_dt = _parse_ts(commence)
    eligible = []
    for row in snaps:
        ts = _parse_ts(row.get("snap") or row.get("snapshot_at"))
        if ts is None or ts > as_of_dt:
            continue
        if commence_dt is not None and ts > commence_dt:
            continue
        eligible.append((ts, row))
    if not eligible:
        return None
    eligible.sort(key=lambda x: x[0])
    book_rows = [r for _, r in eligible if r.get("book") == book]
    return book_rows[0] if book_rows else eligible[0][1]


def opening_from_snapshots(
    snaps: list[dict],
    *,
    side: str,
    market: str,
    as_of,
    commence=None,
    book: str = "draftkings",
) -> MarketBookend | None:
    first = first_eligible_snapshot(
        snaps, as_of=as_of, commence=commence, book=book)
    return bookend_from_odds(first, side, market) if first else None


def load_opening_odds(conn, game_id: str, market: str,
                      as_of, commence=None,
                      book: str = "draftkings") -> dict | None:
    """Earliest leak-bounded pre-game snapshot for this game+market.

    Fail-open (None) if conn is missing or the query errors — a missing
    opener skips steam detection; it does not invent one from the close.
    """
    if conn is None or not game_id or as_of is None:
        return None
    try:
        rows = conn.execute("""
            SELECT snapshot_at, bookmaker, home_price, away_price,
                   over_price, under_price, total_line, spread_home
            FROM odds
            WHERE game_id = ?
              AND market = ?
              AND COALESCE(snapshot_type, '') <> 'in_play'
            ORDER BY snapshot_at ASC
        """, (game_id, market)).fetchall()
    except Exception:  # noqa: BLE001 — fail open
        return None
    snaps = []
    for r in rows:
        snaps.append({
            "snapshot_at": r[0], "book": r[1],
            "home_price": r[2], "away_price": r[3],
            "over_price": r[4], "under_price": r[5],
            "total_line": r[6], "spread_home": r[7],
        })
    return first_eligible_snapshot(
        snaps, as_of=as_of, commence=commence, book=book,
    )


def persist(conn, picks: list[dict], *, mode: str) -> None:
    """Write one row per pick into game_market_gate. Fail-open if the table
    is not there yet (migration has not run on this connection)."""
    if conn is None:
        return
    for p in picks:
        v = p.get("_market_gate")
        if v is None:
            continue
        try:
            conn.execute("""
                INSERT INTO game_market_gate (
                    game_id, model_id, pick_side, game_date, as_of,
                    verdict, mode, reason, applied,
                    model_prob, market_fair_prob, open_fair_prob, no_vig_edge,
                    public_bet_pct, public_money_pct, steamed, public_steam, rlm
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                )
                ON CONFLICT (game_id, model_id, pick_side) DO UPDATE SET
                    game_date = excluded.game_date,
                    as_of = excluded.as_of,
                    verdict = excluded.verdict,
                    mode = excluded.mode,
                    reason = excluded.reason,
                    applied = excluded.applied,
                    model_prob = excluded.model_prob,
                    market_fair_prob = excluded.market_fair_prob,
                    open_fair_prob = excluded.open_fair_prob,
                    no_vig_edge = excluded.no_vig_edge,
                    public_bet_pct = excluded.public_bet_pct,
                    public_money_pct = excluded.public_money_pct,
                    steamed = excluded.steamed,
                    public_steam = excluded.public_steam,
                    rlm = excluded.rlm
            """, (
                p.get("game_id"), p.get("model_id"), p.get("pick_side"),
                p.get("game_date"), p.get("_market_as_of") or p.get("_quote_snapshot_at"),
                v.verdict, mode, v.reason, bool(v.applied),
                p.get("model_probability"), v.market_fair_prob,
                v.open_fair_prob, v.no_vig_edge,
                p.get("public_bet_pct"), p.get("public_money_pct"),
                bool(v.steamed), bool(v.public_steam), bool(v.rlm),
            ))
        except Exception:  # noqa: BLE001 — table missing / dialect
            return


# ── internals ────────────────────────────────────────────────────────────────

def _as_float(x) -> float | None:
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v:  # NaN
        return None
    return v


def _side_prices(odds: dict, side: str) -> tuple[float | None, float | None]:
    side = (side or "").lower()
    if side in ("over", "under"):
        over, under = odds.get("over_price"), odds.get("under_price")
        return (over, under) if side == "over" else (under, over)
    home, away = odds.get("home_price"), odds.get("away_price")
    if side == "away":
        return away, home
    return home, away  # home, and any unknown side fail-open as home


def _line_for_market(odds: dict, market: str) -> float | None:
    if market in _TOTALS_MARKETS:
        return _as_float(odds.get("total_line"))
    if market in _SPREAD_MARKETS:
        return _as_float(odds.get("spread_home"))
    return None


def _parse_ts(v):
    if v is None:
        return None
    t = str(v).strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(t)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def _steamed_through(*, model_prob, side, market, current, opening,
                     current_fair, open_fair, line_steam_pts) -> bool:
    """True when the market has already moved through the model's number.

    Two forms, both requiring an opener so a single snapshot cannot look
    like a steam:

    * Same proposition (h2h, or totals/spreads whose LINE has not moved):
      current no-vig of our side is at or past model_prob, AND that fair
      rose from the open (we got more expensive).
    * Totals/spreads whose LINE moved against us by `line_steam_pts`:
      the number we would be chasing is worse than the open. The model's
      probability is already at the CURRENT line (it is a feature); this
      still refuses the chase of a worse number.
    """
    if opening is None:
        return False
    if _line_moved_against(side, market, opening.line, current.line,
                           line_steam_pts):
        return True
    if current_fair is None or open_fair is None:
        return False
    same_line = not _line_changed(opening.line, current.line, line_steam_pts)
    if not same_line and market in (_TOTALS_MARKETS | _SPREAD_MARKETS):
        return False
    moved_toward = current_fair > open_fair + 1e-12
    past_model = current_fair >= model_prob - 1e-12
    return moved_toward and past_model


def _moved_toward_us(*, side, market, current, opening,
                     current_fair, open_fair, line_steam_pts) -> bool:
    """Did the market move in our favour (price up / line against the other side)?"""
    if opening is None:
        return False
    if _line_moved_against(side, market, opening.line, current.line,
                           line_steam_pts):
        return True
    if current_fair is None or open_fair is None:
        return False
    return current_fair > open_fair + 1e-12


def _line_changed(open_line, current_line, pts) -> bool:
    if open_line is None or current_line is None:
        return False
    return abs(float(current_line) - float(open_line)) + 1e-12 >= pts


def _line_moved_against(side, market, open_line, current_line, pts) -> bool:
    if open_line is None or current_line is None:
        return False
    delta = float(current_line) - float(open_line)
    if abs(delta) + 1e-12 < pts:
        return False
    if side == "over":
        return delta <= -pts
    if side == "under":
        return delta >= pts
    if side == "home":
        return delta <= -pts     # home number got worse (more minus / less plus)
    if side == "away":
        return delta >= pts      # home number got better for home = worse for away
    return False
