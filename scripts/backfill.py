"""Batch backfill: run the translator over every source key in govparti's R2,
producing pair records that go to BOTH R2 (immutable archive) and Neon (query
layer).

By default the sweep iterates both source buckets (`public` = govparti-archive,
`internal` = govparti-internal). Pass `--bucket public` or `--bucket internal`
to restrict.

The translator backend is chosen by `MELILO_BACKEND` in .env (default `hf` for
in-process HF transformers; set to `openai` for any OpenAI-compatible HTTP API
like local Ollama, Parasail, OpenRouter, or a vLLM server).

When the backend is HTTP-based (`openai`), requests are submitted concurrently
via a thread pool of size `MELILO_BACKEND_CONCURRENCY` (default 4). The HF
backend stays sequential since it's already saturating one GPU.

Write order is R2 first, Neon second: if Neon is briefly down the archive still
has the work and the next run reconciles. The skip-if-exists check queries Neon
(faster than listing R2).

Per-doc exceptions are caught and logged; one bad PDF does not kill a sweep of
thousands of documents.

Usage:
    melilo-backfill --prefix federal/caselaw/ --task pirac   --source-type case
    melilo-backfill --prefix statutes/        --task summary --source-type statute
    melilo-backfill --prefix bills/           --task section_walkthrough --source-type bill --bucket internal
"""
from __future__ import annotations

import argparse
import fnmatch
import sys
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Iterable


# Default skip patterns — sidecar metadata files that show up alongside the
# real content in govparti's R2 layout. Feeding these to OLMo wastes tokens.
DEFAULT_EXCLUDE_GLOBS = ("*.meta.json", "*.metadata.json", "*.sidecar.json")

from melilo.config import SOURCE_BUCKETS, settings
from melilo.ingest.extract import extract
from melilo.ingest.r2_client import (
    fetch_source,
    list_source_keys,
    write_pairs_jsonl,
)
from melilo.store import (
    bootstrap_schema,
    list_processed_origins,
    upsert_pairs,
    validate_license,
)
from melilo.translate.backends import load_translator
from melilo.translate.pipeline import translate_document, validate_task_source


TASKS = ("pirac", "brief", "summary", "section_walkthrough")
SOURCE_TYPES = ("case", "statute", "bill", "regulation", "declassified")


def _archive_key(task: str, run_id: str, bucket_role: str, source_key: str) -> str:
    return f"pairs/{task}/{run_id}/{bucket_role}/{source_key}.jsonl"


def _process_one(
    *,
    bucket_role: str,
    source_key: str,
    task: str,
    source_type: str,
    run_id: str,
    translator,
    license: str,
    attribution: str | None,
    source_org: str | None,
) -> tuple[str, str, int, int]:
    """Returns (bucket_role, source_key, n_records, n_inserted). Raises on failure
    so the caller can count failures."""
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
            license=license,
            attribution=attribution,
            source_org=source_org,
        )
    )
    # 1. R2 archive (authoritative for replay).
    write_pairs_jsonl(_archive_key(task, run_id, bucket_role, source_key), records)
    # 2. Neon insert (authoritative for queries).
    inserted = upsert_pairs(records)
    return bucket_role, source_key, len(records), inserted


def _matches_any_glob(key: str, globs: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(key, g) for g in globs)


def _iter_targets(
    buckets: Iterable[str],
    prefix: str,
    already: set[tuple[str, str]],
    limit: int | None,
    exclude_globs: tuple[str, ...],
):
    """Yield (bucket_role, source_key) tuples to process, applying exclude + skip + limit."""
    seen = 0
    for bucket_role in buckets:
        for source_key in list_source_keys(bucket_role=bucket_role, prefix=prefix):
            if _matches_any_glob(source_key, exclude_globs):
                yield ("EXCLUDE", bucket_role, source_key)
                continue
            if (bucket_role, source_key) in already:
                yield ("SKIP", bucket_role, source_key)
                continue
            if limit is not None and seen >= limit:
                return
            seen += 1
            yield ("DO", bucket_role, source_key)


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
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help=(
            "Override MELILO_BACKEND_CONCURRENCY for this run. Ignored for the HF "
            "backend (always 1)."
        ),
    )
    parser.add_argument(
        "--license",
        required=True,
        help=(
            "License of the source corpus for this sweep. Must be one of: PD, CC0, "
            "CC-BY-4.0 (or other CC-BY-*). Per govparti policy, NC/SA/ND licenses "
            "are dealkillers and rejected. Verify-at-source before running."
        ),
    )
    parser.add_argument(
        "--attribution",
        default=None,
        help=(
            "Attribution string. REQUIRED when --license starts with CC-BY. Example: "
            "\"LegiScan; data licensed CC BY 4.0\". Surfaced wherever pair renders."
        ),
    )
    parser.add_argument(
        "--source-org",
        default=None,
        help=(
            "Upstream provider/organization, e.g. LegiScan, Congress.gov, "
            "CourtListener. Stored on each pair for provenance and filtering."
        ),
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=None,
        help=(
            "Glob pattern to skip (e.g. '*.meta.json'). Repeat for multiple. "
            f"Defaults to {DEFAULT_EXCLUDE_GLOBS!r} which skip govparti sidecar metadata."
        ),
    )
    args = parser.parse_args()
    exclude_globs: tuple[str, ...] = (
        tuple(args.exclude) if args.exclude else DEFAULT_EXCLUDE_GLOBS
    )

    validate_task_source(args.task, args.source_type)
    validate_license(args.license, args.attribution)

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    buckets: tuple[str, ...] = (
        SOURCE_BUCKETS if args.bucket == "both" else (args.bucket,)
    )

    # The HF backend is GPU-bound and runs sequentially. HTTP backends can fan out.
    backend = settings.backend.lower().strip()
    if backend == "hf":
        concurrency = 1
    else:
        concurrency = args.concurrency or settings.backend_concurrency

    print("ensuring Neon schema is bootstrapped ...", file=sys.stderr)
    bootstrap_schema()

    print(f"snapshotting already-processed origins for task={args.task} ...", file=sys.stderr)
    already = list_processed_origins(task_type=args.task)
    print(f"  found {len(already)} already-processed (bucket, key) pairs", file=sys.stderr)

    print(
        f"loading translator: backend={backend} "
        f"({'in-process HF' if backend == 'hf' else settings.openai_base_url})",
        file=sys.stderr,
    )
    translator = load_translator()

    counters = {
        "seen": 0,
        "written": 0,
        "skipped": 0,
        "excluded": 0,
        "failed": 0,
        "rows_inserted": 0,
    }
    counters_lock = threading.Lock()

    def _bump(key: str, by: int = 1) -> None:
        with counters_lock:
            counters[key] += by

    def _submit_one(bucket_role: str, source_key: str):
        try:
            br, sk, n_records, inserted = _process_one(
                bucket_role=bucket_role,
                source_key=source_key,
                task=args.task,
                source_type=args.source_type,
                run_id=run_id,
                translator=translator,
                license=args.license,
                attribution=args.attribution,
                source_org=args.source_org,
            )
            _bump("written")
            _bump("rows_inserted", inserted)
            print(
                f"OK   {br}/{sk} -> {n_records} pairs ({inserted} new rows)",
                file=sys.stderr,
            )
        except Exception as exc:  # noqa: BLE001
            _bump("failed")
            print(f"FAIL {bucket_role}/{source_key}: {exc}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

    targets = _iter_targets(buckets, args.prefix, already, args.limit, exclude_globs)

    if concurrency == 1:
        for kind, bucket_role, source_key in targets:
            if kind == "EXCLUDE":
                _bump("excluded")
                continue
            if kind == "SKIP":
                _bump("skipped")
                continue
            _bump("seen")
            _submit_one(bucket_role, source_key)
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = []
            for kind, bucket_role, source_key in targets:
                if kind == "EXCLUDE":
                    _bump("excluded")
                    continue
                if kind == "SKIP":
                    _bump("skipped")
                    continue
                _bump("seen")
                futures.append(pool.submit(_submit_one, bucket_role, source_key))
            # Drain to surface any uncaught exceptions (defense in depth — _submit_one
            # is already try/except'd).
            for fut in as_completed(futures):
                fut.result()

    print(
        "done: "
        f"seen={counters['seen']} written={counters['written']} "
        f"skipped={counters['skipped']} excluded={counters['excluded']} "
        f"failed={counters['failed']} new_rows={counters['rows_inserted']}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
