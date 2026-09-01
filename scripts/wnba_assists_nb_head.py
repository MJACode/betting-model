"""
wnba_assists_nb_head.py — stamp a negative-binomial dispersion head onto the
active wnba_prop_player_assists artifact.

Basis (2026-08-31 all-props sweep, scripts/wnba_prop_sweep.py): assists is the
one WNBA prop with a real plateau on leak-free 2026 lines, and the NB head's
plateau centre (0.54 prob / 0.02 edge → 290 bets, 54.1% vs 52.7% breakeven,
+3.39%, 8/8 neighbours positive, June/August both positive) is the shipped cut.
r = 13.56 was measured on 2025 residuals — genuine OOS for this model (trained
2019-2024) — via models.trainer._nb_dispersion. The scorer reads nb_r through
_nfl_prop_probs, routed for WNBA props in the same change.

No retrain: the fitted means are untouched; only the distribution that turns a
mean into P(over) changes. Poisson (var = mean) overstates both tails on a
count whose true var/mean runs 2-3x, which is precisely the high-conviction
tail where the old 0.69 cut graded -21% on the season.

Usage (no DB needed — reads/writes the pkl; prints the registry SQL to apply):
    python -m scripts.wnba_assists_nb_head
"""

import pickle
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MODELS_DIR  # noqa: E402

MODEL_ID   = "wnba_prop_player_assists"
SOURCE_PKL = Path(MODELS_DIR) / f"{MODEL_ID}_20260531_125558.pkl"
NB_R       = 13.56          # 2025 OOS, models.trainer._nb_dispersion


def main() -> None:
    with open(SOURCE_PKL, "rb") as f:
        artifact = pickle.load(f)
    assert artifact["model_id"] == MODEL_ID

    version = datetime.now().strftime("%Y%m%d_%H%M%S")
    artifact["version"] = version
    artifact["nb_r"] = NB_R
    artifact.setdefault("notes", "")
    artifact["notes"] = (
        "NB head stamped 2026-08-31 (r=13.56, 2025 OOS residuals) on the "
        "20260531_125558 fit; means unchanged. Cut moved 0.69/0.08 -> 0.54/0.02 "
        "from the leak-free 2026 plateau (290 bets +3.39%, 8/8)."
    )

    out = Path(MODELS_DIR) / f"{MODEL_ID}_{version}.pkl"
    with open(out, "wb") as f:
        pickle.dump(artifact, f)
    print(f"wrote {out.name}  (nb_r={NB_R})")
    print("\n-- apply to model_registry:")
    print(f"""UPDATE model_registry SET is_active = 0 WHERE model_id = '{MODEL_ID}';
INSERT INTO model_registry (model_id, version, trained_on, train_seasons,
                            holdout_season, is_active, model_path, notes)
VALUES ('{MODEL_ID}', '{version}', '2026-08-31',
        '[2019, 2020, 2021, 2022, 2023, 2024]', 2025, 1,
        'models/saved/{MODEL_ID}_{version}.pkl',
        'NB head (r=13.56, 2025 OOS) on the 20260531 fit; cut 0.54/0.02 from the leak-free 2026 plateau');""")


if __name__ == "__main__":
    main()
