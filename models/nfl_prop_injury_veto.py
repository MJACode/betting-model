"""Timestamped Out/Doubtful veto for NFL player props.

NOT A FEATURE. ESPN injury statuses do not enter the XGB models. They
gate whether a pick may be written: if the player is Out or Doubtful
and that status was already public when the quote was taken, we refuse
the bet. News that arrived AFTER the line is ignored — using it would
be a look-ahead leak, the same class of error as grading a prop against
an in-play price.

The comparison is status_ts <= quote_ts (ESPN's injury `date` vs the
odds row's snapshot_at). Missing either clock fails OPEN: we cannot
prove the news predates the line, so we do not veto. That is the
leak-prevention half. The ingest writes status_ts on every NFL row, so
the live path has both clocks.

Questionable / Active / unknown players are unaffected. Injured Reserve
is stored as Out by the ingestor, so it vetoes.

Applied by models.nfl_prop_market (the live card) and by
models.scorer.run_nfl_prop_scorer (tackles_assists, still live, and any
distributional sibling that would otherwise bet a scratched player).
"""
from __future__ import annotations

from datetime import datetime, timezone

from data.ingestors.nfl_props_data_ingestor import norm_player_name

# Canonical statuses that mean the player will not play. Lowercased so a
# stored "Out" and ESPN's type.description "out" compare as one.
VETO_STATUSES = frozenset({"out", "doubtful"})


def _as_dt(v) -> datetime | None:
    """Parse a timestamp to an aware datetime, or None.

    Same contract as models.nfl_prop_backtest._as_dt — kickoffs and ESPN
    dates arrive as '2026-09-12T18:14Z' vs '2026-09-12 18:14:00+00:00',
    and a string compare is a leak. Kept HERE so importing the veto
    does not pull xgboost (nfl_prop_backtest's module-level import).
    """
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    t = str(v).strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(t)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

# Canonical statuses that mean the player will not play. Lowercased so a
# stored "Out" and ESPN's type.description "out" compare as one.
VETO_STATUSES = frozenset({"out", "doubtful"})


def should_veto(status: str | None, status_ts, quote_ts) -> bool:
    """True iff this designation was Out/Doubtful before (or at) the quote.

    Equal timestamps veto: ESPN stamps second-precision (`2026-09-12T18:14Z`)
    and a quote taken at that instant already had the news in the world.
    Strictly-after does not.
    """
    if not status or str(status).strip().lower() not in VETO_STATUSES:
        return False
    st = _as_dt(status_ts)
    qt = _as_dt(quote_ts)
    if st is None or qt is None:
        return False
    return st <= qt


def player_is_vetoed(player: str, quote_ts, injury_index: dict) -> bool:
    """`injury_index` is {norm_name: [{status, status_ts}, ...]}."""
    if not player or not injury_index:
        return False
    rows = injury_index.get(norm_player_name(player)) or ()
    return any(should_veto(r.get("status"), r.get("status_ts"), quote_ts)
               for r in rows)


def apply_injury_veto(bets, quotes: dict, injury_index: dict) -> tuple[list, dict]:
    """Drop bets whose player is Out/Doubtful with status_ts <= quote snapshot.

    `quotes` is the board `load_nfl_prop_quotes` returns, keyed
    (game_id, player, market, book) with `snapshot_at` on the value.
    Bets whose quote has no timestamp, or whose player is missing from
    the index, pass through.
    """
    if not bets or not injury_index:
        return list(bets or []), {"injury_veto": 0}
    kept = []
    n = 0
    for b in bets:
        q = (quotes or {}).get((b.game_id, b.player, b.market, b.book)) or {}
        if player_is_vetoed(b.player, q.get("snapshot_at"), injury_index):
            n += 1
            continue
        kept.append(b)
    return kept, {"injury_veto": n}


def load_nfl_injury_index(conn, as_of_date: str | None = None) -> dict:
    """Latest NFL injury report on or before `as_of_date`, keyed by norm name.

    Fail-open: a missing column, a dead connection, or no rows returns {}.
    The card then bets as it did before this gate existed.
    """
    if conn is None:
        return {}
    try:
        if as_of_date:
            latest = conn.execute(
                """
                SELECT MAX(report_date) FROM injuries
                WHERE sport = 'NFL' AND report_date <= %s
                """,
                (as_of_date,),
            ).fetchone()
        else:
            latest = conn.execute(
                "SELECT MAX(report_date) FROM injuries WHERE sport = 'NFL'"
            ).fetchone()
        report_date = latest[0] if latest else None
        if not report_date:
            return {}
        rows = conn.execute(
            """
            SELECT player_name, status, status_ts
            FROM injuries
            WHERE sport = 'NFL' AND scenario = 'A' AND report_date = %s
            """,
            (report_date,),
        ).fetchall()
    except Exception:  # noqa: BLE001
        return {}

    out: dict[str, list] = {}
    for player_name, status, status_ts in rows or ():
        key = norm_player_name(player_name)
        if not key:
            continue
        out.setdefault(key, []).append(
            {"status": status, "status_ts": status_ts, "player_name": player_name}
        )
    return out
