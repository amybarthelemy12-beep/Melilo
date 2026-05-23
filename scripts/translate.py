"""Run the translator over a single R2 source key. Pair record goes to BOTH
R2 (immutable archive) and Neon (query layer), same as the batch backfill.

Usage:
    melilo-translate --bucket public --source-key cases/foo.pdf \
        --task pirac --source-type case
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from melilo.config import SOURCE_BUCKETS, settings
from melilo.ingest.extract import extract
from melilo.ingest.r2_client import fetch_source, write_pairs_jsonl
from melilo.store import bootstrap_schema, upsert_pairs
from melilo.translate.pipeline import translate_document


TASKS = ("pirac", "brief", "summary", "section_walkthrough")
SOURCE_TYPES = ("case", "statute", "bill", "regulation", "declassified")


def _load_translator():
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(settings.translator_model)
    model = AutoModelForCausalLM.from_pretrained(
        settings.translator_model, device_map="auto", torch_dtype="auto"
    )

    def _call(messages: list[dict]) -> str:
        prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tok(prompt, return_tensors="pt").to(model.device)
        out = model.generate(**inputs, max_new_tokens=2048, do_sample=False)
        return tok.decode(out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True).strip()

    return _call


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bucket",
        required=True,
        choices=SOURCE_BUCKETS,
        help="Which source bucket the doc lives in: public or internal.",
    )
    parser.add_argument("--source-key", required=True, help="R2 key in the chosen source bucket")
    parser.add_argument(
        "--task",
        required=True,
        choices=TASKS,
        help=(
            "Output task. pirac/brief: cases only. summary: any source type. "
            "section_walkthrough: statutes, bills, regulations, declassified."
        ),
    )
    parser.add_argument("--source-type", required=True, choices=SOURCE_TYPES)
    parser.add_argument(
        "--out-key",
        default=None,
        help="R2 archive key. Defaults to pairs/<task>/<timestamp>/<bucket>/<source_key>.jsonl",
    )
    args = parser.parse_args()

    bootstrap_schema()

    doc = fetch_source(bucket_role=args.bucket, key=args.source_key)
    text = extract(doc.key, doc.body)

    translator = _load_translator()
    records = list(
        translate_document(
            text=text,
            translator=translator,
            task_type=args.task,
            source_type=args.source_type,
            source_bucket=args.bucket,
            source_key=args.source_key,
        )
    )

    archive_key = args.out_key or (
        f"pairs/{args.task}/"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}/"
        f"{args.bucket}/{args.source_key}.jsonl"
    )
    # R2 first, then Neon. See backfill.py for the rationale.
    write_pairs_jsonl(archive_key, records)
    inserted = upsert_pairs(records)
    print(
        f"wrote {len(records)} {args.task} pairs to R2 ({archive_key}) "
        f"and Neon ({inserted} new rows)"
    )


if __name__ == "__main__":
    main()
