"""The PBP label comes from whichever twin row carries the final.

Four franchises are filed twice in `games` (ARI/AZ, CWS/CHW, OAK/ATH,
WSH/WAS) and the scores sit on the SBR-abbreviated twin. Reading only the
canonical row skipped every one of their games at ingest -- 534 priced 2025
games with no plays, and no CWS or WSH game in the 2024 corpus.
"""
from data.ingestors.mlb_pbp_ingestor import _lookup_home_won, mlb_game_final, sbr_twin_id


class _Conn:
    def __init__(self, rows):
        self.rows = rows
        self.asked = []

    def execute(self, sql, params):
        self.asked.append(params[0])
        row = self.rows.get(params[0])
        return _Cur(row)


class _Cur:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


def test_twin_id_swaps_only_the_renamed_franchises():
    assert sbr_twin_id("MLB_2025-06-12_OAK_WSH") == "MLB_2025-06-12_ATH_WAS"
    assert sbr_twin_id("MLB_2025-06-12_CHC_ARI") == "MLB_2025-06-12_CHC_AZ"
    assert sbr_twin_id("MLB_2025-06-12_NYY_BOS") is None


def test_unscored_live_row_falls_back_to_the_scored_twin():
    conn = _Conn({"MLB_2025-06-12_LAA_CWS": (None, None, None),
                  "MLB_2025-06-12_LAA_CHW": (3.0, 5.0, None)})
    assert mlb_game_final(conn, "MLB_2025-06-12_LAA_CWS") == (3.0, 5.0, 0)
    assert _lookup_home_won(conn, "MLB_2025-06-12_LAA_CWS") == 0
    assert conn.asked[:2] == ["MLB_2025-06-12_LAA_CWS", "MLB_2025-06-12_LAA_CHW"]


def test_scored_canonical_row_wins_and_keeps_its_label():
    conn = _Conn({"MLB_2025-06-12_NYY_BOS": (7.0, 2.0, 1)})
    assert mlb_game_final(conn, "MLB_2025-06-12_NYY_BOS") == (7.0, 2.0, 1)
    assert conn.asked == ["MLB_2025-06-12_NYY_BOS"]


def test_no_final_anywhere_is_none():
    conn = _Conn({"MLB_2025-06-12_LAA_CWS": (None, None, None)})
    assert mlb_game_final(conn, "MLB_2025-06-12_LAA_CWS") is None
    assert _lookup_home_won(conn, "MLB_2025-06-12_LAA_CWS") is None
