"""How far behind a basket each NCAAB in-play source runs, and how long a
DraftKings live line stays up. Every read is stored in Supabase
(live_latency_probe), the cache file beside it is only a cache.

    python -m scripts.ncaab_live_latency_probe espn     --run R --date 2026-11-12 --secs 1200
    python -m scripts.ncaab_live_latency_probe dk       --run R --date 2026-11-12 --secs 1500
    python -m scripts.ncaab_live_latency_probe provider --run R --secs 360     # 2 credits a call
    python -m scripts.ncaab_live_latency_probe import   --run R --probe espn FILE
    python -m scripts.ncaab_live_latency_probe report   --run R

espn      ESPN's D-I scoreboard every 2.5 s and the summaries of up to 16 live
          games in turn (each play's wallclock, the summary's header score).
dk        DraftKings' own NCAAB league board (score, clock, main spread and
          total of each live game) every 2.5 s, plus ESPN's scoreboard and
          scoring plays for matching. DraftKings answers a residential address
          with a browser TLS fingerprint and refuses the Railway worker
          (docs/live_odds_freshness.md, measured 2026-08-31), so this runs on
          mike's machine.
provider  The odds provider's DraftKings NCAAB spreads and totals, every 10 s
          (x-requests-last 2), to pair with the dk run's board.

Each collector writes JSON lines to a cache file under %TEMP% and imports the
file into live_latency_probe at the end of the run (and on Ctrl-C), keyed
(run_id, probe, line_no): a re-import writes nothing already stored.

First run, 2026-11-12 23:5x-00:4x UTC (run 2026-11-12-ncaab), opened by
Indiana -16.5 (live), posted 3 min 15 s after its fetch while DraftKings showed
-22.5: docs/sports/ncaab.md, "In play", and the session log.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SB = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
SUM = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary"
DK = "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusoh/v1/leagues/92483"
DK_BOOT = "https://sportsbook.draftkings.com/leagues/basketball/ncaab"
PROVIDER = "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds"
UA = {"User-Agent": "Mozilla/5.0"}
TABLE = "live_latency_probe"


# ─── storage ──────────────────────────────────────────────────────────────────

def import_file(run_id: str, probe: str, path: Path) -> int:
    """Every JSON line of `path` into live_latency_probe; returns rows written."""
    from data.db import get_connection
    rows = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            if not line.strip():
                continue
            r = json.loads(line)
            t = r.get("t1") or r.get("t0")
            at = datetime.fromtimestamp(float(t), tz=timezone.utc) if t else None
            rows.append((run_id, probe, i, str(r.get("k")), at, json.dumps(r)))
    conn = get_connection()
    written = 0
    try:
        for k in range(0, len(rows), 1000):
            chunk = rows[k:k + 1000]
            before = conn.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE run_id = %s AND probe = %s",
                                  (run_id, probe)).fetchone()[0]
            conn.executemany(f"INSERT INTO {TABLE} (run_id, probe, line_no, kind, read_at, payload) "
                             f"VALUES (%s, %s, %s, %s, %s, %s::jsonb) "
                             f"ON CONFLICT (run_id, probe, line_no) DO NOTHING", chunk)
            conn.commit()
            after = conn.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE run_id = %s AND probe = %s",
                                 (run_id, probe)).fetchone()[0]
            written += int(after) - int(before)
    finally:
        conn.close()
    return written


FROM_CACHE = False                    # report --cache: read the cache files, not Supabase


def load(run_id: str, probe: str) -> list[dict]:
    if FROM_CACHE:
        with open(cache_path(run_id, probe), encoding="utf-8") as f:
            return [json.loads(x) for x in f if x.strip()]
    from data.db import get_connection
    conn = get_connection()
    try:
        rows = conn.execute(f"SELECT payload FROM {TABLE} WHERE run_id = %s AND probe = %s ORDER BY line_no",
                            (run_id, probe)).fetchall()
    finally:
        conn.close()
    return [r[0] if isinstance(r[0], dict) else json.loads(r[0]) for r in rows]


def cache_path(run_id: str, probe: str) -> Path:
    d = Path(tempfile.gettempdir()) / "ncaab_live_latency_probe"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{run_id}_{probe}.jsonl"


# ─── collectors ───────────────────────────────────────────────────────────────

def _espn_scoreboard(sess, date: str, f, t_extra: dict | None = None) -> list:
    t0 = time.time()
    try:
        d = sess.get(SB, params={"dates": date.replace("-", ""), "groups": 50, "limit": 500},
                     headers=UA, timeout=10).json()
    except Exception as exc:                          # noqa: BLE001
        f.write(json.dumps({"k": "sberr", "t0": t0, "err": str(exc)[:200]}) + "\n")
        return []
    t1 = time.time()
    live = []
    for ev in d.get("events") or []:
        st = ev.get("status") or {}
        if (st.get("type") or {}).get("state") != "in":
            continue
        comp = (ev.get("competitions") or [{}])[0]
        cs = {c.get("homeAway"): c for c in comp.get("competitors") or []}
        live.append(ev["id"])
        f.write(json.dumps({"k": "sb", "t0": t0, "t1": t1, "eid": ev["id"],
                            "h": cs.get("home", {}).get("score"), "a": cs.get("away", {}).get("score"),
                            "hl": (cs.get("home", {}).get("team") or {}).get("location"),
                            "al": (cs.get("away", {}).get("team") or {}).get("location"),
                            "per": st.get("period"), "clk": st.get("displayClock")}) + "\n")
    return live


def _espn_summary(sess, eid, f, seen: set, all_plays: bool) -> None:
    t0 = time.time()
    try:
        d = sess.get(SUM, params={"event": eid}, headers=UA, timeout=10).json()
    except Exception:                                 # noqa: BLE001
        return
    t1 = time.time()
    hdr = ((d.get("header") or {}).get("competitions") or [{}])[0]
    sc = {c.get("homeAway"): c.get("score") for c in hdr.get("competitors") or []}
    f.write(json.dumps({"k": "sh", "t0": t0, "t1": t1, "eid": eid, "h": sc.get("home"), "a": sc.get("away")}) + "\n")
    for p in d.get("plays") or []:
        pid = p.get("id")
        if pid in seen or not (all_plays or p.get("scoringPlay")):
            continue
        seen.add(pid)
        f.write(json.dumps({"k": "pl", "t0": t0, "t1": t1, "eid": eid, "pid": pid, "wc": p.get("wallclock"),
                            "sp": bool(p.get("scoringPlay")), "h": p.get("homeScore"), "a": p.get("awayScore"),
                            "per": (p.get("period") or {}).get("number"),
                            "clk": (p.get("clock") or {}).get("displayValue")}) + "\n")


def dk_rows(d: dict) -> list[dict]:
    """Each STARTED event of DraftKings' league board: score (first team = away),
    clock, and the main spread and total selections (label, points, American)."""
    evs = {e["id"]: e for e in d.get("events") or [] if e.get("status") == "STARTED"}
    mk = {}
    for m in d.get("markets") or []:
        nm = (m.get("name") or "").lower()
        if m.get("eventId") in evs and nm in ("spread", "total", "point spread", "total points"):
            mk[m["id"]] = (m["eventId"], "spread" if "spread" in nm else "total")
    lines: dict = {}
    for s in d.get("selections") or []:
        k = mk.get(s.get("marketId"))
        if k:
            lines.setdefault(k, []).append((s.get("label"), s.get("points"),
                                            (s.get("displayOdds") or {}).get("american")))
    out = []
    for eid, e in evs.items():
        sc = ((e.get("eventScorecard") or {}).get("mainScorecard") or {})
        lg = e.get("liveGameState") or {}
        out.append({"eid": eid, "name": e.get("name"), "s1": sc.get("firstTeamScore"),
                    "s2": sc.get("secondTeamScore"), "per": lg.get("period"), "gt": lg.get("gameTime"),
                    "run": lg.get("isClockRunning"), "spread": lines.get((eid, "spread")),
                    "total": lines.get((eid, "total"))})
    return out


def collect(kind: str, run_id: str, date: str, secs: float) -> Path:
    import requests
    path = cache_path(run_id, kind)
    end = time.time() + secs
    es = requests.Session()
    dk = None
    if kind == "dk":
        from curl_cffi import requests as cr
        dk = cr.Session(impersonate="chrome124")
        try:
            dk.get(DK_BOOT, timeout=15)
        except Exception:                             # noqa: BLE001
            pass
    key = None
    if kind == "provider":
        import config
        key = config.ODDS_API_KEY
        if not key:
            raise SystemExit("ODDS_API_KEY is not set")
    seen: set = set()
    live, rr, last_sb, last_dk, calls = [], 0, 0.0, 0.0, 0
    with open(path, "a", encoding="utf-8") as f:
        try:
            while time.time() < end:
                now = time.time()
                if kind == "provider":
                    t0 = time.time()
                    r = es.get(PROVIDER, params={"apiKey": key, "bookmakers": "draftkings",
                                                 "markets": "spreads,totals", "oddsFormat": "american"}, timeout=15)
                    t1 = time.time()
                    calls += 1
                    f.write(json.dumps({"k": "hdr", "t0": t0, "t1": t1, "code": r.status_code,
                                        "last": r.headers.get("x-requests-last"),
                                        "remaining": r.headers.get("x-requests-remaining")}) + "\n")
                    if r.status_code == 200:
                        for ev in r.json():
                            for bk in ev.get("bookmakers") or []:
                                for m in bk.get("markets") or []:
                                    f.write(json.dumps({"k": "oa", "t1": t1, "id": ev["id"], "home": ev["home_team"],
                                                        "away": ev["away_team"], "commence": ev.get("commence_time"),
                                                        "market": m["key"], "lu": m.get("last_update"),
                                                        "out": [(o.get("name"), o.get("point"), o.get("price"))
                                                                for o in m.get("outcomes") or []]}) + "\n")
                    f.flush()
                    time.sleep(max(0.0, 10.0 - (time.time() - t0)))
                    continue
                if dk is not None and now - last_dk >= 2.5:
                    last_dk = now
                    t0 = time.time()
                    try:
                        r = dk.get(DK, timeout=10)
                        t1 = time.time()
                        if r.status_code == 200:
                            for row in dk_rows(r.json()):
                                f.write(json.dumps({"k": "dk", "t0": t0, "t1": t1, **row}) + "\n")
                        else:
                            f.write(json.dumps({"k": "dkerr", "t0": t0, "code": r.status_code}) + "\n")
                    except Exception as exc:  # noqa: BLE001
                        f.write(json.dumps({"k": "dkerr", "t0": t0, "err": str(exc)[:200]}) + "\n")
                if now - last_sb >= 2.5:
                    last_sb = now
                    live = _espn_scoreboard(es, date, f)[:16]
                if live:
                    _espn_summary(es, live[rr % len(live)], f, seen, all_plays=(kind == "espn"))
                    rr += 1
                f.flush()
                time.sleep(0.2)
        except KeyboardInterrupt:
            pass
    n = import_file(run_id, kind, path)
    print(f"{kind}: {n} new rows in {TABLE} (run {run_id}); cache {path}")
    return path


# ─── the report ───────────────────────────────────────────────────────────────

def _ts(s: str) -> float:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def _norm(s) -> str:
    return re.sub(r"[^a-z]", "", (s or "").lower().replace("state", "st").replace("saint", "st"))


def _pct(v) -> str:
    import numpy as np
    v = np.asarray(v, dtype=float)
    if not len(v):
        return "n=0"
    return (f"n={len(v)} min {v.min():.1f} p10 {np.percentile(v, 10):.1f} median {np.median(v):.1f} "
            f"p90 {np.percentile(v, 90):.1f} p99 {np.percentile(v, 99):.1f} max {v.max():.1f}")


def first_at(series: list, h: int, a: int, after: float, hk="h", ak="a"):
    for r in series:
        try:
            if r["t1"] >= after and int(r[hk]) >= h and int(r[ak]) >= a:
                return r["t1"]
        except (TypeError, ValueError, KeyError):
            continue
    return None


def report(run_id: str) -> dict:
    """The numbers quoted in the 2026-11-12 session log, recomputed from Supabase."""
    out: dict = {}
    # 1. ESPN's three surfaces, from the espn run: each scoring play first seen
    #    after its game's first summary read (no backlog), against its wallclock.
    rows = load(run_id, "espn")
    sb, sh, first_sum, plays = defaultdict(list), defaultdict(list), {}, []
    for r in rows:
        if r["k"] == "sb":
            sb[r["eid"]].append(r)
        elif r["k"] == "sh":
            sh[r["eid"]].append(r)
            first_sum.setdefault(r["eid"], r["t1"])
        elif r["k"] == "pl":
            plays.append(r)
    lag = defaultdict(list)
    for p in plays:
        if not p.get("sp") or not p.get("wc") or p["t1"] <= first_sum.get(p["eid"], 0) + 1e-6:
            continue
        w, h, a = _ts(p["wc"]), int(p["h"]), int(p["a"])
        lag["espn_play_list"].append(p["t1"] - w)
        s1 = first_at(sb[p["eid"]], h, a, w - 120)
        if s1 is not None:
            lag["espn_scoreboard"].append(s1 - w)
        s2 = first_at(sh[p["eid"]], h, a, w - 120)
        if s2 is not None:
            lag["espn_summary_header"].append(s2 - w)
    # 2. DraftKings' own score, its line-vs-score order, and line survival, from the dk run.
    rows = load(run_id, "dk")
    dk, loc, dplays, dfirst = defaultdict(list), {}, {}, {}
    for r in rows:
        if r["k"] == "dk":
            dk[r["eid"]].append(r)
        elif r["k"] == "sb":
            loc[r["eid"]] = (r.get("al"), r.get("hl"))
        elif r["k"] == "pl":
            dfirst.setdefault(r["eid"], r["t1"])
            dplays.setdefault(r["pid"], r)
    match = {}
    for e, (al, hl) in loc.items():
        for d, rs in dk.items():
            nm = rs[0]["name"] or ""
            if "@" in nm:
                aa, hh = [_norm(x) for x in nm.split("@", 1)]
                if aa == _norm(al) and hh == _norm(hl):
                    match[e] = d
    order = []
    for p in dplays.values():
        d = match.get(p["eid"])
        if not d or not p.get("wc") or p["t1"] <= dfirst.get(p["eid"], 0):
            continue
        w, h, a = _ts(p["wc"]), int(p["h"]), int(p["a"])
        rs = dk[d]
        t = [r["t1"] for r in rs]
        i = bisect_left(t, w)
        if i == 0 or i >= len(rs):
            continue
        try:
            if int(rs[i - 1]["s2"]) >= h and int(rs[i - 1]["s1"]) >= a:
                continue                              # DraftKings showed it before the wallclock
        except (TypeError, ValueError):
            continue
        s_at = first_at(rs[i:], h, a, w, hk="s2", ak="s1")
        if s_at is not None and s_at - w <= 60:
            lag["dk_score"].append(s_at - w)
        key0, l_at = json.dumps(rs[i - 1].get("spread")), None
        for r in rs[i:]:
            if r["t1"] - w > 60:
                break
            if json.dumps(r.get("spread")) != key0:
                l_at = r["t1"]
                break
        if s_at is not None and l_at is not None and s_at - w <= 60:
            order.append(l_at - s_at)
    for k, v in lag.items():
        out[k] = _pct(v)
    import numpy as np
    o = np.asarray(order)
    out["dk_line_vs_own_score"] = (f"baskets {len(o)}: line moved before DraftKings' score {int(np.sum(o < -0.5))}, "
                                   f"same read {int(np.sum(np.abs(o) <= 0.5))}, after {int(np.sum(o > 0.5))}")
    for mkt in ("spread", "total"):
        surv = []
        for rs in dk.values():
            seq = [(r["t1"], json.dumps(sorted(map(tuple, r[mkt]))) if r.get(mkt) else None) for r in rs]
            for i, (t, k) in enumerate(seq):
                if k is None:
                    continue
                for t2, k2 in seq[i + 1:]:
                    if k2 != k:
                        surv.append(t2 - t)
                        break
        s = np.asarray(surv)
        if len(s):
            out[f"dk_{mkt}_still_up_after"] = ", ".join(f"{x}s {np.mean(s > x):.0%}"
                                                       for x in (10, 20, 30, 60, 90, 120, 180, 240))
    # 3. The provider's DraftKings number against DraftKings' board at the same moment.
    prov = [r for r in load(run_id, "provider") if r["k"] == "oa"]
    names = {eid: rs[0]["name"] for eid, rs in dk.items()}
    same = diff = 0
    ages = []
    for r in prov:
        eid = next((e for e, nm in names.items() if nm and "@" in nm
                    and _norm(r["home"]).startswith(_norm(nm.split("@", 1)[1]))
                    and _norm(r["away"]).startswith(_norm(nm.split("@", 1)[0]))), None)
        if eid is None:
            continue
        rs = dk[eid]
        i = bisect_right([x["t1"] for x in rs], r["t1"]) - 1
        if i < 0 or r["t1"] - rs[i]["t1"] > 6:
            continue
        mk = "spread" if r["market"] == "spreads" else "total"
        board = rs[i].get(mk)
        if not board:
            continue
        if mk == "spread":
            mine = next((pt for n, pt, _ in r["out"] if n == r["home"]), None)
            theirs = board[1][1] if len(board) > 1 else None
        else:
            mine, theirs = (r["out"][0][1] if r["out"] else None), board[0][1]
        if mine is None or theirs is None:
            continue
        if r.get("lu"):
            ages.append(r["t1"] - _ts(r["lu"]))
        if abs(float(mine) - float(theirs)) < 1e-9:
            same += 1
        else:
            diff += 1
    n = same + diff
    out["provider_dk_number_vs_board"] = (f"{n} paired: same {same} ({same / max(n, 1):.0%}), "
                                          f"different {diff} ({diff / max(n, 1):.0%})")
    out["provider_quote_age_live"] = _pct(ages)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("espn", "dk", "provider", "import", "report"))
    ap.add_argument("file", nargs="?")
    ap.add_argument("--run", required=True)
    ap.add_argument("--probe", choices=("espn", "dk", "provider"))
    ap.add_argument("--date", default=datetime.now(timezone.utc).astimezone().date().isoformat())
    ap.add_argument("--secs", type=float, default=1200.0)
    ap.add_argument("--cache", action="store_true", help="report from the cache files (before an import)")
    a = ap.parse_args(argv)
    global FROM_CACHE
    FROM_CACHE = bool(a.cache)
    if a.cmd == "import":
        if not (a.file and a.probe):
            ap.error("import needs --probe and FILE")
        print(f"{import_file(a.run, a.probe, Path(a.file))} new rows")
    elif a.cmd == "report":
        for k, v in report(a.run).items():
            print(f"{k:28s} {v}")
    else:
        collect(a.cmd, a.run, a.date, a.secs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
