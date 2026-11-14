"""UFC prop prices joined to results: props.parquet, one row per (fight,
book, prop, fighter, side) priced on BestFightOdds' event page, with how it
settled. Reads the local mirror's copies of ufc_prop_history and
ufc_prop_history_fights (data/ingestors/ufc_prop_history.py) and the study's
fights.parquet / fight_log.parquet. Run from the study folder.

SETTLEMENT (docs/ufc_market_audit.md section 5):
  * A no contest and an overturned result void every prop on the fight.
  * A disqualification or a "could not continue" stoppage (20 fights from
    2021-06) is not graded on the method and round props: books split on
    whether it is a TKO. `odd_end` marks them, and `won_as_tko` holds the
    grade if it is counted as a TKO, for the sensitivity row. Props that
    depend only on time (goes the distance, round totals, starts round N)
    and the fight winner are graded on them as usual.
  * A draw: the fight winner is void; "goes to decision" wins; every
    fighter-method and round prop loses.
  * Round totals settle on elapsed time: over N.5 rounds needs more than
    N rounds and 2:30; exactly 2:30 is a push (void).
"""
import glob

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

from _paths import MIRROR

DECIDING = {22: "draftkings", 21: "fanduel", 23: "betmgm", 24: "williamhill_us", 25: "betrivers"}


def mirror(t):
    files = glob.glob(f"{MIRROR}\\public.{t}\\*.parquet")
    if not files:
        raise SystemExit(f"public.{t} is not in the local mirror ({MIRROR})")
    return ds.dataset(files, format="parquet").to_table().to_pandas()


P = mirror("ufc_prop_history")
F = mirror("ufc_prop_history_fights")
F = F[F.game_id.notna()]
X = pd.read_parquet("fights.parquet").set_index("game_id")
FL = pd.read_parquet("fight_log.parquet")
detail = FL.groupby("game_id").method_detail.first()

F = F[F.game_id.isin(X.index)].copy()
fx = X.loc[F.game_id]
F["f1_is_a"] = (F.fighter1_id.to_numpy() == fx.a_id.to_numpy())
ok = F.f1_is_a | (F.fighter1_id.to_numpy() == fx.b_id.to_numpy())
F = F[ok.to_numpy()]
fx = X.loc[F.game_id]

res = fx.result_a.to_numpy()
meth = fx.method.to_numpy()
det = detail.reindex(F.game_id).fillna("").to_numpy()
f1a = F.f1_is_a.to_numpy()
# the winner as fighter number 1 / 2 (0 = none)
a_won, b_won = res == "win", res == "loss"
F["winner"] = np.where(a_won, np.where(f1a, 1, 2), np.where(b_won, np.where(f1a, 2, 1), 0))
F["draw"] = res == "draw"
F["void"] = (res == "nc") | (det == "Overturned")
F["odd_end"] = (meth == "dq") | (det == "Could Not Continue")
F["how"] = np.select([meth == "ko_tko", meth == "submission", meth == "decision"],
                     ["ko", "sub", "dec"], "other")
F["detail"] = det
F["end_round"] = fx.end_round.to_numpy()
F["elapsed"] = (fx.end_round.to_numpy() - 1) * 300 + fx.end_time.to_numpy()
F["sched"] = fx.sched.to_numpy()
F["year"] = pd.to_datetime(F.event_date).dt.year
F = F.set_index("matchup_id")


def settle(df, as_tko=False):
    """1 won / 0 lost / NaN void, for each priced row of df (joined to F)."""
    pt, tn, side = df.prop_type.to_numpy(), df.team.to_numpy(), df.side.to_numpy()
    w, how, er = df.winner.to_numpy(), df.how.to_numpy().copy(), df.end_round.to_numpy()
    if as_tko:
        how = np.where(df.odd_end.to_numpy(), "ko", how)
    inside = np.isin(how, ["ko", "sub"])
    x_won = (w == tn) & (tn > 0)
    el = df.elapsed.to_numpy()
    out = np.full(len(df), np.nan)

    def put(mask, yes):
        nonlocal out
        val = np.where(side == 1, yes, ~yes).astype(float)
        out = np.where(mask, val, out)

    out = np.where(pt == 0, (w == side).astype(float), out)    # fight winner: side = fighter
    put(pt == 1, how == "dec")                                   # goes the distance
    for n in (2, 3, 4, 5):
        put(pt == n, er >= n)                                    # fight starts round n
    put(pt == 6, df.draw.to_numpy())
    put(pt == 8, x_won & (how == "ko"))
    put(pt == 9, x_won & (how == "sub"))
    put(pt == 10, x_won & inside)
    put(pt == 11, x_won & (how == "dec"))
    det = df.detail.to_numpy()
    put(pt == 18, x_won & (det == "Decision - Unanimous"))
    put(pt == 19, x_won & np.isin(det, ["Decision - Split", "Decision - Majority"]))
    for n in range(1, 6):
        put(pt == 12 + n, x_won & inside & (er == n))            # fighter wins in round n
        put((pt == 21 + n) & (tn == 0), inside & (er == n))      # fight ends in round n
        put(pt == 238 + n, np.isin(how, ["ko"]) & (er == n))     # ends by TKO/KO/DQ in round n
        put(pt == 243 + n, (how == "sub") & (er == n))           # ends by submission in round n
    for pt_ko, pt_sub, n in ((174, 175, 1), (179, 183, 2), (180, 184, 3), (181, 185, 4), (182, 186, 5)):
        put(pt == pt_ko, x_won & (how == "ko") & (er == n))
        put(pt == pt_sub, x_won & (how == "sub") & (er == n))
    put(pt == 187, how == "ko")
    put(pt == 188, how == "sub")
    put(pt == 211, x_won & inside & (er <= 2))
    put((pt == 226) & (tn == 0), inside & (er <= 2))
    sched = df.sched.to_numpy()
    put((pt == 230) & (tn == 0), (how == "dec") | (inside & (er == sched)))
    put(pt == 231, x_won & ((how == "dec") | (inside & (er == sched))))
    for n in (1, 2, 3, 4):                                       # over / under n.5 rounds
        cut = n * 300 + 150
        m = pt == 31 + n
        put(m, el > cut)
        out = np.where(m & (el == cut), np.nan, out)
    # void: no contest / overturned; a draw voids the fight winner
    out = np.where(df.void.to_numpy(), np.nan, out)
    out = np.where((pt == 0) & df.draw.to_numpy(), np.nan, out)
    # a DQ or could-not-continue end is not graded on method / round props
    time_only = np.isin(pt, [0, 1, 2, 3, 4, 5, 6, 32, 33, 34, 35])
    if not as_tko:
        out = np.where(df.odd_end.to_numpy() & ~time_only, np.nan, out)
    return out


# BFO sometimes splits one fight into two matchups when books spell a fighter
# differently ("Aori Qileng" / "Qileng Aori"), each holding other books'
# prices. Fold every matchup placed on a game onto the one with the most
# priced cells, renumbering its fighters to that one's order; where a book
# priced the same prop in both, the main matchup's price is kept.
cells = P.groupby("matchup_id").size()
F["cells"] = cells.reindex(F.index).fillna(0).to_numpy()
main = F.sort_values("cells", ascending=False).reset_index().drop_duplicates("game_id").set_index("game_id")
F["main"] = main.matchup_id.reindex(F.game_id).to_numpy()
flip = F.f1_is_a.to_numpy() != F.f1_is_a.reindex(F["main"]).to_numpy()
F["flip"] = flip
P = P[P.matchup_id.isin(F.index)].copy()
P["src_matchup"], P["src_team"], P["src_side"] = P.matchup_id, P.team, P.side   # the page's own keys
pf = F.flip.reindex(P.matchup_id).to_numpy()
P["is_main"] = P.matchup_id.to_numpy() == F["main"].reindex(P.matchup_id).to_numpy()
P["matchup_id"] = F["main"].reindex(P.matchup_id).to_numpy()
P["team"] = np.where(pf & (P.team > 0), 3 - P.team, P.team)
P["side"] = np.where(pf & (P.prop_type == 0), 3 - P.side, P.side)
P = P.sort_values("is_main", ascending=False).drop_duplicates(
    ["matchup_id", "book_id", "prop_type", "team", "side"]).drop(columns="is_main")
F = F[F.index.isin(F["main"])]

df = P.join(F[["event_date", "year", "game_id", "winner", "draw", "void", "odd_end", "how", "detail",
               "end_round", "elapsed", "sched", "f1_is_a"]], on="matchup_id", how="inner")
df["won"] = settle(df)
df["won_as_tko"] = settle(df, as_tko=True)
df["dec"] = np.where(df.price > 0, 1 + df.price / 100, 1 + 100 / -df.price.clip(upper=-100))
df["deciding"] = df.book_id.isin(DECIDING)
df.to_parquet("props.parquet")
print(f"{len(df):,} priced rows on {df.matchup_id.nunique():,} placed fights "
      f"({F.index.nunique():,} placed, {len(mirror('ufc_prop_history_fights')):,} on the pages); "
      f"graded {df.won.notna().sum():,}")
print(df[df.deciding].groupby(["year", "bookmaker"]).size().unstack().fillna(0).astype(int).to_string())
