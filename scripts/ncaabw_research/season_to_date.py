"""This season to date, through the totals card's own reads and decision.

The stored games and box rows of the season (scripts/ncaabw_total_card.
load_season, prepare_season), the committed artifact, and
models.ncaabw_total_blend.decide at each game's DraftKings first post (from the
research cache's pre-game quotes). What the card would have decided on every
priced game so far, and how the bets graded. Nothing is written.

It differs from a live run in one way: every box row stored today is used, so
a hold that a late box would have caused does not show.

    python -m scripts.ncaabw_research.season_to_date [season]
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.ncaabw_research._paths import CACHE  # noqa: E402
import config  # noqa: E402
import models.ncaabw_total_blend as nb  # noqa: E402
import scripts.ncaabw_total_blend_build as build  # noqa: E402
import scripts.ncaabw_total_card as card  # noqa: E402
from data.db import get_connection  # noqa: E402

season = int(sys.argv[1]) if len(sys.argv) > 1 else 2027
art = nb.load_artifact()
assert int(art["season"]) == season, (art["season"], season)
cut = config.MODEL_EDGE_THRESHOLDS[nb.MODEL_ID]
with get_connection() as conn:
    games_df, box_df = card.load_season(conn, season)
    d1 = card.d1_team_ids(conn)
sg, box = card.prepare_season(games_df, box_df)
dk = build.first_posts(pd.read_parquet(CACHE / "pregame_quotes.parquet"))
dk = dk[dk["game_id"].isin(set(sg["game_id"]))]
print(f"season {season}: {len(sg)} stored games to {sg['game_date'].max()}, "
      f"{int(sg['home_score'].notna().sum())} finals; DraftKings first totals {len(dk)}")
ns = pd.concat([sg["n_sched_home"], sg["n_sched_away"]])
ids = pd.concat([sg["home_espn_id"], sg["away_espn_id"]])
per_team = pd.DataFrame({"t": ids, "n": ns}).dropna().drop_duplicates("t")
d1_rows = per_team[per_team["t"].astype(int).isin(d1)]
print(f"Division I teams on the schedule: {len(d1_rows)}; with under {nb.SCHED_MIN} stored games: "
      f"{int((d1_rows['n'] < nb.SCHED_MIN).sum())}; fewest {int(d1_rows['n'].min())}, "
      f"median {int(d1_rows['n'].median())}")
quotes = {}
for r in dk.itertuples(index=False):
    at = pd.Timestamp(int(r.quote_ns), tz="UTC").to_pydatetime()
    quotes[r.game_id] = nb.Quote(game_id=r.game_id, line=float(r.line), over_price=float(r.over_price),
                                 under_price=float(r.under_price), quote_at=at, fetched_at=at)
short = card.schedule_short(sg, list(quotes), d1)
print(f"priced games the short-schedule guard would stop: {len(short)}")
got = nb.decide(sg[sg["game_id"].isin(set(quotes))], quotes, sg, box, art, cut)
print("decisions:", pd.Series([d.status for d in got]).value_counts().to_dict())
fin = sg.set_index("game_id")
rows = []
for d in got:
    if d.priced is None:
        print(f"  {d.game_id}: {d.status}: {d.detail}")
        continue
    g = fin.loc[d.game_id]
    total = (g["home_score"] + g["away_score"]) if pd.notna(g["home_score"]) else None
    rows.append({"game_id": d.game_id, "season": season, "game_date": g["game_date"], "total": total,
                 "line": d.quote.line, "side": d.priced.side, "price": d.priced.price,
                 "edge": d.priced.edge, "prob": d.priced.prob, "model": d.model_total,
                 "ng": min(d.ng), "status": d.status})
x = pd.DataFrame(rows)
done = x[x["total"].notna()]
err_line = (done["total"] - done["line"])
err_model = (done["total"] - done["model"])
print(f"priced and final: {len(done)}; the line's mean error {err_line.abs().mean():.2f} (bias "
      f"{err_line.mean():+.2f}), the model's {err_model.abs().mean():.2f} (bias {err_model.mean():+.2f})")
for c in (0.03, 0.04, cut, 0.06, 0.08):
    b = done[done["edge"] > c]
    print(f"  edge > {c:.2f}: {build.grade(b)}")
b = x[x["edge"] > cut]
print(f"bets at the live cut {cut}: {len(b)} ({int(b['total'].isna().sum())} not final yet)")
for r in b.sort_values("game_date").itertuples(index=False):
    res = "" if r.total is None or pd.isna(r.total) else (
        "won" if (r.total - r.line) * (1 if r.side == "over" else -1) > 0 else
        "lost" if (r.total - r.line) != 0 else "push")
    print(f"  {r.game_date} {r.game_id[18:]:44s} {r.side:5s} {r.line:g} {r.price:+.0f} edge {r.edge:+.3f} "
          f"model {r.model:.1f} final {'' if pd.isna(r.total) else int(r.total)} {res}")
