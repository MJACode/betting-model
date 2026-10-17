"""NBA on-court lineup segments ("stints") from ESPN play-by-play. Pure, no I/O.

The writer is data/ingestors/nba_pbp.py; this module takes one game's plays
(rows shaped like the `nba_pbp` table) plus the box score's roster and
starters, and returns one row per continuous segment with the same ten players
on the floor. Every rule below was measured on the sportsdataverse ESPN files
(2018-19 and 2025-26) before it was written; the measurements are in the
docstrings so a later reader can re-check them.

ORDER. Plays are ordered by (period, clock remaining descending, ESPN
sequence number). ESPN's own sequence number is NOT a time order: sorting by it
alone put periods out of order in 239 games of 2018-19 and 446 of 2025-26, and
ran the clock backwards in nearly every game (corrections are appended with
later sequence numbers). The clock-first order has no period or clock
violations and is the order sportsdataverse ships its rows in.

POINTS. A play's points come from what it IS, not from the score columns: a
made field goal is worth its shot value (classify_field_goal); a made free
throw is 1. ESPN's score columns are stale on non-scoring rows (a substitution
between two free throws carries the score from before the first one), and
`score_value` is 0 on every made free throw in the 2018-19 file.

SUBSTITUTIONS DURING FREE THROWS. A substitution logged after a foul and before
the last free throw of that trip, at the same clock, is moved to just after the
last free throw. The free throws are then credited to the players who were on
the floor when the foul happened, which is the convention public adjusted
plus-minus work uses (pbpstats). Without it, a two-shot trip with a change
between the shots creates a zero-second segment that scores a point.

WHO STARTS A PERIOD. ESPN logs no substitutions between periods. Period 1's
five are the box score's starters. For every other period a player is on the
floor at its start when his first appearance in the period is anything other
than being substituted IN (he is substituted out, or records any play). A
player who plays a whole period without a single play or substitution is
invisible to that rule; the period is then filled to five from the team's
players with no appearance in the period, preferring those on the floor when
the previous period ended and then those with the most box-score time not yet
accounted for (the fill order is in `_fill_candidates`).

POSSESSIONS (stated, as the task asks). Counted from events, not estimated.
A team's possession ends on: a made field goal (unless an and-one free throw
by the same team follows at the same clock, in which case the free throw ends
it when made); a made last free throw of a trip (technical, flagrant and
clear-path free throws never end one: the team keeps the ball or it is a
dead-ball extra); a defensive rebound by the other team; a turnover; and the
end of a period, when the team holding the ball got it with time left on the
clock. A possession is credited to the segment in which it ENDS. The Oliver
counts (FGA, FTA, offensive rebounds, turnovers) are kept on every row too, so
the estimate FGA - OREB + TOV + 0.44 x FTA can be recomputed per segment.
ESPN logs a team "offensive rebound" after every missed non-final free throw
(6,784 of 6,846 such misses in 2018-19); those are dead-ball rebounds and are
not counted.

GARBAGE TIME. Cleaning the Glass's published definition
(https://cleaningtheglass.com/stats/guide/garbage_time, read 2026-10-16):
the 4th quarter; score margin >= 25 with 12-9 minutes left, >= 20 with 9-6,
>= 10 for the rest of the quarter; two or fewer of the game's starters on the
floor combined; and "the game can never go back to being non-garbage time, or
this clock resets". So garbage time is the final stretch of a regulation game
during which those conditions hold without a break until the final buzzer; a
game that goes to overtime has none. Zero-second states (two scores at the same
clock) are ignored. A segment is split at the moment garbage time begins, so
every row is wholly in or wholly out of it: the same ten players can appear in
two consecutive rows once per game, at that split.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

HOME, AWAY = "H", "A"
SIDES = (HOME, AWAY)

REG_PERIOD_SECONDS = 720
OT_PERIOD_SECONDS = 300

# The 4th-quarter garbage-time bands, in seconds remaining: margin needed
# when MORE than this many seconds remain (checked in order), else the last.
GARBAGE_BANDS = ((540, 25), (360, 20))
GARBAGE_FINAL_MARGIN = 10
GARBAGE_MAX_STARTERS = 2

_FT_RE = re.compile(
    r"^Free Throw - (?:(?P<tech>Technical)|(?:(?P<kind>Flagrant|Clear Path) )?(?P<n>\d) of (?P<m>\d))")

# Plays whose athletes may be OFF the floor (bench technicals, ejections,
# reviews), so they never place a player on the court.
_PRESENCE_EXCLUDED = ("Ejection", "No Ejection", "Not Available", "Challenge")


def period_seconds(period: int) -> int:
    return REG_PERIOD_SECONDS if period <= 4 else OT_PERIOD_SECONDS


def period_start(period: int) -> int:
    """Game seconds elapsed when `period` begins."""
    if period <= 4:
        return REG_PERIOD_SECONDS * (period - 1)
    return 4 * REG_PERIOD_SECONDS + OT_PERIOD_SECONDS * (period - 5)


def game_seconds(n_periods: int) -> int:
    """48 minutes, plus 5 per overtime (a game is never shorter than four)."""
    return period_start(max(int(n_periods), 4) + 1)


def elapsed(period: int, clock: float) -> float:
    """Game seconds elapsed at `clock` seconds remaining in `period`."""
    return period_start(period) + period_seconds(period) - float(clock)


def parse_clock(display) -> float | None:
    """ESPN's clock display -> seconds remaining in the period.

    '11:47' -> 707.0, '0:2.1' -> 2.1, '45.3' -> 45.3. One 2025-26 game carries
    nine 'M:SS:hh' stamps ('1:38:59'); the third part is read as hundredths.
    """
    s = str(display if display is not None else "").strip()
    if not s:
        return None
    parts = s.split(":")
    try:
        if len(parts) == 1:
            return float(parts[0])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 60 + int(parts[1]) + int(parts[2]) / 100.0
    except ValueError:
        return None
    return None


# ── play classification ─────────────────────────────────────────────────────

def ft_info(type_text: str | None):
    """(kind, n, m) for a free throw, else None. kind is 'normal', 'technical',
    'flagrant', 'clear path' or 'other' (a free-throw label not recognised)."""
    t = type_text or ""
    if not t.startswith("Free Throw"):
        return None
    m = _FT_RE.match(t)
    if not m:
        return ("other", 0, 0)
    if m.group("tech"):
        return ("technical", 1, 1)
    kind = (m.group("kind") or "normal").lower()
    return (kind, int(m.group("n")), int(m.group("m")))


def is_sub(p) -> bool:
    return p.get("type_text") == "Substitution"


_SUB_RE = re.compile(r"^\s*(?P<pin>.*?)\s*enters the game for\s*(?P<pout>.*?)\s*$")


def sub_players(p) -> tuple[int | None, int | None]:
    """(player in, player out) for a substitution.

    Normally athlete_id_1 enters and athlete_id_2 leaves. ESPN sometimes splits
    one change into two half-rows: "Devin Harris enters the game for " (only
    the entering player) and " enters the game for Wesley Matthews", where
    athlete_id_1 is the player LEAVING. The text says which half a row is."""
    a1, a2 = p.get("athlete_id_1"), p.get("athlete_id_2")
    a1 = int(a1) if a1 is not None else None
    a2 = int(a2) if a2 is not None else None
    m = _SUB_RE.match(p.get("text") or "")
    if m:
        if not m.group("pin") and m.group("pout"):
            return None, a1
        if m.group("pin") and not m.group("pout"):
            return a1, None
    return a1, a2


def is_ft(p) -> bool:
    return ft_info(p.get("type_text")) is not None


def is_fga(p) -> bool:
    """A field-goal attempt. ESPN's 'No Shot (Default Shot)' placeholder (13
    rows in 2018-19, 2 in 2025-26) is one only when it scored."""
    if not p.get("shooting_play") or is_ft(p):
        return False
    return p.get("type_text") != "No Shot (Default Shot)" or bool(p.get("scoring_play"))


def is_foul(p) -> bool:
    t = p.get("type_text") or ""
    if t.startswith("Free Throw"):
        return False
    return "Foul" in t or "Technical" in t


def is_turnover(p) -> bool:
    t = p.get("type_text") or ""
    return ("Turnover" in t and t != "No Turnover") or t == "Traveling"


_FEET_RE = re.compile(r"(\d+)-foot")


def classify_field_goal(p) -> int:
    """2 or 3 for a field-goal attempt, from the best evidence the row has.

    In order: ESPN's points_attempted (2025-26 files carry it); the made
    shot's score_value (right on every made field goal; it is free throws
    whose score_value is 0 in 2018-19); the text ("three point" never appears
    on a two); the distance in the text (24 ft or more is a three, 21 or less a
    two); and, for 22-23 ft or no distance, the shot location: ESPN's raw
    coordinates put the basket at (25, 0) in feet, so 23.5 ft out, or 21.5 ft
    in a corner (within 9 ft of the basket's baseline line and 3.5 ft of a
    sideline), is a three.

    Measured against the truth the files carry: 74 wrong of 107,636 made
    field goals in 2018-19 (0.07%); 40 of 110,367 made and 104 of 125,747
    missed in 2025-26 (0.04% and 0.08%). Text alone missed 1.9% and 4.8%.
    """
    pa = p.get("espn_points_attempted")
    if pa in (2, 3):
        return int(pa)
    sv = p.get("espn_score_value")
    if p.get("scoring_play") and sv in (2, 3):
        return int(sv)
    text = (p.get("text") or "").lower()
    if "three point" in text:
        return 3
    m = _FEET_RE.search(text)
    feet = int(m.group(1)) if m else None
    if feet is not None and feet >= 24:
        return 3
    if feet is not None and feet <= 21:
        return 2
    x, y = p.get("coord_x"), p.get("coord_y")
    if x is None or y is None:
        return 2
    dist = ((float(x) - 25.0) ** 2 + float(y) ** 2) ** 0.5
    corner = float(y) <= 9.0 and (float(x) <= 3.5 or float(x) >= 46.5)
    return 3 if dist >= 23.5 or (corner and dist >= 21.5) else 2


def shot_value(p) -> int | None:
    """1 for a free throw, 2 or 3 for a field-goal attempt
    (classify_field_goal), None for a play that is not a shot. A row that
    already carries `shot_value` (an nba_pbp row) is taken at its word."""
    if p.get("shot_value") is not None:
        return int(p["shot_value"])
    if is_ft(p):
        return 1
    if is_fga(p):
        return classify_field_goal(p)
    return None


def play_points(p) -> int:
    """Points the play scored for its own team (see POINTS above)."""
    if not p.get("scoring_play"):
        return 0
    v = shot_value(p)
    return v or 0


def presence_eligible(p) -> bool:
    """Whether the athletes on this play must be on the floor."""
    t = p.get("type_text") or ""
    if is_sub(p):
        return False
    if "Technical" in t and not t.startswith("Free Throw"):
        return False
    return not any(x in t for x in _PRESENCE_EXCLUDED)


def _athletes(p):
    for k in ("athlete_id_1", "athlete_id_2", "athlete_id_3"):
        v = p.get(k)
        if v is not None:
            yield int(v)


def _opp(side):
    return AWAY if side == HOME else HOME if side == AWAY else None


# ── ordering ────────────────────────────────────────────────────────────────

def order_plays(plays: list[dict]) -> list[dict]:
    """(period, clock remaining desc, sequence) — see ORDER above."""
    return sorted(plays, key=lambda p: (int(p["period"]), -float(p["clock"]),
                                        int(p.get("sequence_number") or 0)))


def defer_subs_at_free_throws(plays: list[dict]) -> list[dict]:
    """Move substitutions logged between a foul and the last free throw of the
    trip (same period and clock) to just after that free throw."""
    out: list[dict] = []
    i, n = 0, len(plays)
    while i < n:
        j = i
        key = (plays[i]["period"], float(plays[i]["clock"]))
        while j < n and (plays[j]["period"], float(plays[j]["clock"])) == key:
            j += 1
        group = plays[i:j]
        ft_idx = [k for k, p in enumerate(group) if is_ft(p)]
        if ft_idx:
            first_ft, last_ft = ft_idx[0], ft_idx[-1]
            fouls = [k for k, p in enumerate(group) if k < first_ft and is_foul(p)]
            anchor = fouls[0] if fouls else first_ft
            moved = [p for k, p in enumerate(group) if anchor < k < last_ft and is_sub(p)]
            if moved:
                kept = [p for k, p in enumerate(group) if not (anchor < k < last_ft and is_sub(p))]
                pos = kept.index(group[last_ft]) + 1
                group = kept[:pos] + moved + kept[pos:]
        out.extend(group)
        i = j
    return out


# ── possessions ─────────────────────────────────────────────────────────────

def dead_ball_rebounds(plays: list[dict]) -> set[int]:
    """Indices of the team rebounds ESPN logs after a missed non-final free
    throw (no athlete, same team, the very next play)."""
    out = set()
    for k in range(1, len(plays)):
        p, prev = plays[k], plays[k - 1]
        if p.get("type_text") not in ("Offensive Rebound", "Defensive Rebound"):
            continue
        if p.get("athlete_id_1") is not None:
            continue
        info = ft_info(prev.get("type_text"))
        if info and info[0] != "technical" and info[1] < info[2] and not prev.get("scoring_play"):
            out.add(k)
    return out


def possession_ends(plays: list[dict], dead: set[int] | None = None) -> dict[int, str]:
    """{index: side whose possession ended at that play}, for one game's
    ordered plays. End-of-period possessions are keyed on the period's
    'End Period' play, or on the period's last play when ESPN has none."""
    dead = dead if dead is not None else dead_ball_rebounds(plays)
    ends: dict[int, str] = {}
    n = len(plays)
    i = 0
    while i < n:
        period = plays[i]["period"]
        j = i
        while j < n and plays[j]["period"] == period:
            j += 1
        in_poss = None
        last_end_clock = None
        end_marked = False
        for k in range(i, j):
            p = plays[k]
            side = p.get("team_side")
            t = p.get("type_text") or ""
            info = ft_info(t)
            if t == "End Period":
                if in_poss and (last_end_clock is None or last_end_clock > 0):
                    ends[k] = in_poss
                    last_end_clock = 0.0
                end_marked = True
                continue
            if side not in SIDES:
                continue

            def end(s, k=k, p=p):
                nonlocal in_poss, last_end_clock
                ends[k] = s
                in_poss = _opp(s)
                last_end_clock = float(p["clock"])

            if is_fga(p):
                if p.get("scoring_play"):
                    if _and_one_follows(plays, k, j, side):
                        in_poss = side
                    else:
                        end(side)
                else:
                    in_poss = side
            elif info:
                kind, nn, mm = info
                if kind == "technical":
                    pass
                elif kind in ("flagrant", "clear path"):
                    in_poss = side
                elif kind == "normal" and nn == mm and p.get("scoring_play"):
                    end(side)
                else:
                    in_poss = side
            elif t == "Defensive Rebound" and k not in dead:
                end(_opp(side))
            elif t == "Offensive Rebound" and k not in dead:
                in_poss = side
            elif is_turnover(p):
                end(side)
        if not end_marked and j > i and in_poss and (last_end_clock is None or last_end_clock > 0):
            ends[j - 1] = in_poss if j - 1 not in ends else ends[j - 1]
        i = j
    return ends


def _and_one_follows(plays, k, stop, side) -> bool:
    clock = float(plays[k]["clock"])
    for q in range(k + 1, stop):
        p = plays[q]
        if float(p["clock"]) != clock:
            return False
        info = ft_info(p.get("type_text"))
        if info and info[0] == "normal" and info[1] == 1 and info[2] == 1 \
                and p.get("team_side") == side:
            return True
    return False


# ── period starters ─────────────────────────────────────────────────────────

def pull_sub_ins_forward(plays: list[dict]) -> list[dict]:
    """Within one clock instant, move a substitution to just before the
    entering player's first play at that instant. ESPN sometimes logs a
    player's foul or rebound a line before the substitution that brought him
    on, at the same clock; read in order he would be on the floor before he
    entered."""
    out: list[dict] = []
    i, n = 0, len(plays)
    while i < n:
        j = i
        key = (plays[i]["period"], float(plays[i]["clock"]))
        while j < n and (plays[j]["period"], float(plays[j]["clock"])) == key:
            j += 1
        group = list(plays[i:j])
        k = 0
        while k < len(group):
            p = group[k]
            if is_sub(p):
                pin, _pout = sub_players(p)
                if pin is not None:
                    first = next((q for q in range(k) if presence_eligible(group[q])
                                  and pin in set(_athletes(group[q]))), None)
                    if first is not None:
                        group.insert(first, group.pop(k))
            k += 1
        out.extend(group)
        i = j
    return out


def appearances(period_plays: list[dict], roster: dict[int, str]) -> dict[int, list]:
    """{player: [(index in period, 'in' | 'out' | 'play'), ...]} in order."""
    out: dict[int, list] = {}
    for k, p in enumerate(period_plays):
        if is_sub(p):
            pin, pout = sub_players(p)
            if pin is not None:
                out.setdefault(pin, []).append((k, "in"))
            if pout is not None:
                out.setdefault(pout, []).append((k, "out"))
        elif presence_eligible(p):
            for a in _athletes(p):
                if a in roster:
                    out.setdefault(a, []).append((k, "play"))
    return out


def first_appearances(period_plays: list[dict], roster: dict[int, str]) -> dict[int, str]:
    """{player: 'start' | 'bench'} from each player's first appearance in the
    period: substituted in -> 'bench', anything else -> 'start'."""
    return {pid: ("bench" if seq[0][1] == "in" else "start")
            for pid, seq in appearances(period_plays, roster).items()}


def _next_appearance(app: dict, pid: int, k: int):
    for idx, kind in app.get(pid, ()):
        if idx > k:
            return idx, kind
    return None, None


def _side_of(pid, roster, p=None):
    s = roster.get(pid)
    if s is None and p is not None:
        s = p.get("team_side")
    return s


def _fill_candidates(side, seen, prev_end, roster, box_seconds, credited):
    """Players of `side` with no appearance in the period, in fill order:
    those on the floor when the previous period ended first, then by box
    seconds not yet credited to them (most first). A player with no box
    seconds never fills."""
    pool = [pid for pid, s in roster.items() if s == side and pid not in seen
            and (box_seconds.get(pid) or 0) > 0]

    def remaining(pid):
        return (box_seconds.get(pid) or 0) - credited.get(pid, 0.0)

    return sorted(pool, key=lambda pid: (pid not in prev_end, -remaining(pid), pid))


def _drop_one(lineup: set, app: dict, k: int, last_seen: dict, protect: set):
    """The player to take off a side that has six: the one whose next
    appearance in the period is being substituted IN (he cannot be on the
    floor), else one who never appears again in the period (the quietest
    first), else the one whose next appearance is furthest away."""
    best, best_key = None, None
    for pid in lineup:
        if pid in protect:
            continue
        idx, kind = _next_appearance(app, pid, k)
        if kind == "in":
            key = (0, last_seen.get(pid, -1))
        elif kind is None:
            key = (1, last_seen.get(pid, -1))
        else:
            key = (2, -idx)
        if best_key is None or key < best_key:
            best, best_key = pid, key
    return best


def _add_one(lineup: set, side: str, roster: dict, app: dict, k: int):
    """The player to put on a side that has four: the off-floor player whose
    next appearance is a play or being substituted OUT (so he must be on the
    floor by then), earliest first. None when no one qualifies."""
    best, best_idx = None, None
    for pid, s in roster.items():
        if s != side or pid in lineup:
            continue
        idx, kind = _next_appearance(app, pid, k)
        if kind in ("play", "out") and (best_idx is None or idx < best_idx):
            best, best_idx = pid, idx
    return best


# ── the derivation ──────────────────────────────────────────────────────────

@dataclass
class _Seg:
    period: int
    start: float
    lineup: dict
    garbage: bool
    score_start: tuple
    stats: dict = field(default_factory=lambda: {s: _blank() for s in SIDES})
    touched: bool = False

    def empty(self):
        return not self.touched


def _blank():
    return {"pts": 0, "poss": 0, "fga": 0, "fg3a": 0, "fg3m": 0, "fta": 0, "ftm": 0,
            "oreb": 0, "tov": 0}


@dataclass
class Diagnostics:
    """What the derivation had to infer or repair, per game (all counts)."""
    period_starts: int = 0          # team-periods whose five were set
    filled_prev_end: int = 0        # starters added from the previous period's end
    filled_box: int = 0             # starters added by box-score time left
    short_after_fill: int = 0       # team-periods still short of five at the start
    over_five_trimmed: int = 0      # team-periods whose plays implied six starters
    box_starters_bad: int = 0       # games' sides whose box starters were not usable
    sub_out_not_on: int = 0         # a player substituted out we did not have on
    sub_in_already_on: int = 0      # a player substituted in we already had on
    added_from_play: int = 0        # a player put on because he made a play
    dropped_extra: int = 0          # a sixth player taken off (lookahead)
    added_missing: int = 0          # a fifth player put on (lookahead)
    unknown_ft: int = 0             # free-throw labels the parser did not know
    garbage_start: float | None = None

    def as_dict(self):
        return dict(self.__dict__)


def derive_stints(plays: list[dict], roster: dict[int, str], starters: dict[str, set],
                  box_seconds: dict[int, float] | None = None,
                  ordered: bool = False) -> tuple[list[dict], Diagnostics]:
    """One game's segments.

    plays     rows shaped like nba_pbp: period, clock (seconds remaining),
              sequence_number, type_text, text, team_side ('H'/'A'/None),
              athlete_id_1..3, scoring_play, shooting_play.
    roster    {espn athlete id: 'H' | 'A'} from the box score.
    starters  {'H': {ids}, 'A': {ids}}, the box score's game starters.
    box_seconds  {espn athlete id: seconds played}, used only to fill a period
              whose five cannot all be seen in its plays.

    LINEUP REPAIRS (each counted in Diagnostics). ESPN drops or half-logs
    some substitutions. A sub is applied as written; a play by a player we do
    not have on the floor puts him on. At the end of each clock instant, a
    side with six loses the player `_drop_one` picks and a side with four gains
    the player `_add_one` picks, both by looking ahead in the period.
    """
    box_seconds = box_seconds or {}
    plays = list(plays) if ordered else order_plays(plays)
    plays = pull_sub_ins_forward(defer_subs_at_free_throws(plays))
    diag = Diagnostics()
    if not plays:
        return [], diag
    dead = dead_ball_rebounds(plays)
    ends = possession_ends(plays, dead)
    for p in plays:
        info = ft_info(p.get("type_text"))
        if info and info[0] == "other":
            diag.unknown_ft += 1

    # Pass 1 without a garbage split gives the 4th-quarter states; pass 2
    # splits at the garbage start that pass 1 found.
    _segs, states, _ = _walk(plays, roster, starters, box_seconds, ends, dead, None,
                             Diagnostics())
    g = garbage_start(states, max(int(p["period"]) for p in plays))
    segs, _, diag2 = _walk(plays, roster, starters, box_seconds, ends, dead, g, diag)
    diag2.garbage_start = g[0] if g else None
    return segs, diag2


def _walk(plays, roster, starters, box_seconds, ends, dead, garbage, diag):
    segs_out: list[dict] = []
    states: list[tuple] = []   # 4th quarter: (time, margin, starters_on, next_index)
    credited: dict[int, float] = {}
    score = {HOME: 0, AWAY: 0}
    prev_end: dict[str, set] = {HOME: set(), AWAY: set()}
    all_starters = set(starters.get(HOME, set())) | set(starters.get(AWAY, set()))
    g_time, g_index = garbage if garbage else (None, None)
    split_done = garbage is None

    def starters_on(lu):
        return len((lu[HOME] | lu[AWAY]) & all_starters)

    def close(seg, t):
        dur = t - seg.start
        if dur <= 0 and seg.empty():
            return
        for s in SIDES:
            for pid in seg.lineup[s]:
                credited[pid] = credited.get(pid, 0.0) + max(dur, 0.0)
        segs_out.append(_row(seg, t))

    n = len(plays)
    i = 0
    while i < n:
        period = int(plays[i]["period"])
        j = i
        while j < n and int(plays[j]["period"]) == period:
            j += 1
        pplays = plays[i:j]
        app = appearances(pplays, roster)
        p_start = float(period_start(period))
        p_end = p_start + period_seconds(period)
        lineup = _period_lineup(period, pplays, roster, starters, box_seconds,
                                prev_end, credited, diag, app)
        cur = _Seg(period, p_start, {s: set(lineup[s]) for s in SIDES}, False,
                   (score[HOME], score[AWAY]))
        if period == 4:
            states.append((p_start, abs(score[HOME] - score[AWAY]), starters_on(cur.lineup), i))
        last_seen: dict[int, int] = {}
        in_group: set[int] = set()

        for k in range(i, j):
            lk = k - i
            p = plays[k]
            t = elapsed(period, float(p["clock"]))
            if not split_done and k >= g_index and t >= g_time:
                if g_time > cur.start or not cur.empty():
                    close(cur, g_time)
                    cur = _Seg(period, g_time, {s: set(cur.lineup[s]) for s in SIDES},
                               True, (score[HOME], score[AWAY]))
                else:
                    cur.garbage = True
                split_done = True
            new = {s: set(cur.lineup[s]) for s in SIDES}
            if is_sub(p):
                pin, pout = sub_players(p)
                side = None
                for a in (pin, pout):
                    if a is not None:
                        side = side or _side_of(a, roster, p)
                if side in SIDES:
                    if pout is not None:
                        if pout in new[side]:
                            new[side].discard(pout)
                        else:
                            diag.sub_out_not_on += 1
                    if pin is not None:
                        if pin in new[side]:
                            diag.sub_in_already_on += 1
                        new[side].add(pin)
                        in_group.add(pin)
            elif presence_eligible(p):
                for a in _athletes(p):
                    s = roster.get(a)
                    if s in SIDES:
                        in_group.add(a)
                        if a not in new[s]:
                            new[s].add(a)
                            diag.added_from_play += 1
                            if len(new[s]) > 5:
                                out = _drop_one(new[s], app, lk, last_seen, in_group)
                                if out is not None:
                                    new[s].discard(out)
                                    diag.dropped_extra += 1
            group_end = k + 1 >= j or float(plays[k + 1]["clock"]) != float(p["clock"])
            if group_end:
                for s in SIDES:
                    while len(new[s]) > 5:
                        out = _drop_one(new[s], app, lk, last_seen, in_group)
                        if out is None:
                            break
                        new[s].discard(out)
                        diag.dropped_extra += 1
                    while len(new[s]) < 5:
                        add = _add_one(new[s], s, roster, app, lk)
                        if add is None:
                            break
                        new[s].add(add)
                        diag.added_missing += 1
                in_group = set()
            if new != cur.lineup:
                if t <= cur.start and cur.empty():
                    cur.lineup = new
                else:
                    close(cur, t)
                    cur = _Seg(period, t, new, cur.garbage, (score[HOME], score[AWAY]))
            _accumulate(cur, p, k, ends, dead, score)
            if is_sub(p):
                for a in sub_players(p):
                    if a is not None:
                        last_seen[a] = lk
            elif presence_eligible(p):
                for a in _athletes(p):
                    last_seen[a] = lk
            if period == 4:
                states.append((t, abs(score[HOME] - score[AWAY]), starters_on(cur.lineup), k + 1))
        if not split_done and period == 4 and g_index is not None and g_index >= j \
                and g_time < p_end:
            close(cur, g_time)
            cur = _Seg(period, g_time, {s: set(cur.lineup[s]) for s in SIDES}, True,
                       (score[HOME], score[AWAY]))
            split_done = True
        close(cur, p_end)
        prev_end = {s: set(cur.lineup[s]) for s in SIDES}
        if period == 4:
            states.append((p_end, abs(score[HOME] - score[AWAY]), 0, j))
        i = j

    segs_out = _merge_same_lineup(segs_out)
    for n_, r in enumerate(segs_out, start=1):
        r["stint_no"] = n_
    return segs_out, states, diag


def _period_lineup(period, pplays, roster, starters, box_seconds, prev_end, credited,
                   diag, app):
    diag.period_starts += 2
    status = {pid: ("bench" if seq[0][1] == "in" else "start") for pid, seq in app.items()}
    lineup = {}
    for s in SIDES:
        box5 = set(starters.get(s, set()))
        if period == 1 and len(box5) == 5 and not any(status.get(pid) == "bench" for pid in box5):
            lineup[s] = box5
            continue
        if period == 1:
            diag.box_starters_bad += 1
        on = {pid for pid, st_ in status.items() if st_ == "start" and roster.get(pid) == s}
        if len(on) > 5:
            # Six seen on the floor before any substitution: keep the five
            # seen earliest; the sixth came on through a substitution ESPN
            # did not log, and the walk puts him on at his first play.
            keep = sorted(on, key=lambda pid: (app[pid][0][0], pid))[:5]
            on = set(keep)
            diag.over_five_trimmed += 1
        if len(on) < 5:
            seen = set(status)
            for pid in _fill_candidates(s, seen, prev_end.get(s, set()), roster,
                                        box_seconds, credited):
                if len(on) >= 5:
                    break
                on.add(pid)
                if pid in prev_end.get(s, set()):
                    diag.filled_prev_end += 1
                else:
                    diag.filled_box += 1
        if len(on) < 5:
            diag.short_after_fill += 1
        lineup[s] = on
    return lineup


def _merge_same_lineup(rows: list[dict]) -> list[dict]:
    """Join consecutive rows of one period with the same ten players and the
    same garbage flag (a redundant substitution, or a repair that put back the
    player a half-logged change took off)."""
    out: list[dict] = []
    for r in rows:
        prev = out[-1] if out else None
        if (prev is not None and prev["period"] == r["period"]
                and prev["home_ids"] == r["home_ids"] and prev["away_ids"] == r["away_ids"]
                and prev["garbage_time"] == r["garbage_time"]
                and abs(prev["end_s"] - r["start_s"]) < 1e-6):
            prev["end_s"] = r["end_s"]
            prev["duration_s"] = round(prev["end_s"] - prev["start_s"], 1)
            for key in _blank():
                for side in ("home_", "away_"):
                    prev[side + key] += r[side + key]
            continue
        out.append(dict(r))
    return out


def _accumulate(seg: _Seg, p, k, ends, dead, score):
    side = p.get("team_side")
    if k in ends:
        seg.stats[ends[k]]["poss"] += 1
        seg.touched = True
    if side not in SIDES:
        return
    st = seg.stats[side]
    pts = play_points(p)
    if pts:
        st["pts"] += pts
        score[side] += pts
        seg.touched = True
    t = p.get("type_text") or ""
    if is_fga(p):
        st["fga"] += 1
        if shot_value(p) == 3:
            st["fg3a"] += 1
            if p.get("scoring_play"):
                st["fg3m"] += 1
        seg.touched = True
    elif is_ft(p):
        st["fta"] += 1
        if p.get("scoring_play"):
            st["ftm"] += 1
        seg.touched = True
    elif t == "Offensive Rebound" and k not in dead:
        st["oreb"] += 1
        seg.touched = True
    elif is_turnover(p):
        st["tov"] += 1
        seg.touched = True


def _row(seg: _Seg, end: float) -> dict:
    h, a = seg.stats[HOME], seg.stats[AWAY]
    row = {
        "period": seg.period,
        "start_s": round(seg.start, 1),
        "end_s": round(end, 1),
        "duration_s": round(end - seg.start, 1),
        "home_ids": sorted(seg.lineup[HOME]),
        "away_ids": sorted(seg.lineup[AWAY]),
        "n_home": len(seg.lineup[HOME]),
        "n_away": len(seg.lineup[AWAY]),
        "home_score_start": seg.score_start[0],
        "away_score_start": seg.score_start[1],
        "garbage_time": bool(seg.garbage),
    }
    for prefix, st in (("home_", h), ("away_", a)):
        for key, v in st.items():
            row[prefix + key] = v
    return row


def garbage_start(states: list[tuple], n_periods: int):
    """(game seconds, first play index) at which garbage time begins, or None.

    `states` are the 4th quarter's (time, margin, starters on floor, index of
    the next play) after each play, in order, closed by the quarter's end.
    A state holds from its time to the next state's time; it is split at
    9:00 and 6:00 remaining so each piece sits in one margin band.
    """
    if n_periods != 4 or len(states) < 2:
        return None
    q4_end = float(period_start(5))
    pieces = []   # (start, end, ok, next_index)
    for (t0, margin, on, nxt), (t1, *_rest) in zip(states, states[1:]):
        cuts = [t0] + [q4_end - b for b, _m in GARBAGE_BANDS if t0 < q4_end - b < t1] + [t1]
        for a, b in zip(cuts, cuts[1:]):
            pieces.append((a, b, _garbage_ok(q4_end - a, margin, on), nxt))
    start = None
    for a, b, ok, nxt in reversed(pieces):
        if b - a <= 0:
            continue
        if not ok:
            break
        start = (a, nxt)
    return start


def _garbage_ok(remaining: float, margin: int, starters_on: int) -> bool:
    need = GARBAGE_FINAL_MARGIN
    for secs, m in GARBAGE_BANDS:
        if remaining > secs:
            need = m
            break
    return margin >= need and starters_on <= GARBAGE_MAX_STARTERS
