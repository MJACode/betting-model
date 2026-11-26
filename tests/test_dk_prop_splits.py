"""DraftKings prop splits from DK Network's articles (data/ingestors/dk_prop_splits.py).

The two bodies are cut from the HTML worker_jobs 1723195 printed for posts 481849 (2026-11-23, the side_line
layout) and 443922 (2026-09-14, the leaders layout), entities and markup as served. No network, no database.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from data.ingestors import dk_prop_splits as dps

ROOT = Path(__file__).resolve().parents[1]

NOV = (
    '<p class="wp-block-paragraph"><em>Updated Monday, Nov. 23 at 6:04 p.m. ET.</em></p>\n\n'
    '<figure class="wp-block-table"><table><thead><tr><th>Rank</th><th>Most bet by handle</th>'
    '<th>Most bet by bets</th></tr></thead><tbody><tr><td>1</td><td>Ja&#8217;Marr Chase</td>'
    '<td>Ja&#8217;Marr Chase</td></tr></tbody></table></figure>\n\n'
    '<h2 id="bengals-vs-commanders-player-prop-betting-splits" class="wp-block-heading">Bengals vs. Commanders '
    'player prop betting splits</h2>\n\n<h3 id="h-bengals-vs-commanders-passing-prop-betting-splits" '
    'class="wp-block-heading">Bengals vs. Commanders passing prop betting splits</h3>\n\n'
    '<figure class="wp-block-table"><table><thead><tr><th>Player</th><th>Market</th><th>Line</th>'
    '<th>Handle split</th><th>Bet split</th></tr></thead><tbody><tr><td>Jayden Daniels</td>'
    '<td>Passing completions</td><td>Under 20.5</td><td>66%</td><td>56%</td></tr><tr><td>Joe Burrow</td>'
    '<td>Passing completions</td><td>Under 27.5</td><td>96%</td><td>82%</td></tr><tr><td>Jayden Daniels</td>'
    '<td>Passing yards</td><td>Over 222.5</td><td>50%</td><td>78%</td></tr></tbody></table></figure>')

SEP = (
    '<p class="wp-block-paragraph"><em>Updated September 14, 2026. Splits are a snapshot and may change before '
    'kickoff.</em></p>\n\n<h3 class="wp-block-heading">Passing player prop bet splits</h3>\n\n'
    '<figure class="wp-block-table"><table class="has-fixed-layout"><thead><tr><th>Player prop</th><th>Line</th>'
    '<th>Handle leader</th><th>Bet leader</th></tr></thead><tbody><tr><td>Bo Nix Passing Completions</td>'
    '<td>21.5</td><td>Over (99.1%)</td><td>Over (97.1%)</td></tr><tr><td>Patrick Mahomes Longest Passing '
    'Completion</td><td>35.5</td><td>Over (65.7%)</td><td>Under (53.1%)</td></tr><tr><td>Bo Nix passing yards '
    '&#8211; first half</td><td>109.5</td><td>Under (75.4%)</td><td>Under (66.7%)</td></tr></tbody></table>'
    '</figure>')


def test_side_line_layout_reads_the_named_sides_shares_and_skips_the_rank_table():
    rows, skipped = dps.parse_article(NOV)
    assert skipped == 1                               # the anytime-TD rank list carries no percentages
    assert [(r["player"], r["market"], r["line_value"], r["handle_side"], r["handle_pct"], r["bets_side"],
             r["bets_pct"]) for r in rows] == [
        ("Jayden Daniels", "Passing completions", 20.5, "under", 66.0, "under", 56.0),
        ("Joe Burrow", "Passing completions", 27.5, "under", 96.0, "under", 82.0),
        ("Jayden Daniels", "Passing yards", 222.5, "over", 50.0, "over", 78.0)]
    assert {r["layout"] for r in rows} == {"side_line"}
    assert rows[0]["section"] == "Bengals vs. Commanders passing prop betting splits"
    assert [(r["table_no"], r["row_no"]) for r in rows] == [(2, 1), (2, 2), (2, 3)]


def test_leaders_layout_keeps_each_leaders_own_side():
    rows, skipped = dps.parse_article(SEP)
    assert skipped == 0
    assert [(r["prop_text"], r["line_value"], r["handle_side"], r["handle_pct"], r["bets_side"], r["bets_pct"])
            for r in rows] == [
        ("Bo Nix Passing Completions", 21.5, "over", 99.1, "over", 97.1),
        # The handle leader and the bet leader are different sides on this row.
        ("Patrick Mahomes Longest Passing Completion", 35.5, "over", 65.7, "under", 53.1),
        ("Bo Nix passing yards – first half", 109.5, "under", 75.4, "under", 66.7)]
    assert all(r["player"] is None and r["layout"] == "leaders" for r in rows)


def test_a_table_with_unknown_columns_is_skipped_not_guessed():
    html = "<table><tr><th>Player</th><th>Odds</th></tr><tr><td>Bo Nix</td><td>-110</td></tr></table>"
    assert dps.parse_article(html) == ([], 1)
    # Rows that WOULD read under the side_line columns, under headers that are not that layout.
    html = ("<table><tr><th>Name</th><th>Prop</th><th>Pick</th><th>Money</th><th>Tickets</th></tr>"
            "<tr><td>Bo Nix</td><td>Passing yards</td><td>Over 220.5</td><td>60%</td><td>55%</td></tr></table>")
    assert dps.parse_article(html) == ([], 1)


def test_updated_text_and_title_filter():
    assert dps.updated_text(NOV) == "Updated Monday, Nov. 23 at 6:04 p.m. ET."
    assert dps.updated_text(SEP) == "Updated September 14, 2026."
    assert dps.is_prop_split_title("Vikings vs. 49ers Player Prop & Anytime TD Betting Splits for Sunday Night")
    assert not dps.is_prop_split_title("DraftKings Sportsbook Betting Splits for NFL")


GAMES = [{"game_id": "NFL_2026_12_CIN_WAS", "game_date": "2026-11-23", "home_team": "WAS", "away_team": "CIN"},
         {"game_id": "NFL_2026_12_MIN_SF", "game_date": "2026-11-22", "home_team": "SF", "away_team": "MIN"}]


def test_title_game_names_one_game_or_none():
    posted = datetime(2026, 11, 23, 23, 0, tzinfo=timezone.utc)
    assert dps.title_game("Bengals vs. Commanders Player Prop & Anytime TD Betting Splits", posted, GAMES) \
        == "NFL_2026_12_CIN_WAS"
    assert dps.title_game("Vikings vs. 49ers Player Prop & Anytime TD Betting Splits",
                          datetime(2026, 11, 22, 20, 0, tzinfo=timezone.utc), GAMES) == "NFL_2026_12_MIN_SF"
    assert dps.title_game("NFL Week 4 Sunday Player Prop Bet Splits", posted, GAMES) is None
    # Two games of the same pair inside the window: no answer, never a guess.
    twice = GAMES + [{**GAMES[0], "game_id": "NFL_2026_12_WAS_CIN", "home_team": "CIN", "away_team": "WAS",
                      "game_date": "2026-11-25"}]
    assert dps.title_game("Bengals vs. Commanders Player Prop Bet Splits", posted, twice) is None
    # Outside a day before to three after the post's date: no game.
    assert dps.title_game("Bengals vs. Commanders Player Prop Bet Splits",
                          datetime(2026, 11, 10, 20, 0, tzinfo=timezone.utc), GAMES) is None


class _Conn:
    def __init__(self, seen=()):
        self.seen = list(seen)
        self.articles, self.rows = [], []

    def execute(self, sql, params=None):
        rows = []
        if "to_regclass" in sql:
            rows = [(True,)]
        elif "FROM public.dk_prop_split_articles" in sql:
            rows = self.seen
        elif "FROM public.games" in sql:
            rows = [(g["game_id"], g["game_date"], g["home_team"], g["away_team"]) for g in GAMES]
        elif "INSERT INTO public.dk_prop_split_articles" in sql:
            self.articles.append(params)
        return type("C", (), {"fetchone": lambda s: rows[0] if rows else None, "fetchall": lambda s: rows})()

    def executemany(self, sql, rows):
        assert "INSERT INTO public.dk_prop_splits" in sql
        self.rows.extend(rows)

    def commit(self):
        pass


def _get(asked):
    def get(url, params):
        asked.append((url, params))
        if url == dps.WP_POSTS:
            if params["page"] > 1:
                return 200, "[]", {}
            return 200, json.dumps([
                {"id": 481849, "date_gmt": "2026-11-23T23:00:00", "modified_gmt": "2026-11-23T23:04:00",
                 "link": "a", "title": {"rendered": "Bengals vs. Commanders Player Prop &amp; Anytime TD Betting "
                                                    "Splits for Monday Night Football"}},
                {"id": 1, "date_gmt": "2026-11-23T12:00:00", "modified_gmt": "2026-11-23T12:00:00",
                 "link": "b", "title": {"rendered": "Monday Night Football picks"}}]), {"X-WP-TotalPages": "1"}
        if url == f"{dps.WP_POSTS}/481849":
            return 200, json.dumps({"modified_gmt": "2026-11-23T23:04:00", "content": {"rendered": NOV}}), {}
        raise AssertionError(f"unexpected fetch {url}")
    return get


def test_run_stores_a_new_version_with_its_game_and_ledger_row(monkeypatch):
    monkeypatch.setattr(dps.time, "sleep", lambda s: None)
    asked: list = []
    conn = _Conn()
    out = dps.run(conn, pages=3, get=_get(asked))
    assert out == {"posts": 1, "new_versions": 1, "rows": 3, "tables_skipped": 1, "with_game": 1}
    assert {r["game_id"] for r in conn.rows} == {"NFL_2026_12_CIN_WAS"}
    assert conn.rows[0]["post_modified"] == datetime(2026, 11, 23, 23, 4, tzinfo=timezone.utc)
    (art,) = conn.articles
    assert art["rows_stored"] == 3 and art["tables_skipped"] == 1 and art["game_id"] == "NFL_2026_12_CIN_WAS"
    assert art["updated_text"] == "Updated Monday, Nov. 23 at 6:04 p.m. ET."
    # The search is asked newest first, and the non-prop post's body is never fetched.
    assert asked[0][1]["orderby"] == "date" and asked[0][1]["order"] == "desc"
    assert [u for u, _ in asked].count(f"{dps.WP_POSTS}/481849") == 1


def test_run_does_not_fetch_a_version_already_in_the_ledger(monkeypatch):
    monkeypatch.setattr(dps.time, "sleep", lambda s: None)
    asked: list = []
    conn = _Conn(seen=[(481849, datetime(2026, 11, 23, 23, 4, tzinfo=timezone.utc))])
    out = dps.run(conn, pages=1, get=_get(asked))
    assert out["new_versions"] == 0 and conn.rows == [] and conn.articles == []
    assert all(u == dps.WP_POSTS for u, _ in asked)


def test_migration_is_guarded_locked_down_and_active():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert "dk_prop_splits_2026_11_26.sql" in ACTIVE_MIGRATIONS
    sql = (ROOT / "data" / "migrations" / "dk_prop_splits_2026_11_26.sql").read_text(encoding="utf-8")
    assert sql.index("RETURN;") < sql.index("CREATE TABLE")
    for t in ("dk_prop_split_articles", "dk_prop_splits"):
        assert f"ALTER TABLE public.{t} ENABLE ROW LEVEL SECURITY" in sql
        assert f"REVOKE ALL ON public.{t} FROM anon, authenticated" in sql
    statements = "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--")).upper()
    assert "DELETE" not in statements and "UPDATE " not in statements


def test_wired_into_the_splits_step_and_a_declared_backfill():
    src = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    assert "from data.ingestors.dk_prop_splits import run as run_dk_props" in src
    from tracking import job_queue
    assert job_queue.JOBS["dk_prop_splits_import"][1]({"pages": 50}) == {"pages": 50}
    declared = json.loads((ROOT / "jobs" / "declared_jobs.json").read_text(encoding="utf-8"))
    (entry,) = [d for d in declared if d.get("job_type") == "dk_prop_splits_import"]
    assert entry["args"] == {"pages": 50} and entry["requested_by"] == "mike"
