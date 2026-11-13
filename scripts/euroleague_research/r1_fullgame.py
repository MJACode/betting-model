"""Round 1: full-game numbers at each period-quote mark.

  (A) 2025-26 only: the purchase spool. For each played game and mark, the
      latest spool snapshot at or before the mark's ask time (tip - mark)
      that holds the event, up to 2 hours back. From that ONE snapshot: the
      median over the decidable US books (draftkings, fanduel, betmgm,
      betrivers, fanatics) of the main full-game total and home spread; the
      same over every book in the snapshot; and Pinnacle's own main line.
      Feed names map through config.EUROLEAGUE_ODDS_API_MAP; an event is
      the game's unordered club pair with the nearest start within 30 hours;
      a home spread is read off the outcome named for EuroLeague's home club,
      so a feed that swaps home and away is corrected.
  (B) Every season: Pinnacle's full-game alternate ladders from the same
      per-event fetch as the period quote. The fair number is where the
      ladder's no-vig over (home cover) probability crosses 0.5, linear
      between the two rungs that bracket it.

Writes C:\\Users\\micha\\AppData\\Local\\Temp\\el_r1\\fullgame.parquet (a
temporary working copy; deleted at the end of the round).

    python scripts/euroleague_research/r1_fullgame.py
"""
import gzip
import json
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, r"C:\Users\micha\documents\bm-euroleague-fix")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config  # noqa: E402  (no .env exists in this checkout; only the name map is read)
import r1_lib as L  # noqa: E402

OUT = Path(r"C:\Users\micha\AppData\Local\Temp\el_r1\fullgame.parquet")
NAMES = dict(config.EUROLEAGUE_ODDS_API_MAP)
US = ["draftkings", "fanduel", "betmgm", "betrivers", "fanatics"]

g = L.load_games()
g = g[g.played]

# ── (B) Pinnacle ladders, every season ───────────────────────────────────────
q = pd.read_parquet(L.CACHE / "period_quotes.parquet")
q = q[(q.bookmaker == "pinnacle") & q.market.isin(["alternate_totals", "alternate_spreads"])].copy()


def ladder_fair(x: pd.DataFrame, col: str, a: str, b: str) -> float:
    pa = L.imp(x[a]) / (L.imp(x[a]) + L.imp(x[b]))
    x = x.assign(pa=pa).sort_values(col)
    # over prob falls as the total rises; home-cover prob rises as the home number rises
    v = x[col].to_numpy(float)
    p = x["pa"].to_numpy(float)
    for i in range(len(v) - 1):
        lo, hi = p[i], p[i + 1]
        if (lo - 0.5) * (hi - 0.5) <= 0 and lo != hi:
            return float(v[i] + (0.5 - lo) * (v[i + 1] - v[i]) / (hi - lo))
    return np.nan


rows = []
for (gid, mark), x in q.groupby(["game_id", "mark"]):
    t = x[x.market == "alternate_totals"]
    s = x[x.market == "alternate_spreads"]
    rows.append({"game_id": gid, "mark": mark,
                 "pin_total": ladder_fair(t, "total_line", "over_price", "under_price") if len(t) else np.nan,
                 "pin_spread": ladder_fair(s, "spread_home", "home_price", "away_price") if len(s) else np.nan})
pin = pd.DataFrame(rows)
print("Pinnacle ladder fair numbers:", len(pin), "(game, mark) rows; totals found",
      int(pin.pin_total.notna().sum()), "spreads found", int(pin.pin_spread.notna().sum()))

# ── (A) the spool, 2025-26 only ──────────────────────────────────────────────
files = {}
for d in sorted(L.SPOOL.iterdir()):
    if not d.is_dir() or not ("20250901" <= d.name <= "20260531"):
        continue
    for f in d.glob("*.json.gz"):
        ts = datetime.strptime(f.name.split(".")[0], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        files[ts] = f
stamps = np.array(sorted(files))
print("spool files 2025-09-01..2026-05-31:", len(stamps))


def fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()


@lru_cache(maxsize=256)
def snapshot(ts):
    d = json.loads(gzip.open(files[ts]).read().decode("utf-8"))
    return d.get("data") or []


unmapped = set()


def code(name):
    c = NAMES.get(name)
    if c is None:
        unmapped.add(name)
    return c


def read_event(ev, home, away):
    """One event -> per-book main lines with EuroLeague's home as home."""
    out = []
    for b in ev.get("bookmakers", []):
        rec = {"book": b["key"]}
        for m in b.get("markets", []):
            oc = m.get("outcomes", [])
            if m["key"] == "totals":
                ov = [o for o in oc if o.get("name") == "Over"]
                un = [o for o in oc if o.get("name") == "Under"]
                if ov and un and ov[0].get("point") is not None:
                    rec["total"] = float(ov[0]["point"])
                    rec["over_price"], rec["under_price"] = ov[0]["price"], un[0]["price"]
            elif m["key"] == "spreads":
                h = [o for o in oc if code(o.get("name")) == home]
                a = [o for o in oc if code(o.get("name")) == away]
                if h and a and h[0].get("point") is not None:
                    rec["spread"] = float(h[0]["point"])
                    rec["sh_price"], rec["sa_price"] = h[0]["price"], a[0]["price"]
            elif m["key"] == "h2h":
                h = [o for o in oc if code(o.get("name")) == home]
                a = [o for o in oc if code(o.get("name")) == away]
                if h and a:
                    rec["ml_home"], rec["ml_away"] = h[0]["price"], a[0]["price"]
        out.append(rec)
    return out


targets = []
gs = g[g.season == 2026]
for _, r in gs.iterrows():
    for mk, mins in L.MARK_MIN.items():
        targets.append((r.game_id, mk, r.tip, r.tip - timedelta(minutes=mins), r.home_code, r.away_code))

recs = []
for gid, mk, tip, ask, home, away in targets:
    i = np.searchsorted(stamps, ask.to_pydatetime(), side="right") - 1
    found = None
    while i >= 0 and stamps[i] >= ask.to_pydatetime() - timedelta(hours=2):
        ts = stamps[i]
        best = None
        for ev in snapshot(ts):
            pair = {code(ev.get("home_team")), code(ev.get("away_team"))}
            if pair != {home, away}:
                continue
            ct = datetime.strptime(ev["commence_time"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            gap = abs((ct - tip.to_pydatetime()).total_seconds())
            if gap <= 30 * 3600 and (best is None or gap < best[0]):
                best = (gap, ev)
        if best is not None:
            found = (ts, best[1])
            break
        i -= 1
    if found is None:
        recs.append({"game_id": gid, "mark": mk})
        continue
    ts, ev = found
    books = pd.DataFrame(read_event(ev, home, away))
    rec = {"game_id": gid, "mark": mk, "fg_snap": ts, "fg_snap_lead_min": (tip.to_pydatetime() - ts).total_seconds() / 60,
           "feed_swapped": code(ev.get("home_team")) != home}
    for tag, sel in [("us", books.book.isin(US)), ("all", books.book.notna())]:
        b = books[sel]
        for c in ["total", "spread"]:
            v = b[c].dropna() if c in b else pd.Series(dtype=float)
            rec[f"{c}_{tag}"] = float(v.median()) if len(v) else np.nan
            rec[f"n{c}_{tag}"] = int(len(v))
    p = books[books.book == "pinnacle"]
    for c in ["total", "spread", "over_price", "under_price", "sh_price", "sa_price"]:
        rec[f"pinmain_{c}"] = float(p[c].iloc[0]) if len(p) and c in p and pd.notna(p[c].iloc[0]) else np.nan
    recs.append(rec)

fg = pd.DataFrame(recs)
fg = fg.merge(pin, on=["game_id", "mark"], how="outer")
fg = fg.merge(g[["game_id", "season"]], on="game_id", how="left")
OUT.parent.mkdir(parents=True, exist_ok=True)
fg.to_parquet(OUT, index=False)
print("unmapped feed names:", sorted(unmapped) or "none")
s26 = fg[fg.season == 2026]
print("2025-26 (game, mark) rows:", len(s26), "| with a US-book full-game total:", int(s26.total_us.notna().sum()),
      "| spread:", int(s26.spread_us.notna().sum()), "| feed swapped home/away:", int(s26.feed_swapped.fillna(False).sum()))
print(s26.groupby("mark").agg(rows=("game_id", "size"), total_us=("total_us", "count"),
                              n_books_med=("ntotal_us", "median"), lead_med=("fg_snap_lead_min", "median"),
                              lead_max=("fg_snap_lead_min", "max")).reindex(L.MARKS).to_string())
both = s26.dropna(subset=["total_us", "pin_total"])
print("US-book full-game total minus Pinnacle ladder fair total (same mark), 2025-26:",
      both.assign(d=both.total_us - both.pin_total).d.describe().round(3).to_dict())
both = s26.dropna(subset=["spread_us", "pin_spread"])
print("US-book home spread minus Pinnacle ladder fair spread:",
      both.assign(d=both.spread_us - both.pin_spread).d.describe().round(3).to_dict())
both = s26.dropna(subset=["pinmain_total", "pin_total"])
print("Pinnacle main total (spool) minus Pinnacle ladder fair total (cache):",
      both.assign(d=both.pinmain_total - both.pin_total).d.describe().round(3).to_dict())
