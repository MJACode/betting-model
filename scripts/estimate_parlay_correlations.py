"""
Estimate empirical parlay leg-correlation coefficients (parlay copula engine,
Phase 2) and upsert them into the `parlay_correlations` table.

The mobile copula engine prices a same-game parlay by multiplying a per-leg
"offense polarity" (+1 roots for more offense, -1 for less) by a canonical
"+offense x +offense" correlation looked up by (sport, market-class pair, team
relationship). This script measures those canonical correlations from history:
for each leg it builds the binary outcome ORIENTED TO +offense (a hitter going
over, a starter UNDER on strikeouts, the game total over), then takes the phi
coefficient (corr of the two binary indicators) across all qualifying pairs,
aggregated per bucket. Phi underestimates the latent Gaussian correlation, so
these are conservative (we'd rather understate dependence than overstate it).

Representative lines (coarse by design — buckets lump a market class together):
  batter / off_prop  : hits >= 2            (+offense = over)
  starter / pitching : p_strikeouts <= med  (+offense = fewer Ks)
  game total         : (home+away) > median (+offense = over)

Team relationship ('same' | 'opp' | 'na') comes from player_game_log.team; game
totals are team-agnostic ('na').

Usage:
    python -m scripts.estimate_parlay_correlations --sport MLB [--min-pairs 200]
    python -m scripts.estimate_parlay_correlations --sport NBA
    python -m scripts.estimate_parlay_correlations --sport ALL

MLB has the richest structure (pitching props + run environment). NBA / WNBA
estimate the basketball buckets (two scorers same/opp team, a scorer's points vs
the game total) from their box-score logs — the basketball "+offense" indicator
is `points >= median` among players who actually played. NHL has no player-prop
models, so nothing to estimate there (it keeps the bundled priors). Idempotent
upsert; re-run after new games accumulate. Requires DATABASE_URL.
"""

from __future__ import annotations

import argparse

from data.db import get_connection

# Canonical buckets to estimate. Each entry yields one row, keyed by the
# (market_class_a <= market_class_b, relationship) the engine looks up. The SQL
# measures corr of the +offense-oriented indicators for that pair.
RHO_CLAMP = 0.6


def _median(conn, sql: str) -> float:
    row = conn.execute(sql).fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


def estimate_mlb(conn, min_pairs: int) -> list[tuple]:
    """Return rows (sport, class_a, class_b, rel, rho, n_pairs) for MLB."""
    median_total = _median(
        conn,
        "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY home_score+away_score) "
        "FROM games WHERE sport='MLB' AND home_score IS NOT NULL",
    )
    median_k = _median(
        conn,
        "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY p_strikeouts) "
        "FROM player_game_log WHERE player_type='pitcher' AND is_starter "
        "AND p_strikeouts IS NOT NULL",
    )

    # +offense-oriented binary indicators per leg type.
    ctes = f"""
    WITH bat AS (
      SELECT game_id, team, log_id, (hits>=2)::int AS ind
      FROM player_game_log WHERE player_type='batter' AND hits IS NOT NULL
    ),
    pit AS (
      SELECT game_id, team, (p_strikeouts<={median_k:.0f})::int AS lowk
      FROM player_game_log WHERE player_type='pitcher' AND is_starter
        AND p_strikeouts IS NOT NULL
    ),
    tot AS (
      SELECT game_id, ((home_score+away_score) > {median_total:.0f})::int AS over
      FROM games WHERE sport='MLB' AND home_score IS NOT NULL
    )
    """

    # (label_a, label_b, rel, sql_returning rho + n_pairs). Self-joins use <> so
    # both orderings are included → symmetric corr; n_pairs = count/2.
    queries = {
        ("off_prop", "off_prop", "same"): (
            "SELECT corr(b1.ind,b2.ind), count(*)/2 FROM bat b1 JOIN bat b2 "
            "ON b1.game_id=b2.game_id AND b1.team=b2.team AND b1.log_id<>b2.log_id"
        ),
        ("off_prop", "off_prop", "opp"): (
            "SELECT corr(b1.ind,b2.ind), count(*)/2 FROM bat b1 JOIN bat b2 "
            "ON b1.game_id=b2.game_id AND b1.team<>b2.team AND b1.log_id<>b2.log_id"
        ),
        ("game_total", "off_prop", "na"): (
            "SELECT corr(b.ind,t.over), count(*) FROM bat b JOIN tot t ON b.game_id=t.game_id"
        ),
        ("game_total", "pitching_prop", "na"): (
            "SELECT corr(p.lowk,t.over), count(*) FROM pit p JOIN tot t ON p.game_id=t.game_id"
        ),
        ("off_prop", "pitching_prop", "opp"): (
            "SELECT corr(p.lowk,b.ind), count(*) FROM pit p JOIN bat b "
            "ON p.game_id=b.game_id AND p.team<>b.team"
        ),
        ("off_prop", "pitching_prop", "same"): (
            "SELECT corr(p.lowk,b.ind), count(*) FROM pit p JOIN bat b "
            "ON p.game_id=b.game_id AND p.team=b.team"
        ),
    }

    out: list[tuple] = []
    for (ca, cb, rel), q in queries.items():
        row = conn.execute(ctes + q).fetchone()
        if not row or row[0] is None:
            continue
        rho, n_pairs = float(row[0]), int(row[1])
        if n_pairs < min_pairs:
            print(f"  skip {ca}|{cb}|{rel}: only {n_pairs} pairs (< {min_pairs})")
            continue
        rho = max(-RHO_CLAMP, min(RHO_CLAMP, rho))
        lo, hi = (ca, cb) if ca <= cb else (cb, ca)
        out.append(("MLB", lo, hi, rel, round(rho, 4), n_pairs))
        print(f"  {lo}|{hi}|{rel}: rho={rho:+.4f}  n_pairs={n_pairs}")
    return out


_BBALL_TABLE = {"NBA": "nba_player_game_log", "WNBA": "wnba_player_game_log"}


def estimate_basketball(conn, sport: str, min_pairs: int) -> list[tuple]:
    """Basketball buckets for NBA / WNBA from box-score logs.

    +offense indicator = a player scoring `points >= median` (among players who
    actually played, minutes>0) and the game total going over the median. Only
    off_prop and game_total classes exist for basketball (no pitching analog).
    """
    tbl = _BBALL_TABLE[sport]
    median_pts = _median(
        conn,
        f"SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY points) FROM {tbl} "
        "WHERE minutes>0 AND points IS NOT NULL",
    )
    median_total = _median(
        conn,
        "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY home_score+away_score) "
        f"FROM games WHERE sport='{sport}' AND home_score IS NOT NULL",
    )

    ctes = f"""
    WITH sc AS (
      SELECT game_id, team, log_id, (points>={median_pts:.0f})::int AS ind
      FROM {tbl} WHERE minutes>0 AND points IS NOT NULL
    ),
    tot AS (
      SELECT game_id, ((home_score+away_score) > {median_total:.0f})::int AS ovr
      FROM games WHERE sport='{sport}' AND home_score IS NOT NULL
    )
    """

    queries = {
        ("off_prop", "off_prop", "same"): (
            "SELECT corr(a.ind,b.ind), count(*)/2 FROM sc a JOIN sc b "
            "ON a.game_id=b.game_id AND a.team=b.team AND a.log_id<>b.log_id"
        ),
        ("off_prop", "off_prop", "opp"): (
            "SELECT corr(a.ind,b.ind), count(*)/2 FROM sc a JOIN sc b "
            "ON a.game_id=b.game_id AND a.team<>b.team AND a.log_id<>b.log_id"
        ),
        ("off_prop", "off_prop", "na"): (
            "SELECT corr(a.ind,b.ind), count(*)/2 FROM sc a JOIN sc b "
            "ON a.game_id=b.game_id AND a.log_id<>b.log_id"
        ),
        ("game_total", "off_prop", "na"): (
            "SELECT corr(s.ind,t.ovr), count(*) FROM sc s JOIN tot t ON s.game_id=t.game_id"
        ),
    }

    out: list[tuple] = []
    for (ca, cb, rel), q in queries.items():
        row = conn.execute(ctes + q).fetchone()
        if not row or row[0] is None:
            continue
        rho, n_pairs = float(row[0]), int(row[1])
        if n_pairs < min_pairs:
            print(f"  skip {ca}|{cb}|{rel}: only {n_pairs} pairs (< {min_pairs})")
            continue
        rho = max(-RHO_CLAMP, min(RHO_CLAMP, rho))
        lo, hi = (ca, cb) if ca <= cb else (cb, ca)
        out.append((sport, lo, hi, rel, round(rho, 4), n_pairs))
        print(f"  {lo}|{hi}|{rel}: rho={rho:+.4f}  n_pairs={n_pairs}")
    return out


def estimate(conn, sport: str, min_pairs: int) -> list[tuple]:
    if sport == "MLB":
        return estimate_mlb(conn, min_pairs)
    return estimate_basketball(conn, sport, min_pairs)


UPSERT = """
INSERT INTO parlay_correlations
  (sport, market_class_a, market_class_b, relationship, rho, source, n_pairs)
VALUES (%s, %s, %s, %s, %s, 'empirical', %s)
ON CONFLICT (sport, market_class_a, market_class_b, relationship)
DO UPDATE SET rho=EXCLUDED.rho, source='empirical',
              n_pairs=EXCLUDED.n_pairs, updated_at=now()::text
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Estimate parlay leg correlations.")
    ap.add_argument("--sport", default="MLB", choices=["MLB", "NBA", "WNBA", "ALL"])
    ap.add_argument("--min-pairs", type=int, default=200)
    args = ap.parse_args()

    sports = ["MLB", "NBA", "WNBA"] if args.sport == "ALL" else [args.sport]

    conn = get_connection()
    try:
        total = 0
        for sport in sports:
            print(f"Estimating {sport} parlay correlations…")
            rows = estimate(conn, sport, args.min_pairs)
            for r in rows:
                conn.execute(UPSERT, (r[0], r[1], r[2], r[3], r[4], r[5]))
            total += len(rows)
        conn.commit()
        print(f"Upserted {total} correlation rows.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
