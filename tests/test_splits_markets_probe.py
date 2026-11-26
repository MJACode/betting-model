"""scripts/splits_markets_probe.py: the parsers, on fixtures shaped like the 2026-11-03 probe's measured pages."""
from __future__ import annotations

import json
from pathlib import Path

import scripts.splits_markets_probe as P
from tracking import job_queue

ROOT = Path(__file__).resolve().parents[1]

# DK Network's text, as worker_jobs 936774 measured it (tags reduced to the shape the parser reads).
DK_PAGE = (
    '<a href="https://dknetwork.draftkings.com/draftkings-sportsbook-betting-splits/?tb_eg=88808&#038;'
    'itm_content=NFL&#038;tb_edate=n7days&#038;tb_emt=Moneyline">x</a>'
    '<a href="https://dknetwork.draftkings.com/draftkings-sportsbook-betting-splits/?tb_eg=88808&#038;'
    'itm_content=NFL&#038;tb_edate=n7days&#038;tb_emt=Spread">x</a>'
    '<a href="https://dknetwork.draftkings.com/draftkings-sportsbook-betting-splits/?tb_eg=42648&#038;'
    'itm_content=NBA&#038;tb_edate=n7days&#038;tb_emt=Total">x</a>'
    "<div>JAX Jaguars @ BAL Ravens Thu 11/5 Selection Odds Handle Bets Moneyline BAL Ravens +350 22% 10% "
    "Spread JAX Jaguars -8.5 -115 86% 82% Total Over 42.5 -105 50% 50% Under 42.5 -115 50% 50%</div>"
    "<div>CIN Bengals @ ATL Falcons Selection Odds Handle Bets Moneyline ATL Falcons +136 17% 16% "
    "Spread CIN Bengals -3 -115 50% 81% Total Over 52.5 -102 100% 100%</div>")


def test_dk_sport_links():
    assert P.dk_sport_links(DK_PAGE) == {"88808": "NFL", "42648": "NBA"}


def test_dk_markets_reads_filters_and_row_labels():
    d = P.dk_markets(DK_PAGE)
    assert d["filters"] == ["Moneyline", "Spread", "Total"]
    assert d["games"] == 2
    assert d["labels"] == {"Moneyline": 2, "Spread": 2, "Total": 2}


def test_an_split_markets_counts_only_split_markets_per_period():
    payload = {"games": [
        {"markets": {"15": {"event": {"moneyline": [{"bet_info": {"tickets": {"percent": 55}}}],
                                      "spread": [{"bet_info": {"tickets": {"percent": None}}}]},
                            "firsthalf": {"total": [{"bet_info": {"tickets": {"percent": 0}}}]}},
                     "30": {"event": {"moneyline": [{"bet_info": {"tickets": {"percent": 50}}}]}}}},
        {"markets": {"15": {"event": {"moneyline": [{"bet_info": {"tickets": {"percent": 61}}}]}}}},
    ]}
    # Book 30 (Open) is not asked; 0% (Action Network's no-split placeholder) and null are not splits.
    assert P.an_split_markets(payload) == {"15": {"event": {"moneyline": 2}}}


def test_probe_reports_each_source_and_fails_when_dk_is_unreachable(capsys):
    calls = []

    def get(url, **kw):
        calls.append((url, kw.get("params")))
        if "dknetwork" in url:
            return None, "", "ConnectionError: no route"
        return 200, json.dumps({"games": []}), None
    assert P.probe(get=get, today="20261126") == 1
    out = capsys.readouterr().out
    assert P.SUMMARY_MARK in out and "dk: ConnectionError" in out
    asked = {(p or {}).get("periods") for u, p in calls if "actionnetwork" in u}
    assert asked == set(P.AN_PERIODS)


def test_registered_as_a_worker_job_and_declared():
    assert "splits_markets_probe" in job_queue.JOBS
    declared = json.loads((ROOT / "jobs" / "declared_jobs.json").read_text(encoding="utf-8"))
    mine = [d for d in declared if d["job_type"] == "splits_markets_probe"]
    # The first run (markets and periods) and the rerun for team-total entry shapes, each run once.
    assert [d["key"] for d in mine] == ["splits-markets-probe-2026-11-26", "splits-team-totals-probe-2026-11-26",
                                        "splits-nonzero-probe-2026-11-26"]
    assert all(d["requested_by"] == "matt" and d["args"] == {} for d in mine)


def test_team_score_sample_keeps_the_raw_entries_and_drops_links():
    payload = {"games": [{"home_team_id": 1, "away_team_id": 2, "markets": {"15": {"event": {
        P.TEAM_SCORE_KEY: [{"side": "over", "team_id": 1, "value": 112.5, "deeplink": "x",
                            "bet_info": {"tickets": {"percent": 61}}}]}}}}]}
    out = P.team_score_sample(payload)
    assert out[0] == {"home_team_id": 1, "away_team_id": 2}
    assert out[1] == {"side": "over", "team_id": 1, "value": 112.5, "bet_info": {"tickets": {"percent": 61}}}
    assert P.team_score_sample({"games": [{"markets": {"15": {"event": {}}}}]}) == []


def test_samples_print_before_the_capped_summary(capsys):
    team = {"games": [{"home_team_id": 1, "markets": {"15": {"event": {P.TEAM_SCORE_KEY: [{"side": "over"}]}}}}]}
    P.probe(get=lambda url, **kw: (200, "" if "dknetwork" in url else json.dumps(team), None), today="20261126")
    after = capsys.readouterr().out.split(P.SUMMARY_MARK, 1)[1].strip().splitlines()
    assert after[0].startswith("team_score sample nba:")


def test_a_split_needs_a_non_zero_share_on_a_pre_game_entry():
    def g(tix, money, live=False):
        return {"games": [{"markets": {"15": {"firstquarter": {"total": [
            {"is_live": live, "bet_info": {"tickets": {"percent": tix}, "money": {"percent": money}}}]}}}}]}
    assert P.an_split_markets(g(0, 0)) == {}
    assert P.an_split_markets(g(0, 12)) == {"15": {"firstquarter": {"total": 1}}}
    assert P.an_split_markets(g(55, 60, live=True)) == {}


def test_asks_exactly_as_the_ingestor_does():
    seen = []
    P.probe(get=lambda url, **kw: seen.append(kw.get("params")) or (200, "{}", None), today="20261126")
    an = [p for p in seen if p and "periods" in p]
    assert an and all(p["bookIds"] == "15" for p in an)
