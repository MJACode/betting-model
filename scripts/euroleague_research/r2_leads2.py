"""Full-game round 1, step 4b: the scout's leads 2 and 3 as blind bets. Prints markdown.

Both hypotheses are the scout's (docs/euroleague_market_audit.md leads 2 and 3),
stated before any EuroLeague price was read. Their residual tables were READ
FIRST (r2_leads.py), so these bets are not independent of that read: every
result below is flagged as chosen with the residual tables in view.

  H3  "Weaker teams lean on home court more": bet the HOME UNDERDOG against
      the spread (home line > 0). Neighbourhood fixed here: home line > 0,
      >= +1.5, >= +3, >= +5; and the mirror (the away favourite) for the side
      control. A walk-forward version with nothing chosen by eye: in each
      season, bet home in every closing-spread bucket (r2_leads' six) whose
      mean residual over EVERY EARLIER season is > 0.
  H2  "Home edge depends on crowd size": bet HOME against the spread when the
      home club's previous-season mean attendance is in the top tercile of
      that season's home games (as r2_leads); neighbourhood: top half, top
      quartile; mirror: AWAY when in the bottom tercile.
  Prices: the DraftKings close, the best decidable close (the modal decidable
  number, the best price on it), and DraftKings at 15utc (a pre-tip read).
  Neutral and relocated (R1, R2) games are out.
"""
import numpy as np
import pandas as pd
import r2_lib as L
import contextlib, io
with contextlib.redirect_stdout(io.StringIO()):
    import r2_leads as LD     # its frames are reused; its own tables are printed by r2_leads.py

print("\n## r2_leads2.py\n")
g = LD.g
cb = LD.cb
q = LD.q
dt = LD.dt
b15 = L.board_at(q, dt["15utc"].dropna())
ok = g[g.grp.isin(["own country", "own country, attendance 1-999", "own country, attendance missing (0)"])]
okid = set(ok.game_id)


def modal(d):
    out = {}
    for gid, x in d.groupby("game_id"):
        vc = x.line.value_counts()
        top = sorted(vc[vc == vc.max()].index, key=lambda v: (abs(v - x.line.median()), v))
        out[gid] = top[0]
    return d[d.line == d.game_id.map(out)]


def spread_sides(board, book):
    b = board[(board.market == "spreads") & board.game_id.isin(okid)]
    if book == "best decidable":
        d = modal(b[b.bookmaker.isin(L.DECIDABLE)])
        z = L.sides_long(d)
        z["dz"] = L.dec(z.price)
        return z.sort_values(["game_id", "side", "dz"], ascending=[True, True, False]).drop_duplicates(["game_id", "side"])
    return L.sides_long(b[b.bookmaker == book])


SETS = {"DraftKings close": spread_sides(cb, "draftkings"),
        "best decidable close": spread_sides(cb, "best decidable"),
        "DraftKings 15utc": spread_sides(b15, "draftkings")}


def block(name, sel, extra_rows=True):
    rows = []
    for where, z in SETS.items():
        x = L.grade(sel(z))
        r = L.row({"rule": name, "prices": where, "subset": "all 2021-22 on"}, x)
        rows.append(r)
        if not extra_rows or where != "DraftKings close":
            continue
        for s, xs in x.groupby("season"):
            rows.append(L.row({"rule": name, "prices": where, "subset": f"season {int(s)}"}, xs))
        med = x.groupby("season").game_date.transform(lambda d: sorted(d)[len(d) // 2])
        rows.append(L.row({"rule": name, "prices": where, "subset": "early half of each season"}, x[x.game_date < med]))
        rows.append(L.row({"rule": name, "prices": where, "subset": "late half of each season"}, x[x.game_date >= med]))
        best = x.groupby("game_date").units.sum().sort_values(ascending=False).head(10).index
        rows.append(L.row({"rule": name, "prices": where, "subset": "without its 10 best dates"}, x[~x.game_date.isin(best)]))
        rows.append(L.row({"rule": name, "prices": where, "subset": f"price median {x.price.median():.0f}, range {x.price.min():.0f} to {x.price.max():.0f}"}, x.iloc[0:0]))
    return rows


rows = []
# H3 neighbourhood
for thr, lab in ((0.0, "home line > 0"), (1.5, "home line >= +1.5"), (3.0, "home line >= +3"), (5.0, "home line >= +5")):
    f = (lambda t: (lambda z: z[(z.side == "home") & ((z.line > t) if t == 0 else (z.line >= t))]))(thr)
    rows += block(f"H3 home underdog ATS, {lab}", f, extra_rows=(thr == 0.0))
rows += block("H3 mirror: the away favourite ATS (away line < 0)", lambda z: z[(z.side == "away") & (z.line < 0)], extra_rows=False)
rows += block("control: home ATS, every game", lambda z: z[z.side == "home"], extra_rows=False)
print("### H3, the home underdog against the spread (blind)\n")
print(L.md_table(pd.DataFrame(rows)))

# H3 walk-forward bucket rule
bins = [-99, -10, -5, -1.5, 1.5, 5, 99]
hh = LD.h.copy()
hh["line_used"] = hh.pin_line.fillna(hh.dk_line)
hh["bucket"] = pd.cut(hh.line_used, bins, right=False, labels=False)
rows = []
for where, z in SETS.items():
    z = z[z.side == "home"].copy()
    z["bucket"] = pd.cut(z.line, bins, right=False, labels=False)
    picks = []
    for s in sorted(z.season.unique()):
        if s < 2023:
            continue
        prior = hh[hh.season < s].groupby("bucket").res.mean()
        good = set(prior[prior > 0].index)
        picks.append(z[(z.season == s) & z.bucket.isin(good)])
    x = L.grade(pd.concat(picks))
    rows.append(L.row({"rule": "H3 walk-forward: home in buckets positive over every earlier season", "prices": where, "subset": "2022-23 on"}, x))
    if where == "DraftKings close":
        for s, xs in x.groupby("season"):
            rows.append(L.row({"rule": "H3 walk-forward", "prices": where, "subset": f"season {int(s)}"}, xs))
print("\n### H3 walk-forward (buckets chosen from earlier seasons only)\n")
print(L.md_table(pd.DataFrame(rows)))

# H2 attendance
P = LD.P.copy()
att = P[["game_id", "season", "prev_att"]].dropna()
for lab, qn in (("top tercile", 2 / 3), ("top half", 0.5), ("top quartile", 0.75)):
    thr = att.groupby("season").prev_att.transform(lambda v: v.quantile(qn))
    att[lab] = att.prev_att >= thr
att["bottom tercile"] = att.prev_att <= att.groupby("season").prev_att.transform(lambda v: v.quantile(1 / 3))
rows = []
for lab in ("top tercile", "top half", "top quartile"):
    ids = set(att.game_id[att[lab]])
    rows += block(f"H2 home ATS, previous-season attendance {lab}", (lambda I: (lambda z: z[(z.side == "home") & z.game_id.isin(I)]))(ids),
                  extra_rows=(lab == "top tercile"))
ids = set(att.game_id[att["bottom tercile"]])
rows += block("H2 mirror: away ATS, previous-season attendance bottom tercile", lambda z: z[(z.side == "away") & z.game_id.isin(ids)],
              extra_rows=True)
print("\n### H2, home against the spread by the club's previous-season attendance (blind)\n")
print(L.md_table(pd.DataFrame(rows)))

# overlap of H2 and H3
top = set(att.game_id[att["top tercile"]])
dk = SETS["DraftKings close"]
hd = set(dk.game_id[(dk.side == "home") & (dk.line > 0)])
print(f"\nOverlap at the DraftKings close: home-underdog games {len(hd)}, top-tercile attendance games {len(top & set(dk.game_id))}, both {len(hd & top)}.")
