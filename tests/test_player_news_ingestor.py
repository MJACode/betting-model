"""Recent player news: parsing, player resolution, and the ESPN call budget.

WHY THIS EXISTS. The prop screens now open a "Recent News" sheet, and the sheet
is only as good as the join behind it -- a note stored against a name we never
resolve is a note nobody sees. Two things are pinned here above all:

  * an accented name still finds its news (the same fold data/name_match.py
    exists for, after ~9% of every MLB slate went unpriced on exactly this), and
    an AMBIGUOUS name resolves to no id rather than the wrong player's;
  * the ESPN call budget stays bounded. ESPN has IP-blocked this worker twice,
    and a per-team sweep is precisely how that happens a third time.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from data.ingestors import player_news_ingestor as pni


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _article(item_id="1", headline="Labors in no-decision Sunday", athletes=("Shota Imanaga",),
             published="2026-08-23T21:14:00Z", description="Allowed two runs over two-plus innings."):
    return {
        "id": item_id,
        "headline": headline,
        "description": description,
        "published": published,
        "links": {"web": {"href": f"https://espn.com/story/{item_id}"}},
        "categories": [
            {"type": "team", "team": {"id": "16", "description": "Chicago Cubs"}},
            *[
                {"type": "athlete", "athlete": {"id": str(i), "description": name}}
                for i, name in enumerate(athletes)
            ],
        ],
    }


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class FakeConn:
    """Captures executed SQL. Reads are served from `rows` keyed by a substring
    of the statement, so one fake covers the name index and the prop-team query."""

    def __init__(self, rows=None):
        self.rows = rows or {}
        self.statements = []
        self.commits = 0

    def execute(self, sql, params=()):
        self.statements.append((sql, params))
        for needle, result in self.rows.items():
            if needle in sql:
                return _Result(result)
        return _Result([])

    def commit(self):
        self.commits += 1

    def close(self):
        pass


class _Result:
    def __init__(self, rows):
        self._rows = rows
        self.rowcount = len(rows)

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


# ── Parsing ───────────────────────────────────────────────────────────────────

def test_an_article_becomes_an_item_with_its_players():
    item = pni._to_item(_article(athletes=("Shota Imanaga", "Randal Grichuk")))
    assert item is not None
    assert item.source == "espn"
    assert item.source_item_id == "1"
    assert item.headline == "Labors in no-decision Sunday"
    assert item.body == "Allowed two runs over two-plus innings."
    assert [p.name for p in item.players] == ["Shota Imanaga", "Randal Grichuk"]
    assert item.url == "https://espn.com/story/1"


def test_espn_carries_no_analysis_paragraph():
    """The ANALYSIS block is a licensed fantasy-notes feature. ESPN rows leave it
    NULL and the sheet omits the block -- it must never be faked from the body."""
    assert pni._to_item(_article()).analysis is None


def test_an_article_about_nobody_is_dropped():
    """The sheet is per player, so an item naming none has nowhere to appear."""
    article = _article()
    article["categories"] = [{"type": "team", "team": {"id": "16"}}]
    assert pni._to_item(article) is None


def test_an_article_with_no_timestamp_is_dropped():
    """published_at orders the sheet. A row without one would sort arbitrarily."""
    assert pni._to_item(_article(published=None)) is None


def test_the_same_player_tagged_twice_appears_once():
    item = pni._to_item(_article(athletes=("Shota Imanaga", "Shota Imanaga")))
    assert len(item.players) == 1


def test_timestamps_are_parsed_before_they_are_compared():
    """These arrive as 'Z'-suffixed strings; a string compare on mixed shapes is
    the §7 trap. Parse to an aware datetime."""
    parsed = pni._parse_published("2026-08-23T21:14:00Z")
    assert parsed == datetime(2026, 8, 23, 21, 14, tzinfo=timezone.utc)
    assert pni._parse_published("not a date") is None
    assert pni._parse_published(None) is None


# ── The ESPN call budget ──────────────────────────────────────────────────────

def test_the_league_feed_runs_once_and_team_feeds_are_capped(monkeypatch):
    monkeypatch.setattr(config, "PLAYER_NEWS_MAX_TEAM_FETCHES", 2)
    calls = []

    def fake_fetch(url, params=None, headers=None, timeout=None):
        calls.append(params)
        return FakeResponse({"articles": [_article(item_id=str(len(calls)))]})

    items = pni.fetch_espn_news("MLB", teams=["CHC", "NYY", "BOS", "LAD"], fetch=fake_fetch)

    assert len(calls) == 3, "one league feed + at most two team feeds"
    assert "team" not in calls[0]
    assert [c["team"] for c in calls[1:]] == [
        config.ESPN_MLB_TEAM_IDS["CHC"], config.ESPN_MLB_TEAM_IDS["NYY"]
    ]
    assert len(items) == 3


def test_the_same_story_in_two_feeds_is_stored_once():
    """A team feed repeats the league feed's biggest story. Same id, one item."""
    def fake_fetch(url, params=None, headers=None, timeout=None):
        return FakeResponse({"articles": [_article(item_id="42")]})

    items = pni.fetch_espn_news("MLB", teams=["CHC"], fetch=fake_fetch)
    assert len(items) == 1


def test_a_dead_feed_is_a_quiet_zero():
    """A news outage must never fail the pipeline step it runs in."""
    def fake_fetch(url, params=None, headers=None, timeout=None):
        raise RuntimeError("connection reset")

    assert pni.fetch_espn_news("MLB", teams=[], fetch=fake_fetch) == []


def test_an_http_error_is_a_quiet_zero():
    def fake_fetch(url, params=None, headers=None, timeout=None):
        return FakeResponse({}, status_code=403)

    assert pni.fetch_espn_news("MLB", teams=[], fetch=fake_fetch) == []


def test_a_sport_with_no_espn_path_is_skipped():
    assert pni.fetch_espn_news("CRICKET", teams=[], fetch=None) == []


def test_a_sport_with_no_team_id_map_still_gets_its_league_feed():
    """NFL has no ESPN team id map in config. That must cost the league feed
    nothing -- a missing map is not an error."""
    calls = []

    def fake_fetch(url, params=None, headers=None, timeout=None):
        calls.append(params)
        return FakeResponse({"articles": [_article()]})

    items = pni.fetch_espn_news("NFL", teams=["KC", "BUF"], fetch=fake_fetch)
    assert len(calls) == 1
    assert len(items) == 1


# ── Resolving the feed's names to our players ─────────────────────────────────

def test_an_accented_name_resolves_to_our_player_id():
    """The feed writes "Jose Ramirez"; the log writes "José Ramírez". They are
    one player, and the fold is the only reason his news is reachable by id."""
    conn = FakeConn({"FROM player_game_log": [("545361", "José Ramírez")]})
    index = pni.build_name_index(conn, "MLB")
    assert index[pni.normalize_player_name("Jose Ramirez")] == "545361"


def test_two_players_sharing_a_name_resolve_to_no_id():
    """A wrong player's news is worse than none. Both stay readable by key."""
    conn = FakeConn({"FROM player_game_log": [("1", "Luis Garcia"), ("2", "Luis García Jr.")]})
    index = pni.build_name_index(conn, "MLB")
    assert index[pni.normalize_player_name("Luis Garcia")] is None


def test_an_unreadable_log_yields_an_empty_index_not_an_exception():
    class Boom(FakeConn):
        def execute(self, sql, params=()):
            raise RuntimeError("relation does not exist")

    assert pni.build_name_index(Boom(), "MLB") == {}


def test_a_sport_with_no_game_log_has_no_index():
    assert pni.build_name_index(FakeConn(), "NHL") == {}


# ── Storage ───────────────────────────────────────────────────────────────────

def test_one_row_is_written_per_player_on_an_item():
    conn = FakeConn()
    item = pni.NewsItem(
        source="espn",
        source_item_id="7",
        published_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
        headline="Cubs rout Mariners",
        players=[pni.NewsPlayer(name="Shota Imanaga"), pni.NewsPlayer(name="Randal Grichuk")],
    )
    written = pni.store_items(conn, "MLB", [item], {"shota imanaga": "12345"})

    assert written == 2
    inserts = [(s, p) for s, p in conn.statements if "INSERT INTO player_news" in s]
    assert len(inserts) == 2
    first = inserts[0][1]
    assert first[0] == "MLB"
    assert first[1] == "12345", "resolved id is stored"
    assert first[3] == "shota imanaga", "player_key is the normalized name"
    second = inserts[1][1]
    assert second[1] is None, "an unresolved player is still stored, by key"


def test_pruning_uses_the_configured_window():
    conn = FakeConn()
    pni.prune_old(conn, retention_days=21)
    sql, params = conn.statements[-1]
    assert "DELETE FROM player_news" in sql
    cutoff = params[0]
    assert timedelta(days=20) < datetime.now(timezone.utc) - cutoff < timedelta(days=22)


# ── The provider seam ─────────────────────────────────────────────────────────

def test_an_unknown_provider_is_refused_rather_than_defaulted(monkeypatch):
    """Silently falling back to ESPN would make a typo'd paid-feed rollout look
    like it worked."""
    monkeypatch.setattr(config, "PLAYER_NEWS_PROVIDER", "rotowire-typo")
    assert pni.ingest_player_news(conn=FakeConn()) == {"skipped": "unknown_provider"}


def test_a_fresh_table_is_not_refetched(monkeypatch):
    monkeypatch.setattr(config, "PLAYER_NEWS_PROVIDER", "espn")
    conn = FakeConn({"SELECT MAX(ingested_at)": [(datetime.now(timezone.utc),)]})
    result = pni.ingest_player_news(conn=conn, max_age_min=60)
    assert result["skipped"] == "fresh"
    assert not any("INSERT INTO player_news" in s for s, _ in conn.statements)


def test_an_empty_table_is_never_treated_as_fresh():
    """No rows means "never ingested", which must fetch, not skip."""
    assert pni._minutes_since_last_ingest(FakeConn()) is None


# ── The app's copy of the fold ────────────────────────────────────────────────

def test_the_app_mirrors_the_python_name_fold():
    """mobile/src/lib/playerNews.ts re-implements normalize_player_name so the
    app can query player_key. Derived rather than hand-copied: if the Python
    rule gains a suffix or a folded character and the TS does not, the name
    fallback silently stops matching -- which is the accented-name failure over
    again, one layer up."""
    from data import name_match

    ts = (Path(__file__).parent.parent / "mobile/src/lib/playerNews.ts").read_text()

    for suffix in name_match._SUFFIXES:
        assert f"'{suffix}'" in ts, f"TS mirror is missing the '{suffix}' suffix"

    for ch in "'‘’ʼ.":
        assert ch in ts, f"TS mirror does not delete {ch!r}"
    for ch in "-‐‑‒–—_":
        assert ch in ts, f"TS mirror does not fold {ch!r} to a space"
