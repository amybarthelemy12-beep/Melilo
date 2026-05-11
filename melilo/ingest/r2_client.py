"""R2 (S3-compatible) client wrappers for source docs and pair storage."""
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


def list_source_keys(prefix: str = "") -> Iterator[str]:
    s3 = _client()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.r2_source_bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            yield obj["Key"]


def fetch_source(key: str) -> SourceDoc:
    s3 = _client()
    obj = s3.get_object(Bucket=settings.r2_source_bucket, Key=key)
    return SourceDoc(key=key, body=obj["Body"].read())


def write_pairs_jsonl(key: str, records: Iterable[dict]) -> None:
    """Append-style write of JSONL pair records to the pairs bucket."""
    s3 = _client()
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in records).encode("utf-8")
    s3.put_object(
        Bucket=settings.r2_pairs_bucket,
        Key=key,
        Body=body,
        ContentType="application/x-ndjson",
    )
