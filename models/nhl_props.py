"""NHL count props beyond blocked shots: goalie saves, skater shots on goal, skater assists.

ONE ENGINE, ONE SPEC PER MARKET. models/nhl_prop_blocked_shots.py is the live
blocked-shots model and is deliberately left alone (its artifact was fitted on
exactly that module); this is the same design, generalised so a new market is a
`Spec`, not a new file:

    a gradient-boosted Poisson mean for one player's count in one game, from
    his own exponentially weighted history, his usage, and what the two teams
    do -- every input the weighted mean of EARLIER rows only;
    P(over the line) from the count distribution around that mean.

Tonight's game is scored by appending a row with no result and reading the
same shifted means, so a training row and a live row are one piece of
arithmetic, not two implementations of it.

WHAT DIFFERS BY MARKET
  skater markets   one row per skater-game. Usage is ice time and power-play
                   time; the matchup is what the OPPONENT allows.
  goalie saves     one row per START. A goalie who does not start is void at
                   DraftKings, so a relief appearance is neither history nor a
                   bet here. The matchup is how much the opponent shoots, how
                   much his own team allows, who is at home, and how rested
                   he and both teams are (the last three were added because
                   they predict the COUNT better on seasons the model had not
                   seen -- 0.7% lower deviance -- and for no other reason;
                   the same test added nothing to either skater market).

UNDERS ONLY. In every NHL count market DraftKings' margin sits on the over:
betting every over blind loses 9-12% and every under 0-3.5% (three priced
seasons). The model's overs lose in all three markets here and its unders are
where the return is, so a Spec names the sides it may bet and all three name
the under. That restriction was chosen on the same three seasons the cut was,
which is said out loud in docs/nhl_market_lab.md.

THE BEST PRICE, NOT ONE BOOK. A pick is decided at the best price among the
bettable books (CLAUDE.md 6), and here that is not a detail: the model says
which unders, and several books hang the same player at different numbers and
prices. At DraftKings alone the shots-on-goal unders return about +3% and
nothing in the most recent season; at the best price the same model returns
+5.7% with every season positive. Saves and assists hold either way.
`books()` is who may be shopped. FanDuel is left out: it lists several lines a
player and the shared parser kept one row a player, pairing an over from one
line with an under from another (2,556 of its shots rows fail the coherent-
quote check in the bought history; no other book has more than 11). The
filter drops the pairs it can see, not the ones that happen to sum plausibly.

AT MOST THREE SHOTS-ON-GOAL BETS IN ONE GAME (mike, 2026-10-01: "Limit 3").
Its first live night bet 11 unders in one game; the three priced seasons never
bet more than 9, and nights betting 20%+ of the board lost money. Keeping the
three best-EV bets a game returns +5.4% on 4,210 against +5.7% on 4,707 with
no limit: it bounds a night like that one and does not buy return
(docs/nhl_market_lab.md). Saves and assists carry no limit.

THE DISTRIBUTION. A Poisson count has variance equal to its mean. Saves do
not: a goalie's night swings with the shot volume he faces, so the spread
around the predicted mean is wider. `fit` measures that excess on the training
rows (`dispersion`, 0 = Poisson) and `p_over` uses a negative binomial when it
is positive. Whether a market uses it is in its Spec. Saves does: its counts
are far wider than Poisson. Assists are Poisson to within 3%. Shots on goal
run about 10% wide and are left Poisson, as the lab had them: the wider
distribution does not change what the model claims against what happens, and
the result holds under either (+5.7% Poisson, +4.9% wider, at the 0.10 cut,
every season positive both ways).

THE SHOTS CANDIDATE stays off the card. `USE_MONEYPUCK_SHOTS` is false.
`shots_spec(True)` adds prior-game MoneyPuck skater rates, usage trends,
linemate and power-play deployment, and opponent shot suppression, for
`scripts/nhl_prop_backtest.py --moneypuck` only. The card scores `SHOTS`.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd
from scipy.stats import nbinom, poisson

BOOK = "draftkings"             # the reference book: the DraftKings-only tables, and the bet link
EXCLUDED_BOOKS = frozenset({"fanduel"})
MIN_GAMES = 10                  # a line is not hung on a debutant (career rows in the log, not this season's)
FIRST_TRAIN_SEASON = 2020
PARAMS = dict(objective="count:poisson", n_estimators=400, max_depth=4, learning_rate=0.03,
              subsample=0.8, colsample_bytree=0.8, min_child_weight=50, reg_lambda=5.0,
              random_state=42, n_jobs=-1, verbosity=0)
# Rows appended for games not yet played carry ids from here up, so they can
# never collide with a real NHL game id (ten digits) or sort before one.
UPCOMING_ID0 = 10 ** 12

SKATER_USAGE = ("toi_l", "toi_s", "pp_toi_l", "pp_toi_s", "is_home", "rest", "is_d", "gp")


@dataclass(frozen=True)
class Spec:
    model_id: str
    market: str            # the Odds API market key in player_prop_odds
    stat: str              # the game-log column the bet settles on
    label: str             # how the stat reads in a pick label
    kind: str              # 'skater' | 'goalie'
    features: tuple[str, ...]
    overdispersed: bool = False
    sides: tuple[str, ...] = ("under",)
    max_per_game: int | None = None   # the most bets in one game, best EV first; None = no limit


SAVES = Spec("nhl_prop_saves", "player_total_saves", "saves", "Saves", "goalie",
             ("saves_l", "saves_s", "sa_l", "opp_sf", "own_sa", "gp",
              "is_home", "rest", "own_rest", "opp_rest"), overdispersed=True)
SHOTS = Spec("nhl_prop_shots_on_goal", "player_shots_on_goal", "shots", "Shots on Goal", "skater",
             ("shots_l", "shots_s", "shot_attempts_l", "shot_attempts_s", "opp_sa") + SKATER_USAGE,
             max_per_game=3)
# Live scoring leaves this off. scripts/nhl_prop_backtest.py --moneypuck is the
# only caller. Turning it on here would not, by itself, change the card: the
# card scores SHOTS and never calls shots_spec(True).
USE_MONEYPUCK_SHOTS = False
# All-situation MoneyPuck rows. Half-lives match the skater shot rates (30 / 6),
# the ice-time rates (20 / 4) and the team shot rate (25).
MONEYPUCK_SITUATION = "all"
# A teammate at or above this power-play time that night took a power-play
# shift. The shift chart has no strength, so this is the game log's pp_toi,
# not a flag on the shift. Measured on 2025-26 regular-season skater rows:
# 24,033 of 47,230 were at or above 30 seconds.
PP_UNIT_SECONDS = 30
MONEYPUCK_SHOT_FEATURES = (
    "mp_xg_l", "mp_xg_s",
    "mp_att_l", "mp_att_s",
    "mp_hd_l", "mp_hd_s",
    "toi_trend", "pp_toi_trend",
    "lm_q_l", "lm_q_s",
    "pp_share_l", "pp_share_s",
    "pp_unit_l", "pp_unit_s",
    "opp_mp_sa", "opp_mp_xga",
)
# The shift chart starts in 2023-24. Requiring these would drop every earlier
# season, including the training set that scores 2023-24. XGBoost treats NaN
# as missing. MoneyPuck rates and the ice-time trends are required.
SHIFT_OPTIONAL_FEATURES = frozenset({"lm_q_l", "lm_q_s", "pp_unit_l", "pp_unit_s"})
ASSISTS = Spec("nhl_prop_assists", "player_assists", "assists", "Assists", "skater",
               ("assists_l", "assists_s", "points_l", "opp_ga", "opp_pk_opps") + SKATER_USAGE)
SPECS: dict[str, Spec] = {s.model_id: s for s in (SAVES, SHOTS, ASSISTS)}
LIVE: tuple[Spec, ...] = (SAVES, SHOTS, ASSISTS)


def shots_spec(moneypuck: bool = False, drop: tuple[str, ...] = ()) -> Spec:
    """The live shots spec, or the same spec plus the candidate features.

    The live card keeps `SHOTS`. A backtest that wants the extra inputs asks
    for them here. `drop` removes named candidate features so a group can be
    tested by taking it out. Dropping a live feature is refused.
    """
    if not moneypuck and not drop:
        return SHOTS
    features = SHOTS.features + MONEYPUCK_SHOT_FEATURES
    if drop:
        gone = set(drop)
        if gone & set(SHOTS.features):
            raise ValueError(f"refusing to drop a live feature: {sorted(gone & set(SHOTS.features))}")
        features = tuple(f for f in features if f not in gone)
    if features == SHOTS.features:
        return SHOTS
    return replace(SHOTS, features=features)

SKATER_COLS = ("nhl_game_id", "player_id", "player_name", "position", "season", "game_date",
               "team", "opponent", "is_home", "shots", "shot_attempts", "assists", "points",
               "toi_seconds", "pp_toi_seconds")
GOALIE_COLS = ("nhl_game_id", "player_id", "player_name", "season", "game_date",
               "team", "opponent", "is_home", "started", "saves", "shots_against")
TEAM_COLS = ("nhl_game_id", "game_id", "team", "opponent", "game_date",
             "shots_for", "shots_against", "goals_against", "times_shorthanded")
_SKATER_STATS = ("shots", "shot_attempts", "assists", "points")
_TEAM_STATS = {"sf": "shots_for", "sa": "shots_against", "ga": "goals_against", "pk_opps": "times_shorthanded"}


def books() -> tuple[str, ...]:
    """The books a pick may be decided at: the bettable ones, less EXCLUDED_BOOKS."""
    import config
    return tuple(b for b in config.BEST_LINE_BOOKMAKERS if b not in EXCLUDED_BOOKS)


def name_key(name: str | None) -> str:
    """Letters only, accents and case folded: how a price row finds its player."""
    flat = unicodedata.normalize("NFKD", str(name or ""))
    return "".join(c for c in flat.lower() if c.isalpha())


# ── loading ──────────────────────────────────────────────────────────────────

def load_players(conn, kind: str, player_ids: list | None = None) -> pd.DataFrame:
    """Regular-season rows: all of them to train, a few players' to score."""
    table, cols = (("nhl_goalie_game_log", GOALIE_COLS) if kind == "goalie"
                   else ("nhl_skater_game_log", SKATER_COLS))
    sql = f"SELECT {', '.join(cols)} FROM {table} WHERE game_type = 2 AND player_id IS NOT NULL"
    if player_ids is None:
        rows = conn.execute(sql).fetchall()
    else:
        rows = conn.execute(sql + " AND player_id = ANY(%s)", ([int(p) for p in player_ids],)).fetchall()
    return pd.DataFrame(rows, columns=list(cols))


def load_teams(conn) -> pd.DataFrame:
    rows = conn.execute(f"SELECT {', '.join(TEAM_COLS)} FROM nhl_team_game_log").fetchall()
    return pd.DataFrame(rows, columns=list(TEAM_COLS))


# ── features ─────────────────────────────────────────────────────────────────

def _ew(g, col: str, halflife: float, min_periods: int = 3):
    return g[col].transform(lambda s: s.shift(1).ewm(halflife=halflife, min_periods=min_periods).mean())


def _with_upcoming(players: pd.DataFrame, teams: pd.DataFrame, upcoming: pd.DataFrame | None,
                   cols: tuple[str, ...], results: tuple[str, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Append tonight's players, and both of tonight's teams, as rows with no result."""
    d = players[[c for c in cols if c in players.columns]].copy()
    d["upcoming"] = False
    t = teams[list(TEAM_COLS)].copy()
    if upcoming is None or not len(upcoming):
        return d, t
    u = upcoming.copy()
    # one synthetic game id per game: both teams and every player share it
    ids = {g: UPCOMING_ID0 + i for i, g in enumerate(sorted(u.game_id.unique()))}
    u["nhl_game_id"] = u.game_id.map(ids)
    u["upcoming"] = True
    for c in results:
        u[c] = np.nan
    for c in cols:
        if c not in u.columns:
            u[c] = 1 if c == "started" else np.nan
    d = pd.concat([d, u[list(cols) + ["upcoming"]]], ignore_index=True)
    tu = u[["nhl_game_id", "game_id", "team", "opponent", "game_date"]].drop_duplicates()
    ou = tu.rename(columns={"team": "opponent", "opponent": "team"})
    both = pd.concat([tu, ou[list(tu.columns)]], ignore_index=True)
    for c in _TEAM_STATS.values():
        both[c] = np.nan
    t = pd.concat([t, both[list(TEAM_COLS)]], ignore_index=True).drop_duplicates(
        ["nhl_game_id", "team"], keep="first")
    return d, t


def _team_rates(teams: pd.DataFrame) -> pd.DataFrame:
    """Each team's as-of per-game rates, one row per (game, team)."""
    t = teams.copy()
    for c in _TEAM_STATS.values():
        t[c] = pd.to_numeric(t[c], errors="coerce")
    t["game_date"] = pd.to_datetime(t["game_date"])
    t = t.sort_values(["team", "game_date", "nhl_game_id"]).reset_index(drop=True)
    g = t.groupby("team", sort=False)
    for k, c in _TEAM_STATS.items():
        t[f"t_{k}"] = _ew(g, c, 25, 5)
    t["t_rest"] = (t.game_date - g.game_date.shift(1)).dt.days.clip(upper=6).fillna(6)
    return t


def _attach_teams(d: pd.DataFrame, t: pd.DataFrame) -> pd.DataFrame:
    names = list(_TEAM_STATS) + ["rest"]
    keys = [f"t_{k}" for k in names]
    opp = t[["nhl_game_id", "team"] + keys].rename(
        columns={"team": "opponent", **{f"t_{k}": f"opp_{k}" for k in names}})
    own = t[["nhl_game_id", "team"] + keys].rename(columns={f"t_{k}": f"own_{k}" for k in names})
    d = d.merge(opp, on=["nhl_game_id", "opponent"], how="left").merge(own, on=["nhl_game_id", "team"], how="left")
    gid = t[["nhl_game_id", "game_id"]].dropna().drop_duplicates("nhl_game_id")
    d = d.drop(columns=[c for c in ("game_id",) if c in d.columns]).merge(gid, on="nhl_game_id", how="left")
    d["pkey"] = d.player_name.map(name_key)
    return d


def build_skater_frame(skaters: pd.DataFrame, teams: pd.DataFrame,
                       upcoming: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per skater-game with every input as of BEFORE that game.

    `upcoming` holds games not yet played -- columns player_id, player_name,
    position, season, game_date, team, opponent, is_home, game_id.
    """
    results = _SKATER_STATS + ("toi_seconds", "pp_toi_seconds")
    d, t = _with_upcoming(skaters, teams, upcoming, SKATER_COLS, results)
    for c in results + ("is_home",):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["game_date"] = pd.to_datetime(d["game_date"])
    d = d.sort_values(["player_id", "game_date", "nhl_game_id"]).reset_index(drop=True)
    g = d.groupby("player_id", sort=False)
    for stat in _SKATER_STATS:
        d[f"{stat}_l"], d[f"{stat}_s"] = _ew(g, stat, 30), _ew(g, stat, 6)
    d["toi_l"], d["toi_s"] = _ew(g, "toi_seconds", 20), _ew(g, "toi_seconds", 4)
    d["pp_toi_l"], d["pp_toi_s"] = _ew(g, "pp_toi_seconds", 20), _ew(g, "pp_toi_seconds", 4)
    d["rest"] = (d.game_date - g.game_date.shift(1)).dt.days.clip(upper=6).fillna(6)
    d["gp"] = g.cumcount()
    d["is_d"] = (d.position == "D").astype(int)
    return _attach_teams(d, _team_rates(t))


def build_goalie_frame(goalies: pd.DataFrame, teams: pd.DataFrame,
                       upcoming: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per goalie START with every input as of before it.

    `upcoming` -- player_id, player_name, season, game_date, team, opponent,
    is_home, game_id -- is the goalies a book has priced tonight, taken as
    starting: that is the bet, and it is void if he does not.
    """
    results = ("saves", "shots_against")
    d, t = _with_upcoming(goalies, teams, upcoming, GOALIE_COLS, results)
    for c in results + ("is_home", "started"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d[d.started == 1].copy()
    d["game_date"] = pd.to_datetime(d["game_date"])
    d = d.sort_values(["player_id", "game_date", "nhl_game_id"]).reset_index(drop=True)
    g = d.groupby("player_id", sort=False)
    d["saves_l"], d["saves_s"] = _ew(g, "saves", 25), _ew(g, "saves", 5)
    d["sa_l"] = _ew(g, "shots_against", 25)
    d["rest"] = (d.game_date - g.game_date.shift(1)).dt.days.clip(upper=6).fillna(6)
    d["gp"] = g.cumcount()
    return _attach_teams(d, _team_rates(t))


def build_frame(spec: Spec, players: pd.DataFrame, teams: pd.DataFrame,
                upcoming: pd.DataFrame | None = None) -> pd.DataFrame:
    build = build_goalie_frame if spec.kind == "goalie" else build_skater_frame
    return build(players, teams, upcoming)


def _linemate_raw(frame: pd.DataFrame, mates: pd.DataFrame) -> pd.DataFrame:
    """One row per player-game: shared-ice quality from THAT game's chart.

    The caller shifts it, so the chart of the game being scored is not an
    input. Quality is the mate's prior individual expected goals (`mp_xg_l`),
    weighted by shared seconds. Power-play unit quality uses only mates who
    took at least PP_UNIT_SECONDS of power-play time that night. The chart
    does not say which shifts were a power play.
    """
    empty = pd.DataFrame(columns=["nhl_game_id", "player_id", "lm_raw", "pp_unit_raw"])
    if mates is None or not len(mates):
        return empty
    pairs = mates[["nhl_game_id", "player_id_lo", "player_id_hi", "shared_seconds"]].copy()
    for c in ("nhl_game_id", "player_id_lo", "player_id_hi"):
        pairs[c] = pd.to_numeric(pairs[c], errors="coerce")
    pairs["shared_seconds"] = pd.to_numeric(pairs["shared_seconds"], errors="coerce")
    pairs = pairs.dropna()
    pairs = pairs[pairs.shared_seconds > 0]
    if not len(pairs):
        return empty
    left = pairs.rename(columns={"player_id_lo": "player_id", "player_id_hi": "mate"})
    right = pairs.rename(columns={"player_id_hi": "player_id", "player_id_lo": "mate"})
    edges = pd.concat([left, right], ignore_index=True)
    prior = frame[["nhl_game_id", "player_id", "mp_xg_l", "pp_toi_seconds"]].rename(
        columns={"player_id": "mate", "mp_xg_l": "mate_xg", "pp_toi_seconds": "mate_pp"})
    edges = edges.merge(prior, on=["nhl_game_id", "mate"], how="left")
    known = edges.dropna(subset=["mate_xg"])
    if not len(known):
        return empty
    known = known.assign(wx=known.shared_seconds.to_numpy() * known.mate_xg.to_numpy())
    grouped = known.groupby(["nhl_game_id", "player_id"], sort=False)
    lm = (grouped["wx"].sum() / grouped["shared_seconds"].sum()).rename("lm_raw").reset_index()
    pp = known[known.mate_pp >= PP_UNIT_SECONDS]
    if len(pp):
        pgp = pp.groupby(["nhl_game_id", "player_id"], sort=False)
        unit = (pgp["wx"].sum() / pgp["shared_seconds"].sum()).rename("pp_unit_raw").reset_index()
        lm = lm.merge(unit, on=["nhl_game_id", "player_id"], how="left")
    else:
        lm["pp_unit_raw"] = np.nan
    return lm


def add_moneypuck_skater_features(frame: pd.DataFrame, skaters: pd.DataFrame,
                                  teams: pd.DataFrame, mates: pd.DataFrame) -> pd.DataFrame:
    """Prior-game candidate inputs on a skater frame. The current game is not an input.

    Credit MoneyPuck.com for the skater and team tables (personal, non-commercial).
    `skaters` is all-situation `moneypuck_skater_games` (player_id, nhl_game_id,
    i_f_x_goals, i_f_shot_attempts, i_f_high_danger_shots). `teams` is
    all-situation `moneypuck_team_games` (nhl_game_id, team, game_date,
    shots_on_goal_against, x_goals_against). `mates` is regular-season
    `nhl_shift_linemates` (nhl_game_id, player_id_lo, player_id_hi, shared_seconds).

    Each feature is a shifted weighted mean of EARLIER rows, the same arithmetic
    as shots_l. A player's own xG tonight, tonight's linemates, and the
    opponent's shots tonight are not in the row. Daily Faceoff and EDGE are
    not read. Rows with no MoneyPuck history stay null and `usable` drops them.
    Shift-chart features stay null before 2023-24 and `usable` keeps the row.
    """
    d = frame.copy()
    raw = skaters[["player_id", "nhl_game_id", "i_f_x_goals", "i_f_shot_attempts",
                   "i_f_high_danger_shots"]].copy()
    for c in ("player_id", "nhl_game_id"):
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    for c in ("i_f_x_goals", "i_f_shot_attempts", "i_f_high_danger_shots"):
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw.dropna(subset=["player_id", "nhl_game_id"]).drop_duplicates(["player_id", "nhl_game_id"])
    d = d.drop(columns=[c for c in raw.columns if c in d.columns and c not in ("player_id", "nhl_game_id")])
    d = d.merge(raw, on=["player_id", "nhl_game_id"], how="left")
    d["game_date"] = pd.to_datetime(d["game_date"])
    d = d.sort_values(["player_id", "game_date", "nhl_game_id"]).reset_index(drop=True)
    g = d.groupby("player_id", sort=False)
    d["mp_xg_l"], d["mp_xg_s"] = _ew(g, "i_f_x_goals", 30), _ew(g, "i_f_x_goals", 6)
    d["mp_att_l"], d["mp_att_s"] = _ew(g, "i_f_shot_attempts", 30), _ew(g, "i_f_shot_attempts", 6)
    d["mp_hd_l"], d["mp_hd_s"] = _ew(g, "i_f_high_danger_shots", 30), _ew(g, "i_f_high_danger_shots", 6)
    d["toi_trend"] = d["toi_s"] - d["toi_l"]
    d["pp_toi_trend"] = d["pp_toi_s"] - d["pp_toi_l"]

    sums = (d.groupby(["nhl_game_id", "team"], sort=False)["pp_toi_seconds"]
            .sum(min_count=1).rename("team_pp"))
    d = d.drop(columns=[c for c in ("team_pp",) if c in d.columns])
    d = d.merge(sums.reset_index(), on=["nhl_game_id", "team"], how="left")
    own_pp = d["pp_toi_seconds"]
    share = own_pp / d["team_pp"]
    share = share.where(own_pp.notna() & d["team_pp"].notna())
    share = share.mask((d["team_pp"] == 0) & own_pp.notna(), 0.0)
    d["pp_share_raw"] = share
    # A merge does not keep player-date order, and the weighted mean reads that order.
    d = d.sort_values(["player_id", "game_date", "nhl_game_id"]).reset_index(drop=True)
    g = d.groupby("player_id", sort=False)
    d["pp_share_l"], d["pp_share_s"] = _ew(g, "pp_share_raw", 20), _ew(g, "pp_share_raw", 4)

    raw_lm = _linemate_raw(d, mates)
    d = d.drop(columns=[c for c in ("lm_raw", "pp_unit_raw") if c in d.columns])
    d = d.merge(raw_lm, on=["nhl_game_id", "player_id"], how="left")
    d = d.sort_values(["player_id", "game_date", "nhl_game_id"]).reset_index(drop=True)
    g = d.groupby("player_id", sort=False)
    d["lm_q_l"], d["lm_q_s"] = _ew(g, "lm_raw", 30), _ew(g, "lm_raw", 6)
    d["pp_unit_l"], d["pp_unit_s"] = _ew(g, "pp_unit_raw", 30), _ew(g, "pp_unit_raw", 6)

    played = teams[["nhl_game_id", "team", "game_date", "shots_on_goal_against", "x_goals_against"]].copy()
    for c in ("shots_on_goal_against", "x_goals_against"):
        played[c] = pd.to_numeric(played[c], errors="coerce")
    played["game_date"] = pd.to_datetime(played["game_date"])
    played["nhl_game_id"] = pd.to_numeric(played["nhl_game_id"], errors="coerce")
    if "upcoming" in d.columns and bool(d.upcoming.any()):
        upcoming = d.loc[d.upcoming, ["nhl_game_id", "team", "opponent", "game_date"]].drop_duplicates()
        own = upcoming[["nhl_game_id", "team", "game_date"]]
        opp_rows = upcoming[["nhl_game_id", "opponent", "game_date"]].rename(columns={"opponent": "team"})
        extra = pd.concat([own, opp_rows], ignore_index=True)
        extra["shots_on_goal_against"] = np.nan
        extra["x_goals_against"] = np.nan
        played = pd.concat([played, extra], ignore_index=True)
    played = played.dropna(subset=["nhl_game_id", "team"]).drop_duplicates(["nhl_game_id", "team"], keep="first")
    played = played.sort_values(["team", "game_date", "nhl_game_id"]).reset_index(drop=True)
    tg = played.groupby("team", sort=False)
    played["mp_sa"] = _ew(tg, "shots_on_goal_against", 25, 5)
    played["mp_xga"] = _ew(tg, "x_goals_against", 25, 5)
    opp = played[["nhl_game_id", "team", "mp_sa", "mp_xga"]].rename(
        columns={"team": "opponent", "mp_sa": "opp_mp_sa", "mp_xga": "opp_mp_xga"})
    d = d.drop(columns=[c for c in ("opp_mp_sa", "opp_mp_xga") if c in d.columns])
    d = d.merge(opp, on=["nhl_game_id", "opponent"], how="left")
    drop = ["i_f_x_goals", "i_f_shot_attempts", "i_f_high_danger_shots",
            "pp_share_raw", "team_pp", "lm_raw", "pp_unit_raw"]
    return d.drop(columns=[c for c in drop if c in d.columns])


def usable(spec: Spec, frame: pd.DataFrame) -> pd.DataFrame:
    """Rows the model may train on or score: ten prior games and every required input present.

    Shift-chart features may be missing. Requiring them would delete the
    seasons the chart does not cover. Every other feature on the spec is required.
    """
    required = [f for f in spec.features if f not in SHIFT_OPTIONAL_FEATURES]
    return frame[frame.gp >= MIN_GAMES].dropna(subset=required)


# ── model ────────────────────────────────────────────────────────────────────

def _x(spec: Spec, rows: pd.DataFrame) -> np.ndarray:
    return rows[list(spec.features)].values.astype(float)


def excess_variance(y: np.ndarray, mu: np.ndarray) -> float:
    """alpha in var = mu + alpha * mu^2, by moments. 0 when the counts are no wider than Poisson."""
    y, mu = np.asarray(y, dtype=float), np.asarray(mu, dtype=float)
    return max(0.0, float(((y - mu) ** 2 - mu).sum() / (mu ** 2).sum()))


def fit(spec: Spec, frame: pd.DataFrame, through_season: int) -> dict:
    """Fit on every played, usable row from FIRST_TRAIN_SEASON through `through_season`."""
    from xgboost import XGBRegressor
    tr = usable(spec, frame[~frame.upcoming]).dropna(subset=[spec.stat])
    tr = tr[tr.season.between(FIRST_TRAIN_SEASON, through_season)]
    model = XGBRegressor(**PARAMS)
    y = tr[spec.stat].values.astype(float)
    model.fit(_x(spec, tr), y)
    alpha = excess_variance(y, np.clip(model.predict(_x(spec, tr)), 1e-3, None)) if spec.overdispersed else 0.0
    return {"model": model, "dispersion": alpha, "n_train": len(tr)}


def predict_mean(spec: Spec, fitted: dict, rows: pd.DataFrame) -> np.ndarray:
    return np.clip(fitted["model"].predict(_x(spec, rows)), 1e-3, None)


def p_over(mu, line, dispersion: float = 0.0) -> np.ndarray:
    """P(count > line): the tail above floor(line), Poisson or (dispersion > 0) negative binomial."""
    k = np.floor(np.asarray(line, dtype=float))
    mu = np.asarray(mu, dtype=float)
    if dispersion <= 1e-9:
        return poisson.sf(k, mu)
    n = 1.0 / dispersion
    return nbinom.sf(k, n, n / (n + mu))


def win_per_unit(american: float) -> float:
    return american / 100.0 if american > 0 else 100.0 / abs(american)


def implied(american: float) -> float:
    return 100.0 / (american + 100.0) if american > 0 else abs(american) / (abs(american) + 100.0)


def expected_value(p: float, american: float) -> float:
    return p * (1 + win_per_unit(american)) - 1
