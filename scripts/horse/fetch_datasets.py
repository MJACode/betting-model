"""Download the public horse racing files named in scripts/horse/manifest.json.

Writes under data/horse/, which is gitignored. Does not write picks, does not
call The Odds API, and does not log into a sportsbook or an ADW.

    python -m scripts.horse.fetch_datasets --list
    python -m scripts.horse.fetch_datasets --only gdaley-hkracing
    python -m scripts.horse.fetch_datasets --all
    python -m scripts.horse.fetch_datasets --only deltaromeo-uk-ireland-1988-2026

--all skips the 1.12 GB UK/Ireland zip unless --include-large is set.
Equibase 2023 is manual: the command prints where it arrives and writes nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).resolve().parent / "manifest.json"
USER_AGENT = "betting-model-horse-fetch/1.0"
KAGGLE_DOWNLOAD = "https://www.kaggle.com/api/v1/datasets/download/{owner}/{slug}"


def load_manifest(path: Path | None = None) -> dict:
    return json.loads((path or MANIFEST).read_text(encoding="utf-8"))


def dest_root(manifest: dict, override: Path | None = None) -> Path:
    if override is not None:
        return override
    return ROOT / manifest["dest"]


def kaggle_url(owner: str, slug: str) -> str:
    return KAGGLE_DOWNLOAD.format(owner=owner, slug=slug)


def betfair_names(block: dict) -> list[str]:
    names = [f"ANZ_Thoroughbreds_{year}.zip" for year in block["annual_zip_years"]]
    names += [f"ANZ_Thoroughbreds_{ym}.csv" for ym in block["monthly_csv"]]
    return names


def iter_items(manifest: dict, only: set[str] | None, include_large: bool) -> list[dict]:
    """Downloadable items. Manual rows are never included.

    A large set is fetched when it is named with --only, or when --all is
    paired with --include-large. --all alone leaves it out.
    """
    items: list[dict] = []
    for row in manifest["kaggle"]:
        named = only is not None and row["id"] in only
        if only is not None and not named:
            continue
        if row.get("large") and not include_large and not named:
            continue
        items.append({
            "id": row["id"],
            "url": kaggle_url(row["owner"], row["slug"]),
            "filename": f"{row['slug']}.zip",
            "licence": row["licence"],
            "expected_bytes": row.get("zip_bytes"),
        })
    block = manifest["betfair_anz_thoroughbreds"]
    base = block["base"]
    for name in betfair_names(block):
        item_id = "betfair-" + name
        if only is not None and item_id not in only and "betfair-anz-thoroughbreds" not in only:
            continue
        items.append({
            "id": item_id,
            "url": base + name,
            "filename": name,
            "licence": block["licence"],
            "expected_bytes": None,
            "group": "betfair-anz-thoroughbreds",
        })
    return items


def manual_rows(manifest: dict, only: set[str] | None) -> list[dict]:
    rows = []
    for row in manifest["manual"]:
        if only is None or row["id"] in only:
            rows.append(row)
    return rows


def _download(url: str, dest: Path, timeout: int) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        n = 0
        with tmp.open("wb") as handle:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                handle.write(chunk)
                n += len(chunk)
    tmp.replace(dest)
    return n


def fetch_item(item: dict, root: Path, *, force: bool, timeout: int, unzip: bool) -> Path:
    folder = root / item["id"]
    dest = folder / item["filename"]
    if dest.exists() and dest.stat().st_size > 0 and not force:
        print(f"skip {item['id']} ({dest.stat().st_size} bytes already at {dest})")
        return dest
    print(f"get  {item['id']}  {item['url']}")
    n = _download(item["url"], dest, timeout)
    expected = item.get("expected_bytes")
    if expected is not None and n != expected:
        print(f"warn {item['id']} is {n} bytes; manifest recorded {expected} on the day it was measured")
    else:
        print(f"ok   {item['id']}  {n} bytes  {dest}")
    if unzip and dest.suffix == ".zip":
        with zipfile.ZipFile(dest) as archive:
            archive.extractall(folder)
        print(f"unzip {item['id']} -> {folder}")
    return dest


def print_manual(row: dict) -> None:
    print(f"manual {row['id']}")
    print(f"  licence: {row['licence']}")
    print(f"  register: {row['registration']}")
    print(f"  email: {row['email']}")
    print(f"  wait: {row['wait']}")
    print(f"  {row['note']}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--list", action="store_true", help="print dataset ids and exit")
    p.add_argument("--only", action="append", default=[], help="one id, or betfair-anz-thoroughbreds for that group. Repeatable.")
    p.add_argument("--all", action="store_true", help="every public file except the large UK/Ireland zip")
    p.add_argument("--include-large", action="store_true", help="with --all, also fetch the 1.12 GB UK/Ireland zip")
    p.add_argument("--unzip", action="store_true", help="extract a downloaded zip next to itself")
    p.add_argument("--force", action="store_true", help="download again even if the file is already there")
    p.add_argument("--out", type=Path, default=None, help="directory (default data/horse)")
    p.add_argument("--timeout", type=int, default=180)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = load_manifest()
    if args.list:
        for row in manifest["kaggle"]:
            mark = " large" if row.get("large") else ""
            print(f"{row['id']}{mark}  {row['licence']}")
        print("betfair-anz-thoroughbreds  " + str(len(betfair_names(manifest["betfair_anz_thoroughbreds"]))) + " files")
        for row in manifest["manual"]:
            print(f"{row['id']}  manual  {row['licence']}")
        return 0
    if not args.all and not args.only:
        build_parser().print_help()
        print("\nPass --only <id> or --all. --list shows the ids.", file=sys.stderr)
        return 2
    only = set(args.only) if args.only else None
    items = iter_items(manifest, only, include_large=args.include_large)
    if only is not None:
        known = {row["id"] for row in manifest["kaggle"]}
        known.add("betfair-anz-thoroughbreds")
        known.update("betfair-" + name for name in betfair_names(manifest["betfair_anz_thoroughbreds"]))
        known.update(row["id"] for row in manifest["manual"])
        missing = sorted(only - known)
        if missing:
            print("unknown id: " + ", ".join(missing), file=sys.stderr)
            return 2
    root = dest_root(manifest, args.out)
    for row in manual_rows(manifest, only):
        print_manual(row)
    if not items and not manual_rows(manifest, only):
        print("nothing selected", file=sys.stderr)
        return 2
    for item in items:
        fetch_item(item, root, force=args.force, timeout=args.timeout, unzip=args.unzip)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
