"""Storage backends for Melilo pair records.

Belt-and-suspenders: every pair is written to BOTH

- the R2 Melilo bucket as JSONL (immutable archive, via melilo.ingest.r2_client),
- Neon Postgres as a row in `pairs` (query layer, this package).

R2 is written first; Neon second. That way a transient Neon outage leaves the
archive intact and we can reconcile from it. The pair `id` (a content-addressed
sha256) is the same in both, so reconciliation is a straight idempotent upsert.
"""
from melilo.store.neon import (  # noqa: F401
    bootstrap_schema,
    iter_pairs,
    list_processed_origins,
    upsert_pair,
)
