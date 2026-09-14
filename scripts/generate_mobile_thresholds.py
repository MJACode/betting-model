"""Generate mobile/src/lib/thresholds.generated.ts from config.py.

config.py is canonical (data.threshold_sync mirrors it to Supabase; the app
falls back to the bundled mirror on cold start). Hand-maintaining the TS
mirror drifted for months — measured 2026-09-11 in
tests/test_mobile_threshold_parity.py. Generation closes that class of bug.

Usage
-----
    python -m scripts.generate_mobile_thresholds           # write the file
    python -m scripts.generate_mobile_thresholds --check   # exit 1 on drift (CI)

The companion thresholds.ts re-exports these constants and keeps the runtime
helpers (passesActionFilter, thresholdFor, ...).
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402

OUT = ROOT / "mobile" / "src" / "lib" / "thresholds.generated.ts"


def _fmt(x: float) -> str:
    if isinstance(x, float) and x == int(x):
        return str(int(x))
    return f"{x:.10g}"


def render() -> str:
    lines: list[str] = [
        "/**",
        " * GENERATED FILE — do not edit by hand.",
        " * Source of truth: config.py (ACTION_THRESHOLDS, PAUSED_MODELS,",
        " * PROB_ONLY_MODELS, RETIRED_MODELS, KELLY_*).",
        " * Regenerate: python -m scripts.generate_mobile_thresholds",
        " * Check (CI):  python -m scripts.generate_mobile_thresholds --check",
        f" * Last generated: {date.today().isoformat()}",
        " */",
        "",
        "export interface ModelThreshold {",
        "  min_prob: number;",
        "  min_edge: number;",
        "  min_odds: number | null;",
        "}",
        "",
        "export const ACTION_THRESHOLDS: Record<string, ModelThreshold> = {",
    ]
    for mid in sorted(config.ACTION_THRESHOLDS):
        if mid in config.RETIRED_MODELS:
            continue
        cut = config.ACTION_THRESHOLDS[mid]
        floor = float(config.min_odds_for(mid))
        lines.append(
            f"  {mid}: {{ min_prob: {_fmt(cut['min_prob'])}, "
            f"min_edge: {_fmt(cut['min_edge'])}, "
            f"min_odds: {_fmt(floor)} }},"
        )
    lines.append("};")
    lines.append("")
    lines.append("export const PROB_ONLY_MODELS = new Set<string>([")
    for m in sorted(set(config.PROB_ONLY_MODELS) - set(config.RETIRED_MODELS)):
        lines.append(f"  '{m}',")
    lines.append("]);")
    lines.append("")
    lines.append("export const RETIRED_PROB_ONLY_MODELS = new Set<string>([")
    lines.append("  'mlb_prop_batter_hr',")
    lines.append("]);")
    lines.append("")
    lines.append("export const PAUSED_MODELS = new Set<string>([")
    for m in sorted(set(config.PAUSED_MODELS) - set(config.RETIRED_MODELS)):
        lines.append(f"  '{m}',")
    lines.append("]);")
    lines.append("")
    lines.append("export const RETIRED_MODELS = new Set<string>([")
    for m in sorted(config.RETIRED_MODELS):
        lines.append(f"  '{m}',")
    lines.append("]);")
    lines.append("")
    lines.append(f"export const KELLY_MULTIPLIER = {_fmt(float(config.KELLY_MULTIPLIER))};")
    lines.append(f"export const MAX_KELLY_FRACTION = {_fmt(float(config.MAX_KELLY_FRACTION))};")
    lines.append("")
    return "\n".join(lines)


def _strip_date(s: str) -> str:
    return "\n".join(
        ln for ln in s.splitlines() if not ln.startswith(" * Last generated:")
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the generated file would change",
    )
    args = ap.parse_args()
    body = render()
    if args.check:
        if not OUT.exists():
            print(f"MISSING {OUT.relative_to(ROOT)} — run without --check", file=sys.stderr)
            return 1
        current = OUT.read_text(encoding="utf-8")
        if _strip_date(current) != _strip_date(body):
            print(
                f"DRIFT: {OUT.relative_to(ROOT)} does not match config.py. "
                "Run: python -m scripts.generate_mobile_thresholds",
                file=sys.stderr,
            )
            return 1
        print(f"ok: {OUT.relative_to(ROOT)} matches config.py")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(body, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
