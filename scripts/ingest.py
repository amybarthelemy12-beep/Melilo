"""List source documents in govparti's R2 source buckets.

By default lists both `public` (govparti-archive) and `internal`
(govparti-internal). Pass `--bucket public|internal` to limit.

This is a read-only inventory script — no pairs are written. Useful as a
connectivity smoke test after wiring up .env.
"""
from __future__ import annotations

import argparse

from melilo.config import SOURCE_BUCKETS
from melilo.ingest.r2_client import list_source_keys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bucket",
        default="both",
        choices=("both", *SOURCE_BUCKETS),
        help="Which source bucket(s) to list. Default: both.",
    )
    parser.add_argument("--prefix", default="", help="R2 key prefix to scope the listing")
    args = parser.parse_args()

    roles = SOURCE_BUCKETS if args.bucket == "both" else (args.bucket,)
    for role in roles:
        for key in list_source_keys(bucket_role=role, prefix=args.prefix):
            print(f"{role}\t{key}")


if __name__ == "__main__":
    main()
