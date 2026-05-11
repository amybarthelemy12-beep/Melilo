"""List source documents in the R2 source bucket and print their keys.

Once we agree on a chunking strategy this will pull bytes, parse, and write
chunk manifests to a queue (or a manifest object in the pairs bucket).
"""
from __future__ import annotations

import argparse

from melilo.ingest.r2_client import list_source_keys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="", help="R2 key prefix to scope the listing")
    args = parser.parse_args()

    for key in list_source_keys(prefix=args.prefix):
        print(key)


if __name__ == "__main__":
    main()
