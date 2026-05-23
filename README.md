# Melilo

An Apache 2.0 language model that turns court opinions, statutes, bills,
regulations, and declassified government documents into structured legal
analysis in plain English.

Melilo is fine-tuned from the [OLMo](https://allenai.org/olmo) family
(Allen AI, Apache 2.0). The workflow is pure distillation: a larger OLMo
instruct model is run over raw historical govparti documents to produce
`(source_text, structured_output)` pairs, which then supervise a smaller
student. No hand-labeled data is required for v1.

## Intended users

- **Nonpartisan civic-information platforms** (govparti and similar) — sites
  that surface what a law says, what a court decided, what a bill would do,
  and what it means for a non-lawyer, without taking a side. The system
  prompt forbids characterizing parties, judges, lawmakers, agencies, or
  policy positions.
- **Law students** — PIRAC analyses and case briefs as study aids. Section
  labels and citations are preserved verbatim so the output can be checked
  against the primary source.

Melilo is **not a lawyer**, does not give legal advice, and is not a
substitute for reading the underlying document.

## Tasks and source types

| Task                  | Applies to                                                        | Output                                                                                                                       |
|-----------------------|-------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| `pirac`               | `case`                                                            | FIRAC: `## Facts/Parties`, `## Issue`, `## Rule`, `## Analysis`, `## Conclusion`                                             |
| `brief`               | `case`                                                            | Case brief: `## Citation`, `## Facts`, `## Procedural History`, `## Issue`, `## Holding`, `## Reasoning`, `## Disposition`  |
| `summary`             | `case`, `statute`, `bill`, `regulation`, `declassified`           | Prose lede; for statutes/bills/regulations adds `## Key Provisions` bulleted list; for cases 2–4 sentences; for declassified prose only with redaction markers preserved |
| `section_walkthrough` | `statute`, `bill`, `regulation`, `declassified`                   | One record per § section; each chunk's H2 header is the source's section identifier verbatim, followed by a plain-English explanation |

Valid `(task, source_type)` combinations live in
[`pipeline.VALID_TASK_SOURCE`](melilo/translate/pipeline.py); the CLI fails
fast on a bad combo before loading the model.

## Storage architecture

Pairs are written to **two** places (belt-and-suspenders):

- **R2** (Cloudflare object storage) — the immutable JSONL archive. Authoritative
  for replay. One PUT per source document, keyed as
  `pairs/<task>/<run_id>/<bucket>/<source_key>.jsonl` in the bucket named by
  `R2_MELILO_BUCKET` (default `melilo-pairs`). `R2_MELILO_ENDPOINT` is a
  reference-only URL field — S3 writes go through `R2_ENDPOINT`.
- **Neon Postgres** — the query layer. One row per pair in the `pairs` table.
  Authoritative for SFT data loading, civic-frontend lookups, and dedup.

**Write order is R2 first, then Neon.** If Neon is briefly down, the archive
still has the work and the next run can reconcile from it.

**Raw source docs** live in R2 too, in two buckets:

| Role        | Bucket                | Public URL                          |
|-------------|-----------------------|-------------------------------------|
| `public`    | `govparti-archive`    | `https://archive.govparti.org/<key>` |
| `internal`  | `govparti-internal`   | (no public URL — `r2://` only)      |

Pair records carry `source_bucket` so provenance is preserved; public-bucket
records get a clickable `source_uri` (the `archive.govparti.org` URL) so
civic readers can reach the canonical document.

## Architecture

```
                 R2 source buckets                       Neon Postgres
            (govparti-archive, govparti-internal)        (pairs table, query layer)
                     |                                         ^
                     v                                         |
            +------------------+        +---------------------+--------------+
            |  ingest.r2_client|        | translate.pipeline                  |
            |  + extract       |------->| - validate (task, source_type)      |
            +------------------+        | - section-chunk for walkthrough     |
                                        | - prompt OLMo 3 Instruct            |
                                        | - emit versioned pair records       |
                                        +---------------------+--------------+
                                                              |
                                                  R2 first --> R2 Melilo bucket
                                                  Neon second-> Postgres upsert
                                                              |
                                                              v
                                                  +-----------+-----------+
                                                  | train.sft             |
                                                  | - stream from Neon    |
                                                  | - multi-task SFT      |
                                                  | - OLMo 2 1B student   |
                                                  +-----------------------+
```

## Setup

```bash
cp .env.example .env  # fill in R2 creds, R2_MELILO_BUCKET, NEON_DATABASE_URL
pip install -e .
melilo-migrate        # creates the pairs table + indexes in Neon
```

### Choosing a translator backend

Set `MELILO_BACKEND` in `.env`:

- `openai` (default) — calls any OpenAI-compatible HTTP API. Works with all of:
  - **Local Ollama** (no cost, runs on your GPU):
    ```bash
    # one-time
    winget install Ollama.Ollama
    ollama pull olmo-3:7b-instruct
    # .env defaults already point here; nothing else to change
    ```
  - **Parasail** — set `OPENAI_BASE_URL=https://api.parasail.io/v1`, `OPENAI_API_KEY=<your key>`, `OPENAI_MODEL=<exact Parasail slug>`.
  - **OpenRouter** — set `OPENAI_BASE_URL=https://openrouter.ai/api/v1`, `OPENAI_API_KEY=<your key>`, `OPENAI_MODEL=allenai/olmo-3-7b-instruct`.
  - **vLLM server** — point at the vLLM URL.

- `hf` — loads the HF transformers model directly in the Python process. Use this only if you have a GPU and prefer no external service. Slow without batching.

`MELILO_BACKEND_CONCURRENCY` (default 4) controls how many OpenAI-compatible requests are in flight at once. The HF backend always runs sequentially.

## Backfill flow

Every backfill sweep declares its source's license (per govparti's data-rights
policy — see `melilo-licensing` memo). Approved licenses: `PD`, `CC0`, `CC-BY-*`.
NC/SA/ND/aggregator-restricted licenses are dealkillers and rejected.

For `CC-BY-*` sources, `--attribution` is **required** and gets propagated into
each pair record so downstream renderers can surface it.

```bash
# Smoke test: list raw docs from both source buckets
melilo-ingest --prefix federal/caselaw/

# One-doc trial run (--limit 1, on local Ollama by default)
melilo-backfill --prefix federal/caselaw/ --task summary --source-type case \
    --license PD --source-org CourtListener --limit 1

# Real sweeps (one per task; both source buckets by default)
melilo-backfill --prefix federal/caselaw/ --task pirac --source-type case \
    --license PD --source-org CourtListener
melilo-backfill --prefix federal/govinfo/statutes/ --task summary --source-type statute \
    --license PD --source-org govinfo.gov
melilo-backfill --prefix federal/federal-register/ --task section_walkthrough --source-type regulation \
    --license PD --source-org "Federal Register"
melilo-backfill --prefix states/legiscan/ --task summary --source-type bill \
    --license CC-BY-4.0 --attribution "LegiScan; data licensed CC BY 4.0" --source-org LegiScan
melilo-backfill --prefix declassified-bodies/ --task summary --source-type declassified \
    --license PD --source-org "FOIA / National Security Archive"   # ONLY after PII gate audit

# Then SFT Melilo on accumulated pairs (filtered to the current prompt_version):
melilo-train --output-dir checkpoints/melilo-v0
```

`melilo-backfill` loads the translator model once, sweeps both source buckets
under the given prefix (override with `--bucket public|internal`), writes each
pair to R2 then Neon, and **skips docs already processed** for the given task
(queried from Neon).

## Models

| Role        | HuggingFace ID                  | Size | License    |
|-------------|---------------------------------|------|------------|
| Translator  | `allenai/Olmo-3-7B-Instruct`    | 7B   | Apache 2.0 |
| Student v1  | `allenai/OLMo-2-0425-1B-SFT`    | 1B   | Apache 2.0 |

Higher-quality pairs are possible with `allenai/Olmo-3-32B-Think`, but it
emits `<think>` traces that must be stripped before storage. No 32B
Instruct variant exists in the OLMo 3 line.

## Pair record schema (same in R2 JSONL and Neon `pairs`)

```json
{
  "id": "<sha256 of task|source_type|source_bucket|source_key|section_id|source_text>",
  "task_type": "section_walkthrough",
  "source_type": "regulation",
  "source_bucket": "public",
  "source_key": "federal/federal-register/12cfr1005.html",
  "source_uri": "https://archive.govparti.org/federal/federal-register/12cfr1005.html",
  "section_id": "§ 1005.1",
  "source_text": "§ 1005.1 ... full section text ...",
  "translation": "## § 1005.1\nThis section requires ...",
  "translator_model": "allenai/Olmo-3-7B-Instruct",
  "prompt_version": "v3-pirac-brief-summary-walkthrough",
  "created_at": "2026-05-22T00:00:00Z",
  "license": "PD",
  "attribution": null,
  "source_org": "Federal Register"
}
```

Neon adds three columns not in the JSONL: `training_set`, `human_reviewed`,
`review_notes`. These are written after the fact (when a pair is reviewed by a
human, or consumed by a specific SFT run).

### Licensing policy (`license`, `attribution`)

GovParti's data-rights policy is enforced at the `melilo-backfill` and
`melilo-translate` entry points (`melilo.store.validate_license`):

- **Allowed:** `PD`, `CC0`, `CC-BY-*`
- **Rejected:** anything with NC, SA, or ND in the license; aggregator
  licenses with restrictive terms (SAM.gov, ICPSR, etc.)
- **CC-BY-* requires `--attribution`** — the run refuses without it
- **Verify-at-source** — the operator is responsible for confirming the license
  at the upstream source itself (not internal notes) before each sweep
- **Indigenous sovereignty + PII gates** are enforced UPSTREAM in the govparti
  R2 promotion pipeline, not in Melilo

See `melilo-licensing` memo for the full policy including the deny-list.

## Layout

```
melilo/
  config.py            # env-driven settings, source_uri helper, bucket-role mapping
  ingest/r2_client.py  # public/internal source buckets + Melilo archive bucket
  ingest/extract.py    # PDF/HTML/TXT -> text
  translate/prompts.py # PIRAC / brief / summary / section_walkthrough prompt builders
  translate/pipeline.py# task dispatch, section chunker, pair-record schema
  store/neon.py        # Neon Postgres: schema, upsert, iter_pairs, list_processed_origins
  train/sft.py         # multi-task SFT on the OLMo 2 1B student; streams from Neon
scripts/
  migrate.py           # melilo-migrate: bootstrap the Neon pairs table
  ingest.py            # melilo-ingest: list source keys from one or both buckets
  translate.py         # melilo-translate: one doc -> R2 JSONL + Neon row
  backfill.py          # melilo-backfill: batch sweep across both buckets
  train.py             # melilo-train: SFT the student on Neon pairs
```

## Suggested public corpora

All Apache-2.0 or public-domain compatible:

- **[CourtListener / Free Law Project](https://www.courtlistener.com/help/api/bulk-data/)** — bulk federal and state court opinions.
- **[Caselaw Access Project](https://case.law/)** (Harvard) — open caselaw, CC0 for most jurisdictions.
- **[govinfo.gov bulk data](https://www.govinfo.gov/bulkdata)** — U.S. Code, public laws, federal statutes; federal bills; Federal Register and CFR.
- **[Congress.gov bulk data](https://www.congress.gov/about/data-files-and-bulk-data)** — current bills with sponsor metadata.
- **[National Security Archive](https://nsarchive.gwu.edu/)** / FOIA reading rooms — declassified government documents.

## License

Apache 2.0. Derivative of OLMo (Allen AI), also Apache 2.0.
