#!/usr/bin/env python3
"""Ingest local CAP (Caselaw Access Project) volume zips into a clean text staging tree.

No R2 / GovParti API required. Reads CAP bulk you already have under raw_texts
(or any --root), extracts opinion text from volume zips where possible, and
writes plain .txt files under --out so melilo-backfill (or a later local pair
pass) can consume them.

Usage:
  # dry run / inventory
  python scripts/ingest_local_cap.py --root raw_texts/case-law-archive --dry-run

  # extract a single reporter
  python scripts/ingest_local_cap.py --root raw_texts/case-law-archive --reporter a2d --limit 50

  # extract everything under root (careful — large)
  python scripts/ingest_local_cap.py --root raw_texts/case-law-archive --out staging/cap_text

Notes:
  - CAP volume zips vary in internal layout. This script handles common patterns
    (xml/html/txt/json inside the zip). Unrecognized members are skipped with a log.
  - Output layout: {out}/{reporter}/{volume_id}.txt
  - Does NOT generate Melilo pairs. Stage text first, then run create_pairs or
    push staged text to R2 and use melilo-backfill.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import zipfile
from pathlib import Path


TEXT_SUFFIXES = {".xml", ".html", ".htm", ".txt", ".json"}
SKIP_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".sha256", ".csv", ".tar"}


def _safe_name(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", s)[:180]


def _extract_text_from_bytes(name: str, data: bytes) -> str | None:
    lower = name.lower()
    try:
        if lower.endswith(".json"):
            obj = json.loads(data.decode("utf-8", errors="replace"))
            # CAP-ish shapes
            if isinstance(obj, dict):
                for key in ("casebody", "text", "opinion_text", "body", "html", "xml"):
                    if key in obj and isinstance(obj[key], str) and len(obj[key]) > 80:
                        return obj[key]
                    if key in obj and isinstance(obj[key], dict):
                        # nested casebody.data / opinions
                        inner = obj[key]
                        if "data" in inner and isinstance(inner["data"], str):
                            return inner["data"]
                        if "opinions" in inner and isinstance(inner["opinions"], list):
                            parts = []
                            for op in inner["opinions"]:
                                if isinstance(op, dict) and "text" in op:
                                    parts.append(op["text"])
                            if parts:
                                return "\n\n".join(parts)
            return None
        # xml / html / txt
        text = data.decode("utf-8", errors="replace").strip()
        if len(text) < 80:
            return None
        return text
    except Exception:
        return None


def process_zip(zip_path: Path, out_dir: Path, dry_run: bool) -> int:
    """Extract usable text members from one CAP volume zip. Returns count written."""
    written = 0
    reporter = zip_path.parent.name
    volume_stem = zip_path.stem
    dest_dir = out_dir / _safe_name(reporter)
    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            members = [n for n in zf.namelist() if not n.endswith("/")]
            text_members = [
                n for n in members
                if Path(n).suffix.lower() in TEXT_SUFFIXES
                and Path(n).suffix.lower() not in SKIP_SUFFIXES
            ]
            if not text_members:
                # some CAP zips nest another archive or only have binary — skip loudly
                print(f"  SKIP (no text members): {zip_path}", file=sys.stderr)
                return 0

            chunks: list[str] = []
            for name in text_members:
                try:
                    data = zf.read(name)
                except Exception as exc:
                    print(f"  WARN read {name} in {zip_path.name}: {exc}", file=sys.stderr)
                    continue
                text = _extract_text_from_bytes(name, data)
                if text:
                    chunks.append(text)

            if not chunks:
                print(f"  SKIP (no extractable text): {zip_path}", file=sys.stderr)
                return 0

            combined = "\n\n-----\n\n".join(chunks)
            out_path = dest_dir / f"{_safe_name(volume_stem)}.txt"
            if dry_run:
                print(f"  WOULD WRITE {out_path} ({len(combined):,} chars from {len(chunks)} members)")
            else:
                out_path.write_text(combined, encoding="utf-8")
                print(f"  WROTE {out_path} ({len(combined):,} chars)")
            written = 1
    except zipfile.BadZipFile:
        print(f"  BAD ZIP: {zip_path}", file=sys.stderr)
    except Exception as exc:
        print(f"  FAIL {zip_path}: {exc}", file=sys.stderr)
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage CAP volume zips → plain text")
    ap.add_argument("--root", required=True, help="Path to CAP tree (e.g. raw_texts/case-law-archive)")
    ap.add_argument("--out", default="staging/cap_text", help="Output directory for .txt files")
    ap.add_argument("--reporter", default=None, help="Only process this reporter subfolder (e.g. a2d)")
    ap.add_argument("--limit", type=int, default=None, help="Max volume zips to process")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        print(f"ERROR: {root} is not a directory", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out)
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    # Collect volume zips. Common layout: root/caselaw/{reporter}/{n}.zip
    zips: list[Path] = []
    search_root = root
    if args.reporter:
        candidates = list(root.rglob(args.reporter))
        dirs = [p for p in candidates if p.is_dir()]
        if dirs:
            search_root = dirs[0]
        else:
            print(f"ERROR: reporter {args.reporter!r} not found under {root}", file=sys.stderr)
            sys.exit(1)

    for p in sorted(search_root.rglob("*.zip")):
        # skip giant non-volume archives if any
        if p.name.lower() in {"frs_downloads.zip", "grs-csv.zip"}:
            continue
        zips.append(p)
        if args.limit is not None and len(zips) >= args.limit:
            break

    print(f"Found {len(zips)} volume zips under {search_root}", file=sys.stderr)
    total = 0
    for zp in zips:
        total += process_zip(zp, out_dir, args.dry_run)

    print(f"Done. Staged {total} text files → {out_dir.resolve()}", file=sys.stderr)
    if not args.dry_run and total:
        print(
            "Next: point create_pairs / a local pair runner at this folder, "
            "or upload staging/cap_text to R2 and run melilo-backfill.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
