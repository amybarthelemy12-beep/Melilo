#!/usr/bin/env python3
"""
Inventory raw_texts/ by inferred document type, down to individual files.
Run from Melilo root (or pass --root).

Usage:
  python scripts/inventory_raw_texts.py
  python scripts/inventory_raw_texts.py --root /path/to/raw_texts --json inventory.json
  python scripts/inventory_raw_texts.py --csv inventory.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from pathlib import Path

# Map path segments / filename patterns → canonical source_type
# (aligned with Melilo's source_type values: case, statute, bill, regulation, declassified)
TYPE_RULES = [
    # path-based (higher priority)
    (("caselaw", "case", "opinion", "court"), "case"),
    (("statute", "usc", "code", "public-law", "pl"), "statute"),
    (("bill", "legislation", "legiscan", "congress"), "bill"),
    (("regulation", "cfr", "federal-register", "fr", "rule"), "regulation"),
    (("declassified", "foia", "nsarchive", "cia", "state-dept"), "declassified"),
]


def infer_type(rel_path: str) -> str:
    p = rel_path.lower().replace("\\", "/")
    for keywords, stype in TYPE_RULES:
        if stype and any(k in p for k in keywords):
            return stype
    # filename-only fallbacks
    name = Path(rel_path).name.lower()
    if any(x in name for x in ("opinion", "v.", "vs.", "court", "case")):
        return "case"
    if any(x in name for x in ("usc", "statute", "public_law", "pl_")):
        return "statute"
    if any(x in name for x in ("bill", "hr_", "s_", "legis")):
        return "bill"
    if any(x in name for x in ("cfr", "fr-", "federal_register")):
        return "regulation"
    if any(x in name for x in ("foia", "declass", "nsarchive")):
        return "declassified"
    return "unknown"


def inventory(root: Path):
    by_type: dict[str, list[dict]] = defaultdict(list)
    total_bytes = 0
    file_count = 0

    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.startswith("."):
                continue
            full = Path(dirpath) / fn
            try:
                size = full.stat().st_size
            except OSError:
                continue
            rel = str(full.relative_to(root))
            stype = infer_type(rel)
            by_type[stype].append({
                "path": rel,
                "size_bytes": size,
                "ext": full.suffix.lower() or "(none)",
            })
            total_bytes += size
            file_count += 1

    return by_type, file_count, total_bytes


def main():
    ap = argparse.ArgumentParser(description="Inventory raw_texts by doc type")
    ap.add_argument("--root", default="raw_texts", help="Path to raw_texts folder")
    ap.add_argument("--json", help="Write full inventory to this JSON file")
    ap.add_argument("--csv", help="Write flat CSV of every file")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        print(f"ERROR: {root} does not exist or is not a directory")
        print("Create it and drop .txt/.pdf/.html files (or subfolders) then re-run.")
        return

    by_type, file_count, total_bytes = inventory(root)

    print("=" * 60)
    print(f"RAW_TEXTS INVENTORY  →  {root.resolve()}")
    print(f"Total files: {file_count}   |   Total size: {total_bytes/1_048_576:.2f} MB")
    print("=" * 60)

    for stype in sorted(by_type.keys()):
        files = sorted(by_type[stype], key=lambda x: x["path"])
        size = sum(f["size_bytes"] for f in files)
        print(f"\n## {stype.upper()}  ({len(files)} files, {size/1_048_576:.2f} MB)")
        for f in files:
            print(f"  {f['path']:<70} {f['size_bytes']:>10,}  {f['ext']}")

    # Optional outputs
    if args.json:
        out = {
            "root": str(root.resolve()),
            "total_files": file_count,
            "total_bytes": total_bytes,
            "by_type": {k: v for k, v in by_type.items()},
        }
        Path(args.json).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"\nWrote JSON → {args.json}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["source_type", "path", "size_bytes", "ext"])
            w.writeheader()
            for stype, files in by_type.items():
                for f in files:
                    w.writerow({"source_type": stype, **f})
        print(f"Wrote CSV  → {args.csv}")

    print("\n--- paste the summary above (or the JSON/CSV) back to me ---")


if __name__ == "__main__":
    main()
