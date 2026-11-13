"""Full-game round 1, step 6: the kill tests on the two positive results. Prints markdown.

1. (a) line shopping, spreads, consensus over all ten books, main read 15utc,
   catalogued cut 0.03, priced seasons 2023-24 on (r2_methods.method_a):
   side split; placebo c = 0 (the home offset removed); what the close did to
   the bet line; the bet quote's age and the bet book's next move;
   decomposition (the rule's sides at the consensus line at -110, blind home
   on the same games at the bet quote, blind home on every game at
   DraftKings); 10 best dates removed; early / late inside each season; by
   book; volume.
2. Moneyline favourites at -500 or shorter (the brief's price band) at the
   DraftKings close: by season, early / late, 10 best dates removed, the fair
   under both de-vigs, the stake profile, the neighbouring price thresholds
   (-400 .. -800, fixed here before reading them), the same band at the best
   decidable price, at DraftKings' first post, and at Pinnacle's own close
   (not bettable; is the pattern DraftKings' alone?).
"""
import numpy as np
import pandas as pd
import r2_lib as L
import r2_methods as M

print("## r2_kill.py\n")
CUT = 0.03
A = {r: L.grade(M.method_a(r, "spreads", L.ALLBOOKS)) for r in M.READS}
for r in A:
    A[r] = A[r][A[r].season >= 2024]
bets = {r: A[r][A[r].edge > CUT].copy() for r in A}
b = bets["15utc"]

# 1. side split
rows = []
for r, x in bets.items():
    for lab, sub in (("home", x[x.side == "home"]), ("away", x[x.side == "away"]),
                     ("favourite (by line)", x[((x.side == "home") & (x.line < 0)) | ((x.side == "away") & (x.line > 0))]),
                     ("underdog (by line)", x[((x.side == "home") & (x.line > 0)) | ((x.side == "away") & (x.line < 0))])):
        d = L.row({"read": r, "side": lab}, sub)
        d["share%"] = round(100 * len(sub) / len(x), 1)
        rows.append(d)
print("### 1a. (a) spreads, cut 0.03, 2023-24 on: the side split at every read\n")
print(L.md_table(pd.DataFrame(rows)))

# 2. placebo c = 0
saved = {s: M.TABLES[s]["c_sp"] for s in M.TABLES}
for s in M.TABLES:
    M.TABLES[s]["c_sp"] = 0.0
P = {r: L.grade(M.method_a(r, "spreads", L.ALLBOOKS)) for r in M.READS}
for s in M.TABLES:
    M.TABLES[s]["c_sp"] = saved[s]
rows = []
for r in M.READS:
    for cut in M.A_CUTS:
        x = P[r][(P[r].season >= 2024) & (P[r].edge > cut)]
        d = L.row({"read": r, "cut": cut, "version": "c = 0 (placebo)"}, x)
        d["home%"] = round(100 * float((x.side == "home").mean()), 1) if len(x) else np.nan
        rows.append(d)
        x = A[r][A[r].edge > cut]
        d = L.row({"read": r, "cut": cut, "version": "c fitted (the rule)"}, x)
        d["home%"] = round(100 * float((x.side == "home").mean()), 1) if len(x) else np.nan
        rows.append(d)
print("\n### 1b. Placebo: the home offset c set to 0, everything else unchanged\n")
print(L.md_table(pd.DataFrame(rows)))

# 3. what the close did: consensus at 15utc vs close, the bet line
c15 = M.consensus(M.sign_flag(M.boards["15utc"][M.boards["15utc"].market == "spreads"]), L.ALLBOOKS)[0]
cc = M.cons_sp_close
x = b.copy()
x["c15"] = x.game_id.map(c15)
x["cc"] = x.game_id.map(cc)
sgn = np.where(x.side == "home", 1, -1)
x["off_pts"] = sgn * (x.line - x.c15)           # points better than the 15utc consensus for the bet side
x["line_clv_pts"] = sgn * (x.line - x.cc)       # points better than the close consensus
x["cons_moved_to_bet"] = np.sign(x.cc - x.c15) == np.sign(x.line - x.c15)
x["cons_moved_away"] = np.sign(x.cc - x.c15) == -np.sign(x.line - x.c15)
print("\n### 1c. The bet line against the consensus at the read and at the close (15utc, cut 0.03)\n")
t = pd.DataFrame([{
    "bets": len(x), "mean pts better than 15utc consensus": round(float(x.off_pts.mean()), 3),
    "mean pts better than close consensus": round(float(x.line_clv_pts.mean()), 3),
    "share better than close consensus %": round(100 * float((x.line_clv_pts > 0).mean()), 1),
    "share equal to close consensus %": round(100 * float((x.line_clv_pts == 0).mean()), 1),
    "consensus moved toward the bet line %": round(100 * float(x.cons_moved_to_bet.mean()), 1),
    "consensus moved away %": round(100 * float(x.cons_moved_away.mean()), 1),
    "mean clv (prob, Pinnacle close)": round(float(np.nanmean(M.clv(x))), 4)}])
print(L.md_table(t))
t = x.groupby(x.off_pts.round(1)).agg(bets=("game_id", "size"), units=("units", "sum"), risk=("risk", "sum")).reset_index()
t["ret%"] = (100 * t.units / t.risk).round(2)
print("\nBy how far the bet line sat from the 15utc consensus (points, toward the bet side):\n")
print(L.md_table(t.rename(columns={"off_pts": "off_pts (points)"})))

# 4. freshness: the bet quote's age at the read, and the bet book's next move
T15 = M.dt["15utc"]
x["T"] = x.game_id.map(T15)
x["age_h"] = (x["T"] - x.snapshot_at).dt.total_seconds() / 3600
allq = A["15utc"].copy()
allq["T"] = allq.game_id.map(T15)
allq["age_h"] = (allq["T"] - allq.snapshot_at).dt.total_seconds() / 3600
# every priced decidable quote at the read (not only each game's best)
print("\n### 1d. The bet quote's age at the read (hours since that book's last change)\n")
print(f"- bets: median {x.age_h.median():.1f} h, quartiles {x.age_h.quantile(.25):.1f} / {x.age_h.quantile(.75):.1f}")
print(f"- every game's best decidable quote (bet or not): median {allq.age_h.median():.1f} h")
rows = []
for lab, sub in (("all bets", x), ("quote changed <= 2 h before the read", x[x.age_h <= 2]),
                 ("quote changed <= 6 h before the read", x[x.age_h <= 6]),
                 ("quote older than 6 h", x[x.age_h > 6])):
    rows.append(L.row({"subset": lab}, sub))
print(L.md_table(pd.DataFrame(rows)))
# next move of the bet book after the read
q = M.q
nxt = q[q.market == "spreads"].merge(x[["game_id", "bookmaker", "T", "line", "c15", "side"]].rename(
    columns={"line": "bet_line"}), on=["game_id", "bookmaker"])
nxt = nxt[nxt.snapshot_at > nxt["T"]]
lines_after = nxt[nxt.line != nxt.bet_line].drop_duplicates(["game_id", "bookmaker"], keep="first")
x = x.merge(lines_after[["game_id", "bookmaker", "line", "snapshot_at"]].rename(
    columns={"line": "next_line", "snapshot_at": "next_at"}), on=["game_id", "bookmaker"], how="left")
moved = x.next_line.notna()
toward = moved & ((x.next_line - x.c15).abs() < (x.line - x.c15).abs())
print("\nThe bet book's next LINE change after the read, before the tip:")
print(f"- no line change before tip: {int((~moved).sum())} of {len(x)}; changed: {int(moved.sum())}, "
      f"of which toward the 15utc consensus: {int(toward.sum())}, away or across: {int((moved & ~toward).sum())}; "
      f"median hours from the read to that change: {((x.next_at - x['T']).dt.total_seconds() / 3600)[moved].median():.1f}")

# 5. decomposition
rows = []
rows.append(L.row({"version": "the rule (bet book's line and price)"}, x))
y = x.copy()
y["line"] = y.c15
y["price"] = -110.0
rows.append(L.row({"version": "the rule's sides at the 15utc consensus line, -110"}, L.grade(y)))
y = b.copy()
y["side"] = "home"
y["price"] = y.pa
rows.append(L.row({"version": "home on the same games, at the bet quote's line and home price"}, L.grade(y)))
dk = M.boards["15utc"]
dk = dk[(dk.market == "spreads") & (dk.bookmaker == "draftkings") & (dk.season >= 2024)].copy()
dk["side"] = "home"
dk["price"] = dk.pa
rows.append(L.row({"version": "home on every game, DraftKings at 15utc"}, L.grade(dk)))
dk["side"] = "away"
dk["price"] = dk.pb
rows.append(L.row({"version": "away on every game, DraftKings at 15utc"}, L.grade(dk)))
print("\n### 1e. Decomposition (15utc, cut 0.03, 2023-24 on)\n")
print(L.md_table(pd.DataFrame(rows)))

# 6. best dates, early / late, by book, volume
best = b.groupby("game_date").units.sum().sort_values(ascending=False).head(10).index
rows = [L.row({"subset": "all"}, b), L.row({"subset": "without its 10 best dates"}, b[~b.game_date.isin(best)])]
med = b.groupby("season").game_date.transform(lambda d: sorted(d)[len(d) // 2])
rows.append(L.row({"subset": "early half of each season"}, b[b.game_date < med]))
rows.append(L.row({"subset": "late half of each season"}, b[b.game_date >= med]))
for bk, sub in b.groupby("bookmaker"):
    rows.append(L.row({"subset": f"book: {bk}"}, sub))
for s, sub in b.groupby("season"):
    for half, h in (("early", sub[sub.game_date < med.loc[sub.index]]), ("late", sub[sub.game_date >= med.loc[sub.index]])):
        rows.append(L.row({"subset": f"season {int(s)} {half}"}, h))
print("\n### 1f. Best dates, early / late, by book (15utc, cut 0.03, 2023-24 on)\n")
print(L.md_table(pd.DataFrame(rows)))
ng = A["15utc"].game_id.nunique()
print(f"\nVolume: {len(b)} bets on {ng} priced games ({100 * len(b) / ng:.1f}% of them) over "
      f"{b.season.nunique()} seasons, {len(b) / b.season.nunique():.0f} a season.")
print(f"Price range of the bets: median {b.price.median():.0f}, shortest {b.price.min():.0f}, longest {b.price.max():.0f}.")

# 2. the -500 moneyline band
print("\n### 2. Moneyline favourites at -500 or shorter, DraftKings close\n")
g = M.g
cb = M.boards["close"]
fp = L.first_posts(M.q)


def ml_sides(bd, book):
    z = L.sides_long(bd[(bd.market == "h2h") & (bd.bookmaker == book)])
    z["fair_pow"] = np.where(z.side == "home", z.pa_pow, 1 - z.pa_pow)
    return L.grade(z)


dkc = ml_sides(cb, "draftkings")
band = dkc[dkc.price <= -500]
rows = [L.row({"subset": "all seasons"}, band)]
for s, sub in band.groupby("season"):
    rows.append(L.row({"subset": f"season {int(s)}"}, sub))
medd = band.groupby("season").game_date.transform(lambda d: sorted(d)[len(d) // 2])
rows.append(L.row({"subset": "early half of each season"}, band[band.game_date < medd]))
rows.append(L.row({"subset": "late half of each season"}, band[band.game_date >= medd]))
best = band.groupby("game_date").units.sum().sort_values(ascending=False).head(10).index
rows.append(L.row({"subset": "without its 10 best dates"}, band[~band.game_date.isin(best)]))
rows.append(L.row({"subset": "home side"}, band[band.side == "home"]))
rows.append(L.row({"subset": "away side"}, band[band.side == "away"]))
print(L.md_table(pd.DataFrame(rows)))
print(f"\nStake profile: {len(band)} bets risked {band.risk.sum():.1f} units to win {band.units[band.res > 0].sum():.1f}; "
      f"mean win per winning bet {band.units[band.res > 0].mean():.3f} units; each loss costs up to 3 units "
      f"(mean loss {-band.units[band.res < 0].mean():.2f}). Median price {band.price.median():.0f}, shortest {band.price.min():.0f}.")
print(f"Fair: multiplicative de-vig mean {band.fair.mean():.4f}, power de-vig mean {band.fair_pow.mean():.4f}, "
      f"won {(band.res > 0).mean():.4f}.")
rows = []
for thr in (-400, -450, -500, -550, -600, -700, -800):
    rows.append(L.row({"threshold (price at or shorter)": thr}, dkc[dkc.price <= thr]))
print("\nNeighbouring thresholds (fixed before reading):\n")
print(L.md_table(pd.DataFrame(rows)))
rows = []
for lab, z in (("DraftKings first post", ml_sides(fp, "draftkings")),
               ("Pinnacle close (reference, not bettable)", ml_sides(cb, "pinnacle")),
               ("Bovada close (reference)", ml_sides(cb, "bovada")),
               ("Unibet close (reference)", ml_sides(cb, "unibet"))):
    rows.append(L.row({"where": lab}, z[z.price <= -500]))
for bk in ("fanduel", "betmgm", "betrivers", "fanatics"):
    z = ml_sides(cb, bk)
    rows.append(L.row({"where": f"{bk} close (2025-26 on)"}, z[z.price <= -500]))
print("\nThe same band at other books and reads:\n")
print(L.md_table(pd.DataFrame(rows)))
