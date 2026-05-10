"""Run the translator over a single R2 source key and write a pair JSONL.

This is a thin v0 driver - takes one document, chunks it, calls the translator
callable, writes the resulting records to the pairs bucket. Batching and
parallelism land once we wire up vLLM.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from melilo.config import settings
from melilo.ingest.extract import extract
from melilo.ingest.r2_client import fetch_source, write_pairs_jsonl
from melilo.translate.pipeline import chunk_text, translate_chunks


def _load_translator():
    """Default HF transformers translator. Returns a callable(messages) -> str."""
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(settings.translator_model)
    model = AutoModelForCausalLM.from_pretrained(
        settings.translator_model, device_map="auto", torch_dtype="auto"
    )

    def _call(messages: list[dict]) -> str:
        prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tok(prompt, return_tensors="pt").to(model.device)
        out = model.generate(**inputs, max_new_tokens=1024, do_sample=False)
        return tok.decode(out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True).strip()

    return _call


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-key", required=True, help="R2 key in the source bucket")
    parser.add_argument(
        "--out-key",
        default=None,
        help="R2 key in the pairs bucket. Defaults to pairs/<timestamp>/<source>.jsonl",
    )
    args = parser.parse_args()

    doc = fetch_source(args.source_key)
    text = extract(doc.key, doc.body)
    chunks = list(chunk_text(source_uri=f"r2://{settings.r2_source_bucket}/{doc.key}", text=text))

    translator = _load_translator()
    records = list(translate_chunks(chunks, translator))

    out_key = args.out_key or (
        f"pairs/{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}/{doc.key}.jsonl"
    )
    write_pairs_jsonl(out_key, records)
    print(f"wrote {len(records)} pairs -> r2://{settings.r2_pairs_bucket}/{out_key}")


if __name__ == "__main__":
    main()
