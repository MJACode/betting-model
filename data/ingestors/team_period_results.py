"""Team betting results by period: one row per team, game and period, for the Stats tab.

WHY. Matt, 2026-11-13: the Betting tab should show record AND percent on every
stat, add halves and quarters, and filter by full game / half / quarter, by
full season / last 10 / 5 / 3, and by home / away (the EVAnalytics layout).
The season-only `team_stats_board_compute` cannot window or re-cut by period,
and it returns no win-loss counts for its home / away / favourite / underdog /
rest splits. These rows let the app count every one of those from one read.

WHAT IT WRITES. team_period_results (data/migrations/add_team_period_results_2026_11_13.sql),
rebuilt from what Supabase already holds:

  score    FG = games.home_score / away_score (overtime included, as a full-game
           bet settles); Q1..Q4 = nba_period_scores periods 1..4 (Q4 is the
           regulation fourth quarter only, overtime NOT added); H1 = periods 1 + 2,
           only when both are stored.
  line     per period market (FG spreads/totals, H1 spreads_h1/totals_h1,
           Qn spreads_qn/totals_qn): DraftKings' newest pre-tip row
           (snapshot_at <= commence_time, never in_play). With no DraftKings row,
           the median of every other fetched book's newest pre-tip number,
           rounded to the nearest half point. spread_source / total_source say
           which. A game with neither has no line and no ATS / O-U result; it
           still counts in the score.
  result   ats W/L/P on (pts_for - pts_against) + spread; ou O/U/P on the
           period's points against total_line.
  rest     days since the team's previous game of the same season, from every
           `games` row (played or not), and the opponent's.

DraftKings first, so the full-game number is the same one the Teams board's
season ATS% already grades against (team_stats_board_compute reads DraftKings
alone for NBA). Regular season only (games holds no postseason rows). A row is
rewritten only when a value changed.

    python -m data.ingestors.team_period_results --sport NBA --seasons 2026 2027
"""
from __future__ import annotations

import argparse

from loguru import logger

import config
from data.db import get_connection

TABLE = "team_period_results"
PERIODS = ("FG", "H1", "Q1", "Q2", "Q3", "Q4")
# The Odds API market for each period: (spread market, total market).
PERIOD_MARKETS: dict[str, tuple[str, str]] = {
    "FG": ("spreads", "totals"),
    "H1": ("spreads_h1", "totals_h1"),
    "Q1": ("spreads_q1", "totals_q1"),
    "Q2": ("spreads_q2", "totals_q2"),
    "Q3": ("spreads_q3", "totals_q3"),
    "Q4": ("spreads_q4", "totals_q4"),
}
# Sports this writer knows how to score by period. NCAAB (halves) is next
# (Matt, 2026-11-13: "Start with NBA then move to college basketball").
SPORTS = ("NBA",)
PRIMARY_BOOK = "draftkings"


def line_books() -> list[str]:
    """Every fetched book plus Pinnacle: the consensus pool. Lines only, never a pick's book."""
    return list(dict.fromkeys([*config.LINE_SHOP_BOOKMAKERS, "pinnacle"]))


# %(period_markets)s is a VALUES list built from PERIOD_MARKETS, not user input.
_SQL = """
WITH g AS (
  SELECT game_id, season, game_date, commence_time, home_team, away_team,
         home_score, away_score
    FROM games
   WHERE sport = %(sport)s AND season = ANY(%(seasons)s)
),
team_games AS (
  SELECT game_id, season, game_date, home_team AS team FROM g
  UNION ALL
  SELECT game_id, season, game_date, away_team FROM g
),
rest AS (
  SELECT game_id, team,
         (game_date::date - lag(game_date::date) OVER (
             PARTITION BY team, season ORDER BY game_date, game_id))::int AS rest_days
    FROM team_games
),
played AS (
  SELECT * FROM g WHERE home_score IS NOT NULL AND away_score IS NOT NULL
),
sc AS (
  SELECT p.game_id, 'FG'::text AS period, p.home_score AS hp, p.away_score AS ap
    FROM played p
  UNION ALL
  SELECT ps.game_id, 'Q' || ps.period, ps.home_points, ps.away_points
    FROM nba_period_scores ps
    JOIN played p USING (game_id)
   WHERE %(sport)s = 'NBA' AND ps.period BETWEEN 1 AND 4
     AND ps.home_points IS NOT NULL AND ps.away_points IS NOT NULL
  UNION ALL
  SELECT ps.game_id, 'H1', sum(ps.home_points)::int, sum(ps.away_points)::int
    FROM nba_period_scores ps
    JOIN played p USING (game_id)
   WHERE %(sport)s = 'NBA' AND ps.period IN (1, 2)
     AND ps.home_points IS NOT NULL AND ps.away_points IS NOT NULL
   GROUP BY ps.game_id
  HAVING count(DISTINCT ps.period) = 2
),
mk(period, kind, market) AS (VALUES {period_markets}),
book_lines AS (
  SELECT sc.game_id, sc.period, mk.kind, b.book, o.val
    FROM sc
    JOIN played p USING (game_id)
    JOIN mk ON mk.period = sc.period
   CROSS JOIN unnest(%(books)s::text[]) AS b(book)
    JOIN LATERAL (
      SELECT CASE WHEN mk.kind = 'spread' THEN oo.spread_home ELSE oo.total_line END AS val
        FROM odds oo
       WHERE oo.game_id = sc.game_id
         AND oo.market = mk.market
         AND oo.bookmaker = b.book
         AND oo.snapshot_at < to_char(
               (p.commence_time::timestamptz + interval '1 second') AT TIME ZONE 'UTC',
               'YYYY-MM-DD"T"HH24:MI:SS"Z"')
         AND oo.snapshot_type IS DISTINCT FROM 'in_play'
         AND oo.snapshot_at::timestamptz <= p.commence_time::timestamptz
         AND (CASE WHEN mk.kind = 'spread' THEN oo.spread_home ELSE oo.total_line END) IS NOT NULL
       ORDER BY oo.snapshot_at DESC
       LIMIT 1
    ) o ON true
   WHERE p.commence_time IS NOT NULL
),
per_kind AS (
  SELECT game_id, period, kind,
         max(val) FILTER (WHERE book = %(primary)s) AS dk,
         (round(2 * (percentile_cont(0.5) WITHIN GROUP (ORDER BY val)
                     FILTER (WHERE book <> %(primary)s))::numeric) / 2.0) AS cons
    FROM book_lines
   GROUP BY game_id, period, kind
),
lines AS (
  SELECT game_id, period,
         max(COALESCE(dk, cons)) FILTER (WHERE kind = 'spread') AS spread_home,
         max(CASE WHEN dk IS NOT NULL THEN 'draftkings'
                  WHEN cons IS NOT NULL THEN 'consensus' END) FILTER (WHERE kind = 'spread') AS s_src,
         max(COALESCE(dk, cons)) FILTER (WHERE kind = 'total') AS total_line,
         max(CASE WHEN dk IS NOT NULL THEN 'draftkings'
                  WHEN cons IS NOT NULL THEN 'consensus' END) FILTER (WHERE kind = 'total') AS t_src
    FROM per_kind
   GROUP BY game_id, period
),
j AS (
  SELECT p.season, sc.game_id, sc.period, p.game_date, p.home_team, p.away_team, sc.hp, sc.ap,
         l.spread_home, l.s_src, l.total_line, l.t_src,
         rh.rest_days AS h_rest, ra.rest_days AS a_rest
    FROM sc
    JOIN played p USING (game_id)
    LEFT JOIN lines l ON l.game_id = sc.game_id AND l.period = sc.period
    LEFT JOIN rest rh ON rh.game_id = sc.game_id AND rh.team = p.home_team
    LEFT JOIN rest ra ON ra.game_id = sc.game_id AND ra.team = p.away_team
),
sided AS (
  SELECT season, game_id, period, game_date, home_team AS team, away_team AS opponent,
         TRUE AS is_home, hp AS pts_for, ap AS pts_against,
         spread_home AS spread, s_src, total_line, t_src, h_rest AS rest_days, a_rest AS opp_rest_days
    FROM j
  UNION ALL
  SELECT season, game_id, period, game_date, away_team, home_team,
         FALSE, ap, hp,
         -spread_home, s_src, total_line, t_src, a_rest, h_rest
    FROM j
),
final AS (
  SELECT s.*,
         CASE WHEN s.spread IS NULL THEN NULL
              WHEN (s.pts_for - s.pts_against) + s.spread > 0 THEN 'W'
              WHEN (s.pts_for - s.pts_against) + s.spread < 0 THEN 'L'
              ELSE 'P' END AS ats,
         CASE WHEN s.total_line IS NULL THEN NULL
              WHEN (s.pts_for + s.pts_against) > s.total_line THEN 'O'
              WHEN (s.pts_for + s.pts_against) < s.total_line THEN 'U'
              ELSE 'P' END AS ou
    FROM sided s
)
"""

_UPSERT = """
INSERT INTO team_period_results AS t
       (sport, season, game_id, team, period, game_date, opponent, is_home,
        pts_for, pts_against, spread, total_line, spread_source, total_source,
        ats, ou, rest_days, opp_rest_days)
SELECT %(sport)s, season, game_id, team, period, game_date, opponent, is_home,
       pts_for, pts_against, spread, total_line, s_src, t_src,
       ats, ou, rest_days, opp_rest_days
  FROM final
ON CONFLICT (game_id, team, period) DO UPDATE SET
       sport = EXCLUDED.sport, season = EXCLUDED.season, game_date = EXCLUDED.game_date,
       opponent = EXCLUDED.opponent, is_home = EXCLUDED.is_home,
       pts_for = EXCLUDED.pts_for, pts_against = EXCLUDED.pts_against,
       spread = EXCLUDED.spread, total_line = EXCLUDED.total_line,
       spread_source = EXCLUDED.spread_source, total_source = EXCLUDED.total_source,
       ats = EXCLUDED.ats, ou = EXCLUDED.ou,
       rest_days = EXCLUDED.rest_days, opp_rest_days = EXCLUDED.opp_rest_days,
       updated_at = NOW()
 WHERE (t.sport, t.season, t.game_date, t.opponent, t.is_home, t.pts_for, t.pts_against,
        t.spread, t.total_line, t.spread_source, t.total_source, t.ats, t.ou,
        t.rest_days, t.opp_rest_days)
       IS DISTINCT FROM
       (EXCLUDED.sport, EXCLUDED.season, EXCLUDED.game_date, EXCLUDED.opponent, EXCLUDED.is_home,
        EXCLUDED.pts_for, EXCLUDED.pts_against, EXCLUDED.spread, EXCLUDED.total_line,
        EXCLUDED.spread_source, EXCLUDED.total_source, EXCLUDED.ats, EXCLUDED.ou,
        EXCLUDED.rest_days, EXCLUDED.opp_rest_days)
"""


def _period_values() -> str:
    parts = []
    for period, (spread_market, total_market) in PERIOD_MARKETS.items():
        parts.append(f"('{period}', 'spread', '{spread_market}')")
        parts.append(f"('{period}', 'total', '{total_market}')")
    return ", ".join(parts)


def select_sql() -> str:
    """The rows the writer would store, as a SELECT (read-only; used by checks)."""
    return _SQL.replace("{period_markets}", _period_values()) + "SELECT * FROM final"


def upsert_sql() -> str:
    return _SQL.replace("{period_markets}", _period_values()) + _UPSERT


def params(sport: str, seasons: list[int]) -> dict:
    return {"sport": sport, "seasons": sorted({int(s) for s in seasons}),
            "books": line_books(), "primary": PRIMARY_BOOK}


def table_exists(conn) -> bool:
    row = conn.execute(f"SELECT to_regclass('public.{TABLE}') IS NOT NULL").fetchone()
    return bool(row and row[0])


def rebuild(conn, sport: str, seasons: list[int]) -> dict:
    """Upsert every team-game-period of `seasons`. The table is created by the
    view migration, so a pass before it lands writes nothing and says so."""
    if sport not in SPORTS:
        raise ValueError(f"{sport} has no period scoring here yet; known: {SPORTS}")
    p = params(sport, seasons)
    if not p["seasons"]:
        return {"sport": sport, "seasons": [], "rows": 0}
    if not table_exists(conn):
        logger.warning(f"{TABLE} does not exist yet (add_team_period_results_2026_11_13.sql); skipped")
        return {"sport": sport, "seasons": p["seasons"], "rows": 0, "skipped": "no table"}
    cur = conn.execute(upsert_sql(), p)
    n = cur.rowcount if cur.rowcount is not None else 0
    conn.commit()
    return {"sport": sport, "seasons": p["seasons"], "rows": n}


def seasons_to_build(conn, sport: str, season: int) -> list[int]:
    """This season always; last season only while it has no rows, because the
    last-N windows reach back into it early on (Matt, 2026-10-23) and its
    lines never change again."""
    out = [season]
    if table_exists(conn):
        row = conn.execute(f"SELECT 1 FROM {TABLE} WHERE sport = %s AND season = %s LIMIT 1",
                           (sport, season - 1)).fetchone()
        if not row:
            out.insert(0, season - 1)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sport", default="NBA", choices=SPORTS)
    ap.add_argument("--seasons", type=int, nargs="+", required=True)
    a = ap.parse_args()
    conn = get_connection()
    try:
        print(rebuild(conn, a.sport, a.seasons))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
