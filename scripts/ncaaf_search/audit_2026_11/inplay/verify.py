"""Hand checks on the graded bets and the counts the report quotes."""
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from paths import CACHE, MIRROR, WORK  # noqa: E402
import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = WORK / "inplay"
pd.set_option("display.width", 300); pd.set_option("display.max_columns", 60)
gi = pd.read_parquet(OUT / "ginfo.parquet")
q = pd.read_parquet(OUT / "quotes.parquet")
num = {}

# 2025 orientation: the timeline's last score against the final of the odds row
tl = pd.read_parquet(OUT / "tl_2025.parquet").sort_values(["game_id", "ord"])
last = tl.groupby("game_id").tail(1).merge(gi[["game_id", "fh", "fa"]], on="game_id")
num["tl2025_games"] = int(len(last))
num["tl2025_last_equals_final"] = int(((last.hs == last.fh) & (last.as_ == last.fa)).sum())
num["tl2025_last_is_final_swapped"] = int(((last.hs == last.fa) & (last.as_ == last.fh) & (last.fh != last.fa)).sum())
print("2025 timeline games:", num["tl2025_games"], "last score == the odds row's final:", num["tl2025_last_equals_final"],
      "== the final with the sides swapped:", num["tl2025_last_is_final_swapped"])

# re-grade a sample of bets from the raw final, independently of grid.py's settle
for f in ("bets_A_V1_h2h_H1_0.08.parquet", "bets_A_V1_totals_H2_0.05.parquet", "bets_B1_V1_totals_H2_0.02.parquet",
          "bets_B2_V1_h2h_H2_0.02.parquet"):
    b = pd.read_parquet(OUT / f).merge(gi[["game_id", "fh", "fa", "home_team", "away_team"]], on="game_id")
    tot = b["side"].isin(["over", "under"])
    won = np.where(b["side"] == "over", b.fh + b.fa > b.line, np.where(b["side"] == "under", b.fh + b.fa < b.line,
                   np.where(b["side"] == "home", b.fh > b.fa, b.fa > b.fh)))
    push = tot & ((b.fh + b.fa) == b.line)
    d = np.where(b.price >= 100, 1 + b.price / 100, 1 + 100 / b.price.abs())
    risk = np.minimum(1 / (d - 1), 3.0)
    units = np.where(push, 0.0, np.where(won, risk * (d - 1), -risk))
    print(f, "bets", len(b), "units stored", round(b.units.sum(), 2), "re-graded", round(units.sum(), 2),
          "max |diff|", round(float(np.abs(units - b.units).max()), 6))
    if f.startswith("bets_A_V1_h2h"):
        print(b[["game_id", "home_team", "away_team", "side", "price", "ev", "p_win", "f", "m", "t", "fh", "fa", "result", "units", "risk"]].head(6).to_string(index=False))

# game-level accounting
s26 = pd.read_parquet(OUT / "st_2026.parquet")
g26q = set(q.loc[q.season == 2026, "game_id"])
g26s = set(s26["game_id"])
num["g2026_quote_games"] = len(g26q)
num["g2026_quote_games_with_states"] = len(g26q & g26s)
num["g2026_state_games"] = len(g26s)
num["g2026_quote_games_before_0919"] = len({g for g in g26q if g[6:16] < "2026-09-19"})
num["g2026_quote_games_from_0919"] = len({g for g in g26q if g[6:16] >= "2026-09-19"})
num["g2026_quotes_before_0919"] = int((q.loc[q.season == 2026, "game_id"].str.slice(6, 16) < "2026-09-19").sum())
pA = pd.read_parquet(OUT / "priced_A.parquet")
num["A_games"] = int(pA.game_id.nunique()); num["A_slates"] = int(pA.slate.nunique())
num["A_v2_games"] = int(pA[pA.v2].game_id.nunique()); num["A_v3_games"] = int(pA[pA.v3].game_id.nunique())
num["A_v3_quotes"] = int(pA.v3.sum())
g25 = pd.read_parquet(OUT / "games_2025.parquet")
num["g2025_pbp_games"] = int(len(g25)); num["g2025_matched"] = int((g25.n_rows > 0).sum())
num["g2025_final_ok"] = int(g25.final_ok.sum()); num["g2025_clean"] = int(g25.clean.sum())
num["g2025_train"] = int(g25.train_ok.sum())
num["g2025_train_by_block"] = g25[g25.train_ok].groupby("block").size().to_dict()
num["g2025_train_prior"] = g25[g25.train_ok].groupby("prior_src").size().to_dict()
tr = pd.read_parquet(OUT / "train_states.parquet")
num["train_states"] = int(len(tr)); num["train_states_by_block"] = tr.groupby("block").size().to_dict()
num["g2025_quote_games"] = int(q.loc[q.season == 2025, "game_id"].nunique())
num["g2025_quote_games_clean_pbp"] = int(tl.game_id.nunique())
for n in ("B1", "B2"):
    p = pd.read_parquet(OUT / f"priced_{n}.parquet")
    num[f"{n}_games"] = int(p.game_id.nunique()); num[f"{n}_slates"] = int(p.slate.nunique())
    num[f"{n}_quotes"] = int(len(p)); num[f"{n}_v2_quotes"] = int(p.v2.sum())
num["q2025"] = int((q.season == 2025).sum()); num["q2026"] = int((q.season == 2026).sum())
num["q_by_season_market"] = {f"{k[0]}|{k[1]}": int(v) for k, v in q.groupby(["season", "market"]).size().items()}
num["qgames_by_season_market"] = {f"{k[0]}|{k[1]}": int(v) for k, v in q.groupby(["season", "market"])["game_id"].nunique().items()}
# share of games that bet at each cut, test A V1 (how little the cut selects under a first-crossing rule)
res = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
for v in ("V1", "V2"):
    el = res["A"][v]["eligible"]
    num[f"A_{v}_share_of_games_betting"] = {f"{c['rule']}@{c['cut']}": round(c["bets"] / el[c["rule"]]["games"], 3)
                                            for c in res["A"][v]["cells"]}
# eligible quotes a game and rule: 2026 against the 2025 replay
num["quotes_per_game_rule"] = {
    "2026": round(float(pA.groupby(["rule", "game_id"]).size().mean()), 1),
    "2025": round(float(pd.concat([pd.read_parquet(OUT / "priced_B1.parquet"), pd.read_parquet(OUT / "priced_B2.parquet")]).groupby(["rule", "game_id"]).size().mean()), 1)}
# book-lead coverage
print(json.dumps(num, indent=1, default=str))
(OUT / "numbers.json").write_text(json.dumps(num, indent=1, default=str), encoding="utf-8")
