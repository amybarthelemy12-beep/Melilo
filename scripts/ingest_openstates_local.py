#!/usr/bin/env python3
"""Ingest Open States from a LOCAL pgdump (not from Melilo's pairs Neon).

Your Open States data is:
  raw_texts/OPEN_STATES/2026-08-public.pgdump   (~10GB custom-format dump)
  raw_texts/OPEN_STATES/2026-08-schema.pgdump
  raw_texts/OPEN_STATES/2026-08-manifest.json

Melilo's NEON_DATABASE_URL points at the pairs table — that is NOT Open States.
This script restores the local dump into a *separate* Postgres (local Docker or
a dedicated Neon branch), then stages bill text for Melilo.

Prereqs:
  - pg_restore / psql on PATH (Postgres client tools)
  - A target database that is EMPTY or only for Open States
    (do NOT use the Melilo pairs database)

Quick path (Docker):
  docker run -d --name os-pg -e POSTGRES_PASSWORD=os -p 5433:5432 postgres:16
  $env:OPENSTATES_DATABASE_URL = "postgresql://postgres:os@localhost:5433/postgres"

  python scripts/ingest_openstates_local.py restore --dump raw_texts/OPEN_STATES/2026-08-public.pgdump
  python scripts/ingest_openstates_local.py stage --out staging/openstates_bills --limit 500

Usage:
  python scripts/ingest_openstates_local.py list --dump raw_texts/OPEN_STATES/2026-08-public.pgdump
  python scripts/ingest_openstates_local.py restore --dump ...
  python scripts/ingest_openstates_local.py stage --limit 200 --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    print("pip install psycopg[binary]", file=sys.stderr)
    sys.exit(1)


def _dsn() -> str:
    # Never fall back to NEON_DATABASE_URL — that is Melilo pairs.
    url = os.environ.get("OPENSTATES_DATABASE_URL")
    if not url:
        print(
            "Set OPENSTATES_DATABASE_URL to a SEPARATE Postgres (not Melilo pairs).\n"
            "Example Docker:\n"
            "  docker run -d --name os-pg -e POSTGRES_PASSWORD=os -p 5433:5432 postgres:16\n"
            "  $env:OPENSTATES_DATABASE_URL = 'postgresql://postgres:os@localhost:5433/postgres'",
            file=sys.stderr,
        )
        sys.exit(1)
    return url


def _safe_name(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", str(s))[:160]


def cmd_list(dump: Path) -> None:
    if not dump.is_file():
        print(f"Missing dump: {dump}", file=sys.stderr)
        sys.exit(1)
    print(f"Listing TOC for {dump} ...", file=sys.stderr)
    r = subprocess.run(
        ["pg_restore", "-l", str(dump)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        sys.exit(r.returncode)
    lines = [ln for ln in r.stdout.splitlines() if ln.strip() and not ln.startswith(";")]
    # highlight bill-ish objects
    for ln in lines:
        low = ln.lower()
        if any(k in low for k in ("bill", "version", "vote", "sponsor", "action")):
            print(ln)
    print(f"\n(total TOC entries: {len(lines)})", file=sys.stderr)


def cmd_restore(dump: Path) -> None:
    dsn = _dsn()
    if not dump.is_file():
        print(f"Missing dump: {dump}", file=sys.stderr)
        sys.exit(1)
    print(f"Restoring {dump} → OPENSTATES_DATABASE_URL ...", file=sys.stderr)
    print("This can take a long time on a 10GB dump.", file=sys.stderr)
    # --no-owner --no-acl so it works on Neon / non-superuser
    r = subprocess.run(
        [
            "pg_restore",
            "--verbose",
            "--no-owner",
            "--no-acl",
            "--dbname", dsn,
            str(dump),
        ],
    )
    if r.returncode not in (0, 1):
        # pg_restore often exits 1 with non-fatal warnings
        print(f"pg_restore exited {r.returncode}", file=sys.stderr)
        sys.exit(r.returncode)
    print("Restore finished.", file=sys.stderr)


CANDIDATE_QUERIES = [
    """
    SELECT
        b.id AS bill_id,
        COALESCE(b.identifier, b.bill_id::text) AS identifier,
        COALESCE(b.title, '') AS title,
        COALESCE(b.jurisdiction_id, b.from_organization, 'unknown') AS jurisdiction,
        COALESCE(b.legislative_session, b.session, 'unknown') AS session,
        COALESCE(v.text, v.data, v.content, '') AS body
    FROM bills b
    LEFT JOIN bill_versions v ON v.bill_id = b.id
    WHERE length(COALESCE(v.text, v.data, v.content, '')) > 200
    ORDER BY 1
    LIMIT %s
    """,
    """
    SELECT
        id AS bill_id,
        COALESCE(identifier, id::text) AS identifier,
        COALESCE(title, '') AS title,
        COALESCE(jurisdiction_id, jurisdiction, 'unknown') AS jurisdiction,
        COALESCE(session, legislative_session, 'unknown') AS session,
        COALESCE(title, '') || E'\n\n' || COALESCE(abstract, summary, '') AS body
    FROM bills
    WHERE length(COALESCE(abstract, summary, title, '')) > 80
    LIMIT %s
    """,
]


def cmd_stage(out: Path, limit: int, dry_run: bool, jsonl: Path | None) -> None:
    dsn = _dsn()
    rows: list[dict] = []
    with psycopg.connect(dsn) as conn, conn.cursor(row_factory=dict_row) as cur:
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
        print(f"Tables in Open States DB ({len(tables)}):", file=sys.stderr)
        for t in tables:
            print(f"  {t['table_schema']}.{t['table_name']}", file=sys.stderr)

        for i, sql in enumerate(CANDIDATE_QUERIES):
            try:
                cur.execute(sql, (limit,))
                rows = list(cur.fetchall())
                if rows:
                    print(f"Query #{i+1} → {len(rows)} rows", file=sys.stderr)
                    break
                print(f"Query #{i+1} → 0 rows", file=sys.stderr)
            except Exception as exc:
                print(f"Query #{i+1} failed: {exc}", file=sys.stderr)
                conn.rollback()

    if not rows:
        print(
            "No bill text found. Dump may store versions as links only, or table names differ.\n"
            "Run: python scripts/ingest_openstates_local.py list --dump <dump>\n"
            "Then adjust CANDIDATE_QUERIES.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not dry_run:
        out.mkdir(parents=True, exist_ok=True)

    written = 0
    manifest = []
    for r in rows:
        body = (r.get("body") or "").strip()
        if len(body) < 80:
            continue
        ident = r.get("identifier") or str(r.get("bill_id"))
        juris = r.get("jurisdiction") or "unknown"
        session = r.get("session") or "unknown"
        title = r.get("title") or ""
        fname = _safe_name(f"{juris}_{session}_{ident}") + ".txt"
        text = f"{ident}\n{title}\n{'=' * 60}\n\n{body}"
        if dry_run:
            print(f"  WOULD WRITE {fname} ({len(text):,} chars) {title[:70]}")
        else:
            (out / fname).write_text(text, encoding="utf-8")
            print(f"  WROTE {fname} ({len(text):,} chars)")
        manifest.append({
            "source_type": "bill",
            "source_key": f"openstates/{juris}/{session}/{ident}",
            "title": title,
            "chars": len(text),
        })
        written += 1

    if jsonl and not dry_run:
        with open(jsonl, "w", encoding="utf-8") as fh:
            for m in manifest:
                fh.write(json.dumps(m, ensure_ascii=False) + "\n")
        print(f"Manifest → {jsonl}", file=sys.stderr)

    print(f"Staged {written} bills → {out.resolve()}", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description="Open States local pgdump → Melilo staging")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List bill-related objects in the dump TOC")
    p_list.add_argument("--dump", required=True)

    p_restore = sub.add_parser("restore", help="pg_restore dump into OPENSTATES_DATABASE_URL")
    p_restore.add_argument("--dump", required=True)

    p_stage = sub.add_parser("stage", help="Query restored DB and write bill .txt files")
    p_stage.add_argument("--out", default="staging/openstates_bills")
    p_stage.add_argument("--limit", type=int, default=500)
    p_stage.add_argument("--dry-run", action="store_true")
    p_stage.add_argument("--jsonl", default=None)

    args = ap.parse_args()

    if args.cmd == "list":
        cmd_list(Path(args.dump))
    elif args.cmd == "restore":
        cmd_restore(Path(args.dump))
    elif args.cmd == "stage":
        cmd_stage(Path(args.out), args.limit, args.dry_run, Path(args.jsonl) if args.jsonl else None)


if __name__ == "__main__":
    main()
