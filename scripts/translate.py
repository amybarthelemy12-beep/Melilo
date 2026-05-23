"""Run the translator over a single R2 source key. Pair record goes to BOTH
R2 (immutable archive) and Neon (query layer), same as the batch backfill.

Backend is chosen by `MELILO_BACKEND` in .env (see scripts/backfill.py).

Usage:
    melilo-translate --bucket public --source-key cases/foo.pdf \
        --task pirac --source-type case
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from melilo.config import SOURCE_BUCKETS
from melilo.ingest.extract import extract
from melilo.ingest.r2_client import fetch_source, write_pairs_jsonl
from melilo.store import bootstrap_schema, upsert_pairs, validate_license
from melilo.translate.backends import load_translator
from melilo.translate.pipeline import translate_document


TASKS = ("pirac", "brief", "summary", "section_walkthrough")
SOURCE_TYPES = ("case", "statute", "bill", "regulation", "declassified")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bucket",
        required=True,
        choices=SOURCE_BUCKETS,
        help="Which source bucket the doc lives in: public or internal.",
    )
    parser.add_argument("--source-key", required=True, help="R2 key in the chosen source bucket")
    parser.add_argument(
        "--task",
        required=True,
        choices=TASKS,
        help=(
            "Output task. pirac/brief: cases only. summary: any source type. "
            "section_walkthrough: statutes, bills, regulations, declassified."
        ),
    )
    parser.add_argument("--source-type", required=True, choices=SOURCE_TYPES)
    parser.add_argument(
        "--out-key",
        default=None,
        help="R2 archive key. Defaults to pairs/<task>/<timestamp>/<bucket>/<source_key>.jsonl",
    )
    parser.add_argument(
        "--license",
        required=True,
        help="License of the source. PD/CC0/CC-BY-*. See melilo-licensing memory.",
    )
    parser.add_argument(
        "--attribution",
        default=None,
        help="Attribution string. REQUIRED when --license starts with CC-BY.",
    )
    parser.add_argument("--source-org", default=None, help="Upstream provider/org.")
    args = parser.parse_args()

    validate_license(args.license, args.attribution)
    bootstrap_schema()

    doc = fetch_source(bucket_role=args.bucket, key=args.source_key)
    text = extract(doc.key, doc.body)

    translator = load_translator()
    records = list(
        translate_document(
            text=text,
            translator=translator,
            task_type=args.task,
            source_type=args.source_type,
            source_bucket=args.bucket,
            source_key=args.source_key,
            license=args.license,
            attribution=args.attribution,
            source_org=args.source_org,
        )
    )

    archive_key = args.out_key or (
        f"pairs/{args.task}/"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}/"
        f"{args.bucket}/{args.source_key}.jsonl"
    )
    write_pairs_jsonl(archive_key, records)
    inserted = upsert_pairs(records)
    print(
        f"wrote {len(records)} {args.task} pairs to R2 ({archive_key}) "
        f"and Neon ({inserted} new rows)"
    )


if __name__ == "__main__":
    main()
