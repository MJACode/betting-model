"""Full-game round 1, step 1: coverage and the data check. Prints markdown.

  A. games played per season; games with any pre-game quote per book and market
  B. each book's first post: median hours before tip, by season (and market)
  C. each book's LAST stored change before tip: median minutes before tip
  D. coherence: quotes dropped (price inside -100..+100 or implied sum outside
     1.00-1.15), by book and market
  E. the home-number sign: at each book's last pre-tip h2h and spread, the
     moneyline favourite against the sign of spread_home
  F. the snapshot clock: snapshot_at against the purchase ledger's snapshot times
"""
import numpy as np
import pandas as pd
import r2_lib as L

g = L.load_games()
qa = L.load_quotes(coherent_only=False, games=g)
qa = qa[qa.played]
print("## r2_coverage.py\n")

# A
gp = g[g.played].groupby("season").size().rename("played")
cov = qa.groupby(["season", "market", "bookmaker"]).game_id.nunique().unstack("bookmaker")
cov = cov[[b for b in L.ALLBOOKS if b in cov.columns]]
cov = cov.reset_index().merge(gp.reset_index(), on="season")
print("### A. Games with any pre-game quote, by season, market and book (all rows, coherent or not)\n")
print(L.md_table(cov.fillna(0).astype({c: int for c in cov.columns if c not in ("market",)})))
# decidable any
anyd = qa[qa.bookmaker.isin(L.DECIDABLE)].groupby(["season", "market"]).game_id.nunique().rename("any_decidable")
pin = qa[qa.bookmaker == "pinnacle"].groupby(["season", "market"]).game_id.nunique().rename("pinnacle")
both = qa[qa.bookmaker.isin(L.DECIDABLE)][["season", "market", "game_id"]].drop_duplicates().merge(
    qa[qa.bookmaker == "pinnacle"][["season", "market", "game_id"]].drop_duplicates())
both = both.groupby(["season", "market"]).game_id.nunique().rename("decidable_and_pinnacle")
t = pd.concat([anyd, pin, both], axis=1).fillna(0).astype(int).reset_index()
print("\n### A2. Games with a decidable quote, a Pinnacle quote, and both\n")
print(L.md_table(t))

# B first post
fp = L.first_posts(qa)
fp["lead_h"] = fp.lead_min / 60
t = fp.groupby(["season", "bookmaker"]).lead_h.median().unstack("bookmaker")
t = t[[b for b in L.ALLBOOKS if b in t.columns]].round(1).reset_index()
print("\n### B. Each book's first post (any market): median hours before tip\n")
print(L.md_table(t))
t = fp[fp.bookmaker.isin(L.DECIDABLE + ["pinnacle"])].groupby(["season", "market", "bookmaker"]).lead_h.median().unstack("bookmaker").round(1).reset_index()
print("\n### B2. First post by market (hours before tip, median)\n")
print(L.md_table(t))
t = fp[fp.bookmaker.isin(["draftkings", "pinnacle"])].groupby(["season", "bookmaker"]).lead_h.quantile([.1, .25, .5, .75, .9]).unstack().round(1).reset_index()
print("\n### B3. DraftKings and Pinnacle first post, quantiles of hours before tip (any market)\n")
print(L.md_table(t))

# C last change
lp = L.last_pretip(qa)
t = lp.groupby(["season", "bookmaker"]).lead_min.median().unstack("bookmaker")
t = t[[b for b in L.ALLBOOKS if b in t.columns]].round(0).reset_index()
print("\n### C. Each book's last stored change before tip: median minutes before tip\n")
print(L.md_table(t))

# D coherence
d = qa.assign(bad_price=~(np.isfinite(qa.pa) & np.isfinite(qa.pb) & (qa.pa.abs() >= 100) & (qa.pb.abs() >= 100)),
              bad_sum=~qa.coherent)
t = d.groupby(["bookmaker", "market"]).agg(rows=("coherent", "size"), dropped=("bad_sum", "sum"),
                                            price_inside_100=("bad_price", "sum")).reset_index()
t["dropped_%"] = (100 * t.dropped / t.rows).round(2)
print("\n### D. Coherence: rows dropped (price inside -100..+100, or implied sum outside 1.00-1.15)\n")
print(L.md_table(t))
print("\nTotal rows", len(d), "dropped", int(d.bad_sum.sum()))
x = d[d.coherent]
print("\nImplied-sum quantiles of the kept rows, by book (the margin each book carries):\n")
t = x.groupby(["bookmaker", "market"]).isum.median().unstack().round(4).reset_index()
print(L.md_table(t))

# E sign
q = qa[qa.coherent]
lp = L.last_pretip(q)
h = lp[lp.market == "h2h"][["game_id", "bookmaker", "season", "pa", "pb", "pa_mult"]]
s = lp[lp.market == "spreads"][["game_id", "bookmaker", "line"]]
e = h.merge(s, on=["game_id", "bookmaker"])
e["ml_home_fav"] = e.pa_mult > 0.5
e["sp_home_fav"] = e.line < 0
e2 = e[(e.line != 0)]
e2 = e2.assign(agree=e2.ml_home_fav == e2.sp_home_fav, big=e2.line.abs() >= 1.5)
t = e2.groupby("bookmaker").agg(pairs=("agree", "size"), agree=("agree", "sum"),
                                disagree_line_ge_1_5=("big", lambda b: int((b & ~e2.loc[b.index, "agree"]).sum()))).reset_index()
print("\n### E. Home-number sign: last pre-tip moneyline favourite vs sign of spread_home (line != 0)\n")
print(L.md_table(t))
print("\nhome favourite by moneyline AND negative spread_home:", int((e2.ml_home_fav & e2.sp_home_fav).sum()),
      "| home underdog AND positive spread_home:", int((~e2.ml_home_fav & ~e2.sp_home_fav).sum()))
bad = e2[~e2.agree].sort_values("line", key=lambda v: -v.abs()).head(8)
print("\nLargest disagreements:\n")
print(L.md_table(bad[["game_id", "bookmaker", "pa", "pb", "line"]]))
# the same check on the result: does the home team win more when spread_home < 0
pk = lp[(lp.market == "spreads") & (lp.bookmaker == "pinnacle")]
print("\nPinnacle close: home win rate when spread_home < 0:",
      round(float((pk[pk.line < 0].margin > 0).mean()), 4), "n", int((pk.line < 0).sum()),
      "| when spread_home > 0:", round(float((pk[pk.line > 0].margin > 0).mean()), 4), "n", int((pk.line > 0).sum()))
print("Pinnacle close: corr(spread_home, home margin):", round(float(np.corrcoef(pk.line, pk.margin)[0, 1]), 4))

# F snapshot clock
snap = pd.read_parquet(L.CACHE / "snapshots.parquet")
st = np.sort(snap.snapshot_ts.values.astype("datetime64[us]").astype(np.int64))
qs = qa.snapshot_at.values.astype("datetime64[us]").astype(np.int64)
i = np.searchsorted(st, qs, side="left")
i = np.clip(i, 0, len(st) - 1)
nxt = (st[i] - qs) / 1e6
print("\n### F. snapshot_at against the ledger's snapshot times\n")
print("ledger snapshots:", len(st), "range", snap.snapshot_ts.min(), "to", snap.snapshot_ts.max())
print("seconds from a quote's snapshot_at to the next ledger snapshot (>= it): quantiles",
      pd.Series(nxt).quantile([.01, .05, .25, .5, .75, .95, .99]).round(1).to_dict())
print("share with snapshot_at exactly equal to a ledger snapshot time:", round(float((nxt == 0).mean()), 4))
print("share with the next ledger snapshot within 300 s:", round(float((nxt <= 300).mean()), 4),
      "| within 900 s:", round(float((nxt <= 900).mean()), 4))
gaps = np.diff(st) / 1e6
print("ledger gap seconds quantiles:", pd.Series(gaps).quantile([.05, .25, .5, .75, .95]).round(0).to_dict())
# DraftKings in 2021-22
dk22 = qa[(qa.bookmaker == "draftkings") & (qa.season == 2022)]
print("\nDraftKings rows in 2021-22:", len(dk22), "games", dk22.game_id.nunique(),
      "first", dk22.snapshot_at.min(), "last", dk22.snapshot_at.max())
