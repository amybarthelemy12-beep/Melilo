"""Batch backfill: run the translator over every source key in govparti's R2,
producing pair records that go to BOTH R2 (immutable archive) and Neon (query
layer).

By default the sweep iterates both source buckets (`public` = govparti-archive,
`internal` = govparti-internal). Pass `--bucket public` or `--bucket internal`
to restrict.

Write order is R2 first, Neon second: if Neon is briefly down the archive still
has the work and the next run reconciles. The skip-if-exists check queries Neon
(faster than listing R2), so a stale Neon DB after an outage will cause some
re-archiving until reconciliation lands.

Per-doc exceptions are caught and logged; one bad PDF does not kill a sweep of
thousands of documents.

Usage:
    melilo-backfill --prefix cases/        --task pirac               --source-type case
    melilo-backfill --prefix statutes/     --task summary             --source-type statute
    melilo-backfill --prefix bills/        --task section_walkthrough --source-type bill --bucket internal
"""
from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime, timezone
from typing import Iterable

from melilo.config import SOURCE_BUCKETS, settings
from melilo.ingest.extract import extract
from melilo.ingest.r2_client import (
    fetch_source,
    list_source_keys,
    write_pairs_jsonl,
)
from melilo.store import bootstrap_schema, list_processed_origins, upsert_pairs
from melilo.translate.pipeline import translate_document, validate_task_source


TASKS = ("pirac", "brief", "summary", "section_walkthrough")
SOURCE_TYPES = ("case", "statute", "bill", "regulation", "declassified")


def _load_translator():
    """Load the translator model once. Kept identical to scripts/translate.py's
    loader so a single-doc run and a backfill run produce byte-identical pairs."""
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(settings.translator_model)
    model = AutoModelForCausalLM.from_pretrained(
        settings.translator_model, device_map="auto", torch_dtype="auto"
    )

    def _call(messages: list[dict]) -> str:
        prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tok(prompt, return_tensors="pt").to(model.device)
        out = model.generate(**inputs, max_new_tokens=2048, do_sample=False)
        return tok.decode(out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True).strip()

    return _call


def _archive_key(task: str, run_id: str, bucket_role: str, source_key: str) -> str:
    """R2 archive key, namespaced so the two source buckets never collide."""
    return f"pairs/{task}/{run_id}/{bucket_role}/{source_key}.jsonl"


def _sweep_one_bucket(
    *,
    bucket_role: str,
    prefix: str,
    task: str,
    source_type: str,
    run_id: str,
    translator,
    already: set[tuple[str, str]],
    counters: dict,
    limit: int | None,
) -> None:
    print(f"-- sweeping bucket={bucket_role} prefix={prefix!r}", file=sys.stderr)
    for source_key in list_source_keys(bucket_role=bucket_role, prefix=prefix):
        if (bucket_role, source_key) in already:
            counters["skipped"] += 1
            continue
        if limit is not None and counters["written"] + counters["failed"] >= limit:
            return
        counters["seen"] += 1
        try:
            doc = fetch_source(bucket_role=bucket_role, key=source_key)
            text = extract(doc.key, doc.body)
            records = list(
                translate_document(
                    text=text,
                    translator=translator,
                    task_type=task,
                    source_type=source_type,
                    source_bucket=bucket_role,
                    source_key=source_key,
                )
            )
            # 1. R2 archive (authoritative for replay). One PUT per source doc.
            write_pairs_jsonl(_archive_key(task, run_id, bucket_role, source_key), records)
            # 2. Neon insert (authoritative for queries). ON CONFLICT DO NOTHING.
            inserted = upsert_pairs(records)
            counters["written"] += 1
            counters["rows_inserted"] += inserted
            print(
                f"[{counters['seen']}] {bucket_role}/{source_key} -> "
                f"{len(records)} pairs ({inserted} new rows)",
                file=sys.stderr,
            )
        except Exception as exc:  # noqa: BLE001 — one bad doc shouldn't kill the sweep
            counters["failed"] += 1
            print(
                f"[{counters['seen']}] FAILED {bucket_role}/{source_key}: {exc}",
                file=sys.stderr,
            )
            traceback.print_exc(file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", required=True, help="R2 source-bucket prefix to sweep")
    parser.add_argument("--task", required=True, choices=TASKS)
    parser.add_argument("--source-type", required=True, choices=SOURCE_TYPES)
    parser.add_argument(
        "--bucket",
        default="both",
        choices=("both", *SOURCE_BUCKETS),
        help="Which source bucket(s) to sweep. Default: both.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Tag for this sweep's R2 archive keys. Defaults to a UTC timestamp.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after this many docs are processed (skipped docs don't count).",
    )
    args = parser.parse_args()

    validate_task_source(args.task, args.source_type)

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    buckets_to_sweep: Iterable[str] = (
        SOURCE_BUCKETS if args.bucket == "both" else (args.bucket,)
    )

    print("ensuring Neon schema is bootstrapped ...", file=sys.stderr)
    bootstrap_schema()

    print(f"snapshotting already-processed origins for task={args.task} ...", file=sys.stderr)
    already = list_processed_origins(task_type=args.task)
    print(f"  found {len(already)} already-processed (bucket, key) pairs", file=sys.stderr)

    print(f"loading translator: {settings.translator_model}", file=sys.stderr)
    translator = _load_translator()

    counters = {"seen": 0, "written": 0, "skipped": 0, "failed": 0, "rows_inserted": 0}
    for bucket_role in buckets_to_sweep:
        _sweep_one_bucket(
            bucket_role=bucket_role,
            prefix=args.prefix,
            task=args.task,
            source_type=args.source_type,
            run_id=run_id,
            translator=translator,
            already=already,
            counters=counters,
            limit=args.limit,
        )

    print(
        "done: "
        f"seen={counters['seen']} written={counters['written']} "
        f"skipped={counters['skipped']} failed={counters['failed']} "
        f"new_rows={counters['rows_inserted']}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
