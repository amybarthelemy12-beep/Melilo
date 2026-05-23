"""Supervised fine-tuning entry point for the Melilo student model.

The student is trained multi-task: pirac, brief, summary, and section_walkthrough
examples are mixed into one dataset. The task instruction lives in the user turn
(via the same `build_messages` the translator uses) so at inference time the
caller picks behavior purely by prompt — no separate heads, no task-id embeddings.

Pairs are pulled from Neon (the query layer). Filtering by prompt_version is on
by default — mixing pairs across prompt revisions corrupts the training signal.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from melilo.config import settings
from melilo.store import iter_pairs
from melilo.translate.prompts import build_messages


@dataclass
class TrainConfig:
    output_dir: str = "checkpoints/melilo-v0"
    epochs: int = 1
    learning_rate: float = 2e-5
    per_device_batch_size: int = 4
    gradient_accumulation_steps: int = 8
    max_seq_length: int = 4096
    # Dataset filters — all optional; None means "no filter on this column".
    prompt_version: str | None = None         # defaults to settings.prompt_version
    task_type: str | None = None
    source_type: str | None = None
    human_reviewed_only: bool = False
    training_set_tag: str | None = None       # written to pairs.training_set on use


def format_example(record: dict) -> dict:
    """Turn a pair record into a chat-format SFT example. Reuses the live prompt
    builder so SFT and inference stay byte-identical — bumping a prompt automatically
    re-shapes training data on the next run."""
    task_type = record["task_type"]
    source_type = record.get("source_type", "case")
    messages = build_messages(
        record["source_text"], task_type=task_type, source_type=source_type
    )
    messages.append({"role": "assistant", "content": record["translation"]})
    return {"messages": messages}


def _stream_examples(cfg: TrainConfig) -> Iterable[dict]:
    pv = cfg.prompt_version or settings.prompt_version
    for rec in iter_pairs(
        task_type=cfg.task_type,
        source_type=cfg.source_type,
        prompt_version=pv,
        human_reviewed_only=cfg.human_reviewed_only,
    ):
        yield format_example(rec)


def run(cfg: TrainConfig) -> None:
    # Imports kept local so the CLI stays import-light when only ingesting.
    from datasets import Dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import SFTConfig, SFTTrainer

    tokenizer = AutoTokenizer.from_pretrained(settings.student_model)
    model = AutoModelForCausalLM.from_pretrained(settings.student_model)

    # Materializing into memory is fine for v1 — Postgres iter handles streaming
    # on its end; the HF Dataset wants a list. Swap to `from_generator` if the
    # corpus outgrows RAM.
    ds = Dataset.from_list(list(_stream_examples(cfg)))

    sft_cfg = SFTConfig(
        output_dir=cfg.output_dir,
        num_train_epochs=cfg.epochs,
        learning_rate=cfg.learning_rate,
        per_device_train_batch_size=cfg.per_device_batch_size,
        gradient_accumulation_steps=cfg.gradient_accumulation_steps,
        max_seq_length=cfg.max_seq_length,
        bf16=True,
        logging_steps=10,
        save_strategy="epoch",
    )
    SFTTrainer(model=model, tokenizer=tokenizer, args=sft_cfg, train_dataset=ds).train()
