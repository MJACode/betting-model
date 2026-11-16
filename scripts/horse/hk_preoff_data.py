"""Hong Kong pre-race pool snapshots, 2016-09-28 to 2018-06-27: the time base,
the joins, and a loader the pre-off studies import.

Reads the nch015 Hong Kong / Singapore scrape (`data/horse/nch015-horserace-data`,
stored in Supabase by `scripts/horse/store_files.py`; the files on disk are a
cache of those rows). Hong Kong rows only.

THE TIME BASE (measured by `python -I scripts/horse/hk_preoff_data.py`, part 1):
  * `capture_time` in live_odds is UTC. `race_time` in races is Hong Kong local
    (UTC+8, no daylight saving). minutes_before_start =
    (race_date + race_time) - (capture_time + 8 h), in minutes.
  * Evidence: with +8 h the first capture showing a race's final win odds is
    1.4 to 10.4 minutes after the listed start in 98% of the 1,483 races with a
    capture after it (median 4.4); no capture taken before the start ever shows
    the final odds; the monthly medians stay between 3.9 and 4.4 minutes across
    21 months. Any other whole-hour offset puts the freeze an hour away.
  * The start is the SCHEDULED start. Odds still move at captures taken up to
    ~5 minutes after it in a quarter of races (late starts), so a decision lead
    under about 2 minutes is not safe: the clock is not pinned tighter than that.

THE CAPTURE SCHEDULE: one capture every 12 minutes from ~24-35 h out, every 6
minutes from ~216 minutes out, every 4 minutes after the start for ~25 minutes.
So `snapshot_at(L)` returns a capture taken L to L+6 minutes before the start.

THE JOINS: one Hong Kong meeting per day, so (race_date, race_no) is the race
key across live_odds, races, all_dividends and performances; horse_no is the
runner key within a race. `race_id` here is an integer in (race_date, race_no)
order, so rows are contiguous per race for `clogit.starts_of`. NEVER join on
`performances.race_id`: it is a within-season race number that repeats.

GRADING:
  * won / placed come from the DIVIDENDS only. performances.final_placing has
    errors (2017-06-21 race 3 lists two winners; the place dividends show its
    2nd and 3rd were not its 2 and 3).
  * win_dec / pla_dec = dividend / 10 (HKJC pays per HK$10). A dead-heat
    dividend is ALREADY split (shown 7.0, paid 3.55; the 10 placers whose
    displayed place odds sit above dividend/10 are exactly the tied placers of
    the 5 dead heats for the last place), so grade a dead-heat runner as
    won = 1 / placed = 1 at the dividend. Do not divide by the number of winners
    again (anz_study.summarise does that for Betfair through n_win; do not
    pass these rows to it with an n_win column). performances.winning_odds on
    a dead-heat winner is the unsplit pool odds.
  * Displayed odds (snapshots, performances.winning_odds) are floor(dividend/10)
    to 0.1 under 10 and to a whole number from 10. performances.winning_odds is
    the final pool odds, capped at 99.
  * places_paid: 3 with 7+ runners, 2 with 4-6, counted when the pool OPENED
    (the first capture), not at the off: one race that opened with 7 and lost
    a runner to a scratch still paid 3, and its final place book / 3 is 1.230
    (/ 2 would be 1.845). So the terms are known at any decision moment. The
    count of place dividends is one more on a dead heat for the last place, so
    never use it as the terms. Final place book / places_paid has median
    1.227, the same as the floored win book.
  * A runner priced at the off and missing from performances still ran: it is a
    losing bet (status 'dnf' when sectional_times has a time for it,
    'no_sections' when it has none; for 10 of the 10 'no_sections' runners with
    a post-off capture the final win book is typical only WITH them in it, so
    they were in the pool at the close). Dropping them inflates any blind return.
  * 27 races have no capture after the start (scraper gaps; 22 of them have no
    capture inside 60 minutes, on 2016-10-01, 2016-10-08 and 2017-05-13).
    final_win_disp is NaN there, and a scratch after the last capture would
    not be seen. snapshot_at's staleness cap drops most of them.
  * 63 of the 91 runners that were priced and then scratched were first shown
    SCR inside 15 minutes of the start or after it (gate withdrawals): a rule
    deciding 5 minutes out bets some of them, and those bets are refunds.
  * The last capture before the start (median 2.6 minutes out) and the final
    odds differ by a median of 21% (|log ratio| 0.214): Hong Kong money is late.
  * A runner SCR in the final capture was scratched: a bet on it is refunded.
    `decision_frame` flags runners priced at the decision and scratched later.

Stake and payout of a pool bet: the stake is chosen at the decision (1 unit to
win at the price on the screen, risk capped at 3) and paid at the dividend.
`pool_bet_units` does that; `anz_study.stake_units` alone uses one price for both.

    python -I scripts/horse/hk_preoff_data.py
"""
from __future__ import annotations

import functools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
from scripts.horse.anz_study import stake_units  # noqa: E402

DATA = ROOT_DIR / "data" / "horse" / "nch015-horserace-data"
CAPTURE_TO_HK = pd.Timedelta(hours=8)   # capture_time is UTC; race_time is HK local
WIN_TAKEOUT = 0.175                     # HKJC win pool
PLACE_TAKEOUT = 0.175                   # HKJC place pool
LEADS = [240, 120, 60, 30, 15, 10, 5, 3, 2, 1]


# ---------------------------------------------------------------- basics

@functools.lru_cache(maxsize=None)
def _read(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / f"{name}.csv.gz", encoding="utf-8", dtype=str)


def season_of(dates) -> np.ndarray:
    """Hong Kong season as its START year (seasons open in September), the
    convention hk_study uses: 2017-06-21 is season 2016 ('2016/2017')."""
    d = pd.to_datetime(pd.Series(dates))
    return np.where(d.dt.month >= 9, d.dt.year, d.dt.year - 1).astype(int)


def season_label(season: int) -> str:
    return f"{int(season)}/{int(season) + 1}"


def unfloor(odds) -> np.ndarray:
    """Midpoint of the interval a floored display price came from: +0.05 under
    10, +0.5 from 10. A modelling choice for implied chances, never a paid price."""
    o = np.asarray(odds, float)
    return np.where(o < 10, o + 0.05, o + 0.5)


def pool_bet_units(stake_price, paid_dec, won, refund=None) -> tuple[np.ndarray, np.ndarray]:
    """(profit, risk) per pool bet. Sized at the decision price with the repo's
    stake (anz_study.stake_units: 1 unit to win, risk 1/(d-1) capped at 3),
    paid at the dividend. A refund (scratched after the bet) is 0 and 0."""
    sp = np.asarray(stake_price, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        _, risk = stake_units(sp, np.zeros(len(sp)), 0.0)
    w = np.asarray(won, float) > 0
    paid = np.asarray(paid_dec, float)
    profit = np.where(w, risk * (paid - 1.0), -risk)
    if refund is not None:
        r = np.asarray(refund, bool)
        profit = np.where(r, 0.0, profit)
        risk = np.where(r, 0.0, risk)
    return profit, risk


# ---------------------------------------------------------------- races

@functools.lru_cache(maxsize=None)
def load_races() -> pd.DataFrame:
    """Every Hong Kong race in races.csv, one row each, with an integer race_id
    in (race_date, race_no) order and the scheduled start in HK time and UTC."""
    r = _read("races")
    r = r[r.race_country == "HK"].copy()
    r["race_date"] = pd.to_datetime(r.race_date.str[:10])
    r["race_no"] = r.race_no.astype(int)
    r = r.sort_values(["race_date", "race_no"]).reset_index(drop=True)
    if r.duplicated(["race_date", "race_no"]).any():
        raise ValueError("races: (race_date, race_no) is not unique for Hong Kong")
    r["race_id"] = np.arange(len(r), dtype=int)
    r["venue"] = r.race_location
    r["start_hk"] = r.race_date + pd.to_timedelta(r.race_time + ":00")
    r["start_utc"] = r.start_hk - CAPTURE_TO_HK
    r["distance"] = pd.to_numeric(r.distance, errors="coerce")
    r["season"] = season_of(r.race_date)
    return r[["race_id", "race_date", "race_no", "venue", "season", "start_hk", "start_utc",
              "race_time", "track", "race_class", "course", "going", "distance", "rating",
              "results_available"]]


@functools.lru_cache(maxsize=None)
def _performances_hk() -> pd.DataFrame:
    p = _read("performances")
    p = p[p.race_country == "HK"].copy()
    p["race_date"] = pd.to_datetime(p.race_date.str[:10])
    p["race_no"] = p.race_no.astype(int)
    p["horse_no"] = pd.to_numeric(p.horse_no, errors="coerce").astype("Int64")
    p["final_placing"] = pd.to_numeric(p.final_placing, errors="coerce")
    p["winning_odds"] = pd.to_numeric(p.winning_odds, errors="coerce")
    p["season_start"] = pd.to_numeric(p.season.str[:4], errors="coerce").astype("Int64")
    return p


def load_performances() -> pd.DataFrame:
    """Hong Kong performances, every year from 1979, typed. For form features
    built from EARLIER races. horse_no is present from 2016-09-28 on;
    `race_id` there is a within-season number: do not join on it."""
    return _performances_hk().copy()


@functools.lru_cache(maxsize=None)
def _sectionals_hk() -> pd.DataFrame:
    s = _read("sectional_times")
    s = s[s.race_country == "HK"].copy()
    s["race_date"] = pd.to_datetime(s.race_date.str[:10])
    s = s[s.race_date >= "2016-09-01"].copy()
    s["race_no"] = s.race_no.astype(int)
    s["horse_no"] = s.horse_no.astype(int)
    s["any_section"] = s.sections_time.map(
        lambda x: isinstance(x, str) and any(e.get("time") for e in json.loads(x)))
    return s


# ---------------------------------------------------------------- snapshots

@functools.lru_cache(maxsize=None)
def _snapshots() -> pd.DataFrame:
    lo = _read("live_odds")
    lo = lo[lo.race_country == "HK"].copy()
    lo["race_date"] = pd.to_datetime(lo.race_date)
    lo["race_no"] = lo.race_no.astype(int)
    lo["capture_utc"] = pd.to_datetime(lo.capture_time)
    races = load_races()
    lo = lo.merge(races[["race_id", "race_date", "race_no", "venue", "season", "start_hk"]],
                  on=["race_date", "race_no"], how="inner")
    lo = lo.sort_values(["race_id", "capture_utc"]).reset_index(drop=True)
    lo["snap_no"] = lo.groupby("race_id").cumcount()
    lo["minutes_before_start"] = (lo.start_hk - (lo.capture_utc + CAPTURE_TO_HK)).dt.total_seconds() / 60
    rid, sn, horse, win, pla = [], [], [], [], []
    for r_, s_, js in zip(lo.race_id.to_numpy(), lo.snap_no.to_numpy(), lo.data.to_numpy()):
        d = json.loads(js)
        w, p = d.get("win") or {}, d.get("pla") or {}
        for h, v in w.items():
            rid.append(r_); sn.append(s_); horse.append(int(h)); win.append(v); pla.append(p.get(h))
    long = pd.DataFrame({"race_id": rid, "snap_no": sn, "horse_no": horse, "win_raw": win, "pla_raw": pla})
    long = long.merge(lo[["race_id", "snap_no", "race_date", "race_no", "venue", "season",
                          "capture_utc", "minutes_before_start"]], on=["race_id", "snap_no"])
    long["capture_hk"] = long.capture_utc + CAPTURE_TO_HK
    long["status"] = np.where(long.win_raw == "SCR", "SCR",
                              np.where(long.win_raw == "---", "---", "priced"))
    long["win_disp"] = pd.to_numeric(long.win_raw, errors="coerce")
    long["pla_disp"] = pd.to_numeric(long.pla_raw, errors="coerce")
    priced = long.status == "priced"
    g = long[priced].assign(q=1.0 / long.win_disp[priced], qm=1.0 / unfloor(long.win_disp[priced]),
                            qp=1.0 / long.pla_disp[priced]) \
        .groupby(["race_id", "snap_no"]).agg(field_priced=("q", "size"), book_win=("q", "sum"),
                                             book_win_mid=("qm", "sum"), book_pla=("qp", "sum"))
    long = long.merge(g.reset_index(), on=["race_id", "snap_no"], how="left")
    long["field_priced"] = long.field_priced.fillna(0).astype(int)
    ident = _identity()
    long = long.merge(ident, on=["race_date", "race_no", "horse_no"], how="left")
    cols = ["race_id", "race_date", "race_no", "venue", "season", "snap_no", "capture_utc",
            "capture_hk", "minutes_before_start", "horse_no", "horse_id", "status", "win_disp",
            "pla_disp", "field_priced", "book_win", "book_win_mid", "book_pla"]
    return long[cols].sort_values(["race_id", "snap_no", "horse_no"]).reset_index(drop=True)


@functools.lru_cache(maxsize=None)
def _identity() -> pd.DataFrame:
    """horse_id per (race_date, race_no, horse_no): performances for finishers,
    sectional_times for scratched and non-finishing runners."""
    p = _performances_hk()
    p = p[p.race_date >= "2016-09-28"][["race_date", "race_no", "horse_no", "horse_id"]].dropna()
    p["horse_no"] = p.horse_no.astype(int)
    s = _sectionals_hk()[["race_date", "race_no", "horse_no", "horse_id"]]
    out = pd.concat([p, s]).drop_duplicates(["race_date", "race_no", "horse_no"], keep="first")
    return out


def load_snapshots() -> pd.DataFrame:
    """One row per (race, capture, horse_no). status is 'priced', 'SCR' (scratched)
    or '---' (no price). win_disp / pla_disp are the floored displayed odds
    (NaN unless priced). minutes_before_start is to the SCHEDULED start; a
    negative value is a capture after it. book_win is sum(1/win_disp) over the
    priced runners of that capture (1/(1-0.175) = 1.212 before flooring)."""
    return _snapshots().copy()


def snapshot_at(lead_minutes: float, max_stale: float | None = None) -> pd.DataFrame:
    """For each race, the last capture taken at least `lead_minutes` before the
    scheduled start, and every runner in it (the field as it stood then).

    snap_lead is that capture's real lead; stale_min = snap_lead - lead_minutes.
    Races whose chosen capture is staler than max_stale are dropped: the default
    is 6.5 minutes inside 210 minutes (6-minute cadence) and 12.5 beyond
    (12-minute cadence), which drops only scraper gaps (e.g. 2016-10-01, whose
    race-day captures are missing). Nothing here is from after the capture."""
    if lead_minutes <= 0:
        raise ValueError("a decision lead must be before the scheduled start (> 0 minutes)")
    if max_stale is None:
        max_stale = 6.5 if lead_minutes < 210 else 12.5
    s = _snapshots()
    caps = s[["race_id", "snap_no", "minutes_before_start"]].drop_duplicates(["race_id", "snap_no"])
    caps = caps[caps.minutes_before_start >= lead_minutes]
    pick = caps.loc[caps.groupby("race_id").minutes_before_start.idxmin()].copy()
    pick["stale_min"] = pick.minutes_before_start - lead_minutes
    pick = pick[pick.stale_min <= max_stale]
    out = s.merge(pick[["race_id", "snap_no", "stale_min"]], on=["race_id", "snap_no"])
    out = out.rename(columns={"minutes_before_start": "snap_lead", "status": "status_at_snap",
                              "win_disp": "win_at_snap", "pla_disp": "pla_at_snap",
                              "field_priced": "field_at_snap", "book_win": "book_at_snap",
                              "book_win_mid": "book_mid_at_snap", "book_pla": "book_pla_at_snap"})
    out["lead_minutes"] = float(lead_minutes)
    return out.sort_values(["race_id", "horse_no"]).reset_index(drop=True)


# ---------------------------------------------------------------- results

@functools.lru_cache(maxsize=None)
def _dividends() -> pd.DataFrame:
    d = _read("all_dividends")
    d = d[d.race_country == "HK"].copy()
    d["race_date"] = pd.to_datetime(d.race_date.str[:10])
    d["race_no"] = d.race_no.astype(int)
    rows = []
    for rd, rn, js in zip(d.race_date, d.race_no, d.dividends):
        j = json.loads(js)
        for pool in ("win", "pla"):
            for e in j.get(pool) or []:
                c = e["combination"]
                if len(c) != 1:
                    raise ValueError(f"{pool} combination of length {len(c)} on {rd} race {rn}")
                rows.append((rd, rn, pool, int(c[0]), float(e["dividend"])))
    out = pd.DataFrame(rows, columns=["race_date", "race_no", "pool", "horse_no", "dividend"])
    out.attrs["races_with_row"] = d[["race_date", "race_no"]].drop_duplicates()
    return out


@functools.lru_cache(maxsize=None)
def _results() -> pd.DataFrame:
    s = _snapshots()
    races = load_races()
    # every runner that appears in any capture of the race (performances is a subset)
    run = s.groupby(["race_id", "horse_no"], as_index=False).agg(horse_id=("horse_id", "first"))
    last_no = s.groupby("race_id").snap_no.max().rename("last_snap").reset_index()
    last = s.merge(last_no, left_on=["race_id", "snap_no"], right_on=["race_id", "last_snap"])
    last = last[["race_id", "horse_no", "status", "win_disp", "pla_disp", "minutes_before_start"]] \
        .rename(columns={"status": "status_last", "win_disp": "last_win_disp", "pla_disp": "last_pla_disp",
                         "minutes_before_start": "last_capture_lead"})
    run = run.merge(last, on=["race_id", "horse_no"], how="left")
    run = run.merge(races[["race_id", "race_date", "race_no", "venue", "season"]], on="race_id")
    p = _performances_hk()
    p = p[p.race_date >= "2016-09-28"].dropna(subset=["horse_no"]).copy()
    p["horse_no"] = p.horse_no.astype(int)
    pk = ["race_date", "race_no", "horse_no"]
    run = run.merge(p[pk + ["horse_name", "final_placing", "winning_odds", "season_start", "jockey_id",
                            "trainer_id", "draw", "actual_weight", "rating", "on_date_weight"]]
                    .rename(columns={"winning_odds": "perf_win_odds"}), on=pk, how="left", indicator="_perf")
    run["in_perf"] = run.pop("_perf") == "both"
    sec = _sectionals_hk()[pk + ["any_section"]]
    run = run.merge(sec, on=pk, how="left")
    race_has_perf = run.groupby("race_id").in_perf.transform("any")
    run["status"] = np.select(
        [~race_has_perf, run.in_perf, run.status_last == "SCR", run.any_section.fillna(False).astype(bool)],
        ["no_result_race", "ran", "scratched", "dnf"], default="no_sections")
    dv = _dividends()
    win = dv[dv.pool == "win"].rename(columns={"dividend": "win_dividend"}).drop(columns="pool")
    pla = dv[dv.pool == "pla"].rename(columns={"dividend": "pla_dividend"}).drop(columns="pool")
    run = run.merge(win, on=pk, how="left").merge(pla, on=pk, how="left")
    has_row = dv.attrs["races_with_row"].assign(div_row=True)
    run = run.merge(has_row, on=["race_date", "race_no"], how="left")
    run["div_row"] = run.div_row.fillna(False).astype(bool)
    run["n_win_div"] = run.groupby("race_id").win_dividend.transform("count")
    run["n_pla_div"] = run.groupby("race_id").pla_dividend.transform("count")
    run["graded"] = run.div_row & (run.n_win_div >= 1) & (run.n_pla_div >= 2) & race_has_perf
    run["won"] = np.where(run.graded, run.win_dividend.notna().astype(float), np.nan)
    run["placed"] = np.where(run.graded, run.pla_dividend.notna().astype(float), np.nan)
    run["win_dec"] = run.win_dividend / 10.0
    run["pla_dec"] = run.pla_dividend / 10.0
    starters = run.status.isin(["ran", "dnf", "no_sections"])
    run["field"] = starters.groupby(run.race_id).transform("sum").astype(int)
    # Place terms follow the field when the pool OPENED (priced runners in the
    # race's first capture), not the starters at the off: 2018-03-18 race 3
    # opened with 7, lost one to a scratch and still paid 3 places, while every
    # race that opened with 6 paid 2 (part 2 of __main__ reconciles every race).
    opened = s[s.snap_no == 0].groupby("race_id").status.agg(lambda v: int((v == "priced").sum()))
    run["field_open"] = run.race_id.map(opened).astype(int)
    run["places_at_off"] = np.where(run.field >= 7, 3, np.where(run.field >= 4, 2, 0))
    run["places_paid"] = np.where(run.field_open >= 7, 3, np.where(run.field_open >= 4, 2, 0))
    run["post_off_capture"] = run.last_capture_lead < 0
    run["final_win_disp"] = np.where(run.post_off_capture & (run.status != "scratched"), run.last_win_disp, np.nan)
    run["final_pla_disp"] = np.where(run.post_off_capture & (run.status != "scratched"), run.last_pla_disp, np.nan)
    cols = ["race_id", "race_date", "race_no", "venue", "season", "horse_no", "horse_id", "horse_name",
            "status", "final_placing", "won", "placed", "win_dec", "pla_dec", "n_win_div", "n_pla_div",
            "field", "field_open", "places_paid", "places_at_off", "graded", "post_off_capture",
            "final_win_disp", "final_pla_disp",
            "perf_win_odds", "season_start", "jockey_id", "trainer_id", "draw", "actual_weight", "rating",
            "on_date_weight", "any_section", "last_capture_lead"]
    return run[cols].sort_values(["race_id", "horse_no"]).reset_index(drop=True)


def load_results() -> pd.DataFrame:
    """One row per (race, horse_no) for every runner that was ever in the pool.

    status: 'ran' (in performances), 'scratched' (SCR at the final capture: a
    bet is refunded), 'dnf' (priced, missing from performances, has a sectional:
    a losing bet), 'no_sections' (priced, missing from performances, no
    sectional at all: still in the pool at the close by the win-book test in
    __main__, so a losing bet),
    'no_result_race' (the race has no performances at all: void).
    won / placed come from the dividends and are NaN when the race is not graded.
    win_dec / pla_dec are dividend / 10, already split on a dead heat.
    field = starters at the off; field_open = priced runners when the pool
    opened (first capture); places_paid = 3 if field_open >= 7, 2 if 4-6, 0
    otherwise (places_at_off is the same rule on field, kept for the check).
    final_win_disp is the floored final pool price from a capture after the
    start, NaN for the races without one. perf_win_odds is capped at 99."""
    return _results().copy()


def decision_frame(lead_minutes: float, max_stale: float | None = None) -> pd.DataFrame:
    """snapshot_at(lead) joined to load_results(), graded races only.

    DECISION-TIME columns (a rule may decide on these): everything snapshot_at
    returns (win_at_snap, pla_at_snap, status_at_snap, field_at_snap,
    book_at_snap, book_mid_at_snap, book_pla_at_snap, snap_lead, stale_min),
    bettable (priced at the decision), field_open and places_paid (fixed when
    the pool opened, the day before).

    HINDSIGHT columns (grading only, never an input): final_status, won,
    placed, win_dec, pla_dec, n_win_div, field, places_at_off, final_win_disp,
    perf_win_odds, post_off_capture, refund (priced at the decision, scratched
    later: the bet is returned)."""
    snap = snapshot_at(lead_minutes, max_stale)
    res = _results()
    keep = ["race_id", "horse_no", "status", "won", "placed", "win_dec", "pla_dec", "n_win_div",
            "field", "field_open", "places_paid", "places_at_off", "graded", "final_win_disp", "perf_win_odds",
            "post_off_capture"]
    out = snap.merge(res[keep].rename(columns={"status": "final_status"}), on=["race_id", "horse_no"], how="left")
    out = out[out.graded.fillna(False).astype(bool)].copy()
    out["bettable"] = out.status_at_snap == "priced"
    out["refund"] = out.bettable & (out.final_status == "scratched")
    return out.sort_values(["race_id", "horse_no"]).reset_index(drop=True)


# ---------------------------------------------------------------- evidence

def _q(s: pd.Series, qs=(0, .01, .05, .25, .5, .75, .95, .99, 1)) -> str:
    v = s.quantile(list(qs))
    return "  ".join(f"p{int(round(100 * k)):>2}={x:+.2f}" for k, x in v.items())


def _floor_disp(x) -> np.ndarray:
    x = np.asarray(x, float)
    return np.where(x < 10, np.floor(x * 10 + 1e-9) / 10, np.floor(x + 1e-9))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    s = _snapshots()
    races = load_races()
    res = _results()
    lo_races = s.race_id.unique()
    caps = s.drop_duplicates(["race_id", "snap_no"])[["race_id", "snap_no", "capture_utc", "minutes_before_start"]]
    caps = caps.merge(races[["race_id", "race_date", "start_hk"]], on="race_id")

    print("== 1. time base")
    lastc = caps.loc[caps.groupby("race_id").snap_no.idxmax()]
    raw_h = (lastc.capture_utc - lastc.start_hk).dt.total_seconds() / 3600
    print(f"  last capture minus listed race_time, raw clocks (hours), {len(lastc)} races:\n    {_q(raw_h)}")
    # freeze: the first capture of the final run of identical win odds
    key = [f"{h}:{v:.2f}:{t}" for h, v, t in zip(s.horse_no, s.win_disp.fillna(-1.0), s.status)]
    w = s[["race_id", "snap_no"]].assign(k=pd.Series(key, index=s.index, dtype=object))
    sig = w.groupby(["race_id", "snap_no"]).k.agg(lambda x: "|".join(x)).reset_index()
    sig = sig.merge(caps[["race_id", "snap_no", "minutes_before_start", "race_date"]], on=["race_id", "snap_no"])
    fr = []
    for rid, g in sig.groupby("race_id", sort=False):
        k = g.k.to_numpy(); L = g.minutes_before_start.to_numpy(); i = len(k) - 1
        while i > 0 and k[i - 1] == k[-1]:
            i -= 1
        fr.append((rid, L[i], L[i - 1] if i > 0 else np.nan, L[-1], str(g.race_date.iloc[0])[:7],
                   int(((L >= 0) & (k == k[-1])).sum())))
    fr = pd.DataFrame(fr, columns=["race_id", "first_final", "prev", "last", "month", "pre_start_equal_final"])
    post = fr[fr["last"] < 0]
    print(f"  with +8 h: races whose last capture is after the start {len(post)}, before it {len(fr) - len(post)}")
    print(f"  minutes before start of the FIRST capture showing the final win odds:\n    {_q(post.first_final)}")
    print(f"  ... of the capture just before it (odds still moving):\n    {_q(post.prev)}")
    print(f"  falsifier: captures taken before the start that already show the final odds: "
          f"{int(post.pre_start_equal_final.sum())} (in {int((post.pre_start_equal_final > 0).sum())} races)")
    print(f"  races where odds still changed at a capture >= 1 min after the start: {int((post.prev <= -1).sum())}")
    mm = post.groupby("month").first_final.median()
    print(f"  monthly median of first-final lead: min {mm.min():+.2f} max {mm.max():+.2f} over {len(mm)} months (no DST drift)")
    print("  offset used: HK = capture_time + 8 h; minutes_before_start = start_hk - (capture_utc + 8 h)")

    print("\n== 2. joins (Hong Kong)")
    lo_raw = _read("live_odds")
    lo_raw = lo_raw[lo_raw.race_country == "HK"]
    vchk = lo_raw.assign(race_date=pd.to_datetime(lo_raw.race_date), race_no=lo_raw.race_no.astype(int)) \
        .drop_duplicates(["race_date", "race_no", "race_location"]) \
        .merge(races[["race_date", "race_no", "venue"]], on=["race_date", "race_no"])
    dvr = _read("all_dividends")
    pf = _performances_hk()
    pf16 = pf[pf.race_date >= "2016-09-28"]
    hn = pf.assign(y=pf.race_date.dt.year).groupby("y").horse_no.apply(lambda x: x.notna().mean())
    print(f"  key checks: live-odds races with one venue per (date, race_no) "
          f"{int(vchk.duplicated(['race_date', 'race_no']).sum() == 0)}, venue == races.csv venue "
          f"{int((vchk.race_location == vchk.venue).sum())} of {len(vchk)}; duplicate captures (race, capture_time) "
          f"{int(lo_raw.duplicated(['race_date', 'race_no', 'capture_time']).sum())}; duplicate dividend rows "
          f"{int(dvr.duplicated(['race_date', 'race_no', 'race_country']).sum())}; duplicate performances "
          f"(date, race_no, horse_no) since 2016-09-28 {int(pf16.dropna(subset=['horse_no']).duplicated(['race_date', 'race_no', 'horse_no']).sum())}")
    print(f"  performances.horse_no present: 2015 {hn.get(2015, 0):.0%}, 2016 {hn.get(2016, 0):.0%}, "
          f"2017 {hn.get(2017, 0):.0%}; first date with horse_no {pf[pf.horse_no.notna()].race_date.min().date()}; "
          f"null since 2016-09-28 {int(pf16.horse_no.isna().sum())}")
    hk_all = len(races)
    print(f"  races.csv HK races {hk_all}; in live odds {len(lo_races)} "
          f"({s.race_date.min().date()} to {s.race_date.max().date()}, {s.race_date.nunique()} meetings); "
          f"races.csv HK races with no live odds {hk_all - len(lo_races)} "
          f"({races[~races.race_id.isin(lo_races)].race_date.min().date()} to "
          f"{races[~races.race_id.isin(lo_races)].race_date.max().date()})")
    rr = res.groupby("race_id").agg(graded=("graded", "first"),
                                    has_perf=("status", lambda x: (x != "no_result_race").any()),
                                    n_win=("n_win_div", "first"), n_pla=("n_pla_div", "first"))
    dv_races = _dividends().attrs["races_with_row"].merge(races[["race_id", "race_date", "race_no"]])
    in_dv = rr.index.isin(dv_races.race_id)
    print(f"  live-odds races -> with race_time {len(lo_races)} -> with a dividends row {int(in_dv.sum())} "
          f"-> with performances {int(rr.has_perf.sum())} -> graded (win + place dividends + performances) "
          f"{int(rr.graded.sum())}")
    nog = res[~res.graded].drop_duplicates("race_id")
    for _, r in nog.iterrows():
        why = "no dividends, no performances (void)" if r.status == "no_result_race" else "no dividends row"
        print(f"    not graded: {r.race_date.date()} race {r.race_no}: {why}")
    print(f"  runners ever in the pool {len(res)}; status: {res.status.value_counts().to_dict()}")
    print(f"  performances runners (since 2016-09-28) not in any capture: "
          f"{int(_perf_not_in_pool(res))}")
    first_last = s.groupby(["race_id", "horse_no"]).status.agg(lambda x: "".join("S" if v == "SCR" else "p" for v in x if v != "---"))
    pat = first_last.map(lambda x: "never SCR" if "S" not in x else ("SCR then priced" if "Sp" in x
                         else ("priced then SCR" if x.startswith("p") else "SCR throughout")))
    print(f"  scratch pattern across captures: {pat.value_counts().to_dict()}")
    g = res[res.graded]
    print(f"  graded races {g.race_id.nunique()}, runners {len(g)}, starters {int(g.status.isin(['ran','dnf','no_sections']).sum())}; "
          f"winners per race (win dividends): {g.drop_duplicates('race_id').n_win_div.value_counts().to_dict()}")
    two = _perf_two_firsts(res)
    print(f"  races where performances has two firsts: {two}; with two win dividends: "
          f"{[(str(d.date()), n) for d, n in g[g.n_win_div > 1].drop_duplicates('race_id')[['race_date','race_no']].values]}")
    ran = g[g.status == "ran"]
    bad_w = ran[(ran.final_placing == 1) != (ran.won == 1)]
    print(f"  finishers where placing 1 and the win dividend disagree: {len(bad_w)} "
          f"{bad_w[['race_date','race_no','horse_no','final_placing','won']].astype(str).values.tolist()}")
    pl_by_fp = ran.assign(fp_place=(ran.final_placing <= ran.places_paid).astype(float))
    bad_p = pl_by_fp[pl_by_fp.fp_place != pl_by_fp.placed]
    print(f"  finishers where placing <= places_paid and the place dividend disagree: {len(bad_p)} "
          f"{bad_p[['race_date','race_no','horse_no','final_placing','placed']].astype(str).values.tolist()}")
    pt = g.drop_duplicates("race_id")
    print("  starters at the off against place dividends paid:")
    print("    " + pd.crosstab(pt.field, pt.n_pla_div).to_string().replace("\n", "\n    "))
    print("  priced runners when the pool opened against place dividends paid:")
    print("    " + pd.crosstab(pt.field_open, pt.n_pla_div).to_string().replace("\n", "\n    "))
    fpr = ran.groupby("race_id").final_placing.apply(list)
    for col in ("places_at_off", "places_paid"):
        extra = pt[pt.n_pla_div != pt[col]]
        dh_last = [rid for rid in extra.race_id
                   if sum(x == pt.set_index("race_id").loc[rid, col] for x in fpr.get(rid, [])) > 1]
        other = extra[~extra.race_id.isin(dh_last)]
        print(f"  terms from {col:13s}: races where place dividends != terms {len(extra)}; explained by a dead "
              f"heat at the last place {len(dh_last)}; unexplained {len(other)} "
              f"{[(str(d.date()), n) for d, n in other[['race_date', 'race_no']].values]}")
    seas = res[res.status == "ran"]
    print(f"  season_of(race_date) == performances.season start year: "
          f"{int((seas.season == seas.season_start).sum())} of {len(seas)}; seasons "
          f"{[season_label(x) for x in sorted(res.season.unique())]}")
    perrace = res.drop_duplicates("race_id")
    print(f"  graded races by season: {perrace[perrace.graded].season.value_counts().sort_index().to_dict()}")

    print("\n== 3. snapshot spacing")
    n = caps.groupby("race_id").size()
    print(f"  captures per race: min {n.min()} median {int(n.median())} max {n.max()}; "
          f"first capture lead (h): median {caps.groupby('race_id').minutes_before_start.max().median() / 60:.1f} "
          f"min {caps.groupby('race_id').minutes_before_start.max().min() / 60:.1f}")
    caps = caps.sort_values(["race_id", "snap_no"])
    caps["gap"] = caps.groupby("race_id").minutes_before_start.diff().abs()
    b = pd.cut(caps.minutes_before_start, [-60, 0, 5, 15, 60, 216, 600, 1440, 3000])
    cad = caps.groupby(b, observed=True).gap.agg(["size", "median", lambda x: x.quantile(.9)])
    cad.columns = ["captures", "gap_median", "gap_p90"]
    print("  cadence by lead (minutes):\n    " + cad.round(2).to_string().replace("\n", "\n    "))
    near = int((caps.gap < 1).sum())
    print(f"  near-duplicate captures (< 1 min after the previous one of the same race): {near}")
    tot = len(lo_races)
    gr = set(res[res.graded].race_id)
    for L in LEADS:
        has = caps[(caps.minutes_before_start > 0) & (caps.minutes_before_start <= L)].race_id.nunique()
        sa = snapshot_at(L)
        st = sa.drop_duplicates("race_id").stale_min
        gl = sa[sa.race_id.isin(gr)]
        print(f"  L={L:>3}: races with a capture in (0, {L}] min {has / tot:6.1%}  | snapshot_at: {sa.race_id.nunique()} races "
              f"({len(gl.drop_duplicates('race_id'))} graded, {int((gl.status_at_snap == 'priced').sum())} priced runners), "
              f"stale median {st.median():.2f} p90 {st.quantile(.9):.2f} max {st.max():.2f}")

    print("\n== 4. final prices")
    fw = g[(g.won == 1) & g.post_off_capture]
    single = fw[fw.n_win_div == 1]
    eq = np.isclose(_floor_disp(single.win_dec), single.final_win_disp)
    print(f"  single winners with a post-off capture {len(single)}: floor(dividend/10) == final displayed win odds "
          f"{int(eq.sum())} ({eq.mean():.2%})")
    cap99 = np.minimum(_floor_disp(single.win_dec), 99.0)
    eqp = np.isclose(cap99, single.perf_win_odds)
    print(f"  floor(dividend/10) capped at 99 == performances.winning_odds: {int(eqp.sum())} of {len(single)}")
    allr = res[(res.status == "ran") & res.post_off_capture & res.perf_win_odds.notna()]
    lt = allr[allr.final_win_disp < 99]
    print(f"  every finisher, final displayed < 99: == performances.winning_odds {int(np.isclose(lt.final_win_disp, lt.perf_win_odds).sum())} "
          f"of {len(lt)}; final displayed >= 99: {int((allr.final_win_disp >= 99).sum())}, performances shows "
          f"{allr[allr.final_win_disp >= 99].perf_win_odds.value_counts().to_dict()}")
    fp = g[(g.placed == 1) & g.post_off_capture & g.final_pla_disp.notna()]
    eqpl = np.isclose(_floor_disp(fp.pla_dec), fp.final_pla_disp)
    over = fp.final_pla_disp > fp.pla_dec + 1e-9
    print(f"  placers {len(fp)}: floor(dividend/10) == final displayed place odds {eqpl.mean():.2%}; "
          f"displayed above dividend/10 in {int(over.sum())}")
    dh_last = set(g[g.n_pla_div > g.places_paid].race_id)
    ov = fp[over]
    print(f"    of those {int(over.sum())}: in a race with a dead heat for the last place {int(ov.race_id.isin(dh_last).sum())} "
          f"(dead-heat races {len(dh_last)}, {int(fp[fp.race_id.isin(dh_last)].final_placing.eq(fp[fp.race_id.isin(dh_last)].places_paid).sum())} "
          f"tied placers); others {ov[~ov.race_id.isin(dh_last)][['race_date', 'race_no', 'horse_no', 'pla_dec', 'final_pla_disp']].astype(str).values.tolist()}")
    fin_cap = s[s.minutes_before_start < 0].drop_duplicates(["race_id", "snap_no"])
    fin_cap = fin_cap.loc[fin_cap.groupby("race_id").snap_no.idxmax()].merge(
        g.drop_duplicates("race_id")[["race_id", "places_paid", "places_at_off", "field_open", "field"]], on="race_id")
    fin_cap = fin_cap[fin_cap.places_paid > 0]
    ratio = fin_cap.book_pla / fin_cap.places_paid
    print(f"  final place book / places_paid ({len(fin_cap)} graded races): median {ratio.median():.4f} "
          f"p5 {ratio.quantile(.05):.4f} p95 {ratio.quantile(.95):.4f}; 1/(1-{PLACE_TAKEOUT}) = {1 / (1 - PLACE_TAKEOUT):.4f}")
    for n_pl in (2, 3):
        rr_ = (fin_cap.book_pla / n_pl)[(fin_cap.field_open == 7) & (fin_cap.field == 6)]
        print(f"    races that opened with 7 and started 6 ({len(rr_)}): place book / {n_pl} = "
              f"{', '.join(f'{x:.4f}' for x in rr_)}")
    for n_open in (6, 7):
        sub = fin_cap[fin_cap.field_open == n_open]
        print(f"    races that opened with {n_open} ({len(sub)}): place book median {sub.book_pla.median():.4f} "
              f"(/2 = {sub.book_pla.median() / 2:.4f}, /3 = {sub.book_pla.median() / 3:.4f})")
    dh = g[(g.won == 1) & (g.n_win_div > 1)]
    print("  dead-heat winners (dividend already split):")
    for _, r in dh.iterrows():
        print(f"    {r.race_date.date()} race {r.race_no} horse {r.horse_no}: win_dec {r.win_dec:.2f}, "
              f"final displayed {r.final_win_disp}, performances {r.perf_win_odds}")
    # last pre-start capture against the final
    pre = s[(s.minutes_before_start > 0) & (s.status == "priced")]
    lp = pre.loc[pre.groupby(["race_id", "horse_no"]).minutes_before_start.idxmin()]
    j = lp.drop(columns="status").merge(res[["race_id", "horse_no", "final_win_disp", "status", "graded"]],
                                        on=["race_id", "horse_no"])
    j = j[j.final_win_disp.notna() & (j.status == "ran")]
    lr_ = np.log(j.final_win_disp / j.win_disp)
    print(f"  last pre-start capture vs final displayed win odds ({len(j)} runners, lead median "
          f"{j.minutes_before_start.median():.2f} min): identical {np.isclose(j.win_disp, j.final_win_disp).mean():.1%}, "
          f"|log ratio| median {lr_.abs().median():.3f} p90 {lr_.abs().quantile(.9):.3f}")
    bk = s[(s.minutes_before_start < 0)].drop_duplicates(["race_id", "snap_no"])
    bk = bk.loc[bk.groupby("race_id").snap_no.idxmax()]
    print(f"  final win book (post-off capture, {len(bk)} races): floored median {bk.book_win.median():.4f}, "
          f"un-floored midpoint median {bk.book_win_mid.median():.4f}, 1/(1-{WIN_TAKEOUT}) = {1 / (1 - WIN_TAKEOUT):.4f}")

    print("\n== 5. traps")
    print(f"  raw values: SCR {int((s.status == 'SCR').sum())}, '---' {int((s.status == '---').sum())} "
          f"(races {sorted(set(map(str, s[s.status == '---'].race_date.dt.date)))}), "
          f"win 999 {int((s.win_disp >= 999).sum())} (all > 24 h out: {bool((s[s.win_disp >= 999].minutes_before_start > 1440).all())}), "
          f"win 1.0 {int((s.win_disp == 1.0).sum())}, place 1.0 {int((s.pla_disp == 1.0).sum())}")
    cb = s.drop_duplicates(["race_id", "snap_no"])
    brk = cb[(cb.book_win < 1.15) | (cb.book_win > 1.30)]
    inside = cb[(cb.minutes_before_start > 0) & (cb.minutes_before_start <= 600)].book_win
    print(f"  captures with a win book outside [1.15, 1.30] (thin early pool): {len(brk)}, nearest the start "
          f"{brk.minutes_before_start.min() / 60:.1f} h out; book inside 10 h: min {inside.min():.4f} "
          f"median {inside.median():.4f} max {inside.max():.4f}")
    gap = fr[fr["last"] > 0]
    print(f"  races with no capture after the start (final odds unknown): {len(gap)}; with the last capture "
          f"> 60 min out: {int((gap['last'] > 60).sum())} ({sorted(set(races.set_index('race_id').loc[gap[gap['last'] > 60].race_id].race_date.dt.date.astype(str)))})")
    ns = res[res.status.isin(["dnf", "no_sections"])]
    print(f"  priced at the off, missing from performances: {len(ns)} runners in {ns.race_id.nunique()} races "
          f"({ns.status.value_counts().to_dict()}); any with a dividend: {int(ns.win_dec.notna().sum() + ns.pla_dec.notna().sum())}")
    nsx = ns[ns.status == "no_sections"]
    if len(nsx):
        last_cap = s.merge(s.groupby("race_id").snap_no.max().rename("ls").reset_index(),
                           left_on=["race_id", "snap_no"], right_on=["race_id", "ls"])
        last_cap = last_cap[last_cap.minutes_before_start < 0]
        rows = []
        typ = bk.book_win.median()
        for _, r in nsx.iterrows():
            c = last_cap[(last_cap.race_id == r.race_id) & (last_cap.status == "priced")]
            if c.empty or r.horse_no not in set(c.horse_no):
                continue
            with_ = (1 / c.win_disp).sum()
            without = (1 / c[c.horse_no != r.horse_no].win_disp).sum()
            rows.append((with_, without, abs(with_ - typ) < abs(without - typ)))
        a = np.array(rows, dtype=float) if rows else np.zeros((0, 3))
        print(f"  'no_sections' runners: {len(nsx)}, testable (priced in a post-off capture) {len(a)}; final win "
              f"book WITH the runner nearer the typical {typ:.4f} than WITHOUT it in {int(a[:, 2].sum())} of {len(a)} "
              f"(with: median {np.median(a[:, 0]) if len(a) else float('nan'):.4f}, without: "
              f"{np.median(a[:, 1]) if len(a) else float('nan'):.4f}): in the pool at the close, so graded as a loss")
    nopost = res[~res.post_off_capture]
    print(f"  races with no post-off capture: {nopost.race_id.nunique()}; their runners by status "
          f"{nopost.status.value_counts().to_dict()} (a scratch after the last capture is invisible there)")
    hid = res.horse_id.isna()
    print(f"  pool runners with no horse_id: {int(hid.sum())} {res[hid].status.value_counts().to_dict()}")
    pk = ["race_date", "race_no", "horse_no"]
    pfh = _performances_hk()
    pfh = pfh[pfh.race_date >= "2016-09-28"].dropna(subset=["horse_no"]).assign(horse_no=lambda x: x.horse_no.astype(int))
    both = pfh[pk + ["horse_id"]].merge(_sectionals_hk()[pk + ["horse_id"]], on=pk, suffixes=("_perf", "_sec"))
    print(f"  horse_id, performances vs sectional_times where both hold the runner: agree "
          f"{int((both.horse_id_perf == both.horse_id_sec).sum())} of {len(both)}")
    scr = s.merge(res[res.status == "scratched"][["race_id", "horse_no"]])
    later = scr[scr.status == "priced"]
    first_scr = scr[scr.status == "SCR"].merge(later[["race_id", "horse_no"]].drop_duplicates()) \
        .groupby(["race_id", "horse_no"]).minutes_before_start.max()
    fb = pd.cut(first_scr, [-60, 0, 5, 15, 60, 600, 3000]).value_counts().sort_index()
    print("  priced runners later scratched, by the lead of their first SCR capture: "
          + ", ".join(f"{k}: {v}" for k, v in fb.items()))
    print(f"  runners priced at some capture and scratched by the off: {later.groupby(['race_id','horse_no']).ngroups}; "
          f"races with 7+ priced 60 min out and < 7 starters at the off: "
          f"{_terms_changed(res, 60)}")
    print("  (graphify update . not run: it rewrites graphify-out/, outside this module's remit)")
    return 0


def _perf_not_in_pool(res: pd.DataFrame) -> int:
    p = _performances_hk()
    p = p[p.race_date >= "2016-09-28"].dropna(subset=["horse_no"]).copy()
    p["horse_no"] = p.horse_no.astype(int)
    lo_dates = res[["race_date", "race_no"]].drop_duplicates()
    p = p.merge(lo_dates, on=["race_date", "race_no"])
    m = p.merge(res[["race_date", "race_no", "horse_no"]], on=["race_date", "race_no", "horse_no"], how="left",
                indicator=True)
    return int((m._merge == "left_only").sum())


def _perf_two_firsts(res: pd.DataFrame) -> list:
    r = res[res.status == "ran"]
    c = r[r.final_placing == 1].groupby(["race_date", "race_no"]).size()
    return [(str(d.date()), n) for (d, n), v in c.items() if v > 1]


def _terms_changed(res: pd.DataFrame, lead: float) -> int:
    snap = snapshot_at(lead)
    f = snap.drop_duplicates("race_id")[["race_id", "field_at_snap"]]
    r = res.drop_duplicates("race_id")[["race_id", "field", "graded"]]
    m = f.merge(r, on="race_id")
    return int(((m.field_at_snap >= 7) & (m.field < 7)).sum())


if __name__ == "__main__":
    sys.exit(main())
