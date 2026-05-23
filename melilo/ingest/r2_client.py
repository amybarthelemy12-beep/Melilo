"""R2 (S3-compatible) client wrappers.

Three buckets are addressable through this module:

- `source_bucket_role="public"`   -> reads from `settings.r2_public_bucket`
- `source_bucket_role="internal"` -> reads from `settings.r2_internal_bucket`
- pair writes always target `settings.r2_melilo_bucket`

Callers pass the logical role (`public`/`internal`); the bucket-name lookup
lives in `settings.source_bucket_name` so we have one place to change if the
R2 layout shifts.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Iterator

import boto3
from botocore.client import Config

from melilo.config import settings


def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


@dataclass
class SourceDoc:
    key: str
    body: bytes
    bucket_role: str  # "public" | "internal" — propagated into pair records


def list_source_keys(bucket_role: str, prefix: str = "") -> Iterator[str]:
    """Yield keys under `prefix` in the given source bucket (public or internal)."""
    bucket = settings.source_bucket_name(bucket_role)
    s3 = _client()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            yield obj["Key"]


def fetch_source(bucket_role: str, key: str) -> SourceDoc:
    bucket = settings.source_bucket_name(bucket_role)
    s3 = _client()
    obj = s3.get_object(Bucket=bucket, Key=key)
    return SourceDoc(key=key, body=obj["Body"].read(), bucket_role=bucket_role)


def write_pairs_jsonl(key: str, records: Iterable[dict]) -> None:
    """Write JSONL pair records to the Melilo bucket. One PUT per call."""
    if not settings.r2_melilo_bucket:
        raise RuntimeError(
            "R2_MELILO_BUCKET is not set in .env — set it to the bucket name "
            "where Melilo pairs should be written (default: melilo-pairs)."
        )
    s3 = _client()
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in records).encode("utf-8")
    s3.put_object(
        Bucket=settings.r2_melilo_bucket,
        Key=key,
        Body=body,
        ContentType="application/x-ndjson",
    )


def list_pair_keys(prefix: str = "") -> Iterator[str]:
    """List keys in the Melilo (pairs) bucket. Used by backfill for skip-if-exists."""
    if not settings.r2_melilo_bucket:
        raise RuntimeError("R2_MELILO_BUCKET is not set in .env")
    s3 = _client()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.r2_melilo_bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            yield obj["Key"]
