#!/usr/bin/env python3
"""Pull bill text from an Open States Neon database and stage Melilo-ready records.

No GovParti API. Connects to the same NEON_DATABASE_URL (or a dedicated
OPENSTATES_DATABASE_URL) and extracts bill versions that have usable full text.

Outputs:
  - staging/openstates_bills/{jurisdiction}_{session}_{identifier}.txt  (plain text)
  - optional JSONL of lightweight source records for later pair generation

Usage:
  # inventory what text is available
  python scripts/ingest_openstates_neon.py --dry-run --limit 20

  # stage text
  python scripts/ingest_openstates_neon.py --out staging/openstates_bills --limit 500

  # also write a JSONL manifest
  python scripts/ingest_openstates_neon.py --out staging/openstates_bills --jsonl staging/openstates_manifest.jsonl

Env:
  NEON_DATABASE_URL          – default connection string
  OPENSTATES_DATABASE_URL    – optional override if Open States lives on a different Neon branch/db

Schema assumptions (Open States bulk / common layouts):
  Tries several table/column patterns. Adjust the SQL blocks below if your
  restore used different names. Run with --dry-run first to see what it finds.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    print("psycopg is required: pip install psycopg[binary]", file=sys.stderr)
    sys.exit(1)


def _conninfo() -> str:
    url = os.environ.get("OPENSTATES_DATABASE_URL") or os.environ.get("NEON_DATABASE_URL")
    if not url:
        print("Set NEON_DATABASE_URL or OPENSTATES_DATABASE_URL in the environment.", file=sys.stderr)
        sys.exit(1)
    return url


def _safe_name(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", s)[:160]


# Ordered attempts — first query that returns rows wins.
# Adjust to match your actual Open States restore schema.
CANDIDATE_QUERIES = [
    # Common modern Open States shape (bills + billversions / versions)
    """
    SELECT
        b.id              AS bill_id,
        b.identifier      AS identifier,
        b.title           AS title,
        b.from_organization AS jurisdiction,
        b.legislative_session AS session,
        v.note            AS version_note,
        v.date            AS version_date,
        COALESCE(v.text, v.data, '') AS body
    FROM bills b
    JOIN bill_versions v ON v.bill_id = b.id
    WHERE length(COALESCE(v.text, v.data, '')) > 200
    ORDER BY b.updated_at DESC NULLS LAST
    LIMIT %s
    """,
    # Alternate: versions stored as JSON / links only — pull title + abstract
    """
    SELECT
        b.id         AS bill_id,
        b.identifier AS identifier,
        b.title      AS title,
        b.jurisdiction_id AS jurisdiction,
        b.session    AS session,
        NULL         AS version_note,
        NULL         AS version_date,
        COALESCE(b.title, '') || E'\n\n' || COALESCE(b.abstract, b.summary, '') AS body
    FROM bills b
    WHERE length(COALESCE(b.abstract, b.summary, b.title, '')) > 80
    ORDER BY b.updated_at DESC NULLS LAST
    LIMIT %s
    """,
    # Very flat fallback
    """
    SELECT
        id          AS bill_id,
        identifier  AS identifier,
        title       AS title,
        jurisdiction AS jurisdiction,
        session     AS session,
        NULL        AS version_note,
        NULL        AS version_date,
        COALESCE(text, body, content, title, '') AS body
    FROM bills
    WHERE length(COALESCE(text, body, content, title, '')) > 80
    LIMIT %s
    """,
]


def discover_and_fetch(limit: int) -> list[dict]:
    url = _conninfo()
    rows: list[dict] = []
    with psycopg.connect(url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # List tables to help debugging
            cur.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                  AND table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY 1, 2
                """
            )
            tables = cur.fetchall()
            print(f"Found {len(tables)} tables in Open States DB:", file=sys.stderr)
            for t in tables[:40]:
                print(f"  {t['table_schema']}.{t['table_name']}", file=sys.stderr)
            if len(tables) > 40:
                print(f"  ... +{len(tables) - 40} more", file=sys.stderr)

            for i, sql in enumerate(CANDIDATE_QUERIES):
                try:
                    cur.execute(sql, (limit,))
                    rows = list(cur.fetchall())
                    if rows:
                        print(f"Query #{i+1} returned {len(rows)} rows", file=sys.stderr)
                        break
                    print(f"Query #{i+1} returned 0 rows, trying next...", file=sys.stderr)
                except Exception as exc:
                    print(f"Query #{i+1} failed: {exc}", file=sys.stderr)
                    conn.rollback()
                    continue

    if not rows:
        print(
            "No bill text found with the built-in queries. "
            "Inspect the table list above and adjust CANDIDATE_QUERIES in this script.",
            file=sys.stderr,
        )
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage Open States bill text from Neon")
    ap.add_argument("--out", default="staging/openstates_bills", help="Directory for .txt files")
    ap.add_argument("--jsonl", default=None, help="Optional manifest JSONL path")
    ap.add_argument("--limit", type=int, default=1000, help="Max bills to pull")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = discover_and_fetch(args.limit)
    if not rows:
        sys.exit(1)

    out_dir = Path(args.out)
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    manifest = []
    for r in rows:
        body = (r.get("body") or "").strip()
        if len(body) < 80:
            continue
        ident = r.get("identifier") or r.get("bill_id") or f"row{written}"
        juris = r.get("jurisdiction") or "unknown"
        session = r.get("session") or "unknown"
        title = r.get("title") or ""
        fname = _safe_name(f"{juris}_{session}_{ident}") + ".txt"
        header = f"{ident}\n{title}\n{'=' * 60}\n\n"
        text = header + body

        if args.dry_run:
            print(f"  WOULD WRITE {fname} ({len(text):,} chars) — {title[:80]}")
        else:
            (out_dir / fname).write_text(text, encoding="utf-8")
            print(f"  WROTE {fname} ({len(text):,} chars)")

        manifest.append({
            "source_type": "bill",
            "source_key": f"openstates/{juris}/{session}/{ident}",
            "title": title,
            "jurisdiction": juris,
            "session": session,
            "identifier": ident,
            "chars": len(text),
            "path": str(out_dir / fname) if not args.dry_run else None,
        })
        written += 1

    if args.jsonl and not args.dry_run:
        with open(args.jsonl, "w", encoding="utf-8") as fh:
            for m in manifest:
                fh.write(json.dumps(m, ensure_ascii=False) + "\n")
        print(f"Wrote manifest → {args.jsonl}", file=sys.stderr)

    print(f"Done. Staged {written} bill texts → {out_dir.resolve()}", file=sys.stderr)


if __name__ == "__main__":
    main()
