"""NBA count props: one frame builder for training, the backtest and the live card.

THE DESIGN IS models/nhl_props.py's, carried to basketball. Every input is a
weighted mean of EARLIER rows, or a fact known before the decision; a game
not yet played is scored by appending a row with no result and running the
same arithmetic, so a training row and a live row are one computation.

WHAT IS DIFFERENT FROM HOCKEY, AND WHY

  MINUTES FIRST. A basketball player's count is his minutes times his rate,
  and minutes move with who else is available. So the frame carries
  (a) his own minutes history -- over the games he played, and over his
      TEAM's games with a zero for every game he missed, which is how a
      chronic absence stops counting as "missing";
  (b) TEAMMATE AVAILABILITY AT THE DECISION TIME, read from the official
      injury report: the teammates listed Out or Doubtful in the latest report
      filed at or before the decision, each weighted by his minutes (and
      usage-minutes) over the team's recent games, zeros included; the
      teammates returning (available tonight, missing from recent games); and
      the same for the opponent;
  (c) the schedule (rest, back-to-backs, road trips: known in advance);
  (d) the game's spread and total at the decision time when lines are held.

  THE INJURY REPORT IS READ AS A WHOLE REPORT, NOT A ROW PER PLAYER. A player
  becomes available by dropping off the report, so the status of every player
  on a team is "whatever the team's latest submitted report says, or nothing".
  A team whose latest report reads NOT YET SUBMITTED falls back to its latest
  submitted one. A status that is not one of the five real ones is unknown.

  TWO MODELS OF THE MEAN, CHOSEN ON DEVIANCE. `two_stage`: a minutes model
  (squared error) and a per-minute rate model per base stat (Poisson with
  log-minutes as the exposure), the mean = predicted minutes x predicted rate,
  summed over a market's parts. `direct`: one Poisson gradient-boosted mean per
  market on the same frame. The lab picks per market on out-of-sample
  deviance in the seasons it may choose on, never on profit.

  THE DISTRIBUTION. Negative binomial (var = mu + alpha mu^2) with alpha fitted
  by maximum likelihood on predictions for a season the model had not seen
  (the previous walk-forward fold), so the tails are as wide as they are out of
  sample. alpha = 0 is Poisson.

  DOUBLE- AND TRIPLE-DOUBLES are a binary model on the same frame (logistic
  gradient boosting); the lab compares that against the component counts
  treated as independent.

  NAMES. A price finds its player by name, restricted to the two teams in the
  game: the letters-only key, then the key with Jr/Sr/II/III stripped, a short
  nickname table, the tokens in any order ("Murray Dejounte"), and an initial
  plus a surname ("J. Isaac"). Any step that finds more than one player on the
  two rosters REFUSES the name: two players never share a price (the NHL
  namesake defect, +89.8u phantom).

SETTLEMENT (DraftKings house rules). A player who does not play is void. A
whole-number line can push. Double-double: 10+ in two of points, rebounds,
assists, steals, blocks; triple-double: three.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import nbinom, poisson

CACHE = Path(__file__).resolve().parent.parent / "data" / "local" / "nba"
BOOK = "draftkings"
MIN_GAMES = 10                     # career games played before a player is scored
FIRST_TRAIN_SEASON = 2019          # the first box-score season held
DECISION_LEAD_MIN = 60             # props are decided at tip minus this when no snapshot exists
BASE_STATS = ("points", "rebounds", "assists", "fg3_made", "steals", "blocks", "turnovers")
REAL_STATUS = ("Out", "Doubtful", "Questionable", "Probable", "Available")
POS = ("G", "F", "C")
UPCOMING_PREFIX = "UPCOMING_"


@dataclass(frozen=True)
class Spec:
    model_id: str
    market: str                    # the Odds API market key
    parts: tuple[str, ...]         # base stats summed to settle (count markets)
    label: str
    kind: str = "count"            # 'count' | 'dd' | 'td'


SPECS: tuple[Spec, ...] = (
    Spec("nba_prop_points", "player_points", ("points",), "Points"),
    Spec("nba_prop_rebounds", "player_rebounds", ("rebounds",), "Rebounds"),
    Spec("nba_prop_assists", "player_assists", ("assists",), "Assists"),
    Spec("nba_prop_threes", "player_threes", ("fg3_made",), "Threes"),
    Spec("nba_prop_pra", "player_points_rebounds_assists", ("points", "rebounds", "assists"), "Pts+Reb+Ast"),
    Spec("nba_prop_pr", "player_points_rebounds", ("points", "rebounds"), "Pts+Reb"),
    Spec("nba_prop_pa", "player_points_assists", ("points", "assists"), "Pts+Ast"),
    Spec("nba_prop_ra", "player_rebounds_assists", ("rebounds", "assists"), "Reb+Ast"),
    Spec("nba_prop_blocks", "player_blocks", ("blocks",), "Blocks"),
    Spec("nba_prop_steals", "player_steals", ("steals",), "Steals"),
    Spec("nba_prop_stocks", "player_blocks_steals", ("blocks", "steals"), "Blocks+Steals"),
    Spec("nba_prop_turnovers", "player_turnovers", ("turnovers",), "Turnovers"),
    Spec("nba_prop_double_double", "player_double_double",
         ("points", "rebounds", "assists", "steals", "blocks"), "Double-Double", "dd"),
    Spec("nba_prop_triple_double", "player_triple_double",
         ("points", "rebounds", "assists", "steals", "blocks"), "Triple-Double", "td"),
)
BY_MARKET: dict[str, Spec] = {s.market: s for s in SPECS}
COUNT_SPECS = tuple(s for s in SPECS if s.kind == "count")


def books() -> tuple[str, ...]:
    """The books a pick may be decided at (config.BEST_LINE_BOOKMAKERS: never Pinnacle or Bovada)."""
    import config
    return tuple(config.BEST_LINE_BOOKMAKERS)


# ── names ────────────────────────────────────────────────────────────────────

_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b\.?")
# Book spelling -> box-score spelling, for the names the letters-only key
# misses on the bought history (measured: each is one player, 300-1,500 rows).
NICKNAMES = {
    "nicolas claxton": "nic claxton", "carlton carrington": "bub carrington",
    "herb jones": "herbert jones", "ron holland": "ronald holland", "moe wagner": "moritz wagner",
    "vincent williams": "vince williams", "cameron thomas": "cam thomas",
    "mohamed bamba": "mo bamba", "cam johnson": "cameron johnson", "obadiah toppin": "obi toppin",
    "cameron reddish": "cam reddish", "trayce jackson": "trayce jacksondavis",
    "gregory jackson": "gg jackson", "nahshon hyland": "bones hyland", "james huff": "jay huff",
    "danilo galinari": "danilo gallinari", "nicholas batum": "nicolas batum",
    "brook robert lopez": "brook lopez", "christian james mccollum": "cj mccollum",
    "alfred joel horford reynoso": "al horford", "eric ambrose gordon": "eric gordon",
    "bojan bogdanovich": "bojan bogdanovic", "thor jt": "jt thor",
    "kentavious caldwell pope": "kentavious caldwellpope", "caldwell pope kentavious": "kentavious caldwellpope",
}


def _flat(name) -> str:
    return unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()


def name_key(name) -> str:
    """Letters only, accents and case folded."""
    return "".join(c for c in _flat(name) if c.isalpha())


def base_key(name) -> str:
    """name_key with Jr / Sr / II / III / IV stripped, and the parenthesised team a book appends."""
    s = re.sub(r"\(.*?\)", " ", _flat(name)).replace(",", " ")
    return "".join(c for c in _SUFFIX.sub(" ", s) if c.isalpha())


def _tokens(name) -> list[str]:
    s = re.sub(r"\(.*?\)", " ", _flat(name)).replace(",", " ").replace("-", " ")
    s = _SUFFIX.sub(" ", s)
    return [t for t in ("".join(c for c in w if c.isalpha()) for w in s.split()) if t]


def token_key(name) -> str:
    """The name's words in sorted order: 'Murray Dejounte' and 'Dejounte Murray' agree."""
    return " ".join(sorted(_tokens(name)))


def alias_key(name) -> str:
    t = " ".join(_tokens(name))
    return name_key(NICKNAMES.get(t, t))


def initial_key(name) -> str | None:
    """'J. Isaac' -> 'j|isaac' (a first initial and a surname); None for anything else."""
    t = _tokens(name)
    if len(t) >= 2 and len(re.sub(r"[^a-z]", "", _flat(name).split()[0])) == 1:
        return f"{t[0][0]}|{''.join(t[1:])}"
    return None


def _initial_of_full(name) -> str | None:
    t = _tokens(name)
    return f"{t[0][0]}|{''.join(t[1:])}" if len(t) >= 2 else None


def match_names(priced: pd.DataFrame, roster: pd.DataFrame) -> pd.DataFrame:
    """Attach a player_id to each (game_id, player_name) a book priced, or refuse it.

    `priced`: game_id, player_name. `roster`: game_id, player_id, player_name --
    everyone who could be the player (in the backtest: both teams' players this
    season and last, by game). Each rule is tried in turn; a rule that finds two
    players is a refusal, not a fall-through. Returns priced + player_id +
    how ('key', 'base', 'alias', 'tokens', 'initial', 'shared' = refused,
    'none' = nobody).
    """
    r = roster[["game_id", "player_id", "player_name"]].dropna().drop_duplicates(["game_id", "player_id"])
    names = priced[["game_id", "player_name"]].drop_duplicates().reset_index(drop=True)
    names["player_id"], names["how"] = None, "none"
    rules = (("key", name_key, name_key), ("base", base_key, base_key), ("alias", alias_key, base_key),
             ("tokens", token_key, token_key), ("initial", initial_key, _initial_of_full))
    # each distinct name is keyed once, not once per game
    uniq_r = r.player_name.drop_duplicates()
    uniq_p = names.player_name.drop_duplicates()
    open_ = np.ones(len(names), dtype=bool)
    for how, price_fn, roster_fn in rules:
        rmap = dict(zip(uniq_r, uniq_r.map(roster_fn)))
        pmap = dict(zip(uniq_p, uniq_p.map(price_fn)))
        rk = r.assign(k=r.player_name.map(rmap)).dropna(subset=["k"])
        rk = rk[rk.k != ""]
        hits = rk.groupby(["game_id", "k"]).player_id.agg(["nunique", "first"]).reset_index()
        cand = names.assign(k=names.player_name.map(pmap), _i=np.arange(len(names)))[open_]
        cand = cand.dropna(subset=["k"])
        cand = cand[cand.k != ""].merge(hits, on=["game_id", "k"])
        one = cand[cand["nunique"] == 1]
        two = cand[cand["nunique"] > 1]
        names.loc[one._i.values, "player_id"] = one["first"].values
        names.loc[one._i.values, "how"] = how
        names.loc[two._i.values, "how"] = "shared"
        open_[cand._i.values] = False
    return priced.merge(names, on=["game_id", "player_name"], how="left")


# ── loading ──────────────────────────────────────────────────────────────────

TABLES = ("nba_games", "nba_schedule", "nba_player_game_log", "nba_player_game_adv",
          "nba_game_inactives", "nba_injury_report", "player_positions")


def load_cache(path: Path | str = CACHE, with_props: bool = False, with_lines: bool = True) -> dict:
    """The research cache (scripts/nba_research_cache.py writes it from Supabase)."""
    p = Path(path)
    out = {t: pd.read_parquet(p / f"{t}.parquet") for t in TABLES}
    if with_props:
        out["nba_props"] = pd.read_parquet(p / "nba_props.parquet")
    if with_lines and (p / "nba_odds.parquet").exists():
        out["nba_odds"] = pd.read_parquet(p / "nba_odds.parquet")
    return out


def _utc(s) -> pd.Series:
    return pd.to_datetime(s, utc=True, format="mixed")


# ── the regular-season box, every rostered player ────────────────────────────

def box_panel(data: dict) -> pd.DataFrame:
    """One row per (game, player) for everyone on a regular-season roster: played,
    did not play, or inactive. Stats are NaN unless he played."""
    adv = data["nba_player_game_adv"]
    adv = adv[adv.game_type == "regular"]
    log = data["nba_player_game_log"]
    stats = ["points", "rebounds", "offensive_reb", "defensive_reb", "assists", "steals", "blocks",
             "turnovers", "fg_made", "fg_att", "fg3_made", "fg3_att", "ft_made", "ft_att"]
    a = adv[["game_id", "player_id", "player_name", "season", "game_date", "team", "opponent", "is_home",
             "position", "is_starter", "played", "minutes_exact", "usage_pct", "fouls"]].copy()
    a = a.merge(log[["game_id", "player_id"] + stats], on=["game_id", "player_id"], how="left")
    ina = data["nba_game_inactives"]
    ina = ina[ina.game_type == "regular"][["game_id", "player_id", "player_name", "team", "season", "game_date"]]
    ina = ina.dropna(subset=["player_id"]).merge(
        a[["game_id", "team", "opponent", "is_home"]].drop_duplicates(["game_id", "team"]), on=["game_id", "team"])
    ina = ina[~ina.set_index(["game_id", "player_id"]).index.isin(a.set_index(["game_id", "player_id"]).index)]
    ina = ina.assign(played=False, is_starter=0, minutes_exact=0.0)
    b = pd.concat([a, ina], ignore_index=True)
    b["played"] = b.played.fillna(False).astype(bool)
    b["minutes_exact"] = b.minutes_exact.fillna(0.0).where(b.played, 0.0)
    b["is_home"] = b.is_home.astype(float)
    b["game_date"] = pd.to_datetime(b.game_date)
    b["is_starter"] = b.is_starter.fillna(0).astype(float)
    for c in stats + ["usage_pct", "fouls"]:
        b[c] = pd.to_numeric(b[c], errors="coerce").where(b.played)
    return b


def settle_value(spec: Spec, rows: pd.DataFrame) -> pd.Series:
    """The number the market settles on: a count, or 1/0 for a double- or triple-double."""
    if spec.kind == "count":
        return rows[list(spec.parts)].sum(axis=1, min_count=len(spec.parts))
    tens = (rows[list(spec.parts)] >= 10).sum(axis=1)
    need = 2 if spec.kind == "dd" else 3
    return (tens >= need).astype(float).where(rows[list(spec.parts)].notna().all(axis=1))


# ── schedule and teams ───────────────────────────────────────────────────────

def team_games(data: dict, upcoming: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per (game, team) of the regular season (and tonight's games): when it starts,
    the opponent, home, and the schedule facts known in advance."""
    g = data["nba_games"]
    g = g[g.game_id.isin(data["nba_schedule"].query("game_type in ['regular', 'cup_final']").game_id)
          | g.game_id.isin(data["nba_player_game_adv"].game_id)]
    g = g[["game_id", "season", "game_date", "home_team", "away_team", "commence_time"]].copy()
    if upcoming is not None and len(upcoming):
        u = upcoming[["game_id", "season", "game_date", "home_team", "away_team", "commence_time"]]
        g = pd.concat([g[~g.game_id.isin(u.game_id)], u], ignore_index=True)
    h = g.rename(columns={"home_team": "team", "away_team": "opponent"}).assign(is_home=1.0)
    a = g.rename(columns={"away_team": "team", "home_team": "opponent"}).assign(is_home=0.0)
    t = pd.concat([h, a], ignore_index=True).dropna(subset=["team"])
    t["game_date"] = pd.to_datetime(t.game_date)
    t["tip"] = _utc(t.commence_time)
    t = t.sort_values(["team", "tip", "game_id"]).reset_index(drop=True)
    grp = t.groupby("team", sort=False)
    prev = grp.game_date.shift(1)
    t["rest"] = (t.game_date - prev).dt.days.clip(upper=7).fillna(7)
    t["b2b"] = (t.rest == 1).astype(float)
    t["g4d"] = _games_in_window(t, 3)     # games in the last four days, tonight included
    away = 1.0 - t.is_home
    seg = (t.is_home != grp.is_home.shift(1)).astype(int).groupby(t.team).cumsum()
    t["road_trip"] = away.groupby([t.team, seg]).cumsum() * away   # this game's place in a road run (0 at home)
    return t


def _games_in_window(t: pd.DataFrame, days: int) -> np.ndarray:
    """Games this team plays in the `days` days before tonight, tonight included."""
    out = np.zeros(len(t))
    for _, idx in t.groupby("team", sort=False).indices.items():
        d = t.game_date.values[idx].astype("datetime64[D]").astype(np.int64)
        lo = np.searchsorted(d, d - days, side="left")
        out[idx] = np.arange(len(idx)) - lo + 1
    return out


# ── injury report as of the decision ─────────────────────────────────────────

def injury_asof(inj: pd.DataFrame, decisions: pd.DataFrame) -> pd.DataFrame:
    """Every player listed for a team in its latest SUBMITTED report filed at or before the decision.

    `decisions`: game_id, decision_ts (UTC). Returns game_id, team, player_id,
    player_name, status, report_ts. A team with no row is a team whose report
    lists nobody (or for which no report exists: see `injury_coverage`).
    """
    r = inj[inj.game_id.isin(decisions.game_id)][["game_id", "team", "report_ts", "player_id",
                                                  "player_name", "status"]].copy()
    r = r.merge(decisions[["game_id", "decision_ts"]], on="game_id")
    r = r[r.report_ts <= r.decision_ts]
    r["submitted"] = r.status != "NOT YET SUBMITTED"
    sub = r[r.submitted].groupby(["game_id", "team"]).report_ts.max().rename("use_ts")
    r = r.merge(sub, on=["game_id", "team"])
    r = r[(r.report_ts == r.use_ts) & r.status.isin(REAL_STATUS)]
    return r[["game_id", "team", "player_id", "player_name", "status", "report_ts"]].drop_duplicates(
        ["game_id", "team", "player_id", "player_name"])


def injury_coverage(inj: pd.DataFrame, decisions: pd.DataFrame) -> pd.Series:
    """True for a game with at least one report filed at or before its decision."""
    r = inj[inj.game_id.isin(decisions.game_id)][["game_id", "report_ts"]].merge(
        decisions[["game_id", "decision_ts"]], on="game_id")
    seen = set(r[r.report_ts <= r.decision_ts].game_id)
    return decisions.game_id.isin(seen)


# ── game lines as of the decision ────────────────────────────────────────────

def lines_asof(odds: pd.DataFrame | None, decisions: pd.DataFrame) -> pd.DataFrame:
    """The home spread and the total at the decision: each book's latest pre-game quote at or before
    it (no older than 12 hours), the median across books. Books are stamped at different instants,
    so "the latest snapshot" alone would often be one book.

    `spread_home` is the HOME number (CLAUDE.md 4). NaN where no line is held.
    """
    cols = ["game_id", "spread_home", "total_line"]
    if odds is None or odds.empty:
        return pd.DataFrame(columns=cols)
    o = odds[odds.game_id.isin(decisions.game_id) & odds.market.isin(["spreads", "totals"])].copy()
    if "snapshot_type" in o.columns:
        o = o[o.snapshot_type.astype(str) != "in_play"]
    o["snap"] = _utc(o.snapshot_at)
    o = o.merge(decisions[["game_id", "decision_ts"]], on="game_id")
    # each book's latest quote at or before the decision, no older than 12 hours
    o = o[(o.snap <= o.decision_ts) & (o.snap >= o.decision_ts - pd.Timedelta(hours=12))]
    out = []
    for mk, col in (("spreads", "spread_home"), ("totals", "total_line")):
        m = o[o.market == mk].dropna(subset=[col])
        if m.empty:
            continue
        m = m.sort_values("snap").drop_duplicates(["game_id", "bookmaker"], keep="last")
        out.append(m.groupby("game_id")[col].median())
    if not out:
        return pd.DataFrame(columns=cols)
    return pd.concat(out, axis=1).reset_index().reindex(columns=cols)


def team_spread(spread_home, is_home):
    """The spread from the player's TEAM's side: negative = his team is favoured.

    `spread_home` is the home number, so the away team's number is its negative.
    """
    s = np.asarray(spread_home, dtype=float)
    return np.where(np.asarray(is_home, dtype=float) == 1.0, s, -s)


# ── the frame ────────────────────────────────────────────────────────────────

def _ewm_post(df: pd.DataFrame, by: str, cols: list[str], halflife: float) -> pd.DataFrame:
    """Exponentially weighted mean of each column over the group's rows UP TO AND INCLUDING each row."""
    e = df.groupby(by, sort=False)[cols].ewm(halflife=halflife, ignore_na=True).mean()
    return e.reset_index(level=0, drop=True).reindex(df.index)


def _ewm_prev_fast(df: pd.DataFrame, by: str, cols: list[str], halflife: float) -> pd.DataFrame:
    """The same over the group's EARLIER rows only."""
    e = df.groupby(by, sort=False)[cols].ewm(halflife=halflife, ignore_na=True).mean()
    e = e.reset_index(level=0, drop=True).reindex(df.index)
    return e.groupby(df[by], sort=False).shift(1)


def decisions_for(data: dict, props: pd.DataFrame | None = None,
                  upcoming_decisions: pd.DataFrame | None = None) -> pd.DataFrame:
    """The decision time per game: the prop snapshot where one exists, else tip minus an hour."""
    g = data["nba_games"][["game_id", "commence_time"]].copy()
    g["decision_ts"] = _utc(g.commence_time) - pd.Timedelta(minutes=DECISION_LEAD_MIN)
    if props is not None and len(props):
        s = props.groupby("game_id").snapshot_at.min()
        s = _utc(s)
        g = g.merge(s.rename("snap").reset_index(), on="game_id", how="left")
        g["decision_ts"] = g.snap.where(g.snap.notna(), g.decision_ts)
        g = g.drop(columns="snap")
    if upcoming_decisions is not None and len(upcoming_decisions):
        g = pd.concat([g[~g.game_id.isin(upcoming_decisions.game_id)],
                       upcoming_decisions[["game_id", "decision_ts"]]], ignore_index=True)
    return g[["game_id", "decision_ts"]]


def _positions(b: pd.DataFrame) -> pd.Series:
    """G / F / C as of before each row: the most frequent position in his earlier starts;
    for a player with no start yet, from his weighted rates (assists -> G; rebounds or blocks -> C)."""
    oh = pd.get_dummies(b.position.where(b.is_starter == 1)).reindex(columns=list(POS), fill_value=False)
    cnt = oh.astype(float).groupby(b.player_id, sort=False).cumsum()
    cnt = cnt.groupby(b.player_id, sort=False).shift(1).fillna(0)
    has = cnt.sum(axis=1) > 0
    pos = pd.Series(np.array(POS)[cnt.values.argmax(axis=1)], index=b.index).where(has)
    ast36 = 36 * b.r_assists_l
    reb36 = 36 * b.r_rebounds_l
    blk36 = 36 * b.r_blocks_l
    guess = np.where(ast36 >= 4.5, "G", np.where((reb36 >= 9.5) | (blk36 >= 1.6), "C", "F"))
    return pos.fillna(pd.Series(guess, index=b.index))


def build_frame(data: dict, decisions: pd.DataFrame, upcoming: pd.DataFrame | None = None,
                with_lines: bool = True) -> pd.DataFrame:
    """One row per (game, rostered player): targets where he played, and every input as of the decision.

    `upcoming` (live): one row per player to score tonight -- game_id, player_id,
    player_name, team, opponent, is_home, season, game_date -- with the games in
    data['nba_games'] or appended by the caller.
    """
    b = box_panel(data)
    if upcoming is not None and len(upcoming):
        u = upcoming.copy()
        u["game_date"] = pd.to_datetime(u.game_date)
        u["played"], u["minutes_exact"], u["is_starter"] = True, np.nan, np.nan
        u["upcoming"] = True
        b = pd.concat([b.assign(upcoming=False), u], ignore_index=True)
    else:
        b["upcoming"] = False
    tg = team_games(data)
    b = b.merge(tg[["game_id", "team", "tip"]], on=["game_id", "team"], how="left")
    b = b.sort_values(["player_id", "tip", "game_id"]).reset_index(drop=True)

    # ── his own history: over the games he PLAYED, read the same way on EVERY row ──
    # Each quantity is computed AFTER each played game (that game included), then every row -- played,
    # missed, or tonight's -- reads the value left by his latest played game strictly before it. A row
    # must not be built differently because of whether he went on to play (that would be the outcome).
    hist = b.played & ~b.upcoming
    pl = b[hist].copy()
    for s in BASE_STATS + ("fg_att", "fg3_att", "ft_att", "fouls"):
        pl[f"_{s}"] = pl[s]
    pl["_min"] = pl.minutes_exact
    pl["_usg"] = pl.usage_pct * pl.minutes_exact
    pl["_start"] = pl.is_starter
    post = {}
    ratecols = [f"_{s}" for s in BASE_STATS + ("fg_att", "fg3_att", "ft_att", "fouls")]
    for tag, hl in (("l", 20.0), ("s", 5.0)):
        e = _ewm_post(pl, "player_id", ratecols + ["_min", "_usg"], hl)
        for c in ratecols + ["_min", "_usg"]:
            post[f"{c}_{tag}"] = e[c]
    e = _ewm_post(pl, "player_id", ["_min", "_start"], 10.0)
    post["min_l"], post["start_l"] = e["_min"], e["_start"]
    e = _ewm_post(pl, "player_id", ["_min", "_start"], 3.0)
    post["min_s"], post["start_s"] = e["_min"], e["_start"]
    g = pl.groupby("player_id", sort=False)
    post["min_last"] = pl._min
    post["gp"] = (g.cumcount() + 1).astype(float)
    post["last_tip"] = pl.tip
    # the naive projections the model has to beat (step 4): season to date, last ten, weighted.
    # Season to date read before his first game of a season is last season's whole average.
    for s in BASE_STATS:
        post[f"ew_{s}"] = _ewm_post(pl, "player_id", [s], 8.0)[s]
        post[f"l10_{s}"] = g[s].transform(lambda x: x.rolling(10, min_periods=1).mean())
        post[f"sa_{s}"] = pl.groupby(["player_id", "season"], sort=False)[s].transform(
            lambda x: x.expanding().mean())
    F = pd.DataFrame(post, index=pl.index)
    F = F.reindex(b.index)
    F = F.groupby(b.player_id, sort=False).shift(1).groupby(b.player_id, sort=False).ffill()
    for tag in ("l", "s"):
        for s_ in BASE_STATS + ("fg_att", "fg3_att", "ft_att", "fouls"):
            F[f"r_{s_}_{tag}"] = F[f"_{s_}_{tag}"] / F[f"_min_{tag}"].clip(lower=1.0)
        F[f"usg_{tag}"] = F[f"_usg_{tag}"] / F[f"_min_{tag}"].clip(lower=1.0)
    F = F.drop(columns=[c for c in F.columns if c.startswith("_")])
    F["gp"] = F.gp.fillna(0.0)
    b = pd.concat([b, F], axis=1)
    b["days_since"] = ((b.tip - b.last_tip).dt.total_seconds() / 86400).clip(upper=30)

    # ── his minutes over his TEAM's games, zeros for games he missed ──
    b = b.sort_values(["team", "player_id", "tip"]).reset_index(drop=True)
    b["_tk"] = b.team + "|" + b.player_id.astype(str)
    b["_tmin"] = b.minutes_exact.where(~b.upcoming, np.nan)
    b["_tusg"] = (b.usage_pct.fillna(0) * b.minutes_exact).where(~b.upcoming, np.nan)
    e = _ewm_prev_fast(b, "_tk", ["_tmin", "_tusg"], 4.0)
    b["tm_min"], b["tm_usg"] = e["_tmin"], e["_tusg"]
    miss = (~b.played).astype(float).where(~b.upcoming, np.nan)
    grp = (miss.fillna(0) == 0).groupby(b._tk).cumsum()
    b["miss_streak"] = miss.groupby([b._tk, grp]).cumsum().groupby(b._tk).shift(1).fillna(0)
    b["tm_n"] = b.groupby("_tk").cumcount().astype(float)

    b["pos"] = _positions(b.sort_values(["player_id", "tip"]))

    # ── availability at the decision: whole reports, per team ──
    dec = decisions[decisions.game_id.isin(b.game_id)]
    rep = injury_asof(data["nba_injury_report"], dec)
    rep = _attach_report_ids(rep, b)
    covered = set(dec.game_id[injury_coverage(data["nba_injury_report"], dec).values])
    st = rep.drop_duplicates(["game_id", "player_id"]).set_index(["game_id", "player_id"]).status
    key = pd.MultiIndex.from_arrays([b.game_id, b.player_id])
    b["status"] = st.reindex(key).values
    b["covered"] = b.game_id.isin(covered)
    b.loc[b.covered & b.status.isna(), "status"] = "Listed none"
    b["own_q"] = (b.status == "Questionable").astype(float).where(b.covered)
    b["own_p"] = b.status.isin(["Probable", "Available"]).astype(float).where(b.covered)
    b["own_out"] = b.status.isin(["Out", "Doubtful"]).astype(float).where(b.covered)
    out = b.status.isin(["Out", "Doubtful"])
    q = b.status == "Questionable"
    # teammates returning: not Out/Doubtful tonight, missed the team's last game -- what he plays
    # when he plays, less what he has averaged over the team's recent games
    ret = (b.min_l - b.tm_min).clip(lower=0).where(~out & (b.tm_n > 0) & (b.miss_streak >= 1), 0.0)
    # who is on tonight's roster: in this game's box (backtest) or the caller's upcoming rows (live)
    agg = pd.DataFrame({
        "game_id": b.game_id, "team": b.team, "pos": b.pos,
        "o_min": b.tm_min.where(out, 0.0).fillna(0), "o_usg": b.tm_usg.where(out, 0.0).fillna(0),
        "q_min": b.tm_min.where(q, 0.0).fillna(0), "r_min": ret.fillna(0)})
    tot = agg.groupby(["game_id", "team"])[["o_min", "o_usg", "q_min", "r_min"]].sum()
    bypos = agg.groupby(["game_id", "team", "pos"]).o_min.sum()
    tk = pd.MultiIndex.from_arrays([b.game_id, b.team])
    for c in ("o_min", "o_usg", "q_min", "r_min"):
        own = agg[c].values
        b[f"tm_{c}"] = tot[c].reindex(tk).values - own        # teammates only
    b["tm_o_min_pos"] = bypos.reindex(pd.MultiIndex.from_arrays([b.game_id, b.team, b.pos])).values - agg.o_min.values
    ok = tot.reindex(pd.MultiIndex.from_arrays([b.game_id, b.opponent]))
    b["opp_o_min"], b["opp_o_usg"] = ok.o_min.values, ok.o_usg.values
    for c in ("tm_o_min", "tm_o_usg", "tm_q_min", "tm_r_min", "tm_o_min_pos", "opp_o_min", "opp_o_usg"):
        b[c] = b[c].where(b.covered)
    # the context his recent minutes were played in: the same quantity over his recent played games
    b = b.sort_values(["player_id", "tip", "game_id"]).reset_index(drop=True)
    pl = b[b.played & ~b.upcoming].copy()
    ctx = _ewm_post(pl, "player_id", ["tm_o_min", "tm_o_usg"], 5.0).reindex(b.index)
    ctx = ctx.groupby(b.player_id, sort=False).shift(1).groupby(b.player_id, sort=False).ffill()
    b["ctx_o_min"], b["ctx_o_usg"] = ctx.tm_o_min.values, ctx.tm_o_usg.values
    b["d_o_min"] = b.tm_o_min - b.ctx_o_min
    b["d_o_usg"] = b.tm_o_usg - b.ctx_o_usg

    # ── teams: pace and efficiency, weighted over earlier games ──
    tm = _team_rates(b, tg)
    b = b.merge(tm[["game_id", "team", "pace_l", "ortg_l", "drtg_l", "rest", "b2b", "g4d", "road_trip"]],
                on=["game_id", "team"], how="left")
    o = tm[["game_id", "team", "pace_l", "ortg_l", "drtg_l", "rest", "b2b"]].rename(
        columns={"team": "opponent", "pace_l": "opp_pace_l", "ortg_l": "opp_ortg_l", "drtg_l": "opp_drtg_l",
                 "rest": "opp_rest", "b2b": "opp_b2b"})
    b = b.merge(o, on=["game_id", "opponent"], how="left")

    # ── what the opponent allows, to his position, against expectation ──
    b = _opp_factors(b.copy()).copy()

    # ── the game's lines at the decision ──
    b["spread_team"], b["total_line"] = np.nan, np.nan
    if with_lines and "nba_odds" in data:
        ln = lines_asof(data["nba_odds"], dec)
        if len(ln):
            lm = ln.set_index("game_id").reindex(b.game_id)
            b["spread_team"] = team_spread(lm.spread_home.values, b.is_home.values)
            b["total_line"] = lm.total_line.values
    b["abs_spread"] = b.spread_team.abs()
    b["pos_g"] = (b.pos == "G").astype(float)
    b["pos_c"] = (b.pos == "C").astype(float)
    return b.drop(columns=[c for c in b.columns if c.startswith("_")])


def _attach_report_ids(rep: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """The report's NBA.com id where it has one, else the unique roster player with the name."""
    rep = rep.copy()
    miss = rep.player_id.isna()
    if miss.any():
        ros = b[["team", "season", "player_id", "player_name"]].drop_duplicates(["team", "season", "player_id"])
        ros = ros.assign(k=ros.player_name.map(base_key))
        uniq = ros.groupby(["team", "k"]).player_id.agg(lambda s: s.iloc[0] if s.nunique() == 1 else None)
        ks = list(zip(rep.loc[miss, "team"], rep.loc[miss, "player_name"].map(base_key)))
        rep.loc[miss, "player_id"] = [uniq.get(k) for k in ks]
    return rep.dropna(subset=["player_id"])


def _team_rates(b: pd.DataFrame, tg: pd.DataFrame) -> pd.DataFrame:
    """Possessions, pace and points per 100 for and against, weighted over each team's earlier games."""
    p = b[b.played & ~b.upcoming]
    t = p.groupby(["game_id", "team"]).agg(fga=("fg_att", "sum"), fta=("ft_att", "sum"),
                                           orb=("offensive_reb", "sum"), tov=("turnovers", "sum"),
                                           pts=("points", "sum"), mins=("minutes_exact", "sum")).reset_index()
    t["poss"] = t.fga + 0.44 * t.fta - t.orb + t.tov
    opp = t[["game_id", "team", "poss", "pts"]].rename(columns={"team": "opponent", "poss": "o_poss", "pts": "o_pts"})
    t = t.merge(tg[["game_id", "team", "opponent"]], on=["game_id", "team"]).merge(opp, on=["game_id", "opponent"])
    gm = (t.mins / 5).clip(lower=48)
    t["_pace"] = (t.poss + t.o_poss) / 2 * 48 / gm
    t["_ortg"] = 100 * t.pts / t.poss.clip(lower=1)
    t["_drtg"] = 100 * t.o_pts / t.o_poss.clip(lower=1)
    tt = tg.merge(t[["game_id", "team", "_pace", "_ortg", "_drtg"]], on=["game_id", "team"], how="left")
    tt = tt.sort_values(["team", "tip", "game_id"]).reset_index(drop=True)
    e = _ewm_prev_fast(tt, "team", ["_pace", "_ortg", "_drtg"], 15.0)
    tt["pace_l"], tt["ortg_l"], tt["drtg_l"] = e._pace, e._ortg, e._drtg
    return tt


def _opp_factors(b: pd.DataFrame) -> pd.DataFrame:
    """For each base stat: what the opponent's earlier opponents at his position produced,
    over what their own rates predicted (actual / expected, weighted over the opponent's games)."""
    p = b[b.played & ~b.upcoming & b.min_l.notna()].copy()
    rows = {}
    for s in BASE_STATS:
        p[f"x_{s}"] = p[f"r_{s}_l"] * p.minutes_exact
    cols = [c for s in BASE_STATS for c in (s, f"x_{s}")]
    agg = p.groupby(["game_id", "opponent", "pos"])[cols].sum().reset_index()   # 'opponent' = the defence
    agg = agg.rename(columns={"opponent": "defence"})
    tips = b.drop_duplicates("game_id").set_index("game_id").tip
    agg["tip"] = agg.game_id.map(tips)
    agg = agg.sort_values(["defence", "pos", "tip"]).reset_index(drop=True)
    agg["_k"] = agg.defence + "|" + agg.pos
    # the factor INCLUDING each of the defence's games, carried to the defence's NEXT game:
    # a row at tip T reads the latest defence game with tip strictly before T
    e = agg.groupby("_k", sort=False)[cols].ewm(halflife=20.0, ignore_na=True).mean().reset_index(level=0, drop=True)
    post = agg[["defence", "pos", "tip"]].copy()
    for s in BASE_STATS:
        post[f"opp_f_{s}"] = e[s] / e[f"x_{s}"].clip(lower=1e-6)
    post = post.sort_values("tip")
    left = b[["opponent", "pos", "tip"]].rename(columns={"opponent": "defence"}).reset_index()
    left = left.dropna(subset=["tip", "pos"]).sort_values("tip")
    m = pd.merge_asof(left, post, on="tip", by=["defence", "pos"], allow_exact_matches=False).set_index("index")
    for s in BASE_STATS:
        b[f"opp_f_{s}"] = m[f"opp_f_{s}"].reindex(b.index)
    return b


# ── features per model ───────────────────────────────────────────────────────

OWN = ["min_l", "min_s", "min_last", "start_l", "start_s", "gp", "days_since", "tm_min", "miss_streak",
       "usg_l", "usg_s", "r_fg_att_l", "r_fg3_att_l", "r_ft_att_l", "r_fouls_l", "own_q", "own_p", "own_out",
       "pos_g", "pos_c"]
AVAIL = ["tm_o_min", "tm_o_usg", "tm_q_min", "tm_r_min", "tm_o_min_pos", "ctx_o_min", "ctx_o_usg",
         "d_o_min", "d_o_usg", "opp_o_min", "opp_o_usg"]
SCHED = ["is_home", "rest", "b2b", "g4d", "road_trip", "opp_rest", "opp_b2b"]
TEAM = ["pace_l", "opp_pace_l", "ortg_l", "drtg_l", "opp_ortg_l", "opp_drtg_l"]
LINES = ["spread_team", "abs_spread", "total_line"]
GROUPS = {"own": OWN, "avail": AVAIL, "sched": SCHED, "team": TEAM, "lines": LINES}


def rate_features(stat: str) -> list[str]:
    return [f"r_{stat}_l", f"r_{stat}_s", f"opp_f_{stat}"]


def minutes_features(drop: tuple[str, ...] = ()) -> list[str]:
    cols = OWN + AVAIL + SCHED + TEAM + LINES
    return [c for c in cols if not any(c in GROUPS[g] for g in drop)]


def all_rates() -> list[str]:
    return [c for s in BASE_STATS for c in rate_features(s)]


def count_features(spec: Spec, drop: tuple[str, ...] = ()) -> list[str]:
    rates = [c for s in BASE_STATS for c in rate_features(s)] if spec.kind != "count" else \
        [c for s in spec.parts for c in rate_features(s)]
    return minutes_features(drop) + rates


def usable(frame: pd.DataFrame) -> pd.Series:
    """Rows a model may train on or score: ten earlier games played, and his minutes history present."""
    return (frame.gp >= MIN_GAMES) & frame.min_l.notna()


# ── models ───────────────────────────────────────────────────────────────────

_XGB = dict(n_estimators=300, max_depth=5, learning_rate=0.07, max_bin=64, subsample=0.8, colsample_bytree=0.8,
            min_child_weight=40, reg_lambda=5.0, random_state=42, n_jobs=-1, verbosity=0, tree_method="hist")
XGB_COUNT = dict(objective="count:poisson", **_XGB)
XGB_MIN = dict(objective="reg:squarederror", **_XGB)
XGB_BIN = dict(objective="binary:logistic", **{**_XGB, "max_depth": 4})


def _X(rows: pd.DataFrame, cols: list[str]) -> np.ndarray:
    return rows[cols].astype(float).values


def fit_minutes(train: pd.DataFrame, drop: tuple[str, ...] = (), cols: list[str] | None = None):
    """`cols` overrides the input list (models/nba_prop_projection fits on the worker's inputs)."""
    from xgboost import XGBRegressor
    cols = list(cols) if cols is not None else minutes_features(drop)
    m = XGBRegressor(**XGB_MIN).fit(_X(train, cols), train.minutes_exact.values)
    return {"model": m, "cols": cols}


def predict_minutes(fm: dict, rows: pd.DataFrame) -> np.ndarray:
    return np.clip(fm["model"].predict(_X(rows, fm["cols"])), 1.0, 48.0)


def fit_rate(train: pd.DataFrame, stat: str, drop: tuple[str, ...] = (), cols: list[str] | None = None):
    """Per-minute rate: Poisson on the count with log(minutes) as the exposure."""
    from xgboost import XGBRegressor
    cols = list(cols) if cols is not None else minutes_features(drop) + rate_features(stat)
    tr = train[train.minutes_exact > 0]
    m = XGBRegressor(**XGB_COUNT)
    m.fit(_X(tr, cols), tr[stat].values, base_margin=np.log(tr.minutes_exact.clip(lower=0.5).values))
    return {"model": m, "cols": cols}


def predict_rate_mean(fr: dict, rows: pd.DataFrame, minutes: np.ndarray) -> np.ndarray:
    return np.clip(fr["model"].predict(_X(rows, fr["cols"]),
                                       base_margin=np.log(np.clip(minutes, 0.5, None))), 1e-4, None)


def fit_direct(train: pd.DataFrame, spec: Spec, drop: tuple[str, ...] = ()):
    from xgboost import XGBRegressor
    cols = count_features(spec, drop)
    y = settle_value(spec, train)
    ok = y.notna().values
    m = XGBRegressor(**XGB_COUNT).fit(_X(train[ok], cols), y[ok].values)
    return {"model": m, "cols": cols}


def predict_direct(fd: dict, rows: pd.DataFrame) -> np.ndarray:
    return np.clip(fd["model"].predict(_X(rows, fd["cols"])), 1e-4, None)


def fit_binary(train: pd.DataFrame, spec: Spec, drop: tuple[str, ...] = ()):
    from xgboost import XGBClassifier
    cols = count_features(spec, drop)
    y = settle_value(spec, train)
    ok = y.notna().values
    m = XGBClassifier(**XGB_BIN).fit(_X(train[ok], cols), y[ok].values.astype(int))
    return {"model": m, "cols": cols}


def predict_binary(fb: dict, rows: pd.DataFrame) -> np.ndarray:
    return np.clip(fb["model"].predict_proba(_X(rows, fb["cols"]))[:, 1], 1e-5, 1 - 1e-5)


# ── distributions ────────────────────────────────────────────────────────────

def nb_logpmf(y, mu, alpha: float) -> np.ndarray:
    y, mu = np.asarray(y, dtype=float), np.clip(np.asarray(mu, dtype=float), 1e-6, None)
    if alpha <= 1e-9:
        return poisson.logpmf(y, mu)
    n = 1.0 / alpha
    return nbinom.logpmf(y, n, n / (n + mu))


def fit_alpha(y, mu) -> float:
    """Negative-binomial excess variance by maximum likelihood (0 = Poisson), on held-out predictions."""
    from scipy.optimize import minimize_scalar
    y, mu = np.asarray(y, dtype=float), np.asarray(mu, dtype=float)
    ok = np.isfinite(y) & np.isfinite(mu)
    y, mu = y[ok], mu[ok]
    best = minimize_scalar(lambda la: -nb_logpmf(y, mu, float(np.exp(la))).sum(), bounds=(-9, 1.5), method="bounded")
    a = float(np.exp(best.x))
    return a if nb_logpmf(y, mu, a).sum() > poisson.logpmf(y, mu).sum() else 0.0


def p_over(mu, line, alpha: float = 0.0) -> np.ndarray:
    """P(count > line)."""
    k = np.floor(np.asarray(line, dtype=float))
    mu = np.clip(np.asarray(mu, dtype=float), 1e-6, None)
    if alpha <= 1e-9:
        return poisson.sf(k, mu)
    n = 1.0 / alpha
    return nbinom.sf(k, n, n / (n + mu))


def p_push(mu, line, alpha: float = 0.0) -> np.ndarray:
    """P(count == line): zero for a half-point line."""
    line = np.asarray(line, dtype=float)
    mu = np.clip(np.asarray(mu, dtype=float), 1e-6, None)
    whole = np.isclose(line, np.round(line))
    if alpha <= 1e-9:
        pm = poisson.pmf(np.round(line), mu)
    else:
        n = 1.0 / alpha
        pm = nbinom.pmf(np.round(line), n, n / (n + mu))
    return np.where(whole, pm, 0.0)


# ── prices and units ─────────────────────────────────────────────────────────

def decimal(american) -> np.ndarray:
    a = np.asarray(american, dtype=float)
    return np.where(a > 0, 1 + a / 100.0, 1 + 100.0 / np.abs(a))


def implied(american) -> np.ndarray:
    a = np.asarray(american, dtype=float)
    return np.where(a > 0, 100.0 / (a + 100.0), np.abs(a) / (np.abs(a) + 100.0))


MAX_RISK_UNITS = 3.0


def stake(american) -> tuple[np.ndarray, np.ndarray]:
    """(risk, win) for one unit TO WIN, risk capped at 3 (tracking/discord_notifier.stake_for)."""
    d = decimal(american)
    risk = 1.0 / (d - 1.0)
    capped = risk > MAX_RISK_UNITS
    risk = np.where(capped, MAX_RISK_UNITS, risk)
    win = np.where(capped, MAX_RISK_UNITS * (d - 1.0), 1.0)
    return risk, win


def expected_value(p, american) -> np.ndarray:
    """EV per unit risked: p x decimal - 1 (pushes ignored; the history has no whole-number line)."""
    return np.asarray(p, dtype=float) * decimal(american) - 1.0


# ── calibration (the probability the card prices and publishes) ─────────────
#
# The raw model overclaims: on the worker re-fit's one-a-game bets it claimed
# 0.636 and won 0.464, and across every priced line it under-calls the over in
# points and the combos (claimed 0.437, realised 0.485). A two-parameter logit
# map per market, logit P(over) = a + b * logit(p_model), corrects a shift and
# a slope, stays strictly monotone (no EV ties), and extrapolates sanely in the
# tails. Season S is mapped ONLY by pairs from seasons before S (or, where no
# priced season exists before it, by games strictly before the week's cutoff).
#
# THE MAP HOLDS AT THE CONSENSUS MAIN LINE ONLY. Fitted and checked on 2024-25:
# at the main line it is right (over claimed 0.438, won 0.440); one point off
# it the calibrated number barely moves while the outcome moves 4-8 points, in
# the direction that favours the better-priced side. So the card decides only
# at the main line (DraftKings' two-sided line, else the line most bettable
# books hang) and the map is fitted on main-line pairs only.

_EPS = 1e-4


def _logit(p) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), _EPS, 1 - _EPS)
    return np.log(p / (1 - p))


def fit_platt(p, y, iters: int = 50) -> tuple[float, float]:
    """(a, b) maximising the likelihood of y under sigmoid(a + b * logit(p)); Newton steps."""
    x, y = _logit(p), np.asarray(y, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    X = np.column_stack([np.ones_like(x), x])
    w = np.array([0.0, 1.0])
    for _ in range(iters):
        q = 1 / (1 + np.exp(-(X @ w)))
        g = X.T @ (y - q)
        H = (X * (q * (1 - q))[:, None]).T @ X
        step = np.linalg.solve(H + 1e-9 * np.eye(2), g)
        w = w + step
        if np.abs(step).max() < 1e-10:
            break
    return float(w[0]), float(w[1])


def apply_calibration(p, ab: tuple[float, float]) -> np.ndarray:
    a, b = ab
    return 1 / (1 + np.exp(-(a + b * _logit(p))))


def fit_calibration(pairs: pd.DataFrame, season: int) -> dict[str, tuple[float, float]]:
    """Per-market Platt maps for grading `season`, fitted on `pairs` (season, market, p, y) from EARLIER
    seasons only. Refuses (ValueError) when no earlier pair exists: a season is never mapped by itself."""
    prior = pairs[pairs.season < season]
    if prior.empty:
        raise ValueError(f"no calibration pairs before season {season}")
    return {mk: fit_platt(g.p.values, g.y.values) for mk, g in prior.groupby("market")}


def fit_calibration_before(pairs: pd.DataFrame, cutoff, min_pairs: int = 300) -> dict[str, tuple[float, float]]:
    """Per-market Platt maps from pairs (market, p, y, game_date) of games played strictly BEFORE `cutoff`
    (a game on the cutoff day has not finished when the map is fitted). A market with fewer than
    `min_pairs` such pairs gets no map; the caller says what stands in for it."""
    prior = pairs[pd.to_datetime(pairs.game_date) < pd.Timestamp(cutoff)]
    return {mk: fit_platt(g.p.values, g.y.values) for mk, g in prior.groupby("market") if len(g) >= min_pairs}


def exclude_taken(C: pd.DataFrame, taken: pd.DataFrame) -> pd.DataFrame:
    """Drop every row of C whose (game, player, market) another model already bets -- every line, both
    sides. One bet per proposition across all NBA prop models; ids compared as text."""
    key = lambda d: d.game_id.astype(str) + "|" + d.player_id.astype(str) + "|" + d.market.astype(str)  # noqa: E731
    return C[~key(C).isin(set(key(taken)))]
