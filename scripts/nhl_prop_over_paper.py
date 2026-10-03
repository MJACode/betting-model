"""Paper track for NHL prop OVERs. Not a bet.

The 2026-10-02 side sweep (docs/nhl_market_lab.md) found no over cell whose
return is clear of zero across seasons. Live cards keep publishing unders at
each model's own EV floor. An over that clears that same floor, on the same
books and the same -200 price floor, is written here and nowhere else.

This table is not `picks`. Discord, push and the app read `picks` with
`signal_type = 'BET'`. Nothing in this module inserts a pick.

    python -m scripts.nhl_prop_over_paper              # print the forward record
    python -m scripts.nhl_prop_over_paper --settle     # grade unsettled rows, then print
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

import models.nhl_prop_blocked_shots as bs
import models.nhl_props as np_


def grade_units(actual, line, american) -> tuple[str, float]:
    """Over vs the line, in units. Push is 0. A win pays the American price."""
    if float(actual) == float(line):
        return "PUSH", 0.0
    if float(actual) > float(line):
        return "WIN", round(np_.win_per_unit(float(american)), 4)
    return "LOSS", -1.0


def from_card_row(row: dict) -> dict:
    """A card dict that is an over -> the columns this table stores.

    Refuses anything else, so a published under cannot be copied in by mistake.
    """
    if row.get("pick_side") != "over":
        raise ValueError(f"paper track is overs only, got {row.get('pick_side')!r}")
    price = row.get("decision_odds", row.get("dk_odds"))
    book = row.get("decision_book") or "draftkings"
    return {
        "game_id": row["game_id"],
        "model_id": row["model_id"],
        "player_id": str(row["player_id"]),
        "game_date": row["game_date"],
        "pick_label": row["pick_label"],
        "scored_line": float(row["scored_line"]),
        "price": float(price),
        "book": book,
        "model_probability": float(row["model_probability"]),
        "ev": float(row["_ev"]),
        "pick_side": "over",
    }


def props_paper_overs(spec: np_.Spec, mus, priced, games: dict, game_date: str,
                      dispersion: float) -> list[dict]:
    """Overs the live Spec will not bet, at the same floor the unders use.

    No per-game cap: the cap is an under-board limit (shots on goal, 3). The
    sweep that rejected overs did not apply it.
    """
    from dataclasses import replace

    from scripts.nhl_props_card import pick_rows
    alt = replace(spec, sides=("over",), max_per_game=None)
    rows = pick_rows(alt, mus, priced, games, game_date, 0.0, dispersion)
    return [from_card_row(r) for r in rows]


def blocked_paper_overs(scored, games: dict, game_date: str) -> list[dict]:
    """DraftKings overs that clear the blocked-shots floor. Not picks."""
    import config
    from models.honest_ev import gate
    from scripts.nhl_prop_card import decide

    floor = config.min_odds_for(bs.MODEL_ID)
    out = []
    for r in scored.itertuples():
        d = decide(r.mu, r.line, r.over, r.under, sides=("over",))
        if d is None:
            continue
        ev = gate(bs.MODEL_ID, d["p"], d["price"])
        if not ev.clears or d["price"] < floor:
            continue
        out.append(from_card_row({
            "game_id": r.game_id, "model_id": bs.MODEL_ID, "player_id": str(r.player_id),
            "game_date": game_date,
            "pick_label": f"{r.quote_player} Over {float(r.line):g} Blocked Shots (DK)",
            "scored_line": float(r.line), "decision_odds": d["price"], "decision_book": "draftkings",
            "model_probability": round(d["p"], 4), "_ev": round(d["ev"], 4), "pick_side": "over",
        }))
    return out


_INSERT = """
    INSERT INTO nhl_prop_paper_overs
        (game_id, model_id, player_id, game_date, pick_label,
         scored_line, price, book, model_probability, ev)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (game_id, model_id, player_id) DO NOTHING
    RETURNING id
"""


def record_paper(conn, rows: list[dict]) -> int:
    """Insert-once. A second pass does not overwrite a paper row that exists."""
    written = 0
    for r in rows:
        got = conn.execute(_INSERT, (
            r["game_id"], r["model_id"], r["player_id"], r["game_date"], r["pick_label"],
            r["scored_line"], r["price"], r["book"], r["model_probability"], r["ev"],
        )).fetchone()
        if got:
            written += 1
    if written:
        conn.commit()
    return written


def settle_paper(conn, through_date: str | None = None) -> int:
    """Grade unsettled paper overs the same way a published NHL prop settles.

    Units, not dollars. A goalie who did not start, and a skater who did not
    dress, are NO_ACTION. A game with no log yet is left alone.
    """
    from tracking.paper_tracker import _PROP_STAT_MAP, _load_nhl_goalie_actuals, _load_nhl_prop_actuals

    through_date = through_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pending = conn.execute("""
        SELECT o.id, o.game_id, o.model_id, o.player_id, o.scored_line, o.price, o.game_date
        FROM nhl_prop_paper_overs o
        JOIN games g ON g.game_id = o.game_id
        WHERE o.result IS NULL AND g.home_score IS NOT NULL AND o.game_date <= %s
    """, (through_date,)).fetchall()
    if not pending:
        return 0
    by_date: dict[str, list] = {}
    for row in pending:
        by_date.setdefault(row[6], []).append(row)
    stamped = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    n = 0
    for game_date, rows in by_date.items():
        need_skater = any(_PROP_STAT_MAP.get(r[2], ("",))[0] == "nhl_skater" for r in rows)
        need_goalie = any(_PROP_STAT_MAP.get(r[2], ("",))[0] == "nhl_goalie" for r in rows)
        skater = _load_nhl_prop_actuals(conn, game_date) if need_skater else {}
        starters, goalie_games = _load_nhl_goalie_actuals(conn, game_date) if need_goalie else ({}, set())
        skater_games = {gid for (_pid, gid) in skater}
        for pid, game_id, model_id, player_id, line, price, _gd in rows:
            kind, stat = _PROP_STAT_MAP[model_id]
            if kind == "nhl_goalie":
                actual_row = starters.get((str(player_id), game_id))
                logged = game_id in goalie_games
            else:
                actual_row = skater.get((str(player_id), game_id))
                logged = game_id in skater_games
            if actual_row is None:
                if not logged:
                    continue
                result, units = "NO_ACTION", 0.0
            else:
                actual = actual_row.get(stat)
                if actual is None:
                    continue
                result, units = grade_units(actual, line, price)
            conn.execute("""
                UPDATE nhl_prop_paper_overs
                SET result = %s, profit_units = %s, settled_at = %s
                WHERE id = %s AND result IS NULL
            """, (result, units, stamped, pid))
            n += 1
    if n:
        conn.commit()
    return n


def report(conn) -> str:
    """The forward paper record, in units. Empty until the cards have run."""
    rows = conn.execute("""
        SELECT model_id,
               COUNT(*) FILTER (WHERE result IS NOT NULL AND result <> 'NO_ACTION') AS bets,
               COALESCE(SUM(profit_units) FILTER (WHERE result IN ('WIN','LOSS','PUSH')), 0) AS units
        FROM nhl_prop_paper_overs
        GROUP BY model_id
        ORDER BY model_id
    """).fetchall()
    if not rows:
        return "nhl prop paper overs: no rows yet"
    lines = ["nhl prop paper overs (units, pushes included, NO_ACTION excluded)"]
    for model_id, bets, units in rows:
        bets = int(bets or 0)
        units = float(units or 0)
        roi = f"{units / bets * 100:+.2f}%" if bets else "n/a"
        lines.append(f"  {model_id}: {bets} bets, {units:+.1f} units, {roi}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--settle", action="store_true")
    a = ap.parse_args()
    from data.db import get_connection
    conn = get_connection()
    try:
        if a.settle:
            print(f"settled {settle_paper(conn)}")
        print(report(conn))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
