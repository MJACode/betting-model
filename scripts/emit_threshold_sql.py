"""Emit the per-model action-threshold SQL filter straight from config.py.

CLAUDE.md used to carry three hand-maintained copies of this WHERE clause, and
they drifted — by 2026-08-30 the pasted blocks listed ~50 models while
``config.ACTION_THRESHOLDS`` held 70, so every NFL prop was missing from the
"canonical" SQL. config.py is the source of truth (the scorer reads it directly
and ``data.threshold_sync`` mirrors it into ``model_action_thresholds``), so the
SQL should be generated from it rather than transcribed.

Usage
-----
    python -m scripts.emit_threshold_sql              # bare column names
    python -m scripts.emit_threshold_sql --prefix p.  # for the Claude-mobile join
    python -m scripts.emit_threshold_sql --paused     # also list paused models

Paste the output into the Claude-mobile project instructions whenever a
threshold changes (see docs/mobile_picks_prompt.md).
"""
from __future__ import annotations

import argparse

import config


def emit(prefix: str = "", include_paused_comments: bool = True,
         include_live: bool = False) -> str:
    """Return the ``(model = ... AND prob >= ... AND edge >= ...)`` OR-block.

    Live (in-play) models are omitted by default: every pre-game board filters
    ``is_live IS NOT TRUE`` separately, and the hand-written block this replaces
    never listed them. Pass ``include_live=True`` for a live-board query.
    """
    lines: list[str] = []
    models = [m for m in sorted(config.ACTION_THRESHOLDS)
              if include_live or m not in config.LIVE_MODELS]
    width = max(len(m) for m in models) + 2
    for model_id in models:
        cut = config.ACTION_THRESHOLDS[model_id]
        quoted = f"'{model_id}'".ljust(width)
        if model_id in config.PAUSED_MODELS:
            if include_paused_comments:
                lines.append(f"-- {model_id} PAUSED (cut kept {cut['min_prob']}/{cut['min_edge']})")
            continue
        clause = f"({prefix}model_id = {quoted} AND {prefix}model_probability >= {cut['min_prob']}"
        # Prob-only models ignore edge entirely (config.PROB_ONLY_MODELS).
        if model_id not in config.PROB_ONLY_MODELS:
            clause += f" AND {prefix}edge >= {cut['min_edge']}"
        floor = config.MODEL_MIN_ODDS.get(model_id)
        if floor is not None:
            clause += f" AND ({prefix}dk_odds IS NULL OR {prefix}dk_odds >= {floor})"
        clause += ")"
        lines.append(clause)

    out: list[str] = []
    first = True
    for line in lines:
        if line.startswith("--"):
            out.append(f"    {line}")
            continue
        out.append(("    " if first else "    OR ") + line)
        first = False
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prefix", default="", help="column prefix, e.g. 'p.' for a joined query")
    ap.add_argument("--paused", action="store_true", help="print the paused-model list too")
    ap.add_argument("--live", action="store_true", help="include live (in-play) models")
    args = ap.parse_args()

    print("  AND (")
    print(emit(args.prefix, include_live=args.live))
    print("  )")
    if args.paused:
        print()
        print(f"-- paused ({len(config.PAUSED_MODELS)}): " + ", ".join(sorted(config.PAUSED_MODELS)))


if __name__ == "__main__":
    main()
