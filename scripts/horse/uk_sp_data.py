"""UK and Ireland results at starting price, 1988-2026: the loader the SP studies import.

Reads the three CSVs of the Kaggle set `deltaromeo/horse-racing-results-ukireland-2015-2025`
(stored in Supabase as the downloaded zip, source `horse_racing|deltaromeo_uk_ireland_1988_2026`
per scripts/horse/store_files.py; the CSVs on disk are extracted from it and match its
entries byte for byte in size):

    raceform.csv                     2015-01-01 .. 2026-10-23
    archive_2005-2014/.../2005-2014.csv
    archive_1988-2004/.../1988-2004.csv

All three share one 37-column header. 1988-2004.csv repeats that header 12 more times
inside the file (13 header lines in all, the first two adjacent); those lines are dropped.
The .db copies hold the repeated headers as data rows, so this reads the CSVs.

WHAT IS DECIDABLE (the rules these studies run under):
  * `sp` is the starting price, the price at the off. A bet at SP is executable at UK
    bookmakers, so a rule may be GRADED at `sp`. A rule that CONDITIONS on `sp`, its rank,
    `book` or `sp_fav` has seen the close: such a table is descriptive or an upper bound.
  * Known before the race: code, class, handicap, `ran`, official rating (`or`), weight,
    age, draw, course, going as declared, and anything from EARLIER races.
  * `rpr`, `ts`, `time`, `pos`, `btn`, `ovr_btn`, `comment` are figures from THAT race.
    Never an input for that race; usable only as history for later races.

THE SOURCE CHANGES FORMAT ON 2026-05-01 (`new_format`). From that date horse, sire and dam
lose their country suffix, jockeys and trainers are written as initials ("L Morris",
"T D Easterby"), the F/J/C favourite marker, `rpr` and `ts` are gone, an unrated horse's `or`
is written blank instead of a dash (rated horses keep their mark: 99.8% of GB and 100.0% of
Irish handicaps May-Oct 2026 are fully rated, measured by uk_sp_structure.py Table 0b), and
most rating bands are blank. `horse_id`, `jockey_id` and `trainer_id` bridge
the change; the jockey and trainer bridge is approximate (see `__main__`).

`off` is a 12-hour clock without am/pm in raceform.csv up to 2025-10 ("1:05"), and 24-hour
("13:05", "07:10") everywhere else. Rule: a single-digit hour is p.m. (+12); a two-digit
hour is read as written. Right for every GB/IRE meeting (10:00-21:59); a foreign
early-morning race in the 12-hour period is mis-timed, and none of those is gradeable.

KNOWN GAPS (measured by `__main__`): 1988-2004.csv holds no Irish and no foreign rows for
2000, 2001 and 2002 (British rows are present, 78,102 to 83,654 a year); 1,687 GB/IRE races in 1988-2004 hold fewer
rows than runners (mostly 1988-1997) and are not gradeable; Irish and foreign course names
lose their suffix in the archives and again 2025-10 to 2026-04, so region comes from the
course sets below, and foreign races run under GB names (Ascot in Perth, Sandown in
Melbourne, Newcastle NSW, South Africa's Newmarket in 2003-2004) are moved to OTHER.

won IS ALREADY THE DEAD-HEAT SHARE (1/n for an n-way dead heat for first). Do not divide
it again: `anz_study.summarise(..., won_col="won")` divides by an `n_win` column, which is
deliberately NOT a column here (the count is `n_first`), so that call fails loudly.

    python -I scripts/horse/uk_sp_data.py            # every data check, printed
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

DATA = ROOT_DIR / "data" / "horse" / "deltaromeo-uk-ireland-1988-2026"
FILES = {  # name: (relative path, first year, last year)
    "1988-2004": ("archive_1988-2004/archive_1988-2004/archive_1988-2004/1988-2004.csv", 1988, 2004),
    "2005-2014": ("archive_2005-2014/archive_2005-2014/archive_2005-2014/2005-2014.csv", 2005, 2014),
    "2015-2026": ("raceform.csv", 2015, 2026),
}
HEADER = ("date,course,race_id,off,race_name,type,class,pattern,rating_band,age_band,sex_rest,"
          "dist,going,ran,num,pos,draw,ovr_btn,btn,horse,age,sex,wgt,hg,time,sp,jockey,trainer,"
          "prize,or,rpr,ts,sire,dam,damsire,owner,comment").split(",")
MANIFEST = {"2015-2026": (1_904_737, 194_125), "2005-2014": (1_555_126, 153_300),
            "1988-2004": (1_653_834, 157_900)}  # (valid rows, distinct race_id) as recorded
NEW_FORMAT_FROM = "2026-05-01"

# Raw columns every load reads (the derived core needs them).
CORE_RAW = ["date", "course", "race_id", "off", "race_name", "type", "class", "ran", "pos",
            "horse", "age", "sp", "jockey", "trainer", "going", "sire", "dam"]
# Raw columns added when cols=None: the decidable race and runner facts.
DEFAULT_EXTRA = ["pattern", "rating_band", "age_band", "sex_rest", "dist", "draw", "wgt", "or",
                 "hg", "sex"]

# ------------------------------------------------------------------ courses and regions
# Explicit sets. The "(IRE)" suffix cannot be used: Irish courses are unsuffixed in both
# archives and again from 2025-10 to 2026-04, and foreign courses are unsuffixed in the
# archives. Names are matched after removing a trailing " (IRE)" and " (AW)" only, so
# "Ascot (AUS)", "Sandown (AUS)", "Newcastle (AUS)", "Belmont Park (Perth)" stay OTHER.
GB_COURSES = frozenset("""Aintree|Ascot|Ayr|Bangor-on-Dee|Bath|Beverley|Brighton|Carlisle|Cartmel|
Catterick|Chelmsford|Cheltenham|Chepstow|Chester|Doncaster|Epsom|Exeter|Fakenham|Ffos Las|
Folkestone|Fontwell|Goodwood|Hamilton|Haydock|Hereford|Hexham|Huntingdon|Kelso|Kempton|
Leicester|Lingfield|Ludlow|Market Rasen|Musselburgh|Newbury|Newcastle|Newmarket|
Newmarket (July)|Newton Abbot|Nottingham|Perth|Plumpton|Pontefract|Redcar|Ripon|Salisbury|
Sandown|Sedgefield|Southwell|Stratford|Taunton|Thirsk|Towcester|Uttoxeter|Warwick|Wetherby|
Wincanton|Windsor|Wolverhampton|Worcester|Yarmouth|York""".replace("\n", "").split("|"))
# Down Royal and Downpatrick are in Northern Ireland but race under Horse Racing Ireland
# and the source writes them "(IRE)"; they are IRE here.
IRE_COURSES = frozenset("""Ballinrobe|Bellewstown|Clonmel|Cork|Curragh|Down Royal|Downpatrick|
Dundalk|Fairyhouse|Galway|Gowran Park|Kilbeggan|Killarney|Laytown|Leopardstown|Limerick|
Listowel|Mallow|Naas|Navan|Phoenix Park|Punchestown|Roscommon|Sligo|Thurles|Tipperary|Tralee|
Tramore|Wexford|Wexford (RH)""".replace("\n", "").split("|"))
COURSE_ALIASES = {"Royal Ascot": "Ascot", "Epsom Downs": "Epsom"}  # new labels from 2026-05
AW_VENUES = frozenset({"Lingfield", "Kempton", "Wolverhampton", "Southwell", "Chelmsford",
                       "Newcastle", "Dundalk"})
AW_GOINGS = frozenset({"Standard", "Standard To Slow", "Standard To Fast", "Slow", "Fast"})

# ------------------------------------------------------------------ starting prices
# The UK/Irish bookmaker SP ladder. Prices off it (48/10, 53/10, 116/1 ...) are foreign tote
# returns written as fractions; `sp_ladder` marks which a runner's price is.
_LADDER = """1/100 1/50 1/40 1/33 1/25 1/20 1/16 1/14 1/12 1/11 1/10 1/9 1/8 1/7 2/13 1/6 2/11
1/5 2/9 1/4 2/7 3/10 30/100 1/3 4/11 3/8 2/5 4/9 1/2 8/15 4/7 8/13 4/6 8/11 4/5 5/6 10/11 20/21
Evens Evs 21/20 11/10 6/5 5/4 11/8 6/4 13/8 7/4 15/8 2/1 85/40 9/4 5/2 11/4 3/1 100/30 7/2 4/1
9/2 5/1 11/2 6/1 13/2 7/1 15/2 8/1 17/2 9/1 10/1 11/1 12/1 13/1 14/1 15/1 16/1 18/1 20/1 22/1
25/1 28/1 33/1 40/1 50/1 66/1 80/1 100/1 125/1 150/1 200/1 250/1 300/1 400/1 500/1 1000/1
10/3 1/1"""  # the last two are how the source writes 100/30 and Evens from 2026-05-01
SP_LADDER = frozenset(_LADDER.split())
# A GB/IRE course name with a race off before 10:00 or from 22:00 UK time is a foreign
# namesake (Ascot in Perth, Sandown in Melbourne, Newcastle in NSW): no GB or Irish meeting
# runs then. Those races are OTHER. The bounds are in minutes after midnight.
GBI_FIRST_OFF, GBI_LAST_OFF = 10 * 60, 22 * 60
# Off times do not catch every namesake: South Africa's Newmarket (2003-2004, local times
# close to UK times) and some Australian races with local times. A GB/IRE-named race where
# more than half the runners, and at least SH_MIN_RUNNERS of them, are bred in the
# Southern Hemisphere or Asia is also a namesake. Needs the country suffix, so it cannot
# fire from 2026-05-01.
SH_BRED_RX = r"\((?:AUS|NZ|SAF|ARG|BRZ|CHI|JPN|HK|URU|PER)\)\s*$"
SH_MIN_RUNNERS = 4
# A race's SP book below 1.0 is impossible for a bookmaker SP return: a price or the runner
# list is wrong. Before 2026-05-01 a race with no favourite marker, or a marker off the
# shortest price, is wrong in the same way. Neither is gradeable (`book_low`, `mark_bad`,
# counted in the checks; `gradeable_raw` is the set before these two SP-reading filters).
MIN_BOOK = 1.0
_FRAC = re.compile(r"^(\d+)/(\d+)([FJC]?)$")
_EVENS = re.compile(r"^(Evens|Evs)([FJC]?)$")

# ------------------------------------------------------------------ positions
# Non-finishing codes seen in `pos`. "0" is not a place: in the archives it is ran out,
# refused, disqualified-and-placed-last and foreign unplaced runners. "-" (2026-05 on) is a
# runner in a race with no result (abandoned, void, or not yet scraped).
NONFINISH = {"PU": "pulled up", "F": "fell", "UR": "unseated rider", "BD": "brought down",
             "RO": "ran out", "SU": "slipped up", "RR": "refused to race", "REF": "refused",
             "CO": "carried out", "LFT": "left at start", "DSQ": "disqualified",
             "0": "no placing recorded", "-": "no result"}


# ================================================================== reading

def _read_csv(path: Path, cols: list[str]) -> pd.DataFrame:
    """One CSV, every column as an exact string, strings as categoricals.

    pyarrow with every column forced to string returns the same values as pandas'
    C parser on all 37 columns of all three files (checked 2026-11-15); without the
    forced type it rewrites `off` as "15:35:00"."""
    import pyarrow as pa
    import pyarrow.csv as pc
    tb = pc.read_csv(
        path,
        read_options=pc.ReadOptions(use_threads=True, block_size=1 << 24),
        parse_options=pc.ParseOptions(newlines_in_values=True),
        convert_options=pc.ConvertOptions(
            include_columns=cols, column_types={c: pa.string() for c in cols},
            strings_can_be_null=False, quoted_strings_can_be_null=False))
    out = {}
    for c in cols:
        out[c] = tb.column(c).dictionary_encode().combine_chunks().to_pandas()
    del tb
    return pd.DataFrame(out)


def _concat_cats(parts: list[pd.DataFrame]) -> pd.DataFrame:
    from pandas.api.types import union_categoricals
    cols = parts[0].columns
    return pd.DataFrame({c: union_categoricals([p[c] for p in parts], ignore_order=True)
                         for c in cols})


def _map_cat(s: pd.Series, fn) -> np.ndarray:
    """Apply fn to a categorical's categories and broadcast back by code."""
    s = s.astype("category")
    v = np.asarray(fn(pd.Series(s.cat.categories.astype(str))), dtype=object)
    v = np.append(v, np.nan)  # code -1 (missing) maps to NaN
    return v[s.cat.codes.to_numpy()]


def _cat(values) -> pd.Categorical:
    return pd.Categorical(values)


def read_raw(cols: list[str] | None = None, years=None, root: Path = DATA,
             log: dict | None = None) -> pd.DataFrame:
    """The raw rows of the files that overlap `years`, repeated headers dropped.
    `file` names the source file. Nothing else is changed."""
    cols = list(dict.fromkeys(CORE_RAW + (DEFAULT_EXTRA if cols is None else list(cols))))
    bad = [c for c in cols if c not in HEADER]
    if bad:
        raise ValueError(f"not columns of this set: {bad}")
    if years is None:
        ys = None
    elif isinstance(years, (int, np.integer)):
        ys = {int(years)}
    else:
        ys = {int(y) for y in years}
    parts = []
    for name, (rel, lo, hi) in FILES.items():
        if ys is not None and not any(lo <= y <= hi for y in ys):
            continue
        path = root / rel
        with open(path, encoding="utf-8") as fh:
            first = fh.readline().rstrip("\r\n").split(",")
        if first != HEADER:
            raise SystemExit(f"{path.name}: header differs from raceform.csv's")
        d = _read_csv(path, cols)
        hdr = (d["race_id"].astype(str) == "race_id").to_numpy()
        if log is not None:
            log.setdefault("files", {})[name] = {"rows_in_file": int(len(d)),
                                                 "repeated_header_rows": int(hdr.sum())}
        d = d.loc[~hdr].reset_index(drop=True)
        if ys is not None:
            # The dropped header rows leave "date" behind as an unused category, and
            # _map_cat maps every category: drop it first, or int("date") raises.
            yr = _map_cat(d["date"].cat.remove_unused_categories(),
                          lambda u: u.str[:4].astype(int))
            d = d.loc[np.isin(yr.astype(int), list(ys))].reset_index(drop=True)
        d["file"] = pd.Categorical([name] * len(d), categories=list(FILES))
        parts.append(d)
    if not parts:
        raise SystemExit(f"no file covers years {sorted(ys)}")
    df = _concat_cats(parts) if len(parts) > 1 else parts[0]
    df["file"] = pd.Categorical(df["file"].astype(str), categories=list(FILES))
    for c in df.columns:
        if c != "file" and df[c].dtype.name == "category":
            df[c] = df[c].cat.remove_unused_categories()
    return df


# ================================================================== parsers

def parse_sp(sp: pd.Series) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(decimal, favourite marker, status, on_ladder) per row, through a map of the unique
    strings. Marker is '', 'F', 'J' (joint) or 'C' (co-favourite). Status is 'ok',
    'missing' (blank) or 'unparsed' (anything else, e.g. a bare 'F')."""
    cats = pd.Series(sp.astype("category").cat.categories.astype(str))
    dec, mark, stat, lad = [], [], [], []
    for s in cats:
        m = _FRAC.match(s)
        e = _EVENS.match(s)
        if m and int(m.group(2)) > 0:
            d = 1.0 + int(m.group(1)) / int(m.group(2))
            dec.append(d if d > 1.0 else np.nan)
            mark.append(m.group(3))
            stat.append("ok" if d > 1.0 else "unparsed")
            lad.append(f"{m.group(1)}/{m.group(2)}" in SP_LADDER)
        elif e:
            dec.append(2.0); mark.append(e.group(2)); stat.append("ok"); lad.append(True)
        else:
            dec.append(np.nan)
            mark.append(s if s in ("F", "J", "C") else "")
            stat.append("missing" if s == "" else "unparsed")
            lad.append(False)
    codes = sp.astype("category").cat.codes.to_numpy()
    return (np.asarray(dec, float)[codes], np.asarray(mark, object)[codes],
            np.asarray(stat, object)[codes], np.asarray(lad, bool)[codes])


def parse_off(off: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """(minutes after midnight, twelve_hour flag). A single-digit hour is the 12-hour
    p.m. form and gets +12 h; a two-digit hour is taken as written."""
    def f(u):
        h = u.str.extract(r"^(\d{1,2}):(\d{2})$")
        hh = pd.to_numeric(h[0], errors="coerce")
        mm = pd.to_numeric(h[1], errors="coerce")
        single = h[0].str.len() == 1
        return np.where(single, hh + 12, hh) * 60 + mm
    def g(u):
        return u.str.match(r"^\d:\d\d$").to_numpy()
    return _map_cat(off, f).astype(float), _map_cat(off, g).astype(bool)


def parse_dist(dist: pd.Series) -> np.ndarray:
    """Furlongs from '2m3½f', '7½f', '1m', '1m½f', with yards if written."""
    def f(u):
        m = u.str.extract(r"^(?:(\d+)m)?(?:(\d*)(½)?f)?(?:(\d+)y)?$")
        miles = pd.to_numeric(m[0], errors="coerce").fillna(0)
        furl = pd.to_numeric(m[1], errors="coerce").fillna(0) + m[2].notna() * 0.5
        yards = pd.to_numeric(m[3], errors="coerce").fillna(0)
        out = miles * 8 + furl + yards / 220.0
        return np.where((out > 0) & u.str.len().gt(0), out, np.nan)
    return _map_cat(dist, f).astype(float)


def parse_wgt(wgt: pd.Series) -> np.ndarray:
    """Pounds from 'st-lb' ('11-6' = 160)."""
    def f(u):
        m = u.str.extract(r"^(\d+)-(\d+)$")
        return pd.to_numeric(m[0], errors="coerce") * 14 + pd.to_numeric(m[1], errors="coerce")
    return _map_cat(wgt, f).astype(float)


def parse_num(s: pd.Series) -> np.ndarray:
    """A number, or NaN for '', '-', the en dash the source writes for 'none', or text."""
    return _map_cat(s, lambda u: pd.to_numeric(u, errors="coerce")).astype(float)


_CODES = ("ALG ARG AUS AUT AZE BEL BHR BRB BRZ BUL CAN CHI CRO CYP CZE DEN ECU EG FR GB GDR GER "
          "GR GTM GUE HK HOL HRV HUN IND IOM IRE ISR ITY JER JPN KEN KOR KSA MEM MEX MOR NOR NZ "
          "PER PHI POL POR PR QA RUS SAF SER SLO SPA SU SWE SWI THA TUN TUR UAE UKR URU USA VEN "
          "YUG ZIM").split()
_CODE_RX = re.compile(r"\s*(?:\((?:%s)\)|\s(?:%s))\s*$" % ("|".join(_CODES), "|".join(_CODES)))


def norm_name(u: pd.Series, dam: bool = False) -> pd.Series:
    """Country suffix removed ('(IRE)', or ' GB' unbracketed as some dams are written),
    lower case, letters and digits only. For a dam, a re-registration 'I' glued to the
    name ('Anna Of SaxonyI') is also removed."""
    v = u.str.replace(_CODE_RX, "", regex=True)
    if dam:
        v = v.str.replace(r"(?<=[a-z])I$|\sI$", "", regex=True)
    return (v.str.lower().str.replace(r"[^a-z0-9 ]", "", regex=True)
             .str.replace(r"\s+", " ", regex=True).str.strip())


def person_key(u: pd.Series) -> pd.Series:
    """First initial + surname, lower case: 'Luke Morris' and 'L Morris' -> 'l morris',
    'Tim Easterby' and 'T D Easterby' -> 't easterby'. Titles and bracketed text dropped."""
    v = (u.str.lower().str.replace(r"\(.*?\)", " ", regex=True)
          .str.replace(r"[^a-z& ]", "", regex=True).str.replace(r"\s+", " ", regex=True).str.strip()
          .str.replace(r"^(?:mr|mrs|ms|miss|dr|sir|capt|major|lady|lord)\s+", "", regex=True))
    v = v.str.replace(r"\s+(?:jnr|snr|junior|senior)$", "", regex=True)
    toks = v.str.split(" ")
    return toks.map(lambda t: (t[0][:1] + " " + t[-1]) if len(t) >= 2 else (t[0] if t else ""))


# ================================================================== place terms

def place_terms(ran, handicap) -> tuple[np.ndarray, np.ndarray]:
    """(places paid, fraction of the win odds) under standard UK and Irish each-way terms,
    by runners at the off and handicap or not:
        2-4 runners             win only (places = 1, fraction 0)
        5-7                     2 places at 1/4
        8+ (not a handicap)     3 places at 1/5
        handicap 12-15          3 places at 1/4
        handicap 16+            4 places at 1/4
    Books may offer better terms on a given race; these are the defaults."""
    ran = np.asarray(ran, float)
    hc = np.asarray(handicap, bool)
    places = np.select([ran <= 4, ran <= 7, hc & (ran >= 16), hc & (ran >= 12)], [1, 2, 4, 3], 3)
    frac = np.select([ran <= 4, ran <= 7, hc & (ran >= 12)], [0.0, 0.25, 0.25], 0.2)
    return places.astype(int), frac


def position_share(pos, dh_n, places, has_result=None) -> np.ndarray:
    """Share of a bet that pays when the first `places` positions pay. A tie at position
    p among n runners covers positions p..p+n-1; the share is the number of those inside
    the places over n (a dead heat for the last place pays half each). Non-finishers 0;
    NaN where the race has no result."""
    pos = np.asarray(pos, float)
    n = np.asarray(dh_n, float)
    pl = np.asarray(places, float)
    paid = np.clip(np.minimum(pl, pos + n - 1) - pos + 1, 0, None)
    share = np.where(np.isnan(pos), 0.0, paid / np.where(n > 0, n, 1))
    if has_result is not None:
        share = np.where(np.asarray(has_result, bool), share, np.nan)
    return share


def placed(df: pd.DataFrame, places=None) -> np.ndarray:
    """Place share for every runner under standard terms (or a given `places` per row)."""
    if places is None:
        places, _ = place_terms(df["ran"].to_numpy(), df["handicap"].to_numpy())
    return position_share(df["pos"].to_numpy(), df["dh_n"].to_numpy(), places,
                          df["n_first"].to_numpy() > 0)


# ================================================================== load

def load(cols=None, years=None, root: Path = DATA, log: dict | None = None,
         keep_raw: bool = False) -> pd.DataFrame:
    """One row per runner, sorted so each race is contiguous and races run in time order
    (so `clogit.starts_of(df, "race_key")` works). Columns, besides the raw ones read:

      race_key     int64, one per race, chronological. race_id alone is NOT a race key:
                   raceform.csv reuses 700 ids for different races. Key = (file, race_id,
                   date, course, off).
      date, year, off_min, new_format (rows from 2026-05-01, the changed source)
      course_base, region (GB / IRE / OTHER), surface (AW / Turf / Sand / ''),
      code (Flat / Hurdle / Chase / NH Flat), jumps, handicap, cls (class number)
      ran (runners at the off, from the file), rows (rows held for the race),
      complete (rows == ran)
      pos (finishing position, NaN for a non-finisher), nf_code, finished, dh_n
      n_first (runners placed first), won (DEAD-HEAT SHARE, NaN if no result)
      sp (decimal SP), sp_fav ('' F J C: the closing favourite marker, descriptive only;
      absent from 2026-05-01), sp_status, sp_ladder, book (sum of 1/sp in the race,
      NaN unless every runner's SP parsed)
      gradeable    GB or IRE (namesakes excluded), a result, rows == ran, every SP
                   parsed, not book_low (SP book under MIN_BOOK) and not mark_bad (before
                   2026-05-01: no F/J/C marker, or one off the shortest price). Those two
                   read SPs, as data hygiene only; gradeable_raw is the set without them,
                   so a study can report both ways.
      namesake     a GB/IRE course name used for a foreign race (moved to OTHER)
      arab         an Arabian-horse race (kept in gradeable; filter it if unwanted)
      horse_id, foal_year, jockey_id, trainer_id, jockey_key, trainer_key
      dist_f, wgt_lbs, or_num, draw_num, rpr_num, ts_num (when the raw column is read;
      rpr and ts are THAT race's figures)

    cols: extra raw columns to read (None = DEFAULT_EXTRA). years: an int or iterable of
    ints; only the files covering them are read. race_key numbers the races LOADED, and the
    2026-05 jockey/trainer bridge needs the two years before it in the load, so never join
    race_key, jockey_id or trainer_id across two loads with different `years`; horse_id is
    a string and is stable. Every raw column is kept as a
    categorical except those replaced by parsed versions (keep_raw=True keeps all).
    """
    t0 = time.time()
    if log is None:
        log = {}
    df = read_raw(cols, years, root, log)
    log["read_seconds"] = round(time.time() - t0, 1)
    if df.empty:
        raise SystemExit(f"no rows for years {sorted(years) if years is not None else 'all'}")

    # ---- dates, times, the race key
    dc = df["date"].astype("category")
    df["date"] = pd.to_datetime(pd.Series(dc.cat.categories.astype(str)), format="%Y-%m-%d").to_numpy()[dc.cat.codes.to_numpy()]
    df["year"] = df["date"].dt.year.astype(np.int16)
    df["new_format"] = (df["date"] >= NEW_FORMAT_FROM).to_numpy()
    df["off_min"], twelve = parse_off(df["off"])
    log["off_twelve_hour_rows"] = int(twelve.sum())
    df["race_id"] = pd.to_numeric(df["race_id"].astype(str)).astype(np.int64)

    # exact duplicate runner rows (1988-2004 holds 732 pairs)
    rk = ["file", "race_id", "date", "course", "off", "horse"]
    dup = df.duplicated(rk, keep="first").to_numpy()
    if dup.any():
        inv_ = df.duplicated(rk, keep=False).to_numpy()
        same = np.zeros(len(df), bool)
        same[inv_] = df.loc[inv_].duplicated(list(df.columns), keep="first").to_numpy()
        log["duplicate_runner_rows_dropped"] = {
            "rows": int(dup.sum()), "identical_on_all_read_columns": int((dup & same).sum()),
            "by_file": df.loc[dup, "file"].value_counts().to_dict()}
        df = df.loc[~dup].reset_index(drop=True)
    else:
        log["duplicate_runner_rows_dropped"] = {"rows": 0}

    gkey = ["date", "off_min", "course", "race_id", "off", "file"]
    df["race_key"] = df.groupby(gkey, sort=True, observed=True, dropna=False).ngroup().astype(np.int64)
    df["_row"] = np.arange(len(df))
    df = df.sort_values(["race_key", "_row"], kind="stable").reset_index(drop=True)
    if df.duplicated(["race_key", "horse"]).any():
        raise SystemExit("(race_key, horse) is not unique after de-duplication")
    rkv = df["race_key"].to_numpy()

    # ---- course, region, surface, code, handicap, class
    def base(u):
        b = u.str.replace(r"\s*\(IRE\)\s*$", "", regex=True).str.replace(r"\s*\(AW\)\s*$", "", regex=True)
        return b.map(lambda x: COURSE_ALIASES.get(x, x))
    df["course_base"] = _cat(_map_cat(df["course"], base))
    reg = np.where(df["course_base"].isin(GB_COURSES), "GB",
                   np.where(df["course_base"].isin(IRE_COURSES), "IRE", "OTHER"))
    om = df["off_min"].to_numpy()
    by_time = (reg != "OTHER") & ((om < GBI_FIRST_OFF) | (om >= GBI_LAST_OFF))
    sh = _map_cat(df["horse"], lambda u: u.str.contains(SH_BRED_RX)).astype(bool)
    sh_n = pd.Series(sh.astype(np.int16)).groupby(rkv).transform("sum").to_numpy()
    n_rows = pd.Series(sh).groupby(rkv).transform("size").to_numpy()
    n_ran = pd.Series(parse_num(df["ran"])).groupby(rkv).transform("max").to_numpy()
    sh_share = sh_n / n_rows
    # a partial race (fewer rows than runners, as Australian results are held) needs no minimum
    by_breeding = (reg != "OTHER") & (sh_share > 0.5) & ((sh_n >= SH_MIN_RUNNERS) | (n_rows < n_ran))
    namesake = by_time | by_breeding
    df["namesake"] = namesake
    log["foreign_namesake_rows"] = int(namesake.sum())
    log["foreign_namesake_races"] = {
        "by_off_time": int(pd.Series(by_time).groupby(rkv).any().sum()),
        "by_breeding_only": int(pd.Series(by_breeding & ~by_time).groupby(rkv).any().sum())}
    reg = np.where(namesake, "OTHER", reg)
    df["region"] = pd.Categorical(reg, categories=["GB", "IRE", "OTHER"])
    log["timing"] = {"read": log["read_seconds"], "key_sort": round(time.time() - t0, 1)}
    df["code"] = pd.Categorical(df["type"].astype(str), categories=["Flat", "Hurdle", "Chase", "NH Flat"])
    df["jumps"] = (df["code"] != "Flat").to_numpy()
    aw_name = _map_cat(df["course"], lambda u: u.str.contains(r"\(AW\)")).astype(bool)
    aw_going = (df["course_base"].isin(AW_VENUES).to_numpy() & df["going"].isin(AW_GOINGS).to_numpy()
                & df["code"].isin(["Flat", "NH Flat"]).to_numpy())
    gbi = df["region"].isin(["GB", "IRE"]).to_numpy()
    surf = np.where(~gbi, "", np.where(aw_name | aw_going, "AW",
                                       np.where(df["course_base"].astype(str) == "Laytown", "Sand", "Turf")))
    df["surface"] = pd.Categorical(surf, categories=["AW", "Turf", "Sand", ""])
    log["surface_rule"] = {"aw_by_course_name": int((gbi & aw_name).sum()),
                           "aw_by_going_only": int((gbi & aw_going & ~aw_name).sum())}
    df["arab"] = _map_cat(df["race_name"], lambda u: u.str.contains(
        r"(?i)\barab race\b|\barab selling\b|\bpure[- ]?bred arab|\barabian (?:handicap|stakes|race)\b")).astype(bool)
    hrx = r"handicap|\bh'?cap\b|\bhcp\b"
    hname = _map_cat(df["race_name"], lambda u: u.str.lower().str.contains(hrx)).astype(bool)
    nurs = _map_cat(df["race_name"], lambda u: u.str.lower().str.contains("nursery")).astype(bool)
    df["handicap"] = hname | (nurs & (df["code"] == "Flat").to_numpy())
    log["nursery_named_non_flat_rows"] = int((nurs & (df["code"] != "Flat").to_numpy()).sum())
    df["cls"] = _map_cat(df["class"], lambda u: pd.to_numeric(u.str.extract(r"(\d+)")[0], errors="coerce")).astype(float)

    # ---- field
    ran = pd.Series(parse_num(df["ran"]))
    df["rows"] = ran.groupby(rkv).transform("size").to_numpy().astype(np.int16)
    ran_max = ran.groupby(rkv).transform("max").to_numpy()
    ran_min = ran.groupby(rkv).transform("min").to_numpy()
    log["races_with_varying_ran"] = int(pd.Series(ran_max != ran_min).groupby(rkv).any().sum())
    df["ran"] = ran_max
    df["complete"] = (df["rows"].to_numpy() == df["ran"].to_numpy())

    # ---- positions, dead heats, won share
    pos_raw = df["pos"].astype(str)
    p = parse_num(df["pos"])
    fin = np.isfinite(p) & (p >= 1)
    df["nf_code"] = pd.Categorical(np.where(fin, "", pos_raw.to_numpy()))
    df["pos_raw"] = df["pos"]
    df["pos"] = np.where(fin, p, np.nan)
    df["finished"] = fin
    dh =df.groupby(["race_key", "pos"], sort=False, dropna=True)["pos"].transform("size")
    df["dh_n"] = np.where(fin, dh.fillna(0).to_numpy(), 0).astype(np.int8)
    n_first = pd.Series((df["pos"].to_numpy() == 1).astype(np.int8)).groupby(rkv).transform("sum").to_numpy()
    df["n_first"] = n_first.astype(np.int8)
    df["won"] = position_share(df["pos"].to_numpy(), df["dh_n"].to_numpy(), 1, n_first > 0)

    # ---- starting price
    dec, mark, stat, lad = parse_sp(df["sp"])
    df["sp_raw"] = df["sp"]
    df["sp"] = dec
    df["sp_fav"] = pd.Categorical(mark, categories=["", "F", "J", "C"])
    df["sp_status"] = pd.Categorical(stat, categories=["ok", "missing", "unparsed"])
    df["sp_ladder"] = lad
    inv = np.where(np.isfinite(dec), 1.0 / dec, np.nan)
    s = pd.Series(inv).groupby(rkv)
    all_ok = pd.Series(np.isfinite(dec)).groupby(rkv).transform("all").to_numpy()
    df["sp_all"] = all_ok
    df["book"] = np.where(all_ok, s.transform("sum").to_numpy(), np.nan)
    pre = gbi & (n_first > 0) & df["complete"].to_numpy() & all_ok
    df["gradeable_raw"] = pre
    df["book_low"] = df["book"].to_numpy() < MIN_BOOK
    marked = (mark != "")
    n_mark = pd.Series(marked.astype(np.int16)).groupby(rkv).transform("sum").to_numpy()
    min_sp = pd.Series(dec).groupby(rkv).transform("min").to_numpy()
    off_short = pd.Series(marked & ~np.isclose(dec, min_sp)).groupby(rkv).transform("any").to_numpy()
    df["mark_bad"] = (~df["new_format"].to_numpy()) & all_ok & ((n_mark == 0) | off_short)
    lowr = pd.DataFrame({"k": rkv, "p": pre, "b": df["book_low"].to_numpy(), "m": df["mark_bad"].to_numpy()}).groupby("k").first()
    lowr = lowr[lowr.p]
    log["sp_hygiene_races"] = {"gradeable_raw": int(len(lowr)), "book_low": int(lowr.b.sum()),
                               "mark_bad": int(lowr.m.sum()), "both": int((lowr.b & lowr.m).sum()),
                               "mark_bad_only": int((lowr.m & ~lowr.b).sum())}
    df["gradeable"] = pre & ~df["book_low"].to_numpy() & ~df["mark_bad"].to_numpy()
    log["timing"]["through_sp"] = round(time.time() - t0, 1)

    # ---- ids: horse, jockey, trainer
    nm = _map_cat(df["horse"], norm_name)
    nd = _map_cat(df["dam"], lambda u: norm_name(u, dam=True))
    age = parse_num(df["age"])
    fy = np.where((age >= 1) & (age <= 25), df["year"].to_numpy() - age, np.nan)
    df["foal_year"] = fy
    # build the id string once per distinct (name, dam, foal year if the dam is blank)
    blank = (nd == "")
    fyk = np.where(blank & np.isfinite(fy), fy, -1).astype(np.int32)
    hcd = df["horse"].cat.codes.to_numpy().astype(np.int64)
    dcd = df["dam"].cat.codes.to_numpy().astype(np.int64)
    ndam = int(dcd.max()) + 2
    trip = (hcd * ndam + dcd + 1) * 256 + np.where(fyk >= 0, fyk - 1850, 255)
    code, _ = pd.factorize(trip)
    first = pd.Series(np.arange(len(df))).groupby(code).first().to_numpy()
    u_nm, u_nd, u_y = nm[first], nd[first], fyk[first]
    labels = np.where(u_nd == "", [f"{a}|y{b if b >= 0 else '?'}" for a, b in zip(u_nm, u_y)],
                      [f"{a}|{b}" for a, b in zip(u_nm, u_nd)])
    lab_codes, lab_uniq = pd.factorize(labels)
    df["horse_id"] = pd.Categorical.from_codes(lab_codes[code], categories=lab_uniq)
    log["horse_id_blank_dam_rows"] = int(blank.sum())
    df["sire_n"] = _cat(_map_cat(df["sire"], norm_name))
    df["jockey_key"] = _cat(_map_cat(df["jockey"], person_key))
    df["trainer_key"] = _cat(_map_cat(df["trainer"], person_key))
    log["timing"]["through_horse_id"] = round(time.time() - t0, 1)
    _bridge_people(df, log)
    log["timing"]["through_people"] = round(time.time() - t0, 1)

    # ---- parsed decidable inputs (and same-race figures, flagged by name)
    for raw, new, fn in [("dist", "dist_f", parse_dist), ("wgt", "wgt_lbs", parse_wgt),
                         ("or", "or_num", parse_num), ("draw", "draw_num", parse_num),
                         ("rpr", "rpr_num", parse_num), ("ts", "ts_num", parse_num)]:
        if raw in df.columns:
            df[new] = fn(df[raw])
    if keep_raw:
        df["age_raw"] = df["age"]
    df["age"] = age
    drop = ["_row"] + ([] if keep_raw else ["type", "class"])
    df = df.drop(columns=[c for c in drop if c in df.columns])
    log["load_seconds"] = round(time.time() - t0, 1)
    return df


def _bridge_people(df: pd.DataFrame, log: dict) -> None:
    """jockey_id / trainer_id: the raw name before 2026-05-01; from then on the old-format
    name it maps to, else the new raw name.
    Trainer: the modal last pre-change trainer of the horses a new name trains (at least
    3 such horses and half of them agreeing), else a unique initial+surname match among
    names active in the two years before the change.
    Jockey: the unique initial+surname match only (rides do not follow the horse)."""
    new = df["new_format"].to_numpy()
    lo = pd.Timestamp(NEW_FORMAT_FROM) - pd.DateOffset(years=2)
    recent = (~new) & (df["date"] >= lo).to_numpy()
    hc = df["horse_id"].cat.codes.to_numpy()
    for who in ("jockey", "trainer"):
        cat = df[who].astype("category")
        rc = cat.cat.codes.to_numpy().astype(np.int64)
        names = cat.cat.categories.astype(str)
        kc = df[f"{who}_key"].cat.codes.to_numpy()
        ref = pd.DataFrame({"k": kc[recent], "r": rc[recent]}).drop_duplicates()
        nk = ref.groupby("k")["r"].agg(["nunique", "first"])
        one = nk["nunique"] == 1
        uniq = dict(zip(nk.index[one], nk.loc[one, "first"]))      # key code -> old name code
        mapping, how = {}, {}                                       # new name code -> old name code
        if who == "trainer" and new.any():
            last = pd.Series(rc[~new]).groupby(hc[~new]).last()      # rows are in time order
            nn = pd.DataFrame({"t": rc[new], "h": hc[new]}).drop_duplicates()
            nn["old"] = nn["h"].map(last)
            nn = nn.dropna(subset=["old"])
            for t, grp in nn.groupby("t"):
                vc = grp["old"].value_counts()
                if len(grp) >= 3 and vc.iloc[0] / len(grp) >= 0.5:
                    mapping[int(t)] = int(vc.index[0]); how[int(t)] = "horses"
        for t, k in pd.DataFrame({"t": rc[new], "k": kc[new]}).drop_duplicates().itertuples(index=False):
            if int(t) not in mapping and k in uniq:
                mapping[int(t)] = int(uniq[k]); how[int(t)] = "key"
        out = rc.copy()
        m = pd.Series(rc[new]).map(mapping)
        out[new] = np.where(m.notna(), m.fillna(-1).to_numpy(), rc[new]).astype(np.int64)
        df[f"{who}_id"] = pd.Categorical.from_codes(out, categories=names).remove_unused_categories()
        hw = pd.Series(rc[new]).map(how).fillna("unmapped")
        cnt = pd.Series(rc[new]).value_counts()
        top = [t for t in cnt.index if t in mapping][:8]
        log[f"{who}_bridge"] = {"new_format_rows": int(new.sum()),
                                "by": {k: int(v) for k, v in hw.value_counts().items()},
                                "examples": {names[t]: names[mapping[t]] for t in top}}


def gradeable_races(df: pd.DataFrame) -> pd.DataFrame:
    """One row per gradeable race."""
    r = df[df["gradeable"]]
    return r.groupby("race_key", sort=False).agg(
        date=("date", "first"), year=("year", "first"), region=("region", "first"),
        code=("code", "first"), handicap=("handicap", "first"), ran=("ran", "first"),
        book=("book", "first"))


# ================================================================== checks

def _pct(a, b):
    return f"{100.0 * a / b:.2f}%" if b else "-"


def checks(df: pd.DataFrame, log: dict, root: Path = DATA) -> None:
    P = print
    P("=" * 100)
    P("UK/IRE SP loader: data checks.  python -I scripts/horse/uk_sp_data.py")
    P(f"read {log['read_seconds']}s, load {log['load_seconds']}s, {len(df):,} runner rows, "
      f"{df['race_key'].nunique():,} races, memory {df.memory_usage(deep=True).sum() / 1e9:.2f} GB")
    P(f"cumulative seconds by stage: {log.get('timing')}")

    P("\n-- 0. Files, headers, manifest")
    for name, (rel, lo, hi) in FILES.items():
        f = log["files"].get(name)
        if not f:
            continue
        sub = df[df["file"] == name]
        valid = f["rows_in_file"] - f["repeated_header_rows"]
        man_rows, man_races = MANIFEST[name]
        P(f"  {name}: same 37-column header as raceform.csv: yes | data rows {f['rows_in_file']:,}, "
          f"repeated header rows {f['repeated_header_rows']}, valid {valid:,} (manifest {man_rows:,}: "
          f"{'match' if valid == man_rows else 'DIFFERENT'})")
        P(f"      distinct race_id {sub['race_id'].nunique():,} (manifest {man_races:,}); race keys "
          f"{sub['race_key'].nunique():,}; dates {sub['date'].min().date()} .. {sub['date'].max().date()}")
    P(f"  duplicate runner rows dropped: {log['duplicate_runner_rows_dropped']}")

    P("\n-- 1. Overlaps and duplicates across files")
    ids = df.groupby("race_id")["file"].nunique()
    P(f"  race_id values present in more than one file: {int((ids > 1).sum())}")
    pieces = df.groupby(["file", "race_id"], observed=True)["race_key"].nunique()
    P(f"  race_id values that name more than one race (same file): {int((pieces > 1).sum())} "
      f"({pieces[pieces > 1].groupby(level=0, observed=True).size().to_dict()})")
    sub = df[df["region"] != "OTHER"]
    dh = sub.groupby(["date", "horse_id"], observed=True).size()
    two = dh[dh > 1]
    P(f"  GB/IRE: same horse twice on one date: {len(two)} (horse, date) pairs")
    if len(two):
        x = sub.set_index(["date", "horse_id"]).loc[two.index].reset_index()
        P(f"      rows by file {x['file'].value_counts().to_dict()}; of those rows, in races with no result: "
          f"{int((x['n_first'] == 0).sum())}")
    rr = df.groupby("race_key").agg(region=("region", "first"), file=("file", "first"),
                                    nf=("n_first", "first"), complete=("complete", "first"))
    P("  races by number of runners placed first (0 = no result):")
    P("    " + pd.crosstab([rr["region"], rr["file"]], rr["nf"].clip(upper=3)).to_string().replace("\n", "\n    "))
    P(f"  races with varying `ran` inside one race key: {log['races_with_varying_ran']}")

    P("\n-- 2. Positions and dead heats")
    P("  non-finisher codes (rows): " + str(df.loc[~df["finished"], "nf_code"].value_counts().to_dict()))
    fin = df[df["finished"] & df["gradeable"]]
    grp = fin.groupby(["race_key", "pos"]).size()
    dhg = grp[grp > 1]
    P(f"  gradeable races: dead-heat groups {len(dhg):,}; by size {dhg.value_counts().to_dict()}; "
      f"at position {dhg.reset_index()['pos'].clip(upper=5).value_counts().sort_index().to_dict()}")
    w = dhg.reset_index()
    w = w[(w["pos"] == 1) & (w[0] == 2)]["race_key"]
    nxt = fin[fin["race_key"].isin(w) & (fin["pos"] > 1)].groupby("race_key")["pos"].min()
    P(f"  after a two-way dead heat for first, the next position is {nxt.value_counts().sort_index().to_dict()}")
    wsum = df[df["n_first"] > 0].groupby("race_key")["won"].sum()
    P(f"  won share sums to 1 in {_pct((np.abs(wsum - 1) < 1e-9).sum(), len(wsum))} of races with a result")
    pl = placed(df)
    places, _ = place_terms(df["ran"].to_numpy(), df["handicap"].to_numpy())
    t = pd.DataFrame({"k": df["race_key"].to_numpy(), "s": pl, "p": places, "f": df["finished"].to_numpy(),
                      "gr": df["gradeable"].to_numpy()})
    t = t[t["gr"]].groupby("k").agg(s=("s", "sum"), p=("p", "first"), f=("f", "sum"))
    full = t[t["f"] >= t["p"]]
    P(f"  place share (standard terms) sums to the places paid in {_pct((np.abs(full.s - full.p) < 1e-9).sum(), len(full))} "
      f"of gradeable races with at least that many finishers")
    P(f"  disqualified rows (DSQ) {int((df['nf_code'] == 'DSQ').sum()):,}; position 0 rows "
      f"{int((df['nf_code'] == '0').sum()):,} ({df.loc[df['nf_code'] == '0', 'region'].value_counts().to_dict()}). "
      "Results are the amended official ones; a later disqualification can differ from how bets were settled.")
    dash = df[df["nf_code"] == "-"]
    dw = dash[dash["n_first"] > 0]
    P(f"  '-' rows (no result): {len(dash)}, with a priced SP: {int(np.isfinite(dash['sp']).sum())}; "
      f"in races with a winner: {len(dw)} (regions {dw['region'].value_counts().to_dict()}, gradeable "
      f"{int(dw['gradeable'].sum())}; they grade won=0, the winner being known)")

    P("\n-- 3. SP parsing")
    P("  status by year x region (rows):")
    st = pd.crosstab([df["year"]], [df["region"], df["sp_status"]])
    P("    " + st.to_string().replace("\n", "\n    "))
    raw = df["sp_raw"].astype(str)
    P(f"  distinct SP strings: {raw.nunique():,} over every region "
      f"({raw.str.replace(r'[FJC]$', '', regex=True).nunique():,} once the F/J/C marker is removed); "
      f"GB/IRE rows: {raw[(df['region'] != 'OTHER').to_numpy()].nunique():,}")
    un = df[df["sp_status"] == "unparsed"]["sp_raw"].astype(str).value_counts()
    P(f"  unparsed strings: {un.to_dict()}")
    g = (df.loc[df["region"] != "OTHER", ["race_key", "rows", "file"]]
         .assign(m=(df["sp_status"] != "ok").to_numpy()[(df["region"] != "OTHER").to_numpy()])
         .groupby("race_key").agg(m=("m", "sum"), n=("rows", "first"), file=("file", "first")))
    miss = g[g["m"] > 0]
    P(f"  GB/IRE races with an unpriced runner: {len(miss):,}; of them every runner unpriced: "
      f"{int((miss.m == miss.n).sum()):,}; one or some runners: {int((miss.m < miss.n).sum()):,}")
    P("  favourite marker by period (rows): " + str(pd.crosstab(df["new_format"], df["sp_fav"]).to_dict()))
    g = df[np.isfinite(df["sp"])].groupby("race_key").agg(lad=("sp_ladder", "mean"), region=("region", "first"),
                                                          file=("file", "first"))
    P("  races by share of runners priced on the UK bookmaker ladder (>=0.9 / 0.5-0.9 / <0.5):")
    cut = pd.cut(g["lad"], [-0.01, 0.5, 0.9, 1.0], labels=["<0.5", "0.5-0.9", ">=0.9"])
    P("    " + pd.crosstab([g["region"], g["file"]], cut).to_string().replace("\n", "\n    "))
    off = df[(df["region"] != "OTHER") & np.isfinite(df["sp"]) & ~df["sp_ladder"]]["sp_raw"].astype(str)
    P(f"  GB/IRE priced runners off the ladder: {len(off):,}; top {off.str.replace(r'[FJC]$', '', regex=True).value_counts().head(12).to_dict()}")
    gi = df[(df["region"] != "OTHER") & np.isfinite(df["sp"])]
    share = (~gi["sp_ladder"]).groupby(gi["year"]).mean() * 100
    P("  GB/IRE priced runners off the ladder, % by year: "
      + ", ".join(f"{int(y)} {v:.2f}" for y, v in share.items()))
    low = g[(g["region"] != "OTHER") & (g["lad"] < 0.5)]
    if len(low):
        x = df[df["race_key"].isin(low.index)].groupby("race_key").first()
        P(f"  GB/IRE races with most prices off the ladder: {len(low)}; courses {x['course'].astype(str).value_counts().head(8).to_dict()}")

    P("\n-- 4. Codes, regions, surface, handicap")
    races = df.groupby("race_key").first()
    P("  races by region x file:\n    " + pd.crosstab(races["region"], races["file"]).to_string().replace("\n", "\n    "))
    P("  races by code x region:\n    " + pd.crosstab(races["code"], races["region"]).to_string().replace("\n", "\n    "))
    rows_c = df.groupby(["course", "region"], observed=True).size().rename("rows").reset_index()
    for r in ("GB", "IRE"):
        x = rows_c[rows_c.region == r].sort_values("rows", ascending=False)
        P(f"  {r}: {x['course'].nunique()} course labels, {int(x.rows.sum()):,} rows: "
          + ", ".join(f"{a}={b:,}" for a, b in zip(x.course.astype(str), x.rows)))
    missing_sets = sorted((GB_COURSES | IRE_COURSES) - set(df["course_base"].astype(str)))
    P(f"  GB/IRE set names never seen: {missing_sets}")
    x = rows_c[(rows_c.region == "OTHER")]
    x = x[~x.course.astype(str).str.contains(r"\)\s*$")].sort_values("rows", ascending=False).head(40)
    P("  OTHER, unsuffixed, largest 40: " + ", ".join(f"{a}={b:,}" for a, b in zip(x.course.astype(str), x.rows)))
    ns = races[races["namesake"]]
    P(f"  foreign namesakes moved to OTHER (a GB/IRE course name, off before 10:00 or from 22:00, or most "
      f"runners Southern-Hemisphere-bred): {len(ns):,} races {log['foreign_namesake_races']}, "
      f"{log['foreign_namesake_rows']:,} rows; by course x file "
      f"{ns.groupby(['course', 'file'], observed=True).size().sort_values(ascending=False).head(10).to_dict()}")
    if len(ns):
        P("    sample: " + "; ".join(f"{d.date()} {c} {o} {n[:40]}" for d, c, o, n in
                                    zip(ns["date"].head(6), ns["course"].astype(str), ns["off"].astype(str),
                                        ns["race_name"].astype(str))))
    cs = races[races["region"] == "GB"].groupby("year")["cls"].apply(lambda s: round(float(s.notna().mean()), 4))
    P(f"  GB races with a class, share by year: {cs.to_dict()}")
    gb05 = races[(races["region"] == "GB") & (races["date"] >= "1995-01-01") & races["cls"].isna()]
    P(f"  GB races from 1995 (class >99.8% filled) with no class: {len(gb05)}; by course "
      f"{gb05['course'].astype(str).value_counts().head(12).to_dict()}; by year {gb05['year'].value_counts().sort_index().to_dict()}")
    if len(gb05):
        P("    sample: " + "; ".join(f"{d.date()} {c} {n[:50]}" for d, c, n in
                                    zip(gb05["date"].head(8), gb05["course"].astype(str), gb05["race_name"].astype(str))))
    P(f"  surface rule (GB/IRE rows): {log['surface_rule']}; races "
      + str(pd.crosstab(races["surface"], races["region"]).to_dict()))
    has_band = races["rating_band"].astype(str) != "" if "rating_band" in races else pd.Series(False, index=races.index)
    per = np.where(races["new_format"], "2026-05+", races["file"].astype(str))
    P("  handicap flag x rating band present (races), by period, GB+IRE:")
    m = races["region"] != "OTHER"
    P("    " + pd.crosstab([pd.Series(per[m], name="period"), races.loc[m, "handicap"]],
                           has_band[m].rename("band")).to_string().replace("\n", "\n    "))
    P(f"  'nursery' in a non-Flat race name (not counted as handicap): {log['nursery_named_non_flat_rows']} rows")
    ar = races[races["arab"] & (races["region"] != "OTHER")]
    P(f"  Arabian-horse races at GB/IRE courses (flag `arab`, kept in gradeable): {len(ar)}; "
      f"by year {ar['year'].value_counts().sort_index().to_dict()}")

    P("\n-- 5. Field size")
    P("  races with rows == ran, by region x file:")
    P("    " + (pd.crosstab(rr["region"], rr["file"], values=rr["complete"], aggfunc="mean") * 100).round(2).to_string().replace("\n", "\n    "))
    inc = rr[(rr["region"] != "OTHER") & ~rr["complete"]]
    P(f"  GB/IRE races with rows != ran: {len(inc):,}; by file {inc['file'].value_counts().to_dict()}")
    yr = df.groupby("race_key")["year"].first()
    inc2 = inc.assign(year=yr.loc[inc.index].to_numpy())
    P(f"      by region x year (top): {inc2.groupby(['region', 'year'], observed=True).size().sort_values(ascending=False).head(12).to_dict()}")
    allyears = range(int(df["year"].min()), int(df["year"].max()) + 1)
    for r in ("GB", "IRE", "OTHER"):
        have = set(df.loc[df["region"] == r, "year"].unique())
        P(f"  years with NO {r} rows: {[y for y in allyears if y not in have]}")
    P(f"  SP hygiene on otherwise-gradeable GB/IRE races (NOT gradeable): {log['sp_hygiene_races']}")
    rk1 = df[df["gradeable_raw"]].groupby("race_key").agg(year=("year", "first"), b=("book_low", "first"),
                                                          m=("mark_bad", "first"))
    P("      excluded by year (book_low or mark_bad): "
      + str(rk1[rk1.b | rk1.m].groupby("year").size().to_dict()))
    gr = gradeable_races(df)
    P(f"  gradeable races: {len(gr):,} of {rr[rr.region != 'OTHER'].shape[0]:,} GB/IRE races; "
      f"runners {int(df['gradeable'].sum()):,}")
    P("  gradeable races by year x region:\n    "
      + pd.crosstab(gr["year"], gr["region"]).T.to_string().replace("\n", "\n    "))

    P("\n-- 6. SP book on gradeable races (sum of 1/decimal SP)")
    def bk(s):
        return pd.Series({"races": len(s), "median": s.median(), "mean": s.mean(),
                          "p05": s.quantile(0.05), "p95": s.quantile(0.95),
                          "over_1.6": int((s > 1.6).sum())})
    for r in ("GB", "IRE"):
        x = gr[gr["region"] == r].groupby("year")["book"].apply(bk).unstack()
        P(f"  {r} by year:\n    " + x.round(3).to_string().replace("\n", "\n    "))
    bins = pd.cut(gr["ran"], [1, 4, 7, 11, 15, 19, 24, 50], labels=["2-4", "5-7", "8-11", "12-15", "16-19", "20-24", "25+"])
    x = gr.groupby([gr["region"], bins], observed=True)["book"].apply(bk).unstack()
    P("  by field size:\n    " + x.round(3).to_string().replace("\n", "\n    "))
    x = gr.groupby([gr["region"], gr["code"]], observed=True)["book"].apply(bk).unstack()
    P("  by code:\n    " + x.round(3).to_string().replace("\n", "\n    "))
    gr2 = gr.assign(per_runner=(gr["book"] - 1) / gr["ran"])
    P("  margin per runner, (book-1)/ran, median by field size: "
      + str(gr2.groupby(bins, observed=True)["per_runner"].median().round(4).to_dict()))

    P("\n-- 7. Horse, jockey and trainer ids")
    old = ~df["new_format"]
    P("  horse_id = normalised name | normalised dam (no suffix, lower case); name | foal year where the dam is blank "
      f"({log['horse_id_blank_dam_rows']:,} rows)")
    h = df.groupby("horse_id", observed=True).agg(fmin=("foal_year", "min"), fmax=("foal_year", "max"),
                                                 sires=("sire_n", "nunique"))
    P(f"  ids {len(h):,}; foal-year spread 0: {int(((h.fmax - h.fmin) == 0).sum()):,}, 1: {int(((h.fmax - h.fmin) == 1).sum()):,}, "
      f">=2 (two horses under one id): {int(((h.fmax - h.fmin) >= 2).sum()):,}; ids with >1 sire: {int((h.sires > 1).sum()):,}")
    o = df[old]
    rawn = o.groupby("horse", observed=True)["horse_id"].nunique()
    P(f"  before 2026-05: suffixed names {len(rawn):,}; split over >1 id (dam written two ways): {int((rawn > 1).sum()):,}")
    held = o.groupby("horse_id", observed=True)["horse"].nunique()
    many = held[held > 1].index
    cs = o[o["horse_id"].isin(many)].groupby("horse_id", observed=True)["horse"].agg(lambda s: s.astype(str).str.lower().nunique())
    P(f"  ids holding >1 suffixed name: {len(many):,}; of them differing only in letter case: {int((cs == 1).sum()):,}; "
      f"the rest (suffix differs, same name and dam): {int((cs > 1).sum()):,}")
    P(f"  age: blank or outside 1-25 on {int((~np.isfinite(df['foal_year'])).sum()):,} rows")
    nw = df[df["new_format"]]
    if len(nw):
        seen = set(df.loc[old, "horse_id"].astype(str))
        lk = nw["horse_id"].astype(str).isin(seen)
        P(f"  from 2026-05-01: {len(nw):,} rows, horse id seen before the change: {_pct(lk.sum(), len(nw))}; "
          f"by age {lk.groupby(nw['age'].clip(upper=6)).mean().round(3).to_dict()}")
        g2 = (nw["region"] != "OTHER").to_numpy()
        P(f"      GB/IRE only: {int(g2.sum()):,} rows, seen before: {_pct(lk[g2].sum(), g2.sum())}; by age "
          f"{lk[g2].groupby(nw['age'][g2].clip(upper=6)).mean().round(3).to_dict()}")
        for who in ("jockey", "trainer"):
            b = log[f"{who}_bridge"]
            P(f"  {who}: rows from 2026-05-01 {b['new_format_rows']:,} mapped {b['by']}; top mappings {b['examples']}")
            ref = df[(~df['new_format']) & (df['date'] >= pd.Timestamp(NEW_FORMAT_FROM) - pd.DateOffset(years=2))]
            amb = ref.groupby(f"{who}_key", observed=True)[who].nunique()
            P(f"      initial+surname keys active in the two years before: {len(amb):,}, of which >1 full name: {int((amb > 1).sum()):,}")
    P(f"  distinct raw names: jockeys {df['jockey'].nunique():,}, trainers {df['trainer'].nunique():,}; "
      f"ids: jockeys {df['jockey_id'].nunique():,}, trainers {df['trainer_id'].nunique():,}")

    P("\n-- 8. Off times")
    P(f"  12-hour rows converted (+12 h): {log['off_twelve_hour_rows']:,}")
    x = df[df["region"] != "OTHER"].groupby("file", observed=True)["off_min"].describe()[["min", "max"]] / 60
    P("  GB/IRE off range in hours by file: " + str(x.round(2).to_dict()))
    P("  parsed inputs blank or unparsed (rows): " + str({c: int((~np.isfinite(df[c])).sum()) for c in
                                                          ["dist_f", "wgt_lbs", "or_num", "draw_num"] if c in df}))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=str, default=None, help="e.g. 2015-2026 or 2019")
    a = ap.parse_args(argv)
    years = None
    if a.years:
        lo, _, hi = a.years.partition("-")
        years = range(int(lo), int(hi or lo) + 1)
    log: dict = {}
    df = load(cols=DEFAULT_EXTRA + ["rpr", "ts"], years=years, log=log)
    checks(df, log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
