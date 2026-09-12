"""The app's bundled thresholds are a MIRROR of config.py, and must equal it.

`mobile/src/lib/thresholds.ts` carries `ACTION_THRESHOLDS`, `PAUSED_MODELS` and
the price floors as the app's OFFLINE / FIRST-LAUNCH fallback: `thresholdFor`
and `isModelPaused` consult the server store per model id and fall through to
these constants whenever that store has not been fetched yet, or has no row for
that id. So every cold start renders its first board from this file.

NOTHING PINNED IT. `tests/test_retired_models.py` pins the RETIRED_MODELS half
and stops there, so `ACTION_THRESHOLDS` and `PAUSED_MODELS` drifted for as long
as anyone had been changing cuts -- measured 2026-09-11, on master at 8fe58f26:

  * 1 scorable model absent from the app outright (`nfl_live_prop`, LIVE since
    2026-09-05 and announcing on Discord since #629),
  * 16 models PAUSED in the app while live in config (the twelve NFL props, two
    MLB pitcher props, two WNBA props) -- picks the app hides pre-fetch,
  * 3 models LIVE in the app while PAUSED in config (`mlb_prop_batter_hits`,
    `mlb_runline`, `ufc_total_rounds`) -- the dangerous direction: a stakeable
    BET card for a model the platform has withdrawn,
  * 24 threshold value mismatches, several of them large (`mlb_f5_moneyline`
    0.58/0.02 in config against 0.67/0.07 in the app).

That is CLAUDE.md §1b's parity rule -- "the app, Discord and push show the same
picks, they are identical" -- failing on the one surface whose disagreement
nobody can see, because it only shows before the fetch lands.

This file is the tripwire. A cut changed in `config.py` now fails here until the
mirror is changed with it. It deliberately does NOT generate the TS: that file's
value comments carry the evidence for each cut ("2026-06-28 full-outcome: 77
bets +8.3% (UNPAUSED)"), and a generator would strip the reasoning to keep the
number.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import config

ROOT = Path(__file__).resolve().parents[1]
MIRROR = ROOT / "mobile" / "src" / "lib" / "thresholds.ts"


def _src() -> str:
    # encoding is explicit: this repo runs on Windows, where read_text() with no
    # encoding uses cp1252 and dies on the box-drawing characters in our source
    # at COLLECTION time, taking the whole suite with it (CLAUDE.md §7).
    return MIRROR.read_text(encoding="utf-8")


def _block(src: str, opener: str, closer: str) -> str:
    start = src.index(opener)
    return src[start : src.index(closer, start)]


def _canonical() -> dict[str, dict[str, float]]:
    """config.py's cuts, with the price floor folded in as the app stores it."""
    out: dict[str, dict[str, float]] = {}
    for model_id, cut in config.ACTION_THRESHOLDS.items():
        if model_id in config.RETIRED_MODELS:
            continue
        out[model_id] = {
            "min_prob": float(cut["min_prob"]),
            "min_edge": float(cut["min_edge"]),
            # min_odds_for(), NOT MODEL_MIN_ODDS.get(): every model resolves to a
            # floor -- its own, or DEFAULT_MIN_ODDS (-200) -- and that resolved
            # value is what data/threshold_sync writes into
            # model_action_thresholds, so it is what the mirror has to carry. A
            # first pass at this sync mirrored only the EXPLICIT entries, which
            # left 40 models with no floor at all offline: not a conservative
            # default, but every juicier price let through.
            "min_odds": float(config.min_odds_for(model_id)),
        }
    return out


def _mirror() -> dict[str, dict[str, float]]:
    block = _block(
        _src(),
        "export const ACTION_THRESHOLDS: Record<string, ModelThreshold> = {",
        "\n};",
    )
    out: dict[str, dict[str, float]] = {}
    for m in re.finditer(r"^  ([a-z0-9_]+):\s*\{([^}]*)\}", block, re.M):
        out[m.group(1)] = {
            k: float(v)
            for k, v in re.findall(r"(min_prob|min_edge|min_odds):\s*(-?[\d.]+)", m.group(2))
        }
    assert out, "no threshold rows parsed out of the app mirror"
    return out


def _mirror_paused() -> set[str]:
    """Only ids quoted on a line of their own.

    A bare `'([a-z0-9_]+)'` over this block also matches model names written in
    the COMMENTS above each group -- which is how a first pass at this
    measurement reported `mlb_prop_batter_hits` as live in the app when it is
    commented about, not listed. A regex that reads prose as data produces a
    finding that is not there.
    """
    block = _block(_src(), "export const PAUSED_MODELS = new Set<string>([", "\n]);")
    return set(re.findall(r"^\s*'([a-z0-9_]+)',", block, re.M))


def test_every_scorable_model_is_in_the_app_mirror():
    """A model absent here has NO cut at all before the fetch: `thresholdFor`
    returns null, and `passesActionFilter` refuses it -- so its BETs are
    invisible on a cold start while Discord announces them."""
    missing = sorted(set(_canonical()) - set(_mirror()))
    assert not missing, (
        f"scorable in config.py but absent from {MIRROR.name}, so the app has no "
        f"offline cut for them: {missing}"
    )


def test_the_app_mirror_holds_no_model_config_cannot_score():
    extra = sorted(set(_mirror()) - set(_canonical()) - set(config.RETIRED_MODELS))
    assert not extra, f"in {MIRROR.name} but not scorable in config.py: {extra}"


def test_every_cut_matches_config():
    canon, mirror = _canonical(), _mirror()
    wrong = {
        mid: {"config": canon[mid], "app": mirror[mid]}
        for mid in sorted(set(canon) & set(mirror))
        if canon[mid] != mirror[mid]
    }
    assert not wrong, (
        "the app would apply a different cut from config.py before the server "
        f"store is fetched:\n"
        + "\n".join(f"  {k}: config={v['config']} app={v['app']}" for k, v in wrong.items())
    )


def test_the_paused_set_matches_config():
    """Both directions, and the second is the one that shows a withdrawn bet.

    Paused-in-app-only hides a live model's picks until the fetch lands.
    Live-in-app-only draws a stakeable BET card for a model the platform has
    paused -- the same shape as the retired-model bug of 2026-09-02.
    """
    canon = set(config.PAUSED_MODELS) - set(config.RETIRED_MODELS)
    app = _mirror_paused() - set(config.RETIRED_MODELS)
    hidden = sorted(app - canon)
    shown = sorted(canon - app)
    assert not hidden and not shown, (
        f"paused in the app but live in config (app hides real picks): {hidden}\n"
        f"live in the app but paused in config (app shows a withdrawn bet): {shown}"
    )


def test_the_price_floors_match_config():
    """Every model carries a resolved floor, and a missing one is not a
    conservative default -- it lets every juicier price through.

    `min_odds_for` falls back to DEFAULT_MIN_ODDS (-200), so the floor is never
    absent server-side even though MODEL_MIN_ODDS only names the exceptions.
    The mirror's field is optional, so an omission here is silent."""
    floors = {
        mid: float(config.min_odds_for(mid))
        for mid in config.ACTION_THRESHOLDS
        if mid not in config.RETIRED_MODELS
    }
    mirror = _mirror()
    wrong = {
        mid: (floor, mirror[mid].get("min_odds"))
        for mid, floor in sorted(floors.items())
        if mid in mirror and mirror[mid].get("min_odds") != floor
    }
    assert not wrong, (
        "price floor differs between config.MODEL_MIN_ODDS and the app mirror "
        f"(config, app): {wrong}"
    )


def test_the_prob_only_set_matches_config():
    """The remaining field of ResolvedThreshold, and it is load-bearing.

    A prob-only model SKIPS the min_edge check entirely (`passesActionFilter`)
    and takes a different branch of the Sharp Score, so a drifted entry changes
    whether a pick is actionable at all. The two sets agree today -- this closes
    the guard gap before they do not, and stops this file's own header from
    claiming more than it pins (UX review, 2026-09-11).
    """
    block = _block(_src(), "export const PROB_ONLY_MODELS = new Set<string>([", "\n]);")
    app = set(re.findall(r"^\s*'([a-z0-9_]+)',", block, re.M))
    canon = set(config.PROB_ONLY_MODELS) - set(config.RETIRED_MODELS)
    retired_app = set(
        re.findall(
            r"^\s*'([a-z0-9_]+)',",
            _block(_src(), "export const RETIRED_PROB_ONLY_MODELS = new Set<string>([", "]);"),
            re.M,
        )
    )
    assert (app - retired_app) == canon, (
        f"prob-only drift -- app: {sorted(app - retired_app)}, config: {sorted(canon)}"
    )


# ── the UNLICENSED set (2026-09-12) ──────────────────────────────────────────

def _app_set(name: str) -> set[str]:
    block = _block(_src(), f"export const {name} = new Set<string>([", "\n]);")
    return {m.group(1) for m in re.finditer(r"'([a-z0-9_]+)'", block)}


def test_the_unlicensed_set_matches_the_engine_licence_flags():
    """A model that cannot bet must not render as live.

    `ncaaf_live_spread` is deliberately NOT in config.PAUSED_MODELS -- it is
    dark because its calibration gate failed, which the engine expresses with
    `serve.SPREAD_LICENSED`. Nothing server-side carries that state
    (`threshold_sync` writes `paused` from PAUSED_MODELS only), so the app
    keeps its own set and this test is the only thing stopping the two
    drifting. Drift is silent and one-directional in the bad way: the Models
    tab would list a model as live and tell members to check back for picks it
    can never post.
    """
    import ncaaf_live.serve as serve

    app = _app_set("UNLICENSED_MODELS")
    engine_dark = set()
    if not serve.SPREAD_LICENSED:
        engine_dark.add("ncaaf_live_spread")
    assert app == engine_dark, (
        "the app's UNLICENSED_MODELS and the engine's licence flags disagree: "
        f"app={sorted(app)} engine_dark={sorted(engine_dark)}"
    )


def test_an_unlicensed_model_is_not_also_paused():
    """The two states have different copy for a reason -- a paused model has a
    record to show, an unlicensed one has never bet. Both at once would render
    contradictory sentences."""
    import config

    for mid in _app_set("UNLICENSED_MODELS"):
        assert mid not in config.PAUSED_MODELS, (
            f"{mid} is both unlicensed and paused; pick one"
        )
        assert mid not in _app_set("PAUSED_MODELS"), (
            f"{mid} is in both app sets; pick one"
        )


def test_an_unlicensed_model_still_carries_a_cut_and_a_label():
    """So the day it is licensed, no app build is needed to show it."""
    import config

    for mid in _app_set("UNLICENSED_MODELS"):
        assert mid in config.ACTION_THRESHOLDS, f"{mid} has no cut in config"
        assert f"  {mid}: {{ min_prob" in _src(), f"{mid} has no cut in the app"
