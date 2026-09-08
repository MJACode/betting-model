"""config.SCORING_METHODS — the map that stops a working model reading as broken.

WHY THIS EXISTS. The ops roster judged every model by its `model_registry` row:
no active row -> "NO ARTIFACT", in red, under a banner saying it cannot score.
Seven of the sixteen it accused were scoring perfectly well — five from a frozen
rule with no artifact anywhere, two from a LightGBM engine whose artifacts live
outside the registry on purpose. mike, 2026-09-07: "some models still say no
artifact when I want them to say rules based".

The map is only useful while it is COMPLETE, and the way it rots is silent: a
new lane lands in ACTION_THRESHOLDS, nobody classifies it, and it inherits the
"artifact" default and shows up red. So the coverage assertion below runs in
BOTH directions against the derivation, rather than against a copied list.
"""
import config

VALID = {"artifact", "rule", "engine"}


def _generic() -> set:
    """Models that DO go through the generic artifact scorer."""
    return set(config.MODELS) | set(config.PROP_MODELS)


def test_the_map_covers_exactly_the_non_generic_models():
    """Every model outside MODELS/PROP_MODELS is classified, and nothing else is.

    Both directions matter. Missing an entry means a working model reads as
    broken; a stale entry means a model that was folded back into the generic
    path still claims to be a rule.
    """
    non_generic = set(config.ACTION_THRESHOLDS) - _generic()
    assert set(config.SCORING_METHODS) == non_generic, (
        "config.SCORING_METHODS has drifted from "
        "set(ACTION_THRESHOLDS) - (set(MODELS) | set(PROP_MODELS)). "
        f"unclassified={sorted(non_generic - set(config.SCORING_METHODS))} "
        f"stale={sorted(set(config.SCORING_METHODS) - non_generic)}"
    )


def test_every_declared_method_is_one_of_the_three():
    bad = {m: v for m, v in config.SCORING_METHODS.items() if v not in VALID}
    assert not bad, f"unknown scoring methods: {bad} (allowed: {sorted(VALID)})"


def test_every_classified_model_carries_thresholds():
    """A scoring method for a model that cannot fire is a leftover."""
    unknown = set(config.SCORING_METHODS) - set(config.ACTION_THRESHOLDS)
    assert not unknown, f"not registered in ACTION_THRESHOLDS: {sorted(unknown)}"


def test_a_generic_model_is_never_declared_rule_or_engine():
    """The generic scorer LOADS an artifact, so those two labels would be lies."""
    lying = sorted(m for m, v in config.SCORING_METHODS.items()
                   if v != config.SCORING_ARTIFACT and m in _generic())
    assert not lying, (
        f"{lying} score through the generic artifact path but are declared "
        "rule/engine — a missing registry row for them IS a fault"
    )


def test_accessor_defaults_to_artifact():
    """The default has to be the strict one: unknown means 'a row is expected'."""
    assert config.scoring_method("no_such_model_id") == config.SCORING_ARTIFACT
    assert config.scoring_method("mlb_moneyline") == config.SCORING_ARTIFACT
    assert config.scoring_method("nfl_wind_totals") == "rule"
    assert config.scoring_method("ncaaf_live_total") == "engine"


def test_mlb_live_total_runs_is_artifact_backed():
    """It is the one non-generic model that DOES carry a registry artifact.

    models/live_scorer.py calls load_model(model_id) for it, and
    models/saved/mlb_live_total_runs_*.pkl is committed. Labelling it "rule"
    because it sits outside MODELS would hide a real outage.
    """
    assert config.SCORING_METHODS["mlb_live_total_runs"] == config.SCORING_ARTIFACT


def test_rule_based_models_never_appear_in_a_feature_map():
    """A "rule" model must not go anywhere near the artifact scorer.

    Pinned because this rots in the other direction too: if one of these ever
    gained a feature-map entry it would start being scored generically while
    the roster still called it a rule. Every engine's map is swept rather than
    one named map, so a new engine cannot open a hole.
    """
    import importlib

    modules = (
        ("features.feature_engine",            "FEATURE_MAP"),
        ("features.live_game_features",        "LIVE_FEATURE_MAP"),
        ("features.prop_feature_engine",       "PROP_FEATURE_MAP"),
        ("features.nba_prop_feature_engine",   "NBA_PROP_FEATURE_MAP"),
        ("features.nfl_prop_feature_engine",   "NFL_PROP_FEATURE_MAP"),
        ("features.wnba_prop_feature_engine",  "WNBA_PROP_FEATURE_MAP"),
    )
    mapped, seen = set(), 0
    for mod_name, attr in modules:
        try:
            mod = importlib.import_module(mod_name)
        except Exception:                                   # noqa: BLE001
            continue                                        # optional dep missing
        m = getattr(mod, attr, None)
        if isinstance(m, dict):
            mapped |= set(m)
            seen += 1
    assert seen, "no feature map could be imported — this guard checked nothing"

    rules = {m for m, v in config.SCORING_METHODS.items() if v == "rule"}
    assert not (rules & mapped), (
        f"{sorted(rules & mapped)} are declared rule-based but carry a "
        "feature-map entry, which is the generic artifact path"
    )
