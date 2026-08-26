"""
NCAAF search — label set construction.

Spec section "Data setup". Produces exactly ONE row per game, with a single
line provider chosen by a fixed priority, closing-line labels, push flags and
era tags. Everything downstream reads this and nothing else.

Provider reality in this DB (profiled 2026-08-25 — run `--profile` to refresh):

    2014-2018   cfbd_consensus (~800/season) + cfbd_teamrankings (~750)
    2019-2022   + cfbd_bovada (2019 thin at 318; full from 2021)
    2023        consensus COLLAPSES to 29 games, teamrankings to 52;
                cfbd_draftkings begins (754)
    2024-2025   cfbd_draftkings + cfbd_bovada only

There is therefore NO single provider spanning 2014-2025. Any 10-season label
set mixes providers, and the switch lands on 2023 — which is also the season
the existing margin model performed worst (49.6% ATS). That confound is
reported by `--profile` rather than hidden: see `provider_continuity`.

`cfbd_bovada` is the only provider covering 2021-2025 continuously, which is
also exactly the spec's primary (portal/NIL) regime.

The CFBD `spread` / `over_under` fields are CLOSING numbers. Openers
(`spreadOpen` / `overUnderOpen`) are not in the `odds` table -- so
`opener_coverage()` reports 0% against the DB -- but they ARE available from
CFBD for Bovada from 2021 onward and are cached locally by `openers.py`
(4,311 rows, ~99.9% coverage, joining 87.6% of portal-era label rows). Group D
and CLV are therefore live for 2021+ and unavailable before it.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Spec default: Bovada -> consensus -> anything else. Overridable per run so
# the era/provider tradeoff can be measured rather than assumed.
DEFAULT_PRIORITY = [
    "cfbd_bovada",
    "cfbd_consensus",
    "cfbd_draftkings",
    "cfbd_teamrankings",
]

# Seasons the spec treats as the primary regime (portal/NIL era).
PORTAL_ERA = [2021, 2022, 2023, 2024, 2025]
# Excluded by default (spec item 4).
COVID_SEASON = 2020

# 2014 is EXCLUDED and cannot currently be included.
#
# The snapshot look-ahead fix (cfbd_ingestor._completed_before) requires
# rebuilding every season's snapshots, and 2014 cannot be rebuilt: CFBD's
# /stats/season/advanced endpoint returns a persistent HTTP 500 for
# year=2014&endWeek=1 (verified 4/4 attempts; 2015 and 2016 return 200 for the
# same window). The ingestor fails loud rather than writing NULL-poisoned rows,
# which is the correct behaviour, so 2014's snapshots remain in their original
# LEAKED state and must not be trained on.
#
# Cost is small: 2014 is the oldest season, pre-portal, its lines come from the
# consensus provider we already switch away from in 2021, and it contributes
# nothing to the portal-era arm.
FIRST_USABLE_SEASON = 2015


@dataclass
class LabelSet:
    """One row per game plus the provenance needed to defend the labels."""
    games: pd.DataFrame
    provider_counts: pd.DataFrame
    push_rates: dict
    dropped: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.games)


def _fetch_raw(conn, seasons: list[int]) -> pd.DataFrame:
    """Completed NCAAF games joined to every candidate line row."""
    season_ph = ",".join(["%s"] * len(seasons))
    rows = conn.execute(f"""
        SELECT g.game_id, g.season, g.week, g.game_date, g.commence_time,
               g.home_team, g.away_team, g.home_score, g.away_score,
               g.neutral_site, g.conference_game, g.venue_id
        FROM games g
        WHERE g.sport = 'NCAAF'
          AND g.season IN ({season_ph})
          AND g.home_score IS NOT NULL
          AND g.away_score IS NOT NULL
        ORDER BY g.game_date, g.game_id
    """, seasons).fetchall()
    cols = ["game_id", "season", "week", "game_date", "commence_time",
            "home_team", "away_team", "home_score", "away_score",
            "neutral_site", "conference_game", "venue_id"]
    return pd.DataFrame(rows, columns=cols)


def _fetch_lines(conn, seasons: list[int]) -> pd.DataFrame:
    """
    One row per (game, provider) carrying that provider's closing spread and
    total. Historical CFBD rows are exactly one snapshot per game/provider
    (verified), so no snapshot collapsing is needed; in-play is excluded
    defensively regardless.
    """
    season_ph = ",".join(["%s"] * len(seasons))
    rows = conn.execute(f"""
        SELECT o.game_id, o.bookmaker, o.market, o.spread_home, o.total_line,
               o.snapshot_at
        FROM odds o
        JOIN games g ON g.game_id = o.game_id
        WHERE g.sport = 'NCAAF'
          AND g.season IN ({season_ph})
          AND o.market IN ('spreads', 'totals')
          AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
    """, seasons).fetchall()
    df = pd.DataFrame(rows, columns=["game_id", "bookmaker", "market",
                                     "spread_home", "total_line", "snapshot_at"])
    if df.empty:
        return df

    # Collapse to one spread + one total per (game, provider). Take the LAST
    # snapshot when a provider somehow has several (live 2026 books do).
    df = df.sort_values("snapshot_at")
    spreads = (df[df["market"] == "spreads"]
               .dropna(subset=["spread_home"])
               .groupby(["game_id", "bookmaker"], as_index=False)
               .agg(spread_home=("spread_home", "last")))
    totals = (df[df["market"] == "totals"]
              .dropna(subset=["total_line"])
              .groupby(["game_id", "bookmaker"], as_index=False)
              .agg(total_line=("total_line", "last")))
    return spreads.merge(totals, on=["game_id", "bookmaker"], how="outer")


def _pick_provider(lines: pd.DataFrame, priority: list[str],
                   column: str) -> pd.DataFrame:
    """
    Choose ONE provider per game for `column` by fixed priority.

    Spec: "Never mix providers within the label set." We cannot honour that
    across 2014-2025 (no provider spans it), so the mixing that does occur is
    made explicit — every returned row carries the provider that supplied it.
    """
    sub = lines.dropna(subset=[column]).copy()
    if sub.empty:
        return pd.DataFrame(columns=["game_id", column, f"{column}_provider"])
    rank = {b: i for i, b in enumerate(priority)}
    sub["_rank"] = sub["bookmaker"].map(rank).fillna(len(priority)).astype(int)
    sub = sub.sort_values(["game_id", "_rank"])
    best = sub.groupby("game_id", as_index=False).first()
    return best[["game_id", column, "bookmaker"]].rename(
        columns={"bookmaker": f"{column}_provider"})


def build_label_set(seasons: list[int] | None = None,
                    priority: list[str] | None = None,
                    exclude_covid: bool = True,
                    conn=None) -> LabelSet:
    """
    Build the canonical labelled dataset.

    Labels (pushes EXCLUDED from both, and counted):
        home_covers = (home_score - away_score + closing_spread_home) > 0
        went_over    = (home_score + away_score) > closing_total
    """
    from data.db import get_connection

    priority = list(priority or DEFAULT_PRIORITY)
    seasons = sorted(seasons or [s for s in range(FIRST_USABLE_SEASON, 2026)])
    if exclude_covid:
        seasons = [s for s in seasons if s != COVID_SEASON]

    owned = conn is None
    conn = conn or get_connection()
    try:
        games = _fetch_raw(conn, seasons)
        lines = _fetch_lines(conn, seasons)
    finally:
        if owned:
            conn.close()

    dropped = {"no_game_rows": 0, "no_spread": 0, "no_total": 0,
               "spread_push": 0, "total_push": 0}
    if games.empty:
        return LabelSet(games, pd.DataFrame(), {}, dropped)

    spread = _pick_provider(lines, priority, "spread_home")
    total = _pick_provider(lines, priority, "total_line")
    df = games.merge(spread, on="game_id", how="left") \
              .merge(total, on="game_id", how="left")

    for c in ("home_score", "away_score", "spread_home", "total_line"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["margin"] = df["home_score"] - df["away_score"]
    df["total_points"] = df["home_score"] + df["away_score"]

    # ── Spread label ────────────────────────────────────────────────────────
    dropped["no_spread"] = int(df["spread_home"].isna().sum())
    ats = df["margin"] + df["spread_home"]
    df["spread_push"] = (ats == 0) & df["spread_home"].notna()
    dropped["spread_push"] = int(df["spread_push"].sum())
    df["home_covers"] = np.where(
        df["spread_home"].isna() | df["spread_push"], np.nan, (ats > 0).astype(float))

    # ── Totals label ────────────────────────────────────────────────────────
    dropped["no_total"] = int(df["total_line"].isna().sum())
    df["total_push"] = (df["total_points"] == df["total_line"]) & df["total_line"].notna()
    dropped["total_push"] = int(df["total_push"].sum())
    df["went_over"] = np.where(
        df["total_line"].isna() | df["total_push"], np.nan,
        (df["total_points"] > df["total_line"]).astype(float))

    # ── Era tags ────────────────────────────────────────────────────────────
    df["is_portal_era"] = df["season"].isin(PORTAL_ERA).astype(int)
    df["season_index"] = df["season"] - df["season"].min()

    push_rates = {
        "spread": round(float(df["spread_push"].sum()) /
                        max(int(df["spread_home"].notna().sum()), 1), 5),
        "total": round(float(df["total_push"].sum()) /
                       max(int(df["total_line"].notna().sum()), 1), 5),
    }

    prov = (pd.concat([
        df.groupby(["season", "spread_home_provider"]).size()
          .rename("games").reset_index().assign(market="spreads")
          .rename(columns={"spread_home_provider": "provider"}),
        df.groupby(["season", "total_line_provider"]).size()
          .rename("games").reset_index().assign(market="totals")
          .rename(columns={"total_line_provider": "provider"}),
    ], ignore_index=True))

    assert df["game_id"].is_unique, "duplicate game_ids after provider dedup"
    return LabelSet(df, prov, push_rates, dropped)


def provider_continuity(prov: pd.DataFrame) -> pd.DataFrame:
    """
    Which providers cover which seasons, so an era choice is evidence-based
    rather than a default nobody checked.
    """
    s = prov[prov["market"] == "spreads"]
    return (s.pivot_table(index="provider", columns="season", values="games",
                          aggfunc="sum", fill_value=0)
             .astype(int))


def opener_coverage(seasons: list[int] | None = None, conn=None) -> dict:
    """
    Spec item 3. Openers were never ingested by `cfbd_ingestor`, so this is
    expected to report zero — it exists so the gap is measured, not assumed,
    and so it flips automatically once a backfill lands.
    """
    from data.db import get_connection
    owned = conn is None
    conn = conn or get_connection()
    try:
        cols = {r[0] for r in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='odds'").fetchall()}
        has_cols = {"spread_open", "total_line_open"} & cols
        n_snap = conn.execute("""
            SELECT count(*) FROM odds o JOIN games g ON g.game_id=o.game_id
            WHERE g.sport='NCAAF' AND g.season < 2026
              AND o.bookmaker LIKE 'cfbd_%'
        """).fetchone()[0]
        n_games = conn.execute("""
            SELECT count(DISTINCT o.game_id) FROM odds o
            JOIN games g ON g.game_id=o.game_id
            WHERE g.sport='NCAAF' AND g.season < 2026
              AND o.bookmaker LIKE 'cfbd_%'
        """).fetchone()[0]
    finally:
        if owned:
            conn.close()
    return {
        "opener_columns_present": sorted(has_cols),
        "cfbd_snapshot_rows": n_snap,
        "cfbd_games": n_games,
        "snapshots_per_game": round(n_snap / max(n_games, 1), 3),
        "openers_available": bool(has_cols),
        "note": ("One snapshot per game/provider and no opener columns: the "
                 "stored number is the CLOSE. Group D (open->close movement) "
                 "and CLV are blocked until openers are backfilled."),
    }
