"""Only nba_prop_market reaches a play-in, playoff or Cup final game.

mike's rule, graded on 272 of them (docs/nba_search_postseason.md, branch nba-searches-graded):
it passed; none of the six nba_prop_projection cells did; every other NBA model was graded on
the regular season only. The feed writes a `games` row for every NBA event it quotes, so these
games reach `games` whether or not anything bets them. What keeps the other models off them is
one gate, and these tests are about that gate staying where it is.

The controls matter: every reader below is fed a regular-season game at the same lead, and must
return it, so a reader that returned nothing for some other reason cannot pass.
"""
from __future__ import annotations

import inspect
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import models.nba_total_luck as tl  # noqa: E402
import scripts.nba_first_half_total_luck_card as h1card  # noqa: E402
import scripts.nba_first_half_total_luck_window as h1w  # noqa: E402
import scripts.nba_pregame_window as pregame  # noqa: E402
import scripts.nba_prop_market_card as rule_card  # noqa: E402
import scripts.nba_prop_projection_card as pcard  # noqa: E402
import scripts.nba_team_total_luck_card as ttcard  # noqa: E402
import scripts.nba_team_total_luck_window as ttw  # noqa: E402
import scripts.nba_total_luck_card as tlcard  # noqa: E402
import scripts.nba_total_luck_window as tlw  # noqa: E402

NOW = datetime(2027, 4, 20, 22, 0, tzinfo=timezone.utc)


def _t(minutes: float) -> str:
    return (NOW + timedelta(minutes=minutes)).isoformat()


# The 2026-27 schedule as stored (production, 2026-11-02): regular-season days 10-20..04-11 and
# the Cup final's placeholder with no teams. A later season adds its play-in and playoff rows.
SCHED = [
    ("NBA_2026-10-20_a_b", 2027, "2026-10-20", "regular", "BOS", "NYK", True, True),
    ("NBA_2027-04-11_a_b", 2027, "2027-04-11", "regular", "BOS", "NYK", True, True),
    ("NBA_2026-12-11_nan_nan", 2027, "2026-12-11", "cup_final", "NaN", "NaN", False, False),
    ("NBA_2027-02-14_ALL_STAR", 2027, "2027-02-14", "allstar", "NaN", "NaN", False, False),
    ("NBA_2026-10-03_PRE", 2027, "2026-10-03", "preseason", "UTA", "DEN", False, False),
]
SCHED_COLS = ["game_id", "season", "game_date", "game_type", "home_team", "away_team",
              "in_games", "scored"]


def sched_frame(rows=SCHED) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=SCHED_COLS)


class _Conn:
    """Answers each read by its shape: tonight's games joined to the schedule, the season's
    schedule days, the schedule's rows with their teams, and the ledgers (all empty)."""

    def __init__(self, games, sched=SCHED):
        self.games, self.sched = list(games), list(sched)
        self._rows = []

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if "FROM games g LEFT JOIN nba_schedule" in s:
            self._rows = self.games
        elif s.startswith("SELECT DISTINCT season, game_date, game_type FROM nba_schedule"):
            self._rows = sorted({(r[1], r[2], r[3]) for r in self.sched})
        elif "FROM nba_schedule s LEFT JOIN games g" in s and "in_games" in s:
            self._rows = self.sched
        else:
            self._rows = []
        return self

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def rollback(self):
        pass


def _row(gid, kind, lead, home="LAL", away="GSW", day=None):
    day = day or gid.split("|")[0]
    return (gid, home, away, day, 2027, _t(lead), _t(lead) if kind else None, kind)


# Every lead any reader's window takes, so each reader sees each kind of game inside its window.
LEADS = (46, 48, 50, 52, 54, 55, 56, 58, 60, 62, 63, 64, 65, 66, 67)


def _rows():
    rows = []
    for lead in LEADS:
        rows += [
            _row(f"2027-04-20|REG{lead}", "regular", lead),
            _row(f"2027-04-13|PLAYIN{lead}", "playin", lead),
            _row(f"2027-04-20|PLAYOFF{lead}", "playoff", lead),
            _row(f"2026-12-11|CUPFINAL{lead}", "cup_final", lead),
            # the schedule does not list these: the feed wrote them, a refresh has not caught up
            _row(f"2027-04-20|UNLISTEDAPRIL{lead}", None, lead),
            _row(f"2026-12-11|UNLISTEDFINALDAY{lead}", None, lead),
        ]
    return rows


# The same schedule once the real games are listed: the row the feed mis-dates has something to be
# a copy of. Neither is on a date the leaked rows below fall on.
LISTED_FINAL = ("NBA_2026-12-11_NYK_OKC", 2027, "2026-12-11", "cup_final", "OKC", "NYK", False, False)
LISTED_PLAYIN = ("NBA_2027-04-13_CHA_MIA", 2027, "2027-04-13", "playin", "MIA", "CHA", False, False)
SCHED_LISTED = [*SCHED, LISTED_FINAL, LISTED_PLAYIN]


def _misdated_rows():
    """Feed rows dated onto a regular-season day, the real game listed within two days. The review's
    two, each the same either way round."""
    rows = []
    for lead in LEADS:
        rows += [
            _row(f"2027-04-20|REG{lead}", "regular", lead),
            _row(f"2026-12-10|FINALDAYBEFORE{lead}", None, lead, home="OKC", away="NYK"),
            _row(f"2026-12-10|FINALFLIPPED{lead}", None, lead, home="NYK", away="OKC"),
            _row(f"2027-04-11|PLAYINLASTDAY{lead}", None, lead, home="MIA", away="CHA"),
            _row(f"2027-04-11|PLAYINFLIPPED{lead}", None, lead, home="CHA", away="MIA"),
        ]
    return rows


def _ids(got) -> set[str]:
    if isinstance(got, dict):
        return set(got)
    if isinstance(got, list):
        return set(got)
    if isinstance(got, pregame.PregamePlan):
        return set(got.total_luck) | set(got.team_total.decide) | set(got.first_half.decide)
    return set(got.decide)


_READERS = {
    "nba_total_luck slate": lambda c: tlcard.slate(c, NOW, horizon_min=70),
    "nba_team_total_luck slate": lambda c: ttcard.slate(c, NOW),
    "nba_first_half_total_luck slate": lambda c: h1card.slate(c, NOW),
    "the projection model's slate": lambda c: rule_card.slate(c, NOW),
    "the projection model's to_project": lambda c: pcard.to_project(c, NOW),
    "nba_total_luck window": lambda c: tlw.plan(c, NOW),
    "nba_team_total_luck window": lambda c: ttw.plan(c, NOW),
    "nba_first_half_total_luck window": lambda c: h1w.plan(c, NOW),
    "the pregame plan": lambda c: pregame.plan(c, NOW),
}


@pytest.mark.parametrize("name", sorted(_READERS))
def test_no_other_nba_model_reaches_a_postseason_game(name, monkeypatch):
    monkeypatch.setattr(pcard, "ensure_tables", lambda c: None)
    got = _ids(_READERS[name](_Conn(_rows())))
    assert any("REG" in g for g in got), f"{name} returned no regular-season game: a vacuous pass"
    leaked = sorted(g for g in got if "REG" not in g)
    assert leaked == [], f"{name} reached {leaked}"


@pytest.mark.parametrize("name", sorted(_READERS))
def test_a_postseason_game_dated_onto_a_regular_season_day_reaches_no_other_model(name, monkeypatch):
    """The one input the review found that got past their gate: regular_season counts any unlisted
    row on a regular-season day. The real game is listed a day or two off, either way round."""
    monkeypatch.setattr(pcard, "ensure_tables", lambda c: None)
    got = _ids(_READERS[name](_Conn(_misdated_rows(), sched=SCHED_LISTED)))
    assert any("REG" in g for g in got), f"{name} returned no regular-season game: a vacuous pass"
    assert sorted(g for g in got if "REG" not in g) == []


def test_a_misdated_row_is_named_in_skipped_and_reported_as_refused_by_the_rule():
    """Not a silent drop: the slate says which listed game it is, and the rule's read does not price it."""
    rows = [_row("2026-12-10|FINALDAYBEFORE46", None, 46, home="OKC", away="NYK")]
    skipped = []
    assert tlcard.slate(_Conn(rows, sched=SCHED_LISTED), NOW, skipped, horizon_min=70) == {}
    assert skipped == ["2026-12-10|FINALDAYBEFORE46 (the schedule lists this game as NBA_2026-12-11_NYK_OKC)"]
    skipped = []
    assert rule_card.rule_slate(_Conn(rows, sched=SCHED_LISTED), NOW, skipped, horizon_min=70) == {}
    assert skipped == ["2026-12-10|FINALDAYBEFORE46 (the schedule lists this game as NBA_2026-12-11_NYK_OKC)"]


@pytest.mark.parametrize("row", [
    # three days off the final: outside the window
    _row("2026-12-08|THREEDAYS46", None, 46, home="OKC", away="NYK"),
    # one team of the final and another
    _row("2026-12-10|ONETEAM46", None, 46, home="OKC", away="BOS"),
])
def test_an_unlisted_row_that_is_no_copy_of_the_listed_game_stays_a_regular_season_game(row):
    """The Cup week's filler games: unlisted, on a regular-season day, and real."""
    assert list(tlcard.slate(_Conn([row], sched=SCHED_LISTED), NOW, horizon_min=70)) == [row[0]]


def test_a_listed_regular_game_is_never_asked_about_and_costs_no_schedule_read():
    """The last regular-season day can hold the two teams of a play-in two days on, and the row is real.
    A listed game never reaches the test. And an ordinary night makes no second read of the schedule."""
    rows = [_row("2027-04-11|LASTREGULAR46", "regular", 46, home="MIA", away="CHA")]
    conn = _Conn(rows, sched=SCHED_LISTED)
    seen = []
    real = conn.execute

    def spy(sql, params=None):
        seen.append(" ".join(sql.split()))
        return real(sql, params)

    conn.execute = spy
    assert list(tlcard.slate(conn, NOW, horizon_min=70)) == ["2027-04-11|LASTREGULAR46"]
    assert not any("in_games" in s for s in seen)


def test_before_the_schedule_lists_the_final_a_misdated_row_still_reaches_the_other_models():
    """What the fix cannot do, pinned so the follow-up's warning stays true: the final's slot has no teams,
    so nothing says this row is the final. Remove this test when something closes that gap."""
    rows = [_row("2026-12-10|FINALDAYBEFORE46", None, 46, home="OKC", away="NYK")]
    assert list(tlcard.slate(_Conn(rows), NOW, horizon_min=70)) == ["2026-12-10|FINALDAYBEFORE46"]


@pytest.mark.parametrize("name", sorted(_READERS))
def test_a_cup_final_espn_listed_under_a_reworded_note_reaches_no_other_model(name, monkeypatch):
    """The Cup final is known only by ESPN's note, and a listed 'regular' row passes every other
    model's gate. ESPN's own 2023 final read "NBA In-Season Tournament Championship". So the type
    the refresh stores is what's tested here, end to end: the reworded final goes in through the
    refresh's plan beside the league's placeholder, and whatever type comes out is what the
    other models read."""
    import data.ingestors.nba_schedule_refresh as nsr
    monkeypatch.setattr(pcard, "ensure_tables", lambda c: None)
    board = {"events": [{
        "id": "401909456", "date": "2026-12-12T01:00Z",
        "season": {"type": 2, "year": 2027},
        "status": {"type": {"name": "STATUS_SCHEDULED", "description": "Scheduled"}},
        "competitions": [{
            "date": "2026-12-12T01:00Z", "timeValid": True, "neutralSite": True,
            # neither word of the note the old test keyed on
            "notes": [{"headline": "Emirates NBA Tournament Final"}],
            "competitors": [
                {"homeAway": "home", "team": {"abbreviation": "OKC", "displayName": "Oklahoma City Thunder"}},
                {"homeAway": "away", "team": {"abbreviation": "NY", "displayName": "New York Knicks"}}],
        }],
    }]}
    placeholder = {"nba_game_id": "0062600001", "game_id": "NBA_2026-12-11_nan_nan", "season": 2027,
                   "game_type": "cup_final", "game_date": "2026-12-11",
                   "commence_time": "2026-12-12T01:00:00+00:00", "home_team": "NaN",
                   "away_team": "NaN", "status_text": "Scheduled"}
    p = nsr.plan(nsr.event_rows(board), [placeholder], {}, ["202612"], today="2026-12-11")
    final = next(r for r in p["upsert"] if r["game_id"] == "NBA_2026-12-11_NYK_OKC")
    # the reader sees this row on its own window, typed as the refresh typed it
    rows = [_row(f"2027-04-20|REG{lead}", "regular", lead) for lead in LEADS]
    rows += [_row(f"2026-12-11|FINAL{lead}", final["game_type"], lead) for lead in LEADS]
    got = _ids(_READERS[name](_Conn(rows)))
    assert any("REG" in g for g in got)
    assert sorted(g for g in got if "FINAL" in g) == [], f"{name} would bet the Cup final"


# ── who may read the new slate ───────────────────────────────────────────────

# name -> the files allowed to mention it. Anything else that names one of these is a new way
# for another model to reach these games, so it fails here and has to be argued for.
_ALLOWED = {
    "graded_postseason": {"models/nba_total_luck.py", "scripts/nba_total_luck_card.py"},
    "listed_twin": {"models/nba_total_luck.py", "scripts/nba_total_luck_card.py"},
    # the split read: `slate`'s old body and the postseason read, nothing else
    "_read_games": {"scripts/nba_total_luck_card.py"},
    # scripts/nba_s_postseason.py: the graded search lab defines its own offline function of this name
    # over the research cache; it imports nothing from the live read
    "postseason_games": {"scripts/nba_total_luck_card.py", "scripts/nba_prop_market_card.py",
                         "scripts/nba_s_postseason.py"},
    "rule_slate": {"scripts/nba_prop_market_card.py", "scripts/nba_prop_window.py"},
    # read-only: the alert's look back at what tipped
    "tipped_rule_games": {"scripts/nba_prop_market_card.py", "scripts/nba_pregame_window.py"},
    # read-only: the alert's look at two starts that disagree
    "disputed_start_games": {"scripts/nba_prop_market_card.py", "tracking/failure_alerter.py"},
}


def _python_sources():
    for sub in ("scripts", "models", "tracking", "data", "nfl", "ncaaf_live", "monitoring", "byom"):
        yield from sorted((ROOT / sub).rglob("*.py"))
    yield ROOT / "scheduler.py"
    yield ROOT / "run_pipeline.py"


@pytest.mark.parametrize("name", sorted(_ALLOWED))
def test_only_the_rule_reads_the_postseason_slate(name):
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    found = set()
    for path in _python_sources():
        if pattern.search(path.read_text(encoding="utf-8")):
            found.add(path.relative_to(ROOT).as_posix())
    assert found, f"nothing names {name}: this test has gone stale"
    assert found <= _ALLOWED[name], f"{name} is read from {sorted(found - _ALLOWED[name])}"


def test_the_projection_model_and_the_old_slate_stay_on_the_regular_season():
    """The design's whole isolation rests on these three lines never changing."""
    assert "rule_card.slate(" in inspect.getsource(pcard.to_project)
    assert "rule_card.slate(" in inspect.getsource(pcard.look)
    src = inspect.getsource(rule_card.slate)
    assert "tlcard.slate(" in src and "postseason" not in src.split('"""')[-1]
    assert "tl.regular_season(" in inspect.getsource(tlcard._regular_games)


# ── the pure gate ────────────────────────────────────────────────────────────

def _frame(*rows):
    return pd.DataFrame(rows, columns=["game_id", "season", "game_date", "game_type",
                                       "home_team", "away_team"])


def _post(*rows, sched=SCHED):
    return list(tl.graded_postseason(_frame(*rows), sched_frame(sched))["game_id"])


def _reg(*rows, sched=SCHED):
    days = sched_frame(sched)[["season", "game_date", "game_type"]]
    return list(tl.regular_season(_frame(*rows), days)["game_id"])


LISTED = [("PI", 2027, "2027-04-13", "playin", "MIA", "CHA"),
          ("PO", 2027, "2027-04-20", "playoff", "BOS", "NYK"),
          ("CF", 2027, "2026-12-11", "cup_final", "OKC", "NYK")]


def test_a_listed_play_in_playoff_or_cup_final_game_counts():
    assert _post(*LISTED) == ["PI", "PO", "CF"]


@pytest.mark.parametrize("row", [
    ("PRESEASON", 2027, "2026-10-03", "preseason", "UTA", "DEN"),
    ("ALLSTAR", 2027, "2027-02-14", "allstar", "LAL", "BOS"),
    ("REGULAR", 2027, "2027-03-01", "regular", "LAL", "BOS"),
    # no schedule at all for the season
    ("NOSCHEDULE", 2031, "2031-04-20", None, "LAL", "BOS"),
    # unlisted, in months that hold neither kind of game
    ("JULY", 2027, "2027-07-02", None, "LAL", "BOS"),
    ("JUNE30PLUS", 2027, "2027-07-01", None, "LAL", "BOS"),
    # unlisted, on a preseason day, on the All-Star day, on an ordinary day
    ("UNLISTEDPRE", 2027, "2026-10-03", None, "UTA", "DEN"),
    ("UNLISTEDALLSTAR", 2027, "2027-02-14", None, "LAL", "BOS"),
    ("UNLISTEDREG", 2027, "2027-03-01", None, "LAL", "BOS"),
    # no season on the row
    ("NOSEASON", None, "2027-04-20", None, "LAL", "BOS"),
    # a type the schedule does not have
    ("MADEUP", 2027, "2027-04-20", "friendly", "LAL", "BOS"),
])
def test_nothing_else_counts(row):
    assert _post(row) == []


def test_a_listed_row_needs_two_real_teams():
    """The stored Cup final is a placeholder typed cup_final with no teams, and it can sit in
    `games` (three of the Cup quarterfinal slots do): the type alone must not admit it."""
    assert _post(("CF", 2027, "2026-12-11", "cup_final", "NaN", "NaN"),
                 ("PO", 2027, "2027-04-20", "playoff", "TBD", "BOS")) == []


@pytest.mark.parametrize("gid,day,home,away", [
    ("APRIL13", "2027-04-13", "MIA", "CHA"),       # two days after the last regular day
    ("JUNE30", "2027-06-30", "BOS", "OKC"),        # the last day that can hold one
    ("FINALDAY", "2026-12-11", "OKC", "NYK"),      # the schedule's Cup final day
])
def test_an_unlisted_game_counts_on_a_day_only_these_games_fall_on(gid, day, home, away):
    """A failed refresh must not lose the game: the feed's row is enough on such a day."""
    assert _post((gid, 2027, day, None, home, away)) == [gid]


def test_an_unlisted_row_needs_two_real_teams():
    assert _post(("X", 2027, "2027-04-20", None, "NaN", "BOS"),
                 ("Y", 2027, "2027-04-20", None, "BOS", "TBD")) == []


@pytest.mark.parametrize("row", [
    *LISTED,
    ("REG", 2027, "2027-03-01", "regular", "LAL", "BOS"),
    ("UNLISTEDREG", 2027, "2027-03-01", None, "LAL", "BOS"),
    ("UNLISTEDFINAL", 2027, "2026-12-11", None, "OKC", "NYK"),
    ("UNLISTEDAPRIL", 2027, "2027-04-20", None, "OKC", "NYK"),
    # the one date the two gates meet: the season's last regular-season day
    ("LASTDAY", 2027, "2027-04-11", None, "OKC", "NYK"),
    ("PRE", 2027, "2026-10-03", "preseason", "UTA", "DEN"),
    ("ALLSTAR", 2027, "2027-02-14", "allstar", "LAL", "BOS"),
    ("JULY", 2027, "2027-07-02", None, "LAL", "BOS"),
])
def test_each_row_is_regular_or_postseason_or_neither(row):
    """Never both: a row in both sets would reach the other models as well as this one."""
    assert not (set(_post(row)) & set(_reg(row)))


def test_the_regular_gate_still_refuses_what_it_refused():
    """The same rows `regular_season` has always refused, through the function itself."""
    assert _reg(*LISTED) == []
    assert _reg(("UNLISTEDFINAL", 2027, "2026-12-11", None, "OKC", "NYK"),
                ("UNLISTEDAPRIL", 2027, "2027-04-20", None, "OKC", "NYK")) == []


# ── a feed row beside its real game: the stranded bet ────────────────────────
#
# Settlement needs the game's score, and ESPN's final lands on ESPN's id. A bet on any other id
# stays open for good, and one-a-game counts by id, so the real game can take a second bet.

REAL = ("NBA_2027-05-01_NYK_BOS", 2027, "2027-05-01", "playoff", "BOS", "NYK", True, False)


def test_a_wrong_date_feed_row_beside_its_listed_game_is_refused():
    """Measured on the 2026 WNBA playoffs: four live-feed rows with no score, the real games one
    to two days later under other ids (WNBA_2026-09-25_NY_MIN, 10-01_DAL_GSV, 10-03_NY_ATL,
    10-22_GSV_ATL)."""
    wrong = ("NBA_2027-04-30_NYK_BOS", 2027, "2027-04-30", None, "BOS", "NYK")
    assert _post(wrong, sched=[*SCHED, REAL]) == []
    # the same teams, the row reversed: the other team's home game a day out
    flipped = ("NBA_2027-04-30_BOS_NYK", 2027, "2027-04-30", None, "NYK", "BOS")
    assert _post(flipped, sched=[*SCHED, REAL]) == []
    # and the real game still counts
    assert _post(("NBA_2027-05-01_NYK_BOS", 2027, "2027-05-01", "playoff", "BOS", "NYK"),
                 sched=[*SCHED, REAL]) == ["NBA_2027-05-01_NYK_BOS"]


def test_the_next_game_of_a_series_is_not_a_twin_of_the_one_just_played():
    """143 of the 251 playoff games of 2023-24..2025-26 fall within two days of the previous game
    of their series (nba_schedule, 2026-11-02). A failed refresh leaves Game 4 unlisted beside a
    listed Game 3, and refusing it there would lose the very game the unlisted branch exists to
    keep. So a listed game that already has its final is no twin."""
    game3 = ("NBA_2027-05-01_NYK_BOS", 2027, "2027-05-01", "playoff", "BOS", "NYK", True, True)
    game4 = ("NBA_2027-05-03_NYK_BOS", 2027, "2027-05-03", None, "BOS", "NYK")
    assert _post(game4, sched=[*SCHED, game3]) == ["NBA_2027-05-03_NYK_BOS"]
    # with Game 3 still unscored the row could be a wrong date, so it waits
    unplayed = (*game3[:7], False)
    assert _post(game4, sched=[*SCHED, unplayed]) == []


def test_three_days_away_is_not_a_twin():
    far = ("NBA_2027-05-04_NYK_BOS", 2027, "2027-05-04", "playoff", "BOS", "NYK", True, False)
    assert _post(("NBA_2027-05-01_NYK_BOS", 2027, "2027-05-01", None, "BOS", "NYK"),
                 sched=[*SCHED, far]) == ["NBA_2027-05-01_NYK_BOS"]


def test_a_flipped_final_with_no_row_of_its_own_counts_because_the_results_step_can_score_it():
    """The feed and ESPN can disagree on who is home at a neutral court. If ESPN's id has no
    games row the score can only land on the feed's (nba_results_ingestor.match_game), so that
    row is the game. If ESPN's id does have one, the score goes there, so the feed's is refused."""
    feed = ("NBA_2026-12-11_OKC_NYK", 2027, "2026-12-11", None, "NYK", "OKC")
    espn_no_row = ("NBA_2026-12-11_NYK_OKC", 2027, "2026-12-11", "cup_final", "OKC", "NYK", False, False)
    espn_row = ("NBA_2026-12-11_NYK_OKC", 2027, "2026-12-11", "cup_final", "OKC", "NYK", True, False)
    assert _post(feed, sched=[*SCHED, espn_no_row]) == ["NBA_2026-12-11_OKC_NYK"]
    assert _post(feed, sched=[*SCHED, espn_row]) == []


# ── seasons ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("day,season", [
    ("2026-12-11", 2027), ("2027-04-15", 2027), ("2027-06-10", 2027),
    # the stored first and last of these games by season
    ("2023-12-09", 2024), ("2024-06-17", 2024), ("2024-12-17", 2025), ("2025-06-22", 2025),
    ("2025-12-16", 2026), ("2026-06-13", 2026),
])
def test_a_postseason_game_files_under_the_seasons_ending_year(day, season):
    """The gate reads a game's season against the schedule's last regular-season day, so a game filed
    a year out would be read as a summer row, or as a game of a season with no schedule."""
    from data.ingestors.nba_stats_ingestor import _nba_season_for_date
    from data.ingestors.odds_ingestor import _season_label
    assert _season_label("NBA", day) == season
    assert _nba_season_for_date(day) == season
