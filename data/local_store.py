"""
Local parquet cache for offline modelling work.

WHY THIS EXISTS. Every NFL-prop experiment — a threshold sweep, a new feature,
a re-fit — needs the same ~460k player rows, 277k snap rows and 337k prop-odds
rows. Pulling them from Supabase over the session pooler is minutes per run, and
in a sandbox that cannot reach Supabase at all it is a full commit → CI → poll
round trip. Cached to disk once, the same sweep runs in seconds.

SAFETY. The cache is OFF unless a caller explicitly calls `activate()`. Only
offline entry points do (the backtest, the trainer, the local CLI). The live
scorer and the daily pipeline never call it, so they can never read stale data —
and `data/local/` is gitignored, so a cache cannot reach the worker anyway.

CORRECTNESS. A partial cache is worse than none: silently training on two of
three seasons would look like a result. Every table records the seasons it
actually holds in `manifest.json`, and `read_table` returns None — falling back
to the DB — unless every requested season is covered.

Format is parquet when pyarrow is importable, else gzipped pickle. Both are
regenerable in one command, so the fallback costs nothing but disk.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:                                    # pyarrow is optional, not required
    import pyarrow  # noqa: F401
    _PARQUET = True
except Exception:                       # pragma: no cover - environment dependent
    _PARQUET = False

_DEFAULT_DIR = Path(__file__).resolve().parent / "local"
CACHE_DIR = Path(os.environ.get("BETTING_LOCAL_CACHE_DIR", _DEFAULT_DIR))
_MANIFEST = "manifest.json"

_active = False


def activate() -> bool:
    """Turn the cache on for this process. Offline entry points only."""
    global _active
    _active = True
    return available()


def active() -> bool:
    return _active


def available() -> bool:
    return CACHE_DIR.is_dir() and (CACHE_DIR / _MANIFEST).exists()


def _path(table: str) -> Path:
    return CACHE_DIR / f"{table}.{'parquet' if _PARQUET else 'pkl.gz'}"


def _manifest() -> dict:
    p = CACHE_DIR / _MANIFEST
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _write_manifest(m: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / _MANIFEST).write_text(json.dumps(m, indent=1, sort_keys=True))


def write_table(table: str, df: pd.DataFrame, seasons: list[int] | None) -> Path:
    """Persist `df` and record which seasons it covers."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _path(table)
    if _PARQUET:
        df.to_parquet(path, index=False, compression="zstd")
    else:
        df.to_pickle(path, compression="gzip")
    m = _manifest()
    m[table] = {
        "rows": int(len(df)),
        "seasons": sorted(int(s) for s in seasons) if seasons else None,
        "columns": list(df.columns),
        "bytes": path.stat().st_size,
        "pulled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "format": "parquet" if _PARQUET else "pickle",
    }
    _write_manifest(m)
    return path


def read_table(table: str, seasons: list[int] | None = None) -> pd.DataFrame | None:
    """
    The cached table, or None when the cache cannot honestly serve the request.

    None is returned — and the caller falls back to the DB — when the cache is
    off, the table was never pulled, or it does not cover every requested
    season. Returning a short frame instead would silently change a result.
    """
    if not _active or not available():
        return None
    entry = _manifest().get(table)
    path = _path(table)
    if not entry or not path.exists():
        return None
    if seasons:
        have = entry.get("seasons")
        missing = [s for s in seasons if have is None or int(s) not in have]
        if missing:
            return None
    df = pd.read_parquet(path) if _PARQUET else pd.read_pickle(path, compression="gzip")
    if seasons and "season" in df.columns:
        df = df[df["season"].astype("Int64").isin([int(s) for s in seasons])]
    return df.reset_index(drop=True)


def status() -> str:
    if not available():
        return f"no local cache at {CACHE_DIR} — run: python -m scripts.pull_local_cache"
    m = _manifest()
    lines = [f"local cache: {CACHE_DIR}  (format: {'parquet' if _PARQUET else 'pickle'})"]
    total = 0
    for t, e in sorted(m.items()):
        total += e.get("bytes", 0)
        sea = e.get("seasons")
        span = f"{min(sea)}-{max(sea)}" if sea else "all"
        lines.append(f"  {t:<24} {e['rows']:>9,} rows  {span:<10} "
                     f"{e.get('bytes', 0)/1e6:6.1f} MB  {e.get('pulled_at', '?')}")
    lines.append(f"  {'TOTAL':<24} {'':>9}       {'':<10} {total/1e6:6.1f} MB")
    return "\n".join(lines)
