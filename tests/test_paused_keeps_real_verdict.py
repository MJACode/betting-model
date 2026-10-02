"""A paused model keeps its REAL verdict; being paused only means "not a signal".

2026-09-28, Matt via CoS (Michael-gated: model change). models/scorer.
_paused_signal used to turn a paused model's BET and AVOID into NONE. It now
returns the model's own verdict unchanged, and every row a paused model writes
carries downgrade_reason = config.PAUSED_NOTE ('model paused'). Being paused
means exactly: no Discord post, no push, not in the published record or its
ROI -- and, inside the scorer, no one-bet-per-player slot, no daily-cap unit and
no effect on the Kelly bankroll.

Every exclusion is keyed on the ROW's marker (config.paused_row_exclusion_sql /
the app's isPausedRow), never on the model's present pause state, which is the
record rule of CLAUDE.md 1c: filter on what the pick WAS.

What this pins:
  1. the real verdict (BET / AVOID / NONE) and stake are kept, with the note;
  2. a paused pick is re-decided at the best price exactly like a live one and
     keeps the note (_requalify_keeping_pause; _requalify_at_best unchanged);
  3. a paused BET takes no player slot and no cap unit, and is not downgraded;
  4. no Discord (new / locked / live / free-pick ledger), no push (new, live,
     dropped), no signal_delivery / capture alarms for a paused row;
  5. the published record (Discord recap, both public views, the threshold
     review, the app's record filter) excludes it -- behaviourally on the recap,
     where a settled paused BET is dropped and a live model's BET is kept;
  6. the view migration is registered, ordered, one statement, and no other
     owner's guard reverts it.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

import config
from models import scorer

ROOT = Path(__file__).resolve().parent.parent
MODEL = "mlb_moneyline"
PROP = "mlb_prop_pitcher_k"
IMPLIED = 0.55
NOTE = config.PAUSED_NOTE
EXCL = config.paused_row_exclusion_sql("p")


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _code(sql: str) -> str:
    return "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))


@pytest.fixture(autouse=True)
def _rules(monkeypatch):
    monkeypatch.setitem(config.MODEL_EDGE_THRESHOLDS, MODEL, 0.05)
    monkeypatch.setitem(config.MODEL_PROB_THRESHOLDS, MODEL, 0.55)
    monkeypatch.setitem(config.MODEL_EDGE_THRESHOLDS, PROP, 0.05)
    monkeypatch.setitem(config.MODEL_PROB_THRESHOLDS, PROP, 0.55)
    monkeypatch.setattr(scorer, "MODEL_EDGE_THRESHOLDS", config.MODEL_EDGE_THRESHOLDS)
    monkeypatch.setattr(scorer, "MODEL_PROB_THRESHOLDS", config.MODEL_PROB_THRESHOLDS)
    monkeypatch.setattr(scorer, "PAUSED_MODELS", set())
    monkeypatch.setattr(scorer, "_auto_paused_models", lambda: set())
    monkeypatch.setattr(scorer, "DECIDE_ON_CALIBRATED_PROB", False)
    monkeypatch.setattr(scorer, "REQUIRE_DK_PRICE", False)
    monkeypatch.setattr(scorer, "_blocked_by_min_odds", lambda mid, odds: False)
    monkeypatch.setattr(config, "GLOBAL_MIN_EV", 0.0)


def _pause(monkeypatch, *models):
    monkeypatch.setattr(scorer, "PAUSED_MODELS", set(models))


def _game(prob, dk_odds=-120.0):
    ip = scorer.american_to_implied_prob(dk_odds)
    return scorer._make_pick(
        game_id="G1", model_id=MODEL, sport="MLB", game_date="2026-09-28",
        pick_side="home", pick_label="x", model_prob=prob,
        dk_implied_prob=ip, edge=prob - ip, dk_odds=dk_odds,
        bankroll=10000.0, features={})


def _prop(prob):
    return scorer._make_prop_pick(
        game_id="G1", model_id=PROP, game_date="2026-09-28",
        player_name="Aaron Nola", pick_side="over", model_prob=prob,
        dk_implied_prob=IMPLIED, edge=prob - IMPLIED, dk_odds=-120.0,
        line=5.5, bankroll=10000.0, stat_label="Ks", player_id="P1")


# ── 1. the real verdict is kept ──────────────────────────────────────────────

@pytest.mark.parametrize("prob,verdict", [(0.72, "BET"), (0.40, "AVOID"), (0.57, "NONE")])
def test_a_paused_game_model_writes_the_same_verdict_and_stake_as_a_live_one(
        monkeypatch, prob, verdict):
    live = _game(prob)
    _pause(monkeypatch, MODEL)
    paused = _game(prob)
    assert live["signal_type"] == paused["signal_type"] == verdict
    assert paused["recommended_bet"] == live["recommended_bet"]
    assert paused["kelly_fraction"] == live["kelly_fraction"]
    assert live.get("downgrade_reason") is None
    assert paused["downgrade_reason"] == NOTE


@pytest.mark.parametrize("prob,verdict", [(0.72, "BET"), (0.40, "AVOID")])
def test_a_paused_prop_model_keeps_its_verdict_too(monkeypatch, prob, verdict):
    live = _prop(prob)
    _pause(monkeypatch, PROP)
    paused = _prop(prob)
    assert live["signal_type"] == paused["signal_type"] == verdict
    assert paused["recommended_bet"] == live["recommended_bet"]
    assert paused["downgrade_reason"] == NOTE


def test_paused_signal_returns_the_verdict_and_the_note(monkeypatch):
    _pause(monkeypatch, MODEL)
    for v in ("BET", "AVOID", "NONE"):
        assert scorer._paused_signal(MODEL, v) == (v, NOTE)
    assert scorer._paused_signal(PROP, "BET") == ("BET", None)


def test_the_marker_is_the_shared_constant():
    assert NOTE == "model paused"
    assert EXCL.strip() == "AND p.downgrade_reason IS DISTINCT FROM 'model paused'"
    body = _src("models/scorer.py").split("def _pause_note(")[1].split("\ndef ")[0]
    assert "config.PAUSED_NOTE" in body


# ── 2. re-decided at the best price like a live pick, note kept ─────────────

def _dk(prob=0.66, dk_odds=-150.0):
    ip = scorer.american_to_implied_prob(dk_odds)
    p = {"model_id": MODEL, "pick_label": "TEX ML", "model_probability": prob,
         "dk_implied_prob": round(ip, 4), "edge": round(prob - ip, 4),
         "dk_odds": dk_odds, "bankroll_at_pick": 1000.0,
         "signal_type": scorer._decide(MODEL, prob, ip, prob - ip, dk_odds, is_prop=False),
         "kelly_fraction": 0.0, "recommended_bet": 0.0,
         **scorer._decision_fields("draftkings", dk_odds, ip, prob - ip)}
    return p


def test_a_paused_pick_is_requalified_at_the_best_price_and_stays_paused(monkeypatch):
    monkeypatch.setitem(config.MODEL_EDGE_THRESHOLDS, MODEL, 0.07)
    monkeypatch.setitem(config.MODEL_PROB_THRESHOLDS, MODEL, 0.60)
    monkeypatch.setattr(scorer, "DECIDE_ON_BEST_PRICE", True)
    best = {"book": "fanduel", "odds": -120.0, "link": "fd"}
    live = scorer._requalify_keeping_pause(_dk(), dict(best), is_prop=False)
    paused_in = {**_dk(), "downgrade_reason": NOTE}
    paused = scorer._requalify_keeping_pause(paused_in, dict(best), is_prop=False)
    assert live["signal_type"] == paused["signal_type"] == "BET"
    for k in ("decision_book", "decision_odds", "decision_edge",
              "kelly_fraction", "recommended_bet"):
        assert paused[k] == live[k], k
    assert paused["downgrade_reason"] == NOTE
    assert live["downgrade_reason"] is None


def test_the_requalify_helper_itself_is_unchanged_and_both_callers_use_the_wrapper():
    src = _src("models/scorer.py")
    body = src.split("def _requalify_at_best(")[1].split("\ndef ")[0]
    assert 'declined = pick.get("downgrade_reason")' in body
    stamp = src.split("def _stamp_best_game_prices(")[1].split("\ndef ")[0]
    tag = src.split("def _tag_prop(")[1].split("\ndef ")[0]
    assert "_requalify_keeping_pause(p, best, is_prop=False)" in stamp
    assert "_requalify_keeping_pause(pick, best, is_prop=True)" in tag


# ── 3. no slot, no cap unit, never downgraded ────────────────────────────────

def _bet(model_id, player_id, prob, paused=False):
    return {"game_id": "G1", "model_id": model_id, "player_id": player_id,
            "model_probability": prob, "dk_odds": -110.0, "signal_type": "BET",
            "kelly_fraction": 0.02, "recommended_bet": 200.0,
            "pick_label": f"{player_id} {model_id}",
            "downgrade_reason": NOTE if paused else None}


def test_a_paused_bet_never_takes_a_live_models_player_slot(monkeypatch):
    monkeypatch.setattr(scorer, "_calibrated", lambda mid, p: p)
    pools = {"mlb_pitcher": ["mlb_prop_pitcher_k", "mlb_prop_pitcher_hits"]}
    picks = [_bet("mlb_prop_pitcher_k", "P1", 0.62),
             _bet("mlb_prop_pitcher_hits", "P1", 0.90, paused=True)]
    out = scorer.dedupe_player_props(picks, pools=pools)
    assert [p["signal_type"] for p in out] == ["BET", "BET"]
    assert out[0].get("downgrade_reason") is None
    assert out[1]["downgrade_reason"] == NOTE      # untouched, still marked


def test_a_paused_bet_spends_no_daily_cap_unit(monkeypatch):
    monkeypatch.setattr(scorer, "_calibrated", lambda mid, p: p)
    caps = {"mlb_prop_pitcher_k": 1}
    picks = [_bet("mlb_prop_pitcher_k", "P1", 0.90, paused=True),
             _bet("mlb_prop_pitcher_k", "P2", 0.62)]
    out = scorer.apply_prop_daily_cap(picks, {}, caps=caps)
    assert [p["signal_type"] for p in out] == ["BET", "BET"]
    assert out[0]["downgrade_reason"] == NOTE


class _Capture:
    """A connection that records what it was asked and returns nothing."""

    def __init__(self, one=None):
        self.calls: list[tuple[str, object]] = []
        self._one = one

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return self

    def fetchall(self):
        return []

    def fetchone(self):
        return self._one

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def test_todays_standing_bets_ignore_a_paused_row():
    conn = _Capture()
    scorer._prop_bets_today(conn, "2026-09-28")
    sql, params = conn.calls[0]
    assert "downgrade_reason IS DISTINCT FROM %s" in sql
    assert NOTE in params


def test_a_paused_settled_bet_never_moves_the_kelly_bankroll():
    conn = _Capture()
    scorer._get_current_bankroll(conn)
    sql, params = conn.calls[0]
    assert "downgrade_reason IS DISTINCT FROM %s" in sql and params == (NOTE,)


# ── 4. no Discord, no push, no false delivery alarms ─────────────────────────

def _sql_of(fn, *args):
    conn = _Capture()
    try:
        fn(conn, *args)
    except Exception:      # noqa: BLE001 - only the SQL it issued matters here
        pass
    return "\n".join(s for s, _ in conn.calls)


def test_discord_new_and_locked_signals_skip_a_paused_row():
    from tracking import discord_notifier as dn
    for fn in (dn._new_signals, dn._locked_signals):
        assert EXCL in _sql_of(fn, "2026-09-28"), fn.__name__


def test_the_stale_pause_probe_does_not_report_a_paused_row_as_hidden():
    body = _src("tracking/discord_notifier.py").split(
        "def _log_stale_pause_hiding_bets(")[1].split("\ndef ")[0]
    assert 'config.paused_row_exclusion_sql("p")' in body


def test_live_publishers_share_the_row_gate():
    from tracking.publish_filters import live_publishable_sql
    assert config.paused_row_exclusion_sql("p") in live_publishable_sql("p")
    assert config.paused_row_exclusion_sql("x") in live_publishable_sql("x")
    from tracking import discord_notifier as dn, push_notifier as pn
    assert EXCL in _sql_of(dn._new_live_signals, "2026-09-28")
    assert EXCL in _sql_of(pn._new_live_signals, "2026-09-28")


def test_push_new_bets_and_dropped_skip_a_paused_row():
    from tracking import push_notifier as pn
    assert EXCL in _sql_of(pn._new_bet_signals, "2026-09-28")
    assert EXCL in _sql_of(pn._dropped_signals, "2026-09-28")


def test_opening_signal_capture_skips_a_paused_row():
    """The ledger behind the Discord and X free picks, the dropped push and
    signal_delivery: one paused row captured here is published four ways."""
    src = _src("tracking/opening_signals.py")
    body = src.split("def capture_opening_signals(")[1].split("\ndef ")[0]
    assert body.count('{config.paused_row_exclusion_sql("p")}') == 2


def test_health_checks_do_not_expect_a_paused_row_to_be_delivered_or_captured():
    src = _src("tracking/system_health.py")
    body = src.split("def run_system_health(")[1].split("\ndef ")[0]
    assert '{config.paused_row_exclusion_sql("p")}' in body        # signal_delivery
    assert body.count("downgrade_reason IS DISTINCT FROM 'model paused'") == 2  # capture


def test_first_signal_repair_keeps_the_marker_on_a_restored_lane(monkeypatch):
    from tracking import first_signal_repair as fsr
    monkeypatch.setattr(config, "PAUSED_MODELS", {"m_paused"})
    assert fsr._restore_as_paused("m_live", {"downgrade_reason": NOTE})
    assert fsr._restore_as_paused("m_paused", None)
    assert not fsr._restore_as_paused("m_live", {"downgrade_reason": None})
    src = _src("tracking/first_signal_repair.py")
    assert 'vals["downgrade_reason"] = config.PAUSED_NOTE' in src


# ── 5. not in the published record ───────────────────────────────────────────

def test_the_recap_excludes_a_settled_paused_bet_and_keeps_a_live_models_bet():
    """Behavioural, on SQLite: the recap query itself over three settled BETs.
    `m_now_paused` was live when it bet and is paused today -- it STAYS
    (CLAUDE.md 1c); `m_paused_row` was written while paused -- it goes."""
    from tracking.discord_notifier import _SETTLED_SQL
    if sqlite3.sqlite_version_info < (3, 39):
        pytest.skip("IS DISTINCT FROM needs SQLite >= 3.39")
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE picks (sport, model_id, result, kelly_fraction,
                  dk_odds, clv_pct, is_live, game_date, signal_type,
                  downgrade_reason)""")
    rows = [
        ("MLB", "m_live", "WIN", 0.02, -110, None, 0, "2026-09-28", "BET", None),
        ("MLB", "m_now_paused", "LOSS", 0.02, -110, None, 0, "2026-09-28", "BET", None),
        ("MLB", "m_paused_row", "WIN", 0.02, 250, None, 0, "2026-09-28", "BET", NOTE),
        ("MLB", "m_capped", "WIN", 0.0, -110, None, 0, "2026-09-28", "NONE", "daily cap"),
    ]
    db.executemany("INSERT INTO picks VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    sql = _SETTLED_SQL.format(window="= ?").replace("%%", "%")
    got = sorted(r[1] for r in db.execute(sql, ("2026-09-28",)).fetchall())
    assert got == ["m_live", "m_now_paused"]


MIG = ROOT / "data" / "migrations" / "record_excludes_paused_rows_2026_09_28.sql"


def _bodies(path: Path) -> list[str]:
    return re.findall(r"EXECUTE \$v\$(.*?)\$v\$", _code(path.read_text(encoding="utf-8")), re.S)


def test_both_public_views_exclude_the_paused_row():
    bodies = _bodies(MIG)
    assert len(bodies) == 2
    for b in bodies:
        assert "AND p.downgrade_reason IS DISTINCT FROM 'model paused'" in b
        assert "model_action_thresholds" not in b and "t.paused" not in b
        assert "p.signal_type = 'BET'" in b and "'2026-09-01'" in b


def test_the_view_migration_is_registered_after_its_owners_and_is_one_statement():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS
    i = ACTIVE_MIGRATIONS.index(MIG.name)
    for owner in ("settled_record_survives_a_pause_2026_09_12.sql",
                  "track_record_clv_no_vig_2026_09_14.sql",
                  "live_record_start_views_2026_09_01.sql"):
        assert ACTIVE_MIGRATIONS.index(owner) < i, owner
    code = _code(MIG.read_text(encoding="utf-8"))
    assert code.count("$mig$") == 2 and code.split("$mig$")[-1].strip() == ";"


def test_no_earlier_owner_guard_reverts_the_new_definition():
    """The live-date lesson: an earlier migration whose guard reads the new
    view as "not applied" rewrites it every pass. Evaluate each owner's skip
    condition against the new view bodies."""
    record, daily = _bodies(MIG)
    # settled_record_survives: skips when no 'min_prob' and no 't.paused'.
    sr = _code((ROOT / "data/migrations/settled_record_survives_a_pause_2026_09_12.sql")
               .read_text(encoding="utf-8"))
    assert sr.count("position('min_prob' in d) = 0 AND position('t.paused' in d) = 0") == 2
    assert "position('paused' in d)" not in sr
    for b in (record, daily):
        assert "min_prob" not in b and "t.paused" not in b
        assert "2026-09-01" in b                       # live_record_start guard
        assert re.search(r"(p\.)?dk_odds IS NOT NULL", b)   # require_price guard
    assert "clv_method" in record                      # track_record_clv guard


def test_the_threshold_review_counts_only_published_signals():
    body = _src("tracking/threshold_review.py")
    assert "AND downgrade_reason IS DISTINCT FROM %s" in body
    assert "(EPOCH, config.PAUSED_NOTE)" in body


# ── the app agrees (source pins; tsc keeps the types honest) ────────────────

def test_the_app_filters_the_paused_row_out_of_signals_and_the_record():
    src = _src("mobile/src/lib/thresholds.ts")
    assert "export const PAUSED_NOTE = 'model paused';" in src
    action = src.split("export function passesActionFilter(")[1].split("\n}")[0]
    record = src.split("export function passesRecordFilter(")[1].split("\n}")[0]
    assert "if (isPausedRow(p)) return false;" in action
    assert "if (isPausedRow(p)) return false;" in record
    q = _src("mobile/src/lib/queries.ts")
    for const in ("const PICK_COLUMNS =", "const SETTLED_PICK_COLUMNS ="):
        block = q.split(const)[1].split(";")[0]
        assert "downgrade_reason" in block, const
    assert "const KEY = 'settledPicks.v7';" in _src("mobile/src/lib/settledPickCache.ts")


# ── post-#850 review: the leaks the first pass missed ────────────────────────

def _fn(src: str, sig: str) -> str:
    m = re.search(re.escape(sig) + r".*?\n\}\n", src, re.S)
    assert m, f"{sig} is missing"
    return m.group(0)


def test_the_team_and_player_pick_records_drop_the_paused_row_on_the_server():
    """Aaron Nola's page showed three paused 10/1 BETs, and ATL/PHI a paused
    Over 7.5: both record reads pulled settled BETs with no paused clause."""
    q = _src("mobile/src/lib/queries.ts")
    assert (
        "export const NOT_PAUSED_ROW = `downgrade_reason.is.null,downgrade_reason.neq.${PAUSED_NOTE}`;"
        in q
    ), "NULL must pass explicitly: neq alone drops every unmarked row"
    for sig in (
        "export async function fetchSettledGamePicksForGames(",
        "export async function fetchSettledPropPicksForPlayer(",
    ):
        body = _fn(q, sig)
        assert ".or(NOT_PAUSED_ROW)" in body, sig
        assert "isPausedRow(p)" in body, f"{sig}: belt and braces, filter the rows too"


def test_the_team_and_player_record_reductions_skip_the_paused_row():
    team = _fn(_src("mobile/src/lib/teamDetail.ts"), "export function teamPickRecords(")
    player = _fn(_src("mobile/src/lib/playerDetail.ts"), "export function playerPickRecord(")
    for name, body in (("teamPickRecords", team), ("playerPickRecord", player)):
        assert "if (isPausedRow(p)) continue;" in body, name


def test_every_settled_bet_read_carries_the_paused_clause():
    """Any server read pinned to settled BETs is a record read; it must say
    which rows are not bets. Reads that feed passesRecordFilter (all-signal
    reads) are not pinned to BET and are filtered on the client."""
    q = _src("mobile/src/lib/queries.ts")
    for m in re.finditer(r"export async function (\w+)\(.*?\n\}\n", q, re.S):
        body = m.group(0)
        if ".eq('signal_type', 'BET')" in body and ".in('result', ['WIN', 'LOSS', 'PUSH'])" in body:
            assert ".or(NOT_PAUSED_ROW)" in body, m.group(1)


def test_the_live_board_drops_the_paused_row():
    """The #850 guard the Live board missed: a BET written while its lane was
    paused stays not-a-signal after an unpause."""
    src = _src("mobile/src/screens/PicksHomeScreen.tsx")
    block = src.split("const liveInProgress = useMemo(")[1].split("[allLiveData, liveStates]")[0]
    assert "!isModelPaused(d.pick.model_id)" in block
    assert "!isPausedRow(d.pick)" in block
