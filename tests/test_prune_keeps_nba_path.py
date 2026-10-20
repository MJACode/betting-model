"""data/prune_odds: NBA keeps its whole price path, thinned only of repeats.

The second NBA game-market search (docs/nba_models_2026.md §6.5) needs 2026-27
as an untouched season WITH its movement: when each book moved and from what.
The opener-and-close survivors of the ordinary prune cannot show that. These
run the real thinning SQL on SQLite and check what survives, not the SQL text.
"""
import sqlite3

from data import prune_odds as po

COLS = ("odds_id", "game_id", "sport", "market", "bookmaker", "snapshot_type",
        "snapshot_at", "home_price", "away_price", "draw_price", "spread_home",
        "total_line", "over_price", "under_price", "source")


class _Conn:
    """sqlite3 behind the DBConnection surface thin_repeats uses."""

    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute(f"CREATE TABLE odds ({', '.join(COLS)})")
        self.db.execute("CREATE TABLE games (game_id, sport, game_date)")
        self.n = 0

    def execute(self, sql, params=()):
        return self.db.execute(sql.replace("%s", "?"), tuple(params))

    def commit(self):
        self.db.commit()

    def game(self, gid, sport="NBA", day="2026-10-21"):
        self.db.execute("INSERT INTO games VALUES (?, ?, ?)", (gid, sport, day))

    def quote(self, gid, at, home, away, book="fanduel", market="h2h",
              stype="open", source=None, sport="NBA"):
        self.n += 1
        self.db.execute(f"INSERT INTO odds ({', '.join(COLS)}) VALUES "
                        f"({', '.join('?' * len(COLS))})",
                        (self.n, gid, sport, market, book, stype, at, home, away,
                         None, None, None, None, None, source))
        return self.n

    def ids(self):
        return {r[0] for r in self.db.execute("SELECT odds_id FROM odds")}

    def as_of(self, gid, at, book="fanduel", stype="open"):
        return self.db.execute(
            "SELECT home_price, away_price FROM odds WHERE game_id = ? AND bookmaker = ? "
            "AND snapshot_type = ? AND snapshot_at <= ? ORDER BY snapshot_at DESC LIMIT 1",
            (gid, book, stype, at)).fetchone()


def _ts(i):
    return f"2026-10-21T{i:02d}:00:00Z"


def test_an_unchanged_run_keeps_its_first_and_last_row():
    c = _Conn()
    c.game("G")
    ids = [c.quote("G", _ts(i), -110, -110) for i in range(5)]
    po.thin_repeats(c, today="2026-10-22")
    assert c.ids() == {ids[0], ids[-1]}


def test_every_move_survives_and_every_as_of_price_is_unchanged():
    c = _Conn()
    c.game("G")
    path = [(-110, -110), (-110, -110), (-110, -110), (-120, 100), (-120, 100),
            (-110, -110), (-110, -110), (-110, -110), (-110, -110)]
    for i, (h, a) in enumerate(path):
        c.quote("G", _ts(i), h, a)
    before = [c.as_of("G", _ts(i)) for i in range(len(path))]
    po.thin_repeats(c, today="2026-10-22")
    assert [c.as_of("G", _ts(i)) for i in range(len(path))] == before
    # runs: 0-2, 3-4, 5-8 -> keep 0, 2, 3, 4, 5, 8
    assert c.ids() == {1, 3, 4, 5, 6, 9}


def test_pre_game_and_in_play_are_separate_runs():
    c = _Conn()
    c.game("G")
    pre = [c.quote("G", _ts(i), -110, -110) for i in range(3)]
    live = [c.quote("G", _ts(i + 3), -110, -110, stype="in_play") for i in range(3)]
    po.thin_repeats(c, today="2026-10-22")
    assert c.ids() == {pre[0], pre[-1], live[0], live[-1]}


def test_paid_history_todays_games_and_other_sports_are_untouched():
    c = _Conn()
    c.game("PAID")
    c.game("TODAY", day="2026-10-22")
    c.game("MLB", sport="MLB")
    keep = set()
    for i in range(4):
        keep.add(c.quote("PAID", _ts(i), -110, -110, source="odds_api_historical"))
        keep.add(c.quote("TODAY", _ts(i), -110, -110))
        keep.add(c.quote("MLB", _ts(i), -110, -110, sport="MLB"))
    po.thin_repeats(c, today="2026-10-22")
    assert c.ids() == keep


def test_a_dry_run_counts_and_deletes_nothing():
    c = _Conn()
    c.game("G")
    for i in range(6):
        c.quote("G", _ts(i), -110, -110)
    out = po.thin_repeats(c, today="2026-10-22", dry_run=True)
    assert out["rows"] == 4 and len(c.ids()) == 6


def test_the_two_prune_tiers_never_select_a_path_kept_sport():
    params: dict = {}
    pred = po._unprotected(params, "odds")
    assert "path_kept_sports" in pred and params["path_kept_sports"] == ("NBA",)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE odds (bookmaker, source, sport)")
    db.executemany("INSERT INTO odds VALUES (?, NULL, ?)",
                   [("fanduel", "NBA"), ("fanduel", "MLB")])
    # the predicate's own SQL, run: only the MLB line-shop row is prunable
    sql = pred
    for k, v in params.items():
        lit = "(" + ", ".join(f"'{x}'" for x in v) + ")" if isinstance(v, tuple) else f"'{v}'"
        sql = sql.replace(f"%({k})s", lit)
    assert [r[0] for r in db.execute(f"SELECT sport FROM odds WHERE {sql}")] == ["MLB"]
