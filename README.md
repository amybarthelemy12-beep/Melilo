# Melilo

An Apache 2.0 language model that translates legal text into plain English.

Melilo is fine-tuned from the [OLMo](https://allenai.org/olmo) family
(Allen AI, Apache 2.0). Training pairs are produced by running a larger OLMo
instruct model over legal source documents and storing
`(legal_text, plain_english)` pairs for supervised fine-tuning of a smaller
student model.

## Architecture

```
                Cloudflare R2                          Cloudflare R2
            (legal source docs)                  (translation pairs JSONL)
                     |                                       ^
                     v                                       |
            +------------------+        +--------------------+--------------+
            |  ingest.r2_client|        | translate.pipeline                |
            |  - list/pull docs|------->| - chunk by clause/section         |
            |  - chunk         |        | - prompt OLMo 3 Instruct          |
            +------------------+        | - write versioned pair records    |
                                        +--------------------+--------------+
                                                             |
                                                             v
                                                  +----------+-----------+
                                                  | train.sft            |
                                                  | - load pairs from R2 |
                                                  | - SFT OLMo 2 1B      |
                                                  +----------------------+
```

## Models

| Role        | Model                          | Size | License    |
|-------------|--------------------------------|------|------------|
| Translator  | `allenai/Olmo-3-7B-Instruct`   | 7B   | Apache 2.0 |
| Student v1  | `allenai/OLMo-2-0425-1B`       | 1B   | Apache 2.0 |

The translator is swappable with `Olmo-3.1-32B-Instruct` for higher-quality
pairs once the pipeline is validated end to end.

## Storage

- **Source bucket** (read-only): legal documents (PDF, HTML, TXT).
- **Pairs bucket** (read/write): JSONL records, one per chunk, schema:
  ```json
  {
    "id": "<sha256 of source_text>",
    "source_uri": "r2://legal-source/foo.pdf#section=3.2",
    "source_text": "...",
    "translation": "...",
    "translator_model": "allenai/Olmo-3-7B-Instruct",
    "prompt_version": "v1",
    "created_at": "2026-05-10T00:00:00Z"
  }
  ```

## Layout

```
melilo/
  config.py          # env-driven settings (R2 creds, model ids)
  ingest/r2_client.py
  translate/prompts.py
  translate/pipeline.py
  train/sft.py
scripts/
  ingest.py          # pull + chunk + queue
  translate.py       # run translator over queued chunks
  train.py           # SFT the student on accumulated pairs
```

## Setup

```bash
cp .env.example .env  # fill in R2 credentials
pip install -e .
```

## License

Apache 2.0. Derivative of OLMo (Allen AI), also Apache 2.0.
