"""Neon (Postgres) store for Melilo pair records.

One table, `pairs`, mirroring the JSONL schema written to R2. The R2 archive is
authoritative for replay; Neon is authoritative for queries (training-set
construction, civic frontend lookups, dedup).

Skip-if-exists during backfill is keyed on (task_type, source_bucket, source_key,
section_id) — that tuple uniquely identifies a "unit of work" regardless of
content. If the source text changes for the same key, the unique constraint
still skips, which is what we want for resumption; force-regeneration is a
separate flag wired into the backfill driver.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterable, Iterator, Sequence

import psycopg
from psycopg.rows import dict_row

from melilo.config import settings


SCHEMA_DDL = """
-- 1. Base table (no-op if it already exists).
CREATE TABLE IF NOT EXISTS pairs (
    id                TEXT        PRIMARY KEY,
    task_type         TEXT        NOT NULL,
    source_type       TEXT        NOT NULL,
    source_bucket     TEXT        NOT NULL,  -- 'public' | 'internal'
    source_key        TEXT        NOT NULL,
    source_uri        TEXT        NOT NULL,
    section_id        TEXT,                  -- only set for section_walkthrough
    source_text       TEXT        NOT NULL,
    translation       TEXT        NOT NULL,
    translator_model  TEXT        NOT NULL,
    prompt_version    TEXT        NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL,
    training_set      TEXT,
    human_reviewed    BOOLEAN     NOT NULL DEFAULT FALSE,
    review_notes      TEXT,
    license           TEXT,                  -- 'PD' | 'CC0' | 'CC-BY-4.0' | etc.
    attribution       TEXT,                  -- REQUIRED when license starts with 'CC-BY'
    source_org        TEXT                   -- 'LegiScan' | 'Congress.gov' | etc.
);

-- 2. Idempotent column adds — run BEFORE any index uses these columns so
-- existing-deployment migrations succeed in one transaction.
ALTER TABLE pairs ADD COLUMN IF NOT EXISTS license     TEXT;
ALTER TABLE pairs ADD COLUMN IF NOT EXISTS attribution TEXT;
ALTER TABLE pairs ADD COLUMN IF NOT EXISTS source_org  TEXT;

-- 3. Indexes. COALESCE on section_id so NULL collapses to '' for the unique
-- constraint (Postgres NULLs would otherwise allow duplicates).
CREATE UNIQUE INDEX IF NOT EXISTS uq_pairs_origin
    ON pairs (task_type, source_bucket, source_key, COALESCE(section_id, ''));

CREATE INDEX IF NOT EXISTS ix_pairs_task_source     ON pairs (task_type, source_type);
CREATE INDEX IF NOT EXISTS ix_pairs_source_key      ON pairs (source_key);
CREATE INDEX IF NOT EXISTS ix_pairs_prompt_version  ON pairs (prompt_version);
CREATE INDEX IF NOT EXISTS ix_pairs_training_set    ON pairs (training_set);
CREATE INDEX IF NOT EXISTS ix_pairs_license         ON pairs (license);
CREATE INDEX IF NOT EXISTS ix_pairs_source_org      ON pairs (source_org);
"""


# Licenses approved by govparti's policy (see melilo-licensing memory).
# Anything else must be rejected before we burn translator tokens on it.
APPROVED_LICENSES: set[str] = {
    "PD",            # public domain (17 USC § 105, court opinions, state statutes)
    "CC0",
    "CC-BY-4.0",
    "CC-BY-3.0",
    "CC-BY-2.0",
    "CC-BY-1.0",
}


def validate_license(license_: str | None, attribution: str | None) -> None:
    """Enforce govparti's license policy at the point pairs would be written.
    Raises ValueError if the (license, attribution) pair is unacceptable."""
    if not license_:
        raise ValueError(
            "license is required for every backfill run. Pass --license "
            f"with one of: {sorted(APPROVED_LICENSES)}. See melilo-licensing memo."
        )
    if license_ not in APPROVED_LICENSES:
        raise ValueError(
            f"license {license_!r} is not on the approved list "
            f"({sorted(APPROVED_LICENSES)}). NC/SA/ND/aggregator licenses are "
            "dealkillers per govparti policy."
        )
    if license_.startswith("CC-BY") and not attribution:
        raise ValueError(
            f"license {license_!r} requires --attribution to be set. CC BY "
            "demands attribution wherever the data renders."
        )


@contextmanager
def _connect() -> Iterator[psycopg.Connection]:
    if not settings.neon_database_url:
        raise RuntimeError(
            "NEON_DATABASE_URL is not set in .env — set it to your Neon "
            "connection string (postgresql://...)."
        )
    # autocommit=False; callers commit explicitly. psycopg defaults to a
    # transaction at first execute(), which is what we want.
    with psycopg.connect(settings.neon_database_url) as conn:
        yield conn


def bootstrap_schema() -> None:
    """Create the `pairs` table and indexes if they don't exist. Safe to call on
    every startup; CREATE ... IF NOT EXISTS is idempotent."""
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(SCHEMA_DDL)
        conn.commit()


_PAIR_COLS = (
    "id", "task_type", "source_type", "source_bucket", "source_key",
    "source_uri", "section_id", "source_text", "translation",
    "translator_model", "prompt_version", "created_at",
    "license", "attribution", "source_org",
)


def upsert_pair(record: dict) -> bool:
    """Insert a pair record. Returns True if a new row was written, False if a
    row for the same (task, source_bucket, source_key, section_id) already
    existed. The `id` PK collision case is also handled (same content -> same id)."""
    placeholders = ", ".join(["%s"] * len(_PAIR_COLS))
    sql = (
        f"INSERT INTO pairs ({', '.join(_PAIR_COLS)}) VALUES ({placeholders}) "
        "ON CONFLICT DO NOTHING RETURNING id"
    )
    values = tuple(record.get(c) for c in _PAIR_COLS)
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, values)
        inserted = cur.fetchone() is not None
        conn.commit()
        return inserted


def upsert_pairs(records: Sequence[dict]) -> int:
    """Batched insert. Returns the number of newly-inserted rows."""
    if not records:
        return 0
    placeholders = ", ".join(["%s"] * len(_PAIR_COLS))
    sql = (
        f"INSERT INTO pairs ({', '.join(_PAIR_COLS)}) VALUES ({placeholders}) "
        "ON CONFLICT DO NOTHING"
    )
    with _connect() as conn, conn.cursor() as cur:
        rows = [tuple(r.get(c) for c in _PAIR_COLS) for r in records]
        cur.executemany(sql, rows)
        inserted = cur.rowcount  # psycopg sums executemany rowcounts
        conn.commit()
        return inserted


def list_processed_origins(
    task_type: str,
    source_bucket: str | None = None,
) -> set[tuple[str, str]]:
    """Return the set of (source_bucket, source_key) tuples that already have at
    least one pair row for the given task. Backfill uses this to skip already-
    processed sources before invoking OLMo."""
    sql = "SELECT DISTINCT source_bucket, source_key FROM pairs WHERE task_type = %s"
    params: list = [task_type]
    if source_bucket is not None:
        sql += " AND source_bucket = %s"
        params.append(source_bucket)
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return {(row[0], row[1]) for row in cur.fetchall()}


def iter_pairs(
    *,
    task_type: str | None = None,
    source_type: str | None = None,
    prompt_version: str | None = None,
    human_reviewed_only: bool = False,
    batch_size: int = 500,
) -> Iterator[dict]:
    """Stream pair records as dicts, filterable. Used by SFT to build the training
    dataset. Yields in `created_at` order so the resulting dataset is reproducible
    for a given filter snapshot."""
    where: list[str] = []
    params: list = []
    if task_type is not None:
        where.append("task_type = %s")
        params.append(task_type)
    if source_type is not None:
        where.append("source_type = %s")
        params.append(source_type)
    if prompt_version is not None:
        where.append("prompt_version = %s")
        params.append(prompt_version)
    if human_reviewed_only:
        where.append("human_reviewed = TRUE")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"SELECT * FROM pairs {where_sql} ORDER BY created_at, id"
    with _connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        while True:
            rows = cur.fetchmany(batch_size)
            if not rows:
                break
            yield from rows
