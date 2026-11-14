"""One row per UFC fight with pre-fight (as-of) features. Nothing in a row uses
the fight itself or anything after it.

Inputs: fight_log.parquet (two rows per fight), fighters.parquet.
Output: fights.parquet, oriented A = lexicographically smaller slug.
"""
import math, re, unicodedata
from collections import defaultdict
import numpy as np
import pandas as pd

FL = pd.read_parquet("fight_log.parquet")
FT = pd.read_parquet("fighters.parquet").set_index("fighter_id")
for c in ("end_round", "end_time_sec", "scheduled_rounds", "knockdowns", "sig_strikes_landed",
          "sig_strikes_attempted", "sig_strikes_absorbed", "takedowns_landed", "takedowns_attempted",
          "sub_attempts", "control_time_sec", "is_title_fight"):
    FL[c] = pd.to_numeric(FL[c], errors="coerce")


def slugify(n):
    n = unicodedata.normalize("NFKD", str(n)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")


FL["date"] = pd.to_datetime(FL.game_date)
FL = FL.sort_values(["date", "game_id", "log_id"])
FL["mins"] = ((FL.end_round - 1) * 300 + FL.end_time_sec) / 60.0

# Elo (K by fights so far), per fighter, updated after each fight
K0 = 64.0
elo = defaultdict(lambda: 1500.0)
n_f = defaultdict(int)
hist = defaultdict(list)       # fighter_id -> list of dicts of past fights

rows = []
for gid, g in FL.groupby("game_id", sort=False):
    if len(g) != 2:
        continue
    a, b = g.iloc[0], g.iloc[1]
    if slugify(a.fighter_name) > slugify(b.fighter_name):
        a, b = b, a
    d = a.date
    feat = dict(game_id=gid, date=d, season=int(a.season), event=a.event_name,
                weight_class=a.weight_class, title=a.is_title_fight,
                sched=a.scheduled_rounds, a_id=a.fighter_id, b_id=b.fighter_id,
                a_name=a.fighter_name, b_name=b.fighter_name,
                result_a=a.result, method=a.method, end_round=a.end_round,
                end_time=a.end_time_sec)
    for side, f in (("a", a), ("b", b)):
        fid = f.fighter_id
        h = hist[fid]
        feat[f"{side}_elo"] = elo[fid]
        feat[f"{side}_n"] = len(h)
        if h:
            H = pd.DataFrame(h)
            feat[f"{side}_days_off"] = (d - H.date.iloc[-1]).days
            feat[f"{side}_win_rate"] = (H.result == "win").mean()
            feat[f"{side}_fin_rate"] = (H.method.isin(["ko_tko", "submission"])).mean()   # fights that ended early
            feat[f"{side}_ko_win"] = ((H.result == "win") & (H.method == "ko_tko")).mean()
            feat[f"{side}_sub_win"] = ((H.result == "win") & (H.method == "submission")).mean()
            feat[f"{side}_ko_loss"] = ((H.result == "loss") & (H.method == "ko_tko")).mean()
            feat[f"{side}_dec_rate"] = (H.method == "decision").mean()
            mins = H.mins.sum()
            feat[f"{side}_mins"] = mins
            feat[f"{side}_slpm"] = H.sig_strikes_landed.sum() / mins if mins else np.nan
            feat[f"{side}_sapm"] = H.sig_strikes_absorbed.sum() / mins if mins else np.nan
            feat[f"{side}_td15"] = 15 * H.takedowns_landed.sum() / mins if mins else np.nan
            feat[f"{side}_kd15"] = 15 * H.knockdowns.sum() / mins if mins else np.nan
            feat[f"{side}_sub15"] = 15 * H.sub_attempts.sum() / mins if mins else np.nan
            feat[f"{side}_avg_mins"] = H.mins.mean()
            feat[f"{side}_streak"] = int(np.sign((H.result == "win").astype(int).iloc[-1] - 0.5))
        p = FT.loc[fid] if fid in FT.index else None
        if p is not None:
            dob = pd.to_datetime(p.dob, errors="coerce")
            feat[f"{side}_age"] = (d - dob).days / 365.25 if pd.notna(dob) else np.nan
            feat[f"{side}_reach"] = pd.to_numeric(p.reach_in, errors="coerce")
            feat[f"{side}_height"] = pd.to_numeric(p.height_in, errors="coerce")
            feat[f"{side}_stance"] = p.stance
    rows.append(feat)
    # update after the fight
    ea, eb = elo[a.fighter_id], elo[b.fighter_id]
    pa = 1 / (1 + 10 ** ((eb - ea) / 400))
    sa = {"win": 1.0, "loss": 0.0, "draw": 0.5}.get(a.result)
    if sa is not None:
        ka = K0 / math.sqrt(1 + n_f[a.fighter_id] / 4)
        kb = K0 / math.sqrt(1 + n_f[b.fighter_id] / 4)
        elo[a.fighter_id] = ea + ka * (sa - pa)
        elo[b.fighter_id] = eb - kb * (sa - pa)
    for f in (a, b):
        n_f[f.fighter_id] += 1
        hist[f.fighter_id].append(dict(date=d, result=f.result, method=f.method, mins=f.mins,
                                       sig_strikes_landed=f.sig_strikes_landed,
                                       sig_strikes_absorbed=f.sig_strikes_absorbed,
                                       takedowns_landed=f.takedowns_landed,
                                       knockdowns=f.knockdowns, sub_attempts=f.sub_attempts))

F = pd.DataFrame(rows)
F["women"] = F.weight_class.str.contains("Women", case=False, na=False)
F["rounds_done"] = (F.end_round - 1) + F.end_time / 300.0
F["finished"] = F.method.isin(["ko_tko", "submission"])
F.to_parquet("fights.parquet")
print(len(F), "fights", F.date.min().date(), F.date.max().date())
print(F.groupby(F.date.dt.year).finished.mean().round(3).to_string())
