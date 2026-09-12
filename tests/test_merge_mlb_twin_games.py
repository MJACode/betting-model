"""The twin-game merge's id mapping, and the counts it verifies itself with.

The script itself writes to production and is run by hand; what is testable
(and what got the 2026-09-12 run a false FAILED) is the id arithmetic and the
shape of the verification.
"""
from scripts.merge_mlb_twin_games import CANON, canonical, counts


def test_only_the_four_renamed_franchises_map():
    assert canonical("MLB_2025-08-26_WAS_NYY") == "MLB_2025-08-26_WSH_NYY"
    assert canonical("MLB_2019-05-04_ATH_PIT") == "MLB_2019-05-04_OAK_PIT"
    assert canonical("MLB_2024-07-04_AZ_SF") == "MLB_2024-07-04_ARI_SF"
    assert canonical("MLB_2023-04-01_CHW_DET") == "MLB_2023-04-01_CWS_DET"


def test_a_canonical_id_maps_to_nothing():
    assert canonical("MLB_2025-08-26_WSH_NYY") is None
    assert canonical("MLB_2025-08-26_BOS_NYY") is None


def test_both_teams_are_mapped_in_one_id():
    assert canonical("MLB_2024-06-01_ATH_WAS") == "MLB_2024-06-01_OAK_WSH"


def test_a_non_mlb_or_malformed_id_is_left_alone():
    assert canonical("NFL_2025-09-07_KC_BUF") is None
    assert canonical("MLB_2025-08-26_WAS") is None
    assert canonical("nonsense") is None


def test_the_map_is_the_repo_abbreviation_in_every_case():
    assert CANON == {"AZ": "ARI", "CHW": "CWS", "ATH": "OAK", "WAS": "WSH"}


class _Conn:
    """Answers every count with a fixed number and records the scopes asked for."""

    def __init__(self):
        self.scopes = []
        self._n = 0

    def execute(self, sql, params=None):
        if "= ANY(" in sql:
            self.scopes.append(params[0])
        self._n += 1
        return self

    def fetchone(self):
        return (self._n,)


def test_an_empty_scope_counts_zero_rather_than_none():
    """The NO-OP re-run (nothing left to merge) must still verify, not crash
    on a None count — it did on 2026-09-12."""
    out = counts(_Conn(), [])
    assert out["odds_scoped"] is not None
    assert out["game_weather_scoped"] is not None


def test_the_scoped_count_asks_only_about_the_affected_ids():
    """Counting whole tables reported a false FAILED: `odds` grew by 34,134
    rows of TODAY's live games while the 2026-09-12 merge ran."""
    conn = _Conn()
    counts(conn, ["MLB_2025-08-26_WAS_NYY", "MLB_2025-08-26_WSH_NYY"])
    assert conn.scopes and all(
        s == ["MLB_2025-08-26_WAS_NYY", "MLB_2025-08-26_WSH_NYY"] for s in conn.scopes)
